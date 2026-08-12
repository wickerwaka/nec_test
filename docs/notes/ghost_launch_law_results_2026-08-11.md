# THE `8F` GHOST-READ DECORATION LAW — THE MECHANISM BEHIND THE `dQS` TABLE

Branch `fuzz-v2-on-relanding`, base **`f0dab185eb`** (`git rev-parse HEAD`
verified; isolated worktree, provisioned at `master` and RESET to the base
before anything was read).

**OFFLINE ONLY. NO BOARD** (`flash_log.jsonl` untouched, no socket command
issued). **NO RTL CHANGED — `git diff f0dab185eb -- hdl/ sim/` is EMPTY**, and
therefore **no Quartus, no G6, no bitstream**; §7 says why and books what a
landing would be. **THE WAVE-8 HOLDOUT IS STILL SEALED** — not opened, not
scored, not inspected. No banked seed was replayed.

Prior documents this answers: `ghost_pred_cell_prereg_2026-08-11.md`,
`ghost_pred_cell_key_2026-08-11.md`, `ghost_pred_cell_results_2026-08-11.md`
§9.2 — *"the next wave's job is the MECHANISM that produces it"*.

---

## §0 HEADLINE

| | |
|---|---|
| **The law** | **THE GHOST READ IS DECORATED AT *LAUNCH*, NOT AT *POST*.** With `dGR` = the clocks the posted ghost read waits for the bus: `dGR == 0` → `SS:SP`; `dGR == 1` → `stale & SP`; `dGR >= 2` → `stale`. |
| **Its shape** | **ONE monotone predicate on ONE quantity.** No opcode is named in it, no modulus, no mask table, no per-class case. Three outcomes because there are **two drivers**: the posting micro-row's `SP` drive is on for phases {0,1} and the stale rail for {1,2,…}; the `AND` is their one-clock overlap. |
| **Score** | **200 / 200 = 100.0 %** — derivation 112/112, **DISJOINT validation 56/56**, **multiply 32/32**. `python3 sw/ghost_launch_law.py score`, exit 0. |
| **The multiply class** | **NOT A SEPARATE MECHANISM.** `ghost_pred_cell_results` §3.2's second finding — the key's only impure bin *"entirely and exactly `mul` and `imul`, 32 blocks of 32"* — is those cells at `dGR` 4 and 5, which every **counting** key aliases onto a low residue and which `dGR >= 2 → BARE` reads correctly. They selected nothing here. ⚠ This does **NOT** authorise deleting `ghost_uses_mul_hi` — §5.3. |
| **Why the table looked like a table** | Two artefacts of its anchor, both measured: it anchored on `QS == 1` when the anchoring event is the **request**, and re-anchored on the last queue op of **any** kind the seven rows become the **contiguous** range `dQ ∈ [1,7]` with the `dQS == 4` hole explained; `dQ mod 4` then partitions **672/672** non-multiply blocks, which is an **ALIAS** of `dGR` valid only while `dGR < 4`. §3. |
| **No free parameter** | `upc_opc == 8'h8f && upc_loc == 4'd4` is **`v30u_eu.sv` line 924's own existing constant** (`ghost_preread_tail`), not a fitted one. The three-way map was read off the seven derivation legs and held **byte-fixed** for the validation and multiply legs. |
| **A negative result that matters** | **NO existing named ucore state reproduces it**: 226 save-state addresses × 12 freeze offsets = **2,712 candidates, 0 pure**. And the **pair** scan is a *fitting swamp* — 1,169 pure pairs on 112 cells, **1,097 of them still 100 % on the "disjoint" set**. §6. That is why the law was derived from the RTL's own ghost-row constant and not chosen by scanning. |
| **The structural finding** | **THE ucore COMPOSES THE GHOST ADDRESS AT THE WRONG CLOCK.** It composes at POST (`eu_addr` → `rq_addr[]`); silicon composes at LAUNCH (`cmt_addr`). This is why no state at the ghost T1 can carry the law: the deciding quantity does not exist yet when the ucore commits to a value. §7. |
| **RTL** | **NONE, and that is a decision with a reason** (§7): the law is a *datapath relocation*, not a predicate swap, and it is booked with its design, its flop count and its own falsifier rather than rushed into a tree whose retention band bottom is **38.82 MHz** against a **38.0 STOP**. |

