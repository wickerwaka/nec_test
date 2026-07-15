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

---

# Phase 2d — discovery gate (corrects a Phase-2c overclaim; gate NOT yet closed)

New infra: exact-as-possible QUEUE RECONSTRUCTION (`build_cycles`: fetch width by
address parity even=2/odd=1 byte, QS F/S pops = -1, QS E = flush, capped at the
6-byte V30 queue - stays in [0,6]); ARCHITECTURAL anchor identity (EU access
addr+bs+ordinal, wait-invariant); subcommands `arbpop`, `episodes`.

## Correction to Phase 2c: N* is QUEUE-driven, NOT wait-background-stable

Phase 2c claimed "N* stable across backgrounds => architectural / wait-history-
independent." That was an ARTIFACT of testing only random backgrounds (r2/r5/r7),
which collapsed to the same local queue regime. Re-run with DIVERSE backgrounds
(all-0, all-1, all-wmax, alternating) and UNIQUE-anchor accounting (keyed by EU
identity, not bus index): 29 unique EU-anchors (11 variant / 18 invariant; the
Phase-2c "14 vs 2" was the same anchors counted once per background).

**N* tracks the reconstructed queue occupancy entering the EU decision**, per
architectural anchor (matched instruction, varied background => occ_in varies =>
N* moves, monotonically):

    occ_in 2 -> N* in {1,2,3}   occ_in 3 -> {0,1,2}   occ_in 4 -> {0,1}
    occ_in 5 -> {0}             occ_in 6 -> {0}

i.e. a FULL queue (occ 5-6) => the chip goes straight to the EU (N*=0, no
prefetch); an EMPTY-er queue (occ 2) => the chip prefetches first and needs 1-3
waits to suppress it. This is Codex's factorial experiment B (match the EU
access/request path, vary queue fill): **queue-slack is a confirmed CAUSAL
driver of the prefetch-vs-EU boundary.** So the arbiter IS queue-eligibility
driven (consistent with the w0 priority: split-half, ready EU, then prefetch).

## But queue-fill is NOT sufficient — a second variable remains (gate OPEN)

- Residual at fixed occ_in: occ=2 gives N* in {1,2,3}, occ=4 in {0,1} - the same
  reconstructed occupancy yields different boundaries, so occupancy alone does
  not determine the decision.
- Episode analysis (one-vs-two mechanisms, #4): over-prefetch (core inserts
  CODE, 34) and under-prefetch (core omits CODE, 28) OVERLAP in occupancy (both
  peak at occ_in=4: OVER {0:5,2:8,3:6,4:14,5:1}, UNDER {2:4,3:7,4:16,5:1}). A
  single occupancy threshold placed wrong would put the two signs in
  COMPLEMENTARY regimes; the overlap means coarse occupancy does NOT separate
  them. So the one-vs-two-mechanism question is UNRESOLVED without a finer state
  (request-age / in-flight bytes / fetch-parity phase).

## Honest verdict (Phase 2d) — NOT closed

- CONFIRMED: the prefetch-vs-EU arbitration boundary is driven by queue slack
  (corrects Phase 2c). The model's error is a boundary misplacement, BIDIRECTIONAL
  (over- AND under-prefetch, ~equal counts) - it mis-tracks the chip's
  queue-eligibility threshold.
- OPEN (blocks RTL): (a) queue-fill is necessary but not sufficient - a second
  variable at fixed occupancy is unresolved; the request-age-vs-queue FACTORIAL
  (experiment A: match queue, vary reservation onset via reader/store/RMW/EA
  variants) is NOT done - the base fuzz corpus lacks the matched-queue/varied-
  request strata; (b) the queue reconstruction is approximate (parity width; no
  explicit in-flight/discarded-fetch/aging model) and may itself cause the fixed-
  occ residual; (c) held-out families (RMW read->write, odd split, string, push
  chains, IO, branch/flush) not exercised - base menu only; (d) no validated
  exact-decision predictor (CODE-vs-EU + count + clock + address).
- Bottom line: the arbitration rule is NOT yet a single validated state->decision
  transition. Queue-slack is established as the dominant axis; closing requires
  the factorial request-age dissociation + a finer queue model + held-out-family
  validation before any RTL.

---

# Phase 2e — closing gate via RTL internal state (rule NOT yet closed; request-age pinned)

Codex flagged that the external queue reconstruction had a push-timing bug that
could manufacture the fixed-occ residual. Rather than debug an approximate
external model, I PIVOTED to the RTL's OWN state: the Verilator TB dumps the
exact queue-pipeline internals via `+eudbg` (occupied, q_aged, infl, q_cnt,
q_avl, eu_req, eu_ready, eval_ext), and the TB is bit-identical to the fabric,
so UP TO THE FIRST CHIP DIVERGENCE the model's internals EQUAL the chip's. This
gives the true `occupied` (= cnt_next + infl, the RTL eligibility quantity) with
zero reconstruction error. Tool: `predicate` (+ `run_tb_internal`). Anchor
identity fixed (Step 2): keys now include the program seed.

## The collision test (Step 3) — 21,070 aligned chip CODE/EU decisions

Keying the chip's CODE-vs-EU decision by the model's fielded state:
- (occupied, q_aged, eu_req, consuming): 23 cells, **10 COLLISIONS**.
- + eu_ready: 9 collisions. + eval_ext: collisions REMAIN.
The collisions are heavily lopsided (eu_req=1 -> mostly EU; eu_req=0 & occupied
low -> mostly CODE), i.e. the chip decision is ALMOST a function of
(occupied, eu_req) but a residual minority defies it. **NOT collision-free** ->
per Codex's decision rule, a request-age / arbitration-phase variable is NECESSARY.

## One mechanism, and it is the waited-window override + late EU-request (Step 5)

- **All 27 first-divergences are OVER-prefetch** (chip goes EU, model issues a
  CODE prefetch). The under-prefetch edit-ops seen in the Phase-2d aligned
  inventory are therefore CASCADES downstream of an over-prefetch, not an
  independent mechanism. -> ONE primary mechanism.
- **eval_ext = 1 at 21/27 divergences**: the model's deferred-completion
  waited-window prefetch override (`prefetch_ext`, v30_biu) is what issues the
  doomed prefetch. In the dominant cell (occ=4, eu_req=1, consuming=1, 10 cases)
  the model prefetched DESPITE eu_req=1 - which plain `prefetch_ok` forbids
  (!(eu_req)) - so it can only be the eval_ext override bypassing the ready-EU
  priority.
- **eu_ready = 0 at ALL 27 divergences** while the chip goes EU: the chip's EU
  request is ready by the decision edge, but the model's readiness signal has
  not asserted. So the model's eu_req/eu_ready assert TOO LATE relative to the
  chip -> the model prefetches in the gap. This is the REQUEST-AGE variable,
  identified directly (converging with Codex's Factorial-A prediction without
  yet running the reader-vs-store pair).

## Honest bottom line (Phase 2e)

- Is the decision COLLISION-FREE over the corrected full state? **NO.** The
  model's queue-pipeline state (RTL-exact `occupied` etc.) + eu_req + eu_ready +
  eval_ext does NOT determine the chip decision (10 residual colliding cells).
