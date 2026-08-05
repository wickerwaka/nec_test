#!/usr/bin/env python3
"""sm3_s16_cell -- THE DIRECTED DISPLAY-WINDOW WALK (SM3 sitting 16, task #36).

WHAT IT IS FOR.  `ucore_provenance.md` §76.D.3 forbids a re-land of F52 from
scoring itself on the four s10/s13 HLT delay sweeps: those numbers are known,
and a bar written after seeing them is not a bar.  This is the NEW authorising
population.  It did not exist when anything was scored.

WHAT IT WALKS.  The HALT window's PIN GROUP, directly: for every wait level, a
HALT form whose wake fetch lands at a swept pin-event delay, so the woken code
fetch's DISPLAY and the acknowledge's DISPLAY are driven across the whole band
where the announcement has to wait for a busy bus.  The observables are the
composed A19-16 nibble on each clock of a display window, the UBE pin across a
WITHDRAWN announcement, and the T-state the analyser assigns to the row after
the window.

WHY THE PROGRAMS ARE NOT THE SWEEP'S.  The s10/s13 sweeps run ONE fixed program
per form, and that program's wake-fetch linear address is `0x57CB4`, whose top
nibble `5` is a LEGAL segment-status code ({md=0, ie=1, segc=SS}).  ucsim-t
§26.7 named this the confound: on such a capture "address" and "status" are not
separable on the display clock.  This cell carries SIX programs per form, chosen
OFFLINE and FROZEN below, spanning three classes:

    SAME        the wake nibble EQUALS the status nibble -- the confounded case,
                kept deliberately as the control the sweeps are;
    legal-diff  the wake nibble is a different LEGAL status code;
    IMPOSSIBLE  the wake nibble has bit 3 set, i.e. it names the 8080 EMULATION
                MODE bit in a capture that is not in emulation mode.  No segment
                status can carry it, so the nibble NAMES ITSELF as the address.

Three forms give two status nibbles: `HLT.INT` (ie=1 -> `0x6`), `HLT.RES`
(ie=0 -> `0x2`) and `HLT.NMI` (ie random per program -> either).

BOARD DISCIPLINE (CLAUDE.md), asserted in code:
  * SOCKET ONLY -- `es.EMIT_USE_CORE is False`, asserted at import;
  * the DIVIDER IS PINNED on every probe and the runner's own readback is
    RECORDED; UNPINNED is a rig-integrity FINDING and this says so;
  * raw 64-bit capture words retained with a sha256 BESIDE the full per-clock
    row stream, never digests alone;
  * `idle` runs `board_idle()` and states the result;
  * no flashing anywhere, and nothing here writes a bitstream.

Usage:
    python3 sw/sm3_s16_cell.py plan                 # offline: print the frozen population
    python3 sw/sm3_s16_cell.py capture [--reps 3] [--waits 0,1,2,3]
    python3 sw/sm3_s16_cell.py measure              # offline: the four predictions
    python3 sw/sm3_s16_cell.py sha
    python3 sw/sm3_s16_cell.py idle
"""
import argparse
import gzip
import hashlib
import json
import random
import sys
import time
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

import emit_suite as es                                     # noqa: E402
import v30run                                               # noqa: E402
from t2b_board import HOST                                  # noqa: E402
from s10_board import (reps_capture, pin_div, DIV_OF_RECORD,  # noqa: E402
                       _evt_image)

OUT = ROOT / "sw" / "testdata" / "sm3-s16cell"
SUITE_ROOT = ROOT / "tests" / "v30"

assert es.EMIT_USE_CORE is False, \
    "S16 refuses to run: truth source is not the socket"
assert DIV_OF_RECORD == es.EMIT_DIV, \
    "divider of record disagrees with the emission pin"

# --------------------------------------------------------------------------- #
# THE FROZEN POPULATION.  Chosen offline from `gen_evt_case` alone -- no board,
# no capture -- by the nibble classes above, and written down here so the
# population is fixed before contact.  `plan` reprints it from the generator.
# --------------------------------------------------------------------------- #
FORMS = ("HLT.INT", "HLT.RES", "HLT.NMI")
PROGRAMS = (0, 1, 2, 3, 4, 5)
WAITS = (0, 1, 2, 3)
DELAYS = tuple(range(0, 21))
SEED = "v30-sm3-s16/{form}/p{p}"


def gen_case(form, p):
    """The frozen program: one RNG seed string, one draw, no rerolls."""
    spec = es.EVT_FORMS[form]
    rng = random.Random(SEED.format(form=form, p=p))
    return spec, es.gen_evt_case(spec, rng)


