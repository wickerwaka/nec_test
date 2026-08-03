#!/usr/bin/env python3
"""s10_board -- the S10 board probes (ucsim-t addendum #6, ucsim_t_provenance 21).

The capture-first session.  SOCKET ONLY (`use_core=False`, passed explicitly on
every call because the board's CFG is sticky), no FPGA flashing anywhere, raw
64-bit capture words retained with a sha256 beside every derived record, the
FULL per-clock row stream retained beside every digest (the P2 lesson, 13.4),
`board_idle()` at the end of the session, a SHA256SUMS per probe directory.

Probes (specs + PRE-REGISTERED expected values: ucsim_t_provenance.md 21.0):

  s1cells  S1's 24 declared repeatability cells, with raw words + full rows.
           (The S1 TRANCHE itself is emitted by the guarded `emit_suite emit`
           path into tests/v30/v0.1-w{1,3}evt -- see 21.0.5 item 1.)
  s2       the HLT delay sweep: HLT.INT / HLT.RES x delay 0..48 x waits{0,1}.
           Emits a delay-swept GOLDEN suite (so timed_gate can score it) and
           retains raw words + rows for the sweep's own cells.
  s4       INT.F3AA at waits 0 and 2 (w1/w3 come from S1) -- the chained
           withdrawal magnitude's remaining wait levels.
  s5       A30: BRKEM -> 8080 EI -> INTR, PS3 read off the acknowledge cycles.
  idle     board_idle().

Usage:
    python3 sw/s10_board.py s2 [--reps 5]
    python3 sw/s10_board.py s5
    python3 sw/s10_board.py sha            # (re)write SHA256SUMS per probe dir
    python3 sw/s10_board.py idle
"""
import argparse
import gzip
import hashlib
import json
import random
import subprocess
import sys
import time
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

import testimage                                        # noqa: E402
import emit_suite as es                                 # noqa: E402
from v30run import run_image                            # noqa: E402
from t2b_board import stable_key, HOST, DIVS, REPS      # noqa: E402

OUT = ROOT / "sw" / "testdata" / "s10"

# The truth-source pin, re-asserted here: goldens and directed captures alike
# come from the SOCKETED REAL CHIP and from nothing else (emit_suite:139).
assert es.EMIT_USE_CORE is False, "S10 refuses to run: truth source is not the socket"

# --------------------------------------------------------------------------- #
# THE DIVIDER PIN (S10 finding, 21.1) -- read this before adding a probe.
#
# The board's CFG clock divider is STICKY: it lives on the board, survives
# process exit, and `run_image(div=None)` sends '-' meaning "leave the board
# default".  `emit_suite.cmd_emit` NEVER sets it.  So a golden suite emitted
# without pinning `div` silently inherits whatever the PREVIOUS session left.
#
# That is not cosmetic.  MEASURED A/B over 12 identical cases (same seeds, same
# image, same waits), 143 pre-T1 Ti rows each:
#     div=8 (4 MHz):  bs_early on the pre-T1 Ti row = the NEW cycle's status
#                     (CODE/INTA/MEMR/MEMW)  -- 143/143
#     div=4 (8 MHz):  bs_early on the pre-T1 Ti row = PASV                    -- 143/143
# i.e. at 8 MHz the address-phase sampling edge lands before the status pulse
# and the DISPLAY CLOCK vanishes from the capture.  This is exactly the T2b
# 12.1 phenomenon ("within-cycle pulses read at a fixed sampling edge"), and at
# 8 MHz it corrupts a COMPARED column instead of an excluded one.
#
# Every S10 probe therefore pins the divider EXPLICITLY, and records it.
# --------------------------------------------------------------------------- #
DIV_OF_RECORD = 8              # 4 MHz -- the whole banked corpus's frequency


def pin_div(div=DIV_OF_RECORD, waits=0):
    """Force the board's CFG divider, so nothing inherits a stale one."""
    img, _ = testimage.compose(regs={}, instr=bytes([0x90]))
    run_image(bytes(img), HOST, tag="pindiv", waits=waits, use_core=False,
              div=div)
    return div


