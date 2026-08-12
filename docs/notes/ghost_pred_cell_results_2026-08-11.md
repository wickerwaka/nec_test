# THE `8F` GHOST-READ **PREDICATE** — DIRECTED BOARD CELL — RESULTS

Pre-registration: `docs/notes/ghost_pred_cell_prereg_2026-08-11.md`, committed
**`cf5defee5f`, before the first board command**. The key registration:
`docs/notes/ghost_pred_cell_key_2026-08-11.md`, committed **`b70dbb32f0`, before
the validation legs were captured**. Read them first; this document answers them
clause by clause.

Branch `fuzz-v2-on-relanding`, base **`770c0d1b85`** (`git rev-parse HEAD`
verified). **MAIN checkout. CAPTURE ONLY — socket (`use_core=False`, explicit),
NO FLASHING (FLASH #18 resident, `flash_log.jsonl` **21 entries** before and
after), NO RTL CHANGE, no Quartus, `sim/` not extended, the wave-8 HOLDOUT
SEALED.**

---

## §0 HEADLINE

| | |
|---|---|
| **The degeneracy** | **BROKEN BY CONSTRUCTION.** Every value on the pins names itself: `X`, `X & SP`, `X & Y`, `X \| Y` and `SP` are all distinct by design, and the popped DATA confirms the address decode independently. |
| **H-A** (wave-4's unconditional AND) | **REFUTED.** On `alu88_w2_a0` the chip reads `SS:8800` — the rail BARE — where H-A predicts `SS:8000`. |
| **H-B** (AND iff the EA path wrote last) | **REFUTED.** The predecessor, the rail and the program are IDENTICAL across the cells that AND and the cells that do not; only `waits` and `align` move. |
| **H-C** (never AND, M10-SYS generalised) | **REFUTED.** On `alu88_w0_a0` the chip reads `SS:8000` — the rail ANDed with `SP` — 80 blocks of 80. |
| **H-E** (wave-6's stale MAR) | **REFUTED.** `pop1`/`pop2` put the last bus address at `SS:8800` and `SP` at `SS:f0f0`, **0x8800 apart**; the chip reads `SS:f0f0` on **64/64 STEADY blocks** (78/80 and 79/80 counting the cold block 0). Silicon does **not** read the stale bus address. |
| **WHAT IT IS INSTEAD** | **A CYCLE-LEVEL STATE AT THE PROBE, AND THERE ARE THREE OUTCOMES, NOT TWO**: the rail BARE, the rail `& SP`, and the plain stack address `SS:SP`. |
| **The measured key** | `dQS`, the clocks from the last `QS = 1` opcode pop to the ghost `T1`. **94.4 % (544/576)** on the set that selected it; **100.0 % (224/224), ZERO misses**, on a **disjoint** validation family built afterwards. |
| **K-1 as registered** | **MISSED — 75.0 %**, and it is reported as MISSED. Every one of the 56 shortfalls is `v_lea`'s **K-4 RAIL DISAGREES**, not a single decoration error. §3.1. |
| **Second finding** | **`ghost_uses_mul_hi` IS NOT INERT.** The key's ONLY impure bin is entirely and exactly `mul` and `imul` at `w1`/`w2` — 32 blocks of 32. Wave-4 §7's *"cheapest remaining simplification"* is **REFUTED: do not delete it.** |
| **Third finding** | **`LEA` DIVERGES ON THE RAIL ITSELF.** On `LEA AW,[0x8800]` — a ModR/M form with **no memory access** — the chip's rail is `0x8800`, the LEA's own EA; the ucore's is `0x78f0`. |
| **Retro-prediction** | **2 of 2** on M10-SYS's two speaking seats: both land in the key's `dQS = 5 → SP` bin, and both are measured `SS:SP` undecorated. §7. |
| **Integrity** | 528 board cells, **520 structurally valid**, 8 invalid for a NAMED reason (§4.4). **0 transport errors, every `div_guard` PINNED, 66/66 stability repeats byte-identical**, `board_idle` clean, `check_ab_hw chip 800` **MATCH over 800 rows** after. |
| **RTL** | **NONE. Nothing built, nothing landed, no G6.** The key is a seven-row non-monotone table and the SIMPLICITY principle says that is a signal of misunderstanding: it is an INSTRUMENT, and §8 books the mechanism it points at. |

---

## §1 THE INSTRUMENT, AND WHY IT WORKS WHERE THE CORPUS COULD NOT

`SP = 0xF0F0` is a **mask**; every other sentinel carries exactly one bit inside
it and one bit outside it, no two sharing either bit:

```
SP f0f0   A_POP 8800   E1 4400   E2 2200   E3 1100   V1 0088   V2 0044   E_SEG 0022
```

Four segments at pairwise-disjoint 64 KB windows (`CS 08000 / SS 20000 /
DS 40000 / ES 60000`) make the (segment, offset) decode of a 20-bit pin address
unique. `R = 5` identical 32-byte blocks per image give five independent
repeats; block 0 is the COLD block and is excluded from every scored figure and
said so.

**The independent confirmation that the decode is right**: the popped DATA. A
recognisable word is planted at every candidate address, so `alu88_w0_a0` reads
`0x28000` and returns `db20` — the word planted at `A_POP & SP` — while
`alu88_w1_a1` reads `0x2f0f0` and returns `da10`, the word planted at `SP`. The
address channel and the data channel agree on every scored block.

**THE READER'S POSITIVE CONTROL PASSES (G-2): `n_pop` 80/80 and `n_mod0` 80/80
blocks at `SS:f0f0` exactly.** `n_mod0` is `8F /0` with a real ModR/M memory
operand — FLASH #13's mod ≠ 3 control, reproduced on a directed program, and it
is **identical chip-vs-core on 16 of 16 cells (G-6 MET)**.

### §1.1 The construction's own falsifier, run BEFORE the board

`ghost_pred_cell rails` freezes the core at each leg's ghost row through
**M10-SYS**, with M10's own calibration (sweep `d ∈ [-12,+1]`, take the clock at
which `SSA_B_CUR_ADDR` **is** the ghost address). Every leg calibrated at
`d = -1`. Two things it measured, both disclosed in the pre-registration:

* **the ALU RESULT is what lands in `TMPA`** — which is why the three `ADD` legs
  can put a *chosen* sentinel in the rail, and they do: `8800`, `4400`, `0088`;
* **`ea_residue` is not an EA at all** — `v30u_eu.sv:3274` loads it from
  `tmpa_n`, so it is a one-deep `TMPA` history and `ghost_uses_ea` means
  *"TMPA moved"*. Three waves have reasoned about it as a retained EA.

---

## §2 THE REGISTERED GRID — 19 LEGS × 4 WAITS × 4 ALIGNS

The chip's ghost address, per leg, `align` across, `waits` down. `AND` =
`rail & SP`, `BARE` = the rail, `SP` = the plain stack address.

```
alu88 (rail 8800)      alu44 (rail 4400)      alu08 (rail 0088)
     a0   a1   a2   a3      a0   a1   a2   a3      a0   a1   a2   a3
 w0 AND BARE AND BARE   AND BARE AND BARE   AND BARE AND BARE
 w1 AND  SP  AND  SP    AND  SP  AND  SP    AND  SP  AND  SP
 w2 BARE AND BARE AND   BARE AND BARE AND   BARE AND BARE AND
 w3 BARE BARE BARE BARE BARE BARE BARE BARE BARE BARE BARE BARE

mul (rail 1100)        imul (rail 1100)       memw (rail fc40)
 w0 AND BARE AND BARE   BARE AND BARE AND    AND AND AND AND
 w1 BARE BARE BARE BARE BARE BARE BARE BARE  AND AND AND AND
 w2 BARE BARE BARE BARE BARE BARE BARE BARE  BARE BARE BARE BARE
 w3 BARE BARE BARE BARE BARE BARE BARE BARE  BARE BARE BARE BARE

mempop (rail cb40)     mov8e (rail 0022)      pfxpro (rail eb50)
 w0 AND AND AND AND     BARE BARE BARE BARE   AND BARE AND BARE
 w1 AND  SP  AND  SP    SP   SP   SP   SP     BARE AND BARE AND
 w2 BARE AND BARE AND   AND  AND  AND  AND    BARE BARE BARE BARE
 w3 BARE BARE BARE BARE BARE BARE BARE BARE   AND BARE AND BARE
```

**Three readings, all of them registered predictions falling:**

1. **`align` matters only mod 2** — `a0 ≡ a2` and `a1 ≡ a3` on **every one of
   the 27 legs at every wait level, without exception**. `BLOCK = 32` is even,
   so the only thing `align` changes is the block's **byte parity**. That is an
   internal consistency check the cell did not have to pass and did.
2. **The same program, the same rail, the same predecessor — and the decoration
   flips with `waits` and with byte parity.** No predecessor-type law and no
   rail law can produce that table. H-A, H-B and H-C are refuted together.
3. **There are THREE outcomes.** `SP` — the plain stack address, the ucore's own
   `(eu_ghost_idle && !q_ripe) ? gpr[R_SP]` arm — is a real, reproducible third
   state occupying whole rows of the table.

### §2.1 H-E is REFUTED, and this is the first time it could be asked

`pop1` puts the last bus address at `SS:8800` and `SP` at `SS:f0f0`. **The chip
reads `SS:f0f0` on 64 of 64 STEADY blocks** — and on `pop2` and `pop0` alike.
Counting the cold block 0 as well the figures are 78/80, 79/80 and 78/80: the
five exceptions across the three legs are **all block 0**, all at `SS:f8f0`, and
they are reported and excluded by the standing block-0 rule, not explained.

Silicon does **not** reuse the stale bus address. Wave-6's *"the ghost read
reuses the last-latched memory-address register"* is refuted on a program built
specifically to let it show, and wave-7's `IND` probe — which lost two seeds —
was refuted for the right reason.

---

## §3 THE KEY, AND ITS DISJOINT VALIDATION

`dQS` = clocks from the last `QS = 1` (opcode pop) row to the ghost `T1`.
`QS = 1` is **`ucore_provenance.md` §86's own sampling boundary**, not a quantity
invented here.

```
  dQS == 1 -> AND     dQS == 5 -> SP      dQS == 4 -> NOT OBSERVED (silent)
  dQS == 2 -> BARE    dQS == 6 -> AND
  dQS == 3 -> BARE    dQS >= 7 -> BARE
```

| set | blocks | result |
|---|---:|---|
| **DERIVATION** — the nine discriminating legs (**the set that SELECTED the key; NOT evidence**) | 576 | **544 / 576 = 94.4 %**, the only impure bin `dQS == 1` |
| **VALIDATION as registered** (`v_sub v_or v_inc v_lea`, K-4 in force) | 224 | **168 / 224 = 75.0 % — K-1 MISSED** |
| **VALIDATION, secondary and LABELLED** (classified against the chip's OWN rail) | 224 | **224 / 224 = 100.0 %, ZERO decoration misses** |

Per-bin on the disjoint set: `dQS 1 → AND ×64`, `2 → BARE ×48`, `3 → BARE ×24`,
`5 → SP ×32`, `6 → AND ×32`, `7 → BARE ×24`. **Six of the key's seven rows are
exercised and every one is exact.**

### §3.1 K-1 IS REPORTED AS MISSED, AND THE REASON IS ONE LEG

All 56 shortfalls are `v_lea`, and none of them is a decoration error: K-4 says
*"a leg whose CHIP rail is neither the core's `X` nor `X & SP` nor `SP` is
reported as RAIL DISAGREES, scored as a miss, and named"*. It is named in §6.
The registered figure stands at **75.0 %** and is not restated.

### §3.2 THE IMPURE BIN IS THE MULTIPLY CLASS, EXACTLY AND ONLY

The 32 derivation-set misses are **all** `mul` and `imul`, and **only** at
`w1` and `w2` — 8 blocks each, 32 of 32. Every other leg in the `dQS == 1` bin
is `AND` without exception.

`mul` and `imul` are the only long multi-cycle predecessors in the set, and they
are exactly the class `v30u_eu.sv:1487`'s `ghost_uses_mul_hi` names (the
`14'h0104` native PLA class, `69`/`6B`). **Wave-4 §2.1 measured that arm INERT
on 654 banked seeds and §7 booked its deletion as *"the cheapest remaining
simplification … it needs a population that reaches them"*.** This population
reaches it. **The arm is NOT inert and the booked deletion is REFUTED.**

---

## §4 THE REGISTERED BARS, ANSWERED

| id | registered | outcome |
|---|---|---|
| **G-1** | 304 cells, ≥ 95 % structurally valid | **MET** — 304/304 on the registered grid, `pre_ok` 304/304. Over all 528 cells captured (grid + post-hoc sled + validation) it is **520/528 = 98.5 %**, the 8 exceptions named in §4.4 |
| **G-2** | the NULL controls read `SS:SP` on 100 % of 160 blocks | **MET — 80/80 and 80/80** |
| **G-3** | the ghost address uniform across the 5 blocks on ≥ 90 % of valid cells | **MET on the steady blocks — 520/520 = 100 %.** Block 0 differs on 5 cells (`pop0`/`pop1` ×2, `pop2` ×1) and is excluded by the standing rule, which was written before the run |
| **G-4** | the D3 band gives ONE verdict | **MISSED, AND THAT IS THE RESULT.** The band is split *within each leg*, by `waits` and byte parity. The registered text: *"a split D3 band means the predicate is finer than 'predecessor class' and the cell says so."* It is finer, and this is the cell saying so |
| **G-5** | every 8th cell 3×, identical ghost addresses on 100 % | **MET — 66 repeat groups, 66/66 identical ghost addresses AND 66/66 byte-identical capture words** |
| **G-6** | `n_mod0` identical chip-vs-core on 16/16 | **MET — 16/16** |
| **I-1** | single-writer OK before first capture | **MET** — `uptime` returned, no `v30ctl`/`serve` on the board, no local serve client, at each of the four `run` invocations |
| **I-2** | `div_guard` PINNED at every stratum boundary | **MET — 42 guards over four invocations, every one PINNED.** ⚠ instrument note: `manifest.json` is rebuilt per invocation and retains the last one's 8; the other 34 are in the run transcripts |
| **I-3** | 0 transport errors | **MET — 0**, no `RigMismatch`, no retry |
| **I-4** | `use_core` False; `flash_log.jsonl` 21 before and after | **MET — False on every command, 21 → 21** |
| **I-5** | `board_idle()` and `check_ab_hw chip 800` MATCH after | **MET — `board_idle` clean, `chip-vs-golden: MATCH over 800 rows`** |
| **K-1** | ≥ 85 % on 256 disjoint validation blocks | **MISSED — 75.0 %** (§3.1) |
| **K-2** | `v_shl`/`v_neg` declared degenerate in advance | **HELD** — reported, not scored; and both corroborate the `dQS = 5 → SP` row (24 blocks) which is the one outcome their degeneracy does not hide |
| **K-3** | a `dQS == 4` block is NOT PREDICTED | **HELD** — `dQS == 4` never occurred, in either set |
| **K-4** | RAIL DISAGREES is a named miss | **HELD — `v_lea`, 56 blocks, §6** |
| **K-5** | if K-1 misses, no repaired key may be scored on the same data | **HELD** — the key in `ghost_pred_cell.KEY` is byte-identical to `b70dbb32f0`'s and was not touched after the validation capture |

### §4.4 THE EIGHT INVALID CELLS ARE A FINDING, NOT A DEFECT

All eight are `v_inc`, and all eight report *"10 MEMR cycles, expected 5
`[= R*(n_pre+2)`: every probe read may have SPLIT]"* — the message the reader
was given before the run. **`v_inc`'s rail is `0x0FFF`, the only ODD rail in the
cell, and the ghost word SPLITS**: the pins read `SS:0fff` then `SS:1000`, i.e.
`acc_split` / `acc_phys2`'s own case, on silicon, in a directed program. They
are retained, reported and not scored — and they are the only cells in which
`v_inc`'s rail is seen BARE at all.

