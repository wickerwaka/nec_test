#!/usr/bin/env python3
"""RR4 reproduction: segment-override latch (seg_ovr_en) leaks past instruction
exit paths that reach S_FIRST without retire()/inline-clear. TB-only (+pfxdbg);
no RTL edits; sim only. Two members of the bug class:

  (A) USER'S CASE - CALL near indirect (FF /2 via S_CALLFL->S_CALLPUSH->
      S_CALLW->S_FIRST, no clear): `ES: CALL near [mem]` -> seg_ovr_en STILL 1
      at the successor's decode (latch-level leak).
  (B) EXPLICIT SYMPTOM - MOV reg,imm (B8, S_IMM_HI->S_FIRST, no clear):
      `ES: MOV AX,imm` ; `MOV AX,[mem]` -> the successor's memory read drives
      ES not DS (eu_addr high nibble 0x3 vs 0x2). The DUT drives the full
      20-bit (seg<<4)+off regardless of the RAM mirror.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import testimage
import check_core as CC

BIN = CC.OBJ / "Vtb_v30_core"


def run(instr, ram, stub, bootn=1200):
    regs = {"DS0": 0x2000, "DS1": 0x3000, "PS": 0, "PC": 0x0500,
            "SS": 0x0000, "SP": 0x0400}
    image, _ = testimage.compose(regs=regs, instr=instr, ram=ram,
                                 stub_linear=stub)
    td = tempfile.mkdtemp()
    hexf, outf = f"{td}/i.hex", f"{td}/o.txt"
    open(hexf, "w").write("\n".join(f"{b:02x}" for b in image) + "\n")
    subprocess.run([str(BIN), f"+bootimg={hexf}", "+mirror=1",
                    f"+bootn={bootn}", "+pfxdbg", f"+out={outf}"],
                   cwd=CC.ROOT, capture_output=True, text=True)
    rows = []
    for line in open(outf):
        p = line.split()
        if p and p[0] == "p":
            rows.append(dict(clk=int(p[1]), state=int(p[2]), opc=int(p[3], 16),
                             soe=int(p[4]), so=int(p[5]), eu_seg=int(p[6]),
                             eu_addr=int(p[7], 16), eu_req=int(p[8])))
    return rows


def caseA():
    # ES: CALL near [0x0520]; operand ES:[0x0520]=0x0510 target
    instr = bytes([0x26, 0xFF, 0x16, 0x20, 0x05])
    ram = [(0x0510 + k, b) for k, b in enumerate(bytes([0xA1, 0x30, 0x05]))]
    ram += [(0x0520, 0x10), (0x0521, 0x05), (0x0530, 0xDA), (0x0531, 0xDA)]
    rows = run(instr, ram, 0x0513)
    # CALL is opc ff; find S_FIRST(state 1)/S_DEC(state 2) rows AFTER the CALL's
    # S_CALLW where seg_ovr_en is still set (the leak into the successor)
    call_seen = any(r["opc"] == 0xFF for r in rows)
    leak = [r for r in rows if r["opc"] != 0xFF and r["opc"] != 0x26
            and r["soe"] == 1 and r["state"] in (1, 2)]
    print("CASE A - ES: CALL near indirect (user's case):")
    print(f"  CALL executed: {call_seen}; successor decode rows with "
          f"seg_ovr_en STILL SET: {len(leak)}")
    if leak:
        r = leak[0]
        print(f"  -> LEAK: clk={r['clk']} state={r['state']} "
              f"succ-opc={r['opc']:02x} seg_ovr_en={r['soe']} "
              f"(override survived the CALL retire)")
    return bool(leak)


def caseB():
    # ES: MOV AX,0x1234 ; MOV AX,[0x0530]
    instr = bytes([0x26, 0xB8, 0x34, 0x12])
    ram = [(0x0504 + k, b) for k, b in enumerate(bytes([0xA1, 0x30, 0x05]))]
    ram += [(0x0530, 0xDA), (0x0531, 0xDA)]
    rows = run(instr, ram, 0x0507, bootn=600)
    print("CASE B - ES: MOV reg,imm ; MOV [mem] (explicit symptom):")
    for r in rows:
        if r["opc"] == 0xA1 and (r["eu_addr"] & 0xFFFF) == 0x0530 \
                and r["eu_req"] == 1:
            seg = r["eu_addr"] >> 16
            v = ("LEAK: successor read used ES" if seg == 0x3
                 else "OK: used DS" if seg == 0x2 else f"seg=0x{seg}")
            print(f"  clk={r['clk']} successor MOV [0x0530]: seg_ovr_en="
                  f"{r['soe']} eu_addr={r['eu_addr']:05x} -> {v}")
            return seg == 0x3
    print("  (successor access not found)")
    return False


def main():
    if not BIN.exists():
        print("build tb_v30_core first (check_core.build)"); return 1
    a = caseA()
    b = caseB()
    print(f"\nREPRO: caseA(CALL latch leak)={'CONFIRMED' if a else 'no'}; "
          f"caseB(MOV reg,imm address leak)={'CONFIRMED' if b else 'no'}")
    return 0 if (a and b) else 1


if __name__ == "__main__":
    sys.exit(main())
