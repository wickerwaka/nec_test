# PRE-REGISTRATION — THE `8F` GHOST LAUNCH-LAW RELOCATION (RTL)

Branch `fuzz-v2-on-relanding`, base **`a37f05d4b8`** (`git rev-parse HEAD`
verified; isolated worktree, provisioned at `master` and **RESET** to the base
before anything was read or run).

**OFFLINE ONLY. NO BOARD, NO FLASH** (`flash_log.jsonl` untouched, no socket
command issued). Quartus IS in scope. A board sitting (FLASH #19) runs
concurrently in the main checkout; **nothing in this worktree enters it and the
main checkout is not touched, read or written.**

**EVERY NUMBER BELOW IS REGISTERED BEFORE THE FIRST RTL EDIT.**
`git diff a37f05d4b8 -- hdl/ sim/` is EMPTY at the commit that carries this
file.

Prior documents this executes: `ghost_launch_law_results_2026-08-11.md` (the
law, 200/200, and §7 *"why no RTL landed, and what a landing is"*),
`ghost_pred_cell_results_2026-08-11.md` §8 (the registered non-closure list),
`ghost_pred_cell_key_2026-08-11.md`.

---

## §1 THE LAW, VERBATIM AND UNEDITED

`dGR` = clocks from the FIRST clock the `8F` ghost read's own micro-row is
current (`upc_opc == 8'h8f && upc_loc == 4'd4` — `v30u_eu.sv:924`'s own
existing constant) to the clock the BIU LAUNCHES the cycle (its T1).

```
   dGR == 0   ->  SS:SP          the posting micro-row's own stack drive, alone
   dGR == 1   ->  stale & SP     both drivers on the rail -- the wired AND
   dGR >= 2   ->  stale          the row has released; only the stale rail
```

`sw/ghost_launch_law.py law()` is **FROZEN** and is not edited by this landing.
`python3 sw/ghost_launch_law.py score` reads **200/200** at the base and must
still read 200/200 after (it scores the CHIP off retained words; the RTL cannot
move it — it is the control that the instrument did not drift).

**SIMPLICITY (user directive 2026-08-01), verbatim.** *"SIMPLICITY: this is
80's era hardware — nothing on the die is wasted. Complex or confusing observed
behavior is likely simple systems interacting in ways not yet understood. A
large fitted table, a many-cased rule, or a per-opcode special case is a signal
of misunderstanding, not a deliverable."*

---

## §2 THE DESIGN — TWO DRIVERS, ONE AGE, ONE MUX

The ucore composes the ghost address at **POST** (`v30u_biu.sv:1647`,
`rq_addr[rq_n[0]] = eu_addr`); silicon composes it at **LAUNCH**
(`v30u_biu.sv:1991`, `cmt_addr = rq_addr[0]`). `dGR` is by definition the
distance between those two clocks, so no expression evaluated at post can carry
it. The relocation carries the two ALTERNATIVE composed addresses to the launch
and picks there.

### 2.1 EU (`v30u_eu.sv`) — three new output wires, NO new flop

```systemverilog
// the two drivers' own composed addresses, at the clock the ROW is current
wire [19:0] ghost_phys_sp   = {acc_segv, 4'd0} + {4'd0, gpr[R_SP]};
wire [19:0] ghost_phys_bare = {acc_segv, 4'd0} + {4'd0, ghost_off};
assign eu_ghost_row  = ghost_read_stale_alu && !ghost_uses_mul_hi;
assign eu_ghost_acc  = eu_ghost_row && !vector_early && !pr_active;
assign eu_ghost_sp   = ghost_phys_sp;
assign eu_ghost_bare = ghost_phys_bare;
```

and **ONE ARM IS DELETED** from `ghost_bus_off` — wave-4's V2
`(eu_ghost_idle && !q_ripe) ? gpr[R_SP]`. That arm is a FITTED approximation of
`dGR == 0` (`ghost_pred_cell_results` §5: *"it fires in the wrong cells"*), and
it is exactly what the law replaces. What remains is V1, the unconditional AND,
which stays the POSTED value so that every post-time derived quantity
(`acc_phys`, `acc_phys2`, `acc_split`, `eu_split`, `rq_ube`, `rq_odd`,
`eu_word`, `eu_bs`) is computed from the SAME expression it is computed from
today.

`ghost_uses_mul_hi` **IS NOT TOUCHED** (`ghost_launch_law_results` §5.3): where
it fires, `eu_ghost_row` is low, the request is not tagged, and the cycle keeps
today's address and today's every derived bit, byte for byte.

### 2.2 BIU (`v30u_biu.sv`) — 45 flops and a 3:1 mux, no new adder at launch

| register | bits | what it is |
|---|---:|---|
| `g_sp[19:0]` | 20 | the SP driver's composed address, captured at the row's FIRST clock |
| `g_bare[19:0]` | 20 | the stale driver's, same clock |
| `g_age[1:0]` | 2 | `dGR`, saturating at 2 — the law needs no more |
| `g_row_q` | 1 | the row's currency one clock ago; the arm is its RISING EDGE |
| `rq_ghost[0:1]` | 2 | which backing-store slot holds the ghost request |
| | **45** | |

placed in the `always_comb`, BEFORE the eval, in the module's own idiom:

```systemverilog
g_row_q = eu_ghost_row;
if (eu_ghost_row && !r_g_row_q) begin      // the row goes current: ARM
    g_age = 2'd0; g_sp = eu_ghost_sp; g_bare = eu_ghost_bare;
end else if (g_age != 2'd2) g_age = g_age + 2'd1;
```

and at the commit, inside the existing EU-request branch only:

```systemverilog
cmt_bs = rq_bs[0]; cmt_addr = rq_addr[0];      // unchanged
if (rq_ghost[0] && g_age != 2'd1)
    cmt_addr = (g_age == 2'd0) ? g_sp : g_bare;
```

**`g_age == 1` reads `rq_addr[0]`, which IS the AND** — so the mux has three
inputs and two of them are new registers. A same-clock post-and-grant (`dGR ==
0`) works because the module is one `always_comb` with blocking assignment: the
arm above runs before the eval and the eval reads what it wrote. That is the
same discipline `rq_*` already uses.

`rq_ghost[]` is tagged at the post (`rq_ghost[rq_n[0]] = eu_ghost_acc`), cleared
on every other post, shifted with the queue exactly as `rq_late` is, and set to
0 for the BIU-manufactured SPLIT partner (`rq_ghost[1] = 1'b0` in the split
arm) — see §7 residue (b).

### 2.3 Save state — the version bump, registered exactly

| | before | after |
|---|---:|---:|
| `SS_VERSION` | 0x8D | **0x8E** |
| `SS_BIU_COUNT` | 103 | **109** |
| `SS_EU_COUNT` | 122 | **122** |
| `SS_COUNT` | 226 | **232** |
| `SS_TAG` | 0x8DE2 | **0x8EE8** |
| flop census | 214 (BIU 85 + EU 129) | **219** (BIU **90** + EU 129) |

SIX addresses APPENDED past the BIU region's top (`SSA_B_LAST_AD_LO` = 9'h06C),
so nothing is renumbered and the map's one hole (9'h038) and the 9'h066-069
retirement are untouched:

