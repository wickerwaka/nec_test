# Empirical measurements from the real μPD70116C-8

Facts measured on the harness, with provenance to capture files
(sw/testdata/) and harness conditions. These are the ground truth the
documentation claims get checked against. Conventions: CPU clock = 4 MHz
(cfg_clk_div=8), zero wait states, small-scale mode, boot image from
sw/make_boot.py unless stated.

## Reset behavior (small mode)

- **Reset release → first bus cycle: 8 CPU clocks** (ASTB of the FFFF0h
  fetch; the pins transition from float to driven-idle during those
  cycles). First data transfer completes 3 clocks later.
  - Source: `smallmode_boot_sticky.hex` (2026-07-11), reset released at
    record 33, first T1 at record 41.
  - Caveat: sampling offsets not yet calibrated to ±1 clock; datasheet
    says nothing to compare against (measured value, not documented).
- First fetch address is FFFF0h, word access (UBE̅ low, even address).

## Bus cycle shape (small mode, zero waits)

- **Every observed bus cycle is 4 CPU clocks** (T1-T4, no idle between
  back-to-back cycles during straight-line prefetch).
- Word fetches march at 4-clock intervals during pure prefetch: bus
  bandwidth-limited fetch rate = 2 bytes / 4 clocks.

## Prefetch (small mode — no queue status visible)

- After the reset-vector fetch at FFFF0h, the BIU fetched FFFF2, FFFF4,
  FFFF6 (8 bytes total) before the far jump redirected it — i.e. it
  overshot a 5-byte instruction by 3 bytes while the EU decoded.
- Before the backwards short jump in the boot loop (JMP at 0010F/0110),
  prefetch reached 00112 — 2 bytes beyond the jump's last byte.
- Queue depth/refill policy not measurable without QS (large mode).

## Odd-address word access (small mode)

