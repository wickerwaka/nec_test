# V30 BIU model (Campaign 1 exit artifact — in progress)

Behavioral model of the μPD70116 Bus Interface Unit, every claim backed by
a measurement. Conditions unless stated: max mode, 4 MHz, zero wait states,
sw/exp_biu.py experiments via the load/store machinery.

## Prefetch queue geometry — MEASURED (exp 1, queue-limit, 2026-07-11)

- **Queue capacity: 6 bytes.** During a long EU-bound instruction (DIVU),
  the BIU fetches words back-to-back at 4-cycle cadence until reconstructed
  depth reaches exactly 6, then the bus idles (PASV/TI). Hard stop at 6 in
  all cases; never a fetch initiated at depth ≥ 5.
- **Refill threshold: 2 bytes free.** From a full queue, the first pop
  (depth 6→5) does NOT restart fetching; the second (→4) does, with a new
  T1 within ~2 cycles. All observed fetch initiations occur at depth ≤ 4.
  Matches the 8086's documented rule (word-fetch BIU waits for 2 free).
- Fetch size: words at even addresses (+2 per completed fetch, at T4).
  Odd-address fetch behavior: pending (exp 6).

## Instruction timing observations (methodology calibration pending, exp 3)

- **DIVU reg16 is data-independent: 28 cycles F-to-next-F** across
  {FFFF/1, 1/1, 1234:5678/FFFF, 0/8000}. Documented value 25; the +3 is
  the F-to-F attribution offset to be calibrated by the saturated-queue
  NOP-sled experiment. Contrast: Intel 8086 DIV is iterative and
  data-dependent (144-162 clocks) — NEC's hardware divider claim is
  behaviorally confirmed.

## Pending (campaign 1 experiment list, see ROADMAP.md)

- exp 2: flush-to-refetch penalty, even vs odd jump targets
- exp 3: saturated-queue F-spacing calibration (NOP sleds + variable insn)
- exp 4: fetch/EU bus arbitration and idle patterns
- exp 5: wait-state interaction (BIU-bound vs EU-bound separation)
- exp 6: odd-target first-fetch width; self-modifying-code distance

## Provenance

exp 1 captures: produced by `sw/exp_biu.py queue-limit`; representative
timeline in the command output (case 0), cycle-indexed against the
capture. Re-run reproduces on demand (~10 s).
