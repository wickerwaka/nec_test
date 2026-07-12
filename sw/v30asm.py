#!/usr/bin/env python3
"""v30asm - NEC-syntax mini-assembler driven by docs/facts/instructions.json.

Encodings come straight from the extracted User's Manual database, so every
successful assembly cross-checks the database; there is no second opcode
table to drift out of sync. NEC mnemonics and register names (AW, BW, IX,
IY, PS, DS0...) as in the manual.

Supported syntax (one instruction/directive per line, ';' comments):
    org 0x100
    label:
    MOV AW, 0x1234
    MOV [BW], AW          ; memory operands: [BW+IX+4], [0x2000], [BP+IX]
    ADD AL, byte [IX]     ; byte/word force ambiguous memory sizes
    BNZ label             ; short-label branches are PC-relative
    DB 0x90, 0x90
    DW 0xFFFF

Library use:
    a = Assembler()
    code = a.assemble(source, org=0x100)
    img = build_image(code, org=0x100)      # 64 KB, reset vector included

Self-test: python3 sw/v30asm.py --selftest
"""

import argparse
import json
import re
import sys
from pathlib import Path

FACTS = Path(__file__).resolve().parent.parent / "docs" / "facts" / "instructions.json"

REG16 = {"AW": 0, "CW": 1, "DW": 2, "BW": 3, "SP": 4, "BP": 5, "IX": 6, "IY": 7}
REG8  = {"AL": 0, "CL": 1, "DL": 2, "BL": 3, "AH": 4, "CH": 5, "DH": 6, "BH": 7}
SREG  = {"DS1": 0, "PS": 1, "SS": 2, "DS0": 3}

# Table 12-5 memory addressing: base/index combination -> mem field
MEM_COMBO = {
    ("BW", "IX"): 0, ("BW", "IY"): 1, ("BP", "IX"): 2, ("BP", "IY"): 3,
    ("IX",): 4, ("IY",): 5, ("BP",): 6, ("BW",): 7,
}


class AsmError(Exception):
    pass


class Operand:
    def __init__(self, kind, **kw):
        self.kind = kind           # reg8/reg16/sreg/mem/imm/label
        self.__dict__.update(kw)

    def __repr__(self):
        return f"<{self.kind} {self.__dict__}>"


def parse_int(s):
    s = s.strip()
    m = re.fullmatch(r"([0-9A-Fa-f]+)[hH]", s)
    if m:
        return int(m.group(1), 16)
    return int(s, 0)


def parse_operand(text):
    t = text.strip()
    force = None
    m = re.match(r"(?i)^(byte|word)\s+(.*)$", t)
    if m:
        force = 8 if m.group(1).lower() == "byte" else 16
        t = m.group(2).strip()
    u = t.upper()
    if u in REG16:
        return Operand("reg16", reg=REG16[u], name=u)
    if u in REG8:
        return Operand("reg8", reg=REG8[u], name=u)
    if u in SREG:
        return Operand("sreg", reg=SREG[u], name=u)
    if u in ("CY", "DIR", "PSW", "R"):
        return Operand("special", name=u)
    if t.startswith("["):
        if not t.endswith("]"):
            raise AsmError(f"bad memory operand {text!r}")
        inner = t[1:-1]
        regs, disp = [], 0
        has_disp = False
        for part in re.split(r"[+]", inner):
            part = part.strip()
            pu = part.upper()
            if pu in ("BW", "BP", "IX", "IY"):
                regs.append(pu)
            else:
                disp += parse_int(part)
                has_disp = True
        key = tuple(sorted(regs, key=lambda r: (r not in ("BW", "BP"), r)))
        if not regs:
            return Operand("mem", direct=True, disp=disp, force=force)
        if key not in MEM_COMBO:
            raise AsmError(f"unencodable address {text!r}")
        return Operand("mem", direct=False, mem=MEM_COMBO[key], regs=key,
                       disp=disp, has_disp=has_disp, force=force)
    # far pointer seg:offset (both numeric)
    m = re.fullmatch(r"([^:\s]+)\s*:\s*([^:\s]+)", t)
    if m:
        try:
            return Operand("farptr", seg=parse_int(m.group(1)),
                           off=parse_int(m.group(2)))
        except ValueError:
            pass
    # immediate or label
    try:
        return Operand("imm", value=parse_int(t))
    except ValueError:
        return Operand("label", name=t)