- What remains (the exact missing field): the CHIP's true **EU-request-ready
  edge (request-age)** - the model's eu_req/eu_ready assert later than the chip's
  actual readiness, and the **eval_ext waited-window prefetch override** issues a
  prefetch in that window, violating the ready-EU-beats-prefetch priority.
- Mechanism count: **ONE** (over-prefetch via the eval_ext override; under-prefetch
  is cascade).
- NOT ready for RTL. Phase 2f (still discovery) should: (a) run the clean
  Factorial-A reader-vs-store (8B07 vs 8907) at matched queue state to confirm
  request-age causally and MEASURE the chip's request-ready timing vs the model's
  eu_req edge; (b) with the measured request-age class added, re-run the collision
  test for collision-freeness; (c) then fit + validate the exact decision table
  (held-out anchors + invariant anchors + the single over sign). The likely RTL
  target (Phase 3, not now) is the eval_ext override's EU-request priority /
  eu_req assertion timing, unified across w0..wN.

---

# Phase 2f — no-competition control (Hyp A ruled out; B favored; not yet closed)

Method correction accepted: external equivalence is many-to-one, so RTL internals
label the MODEL only, never the chip. All Phase-2f measures are CHIP-OBSERVABLE
(bus type + QS F/S pop pulses + absolute clocks); RTL internals only label the
model side. Tool: `nocomp`.

## Step 1 (the crux) — no-competition control

At reproducible over-prefetch anchors, measure EU-T1 relative to the final
instruction-byte pop (QS F/S) across diverse backgrounds, and compare chip vs
model in cells where NEITHER side prefetched (mutual no-competition - clean of
arbitration):

- fz90003 (target MEMW@03efe): 4/4 mutual cells chip lat == model lat EXACTLY;
  the over-prefetch cell (r7) has chip EU lat=5 = its no-competition baseline,
  with the model inserting an EXTRA prefetch (+6 clk).
- fz90030 (target MEMR@02624): mutual cell matches; divergence cells show the
  chip issuing EU on its baseline schedule, model inserting a prefetch (+3/+5).
- fz90007: mutual cells differ by +/-1 in BOTH directions (chip earlier AND later)
  = measurement noise in the coarse final-pop/EU-T1 anchor, not a systematic lead.

**Verdict: Hypothesis A (chip EU readiness/issue genuinely EARLIER) is RULED OUT
in its strong/systematic form** - with no competition the chip and model issue
the EU access at the SAME latency from the final byte pop. The divergence is the
model inserting an EXTRA prefetch while the chip issues EU on its normal schedule
and **leaves the queue-eligible slot UNUSED (reserved for the pending EU)** ->
consistent with **Hypothesis B (pending-reservation priority over prefetch)**.
Caveat: the coarse fuzz-latency measure carries +/-1 noise, so a 1-cycle
readiness component cannot be excluded, and B-vs-C is not fully separated by this
control alone.

## What remains (the decisive Step-2 experiment, not yet run)

The reader/store Factorial-A (8B07 MOV AX,[BX] vs 8907 MOV [BX],AX: equal length,
same no-disp EA, reader reserves from S_EA1 / store from S_EA2) at MATCHED
queue-pipeline state is required to (a) confirm reservation/request AGE causally
and (b) cleanly separate B (distinct pending-reservation signal: chip suppresses
CODE one cycle BEFORE it can issue EU-T1) from C (arbitration edge premature).
The observable-measurement tooling is built (`nocomp`); the controlled-image
construction needs the harness's NEC-named full register setup + precise anchor
placement + queue-state bucketing (a focused mini-campaign) - flagged for Phase 2g
rather than rushed (a wrong B/C answer would mis-target the RTL fix).

## Honest bottom line (Phase 2f)

- **Hyp A ruled out** (strong form): EU readiness/issue timing is correct; the
  defect is ARBITRATION, not readiness. RTL target is NOT eu_ready timing.
- **Hyp B favored**: the chip reserves the bus for a pending EU request and
  suppresses the queue-eligible prefetch; the model (via the eval_ext waited-
  window override, 21/27) issues that prefetch instead. ONE mechanism.
- **Not closed**: B-vs-C needs the reader/store factorial; a 1-cycle readiness
  component isn't excluded by the coarse control. No collision-free table yet.
  Phase 2g: run Factorial-A at matched queue state, resolve B/C + any 1-cycle
  readiness, then fit+validate the decision table. Likely RTL target (Phase 3):
  a pending-EU-reservation priority that gates prefetch across w0..wN (replacing
  the eval_ext priority-bypassing override), pending the factorial.

---

# Phase 2g — LEA no-request control: B DECIDED over C (arbitration edge exists)

Codex: 'chip reserves an eligible slot' had not yet proven the chip ARBITRATES at
that slot (B) vs has no decision edge there (C). The no-request LEA control
settles it. Tool: `leactl` (builds a matched 3-variant block via testimage with
the correct NEC-named registers).

## The control (Step 1)

Matched block at one anchor (BW=0x0200, ModRM 07, data seeded at 0x0200):
  reader 8B07 mov AW,[BW]   - reserves early (S_EA1)
  store  8907 mov [BW],AW   - reserves later (S_EA2)
  lea    8D07 lea AW,[BW]   - same 2-byte ModRM/EA decode, NO EU bus request
At the disputed edge E (the bus cycle right after the ModRM byte is delivered),
sweeping the ModRM-delivery fetch's wait N=0..8:

    lea    -> CODE at E   (a prefetch IS issued: E is a real opportunity)
    reader -> EU   at E   (the pending read request suppresses the prefetch)
    store  -> EU   at E   (the pending write request suppresses the prefetch)

**Verdict: Hypothesis B, C refuted.** E is a REAL arbitration edge - the
no-request LEA variant proves a prefetch is eligible there - and a PENDING EU
request SELECTIVELY suppresses it (reader/store issue their access instead). If E
had no decision edge (C), LEA would not prefetch there either; it does. So the
chip's rule at E is: pending-EU-reservation takes priority over an otherwise-
eligible prefetch.

## What Phase 2g did NOT close (honest)

- **Reservation-AGE threshold (Step 2): NOT measured.** At this clean minimal
  block the reservation is always old-enough: reader AND store both suppress at
  every N, and the MODEL AGREES (no divergence). So the model is not
  "always over-prefetch" - its error is confined to the YOUNG/coincident-
  reservation boundary (the pf_late_rsv region, v30_biu), which this bare
  post-flush block never reaches (single waits on the surrounding fetches
  produced zero chip-vs-model divergence). Measuring the age threshold (how old
  a pending reservation must be to block prefetch, per read/write/RMW/string/IO)
  requires reproducing the young-reservation condition - a queue-fill setup or
  anchoring on the fuzz divergences.
- **6 non-eval_ext cases (Step 3):** not yet localized at the true commit strobe.
- **A-exclusion tightening (Step 4):** partial (Phase 2f coarse control).
- **No collision-free decision table yet.**

## Honest bottom line (Phase 2g)

