# THE G6 DISTRIBUTION GATE — PRE-REGISTRATION

**Committed BEFORE a single fit of the N=8 sweep was run.**  Tree `a74c741d1c`
(`master`).  **Offline.  Quartus is the instrument.  NO board, NO flash, NO
RTL.**

---

## §1 WHY

`ucore_provenance.md` §74.4 asked for a multi-seed worst-of-N timing gate and
**nobody built one**, so every Fmax figure in this repo from §52 onward is
**one draw of a distribution nobody has characterised**.

The k=0.5 wave (`t1_half2_results_2026-08-13.md` §5) measured how bad that is.
`hdl/` at this HEAD is **byte-identical to `41a60bd42c`** (`git diff --stat
41a60bd42c HEAD -- hdl/` is empty), so every draw below is a draw of **this**
tree, on the same 88-file input manifest `c23e63aa4cf19684…`:

| configuration | draws on record | width |
|---|---|---:|
| CONTROL | 39.79 · 39.79 · 39.79 (CHAIN_MAX) · **42.09** (t1half2) | **2.30 MHz** |
| RETENTION | 43.76 · 43.76 (CHAIN_MAX) · **39.99** (t1half2) | **3.77 MHz** |

**And the configurations' ORDER flipped**: CHAIN_MAX had RETENTION 3.97 MHz
above CONTROL; the t1half2 wave had it 2.10 MHz below.

⚠ **All seven of those draws are `SEED 1`** — `hdl/nec_test.qsf:51` and
`hdl/nec_test_ucore.qsf:62` both assign `SEED 1`, and no historical invocation
overrode it.  So the 2.30 and 3.77 MHz widths are **same-seed, same-manifest**
variation.  The N=8 sweep varies a knob that has **never been varied in this
repo**, and it is registered here that its spread is therefore expected to be
**at least** as wide as the same-seed spread, not obviously wider.

**`timing50_chainmax_results_2026-08-12.md` §7.1's *"three agreeing CONTROL
draws… so the CONTROL loss is a property of the tree, not of a draw"* is the
claim this instrument exists to make unrepeatable.**  It was refuted by a
fourth draw.  *N agreeing draws inside one session measure that session's
determinism.*

---

## §2 THE INSTRUMENT, AS BUILT (committed with this document)

`python3 sw/quartus_gate.py --seeds N [--retention]`

* **ONE `quartus_map`, then N × `quartus_fit --seed=S --recompile=off`**, each
  followed by `quartus_asm`, `quartus_sta` and `sw/sta_truefmax_probe.tcl`.
  Map-once is what makes the N draws a distribution **of one netlist**: a
  re-map per seed would fold Analysis & Synthesis non-determinism (§74.4a — the
  COMBINATIONAL counts are not reproducible run to run) into the same number as
  placement variance, and report two effects as one.
* `--recompile=off` is **pinned explicitly** although it is already the default,
  because the project carries `SMART_RECOMPILE ON` and a sweep in which fit N+1
  started from fit N's placement would report a spread that is an artefact of
  seed ORDER.