#----------------------------------------------------------------------------
# encoding-form matching
#----------------------------------------------------------------------------

def atom_match(atom, op, mnemonic):
    """Does operand `op` satisfy pattern atom `atom`? Returns None or a
    weight (lower = more specific form, preferred)."""
    a = atom.strip()
    k = op.kind
    # literal atoms: a specific register or flag named in the form
    if a.upper() == getattr(op, "name", None):
        return 0
    if a == "reg" and k in ("reg8", "reg16"):
        return 2
    if a == "reg8" and k == "reg8":
        return 1
    if a in ("reg16", "regptr16") and k == "reg16":
        return 1
    if a == "sreg" and k == "sreg":
        return 1
    if a == "acc" and k in ("reg8", "reg16") and op.reg == 0:
        return 0
    if a in ("mem", "mem8", "mem16", "memptr16", "mem32", "memptr32") and k == "mem":
        return 2
    if a == "dmem" and k == "mem" and getattr(op, "direct", False):
        return 1
    if a in ("imm", "imm8", "imm16", "imm3", "imm4", "pop-value") and k == "imm":
        return 2
    if a == "1" and k == "imm" and op.value == 1:
        return 0
    if a == "CL" and k == "reg8" and op.reg == 1:
        return 0
    if a in ("far-label", "far-proc") and k == "farptr":
        return 1
    if a == "short-label" and k in ("label", "imm"):
        return 1
    if a in ("near-label", "near-proc") and k in ("label", "imm"):
        return 3      # prefer the short form when both exist
    return None


def op_width(pattern_atoms, ops):
    """Determine W (0=byte, 1=word) from the operands."""
    for a, op in zip(pattern_atoms, ops):
        if op.kind == "reg16":
            return 1
        if op.kind == "reg8":
            return 0
    for a, op in zip(pattern_atoms, ops):
        if op.kind == "mem" and getattr(op, "force", None):
            return 1 if op.force == 16 else 0
        if a.endswith("16"):
            return 1
        if a.endswith("8"):
            return 0
    return None


def norm_token(t):
    """Normalize encoding-byte templates against transcription noise."""
    t = t.strip()
    t = re.sub(r"imm8-?\s+or\s+imm16-low", "imm8 or imm16-low", t)
    t = re.sub(r"\s+", " ", t)
    return t


