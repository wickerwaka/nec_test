#!/usr/bin/env python3
"""testimage - compose per-test 64 KB memory images for the V30 harness.

Implements docs/notes/loadstore_design.md: a reserved page at 0xFF00-0xFFFF
holds the register load routine, the store-main routine, the scratch stack,
the PSW injection word, and the reset vector. The test instruction and a
17-byte store stub live in test-owned space.

Register injection order and store word order are fixed contracts shared
with v30run.py's trace parser.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from v30asm import Assembler, AsmError  # noqa: E402

LOAD_AT       = 0xFF00
STORE_MAIN_AT = 0xFF40
SCRATCH_SP    = 0xFFEE    # POP PSW reads FFEE/FFEF; PUSH PSW writes FFEC/FFED
PSW_IMAGE_AT  = 0xFFEE
PSW_PUSH_AT   = 0xFFEC
VECTOR_AT     = 0xFFF0
RESERVED      = range(0xFF00, 0x10000)

# both ports even: word OUT to an odd port splits into two byte cycles and
# the second half would land on the neighboring port (measured on silicon)
OUT_PORT_REGS = 0xFE
OUT_PORT_DONE = 0xFC
DONE_SENTINEL = 0xF00D

# store word order at port 0xFE (contract with the parser)
STORE_ORDER = ["AW", "PS", "SS", "SP", "DS0", "DS1", "BW", "CW", "DW",
               "BP", "IX", "IY"]

REG_DEFAULTS = {
    "AW": 0, "BW": 0, "CW": 0, "DW": 0, "SP": 0, "BP": 0, "IX": 0, "IY": 0,
    "DS0": 0, "DS1": 0, "SS": 0, "PS": 0, "PC": 0x0100, "PSW": 0x0002,
}


def normalize_psw(v):
    """V30 PSW: force MD=1 + reserved 14-12=1, bit1=1; clear 5,3; never TF."""
    return (v & 0x0ED5) | 0xF002


def load_routine(regs):
    """Register injection; AW is the segment shuttle and is loaded last.
    The terminal far jump sets PS:PC and flushes the queue (test anchor)."""
    return f"""
    MOV AW, 0
    MOV SS, AW
    MOV SP, 0x{SCRATCH_SP:04X}
    POP PSW
    MOV AW, 0x{regs['SS']:04X}
    MOV SS, AW
    MOV SP, 0x{regs['SP']:04X}
    MOV AW, 0x{regs['DS0']:04X}
    MOV DS0, AW
    MOV AW, 0x{regs['DS1']:04X}
    MOV DS1, AW
    MOV BW, 0x{regs['BW']:04X}
    MOV CW, 0x{regs['CW']:04X}
    MOV DW, 0x{regs['DW']:04X}
    MOV BP, 0x{regs['BP']:04X}
    MOV IX, 0x{regs['IX']:04X}
    MOV IY, 0x{regs['IY']:04X}
    MOV AW, 0x{regs['AW']:04X}
    BR 0x{regs['PS']:04X}:0x{regs['PC']:04X}
"""


STORE_STUB = f"""
    NOP
    NOP
    NOP
    NOP
    NOP
    NOP
    OUT 0x{OUT_PORT_REGS:02X}, AW
    MOV AW, PS
    OUT 0x{OUT_PORT_REGS:02X}, AW
    BR 0x0000:0x{STORE_MAIN_AT:04X}
"""

STORE_MAIN = f"""
    MOV AW, SS
    OUT 0x{OUT_PORT_REGS:02X}, AW
    MOV AW, SP
    OUT 0x{OUT_PORT_REGS:02X}, AW
    MOV AW, 0
    MOV SS, AW
    MOV SP, 0x{SCRATCH_SP:04X}
    PUSH PSW
    MOV AW, DS0
    OUT 0x{OUT_PORT_REGS:02X}, AW
    MOV AW, DS1
    OUT 0x{OUT_PORT_REGS:02X}, AW
    MOV AW, BW
    OUT 0x{OUT_PORT_REGS:02X}, AW
    MOV AW, CW
    OUT 0x{OUT_PORT_REGS:02X}, AW
    MOV AW, DW
    OUT 0x{OUT_PORT_REGS:02X}, AW
    MOV AW, BP
    OUT 0x{OUT_PORT_REGS:02X}, AW
    MOV AW, IX
    OUT 0x{OUT_PORT_REGS:02X}, AW
    MOV AW, IY
    OUT 0x{OUT_PORT_REGS:02X}, AW
    MOV AW, 0x{DONE_SENTINEL:04X}
    OUT 0x{OUT_PORT_DONE:02X}, AW
    HALT