def nibbles(case):
    """(wake-fetch A19-16, segment-status nibble, class) for one program."""
    r = case["regs"]
    anchor = ((r["cs"] << 4) + r["ip"]) & 0xFFFFF
    wake = (anchor + 2) & 0xFFFFF
    ie = (r["flags"] >> 9) & 1
    stat = (ie << 2) | 2                      # data_ps(CS) = {md=0, ie, 2'b10}
    a = (wake >> 16) & 0xF
    cls = "IMPOSSIBLE" if a >= 8 else ("SAME" if a == stat else "legal-diff")
    return a, stat, cls


def suite_dir(waits, p):
    return SUITE_ROOT / f"s16-dispwalk-w{waits}-p{p}"


# --------------------------------------------------------------------------- #
def div_guard(tag):
    """s13_board.div_guard, verbatim in substance: PIN, then ask the transport
    what it commanded and RECORD the answer.  UNPINNED is a FINDING."""
    pin_div()
    r = v30run._runners.get(HOST)
    rb = (r.div_readback if r is not None
          else "div=UNKNOWN (no live serve runner to ask)")
    state = "PINNED" if "UNPINNED" not in str(rb) and "UNKNOWN" not in str(rb) \
        else "UNPINNED"
    print(f"  [div guard] {tag}: {rb}   -> {state}", flush=True)
    if state != "PINNED":
        print("  [div guard] *** UNPINNED READBACK -- recorded, not smoothed "
              "***", flush=True)
    return {"readback": str(rb), "state": state}


def _sha_dir(d):
    lines = []
    for f in sorted(d.iterdir()):
        if f.is_file() and f.name != "SHA256SUMS":
            lines.append(f"{hashlib.sha256(f.read_bytes()).hexdigest()}  "
                         f"{f.name}")
    (d / "SHA256SUMS").write_text("\n".join(lines) + "\n")
    return len(lines)


# --------------------------------------------------------------------------- #
def cmd_plan(a):
    print(f"SM3-S16 the display walk: {len(FORMS)} forms x {len(PROGRAMS)} "
          f"programs x {len(WAITS)} waits x {len(DELAYS)} delays = "
          f"{len(FORMS)*len(PROGRAMS)*len(WAITS)*len(DELAYS)} cells")
    cls_n = {}
    for form in FORMS:
        for p in PROGRAMS:
            _spec, case = gen_case(form, p)
            r = case["regs"]
            anch = ((r["cs"] << 4) + r["ip"]) & 0xFFFFF
            a, stat, cls = nibbles(case)
            cls_n[cls] = cls_n.get(cls, 0) + 1
            print(f"  {form:8s} p{p}  cs={r['cs']:04x} ip={r['ip']:04x} "
                  f"anchor={anch:05x}  wake_nib={a:x}  status_nib={stat:x}  "
                  f"{cls}")
    print(f"  classes: {cls_n}")
    return 0


# --------------------------------------------------------------------------- #
def cmd_capture(a):
    OUT.mkdir(parents=True, exist_ok=True)
    waits_sel = [int(x) for x in a.waits.split(",")]
    man = {"probe": "SM3-S16 directed display walk", "use_core": False,
           "host": HOST, "spec": "docs/notes/sm3_s16_prereg_2026-08-05.md",
           "forms": list(FORMS), "programs": list(PROGRAMS),
           "waits": waits_sel, "delays": list(DELAYS), "reps": a.reps,
           "cells": {}, "div_guard": {}}
    t0 = time.time()
    man["div_guard"]["open"] = div_guard("s16 open")
    n = err = 0
    for waits in waits_sel:
        for p in PROGRAMS:
            sd = suite_dir(waits, p)
            sd.mkdir(parents=True, exist_ok=True)
            for form in FORMS:
                spec = es.EVT_FORMS[form]
                tests = []
                for di, delay in enumerate(DELAYS):
                    try:
                        _s, case = gen_case(form, p)
                    except es.ComposeError:
                        continue
                    case["delay"] = delay          # THE SWEEP AXIS
                    image, evt, _ = _evt_image(spec, case)
                    key = f"{form}_p{p}_w{waits}_d{delay}"
                    try:
                        rec, rows, raw = reps_capture(
                            image, waits=waits, evt=evt, tag="s16",
                            reps=a.reps, divs=(DIV_OF_RECORD,))
                    except Exception as e:                  # noqa: BLE001
                        err += 1
                        print(f"    CAPTURE ERR {key}: {str(e)[:120]}",
                              flush=True)
                        continue
                    man["cells"][key] = rec
                    with gzip.open(OUT / f"{key}.rows.json.gz", "wt") as f:
                        json.dump(rows, f, separators=(",", ":"))
                    with gzip.open(OUT / f"{key}.raw.hex.gz", "wt") as f:
                        f.write("\n".join(raw) + "\n")
                    # the GOLDEN, through the standard emission path so
                    # check_core scores it with no new machinery
                    try:
                        t = es.emit_evt_case(spec, case, HOST, tag="s16g",
                                             preload_n=0, waits=waits)
                        t["idx"] = di
                        tests.append(t)
                        n += 1
                    except (es.ComposeError, es.RunError) as e:
                        err += 1
                        print(f"    golden {key}: {str(e)[:120]}", flush=True)
                if tests:
                    with gzip.open(sd / f"{form}.json.gz", "wt") as f:
                        json.dump(tests, f, separators=(",", ":"))
                print(f"  w{waits} p{p} {form}: {len(tests)} goldens "
                      f"({time.time()-t0:.0f}s)", flush=True)
    man["div_guard"]["close"] = div_guard("s16 close")
    man["seconds"] = round(time.time() - t0, 1)
    man["n_goldens"] = n
    man["errors"] = err
    (OUT / "manifest.json").write_text(json.dumps(man, indent=1))
    print(f"CAPTURE: {n} goldens, {err} errors, {man['seconds']}s")
    print(f"  SHA256SUMS: {_sha_dir(OUT)} files")
    return 0