# --------------------------------------------------------------------------- #
# capture primitive -- t2b_board.capture() plus the pin-event arguments
# --------------------------------------------------------------------------- #
def capture(image, waits=0, div=None, evt=None, pins=None, tag="s10"):
    """One socket capture WITH an optional rig pin-event schedule.

    Row semantics are `t2b_board.capture()`'s exactly (reset-trimmed, TI/T4
    `bs_early` replaced by the end-of-cycle sample -- the campaign's
    established capture semantics, 21.0.0 item 2) so every banked t2b/t4/s10
    record is comparable.  The RAW 64-bit words are returned untouched and
    hashed, per the blackbox retention rule.

    Returns (rows, raw_hex_lines, sha256, evt_fired).
    """
    recs, fired, words = run_image(bytes(image), HOST, tag=tag, waits=waits,
                                   use_core=False, div=div, evt=evt, pins=pins,
                                   want_fired=True, want_raw=True)
    raw = [f"{w:016x}" for w in words]
    sha = hashlib.sha256(("\n".join(raw) + "\n").encode()).hexdigest()
    rel = next(i for i, r in enumerate(recs) if not r["rst"])
    rows = recs[rel:]
    for r in rows:
        if r["t"] in (0, 5):
            r["bs_early"] = r["bs_late"]
    return rows, raw, sha, fired


def reps_capture(image, waits=0, evt=None, pins=None, tag="s10",
                 reps=REPS, divs=(8,)):
    """The protocol capture: `reps` repetitions at each clock divider.

    Dual-frequency promotion is applied only where the blackbox protocol
    requires it (21.0.2), so `divs` defaults to 4 MHz alone and the caller
    opts in to (8, 4) for cells a verdict is FROZEN against.
    """
    rec = {"waits": waits, "reps": reps, "divs": list(divs), "captures": {}}
    rows0 = raw0 = None
    fired0 = None
    for div in divs:
        keys, shas, fires = [], [], []
        for _ in range(reps):
            rows, raw, sha, fired = capture(image, waits=waits, div=div,
                                            evt=evt, pins=pins, tag=tag)
            keys.append(stable_key(rows))
            shas.append(sha)
            fires.append(bool(fired))
            if rows0 is None:
                rows0, raw0, fired0 = rows, raw, fired
        rec["captures"][str(div)] = {
            "stable_key": keys[0],
            "stable_identical": len(set(keys)) == 1,
            "evt_fired": fires,
            "raw_sha": shas,
        }
    rec["freq_identical"] = len({v["stable_key"]
                                 for v in rec["captures"].values()}) == 1
    rec["fired"] = bool(fired0)
    return rec, rows0, raw0


# --------------------------------------------------------------------------- #
# bus-cycle reading helpers (pins only -- no model anywhere in these)
# --------------------------------------------------------------------------- #
BS = {0: "INTA", 1: "IOR", 2: "IOW", 3: "HALT", 4: "CODE", 5: "MEMR",
      6: "MEMW", 7: "PASV"}


def cycles(rows):
    """Bus cycles as (kind, t1_idx, t4_idx, tw, addr, ps).  A cycle starts at
    its T1 row; `tw` is the count of Tw rows inside it.  Pins only."""
    out = []
    cur = None
    for i, r in enumerate(rows):
        t = r["t"]
        if t == 1:                                  # T1
            if cur is not None:
                out.append(cur)
            cur = {"kind": BS[r["bs_early"]], "t1": i, "t4": None, "tw": 0,
                   "addr": r["ad_addr"], "ps": None}
        elif cur is not None:
            if t == 4:
                cur["tw"] += 1
            elif t == 5:
                cur["t4"] = i
            if t == 2 and cur["ps"] is None:
                cur["ps"] = r["ps"]
    if cur is not None:
        out.append(cur)
    return out


def inta_runs(cyc):
    """Maximal runs of consecutive INTA cycles.  Returns a list of the runs,
    each a list of the cycle dicts.  This is the A30 observable and it is read
    off the pins with no model in the loop."""
    runs, cur = [], []
    for c in cyc:
        if c["kind"] == "INTA":
            cur.append(c)
        elif cur:
            runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)
    return runs


def halt_status(rows):
    """(first_row, n_rows) of the HALT status display, or None if the chip
    never drove it.  The 32-seed HALTWAKE shape (20.12 item 2) is exactly the
    `None` case, so this returns None deliberately rather than raising."""
    first = None
    n = 0
    for i, r in enumerate(rows):
        if r["bs_early"] == 3:                      # BS = HALT
            if first is None:
                first = i
            n += 1
        elif first is not None:
            break
    return None if first is None else (first, n)


