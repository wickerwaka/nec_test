# TIMING50 — `CHAIN_MAX` 12 → 7: THE RESULTS

Pre-registration: `timing50_chainmax_prereg_2026-08-12.md`, committed at
`7346953a7c` **before the edit**.  Landing `4dd395a7ad`.  Harness `9c5fb42490`.
Tree at start `298d522872` (`master`).  **Offline.  NO board, NO flash.**

---

## §0 HEADLINE

**The lever bought AREA and DEPTH.  It did not buy BAND, and the
pre-registration said it would not.**

| | |
|---|---|
| the edit | `v30u_eu.sv:3068`, `CHAIN_MAX` `4'd12` → `4'd7`. One line of function. |
| behaviour | **ZERO CHANGE, measured three independent ways** (§3) |
| area | `v30u_eu` own combinational ALUTs **11,282 → 8,480 (−2,802, −24.8 %)**; `v30_core` total **13,521 → 10,738 (−20.6 %)**; registers **unmoved** |
| band | **CONTROL worst-of-2 41.18 → 39.79 MHz (−1.39)** — see §5, and **P-4 was pre-registered as PREDICTED TO MISS** |
| the finding | **the chain is not in this tree's binding cone, and now that is measured and not merely argued** (§4) |

---

## §1 THE EDIT

```
-localparam bit [3:0] CHAIN_MAX = 4'd12;
+localparam bit [3:0] CHAIN_MAX = 4'd7;
```

plus the comment block that records the three sources and the width refusal.
**Nothing else in `hdl/rtl/` changed.**