* **Per seed**: its own receipt (`sw/testdata/g6dist/<label>/seed<S>_quartus_gate.json`),
  self-labelling **configuration** (DERIVED from the reports, never from the
  flag — the FLASH #18 check, unchanged) **and seed** (asked AND echoed).
  Per-k-class ceilings from the truefmax probe, `.sta.summary`, `.sof`/`.rbf`
  hashes.
* **Per sweep**: `distribution.json` — min / median / max / spread per class,
  the binding-path endpoint pair per seed, and `worst_of_n`.

### 2.1 THE TWO NEW BARS

* **E7 — INPUT-HASH ORDERING.**  The manifest is hashed **before**
  `quartus_map` and **re-hashed after the last stage**; a difference is a
  **RED**, not a warning.  ⚠ **Honest statement of what moved**: the pre-build
  hash was *already* correct at HEAD (`mf = input_manifest()` precedes the
  build).  What did not exist, and now does, is the **post-build re-read**, so
  an input that moved during a ten-to-twenty-minute compile was undetectable
  after the fact.  E7 is added to **both** the single-build path and the sweep,
  and deliberately **not** to `--parse-only`, where there is no interval to
  bracket and the bar would pass vacuously.
* **E8 — THE SEED WAS HONOURED.**  Read back out of `<rev>.fit.rpt` two
  independent ways (`Info: Command:` and the Fitter Settings `Seed` row); a
  disagreement with what was asked is a RED.  This is the `want_raw` /
  `X1_AD_RETENTION` lesson applied to `--seed`: **a sweep whose flag was
  accepted and ignored reports a spread of 0.00 MHz, which reads as a
  reassuring result.**

### 2.2 THE QUOTING RULE (registered in `standing_gates.md` §A with this wave)

> A distribution figure is **`worst-of-N@seeds{...}`** with N and the seed set
> named, and **the WORST draw is the quotable one**.  A single fit is
> **`draw@seed<S>`** and is **not promotion evidence**.
> **G6 PASS for a PROMOTION requires N ≥ 5.**  N = 2 remains acceptable for an
> intermediate wave measurement **with the caveat printed**.

---

## §3 THE REGISTERED PREDICTIONS — N = 8 per configuration, seeds 1..8

Scored as registered.  A MISS is reported as a MISS.

| # | prediction | falsifier |
|---|---|---|
| **P-1** | **E8 PASS on 16/16 fits** — every fit echoes the seed it was given, on both readings | any fit whose `fit.rpt` echoes a seed ≠ the one asked |
| **P-2** | **CONTROL min-max width ∈ [1.5, 6.0] MHz** | a width outside the interval |
| **P-3** | **RETENTION min-max width ∈ [2.0, 8.0] MHz** | a width outside the interval |
| **P-4** | **THE BINDING CLASS DOES NOT FLIP**: the `k = 1` DEFAULT class binds on **8/8 CONTROL and 8/8 RETENTION**.  The k=0.5 wave puts the ENABLE arc 40+ MHz clear of binding, and *a draw-to-draw swing cannot turn a `k = 0.5` arc into a `k = 1` arc* | any draw whose true ceiling is set by a class other than DEFAULT |
| **P-5** | **THE BINDING CONE *DOES* FLIP within the class**: **≥ 2 distinct `(from, to)` endpoint pairs** over the 8 CONTROL draws | exactly 1 distinct pair over 8 draws |
| **P-6** | **16/16 draws are a G6 PASS** (E1-E5: Fmax ≥ 32, worst setup > 0, TNS 0.000 setup AND hold) | any draw RED |
| **P-7** | **E7 PASS on both sweeps** — 0 inputs move during ~1.5 h of compiling | any input moved |
| **P-8** | **THE TWO CONFIGURATIONS' BANDS OVERLAP**: `[min, max]` CONTROL ∩ `[min, max]` RETENTION ≠ ∅.  If true, **no draw-pair may be quoted as a control-vs-retention delta** — which is the standing "recorded, not explained" sign instability (FLASH #13 +0.46, #14 +1.50, #15 +2.24, #16 +0.12, #17 +0.71, #18 −1.31) reported as **one distribution seen twice** | disjoint intervals |
| **P-9** | **`upc_opc → …|ad_in_q[*]` is the binding cone on ≥ 6 of 8 CONTROL draws** — i.e. the AD publication cone §8.2 names as the #1 lever is the lever on most draws, not just on the one that was measured | fewer than 6 |

### 3.1 WHAT IS *NOT* PREDICTED, AND IS RECORDED EITHER WAY

* Whether any two seeds give a **byte-identical `.rbf`**.  FLASH #14 recorded
  two byte-identical draws at the same seed, so identity is a legitimate
  outcome and cannot be gated on — **but if all 8 were identical, E8 would
  still pass and the sweep would be measuring nothing**, so the `.rbf` hashes
  are recorded per seed and the count of distinct ones is reported as a finding
  either way.
* The absolute worst-of-8 numbers.  Registering a point prediction for those
  would be registering the answer.

---

## §4 DISCIPLINE

* Wall clock is real: 2 maps + 16 fits + 16 asm + 32 STA runs.  **If N is
  reduced, the CLAIM is reduced with it and the reduction is stated** — a
  worst-of-5 may not be quoted as a worst-of-8.
* No RTL is touched.  Controls re-run beside the sweeps: `test_artifact`
  45/45, `test_quartus_gate`, `gen_ucore_qsf --check`, `r7_lint`, `ss_lint`,
  `check_core --opcodes 8F.0`.
* Every figure below is quoted as `worst-of-N@seeds{...}` or not quoted.
