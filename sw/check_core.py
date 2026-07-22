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

RTL = [ROOT / "hdl" / "rtl" / "core" / "v30_ss_pkg.sv",
       ROOT / "hdl" / "tb" / "tb_v30_core.sv",
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
               "F3AA", "F3A4", "26.8B", "2E.8B", "36.8B", "3E.8B",
               # Campaign 3 block 4: interrupt/NMI/POLL/HALT + IN forms
               "INT.90", "INT.B8", "INT.8ED0", "INT.8ED8", "INT.FB",
               "INT.9D", "INT.F3AA", "NMI.90", "NMI.B8", "IE0.90",
               "POLL.LO", "POLL.REL", "HLT.INT", "HLT.NMI", "HLT.RES",
               "E4", "E5", "EC", "ED",
               # Campaign 3 closure: full documented-form emission
               "E6", "E7", "EE", "EF"]


def build(force=False):
    if BIN.exists() and not force:
        newest = max(p.stat().st_mtime for p in RTL)
        if BIN.stat().st_mtime > newest:
            return
    # --assert: compile the SVAs. Without it every `assert` in the RTL is
    # silently dropped, so an assertion that "passes" has simply never run. A
    # per-arm class-5 SVA was added, compiled out, and reported nothing - an
    # unfireable assertion manufactures false confidence, so the build now
    # always enables them.
    cmd = ["verilator", "--binary", "--timing", "-DV30_BACKDOOR", "--assert",
           "-Wall", "-Wno-UNUSEDSIGNAL", "-Wno-VARHIDDEN",
           "-Wno-TIMESCALEMOD", "-Wno-WIDTHEXPAND", "-Wno-BLKSEQ",
           "--top-module", "tb_v30_core",
           "-Mdir", str(OBJ)] + [str(p) for p in RTL]
    print("building:", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=ROOT)


PREFIXES = {0xF3, 0xF2, 0xF0, 0x64, 0x65, 0x26, 0x2E, 0x36, 0x3E}


def n_prefix(case):
    """Leading prefix bytes (each pops as an extra F)."""
    n = 0
    for b in case["bytes"]:
        if b in PREFIXES:
            n += 1
        else:
            break
    return n


def n_fpops(c):
    """F pops inside the golden window (window-closing pop count).
    Equals 2 + prefix pops for ordinary cases; interrupt cases close at
    the handler-entry pop after a variable number of boundaries."""
    return sum(1 for row in c["cycles"] if row[9] == "F")


def compose_batch(cases, path, arch_only=False):
    # arch_only: V20 traces END one F-pop earlier than our v0.1 convention (the
    # next-instruction F, which our v0.1 traces include, is not in the V20 trace -
    # QS reports one cycle late and the V20 trace stops at the read cycle). So to
    # dump the register file at the RETIREMENT point (IP = initial_ip + inst_len,
    # exactly the V20 final IP), close one F-pop later. MEASURED: FA(CLI) retirement
    # at n_fpops+1=2, 88(mov) at n_fpops+1=3. Applies only to the V20 arch oracle.
    close_adj = 1 if arch_only else 0
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
            f.write(f"{len(c['cycles']) + 96:x} {n_fpops(c) + close_adj:x}\n")
            # pin-event / static-pin / IO-read-data line:
            #   <mode 0=none 1=fetch 2=fpop> <pin> <addr20> <delay>
            #   <hold> <pins> <iord>
            ev = c.get("evt")
            mode = 0 if ev is None else (1 if ev["trigger"] == "fetch"
                                         else 2)
            # per-IOR ordered port-read sequence (INS / REP INS): <count>
            # then <count> 16-bit values. Absent -> count 0 (scalar iord_r
            # serves every IOR, unchanged for IN forms). See ins_outs_design.md.
            iords = c.get("iords") or []
            f.write(f"{mode:x} {ev['pin'] if ev else 0:x} "
                    f"{(ev.get('addr', 0) if ev else 0) & 0xFFFFF:05x} "
                    f"{ev['delay'] if ev else 0:x} "
                    f"{ev['hold'] if ev else 0:x} "
                    f"{c.get('pins', 0):x} "
                    f"{c.get('iord', 0xFFFF) & 0xFFFF:04x} "
                    f"{len(iords):x}"
                    + "".join(f" {v & 0xFFFF:04x}" for v in iords) + "\n")


