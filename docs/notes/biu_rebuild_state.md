# BIU prefetch/bus-grid rebuild — durable campaign state (task #34)

*Fresh-worker handoff insurance (t31_state.md idiom). The #1-priority random-wait
cycle-accuracy rebuild. Charter = `~/.claude/plans/jiggly-zooming-harbor.md`.
Single-writer worker owns the tree + board. Updated at every stage boundary.*

**Victory condition (user-fixed):** a NEW standing random-wait tranche gate,
cycle-exact (Stage H). Census mass reduction is a progress metric, not the finish
line. Dedicated `biu-rebuild` branch; merge to master only at pause boundaries
(P0-P3) with ALL gates green. Auto-mode with stage gates: workers execute,
coordinator verifies each boundary; genuine STOP verdicts (resume-closure NO-GO,
C1 underivable) come to the user.

**Governing corrections (over the old design doc):** (1) w0 bit-exactness (169k +
3.7M) is a HARD gate at every commit — wait-gated selection makes consumption
w0-neutral by construction; the old "adjudicate w0 regressions" rule survives
only for suspected golden mis-captures. (2) Laws constrain via **LAW CARDS**
(`biu_law_cards.md`), never literal fitted predicates.

---

## Baseline freeze / rollback anchor

- **Branch:** `biu-rebuild`, cut from master HEAD.
- **Rollback anchor (merge-base with master): `8598887`** (= master tip
  `8598887602de06cb03fe3c6326d669910cbd5787`, "mc2: 10k campaign on the fixed
  fabric + novelty report"). A pre-existing stale `biu-rebuild` branch (tip
  `767e14e`, a PRIOR rebuild campaign already fully merged into master —
  merge-base == its own tip) was reset forward to master HEAD; nothing was lost
  (verified `git merge-base --is-ancestor biu-rebuild master` = YES before the
  reset).
- Baseline gate battery: `sw/biu_rebuild_gate.sh` → `sw/biu_rebuild_baseline.log`
  (totals recorded in the Stage-A evidence below).

---

## Stage checklist

| Stage | Scope | Board | Pause | Status |
|---|---|---|---|---|
| **A** | Pre-flight: law cards, flop-census lint, bank note, baseline freeze | 0 | **P0** | **IN PROGRESS** |
| B | Measurement: re-based census, per-cell targets, wvec law-fitting, exp_resume closure | ~15 min | P1 | pending |
| C | grid_phase promotion (fix stretched-grid idle window; GRID_PHASE_STRICT; shadow re-point) | 0 | P2 | pending |
| D | Shadow grid-slot scheduler (gsched_*, cov counters, --assert equivalence) | 0 | P3 | pending |
| E | Consume branch-by-branch (E1 resume → E2 commit/eval → E3 arbitration → E4 display); M1 reflash | M1 | — | pending |
| F | EU-side KE1-KE5 (bus-facing dly→grid); M2 reflash | M2 | — | pending |
| G | Savestate coordinated swap (SSA_B map, SS_VERSION bump, ss-sweep battery) | 0 | — | pending |
| H | Victory census + the standing random-wait tranche gate; M3 reflash | ~10 min | — | pending |

---

## Stage A — pre-flight (→ P0)

### A1 — Law cards ✅
`docs/notes/biu_law_cards.md`: 8 cards (LC1-LC8). MUST-reproduce set = LC1 unified
resume/demand-deadline, LC2 low-band pause, LC3 Tw-parity H-PHASE, LC4 eu_req=0
reservation family (untouchable + carve-outs), LC6 Family-5/7 strio vetoes.
CHARACTERIZED = LC5 H-ARB (rekey NO-GO). MAY-discard/class-C = LC7 store_pf_boost
(~30u ceiling, shadow). DELETED = LC8 mid-band + pf_drain. 21 MUST invariant
cases + 2 characterized + 2 class-C. Each card cites RTL line refs (current
2051-line BIU) + evidence (`class5_campaign_record.md` floor table,
`biu_model.md` measured sections, `t33_state.md` census).

