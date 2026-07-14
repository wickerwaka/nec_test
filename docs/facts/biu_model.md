# V30 BIU model (Campaign 1 exit artifact)

Behavioral model of the μPD70116 Bus Interface Unit. Every claim is backed
by a measurement on the real chip. Conditions unless stated: max mode,
4 MHz, zero wait states, experiments via `sw/exp_biu.py` (re-runnable,
~10 s each). Date: 2026-07-11/12.

## Prefetch queue geometry (exp 1: queue-limit)

- **Capacity: 6 bytes.** Back-to-back word fetches (4-cycle cadence) until
  reconstructed depth reaches exactly 6, then the bus idles. No fetch was
  ever initiated at depth ≥ 5.
- **Refill threshold: 2 bytes free.** From full, the first pop (6→5) does
  not restart fetching; the second (→4) does, new T1 within ~2 cycles.
  Same rule as the 8086's word-fetch BIU.
- Fetches are words at even addresses (+2 bytes at T4).

## Flush / jump behavior (exp 2 + Campaign 3 mission E, unified law)

Refined against the 4,500-case control-flow tranche (EB/E9/74/75/7C/E2/
E8/C3/C2, all cycle-exact in the RTL core). Exp 2's "flush→T1 in 1
cycle" and the divide-trap traces' E+2 shape are both special cases of:

- **Internal flush X** (queue clear + fetch-pointer redirect) is
  EU-deterministic per instruction: EB/E9 at lastdisp-pop+3, Jcc taken
  at pop+4, DBNZ taken at pop+6, CALL at hi-pop+3 (one cycle before its
  push request), RET/RET-pop at read-done+1, divide trap at the cycle
  after the PS push (raised with the PC push request).
- **Redirect commit**: the redirected prefetch commits at the normal
  evaluation points (T3->T4 edge, end of idle cycle) from the END of X
  onward, plus one flush-only point: the end of a PREFETCH cycle's T4.
  An EU access's T4 is never an eval point, flush or not (RET's E+2
  shape). A pending EU request (CALL push, trap PC push) still wins the
  first slot; the redirect follows it.
