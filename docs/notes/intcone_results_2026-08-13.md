# THE `c_int_q` WAVE — RESULTS, AND THE 50 MHz CAMPAIGN'S CLOSING STATEMENT

Anatomy first (`intcone_anatomy_2026-08-13.md`), committed **before any
design**.  Branch `master`, HEAD `3ce86eb4b5` verified on entry, isolated
worktree.  **OFFLINE ONLY.  NO BOARD, NO FLASH.  No Codex consulted, no nested
task spawned.**

The floor this wave is scored against was registered **in the wave brief,
before the anatomy was taken**, and is reported here in the form it was
registered in: *"floor worst-of-5 ≥ +1.5 MHz on at least one config,
pin-sensitive ladder byte-identical, revert rule"*.  **No pre-registration
document is written after the fact to stand in for it.**

---

## §0 HEADLINE

| | |
|---|---|
| **PART 1 — `c_int_q`** | **BOOKED WITH THE MEASURED SHAPE.  NO RTL WAS CHANGED.**  The registered floor is **unreachable by arithmetic, not by difficulty**: on the worst draw of *each* configuration the design is bound by the OBSERVATION class, and `c_int_q` is behind it.  Measured directly — with `c_int_q` excluded as a launch register, CONTROL seed 1's worst path is **+7.276 ns**, the draw's own binding path. **A perfect fix is +0.00 MHz on `worst-of-5`.** |
| **the anatomy** | prefix **3.154 ns / 6 cells**, tail **19.916 / 21**; the tail is **86.3 %** of the data path.  Phase 2's *"this cone is TAIL-limited"* **reproduces on a tree two structural landings later**, and the prefix has not moved by a tenth of a nanosecond. |
| **what DID change** | **`CHAIN_MAX` emptied the EU end**: the `row_posted_n~1…~9` cascade is gone from all 60 paths and the EU contributes **2 cells**.  All of it, and more, moved into the BIU: **20 of the 27 levels are inside one procedural `always_comb`.** |
| **the R7′ question, answered NEGATIVELY** | `flush_int_live`'s consumers are `rd_pending[0]`/`[1]`/`row_posted`, and the EU-side cone is **already** a `D`-pin mux under register-only predicates.  **R7′'s move has been made at that end; there is nothing left to take there.** |
| **one mechanism found, NAMED, NOT TAKEN** | the pin rides the **M7 prefetch-eligibility occupancy adder** — `occ`'s `cmt_valid && cmt_fetch` term is read *after* `kill_l` clears it — **8 cells and 5.594 ns, 24.2 % of the cone**.  Registered with its predicted benefit (**+0.00 MHz**, by the same arithmetic) and therefore not built. |
| **PART 2 — PAIRED REPORTING** | **ADOPTED AND REGISTERED** (`standing_gates.md` §A).  G6's `--seeds N` output is now a PAIR: whole-design worst-of-N (**the promotion gate, unchanged**) and core-domain worst-of-N (**not a gate; no bar reads it**), each with its binding cone and `k`.  Falsifier `test_quartus_gate.py` **240/240** (was 200/200). |
| **and an ERRATUM IT FOUND BEFORE ITS FIRST USE** | the `k=4.0` class row is contaminated by the `t1_half2~DUPLICATE` leak **in the UNSAFE direction** (98.30 where a clean draw reads 60.99), which **refutes** `timing50_distribution_2026-08-13.md` §6's *"never wrong in the unsafe direction"* for that row.  The core-domain figure is therefore declared an **UPPER BOUND** and flags itself per draw. |
| **PART 3 — the final band** | **CONTROL whole-design `worst-of-5` 41.71 / core-domain 60.67; RETENTION 43.50 / 59.52.**  Both sweeps PASS, TNS 0.000 on all ten draws, and **all ten draws reproduce L1 to the digit** — the fifth confirmation that the fit is deterministic given netlist and seed.  **The core-domain half clears 50 MHz on both configurations; the whole-design half does not, and is short by 8.29 / 6.50 MHz.** |

---

## §1 PART 1 — THE VERDICT: **BOOKED**, AND THE BOOKING IS ARITHMETIC

### 1.1 THE FLOOR, SCORED AS REGISTERED

| id | registered (wave brief, before the anatomy) | measured | |
|---|---|---|---|
| **P-1** | `worst-of-5` improves **≥ +1.5 MHz on at least one configuration** | **+0.00 MHz is the CEILING of what this cone can give on either**, measured (§1.2) | **UNREACHABLE — the wave BOOKS rather than builds** |
| **P-2** | the pin-sensitive ladder byte-identical | **VACUOUSLY MET: no RTL was changed**, so nothing can have moved.  It is reported as vacuous, not as a pass. | — |
| **P-3** | the revert rule | **not exercised**: nothing was landed to revert | — |

**A floor that cannot be met is a result**, and it is the result this wave was
sent to get: the brief's own instruction was *"if the anatomy says the cone
cannot shorten without touching recognition or without a fitted special case:
BOOK it with the measured shape — that is this lever spent, honestly."*  What
the anatomy actually says is stronger and simpler than that conditional: the
cone **can** shorten, by a named mechanism, and **shortening it is worth
nothing on the registered figure.**

### 1.2 WHAT A PERFECT FIX IS WORTH — MEASURED PER DRAW, NOT ARGUED