# --------------------------------------------------------------------------- #
# S1 -- the 24 declared repeatability cells (the tranche itself is emitted by
#       `emit_suite emit`; this retains raw words + rows for the protocol cells)
# --------------------------------------------------------------------------- #
S1_FORMS = ["INT.90", "NMI.90", "HLT.INT", "HLT.RES", "INT.F3AA", "INT.9D"]


def s1_delay(delay, waits):
    """The WAIT-SCALED delay stratum.

    DEVIATION from the registration (21.0 S1 said "each form's OWN stratum,
    unchanged"), recorded per 21.0.4 with the measurement that motivated it:
    emitting the forms' w0 strata verbatim at w3 produced INT.90 1/200 and
    NMI.90 1/200 (600 rerolls exhausted).  The cause is that `evt.delay` is a
    CLOCK COUNT while the stratum was chosen to sample a PHASE OF THE
    INSTRUCTION: at wN every bus cycle is (4+N) clocks instead of 4, so the
    same clock count lands at a systematically earlier point of the same
    instruction.  Scaling by (4+N)/4 samples the same phase, which is what the
    stratum was for.  The unscaled partial run is retained as evidence under
    sw/testdata/s10/s1-instrument/.
    """
    return max(1, int(round(delay * (4.0 + waits) / 4.0)))


def cmd_s1(args):
    """Emit the S1 tranche: 6 forms x 200 cases x waits{1,3}, COLD anchor only.

    COLD-only is the second half of the same deviation.  The PREFETCHED anchor
    adds `delay_hw = delay + 50*preload_n` where 50 (`emit_suite.PRELOAD_CYCLES`)
    is an explicitly MEASURED w0 constant ("63 C0 retires in 50 cycles"); under
    waits the preload takes longer, the assert lands before the window opens,
    and `emit_evt_case` rejects the case ("pf assert before window (-N)", 380 of
    600 rerolls on INT.90 at w3).  Holding the anchor law fixed at `fetch`
    removes a w0 constant from the wait-axis measurement entirely, which is the
    scientifically correct move rather than a convenience.
    """
    t0 = time.time()
    for waits in args.waits:
        sd = ROOT / "tests" / "v30" / f"v0.1-w{waits}evt"
        sd.mkdir(parents=True, exist_ok=True)
        div = pin_div(waits=waits)              # THE DIVIDER PIN -- see above
        log = sd / "emit_log.txt"
        with log.open("a") as f:
            f.write(f"# TRUTH SOURCE: SOCKET (real chip, use_core=False)  "
                    f"seed_base=v30-s10-w{waits}evt  cases={args.cases}  "
                    f"waits={waits}  forms={len(S1_FORMS)}  "
                    f"anchor=COLD-only  delay=wait-scaled x(4+N)/4  "
                    f"div={div} ({32//div} MHz, PINNED)\n")
        for op in (args.only or S1_FORMS):
            spec = es.EVT_FORMS[op]
            tests, rerolls = [], 0
            i = 0
            while len(tests) < args.cases and rerolls < args.cases * 4:
                idx = len(tests)
                rng = random.Random(f"v30-s10-w{waits}evt/{op}/{i}")
                i += 1
                try:
                    case = es.gen_evt_case(spec, rng)
                    case["delay"] = s1_delay(case["delay"], waits)
                    t = es.emit_evt_case(spec, case, HOST, tag=f"s1{op}",
                                         preload_n=0, waits=waits)
                except (es.ComposeError, es.RunError) as e:
                    rerolls += 1
                    with log.open("a") as f:
                        f.write(f"{op} case-seed {i-1} reroll: {e}\n")
                    continue
                t["idx"] = idx
                tests.append(t)
            with gzip.open(sd / f"{op}.json.gz", "wt") as f:
                json.dump(tests, f, separators=(",", ":"))
            print(f"  {op}: {len(tests)}/{args.cases} ({rerolls} rerolls) "
                  f"w{waits}  ({time.time()-t0:.0f}s)", flush=True)
    print(f"S1 emission done ({time.time()-t0:.0f}s)")


