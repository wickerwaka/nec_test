#!/usr/bin/env python3
"""ie_pinfall_cell -- THE DIRECTED BOARD CELL on the IE-rise / pin-fall race.

THE CELL THREE BOOKINGS ASK FOR AND NONE OF THEM HAS.

  1. `docs/notes/fz2_w5_p3_results_2026-08-10.md` §4 (C-gamma).  The vectoring
     HALT wake's prefetch suspend is REAL and its carrier `irq_int_lvl` is
     WRONG: it fires both where silicon SUSPENDS (the 3 C2 seats) and where
     silicon RUNS THE ACKNOWLEDGE LATE (`fz2c/404040`, the c2a four), and those
     two populations are identical on every recognition-path coordinate
     available offline.  Re-open condition, verbatim: *"a DIRECTED BOARD CELL
     on that race ... that measures, on silicon, whether the wake prefetch is
     present as a function of the IE/pin phase."*
  2. `docs/notes/fz2_w4_results_2026-08-10.md` §3.3 (C-beta).  The park cost
     when the display is cancelled.  Its falsifier is *"a capture in which
     `sti; hlt` with the pin already high delivers INTA with NO idle clocks
     between the HALT boundary and the acknowledge"* -- and it may not be
     fitted on the three seats that raised it.
  3. `docs/notes/fz2_c2_results_2026-08-10.md` §5.2 (the nine load-bearing
     clocks).  `run - arm` is the ONLY column that separates anything, and
     `fz2c/404040` (silicon TAKES) is identical to the four `run - arm == 2`
     seats (silicon does NOT) on the arm offset, the window opening, the window
     length, `rep_kind`, the hold and the take offset.  *"Closing them needs a
     directed board cell on the IE-rise / pin-fall race, which does not exist;
     deriving one from these nine rows would be fitting."*

WHAT IT MEASURES, IN ONE SENTENCE.  With IE brought DOWN and back UP by the
program itself, and the INT pin's RISE and FALL both placed to the clock by the
rig's own scheduler, it walks the pin's FALL across the IE rise and reads
TAKEN / NOT-TAKEN off the pins.

THE GEOMETRY.  Four directed programs, identical in length and in queue-pop
structure, differing only in two bytes:

    eirun   DI  NOP x6  EI  NOP x64        IE falls, rises again, free run
    eihlt   DI  NOP x6  EI  HLT  NOP x64   ... and then parks
    ierun   NOP NOP x6  NOP NOP x64        control: IE never falls
    iehlt   NOP NOP x6  NOP HLT  NOP x64   control: IE never falls, parks

`testimage.normalize_psw` FORCES IE=1 into every composed image (fuzz-v2), so
the only way to a cleared IE is an instruction, and `DI` is it.  The controls
put `NOP` where the setter bytes go, so the pop geometry, the fetch geometry
and every address are IDENTICAL and the ONLY difference between a leg and its
control is the state of one flag.

THE REFERENCE CLOCK IS MEASURED, NOT MODELLED.  Every quantity is reported
against `t_ei`, the EIGHTH queue F-pop at or after the CODE T1 whose address is
the body anchor.  The loader's terminal far jump flushes the queue, so that T1
is the program's first fetch and the eight pops are `DI` + six `NOP` + the
setter, in order, on any engine and on silicon alike.  `t_ei` is read off the
QS pins with no model in the loop.  Likewise the pin's own RISE and FALL are
read from capture bits [52] (`pin_int`, the EFFECTIVE level the CPU is shown),
not from the directive that was sent -- INV-1 is the reason.

THE SWEEP.  Two offsets, both in clocks and both against `t_ei`:

    rise_off = rise - t_ei          where the pin arrives
    fall_off = fall - t_ei          where it leaves (fall = first low row)

The rig takes `(delay, hold)`; `delay` places the rise (`rise = anchor_t1 +
delay + 2`, the harness scheduler law, re-measured in `calib`) and `hold` is the
pulse WIDTH, so `fall_off = rise_off + hold`.  `hold = 300` is the corpus's own
never-falls case and is swept beside the finite ones.

THE OBSERVABLE IS BINARY AND ENGINE-FREE: is there an INTA cycle?  Plus, for
the HLT legs, the count of CODE cycles between the HALT display and the first
INTA (C-gamma's own quantity) and the acknowledge's offset from the HALT pop
(C-beta's).

BOARD DISCIPLINE (CLAUDE.md), in code: single-writer asked of the board before
the first capture; SOCKET ONLY (`use_core=False`, passed explicitly, because
the board's CFG is sticky); NO FLASHING anywhere; the divider PINNED and
`div_guard`'s readback RECORDED at every stratum boundary; the FULL per-clock
capture words retained with a sha256 per cell; `board_idle()` at the end; a run
of consecutive transport errors STOPS the cell and is reported as a rig
finding, which outranks the measurement.

Usage:
    python3 sw/ie_pinfall_cell.py calib                 # offline (tb_sys)
    python3 sw/ie_pinfall_cell.py predict               # offline
    python3 sw/ie_pinfall_cell.py core [--strata ...]   # offline (tb_sys)
    python3 sw/ie_pinfall_cell.py run   [--strata ...]  # BOARD, socket only
    python3 sw/ie_pinfall_cell.py score
    python3 sw/ie_pinfall_cell.py seats
    python3 sw/ie_pinfall_cell.py idle
"""
import argparse
import gzip
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

import testimage as ti                                   # noqa: E402

OUT = ROOT / "sw" / "testdata" / "ie-pinfall"
CALIB = OUT / "calib.json"
PRED = OUT / "predictions.json"

# --------------------------------------------------------------------------- #
# the four programs
# --------------------------------------------------------------------------- #
SLED = 64
INT_VECTOR = 0xFF
VEC_TARGET = 0x8800          # inside the code region, 0xCC fill -> INT3 -> term

LEGS = {
    #        prologue byte 0   setter byte   trailing
    "eirun": dict(b0=0xFA, b7=0xFB, hlt=False,
                  what="DI . NOP x6 . EI . sled"),
    "eihlt": dict(b0=0xFA, b7=0xFB, hlt=True,
                  what="DI . NOP x6 . EI . HLT . sled"),
    "ierun": dict(b0=0x90, b7=0x90, hlt=False,
                  what="control, IE never falls: NOP x8 . sled"),
    "iehlt": dict(b0=0x90, b7=0x90, hlt=True,
                  what="control, IE never falls: NOP x8 . HLT . sled"),
}


