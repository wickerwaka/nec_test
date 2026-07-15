# BIU rebuild — minimal-pair isolation of the prefetch-resume discriminator

Branch `biu-rebuild`. The statistical two-rhythm predictor plateaued at ~75-80%
on the big-gap resumes because fill-vs-steady are CONFOUNDED in fuzz. This
campaign switched to controlled minimal-pair isolation to de-confound and pin
the hidden discriminator directly. RESULT: the discriminator is FOUND, it is
RTL-trackable (EU consumption activity via `q_pop`), and gating on it LANDS the
first waits-drift drop of the whole campaign (w1 625.6 -> 554.0) with w0 and
w1/w3 golden preserved.

## Method
For each candidate history variable: mine the cached chip captures for events
with IDENTICAL instantaneous observable state (kind, beat, occ, occ_end, drain)
but different resume gap, add the candidate to the key, and measure whether it
resolves the contradictions (big-gap match -> 100%). Then extract a concrete
matched minimal PAIR and inspect the raw cycle context to SEE what differs.

## Candidate history variables — RULED OUT (statistical mining)
Adding each to (kind, beat, occ), big-gap match at w1 (baseline 70.7%):
| variable | big-gap match | verdict |
|---|---|---|
| saturation-history (occ hit 6 since flush) | 77.1% | ruled out |
| queue-went-empty (occ hit 0) | 70.7% | ruled out |
| fetches-since-flush | 71.3% | ruled out |
| idle-run length | 77.1% | ruled out |
| prefetch-momentum (prev cycle back-to-back) | 70.7% | ruled out |
| occ_end | 77.1% | (marginal) |
None resolve it — all plateau at the same ~77%. The enumerated history
variables are not the discriminator.

## Confound 1 — FLUSH events (identified + excluded)
The first extracted minimal pair revealed a "big-gap" event that was actually a
BRANCH/JUMP (a `QS=E` flush between the fetches, queue cleared, refetch from the
jump target 0x530) — a flush/branch-resolution phenomenon (Stage 5), not
prefetch pacing. Excluding flush-contaminated events (137 of 4148) is correct
de-confounding but only accounts for ~10 of 188 big-gaps; the plateau persists
(70.7% -> 74.7%). Flush is a real but minor confound.

## THE DISCRIMINATOR — EU consumption activity (FOUND)
A clean non-flush minimal pair (both PF-completed, occ_c=4, occ_end=4, beat=0,
drain=1) exposed it directly:
- **BIG-GAP** (seed90001, gap 4): after the fetch T4, the EU is actively
  CONSUMING — pops at cycles 385/386/387 (occ draining 4->1); the fetch resumes
  at occ=1.
- **IMMEDIATE** (seed90002, gap 1): after the fetch T4, the EU is STALLED — NO
  pops (occ stable at 4, filling toward 6); the fetch resumes at occ=4.

Systematic confirmation over all non-flush PF resumes (pops in the resume
window):
- BIG-GAP (gap>2): mean 1.82 pops, distribution {1:40, 2:51, 3:20} (always 1-3).
- IMMEDIATE (gap<=2): mean 0.03 pops, distribution {0:2896, 1:89} (97% zero).
Near-perfect separation. **The resume gap is governed by whether the EU is
consuming (popping) — fetch-limited/steady = consuming = paced (big gap);
EU-stalled = queue fills = immediate.**

CAUSAL, reconstructable version (recent pop-rate in the 8 cycles BEFORE the
decision) added to the predictor key:
| key | big-gap match w1 | w3 |
|---|---|---|
| (kind,beat,occ) | 74.7% | 78.7% |
| + recent-pop-rate | 87.6% | 78.7% |
| (kind,occ_end,recent-pop) | 88.8% | 85.2% |
| (kind,beat,occ,occ_end,recent-pop) | **93.8%** | **85.8%** |
Consumption activity lifts big-gap prediction from 74.7% to 93.8% (overall
99.5%). It is the dominant closing variable, and it is RTL-trackable (`q_pop`).

## RTL implementation (LANDED — first drift drop of the campaign)
`v30_biu` (Stage 3): `pop_sr` (8-cycle history of `pop_now`) -> `eu_consuming`
= (pops in window >= 2). After a WAITED prefetch (`pf_drain`, set at the fetch's
deferred completion, cleared at the next T1), the refill threshold tightens to
occ<=3 ONLY while `eu_consuming` (else stays occ<=4). This paces the fetch when
the EU is consuming and resumes immediately when it is stalled - the measured
discriminator.
- **w0-NEUTRAL:** `pf_drain` is only ever set on a Tw cycle, so at w0 it is
  always 0 and `prefetch_ok` is bit-identical. Proven: w0 golden 169000/169000.
