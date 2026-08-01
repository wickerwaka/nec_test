#!/usr/bin/env python3
"""pla3_check - standing gate for the V20/V30 GROUP-DECODE PLA identification.

Recomputes, from first principles, every claim made in docs/facts/pla_model.md
about docs/pla_3.txt / docs/pla3_outputs.txt (the per-opcode group-decode PLA)
and about docs/pla_2.txt (the condition-evaluation PLA).

Checks performed (all must pass; exit 0 on success, 1 on any failure):

  A. STRUCTURE  - the 59 product terms of docs/pla_3.txt, OR-ed, reproduce all
                  3 x 256 output vectors of docs/pla3_outputs.txt bit-exactly.
                  Establishes that the 2-bit prefix is a MODE select:
                  01 = native, 00 = 8080-emulation, 11 = 0F/ext page.
  B. COLUMNS    - each of the 14 native-mode output columns equals a predicate
                  computed from INDEPENDENT metadata (docs/facts/instructions.json
                  encodings + sw/optable.py + opcode arithmetic), up to an
                  explicitly declared exception set.  Exceptions are findings,
                  not slack: every one is named and justified.
  C. XOP FIELD  - columns 10..13 form a 4-bit encoded field.  For the
                  one-byte-logic class (column 2) it is a complete 16-entry
                  hardware-op table; the six ops that exist in BOTH the native
                  and the 8080 section must carry IDENTICAL field values.
                  For the remaining classes the field is reconstructed from a
                  class table and must match all 256 native entries exactly.
  D. EXT PAGE   - the 0F-page section decodes at BLOCK granularity; the
                  documented 0F forms must be a subset of each block and the
                  extra members must be exactly the block fill (alias opcodes).
  E. PLA_2      - the condition-evaluation PLA model (12 active-low inputs:
                  mode, /V /CY /Z /S /P, /op5../op0) must reproduce all 16 x86
                  conditions and all 8 8080 conditions over every flag vector.

Usage:  python3 sw/pla3_check.py [-v]
"""
import argparse
import json
import re
import sys
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))
import optable  # noqa: E402
import fuzz_cov  # noqa: E402

DOCS = ROOT / "docs"
NATIVE, MODE8080, EXT = "native opcodes", "8080 opcodes", "ext opcodes"
PREFIX_OF = {NATIVE: "01", MODE8080: "00", EXT: "11"}

ERRORS = []
NOTES = []


def fail(msg):
    ERRORS.append(msg)


def note(msg):
    NOTES.append(msg)


# ---------------------------------------------------------------------------
# A. parse + structural reproduction
# ---------------------------------------------------------------------------
def load_outputs():
    sections, cur = {}, None
    for line in (DOCS / "pla3_outputs.txt").read_text().splitlines():
        s = line.strip()
        if not s:
            continue
        m = re.match(r"^([0-9A-Fa-f]{2}) ([01]{14})$", s)
        if m:
            sections[cur][int(m.group(1), 16)] = m.group(2)
        else:
            cur = s
            sections[cur] = {}
    return sections


def load_terms():
    terms = []
    for line in (DOCS / "pla_3.txt").read_text().splitlines():
        s = line.strip()
        if not s:
            continue
        m = re.match(r"^([01?]{2}) ([01?]{8}) ([01]{14})(.*)$", s)
        if not m:
            fail(f"pla_3.txt: unparsable product term {s!r}")
            continue
        terms.append((m.group(1), m.group(2), m.group(3), m.group(4).strip()))
    return terms


def pat_match(pat, bits):
    return all(p == "?" or p == b for p, b in zip(pat, bits))