- **A retired** (Phase 2f): the defect is arbitration, not EU readiness.
- **B decided over C** (Phase 2g LEA control): there IS an arbitration edge at E,
  and a pending EU request selectively suppresses an eligible prefetch. The RTL
  target is the **pending-EU-reservation priority** over prefetch - which the
  eval_ext waited-window override bypasses.
- **NOT fully closed:** the exact reservation-AGE threshold (the precise rule -
  pf_late_rsv deliberately lets a too-young request lose to CODE) is unmeasured;
  the 6 non-eval_ext cases and the collision-free table remain. Phase 2h:
  reproduce the young-reservation boundary (queue-fill or fuzz-divergence-
  anchored) to measure the per-access-type age threshold, localize the 6, then
  fit + validate the table. Phase-3 RTL target (design note): ONE arbitration
  transition f(request_state, fetch_state) at every legal edge, with a
  reservation-age-gated pending-EU priority, eval_ext demoted to an edge label -
  pending the threshold measurement.

---

# Phase 2h — the IDLE-SLOT proof of B's failing form (mechanism identified)

Codex: the clean LEA block showed ORDINARY ready-EU priority (reader/store ready
at E), not the young/coincident case that FAILS. Phase 2h reproduces the young
boundary from the real fuzz divergences and finds the idle-slot signature. Tool:
`idleslot` (raw per-CPU-cycle T-state + RTL commit state at over-prefetch
divergences).

## The idle-slot proof (Steps 1-2)

Example (fz90007, waited CODE@00510 then the disputed edge):

    CHIP : CODE(1 Tw) T4 -> Ti Ti (TWO idle PASV cycles) -> MEMR@023fc
    MODEL: CODE(1 Tw) T4 -> Ti CODE@00512 (eval_ext commit, req1 rdy0) -> ...
                           doomed prefetch -> MEMR@023fc

Over 8 confirmed over-prefetch divergences (fz90003/07/15/21/30):
- **The chip inserts >=1 IDLE (Ti) slot in 8/8** (3-4 idle cycles) where the
  model issues the doomed prefetch. => **B's FAILING form is PROVEN**: a pending
  EU reservation that is NOT yet ready makes the chip IDLE (reserve the bus)
  rather than prefetch; it is not merely ordinary ready-EU priority.
- **eval_ext = 1 at the commit in 8/8** (sampled at the ACTUAL model CODE-T1, not
  T1-1): the doomed prefetch is always the waited-completion override.
- Reservation state at the model's commit: **eu_req=1 & eu_ready=0 (pending but
  UNREADY) in 6/8**; eu_req=0 (request registered too late) in 2/8. Both are the
  eval_ext override failing to respect the chip's pending EU reservation.
- Queue occupancy at the commit: occ in {2,4} - **ELIGIBLE and NON-URGENT** (not
  the empty/starved string regime that pf_late_rsv was fitted for, v30_biu:420).

## The rule, and the model's exact error

Chip rule (measured, non-urgent eligible regime): a PENDING EU reservation - even
before it is ready - takes priority over an eligible prefetch; the chip IDLES
until the EU can issue. The model's eval_ext override instead lets the prefetch
win when the reservation is unready/late (pf_late_rsv's "young loses to CODE",
which is CORRECT only in the urgent/starved string regime). So the defect is:
**the eval_ext override applies the young-loses-to-CODE rule in the NON-URGENT
regime, where the chip actually reserves+idles.** ONE mechanism; two request-state
manifestations (pending-unready vs registered-late).

## What is now bounded vs still open

- **CLOSED (mechanism):** over-prefetch = the eval_ext waited-completion override
  issuing a prefetch when a pending (unready/late) EU reservation should reserve
  the bus; the chip's proof is the idle slot. RTL target: gate the eval_ext
  override so a pending EU reservation suppresses the prefetch in the non-urgent
  regime, WITHOUT regressing the urgent/starved string case (pf_late_rsv) or RMW
  (ext_ok_wr) that the override was fitted for.
- **STILL OPEN (for a formal closure/table):** the exact reservation-age x
  queue-URGENCY x access-KIND boundary (I measured the non-urgent eligible
  regime; the urgent/string boundary where young SHOULD lose to CODE needs the
  string/RMW comparison); the Phase-2e "6 non-eval_ext" - at the corrected commit
  strobe all 8 here are eval_ext, so those 6 were likely the T1-1 sampling
  artifact, but not confirmed against the exact 27; the w0 young-cell
  re-measurement; a formally validated collision-free table on held-out families.

## Honest bottom line (Phase 2h)

- **A retired; B decided over C; B's failing form PROVEN** (universal idle-slot
  signature). The mechanism and RTL target are now concrete: the eval_ext
  override must respect a pending EU reservation (reserve/idle) in the non-urgent
  regime, preserving the urgent/string/RMW exceptions.
- **Not yet a formally-closed bounded TABLE:** the urgency x access-kind threshold
  boundary and held-out validation remain. Phase 2i (if required before RTL):
  map the urgency/access-kind boundary (string/RMW/IO) so the Phase-3 fix does
  not regress the cases pf_late_rsv/ext_ok_wr were fitted for; re-measure w0 young
  cells vs chip. Phase-3 design target (unchanged): ONE age+urgency-aware
  arbitration transition at every edge, eval_ext demoted to an edge label.

---

# Phase 2i — the urgency predicate MEASURED: q_cnt, not occupied

Codex: 'non-urgent' was inferred from occupied in {2,4}, not a measured predicate.
Phase 2i measures it. Tool: `urgency` (classifies the chip's IDLE-vs-CODE action
at waited-CODE->EU contested edges vs the aligned queue-pipeline state, filtered
to reservation-pending edges).

## Result: occupied is the WRONG abstraction; q_cnt is the urgency variable

Over 4620 contested edges, NO single queue field (occupied / q_avl / q_cnt) nor a
chip-observable reservation-age proxy separates IDLE from CODE - all MIXED. The
conflation was reservation-ABSENT edges (ordinary prefetch) mixed with
reservation-PENDING (contested) ones. Filtering to the RESERVATION-PENDING subset
(eu_req=1 at the decision edge), 1366 edges:

- **The chip IDLEs (reserves) in 1326/1366 = 97%** - pending-reservation priority.
- **At q_cnt >= 2 the chip reserves in 346/346 = 100% (zero CODE).**
- The 40 CODE-despite-reservation cases are ALL at **q_cnt <= 1**.

Because occupied=2 spans q_cnt in {0,1} (occupied counts in-flight `infl` bytes)
while q_cnt>=2 is clean, **`occupied` is the wrong abstraction - the urgency
variable is q_cnt (COMPLETED/poppable bytes); in-flight bytes do not count toward
"the queue can feed the decoder."** This is a MEASURED predicate, not occupied<=X.

## The urgent regime (q_cnt <= 1) - a finer residual

q_cnt<=1 pending edges: 1020, of which 980 IDLE / 40 CODE (96% still reserve). The
40 CODE cases cluster at YOUNG reservation ages (resage 0-3; at resage>=4 the chip
always reserves) but the coarse chip-observable resage proxy does not fully
separate them - they are the near-starved string/RMW urgent-refill region that
pf_late_rsv (v30_biu:420) and ext_ok_wr (:388) were fitted for. The exact
sub-rule there needs the finer imminent-consumption / access-kind signal.

