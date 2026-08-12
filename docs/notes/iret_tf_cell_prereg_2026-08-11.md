# PRE-REGISTRATION — THE `IRET`-SETTER TF BOUNDARY DIRECTED BOARD CELL

**Committed before the first board contact.  Nothing below may be edited after
the board is touched; corrections go in an erratum, as `tf0f` A-1 did.**

| | |
|---|---|
| tool | `sw/iret_tf_cell.py` |
| tree | `fuzz-v2-on-relanding`, `292d898837` |
| board | **FLASH #17**, socket only (`use_core=False`, explicit), **NO FLASH** — `flash_log.jsonl` stays at 20 entries |
| engine leg | `tb_sys ret`, rebuilt on this tree at the KM landing, receipt `63308b10ac00a812…` |
| artifacts | `sw/testdata/iret-tf/` (`predictions.json`, `calib.json`, `core/`, `board/`, `SHA256SUMS` per directory) |
| predecessor | `docs/notes/tf0f_cell_results_2026-08-11.md` (prereg `f08a597ed5`, amendment `c13ec814f3`), landing `e57c3b4d12` / `ef7c493f20` |

---

## 1. WHY THIS CELL EXISTS

`tf0f_cell_results_2026-08-11.md` §5.2, verbatim:

> `pushed_off` measures the **COUNT** of units a probe contributes (1 vs 2), not
> **where** the second one sits — at a count of 2 the third unit is the first pad
> byte whatever the second unit's position. *"The second boundary is at the
> opcode byte"* is an **INTERPRETATION** of the count, not a measurement.
> Resolving it needs the trap to land one boundary earlier — an `IRET` setter,
> §86.C's own W-3 asymmetry — and that cell is **not built here**.

The `KM` landing matched the ucore to silicon's **count** on 30 legs.  Its own
closing note: *"this landing matches a count, not a position."*  Every `tf0f`
leg raised `TF` with `push imm16 ; popf`, so the first trap after the setter
always had the setter's own retire in the picture, and the trap never landed on
a boundary early enough for a position to be visible.

Separately, §86's other registered properties — the one-flop arm, the depth-4
pipeline (`rise_sim = rise_rtl + 1`), the `01D8` door — were all measured on
**one-byte** streams.  The interaction of that pipeline with the two-unit
decoration is unmeasured.

---

## 2. THE MECHANISM AS THE RTL IMPLEMENTS IT

The predictions below are derived from this, not from the "unit" surface
language, because the surface language is what §5.2 says is under-determined.
`hdl/rtl/ucore/v30u_eu.sv`:

* a **SAMPLE** rides a boundary POP —
  `brk_smp_n = q_pop && q_ripe && q_bnd_pop`, with
  `q_bnd_pop = q_first || (st == S_EXT_POP)` since `KM`;
* the arm is a **LEVEL** — `if (brk_smp) brk_arm_n = brk_seen`;
* the **TAKE** is `bnd_fire = at_bnd && bnd_take`, and `bnd_opc` is gated by
  `bnd_armed`, **which is set only at a RETIRE and never at a prefix
  hand-over** (`v30u_eu.sv:1932`).

Two consequences, and they are the whole cell:

1. **The ucore's pushed PC is always an instruction start.**  Silicon's need not
   be.  If the part can take at a prefix / escape hand-over, the pushed PC lands
   *inside* the probe — and that address **is** where the second boundary sits.
2. **`tf0f` could not see it.**  With its geometry (`f = 0`) the arming pop was
   already the probe's *last* decoration pop, so no hand-over remained between
   the arm and the retire.  Move the arm one pop earlier and every hand-over is
   back in front of it.

This also re-derives `tf0f`'s whole measured column with no new law:
`nop` → 6, `addrr` → 7, `movi` → 8, `pfx1` → 7, `pfx2` → 8, `pfx4` → 10,
`x1b` → 8, `z1b` → 9 are exactly *"arm on the second boundary pop after the
setter, take at the first retire after it."*

---

## 3. THE PROGRAM

`R = 6` identical blocks of `BLOCK = 16` bytes, **one trap each**, so a capture
is six independent repeats of one measurement.

```
popf geometry     68 00 01 9D   push 0x100 ; popf        <- TF <- 1
                  90 * f        THE FILLER, f = 0, 1 or 2
                  <P>           the probe
                  90 ...        pad to BLOCK

iret geometry     CD 04         BRK 4.  Vector 4's handler writes TF into the
                  90 * f        frame it is about to return through, so the
                  <P>           instruction that RAISES TF is that handler's
                  90 ...        IRET — and there is nothing whatever between
                                that IRET and the probe.
```