- **Golden preserved:** w1 800/800, w3 600/600 (the fitted forms unaffected).
- **DRIFT DROP:** w1 bad-rows mean 625.6 -> **554.0** (~11%), first-divergence
  median 328 -> 374 (divergence pushed later); w3 613.2 (neutral on 30 seeds).
Config swept: `eu_consuming>=2 / pf_lim<=3` is the w1 optimum; >=3/<=2 trades w1
for a small w3 gain. Adjudication ledger: **0 w0 deltas** (w0-neutral).

## Follow-up: the beat law + the remaining-drift breakdown (2026-07-14)

Denser measurement of the resume gap per (consuming, beat) where
beat = (crossing_cycle - last_T1) mod (4+N):
- **beat=0 → immediate (gap 1) in 97-99% of events** (both consuming and not);
  beat=0 means occ<=4 already at T4+1 (queue had room).
- **beat!=0 → paced**, with a specific per-beat gap (w1: beat2->~19, beat3->15,
  beat4->11; these large gaps are the EU-STALLED long-instruction cases where
  the queue stays full and the EU execution time sets the gap - already timed by
  the EU model). Consumption was a CORRELATE of beat!=0, not the primitive.
So the fitted resume law is beat-dominated: resume immediately when the refill
crossing lands on-grid (beat 0), pace when off-grid / queue-full.

**Remaining-drift breakdown (the strategic finding).** With the consumption-gate
landed, classifying the FIRST divergence of 40 w1 seeds:
| class | count | phenomenon |
|---|---|---|
| FLUSH / branch | 13 | chip flushes ~1 cyc later than TB on a jump redirect (Stage 5) |
| EU-arbitration | 13 | TB commits an EU MEMW where the chip prefetches CODE first |
| resume / other | 13 | residual prefetch-resume pacing |
| CLEAN | 1 | |
The waits>=1 drift is a ROUGHLY-EQUAL THREE-WAY split. The consumption-gate
addressed part of the resume third; the other two thirds are DISTINCT
phenomena: flush/branch-resolution timing (Stage 5) and EU-vs-prefetch
arbitration timing. **No single resume function closes the gate** - full closure
is a multi-front effort (resume + flush + arbitration), each ~1/3 of the drift.
This reframes the plan: after the resume third, Stage 5 (flush) and an
arbitration-timing pass are co-equal priorities, not sequential afterthoughts.

## Three-front close — progress (2026-07-14)

Committed to driving all three drift thirds (arbitration / flush / resume) to
near-zero, each w0-neutral + golden-preserved + chip-adjudicated.

### Front 1 — EU-arbitration: LANDED (commit 4482576)
Measured (seed90008 STM, +eudbg): under waits a STORE that empties the queue
(q_cnt=0) reserves (S_RSV, eu_req high, not ready) during the deferred eval; the
CHIP prefetches to refill BEFORE the store, the TB idled (eu_req blocked the
prefetch). Fix `prefetch_ext`: a STARVED queue (q_cnt==0) prefetch wins over a
not-yet-ready EU MEMW reservation, ONLY in the eval_ext window (w0-neutral).
Gating: must be `eu_wr && K_MEM` (a real store) - the EB branch reservation also
shows q_cnt==0 / eu_kind==K_MEM / eu_wr==0 (indistinguishable from a LOAD), so
loads can't be separated from branch flushes by these signals (needs Front 2).
Result: w0 169000/169000, w1 800/800, w3 600/600; DRIFT w1 593.6->565.3, w3
619.6->606.2. 0 w0 deltas.

### Front 2 — flush/branch: PER-BRANCH LAW measured; Jcc-w1 doomed-prefetch LANDED (830f1b2)

Measure-first (sw/exp_flush.py, controlled branches x w0/w1/w3, chip-vs-TB):
**ONLY Jcc (conditional taken) diverges at the flush under waits** - EB, E9,
LOOP, CALL all MATCH at w0/w1/w3. The blanket bus_tw stretch was wrong because
it touched the 4 correct branch types. Jcc has TWO sub-mechanisms under waits:
- **w1 (queue has room): a DOOMED fall-through prefetch** runs during resolution
  before the flush; the TB's hard S_JWAIT reservation blocked it. FIXED: Jcc
  reserves only dly<=1 under waits (`waits_seen`-gated, w0 keeps its dly==3 gap
  -> w0-neutral) so the doomed prefetch commits. Controlled Jcc w1 MATCHES;
  DRIFT w1 565.3->506.0.