`sta_intcone_probe.tcl` §D removes `c_int_q` from the launch set and asks for
the design's worst path.  That is exactly *"what would a perfect fix leave
behind"*, and it needs no model.

| CONTROL draw | design Fmax / worst setup | `c_int_q` own-Fmax | **§D: worst path with `c_int_q` excluded** | benefit of a PERFECT fix |
|---|---:|---:|---|---:|
| **seed 1 — THE `worst-of-5` DRAW** | **41.71 / +7.276** | 42.92 | **+7.276**, `opc_from_modrm → ad_in_q[14]` — **the same path** | **+0.000 ns** |
| seed 4 | 42.50 / +7.722 | **42.50 — it BINDS** | +8.538, `modrm_reg[0] → ad_in_q[15]` ⁽¹⁾ | +0.816 ns → 44.03 MHz |
| seed 5 | 44.36 / +8.708 | 47.34 | **+8.708**, `ucdecode M10K → ad_in_q[0]` — **the same path** | **+0.000 ns** |

⁽¹⁾ **read past two `sld_jtag_hub` rows at +8.272 / +8.498.**  They are
cross-domain (`capture_buf` → JTAG hub) and Quartus computes Fmax only for
paths whose source and destination share a clock, so they are **not a `divclk`
ceiling** — `sta_truefmax_probe.tcl` excludes exactly this class for exactly
this reason and says so in its own comments.  `sta_intcone_probe.tcl` does
**not** filter by clock domain; that is a gap in the probe, it is named here,
and the rows are read past rather than deleted.

> **`worst-of-N` IS THE MINIMUM OVER THE DRAWS.  The CONTROL minimum is seed 1,
> seed 1 is bound by the observation class, and a cone 0.673 ns behind the
> binding cone on the draw that SETS the figure cannot move the figure.**

**AND RETENTION IS MEASURED THE SAME WAY, NOT QUOTED.**  After the wave-end
sweeps the same probe was run on the RETENTION worst draw (seed 2) on its own
map (`intcone_anatomy_2026-08-13.md` §5.4):

| RETENTION seed 2 — **the `worst-of-5` draw** | |
|---|---|
| worst setup | **+8.261**, the sweep's own figure to the digit |
| `c_int_q` own-Fmax | **47.42 MHz**, `c_int_q → row_posted`, **60 of 60** paths latch there |
| **§D: worst path with `c_int_q` excluded** | **+8.261**, `ucdecode M10K → ad_in_q[11]` — **the same path** |
| **benefit of a PERFECT fix** | **+0.000 ns** |

> **BOTH CONFIGURATIONS, EACH ON ITS OWN WORST DRAW, WITH THE SAME INSTRUMENT:
> a perfect fix of `c_int_q` is worth +0.000 ns.**  RETENTION's 47.42 also
> reproduces L1's committed `rung 1a` for seed 2 to the digit, and this wave's
> retention sweep reports the same 47.42 in its own `RUNG 1a` row — three
> independent readings of one number.

### 1.3 THE R7′ QUESTION, AND ITS ANSWER IS NEGATIVE

The brief asked: *which register `D`-pins does `flush_int_live` ultimately
gate, and what is the analogous move to the one §73 made for `eu_rd_edge`?*

**Answered, and the answer is that the move is already made.**  Over the worst
200 paths from the pin the endpoints are **`rd_pending[0]` 93 · `rd_pending[1]`
89 · `row_posted` 18**, and nothing else.  In the EU the carrier's whole cone is
`v30u_eu_step.svh`'s `S_PRERD` arm, where **every branch sets `stop`** — so it
selects a `D`-pin value under register-only predicates and does not seed the
twelve-position chain.  `v30u_eu.sv:1754-1756` states this as the R7′ landing's
own by-elimination argument, and the netlist agrees: **two combinational
cells, 3.203 ns.**

**There is no `eu_rd_edge`-shaped move left at the consumer end.**  The depth
is on the producer side, inside `v30u_biu`.

### 1.4 THE ONE MECHANISM THIS WAVE FOUND — NAMED, COSTED, AND NOT TAKEN

`v30u_biu.sv:1895-1899`, section (c), the M7 prefetch-eligibility sample:

```systemverilog
if (ts == TS_T3) begin
    occ = {1'b0, q_cnt}
        + (cur_fetch ? {3'b0, cur_pn} : 5'd0)
        + ((cmt_valid && cmt_fetch) ? {3'b0, cmt_pn} : 5'd0)   // <- the pin
        + (infl_now ? {3'b0, infl_n_now} : 5'd0);
    pf_arm = (occ <= 5'd4) && !halted;
end
```

`cmt_valid` here is the value **after** `kill_l = ann_kill` cleared it
(`:1644`, `:1677`), so **the live INT pin arrives at the input of a five-bit
carry chain and rides all of it**, then `pf_arm`, then the eval.  Measured
cost: **8 cells and 5.594 ns — 24.2 % of the cone** (§3 of the anatomy).

**The candidate design, in the R7′ idiom**: compute the sum twice from
REGISTERS ONLY — with and without the committed fetch's `cmt_pn` — and select
between the two `pf_arm` answers with `kill_l` **at the end**, so the pin
becomes a mux SELECT after a register-only cone instead of an addend at the
head of one.  No behaviour change (it is a Shannon expansion of a term that is
already exactly this function), no new flop, ~8 cells out of the pin's cone.