## The measured rule + the RTL target

- **Non-urgent (q_cnt >= 2): a pending EU reservation ALWAYS reserves the slot
  (IDLE), deterministic.** This is the dominant over-prefetch drift and it is
  CLEANLY measured.
- **Urgent (q_cnt <= 1): mostly reserve, but a young reservation can lose to CODE
  (~4%)** - the string/RMW near-starved region, handled by the existing
  pf_late_rsv/ext_ok_wr.
- **Phase-3 change (concrete, measured):** replace pf_late_rsv's BROAD "late
  reservation yields to CODE" with "yields to CODE only when q_cnt <= 1
  (measured near-starved)". q_cnt>=2 must reserve (IDLE). This fixes the
  non-urgent over-prefetch while preserving the urgent/string/RMW cases the
  override was fitted for. `measured_refill_urgent := (q_cnt <= 1)`.

## Honest bottom line (Phase 2i)

- **Urgency predicate MEASURED: q_cnt (completed poppable bytes), threshold
  q_cnt>=2 => always reserve.** `occupied` refuted (it conflates completed with
  in-flight bytes). This is the measured gate Phase 3 needs.
- **Substantially CLOSED** for the dominant (non-urgent) drift: the arbitration at
  a pending reservation is q_cnt-gated, collision-free at q_cnt>=2.
- **Residual (small, bounded):** the q_cnt<=1 urgent sub-rule (~4% of pending
  edges) is not separated by coarse proxies - it is the string/RMW region the
  current RTL already handles, so the Phase-3 change (gate on q_cnt<=1) preserves
  it. Also unclosed: the 2/8 eu_req=0 late-registration cases (EU reservation-
  ONSET timing, a possible distinct EU-side site) and the w0 young-boundary
  chip re-measurement.
- **Phase 3 justified** for the measured non-urgent fix (q_cnt-gated reservation
  priority replacing broad pf_late_rsv), with the urgent sub-rule + req0 onset
  timing as follow-ups. Phase-3 arbiter (Codex): split-cont -> ready-EU ->
  EU-reservation-owns-slot(IDLE) -> urgent-refill(CODE, gated on q_cnt<=1) ->
  ordinary-prefetch(CODE) -> IDLE; eval_ext = edge label only; preserve ext_ok_wr;
  validate w0 vs fresh chip traces.

---

# Phase 2j — SAMPLER FIX overturns Phase 2i; q_cnt edit is a NO-OP; real gate = read/write

Codex flagged the Phase-2i sampler bug: q_cnt was read at the completing-CODE T4
row but eu_req one cycle later, and q_cnt advances every CPU edge. Fixed: added
eu_req_p1 / pf_late_rsv / pf_starved / prefetch_ext / prefetch_ok to the eudbg
dump (tb_v30_core) and re-measured with ALL gate inputs sampled LIVE on the same
eval_ext decision row. Branch: biu-arb-qcnt.

## Corrected measurement (11,515 contested edges, live eval_ext-row sampling)

Action by request-age class at the eval_ext row:
- absent (eu_req=0): CODE 8092 / IDLE 8  (no reservation -> prefetch, correct)
- ready (eu_ready=1): IDLE 3294 / CODE 0  (ready-EU priority, correct)
- young  (eu_req=1, eu_req_p1=0, coincident): CODE 109 / IDLE 12

YOUNG reservations, keyed by (q_cnt_eval, access family) - **0 collisions**:
- q_cnt=0, MEMR: CODE 62   q_cnt=0, MEMW: CODE 23   (urgent refill, both prefetch)
- q_cnt=1, MEMR: **IDLE 12**   q_cnt=1, MEMW: CODE 24

## Two conclusions that CHANGE the plan

1. **The Phase-2i "q_cnt>=2" claim was a SAMPLER-BUG ARTIFACT.** With live
   sampling, young/coincident reservations occur ONLY at q_cnt<=1, and
   **pf_late_rsv fires ONLY at q_cnt<=1 (0 firings at q_cnt>=2, over 109
   firings).** So the proposed `pf_late_rsv &&= (q_cnt<=1)` edit is a NO-OP -
   it removes nothing. Per Codex's stop-condition (q_cnt>=2 not actionable),
   **NO EDIT MADE.**
2. **The real over-prefetch bug, precisely:** pf_late_rsv fires for young
   ORDINARY READ reservations at q_cnt=1 (12/12 chip IDLE = the chip reserves the
   read; the model prefetches = over-prefetch). Ordinary WRITES at q_cnt=1
   (CODE 24) and BOTH at q_cnt=0 (urgent refill) correctly prefetch. The RTL
   pf_late_rsv condition `eu_mem_acc && eu_kind==K_MEM` does NOT distinguish
   read from write, yet its own comment calls it "the fitted WRITE-half
   reservation law" - it is wrongly applied to reads. **The discriminator is
   read-vs-write at q_cnt=1, NOT q_cnt<=1.**

## Why I did NOT make an edit (and what's needed first)

- The pre-approved edit (q_cnt<=1) is a no-op; making it would be theater.
- The measured fix (gate pf_late_rsv to exclude ORDINARY reads) is promising but
  UNVALIDATED against the FITTED cases: pf_late_rsv was fitted on REP-string
  seeds (a4/a5/ab/ac/ad = MOVS/STOS/LODS), which include string READS (LODS).
  My corpus is the base fuzz menu (ordinary loads/stores, NO string ops), so
  "reads reserve at q_cnt=1" is measured for ORDINARY reads only. A string LODS
  read may LEGITIMATELY lose to CODE (pf_late_rsv correct there) - so the real
  discriminator may be ORDINARY-vs-STRING, not plain read-vs-write. Editing on
  the plain read/write split risks regressing the string cases pf_late_rsv was
  fitted for. The Step-2 FITTED-CASE INVENTORY (pf_late_rsv firings in golden
  string/RMW traces, by family + q_cnt) MUST run before any edit.

## Correction to the above: the read/write split was an EDGE-MATCHING ARTIFACT

The "young MEMR reserves / MEMW prefetches at q_cnt=1" split used the CHIP's next
ARCHITECTURAL access as the family label. Adding `eu_wr` to the eudbg dump and
re-keying by the RTL's ACTUAL reservation direction at the eval_ext row shows:
**every young q_cnt=1 reservation is eu_wr=1 (a WRITE) at that row**, and those
writes are MIXED (12 IDLE / 24 CODE). So `eu_wr` does NOT separate them - the
apparent read/write split was the edge-finder pairing the eval_ext reservation
with a DOWNSTREAM architectural access of a different type, not the reservation's
own access. I made the `&& eu_wr` edit, validated it (golden w0 169000, w1/w3
1200/1200 - safe), but it did NOT remove the over-prefetch divergences (they are
eu_wr=1), so it is INEFFECTIVE. **Edit REVERTED; RTL back to baseline.**