# --------------------------------------------------------------------------- #
# THE MEASUREMENT -- the four registered predictions, read off the captured
# GOLDEN rows alone.  No model, no core: these are statements about silicon.
# --------------------------------------------------------------------------- #
BS_C, T_C, UBE_C, BUS_C, ALE_C = 7, 8, 5, 1, 0


def _windows(cy):
    """Display windows, split at the ALE row.

    A run of rows carrying one non-PASV status covers the announcement's
    DISPLAY clocks and then that cycle's own body.  The two are separated by
    the ALE row, which IS the cycle's T1 -- so the window is the part of the
    run BEFORE the ALE, and the body is the rest.  A run with no ALE in it is a
    WITHDRAWN announcement, and the whole run is the window.

    NOTE the T-state column is NOT usable to make this split: a display that
    lands inside a HALT pseudo-cycle sits on rows the analyser labels T3/Tw/T4,
    because those T-states belong to the HALT and not to the announcement.

    -> [(first, last, status, t1_row_or_None)]"""
    out = []
    i = 0
    n = len(cy)
    while i < n:
        bs = cy[i][BS_C]
        if bs == "PASV":
            i += 1
            continue
        j = i
        while j + 1 < n and cy[j + 1][BS_C] == bs:
            j += 1
        ale = next((r for r in range(i, j + 1) if cy[r][ALE_C] == 1), None)
        if ale is None:
            out.append((i, j, bs, None))
        elif ale > i:
            out.append((i, ale - 1, bs, ale))
        i = j + 1
    return out


def _addr_nibble(case, data16):
    """The A19-16 the announced CODE fetch's own address must carry, derived
    from the program's anchor and the window's held low 16 bits alone.  The
    fetch stream around a HALT is within a few bytes of the anchor, so the low
    16 bits pick the linear address out uniquely.  None if this window's low
    lanes name no address near the anchor (an acknowledge, a handler fetch, a
    stack access)."""
    r = case["regs"]
    anchor = ((r["cs"] << 4) + r["ip"]) & 0xFFFFF
    for k in range(-64, 65):
        a = (anchor + k) & 0xFFFFF
        if (a & 0xFFFF) == (data16 & 0xFFFF):
            return (a >> 16) & 0xF
    return None


