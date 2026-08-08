#!/usr/bin/env python3
"""testimage - compose per-test 64 KB memory images for the V30 harness.

FUZZ v2 IMAGE (compose_ver 2).  The v1 shape -- a test instruction with a
fall-through store stub at `stub_linear` and the PSW recovered from a
`MEMW @ 0xFFEC` -- IS GONE.  What replaces it:

  * a power-of-two-aligned CODE REGION (0x8000-0xBFFF, 16 KB) holding the
    fuzz body at the anchor, an 8 x 32-byte interrupt modification-handler
    table, and the termination handler + dump tail;
  * `0xCC` (INT3) fill everywhere in the image except four carve-outs --
    IVT, data window, stack region, loader page -- so ANY escape, at any
    alignment, executes a one-byte INT3 and vectors to TERM_AT.  Vector 3
    is composed by this module and is not the caller's to set;
  * a termination handler that POPS ITS OWN INTERRUPT FRAME and emits
    IP/CS/FLAGS as ordinary `OUT 0xFE` words.  Interrupt entry clears IE
    and BRK in hardware, so a `PUSH PSW` inside a handler reports
    IE=0/TF=0 always; the frame is the only place the pre-trap bits
    survive.  Popping first also makes the handler correct wherever the
    frame landed, which is the mitigation for a wild SP.

The reserved loader page (0xFF00-0xFFFF) is unchanged in role: register
load routine, scratch stack, PSW injection word, reset vector.

Register injection order and the 15-name store word order (STORE_ORDER)
are fixed contracts shared with the trace parsers.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from v30asm import Assembler, AsmError  # noqa: E402

COMPOSE_VER = 2

# --------------------------------------------------------------------------- #
# loader page (unchanged from v1 apart from STORE_MAIN, which is retired)
# --------------------------------------------------------------------------- #
LOAD_AT       = 0xFF00
LOAD_LIMIT    = 0xFFC0    # load routine must end here (scratch-stack headroom)
SCRATCH_SP    = 0xFFEE    # POP PSW reads FFEE/FFEF
PSW_IMAGE_AT  = 0xFFEE
VECTOR_AT     = 0xFFF0
RESERVED      = range(0xFF00, 0x10000)

# --------------------------------------------------------------------------- #
# THE CODE REGION.
#
# 16 KB at 0x8000.  Why this block and this size:
#   * it is the LARGEST power-of-two-aligned block that clears every carve-out
#     (IVT 0x0000-03FF, data 0x2000-2FFF, stack 0x3000-3FFF, loader 0xFF00-FFFF).
#     0x8000-0xFFFF (32 KB) would swallow the loader page; 0x4000-0xBFFF is not
#     32 KB-aligned.  So 16 KB is the ceiling, and there is no cost to taking it.
#   * "inside the code region" is `addr[15:14] == 2'b10` -- a two-bit test, which
#     is what the plan's optional hardware prefetch mask would have to decode.
#   * 16 KB of 0xCC between the body and the fixed structures means a runaway
#     traps long before it can reach them.
# --------------------------------------------------------------------------- #
CODE_LO   = 0x8000
CODE_SIZE = 0x4000
CODE_HI   = CODE_LO + CODE_SIZE          # exclusive
CODE_FILL = 0xCC                         # INT3

IHT_N      = 8                           # interrupt modification-handler bodies
IHT_STRIDE = 32
IHT_AT     = CODE_HI - 0x0200            # 0xBE00 .. 0xBEFF
TERM_AT    = CODE_HI - 0x0100            # 0xBF00 -- the TVEC target
ANCHOR0    = CODE_LO + 0x0100            # default body anchor (0xCC apron below)

# carve-outs: filled with `fill`, never with 0xCC
IVT_REGION    = range(0x0000, 0x0400)
DATA_REGION   = range(0x2000, 0x3000)    # incl. the IX/IY string bands
STACK_REGION  = range(0x3000, 0x4000)
LOADER_REGION = RESERVED
CARVE_OUTS = (IVT_REGION, DATA_REGION, STACK_REGION, LOADER_REGION)

TERM_VECTOR = 3                          # INT3, reached from the 0xCC fill

# both ports even: word OUT to an odd port splits into two byte cycles and
# the second half would land on the neighboring port (measured on silicon)
OUT_PORT_REGS = 0xFE
OUT_PORT_DONE = 0xFC
DONE_SENTINEL = 0xF00D
MAGIC         = 0x5EED   # dump anchor; index 1 of STORE_ORDER

# store word order at port 0xFE (contract with the parsers).  AW precedes
# MAGIC because AW is the segment shuttle and must be emitted before it is
# used.  PC/PS/PSW are the popped interrupt frame, in hardware push order.
STORE_ORDER = ["AW", "MAGIC", "PC", "PS", "PSW", "SS", "SP", "DS0", "DS1",
               "BW", "CW", "DW", "BP", "IX", "IY"]

# the 8086/V30 interrupt frame, top of stack first
FRAME_ORDER = ("PC", "PS", "PSW")

REG_DEFAULTS = {
    "AW": 0, "BW": 0, "CW": 0, "DW": 0, "SP": 0x3F00, "BP": 0, "IX": 0,
    "IY": 0, "DS0": 0, "DS1": 0, "SS": 0,
    "PS": CODE_LO >> 4, "PC": ANCHOR0 - CODE_LO, "PSW": 0x0202,
}

# structural invariants of the map, checked once at import
assert CODE_SIZE and (CODE_SIZE & (CODE_SIZE - 1)) == 0, "code region not 2^n"
assert CODE_LO % CODE_SIZE == 0, "code region not naturally aligned"
assert CODE_HI <= 0x10000
for _rg in CARVE_OUTS:
    assert _rg.start >= CODE_HI or _rg.stop <= CODE_LO, \
        f"carve-out {_rg} intersects the code region"
assert CODE_LO <= IHT_AT and IHT_AT + IHT_N * IHT_STRIDE <= TERM_AT
assert TERM_AT < CODE_HI
assert ((REG_DEFAULTS["PS"] << 4) + REG_DEFAULTS["PC"]) == ANCHOR0


def normalize_psw(v):
    """V30 PSW: force MD=1 + reserved 14-12=1, bit1=1, IE=1; clear 5,3;
    never TF.

    IE is FORCED (v2): a randomized PSW that arrives with interrupts masked
    makes the external INT event a no-op, so the INT axis would silently
    stop being exercised."""
    return (v & 0x0ED5) | 0xF202


def load_routine(regs):
    """Register injection; AW is the segment shuttle and is loaded last.
    The terminal far jump sets PS:PC and flushes the queue (test anchor).

    STRUCTURE IS FROZEN -- only the 13 imm16 values move.  `_build_load_template`
    locates them by unique byte-pair search; adding a constant that collides with
    a sentinel silently drops compose onto the ~7 ms assembler path."""
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


# --------------------------------------------------------------------------- #
# THE TERMINATION HANDLER.
#
# Entered two ways, identically: INT3 from the 0xCC fill (vector 3) and the
# harness-intercepted NMI (the host programs TERM_AT into the rig's TVEC).
# Both push the same 3-word frame, so there is one entry path and no test.
#
# It must NOT `IRET` -- the pushed frame points back into the seed.
#
# Split in two only so the map's two named parts have their own byte lengths.
# Neither half contains a label, a branch or an absolute address, so both are
# position-independent and their concatenation is byte-identical to assembling
# the joined source (asserted below).
# --------------------------------------------------------------------------- #
TERM_HANDLER = f"""
    OUT 0x{OUT_PORT_REGS:02X}, AW
    MOV AW, 0x{MAGIC:04X}
    OUT 0x{OUT_PORT_REGS:02X}, AW
    POP AW
    OUT 0x{OUT_PORT_REGS:02X}, AW
    POP AW
    OUT 0x{OUT_PORT_REGS:02X}, AW
    POP AW
    OUT 0x{OUT_PORT_REGS:02X}, AW