**IT IS NOT TAKEN, AND THE REASON IS THE MEASUREMENT, NOT THE RISK.**

1. **Its benefit on the registered figure is +0.00 MHz** (§1.2) — the same
   arithmetic that disposes of the whole lever.
2. **Phase 2 built the analogous transform and measured the fitter reclaiming
   98 % of it** (a 1.938 ns prefix saving became a 0.039 ns total saving, for
   +106 ALMs).  This one is a duplication too.
3. **`occ`'s `cmt_valid` term is silicon-correct as written**: a withdrawn
   fetch's bytes must not be counted by the arbiter that decides whether to
   fetch more.  Nothing here is a defect to fix; it is a cone to shorten.

**RE-OPEN CONDITION, and it is a single sentence**: *re-open `c_int_q` when the
observation class no longer binds the worst draw of a configuration* — i.e.
after the AD publication cone's remaining **+0.79 (CTL) / +1.71 (RET)** is
taken, at which point `adcone_l1_results_2026-08-13.md` §3.2 says `c_int_q`
binds on **every** draw.  Until then any work here is measured against a wall
that is not it.

### 1.5 THE SIMPLICITY PRINCIPLE, APPLIED TO THE THING NOT BUILT

> *SIMPLICITY: this is 80's era hardware — nothing on the die is wasted.
> Complex or confusing observed behavior is likely simple systems interacting
> in ways not yet understood. A large fitted table, a many-cased rule, or a
> per-opcode special case is a signal of misunderstanding, not a deliverable.*

The alternative to §1.4's mechanism-level change would have been to *prove the
pin cannot change `slot_busy` on this clock and tie it off*.  That proof exists
only as a case list — `ann_kill` requires `r_cmt_fetch`, the slot-free arm
requires `!cmt_fetch`, so the pin reaches `slot_busy` only through the eval's
own same-clock re-grant, and only through `vector_follow_preview` — **and a
case list is exactly what the principle says is a signal of misunderstanding
rather than a deliverable.**  It is written down here so that the next agent
does not have to re-derive it before declining it.

---

## §2 PART 2 — THE PAIRED-REPORTING CONTRACT

Registered in `standing_gates.md` §A; implemented in `sw/quartus_gate.py`
(`core_domain_fmax()`, `paired_figures()`); falsified by
`sw/test_quartus_gate.py` **240/240** (Q16 is its own section, 40 checks).

> **G6's registered output for a `--seeds N` run is a PAIR, both halves
> worst-of-N over the SAME N draws of the SAME map:**
>
> * **`whole-design worst-of-N@seeds{…}`** — Quartus's own Fmax.  **THE
>   PROMOTION GATE, UNCHANGED IN ROLE**; E3/E4/E5 score this and nothing else;
>   it is the number the board must satisfy.
> * **`core-domain worst-of-N@seeds{…}`** — the worst path with **both**
>   endpoints inside `v30u_eu`/`v30u_biu`; what a downstream integration
>   inherits.  **NOT A GATE.  No bar reads it**, and Q16 asserts that per bar
>   by name.
>
> **Each is quoted with its BINDING CONE and its `k`; neither stands in for the
> other.**

**Core-domain is three classes, not one.**  `nec_test.sdc` collects `$v30u_ce`
as (every `v30u_eu` + `v30u_biu` register) MINUS `t1_half2`, and `t1_half2` is
itself a `v30u_biu` register — so `k=4.0`, `k=1.5` and `k=2.5` are all
core-internal on both ends, while `DEFAULT` is the whole design and `k=0.5` is
`(not $v30u_ce) → t1_half2`, whose launch side is outside the core by
construction.  The figure is the **minimum over the three**, binding class
named.  **Absence is not data**: a missing or ceiling-less class yields **no
figure** and a list of what was missing, never a minimum over the survivors.

⚠ **IT IS AN UPPER BOUND, AND THE FIRST ARTIFACT IT WAS POINTED AT PROVED IT.**
On CONTROL seed 1 the `k=4.0 $v30u_ce → $v30u_ce` row returned
`to: …|t1_half2~DUPLICATE`, `k = 1.5000`, **98.30 MHz** — an arc into the very
register the class is defined by excluding — where CONTROL seed 4, which
carries no duplicate, reads a clean `k = 4.0000`, **60.99 MHz**.  **The
contaminated reading is the HIGHER one**, which **refutes**
`timing50_distribution_2026-08-13.md` §6's *"a missed duplicate can only make
those queries conservative, never wrong in the unsafe direction"* for the
`k=4.0` row — that row's collection is built by **excluding an exact name on
both ends**.  The mechanism by which the duplicate reaches collections built
from `t1_half2` by exact name is **not established** and is booked, not
guessed.  Every draw now carries `off_class`, `k_measured` and
`upper_bound: True`, and the sweep prints them.

---

## §3 PART 3 — THE WAVE-END MEASUREMENT AND THE CAMPAIGN'S CLOSING STATEMENT

One `--seeds 5` sweep per configuration on the **final tree** — which, because
this wave landed no RTL, is **byte-identical in `hdl/` to L1's**: both sweeps
report the input manifest **`d47c1d003d64c4c5…`**, the same 88 files L1's
sweeps were taken on.  So these are not only this wave's figures; they are a
**second, independent draw of L1's own numbers at the same seeds**, and that
makes them a determinism control as well as a measurement.