def _evt_image(spec, case, preload_n=0):
    """emit_evt_case's image construction, lifted so a directed probe can keep
    the raw words the golden path does not return.  preload_n=0 (COLD) only:
    the sweep axis is the delay, so the anchor law is held fixed at `fetch`."""
    nec_regs = {es.INTEL2NEC[k]: v for k, v in case["regs"].items()}
    instr = case["instr"]
    anchor = ((case["regs"]["cs"] << 4) + case["regs"]["ip"]) & 0xFFFFF
    if spec["close"] == "handler":
        stub_linear = case["stub_linear"]
    else:
        stub_linear = (anchor + len(instr)) & 0xFFFF
    image, meta = testimage.compose(regs=nec_regs, instr=instr,
                                    ram=case["ram"], ivt=case["ivt"],
                                    stub_linear=stub_linear)
    evt = None
    if spec["pin"] is not None:
        evt = (anchor, case["delay"], spec["hold"], spec["pin"])
    return image, evt, meta


def cmd_s1cells(args):
    d = OUT / "s1-tranche"
    d.mkdir(parents=True, exist_ok=True)
    man = {"probe": "S1 w1/w3 pin-event tranche -- declared repeatability cells",
           "spec": "docs/notes/ucsim_t_provenance.md 21.0 S1",
           "note": ("the TRANCHE itself is the guarded emit_suite emission into "
                    "tests/v30/v0.1-w1evt / -w3evt (21.0.5 item 1); these are "
                    "the 24 declared protocol cells, retained with raw words"),
           "use_core": False, "host": HOST, "cells": {}}
    t0 = time.time()
    man["div"] = pin_div()                      # THE DIVIDER PIN
    for op in S1_FORMS:
        spec = es.EVT_FORMS[op]
        for waits in (1, 3):
            for idx in (0, 2):                      # two COLD cells per form
                rng = random.Random(f"v30-s10-w{waits}evt/{op}/{idx}")
                try:
                    case = es.gen_evt_case(spec, rng)
                except es.ComposeError as e:
                    man["cells"][f"{op}:w{waits}:{idx}"] = {"error": str(e)}
                    continue
                image, evt, _ = _evt_image(spec, case)
                # one cell per form is promoted to both frequencies
                divs = DIVS if (idx == 0 and waits == 1) else (8,)
                rec, rows, raw = reps_capture(image, waits=waits, evt=evt,
                                              tag="s1", reps=args.reps,
                                              divs=divs)
                key = f"{op}_w{waits}_{idx}"
                rec["delay"] = case["delay"]
                rec["anchor"] = evt[0] if evt else None
                man["cells"][key] = rec
                with gzip.open(d / f"{key}.rows.json.gz", "wt") as f:
                    json.dump(rows, f, separators=(",", ":"))
                with gzip.open(d / f"{key}.raw.hex.gz", "wt") as f:
                    f.write("\n".join(raw) + "\n")
                print(f"  {key}: fired={rec['fired']} "
                      f"stable={all(v['stable_identical'] for v in rec['captures'].values())} "
                      f"freq_id={rec['freq_identical']} rows={len(rows)}",
                      flush=True)
    man["seconds"] = round(time.time() - t0, 1)
    (d / "manifest.json").write_text(json.dumps(man, indent=1))
    print(f"wrote {d}/manifest.json  ({man['seconds']}s)")


# --------------------------------------------------------------------------- #
# S2 -- the HLT delay sweep
# --------------------------------------------------------------------------- #
S2_FORMS = ["HLT.INT", "HLT.RES"]
S2_DELAYS = list(range(0, 49))


