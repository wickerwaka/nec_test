# BIU rebuild Stage 2/3 — resume-predicate attempt + characterization

Branch `biu-rebuild`. This round attempted the commit-collapse (Stage 2) and,
principally, the resume predicate (Stage 3, the floor-closer). Result: a
sharper, measurement-backed characterization of the resume law and a THIRD
independent confirmation that it is NOT closable by a local gate on any
existing signal — it requires a free-running prefetch-issue-phase model. No
regressing change was landed; the branch stays at the clean baseline (w0
169000/169000, w1/w3 golden 100%). Adjudication ledger: `biu_rebuild_adjudication.md`.

## Measurement harness (landed, reusable)

`sw/measure.py`: chip-vs-TB drift metric with CACHED chip references
(`sw/testdata/chipcache/`, keyed by seed/waits) so an RTL edit only re-runs the
Verilator TB. Reports per-seed bad-rows, aggregate mean/median, fully-clean
count, first-divergence median. `cache` fills the chip cache; `drift` measures;
`adjud SEED` dumps a single seed for w0-delta adjudication.

**Baseline (branch HEAD, 30 seeds 90000-90029):**
- w0: mean 0.0, CLEAN 30/30 (chip-vs-TB EXACT — the w0 endpoint invariant holds).
- w1: mean 625.6, median 580.5, CLEAN 1/30, first-div median 328.
- w3: mean 613.2, median 625.0, CLEAN 7/30, first-div median 416.

## The dominant drift, localized to one mechanism

Per-cycle localization of the first w1 divergence (seed 90001 @ row 384):
after a WAITED CODE prefetch completes its T4 (row 383), the **chip inserts 3
idle cycles then resumes the next prefetch** (T1 @ 388); the **TB resumes
immediately** at T4+1 via the `eval_ext` deferred-completion path (T1 @ 385).
The core skips the measured bus-grid prefetch-resume gap (biu_model exp4) under
waits — exactly the KB1 (`eval_ext`) kludge from the audit. This is the
dominant mass (Round-2 histogram: retire/MOV-imm/prefetch-resume cadence).

## The resume law, characterized (sharper than the prior campaign)

Measured the chip's resume gap vs queue occupancy and completed-cycle-kind
across seed 90001 w1 (occupancy reconstructed from fetch T4s + QS pops):

- **Big resume gaps correlate with high occupancy at the completing fetch's
  T4** (occ 5-6 → gap 13-15; occ 4 → gap 3-4; occ 2-3 → gap 1). The refill-
  threshold shape is real.
- **BUT occupancy alone does not decide** — the decisive counter-example:
  - row 321 (occ@T4 = **4**, gap **1**, resume immediately) completes a **MEMR
    (EU access)**.
  - row 383 (occ@T4 = **4**, gap **4**, insert gap) completes a **CODE
    prefetch**.
  Same occupancy 4, opposite behavior, split by the **completed-cycle-KIND**:
  after a waited EU access the chip resumes prefetch immediately even at occ 4;
  after a waited prefetch it paces by drain and inserts the bus-grid gap.
- **The completed-kind split still does not fully close it.** The queue-FILL
  case (loader reset-vector fetches, and the fitted w1/w3 golden B8 ramp) is
  ALSO prefetch-after-prefetch, at occ 2 AND at occ 4, and there the chip
  resumes IMMEDIATELY (gap 1). So golden-fill-occ4-after-prefetch (immediate)
  vs fuzz-steady-occ4-after-prefetch (gap) are identical in (occupancy,
  completed-kind) yet differ — separated only by the aperiodic phase the
  sequence arrives with (the Round-3 bidirectional-flip finding).

## Three local-gate attempts, all measured to FAIL (the wall)

Each is w0-neutral by construction (`eval_ext` never fires at w0 — all held w0
golden 169000/169000) and each was reverted:

| gate on `eval_ext` prefetch resume | w1 mean | first-div | verdict |
|---|---|---|---|
| baseline (unconditional immediate resume) | 625.6 | 328 | — |
| remove entirely (route via idle path) | 1065.9 | 14 | breaks fill/loader |
| only after EU access (`!cur_fetch`) | 1063.6 | 14 | breaks fill (also prefetch-after-prefetch) |
| gate on `grid_phase` | 1023.0 | 14 | breaks fill |
| gate on `bus_phase` | 1023.0 | 14 | breaks fill |

Every gate that inserts the steady-state gap also blocks the fill resume the
loader/golden needs, and every existing phase signal fails identically.

## WHY the phase gate fails — the structural root (the key new finding)