```
9'h06D SSA_B_GHOST_SP_LO   16      9'h070 SSA_B_GHOST_BARE_HI  4
9'h06E SSA_B_GHOST_SP_HI    4      9'h071 SSA_B_GHOST_AGE      2
9'h06F SSA_B_GHOST_BARE_LO 16      9'h072 SSA_B_GHOST_TAG      3   (rq_ghost[1:0], g_row_q)
```

`sw/ss_lint.py`'s `EXPECT` block is updated to those six numbers **in the same
commit as the RTL**, and the flop census is the falsifier that no seventh flop
crept in.

---

## §3 REGISTERED BARS

`sw/ghost_launch_pred.py` (committed WITH this file, before the edit) builds the
predicted core column from three transcribed parts and no free parameter — the
law's class, the RTL's own `ghost_off` expression, and `SS:{SP, rail&SP, rail}`.
Its `model` subcommand is its own pre-edit falsifier and it reads **2,640 /
2,640**: every block-instance of TODAY's core column is `SS:(x & SP)` (2,014) or
`SS:SP` (626), which is what the RTL says it must be. The prediction is
`sw/testdata/ghost-pred/launch-law/pred.json`, committed here.

| # | bar | falsifier |
|---|---|---|
| **G-1** | **THE PRIMARY.** `ghost_pred_cell score` chip-vs-core `identical` goes **275 → 374** (+99, **−0**), `different` **245 → 154**, and the 99 closers are EXACTLY the committed `CLOSE` list in `pred.json`. | any other count; any cell closing or breaking off the list |
| **G-2** | `ghost_launch_pred score` — the MEASURED core column against the registered per-cell prediction — is **2,640 / 2,640**. | any miss, itemised cell for cell |
| **G-3** | On the LAW's own population (block 2 of the 13 swept legs, `dGR` from the committed `sweep.json`), the core reproduces the CHIP on **128 / 208**, per leg: `alu88` `alu44` `alu08` `mul` `imul` `v_sub` `v_or` **16/16 each**, `v_inc` **8/16**, `mov8e` **4/16**, `mempop` **2/16**, `v_lea` **2/16**, `memw` **0/16**, `pfxpro` **0/16**. | any leg off its number |
| **G-4** | **THE 80 MISSES IN G-3 ARE ALL RAIL DIVERGENCE, NOT DECORATION** — the core's own rail differs from the chip's on those five legs, which is `ghost_launch_law_results` §5.4 / `ghost_pred_cell_results` §6, a DIFFERENT mechanism and not this landing's. | a G-3 miss whose core address is the chip's rail decorated differently |
| **G-5** | `ghost_launch_law.py score` still **200/200, exit 0**. | anything else (it would mean the instrument moved) |
| **G-6** | `check_core --core ucore --opcodes 8F.0 --cases 0` **500/500** and `--opcodes all --cases 0` **169,000/169,000**. ⚠ The goldens have NO predecessor; if the relocation disturbs the no-stale case this is where it shows, and a miss here is a **HARD STOP**, not a residue. | any case |
| **G-7** | `ulockstep.py --golden all --cases 50` **17,350/17,350**. `acc_phys`/`acc_phys2`/`acc_split` read `ghost_bus_off` and this landing re-plumbs its consumers; this is where that breaks loudly. | any form off lockstep |
| **G-8** | The four HLT sweeps **97 · 93 · 45 · 44 = 279/283** (`--waits 1/2/3` on the w1/w2/w3 suites). | any cell |
| **G-9** | `ss_lint --core ucore` PASS at **0x8E / 109 / 122 / 232 / 0x8EE8**, census **219** flops, **0 UNMAPPED**; `r7_lint` PASS with **no new exception and no new tainted signal**; `test_artifact` **45/45**; `gen_ucore_qsf --check` up to date. | any |
| **G-10** | **G6, both configurations, TWO DRAWS EACH, worst-of-2 quoted.** The band after E-1 is CONTROL **44.72** / RETENTION **45.71**. Registered: worst-of-2 ≥ **38.0 MHz** on both (the STOP), worst setup > 0, setup AND hold TNS 0.000, 0 errors / 0 latches / 0 `lpm_divide`, and the retention `.rbf` DIFFERENT from the control's with the receipt self-labelling RETENTION (E-6/E-9). **A worst-of-2 below ~43 MHz on either configuration is a registered YELLOW FLAG** — reported, itemised, and not a stop. | < 38.0, or negative slack, or non-zero TNS |