---

## §1 THE INSTRUMENT, AND WHAT IT COST

Everything here re-runs from bytes already in the tree — the 528 retained board
cells (`sw/testdata/ghost-pred/board/`, `sha256sum -c SHA256SUMS` **clean, 135
files**, both directories) and `tb_sys ret`. The tool is
**`sw/ghost_launch_law.py`** with three subcommands:

```bash
python3 sw/x1_retention.py build --leg ret     # receipt 639c020969258612…
python3 sw/ghost_launch_law.py dq              # the pin-side re-anchoring
python3 sw/ghost_launch_law.py sweep           # ~9 min, 208 cells x 12 freezes
python3 sw/ghost_launch_law.py score           # the law, exit 0
```

`sweep` freezes the ucore through **M10-SYS** across `d ∈ [-10,+1]` around each
cell's own ghost T1 and retains `SSA_E_UPC_LOC` / `SSA_E_UPC_OPC`. `score`
never edits the map.

## §2 THE LAW

`dGR` = the number of clocks between

* **(a)** the FIRST clock on which the `8F` ghost read's own micro-row is
  current — `upc_opc == 8'h8f && upc_loc == 4'd4` — i.e. the clock the read is
  **POSTED**, and
* **(b)** the clock the BIU **LAUNCHES** the bus cycle: the ghost read's T1.

```
   dGR == 0   ->  SS:SP          the posting micro-row's own stack drive, alone
   dGR == 1   ->  stale & SP     both drivers on the rail -- the wired AND
   dGR >= 2   ->  stale          the row has released; only the stale rail
```

**In one sentence.** *The internal address rail is driven by the posting
micro-row while that row is current; the stale rail re-asserts one clock after
the row retires; the `AND` is the one-clock overlap.* Which is the same
sentence `v30u_biu.sv:691` already writes for the neighbouring case — *"later
phases leave the undocumented 8F register-POP address fighting the stack
rail"* — with the phase finally named.

### §2.1 It is TWO drivers, not three outcomes

| | SP driver | stale driver | result |
|---|---|---|---|
| `dGR == 0` | on | off | `SP` |
| `dGR == 1` | on | on | `stale & SP` |
| `dGR >= 2` | off | on | `stale` |

Two one-bit conditions over one monotone quantity. The fourth combination
(neither) would read `FFFF` and is **not observed** — registered here as the
law's own falsifier: a `ghost` read at `SS:FFFF` refutes this decomposition.

## §3 WHAT WAS WRONG WITH THE `dQS` KEY — MEASURED, NOT ASSERTED

`python3 sw/ghost_launch_law.py dq`, 800 scoreable blocks (block 0, the COLD
one, excluded by the standing rule).

**(a) THE ANCHOR.** The key counted from the last `QS == 1` (opcode pop). Count
instead from the last queue op **of any kind** and the seven rows become one
contiguous range — and the key's *"`dQS == 4` NOT OBSERVED, the key is
SILENT"* is simply the clock at which the last op switches from the next
instruction's opcode `F` to the `8F`'s own ModR/M `S`:

| `dQS` (registered) | 1 | 2 | 3 | — | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| `dQ` (re-anchored) | 1 | 2 | 3 | **4** | 5 | 6 | 7 | — |
| last op's kind | F | F | F | S | S | S | S | |

**(b) THE ALIAS.** `dQ mod 4` is **PURE 672/672 on the non-multiply blocks**
(`0 → SP`, `1 → AND`, `2,3 → BARE`) and **80/128 on the multiply ones**. The
period is not assumed: residues 1, 2 and 3 each **recur at +4 with the same
outcome**, three independent confirmations. But it is an alias — `dQ mod 4`
and `dGR` agree only while `dGR < 4`, and every cell where they part is a cell
the key gets wrong.