---

## §5 CHIP vs CORE

**275 of 520 valid cells have identical ghost addresses; 245 differ.** The core
is essentially H-A with its `SP` escape arm: it ANDs on 14 of 16 cells of every
`D3` leg and takes `SP` on the other 2, with no dependence on byte parity at
all. The chip's dependence on byte parity has no counterpart in the ucore.

The `SP` outcome is where the two engines come closest: the ucore already
carries the arm (`(eu_ghost_idle && !q_ripe) ? gpr[R_SP]`, wave-4's V2, measured
`+2 closed / 1 LOST`) — **it fires in the wrong cells.** M10-SYS §4.5 put it
exactly: *"on `524030` and `529067` that arm's answer is the right one and the
arm did not fire."* §7 shows the key names when it should.

---

## §6 THE `LEA` RAIL DIVERGENCE — THE WAVE'S SECOND MECHANISM

`v_lea`'s predecessor is `LEA AW,[0x8800]` — a ModR/M form that computes an
effective address and **performs no memory access**.

* the ucore's rail there is **`0x78f0`** (`TMPA`, read out of the save-state map
  at the calibrated freeze);
* the chip's is **`0x8800` — the LEA's own EA** — seen BARE on 32 blocks and
  ANDed to `0x8000` on 24, with `SP` on 8.

