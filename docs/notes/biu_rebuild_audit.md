# BIU QUEUE/PREFETCH REBUILD — Phase 1 KLUDGE AUDIT

Baseline commit (rollback / comparison anchor): **c0c28f1**
(`waits>=1 structural round 3: controlled-sled measurement -> bus-phase FLOOR`).
Files audited: `hdl/rtl/core/v30_biu.sv` (952 lines) and the bus-interaction
surface of `hdl/rtl/core/v30_eu.sv` (4845 lines). This is the MAP of what the
rebuild replaces.

## Framing — the single structural defect

The chip drives every queue/prefetch/arbitration/retire decision off the
**true bus grid**: each bus cycle is 4+N clocks (N = wait states), and the
chip's decisions are keyed to the T-state and the 2-cycle bus-grid PHASE of
that grid. The current core instead drives most of those decisions off
**fixed CPU-cycle offsets** (`dly` countdowns, per-state `eu_req`
reservations keyed on `dly==1`, and a set of special-case commit paths in the
BIU that fire on fixed cycle relationships). At N=0 the CPU clock and the bus
grid coincide cycle-for-cycle, so the fixed offsets land on the correct bus
slot and the w0 golden passes. Under N>=1 the grid stretches but the fixed
offsets do not, so events land on the wrong bus slot -> accumulating drift.

Two distinct classes of kludge implement this "fake the grid at w0" behavior:

- **Class K-BIU**: special-case commit/eval/display paths in `v30_biu.sv`
  bolted on to reproduce measured w0 (and 6-form-fitted w1/w3) shapes. Each is
  a patch over the fact that the BIU does not carry a first-class bus-grid
  phase/occupancy state machine — it carries a `state` T-state counter plus a
  thicket of qualifier flags.
- **Class K-EU**: the EU issues bus requests and multi-access chains off fixed
  `dly` CPU-cycle counters and `eu_done`-keyed transitions. The full inventory
  and classification already lives in `docs/notes/waits_structural_plan.md`
  §"Inventory + classification of every fixed-CPU-cycle mechanism" (A/B/C/D);
  this audit references it rather than re-transcribing every `dly<=K` site.

The decisive evidence that these are kludges and not the real law: the prior
3-round structural campaign (waits_structural_plan.md, rounds 1-3) proved the
residual waits>=1 drift is a **bidirectional bus-phase-alignment floor** — at
even leading phase the core resumes prefetch ~3 cycles too EARLY, at odd phase
it stalls ~8 cycles too LATE (biu_model.md §Round 3, A2 table). A model built
on fixed offsets cannot be phase-correct in both directions simultaneously;
only a model that tracks the real grid phase can.

--------------------------------------------------------------------------
## Class K-BIU — the BIU special-case commit/eval/display paths

Each entry: WHAT it does · WHY it passes w0 · HOW/why it breaks under waits.

### KB1. `eval_ext` — the deferred waited-cycle completion eval
Lines 456, 588-669 (ST_TI branch), 819-821 (ST_T4 -> set eval_ext), 899.
- WHAT: a waited bus cycle does NOT evaluate the next commit at its T3->T4
  edge; instead a flag `eval_ext` is raised at the T4 edge and the "completion
  eval" runs DURING the following (post-T4) cycle, mid-cycle, driving the
  picked status/address and entering T1 at that cycle's end. Its own end is
  explicitly NOT an eval point.
- WHY w0: at w0, `evald` is always set at the T3->T4 edge (READY high), so the
  `!evald` guard at line 819 is false and `eval_ext` never fires — the whole
  path is dead code at zero waits. The w0 commit runs at the T3->T4 edge as
  the "normal" law.
- HOW it breaks / why it is a kludge: `eval_ext` is the SINGLE most load-
  bearing waits-only mechanism, and it is where the dominant drift lives.
  Round 2 localized the dominant retire / MOV-imm drift to "the core resumes
  the next prefetch at the completed fetch's `eval_ext` (T4+1) with the queue
  at threshold, while the chip inserts the ~3-idle bus-grid prefetch-resume
  gap and resumes at ~T4+4 (w1) / T4+3 (w3)." So `eval_ext` fires the resumed
  prefetch on the wrong bus slot. It is a fixed T4+1 rule standing in for a
  phase-dependent grid decision (biu_model.md §Round 2/3).

