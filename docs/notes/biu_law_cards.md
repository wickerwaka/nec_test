# BIU class-5 / waited-cadence LAW CARDS

*Stage-A1 deliverable of the BIU prefetch/bus-grid rebuild (task #34, plan
`jiggly-zooming-harbor.md`). The rebuild is constrained by the **silicon-observed
invariant I/O cases** on these cards (the MUST-reproduce set), NOT by the literal
fitted predicates below (the MAY-discard set), per the t33-v2 R4 correction
(`t33_state.md`). A rebuild that reproduces every card's invariant cases is
correct even if it computes them from grid state instead of the current flags.*

**Provenance.** Line refs are into `hdl/rtl/core/v30_biu.sv` / `v30_eu.sv` at the
`biu-rebuild` branch baseline (= master HEAD `8598887`, 2051-line BIU). Evidence
is sourced from `class5_campaign_record.md` (floor table §1, laws §3),
`docs/facts/biu_model.md` (measured sections), and `t33_state.md` (mc1 census).
The audit docs (`biu_rebuild_audit.md`, `class5_path_unification_plan.md`) predate
this RTL (they cite a 952-line BIU at `c0c28f1`); their line numbers are STALE —
use the refs on these cards.

**Global w0-neutrality invariant (all cards).** Every law below is gated by
`eval_ext` and/or `cur_fetch` and never fires at w0. The w0 golden
(169000/169000) + w1/w3 (1200/1200) are the standing falsifiers that this holds;
the mc1 census w0-control is 0/22188. Any rebuild expression of a law inherits
this: `waited ? new : legacy-exact`.

Card index:
- **LC1** Unified resume / demand-deadline (SLOT_LAW_RESUME) — MUST, silicon-pinned
- **LC2** Low-band pause — MUST (owns the d_cnt==2 hysteresis cell)
- **LC3** Tw-parity H-PHASE RMW-write commit (tw_par/ext_ok_wr) — MUST, board 15/15
- **LC4** eu_req=0 reservation family — MUST (ratified untouchable); carve-outs noted
- **LC5** H-ARB eu_ready arbitration — CHARACTERIZED only; rekey NO-GO
- **LC6** Family-5/7 strio vetoes — MUST (narrow, hardened w/ counters)
- **LC7** store_pf_boost / MEMW→CODE−1 — class-C irreducible ~30u ceiling; shadow only
- **LC8** mid-band + pf_drain — DELETED / subsumed (do NOT re-implement)

---

## LC1 — Unified resume / demand-deadline (SLOT_LAW_RESUME)

**Intervention performed.** Replaced the staged `law_block` resume delivery
(fired via SLOT_TI_PLAIN, STAGED, delta=2 → commit at T4+2 → hit the `q_aged`
blackout → cidle 3 slipped to 4) with a DIRECT-path resume: on a waited
completion eval the BIU latches a scheduled resume and fires `SLOT_LAW_RESUME`
(COMMIT_DIRECT, delta=1) at T4+`cidle_sel`, so T1 = T4+1+cidle_sel for both
durations, bypassing the q_aged blackout at T4+2.

**Silicon-observed invariant I/O cases (MUST-reproduce).**
- After a WAITED CODE fetch completes with the queue in the refill regime, the
  post-fetch CODE prefetch resumes at a **grid slot determined by the completed
  cycle's occupancy/aging + Tw count**, NOT at the model's old unconditional
  T4+1. Steady-state fetch-limited streams take the ~3-idle-slot resume gap;
  queue-fill ramps resume immediately (`biu_model.md` "Two-rhythm predictor";
  arbitration exp4: "prefetch resumes after 3 idle cycles").
- **Arm C silicon pin: the chip pins cidle=3 at high Tw** — N=8 gap 22:12, N=12
  gap 28:2 (the old staged path emitted cidle 3 exactly zero times). The
  `law_dtw>=4 → sel=3` arm is NOT softened.
- The unpaired CODE→CODE residual after the law is **190u ± 10** (the standing
  DONE-guard); largest clean cell 8u < the 10u observable floor.
