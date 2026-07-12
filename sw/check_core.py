#!/usr/bin/env python3
"""check_core - golden-trace replay checker for the v30_core RTL.

Drives hdl/tb/tb_v30_core.sv (Verilator) with SingleStepTests-format cases
from tests/v30/v0.1 and diffs, per case:

  - the 11-column cycle rows (synthesized from the TB's raw per-cycle
    records with the same logic as the suite emitter, sw/emit_suite.py)
    against the recorded golden rows, cycle by cycle;
  - the final architectural state (registers incl. raw PSW, RAM byte
    diffs reconstructed from the write transactions, queue contents).

Row-compare policy (hardware sampling artifacts):
  cols pins/seg/mem/io/ube/status/tstate/qop/qbyte: compared on every row;
  col1 (bus) and col6 (data): compared on T1/T2/T3/Tw rows and on T4/Ti
  rows that carry a committed next cycle (busstat != PASV). Idle-row
  bus values are float retention of pre-window history on the real chip
  and are not reproducible from an injected start (masked; counted).

Usage:
  check_core.py [--build] [--opcodes B8,40,...] [--cases N] [--variant all]
                [--details N] [--out-dir DIR]
                [--suite-dir tests/v30/v0.1-w1] [--waits N]

--waits N drives the TB's READY wait-state model (+waits plusarg,
mirroring the harness nec_bus insertion); use with a golden suite that
was emitted at the same CFG waits setting (--suite-dir).
"""

import argparse
import gzip
import json
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
SUITE = ROOT / "tests" / "v30" / "v0.1"
TB_DIR = ROOT / "hdl" / "tb"
OBJ = TB_DIR / "obj_dir"
BIN = OBJ / "Vtb_v30_core"

RTL = [ROOT / "hdl" / "tb" / "tb_v30_core.sv",
       ROOT / "hdl" / "rtl" / "core" / "v30_core.sv",
       ROOT / "hdl" / "rtl" / "core" / "v30_biu.sv",
       ROOT / "hdl" / "rtl" / "core" / "v30_eu.sv"]

REGS = ["ax", "cx", "dx", "bx", "sp", "bp", "si", "di",
        "es", "cs", "ss", "ds", "ip", "flags"]

SEG_STR = {0: "ES", 1: "SS", 2: "CS", 3: "DS"}
BUS_STR = {0: "INTA", 1: "IOR", 2: "IOW", 3: "HALT",
           4: "CODE", 5: "MEMR", 6: "MEMW", 7: "PASV"}
T_STR = {0: "Ti", 1: "T1", 2: "T2", 3: "T3", 4: "Tw", 5: "T4"}
Q_STR = {0: "-", 1: "F", 2: "E", 3: "S"}

DEFAULT_OPS = ["B8", "40", "48", "50", "58", "86", "87", "88", "89",
               "8A", "8B", "00", "08", "10", "18", "20", "28", "30", "38",
               "F6.4", "F7.6", "F6.7", "F7.7", "D0.4", "FE.0",
               "0F18", "0F20", "0F28",
               "EB", "E9", "74", "75", "7C", "E2", "E8", "C3", "C2",
               "98", "99", "8C", "8D", "8E", "D7",
               "A0", "A1", "A2", "A3", "A4", "A5", "AA", "AB", "AC", "AD",
               "F3AA", "F3A4", "26.8B", "2E.8B", "36.8B", "3E.8B"]


def build(force=False):
    if BIN.exists() and not force:
        newest = max(p.stat().st_mtime for p in RTL)
        if BIN.stat().st_mtime > newest:
            return
    cmd = ["verilator", "--binary", "--timing", "-DV30_BACKDOOR",
           "-Wall", "-Wno-UNUSEDSIGNAL", "-Wno-VARHIDDEN",
           "--top-module", "tb_v30_core",
           "-Mdir", str(OBJ)] + [str(p) for p in RTL]
    print("building:", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=ROOT)


PREFIXES = {0xF3, 0xF2, 0xF0, 0x26, 0x2E, 0x36, 0x3E}


def n_prefix(case):
    """Leading prefix bytes (each pops as an extra F)."""
    n = 0
    for b in case["bytes"]:
        if b in PREFIXES:
            n += 1
        else:
            break
    return n