def cmd_measure(a):
    stats = {"cells": 0, "windows": 0, "multi": 0,
             "P1_disp_addr": [0, 0], "P1_impossible": [0, 0],
             "P1_after_status": [0, 0],
             "P2_inta_disp_zero": [0, 0], "P2_inta_late_t1": [0, 0],
             "P3_ube_hold": [0, 0], "P4_two_sample": 0,
             "classes": {}}
    detail = []
    for waits in WAITS:
        for p in PROGRAMS:
            sd = suite_dir(waits, p)
            if not sd.exists():
                continue
            for form in FORMS:
                fn = sd / f"{form}.json.gz"
                if not fn.exists():
                    continue
                _s, case = gen_case(form, p)
                anib, stat, cls = nibbles(case)
                stats["classes"][cls] = stats["classes"].get(cls, 0) + 1
                for t in json.load(gzip.open(fn)):
                    cy = t["cycles"]
                    stats["cells"] += 1
                    for (i, j, bs, t1) in _windows(cy):
                        stats["windows"] += 1
                        L = j - i + 1
                        if L < 2:
                            continue
                        stats["multi"] += 1
                        # P1/P2: the display clock carries the ADDRESS-phase
                        # value; every later clock of the window carries the
                        # segment status.
                        hi0 = (cy[i][BUS_C] >> 16) & 0xF
                        if bs == "INTA":
                            stats["P2_inta_disp_zero"][0] += (hi0 == 0)
                            stats["P2_inta_disp_zero"][1] += 1
                            if hi0 != 0:
                                detail.append(
                                    f"P2 {form} p{p} w{waits} idx{t['idx']} "
                                    f"row {i}: INTA display hi={hi0:x} want 0")
                        else:
                            want = _addr_nibble(case, cy[i][BUS_C] & 0xFFFF)
                            if want is not None:
                                stats["P1_disp_addr"][0] += (hi0 == want)
                                stats["P1_disp_addr"][1] += 1
                                if want >= 8:
                                    stats["P1_impossible"][0] += (hi0 == want)
                                    stats["P1_impossible"][1] += 1
                                if hi0 != want:
                                    detail.append(
                                        f"P1 {form} p{p} w{waits} "
                                        f"idx{t['idx']} row {i}: hi={hi0:x} "
                                        f"want addr nibble {want:x}")
                        for r in range(i + 1, j + 1):
                            hi = (cy[r][BUS_C] >> 16) & 0xF
                            stats["P1_after_status"][0] += (hi == stat)
                            stats["P1_after_status"][1] += 1
                            if hi != stat:
                                detail.append(
                                    f"P1b {form} p{p} w{waits} idx{t['idx']} "
                                    f"row {r}: hi={hi:x} want stat={stat:x}")
                        # P2b: a LATE INTA T1 carries the status nibble
                        if bs == "INTA" and t1 is not None and t1 > i + 1:
                            hi = (cy[t1][BUS_C] >> 16) & 0xF
                            stats["P2_inta_late_t1"][0] += (hi == stat)
                            stats["P2_inta_late_t1"][1] += 1
                        # P4: the two-sample signature -- a non-PASV status on
                        # the last clock of a WITHDRAWN window whose next row
                        # the analyser calls Ti.
                        if t1 is None and j + 1 < len(cy) and \
                                cy[j][T_C] in ("T4", "Ti") and \
                                cy[j + 1][T_C] == "Ti":
                            stats["P4_two_sample"] += 1
                    # P3: UBE changes only on a display clock at cdage != 0 or
                    # on a T1.  Read as: every UBE change sits on a row whose
                    # status is non-PASV and which is not the FIRST clock of
                    # its window, or on an ALE row.
                    wins = {r: (i, j) for (i, j, _b, _t) in _windows(cy)
                            for r in range(i, j + 1)}
                    for r in range(1, len(cy)):
                        if cy[r][UBE_C] == cy[r - 1][UBE_C]:
                            continue
                        w = wins.get(r)
                        legal = (cy[r][ALE_C] == 1) or (w is not None
                                                        and r > w[0])
                        stats["P3_ube_hold"][0] += legal
                        stats["P3_ube_hold"][1] += 1
                        if not legal:
                            detail.append(
                                f"P3 {form} p{p} w{waits} idx{t['idx']} "
                                f"row {r}: UBE {cy[r-1][UBE_C]}->"
                                f"{cy[r][UBE_C]} outside an address phase")
    print(json.dumps(stats, indent=1))
    for d in detail[:40]:
        print("  " + d)
    if len(detail) > 40:
        print(f"  ... {len(detail)-40} more")
    (OUT / "measure.json").write_text(json.dumps(
        {"stats": stats, "detail": detail}, indent=1))
    return 0


# --------------------------------------------------------------------------- #
def cmd_sha(a):
    print(f"  {OUT}: {_sha_dir(OUT)} files")
    return 0


def cmd_idle(a):
    """s13_board.cmd_idle verbatim -- the session-closing idle."""
    import b1_recapture
    r = b1_recapture.board_idle()
    print(f"board_idle -> {r}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("plan").set_defaults(fn=cmd_plan)
    c = sub.add_parser("capture")
    c.add_argument("--reps", type=int, default=3)
    c.add_argument("--waits", default="0,1,2,3")
    c.set_defaults(fn=cmd_capture)
    sub.add_parser("measure").set_defaults(fn=cmd_measure)
    sub.add_parser("sha").set_defaults(fn=cmd_sha)
    sub.add_parser("idle").set_defaults(fn=cmd_idle)
    a = ap.parse_args()
    sys.exit(a.fn(a))


if __name__ == "__main__":
    main()
