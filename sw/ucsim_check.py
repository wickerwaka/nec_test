#!/usr/bin/env python3
"""ucsim_check - the PRODUCTION checker for sim/v30sim (campaign `ucsim`).

Ports sw/check_core.py::check_case's ARCHITECTURAL policy onto the microcode
simulator.  The simulator is driven with `run --emit-final`, which returns, per
case, the 14 final registers, the ordered byte write stream, and the
instruction bytes the decoder consumed; every comparison decision lives here.

Policy, item by item (all of it mirrors sw/check_core.py unless noted):

  registers   SPARSE-DELTA reconstruction of the expected final state:
              `initial.regs` updated by `final.regs`.

  flags       compared under the metadata flags-mask, resolved with
              sw/emit_suite.py::_flags_mask_of semantics -- grouped forms XX.N
              take their mask from opcodes[XX]["reg"][N], NOT from the base
              entry (the old top-level lookup silently masked nothing).
              `--raw-flags` disables all masking.

  RAM         reconstructed from the ordered write stream with check_core's
              FALLBACK semantics: a write is recorded only where it changes the
              running image, and an address absent from a side falls back to
              the initial RAM (so a write-back of the same value is not a
              diff).

  queue       DEFERRED -- the functional model fetches on demand and has no
              prefetch timing, so `final.queue` is not comparable (ledger R5).
              In its place the checker asserts that the bytes the decoder
              CONSUMED are exactly the case's `bytes`, which is the part of the
              queue contract that is architectural.

  don't-care  metadata `dont_care` entries (8F.0 mod3 ghost read) are parsed
              and honoured.  Their coordinates are CYCLE-ROW columns (bus
              address + read data of an architecturally inert read), so they
              never mask an architectural field; the count of cases they cover
              is reported so the entry stays live rather than silently vacuous.

  pin events  cases carrying `evt`/`close_addr` compare ARCHITECTURAL final
              flags derived from the interrupt-pushed PSW in memory
              (check_core::_pushed_psw_flags) on BOTH sides, because the
              recorded final.flags is an unreliable post-handler store-stub
              capture.  A pin event that did NOT fire (SP unchanged, no frame)
              drops flags entirely, exactly as check_core does.

Suite specials:

  --residue stale-ea   tests/v30/mod3_illegal: the LEA mod3 stale-EA residue.
                       The golden's destination register carries the CHIP's
                       pre-window address-latch value, which no injected model
                       can reproduce; the gate is that the divergence is
                       CONFINED to exactly that register (metadata's claim).

  --enter-nesting      tests/v30/enter_nesting: replays MOV BP,imm / ENTER and
                       compares the stack-region walk write stream against the
                       chip digest, using check_enter_nesting._mask_walk's
                       conventions (nesting NOT masked mod 32).

  known_div   `known_divergences.json` is read by CLASS.  VOID = a contaminated
              CAPTURE, excluded from the totals.  EDGE = a known pre-existing
              CYCLE edge recorded as "arch-CLEAN"; this checker compares
              architectural state only, so an EDGE case is KEPT and must pass.

  I/O reads   R3 policy: the port value is REPLAYED, never predicted.  Three
              encodings are honoured -- the case name (`iord=XXXX`), an
              `iords/` sidecar (sw/extract_iords.py), and, for the V20 suite,
              the case's own bus trace (iords_from_cycles).

Usage:
  ucsim_check.py [--suite tests/v30/v0.1] [--forms 88,89,...] [--cases N]
                 [--raw-flags] [--details N] [--report out.json]
                 [--residue stale-ea] [--enter-nesting]
                 [--subset subset.json] [--wrap-scan out.json]
                 [--coverage cov.json] [--coverage-report cov.json]
                 [--alu-hw]
"""

import argparse
import gzip
import json
import re
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
import simbin                                          # noqa: E402

# U1: the C++ model THROUGH THE ARTIFACT/RECEIPT LAYER.  `simbin.SIM` is
# `sim/build/v30sim`, the binary `simbin.recipe()` declares; nothing here
# resolves the model by bare path any more.  See sw/simbin.py.
SIM = simbin.SIM
ROM = ROOT / "docs" / "V20BITS.TXT"
V01 = ROOT / "tests" / "v30" / "v0.1"

REGS = ["ax", "cx", "dx", "bx", "sp", "bp", "si", "di",
        "es", "cs", "ss", "ds", "ip", "flags"]
SS_I, SP_I = REGS.index("ss"), REGS.index("sp")


# --------------------------------------------------------------------------- #
# metadata policy
# --------------------------------------------------------------------------- #
def load_meta(suite: Path):
    """Suite metadata, falling back to v0.1's (wait-state and derived tranches
    carry none of their own) -- same rule as sw/check_core.py."""
    fn = suite / "metadata.json"
    if not fn.exists() or "opcodes" not in json.load(open(fn)):
        fn = V01 / "metadata.json"
    return json.load(open(fn))


