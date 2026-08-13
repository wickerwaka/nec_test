# L1 — THE REGISTERED DECODE.  RESULTS, SCORED AS REGISTERED.

Pre-registration `107c0e3877` (`adcone_l1_prereg_2026-08-13.md`), committed
**before the edit**.  Anatomy `05bd462643` / `83c00e753f`
(`adcone_anatomy_2026-08-13.md`), committed **before the design**.  Edit
`9bf70f2eec`.  Branch `master`, isolated worktree, HEAD verified at
`faabb15128` on entry.  **OFFLINE ONLY.  NO BOARD, NO FLASH.  No Codex
consulted, no nested task spawned.**

---

## §0 HEADLINE

| | |
|---|---|
| **The edit** | **12 lines of RTL.** The decode of the micro-address the EU's register bank is *about to commit* is taken on the edge that commits it, from that bank's own selection expression. No SDC edit. |
| **P-1, THE FLOOR AND THE REVERT CONDITION** | **MET ON BOTH CONFIGURATIONS.** `worst-of-5@seeds{1,2,3,4,5}`: **CONTROL 38.97 → 41.71 (+2.74)**, **RETENTION 39.74 → 43.50 (+3.76)**. |
| **Pin identity** | **BYTE-IDENTICAL on every leg with a control**: 306 fz2 seeds / **1,243,278 replayed rows**, 4 × 400,000 LFSR clocks, 2,200 `ie-pinfall` directed cells, and the whole golden ladder. |
| **What it cost in area** | **−230 ALMs (CTL), −70 (RET)**. Quartus stopped refusing to infer a memory and built `ucdecode` as an **M10K ROM**. |
| **What the cone looks like now** | the microcode head is **1.545 ns/path and 0.8 cells/path** on CONTROL seed 1 (it was **8.976 ns and 8.3 cells**), and neither table appears in the ≥25 % net census at all. |
| **⚠ THE LEVER IS SPENT** | on CONTROL seed 1 the observation class binds at **+7.276** and `c_int_q → v30u_eu\|rd_pending[0]` sits at **+7.949** — **0.673 ns behind it**. Closing the *entire* remaining class is worth **+0.79 MHz (CTL) / +1.71 (RET)** on a worst-of-5 basis, and then `c_int_q` binds on every draw. |
| **50 MHz** | **not reachable by this lever, and now that is measured**: the worst-of-5 ceiling behind the whole observation class is **42.50 (CTL) / 45.21 (RET)**. |
| **A gate that did not exist** | **`sw/ucrom_mif_check.py`** — the microcode's SYNTHESIS-side F44 check. The M10K made it urgent and the whole offline ladder was blind to it. |
| **Next lever** | **`c_int_q`**, and it is R7′-shaped. §4. |

---

## §1 THE PIN-IDENTITY LADDER — EVERY LEG AS REGISTERED

`hdl/rtl/ucore/v30u_eu.sv` is the only RTL file this wave edits, and
`sw/ss_flop_whitelist_ucore.txt` the only other functional file.  The `.sdc` is
**untouched**.

