# THE VERDICT-INPUT RESIDUE CENSUS — SM3 sitting 27, 2026-08-05

**THIS DOCUMENT IS THE PHASE VERDICT'S INPUT.**  It is a complete accounting of
what is left against silicon, on **ONE TREE** (`f3f7b6b20d`, the tree FLASH #10
was built from), in **ONE CENSUS**, for **BOTH ENGINES**, with **the disposition
of every family CARRIED from the ledgers as a named exclusion** rather than
re-litigated.

**NOTHING WAS FIXED, LANDED OR PROPOSED WHILE TAKING IT.**  `git diff` over
`hdl/rtl/` and `sim/` is empty for the whole sitting.  It supersedes
`sm3_residue_census_2026-08-04.md` as the current measurement; that document is
retained and its H1/H2/H3 history is still the reading for how the residue got
here.

> **Standing principle.**  *"A guiding principal here needs to be simplicity.
> This is 80's era hardware, they aren't wasting silicon on anything that isn't
> necessary.  Complex or confusing behavior that we see is likely to be simple
> systems interacting in ways you do not fully understand yet."*

---

## §0 THE HEADLINE

| | |
|---|---|
| the `ucore`'s total banked-corpus residue | **222 seeds** of 2,710 scored (145 REGISTERED + 77 EVT) |
| **DEFERRED BY USER — 8080 / BRKEM class A** | **92** (81 REG + 11 EVT) |
| **DEFERRED BY USER — H3-B, the grant-order swap** | **10** (4 REG + 6 EVT) |
| **SPEC'D, awaiting a directed cell** | **2** (`mc1/721`, `mc2/584`) |
| **MODEL-SHARED** — a mechanism in both engines; lands `sim/` FIRST | **109** (54 REG + 55 EVT) |
| **INSTRUMENT-CLASS (family D)** — user disposition: scored on `tb_sys` | **0 in this corpus**; 4 sweep cells + 24 S16 cells elsewhere |
| ⚠ **THE CATCH-ALL — `ucore`-only, NO disposition of any kind** | **9 SEEDS**, enumerated in §5 |
| **FROZEN BY USER — the MODEL-ONLY residue** | **366 seeds** the model misses and the `ucore` does not |

**THE NUMBER THE VERDICT TURNS ON IS NINE.**  Nine seeds of 2,710 — **0.33 %** —
are `ucore`-only, carry no user decision, no booked mechanism, no specified cell
and no named hypothesis.  **Five of the nine have never been named in any ledger
in this repository**; four are §87.A.3's already-booked "the model closed five
seeds the `ucore` does not" (the fifth of that five is H3-B).

---

## §1 PER-POPULATION TOTALS, BOTH ENGINES

Every figure re-measured on this tree.  `⧉` = receipted artifact; the `ucore`
TB is `hdl/tb/obj_dir_ucore/Vtb_v30_core` receipt `cede73e73a318753…`.

### §1.1 The banked fuzz corpus (3,242 seeds; 2,710 scored, 532 `OPEN_BUS`)

| | `ucore` | `sim` |
|---|---|---|
| **REGISTERED** (1,702) | **1,557 / 1,702 (91.5 %)** | **1,338 / 1,702 (78.6 %)** |
| **EVT** (1,008) | **931 / 1,008 (92.4 %)** | **798 / 1,008 (79.2 %)** |
| **COMBINED** (2,710) | **2,488 / 2,710 (91.8 %)** | **2,136 / 2,710 (78.8 %)** |
| residue | **222** | **574** |
| `INVALIDATED` | **0** | **0** |
| `ENGINE ABORTS` | **0** | **0** |
| `BOUND WARNINGS` | **4** (`mc1/2123`, `mc1/3613`, `t30-raw/446`, `t30-raw/52`) | — |

Every one of these six figures reproduces the standing ratchet **to the seed**.
`BOUND WARNINGS` seeds are scored normally and are not excused.

