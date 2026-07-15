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