**(c) `dQ` IS EXACT IN THE ucore.** Computed on the core column and on the
board column independently, `dQ` is **IDENTICAL on 800 / 800 shared blocks, 0
differing**. The ucore's queue and bus timing here is already right; only the
decoration is wrong. That is what makes the core's `upc_loc` admissible as the
instrument for a chip-side law.

## §4 THE SCORE, BY POPULATION

`python3 sw/ghost_launch_law.py score` — the law applied **unchanged**.

| population | legs | cells | score |
|---|---|---:|---|
| **DERIVATION** — the set the map was read off; **NOT evidence** | `alu88 alu44 alu08 memw pfxpro mempop mov8e` | 112 | **112 / 112** |
| **VALIDATION** — **DISJOINT**, and it selected nothing | `v_sub v_or v_inc v_lea` | 56 | **56 / 56** |
| **MULTIPLY** — the one class every counting key failed | `mul imul` | 32 | **32 / 32** |
| | | **200** | **200 / 200 = 100.0 %** |

Per bin, all three populations pooled:

| `dGR` | 0 | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---:|---:|---:|---:|---:|---:|---:|
| law | SP | AND | BARE | BARE | BARE | BARE | BARE |
| measured | SP ×20 | AND ×72 | BARE ×60 | BARE ×26 | BARE ×8 | BARE ×10 | BARE ×4 |

**Every bin is pure and there are no exceptions to report**, which is itself
the thing to be suspicious of — §6 is the control that says why it is not a
fit.

### §4.1 The two cells that break `dQ mod 4` and not `dGR`

`pfxpro_w2_a0` and `pfxpro_w2_a2`: `dGR = 5` (→ `BARE`, measured `BARE`) but
`dQ mod 4 = 2`. They are the smallest available demonstration that the modulus
is the alias and the wait is the quantity.

## §5 WHAT THIS RETIRES, AND WHAT IT DOES NOT

### §5.1 The seven-row table is retired as a LAW and kept as a MEASUREMENT
`ghost_pred_cell_key_2026-08-11.md` registered the key explicitly as *"an
INSTRUMENT — a testable statement about silicon — not as a law"*, with the
warning that a seven-row non-monotone table *"is a signal of misunderstanding,
not a deliverable"*. It was right on both counts and its 224/224 disjoint
validation stands: `dGR` reproduces every row it got right and the 32 blocks it
got wrong.

### §5.2 `ghost_pred_cell_results` §9.2's lead is CONFIRMED IN DIRECTION AND
### CORRECTED IN OBJECT
That section proposed wave-4's deleted `ghost_relax` — gated on
`eu_ghost_full` / `eu_ghost_idle`, *"a three-state queue-condition gate on
exactly this decoration"*. The instinct (three states, one gate) is right. The
object is not: `eu_ghost_full` / `eu_ghost_idle` are **functions of `r_ts` and
`r_cur_fetch`**, and the bus state around the ghost T1 is measured **IMPURE** —
`(bs, T)` at one clock before the T1 takes 2 values and separates **0 / 800**;
at three clocks, 4 values and **88 / 800**. The gate is the **request's own
wait**, not the fetch's T-state.

### §5.3 `ghost_uses_mul_hi` IS NOT AUTHORISED FOR DELETION BY THIS DOCUMENT
The law scores `mul`/`imul` 32/32 **as a decoration question**. That arm is not
a decoration: it substitutes a **different value** (`tmpa & opr`). Its deletion
is a second mechanism and must be measured as one. `ghost_pred_cell_results`
§3.2's *"do not delete it"* is left standing; what is withdrawn is only its
**reason** — the impurity it rested on is `dGR ∈ {4,5}`, not a multiply effect.

### §5.4 The `LEA` rail divergence (§6 of the previous results) is UNTOUCHED
`v_lea` scores **16/16** here because `_classify` is taken against the **chip's
own rail**; the rail question — the chip puts the `LEA`'s EA on the rail where
the ucore puts `TMPA` — is orthogonal, unmeasured here, and stays booked.

## §6 THE CONTROL: THIS POPULATION CANNOT SELECT AMONG INTERNAL STATES