class Assembler:
    def __init__(self, facts=FACTS):
        db = json.load(open(facts))
        self.forms = {}
        for rec in db["instructions"]:
            rec = dict(rec)
            rec["encoding"] = [
                ("(" + norm_token(b.strip("()")) + ")") if b.startswith("(") else norm_token(b)
                for b in rec["encoding"]
            ]
            # dual-form headings ("XCH AW,reg16 / XCH reg16,AW") become
            # separate aliases sharing one encoding
            for form in rec["nec_form"].split(" / "):
                parts = form.split(None, 1)
                mnem = parts[0].upper()
                ops = parts[1] if len(parts) > 1 else ""
                if ops.startswith("(no operand)"):
                    ops = ""
                self.forms.setdefault(mnem, []).append((ops, rec))

    # ------------------------------------------------------------------
    def assemble(self, source, org=0):
        lines = self._parse_lines(source)
        # pass 1: sizes + labels (assemble with dummy label values)
        labels = {}
        for _pass in (1, 2):
            out = bytearray()
            pc = org
            for ln, kind, payload in lines:
                try:
                    if kind == "label":
                        labels[payload] = pc
                    elif kind == "org":
                        pc = payload
                    elif kind == "db":
                        vals = [self._val(v, labels, _pass) & 0xFF for v in payload]
                        out += bytes(vals); pc += len(vals)
                    elif kind == "dw":
                        for v in payload:
                            x = self._val(v, labels, _pass) & 0xFFFF
                            out += bytes((x & 0xFF, x >> 8)); pc += 2
                    else:
                        code = self._encode(payload, pc, labels, _pass)
                        out += code; pc += len(code)
                except AsmError as e:
                    raise AsmError(f"line {ln}: {e}") from None
        return bytes(out)

    def _parse_lines(self, source):
        lines = []
        for ln, raw in enumerate(source.splitlines(), 1):
            line = raw.split(";")[0].strip()
            if not line:
                continue
            m = re.match(r"^(\w+):\s*(.*)$", line)
            if m:
                lines.append((ln, "label", m.group(1)))
                line = m.group(2).strip()
                if not line:
                    continue
            m = re.match(r"(?i)^org\s+(.+)$", line)
            if m:
                lines.append((ln, "org", parse_int(m.group(1))))
                continue
            m = re.match(r"(?i)^d([bw])\s+(.+)$", line)
            if m:
                vals = [v.strip() for v in m.group(2).split(",")]
                lines.append((ln, "d" + m.group(1).lower(), vals))
                continue
            lines.append((ln, "insn", line))
        return lines

    def _val(self, v, labels, _pass):
        try:
            return parse_int(v)
        except ValueError:
            if v in labels:
                return labels[v]
            if _pass == 1:
                return 0
            raise AsmError(f"undefined symbol {v!r}")

    # ------------------------------------------------------------------
    def _encode(self, line, pc, labels, _pass):
        parts = line.split(None, 1)
        mnem = parts[0].upper()
        ops = []
        if len(parts) > 1:
            depth = 0
            cur = ""
            for ch in parts[1]:
                if ch == "," and depth == 0:
                    ops.append(parse_operand(cur)); cur = ""
                else:
                    if ch == "[":
                        depth += 1
                    elif ch == "]":
                        depth -= 1
                    cur += ch
            if cur.strip():
                ops.append(parse_operand(cur))
        if mnem not in self.forms:
            raise AsmError(f"unknown mnemonic {mnem!r}")

        # resolve labels to values for matching purposes
        for op in ops:
            if op.kind == "label":
                op.value = labels.get(op.name, 0) if _pass == 1 or op.name in labels \
                    else None
                if op.value is None:
                    raise AsmError(f"undefined symbol {op.name!r}")

        best = None
        for pattern, rec in self.forms[mnem]:
            atoms = [a for a in pattern.split(",") if a] if pattern else []
            if len(atoms) != len(ops):
                continue
            score = 0
            ok = True
            for a, op in zip(atoms, ops):
                w = atom_match(a, op, mnem)
                if w is None:
                    ok = False
                    break
                score += w
            if ok and (best is None or score < best[0]):
                best = (score, atoms, rec)
        if best is None:
            raise AsmError(f"no matching form for {line!r} "
                           f"(available: {[p for p, _ in self.forms[mnem]]})")
        _, atoms, rec = best
        try:
            return self._emit(rec, atoms, ops, pc)
        except AsmError as e:
            raise AsmError(f"{line!r}: {e}") from None

    # ------------------------------------------------------------------
    def _emit(self, rec, atoms, ops, pc):
        """Fill the encoding byte templates with field values."""
        # operand roles
        regop = next((o for o in ops if o.kind in ("reg8", "reg16")), None)
        sregop = next((o for o in ops if o.kind == "sreg"), None)
        memop = next((o for o in ops if o.kind == "mem"), None)
        immop = None
        for a, o in zip(atoms, ops):
            if o.kind in ("imm", "label") and a not in ("1", "CL"):
                immop = (a, o)
        # for reg,reg forms the second reg goes into the mem/rm slot;
        # operands matched by a literal atom (e.g. the implied AW in
        # "XCH AW,reg16") do not occupy an encoding field
        regs = [o for a, o in zip(atoms, ops)
                if o.kind in ("reg8", "reg16")
                and a.strip().upper() != getattr(o, "name", None)]
        if regop is not None and regop not in regs:
            regop = regs[0] if regs else None
        w = op_width(atoms, ops)

        # instruction length estimate for PC-relative operands: computed
        # after emission; use two-step emit with placeholder then patch
        body = bytearray()
        pending_rel = None   # (pos, size, atom)

        mod = mem = None
        disp_bytes = b""
        if memop is not None:
            if memop.direct:
                mod, mem = 0, 6
                disp_bytes = bytes((memop.disp & 0xFF, (memop.disp >> 8) & 0xFF))
            else:
                d = memop.disp
                if d == 0 and not (memop.mem == 6 and len(memop.regs) == 1):
                    mod, disp_bytes = 0, b""
                elif -128 <= d <= 127:
                    mod, disp_bytes = 1, bytes((d & 0xFF,))
                else:
                    mod, disp_bytes = 2, bytes((d & 0xFF, (d >> 8) & 0xFF))
                mem = memop.mem

        imm_s = 0
        if immop and "S" in rec["encoding"][0]:
            a, o = immop
            v = o.value
            if w == 1 and -128 <= ((v ^ 0x8000) - 0x8000 if v > 0x7FFF else v) <= 127:
                imm_s = 1

        for tmpl in rec["encoding"]:
            optional = tmpl.startswith("(") and tmpl.endswith(")")
            t = tmpl.strip("()")

            if t in ("disp-low", "disp-high") and optional and memop is not None:
                continue    # modrm displacement, handled with the modrm byte
            if t == "disp8":
                body.append(0)
                pending_rel = (len(body) - 1, 1)
                continue
            if t in ("disp-low", "disp-high"):
                # 16-bit PC-relative (BR near-label / CALL near-proc); the
                # manual parenthesizes these in some entries
                if t == "disp-low":
                    body += b"\x00\x00"
                    pending_rel = (len(body) - 2, 2)
                continue
            if t in ("addr-low",):
                body.append(memop.disp & 0xFF)
                continue
            if t in ("addr-high",):
                body.append((memop.disp >> 8) & 0xFF)
                continue
            if t in ("offset-low", "offset-high", "seg-low", "seg-high"):
                fp = next(o for o in ops if o.kind == "farptr")
                v = {"offset-low": fp.off, "offset-high": fp.off >> 8,
                     "seg-low": fp.seg, "seg-high": fp.seg >> 8}[t]
                body.append(v & 0xFF)
                continue
            if t == "imm3" or t == "imm4":
                body.append(immop[1].value & 0xFF)
                continue
            if t == "imm8":
                body.append(immop[1].value & 0xFF)
                continue
            if t == "imm8 or imm16-low":
                v = immop[1].value
                body.append(v & 0xFF)
                if w == 1 and not imm_s and "imm16-high" not in \
                        [x.strip("()") for x in rec["encoding"]]:
                    body.append((v >> 8) & 0xFF)
                continue
            if t == "imm16-low":
                body.append(immop[1].value & 0xFF)
                continue
            if t == "imm16-high":
                if imm_s or (w == 0):
                    continue
                body.append((immop[1].value >> 8) & 0xFF)
                continue
            if t in ("pop-value-low",):
                body.append(immop[1].value & 0xFF); continue
            if t in ("pop-value-high",):
                body.append((immop[1].value >> 8) & 0xFF); continue

            # generic bit-field byte
            byte, nbits = 0, 0
            fields = t.split()
            reg_used = 0
            for f in fields:
                if re.fullmatch(r"[01SW]+", f):
                    for ch in f:
                        bit = {"0": 0, "1": 1,
                               "W": w if w is not None else 0,
                               "S": imm_s}[ch]
                        byte = (byte << 1) | bit
                        nbits += 1
                elif f == "mod":
                    if mod is None:
                        # register form of a mem-capable encoding
                        byte = (byte << 2) | 3; nbits += 2
                    else:
                        byte = (byte << 2) | mod; nbits += 2
                elif f == "mem":
                    if mem is None:
                        byte = (byte << 3) | (regs[-1].reg if regs else 0)
                        nbits += 3
                    else:
                        byte = (byte << 3) | mem; nbits += 3
                elif f == "reg":
                    src = regs[reg_used] if reg_used < len(regs) else regop
                    if src is None:
                        raise AsmError(f"no register for field in {t!r}")
                    byte = (byte << 3) | src.reg; nbits += 3
                    reg_used += 1
                elif f == "sreg":
                    byte = (byte << 2) | sregop.reg; nbits += 2
                else:
                    raise AsmError(f"unsupported encoding field {f!r} in {t!r}")
            if nbits != 8:
                raise AsmError(f"field widths sum to {nbits} in {t!r}")
            body.append(byte)
            # modrm byte: displacement follows immediately
            if "mod" in fields and disp_bytes and mod in (1, 2) or \
               ("mod" in fields and mod == 0 and mem == 6):
                body += disp_bytes
                disp_bytes = b""

        if pending_rel:
            pos, size = pending_rel
            target = immop[1].value
            rel = target - (pc + len(body))
            if size == 1:
                if not -128 <= rel <= 127:
                    raise AsmError(f"short branch out of range ({rel})")
                body[pos] = rel & 0xFF
            else:
                body[pos] = rel & 0xFF
                body[pos + 1] = (rel >> 8) & 0xFF
        return bytes(body)


