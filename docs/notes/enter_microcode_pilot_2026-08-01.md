# ENTER/PREPARE (C8) microcode-refit pilot — 2026-08-01

Second refit pilot (after `docs/notes/ins_microcode_pilot_2026-08-01.md`).
ENTER was chosen as the already-fit opcode with the most complex FSM logic
and the worst bug history: two silicon bugs found late (task #31 nesting
mask efdd0b8; PUSH-BP-drop-under-waits d104673), six `S_PREP_*` states,
fitted `dly` constants, and the `prep_acc`/`w4skip` patch flags in
`hdl/rtl/core/v30_eu.sv`.

**Verdict: GO, stronger than INS.  Every timing event in all 500 retained
C8 goldens is predicted exactly — zero residuals in fit AND frozen
validation slices — by seven global constants plus one grant law derived
from the ROM's 20-row ENTER micro-sequence.**

Runner: `sw/enter_ucode_pilot.py` (offline; reads `tests/v30/v0.1/C8.json.gz`
and `tests/v30/enter_nesting/goldens_waited.json.gz`).

## Mechanism (ROM rows 0260–0273, `docs/V20UC.TXT`)

```
0260 Q->tmpaL  pop dispL          0261 Q->tmpaH  pop dispH, SP-2 -> IND
0262 MEMW SS   issue BP push      0263 BP->OPR  F   stall until accepted
0264 Q->tmpb   pop LEVEL          0265-0269      tests / COUNT loads
026A-026E      copy loop: MEMR at BP-2k, MEMW push   (level-1 iterations)
026F-0270 MEMW frame-pointer push 0271 F  0272 SP -= size, E
```

The `F` at `0263` is the structural fact of interest: the level pop at
`0264` **cannot** precede BP-push acceptance.  The FSM's
PUSH-BP-drop-under-waits bug (task #31) was precisely a hand-coded race
this interlock cannot express; the fix (`prep_acc` gating of `pop_want`)
re-implements the F-stall by hand.

## Laws (all global; frozen on golden cases [0:100], validated [100:500])

```
bp_req   = disphi_pop + 3
lvl_pop  = disphi_pop + 4              (w0; interlock not binding at w0)
walk_req = lvl_pop + 9   (nest>=2: first copy MEMR)
         = lvl_pop + 10  (nest==1: frame MEMW; write issues 1 later)
chain    : every subsequent stack txn T1 = prev stack txn T4 + 1
           (copy pairs, split halves, frame push — no special cases)
retire   : next F pop = last stack T4 + 1        (nest >= 1)
           max(lvl_pop + 5, bp_push.T4 + 1)      (nest == 0)

grant(req, busfree):  slots at busfree+1 and busfree+3, then free-running
      T1 = busfree+1  if req <= busfree+1
           busfree+3  if req <= busfree+3
           req        otherwise
```

## Results

| Event class | fit [0:100] | frozen validate [100:500] |
| --- | ---: | ---: |
| BP push T1        | 100/100 | 400/400 |
| level-pop clock   | 100/100 | 400/400 |
| first walk grant  |  76/76  | 305/305 |
| walk chain T1s    | 431/431 | 1672/1672 |
| retire boundary   | 100/100 | 400/400 |

Coverage: nest 0–255 (random), both split geometries (odd SP doubles every
push; odd BP doubles every copy read), random fsize/contexts.  **Zero
residuals.**  Waited digest tranche (154 records, waits {0,1,2,3,7} +
wrand): push count = nest+1 in 154/154 (the F-interlock property), every
transaction duration = 3+wait in 9,602/9,602.

## Cross-opcode transfer (the mechanism test)

The two-slot-then-free grant law was discovered here, on ENTER.  Applied
retroactively to the INS pilot's R2-issue cells (untouched data, adjusted
one clock for the case250 T4 convention), it improves 782/800 → **796/800**.
The 4 remaining cells sit at odd slots — the stretched-grid phase state
(`biu_rebuild_design.md` B1), BIU-layer.  A law fitted on one opcode
improving a different opcode's untouched dataset is behavior a per-opcode
rail forest cannot exhibit.

## What the FSM needed vs what the march needs

FSM: 6 states (`S_PREP_L/W2/W3A/W3/RDGO/PW2`), fitted `dly` 3/6/6,
`prep_acc` + `w4skip` patch flags, `a4_k`/`a4_cnt` counters, two
silicon-bug fixes, and savestate entries for the patch state.
March: the ROM row sequence + 7 integers + the shared grant law; the
task-#31 bug class is unrepresentable.

## Limits (honest ledger)

- w0-only cycle rows: the F-interlock's *timing* under waits (level pop =
  max(disphi+4, accept+k)) is untested at cycle granularity — the waited
  tranche pins it only structurally (push count).  A waited cycle-row
  capture (w1/w3 C8 tranche) would close it and is a one-session board
  task with existing rig (`sw/char_enter.py`).
- The layout-specific w2 walk/prefetch interleave (metadata `note_33`)
  is not covered by any retained cycle-row data.
- Constants 9/10 (walk issue) are fitted sums of row costs, not derived
  per-row; same status as the INS intercepts.

## Suggested next steps

1. Capture a small waited C8 cycle-row tranche (w1/w3, nest {0,1,3},
   both alignments) to close the interlock timing prospectively.
2. Promote the grant law (two slots then free) to a shared BIU primitive —
   it now has two-opcode support; reconcile with the INS pilot's
   `busfree+2` convention and the B1 grid_phase work.
3. RTL migration decision: INS + ENTER now both have complete march-law
   replacements for their FSM rails; a `v30_eu` micro-march skeleton
   (Q-pop stalls, F-interlock, issue offsets, chain rule) covering these
   two families would retire the two worst rail forests and both task-#31
   patch flags in one structure.