Run **before** the law was written, and reported because it is the reason the
law was not chosen by scanning (CLAUDE.md §64.1).

| scan | candidates | pure on the 112 derivation cells | still 100 % on the 56 DISJOINT cells |
|---|---:|---:|---:|
| **single** save-state address × freeze offset | 2,712 | **0** | — |
| **pair** of addresses (≤ 8 values each, ≤ 12 joint) | ~410,000 | **1,169** | **1,097** |

**1,097 of 1,169 survive a "disjoint" validation.** A disjoint population that
admits a thousand candidates is not a filter, and any one of those pairs quoted
as a mechanism would have been a fit with a receipt. `dGR` is not on that list:
it is not a pair of flops, its two constants are the **RTL's own** and its
validation includes a class (`mul`/`imul`) that every previous key failed.

## §7 WHY NO RTL LANDED, AND WHAT A LANDING IS

**The law relocates a composition, it does not swap a predicate.** In the ucore
the ghost address is composed by the EU and captured at **POST**
(`v30u_biu.sv:1647`, `rq_addr[rq_n[0]] = eu_addr`); silicon composes it at
**LAUNCH** (`v30u_biu.sv:1991`, `cmt_addr = rq_addr[0]`). `dGR` is by
definition the distance between those two clocks, so **no expression evaluated
at post can carry it** — which is exactly what §6's 0-of-2,712 measures.

The design, sized so the next sitting does not re-derive it:

* **EU** — at the ghost post, latch the two *alternative composed physical
  addresses* the EU can already build with the adder pattern it has
  (`{acc_segv,4'd0} + gpr[R_SP]` and `{acc_segv,4'd0} + (ghost_off & gpr[R_SP])`):
  **40 flops**, computed at POST so no adder enters the launch cone. Post the
  **BARE** `ghost_off` as `eu_addr` (today it posts the AND). A **2-bit
  saturating age** armed at the ghost post: **2 flops**.
* **BIU** — a per-slot `rq_ghost` tag (**2 flops**) and, at the commit,
  a 3:1 mux on `cmt_addr` only. **No new adder in the launch path.**
* **Save state** — ~6 new addresses (`SS_COUNT` 226 → 232, `SS_VERSION` bump).
* **Total ≈ 44 flops, one 20-bit 3:1 mux at `cmt_addr`.**

Why it is booked rather than taken here:

1. **`acc_phys`, `acc_phys2` and `acc_split` all read `ghost_bus_off`**
   (`v30u_eu.sv:1543-1569`), and the odd-stack split decision is taken from it.
   Changing the posted value to BARE changes those decisions; that is a
   **second** behavioural change and it is on the path of `check_core --opcodes
   all` (169,000) and `ulockstep` (17,350).
2. **`cmt_addr` feeds the AD pads.** The band on this branch is CONTROL
   39.16–40.13 and RETENTION **38.82** at FLASH #18 against this sitting's
   **38.0 STOP** — 0.82 MHz of margin, and `standing_gates.md` §A governs:
   one green build is not closure.
3. **The reach is bounded and already registered**: `ghost_pred_cell_results`
   §8 names **at most 13 seats of 3,839, realistically 9**, with **13 seats
   registered as cascade-bound NON-closures** before any landing.

A landing therefore owes its **own** pre-registration, its own predicted
528-cell table, its own control build and its own G6 — none of which a rushed
diff would have. The derivation is the deliverable; the datapath move is the
next one.

## §8 FALSIFIERS

1. **`python3 sw/ghost_launch_law.py score` must exit 0 at 200/200.** It reads
   the retained board words and a `tb_sys ret` sweep; it re-derives, it does
   not replay a stored answer.
2. **A ghost read observed at `SS:FFFF`** refutes §2.1's two-driver
   decomposition.
3. **A ghost read at `dGR == 0` that is not `SS:SP`, or at `dGR == 1` that is
   not `stale & SP`,** refutes the law outright. The cheapest place to look is
   a `dGR >= 7` cell, which this corpus does not contain: the law predicts
   `BARE` and nothing here tests it.