def flags_mask_of(op, meta):
    """sw/emit_suite.py::_flags_mask_of, verbatim semantics."""
    base = op.split(".")[0]
    entry = meta["opcodes"].get(op) or meta["opcodes"].get(base, {}) or {}
    if "." in op and "reg" in entry:
        return entry["reg"].get(op.split(".", 1)[1], {}).get("flags-mask", 0xFFFF)
    return entry.get("flags-mask", 0xFFFF)


_WHEN_RE = re.compile(r"^bytes\[(\d+)\]\s*==\s*(0x[0-9A-Fa-f]+|\d+)"
                      r"(?:\s+and\s+\(bytes\[(\d+)\]\s*&\s*(0x[0-9A-Fa-f]+|\d+)\)"
                      r"\s*==\s*(0x[0-9A-Fa-f]+|\d+))?$")


def dont_care_spec(op, meta):
    """The metadata `dont_care` entry for a form, with its `when` predicate
    compiled (a tiny fixed grammar -- never eval()).  Returns (spec, pred) or
    (None, None)."""
    entry = meta["opcodes"].get(op) or {}
    dc = entry.get("dont_care")
    if not dc:
        return None, None
    m = _WHEN_RE.match(dc.get("when", "").strip())
    if not m:
        return dc, None
    i0, v0, i1, msk, v1 = m.groups()

    def pred(b, i0=int(i0), v0=int(v0, 0), i1=i1, msk=msk, v1=v1):
        if len(b) <= i0 or b[i0] != v0:
            return False
        if i1 is None:
            return True
        i1i = int(i1)
        return len(b) > i1i and (b[i1i] & int(msk, 0)) == int(v1, 0)

    return dc, pred


# --------------------------------------------------------------------------- #
# per-case comparison (sw/check_core.py::check_case, architectural half)
# --------------------------------------------------------------------------- #
def pushed_psw_flags(sp, ss, img):
    """check_core::_pushed_psw_flags.  The interrupt frame's PSW word sits at
    SS:(SP+4) once the three pushes have run; IE/BRK are cleared on entry."""
    if sp is None or ss is None:
        return None
    a = ((ss << 4) + ((sp + 4) & 0xFFFF)) & 0xFFFFF
    a1 = ((ss << 4) + ((sp + 5) & 0xFFFF)) & 0xFFFFF
    return ((img.get(a, 0x90) | (img.get(a1, 0x90) << 8)) & ~0x300) & 0xFFFF


def check_case(c, sim, flags_mask, raw_flags=False):
    """-> dict(arch_ok, reg_bad, ram_bad, bytes_ok, notes, ...)"""
    res = {"arch_ok": False, "reg_bad": [], "ram_bad": [], "bytes_ok": True,
           "notes": [], "flags_masked_ok": True}
    if sim is None:
        res["notes"].append("no sim record")
        return res
    if "e" in sim:
        res["notes"].append(sim["e"])
        return res

    exp = dict(c["initial"]["regs"])
    exp.update(c["final"]["regs"])
    got = {k: v for k, v in zip(REGS, sim["r"])}

    # --- RAM: ordered write stream -> {addr: byte}, check_core semantics ----
    init_ram = {a & 0xFFFFF: v for a, v in c["initial"]["ram"]}
    memv = dict(init_ram)
    got_ram = {}
    for a, b in sim["w"]:
        a20 = a & 0xFFFFF
        if memv.get(a20) != b:
            memv[a20] = b
            got_ram[a20] = b
    exp_ram = {a & 0xFFFFF: v for a, v in c["final"]["ram"]}
    ram_bad = sorted(a for a in set(exp_ram) | set(got_ram)
                     if exp_ram.get(a, init_ram.get(a)) !=
                     got_ram.get(a, init_ram.get(a)))

    reg_bad = [k for k in REGS if exp[k] != got[k]]
    mask = 0xFFFF if raw_flags else flags_mask
    flags_ok_masked = (exp["flags"] & mask) == (got["flags"] & mask)
    res["flags_masked_ok"] = ("flags" not in reg_bad) or flags_ok_masked
    if flags_ok_masked:
        reg_bad = [k for k in reg_bad if k != "flags"]

    # --- pin-event forms: architectural flags come out of the pushed frame --
    if c.get("evt") is not None or "close_addr" in c:
        golden_img = dict(init_ram)
        golden_img.update(exp_ram)
        gp = pushed_psw_flags(exp.get("sp"), exp.get("ss"), golden_img)
        sp_ = pushed_psw_flags(got.get("sp"), got.get("ss"), memv)
        init_sp = c["initial"]["regs"]["sp"]
        no_push = (exp.get("sp") == init_sp) and (got.get("sp") == init_sp)
        if gp is not None and sp_ is not None and (gp & 0xF000) == 0xF000:
            reg_bad = [k for k in reg_bad if k != "flags"]
            eq = (gp & mask) == (sp_ & mask)
            if not eq:
                reg_bad.append("flags")
            res["flags_masked_ok"] = eq
            res["pin_pushed_psw"] = (gp, sp_)
        elif no_push:
            reg_bad = [k for k in reg_bad if k != "flags"]
            res["flags_masked_ok"] = True
            res["pin_nofire"] = True

    # --- final QUEUE is deferred; consumed instruction bytes stand in ------
    cb = list(sim.get("b", []))
    if cb:
        res["bytes_ok"] = cb == list(c["bytes"])
    else:
        res["notes"].append("no bytes consumed (event fired at the boundary "
                            "before the anchor)")

    res["reg_bad"] = reg_bad
    res["ram_bad"] = ram_bad
    res["exp"] = exp
    res["got"] = got
    res["arch_ok"] = not reg_bad and not ram_bad and res["bytes_ok"]
    return res