So on `LEA` the two engines put **different values** on the ghost rail, and the
chip's is the EA. This is the *"WHICH RAIL"* free choice that wave-4 left
standing, caught on a directed leg with no memory cycle to confuse it. It is
**BOOKED, not landed** — one leg is one leg, and the population that would
validate a rail change does not exist yet.

---

## §7 RETRO-PREDICTION ON THE BANKED SEATS — 2 OF 2

The key is applied, unchanged, to the banked chip rows of the seats whose
decoration is measured, at the fork row the M10 survey names (anchor verified:
`bs == MEMR`, `t == T1`, `ad_addr == chip_addr`).

| seat | `dQS` | key says | measured |
|---|---:|---|---|
| `fz2e/524030` | **5** | **SP** | `SS:SP` undecorated, bit-exact (M10-SYS §4.4) — **HIT** |
| `fz2e/529067` | **5** | **SP** | `SS:SP` undecorated, bit-exact (M10-SYS §4.4) — **HIT** |

**Both of M10-SYS's speaking seats fall in the key's `dQS = 5 → SP` bin, which
is the bin the directed cell measures at 48/48 and validates at 32/32.** The
seat that could not be explained by any rail — because `SP`, `TMPB` and `IND`
were degenerate on it — is explained by the key without needing to know which
rail it was: at `dQS = 5` the part does not use a rail at all.