"""

DUMP_TAIL = f"""
    MOV AW, SS
    OUT 0x{OUT_PORT_REGS:02X}, AW
    MOV AW, SP
    OUT 0x{OUT_PORT_REGS:02X}, AW
    MOV AW, 0
    MOV SS, AW
    MOV SP, 0x{SCRATCH_SP:04X}
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

# an unfilled handler slot is a bare IRET; compose appends IRET to every body
# so a handler can never fall out of its slot
IRET_BYTE = 0xCF


class ComposeError(Exception):
    pass


# --- Path A / F: pre-assembled compose templates. The load routine varies ONLY
# in 13 imm16 constants at fixed byte offsets; the terminator halves are
# org-independent byte constants. Assembling once and patching drops compose
# from ~7 ms to <1 ms.  A failed template build falls back to the assembler
# path transparently.
_LOAD_PATCH_KEYS = ('SS', 'SP', 'DS0', 'DS1', 'BW', 'CW', 'DW', 'BP',
                    'IX', 'IY', 'AW', 'PS', 'PC')


def _build_load_template():
    sent = {'SS': 0x1101, 'SP': 0x2202, 'DS0': 0x3303, 'DS1': 0x4404,
            'BW': 0x5505, 'CW': 0x6606, 'DW': 0x7707, 'BP': 0x8808,
            'IX': 0x9909, 'IY': 0xAA0A, 'AW': 0xBB0B, 'PS': 0xCC0C, 'PC': 0xDD0D}
    r = dict(REG_DEFAULTS)
    r.update(sent)
    try:
        tmpl = bytearray(Assembler().assemble(load_routine(r), org=LOAD_AT))
    except AsmError:
        return None, None
    offs = {}
    for k, v in sent.items():
        pat = bytes([v & 0xFF, v >> 8])
        i = tmpl.find(pat)
        if i < 0 or tmpl.find(pat, i + 1) != -1:
            return None, None          # not uniquely locatable -> slow path
        offs[k] = i
    return bytes(tmpl), offs


