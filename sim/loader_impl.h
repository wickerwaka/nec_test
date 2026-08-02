// loader_impl.h -- the pre-decode hardware, as a template over the BUS POLICY.
//
// Split out of loader.cpp for the ucsim-t timing campaign (T0).  The body is
// UNCHANGED; the concrete `Biu&` parameter became a `Bus&` template parameter
// and the file-static helpers moved from an anonymous namespace into
// `sim::loader_detail`.  `loader.cpp` explicitly instantiates
// `loader_decode<Biu>` (the FUNCTIONAL bus) and `exec_timed.cpp` instantiates
// `loader_decode<BiuTimed>` (the TIMED bus), so the functional build keeps the
// codegen shape it had before the split: one out-of-line copy in loader.o,
// called (never inlined) from exec.o.
//
// Bus concept used here: `next_byte(cs, upc)`,
// `mem_read(seg_val, off, word, seg_idx, upc)`, and (ucsim-t T1) the timed
// extensions `charge(n)`, `opcode_pending()` and `prefix_retire()` that carry
// the decoder's byte-demand SCHEDULE.  All three are `{}` on sim::Biu, so the
// functional instantiation is unchanged.

#ifndef LOADER_IMPL_H
#define LOADER_IMPL_H

#include "loader.h"

#include "ea.h"
#include "pla3_table.h"

