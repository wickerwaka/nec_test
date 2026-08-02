# Retirement of the biu-rebuild campaign (task #34)

**Date:** 2026-08-01
**Decision:** the user's, recorded in the ucsim-t campaign plan.
**Status:** task #34 CLOSED — retired, not paused, not resumed.

---

## 1. The decision

> **Retire biu-rebuild (task #34) entirely.** The C++ sim becomes the reference
> model; the RTL is eventually regenerated from the closed laws in a fresh
> campaign. The P1-v2 resume path is discarded; the law corpus, law cards,
> frozen oracles, and census artifacts are INHERITED here as the constraint set.
> Formal retirement note + task closure in T0.
> — ucsim-t campaign plan, "User decisions (2026-08-01)"

Three separable parts, all in force:

1. **Task #34 is closed.**  The campaign is retired outright.  The P1-v2 resume
   path — the Stage-C `resume_slot[phase][occ][fill]` sled capture that the
   campaign was blocked on — is DISCARDED as a work item of that campaign.  It
   is not "paused pending a board window"; there is no resume path.
2. **The C++ simulator is now the reference model.**  `sim/` is the artifact
   that answers both the architectural question (settled: ucsim campaign,
   7.34 M cases exact, `docs/notes/ucsim_campaign_verdict_2026-08-01.md`) and
   the timing question (open: the ucsim-t campaign).  The RTL is no longer the
   thing being made correct; it is a downstream consumer.
3. **RTL regeneration is DEFERRED to a future campaign**, to be driven from the
   laws once they close in the simulator.  No RTL work is in scope for ucsim-t.

## 2. What is inherited, and by whom

The law corpus is **formally inherited by the ucsim-t campaign as its
constraint set**.  Inheritance means: these artifacts are the constraints the
simulator's timing model must satisfy, and each is either replayed as a gate or
explicitly retired with a written reason.  Nothing is silently dropped and
nothing is re-derived.

| inherited asset | location | how ucsim-t uses it |
|---|---|---|
| **Law cards C1-C16** — 11 MUST cards (C1-C7, C9-C12) + 5 provisional; **LC8 is DELETED and must not be reimplemented** | `docs/notes/biu_law_cards.md` | the MUST set becomes sim unit gates; stage exit T1 |
| **Frozen black-box oracles** — 104 oracle/validation JSONs: chip-oracle-v2..v7 (arbitration, 11-tuple keys), prefix-phase (mod-3 law), strio-completion v2..v5, decoder-drain v1/v2 + multibyte, flush / string / multistack / swint / nmi / hwint, case250 INS factorials (800 cells) | `sw/testdata/biu_blackbox/` | L1 state-injection unit gates (T1) and L2 image replay (T2) |
| **Census artifacts** and the class-5 unified-law material | `docs/notes/`, census JSONs | triage lenses for the T3 fuzz_bank survey |
| **B1-B4 tooling** — `sw/b1_recapture.py`, `sw/b2_predict.py`, `sw/b3_fit.py`, `sw/b4_closure_v2.py` + their logs and `sw/b4_resume_events.json` | `sw/` | retained as measurement/analysis tooling; see §3 for what their RESULTS are worth |
| **Design documents** — stretched `grid_phase`, `resume_ok(phase, occ, fill)`, the §4 truth-table measurement spec, the flush law, mission-H commit/eval deferral, queue-push defer, cadence laws | `docs/notes/biu_rebuild_design.md`, `docs/facts/biu_model.md`, `docs/facts/measurements.md` | the mechanism hypotheses T1/T2 test |
| **Pilot laws** — INS (`eval law e=(tw>0)`, S-linear deadlines, `R2 issue = R1.T4+e+18+off`) and ENTER (grant law: slots at busfree+1/+3 then free-running; chain = prev.T4+1) | `sw/ins_ucode_pilot.py`, `sw/enter_ucode_pilot.py` | must be REPRODUCED from the sim, not from the offline scripts (T2) |
| **Timing measurements** — 306 F-spacing retirement measurements | `docs/facts/timing_measured.json` | the T1 cadence calibration corpus |
| **fuzz_bank `chip_rows`** — 3,242 seeds × ~4k per-clock pin records | `tests/v30/fuzz_bank/` | the T3 monster gate |

The inherited constraint set and every T0 provenance decision are recorded in
`docs/notes/ucsim_t_provenance.md`.

## 3. Carried-over caveat: B4 closure is NOT established

The one inherited RESULT that must not be carried over at face value is the B4
`(grid_phase, occupancy, fill)` closure claim.  It was adjudicated in T0 and
**retracted**; the full argument, with citations, is
`docs/notes/ucsim_t_provenance.md` §0.1.  In short:

* `sw/b4_closure_v2.log:31` — the artifact commit c23c6c1808 itself committed —
  reads `=== B4_V2_VERDICT: NO-GO  (violations=21) ===`.
* The pre-registration (`sw/b4_closure_v2.py:26-27`, committed 3 minutes before
  the run) said *"GO iff 0 testable-cell violations. Any violation ⇒ NO-GO"*,
  with `w` inside the match key and no w0 carve-out.  The `0/988 at w1/w3`
  headline restricts the falsifier's domain AFTER the numbers were seen.
* The 2026-08-01 audit (`docs/notes/biu_eu_session_summary_2026-08-01.md:31-47`)
  additionally invalidates the figure on grounds unrelated to w0: `seed` and
  `eu_ord` are in the match key, so it never compares two different preparation
  histories, and 9,936 of 14,536 events are excluded.  It downgrades the result
  to *"within-history repeatability"*.

**Usable residual claim:** within-history phase-parity repeatability holds
988/988 at w1/w3 on EU-preceded resumes.  That is not state closure, and
ucsim-t may not assume `(phase, occ, fill)` closes the machine.

Documents that still assert `B4 = GO` (`docs/notes/biu_rebuild_P1.md:90`,
`docs/notes/biu_rebuild_state.md:50/334/484-488`, and the biu-rebuild campaign
memory file) are **stale**.  They are historical records of a retired campaign
and are deliberately left unedited; the erratum is recorded in the ucsim-t
ledger instead.

## 4. What happens to the branch and the worktree

* **Branch `biu-rebuild` stays as ARCHIVE.**  It is not merged, not deleted,
  not rebased.  Its head is `d3f1c386ad "WIP - campaign paused by user order"`.
* **The paused worktree files are NOT to be touched.**  The uncommitted
  modifications under `hdl/` and `sw/`, and the untracked `docs/notes/biu_*`
  discovery notes, belong to the retired campaign.  ucsim-t work stages only
  its own files; `git add -A` is forbidden in this campaign.
* **No RTL work, no Quartus, no flashing** is in scope for ucsim-t.  (Note the
  standing debt this leaves: task #31's two ENTER RTL fixes remain unflashed.
  That debt now belongs to the future RTL-regeneration campaign, not here.)

## 5. Unresolved threads, and where they went

The campaign's open questions are not closed by retirement; they became the
ucsim-t discovery scope.  Recorded here so nothing is lost:

| unresolved in biu-rebuild | now |
|---|---|
| Stage-C `resume_slot[phase][occ][fill]` truth table (the capture that blocked the campaign; spec in design §4, k = 0..7 NOP-prepend sled) | ucsim-t **T2**, as a BOARD capture — but only if the retained data underdetermines the mechanism, and with the §0.1 caveat that the coarse tuple is not known to close |
| `grid_phase` stretched-grid idle-window limitation (post-waited idle offset) | ucsim-t **T2** |
| the 20-28 % per-cell fittability residual (fabric-vs-chip); `prev_tw` sign-flip law; `done_mismatch` directional regime | ucsim-t **T3** triage lenses; the sim starts from mechanism and must beat the 72-81 % fabric fittability |
| strio mature-RMW cell; ≥2-overlapping-pop completion states; multi-byte BCD/imm/branch decoder classes | ucsim-t **T4** parked probes |
| parked ucsim probes: A30 (BRKEM+INTR bank-A), status-latch persistence after ROM sweep, R6 CL=0 uninterrupted, POLL BUSY split probes, R7 CMP4S | ucsim-t **T4** parked probes |

## 6. Why retiring was the right call (recorded for the future campaign)

The campaign's own artifacts say it: the 2026-08-01 audit removed long-trace
chip-versus-RTL classification from the discovery boundary and left "the full
BIU/EU model explicitly open".  The rebuild was trying to make an RTL
implementation correct against laws that were not yet closed, using an RTL that
was simultaneously the instrument measuring them — the circularity the B4
episode is a symptom of.  Putting the reference model in software first breaks
that loop: the sim has no fabric of its own to confound the measurement, its
laws are stated as mechanisms in code rather than as fitted tables, and the RTL
can then be regenerated from laws that have already been proven sufficient
against silicon.

This is also where the campaign's guiding principle bites hardest.  A large
fitted table or a many-cased rule is a signal of misunderstanding, not a
deliverable; a `resume_slot` truth table indexed by a coarse tuple that
provably does not close is exactly that signal.  The successor campaign's
standard is that every law table must either collapse into a small mechanism —
a counter, a latch, a phase bit interacting with another — or have its
irreducibility argued from the silicon's own economics.