_LOAD_TMPL, _LOAD_OFFS = _build_load_template()
try:
    _TERM_HEAD = bytes(Assembler().assemble(TERM_HANDLER, org=TERM_AT))
    _TERM_TAIL = bytes(Assembler().assemble(DUMP_TAIL,
                                            org=TERM_AT + len(_TERM_HEAD)))
    _TERM = _TERM_HEAD + _TERM_TAIL
    _VECTOR = bytes(Assembler().assemble(f"BR 0x0000:0x{LOAD_AT:04X}", org=VECTOR_AT))
except AsmError:
    _TERM_HEAD = _TERM_TAIL = _TERM = _VECTOR = None

_FAST_OK = _LOAD_TMPL is not None and _TERM is not None


def _fast_load(r):
    buf = bytearray(_LOAD_TMPL)
    for k in _LOAD_PATCH_KEYS:
        v = r[k] & 0xFFFF
        o = _LOAD_OFFS[k]
        buf[o] = v & 0xFF
        buf[o + 1] = v >> 8
    return buf


# --------------------------------------------------------------------------- #
# Emission-order falsifier.  Decodes the assembled terminator and recovers the
# sequence of words actually written to port 0xFE.  If this ever disagrees with
# STORE_ORDER every register in every dump is silently mislabelled, so it is an
# import-time assertion rather than a test.
# --------------------------------------------------------------------------- #
_R16 = ("AW", "CW", "DW", "BW", "SP", "BP", "IX", "IY")
_SREG = {0xC0: "DS1", 0xC8: "PS", 0xD0: "SS", 0xD8: "DS0"}


