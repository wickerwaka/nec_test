# RESULTS — THE `IRET`-SETTER TF BOUNDARY DIRECTED BOARD CELL

**`tf0f` §5.2 is CLOSED, and the answer is that the question had a false
presupposition.  There is no position for the second boundary to sit at,
because the second boundary is a SAMPLE and not a TAKE POINT: silicon takes the
`TF` trap at instruction RETIRES ONLY and never pushes a mid-instruction return
address.  `KM`'s count law is VALIDATED on a setter it was not derived on;
`KM`'s own INTERPRETATION — "the second boundary is at the opcode byte" — is
REFUTED as a statement about where the trap lands.**

| | |
|---|---|
| pre-registration | `docs/notes/iret_tf_cell_prereg_2026-08-11.md`, commit **`53242e3865`**, before the first board contact |
| tool | `sw/iret_tf_cell.py` |
| artifacts | `sw/testdata/iret-tf/` (`board/`, `core/`, `predictions.json`, `calib.json`, `score_der.json`, `qs.json`, `SHA256SUMS` per directory) |
| tree | `fuzz-v2-on-relanding`, `292d898837` → `53242e3865` |
| board | **FLASH #17** (`.sof` `26c19f613e2caae8…`), socket only, `flash_log.jsonl` **20 entries before and after** |
| engine leg | `tb_sys ret`, rebuilt on this tree at the `KM` landing, receipt `63308b10ac00a812…` |

---

## 1. THE HEADLINE, IN ONE PARAGRAPH

The `TF` trap is taken at an instruction **RETIRE** and at nothing else.  A
prefix hand-over and an `0F` escape's re-decode are **sample** events — they
decide *which* boundary pop arms the trap — and neither is ever a place the trap
can land.  The whole 20-rule pre-registered product collapses to **one** rule
that clears the bar, `S1.*.B0`, at **49 of 49 derivation legs**, and the chip
and the ucore give **identical answers on all 832 cells, in every scored
column**.  The one genuinely new fact is the setter adjacency: **the `IRET`
setter arms on the FIRST boundary pop after it and `popf` arms on the SECOND**,
which is one instruction per trap — a single step — and which needs no new
mechanism, only §86.B's existing 4-clock floor applied to a rise that sits many
clocks further back.

---

## 2. WHAT WAS RUN

One board leg, socket-only (`use_core=False`, explicit), on FLASH #17.

| | derivation |
|---|---|
| legs | 52 (49 scored + 3 null) |
| cells (leg × waits 0-3 × align 0-3) | **832** |
| scored traps | **4,704** per engine (49 legs × 96) |
| wall clock | board **35 s**, `tb_sys ret` 244 s |
| transport errors | **0** |
| `div_guard` | **54 boundaries, all PINNED**, 0 UNPINNED |
| structurally invalid cells | **0 of 832** |

Stability: **104 of 832 cells (12.5 %) captured ×3** — **0 TAKE-unstable** and
**0 stream-distinct**, i.e. the full 64-bit word streams were byte-identical
across repeats as well.  Every leg is single-valued across all 16 of its cells
and all 6 of its traps, on both engines: 96 traps, one number, 49 times.

---

## 3. THE MEASURED COLUMN

`pushed_off` = pushed return address − block base.  `f` is the filler.