## Honest bottom line (Phase 2j) - NOT closed, NOT flash-ready

- **Sampler fixed; Phase-2i conclusion overturned.** pf_late_rsv fires only at
  q_cnt<=1; the pre-approved q_cnt<=1 edit is a NO-OP (0 firings at q_cnt>=2).
- **The read/write edit is INEFFECTIVE** (divergent cases are eu_wr=1 writes);
  reverted. It was an edge-matching artifact, not a real discriminator.
- **A real COLLISION persists at the reliable state:** at (q_cnt=1, young
  coincident reservation, eu_wr=1, eval_ext) the chip both IDLEs (reserves, 12)
  and prefetches (CODE, 24) - and NO measured RTL-observable field (q_cnt, occ,
  eu_wr, eu_req, eu_req_p1, eu_ready, q_aged, infl) separates them. So the
  arbitration decision is NOT a function of the currently-measured state.
- **Root measurement issue:** the edge-finder must associate the eval_ext
  reservation with ITS OWN pending access (identity/kind/age), not a downstream
  architectural access. Until the reservation is correctly identified per edge,
  the discriminator can't be measured. The hidden variable is likely the precise
  reservation ONSET/age or the specific pending-access microstate - needing the
  controlled per-access-family experiment (reader/store/RMW/string with a
  young reservation), not the fuzz scan.
- **No actionable edit. NOT flash-ready.** The predicate is NOT closed; the
  q_cnt and read/write hypotheses are both refuted at the reliable state. Report
  to Codex: the closure needs correct per-edge reservation identification, then
  the collision re-tested; the 2/8 eu_req=0 cases and w0 re-measurement remain
  separate follow-ups.

# Phase 2k — the collision RESOLVED: discriminator = reservation SOURCE (+ q_cnt)

Codex's verdict on the Phase-2j collision was correct: the coarse `eu_req_p1==0`
"young" bit conflates ~10 different EU reservation-generating microstates, and
the discriminator is the reservation's OWN SOURCE (+ onset age). Phase 2k added
RESERVATION-ONSET INSTRUMENTATION (TB-only, measurement; no functional RTL
change) and MEASURED it. **The collision is resolved: the discriminator is the
reservation SOURCE (the EU state at the eu_req rising edge), collision-free when
keyed with q_cnt. Onset AGE is NOT the discriminator; q_avl/q_aged are not
needed.**

## Instrumentation (measurement only)

`hdl/tb/tb_v30_core.sv`: on every `eu_req` RISING edge, latch the EU state
generating it (`onset_state` = the reservation's own source, e.g.
S_EA1/S_EA2/S_DISP8/S_DHI/S_MHI/S_RSV/S_RMWX/S_DEC/S_PUSH_CALC/...), the
absolute CPU clock (`onset_clock` -> exact onset age), and the opcode/kind/dir
at onset. Carried until eu_started/withdrawal/flush. The dumped fields are
computed COMBINATIONALLY on the onset cycle (eu_req rises ON this row ->
onset_state=current state, age=0) so a withdrawal/reassert cannot alias the
age-0 case. Appended to `+eudbg` (5 new fields: onset_state onset_age onset_opc
onset_kind onset_wr). Golden path UNCHANGED: check_core 169000/169000 full.
`sw/causal_wrand.py`: new `onset` subcommand + STATE_NAMES parsed from v30_eu.sv.

## The two collision exemplars (extracted + chip-verified, Step 2)

Both have IDENTICAL coarse state at the eval_ext decision row - q_cnt=1, q_avl=1,
q_aged=0, eu_req=1, eu_req_p1=0, eu_ready=0, eu_wr=1, pf_late_rsv=1 - and differ
ONLY in the reservation's own source:

    fz90007 ws1 wmax1 bus45  onset=S_DHI  age0 opc31(XOR Ev,Gv/RMW-read)  -> chip IDLE
    fz90030 ws1 wmax1 bus47  onset=S_RSV  age0 opc AA(STOS byte store)     -> chip CODE

The chip inserts an idle slot then issues MEMR@023fc for the S_DHI case; runs
three more prefetches before MEMW@02928 for the S_RSV case. pf_late_rsv fires
(model prefetches) in BOTH - so the S_DHI case is the model's over-prefetch bug.

## The collision-free table (chip ground truth; SOURCE x q_cnt, onset_age==0 throughout)

Merged over discovery (90003/07/15/21/30) AND held-out (90042/51/63/77/88), each
5 seeds x nws10 x wmax{1,2,3,7}; young = coincident reservation (eu_req=1,
eu_req_p1=0, eu_ready=0); action is the CHIP's IDLE(reserve)/CODE(prefetch):

    onset SOURCE   q_cnt=0   q_cnt=1        q_cnt=2
    S_DHI            -        IDLE (14)        -        <-- the ONLY reserving source at q1
    S_MHI            -        CODE (12)        -
    S_RSV          CODE(68)   CODE (12)        -
    S_DEC          CODE(14)     -              -
    S_JWAIT        CODE(18)     -            CODE (12)
    S_PUSH_CALC    CODE(13)     -            IDLE (6)   <-- reserves only at q_cnt>=2

- Keyed by (SOURCE, q_cnt): **0 collisions in BOTH corpora** (COLLISION-FREE).
- Keyed by SOURCE ALONE: collision-free on discovery, but the held-out set
  exposes S_PUSH_CALC as q_cnt-dependent (CODE at q0, IDLE at q2) -> q_cnt is a
  necessary co-key. The 12/24(here 12/12) reliable collision itself (q_cnt=1,
  eu_wr=1) is resolved by SOURCE alone: S_DHI->IDLE vs S_RSV/S_MHI->CODE.
- **onset AGE = 0 for EVERY contested young edge** (the coincident cases are all
  age-0 by construction) -> age is NOT a discriminator in the measured data.
- **q_avl/q_aged identical within each collision cell** (q_avl=1, q_aged=0) ->
  the queue-pipeline split adds no resolving power here.

## The mechanism + the model's exact error (for Codex, NO RTL edit made)

The chip's reserve-vs-prefetch decision at a coincident (age-0) pending
reservation is a function of WHICH microstate generated it: only S_DHI-sourced
reservations (reader / RMW-read final displacement-byte pop) RESERVE the bus
(IDLE) at q_cnt=1; S_RSV (generic store/string reservation, e.g. C6 store, STOS),
S_MHI (moffs), S_JWAIT, S_DEC (POP/RET decode) let the prefetch win; S_PUSH_CALC
reserves only at q_cnt>=2. The model's `pf_late_rsv` (v30_biu) yields to CODE for
ALL of these young sources - CORRECT for the CODE rows, WRONG (over-prefetch) for
S_DHI@q1 and S_PUSH_CALC@q2 where the chip reserves. Phase-3 RTL target (not now):
gate pf_late_rsv by reservation SOURCE - reserve (suppress the prefetch) for the
S_DHI reader/disp-pop class and S_PUSH_CALC@q_cnt>=2; keep yielding to CODE for
S_RSV/S_MHI/S_JWAIT/S_DEC.

## Kept separate (as instructed): the eu_req=0 late-registration cases