def body_of(leg):
    s = LEGS[leg]
    b = [s["b0"]] + [0x90] * 6 + [s["b7"]]
    if s["hlt"]:
        b.append(0xF4)
    b += [0x90] * SLED
    return bytes(b)


def image_of(leg):
    """The composed 64 KB image.  Deterministic: no rng anywhere in this cell,
    which is what makes it a DIRECTED cell and not a fuzz."""
    img, meta = ti.compose(instr=body_of(leg),
                           ivt={INT_VECTOR: (0x0000, VEC_TARGET)})
    return bytes(img), meta


def image_sha(leg):
    return hashlib.sha256(image_of(leg)[0]).hexdigest()


# --------------------------------------------------------------------------- #
# row reading -- pins only, no engine
# --------------------------------------------------------------------------- #
BS = {0: "INTA", 1: "IOR", 2: "IOW", 3: "HALT", 4: "CODE", 5: "MEMR",
      6: "MEMW", 7: "PASV"}


def _rows_from_words(words):
    """Decode + trim reset, exactly `s10_board.capture`'s row semantics."""
    from analyze_capture import decode_words
    recs = decode_words(words)
    rel = next((i for i, r in enumerate(recs) if not r["rst"]), 0)
    rows = recs[rel:]
    for r in rows:
        if r["t"] in (0, 5):
            r["bs_early"] = r["bs_late"]
    return rows


def features(rows, leg, anchor):
    """Every measured quantity this cell reports, off the pins.

    `ok` is False when the cell is STRUCTURALLY INVALID -- the anchor T1 was
    not captured, or fewer than eight F pops were seen before the window ends,
    or an INTA landed BEFORE `t_ei` (which means the pin was recognised while
    IE was still SET from the loader, i.e. the rise beat the `DI`).  Those
    cells are RETAINED and REPORTED, never silently dropped."""
    f = {"ok": False, "why": None}
    a = next((i for i, r in enumerate(rows)
              if r["t"] == 1 and r["bs_early"] == 4 and r["ad_addr"] == anchor),
             None)
    f["anchor_t1"] = a
    pops = [i for i, r in enumerate(rows) if r["qs"] == 1 and a is not None and i >= a]
    inta = [i for i, r in enumerate(rows) if r["t"] == 1 and r["bs_early"] == 0]
    halt = [i for i, r in enumerate(rows) if r["bs_early"] == 3]
    rise = next((i for i, r in enumerate(rows) if r["pin_int"] == 1), None)
    fall = None
    if rise is not None:
        fall = next((i for i, r in enumerate(rows)
                     if i > rise and r["pin_int"] == 0), None)
    f.update(rise=rise, fall=fall, n_rows=len(rows),
             ack=(inta[0] if inta else None), n_inta=len(inta),
             halt_first=(halt[0] if halt else None), n_halt=len(halt))
    if a is None:
        f["why"] = "anchor T1 not in the capture window"
        return f
    if len(pops) < 8:
        f["why"] = f"only {len(pops)} F pops after the anchor"
        return f
    t_ei = pops[7]
    t_hlt = pops[8] if LEGS[leg]["hlt"] and len(pops) > 8 else None
    f["t_ei"] = t_ei
    f["t_hlt"] = t_hlt
    if inta and inta[0] < t_ei:
        f["why"] = "INTA before t_ei -- the rise beat the DI (PRE_DI)"
        return f
    f["taken"] = bool(inta)
    f["rise_off"] = None if rise is None else rise - t_ei
    f["fall_off"] = None if fall is None else fall - t_ei
    f["ack_off"] = None if not inta else inta[0] - t_ei
    if t_hlt is not None:
        f["halt_off"] = None if not halt else halt[0] - t_hlt
        f["ack_off_hlt"] = None if not inta else inta[0] - t_hlt
        # C-gamma's own quantity: CODE cycles between the HALT display and
        # the acknowledge.  Counted on T1 rows, so a cycle is counted once.
        if halt and inta:
            f["wake_prefetch"] = sum(
                1 for i, r in enumerate(rows)
                if halt[0] < i < inta[0] and r["t"] == 1 and r["bs_early"] == 4)
        else:
            f["wake_prefetch"] = None
    f["ok"] = True
    return f


# --------------------------------------------------------------------------- #
# the sweep grid
# --------------------------------------------------------------------------- #
# Both offsets are in CLOCKS against `t_ei`.  The ranges bracket the ucore's
# own measured threshold (`fall_off == 3` on `eirun` w0) with >= 6 clocks of
# margin on each side and cover the whole acknowledge latency (9 clocks), so a
# silicon threshold anywhere in [-8, +16] is INSIDE the sweep.
RISE_OFF_FULL = [-16, -12, -8, -6, -4, -2, 0, 2, 4, 6, 8, 10, 12, 16, 20]
RISE_OFF_CTL = [-16, -8, -4, 0, 4, 8, 16]
FALL_OFF = list(range(-8, 17))
HOLD_INF = 300               # the corpus's own never-falls hold


def grid(leg, waits, full=True):
    """[(rise_off, hold)] for one (leg, waits) stratum.

    A finite hold is emitted only where it lands the fall inside FALL_OFF; the
    infinite hold is emitted once per rise, because "the pin never leaves" is a
    different experiment from "it leaves at clock X"."""
    rs = RISE_OFF_FULL if full else RISE_OFF_CTL
    cells = []
    for r in rs:
        cells.append((r, HOLD_INF))
        for fo in FALL_OFF:
            h = fo - r
            if 1 <= h < HOLD_INF:
                cells.append((r, h))
    return cells


STRATA = []
for _leg in ("eirun", "eihlt"):
    for _w in (0, 1, 2, 3):
        STRATA.append((_leg, _w, True))
for _leg in ("ierun", "iehlt"):
    for _w in (0, 3):
        STRATA.append((_leg, _w, False))


def stratum_key(leg, waits):
    return f"{leg}_w{waits}"


# --------------------------------------------------------------------------- #
# calibration -- offline, on tb_sys, and it sets INSTRUMENT settings ONLY
# --------------------------------------------------------------------------- #
def _tbsys():
    import fz2_tbsys
    return fz2_tbsys