def check_structure(sections, terms):
    if len(terms) != 59:
        fail(f"A: expected 59 product terms in pla_3.txt, got {len(terms)}")
    for name, prefix in PREFIX_OF.items():
        if name not in sections:
            fail(f"A: section {name!r} missing from pla3_outputs.txt")
            continue
        if len(sections[name]) != 256:
            fail(f"A: section {name!r} has {len(sections[name])} entries, want 256")
            continue
        bad = 0
        for op in range(256):
            ob = format(op, "08b")
            acc = ["0"] * 14
            for tp, top, tout, _ in terms:
                if pat_match(tp, prefix) and pat_match(top, ob):
                    for i, c in enumerate(tout):
                        if c == "1":
                            acc[i] = "1"
            if "".join(acc) != sections[name][op]:
                bad += 1
        if bad:
            fail(f"A: {name}: {bad}/256 opcodes where the product terms do not "
                 f"reproduce the dumped output vector")
        else:
            note(f"A: {name} (prefix {prefix}): 256/256 output vectors reproduced "
                 f"by the {len(terms)} product terms")


# ---------------------------------------------------------------------------
# metadata: per-opcode facts derived from instructions.json + optable
# ---------------------------------------------------------------------------
def load_encodings():
    """Map each documented first-byte encoding pattern to the opcodes it covers.

    Returns (cover, recs) where cover[op] = list of records covering op and each
    record is the raw instructions.json dict.
    """
    db = json.loads((DOCS / "facts" / "instructions.json").read_text())["instructions"]
    cover = {op: [] for op in range(256)}
    for r in db:
        e = r["encoding"][0]
        ops = expand_first_byte(e)
        for op in ops:
            cover[op].append(r)
    return cover, db


def expand_first_byte(e):
    """Expand a documented first-byte pattern into the opcodes it covers."""
    e = e.strip()
    if re.fullmatch(r"[01WSXV]{8}", e):
        out = [0]
        for c in e:
            if c in "01":
                out = [(v << 1) | int(c) for v in out]
            else:
                out = [(v << 1) | b for v in out for b in (0, 1)]
        return sorted(set(out))
    fields = e.split()
    # field-style: literal bit runs plus named 2/3-bit fields
    widths = {"sreg": 2, "reg": 3, "W": 1}
    bits = []
    for f in fields:
        if re.fullmatch(r"[01]+", f):
            bits.extend(list(f))
        elif f in widths:
            bits.extend(["?"] * widths[f])
        else:
            return []
    if len(bits) != 8:
        return []
    out = [0]
    for c in bits:
        if c in "01":
            out = [(v << 1) | int(c) for v in out]
        else:
            out = [(v << 1) | b for v in out for b in (0, 1)]
    return sorted(set(out))


def build_facts():
    cover, db = load_encodings()
    F = {}
    # W at opcode bit 0 (documented byte/word pairs)
    w_bit0 = set()
    for r in db:
        e = r["encoding"][0].strip()
        if re.fullmatch(r"[01WSXV]{8}", e) and e[7] == "W":
            w_bit0.update(expand_first_byte(e))
    # W at opcode bit 3: the '1011 W reg' MOV reg,imm family
    mov_reg_imm = set()
    for r in db:
        if r["encoding"][0].strip() == "1011 W reg":
            mov_reg_imm.update(expand_first_byte(r["encoding"][0]))
    # BCD ADJUST category (ADJ4A/ADJ4S/ADJBA/ADJBS)
    bcd_adjust = set()
    for r in db:
        if r["category"] == "BCD ADJUST":
            bcd_adjust.update(expand_first_byte(r["encoding"][0]))
    # segment-register MOV forms (fully specified first byte mentioning sreg)
    sreg_mov = set()
    for r in db:
        e = r["encoding"][0].strip()
        if "sreg" in r["nec_form"] and re.fullmatch(r"[01WSXV]{8}", e):
            sreg_mov.update(expand_first_byte(e))
    # implicit accumulator operand whose width is the W bit
    acc_w = set()
    for r in db:
        e = r["encoding"][0].strip()
        if not (re.fullmatch(r"[01WSXV]{8}", e) and e[7] == "W"):
            continue
        if "acc" in r["nec_form"] or re.search(r"\bAW\b", r["operation"]):
            acc_w.update(expand_first_byte(e))
    # data-conversion / translate block members that are documented
    conv = set()
    for r in db:
        if r["nec_form"].split()[0] in ("CVTBD", "CVTDB", "TRANS", "TRANSB"):
            conv.update(expand_first_byte(r["encoding"][0]))
    F.update(cover=cover, db=db, w_bit0=w_bit0, mov_reg_imm=mov_reg_imm,
             bcd_adjust=bcd_adjust, sreg_mov=sreg_mov, acc_w=acc_w, conv=conv)
    return F


