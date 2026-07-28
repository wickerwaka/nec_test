# Task #33 — wait-state cadence characterization — durable state

#1-priority: arbitrary/random per-access WAIT-STATE cycle-accuracy (chip vs core
cycle-for-cycle). Builds on the CLOSED class-5 campaign (branch biu-arb-qcnt merged
ba64af8; census 494 fully attributed; laws in the memory + docs/notes/
class5_campaign_record.md). #33 = assemble the broader mc1 waited-cadence dataset +
the seeded multi-push datapoints, cluster by context tuple, extract candidate laws,
quantify mass explained, rank for the from-scratch bus-grid prefetch-rebuild.

## STAGE 1 — DATASET ASSEMBLY + CLUSTER CENSUS (this boundary)

### Population inventory (mc1 campaign, results.jsonl + captures)
- **Waited-TIMING: 1771 seeds** (soup 1650, raw 121). Waits: wrand 1353 (the
  #1-priority per-cycle-random), w1 165, w2 126, w3 127.
- maxstep bands (drift changepoint magnitude): 0-9:78, 10-15:265, 16-30:396,
  31-63:487, 64-127:324, 128+:221. **The floor-rejected 10-63 band = 1148 seeds**
  (the candidate cadence-bug core); 64+ (545) = large-drift/desync tail.
- **done_mismatch: 542 → FOLDS IN (confirmed drift-accumulation window-truncation).**
  done_real/done_sim = (True,False) in 540/542, truncated in 524/542: the CHIP
  reaches done, the FABRIC is >window BEHIND (systematically SLOWER under waits) and
  truncates. This is the severe-drift tail of the same family, not a separate class.
- **=> WAITED-CADENCE FAMILY = 2313 seeds** (1771 TIMING + 542 done_mismatch).
- Soup-dominated (the #32 reframe: soup TIMING 2257 is all IN-IMAGE cadence, bigger
  than the survey credited; raw waited-TIMING only 121).

### First-pass slip census (46536 changepoint-slip events over the 2313 family)
COARSE (campaign drift-changepoint metric, NOT the fine gaperr per-transition
instrument — see below). Gross composition:
- **Sign near-symmetric: -23276 / +23260** => most raw slip mass is PAIRED (adjacent
  +N/-N from ±-slot shifts; class5: "paired != ordering", any 1-slot shift makes a
  pair). Net directional mass is the residual after one-to-one matching.
- **occ-keyed: occ0 27734 (60%), occ1 4385, occ2 3613, occ3 609, occ4 111, occ5+ 59,
  occNone 10025.** The mass CONCENTRATES at occ0 = the STARVED-QUEUE RESUME cell (the
  class5 demand-deadline / queue-demand resume law's domain).
- magnitude: |1|:2091 |2|:4403 |3-9|:25792 |10-35|:10071 |36+|:4179.

### Seeded datapoints (the NEW candidate law — the proven template)
- **Multi-push BUS-HOLD law** (from #31): the chip holds the bus through a whole
  multi-push microcode sequence before the next prefetch; the fabric interleaves ONE
  prefetch. WAIT-COUNT-DEPENDENT, NON-MONOTONIC (w1 chip prefetches mid-walk, w2
  holds, w3+ no mid-walk prefetch). Spans **ENTER-w2** (directed 0:0x500 harness) AND
  **PUSHA-w2 (k=2062)**. This is a NEW cadence law NOT in the class-5 census (class5
  corpus = single-access streams; multi-push microcode is a distinct geometry).
- **k=15 queue-split context** (mc1 #33 head, prefetch/queue-split datapoint —
  captured; to re-fold).

### The authoritative fitting instrument
class-5 **gaperr** (sw/class5_gaperr.py): signed inter-T1 gap-error per aligned bus
ordinal, TRUE per-cycle-random waits (the wv-per-element bug is FIXED). Its taxonomy
(chip=truth): built-law resume scatter (H-SLIP, closed), EU-access timing
(CODE->EU 125u = largest never-attacked block; CODE->MEMW/MEMW->CODE/IOW->CODE),
CODE->CODE resume residual (honest floor), ordering/arbitration (H-ARB, eu_ready-
keyed), temporal-observability floors. class-5 census = 544 real random-wait (fully
attributed: 288 paired-ordering, 135 non-CODE EU-access, 121 CODE->CODE scatter),
later 494 after H-PHASE landed. Runs on the causal_wrand corpus, NOT mc1 captures.

## STAGE 2a — GAP-ERROR CENSUS (board-free, sw/t33_census.py) — DONE

Per-transition signed gap-error (chip=real vs board-fabric=sim, same campaign
wrand, already wait-aligned; class5 accesses()+align()) over the full 2313-seed
family. **378699 aligned intervals, 32591 nonzero (8.6%), TOTAL |ge| mass 72438.**
- **PAIRED 27310 (38%) / UNPAIRED net-directional 45128 (62%)**: unlike the class5
  causal_wrand corpus (paired-ordering dominant), the mc1 population is 62% NET
  DIRECTIONAL DRIFT — the fabric is systematically off, not just ±1-slot scatter.
  This is the headline: a large real net-drift component to fit, not noise.
- **KIND-cell mass map** (class5 top taxonomy):
  | cell | err% | mass | mass% |
  |---|---|---|---|
  | CODE->CODE | 7.2 | 34836 | **48.1%** |
  | EU->CODE | 10.1 | 14106 | 19.5% |
  | CODE->EU | 8.5 | 12170 | 16.8% |
  | EU->EU | 13.8 | 11326 | **15.6%** |
  - CODE->CODE (48%) = the prefetch/resume cadence — the class5 domain (resume law,
    midband, demand-deadline), the single biggest lever.
  - EU-access cells (EU->CODE + CODE->EU + EU->EU = ~52%) — MUCH bigger than class5
    (which was single-access, EU->EU ~1%). The mc1 soup multi-access geometry
    (string/RMW/multi-push/ENTER-walk/INT) lifts EU->EU to 15.6%.
  - CODE->EU 16.8% confirms the never-attacked block is substantial at mc1 scale.
- **Highest ERROR-RATE cells = the multi-access/alternation geometries** (where the
  multi-push bus-hold + RMW + string + ENTER-walk + INT live):
  MEMW->MEMR **28.9%** (mass 1727), INTA->MEMR **29.4%** (282), MEMR->MEMW 20.1%
  (2620), MEMR->MEMR 12.2% (4454). IOW<->CODE (done-marker + soup OUTs) ~11% (5921
  +5671). The EU-alternation block (MEMR/MEMW inter-transitions) ~10.6k mass (14.6%)
  is the upper bound for the multi-push bus-hold law's share — precise isolation
  needs the Stage-2b probe (a fabric CODE prefetch interleaved in a chip push run).
- **Reconciles the coarse 46536-slip picture**: coarse occ0-dominance (60%) maps to
  the CODE->CODE starved-queue resume cell (48% of fine mass); coarse sign-symmetry
  = the 38% paired component. The fine census additionally exposes the 62% net-drift
  and the EU-access mass the changepoint metric flattened.

RANKING for the prefetch-rebuild (by census mass, to guide Stage-2b probes):
1. CODE->CODE resume cadence (48%) — largest; the class5 laws already fit much of
   its causal_wrand analog, but at mc1 scale + net-drift it needs re-fitting.
2. EU->CODE / CODE->EU EU-access timing (36%) — incl. the never-attacked CODE->EU.
3. EU->EU multi-access (15.6%) — NEW at scale; the multi-push bus-hold candidate
   law sits here + in the EU<->CODE interleave. Highest per-transition error rates.

## STAGE 2b PROBE 1 — MULTI-PUSH BUS-HOLD (board) — CHARACTERIZED, small mass

Directed board probe (chip use_core=0 vs core use_core=1), push-runs x waits x
queue-fill (prime NOPs) x geometry. The "multi-push bus-hold law" is NOT a new
broad law — it is a NARROW single-slot prefetch-interleave that FOLDS INTO the
class5 Tw-parity family:
- **Single-slot, count-INDEPENDENT**: ENTER w2, nesting 1..8 -> chip HOLDS the bus
  through the whole walk (0 interleaved fetches), core interleaves EXACTLY ONE
  prefetch after the FIRST push (1C), for every push count. Not a count-scaling hold.
- **Wait-specific: w2 ONLY** (w1/w3/w7 chip==core). Non-monotonic, as seeded.
- **Tw-PARITY gated**: even prime (0,2,4,6) -> interleave; odd prime (1,3,5) -> none.
  This is the SAME Tw-parity / grid-phase displacement the class5 H-PHASE arc
  characterized + landed (RMW-write parity split, 9193372).
- **Geometry-specific**: ENTER (frame-walk = read+write) shows it; PUSHA/PUSHrun/
  PUSHF are chip==core at ALL waits+primes in the directed harness. k=2062 (PUSHA
  soup w2) showed it only under a specific SOUP queue state -> queue-occupancy, not
  the push instruction, is the enabler.
- **MASS**: SMALL. One slot per affected ENTER at w2 x even-parity x enabling queue
  state; a small fraction of the 14.6% EU-alternation block (the bulk of which is
  EU-access timing / string / RMW, not the interleave). NOT rebuild-priority as its
  own law; it is a known-mechanism (Tw-parity) narrow cell.

RECOMMENDATION: do NOT invest rebuild effort in a standalone multi-push bus-hold
law; account it under the class5 Tw-parity family. Census-first + this probe
prevented a rebuild investment in a ~small-mass cell that looked broad.

## STAGE 2b PROBE 2 — k=15 qs-split — ORDERING/ARBITRATION (H-ARB), board-free

k=15 (soup, wrand w2, done_mismatch) capture divergence (ordinal 158, chip vs
board-fabric = board data): the chip interleaves a CODE prefetch (0x57e) BETWEEN a
MEMR (0x2747) and an RMW (MEMR/MEMW 0x2cfe); the fabric does the RMW FIRST then the
prefetch. An ADJACENT TRANSPOSITION of prefetch vs EU-RMW-read = a +N/-N PAIR. This
is the class5 **H-ARB / paired-ordering** family (arbitration = queue-demand vs EU-
readiness, eu_ready-keyed) whose arbiter-rekey arc closed NO-GO (only 122u/544
want_eu-decided; swap sites had eu_ready=1, chip prefetched anyway, predicate
coverage/false-flip failed both gates). Folds into H-ARB; no new board time (the
capture is chip-vs-board-fabric). Mass = in the PAIRED component.

## STAGE 2b PROBE 3 — CODE->CODE NET-DRIFT (board-free) — MOSTLY SCATTER

Per-transition + per-seed cumulative over the family (chip vs board-fabric):
- CODE->CODE: mass +18049/-16787 = **net +1262 (3.6%)**; per-seed cumulative ZERO
  for 1534/2313. CODE->CODE is bidirectional SCATTER (class5 resume-law +-slot
  jitter at the observable floor), NOT net accumulation.
- **The census "62% unpaired" OVERSTATED net-drift** (adjacency-3 matcher artifact).
  True per-seed net: waited-TIMING (1771) abs|ge| 54714 but sum|net| only 5610
  (10%) - 1209/1771 seeds |net|<=2 => 90% SCATTER. done_mismatch (542) is the
  genuine net-directional tail (fabric BEHIND, median -3; real accumulation past the
  alignment cutoff -> truncation), abs 17724 / sum|net| 2400.
- prev_tw asymmetry: prev_tw=0 net -3333 (fabric later after a non-waited pred);
  prev_tw>=2 net positive. Higher-tw cells (4-15) higher err% (9-14%) small n.

## STAGE 3 — LAW-FITTING REPORT (for Codex review before canonization)

### The mc1 waited-cadence residual (72438 |ge| mass, 2313 seeds) decomposes as:
| family | mass% | nature | disposition |
|---|---|---|---|
| CODE->CODE resume scatter | 48% | class5 resume-law +-slot jitter; per-seed ~0 net | at OBSERVABLE FLOOR (class5 laws fit the mechanism); rebuild must REPRODUCE, won't reduce |
| EU->CODE + CODE->EU EU-access | 36% | scatter-dominated; CODE->EU = largest NEVER-ATTACKED block | rebuild OPPORTUNITY (class5 never fully attacked; needs model-internal frame) |
| EU->EU multi-access | 15.6% | NEW at mc1 scale (class5 ~1%): string/RMW/ENTER-walk/multi-push; highest per-transition err | rebuild OPPORTUNITY; incl. the DEMOTED multi-push bus-hold (small, Tw-parity) |
| ordering/arbitration (H-ARB) | (paired, cross-cell) | prefetch-vs-EU swaps at queue-splits (k=15) | characterized; rekey NO-GO; +-1-slot floor |
| done_mismatch net-drift tail | (542 seeds) | fabric net-BEHIND, accumulates past alignment | genuine directional bias to nail |

### Candidate laws + mass-explained
1. **class5 resume law** (successor_T1=max(demand_slot, pred_T4+turnaround_floor);
   demand-deadline L(q_cnt,age); midband_pause q_cnt3-4 band_age>=2; capacity
   back-to-back<=occ4/pause>=occ5) — explains the bulk of CODE->CODE; RESIDUAL is
   the observable-floor scatter (chip-internal fetch-scheduler micro-state).
2. **class5 Tw-parity (H-PHASE)**: even/odd Tw displacement; explains the demoted
   multi-push bus-hold cell + RMW-write parity. SMALL mass, landed mechanism.
3. **class5 H-ARB ordering**: eu_ready-keyed prefetch-vs-EU arbitration; explains the
   PAIRED/ordering swaps (k=15); rekey NO-GO -> +-1-slot floor.
4. **EU-access timing (EU->EU + CODE->EU)**: NOT yet a fitted law at mc1 scale - the
   class5 corpus was single-access. This 52%-of-mass block is the rebuild's PRIMARY
   fittable territory; needs the model-internal frame (TB re-run) to key.

### RANKED rebuild requirements (from-scratch bus-grid queue/prefetch model)
1. **MUST reproduce the class5 laws** (resume demand-deadline, midband, Tw-parity,
   capacity, H-ARB eu_ready arbitration) - they are silicon-confirmed and cover the
   CODE->CODE + ordering bulk; a rebuild that doesn't will regress these.
2. **PRIMARY new fitting target = the EU-access cells (EU->EU 15.6% + CODE->EU 16.8%,
   ~32% combined)** - the mc1 multi-access geometry (string/RMW/ENTER-walk) the
   single-access class5 corpus never exercised. This is where the rebuild can reduce
   mass class5 could not. Needs the model-internal (occ/q_cnt/eval_ext) frame.
3. **The bulk is SCATTER at the observable floor** (90% of TIMING mass cancels per-
   seed) - the rebuild should NOT expect to eliminate it; it is chip-internal micro-
   state (class5's established closure classes: built-law scatter / temporal-
   observability / state-identity / key-exhaustion).
4. **done_mismatch net-drift tail** - a small directional bias (fabric slow) to nail;
   the only clear net-accumulation signal.

### KEY CORRECTIONS this stage banked
- The census 62%-unpaired OVERSTATED net-drift (adjacency-matcher artifact); the
  bulk is scatter at the class5 floor.
- The multi-push bus-hold DEMOTED to a narrow Tw-parity cell (small mass).
- k=15 qs-split = H-ARB ordering (already characterized, rekey NO-GO).
- The NEW mass vs class5 = the EU-access multi-access block (the rebuild's opportunity).

-> ROUTE TO CODEX critical review (challenge the w0 assumptions + the prefetch/BIU
reasoning, esp. the "observable floor" and EU-access-opportunity claims) before this
becomes the rebuild foundation.

## Open threads / next stages
- STAGE 2 (fitting): run gaperr's per-transition frame over the mc1 waited-cadence
  family (or a stratified sample) to get the CONTEXT-TUPLE census (occ, tw, kind,
  parity, q_cnt/demand-age, fillhist, gap signatures) in the class5 taxonomy;
  reconcile the coarse 46536-slip picture with the fine per-transition mass.
- Fit the MULTI-PUSH BUS-HOLD law across PUSH counts x waits x queue states (ENTER/
  PUSHA/PUSHF/INT-push) — directed board probes (bounded); this is likely a NEW law
  family the single-access class5 corpus never exercised.
- k=15 qs-split geometry swept over occ x tw (directed probe).
- Quantify how much of the 2313-family mass each candidate law explains; rank what a
  prefetch-rebuild must implement. -> the LAW-FITTING REPORT (Stage 2 deliverable).
- Caveat carried from class5: every census historically FLOORED by cutoff/wv bugs;
  freshness-check instruments; per-cycle-random is the target (uniform is degenerate).