### 3.1 The named NON-MOVERS (silicon-side, seat level)

Registered unmoved, from `fz2_w8_ghostsel_prereg` W8-4 and `fz2_flash18_results`
§4: `fz2c/404040` stays `bad == 0`; the §64.1 four `fz2c/405002` 527 ·
`fz2c/405013` 1331 · `fz2c/405072` 636 · `fz2e/512056` 1475; W7-4's older §64.1
four `fz2c/406063` · `fz2c/410047` · `fz2e/518053` · `fz2e/535027`; KM's three
`fz2c/404041` · `fz2e/501066` · `fz2e/513019` ABSENT from the ledger;
phantom-T1's three at `bad_rows == 1` with `first_bad` 243 / 234 / 583; the
**24** IMMATERIAL class-stable; M10's LEA-mod3 six `fz2c/406054` ·
`fz2c/408019` · `fz2e/518038` · `fz2e/522019` · `fz2e/524034` · `fz2e/530001`.

⚠ **AND THEY CANNOT BE MEASURED IN THIS WORKTREE — SEE §5.** They are registered
so that the sitting which CAN measure them scores a genuinely prior prediction.

### 3.2 The offline NULL CONTROLS, and a model correction found before the edit

`n_pop` (a documented `POP AW`) and `n_mod0` (`8F /0` with a real ModR/M memory
operand) carry **no ghost**: `ghost_read_stale_alu` is false on both, so the
relocation cannot reach them BY CONSTRUCTION and their 32 cells are predicted
**unmoved**. The first run of `ghost_launch_pred` did not know that and
predicted **24 of them would BREAK**; the model was corrected — in the tool, with
the reason written beside it — **before** the RTL was touched. It is reported
here rather than quietly fixed, because a predictor that has been edited after
seeing a result is not a prediction.