- **w3 (queue full, no room): a bare +1-LATE flush redirect** (no doomed
  prefetch). DEFERRED after two measured attempts, BOTH over-shoot by exactly
  +1: (a) EU-side S_JWAIT transition at dly==0 -> the BIU redirect-commit eval
  adds a 2nd idle (+2 net); (b) BIU-side blocking the eval_ext flush commit ->
  the next do_commit is +2 (a push-absorb/eval interaction inserts a 2nd idle),
  turning 1-early into 1-late, w3 drift worse. The precise +1 needs a 1-cycle-
  HOLD of the eval_ext flush redirect (commit at eval_ext+1, not skip to the
  next do_commit) - a fiddly latched-redirect mechanism, deferred as not worth
  the risk vs the four landed fronts. Jcc w3 still DIVERGES; w3 moved via the
  LOAD EXTENSION instead (606.7->583.6). Follow-up: the latched +1 redirect.

### (superseded) earlier blanket-stretch attempt: CHARACTERIZED + DEFERRED
Measured (seed90003 Jcc 0x73, +eudbg): the branch resolves via S_JDISP->S_JWAIT
(dly countdown)->S_JFLUSH; the CHIP flushes ~1 cyc LATER than the TB under waits
(chip E@237/T1@238 vs TB S_JFLUSH@236/T1@237). This CONFIRMS +1-LATE (opposite
Round 3's "flushes earlier" guess). Attempted fix: pause the S_JWAIT dly during
Tw (`if(!bus_tw) dly<=dly-1`), w0-neutral. Result: w0 held 169000 BUT w1 golden
705/800 arch 757, w3 346/600 arch 552 - a CYCLE AND ARCH regression (drift also
worse, first-div 32 = broke the loader). The blanket Tw-pause over-delays:
branch resolution spans multiple waited cycles so it delays by many, not the
measured +1, and EB (golden, on-time under waits) and the loader branches get
mis-delayed - changing execution (arch). The correct fix is a PER-BRANCH precise
+1 (which Tw to pause on distinguishes Jcc-late from EB-on-time), needing a
denser flush-point-vs-wait×branch-type measurement. HIGH golden risk (this is
the front the prior campaign also failed on). DEFERRED with this characterization
+ reverted; Fronts 1 and 3 kept.

### Front 3b — arbitration (late reservation): LANDED (commit 56c1a19)
Measured (seed90020/90010/90017/90000/90012, all REP-string a4/a5/ab/ac/ad, w1):
at the last CODE fetch's T4 `eu_req==0`, at the eval_ext Ti `eu_req==1`/
`eu_ready==0`/`q_cnt==1` - a store/load reservation that first asserts AT the
deferred eval (did NOT lead it). The chip commits ONE refill CODE prefetch and
the string access takes the next slot; the TB blocked prefetch on the
coincident `eu_req`. The fitted WRITE-half reservation law only blocks a
LEADING reservation (`eu_req_p1==1`). Fix `pf_late_rsv`: at eval_ext, a
mem-access reservation with `eu_req && !eu_req_p1 && !eu_ready`, `occupied<=4`,
does not block the refill prefetch. Gated occ<=4 so the fitted single-store
forms (occ>4, leading reservation) are excluded. w0-neutral (eval_ext).
Result: w0 169000, w1 800, w3 600, w0 fuzz clean; DRIFT w1 459.3->414.1 (-10%),
ARB first-div count 10->3, w3 neutral. 0 w0 deltas.

### Front 2b (Stage 5) — near-flush +1-late redirect: LANDED (commit b41fd4d)
The DEFERRED Jcc-w3 latched +1 redirect - now closed AND generalizing to w1.
Measured (seed90003/90018/90005, opc 73 Jcc, w1, +eudbg with q_flush/eval_ext):
a NEAR flush's `q_flush` asserts DURING the eval_ext cycle; the TB committed the
redirect via the eval_ext mid-cycle path THAT cycle (display @T4+1); the CHIP
inserts exactly ONE more idle and mid-cycle-commits the redirect the NEXT idle
(display @T4+2). The prior two attempts overshot because a plain do_commit at
the next idle lands @T4+3. Fix `flush_hold`: latch the deferral one cycle, then
commit via the SAME mid-cycle path (state->T1 + display this cycle) - inserts
ONE idle, not two. `flush_fast` (far) redirect unchanged (already @T4+1).
Follow-up 5b: a far flush committing AT the eval_ext cycle showed E one cycle
late (ff_show requires !eval_ext); added `ff_evalext` to qs_e (display-only).
Result: w0 169000, w1 800, w3 600, w0 fuzz clean; DRIFT w1 414.1->307.3
(CLEAN 6->18, seed90003 576->0, seed90018 484->0), w3 583.3->475.6
(CLEAN 15->21, w3 FLUSH first-div count 8->0). 0 w0 deltas. This closes the
FLUSH third: w1 FLUSH 10->2, w3 FLUSH 8->0.

### Front 3 — resume: PARTIAL (consumption-gate landed f9c33f6)
The beat-dominated resume law; consumption-gate handles part. Limited ceiling
(big beat!=0 gaps are EU-execution-time, already EU-timed). Low priority.

### Front 3c — full beat-lookup resume: ATTEMPTED, REVERTED (5th refutation of the coarse model, 2026-07-14)

After the FLUSH+ARB thirds closed (resume became the sole dominant third: 27 w1
/ 25 w3), attempted the full two-rhythm resume-slot lookup the plan flagged.
Extracted the gap table from cached captures (predict_resume.collect): keyed on
(kind, beat, occ) the law is remarkably CLEAN in aggregate - **beat==0 -> gap 1
(resume at the eval_ext cycle T4+1), beat!=0 -> gap 2 (one extra idle)**,
uniform across EU/PF kinds and w1/w3. Implemented in RTL as a proper mod-P beat
counter (beat_cnt = cycles since last T1, period = 4 + the cycle's Tw count,
on_grid = beat_cnt % period == 0) gating a `resume_block` that inserts exactly
one idle when a waited-window resume crossing is off-grid. w0-neutral by
construction (pf_drain, hence resume_block, is 0 at w0).

- **Behaviorally VALID**: w0 golden 169000/169000, w1/w3 golden ALL forms pass
  (the fitted forms only passed once the beat counter used true mod-P, not the
  `!eval_ext` proxy - the proxy mis-flagged beat-0-via-wrap crossings and tripped
  the Stage-1 phase SVA + regressed the fitted forms; the mod-P version fixed it).
- **But the DRIFT got WORSE**: w1 307.3 -> 659.8 (CLEAN 18->3), w3 475.6 -> 707.8
  (CLEAN 21->5). The coarse "beat!=0 -> +1 idle" fires BIDIRECTIONALLY wrong: the
  RTL's crossing-detection (occ<=threshold in the pf_drain window) does not
  coincide with the predictor's reconstructed crossing (feature-lossiness), so
  the +1 idle lands at the wrong cycles - helping some phases, hurting others,
  net strongly negative. REVERTED.

This is the 5th independent refutation (after grid_phase/counter/occupancy/kind
in biu_model, and rounds 1-3) that the resume floor does NOT close over any
coarse externally-reconstructable tuple - EXACTLY as design doc 4a predicted
("fails to close even at w0 where the model is bit-exact... it does NOT reduce
to a coarse 3-tuple; the rewrite MODELS the grid state, it does not tabulate").
**VERDICT: the RESUME third is the irreducible floor for LOCAL w0-neutral
changes.** Closing it requires the full grid-state scheduler keyed on the RTL's
EXACT internal state (in-flight bytes + q_aged + exact stretched-grid crossing
position), NOT a coarse lookup - a large structural rewrite of the prefetch-issue
path, not a tractable increment. The honest stopping point for the resume third.

## Verdict — waits>=1 is closable non-invasively; the discriminator is real
The isolation SUCCEEDED: the fill-vs-steady discriminator is the EU consumption
activity (recent `q_pop`), a reconstructable AND RTL-trackable variable — NOT
internal-only, NOT requiring decap. It reopened the build and landed the first
waits-drift drop (every prior attempt worsened it). The current threshold
implementation is a FIRST, working realization that captures the dominant
"core-too-fast when the chip paces consumption" direction (w1 -11%). It does not
fully close (554 not ~0) because a threshold is one-directional while the true
resume law is the bidirectional resume-SLOT function keyed on
(consumption-activity, beat, occ) — the predictor is a lookup (93.8%), not a
threshold. REMAINING WORK: implement the fuller resume-slot function (consumption
+ beat) to capture the bidirectional alignment and the w3 cases, iterating each
step against the drift harness. The path is now open and measure-driven.
