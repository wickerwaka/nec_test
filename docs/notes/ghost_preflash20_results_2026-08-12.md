# RESULTS — THE PRE-FLASH-#20 OFFLINE WAVE

Pre-registration `ghost_preflash20_prereg_2026-08-12.md` (`d1d19a1d2e`,
committed **before the first RTL edit**) with **amendment A-1** (`7df621ba89`,
committed **before F-B′ was scored**). Landing `292f30bcf8`.

Base `5cdca40b60`, branch `fuzz-v2-on-relanding`, isolated worktree
(provisioned at `master`, **RESET** to the base before anything was read).
**OFFLINE THROUGHOUT — the board was not touched**, no socket command issued,
`flash_log.jsonl` untouched. No Codex, no nested tasks.

⚠ `--no-fabric-era-guard` is in force on every `fz2_replay` figure below, for
`5cdca40b60` §1's reason: the relocation's four RTL files postdate FLASH #19's
bitstream. **Every replay number here is an offline CORE-side number scored
against FLASH #19's banked SOCKET rows**, which are silicon and are not in
question. No fabric figure is quoted or implied.

---

## §0 HEADLINE

| item | disposition |
|---|---|
| **1 — `fz2e/528010`** | **DIAGNOSED to mechanism and FIXED.** `bad_rows` 2,067 → **7**. The relocation EXPOSED a pre-existing wrong; the fix (F-B′) is derived from the law and DELETES a case. Residual +3 vs the pre-relocation 4 is diagnosed as relocation prereg §7(c), booked. |
| **2 — `fz2c/406063`** | **DIAGNOSED to mechanism, BOOKED, not fixed.** The relocation is RIGHT on this seed — it closes rows 245-248 exactly onto silicon. The residue is the un-relocated SPLIT PARTNER, relocation prereg §7(b), whose registered note is that no measurement exists. This is its first measurement. Non-mover clause recorded as MISSED. |
| **3 — the `imul` falsifier** | **TAKEN AND ALL FIVE BARS MET EXACTLY.** `imul` 2/16 → **16/16**, `mul` unmoved, cell 384 → **398** (+14, −0), **0** banked seeds moved. The registered G-3 shortfall is fully closed. |
| **4 — the retention yellow flag** | see §6 |
| **FLASH #20** | see §7 |

---

## §1 THE BASELINE, MEASURED NOT ASSUMED

Every number in this document is a delta against a measurement taken at
`5cdca40b60` on a clean tree before any edit.

```
fz2_replay --ledger …f19… --all-failures --pass-sample 150 --leg ret --jobs 8
  264 seeds (114 fabric-FAIL, 150 fabric-PASS), 0 errors
  verdict agreement 261/264 = 98.9 %,  total bad_rows 118,854
ghost_pred_cell score   identical 384 / different 136
ghost_launch_law score  200/200, exit 0
```

`fz2e/528010` **2,067** · `flick` 2 · `first` 1,383 · `fz2c/406063` **3,165** ·
`first` 249 — reproducing `5cdca40b60` §3.4 exactly.

**AND THE PRE-RELOCATION COLUMN WAS BUILT, NOT ASSUMED.** The four relocation
RTL files were reverted in place to `3836779ade`, `tb_sys ret` rebuilt, and both
seeds replayed: **`528010` `bad` 4 / `first` 1,383 and `406063` `bad` 3,149 /
`first` 245 — the banked FLASH #19 ledger values exactly.** The RTL was then
restored to HEAD and the numbers reproduced. That is the before-column every
bisect below is read against.

---

## §2 ITEM 1 AND ITEM 2 — THE BISECT

The relocation has two separable halves. The bisect variant is **HEAD with
wave-4's V2 arm restored into `ghost_bus_off` and the BIU launch relocation left
in place**; it is a diagnostic and was never a landing candidate.

| seed | bisect vs PRE-relocation | bisect vs HEAD |
|---|---|---|
| `fz2e/528010` | **byte-identical, all 4,063 rows** | first differs at 1,383 |
| `fz2c/406063` | first differs at 245 | **byte-identical, all 4,063 rows** |

**Each half is INERT on the other's seed.** `528010` is owned entirely by the
EU-side V2 deletion; `406063` entirely by the BIU launch relocation.