def emitted_order(blob):
    """(names written to OUT_PORT_REGS, value written to OUT_PORT_DONE).

    Frame pops are reported as FRAME_ORDER[n] for the n-th POP AW, which is
    the hardware push order (IP, CS, FLAGS), not an assumption about this
    routine."""
    out, done, aw, pops, i = [], None, None, 0, 0
    while i < len(blob):
        b = blob[i]
        if b == 0xE7:                                   # OUT imm8, AW
            port = blob[i + 1]
            if port == OUT_PORT_REGS:
                out.append(aw)
            elif port == OUT_PORT_DONE:
                done = aw
            else:
                raise ComposeError(f"terminator OUTs to port {port:#04x}")
            i += 2
        elif b == 0x58:                                 # POP AW
            aw = FRAME_ORDER[pops] if pops < len(FRAME_ORDER) else f"POP{pops}"
            pops += 1
            i += 1
        elif b == 0xB8:                                 # MOV AW, imm16
            v = blob[i + 1] | (blob[i + 2] << 8)
            aw = "MAGIC" if v == MAGIC else v
            i += 3
        elif b == 0x8B and (blob[i + 1] & 0xF8) == 0xC0:   # MOV AW, r16
            aw = _R16[blob[i + 1] & 7]
            i += 2
        elif b == 0x8C and blob[i + 1] in _SREG:           # MOV AW, sreg
            aw = _SREG[blob[i + 1]]
            i += 2
        elif b == 0x8E:                                 # MOV sreg, AW
            i += 2
        elif b == 0xBC:                                 # MOV SP, imm16
            i += 3
        elif b == 0xF4:                                 # HALT
            i += 1
        else:
            raise ComposeError(f"terminator byte {b:#04x} at +{i} not decodable")
    return out, done


if _FAST_OK:
    _emit, _done = emitted_order(_TERM)
    # AW is emitted before it is ever loaded: index 0 decodes as None
    assert _emit[0] is None and STORE_ORDER[0] == "AW", \
        f"terminator does not emit the entry AW first: {_emit[:2]}"
    assert _emit[1:] == STORE_ORDER[1:], \
        f"emission order {_emit} != STORE_ORDER {STORE_ORDER}"
    assert _done == DONE_SENTINEL, f"done marker {_done!r}"
    # the two halves really are position-independent
    assert bytes(Assembler().assemble(TERM_HANDLER + DUMP_TAIL,
                                      org=TERM_AT)) == _TERM, \
        "TERM_HANDLER/DUMP_TAIL are not position-independent"
    assert TERM_AT + len(_TERM) <= CODE_HI, "terminator overruns the code region"


def _in_code(lo, n):
    return CODE_LO <= lo and lo + n <= CODE_HI