absent (model eu_req=0 at the eval row) is dominated by correct prefetch (CODE
4258+5667) but has 7 (discovery) + 14 (held-out) chip-IDLE outliers where the
CHIP reserves yet the MODEL has NO live reservation at the eval row. These do
NOT collapse into the source rule: with model eu_req=0 there is no reservation to
attribute - the model's eu_req ONSET is later than the chip's. This is a distinct
EU-side reservation-onset TIMING site, a separate follow-up (not the pf_late_rsv
arbitration site resolved above).

## Bottom line (Phase 2k)

- **The 12/24 collision is COLLISION-FREE as a function of RTL-observable
  reservation state: (onset SOURCE, q_cnt).** Verified on discovery AND held-out
  corpora, chip ground truth. onset AGE and q_avl/q_aged are not needed.
- ONE arbitration mechanism (source-dependent reserve-vs-prefetch); the model's
  pf_late_rsv is source-blind and over-prefetches the S_DHI/S_PUSH_CALC-q2
  reserving classes. **Phase 3 (source-aware pf_late_rsv gate) is now justified**
  - pending Codex review. NO RTL functional change made (instrumentation only).
- Separate residual: the eu_req=0 late-registration chip-IDLE outliers
  (EU-side onset timing), and any onset-age>0 boundary (unobserved here - all
  contested cases are age 0).

Repro (Phase 2k): `python3 sw/causal_wrand.py onset --seeds 90003 90007 90015 90021 90030 --nws 10 --wmaxes 1 2 3 7`
(held-out: `--seeds 90042 90051 90063 90077 90088`).

# Phase 3 — the source-aware pf_late_rsv veto (FIRST functional RTL; FLASH-READY)

Codex reviewed Phase 2k (gpt-5.6-sol, session 019f663c) and gave GO to author the
narrow source-aware reserve veto. This is the FIRST functional RTL of the
campaign. Authored + validated in SIM; reported FLASH-READY (coordinator flashes
+ chip-replays after Codex signs off).

## The RTL edit (clean EU->BIU interface, NOT raw microstate)

- `v30_eu.sv`: export two SEMANTIC 1-bit reservation-class hints (Moore of the
  current state): `eu_rsv_dhi = (state==S_DHI)`, `eu_rsv_push_calc =
  (state==S_PUSH_CALC)`. NOT the raw 7-bit state (avoids brittle coupling).
- `v30_biu.sv`: `owns_slot = eu_rsv_dhi || (eu_rsv_push_calc && q_cnt>=2)`;
  `pf_late_rsv = <existing conditions> && !owns_slot`. ONLY the eval_ext override
  is gated - prefetch_ok, pf_starved, ext_ok, ext_ok_wr UNTOUCHED. ENUMERATED
  reserve-veto set: only S_DHI + S_PUSH_CALC@q_cnt>=2 own the slot; every other/
  unobserved source keeps baseline behaviour.
- `v30_core.sv`: wire the two hints EU->BIU (gated to 0 under scr_en like the
  other reservation signals).
- Since the veto is a single `&& !owns_slot` AND on pf_late_rsv, by construction
  ONLY owns_slot edges can change - the diff audit is closed structurally, then
  verified empirically.

## Why the veto is w0-neutral and safe at q_cnt=0 (no pf_starved conflict)

- pf_late_rsv requires eval_ext, which never fires at w0 -> w0 bit-identical
  (verified: check_core 169000/169000 full).
- At q_cnt=0 the INDEPENDENT `pf_starved` term (q_cnt==0 && eu_req && !eu_ready &&
  eu_mem_acc && K_MEM) keeps prefetch_ext=1 REGARDLESS of owns_slot, so a
  S_DHI@q_cnt=0 urgent-refill still CODEs - the veto only actually changes the
  decision at q_cnt>=1 (where pf_starved is off). Young coincident reservations
  occur only at q_cnt<=1 (Phase 2j), so the veto's live regime is exactly the
  measured S_DHI@q_cnt=1 IDLE cell + S_PUSH_CALC@q_cnt>=2.

## SOURCE-CAUSALITY verdict (Codex Step 3): SOURCE is CAUSAL, not a proxy

Confirmed from natural corpus diversity (chip ground truth, aligned by
(BUS TYPE, ADDRESS), live eval_ext==1 rows):
- COMPLEMENTARY CONTRAST at matched q_cnt=1: **S_DHI -> IDLE** vs **S_MHI -> CODE**
  vs **S_RSV -> CODE** - all memory final-byte-pop reservations, differing by
  SOURCE alone. Refutes the 'ready-next-cycle / reaches-S_REQ' proxy (S_MHI also
  pops its last byte -> access but the chip picks CODE).
- COVARIATE SPREAD within source (source-consistent): S_DHI holds IDLE across 3
  opcodes/widths (0x31 XOR-word, 0x09 OR-word, 0x38 CMP-byte); S_RSV holds CODE
  across 5 string opcodes (a4/a5/aa/ab/ac/ad), BOTH parities, q_cnt {0,1}
  (66/66 + 38/38); S_JWAIT CODE across both parities and q_cnt {0,2}. At MATCHED
  parity=0, S_DHI->IDLE but S_RSV->CODE -> parity/width/opcode dissociated from
  source. The ONLY q_cnt-dependent source is S_PUSH_CALC (q0->CODE, q2->IDLE),
  exactly the encoded q_cnt>=2 gate.

## DIFF AUDIT + regression check (no golden CODE cell changed)

`vetoaudit` (chip vs PATCHED model) over 4 corpora: discovery 90003/07/15/21/30,
held-out 90042/51/63/77/88 (nws10 x wmax{1,2,3,7}), plus two expansion batches
(90101..90197, 90200..90299; nws10 x wmax{1,3,7}) - ~40k contested edges total:
- owns_slot fires EXACTLY iff source in {S_DHI, S_PUSH_CALC&q_cnt>=2} in ALL four
  corpora (the base menu already exercises string/branch/TEST-RMW/push/moffs).
- owns_slot=1 cells: PATCHED model now IDLE, matches chip 100% (S_DHI@q1 22/22,
  S_PUSH_CALC@q2 6/6). owns_slot=0 cells: model UNCHANGED, match chip.
- **ZERO owns_slot=1 & chip=CODE anywhere = NO veto-induced regression.** The
  patch is a single `&& !owns_slot` on pf_late_rsv, so by construction only the
  enumerated cells can change - confirmed empirically.

## IMPORTANT: the veto is a SAFE PARTIAL fix - the boundary is a per-source
## q_cnt THRESHOLD, broader than 2 sources (Step-3 probe finding)

The deeper source-causality probe (expansion batches) revealed the reserve-vs-
prefetch decision is a per-source q_cnt threshold - collision-free as
f(source, q_cnt) but NOT captured by 2 enumerated sources. Chip-ground-truth
(source, q_cnt) -> action, merged over all four corpora:

    source        q_cnt=0   q_cnt=1     q_cnt=2
    S_DHI           -        IDLE(22)      -        (reserve; q0 unobserved)
    S_PUSH_CALC    CODE      IDLE(6)     IDLE(6)    (reserve q>=1)
    S_DEC          CODE      CODE        IDLE(6)    (reserve q>=2)
    S_MHI           -        CODE(18)      -        (CODE at q1)
    S_RSV          CODE      CODE          -        (CODE through q1)
    S_JWAIT        CODE       -          CODE(6)    (CODE through q2)

