# V30 interrupt / NMI / POLL / HALT model (Campaign 3 block 4, Mission L)

Behavioral model of μPD70116 external-event handling. Every claim is backed
by a measurement on the real chip via the harness pin-event scheduler
(`sw/exp_int.py`, re-runnable; scheduler asserts the pin during capture
cycle `idx(trigger CODE T1) + 2 + delay`). Conditions unless stated: max
mode, 4 MHz, zero wait states, harness INT vector = 0xFF (CFG default).
Date: 2026-07-12. Resolves OPEN_QUESTIONS Q14.

## INT (maskable, level-sensitive)

### Recognition points

- **Sampled once per instruction, at its boundary.** On a saturated NOP
  sled the recognition groups advance in exact 3-cycle (NOP retire)
  steps; on a mixed stream they advance with the actual (fetch-limited)
  retire times. If the pin is high at instruction N's boundary sample,
  instruction N+1 is not executed; the pushed PC is its address.
- A pin assert can be recognized at the boundary **before the first
  anchor instruction** (delay 0 pushes PC = anchor): the boundary sample
  belongs to the retiring instruction, not the following one.
- **IE=0 masks INT completely** (no INTA, stream runs to completion) —
  the pin level is simply ignored at the samples.
- **Recognition-deferring instructions** (their boundary sample is
  skipped; next opportunity is one instruction later):
  - every segment-register load: measured on `MOV SS,AW` AND
    `MOV DS0,AW` (8E) — the V30 shadows ALL sreg loads, not just SS;
  - `EI` (FB): STI-style one-instruction shadow, measured with INT
    already pending — earliest pushed PC is after the *following*
    instruction, which does execute;
  - prefixes: no sample between a prefix and its instruction (26 8B
    recognized only at the whole instruction's end).
- **POP PSW has NO shadow** (measured: recognition at its own boundary
  works, pushed PSW = the freshly popped value).
- Long EU-bound instructions (DIVU, 28cyc) defer to their end — no
  mid-instruction samples.

### REP string interruption

- REP iterations are individually interruptible: the interrupted
  instruction stops after a completed element with **CW decremented and
  IX/IY advanced consistently** for exactly the elements whose bus
  accesses completed.
- **Pushed PC = the FIRST prefix byte** (measured `26 F3 A4`: pushed PC
  is the 26, i.e. the V30 resumes with ALL prefixes — no 8086
  lost-prefix bug).
- Bus-visible resume quirk: on recognition the CPU **flushes the queue
  and issues a CODE fetch at the resume (prefix) address BEFORE the
  INTA sequence** (measured: `CODE @prefix` T1 4 cycles before INTA1
  T1); the fetched bytes are then discarded by the vectoring flush.

### INTA / vectoring anatomy (zero waits)

Measured event schedule, from a NOP-sled recognition (`exp_int anatomy`,
capture cycles 188-247) and reproduced on cold-queue REP cases:

- assert → **INTA1 T1**: minimum 7 (running; alternates 7/8/10 with the
  prefetch-cadence arbitration — INTA commits at bus-cycle boundaries
  like an EU request), constant 8 from HALT (idle bus).
- **INTA cycle**: 4 states, T1 drives NO address (AD float-retains the
  previous value; ALE still fires), the harness/vector byte rides the
  data lanes as a read, UBE_N=0. Status INTA shows from the commit
  (idle) cycle before T1, passive from T3 (normal zero-wait display).
- **INTA2 T1 = INTA1 T1 + 7** (3 idle cycles between; the vector byte is
  architecturally consumed from INTA2; both cycles carry it on this
  harness).
- **IVT low word read T1 = INTA2 T4 + 7** (MEMR at vector*4); **IVT high
  word back-to-back** (T1 = low read's T4 + 1).
- From the IVT reads on, the chain is EXACTLY the divide-trap microcode
  law (v30_eu.sv header):
  - PSW push T1 = IVT-hi T4 + 5 (ready at done+3),
  - PS push T1 = PSW-push T4 + 4 (ready at done+2),
  - queue flush (QS=E) one cycle after the PS push's T4, raised together
    with the PC push request,
  - PC push T1 = PS-push T4 + 3, handler prefetch commits in the PC
    push's own slot (first handler CODE T1 = PC-push T4 + 1).
- **Pushed PSW = pre-recognition value** (IE=1 as loaded); after entry
  the live PSW has **IE=0 and BRK=0** (store-routine dump = 0xF002 from
  0xF202). PS:PC pushed at SP-4/SP-6, SP ends 6 lower.

## NMI (edge-triggered, latched)

- A 2-clock pulse is latched and recognized at the next instruction
  boundary — the pin can be low again long before recognition.
- **Works with IE=0** (measured), same boundary-sampling quantization as
  INT (3-cycle groups on the NOP sled).
- **No INTA cycles.** The sequence goes straight to the IVT: vector-2
  low word read (addr 8) T1 = assert + 13..15 running (min 13), + 14
  from HALT; the IVT-read/push/flush tail is identical to INT/trap.
- Long instructions defer recognition to their end (measured mid-DIVU:
  pushed PC is either before or after the DIV, never inside; register
  state matches — quotient present only when pushed PC is after).

## POLL (instruction 9B, POLL_N pin)

- POLL_N low at execution: POLL retires like a 3-cycle no-op (saturated
  F-gap 3).
- POLL_N high: the instruction waits, **sampling the pin every 5
  clocks**; a release (pin drops) is only seen at the next sample —
  measured release-cycle groups quantize in exact 5s across 45 delays.
- After the sample that sees the pin low, the **next instruction's F pop
  follows 4 cycles later** (gap to next F = 3 + 5k for k missed
  samples).

## HALT (F4)

- **Entry**: after the F pop, the CPU issues one HALT-status
  pseudo-cycle — status BS=HALT with an ALE/T1 that drives the current
  prefetch-pointer address, NO data phase (T2 onward passive) — then the
  bus goes fully idle; the queue freezes (no further prefetch).
- **Wake by INT with IE=1**: INTA1 T1 = assert + 8, constant (idle bus,
  no boundary quantization); then the normal INT chain; pushed PC = the
  instruction after HALT.
- **Wake by NMI**: IVT-2 read T1 = assert + 14; pushed PC = after HALT.
- **Wake by INT with IE=0: the CPU RESUMES at the next instruction
  without vectoring** (no INTA, no pushes — measured: the post-HALT
  stream runs to completion while INT stays asserted and masked). This
  differs from the 8086, which stays halted. Consequence: any test
  image whose store routine parks on HALT will loop back through the
  reset vector if INT is still asserted (observed as a ~693-cycle
  re-run loop in the captures; harmless — analysis uses the first
  pass).

## Cycle-level laws fitted against the golden tranches (Mission M)

Refined from the 15 interrupt-form tranches (200 cases each, both queue
variants) during the RTL fit; each law is verified cycle-exact on the
passing corpus (v30_eu.sv / v30_biu.sv are the executable reference).

- **INT recognition pipeline**: the boundary decision runs during the
  would-pop cycle B of the next instruction and sees the pin level of
  cycle B-3 (latest catching assert = B-3, measured on the delay-swept
  tranches). Recognition consumes one internal decision cycle; the INTA
  request is READY during B+2 and commits at the normal BIU eval points
  (idle-cycle ends and in-flight-fetch T3 edges) - this arbitration
  reproduces the measured 7/8/10 assert-to-INTA1 spread exactly.
- **NMI latch**: set 3 cycles after the pin edge; latest catching edge =
  B-4. The IVT read request is ready during B+7 (IVT T1 = B+9 on a
  quiet bus).
- **NMI IVT-read idle-window early commit** (random-context generalization,
  Mission-D hardware-interrupt fit, chip-vs-TB): the S_TRAP_IVT1 request
  goes ready (eu_req+eu_ready together) with NO eu_soon lead, and the BIU
  displays it +2 (do_commit) on a saturated bus. In a QUEUE-STARVED
  context (q_cnt<=2, so a doomed prefetch ran through the dispatch wait and
  left the bus grid live) with the pre-IVT wait cycle on bus_phase==1, the
  chip instead commits the IVT-read display ONE cycle earlier - directly in
  the idle window (E+0, the reg-EA reader defer_idle analogue). On the
  saturated NOP sled (q_cnt>=5, no doomed prefetch) it stays at E+1, which
  is why the golden tranches never exposed this. Measured cycle-exact on 11
  random-context NMI inject seeds (fz10041 et al.); fitted as eu_soon_ivt
  (v30_eu.sv) arming the BIU defer_idle when q_cnt<=2 (v30_biu.sv). Applies
  ONLY to the NMI running-boundary IVT wait (irq_nmi_ivt), NOT the INT
  INTA2->IVT gap.
- **Recognition-shadow lasts exactly ONE boundary** (RESOLVED, was the
  fetch-limited residual): the sreg-load / far-CALL recognition shadow must
  drop as soon as the NEXT opcode is popped past the shadowed S_FIRST - it
  is a single-boundary skip, NOT tied to the intervening instruction's
  retire. The chip re-enables the boundary sample at the shadowed
  instruction's successor pop, uniformly (saturated AND queue-starved);
  measured chip-vs-TB (fz10066: chip commits INTA at the boundary the RTL
  was still shadowing). The RTL previously cleared shadow only in retire(),
  but several completion paths reach S_FIRST WITHOUT retire() - MOV reg,imm,
  the MOV Sreg fast path, and the far-JMP S_JFLUSH - so a shadow set in one
  of them (or leaked across a far JMP into the anchor) persisted across
  MANY instructions in fetch-limited streams, deferring INT/NMI recognition
  ~2 cyc too long. Fixed by clearing shadow at the S_FIRST opcode pop (the
  block that cycle is combinational so it still holds; the clear is
  registered; a sreg load re-sets shadow at its own later completion). This
  is UNIFORM - the saturated golden sreg-load tranches INT.8ED0/8ED8 stay
  200/200 on the SAME corrected timing (the earlier queue-starved bypass
  attempt regressed them because it fired on the skipped boundary itself).
  Closed 6 of the 11 chip-vs-TB residuals (INT fz10066/10251/10459; NMI
  fz10248/10431/10486). Remaining 5 are a DIFFERENT mechanism (below).
- **Taken-branch recognition boundary = the FLUSH cycle** (RESOLVED, 2
  seeds): the recognition sample after a taken branch is anchored to the
  branch's flush (pin@flush-3), NOT to the fetch-limited target pop.
  Measured on a controlled JMP-short delay sweep (chip vs TB pushedPC):
  recognition maps NOP@500 -> NOP@501 -> JMP@502 -> [3-delay GAP, the flush,
  INT dropped, no latch] -> target@50A, and the chip's target window opens
  one delay EARLIER than a pop-anchored boundary. The RTL sampled int_p[2]
  (pin@pop-3) at the first post-flush S_FIRST and so recognized 1 cyc late
  (missing the pin in fetch-limited streams). Fixed with a 1-cycle post_flush
  pulse (the S_FIRST after S_JFLUSH) that taps int_p[3]/ie_p[3] (= pin/IE at
  flush-3). Golden 169000/169000 held; closed fz10117 (JMP-short), fz10283
  (Jcc). Controlled sweep now chip==TB at every delay incl the 3-delay gap.
- **8C sreg-STORE shadows recognition too** (RESOLVED, 1 seed): the 8C MOV
  r/m,Sreg store defers the INT sample by one boundary EXACTLY like the 8E
  sreg load - measured on controlled pushedPC sweeps for BOTH the reg form
  (8C DB) and the mem form (8C 1E: 0505/0507 boundary skipped). The RTL set
  shadow only on the load path; op_srst (store) did not, so the TB
  recognized one boundary early (opposite sign to the fetch-limited class).
  Fixed: op_srst sets shadow at its reg-form completion AND its mem-store
  completion (S_WBUSW). Golden 169000/169000 held; closed fz10317.
- **Remaining recognition-point residuals (OPEN, 2 seeds, chip-vs-TB, two
  DISTINCT mechanisms)**: fz10460 REP/string abort (LODSB - irq_take gated by
  rep_en, the abort element-count differs by one); fz10175 NMI. Each a
  separate fit; not yet done.
- **IE gating is itself pipelined**: the decision at B uses IE@B-3.
  This single law IS the "EI shadow" AND explains POP PSW's behavior on
  an IE 0->1 transition (the immediately following boundary still sees
  IE=0). There is no separate EI shadow flag in the silicon model.
- **EI/DI commit IE when the NEXT opcode byte is present in the queue**:
  at their pop edge if a byte remains after the pop, else at the queue
  refill (measured on dry-queue EI: the new IE appears in the PS pins
  only after the next byte is fetched).
- **POP PSW consumes the popped image at its read's data edge** (the
  new IE shows in the PS bits during the read's own T4).
- **HALT display law**: HALT never enters the bus-commit machinery. The
  HALT status appears at the first idle (Ti, nothing committed) cycle
  after the opcode pop, followed by one address-strobe T1 that drives
  the LAST FETCH address (fetch pointer - 2) on AD15:0 only, releasing
  UBE_N high; no data phase. Prefetch is blocked from the decode cycle.
- **HALT wake**: INT(IE=1): INTA request ready at assert+6, commits at
  the eval points (idle bus: INTA1 T1 = assert+8; a cold queue lets one
  prefetch commit first and the INTA rides its T3 eval). NMI: bus held,
  IVT request ready at assert+12 (T1 = assert+14). Masked-INT resume:
  prefetch resumes at the decision cycle (assert+3), the next
  instruction pops one cycle later.
- **INTA cycle drive**: no address is driven - AD15:0 float through the
  commit display and T1; AD19:16 are driven to 0 during both; PS bits
  (IE, seg=CS) drive T2-T4 as usual; UBE_N low.
- **REP abort**: iteration boundaries sample a one-deeper pin pipeline
  (pin@edge-4); on recognition the in-flight write completes, the
  internal flush fires 9 cycles after the abort decision edge, the
  resume refetch T1 follows the flush display by 2, and INTA1 T1 by 6.
- **REP abort, FIRST boundary is pop-anchored** (closure block, fitted
  on all 56 INT.F3AA abort cases): the boundary-1 decision edge sits at
  a fixed opcode-pop+7 (sampling pin@pop+3 per the edge-4 tap), and its
  flush is invariant at pop+16 = edge+9 - the first write's commit slot
  floats +-1 beneath both without moving them. A write already accepted
  before the edge still completes; a next-iteration write issued but
  not yet committed at the edge is withdrawn (no bus activity). Chained
  boundaries (>= 2) are write-accept-anchored: decision at the accept
  edge, flush at accept+9, as before.

### Known residuals

None. Both block-4 residuals are resolved (closure block); the whole
interrupt corpus is cycle- and state-exact.

- ~~REP STM abort flush slot~~ RESOLVED: the apparent +-1 was the
  write-accept slot floating beneath a pop-anchored first-boundary
  decision/flush - see "REP abort, FIRST boundary is pop-anchored"
  above. INT.F3AA is 200/200.
- ~~POP PSW boundary race~~ RESOLVED: see the section below.

### POP PSW boundary race (closure block: RESOLVED, exhaustively measured)

- When INT recognition lands on POP PSW's own boundary (or one NOP
  later - same law, 7/7 tranche late races) with **pre-pop IE=1**, the
  final LIVE PSW is either the popped image (class A) or the PRE-pop
  image (class B), IE/BRK cleared either way; the pushed PSW is the
  popped image in both classes, pushed PC = IP+1 (POP retires fully
  either way).
- The class is **deterministic in the two flag words' data** and
  nothing else: single-bit flips of pre.DIR / pre.P / pop.S flip the
  class at bit-identical bus timing; register values are inert (bench
  factorial + 21/21 repeatability check).
- The law resists compact algebra: not GF(2)-linear or quadratic, no
  <=4-variable dependence, no masked compare/carry predicate fits; the
  ANF of the full table has ~2000 terms up to degree 13 and the
  function is asymmetric in (pre, pop). Implemented as the
  exhaustively measured 2^14 truth table over {V,DIR,S,Z,AC,P,CY} of
  both words (hdl/rtl/core/int9d_race.hex; provenance
  docs/facts/int9d_race_table.json.gz; one board run per cell at the
  d=5 own-boundary geometry, corrupted cells re-measured).
- pre-IE=0 pops never race (recognition waits for the popped IE;
  89/89 class A in the tranche).
- **Ghost pending INT** (224 table cells at specific pop patterns,
  e.g. pop {Z,S,DIR,V}): the entry ALSO fails to clear the internal
  INT-pending latch. Architectural state = class A (verified on the
  bus: normal pushes, store-routine PSW capture = pop & ~(IE|BRK)),
  but any later IE=1 re-dispatches a spurious INTA with the pin long
  released, and HALT falls through via the masked-INT resume path.
  Out of scope for the golden windows (they close at handler entry);
  flagged for Campaign 4 A/B runs. The ghost is also why 3 tranche
  finals (INT.9D idx 45/94, INT.FB idx 55) carried corrupted
  extractions: the run loops through the loader and the last
  scratch-page write is no longer the PSW capture. All three patched
  from the measured table/law.

## Priority / notes

- NMI latch + INT level both pending: not yet measured (needs a
  two-event scheduler); documented priority is NMI > INT.
- The INT vector byte is supplied by the harness (CFG int_vector); both
  INTA cycles carry it on the data lanes, consumption is from INTA2 (by
  8086-family convention; single-vector harness cannot distinguish).
- evt_fired (STATUS bit 3) must be read before host_reset; the serve
  protocol's RUN reply carries it as a third field.
