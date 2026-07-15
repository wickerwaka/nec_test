# Exact-grid-state RESUME SCHEDULER — design + go/no-go (Phase B)

The prefetch-resume-under-waits drift is the last dominant third and the
irreducible floor for LOCAL w0-neutral changes: **six** independent refutations
(grid_phase / free-running counter / occupancy threshold / completed-kind /
consumption trigger in biu_model.md, plus the reverted beat-lookup Front 3c)
that NO coarse externally-reconstructable tuple closes it. This doc scopes the
from-scratch scheduler keyed on the RTL's EXACT INTERNAL grid state — "models
the grid, does not tabulate" (design doc §4a) — and reports the exact-internal-
state predictor go/no-go that the earlier bus-reconstructed 93.8% plateau could
not give.

## 1. Why the reverted beat-lookup (Front 3c) failed — the precise lesson

Front 3c implemented the aggregate gap law (beat==0 → gap 1, beat!=0 → gap 2)
via a mod-P beat counter gating a one-idle `resume_block`. It was behaviorally
VALID (w0 169000, w1/w3 golden all forms) but net-REGRESSED drift (w1 307→660,
w3 476→708). Root cause, now pinned by the exact-state predictor below: the RTL
crossing-detection ("first idle where the RECONSTRUCTED occupancy ≤ refill") did
not coincide with the chip's true resume-decision cycle, so the ±1-idle landed
at the WRONG cycles — bidirectionally wrong. The lesson is NOT "beat is wrong";
it is that the decision must be driven off the RTL's EXACT internal crossing and
EXACT grid phase, not a reconstructed proxy.

## 2. Go/No-Go — the exact-internal-state predictor (sw/exact_predict.py)