| leg | registered | measured | |
|---|---|---|---|
| `r7_lint` | PASS, 0 violations, 20 nets / 1 carrier / 3 tainted / 51 `stop` | **PASS**, identical counts | ✓ |
| `ss_lint --core ucore` | `SS_COUNT` **232** unchanged, flops **220 → 221**, whitelist **2 → 3**, 0 UNMAPPED | **232**; BIU 91 mapped, EU **130** flops → 127 mapped + **3** whitelisted; **221** flops, **0 UNMAPPED** | ✓ **P-5 MET** |
| `check_core --opcodes all --cases 0` | 169,000 | **169,000/169,000** | ✓ |
| `check_core --opcodes 8F.0 --cases 0` | 500 | **500/500** (cycles 500, arch 500) | ✓ |
| HLT sweeps ⚠ `--waits 0/1/2/3` | 97 · 93 · 45 · 44 = 279/283 | **97 · 93 · 45 · 44 = 279/283** | ✓ |
| `ulockstep --golden all --cases 50` | 17,350 | **17,350/17,350 ALL LOCKSTEP** | ✓ |
| `ghost_launch_law score` | 200/200 | **200/200 = 100.0 %** | ✓ |
| `check_boot --core ucore` | 220 and 400 | **MATCH over 220** and **over 400** rows | ✓ |
| `check_ab_sim --core ucore` | MATCH 187 rows | **MATCH over 187 rows** | ✓ |
| `v0.1-w1` / `-w3` | 1,200 each | **1,200/1,200** each | ✓ |
| `v0.1-w1 --opcodes EB` | 200 | **200/200** | ✓ |
| the four `evt` cells (w0/w1/w2/w3) | 200 / 1,200 / 200 / 1,200 | **200 / 1,200 / 200 / 1,200** | ✓ |
| `v0.1-w1evt-biased` | 1,200 | **1,200/1,200** | ✓ |
| **S16 display walk** `sm3_s16_score --core ucore` | 1,320/1,371 | **1,320/1,371**, signature census `busstat_other` 24 · `ARCH` 27 | ✓ |
| `fz2_immaterial falsify` | G1-G8 PASS | **G1-G8 PASS**, 22 members / 84 non-members of 106 | ✓ |
| `test_artifact` | 45/45 | **45/45**, non-vacuous | ✓ |

### 1.1 THE TWO LEGS THAT WOULD HAVE CAUGHT A MOVED PIN — **BOTH BYTE-IDENTICAL**

`check_core` and the golden suites score against *goldens*, so they answer *"is
the core still right"*.  Neither answers *"did anything at all change"*.  These
two do, and they are the registered **P-3**:

**(a) `chain_lfsr_gate` — 4 seeds × 400,000 fabric clocks of ARBITRARY BYTES**,
with LFSR memory, LFSR `READY` and LFSR `INT`, i.e. a stimulus distribution with
nothing in common with the golden suite.  It emits a per-seed running signature.

| seed | before | after |
|---|---|---|
| 1 | `2138eabbcea8796c` | **`2138eabbcea8796c`** |
| 2 | `fad6633fc67db084` | **`fad6633fc67db084`** |
| 3 | `f90444c46a589273` | **`f90444c46a589273`** |
| 4 | `5404f98f2d8bc343` | **`5404f98f2d8bc343`** |

`CHAIN_DEPTH_MAX 6` / `entry_st 25` / `coincide 0` / `ce_clocks` and all eight
gap counts identical too; **the only diff in the whole transcript is the
Verilator binary receipt, which must change.**

**(b) `fz2_replay --all-failures --pass-sample 200 --leg ret` — the FULL
`tb_sys` replay of the fuzz-v2 corpus**, 306 seeds, scored against the banked
**socket** rows with the corpus's own column policy and window.

```
before  tb_sys receipt c7b10164b3fb1892…
after   tb_sys receipt f5a82f26f80eb297…
seeds: 306 vs 306
replayed rows compared: 1,243,278
tables block identical: True
IDENTICAL: 306 seeds, 1,243,278 replayed rows, every `sys` field and every
           banked reference field unmoved
```

`sw/adcone_replay_diff.py` compares `n`, `nrows`, `bad`, `flick`, `first`,
`fired`, `vecused` per seed plus the banked `fabric_bad` / `fabric_first` /
`win` / `family`, and the whole `tables` block.  **A pin that moved on any clock
of any of those 306 programs moves at least one of those fields.**

⚠ **BOTH `fz2_replay` LEGS RAN WITH `--no-fabric-era-guard`, AND THAT IS
STATED RATHER THAN WORKED AROUND.**  The guard already REFUSED on the
**pre-edit** tree — `hdl/rtl/ucore/v30u_eu.sv`, `hdl/nec_test.sdc` and
`hdl/nec_test.qsf` have all moved since FLASH #20's bitstream
(`26d6e79166183a21…`) — so this tree was a cross-era read *before this wave
touched it*.  **What these two legs measure is BEFORE vs AFTER on ONE tree.
They say nothing about fabric, and no fabric claim is made from them.**