def cmd_calib(a):
    """Measure `anchor_t1` and `t_ei` per (leg, waits) on the ucore, so the
    sweep's `delay` values put the pin where the sweep says.

    THIS IS AN INSTRUMENT SETTING, NOT A RESULT.  It decides WHERE the sweep
    looks, never what the sweep is scored against: every reported offset in
    `run`/`score` is recomputed from the capture's OWN measured `t_ei` and its
    OWN measured pin edges, so a calibration that is wrong by k clocks shifts
    the coverage and biases nothing.  It is taken on an engine because the
    quantities it measures (where the eighth pop of a fixed program lands) are
    program geometry, and because taking it on the board would be board contact
    before the pre-registration."""
    tbs = _tbsys()
    OUT.mkdir(parents=True, exist_ok=True)
    cal = {"tool": "ie_pinfall_cell calib", "leg": "tb_sys ret",
           "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "note": "instrument setting only; every scored offset is measured "
                   "from the capture's own t_ei and its own pin edges",
           "cells": {}}
    tmp = OUT / "_calib.hex"
    for leg in LEGS:
        img, meta = image_of(leg)
        anchor = meta["anchor_linear"]
        for w in (0, 1, 2, 3):
            # a long hold and a late rise: the geometry must be read from a run
            # whose recognition cannot disturb the eight pops we are locating
            ncap = 700 + 500 * w
            # tb_sys does NOT truncate its capture file, so a shorter run after
            # a longer one would parse the previous run's TAIL.  Measured: it
            # is what made the first `core` chunk die on `eihlt_w0`.
            tmp.unlink(missing_ok=True)
            r = tbs.run_tb("ret", img, tmp, ncap=ncap, waits=w,
                           evts={0: (anchor, 4000, 1, 0)}, quiet=True)
            rows = _rows_from_words(r["words"])
            f = features(rows, leg, anchor)
            cal["cells"][stratum_key(leg, w)] = {
                "anchor": anchor, "anchor_t1": f["anchor_t1"],
                "t_ei": f.get("t_ei"), "t_hlt": f.get("t_hlt"),
                "n_rows": len(rows), "image_sha256": image_sha(leg)}
            print(f"  {stratum_key(leg, w):12s} anchor_t1={f['anchor_t1']} "
                  f"t_ei={f.get('t_ei')} t_hlt={f.get('t_hlt')}")
    tmp.unlink(missing_ok=True)
    # the capture depth each stratum needs: through the acknowledge, the HALT
    # wake and a margin, scaled by the wait level
    for k, c in cal["cells"].items():
        w = int(k.rsplit("w", 1)[1])
        c["ncap"] = int(c["t_ei"] + 120 + 60 * w + 64) if c["t_ei"] else None
    CALIB.write_text(json.dumps(cal, indent=1))
    print(f"  -> {CALIB}")
    return 0


def _cal():
    if not CALIB.exists():
        raise SystemExit("run `ie_pinfall_cell.py calib` first")
    return json.loads(CALIB.read_text())


def delay_for(cal, leg, waits, rise_off):
    """rise = anchor_t1 + delay + 2  (nec_bus.sv g_evt: match at T1, count
    `delay` ticks, drive on the next).  Re-measured in `calib`."""
    c = cal["cells"][stratum_key(leg, waits)]
    d = c["t_ei"] + rise_off - c["anchor_t1"] - 2
    return d


# --------------------------------------------------------------------------- #
# the sweep driver, shared by the board leg and the tb_sys leg
# --------------------------------------------------------------------------- #
def _sweep(cal, strata, capture_fn, tag, outdir, reps_every=20, reps=3,
           limit=None, progress=50):
    """capture_fn(image, waits, evt, ncap) -> (words, extra) ."""
    outdir.mkdir(parents=True, exist_ok=True)
    table = []
    raws = {}
    t0 = time.time()
    n = 0
    unstable = []
    for leg, w, full in strata:
        key = stratum_key(leg, w)
        c = cal["cells"][key]
        img, meta = image_of(leg)
        anchor = meta["anchor_linear"]
        cells = grid(leg, w, full)
        if limit:
            cells = cells[:limit]
        shard = {}
        for i, (ro, hold) in enumerate(cells):
            d = delay_for(cal, leg, w, ro)
            if d < 0:
                print(f"    SKIP {key}:r{ro}:h{hold} -- delay {d} < 0 "
                      f"(the rise would precede the anchor T1)", flush=True)
                continue
            evt = (anchor, d, hold, 0)
            words, extra = capture_fn(img, w, evt, c["ncap"])
            rows = _rows_from_words(words)
            f = features(rows, leg, anchor)
            sha = hashlib.sha256(
                ("\n".join(f"{x:016x}" for x in words) + "\n").encode()
            ).hexdigest()
            ck = f"{key}:r{ro}:h{hold}"
            row = {"cell": ck, "leg": leg, "waits": w, "rise_off_req": ro,
                   "hold": hold, "delay": d, "sha256": sha, "n_words": len(words)}
            row.update({k: v for k, v in f.items()})
            row.update(extra)
            # stability: a declared fraction of the points, captured `reps`
            # times, compared on the FULL word stream
            if reps_every and i % reps_every == 0:
                shas = [sha]
                for _ in range(reps - 1):
                    w2, _e = capture_fn(img, w, evt, c["ncap"])
                    shas.append(hashlib.sha256(
                        ("\n".join(f"{x:016x}" for x in w2) + "\n").encode()
                    ).hexdigest())
                row["rep_shas"] = shas
                row["stable"] = len(set(shas)) == 1
                if not row["stable"]:
                    unstable.append(ck)
            table.append(row)
            shard[ck] = [f"{x:016x}" for x in words]
            n += 1
            if progress and n % progress == 0:
                print(f"    {n} cells  ({time.time() - t0:.0f}s)  {ck}",
                      flush=True)
        raws[key] = shard
        with gzip.open(outdir / f"{key}.raw.json.gz", "wt") as fh:
            json.dump(shard, fh, separators=(",", ":"))
        print(f"  {key}: {len(shard)} cells  ({time.time() - t0:.0f}s)",
              flush=True)
    return table, unstable, time.time() - t0


def _merge(outdir, table):
    """A resumed invocation must not silently DELETE the strata a previous one
    measured.  Merge by cell key, newest wins, and say how many were carried."""
    p = outdir / "table.json"
    old = json.loads(p.read_text()) if p.exists() else []
    by = {r["cell"]: r for r in old}
    kept = len(by)
    for r in table:
        by[r["cell"]] = r
    merged = sorted(by.values(), key=lambda r: (r["leg"], r["waits"], r["cell"]))
    if kept:
        print(f"  merged with {kept} previously measured cells -> {len(merged)}")
    return merged


def _select(strata_arg):
    if not strata_arg:
        return list(STRATA)
    want = set(strata_arg.split(","))
    sel = [s for s in STRATA if stratum_key(s[0], s[1]) in want or s[0] in want]
    if not sel:
        raise SystemExit(f"no stratum matches {strata_arg!r}")
    return sel


