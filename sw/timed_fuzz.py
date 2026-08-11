#!/usr/bin/env python3
"""timed_fuzz -- the fuzz bank's `chip_rows`, replayed CLOCK BY CLOCK through
the TIMED simulator (campaign `ucsim-t`, stage T3).

`sw/ucsim_fuzz.py` replays the same banks FUNCTIONALLY: it regenerates each
image, verifies its sha, runs the architectural simulator and compares the
ordered bus TRANSACTION stream.  This harness runs the same seeds through
`v30sim timed-boot` from RESET and compares the PER-CLOCK PIN ROWS against the
socket capture the bank stores.

U3: the harness now has TWO ENGINE LEGS, selected with `--core`:

  --core sim     (default)  `sim/v30sim timed-boot`, the C++ timed model
  --core ucore              the ROM-driven RTL core in the Verilator TB
                            (`hdl/tb/obj_dir_ucore/Vtb_v30_core`, +bootimg)
  --core fsm                the original FSM RTL core (`obj_dir`), same driver

The ENGINE is the only thing the flag changes.  The regeneration path and its
sha gate, the comparison window, the column policy, the scored-population
`excuse()` rules, the population tags and the report format are shared code and
are not parameterised by the leg, so a number moving between legs is the PART's
rendering and never the harness's.

Two things are necessarily engine-NATIVE and are named here rather than hidden:

  * the WAIT input.  The model takes `--waits` / `--wmax --wseed`; the TB takes
    `+waits` / `+wrand=1 +wmax +wseed`.  Both drive the SAME 16-bit Galois LFSR
    (poly 0xB400, seeded from wseed, one draw per bus cycle at T1 entry,
    n = (draw[7:0]*(wmax+1))>>8) -- the TB's copy carries the standing
    "MUST stay byte-for-byte equivalent to the mirror in hdl/rtl/nec_bus.sv"
    comment, and the phase is checked empirically by the wrand wait classes
    scoring like the fixed ones rather than collapsing.
  * the EXTERNAL EVENT.  The model has no pin scheduler, so `--evt-replay`
    REPLAYS the capture's own acknowledge positions into it (`evt_directive`).
    The TB has the rig's scheduler in it, so it is given the rig's own
    directive -- the identical `(anchor_linear, delay, hold, pin)` tuple
    `fuzz_campaign._evt_tuple` handed the board -- and PREDICTS where the
    acknowledge lands.  Same axis, same seed record, strictly the harder side
    for the RTL.

Three things are inherited rather than re-invented, deliberately:

  * the REGENERATION path (`ucsim_fuzz.regen`) and its sha256 gate -- a drift
    is a hard failure, because the image the simulator would run is then not
    the image the chip ran;
  * the COMPARISON WINDOW (`ucsim_fuzz.window_of`) -- the done-shrunk window
    the banks themselves were built with;
  * the COLUMN POLICY (`fuzz_classify.diff_rows`) -- byte for byte the policy
    the banks' own `first_bad` / `bad_rows` were computed with, which is the
    same masking family as `check_core` / `timed_gate` (`bs_late` and `rd_n`
    are WITHIN-CYCLE pulses read at a fixed sampling edge and carry no
    independent content -- T2b 12.1 -- so neither side compares them; AD is
    compared as an ADDRESS at T1 and as DATA at T2/T3 only, never on a TI or
    T4 clock, where the multiplexed pins are sampled at a different
    half-cycle).

WAIT VECTORS are rebuilt from the bank's own `waits` record: a fixed level
goes to `--waits`, and a random one to `--wmax/--wseed`, which drives the
model's copy of the rig's Galois LFSR (poly 0xB400, drawn once per bus cycle
at T1 entry -- ucsim_t_provenance.md 11.1, validated end to end by the ENTER
wrand slices).

Usage:
  timed_fuzz.py [--bank mc1,mc2,t30-raw,t30-brkem] [--limit N] [--jobs N]
                [--pilot N] [--report out.json] [--details N] [--all]
                [--core sim|ucore|fsm] [--native-only] [--current-silicon]
"""

import argparse
import gzip
import hashlib
import json
import os
import random
import subprocess
import sys
import tempfile
import time
from collections import Counter, defaultdict
from multiprocessing import Pool
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

import simbin                                          # noqa: E402

# U1: the C++ model THROUGH THE ARTIFACT/RECEIPT LAYER.  `simbin.SIM` is
# `sim/build/v30sim`, the binary `simbin.recipe()` declares; nothing here
# resolves the model by bare path any more.  See sw/simbin.py.
SIM = simbin.SIM
ROM = ROOT / "docs" / "V20BITS.TXT"
BANK = ROOT / "tests" / "v30" / "fuzz_bank"
H7_RECAP = ROOT / "sw" / "testdata" / "sm3-h7rep" / "capture.json"
H7_RECAP_ALL = ROOT / "sw" / "testdata" / "sm3-h7rep" / "control_all.json"

import fuzz_classify as fc                            # noqa: E402
import fuzz_accept as fa                              # noqa: E402
import ucsim_fuzz as uf                               # noqa: E402
import bank_status as bs                              # noqa: E402

# The v1 corpus.  ⚠ ALL FOUR ARE `status: SUPERSEDED` SINCE 2026-08-09
# (`docs/notes/invalidation_ledger.md` § SUP-1), so `seeds_of` returns NOTHING
# for them unless `--include-superseded` is given.  The list is kept, and kept
# as the `--bank` default, so the historical command line reproduces the
# historical population EXACTLY when the flag is added -- retirement is not
# deletion.  `bank_status.bank_cids()` is the ACTIVE population.
BANKS = ["mc1", "mc2", "t30-raw", "t30-brkem"]