def compose(regs=None, instr=b"", ivt=None, ram=None, handlers=None,
            fill=0x90):
    """Build a 64 KB v2 test image.

    regs:     register values (defaults + overrides); PSW normalized here.
    instr:    fuzz body bytes, placed at linear (PS*16+PC) mod 64K, which
              MUST lie wholly inside the code region.
    ivt:      {vector: (seg, off)} entries to compose.  Vector 3 is composed
              by this function (-> TERM_AT) and passing it raises.
    ram:      [(linear, byte)] extra placements; 64K-mirror aliases rejected.
    handlers: up to IHT_N interrupt modification-handler bodies, each at most
              IHT_STRIDE-1 bytes.  compose appends IRET to every slot, so a
              body cannot fall out of its slot.  None -> all slots bare IRET.
    fill:     the byte used for the four carve-outs.  Everything else in the
              image is CODE_FILL (0xCC = INT3).

    Returns (image: bytes, meta: dict).
    """
    r = dict(REG_DEFAULTS)
    if regs:
        r.update(regs)
    r["PSW"] = normalize_psw(r["PSW"])

    # ---- fill: 0xCC everywhere, `fill` in the four carve-outs -------------
    img = bytearray([CODE_FILL]) * 0x10000
    for rg in CARVE_OUTS:
        img[rg.start:rg.stop] = bytes([fill]) * (rg.stop - rg.start)

    # ---- loader page -------------------------------------------------------
    if _FAST_OK:
        load = _fast_load(r)          # template-patch (proven byte-identical)
        term = _TERM
        vec = _VECTOR
    else:
        a = Assembler()
        load = a.assemble(load_routine(r), org=LOAD_AT)
        term = a.assemble(TERM_HANDLER + DUMP_TAIL, org=TERM_AT)
        vec = a.assemble(f"BR 0x0000:0x{LOAD_AT:04X}", org=VECTOR_AT)
    if LOAD_AT + len(load) > LOAD_LIMIT:
        raise ComposeError(f"load routine too long ({len(load)})")
    img[LOAD_AT:LOAD_AT + len(load)] = load

    img[PSW_IMAGE_AT] = r["PSW"] & 0xFF
    img[PSW_IMAGE_AT + 1] = r["PSW"] >> 8
    img[VECTOR_AT:VECTOR_AT + len(vec)] = vec

    # ---- code region: terminator + handler table ---------------------------
    img[TERM_AT:TERM_AT + len(term)] = term

    hs = list(handlers) if handlers else []
    if len(hs) > IHT_N:
        raise ComposeError(f"{len(hs)} handler bodies > IHT_N ({IHT_N})")
    for i in range(IHT_N):
        body = bytes(hs[i]) if i < len(hs) else b""
        if len(body) > IHT_STRIDE - 1:
            raise ComposeError(
                f"handler {i} is {len(body)} bytes, slot is {IHT_STRIDE - 1}+IRET")
        slot = IHT_AT + i * IHT_STRIDE
        img[slot:slot + len(body)] = body
        img[slot + len(body)] = IRET_BYTE

    # ---- extra RAM placements (20-bit linear); reject mirror aliases -------
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

    # ---- the body ----------------------------------------------------------
    anchor = ((r["PS"] << 4) + r["PC"]) & 0xFFFFF
    anchor_phys = anchor & 0xFFFF
    if not _in_code(anchor_phys, len(instr)):
        raise ComposeError(
            f"body [{anchor_phys:04x},{anchor_phys + len(instr):04x}) is not "
            f"inside the code region [{CODE_LO:04x},{CODE_HI:04x})")

    # ---- footprint/collision checks (design section 1) ---------------------
    if ivt and TERM_VECTOR in ivt:
        raise ComposeError(
            f"vector {TERM_VECTOR} is composed by testimage (-> {TERM_AT:04x}); "
            "the caller must not set it")
    vecs = dict(ivt) if ivt else {}
    vecs[TERM_VECTOR] = (0x0000, TERM_AT)

    iht_span = set(range(IHT_AT, IHT_AT + IHT_N * IHT_STRIDE))
    footprint = set(range(anchor_phys, anchor_phys + len(instr))) | \
        set(range(TERM_AT, TERM_AT + len(term))) | iht_span
    for n in vecs:
        footprint |= set(range(4 * n, 4 * n + 4))
    if any(p in RESERVED for p in footprint):
        raise ComposeError("test footprint intersects the reserved page")
    if len(footprint) != (len(instr) + len(term) + len(iht_span)
                          + 4 * len(vecs)):
        raise ComposeError("footprint overlap (body/terminator/table/ivt collide)")

    img[anchor_phys:anchor_phys + len(instr)] = instr

    for n, (seg, off) in vecs.items():
        img[4 * n:4 * n + 4] = bytes((off & 0xFF, off >> 8,
                                      seg & 0xFF, seg >> 8))

    meta = {
        "compose_ver": COMPOSE_VER,
        "regs_in": r,
        "anchor_linear": anchor,
        "anchor_phys": anchor_phys,
        "instr_len": len(instr),
        "store_order": STORE_ORDER,
        "magic": MAGIC,
        "done_sentinel": DONE_SENTINEL,
        "code_lo": CODE_LO,
        "code_hi": CODE_HI,
        "code_fill": CODE_FILL,
        "term_at": TERM_AT,
        "term_len": len(term),
        "iht_at": IHT_AT,
        "iht_n": IHT_N,
        "iht_stride": IHT_STRIDE,
        "term_vector": TERM_VECTOR,
    }
    return bytes(img), meta