### 2.1 `fz2e/528010` — A WHOLE BUS CYCLE, NOT AN ADDRESS

One ghost event in the entire window. EU probe (added, read, **removed**; the
landed tree has no probe, and its removal was proved inert — 264 seeds, 0
moved, total `bad_rows` byte-identical):

```
V2 present  bus_off=9537 sp=9537 and=9504 uses_ea=1  addr=863a7 split=1 pair2=1
HEAD        bus_off=9504 sp=9537 and=9504 uses_ea=1  addr=86374 split=0 pair2=0
```

`acc_split`'s ghost branch was `(ghost_uses_ea || ghost_uses_mul_hi) ?
acc_phys_base[0] : ghost_stack_phys[0]`, and `acc_phys_base[0]` **is the posted
value's low bit**. V2 posted `SP` = `0x9537`, ODD → split. HEAD posts the AND =
`0x9504`, EVEN → no split.

The row stream is the direct consequence, measured: from 1,383 onward
**`post[i] == pre[i+6]` on 2,241 of 2,674 rows (83.8 %)** against ~16 % at every
other shift in [0, 12]. **One six-clock bus cycle — the split partner — is
missing.** That is the whole of 4 → 2,067.

**VERDICT: THE RELOCATION EXPOSED A PRE-EXISTING WRONG, AND ITS §2.1 CLAIM IS
FALSE AS WRITTEN.** `ghost_launch_landing_prereg` §2.1 says the surviving V1 arm
*"stays the POSTED value so that every post-time derived quantity … is computed
from the SAME expression it is computed from today."* **Deleting an arm IS a
change to the expression wherever that arm fired.** The quantity that moved is
not a decoration but the NUMBER OF BUS CYCLES.

The chip's own T1 there is `0x8B92D`, likewise ODD — **silicon splits and the
ucore had stopped**. V2 was accidentally right about the SHAPE while wrong about
the ADDRESS, so restoring it would be re-installing a fitted arm to recover a
coincidence. It was not restored.

### 2.2 `fz2c/406063` — THE RELOCATION WORKING, RESIDUE ON THE PARTNER

Probe: `uses_ea=0`, `v2fire=0`, `split=1` from `ghost_stack_phys[0]`,
`addr=13eb1` / `addr2=13eb2`.

Row for row, **the relocation CLOSES rows 245-248 exactly onto the chip**: core
`0x13EB1` → `0x1EF01`, which is the chip's own value, and row 247 likewise.
`first_bad` 245 → **249, four rows LATER**.

Row 249 is the **split partner**, un-relocated by construction
(`rq_ghost[1] = 1'b0`). The core drives posted+1 = `0x13EB2`; the chip drives
`0x1EF4E`, which is not the relocated first half + 1 either. **That is
relocation prereg §7(b) THE SPLIT GHOST, registered with *"no measurement
exists"* — this is its first measurement.**

3,149 → 3,165 is **+16 on a seed where 3,149 of 4,000 rows already diverge**: a
saturated cascade re-phasing behind a divergence that starts four rows later.
`5cdca40b60`'s own refutation of the band rule says the same thing from the
other side.

**DISPOSITION: BOOKED, NOT FIXED.** Relocating the partner is a second
mechanism (the BIU manufactures that cycle; it would have to carry the tag and
the age through the split arm) and it must be measured as one.

### 2.3 THE NON-MOVER AND HOLDOUT MISSES, RECORDED

`fz2c/406063` is a wave-8 HOLDOUT seat predicted *cascade-bound non-closure*
(H-2 stands — it did not close) **and** a W7-4 §64.1 named non-mover. It moved.
**Recorded as a non-mover clause MISS**, attributed to the BIU launch
relocation, mechanism §2.2. It is one of the 11 UNSCOREABLE seeds that
`fz2_immaterial_disposition` §4 explicitly declines to dispose of.

---

## §3 ITEM 3 — F-A, THE `imul` FALSIFIER: ALL FIVE BARS MET EXACTLY

`ghost_uses_mul_hi` DELETED with all three of its uses. Measured **alone**.

