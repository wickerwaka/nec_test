#!/usr/bin/env python3
"""exp_flush - measure the chip's flush-point vs (branch type x wait level).

Front-2 (flush/branch) measure-first. Reflash-free, chip position. For each
taken branch type, a saturated-queue runway + the branch + a target region;
capture at w0/w1/w3 and locate the flush (QS=E) and the redirect T1 relative to
the branch's last operand pop, to pin exactly how the flush point stretches
under waits per branch type (Jcc is +1 late, EB was on-time in the blanket
attempt - confirm per type).
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from v30asm import Assembler                     # noqa: E402
from v30run import run_test                      # noqa: E402

T = {0: "Ti", 1: "T1", 2: "T2", 3: "T3", 4: "Tw", 5: "T4"}
QN = {0: "-", 1: "F", 2: "E", 3: "S"}
BS = {4: "CO", 5: "MR", 6: "MW", 2: "IW", 1: "IR", 0: "IN", 3: "HL", 7: "--"}


def branch_prog(a, kind, org=0x0500):
    """Return (code, regs, target_lin) for a taken branch of `kind`."""
    regs = {"PS": 0, "PC": org}
    runway = "    NOP\n" * 16
    gap = "    NOP\n" * 0x30       # target ~0x30 ahead (distinct from 0x500)
    tail = "    NOP\n" * 10
    if kind == "EB":                 # br short (unconditional)
        body = "    BR t\n" + gap + "t:\n"
    elif kind == "E9":               # near jmp (raw: E9 disp16)
        disp = 0x30
        code = a.assemble(runway, org=org) + \
            bytes([0xE9, disp & 0xFF, (disp >> 8) & 0xFF]) + \
            a.assemble(gap + tail, org=org)
        return code, regs
    elif kind == "Jcc":              # JNC taken (CY=0)
        regs["PSW"] = 0xF002
        body = "    BNC t\n" + gap + "t:\n"
    elif kind == "LOOP":             # DBNZ taken (CW=2 -> branch)
        regs["CW"] = 2
        body = "    DBNZ t\n" + gap + "t:\n"
    elif kind == "CALL":             # near call
        regs["SP"] = 0x2000
        regs["SS"] = 0
        body = "    CALL t\n" + gap + "t:\n"
    else:
        raise ValueError(kind)
    src = runway + body + tail
    code = a.assemble(src, org=org)
    return code, regs


def analyze(recs, kind, w):
    # find the branch's flush E: the one whose redirect T1 lands in my code
    # region (0x00500-0x00560), not the boot/reset flush (-> ffff0).
    def redirect_to_code(ei):
        for i in range(ei, min(ei + 12, len(recs))):
            if recs[i]["t"] == 1 and recs[i]["bs_early"] == 4:
                # branch target region (~0x0540..0x0560), NOT the 0x0500 start
                return 0x00538 <= (recs[i]["ad_addr"] & 0xFFFFF) <= 0x00560
        return False
    es = [i for i, r in enumerate(recs) if r["qs"] == 2 and redirect_to_code(i)]
    if not es:
        print(f"  {kind} w{w}: no branch flush E found")
        return
    e = es[0]
    # redirect T1 = first CODE T1 after e
    rt = next((i for i in range(e, len(recs)) if recs[i]["t"] == 1
               and recs[i]["bs_early"] == 4), None)
    # last bus T4 before e
    t4 = next((i for i in range(e, 0, -1) if recs[i]["t"] == 5), None)
    tgt = recs[rt]["ad_addr"] if rt else 0
    # count Tw cycles in the [t4, rt] window (how waited the resolution was)
    print(f"  {kind:5} w{w}: E@{e} T1@{rt}->{tgt:05x} | E->T1={rt-e if rt else '?'} "
          f"T4->E={e-t4 if t4 else '?'}")
    for i in range(e - 5, (rt or e) + 3):
        r = recs[i]
        mk = " <E" if i == e else " <T1" if i == rt else ""
        print(f"      {i} {T.get(r['t']):<2} {BS.get(r['bs_early'],'?')} "
              f"{r['ad_addr']:05x} {QN[r['qs']]}{mk}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="root@mister-nec")
    ap.add_argument("--kinds", default="EB,E9,Jcc,LOOP,CALL")
    ap.add_argument("--waits", default="0,1,3")
    args = ap.parse_args()
    a = Assembler()
    for kind in args.kinds.split(","):
        print(f"=== {kind} ===")
        for w in [int(x) for x in args.waits.split(",")]:
            try:
                code, regs = branch_prog(a, kind)
            except Exception as ex:
                print(f"  {kind}: asm fail {ex}"); break
            res = run_test(regs=regs, instr=code, host=args.host,
                           tag="flush", waits=w)
            analyze(res["recs"], kind, w)
    return 0


if __name__ == "__main__":
    sys.exit(main())
