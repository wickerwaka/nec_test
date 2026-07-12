# Undefined-flag behavior on the real μPD70116C-8 (Campaign 2 mission 8)

What the flags documented **U** (undefined) in the User's Manual actually do
on silicon. Method: `sw/probe_flags.py` — for every instruction class with U
entries in `docs/facts/instructions.json`, run several operand patterns; the
first two patterns run at both PSW=0x0000 and PSW=0x0ED5 (all writable flags
set, TF excluded), so every U flag is seen with in=0 and in=1. Conditions:
max mode, 4 MHz, 0 waits, state injection/extraction per
`docs/notes/loadstore_design.md`.

Data: 53 case runs (48 sweep + 5 disambiguation), 275 hardware runs, zero
skips. Raw per-run log `sw/testdata/flags_log.jsonl`, full console rows
`sw/testdata/flags_run.out`, machine-readable verdicts
`sw/testdata/flags_report.json` (2026-07-11).

Verdict vocabulary:
- **preserved** — out == in for every sample (instruction never touches it)
- **always 0 / always 1** — constant across all samples (both input values)
- **acts defined** — matches a standard S/Z/P function of a result register
- **operand-dependent** — deterministic (identical across PSW inputs) but no
  simple function found; samples in flags_report.json

## Summary table

| Instruction (U flags per manual) | Observed behavior |
|---|---|
| MULU reg8/reg16 (S,Z,AC,P) | **all four preserved** |
| MUL reg8/reg16 (S,Z,AC,P) | all four overwritten, operand-dependent (below) |
| MUL reg16,reg16,imm8/imm16 (S,Z,AC,P) | S=MSB(result), Z=(result==0) in all samples; AC,P operand-dependent |
| DIVU reg8/reg16 (V,S,Z,AC,P,CY) | **V=0, Z=0, S=1, AC=1, CY=1** constant; P operand-dependent |
| DIV reg8/reg16 (V,S,Z,AC,P,CY) | **V=S=AC=CY=0, P=1** constant; **Z=(quotient==0)** |
| ADJBA (V,S,Z,P) | V=0, S=0, Z=(AW==0); P operand-dependent |
| ADJBS (V,S,Z,P) | V=0, Z=(AL==0), P=parity(AL); S operand-dependent |
| ADJ4A (all X per manual) / ADJ4S (V=U) | V data-dependent on both (see note) |
| CVTBD / AAM (V,AC,CY) | **all three always 0** |
| CVTDB / AAD (V,AC,CY) | V=0; AC,CY operand-dependent (internal-add residue) |
| AND/OR/XOR/TEST reg,reg byte+word (AC) | **AC always 0** |
| SHL/SHR/SHRA reg,1 and reg,CL and reg,imm8 (AC; V for n!=1 forms) | **AC always 0**; V: see shift-V law |
| shift/rotate by CL with **CL=0** | **all flags preserved** (incl. V, AC) |
| ROL/ROR/ROLC/RORC reg,CL n>1 (V) | V data-dependent: see shift-V law |
| NOT1/CLR1/SET1 CY — F5/F8/F9 (V,S,Z,AC,P) | **all five preserved** (only CY touched) |
| TEST1 reg,CL / reg,imm (S,AC,P) | AC=0; **S,P (and defined Z) = S/Z/P of the masked test value** (below) |
| NOT1/CLR1/SET1 reg,CL / reg,imm — 0F forms (V,S,Z,AC,P) | **all five preserved** |
| INS reg,reg / reg,imm4 (all six) | all -> 0 (P in the imm4 form tracked parity(DL) over 2 patterns; weak sample) |
| EXT reg,reg (all six) | V=S=AC=CY=0; Z=(result==0), P=parity(result) |
| EXT reg,imm4 (all six) | V=S=Z=AC=CY=0 in samples; P operand-dependent |
| ADD4S/SUB4S/CMP4S (V,S,AC,P) | **V=0; S=CY(out); AC=CY(out); P=Z(out)** — 7 carry/borrow/equal configurations, no exception |

