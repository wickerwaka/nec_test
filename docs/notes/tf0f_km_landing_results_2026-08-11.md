# RESULTS — `KM` IS LANDED. ONE TERM, NO FLOP, AND THE PINS DID NOT MOVE.

**The `0F` escape's OPCODE pop is a TF boundary sample. Every registered clause
of the primary evidence leg is MET, the QS pin stream is byte-identical, the
whole standing ladder is ZERO DELTA, and all THREE anchor seats closed — one of
them against its own pre-registration.**

| | |
|---|---|
| pre-registration | `docs/notes/tf0f_km_landing_prereg_2026-08-11.md`, commit **`7e56aea9d1`**, **before the RTL was touched** |
| the law | `KM`, `docs/notes/tf0f_cell_results_2026-08-11.md` (prereg `f08a597ed5`, amendment `c13ec814f3`) |
| tree | `fuzz-v2-on-relanding`, `38a34dc70e` → `7e56aea9d1` → this |
| scope | **offline only.** No board. No flash. `flash_log.jsonl` untouched. |
| engine leg | `tb_sys ret`, receipt **`4ff6a9ee86849f7b…`** · `tb_v30_core ucore`, receipt **`dc3c5f76bfc4e6f2…`** |

---

## 1. THE EDIT — EXACTLY, AND IT IS TWO LINES OF LOGIC

`hdl/rtl/ucore/v30u_eu.sv`. **No flop. No save-state address. No opcode named.
No `hdl/rtl/ucore/v30u_ss_pkg.sv` edit.**

**(a)** a second consumer's term, declared beside `assign q_first`:

```systemverilog
wire q_bnd_pop = q_first || (st == S_EXT_POP);
```

**(b)** the sample, at what was `:3126`:

```systemverilog
-        brk_smp_n = (q_pop && q_ripe && q_first)   || (bnd_fire && irq_take);
+        brk_smp_n = (q_pop && q_ripe && q_bnd_pop) || (bnd_fire && irq_take);
```

Everything else in the diff is comment: the law and its silicon at `q_bnd_pop`,
the erratum against §86's paragraph in place, and a note at
`v30u_eu_step.svh`'s `S_EXT_CHG1` branch recording why that branch is
deliberately still empty.

**THE ONE SENTENCE IT IMPLEMENTS.** *The boundary the BRK/TF arm samples is the
pop of the byte the LOADER DECODES — the instruction's first byte, the byte a
prefix hands over to, and the `0F` escape's second byte — whereas the `QS` pins
announce the pop that STARTS an instruction. Silicon already says these are two
different things, in both directions.*

### 1.1 SATURATION IS INHERITED, NOT ADDED — AND THAT IS WHY THERE IS NO COUNTER

`KM` saturates: one extra unit however deep and however many kinds of
decoration. **Nothing in this landing implements that, because this core
already did.** `brk_arm` is ONE FLOP holding a LEVEL (`brk_arm_n = brk_seen`),
and the TAKE is `bnd_fire = at_bnd && bnd_take` whose `bnd_opc` arm is gated by
`bnd_armed`, set only at a RETIRE and never at a prefix hand-over. So extra
samples *inside* an instruction cannot move its trap earlier than its own
boundary. That is already why `pfx1…pfx4` read two units at every depth while
the pins announce two, three, four and five.

**MEASURED, not argued:** clause **E-7**, below — `z1b`, `v_p2x`, `v_p4x`,
**288 traps, UNMOVED**.

### 1.2 ⚠ THE RESULTS DOCUMENT'S §8 WARNING IS WITHDRAWN — THE NAIVE FIX IS INERT, NOT DANGEROUS