def mnem_root(op):
    o = optable.TABLE.get(op)
    return o.mnem.split()[0] if o else None


def mnem_operands(op):
    o = optable.TABLE.get(op)
    if not o or " " not in o.mnem:
        return []
    return [x.strip() for x in o.mnem.split(" ", 1)[1].split(",")]


def has_modrm(op):
    o = optable.TABLE.get(op)
    return bool(o and o.modrm)


def dir_pairs():
    """Opcodes whose bit 1 is the source/destination DIRECTION bit.

    Rule: op and op^2 both carry a ModR/M byte, share a mnemonic root, and
    their operand lists are exact reverses of one another (non-empty).
    """
    out = set()
    for op in range(256):
        alt = op ^ 0x02
        if not (has_modrm(op) and has_modrm(alt)):
            continue
        if mnem_root(op) is None or mnem_root(op) != mnem_root(alt):
            continue
        a, b = mnem_operands(op), mnem_operands(alt)
        if len(a) != 2 or len(b) != 2:
            continue
        if a[0] == a[1] or a != list(reversed(b)):
            continue
        out.add(op)
    return out


# ---------------------------------------------------------------------------
# B. the 14 native columns
# ---------------------------------------------------------------------------
def col_set(sections, name, bit):
    return {op for op in range(256) if sections[name][op][bit] == "1"}


COLUMN_NAMES = [
    "BYTE_ONLY",       # 0
    "W_FROM_BIT0",     # 1
    "ONE_BYTE_LOGIC",  # 2
    "ACC_W_OPERAND",   # 3
    "SREG_MOV",        # 4
    "HAS_MODRM",       # 5
    "MODRM_STORE",     # 6
    "DIR_FROM_BIT1",   # 7
    "NATIVE_HI",       # 8
    "INCDEC_NO_CY",    # 9
    "XOP3", "XOP2", "XOP1", "XOP0",  # 10..13
]

# one-byte-logic (column 2) hardware-op decode: XOP value -> (native ops, 8080 ops, name)
BL1_TABLE = {
    0b0000: ({0x26, 0x2E, 0x36, 0x3E}, set(), "segment override prefix"),
    0b0001: ({0x0F}, {0xED}, "extension-page prefix (0F native / ED 8080)"),
    0b0010: ({0xFD}, set(), "SET1 DIR (STD)"),
    0b0011: ({0xFC}, set(), "CLR1 DIR (CLD)"),
    0b0100: ({0xFB}, {0xFB}, "EI (STI)"),
    0b0101: ({0xFA}, {0xF3}, "DI (CLI)"),
    0b0110: ({0xF9}, {0x37}, "SET1 CY (STC)"),
    0b0111: ({0xF8}, set(), "CLR1 CY (CLC)"),
    0b1000: ({0x65}, set(), "REPC prefix"),
    0b1001: ({0x64}, set(), "REPNC prefix"),
    0b1010: ({0xF5}, {0x3F}, "NOT1 CY (CMC)"),
    0b1011: ({0xF4}, {0x76}, "HALT"),
    0b1100: ({0xF3}, set(), "REP/REPE prefix"),
    0b1101: ({0xF2}, set(), "REPNE prefix"),
    0b1110: ({0xF1}, set(), "BUSLOCK alias prefix (undocumented 0xF1)"),
    0b1111: ({0xF0}, set(), "BUSLOCK prefix"),
}

