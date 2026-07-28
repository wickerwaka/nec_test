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
