# v0.3 divergence ledger — chip-vs-RTL residuals

62 cases in the v0.3 suite (347 forms × 10,000) where the socket-captured golden
(chip = truth) is **not reproduced by the internal RTL core** (the DUT), and the
mismatch is **memory-model-independent** — the case fails on both flat-1MB *and*
64K-mirrored replay, so it is not a mirror-collision artifact (those 62 were
separately re-emitted to flat-valid). Per the suite's flat-validity policy these are
**retained as valid suite content**: the chip behavior is real, and the RTL is what is
behind.

**Status: new intake for the next RTL campaign.** These are NOT residuals of a closed
investigation — the class-5 branch merged and the V20 architectural oracle closed 100%.
They are new, real chip-vs-RTL divergences at ~1-2 per 10,000 rates that only native
10k-deep sampling exposes — exactly what this suite was built to find. Booked as its own
task by the coordinator.

Found by `sw/check_core.py --suite-dir tests/v30/v0.3 --opcodes all` (three-way flat/
mirror pass); indices re-extracted on the settled post-re-emit suite. `cyc` = cycle-row
(bus-timing) divergence only; `arch` = final architectural state (regs/flags/ram) only;
`both` = fails on both axes.

## Families

### 1. `0F31` INS bit-field — pure timing, busstat @ cycle 9-10 (25 cases, largest family)
BIU/queue-adjacent bus-status timing. arch state matches exactly; only the cycle-row
bus-status column diverges at cycles 9-10.
idx (all `cyc`): 116, 547, 549, 759, 825, 1554, 1793, 1977, 2271, 2333, 2733, 3207,
3337, 3930, 4581, 4606, 5303, 6004, 6332, 6349, 7027, 7289, 7526, 7844, 8463

### 2. BCD string-4S functional residuals (24 cases)
`sub4s`/`cmp4s`/`add4s`. **NOTE: these are NOT the large-CL story** — the 4S generator
uses CL 1-6, so this is a genuinely new low-CL functional divergence, not a known count
limit. `0F22`/`0F26` are pure `arch` (final-state) misses; `0F20` is mixed.
- `0F26` cmp4s (10, `arch`): 279, 1022, 1406, 1455, 2829, 3135, 4217, 7202, 7885, 8474
- `0F22` sub4s (5, `arch`): 2526, 2852, 3415, 9381, 9460
- `0F20` add4s (9): 1938/3766/3941/6195/6785/8489 (`arch`), 1209/4493/7815 (`cyc`)

### 3. Pin-event functional residuals (10 cases, all `arch`)
- `HLT.RES` HALT masked-INT resume (6): 1973, 4366, 4870, 5710, 5820, 9308
- `IE0.90` masked INT (4): 1064, 3586, 4464, 7142

### 4. Single mixed bus-timing residuals (3 cases, all `both`)
- `0F1B` (1): 3917
- `83.5` (1): 8683
- `FF.3` (1): 7685

## Total
25 (0F31) + 24 (BCD-4S) + 10 (pin-event) + 3 (single) = **62 cases** across 9 forms.
Cycle-only: 28; arch-only: 31; both: 3.

These ship with the suite (chip truth). They do not block the campaign and are not suite
defects; each is an RTL work item.