`tf0f_cell_results_2026-08-11.md` §8 warns that setting `pop_is_first_n = 1'b1`
in `S_EXT_CHG1` would give a prefixed `0F` instruction three units. **Registered
in the pre-registration before any edit, and it stands:** that edit changes
nothing at all. `pop_is_first` has exactly two readers in the tree —
`assign q_first` and `v30u_eu_ss_read.svh` — and `q_first` consults it **only
when `st == S_OPC_POP`**; `S_EXT_CHG1`'s successor is `S_EXT_POP`, and the next
`S_OPC_POP` already has `pop_is_first` set by `S_INSTR_END` / `S_IRQ_D`. It
moves neither the boundary nor the pins. (And by §1.1 it could not have
regressed the observable even if it had reached it.) The note is now written
into `v30u_eu_step.svh` beside the branch, so the next reader does not have to
re-derive it.

---

## 2. THE PRIMARY EVIDENCE LEG — THE BANKED TF × `0F` CELL

`sw/tf0f_cell.py core --strata <all 32 probes>` then `score` and `qs`.
**The board column is silicon and was NOT re-run** (no board contact); only the
`tb_sys ret` core column was re-taken, over all **512 cells**, and the
pre-landing core column is archived byte-identical at
`sw/testdata/tf0f/core-pre-km/` (**131 files, sha256-verified file for file**
before the RTL was touched).

### 2.1 THE COLUMN

| stg | leg | bytes | **chip** | core BEFORE | **core AFTER** |
|---|---|---|---:|---:|---:|
| der | `nop` | `90` | 6 | 6 | **6** |
| der | `clc` | `f8` | 6 | 6 | **6** |
| der | `incaw` | `40` | 6 | 6 | **6** |
| der | `movi` | `b83412` | 8 | 8 | **8** |
| der | `addrr` | `01d8` | 7 | 7 | **7** |
| der | `pfx1` | `2e01d8` | 7 | 7 | **7** |
| der | `pfx2` | `2e3e01d8` | 8 | 8 | **8** |
| der | `pfx3` | `2e3e2601d8` | 9 | 9 | **9** |
| der | `pfx4` | `2e3e263601d8` | 10 | 10 | **10** |
| der | `x13` | `0f13c0` | **7** | 8 | **7** ✔ |
| der | `x1b` | `0f1be84f` | **8** | 9 | **8** ✔ |
| der | `x18` | `0f18c005` | **8** | 9 | **8** ✔ |
| der | `x28` | `0f28c0` | **7** | 8 | **7** ✔ |
| der | `x33` | `0f33c3` | **7** | 8 | **7** ✔ |
| der | `y1e` | `0f1e06002005` | **10** | 11 | **10** ✔ |
| der | `z1b` | `2e0f1be84f` | 9 | 9 | **9** ← SATURATION |
| val | `v_p2x` | `2e3e0f1be84f` | 10 | 10 | **10** ← SATURATION |
| val | `v_p4x` | `2e3e26360f1be84f` | 12 | 12 | **12** ← SATURATION |
| val | `v_pfxi` | `2eb83412` | 8 | 8 | **8** |
| val | `v_rep` | `f301d8` | 7 | 7 | **7** |
| val | `v_lock` | `f001d8` | 7 | 7 | **7** |
| val | `v_x39` | `0f39c004` | **8** | 9 | **8** ✔ |
| val | `v_x1f` | `0f1fc003` | **8** | 9 | **8** ✔ |
| val | `v_x10` | `0f10c0` | **7** | 8 | **7** ✔ |
| val | `v_x2a` | `0f2ac0` | **7** | 8 | **7** ✔ |
| val | `v_y13` | `0f13060000` | **9** | 10 | **9** ✔ |
| val | `v_add` | `81c03412` | 9 | 9 | **9** |
| val | `v_movm` | `a10000` | 8 | 8 | **8** |
| val | `v_push` | `50` | 6 | 6 | **6** |
| val | `v_xchg` | `93` | 6 | 6 | **6** |

Every cell single-valued over its 96 traps, both before and after.

### 2.2 THE REGISTERED CLAUSES, SCORED

