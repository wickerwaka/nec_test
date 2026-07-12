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
| MULU CW (reg16) | **31** | 21-22 — **+9?** needs dedicated follow-up |

Interpretation (working hypothesis): the manual's claim that clock counts
"include decoding" holds for register/immediate forms but understates
modrm/memory forms by ~2 cycles and MULU/DIVU by more — exactly the
decode/EA gap this project exists to measure. Campaign 2 sweeps this per
opcode.

## Open items carried to Campaign 2

- MULU discrepancy (31 vs 21-22): verify against operand values, byte
  forms, and the mem variants; check the manual's per-case notes.
- Post-flush fetch scheduling with wait states; INTA-cycle anatomy.
- Odd-anchor F-spacing (all exp-3 anchors were even).
- SMC boundary vs instruction sequence (generalize with queue-state data).
