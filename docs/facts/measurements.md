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

## Divide-overflow semantics (prior work, large context)

- MAME's divide-overflow behavior for V30 (CY/V = !overflow, registers
  preserved) is already grounded in hardware testing by Martin (MAME PR
  #15620) — see docs/notes/mame_necv.md.