---

## §4 THE WAVE-8 HOLDOUT — PREDICTED BEFORE UNSEALING

The split is `docs/notes/fz2_w8_split.json` (`sha256(seed + "w8")[0] < '8'` →
DERIVE), frozen at `fz2_w8_split.py` and untouched here. **No holdout seat has
been solved, replayed or inspected by this sitting**; the only fields read are
`family` and `diverging_rows`, both of which `ghost_pred_cell_results` §8 already
published for all 39 E1 seats.

**The rule is mechanical and it is §8's own bands, applied to the F18 ledger:**

* `diverging_rows` ≤ 40 → **CLOSURE PLAUSIBLE** (scored MET on closure OR a
  strict decrease in `bad_rows`)
* 40 < rows < 320 → **ROW-IMPROVEMENT, NOT CLOSURE**
* rows ≥ 320 → **CASCADE-BOUND NON-CLOSURE** (closure is the falsifier)

| seat | F18 rows | first_bad | **PREDICTED** |
|---|---:|---:|---|
| `fz2c/406006` | 16 | 478 | closure plausible |
| `fz2e/521059` | 20 | 1235 | closure plausible |
| `fz2e/518038` | 194 | 429 | row-improvement, NOT closure *(also an M10 LEA-mod3 six member)* |
| `fz2e/526054` | 320 | 265 | cascade-bound NON-closure |
| `fz2e/522003` | 404 | 3164 | cascade-bound NON-closure |
| `fz2e/518022` | 742 | 281 | cascade-bound NON-closure |
| `fz2e/520000` | 838 | 502 | cascade-bound NON-closure |
| `fz2c/408019` | 1087 | 1617 | cascade-bound NON-closure *(LEA-mod3 six)* |
| `fz2e/518050` | 2561 | 748 | cascade-bound NON-closure |
| `fz2e/534060` | 2670 | 1067 | cascade-bound NON-closure |
| `fz2e/522019` | 3075 | 396 | cascade-bound NON-closure *(LEA-mod3 six)* |
| `fz2c/406054` | 3141 | 470 | cascade-bound NON-closure *(LEA-mod3 six)* |
| `fz2c/406063` | 3149 | 245 | cascade-bound NON-closure *(also a W7-4 §64.1 named non-mover)* |
| `fz2e/527037` | 3183 | 404 | cascade-bound NON-closure |
| `fz2e/524034` | 3479 | 457 | cascade-bound NON-closure *(LEA-mod3 six)* |

**H-1 — REGISTERED CLOSURES: ZERO.** Not one holdout seat is in §8's ≤ 8-row
closeable core, so this landing promises **no** holdout closure. The two
"plausible" seats are named; a closure there is an UNREGISTERED BONUS and is
reported as one.
**H-2 — the twelve seats at ≥ 320 rows DO NOT close.** Falsifier: any of them
reaching `bad_rows == 0`.
**H-3 — LOST = 0** over the replayed population: no seed at `bad_rows == 0`
before goes non-zero after.
**H-4 — at least ONE of the 15 shows a strict decrease in `bad_rows`.** A flat
15 would say the mechanism does not reach the banked population at all, and that
is worth knowing.

---

## §5 A GATE THIS WORKTREE CANNOT RUN, DECLARED BEFORE IT IS ATTEMPTED