def cmd_s2(args):
    """Emit a DELAY-SWEPT golden suite plus the directed capture.

    Two artifacts, deliberately:
      * tests/v30/s10-hltsweep-w{0,1}/<form>.json.gz -- standard golden format,
        so `timed_gate.py` scores the model against it with no new machinery;
      * sw/testdata/s10/s2-hltsweep/ -- raw words + full rows + the pins-only
        measurement table (status driven?, display clock, entry/pop clock).
    """
    d = OUT / "s2-hltsweep"
    d.mkdir(parents=True, exist_ok=True)
    man = {"probe": "S2 HLT delay sweep", "use_core": False, "host": HOST,
           "spec": "docs/notes/ucsim_t_provenance.md 21.0 S2",
           "delays": S2_DELAYS, "forms": S2_FORMS, "cells": {}}
    table = []
    t0 = time.time()
    man["div"] = pin_div()                      # THE DIVIDER PIN
    for waits in (0, 1):
        sd = ROOT / "tests" / "v30" / f"s10-hltsweep-w{waits}"
        sd.mkdir(parents=True, exist_ok=True)
        for op in S2_FORMS:
            spec = es.EVT_FORMS[op]
            tests = []
            for di, delay in enumerate(S2_DELAYS):
                # ONE fixed program per form: the sweep axis is the delay and
                # nothing else, so the state is drawn from a single fixed seed.
                rng = random.Random(f"v30-s10-hlt/{op}")
                try:
                    case = es.gen_evt_case(spec, rng)
                except es.ComposeError:
                    continue
                case["delay"] = delay               # THE SWEEP AXIS
                image, evt, _ = _evt_image(spec, case)
                rec, rows, raw = reps_capture(image, waits=waits, evt=evt,
                                              tag="s2", reps=args.reps,
                                              divs=(8,))
                hs = halt_status(rows)
                cyc = cycles(rows)
                runs = inta_runs(cyc)
                # first CODE fetch strictly after the HALT display (the woken
                # fetch), and the acknowledge, both read off the pins alone
                woke = None
                if hs is not None:
                    woke = next((c["t1"] for c in cyc
                                 if c["kind"] == "CODE" and c["t1"] > hs[0]), None)
                row = {"form": op, "waits": waits, "delay": delay,
                       "fired": rec["fired"],
                       "halt_driven": hs is not None,
                       "halt_first": None if hs is None else hs[0],
                       "halt_len": None if hs is None else hs[1],
                       "woken_fetch_t1": woke,
                       "inta1_t1": runs[0][0]["t1"] if runs else None,
                       "inta_run_len": len(runs[0]) if runs else 0,
                       "n_rows": len(rows),
                       "stable": rec["captures"]["8"]["stable_identical"]}
                table.append(row)
                key = f"{op}_w{waits}_d{delay}"
                man["cells"][key] = rec
                with gzip.open(d / f"{key}.rows.json.gz", "wt") as f:
                    json.dump(rows, f, separators=(",", ":"))
                with gzip.open(d / f"{key}.raw.hex.gz", "wt") as f:
                    f.write("\n".join(raw) + "\n")
                # the golden, through the STANDARD path so timed_gate can score
                try:
                    t = es.emit_evt_case(spec, case, HOST, tag="s2g",
                                         preload_n=0, waits=waits)
                    t["idx"] = di
                    tests.append(t)
                except (es.ComposeError, es.RunError) as e:
                    print(f"    golden {key}: {e}", flush=True)
            if tests:
                with gzip.open(sd / f"{op}.json.gz", "wt") as f:
                    json.dump(tests, f, separators=(",", ":"))
            print(f"  {op} w{waits}: {len(tests)} goldens "
                  f"({time.time()-t0:.0f}s)", flush=True)
    man["seconds"] = round(time.time() - t0, 1)
    (d / "manifest.json").write_text(json.dumps(man, indent=1))
    (d / "sweep_table.json").write_text(json.dumps(table, indent=1))
    print(f"wrote {d}/sweep_table.json  ({man['seconds']}s)")
    _s2_report(table)


def _s2_report(table):
    """The registered readings: the threshold d*, per form and wait level."""
    print("\n  --- S2, the registered threshold reading ---")
    for op in S2_FORMS:
        ds = {}
        for w in (0, 1):
            rows = sorted([r for r in table if r["form"] == op and r["waits"] == w],
                          key=lambda r: r["delay"])
            drv = [r["delay"] for r in rows if r["halt_driven"]]
            nod = [r["delay"] for r in rows if not r["halt_driven"]]
            # d* = the smallest delay at or above which the status is driven
            dstar = min(drv) if drv else None
            sharp = (not nod or not drv or max(nod) < min(drv))
            lens = sorted({r["halt_len"] for r in rows if r["halt_driven"]})
            ds[w] = dstar
            print(f"    {op:8s} w{w}: d*={dstar}  sharp={sharp}  "
                  f"not-driven={len(nod)}/{len(rows)}  halt_len={lens}")
        if ds.get(0) is not None and ds.get(1) is not None:
            print(f"    {op:8s} d*(w1)-d*(w0) = {ds[1]-ds[0]:+d}   "
                  f"(REGISTERED PREDICTION: +1)")


# --------------------------------------------------------------------------- #
# S4 -- INT.F3AA at the wait levels S1 does not cover
# --------------------------------------------------------------------------- #
def cmd_s4(args):
    """INT.F3AA at waits 0 and 2 -- the wait levels S1 does not cover.

    Deliberately run through cmd_s1's OWN protocol (div PINNED, COLD anchor,
    wait-scaled delay) so the four wait levels {0,1,2,3} are one factorial and
    not two differently-instrumented halves.  w2 is the HELD-OUT cell for the
    acknowledge law measured on {0,1,3}.
    """
    class A:
        cases = args.cases
        waits = [0, 2]
        only = ["INT.F3AA"]
    return cmd_s1(A())