# --------------------------------------------------------------------------- #
# simulator driver
# --------------------------------------------------------------------------- #
COVER = [0] * 1028          # accumulated micro-row execution counters
_COVER_ON = [False]
ALUHW = Counter()           # accumulated --alu-hw-report attribution
_ALUHW_ON = [False]


def _slim(cases):
    """The simulator reads `initial`, `final`, `bytes`, `name` and `iords`.  It
    reads `cycles` only for a pin-event case (derive_replay's REP-abort element
    count), and never reads `hash`.  `cycles` is ~70 % of a v0.3 form's bytes,
    so dropping it off the non-event cases cuts the serialise+parse cost of the
    mass suites by about a third.  Event cases are passed through untouched."""
    out = []
    for c in cases:
        if "evt" in c:
            out.append(c)
        elif "cycles" in c or "hash" in c:
            out.append({k: v for k, v in c.items()
                        if k != "cycles" and k != "hash"})
        else:
            out.append(c)
    return out


def run_sim(cases, mirror=False, wrap_scan=False):
    """-> [record] positionally aligned with `cases`."""
    if not cases:
        return []
    payload = json.dumps(_slim(cases), separators=(",", ":")).encode()
    argv = [str(SIM), "run", str(ROM), "--emit-final"]
    if mirror:
        argv.append("--mirror")
    if wrap_scan:
        argv.append("--wrap-scan")
    if _COVER_ON[0]:
        argv.append("--coverage")
    if _ALUHW_ON[0] and not mirror:
        argv.append("--alu-hw-report")
    p = subprocess.run(argv, input=payload, stdout=subprocess.PIPE)
    out = [None] * len(cases)
    for line in p.stdout.decode().splitlines():
        if not line:
            continue
        r = json.loads(line)
        if "coverage" in r:
            for i, n in enumerate(r["coverage"]):
                COVER[i] += n
            continue
        if r.get("alu_hw_report"):
            for k, v in r.items():
                if k != "alu_hw_report":
                    ALUHW[k] += v
            continue
        i = r["i"]
        if 0 <= i < len(out):
            out[i] = r
    return out


# --------------------------------------------------------------------------- #
# I/O read replay (ledger R3: there is no I/O model -- the value the port
# presented is REPLAYED from the capture, never predicted)
# --------------------------------------------------------------------------- #
IO_READ_W = {0xE4: 1, 0xE5: 2, 0xEC: 1, 0xED: 2, 0x6C: 1, 0x6D: 2}
PREFIX_BYTES = {0x26, 0x2E, 0x36, 0x3E, 0x64, 0x65, 0xF0, 0xF1, 0xF2, 0xF3}


def io_opcode(b):
    for x in b:
        if x not in PREFIX_BYTES:
            return x
    return None


