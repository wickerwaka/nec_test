# Class-5 Timing Campaign — Closing Record

*The document to read FIRST. Standalone: the class-5 (same bus decisions, wrong clock)
cycle-accuracy campaign for the V30 BIU, its floor, its open leads, and the method rules
that were paid for in failures. Cross-referenced from the top of `bringup_log.md`.*

Metric throughout: the signed inter-T1 **gap-error census** under PER-CYCLE-RANDOM wait
vectors (`sw/class5_gaperr.py`); chip = ground truth (read-only `run_chip`), model = the
Verilator TB (bit-identical to fabric on the aligned prefix). Census total under the
authoritative one-to-one pairing matcher: **494u** over seeds 90000-90019 (was 544u before
the H-PHASE landing; the CODE→MEMW RMW-write cell, −50u, is now a landed silicon-confirmed
fix — see §2, §3).

---

## 1. THE FLOOR TABLE (closure classes + reopenability)

Every nonzero census row is assigned exactly ONE (pairing-status, transition-class,
law-cell) triple (`sw/class5_remap.py`, disjoint accounting). The mass then partitions
by CLOSURE CLASS:

| Class | What | Mass | Reopenability |
|---|---|---|---|
| **A — landed fix** | resume-duration law, mid-band, low-band, eu_req=0 corrections (all silicon-confirmed) | — (already removed from the residual) | falsifiable per-law (see §3) |
| **B — built-law scatter (H-SLIP)** | paired CODE-successor: a resume delivered ±1-2 slots early/late makes a +N/−N pair. 100% land in populated law cells, 78-82% slot-scale | ~129u (paired 148u total) | reopens only if the built law's delivery variance is itself reduced |
| **C — irreducible-by-construction** | MEMW→CODE store-resume: chip commits at occ5 one clock early; board-confirmed real (random 17/17, uniform 3/3, w0-absent) | **~30u** (in-principle floor) | reopens ONLY if a new model-state signal exposes the forecast (see §2, §4) |
| **D — key-exhaustion asymptote** | unpaired CODE→CODE genuine residual (largest clean cell 8u < 10u floor); CODE→IOW scatter; small-cell tails | ~190u CC + ~53u IO/tail | reopens if a never-tried key cleanly separates a ≥10u sign-pure held-out cell |
| **A′ — LANDED (this arc): H-PHASE** | **CODE→MEMW RMW-write cell** — the eval_ext deferred-commit was denied by `ext_ok_wr`'s "ready ENTERING T4" rule on the ODD-tw-parity phase class the uniform fit never separated. Fixed by the `tw_par` observable + parity widen. SILICON-CONFIRMED (fabric==TB 15/15 even→early/odd→late). | **−50u (58u→8u)** | falsifiable (any even-parity ready-AT-T4 RMW that is chip-late refutes) |
| **E′ — booked for fresh probes** | CODE→MEMR loads (interval-3, not RMW, don't split on parity) + 2 odd-parity-early rows (H-PHASE edge) | ~25u | OPEN — fresh probes, NOT widens (veto-stacking rule) |

Architect floor figures (pre-landing framing): in-principle floor ~30u (class-C temporal
cell); operating floor ~414u of which ~285u mechanism-backed scatter; 0u not-excluded-in-
principle; ~130u attackable. POST-LANDING: the H-PHASE fix removed 50u (census 544→494);
the CODE→EU attackable block resolved to a landed fix (RMW writes) + ~25u booked for fresh
probes (loads + odd-parity edge).

---

## 2. THE CODE→EU VERDICT (the last never-attacked block)

CODE→EU = 125u (23% of census), never validated under per-cycle-random vectors. Probe
`sw/class5_codeeu.py`, form-free, fit(even seeds)→FREEZE→score(odd):

- **A KEY SEPARATES.** `eu_kind==MEM` → **CODE→MEM (MEMW store + MEMR load) is a
  near-constant ge=−2** (36/38 = 95%; model places the EU access 2 clocks LATE).
  GENERALISES on both seed groups (even 28/30, odd 8/8 PURE), **FLAT across cur_tw 0-5**
  (wait-INDEPENDENT), and across d_cnt@EU-T3. Commit path is dominantly **TI_PLAIN
  (30/36)**, NOT the eval_ext-deferred ext_ok path (5) — so it is the *plain*
  EU-commit-after-CODE timing that is 2 clocks late under random waits, not (as first
  hypothesised) the ext_ok rule-A/B family. ~72u, a CHARACTERISED ATTACKABLE cell.
- **CODE→IOW is scattered** (ge −5..+5, n=21, ~47u) — joins the class-D asymptote.

**LANDED (H-PHASE, silicon-confirmed).** The −2 was mechanism-traced to a DENIAL: the chip
commits the RMW write at the eval_ext DIRECT slot (T4+2) but the model's `ext_ok_wr` ("ready
ENTERING T4" = eu_ready_p1 && eu_ready_p2) rejected it, falling to the plain staged path
(T4+4) — 2 clocks. The finer phase separating chip-early from chip-late was **Tw PARITY**
(T4's displacement against the 2-clock bus microcycle): even-tw → chip early, odd-tw → chip
late, **30/30, 0 violations, board-confirmed, both seed groups, random+uniform**. Loads
(MEMR) do NOT split → the fix is write-scoped (`ext_ok_wr` only). Fix = a `tw_par` flop +
`ext_ok_wr` gains `(eu_ready_p1 && !eu_ready_p2 && !tw_par)`. Gates all green (§3); census
CODE→MEMW RMW 58u→8u; DONE-guard 190→190; synth 0-err setup +5.228ns; **fabric==TB 15/15
even→early/odd→late on silicon**. Residual booked for fresh probes: MEMR loads (17u) + 2
odd-parity-early edge rows.

---

## 3. LAWS LANDED (class A — all silicon-confirmed unless noted)

- **CODE→CODE resume-duration law** — arm: PAUSE iff `d_cnt_a>=3 && occ>=2`; duration:
  `cidle_sel` via the sixth-attempt DIRECT path (SLOT_LAW_RESUME, delta 1) that bypasses
  the q_aged blackout. DONE, **re-ratified** on the authoritative matcher (§5): unpaired
  CODE→CODE 105 rows/190u, largest clean cell 8u < 10u; H-SLIP explains the paired mass.
  Standing DONE-guard invariant: **unpaired CODE→CODE = 190u ± 10**.
- **Mid-band fix** (8086 prefetch-band insight) — `band34_age`, eval_ext-gated, −10%
  class-5 mass, w0-neutral. Silicon-confirmed.
- **Low-band pause** — occ34_age delay window at q_cnt≤2, eval_ext+cur_fetch-gated.
- **eu_req=0 onset family** — `pf_rsv_lead`, `pf_late_rsv`, `owns_slot`, `pf_starved`,
  and `eu_rsv_lead` (silicon-confirmed, untouchable). All eval_ext-gated → w0-neutral.
  Carve-outs RATIFIED to STAY (association ≠ harm; real-outcome-fitted).
- **Phase R** — commit-path unification into one canonical slot decision (behaviour-
  preserving; w0 169000/169000, w1/w3 1200/1200 at every stage).
- **H-PHASE (Tw-parity RMW-write commit)** — the eval_ext deferred RMW-write commit is
  qualified by `ext_ok_wr`; its "ready ENTERING T4" rule (fitted on UNIFORM sweep_rmw) was
  too strict for the ODD-vs-EVEN Tw-parity phase class random waits generate. New local
  observable `tw_par` (a flop: clear@ST_T1, toggle@ST_TW, sampled at the completion eval —
  NOT grid_phase / NOT ph_now, both of which erase the displacement). `ext_ok_wr` gains
  `(eu_ready_p1 && !eu_ready_p2 && !tw_par)` — even-parity ready-AT-T4 RMW writes now take
  the eval_ext direct slot. Write-scoped (loads keep `ext_ok`). SILICON-CONFIRMED
  (fabric==TB even→early/odd→late, per-cycle-random T1-exact). Tooling: `sw/class5_hext.py`,
  `sw/class5_codeeu.py`; ext_ok subterms at eudbg d[68..75].

## 3b. DELETIONS (subsumed, proven strict-superset)

- **pf_drain** — deleted; the resume law is a verified strict superset (its true-positive
  coverage 100% subsumed, residue pure harm).
- **midband_pause** — deleted; the unified law covers 656/656 firings on both corpora.

## 3c. KILLS (NO-GO, each a valuable result)

- **Phase S** (eval_ext PAUSE-only veto) — no zero-false-pause predicate at the ≥10% bar.
- **pf_lim=2** — −291 blow-up.
- **low-band duration control** — reverted, made things worse (suppression only delays).
- **Bus-claim re-key (Rule B)** — the +5.76pt "attributable benefit" was 78% a PROXY
  ARTIFACT (the audit's `model_go=!eu_req` omitted the occ≤pf_lim/q_aged gates the RTL
  already applies); genuine benefit ~0.3-0.4pt. Parked (documented, derived, validated).
- **Arbiter surgery (want_eu demotion)** — hard KILL. The paired mass is 88% prefetch-
  timing (want_eu=0), NOT the want_eu>prefetch arbitration; no discriminator reaches
  ≥60% coverage with <2% false-flip (best 32%/58%). Largest-radius surgery avoided.
- **MEMW→CODE −1 store-resume fix** — mechanism board-confirmed, but (i) the enable
  broke w1/w3 (wait-PATTERN-specific, recent_evx over-fired), reverted per the golden
  falsifier; (ii) the forecast probe then KILLED it: the chip commits BEFORE the only
  distinguishing event (the off-3 pop), so the forecast is not locally observable at the
  commit cycle. Irreducible-by-construction (class C).

---

## 4. THE INSTRUMENT-FAILURE FAMILY (self-validating false positives)

Every one presented as "everything passed." The recurring shape: **an action that looks
safe under conditions not verified.**

1. **gaperr `wv_of` bug** — constructed a new `Random(seed)` per element → a CONSTANT
   (uniform-wait) vector. The ENTIRE census history was a degenerate uniform-wait census,
   not the random-wait target. Fixed → real census 834→544.
2. **Stale Verilator binary** — a failed build leaves the OLD binary; a result that
   reproduces the baseline TO THE ROW is a SMELL, not a pass. Check mtime vs run clock.
3. **Silently compiled-out assertion** — Verilator drops every `assert` without
   `--assert`; an assertion that cannot fire manufactures confidence. Probe with a
   deliberate always-false assert.
4. **Stale `.sof` bitstream** — 14h older than the RTL; flashing it would FABRICATE a
   silicon confirmation that looks clean (fabric matches a TB built from the same stale
   source). Check `.sof` mtime before EVERY flash.
5. **Tempdir leak → EDQUOT** — 32k stale dirs (~9GB) blew the disk quota; every shell
   failed while `df` showed free space. try/finally + rmtree; check eud_/seq_/lbcal_/asrt_.
6. **`finally` does not survive SIGKILL** — outer `timeout` SIGKILLs the interpreter, the
   finally never runs. Ad-hoc scripts get harness discipline or write to the scratchpad.
7. **The lost 288u pairing matcher** — an irreproducible ad-hoc instrument cannot anchor
   anything. Disqualified; replaced by the greedy one-to-one matcher (148u) shipped WITH
   sensitivity error bars.
8. **The proxy `model_go=!eu_req`** — omitted the real conjunct (occ/q_aged), inflating a
   counterfactual 10×. → the corollary (§5).
9. **census544 first-divergence truncation** — a hard cutoff threw away 92/94 agreement
   after a 2-access swap; every historical corpus size was a FLOOR, not a count. Fixed
   with resync-tolerant alignment.
10. **Scratch-space wildcard deletion** — cleaning foreign `/tmp/tmp*` (owned by no one).
    → the new standing rule (§5).

---

## 5. METHOD RULES (standing, paid-for)

- **Freshness**: verify every artifact against its source — rebuild before trusting a
  result; parser field names are part of the chain; sign conventions vs saved tables;
  thresholds re-derived from CURRENT composition, never carried forward.
- **The counterfactual corollary**: score against the REAL implemented rule, FULL
  conjunct, with the baseline's own accuracy printed alongside. No proxy.
- **Goldens are necessary, not sufficient.** They CANNOT gate class-5 work (the census is
  the verdict) — but they are the only instrument for what the random-wait census can't
  see. **w1/w3 = the UNIFORM-PATTERN gate** (they caught the recent_evx over-generalisation
  the census could not). w0 169000 is the decisive w0-neutrality gate.
- **Report data, not direction.** A failed gate is a valuable result. Do not tune past a
  freeze to manufacture a pass. If acceptance fails, revert the enable, keep the shadow,
  report — the architect re-enters there.
- **Board-free first.** Probe on existing dumps before any board/synth/flash spend. The
  campaign rule decides DESIGN choices too — probe both candidates, don't ask.
- **Disjoint accounting** (each row one triple); **pairing with sensitivity error bars**.
- **Key-exhaustion cannot be claimed where no key was ever tried.**
- **Irreducibility, two strengths**: "no key separates on two groups" (class D), and the
  stronger **temporal-observability** argument — the commit is prior to the only
  distinguishing observation (class C).
- **Scratch space**: delete ONLY paths you created, by their specific known prefixes
  (eud_/seq_/lbcal_/asrt_ + your own named scratch); never by generic wildcard, never
  foreign. Report foreign accumulation; let the user decide.
- **Shadow-first**: log-only predictor validated (coverage/false-fire + w0 silence)
  BEFORE wiring behaviour.

---

## 6. WHAT-FIRST (for the next session / the user)

1. **Read this record, then `bringup_log.md` top.** The map's one attackable cell (CODE→MEM
   RMW writes) is now LANDED (H-PHASE, silicon-confirmed); ~25u remains booked for fresh
   probes.
2. **LANDED — CODE→MEMW RMW-write cell (H-PHASE, −50u, class A′).** See §2/§3. Two residuals
   are booked for FRESH PROBES (not widens — the veto-stacking rule forbids a second predicate
   on the same class without a fresh probe): (a) **CODE→MEMR loads (17u, interval-3)** — a
   separate non-RMW mechanism that does NOT split on Tw parity; (b) **2 odd-parity-early edge
   rows** — H-PHASE mispredicts a handful of random-wait phases the 4-vector probe subset
   didn't sample (the census `prev_tw` field even logs them parity-0, a chip-vs-model frame
   discrepancy worth resolving first).