# --------------------------------------------------------------------------- #
# the scored population (see the PRE-REGISTRATION in ucsim_t_provenance.md 13)
# --------------------------------------------------------------------------- #
def excuse(entry, recs, win, evt_replay=False):
    """Why this seed is OUT of the scored population, or None.

    Both exclusions are declared BEFORE the run and are properties of the
    CAPTURE, not of the model's answer on it.

    S9b: with `evt_replay` the EVT exclusion becomes a POPULATION TAG rather
    than an exclusion -- the seed is scored and reported in its own addendum
    table, and the REGISTERED 1,702-seed denominator is what the default
    (flag off) run still produces, byte for byte.  OPEN_BUS is untouched: it
    stays an exclusion in BOTH populations, and it is tested FIRST for an EVT
    seed so the two tables cannot overlap."""
    if entry.get("evt") and not evt_replay:
        # Interrupt / INTA timing under waits is an explicit scope exclusion
        # of the whole campaign (plan, T1..T4) -- no law for it is measured
        # and no gate may pretend one is.
        return "EVT"
    if len(fa.open_bus_escape_metrics(recs, win)[0]) >= 8:
        # The program made >= 8 CODE fetches above linear 0x10000 -- it left
        # the loaded 64 KB image.  Detected with the bank's OWN detector.
        #
        # ⚠ ERRATUM 2026-08-11, PROSE ONLY -- THE NAME AND THE POPULATION ARE
        # UNCHANGED, TO THE SEED.  This comment used to say the chip "is
        # reading the rig's OPEN BUS (ad_data == ad_addr feedthrough)" and that
        # the divergence "is the RIG, not the model".  THERE IS NO OPEN BUS ON
        # THIS RIG: `hdl/rtl/test_mem.sv` decodes `addr[15:1]` and mirrors the
        # image across the whole 1 MB space, so BOTH legs read defined image
        # bytes out of image, and the `ad_data == ad_addr` test is the address
        # phase of a multiplexed bus (a tautology -- 140,741 of 140,741 chip
        # CODE T1 rows).  The exclusion is retained under its registered name
        # because it is a PRE-REGISTERED population of the v1 campaign and
        # every ratchet quoting `OPEN_BUS N` is scored against it; re-opening
        # it is a different piece of work from retiring the accept rule
        # (`sw/fuzz_accept.py` tombstone, 2026-08-11).  What is withdrawn is
        # the claim that these seeds diverge BECAUSE of the rig.
        #
        # THE PREDICATE MOVED, THE POPULATION DID NOT.  This used to call
        # `fuzz_classify._open_bus_escaped_before`, which fuzz-v2 T4 replaced
        # with a PHYSICAL-OFFSET containment falsifier (`escaped_code_region`)
        # for the v2 image map.  That new predicate would exclude essentially
        # every seed of THIS (v1, discarded) bank, whose code lives nowhere
        # near the v2 code region, so it is deliberately NOT used here.
        # `fuzz_accept.open_bus_escape_metrics` is the v1-era measurement the
        # deleted predicate mirrored, at its own default threshold of 8 -- the
        # same rows, the same test, the same count, so this exclusion selects
        # exactly the seeds it selected before.
        return "OPEN_BUS"
    return None


def native_exclusion(entry, recs, win):
    """Why this capture is outside a NATIVE-only score, or ``None``.

    The dedicated ``t30-brkem`` bank is an emulation-mode population by
    construction.  Outside it, use the part's own mode-status pin: PS3 is 1
    on a CODE T1 exactly while the chip is executing 8080-mode instructions
    (M9; ``ucsim_t_provenance.md``).  Requiring CODE+T1 avoids treating the
    separately-booked retained PS3 value on a few stack writes as mode entry.

    This predicate reads only the capture.  It never consults the engine's
    answer, and a native seed that merely contains BRKEM bytes remains in the
    score unless the chip actually enters emulation mode inside the window.
    """
    if entry.get("cid") == "t30-brkem":
        return "8080_BANK"
    for r in recs[:min(win, len(recs))]:
        if r.get("t_state", r.get("t")) == 1 and \
                r.get("bs_early") == 4 and (int(r.get("ps", 0)) & 8):
            return "8080_EXECUTED"
    return None


_stale_h7_keys = None


def stale_current_silicon(entry):
    """Whether the checked-in silicon recapture contradicts this NMI trace.

    ``sm3-h7rep/capture.json`` is the retained 10-repeat socket recapture of
    the complete banked NMI gap-12 population.  ``control_all.json`` is the
    three-repeat recapture of all 193 NMI seeds.  A member is stale only when
    its identity matches (cid, k, image hash) and every fresh repetition moved
    later than its banked gap.  This selects exactly the 30 floor captures
    (0/300 reproduced) plus the sole contradicted neighbour, ``mc1/2468``
    (0/3 reproduced); the other 162 non-floor seeds reproduced exactly
    (``ucore_provenance.md`` sec.81.B).

    This is deliberately an annotation unless ``--current-silicon`` is
    requested.  Thus the historical registered gate and report remain
    reproducible, while a score whose stated target is current silicon cannot
    silently count captures current silicon refuted.
    """
    global _stale_h7_keys                                  # noqa: PLW0603
    if _stale_h7_keys is None:
        floor = json.loads(H7_RECAP.read_text())
        controls = json.loads(H7_RECAP_ALL.read_text())
        floor_keys = {
            (s.get("cid"), int(s.get("k")), s.get("image_sha256"))
            for s in floor.get("seeds", [])
            if s.get("banked", {}).get("gap") == 12
            and len(s.get("reps", [])) == 10
            and all(r.get("gap") is not None and r["gap"] > 12
                    for r in s.get("reps", []))
        }
        control_keys = {
            (s.get("cid"), int(s.get("k")), s.get("image_sha256"))
            for s in controls.get("seeds", [])
            if len(s.get("reps", [])) == 3
            and s.get("banked", {}).get("gap") is not None
            and all(r.get("gap") is not None
                    and r["gap"] > s["banked"]["gap"]
                    for r in s.get("reps", []))
        }
        _stale_h7_keys = floor_keys | control_keys
    return (entry.get("cid"), int(entry.get("k", -1)),
            entry.get("image_sha256")) in _stale_h7_keys