def iords_from_cycles(cases, bus8):
    """The V30 suites carry the port value in the case NAME (`iord=XXXX`) or in
    an `iords` sidecar.  The V20 SingleStepTests suite carries neither: the
    value rides its own bus trace, on the T3 row of each IOR cycle.  Extract it
    into the same per-ELEMENT `iords` list the simulator already consumes.

    The V20 (uPD70108) has an 8-BIT bus, so a word port read is two consecutive
    byte cycles; the simulator's port model is a 16-bit `src` word with a
    parity-selected lane.  Folding is therefore `lo | hi << 8` for a word and
    the byte REPLICATED on both lanes for a byte -- replication is what an 8-bit
    bus physically does (every byte arrives on AD0-7), and it makes the lane
    transform inert.  `mixed` counts elements whose two byte cycles disagreed:
    those are the only cases where the 8-bit/16-bit bus difference could be
    observable, and the caller reports them."""
    mixed = 0
    for c in cases:
        if c.get("iords") or "iord=" in c.get("name", ""):
            continue
        w = IO_READ_W.get(io_opcode(c.get("bytes", [])))
        if not w:
            continue
        # Both trace conventions stop labelling the bus status at T2, so the
        # data column has to be taken off the row that FOLLOWS an IOR cycle at
        # T3 (sw/extract_iords.py's `r[7] == "IOR" and r[8] == "T3"` never
        # matches, which is why that tool falls back to final.ram).
        raw, pend = [], False
        for r in c.get("cycles", ()):
            if len(r) < 9:
                continue
            if r[7] == "IOR":
                pend = True
            elif pend and r[8] == "T3":
                raw.append(int(r[6]) & 0xFFFF)
                pend = False
        if not raw:
            continue
        if not bus8:
            c["iords"] = raw           # 16-bit bus: one word per element
            continue
        if w == 1:
            c["iords"] = [(b & 0xFF) * 0x0101 for b in raw]
        else:
            seq = []
            for i in range(0, len(raw) - 1, 2):
                if (raw[i] & 0xFF) != (raw[i + 1] & 0xFF):
                    mixed += 1
                seq.append((raw[i] & 0xFF) | ((raw[i + 1] & 0xFF) << 8))
            c["iords"] = seq
    return mixed


def load_form(suite: Path, op: str, limit: int = 0, bus8: bool = False):
    cases = json.load(gzip.open(suite / f"{op}.json.gz"))
    side = suite / "iords" / f"{op}.iords.json.gz"
    excluded_amb = []
    if side.exists():
        sc = json.load(gzip.open(side))
        imap = sc.get("iords", {})
        amb = set(sc.get("ambiguous", []))
        for c in cases:
            v = imap.get(str(c["idx"]))
            if v is not None:
                c["iords"] = v
        if amb:
            excluded_amb = sorted(amb)
            cases = [c for c in cases if c["idx"] not in amb]
    if limit:
        cases = cases[:limit]
    if cases and io_opcode(cases[0].get("bytes", [])) in IO_READ_W:
        n = iords_from_cycles(cases, bus8)
        if n:
            print(f"  [{op}] {n} word port read(s) whose two byte cycles "
                  f"DISAGREED -- 8-bit-bus lane order is observable there")
    return cases, excluded_amb


# --------------------------------------------------------------------------- #
# the mod3 stale-EA residue special
# --------------------------------------------------------------------------- #
def stale_ea_confined(c, res):
    """tests/v30/mod3_illegal: LEA reg,rm with mod==3 loads the EU's STALE
    effective-address latch (metadata `finding`).  On silicon that latch holds
    the last EA the pre-window injection stub computed; a from-scratch model has
    no such history, so the destination register cannot transfer.  The gate is
    CONFINEMENT: the divergence must be exactly that one register and nothing
    else."""
    b = c["bytes"]
    if len(b) < 2 or b[0] != 0x8D or (b[1] & 0xC0) != 0xC0:
        return False
    dest = REGS[(b[1] >> 3) & 7]
    return res["reg_bad"] == [dest] and not res["ram_bad"] and res["bytes_ok"]


# --------------------------------------------------------------------------- #
# the ENTER-nesting walk special
# --------------------------------------------------------------------------- #
STK_LO, STK_HI = 0x2000, 0x3FFF
KIND = {"kMemRead": "MEMR", "kMemWrite": "MEMW"}