**`fz2_replay` and `fz2_immaterial falsify` ARE NOT RUNNABLE HERE.** Their input
is the per-seed capture set under `sw/testdata/campaigns/*/captures/`, which
`.gitignore` excludes by name (*"the loose per-seed captures (242M+) … are
working data"*). A git worktree carries tracked files only, so **110 of 110**
F18 ledger captures and **113 of 113** F17 ones are absent, measured, and
`fz2_immaterial falsify` dies in `fz2_materiality.measure(...)` on the first
`open()`.

The only copy is the main checkout's working tree, **which this sitting is
forbidden to touch and in which a board sitting (FLASH #19) is concurrently
writing that very directory.** Reading it mid-capture would be unsound as well
as out of scope.

**So the fuzz validation leg is OWED, not waived.** §4's holdout table and
§3.1's non-movers are registered here precisely so a later sitting with capture
access scores a prediction it did not write. The landing is gated on G-1..G-10,
which are all runnable, and the report will say so in those words.

---

## §6 STOP CONDITIONS AND THE REVERT RULE

1. **G-6 (`check_core`) is a HARD STOP.** The goldens are silicon and they have
   no predecessor; if the relocation moves the no-stale case the design is
   wrong, not the goldens.
2. **G-7 (`ulockstep`) is a HARD STOP** for the same reason at the form level.
3. **G-10 below 38.0 MHz worst-of-2 is a HARD STOP** — the landing is reverted
   and booked with the cone named, exactly as the 8F ghost FEED was.
4. **If the law cannot be reproduced without a `dGR` counter wider than 2, a
   second predicate, or a per-opcode case, the landing is BOOKED, not taken**,
   and the residue is named. A partial landing may land only if the landed part
   is ONE predicate and the booked part is named in this file.
5. Everything else is reported AS REGISTERED — the number that was registered,
   the number that was measured, and the difference — never restated.

---

## §7 THE RESIDUE THIS LANDING DOES NOT CLOSE, NAMED NOW

* **(a) THE RAIL.** Where the ucore's `ghost_off` differs from the chip's rail
  (`memw` `pfxpro` `mempop` `mov8e` `v_lea`, and half of `v_inc`) the decoration
  is right after this landing and the ADDRESS is still wrong. That is
  `ghost_pred_cell_results` §6's *WHICH RAIL* free choice, one leg of which
  (`LEA`) is measured. **80 of the law's 208 cells, booked.**
* **(b) THE SPLIT GHOST.** The BIU-manufactured second cycle of a split ghost
  keeps its POSTED address; only the request the EU posted is relocated. No
  measurement exists — every split probe read makes its cell structurally
  invalid in `ghost_pred_cell.features` — and inventing a rule for it would be a
  fit. **Falsifier: a capture of a SPLIT `8F` mod=3 ghost whose second T1 does
  not carry the posted address + 1.**
* **(c) `UBE` AND `A0`.** They are computed at the post from the AND value and
  are NOT recomputed from the relocated address. Every `BARE` value in the
  measured population is EVEN, so nothing here tests it. **Falsifier: a measured
  ghost T1 whose `UBE`/`A0` disagree with its relocated address.**
* **(d) `ghost_uses_mul_hi`.** Untouched by construction (§2.1). It stays inert
  on this population and its deletion remains a second mechanism to be measured
  as one (`ghost_launch_law_results` §5.3).

---

## §8 RE-RUNNING THIS

```bash
git rev-parse HEAD                                   # a37f05d4b8 at registration
python3 sw/ghost_launch_law.py score                 # 200/200, exit 0
python3 sw/ghost_launch_pred.py model                # 2640/2640 explained
python3 sw/ghost_launch_pred.py pred                 # writes pred.json
python3 sw/ghost_pred_cell.py score                  # 275 / 245 at the base
# after the landing:
python3 sw/check_core.py --build --core ucore
python3 sw/x1_retention.py build --leg ret
python3 sw/ghost_pred_cell.py core                   # the re-capture (~20 min)
python3 sw/ghost_launch_pred.py score                # G-2
python3 sw/ghost_pred_cell.py score                  # G-1
python3 sw/quartus_gate.py                           # G-10 control
python3 sw/quartus_gate.py --retention               # G-10 retention
```

`sw/testdata/ghost-pred/launch-law/rails_all.json` is the 33-leg rail table this
prediction rests on. It was produced by `ghost_pred_cell rails` (whose output
path is `rails/rails.json`), then COPIED to `launch-law/` and the committed
`rails/rails.json` and `score.json` **restored with `git checkout`, byte for
byte** — `ghost_launch_law_results` §9's last note is that rewriting another
wave's artefact as a side effect of reading it is how a ledger stops being a
record.