def banked_wvec(entry):
    """task #38 -- the seed's PER-ACCESS WAIT VECTOR, from the bank's own
    literal record, or None.

    THE INTEGRITY CHECK IS HERE AND NOT IN A SEPARATE TOOL, because this is
    the function every scoring leg goes through: `wvec_hex` is the vector the
    rig was handed and `wvec_sha256` is what it hashed to when it was handed
    over.  If the two disagree the record has been edited or truncated since
    the capture, and an engine scored against it would be answering a question
    nobody asked.  That is INV-1's shape exactly (a capture taken under a
    directive other than the one the bank records), so it RAISES rather than
    warning."""
    import wvec_shapes as wv                              # noqa: PLC0415
    hx = entry.get("wvec_hex")
    if not hx:
        return None
    v = wv.from_hex(hx)
    want = entry.get("wvec_sha256")
    got = wv.sha256_of(v)
    if want and want != got:
        raise ValueError(f"wvec_sha256 mismatch: banked {want[:16]}… "
                         f"recomputed {got[:16]}…")
    if entry.get("wvec_n") and len(v) != int(entry["wvec_n"]):
        raise ValueError(f"wvec length {len(v)} != banked wvec_n "
                         f"{entry['wvec_n']}")
    return v


def wait_args(entry, td):
    # replay > random > uniform, the rig's own priority order
    # (nec_bus.sv / tb_v30_core.sv / biu_timed.cpp all three).
    v = banked_wvec(entry)
    if v is not None:
        import wvec_shapes as wv                          # noqa: PLC0415
        # DECIMAL: `sim/timed_runner.cpp` reads this file with fscanf("%d").
        # The TB's file is HEX.  They are not interchangeable and the failure
        # is silent -- see wvec_shapes' property (1).
        return [f"--wvec={wv.write_sim(Path(td) / 'wvec_sim.txt', v)}"]
    w = entry.get("waits") or {}
    if w.get("wrand"):
        return [f"--wmax={int(w.get('wmax', 0))}",
                f"--wseed={int(w.get('wseed', 0))}"]
    return [f"--waits={int(w.get('fixed') or 0)}"]


def tb_bin(core):
    """The Verilator TB binary for an RTL leg -- `sw/check_boot._bin`'s rule,
    unchanged: the FSM core is `obj_dir`, every other core is `obj_dir_<core>`."""
    d = "obj_dir" if core == "fsm" else f"obj_dir_{core}"
    return ROOT / "hdl" / "tb" / d / "Vtb_v30_core"


def tb_wait_args(entry, td):
    """`wait_args` for the TB: the SAME bank record, the same LFSR, the TB's
    spelling.  +wseed is read with %h (check_seq.run_tb's convention)."""
    v = banked_wvec(entry)
    if v is not None:
        import wvec_shapes as wv                          # noqa: PLC0415
        # HEX: the TB reads this file with $readmemh.  See wait_args above.
        return [f"+wvec={wv.write_tb(Path(td) / 'wvec_tb.hex', v)}"]
    w = entry.get("waits") or {}
    if w.get("wrand"):
        return ["+wrand=1", f"+wmax={int(w.get('wmax', 0))}",
                f"+wseed={int(w.get('wseed', 0)):04x}"]
    return [f"+waits={int(w.get('fixed') or 0)}"]


def rig_hold(entry, mode="banked"):
    """The pin HOLD, in the three spellings that exist.

    `banked` -- the number the seed record stores, i.e. what the HOST ASKED
    FOR.  This is what every standing scoring of this harness used, so it is
    the default and the registered ledger is reproducible with it.

    `reg8` -- the number the PART WAS GIVEN in the 8-BIT ERA.  The rig's hold
    was an EIGHT-BIT register field (`hdl/rtl/hps_axi_slave.sv`:
    `evt_hold <= wdata[23:16]`, carried as `input [7:0] evt_hold` into
    `hdl/rtl/nec_bus.sv`'s scheduler), so a banked hold of 300 reached the
    socket as 300 & 0xFF = 44 clocks.  Both engine legs are told the same
    thing, so this is a property of the DRIVER and never of the part -- the
    same class of correction as the comparison window
    (ucore_provenance.md sec.42.2).  The register is 12 bits since 2026-08-04;
    this mode remains because the 760 seeds captured BEFORE that are still on
    disk and reading them any other way misstates what the socket did.

    `applied` -- the seed's OWN record of what its rig could apply.  Captures
    taken after the widen carry `evt.hold_bits` / `evt.hold_applied`
    (`fuzz_campaign.build`); this mode uses them and falls back to `reg8` for
    a record that predates the field, because every such record was taken on
    the 8-bit rig.  This is the mode that stops the width from having to be
    re-derived from whatever the RTL happens to say today.

    It matters to a PREDICTING engine and barely at all to a REPLAYING one:
    with INT level-asserted for 300 clocks instead of 44 an engine that
    computes its own recognition re-enters the handler two to four times
    where the socket entered once."""
    e = entry.get("evt") or {}
    h = int(e.get("hold", 0))
    if mode == "reg8":
        return h & 0xFF
    if mode == "applied":
        if "hold_applied" in e:
            return int(e["hold_applied"])
        return h & 0xFF          # pre-widen capture: the 8-bit rig, by date
    return h


