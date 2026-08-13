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
| **PART 3 — the final band** | <!-- P3-HEADLINE --> |

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
| seed 5 | 44.36 / +8.708 | 47.34 | <!-- SEED5-D --> | <!-- SEED5-BENEFIT --> |

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

**RETENTION reaches the same place from its own committed numbers**: its
`worst-of-5` is **seed 2 at 43.50**, binding cone `ucdecode M10K → ad_in_q[11]`
(observation), with `rung 1a` — the `c_int_q` class — at **47.42 (k = 1.0)**,
**3.92 MHz clear**.  §3.3 re-measures it with this wave's own instrument on the
final tree rather than leaving it quoted.

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

<!-- P3-TABLES -->

### 3.2 THE CENSUS — WHAT BINDS, AND WHAT IS BEHIND IT

<!-- P3-CENSUS -->

### 3.3 WHAT 50 MHz MEANS UNDER PAIRED REPORTING

<!-- P3-50 -->

### 3.4 THE CLOSING STATEMENT OF THE 50 MHz CAMPAIGN

<!-- P3-CLOSING -->

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
5. **A worst-of-N over *(map, seed)* pairs** — still booked, not built
   (`timing50_distribution_2026-08-13.md` §13.1).  Everything in §3 is a
   distribution at a FIXED map, and map variance sits on top of it.
