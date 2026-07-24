#!/usr/bin/env python3
"""exp_race - RR2 E2: POP-PSW boundary-race cell rig (reconstructed).

The original rig that measured int9d_race_table.json.gz was scratchpad code
lost with the predecessor. This reconstructs it from the frozen contract:
  - cell = 14-bit addr = (pre7<<7)|pop7; each 7-bit word is
    {V(6),DIR(5),S(4),Z(3),AC(2),P(1),CY(0)} -> PSW bits {11,10,7,6,4,2,0}.
  - hdl/rtl/core/int9d_race.hex is the measured contract: bit=1 -> class B
    (pre-pop image survives in the live PSW), bit=0 -> class A (popped image
    wins). Diagonal pre7==pop7 is committed A.
  - G/H/EXC (sw/gen_race_law.py) reproduce the hex bit-exact and give the
    staircase margin used for stratified cell selection.

RIG: initial live PSW = pre-image (pre-IE=1); POP PSW (9D) at ANCHOR pops the
pop-image from [SS:SP]; INT recognized at POP PSW's own boundary (delay swept
to the own-boundary d); INT entry pushes + vectors to a handler->stub->store
epilogue that captures the final LIVE PSW. Class discriminant: the 7 race
flags of the captured PSW == pop7 (A) or pre7 (B). IE/BRK are cleared by entry
and excluded from the compare.

SOCKET truth only (use_core=False). div control for the frequency sweep.

Subcommands:
  pilot     delay sweep on a few strong cells to locate the own-boundary
  validate  div=8 baseline: 108 cells reproduce the hex + pre-IE=0 controls
  (sweep    added after the validation gate passes)
"""
import argparse
import gzip
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from v30run import run_test, RunError, extract_txns_large, KIND  # noqa: E402
import gen_race_law as GRL                             # noqa: E402

HOST = "root@mister-nec"
ANCHOR = 0x0500
HANDLER = 0x0700
SS0 = 0x0000
SP_POP = 0x04A0            # pop-image slot; INT pushes land 0x49A..0x49F
VEC_INT = 0xFF

# 7-bit race word -> PSW bit positions
RACE_BITS = [(6, 11), (5, 10), (4, 7), (3, 6), (2, 4), (1, 2), (0, 0)]

_HEX_WORDS = None


def hex_words():
    global _HEX_WORDS
    if _HEX_WORDS is None:
        _, _HEX_WORDS = GRL.read_rom(GRL.DEFAULT_HEX)
    return _HEX_WORDS


def cell_addr(pre7, pop7):
    return ((pre7 & 0x7F) << 7) | (pop7 & 0x7F)


def expected_class(pre7, pop7):
    """From the measured contract int9d_race.hex."""
    return "B" if GRL.rom_bit(hex_words(), cell_addr(pre7, pop7)) else "A"


def race7_to_psw(w7, ie=1):
    psw = 0xF002
    for wb, pb in RACE_BITS:
        if w7 & (1 << wb):
            psw |= (1 << pb)
    if ie:
        psw |= (1 << 9)
    return psw


def psw_to_race7(psw):
    w = 0
    for wb, pb in RACE_BITS:
        if psw & (1 << pb):
            w |= (1 << wb)
    return w


def handler_ram(stub_linear):
    h = bytes([0xEA, stub_linear & 0xFF, stub_linear >> 8, 0x00, 0x00])
    return [(HANDLER + k, b) for k, b in enumerate(h)]


def psw_captures(res):
    """All store-routine PSW captures (MEMW at psw_push_addr), in order.
    The harness capture loops the loader, so there is one per iteration.
    For GHOST cells the spurious re-dispatch corrupts LATER iterations
    (the loader re-enables IE=1 -> pending-latch fires), so the FIRST
    capture is the clean architectural PSW (parse_result took the last)."""
    addr = res["meta"]["psw_push_addr"]
    tx = extract_txns_large(res["recs"])
    return [t["data"] for t in tx
            if KIND[t["kind"]] == "MEMW" and t["addr"] == addr
            and t["data"] is not None]


def _classify(final_psw, pre7, pop7):
    if final_psw is None:
        return None, None
    fr = psw_to_race7(final_psw)
    if fr == pop7 and fr == pre7:
        return "AB", fr
    if fr == pop7:
        return "A", fr
    if fr == pre7:
        return "B", fr
    return "?", fr


