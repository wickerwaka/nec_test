# THE `c_int_q → v30u_eu` LAUNCH CONE — THE ANATOMY, BEFORE ANY DESIGN

**Branch `master`, HEAD `3ce86eb4b5` (isolated worktree, HEAD verified on
entry).  OFFLINE ONLY.  NO BOARD, NO FLASH.  No Codex consulted, no nested task
spawned.**  Nothing in `hdl/` is edited by this document; it is the measurement
the design must be chosen from, and it is committed **before** the design.

---

## §0 WHY RE-TAKE AN ANATOMY THAT ALREADY EXISTS

`timing50_phase2_results_2026-08-12.md` measured this cone once and concluded
**"the INT cone is TAIL-limited, not prefix-limited — removing three levels at
the head buys nothing"**.  That finding was taken on **one seed** of a tree
that predates **both** structural landings since:

* **`CHAIN_MAX 12 → 7`** (`41a60bd42c`), which took the EU's `row_posted_n~1…~9`
  cascade — Phase 2's own named tail component, *"~5.7 ns, 12 levels"* — out of
  the design; and
* **L1** (`9bf70f2eec`), which moved the microcode head onto an M10K, dropped
  ~230 ALMs and **re-placed the whole netlist**.

Phase 2's §7.2 handed `CHAIN_MAX` forward as *"the named, measured next lever"*
in this cone's tail.  It has since been taken.  **So the question this document
re-asks is not whether the tail dominated in the past; it is where the delay
sits now, on the draws the current registered figure is quoted from.**

