# Bring-up log

## 2026-07-16 — CLASS-5 MID-BAND fix landed (8086 insight; -10% class-5 mass)

The 8086 prefetch-band rule (Ken Shirriff, righto.com: queue 0-2 -> fetch; 3-4 ->
DELAY 2 clocks; 5-6 -> blocked) REOPENED class-5. Band-age replay
(sw/class5_bandage.py over the full CODE->CODE opportunity population) found the
class-5 mid-band 50/50 boundary we had called "irreducible" was TIMER-STATE
ALIASING: for q_cnt in the 3-4 band, band-age (CE clocks continuously in 3-4)
separates chip GO (age 0) from chip PAUSE (age>=5) - 0/169 held-out. So the
earlier "observable floor" conclusion was WRONG for the mid-band (right for the
low-band). w0-GO and waited-PAUSE overlap at the SAME band-age (both age>=5 at
w0 too), so the delay is WAIT-DEPENDENT, not a unified queue policy; and the pause
applies only at the CODE-fetch-completion resume edge (eval_ext && cur_fetch) -
the global and broad-eval_ext forms shattered w1/w3.

Fix (commit d378fe6): band34_age counter; midband_pause = eval_ext && cur_fetch &&
q_cnt in {3,4} && band34_age>=2 && q_aged==0 && !q_flush && !eu_hold; ANDed into
prefetch_ext (same shape as the eu_req=0 pf_rsv_lead). w0-NEUTRAL by the eval_ext
gate. Validation: w0 169000, w1/w3 1200 (bit+cycle exact); random-wait gap-error
census (18 seeds) |mass| 557->501 (-10%), net +267->+233, +3 impulses 67->52, NO
new negative tail (both positive and negative mass down; -4/-5 tail shrank). The
FIRST clean class-5 mass reduction (cf. pf_lim=2 -> -291 blowup, Phase S NO-GO).
RESIDUAL: the low-band (q_cnt 0-2) EU-drain pauses (all eu_consuming=1) remain a
separate mechanism at the observable floor - needs Codex's controlled band-ladder
(tests B/E), not the mid-band timer. Threshold is >=2 (the dump gap is age 1-4,
GO at 0 / PAUSE at >=5, so 2..5 are equivalent on the measured data).

## 2026-07-15 — PHASE R: eval_ext/do_commit PATH UNIFICATION landed (behavior-preserving)

Implemented Phase R of the commit-path unification (docs/notes/class5_path_unification_plan.md,
Codex-planned; opus sub-agent executed). The BIU's two commit paths (direct-entry
eval_ext/ff/defer vs staged do_commit) are now canonicalized into ONE slot decision
slot_fire/slot_id/slot_mode/slot_desc; direct-vs-staged is delivery metadata only.
11 stages R1-R7 (commits 2dc1228..be667df on biu-arb-qcnt), one commit each, gated
after every step. BEHAVIOR-PRESERVING - proven:
- w0 169000/169000, w1 1200/1200, w3 1200/1200 bit+cycle exact at every stage
  (independently re-verified at HEAD be667df).
- class-5 control traces fz90007/fz90011 BYTE-IDENTICAL to the R0 baseline at every
  stage (board-free run_tb_internal, uniform wv).
- Extra: --assert binaries built at R5/R6c/R7, full suites + a class-5/flush/interrupt
  spread run with ZERO assertion failures (shadow arbiter == every real branch;
  slot_show_now == ext_show byte-for-byte before switching the display driver).
- R7 handled a Verilator UNOPTFLAT false loop (packed slot_desc pulled pick_wdata<-ad_i
  into the display cone): slot_desc moved to a continuous assign; slot_fire/slot_mode
  depend only on ad_i-independent req_*; QS=E/HALT/INTA rules untouched.
Phase-S HOOK in place (v30_biu.sv:696-698): selected_prefetch_grant =
slot_is_eval_ext ? prefetch_ext : prefetch_ok (declared, inert - Codex noted it is
not yet CONSUMED; S0 would wire it, but see NO-GO below).

PHASE S = NO-GO (opportunity audit, sw/class5_pauseaudit.py, Codex-designed gate).
Codex's Phase-S plan (docs/notes/class5_phase_s_plan.md) was a partial PAUSE-ONLY
veto of the eval_ext resume, gated by a ZERO-FALSE-PAUSE predicate from an
opportunity audit (S3 only if >=10% zero-FP coverage on held-out+fresh). The audit
(discovery/held-out/fresh corpora, uniform+random waits) is DECISIVE: at the q_cnt=2
boundary the model-GO population is overwhelmingly CORRECT (disc 525/540, held
400/419, fresh 337/340 chip-GO); only ~3-5% are chip-PAUSE (the fixable +errors:
15/19/3). Grid search over cad/dage/popc found NO zero-false-pause predicate at the
>=10% bar - the best is 5% AND has a false pause on discovery. The fixable chip-PAUSE
cases are INSEPARABLE from the correct chip-GO cases in predicate space, so any veto
injects ~as many -impulses as it fixes (the pf_lim=2 lesson, now proven at the
boundary). The audit GATE did its job - it prevented an over-correction. CONCLUSION:
class-5's ~15% boundary residual is genuinely IRREDUCIBLE on chip-observable +
model-internal state (it needs the chip's internal fetch-scheduler micro-state,
unobservable from bus+QS past the divergence). The class-5 random-wait residual is
at its OBSERVABLE FLOOR. Phase R (the structural unification) stands as the durable
win; Phase S is closed NO-GO. The eu_req=0 store+MOFFS fixes remain the
silicon-confirmed cycle-accuracy improvements.

## 2026-07-15 — CLASS-5 pivot: prefetch-resume idle-cadence localized (gap-error census)

With store + MOFFS eu_req=0 landed, the whole random-wait residual is class-5
"same bus decisions, WRONG CLOCK" (80% fitting / 90% held-out). Built the signed
inter-T1 gap-error census (sw/class5_gaperr.py, commit 2283046, Codex instrument):
gap_error[i] = (chip_T1[i]-chip_T1[i-1]) - (model_T1[i]-model_T1[i-1]) over the
aligned prefix of every vector, w0 (wmax=0) included as zero-error controls.

Result (18 seeds x 6 ws x wmaxes{0,1,3,7}, 76,000 aligned intervals):
- w0 control: 19,308 intervals, 0 nonzero -> instrument sound, w0 bit-exact.
- 99.6% clock-exact. The 0.4% errors (~213 impulses) are ENTIRELY idle-count:
  gap_error == Ti_delta exactly (not wait counts, not T-state length - purely the
  number of idle Ti cycles inserted between consecutive bus cycles).
- 202/213 impulses are CODE->CODE => a PREFETCH-RESUME cadence defect (the model
  inserts the wrong number of idle cycles before the next prefetch T1). Small
  EU-adjacent set (CODE->MEMW, MEMW->CODE, CODE->IOW).
- prev_tw LAW: after a heavily-waited fetch (prev_tw=6,7) the error is
  systematically POSITIVE (+2:42/+3:12 at tw7; +2:17 at tw6) - model resumes
  2-3 clocks too TIGHT (too early). After light waits (prev_tw=1) it is
  BIDIRECTIONAL (+3:32 and -3:16). net=+267 vs |mass|=557 => ~half the impulses
  cancel (why class5tax first-divergence over-attributed).

Mechanism (working): the model's prefetch resume (occ<=pf_lim + pf_drain
threshold) does not capture the chip's resume delay, which scales with the
predecessor fetch's STRETCHED-GRID geometry (wait count) + queue occupancy/
consumption. This is the long-suspected "prefetch-resume law under waits"
(instantaneous EU state proven insufficient; needs accumulated bus-grid-vs-
consumption phase history).

DENOMINATOR census (12 seeds, sw/class5_gaperr.py --denominators): prev_tw=0 is
PERFECTLY clean (0/24,570) - the resume defect ONLY follows a waited fetch
(necessary). But error rate is only 0.5-1.3% (not sufficient - extra state selects
which waited refills err). Sign structured by wait duration: prev_tw=7 all +ve
(+42/-0), prev_tw=1,2 bidirectional. => cannot blanket-correct; need the
discriminator.

FACTOR-W experiment (sw/class5_factorW.py): at a fixed CODE->CODE anchor, sweep
ONLY the predecessor's wait N via WVEC, measure chip vs model resume_idle. ABSORB-
TO-FLOOR DEADLINE LAW (Codex-formalized, exact for anchor A fz90011):
    gap(N)  = max(D, 4+N+F);  resume_idle(N) = max(D-(4+N), F);  D=12, F=4.
