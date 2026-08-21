# REP termination versus external INT -- directed-cell preregistration

Date: 2026-08-20

This document is committed before first board contact.  The socketed V30 is
the correctness target.  No bitstream is flashed by this experiment.

## 1. Claim under test

At `C_REP`, a completed SCAS/CMPS iteration whose ZF result terminates REPE or
REPNE must retire before a simultaneously pending external INT is serviced.
The interrupt therefore belongs to the next instruction boundary.  A core
which withdraws REP first instead pushes the prefix IP and, after IRET,
restarts the scan after the element which already satisfied the termination
condition.

The existing `INT.F3AA` corpus is not a test of this ordering: REP STOSB uses
`TEST_NONE`, so there is no ZF termination result to race against withdrawal.

## 2. Frozen directed cell

Driver: `sw/rep_int_term_race.py`.

Two arms, 300 one-clock delay positions each, external INT held for 22 clocks:

| arm | bytes | data 0..11 | architectural terminator |
|---|---|---|---|
| REPNE | `F2 AE` | `42 42 42 42 42 41 42 42 42 42 42 42`, AL=`41` | byte 5 matches |
| REPE | `F3 AE` | `41 41 41 41 41 42 41 41 41 41 41 41`, AL=`41` | byte 5 mismatches |

Both start with `CW=12`, `IY=0x2400`, DF=0, IE=1.  Correct retirement is
`IY=0x2406, CW=6`.  The six-byte tail is deliberately the opposite polarity,
so a lost termination decision produces the unambiguous signature
`IY=0x240C, CW=0`.

The external vector runs `INC BP; IRET`.  BP is therefore an independent ISR
count.  The capture also counts INTA address phases and reconstructs the
interrupt-pushed IP from the three stack writes.

## 3. Pre-board baseline prediction

On unmodified `e61f2e0988`, the bare `v30_core` sweep is predicted and already
measured offline to fail exactly 20/600:

- REPNE delays 59..68: `IY=0x240C, CW=0`, pushed `IP=0x0500`;
- REPE delays 59..68: `IY=0x240C, CW=0`, pushed `IP=0x0500`;
- every failure: BP=1 and two INTA cycles;
- delay 58 control: correct final state, prefix IP (`0x0500`);
- delay 69 control: correct final state, next IP (`0x0502`).

The board comparison is frozen to delays 58..69 on both arms: 24 cells.  The
full 600-cell local sweep remains the regression gate.

## 4. Silicon prediction and verdict rules

Primary silicon prediction: zero architectural overruns in all 24 selected
cells.  Every selected cell in which BP=1 must finish at
`IY=0x2406, CW=6`; none may finish at `0x240C/0`.

For cells aligned to the termination race, silicon is predicted to push the
post-instruction PC (`0x0102` in the whole-image board geometry), not the
prefix PC (`0x0100`).  A coordinate shift relative to the backdoor-injected
TB is reported as an instrument/queue-geometry result rather than silently
relabelled; the primary final-state rule is unchanged.

Integrity gates:

- `use_core=False` explicitly on every capture; no fabric A/B and no flash;
- BP is 0 or 1 only; any re-entry is a cell failure;
- a serviced external INT has the same two INTA cycles before and after the
  RTL change; no interrupt may disappear;
- retain every raw 64-bit capture stream, per-cell SHA-256, image SHA-256,
  divider readback, flash-log pin, and the derived row;
- single-writer preflight before capture, divider pinned, then `board_idle`
  and the serve session closed at completion or error.

Silicon refutes the report if any repeatable, structurally valid serviced
cell overruns past byte 5.  A transport error, rig readback mismatch, missing
terminator dump, ISR re-entry, or non-idle closeout is an integrity failure,
not evidence about the CPU.

## 5. RTL change and acceptance gates

The only authorized functional edit is to give the `TEST_Z`/`TEST_CY`
termination outcome priority over the external-INT/TF withdrawal paths in
`hdl/rtl/ucore/v30u_eu_cond.svh:C_REP`.  Count exhaustion keeps its existing
highest priority.  `TEST_NONE` must retain the old withdrawal behavior.

Acceptance:

1. pre-fix bare-core gate: 20/600 with the exact signatures above;
2. socket comparison: zero overruns, integrity gates clean;
3. post-fix bare-core gate: 0/600, with the same serviced-cell and INTA/ISR
   counts as the pre-fix control population;
4. existing `INT.F3AA` silicon corpus remains green;
5. standing lint/save-state gates remain green;
6. Quartus promotion receipt passes before the RTL is considered landable.