4. **`dQ` core-vs-chip must stay 800/800.** If the ucore's queue timing drifts,
   `upc_loc` stops being an admissible instrument for a chip-side law and §3(c)
   must be re-measured before anything here is quoted.
5. **The map in `ghost_launch_law.law()` is frozen.** If a future population
   needs it edited, that is a new key and CLAUDE.md's re-key rule applies in
   full.

## §9 DISCIPLINE NOTES

* **No RTL, no Quartus, no board, no flash.** `git diff f0dab185eb -- hdl/ sim/`
  is EMPTY; the standing gates re-run in §10 are a **control on an unchanged
  tree**, not a promotion receipt.
* **The wave-8 HOLDOUT is SEALED** and was never opened. Unsealing it is the
  validation leg of a *landing*; spending it without one buys nothing.
* **The order is the evidence**: §6's two scans were run before §2 was written,
  and their negative result is reported in full rather than as an aside.
* **The map was frozen before the validation and multiply legs were scored**,
  and `ghost_launch_law.law()` has not been edited since.
* `sw/testdata/ghost-pred/launch-law/sweep.json` retains the per-clock
  `upc_loc` / `upc_opc` for all 208 cells with the `tb_sys` receipt and the
  `git` head, so `score` can be revised without re-running `sweep`.
* ⚠ **AN INHERITED INCONSISTENCY, REPORTED AND NOT "FIXED".** Re-running
  `ghost_pred_cell score` reproduces its headline exactly (**275 identical /
  245 differ**) but rewrites the `pred` bookkeeping inside
  `sw/testdata/ghost-pred/score.json`: the committed file carries `H-A`/`H-B`/
  `H-C` predictions for the grid legs, while the committed
  `rails/rails.json` holds **only the six `v_*` legs** (the validation
  `rails --legs …` run overwrote the grid's). So the committed `score.json`
  was written against a rails file that is no longer in the tree. **Nothing
  scored depends on it** — `_verdict` and the chip-vs-core column are computed
  from the board and core tables — and the file was **reverted, not amended**,
  because rewriting another wave's artefact as a side effect of reading it is
  how a ledger stops being a record.

## §10 THE CONTROL LADDER ON THE UNCHANGED TREE

**`git diff f0dab185eb -- hdl/ sim/` is EMPTY**, so every engine figure in
`CLAUDE.md` stands unmoved by construction and the receipt layer enforces it.
These were re-run anyway, as a control that the worktree is the tree it claims
to be. **They gate nothing here, because nothing was landed.**

| gate | measured | registered |
|---|---|---|
| `sw/r7_lint.py` | **PASS** — 20 nets / 1 carrier / 3 tainted / 51 `stop` sites / 0 violations | PASS |
| `sw/ss_lint.py --core ucore` | **PASS** — `SS_COUNT` **226** (103×2 BIU + 122×2 EU + tag), census **214** flops, **0 UNMAPPED** | 0x8D / 226 / 214 |
| `sw/test_artifact.py` | **45 / 45** | 45/45 |
| `sw/gen_ucore_qsf.py --check` | **up to date** | PASS |
| `sw/fz2_w1.py lint` | **PASS** — 0 hits, 48 stratum rows | PASS |
| `sw/fz2_immaterial.py falsify` | **PASS G1-G8**; residue `86 = 110 - 24`, `45 FUNCTIONAL + 30 TIMING + 11 UNSCOREABLE` | PASS |
| `sha256sum -c` on both `ghost-pred` capture dirs | **clean**, 135 files each | — |
| `ghost_pred_cell score` | **275 / 520 identical chip-vs-core, 245 differ** — the BASELINE the law would move, unchanged | 275/520 |
| **`ghost_launch_law score`** | **200 / 200, exit 0** | *this document* |

**No Quartus run and no G6 receipt**, because there is nothing to promote:
CLAUDE.md's rule is that a Quartus receipt gates *"any RTL landing … or any
bitstream flashed"*, and this sitting produced neither. The band a landing must
clear is quoted in §7.2.