> **THE EVT COLUMN IS NOT A HEAD-TO-HEAD, AND NO DELTA BETWEEN THE TWO EVT
> FIGURES IS COMPUTED ANYWHERE IN THIS DOCUMENT.**  Under `--evt-replay` the
> model is handed the capture's own acknowledge positions and the chip's pushed
> `CS:IP` and **REPLAYS**; the `ucore` is handed only `(anchor, delay, hold,
> pin)` and **PREDICTS**.  Each figure is a valid silicon-match ratchet for its
> own engine; neither ranks the two.  (`standing_gates.md`, "HOW THE EVT COLUMN
> MAY AND MAY NOT BE QUOTED".)  The REGISTERED column has no such asymmetry and
> is the column to use for a comparison.

### §1.2 The directed and tranche populations

| population | `ucore` | `sim` | note |
|---|---|---|---|
| the b2 victory tranche (188) | **177 / 188** | **159 / 188** | V5 is a standing REGISTERED FAILURE, not re-opened |
| the b3 priority tranche, **IN FABRIC** (178 scored, 22 excused) | **`core_f10` 178 / 178 (100.0 %)** | — | `chip_f10` 178/178.  **RESIDUE EMPTY** — `gaps` §T4 has no members left |
| the four HLT delay sweeps, **offline** (283 cells) | **279 / 283** | **283 / 283** | the model's leg is PERFECT |
| the four HLT delay sweeps, **IN FABRIC** on FLASH #10 | **279 / 283** | — | = the `tb_sys ret` column cell for cell, 0 coordinate differences |
| the S16 directed display walk (1,371 cells, arch + rows) | **1,320 / 1,371** | **1,305 / 1,371** | |
| the S16 walk, ROWS ONLY, **IN FABRIC** on FLASH #10 | **1,347 / 1,371** | — | = `vsys_ret` cell for cell |
| the BRK/TF floor cell, against SILICON per clock | **121,860 rows, 0 row-diffs, EXACT on all 30 captures at depth 4** — and **NON-ZERO at every other depth in [1,7]**, nearest **14,630** at depth 5; W-2 surviving floors **{4}**, **22 / 22 cells** | **121,890 rows, 0 row-diffs** at floor 3, non-zero at every other depth in [1,7], nearest **11,032** at 4; W-2 surviving floors **{3}**, 22 / 22 | banked SOCKET captures; the trap is internal and drives no pin, so **no board contact is needed and none was taken.**  W-0a / W-0b / W-1 / W-3 / W-4 / W-5 all **MET** on both engines |

### §1.3 The architectural and structural walls

| wall | measured |
|---|---|
| `simbin --disasm` | **PASS, 1,285 rows** byte-exact, receipt `6d61498fd2e8941f…` |
| `pla3_check` | **21 / 21** |
| `check_ucore_tables` (G0) | **PASS — 9,988 entries** byte-identical to `sim/`, both legs |
| `ss_lint` / `ss_flopcensus` | **PASS — 205 architectural flops, 0 UNMAPPED**, `SS_VERSION` 0x87 / `SS_COUNT` 219 |
| `check_core --core ucore --opcodes all --cases 0` | **169,000 / 169,000** (cycles AND arch) |
| `check_boot --core ucore --timed 220` / `400` | **MATCH / MATCH** |
| `ulockstep --golden all --cases 50` | **17,350 / 17,350** |
| `timed_wvec_gate --core ucore` | **88 / 88, +0.0 %** |
| `timed_enter_replay --core ucore` | **154 / 154 ×5 legs** ⚠ *see the ERRATUM below — this cell read "×3 legs" as committed* |
| `timed_ins_replay --core ucore --raw` | resolved **800 / 800**, write rails **1,312 / 1,312**, vs-chip rails **2,624 / 2,624** |
| **the MODEL's `v0.1` timed wall** — `timed_gate --suite v0.1 --forms all` | **169,000 / 169,000**, arch and window, **row-diffs 0** |
| **the MODEL's four HLT sweeps** — `timed_gate` per suite | **97/97 · 95/95 · 46/46 · 45/45 = 283 / 283**, row-diffs 0 on all four |
| `check_ab_sim --core ucore` | **MATCH over 187 rows** |
| `test_artifact` | **45 / 45** |
| G6 (Quartus), CONTROL build at HEAD | **PASS** — 47.85 MHz, +8.602 ns, TNS 0.000, ALMs 11,147 (27 %), 0 latches, 0 `lpm_divide` |
| the 7,341,126-case functional set (`ucsim_check`) | **NOT re-run this sitting.**  Measured at sitting 26 (§87.A.3) on a tree whose 88-file `hdl/` manifest hash and whose `sim/` receipt are **identical to this one's**; it is cited, not restated as a fresh measurement |

> ⚠ **ERRATUM (verdict finalization, 2026-08-05) — `timed_enter_replay`'s LEG
> COUNT.**  The row above read **"154 / 154 ×3 legs"** as committed at
> `74fa20f892`.  It is **×5**.  `standing_gates.md` §B has registered **154 / 154
> ×5** throughout; `sw/timed_enter_replay.py` prints **five** counters —
> `pushes`, `walk`, `full`, `active`, `halt_display` — each **154 / 154**, on the
> TB receipt `cede73e73a318753…`, which is this census's own binary.  **`sw/timed_enter_replay.py`'s own
> source is the check**: `n["pushes"]`, `n["walk"]`, `n["full"]`, `n["active"]`
> and `n["halt_display"]` are five distinct accumulators, four printed in the
> loop at line 180 and `halt_display` printed beside them.  **NO NUMBER MOVES —
> 154 / 154 is right on every leg; the LEG COUNT was wrong.**  The same
> mis-statement is corrected erratum-style at `ucore_provenance.md` §87.A.3 and
> §88.B.1, where the original text is preserved because that ledger is
> append-only.  Found by the phase verdict's cross-check
> (`sm3_verdict_2026-08-05.md`, appendix item 1) and reported rather than
> silently corrected.

---

## §2 THE FAMILY CENSUS — `s15_census`, `--core` MATCHED TO THE REPORT

*Matching matters: `s15_census` used to replay the model unconditionally, so
pointed at a `--core ucore` report with the default engine it ran clean and
reported the MODEL's families for the `ucore`'s seeds (gap R4, closed
2026-08-04).  Both dumps below name their own engine.*

### §2.1 The `ucore`

| family | REGISTERED | EVT | total |
|---|---|---|---|
| `PF_LOST` | 85 | 17 | **102** |
| `SCHEDULE` | 13 | 31 | **44** |
| `DATA_SEQ` | 33 | 8 | **41** |
| `PF_GAINED` | 2 | 13 | **15** |
| `PF_ADDR` | 8 | 3 | **11** |
| `PIN` | 4 | 5 | **9** |
| `TAIL_EXTRA` | 0 | 0 | **0** |
| **catch-all (unclassified by the taxonomy)** | — | — | **EMPTY** |
| **total** | **145** | **77** | **222** |

### §2.2 The `sim`

| family | REGISTERED | EVT | total |
|---|---|---|---|
| `PF_LOST` | 216 | 66 | **282** |
| `SCHEDULE` | 87 | 109 | **196** |
| `DATA_SEQ` | 27 | 3 | **30** |
| `PF_ADDR` | 17 | 10 | **27** |
| `PIN` | 15 | 11 | **26** |
| `PF_GAINED` | 2 | 11 | **13** |
| `TAIL_EXTRA` | 0 | 0 | **0** |
| **total** | **364** | **210** | **574** |

**`TAIL_EXTRA` IS ZERO IN BOTH ENGINES AND THE TAXONOMY'S OWN CATCH-ALL IS
EMPTY IN BOTH** — the illegal-form stall (§87.A) closed the family and no seed
in either engine fails to classify.

### §2.3 The cross-engine partition of the seeds

| | count |
|---|---|
| diverging in **both** engines (model-shared) | **208** |
| **`ucore`-only** | **14** |
| **model-only — FROZEN BY USER DECISION** | **366** |

Independent reproduction of §87.A.3's own two numbers ("the `ucore`'s OWN
registered residue is 14"; "the `ucore` is still exact on 366 seeds the model is
not"), derived here from two fresh dumps rather than carried.

**All fourteen `ucore`-only seeds are individually located**: nine are the
catch-all (§5), two are L3 (`mc1/721`, `mc2/584`) and three are L2 (`mc2/2808`,
and — added at the verdict's finalization, §4.2's erratum — **`mc2/549`** and
**`mc2/1791`**).  As committed, this section gave the count and located twelve;
the last two are named at §4.2.

---

## §3 THE DISPOSITIONS, CARRIED — NOT RE-LITIGATED

Every row is a USER DECISION or a booked ledger disposition.  This census does
not argue with any of them; it counts them.

| # | partition | disposition | where it is written |
|---|---|---|---|
| **L1** | **8080 / BRKEM class A** | **DEFERRED BY USER DECISION 2026-08-05**: *"8080 mode should not be tested or considered right now. It is something we will explore in a later campaign."*  Carried as a named exclusion, not worked, **not counted against any silicon-match verdict** | `gaps` §0 F1, FIFTH UPDATE; §63.5 |
| **L2** | **H3-B** — `PF_LOST` class B, the grant-order swap | **DEFERRED BY USER DECISION.**  Booked, not worked; its two directed cells stay specified and unrun.  ***It is not refuted*** | `gaps` FIFTH UPDATE; §63.6 |
| **L3** | **spec'd, awaiting a directed cell** | `mc1/721` — a **collision between two independently measured laws**, whose fix needs a second micro-ROM read in one clock, which an 80s die does not do; `mc2/584` — booked and undiagnosed.  The `8F` mod-3 ghost cell (B2a) is specified and unrun | §87.B; §86.H; §84.6 |
| **L4** | **model-shared** | a mechanism present in BOTH engines lands **`sim/` first**, exactly as it has all campaign.  This is a ROUTING rule, not an exemption | `gaps` FIFTH UPDATE |
| **L5** | **the MODEL-ONLY residue** | **FROZEN BY USER DECISION.**  No model-only work.  A defect in `sim/` and not in the `ucore` is not a work item for the remainder of this campaign | `gaps` FIFTH UPDATE; §79.I, §80.A |
| **L6** | **family D** — the analyser's second `BS` sample | **USER DISPOSITION: SCORED VIA `tb_sys`.**  Not patched, and **not scored on `tb_v30_core`**, on which they are unfixable by construction | `gaps` FOURTH UPDATE; §77.A.2 |
| **L7** | **H7** — the `0x0008` NMI-vector floor | **BLOCKED**, and since §81.B its floor of `A + 12` **has no live evidence**: 0 of 30 banked seeds reproduce it, 162 of 163 non-floor seeds do | §63.3, **§81.B** |

---

## §4 THE `ucore`'s RESIDUE, PARTITIONED BY DISPOSITION

The partition is computed, not asserted.  **Class A's criterion is §63.5's
verbatim and is mechanical and board-free**: the chip's cell at the first
contested slot is `CODE 00484` **and** the chip's window contains `CODE:00008`
(the 8080 `RST 1` vector fetch).  H3-B is `PF_LOST` minus class A.

| layer | REGISTERED | EVT | total | share of 2,710 |
|---|---|---|---|---|
| **L1** 8080 class A — deferred by user | 81 | 11 | **92** | 3.39 % |
| **L2** H3-B — deferred by user | 4 | 6 | **10** | 0.37 % |
| **L3** spec'd, awaiting a cell | 2 | 0 | **2** | 0.07 % |
| **L4** model-shared — `sim/` first | 54 | 55 | **109** | 4.02 % |
| **L6** instrument-class (family D) | 0 | 0 | **0** | — |
| ⚠ **CATCH-ALL** — `ucore`-only, no disposition | **4** | **5** | **9** | **0.33 %** |
| **total residue** | **145** | **77** | **222** | 8.19 % |

### §4.1 L1 — the 8080 class, characterised FRESH and still exception-free

Re-measured on this tree, not carried from §63.5:

| | measured |
|---|---|
| size | **92** (81 REG + 11 EVT) — **identical to §63.5's 92**, four sittings and five landings later |
| by bank | `t30-brkem` **50 / 50 — the whole bank**, `mc2` 19, `t30-raw` 15, `mc1` 8 |
| the engine's cell at the contested slot | **`MEMR` 92 / 92** (the native `IRET`'s first pop — the `ucore` has no 8080 mode) |
| `delta` (engine T1 − chip T1) | **+2 on 92 / 92** |
| recovery | **`NONE` 92 / 92** |