The chip has a scheduled earliest successor-T1 DEADLINE (D); predecessor Tw
consumes the slack before it; once the min post-T4 separation (floor F~3-4) is
hit, extra waits move the successor. anchor A chip_gap CONSTANT 12 for N=0..4
(smoking gun). The model's occupancy resume only ACCIDENTALLY coincides (A N=0..4)
and glitches (A N=5 late, N=6 early = threshold/commit-path aliasing). Anchors B/C
(fz90007/90002) do NOT fit a single (D,F) - deadline+floor are CONTEXT-DEPENDENT,
so "fixed bus-grid slot" is one hypothesis, not proven.

Implementation shape (Codex): a TARGETED resume-slot scheduler (separate
prefetch_eligible from prefetch_resume_slot), choosing among eval_ext / next-idle
/ later-refill slot - must handle BOTH early and late (one-direction delay
inadequate). Do NOT consume grid_phase yet (documented post-wait carry divergence,
inert for good reason).

FACTOR-P (anchor cycle-traces, sw/class5_anchortrace.py): the matched-pop image
construction is UNNECESSARY - the N-sweep already answers the bus-grid-vs-
consumption question. At anchors A (fz90011) and B (fz90007), across N, chip
successor_T1 = predecessor_T4 + 5 (const), INVARIANT to the post-T4 consumption
pop placement (pops at T4+2, or T4+0/+3, or T4+1/+4; successor unmoved). Measuring
relative to T4 factors out the grid shift N introduces, leaving pop placement as
the varying factor which the chip ignores => the resume is BUS-COMPLETION (T4)
anchored, not consumption-anchored. The model instead resumes at the eval_ext
(T4+1) once occ<=pf_lim (more waits -> more consumption during Tw -> lower occ ->
early resume; collapse-to-1). Codex confirmed: skip matched-pop; T4-relative
turnaround is real at these anchors.