# non-1BL XOP classes for the native section: name -> (opcode set, value)
def native_xop_classes(F):
    grp = {0xF6, 0xF7, 0xFE, 0xFF}
    return [
        ("decimal adjust", F["bcd_adjust"], 0b1010),
        ("increment/decrement", set(range(0x40, 0x50)), 0b1100),
        ("port I/O", {0xE4, 0xE5, 0xE6, 0xE7, 0xEC, 0xED, 0xEE, 0xEF}, 0b1111),
        ("second-byte group dispatch", grp, 0b1011),
        ("block I/O (INM/OUTM)", {0x6C, 0x6D, 0x6E, 0x6F}, 0b0110),
        ("count/compare-loop", {0xA6, 0xA7, 0xAE, 0xAF, 0xC0, 0xC1, 0xE0, 0xE1}, 0b1110),
        ("multiply / ALU-immediate group", {0x69, 0x6B} | set(range(0x80, 0x88)), 0b0100),
        ("segment-register operand", {0x07, 0x17, 0x1F, 0x8C, 0x8E}, 0b0001),
    ]


def check_native_columns(sections, F):
    S = sections[NATIVE]
    got = [col_set(sections, NATIVE, b) for b in range(14)]

    onebyte_logic = ({0x0F} | set(optable.PREFIXES)
                     | {0xF4, 0xF5, 0xF8, 0xF9, 0xFA, 0xFB, 0xFC, 0xFD})
    modrm_store = {0x88, 0x89, 0x8C, 0x8F, 0xC6, 0xC7}
    byte_only = F["bcd_adjust"] | F["conv"] | {op for op in F["mov_reg_imm"] if not op & 0x08}

    # (bit, predicate set, extra-exceptions {op: reason})
    spec = [
        (0, byte_only, {
            0xD6: "undocumented SALC/0xD6 - shares the '110101??' D4-D7 product term",
        }),
        (1, F["w_bit0"], {
            0xE0: "LOOPNE - PLA merge, shares term '11?0000?' with C0/C1",
            0xE1: "LOOPE  - PLA merge, shares term '11?0000?' with C0/C1",
        }),
        (2, onebyte_logic, {
            0xF1: "0xF1 decoded as a BUSLOCK-alias PREFIX (term '01 111100??')",
        }),
        (3, F["acc_w"], {
            0xA4: "MOVBK  - block merge, term '01 1010????' covers all of A0-AF",
            0xA5: "MOVBK  - block merge, term '01 1010????' covers all of A0-AF",
            0xA6: "CMPBK  - block merge, term '01 1010????' covers all of A0-AF",
            0xA7: "CMPBK  - block merge, term '01 1010????' covers all of A0-AF",
        }),
        (4, F["sreg_mov"], {}),
        (5, {op for op in range(256) if has_modrm(op)}, {
            0x63: "PLA decodes 0x63 WITH a ModR/M byte (term '01 01100?1?' = 62/63/66/67); "
                  "sw/optable.py currently models 0x63 as ModR/M-less",
        }),
        (6, modrm_store, {
            0x8D: "LDEA/LEA - PLA merge, shares term '01 100011?1' with 8F POP mem16",
        }),
        (7, dir_pairs(), {
            0xC0: "PLA merge, term '01 11?0000?' (C0/C1/E0/E1)",
            0xC1: "PLA merge, term '01 11?0000?' (C0/C1/E0/E1)",
            0xE0: "PLA merge, term '01 11?0000?' (C0/C1/E0/E1)",
            0xE1: "PLA merge, term '01 11?0000?' (C0/C1/E0/E1)",
        }),
        (8, set(range(0x80, 0x100)), {}),
        (9, set(range(0x40, 0x50)) | {0xFE, 0xFF}, {
            0xF6: "GRP3 - PLA merge, term '01 1111?11?' covers F6/F7/FE/FF",
            0xF7: "GRP3 - PLA merge, term '01 1111?11?' covers F6/F7/FE/FF",
        }),
    ]
    for bit, pred, exc in spec:
        want = set(pred) | set(exc)
        missing = want - got[bit]
        extra = got[bit] - want
        if missing:
            fail(f"B: native column {bit} {COLUMN_NAMES[bit]}: predicate opcodes NOT "
                 f"asserted: {sorted(format(o, '02X') for o in missing)}")
        if extra:
            fail(f"B: native column {bit} {COLUMN_NAMES[bit]}: UNDECLARED extra "
                 f"opcodes asserted: {sorted(format(o, '02X') for o in extra)}")
        if not missing and not extra:
            note(f"B: native column {bit:>2} {COLUMN_NAMES[bit]:<15} EXACT "
                 f"({len(got[bit])} opcodes, {len(exc)} declared exception(s))")