### 3.1 THE PAIRED FIGURES, BOTH CONFIGURATIONS

**CONTROL** — record `ad7dc5db6e6a6002…`, `sw/testdata/g6dist/intcone-control-n5/`

| seed | Fmax | worst setup | ALMs | **core-domain** | class | k | binding cone (whole design) |
|---|---:|---:|---:|---:|---|---:|---|
| **1** | **41.71** | **+7.276** | 10,154 | ⚠ 98.28 | k=1.5 | 1.5 | `opc_from_modrm → ad_in_q[14]` |
| 2 | 42.48 | +7.710 | 10,105 | ⚠ 104.11 | k=4.0 | ⚠ 1.5 | `ucdecode M10K → ad_in_q[15]` |
| **3** | 42.57 | +7.758 | 10,116 | **60.67** | k=4.0 | 4.0 | `ucdecode M10K → ad_in_q[17]` |
| 4 | 42.50 | +7.722 | 10,115 | 60.99 | k=4.0 | 4.0 | **`c_int_q → row_posted`** |
| 5 | 44.36 | +8.708 | 10,085 | 60.84 | k=4.0 | 4.0 | `ucdecode M10K → ad_in_q[0]` |

> **WHOLE-DESIGN `worst-of-5@seeds{1,2,3,4,5}` = 41.71 MHz** (seed 1, **k = 1.0**),
> bound by `v30u_eu|opc_from_modrm → nec_bus|ad_in_q[14]` · median 42.50 ·
> spread **2.65**
> **CORE-DOMAIN `worst-of-5@seeds{1,2,3,4,5}` = 60.67 MHz** (seed 3, **k = 4.0**),
> bound by `ucdecode M10K → v30u_eu|wb_kind[0]` · per class **k=4.0 60.67 ·
> k=1.5 94.80 · k=2.5 228.98**

**RETENTION** — record `c487a9ae7bbd4f3c…`, `…/intcone-retention-n5/`

| seed | Fmax | worst setup | ALMs | **core-domain** | class | k | binding cone (whole design) |
|---|---:|---:|---:|---:|---|---:|---|
| 1 | 45.21 | +8.988 | 10,194 | 62.91 | k=4.0 | 4.0 | ⚠ `cfg_clk_div[4] → t1_half2` (k=0.5 artifact) |
| **2** | **43.50** | **+8.261** | 10,145 | 60.44 | k=4.0 | 4.0 | `ucdecode M10K → ad_in_q[11]` |
| 3 | 44.33 | +6.758 | 10,178 | 59.55 | k=4.0 | 4.0 | ⚠ `div_cnt[1] → t1_half2` (k=0.5 artifact) |
| **4** | 43.84 | +8.442 | 10,134 | **59.52** | k=4.0 | 4.0 | `opc_from_modrm → ad_in_q[18]` |
| 5 | 44.80 | +8.929 | 10,166 | ⚠ 103.85 | k=1.5 | 1.5 | `ucdecode M10K → ad_in_q[3]` |

> **WHOLE-DESIGN `worst-of-5@seeds{1,2,3,4,5}` = 43.50 MHz** (seed 2, **k = 1.0**),
> bound by `ucdecode M10K → nec_bus|ad_in_q[11]` · median 44.33 · spread **1.71**
> **CORE-DOMAIN `worst-of-5@seeds{1,2,3,4,5}` = 59.52 MHz** (seed 4, **k = 4.0**),
> bound by `ucdecode M10K → v30u_eu|Mux73~0` · per class **k=4.0 59.52 ·
> k=1.5 103.85 · k=2.5 225.57**

**Both sweeps `verdict PASS`** on E7-E10, **TNS 0.000 setup AND hold on every
domain of all ten draws**, 0 errors / 0 latches / 0 `lpm_divide`, ALMs
**24 %** throughout, input manifest **`d47c1d003d64c4c5…`** on both — the same
88 files L1's sweeps were taken on.  Wall clock 2,326 s + 1,909 s.

⚠ **THE BANDS OVERLAP** ([41.71, 44.36] vs [43.50, 45.21]), so **no
control-vs-retention delta may be computed** from them, per the distribution
gate's own rule.

⚠ **THREE OF THE TEN CORE-DOMAIN ROWS ARE OFF-CLASS** (CONTROL seeds 1 and 2,
RETENTION seed 5 — flagged in the record and printed by the sweep).  On both
configurations the contamination went **upward**, so it did **not** set either
minimum: both reported core-domain figures come from clean `k = 4.0` rows.
That is a fact about these ten draws, not a property of the instrument.

⚠ **AND THE TWO KNOWN `sta_truefmax_probe.tcl` DEFECTS BOTH REPRODUCED**, at
exactly the rates L1 recorded: the `DEFAULT`-row-by-slack artifact on **2 of 5
RETENTION draws** (seeds 1 and 3 name a `k = 0.5` enable arc), and the
`~DUPLICATE` leak.  Neither touches the two quotable figures, whose own draws
(CONTROL seed 1, RETENTION seed 2) are clean `k = 1.0` reads.

### 3.1b THE DETERMINISM CONTROL — **TEN OF TEN DRAWS REPRODUCE L1 TO THE DIGIT**