**(c) `ie_pinfall_cell core` — 2,200 DIRECTED CELLS ON `tb_sys ret`, AND ITS
CONTROL HAD TO BE BUILT.**  Re-run on the L1 tree it differs from the
**committed** `sw/testdata/ie-pinfall/core/table.json` in 32 fields over 8
cells (`eihlt_w2:r10:h{1,2,3,4,300}` move `n_inta` 1→2, `ack` 299→291,
`ack_off` 27→19, `ack_off_hlt` 23→15; `eihlt_w1:r6:h1` moves only its raw
`sha256`).

**THAT IS NOT AN L1 FINDING, AND THE CONTROL PROVES IT.**  The committed table
was captured **2026-08-11T21:50:45Z** on `tb_sys` receipts `0b7e547c…` /
`5ea26900…` against this tree's `06771ec3…` / `fe9c9656…` — a different era, and
its own manifest records 163.7 s against this run's 668.8 s, so the two runs did
not cover the same work before merging.  So the leg was **re-run on the PRE-L1
tree** (`107c0e3877`'s `v30u_eu.sv`, `tb_sys ret` rebuilt at receipt
`1a87952f60986b46…`) and compared to the post-L1 run:

```
cells: 2200 vs 2200
IDENTICAL: 2200 cells, every measured field unmoved
```

**Pre-L1 vs post-L1: identical, `sha256` included.**  The committed artifact is
restored byte-identical; the two runs are kept at
`sw/testdata/adcone/l1/iepinfall_core_{prel1,l1}.json`.

### 1.3 AN INCIDENTAL FINDING, NAMED AND NOT FIXED HERE

**`sw/testdata/ie-pinfall/core/table.json` as committed on `master` is STALE:**
8 of its 2,200 cells disagree with what the same tool produces at
`faabb15128` **before this wave's edit**.  It belongs to another wave's record
and is left byte-identical; it is booked in §4.3.

### 1.4 ONE REGISTERED FIGURE READ DIFFERENTLY, AND IT IS THE ENVIRONMENT

`test_quartus_gate` is registered at **200/200**; on the first run it printed
**199/199 with one `[skip]`** — *"no live `fit.rpt` on disk to check the parser
against"* — because a clean build had just deleted `hdl/output_files_ucore/`.
It is a **conditional check, not a lost one**: re-run with a build on disk it
reads **200/200**, measured.  Reported here rather than quietly rounded up.

---

## §2 THE MEASUREMENT — G6 `--seeds 5`, BOTH CONFIGURATIONS

### 2.0 HOW THE BEFORE FIGURE IS OBTAINED, AND WHY THAT IS LEGITIMATE

The **before** leg is `timing50_distribution_2026-08-13.md` §4's seeds 1-5, i.e.
`worst-of-5@seeds{1,2,3,4,5}` = **CONTROL 38.97** (seed 5) and **RETENTION
39.74** (seed 5), re-derived from those receipts by `sw/adcone_g6_table.py`
(which reproduces that document's two tables cell for cell — the check that it
reads the artifacts the way the document did).

**It is not re-built, and the reason is measured rather than assumed**: this
wave's anatomy took three CONTROL draws on its OWN independently produced map
and reproduced **38.97 / 39.79 / 41.28 to the digit** at seeds 5, 6 and 8
(`adcone_anatomy_2026-08-13.md` §5.1).  So on the BEFORE side, map variance is
measured at zero on 3 of 3 seeds tested.

⚠ **The AFTER side carries a new map and that cannot be avoided** — an RTL edit
re-maps by construction — so the residual exposure is one map draw on one side.
`timing50_distribution_2026-08-13.md` §7 puts historical map variance at
~2.3 MHz (CONTROL), **which is larger than P-1's 2.0 MHz floor**.  P-1 was
registered knowing that.

### 2.1 THE TWO SWEEPS

Both `verdict PASS`; input manifest **`d47c1d003d64c4c5…`** (the baseline's is
`c23e63aa4cf19684…` — they differ by `v30u_eu.sv` and the whitelist, which is
the check that the edit reached the compiler).  **E7** `n_moved` 1 /
`moved_offending` 0 (the one declared §70.7 exemption), **E8** 5/5 seeds
honoured on both readings, **E9** every draw a G6 PASS, **E10** N = 5.
**TNS 0.000 setup AND hold on every domain of all ten draws.**

