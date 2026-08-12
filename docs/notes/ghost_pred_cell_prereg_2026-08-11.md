# THE `8F` GHOST-READ **PREDICATE** — DIRECTED BOARD CELL — PRE-REGISTRATION

Branch `fuzz-v2-on-relanding`, base **`770c0d1b85`** (`git rev-parse HEAD`
verified; the MAIN checkout, because the board lives here).
**BOARD CONTACT IS FOR CAPTURE ONLY — SOCKET ONLY (`use_core=False`, passed
explicitly), NO FLASHING (FLASH #18 is resident, `flash_log.jsonl` stays at 21
entries), NO RTL CHANGE, `sim/` NOT EXTENDED, NO QUARTUS.**

This document is committed **before the first board command**. Everything in it
that is a number was measured **offline**, on `tb_sys ret`, and is committed with
it: `sw/testdata/ghost-pred/{predictions.json,calib.json,rails/,core/}`.

---

## §0 THE QUESTION, AND WHY THE BANKED CORPUS CANNOT ANSWER IT

The undocumented `8F` with `mod == 3` issues a stack read at a **stale address**.
Four waves have measured that address and stopped at the same wall:

| wave | what it settled | what stopped it |
|---|---|---|
| **W4** (`fz2_w4_ghostaddr_results_2026-08-10.md`) | landed `ghost_bus_off = ghost_off & gpr[R_SP]`, the AND **unconditional**, on **3 seats where the CHIP ANDs and the core did not** | its own §2.2: *"THE AND IS NOT UNIVERSAL AND THIS LANDING DOES NOT CLAIM IT IS … the two free choices left standing are WHICH RAIL and WHETHER THE AND HAPPENS"* |
| **W6** | REFUTED the single rail — `IND` at `near_dist 0`, `M_EA` at 1, intersection EMPTY | needs a retained flop, out of charter |
| **W7** | REFUTED the retained flop — 0 closures, **2 LOST** | the stale source is predecessor-type-indexed, i.e. a SELECTOR |
| **W8** | NOT EVALUABLE — **n = 1** | on that one seat `IND == SP == ec50`: *"one seat, with two candidate rails degenerate on it, is not a derivation — it is a coincidence with a receipt"* |
| **M10-SYS** (W9) | fixed the INSTRUMENT (13/13 vs 7/13) and got **two** speaking seats, **both UNDECORATED**, `SS:SP` bit-exact | *"on both speaking seats the undecorated value is held simultaneously by `SP`, `TMPB` and `IND`"* |

So silicon **sometimes ANDs** (W4, 3 seats) and **sometimes does not** (M10-SYS,
2 seats), and **the deliverable is the PREDICATE deciding when**. The banked
corpus is random programs; on every seat that speaks, the candidate rails hold
the same number. **The fix is construction, not more fuzz.**

## §1 THE INSTRUMENT — `sw/ghost_pred_cell.py`

### §1.1 The sentinel alphabet, and why it is the whole trick

`SP` is given the **mask** value `0xF0F0`. Every other sentinel carries exactly
**one bit inside that mask** and **one bit outside it**, and no two share either
bit:

```
SP    f0f0     A_POP 8800     E1 4400     E2 2200     E3 1100
V1    0088     V2    0044     E_SEG 0022
```

Therefore, mechanically and with no hand-written constant:

| what appears on the pins | what it means |
|---|---|
| `8800` (two bits, one OUTSIDE the mask) | the **bare** rail |
| `8000` (one bit, INSIDE the mask) | the rail **ANDed with SP** |
| `0000` | an AND of two different sentinels |
| `cc00`-class (four bits) | a wired **OR** |
| `f0f0` | the plain stack address (`SP`'s own bit 4 belongs to no sentinel) |

**Every candidate value names itself.** That is the property the banked corpus
does not have and cannot be given.

### §1.2 The segments

`CS 0800 / SS 2000 / DS 4000 / ES 6000` — bases `0x08000 / 0x20000 / 0x40000 /
0x60000`, chosen so the four 64 KB windows are **pairwise disjoint** and the
(segment, offset) decode of a 20-bit pin address is **unique**. The board's
memory is the 64 KB image mirrored through 1 MB, so every one of them addresses
the same bytes.

### §1.3 The program

`R = 5` identical blocks of `BLOCK = 32` bytes: `<pre>` (the rail-loading
preamble and the predecessor class), then `8F C3` (POP BW, `mod = 3`), then NOP
pad. Every block re-arms `SP` with `MOV SP, imm16`, so the 5 blocks are **5
independent repeats of one measurement**, not a drifting sequence. The tail
re-arms `SP` to a safe stack and falls into the `0xCC` (INT3) fill, which
reaches `testimage`'s own terminator. **The cell drives NO PIN**: no `evt`, no
hold, no `fired`, none of INV-1's directive-truncation exposure.

Axes: **`waits` 0-3** and **`align` 0-3** (NOPs ahead of block 0, which moves
every block's byte phase against the word-aligned fetch, i.e. the
queue-alignment axis). **19 legs × 4 × 4 = 304 cells.**

### §1.4 The reader

`8F` `mod=3` issues exactly ONE memory read. The test phase runs from the anchor
`CODE` T1 to the first vector-3 read or the first `IOW`; inside it the MEMR
cycles are grouped `R × (n_pre + 1)`, the first `n_pre` of each group are
checked against the composed preamble addresses (`pre_ok`), and the last is the
**ghost**. Nothing in the reader decodes an opcode, runs an engine or consults a
golden. Full per-clock words are retained with a `sha256` per cell.

## §2 THE OFFLINE MEASUREMENT THAT MAKES THE PREDICTIONS NUMBERS

`ghost_pred_cell rails` freezes the **core** at each leg's own ghost row through
**M10-SYS** (`+ss_at`, read-only, wave-9's instrument) — with M10's own
calibration, sweeping `d ∈ [-12,+1]` and taking the clock at which
`SSA_B_CUR_ADDR` **is** the ghost address, because *a register read at the wrong
clock is a fitted number*. Every leg calibrates at **`d = -1`**.

This characterises the **STIMULUS** — what this program puts in which named
register. It is not silicon and nothing about silicon is derived from it; it is
what turns *"hypothesis H-A"* into *"H-A predicts THIS 20-bit number on THIS
leg"*, which is M10's own method.

**What it measures, and it is disclosed in full because it is the cell's own
falsifier** (`sw/testdata/ghost-pred/rails/rails.json`):

* the **ALU result is what lands in `TMPA`** (and in `IND` and `EA_RESIDUE`), so
  the three `ADD` legs put a **chosen sentinel** in the rail: `alu88` → `8800`,
  `alu44` → `4400`, `alu08` → `0088`, `mul` → `1100`, `imul` → `1100`;
* `ea_residue` is **not an EA** in this RTL — `v30u_eu.sv:3274` loads it from
  `tmpa_n` when `TMPA` moves, so it is a one-deep `TMPA` history and
  `ghost_uses_ea = (ea_residue != tmpa)` is *"TMPA changed"*;
* **on the POP legs the degeneracy is NOT broken in the core's registers**:
  `pop1`/`pop2` have `TMPA = TMPB = IND = EA_RESIDUE = SP = f0f0`, exactly
  M10-SYS's three-way degeneracy. It is disclosed here, before the run, and it
  is precisely why those legs are registered against **H-E** and nothing else:
  the last BUS address there is `0x8800` and **no core register holds it**.

## §3 THE FIVE HYPOTHESES

| id | statement |
|---|---|
| **H-A** | wave-4's landed law: the rail, ANDed with `SP`, **UNCONDITIONALLY** |
| **H-B** | the AND happens **iff the EA path was the last writer** of the address latch (the best available form of *"AND only when …"*) |
| **H-C** | M10-SYS's two undecorated seats **generalised**: the AND never happens |
| **H-D** | the null: the ghost is the plain stack address `SS:SP` |
| **H-E** | wave-6's stale-MAR reading: the ghost is the **last bus address**, segment and all |

H-A/H-B/H-C are the RTL's own expression (`v30u_eu.sv:1481-1493`) evaluated on
the leg's own frozen registers — transcribed, with **no free parameter**.

## §4 THE REGISTERED PER-LEG PREDICTIONS

Committed as `sw/testdata/ghost-pred/predictions.json`. `--` = the hypothesis
makes no prediction on that leg (declared **NON-DISCRIMINATING IN ADVANCE**).

| leg | band | rail | H-A | H-B | H-C | H-D | H-E |
|---|---|---|---|---|---|---|---|
| `alu88` | **D3** | `8800` | **SS:A_POP&SP** | SS:A_POP | SS:A_POP | SS:SP | -- |
| `alu44` | **D3** | `4400` | **SS:E1&SP** | SS:E1 | SS:E1 | SS:SP | -- |
| `alu08` | **D3** | `0088` | **SS:V1&SP** | SS:V1 | SS:V1 | SS:SP | -- |
| `mul` | **D3** | `1100` | **SS:E3&SP** | SS:E3 | SS:E3 | SS:SP | -- |
| `imul` | **D3** | `1100` | **SS:E3&SP** | SS:E3 | SS:E3 | SS:SP | -- |
| `mem3` | **D2** | `cb40` | SS:`c040` | SS:`c040` | SS:`cb40` | SS:SP | DS:E3 |
| `mem3r` | **D2** | `cb20` | SS:`c020` | SS:`c020` | SS:`cb20` | SS:SP | DS:E1 |
| `mem1` | D2 | `0000` | SS:ZERO | SS:ZERO | SS:ZERO | SS:SP | DS:E3 |
| `memw` | D2 | `0000` | SS:ZERO | SS:ZERO | SS:ZERO | SS:SP | DS:E2 |
| `popmem` | D2 | `0000` | SS:ZERO | SS:ZERO | SS:ZERO | SS:SP | DS:E3 |
| `pfxmem` | D2 | `0000` | SS:ZERO | SS:ZERO | SS:ZERO | SS:SP | **ES:E3** |
| `mov8e` | D2 | `f0f0` | SS:SP | SS:SP | SS:SP | SS:SP | DS:E_SEG |
| `pop1` | **D1** | `f0f0` | SS:SP | SS:SP | SS:SP | SS:SP | **SS:A_POP** |
| `pop2` | **D1** | `f0f0` | SS:SP | SS:SP | SS:SP | SS:SP | **SS:A_POP+2** |
| `mempop` | D1 | `0000` | SS:ZERO | SS:ZERO | SS:ZERO | SS:SP | SS:A_POP |
| `pop0` | X | `0000` | SS:ZERO | SS:ZERO | SS:ZERO | SS:SP+2 | SS:SP |
| `pfxpro` | X | `0000` | SS:ZERO | SS:ZERO | SS:ZERO | SS:SP | DS:E3 |
| `n_pop` | **N** | -- | SS:SP | SS:SP | SS:SP | SS:SP | SS:SP |
| `n_mod0` | **N** | -- | SS:SP | SS:SP | SS:SP | SS:SP | SS:SP |

**D3 separates H-A from {H-B, H-C} on FIVE legs. D2 (`mem3`/`mem3r`) separates
{H-A, H-B} from H-C. D1 (`pop1`/`pop2`) separates H-E from all four.** Together
they name exactly one — **or none of them, which is a finding and will be
reported as one**.

## §5 THE BARS, REGISTERED BEFORE CONTACT

| id | bar | how it can fail |
|---|---|---|
| **G-1** | all **304** cells captured; **≥ 95 %** structurally valid (`ok`) and `pre_ok` | fewer, or a leg with 0 valid cells |
| **G-2** | **THE NULL CONTROLS**: `n_pop` and `n_mod0` read `SS:f0f0` on **100 %** of their blocks (160 blocks) | any other address — and if this fails the reader is wrong and NOTHING else in the cell may be quoted |
| **G-3** | the ghost address is **UNIFORM across the 5 blocks** of a cell on ≥ 90 % of valid cells | non-uniformity is reported per cell, never averaged away |
| **G-4** | the D3 band gives ONE verdict: either **all five legs ANDed** (H-A) or **all five bare** (H-B/H-C) | a split D3 band means the predicate is finer than "predecessor class" and the cell says so |
| **G-5** | **STABILITY**: every 8th cell captured 3× — identical `ghost_addr` on **100 %** of repeats (≈ 12.5 % of cells, above the 5 % floor) | any disagreement is a rig finding and outranks the measurement |
| **G-6** | the **mod ≠ 3 control** (`n_mod0`) is identical chip-vs-core on 100 % of its 16 cells — FLASH #13's 130/130 reproduced on a directed program | any divergence |
| **I-1** | single-writer asked of the board (`uptime` + `ps` + local `pgrep`) and **OK** before the first capture | anything else → STOP |
| **I-2** | `div_guard` **PINNED** at every stratum boundary (21 guards) | UNPINNED is a rig-integrity FINDING, recorded, not smoothed |
| **I-3** | **0 transport errors**; three consecutive → STOP | — |
| **I-4** | `use_core` **False** on every command; `flash_log.jsonl` **21 entries** before and after | — |
| **I-5** | `board_idle()` and `check_ab_hw chip 800` **MATCH** after the last capture | — |

**STOP CONDITIONS**: a failed single-writer check; a `RigMismatch`; three
consecutive transport errors; an UNPINNED `div_guard`. Any of them outranks the
measurement and ends the cell with the data taken so far retained.

## §6 WHAT IS *NOT* CLAIMED

* **No RTL is written, built or scored.** This is a measurement wave; the RTL
  candidate it produces is BOOKED for the next one, with its own
  pre-registration and its own G6.
* **The 15-seat wave-8 HOLDOUT stays SEALED.** No seat of it is solved, scored
  or inspected here, and no banked seed is replayed.
* **No closure count is registered.** The F18 residue's ghost population is 29
  `P4` seats of 39 in family `E1`, and W7 §4.2 / W8 §4.1 have both measured that
  most of them carry thousand-row cascades a ghost-address law cannot zero.
  A **predicted reach** will be reported in the results, honestly, with the
  cascade-bound seats named as registered NON-closures.
* **The core column is not the reference** (CLAUDE.md, 2026-08-04). It is taken
  on `tb_sys ret` on the identical stimulus so the measured silicon predicate
  can be put beside the engine's cell for cell.

## §7 THE OFFLINE ARTEFACTS COMMITTED WITH THIS DOCUMENT

```
sw/ghost_pred_cell.py                       the cell
sw/testdata/ghost-pred/predictions.json     §4, machine-readable
sw/testdata/ghost-pred/calib.json           capture depth per wait (instrument)
sw/testdata/ghost-pred/rails/rails.json     §2, the frozen rails + the d-walk
sw/testdata/ghost-pred/core/                the 304-cell tb_sys ret column
```

`core/` is **304 / 304 structurally valid, `pre_ok` 304 / 304**, taken on
`tb_sys ret`, and it is committed BEFORE the board so it cannot be retrofitted.

## §8 RE-RUNNING THIS

```bash
git rev-parse HEAD                                  # 770c0d1b85 + this commit
python3 sw/ghost_pred_cell.py show                  # the programs + the alphabet
python3 sw/x1_retention.py build --leg ret          # the offline instrument
python3 sw/ghost_pred_cell.py calib                 # instrument setting only
python3 sw/ghost_pred_cell.py rails                 # the frozen rails (M10-SYS)
python3 sw/ghost_pred_cell.py predict               # §4
python3 sw/ghost_pred_cell.py core                  # the ucore's own column
python3 sw/ghost_pred_cell.py run                   # BOARD, socket only
python3 sw/ghost_pred_cell.py score
python3 sw/ghost_pred_cell.py idle
python3 sw/check_ab_hw.py chip 800
```