`grid_phase` (Stage 1, T-state-pinned, Tw-held) and `bus_phase` (ph_ff) are
BOTH **re-pinned every bus cycle** — active T-states force them to fixed values
(T1/T3 = 0, T2/T4 = 1) each cycle. At a fixed wait level the `eval_ext` cycle
sits at a constant offset from T4, so the phase there is a **constant**, not a
carrier of history — gating on it allows either ALL resumes or NONE (hence the
uniform break). **Neither signal carries the aperiodic instruction-length
history** that Round 3 proved the divergence flips on. The floor-closing
variable is the **relative phase between the EU's queue-consumption timing and
the bus grid** — i.e. *when* the queue crosses the refill threshold, modulo the
bus-cycle length — which accumulates over aperiodic idle runs and is reset by
no existing signal. This is the same conclusion the prior 3-round campaign
reached ("needs a from-scratch bus-grid-accurate queue/prefetch model"), now
re-derived with fresh measurement AND localized to the exact missing state:
a **free-running prefetch-issue-phase** that is NOT re-pinned by bus cycles.

**Consequence for Stage 1's `grid_phase`:** it is a correct and necessary
primitive (T4 always phase 1, T1 always phase 0 — verified on every chip
resume), but as a T-state-pinned signal it is NOT SUFFICIENT to close the
floor. The Stage-0 GO (grid_phase is the flip variable) is confirmed in
DIRECTION but the ACTIONABLE phase must be a free-running issue-phase counter,
not the pinned parity. This is the concrete correction to the Stage-1/Stage-3
plan.

## The real Stage 3 (design for the next attempt)

A **free-running prefetch-issue-phase**: a small counter that advances the bus-
grid position CONTINUOUSLY (every clock, period = the bus-cycle length 4+N
inferred from the T-state stream) and is NOT reset by T1/bus-cycle starts, so
it carries the aperiodic idle accumulation. Prefetch ISSUE is then allowed only
when (a) the queue is below the refill threshold AND (b) the issue-phase is at
the fetch-issue position. After an EU access the position aligns immediately
(matching the row-321 immediate resume); after a prefetch it must wait for the
next issue position (the row-383 gap), and the golden-fill vs fuzz-steady occ4
split falls out of WHICH issue-position the aperiodic history left the counter
at. w0-neutrality must be constructed (at w0 the counter's issue positions
coincide with the current T3->T4 / idle-end eval points) and PROVEN on the
169000 golden; w1/w3 golden must be re-adjudicated against the chip (the fitted
forms may move and must be checked vs fresh chip capture, not the old golden).
This is a structural BIU change with high w0-AND-golden blast radius — a
dedicated effort, measure-first (a controlled fetch-limited-sled sweep to pin
the issue-position law at w0/w1/w3 before coding), NOT a local gate.

## Stage 2 (commit-collapse) status

Deferred as moot for now: re-pointing the 4 `bus_phase` EU consumers onto
`grid_phase` is a behavior change whose only purpose was to feed the resume
predicate; since the pinned `grid_phase` does not close the floor (above), the
re-point would change w1/w3 behavior with no benefit and non-zero regression
risk. The flag-collapse (eval_ext/defer_t4/defer_idle/ff_t4/ext_ok) is
subsumed by the free-running-issue-phase model — it should be done AS PART of
that structural rewrite, not before it. No Stage-2 change landed.

## Stage-3 build round — measure-first Step 1 VERDICT: no simple mechanism closes it

Per the directive, measured the prefetch-issue-position law before building the
free-running counter (full results + numbers in biu_model.md "Prefetch-issue-
position law"). Predictor match rates against the chip's own prefetch T1s
(30 seeds, w0/w1/w3):

| candidate issue law | match | verdict |
|---|---|---|
| first grid_phase-0 slot, occ <= 4 | 98.5% (w1) | misses EXACTLY the big-gap drift cases |
| free-running counter, fixed residue mod (4+N) | uniform residues | REFUTED (no clustering) |
| consumption-triggered (pop-anchored) | 10.4% (w1) | REFUTED |
| occ <= 2 threshold | worse overall | breaks fitted golden fill (Round 2) |
| completed-kind / grid_phase / bus_phase gate | breaks fill @14 | measured last round |

**The free-running counter is REFUTED by measurement** (uniform prefetch-T1
residues at every period) — the aperiodic flip phase is NOT an absolute grid
residue. The drift-driving big-gap resumes are a RELATIVE-phase-of-two-rhythms
phenomenon (bus grid vs EU consumption cadence); no single pinned or free-
running signal carries it. This is the coordinator's explicit "STOP and report
— major finding" branch: the mechanism we localized (a free-running issue-phase
counter) does NOT close the floor. Closing it needs the full two-rhythm
BIU<->EU consumption-vs-grid scheduler, a from-scratch prefetch model — not the
counter. No RTL built this round (correctly, per measure-first: the measurement
said do not build the counter).

## Net this round

- Landed: `sw/measure.py` (drift harness + chip cache), baseline numbers, and
  the sharpest characterization to date of the resume law (occupancy +
  completed-kind + free-running-relative-phase), with three measured local-gate
  refutations and the exact missing-state identification.
- NOT landed: any RTL change (all regressed w1 and were reverted; the branch is
  at the clean baseline — grid_phase + LOCK, no w0/w1/w3 regression).
- The floor is closable (Stage 0 GO stands) but ONLY by the free-running-issue-
  phase structural model, not a local gate — the design above is the next
  attempt. This is the honest state: the payoff (drift drop) is NOT yet
  realized; the round's value is pinning exactly what the closing change must be.