**CONTROL** — record `65649b8f8b7e7451…`, `sw/testdata/g6dist/adcone-l1-control-n5/`

| seed | Fmax | worst setup | ALMs | binding cone | rung 1a (k) |
|---|---:|---:|---:|---|---:|
| **1** | **41.71** | **+7.276** | 10,154 | `opc_from_modrm → ad_in_q[14]` | 42.92 (1.0) |
| 2 | 42.48 | +7.710 | 10,105 | `ucdecode M10K → ad_in_q[15]` | ⚠ 94.79 (0.5) |
| 3 | 42.57 | +7.758 | 10,116 | `ucdecode M10K → ad_in_q[17]` | 50.27 (1.0) |
| 4 | 42.50 | +7.722 | 10,115 | **`c_int_q → row_posted`** | 42.50 (1.0) |
| 5 | 44.36 | +8.708 | 10,085 | `ucdecode M10K → ad_in_q[0]` | 47.34 (1.0) |

> **`worst-of-5@seeds{1,2,3,4,5}` = 41.71 MHz** · median 42.50 · best 44.36 ·
> spread **2.65** (was 3.34)

**RETENTION** — record `2c53275e981ebf85…`, `…/adcone-l1-retention-n5/`

| seed | Fmax | worst setup | ALMs | binding cone | rung 1a (k) |
|---|---:|---:|---:|---|---:|
| 1 | 45.21 | +8.988 | 10,194 | **`c_int_q → row_posted~DUP`** | 45.21 (1.0) |
| **2** | **43.50** | **+8.261** | 10,145 | `ucdecode M10K → ad_in_q[11]` | 47.42 (1.0) |
| 3 | 44.33 | +6.758 | 10,178 | `ucdecode M10K → ad_in_q[*]` | 46.57 (1.0) |
| 4 | 43.84 | +8.442 | 10,134 | `opc_from_modrm → ad_in_q[18]` | 45.96 (1.0) |
| 5 | 44.80 | +8.929 | 10,166 | `ucdecode M10K → ad_in_q[3]` | ⚠ 79.03 (0.5) |

> **`worst-of-5@seeds{1,2,3,4,5}` = 43.50 MHz** · median 44.33 · best 45.21 ·
> spread **1.71** (was 4.00)

⚠ **THE "binding cone" COLUMN IS READ FROM Quartus's Fmax SUMMARY, NOT FROM THE
PROBE'S `DEFAULT` ROW.**  That row is an unconstrained `get_timing_paths` and on
RETENTION seeds 1 and 3 it named a **k = 0.5** enable arc
(`cfg_clk_div[4] → t1_half2` at 75.34; `div_cnt[1] → t1_half2`) — the
distribution gate's §3.1 artifact, on 2 of these 5 draws.  The `⚠` rung-1a cells
are the §6 `~DUPLICATE` leak, on 2 of 10.  **Both known instrument defects
reproduced here; neither is repaired by this wave and both are visible in the
table because `sw/adcone_g6_table.py` prints `k` beside the ceiling.**

### 2.2 THE PREDICTIONS, SCORED AS REGISTERED