### KB2. `defer_t4` / `eu_soon` — fetch-T3 eval deferred into T4
Lines 449, 702-704 (arm on fetch T3 when `eu_soon && !eu_ready`), 720-742
(consume mid-T4), `defer_show` 884.
- WHAT: when a prefetch's T3 completion eval coincides with an EU reader that
  will be ready NEXT cycle (`eu_soon`), the eval is deferred into that fetch's
  T4; the now-ready read commits mid-T4 and its T1 follows at the T4 edge —
  one cycle earlier than the plain do_commit path.
- WHY w0: fitted exactly on the reg-EA reader law (biu_model.md §"Idle-window
  reg-EA reader commit law"). At w0 `eu_soon` (ready-next-cycle) lines up with
  the fetch T4 by construction.
- HOW it breaks: `eu_soon` is a fixed "ready in exactly 1 CPU cycle" promise
  from the EU (`dly==1`), not a bus-grid lead. Under waits the fetch T4 and
  the reader's readiness no longer sit one CPU cycle apart, so the mid-T4
  commit either fires early or misses. This is one of the "premature-under-
  waits reservations" the plan flags (§C).

### KB3. `defer_idle` / `eu_soon_ea` / `eu_soon_ivt` — idle-window early commit
Lines 456, 608-668, `eu_soon_ea` 105-109, `eu_soon_ivt` 108-110, gates 650-667,
`idle_commit` display 898.
- WHAT: when a reg-EA reader's 2-cycle EA compute falls entirely in a bus-idle
  window (no in-flight fetch for `defer_t4`'s T4 to land on), a separate flag
  `defer_idle` is armed one idle cycle early so the read commits directly in
  the idle window (address strobe rides the S_REQ idle cycle) instead of
  waiting a fresh idle-end do_commit. `eu_soon_ivt` extends the same trick to
  the NMI/INT IVT read gated on `q_cnt<=2`.
- WHY w0: fitted to close the "reg-EA reader reads +1 late at the one idle-
  landing phase" residual (ph7 on the NOP-sled sweep). Purely a w0 phase-alias
  fix — the comment at 662-667 openly documents that it is gated on
  queue-starvation (`q_cnt<=2`) because that is the ONLY occupancy that drove
  a doomed prefetch establishing the live grid the chip commits onto E+0.
- HOW it breaks: it is a hand-tuned occupancy+phase discriminator (`q_cnt<=2`,
  `eu_soon_ea`, `eu_soon_ivt` all separate one-off gates) standing in for the
  chip's uniform "commit the read onto the next grid slot" rule. It does not
  generalize across waits or across the phase history the plan's Round-3
  bidirectional finding exposes.

### KB4. `ext_ok` / `ext_ok_wr` / `eu_defer_wr` — mid-cycle qualification rules
Lines 346-365, `eu_req_p1/p2` + `eu_ready_p1/p2` pipelines 872-876, RMW
stricter rule 350-363.
- WHAT: the `eval_ext` mid-cycle commit only picks up an EU request that was
  visible "early enough": rule A (readiness registered during T4,
  `eu_ready_p1`), rule B (req line up during T4 AND the cycle before,
  `eu_req_p1 && eu_req_p2`, killed by a flush at the T4 edge via
  `ext_flushed`). The RMW mem write (`eu_defer_wr`, = state S_WREQ) uses a
  STRICTER rule `ext_ok_wr = eu_ready_p1 && eu_ready_p2` (ready ENTERING T4).
- WHY w0: `eval_ext` is dead at w0, so these qualifiers are inert at zero
  waits and cannot touch the golden.
- HOW it breaks / kludge nature: these are three different fitted
  registered-readiness rules (A, B, and the RMW-only stricter one) each pinned
  to a specific sweep (load d0/store d2 vs store d0/d1 vs `sweep_rmw.py` w1 vs
  w3). They encode "how many CPU cycles before T4 was the request up" — a
  fixed-offset proxy for the chip's grid-phase-relative arbitration decision.
  The RMW rule (350-363) is the clearest example: an entire paragraph of
  comment justifies a one-bit `eu_ready_p2` distinction from a single sweep.

### KB5. `ff_show` / `ff_t4` — far-flush mid-cycle redirect commit
Lines 774-811 (ST_T4 fast mid-T4 path), `ff_show` 887, `ff_t4` 892, `flush_fast`
input 111.
- WHAT: an EA/BR/far-CALL flush (`flush_fast`) landing on a prefetch T4 commits
  the redirect MID-T4 (target CODE status/address ride that T4 row with QS=E,
  T1 next cycle), one cycle ahead of the near-flush deferred path.
- WHY w0: gated on `evald` (line 774) — at w0 a fetch's completion eval always
  fires at T3->T4 so `evald==1`, preserving the fast commit. Fitted on
  fz8304.
- HOW it breaks: the comment at 782-792 documents the kludge explicitly: under
  waits `evald==0`, so the fast path is bypassed and the redirect "happens to"
  fall to the near-flush do_commit path one cycle later — which the note says
  matches the chip "measured: fz84xxx w1." That is a fitted coincidence, not a
  modeled law: the flush point itself moves under waits (Round 3 Track B found
  the chip flushes ~2 cyc EARLIER under waits, and stretching the branch dly
  regressed arch), so `ff_t4`'s `evald` gate is a w0/w1-alias that is not
  guaranteed at w3+ or across phases.

### KB6. `prefetch_ok` — occupancy + `q_aged` + reservation gate
Lines 252-260 (`infl`, `occupied`, `prefetch_ok`), `q_aged` pipeline 549.
- WHAT: a prefetch commits only if `!(eu_req||eu_hold) && occupied<=4 &&
  q_aged==0`. `occupied` folds `cnt_next` + `infl` (bytes of an in-flight
  fetch not yet pushed). `q_aged` (bytes pushed at the previous edge) blocks a
  commit during the "push-absorb" cycle.
- WHY w0: `occupied<=4` reproduces the measured refill-at-2-free threshold and
  `q_aged` reproduces the boot-loop push-absorb stall — both fitted at w0.
- HOW it breaks: this is the CENTRE of the floor. Round 2 proved the chip's
  "resume now vs 3-idle gap" decision does NOT reduce to `occupied` — the
  queue-FILL case (needs resume at occupied==4) and the steady-state fetch-
  limited case (needs the 3-idle gap) BOTH sit at occupied==4 at the decision
  point. `prefetch_ok` cannot distinguish them because it carries no fill-
  history / bus-grid-phase state. The `q_aged` push-absorb block is a 1-cycle
  fixed stall that is itself a proxy for the grid's push timing.

### KB7. `ph_ff` / `bus_phase` — the 2-cycle grid parity HEURISTIC
Lines 845-851, exported as `bus_phase`.
- WHAT: a 1-bit parity that is T1/T3=0, T2/T4=1, forced to 1 in the committed
  pre-T1 idle slot, and otherwise free-runs (`ph_ff`) through idle cycles.
- WHY w0: explicitly a "zero-wait definition; Tw phases not calibrated" (line
  844) — used by a handful of EU pop-anchored slots (e.g. `op_popm` disp reads,
  BRK vector-pop). Correct at w0 where each bus cycle is exactly 2 grid ticks.
- HOW it breaks: the comment states outright that Tw phases are NOT calibrated.
  Under waits a bus cycle is >2 clocks so this parity no longer tracks the true
  grid phase. This is the single existing signal that GESTURES at the right
  abstraction (grid phase) but is a fake: it is a free-running clock parity,
  not a bus-grid-cycle phase. **The rebuild's central new primitive replaces
  exactly this.**

### KB8. `q_fresh` / `q_head_dry_q` — disp-phase 1-cycle defer
Lines 270-274 (registered `q_avl==0`), consumed by S_DISP8/S_DHI in EU.
- WHAT: a 1-cycle "head byte became poppable this cycle" flag used to defer the
  final-displacement pop by one cycle when it coincides with an in-flight
  fetch's T2 (the "Campaign 4 disp-phase law").
- WHY w0: fitted to the disp-reader golden.
- HOW it breaks: a fixed 1-cycle defer keyed on a queue transition, not on the
  grid position of the fetch — another per-context fixed offset (plan §C flags
  the S_DISP8/S_DHI reservation as a premature-under-waits shared-path floor).

### KB9. `push_pend` / `q_aged` / `q_avl` push-to-pop latency pipeline
Lines 246-249, 547-564.
- WHAT: pushes lag the completion eval by one cycle (`push_pend`), become
  poppable one further cycle later (`q_avl` lags `q_cnt`), and `q_aged` marks
  the absorb cycle. Encodes the measured push-to-pop latency.
- WHY w0: these ARE close to real (measured 2-cycle push-to-pop). Mostly
  correct; listed because the latencies are hard-coded relative to the CPU
  edge, not the grid edge, so they inherit the eval-deferral kludge under waits
  (push "follows the eval by one cycle" — line 553 — which means it follows
  `eval_ext` under waits, KB1).

### KB10. `e_wait` / `qs_e` — QS=E flush display deferral law
Lines 283-308, 582-583, `flush_busy_fetch`/`flush_quiet`/`e_wait_show`.
- WHAT: a multi-condition state machine deciding when the QS=E code appears on
  the pins after a flush (busy-fetch, push-absorb, ready-but-unstarted-EU-req
  exceptions, plus the far-flush `ff_show`/`ff_t4` overrides).
- WHY w0 / waits: fitted piecewise at w0 (mission E) and extended at w1/w3
  (mission H "QS=E under waits"). It is display-only (does not gate execution)
  but it is a pure fitted-condition pile-up — 3 named wires with ~8 AND terms —
  standing in for "E shows on the first grid slot the BIU is quiet." Rebuild
  should regenerate it from the grid model, not carry the conditions.

### KB11. Reset-vector 7-cycle EU reservation (mission G)
BIU header lines 36-43; EU `op_srst`/reset flow + `S_RESET`.
- WHAT: after RESET release the EU holds a bus reservation for a fixed 7 cycles
  then flush-redirects to FFFF:0000 through the flush machinery.
- WHY w0: reproduces the measured boot pattern (QS=E at release+7, first fetch
  T1 at release+9) cycle-exact vs the boot capture.
- HOW it breaks: a fixed 7-CPU-cycle count. Boot is only ever measured at w0,
  so this is untested under waits; it is a fixed offset like all the others.

### K-BIU summary
The BIU has NO first-class representation of "which bus-grid slot are we on and
how full is the queue relative to the grid." Instead it has `state` (a T-state
counter) plus ~12 qualifier flags (`evald`, `eval_ext`, `defer_t4`,
`defer_idle`, `eu_soon*`, `ext_ok*`, `ff_*`, `e_wait`, `q_aged`, `ph_ff`,
`tw_any`) that each patch one measured shape. The rebuild replaces this flag
thicket with an explicit grid-phase + occupancy model.

--------------------------------------------------------------------------
## Class K-EU — the EU's fixed-CPU-cycle bus issue

Full inventory in `waits_structural_plan.md` §"Inventory + classification"
(groups A-D). Summary of the kludge categories (line refs into v30_eu.sv):

### KE1. `dly` countdown gaps (reg `dly`, 6-bit) — the pervasive fixed offset
Dozens of `dly <= K` sites (grep: lines 1512, 1898-2064, 2138-2608, ...). Every
`S_WAITX`-driven wait and explicit gap. Three sub-kinds:
- **Bus-facing waits** (retire->prefetch-resume, pre-read/pre-write lead-in,
  S_A4_G1/G2 inter-access gaps, S_PREP_* gaps, ie_dly bus legs, RMW write-ready
  pop+2/pop+4 at 2456/2542): these SHOULD track the bus grid. They are the
  kludges — fixed CPU-cycle counts that the plan marks `[BUSDLY]` (convert via
  `bus_tw`). At w0 they equal the grid; under waits they fire early.
- **Branch/loop resolution** (`S_JWAIT`, `dly<=K; wnext=S_JFLUSH`, lines
  2580-2608): the flush timing. `[BUSDLY]` but HIGH golden risk — Round 3
  Track B proved stretching it regresses cycle AND arch (chip flushes ~2 cyc
  EARLIER under waits, so a symmetric stretch is backwards). This is a fixed
  offset that is WRONG-SIGNED under waits, not merely unstretched.
- **EU-compute burns** (DIVU=28 at 1938, MUL, IDIV, ROL4/4S nibble-serial,
  IE_TAIL 256*len runaway): these are LEGITIMATELY fixed CPU cycles — EU-bound
  ops are wait-insensitive by measurement (biu_model.md exp5). NOT kludges;
  the rebuild must NOT gate them on the grid. The audit flags them so the
  rebuild does not over-convert.

### KE2. `eu_req` reservations keyed on `dly==1` (always_comb per state)
Lines 1116-1346. `S_EA1/S_EA2` (1128-1141), `S_DISP8/S_DHI` (1145-1147),
`S_PUSH_CALC` (1234), PUSHA last S_WAITX (1209), RMW last S_RMWX (via S_RMWX),
`S_JWAIT` dly<=3 cutoff (1249-1251), CD pre-IVT occ threshold (1189-1191).
- WHAT: "lead the request by one cycle" reservations so a competing prefetch
  does not steal the T4/idle slot. Most are w0-neutral no-ops unless a prefetch
  actually competes.
- KLUDGE nature: `dly==1` is "one CPU cycle before S_REQ." Under waits the
  reservation must lead by one BUS cycle, not one CPU cycle, so it either
  under- or over-blocks (plan §C "premature-under-waits reservations"). The
  `S_EA/S_DISP` reader reservations share `S_REQ` with the fitted readers, so
  they are the "narrow-phase shared-path floor" the grind rounds could not
  touch without regressing the reader golden.

### KE3. `eu_done`-keyed multi-access transitions
`S_A4_*` (ADD4S, 243-244), `S_IE_*` (INS/EXT, 241-242), `S_CMPW1/2`/`S_SCASW`
(251), `S_FRETW` (RETF/IRET stack reads, 234), `S_LD_W1/W2`/`S_MHI/MLO`
(237/246), `S_BUSW` (234).
- WHAT: chain the next bus access on `eu_done` (which is the T4 cycle at w0 but
  the cycle-after-T4 under waits, `eval_ext`, KB1).
- KLUDGE nature: because `eu_done` stretches +1 per waited access, any chain
  marched on it drifts +1 per access. Round 1 landed the PUSHA/far-CALL fix
  (march on `eu_wdone`, the zero-wait completion point) but proved re-keying
  ADD4S to `eu_rdone` OVERSHOOTS (the chip's ADD4S laws track the STRETCHED
  eu_done — data-dependent, correctly `eu_done`-keyed). So this category splits:
  spurious-extra-cycle chains want `eu_wdone/eu_rdone`; data-dependent chains
  correctly stay `eu_done`. The current code keys everything on `eu_done`
  because that was correct at w0.

### KE4. `eu_soon` / `eu_soon_ea` / `eu_soon_ivt` plumbing
Lines 140-146, 1141, 1210, 1352-... These EU-side outputs feed KB2/KB3. They
are the "ready in exactly 1 CPU cycle" promises that the BIU's `defer_t4`/
`defer_idle` fixed-offset paths consume. Same fixed-offset kludge, EU side.

### KE5. Primitives already added but INERT / partially used
`eu_wdone` (write zero-wait completion, USED by PUSHA/far-CALL), `eu_rdone`
(read mirror, added but only ADD4S-tested and reverted), `bus_tw` (stretch
tick, added but no `dly` currently gated on it after the Round 3 reverts).
These are the correct-direction primitives; the rebuild keeps/extends them but
they are not the whole answer (Round 3 proved bus_tw alone hits the bidirectional
floor).

--------------------------------------------------------------------------
## What the audit implies for the rebuild (feeds the design doc)

1. The **grid-phase primitive must become first-class** — replace `ph_ff`
   (KB7) with a real bus-grid-cycle phase that is defined for w0 AND w>=1, and
   route the prefetch-resume / eval / reservation decisions off it.
2. The **prefetch-resume decision (KB6/KB1) is the dominant mass** and needs a
   grid-phase + occupancy(+fill-history) model, not the `occupied<=4` +
   `eval_ext(T4+1)` fixed rule. This is the bidirectional floor's root.
3. The **~10 BIU qualifier flags (KB1-KB5, KB10)** collapse into a small
   grid-slot state machine: "at each grid slot, pick {locked-half2, ready-EU,
   prefetch} by grid-phase-aware arbitration; commit at the slot; display
   status/QS from the slot." The fitted A/B/RMW registered-readiness rules
   (KB4) should fall out of "was the request up at the grid slot," not from
   CPU-cycle-count pipelines.
4. The **EU `dly` bus-facing gaps (KE1) and reservations (KE2)** convert to
   grid-cycle counts (`bus_tw`-gated) — but the EU-compute burns must be left
   as fixed CPU cycles. The split is already classified in the plan.
5. The **branch resolution (KE1 branch / KB5)** is wrong-signed under waits and
   is the highest-risk conversion — do it LAST, measure-first with a chip
   flush-point sweep across waits.
6. **BUSLOCK** (new, measured this phase — see biu_model.md §BUSLOCK) is an
   EU-latch overlaid on the grid, deasserting on a grid event (final locked
   write T4). It slots cleanly into the rebuilt arbitration model as a lock
   latch that (a) does NOT gate prefetch and (b) will gate HOLD/RQ-AK
   arbitration (to be implemented). It is a clean second observable that the
   deassertion is grid-keyed, corroborating the grid model.