### A2 — Flop-census-vs-map lint ✅
`sw/ss_flopcensus.py` (invoked by `sw/ss_lint.py`) + `sw/ss_flop_whitelist.txt`.
Enumerates every reg/flop in v30_biu.sv + v30_eu.sv, classifies architectural vs
sim-only, asserts every architectural flop is SSA-mapped or whitelisted.
- **Result: 181 architectural flops (76 BIU + 105 EU), all SSA-mapped, 0
  whitelist entries needed.** (Consistent with the known-good 82 BIU + 120 EU SSA
  symbols; the reg↔symbol ratio is not 1:1 — multi-bit regs like `cur_addr` split
  into LO/HI symbols; arrays like `rf[0:7]` map to per-index symbols.)
- **Classification rule (documented in the tool):** a flop is a `reg`/`output
  reg` that is a NON-BLOCKING (`<=`) assignment target in a sequential block.
  Sim-only (exempt) = declared inside `ifndef SYNTHESIS` or `ifdef {VERILATOR,
  GRID_PHASE_STRICT, V30_PFX_ASSERT, V30_BACKDOOR}` (V30_BACKDOOR + V30_PFX_ASSERT
  confirmed TB-only `-D` flags in the Verilator build line). Combinational
  `output reg` outputs assigned only with `=` in always_comb (eu_req/eu_ready/
  eu_soon) are NOT flops. Exempt sim-only regs: 9 BIU (cov_*/dbg_direct_q/
  cyc_saw_tw/law_dcnt_probe) + 2 EU (pfx_last_op/pfx_grace under V30_PFX_ASSERT).
  A self-consistency test asserts every currently-mapped reg is detected as a
  flop (proving the `<=` detector has no blind spot).
- **Non-vacuity PROVEN:** a deliberate unmapped test flop (`probe_unmapped_flop`,
  a `<=` target in a clocked block, not SSA-mapped) FAILED the lint (exit 1,
  "architectural flop 'probe_unmapped_flop' (v30_biu.sv:366) is UNMAPPED"). The
  first probe form (one-line `always_ff ... x <= y;`) exposed a detector blind
  spot — STMT_PREFIX now strips leading `always/@()` clauses so one-line clocked
  assignments are caught too. Probe removed; RTL bit-identical to master HEAD
  (`git diff hdl/` empty).

### A3 — fuzz_bank layout note ✅
The fuzz bank is `tests/v30/fuzz_bank/{mc1,mc2,t30-raw,t30-brkem}/seeds/` (NOT a
top-level `fuzz_bank/` — the earlier empty-glob confusion was a wrong path). Seed
counts, git-tracked and on-disk identical: **mc1 = 1295, mc2 = 1294, t30-raw =
568, t30-brkem = 85, total = 3242.** This matches the plan's expected inventory
(A3). `check_fuzz_bank.py` round-trips all four banks (regenerate → GEN-DRIFT hard
fail → TB replay → re-classify vs banked chip rows).

### A4 — Baseline freeze ✅
- Branch cut + rollback anchor recorded (above). Battery: `sw/biu_rebuild_gate.sh`
  (detached, repo-relative log `sw/biu_rebuild_baseline.log`, LOG-MTIME watched),
  a superset of `t30_sweep.sh` adding check_enter_nesting (MASK+WAITED),
  check_fuzz_bank, offline verdict/accept tests, and a bounded savestate sweep.
  Fresh Verilator binary built first (class5 stale-binary rule). Completed
  2026-07-29T00:21:12Z, ALL GREEN.
- **Gate totals (baseline freeze, HEAD 8598887 on biu-rebuild):**
  - ss_lint + ss_flopcensus: PASS (82×2 BIU + 120×2 EU + tag = 203; 181
    architectural flops all SSA-mapped, 0 whitelist).
  - prefix_clear_lint / ea_step_lint PASS; check_race_law 2/2; optable 0 err;
    fuzz_campaign lint PASS; test_fuzz_classify/accept 0 failures.
  - check_ff_t4 9/9 (9 SLOT_FF_T4 fires); check_mod3_illegal 128/128;
    **check_enter_nesting PASS (MASK+WAITED)**; **check_fuzz_bank 3242 stable
    (gen_drift 0, regen_err 0)**.
  - **v0.1 w0 169000/169000 full · w1 1200/1200 · w3 1200/1200** · f0lock 400/400
    · f4a 160/160 · **savestate sweep 2776/2776** · **v0.3 w0 3699997/3699997
    full (3 documented pre-existing exclusions).**