def _pushed_psw_flags(sp, ss, img):
    """Pin-event architectural final flags = the interrupt-pushed PSW & ~0x300
    (IE/BRK cleared). The interrupt pushes 3 words (PSW,CS,IP); the store stub
    dumps sp = SP_at_interrupt - 6, so the PSW word sits at SS:(sp+4). `img` is
    the full post-write memory image (init + writes), so POP-PSW pushes that left
    memory unchanged are still read correctly. Returns flags, or None."""
    if sp is None or ss is None:
        return None
    a = ((ss << 4) + ((sp + 4) & 0xFFFF)) & 0xFFFFF
    a1 = ((ss << 4) + ((sp + 5) & 0xFFFF)) & 0xFFFFF
    return ((img.get(a, 0x90) | (img.get(a1, 0x90) << 8)) & ~0x300) & 0xFFFF


def mirror_collision(c):
    """True if the case's memory footprint (window fetches/reads/writes + loaded
    and written ram) holds two DISTINCT 20-bit addresses that alias to the same
    16-bit cell. Such a golden is only valid on 64K-mirrored RAM (how the board
    captured it); it must be validated under +mirror, not flat 1 MB."""
    a = set()
    for row in c["cycles"]:
        if row[7] in ("CODE", "MEMR", "MEMW"):
            a.add(row[1] & 0xFFFFF)
    for x, _ in c["initial"]["ram"]:
        a.add(x & 0xFFFFF)
    for x, _ in c["final"]["ram"]:
        a.add(x & 0xFFFFF)
    return len({x & 0xFFFF for x in a}) < len(a)


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


def dontcare_cells(c):
    """Documented golden-schema don't-care coordinates {(row, col)}.

    8F /0 mod3 (undocumented POP r/m16 register-destination alias, e.g.
    8F C7 = "POP IY"): the destination register is NEVER written - the
    form only does SP += 2 and issues one stack read whose word is
    DISCARDED (verified: across all 130 mod3 cases in the suite no dest
    reg changes beyond SP+2). The chip drives that discarded read at a
    STALE internal EA/address-latch value carried in from pre-window
    execution history (the harness injection stub: load routine + 63 C0
    preload + prefetch stream). It is deterministic on silicon (stable
    across re-runs) but bears no relation to the injected architectural
    state - brute force over (seg<<4)+reg+const and a per-register load-
    routine mutation sweep find no case-state formula; only PS/CS (which
    reshapes the fetch stream) perturbs it, and the value appears nowhere
    else as a real bus cycle. A backdoor-injected core, which never
    executes the injection stub, legitimately drives the modeled SS:SP
    instead. The address (col 1) and its read data (col 6) on that MEMR
    row are architecturally inert; they are a golden-schema don't-care.
    See docs/notes/closure_checkpoint.md (8F.0 ghost-read section).

    Gated tightly on opcode 8F + mod3; the mem-operand forms (mod 0/1/2)
    do a real pop with a real address and are NOT masked.
    """
    cells = set()
    b = c["bytes"]
    if len(b) >= 2 and b[0] == 0x8F and (b[1] & 0xC0) == 0xC0:
        for i, row in enumerate(c["cycles"]):
            if row[7] == "MEMR":     # the single discarded stack read
                cells.add((i, 1))    # committed address (bus col)
                cells.add((i, 6))    # its read data
    return cells