This wave changed no RTL, so every draw above should equal L1's at the same
seed.  **All ten do** — Fmax, worst setup and ALM count, on independently
produced maps:

| | CONTROL | RETENTION |
|---|---|---|
| L1 (`adcone_l1_results` §2.1) | 41.71 · 42.48 · 42.57 · 42.50 · 44.36 | 45.21 · 43.50 · 44.33 · 43.84 · 44.80 |
| **here** | **41.71 · 42.48 · 42.57 · 42.50 · 44.36** | **45.21 · 43.50 · 44.33 · 43.84 · 44.80** |
| spread | 2.65 = 2.65 | 1.71 = 1.71 |

**That is the fifth independent confirmation of the distribution gate's §7
determinism finding** (the fit is deterministic given netlist and seed), and it
is what makes the paired figures above a property of the tree rather than of
this sitting.

#### 3.1a THE SAME PAIR, READ RETROACTIVELY OFF L1'S OWN RECEIPTS — A CONTROL THAT COST NOTHING

L1's per-seed receipts already carry `truefmax_full`, so `core_domain_fmax()`
can be applied to them **without rebuilding anything**.  That gives an
independent draw of the core-domain half on the same tree, taken by a different
sitting, and it is quoted here as a control on §3.1 rather than as a second
measurement:

| | seed 1 | 2 | 3 | 4 | 5 | **worst-of-5** |
|---|---:|---:|---:|---:|---:|---:|
| **CONTROL** whole-design | **41.71** | 42.48 | 42.57 | 42.50 | 44.36 | **41.71** (seed 1) |
| **CONTROL** core-domain | ⚠ 98.28 | ⚠ 104.11 | **60.67** | 60.99 | 60.84 | **60.67** (seed 3) |
| **RETENTION** whole-design | 45.21 | **43.50** | 44.33 | 43.84 | 44.80 | **43.50** (seed 2) |
| **RETENTION** core-domain | 62.91 | 60.44 | 59.55 | **59.52** | ⚠ 103.85 | **59.52** (seed 4) |

⚠ = an **off-class** row (§2): the `k=4.0` query returned a `k=1.5` path into
`t1_half2~DUPLICATE`.  **Three of the ten draws are contaminated, and on both
configurations the contamination went UPWARD, so it did not set either
minimum** — the reported worst-of-5 comes from a clean row in each case.  That
is a fact about these ten draws, **not a property of the instrument**, and it
is exactly why `off_class` is printed rather than remembered.

### 3.2 THE CENSUS — WHAT BINDS, AND WHAT IS BEHIND IT

Read off each sweep's own per-seed `truefmax` artifacts.

| | CONTROL (worst draw, seed 1) | RETENTION (worst draw, seed 2) |
|---|---|---|
| **binds** (k = 1.0) | **+7.276** `opc_from_modrm → ad_in_q[14]` | **+8.261** `ucdecode M10K → ad_in_q[11]` |
| **RUNG 1a** — the worst k=1 survivor once the observation registers are excluded | **+7.949 → 42.92 MHz**, `c_int_q~DUP → rd_pending[0]` | **+10.163 → 47.42 MHz**, `c_int_q → row_posted` |
| how far behind the binding cone | **0.673 ns / +1.21 MHz** | **1.902 ns / +3.92 MHz** |
| **CORE→CORE (k = 4)** | 60.67 MHz (worst-of-5) | 59.52 MHz (worst-of-5) |

**`c_int_q` is the first wall behind the observation class on BOTH
configurations' worst draws, and it is BEHIND it on both** — which is §1.2's
verdict, re-measured on this wave's own sweeps.  RETENTION's 47.42 reproduces
L1's committed `rung 1a` for seed 2 **to the digit**, a fourth agreement.

⚠ **THE LADDER CANNOT NAME THE THIRD WALL, AND THAT IS AN INSTRUMENT LIMIT.**
`RUNG 2` (*not latching in an observation register AND not launching from
`c_int_q`*) reads **68.75 MHz at k = 0.5** on RETENTION seed 2 and **42.92 at
k = 1.0** on CONTROL seed 1 — the first is the `div_cnt → t1_half2` enable arc
returned because the rung query ranks by SLACK rather than `slack/k`, and the
second is the `~DUPLICATE` leak returning the `c_int_q` path the rung was
supposed to exclude.  **Neither is a third wall.**  So: *what is behind the two
rig-crossing cones is currently UNMEASURED*, and repairing the rungs is the
first thing a 50 MHz continuation would have to do.

### 3.3 WHAT 50 MHz MEANS UNDER PAIRED REPORTING

**Ask the question the pairing was adopted to make askable, and answer it with
the measurement rather than with a hope.**

| | CONTROL | RETENTION | ≥ 50 ? |
|---|---:|---:|---|
| **whole-design** `worst-of-5` | **41.71** | **43.50** | **NO** — short by **8.29** and **6.50 MHz** |
| **core-domain** `worst-of-5` (⚠ upper bound) | **60.67** | **59.52** | **YES**, by **+10.67** and **+9.52 MHz** |

> **THE HONEST SENTENCE, IN THE FORM §8.3 ASKED FOR IT:**
> *the ucore's own logic closes at **60.67 MHz (CONTROL) / 59.52 (RETENTION)**,
> bound by the `k = 4` CE-domain cone `ucdecode M10K → v30u_eu|{wb_kind, Mux73}`;
> the `nec_test` RIG closes at **41.71 / 43.50**, bound by the AD publication
> cone into `nec_bus|ad_in_q`.*