| id | registered | measured | |
|---|---|---|---|
| **P-1** | worst-of-5 improves **≥ 2.0 MHz on at least one** configuration | **+2.74 (CTL)** and **+3.76 (RET)** — **both** | **MET** |
| **P-1a** | CTL ∈ [42.0, 46.5] · RET ∈ [41.0, 46.0] | CTL **41.71** · RET **43.50** | ⚠ **CTL MISSED — BELOW the band by 0.29 MHz**; RET MET. The band came from the anatomy's 4.691 ns/path capped by each draw's own rung-1a ceiling; **what it did not model is that the ceiling MOVES when the netlist does.** Reported as registered, not restated. |
| **P-2** | the whole golden + pin-sensitive ladder unmoved | §1, every row | **MET** |
| **P-3** | `chain_lfsr` 4/4 signatures and 306 `fz2_replay` `sys` blocks byte-identical | 4/4 and **306 / 1,243,278 rows** | **MET** |
| **P-4** | `r7_lint` PASS, counts unchanged | PASS, 20 / 1 / 3 / 51 / 0 | **MET** |
| **P-5** | `SS_COUNT` 232 unchanged, flops 220 → 221, whitelist 2 → 3, 0 UNMAPPED | exactly that | **MET** |
| **P-6** | `$v30u_ce` **1805 → 1815** | ⚠ **MISSED AS REGISTERED, AND THE BAR WAS THE WRONG SHAPE.** The count is **STAGE-DEPENDENT** — the R7 refutation's own finding (`ucore_provenance.md` §70: *"the two figures were different STAGES of one flow, the collection GREW stage for stage"*), and P-6 picked one stage's number without saying which. Like for like: **first read 1161 → 1181 (+20)**, placement-prep read **1805 → 1758**, STA read **1937 → 2032-2061 (CTL)** / **1905-1908 (RET)**. **The load-bearing question P-6 was really asking — is the M10K inside `$v30u_ce`? — is answered YES**: `…|ucdecode_rtl_0|…|ram_block1a4~PORT_A_WRITE_ENABLE_REG` appears as a `$v30u_ce` endpoint in the k=4.0 class row of every draw, so the 4/3 CE multicycle covers the inferred memory's arcs. | ⚠ |
| **P-7** | the k=4 `CORE→CORE` class does not become binding | **+31.613 ns (CTL) / +32.431 (RET)** against binding **+7.276 / +8.929** — and it got *shorter*, as predicted, because the same edit takes `ucdecode` **and** `ucrom` off the `upc → … → chain → upc_n` path | **MET** |
| **P-8** | every draw a G6 PASS, E7/E8 clean | 10/10, E7 1 exempt / 0 offending, E8 5+5 | **MET** |
| **P-9** | *recorded, not predicted*: does Quartus now infer an M10K? | **YES** — `altsyncram:ucdecode_rtl_0`, `OPERATION_MODE ROM`, 8192 × 12, `dec_q[0..9]` **packed into it as the address register**, `OUTDATA_REG_A UNREGISTERED`, `INIT_FILE db/…hdl.mif`. §3.3 | **RECORDED** |
| **P-10** | ALMs move < ±2 % | CTL 10,336-10,391 → **10,085-10,154** (−2.2 %), RET 10,215-10,257 → **10,134-10,194** (−0.7 %) | **MET (CTL at the edge, in the good direction)** |

---

## §3 THE CENSUS — WHAT BINDS NOW

Probes on each configuration's own fitted `db`
(`sw/testdata/adcone/l1/census-{ctl,ret}/`).  The CONTROL leg cost one extra
map + fit at **seed 1, the worst draw**, and that fit **reproduced +7.276 to the
digit** — so the census is on the draw the sweep scored, not on a neighbour.

### 3.1 THE MICROCODE HEAD IS OUT OF THE CONE

| | before (CTL seed 5) | after (CTL seed 1) | after (RET seed 5) |
|---|---:|---:|---:|
| `UCROM` region, ns / path | **8.976** | **1.545** | 8.852 |
| `UCROM` region, cells / path | **8.3** | **0.8** | 5.0 |
| `ucdecode` on the worst path | 4.770 ns / **5 cells** | — | **1.046 ns / 0 cells** |
| `ucrom` on the worst path | 5.051 ns / 4 cells | — | 3.994 ns / 3 cells |
| whole data path | **25.031 ns / 29 cells** | — | **20.701 ns / 23 cells** |

**On CONTROL seed 1 neither `ucdecode` nor `ucrom` appears in the ≥25 % net
census at all.**  What replaced them there: `Mux95` (49/60, 3.782 ns/hit),
`Add4` (50/60, 3.382), `Mux309` (47/60, 2.984) — EU rails, not the ROM.

The RETENTION leg still shows the head because its own worst path launches from
the M10K, and there it is **1.046 ns of data and ZERO combinational cells**
where the LUT ROM was 4.770 ns and five.  **The M10K's `clk→q` is 1.594 ns
against an ordinary flop's 0.569, so ~1.0 ns of the 3.7 ns saved is handed
back on the launch side** — which is why the measured gain is ~+3 MHz and not
the ~+6 the LUT count alone would suggest.

### 3.2 WHAT BINDS, AND HOW FAR BEHIND IT THE NEXT WALL IS

