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

## Divide-overflow semantics (prior work, large context)

- MAME's divide-overflow behavior for V30 (CY/V = !overflow, registers
  preserved) is already grounded in hardware testing by Martin (MAME PR
  #15620) — see docs/notes/mame_necv.md.
