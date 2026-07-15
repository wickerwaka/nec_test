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

---

# Phase 2c — corrections + deepened arbitration discovery

Codex flagged 3 overclaims in Phase 2b. All corrected below; the reframe (resume
gap already correct; real defect = prefetch-vs-EU arbitration) stands and is now
mechanistically characterized. New tool subcommands: `impulse` (fixed +
intervention matrix + timing-K/decision-K), `arbsweep`, `arbscan`, `align`.

## Correction 1 — K=0 is the TIMING radius only (qualified)

The impulse tool had a bug (found next CODE, not the IMMEDIATE successor) —
fixed to require the immediate ->CODE resume for reference and intervention.
Re-run with a per-offset INTERVENTION MATRIX (stream-preserved-inert /
stream-preserved-gap-changed / stream-changed / anchor-lost):

- **TIMING-K = 0**: under STREAM-PRESERVED single-wait flips, the resume gap
  changes only for offset 0 (the completing access's own wait). Correct
  restatement: *for immediate MEMR/MEMW→CODE events, the conditional resume
  timing given a fixed bus stream has K=0.*
- **But upstream waits DO causally alter the ISSUE/ARBITRATION decision**
  (stream-changed cells, DECISION-K > 0). That is exactly Finding 4 — it is a
  real causal outcome, not a skip. Timing-radius and arbitration-radius are
  distinct; K=0 is only the former.

## Correction 2 — divergence-class inventory (aligned, not one first-mismatch)

`align`: SEQUENCE-ALIGN chip vs core bus streams by (bs, ADDRESS) with
difflib, classify every edit op, exclude the post-program idle tail. Corpus 5
programs × 6 wait-seeds × wmax∈{1,3,7,15} (120 runs), 86 in-program edit-ops:

    core-INSERTS CODE  35   |  core-OMITS CODE  28   |  REORDER CODE  4   (= 78%)
    IOW/MEMR/MEMW insert/omit ~19  (downstream cascades of a CODE divergence)

So it is essentially **ONE mechanism — a CODE prefetch issued/omitted wrong**,
and it is **BIDIRECTIONAL** (the model both over-prefetches AND under-prefetches
depending on context; Phase 2b's "extra prefetch" was only one sign). The
EU-access edits are cascades once the prefetch stream diverges. No
same-type-wrong-address class appeared (fetch addresses match where aligned).

## Correction 3 — NOT a one-bit phase/parity latch (REFUTED); it is a slack boundary

The decisive experiment (`arbsweep`/`arbscan`): at each CODE→EU anchor, sweep the
preceding CODE's wait N=0..15 (fixed background) and record the chip's decision
(prefetch-first vs EU-next). Result across 96 anchors (4 programs × 3 backgrounds):

- The chip's decision is a **step**: prefetch-first for N < N*, EU-next for
  N ≥ N* — a real arbitration BOUNDARY N* in preceding-CODE-wait units.
- **N* varies by anchor: {N*=1: 14 anchors, N*=2: 2 anchors}.** A fixed
  phase/parity latch would give a single N* everywhere — REFUTED. (Phase 2b's
  "Tw=1 diverges, Tw=3 doesn't" was simply N=1 sitting on the chip's boundary at
  those anchors.)
- **N* is STABLE across wait backgrounds** (bg 2/5/7/11 give the same N* per
  anchor) → N* is set by the ARCHITECTURAL / queue state at that program point,
  not by the wait history. It does NOT reduce to coarse proxies (anchors with
  equal idle-gap=8 have N*=1 and N*=2; CODE-run-length doesn't track it either)
  → the state is a finer queue-occupancy + EU-request-age coupling.

## The model bug, precisely

`arbscan` flags the divergent cells: at anchors where the chip's boundary is
N*=1, the MODEL's boundary is N*=2 (e.g. fz90007 CODE@bus45 across bg 2/5/7:
chip EU-next at N=1, core still prefetches). The model computes the prefetch
slack **±1 wrong** — it grants one extra prefetch opportunity the chip does not
(and, per the aligned inventory, sometimes one too few). This ±1 boundary error,
fired repeatedly, is the ≤15-clock accumulating drift.

## Minimal sufficient state (narrowed, not yet closed)

- The arbitration boundary N* is a small bounded integer (observed ≤ 2),
  per-anchor stable across wait backgrounds → a QUEUE-FILL / prefetch-opportunity
  count set at w0, with the preceding CODE's wait consuming realized
  opportunities. It is NOT a phase/parity latch.
- Full closed-form (which exact bytes-in-queue + request-age combination yields
  N*=1 vs 2) is NOT yet pinned: coarse proxies fail, so it needs finer queue
  reconstruction AND instruction-variant control to dissociate request-age from
  queue-fill (the two are confounded across the fixed fuzz anchors). That
  dissociation is the first Phase-3-discovery step before RTL.

## Honest verdict (Phase 2c)

- Resume-gap sub-problem: **CLOSED** (timing-K=0, model already correct).
- Drift defect: **one bidirectional mechanism** — a prefetch-vs-EU arbitration
  BOUNDARY the model computes ±1 wrong. The chip's boundary is a small (≤2),
  architecturally-determined, wait-background-stable slack count; **a fixed
  phase/parity latch is refuted**; the exact queue+request-age state is narrowed
  but not yet closed-form.
- Phase 3 (not RTL yet): dissociate request-age vs queue-fill with instruction
  variants + finer queue reconstruction to close the boundary predictor, then a
  unified w0..wN arbiter whose prefetch-vs-EU boundary tracks the bus-grid/queue
  state (a cycle-experienced-Tw / queue-slack count), validated against these
  controlled interventions on held-out programs.

Tools: `sw/causal_wrand.py`. Repro examples:
`python3 sw/causal_wrand.py determ --seed 90003`;
`... impulse --seed 90007 --anchor-bus 59 --k 12`;
`... ownwait --seed 90003 --anchor-bus 137 --core`;
`... pfdiff --seed 90003 --wseed 2 --wmax 3`;
`... arbsweep --seed 90003 --anchor-bus 138 --bgseed 2 --maxn 15`;
`... arbscan --seeds 90003 90007 90015 --bgs 2 5 7 --maxn 6`;
`... align --seeds 90003 90007 90015 90021 90030 --wmaxes 1 3 7 15`.