# ---------------------------------------------------------------------------
# C. the XOP[3:0] field
# ---------------------------------------------------------------------------
def xop(sections, name, op):
    return int(sections[name][op][10:14], 2)


def check_xop(sections, F):
    # C1: the 1BL table is complete and consistent within the native section
    seen = {}
    for val, (nat, m80, label) in BL1_TABLE.items():
        for op in nat:
            if sections[NATIVE][op][2] != "1":
                fail(f"C: native {op:02X} ({label}) not marked ONE_BYTE_LOGIC")
            if xop(sections, NATIVE, op) != val:
                fail(f"C: native {op:02X} ({label}) XOP={xop(sections,NATIVE,op):04b}, "
                     f"want {val:04b}")
            seen[op] = val
        for op in m80:
            if sections[MODE8080][op][2] != "1":
                fail(f"C: 8080 {op:02X} ({label}) not marked ONE_BYTE_LOGIC")
            if xop(sections, MODE8080, op) != val:
                fail(f"C: 8080 {op:02X} ({label}) XOP="
                     f"{xop(sections,MODE8080,op):04b}, want {val:04b}")
    if len(BL1_TABLE) != 16:
        fail("C: the 1BL XOP table must enumerate all 16 field values")
    # every native 1BL opcode must be in the table
    nat1bl = {op for op in range(256) if sections[NATIVE][op][2] == "1"}
    tbl = set().union(*(v[0] for v in BL1_TABLE.values()))
    if nat1bl != tbl:
        fail(f"C: native ONE_BYTE_LOGIC set {sorted(nat1bl)} != 1BL table {sorted(tbl)}")
    else:
        note(f"C: 1BL hardware-op table complete: 16/16 field values, "
             f"{len(nat1bl)} native opcodes")
    m801bl = {op for op in range(256) if sections[MODE8080][op][2] == "1"}
    tbl80 = set().union(*(v[1] for v in BL1_TABLE.values()))
    if m801bl != tbl80:
        fail(f"C: 8080 ONE_BYTE_LOGIC set {sorted(m801bl)} != table {sorted(tbl80)}")
    else:
        note(f"C: 8080-mode 1BL set matches ({len(m801bl)} opcodes); the six ops "
             f"present in both modes carry IDENTICAL XOP values")

    # C2: reconstruct all 256 native XOP values from the class table
    recon = {op: 0 for op in range(256)}
    for op, val in seen.items():
        recon[op] = val
    for label, ops, val in native_xop_classes(F):
        for op in ops:
            if op in seen and seen[op] != val:
                continue  # 1BL wins (context-dependent field)
            recon[op] = val
    bad = [op for op in range(256) if recon[op] != xop(sections, NATIVE, op)]
    if bad:
        fail("C: native XOP class table does not reconstruct: "
             + ", ".join(f"{o:02X}(got {xop(sections,NATIVE,o):04b} want "
                         f"{recon[o]:04b})" for o in bad[:16]))
    else:
        note("C: native XOP[3:0] reconstructed for all 256 opcodes from the "
             "1BL table + 8 non-1BL classes")

    # C3: cross-mode agreement of the non-1BL classes
    cross = [
        ("decimal adjust", 0b1010, [(NATIVE, 0x27), (MODE8080, 0x27), (EXT, 0x20)]),
        ("increment/decrement", 0b1100, [(NATIVE, 0x40), (MODE8080, 0x04)]),
        ("port I/O", 0b1111, [(NATIVE, 0xE4), (MODE8080, 0xDB), (MODE8080, 0xD3)]),
    ]
    for label, val, refs in cross:
        for sec, op in refs:
            if xop(sections, sec, op) != val:
                fail(f"C: cross-mode {label}: {sec} {op:02X} XOP="
                     f"{xop(sections,sec,op):04b}, want {val:04b}")
    note("C: cross-mode XOP agreement holds for decimal-adjust / inc-dec / port-I/O")


