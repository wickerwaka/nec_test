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

## Flush / jump behavior (exp 2: flush)

- Queue flush (QS=E) → next fetch **T1 in 1 cycle**, both target parities.
- Flush → first byte of the target consumed (QS=F): **6 cycles**, both
  parities (= 1 + 4-cycle fetch + 1).
- **Odd jump target: the first fetch is a single byte at the odd address**
  (upper lane, UBE̅ low, A0=1), then word-aligned fetching resumes.

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

Interpretation (working hypothesis): the manual's claim that clock counts
"include decoding" holds for register/immediate forms but understates
modrm/memory forms by ~2 cycles and MULU/DIVU by more — exactly the
decode/EA gap this project exists to measure. Campaign 2 sweeps this per
opcode.

## Open items carried to Campaign 2

- ~~MULU discrepancy~~ RESOLVED 2026-07-11 (see MUL/MULU section above):
  doc-lookup error plus the ordinary +1..3 deviation; MULU data-independent,
  signed MUL +4 on differing operand signs.
- Post-flush fetch scheduling with wait states; INTA-cycle anatomy.
- Odd-anchor F-spacing (all exp-3 anchors were even).
- SMC boundary vs instruction sequence (generalize with queue-state data).