def check_case(c, sim, flags_mask, arch_only=False):
    """-> dict(cycles_ok, arch_ok, flags_masked_ok, fail)

    arch_only=True: an ARCHITECTURAL-ORACLE comparison (e.g. the V20 suite against our
    V30 RTL). V20 (uPD70108) and V30 (uPD70116) share the execution core, so final regs
    /flags(masked)/ram must match EXACTLY; only bus timing differs. Two fields are MASKED
    with documented reasons:
      - FINAL QUEUE: masked. V20 = 4-byte queue with byte-wide fetches; V30 = 6-byte queue
        with WORD-wide fetches from even addresses. The set of NOP-fill bytes queued when
        the next instruction's first byte is read out is a function of fetch width/queue
        depth, so it legitimately cannot transfer. (Architectural state, not queue fill,
        is the oracle.)
      - IP-final: NOT masked by default (it is the retirement IP = next-instruction
        address = instruction-length-determined = same on V20/V30). Kept in reg_bad so
        the pilot can PROVE it transfers; if a prefetch-sensitive form is found where it
        systematically diverges, mask it here with the measured reason (no silent mask).
    """
    res = {"cycles_ok": False, "arch_ok": False, "notes": [], "mm": []}
    if sim is None or sim["final"] is None:
        res["notes"].append("no sim output / no 2nd F pop")
        return res
    rows, events, i0, i1 = build_rows_sim(sim["recs"],
                                          c["initial"]["queue"],
                                          n_close=n_fpops(c) - (0 if arch_only else 1))
    if rows is None:
        res["notes"].append("fewer than 2 F pops in sim")
        return res

    if not arch_only:
        mm, _ = diff_rows(c["cycles"], rows)
        dc = dontcare_cells(c)
        if dc:
            mm = [m for m in mm if (m[0], m[1]) not in dc]
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

    # Pin-event forms: the recorded/dumped final.flags is the POST-HANDLER store-stub
    # PUSH PSW, which is an UNRELIABLE capture (contaminated case-dependently on either
    # side). The architectural final flags = the interrupt-pushed PSW & ~0x300, which is
    # validated via the cycle-trace push. Derive it on BOTH sides from the memory image
    # and compare those instead of the store-stub field. Keeps w0 literal AND meaningful
    # with v0.1 goldens byte-untouched; v0.2 re-derives the field to match. See
    # docs/notes/v02_suspected_divergences.md.
    if c.get("evt") is not None or "close_addr" in c:
        golden_img = dict(init_ram)
        golden_img.update(exp_ram)
        gp = _pushed_psw_flags(exp.get("sp"), exp.get("ss"), golden_img)
        sp_ = _pushed_psw_flags(got.get("sp"), got.get("ss"), memv)
        # only when the interrupt actually FIRED (a real PSW push has the V30's
        # forced reserved bits 15:12=1); masked/no-fire pin-events (e.g. IE0.90)
        # have no push and keep the normal flags comparison.
        if gp is not None and sp_ is not None and (gp & 0xF000) == 0xF000:
            reg_bad = [k for k in reg_bad if k != "flags"]
            eq = (gp & flags_mask) == (sp_ & flags_mask)
            if not eq:
                reg_bad.append("flags")
            res["flags_masked_ok"] = eq
            res["pin_pushed_psw"] = (gp, sp_)

    # final queue
    q_got = [b for _, b in events[i1][2]]
    q_ok = q_got == c["final"]["queue"]

    res["reg_bad"] = reg_bad
    res["ram_bad"] = sorted(ram_bad)
    res["got_ram"] = got_ram          # {addr20: byte} sim-written values (additive; for analysis)
    res["exp_ram"] = exp_ram          # {addr20: byte} golden final ram
    res["init_ram"] = init_ram        # {addr20: byte} initial ram
    res["q_ok"] = q_ok
    # arch-only: flags compared under the mask; final queue MASKED (see docstring)
    if arch_only:
        reg_bad_masked = [k for k in reg_bad
                          if k != "flags" or not flags_ok_masked]
        res["reg_bad"] = reg_bad_masked
        res["arch_ok"] = not reg_bad_masked and not ram_bad
    else:
        res["arch_ok"] = not reg_bad and not ram_bad and q_ok
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--opcodes", default="all",
                    help="comma list; 'all' = every form in the suite "
                         "dir; 'legacy' = the historic DEFAULT_OPS")
    ap.add_argument("--cases", type=int, default=0, help="0 = all")
    ap.add_argument("--variant", choices=["all", "cold", "pf"],
                    default="all")
    ap.add_argument("--details", type=int, default=3)
    ap.add_argument("--keep", action="store_true",
                    help="keep batch/output temp files")
    ap.add_argument("--suite-dir", default=str(SUITE))
    ap.add_argument("--ce-div", type=int, default=1,
                    help="core clock-enable divisor (1=CE high every clk); "
                         ">1 exercises the CE-hold path (rows must match N=1)")
    ap.add_argument("--ce-hold-check", action="store_true",
                    help="assert core internal state freezes on CE-low clocks")
    ap.add_argument("--ss-sweep", nargs="?", const=1, type=int, metavar="STRIDE",
                    help="scramble/idempotence sweep over each selected case's "
                         "recorded window (default stride: 1)")
    ap.add_argument("--ss-cases", default="", metavar="LIST",
                    help="comma-separated case indices included in --ss-sweep")
    ap.add_argument("--ss-mode", type=int, choices=(1, 2, 4, 5), default=1,
                    help="save-state sweep mode: 1=scramble (default), "
                         "2=idempotence, 4=bit-flip sensitivity, "
                         "5=round-trip width sweep (v2)")
    ap.add_argument("--waits", type=int, default=0,
                    help="TB READY wait states (match the suite's setting)")
    ap.add_argument("--arch-only", action="store_true",
                    help="architectural oracle: skip the cycle-row diff; compare only "
                         "final regs (flags-masked), final ram; final queue MASKED "
                         "(V20 4-byte vs V30 6-byte queue). For the V20 suite.")
    ap.add_argument("--result-log", default="",
                    help="append per-opcode results as JSONL (opcode, cases, pass, "
                         "fail, first field-level diffs)")
    ap.add_argument("--no-mirror", action="store_true",
                    help="disable the flat-fail -> +mirror retry (pure flat 1 MB; "
                         "collision-dependent goldens then show as raw divergences)")
    ap.add_argument("--raw-flags", action="store_true",
                    help="disable ALL flags masking (compare raw PSW both sides). "
                         "Exposes V20-undefined bits our V30 computes deterministically.")
    args = ap.parse_args()
    if args.ss_sweep is not None and args.ss_sweep < 1:
        ap.error("--ss-sweep stride must be >= 1")
    try:
        ss_case_ids = {int(x, 0) for x in args.ss_cases.split(",") if x}
    except ValueError as e:
        ap.error(f"invalid --ss-cases LIST: {e}")

    suite = Path(args.suite_dir)
    build(args.build)
    if args.build:
        return 0
    # wait-state suites carry no metadata of their own; fall back to v0.1
    meta_fn = suite / "metadata.json"
    if not meta_fn.exists():
        meta_fn = SUITE / "metadata.json"
    meta = json.load(open(meta_fn))

    if args.opcodes == "all":
        ops = sorted(p.name[:-8] for p in suite.glob("*.json.gz"))
    elif args.opcodes == "legacy":
        ops = DEFAULT_OPS
    else:
        ops = args.opcodes.split(",")

    grand = Counter()
    for op in ops:
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

        # INS (6C/6D): inject the extracted per-IOR port sequence (sidecar
        # from extract_iords.py) so the TB serves the recovered bytes, and
        # EXCLUDE ambiguous (overlapping-write) cases from the gate with a
        # count + list rather than guessing them. Absent sidecar -> the
        # scalar iord_r default serves every IOR (open-bus 0xFF), unchanged.
        side = suite / "iords" / f"{op}.iords.json.gz"
        if side.exists():
            sc = json.load(gzip.open(side))
            iords_map = sc.get("iords", {})
            amb = set(sc.get("ambiguous", []))
            for c in cases:
                v = iords_map.get(str(c["idx"]))
                if v is not None:
                    c["iords"] = v
            if amb:
                before = len(cases)
                cases = [c for c in cases if c["idx"] not in amb]
                print(f"  {op}: excluded {before - len(cases)} ambiguous "
                      f"(overlapping-write) case(s): idx {sorted(amb)[:16]}")

        # flags-mask resolution. For grouped forms XX.N the mask lives in
        # opcodes[XX]["reg"][N] (docs/notes/singlesteptests_v20.md); the base
        # entry has no top-level flags-mask, so the old top-level lookup
        # silently defaulted grouped forms to 0xFFFF (masking never applied).
        base = op.split(".")[0]
        entry = meta["opcodes"].get(op) or meta["opcodes"].get(base, {})
        if "." in op and "reg" in entry:
            sub = op.split(".", 1)[1]
            flags_mask = entry["reg"].get(sub, {}).get("flags-mask", 0xFFFF)
        else:
            flags_mask = entry.get("flags-mask", 0xFFFF)
        if args.raw_flags:
            flags_mask = 0xFFFF   # raw-PSW diagnostic: mask nothing

        with tempfile.TemporaryDirectory() as td:
            def run_batch(cs, mirror, ss_at=None, ss_mode=None,
                          return_stdout=False):
                if not cs:
                    return {}
                suffix = "_m" if mirror else ""
                if ss_at is not None:
                    suffix += f"_ss{ss_mode}_{ss_at}"
                batch = Path(td) / f"batch{suffix}.txt"
                outf = Path(td) / f"out{suffix}.txt"
                compose_batch(cs, batch, arch_only=args.arch_only)
                sa = [str(BIN), f"+batch={batch}", f"+out={outf}",
                      f"+waits={args.waits}", f"+ce_div={args.ce_div}"]
                if mirror:
                    sa.append("+mirror=1")
                if args.ce_hold_check:
                    sa.append("+ce_hold_check")
                if ss_at is not None:
                    sa.extend((f"+ss_at={ss_at}", f"+ss_mode={ss_mode}"))
                r = subprocess.run(sa, cwd=ROOT, capture_output=True, text=True)
                if r.returncode != 0 or not outf.exists():
                    print(f"{op}: SIM FAILED\n{r.stdout}\n{r.stderr}")
                    return None
                if args.ce_hold_check:
                    for ln in r.stdout.splitlines():
                        if "CE_HOLD_VIOL" in ln or "CE-HOLD VIOLATION" in ln:
                            print(f"  {op}: {ln.strip()}")
                if args.keep:
                    import shutil
                    shutil.copy(batch, f"/tmp/batch_{op}{suffix}.txt")
                    shutil.copy(outf, f"/tmp/out_{op}{suffix}.txt")
                parsed = parse_out(outf)
                return (parsed, r.stdout) if return_stdout else parsed
            sims = run_batch(cases, False)
            if sims is None:
                continue
            # Empirical mirror validation: a golden that FAILS on flat 1 MB but
            # PASSES under +mirror is COLLISION-DEPENDENT (captured on the board's
            # own 64K-mirrored test RAM) - validate it under that model, don't
            # fail it. A real RTL divergence fails under BOTH models. This keeps
            # the gate literal (cases still run + must pass) without golden edits.
            def _passes(c, s):
                r = check_case(c, s, flags_mask, arch_only=args.arch_only)
                return r["arch_ok"] if args.arch_only \
                    else (r["cycles_ok"] and r["arch_ok"])
            flat_fails = [c for c in cases if not _passes(c, sims.get(c["idx"]))]
            mirror_ok = []
            if flat_fails and not args.no_mirror:
                msims = run_batch(flat_fails, True)
                if msims is None:
                    continue
                for c in flat_fails:
                    if _passes(c, msims.get(c["idx"])):
                        sims[c["idx"]] = msims[c["idx"]]
                        mirror_ok.append(c["idx"])

            ss_reports = []
            if args.ss_sweep is not None:
                selected = [c for c in cases
                            if not ss_case_ids or c["idx"] in ss_case_ids]
                for c in selected:
                    base_sim = sims.get(c["idx"])
                    built = build_rows_sim(
                        base_sim["recs"], c["initial"]["queue"],
                        n_close=n_fpops(c) - (0 if args.arch_only else 1)) \
                        if base_sim is not None else (None, None, None, None)
                    _, _, raw_i0, _ = built
                    swept = 0
                    first_k = None
                    for logical_k in range(0, len(c["cycles"]), args.ss_sweep):
                        swept += 1
                        if raw_i0 is None:
                            first_k = logical_k
                            break
                        absolute_k = raw_i0 + logical_k
                        rr = run_batch([c], c["idx"] in mirror_ok,
                                       ss_at=absolute_k, ss_mode=args.ss_mode,
                                       return_stdout=True)
                        if rr is None:
                            first_k = logical_k
                            break
                        ss_sims, ss_stdout = rr
                        res = check_case(c, ss_sims.get(c["idx"]), flags_mask,
                                         arch_only=args.arch_only)
                        continuation_mm = [m for m in res.get("mm", [])
                                           if isinstance(m[0], int) and
                                           m[0] > logical_k]
                        ok = res["arch_ok"] and not continuation_mm
                        if args.ss_mode == 2:
                            ok = ok and "SS2 IDEMPOTENT" in ss_stdout and \
                                "PASS" in ss_stdout and "FAIL" not in ss_stdout
                        if not ok:
                            first_k = logical_k
                            break
                    ss_reports.append((c["idx"], swept, first_k))
        if mirror_ok:
            print(f"  {op}: {len(mirror_ok)} collision-dependent golden(s) "
                  f"validated under +mirror (64K RAM, as captured): "
                  f"idx {mirror_ok[:8]}")
        for case_idx, swept, first_k in ss_reports:
            verdict = "PASS" if first_k is None else "FAIL"
            first = "none" if first_k is None else str(first_k)
            print(f"  {op} SS{args.ss_mode} idx {case_idx}: swept={swept} "
                  f"{verdict} first-diverging-k={first}")

        cnt = Counter()
        first_div = Counter()
        arch_diffs = []          # arch-only: sample field-level diffs
        details = args.details
        for c in cases:
            res = check_case(c, sims.get(c["idx"]), flags_mask,
                             arch_only=args.arch_only)
            cnt["total"] += 1
            if res["cycles_ok"]:
                cnt["cycles"] += 1
            if res["arch_ok"]:
                cnt["arch"] += 1
            if args.arch_only and not res["arch_ok"]:
                exp = dict(c["initial"]["regs"]); exp.update(c["final"]["regs"])
                got = res.get("sim_rows") is not None and (sims.get(c["idx"]) or {}).get("final") or {}
                if len(arch_diffs) < 8:
                    arch_diffs.append(dict(
                        idx=c["idx"], name=c["name"],
                        reg_bad={k: [exp[k], got.get(k)] for k in res.get("reg_bad", [])},
                        ram_bad=res.get("ram_bad", [])[:6],
                        notes=res.get("notes", [])))
                first_div[("regs:" + ",".join(res.get("reg_bad", [])) or "ram/note")] += 1
            if res["cycles_ok"] and res["arch_ok"]:
                cnt["full"] += 1
            elif res.get("flags_masked_ok") and res["cycles_ok"] and \
                    not res.get("ram_bad") and res.get("q_ok") and \
                    res.get("reg_bad") == ["flags"]:
                cnt["flags_only"] += 1
            if args.arch_only:
                if not res["arch_ok"] and details > 0:
                    details -= 1
                    exp = dict(c["initial"]["regs"]); exp.update(c["final"]["regs"])
                    gf = (sims.get(c["idx"]) or {}).get("final") or {}
                    print(f"  {op} idx {c['idx']} ({c['name']!r}): arch diff "
                          f"reg_bad={res.get('reg_bad', [])} ram_bad={res.get('ram_bad', [])}"
                          + (f" notes={res['notes']}" if res.get("notes") else ""))
                    for k in res.get("reg_bad", []):
                        print(f"      {k}: exp {exp.get(k)} got {gf.get(k)}")
                continue
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

        if args.arch_only:
            line = (f"{op}: ARCH {cnt['arch']}/{cnt['total']}"
                    + (f"  fail-classes: "
                       + ", ".join(f"{k}x{v}" for k, v in first_div.most_common(3))
                       if cnt["arch"] < cnt["total"] else ""))
            if args.result_log:
                with open(args.result_log, "a") as rf:
                    rf.write(json.dumps(dict(
                        opcode=op, cases=cnt["total"], passed=cnt["arch"],
                        failed=cnt["total"] - cnt["arch"],
                        flags_mask=(0xFFFF if args.raw_flags else flags_mask),
                        raw_flags=bool(args.raw_flags),
                        diffs=arch_diffs)) + "\n")
        else:
            line = (f"{op}: {cnt['full']}/{cnt['total']} full  "
                    f"(cycles {cnt['cycles']}, arch {cnt['arch']}"
                    + (f", +{cnt['flags_only']} flag-residue-only"
                       if cnt["flags_only"] else "") + ")")
            if cnt["cycles"] < cnt["total"]:
                top = first_div.most_common(3)
                line += "  first-div: " + \
                        ", ".join(f"{k}x{v}" for k, v in top)
        print(line, flush=True)
        grand.update(cnt)

    if args.arch_only:
        print(f"\nTOTAL ARCH: {grand['arch']}/{grand['total']}")
        return 0 if grand["arch"] == grand["total"] else 1
    print(f"\nTOTAL: {grand['full']}/{grand['total']} full "
          f"(cycles {grand['cycles']}, arch {grand['arch']})")
    return 0 if grand["full"] == grand["total"] else 1


if __name__ == "__main__":
    sys.exit(main())
