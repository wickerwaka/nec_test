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
- **DEFERRED — software INT (CD imm) pre-IVT doomed prefetch.** The BRK-imm
  vector wait is NOT a clean dly cutoff: the chip idle-starts a doomed
  prefetch at dly=3 when the queue has room (fz73013) but stays idle at
  dly=3 when it is full (sweep ph4), i.e. it is queue-state-dependent, and
  a residual 1-cycle IVT-read idle-commit timing rides the shared
  S_WAITX->S_TRAP_IVT1 handoff (also the divide-trap path). Three candidate
  laws (dly<=2 / dly<=3 / free) were measured; none is clean. Left on the
  golden-proven dly<=2 (~0.8% chip-vs-TB residual). INT3 (CC) and INTO (CE)
  are clean at all phases.

## Fetch/EU bus arbitration (exp 4: arbitration)

- An EU data access **never preempts an in-flight prefetch**; it wins
  arbitration at the next bus-cycle boundary (gap = 0 after the fetch's T4).
- After an EU access, prefetch resumes after **3 idle cycles** (consistent
  across a MOV [BW],AW stream; steady state 11 cycles/write = 4 MEMW +
  4 CODE + 3 idle, matching the instruction's 11-cycle F-gap).

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