- **wvec replay / A/B trace set (board-free):** `docs/notes/biu_rebuild_wvec_
  baseline.json` (80 deterministic case digests = class5 seeds fz90000..90019 ×
  wvec {ws0/wmax0 w0-control, ws5/wmax1, ws7/wmax3, ws11/wmax7}); generator/
  checker `sw/biu_rebuild_wvec_freeze.py` (model-side `run_tb_internal` only, NO
  board). Stage C/D re-run `--check` to attribute every changed row; round-trip
  verified PASS (80/80 identical). This is the R0 "baseline-versus-refactor trace
  gate" for the shadow-promotion stages.

### P0 boundary
STOP at P0 for coordinator verify + Codex critical review of the law cards before
Stage B dispatches. (This worker does NOT proceed to Stage B.)

---

## Commit ledger (biu-rebuild branch)

| Commit | Substage | Contents |
|---|---|---|
| `d7cc0af` | A1 | biu_law_cards.md |
| `3c0320a` | A2 | ss_flopcensus.py + ss_flop_whitelist.txt + ss_lint.py wiring |
| `5e7a6ad` | A3+state | biu_rebuild_state.md (this doc, incl. A3 note) |
| A4 | A4 | biu_rebuild_gate.sh + biu_rebuild_wvec_freeze.py + wvec_baseline.json + baseline evidence |

## Process rules (paid-for this stage)
- **Completion-marker grep must match the LITERAL emitted string.** The battery
  emits `=== BASELINE_BATTERY_DONE  <ts> ===`; a watcher grepping a pattern that
  assumed a different spacing/format missed it and timed out. Rule: grep the
  exact literal marker substring the script prints, nothing fancier.

---

## Open questions / carried threads

- **B4 exp_resume closure (Stage B):** is `resume_slot` a function of (phase, occ,
  fill) or is hidden state left? NO-GO = STOP, report to user (data-only, zero RTL
  risk). Stage-0 said GO (`biu_rebuild_design.md §4a`), but B4 re-runs on CURRENT
  RTL.
- **C1 stretched-grid idle-window (Stage C):** grid_phase is INERT and its
  stretched-grid definition has a documented KNOWN LIMITATION (post-waited idle
  window offset; v30_biu.sv:1715-1727). C1 must fix it from B3's wvec cells before
  re-enabling GRID_PHASE_STRICT; if underivable → data-only STOP.
- **LC5 H-ARB rekey = NO-GO:** re-keying arbitration off the current predicate is
  a STOP-and-report design decision, not a worker action.
- **LC7 class-C ~30u:** reopens ONLY if the grid model surfaces a new pre-commit
  observable (beat_at_cross exposing the off-3 pop forecast).
- **Absolute census mass is ~2x pre-fix-inflated** (t33-v2 R2): Stage B1 must
  re-base on the fixed fabric before it seeds any quantitative baseline. Ranking
  is stable (CODE→CODE > EU-access > EU→EU).
- **done_mismatch (24.5% mass)** is a distinct DIRECTIONAL regime (fabric drifts
  behind from early on), not floor tail — a first-class net-drift family to fit
  (t33-v2 R3).

## Conflicts found between the plan and on-disk docs (report, don't improvise)
1. **Stale line refs in the audit / unification-plan docs.** `biu_rebuild_audit.md`
   and `class5_path_unification_plan.md` cite a 952-line BIU at `c0c28f1`
   (v30_biu.sv:456, :819, etc.). The current BIU is 2051 lines (biu-rebuild ==
   master HEAD 8598887). All A1 card line refs are to the CURRENT RTL. No action
   needed beyond this note; the design intent in those docs is unchanged.
2. **A pre-existing `biu-rebuild` branch already existed** (prior rebuild
   campaign, tip 767e14e, already merged into master). Resolved cleanly by
   resetting it forward to master HEAD (it was a strict ancestor). Recorded above.
3. **`biu_model.md` lives at `docs/facts/`**, not `docs/notes/` (the plan/records
   reference it without a path). Noted for future workers.
4. Nothing in the design docs contradicts the plan's Stage sequence or the law
   dispositions; the law cards reconcile with the t33-v2 corrections (H-ARB
   downgraded to CHARACTERIZED, MUST = silicon invariants not predicates).