# ---------------------------------------------------------------------------
# D. the 0F extension page
# ---------------------------------------------------------------------------
EXT_BLOCKS = {
    "bit manipulation (TEST1/CLR1/SET1/NOT1)": set(range(0x10, 0x20)),
    "BCD string (ADD4S/SUB4S/CMP4S)": set(range(0x20, 0x28)),
    "nibble rotate (ROL4/ROR4)": set(range(0x28, 0x30)),
    "bit field (INS/EXT)": set(range(0x30, 0x40)),
}


def check_ext(sections):
    S = sections[EXT]
    got = {b: col_set(sections, EXT, b) for b in range(14)}
    blocks = EXT_BLOCKS
    expect = {
        5: blocks["bit manipulation (TEST1/CLR1/SET1/NOT1)"]
           | blocks["nibble rotate (ROL4/ROR4)"] | blocks["bit field (INS/EXT)"],
        1: blocks["bit manipulation (TEST1/CLR1/SET1/NOT1)"]
           | blocks["nibble rotate (ROL4/ROR4)"] | blocks["bit field (INS/EXT)"],
        0: blocks["BCD string (ADD4S/SUB4S/CMP4S)"],
        3: blocks["bit field (INS/EXT)"],
        6: blocks["nibble rotate (ROL4/ROR4)"] | blocks["bit field (INS/EXT)"],
        10: blocks["BCD string (ADD4S/SUB4S/CMP4S)"],
        12: blocks["BCD string (ADD4S/SUB4S/CMP4S)"] | blocks["bit field (INS/EXT)"],
        13: blocks["bit field (INS/EXT)"],
    }
    for b, want in expect.items():
        if got[b] != want:
            fail(f"D: ext column {b} {COLUMN_NAMES[b]}: got "
                 f"{sorted(format(o,'02X') for o in got[b])}, want "
                 f"{sorted(format(o,'02X') for o in want)}")
    for b in (2, 4, 7, 8, 9, 11):
        if got[b]:
            fail(f"D: ext column {b} {COLUMN_NAMES[b]} expected empty, got "
                 f"{sorted(format(o,'02X') for o in got[b])}")
    # documented 0F ModR/M forms must be a subset of the ModR/M blocks
    documented = set(fuzz_cov.F0_MODRM)
    if not documented <= got[5]:
        fail(f"D: documented 0F ModR/M forms not covered: "
             f"{sorted(format(o,'02X') for o in documented - got[5])}")
    fill = got[5] - documented
    note(f"D: 0F page decodes at BLOCK granularity; {len(documented)} documented "
         f"ModR/M forms + {len(fill)} alias fill-ins "
         f"({', '.join(format(o,'02X') for o in sorted(fill))})")
    # the whole page outside 0x10-0x3F must be inert
    inert = {op for op in range(256) if S[op] != "0" * 14}
    if inert != set(range(0x10, 0x40)):
        fail(f"D: ext page non-zero rows are {sorted(format(o,'02X') for o in inert)}, "
             f"want 10-3F")
    else:
        note("D: 0F page asserts nothing outside 0F 10-3F (0F FF BRKEM is handled "
             "entirely by microcode, not by this PLA)")