| leg | bytes | f | **chip** | core | Δ |
|---|---|---:|---:|---:|---:|
| `P1_nop` | `90` | 1 | 6 | 6 | 0 |
| `I0_nop` | `90` | 0 | **3** | 3 | 0 |
| `I1_nop` | `90` | 1 | **3** | 3 | 0 |
| `P1_addrr` | `01d8` | 1 | 7 | 7 | 0 |
| `I0_addrr` | `01d8` | 0 | **4** | 4 | 0 |
| `I1_addrr` | `01d8` | 1 | 3 | 3 | 0 |
| `P1_movi` | `b83412` | 1 | 8 | 8 | 0 |
| `I0_movi` | `b83412` | 0 | **5** | 5 | 0 |
| `I1_movi` | `b83412` | 1 | 3 | 3 | 0 |
| `P1_pfx1` | `2e01d8` | 1 | **8** | 8 | 0 |
| `I0_pfx1` | `2e01d8` | 0 | **5** | 5 | 0 |
| `I1_pfx1` | `2e01d8` | 1 | 3 | 3 | 0 |
| `P1_pfx2` | `2e3e01d8` | 1 | **9** | 9 | 0 |
| `I0_pfx2` | `2e3e01d8` | 0 | **6** | 6 | 0 |
| `I1_pfx2` | `2e3e01d8` | 1 | 3 | 3 | 0 |
| `P1_pfx3` | `2e3e2601d8` | 1 | **10** | 10 | 0 |
| `I0_pfx3` | `2e3e2601d8` | 0 | **7** | 7 | 0 |
| `I1_pfx3` | `2e3e2601d8` | 1 | 3 | 3 | 0 |
| `P1_pfx4` | `2e3e263601d8` | 1 | **11** | 11 | 0 |
| `I0_pfx4` | `2e3e263601d8` | 0 | **8** | 8 | 0 |
| `I1_pfx4` | `2e3e263601d8` | 1 | 3 | 3 | 0 |
| `P1_x1b` | `0f1be84f` | 1 | **9** | 9 | 0 |
| `I0_x1b` | `0f1be84f` | 0 | **6** | 6 | 0 |
| `I1_x1b` | `0f1be84f` | 1 | 3 | 3 | 0 |
| `P1_x13` | `0f13c0` | 1 | **8** | 8 | 0 |
| `I0_x13` | `0f13c0` | 0 | **5** | 5 | 0 |
| `I1_x13` | `0f13c0` | 1 | 3 | 3 | 0 |
| `P1_z1b` | `2e0f1be84f` | 1 | **10** | 10 | 0 |
| `I0_z1b` | `2e0f1be84f` | 0 | **7** | 7 | 0 |
| `I1_z1b` | `2e0f1be84f` | 1 | 3 | 3 | 0 |
| `P1_p2x` | `2e3e0f1be84f` | 1 | **11** | 11 | 0 |
| `I0_p2x` | `2e3e0f1be84f` | 0 | **8** | 8 | 0 |
| `I1_p2x` | `2e3e0f1be84f` | 1 | 3 | 3 | 0 |
| `P1_p4x` | `2e3e26360f1be84f` | 1 | **13** | 13 | 0 |
| `I0_p4x` | `2e3e26360f1be84f` | 0 | **10** | 10 | 0 |
| `I1_p4x` | `2e3e26360f1be84f` | 1 | 3 | 3 | 0 |
| `P0_*` | `nop addrr pfx2 pfx4 x1b z1b` | 0 | 6 · 7 · 8 · 10 · 8 · 9 | same | 0 |
| `P2_*` | `nop pfx4 z1b p4x` | 2 | 6 · 6 · 6 · 6 | same | 0 |
| `RP_*` | `nop x1b z1b` (tf0f's own images) | 0 | 6 · 8 · 9 | same | 0 |

**`176 of 832` cells differ chip-vs-core: zero.  Every scored column — entry
count, `pushed_off`, its set, the prefetch high-water mark, uniformity,
termination — is 0 / 832.**

The bolded rows are the ones that carry the answer: every one of them is
`probe_start + probe_length`, the retire.  **Not one of the deep legs pushes a
mid-instruction address.**  `P1_p4x` is the sharpest single row in the cell:
the four hand-over rules put the trap at 6, 9 or 10 and it reads **13**.

---

## 4. THE VERDICTS ON THE PRE-REGISTERED PRODUCT

Reported as registered, not restated.  20 composite rules, scored on 49 legs.

| rule | says | chip | core |
|---|---|---:|---:|
| **`S1.PA.B0`** | **IRET arms on the first pop; takes at RETIRES ONLY** | **49/49** | **49/49** |
| **`S1.Pall.B0`** | the same — `PA` and `Pall` are indistinguishable under `B0` | **49/49** | **49/49** |
| `S1.PA.Bnp` | …and also at the prefix stack's hand-over | 35/49 | 35/49 |
| `S2.PA.B0` | IRET arms on the SECOND pop, as `popf` does | 34/49 | 34/49 |
| `S2.Pall.B0` | " | 34/49 | 34/49 |
| `S1.Pall.Bnp` | | 33/49 | 33/49 |
| `S1.PA.B1` · `S1.PA.Bd` · `S1.PA.Ball` · `S1.Pall.B1` | | 31/49 | 31/49 |
| `S1.Pall.Bd` · `S1.Pall.Ball` · `S2.PA.Bnp` | | 27/49 | 27/49 |
| `S2.PA.B1` · `S2.PA.Bd` · `S2.PA.Ball` · `S2.Pall.B1` | | 25/49 | 25/49 |
| `S2.Pall.Bnp` | | 20/49 | 20/49 |
| `S2.Pall.Bd` · `S2.Pall.Ball` | | 15/49 | 15/49 |

**The §5.3 bar is MET by exactly one registered rule** (up to the `PA`/`Pall`
degeneracy that `B0` induces and which no observable in this cell can lift —
§8).  No replacement was needed, so **no erratum arises and the standing
"validate a replacement on disjoint data" rule is not triggered**; the disjoint
validation population registered in §7 of the pre-registration is nevertheless
captured, because it was registered, and is reported in §7 below.

### 4.1 The control clauses

* **I-4 THE NULL — PASS.**  `N_p1_z1b`, `N_i0_z1b`, `N_i0_p4x`: 48 cells,
  **0 vector-1 entries**.  With `TF` clear the identical geometry — including
  the `BRK 4` / handler / `IRET` path itself — traps not at all, so nothing in
  the setter machinery is generating the entries being counted.
* **I-4b THE INSTRUMENT CONTROL — PASS.**  The three `RP_*` legs are `tf0f`'s
  own images, asserted **byte-identical** (12 of 12), and reproduce its
  published chip column exactly: **6 · 8 · 9**.  A second rig measuring the same
  silicon a day later gets the same three numbers.
* **I-1** single writer OK · **I-2** socket only, `EMIT_USE_CORE is False`
  asserted at import · **I-3** flash pin **20 entries** before and after, board
  on FLASH #17 throughout · **I-5** 0 invalid cells of 832 · **I-6** 54
  `div_guard` boundaries, **all PINNED**, 0 UNPINNED · **I-7** **0** transport
  errors, 0 `RigMismatch` · **I-8** 12.5 % ×3, **0** TAKE-unstable, **0**
  stream-distinct · **I-9** full per-clock words retained, `SHA256SUMS` over
  both directories (210 files each) · **I-10** below.

---

## 5. THE MEASURED LAW

> **KR — SILICON.**  The `TF` trap is taken at an instruction **RETIRE** and at
> nothing else.  A prefix hand-over and an `0F` escape's re-decode are
> **SAMPLE** events only.
>
> **KS — SILICON, the setter adjacency.**  Counting boundary pops from the
> first one after the setter: a `popf` setter arms on the **SECOND**; an `IRET`
> setter arms on the **FIRST**.
>
> **KM stands, and is now validated on a second setter.**  An instruction
> contributes ONE boundary unit plus ONE MORE iff its opcode byte is not its
> first byte — that is `KM` — and this cell adds that the extra unit is a
> *sample*, so it changes *which pop arms* and never *where the trap lands*.

### 5.1 `KS` needs no new mechanism — it is §86.B's existing floor

§86.B measures the arm's floor at **4 clocks** from the `TF` rise.  With
`push imm16 ; popf` the rise is the `popf`'s own flag write, one to two clocks
before its retire, so the very next boundary pop is inside the floor and is
lost — which is exactly why `tf0f`'s `nop` reads 6 and not 5.  With an `IRET`
the flag load is followed by the target computation, the **queue flush** and a
full refetch before any successor pop can happen, so the first pop is already
clear of the floor.  **One constant, already in the RTL, explains both setters.**
Nothing here asks for a second term, a table or a per-setter case.

### 5.2 What §5.2 of the `tf0f` results was really asking

It asked *"where does the second unit sit?"* on the assumption that a unit is a
place a trap can land.  It is not.  The second unit is a pop the arm samples on,
and the arm can only ever be discharged at a retire.  Under that reading the two
readings §5.2 could not separate — *"the extra unit is consumed BEFORE the
opcode pop"* and *"AFTER"* — are **not distinguishable by any trap-position
observable at all**, and this cell proves it constructively rather than by
failing to find a difference: it moved the arm one pop earlier, put four
distinct candidate hand-over positions in front of it, and **all four are
empty**.

---

## 6. THE QS-PIN CONTROL — THE FRONT ENDS ARE IDENTICAL

`sw/iret_tf_cell.py qs`, pins only, no engine in the comparison: the chip and
the core emit the **same `QS` stream from the anchor to the first vector-1
entry** on **832 of 832 cells, every leg including the nulls, 0 differ**.  So
the agreement in §3 is not two different front ends arriving at the same answer
by luck; the stream is the same and the thing that consumes it now agrees too.

This also re-states, on a second and larger population, `tf0f` §6's
engine-free refutation of §86's *prose*: `pfx4` announces five `QS = 1` pops and
contributes two boundary units, and a bare `0F`'s opcode is announced
SUBSEQUENT yet is a boundary — the pins are not the boundary count, in either
direction, on either engine.  Nothing in this cell disturbs `q_bnd_pop`, which
is the predicate `KM` landed.

---

## 7. THE DISJOINT VALIDATION POPULATION

Registered in the pre-registration §7 before any board contact, captured after
the derivation verdict was committed.  Seven probes whose bytes appear nowhere
in the derivation set, on the two discriminating geometries, plus its own null.

*(Filled in by the validation leg — see §7.1.)*

---

## 8. WHAT THIS CELL DOES **NOT** RESOLVE — as registered

* **`PA` vs `Pall` is not separable here, and it was declared not separable
  before the run** (pre-registration §8, first bullet).  Under `B0` the sample
  set only matters through *which pop is the N-th*, and every leg in this cell
  has its arming pop either on a filler NOP or on the probe's first byte, so a
  sample at the second decoration byte is unobservable.  **The verdict is `B0`,
  with that caveat attached**, and the ucore's `q_bnd_pop` (a `Pall`-shaped
  predicate) is neither confirmed nor refuted as a *sample set* by this cell —
  only its *consequences for the take* are, and they match.