# --------------------------------------------------------------------------- #
def cmd_core(a):
    """The SAME grid on `tb_sys ret` -- the ucore's own take-map.

    This is the core leg of the comparison and it is NOT the reference: the
    correctness target is silicon (CLAUDE.md, 2026-08-04).  It exists so the
    measured silicon threshold can be put beside the engine's, cell for cell,
    on the identical stimulus."""
    tbs = _tbsys()
    cal = _cal()
    d = OUT / "core"
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / "_run.hex"

    def cap(img, w, evt, ncap):
        tmp.unlink(missing_ok=True)      # see cmd_calib: tb_sys does not truncate
        r = tbs.run_tb("ret", img, tmp, ncap=ncap, waits=w,
                       evts={0: (evt[0], evt[1], evt[2], evt[3])}, quiet=True)
        return r["words"], {"fired": r["fired"]}

    table, unstable, secs = _sweep(cal, _select(a.strata), cap, "core", d,
                                   reps_every=0, limit=a.limit)
    tmp.unlink(missing_ok=True)
    man = {"tool": "ie_pinfall_cell core", "leg": "tb_sys ret",
           "receipt": _tbsys_receipt(), "cells": len(table),
           "seconds": round(secs, 1),
           "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    table = _merge(d, table)
    man["cells"] = len(table)
    (d / "manifest.json").write_text(json.dumps(man, indent=1))
    (d / "table.json").write_text(json.dumps(table, indent=1))
    print(f"  core: {len(table)} cells in {secs:.0f}s -> {d}")
    return 0


def _tbsys_receipt():
    try:
        import artifact
        import x1_retention as x1
        return {k: artifact.receipt_of(v) if hasattr(artifact, "receipt_of")
                else hashlib.sha256(v.read_bytes()).hexdigest()
                for k, v in x1.BIN.items() if v.exists()}
    except Exception as e:                                   # noqa: BLE001
        return {"error": str(e)}


# --------------------------------------------------------------------------- #
# the BOARD leg
# --------------------------------------------------------------------------- #
def _board():
    import v30run
    from t2b_board import HOST
    from s13_board import div_guard
    from s10_board import pin_div, DIV_OF_RECORD
    import emit_suite as es
    assert es.EMIT_USE_CORE is False, \
        "ie_pinfall_cell refuses to run: truth source is not the socket"
    return v30run, HOST, div_guard, pin_div, DIV_OF_RECORD


def _ssh(host, cmd, timeout=25):
    r = subprocess.run(["ssh", "-o", "BatchMode=yes",
                        "-o", "ConnectTimeout=10", host, cmd],
                       capture_output=True, text=True, timeout=timeout)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def single_writer(host):
    """Asked of the board, not assumed (CLAUDE.md).  Returns the record."""
    rec = {}
    rc, up, err = _ssh(host, "uptime")
    rec["uptime"] = up if rc == 0 else f"UNREACHABLE rc={rc} {err[:120]}"
    print(f"  uptime: {rec['uptime']}")
    if rc != 0:
        rec["single_writer"] = "UNKNOWN (unreachable)"
        return rec
    rc, ps, _ = _ssh(host, "ps w | grep -E 'v30ctl|serve' | grep -v grep || true")
    others = [l for l in ps.splitlines() if l.strip()]
    rec["board_procs"] = others
    rec["single_writer"] = "VIOLATED" if others else "OK"
    for l in others:
        print(f"    *** {l}")
    lp = subprocess.run(["bash", "-lc", "pgrep -af '[v]30ctl.py serve' || true"],
                        capture_output=True, text=True).stdout.strip()
    rec["local_serve_procs"] = [l for l in lp.splitlines() if l.strip()]
    if rec["local_serve_procs"]:
        rec["single_writer"] = "VIOLATED"
        print(f"  *** local serve client(s): {rec['local_serve_procs']}")
    if rec["single_writer"] == "OK":
        print("  no v30/serve process on the board -> SINGLE WRITER")
    return rec


def _flash_pin():
    p = ROOT / "sw" / "testdata" / "flash_log.jsonl"
    ls = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
    return {"entries": len(ls), "tail": ls[-1]}


def cmd_run(a):
    v30run, HOST, div_guard, pin_div, DIV = _board()
    cal = _cal()
    d = OUT / "board"
    d.mkdir(parents=True, exist_ok=True)

    man = {"tool": "ie_pinfall_cell run", "host": HOST, "use_core": False,
           "div": DIV, "spec": "docs/notes/ie_pinfall_cell_prereg_2026-08-11.md",
           "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "flash": _flash_pin(),
           "images": {k: image_sha(k) for k in LEGS},
           "div_guards": []}
    print("== single-writer / reachability")
    man["preflight"] = single_writer(HOST)
    if man["preflight"]["single_writer"] != "OK" and not a.force:
        (d / "manifest_aborted.json").write_text(json.dumps(man, indent=1))
        raise SystemExit("single-writer check did not pass -- STOP (CLAUDE.md)")
    print(f"== flash pin: {man['flash']['entries']} entries, "
          f"sof {man['flash']['tail']['sha256'][:16]}...")
    pin_div()
    man["div_guards"].append(("preflight", div_guard("preflight")))

    errs = {"n": 0, "run": 0}

    def cap(img, w, evt, ncap):
        for attempt in (1, 2, 3):
            try:
                recs, fired, words = v30run.run_image(
                    img, HOST, tag="iepf", waits=w, use_core=False, div=DIV,
                    evt=evt, want_raw=True, cap=ncap)
                errs["run"] = 0
                return words, {"fired": bool(fired)}
            except v30run.RigMismatch as e:
                raise SystemExit(
                    f"RIG MISMATCH -- the rig is not holding the directive it "
                    f"was handed (INV-1's own failure mode): {e}.  STOP; a "
                    f"rig-integrity finding outranks the cell.")
            except Exception as e:                            # noqa: BLE001
                errs["n"] += 1
                errs["run"] += 1
                print(f"    transport error ({errs['run']}): {e}", flush=True)
                if errs["run"] >= 3:
                    raise SystemExit(
                        "three consecutive transport errors -- STOP.  A rig "
                        "finding outranks the cell (CLAUDE.md).")
                time.sleep(2)
        raise SystemExit("unreachable")

    strata = _select(a.strata)
    table = []
    unstable = []
    secs = 0.0
    for s in strata:
        man["div_guards"].append((stratum_key(s[0], s[1]),
                                  div_guard(stratum_key(s[0], s[1]))))
        t, u, sec = _sweep(cal, [s], cap, "board", d,
                           reps_every=a.reps_every, reps=a.reps, limit=a.limit)
        table += t
        unstable += u
        secs += sec
        out_table = _merge(d, table)
        man["cells"] = len(out_table)
        man["seconds"] = round(secs, 1)
        man["transport_errors"] = errs["n"]
        man["unstable"] = unstable
        (d / "manifest.json").write_text(json.dumps(man, indent=1))
        (d / "table.json").write_text(json.dumps(out_table, indent=1))
    man["div_guards"].append(("final", div_guard("final")))
    out_table = _merge(d, table)
    man["cells"] = len(out_table)
    (d / "manifest.json").write_text(json.dumps(man, indent=1))
    (d / "table.json").write_text(json.dumps(out_table, indent=1))
    print(f"\n  board: {len(table)} cells in {secs:.0f}s, "
          f"{errs['n']} transport errors, {len(unstable)} unstable")
    print(f"  SHA256SUMS: {_sha_dir(d)} files")
    return 0


def _sha_dir(dd):
    lines = []
    for p in sorted(dd.rglob("*")):
        if p.is_file() and p.name != "SHA256SUMS":
            lines.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  "
                         f"{p.relative_to(dd)}")
    (dd / "SHA256SUMS").write_text("\n".join(lines) + "\n")
    return len(lines)


