# Task #29 close-out — massive fuzz expansion

Status at report time: the full generation → classification → acceptance →
campaign → bank/gate/report stack is built, gated, and running the first scaled
campaign (`mc1`). The final 100k-seed campaign numbers + coverage deltas are
appended when that run completes; everything else below is final.

## 1. Architecture

| Layer | Module(s) | Role |
|---|---|---|
| Generation | `optable.py`, `gen_soup.py` (Tier A), `gen_raw.py` (Tier B) | full-opcode-space draw; contained fall-through; scrub pass; lint-proven no chip-wedge image |
| Classification | `fuzz_classify.py` | `diff_rows` (check_seq refactor, byte-identical), verdict tree SUCCESS/FUNCTIONAL/TIMING/KNOWN_ACCEPTED/QUARANTINE, signatures, drift, EscalationPolicy |
| Acceptance | `fuzz_accept.py` + `testdata/fuzz_accept_rules.json` | brkem_gap, cadence_floor (frozen v1.0), lea_mod3, static — strict fail-safe rules |
| Campaign | `fuzz_campaign.py` | seed→config derivation, board hw-ab / tb-only, sessions, resume, circuit breaker, escalation, stratified SUCCESS ballast |
| Bank/gate/report | `fuzz_bank.py`, `check_fuzz_bank.py`, `fuzz_report.py`, `sig_ledger.json` | promotion/dedup, standing replay-regression gate (GEN-DRIFT hard fail), rollup, novelty ledger |

## 2. Campaign numbers

- **Lint gate**: 10k soup + 100k raw images, 0 chip-wedge hits, 0 compose errors.
- **Pilots** (board, reflashed task-#30 build): BRKEM-200 — 85 BRKEM seeds, 0
  quarantines, **0 power cycles**, following-seed clean, positional check
  validated; raw-1k — **0 wedge**, no-done 99% (window-only), verdicts sane;
  budgeted-wrand re-cal 150.
- **Bank**: 653 banked (85 BRKEM + 568 raw); **check_fuzz_bank PASS 653/653
  stable** (0 worse/gen_drift/float-floor/new-sig). Ledger: 809 campaign sigs +
  688 legacy baseline.
- **mc1 session 1** (strict mainline, escalation armed): clean — 5 waited/evt
  TIMING + 2 w0 SUCCESS, **0 escalation triggers** (0 w0-FUNCTIONAL, 0
  provenance, 0 new-sig w0 TIMING); stopped at the `--stop-after 5` review gate.
- Throughput (hw-ab, serve v2 + delta): **~10 seeds/s** single-thread.

## 3. Discovery ledger

| Finding | Class | Status |
|---|---|---|
| **LEA (0x8D) mod=11 core wedge** (pilot-w0 k=30) | latent EU decode gap: mem-only op with a register operand parks at S_HALT while the chip executes it | FIXED (task #30): op_lea mod=11 branch loads the stale-EA latch, cycle-exact; whitelist assert on the terminal-else park; generator excludes it; lea_mod3 accept rule for the residue |
| **F7a COLD-ARM assert** | over-narrow task-#24 strio invariant firing under waited/interrupt-shifted timing | FIXED (Phase 5): board-arbitrated chip-correct -> downgraded to counter |
| FE /6,/7 mod=11 (chip-executes), FE /2,/4 (chip-runaway) | mem-only-adjacent illegal forms, core parks | BOOKED (whitelist-asserted; unreachable from soup) |
| w0 soup-breadth functional class | containment escapes (a gadget loading a wild PS/DS) | BOOKED (survey-mode census; distinct from the k=30 hang) |
| LEA-mod3 stale-EA residue law | undocumented microcode-path-dependent latch value | BOOKED deferred physics (tranche residue cases are the raw material) |

The two BUGS (LEA mod=11, F7a) were both invisible to the curated green suites —
coverage vacuity, the campaign's stated target — and both were surfaced by the
soup. The k=30 fix passed the full ~3.87M-case golden sweep with zero
regressions before reflash.

## 4. Meta-finding: the vacuous-gate pattern

Three green gates were VACUOUS this campaign (they checked only the known):
F7a's over-narrow assert, the terminal-else silent S_HALT park (no assert), and
ss_lint's unmapped-flop blind spot (`last_ea` mapped only after the fact). Full
writeup + the recommended **flop-census-vs-map lint** in
`docs/notes/standing_gates.md`. The mechanization rule adopted — instrument the
silent path so the first exercise is caught — closed the first two.

## 5. Cadence floor

Frozen v1.0 (`max_step=9`, `slip_per_waited_fetch_max=0.25`) from the clean
fixed-w1/w3 corpus. The budget-coupled wrand re-cal + mc1's waited/evt TIMING
population confirm the wrand floor is genuinely wider (steps to ~24, rate to
~0.65). A widening PROPOSAL (`max_step 15`, `rate 0.40`) is documented in
`cadence_calibration.md`, **NOT applied** — it needs a >=500-seed budgeted-wrand
sample to confirm the tail is one mechanism. That sample rides mc1 as
observe-only side collection (the wrand seeds in `mc1/results.jsonl` are it).
Conservative-by-design: floor over-acceptance masking a real waits bug is risk #1.

## 6. Coverage

Pilot coverage (fuzz_cov): the campaign exercised prefix combinations
(incl. the previously-unexercised repnz/lock/repnc/repc), the full opcode-signature
space, and queue-fill-at-dispatch buckets that the curated suites never touched.
Per-campaign deltas vs the pre-campaign baseline are in each campaign's
`coverage.json`; the mc1 full-run delta is appended at completion.

## 7. Continuation cadence (the user decision)

At the measured **~10 seeds/s** board rate:
- 100k seeds ≈ **3 board-hours** (mc1, one campaign).
- 1M seeds ≈ **~30 board-hours** (~4 watched days at reasonable session lengths).
- "millions" ≈ **multi-week** board occupation — survivable via sessions +
  resumability (pure (cid,k) derivation ⇒ identical re-run), but a real
  commitment of the single shared board.

Recommendation: run `mc1` to completion (3 h) as the first full campaign, review
its bank/report, and decide the sustained cadence from there. The infra scales
(parallel TB replay for forensics, board is the only serial resource); the gating
question is board-time budget, not tooling. The escalation policy makes long
unattended runs safe (any real w0 functional / provenance alarm / new w0 timing
signature STOPs and banks the evidence).
