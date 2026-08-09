# RETENTION BUILD PRE-REGISTRATION — `fuzz-v2-on-relanding` @ `c5f29a405b`

Written and committed **BEFORE** the first retention compile of this tree.
Nothing below was edited after a number existed.

## §1 WHY THIS RUN EXISTS

`c5f29a405b` records G6 GREEN on the **CONTROL/DEFAULT** build of this branch:
**41.80 MHz**, worst setup **+7.325 ns**, TNS **0.000** setup and hold on every
domain, ALMs **12,096 / 41,910 (29 %)**, fitter registers **6,078**, two draws
with a byte-identical `.rbf` **`c09e9b63f37d7c14…`**, receipts
**`b6a76f1acdb06a35…`** (draw 1) and **`7d6c5da3b1d1d92b…`** (draw 2).

**But the bitstream that gets flashed is the RETENTION build**
(`X1_AD_RETENTION=1`) — it is the RESTING CONFIGURATION since FLASH #6
(`ucore_provenance.md` §69.4/§73.8, `wrfuzz_provenance.md` W4 §, CLAUDE.md's
board line: FLASH #6, #9, #10 and #11 were all retention builds), and the whole
W1 corpus was captured on one.  Retention has **never been built on this tree**.

## §2 THE MECHANISM — READ, NOT GUESSED

`sw/quartus_gate.py`'s own `build()` runs
`quartus_sh --flow compile nec_test -c nec_test_ucore` with **no
`--verilog_macro`**; it therefore CANNOT produce a retention build.  The
recorded recipe (`sm3_s19b_prereg` §B.1, `sm3_s27_prereg` §A.1,
`wrfuzz_w4_prereg` §, `ucore_provenance.md` §69.4/§73.8, all four in identical
words) is, from the same clean regenerated `.qsf`:

    quartus_map --verilog_macro="X1_AD_RETENTION=1" nec_test -c nec_test_ucore
    quartus_fit nec_test -c nec_test_ucore
    quartus_asm nec_test -c nec_test_ucore
    quartus_sta nec_test -c nec_test_ucore

then `quartus_gate.py --parse-only --no-qsf-check`, which is exactly how all
four archived retention receipts were written (`build` = `{"note":
"--parse-only: reports gated as found"}`, `E1` = `skipped (--no-qsf-check)`).
`.rbf` comes from the assembler: `GENERATE_RBF_FILE ON` is set in
`hdl/nec_test_ucore.qsf` line 29, so `quartus_asm` emits it; there is no
post-flow script and no `quartus_cpf` step in this tree.

`gen_ucore_qsf --check` is run GREEN BEFORE the build and the `.qsf` is
regenerated and re-checked AFTER, because a hand-run `quartus_map` writes
settings files and appends pin assignments — the §80.B.1 artefact that makes a
retention receipt's `input_manifest` differ from its control's.  That
difference is RECORDED, not barred, and it is the reason the archived retention
receipts carry a different manifest hash from the control taken minutes before.

## §3 THE PREDICTION

**Point estimate: retention Fmax ≈ 41 MHz; band 39.5 – 41.8 MHz; PASS with
≥ 7 MHz of margin over the 32 MHz bar.**

Reasoning, from every control→retention pair in the receipt history:

| sitting | control | retention | Δ |
|---|---|---|---|
| SM3 s12 | 45.89 | 45.87 | **−0.02** |
| SM3 s19 | 45.49 | 44.99 | **−0.50** |
| SM3 s27 | 47.85 | 45.72 | **−2.13** |
| wrfuzz W4 | 47.31 | 46.74 | **−0.57** |
| T9 fuzz-v2 (pre-rebase, tree already RED) | 15.14 | 14.76 | −0.38 |

The retention model is 20 registers on the OBSERVATION path (`hb_ad_sample`,
`system_large.sv` §427-471) keyed on the `AD_OE` port; it adds no core logic and
sits in no core timing cone.  The observed cost is 0.02–2.13 MHz, and the worst
case of that band applied to this tree's 41.80 gives 39.67.  I therefore predict
**no domain below 32 MHz**.

Secondary, all RECORDED not barred:

* worst setup **+5.0 to +7.5 ns** (control +7.325; historical retention cost
  −0.12, −1.42, −2.50 ns, and +0.31 once);
* TNS **0.000**, setup AND hold, on every domain;
* ALMs **12,050 – 12,350** (control 12,096; historical retention deltas
  +18, +100, +112, and −251 once — A&S combinational counts are not run-to-run
  reproducible, §74.4a);
* fitter registers **≈ 6,098** (control 6,078, **+20** for the model's own
  registers — the REGISTER counts *are* reproducible, §74.4a).

**THE MACRO'S EFFECT IS CHECKED, NOT ASSERTED**: the retention `.rbf` MUST
differ from the control's `c09e9b63f37d7c14…`.  A `--verilog_macro` that never
reached the compiler would produce the same bitstream, and that is how a silent
no-op would look like a pass.

**Two draws, both receipts retained.**  I predict the two draws agree to the
digit and their `.rbf`s are byte-identical, as this tree's two CONTROL draws
were — but §74.4 governs and that is a prediction, not a bar: one green build is
not closure, and this same design has drawn 19.42 and 45.91 MHz.

## §4 WHAT WOULD REFUTE IT — WRITTEN IN ADVANCE

1. **Retention materially below the 32 MHz bar.**  Then the flash cannot
   proceed and *that is the finding*.  Not to be restated, not to be re-drawn
   until it passes.
2. **Any failing path launching from `system_large|c_ready_q` into `v30u_eu`.**
   That is the ghost-feed cone (R7′, `ucore_provenance.md` §73), and the
   CONTROL build of this tree showed **zero** occurrences of it.  Its
   reappearance under retention would say the macro perturbs the EU's
   next-state cone, which by construction it must not.
3. **A receipt still reading `CONTROL`.**  `sw/quartus_gate.py` was repaired at
   `4bb65d2ab6` so `configuration` is DERIVED from `<rev>.flow.rpt`'s
   `VERILOG_MACRO` rows and `<rev>.map.rpt`'s `Info: Command:` line.  **This run
   is that fix's first exercise in the configuration that matters** — every one
   of the four archived retention receipts (`fdce06392992…`, `a2d605a47f61…`,
   `7aef327c763f…`, `6e9460fabfff…`, the third of which is FLASH #11's and the
   second FLASH #10's) is mislabelled `CONTROL/DEFAULT (no X1_AD_RETENTION)`.
   If the receipt still says CONTROL, the fix is incomplete and that is a
   defect to report, not to work around.

## §5 A CALIBRATION POINT THE BRIEF DID NOT CARRY (written before the run)

The most recent retention build in the archive, **`6e9460fabfff…` "T9 fuzz-v2
RETENTION"**, is **RED**: 14.76 MHz, worst setup **−36.484 ns**, setup TNS
**−16,590.195** on `divclk`.  It was taken on `989a33d28e`, the fuzz-v2 branch
*before* the rebase onto the relanding, and its **CONTROL** draws on the same
tree are equally RED (15.14 MHz, −34.806 ns, receipts `03efc09222a3…` /
`591923a3363e…`).  So that RED is the *tree's*, not the macro's, and it is the
condition the rebase onto `ucore-relanding` was meant to leave behind — which
`c5f29a405b`'s 41.80 MHz control says it did.  It is recorded here because a
prediction should name the nearest contrary datum before the run, not after.

---

# §6 THE RESULT — **BOTH DRAWS PASS.  G6 GREEN ON THE RETENTION BUILD.**

Appended after the run.  Nothing in §1-§5 was edited; the prediction stands as
it was committed at `ce7fa2c073`.

## §6.1 THE RUN

Two independent draws, each from a **deleted `db` / `incremental_db` /
`output_files_ucore`** and a freshly regenerated `.qsf`, each the recorded
recipe verbatim:

    quartus_map --verilog_macro="X1_AD_RETENTION=1" nec_test -c nec_test_ucore
    quartus_fit  nec_test -c nec_test_ucore
    quartus_asm  nec_test -c nec_test_ucore
    quartus_sta  nec_test -c nec_test_ucore
    python3 sw/quartus_gate.py --parse-only --no-qsf-check \
        --log hdl/quartus_gate_retention_draw<N>.log --label "…draw <N> of 2"

Draw 1 **609 s**, draw 2 **618 s**.  All four stages `Successful, 0 errors` on
both draws (1175 / 103 / 2 / 93 warnings, identical counts on both).

## §6.2 THE BARS — as registered

| | bar | **draw 1** | **draw 2** |
|---|---|---|---|
| **E2** | 0 errors, every stage `Successful` | **PASS** — 0 stage errors, 0 error lines, map·fit·asm all Successful | **PASS**, identical |
| **E3** | `divclk` Fmax ≥ 32.0 MHz | **PASS — 40.96 MHz** | **PASS — 40.96 MHz** |
| **E4** | worst setup slack > 0 | **PASS — +6.836 ns** | **PASS — +6.836 ns** |
| **E5** | TNS 0.000, setup AND hold, every domain | **PASS — no violating domain** | **PASS**, identical |
| **E1** | `gen_ucore_qsf --check` | run GREEN before each build; `skipped` in the receipt (`--no-qsf-check`), as every archived retention receipt is | same |

**Per-domain, both draws identical to the digit:**

| clock | setup slack | setup TNS | hold slack | hold TNS |
|---|---|---|---|---|
| `emu\|pll\|…\|divclk` | **+6.836** | **0.000** | +0.251 | **0.000** |
| `altera_reserved_tck` | +8.711 | 0.000 | +0.171 | 0.000 |
| `FPGA_CLK2_50` | +12.889 | 0.000 | +0.426 | 0.000 |
| `pll_audio\|…\|divclk` | +23.396 | 0.000 | +0.259 | 0.000 |

Fmax on the other domains: `FPGA_CLK2_50` 140.63, `pll_audio` 57.85,
`altera_reserved_tck` 62.85.

RECORDED, NOT BARRED, both draws identical: **ALMs 12,021 / 41,910 (29 %)**,
**0 latches**, **0 `lpm_divide`**, A&S registers **5,054**, fitter registers
**5,935**.

**Receipts: draw 1 `9f639c83304fa934…`, draw 2 `27fb750f925c539e…`**, tool
`Version 17.1.0 Build 590 10/25/2017 SJ Lite Edition`, both `verdict: PASS`,
both retained in `sw/testdata/receipts/quartus_bitstream.jsonl`.
Input manifest **88 files `998e129ef7ec3882…` on BOTH draws** — byte-identical,
which is the mechanical statement that `hdl/` did not move between them.
Build logs (untracked, per this tree's existing practice for
`quartus_gate_*.log`): `hdl/quartus_gate_retention_draw1.log`
`1026f6a8ca805c86…`, `draw2` `617bbd75513bbb08…`.

## §6.3 `.rbf` — **BYTE-IDENTICAL ACROSS THE TWO DRAWS**

**`74856c80900bb18c9bc611b50a6245aa4816e1f3e6163b32e3f63d6c36f834de`** on both.

The `.sof`s DIFFER (`5e955cc7f8cde619…` vs `8db6dadf5c4c621c…`).  **That is this
tree's normal behaviour and not a finding**: the two CONTROL draws at
`c5f29a405b` behave the same way — identical `.rbf` `c09e9b63f37d7c14…`,
different `.sof` (`73b741c170488a91…` vs `d8763a0a07e71ab2…`).  The `.rbf` is
the raw configuration bitstream and is the artifact that gets flashed.

## §6.4 THE MACRO'S EFFECT IS CHECKED, NOT ASSERTED — FOUR WAYS

1. **`.rbf` `74856c80900bb18c…` ≠ the control's `c09e9b63f37d7c14…`.**  A
   `--verilog_macro` that never reached the compiler would have produced the
   same bitstream from the same tree.
2. **A&S `Total registers` 5,033 → 5,054 = +21.**  The retention model is 20
   registers (`core_ad_hold[19:0]`, `system_large.sv` §471-…), and §69.3's
   recorded whole-design figure is **+20 wobbling ±1 in an unrelated MiSTer
   module**.  This is the reproducible count (§74.4a: register counts are
   run-to-run stable, combinational counts are not) and it lands exactly there.
3. **`core_ad_hold` does not appear in `Registers Removed During Synthesis`** —
   0 occurrences anywhere in `.fit.rpt` or `.map.rpt`.  This is §69.3's own
   test, and it is the one that was RED in the `=== 1'bz` era (§59.7.1), when
   Quartus folded the construct and deleted the register for want of fanout.
4. **`configuration` reads RETENTION** — see §6.5, which is a stronger form of
   the same statement because it is read out of the compiler's own transcript.

## §6.5 THE `4bb65d2ab6` FIX — **IT WORKS.  FIRST EXERCISE IN THE CONFIGURATION THAT MATTERS.**

Both receipts read, in full:

> `RETENTION (X1_AD_RETENTION=1) -- DERIVED from
> hdl/output_files_ucore/nec_test_ucore.flow.rpt,
> hdl/output_files_ucore/nec_test_ucore.map.rpt`

and `configuration_detail.retention` is `true`, with

* `command_line`: `quartus_map --verilog_macro=X1_AD_RETENTION=1 nec_test -c nec_test_ucore`
* `cmdline_macros`: `["X1_AD_RETENTION=1"]` (off `.map.rpt`'s `Info: Command:`)
* `qsf_macros`: `["MISTER_DEBUG_NOHDMI=1", "MISTER_DISABLE_ALSA=1", "MISTER_DISABLE_YC=1", "SYNTHESIS=1", "X1_AD_RETENTION=1"]` (off `.flow.rpt`)
* both sources present, so the answer is derived from BOTH and not from a
  default.

**Refuter #3 is not triggered.**  Every one of the four archived retention
receipts — `fdce06392992…` (FLASH #9), `a2d605a47f61…` (FLASH #10),
`7aef327c763f…` (FLASH #11), `6e9460fabfff…` (T9) — still reads
`CONTROL/DEFAULT (no X1_AD_RETENTION)`.  Those labels are the pre-fix defect and
are **wrong on their face**; the fix does not and cannot retro-correct them, and
they should be read as mislabelled wherever they are quoted.

## §6.6 SCORING THE PREDICTION — one registered MISS, reported as a miss

| quantity | predicted | **measured** | |
|---|---|---|---|
| Fmax, `divclk` | 41 MHz (band 39.5–41.8) | **40.96** | **HIT** — 0.04 off the point estimate |
| Δ vs control | −0.02 to −2.13 | **−0.84** (41.80 → 40.96) | **HIT**, mid-band |
| worst setup | +5.0 to +7.5 ns | **+6.836** | **HIT** |
| TNS setup AND hold, every domain | 0.000 | **0.000** | **HIT** |
| ALMs | 12,050 – 12,350 | **12,021** | **MISS — 29 ALMs BELOW the band** |
| A&S registers | ≈ +20 | **+21** (5,033 → 5,054) | **HIT** |
| fitter registers | ≈ 6,098 | **5,935** (control 6,078, i.e. **−143**) | **MISS — 163 below, and the wrong sign** |
| two draws agree | yes | **yes, to the digit** | HIT |
| `.rbf` byte-identical across draws | yes | **yes** | HIT |
| `.rbf` ≠ control's | required | **yes** | HIT |

**THE TWO MISSES ARE BOTH IN THE SAME PLACE AND BOTH ARE MINE, NOT THE
BUILD'S.**  I predicted retention would ADD resources monotonically, from the
`+20 registers` mechanism.  It does add A&S registers (+21, on the nose) but it
does **not** add ALMs or fitter registers — both went DOWN.  That is the
documented behaviour I quoted in my own §3 table and then failed to carry into
the secondary predictions: A&S **combinational** counts are not run-to-run
reproducible (§74.4a), the fitter's register total moves with packing and
duplication decisions rather than with source registers, and the archive already
contained a control→retention pair where ALMs went DOWN by 251
(`591923a3363e…` → `6e9460fabfff…`, 12,466 → 12,215).  I had that datum in front
of me and still predicted a monotone increase.  **Both are misses on RECORDED,
NOT BARRED quantities — no bar moved — but they are misses and are not
restated.**

## §6.7 REFUTER #2 — THE GHOST-FEED CONE IS ABSENT

`c_ready_q` appears **0 times** in `nec_test_ucore.sta.rpt`, and with setup TNS
0.000 on all four domains there are **no failing paths at all**, so there is no
path from `system_large|c_ready_q` into `v30u_eu` to find.  The retention build
matches the control build on this: **zero occurrences.**  R7′ stays closed under
the macro, which is what "the retention is on the OBSERVATION path only" has to
mean if it means anything.

## §6.8 WHAT THIS DOES AND DOES NOT AUTHORISE

It clears the last offline gate before board contact: **T11's bitstream exists,
it is `nec_test_ucore.rbf 74856c80900bb18c…`, it is a genuine
`X1_AD_RETENTION=1` build, and it meets every registered G6 bar with 8.96 MHz
and 6.836 ns of margin.**

It does NOT close the repeatability question.  §74.4 governs: two draws is two
draws.  This same design has drawn 19.42 and 45.91 MHz, and on the pre-rebase
fuzz-v2 tree the retention build drew 14.76 (§5).  Two agreeing draws raise
confidence; they are not a distribution.

**No board was touched.  Nothing was flashed.  No branch was switched.**
The `.qsf` was regenerated after each build and `gen_ucore_qsf --check` is green;
`hdl/` is clean.

## §6.9 A TREE-INTEGRITY OBSERVATION — **THE TREE WAS NOT QUIESCENT**

The brief states "the tree is quiescent and yours".  It was not.  At the start
of this sitting `git status` showed nine untracked paths; at 20:32–20:33, while
draw 1 was compiling, **`sw/fz2_w1.py` (59,619 bytes) and `sw/testdata/fz2/`
(`fz2_population.json`, `fz2_population.sha256`, `fz2_preflight.json`) appeared**
— created by something other than this sitting, which wrote no file under `sw/`
except the receipt history.

**It does not affect these figures.**  `quartus_gate`'s input manifest is 88
files, all under `hdl/`, and it is **byte-identical across both draws**
(`998e129ef7ec3882…`), which is exactly the mechanical check that says the
build's inputs did not move underneath it.  Only `sw/testdata/receipts/
quartus_bitstream.jsonl` and this file were staged, by explicit path.

It is recorded because a second writer in a shared working tree is a
rig-integrity fact, and because the next agent to read a `-dirty` git state in
one of these receipts should know a concurrent writer was present.