namespace sim {


namespace loader_detail {

constexpr uint16_t kPreDecodeUpc = 0xFFFF;

inline OperandRef reg_ref(uint8_t idx, bool byte) {
    OperandRef r;
    r.kind = OperandRef::kReg;
    r.idx = uint8_t(idx & 7);
    r.byte = byte;
    return r;
}

inline OperandRef sreg_ref(uint8_t idx) {
    OperandRef r;
    r.kind = OperandRef::kSregRef;
    r.idx = uint8_t(idx & 3);
    r.byte = false;
    return r;
}

inline OperandRef mem_ref(uint16_t ea, uint8_t seg, bool byte) {
    OperandRef r;
    r.kind = OperandRef::kMem;
    r.ea = ea;
    r.seg = seg;
    r.byte = byte;
    return r;
}

}  // namespace loader_detail

namespace loader_detail {

// --- 8080 emulation-mode decode -------------------------------------------
// The V20's emulation mode maps the 8080 register file onto the V30's, and the
// ROM's 8080 pages address it through the SAME `M` / `R` operand latches the
// native pages use.  Both mappings are read straight out of the microcode:
//   * `EB` XCHG is `BX <-> DX`, `F9` SPHL is `BX -> BP`, `E9` PCHL is
//     `BX -> PC`  =>  HL = BX, DE = DX, SP = BP;
//   * `LDAX B/D` is `R -> IND`  =>  BC = CX;
//   * `MOV` is `M -> tmpa` / `tmpa -> R`, and `INR`/`MVI` write through `R`
//     with `[-06-]`  =>  M is the SOURCE field (bits 2:0), R the DESTINATION
//     field (bits 5:3), and register code 110 is memory at DS:BX.
// A = AL follows from `SIGMA -> AL` in the ALU block.
constexpr uint8_t k8080Reg8[8] = {
    5,  // B -> CH
    1,  // C -> CL
    6,  // D -> DH
    2,  // E -> DL
    7,  // H -> BH
    3,  // L -> BL
    0xFF,  // M -> memory at DS:BX
    0,  // A -> AL
};
constexpr uint8_t k8080Pair[4] = {kCW, kDW, kBW, kBP};

inline OperandRef r8080(Machine& m, uint8_t code) {
    uint8_t r = k8080Reg8[code & 7];
    if (r == 0xFF) return mem_ref(m.gpr[kBW], kDS, true);
    return reg_ref(r, true);
}

template <class Bus>
LoadResult loader_decode_8080(Machine& m, Bus& biu) {
    LoadResult out;
    auto fetch = [&]() -> uint8_t {
        uint8_t b = biu.next_byte(m.sreg[kCS], kPreDecodeUpc);
        m.pc = uint16_t(m.pc + 1);
        return b;
    };

    uint8_t b = fetch();
    uint16_t v = pla3::kMode8080[b];
    bool ext = false;
    if (pla3::one_byte_logic(v) &&
        pla3::bl1_op(v) == pla3::Bl1Op::kExtPrefix) {
        ext = true;
        ++m.pfxcnt;
        b = fetch();          // ED ED = CALLN, ED FD = RETEM
        v = pla3::kMode8080[b];
    }
    out.opcode = b;
    out.pla = v;
    m.opc_reg = b;
    m.xop = pla3::xop(v);

    if (!ext && pla3::one_byte_logic(v)) {
        out.executed = true;
        switch (pla3::bl1_op(v)) {
            case pla3::Bl1Op::kSetIe: m.psw |= kFlagIE; break;
            case pla3::Bl1Op::kClrIe: m.psw &= uint16_t(~kFlagIE); break;
            case pla3::Bl1Op::kSetCy: m.psw |= kFlagCY; break;
            case pla3::Bl1Op::kNotCy: m.psw ^= kFlagCY; break;
            case pla3::Bl1Op::kHalt: m.halted = true; out.halt = true; break;
            default: break;
        }
        m.set_flags(m.psw);
        return out;
    }

    bool byte = pla3::byte_only(v);
    m.op8 = byte;
    m.imm8 = byte;

    // `R` is a 16-bit PAIR for every non-byte form, and additionally for
    // STAX/LDAX (`02`/`0A`/`12`/`1A`), whose DATA is a byte but whose `R` is
    // the BC/DE pointer the ROM loads straight into IND.
    bool pair = !byte || (b < 0x20 && (b & 7) == 2);
    if (pla3::has_modrm(v)) {
        // The register fields live IN the opcode; no second byte is fetched.
        // In the ALU block (80-BF) bits 5:3 are the OPERATION, not a register,
        // so only the source field binds.
        if (b < 0x80) m.R = r8080(m, uint8_t((b >> 3) & 7));
        if (!pla3::dir_from_bit1(v))     // MOV / ALU: bits 2:0 is the source
            m.M = r8080(m, uint8_t(b & 7));
    } else if (pla3::dir_from_bit1(v)) {
        m.R = r8080(m, uint8_t((b >> 3) & 7));   // MVI r,d8
    } else if (pair) {
        m.R = reg_ref(k8080Pair[(b >> 4) & 3], false);
    }
    if (pair && m.R.kind == OperandRef::kReg) m.R.byte = false;

    // The ALU group's OPC permutation (80-BF, C6-FE = xop 0, ByteOnly, and the
    // immediate block); the rotate block 07/0F/17/1F keeps the native
    // ROL/ROR/RCL/RCR order off `opc_base`.
    if ((b >= 0x80 && b <= 0xBF) || (b >= 0xC0 && (b & 7) == 6))
        m.opc8080 = true;
    else if (b < 0x20 && (b & 7) == 7)
        m.opc_base = kRol;

    // Pre-read: the operand the sequence READS, and only that one.  MOV / ALU
    // read `M`; INR / DCR read `R`; MVI writes `R` without reading it.
    const OperandRef* pre = nullptr;
    if (pla3::has_modrm(v)) pre = pla3::dir_from_bit1(v) ? &m.R : &m.M;
    if (pre && pre->kind == OperandRef::kMem) {
        m.opr = biu.mem_read(m.sreg[pre->seg], pre->ea, false, pre->seg,
                             kPreDecodeUpc);
        out.preread = true;
    }
    // `[-06-]` commits the DESTINATION when it is memory (MOV M,r / MVI M /
    // INR M / DCR M).  In native mode only the r/m operand can be memory, so
    // the strobe is bound to `M` there; in 8080 mode BOTH fields can name
    // memory and the strobe follows the destination, i.e. `R`.  `MOV r,M`
    // therefore issues no write-back at all -- which is exactly what the chip
    // does, and what binding the strobe to `M` would get wrong.
    if (m.R.kind == OperandRef::kMem) m.WB = m.R;

    out.entry.page = ext ? 5 : 6;
    out.entry.opc = b;
    out.entry.loc = 0;
    return out;
}

}  // namespace loader_detail

template <class Bus>
LoadResult loader_decode(Machine& m, Bus& biu) {
    LoadResult out;

    // Per-instruction latch reset.
    m.seg_override = false;
    m.seg_ovr = kDS;
    m.rep = kRepNone;
    m.lock = false;
    m.pfxcnt = 0;
    m.M = OperandRef{};
    m.R = OperandRef{};
    m.WB = OperandRef{};
    m.opc_base = 0;
    m.opc_from_modrm = false;
    m.modrm_reg = 0;
    m.rep_test = kTestNone;
    m.rep_pol = false;
    m.bus_word = false;
    m.opc8080 = false;
    // The address adder stands on the SIGMA path with its default operation
    // (ledger, "EA-in-SIGMA"): ADD of the two tmp ports.  XLAT's 012D is the
    // row that forces it -- BX + AL with no ALU row of its own.
    m.alu = AluLatch{};
    m.alu.op = kAdd;
    m.alu.tmp = 0;
    m.alu.byte = false;

    // 8080 emulation mode decodes off a different PLA section into different
    // micro-pages; everything downstream (operand latches, bus rows, the
    // write-back strobe) is the same machine.
    if (m.mode8080) return loader_detail::loader_decode_8080(m, biu);

    auto fetch = [&]() -> uint8_t {
        uint8_t b = biu.next_byte(m.sreg[kCS], loader_detail::kPreDecodeUpc);
        m.pc = uint16_t(m.pc + 1);
        return b;
    };

    // --- the decoder's byte-demand schedule (ucsim-t T1) ------------------
    // MEASURED (v0.1 saturated-queue goldens; identical to the frozen
    // decoder-displacement / decoder-multibyte oracles) with the opcode pop
    // at relative clock 0:
    //     opcode  0    modrm  1    disp8  3    disp16  2 and 4
    //     first micro-row: mod3 2, mod!=3 no-disp 3, disp8 4, disp16 5
    // An opcode the previous instruction's E row already pre-popped rides
    // THAT clock, so only a fresh pop advances the cursor here.
    auto pop_opcode = [&]() -> uint8_t {
        bool pre = biu.opcode_pending();
        uint8_t v = fetch();
        if (!pre) biu.charge(1);
        return v;
    };

    // --- prefix loop ------------------------------------------------------
    bool ext = false;
    uint8_t b = 0;
    for (;;) {
        b = pop_opcode();
        uint16_t v = pla3::kNative[b];
        if (!pla3::is_prefix(v)) break;
        switch (pla3::bl1_op(v)) {
            case pla3::Bl1Op::kSegPrefix:
                m.seg_override = true;
                m.seg_ovr = uint8_t((b >> 3) & 3);  // 26/2E/36/3E -> ES/CS/SS/DS
                break;
            case pla3::Bl1Op::kRepPfx: m.rep = kRepE; break;
            case pla3::Bl1Op::kRepnePfx: m.rep = kRepNE; break;
            case pla3::Bl1Op::kRepcPfx: m.rep = kRepC; break;
            case pla3::Bl1Op::kRepncPfx: m.rep = kRepNC; break;
            case pla3::Bl1Op::kLock:
            case pla3::Bl1Op::kLockAlias: m.lock = true; break;
            case pla3::Bl1Op::kExtPrefix: ext = true; break;
            default: break;
        }
        ++m.pfxcnt;
        if (ext) {
            // The 0F escape is a 2-clock re-decode: the real opcode pops two
            // clocks after 0F, as an S (0F is not one of the F-popping
            // prefixes -- check_core::PREFIXES).
            biu.charge(1);
            b = fetch();  // second byte of the 0F page: this IS the opcode
            biu.charge(1);
            break;
        }
        // A prefix retires as its own 2-clock instruction with its own F pop.
        biu.charge(1);
        biu.prefix_retire();
    }

    uint16_t v = ext ? pla3::kExt[b] : pla3::kNative[b];
    out.opcode = b;
    out.pla = v;

    // --- ONE_BYTE_LOGIC: executed by the pre-decode logic, no microcode ----
    if (!ext && pla3::one_byte_logic(v)) {
        out.executed = true;
        switch (pla3::bl1_op(v)) {
            case pla3::Bl1Op::kSetDir: m.psw |= kFlagDIR; break;
            case pla3::Bl1Op::kClrDir: m.psw &= uint16_t(~kFlagDIR); break;
            case pla3::Bl1Op::kSetIe: m.psw |= kFlagIE; break;
            case pla3::Bl1Op::kClrIe: m.psw &= uint16_t(~kFlagIE); break;
            case pla3::Bl1Op::kSetCy: m.psw |= kFlagCY; break;
            case pla3::Bl1Op::kClrCy: m.psw &= uint16_t(~kFlagCY); break;
            case pla3::Bl1Op::kNotCy: m.psw ^= kFlagCY; break;
            case pla3::Bl1Op::kHalt: m.halted = true; out.halt = true; break;
            default: break;
        }
        m.set_flags(m.psw);
        biu.charge(1);   // pre-decode-executed forms retire in 2 clocks
        return out;
    }

    // --- operand width ----------------------------------------------------
    bool byte;
    if (pla3::byte_only(v))
        byte = true;
    else if (pla3::w_from_bit0(v))
        byte = (b & 1) == 0;
    else
        byte = false;
    m.op8 = byte;
    // OP8 (Str_Cond[7]) gates the SECOND immediate byte fetch: it means "the
    // immediate is one byte".  For every form but 83 and 6B that coincides
    // with the operand width; those two take a sign-extended imm8 against a
    // word operand (ledger, OP8 vs OP8b).
    m.imm8 = byte || b == 0x83 || b == 0x6B;
    m.xop = pla3::xop(v);

    uint8_t page = ext ? 4 : (m.rep != kRepNone ? 1 : 0);
    m.opc_reg = b;

    // --- ModR/M + displacement + effective address ------------------------
    ModRm rm{};
    bool has_rm = pla3::has_modrm(v);
    out.has_modrm = has_rm;
    if (has_rm) {
        rm = modrm_decode(fetch());          // rides opcode+1
        biu.charge(1);
        out.modrm = rm.raw;
        uint16_t disp = 0;
        if (rm.disp_bytes == 1) {
            biu.charge(1);                   // opcode+2: no byte demanded
            disp = uint16_t(int16_t(int8_t(fetch())));   // opcode+3
            biu.charge(1);
        } else if (rm.disp_bytes == 2) {
            uint8_t lo = fetch();            // opcode+2
            biu.charge(2);                   // opcode+3: no byte demanded
            uint8_t hi = fetch();            // opcode+4
            biu.charge(1);
            disp = uint16_t(lo | (uint16_t(hi) << 8));
        } else if (rm.mod != 3) {
            biu.charge(1);                   // opcode+2: the EA-compute clock
        }
        out.disp = disp;
        if (rm.mod != 3) {
            uint16_t ea = ea_compute(m, rm, disp);
            uint8_t seg = m.seg_override
                              ? m.seg_ovr
                              : uint8_t(ea_uses_bp(rm) ? kSS : kDS);
            m.ind = ea;
            // The address adder's output stands on the SIGMA path at micro-row
            // 0 (evidence: LEA 0055, POP m 0058).  mod==3 leaves the previous
            // instruction's value standing (the documented stale-EA residue).
            m.alu.ea_const = true;
            m.alu.ea_value = ea;
            out.ea_valid = true;
            out.ea = ea;
            out.ea_seg = seg;
        }
    }

    // No ModR/M: the decoder still spends the opcode+1 clock before handing
    // over, so micro-row 0 lands at opcode+2 exactly as it does for mod3.
    if (!has_rm) biu.charge(1);

    // --- second-byte group dispatch (F6/F7 -> page 2, FE/FF -> page 3) ----
    if (has_rm && pla3::xop(v) == uint8_t(pla3::XopAux::kGroupDispatch)) {
        page = uint8_t((b & 8) ? 3 : 2);
        m.opc_reg = rm.raw;  // the ModR/M byte occupies the opcode slot
    }

    // --- OPC select: which field, and which block of kStrOp ---------------
    // OPC = opc_base + sel.  sel is opcode bits 5:3 except for the ModR/M
    // "group" opcodes, where the reg field is an opcode extension.
    m.modrm_reg = rm.reg;
    if (page == 2 || page == 3) {
        m.opc_base = kInc;  // INC DEC NOT NEG
        m.opc_from_modrm = true;
    } else if (!ext && (b >= 0x80 && b <= 0x83)) {
        m.opc_base = 0;  // ADD OR ADC SBB AND SUB XOR CMP
        m.opc_from_modrm = true;
    } else if (!ext && (b == 0xC0 || b == 0xC1 || (b >= 0xD0 && b <= 0xD3))) {
        m.opc_base = kRol;  // ROL ROR RCL RCR SHL SHR - SAR
        m.opc_from_modrm = true;
    } else if (pla3::xop(v) == uint8_t(pla3::XopAux::kIncDec)) {
        m.opc_base = kInc;
    }

    // --- REP / loop continuation test (pla_3 XOP 1110 = count/compare-loop)
    if (pla3::xop(v) == uint8_t(pla3::XopAux::kCountLoop)) {
        if (!ext && (b & 0xFE) == 0xE0) {
            m.rep_test = kTestZ;         // LOOPNE / LOOPE
            m.rep_pol = (b & 1) != 0;
        } else if (m.rep == kRepE || m.rep == kRepNE) {
            m.rep_test = kTestZ;
            m.rep_pol = (m.rep == kRepE);
        } else if (m.rep == kRepC || m.rep == kRepNC) {
            m.rep_test = kTestCy;
            m.rep_pol = (m.rep == kRepC);
        }
    }

    // --- operand binding --------------------------------------------------
    // The 0F-page BIT-FIELD group (pla_3 ext XOP = 0011, i.e. 0F 30-3F =
    // INS/EXT) selects BYTE registers for both ModR/M operands even though its
    // W bit says word -- the word width belongs to the string access through
    // IND, not to the offset/length register pair.  MEASURED: `ext dl, ch`
    // (ModR/M D5) takes its offset from CH, not from the low byte of BP.
    bool reg_byte = byte || (ext && pla3::xop(v) == 0x3);
    if (has_rm) {
        m.R = pla3::sreg_mov(v) ? loader_detail::sreg_ref(rm.reg)
                                : loader_detail::reg_ref(rm.reg, reg_byte);
        m.M = (rm.mod == 3) ? loader_detail::reg_ref(rm.rm, reg_byte)
                            : loader_detail::mem_ref(out.ea, out.ea_seg, byte);
        if (pla3::dir_from_bit1(v) && (b & 2)) {
            OperandRef t = m.M;
            m.M = m.R;
            m.R = t;
        }
    } else if (pla3::acc_w_operand(v)) {
        m.M = loader_detail::reg_ref(kAW, byte);  // AL when byte, AW when word
    } else if (b < 0x40 && (b & 7) >= 6) {
        m.R = loader_detail::sreg_ref(uint8_t((b >> 3) & 3));  // PUSH/POP sreg
    } else {
        m.M = loader_detail::reg_ref(uint8_t(b & 7), byte);  // 40-5F, 90-97, B0-BF
    }

    m.WB = m.M;

    // --- operand pre-read -------------------------------------------------
    // MODRM_STORE (pla_3 b6) = "the r/m operand is written without being
    // read": no pre-read.  The suppression is NATIVE-DECODE-MODE ONLY --
    // pla_3 asserts b6 for the 0F blocks 28-2F (ROL4/ROR4) and 30-3F
    // (INS/EXT) as well, yet those read their r/m operand.  MEASURED from the
    // v0.2 cycle records: 0F 28/2A memory forms issue 3 MEMR + 3 MEMW cycles
    // while 88/89/8C/C6/C7 memory forms issue 0 MEMR.  Everything else with a
    // memory operand is fetched by the pre-decode hardware before micro-row 0.
    if (has_rm && rm.mod != 3 && !(!ext && pla3::modrm_store(v))) {
        const OperandRef& mo = (m.M.kind == OperandRef::kMem) ? m.M : m.R;
        if (mo.kind == OperandRef::kMem) {
            m.opr = biu.mem_read(m.sreg[mo.seg], mo.ea, !mo.byte, mo.seg,
                                 loader_detail::kPreDecodeUpc);
            out.preread = true;
        }
    }

    out.entry.page = page;
    out.entry.opc = m.opc_reg;
    out.entry.loc = 0;
    return out;
}

}  // namespace sim

#endif  // LOADER_IMPL_H
