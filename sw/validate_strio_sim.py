#!/usr/bin/env python3
"""validate_strio_sim - RTL-TB sim validation for the 6C-6F string-I/O generator.

Board-free gate the coordinator requires before any INS/OUTS board capture:
generate cases with emit_suite.gen_case, run each through hdl/tb/tb_v30_core.sv
(the same Verilator TB check_core drives, which already serves the per-element
iords sequence), and confirm each case EXERCISES CLEANLY -- it retires (dumps a
final register state) and the trace is plausible:

  * REP forms terminate with CW == 0
  * IX (OUTS) / IY (INS) advanced by sign(DF) * width * count
  * the number of IO bus cycles (IOR for INS, IOW for OUTS) equals the count
  * for INS, the served port bytes land at ES:IY (reconstructed from MEMW rows)

No golden is compared (there is none yet); this validates the GENERATOR, not a
suite. Usage: validate_strio_sim.py [--per N] [--opcodes 6C,6D,...]
"""
import argparse
import random
import subprocess
import sys
import tempfile
from pathlib import Path

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
import emit_suite as E                        # noqa: E402
import check_core as C                        # noqa: E402

BUS = {v: k for k, v in C.BUS_STR.items()}    # name -> code
IOR, IOW = BUS["IOR"], BUS["IOW"]


def write_batch(cases, path):
    """TB batch grammar (see tb_v30_core.sv), built from raw generated cases.
    initial.ram = generated ram + instruction bytes at CS:IP; the TB fills all
    other memory with 0x90 (NOP) so the case retires without a captured fetch
    footprint. Window closes at 2 + prefix-pops F-pops."""
    with open(path, "w") as f:
        f.write(f"{len(cases):x}\n")
        for k, c in enumerate(cases):
            r = c["regs"]
            anchor = ((r["cs"] << 4) + r["ip"]) & 0xFFFFF
            ram = list(c["ram"]) + [((anchor + i) & 0xFFFFF, b)
                                    for i, b in enumerate(c["instr"])]
            # only leading prefixes count as extra F-pops
            npfx = 0
            for b in c["instr"]:
                if b in C.PREFIXES:
                    npfx += 1
                else:
                    break
            nf = 2 + npfx
            f.write(f"{k:x}\n")
            # REGS is the full 14 (ax..ds, ip, flags) on one line, as compose_batch
            f.write(" ".join(f"{r[g]:04x}" for g in C.REGS) + "\n")
            f.write(f"0 0 0 0 0 0 0 {r['ip']:04x}\n")      # empty queue
            f.write(f"{len(ram):x}\n")
            for a, v in ram:
                f.write(f"{a & 0xFFFFF:05x} {v & 0xFF:02x}\n")
            f.write(f"{600:x} {nf:x}\n")                    # generous cap
            iords = c.get("iords") or []
            f.write(f"0 0 0 0 0 0 ffff {len(iords):x}"
                    + "".join(f" {v & 0xFFFF:04x}" for v in iords) + "\n")
    return


def io_cycles(recs, code):
    """count IO bus cycles of the given status (one per T1 address phase)."""
    return sum(1 for x in recs if x["t"] == 1 and x["bs_early"] == code)


def sim_writes(recs):
    """{addr20: byte} from MEMW rows (address at T1, data at T2, UBE+parity)."""
    w = {}
    n = len(recs)
    for i, x in enumerate(recs):
        if not (x["bs_early"] == BUS["MEMW"] and x["t"] == 1):
            continue
        addr = x["ad_addr"] & 0xFFFFF
        ube = x["ube_n"]
        data = None
        for j in range(i + 1, min(i + 4, n)):
            if recs[j]["t"] == 2:
                data = recs[j]["ad_data"]
                break
        if data is None:
            continue
        if (addr & 1) == 0 and not ube:
            w[addr] = data & 0xFF
            w[(addr + 1) & 0xFFFFF] = (data >> 8) & 0xFF
        elif (addr & 1) == 0:
            w[addr] = data & 0xFF
        else:
            w[addr] = (data >> 8) & 0xFF
    return w


def check(op, c, out):
    """-> (ok, note). out = parse_out entry for this case."""
    if out is None or out.get("final") is None:
        return False, "no retirement (no final dumped)"
    spec = E.OPCODES[op]
    r = c["regs"]
    fin = out["final"]
    nb = 2 if spec["w"] else 1
    df = (r["flags"] >> 10) & 1
    cnt = (r["cx"] & 0xFFFF) if spec["rep"] else 1
    sign = -1 if df else 1
    # REP terminates CW == 0
    if spec["rep"] and (fin["cx"] & 0xFFFF) != 0:
        return False, f"rep did not drain CW: final cx={fin['cx']:04x}"
    # pointer advance
    ptr = "si" if spec["strio"] == "outs" else "di"
    want = (r[ptr] + sign * nb * cnt) & 0xFFFF
    if (fin[ptr] & 0xFFFF) != want:
        return False, (f"{ptr} advance wrong: {r[ptr]:04x} -> {fin[ptr]:04x} "
                       f"(want {want:04x}; nb={nb} cnt={cnt} df={df})")
    # IO cycle count
    code = IOR if spec["strio"] == "ins" else IOW
    nio = io_cycles(out["recs"], code)
    if nio != cnt:
        return False, (f"{'IOR' if code == IOR else 'IOW'} cycles={nio}, "
                       f"expected {cnt}")
    # INS: served bytes land at ES:IY (walk the sequence)
    if spec["strio"] == "ins" and cnt:
        w = sim_writes(out["recs"])
        for i in range(cnt):
            step = -i * nb if df else i * nb
            do = (r["di"] + step) & 0xFFFF
            base = ((r["es"] << 4) + do) & 0xFFFFF
            served = c["iords"][i]
            for kk in range(nb):
                got = w.get((base + kk) & 0xFFFFF)
                exp = (served >> (8 * kk)) & 0xFF
                if got != exp:
                    return False, (f"INS elem {i} byte {kk} at {base+kk:05x}: "
                                   f"wrote {got}, served {exp:02x}")
    return True, ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per", type=int, default=40)
    ap.add_argument("--opcodes", default=",".join(sorted(E.STRIO_OPS)))
    args = ap.parse_args()
    C.build()
    ops = args.opcodes.split(",")
    total = fails = 0
    fail_ex = []
    for op in ops:
        spec = E.OPCODES[op]
        rng = random.Random(f"strio-sim/{op}")
        cases = [E.gen_case(spec, rng) for _ in range(args.per)]
        with tempfile.TemporaryDirectory() as td:
            bp, opth = Path(td) / "b.txt", Path(td) / "o.txt"
            write_batch(cases, bp)
            subprocess.run([str(C.BIN), f"+batch={bp}", f"+out={opth}"],
                           cwd=C.ROOT, capture_output=True, text=True,
                           timeout=300)
            res = C.parse_out(opth)
        opok = opfail = 0
        for k, c in enumerate(cases):
            ok, note = check(op, c, res.get(k))
            total += 1
            if ok:
                opok += 1
            else:
                opfail += 1
                fails += 1
                if len(fail_ex) < 20:
                    fail_ex.append(f"{op} #{k}: {note} | {c['name'][:50]}")
        print(f"  {op:6}: {opok}/{opok + opfail} clean", flush=True)
    print(f"\nstrio sim validation: {total - fails}/{total} clean "
          f"across {len(ops)} forms")
    for e in fail_ex:
        print("  FAIL", e)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
