#!/usr/bin/env python3
"""ARC 2 H-EXT PROBE: the CODE->MEM -2 cell mechanism.

Architect's H-EXT (denial composition): the chip commits the MEM access at the eval_ext
DIRECT slot (T4+1 fire, delta 1 -> T1 = T4+2); the model's qualification REJECTS it and
the request falls to the plain idle STAGED path (T4+2 fire, delta 2 -> T1 = T4+4). Two
clocks = one lost slot + one delta. ge = -2.

BOARD-ALIGNED RESULT (run_chip + align on the census combos, 29 confirmed ge=-2
CODE->MEMW): the ARITHMETIC is confirmed - MODEL interval CODE-T4->MEMW-T1 = 4 (all),
CHIP interval = 2 (all), fired slot TI_PLAIN (all), eval_ext fires in the completion
window (all). BUT the denying clause is NOT ext_ok (rule A/B) - it is EXT_OK_WR:
  25/29 are RMW writes (eu_defer_wr=1) with ext_ok_wr=0 (eu_ready_p1=1, eu_ready_p2=0).
  4/29 are non-RMW (eu_defer_wr=0, ext_ok=1 ACCEPTS) - a DIFFERENT minority mechanism,
    tagged separately, NOT averaged in.
ext_ok_wr (v30_biu.sv:522) = eu_ready_p1 && eu_ready_p2 (ready ENTERING T4). Under
per-cycle-random waits the write-readiness arrives AT T4 (p1=1, p2=0), so ext_ok_wr
denies and the RMW write is placed 2 clocks late; the chip takes the eval_ext direct.

BRANCH (pre-registered): eu_ready is LIVE at the eval (first-high offset from CODE-T4 =
0, i.e. ready during T4, one cycle BEFORE the T4+1 eval) with leading eu_req -> BRANCH A
(not B, not the trip-wire: the chip does NOT precede eu_ready). The fix direction is a
QUALIFICATION WIDENING of ext_ok_wr to accept ready-AT-T4 (eu_ready_p1 alone) for this
class - the same acceptance ext_ok already gives PLAIN stores.

This module reproduces the GOLDEN PHASE-CLASS (board-free) part: the cell's RMW class is
ABSENT from the w1/w3 goldens (the suite's opcode-89 is a plain store; zero RMW writes).
The w1 golden DOES contain 64 plain-store commits at the SAME ready-AT-T4 phase that pass
via ext_ok accepting -> ready-AT-T4 -> early is CORRECT; only ext_ok_wr's extra rdy_p2
requirement makes RMW writes late.

CAVEAT for the architect (why this is report-and-hold, not auto-build): ext_ok_wr was
FITTED on sweep_rmw.py (ADD word[mem],imm, UNIFORM w0-w5), which measured ready-AT-T4 ->
chip commits LATE (plain idle, rdT1->wrT1=14). The per-cycle-random census measures the
OPPOSITE (ready-AT-T4 RMW -> chip EARLY, eval_ext direct). Same observable (ready AT T4),
opposite chip behaviour by wait regime - EITHER the architect's readiness-phase-class
thesis (uniform never generates the random class; the finer phase must exist) OR a
same-observable wall on RMW. The golden CANNOT adjudicate (no RMW opcodes). A uniform-RMW
re-check (sweep_rmw-style, board) is the missing piece before the widening is safe.
"""
import sys, subprocess, json, gzip
from pathlib import Path
from collections import Counter

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
import check_core as CC
from causal_wrand import accesses

SCR = Path("/tmp/claude-1000/-home-wickerwaka-src-nec-test/"
           "d28f988f-be24-491f-b4b1-5a987e9cc8bb/scratchpad")


def golden_phase(op, suite, waits):
    cases = json.load(gzip.open(f"tests/v30/{suite}/{op}.json.gz"))
    batch = SCR / "hext_batch.txt"; outf = SCR / "hext_out.txt"
    CC.compose_batch(cases, batch)
    subprocess.run([str(CC.BIN), f"+batch={batch}", f"+out={outf}",
                    f"+waits={waits}", "+eudbg"], cwd=CC.ROOT,
                   capture_output=True, text=True)
    co = {}; cur = None; pend = None
    for ln in open(outf):
        p = ln.split()
        if not p:
            continue
        if p[0] == "=":
            cur = []; co[int(p[1])] = cur
        elif p[0] == "d":
            pend = p
        elif p[0] == "r" and cur is not None and pend is not None:
            cur.append(dict(eu_defer_wr=int(pend[74]), ext_ok_wr=int(pend[73]),
                            rdy_p1=int(pend[68]), rdy_p2=int(pend[69]),
                            t=int(p[1]), bs=int(p[2]), qs=int(p[3]),
                            addr=int(p[5], 16)))
            pend = None
    ph = []
    for idx, kr in co.items():
        ka = accesses([dict(t=x["t"], bs_early=x["bs"], qs=x["qs"],
                            ad_addr=x["addr"], ad_data=0) for x in kr])
        for j in range(1, len(ka)):
            if ka[j-1]["bs"] == 4 and ka[j]["bs"] in (5, 6) \
                    and ka[j-1]["t4"] is not None:
                ev = kr[ka[j-1]["t4"] + 1] if ka[j-1]["t4"]+1 < len(kr) \
                    else kr[ka[j-1]["t4"]]
                ph.append((ev["eu_defer_wr"], ev["ext_ok_wr"],
                           ev["rdy_p1"], ev["rdy_p2"]))
    return ph


def main():
    print("=== GOLDEN PHASE-CLASS (board-free): is the cell's RMW class in the golden? ===")
    for suite, w in [("v0.1-w1", 1), ("v0.1-w3", 3)]:
        ph = golden_phase("89", suite, w)
        rmw = sum(1 for p in ph if p[0] == 1)
        readyatT4 = sum(1 for p in ph if p[2] == 1 and p[3] == 0)
        print(f"  {suite} golden-89 CODE->MEM commits {len(ph)}: "
              f"(defer_wr,ext_ok_wr,rdy_p1,rdy_p2) {dict(Counter(ph))}")
        print(f"    RMW writes (defer_wr=1): {rmw} -> cell class "
              f"{'ABSENT' if rmw == 0 else 'PRESENT'}; plain-store ready-AT-T4 "
              f"commits (rdy_p1=1,rdy_p2=0): {readyatT4} (pass via ext_ok accepting "
              f"-> ready-AT-T4 -> early is CORRECT)")
    print("\nBOARD-ALIGNED (documented, needs run_chip): 29 confirmed ge=-2 CODE->MEMW"
          " -> model interval 4 / chip 2 / TI_PLAIN / eval_ext-in-window (all); denial"
          " = ext_ok_wr (25 RMW: defer_wr=1,ext_ok_wr=0,rdy_p1=1,rdy_p2=0; 4 non-RMW"
          " minority tagged out). BRANCH A fired. See module docstring + bringup_log.")


if __name__ == "__main__":
    main()
