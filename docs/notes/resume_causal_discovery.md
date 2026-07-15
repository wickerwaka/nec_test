# Phase 2b: prefetch-resume causal-radius discovery (controlled interventions)

Method: explicit wait-vector REPLAY on the PHYSICAL CHIP (ground truth), with
single-wait impulse experiments — a true controlled intervention, not the
confounded LFSR-seed correlation of Phase 1. Tool: `sw/causal_wrand.py`
(subcommands determ / scan / impulse / ownwait / pfdiff). Board root@mister-nec,
reflash-free, replay bitstream 8f2b45a. Programs fz90003/90007/90015/90021/90030.

## Foundational falsification checks (all PASS)

- **Chip determinism under a fixed explicit vector: PASS.** 4 repeat runs of the
  same wait-vector give BIT-IDENTICAL captures. (Falsification #8 does not hold —
  the chip is a deterministic function of the wait vector.)
- Replay fidelity: the chip applies the exact host vector (Tw per bus cycle
  matches k%4 over 225/225 accesses); chip == fabric per-access.

## Resume event: narrow definition + class separation

Resume event = a completing bus cycle whose IMMEDIATELY-following bus cycle is a
CODE fetch. gap = CODE_T1 − completing_T4. Anchored by ARCHITECTURAL ordinal
(k-th MEMR/MEMW/CODE) so a single upstream wait can't renumber the target; every
perturbed run is checked against the reference bus-stream up to the event
(generator-desync guard). Classes kept SEPARATE: Rc CODE→CODE, Rr MEMR→CODE,
Rw MEMW→CODE, Ri IO→CODE.

## Finding 1 — the resume-gap-given-stream causal radius is K = 0

Impulse: all-zero (w0) reference, flip ONE access's Tw 0→1 at offsets 0,−1,…,−K,
measure the gap change. Result, consistent across Rr and Rw, small gaps (1) and
large queue-drained gaps (5, 11), and programs 90003/90007/90015:

- **Only offset 0 (the completing access's OWN wait) is causal.** Every upstream
  offset −1..−12 is inert (Δgap = 0) or changes the bus stream (desync, skipped).
- So **K = 0**: given a fixed bus stream, the resume gap depends only on the
  completing access's own wait — no dependence on any prior access's wait, no
  accumulated history, no queue trajectory. This DIRECTLY REFUTES Phase 1's
  "bounded 5-access local window" (Codex was right: the LFSR local window merely
  correlated with the access's own wait).

## Finding 2 — the own-wait response law (additive + one bus-grid phase bit)

Own-wait sweep N=0..6 measuring resume position relative to the FIXED access T1
(CODE_T1 − access_T1, which removes the T4-shift confound). Identical shape at
every Rr/Rw anchor:

    resume(N) = base + N + (N >= 1 ? 1 : 0)

i.e. each wait delays the resume by exactly 1 (ADDITIVE — the gap-vs-T4
"saturation" was an artifact of T4 itself moving with N), PLUS a single +1
"phase kick" the instant the access is waited at all (the waited T4 lands one
bus-grid slot late). Generalizes cleanly to wmax (linear to N=6; not saturating,
not multi-phase). Per-class difference (validates not pooling): **Rc CODE→CODE
refill is own-wait-INDEPENDENT** (the completing prefetch's own wait does not
move the next refill; resume constant for all N).

## Finding 3 — the MODEL ALREADY IMPLEMENTS the resume-gap law correctly

Running the identical own-wait sweeps on the fabric core (chip vs core, same
vector): **the model reproduces the chip's resume position at every N, every
anchor, every class** (including the +1 phase kick and the Rc independence). So
the resume-gap-given-stream is NOT the bug — this whole sub-problem is already
correct in the merged RTL.

## Finding 4 — the real drift driver = prefetch-ISSUE / EU-arbitration (queue trajectory)

`pfdiff`: run the same random vector on chip and fabric, find the FIRST bus cycle
where their bus-type streams differ. Across 60 runs (5 programs × 6 wait-seeds ×
wmax∈{3,7}) only 3 diverged, and ALL share one signature:

    (chip = EU data access [MEMR/MEMW], core = CODE) after prev = CODE with Tw >= 1

i.e. after a WAITED prefetch, with an EU access pending, the CHIP performs the
EU access next, but the MODEL squeezes in one more (doomed) CODE prefetch first —
then the streams re-sync. These local reorders accumulate into the ≤15-clock
baseline drift.

Controlled confirmation (fz90003, the bus-138 waited prefetch → bus-139 divergence):
- unwait the preceding prefetch (Tw 1→0): **divergence VANISHES**.
- Tw 1→3: divergence also vanishes.
So the bug is **phase-specific**: triggered only when the preceding prefetch's
wait puts its completion on a particular bus-grid phase (Tw=1 here), not Tw=0/2/3.
This is exactly the "EU issues off fixed CPU-cycle offsets while the chip tracks
the bus grid" class (closure_checkpoint / biu_model doomed-prefetch).

## Queue-orthogonalization verdict

Two decisions with different state:
- **Resume gap (given stream): recent-READY only, no queue trajectory.** K=0,
  purely the completing access's own wait (a 1-bit "any wait" phase + the trivial
  T4 shift). No queue-occupancy dependence.
- **Prefetch-issue arbitration: joint (queue-occupancy AND recent-wait-phase).**
  It fires only when an EU access is pending (queue-occupancy signal) AND the
  immediately-preceding prefetch waited into a specific phase (recent-READY
  signal). The causal footprint is the LAST cycle's wait phase + the
  queue/EU-pending state — still small and bounded, not accumulated history.

## Minimal sufficient state (candidate small state machines)

- Resume gap: `resume = f0(queue_state@w0) + own_wait + [own_wait>=1]` — the w0
  gap (already modeled) plus the access's own wait plus a 1-bit phase kick.
- Prefetch-issue: a small **bus-grid-phase latch** (the phase at which the
  current bus cycle completes, advanced by wait states) gating the
  prefetch-vs-EU arbitration when the queue is near-full / an EU access is
  pending. The model currently arbitrates off fixed CPU-cycle offsets and so
  admits an extra prefetch at the Tw=1 phase.

## Honest verdict

- A **finite causal radius is PROVEN for the resume gap: K = 0** (own access wait
  only), across classes, programs (incl. held-out 90015), and wmax — and the
  model is ALREADY correct there. This closes the sub-problem the campaign framed
  as "the resume law."
- The residual drift is the **prefetch-ISSUE arbitration**, localized to a single
  reproducible signature (extra doomed prefetch before a pending EU access at a
  specific waited-prefetch phase), confirmed causal by controlled flip, with a
  small bounded footprint (last-cycle wait phase + queue/EU-pending). It is NOT
  unbounded history.
- Remaining for Phase 3 (RTL, not discovery): build the full predictive
  bus-grid-phase model of the prefetch-issue arbitration and validate it against
  the controlled interventions on held-out programs, then re-fit the RTL
  (w0..wN unified, no waited exception) and re-measure vs fresh chip traces.

Tools: `sw/causal_wrand.py`. Repro examples:
`python3 sw/causal_wrand.py determ --seed 90003`;
`... impulse --seed 90007 --anchor-bus 59 --k 12`;
`... ownwait --seed 90003 --anchor-bus 137 --core`;
`... pfdiff --seed 90003 --wseed 2 --wmax 3`.