#----------------------------------------------------------------------------
def build_image(code, org, size=0x10000, entry_seg=0x0000, entry_off=None,
                fill=0x90):
    """64 KB memory image: program at org, far jump at the reset vector."""
    img = bytearray([fill]) * 1
    img = bytearray([fill]) * size
    img[org:org + len(code)] = code
    if entry_off is None:
        entry_off = org
    vec = bytes([0xEA, entry_off & 0xFF, entry_off >> 8,
                 entry_seg & 0xFF, entry_seg >> 8])
    img[0xFFF0:0xFFF0 + len(vec)] = vec
    return bytes(img)


BRINGUP = """
    org 0x100
start:
    MOV AW, 1234h
    MOV BW, 2000h
    MOV [BW], AW
    MOV AL, [2000h]
    MOV AW, [2001h]
    NOP
    BR start
"""

def selftest():
    a = Assembler()
    code = a.assemble(BRINGUP, org=0x100)
    expect = bytes([
        0xB8, 0x34, 0x12,
        0xBB, 0x00, 0x20,
        0x89, 0x07,
        0xA0, 0x00, 0x20,
        0xA1, 0x01, 0x20,
        0x90,
        0xEB, 0xEF,
    ])
    ok = True
    if code != expect:
        ok = False
        print("bring-up mismatch:")
        print("  got   ", code.hex(" "))
        print("  expect", expect.hex(" "))
    cases = [
        ("MOV CW, 5", "b9 05 00"),
        ("ADD AL, 7", "04 07"),
        ("ADD BW, 200h", "81 c3 00 02"),
        ("ADD BW, 4", "83 c3 04"),
        ("SUB AW, [BW+IX]", "2b 00"),
        ("CMP byte [0x3000], 1", "80 3e 00 30 01"),
        ("INC IY", "47"),
        ("DEC CL", "fe c9"),
        ("PUSH BW", "53"),
        ("POP DS0", "1f"),
        ("XCH AW, BW", "93"),
        ("HALT", "f4"),
        ("EI", "fb"),
        ("SHL AL, 1", "d0 e0"),
        ("SHL AW, CL", "d3 e0"),
        ("MULU CL", "f6 e1"),
        ("DIV CW", "f7 f9"),
        ("TEST1 AL, 3", "0f 18 c0 03"),
        ("NOT1 CY", "f5"),
        ("MOV AH, PSW", "9f"),
    ]
    for src, want in cases:
        try:
            got = a.assemble(src).hex(" ")
        except AsmError as e:
            got = f"ERROR: {e}"
        if got != want:
            ok = False
            print(f"MISMATCH {src!r}: got {got}, want {want}")
    print("SELFTEST PASSED" if ok else "SELFTEST FAILED")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source", nargs="?")
    ap.add_argument("-o", "--out", default="a.bin")
    ap.add_argument("--org", type=lambda x: int(x, 0), default=0x100)
    ap.add_argument("--image", action="store_true",
                    help="emit a 64 KB boot image instead of raw code")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        sys.exit(selftest())
    if not args.source:
        ap.error("source file required")
    a = Assembler()
    code = a.assemble(open(args.source).read(), org=args.org)
    data = build_image(code, args.org) if args.image else code
    Path(args.out).write_bytes(data)
    print(f"wrote {len(data)} bytes to {args.out}")


if __name__ == "__main__":
    main()