# --------------------------------------------------------------------------- #
def cmd_confirm(a):
    """RE-CAPTURE the boundary cells at high repetition.

    A threshold is only a threshold if the clock either side of it is STABLE.
    This re-runs every cell of the named strata whose `fall_off` lands within
    `--band` clocks of the measured T*, `--reps` times each, and reports the
    distinct capture streams per cell.  A cell that flips is CHARACTERISED, not
    forced to be deterministic (the RR1 / s13 P5 precedent)."""
    v30run, HOST, div_guard, pin_div, DIV = _board()
    cal = _cal()
    board = _load("board")
    d = OUT / "board-confirm"
    d.mkdir(parents=True, exist_ok=True)
    man = {"tool": "ie_pinfall_cell confirm", "host": HOST, "use_core": False,
           "div": DIV, "reps": a.reps, "band": a.band,
           "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "flash": _flash_pin(), "div_guards": [], "cells": {}}
    print("== single-writer / reachability")
    man["preflight"] = single_writer(HOST)
    if man["preflight"]["single_writer"] != "OK":
        raise SystemExit("single-writer check did not pass -- STOP")
    pin_div()
    man["div_guards"].append(("preflight", div_guard("confirm")))
    want = _select(a.strata)
    errs = 0
    unstable = []
    t0 = time.time()
    for leg, w, _full in want:
        ts_, _sharp, _sel = threshold(board, leg, w)
        if ts_ is None:
            continue
        key = stratum_key(leg, w)
        img, meta = image_of(leg)
        anchor_lin = meta["anchor_linear"]
        cells = [r for r in board
                 if r["leg"] == leg and r["waits"] == w and r.get("ok")
                 and r.get("fall_off") is not None
                 and abs(r["fall_off"] - ts_) <= a.band]
        man["div_guards"].append((key, div_guard(key)))
        shard = {}
        for r in cells:
            shas, takes = [], []
            keep = {}
            for _ in range(a.reps):
                recs, fired, words = v30run.run_image(
                    img, HOST, tag="iepfc", waits=w, use_core=False, div=DIV,
                    evt=(anchor_lin, r["delay"], r["hold"], 0),
                    want_raw=True, cap=cal["cells"][key]["ncap"])
                sha = hashlib.sha256(
                    ("\n".join(f"{x:016x}" for x in words) + "\n").encode()
                ).hexdigest()
                shas.append(sha)
                takes.append(features(_rows_from_words(words), leg,
                                      anchor_lin).get("taken"))
                keep.setdefault(sha, [f"{x:016x}" for x in words])
            rec = {"reps": a.reps, "distinct": len(set(shas)),
                   "shas": shas, "takes": takes,
                   "take_stable": len(set(takes)) == 1,
                   "T_star": ts_, "fall_off": r["fall_off"],
                   "rise_off": r["rise_off"], "hold": r["hold"]}
            man["cells"][r["cell"]] = rec
            shard[r["cell"]] = keep
            if not rec["take_stable"] or rec["distinct"] > 1:
                unstable.append(r["cell"])
        with gzip.open(d / f"{key}.raw.json.gz", "wt") as fh:
            json.dump(shard, fh, separators=(",", ":"))
        print(f"  {key}: {len(cells)} boundary cells x {a.reps} reps  "
              f"T*={ts_}  ({time.time() - t0:.0f}s)", flush=True)
    man["div_guards"].append(("final", div_guard("final")))
    man["unstable"] = unstable
    man["transport_errors"] = errs
    man["seconds"] = round(time.time() - t0, 1)
    (d / "manifest.json").write_text(json.dumps(man, indent=1))
    print(f"\n  confirm: {len(man['cells'])} cells x {a.reps} reps, "
          f"{len(unstable)} unstable")
    print(f"  SHA256SUMS: {_sha_dir(d)} files")
    return 0


# --------------------------------------------------------------------------- #
# the PRE-REGISTERED hypothesis table
# --------------------------------------------------------------------------- #
# Each hypothesis names the SMALLEST `fall_off` at which a maskable request is
# TAKEN, on a leg whose rise is well before the IE rise.  `None` means "never
# on a finite pulse that ends before the acknowledge".
HYPOTHESES = {
    "H1-ucore-3": {
        "T_star": 3,
        "says": "silicon's recognition needs the pin HIGH at t_ei+2 -- the "
                "ucore's own measured threshold, i.e. the engine is already "
                "right and the C2 residue is NOT a threshold question",
        "implies": "the §64.1 four and fz2c/404040 are not separated by this "
                   "cell; C-gamma stays blocked and the seats need another "
                   "mechanism",
    },
    "H2-later-4": {
        "T_star": 4,
        "says": "silicon needs the pin one clock LATER than the ucore: the "
                "engine takes on a pin the die has already let go",
        "implies": "the four `run - arm == 2` seats (ucore takes, silicon does "
                   "not) are explained EXACTLY, and fz2c/404040 (both take) "
                   "must have its fall one clock later than theirs",
    },
    "H2-later-5": {
        "T_star": 5,
        "says": "as H2-later-4, two clocks later",
        "implies": "same shape; separates the seats only if their falls "
                   "straddle t_ei+4",
    },
    "H3-latch": {
        "T_star": -1,
        "says": "silicon REMEMBERS a request that was present before IE rose "
                "and is gone by the time IE is set -- a true IE-rise latch",
        "implies": "the ucore is right in kind and too SHORT in reach; the "
                   "four seats are then NOT explained by the threshold at all",
    },
    "H4-level-only": {
        "T_star": 9,
        "says": "no memory whatever: the pin must still be high when the "
                "microcode reaches its INTA, i.e. T* equals the acknowledge "
                "latency",
        "implies": "refuted outright by fz2_c2_results §5.3 -- 31 of 251 chip "
                   "acknowledge runs BEGIN at or after the pin's own fall -- "
                   "and it is registered so the cell can say so on its own "
                   "evidence rather than by citation",
    },
}

WAKE_HYPOTHESES = {
    "W1-always-suspend": "0 CODE cycles between the HALT display and the first "
                         "INTA at EVERY vectoring sweep point (wave-5's C-gamma "
                         "as written, with irq_int_lvl a sufficient carrier)",
    "W2-always-prefetch": ">= 1 CODE cycle at EVERY vectoring sweep point (the "
                          "ucore's current behaviour is the law and the seats "
                          "are something else)",
    "W3-phase-split": "the count DEPENDS on the pin phase, with a threshold "
                      "clock this cell names -- the outcome wave-5's own "
                      "measured split implies, and the one that re-opens "
                      "C-gamma keyed on a measured quantity",
}


def cmd_predict(a):
    OUT.mkdir(parents=True, exist_ok=True)
    cal = _cal()
    p = {"tool": "ie_pinfall_cell predict",
         "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
         "images": {k: image_sha(k) for k in LEGS},
         "programs": {k: {"what": v["what"],
                          "bytes": body_of(k).hex()} for k, v in LEGS.items()},
         "hypotheses": HYPOTHESES,
         "wake_hypotheses": WAKE_HYPOTHESES,
         "grid": {"rise_off_full": RISE_OFF_FULL, "rise_off_ctl": RISE_OFF_CTL,
                  "fall_off": FALL_OFF, "hold_inf": HOLD_INF},
         "strata": [{"leg": l, "waits": w, "full": f,
                     "cells": len(grid(l, w, f))} for l, w, f in STRATA],
         "calib": cal["cells"]}
    p["total_cells"] = sum(s["cells"] for s in p["strata"])
    # WHERE THE CELL DISCRIMINATES AND WHERE IT DOES NOT -- stated in the
    # artifact, so a sweep point that proves nothing cannot be quoted as if it
    # did.  Two hypotheses are separated only at fall_off values BETWEEN their
    # thresholds; everywhere else they agree by construction.
    ts = sorted({h["T_star"] for h in HYPOTHESES.values()})
    p["discrimination"] = {
        "separating_fall_offsets": {
            f"{a_}|{b_}": list(range(min(a_, b_), max(a_, b_)))
            for i, a_ in enumerate(ts) for b_ in ts[i + 1:]},
        "null_region": (f"fall_off >= {max(ts)} : EVERY hypothesis says TAKEN. "
                        f"fall_off < {min(ts)} : EVERY hypothesis says NOT "
                        f"TAKEN.  Points there are coverage, not evidence, and "
                        f"they are reported as such."),
    }
    PRED.write_text(json.dumps(p, indent=1))
    print(json.dumps({k: v for k, v in p.items()
                      if k not in ("calib", "programs")}, indent=1))
    print(f"  -> {PRED}  ({p['total_cells']} cells)")
    return 0


# --------------------------------------------------------------------------- #
# scoring
# --------------------------------------------------------------------------- #
def _load(which):
    p = OUT / which / "table.json"
    if not p.exists():
        raise SystemExit(f"no {p}")
    return json.loads(p.read_text())


def threshold(rows, leg, waits):
    """T* = min fall_off at which the cell is TAKEN, over cells whose RISE is
    strictly before t_ei (so the pin is present across the IE rise and the only
    question is when it leaves).  Returns (T*, sharp, taken_offsets)."""
    sel = [r for r in rows if r["leg"] == leg and r["waits"] == waits
           and r.get("ok") and r.get("rise_off") is not None
           and r["rise_off"] < 0 and r.get("fall_off") is not None]
    tk = sorted({r["fall_off"] for r in sel if r["taken"]})
    nt = sorted({r["fall_off"] for r in sel if not r["taken"]})
    if not tk:
        return None, None, sel
    sharp = (not nt) or max(nt) < min(tk)
    return min(tk), sharp, sel


COLS = ["taken", "ack_off", "n_inta", "halt_first", "n_halt", "halt_off",
        "ack_off_hlt", "wake_prefetch", "rise", "fall", "t_ei", "anchor_t1",
        "n_rows"]


def cmd_score(a):
    from collections import Counter
    board = _load("board")
    core = None
    try:
        core = _load("core")
    except SystemExit:
        pass
    ck = {r["cell"]: r for r in (core or [])}
    out = {"thresholds": {}, "wake": {}, "columns": {}, "controls": {},
           "disagree": [], "phase_diffs": []}

    print("== 0. THE §3 CONTROLS -- nothing below is quotable without these\n")
    for leg in ("ierun", "iehlt"):
        for w in (0, 3):
            sel = [r for r in board if r["leg"] == leg and r["waits"] == w]
            if not sel:
                continue
            pre = [r for r in sel if not r["ok"]]
            ok = [r for r in sel if r["ok"]]
            tk = [r for r in ok if r["taken"]]
            out["controls"][stratum_key(leg, w)] = {
                "n": len(sel), "pre_di": len(pre), "ok": len(ok),
                "ok_taken": len(tk),
                "not_taken_holds": sorted({r["hold"] for r in ok
                                           if not r["taken"]})}
            print(f"  {leg} w{w}: {len(sel)} cells -- {len(pre)} recognised "
                  f"BEFORE t_ei (IE was set: the pin path works), "
                  f"{len(tk)}/{len(ok)} of the rest TAKEN; the untaken are "
                  f"holds {sorted({r['hold'] for r in ok if not r['taken']})}")

    print("\n== 1. T*  (min fall_off TAKEN, rise strictly before t_ei)\n")
    print("  leg      w | board T*  sharp | core T*  sharp | delta")
    for leg in ("eirun", "eihlt"):
        for w in (0, 1, 2, 3):
            bt, bs, sel = threshold(board, leg, w)
            if not sel:
                continue
            ct, cs, _ = threshold(core or [], leg, w)
            out["thresholds"][stratum_key(leg, w)] = {
                "board": bt, "board_sharp": bs, "core": ct, "core_sharp": cs,
                "n": len(sel)}
            dl = None if (bt is None or ct is None) else bt - ct
            print(f"  {leg:8s} {w} | {str(bt):8s} {str(bs):5s} | "
                  f"{str(ct):7s} {str(cs):5s} | {dl}")

    print("\n== 2. hypothesis verdicts (eirun, the clean recognition leg)")
    for w in (0, 1, 2, 3):
        bt, _bs, _ = threshold(board, "eirun", w)
        if bt is None:
            continue
        hits = [n for n, h in HYPOTHESES.items() if h["T_star"] == bt]
        print(f"  w{w}: T* = {bt}  -> "
              f"{hits[0] if hits else 'NONE of the registered five'}"
              f"{'' if hits else ' (registered outcome six/seven)'}")

    print("\n== 3. wake prefetch (eihlt): CODE cycles, HALT display -> INTA")
    for w in (0, 1, 2, 3):
        sel = [r for r in board if r["leg"] == "eihlt" and r["waits"] == w
               and r.get("ok") and r.get("wake_prefetch") is not None]
        if not sel:
            continue
        vals = sorted({r["wake_prefetch"] for r in sel})
        dis = sum(1 for r in sel
                  if ck.get(r["cell"], {}).get("wake_prefetch")
                  != r["wake_prefetch"])
        out["wake"][f"w{w}"] = {"values": vals, "n": len(sel),
                                "core_disagreements": dis}
        parts = []
        for v in vals:
            g = [r["rise_off"] for r in sel if r["wake_prefetch"] == v]
            parts.append(f"{v}: rise_off [{min(g)},{max(g)}] x{len(g)}")
        print(f"  w{w}: n={len(sel)}  {' | '.join(parts)}  "
              f"core disagreements {dis}")

    print("\n== 4. board vs core, EVERY measured column")
    diff, tot = Counter(), Counter()
    for r in board:
        c = ck.get(r["cell"])
        if not c or not r.get("ok") or not c.get("ok"):
            continue
        for k in COLS:
            tot[k] += 1
            if r.get(k) != c.get(k):
                diff[k] += 1
                out["phase_diffs"].append(
                    {"cell": r["cell"], "col": k, "board": r.get(k),
                     "core": c.get(k), "rise_off": r.get("rise_off"),
                     "fall_off": r.get("fall_off"), "hold": r.get("hold")})
                if k == "taken":
                    out["disagree"].append(
                        {"cell": r["cell"], "board": r.get("taken"),
                         "core": c.get("taken"), "rise_off": r.get("rise_off"),
                         "fall_off": r.get("fall_off")})
    for k in COLS:
        out["columns"][k] = {"diff": diff[k], "compared": tot[k]}
        flag = "  <== DIFFERS" if diff[k] else ""
        print(f"  {k:16s} {diff[k]:5d} / {tot[k]:5d}{flag}")

    print("\n== 5. the high-repetition confirmation")
    cp = OUT / "board-confirm" / "manifest.json"
    if cp.exists():
        m = json.loads(cp.read_text())
        cells = m["cells"]
        tk = [k for k, v in cells.items() if not v["take_stable"]]
        ds = [k for k, v in cells.items() if v["distinct"] > 1]
        out["confirm"] = {"cells": len(cells), "reps": m["reps"],
                          "take_unstable": len(tk),
                          "stream_distinct": len(ds)}
        print(f"  {len(cells)} boundary cells x {m['reps']} reps = "
              f"{len(cells) * m['reps']} captures: TAKE-unstable {len(tk)}, "
              f"stream-distinct {len(ds)}")
    (OUT / "score.json").write_text(json.dumps(out, indent=1))
    print(f"\n  -> {OUT / 'score.json'}")
    return 0


# --------------------------------------------------------------------------- #
# the booked seats, scored against the MEASURED threshold
# --------------------------------------------------------------------------- #
SEATS = {
    # fz2_c2_results_2026-08-10.md §5.2, the nine load-bearing clocks
    "fz2c/404040": "§64.1 sharp -- silicon AGREES (takes); run-arm == 2",
    "fz2c/405002": "c2a -- silicon disagrees; run-arm == 2",
    "fz2c/405013": "c2a -- silicon disagrees; run-arm == 2",
    "fz2c/405072": "c2a -- silicon disagrees; run-arm == 2",
    "fz2e/512056": "c2a -- silicon disagrees; run-arm == 2",
    "fz2e/531000": "silicon AGREES; run-arm == 3",
    "fz2e/513019": "improved by the C2 landing; run-arm == 5",
    # wave-5 C2 seats (the C-gamma population)
    "fz2c/404071": "C2 seat -- silicon SUSPENDS at the vectoring wake",
    "fz2e/514044": "C2 seat -- silicon SUSPENDS at the vectoring wake",
    "fz2e/516001": "C2 seat -- silicon SUSPENDS at the vectoring wake",
    "fz2e/516065": "C2 -- 2 INTA both legs, divergence is WHEN not HOW MANY",
}


def cmd_seats(a):
    """Read the banked FABRIC captures for the booked seats and report, for
    each, the coordinates the measured law is a function of -- pin rise, pin
    fall, the acknowledge, and their separations.  ENGINE-FREE: chip rows only.

    This does NOT re-fit anything.  The threshold comes from `score`, on the
    directed cell; this command only asks whether the seats fall on the side of
    it their silicon behaviour says they should."""
    led = json.loads((ROOT / "sw" / "testdata" / "fz2" /
                      "fz2_failure_ledger_f17_2026-08-11.json").read_text())
    by = {f["seed"]: f for f in led["failures"]}
    sc = json.loads((OUT / "score.json").read_text()) if \
        (OUT / "score.json").exists() else {}
    print("== booked seats, on their own banked FABRIC rows\n")
    rows_out = []
    for seed, why in SEATS.items():
        rec = by.get(seed)
        cap = _seat_capture(seed, rec)
        if cap is None:
            print(f"  {seed:14s} NO CAPTURE FOUND  ({why})")
            rows_out.append({"seed": seed, "why": why, "capture": None})
            continue
        r = _seat_features(cap)
        r.update(seed=seed, why=why,
                 in_f17_ledger=bool(rec),
                 family=(rec or {}).get("family"))
        rows_out.append(r)
        af = [a["ack_minus_fall"] for a in r["chip_acks"]]
        mr = [(m["chip"], m["core_minus_chip"], m["chip_halt_rows_before"])
              for m in r["matched_runs"]]
        print(f"  {seed:14s} chip runs={r['chip_n_runs']} core runs="
              f"{r['core_n_runs']} ({r['extra_core_runs']:+d})  "
              f"extra HALT-adjacent={r['halt_adjacent_extra']}/"
              f"{len(r['extra_runs'])}  ack-fall={af}")
        print(f"                 matched (chip_row, core-chip, chip HALT rows "
              f"before)={mr}")
        print(f"                 {why}")
    (OUT / "seats.json").write_text(json.dumps(
        {"threshold": sc.get("thresholds", {}), "seats": rows_out}, indent=1))
    print(f"\n  -> {OUT / 'seats.json'}")
    return 0


def _seat_capture(seed, rec):
    if rec and rec.get("capture"):
        p = ROOT / rec["capture"]
        if p.exists():
            return p
    cid, k = seed.split("/")
    for p in sorted((ROOT / "sw" / "testdata" / "campaigns" / cid /
                     "captures").glob(f"*_{k}_*.json.gz")):
        return p
    return None


def _seat_features(path):
    """The banked fuzz-v2 capture carries BOTH legs as already-decoded rows:
    `real` = the CHIP, `sim` = the core.  Nothing here decodes words and
    nothing here runs an engine -- the core column is READ, not produced."""
    with gzip.open(path, "rt") as fh:
        cap = json.load(fh)
    out = {"capture": str(path.relative_to(ROOT)),
           "n_rows": len(cap.get("real", []))}
    for tag, key in (("chip", "real"), ("core", "sim")):
        rows = cap.get(key) or []
        rise = [i for i, r in enumerate(rows)
                if r["pin_int"] == 1 and (i == 0 or rows[i - 1]["pin_int"] == 0)]
        fall = [i for i, r in enumerate(rows)
                if r["pin_int"] == 0 and i and rows[i - 1]["pin_int"] == 1]
        inta = [i for i, r in enumerate(rows)
                if r["t"] == 1 and r["bs_early"] == 0]
        # INTA RUNS: maximal runs of consecutive INTA cycles (the A30 reader)
        runs = []
        for i in inta:
            if runs and i - runs[-1][-1] < 12:
                runs[-1].append(i)
            else:
                runs.append([i])
        out[f"{tag}_n_rise"] = len(rise)
        out[f"{tag}_rises"] = rise[:8]
        out[f"{tag}_falls"] = fall[:8]
        out[f"{tag}_n_inta"] = len(inta)
        out[f"{tag}_n_runs"] = len(runs)
        out[f"{tag}_run_starts"] = [r[0] for r in runs][:8]
        # for every acknowledge run, where the pin last LEFT before it
        acks = []
        for r in runs:
            pf = [f for f in fall if f <= r[0]]
            pr = [x for x in rise if x <= r[0]]
            acks.append({"ack": r[0],
                         "prev_fall": (pf[-1] if pf else None),
                         "prev_rise": (pr[-1] if pr else None),
                         "ack_minus_fall": (r[0] - pf[-1]) if pf else None,
                         "pin_at_ack": bool(rows[r[0]]["pin_int"])})
        out[f"{tag}_acks"] = acks
    out["extra_core_runs"] = out["core_n_runs"] - out["chip_n_runs"]
    # THE SEAT TEST THE DIRECTED CELL MAKES POSSIBLE.  The cell's only
    # board-vs-core TAKE divergence is at a HALT WAKE, so a seat is in that
    # regime only if the acknowledge the core adds is HALT-adjacent.  Counted
    # on the core's own rows, engine-free: BS = HALT in the 40 clocks before
    # each core acknowledge run the chip does not have.
    chip_rows = cap.get("real") or []
    core_rows = cap.get("sim") or []

    def _runs(rows):
        ia = [i for i, r in enumerate(rows)
              if r["t"] == 1 and r["bs_early"] == 0]
        rr = []
        for i in ia:
            if rr and i - rr[-1][-1] < 12:
                rr[-1].append(i)
            else:
                rr.append([i])
        return rr
    rc, ro = _runs(chip_rows), _runs(core_rows)
    extra = [r for r in ro if not any(abs(r[0] - x[0]) < 30 for x in rc)]
    out["extra_runs"] = [
        {"at": r[0],
         "halt_rows_before": sum(1 for i in range(max(0, r[0] - 40), r[0])
                                 if core_rows[i]["bs_early"] == 3)}
        for r in extra]
    out["halt_adjacent_extra"] = sum(1 for e in out["extra_runs"]
                                     if e["halt_rows_before"])
    # and, for the runs BOTH legs have, how far apart they are
    out["matched_runs"] = []
    for x in rc:
        if not ro:
            continue
        m = min(ro, key=lambda b: abs(b[0] - x[0]))
        if abs(m[0] - x[0]) < 40:
            out["matched_runs"].append(
                {"chip": x[0], "core": m[0], "core_minus_chip": m[0] - x[0],
                 "chip_halt_rows_before": sum(
                     1 for i in range(max(0, x[0] - 25), x[0])
                     if chip_rows[i]["bs_early"] == 3)})
    return out


# --------------------------------------------------------------------------- #
def cmd_idle(a):
    import b1_recapture
    r = b1_recapture.board_idle()
    print(f"board_idle -> {r}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("calib").set_defaults(fn=cmd_calib)
    sub.add_parser("predict").set_defaults(fn=cmd_predict)

    p = sub.add_parser("core")
    p.add_argument("--strata", default="")
    p.add_argument("--limit", type=int, default=0)
    p.set_defaults(fn=cmd_core)

    p = sub.add_parser("run")
    p.add_argument("--strata", default="")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--reps", type=int, default=3)
    p.add_argument("--reps-every", type=int, default=20)
    p.add_argument("--force", action="store_true",
                   help="proceed past a failed single-writer check (recorded)")
    p.set_defaults(fn=cmd_run)

    p = sub.add_parser("confirm")
    p.add_argument("--strata", default="eihlt_w0,eihlt_w1,eihlt_w2,eihlt_w3,"
                                       "eirun_w0,eirun_w1,eirun_w2,eirun_w3")
    p.add_argument("--reps", type=int, default=11)
    p.add_argument("--band", type=int, default=2)
    p.set_defaults(fn=cmd_confirm)

    sub.add_parser("score").set_defaults(fn=cmd_score)
    sub.add_parser("seats").set_defaults(fn=cmd_seats)
    sub.add_parser("idle").set_defaults(fn=cmd_idle)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