## Laws worth stating

### MULU vs MUL asymmetry
Unsigned multiply **does not write** its undefined flags — S/Z/AC/P pass
through unchanged (CY/V behave as documented). Signed MUL overwrites all
four with values that match no simple function of the result: e.g. MUL reg8
0x80*0x7F -> AW=C080 gives **Z=1** with a non-zero result and S=0 with MSB
set; 3-operand MUL 0x2000*5 -> CW=A000 gives S=0. S/Z looked
result-derived in most samples (and exactly result-derived in all 3-operand
samples), but the violations above rule out SZP-of-result for the 2-operand
forms — consistent with residue of the internal sign-fixup micro-ops (the
same fixup that costs MUL +10/+4 cycles over MULU, measurements.md). An RTL
core must reproduce these per-form, not via a generic flag rule.

### Signed/unsigned divide constants
DIVU forces S=1, AC=1, CY=1, Z=0, V=0 (P varies); DIV forces the complement
pattern S=AC=CY=V=0, P=1, with Z tracking quotient==0 (verified with
quotient-0 cases in both widths). Deterministic, so SingleStepTests-style
tests will capture them exactly.

**CORRECTION (2026-07-12, Campaign 3): the DIVU "constants" are a
sampling artifact.** Fitting the full v0.1 F7.6 corpus (500 cases, both
trap and non-trap) shows the complete law: **DIVU leaves exactly the
flags of its 16-bit overflow pre-check compare `SUB(DW, divisor)`** —
all six of S, Z, AC, P, CY, V — and the trap condition is that compare's
"no borrow" (which also covers divisor=0). The trapped path pushes those
compare flags as the PSW; the divide loop itself never touches flags.
For non-trap cases DW < divisor always holds, so the borrow forces CY=1,
Z=0, and (for this probe's operand mix) S=1/AC=1 — hence the earlier
constant reading. Verified bit-exact 500/500 by the RTL core replay
(sw/check_core.py).

**CORRECTION (2026-07-12, Campaign 3 mission F): DIV (signed) re-fitted
on dedicated F7.7/F6.7 tranches (500 cases each incl. traps).** The
signed law is the magnitude analog - the flags are always the residue
of the LAST magnitude micro-op, bit-exact on all 1000 cases:
- **Trap condition** (byte and word forms): divisor==0, or
  |num_high| >= |divisor| (magnitude pre-check on absolute values), or
  the unsigned quotient |num|/|divisor| exceeds 2^(n-1)-1. The range
  check is SYMMETRIC: quotient -128/-32768 TRAPS (measured: AW=0x3C15
  / divisor 0x88, quotient exactly -128, takes vector 0).
- **Early trap** (divisor 0 / pre-check): flags = flags of
  SUB(|num_high|, |divisor|) at operand width - all six, pushed PSW
  included (live flags additionally lose IE/TF as usual).
- **Late trap and non-trap**: flags = S/Z/P of the UNSIGNED quotient
  with CY=AC=V=0 (the quotient-magnitude write; the sign-fixup
  micro-ops never touch flags). The old "P=1, Z=(quotient==0)"
  constants were this law seen through small-quotient probes.
- Quotient/remainder truncate toward zero; remainder sign follows the
  dividend (126+123 non-trap cases).

### Shift/rotate V (the "o" the V20 suite masks)
All samples fit the 8086's single-step OF formula applied to the **final**
state:
- left ops (SHL, ROL, ROLC): V = MSB(result) XOR CY(out)
- right ops (ROR, RORC; SHR/SHRA samples consistent): V = bit(msb) XOR
  bit(msb-1) of the result
SHL by >= width gives V=0 (result and CY both 0). Count=0 leaves every flag
untouched. This extends mission 6's RORC finding (documented U behaving as
X) to the whole shifter family.