def compose_batch(cases, path):
    with open(path, "w") as f:
        f.write(f"{len(cases):x}\n")
        for c in cases:
            r = c["initial"]["regs"]
            q = list(c["initial"]["queue"])
            f.write(f"{c['idx']:x}\n")
            f.write(" ".join(f"{r[k]:04x}" for k in REGS) + "\n")
            qpad = q + [0] * (6 - len(q))
            fetch_ip = (r["ip"] + len(q)) & 0xFFFF
            f.write(f"{len(q):x} " +
                    " ".join(f"{b:02x}" for b in qpad) +
                    f" {fetch_ip:04x}\n")
            ram = c["initial"]["ram"]
            f.write(f"{len(ram):x}\n")
            for a, v in ram:
                f.write(f"{a & 0xFFFFF:05x} {v:02x}\n")
            f.write(f"{len(c['cycles']) + 96:x} {2 + n_prefix(c):x}\n")


def parse_out(path):
    """-> {idx: {'recs': [...], 'final': {...}}}"""
    out = {}
    cur = None
    with open(path) as f:
        for line in f:
            p = line.split()
            if not p:
                continue
            if p[0] == "=":
                cur = {"recs": [], "final": None}
                out[int(p[1])] = cur
            elif p[0] == "r":
                cur["recs"].append({
                    "t": int(p[1]), "bs_early": int(p[2]),
                    "qs": int(p[3]), "ube_n": int(p[4]),
                    "ad_addr": int(p[5], 16), "ad_data": int(p[6], 16),
                    "ps": int(p[7], 16)})
            elif p[0] == "f":
                cur["final"] = {k: int(v, 16) for k, v in zip(REGS, p[1:])}
    return out


def build_rows_sim(recs, init_queue, n_close=1):
    """Shadow-queue reconstruction + 11-column row synthesis over the sim
    records, mirroring sw/emit_suite.build_rows. The shadow queue is
    seeded with the injected initial queue. Returns
    (rows, events, i0, i1) for the window [first F .. F #n_close]
    (prefix bytes pop one extra F each)."""
    queue = [(None, b) for b in init_queue]
    pend = None
    pend_data = None
    events = []
    for r in recs:
        popped = None
        if r["t"] == 1 and r["bs_early"] == 4:
            w = 2 if (r["ad_addr"] & 1) == 0 and not r["ube_n"] else 1
            pend = (w, r["ad_addr"])
            pend_data = None
        if r["t"] in (3, 4) and pend:
            pend_data = r["ad_data"]
        if r["t"] == 5 and pend:
            w, addr = pend
            if pend_data is not None:
                if w == 2:
                    queue.append((addr, pend_data & 0xFF))
                    queue.append((addr + 1, pend_data >> 8))
                else:
                    queue.append((addr, pend_data >> 8 if addr & 1
                                  else pend_data & 0xFF))
            pend = None
        if r["qs"] in (1, 3) and queue:
            popped = queue.pop(0)
        elif r["qs"] == 2:
            queue = []
        events.append((r, popped, list(queue)))

    fpop_is = [i for i, (r, _, _) in enumerate(events) if r["qs"] == 1]
    if len(fpop_is) < n_close + 1:
        return None, events, None, None
    i0, i1 = fpop_is[0], fpop_is[n_close]

    rows = []
    for r, popped, _ in events[i0:i1 + 1]:
        t = r["t"]
        bs = BUS_STR[r["bs_early"]]
        ale = 1 if t == 1 else 0
        bus = r["ad_addr"] if t == 1 else \
            ((r["ps"] << 16) | r["ad_data"]) & 0xFFFFF
        seg = SEG_STR[r["ps"] & 3] if t in (2, 3, 4) and \
            r["bs_early"] != 7 else "--"
        mem = "---"
        io = "---"
        if bs in ("CODE", "MEMR") and t in (2, 3, 4):
            mem = "R--"
        elif bs == "MEMW":
            mem = "-A-" if t == 2 else ("-AW" if t in (3, 4) else "---")
        elif bs == "IOR" and t in (2, 3, 4):
            io = "R--"
        elif bs == "IOW":
            io = "-A-" if t == 2 else ("-AW" if t in (3, 4) else "---")
        rows.append([ale, bus, seg, mem, io, r["ube_n"], r["ad_data"],
                     bs, T_STR[t], Q_STR[r["qs"]],
                     popped[1] if popped else 0])
    return rows, events, i0, i1