def f46_invalidated(entry):
    """INV-1 (docs/notes/invalidation_ledger.md): was this capture taken under
    a directive the RIG COULD NOT APPLY?

    DERIVED, never listed.  A banked seed records `evt.hold` -- what the HOST
    ASKED FOR -- and, since 2026-08-04, `evt.hold_bits` -- what the RIG THAT
    TOOK THE CAPTURE could hold.  A record with no `hold_bits` was taken on the
    8-bit rig, by date: the field was added in the same commit that widened the
    register.  If the two disagree, the socket was given a DIFFERENT directive
    from the one the bank records, and scoring a PREDICTING engine against that
    capture asks it to reproduce something it was never told.

    This is a predicate and not a seed list on purpose.  A list can drift away
    from what it describes and a rename can be undone silently; a derivation
    from the record cannot, and it self-heals -- a re-capture on the widened rig
    banks `hold_bits = 12`, and the seed leaves this set by arithmetic.

    TWO LIMBS, and the second was added at SM3 sitting 5 (Codex concern #4).

      (a) REPRESENTABILITY.  `hold` does not fit the rig's register width, so
          the socket was silently given `hold & mask`.  That is F46 exactly.
      (b) APPLICATION.  The record itself says the rig applied something other
          than what the bank asks for (`hold_applied != hold`).  Limb (a) is a
          DERIVATION of limb (b) for the one defect we found; it is not the
          whole of it.  A directive that is perfectly representable and still
          mis-applied -- a scheduler that clamps, a host that rounds, a future
          field the RTL widens again -- passes (a) and is caught only by (b).
          Without this limb such a capture would stay silently SCORED, which is
          the failure mode INV-1 exists to make impossible.

    A record with no `hold_applied` field cannot be tested by (b); it falls
    through to (a), which is the pre-widen behaviour and is correct by date."""
    e = entry.get("evt") or {}
    if not e:
        return False
    h = int(e.get("hold", 0))
    bits = int(e.get("hold_bits", 8))
    if h != (h & ((1 << bits) - 1)):
        return True
    if "hold_applied" in e and int(e["hold_applied"]) != h:
        return True
    return False


def evt_tuple(entry, meta, hold_mode="banked"):
    """The RIG's own event directive for the TB's scheduler -- byte for byte
    `fuzz_campaign._evt_tuple`, i.e. exactly what check_seq.run_chip handed the
    board when this seed was captured.  The TB then PREDICTS the acknowledge;
    nothing from the capture is fed back in."""
    e = entry.get("evt")
    if not e:
        return None
    return (int(meta["anchor_linear"]) & 0xFFFFF, int(e.get("delay", 0)),
            rig_hold(entry, hold_mode), int(e.get("pin", 0)))


def evt_directive(entry, meta, recs, win, hold_mode="banked"):
    """S9b -- the `timed-boot` pin-event replay directive, or None.

    Two coordinates and nothing else, both of them INPUTS:

      the RIG's schedule   the seed's own `evt` axis (pin / delay / hold) plus
                           the fetch anchor `meta["anchor_linear"]` the rig
                           arms on -- exactly the tuple check_seq.run_chip
                           handed the board (`fuzz_campaign._evt_tuple`).
      the CAPTURE's        the ordered bus position of each acknowledge and the
      boundaries           CS:IP the chip's own pushed frame recorded, computed
                           by `ucsim_fuzz.entry_points` / `frame_of` -- the
                           SAME functions the functional replay uses, imported
                           rather than forked.

    `pins` is the rig's static PINS register, which check_seq.run_chip never
    writes: it holds its reset value 0 (hps_axi_slave.sv `poll_n_out <= 0`), so
    POLL_N sits statically LOW and 9B is never busy -- the model's standing
    behaviour with no event at all.
    """
    evt = entry.get("evt")
    if not evt:
        return None
    pin = int(evt.get("pin", 0))
    cstream = uf.chip_stream(recs, win)
    fires = uf.entry_points(cstream, pin)
    frames = [uf.frame_of(cstream, i) for i in fires]
    # A frame the capture window cut short cannot name a boundary; drop it and
    # everything after it rather than guessing one.
    keep = 0
    while keep < len(fires) and frames[keep][0] >= 0:
        keep += 1
    fires, frames = fires[:keep], frames[:keep]
    return {"pin": pin,
            "addr": int(meta["anchor_linear"]) & 0xFFFFF,
            "delay": int(evt.get("delay", 0)),
            "hold": rig_hold(entry, hold_mode),
            "pins": 0,
            "at": fires,
            "cs": [f[0] for f in frames],
            "ip": [f[1] for f in frames]}


def run_sim(image, entry, nrows, td, evt=None):
    img = Path(td) / "img.bin"
    img.write_bytes(bytes(image))
    argv = [str(SIM), "timed-boot", str(ROM), str(img),
            f"--clocks={nrows}", "--ndjson"] + wait_args(entry, td)
    if evt is not None:
        ep = Path(td) / "evt.json"
        ep.write_text(json.dumps(evt))
        argv.append(f"--evt={ep}")
    p = subprocess.run(argv, capture_output=True)
    rows = []
    for l in p.stdout.decode().splitlines():
        if not l.startswith("{"):
            continue
        o = json.loads(l)
        if "t" in o:
            rows.append(o)
    return rows, p.stderr.decode()