def enter_nesting(details):
    """Replay `MOV BP,imm16 ; ENTER fsize,nest` and compare the stack-region
    walk stream (kind, addr16, data) against the chip digest, exactly the subset
    sw/check_enter_nesting.py::_mask_walk / char_enter.walk_of compare.  The
    memory image the chip ran on is the NOP-filled test image, so the sim runs
    on 0x90 fill too (the golden's MEMR data is 0x9090)."""
    tr = ROOT / "tests" / "v30" / "enter_nesting"
    tot = Counter()
    fails = []
    for name, key in (("goldens.json.gz", "digest"),
                      ("goldens_waited.json.gz", "full")):
        path = tr / name
        if not path.exists():
            print(f"  {name}: MISSING")
            tot["missing"] += 1
            continue
        goldens = json.load(gzip.open(path, "rt"))
        sub = Counter()
        cases = []
        for g in goldens:
            instr = ([0xBD] + list(int(g["bp"]).to_bytes(2, "little")) +
                     [0xC8] + list(int(g["fsize"]).to_bytes(2, "little")) +
                     [g["nest"]])
            # CS:IP = 0:0x100 with the two instructions in place, SS = 0 (the
            # test image's flat layout), the rest of memory NOP fill.
            ram = [[0x100 + i, b] for i, b in enumerate(instr)]
            ram += [[a, 0x90] for a in range(0x2000, 0x4000)]
            cases.append({
                "idx": len(cases), "name": f"enter n={g['nest']}",
                "bytes": instr,
                "initial": {"regs": {"ax": 0, "cx": 0, "dx": 0, "bx": 0,
                                     "sp": g["sp"], "bp": g["bp"], "si": 0,
                                     "di": 0, "es": 0, "cs": 0, "ss": 0,
                                     "ds": 0, "ip": 0x100, "flags": 0xF002},
                            "queue": [], "ram": ram},
                "final": {"regs": {}, "ram": [], "queue": []}})
        # two instructions per golden: run them as two sim passes over the same
        # image is not possible (one instruction per case), so the walk is taken
        # from the ENTER case whose BP is pre-loaded in `initial.regs`.
        for c in cases:
            c["bytes"] = c["bytes"][3:]
            c["initial"]["regs"]["ip"] = 0x103
        sims = run_sim(cases)
        for g, c, s in zip(goldens, cases, sims):
            got = []
            if s is not None:
                img = dict((a, v) for a, v in c["initial"]["ram"])
                for a, v in s["w"]:
                    got.append(["MEMW", a & 0xFFFF, v])
                    img[a] = v
            # the sim's write stream is BYTE granular; fold it back to the
            # golden's word transactions.
            words, i = [], 0
            while i < len(got):
                if i + 1 < len(got) and got[i + 1][1] == got[i][1] + 1:
                    words.append(["MEMW", got[i][1],
                                  got[i][2] | (got[i + 1][2] << 8)])
                    i += 2
                else:
                    words.append(got[i])
                    i += 1
            got_w = [t for t in words if STK_LO <= t[1] <= STK_HI]
            if key == "digest":
                chip = [[k, a, d] for k, a, d in g["digest"]["txns"]
                        if STK_LO <= a <= STK_HI]
            else:
                chip = [[k, a, d] for k, a, d, _ in g["full"]
                        if k in ("MEMW", "MEMR") and STK_LO <= a <= STK_HI]
            chip_w = [t for t in chip if t[0] == "MEMW"]
            tot["cases"] += 1
            sub["cases"] += 1
            sub["max_push"] = max(sub["max_push"], len(chip_w))
            if got_w == chip_w:
                tot["pass"] += 1
                sub["pass"] += 1
            else:
                tot["fail"] += 1
                if len(fails) < details:
                    fails.append((name, g["ctx"], g["nest"],
                                  len(chip_w), len(got_w)))
        print(f"  {name}: walk-writes {sub['pass']}/{sub['cases']} "
              f"(max stack pushes {sub['max_push']} -- nesting NOT masked "
              f"mod 32: nest=255 => 256)")
    for f in fails:
        print(f"    FAIL {f[0]} ctx{f[1]} nest={f[2]}: "
              f"chip {f[3]} pushes, sim {f[4]}")
    return tot


# --------------------------------------------------------------------------- #
# micro-row coverage report
# --------------------------------------------------------------------------- #
def coverage_report(path: str):
    """Read an accumulated coverage file and name the rows nothing executed.

    `v30sim disasm` prints the ROM in row order with a `------- <pattern>
    <opcodes>` header before each 4-row bank, so the row INDEX in that listing
    is exactly the coverage index (`bank * 4 + row`)."""
    cov = json.load(open(path))["rows"]
    txt = subprocess.run([str(SIM), "disasm", str(ROM)],
                         stdout=subprocess.PIPE).stdout.decode().splitlines()
    banks, cur = [], None
    for ln in txt:
        if ln.startswith("-------"):
            cur = ln[8:].strip()
        elif ln[:4].strip() and cur is not None:
            banks.append((int(ln[:4], 16), cur, ln.rstrip()))
    dead = [(i, b, t) for i, b, t in banks if not cov[i]]
    print(f"micro-row coverage: {sum(1 for n in cov if n)}/{len(cov)} rows "
          f"executed; {len(dead)} never executed")
    last = None
    for i, b, t in dead:
        if b != last:
            print(f"  --- {b}")
            last = b
        print(f"    {t}")
    return 0