**Exception-free on all four axes.**  This is one place in the harness —
`gen_soup.py` points all 256 IVT vectors at a bare handler at `0x0480`, and the
chip's `CF` there is the 8080 `RST 1` — not a law about prefetching.  Its
`PF_LOST` label is an artefact of "the first bus-visible disagreement": the two
machines are executing **different instructions**.

### §4.2 L2 — H3-B, by population

`PF_LOST` 102 − class A 92 = **10** (4 REGISTERED, 6 EVT).  It was 37 `ucore`
seeds at §63.6 and the family has shrunk by 27 across the campaign's landings
without ever being worked.  **Deferred, not refuted.**

> ⚠ **ERRATUM / COMPLETION (verdict finalization, 2026-08-05) — THE TWO
> UNLOCATED `ucore`-ONLY SEEDS ARE NAMED, AND THEY ARE BOTH HERE.**
>
> As committed at `74fa20f892` this census gave **`ucore`-only = 14** (§2.3) and
> a catch-all of **9** (§4/§5), and named three of the remaining five
> individually — `mc1/721` and `mc2/584` at L3, `mc2/2808` at L2.  **It did not
> say where the other two were**, and `sm3_verdict_2026-08-05.md`'s appendix
> item 3 flagged that rather than deriving it.  **DERIVED NOW, from this
> census's own two dumps and this section's own criterion — nothing new was
> measured and no layer size moves:**
>
> | seed | pop | family | wait | chip cell | engine cell | `recov` | layer |
> |---|---|---|---|---|---|---|---|
> | **`mc2/549`** | EVT | `PF_LOST` | `wrand3`, pin 0 | `CODE 00506` | `INTA 0645f` | `NONE` | **L2 — H3-B** |
> | **`mc2/1791`** | EVT | `PF_LOST` | `wrand1`, pin 0 | `CODE 0050a` | `INTA 0fb80` | `MISS` | **L2 — H3-B** |
>
> **How they are placed, mechanically.**  Both are `PF_LOST`, so by §4's
> partition they are L1 or L2 and nothing else.  §63.5's class-A criterion —
> *the chip's cell at the first contested slot is `CODE 00484` **and** the chip's
> window contains `CODE:00008`* — is FALSE for both (their contested cells are
> `CODE 00506` and `CODE 0050a`, and neither window carries the 8080 `RST 1`
> vector fetch).  Therefore **L2**.  Re-running that criterion over the whole
> `PF_LOST` family reproduces this section's own two counts to the seed —
> **class A 92 (81 REG + 11 EVT), L2 10 (4 REG + 6 EVT)** — which is the control
> that says the placement is the census's arithmetic and not a new judgement.
>
> **The full L2 membership, so it is never unenumerated again**: `mc1/444`,
> `mc1/2603`, `mc2/199`, **`mc2/549`**, **`mc2/1791`**, `mc2/2808`,
> `t30-raw/61`, `t30-raw/235`, `t30-raw/805`, `t30-raw/987`.  Of those, **five
> are `ucore`-only** (`mc2/549`, `mc2/1791`, `mc2/2808` at L2 plus `mc1/721` and
> `mc2/584` at L3) and **nine are the catch-all** — 5 + 9 = **14**, which closes
> the reconciliation §2.3 left open.
>
> ⚠ **THIS DOES NOT MOVE THE CATCH-ALL.**  Both seeds carry a USER DECISION
> (H3-B, DEFERRED, `gaps` FIFTH UPDATE); neither is undispositioned, and the
> number the verdict turns on is still **NINE**.