Vector 1's handler is `MOV BP,SP ; MOV word [BP+4],0xF002` + the `IRET` compose
appends — it CLEARS `TF` in the frame it returns through, so each block traps
exactly once.  Vector 4's handler is the same shape with `0xF102` (TF **set**);
on the NULL legs it writes `0xF002` instead, which is the whole difference.

`testimage.normalize_psw` forces `TF` clear into every composed image, so the
only way to a raised `TF` is one of these two setters.

**Every probe is `mod = 3`** — register-only, no memory operand anywhere.  This
is load-bearing, not incidental: a take that lands *inside* a probe resumes
there and re-executes the tail as a different, shorter instruction.  At `mod = 3`
that tail can have no memory side effect at all, so the geometry cannot perturb
itself and no leg can corrupt another.

**Axes.** `waits` 0-3 and `align` 0-3 (leading NOPs, which move every block's
byte phase against the word-aligned fetch).  Both declared here; neither is
chosen after seeing a result.  16 cells per leg, 6 traps per cell.

---

## 4. THE HYPOTHESIS SPACE — A PRODUCT, NOT A LIST

Three degrees of freedom, fully crossed.  20 composite rules.  Nothing can be
added afterwards without changing the product, and there is no per-opcode
special case anywhere in it.

**S — which pop arms**, counting boundary pops from the first one after the
setter.

| | |
|---|---|
| **S1** | the **FIRST** boundary pop after the setter arms.  With an `IRET` setter the flag load sits at the end of a long, queue-flushing instruction, so §86.B's 4-clock floor may already be cleared — and this is what makes a conventional single-step advance one instruction per trap. |
| **S2** | the **SECOND** arms, exactly as `popf` does. |

For the `popf` setter `S = 2` is **MEASURED** (`tf0f`: `nop` reads 6, not 5) and
is held fixed; the `P0` and `RP` legs re-measure it here on this cell's own
images.  For the `IRET` setter both are open.

**P — which pops inside a decorated instruction are samples.**

| | |
|---|---|
| **PA** | the instruction-start pop and the **OPCODE** pop only — two, whatever the depth. |
| **Pall** | **every** decoration byte's pop and the opcode's — which is what the `QS = 1` pins announce and what `pop_is_first` does in the ucore (`pfx4` = five pops). |

**B — where a take may land inside a decorated instruction**, over and above its
own retire (which always takes).  Write `a` for the probe's first byte, `np` for
its prefix count, `d = np + esc` for its decoration length.

| | |
|---|---|
| **B0** | nowhere — **RETIRE ONLY**.  *This is the ucore as landed, and it is prediction (a).* |
| **B1** | also at the FIRST decoration byte's hand-over (resume `a+1`) |
| **Bnp** | also at the PREFIX STACK's hand-over (resume `a+np`) — the `0F` byte on an escaped probe |
| **Bd** | also at the **OPCODE's** hand-over (resume `a+d`) — ***this is `KM`'s own interpretation***, *"the second boundary is at the opcode byte"* |
| **Ball** | at **every** decoration byte's hand-over |

**The simulation.**  Walk one block's events in program order from the first pop
after the setter; arm on the S-th POP; take at the first BOUNDARY after it; the
pushed PC is that boundary's resume address.  `sw/iret_tf_cell.py predict` does
exactly this and writes every per-leg number to `predictions.json`; the table is
reproducible by hand from the four lines above.

### 4.1 Why the filler resolves what `tf0f` could not

At `f = 1` the arming pop is the probe's **first** pop, so all of `B1`, `Bnp`,
`Bd` and `Ball` are still ahead of it and they separate.  Worked example,
`P1_p4x` (`2e 3e 26 36 0f 1b e8 4f`, probe at offset 5):

| rule | pushed_off |
|---|---:|
| `B0` retire only | **13** |
| `B1` first decoration byte | **6** |
| `Bnp` the prefix stack's hand-over (at the `0F`) | **9** |
| `Bd` the opcode's hand-over | **10** |
| `Ball` | **6** |

At `f = 0` — `tf0f`'s geometry — the same five collapse to 10.  That is §5.2,
in one row.

### 4.2 Legs declared NON-DISCRIMINATING in advance

All 20 rules agree on these, so they may never be quoted as evidence for a
rule.  They are carried as controls: `P1_nop`, `P1_addrr`, `P1_movi`,
`P0_nop`, `P0_addrr`, `P0_x1b`, `P2_nop`, `P2_pfx4`, `P2_z1b`, `P2_p4x`,
`RP_nop`, `RP_x1b`, `P1_v_xchg`.  (Bare-`0F` probes have `d = 1`: the escape and
the opcode are adjacent, so no position rule can separate them.  This is why the
`prefix + 0F` probes exist.)