def sim_writes(events, i0, i1):
    """MEMW transactions with T1 inside the window -> byte writes."""
    out = []
    cur = None
    for r, _, _ in events[i0:i1 + 1]:
        if r["t"] == 1 and r["bs_early"] == 6:
            cur = {"addr": r["ad_addr"], "ube_n": r["ube_n"], "data": None}
        elif r["t"] in (3, 4) and cur:
            cur["data"] = r["ad_data"]
        elif r["t"] == 5 and cur:
            out.append(cur)
            cur = None
    bytes_out = []
    for t in out:
        a, d = t["addr"], t["data"]
        if a & 1:
            if not t["ube_n"]:
                bytes_out.append((a, d >> 8))
        else:
            bytes_out.append((a, d & 0xFF))
            if not t["ube_n"]:
                bytes_out.append((a + 1, d >> 8))
    return bytes_out


COMPARED_COLS = [0, 2, 3, 4, 5, 7, 8, 9, 10]
COL_NAME = {0: "pins", 1: "bus", 2: "seg", 3: "memcmd", 4: "iocmd",
            5: "ube", 6: "data", 7: "busstat", 8: "tstate", 9: "qop",
            10: "qbyte"}


def diff_rows(exp, got):
    """-> (mismatches [(row, col, exp, got)], masked_count)"""
    mm = []
    masked = 0
    n = min(len(exp), len(got))
    for i in range(n):
        e, g = exp[i], got[i]
        for c in COMPARED_COLS:
            if e[c] != g[c]:
                mm.append((i, c, e[c], g[c]))
        t = e[8]
        full = t in ("T1", "T2", "T3", "Tw") or e[7] != "PASV"
        if full:
            if e[1] != g[1]:
                mm.append((i, 1, e[1], g[1]))
            # col6 compared on T1 rows too (mission F): write cycles drive
            # the write data in T1's second half (modeled in the BIU);
            # read/fetch T1 rows hold the address by retention
            if e[6] != g[6]:
                mm.append((i, 6, e[6], g[6]))
        else:
            masked += 1
    if len(exp) != len(got):
        mm.append((n, "len", len(exp), len(got)))
    return mm, masked


