// loader.cpp -- see loader.h.

#include "loader.h"

#include "ea.h"
#include "pla3_table.h"

namespace sim {

namespace {

constexpr uint16_t kPreDecodeUpc = 0xFFFF;

OperandRef reg_ref(uint8_t idx, bool byte) {
    OperandRef r;
    r.kind = OperandRef::kReg;
    r.idx = uint8_t(idx & 7);
    r.byte = byte;
    return r;
}

OperandRef sreg_ref(uint8_t idx) {
    OperandRef r;
    r.kind = OperandRef::kSregRef;
    r.idx = uint8_t(idx & 3);
    r.byte = false;
    return r;
}

OperandRef mem_ref(uint16_t ea, uint8_t seg, bool byte) {
    OperandRef r;
    r.kind = OperandRef::kMem;
    r.ea = ea;
    r.seg = seg;
    r.byte = byte;
    return r;
}

}  // namespace

LoadResult loader_decode(Machine& m, Biu& biu) {
    LoadResult out;

    // Per-instruction latch reset.
    m.seg_override = false;
    m.seg_ovr = kDS;
    m.rep = kRepNone;
    m.lock = false;
    m.pfxcnt = 0;
    m.M = OperandRef{};
    m.R = OperandRef{};
    m.incdec_class = false;

    auto fetch = [&]() -> uint8_t {
        uint8_t b = biu.next_byte(m.sreg[kCS], kPreDecodeUpc);
        m.pc = uint16_t(m.pc + 1);
        return b;
    };

    // --- prefix loop ------------------------------------------------------
    bool ext = false;
    uint8_t b = 0;
    for (;;) {
        b = fetch();
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
            b = fetch();  // second byte of the 0F page: this IS the opcode
            break;
        }
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

    uint8_t page = ext ? 4 : (m.rep != kRepNone ? 1 : 0);
    m.opc_reg = b;

    // --- ModR/M + displacement + effective address ------------------------
    ModRm rm{};
    bool has_rm = pla3::has_modrm(v);
    out.has_modrm = has_rm;
    if (has_rm) {
        rm = modrm_decode(fetch());
        out.modrm = rm.raw;
        uint16_t disp = 0;
        if (rm.disp_bytes == 1) {
            disp = uint16_t(int16_t(int8_t(fetch())));
        } else if (rm.disp_bytes == 2) {
            uint8_t lo = fetch();
            disp = uint16_t(lo | (uint16_t(fetch()) << 8));
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

    // --- second-byte group dispatch (F6/F7 -> page 2, FE/FF -> page 3) ----
    if (has_rm && pla3::xop(v) == uint8_t(pla3::XopAux::kGroupDispatch)) {
        page = uint8_t((b & 8) ? 3 : 2);
        m.opc_reg = rm.raw;  // the ModR/M byte occupies the opcode slot
    }
    m.incdec_class =
        (page == 3) || (pla3::xop(v) == uint8_t(pla3::XopAux::kIncDec));

    // --- operand binding --------------------------------------------------
    if (has_rm) {
        m.R = pla3::sreg_mov(v) ? sreg_ref(rm.reg) : reg_ref(rm.reg, byte);
        m.M = (rm.mod == 3) ? reg_ref(rm.rm, byte)
                            : mem_ref(out.ea, out.ea_seg, byte);
        if (pla3::dir_from_bit1(v) && (b & 2)) {
            OperandRef t = m.M;
            m.M = m.R;
            m.R = t;
        }
    } else if (pla3::acc_w_operand(v)) {
        m.M = reg_ref(kAW, byte);  // AL when byte, AW when word
    } else if (b < 0x40 && (b & 7) >= 6) {
        m.R = sreg_ref(uint8_t((b >> 3) & 3));  // PUSH/POP sreg
    } else {
        m.M = reg_ref(uint8_t(b & 7), byte);  // 40-5F, 90-97, B0-BF
    }

    // --- operand pre-read -------------------------------------------------
    // MODRM_STORE (pla_3 b6) = "the r/m operand is written without being
    // read": no pre-read.  Everything else with a memory operand is fetched
    // by the pre-decode hardware before micro-row 0.
    if (has_rm && rm.mod != 3 && !pla3::modrm_store(v)) {
        const OperandRef& mo = (m.M.kind == OperandRef::kMem) ? m.M : m.R;
        if (mo.kind == OperandRef::kMem) {
            m.opr = biu.mem_read(m.sreg[mo.seg], mo.ea, !mo.byte, mo.seg,
                                 kPreDecodeUpc);
            out.preread = true;
        }
    }

    out.entry.page = page;
    out.entry.opc = m.opc_reg;
    out.entry.loc = 0;
    return out;
}

}  // namespace sim