| # | registered | measured | |
|---|---|---|---|
| **E-1** | `KM` vs core, DERIVATION **16/16** (was 10/16) | **16 / 16** | **MET** |
| **E-2** | `KM` vs core, VALIDATION **14/14** (was 9/14) | **14 / 14** | **MET** |
| **E-3** | chip ≠ core cells → **0** (was 176 of 512) | **0 / 512** on `n_entries`, `pushed_off`, `pushed_off_set`, `lastcode_off_set`, `uniform` AND `term_done` | **MET** |
| **E-4** | control band unmoved, 480 traps | `nop clc incaw movi addrr` = 6 · 6 · 6 · 8 · 7, chip = core | **MET** |
| **E-5** | the NULL, 0 entries in all 32 cells | `notf` **[0]**, `v_notf` **[0]** | **MET** |
| **E-6** | eleven bare-`0F` legs each **−1** onto the chip | all eleven, each single-valued over 96 traps | **MET** |
| **E-7** | **SATURATION** — `z1b` · `v_p2x` · `v_p4x` UNMOVED, 288 traps | **9 · 10 · 12, unmoved** | **MET** |
| **E-8** | every other leg unmoved | 19 legs unmoved | **MET** |
| **E-9** | `qs` `stream_diff` **[]**, `compared` **480** | **[] / 480** | **MET** |
| **E-10** | `qs` `pins_core` byte-identical on every probe | **0 of 30 probes changed** (and `pins_chip` 0, `chip_units` 0) | **MET** |
| **E-11** | `core_units` **1 → 2** on the bare-`0F` legs | exactly those **11**, and `core_units == chip_units` on **all 30** | **MET** |

**KC vs CORE now reads 10/16 and 9/14 — i.e. the core has stopped implementing
`KC`** — and `KM vs CORE` reads 16/16 and 14/14. Stability re-measured: 64 of
512 cells ×3, **0 TAKE-unstable, 0 stream-distinct**.

Unregistered, worth recording: the **prefetch high-water mark** (`lastcode_off`)
is chip = core distribution for distribution on **all 30 probes**, so the trap
moved without the fetch stream moving.

### 2.3 THE QS-PIN CONSTRAINT — MET

This was the landing's hard constraint: **move the boundary without moving the
pins**, on a stream that already matched silicon 480/480.

* the chip-vs-core **QS pin stream**: `0 of 16 cells differ` on **all 30 probes**,
  `stream_diff` **[]**, `compared` **480** — *identical to the banked column*;
* `pins_chip` and `pins_core` **unchanged on every one of the 30 probes**;
* the only thing that moved is `core_units`, on exactly the eleven bare-`0F`
  legs, **1 → 2**, which is the landing.

The die does the same thing: `pfx4` announces five `QS = 1` and uses two units;
a bare `0F` uses a boundary the pins never announce. **Two consumers, two
predicates — and `q_first` still serves the pins, `eu_halt` and
`first_pop_seen`.**

---

## 3. SEATS — ALL THREE CLOSED, AND ONE OF THEM AGAINST ITS PRE-REGISTRATION

Instrument `sw/fz2_replay.py --leg ret`, scored against the banked FLASH #17
socket rows. ⚠ **Every post-edit run carries `--no-fabric-era-guard`, and the
tool printed `*** OVERRIDDEN ***` on each.** That is the honest status: the
flashed bitstream predates this RTL, the guard is right to fire, and **no
fabric figure in this repository may be quoted against this tree.** The
pre-edit baselines below ran with the guard **PASSING**.

| leg | before | after |
|---|---|---|
| `--all-failures` | 113 seeds, **113 replay-FAIL**, agreement 113/113, `first_bad` identical on 113 | **110 replay-FAIL**, agreement 110/113 = 97.3 %, `first_bad` identical on 110 |
| `--pass-sample 600` | 538 seeds, **538 replay-PASS**, 538/538 | **538 replay-PASS, 538/538** |