### §4.3 L4 — the model-shared column, by family

| family | REG shared | EVT shared | total | named by |
|---|---|---|---|---|
| `SCHEDULE` | 13 | 31 | **44** | `ucsim_t_provenance` §26.10 D item 3 (*"`SCHEDULE`'s −3"*), `gaps` §I.5 — an OPEN SURFACE item, model-shared |
| `DATA_SEQ` | 30 | 7 | **37** | **H4** (§62.9 rank 2).  Partition B was split at §83: **B1** is the BRK/TF trap and is **LANDED** (§84/§86), **B2a** is the `8F` mod-3 ghost (12 seeds, cell specified and unrun, §84.6), **B2b** is inherited functional residue routed OUT of the timing census |
| `PF_GAINED` | 2 | 11 | **13** | **no hypothesis names it** |
| `PF_ADDR` | 6 | 3 | **9** | **no hypothesis names it** — §62.9 says so in as many words |
| `PIN` | 3 | 3 | **6** | **no hypothesis names it** |
| **total** | **54** | **55** | **109** | |

**The honest reading of this column**: 81 of its 109 seeds (`SCHEDULE` +
`DATA_SEQ`) sit under a named, cited mechanism; **28 do not** — they are
`PF_GAINED`, `PF_ADDR` and `PIN`, small families nobody has looked at, and they
are model-shared, so under the governance rule they are `sim/`'s first.  They
are counted here so that "the model-shared column is dispositioned" is not read
as "the model-shared column is explained."