- Resume slot flips as a ≤2-valued function of leading grid phase with
  occupancy/fill fixed (`biu_rebuild_design.md §4a`: 256/266 aligned sweep cases
  CONSTANT or CLEAN-PARITY) — the bidirectional Round-3 A2 finding.

**Fitted predicate as implemented (MAY-discard).**
- Arm: `law_arm` = `eval_ext && cur_fetch && law_dcnt>=3 && 2<=occupied<=4 &&
  !q_flush && !eu_hold` (v30_biu.sv:768).
- Duration select `cidle_sel` (`law_sel`, v30_biu.sv:1969-1993): `3` if
  `law_dtw==0 || law_dtw>=4 || occupied<=2`; `4` provisional (→3 on a pop at
  T4+2) if `occupied==3`; else `4`.
- Due: `law_due` = `law_window && (law_sel-2 <= law_ctr <= law_sel) && !q_flush
  && !eval_ext` (v30_biu.sv:789). Frame: `law_ctr==0` at cycle T4+2, so
  cycle=T4+2+law_ctr; first due at `sel-2`, bounded retry to `sel` (T4+sel).
- Grants: `law_arm` suppresses the eval_ext prefetch grant (`selected_evalext_pf
  _grant`, :795); `law_window` suppresses the ti_plain grant (`selected_plain_pf
  _grant`, :796); `pick_law` carries `law_grant` (:774,802). Slot fires
  SLOT_LAW_RESUME at v30_biu.sv:963.
- Frame latch: `law_dcnt` = `cnt_next` latched at the T3 state cycle
  (v30_biu.sv:1964, "frame A").

**Counterexamples & falsifiers.** SVA1 (v30_biu.sv:2043): the slot fires ONLY
within `[sel-2, sel]` — a mistimed fire is a hard $error. SVA2/3 (:2027):
`law_due` never co-asserts with `eval_ext`/`q_flush`. SVA5/6 (:2031): window
lifetime ≤ sel (no immortal window). SVA-arm-domain (:2036): armed only at
occ 2..4. The census DONE-guard: unpaired CODE→CODE drifting off 190u±10 refutes.
The +1 sel-frame bug (sel-1 vs sel-2) is documented as the trap the Fix-A+B
template carried three times (:782-788) — a rebuild that reproduces the SLOT but
mis-frames the counter regresses ~150u.

**Discovery vs held-out corpus.** Fitted/ratified on the class5 causal_wrand
census seeds 90000-90019 (494u total; `class5_gaperr.py`/`class5_remap.py`
one-to-one matcher). Arm C (cidle-3 pin) measured on the directed N=8/N=12 sled.
Re-ratified on the authoritative matcher (§5 of the campaign record). midband_
pause DELETED as a proven strict-subset (656/656 firings covered on both corpora
— see LC8).

**Disposition: MUST-reproduce** (silicon-confirmed, covers the CODE→CODE bulk).
The rebuild expresses the resume slot as f(grid_phase, occ, fill_state,
completed-kind) per the Stage-3 design; the invariant cases above are the
acceptance set for E1 (`selected_prefetch_grant` hook).

---

## LC2 — Low-band pause

**Intervention performed.** At a WAITED resume with the queue starved (q_cnt≤2),
delay the prefetch while the occupancy has AGED in the 3-4 band — the Intel-8086
prefetch-band polarity. Kept when `midband_pause` was deleted (LC8) because it
owns a cell the unified law cannot express.