| # | registered | measured | |
|---|---|---|---|
| **S-1** | `fz2e/501066` **CLOSES** | **CLOSED** — 572 bad rows → **0** (first_bad was 515) | **MET** |
| **S-2** | `fz2e/513019` **CLOSES** | **CLOSED** — 2,843 → **0** (first_bad was 656) | **MET** |
| **S-3** | `fz2c/404041` **MOVES, DOES NOT CLOSE** | ⚠ **MISSED — IT CLOSED.** 2,437 → **0** (first_bad was 933) | **MISSED** |
| **S-4** | total ledger closures **2 of 113** | ⚠ **MISSED — 3 of 113** | **MISSED** |
| **S-5** | **0 lost**: 538/538 still PASS; 0 `first_bad` earlier | **0 lost. 0 bad-row changes and 0 `flick` changes across all 538. 0 of the 110 moved `first_bad`. 0 seeds anywhere gained a bad row.** | **MET** |
| **S-6** | the six named count-movers, **0 close** | `fz2c/406063` · `fz2c/410047` · `fz2e/518039` · `fz2e/518053` · `fz2e/522019` · `fz2e/535027` — **bad-row counts byte-identical, 0 closed** | **MET** |
| **S-7** | `fz2c/404040` non-mover | `bad 0`, `flick 0`, `nrows 4063`, `win 2001` — identical before and after | **MET** |
| **S-8** | `fz2_immaterial.py falsify` **PASS**, 21/92/113 | **PASS**, G1–G8, **21 members / 92 non-members / 113 failures**, residue 92 = 48 + 33 + 11 | **MET** |

**Total bad rows over the 113: 119,192 → 113,340 (−5,852). Seeds with MORE bad
rows: ZERO.**

### 3.0 THE SHARPEST FORM OF THE REGRESSION RESULT

Over the **651 seeds replayed on both sides** (113 ledger failures + 538
passing), the complete `tb_sys` replay record — `n`, `nrows`, `bad`, `flick`,
`first`, `fired`, `vecused` — is **BYTE-IDENTICAL on 648**, and the **only three
seeds that changed at all are the three anchor seats**:

```
fz2c/404041   bad 2437 -> 0   (first_bad 933)
fz2e/501066   bad  572 -> 0   (first_bad 515)
fz2e/513019   bad 2843 -> 0   (first_bad 656)
```

Named non-movers verified individually, all four with their `first_bad` rows
identical to the values `n1_halt_wake_sample_prereg_2026-08-11.md` N1-3
registered — **the §64.1 four**:

| seed | bad | first_bad |
|---|---:|---:|
| `fz2c/405002` | 840 → 840 | **527 → 527** |
| `fz2c/405013` | 921 → 921 | **1331 → 1331** |
| `fz2c/405072` | 891 → 891 | **636 → 636** |
| `fz2e/512056` | 984 → 984 | **1475 → 1475** |

The "ghost family" and every other named non-moving population are inside the
648 by construction: **nothing outside the three seats moved by one row.**

### 3.1 ⚠ S-3 AND S-4 ARE REPORTED AS MISSES, IN THE FAVOURABLE DIRECTION

`fz2c/404041` was registered — here, and in the cell's own pre-registration
committed before board contact — as **not closing by this alone**, because its
core leg *"retires a further far `CALL` after the displaced boundary"* and its
streams *"re-align only 2/342"*. **It closed outright.** The registered
reasoning was wrong: the further far `CALL` and the 340 unaligned rows were
**consequences** of the displaced boundary, not evidence of a second mechanism.
That is worth saying plainly, because the pre-registration's function is to make
a surprise legible in both directions, and this one is a surprise.

**The reach is therefore 3 seeds, not 2 — and P-3 IS STILL MET, NOT BEATEN.**
The cell registered *"the honest reach is 2–3 seeds"* and *"any claim of a
two-digit seat gain from this mechanism is registered IN ADVANCE as
unsupported"*. **3 is the top of that range and nothing here licenses more.**
This is an OFFLINE figure on `tb_sys`; the fabric leg is a future flash's.

---

## 4. THE STANDING LADDER — ZERO DELTA, AS REGISTERED

Every one of these was re-run **after the RTL text was frozen**, on binaries
rebuilt from the final bytes.