---

## §5 ⚠ **THE CATCH-ALL — NINE SEEDS, ENUMERATED**

**Definition, stated before the count**: a banked-corpus seed on which the
`ucore` diverges from silicon, the **model does not**, and which carries **no
user decision, no booked mechanism, no specified directed cell and no named
hypothesis**.  This is the number the phase verdict turns on.

| seed | pop | family | first-divergence signature | row | `ndiff` | wait | chip cell | engine cell |
|---|---|---|---|---|---|---|---|---|
| `mc1/1023` | REG | `DATA_SEQ` | `nxta` | 874 | 2,605 / 4,000 | `wrand15` | `MEMR 053b7` | `MEMR 053b8` |
| `mc2/640` | REG | `DATA_SEQ` | `data` | 451 | 354 / 4,000 | `fix0` | `MEMW 0eaa7` | `MEMW 0eaa8` |
| `t30-raw/15` | REG | `DATA_SEQ` | `data` | 539 | 123 / 4,000 | `fix0` | `MEMR aa576` | `MEMR aa574` |
| `mc2/887` | REG | `PF_ADDR` | `nxta` | 436 | 8 / 4,000 | `wrand1` | `CODE 0ddfe` | `CODE 041de` |
| `mc1/2468` | EVT | `PF_GAINED` | `qs -!=F` | 319 | 760 / 1,140 | `wrand7` | `MEMR 00008` | `CODE 00510` |
| `mc1/3034` | EVT | `PF_GAINED` | `bs PASV!=CODE` | 484 | 88 / 4,000 | `fix0` | `INTA 0f4fb` | `CODE 0050a` |
| `mc2/327` | EVT | `DATA_SEQ` | `t Ti!=T1` | 270 | 1,370 / 1,709 | `fix2` | `INTA 00506` | `PASV 60506` |
| `mc1/1629` | EVT | `PIN` | `data` | 3,419 | **2** / 3,628 | `wrand7` | — | — |
| `mc1/3072` | EVT | `PIN` | `data` | 903 | **2** / 1,100 | `fix0` | — | — |