⚠ **AND THE CORE-DOMAIN HALF IS AN UPPER BOUND** (§2), so the correct reading
is *"the core's own logic is not what stops this design reaching 50, and it has
about 10 MHz of measured headroom above it — subject to a class query that can
return an off-class path."*  It is **not** *"the core closes at 60 MHz"* said
flatly.

**WHAT THE WHOLE-DESIGN NUMBER WOULD NEED, in nanoseconds rather than wishes:**

* CONTROL 41.71 → 50.00 is `T_min` **23.974 → 20.000 ns = 3.974 ns** off the
  binding path; RETENTION 43.50 → 50.00 is **22.989 → 20.000 = 2.989 ns**.
* **What is measured as available**: closing everything the observation class
  still contains is worth **+0.79 (CTL) / +1.71 (RET)** — landing on
  **42.50 / 45.21** — and then `c_int_q` binds on every draw
  (`adcone_l1_results_2026-08-13.md` §3.2).
* **Closing `c_int_q` PERFECTLY after that** would land on whatever is behind
  it — **and §3.2 says the ladder cannot currently name that number.**
* So **50 MHz is short by roughly 3.2 ns (CTL) / 1.3 ns (RET) with BOTH
  rig-crossing cones perfectly closed**, and the remainder would have to come
  from a class nobody has measured yet.

**50 MHz IS NOT REACHABLE BY ANY LEVER CURRENTLY ON THE TABLE, AND THAT IS NOW
ARITHMETIC RATHER THAN OPINION.**

### 3.4 THE CLOSING STATEMENT OF THE 50 MHz CAMPAIGN

#### (a) THE BAND, STAGE BY STAGE — every figure with its N, and none of them comparable to the next without saying so

| stage | tree | CONTROL | RETENTION | N | what moved |
|---|---|---:|---:|---:|---|
| Phase 1 baseline | `1e554257b6` | 45.54 | 45.57 | 2 | **includes E-1** |
| Phase 1's correctness fix | `f17102066f` | −0.07 | — | 2 | the CE multicycle **split by enable phase** — it was optimistic by two full periods on the one `ce_half`-gated flop |
| amendment **A-1** | built | **−2.41** | — | 2 | **BUILT, MEASURED, WITHDRAWN** |
| **E-1 DELETED** | `a1c63e78e4` | **41.18** | **42.28** | 2 | −4.36 / −3.29.  A constraint whose premise could not be derived from the ce/ce_half contract |
| **P2-A** (the INT prefix) | `c137e8c105` | +0.25 | −0.09 | 2 | **REVERTED by its own pre-registered rule** |
| **`CHAIN_MAX` 12 → 7** | `41a60bd42c` | 39.79 | 43.76 | 2 | ALMs **12,271 → 10,358 (−15.6 %)** |
| **THE DISTRIBUTION GATE** | `a74c741d1c` | **38.97** | **37.73** | **8** | *the first honest band* — and **below every single draw ever registered for that tree** |
| the `t1_half2` half-arc | — | — | — | — | **REFUTED: there is no wall** (90.91 / 83.43, fourth-ranked).  **No RTL changed.** |
| **L1** | `9bf70f2eec` | **41.71** | **43.50** | **5** | **+2.74 / +3.76** at the same seeds; ALMs → **~10,100 (24 %)** |
| **this wave** | `3ce86eb4b5` | **41.71** | **43.50** | **5** | **no RTL.**  Paired reporting adopted; `c_int_q` booked |

⚠ **A worst-of-2 and a worst-of-8 are not the same quantity**, and the rows
above are labelled with their N precisely so that no reader subtracts across
them.  The only like-for-like deltas in the table are the ones taken at the
same N **and the same seed set**: A-1's −2.41, E-1's −4.36 / −3.29, P2-A's
+0.25 / −0.09, and L1's **+2.74 / +3.76**.

#### (b) WHAT THE CAMPAIGN ACHIEVED

1. **Two constraint CORRECTIONS landed, and both made the tree honestly
   slower.**  E-1's deletion cost 4.36 / 3.29 MHz and the enable-phase split
   cost 0.07, and both were kept.  A campaign whose headline number went *down*
   twice on purpose is the discipline working, not failing.
2. **One RTL landing that paid: L1**, +2.74 / +3.76 MHz on a worst-of-5 basis,
   twelve lines, no SDC edit, pin identity a construction rather than an
   experiment (306 seeds / 1,243,278 replayed rows byte-identical).
3. **One RTL landing that paid in AREA: `CHAIN_MAX`**, −15.6 % ALMs.  Together
   with L1 the design went from **12,271 ALMs (29 %) to ~10,100 (24 %)** — **−18 %**.
4. **Three things were built, measured and REFUSED**: amendment A-1
   (−2.41 MHz), P2-A (the INT prefix, +0.25 / −0.09 against a 1.5 bar), and the
   `t1_half2` arc (refuted outright — there was no wall to fix).  **Each was
   disposed of by a rule written before its number was known.**
