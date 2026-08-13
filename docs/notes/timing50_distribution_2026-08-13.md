# THE G6 DISTRIBUTION GATE — N=8 BASELINE, BOTH CONFIGURATIONS

Pre-registration `b74c79d6ea` (`timing50_distribution_prereg_2026-08-13.md`),
committed **before the first fit**.  Tree `a74c741d1c` (`master`); `hdl/` is
byte-identical to `41a60bd42c`, so every historical draw quoted below is a draw
of **this** tree.  **Offline.  Quartus is the instrument.  NO board, NO flash,
NO RTL — `hdl/` is untouched by this wave.**

---

## §0 HEADLINE

**The honest worst-case band of this tree is `worst-of-8@seeds{1..8}` =
38.97 MHz (CONTROL) and 37.73 MHz (RETENTION) — and BOTH are below every
single draw ever registered for it.**

| | CONTROL | RETENTION |
|---|---:|---:|
| **worst-of-8@seeds{1..8}** — **the quotable figure** | **38.97** (seed 5) | **37.73** (seed 8) |
| median of 8 | 40.475 | 40.230 |
| best of 8 | 42.31 (seed 4) | 41.73 (seed 2) |
| **spread** | **3.34 MHz** | **4.00 MHz** |
| previously registered for this tree | 39.79 ×3, 42.09 | 43.76 ×2, 39.99 |
| distribution record | `b7e122d9b2f90197…` | `901c655ecf7ae398…` |