Class table on each draw's own `db`:

| class | CONTROL seed 1 | RETENTION seed 5 |
|---|---:|---:|
| `CORE→ANY` (the observation cone) | **+7.276** `opc_from_modrm → ad_in_q[14]` — **BINDS** | **+8.929** `ucdecode M10K → ad_in_q[3]` — **BINDS** |
| `ANY→CORE` | **+7.949** `c_int_q~DUP → v30u_eu\|rd_pending[0]` | +9.289 `cfg_clk_div[5] → t1_half2` (k=0.5) |
| `CORE→CORE` (k = 4) | +31.613 | +32.431 |

**`c_int_q → v30u_eu|{row_posted, rd_pending[*]}` is the rung-1a wall on 8 of
the 10 draws** (the other two are the §6-contaminated k=0.5 reads).  Its
ceiling: **42.50 · 42.92 · 47.34 · 50.27 (CTL, n=4)** and **45.21 · 45.96 ·
46.57 · 47.42 (RET, n=4)**.

> **So a PERFECT fix of everything the observation class still contains moves
> `worst-of-5` from 41.71 → 42.50 (CONTROL, +0.79) and from 43.50 → 45.21
> (RETENTION, +1.71), and then `c_int_q` binds on every draw.**
> On CONTROL seed 4 and RETENTION seed 1 it binds **already**.

### 3.3 THE M10K — RECORDED, WITH ONE NEW OWED BAR

Quartus's refusal to infer a memory for `ucdecode` was for *"asynchronous read
logic"* (`v30u_ucrom.sv`).  With the output registered it infers one:

```
altsyncram:ucdecode_rtl_0   OPERATION_MODE ROM   8192 x 12   WIDTHAD_A 13
OUTDATA_REG_A UNREGISTERED  (so `dec_q` is realised as the ADDRESS register)
Registers Packed Into Inferred Megafunctions:  dec_q[0..9]
INIT_FILE db/nec_test_ucore.ram0_v30u_ucrom_f358d0ef.hdl.mif
```

`q(t) = mem[addr_reg(t)]` with `addr_reg(t) = dec_addr_next(t-1)` is *exactly*
what the RTL says, so nothing moves — **but the `.mif` is a build artefact no
functional gate had ever looked at.**  Hence `sw/ucrom_mif_check.py`, and it
reads **PASS on both configurations' own `db`**: 8192 × 12 against
`ucdecode.hex` and 1028 × 29 against `ucrom.hex`, **every word identical**,
non-vacuous (one flipped bit at address 0 → FAIL).

⚠ **THE OWED BAR: no bitstream carrying an M10K `ucdecode` has been in fabric.**
F44's failure mode is a *silent* empty table, and Verilator cannot see it. Before
any flash of this tree, `ucrom_mif_check` must be run on that build's own `db`
**and** first light `check_ab_hw` MATCH 800 ×3 must be taken as usual.  **This
wave flashes nothing.**

---

## §4 THE VERDICT AND THE NEXT LEVER

### 4.1 VERDICT — **L1 LANDS**

P-1's floor is met on both configurations with margin (+2.74 / +3.76 against a
2.0 bar), the ladder is byte-identical on every leg that has a control, and the
edit is twelve lines with no SDC change and no new SSA address.  **The
`ucrom → assign ad_o` lever named by `timing50_e1_rederivation_2026-08-12.md`
§8.3 as "THE PAIRED RTL ITEM" is now landed** — which matters beyond the MHz,
because §8.3 made its recommendation (c) honest *only if paired with it*.

⚠ **ONE CAVEAT THE MEASUREMENT CANNOT REMOVE.**  The AFTER side carries a new
map; the BEFORE side does not (this wave re-measured seeds 5, 6 and 8 on its own
map and got 38.97 / 39.79 / 41.28 to the digit).  Historical map variance is
~2.3 MHz, **larger than P-1's floor**, so the CONTROL result of +2.74 is inside
that band and the RETENTION result of +3.76 is barely outside it.  What raises
confidence above the arithmetic is that the CENSUS agrees with the edit
mechanism cell for cell: the microcode head left the cone (8.3 → 0.8 cells/path),
the launch register moved to the ROM, and the two classes converged exactly as a
3.7-ns shortening of one of them predicts.