> ⚠ **A THIRD SEAT WAS ATTEMPTED AND THE TEST IS INVALID, WHICH IS SAID RATHER
> THAN DROPPED.** `fz2c/410008` is wave-4's ANDed seat, and its F18 fork row is
> **1199**, not the row 1192 whose decoration wave-4 measured — wave-4 §3.2 says
> in terms that row 1192 *"now MATCHES"* and the seed *"keeps failing from row
> 1198 … on something this package does not own."* The key evaluated at row 1199
> says `BARE`; that is a prediction about a **different** bus cycle and it is
> **not scored either way**. The retro-prediction is reported as **2 of 2 on the
> seats whose decoration is measured at the surveyed row**, and not as 2 of 3.

---

## §8 PREDICTED REACH INTO THE F18 RESIDUE — HONEST, AND MOSTLY NON-CLOSURE

The F18 ledger's family `E1` carries **39 seats**; **29** are `near_package ==
P4` (an `8F` `mod == 3` one to three pops back) and **26** of those have a
differing `T1` address, i.e. are ghost-ADDRESS seats.

Their cascade sizes (`diverging_rows`) partition them, and W7 §4.2 / W8 §4.1
already warned this is what bounds any ghost-address law:

| `diverging_rows` | seats | disposition |
|---:|---:|---|
| ≤ 8 | **9** | a ghost-address correction could plausibly ZERO them |
| 9-40 | 4 | plausible; the cascade is short |
| 320-3,413 | **13** | **REGISTERED CASCADE-BOUND NON-CLOSURES** — named now, before any landing |

**The honest predicted reach of a correct predicate is therefore AT MOST 13
seats of 3,839, and realistically 9**, and the other 13 ghost-address seats will
still fail after it for reasons this mechanism does not own. No closure count is
claimed and none was registered; this is the number a future landing must be
scored against rather than the number it may promise.

---

## §9 WHAT THE NEXT WAVE INHERITS

1. **A CORPUS THAT CAN BE BUILT AT WILL.** Before this cell the whole world's
   evidence on the decoration question was **five seats**, all with degenerate
   rails. It is now **528 engine-free board cells with a generator**, and any
   proposed predicate must reproduce the tables in §2 cell for cell. That is the
   falsifier, and it costs 11 seconds of board time.
2. **THE KEY, AND WHAT IS WRONG WITH IT.** `dQS` is 94.4 % / 100 % but it is a
   **seven-row non-monotone table**, and the standing principle says that is a
   signal of misunderstanding, not a deliverable. The next wave's job is the
   MECHANISM that produces it. The obvious candidate, and it is the tree's own:
   wave-4 DELETED `ghost_relax`, whose three arms were `eu_ghost_full → FFFF`
   (no AND), `eu_ghost_idle → a mask`, else `0000` (full AND) — a **three-state
   queue-condition gate on exactly this decoration**, discarded because its
   *masks* were a fitted table. **This cell measures three states.** The mask
   table deserved to go; the gating quantity may not have.
3. **`ghost_uses_mul_hi` STAYS.** §3.2 refutes wave-4 §7's booked deletion with
   32 blocks of 32, and the multiply class is the ONE class the key cannot
   predict — which makes it the sharpest place to look next.
4. **THE `LEA` RAIL** (§6), booked with its measurement.
5. **THE 15-SEAT WAVE-8 HOLDOUT IS STILL SEALED.** Not solved, not scored, not
   inspected, and no banked seed was replayed except the two of §7, whose rows
   were read for a `QS` count and nothing else.
6. **A REGISTERED NON-CLOSURE LIST** (§8), so the next landing cannot be
   credited with seats it cannot reach.

---

## §10 DISCIPLINE NOTES

* **The ORDER is the evidence.** `cf5defee5f` (prereg + the offline rails, the
  predictions and the 304-cell core column) precedes the first board command;
  `b70dbb32f0` (the frozen key) precedes the validation capture. Neither was
  amended afterwards.
* ⚠ **A CONCURRENT MERGE LANDED MID-CELL AND IS DISCLOSED.** Another agent's
  offline F18 housekeeping (`a05af666aa` … `05acfff3e0`) merged into this branch
  between the registered grid's capture and the validation capture. **It moves
  no RTL**: `git diff 770c0d1b85 HEAD -- hdl/ sim/` is **EMPTY**, so the
  `tb_sys ret` core column and every offline figure here are the same tree's.
  The consequence to know: `board/manifest.json` records the *last* `run`
  invocation's `git` (`b70dbb32f0`); the registered 304-cell grid and the
  128-cell sled family were captured at `cf5defee5f`. Both are pre-merge
  by content and post-prereg by commit, which is the ordering the cell needs.
* **Three registered bars MISSED and are reported as missed** — G-4, K-1 — and
  one of them (G-4) is missed in the direction that makes the wave's finding
  possible. Nothing is restated.
* **Two post-hoc families are labelled post-hoc in the code and in the data**:
  the 128-cell sled sweep and the `dQS` scan. The scan's product was frozen and
  validated on a population built afterwards, per §64.1.
* **No RTL, no Quartus, no flash, `sim/` not extended.** `flash_log.jsonl` 21
  before and 21 after. Socket only.
* **Full per-clock words retained** — `sw/testdata/ghost-pred/{board,core}/*.raw.json.gz`
  with a `sha256` per cell and a `SHA256SUMS` per directory. The `dQS` scorer
  reads those words, not a digest, which is why it could be written after the
  board was released.

## §11 RE-RUNNING THIS

```bash
git rev-parse HEAD
python3 sw/x1_retention.py build --leg ret
python3 sw/ghost_pred_cell.py show      # the alphabet, the legs, the image shas
python3 sw/ghost_pred_cell.py calib     # instrument setting only
python3 sw/ghost_pred_cell.py rails     # the frozen core rails (M10-SYS)
python3 sw/ghost_pred_cell.py predict   # the registered per-leg predictions
python3 sw/ghost_pred_cell.py core      # the ucore's own column
python3 sw/ghost_pred_cell.py run       # BOARD, socket only, ~20 s
python3 sw/ghost_pred_cell.py score     # 2, the per-leg tables
python3 sw/ghost_pred_cell.py key       # 3, derivation vs disjoint validation
python3 sw/ghost_pred_cell.py idle ; python3 sw/check_ab_hw.py chip 800
```