**Every one of the 16 draws is a G6 PASS** (E1-E5: Fmax ≥ 32, worst setup > 0,
TNS 0.000 setup AND hold), on the 88-file input manifest
**`c23e63aa4cf19684…`**, `build_id.v` = `` `define BUILD_DATE "260813" ``.
Wall clock 2,952 s + 2,935 s = **98 minutes** for 2 maps + 16 fits + 16
assembles + 32 STA runs.

**All nine registered predictions are MET.**  The five findings that were not
predicted are §5-§9, and two of them are instrument defects this sweep exposed
that a single draw structurally cannot see.

---

## §1 THE INSTRUMENT

`python3 sw/quartus_gate.py --seeds N [--retention]` — **one `quartus_map`,
then N × `quartus_fit --seed=S --recompile=off`**, each followed by
`quartus_asm`, `quartus_sta` and `sw/sta_truefmax_probe.tcl`.

Map-once is the load-bearing choice: it makes the N draws a distribution **of
one netlist**.  Re-mapping per seed would fold Analysis & Synthesis
non-determinism into the same number as placement variance and report two
effects as one — **and §7 shows those two effects are genuinely different and
that this instrument measures only the second.**

**Per seed**: its own receipt in `sw/testdata/g6dist/<label>/`, self-labelling
the **configuration** (still DERIVED from the reports, never from the flag) and
the **seed** (asked AND echoed), plus the per-k-class ceilings, `.sta.summary`,
and `.sof`/`.rbf` hashes.  **Per sweep**: `distribution.json`.

### 1.1 THE FOUR BARS THE SWEEP ADDS

| bar | what it refuses |
|---|---|
| **E7** input-hash ordering | an input that moved between the hash taken **before** `quartus_map` and the hash taken **after** the last stage.  One DECLARED §70.7 exemption, `hdl/nec_test_ucore.qsf`, because Quartus rewrites the revision file it compiles |
| **E8** seed honoured | a fit that did not use the seed it was given, read back off Quartus's own `Fitter Initial Placement Seed` row.  **A sweep whose flag was accepted-and-ignored reports a spread of 0.00 MHz, which reads as a reassuring result** |
| **E9** every draw passes | any draw RED on E1-E5 |
| **E10** promotion width | `N < 5` being quoted as promotion evidence |

Falsifier `python3 sw/test_quartus_gate.py` — **200/200, no Quartus needed**
(it was 75/75 before this wave).  **It is demonstrably non-vacuous**: on its
first run it caught seven real defects, including `--seeds -3` being ACCEPTED.

---

## §2 THE QUOTING RULE — REGISTERED IN `standing_gates.md` §A

> A distribution figure is **`worst-of-N@seeds{...}`** with N and the seed set
> named, and **the WORST draw is the quotable one**.  A single fit is
> **`draw@seed<S>`** and is **not promotion evidence**.
> **G6 PASS for a PROMOTION requires N ≥ 5.**  N = 2 remains acceptable for an
> intermediate wave measurement **with the caveat printed**.

---

## §3 THE REGISTERED PREDICTIONS, SCORED AS REGISTERED

| # | prediction | measured | verdict |
|---|---|---|---|
| **P-1** | E8 PASS on 16/16 | 16/16, both readings agreeing on every fit | **MET** |
| **P-2** | CONTROL width ∈ [1.5, 6.0] MHz | **3.34** | **MET** |
| **P-3** | RETENTION width ∈ [2.0, 8.0] MHz | **4.00** | **MET** |
| **P-4** | the k=1 DEFAULT class binds on 8/8 and 8/8 | **8/8 and 8/8** — see §3.1, the test had to be re-derived | **MET** |
| **P-5** | ≥ 2 distinct binding endpoint pairs over 8 CONTROL draws | **8 of 8 distinct** (RETENTION also 8 of 8) | **MET, far exceeded** |
| **P-6** | 16/16 draws a G6 PASS | **16/16** | **MET** |
| **P-7** | E7 PASS on both sweeps | PASS on both — ⚠ **after the §70.7 exemption was added mid-wave**, see §3.2 | **MET as re-registered** |
| **P-8** | the two configurations' bands OVERLAP | CONTROL [38.97, 42.31] ∩ RETENTION [37.73, 41.73] = **[38.97, 41.73]**, non-empty | **MET** |
| **P-9** | the AD publication cone binds on ≥ 6 of 8 CONTROL draws | **7/8** land in an observation register, 7/8 launch from `upc_*`; RETENTION is **8/8 and 8/8** | **MET** |

### 3.1 ⚠ P-4's TEST AS WRITTEN WAS NOT A TEST, AND IS RE-DERIVED

The pre-registration said *"the DEFAULT class binds"*, and the obvious way to
score it — *is the `DEFAULT` row the minimum of the five?* — is **trivially
true**, because `sta_truefmax_probe.tcl`'s `DEFAULT` row is an **unconstrained**
`get_timing_paths`: the worst path by SLACK over the whole design.  It names the
k=1 binding path only when the k=1 path happens to have the smallest slack.
**On CONTROL seed 3 it did not** — the row returned `div_cnt[4] →
t1_half2~DUPLICATE` at **k=0.5**.

The valid test, and the one scored above: **k=1 binds iff Quartus's own Fmax is
strictly below all four EXPLICITLY-CONSTRAINED class ceilings** (k=0.5, 1.5,
2.5, 4.0), which are real class queries and are not contaminated.  That holds on
**16 of 16 draws**.  *This is §2 of the k=0.5 wave — rank by `slack/k`, not by
slack — biting the instrument that was written to state it.*

### 3.2 ⚠ E7 AS FIRST WRITTEN FAILED ON A KNOWN EXEMPTION, AND THAT IS REPORTED

The first complete CONTROL sweep went **RED on E7** with exactly one file moved:
`hdl/nec_test_ucore.qsf`.  That is not a mid-build input flip — it is Quartus
rewriting the revision file it compiles (§70.7), which is the whole reason E1
runs BEFORE the build and `gen_ucore_qsf.py` runs after it.  It is the **same
single exemption the fabric era guard already carries**.

The exemption is a **named list of one, not a pattern**, and the bar reports
`moved_exempt` and `moved_offending` separately so the rewrite stays visible.
`hdl/nec_test.qsf` is NOT exempt.  Falsifiers were added for all three cases,
including *an RTL flip ALONGSIDE the exempt rewrite is still RED* — without
which the exemption could have degraded into "a `.qsf` moved, so pass".

**P-7 is reported as MET against the re-registered bar, not against the bar as
pre-registered.**  Both sweeps report `n_moved` 1, offending 0.

---

## §4 THE DRAWS

### 4.1 CONTROL — `worst-of-8@seeds{1,2,3,4,5,6,7,8} = 38.97 MHz`

| seed | Fmax | worst setup | ALMs | binding cone | rung 1a | benefit |
|---|---:|---:|---:|---|---:|---:|
| 1 | 42.09 | +7.489 | 10,371 | `upc_opc[6]~DUP → ad_in_q[16]` | 43.59 | +1.50 |
| 2 | 39.84 | +6.148 | 10,343 | `upc_opc[6]~DUP → ad_in_q[8]` | — | ⚠ §6 |
| 3 | 40.95 | +6.759 | 10,391 | ⚠ probe returned k=0.5, §3.1 | — | ⚠ §6 |
| 4 | 42.31 | +7.616 | 10,381 | `upc_opc[5]~DUP → ad_in_q[14]` | — | ⚠ §6 |
| **5** | **38.97** | **+5.592** | 10,336 | `upc_opc[7]~DUP → ad_in_q[14]` | 45.77 | +6.80 |
| 6 | 39.79 | +6.115 | 10,345 | `upc_opc[3]~DUP → ad_in_q[14]` | 49.95 | +10.16 |
| 7 | 40.00 | +6.248 | 10,384 | `upc_opc[6]~DUP → ad_in_q[15]` | 44.43 | +4.43 |
| 8 | 41.28 | +7.023 | 10,370 | `upc_page[1] → ad_in_q[14]` | 51.23 | +9.95 |

### 4.2 RETENTION — `worst-of-8@seeds{1,2,3,4,5,6,7,8} = 37.73 MHz`

| seed | Fmax | worst setup | ALMs | binding cone | rung 1a | benefit |
|---|---:|---:|---:|---|---:|---:|
| 1 | 39.99 | +6.242 | 10,257 | `upc_opc[5]~DUP → ad_in_q[7]` | 49.51 | +9.52 |
| 2 **R** | 41.73 | +7.288 | 10,250 | `upc_opc[7] → ad_in_q[8]` | 44.26 | +2.53 |
| 3 | 40.88 | +6.787 | 10,231 | `upc_opc[3]~DUP → ad_in_q[12]` | 47.42 | +6.54 |
| 4 | 40.13 | +6.334 | 10,242 | `upc_opc[6] → ad_in_q[12]` | 46.22 | +6.09 |
| 5 | 39.74 | +6.085 | 10,228 | `upc_opc[0]~DUP → ad_in_q[11]` | 50.37 | +10.63 |
| 6 | 40.94 | +6.824 | 10,226 | `upc_opc[2]~DUP → core_ad_hold[11]` | 48.60 | +7.66 |
| 7 **R** | 40.33 | +6.457 | 10,234 | `upc_opc[1]~DUP → ad_in_q[10]` | 46.23 | +5.90 |
| **8** | **37.73** | **+4.745** | 10,215 | `upc_opc[3]~DUP → ad_in_q[8]` | 48.15 | +10.42 |

**R** = the per-k-class row is RECOVERED from a probe that crashed at exit; §8.

**16 draws, 16 distinct `.rbf`.**  Every draw of one input manifest is a
different bitstream, and no two agree.

---

## §5 FINDING — THE HONEST BAND IS BELOW EVERYTHING PREVIOUSLY QUOTED

`worst-of-8` is **38.97 / 37.73**.  The registered draws for this identical
tree were CONTROL 39.79 ×3 and 42.09, RETENTION 43.76 ×2 and 39.99.

**Every previously registered figure for this tree is above its own
worst-of-8**, by 0.8-3.3 MHz (CONTROL) and 2.0-6.0 MHz (RETENTION).  Nothing was
wrong with those measurements; they were single draws, and a single draw is a
sample from the upper part of a band as often as the lower.  **The FLASH #18
sitting's observation that its flashed build cleared its own 38.0 STOP "by only
+0.82 MHz" now reads differently: at worst-of-8 that margin is negative.**

---

## §6 FINDING — AN INSTRUMENT DEFECT ONLY A SWEEP COULD FIND: THE `~DUPLICATE` LEAK

`sta_truefmax_probe.tcl:58` builds its exclusion collection as

```tcl
set v30u_half [get_registers -nowarn {*|v30u_biu:*|t1_half2}]
```

— an **exact name**.  The fitter is free to duplicate that register, and on
**CONTROL seeds 2, 3 and 4 it did**, producing `t1_half2~DUPLICATE`, which the
pattern does **not** match.  So `RUNG 1a` — documented as *"the worst k=1
survivor"* — returned the **k=0.5 ENABLE arc** on those three draws, at 71.94,
56.40 and 79.45 MHz.

**Those three rung-1a cells are CONTAMINATED and are excluded from every
benefit figure in this document.**  They are shown as `⚠ §6` in §4.1 rather
than deleted.

**A single draw cannot find this.**  The k=0.5 wave measured seed 1, where no
duplicate exists, so `RUNG 1a` returned the genuine `c_int_q → row_posted` and
the exclusion looked sound.  3 of 16 draws here were affected.

**Booked, not fixed in this wave**, because fixing it requires re-fitting to
re-measure and the fix belongs with the probe's own next use.  The fix is to
match the duplicate suffix; the falsifier is that CONTROL seeds 2/3/4 must then
return a `k = 1.0` path.  ⚠ **The FIVE exception-class rows are NOT affected** —
`k=1.5`, `k=2.5` and `k=0.5` all use the same collection but they use it as a
*destination they want*, not as an *exclusion*, so a missed duplicate can only
make those queries conservative, never wrong in the unsafe direction.

---

## §7 FINDING — THERE ARE **TWO** SOURCES OF VARIANCE AND THIS GATE MEASURES ONE

**The fit is deterministic given (netlist, seed).**  Measured three ways:

* CONTROL seeds 1-8 were run **twice**, on two independently produced maps, and
  **all eight values reproduced to the digit** (42.09 · 39.84 · 40.95 · 42.31 ·
  38.97 · 39.79 · 40.00 · 41.28 both times).
* CONTROL seed 1 = **42.09 / +7.489 / 10,371 ALMs** — the k=0.5 wave's
  `--flow compile` CONTROL draw, to the digit.
* RETENTION seed 1 = **39.99 / +6.242 / 10,257 ALMs** — likewise.

**So the 2.30 MHz CONTROL disagreement the k=0.5 wave recorded (CHAIN_MAX 39.79
×3 vs t1half2 42.09, same manifest) CANNOT be fit-seed variance**: both were
`SEED 1`, and seed 1 on this tree draws 42.09 three times out of three.  It must
be a **MAP-level** difference — §74.4a's *"Analysis & Synthesis is not
reproducible run to run; the REGISTER counts are, the COMBINATIONAL counts are
not"*.

**The consequence, and it is the most important caveat in this document:**

> **This instrument characterises PLACEMENT variance at a fixed map.  MAP
> variance sits on top of it and is NOT measured here.**  The historical record
> puts map variance at ~2.3 MHz (CONTROL) and ~3.8 MHz (RETENTION) at fixed
> seed.  **So `worst-of-8` = 38.97 / 37.73 is an UPPER bound on the honest
> worst case, not the worst case.**  A worst-of-N over *(map, seed)* pairs
> would be the complete instrument and is **BOOKED, not built** — it costs a
> re-map per draw, i.e. ~3× the wall clock.

Note that 39.79 — CHAIN_MAX's three-times-agreeing CONTROL figure — **appears in
this sweep at seed 6**.  That is a coincidence of two different mechanisms
landing on the same number, and is recorded as such rather than as a
reconciliation.

---

## §8 FINDING — `quartus_sta` CRASHED AT EXIT ON 2 OF 16 DRAWS, AFTER FINISHING

On RETENTION seeds 2 and 7 the class probe wrote its **complete** artifact —
all five exception classes, all four rungs, trailer included — and then crashed
in Tcl namespace teardown, returning **rc=2**.

The gate originally keyed acceptance on the exit code and **discarded a valid,
finished measurement**.  Fixed: `truefmax_complete()` judges the **artifact**
(every one of the five classes present WITH a ceiling), and the rc is recorded
either way in `truefmax_probe.salvaged_despite_rc`.  *Verify against the
artifact, not against a proxy for it* — the proxy here was an unrelated crash in
the tool's shutdown path.

**The two receipts as written carry no per-class rows**, because the fix landed
after that sweep.  The raw artifacts are retained verbatim at
`sw/testdata/g6dist/g6dist-retention-n8/seed{2,7}.truefmax.RECOVERED.txt`, are
labelled **R** in §4.2, and both parse as COMPLETE under the new check.  **The
receipts were NOT retro-edited.**

---

## §9 WHAT THIS MEANS FOR 50 MHz AND THE `upc_opc → ad_in_q` LEVER

**The lever is confirmed as the right one, and its benefit is a distribution,
not a number.**

The binding cone is `upc_* → observation register` on **15 of 16 draws** (the
16th is CONTROL seed 3, where the probe's DEFAULT row is the §3.1 artifact — an
instrument gap, not a counterexample).  It is a *different endpoint pair on
every single draw*: 8 distinct pairs out of 8 on each configuration, ranging
over `ad_in_q[7,8,10,11,12,14,15,16]` and `core_ad_hold[11]`.

> **The cone's IDENTITY as a class is a property of the tree.  The individual
> path is a property of the draw.**  So the lever is real, but no *specific*
> path may be optimised against — a fix aimed at `ad_in_q[16]` would be fitting
> to seed 1.

**What closing the whole observation class is worth**, measured per draw as
rung 1a minus that draw's own Fmax, on the 13 uncontaminated draws:

| | min | max | spread |
|---|---:|---:|---:|
| CONTROL (n=5) | **+1.50** | **+10.16** | 8.66 |
| RETENTION (n=8) | **+2.53** | **+10.63** | 8.10 |

**The k=0.5 wave quoted `+1.50 (CTL)` and `+9.52 (RET)`.  Both are seed-1
draws, and the CONTROL one is the MINIMUM of its own distribution.**  Neither
was wrong; neither was the benefit.

**And the ceiling you would land on is also a distribution**: rung 1a is
**43.59-51.23 MHz (CONTROL)** and **44.26-50.37 MHz (RETENTION)**.  The next
wall is `c_int_q → v30u_eu|row_posted` on **13 of 13** uncontaminated draws —
which confirms the k=0.5 wave's §4 correction (that `c_int_q` DOES bind once the
observation class is fixed) on 13 draws instead of one.

**So, stated honestly:**

1. **A perfect fix of the observation class does not reach 50 MHz on a
   worst-of-8 basis.**  It moves the worst draw to roughly 44-46 MHz, and
   `c_int_q → row_posted` is then the wall on every draw.
2. **50 MHz needs BOTH rig↔core single-cycle crossings closed**, and behind
   them sits the EU's own k=4 class, whose own worst-of-8 is **58.80 MHz
   (CONTROL)** / **55.98 MHz (RETENTION)** — itself only ~6-9 MHz of headroom
   above 50, and itself a distribution.
3. **Any benefit claim for either lever must now be quoted as a worst-of-N
   difference**, because a benefit measured on one draw pair has an error bar
   of ±8 MHz — larger than either lever's own effect.

### 9.1 A NOTE ON THE k=0.5 ENABLE ARC

It **never binds — 16 of 16 draws**, which confirms the k=0.5 wave's
disposition (no RTL change) on 16 draws rather than 2.  But its clearance is
**not** the 48.8 MHz that single draw suggested: across the sweep its ceiling
ranges **56.40 – 91.66 MHz**, so the margin over the binding path ranges from
**+15.45 MHz (CONTROL seed 3)** to **+51.66 MHz**.  Still clear on every draw;
*"48.8 MHz clear"* was the luckiest draw of eight.

---

## §10 THE LADDER — RE-MEASURED AT HEAD AS A CONTROL

No RTL was changed, so these are a control on the worktree, not an equivalence
claim.

| gate | registered | measured |
|---|---|---|
| `test_artifact` | 45/45 | **45/45**, non-vacuous |
| `test_quartus_gate` | 75/75 | **200/200** (Q9-Q15 added this wave) |
| `r7_lint` | PASS, 0 violations | **PASS** — 20 nets / 1 carrier / 3 tainted / 51 `stop` sites / 0 violations |
| `ss_lint --core ucore` | `SS_COUNT` 232 / 220 flops / 0 UNMAPPED | **PASS** — 109×2 BIU + 122×2 EU + tag = **232**; **220** flops, 0 UNMAPPED |
| `gen_ucore_qsf --check` | PASS | **PASS** (E1, on all 16 draws) |
| `check_core --opcodes 8F.0` | 500 | **500/500 full** (cycles 500, arch 500), TB receipt `c90e89f96b8d0db1…` |
| **G6 CONTROL** | ≥ 32 MHz, setup > 0, TNS 0.000 | **PASS on 8/8 draws**, `worst-of-8` **38.97** |
| **G6 RETENTION** | ≥ 32 MHz, setup > 0, TNS 0.000 | **PASS on 8/8 draws**, `worst-of-8` **37.73** |

---

## §11 A RIG DEFECT FOUND ON THE WAY IN — THE RECORDED `--retention` RECIPE COULD NOT BUILD

`hdl/sys/sys.tcl:211` sets `PRE_FLOW_SCRIPT_FILE "quartus_sh:sys/build_id.tcl"`,
and that hook is honoured by `quartus_sh --flow compile` **and by nothing
else**.  Any path invoking `quartus_map` directly skips it, so `hdl/build_id.v`
— which `nec_test.sv:200` includes — is never generated:

```
Error (10054): ... can't open Verilog Design File "build_id.v"
```

Measured on this worktree: **exit 3 in 11 s, on both configurations.**

**The defect is not the sweep's.**  It is in the **recorded four-step
`--retention` recipe** too, and has been latent since that recipe was written:
`build_id.v` is gitignored and left behind by any previous CONTROL
`--flow compile`, so every retention build ever taken found one already there.
On a fresh clone or worktree, `--retention` fails at map.  *It is the same shape
as the `check_ab_sim` finding — a path that only ever ran second.*

Fixed by running the project's own hook explicitly; the four recorded stages are
unchanged in content and order.

⚠ **`build_id.v` is a build input that `input_files()` does not name**, and it
is recorded **beside** the manifest rather than inside it: it is a `%y%m%d` date
stamp, so folding it in would move the input hash every midnight and destroy the
comparability that lets this wave say its manifest `c23e63aa4cf19684…` is the
one the k=0.5 wave and the CHAIN_MAX draws were taken on.  **The gap is named,
not closed silently.**

---

## §12 A SECOND RIG FINDING — TWO SWEEPS SHARED ONE `hdl/db`

An orphaned `quartus_gate.py --seeds` survived a `pkill` and was found fitting
**alongside** a freshly launched sweep, both writing the same
`hdl/output_files_ucore` reports.  Neither run's figures would have been
attributable to its own fits, and **nothing would have said so**.

`sw/run_g6dist_n8.sh` now carries a **single-writer guard** — the board
discipline's rule applied to the build tree — matching stage binaries by exact
name (`pgrep -x`), because `pgrep -f 'quartus_gate.py --seeds'` matches its own
argv and would refuse every run: broken in the safe direction, and therefore
never noticed.  It was demonstrated to refuse against a live `quartus_map`
before being relied on.

**No figure in this document comes from the interleaved run.**  Everything in
§4 is from the sweeps started after the guard landed, from a wiped `db`.

---

## §13 WHAT IS BOOKED, NOT DONE

1. **A worst-of-N over `(map, seed)` pairs** — §7.  The complete instrument.
   ~3× the wall clock.  Until it exists, `worst-of-8` is an upper bound on the
   honest worst case.
2. **The `~DUPLICATE` leak in `sta_truefmax_probe.tcl`** — §6, with its
   falsifier written down.
3. **N=8 is one sample of a distribution too.**  Nothing here says 8 is enough;
   it says 1 is not, and that the spread at N=8 is 3.34 / 4.00 MHz.