5. **THE INSTRUMENTS ARE THE LARGEST DELIVERABLE, and they outlast the
   number.**  `quartus_gate.py --seeds N` (worst-of-N, E7-E10);
   `sta_truefmax_probe.tcl` (rank by `slack/k`, five classes);
   `sta_fmax_attrib.tcl` (own-Fmax); `sta_halfarc_probe.tcl` (`d(slack)/dT`
   measured, not assumed); `sta_adcone_anatomy.tcl` and
   `sta_intcone_anatomy.tcl` (population anatomies); `sta_intcone_probe.tcl`
   (per-launch ceilings); `ucrom_mif_check.py` (the microcode's
   SYNTHESIS-side F44 check, which never existed); `chain_lfsr_gate`;
   `adcone_g6_table.py`, `adcone_replay_diff.py`, `adcone_iepinfall_diff.py`;
   and this wave's **paired reporting**.
6. **And it found what it was not looking for**: that a single Quartus draw is
   not a property of a tree (three agreeing draws refuted), that map variance
   sits *above* seed variance and is unmeasured, that `sta_truefmax_probe.tcl`
   leaks `~DUPLICATE` in two different ways — one of them, found here, in the
   **unsafe** direction — and that a committed directed-cell table had been
   stale for six landings.

#### (c) WHAT IT DID NOT ACHIEVE, STATED PLAINLY

**50 MHz was not reached on the whole-design number, and it is not reachable by
any lever currently on the table.**  Not *"not yet"*: the two cones that bind
are measured, the value of closing them is measured, and the sum is short.

#### (d) THE ONE-SENTENCE CLOSING STATEMENT

> **The ucore's own logic closes comfortably above 50 MHz; the `nec_test` RIG
> does not, and both cones that bind it have one endpoint in the rig.  The
> campaign's honest deliverable is that this is now MEASURED — with an
> instrument that reports a distribution rather than a draw, a pair rather than
> a single number, and a ceiling rather than a hope.**

---

## §4 THE FLASH #21 DEBT

**THE BOARD CARRIES FLASH #20** — `nec_test_ucore.sof` **`26d6e79166183a21…`**,
built from **`3118a2db46`** WITH `X1_AD_RETENTION=1`, `flash_log.jsonl`
**23 entries** (`fz2_flash20_results_2026-08-12.md`).  Everything below has
landed since and **has never been in fabric**.

### 4.1 WHAT IS IN THE TREE AND NOT IN THE BITSTREAM

`git diff 3118a2db46..HEAD -- hdl/rtl` touches **one file**,
`hdl/rtl/ucore/v30u_eu.sv` (+99 / −7), and the constraint set has moved twice:

| # | landing | commit | what it changes for a bitstream |
|---|---|---|---|
| 1 | **The SDC's CE multicycle SPLIT BY ENABLE PHASE** — `ce → ce_half` 2/1 and `ce_half → ce` 3/2 beside the 4/3 | `f17102066f`, results `5b409f6a27` | a **correctness** fix to the constraints (the uniform multicycle was optimistic by two full periods on the one `ce_half`-gated flop).  Amendment A-1 was built, measured at **−2.41 MHz** and **WITHDRAWN**. |
| 2 | **`hdl/nec_test.qsf` CRLF restored** | `78f2cf4a77` | none functionally; it is an erratum against the SignalTap edit |
| 3 | **E-1 DELETED** — the observation multicycle | `a1c63e78e4` | the tree is now constrained **strictly tighter** than FLASH #20's.  Cost measured at −4.36 / −3.29 MHz. |
| 4 | **`CHAIN_MAX 12 → 7`** | `4dd395a7ad` | **RTL.**  ALMs −15.6 % (12,271 → 10,358; EU combinational −25 %).  Zero-behaviour by its own registered ladder. |
| 5 | **the chain-depth falsifier** `hdl/tb/tb_chain_lfsr.sv` | `9c5fb42490`, `4ff3c38ef8` | **testbench only — not in any bitstream.**  Listed so it is not mistaken for one. |
| 6 | **L1 — the registered microcode decode** | `9bf70f2eec` | **RTL**, and it makes Quartus infer an **M10K** for `ucdecode` (8192 × 12, `dec_q[0..9]` packed in as its address register) |
| 7 | **this wave** | `575649e2c1` … `4a90dd3f4e` | **NOTHING.  No RTL was changed.**  Paired reporting, the anatomy, the instruments and the ie-pinfall re-derivation are all offline. |

### 4.2 THE OWED FABRIC BAR THAT IS NEW, AND WHY IT IS NOT OPTIONAL

**No bitstream carrying an M10K `ucdecode` has ever been in fabric.**  F44's
failure mode is a **silent empty table** — the design runs and the microcode is
wrong — and **Verilator cannot see it**, because Verilator reads `ucrom.hex`
through `$readmemh` while Quartus programs a `.mif` it generates itself.
`adcone_l1_results_2026-08-13.md` §3.3 registered the bar and this wave does
not discharge it:

> Before any flash of this tree, **`python3 sw/ucrom_mif_check.py` must be run
> on THAT BUILD's own `db`** (it reads `hdl/db/…hdl.mif`, so it is on-demand
> after a build and cannot be run in advance), **and first light
> `check_ab_hw` MATCH 800 ×3 must be taken as usual.**

### 4.3 THE FLASH #21 PRE-REGISTRATION SKELETON

Everything below is committed **before board contact**, per the standing board
discipline.  **This wave writes the skeleton; it does not fill it in, and it
touches no board.**