# --------------------------------------------------------------------------- #
def _selfcheck():
    """Round-trip: every declared region contains what compose intended."""
    ok = True

    def chk(name, cond, detail=""):
        nonlocal ok
        ok = ok and cond
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}{(' ' + detail) if detail else ''}")

    print(f"compose_ver          {COMPOSE_VER}")
    print(f"_LOAD_TMPL           {'not None' if _LOAD_TMPL is not None else 'None'}"
          f" ({len(_LOAD_TMPL) if _LOAD_TMPL else 0} bytes, "
          f"{len(_LOAD_OFFS or ())} patch slots)")
    print(f"code region          [{CODE_LO:04X},{CODE_HI:04X}) "
          f"= {CODE_SIZE} bytes, fill {CODE_FILL:#04x}")
    print(f"TERM_HANDLER         @ {TERM_AT:04X}  {len(_TERM_HEAD)} bytes")
    print(f"DUMP_TAIL            @ {TERM_AT + len(_TERM_HEAD):04X}  "
          f"{len(_TERM_TAIL)} bytes")
    print(f"terminator total     @ {TERM_AT:04X}..{TERM_AT + len(_TERM) - 1:04X}"
          f"  {len(_TERM)} bytes")
    print(f"handler table        @ {IHT_AT:04X}..{IHT_AT + IHT_N * IHT_STRIDE - 1:04X}"
          f"  {IHT_N} x {IHT_STRIDE}")
    em, dn = emitted_order(_TERM)
    print(f"emitted order        {['AW' if e is None else e for e in em]}")
    print(f"done marker          {dn:#06x} to port {OUT_PORT_DONE:#04x}")
    print()

    chk("_LOAD_TMPL is not None", _LOAD_TMPL is not None)
    chk("_FAST_OK", _FAST_OK)
    chk("13 load patch slots", len(_LOAD_OFFS) == 13)
    chk("STORE_ORDER has 15 names", len(STORE_ORDER) == 15,
        f"({len(STORE_ORDER)})")
    chk("emission order == STORE_ORDER index for index",
        ['AW' if e is None else e for e in em] == STORE_ORDER)
    chk("done marker == DONE_SENTINEL", dn == DONE_SENTINEL)

    body = bytes([0x90, 0x90, 0x90, 0xF8])
    hbodies = [bytes([0x40 + i]) for i in range(IHT_N)]     # INC r16 per slot
    ramw = [(0x2100, 0x11), (0x2101, 0x22)]
    img, meta = compose(regs={"AW": 0x1111, "BW": 0x2222, "SS": 0x0300,
                              "SP": 0x0F00},
                        instr=body, ram=ramw, handlers=hbodies,
                        ivt={0: (0, 0x0480)})
    a = meta["anchor_phys"]
    chk("image is 64 KB", len(img) == 0x10000, f"({len(img)})")
    chk("body at anchor", img[a:a + len(body)] == body, f"anchor {a:04X}")
    chk("terminator at TERM_AT",
        img[TERM_AT:TERM_AT + len(_TERM)] == _TERM)
    for i in range(IHT_N):
        s = IHT_AT + i * IHT_STRIDE
        if img[s:s + 2] != hbodies[i] + bytes([IRET_BYTE]):
            chk(f"handler slot {i}", False, f"@{s:04X} {img[s:s+2].hex()}")
            break
    else:
        chk(f"all {IHT_N} handler slots = body+IRET", True)
    chk("handler slot pad is 0xCC",
        set(img[IHT_AT + 2:IHT_AT + IHT_STRIDE]) == {CODE_FILL})
    chk("vector 3 -> TERM_AT",
        img[12:16] == bytes((TERM_AT & 0xFF, TERM_AT >> 8, 0, 0)),
        img[12:16].hex())
    chk("caller vector 0 preserved",
        img[0:4] == bytes((0x80, 0x04, 0, 0)), img[0:4].hex())
    chk("load routine at LOAD_AT",
        img[LOAD_AT:LOAD_AT + 3] == bytes([0xB8, 0x00, 0x00]),
        img[LOAD_AT:LOAD_AT + 3].hex())
    chk("reset vector at VECTOR_AT",
        img[VECTOR_AT:VECTOR_AT + 5] == bytes([0xEA, 0x00, 0xFF, 0, 0]),
        img[VECTOR_AT:VECTOR_AT + 5].hex())
    chk("PSW image = normalize_psw(default)",
        img[PSW_IMAGE_AT] | (img[PSW_IMAGE_AT + 1] << 8) == normalize_psw(0x0202))
    chk("PSW image has IE set", (img[PSW_IMAGE_AT + 1] >> 1) & 1 == 1)
    chk("ram bytes placed", img[0x2100] == 0x11 and img[0x2101] == 0x22)

    # code region: everything outside {body, table, terminator} is 0xCC
    structured = set(range(a, a + len(body))) \
        | set(range(IHT_AT, IHT_AT + IHT_N * IHT_STRIDE)) \
        | set(range(TERM_AT, TERM_AT + len(_TERM)))
    bad = [p for p in range(CODE_LO, CODE_HI)
           if p not in structured and img[p] != CODE_FILL]
    chk("code region outside structures is 0xCC", not bad,
        f"{len(bad)} bytes not 0xCC" if bad else "")
    # the handler-slot pads ARE inside `structured` but must also be 0xCC
    pads = [p for i in range(IHT_N)
            for p in range(IHT_AT + i * IHT_STRIDE + len(hbodies[i]) + 1,
                           IHT_AT + (i + 1) * IHT_STRIDE)]
    chk("handler slot pads are 0xCC",
        all(img[p] == CODE_FILL for p in pads), f"{len(pads)} bytes")

    # carve-outs carry no 0xCC that compose did not place
    for nm, rg in (("IVT", IVT_REGION), ("DATA", DATA_REGION),
                   ("STACK", STACK_REGION), ("LOADER", LOADER_REGION)):
        placed = set()
        if rg is IVT_REGION:
            placed = set(range(0, 4)) | set(range(12, 16))
        if rg is LOADER_REGION:
            placed = set(range(LOAD_AT, LOAD_AT + 64)) | \
                set(range(PSW_IMAGE_AT, 0x10000))
        if rg is DATA_REGION:
            placed = {0x2100, 0x2101}
        n = sum(1 for p in rg if p not in placed and img[p] == CODE_FILL)
        chk(f"carve-out {nm} [{rg.start:04X},{rg.stop:04X}) free of 0xCC",
            n == 0, f"({n} stray 0xCC)" if n else "")

    # negative controls: the checks that must still bite
    for nm, kw in (("body outside code region", dict(regs={"PS": 0, "PC": 0x0500},
                                                     instr=b"\x90")),
                   ("body overruns code region",
                    dict(regs={"PS": CODE_LO >> 4, "PC": CODE_SIZE - 2},
                         instr=b"\x90" * 8)),
                   ("caller sets vector 3", dict(ivt={3: (0, 0x1234)})),
                   ("body collides with terminator",
                    dict(regs={"PS": TERM_AT >> 4, "PC": 0}, instr=b"\x90" * 4)),
                   ("9 handler bodies", dict(handlers=[b""] * 9)),
                   ("oversize handler body",
                    dict(handlers=[b"\x90" * IHT_STRIDE])),
                   ("ram in reserved page", dict(ram=[(0xFF10, 0)])),
                   ("mirror alias", dict(ram=[(0x12100, 1), (0x22100, 2)]))):
        try:
            compose(**kw)
            chk(f"rejects: {nm}", False, "-- NO ComposeError")
        except ComposeError as e:
            chk(f"rejects: {nm}", True, f"-- {e}")

    print()
    print("SELFCHECK", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    if "--selfcheck" in sys.argv:
        sys.exit(_selfcheck())
    img, meta = compose(regs={"AW": 0x1111, "BW": 0x2222})
    print(f"composed {len(img)} bytes; meta: {meta}")