3. **PIGGYBACK still booked: pf_starved toggle-census** — the only carve-out whose ~87u
   entanglement justified a toggle-census; needs its own synth+flash+census cycle; deferred
   from the H-PHASE board session for time.
3. **Do NOT reopen (all closed, mechanism-understood):** the resume law (DONE, 190±10
   guard, falsifiable); the MEMW→CODE store-resume cell (irreducible-by-construction —
   only a NEW model-state signal exposing the forecast reopens it); CODE→IOW scatter and
   the unpaired-CODE→CODE small-cell tail (key-exhaustion, largest clean cell 8u).
4. **Instrumentation in place**: `sw/class5_remap.py` (matcher + disjoint accounting),
   `class5_storeanchor.py`, `class5_poprelease.py`, `class5_forecast.py`, `class5_codeeu.py`;
   shadow fields at eudbg d[62..67] (arbiter + store-resume, behaviour-neutral).
5. **Standing gates** any build must hold: w0 169000/169000, w1/w3 1200/1200 (uniform-
   pattern gate), **w2 610/610 = fabric==TB at uniform w2** (a silicon check, NOT the
   check_seq chip-vs-TB fuzz — that fuzz has a pre-existing boot-prefix divergence),
   DONE-guard unpaired CODE→CODE 190u±10, census w0 control 0/22188, silicon fabric==TB
   incl. per-cycle-random vectors. **RMW-class fix gate of record: your own uniform-RMW
   fabric/chip capture** — no golden suite carries RMW opcodes, so an RMW-touching change
   MUST bring its own uniform-RMW gate.
