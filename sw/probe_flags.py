#!/usr/bin/env python3
"""probe_flags - Campaign 2 mission 8: what do the documented-U flags do?

For each instruction class with U entries in its instructions.json flag row,
run several operand patterns (the first two at two initial PSW values) and
classify each undefined flag: preserved / constant / standard S-Z-P function
of some result register / operand-dependent (samples listed).

Robustness contract (lesson from a wedged predecessor): every hardware case
is wrapped in try/except with one retry then skip-and-log; every run is
appended to sw/testdata/flags_log.jsonl as it happens; all prints flush.

Output feeds docs/facts/undefined_flags.md.

Usage: probe_flags.py all [--host ...] [--only SUBSTR]
       probe_flags.py list
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from v30asm import Assembler                          # noqa: E402
from v30run import run_test                           # noqa: E402

LOG = Path(__file__).resolve().parent / "testdata" / "flags_log.jsonl"
REPORT = Path(__file__).resolve().parent / "testdata" / "flags_report.json"

FLAG_BITS = {"CY": 0x01, "P": 0x04, "AC": 0x10, "Z": 0x40, "S": 0x80,
             "V": 0x800}
PSW_IN = (0x0000, 0x0ED5)      # writable-clear / writable-set (no TF)

# Each case: (name, code, uflags, patterns[, ram])
#   code: asm string or raw bytes (for forms the assembler can't emit)
#   patterns: register overrides; first two patterns run at both PSW values
#   ram: list of (addr, byte) placed in the image (string/bitfield operands)
CASES = [
    # --- multiply / divide (U = S,Z,AC,P; div adds V,CY) ---
    ("MULU reg8", "MULU CL", ["S", "Z", "AC", "P"],
     [{"AW": 0x0000, "CW": 0x00}, {"AW": 0x00FF, "CW": 0xFF},
      {"AW": 0x0007, "CW": 0x05}, {"AW": 0x0080, "CW": 0x02},
      {"AW": 0x0010, "CW": 0x10}]),
    ("MULU reg16", "MULU CW", ["S", "Z", "AC", "P"],
     [{"AW": 0x0000, "CW": 0x0000}, {"AW": 0xFFFF, "CW": 0xFFFF},
      {"AW": 0x0007, "CW": 0x0005}, {"AW": 0x8000, "CW": 0x0002},
      {"AW": 0x0100, "CW": 0x0100}]),
    ("MUL reg8", "MUL CL", ["S", "Z", "AC", "P"],
     [{"AW": 0x0000, "CW": 0x00}, {"AW": 0x00FF, "CW": 0xFF},
      {"AW": 0x007F, "CW": 0x7F}, {"AW": 0x0080, "CW": 0x7F},
      {"AW": 0x00FF, "CW": 0x01}]),
    ("MUL reg16", "MUL CW", ["S", "Z", "AC", "P"],
     [{"AW": 0x0000, "CW": 0x0000}, {"AW": 0xFFFF, "CW": 0xFFFF},
      {"AW": 0x7FFF, "CW": 0x7FFF}, {"AW": 0x8000, "CW": 0x7FFF},
      {"AW": 0xFFFF, "CW": 0x0001}]),
    ("MUL reg16,reg16,imm8", "MUL CW, DW, 5", ["S", "Z", "AC", "P"],
     [{"DW": 0x0000}, {"DW": 0xFFFF}, {"DW": 0x0007}, {"DW": 0x2000},
      {"DW": 0x8000}]),
    ("MUL reg16,reg16,imm16", "MUL CW, DW, 0x300", ["S", "Z", "AC", "P"],
     [{"DW": 0x0000}, {"DW": 0x00FF}, {"DW": 0xFFFF}, {"DW": 0x5555}]),
    ("DIVU reg8", "DIVU CL", ["V", "S", "Z", "AC", "P", "CY"],
     [{"AW": 0x0009, "CW": 0x03}, {"AW": 0x0100, "CW": 0x03},
      {"AW": 0xFE01, "CW": 0xFF}, {"AW": 0x0007, "CW": 0x02},
      {"AW": 0x0000, "CW": 0x01}]),
    ("DIVU reg16", "DIVU CW", ["V", "S", "Z", "AC", "P", "CY"],
     [{"AW": 0x0009, "DW": 0, "CW": 0x0003},
      {"AW": 0x0000, "DW": 1, "CW": 0x0003},
      {"AW": 0xFFFF, "DW": 0, "CW": 0x0001},
      {"AW": 0x0007, "DW": 0, "CW": 0x0002}]),
    ("DIV reg8", "DIV CL", ["V", "S", "Z", "AC", "P", "CY"],
     [{"AW": 0x0009, "CW": 0x03}, {"AW": 0xFFF7, "CW": 0x03},
      {"AW": 0xFFF7, "CW": 0xFD}, {"AW": 0x0007, "CW": 0xFE},
      {"AW": 0x0000, "CW": 0x01}]),
    ("DIV reg16", "DIV CW", ["V", "S", "Z", "AC", "P", "CY"],
     [{"AW": 0x0009, "DW": 0x0000, "CW": 0x0003},
      {"AW": 0xFFF7, "DW": 0xFFFF, "CW": 0x0003},
      {"AW": 0xFFF7, "DW": 0xFFFF, "CW": 0xFFFD},
      {"AW": 0x0007, "DW": 0x0000, "CW": 0xFFFE}]),
    # --- BCD adjust / convert ---
    ("ADJBA", "ADJBA", ["V", "S", "Z", "P"],
     [{"AW": 0x000B}, {"AW": 0x0004}, {"AW": 0x010A}, {"AW": 0x00FF},
      {"AW": 0x0000}]),
    ("ADJBS", "ADJBS", ["V", "S", "Z", "P"],
     [{"AW": 0x000B}, {"AW": 0x0004}, {"AW": 0x010A}, {"AW": 0x00FF},
      {"AW": 0x0000}]),
    # ADJ4A documented all-X (defined); probed as a cross-check of V.
    ("ADJ4A", "ADJ4A", ["V"],
     [{"AW": 0x009A}, {"AW": 0x0033}, {"AW": 0x00FF}, {"AW": 0x000A}]),
    ("ADJ4S", "ADJ4S", ["V"],
     [{"AW": 0x009A}, {"AW": 0x0033}, {"AW": 0x00FF}, {"AW": 0x000A}]),
    ("CVTBD", "CVTBD", ["V", "AC", "CY"],
     [{"AW": 0x0053}, {"AW": 0x00FF}, {"AW": 0x0000}, {"AW": 0x000A}]),
    ("CVTDB", "CVTDB", ["V", "AC", "CY"],
     [{"AW": 0x0503}, {"AW": 0x0000}, {"AW": 0x09FF}, {"AW": 0xFF03}]),
    # --- logic ops (U = AC only) ---
    ("AND reg8,reg8", "AND AL, CL", ["AC"],
     [{"AW": 0x00FF, "CW": 0x0F}, {"AW": 0x0000, "CW": 0x00},
      {"AW": 0x00AA, "CW": 0x55}]),
    ("OR reg8,reg8", "OR AL, CL", ["AC"],
     [{"AW": 0x00FF, "CW": 0x0F}, {"AW": 0x0000, "CW": 0x00},
      {"AW": 0x00AA, "CW": 0x55}]),
    ("XOR reg8,reg8", "XOR AL, CL", ["AC"],
     [{"AW": 0x00FF, "CW": 0x0F}, {"AW": 0x0000, "CW": 0x00},
      {"AW": 0x00AA, "CW": 0x55}]),
    ("TEST reg8,reg8", "TEST AL, CL", ["AC"],
     [{"AW": 0x00FF, "CW": 0x0F}, {"AW": 0x0000, "CW": 0x00},
      {"AW": 0x00AA, "CW": 0x55}]),
    ("AND reg16,reg16", "AND AW, CW", ["AC"],
     [{"AW": 0x8000, "CW": 0x8000}, {"AW": 0x0000, "CW": 0x0000},
      {"AW": 0xAAAA, "CW": 0x5555}]),
    # --- shifts / rotates ---
    ("SHL reg,CL n=3", "SHL AL, CL", ["V", "AC"],
     [{"AW": 0x001F, "CW": 3}, {"AW": 0x0080, "CW": 3},
      {"AW": 0x00FF, "CW": 3}, {"AW": 0x0000, "CW": 3}]),
    ("SHL reg,CL n=9 (>width)", "SHL AL, CL", ["V", "AC"],
     [{"AW": 0x00FF, "CW": 9}, {"AW": 0x0001, "CW": 9}]),
    ("SHL reg,CL n=0", "SHL AL, CL", ["V", "AC"],
     [{"AW": 0x00FF, "CW": 0}, {"AW": 0x0080, "CW": 0}]),
    ("SHR reg,CL n=3", "SHR AL, CL", ["V", "AC"],
     [{"AW": 0x001F, "CW": 3}, {"AW": 0x0080, "CW": 3},
      {"AW": 0x00FF, "CW": 3}]),
    ("SHRA reg,CL n=3", "SHRA AL, CL", ["V", "AC"],
     [{"AW": 0x0080, "CW": 3}, {"AW": 0x001F, "CW": 3},
      {"AW": 0x00FF, "CW": 3}]),
    ("SHL reg,1", "SHL AL, 1", ["AC"],
     [{"AW": 0x0008}, {"AW": 0x0088}, {"AW": 0x00FF}]),
    ("SHR reg,1", "SHR AL, 1", ["AC"],
     [{"AW": 0x0008}, {"AW": 0x0081}, {"AW": 0x00FF}]),
    ("SHL reg,imm8 n=4", "SHL AL, 4", ["V", "AC"],
     [{"AW": 0x0008}, {"AW": 0x0088}, {"AW": 0x00FF}]),
    ("ROL reg,CL n=3", "ROL AL, CL", ["V"],
     [{"AW": 0x0080, "CW": 3}, {"AW": 0x0011, "CW": 3},
      {"AW": 0x00FF, "CW": 3}]),
    ("ROR reg,CL n=3", "ROR AL, CL", ["V"],
     [{"AW": 0x0080, "CW": 3}, {"AW": 0x0011, "CW": 3},
      {"AW": 0x00FF, "CW": 3}]),
    ("ROLC reg,CL n=3", "ROLC AL, CL", ["V"],
     [{"AW": 0x0080, "CW": 3}, {"AW": 0x0011, "CW": 3}]),
    ("RORC reg,CL n=3", "RORC AL, CL", ["V"],
     [{"AW": 0x0080, "CW": 3}, {"AW": 0x0011, "CW": 3}]),
    # --- CY bit ops (single byte F5/F8/F9; U = V,S,Z,AC,P per manual!) ---
    ("NOT1 CY", "NOT1 CY", ["V", "S", "Z", "AC", "P"],
     [{}, {"AW": 1}]),
    ("CLR1 CY", "CLR1 CY", ["V", "S", "Z", "AC", "P"],
     [{}, {"AW": 1}]),
    ("SET1 CY", "SET1 CY", ["V", "S", "Z", "AC", "P"],
     [{}, {"AW": 1}]),
    # --- 0F bit ops ---
    ("TEST1 reg16,CL", "TEST1 DW, CL", ["S", "AC", "P"],
     [{"DW": 0x8000, "CW": 15}, {"DW": 0x0000, "CW": 0},
      {"DW": 0xFFFF, "CW": 4}, {"DW": 0x0001, "CW": 0}]),
    ("TEST1 reg8,imm3", "TEST1 DL, 3", ["S", "AC", "P"],
     [{"DW": 0x0008}, {"DW": 0x0000}, {"DW": 0x00F7}]),
    ("NOT1 reg8,CL", "NOT1 DL, CL", ["V", "S", "Z", "AC", "P"],
     [{"DW": 0x0001, "CW": 0}, {"DW": 0x0000, "CW": 7}]),
    ("CLR1 reg16,imm4", "CLR1 DW, 5", ["V", "S", "Z", "AC", "P"],
     [{"DW": 0xFFFF}, {"DW": 0x0020}, {"DW": 0x0000}]),
    ("SET1 reg8,imm3", "SET1 DL, 2", ["V", "S", "Z", "AC", "P"],
     [{"DW": 0x0000}, {"DW": 0x00FF}]),
    # --- bit field INS/EXT (assembler lacks these forms; raw bytes) ---
    # INS DL,CL = 0F 31 CA (DL = bit offset, CL = length); dst DS1:IY
    ("INS reg8,reg8", bytes([0x0F, 0x31, 0xCA]),
     ["V", "S", "Z", "AC", "P", "CY"],
     [{"AW": 0xFFFF, "DW": 0, "CW": 3, "IY": 0x0620},
      {"AW": 0x0000, "DW": 0, "CW": 7, "IY": 0x0620},
      {"AW": 0x5555, "DW": 4, "CW": 3, "IY": 0x0620}]),
    # INS DL,4 = 0F 39 C2 04
    ("INS reg8,imm4", bytes([0x0F, 0x39, 0xC2, 0x04]),
     ["V", "S", "Z", "AC", "P", "CY"],
     [{"AW": 0x000F, "DW": 0, "IY": 0x0620},
      {"AW": 0xFFFF, "DW": 3, "IY": 0x0620}]),
    # EXT DL,CL = 0F 33 CA; src DS0:IX
    ("EXT reg8,reg8", bytes([0x0F, 0x33, 0xCA]),
     ["V", "S", "Z", "AC", "P", "CY"],
     [{"DW": 0, "CW": 7, "IX": 0x0600}, {"DW": 4, "CW": 3, "IX": 0x0600},
      {"DW": 0, "CW": 15, "IX": 0x0600}],
     [(0x600, 0xA5), (0x601, 0x3C)]),
    # EXT DL,4 = 0F 3B C2 04
    ("EXT reg8,imm4", bytes([0x0F, 0x3B, 0xC2, 0x04]),
     ["V", "S", "Z", "AC", "P", "CY"],
     [{"DW": 0, "IX": 0x0600}, {"DW": 5, "IX": 0x0600}],
     [(0x600, 0xA5), (0x601, 0x3C)]),
    # --- BCD string ops (0F 20/22/26); src DS0:IX, dst DS1:IY, CL digits ---
    ("ADD4S", bytes([0x0F, 0x20]), ["V", "S", "AC", "P"],
     [{"CW": 4, "IX": 0x0600, "IY": 0x0620},
      {"CW": 2, "IX": 0x0600, "IY": 0x0620}],
     [(0x600, 0x34), (0x601, 0x12), (0x620, 0x66), (0x621, 0x88)]),
    ("SUB4S", bytes([0x0F, 0x22]), ["V", "S", "AC", "P"],
     [{"CW": 4, "IX": 0x0600, "IY": 0x0620},
      {"CW": 2, "IX": 0x0600, "IY": 0x0620}],
     [(0x600, 0x34), (0x601, 0x12), (0x620, 0x66), (0x621, 0x88)]),
    ("CMP4S", bytes([0x0F, 0x26]), ["V", "S", "AC", "P"],
     [{"CW": 4, "IX": 0x0600, "IY": 0x0620},
      {"CW": 2, "IX": 0x0600, "IY": 0x0620}],
     [(0x600, 0x34), (0x601, 0x12), (0x620, 0x66), (0x621, 0x88)]),
    # --- disambiguation reruns (first sweep undersampled these) ---
    # DIV reg16 with quotient 0: is Z really constant-0 or Z(result)?
    ("DIV reg16 q0", "DIV CW", ["V", "S", "Z", "AC", "P", "CY"],
     [{"AW": 0x0000, "DW": 0x0000, "CW": 0x0001},
      {"AW": 0x0001, "DW": 0x0000, "CW": 0x0002}]),
    # imm with non-zero low byte (0x300's zero low byte masked P)
    ("MUL reg16,reg16,imm16 b", "MUL CW, DW, 0x123", ["S", "Z", "AC", "P"],
     [{"DW": 0x0000}, {"DW": 0x0007}, {"DW": 0xFFFF}, {"DW": 0x00FF}]),
    # BCD strings: vary carry/borrow/equality situations
    ("ADD4S nocarry", bytes([0x0F, 0x20]), ["V", "S", "AC", "P"],
     [{"CW": 4, "IX": 0x0600, "IY": 0x0620},
      {"CW": 2, "IX": 0x0600, "IY": 0x0620}],
     [(0x600, 0x11), (0x601, 0x11), (0x620, 0x22), (0x621, 0x22)]),
    ("SUB4S borrow", bytes([0x0F, 0x22]), ["V", "S", "AC", "P"],
     [{"CW": 4, "IX": 0x0600, "IY": 0x0620},
      {"CW": 2, "IX": 0x0600, "IY": 0x0620}],
     [(0x600, 0x44), (0x601, 0x44), (0x620, 0x11), (0x621, 0x11)]),
    ("CMP4S equal", bytes([0x0F, 0x26]), ["V", "S", "AC", "P"],
     [{"CW": 4, "IX": 0x0600, "IY": 0x0620},
      {"CW": 2, "IX": 0x0600, "IY": 0x0620}],
     [(0x600, 0x34), (0x601, 0x12), (0x620, 0x34), (0x621, 0x12)]),
]


def parity8(v):
    return 1 if bin(v & 0xFF).count("1") % 2 == 0 else 0


def reg_views(r):
    """Named sub-register views used by the classifier candidates."""
    return {
        "AL": r["AW"] & 0xFF, "AH": (r["AW"] >> 8) & 0xFF, "AW": r["AW"],
        "CL": r["CW"] & 0xFF, "CW": r["CW"],
        "DL": r["DW"] & 0xFF, "DW": r["DW"], "BW": r["BW"],
    }


def candidates():
    """flag-letter-keyed standard functions of result registers."""
    c = {}
    for name in ("AL", "AH", "AW", "CL", "CW", "DL", "DW", "BW"):
        wid = 8 if name.endswith(("L", "H")) else 16
        c[f"S=MSB({name})"] = ("S", name,
                               lambda v, w=wid: (v >> (w - 1)) & 1)
        c[f"Z=({name}==0)"] = ("Z", name, lambda v: 1 if v == 0 else 0)
        c[f"P=parity({name}.lo8)"] = ("P", name, parity8)
    return c


CANDS = candidates()


def classify(flag, samples):
    """samples: list of (psw_in_bit, out_bit, regs_out). Returns verdict."""
    outs = [o for _, o, _ in samples]
    ins = [i for i, _, _ in samples]
    if all(o == i for i, o, _ in samples) and 0 in ins and 1 in ins:
        return "preserved (out == in)"
    if all(o == 0 for o in outs):
        return "always 0" + ("" if 1 in ins else " (never saw in=1!)")
    if all(o == 1 for o in outs):
        return "always 1" + ("" if 0 in ins else " (never saw in=0!)")
    hits = [name for name, (fl, reg, fn) in CANDS.items()
            if fl == flag[0] and
            all(fn(reg_views(r)[reg]) == o for _, o, r in samples)]
    if hits:
        return "acts defined: " + " and ".join(hits)
    return "operand-dependent: " + " ".join(
        f"[in={i} out={o} AW={r['AW']:04x} CW={r['CW']:04x} "
        f"DW={r['DW']:04x}]"
        for i, o, r in samples)


def log_line(obj):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as f:
        f.write(json.dumps(obj) + "\n")


def run_case_pattern(host, name, instr, pat, psw_in, ram, tag):
    """One hardware run with one retry then skip-and-log. Returns regs
    dict or None (skipped)."""
    regs = dict(pat, PSW=psw_in)
    for attempt in (1, 2):
        try:
            res = run_test(regs=regs, instr=instr, host=host, tag=tag,
                           ram=ram)
            out = res["regs"]
            if out.get("PSW") is None:
                raise RuntimeError("no PSW push found in trace")
            log_line({"case": name, "pat": pat, "psw_in": psw_in,
                      "regs_out": {k: v for k, v in out.items()}})
            return out
        except Exception as e:                          # noqa: BLE001
            print(f"    attempt {attempt} failed: {str(e)[:100]}",
                  flush=True)
            if attempt == 2:
                log_line({"case": name, "pat": pat, "psw_in": psw_in,
                          "error": str(e)[:200]})
                return None
            time.sleep(2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["all", "list"])
    ap.add_argument("--host", default="root@mister-nec")
    ap.add_argument("--only", default=None,
                    help="run only cases whose name contains SUBSTR")
    args = ap.parse_args()
    a = Assembler()
    if args.cmd == "list":
        for c in CASES:
            print(c[0])
        return 0
    report = {}
    skipped = []
    t0 = time.time()
    for case in CASES:
        name, code, uflags, patterns = case[:4]
        ram = case[4] if len(case) > 4 else None
        if args.only and args.only not in name:
            continue
        instr = code if isinstance(code, bytes) else a.assemble(code)
        print(f"\n=== {name} [{instr.hex(' ')}] ===", flush=True)
        samples = {f: [] for f in uflags}
        rows = []
        for pi, pat in enumerate(patterns):
            for psw_in in PSW_IN if pi < 2 else PSW_IN[:1]:
                out = run_case_pattern(args.host, name, instr, pat, psw_in,
                                       ram, tag=f"fl{pi}")
                if out is None:
                    skipped.append((name, pat, psw_in))
                    continue
                norm_in = (psw_in & 0x0ED5) | 0xF002
                rows.append((pat, norm_in, out))
                for f in uflags:
                    b = FLAG_BITS[f]
                    samples[f].append((1 if norm_in & b else 0,
                                       1 if out["PSW"] & b else 0, out))
        for pat, pin, out in rows:
            fl = "".join(n for n, b in FLAG_BITS.items() if out["PSW"] & b)
            print(f"  {json.dumps(pat):<44} psw_in={pin:04x} -> "
                  f"AW={out['AW']:04x} CW={out['CW']:04x} "
                  f"DW={out['DW']:04x} PSW={out['PSW']:04x} [{fl}]",
                  flush=True)
        report[name] = {}
        for f in uflags:
            if not samples[f]:
                report[name][f] = "NO DATA (all runs skipped)"
            else:
                report[name][f] = classify(f, samples[f])
            print(f"  U-flag {f:<3}: {report[name][f]}", flush=True)
    if args.only:
        # partial run: merge into the existing report instead of clobbering
        merged = json.loads(REPORT.read_text()) if REPORT.exists() else {}
        merged.update(report)
        report = merged
    REPORT.write_text(json.dumps(report, indent=1) + "\n")
    print(f"\nreport -> {REPORT}", flush=True)
    if skipped:
        print(f"SKIPPED {len(skipped)} runs: {skipped}", flush=True)
    print(f"total {time.time() - t0:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