| bar | registered | measured | verdict |
|---|---|---|---|
| **A-1** | `imul` **2/16 → 16/16** | **16/16** | **MET** |
| **A-2** | `mul` unmoved 16/16; every other leg on its number | all thirteen EXACT; total core==chip **114/208 → 128/208** | **MET** |
| **A-3** | cell identical **384 → 398** (+14, −0) | **398 / 122** | **MET** |
| **A-4** | **0 banked seeds moved** over the 264 | **0 moved**, total `bad_rows` byte-identical at 118,854 | **MET** |
| **A-5** | `8F.0` 500/500 · `all` 169,000/169,000 · `ulockstep` 17,350 · sweeps 279/283 | all four exactly | **MET** |
| **A-6** | `ss_lint` 0x8E/232/220 · `r7_lint` · `test_artifact` 45/45 · qsf | all | **MET** |

Per leg, measured against the registered numbers:
`alu08` `alu44` `alu88` `imul` `mul` `v_or` `v_sub` **16/16** · `v_inc` **8/16**
· `mov8e` **4/16** · `mempop` **2/16** · `v_lea` **2/16** · `memw` **0/16** ·
`pfxpro` **0/16**. **Thirteen of thirteen on their registered number.**

**WHY THE ARM WAS INVISIBLE FOR SO LONG, and it is the interesting part:** on
the directed `imul` leg the chip's rail is `TMPA` = `0x1100` and the arm's value
`tmpa & opr` is `0x1000`, **which is also `E3 & SP`**. The two are
indistinguishable on every population that came before this one. Wave-4
measured the arm INERT on 654 seeds and left it standing for exactly the right
reason; `ghost_launch_law_results` §5.3 refused to authorise its deletion for
exactly the right reason; and the landing that found the coincidence refused to
act on it in the same sitting for exactly the right reason. **It is not a
second mechanism. It is a coincidence that was written down.**

### 3.1 AN OBSERVATION AGAINST A FROZEN INSTRUMENT, NOT A BAR

`ghost_launch_pred score` — the relocation's **G-2**, 2,640/2,640 — now reads
**2,562 / 2,640**. `pred.json` is FROZEN and its own docstring says
*"`ghost_uses_mul_hi` is NOT modelled: the landing leaves that arm alone."*
**All 16 `imul` misses read `got == chip`**: the core now matches SILICON and
the stale prediction is what is wrong. Reported, not repaired — re-writing
`pred.json` to match a result is how a prediction stops being one.

---

## §4 F-B → F-B′ — REPORTED AS REGISTERED

### 4.1 F-B AS REGISTERED IS MISSED

| bar | registered | measured | verdict |
|---|---|---|---|
| **B-1** | `528010` `bad` **4** · `flick` 0 · `first` 1,383 | `bad` **7** · `flick` 0 · `first` 1,383 | **MISSED by +3** |
| **B-2** | `406063` unmoved 3,165 / 249 | unmoved | **MET** |
| **B-3** | 0 LOST, 0 first_bad EARLIER | 0 and 0 | **MET** |

and three seeds moved, **two unregistered, one of them WORSE**: `fz2e/518067`
3,278 → 45 (−3,233), `fz2e/528010` 2,067 → 7, **`fz2e/520066` 8 → 589 (+581)**.

### 4.2 THE DISCRIMINATOR IS THE GHOST'S OWN WIDTH — MEASURED, THEN REGISTERED

```
518067  uses_ea=1 accbase=56230 (EVEN) stackphys=5e249 (ODD) word=1  -> split RIGHT
520066  uses_ea=1 accbase=28f40 (EVEN) stackphys=2d597 (ODD) word=0  -> split WRONG
```

**`520066` is a BYTE ghost and a byte access cannot split.** `acc_split` guards
on `!acc_byte`; `eu_word` **is** `!acc_byte` on every non-ghost path (its own
default arm) and is **not** on the ghost's, which carries
`ghost_next_byte || (eu_ghost_full && modrm_reg == 0 && m_idx == 0)`. **The lane
mux and the split decision were reading two different widths.** One wire deep,
and it is the same misunderstanding wave-4's fitted V2 arm was papering over.

Amendment **A-1** was written and committed (`7df621ba89`) **before F-B′ was
built or scored**.