**Silicon-observed invariant I/O cases (MUST-reproduce).**
- At q_cnt≤2, a resume landing INSIDE the delay window (occ==4 aged 1-3 CE
  clocks, or occ==3 aged 1-2) is PAUSED by the chip; age-0 (band just entered by
  the completing fetch's own push) and aged-out GO. 0 false pauses held-out.
- Owns **11 real chip pauses** in the d_cnt==2 hysteresis cell that the unified
  law would lose, plus **10 non-CODE-successor rows** the law was never fitted on
  (campaign record §3 / v30_biu.sv:735-739).

**Fitted predicate as implemented (MAY-discard).** `lowband_pause` (v30_biu.sv
:743): `eval_ext && cur_fetch && q_cnt<=2 && ((occupied==4 && 1<=occ34_age<=3)
|| (occupied==3 && 1<=occ34_age<=2)) && q_aged==0 && !q_flush && !eu_hold`.
`occ34_age` (v30_biu.sv:443, :1345) = CE clocks the OCCUPIED count has sat
continuously in the 3-4 band. Vetoes `prefetch_ext` (:751).

**Counterexamples & falsifiers.** Ungated (without q_cnt≤2) it fires on mid-band
chip-GO cases — that is why it is scoped to the starved band (a wider gate
refutes). Any q_cnt≤2 occ-4 age-2 resume that is chip-GO refutes the window.

**Discovery vs held-out corpus.** `class5_bandage.py`, 0/169 held-out false
pauses; the 3-4 vs GO threshold sits in a wide age gap (PAUSE cases age≥5, GO
age 0 before hysteresis).

**Disposition: MUST-reproduce.** Small mass but silicon-real; the rebuild must
reproduce the d_cnt==2 hysteresis pause the resume law cannot.

---

## LC3 — Tw-parity H-PHASE RMW-write commit (tw_par / ext_ok_wr)

**Intervention performed.** The eval_ext deferred RMW-write commit is qualified
by `ext_ok_wr` ("ready ENTERING T4" = `eu_ready_p1 && eu_ready_p2`, fitted on the
UNIFORM sweep_rmw). That rule was too strict for one phase class random waits
generate. Added a local observable `tw_par` and widened `ext_ok_wr` so an
even-Tw-parity ready-AT-T4 RMW write takes the eval_ext DIRECT slot.

**Silicon-observed invariant I/O cases (MUST-reproduce).**
- For an RMW mem WRITE whose readiness asserts exactly AT the deferred prefetch's
  T4 (`eu_ready_p1 && !eu_ready_p2`): **even Tw-parity → chip commits EARLY (the
  eval_ext direct slot, T4+2); odd Tw-parity → chip commits LATE (plain staged
  T4+4)**. Board-confirmed **fabric==TB 15/15 even→early / odd→late** on silicon,
  per-cycle-random, T1-exact (`class5_campaign_record.md` §2/§3, class A′).
- The split is **write-scoped**: MEMR loads do NOT split on parity (they keep
  `ext_ok`). 30/30, 0 violations, both seed groups, random+uniform.
- Census effect: CODE→MEMW RMW cell 58u → 8u (−50u).

**Fitted predicate as implemented (MAY-discard).** `tw_par` (v30_biu.sv:651): a
flop cleared @ST_T1, toggled every ST_TW, sampled at the completion eval —
deliberately NOT `grid_phase` (stretched grid erases the displacement + carries a
post-wait carry) and NOT `ph_now` (forces T4→phase 1). `ext_ok_wr` (:660) =
`(eu_ready_p1 && eu_ready_p2) || (eu_ready_p1 && !eu_ready_p2 && !tw_par)`.
Consulted ONLY for `eu_defer_wr` (RMW writes) via `want_eu` (:662).

**Counterexamples & falsifiers.** Any even-parity ready-AT-T4 RMW that is
chip-LATE refutes (campaign record §1 class A′). Odd-tw rows STAY denied (stay
late) by construction — an odd-parity chip-EARLY refutes. Booked residuals (fresh
probes, NOT widens): CODE→MEMR loads (17u, interval-3, do NOT split on parity)
and 2 odd-parity-early edge rows the 4-vector probe subset didn't sample.

**Discovery vs held-out corpus.** `class5_hext.py`/`class5_codeeu.py`; fit(even
seeds)→FREEZE→score(odd), 30/30 both groups. **Gate of record: the RMW-touching
change MUST bring its own uniform-RMW fabric/chip capture** — no golden suite
carries RMW opcodes (campaign record §5).

**Disposition: MUST-reproduce** (the parity displacement, write-scoped). H-ARB
(LC5) and this are the two phase laws the rebuild's arbitration re-expression
(Stage E3) must reproduce (H-PHASE 15/15).

---

## LC4 — eu_req=0 reservation family (ratified untouchable)

**Intervention performed.** A family of eval_ext-window vetoes that stop a DOOMED
CODE prefetch from winning a slot the chip has already (or is about to) reserve
for an EU mem access, in cases where the model's `eu_req` lags the chip's
reservation. Five members: `pf_rsv_lead`, `pf_late_rsv`, `owns_slot`,
`pf_starved`, `eu_rsv_lead`. All eval_ext-gated → w0-neutral. **RATIFIED to STAY
(association ≠ harm; real-outcome-fitted); untouchable.**

**Silicon-observed invariant I/O cases (MUST-reproduce).**
- `pf_starved` / `prefetch_ext` override: when a deferred eval finds the queue
  EMPTY and the pending mem access is still only RESERVING (eu_req high, not
  ready), the chip PREFETCHES to refill BEFORE the EU access. Measured seed90008
  STM: chip fetches 0x51a then stores (v30_biu.sv:677-686).
- `pf_late_rsv`: a mem reservation that first asserts AT the eval (`eu_req &&
  !eu_req_p1`) is TOO LATE to claim that eval's slot — the chip commits a refill
  CODE prefetch and the string access takes the next slot. Measured on REP-string
  arb seeds 90020/90010/90017/90000/90012 (a4/a5/ab/ac/ad), q_cnt==1
  (v30_biu.sv:687-716).
- `owns_slot`: the CONVERSE — a coincident (age-0) reservation OWNS the slot (chip
  idles/reserves) for an ENUMERATED source set only: the S_DHI final-disp-pop
  read/RMW-read class (chip reserves at q_cnt==1) and S_PUSH_CALC push ONLY when
  q_cnt≥2. Every other reservation source keeps the baseline yield-to-CODE
  (v30_biu.sv:700-712).
- `pf_rsv_lead`: the chip's mem reservation LEADS the model's `eu_req` by one
  EU-state (disp16 store reserves at S_DHI, model eu_req rises at S_RSV); at the
  eval eu_req is still 0, so suppress the doomed prefetch. 7/7 class-1 cases
  (v30_biu.sv:717-728). Distinct from pf_late_rsv/owns_slot (those require
  eu_req==1).
- Store-vs-prefetch WRITE-half law generally: "the reservation must LEAD the
  request by one cycle" — a fresh prefetch (queue has room) must NOT win the T4
  slot when a store goes ready one cycle after a completing prefetch's eval
  (`biu_model.md` §"Store-vs-prefetch reservation law"; golden 169000/169000, 20
  PUSHA/RMW reorder seeds cycle-exact).

**Fitted predicate as implemented (MAY-discard).** See the wires above:
`pf_starved` :685, `owns_slot` :711, `pf_late_rsv` :713, `pf_rsv_lead` :727, all
folded into `prefetch_ext` (:747-751). `eu_rsv_lead` is an EU→BIU input
(v30_eu.sv, port at v30_biu.sv:145) driving `pf_rsv_lead`.

**Counterexamples & falsifiers.** The `owns_slot` carve-out is ENUMERATED (S_DHI
+ S_PUSH_CALC@q≥2) precisely because forcing ALL absent sources to reserve
over-blocks — a rebuild that makes reservation uniform across sources refutes on
the non-enumerated sources (S_RSV/S_MHI/S_JWAIT/S_DEC). `pf_late_rsv` is gated
`occupied<=4` so it never fires when the queue is full (the fitted single-store
forms sit at occ>4 with a LEADING reservation — both excluded).

**Discovery vs held-out corpus.** `eureq0_char` census (chip ground truth) +
Codex staged GO, session 019f663c; REP-string arb seeds; the WRITE-half law from
sweep_regea/PUSH sweeps + fz80200-81199/fz82000-82999 fuzz.

**Disposition: MUST-reproduce (ratified untouchable), WITH the carve-outs
flagged as carve-outs.** The rebuild keys arbitration on the reservation LEADING
the grid slot ("was the request up at this grid slot"); the enumerated
`owns_slot` source set and the eu_req-lead-by-one-EU-state gap are the specific
silicon facts it must honor, not the current CPU-cycle `_p1/_p2` pipelines.

---

## LC5 — H-ARB eu_ready arbitration (CHARACTERIZED — rekey NO-GO)

**Intervention performed.** NONE that survived. The prefetch-vs-EU arbitration
(queue-demand vs EU-readiness) was probed for a re-key; the arc closed **NO-GO**.
This card exists so the rebuild keys arbitration on `eu_ready` WITHOUT inheriting
a predicate that failed its own gates.

**Silicon-observed invariant I/O cases (the CHARACTERIZED finding — reproduce the
OUTCOMES, do not re-fit).**
- At a queue-split, the chip sometimes interleaves a CODE prefetch BETWEEN an EU
  mem read and a following RMW — an adjacent transposition of prefetch vs
  EU-RMW-read (k=15: chip fetches 0x57e between MEMR 0x2747 and RMW 0x2cfe; the
  fabric does the RMW first then the prefetch). This is a +N/−N PAIR
  (`t33_state.md` Probe 2).
- The paired/ordering mass is **±1-slot arbitration jitter at the observable
  floor**; H-SLIP (LC-family B in the floor table) — a resume delivered ±1-2
  slots early/late makes a +N/−N pair; ~129u paired.

**Why the rekey is NO-GO (falsifier record — MUST NOT re-attempt without a fresh
board probe).**
- Arbiter surgery (want_eu demotion): **hard KILL**. The paired mass is 88%
  prefetch-timing (want_eu=0), NOT want_eu>prefetch arbitration; no discriminator
  reaches ≥60% coverage with <2% false-flip (best 32%/58%) (campaign record §3c).
- mc1 rekey attempt: only 122u/544 want_eu-decided; swap sites had eu_ready=1 and
  the chip prefetched anyway; predicate coverage/false-flip failed both gates
  (`t33_state.md` Probe 2).

**Discovery vs held-out corpus.** k=15 soup wrand-w2 capture (chip-vs-board-
fabric); the class5 arbiter-rekey arc.

**Disposition: CHARACTERIZED, NOT a required law. rekey = NO-GO.** The rebuild
keys arbitration on `eu_ready` (split-half > eligible-EU > selected-prefetch
priority) but is **not bound to the current predicate**; the ±1-slot pair is
encoded as EXPECTED residual, not a target to close. Re-keying arbitration is a
STOP-and-report design decision, not a worker action.

---

## LC6 — Family-5/7 strio vetoes

**Intervention performed.** Two narrow strio-single (string I/O) reservation
vetoes hardened after the task-#29 vacuous-assert lesson: a T3-eval-scoped
prefetch veto and an idle-window arm, each backed by NON-VACUOUS coverage
counters (the F7a assert that mis-fired was downgraded to a counter).

**Silicon-observed invariant I/O cases (MUST-reproduce).**
- **Family-5** (`eu_rsv_strio`, v30_biu.sv:149): at the completion eval's
  successor-fetch grant, the strio-single uline-1 reservation is seen (the chip's
  decision instant is T4-entry ≥ pop+1), so `pick_t3` excludes prefetch:
  `pick_t3 = want_half2 || want_eu || (prefetch_ok && !eu_rsv_strio)`
  (v30_biu.sv:676). TI grants (chip decides pop-1/pop+0) are EXEMPT, so warm-1 /
  warm-2-prefix populations (chip-granted) survive. Only `req_t3_eval` + its
  dispatch use `pick_t3`; every other slot keeps `pick_any`.
- **Family-7** (`eu_soon_strio`, v30_biu.sv:116): the strio-single idle-window
  lead feeds the defer_idle path.
- Invariant guard: the three coverage counters MUST be NONZERO under the wrand
  strio-gadget fuzz (a zero counter = the veto never exercised = vacuous).

**Fitted predicate as implemented (MAY-discard).** `pick_t3` (:676); coverage
counters `cov_f7a_idle_arm`/`cov_f7a_eval_ext`/`cov_f5a_t3_veto`/`cov_f7a_coldarm`
(v30_biu.sv:1050-1053, under `ifdef VERILATOR` — sim-only, exempt from the flop
census). Codex trio-review coda (v30_biu.sv:1044).

**Counterexamples & falsifiers.** The F7a strio-domain assert ORIGINALLY fired on
a chip-correct state under waited/interrupt-shifted timing (task-#29
meta-finding): board arbitration proved the state chip-correct → the assert was
WRONG, downgraded to `cov_f7a_coldarm`. Falsifier: any counter reading 0 under
the strio-gadget fuzz (vacuous veto); or a warm-1/warm-2-prefix strio that the
T3 veto wrongly suppresses.

**Discovery vs held-out corpus.** Task #24 strio campaign; the wrand
strio-gadget fuzz corpus; Codex trio-review.

**Disposition: MUST-reproduce** (narrow, but silicon-real and already
non-vacuously guarded). The rebuild must preserve the T3-eval-scoped veto with
the TI-grant exemption and keep the counters live.

---

## LC7 — store_pf_boost / MEMW→CODE−1 (class-C irreducible ceiling ~30u)

**Intervention performed.** SHADOW ONLY. The mechanism (chip resumes the
post-store CODE prefetch one occupancy-level early, at occ==5) was board-confirmed
but the ENABLE was REVERTED — it broke the w1/w3 goldens. `store_pf_boost`,
`recent_evx`, `last_was_store` are computed and SSA-mapped but NOT wired into
`prefetch_ok`. Kept as a shadow for re-derivation.

**Silicon-observed invariant I/O cases (MUST-reproduce IF a new model-state
signal exposes the forecast; otherwise ACCEPT as residual).**
- After a MEMW store completes via the waited deferred completion, the chip
  resumes the post-store CODE prefetch at **occupied==5 (one idle clock SOONER)**
  rather than waiting for occ≤4. **28/28 unpaired MEMW→CODE rows at occ@T4+1 ∈
  {5,6} show ge=−1**, flat across the store's own Tw/pop/parity, both seed groups
  (disc 2/2, held 26/29, 7 seeds) (v30_biu.sv:464-475).
- Board-confirmed REAL: random 17/17, uniform 3/3, **w0-absent** (campaign record
  §1 class C).

**Why it is class-C irreducible-by-construction (the falsifier that closed it).**
The forecast probe KILLED the enable: **the chip commits BEFORE the only
distinguishing event (the off-3 pop)** — so the forecast is not locally
observable at the commit cycle. And the enable (`|| store_pf_boost`) passed w0
169000/169000 but broke w1/w3 (opcode 89 store 1200→1186/1181, PASV→CODE): the
−1 is wait-PATTERN-specific (chip resumes early under RANDOM waits but NOT under
uniform w1/w3) and `recent_evx` does not discriminate the two (v30_biu.sv:516-521).

**Fitted predicate as implemented (MAY-discard, SHADOW).** `store_pf_boost`
(v30_biu.sv:513): `last_was_store && recent_evx<=7 && state==ST_TI &&
occupied==5 && !(eu_req||eu_hold) && q_aged==0 && !q_flush`. `recent_evx` (:484)
saturates at 0xF (= w0, boost can never arm — verified 0/176358 w0 cycles).
`last_was_store` (:497) set at the store's T4, cleared at ST_T1.

**Counterexamples & falsifiers.** The w1/w3 golden IS the falsifier (recent_evx
over-fired → PASV→CODE regressions). Reopens ONLY if a NEW model-state signal
exposes the pre-commit forecast (campaign record §1 class C, §3c KILL).

**Discovery vs held-out corpus.** `class5_storeanchor.py`/`class5_remap.py`/
`class5_forecast.py`; disc/held split on 7 seeds.

**Disposition: MAY-discard the predicate; ACCEPT ~30u as the class-C
irreducible-by-construction ceiling** (in-principle floor). The rebuild keeps the
shadow; it reopens the cell ONLY if the grid model surfaces a NEW pre-commit
observable (e.g. beat_at_cross exposing the off-3 pop forecast). Not a
worker-closable cell.

---

## LC8 — mid-band + pf_drain (DELETED / subsumed — do NOT re-implement)

**This card exists so nobody re-implements two deleted mechanisms.** Both were
proven strict-subsets of surviving laws.

**pf_drain (DELETED).** Applied a tighter `pf_lim=3` in the post-waited-prefetch
window while the EU was consuming — a Stage-3-era fit of AGGREGATE drift made
before the class5 decision law existed. MEASURED on the corpus: over all waited
non-flush rows with pf_drain active (n=11,805) the chip GOes on 98.4%; where it
binds it is WRONG (legacy false-pause cell: chip GO on 68/68). Its 191
"legitimate" pauses are 169 already law-armed + 22 at occ≤3 where pf_lim=3 cannot
bind — **true-positive coverage 100% subsumed by the resume law, residue pure
harm**. w0-safe to delete (0 active cycles at w0). (v30_biu.sv:450-462; `pf_lim`
is now a constant `4'd4` at :463.)

**midband_pause / band34_age (DELETED, B2′).** The unified resume law (LC1) is a
verified STRICT SUPERSET — **656/656 firings covered, full-trace, both corpora**.
`band34_age` deleted with it. (v30_biu.sv:735-736.) NOTE: `lowband_pause` (LC2)
is a DIFFERENT law and is KEPT (owns the d_cnt==2 hysteresis + non-CODE-successor
rows the unified law cannot express).

**Disposition: DELETED — MUST NOT re-implement.** A rebuild that re-introduces a
pf_lim=3 drain or a separate mid-band pause duplicates the resume law and
re-adds pure harm. The invariant cases these targeted are already MUST-reproduce
under LC1 (mid-band) and LC2 (low-band).

---

## Summary table

| Card | Law | Invariant I/O cases | MUST / MAY |
|---|---|---|---|
| LC1 | Unified resume / demand-deadline | 4 (resume slot f(occ,fill,phase,Tw); cidle-3 high-N pin; 190±10 guard; ≤2-valued phase flip) | **MUST** (predicate MAY-discard) |
| LC2 | Low-band pause | 2 (occ4 age1-3 / occ3 age1-2 pause @q≤2; 11 d_cnt==2 + 10 non-CODE rows) | **MUST** |
| LC3 | Tw-parity H-PHASE RMW-write | 3 (even→early/odd→late 15/15; write-scoped; −50u) | **MUST** |
| LC4 | eu_req=0 reservation family | 5 (pf_starved refill; pf_late_rsv; owns_slot enum; pf_rsv_lead 7/7; WRITE-half lead) | **MUST** (untouchable; carve-outs noted) |
| LC5 | H-ARB eu_ready arbitration | 2 (queue-split interleave pair; ±1-slot floor) | **CHARACTERIZED** (rekey NO-GO) |
| LC6 | Family-5/7 strio vetoes | 3 (F5 T3-veto w/ TI exemption; F7 idle arm; counters NONZERO) | **MUST** |
| LC7 | store_pf_boost / MEMW→CODE−1 | 2 (occ==5 resume −1, 28/28; class-C not locally observable) | **MAY-discard** (~30u class-C ceiling; shadow) |
| LC8 | mid-band + pf_drain | 0 (DELETED; subsumed by LC1/LC2) | **DELETED** (do not re-implement) |

**MUST / MAY split:** LC1, LC2, LC3, LC4, LC6 are MUST-reproduce (their
silicon-invariant I/O cases are the E1-E3 acceptance sets). LC5 is CHARACTERIZED
(reproduce the ±1-slot outcome as residual; rekey is a STOP verdict). LC7 is a
MAY-discard predicate + a class-C ~30u accepted ceiling. LC8 is DELETED.
Invariant-case count: 21 MUST cases across LC1/2/3/4/6; 2 characterized (LC5);
2 class-C (LC7).