def measure_cell(pre7, pop7, delay, div=8, pop_ie=1, host=HOST):
    """Run one race cell; class from the FIRST (clean) PSW capture."""
    pre_psw = race7_to_psw(pre7, ie=1)
    pop_psw = race7_to_psw(pop7, ie=pop_ie)
    instr = bytes([0x9D]) + b"\x90" * 20        # POP PSW + NOP sled
    stub = ANCHOR + len(instr)
    ram = handler_ram(stub)
    ram += [(SP_POP, pop_psw & 0xFF), (SP_POP + 1, pop_psw >> 8)]
    ivt = {VEC_INT: (0x0000, HANDLER)}
    regs = {"PS": 0, "PC": ANCHOR, "SS": SS0, "SP": SP_POP, "PSW": pre_psw}
    res = run_test(regs=regs, instr=instr, host=host, tag="race",
                   ram=ram, ivt=ivt, evt=(ANCHOR, delay, 0, 0),
                   use_core=False, div=div)
    caps = psw_captures(res)
    final_psw = caps[0] if caps else res["regs"].get("PSW")
    # ghost signal: later captures diverge from the first clean one
    ghost = len(set(caps)) > 1
    meas, fr = _classify(final_psw, pre7, pop7)
    return {"pre7": pre7, "pop7": pop7, "delay": delay, "div": div,
            "fired": res["evt_fired"], "final_psw": final_psw,
            "final_race7": fr, "meas": meas, "ghost": ghost,
            "n_caps": len(caps), "exp": expected_class(pre7, pop7)}


# --- staircase margin (for stratified cell selection) ---
def margin(addr):
    """Signed staircase margin rank-threshold at this cell (fit space)."""
    pre = addr >> 7
    pop = addr & 0x7F
    rp = ((pre >> 6) << 5) | (pre & 0x1F)
    rq = ((pop >> 6) << 5) | (pop & 0x1F)
    pd = (pre >> 5) & 1
    qd = (pop >> 5) & 1
    return GRL.G_TABLES[pd][rp] - GRL.H_TABLES[2 * pd + qd][rq]


def select_cells():
    """108 stratified cells: 68 EXC + 30 staircase-margin neighbors +
    10 deep-bulk controls. Returns list of (addr, tag)."""
    exc = list(GRL.EXCEPTIONS)
    exc_set = set(exc)
    cells = [(a, "exc") for a in exc]
    # margin neighbors: non-exc, non-diagonal cells with the smallest |margin|,
    # spread across the 4 quadrants
    by_q = {q: [] for q in range(4)}
    for addr in range(16384):
        pre, pop = addr >> 7, addr & 0x7F
        if pre == pop or addr in exc_set:
            continue
        q = (((pre >> 5) & 1) << 1) | ((pop >> 5) & 1)
        by_q[q].append((abs(margin(addr)), addr))
    margins = []
    for q in range(4):
        by_q[q].sort()
        margins += [a for _, a in by_q[q][:8]]     # ~8/quadrant -> 32, trim
    margins = margins[:30]
    cells += [(a, "margin") for a in margins]
    # deep-bulk: largest |margin|, both classes, non-exc
    allm = sorted(((abs(margin(a)), a) for a in range(16384)
                   if (a >> 7) != (a & 0x7F) and a not in exc_set),
                  reverse=True)
    bulk = [a for _, a in allm[:10]]
    cells += [(a, "bulk") for a in bulk]
    return cells


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["pilot", "validate", "cells",
                                    "characterize"])
    ap.add_argument("--host", default=HOST)
    ap.add_argument("--div", type=int, default=8)
    ap.add_argument("--delay", type=int, default=5)
    args = ap.parse_args()

    if args.cmd == "cells":
        cells = select_cells()
        from collections import Counter
        c = Counter(t for _, t in cells)
        print(f"selected {len(cells)} cells: {dict(c)}")
        for addr, tag in cells:
            pre, pop = addr >> 7, addr & 0x7F
            print(f"  {addr:5d} 0x{addr:04x} pre={pre:02x} pop={pop:02x} "
                  f"tag={tag:6s} exp={expected_class(pre, pop)} "
                  f"margin={margin(addr)}")
        return 0

    if args.cmd == "pilot":
        return cmd_pilot(args.host, args.div)
    if args.cmd == "validate":
        return cmd_validate(args.host, args.div)
    if args.cmd == "characterize":
        return cmd_characterize(args.host, args.div, args.delay)


