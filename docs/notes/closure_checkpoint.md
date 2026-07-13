# Campaign 3 closure block — final checkpoint

Closure block complete (2026-07-13). Board = root@mister-nec (health:
`python3 sw/v30run.py echo`; last verified this date). NEVER reprogram
the FPGA; one board user at a time. No background chains are running.
Serve v2 (delta/partial-capture) is DEPLOYED and validated (31 ms/case).

## GRAND REGRESSION (311 forms x 500/200, zero waits)

TOTAL: 155440/155500 cycle-exact (99.96%); arch 155500/155500 (100.0%).
Wait-state suites (v0.1-w1, v0.1-w3): 1200/1200 each.

310 of 311 forms are 100% cycle- AND state-exact. The single
residual:

- **8F.0 at 440/500 cycles (arch 500/500)**: 60 cases (33 pf mod3 +
  27 cold-pop@4 mod3) where the mod3 ghost stack-read's committed
  ADDRESS, visible only on the final captured row(s), is not SS:SP.
  Brute force over all (seg<<4)+reg+const combinations finds no
  case-state formula in either class - the driven address is
  pre-window internal latch state from the harness injection stub
  (the 63 C0 preload), invisible to the golden schema. Registers,
  RAM, flags and every bus SLOT are exact; only the address value on
  that commit row differs. To close it the golden schema would need a
  pre-window latch field (or the injection stub modeled in the TB).
  Flagged for Campaign 4 A/B runs where the stub runs for real.

## Closure-block results (this session, commits 793c61a..HEAD)

- **INS/EXT (0F 31/33/39/3B) implemented**: all four forms 500/500.
  Full semantics + timing laws in the v30_eu.sv decode comment
  (op_insext) and state comments: offset-reg-update-before-source
  aliasing, EXT AL/AH-offset degenerate modes incl. the 256*len
  runaway, flags from s=off+len, the split-access chain laws, and
  0F39's mid-flow imm pop (mrm+6 / read-done+4+off).
- **0F22/0F26 (SUB4S/CMP4S) resolved**: 500/500 each. High-adjust
  fires additionally at dec==9 with an invalid low nibble gated on
  !c1 (pre-adjust >99h DAS threshold); SUB4S driven sibling =
  dst_o - src_o - braw - badj + 1 (byte-boundary borrows of the raw
  subtract and the -6/-60h adjust step).
- **FF.2/FF.6 resolved**: 500/500 each. The parked "carried-phase
  artifact" was an aliased fit - the reg-form push slot is a constant
  ready=pop+4 (no bus_phase term).
- **8F.0 reservation laws fixed** (440/500, arch 500/500): mod3 ghost
  pop reserves from pop+1 with ready at the pop-phase slot; the mem
  mod0 form does NOT reserve during EA compute. Remaining 60 = the
  address residual above.
- **C8 PREPARE resolved**: 500/500. level 0 retires at
  max(level-pop+4, push done); level>=2's first pointer-copy read is
  ready at level-pop+7 (address staged in the preceding wait cycle)
  behind a one-cycle reservation at level-pop+6. The suspected
  T4-end-eval BIU rule is NOT needed - no BIU change landed.
- POP-PSW boundary race and REP-abort flush slot: resolved by the
  predecessor (see interrupt_model.md); confirmed in this grand
  regression (INT.9D / INT.F3AA 200/200).

## Board / pipeline state

- All tranches (batches 1-3 + addenda) LANDED in tests/v30/v0.1
  (ground truth). No emissions pending. Board echo-verified, no jobs.
- sw/v30ctl.py on-board = serve v2 ("OK SERVE v2" banner).

## Notes for the next agent (Mission S was reassigned)

- Mission S (sequence fuzz, sw/gen_seq.py + sw/check_seq.py) was
  reassigned by the coordinator and NOT run in this block. The fuzz
  generator must respect: forbidden opcodes (0F >= 40h / 0F 34), and
  should be aware that EXT with offset reg AH and len<16 burns
  256*len cycles (case timeouts), and that INS/EXT mem-mod (mod!=3)
  encodings are PARKED (S_HALT) in the core - exclude them from
  sequences until characterized on silicon.
- Untested extrapolations (no tranche coverage, flagged in-code):
  0F31 (reg-len INS) with off=0 AND len=16 - implemented as
  read+write-at-41 (the reg-form s=16 path), but 0F39 measurements
  show a no-read lone write for the imm form; silicon likely skips
  the read for the reg form too. One targeted board measurement
  would settle it.
- Fit-loop recipe unchanged: `python3 sw/check_core.py --opcodes X
  --keep`, diff via build_rows_sim/diff_rows, adjust dly constants,
  rebuild, rescore; commit per family; keep neighbors green.
- Infrastructure notes (defer_t4/bus_phase/flush_fast etc.) unchanged
  from the predecessor block - see git history of this file.