# --------------------------------------------------------------------------- #
# the A12 segment-boundary EXTRACTION pass
# --------------------------------------------------------------------------- #
def wrap_scan(suite: Path, forms, args):
    """A12 says word memory accesses wrap the OFFSET at 16 bits inside the
    segment.  `tests/v30/v0.3-f4a-boundary` was never captured (the directory
    holds an emit log and no data), so the boundary exposure has to be EXTRACTED
    from the mass suite instead: run every case with the simulator's boundary
    instrumentation and keep the ones whose DATA accesses land in the last four
    bytes of a segment (0xFFFC..0xFFFF) or actually wrap.  Code-fetch wraps are
    counted separately -- CS:PC rolling over is a different mechanism.

    This pass performs NO comparison: it only writes the subset file, so the
    boundary gate that follows is a first-look verdict, not a re-read of results
    already seen."""
    out = {"_doc": "A12 boundary subset extracted from " + str(suite) +
                   " (v30sim --wrap-scan): cases with a DATA access at "
                   "segment offset >= 0xFFFC or an actual 16-bit offset wrap."}
    code = {}
    tot = wrapped = codew = scanned = 0
    t0 = time.time()
    for op in forms:
        if not (suite / f"{op}.json.gz").exists():
            continue
        cases, _ = load_form(suite, op, args.cases)
        sims = run_sim(cases, wrap_scan=True)
        hit, cw = [], []
        for c, s in zip(cases, sims):
            scanned += 1
            if not s:
                continue
            if s.get("x") or s.get("xw"):
                hit.append(c["idx"])
                wrapped += 1 if s.get("xw") else 0
            if s.get("xc"):
                cw.append(c["idx"])
                codew += 1
        if hit:
            out[op] = hit
            tot += len(hit)
            print(f"  {op}: {len(hit)} boundary case(s)", flush=True)
        if cw:
            code[op] = cw
    print(f"\nA12 boundary subset: {tot} case(s) over {len(out) - 1} form(s) "
          f"of {scanned} scanned; {wrapped} with an ACTUAL offset wrap; "
          f"{codew} case(s) additionally wrap the code fetch pointer "
          f"({time.time() - t0:.1f}s)")
    Path(args.wrap_scan).write_text(json.dumps(out, indent=1))
    print(f"subset -> {args.wrap_scan}")
    if code:
        cp = args.wrap_scan.replace(".json", "") + ".codewrap.json"
        Path(cp).write_text(json.dumps(code, indent=1))
        print(f"code-fetch-wrap subset -> {cp}")
    return 0


