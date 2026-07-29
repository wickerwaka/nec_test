# BIU prefetch/bus-grid rebuild — P1 package (Stage-B close, for consolidated Codex review)

*The pause-point P1 deliverable (task #34). Routes to the coordinator for the
consolidated Codex review — the cards re-review folded in, per the P0 arrangement.
**Stage C (grid_phase promotion, the first RTL-touching stage) dispatches only
after this review clears.** All results below are on the `biu-rebuild` branch
(HEAD `f7e4652`), RTL == master (`8598887`, no RTL touched), board on the master
pin (fae64d5), captures 0-wedge / 0-flash. Full detail + commit ledger in
`docs/notes/biu_rebuild_state.md`; law cards in `docs/notes/biu_law_cards.md`.*

## 1. The acceptance-basis matrix (terminal state)

**8 laws independently gated board-free-re-runnable + CONTROL silent + M-LC3
board-by-construction (milestone-gated).** From `sw/biu_law_mutation.py` (ok=True):

| law | gate | law | gate |
|---|---|---|---|
| LC1 resume | wvec | LC4b pf_late_rsv | wvec |
| LC2 low-band | wvec (seed 90364) | LC6 strio veto | lc6 gadget |
| LC4a pf_rsv_lead | wvec (seed 90270) | ff_t4 / eval_ext / race | ff_t4 / w1w3 / race |
| **CONTROL** (store_pf_boost) | **SILENT (non-spurious)** | **M-LC3 H-PHASE** | **board-by-construction** |

- **G-LC2/G-LC4a** closed via the gate-search directed-seed finder; **G-LC6** via a
  hand-built strio-OUTSB gadget gate (`check_lc6_gate.py`).
- A **stale-binary instrument-failure** was caught (a first re-run's "fully green"
  was a phantom from a syntax-broken mutation running on the prior binary) and
  fixed (build now requires exit 0 + a freshened mtime); disclosed in full.

## 2. G-LC3 (H-PHASE) resolution — board-by-construction, milestone-gated

- **Board-free gate NOT achievable — proven.** Four attempts (isolated + sequence
  RMW gadgets, broad seed search, the EXACT class5 census combos where
  `class5_hext` confirmed the 29-case cell) + a **decisive raw per-cycle-row diff**
  over all 360 census combos: **M-LC3 is BIT-IDENTICAL to the current model.** The
  widen's observable footprint exists only on the `sweep_rmw` directed structure,
  which is **genuinely unrecoverable** (never a tracked path). No gate — board or
  board-free — can detect M-LC3 on a reproducible config.
- **Silicon provenance already on record** (campaign A′: fabric==TB 15/15 + 30/30
  even→early/odd→late; RTL unchanged since).
- **Terminal (coordinator-confirmed):** accept board-by-construction + a
  **mandatory uRMW hw-A/B check at every milestone M1/M2/M3, with a CHIP-SIDE
  POSITIVE CONTROL** (iterate the directed structure on-board until the CHIP shows
  the interval-2 even→early signature, THEN fabric==chip; FAILS VACUOUS if the
  signature can't be produced). Banking those chip rows at M1 makes the board-free
  replay gate buildable (deferred, not dead → path back to 9-green stays open).
- **Honest-tension (to re-establish at M1):** the landing's −50u census effect vs
  the zero raw-diff census dependence — presumably the landing predates the
  `wv_of` bug fix and/or was directed-structure-measured.

## 3. Canonical re-based census — 39780

`sw/b1_recapture.py`, full 2313-seed family, chip vs fabric fae64d5, 2026-07-29,
0 runerr, 172s. **This supersedes the stale pre-fix 72438 (~2× inflated);** every
later delta cites 39780.

| regime | seeds | mass | net | CODE→CODE | EU→CODE | CODE→EU | EU→EU |
|---|---|---|---|---|---|---|---|
| TIMING | 1771 | 30592 | +1344 | 54.9% | 16.5% | 15.6% | 13.1% |
| done_mismatch | 542 | 9188 | **−1436** | 38.1% | 21.9% | 16.2% | 23.7% |
| **GRAND** | 2313 | **39780** | | | | | |

Confirms t33-v2: (R2) mass **−45%**, ranking stable; (R3) done_mismatch a distinct
**directional** regime (fabric drifts behind, net −1436).

## 4. Per-cell held-out TARGETs (P1-frozen) — `sw/b2_predict.py`

| cell | held-out sign acc / majority | **mass-fittable** |
|---|---|---|
| CODE→CODE | 82.0% / 50.4% | **78.6%** |
| EU→CODE | 81.5% / 53.5% | 80.6% |
| CODE→EU | 74.9% / 52.9% | 72.3% |
| EU→EU | 78.6% / 63.4% | 79.7% |

**72-81% of the mass is context-predictable per cell** — far above the t33-v2
aggregate 55%. Even the "hard" CODE→EU block is 72% fittable. The rebuild must
meet/beat these; the ~20-28% per-cell residual is the observable floor.

## 5. Fitted grid-term laws — `sw/b3_fit.py` (held-out validated)

- **prev_tw SIGN-FLIP (CODE→CODE, the two-rhythm grid beat phase):** prev_tw=0 →
  −1.68 (fabric later); prev_tw=1/2/3+ → +0.72/+0.88/+1.35 (fabric earlier). **ONE
  grid-observable variable explains 74.7% of the dominant cell's mass held-out**
  (72.2% sign acc vs 50.4% majority). The beat-phase premise is confirmed on fresh
  data.
- **EU-access block (grid key prev_tw, cur_tw, prev_bs):** CODE→EU 74.3%, EU→CODE
  78.4%, EU→EU 75.9% mass-fittable — the never-attacked block is 74% grid-fittable.
- All laws in GRID terms (prev_tw/cur_tw = the stretched-grid phases Stage C makes
  first-class), NO model-internal keys.

## 6. B4 exp_resume closure — **GO**

`sw/exp_resume.py`, aligned phase-sweep on the current RTL (14536 events, 8 seeds ×
k0-7 × w0/w1/w3). Verdict: constant 440, clean-parity 94, wander 31. **Pre-
registered WANDER accounting: 26 excused by occ-variation, 5 by w0 bit-exactness,
0 genuine.** → **The resume law CLOSES over (grid_phase, occ, fill); no hidden
state remains.** Re-confirms Stage-0 on the current RTL — the dominant floor is
grid-closable.

## 7. LC6 silicon provenance — confirmed

P-C14 (T3-veto) + P-C15 (TI-exemption) + P-C16 (F7 idle-arm): 1 + 9 strio-OUTSB
gadget configs at w0, **all chip==fabric bad=0** → the Family-5/7 veto behaviors
are silicon-correct across the queue-state range. Banked (`lc6_provenance{,_ext}.jsonl`).

## 8. w0 floor — intact (a flag caught + resolved)

A k=9 strio-gadget w0 chip-vs-core divergence was flagged and given a bounded
probe: TB-vs-FABRIC bad=0 (core self-consistent), first divergence at row 198/467
→ rows 0-197 (the whole gadget) chip==core==exact; the divergence is only the
post-gadget wander (my un-fenced synthetic gadget). **w0 bit-exactness on
characterized code is intact** (golden 169000/169000 + fuzz-bank are the real w0
guarantees).

## 9. What this greenlights + the standing gates Stage C inherits

**The rebuild's entire premise is confirmed on fresh data:** the residual is
dominantly grid-phase LAW (72-81% fittable per cell; prev_tw alone = 74.7% of the
dominant cell), and the resume law CLOSES over grid state (B4 GO). Stage C
(grid_phase promotion) is the greenlit first RTL stage.

**Standing gates any RTL change must hold** (all board-free, added this campaign):
`ss_lint` + `ss_flopcensus` (flop-census-vs-map), `check_lc6_gate` (strio veto),
`biu_law_mutation.py` (the acceptance-basis matrix, ok=True), `biu_rebuild_wvec_
freeze --check` (the timing-sensitive A/B set incl. directed seeds),
`biu_rebuild_gate.sh` (full battery), plus the pre-existing set. w0 169k + w1/w3 +
v0.3 3.7M + fuzz-bank 3242 remain the hard floor.

**Open (deferred, non-blocking):** the M-LC3 uRMW milestone check + its chip-side
positive control (M1); the deferred board-free replay gate (buildable from M1's
banked rows → path to 9-green); LC3's −50u honest-tension re-establishment (M1).

---
**Verdict requested:** does the Stage-B package + the cards (v2 + the B0/board
findings) clear for Stage C dispatch? P2/grid_phase promotion is w0-neutral by
construction (bit-identical to bus_phase at w0) and shadow-first per the plan.