---

## 5. THE REGISTERED PREDICTIONS

### 5.1 Prediction (a) — `KM`-as-landed, extended naively to `IRET`

**The ucore's own offline column IS this prediction**, and it is committed with
this document (`sw/testdata/iret-tf/core/table.json`, `manifest.json` carrying
the `tb_sys ret` receipt `63308b10ac00a812…`).  832 cells, **0 structurally
invalid**, every leg single-valued over its 96 traps, the three NULL legs at 0
entries.  Measured, not asserted:

| leg | bytes | f | core | leg | core | leg | core |
|---|---|---|---:|---|---:|---|---:|
| `nop` | `90` | | `P1` **6** | `I0` **3** | | `I1` **3** | |
| `addrr` | `01d8` | | `P1` **7** | `I0` **4** | | `I1` **3** | |
| `movi` | `b83412` | | `P1` **8** | `I0` **5** | | `I1` **3** | |
| `pfx1` | `2e01d8` | | `P1` **8** | `I0` **5** | | `I1` **3** | |
| `pfx2` | `2e3e01d8` | | `P1` **9** | `I0` **6** | | `I1` **3** | |
| `pfx3` | `2e3e2601d8` | | `P1` **10** | `I0` **7** | | `I1` **3** | |
| `pfx4` | `2e3e263601d8` | | `P1` **11** | `I0` **8** | | `I1` **3** | |
| `x1b` | `0f1be84f` | | `P1` **9** | `I0` **6** | | `I1` **3** | |
| `x13` | `0f13c0` | | `P1` **8** | `I0` **5** | | `I1` **3** | |
| `z1b` | `2e0f1be84f` | | `P1` **10** | `I0` **7** | | `I1` **3** | |
| `p2x` | `2e3e0f1be84f` | | `P1` **11** | `I0` **8** | | `I1` **3** | |
| `p4x` | `2e3e26360f1be84f` | | `P1` **13** | `I0` **10** | | `I1` **3** | |

`P0` reads 6 · 7 · 8 · 10 · 8 · 9 (`nop addrr pfx2 pfx4 x1b z1b`), `P2` reads 6
on all four, and the three `RP` legs read **6 · 8 · 9** — `tf0f`'s published
CHIP column exactly, on byte-identical images, which is the `KM` landing
confirmed offline (before the landing the core read `x1b` = 9).

**The unique composite rule that reproduces all 52 core legs is `S1.*.B0`** —
`PA` and `Pall` are indistinguishable under `B0`, because with no hand-over
take point it does not matter which pops sample.  Two things in that are
themselves registered predictions, not restatements:

* **the ucore is `S1` on the `IRET` setter and `S2` on `popf`** — `I0_nop`
  reads 3, not 4.  One instruction per trap, which is what a single-step is;
* **`B0` everywhere** — no pushed PC on any of the 832 cells is a
  mid-instruction address.

Any chip-vs-core difference on this cell is physics `KM` does not carry.

### 5.2 Prediction (b) — the §86-pipeline-interaction alternatives

Stated sharply, and they are the other 16 rules.  The one to beat is **`Bd`**:
if the extra unit really is *at the opcode byte*, then at `f = 1` the trap is
taken there and the pushed PC is `a + d` — a **mid-instruction return address**,
three to five bytes below where the ucore puts it on the deep probes.  `Bnp`
says the escape is where the boundary sits and the opcode pop is not a take
point; `B1` and `Ball` say the depth-4 pipeline shifts the take to the first
decoration byte and the two-unit decoration is a saturation of *takes*, not of
*samples*.

### 5.3 THE BAR

> A composite rule is declared **the measured law** only if it reproduces the
> chip's `pushed_off` on **every scored derivation leg**, each leg single-valued
> across all 16 of its cells and all 6 of its traps.

If no registered rule clears it, that is reported as **the outcome** and the
replacement is stated as an **erratum**, committed, and only then scored on the
**disjoint validation population** (§7) — the `tf0f` A-1 procedure, which is the
standing rule.

### 5.4 The anchor

The `KM` landing predicts the **core** column.  Agreement chip-vs-core is a
**VALIDATION of `KM` on a setter it was not derived on** and is to be reported
as such, plainly, not as a disappointment.  Disagreement is the next law's
evidence.  The cell has value either way and that is why it is being run.

---

## 6. THE INTEGRITY BARS

