# Class-5 Timing Campaign — Closing Record

*The document to read FIRST. Standalone: the class-5 (same bus decisions, wrong clock)
cycle-accuracy campaign for the V30 BIU, its floor, its open leads, and the method rules
that were paid for in failures. Cross-referenced from the top of `bringup_log.md`.*

Metric throughout: the signed inter-T1 **gap-error census** under PER-CYCLE-RANDOM wait
vectors (`sw/class5_gaperr.py`); chip = ground truth (read-only `run_chip`), model = the
Verilator TB (bit-identical to fabric on the aligned prefix). Census total under the
authoritative one-to-one pairing matcher: **544u** over seeds 90000-90019.

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
| **E — attackable, characterised** | **CODE→MEM (−2 kind-offset)** — the CODE→EU probe's separating cell | **~72u** | OPEN — architect fix-design pending (§6) |

Architect floor figures (independent framing): **in-principle floor ~30u** (the class-C
temporal cell, at the current model-state observability surface); **operating floor ~414u**
of which **~285u is mechanism-backed built-law scatter** (classes B + D); **0u still not
excluded in principle**; **~130u attackable** (the CODE→EU/EU→EU block, §6 refines it to
~72u fixable + ~58u asymptote).

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

Ruling applied: a key separated → cell reported, **STOPPED before fix design.** The
architect re-enters at the CODE→MEM −2 cell. Key-exhaustion is NOT claimed for this
territory — a key WAS tried and it separated. The map is therefore NOT fully closed:
one characterised, generalising, wait-independent fixable cell remains.

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

1. **Read this record, then `bringup_log.md` top.** The map is complete EXCEPT one open
   lead.
2. **The one open fixable lead: CODE→MEM −2 (~72u, class E).** Characterised, generalising,
   wait-independent, plain-EU-commit-after-CODE 2 clocks late under random waits. The
   ARCHITECT owns the fix design (I stopped at the cell per the ruling). Fix under full
   protocol: enumeration → shadow → w0 gate → **w1/w3/w2 WITH NO WAIT-PATTERN TERM** →
   ONE census (CODE→MEM column → target; DONE-guard 190±10; no new class) → synth/flash/
   silicon. Note it is TI_PLAIN-dominant, NOT the ext_ok-deferred path — enumerate the
   plain EU-commit timing, not just ext_ok.
3. **Do NOT reopen (all closed, mechanism-understood):** the resume law (DONE, 190±10
   guard, falsifiable); the MEMW→CODE store-resume cell (irreducible-by-construction —
   only a NEW model-state signal exposing the forecast reopens it); CODE→IOW scatter and
   the unpaired-CODE→CODE small-cell tail (key-exhaustion, largest clean cell 8u).
4. **Instrumentation in place**: `sw/class5_remap.py` (matcher + disjoint accounting),
   `class5_storeanchor.py`, `class5_poprelease.py`, `class5_forecast.py`, `class5_codeeu.py`;
   shadow fields at eudbg d[62..67] (arbiter + store-resume, behaviour-neutral).
5. **Standing gates** any build must hold: w0 169000/169000, w1/w3 1200/1200 (uniform-
   pattern gate), w2 610/610, DONE-guard unpaired CODE→CODE 190u±10, census w0 control
   0/22188, silicon fabric==TB incl. per-cycle-random vectors.