**PROVENANCE OF EACH, STATED.**  `mc1/1023`, `mc2/640`, `mc2/887` and
`t30-raw/15` are four of the five seeds §87.A.3 booked as *"the MODEL closed five
seeds the `ucore` does not"* — the fifth, `mc2/2808`, is H3-B and is at L2.
**`mc1/1629`, `mc1/2468`, `mc1/3034`, `mc1/3072` and `mc2/327` appear in NO
ledger in this repository** — a grep of `docs/notes/` for each returns zero
hits.  This census is their first enumeration, and that is exactly what a
catch-all is for.

### §5.1 ONE OBSERVATION ABOUT THREE OF THEM — recorded as an observation, NOT a mechanism claim

On `mc1/1023`, `mc2/640` and `t30-raw/15` the chip and the engine open **the
same cycle, of the same type, at the same clock**, and the ADDRESS differs by
**±1 or ±2 in the low bits** (`053b7`/`053b8`, `0eaa7`/`0eaa8`,
`aa576`/`aa574`).  That is the shape `gaps` §T8 already describes for a
different, now-closed population — *"an exact byte swap on an odd-address word
write (M5b's `A0` swapper applied where the chip does not)"*.

**IT IS NOT CLAIMED HERE.**  §T8's four seeds were model-shared and these three
are `ucore`-only, so the two cannot be the same defect without a further
measurement that nobody has taken.  Recorded so the next sitting starts from a
shape rather than from nine unrelated seeds, **with its falsifier**: any of the
three whose divergence survives forcing the engine's `A0` to the chip's on that
one cycle is not this shape.

### §5.2 AND ONE ABOUT THE TWO `PIN` SEEDS

`mc1/1629` and `mc1/3072` each differ from silicon in **exactly two rows** out
of 3,628 and 1,100, both on the `data` pins.  They are the two smallest
divergences in the entire corpus.  No mechanism is proposed.

---

## §6 THE NON-BANK RESIDUE

### §6.1 The four HLT delay sweeps — 279 / 283, offline AND in fabric

**The residue is FOUR CELLS, one class, catch-all EMPTY**: `s10-w1/HLT.INT/8`
and `/9` (first divergence row 11), `s13-w2/HLT.INT/12` (row 13),
`s13-w3/HLT.INT/15` (row 15), all column `pins`.  All four are **family D**, the
analyser's second `BS` sample, whose **USER DISPOSITION is that they are scored
on the `tb_sys` / fabric column and are not patched** — and this sitting scored
them there: **identical in fabric, cell for cell and coordinate for coordinate**.
The MODEL's leg on this population is **283 / 283, perfect**.

### §6.2 The S16 directed display walk

* **Rows only, in fabric on FLASH #10: 1,347 / 1,371.**  Its 24 failing cells are
  **the same four family-D coordinates crossed with the six frozen programs and
  nothing else** — the catch-all is EMPTY in fabric.
* **`ucore`, arch + rows: 1,320 / 1,371**, per wait **372 · 328 · 318 · 302**
  (**w0 is 372/372, perfect**).  Residue **two classes and no third**:
  **24 `D_tstate`** (family D, the `tb_sys` item) and **27 `ARCH`**.
* **`sim`, arch + rows: 1,305 / 1,371**, residue **39 `qop` + 30 `ARCH`** —
  reproduced to the cell this sitting — both inside the model-only debt the user
  **FROZE**.

### §6.3 The 27-cell `ARCH` class — the one non-bank item with no disposition

The `ucore`'s S16 residue is 24 family-D + **27 `ARCH`**, and the `ARCH` cells
are architectural read-back differences (`sp`/`bp`, `ax`/`dx`, `sp`/`si`/`flags`
on `HLT.RES` at `w1`/`w2`), not timing.  **They are booked and undispositioned.**
They are not in the catch-all of §5 because that count is defined over the fuzz
corpus; they are called out here so that the phase verdict does not read
"catch-all = 9" as "9 unexplained things in the whole project".  The honest
statement is: **9 unexplained SEEDS in the banked corpus, plus 27 unexplained
S16 `ARCH` CELLS, and nothing else without a disposition.**

---

## §7 WHAT IS EXPLICITLY EXCLUDED, AND BY WHOM

Carried, named, and **not** counted against the silicon-match verdict:

1. **8080 / BRKEM** — 92 corpus seeds, the whole `t30-brkem` bank, 192 ROM rows,
   116 of 1,028 ROM rows never executed.  **USER DECISION, 2026-08-05.**
2. **H3-B** — 10 corpus seeds.  **USER DECISION.**  Not refuted.
3. **The model-only residue** — 366 corpus seeds and the model's 39-cell `qop`
   S16 class.  **USER DECISION: FROZEN.**
4. **Family D** — 4 sweep cells + 24 S16 cells.  **USER DISPOSITION**: scored on
   `tb_sys`, where they now score identically in fabric.
5. **V5**, the b2 tranche's standing REGISTERED FAILURE — not to be re-opened.
6. **H7** — BLOCKED, and §81.B removed the live evidence for its floor.
7. **`mc1/721` / `mc2/584` / the `8F` ghost** — specified, awaiting directed
   cells; `mc1/721`'s is a collision between two measured laws and the ledger
   says explicitly that one seed cannot decide it.
8. The three UNRESOLVED law cards **C6 / C7 / C11** and the four remaining items
   of the ucsim-t open surface — model-shared, unchanged.

---

## §8 HOW TO READ THIS DOCUMENT AGAINST THE VERDICT

* **Quote 91.5 % / 92.4 % / 91.8 % with the population named**, never a single
  "accuracy" number.
* **Never compute a delta between the two EVT columns.**
* **Quote a fabric figure only against its own bitstream.**  Everything in
  §1.2's fabric rows is **FLASH #10**, `nec_test_ucore.sof 1a01a6975e4a…`.
* **The catch-all is 9.**  Everything else in the 222 is either a user decision,
  a booked mechanism, a specified cell, or `sim/`'s first under the
  shared-mechanism rule.
* **9 is not 0**, and this document does not claim closure.  It claims that the
  undispositioned surface is nine banked seeds and twenty-seven S16 `ARCH`
  cells, that both are enumerated, and that neither was discovered by looking
  for a number that would look good.