Every one of these is a clause of the run, not a hope.

* **I-1** single-writer asked of the board (not assumed) before the first
  capture; a violation **STOPS** the cell.
* **I-2** socket only — `use_core=False` passed explicitly on every capture, and
  `emit_suite.EMIT_USE_CORE is False` asserted at import.
* **I-3** **NO FLASHING.**  `flash_log.jsonl` = **20 entries** before and after,
  recorded in the manifest with the resident `.sof` sha256.
* **I-4** **THE NULL** — three legs whose only difference is that vector 4's
  handler (or the `popf` immediate) leaves `TF` clear: `N_p1_z1b`, `N_i0_z1b`,
  `N_i0_p4x`.  **0 vector-1 entries in 48 of 48 cells** or nothing else here is
  quotable.
* **I-4b** **THE INSTRUMENT CONTROL** — the three `RP_*` legs are `tf0f`'s own
  images, asserted **byte-identical** (`repro_image_identical_to_tf0f`, 12 of
  12 true at `predict` time), and must reproduce its published chip column:
  `RP_nop` **6**, `RP_x1b` **8**, `RP_z1b` **9**.
* **I-5** **0 structurally invalid cells** — anchor present, exactly `R` (or 0)
  vector-1 entries, three pushes each.  Invalid cells are RETAINED and REPORTED,
  never dropped.
* **I-6** `div_guard` **PINNED at every leg boundary**, 0 UNPINNED.
* **I-7** **0 transport errors**, 0 `RigMismatch`.  Three consecutive transport
  errors STOP the cell; a `RigMismatch` STOPS it immediately, because a
  rig-integrity finding outranks the measurement.
* **I-8** stability: **≥ 5 % of cells captured ×3**, **0 TAKE-unstable**.
  Stream-distinct repeats are reported, not smoothed.
* **I-9** the FULL per-clock 64-bit words retained per cell with a `sha256`,
  `SHA256SUMS` over each directory.
* **I-10** `board_idle()` clean and **`check_ab_hw.py chip 800` = MATCH** after
  everything.

**STOP conditions**, in force order: `RigMismatch` → three consecutive transport
errors → single-writer violation → an UNPINNED `div_guard` readback.  Any of
them is a rig finding and is reported as one, above the cell's own result.

---

## 7. THE DISJOINT VALIDATION POPULATION

Registered here, **before** any board contact, so it is a genuine hold-out for
whatever rule the derivation names — including a replacement.  Its bytes appear
nowhere in the derivation set.

| leg | bytes | shape |
|---|---|---|
| `P1_v_pfxa` / `I0_v_pfxa` | `36 26 01 d8` | 2 prefixes, no escape |
| `P1_v_pfxb` / `I0_v_pfxb` | `f3 2e 3e 01 d8` | 3 prefixes incl. REP |
| `P1_v_z13` / `I0_v_z13` | `3e 0f 13 c0` | 1 prefix + escape |
| `P1_v_p3x` / `I0_v_p3x` | `26 36 3e 0f 13 c0` | 3 prefixes + escape |
| `P1_v_x2a` / `I0_v_x2a` | `0f 2a c0` | bare escape |
| `P1_v_lock` / `I0_v_lock` | `f0 01 d8` | LOCK prefix |
| `P1_v_xchg` / `I0_v_xchg` | `93` | undecorated |
| `N_p1_v_p3x` | — | the validation NULL |

It is **captured and scored only after the derivation verdict is committed**.
Its core column is likewise taken after that commit.

---

## 8. WHAT THIS CELL DOES **NOT** RESOLVE — stated before the run

* It observes the **pushed return address**, so it can only see a boundary the
  part is willing to **take** at.  A boundary that samples but can never take —
  which is exactly what `Pall` describes in the ucore today — is invisible to it
  except through the counting of §4.  A rule of the form *"the sample sits at
  byte X but the take is always deferred to the retire"* is therefore
  observationally identical to `B0` **on this cell**, and will be reported as
  `B0` with that caveat attached.
* It says nothing about 8080/BRKEM (deferred by user decision 2026-08-05), and
  no probe is a BRKEM alias.
* It writes **no RTL**.  Any landing candidate is booked with a falsifier and a
  seat reach, and the seat reach will be stated honestly: the `tf0f` precedent
  registered *"any claim of a two-digit seat gain from this mechanism is
  registered IN ADVANCE as unsupported"* and that clause carries over here
  unchanged until a disjoint population says otherwise.
* No head-to-head "the chip beats the core" figure will be computed.  Both
  columns are scored against **silicon**, which is the chip column itself.