| gate | registered | measured | |
|---|---|---|---|
| `gen_ucore_qsf.py --check` | up to date | **up to date** | PASS |
| `r7_lint.py` | PASS, 3 tainted, 51 `stop` sites, **no new exception** | **PASS — 0 undeclared carriers, 0 undeclared unresolved, 3 tainted (`eu_rd_edge`, `rd_edge_psw_take`, `rd_edge_take_raw`), 51 `stop` sites, 0 violations** | PASS |
| `ss_lint.py --core ucore` | `SS_VERSION` 0x8D / BIU 103 / EU 122 / `SS_COUNT` 226 / `SS_TAG` 0x8DE2, **214** flops, 0 UNMAPPED | **identical, UNCHANGED** (85 BIU flops → 85 mapped; 129 EU → 127 mapped + 2 whitelisted; 1 sim-only exempt) | PASS |
| `test_artifact.py` | 45/45 | **45/45** | PASS |
| `check_core.py --core ucore --opcodes all --cases 0` | 169,000/169,000 | **169,000 / 169,000** (cycles 169,000, arch 169,000) | PASS |
| `s10-hltsweep-w0 --waits 0` | 97/97 | **97 / 97** | PASS |
| `s10-hltsweep-w1 --waits 1` | 93/95 | **93 / 95** | PASS |
| `s13-hltsweep-w2 --waits 2` | 45/46 | **45 / 46** | PASS |
| `s13-hltsweep-w3 --waits 3` | 44/45 | **44 / 45** | PASS |
| the four together | **279 / 283**, the four survivors the four family-D cells | **279 / 283**, `HLT.RES` 49 · 49 · 25 · 25 PERFECT | PASS |
| `ulockstep.py --golden all --cases 50` | 17,350/17,350 | **17,350 / 17,350, ALL CASES LOCKSTEP** | PASS |