# --------------------------------------------------------------------------- #
def main():
    # U1 / P-2.  EAGERLY, before any loop: `ArtifactError` is a
    # `RuntimeError`, and a per-case `except Exception` would turn one
    # sentence naming a stale binary into N unreadable case failures.
    simbin.ensure(why=__name__)
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", default=str(V01))
    ap.add_argument("--forms", default="all",
                    help="comma list, or 'all' (every form file in the suite)")
    ap.add_argument("--cases", type=int, default=0, help="0 = all")
    ap.add_argument("--details", type=int, default=4)
    ap.add_argument("--raw-flags", action="store_true",
                    help="compare the raw PSW on both sides (no masking)")
    ap.add_argument("--report", default="",
                    help="write a JSON report artifact here")
    ap.add_argument("--residue", choices=["stale-ea"], default=None,
                    help="documented-residue policy for a specials tranche")
    ap.add_argument("--enter-nesting", action="store_true",
                    help="the ENTER walk-stream gate (tests/v30/enter_nesting)")
    ap.add_argument("--no-mirror", action="store_true",
                    help="disable the flat-fail -> 64K-mirror retry")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--subset", default="",
                    help="JSON {form: [idx, ...]} -- run only those cases")
    ap.add_argument("--coverage", default="",
                    help="accumulate per-ROM-row execution counters and write "
                         "them here (S4 sufficiency counter)")
    ap.add_argument("--wrap-scan", default="",
                    help="EXTRACTION mode: run the suite with the A12 "
                         "segment-boundary instrumentation and write the "
                         "subset file (no comparison is performed)")
    ap.add_argument("--coverage-report", default="",
                    help="read an accumulated coverage file and list the ROM "
                         "rows nothing has ever executed")
    ap.add_argument("--alu-hw", action="store_true",
                    help="accumulate the --alu-hw-report attribution (how much "
                         "of the final PSW did NOT emerge from the microcode)")
    args = ap.parse_args()
    if args.coverage:
        _COVER_ON[0] = True
    if args.alu_hw:
        _ALUHW_ON[0] = True
    if args.coverage_report:
        return coverage_report(args.coverage_report)

    if args.enter_nesting:
        print("ucsim_check: ENTER nesting walk streams")
        t = enter_nesting(args.details)
        ok = t["fail"] == 0 and not t["missing"]
        print(f"\nTOTAL ENTER walk: {t['pass']}/{t['cases']} "
              f"{'PASS' if ok else 'FAIL'}")
        return 0 if ok else 1

    suite = Path(args.suite)
    if not suite.is_absolute():
        suite = ROOT / suite
    meta = load_meta(suite)
    # The uPD70108 (V20) has an 8-BIT bus: a word port read is two byte
    # cycles.  It changes only how the replayed port value is folded.
    bus8 = str(meta.get("cpu", "")).upper().startswith("V20")

    # known_divergences policy.  The file classifies each documented case:
    #   VOID  a contaminated CAPTURE (ram-vs-instruction physical collision) --
    #         the golden is not a statement about the chip, so it is excluded.
    #   EDGE  a genuine but known pre-existing CYCLE edge, explicitly recorded
    #         as "arch-CLEAN".  This checker only compares ARCHITECTURAL state,
    #         so an EDGE case must still PASS; excluding it would silently drop
    #         a case the ledger says is architecturally sound.  It is kept in
    #         the totals and tracked separately so the claim stays live.
    kd, kd_edge = {}, {}
    kd_fn = suite / "known_divergences.json"
    if kd_fn.exists():
        raw = json.load(open(kd_fn))
        for k, v in raw.items():
            if k.startswith("_"):
                continue
            for i, why in (v.items() if isinstance(v, dict)
                           else ((i, "") for i in v)):
                tgt = kd_edge if str(why).strip().upper().startswith("EDGE") \
                    else kd
                tgt.setdefault(k, set()).add(int(i))
        print(f"[known_divergences] {sum(len(v) for v in kd.values())} VOID "
              f"case(s) excluded; {sum(len(v) for v in kd_edge.values())} "
              f"EDGE case(s) KEPT (cycle-only, arch must pass)")

    subset = None
    if args.subset:
        subset = {k: {int(i) for i in v}
                  for k, v in json.load(open(args.subset)).items()
                  if not k.startswith("_")}
        print(f"[subset] {len(subset)} form(s), "
              f"{sum(len(v) for v in subset.values())} case(s)")

    if args.forms == "all":
        forms = sorted(p.name[:-len(".json.gz")]
                       for p in suite.glob("*.json.gz"))
    else:
        forms = args.forms.split(",")
    if subset is not None:
        forms = [f for f in forms if f in subset]

    if args.wrap_scan:
        return wrap_scan(suite, forms, args)

    grand = Counter()
    per_form = {}
    categories = Counter()
    samples = []
    t0 = time.time()

    for op in forms:
        if not (suite / f"{op}.json.gz").exists():
            print(f"{op}: no suite file")
            continue
        cases, amb = load_form(suite, op, args.cases, bus8)
        if subset is not None:
            keep = subset[op]
            cases = [c for c in cases if c["idx"] in keep]
            if not cases:
                continue
        mask = flags_mask_of(op, meta)
        dc_spec, dc_pred = dont_care_spec(op, meta)
        sims = run_sim(cases)
        excl = kd.get(op, set())
        edge = kd_edge.get(op, set())

        # Empirical mirror validation (check_core's rule, ported): a golden that
        # fails on flat 1 MB but passes under the board's real 64K-MIRRORED RAM
        # is COLLISION-DEPENDENT -- its memory footprint holds two distinct
        # 20-bit addresses aliasing to one 16-bit cell, so it is only meaningful
        # under the model it was captured on.  A real divergence fails under
        # BOTH.  Keeps the gate literal without editing goldens.
        mirror_ok = []
        if not args.no_mirror:
            retry = [(i, c) for i, (c, s) in enumerate(zip(cases, sims))
                     if c["idx"] not in excl and
                     not check_case(c, s, mask,
                                    raw_flags=args.raw_flags)["arch_ok"]]
            if retry:
                msims = run_sim([c for _, c in retry], mirror=True)
                for (i, c), ms in zip(retry, msims):
                    if check_case(c, ms, mask,
                                  raw_flags=args.raw_flags)["arch_ok"]:
                        sims[i] = ms
                        mirror_ok.append(c["idx"])

        cnt = Counter()
        first_div = Counter()
        shown = 0
        for c, s in zip(cases, sims):
            if c["idx"] in excl:
                cnt["excluded"] += 1
                continue
            res = check_case(c, s, mask, raw_flags=args.raw_flags)
            cnt["total"] += 1
            if c["idx"] in edge:
                cnt["edge"] += 1
                cnt["edge_arch_ok"] += 1 if res["arch_ok"] else 0
            if dc_pred and dc_pred(c["bytes"]):
                cnt["dontcare"] += 1
            ok = res["arch_ok"]
            if not ok and args.residue == "stale-ea" and \
                    stale_ea_confined(c, res):
                ok = True
                cnt["residue"] += 1
            if ok:
                cnt["arch"] += 1
                continue
            cnt["fail"] += 1
            if res["notes"]:
                cat = "note:" + res["notes"][0][:40]
            elif not res["bytes_ok"]:
                cat = "bytes"
            elif res["reg_bad"]:
                cat = "regs:" + ",".join(res["reg_bad"])
            else:
                cat = "ram"
            first_div[cat] += 1
            categories[f"{op}|{cat}"] += 1
            if shown < args.details:
                shown += 1
                d = {"form": op, "idx": c["idx"], "name": c["name"],
                     "cat": cat,
                     "regs": {k: [res["exp"][k], res["got"][k]]
                              for k in res.get("reg_bad", [])}
                     if "exp" in res else {},
                     "ram_bad": res["ram_bad"][:8],
                     "notes": res["notes"]}
                if len(samples) < 200:
                    samples.append(d)
                if not args.quiet:
                    print(f"  {op} idx {c['idx']} ({c['name']!r}): {cat}")
                    for k, (e, g) in d["regs"].items():
                        print(f"      {k}: exp {e:04X} got {g:04X}")
                    for a in d["ram_bad"]:
                        print(f"      ram[{a:05X}]")
                    if d["notes"]:
                        print(f"      {d['notes']}")

        line = f"{op}: {cnt['arch']}/{cnt['total']}"
        extra = []
        if cnt["residue"]:
            extra.append(f"{cnt['residue']} documented residue")
        if cnt["excluded"]:
            extra.append(f"{cnt['excluded']} excluded-VOID")
        if cnt["edge"]:
            extra.append(f"{cnt['edge_arch_ok']}/{cnt['edge']} "
                         f"EDGE arch-clean (kept)")
        if cnt["dontcare"]:
            extra.append(f"{cnt['dontcare']} dont-care-covered")
        if mirror_ok:
            extra.append(f"{len(mirror_ok)} collision-dependent "
                         f"(validated on 64K-mirrored RAM, as captured): "
                         f"idx {mirror_ok[:8]}")
            cnt["mirror"] = len(mirror_ok)
        if amb:
            extra.append(f"{len(amb)} ambiguous-iord excluded")
        if extra:
            line += "  (" + ", ".join(extra) + ")"
        if cnt["fail"]:
            line += "  first-div: " + ", ".join(
                f"{k}x{v}" for k, v in first_div.most_common(3))
        if not args.quiet or cnt["fail"]:
            print(line, flush=True)
        per_form[op] = dict(cnt)
        grand.update(cnt)

    dt = time.time() - t0
    print(f"\nTOTAL ARCH: {grand['arch']}/{grand['total']}"
          + (f"  [{grand['excluded']} documented pre-existing excluded]"
             if grand["excluded"] else "")
          + (f"  [{grand['residue']} documented residue]"
             if grand["residue"] else "")
          + (f"  [{grand['mirror']} collision-dependent under 64K mirror]"
             if grand["mirror"] else "")
          + f"  ({dt:.1f}s)")

    if args.report:
        Path(args.report).write_text(json.dumps({
            "suite": str(suite), "raw_flags": bool(args.raw_flags),
            "residue_policy": args.residue,
            "total": grand["total"], "arch": grand["arch"],
            "fail": grand["fail"], "excluded": grand["excluded"],
            "residue": grand["residue"], "mirror": grand["mirror"],
            "seconds": round(dt, 1),
            "per_form": per_form,
            "categories": dict(categories.most_common()),
            "samples": samples}, indent=1))
        print(f"report -> {args.report}")

    if ALUHW:
        n = ALUHW["cases"]
        print("\nALU-hardware flag attribution (the PSW bits the microcode "
              "does NOT determine):")
        print(f"  cases                        {n}")
        print(f"  cases whose FINAL PSW keeps  {ALUHW['cases_any']} "
              f"({100.0 * ALUHW['cases_any'] / max(n, 1):.2f} %) "
              f"a hardware-owned bit")
        for k in ("shift_v", "logic_ac", "bcd"):
            print(f"    {k:10s} commits {ALUHW[k + '_commits']:>10d}  "
                  f"cases {ALUHW[k + '_cases']:>9d}  "
                  f"final bits {ALUHW[k + '_bits']:>9d}")

    if args.coverage:
        # Accumulate into the file if it already holds a run, so the counter is
        # the union over every gate the campaign runs (S4 asks for rows that no
        # green gate ever executed).
        prev = [0] * 1028
        cp = Path(args.coverage)
        if cp.exists():
            prev = json.load(open(cp))["rows"]
        rows = [a + b for a, b in zip(prev, COVER)]
        cp.write_text(json.dumps({
            "_doc": "per-ROM-row micro-instruction execution counts, index = "
                    "bank*4 + row (ucrom::UcRom::op()); accumulated across "
                    "gates",
            "executed": sum(1 for n in rows if n),
            "rows": rows}))
        print(f"coverage: {sum(1 for n in rows if n)}/1028 rows executed "
              f"(cumulative) -> {args.coverage}")

    return 0 if grand["arch"] == grand["total"] else 1


if __name__ == "__main__":
    sys.exit(main())
