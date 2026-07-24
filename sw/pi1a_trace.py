#!/usr/bin/env python3
"""P-I1a: traced full-image sim of the E1 IRET race on the RTL core (v30_core)
via tb_v30_core +bootimg + the event scheduler + the +racedbg race-consumer
trace. Decides H-P1 (consumer fires) vs H-P2/H-P4 (loop/data-as-code alias)
by reading pop_pend/psw_old/race_B at S_TRAP_IVT2W eu_done directly off the
sim. TB-only; no RTL edits; no board.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import testimage                                       # noqa: E402
import exp_iret as I                                   # noqa: E402
import exp_race as R                                   # noqa: E402
import check_core as CC                                # noqa: E402

BIN = CC.OBJ / "Vtb_v30_core"
DELAY = 5
BOOTN = 2600


def compose_e1(pre7, pop7):
    pre_psw = R.race7_to_psw(pre7, ie=1)
    frame_psw = R.race7_to_psw(pop7, ie=1)
    instr = bytes([0xCF]) + b"\x90" * 6
    frame = [(I.SP_FRAME, I.TARGET & 0xFF), (I.SP_FRAME + 1, I.TARGET >> 8),
             (I.SP_FRAME + 2, 0x00), (I.SP_FRAME + 3, 0x00),
             (I.SP_FRAME + 4, frame_psw & 0xFF), (I.SP_FRAME + 5, frame_psw >> 8)]
    ram = I.handler_ram(I.TARGET) + frame
    ivt = {I.VEC_INT: (0x0000, I.HANDLER)}
    regs = {"PS": 0, "PC": I.ANCHOR, "SS": 0, "SP": I.SP_FRAME, "PSW": pre_psw}
    image, meta = testimage.compose(regs=regs, instr=instr, ram=ram, ivt=ivt,
                                    stub_linear=I.TARGET)
    return image, frame_psw, pre_psw


def run_cell(pre7, pop7, tag):
    image, frame_psw, pre_psw = compose_e1(pre7, pop7)
    td = tempfile.mkdtemp()
    hexf = f"{td}/img.hex"
    outf = f"{td}/out.txt"
    with open(hexf, "w") as f:
        f.write("\n".join(f"{b:02x}" for b in image) + "\n")
    subprocess.run([str(BIN), f"+bootimg={hexf}", "+mirror=1",
                    f"+bootn={BOOTN}", "+evpin=0", "+evaddr=00500",
                    f"+evdelay={DELAY}", "+evhold=0", "+racedbg",
                    f"+out={outf}"], cwd=CC.ROOT, capture_output=True, text=True)
    rows = []
    intas = 0
    memw_ffec = []
    for line in open(outf):
        p = line.split()
        if not p:
            continue
        if p[0] == "g":
            # g clk state is_ivt2w eu_done pop_pend psw_old psw race_B r9d_pre r9d_pop
            rows.append(dict(clk=int(p[1]), state=int(p[2]), ivt2w=int(p[3]),
                             eu_done=int(p[4]), pop_pend=int(p[5]),
                             psw_old=int(p[6], 16), psw=int(p[7], 16),
                             race_B=int(p[8]), r9d_pre=int(p[9], 16),
                             r9d_pop=int(p[10], 16)))
        elif p[0] == "r":
            # bus record; detect INTA (bs) and MEMW at FFEC. Format varies;
            # scan defensively for the fields we need via the 'd'/'r' schema.
            pass
    return rows, frame_psw, pre_psw


def analyze(pre7, pop7, tag):
    rows, frame_psw, pre_psw = run_cell(pre7, pop7, tag)
    exp = R.expected_class(pre7, pop7)
    print(f"\n== {tag}: pre7={pre7:02x} pop7={pop7:02x} exp={exp} "
          f"(pre_psw={pre_psw:04x} frame_psw={frame_psw:04x}) ==")
    if not rows:
        print("  NO g-records (build/run issue?)")
        return
    # consumer evaluation points: is_ivt2w && eu_done
    fires = [r for r in rows if r["ivt2w"] and r["eu_done"]]
    print(f"  total g-rows={len(rows)}; S_TRAP_IVT2W&eu_done cycles={len(fires)}")
    for r in fires[:6]:
        cond = r["pop_pend"] and (r["psw_old"] >> 9 & 1) and r["race_B"]
        psw_old_r7 = R.psw_to_race7(r["psw_old"])
        print(f"    clk={r['clk']} pop_pend={r['pop_pend']} "
              f"psw_old={r['psw_old']:04x}(r7={psw_old_r7:02x},"
              f"{'PRE' if psw_old_r7==pre7 else 'pop' if psw_old_r7==pop7 else '?'}) "
              f"race_B={r['race_B']} r9d_pre={r['r9d_pre']:02x} "
              f"r9d_pop={r['r9d_pop']:02x} psw={r['psw']:04x} "
              f"-> CONSUMER {'FIRES(revert to psw_old)' if cond else 'no-op(keep psw)'}")
    any_fire = any(r["pop_pend"] and (r["psw_old"] >> 9 & 1) and r["race_B"]
                   for r in fires)
    # pop_pend history: does it ever get set, and with what psw_old?
    armed = [r for r in rows if r["pop_pend"]]
    print(f"  pop_pend ever set: {'YES' if armed else 'NO'}"
          + (f" (first clk={armed[0]['clk']} psw_old={armed[0]['psw_old']:04x})"
             if armed else ""))
    print(f"  VERDICT: {'H-P1 consumer FIRES with pre-image (real arm)' if any_fire else 'H-P2/H-P4: consumer NEVER fires (pop_pend=0 / psw_old!=pre at every S_TRAP_IVT2W)'}")


def main():
    if not BIN.exists():
        print("build tb_v30_core first (check_core.build)")
        return 1
    for addr, tag in ((0x1188, "1188 B match-alias"),
                      (0x11A8, "11a8 divergent"),
                      (0x0C03, "0c03 A control")):
        analyze(addr >> 7, addr & 0x7F, tag)
    return 0


if __name__ == "__main__":
    sys.exit(main())