**The `[3:0]` width did NOT narrow, as pre-registered.** A `[2:0]` `chain`
wraps at the loop's own `chain + 4'd1` on reaching 7, so `8 < 7` never becomes
false and the unroll never terminates — an **elaboration hang**. It would also
silently re-key `CHAIN_PROBE`'s `{chain, st_n}` census, which assumes 4 + 6
bits. Six sites were read; the reason is now written beside the declaration.

---

## §2 THE NEW STANDING INSTRUMENT — `tb_chain_lfsr` + `chain_lfsr_gate`

`m72_downstream_timing_2026-08-12.md` §3 offered its LFSR harness and recorded
that it existed in neither repo. **It exists here now**, and it is a gate, not
a scratch artifact.

The environment is entirely LFSR — memory, `READY`, `INT`/`NMI`/`POLL_N` — and
the CE train is built to the **ce/ce_half contract (Reading B)** and to nothing
narrower: `ce` for one fabric clock, `ce_half` on the **next**, then an
LFSR-drawn gap `g ∈ [0,7]`. **There is no `div` in the file.**

### 2.1 THE REGISTERED BARS, ALL FOUR MET

| id | clause | result |
|---|---|---|
| **H-1** | depth ≤ 6, 0 overflows, 4 seeds × 400,000 fabric clocks | **MET** — `CHAIN_DEPTH_MAX 6`, `entry_st 25` (`S_EPOP`) on **every** seed, 0 overflows |
| **H-2** | the train reaches the contract MINIMUM gap ≥ 1,000×/seed; `ce & ce_half` coincide 0× | **MET** — `g0` = 8,985 / 9,163 / 8,903 / 8,936; coincide **0** |
| **H-3** | **NON-VACUITY**: at `CHAIN_MAX = 4` the `$fatal` must FIRE | **MET** — fires **4/4 seeds** |
| **H-4** | after the edit, output signatures byte-identical to the pre-edit run | **MET** — **4/4 seeds identical** |

`entry_st 25` is `S_EPOP` (`v30u_eu.sv:470`). **M72 reported depth 6 at entry
state 25; §51.2's census reported max depth 6. This tree reproduces both, on
arbitrary bytes rather than 347 known forms.**

`sw/chain_lfsr_gate.py` reads `CHAIN_MAX` **out of the RTL** rather than
carrying a second copy of the number it is checking, and requires
`depth ≤ CHAIN_MAX − 1` — a run that reaches the declared bound has consumed
the spare position and must be reported.

### 2.2 TWO INSTRUMENT FINDINGS, BOTH CAUGHT BY THE HARNESS'S OWN FALSIFIERS

**(a) THE FIRST SIGNATURE MIXER WAS SINGULAR AND THE CROSS-SEED CHECK FOUND
IT.** It was `sig <= rotl1(sig) ^ rotl32(sig) ^ data`. Both terms are
rotations, so the state map is the GF(2) polynomial `R + R^32 = R(1 + R^31)`,
which shares large factors with `R^64 + 1` and is **not invertible**: injected
data decays into the kernel. Measured, it returned the identical value
`a2f01e4ce7100a3b` on four seeds whose `BS_HIST` differed by a factor of five
(`MEMR` 890 vs 171). Replaced with a Fibonacci LFSR step (invertible), and
**"the signatures must DIFFER across seeds" is now a permanent bar** —
otherwise H-4 is a constant reproducing itself and proves nothing.

**(b) A LIVENESS FLOOR WAS ADDED.** A depth gate that passes on a core that is
not executing is vacuous — `CHAIN OVERFLOW` cannot fire in a machine that never
decodes. The harness now counts bus cycles by status, queue pops and
first-byte pops, and the gate floors them. Stated plainly: **the floor numbers
were chosen after seeing a run** (~1/3 of the weakest registered seed). They
are a dead-core detector and **nothing scored depends on them**.

The floors also caught something real on an unregistered exploratory set: at
4,000,000 clocks seed 14 reaches `fpops = 6`. Random byte streams can wedge,
and activity does **not** scale with clock count — so the gate's scaling of the
floor by `clocks/400000` is wrong above the registered form. Booked, not fixed
in this wave; the registered gate form (4 × 400,000) is unaffected.

---

## §3 ZERO BEHAVIOUR CHANGE, MEASURED THREE WAYS

1. **LFSR signatures byte-identical**, 4 seeds × 400,000 fabric clocks, over
   every core output on every fabric clock (H-4).
2. **`fz2_replay` byte-identical on 107 seeds.** Scored-content sha256
   `210867b198835c9c975f4ecb3c8c0922fe809b53774938256b25ea3f619a69b7` at
   `CHAIN_MAX = 12` **and** at `7`; the only field that moves is the `tb_sys`
   binary receipt, which must. First-bad-row agreement with fabric is
   **106/106 = 100 %** on both.
   ⚠ **THE FABRIC ERA GUARD WAS OVERRIDDEN AND THIS SAYS SO.** HEAD already
   differs from FLASH #19's bitstream in `nec_test.sdc`, `v30_core.sv`,
   `v30u_biu.sv`, `v30u_eu.sv`, `v30u_ss_pkg.sv` and `nec_test.qsf` — **that is
   E-1's deletion, committed before this wave, and not this change.** The A/B
   is therefore run tree-against-itself, which is what isolates `CHAIN_MAX`;
   no fabric claim is made.
3. **The full sim ladder at its registered values** — §6.

---

## §4 WHAT BINDS, AND HOW MUCH OF IT RUNS THROUGH THE CHAIN

**The brief's central question. The answer is: essentially none of it, and the
band result is the consequence.**

### 4.1 THE STRUCTURAL ANSWER, MEASURED ON THE SOURCE

The binding class is `v30u_eu|upc_opc[*] → nec_bus|ad_in_q[*]`, 29-40 levels,
single-cycle, 60 of the top 60 in both configurations
(`timing50_e1_rederivation_2026-08-12.md` §5, R-3).

**The chain writes only `*_n` — next-state names — and every one of them
terminates on a register `D` pin.** The core's AD publication is a separate
expression tree that never enters the chain:

```
upc_page / upc_opc / upc_loc   (REGISTERS)
    -> v30u_ucrom -> row
    -> v30u_eu   `assign eu_addr` / `eu_bs` / `eu_wdata` / `eu_pair`  (:2149-2177)
    -> v30u_biu  `assign ad_o`                                        (:1056-1065)
    -> nec_bus|ad_in_q