### 4.2 THE NEXT LEVER — **`c_int_q`, AND IT IS R7′ AGAIN**

Ranked by the census and by nothing else:

1. **`c_int_q → v30u_eu|{row_posted, rd_pending[*]}`** — rung 1a on 8 of 10
   draws, **0.673 ns behind the binding cone on CONTROL seed 1 and already
   binding on two draws**.  It is the *same shape* R7′ closed once already: a
   **live rig pin reaching the EU's next-state cone single-cycle**, exactly as
   `c_ready_q` did before §73 put it on a register's `D` pin.  `r7_lint` was
   written for that invariant and does not model this net.
   ⚠ **`timing50_e1_rederivation_2026-08-12.md` §6.2's verdict that "closing
   `c_int_q` would move Fmax by ZERO" is now REFUTED BY MEASUREMENT, not by
   argument** — it was true of the tree it was measured on and is false of this
   one.  (`t1_half2_results_2026-08-13.md` §8.2 had already withdrawn it on
   different grounds.)
2. **Finish the observation class** — worth **+0.79 (CTL) / +1.71 (RET)** and no
   more, measured.  Its remaining content is EU rails (`Mux95`, `Add4`,
   `Mux309`) and the `ad_o` mux, not the microcode.  **`ucrom` as a second
   registered table (the L2 that was deliberately not bundled) is inside this
   +0.79/+1.71 and cannot exceed it**; it is therefore *not* recommended on
   timing grounds alone.
3. **The k = 0.5 enable arc** `div_cnt / cfg_clk_div → t1_half2` — it now
   appears as the *smallest-slack* path on 2 of 5 RETENTION draws (which is why
   the probe's `DEFAULT` row misreports them). By `slack/k` it is still clear,
   but it is closer than it was and it is RTL-only.

**AND THE PAIRED-REPORTING HANDOFF SHOULD NOW BE TAKEN.**
`timing50_e1_rederivation_2026-08-12.md` §8.3 recommended reporting
**whole-design Fmax** (the promotion gate, unchanged) *beside* **core-domain
Fmax**, "**only if it is paired with the RTL item**" — the item being this
cone.  That item is landed, so the pairing's precondition is discharged and the
re-scoping no longer hides anything: on this tree `CORE→CORE` carries
**+31.6 / +32.4 ns** while the design binds at **+7.3 / +8.9**, and **both of
the cones that bind now have one endpoint in the rig** (`nec_bus|ad_in_q`,
`system_large|c_int_q`).  **Recommend: adopt (c) paired, and open `c_int_q`
as the next wave.**

### 4.3 WHAT IS BOOKED, NOT DONE

1. **A fabric bar for the M10K `ucdecode`** — §3.3. Owed before any flash.
2. **`sta_truefmax_probe.tcl`'s two defects reproduced here** — the `~DUPLICATE`
   leak (2 of 10 rung-1a cells) and the `DEFAULT`-row-by-slack artifact (2 of 5
   RETENTION draws). Both were already booked by the distribution gate; this
   wave adds that the leak now also hits **RUNG 2's `c_int_q` exclusion**
   (`c_int_q~DUPLICATE` is not matched by it), which matters more than before
   because `c_int_q` is the next lever.
3. **`sw/testdata/ie-pinfall/core/table.json` IS STALE ON `master`** — §1.3.
   Not this wave's to fix, but named.
4. **L2, the registered ROW table** — capped at §3.2's +0.79 / +1.71 and
   therefore not recommended on timing grounds. If it is ever wanted for another
   reason, the construction is identical and is written out in
   `adcone_l1_prereg_2026-08-13.md` §1.
5. **`v30u_ucrom`'s `dec_addr` port is now fed a *next*-clock address** and its
   own header still describes it as "the 13-bit micro-address".
   **Deliberately NOT edited**: an `hdl/` edit after the builds is an `hdl/` edit
   that was not measured, and the manifest `d47c1d003d64c4c5…` in both receipts
   must keep naming the bytes that were compiled. The instantiation side in
   `v30u_eu.sv` carries the full explanation.