def run_tb(image, entry, nrows, td, core, evt=None):
    """The RTL leg.  +bootimg replay -- no backdoor, the image's own loader stub
    runs in the core, records start at the RESET-release edge, which is the
    frame `chip_rows` is stored in and the frame `timed-boot` emits.  +mirror=1
    is the capture board's 64 KB wiring and is the SAME memory the model is
    given (`sim/timed_runner.cpp:432  biu.set_mirror(true)`)."""
    img = Path(td) / "img.hex"
    outp = Path(td) / "out.txt"
    img.write_text("\n".join(f"{b:02x}" for b in bytes(image)) + "\n")
    argv = [str(tb_bin(core)), f"+bootimg={img}", f"+bootn={nrows}",
            "+mirror=1", f"+out={outp}"] + tb_wait_args(entry, td)
    if evt is not None:
        a, d, h, pin = evt
        argv += [f"+evaddr={a:05x}", f"+evdelay={d}", f"+evhold={h}",
                 f"+evpin={pin}"]
    p = subprocess.run(argv, capture_output=True, timeout=600)
    so = p.stdout.decode()
    if "BOOT DONE" not in so:
        return [], (so[-200:] + " " + p.stderr.decode()[-200:]).strip()
    rows = []
    for line in outp.read_text().splitlines():
        f = line.split()
        if f and f[0] == "r":
            rows.append({"t": int(f[1]), "bs_early": int(f[2]),
                         "qs": int(f[3]), "ube_n": int(f[4]),
                         "ad_addr": int(f[5], 16), "ad_data": int(f[6], 16),
                         "ps": int(f[7], 16)})
    # F48/U4: a SUCCESSFUL run can still have left the regime the store-bound
    # proof covers -- the assertions are `$warning` now, so they no longer take
    # the run down.  Carry those lines out (deduplicated: a saturating store
    # warns on every completion, and thousands of identical lines are noise, not
    # information) so the report can COUNT them.  Everything else on stderr is
    # dropped exactly as before, so no other caller sees a behaviour change.
    # Verilator writes `$warning` to STDOUT (measured), not stderr; and it
    # stamps every line with the sim time, so dedup on the MESSAGE -- the part
    # after the `] ` -- or a saturating store contributes one "unique" line per
    # completion and the dedup does nothing.
    warn = sorted({ln.split("] ", 1)[-1].strip() for ln in so.splitlines()
                   if "completed-read store overflow" in ln
                   or "rd_done_cnt saturated" in ln})
    return rows, "\n".join(warn)


def first_kind(d):
    """One-word family for a RowDiff -- what parted FIRST, on the first row
    that parted at all."""
    if d.other:
        return d.other[0].split()[0]
    return "qsflicker" if d.flicker else "qs"


def one(path, evt_replay=False, core="sim", hold_mode="banked",
        native_only=False, current_silicon=False):
    entry = json.loads(gzip.decompress(Path(path).read_bytes()))
    out = {"path": str(path), "cid": entry.get("cid"), "k": entry.get("k"),
           "verdict": entry.get("verdict"), "reason": entry.get("promoted_reason"),
           "waits": entry.get("waits"), "evt": entry.get("evt"),
           "wvec": entry.get("wvec")}
    try:
        image, meta, g, sha = uf.regen(entry)
    except Exception as e:                                    # noqa: BLE001
        out["cat"] = "REGEN_ERROR"
        out["detail"] = str(e)[:200]
        return out
    if sha != entry["image_sha256"]:
        out["cat"] = "GEN_DRIFT"
        out["detail"] = f"{sha[:16]} != {entry['image_sha256'][:16]}"
        return out

    recs = entry["chip_rows"]
    win = uf.window_of(recs)
    if native_only:
        out["native_exclusion"] = native_exclusion(entry, recs, win)
    if current_silicon:
        out["stale_current_silicon"] = stale_current_silicon(entry)
    ex = excuse(entry, recs, win, evt_replay)
    armed = evt_replay and not ex
    with tempfile.TemporaryDirectory() as td:
        if core == "sim":
            evt = evt_directive(entry, meta, recs, win, hold_mode) \
                if armed else None
            if evt is not None:
                out["fires"] = len(evt["at"])
            rows, err = run_sim(image, entry, len(recs), td, evt)
        else:
            ev = evt_tuple(entry, meta, hold_mode) if armed else None
            if ev is not None:
                out["fires"] = None      # the RTL predicts them; not replayed
            rows, err = run_tb(image, entry, len(recs), td, core, ev)
    out["stderr"] = err.strip()[:200]
    out["pop"] = "EVT" if entry.get("evt") else "REG"
    out["invalidated"] = f46_invalidated(entry)
    if not rows:
        # The ENGINE produced nothing (an RTL assertion `$stop`, a driver
        # abort).  The scored population is a property of the CAPTURE
        # (`excuse` above) and must NOT move with the engine, so:
        #   * a seed the capture already excuses stays excused, and
        #   * a seed inside the population stays inside it and scores as a
        #     total divergence.
        # Silently dropping it would hand the failing engine a smaller
        # denominator, i.e. a free pass.  Counted separately so it cannot hide.
        out["engine_error"] = True
        out["cat"] = ex or "DIVERGE"
        out["excused"] = ex
        if ex:
            return out
        out["n"] = win
        out["ndiff"] = win
        out["chip_rows"] = len(recs)
        out["sim_rows"] = 0
        out["first_bad"] = 0
        out["kind"] = "abort"
        out["detail"] = out["stderr"]
        out["flicker_only"] = False
        out["exact"] = False
        return out
    dr = fc.diff_rows(recs, rows)
    out["n"] = dr.n
    out["ndiff"] = len(dr.rows)
    out["chip_rows"] = len(recs)
    out["sim_rows"] = len(rows)
    if dr.rows:
        d0 = dr.rows[0]
        out["first_bad"] = d0.i
        out["kind"] = first_kind(d0)
        out["detail"] = (d0.qs_txt or "") + " " + " ".join(d0.other)
        # a diff stream that is nothing but the documented F/S QS flicker
        out["flicker_only"] = all(r.flicker for r in dr.rows)
    else:
        out["first_bad"] = dr.n
        out["kind"] = "-"
        out["flicker_only"] = False
    out["exact"] = not dr.rows
    out["cat"] = ex or ("EXACT" if out["exact"] else "DIVERGE")
    out["excused"] = ex
    # S9b population tag: which of the two tables this seed belongs to.  The
    # REGISTERED population is exactly the seeds with no `evt` axis (set above,
    # before the engine-abort return, so both paths carry it).
    return out


