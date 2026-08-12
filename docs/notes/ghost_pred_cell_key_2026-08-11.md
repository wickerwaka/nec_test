# THE `dQS` KEY — FROZEN, AND THE DISJOINT VALIDATION REGISTERED BEFORE IT RUNS

Branch `fuzz-v2-on-relanding`, base **`cf5defee5f`** (the pre-registration
commit). **Committed BEFORE the six validation legs are captured.** Board
contact so far: the registered 304-cell grid + the 128-cell post-hoc sled
family, socket only, `flash_log.jsonl` **21**, 0 transport errors.

---

## §1 WHY THIS DOCUMENT EXISTS

The registered grid (`ghost_pred_cell_prereg_2026-08-11.md` §4) **refuted all
three registered hypotheses at once**: with the rail, the predecessor and the
program held fixed, silicon ANDs on some `(waits, align)` cells and not on
others. So the predicate is a **cycle-level state at the probe**, and the
obvious question — *which* state — was answered by SCANNING the capture.

**A key found by scanning is a fitted key.** The standing rule
(CLAUDE.md): *"A refuted key's REPLACEMENT must be validated on data that was
not used to select it … choosing its successor by scanning the same capture and
then scoring the successor on that capture is fitting, and the score is not
evidence."* This document freezes the key and registers its validation on a
population that did not exist when it was chosen.

## §2 THE KEY

For each ghost read, `dQS` = **the number of clocks from the last `QS == 1`
(opcode pop) row to the ghost read's own `T1` row**, read off the pins.

`QS = 1` is not a quantity invented here: it is the SAME sampling boundary
`ucore_provenance.md` §86 registers for the BRK/TF arm — *"the `QS = 1` opcode
pop, because a prefix retires with its own F pop"*.

```
  dQS == 1  ->  AND       dQS == 5  ->  SP        dQS == 4  ->  (NOT OBSERVED,
  dQS == 2  ->  BARE      dQS == 6  ->  AND                      the key is
  dQS == 3  ->  BARE      dQS >= 7  ->  BARE                     SILENT)
```

In code: `ghost_pred_cell.KEY` / `key_of()` / `dqs_of()`. Three outcomes, not
two: `BARE` = the rail undecorated, `AND` = the rail ANDed with `SP`, `SP` = the
plain stack address.

### §2.1 Its accuracy ON THE SET THAT SELECTED IT — which is NOT evidence

Derivation set: the **nine** legs of the registered grid whose rail carries a
bit outside `SP`'s mask (`alu88 alu44 alu08 mul imul memw pfxpro mempop
mov8e`) × 16 cells × 4 steady-state blocks (block 0, the cold block, is
excluded and said so) = **576 blocks**.

| `dQS` | AND | BARE | SP | key | correct |
|---:|---:|---:|---:|---|---:|
| 1 | 144 | 32 | 0 | AND | 144 / 176 |
| 2 | 0 | 160 | 0 | BARE | 160 / 160 |
| 3 | 0 | 88 | 0 | BARE | 88 / 88 |
| 5 | 0 | 0 | 48 | SP | 48 / 48 |
| 6 | 48 | 0 | 0 | AND | 48 / 48 |
| 7 | 0 | 48 | 0 | BARE | 48 / 48 |
| 8 | 0 | 8 | 0 | BARE | 8 / 8 |

**544 / 576 = 94.4 %**, and the ONLY impure bin is `dQS == 1`.

⚠ **THE KEY IS A SEVEN-ROW TABLE AND THE SIMPLICITY PRINCIPLE SAYS THAT IS A
SIGNAL OF MISUNDERSTANDING, NOT A DELIVERABLE.** It is non-monotone
(1 AND, 2-3 BARE, 5 SP, 6 AND, 7+ BARE). It is registered here as an
INSTRUMENT — a testable statement about silicon — **not** as a law, and no RTL
is proposed from it. What it is FOR is to establish that the predicate is a
cycle-level quantity at all, on data that did not select it.

## §3 THE DISJOINT VALIDATION POPULATION, AND ITS BAR

**Six legs that did not exist when the key was chosen**, each reaching a rail by
a different opcode of a different length:

| leg | predecessor | core rail (measured offline, `rails`) | usable? |
|---|---|---|---|
| `v_sub` | `SUB AW,BW` = 0x8800 | `8810` | **YES** (`&SP` = `8010`) |
| `v_or` | `OR AW,BW` = 0x8800 | `8800` | **YES** (`&SP` = `8000`) |
| `v_inc` | `INC AW` — ONE byte | `0fff` | **YES** (`&SP` = `00f0`) |
| `v_lea` | `LEA AW,[0x8800]` — ModR/M, no memory access | `78f0` | **YES** (`&SP` = `70f0`) |
| `v_shl` | `SHL AW,1` | `1000` | **NO — DEGENERATE**, declared now |
| `v_neg` | `NEG AW` | `0000` | **NO — DEGENERATE**, declared now |

**Four usable legs × 16 cells × 4 steady blocks = 256 blocks**, none of which
was seen when the key was frozen.

| id | bar |
|---|---|
| **K-1** | the key, applied UNCHANGED, is correct on **≥ 85 %** of the 256 validation blocks (its derivation-set figure is 94.4 %, and a validation bar above the derivation figure would be dishonest) |
| **K-2** | the two DEGENERATE legs are declared here, IN ADVANCE, and are reported but not scored |
| **K-3** | a `dQS == 4` block is reported as **NOT PREDICTED**, never as a miss and never as a hit |
| **K-4** | a leg whose CHIP rail is neither the core's `X` nor `X & SP` nor `SP` is reported as **RAIL DISAGREES**, scored as a miss, and named |
| **K-5** | if K-1 misses, the key is **REFUTED** and the results document says so; no repaired key may then be scored on this same data |

## §4 WHAT IS STILL NOT CLAIMED

No RTL. No closure count. The wave-8 HOLDOUT stays sealed. The key is an
instrument for the next wave's derivation, and the next wave owes a MECHANISM
that produces this table rather than a table that reproduces it.