def check_case(c, sim, flags_mask):
    """-> dict(cycles_ok, arch_ok, flags_masked_ok, fail)"""
    res = {"cycles_ok": False, "arch_ok": False, "notes": [], "mm": []}
    if sim is None or sim["final"] is None:
        res["notes"].append("no sim output / no 2nd F pop")
        return res
    rows, events, i0, i1 = build_rows_sim(sim["recs"],
                                          c["initial"]["queue"],
                                          n_close=1 + n_prefix(c))
    if rows is None:
        res["notes"].append("fewer than 2 F pops in sim")
        return res

    mm, _ = diff_rows(c["cycles"], rows)
    res["mm"] = mm
    res["cycles_ok"] = not mm
    res["sim_rows"] = rows

    # final regs
    exp = dict(c["initial"]["regs"])
    exp.update(c["final"]["regs"])
    got = sim["final"]
    reg_bad = [k for k in REGS if exp[k] != got[k]]
    flags_ok_masked = (exp["flags"] & flags_mask) == \
                      (got["flags"] & flags_mask)
    res["flags_masked_ok"] = ("flags" not in reg_bad) or (
        flags_ok_masked and
        all(k == "flags" for k in reg_bad))

    # final ram from write transactions
    init_ram = {a & 0xFFFFF: v for a, v in c["initial"]["ram"]}
    memv = dict(init_ram)
    got_ram = {}
    for a, b in sim_writes(events, i0, i1):
        a20 = a & 0xFFFFF
        if memv.get(a20) != b:
            memv[a20] = b
            got_ram[a20] = b
    exp_ram = {a & 0xFFFFF: v for a, v in c["final"]["ram"]}
    ram_bad = {a for a in set(exp_ram) | set(got_ram)
               if exp_ram.get(a, init_ram.get(a)) !=
                  got_ram.get(a, init_ram.get(a))}

    # final queue
    q_got = [b for _, b in events[i1][2]]
    q_ok = q_got == c["final"]["queue"]

    res["reg_bad"] = reg_bad
    res["ram_bad"] = sorted(ram_bad)
    res["q_ok"] = q_ok
    res["arch_ok"] = not reg_bad and not ram_bad and q_ok
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--opcodes", default=",".join(DEFAULT_OPS))
    ap.add_argument("--cases", type=int, default=0, help="0 = all")
    ap.add_argument("--variant", choices=["all", "cold", "pf"],
                    default="all")
    ap.add_argument("--details", type=int, default=3)
    ap.add_argument("--keep", action="store_true",
                    help="keep batch/output temp files")
    ap.add_argument("--suite-dir", default=str(SUITE))
    ap.add_argument("--waits", type=int, default=0,
                    help="TB READY wait states (match the suite's setting)")
    args = ap.parse_args()

    suite = Path(args.suite_dir)
    build(args.build)
    # wait-state suites carry no metadata of their own; fall back to v0.1
    meta_fn = suite / "metadata.json"
    if not meta_fn.exists():
        meta_fn = SUITE / "metadata.json"
    meta = json.load(open(meta_fn))

    grand = Counter()
    for op in args.opcodes.split(","):
        fn = suite / f"{op}.json.gz"
        if not fn.exists():
            print(f"{op}: no suite file")
            continue
        cases = json.load(gzip.open(fn))
        if args.variant == "cold":
            cases = [c for c in cases if c["idx"] % 2 == 0]
        elif args.variant == "pf":
            cases = [c for c in cases if c["idx"] % 2 == 1]
        if args.cases:
            cases = cases[:args.cases]

        mkey = op if op in meta["opcodes"] else op.split(".")[0]
        flags_mask = meta["opcodes"].get(mkey, {}).get("flags-mask", 0xFFFF)

        with tempfile.TemporaryDirectory() as td:
            batch = Path(td) / "batch.txt"
            outf = Path(td) / "out.txt"
            compose_batch(cases, batch)
            r = subprocess.run([str(BIN), f"+batch={batch}",
                                f"+out={outf}", f"+waits={args.waits}"],
                               cwd=ROOT, capture_output=True, text=True)
            if r.returncode != 0 or not outf.exists():
                print(f"{op}: SIM FAILED\n{r.stdout}\n{r.stderr}")
                continue
            sims = parse_out(outf)
            if args.keep:
                import shutil
                shutil.copy(batch, f"/tmp/batch_{op}.txt")
                shutil.copy(outf, f"/tmp/out_{op}.txt")

        cnt = Counter()
        first_div = Counter()
        details = args.details
        for c in cases:
            res = check_case(c, sims.get(c["idx"]), flags_mask)
            cnt["total"] += 1
            if res["cycles_ok"]:
                cnt["cycles"] += 1
            if res["arch_ok"]:
                cnt["arch"] += 1
            if res["cycles_ok"] and res["arch_ok"]:
                cnt["full"] += 1
            elif res.get("flags_masked_ok") and res["cycles_ok"] and \
                    not res.get("ram_bad") and res.get("q_ok") and \
                    res.get("reg_bad") == ["flags"]:
                cnt["flags_only"] += 1
            if not res["cycles_ok"]:
                if res["mm"]:
                    i, col, e, g = res["mm"][0]
                    first_div[(i, COL_NAME.get(col, col))] += 1
                else:
                    first_div[tuple(res["notes"])] += 1
                if details > 0:
                    details -= 1
                    print(f"  {op} idx {c['idx']} ({c['name']!r}):")
                    for m in res["mm"][:6]:
                        i, col, e, g = m
                        print(f"    row {i} {COL_NAME.get(col, col)}: "
                              f"exp {e!r} got {g!r}")
                    if not res["mm"]:
                        print(f"    {res['notes']}")
            elif not res["arch_ok"] and details > 0:
                details -= 1
                print(f"  {op} idx {c['idx']} ({c['name']!r}): arch diff "
                      f"regs={res['reg_bad']} ram={res['ram_bad']} "
                      f"q_ok={res['q_ok']}")
                for k in res["reg_bad"]:
                    exp = dict(c["initial"]["regs"])
                    exp.update(c["final"]["regs"])
                    print(f"      {k}: exp {exp[k]:04x} got "
                          f"{sims[c['idx']]['final'][k]:04x}")

        line = (f"{op}: {cnt['full']}/{cnt['total']} full  "
                f"(cycles {cnt['cycles']}, arch {cnt['arch']}"
                + (f", +{cnt['flags_only']} flag-residue-only"
                   if cnt["flags_only"] else "") + ")")
        if cnt["cycles"] < cnt["total"]:
            top = first_div.most_common(3)
            line += "  first-div: " + \
                    ", ".join(f"{k}x{v}" for k, v in top)
        print(line)
        grand.update(cnt)

    print(f"\nTOTAL: {grand['full']}/{grand['total']} full "
          f"(cycles {grand['cycles']}, arch {grand['arch']})")
    return 0 if grand["full"] == grand["total"] else 1


if __name__ == "__main__":
    sys.exit(main())