Method: run the TB with +eudbg to read the RTL's EXACT internal state per cycle
(occupied incl. in-flight, q_aged, infl, bus_ts sub-phase, bus_phase grid
parity); extract each prefetch-resume event with those exact features at the
crossing; align to the CHIP's resume events by prefetch-T1 order (identical
fetch-address sequence); predict the CHIP's resume gap. Evaluated on the CLEAN
PRE-DIVERGENCE PREFIX of each seed — the rows BEFORE the first chip-vs-TB
divergence, where the TB's internal state PROVABLY equals the chip's (so the
"exact state" is genuinely the chip's, not a drifted TB approximation).

Result (40 seeds, feature = exact internal state → CHIP gap):

| wait | key (kind, exact-occ) overall / big-gap | vs bus-reconstructed big-gap |
|---|---|---|
| **w0 (control)** | **100.0% / —** (no big-gaps; TB==chip) | (RTL is 169000/169000 exact) |
| **w1** | 96.1% / **83.5%** | 70.7% |
| **w3** | 97.7% / **97.8%** | 77.2% |

Findings:
- **w0 CONTROL = 100%.** With TB==chip, the exact state predicts the gap
  perfectly — confirming the resume law is a deterministic FUNCTION of the exact
  internal state (no hidden/unmodelable variable), exactly the design-doc §4a
  claim, now measured not just argued.
- **Exact occupancy is the dominant closer.** The EXACT internal `occupied`
  (q_cnt + in-flight, the RTL's true value) lifts clean-prefix big-gap
  prediction to 83.5% (w1) / 97.8% (w3) — well above the 70-77% the
  bus-RECONSTRUCTED occupancy/beat gave (and above the reverted attempt's
  lossy features). This is the empirical proof that the reconstruction-loss,
  not a hidden variable, was the reverted attempt's ceiling.
- **The residual to 100% (≈16% of w1 big-gaps) is NOT in the compact features
  I captured.** Adding bus_ts / q_aged / infl did not move it; adding bus_phase
  OVERFIT the sparse big-gap sample (127 w1 / 92 w3) and dropped it. The
  remaining big-gap misses need the EXACT prefetch-ISSUE decision cycle — the
  true sub-cycle position at which the RTL commits the resume — which my
  offline "crossing = first idle occupied≤refill" reconstructs only coarsely.
  The RTL naturally HAS this exact decision cycle; a compact external key
  approximates it. This is WHY the compact predictor caps below 100% and why
  a lookup (Front 3c) cannot work — the scheduler must model the decision
  cycle, not tabulate a coarse key.

**VERDICT: QUALIFIED GREENLIGHT (same posture as design-doc §4a, now with
exact-state evidence).** The exact internal state closes w0 to 100% and lifts
w1/w3 big-gap prediction to 83-98% — the residual is the exact-decision-cycle
sub-phase the RTL owns but a compact key loses, NOT a hidden variable. The
scheduler is buildable; the risk is entirely in fitting the exact-decision-cycle
resume slot, which must be measured from the RTL's own internal signals during
the build (not a reconstructed crossing).

## 3. WHAT exact internal state the scheduler keys on

All already present in v30_biu (this is the point — the RTL has the state; the
current model just doesn't USE it for the resume decision):
- **`occupied`** = `q_cnt` + `infl` (in-flight fetch bytes) — the EXACT queue
  fill INCLUDING the bytes a mid-cycle fetch will push. (Predictor: the single
  dominant closer.) NOT the bus-reconstructed occupancy.
- **the exact crossing cycle** — the precise cycle `occupied` crosses the
  refill threshold (≤4), tracked as a live event in the BIU, NOT reconstructed
  as "first idle occupied≤4" after the fact. In-flight bytes mean the crossing
  can occur mid-fetch, not only at idle.
- **`q_aged`** — bytes pushed at the previous edge (a push-absorb cycle cannot
  host a commit); already gates prefetch_ok.
- **the CORRECT stretched-grid phase at the crossing** — the true bus-grid
  position (period 4+N), re-synced at T1, advancing one step per COMPLETED grid
  slot. NOTE: the current `grid_phase` (Stage 1) is INERT and its definition is
  BUGGY under waits (the gated Stage-1 SVA fires on 8B/89/B8 — the gph_ff
  Tw-hold vs ph_ff toggle carry offsets the idle-window phase). The scheduler
  build MUST first correct grid_phase to a true stretched-grid counter and
  re-enable `GRID_PHASE_STRICT`, since the resume slot keys on it.
- **completed-cycle kind** (`cur_fetch`/`cur_kind`) — EU-access-completed vs
  prefetch-completed; a cheap key component.

## 4. HOW it models the resume decision (state machine, not a table)

Replace the resume path (`pf_drain` + `pf_lim` consumption threshold + the
`prefetch_ok` occ≤4 gate) with a small resume state machine:
1. On a WAITED bus cycle's completion, arm a `resume_pending` state carrying the
   completed kind and the current exact grid phase.
2. Track `occupied` live each cycle (already available). Detect the EXACT
   crossing cycle when `occupied` first ≤ refill AND `q_aged`==0.
3. At the crossing, sample the true stretched-grid phase (`beat_at_cross`) and
   the exact occupancy. The resume prefetch T1 is issued at the grid slot the
   resume-slot FUNCTION selects: `slot = f(kind, beat_at_cross, occ_at_cross)`
   evaluated on the EXACT crossing/grid state — issue immediately when the
   crossing is grid-aligned, delay to the next grid-aligned slot when it is
   not. Because `beat_at_cross` and `occupied` are the RTL's exact values (not
   reconstructed), the decision fires on the true cycle — the fix for Front 3c's
   wrong-cycle regression.
4. `f` is FITTED during the build from a dense controlled sweep (exp_resume.py
   style) recorded against the RTL's OWN internal signals — measure the resume
   slot as a function of the exact (kind, beat_at_cross, occ) truth table at
   w0/w1/w3, then wire it and gate on the drift harness.

## 5. W0-neutrality plan (prove-able on 169000)

The whole scheduler is armed only on WAITED cycles (like `pf_drain`/`eval_ext`
today): at w0 there are no Tw, `resume_pending` never arms, and the resume path
must reduce EXACTLY to today's `prefetch_ok` occ≤4 commit. Construction: gate
every scheduler action on a `waited-cycle` predicate that is 0 at w0; keep the
w0 commit path byte-identical. PROVE on the full 169000 golden bit+cycle-exact
after every micro-step (the standing gate). The corrected grid_phase must ALSO
be w0-identical to bus_phase (re-enabled SVA passes at w0) — a Stage-1
re-validation folded into the build.

## 6. Blast radius + staged plan

Replaces: `pf_drain`, `pop_sr`/`eu_consuming`/`pf_lim` (the consumption gate),
and the `prefetch_ok` occ≤4 resume gate — the shared prefetch-issue path. Does
NOT touch: the eval/commit machinery (Stage-2 eval_ext), the EU-arbitration
overrides (`pf_late_rsv`, already landed), the flush path (`flush_hold`, already
landed), BUSLOCK. HIGH blast radius (shared prefetch-issue), so:
- **B1**: correct `grid_phase` to a true stretched-grid counter; re-enable
  `GRID_PHASE_STRICT`; prove w0 169000 + w1/w3 golden 1200/1200 with it
  consumed nowhere yet (inert-but-correct). Gate: SVA passes all waits.
- **B2**: measure the exact-state resume-slot truth table (exp_resume.py vs the
  +eudbg internal signals) at w0/w1/w3 — the `f` fit, decoupled from golden.
- **B3**: wire the resume state machine + `f`, gated waited-only; prove w0
  169000 bit-exact; GATE on the drift harness (w1 must fall below 307, w3 below
  476, resume-class first-div count falls from 27/25, CLEAN up) + w1/w3 golden.
- **B4**: iterate `f` against the drift; adjudicate any w0 delta vs a fresh chip
  capture. Stop when the resume third reaches near-zero OR a residual is
  characterized (the exact-decision-cycle sub-phase, if the ≈16% w1 big-gap
  residual proves to need finer state than B1-B3 expose).

Central risk: the same as the reverted attempt if the exact crossing/grid phase
is not truly exact — hence B1 (correct grid_phase) and B2 (fit against internal
signals, not reconstructed) are prerequisites, and B3 gates HARD on the drift
harness, not w0-neutrality alone. The exact-state predictor (§2) is the evidence
this closes; the honest residual risk is the last ≈16% w1 big-gap needing the
exact-decision-cycle, to be confirmed or characterized in B2/B4.