CODEX RULING - the fix is NOT a blanket post-waited-fetch counter (Gate-A
falsified it: 17,052 waited CODE->CODE opportunities, chip prefetched IMMEDIATELY
in 16,952 = 99.4%, class-5 idle in only 100 = 0.6%; a 1-cycle block shattered
w1/w3). "Waited CODE fetch" is NOT the arming discriminator, and no blocking
counter fixes both signs (anchor A N=5 needs the model to launch EARLIER). Law
shape: successor_T1 = max(deadline, pred_T4 + Lmin), Lmin = resume_idle_floor + 1.
TWO pieces remain before any RTL:
  (1) Lmin as a collision-free function of FETCH GEOMETRY (Lmin=5 anchor A / =4
      B,C; leading candidate = even/odd physical fetch parity - A succ fetch ODD
      6fee7, B EVEN 69090). Measure a geometry matrix (even/odd pred x even/odd
      succ), sweep N to saturation, extract Lmin per cell.
  (2) The resume/DEADLINE ARMING EVENT that separates the 0.6% delayed cells from
      the 99.4% immediate-CODE controls (retrospective: deadline_candidate =
      successor_T1 when L>Lmin; compare vs last-pop-before-pred-T1, occupancy-
      cross-refill, pred_T1, prior-CODE-T1, queue-push-completion; the
      invariant-offset event is D's physical source). An opportunity census must
      prove the arming event isolates the rare cells (else another Gate-A fit).
Minimal RTL (once 1+2 known): resume_pending / resume_deadline / turnaround_ready
/ higher_priority_clear; commit CODE when all met; UNIFY eval_ext + do_commit into
one slot-selection + common commit (eval_ext = one candidate slot, not a separate
policy - the discontinuity plausibly causes the +/-2/3 glitches). w0-neutral via a
waited-only token (set only when completed cycle is CODE AND saw >=1 Tw; clear on
successor commit / any EU bus commit / flush / discard / reset; bit-identical when
inactive). Codex thread 019f663c consulted at each step.

PIECE 1 (Lmin) MEASURED (sw/class5_lmin.py, 18 anchors): Lmin (resume floor) =
5 if q_cnt(pred_T4)>=3 else 4, for linear even->even resumes (parity REFUTED - my
earlier odd/even claim was a misread of the data-phase bus column; all linear
resumes are even->even; the 2 Lmin=1 anchors are ODD-successor BRANCH REDIRECTS =
separate immediate-fetch machinery, exclude structurally not by parity). CAVEAT
(Codex): the split is CONFOUNDED - the 3 q_cnt=3 anchors are EXACTLY the
non-consuming ones (pred_state S_WAITX/S_FIRST), so q_cnt vs consumption vs
deadline-still-active are entangled; q_cnt=3 is not queue-full (cap 6). q_cnt(T4)
is a DEMAND signal (pre-existing bytes; the waited fetch's own push is deferred
past T4), not a turnaround signal. Do NOT encode q_cnt>=3?5:4 until Factor-Q.

PIECE 2 = FACTOR-Q (the single decisive experiment, Codex): a CONTROLLED,
BIDIRECTIONAL q_cnt(T4) boundary intervention (2<->3) via UPSTREAM WVEC
perturbation, holding fixed the predecessor/successor addresses, predecessor N,
fetch width, sequential/non-flush status, T1/T4 phase, EU req/hold, and local bus
stream. Drive a DELAYED anchor 3->2 (expect L=5->immediate/4) and an IMMEDIATE
control 2->3 (expect L=4->delayed/5), at two N (below-knee + saturated). If the
delay/immediate outcome FOLLOWS the controlled boundary AND one event->successor
offset predicts both -> queue-DEMAND-deadline law confirmed. If identical
reconstructed q_cnt(T4) still yields both outcomes -> history-latched (test
last-pop / threshold-crossing CLOCK, not snapshot fields). Record candidate
deadline events (last QS pop before pred T1/T4; queue-count 4->3/3->2/2->1
transitions; occupied<=4 / <=3 first-true; prior seq CODE T1/T4; pred T1;
pred push clock; first post-T4 q_avl increase; first post-T4 legal no-EU/no-flush
slot; successor T1) and find the invariant offset = D's physical source. The
all-opportunity census is the VALIDATION gate AFTER Factor-Q proposes the law
(census shows separation but cannot establish causality). Gate-A warning: coarse
occupancy at the DECISION edge was NOT collision-free (occ2/consuming gave both
11,488 immediate + 48 delayed); the new candidate uses q_cnt at pred T4 (earlier
edge) - must be tested across the whole population. RTL = LATCHED refill-request/
deadline (not a lower pf_lim - residual is bidirectional, anchor A N=5 needs an
EARLIER launch). Codex thread 019f663c consulted at each step.

FACTOR-Q RESULT (sw/class5_factorQ.py): the resume timing IS governed by
q_cnt(pred_T4) - the queue-demand-deadline hypothesis is causally supported. At a
fixed anchor (N + pred/succ addrs held; predecessor re-located by address each
run), driving q_cnt(pred_T4) via upstream WVEC perturbation moves L monotonically:
fz90013 q0->L2, q1->L4, q3->L5 (fz90011 corroborates q3->L5 stable). DE-CONFOUNDED
within the data: two far-upstream perturbations (acc#100 w0 vs w1) FLIP the pred-T4
grid parity yet both keep q_cnt=1 and both give L=4 -> at fixed q_cnt, grid parity
does NOT change L. So L=f(queue fill at completion), not parity or consumption.
(Near-anchor perturbations confound the deadline: q4->L7-10 decreasing - excluded.)
REMAINING before RTL: (a) map the full L(q_cnt) function (fill q2, q4 - so far
q0->2, q1->4, q3->5, monotonic but not linear); (b) the D deadline-source
retrospective for the absorb regime (which pre-T1 event D is anchored to); (c)
then the latched-deadline RTL + full validation gate.

BIDIRECTIONAL MECHANISM (instrumented traces, sw/class5_anchortrace.py): the
resume is a FIXED T4-relative SLOT, not an occupancy threshold - proven in BOTH
directions. +case fz90007 N=3: model prefetches at eval_ext occ=3<=pf_lim=3, chip
IDLES (chip threshold lower). -case fz90011 N=5: chip prefetches at occ=4, model
waits for occ<=3 then loses a clock to the do_commit path -> model LATE (chip
threshold higher). occ at eval_ext already includes the deferred push (cnt_next),
which is the misleading value. So occ<=pf_lim is wrong in both signs; the
eval_ext-vs-do_commit split adds +/-1 jitter.

RTL DESIGN (Codex-specified, session 019f663c): law =
  successor_T1 = max(prefetch_due_slot, pred_T4 + turnaround_floor)
The chip SEPARATES demand-detection (a queue-demand event LATCHES a pending refill
+ deadline slot) from the commit CLOCK; the model conflates both into
occupied<=pf_lim. Do NOT implement a q_cnt-only T4 countdown: the q0->{L2,L4}
collision proves a second state (DEMAND-AGE: how long ago the queue reached demand
/ emptied) remains. Latch the PRE-PUSH q_cnt at pred T4 (registered value before
the deferred push - NOT cnt_next/occupied/q_avl). Minimal RTL = a small
waited-resume scheduler: state {pf_demand_pending, pf_demand_age/deadline,
waited_resume, resume_pre_qcnt, turnaround_left}; demand tracking runs continuously
(inert at w0); at the waited sequential CODE T4 set waited_resume + latch
pre-push q_cnt + turnaround floor; resume_commit = waited_resume &&
pf_demand_pending && demand_deadline_reached && turnaround_reached && !eu_owner &&
!eu_hold && !q_flush && !fetch_discard && !split_continuation. BOTH the eval_ext
and plain-idle commit sites consume this ONE unified policy result (must SUPPRESS
prefetch_ext when early AND PERMIT commit when occ<=pf_lim is false when late - a
gate that only ANDs into prefetch_ok cannot fix fz90011). w0-neutral via explicit
mux: if(!waited_resume) legacy bit-identical else scheduler; waited_resume sets
only when the completed cycle is CODE + sequential + saw >=1 Tw; clears on
successor commit / any EU bus commit / flush / redirect / discard / reset.
STREAM-CADENCE (sw/class5_streamcadence.py, 1929 CODE->CODE resumes uniform w1-3):
the capacity model - chip fetches BACK-TO-BACK while occ<=4 (q_cnt<=2), PAUSES at
occ>=5 (q_cnt>=3) = exactly the model pf_lim=4, so the model is RIGHT for the bulk.
The class-5 disagreement CONCENTRATES at q_cnt=2 (14/55=25%), boundary discriminator
= eu_consuming/pop_cnt (consuming -> pause). BUT the tractable fixes are RULED OUT:
(1) pf_lim 3->2 in the drain+consuming window: w0/w1/w3 goldens all held, but the
random-wait gap-error census OVER-CORRECTED - 485 impulses (up from ~226), flipped
to negative (CODE->CODE +161/-291), prev_tw=1 err 0.87%->3.48%. Bidirectional
confirmed AGAIN (not a threshold). (2) DECISION-EDGE discriminator: within the
pf_lim=3 boundary the chip go-vs-pause is 23/22 = ~50/50 on EVERY observable
(decision-edge occ/q_avl/q_cnt/pop_now/push_now/recent-pop). => a chip-INTERNAL
fetch-scheduler state (or exact microtiming the model cannot reconstruct past the
divergence point) governs the final decision. THE WALL: class-5's fine structure
needs the chip's demand/deadline state reconstructed PURELY from chip-observable
history (bus + QS F/S pops + fetch widths), INDEPENDENT of the diverged model
(Codex's suggested reconstruction) - a substantial new tool, the principled next
effort. Model-internal discrimination is exhausted (the model==chip only up to the
divergence, which is exactly where the decision differs).
  CORRECTION (the "wall" was premature): the model==chip UP TO the divergence, and
the resume decision IS the divergence, so the state AT/BEFORE the decision is
chip-accurate - the instantaneous 50/50 means a HISTORY variable governs (the
latched demand slot, exactly as Codex said). Adding history variables to
streamcadence resolves the q_cnt=2 boundary FAR better: fetch-cadence MOMENTUM.
cad = clocks between the two prior fetches: cad<=9 (tight/back-to-back burst) ->
GO ~79%; cad>=16 (slow/paused) -> PAUSE ~85%. demand-age agrees: recent demand
(dage 5-13) -> go; old (dage 29+) -> pause. So the chip has PREFETCH MOMENTUM -
it continues a fill burst once started and stays paused once saturated; the q_cnt=2
boundary decision follows the recent cadence, NOT instantaneous occupancy. The
model (occ<=pf_lim, memoryless) lacks this hysteresis. FIX DIRECTION: add
cadence-momentum hysteresis to the boundary prefetch decision (continue if recently
bursting, pause if recently paused), w0-neutral. Still ~80% clean, not yet
bit-exact - needs a cleaner momentum rule (pin the exact cad/dage thresholds +
any second variable) before a bit-exact RTL. This is the tractable next effort,
NOT a wall.

FLOOR-ONLY RTL ATTEMPT (reverted) - a decisive negative result: implemented the
suppression-half scheduler (arm wr_active at the waited-completion !evald T4, latch
wr_L from the surface floor arithmetic q_cnt>=2?5:q_cnt==1?4:age<=3?4:2, and
wr_block = wr_active && wr_ctr+1<wr_L gating prefetch_ok until the slot). w0 held
169000/169000 (w0-neutral confirmed - arms only in !evald), BUT w1/w3 goldens
SHATTERED (347/1200, 350/1200; failures = CODE got PASV = suppressed prefetches
that should happen). ROOT CAUSE: in uniform-wait streams EVERY fetch is waited so
the scheduler is always active and imposes the floor idle even while the queue is
still FILLING toward capacity - but there the chip prefetches BACK-TO-BACK. The
floor arithmetic was measured with an ISOLATED saturated-N predecessor (queue in a
paused/saturated state); it does NOT capture the FILLING-vs-SATURATED distinction
that governs stream cadence. This empirically CONFIRMS Codex's warning: a
q_cnt-only floor countdown is insufficient; the resume timing needs the full
demand/CAPACITY model (prefetch back-to-back while filling toward cap 6; pause per
the demand deadline only when saturated/well-fed). The floor L is the PAUSED-state
slot, not the fill-cadence. REMAINING: measure the resume cadence in STREAM context
(when the chip prefetches back-to-back vs pauses = the demand_slot/capacity rule),
NOT with isolated anchors; then the RTL must gate the slot-idle on the
saturated/well-fed condition (not merely "waited fetch").

NEXT DECISIVE MEASUREMENT (Codex): the fixed-q0 STARVATION-AGE experiment - hold
q_cnt(T4)=0/q_avl=0/geometry fixed, vary only empty_age = pred_T4 - clock(queue
1->0), targets empty_age 0/1,2,3+. If L follows empty_age (newly empty -> L4
scheduled later; long empty -> overdue -> L2 immediate) the deadline event is the
queue-empty transition -> RTL needs a demand-age/slot latch. Then sweep the same
demand-age rule through q1-q4 (may eliminate the L table entirely). More decisive
than filling q2/q4 (a lookup table is meaningless while q0 collides).

## 2026-07-15 — eu_req=0 MOFFS stage: PARITY-GATED S_MLO lead-veto (SILICON-CONFIRMED)

Second stage of the eu_req=0 look-ahead veto (commit 981f3af, bitstream flashed;
setup slack +5.686 ns, hold +0.248 ns). Unlike the disp16 store (a clean blanket
reserve), the MOFFS load is PARITY/WIDTH-DEPENDENT - a genuine bus-grid finding
caught by running the opportunity census BEFORE the RTL (the Gate-A discipline).

Opportunity census (moffs_optcensus.py, chip ground truth, 20 aligned
eval_ext+S_MLO+q_pop cells):
  A1 word load, EVEN addr (aligned, 1 bus cycle): chip PREFETCHES 12/12
  A1 word load, ODD addr  (split,  2 bus cycles): chip RESERVES   4/4
  A0 byte load:                                    chip RESERVES   4/4
The chip reserves at S_MLO for a MOFFS load EXCEPT an ALIGNED WORD load (an
aligned single-cycle read leaves grid room to prefetch; a byte or split read
does not). A blanket S_MLO veto would have wrongly suppressed 12 legal chip
prefetches. Discriminator computable at S_MLO: addr LSB = q_byte[0] (low byte
popping), width = opc[0]; aligned word = opc[0] && !q_byte[0]; veto =
!(aligned word). eu_rsv_lead += (S_MLO && op_moff && q_pop && (!opc[0] ||
q_byte[0])). op_moffw stores (A2/A3) excluded (negative control). Same eval_ext
pf_rsv_lead mechanism -> w0-NEUTRAL.

Validation (chip ground truth):
  w0 169000/169000, w1 1200/1200, w3 1200/1200 (bit+cycle exact).
  eu_req=0 census: MOFFS cases eliminated, 6->4 class-1 (only POP r16 remains).
  fitting census N=300: class-1 42->36 mass; NO over-suppression, NO new class.
  held-out census N=300: IDENTICAL to pre-MOFFS (class-1=0, no under-prefetch) -
    the parity gate did NOT break the aligned-word prefetches.
  SILICON (fabric use_core=1 vs chip use_core=0): fz90063 MOFFS over cases now
    chip==fabric==TB (doomed prefetch gone). fabric==TB on all 7 vectors; the 2
    held-out diffs are byte-identical to the store-flash run (pre-existing
    class-6/7; ZERO new fabric divergence from MOFFS).

eu_req=0 residual now: 4 POP r16 cases (DEFERRED - S_FIRST needs live q_byte
decode). Whole random-wait residual now DOMINATED by class-5 WRONG-CLOCK (80%
fitting / 90% held-out) - the campaign PIVOTS there next (structural bus-slot
scheduling, NOT another eval_ext veto - Codex).

## 2026-07-15 — eu_req=0 STORE stage: wait-dependent BIU look-ahead veto (SILICON-CONFIRMED)

Landed + flashed + silicon-confirmed the first stage of the eu_req=0 onset fix
(commit f145345, bitstream checksum 0x03D40ED0 live in fabric). This corrects a
class of random-wait over-prefetch where the model committed a DOOMED CODE
prefetch one EU-state before its own eu_req rose, while the chip had already
reserved the bus for an imminent store.

KEY DISCOVERY (overturns a prior w0 assumption): the reservation onset is NOT a
fixed EU-state that can be shifted earlier. The first implementation asserted
eu_req at S_DHI unconditionally and REGRESSED the w0 golden 168854/169000, every
failing cell a disp16 store showing exp CODE/T1 at the post-EA cycle. The chip
DOES prefetch at that cycle at w0 (golden = chip ground truth). The correct model
(Codex framing): the BIU has a WAITED-completion (eval_ext) look-ahead veto that
recognizes an imminent store one EU-state before ordinary eu_req; the SAME EU
state does not suppress a legal w0 prefetch. "May use this slot now" (w0
prefetch_ok) vs "must preserve the next grid slot for an imminent access"
(eval_ext). eval_ext is a model proxy for that hardware grid opportunity,
validated for the measured cells (not proven the chip's mechanism).

Implementation: EU exports eu_rsv_lead = (S_DHI && (op_movs8|op_movs16) &&
q_pop); BIU pf_rsv_lead = eval_ext && eu_rsv_lead && q_aged==0 && !q_flush &&
!eu_hold, ANDed as `!pf_rsv_lead` into prefetch_ext. w0-NEUTRAL by construction
(eval_ext never fires at w0). Distinct from pf_late_rsv/owns_slot (those require
eu_req==1; here the reservation LEADS with eu_req==0).

Validation (all chip ground truth):
- Golden chip-vs-TB: w0 **169000/169000**, w1 **1200/1200**, w3 **1200/1200**
  (bit+cycle exact; the -146 w0 regression was the REJECTED unconditional edit).
- eu_req=0 census (board): store case fz90015 ELIMINATED, 7->6 class-1.
- Fitting census N=300: no new divergence, no over-suppression, no new class.
- Held-out census N=300 (91000-91009): class-1=0, no over-suppression.
- **SILICON (fabric use_core=1 vs socketed chip use_core=0)**: fz90015 bus 37
  now MEMW@02608 on chip==fabric==TB (doomed CODE gone; exact idle count/index).
  fabric==TB on all 5 acceptance vectors (faithful synthesis). Setup slack
  +4.795 ns, hold +0.246 ns. The 2 held-out chip-vs-fabric diffs (fz91000 b130
  CODE/CODE addr±1; fz91003 b136 IOW) are PRE-EXISTING class-6/7 residuals, not
  this fix (fabric==TB on both).

Residual now dominated by class-5 "same bus decisions, WRONG CLOCK" (78% fitting,
90% held-out). NEXT: MOFFS stage (S_MLO lead-veto, same mechanism, needs its own
opportunity census); then PIVOT to class-5 as structural bus-slot scheduling (NOT
another eval_ext veto). Codex thread 019f663c consulted (staged GO, this framing).

## 2026-07-15 — MERGE biu-rebuild -> master (BIU rebuild banked to mainline)

The BIU bus-model rebuild campaign merged to master (fast-forward; master was at
the Phase-1 doc commit, biu-rebuild 26 ahead). Rollback tag `biu-rebuild-baseline`
(c0c28f1) retained. Comprehensive pre-merge validation, ALL clean vs baselines:

- **Full golden (chip-vs-TB / check_core)**: w0 **169000/169000**, w1 **1200/1200**,
  w3 **1200/1200** (all 6 forms). NOTE: w1/w3 now report the FULL 1200 (not the
  historically-cited 800/600) because a pre-existing over-strict Stage-1
  grid_phase SVA was `$stop`-aborting the 8B/89/B8 load/MOV-imm forms' sim under
  waits and check_core silently skipped them (masked by prior tail/grep-TOTAL
  reporting). grid_phase is INERT (unconsumed - EU uses bus_phase), so ZERO
  behavioral impact; the strict SVA is now gated behind `GRID_PHASE_STRICT`
  (off) with the abort removed, so those forms VALIDATE cycle-exact. Confirmed
  pre-existing at 01c31e7.
- **waits=0 arbitrary-sequence fuzz** fz20000-20299 chip-vs-TB: **300/300 clean**
  (store/push/reader/callret surface unregressed by the whole rebuild).
- **Interrupt inject gate** fz10000-10499 --inject-int chip-vs-TB: **497/500**.
  The 3 residuals (fz10209/10300/10304) are the DOCUMENTED doomed-prefetch/
  accept-edge interrupt-vectoring class (chip does a doomed CODE prefetch before
  INTA the RTL doesn't model - same class as the deferred fz10175/10460). They
  DIVERGE IDENTICALLY at 01c31e7 (@251/@264/@202), and the session's four fronts
  are w0-neutral (all eval_ext-gated; inject runs at w0 where eval_ext never
  fires) -> the inject gate is bit-identical HEAD-vs-baseline. NOT a regression;
  the 497-vs-documented-498 is gen_seq/corpus evolution surfacing the same class
  on different seeds. Sub-1%, out of scope (deferred interrupt-timing floor).
- **Silicon A/B (this session, bitstream 0f383e0 live in fabric)**: w0 crown
  jewel chip/core/golden MATCH 800 rows; w1/w3 fabric-vs-chip == chip-vs-TB
  EXACTLY per-seed 15/15 both, float-floor 15/15 clean; BUSLOCK exact;
  inject-int fz10000-10049 50/50. The arb/Jcc-flush/far-flush fronts are real
  in fabric.
- **Adjudication ledger**: 0 w0 deltas; every landed front w0-neutral by
  construction (all eval_ext-gated -> inert at w0).

FABRIC == MASTER: the SVA-gating + eudbg-dump + tooling changes are entirely
TB-only / `ifndef SYNTHESIS`; the SYNTHESIZABLE RTL at master HEAD is
bit-identical to the flashed bitstream 0f383e0 (no reflash needed - current best
RTL is already in silicon). Session drift result (silicon-confirmed): w1
459.3->307.3 (-33%, CLEAN 4->18), w3 583.6->475.6 (-18%, CLEAN 15->21) via three
landed fronts (late-reservation arb / near-flush +1 redirect / far-flush
eval_ext E-display); the RESUME third characterized as the irreducible local
floor. Next campaign: the exact-grid-state resume scheduler
(resume_scheduler_design.md; exact-state predictor go/no-go = qualified
greenlight, w0 100% control + w1/w3 big-gap 83-98% on the clean prefix).

## 2026-07-14 — reflash: WAITS>=1 grind round 2 (far-CALL + RMW-narrow)

- SCOPE: two waits>=1 fixes since the prior reflash - far CALL (9A/FF.3) PC
  push marched on eu_wdone (trap-chain law, like PUSHA); RMW deferred-eval
  defer narrowed to op_alui (imm-less RMW forms commit early via rule A -
  the round-1 all-S_WREQ defer had regressed the 0F NOT1 case).
- BUILD: 0 errors. Timing MET: setup slack +5.813 ns, hold +0.267 ns. sof
  fresh (mtime > RTL).
- REFLASH: safe_flash OK, echo-healthy BEFORE and AFTER.
- HARDWARE A/B (real silicon, chip vs fabric):
  * waits=0 fz40000-40199 199/200 (the 1 = fz40173, documented 1-row PS
    transient @ row 754 ps 2!=6, confirmed cosmetic chip-vs-TB - NOT a
    regression). waits=0 surface unregressed.
  * waits=1 fz84000-84049: first-div median 408.5 -> 443.0 (fixes live,
    drift pushed deeper). Still 0/50 fully clean.
  * waits=3 fz84000-84049: clean 4/50 -> 6/50, first-div median 527 -> 558.5.
- Golden 169000/169000 + w1/w3 1200/1200 held (TB); waits=0 chip-vs-TB fuzz
  80/80 clean. 5 contexts now cycle-exact (far-flush, PUSHA, RMW write,
  far-CALL, RMW-narrow); waits>=1 gate NOT met - the remaining tail is the
  shared-path wait-aware reservation FLOOR (biu_model.md / closure_checkpoint).

## 2026-07-14 — reflash: WAITS>=1 RMW-write deferred-eval qualification

- SCOPE: one waits>=1 core-RTL fix (commit d339204) - the RMW mem write
  (S_WREQ) takes the deferred (eval_ext) commit only if readiness was
  registered ENTERING T4 (new eu_defer_wr -> stricter ext_ok_wr in v30_biu).
  Cycle-exact vs chip at w0-w5 (sweep_rmw.py) for ADD/NEG/INC word forms;
  byte forms exact at w1/w3 (gate levels). Context 2 (trailing POP read)
  investigated + found NOT a distinct bug (accumulated drift); remaining is
  a diverse phase tail - characterized + deferred (biu_model.md).
- BUILD: 0 errors. Timing MET: setup slack +4.958 ns, hold +0.265 ns
  (Full Compilation successful). sof fresh (mtime > RTL).
- REFLASH: safe_flash OK (0 errors, VERIFY ok cfg 0x1ff0008). echo-healthy
  BEFORE and AFTER.
- HARDWARE A/B (real silicon, chip vs fabric):
  * waits=0 fz30000-30199 200/200 clean (unregressed - critical gate).
  * waits=1 fz84000-84049: first-divergence median row 385 -> 408.5
    (RMW fix live; drift reduced a touch deeper). Still 0/50 fully clean.
  * waits=3 fz84000-84049: 4/50 clean, first-divergence median 527.
- Golden 169000/169000 + w1/w3 1200/1200 held (TB); waits=0 chip-vs-TB fuzz
  120/120 clean. 3 contexts now generalized (far-flush, PUSHA, RMW write);
  waits>=1 arbitrary-sequence gate still NOT met (diverse phase tail).

## 2026-07-14 — reflash: WAITS>=1 cadence generalization (far-flush + PUSHA)

- SCOPE: two waits>=1 core-RTL cadence fixes (commits 84d59ee far-flush
  ff_t4 gated on evald; de18d78 PUSHA marches inter-write chain on eu_wdone).
- BUILD: 0 errors. Timing MET: setup slack +5.000 ns, hold +0.264 ns
  (Full Compilation successful, 305 warnings). Util 9,776 ALMs (23%),
  5153 regs, 13 DSP. sof fresh (verified mtime > RTL edits).
- REFLASH: safe_flash OK (quartus_pgm 0 errors, VERIFY ok cfg 0x1ff0008,
  use_core=False). echo-healthy BEFORE and AFTER (ECHO TEST PASSED both).
- HARDWARE A/B (real silicon, chip vs fabric):
  * waits=0 fz20000-20199 200/200 clean (unregressed - critical gate).
  * waits=1 fz84000-84049: first-divergence row min 224 / median 385
    (pre-fix the first drift was the loader far-flush at ~row 30 in EVERY
    seed; the fix pushed it to row 385 median - loader + early stream now
    bit-clean in silicon). Not fully closed (RMW-write / trailing-read
    contexts remain deeper - characterized + deferred, biu_model.md).
  * waits=3 fz84000-84049: 4/50 fully clean, first-divergence median 527.
- Golden 169000/169000 + w1/w3 1200/1200 held (TB); waits=0 chip-vs-TB
  fuzz 120/120 clean. PARTIAL closure of the waits>=1 arbitrary-sequence
  surface - drift rate cut, gate not yet met.

## 2026-07-14 — reflash: taken-branch flush + 8C-store recognition fits

- BUILD: 0 errors. Timing MET: setup slack +5.562 ns, hold +0.267 ns.
- safe_flash: Configuration succeeded, VERIFY ok; echo-healthy before/after;
  no wedge. Fabric now carries commit 5568052 (post_flush pin tap + 8C
  sreg-store shadow, on top of the shadow single-boundary fix).
- HARDWARE A/B (chip vs fabric, fz10000-10499 --inject-int): 494 -> 497/500
  (fz10117/10283 branch-flush + fz10317 8C-store now clean in silicon;
  residual 3 = fz10055 float floor + fz10175 NMI + fz10460 REP-LODSB).
- chip-vs-TB (ground truth): 498/500. Regression corpus replay chip-vs-TB
  all d=0 (incl now-closed fz10066/10117/10283/10317/10486, loop/farjmp/
  swint). Added fz10175/fz10460 residual reps to the corpus.

## 2026-07-14 — reflash: recognition-shadow single-boundary fix

- BUILD: 0 errors, 305 warnings. Timing MET: setup slack +4.242 ns, hold
  +0.255 ns.
- safe_flash: quartus_pgm Configuration succeeded (0 errors), VERIFY ok
  (pwr_good/cpu_running/MAGIC). Echo-healthy before/after; no wedge.
- Fabric now carries commit 1a7f601 (shadow cleared at S_FIRST opcode pop).
- HARDWARE A/B (chip vs fabric, fz10000-10499 --inject-int): 488 -> 494/500.
  The 6 shadow-caused seeds now clean in silicon (INT fz10066/10251/10459,
  NMI fz10248/10431/10486); residual 6 = fz10055 (fabric synth float floor)
  + the 5 branch-flush/8C-store recognition-point residuals.
- chip-vs-TB (ground truth): 495/500. Regression corpus replay chip-vs-TB
  all d=0 (inject fz10041/10055/10059/10066/10486, loop fz7203/7207, farjmp
  fz8304, swint fz8007/8032).

## 2026-07-14 — reflash: NMI IVT-read idle-window early commit (Mission-D)

- BUILD: quartus_sh --flow compile, 0 errors, 305 warnings. Timing MET:
  worst-case setup slack +3.829 ns, hold +0.265 ns (recovery +29.171,
  removal +0.944, min-pulse +1.196). All positive.
- safe_flash: PREP ok, quartus_pgm Configuration succeeded (0 errors),
  VERIFY ok (pwr_good/cpu_running/MAGIC). Board echo-healthy BEFORE and
  AFTER; final echo PASSED. No wedge.
- Fabric now carries commit 07f65f6 (eu_soon_ivt + q_cnt<=2 defer_idle arm).
- HARDWARE A/B (chip vs fabric, fz10000-10499 --inject-int): 488/500 (was
  477/500). The 11 NMI IVT-read seeds now clean in silicon; residual 12 =
  fz10055 (fabric synth float floor, chip-vs-TB clean) + the 11 chip-vs-TB
  residuals (7 INT INTA-commit, 4 NMI doomed-prefetch).
- chip-vs-TB (ground truth, socketed chip forced): 489/500. Regression
  corpus replay (chip-vs-TB): inject fz10041/10055/10059, loop fz7203/7207,
  farjmp fz8304, swint fz8007/8032 all d=0 (the flush seeds closed for free
  by 006b257/a9f1468 as anticipated).

## 2026-07-11 — first deployment: harness verified, CPU not driving pins

Deployed the phase-3 harness (4 MHz CPU clock, zero wait states, bring-up
boot image) over JTAG and dumped the capture buffer repeatedly.

**Verified working:**
- JTAG programming, In-System Memory readout of all three instances
  (ME0/ME1/CAPT). Boot image read back byte-perfect from ME0.
- Capture pipeline: reset-tail records (RESET=1, READY=1, 33 records) then
  per-cycle records exactly as designed.
- Power-up sequencing added during debug: ENABLE_N asserted at config, ~131 ms
  rail-settle wait, then 32 CPU-clock RESET pulse (nec_bus.sv).

**Problem: every CPU-driven pin (BS, QS, RD_N, UBE_N, BUSLOCK_N, AD) reads
floating-low through the level shifters — before, during, and after reset.**
The V30 never drove anything. The harness FSM chases the floating status
(000 reads as INTA ≠ PASV) in an endless T1→T2→T3→T4 loop; that loop in the
trace is a harness artifact, not CPU activity.

Evidence and eliminations:
- Reset sequencing correct at the FPGA (captured in-trace).
- Float pattern was high-ish (PASV, AD=207FF) ~8 µs after config, all-low by
  131 ms — consistent with residual charge draining from an unpowered rail.
- ENABLE_N polarity test: inverted to 1 → identical float signature. Both
  polarities leave the CPU dead, suggesting the PMOS power switch is not the
  (only) polarity issue, or power isn't the whole story.
- Schematic: ~CHIP_ENABLE gates a P-MOSFET high-side switch on the V30's 5V;
  AD0-15 behind F_AD_DIR transceivers; A16-19 fixed CPU→FPGA.

**Physical measurements (Martin, 2026-07-11):** VDD = 5 V, CLK = 4 MHz,
READY high, RESET low (post-release), CHIP_ENABLE gating works. Chip is
powered, clocked, and reset correctly — yet drives nothing.

## ROOT CAUSE: RQ/AK0 and RQ/AK1 grounded on the PCB

The PCB netlist ties V30 socket pads 30 and 31 to GND. Correct for
small-mode semantics (HLDRQ active-high input, HLDAK output idles low), but
the harness straps LARGE mode, where pins 30/31 are RQ/AK1 and RQ/AK0 —
**active-low bus-hold request inputs. Grounded = permanent hold request.**
Per datasheet p98-99, the CPU acknowledges and floats the address bus,
AD bus, and all control lines — indefinitely. Matches every observation,
including the lone queue-status blip at startup.

**Fix (chip is socketed):** bend pins 30 and 31 out of the socket and pull
each up to 5 V through 10 k. (The 8086 has internal pull-ups on RQ/GT and
the V30 likely inherits them, but the datasheet doesn't confirm it — use
external pull-ups.)

**Alternative validation path (no rework):** drive S/LG high (FPGA pin
NEC_LG_N) to select small mode, where the grounded pins are electrically
correct — but this loses QS0/QS1 queue status, so it is only a stepping
stone. Harness FSM would need a min-mode decode variant (ASTB as address
strobe, IO/M + RD/WR for cycle type).

## 2026-07-11 (later) — SMALL MODE: CPU EXECUTING, full chain verified

Implemented small-scale mode in nec_bus (cfg_small_mode: transparent ASTB
address latch, RD/WR strobe-driven datapath, IO/M low=I/O). NEC_LG_N=1.
Dual-mode verilator TB passes. Deployed to hardware:

**The V30 executes the boot program.** Captured trace (capture8) shows:
- RESET release → pins go from floating to driven-idle ~8 cycles later;
  **first bus cycle ~9 CPU clocks after reset release** (small mode,
  preliminary — sampling offsets not yet calibrated out).
- First fetch at FFFF0h, FPGA BRAM returns 00EA (far jump) — then prefetch
  overshoot: fetches FFFF2/FFFF4/FFFF6 (8 bytes for a 5-byte instruction)
  while the EU decodes.
- Jump lands: next fetch 00100h. Program bytes stream back exactly as
  loaded (34B8, BB12, 2000, 0789, 00A0, A120...).
- MOV [BW],AW executes: MEMW at 02000h, data 1234h, correct byte enables.
- Loop repeats ~35x across the 4096-cycle trace. 4-cycle bus cycles, zero
  wait states throughout.

Known capture artifacts to fix:
- ASTB pulses fall between the two per-cycle sample points → the record's
  QS[0] bit never shows ASTB high. Make it a sticky-OR over the cycle.
  (The transparent address latch works; only the record bit is affected.)
- Pre-drive float reads as "IOR" in the decoder until the CPU starts
  driving (~8 cycles post-release). Cosmetic.
- JTAG bulk reads still occasionally all-zero; dump_capture.tcl now
  retries aggressively (all-zero chunk = provably bogus since READY bit
  is always set in valid records). capture8 = 4096/4096 valid.

**Milestone: full discovery-loop chain works** — assemble program → load
BRAM → power/reset sequence → real V30 executes → per-cycle capture →
JTAG dump → decode. Next: sticky strobe bits, then the RQ/AK rework to
unlock large mode + queue status.

## 2026-07-11 (later) — HPS bridge: ARM lockup incident + hardening

First deployment of the lightweight-bridge harness control locked up the
DE10's ARM hard (network dead, SSH gone): the first /dev/mem access to
0xFF200000 stalled — an unanswered lw-bridge AXI transaction seizes the L3
interconnect and takes the whole SoC down. Likely cause: the AXI slave was
reset by the MiSTer framework reset (hps_io status/buttons), which is
undefined once MiSTer Main is killed — the slave never asserted ready.

Remote recovery attempts, all failed (documenting for next time):
- Reconfiguring the FPGA with an always-responding slave (hoping the fresh
  fabric would complete the pending transaction): no recovery.
- System Console DAP master: Quartus Lite exposes no HPS master service.
- quartus_hps -o I: DAP IDCODE reads, but "Fail to power up the System and
  Debug power" — the seizure blocks the debug power handshake too.
→ **A physical power cycle is the only way back.**

Hardening now in place (sim-verified, awaiting hardware retest):
- hps_axi_slave reset by a local POR pulse only — always responds,
  regardless of framework/MiSTer state.
- host_attached latch: standalone boots use the framework reset as before;
  after the first CTRL write the host owns the harness lifecycle.
- capture_buf reset is POR-only; trace survives host_reset for readout.
- sw/v30ctl.py `prep` puts the bridges into reset BEFORE FPGA
  reconfiguration (run it every time before quartus_pgm).

Safe flow after every boot: killall MiSTer → v30ctl.py prep → make run →
v30ctl.py status.

## 2026-07-11 (evening) — HPS bridge verified: full discovery loop live

After the power cycle, the hardened bridge worked first try (prep →
flash → status, no lockup). Verified end-to-end on hardware:

- `v30ctl.py run boot.bin`: stop → load 64 KB over the bridge → fast
  restart → capture full → dump, in seconds (vs minutes over JTAG).
  Results identical to the JTAG-era captures (8-clk reset latency,
  64-clk boot loop).
- **Full toolchain loop**: a new program assembled with v30asm
  (MOV CW,0AAAAh; MOV BW,3000h; loop: MOV [BW],CW; INC CW; BR loop),
  loaded and run via the bridge — capture shows 161 iterations with the
  write data incrementing aaaa, aaab, aaac... (live execution proof).
  Loop period: **25 CPU clocks** for MOV [BW],CW + INC CW + BR short.

The write-test → run-on-silicon → measure loop is fully operational.
Remaining before suite-grade data: load/store routines (designed,
docs/notes/loadstore_design.md), RQ/AK rework for large mode + queue
status.

## 2026-07-11 (night) — LARGE MODE LIVE: real queue status

RQ/AK0-1 rework done (pins lifted + pulled up). S/LG̅ strap rewired to
follow CFG.small_mode so mode is host-switchable (change only in
host_reset). First max-mode run: BS status + T-states decode cleanly,
QS0/QS1 report real queue ops, queue-depth reconstruction works (peak 5),
442 instruction boundaries visible, per-instruction F-to-F times
{3,5,7,11,12,12,14} sum to the 64-clock loop measured independently on
the bus side. See docs/facts/measurements.md.

One transient: the first large-mode `v30ctl run` invocation hung in
load_mem (>45 s); an identical retry completed in 0.7 s. Unexplained —
watch for recurrence.

Everything is now in place for the decode/prefetch research program and
the load/store implementation (stage 1+2 together, since queue status
is available).

**Tooling notes:**
- `read_content_from_memory` returns content highest-address-first; bulk
  reads intermittently return all-zeros on Quartus 17.1 even with re-read
  verification (single-word reads are reliable). sw/dump_capture.tcl uses
  64-word chunks + retry; treat all-zero regions in dumps with suspicion —
  a genuine record always has the READY bit (51) set.
- A valid capture record can never be 0x0000000000000000.

## 2026-07-13 — Campaign 4 kickoff: in-FPGA A/B integration + safe-flash

### A/B integration architecture (landed, commit 61185d0)
The v30_core is instantiated inside system_large behind a CFG selector so
nec_bus's pin side drives either the socketed chip or the internal core:

- **CFG.use_core (bit 25)** in hps_axi_slave (default 0 = chip). Change
  only under host_reset, like the other CFG fields.
- **nec_bus AD refactor**: the inout `NEC_AD` port became a unidirectional
  trio `ad_drive` / `ad_drive_en` / `ad_sample`. This removes the
  inout<->inout bridge that a naive A/B mux would need (Verilator flagged
  UNOPTFLAT/circular; Quartus would cut the false loop arbitrarily). The
  chip datapath is bit-identical: `ad_sample` = NEC_AD in chip mode, the
  drive is the same registered `rdata_q` under the same `drive_en`.
  tb_harness passes unchanged; largemode_synth.hex regenerates byte-
  identical; the 155440/155500 core golden regression is untouched.
- **system_large mux**: one-directional status pins (BS/QS/RD_N/UBE_N/
  BUSLOCK_N) mux chip<->core with plain 2:1s; the harness read data is
  injected on the core's shared AD net under `ad_drive_en`; nec_bus's
  outputs fan out to both the physical pins and the core; the socketed
  chip is powered off (ENABLE_N) while the core is selected. The core is
  clocked by NEC_CLK (same 4 MHz cadence the chip sees) and held in reset
  unless selected.

### Sim A/B (Mission A) — tb_ab.sv + sw/check_ab_sim.py
tb_ab drives the real integration (system_large) from the AXI master BFM
only and exercises BOTH selector positions. check_ab_sim runs the core
position, drains the harness capture, and diffs it against the real-chip
boot golden (sw/testdata/largemode_boot_real.hex) with check_boot's column
policy.

- **Chip position**: passes (large-mode BFM vector fetch + write/readback).
- **Core position**: the core boots from the in-memory image behind the
  real capture path, but DESYNCS. This is the current gate.

### FINDING — core<->harness commit-phase desync (gates hardware)
Aligned at the first vector fetch, the harness-core trace is identical to
the `+bootimg` replay (which matches the chip, mission G) for cycles 0-5,
including the fetched data words (00ea/0001/9000). Then it diverges: the
core's EU pops the 2nd queue byte one cycle EARLY (at T3 rather than T4),
loses far-jump alignment, and runs off into spurious MEMR/MEMW at 00000
instead of taking JMP FAR 0000:0100.

Ruled out: READY is clean (1 every cycle, no phantom Tw); read data is
correct (right bytes fetched); boot images are byte-identical
(boot_even/odd.hex == boot.bin). Correlated signal: the harness-core
starts its first fetch one NEC_CLK earlier relative to RESET release
(release+8 vs the +bootimg release+9). Since a deterministic FSM with
matching inputs must match, an input differs at a cycle <=5 — the suspects
are the RESET-release phase (NEC_CLK-domain core vs nec_bus sys-clock
release) and the exact edge at which the BIU consumes ad_i.

BIU read-data contract (v30_biu): `fetch_data <= ad_i` (prefetch) and the
`eu_rdata` latch fire at the SINGLE clock edge that ends T3 or the final
Tw, guarded by `ready` sampled high at that edge (t3_done). `ad_i` and
`ready` must both be valid at that NEC_CLK posedge. An idealized TB drives
read data combinationally through T2/T3/Tw and trivially satisfies this;
nec_bus must present the same stability at the core's sampling edge.

Next step before any new-bitstream flash: align the core's RESET-release
phase / read-data presentation so the harness-core matches the golden in
sim (Mission A's own gate), likely aided by exposing the core's
V30_BACKDOOR dbg state through system_large in a debug build to pinpoint
the first EU/BIU state that diverges. Only then flash (Mission C).

### Safe-flash (Mission B) — sw/safe_flash.sh, TESTED
Atomic prep -> quartus_pgm -> status(magic) verify, per-step timeouts.
Tested once with the CURRENT known-good bitstream
(hdl/output_files/nec_test.sof, built 2026-07-12): prep OK, quartus_pgm
"Configuration succeeded", verify OK (MAGIC confirmed, cfg readback
0x01ff0008 = known-good small-mode design, use_core bit reads 0). Board
echo test passed afterward. On an unreachable board after flashing the
script STOPs and demands a physical power cycle (no retry). This is the
ONLY sanctioned path to reprogram the FPGA.

### 2026-07-13 (cont.) — desync root-cause refinement + review items

Refined hypothesis for the core<->harness desync (leading candidate): a
read-data HOLD-margin race at the core's sampling edge. The BIU latches
fetch/read data at the rising CLK edge that ends T3 (t3_done). nec_bus
drives read data under `drive_en`, which it DEASSERTS entering T4 - i.e.
at essentially the same NEC_CLK edge the core samples on. The real chip
samples with its ~65 ns internal output/again-input delay, so it reads the
data mid-T3 with margin; the synchronous core samples AT the T3->T4 edge,
where nec_bus is simultaneously releasing the drive - zero hold margin, a
phase race that resolves per-fetch depending on micro-alignment (explains
why the first fetches read correct bytes but a later one desyncs the queue
pop by one cycle). Fix direction: hold the harness read-data drive to the
core through (past) its T3->T4 sampling edge - i.e. present read data to
the core the way tb_v30_core does (valid across T2/T3 and stably past the
sampling edge), NOT gated to release exactly at T4. This must hold on
hardware too (the FPGA-internal core sampling the harness-driven bus).
Next iteration: implement the core-side read-data hold, re-run
check_ab_sim to green, THEN proceed to Mission C (flash) / D (disp phase
matrix) via the now-plumbed CFG.use_core. A debug build exposing the
core's V30_BACKDOOR dbg_regs through system_large would pinpoint the first
divergent EU/BIU microstate if the hold fix is insufficient.

Review items folded in (commit 2035cce):
- HOST PATH: CFG.use_core (bit 25) now plumbed through v30ctl.py (set_cfg,
  serve CFG 5th field, cfg --use-core, status), v30run.py
  (ServeRunner.cfg + run_image use_core=). Backward compatible; updated
  v30ctl.py scp'd to the board.
- gen_seq CONTAINMENT: forward branches could land inside a safe-gadget
  (DIV / string), skipping trap-safe setup and escaping via the untouched
  IVT (fz101 -> 0x99xxx). Gadgets are now atomic (emit_atomic + branch
  target snap-forward). 120 seeds clean.
- QS-FLICKER: classified as a queue-status display artifact - check_seq
  separates a 1-cycle F<->S QS-only disagreement into a tolerated `flick`
  count (real divergence always shows in the other columns); --strict-qs
  to investigate; the A/B run is the definitive confirmation.

## 2026-07-13 (block 2) — Mission A2/D/E: laws landed, gate satisfied

Mission A2 (hold fix): the core<->harness desync was the predicted
delta-cycle race - the core's derived CLK posedge saw POST-edge values
of nec_bus outputs (zero hold), where the chip sees pre-edge values via
board propagation. Fix = one sys-clock input pipeline on every
nec_bus->core signal (system_large only). check_ab_sim: core boot now
MATCHES the chip golden in-harness (187 rows, loop-aligned). Chip path
bit-identical (tb_harness 25/25, synth hex byte-identical).

Mission D (three laws, all golden-neutral at 155440/155500 exact):
1. disp-reader final-pop defer: fresh queue head (dry last cycle) + pop
   on fetch T2 -> defer 1 (the 2-cycle read shift is mechanical).
   S_DLO polls dry queues every cycle (old 2-grain was aliased).
2. disp16 store ready @ hi-pop+2 (old @+3 was a phase-aliased fit).
3. split word access at offset FFFFh: 2nd byte at offset 0 of the SAME
   segment (found by fz494; real functional bug, was 20-bit linear +1).
Method: sw/sweep_dispphase.py (168-cell matrix: 4 reader + 3 store EA
modes x 3 prefixes x 8 phases) + tb_v30_core +eudbg state dump; three
law iterations to 168/168. All measured chip-vs-TB through serve -
no flash needed; silicon A/B confirmation rides with Mission C.

Mission E: **Campaign 3 exit gate SATISFIED - 500/500 consecutive
clean (fz600-1099), zero flickers.** Expansions: callret 500/500
(fz1100-1599); sregw/popf gating in progress. Cumulative session fuzz:
~2400 board-vs-TB sequences.

Known open (non-gate): waits>=1 qs_e flush-display timing at far jumps
(2 rows/trace, phase-parity; execution identical) - the only class the
w1 matrix shows; reader/store laws are wait-clean.

## 2026-07-13 (block 3) — synthesis fix + Mission C FIRST LIGHT

### Iterative shifter (second synth anti-pattern, commit e7c315a)
After the iterative divider (c2beb6a) the Quartus build was still slow:
a SECOND 255-deep combinational unroll dominated - the `shrot` shift/
rotate function (D0-D3/C0/C1, all 8 sub-ops), evaluated as one giant
cone at retirement. Replaced with ONE iterative shift stage (the divider
pattern): loaded at each dispatch site, one single-bit shift per clock
through the S_SHWAIT/S_WAITX window already spent, result+flags landing
in sh_res/sh_fl before S_EX/S_RMWX. Full-8-bit-count/no-masking, the
byte sibling-lane shift register, and every fitted flag law preserved
bit-for-bit. GATE: golden 155440/155500 (per-op BYTE-IDENTICAL to
baseline), all shift forms 500/500 (13000/13000), fuzz 30/30 chip-vs-TB.
Also audited the EU: the 255 shifter was the ONLY large combinational
unroll; INS/EXT, ROL4/ROR4, 4S are sequential (burn-counter) machines.

### Quartus build (Task 2) - the spike is GONE
Full compile clean (0 errors, 0 critical warnings), .sof produced:
- **Analysis & Synthesis (quartus_map): 00:03:47** (was ~25 min).
- Fitter 00:03:57, Assembler 12s, STA 5s; total 00:08:01.
- Megafunctions: 2 lpm_divide, BOTH the small 8-bit AAM (D4/CVTBD)
  `/` and `%` (the intended small combinational unit, c2beb6a) - no
  wide/group dividers, no giant combinational cones.
- Fmax emu/core clock 84.82 MHz (FPGA_CLK2_50 137 MHz); worst-case
  setup slack +9.151 ns, hold +0.268 ns - timing MET.
- Utilization 9,835/41,910 ALMs (23%), 5079 registers, 13 DSP (12%).

### Mission C - safe_flash + IN-SILICON FIRST LIGHT
safe_flash.sh hdl/output_files/nec_test.sof: PREP/FLASH/VERIFY all OK
(cfg 0x1ff0008, use_core=False, pwr_good, cpu_running). Board reachable.

check_ab_hw.py all 800 (boot image, both selector positions in silicon):
- **chip position (use_core=0) vs boot golden: MATCH over 800 rows** -
  the new bitstream did NOT disturb the known-good chip path.
- **core position (use_core=1) vs chip: MATCH over 800 rows** - FIRST
  LIGHT: the in-fabric V30 core matches the socketed part, same harness,
  same run, in real silicon.
- core vs golden: MATCH over 800 rows.

In-silicon A/B sequence fuzz (check_seq --hw-ab, chip vs fabric core
BOTH on the FPGA, no Verilator): **fz4000-4039 40/40 clean** - the
definitive in-silicon confirmation of the Mission D disp-reader /
disp16-store / split-wrap laws (previously chip-vs-TB only).

### Campaign 4 A/B done-criterion SATISFIED (2026-07-13)
**In-silicon A/B sequence fuzz, chip (use_core=0) vs fabric core
(use_core=1) both on the same FPGA, no Verilator: fz4040-4539 500/500
clean, zero divergence, zero QS flickers** (with fz4000-4039 = 540
consecutive). This is the true-silicon analogue of the Campaign 3 exit
gate and satisfies the Campaign 4 done-criterion (>=500 zero-divergence
across the corpus). Board echo-healthy after the run. The in-fabric V30
core is now cycle-for-cycle indistinguishable from the socketed chip
across the fuzz corpus in real silicon.

## 2026-07-13 (block 4) — clock-enable (CE) refactor, all gates passed

The in-fabric core was decoupled from NEC_CLK: it now runs on the fast sys
clk and advances only on CE (= nec_bus tick_rise) with CE_HALF (= tick_fall)
for the one negedge process. CE is locked to the NEC_CLK cadence so the A/B
comparison stays lock-step with the chip. Full plan + itemized outcome in
docs/notes/ce_plan.md; commits e15492d / 9716b01 / 6f7cdd2 (+ this doc/build
commit).

- RTL: every sequential process in v30_biu/v30_eu gated `if(srst) ...
  else if(ce)`; reset stays ungated (bkd_load fires on RESET regardless of
  CE). The two desync traps were handled: eu_started moved into the ce
  branch and added to the biu reset; the eu "every-state" pulse/pin block
  moved inside `else if(ce)` with flush_now<=0 added to the eu reset;
  negedge t1_half2 gated by ce_half.
- GOLDEN GATE (CE-high): 155440/155500 bit+cycle-identical (only 8F.0
  residual); w1/w3 1200/1200. CE-HOLD SANITY (+ce_div=N>1, +ce_hold_check):
  rows identical to N=1 and u_eu.state/u_biu.state/q_cnt/div_cnt frozen on
  CE-low clocks (N=3 9940/10000, N=7 5000/5000, zero freeze violations).
- HARNESS: nec_bus exposes tick_rise_o/tick_fall_o (its only change);
  system_large u_core switched to .CLK(clk)/.CE/.CE_HALF. check_ab_sim core
  boot MATCH 287 rows (Mission A2 input pipe carried over unchanged — no
  new phase fix needed, contra the 2026-07-13 boot-desync worry). Chip path
  bit-identical: tb_harness ALL PASSED, largemode_synth.hex byte-identical.
- BUILD: 0 errors, 8m40s total (quartus_map 3m52s, Fitter 4m24s) — no
  synthesis spike. Timing MET: emu/core clock 32 MHz, Fmax 48.09 MHz
  (setup slack +5.227 ns, hold +0.263 ns). Fmax fell from the pre-CE
  84.82 MHz because the core now lives on the 32 MHz fabric domain by
  design; 50% headroom. Util 9,690 ALMs (23%), 5117 regs, 13 DSP; only
  the 2 intended small AAM lpm_divide units. safe_flash'd (VERIFY ok).
- HARDWARE A/B (real silicon): chip position vs golden MATCH 800/800
  (chip path undisturbed by the new bitstream); FIRST LIGHT — CE-driven
  fabric core vs socketed chip MATCH 800/800; in-silicon A/B sequence
  fuzz fz5000-5499 500/500 clean, zero divergence, zero QS flickers.
  Board echo-healthy after. The CE-driven in-fabric core is cycle-for-
  cycle indistinguishable from the socketed chip in real silicon.
- Deferred (as coordinated): a host-selectable independent core-rate CE
  divider (feed the core CE from a host-controllable divider rather than
  tick_rise); the +ce_div plumbing in tb_v30_core is the sim-side seed.

## BIU-rebuild first silicon confirmation (2026-07-14, biu-rebuild @ a5a92a3)

Flashed the biu-rebuild bitstream (coordinator ran safe_flash: Configuration
succeeded 0 errors; VERIFY pwr_good/cpu_running/cap_full True, use_core False
default; harness healthy). Synthesis: 0 errors, timing MET (worst-case setup
slack +4.199ns, hold +0.260ns, all clocks positive). Full hardware A/B:

1. HEALTH echo PASSED (before + after).
2. w0 CROWN JEWEL: boot chip(use_core=0)-vs-fabric(use_core=1) MATCH 200 rows;
   core-vs-golden MATCH. The whole rebuild is w0-EXACT in silicon.
3. w1/w3 DRIFT DROP LIVE: chip-vs-fabric drift is IDENTICAL PER-SEED to the sim
   chip-vs-TB drift (15 seeds 90000-14: w1 both mean 408.1 CLEAN 1/15; w3 both
   596.5 CLEAN 3/15 - every seed value matches exactly). Synth float floor = 0;
   the fabric core is cycle-for-cycle the Verilator TB. The five landed fronts
   (consumption-resume, arb-store, Jcc-w1-flush, load-ext) are REAL in fabric.
4. BUSLOCK live: chip-vs-fabric release-at-write-T4 EXACT, prefetch-transparency
   EXACT (1 fetch inside), no-false-lock EXACT; assert 2-cyc-late (documented
   inert Stage-6 residual). Stage-6 LOCK confirmed in silicon.
5. INTERRUPTS: chip-vs-TB inject-int fz10000-10199 = 200/200 CLEAN (unregressed;
   the flush/arbitration changes are w0-neutral). The 2 chip-vs-FABRIC hw-ab
   flags (fz10000/10018) are chip-vs-TB clean = the inert async-INT-recognition
   float floor (async pin latched 1 cyc differently in fabric), not a bug.

VERDICT: the rebuild's first silicon confirmation is CLEAN. w0 chip-exact in
fabric; the w1/w3 drift drop is real (silicon==sim exactly); BUSLOCK live;
interrupts unregressed. Board healthy on the new bitstream.