# --------------------------------------------------------------------------- #
# S5 -- A30: BRKEM -> 8080 EI -> INTR
# --------------------------------------------------------------------------- #
# The 8080-mode stub: EI (0xFB) then a NOP (0x00) run.  Both encodings are the
# 8080 ones and both are decoded from the ROM's 8080 pages (110 / 101).
S5_STUB = bytes([0xFB]) + bytes([0x00]) * 40
S5_BRKEM_VEC = 0x20            # the BRKEM vector; IVT[0x20] -> the 8080 stub


def s5_image(stub_at, ps=0x0000, pc=0x0500, sp=0x3F00):
    """BRKEM imm8 at the anchor; the 8080 stub placed as raw RAM at `stub_at`.

    BRKEM pushes PSW/CS/IP and enters emulation mode with IE CLEARED, so the
    stub's first byte is an 8080 EI -- otherwise the INTR can never be
    recognised and the probe would measure nothing (21.0 S5).
    """
    instr = bytes([0x0F, 0xFF, S5_BRKEM_VEC])
    ram = [(stub_at + i, b) for i, b in enumerate(S5_STUB)]
    regs = {"PS": ps, "PC": pc, "SS": 0, "SP": sp, "DS0": 0, "DS1": 0,
            "PSW": 0xF202 | 0x0200,           # IE set entering BRKEM
            "AW": 0x1234, "BW": 0x2345, "CW": 0x0003, "DW": 0x0040,
            "BP": 0x3456, "IX": 0x2500, "IY": 0x2A00}
    # IVT[0x20] -> the 8080 stub.  The acknowledge's own vector (the rig's INTA
    # constant, 0xFF) is left pointing at the composed store stub.
    ivt = {S5_BRKEM_VEC: (0x0000, stub_at)}
    image, meta = testimage.compose(regs=regs, instr=instr, ram=ram, ivt=ivt)
    return image, meta


def cmd_s5(args):
    d = OUT / "s5-a30"
    d.mkdir(parents=True, exist_ok=True)
    man = {"probe": "S5 A30 -- BRKEM -> 8080 EI -> INTR",
           "spec": "docs/notes/ucsim_t_provenance.md 21.0 S5",
           "use_core": False, "host": HOST, "cells": {}}
    obs = []
    t0 = time.time()
    man["div"] = pin_div()                      # THE DIVIDER PIN
    for hist, stub_at in enumerate((0x0800, 0x1200)):     # 2 preparation histories
        image, meta = s5_image(stub_at)
        anchor = meta["anchor_linear"] & 0xFFFFF
        for waits in (0, 1):
            for delay in args.delays:
                evt = (anchor, delay, 0, 0)              # pin 0 = INT
                divs = DIVS if delay == args.delays[0] else (8,)
                rec, rows, raw = reps_capture(image, waits=waits, evt=evt,
                                              tag="s5", reps=args.reps,
                                              divs=divs)
                cyc = cycles(rows)
                runs = inta_runs(cyc)
                # MD is PS3 (M9).  Read it on the ACKNOWLEDGE CYCLES THEMSELVES
                # -- that is the whole point of the probe (14.5): no model, no
                # inference, no has_brkem flag.
                md_seen = any((c["ps"] or 0) & 0x8 for c in cyc)
                cell = {"hist": hist, "stub_at": stub_at, "waits": waits,
                        "delay": delay, "fired": rec["fired"],
                        "md_anywhere": md_seen,
                        "n_runs": len(runs),
                        "runs": [{"len": len(r),
                                  "ps": [c["ps"] for c in r],
                                  "md": [bool((c["ps"] or 0) & 0x8) for c in r],
                                  "t1": r[0]["t1"]} for r in runs],
                        "stable": rec["captures"]["8"]["stable_identical"]}
                obs.append(cell)
                key = f"h{hist}_w{waits}_d{delay}"
                man["cells"][key] = rec
                with gzip.open(d / f"{key}.rows.json.gz", "wt") as f:
                    json.dump(rows, f, separators=(",", ":"))
                with gzip.open(d / f"{key}.raw.hex.gz", "wt") as f:
                    f.write("\n".join(raw) + "\n")
        print(f"  hist{hist} (stub {stub_at:#06x}) done "
              f"({time.time()-t0:.0f}s)", flush=True)
    man["seconds"] = round(time.time() - t0, 1)
    (d / "manifest.json").write_text(json.dumps(man, indent=1))
    (d / "a30_observations.json").write_text(json.dumps(obs, indent=1))
    _s5_report(obs)
    print(f"wrote {d}/a30_observations.json  ({man['seconds']}s)")