* It says nothing about 8080/BRKEM, and no probe is a BRKEM alias.
* No head-to-head figure is computed.  Both columns are scored against silicon,
  which is the chip column itself.

---

## 9. THE RTL CANDIDATE, AND WHY THERE ISN'T ONE

**There is no landing to book.**  The ucore reproduces silicon on 832 of 832
cells and 4,704 of 4,704 traps, and the unique surviving law is the one it
already implements: `bnd_armed` is set only at a retire (`v30u_eu.sv:1932`), and
the `IRET`/`popf` asymmetry falls out of the `BRK_FLOOR` pipeline that is
already there.  **A cell that finds the mechanism already complete is a
VALIDATION, and it is stated plainly as one.**

Two things it does buy, both cheap and both real:

1. **`KM` is now validated on a disjoint SETTER**, not only on a disjoint probe
   population.  Its landing (`e57c3b4d12`) was scored entirely on `popf`-set
   traps; the 24 `I0`/`I1` legs here are `IRET`-set and it holds on all of them.
2. **`ucore_provenance.md` §86's remaining prose can be corrected against
   measurement rather than argument** — the sampling boundary is not a place the
   trap lands, and the `IRET` asymmetry is now a measured constant of the same
   floor rather than an unexamined asymmetry (§86.C's "W-3 asymmetry" is
   answered: it is `KS`).