"""


class ComposeError(Exception):
    pass


def compose(regs=None, instr=b"", stub_linear=None, ivt=None, ram=None,
            fill=0x90):
    """Build a 64 KB test image.

    regs: register values (defaults + overrides); PSW normalized here.
    instr: test instruction bytes placed at linear (PS*16+PC) mod 64K.
           Empty = register echo test (stub sits at the anchor itself).
    stub_linear: where the store stub goes; default = fall-through
                 continuation (anchor + len(instr)).
    ivt: {vector_number: (seg, off)} entries to compose.

    Returns (image: bytes, meta: dict) — meta carries the anchors the
    parser needs.
    """
    r = dict(REG_DEFAULTS)
    if regs:
        r.update(regs)
    r["PSW"] = normalize_psw(r["PSW"])

    a = Assembler()
    img = bytearray([fill]) * 0x10000

    load = a.assemble(load_routine(r), org=LOAD_AT)
    if LOAD_AT + len(load) > STORE_MAIN_AT:
        raise ComposeError(f"load routine too long ({len(load)})")
    img[LOAD_AT:LOAD_AT + len(load)] = load

    main = a.assemble(STORE_MAIN, org=STORE_MAIN_AT)
    if STORE_MAIN_AT + len(main) > 0xFFC0:
        raise ComposeError(f"store main too long ({len(main)})")
    img[STORE_MAIN_AT:STORE_MAIN_AT + len(main)] = main

    img[PSW_IMAGE_AT] = r["PSW"] & 0xFF
    img[PSW_IMAGE_AT + 1] = r["PSW"] >> 8

    vec = a.assemble(f"BR 0x0000:0x{LOAD_AT:04X}", org=VECTOR_AT)
    img[VECTOR_AT:VECTOR_AT + len(vec)] = vec

    # extra RAM placements (20-bit linear addresses, e.g. from a V20 suite
    # test case); reject aliasing collisions in the 64K-mirrored space
    if ram:
        seen = {}
        for addr, val in ram:
            phys = addr & 0xFFFF
            if phys in RESERVED:
                raise ComposeError(f"ram byte at {addr:05x} hits reserved page")
            if phys in seen and seen[phys] != (addr, val):
                pa, pv = seen[phys]
                if pa != addr:
                    raise ComposeError(
                        f"mirror alias: {pa:05x} and {addr:05x} both map to "
                        f"{phys:04x}")
            seen[phys] = (addr, val)
            img[phys] = val & 0xFF

    anchor = ((r["PS"] << 4) + r["PC"]) & 0xFFFFF
    anchor_phys = anchor & 0xFFFF
    if stub_linear is None:
        stub_linear = (anchor_phys + len(instr)) & 0xFFFF

    stub = a.assemble(STORE_STUB, org=stub_linear)

    # footprint/collision checks (design section 1)
    footprint = set(range(anchor_phys, anchor_phys + len(instr))) | \
        set(range(stub_linear, stub_linear + len(stub)))
    if ivt:
        for n in ivt:
            footprint |= set(range(4 * n, 4 * n + 4))
    if any(p in RESERVED for p in footprint):
        raise ComposeError("test footprint intersects the reserved page")
    if len(footprint) != len(instr) + len(stub) + (4 * len(ivt) if ivt else 0):
        raise ComposeError("footprint overlap (instr/stub/ivt collide)")

    img[anchor_phys:anchor_phys + len(instr)] = instr
    img[stub_linear:stub_linear + len(stub)] = stub

    if ivt:
        for n, (seg, off) in ivt.items():
            img[4 * n:4 * n + 4] = bytes((off & 0xFF, off >> 8,
                                          seg & 0xFF, seg >> 8))

    meta = {
        "regs_in": r,
        "anchor_linear": anchor,
        "anchor_phys": anchor_phys,
        "stub_linear": stub_linear,
        "instr_len": len(instr),
        "store_order": STORE_ORDER,
        "psw_push_addr": PSW_PUSH_AT,
        "done_sentinel": DONE_SENTINEL,
    }
    return bytes(img), meta


if __name__ == "__main__":
    img, meta = compose(regs={"AW": 0x1111, "BW": 0x2222})
    print(f"composed {len(img)} bytes; meta: {meta}")