### TEST1 sets S/Z/P of the masked value
TEST1 op,n computes t = op AND (1<<n) and sets Z=(t==0) (documented) and
also S=MSB_width(t), P=parity8(t) (documented U). Verified across reg16/CL,
reg8/imm3 forms; AC=0.

### BCD string ops mirror their own outputs
ADD4S/SUB4S/CMP4S: undefined S and AC always equal the defined CY output
(BCD carry/borrow), undefined P always equals the defined Z output, V=0.
Probed with carry/no-carry (ADD4S), borrow/no-borrow (SUB4S),
greater/equal (CMP4S) datasets.

**Correction (Campaign 3, 0F20 golden tranche, all 500 cases / 1020 byte
iterations bit-exact):** on non-BCD inputs ADD4S is a nibble-serial
adder with a one-carry-rail decision quirk. Per byte (a=dst, b=src, cin):
low digit = binary nibble add, +6 adjust if it carried (c1) or exceeded
9 (c2). The high digit SUM receives c1+c2 as two carries, but the high
ADJUST DECISION computes ahi+bhi+(c1|c2) and fires >9 — so when both
carries land on a 9 the high digit becomes 0xA unadjusted. CY out =
that decision. **Z accumulates on the PRE-adjust bytes** (an adjust
that wraps a byte to 00 still gives Z=0), P mirrors that Z, S=AC=CY as
above. The byte written to memory drives its sibling lane with
src_other + dst_other + fire + (high-sum-carry AND pre-adjust-high>9)
- 1 (the internal 16-bit adder's other lane, one short when no adjust
fired). Timing: retire is one cycle slower when the final carry is 0
(13+22n becomes 14+22n).

### "Undefined" that is really "unchanged"
The manual marks V,S,Z,AC,P undefined on NOT1/CLR1/SET1 CY (F5/F8/F9) and
on the 0F-prefixed NOT1/CLR1/SET1 reg forms — silicon **preserves** all of
them (as it does for MULU). For emulation, U here means "not modified".

### ADJ4A/ADJ4S note
The manual marks ADJ4A's V as X (defined) but ADJ4S's as U, yet both are
data-dependent in the same way on silicon (set on some inputs, clear on
others, PSW-input-independent) — the same documentation inconsistency
pattern as the RORC V erratum (mission 6).

## Relation to the V20 SingleStepTests flags-mask convention

The V20 suite (docs/notes/singlesteptests_v20.md) records raw hardware flag
values and ships per-opcode `flags`/`flags-mask` metadata naming exactly the
NEC-manual U sets (MUL `...szap.`, DIV `o..szapc`, CL-shifts `o.......`),
letting consumers mask undefined bits on comparison. Our measurements show
those bits are nevertheless **deterministic** on the V30 — constants,
preserved inputs, SZP-of-result, or reproducible microcode residue — so:

- For the V30 suite we emit, the V20 approach carries over unchanged:
  record raw values, keep the masks for consumers.
- For the RTL core (Campaign 3), the masks are not enough: the golden-trace
  diff compares raw PSW, so the core must implement the behaviors above.
- **VERIFIED (2026-07-11, mission 12): V30 undefined-flag behavior is
  bit-exact with the V20.** `sw/pilot_v20.py --raw-flags` compares the
  FULL 16-bit flags word (no mask) against the V20 suite's recorded final
  values: 75/75 cases passed across the U-flag-heavy opcodes 37 (AAA),
  27 (DAA), D2.4 (SHL r/m8,CL), F6.4 (MUL r/m8), and F6.6 (DIV r/m8,
  including divide-exception paths with flag words pushed to the stack) —
  15 non-prefetched cases each (sw/testdata/rawflags_run.out; suite data
  provenance in tests/v30/v20suite/README.md). The V20 suite's raw flag
  values can therefore serve as a golden reference for the V30 core's
  undefined flags, and the classifications above describe both parts.
