# BIU rebuild — w0-golden delta adjudication ledger

Per the inverted philosophy: the endpoint invariant is "new-model-TB == CHIP at
w0 AND w1 AND w3 for arbitrary sequences," NOT "w0 golden 169000/169000." When
a rebuilt-model change moves a w0 golden case, capture a fresh chip reference
(reflash-free) for that exact case and classify:
- (a) new-model-TB == chip, != old golden → the old golden passed via a KLUDGE
  (or a don't-care). Model is right; record the exposed kludge; the golden case
  needs acceptance/re-capture.
- (b) new-model-TB != chip → MODEL BUG; fix it.
- (c) chip non-deterministic / don't-care there → note; neither is wrong.

## Ledger

| stage | change | w0 deltas | (a) kludge-exposed | (b) bug-fixed | (c) don't-care |
|---|---|---|---|---|---|
| 1 | grid_phase primitive (inert) | 0 | 0 | 0 | 0 |
| 6 | BUSLOCK (F0) | 0 | 0 | 0 | 0 |
| 2/3 | resume-predicate gate attempts | 0 | 0 | 0 | 0 |

**Total w0 golden deltas landed: 0.** No committed change moved a w0 golden
case, so nothing required chip adjudication yet. Stages 1 and 6 are w0-neutral
by construction (grid_phase == bus_phase at w0; F0/lock_en inert on non-F0
streams). The Stage-2/3 resume-gate attempts were all w0-neutral too (eval_ext
never fires at w0) — they moved only w1/w3 drift, and all REGRESSED it, so were
reverted (see biu_rebuild_stage23.md); none landed.

**Kludge exposed but not yet replaced:** the characterization DID confirm the
audit's KB1 (`eval_ext` unconditionally resuming prefetch at T4+1) is the
dominant waits-drift kludge — but replacing it cleanly requires the free-
running-issue-phase structural model (biu_rebuild_stage23.md "The real Stage
3"), not a local gate, so no replacement is committed and no w0 delta arises
yet. The first w0/w1/w3 adjudications will come when that structural model
lands and the fitted w1/w3 golden forms move against the chip.