# ---------------------------------------------------------------------------
# E. pla_2 - the condition-evaluation PLA
# ---------------------------------------------------------------------------
def check_pla2():
    rows = [l.strip() for l in (DOCS / "pla_2.txt").read_text().splitlines() if l.strip()]
    if any(len(r) != 12 for r in rows):
        fail("E: pla_2.txt rows are not all 12 bits wide")
        return
    b0 = [r for r in rows if r[0] == "0"]
    b1 = [r for r in rows if r[0] == "1"]
    if (len(b0), len(b1)) != (18, 8):
        fail(f"E: pla_2 bank sizes {(len(b0), len(b1))}, want (18, 8)")

    def word(mode, V, CY, Z, S, P, op):
        b = [0] * 12
        b[0] = mode
        for i, f in enumerate([V, CY, Z, S, P]):
            b[1 + i] = 1 - int(f)          # flags are ACTIVE LOW
        for k in range(6):                 # /op5../op0 -> positions 6..11
            b[6 + k] = 1 - ((op >> (5 - k)) & 1)
        return b

    def hit(terms, b):
        return any(all(c == "?" or int(c) == b[i] for i, c in enumerate(r))
                   for r in terms)

    def x86(cc, CY, P, Z, S, V):
        return [V, not V, CY, not CY, Z, not Z, CY or Z, not (CY or Z),
                S, not S, P, not P, S != V, S == V, Z or (S != V),
                (not Z) and (S == V)][cc]

    def i8080(ccc, CY, P, Z, S):
        return [not Z, Z, not CY, CY, not P, P, not S, S][ccc]

    bad = tot = 0
    for cc in range(16):
        for hi in range(4):
            for fv in range(32):
                V, CY, Z, S, P = [bool((fv >> k) & 1) for k in range(5)]
                tot += 1
                if hit(b0, word(0, V, CY, Z, S, P, (hi << 4) | cc)) != \
                        x86(cc, CY, P, Z, S, V):
                    bad += 1
    if bad:
        fail(f"E: pla_2 native bank: {bad}/{tot} mismatches vs the x86 Jcc table")
    else:
        note(f"E: pla_2 bank 0 == all 16 native conditions, {tot}/{tot} cells "
             f"(cc = opcode bits 3..0, flags V/CY/Z/S/P, all inputs active-low)")
    bad = tot = 0
    for ccc in range(8):
        for lo in range(8):
            for fv in range(32):
                V, CY, Z, S, P = [bool((fv >> k) & 1) for k in range(5)]
                tot += 1
                if hit(b1, word(1, V, CY, Z, S, P, (ccc << 3) | lo)) != \
                        i8080(ccc, CY, P, Z, S):
                    bad += 1
    if bad:
        fail(f"E: pla_2 8080 bank: {bad}/{tot} mismatches vs the 8080 ccc table")
    else:
        note(f"E: pla_2 bank 1 == all 8 8080 conditions, {tot}/{tot} cells "
             f"(ccc = opcode bits 5..3; AC and V are not testable, as on the 8080)")


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    sections = load_outputs()
    terms = load_terms()
    check_structure(sections, terms)
    if ERRORS:
        report(args)
        return 1
    F = build_facts()
    check_native_columns(sections, F)
    check_xop(sections, F)
    check_ext(sections)
    check_pla2()
    return report(args)


def report(args):
    if args.verbose or not ERRORS:
        for n in NOTES:
            print("  ok  " + n)
    if ERRORS:
        print(f"\npla3_check: {len(ERRORS)} FAILURE(S)")
        for e in ERRORS:
            print("  FAIL " + e)
        return 1
    print(f"\npla3_check: OK ({len(NOTES)} checks passed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