**BUILD AND PROVENANCE**
* the built tree's commit; `nec_test_ucore.sof` / `.rbf` sha256; **RETENTION**
  (`--retention`), with the receipt **self-labelling** `RETENTION
  (X1_AD_RETENTION=1)` and an `.rbf` **differing from the control's** (E-6/E-9,
  the FLASH #18 falsifier, unchanged);
* **G6 `--seeds 5` on BOTH configurations of the exact tree to be flashed**,
  reported as the **PAIR** (§2): the **whole-design worst-of-5** is the
  promotion gate (≥ 32 MHz, worst setup > 0, TNS 0.000 setup AND hold, E7-E10);
  the core-domain worst-of-5 is recorded beside it and **gates nothing**;
* `flash_log.jsonl` **23 → 24**, `sw/safe_flash.sh` with its VERIFY leg.

**THE NEW BAR (§4.2)**
* **N-1** `ucrom_mif_check` **PASS on the flashed build's own `db`** — 8192 × 12
  against `ucdecode.hex` and 1028 × 29 against `ucrom.hex`, every word — with
  its non-vacuity control (one flipped bit → FAIL) run in the same sitting;
* **N-2** first light `check_ab_hw` **MATCH 800 ×3**.

**THE PRIMARY PREDICTION IS A NULL, AND THAT IS THE STRONGEST FORM AVAILABLE**
* Both RTL landings since FLASH #20 (`CHAIN_MAX`, L1) are **registered
  zero-behaviour** and were measured as such offline (L1: 306 fz2 seeds /
  1,243,278 replayed rows, 4 × 400,000 LFSR clocks and 2,200 ie-pinfall cells
  **byte-identical**).  So:
  * **P-1** the fz2 corpus does **not** move: failures and the seed/row rates
    identical to FLASH #20's, **0 ledger membership flips in either direction**,
    `first_bad` identical on every failure;
  * **P-2** the directed cells do not move: `tf0f`, `ie-pinfall` **0 chip-column
    movers** and the core column identical to this tree's offline table
    (`963a8065eb94b49c…`, §5);
  * **P-3** the S16 walk and the four HLT sweeps reproduce their offline
    columns cell for cell, `0` PASS/FAIL disagreements against `tb_sys ret`;
  * **A MOVER IS A FINDING, NOT A FAILURE** — it would mean a landing that
    measured zero-behaviour offline is not zero-behaviour in fabric, and the
    M10K is the named suspect.
* **P-4** the fabric era guard PASSES **without** the bypass (the one §70.7
  `.qsf` exemption);
* **P-5** `use_core=0` chip proof **MATCH 800** after everything;
  `div_guard` **PINNED** on 100 % of probes; `board_idle()` clean.

**RISK, NAMED IN ADVANCE**
* the M10K is the first block memory ever to hold the microcode in fabric
  (N-1/N-2 exist for it);
* the tree's constraint set is **tighter** than FLASH #20's in two independent
  ways (E-1 deleted, the enable-phase split), so a **regression** in fabric
  would be evidence about the constraints, not about the RTL — and the control
  that separates them is that **no RTL changed between the two SDC landings**.

---

## §5 WHAT IS BOOKED, NOT DONE

1. **`c_int_q`, with its re-open condition** (§1.4): re-open when the
   observation class no longer binds the worst draw of a configuration.  The
   mechanism, its cost and its candidate design are written down so the next
   agent does not re-derive them.
2. **The `~DUPLICATE` leak in `sta_truefmax_probe.tcl`'s `k=4.0` row** (§2) —
   now known to err in the **unsafe** direction, which §6 of the distribution
   gate said it could not.  The repair is to match the duplicate suffix in the
   SDC-mirroring collections **and** to rank by `slack/k` inside each class;
   it is not taken here because it would silently re-base every figure taken
   with the current probe.
3. **`sta_intcone_probe.tcl` does not filter by clock domain** (§1.2 note ⁽¹⁾):
   its §D/§E ceilings can return a `sld_jtag_hub` cross-domain path that is not
   a `divclk` ceiling.  `sta_truefmax_probe.tcl` already excludes that class and
   documents why; this probe should inherit the filter.
4. **The M10K fabric bar** (§4.2) — owed before any flash, not this wave's to
   discharge because this wave flashes nothing.
5. **A RIG NOTE FOUND BY THIS WAVE, AND IT COST A BUILD**: `sw/run_intcone_g6.sh`
   assumed the sweep's `hdl/db` survives the sweep, so it could re-fit one seed
   on the sweep's own map for a few minutes instead of re-mapping.  **It does
   not**: `run_sweep()` re-runs `gen_ucore_qsf.py` after the last stage, and
   Quartus then refuses the fit with
   *"Run Analysis and Synthesis (quartus_map) … before running the current
   software"*.  The leg was re-run from a clean map instead.  **Nothing was
   claimed from the failed run**, and the question it was going to answer —
   *does `c_int_q` bind the RETENTION worst draw?* — was already answered by
   that sweep's own `RUNG 1a` (§3.2), with no extra build at all.
6. **A worst-of-N over *(map, seed)* pairs** — still booked, not built
   (`timing50_distribution_2026-08-13.md` §13.1).  Everything in §3 is a
   distribution at a FIXED map, and map variance sits on top of it.
