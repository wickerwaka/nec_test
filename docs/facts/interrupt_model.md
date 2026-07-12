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

### Known residuals (documented, not yet modeled)

- **POP PSW + interrupt at its own boundary** (INT.9D, 53/200): the
  tranche splits into two classes - final live PSW = popped value
  (majority, modeled) vs = PRE-pop value (both with IE/BRK cleared; the
  pushed PSW is the popped value in both classes). Identical stimulus
  timing signatures show both classes, so the discriminator is a data
  or deeper-state condition; needs targeted bench sweeps.
- ~~REP STM abort flush slot~~ RESOLVED (closure block): the apparent
  +-1 was the write-accept slot floating beneath a pop-anchored
  first-boundary decision/flush - see "REP abort, FIRST boundary is
  pop-anchored" above. INT.F3AA is 200/200.

## Priority / notes

- NMI latch + INT level both pending: not yet measured (needs a
  two-event scheduler); documented priority is NMI > INT.
- The INT vector byte is supplied by the harness (CFG int_vector); both
  INTA cycles carry it on the data lanes, consumption is from INTA2 (by
  8086-family convention; single-vector harness cannot distinguish).
- evt_fired (STATUS bit 3) must be read before host_reset; the serve
  protocol's RUN reply carries it as a third field.