- `MOV AW,[2001h]` (odd word read) executes as **two byte bus cycles**:
  MEMR @02001 (upper lane, UBE̅=0, A0=1) then MEMR @02002 (lower lane,
  UBE̅=1, A0=0), 4 clocks each. Matches the documented split-access rule
  (User's Manual p98 table).

## Instruction-sequence timing (small mode)

- The boot loop (MOV AW,imm; MOV BW,imm — first iteration only —
  then per iteration: MOV [BW],AW; MOV AL,[2000h]; MOV AW,[2001h]; NOP;
  JMP short back) runs at **64 CPU clocks per iteration**, comprising 14
  bus transactions (11 fetch, 3 data).
  - Source: `smallmode_boot_sticky.hex`, loop analysis by
    sw/analyze_capture.py --loops.
  - Not yet decomposed into per-instruction times (needs queue
    visibility or single-instruction tests).

## Large (max) mode — first queue-status measurements (2026-07-11, post RQ/AK rework)

Source: `sw/testdata/largemode_boot_real.hex` (boot image, 4 MHz, zero waits,
max mode via CFG.small_mode=0 → S/LG̅ low).

- **Queue status works**: QS reports F/S/E ops; 442 instruction first-byte
  ops in the trace; queue flush (E) once per loop iteration (the short jump).
- **Reconstructed queue depth peaks at 5** (documented depth 6; this loop
  never lets it saturate — dedicated queue-limit experiment pending).
- **Per-instruction times from F-to-F spacing** (queue-supply constrained,
  not yet decomposed into EU vs BIU bound): the 7-instruction loop
  (MOV AW,imm / MOV BW,imm / MOV [BW],AW / MOV AL,dmem / MOV AW,odd-dmem /
  NOP / BR short) shows gaps {3, 5, 7, 11, 12, 12, 14} clocks, sum = 64 —
  matching the bus-side loop measurement exactly. Attribution of each gap
  to its instruction awaits the shadow-queue parser (loadstore_design.md
  stage 2).
- Float-window artifact: the ~8 cycles between reset release and first
  drive decode as phantom INTA transactions in max mode (BS floats to 000),
  analogous to the small-mode phantom reads. Parser must tolerate.

## State injection/extraction verified (2026-07-11, max mode)

- **Register echo test passes**: all 8 GPRs, all 4 segment registers, PSW,
  and PC injected via the load routine (POP PSW + MOV sequence +
  terminal far jump) and extracted via OUT-port stores read back exactly
  (sw/v30run.py echo).
- **PSW writable bits**: patterns exercising V/DIR/IE/S/Z/AC/P/CY all echo
  with zero diff after normalization (psw = (req & 0x0ED5) | 0xF002).
  Reserved bits (15:12 forced 1, 5/3 forced 0, 1 forced 1) read back as
  forced. NOT yet probed: whether bit 15 (MD) can be cleared by POP PSW in
  native mode — deferred until a recovery path for accidental
  8080-emulation entry exists.
- **Word OUT to an odd port splits into two byte I/O cycles** (measured:
  OUT 0xFD,AW produced byte writes at 0xFD and 0xFE, operand low byte
  first on the upper lane) — same split rule as odd memory words. Harness
  convention: keep exfiltration ports even.

## V20-baseline cross-validation (2026-07-11, pilot)

sw/pilot_v20.py runs V20 SingleStepTests cases (non-prefetched variants)
on the real V30 and compares architectural results. **60/60 passed**:
20 cases each of B8 (MOV AX,imm), 00 (ADD r/m8,r8 — modrm, memory
operands, arithmetic flags), 37 (AAA — undefined flags masked per suite
metadata). Registers, flags (documented bits), and final memory
(byte-lane-accurate) all match the V20 hardware baseline, consistent
with the documented architectural equivalence of the V20/V30 execution
cores. Throughput ~2-3 s/case over SSH (unbatched); suite-scale
campaigns need the batching work from loadstore_design.md stage 3.

## MUL/MULU timing characterization (2026-07-11, Campaign 2 mission 1)

Method: saturated-queue F-spacing (sw/sweep_timing.py mul), max mode,
4 MHz, 0 waits; 42 measurements in docs/facts/timing_measured.json.

- **MULU (unsigned) is data-independent**: reg8 = 24 cycles, reg16 = 31,
  mem8 [BW] = 34, mem16 [BW] even = 41 — identical across operand sets
  including 0, 1, and all-ones.
- **MUL (signed) = MULU + 10, plus exactly +4 when the operand sign bits
  differ** (zero counts as positive; the product's own sign is
  irrelevant): reg8 = 34/38, reg16 = 41/45, mem8 = 44, mem16 = 51,
  reg16,reg16,imm8 = 40/44, reg16,reg16,imm16 = 40.
- vs documentation: MULU reg forms +1..3 (like other reg ops), MULU mem
  forms +5..6; all signed-MUL measurements fall inside the manual's
  "according to data" ranges EXCEPT **MUL reg16,reg16,imm8: measured
  40/44 vs documented 28-34** — a genuine documentation error.
- The earlier "MULU CW = 31 vs 21-22 (+9)" open item was a doc-lookup
  error: 21-22 is MULU reg8; MULU reg16 is documented 29-30.

## Per-opcode timing sweep, 113 forms (2026-07-11, Campaign 2 mission 2)

sw/sweep_timing.py sweep; all data with operands and provenance in
docs/facts/timing_measured.json. Conditions: max mode, 4 MHz, 0 waits,
even-aligned code/data, saturated-queue F-spacing. 113 measured + 7
verification re-runs (different registers / SP) — every value reproduced
exactly; 0 forms unassemblable. 84/113 deviate from the User's Manual.

**Deviations are class-consistent** (every op in a class shows the same
delta):

| Form class | Measured | Documented | Delta |
|---|---|---|---|
| No-modrm reg/imm forms (NOP, MOV reg,imm, acc,imm ALU, INC/DEC reg16, XCH AW,r, CY/DIR flag ops) | doc | — | **0** |
| ALU/MOV reg,reg (modrm) | 3 | 2 | +1 |
| ALU reg,imm (group 80/81/83) | 6 | 4 | +2 |
| Unary reg: NOT/NEG reg, INC/DEC reg8 (F6/FE groups) | 4 | 2 | +2 |
| Loads reg,mem [BW] (MOV/ALU/CMP) | 13 | 11 | +2 |
| TEST mem,reg | 12 | 10 | +2 |
| Stores mem,reg / mem,imm / mem16,sreg | **all 11** | 9 / 11 / 10 | +2 / 0 / +1 |
| MOV acc,dmem (direct load) | 10 | 10 | 0 |
| MOV dmem,acc (direct store) | 10 | 9 | +1 |
| RMW mem,reg (ALU), XCH mem,reg | 19 | 16 | +3 |
| RMW unary mem (INC/DEC/NEG), ALU mem,imm | 20 / 22 | 16 / 18 | +4 |
| Shift/rotate reg,1 (all 8 ops, byte+word) | **6** | 2 | **+4** |
| Shift/rotate reg,CL or reg,imm8, n≥1 | 10+n | 7+n | +3 |
| Shift reg,CL with CL=0 | 9 | 7 | +2 |
| Shift/rotate mem,1 | 22 | 16 | +6 |
| PUSH/POP reg16/sreg/PSW (SP even) | 9 | 8 | +1 |
| PUSH imm8 / imm16 | 9 / 10 | 7 / 8 | +2 |
| PUSH R (even) | **52** | 35 | **+17** |
| POP R (even) | **33** | 43 | **-10** (only negative deviation) |
| Bit ops SET1/NOT1 reg,CL and reg,imm | 6 | 4 / 5 | +2 / +1 |
| CLR1 reg,CL and reg,imm3 | 7 | 5 / 6 | +2 / +1 |
| DIVU reg16 | 28 | 25 | +3 |
| MULU reg8/reg16, mem8/mem16 | 24/31/34/41 | 21-22/29-30/27-28/35-36 | +2/+1/+6/+5 |

Notable structure:

- **Silicon is uniform where the manual is not.** All three 2-byte-EA
  store forms measure 11 though the manual says 9/10/11; SET1/NOT1
  CL-forms and imm-forms measure identically though the manual charges
  the imm forms +1; all eight shift/rotate ops match each other exactly.
- **TEST reg,reg (2), XCH reg,reg (3), MOV sreg,reg16 / reg16,sreg (2)
  match documentation** while every other modrm reg,reg op takes 3 —
  TEST and the sreg MOVs are genuinely 1 cycle faster than ADD reg,reg
  on silicon (verified across register choices).
- Shift-by-1 at 6 cycles (vs documented 2) is the largest relative
  register-form deviation; shift-by-CL measures 10+n (n>=1), 9 (n=0).
- PUSH R/POP R: 52/33 vs documented 35/43. POP R (reads) runs near the
  4-cycle/word bus floor (33 ~= 8x4+1); PUSH R (writes) at 52 ~= 6.5
  cycles/word matches the writes-do-not-overlap-fetch arbitration
  pattern (biu_model.md exp 4).
- Direct-address loads (MOV acc,dmem) are the only memory reads with
  zero deviation; modrm EA loads all pay +2.

## Divide-overflow semantics (prior work, large context)

- MAME's divide-overflow behavior for V30 (CY/V = !overflow, registers
  preserved) is already grounded in hardware testing by Martin (MAME PR
  #15620) — see docs/notes/mame_necv.md.