New instrument: **`sw/sta_intcone_anatomy.tcl`** — `sta_adcone_anatomy.tcl`'s
treatment (region histogram, net census over a population, worst path node by
node) aimed at paths **launched by** `c_int_q` instead of paths **landing in**
an observation register, plus two sections the AD-cone version has no use for:
an **endpoint histogram** (what does the pin's cone actually latch in?) and
**Phase 2's own prefix/tail split at `ann_kill`**, so the two measurements are
comparable number for number.  Driver `sw/run_intcone_anatomy.sh`, which
replicates `quartus_gate.py --seeds` stage for stage and carries the same
single-writer guard.  **Neither is a gate and neither writes a receipt.**

⚠ **THE LAUNCH COLLECTION INCLUDES THE `~DUPLICATE` FORMS.**  The distribution
gate's §6 found `sta_truefmax_probe.tcl` missing them by exact name, and
`adcone_l1_results_2026-08-13.md` §4.3 records that the leak *"now also hits
RUNG 2's `c_int_q` exclusion"* — which is this cone.  Measured here: the
collection is **3 registers** and **the worst path launches from
`c_int_q~DUPLICATE`**, so an exact-name query would have missed it.

---

## §1 THE DRAW — CONTROL SEED 1, AND IT REPRODUCES THE REGISTERED SWEEP EXACTLY

`sw/testdata/intcone/anat-ctl/`, CONTROL, corner Slow 1100 mV 100 C, `divclk`
at 31.250 ns, seed echoed back by Quartus as `Fitter Initial Placement Seed 1`.

| | registered in `adcone_l1_results_2026-08-13.md` §2.1/§3.2 | measured here |
|---|---|---|
| CONTROL seed 1 worst setup | **+7.276** | **+7.276** |
| binding cone | `opc_from_modrm → ad_in_q[14]` | `opc_from_modrm → ad_in_q[14]` |
| `ANY→CORE` (the `c_int_q` cone) | **+7.949**, `c_int_q~DUP → rd_pending[0]` | **+7.949**, `c_int_q~DUP → rd_pending[0]` |

**An independently produced map reproduces the registered draw to the digit on
all three quantities.**  That is the control that makes this the anatomy of the
draw the current CONTROL `worst-of-5` is quoted from — **seed 1 IS that draw**
(`worst-of-5@seeds{1..5} = 41.71`, seed 1).

---

## §2 THE FINDING THAT DECIDES THE WAVE, AND IT IS MEASURED, NOT ARGUED

`sw/sta_intcone_probe.tcl` §D asks the only question that matters for a benefit
claim: **what is the worst path in the design once `c_int_q` is excluded as a
launch register** — i.e. what would a *perfect* fix of this cone leave behind?

```
D. CEILING -- worst setup path with c_int_q excluded as a LAUNCH register:
       7.276 ns   20 levels   v30u_eu|opc_from_modrm -> nec_bus|ad_in_q[14]
       7.340 ns   20 levels   v30u_eu|opc_from_modrm -> nec_bus|ad_in_q[14]
       7.376 ns   20 levels   v30u_eu|opc_from_modrm -> nec_bus|ad_in_q[14]
E. CEILING -- worst setup path with the WHOLE pin class excluded as launch:
       7.276 ns   20 levels   (identical -- the other four pins are 19-30 ns clear)
```

> **THE CEILING BEHIND `c_int_q` ON THE WORST CONTROL DRAW IS `+7.276` — THE
> DRAW'S OWN WORST SETUP.  A PERFECT FIX OF THIS CONE MOVES THIS DRAW BY
> 0.000 ns AND THE CONTROL `worst-of-5` BY +0.00 MHz.**

It is worth being exact about why, because it is arithmetic and not a
prediction: **`worst-of-N` is the MINIMUM over the draws**, the CONTROL minimum
is seed 1 at **41.71 MHz**, and seed 1 is bound by the **observation** class,
not by `c_int_q`.  Fixing a cone that is 0.673 ns *behind* the binding cone on
the draw that sets the figure cannot move the figure.

The same holds on RETENTION from the committed sweep: its `worst-of-5` is
**seed 2 at 43.50**, whose binding cone is `ucdecode M10K → ad_in_q[11]`
(observation) with **rung 1a at 47.42 (k = 1.0)** — the `c_int_q` class, **3.92
MHz clear**.  §5 re-measures this with the same instrument rather than quoting
it.

**This is the same shape as Phase 2's own disposition** (§5.2: *"R-a was
already decided arithmetically by CONTROL draw 1"*), and it is why this wave's
pre-registered floor is evaluated **before** an edit is written rather than
after a build.

---

## §3 WHERE THE DELAY IS — THE WORST PATH, SEGMENT BY SEGMENT

Read off `seed1.intanat.txt` §C.  The launch register's clock arrives at cum
**8.208 ns** (5.334 ns of PLL/clock network + 2.309 routing + 0.565 clk→q), so
the **DATA PATH is 31.278 − 8.208 = 23.070 ns over 27 logic levels.**

| # | segment | nodes | ns | % | cells |
|---|---|---|---:|---:|---:|
| 1 | **the PREFIX** — the pin into the announcement | `flush_direct~0 · qs_e_now~7 · ~8 · ~9 · ann_kill~0 · ~1` | **3.154** | **13.7 %** | 6 |
| 2 | **the M7 PREFETCH-ELIGIBILITY SUM** | `display · occ~1 · Add40~3 · Add40~7 · Add39~17 · Add39~9 · pf_arm~2 · ~3` | **5.594** | **24.2 %** | 8 |
| 3 | **the EVAL, the GRANT and the SLOT** | `rmw_yield~1 · ~2 · cmt_valid~0 · ~1 · cmt_noaddr~0 · always2~15 · ~16 · LessThan19~0 · always2~19 · rq_bs~4 · slot_accept~1 · slot_busy~2` | **11.119** | **48.2 %** | 12 |
| 4 | **the EU** — `eu_slot_busy_n` to the register's own `D` pin | `rd_pending[1]~1 · rd_pending~3` | **3.203** | **13.9 %** | 2 |
| | **TOTAL** | | **23.070** | | **27** |

⚠ **A POST-FIT NODE NAME IS NOT A SIGNAL NAME.**  Quartus names a merged LUT
after one of the signals it participates in, so `display|combout` and
`always2~15` are cells on this path, not evidence that the RTL wire `display`
feeds `occ`.  The segment boundaries above are drawn where the RTL says they
are (§4) and the node list is quoted as the tool produced it.

### 3.1 THE PHASE-2 SPLIT, RE-MEASURED — **THE TAIL STILL DOMINATES**

Averaged over 60 paths, `ann_kill` on **60 of 60**:

| | Phase 2 (one seed, pre-`CHAIN_MAX`, pre-L1) | **here** |
|---|---:|---:|
| PREFIX `c_int_q → ann_kill` (data) | 3.251 ns / 6 levels | **3.154 ns / 6 levels** |
| TAIL `ann_kill → endpoint` | 17.983 ns | **19.916 ns** (worst path) · **19.344** (60-path mean) |
| total data delay | 21.234 ns | **23.070 ns** |
| tail as a fraction of the data path | 84.7 % | **86.3 %** |

**The head is worth 3.154 ns of 23.070 and the answer to Phase 2's question is
unchanged: this cone is TAIL-limited.**  Two structural landings later, on a
different netlist, the prefix has not moved by a tenth of a nanosecond.

### 3.2 WHAT *DID* CHANGE — **`CHAIN_MAX` EMPTIED THE EU END, AND THE BIU KEPT ALL OF IT**

Phase 2 §7.2 partitioned the 21.2 ns tail as *"~12.0 ns / ~23 levels of BIU
next-state, then ~5.7 ns / 12 levels of EU, of which `row_posted_n~1 … ~9` is
the twelve-position chain's `stop` ladder"*.

**The EU half is gone.**  On this tree the EU contributes **two combinational
cells and 3.203 ns** — `slot_busy~2 → rd_pending[1]~1 → rd_pending~3 → the
`D` pin — and the `row_posted_n~*` cascade does not appear on any of the 60
paths.  `CHAIN_MAX 12 → 7` did exactly what it was landed to do.

**And the cone did not get shorter.**  All of the EU's lost depth, and more,
now sits in the BIU: segments 2 and 3 together are **16.713 ns and 20 of the 27
levels — 72.4 % of the data path — inside `v30u_biu`'s single procedural
next-state block.**

### 3.3 THE NET CENSUS — THE CLASS IS ONE CHAIN, ON EVERY PATH

Fifteen nets are on **60 of 60** paths: `c_int_q`, the clock network,
`qs_e_now` (2.052 ns/hit), `ann_kill` (0.638), `occ` (0.865), `Add40` (1.372),
`Add39` (1.725), `pf_arm` (0.853), `rmw_yield` (1.210), `rq_bs` (1.147),
`slot_accept` (1.042), `always2` (2.280); `slot_busy` and `rd_pending` are on
58.  **There is no second cone here** — the pin has one route into the EU and
the 60 worst paths are 60 placements of it.

### 3.4 THE ENDPOINTS — **WHAT `flush_int_live` ULTIMATELY GATES**

Over the worst **200** paths from `c_int_q` (`sta_intcone_probe.tcl` §B):

| endpoint | paths |
|---|---:|
| `v30u_eu|rd_pending[0]` | **93** |
| `v30u_eu|rd_pending[1]` | **89** |
| `v30u_eu|row_posted` | **18** |

25-30 logic levels, no other endpoint at all.  And the other four free-running
pin registers are not in the same conversation: `c_ready_q` **+20.196**,
`c_reset_q` **+19.450**, `c_polln_q` **+29.042**, `c_nmi_q` **+29.914** (one
level — it goes straight to `nmi_p[2]`, a flop).  **`c_int_q` is 12.2 ns worse
than the next-worst pin in its own class.**

---

## §4 THE RTL THE ANATOMY IMPLICATES, AND THE §64.1 BOUNDARY — **VERIFIED FIRST**

**THE RECOGNITION MACHINERY IS NOT ON THIS PATH, AND THAT IS CHECKED IN THE RTL
RATHER THAN ASSUMED.**  `v30u_eu.sv` reads the interrupt pin twice and the two
readings are different objects:

* **RECOGNITION** is `int_p[k]` / `ie_p[k]` / `intr_pending` — `irq_pin_int =
  int_p[2]`, `irq_int_lvl`, `eu_bnd_post`, `hlt_wake_*`.  **Every one is a tap
  of a shift register**, i.e. register-only, and the §64.1 one-bit wall lives
  there.  `pin_int`'s only route into it is `int_p`'s own `D` pin.
* **THE FLUSH** is `assign flush_int_live = pin_int` (`v30u_eu.sv:2323`) — the
  LIVE pin, published to the BIU.  **This anatomy is entirely about that wire**,
  and nothing below reads or moves an `int_p`, an `ie_p` or `intr_pending`.

Inside `v30u_biu.sv` the pin's route is four named steps and they line up with
§3's four segments:

1. `flush_direct` / `flush_src_live` (`:629-633`) → `qs_e_now` (`:799`) →
   `ann_kill` (`:510`) — **the prefix**.
2. `kill_l = ann_kill` is the next-state block's **first statement** (`:1644`),
   and its body clears **`cmt_valid`** (`:1677`).
3. Section (c)'s M7 sample (`:1895-1899`) then reads that same `cmt_valid`:

   ```systemverilog
   if (ts == TS_T3) begin
       occ = {1'b0, q_cnt}
           + (cur_fetch ? {3'b0, cur_pn} : 5'd0)
           + ((cmt_valid && cmt_fetch) ? {3'b0, cmt_pn} : 5'd0)   // <- the pin
           + (infl_now ? {3'b0, infl_n_now} : 5'd0);
       pf_arm = (occ <= 5'd4) && !halted;
   end
   ```

   **This is §3's segment 2, and it is a genuine term**: a withdrawn fetch's
   bytes must not be counted by the arbiter that decides whether to fetch more.
   The pin arrives at the *input* of a five-bit carry chain and rides all of it.
4. Section (d)'s eval (`:2055` `if (ev_here && !cmt_valid)`) then re-reads
   `cmt_valid` **and** `pf_arm` (`:2072`, `:2114`), grants, sets `slot_accept`
   (`:2103`) and `slot_busy` (`:1762` / `:2268`) — **§3's segment 3** — and
   `assign eu_slot_busy_n = slot_busy` (`:845`) crosses into the EU.

**AND THE CONSUMER END IS ALREADY IN THE R7′ FORM.**  The brief's question —
*which register `D`-pins does `flush_int_live` ultimately gate, and is there an
`eu_rd_edge`-shaped move at that end?* — is answered by §3.4 and by
`v30u_eu_step.svh:546-556`:

```systemverilog
S_PRERD: if (chain == 4'd0) begin
    if (!row_posted_n) begin
        if (eu_slot_busy_n) stop = 1'b1;
        else begin row_posted_n = 1'b1; rd_pending_n = rd_pending_n + 2'd1; stop = 1'b1; end
    end
```

Every branch sets `stop`, so the carrier's cone **ends at `row_posted_n` /
`rd_pending_n`** — it selects a `D`-pin value under register-only predicates
and does **not** seed the twelve-position chain.  `v30u_eu.sv:1754-1756` says
so in as many words, and the measurement agrees: **two combinational cells**.
**R7′'s move has already been made at this end.  There is nothing left to take
there** — which is the answer to the question, and it is a negative one.

---

## §5 SEEDS 4 AND 5 — THE STABILITY CHECK

Same map, same driver.  Seed 4 is the CONTROL draw on which **`c_int_q` BINDS**
(`adcone_l1_results_2026-08-13.md` §2.1: 42.50, binding cone
`c_int_q → row_posted`); seed 5 is that sweep's **best** draw (44.36).  The
design conclusion is drawn from seed 1 — **the draw that sets the registered
figure** — and these two are the check that the structure is the tree's and not
the draw's.

### 5.1 ALL THREE DRAWS REPRODUCE THEIR REGISTERED VALUES TO THE DIGIT

| seed | `adcone_l1_results` §2.1 Fmax / setup | measured here | `rung 1a` there | `c_int_q` own-Fmax here |
|---|---:|---:|---:|---:|
| **1** | 41.71 / **+7.276** | **+7.276** | **42.92** | **42.92** |
| 4 | 42.50 / **+7.722** | **+7.722** | **42.50** | **42.50 — it BINDS** |
| 5 | 44.36 / **+8.708** | **+8.708** | **47.34** | **47.34** |

**Six independent agreements on an independently produced map** — three worst
setups and three `rung 1a` ceilings — which is the distribution gate's §7
determinism finding confirmed again, and the control that makes §2's ceiling
reading a statement about the registered sweep rather than about this run.

### 5.2 THE STRUCTURE IS THE TREE'S; THE ENDPOINT IS THE DRAW'S

| | seed 1 | seed 4 | seed 5 |
|---|---|---|---|
| endpoints over 60 paths | `rd_pending[0]` 30 · `[1]` 28 · `row_posted` 2 | **`row_posted` 60** | `rd_pending[0]` 19 · `[1]` 21 · `[1]~DUP` 20 |
| `ann_kill` on the path | **60/60** | **60/60** | **60/60** |
| PREFIX (incl. clock arrival) | 11.208 | 12.166 | 12.453 |
| TAIL `ann_kill → endpoint` | **19.344** | **18.797** | **16.485** |
| tail share of the two | **63.3 %** | **60.7 %** | **57.0 %** |

The three draws latch in three different places — one is entirely
`row_posted`, one is almost entirely `rd_pending`, one splits three ways
including a `~DUPLICATE` — and **the route is the same route on every path of
all three**: `flush_direct → qs_e_now → ann_kill → [the M7 occupancy sum] →
pf_arm → rmw_yield → cmt_* → rq_bs/slot_accept → slot_busy → the EU's D pin`.
Seed 4's own net census names it cell for cell with `occ`, `Add40`, `Add39`,
`pf_arm`, `rmw_yield` and `slot_busy` all on **60 of 60**, exactly as seed 1's
does.

**This is the AD cone's finding in the other cone: the class is a property of
the tree and the path is a property of the draw.**

### 5.3 AND THE CEILING READING HOLDS ON ALL THREE

`sta_intcone_probe.tcl` §D, per draw — *what a PERFECT fix would leave*:

| seed | worst path with `c_int_q` excluded | vs the draw's own worst setup | benefit |
|---|---|---:|---:|
| **1** | **+7.276** `opc_from_modrm → ad_in_q[14]` | +7.276 | **+0.000 ns** |
| 4 | +8.538 `modrm_reg[0] → ad_in_q[15]` ⁽¹⁾ | +7.722 | +0.816 ns |
| 5 | **+8.708** `ucdecode M10K → ad_in_q[0]` | +8.708 | **+0.000 ns** |

⁽¹⁾ read past two `sld_jtag_hub` rows at +8.272 / +8.498: they are
**cross-domain** (`capture_buf` → JTAG hub) and Quartus computes Fmax only
within a clock, so they are not a `divclk` ceiling.
`sta_truefmax_probe.tcl` excludes that class deliberately and says why;
**`sta_intcone_probe.tcl` does not filter by clock domain, and that is a gap in
the probe, named here rather than worked around.**

**Two of the three draws move by ZERO, and the one that moves is not the draw
that sets `worst-of-5`.**

---

## §6 WHAT IS *NOT* MEASURED HERE

* **Anything about fabric.**  No board was touched and no bitstream was built.
* **Whether a shorter cone would survive re-placement.**  Phase 2 measured that
  a 1.938 ns prefix saving was re-absorbed **98 %** by the fitter (+106 ALMs of
  duplication).  Nothing here re-tests that, and §2 is why nothing needs to.
* **`own-Fmax` is SLOW-1100 mV-100 C only**, so it is an upper bound on the
  multi-corner figure Quartus reports.  Used here only to rank cones within one
  draw, never as a band.