- q2 is NOT uniformly reserve (S_DEC/S_PUSH_CALC reserve, S_JWAIT prefetches) ->
  source STILL matters at q2; this is a genuine 2-D (source x q_cnt) rule, not a
  global q_cnt gate (consistent with, and corrects, the old Phase-2i "q>=2 always
  reserve" which conflated sources).
- The narrow veto (S_DHI any-q + S_PUSH_CALC@q>=2) is a VALIDATED, REGRESSION-FREE
  SUBSET: it fixes the DOMINANT over-prefetch (S_DHI@q1 = the resolved 12/24
  collision) + S_PUSH_CALC@q2. It does NOT close the phenomenon: it still MISSES
  S_PUSH_CALC@q1 (6 cases, 1 anchor) and S_DEC@q2 (6 cases, 1 anchor), and the
  higher-q_cnt thresholds of S_MHI/S_RSV are unmapped. These are additional (rarer)
  over-prefetch cells, each currently a single anchor x 6 waits.

## SIM validation + build

- Golden: check_core w0 169000/169000 full; w1 1200/1200; w3 1200/1200 (w0-neutral
  as pf_late_rsv is eval_ext-gated; waited goldens unaffected).
- The narrow-veto target cells (S_DHI@q1 + S_PUSH_CALC@q2) now IDLE in sim, chip-
  matching; every measured-CODE cell stays CODE; zero regression.
- Bitstream: quartus_sh --flow compile of the narrow veto, 0 errors, timing MET
  (all corners positive: setup +4.903 ns, hold +0.248, recovery/removal +1.053,
  min-pulse +1.196). nec_test.sof built.

# Phase 3 (cont) — IN-SILICON chip-replay validation (narrow-veto A/B, FLASHED)

Coordinator FLASHED the narrow-veto bitstream (2963147) into the FABRIC (safe_flash
0 errors, VERIFY ok, cfg 0x1ff0008). This is the FIRST in-silicon confirmation of
the source-veto mechanism. Chip-replay = measurement/read only; the socketed CHIP
(use_core=0) is ground truth, the PATCHED veto RTL is live in the FABRIC
(use_core=1). Tool: `causal_wrand.py hwreplay` (chip vs fabric + TB for source
labels, aligned by BUS TYPE+ADDRESS). Label: 'Phase-3 narrow-veto A/B' - a
known-PARTIAL fix, NOT arbitrary-wait closure.

## Acceptance results (discovery 90003/07/15/21/30 + held-out 90042/51/63/77/88)

1. **Board echo health: PASSED** before AND after (14/14 registers; board healthy).
2. **POSITIVE cells - fixed in silicon: 20/20.** Every model-CODE over-prefetch
   target now IDLEs in the FABRIC and MATCHES the chip: S_DHI@q1 14/14 (12
   discovery + 2 held-out), S_PUSH_CALC@q2 6/6. The doomed prefetch is gone on
   silicon.
3. **NEGATIVE controls - no over-correction: 173/173.** Every measured-CODE cell
   (S_MHI@q1, S_RSV@q0/q1, S_JWAIT@q0/q2, S_DEC@q0, S_PUSH_CALC@q0) STAYS CODE in
   the fabric. ZERO observed veto cell where the chip wanted CODE.
4. **w0 crown jewel: UNCHANGED.** chip vs fabric at w0 (all-zero wvec, 20 held-out
   seeds): write-anchored-clean 20/20, per-access (bs,Tw) identical 20/20 (the
   only pin diffs are float-floor idle addresses, not real). w0-neutral confirmed
   in silicon.
5. **fabric==TB 14301/14301 under replay** - silicon EXACTLY mirrors the patched
   Verilator model, validating all the TB-based analysis as silicon-faithful.
   Residual young fabric!=chip = 0; the only chip!=fabric are the eu_req=0
   late-registration outliers (7 discovery + 2 held-out), untouched by the veto
   (tracked follow-up).

## HELD-OUT RANDOM-WAIT DRIFT (the payoff metric, true-cycle write-anchored)

Measured PRE (chip vs baseline-TB built from HEAD~1) vs POST (chip vs veto-TB ==
chip vs FABRIC, confirmed identical) under EXPLICIT-VECTOR REPLAY (the wrand LFSR
path mis-seeds the local TB vs the board - a tooling caveat; replay is the
artifact-free cross-position comparison). Cell-bearing corpus (N=300, replay vecs
over discovery+held-out at wmax{1,3,7}):
- **|final| offset: total 294 -> 260 clocks (12% reduction); peak-excursion: total
  338 -> 276 (18% reduction).** drifted-seed count 96 -> 90; 12/300 cases improved;
  worst-case (9-10 clk) UNCHANGED.
- Interpretation: the DOMINANT S_DHI/S_PUSH_CALC@q2 mechanism accounts for ~12-18%
  of the write-anchored drift on cell-bearing seeds - a real, partial drop exactly
  as expected for a partial fix. The worst-case and the remaining ~82-88% are the
  UNMAPPED per-source threshold cells (S_PUSH_CALC@q1, S_DEC@q2, S_MHI/S_RSV
  higher-q) + the eu_req=0 onset-timing residual - the Phase-3b targets. (On low-
  drift random held-out seeds 90300-90319 the baseline drift is already ~<1 clk, so
  the reduction there is small in absolute terms.)

## Bottom line (Phase-3 narrow-veto A/B, in silicon)

The source-veto mechanism is CONFIRMED IN SILICON: all 20 targeted over-prefetch
cells switch to chip-matching IDLE in the fabric, zero observed veto cell where the
chip wanted CODE (no over-correction), w0 unchanged, fabric==TB exactly. The
dominant fix removes ~12-18% of the true-cycle write-anchored drift on cell-bearing
seeds (partial, as designed). Phase 3b: map the full per-source q_cnt threshold
table (S_PUSH_CALC@q1, S_DEC@q2, S_MHI/S_RSV/S_DHI other-q, absent sources),
require ~3 independent architectural anchors per gate cell before promoting it,
keep the source-keyed representation (S_JWAIT@q2->CODE refutes 'q>=2 always
reserves'). eu_req=0 onset + w0 young-onset stay tracked follow-ups.

Repro (chip-replay): `python3 sw/causal_wrand.py hwreplay --seeds 90003 90007 90015 90021 90030 --nws 10 --wmaxes 1 2 3 7`.

# Phase 3b prelude — RESIDUAL ATTRIBUTION census (attribute before widening)

Codex: the 12-18% is a treatment effect, not a mechanism decomposition; ATTRIBUTE
the remaining drift before launching per-source-table fitting. `causal_wrand.py
census`: post-veto ABSOLUTE first (BUS TYPE, ADDRESS) chip-vs-fabric divergence
per vector, classified from TB internals (fabric==veto-TB), with the seed's
write-anchored drift MASS attributed to that class. Exact 300 explicit vectors
(discovery+held-out, ws1..10 x wmax{1,3,7}); reflash-free, chip=ground truth.

## Census result (N=300; 210 clean, total residual mass |final|=260 peak=276)

    class                                     seeds  |final|mass  peakmass
    5. SAME decisions, WRONG CLOCK              81      196 (75%)   210 (76%)   <== DOMINANT
    1. eu_req=0 chipIDLE/fabCODE (EU-onset)      7       50 (19%)    52 (19%)
    7. other                                     2       14 ( 5%)    14 ( 5%)
    2/3. young per-source (S_PUSH_CALC@q1,
         S_DEC@q2, unseen source/q_cnt cells)    0        0 ( 0%)     0 ( 0%)   <== NOT a driver here

## Counterfactual attribution (drift removed if each class were oracle-corrected)

- Fix eu_req=0 (class 1): residual |final| 260 -> 210 (**-19%**), peak 276 -> 224.
- Fix per-source cells (class 2/3): 260 -> 260 (**0%** in this corpus - the
  S_PUSH_CALC@q1 / S_DEC@q2 cells found in seeds 90175/90200 carry NEGLIGIBLE mass
  here and are NEVER the first divergence).
- Fix class 5 (wrong-clock): 260 -> 64 (**-75%**) - the big lever.

## What the two dominant residual classes ARE (characterized, chip vs fabric silicon)

- **Class 5 (DOMINANT, 75%): prefetch/idle-SCHEDULING timing, NOT arbitration.**
  chip and fabric make byte-identical bus decisions (same access types/addresses/
  order) but land at different clocks. Exemplar fz90007 ws10 wmax7: the CHIP
  inserts 3 extra idle (Ti/PASV) cycles before a CODE fetch that the model does
  NOT (chip 153 clk vs fabric 150 clk for the same segment) -> the model prefetches
  ~3 cycles too EARLY. Same decision, wrong clock. This is the resume-gap /
  idle-reservation TIMING model (Phase-2b territory), a DIFFERENT site than both
  the BIU decision veto and the EU onset.
- **Class 1 (19%): eu_req=0 late-onset over-prefetch (real decision divergence).**
  Exemplar fz90015 ws10 wmax7 ord37: chip issues MEMW@02608; fabric prefetches an
  extra CODE@00508 FIRST then the write - model eu_req=0 at the eval (the write's
  reservation ONSET asserts a cycle late vs the chip's effective reservation). A
  distinct EU-side site (reservation-onset timing), NOT the BIU arbitration veto.

## Bottom line for Codex (which residual DRIVES the drift + worst-case)

RANKED: **class 5 wrong-clock timing (75%) >> eu_req=0 EU-onset (19%) > other (5%)
> per-source table (0%).** The worst-case (unimproved by the veto) is class 5.
- **DO NOT launch Phase-3b per-source-table widening** - it addresses ~0% of this
  corpus's residual (attribute-before-widening vindicated).
- The eu_req=0 EU-onset defect is the leading DECISION defect (19%) - a real fix
  target (the model's reservation onset asserts ~1 cycle late; characterize which
  EU states/edges), but it is NOT the biggest lever.
- The BIGGEST lever is the class-5 prefetch/idle-SCHEDULING timing (75%): same
  decisions, wrong clock. This is a cycle-timing model refinement (idle-gap /
  resume scheduling), distinct from the arbitration decision work. Recommend Codex
  prioritize the class-5 timing attribution next (it dominates both frequency-mass
  AND the worst-case), with eu_req=0 onset second, per-source table deprioritized.
  (Caveat: class 5 = 'same bus decisions' so it does NOT re-order execution - a
  pure cadence/idle-count model target; may split further under finer analysis.)

Repro (census): `python3 sw/causal_wrand.py census --seeds 90003 90007 90015 90021 90030 90042 90051 90063 90077 90088 --nws 10 --wmaxes 1 3 7`.

## Verdict for Codex (scope decision before flash)

The narrow source-aware veto is CORRECT, source CONFIRMED CAUSAL (S_DHI vs S_MHI
at matched q1; covariate-invariant), and REGRESSION-FREE - safe to flash as a
partial fix that removes the dominant over-prefetch. BUT it is NOT the complete
fix: the reserve boundary is a per-source q_cnt threshold and additional cells
(S_PUSH_CALC@q1, S_DEC@q2, unmapped S_MHI/S_RSV) still over-prefetch. DECISION for
Codex: (a) flash the narrow safe veto now (strictly reduces over-prefetch, zero
regression), then map the full per-source threshold table as Phase 3b; or (b)
first map+fit the full (source, q_cnt) threshold table before any flash. Either
way the RTL interface (per-source class hints -> BIU owns_slot) generalizes:
Phase 3b widens owns_slot's enumerated set / per-source q_cnt thresholds.

## Tracked follow-ups (do NOT block this fix)

- eu_req=0 late-registration chip-IDLE outliers (EU-side reservation onset TIMING,
  distinct site; model has no live reservation at the eval row).
- onset-age>0 boundary (all contested cases are age 0; unobserved).

Repro (Phase 3): `python3 sw/causal_wrand.py vetoaudit --seeds 90003 90007 90015 90021 90030 --nws 10 --wmaxes 1 2 3 7`;
`python3 sw/causal_wrand.py vetoaudit --seeds 90200 90211 90222 90233 90244 90255 90266 90277 90288 90299 --nws 10 --wmaxes 1 3 7` (surfaces S_DEC@q2);
`python3 sw/causal_wrand.py onset --seeds 90042 90051 90063 90077 90088 --nws 10 --wmaxes 1 2 3 7` (SOURCE-CAUSALITY block).

Tools: `sw/causal_wrand.py` (`urgency` corrected, `onset`+`vetoaudit` added). Repro:
`python3 sw/causal_wrand.py urgency --seeds 90003 90007 90015 90021 90030 --nws 10 --wmaxes 1 2 3 7`;
`python3 sw/causal_wrand.py idleslot --seeds 90003 90007 90015 --nws 8 --wmaxes 1 3 7`;
`python3 sw/causal_wrand.py leactl --maxn 8`;
`python3 sw/causal_wrand.py nocomp --seed 90003 --refws 2`;
`python3 sw/causal_wrand.py predicate --seeds 90003 90007 90015 --nws 8 --wmaxes 1 3 7`;
`python3 sw/causal_wrand.py determ --seed 90003`;
`... impulse --seed 90007 --anchor-bus 59 --k 12`;
`... ownwait --seed 90003 --anchor-bus 137 --core`;
`... arbsweep --seed 90003 --anchor-bus 138 --bgseed 2 --maxn 15`;
`... arbscan --seeds 90003 90007 90015 --bgs 2 5 7 --maxn 6`;
`... align --seeds 90003 90007 90015 90021 90030 --wmaxes 1 3 7 15`;
`... arbpop --seeds 90003 90007 90015 --bgs z o t a --core`;
`... episodes --seeds 90003 90007 90015 90021 90030 --wmaxes 1 3 7`.