```

`v30u_biu.sv:1046-1049` already states the loop rule for this cone: *"this is
REGISTER-ONLY LOOKAHEAD … `eu_pair` / `eu_wdata`, which are functions of EU
REGISTERS only, and `ad_o` is a pin that feeds nothing inside the core."*

**Measured, not asserted**: the transitive fan-in of `eu_addr`, `eu_bs`,
`eu_wdata`, `eu_pair`, `eu_post`, `eu_addr2`, `eu_seg`, `eu_word`, `eu_split`
and `eu_ghost_acc` — **301 nets** — contains **ZERO** names written inside the
chain's `always @*` block or any of its nine `.svh` includes. (Three apparent
hits — `st`, `opr`, `opc_base` — are matches inside **comments**.)

### 4.2 WHY M72 SAW THE OPPOSITE, AND WHY THAT IS NOT A CONTRADICTION

M72's failing class was `upc_opc → ucdecode → ucrom → **the chain** →
`r_kind` / `modrm_reg`` — endpoints **inside the core**, i.e. `CORE→CORE`.

On this tree `CORE→CORE` carries **+30.696 (CTL) / +30.789 (RET)** and is
nowhere near binding, because `nec_test.sdc` gives it a **4-period** CE
multicycle where M72's `ce_steady` train gives it **two `clk_sys` periods**.
**The chain is deep in both designs; only one of them has a budget too small
for it.** Nothing in M72's report is wrong; the class it fixed is not the class
that binds here.

*Post-land census (`sta_census.tcl` on the fitted db): see §7.*

---

## §5 THE BAND — G6, WORST-OF-2, BOTH CONFIGURATIONS

Corner: 17.1.0 Lite, `5CSEBA6U23I7`, Slow 1100 mV 100 C, `divclk` 31.250 ns.

| draw | config | Fmax | worst setup | TNS setup/hold | verdict | receipt |
|---|---|---:|---:|---|---|---|
| 1 | CONTROL | **39.79** | +6.121 | 0.000 / 0.000 | PASS | `2b9667651e659f27…` |
| 2 | CONTROL | **39.79** | +6.121 | 0.000 / 0.000 | PASS | `9abc042b915939e…` |
| 1 | RETENTION | **43.76** | +8.396 | 0.000 / 0.000 | PASS | `75ca561fb619da23…` |
| 2 | RETENTION | _pending_ | | | | |

All draws carry input manifest `c23e63aa4cf19684…`, distinct from the baseline
tree's `837b0c700ac2138b…`. Both CONTROL draws drew the same number.

⚠ **THE TWO CONFIGURATIONS MOVED IN OPPOSITE DIRECTIONS** — CONTROL **−1.39
MHz**, RETENTION **+1.48 MHz**. Recorded, **not explained**. It is the same
sign instability `timing50_e1_rederivation_2026-08-12.md` §6.1a and
`standing_gates.md` §A have recorded and declined to explain at FLASH #13
(+0.46), #14, and Phase 1 (+0.03) — but this is the first time it has appeared
as a *difference of deltas* rather than a difference of levels, and it is
larger than any of those.

### 5.1 AGAINST THE HONEST BAND

| | baseline (CHAIN_MAX 12) | this tree (7) | delta |
|---|---:|---:|---|
| CONTROL worst-of-2 | **41.18** (three agreeing draws) | **39.79** | **−1.39 MHz** |
| RETENTION worst-of-2 | **42.28** (two agreeing draws) | _pending_ | |

### 5.2 THE REGISTERED DISPOSITION, APPLIED AS WRITTEN

| id | clause | result |
|---|---|---|
| **P-1** | whole-design ALMs strictly below 12,271 (CTL) / 12,317 (RET) | **MET** — §5.3 |
| **P-2** | `CORE→CORE` worst slack improves | §7 |
| **P-3** | the binding class stays `CORE→ANY`, `upc_opc → ad_in_q` | §7 |
| **P-4** | worst-of-2 improves ≥ 1.0 MHz on at least one configuration | **MISSED — and it was PRE-REGISTERED AS PREDICTED TO MISS** (prereg §4.1) |

### 5.3 P-1 — AREA, THE THING THE LEVER ACTUALLY BOUGHT

| | CHAIN_MAX 12 | CHAIN_MAX 7 | delta |
|---|---:|---:|---|
| whole design, ALMs (CONTROL) | **12,271 / 41,910 (29 %)** | **10,358 / 41,910 (25 %)** | **−1,913 (−15.6 %)** |
| whole design, ALMs (RETENTION) | **12,317 (29 %)** | **10,355 (25 %)** (draw 1) | **−1,962 (−15.9 %)** |
| `v30_core` total comb ALUTs (RET) | 13,503 | **10,673** | −2,830 (−21.0 %) |
| `v30u_eu` own comb ALUTs (RET) | 11,270 | **8,424** | **−2,846 (−25.3 %)** |
| `v30_core` total combinational ALUTs | 13,521 | **10,738** | **−2,783 (−20.6 %)** |
| `v30u_eu` own combinational ALUTs | 11,282 | **8,480** | **−2,802 (−24.8 %)** |
| `v30u_eu` total | 12,344 | 9,529 | −2,815 |
| `v30u_biu` own | 1,176 | 1,208 | +32 |
| `v30u_ucrom` own | 1,062 | 1,049 | −13 |
| `v30u_eu` dedicated logic registers | **724** | **724** | **0** |
| `v30u_biu` registers | **438** | **438** | **0** |
| `v30_core` total registers | **1,162** | **1,162** | **0** |
| whole design, fit registers | 6,053 | 5,982 | −71 |

Both CONTROL draws returned the identical ALM count.

**Five folded chain positions cost ~560 combinational ALUTs each.** §51.1
measured **~2,200 logic cells** for an *unfolded* position; this is the fold's
own factor of four, measured from the other side, and it is the first time the
folded position's marginal cost has been put on the record.

**The core's own register count did not move** — `v30_core` total 1,162 both
ways, in agreement with `ss_lint`'s 220 architectural flops. The **−71**
whole-design fit registers therefore sit **outside the core**; recorded as
observed, **not explained**, and consistent with the fitter making different
duplication decisions for a design 1,913 ALMs smaller.

The rule, registered before the builds: *a **P-4** miss is a finding, not a
failure — it reports that the chain was NOT the binding term here.* **NO REVERT
unless P-1 also misses.**

⚠ **REPORTED AS REGISTERED, NOT RESTATED**: P-4 did not merely fail to improve,
it **moved the wrong way by 1.39 MHz on CONTROL**. The disposition rule does
not distinguish "no gain" from "a loss" and it is applied as written; the loss
is recorded here as the thing to weigh, not argued away. Two considerations,
both stated as considerations and not as explanations:

* `standing_gates.md` §A governs — **one green build is not closure**, and the
  same tree has drawn 19.42 and 45.91 MHz. This is one pair of draws.
* The two draws agree exactly, as the baseline's three did, so this is not
  draw-to-draw scatter *within* a tree. **What it is, this wave does not
  know**, and a 20 % smaller EU changing the fitter's placement is a
  hypothesis, not a measurement.

---

## §6 THE LADDER

| gate | bar | measured |
|---|---|---|
| `gen_ucore_qsf --check` | PASS | **PASS** |
| `r7_lint` | PASS, 0 violations | **PASS** — 20 nets / 1 carrier / 3 tainted / 51 `stop` sites / 0 violations |
| `test_artifact` | 45/45 | **45/45** |
| `ss_lint --core ucore` | exit 0, no flop moved | **PASS** — `SS_VERSION` 0x8E / `SS_COUNT` 232 / `SS_TAG` 0x8EE8, **220 flops**, 0 UNMAPPED |
| `check_core --opcodes all --cases 0` | 169,000 | **169,000/169,000** |
| `check_core --opcodes 8F.0` | 500 | **500/500** |
| HLT sweeps w0/w1/w2/w3 (⚠ `--waits`) | 97 · 93 · 45 · 44 = 279/283 | **97 · 93 · 45 · 44 = 279/283** |
| `v0.1-w1` / `-w3` | 1,200 / 1,200 | **1,200 / 1,200** |
| `v0.1-w1 --opcodes EB` | 200 | **200/200** |
| `w0evt`/`w1evt`/`w2evt`/`w3evt` | 200/1,200/200/1,200 | **200 / 1,200 / 200 / 1,200** |
| `v0.1-w1evt-biased` | 1,200 | **1,200/1,200** |
| `check_boot --core ucore` | 220 / 400 MATCH | **MATCH / MATCH** |
| `ulockstep --golden all --cases 50` | 17,350 | **17,350/17,350** |
| `ghost_launch_law score` | 200/200 | **200/200 = 100.0 %** |
| `check_fuzz_bank` | PASS, 621 seeds | **PASS \| 621 \| stable 621 improved 0 worse 0 \| gen_drift 0 regen_err 0 \| new-sig TIMING 0** |
| `sm3_s16_score --core ucore` | 1,320/1,371 | **1,320/1,371** |
| `check_core --suite-dir f4a_boundary` | 160 | **160/160** |
| `check_core --suite-dir f0lock_tranche` | 400 | **400/400** |
| `fz2_w1 bars` | 11/11 MET | **11/11 MET** — `fz2_bars.json` byte-identical but for its timestamp, so the file was reverted rather than committed as noise |
| `fz2_w1 lint` | PASS | **PASS / 0 hits / 48 stratum rows** (it cross-checks the campaign docs against the code; this wave's doc edits do not trip it) |
| `fz2_replay` | byte-identical | **byte-identical**, §3 item 2 |
| `chain_lfsr_gate` | depth ≤ 6, 0 overflows | **PASS**, §2 |
| **G6** ×2 CONTROL, ×2 RETENTION | PASS every draw | §5 |

### 6.1 THE ie-pinfall REPLAY — ATTEMPTED, AND REPORTED AS ATTEMPTED

`ie_pinfall_cell.py core` reproduces **2,200 cells** and its output is
**not** byte-identical to the committed reference. **That reference is dated
2026-08-11 and predates E-1's deletion**, so it is stale against HEAD
independently of this change — the same situation the fz2 era guard names.
10 of its 14 files are identical; the 4 that differ are `eihlt_w1`, `eihlt_w2`,
`table.json` and the manifest (whose `seconds`/`ts` must differ).

The A/B that would isolate `CHAIN_MAX` — regenerate at 12 on **this** tree and
diff — **was started and deliberately abandoned**, because it required flipping
the RTL while a Quartus build was running. See §8. The evidence for zero
behaviour change rests on the three legs in §3, and this leg is reported as
**not run**, not as passed.

---

## §7 POST-LAND CENSUS — WHAT BINDS NOW

`sw/sta_census.tcl` on each configuration's **own** fitted `db`, corner Slow
1100 mV 100 C.  Baseline column is
`timing50_e1_rederivation_2026-08-12.md` §6.1 / §6.1a.

### 7.1 CONTROL

| class | CHAIN_MAX 12 | **CHAIN_MAX 7** | |
|---|---:|---:|---|
| `CORE→CORE` | +30.696 (`upc_opc[4] → t1_half2`) | _pending_ | |
| `CORE→ANY` | **+6.964** (`upc_opc[0]~DUPLICATE → ad_in_q[13]`, 29 levels) | _pending_ | |
| `ANY→CORE` | +9.114 (`div_cnt[4] → t1_half2`) | _pending_ | |
| `ANY→ANY` | +6.964 | _pending_ | |

### 7.2 RETENTION

| class | CHAIN_MAX 12 | **CHAIN_MAX 7** | |
|---|---:|---:|---|
| `CORE→CORE` | +30.789 (`upc_opc[3] → t1_half2`) | _pending_ | |
| `CORE→ANY` | **+7.600** (`upc_opc[3]~DUPLICATE → ad_in_q[8]`) | _pending_ | |
| `ANY→CORE` | +8.573 (`div_cnt[4] → t1_half2`) | _pending_ | |
| `ANY→ANY` | +7.600 | _pending_ | |

### 7.3 HOW FAR TO 50, AND WHAT IS NEXT

_pending._

---

## §8 A PROCESS FINDING, RECORDED BECAUSE IT NEARLY PRODUCED A FALSE NUMBER

**Two RETENTION draws were built from the WRONG RTL and were discarded before
either wrote a receipt.**

To run the ie-pinfall A/B, `CHAIN_MAX` was flipped back to `4'd12` in the
working tree at 22:19:49 local. `quartus_map` for `chainmax7-retention-d1`
started at **22:20:08 — nineteen seconds later**, and Quartus reads the RTL off
disk at that moment. Both retention draws were killed, the RTL restored, and
the two draws re-run from a clean `db` with nothing else touching `hdl/`.

**The receipt layer would NOT have caught this.** `quartus_gate` hashes its
88-file input manifest at *receipt-writing* time, i.e. after the build, so a
file restored during the run hashes to the value the build did not use. What
caught it was a wall-clock comparison of the file's mtime against the
`Processing started` line in the stage log. **The two CONTROL draws are
unaffected and are proved so two ways**: draw 1 completed entirely before the
flip, and draw 2 carries the identical input manifest `c23e63aa4cf19684…`.

Booked as an instrument gap: *a build gate whose input manifest is taken after
the build cannot detect a source file that changed during it.* A start-time
manifest, compared against the end-time one, would close it. Not taken here.

**Also recorded**: one **RED, unlabelled receipt** (`ffa6bddc8a30e36b…`) sits in
`sw/testdata/receipts/quartus_bitstream.jsonl` from a `--parse-only` probe run
against a half-finished report set. It carries no Fmax, is marked RED, and
**nothing quotes it**. It is retained rather than deleted.