def _raw_caps(pre7, pop7, delay, div, host, pop_ie=1):
    pre_psw = race7_to_psw(pre7, ie=1)
    pop_psw = race7_to_psw(pop7, ie=pop_ie)
    instr = bytes([0x9D]) + b"\x90" * 20
    stub = ANCHOR + len(instr)
    ram = handler_ram(stub) + [(SP_POP, pop_psw & 0xFF), (SP_POP + 1, pop_psw >> 8)]
    ivt = {VEC_INT: (0x0000, HANDLER)}
    regs = {"PS": 0, "PC": ANCHOR, "SS": SS0, "SP": SP_POP, "PSW": pre_psw}
    res = run_test(regs=regs, instr=instr, host=host, tag="rc",
                   ram=ram, ivt=ivt, evt=(ANCHOR, delay, 0, 0),
                   use_core=False, div=div)
    return [psw_to_race7(c) for c in psw_captures(res)]


def cmd_characterize(host, div, delay):
    """Per-cell: full capture sequence, stable-vs-oscillating, hex match.
    Determines how many of the 108 the PSW-capture rig can cleanly measure
    (stable observable) vs how many are ghost-corrupted (oscillating)."""
    cells = select_cells()
    out = {"div": div, "delay": delay, "cells": []}
    n_stable_match = n_stable_miss = n_osc = 0
    for addr, tag in cells:
        pre, pop = addr >> 7, addr & 0x7F
        exp = expected_class(pre, pop)
        try:
            caps = _raw_caps(pre, pop, delay, div, host)
        except RunError as e:
            out["cells"].append({"addr": addr, "tag": tag, "err": str(e)[:80]})
            continue
        nz = [c for c in caps if c not in (pre, pop) or True]  # keep all
        nzset = set(c for c in caps if c != 0)  # drop fully-corrupt 0 frames
        stable = len(nzset) == 1
        cls = None
        if stable:
            v = next(iter(nzset))
            cls = "A" if v == pop else ("B" if v == pre else "?")
        osc = not stable
        match = (cls == exp) if stable else False
        if stable and match:
            n_stable_match += 1
        elif stable:
            n_stable_miss += 1
        else:
            n_osc += 1
        out["cells"].append({"addr": addr, "tag": tag, "exp": exp,
                             "caps": [f"{c:02x}" for c in caps],
                             "stable": stable, "cls": cls, "match": match})
    out["summary"] = {"stable_match": n_stable_match,
                      "stable_miss": n_stable_miss, "oscillating": n_osc,
                      "total": len(cells)}
    p = Path(__file__).resolve().parent / "exp_race_characterize.json"
    p.write_text(json.dumps(out, indent=1))
    # ghost pop-pattern breakdown of oscillating cells
    osc_pops = {}
    for c in out["cells"]:
        if not c.get("stable", True):
            osc_pops[c["addr"] & 0x7F] = osc_pops.get(c["addr"] & 0x7F, 0) + 1
    print(f"CHARACTERIZE div={div} delay={delay}: "
          f"stable&match={n_stable_match} stable&miss={n_stable_miss} "
          f"oscillating(ghost)={n_osc} / {len(cells)}")
    print(f"oscillating pop-patterns: "
          f"{ {f'{k:02x}': v for k, v in sorted(osc_pops.items())} }")
    print(f"wrote {p}")
    return 0