**Falsifier for `KR`.**  Any capture in which a `TF` trap pushes a return
address that is not an instruction start — in particular any capture in which a
decorated instruction with `PSW.TF` set pushes its own opcode byte, its `0F`
byte, or any interior byte.  832 cells and 4,704 traps here contain none.

**Falsifier for `KS`.**  Any capture in which an `IRET`-set `TF` trap skips the
first instruction after the `IRET`, or a `popf`-set one does not.

---

## 10. PREDICTED SEAT REACH — HONEST, AND SMALL

* **P-1 — ZERO seats.**  No RTL changed and none is proposed, so no banked seat
  can move.  This is not a hedge: it is the arithmetic of a validation.
* **P-2 — the TF-family residue is UNAFFECTED and the `tf0f` §9 reach stands
  unchanged.**  The corpus has 101 `PSW.TF` seeds; `tf0f` P-3 registered the
  honest reach of the `KM` mechanism at **2–3 seeds** and registered *"any claim
  of a two-digit seat gain from this mechanism is registered IN ADVANCE as
  unsupported"*.  Nothing here raises it.  What this cell removes is a
  **hypothesis** that would have justified further RTL work on the take path:
  had `Bd` been the law, the `KM` landing would have been placing a boundary in
  the wrong place and every prefixed-`0F` seat would have been suspect.  It
  isn't, and they aren't.
* **P-3 — the one live lead this closes off.**  `fz2c/404041`'s core leg was
  known to retire a further far `CALL` after the displaced boundary and to
  re-align only 2/342 (`tf0f` §9 P-1).  A take-position defect was the obvious
  candidate explanation and it is now **excluded**: on this population the two
  engines' take positions are identical at every filler and both setters.  That
  seat's residue is elsewhere.

---

## 11. WHAT THIS SITTING DID NOT DO

* **No RTL was edited.**  `hdl/` is byte-identical to `292d898837`.
* **No bitstream was built and none was flashed**; `flash_log.jsonl` is **20
  entries** before and after, and the board carries FLASH #17 throughout.
* No rule outside the registered product was derived from the measured column.
  The winner was pre-registered; nothing was fitted; no erratum arose.
* `sm3_tf_floor_cell` was not repaired or re-anchored.
