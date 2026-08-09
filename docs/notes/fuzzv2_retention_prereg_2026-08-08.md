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

## §5 A CALIBRATION POINT THE BRIEF DID NOT CARRY

The most recent retention build in the archive, **`6e9460fabfff…` "T9 fuzz-v2
RETENTION"**, is **RED**: 14.76 MHz, worst setup **−36.484 ns**, setup TNS
**−16,590.195** on `divclk`.  It was taken on `989a33d28e`, the fuzz-v2 branch
*before* the rebase onto the relanding, and its **CONTROL** draws on the same
tree are equally RED (15.14 MHz, −34.806 ns, receipts `03efc09222a3…` /
`591923a3363e…`).  So that RED is the *tree's*, not the macro's, and it is the
condition the rebase onto `ucore-relanding` was meant to leave behind — which
`c5f29a405b`'s 41.80 MHz control says it did.  It is recorded here because a
prediction should name the nearest contrary datum before the run, not after.