# --------------------------------------------------------------------------- #
def seeds_of(banks, include_superseded=False):
    """The seed paths for the named banks, STATUS-FILTERED.

    A campaign retired with `status: SUPERSEDED` in its own `manifest.json`
    (`sw/bank_status.py`, `docs/notes/invalidation_ledger.md` § SUP-1) is out of
    the default population even when it is named here -- naming a bank selects
    it, it does not un-retire it.  Nothing is moved or deleted and
    `include_superseded=True` returns it in full, which is how a pre-v2 figure
    is re-derived.  The exclusion is ANNOUNCED on stderr, never silent: a
    measurement tool that suddenly scores 0 seeds must say why.
    """
    out, dropped = bs.seed_paths(include_superseded=include_superseded,
                                 cids=list(banks))
    note = bs.dropped_note(dropped)
    if note:
        print(f"timed_fuzz: {note}", file=sys.stderr, flush=True)
    return [str(p) for p in out]


def axes_of(path):
    """(pop, pin, wait-class) for a banked seed, read from the record itself.
    Used only to SELECT a population / a stratified pilot -- never to score."""
    e = json.loads(gzip.decompress(Path(path).read_bytes()))
    ev = e.get("evt")
    return ("EVT" if ev else "REG", int(ev["pin"]) if ev else -1,
            wait_class(e))


def wait_class(entry):
    """The seed's wait-source stratum label.  ONE definition, used by the
    stratifier and by the report, so a stratum cannot be named two things."""
    v = entry.get("wvec")
    if v:
        return f"wvec-{v.get('shape', '?')}"
    w = entry.get("waits") or {}
    return f"wrand{w.get('wmax')}" if w.get("wrand") else \
        f"fix{w.get('fixed') or 0}"


def stratify(paths, n, seed=20260802, keys=None):
    """A stratified pilot: proportional over the strata, deterministic.

    Default strata = the bank.  `keys` (path -> tuple) refines them; the S9b
    EVT pilot uses (bank, pin, wait class) so the pilot cannot miss the NMI or
    the waited slices."""
    strata = defaultdict(list)
    for p in paths:
        b = Path(p).parent.parent.name
        if keys:
            b = (b,) + tuple(keys[p])
        strata[b].append(p)
    rr = random.Random(seed)
    picked = []
    if keys:
        # Refined strata are many and small, so a concatenation truncated at
        # `n` would return the first stratum only: draw ROUND-ROBIN, which
        # keeps every stratum represented at any n.  (The default, unrefined
        # path below is untouched -- it is the T3 pre-registration's own.)
        pools = []
        for b in sorted(strata, key=repr):
            pool = sorted(strata[b])
            rr.shuffle(pool)
            pools.append(pool)
        # ...and the STRATUM ORDER is shuffled too, so that a pilot smaller
        # than the number of strata is not just the alphabetically first ones
        # (which is one bank).
        rr.shuffle(pools)
        i = 0
        while len(picked) < n and any(len(p) > i for p in pools):
            for p in pools:
                if i < len(p):
                    picked.append(p[i])
                    if len(picked) >= n:
                        break
            i += 1
        return picked[:n]
    for b in sorted(strata, key=repr):
        take = max(1, round(n * len(strata[b]) / len(paths)))
        pool = sorted(strata[b])
        rr.shuffle(pool)
        picked += pool[:take]
    return picked[:n]