def _s5_report(obs):
    """The A30 verdict, read off the pins.  A run taken with MD=1 on the
    acknowledge cycles is the only kind that counts (21.0 S5's instrument
    falsifier: PS3=0 on the acknowledge VOIDS the cell)."""
    print("\n  --- S5, the A30 reading ---")
    md1, md0, lens = 0, 0, {}
    for c in obs:
        for r in c["runs"]:
            if all(r["md"]):
                md1 += 1
                lens[r["len"]] = lens.get(r["len"], 0) + 1
            else:
                md0 += 1
    print(f"    acknowledges with MD=1 on EVERY cycle of the run: {md1}")
    print(f"    acknowledges with MD=0 somewhere (VOID cells):    {md0}")
    print(f"    run-length histogram over the MD=1 acknowledges:  {lens}")
    if md1 == 0:
        print("    VERDICT: VOID -- the part was not in emulation mode at any "
              "acknowledge; the probe measured nothing and the stub is at "
              "fault, not the chip (21.0 S5 instrument falsifier).")
    elif set(lens) == {2}:
        print("    VERDICT: BANK B / fixed priority -- every emulation-mode "
              "acknowledge is a TWO-cycle pair.  The emulation-mode-input "
              "(14th decoder input) mechanism predicts ONE and is REFUTED.")
    elif set(lens) == {1}:
        print("    VERDICT: BANK A -- a SINGLE acknowledge in emulation mode. "
              "A30's 14th-decoder-input assumption is CONFIRMED and the "
              "model (which runs bank B always) is WRONG.")
    else:
        print("    VERDICT: MIXED run lengths -- reported as a finding, not "
              "resolved; neither reading predicts a mixture.")


# --------------------------------------------------------------------------- #
def cmd_sha(args):
    """Write a plain `sha256sum`-format SHA256SUMS into every probe dir."""
    n = 0
    for d in sorted(p for p in OUT.iterdir() if p.is_dir()):
        files = sorted(f for f in d.rglob("*")
                       if f.is_file() and f.name != "SHA256SUMS")
        lines = []
        for f in files:
            h = hashlib.sha256(f.read_bytes()).hexdigest()
            lines.append(f"{h}  {f.relative_to(d)}")
        (d / "SHA256SUMS").write_text("\n".join(lines) + "\n")
        print(f"  {d.name}: {len(files)} files")
        n += len(files)
    print(f"wrote SHA256SUMS over {n} files")


def cmd_idle(args):
    import b1_recapture                                  # noqa: E402
    b1_recapture.board_idle()
    print("board_idle() done -- socket, use_core=0")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("s1")
    p.add_argument("--cases", type=int, default=200)
    p.add_argument("--waits", type=int, nargs="+", default=[1, 3])
    p.add_argument("--only", nargs="*")
    p.set_defaults(fn=cmd_s1)
    p = sub.add_parser("s1cells"); p.add_argument("--reps", type=int, default=REPS)
    p.set_defaults(fn=cmd_s1cells)
    p = sub.add_parser("s2"); p.add_argument("--reps", type=int, default=REPS)
    p.set_defaults(fn=cmd_s2)
    p = sub.add_parser("s4"); p.add_argument("--cases", type=int, default=200)
    p.set_defaults(fn=cmd_s4)
    p = sub.add_parser("s5")
    p.add_argument("--reps", type=int, default=REPS)
    p.add_argument("--delays", type=int, nargs="+",
                   default=[40, 45, 50, 55, 60, 65, 70, 75, 80, 90])
    p.set_defaults(fn=cmd_s5)
    sub.add_parser("sha").set_defaults(fn=cmd_sha)
    sub.add_parser("idle").set_defaults(fn=cmd_idle)
    a = ap.parse_args()
    return a.fn(a) or 0


if __name__ == "__main__":
    sys.exit(main())