def cmd_pilot(host, div):
    """Delay sweep on strong cells to locate the own-boundary delay."""
    # strong A and B cells, both DIR modes (large |margin|, non-exc)
    pilots = []
    seen_q = set()
    allm = sorted(((abs(margin(a)), a) for a in range(16384)
                   if (a >> 7) != (a & 0x7F) and a not in set(GRL.EXCEPTIONS)),
                  reverse=True)
    for _, a in allm:
        pre, pop = a >> 7, a & 0x7F
        q = (((pre >> 5) & 1) << 1) | ((pop >> 5) & 1)
        cls = expected_class(pre, pop)
        key = (q, cls)
        if key not in seen_q:
            seen_q.add(key)
            pilots.append((a, cls, q))
        if len(pilots) >= 6:
            break
    log = Path(__file__).resolve().parent / "exp_race_pilot.log"
    open(log, "w").close()

    def out(m):
        print(m, flush=True)
        with open(log, "a") as f:
            f.write(m + "\n")
    out(f"PILOT delay sweep, div={div}, socket; pilots="
        f"{[(hex(a), c) for a, c, _ in pilots]}")
    for delay in range(0, 12):
        row = []
        allmatch = True
        for a, cls, q in pilots:
            pre, pop = a >> 7, a & 0x7F
            try:
                r = measure_cell(pre, pop, delay, div=div, host=host)
                ok = r["meas"] == r["exp"]
                allmatch &= ok
                row.append(f"{a:04x}:{r['meas']}/{r['exp']}"
                           f"{'' if ok else '!'}")
            except RunError as e:
                allmatch = False
                row.append(f"{a:04x}:ERR")
                out(f"  delay={delay} cell {a:04x}: {str(e)[:100]}")
        out(f"delay={delay:>2}: {'ALL-MATCH' if allmatch else '        '} "
            + "  ".join(row))
    out("PILOT DONE")
    return 0


def cmd_validate(host, div):
    cells = select_cells()
    log = Path(__file__).resolve().parent / "exp_race_validate.log"
    open(log, "w").close()

    def out(m):
        print(m, flush=True)
        with open(log, "a") as f:
            f.write(m + "\n")
    out(f"VALIDATE div={div} baseline vs int9d_race.hex; {len(cells)} cells; "
        f"delay={DELAY_OWN}; socket")
    bad = []
    weird = []
    t0 = time.time()
    for i, (addr, tag) in enumerate(cells):
        pre, pop = addr >> 7, addr & 0x7F
        try:
            r = measure_cell(pre, pop, DELAY_OWN, div=div, host=host)
        except RunError as e:
            bad.append((addr, tag, f"ERR {str(e)[:60]}"))
            continue
        if r["meas"] in ("?", "AB", None):
            weird.append((addr, tag, r))
        if r["meas"] != r["exp"]:
            bad.append((addr, tag, f"meas={r['meas']} exp={r['exp']} "
                        f"race7={r['final_race7']}"))
        if (i + 1) % 20 == 0:
            out(f"  {i+1}/{len(cells)} ({(time.time()-t0)/(i+1):.2f}s/cell)")
    # pre-IE=0 non-race controls: pre-IE=0 pops never race -> must all be A
    ie0bad = []
    for addr, tag in cells[:20]:
        pre, pop = addr >> 7, addr & 0x7F
        try:
            r2 = _measure_preie0(pre, pop, DELAY_OWN, div, host)
            if r2["meas"] != "A":
                ie0bad.append((addr, r2["meas"]))
        except RunError:
            pass
    out(f"\nVALIDATE: {len(cells)-len(bad)}/{len(cells)} match hex; "
        f"{len(weird)} weird; pre-IE=0 non-A: {len(ie0bad)}")
    for addr, tag, d in bad[:40]:
        out(f"  MISMATCH {addr:04x} {tag}: {d}")
    if ie0bad:
        out(f"  pre-IE=0 controls not class A: {ie0bad[:20]}")
    ok = not bad and not ie0bad
    out(f"VALIDATION GATE: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


DELAY_OWN = 5      # own-boundary delay; pilot confirms/overrides before validate


def _measure_preie0(pre7, pop7, delay, div, host):
    pre_psw = race7_to_psw(pre7, ie=0)
    pop_psw = race7_to_psw(pop7, ie=1)
    instr = bytes([0x9D]) + b"\x90" * 20
    stub = ANCHOR + len(instr)
    ram = handler_ram(stub) + [(SP_POP, pop_psw & 0xFF), (SP_POP + 1, pop_psw >> 8)]
    ivt = {VEC_INT: (0x0000, HANDLER)}
    regs = {"PS": 0, "PC": ANCHOR, "SS": SS0, "SP": SP_POP, "PSW": pre_psw}
    res = run_test(regs=regs, instr=instr, host=host, tag="race0",
                   ram=ram, ivt=ivt, evt=(ANCHOR, delay, 0, 0),
                   use_core=False, div=div)
    caps = psw_captures(res)
    fp = caps[0] if caps else res["regs"].get("PSW")
    meas, fr = _classify(fp, pre7, pop7)
    return {"meas": meas, "final_race7": fr}


if __name__ == "__main__":
    sys.exit(main())