def main():
    # U1 / P-2.  EAGERLY, before any loop: `ArtifactError` is a
    # `RuntimeError`, and a per-case `except Exception` would turn one
    # sentence naming a stale binary into N unreadable case failures.
    simbin.ensure(why=__name__)
    ap = argparse.ArgumentParser()
    ap.add_argument("--bank", default=",".join(BANKS))
    # RETIREMENT IS NOT DELETION.  The four v1 banks named in `--bank`'s default
    # are SUPERSEDED (SUP-1); with this flag they are scored in full and every
    # pre-2026-08-09 figure on this harness is re-derivable byte for byte.
    ap.add_argument("--include-superseded", action="store_true",
                    help="score banks marked SUPERSEDED in their manifest "
                         "(the v1 corpus: mc1, mc2, t30-raw, t30-brkem)")
    # T4: the victory tranche is scored by THIS harness, unchanged -- same
    # regeneration path and sha gate, same window, same column policy.  The
    # only thing --seeddir changes is which directory the records come from.
    ap.add_argument("--seeddir", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--pilot", type=int, default=0)
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 4)
    ap.add_argument("--report", default="")
    ap.add_argument("--details", type=int, default=0)
    # S9b.  OFF by default: `python3 sw/timed_fuzz.py` with no flags is the
    # REGISTERED gate (sec.13.0's population, denominator and policy) and is
    # not touched by this session.  With the flag the EVT seeds are scored too
    # and reported as their OWN table plus a combined figure.
    ap.add_argument("--evt-replay", action="store_true",
                    help="score the EVT seeds through the pin-event replay "
                         "(reported separately; the registered table is "
                         "unchanged)")
    # U3.  The ENGINE, and nothing else.  `sim` is the default so every
    # standing invocation of this harness scores exactly what it scored before.
    ap.add_argument("--core", default="sim", choices=("sim", "ucore", "fsm"),
                    help="replay engine: the C++ timed model (sim) or an RTL "
                         "core in the Verilator TB (ucore / fsm)")
    # U3.  The pin-hold the seed record stores is what the HOST asked for;
    # the rig's register was 8 bits wide (see `rig_hold`), 12 since 2026-08-04.
    # `banked` is the default so every standing number of this harness is
    # reproducible; `reg8` is the 8-bit-era like-for-like directive and applies
    # to BOTH legs identically; `applied` reads the seed's own record.
    ap.add_argument("--rig-hold", default="banked",
                    choices=("banked", "reg8", "applied"),
                    help="pin hold fed to the engine: as banked (the host's "
                         "request, the standing default), truncated to the "
                         "8-bit-era register (what the socket was given), or "
                         "the seed record's own evt.hold_applied")
    ap.add_argument("--pop", default="all", choices=("all", "reg", "evt"),
                    help="restrict to the registered (no-evt) or the EVT "
                         "population; selection only, scoring is unchanged")
    ap.add_argument("--native-only", action="store_true",
                    help="exclude the dedicated BRKEM bank and captures in "
                         "which the chip actually executes CODE with PS3=1 "
                         "(8080 emulation mode); capture-derived, never "
                         "engine-answer-derived")
    ap.add_argument("--current-silicon", action="store_true",
                    help="exclude the 31 banked NMI captures contradicted by "
                         "the checked-in socket recaptures (30 floor-12 seeds "
                         "at 0/300 plus mc1/2468 at 0/3); historical default "
                         "remains unchanged")
    args = ap.parse_args()
    if args.core != "sim" and not tb_bin(args.core).exists():
        sys.exit(f"timed_fuzz: no TB binary at {tb_bin(args.core)}")
    if args.core != "sim":
        # THE SCORER POSTCONDITION (sw/artifact.py).  `.exists()` above is the
        # test the whole vacuous-gate pattern passes; this is the one it does
        # not.  It does NOT rebuild -- 1,702 REGISTERED + 1,008 EVT seeds is
        # exactly the size of run whose number must be attributable to bytes.
        import artifact as art                               # noqa: PLC0415
        art.require(tb_bin(args.core), why=f"timed_fuzz --core {args.core}")
        print(f"timed_fuzz: RTL leg {art.relpath(tb_bin(args.core))}  "
              f"receipt {str(art.receipt_id(tb_bin(args.core)))[:16]}…",
              flush=True)

    paths = sorted(str(x) for x in Path(args.seeddir).glob("*.json.gz")) \
        if args.seeddir else seeds_of([b for b in args.bank.split(",") if b],
                                      include_superseded=args.include_superseded)
    # Selection only.  With --pop all (the registered gate) NOTHING here runs,
    # so the default path -- including the T3 pilot's own stratification -- is
    # byte for byte what it was.
    keys = None
    if args.pop != "all":
        with Pool(args.jobs) as pool:
            ax = pool.map(axes_of, paths, chunksize=16)
        keys = dict(zip(paths, ax))
        want = "EVT" if args.pop == "evt" else "REG"
        paths = [p for p in paths if keys[p][0] == want]
    if args.pilot:
        paths = stratify(paths, args.pilot, keys=keys)
    elif args.limit:
        paths = paths[:args.limit]

    t0 = time.time()
    with Pool(args.jobs) as pool:
        res = pool.starmap(one, [(p, args.evt_replay, args.core,
                                  args.rig_hold, args.native_only,
                                  args.current_silicon) for p in paths],
                           chunksize=4)

    cat = Counter(r["cat"] for r in res)
    # INV-1: a capture taken under a directive the rig could not apply leaves
    # the GATE.  It does not leave the tree, it is not deleted, and it is
    # reported on its own line below -- but nothing gates on it.
    inval = [r for r in res
             if r["cat"] in ("EXACT", "DIVERGE") and r.get("invalidated")]
    nonnative = [r for r in res
                 if r.get("native_exclusion") and
                 r["cat"] in ("EXACT", "DIVERGE")]
    stale = [r for r in res
             if r.get("stale_current_silicon") and
             r["cat"] in ("EXACT", "DIVERGE")]
    all_scored = [r for r in res
                  if r["cat"] in ("EXACT", "DIVERGE")
                  and not r.get("invalidated")
                  and not (args.native_only and r.get("native_exclusion"))
                  and not (args.current_silicon and
                           r.get("stale_current_silicon"))]
    reg = [r for r in all_scored if r.get("pop") != "EVT"]
    evtp = [r for r in all_scored if r.get("pop") == "EVT"]
    eng = {"sim": "the TIMED sim"}.get(args.core, f"the {args.core} RTL core")
    print(f"== timed_fuzz -- fuzz-bank chip_rows through {eng} "
          f"({len(paths)} seeds, {time.time()-t0:.0f} s)")
    print("  categories      " + "  ".join(f"{k}={v}" for k, v in
                                           sorted(cat.items())))
    aborts = [r for r in res if r.get("engine_error")]
    if aborts:
        # Loud by construction: an engine that cannot RUN a seed is scored as a
        # miss on it, and the count is stated on its own line.
        print(f"  ENGINE ABORTS   {len(aborts)}  "
              f"(scored as total divergences; "
              f"{sum(1 for r in aborts if r.get('excused'))} were already "
              f"excused by the capture)")
        for r in aborts[:8]:
            print(f"    {r['cid']}/{r['k']:<6} {r.get('stderr','')[:150]}")
    # F48/U4 -- SEEDS THAT LEFT THE PROVEN REGIME, COUNTED.
    # The EU's completed-read store bound is a theorem over the GRADED corpus
    # and not over arbitrary code (`sw/qdepth_probe.py`; the model's own stores
    # reach 3 and 4 on this very bank).  So the RTL saturates instead of
    # wrapping and warns instead of aborting -- but "warns" is only a gate if
    # somebody counts it, so it is counted here and named in the report.  These
    # seeds are SCORED normally; the line says how many of them ran outside the
    # regime the bound proof covers.
    oor = [r for r in res
           if "completed-read store overflow" in (r.get("stderr") or "")
           or "rd_done_cnt saturated" in (r.get("stderr") or "")]
    if oor:
        print(f"  BOUND WARNINGS  {len(oor)}  (seeds whose completed-read store "
              f"saturated -- OUTSIDE the regime sw/qdepth_probe.py proves; "
              f"scored normally, not excused)")
        for r in oor[:8]:
            print(f"    {r['cid']}/{r['k']:<6} cat={r.get('cat')} "
                  f"ndiff={r.get('ndiff')}/{r.get('n')}")
    if inval:
        ex = sum(1 for r in inval if r["exact"])
        print(f"  INVALIDATED     {len(inval)}  (INV-1 / F46: banked under a "
              f"pin hold the rig could not apply -- NOT SCORED, NOT A GATE; "
              f"their chip_rows are retained and are true captures of the hold "
              f"the rig DID apply.  For reference only, cycle-exact "
              f"{ex}/{len(inval)}.  docs/notes/invalidation_ledger.md)")
    if args.native_only:
        why = Counter(r["native_exclusion"] for r in nonnative)
        print(f"  NON-NATIVE     {len(nonnative)}  (NOT SCORED: "
              + "  ".join(f"{k}={v}" for k, v in sorted(why.items())) + ")")
    if args.current_silicon:
        ex = sum(1 for r in stale if r["exact"])
        print(f"  STALE NMI      {len(stale)}  (NOT SCORED: 31 banked NMI "
              f"captures contradicted by current silicon: floor-12 0/300 "
              f"plus mc1/2468 0/3; historical rows retained; reference "
              f"cycle-exact {ex}/{len(stale)})")
    if args.evt_replay:
        for lbl, grp in (("REGISTERED", reg), ("EVT-unlocked", evtp),
                         ("COMBINED", all_scored)):
            if not grp:
                continue
            ex = sum(1 for r in grp if r["exact"])
            fl = sum(1 for r in grp if r.get("flicker_only"))
            print(f"  {lbl:<14}  cycle-exact {ex}/{len(grp)} "
                  f"({100.0*ex/len(grp):.1f} %)   "
                  f"+flicker {ex+fl}/{len(grp)} "
                  f"({100.0*(ex+fl)/len(grp):.1f} %)")
    # The detail block below always describes the SCORED set of this run.
    scored = all_scored
    exact = [r for r in scored if r["exact"]]
    flick = [r for r in scored if r.get("flicker_only")]
    print(f"  SCORED          {len(scored)}")
    if scored:
        print(f"  cycle-exact     {len(exact)}/{len(scored)} "
              f"({100.0*len(exact)/len(scored):.1f} %)")
        print(f"  ...+flicker     {len(exact)+len(flick)}/{len(scored)} "
              f"({100.0*(len(exact)+len(flick))/len(scored):.1f} %)")
        fr = sorted(r["first_bad"] / max(1, r["n"]) for r in scored)
        med = fr[len(fr)//2]
        print(f"  prefix fraction median {med:.3f}   "
              f">=0.5 {sum(1 for x in fr if x >= .5)}/{len(fr)}   "
              f">=0.9 {sum(1 for x in fr if x >= .9)}/{len(fr)}")
        fb = sorted(r["first_bad"] for r in scored)
        print(f"  first divergence rows: median {fb[len(fb)//2]}, "
              f"p10 {fb[len(fb)//10]}, p90 {fb[9*len(fb)//10]}")
        print("  first-divergence family: " +
              "  ".join(f"{k}={v}" for k, v in
                        Counter(r["kind"] for r in scored
                                if not r["exact"]).most_common()))
        wc = defaultdict(lambda: [0, 0])
        for r in scored:
            key = wait_class(r)
            wc[key][0] += 1
            wc[key][1] += 1 if r["exact"] else 0
        print("  by wait class:  " + "  ".join(
            f"{k} {v[1]}/{v[0]}" for k, v in sorted(wc.items())))
        bc = defaultdict(lambda: [0, 0])
        for r in scored:
            bc[r["cid"]][0] += 1
            bc[r["cid"]][1] += 1 if r["exact"] else 0
        print("  by bank:        " + "  ".join(
            f"{k} {v[1]}/{v[0]}" for k, v in sorted(bc.items())))

    if args.details:
        for r in sorted((r for r in scored if not r["exact"]),
                        key=lambda r: r["first_bad"])[:args.details]:
            print(f"    {r['cid']}/{r['k']:<6} first_bad={r['first_bad']:>5} "
                  f"n={r['n']:>5} ndiff={r['ndiff']:>5} {r['kind']:<10} "
                  f"{r.get('detail','')[:70]}")
    if args.report:
        Path(args.report).write_text(json.dumps(res))
        print(f"  report -> {args.report}")
    bad = cat.get("GEN_DRIFT", 0) + cat.get("REGEN_ERROR", 0) + \
        cat.get("SIM_ERROR", 0) + len(aborts)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