- **QS=E pin display**: shows during X itself when the BIU is quiet;
  otherwise it waits for the first cycle with (a) no doomed in-flight
  fetch in T1-T3/TW (a flush during T1-T3 shows at that fetch's T4; a
  flush AT a fetch's T4 shows one later), (b) no queue-push absorb
  (cycle after a fetch T4), and (c) no ready-but-not-yet-started EU
  request (CALL: E waits for the push's status cycle). (c) does not
  apply at X itself: the trap raises flush and PC-push-ready together
  and still shows E at once. Exp 2's "T1 in 1 cycle" was the
  quiet-idle-at-X case.
- A doomed in-flight fetch always completes its bus cycle; its data is
  discarded. This includes fetches that only START their T1 after X
  (committed at an eval just before the flush - Jcc cold variants show
  the doomed T1 mid-resolution).
- **Prefetch-reservation start during branch resolution** (from
  old-stream commits observed inside the window, 500 cases/opcode):
  EB and CALL/RET-pop reserve at their final-pop cycle; E9 at pop+1;
  Jcc/DBNZ at pop+2; RET holds its decode reservation through the
  stack read (plain POP r16 does not).
- **Odd jump target: the first fetch is a single byte at the odd address**
  (upper lane, UBE̅ low, A0=1), then word-aligned fetching resumes.

### Doomed-prefetch generalization (Campaign 5 flush-modeling, waits=0)

Measured with the per-phase chip-vs-TB sweep tools (sw/sweep_loop.py,
sweep_farjmp.py, sweep_swint.py) across the prefetch-phase x queue-fill
grid. These refine the "reservation-start per opcode" bullet above, which
was a golden-phase alias: the golden injects one queue alignment, so a
per-opcode `pop+k` reservation and the true cutoff coincided there but
diverge across phases.

- **Loop family (E0/E1/E2/E3 taken) — the resolution reservation is a
  fixed cutoff, not a per-opcode start.** During the JWAIT resolution
  window the bus is HARD-reserved (no prefetch) only in the last 3 cycles
  before the flush (dly<=3); at dly>=4 the prefetcher runs FREELY. A
  prefetch committed at dly>=4 — whether a fresh idle-start or an in-flight
  fetch's back-to-back successor — survives as the one doomed fetch the
  flush discards; its T4 becomes the redirect commit point. A commit whose
  eval would land at dly<=3 is blocked. Measured cutoff exactly dly=4 free
  / dly=3 blocked for both commit kinds (idle-start: E0 body2 ph3/9/15/21;
  back-to-back: E2 ph2/8/14 free vs ph0/4/10 blocked). Verified 0-divergent
  across E0-E3, bodies 1-2, phases 0-23, and 1020/1020 in-silicon A/B.
  The old per-opcode split (E2 reserved from pop+2/dly=4, E0/E1 had no
  reservation) over-blocked E2 and under-blocked E0/E1 off-phase.
- **Far transfer flush landing on a prefetch T4 — the fast (EA/FF-rm-reg)
  flush commits the redirect MID-T4.** When the doomed fetch completes at
  its T3 and the flush fires at its T4, the fast flush drives the target
  CODE status/address and QS=E on that T4 row and the redirect T1 follows
  the next cycle (ff_t4 in v30_biu). A NEAR flush (E9/Jcc/loop) at a
  prefetch T4 keeps the deferred display (redirect at the following idle
  Ti, one cycle later). The NOP-sled EA sweep never hit a completed-fetch
  T4; exposed by fz8304 (chip-vs-TB DIVERGE@565 -> MATCH).
- **DEFERRED — software INT (CD imm) pre-IVT doomed prefetch — DISCRIMINATOR
  RESOLVED, RTL fit deferred (2026-07-14).** The "3 laws none clean" was a
  false dichotomy: the doomed-prefetch decision is a clean QUEUE-OCCUPANCY
  threshold, not a dly cutoff. Measured sweep_swint intn ph0-15 q_cnt at the
  dly=3 decision: the chip idle-starts the fall-through doomed prefetch only
  when occupancy <= 3; at occ==4 it stays idle. Divergent cells are EXACTLY
  the occ==4 phases (ph4, ph10); all clean phases are occ 1-3 (both prefetch)
  or occ 5 (queue full, neither prefetches). So the CD pre-IVT prefetch
  threshold is occ<=3 - one tighter than the normal prefetch_ok (occ<=4).
  A bare eu_req reservation at (opc==CD && dly==3 && q_occ>=4) - plumbing
  q_cnt to the EU - blocks exactly the occ==4 doomed prefetch and holds
  golden 169000/169000. BUT it only closes the FIRST of two coupled cycles:
  it exposes a residual 1-cycle IVT-read idle-commit (S_TRAP_IVT1 commits E+1
  in the RTL, E+0 on the chip for CD). That IVT-commit law is PER-INTERRUPT-
  TYPE and CONFLICTS on the shared S_WAITX->S_TRAP_IVT1 handoff: NMI commits
  E+1 at a stale idle window (the eu_soon_ivt/q_cnt<=2 fix), but CD commits
  E+0 even at occ==4 (stale). Closing swint fully needs both the occ
  reservation AND a type-gated E+0 IVT commit on the divide-trap-SHARED
  handoff - too high a regression risk for a 2-cell, non-inject-gate residual
  (~0.8%). Left on golden-proven dly<=2. INT3 (CC)/INTO (CE) clean all phases.

### Doomed-prefetch/accept-edge unifying class (Mission-D interrupt siblings)
The two waits=0 interrupt inject residuals reduce to this SAME machinery:
- **fz10175 (NMI):** during the NMI vectoring flush (POP ES sreg-load context)
  the chip issues resume CODE prefetches into the flush before the IVT read
  that the RTL does not model - the doomed-prefetch bus-tail.
- **fz10460 (REP-LODS):** ACCEPT-EDGE ANCHORING - a read already accepted
  before the abort edge COMPLETES (the chip reads the CW=1 element @243f and
  vectors at the REP end, not withdrawing it); then the vectoring tail issues
  several resume prefetches before INTA (doomed-prefetch bus-tail again).
  Measured: REP READ-strings ARE individually interruptible (interrupt_model
  .md) - the RTL LDM loop lacks any abort - but a cycle-exact fit needs the
  accept-edge anchoring + the doomed-prefetch tail.
All three (swint CD, fz10175, fz10460) share the prefetch-during-flush issue
+ accept-edge withdrawal. A unified fit means touching prefetch_ok / the
shared vectoring handoff - the machinery the whole waits=0-7 surface rests
on - for a sub-1% non-inject-gate gain. DEFERRED as a coherent future
campaign; the measured law (occ<=3 doomed-prefetch threshold, accept-edge
completes-if-accepted, per-type IVT commit) is documented here for it.

## Fetch/EU bus arbitration (exp 4: arbitration)

- An EU data access **never preempts an in-flight prefetch**; it wins
  arbitration at the next bus-cycle boundary (gap = 0 after the fetch's T4).
- After an EU access, prefetch resumes after **3 idle cycles** (consistent
  across a MOV [BW],AW stream; steady state 11 cycles/write = 4 MEMW +
  4 CODE + 3 idle, matching the instruction's 11-cycle F-gap).

### Idle-window reg-EA reader commit law (Campaign 5 closure, 2026-07-13)

Measured with sweep_regea.py (mod0 register-indirect / based-indexed EA
readers - MOV/ALU reg,[mem] - and the 8C sreg store that shares the reader
reservation schedule; the +eudbg per-cycle EU/BIU dump). A reg-EA reader's
read becomes ready one cycle after its EA settles (S_EA2 -> S_REQ).

- **When the read becomes ready with an in-flight prefetch present** the
  read commits back-to-back off that fetch's T4 (the eu_soon / defer_t4
  reservation: a fetch-T3 completion eval coinciding with S_EA2 is deferred
  into T4 and the read's T1 follows). Cycle-exact at every non-idle phase.
- **When the whole 2-cycle EA compute falls in a BUS-IDLE window** (no
  in-flight fetch for defer_t4's T4 to land on) the chip still commits the
  read ONE eval earlier - directly in the idle window: the read's address
  strobe rides the S_REQ idle cycle (the cycle its address first settles)
  and its T1 follows the next cycle. It does NOT wait for a fresh idle-end
  do_commit (which would insert a separate display cycle -> +1 late). This
  is the idle-window analogue of the fetch-T4 defer: the eu_soon reservation
  arms an early mid-cycle commit that fires on the next idle cycle when the
  request goes ready (v30_biu defer_idle / eu_soon_ea, gated to the S_EA2
  reg-EA case so the S_WAITX/INT eu_soon is untouched). Systematic: every
  reg-EA reader form reads +1 late at the one idle-landing phase (ph7 on the
  NOP-sled sweep) before the fix; cycle-exact at all phases after
  (sweep_regea --tb 216/216; in-silicon chip-vs-fabric 60/60, d=0 all phases).

### Store-vs-prefetch reservation law (WRITE half, 2026-07-13)

The write-path sibling of the idle-window reader law. When a store request
becomes ready (eu_ready) exactly ONE cycle after a completing prefetch's
T3->T4 eval, the chip must ALREADY hold an eu_req reservation at that eval so
the fresh prefetch (queue has room) does NOT win the T4 slot. Without the
lead reservation the prefetch commits at the fetch T4 and the store is pushed
~4 cycles late (an extra CODE fetch inserted); the chip blocks the prefetch
(fetch T4 goes PASV) and commits the store via the normal idle do_commit ~2
cycles later. This is the same "the reservation must LEAD the request by one
cycle" rule already fitted for PUSH r16 (S_PUSH_CALC), the reg-EA store
(S_EA2), and PUSH imm / C6-C7 (S_AI_*). Two forms lacked it and raced in
fuzz (found fz80200-81199, deterministic per session):
- **PUSHA (0x60)** first stack write: reserve its last S_WAITX cycle (dly==1,
  wnext==S_REQ). PUSHA was absent from the NOP-sled push sweep.
- **mem RMW writes** (NOT/NEG/INC/DEC/shift/ALU-imm/XCHG [mem], via
  S_RMWX->S_WREQ): reserve the last S_RMWX cycle (dly==1). The RMW compute
  cycles held no reservation between the operand read and the write.
Both are bare eu_req (no eu_ready): a no-op unless a prefetch actually
competes at that eval, and the chip always blocks it - so the golden phases
(no competing prefetch) stay bit+cycle-identical. Verified: golden
169000/169000; the 20 PUSHA/RMW reorder seeds cycle-exact; fresh gate
fz82000-82999 997/1000 (residuals = parked-undoc FE, a 4S BCD store, and
1-row status transients - all separate classes).

## Wait-state interaction (exp 5: waits + long-sled follow-up)

- Wait states lengthen bus cycles exactly as configured (4 → 4+N cycles,
  verified N=0..3).
- EU-bound instructions are wait-insensitive: DIVU stays 28 cycles at all
  wait settings.
- Supply-bound streams degrade to the fetch rate: a NOP sled at 3 waits
  retires at a 3/5-cycle alternation (avg 4 cyc/NOP), queue oscillating
  0↔1 bytes. The 6-byte queue smooths short bursts: a ~2-byte/cycle-deficit
  takes >100 cycles to drain from full, so short sequences can hide
  BIU-boundedness (beware median statistics — the 3/5 alternation medians
  to 3).

## Wait states, cycle-level laws (Campaign 3 mission H)

Extracted from 200-case golden tranches per form (B8/8B/89/F7.6/EB/E8)
at waits=1 and waits=3 (tests/v30/v0.1-w1, -w3), RTL core cycle-exact
against all 2,400 cases plus the full zero-wait regression. The harness
inserts N Tw states per bus cycle via READY (armed at T1, sampled at the
end of T3/Tw).

- **Status display**: the bus status stays ACTIVE through T3 and every
  Tw while READY has not yet been sampled high in the cycle; it drops to
  passive from the cycle after the ready-high sample. At zero waits
  READY is already high at the end of T2, so T3 displays passive — the
  familiar law is the degenerate case.
- **Completion-eval deferral**: the commit evaluation at the "T3->T4
  edge" exists only for zero-wait cycles (READY high at two consecutive
  sampling edges). A waited cycle's completion eval instead runs DURING
  the cycle following T4: it evaluates requests live (sees EU requests
  that assert in that very cycle), drives the committed status/address
  mid-cycle (bs_early sample), and the winner's T1 starts at the cycle's
  end. The end of that deferred-eval cycle is NOT an eval point — a
  request that first asserts inside it waits for the next idle-cycle
  end.
- **Mid-cycle qualification**: the deferred eval picks up an EU request
  only if (A) its readiness was registered during T4, or (B) its req
  line was registered during both T4 and the cycle before (an armed
  reservation) with readiness arriving live. A flush raised at the T4
  edge consumes the rule-B slot (CALL's push commits one idle later).
  Prefetch commits qualify unconditionally.
- **Queue push / EU handover defer with the eval**: the push lands one
  cycle after the completion eval (zero waits: end of T4; waited: end of
  the deferred-eval cycle), poppable two cycles after the push edge, and
  eu_done (read data handover, store/RMW retire) shifts identically —
  post-access EU schedules stretch by exactly one cycle per waited
  access.
- **Trap-chain pace (eu_wdone)**: the divide-trap microcode does NOT
  wait for its pushes' stretched completion: it marches on from the
  zero-wait completion point (the cycle after the first T3). Under
  waits the next push request is therefore already ready and registered
  when the current push's deferred eval runs, and commits mid-cycle by
  rule A (measured: at waits=3 the PS push's T1 lands 2 cycles after
  the PSW push's T4; the flush/PC-push raise migrates into the PS
  push's own Tw window). The trap chain also holds a PURE bus
  reservation (blocks prefetch, no request history) across its whole
  IVT-read/push sequence — invisible at zero waits where the queue is
  full by trap time.
- **QS=E under waits**: a doomed fetch counts as busy through its
  (deferred) completion eval — E moves from the doomed fetch's T4 to
  the following cycle; a cleanly completed fetch defers E while its
  queue push is pending; a mid-cycle-committed push shows E during its
  own status cycle (the (c) exception generalizes).

### Wait-state generalization across arbitrary sequences (2026-07-14)

The mission-H laws above were originally FITTED on 6 single forms
(B8/8B/89/F7.6/EB/E8) at only waits=1 and waits=3. They were never
validated on arbitrary multi-instruction sequences or on any other wait
level. This campaign closes that gap and finds the parametric model
holds UNCHANGED — no new wait-state law and no RTL change were needed.

- **The wait knob is a single static config**: `cfg_wait_states`
  (nec_bus.sv, 4-bit) inserts exactly N Tw states in EVERY bus cycle,
  0-15. The Verilator TB mirrors it via `+waits=N` (waits_cfg). There is
  NO per-address / patterned / variable-within-a-program wait mechanism
  anywhere in the harness (nec_bus, tb_v30_core, or serve/v30ctl), so the
  "variable/patterned waits" axis is not measurable on this rig — only a
  uniform N-per-cycle setting.
- **The deterministic chip-vs-TB fuzz gate now threads waits.** The gap
  that made the predecessor believe "the ENTIRE corpus diverges at
  waits>=1" was purely a TOOLING bug: sw/check_seq.py `run_tb()` never
  passed `+waits` to the TB, so the fuzz gate compared a WAITED chip
  against a ZERO-WAIT TB (they skew by ~2 cycles from the first reset-
  vector fetch — the exact "diverge well before the store stub, done
  delta ±1" signature). Threading `waits` into run_tb (and both check_seed
  callers) makes the gate real. There was never an arbitrary-sequence
  wait-state divergence to fit.
- **Result (arbitrary-sequence chip-vs-TB, deterministic ground truth,
  the full strict + flush ext menu):** cycle-exact at EVERY wait level
  tested — waits=1 1000/1000, waits=2 1000/1000, waits=3 1000/1000,
  waits=5 500/500, waits=7 300/300; combined strict+swint/farjmp/loop
  menu waits=1 500/500 and waits=3 500/500; the swint/farjmp/loop flush
  families alone 300/300 at each of waits=0/1/3; documented deferred
  flush seeds fz7207/fz8304 MATCH at waits=0 and waits=1. >6000 waited
  seed-pairs, zero divergence. The ~4063-cycle chip capture is fixed in
  CPU cycles, so at high waits a long program's store-stub done marker
  falls outside the window; the compare still covers the full ~4000-row
  captured window per seed (short programs reach done and match). The
  parametric mission-H model (READY sampling / eval_ext deferral / push +
  eu_done + eu_wdone stretch-by-one-per-waited-access / tw_any) is
  general in N — it was correct all along; only the fuzz gate was blind.
- **Out of scope, unmeasured under waits (per campaign scope):** pin-
  injected INT/NMI recognition/vectoring/INTA timing (`--inject-int`)
  under waits — the interrupt laws were fitted at waits=0, where the gate
  now stands at **498/500 chip-vs-TB** (the two residuals fz10175/fz10460
  are the deferred doomed-prefetch/accept-edge class); left for a dedicated
  interrupt-timing pass. (The "476/500" this note originally cited was the
  first-pass number before the five landed interrupt fits.)
- **RE-VERIFICATION 2026-07-14 — the "all clean" result above is REFUTED
  (measurement error).** A fresh waits>=1 **chip-vs-TB** fuzz gate over
  arbitrary sequences DIVERGES for ~every seed. Root-caused: NOT a wait-
  routing/board issue (the socketed chip waits correctly — direct probe:
  waits=1 => 1 Tw, waits=3 => 3 Tw) and NOT tooling (hw-ab chip-vs-FABRIC,
  both via nec_bus, drifts IDENTICALLY to chip-vs-TB). It is a **real
  accumulating core-vs-chip cycle-cadence drift under waits**: all fetch
  addresses match (execution arch-correct) but the core runs ~1 cycle
  fewer per ~10-20 waited fetches (chip-behind-core = +0/+1/+6/+10 at
  fetch 0/5/50/100, waits=1). So the parametric mission-H model is
  fitted-exact for its 6 forms (golden w1/w3 pass) but does NOT generalize
  to arbitrary streams — this is the ORIGINAL Priority-4 finding, which the
  WAITS campaign wrongly overturned. Fixing it is a Mission-H-scale CORE
  RTL fit + reflash (deferred; touches the shared wait/eval machinery).
  waits=0 unaffected. Full evidence: closure_checkpoint.md "WAITS>=1
  caveat". The parametric model below holds only in N for those fitted
  forms, not across arbitrary sequences.

### WAITS>=1 CADENCE GENERALIZATION campaign (2026-07-14) — measured law + partial fit

Method (Mission-D style, measure-first): captured live-chip waits=1 refs
(fz84000-84119) and waits=3 refs (fz84000-84059) on the strict fuzz menu
(reflash-free, socketed chip = ground truth), rebuilt the Verilator TB per
RTL change, and localized drift per inter-fetch interval (chip_gap vs
tb_gap, EU-state-set context via the +eudbg dump). The accumulating drift
is NOT one bug — it is a CATALOG of per-context cycle miscadences under
waits, several the zero-wait "mid-cycle / immediate commit" laws that the
mission-H deferred-completion-eval rule stretches everywhere EXCEPT these
points. Contexts (summed drift cycles over 20 seeds, w1):

- **Far-transfer flush on a prefetch T4 (flush_fast: EA/BR/far-CALL)** —
  the `ff_t4` mid-T4 redirect commit is the ZERO-WAIT law; under waits the
  chip defers the redirect one cycle (redirect target rides the Ti ad_data,
  T1 one later). **FIXED** (v30_biu `ff_t4` gated on `evald`: at zero waits
  a fetch T4 always has evald==1 so bit-exact; under waits evald==0 falls
  to the near-flush do_commit path). The FIRST drift in every seed (the
  loader's reset-vector + terminal BR, fetch 3). w1 loader now bit-clean.
- **PUSHA (0x60) inter-write chain** — issued each of its 8 stack writes
  from the previous write's `eu_done`; under waits eu_done stretches +1/wait
  so the next write lands late and a prefetch splices between writes (chip:
  8 contiguous MEMW). **FIXED** (v30_eu: march the next write on `eu_wdone`,
  the write's zero-wait completion point - the trap-chain law generalized;
  eu_wdone==eu_done at w0 so golden bit-exact). fz84007 w1.
- **RMW memory write (op80/81 ALU-imm, NOT/NEG/INC/DEC mem, XCHG mem):
  S_RMWX->S_WREQ->S_WBUSW** — GENERALIZED (2026-07-14, commit d339204).
  Full sweep (sweep_rmw.py, read-T1 -> write-T1, ADD word[mem],imm w0-w5):
  chip = **12,14,14,16,18,20** (a w1==w2 quantization). The TB matched
  everywhere except w1 (gave 12): whenever the write-ready coincided with
  the post-read prefetch's T4, the mission-H rule A/B (the S_RMWX lead
  reservation) took the deferred eval 2 cycles early. Mechanism pinned by
  the +eudbg trace: at w1 the write-ready first asserts AT the prefetch T4
  (rdy high only at T4); at w3 it asserts during the prefetch's Tw (ready
  ENTERING T4). LAW: the RMW write takes the deferred (eval_ext) commit
  ONLY if readiness was registered for the two edges ending at T4
  (eu_ready_p1 && eu_ready_p2), else it commits at the next plain idle.
  Implemented via eu_defer_wr (=state S_WREQ, RMW-write-only; the fitted
  88/89 stores use S_REQ) gating a stricter ext_ok_wr in v30_biu. eval_ext
  is waits-only so w0 is untouched; no golden form is an RMW write. Sweep
  now delta-0 chip-vs-TB at w0-w5 for ADD/NEG/INC word; byte NEG exact;
  byte ALU-imm exact at ALL phases for w1 AND w3 (the gate levels) with a
  residual only at even waits>=2 (byte-vs-word phase diff, out of gate
  scope). Context [16,17,18,21,22,33] / [1,7,8,9,33,34,35].
- **Trailing POP/stack read "arbitration" — NOT a distinct bug (verified
  2026-07-14).** Chased as the read-side mirror of the RMW write, but: a
  controlled POP r16 (NOP-runway sweep) matches chip-vs-TB bit-exact at
  w1; and in the fuzz (fz84009) the POP stack-read (03efe) T1 rows match
  chip-vs-TB for its first occurrences - only the LATER one drifts, purely
  from accumulated upstream drift. The "trailing MEMR" the localizer
  flagged is the manifestation of earlier phase-context drift reaching a
  POP region, not a fresh late-request bug. NO reservation fix warranted.
- **Remaining after the 3 fixes: a DIVERSE phase-dependent long tail.**
  Genuine first-divergence contexts across fz84000-84019 w1 are now spread
  (rows 230-681, past the loader): S_WAITX/S_EX retire timing (31/32),
  INS/EXT bitfield reads (S_IE_* 40-48), disp-EA readers (16-19), a couple
  residual RMW phases - each hitting 1-2 seeds, none dominant. No single
  high-value target remains; each needs its own micro-sweep. DEFERRED.
- **Near-jump (E9/Jcc) flush** — mostly CORRECT under waits (clean forward
  jumps match bit-exact at w1: the redirect lands on the normal post-T4 Ti
  commit slot). The histogram's [1,2,6,59,62,63] mass is DEGENERATE cases
  (jmp+0 / target == in-flight doomed-prefetch address) and phase edges,
  not a systematic law. DEFERRED as low-value phase cases.

Result (120-seed cached-chip w1 / 60-seed w3, bad-rows = diff() divergent
rows): w1 mean 1286->864, median 1214->867, net-drift@fetch80 spread
+-30 -> +-10; w3 mean 1025->931. Two contexts generalized (golden
169000/169000 + w1/w3 1200/1200 held, waits=0 fuzz 120/120 clean); RMW
write + trailing-read arbitration characterized with numbers and deferred
(phase-swept laws). The waits>=1 arbitrary-sequence surface is PARTIALLY
closed (drift rate cut, not eliminated); the gate is not yet met.

### EU bus-grid-aware timing campaign — primitives + direction law (2026-07-14)

Structural campaign to close the waits>=1 arbitrary-sequence drift (design:
docs/notes/waits_structural_plan.md). Round 1 landed two BIU primitives and
established the closing-direction law.

- **`eu_rdone`** (v30_biu): read-completion mirror of `eu_wdone`
  (`eu_completing && !cur_wr && ((TW && !tw_any) || (T4 && evald))`).
  == eu_done at w0 (fires at T4 there); one cycle earlier under waits (first
  Tw). Read DATA is NOT available at first Tw — decouple via eu_rd_now.
- **`bus_tw`** (v30_biu): `state==ST_TW`, the wait-cycle stretch tick. Zero
  at w0. Gate a dly `if (!bus_tw) dly<=dly-1` to count BUS cycles (stay on
  the grid) instead of CPU cycles. This is the general closing lever.
- Both proven w0-neutral: full 169000 golden + w1/w3 drift EXACTLY baseline
  with them present-but-inert.

- **DIRECTION LAW (measured this round).** The residual waits>=1 drift is
  core-FASTER-than-chip (core runs fewer cycles). Closing it requires making
  the core SLOWER under waits = STRETCH a fixed dly offset via `bus_tw`. The
  `eu_wdone`/`eu_rdone` strobes move EARLIER (faster) and only help the
  narrow class where the core inserts a SPURIOUS extra bus cycle at eu_done
  (PUSHA / far-CALL push chains, already landed). Applying strobes elsewhere
  overshoots. Verified negative on ADD4S: marching S_A4_SRCW read->read on
  eu_rdone (w1 mean 818->845) and S_A4_WRW write->read on eu_wdone (w3
  923->934) both WORSEN drift — ADD4S's "dst @ srcdone+2 / write @ dstdone+4"
  laws track the STRETCHED eu_done, not a bus-grid-early point. Reverted.
- **Empirical drift-context histogram (localize.py, 60 w1 seeds).** Dominant
  drift is the retire / prefetch-resume / decode cadence shared by every
  instruction: S_FIRST/S_DEC/S_NOP (217), MOV-imm S_IMM_LO/HI (183),
  S_WAITX/S_EX retire (118), branch S_JWAIT (75), disp16 reader
  S_DLO/DGAP/DHI (73). ADD4S is NOT in the top 25 (niche). The dominant mass
  is the bus-grid prefetch-resume law (exp4 "3 idle cycles after an EU
  access") not stretching under waits — a bus_tw/BIU-cadence target, the
  round-2 focus.

## Self-modifying code (exp 6b: smc)

- After `MOV byte [T],imm`, targets **≤2 bytes past the instruction's end
  execute the stale (prefetched) byte; ≥3 bytes past get the new value**
  (this sequence; boundary = fetch-pointer position at write retirement,
  which the captures expose per-case). No queue snooping of writes.

## Instruction timing via saturated-queue F-spacing (exp 3: fspacing)

Method: 16-NOP runway saturates the queue, the target instruction's
F-to-next-F gap is its retirement-to-retirement time. **Validated exactly
against four documented values** — the method has no fixed offset:

| Instruction | Measured | Documented (User's Manual) |
|---|---|---|
| NOP | 3 | 3 ✓ |
| MOV AW,imm16 | 4 | 4 ✓ |
| ADD AW,imm16 | 4 | 4 ✓ |
| INC AW | 2 | 2 ✓ |
| MOV AW,[BW] | **13** | 11 — **+2 undocumented** |
| MOV AW,[BW+IX] | **13** | 11 — flat EA across modes ✓, but +2 |
| MOV AW,[BW+IX+disp8] | **13** | 11 — flat ✓, +2 |
| MOV AW,dmem (A1 direct) | **10** | 10 ✓ (direct form is 3 faster than modrm) |
| MOV [BW],AW | **11** | 9 — +2 |
| DIVU CW (reg16) | **28** | 25 — +3, and **data-independent** (4 operand sets) |
| MULU CW (reg16) | **31** | 29-30 — +1..2 (early "+9 anomaly" was a doc-lookup
error: 21-22 is the reg8 figure; resolved 2026-07-11, see below) |

### MUL/MULU characterization (Campaign 2 mission 1, 2026-07-11)

42 measurements via sw/sweep_timing.py mul (docs/facts/timing_measured.json):

| Form | Measured | Documented | Delta |
|---|---|---|---|
| MULU reg8  | 24 (all 6 operand sets) | 21-22 | +2..3 |
| MULU reg16 | 31 (all 6 operand sets) | 29-30 | +1..2 |
| MULU mem8 [BW] | 34 | 27-28 | **+6** |
| MULU mem16 [BW] even | 41 | 35-36 | **+5** |
| MUL reg8   | 34 / 38 | 33-39 "according to data" | in range |
| MUL reg16  | 41 / 45 | 41-47 | in range |
| MUL mem8   | 44 | 39-45 | in range |
| MUL mem16 even | 51 | 47-53 | in range |
| MUL reg16,reg16,imm8  | 40 / 44 | 28-34 | **+6..+10** |
| MUL reg16,reg16,imm16 | 40 | 36-42 | in range |

- **MULU is fully data-independent** (0x0000..0xFFFF operands, zeros,
  all-ones: identical timing per form).
- **MUL (signed) costs exactly +4 when the operand sign bits differ**,
  zero counting as positive: -1 x -1 is fast (34), -1 x 0 is slow (38),
  +2 x -64 slow, -32768 x 0 slow (45). It is NOT the product's sign —
  a zero product from a negative operand still pays the +4. Consistent
  across reg8/reg16/imm8/imm16 forms (13/13 measurements). Reads as a
  fixed sign-fixup pass keyed on sign(a) XOR sign(b).
- MUL form = matching MULU form + 10 (fast case), uniformly.
- The 3-operand **MUL reg16,reg16,imm8 documentation (28-34) is wrong**
  by +6..+10; the imm16 variant's range (36-42) is consistent with its
  own measurement, which suggests the manual's imm8 row understates by
  a constant.

Interpretation — CONFIRMED AND REFINED by the Campaign 2 sweep of 113
forms (2026-07-11, docs/facts/timing_measured.json, summary table in
measurements.md): the deviations are class-consistent, not per-opcode
noise. No-modrm reg/imm forms hit documentation exactly; modrm reg,reg
pays +1; immediate-with-modrm and unary-group reg forms +2; modrm EA
loads +2, RMW +3..4; shifts-by-1 +4 (6 vs 2!); PUSH R/POP R deviate
+17/-10. Where the silicon is uniform the manual sometimes is not
(store forms all 11 vs documented 9/10/11), and TEST reg,reg (2),
XCH reg,reg (3) and the sreg MOVs (2) are genuinely faster than the
other reg,reg ops (3). The "clock counts include decoding" claim holds
only for the simplest encodings.

## Open items carried to Campaign 2

- ~~MULU discrepancy~~ RESOLVED 2026-07-11 (see MUL/MULU section above):
  doc-lookup error plus the ordinary +1..3 deviation; MULU data-independent,
  signed MUL +4 on differing operand signs.
- Post-flush fetch scheduling with wait states; INTA-cycle anatomy.
- Odd-anchor F-spacing (all exp-3 anchors were even).
- SMC boundary vs instruction sequence (generalize with queue-state data).