⚠ **`fz2e/520066` SELECTED the `eu_word` term, so its own recovery is NOT
evidence** (CLAUDE.md's standing rule). What is not fitted: `518067`, `528010`,
the three further seeds F-B′ improves that F-B did not, the 258 unmoved, the
golden ladder and the directed cell.

### 4.3 F-B′ — ALL EIGHT BARS MET

```systemverilog
wire acc_split = ghost_read_stale_alu ? (eu_word && ghost_stack_phys[0])
                                      : (!acc_byte && acc_phys[0]);
```

**An access splits iff it transfers a WORD across an ODD boundary.** Two cases,
as before; the `ghost_uses_ea` rail case deleted; the non-ghost arm byte-for-byte
unchanged, so `row_wr_add` and `pr_active` are untouched.

| bar | registered | measured | verdict |
|---|---|---|---|
| **B′-1** | `520066` returns to **8** *(selecting seed, not evidence)* | **8** | **MET** |
| **B′-2** | `518067` keeps **45** | **45** | **MET** |
| **B′-3** | `528010` keeps **7**, and the +3 is diagnosed | **7**, diagnosed §4.5 | **MET** |
| **B′-4** | `406063` UNMOVED 3,165 / 249 | unmoved | **MET** |
| **B′-5** | 0 LOST, 0 first_bad EARLIER, **no seed worse** | 0 / 0 / **0 worse** | **MET** |
| **B′-6** | golden ladder unmoved | §5 | **MET** |
| **B′-7** | cell and law unmoved from F-A's | **398** / **200/200** | **MET** |
| **B′-8** | `ss_lint` 0x8E/232/220, `r7_lint`, `test_artifact` | all | **MET** |

### 4.4 THE POPULATION MOVEMENT — SIX SEEDS, ALL SIX IMPROVED

| seed | HEAD | after | Δ | note |
|---|---:|---:|---:|---|
| `fz2e/518053` | 3,413 | **8** | **−3,405** | ⚠ a **W7-4 §64.1 named NON-MOVER** |
| `fz2e/518067` | 3,278 | **45** | −3,233 | |
| `fz2e/528010` | 2,067 | **7** | −2,060 | item 1 |
| `fz2e/530020` | 667 | **0** | −667 | **CLOSED**; a `TIMING_RECONVERGED` member |
| `fz2e/530046` | 2,063 | **1,634** | −429 | |
| `fz2c/409077` | 3,023 | **2,683** | −340 | |

**0 LOST · 0 first_bad EARLIER · 0 WORSE · net −10,134 rows** (118,854 →
108,720).

⚠ **`fz2e/518053` IS A NAMED NON-MOVER AND IT MOVED** — favourably, but the
clause is a clause. **Recorded as a second non-mover MISS**, mechanism §4.2.

⚠ **THE VERDICT-AGREEMENT CELL DROPS 261/264 → 260/264**, and the reason is
`fz2e/530020` closing: the offline core now replays PASS where FLASH #19's
fabric says FAIL. **That is the landing working, not a regression** — it is the
expected consequence of the core moving ahead of the flashed bitstream, and it
is precisely why FLASH #20 exists.

### 4.5 THE +3 ON `528010`, DIAGNOSED AND NOT ABSORBED

With the split restored the divergence is contained to rows 1,383-1,389.
Against the pre-relocation four:

* **4 rows are the RAIL** (§7(a)) — the ucore's `ghost_off` is not the chip's;
  unchanged in count.
* **3 rows (1,387-1,389) differ from silicon in `ube_n` ALONE**, `0` where the
  chip drives `1`.

That is relocation prereg **§7(c)** verbatim — *"`UBE` AND `A0` … are computed
at the post from the AND value and are NOT recomputed from the relocated
address. Every `BARE` value in the measured population is EVEN, so nothing here
tests it. Falsifier: a measured ghost T1 whose `UBE`/`A0` disagree with its
relocated address."* **THE FALSIFIER FIRES, AND THIS IS ITS FIRST
MEASUREMENT.** Booked; relocating `rq_ube`/`rq_odd` is the same second mechanism
as §2.2's partner and belongs with it.

### 4.6 THE PER-MECHANISM ATTRIBUTION IS EXACT

F-A alone: **0** of 264 seeds move. F-B′ alone: **6**, −10,134. Combined:
**identical to F-B′ alone on all 264, byte for byte.** Neither edit is credited
with the other's benefit, and F-A's whole measurable benefit is in the directed
cell (+14) and the law population (+14).

---

## §5 THE LADDER, ON THE LANDED TREE (`292f30bcf8`)

| gate | measured | registered |
|---|---|---|
| `check_core --core ucore --opcodes 8F.0 --cases 0` | **500/500** | 500/500 |
| `check_core --core ucore --opcodes all --cases 0` | **169,000/169,000** | 169,000 |
| `ulockstep --golden all --cases 50` | **17,350/17,350** | 17,350 |
| HLT sweeps (`--waits 0/1/2/3`) | **97 · 93 · 45 · 44 = 279/283** | 279/283 |
| `ghost_pred_cell score` (528-cell replay) | **398 identical / 122 different** | 398 |
| `ghost_launch_law score` | **200/200**, exit 0 | 200/200 |
| `fz2_replay` full, 264 seeds | 0 errors, **0 LOST**, **0 first_bad EARLIER**, 0 worse | as registered |
| `fz2_immaterial falsify` | **PASS, G1-G8** | PASS |
| `ss_lint --core ucore` | **PASS**, `SS_VERSION` 0x8E / `SS_COUNT` 232 / `SS_TAG` 0x8EE8, census **220**, 0 UNMAPPED | UNMOVED |
| `r7_lint` | **PASS**, 0 undeclared carriers, 0 `stop` sites | PASS |
| `test_artifact` | **45/45** | 45/45 |
| `gen_ucore_qsf --check` | up to date | up to date |
| `fz2_w1 lint` | **PASS**, 0 hits, 48 stratum rows | PASS |
| `fz2_w1 bars` | **10/11**, C-6 MISSED | carried as registered from FLASH #19, not re-litigated |

`v30u_ss_pkg.sv` is **untouched** by this wave — both edits DELETE combinational
terms and neither adds or removes a flop.

⚠ `fz2_bars.json` was **restored with `git checkout` after `bars` was run**, so
this wave does not overwrite another wave's artefact as a side effect of reading
it (`ghost_launch_law_results` §9's rule).

---

## §6 ITEM 4 — G6, AND THE RETENTION CONE NAMED

### 6.1 G6 — FOUR DRAWS, TWO PER CONFIGURATION, WORST-OF-2 QUOTED

| draw | config | Fmax | worst setup | TNS | ALMs | receipt |
|---|---|---:|---:|---|---:|---|
| 1 | CONTROL | **45.61** | +8.892 | 0.000 setup AND hold | 12,282 (29 %) | `5cb7bf587a1a202b…` |
| 2 | CONTROL | **45.61** | +8.892 | 0.000 | 12,282 (29 %) | `9f231a850f9a71a1…` |
| 1 | RETENTION | **44.32** | +8.689 | 0.000 | 12,245 (29 %) | `24a78dc1c617384c…` |
| 2 | RETENTION | **44.32** | +8.689 | 0.000 | 12,245 (29 %) | `517c06c81d51eae8…` |

**WORST-OF-2: CONTROL 45.61 / RETENTION 44.32.** 0 errors, 0 latches, 0
`lpm_divide` on all four. Every draw PASSES; the **38.0 STOP is cleared by
+6.32 MHz** on the worse configuration.

* **E-6 / E-9 MET**: the retention receipts **self-label RETENTION
  (X1_AD_RETENTION=1)**, DERIVED from the reports, and the retention `.rbf`
  `15742aa2f00431c4…` **differs** from the control's `277e7de5f8fcfcde…` — the
  check that `--verilog_macro` reached the compiler.
* Within each configuration **both draws produced a BYTE-IDENTICAL `.rbf`** and
  an identical 88-file input manifest `304b5d67ccd2cd5c…`.
* ⚠ CONTROL draw 1 and RETENTION draws 1-2 record `-dirty`. The dirt is this
  results document and the census outputs, **not a compiler input**: the input
  manifest sha256 is identical across all four draws and control draw 1's `.rbf`
  is byte-identical to clean-tree draw 2's. Stated rather than hidden.

**AGAINST THE REGISTERED BAND:**

| | E-1 reference | the relocation | **this tree** | Δ vs E-1 |
|---|---:|---:|---:|---:|
| CONTROL | 44.72 | 44.67 | **45.61** | **+0.89** |
| RETENTION | 45.71 | **41.60** | **44.32** | **−1.39** |

**THE REGISTERED YELLOW FLAG HAS RECEDED BUT IS NOT CLEARED.** The relocation's
retention deficit was −4.11 vs E-1; it is now **−1.39**, and the
control→retention gap is **−1.29 MHz**, inside the historical 0.02–2.13 cost
range. This wave adds no logic — both edits DELETE combinational arms — and ALMs
fall 12,282 → 12,245 between configurations. ⚠ **`standing_gates.md` §A governs:
ONE GREEN BUILD IS NOT CLOSURE**, and the same tree has drawn 19.42 and 45.91
MHz. Two draws agreeing bit-for-bit is stronger evidence than one, and it is
still two.

### 6.2 THE CONE, NAMED — AND IT IS **NOT** THE RELOCATION AND **NOT** RETENTION

`sw/sta_census.tcl` and `sw/sta_probe.tcl` on the retention build's own fitted
db (slow 1100 mV 100 C, the corner the gate scores), plus a control census for
comparison:

```
RETENTION   worst  8.689  47 levels
            emu|system_large|c_int_q  ->  v30u_eu|row_posted
            class census over the top 60: OUT->CORE n=60, worst 8.689
            latch histogram: v30u_eu 52 · v30u_biu 8
            worst per class: CORE->CORE 36.355 · ANY->CORE 8.689 · CORE->ANY 25.579

CONTROL     worst  8.892   8 levels   sld_mod_ram_rom -> sld_jtag_hub|tdo
            next    8.996  10 levels  nec_bus|div_cnt[4] -> v30u_biu|t1_half2
            the same c_int_q -> row_posted class is present at 45-50 levels,
            worst 9.324
```

**THREE THINGS THIS SETTLES:**

1. **IT IS NOT THE RELOCATION'S MUX.** `g_sp`, `g_bare`, `g_age`, `g_row_q`,
   `rq_ghost`, `cmt_ghost`, `cmt_addr`, `acc_split` and the string `ghost`
   appear **ZERO times** in either census, in the worst-path report, or in any
   worst-per-class row. The core's own `CORE->CORE` worst has **+36.355 ns** of
   slack against a 31.250 ns period.
2. **IT IS NOT THE RETENTION OBSERVATION PATH.** `sta_probe`'s ceiling leg
   excludes **all 48 observation registers** — including all twenty
   `core_ad_hold[*]` — and the worst path over the remaining 15,165 endpoints is
   **the same path at the same 8.689**. E-1 already covers `core_ad_hold`, and
   it is doing its job.
3. **IT IS `c_int_q → v30u_eu|row_posted`: THE INT PIN'S CAPTURE REGISTER
   REACHING THE EU'S POST DECISION, OUT→CORE, SINGLE-CYCLE, AT 46-47 LOGIC
   LEVELS.** Data delay 21.913 ns of a 31.250 ns period, 58 % interconnect.
   `nec_test.sdc`'s 4/3 CE multicycle covers only `v30u_* -> v30u_*`, so this
   class is checked single-cycle. **It is structurally the SAME class R7′ closed
   on `READY`** — a live pin carrier crossing into the EU's chain — on the INT
   pin instead.

**WHY THE TWO CONFIGURATIONS DIFFER** is then readable: the CONTROL number is
not bound by the core at all — its worst path is the SignalTap/JTAG hub
(`sld_mod_ram_rom → sld_jtag_hub|tdo`, 8 levels), an artefact of the debug
fabric. The RETENTION number IS bound by the INT cone. **The 1.29 MHz gap is not
a cost of the retention model; it is which of two unrelated cones happens to
bind.**

### 6.3 NO FIX TAKEN — BOOKED, WITH THE DERIVATION IT WOULD NEED

> ⚠⚠ **ERRATUM, 2026-08-12: THE RECIPE BELOW IS VOID TWICE OVER, AND THE
> BOOKING SURVIVES ONLY AS "THIS IS AN RTL PROBLEM".**
>
> The **USER RULING** of 2026-08-12 (part 1, the ce/ce_half portability
> contract; part 2, **it is UNIVERSAL**) forbids `div/2 − 1` as a premise
> anywhere in the SDC, rig-side included — so *"show … no path from it is read
> before `E(div/2 − 1)`"* is not a derivation that can be done.  And **E-1
> itself was DELETED** on the same ruling (`a1c63e78e4`;
> `docs/notes/timing50_e1_rederivation_2026-08-12.md`), so *"the same claim
> E-1 makes"* names a claim that no longer exists.
>
> **What stands**: `c_int_q → v30u_eu|row_posted` is a real cone and it is an
> **RTL** item — R7′'s shape on the INT pin — exactly as this section
> concludes.  **What is struck**: any suggestion that an SDC exception is the
> route to it.  There is no contract-only SDC form of this fix.

An E-1 analogue for `c_int_q` is **not a one-liner and is not taken**. E-1 is
legal only because `nec_test.sdc` §E-1 *derives* that every large-mode consumer
of the observation registers is gated by `tick_rise`/`tick_fall` and that the
earliest sample read has had `div/2 - 1` sys periods to settle. **The same
derivation has not been done for `c_int_q`**, whose consumer is the core's own
interrupt recognition and therefore inside the CPU, not in the harness.

**BOOKED for a timing pass, with the falsifier:** show that every consumer of
`c_int_q` is CE-gated at `bus_tick_rise` and that no path from it is read before
E(div/2 − 1); then and only then a `-setup 2 -hold 1` on that endpoint set is
the same claim E-1 makes. **Until that derivation exists, widening the SDC here
would be asserting something unproven about interrupt recognition**, which is
the one mechanism this campaign has spent the most measurements on.

---

## §7 FLASH #20 — THE THREE OFFLINE BLOCKERS ARE DISCHARGED

`5cdca40b60` declared FLASH #20 **NO-GO on three named offline items, none of
which needs the board.** All three are discharged:

| blocker | disposition |
|---|---|
| `fz2e/528010` | **FIXED** — 2,067 → **7**, mechanism named (§2.1), fix derived from the law and case-DELETING (§4.3), residual +3 diagnosed as §7(c) and booked (§4.5). **Final state REGISTERED.** |
| `fz2c/406063` | **DIAGNOSED and BOOKED** — the relocation is right on it; the residue is the un-relocated split partner, §7(b), first measurement (§2.2). **Final state REGISTERED at `bad` 3,165 / `first` 249.** Non-mover clause recorded MISSED. |
| the `imul` falsifier | **TAKEN, all five bars MET exactly** (§3). The registered G-3 shortfall is fully closed. |

**NO OFFLINE BLOCKER REMAINS**, and the wave additionally bought −10,134 rows
over the replayed population with **0 lost and 0 first-divergences earlier**.

**WHAT A FLASH #20 SITTING WOULD CARRY** — the two edits here plus the whole
launch relocation (`ef19010e63`), **which has never been in fabric**. Its
registered named-seat batch, to be pre-registered properly by that sitting:

* **this wave's six movers** — `fz2e/518053` 8 · `fz2e/518067` 45 ·
  `fz2e/528010` 7 · **`fz2e/530020` 0 (CLOSES)** · `fz2e/530046` 1,634 ·
  `fz2c/409077` 2,683;
* **the relocation's 28**, 26 of which improved, headed by `fz2e/526054`
  320 → 48 and the three unregistered closures `fz2e/521024`, `522002`,
  `534003`;
* **named non-movers to re-check** — `fz2c/406063` at 3,165, `fz2e/520066` at 8,
  and the rest of the §3.1 list;
* **the directed `8F` mod=3 cell**, where the ucore's column is now 398/520 and
  `imul` is 16/16.

⚠ **TWO THINGS THE BOARD SITTING MUST CARRY, NOT THIS ONE:**

1. **Every replay figure in this document is ERA-GUARD-BYPASSED** and is an
   OFFLINE core-side number. No fabric figure exists for this tree and none is
   implied. That is exactly what FLASH #20 would produce.
2. **`fz2_w1 bars` reads 10/11 with C-6 MISSED**, carried as registered from
   FLASH #19 and deliberately not re-litigated here.

**THE GO/NO-GO ITSELF IS NOT THIS WAVE'S TO TAKE** — it needs a board sitting
with its own pre-registration, single-writer check, and `use_core=False` socket
discipline. What this wave establishes is that **the reasons FLASH #20 was
NO-GO are gone.**