⚠ **`ss_lint`'s registered values are this branch tip's, not CLAUDE.md's.**
CLAUDE.md carries `0x8C / 224 / 0x8CE0 / 212`; the tree at `38a34dc70e` carries
**`0x8D / 226 / 0x8DE2 / 214`** (`v30u_ss_pkg.sv` comments it *"ucore map v13
(F58 AD latch)"*). Measured at HEAD **before** the edit and unchanged after.
CLAUDE.md's line is STALE and is not this landing's to move.

**Why zero delta is structural rather than lucky:** `brk_smp` has exactly one
consumer, `if (brk_smp) brk_arm_n = brk_seen`, and `brk_seen` is
`psw[FBRK] && brk_p[BRK_FLOOR-1]`. With `TF` clear an extra sample writes the
value the flop already holds. Every golden suite, every HLT sweep and every
lockstep form runs TF-clear.

---

## 5. G6 — SYNTHESIS. TWO DRAWS, BOTH GREEN, AND IDENTICAL TO THE DECIMAL.

`python3 sw/quartus_gate.py`, CONTROL/DEFAULT configuration (no
`X1_AD_RETENTION`), each from a clean `db`.

| | **draw 1** | **draw 2** |
|---|---|---|
| label | `KM landing draw 1 (CONTROL)` | `KM landing draw 2 (CONTROL)` |
| **Fmax** | **38.7 MHz** | **38.7 MHz** |
| **worst setup** | **+5.41 ns** | **+5.41 ns** |
| **TNS** | **0.000, setup AND hold, every domain** | **0.000, setup AND hold, every domain** |
| errors / latches / `lpm_divide` | 0 / 0 / 0 | 0 / 0 / 0 |
| ALMs | **12,212 / 41,910 (29 %)** | **12,212 / 41,910 (29 %)** |
| E1 `gen_ucore_qsf --check` | PASS | PASS |
| 88-file input manifest | **`fcfadf118a1080df…`** | **`fcfadf118a1080df…`** |
| 9-file report manifest | `2dbccab6bb727bda…` | `0993fa8ed90782f3…` |
| **receipt** | **`004a8b0e6d3f5391…`** | **`d88f10f646d39d1a…`** |
| git | `7e56aea9d1-dirty` (the landing not yet committed) | **`e57c3b4d12`, CLEAN** |
| compile | rc=0, 670 s | rc=0, 625 s |

**BOTH DRAWS CLEAR THE REGISTERED 38.0 MHz HARD STOP, and both sit inside the
registered `38.4 – 42` band.** Quartus 17.1.0 Build 590 in both cases.

**The input manifest is byte-identical across the two draws**, which is the
check that the commit between them changed no file the compiler reads: draw 1
was taken on a dirty tree and draw 2 on `e57c3b4d12`, and the compiler saw the
same 88 files. The report manifests differ, as they must — the reports carry
timestamps.

⚠ **TWO GREEN BUILDS ARE STILL NOT CLOSURE.** `standing_gates.md` §A governs and
the multi-seed worst-of-N gate is not built; the same tree has drawn 19.42 and
45.91 MHz historically. What is registered and met is: two draws, both quoted,
both above the STOP.

⚠ **RECORDED, NOT EXPLAINED — the two draws agree to the decimal on Fmax, worst
setup AND ALM count.** Analysis & Synthesis is documented in this repo as *not*
reproducible run to run for combinational counts (§74.4a), so an exactly
repeated triple is worth writing down rather than assuming. It is reported as an
observation about these two draws and is not offered as evidence that the flow
has become deterministic.

**Band context, quoted honestly.** The branch's recent CONTROL draws are
39.16 · 39.37 · 39.47 · 39.63 · 39.81 · 40.11 MHz; this landing draws
**38.7 · 38.7**, i.e. **at the bottom of the branch's control band but above the
registered stop**, with ALMs 12,212 against the FLASH #13-era control's 12,340.
The immediately preceding sitting (N-1) collapsed a build to 20.80 MHz on a
pin-path edit; this edit is in the step/decode zone and did not. **Reported, not
explained.**

---

## 6. THE §86 ERRATUM — LANDED

`ucore_provenance.md` is **CLOSED at §88** and says so, so nothing was appended
to it. The erratum is written **in place, under §86's own heading**, as a
clearly-labelled ERRATUM block, because a closed ledger carrying an unmarked
refuted claim is worse than one carrying an erratum. **Nothing of §86 was
deleted.** The same correction is written into the RTL twice: at the
`q_bnd_pop` declaration, and against the paragraph in block (g) that used to end
*"and the `0F` escape's first byte does too"*.

What it says, in three lines: §86's *"a prefix retires with its own F pop"* is
**right in kind and wrong in count** (a prefix STACK is ONE extra unit at any
depth — `pfx1…pfx4` = 7 · 8 · 9 · 10 on both engines, 384 traps); its *"and the
`0F` escape's first byte does too"* was **never implemented and names the wrong
byte** (silicon counts the escape's SECOND byte, which the pins announce
SUBSEQUENT); and therefore *"the sampling boundaries are simply the opcode pops
the `QS = 1` pins announce"* is **refuted in both directions, engine-free**.
§86's sample instant, its one-flop arm, its take, its `01D8` row-0/row-2 door
and its depth-4 pipeline are **untouched**.

---

## 7. WHAT THIS SITTING DID NOT DO

* **No board. No flash.** `flash_log.jsonl` untouched; the board still carries
  FLASH #17. **No fabric figure may be quoted against this tree**, and the
  `fz2_replay` era guard says so on every post-edit run.
* `sw/testdata/tf0f/board/` was **not** re-run and not modified.
* `timed_scenario`, `timed_ins_replay`, `timed_wvec_gate`, `timed_enter_replay`
  were **not run and are not quoted** — they die in `gen_seq._v1_anchor_stop` on
  this branch, engine-independently.
* No Codex delegation, no nested tasks.
* No head-to-head between the ucore and the model is computed anywhere.
* The `IRET`-setter cell that would resolve **where** the second boundary sits
  (cell §5.2) is still **not built**. This landing moves a COUNT to match
  silicon's count; *"the second boundary is at the opcode byte"* remains an
  interpretation.
* `sm3_tf_floor_cell` was not repaired or re-anchored.
