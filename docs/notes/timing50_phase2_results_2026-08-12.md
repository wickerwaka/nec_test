# TIMING50 PHASE 2 — RESULTS: **P2-A IS BUILT, MEASURED, AND REVERTED BY ITS OWN RULE**

**Branch `master`, from HEAD `1e554257b6`.  ISOLATED WORKTREE.  OFFLINE ONLY.
NO BOARD, NO FLASH.**  `flash_log.jsonl` untouched, no socket command issued,
no Codex consulted, no nested task spawned.

Pre-registration `0e7be16342` (`timing50_phase2_prereg_2026-08-12.md`),
committed BEFORE the edit and BEFORE every build that scores it; the edit
`c137e8c105`, committed before every build that scores it.

---

## §0 HEADLINE

| | |
|---|---|
| **The cone's PREFIX did exactly what was predicted** | `c_int_q` → the next-state function: **6 levels / 3.251 ns → 3 levels / 1.313 ns**, a **−1.938 ns** saving, and `flush_direct` is gone from the pin's path entirely |
| **The cone's TOTAL did not move** | data delay **21.234 → 21.195 ns**, **−0.039 ns**. The tail from `ann_kill` to the endpoint grew **+1.899 ns** — it absorbed **98 %** of what the head gave up |
| **THE FINDING** | **the INT cone is TAIL-limited, not prefix-limited.** Removing three levels at the head buys nothing, because the 35 levels behind it re-place to fill the space. This is measured, not argued: the two figures agree to 0.04 ns. |
| **THE BAND** | CONTROL worst-of-2 **45.54 → 45.79** (**+0.25**); RETENTION, one draw, **45.57 → 45.48** (**−0.09**) — against **R-a's ≥ 1.5 on both** |
| **DISPOSITION** | **REVERTED, by the pre-registered rule R-a.** Not by judgement, not after re-reading the bar. |
| **ZERO BEHAVIOUR CHANGE — PROVEN TWICE** | the Shannon identity exhaustively over **8,388,608** assignments (0 mismatches, non-vacuity control 4,194,304), and the ie-pinfall column **2,200 / 2,200 cells BYTE-IDENTICAL** on this tree's own baseline |
| **WHAT PHASE 2 HANDS FORWARD** | the tail is **~23 BIU next-state levels + 12 EU levels**, of which the EU's `row_posted_n~1…~9` cascade is the twelve-position chain. **`CHAIN_MAX` is now the named, measured next lever** — and the ceiling behind the whole cone is **57.35 MHz (CONTROL) / 54.42 (RETENTION)**, so the headroom is real and unclaimed. |
| **⚠ A CORPUS EVENT, NOT THIS PHASE'S** | **0 of 114** fz2 ledger captures in the main checkout still match the ledger's `capture_sha256`; 107 were rewritten 2026-08-12 04:56–05:06 PDT and 7 are absent. `fz2_immaterial falsify` **cannot run** and is **owed, not claimed**. §6.3. |

---

## §1 THE INSTRUMENT FINDING THAT SCOPED THIS PHASE (prereg §2, restated because it is load-bearing)

`E4_worst_setup` and `E3_fmax` on the same G6 build are **different cones**.  A
posedge→negedge arc latches at `0.5 × T` and its slack shrinks twice as fast as
a full-period path's; a `-setup 4` arc's shrinks four times as slowly.  Ranking
cones by raw slack compares different quantities, and this campaign had been
doing exactly that.

`sw/sta_fmax_attrib.tcl` (new) derives each path's latch multiple `M` from that
path's own launch/latch times and reports the frequency at which its own slack
reaches zero.  On the baseline CONTROL build, over 20,000 paths:

| own-Fmax | M | slack | levels | path |
|---:|---:|---:|---:|---|
| **46.59** | 1.00 | 9.785 | 38 | `c_int_q → row_posted` — **and the 12 lowest are all this cone** |
| 57.35 | 1.00 | 13.813 | 12 | `cfg_use_core → rowq[0]` — **the ceiling** |
| 80.36 | **0.50** | **9.403** | 2 | `div_cnt[4] → t1_half2` — **E4's path, and it is not binding Fmax** |

⚠ **The census's "`div_cnt → t1_half2` is the #2 cone in both configurations"
is WITHDRAWN AS A RANKING** (it was taken on raw slack).  The arc is still a
true half period and still may not be relaxed — that part is untouched.

⚠ **The own-Fmax figures are SLOW-1100 mV-100 C only**; G6's Fmax is
multi-corner, so own-Fmax is an upper bound on the reported figure and the two
coincide only when 100 C is the limiting corner.  Baseline: own 46.59 vs
reported 45.54 (another corner limits).  After P2-A: own 45.79 vs reported
45.79 (100 C limits).  **Stated because the two were compared and they are not
the same measurement.**

---

## §2 THE BASELINE, RE-MEASURED IN THIS WORKTREE — BOTH CONFIGURATIONS REPRODUCE

| config | Fmax | worst setup | TNS s/h | ALMs | manifest | receipt |
|---|---:|---:|---|---:|---|---|
| CONTROL | **45.54** | +9.403 | 0.000 / 0.000 | 12,253 | `81d833748e3a1c18…` | `32682e473d4d0453…` |
| RETENTION | **45.57** | +8.868 | 0.000 / 0.000 | 12,213 | `81d833748e3a1c18…` | `576dcee3e56638be…` |

**Both reproduce the committed Phase-1 band to the last digit** (draws 12–15:
45.54 / +9.403 / 12,253 and 45.57 / +8.868 / 12,213), on the same 88-file input
manifest.  That is a third and fourth agreeing draw per configuration.

⚠ The RETENTION receipt records `git 1e554257b6-dirty`.  Its **input manifest is
`81d833748e3a1c18…`, byte-identical to the clean CONTROL build's**, because
`quartus_gate` hashes its inputs *before* the compile; the `dirty` flag is the
git status at receipt-WRITE time, by which point the P2-A edit existed in the
working tree.  **The manifest is the artifact and it says the build is the
baseline's.**

**Per-configuration cone census, baseline:**

| | CONTROL | RETENTION |
|---|---|---|
| INT cone own-Fmax | **46.59** | **46.08** |
| the 12 lowest own-Fmax paths | all `c_int_q` | all `c_int_q` |
| ceiling with `c_int_q` removed | **57.35** (`cfg_use_core → rowq[0]`) | **54.42** (`cfg_use_core → rowq[1]`) |
| endpoints | `row_posted` 200/200 | `row_posted` 109, `rd_done_cnt_n` 91 |

**50 MHz is inside the ceiling in both configurations.  This one cone is the
whole gap** — which is what made the phase worth running, and it remains true.

---

## §3 THE CONE, NODE BY NODE, BEFORE AND AFTER

### 3.1 What the pin does

`c_int_q` has exactly two consumers in the core: `int_p_n`'s shift (a register
`D` pin, inert) and `assign flush_int_live = pin_int`.  **The recognition path
is not involved** — `irq_pin_int = int_p[2]`, `irq_int_lvl`, `intr_pending`'s
arm and the §64.1 one-bit wall are all register-fed, and this phase's diff does
not read any of them.

The live rail enters the BIU's next-state function on that function's **first
statement** (`kill_l = ann_kill`, `v30u_biu.sv:1644`) — and it gets there
through a **display**, `qs_e_now`, whose declared job is `assign qs = qs_e_now ?
QS_EMPTY : …`.

### 3.2 The prefix — **P2-A's registered target, and it MOVED**

| | baseline | **after P2-A** |
|---|---|---|
| the pin's path to the next-state cone | `flush_direct~0` → `flush_direct~1` → `qs_e_now~6` → `qs_e_now~8` → `ann_kill~0` → `ann_kill~1` | **`qs_e_now~0` → `ann_kill~0` → `ann_kill~1`** |
| levels | **6** | **3** |
| ns | 8.197 → 11.448 = **3.251** | 8.212 → 9.525 = **1.313** |
| `flush_direct` in the pin's path | yes, twice | **absent — the transform survived synthesis** |

**T-1 as registered: "≤ 2 logic levels AND ≤ 1.6 ns".  The ns clause is MET
(1.313).  The levels clause is MISSED (3 > 2).  Reported as registered.**

⚠ **R-d is NOT triggered, and the reason is stated rather than assumed.**  R-d
reverts on a T-1 miss *because a miss would mean synthesis re-merged the
branches*.  The netlist falsifies that reading directly: `c_int_q|q` now feeds
`qs_e_now~0` with **no `flush_direct` node anywhere in the pin's cone**, and the
prefix delay **halved**.  The mechanism is not refuted; **R-a is what disposes
of this landing, and it does so on its own terms.**

### 3.3 The tail — **and this is the phase's actual result**

| segment | baseline | after | Δ |
|---|---:|---:|---:|
| `c_int_q` → `ann_kill` (the prefix) | 3.251 | **1.313** | **−1.938** |
| `ann_kill` → endpoint (the tail) | 17.983 | **19.882** | **+1.899** |
| **total data delay** | **21.234** | **21.195** | **−0.039** |
| logic levels | 38 | 38 | 0 |

**THE TAIL ABSORBED 98 % OF WHAT THE HEAD GAVE UP.**  Nothing in the tail's
*logic* changed — the same `Add40`/`Add39` occupancy sum, `pf_arm`,
`rmw_yield`, `cmt_need`, `rq_n`, `cdage`, `LessThan19`, `rq_bs`, `r_rq_data`,
`slot_accept`, `slot_busy`, then the EU.  What changed is **placement**: the
duplicated branches cost **+106 ALMs**, the fitter spread the cone, and the
routing it had been spending on the prefix it now spends on the tail.

**This is a measured mechanism statement, not a hypothesis: the INT cone is
TAIL-limited.  Any further work on its head is worth ≤ 0.04 ns.**

---

## §4 THE BAND — EVERY DRAW TAKEN THIS SITTING

All builds from a clean `db` via `sw/quartus_gate.py`, Quartus 17.1.0 Lite,
5CSEBA6U23I7, `divclk` at 31.250 ns, corner Slow 1100 mV 100 C.

⚠ **Every absolute figure below includes E-1, which the 2026-08-12 Reading-B
ruling slates for removal in a separate wave.  The A/B is like-with-like (both
sides carry E-1), so the DELTA is the quotable quantity and the band is
secondary.**

| # | config | tree | Fmax | worst setup | TNS s/h | ALMs | manifest | receipt |
|---|---|---|---:|---:|---|---:|---|---|
| 1 | CONTROL | baseline `1e554257b6` | **45.54** | +9.403 | 0.000/0.000 | 12,253 | `81d833748e…` | `32682e473d4d0453…` |
| 2 | RETENTION | baseline | **45.57** | +8.868 | 0.000/0.000 | 12,213 | `81d833748e…` | `576dcee3e56638be…` |
| 3 | CONTROL | **P2-A** `c137e8c105`, draw 1 | **45.79** | +7.488 | 0.000/0.000 | **12,359** | `d4ce12a462…` | `9a89e785c6d46e08…` |
| 4 | CONTROL | **P2-A**, draw 2 | **45.79** | +7.488 | 0.000/0.000 | **12,359** | `d4ce12a462…` | `2f91e2ea85c4ad56…` |
| 5 | RETENTION | **P2-A**, **one draw only** (§7.3) | **45.48** | +8.448 | 0.000/0.000 | **12,301** | `d4ce12a462…` | `57b2ae9290861c55…` |

### 4.1 THE BAND, SCORED

| | baseline | **P2-A** | Δ |
|---|---:|---:|---:|
| **CONTROL worst-of-2** | 45.54 | **45.79** | **+0.25** |
| RETENTION (**one draw, not a band**) | 45.57 | **45.48** | **−0.09** |
| CONTROL ALMs | 12,253 | **12,359** | **+106** |
| RETENTION ALMs | 12,213 | **12,301** | +88 |

**The two CONTROL draws are IDENTICAL in Fmax, worst setup and ALMs**, on the
same input manifest `d4ce12a462946205…`.  That is two draws, not closure —
`standing_gates.md` §A governs, and the same tree has drawn 19.42 and 45.91.

⚠ **RETENTION went DOWN.**  P2-A buys +0.25 MHz in one configuration and costs
0.09 in the other, for +106 / +88 ALMs.  **Against R-a's ≥ 1.5 MHz on BOTH,
that is not close, and it is not a measurement that needed a second retention
draw to settle** (§5.2).

⚠ Every `git` field in the P2-A receipts reads `c137e8c105-dirty`.  The dirt is
**untracked build output and receipt appends only** — `hdl/quartus_gate_build.log`,
`sw/testdata/receipts/*.jsonl`, and the two read-only capture symlinks of §6.3.
**No tracked RTL file was modified at any point during these builds**, and the
input manifest `d4ce12a462946205…` is identical across all three.

**Every draw PASSED G6** — 0 errors, 0 latches, 0 `lpm_divide`, every stage
Successful, TNS 0.000 setup **and** hold on every domain, `gen_ucore_qsf
--check` PASS.  **T-6 MET on every draw.**

⚠ **A SECOND AGENT WORKTREE (`agent-a5b17cd304ab29545`) WAS RUNNING ITS OWN
QUARTUS COMPILE CONCURRENTLY** for part of this sitting.  Separate worktree,
separate `db`, separate output tree — it competes for CPU and changes wall
times, and it touches nothing this sitting measured.  Recorded because an
unexplained slowdown in a log is worth a sentence.

---

## §5 THE PRE-REGISTERED BARS, SCORED

**PRIMARY — the cone:**

| id | bar | measured | |
|---|---|---|---|
| **T-1** | prefix ≤ 2 levels **and** ≤ 1.6 ns | **3 levels / 1.313 ns** | **⚠ SPLIT — ns MET, levels MISSED** |
| **T-2** | INT cone data delay ≤ 19.6 ns | **21.195** | **MISSED** |
| **T-3** | INT cone own-Fmax ≥ 50.0 MHz | **45.79** (CONTROL) | **MISSED** |
| **T-8** | ceiling behind the cone still ≥ 57.0 | **54.20** (CONTROL, after) | **MISSED — and see §5.1** |

**SECONDARY — the band (E-1 caveat above):**

| id | bar | measured | |
|---|---|---|---|
| **T-4** | CONTROL worst-of-2 ≥ 47.0, point ≥ 48.5 | **45.79** | **MISSED** |
| **T-5** | RETENTION worst-of-2 ≥ 47.0 | **45.48**, one draw | **MISSED** |
| **T-6** | TNS 0.000 s+h, 0 errors/latches/`lpm_divide`, E1 PASS, every draw | as stated | **MET** |
| **T-7** | ALMs ≤ 12,353 | **12,359** | **MISSED by 6** |

### 5.1 On T-8, and why the miss is not a surprise

T-8 registered "the class behind the cone is unchanged, ≥ 57.0".  It measured
**54.20** on the P2-A CONTROL build — but the baseline RETENTION ceiling was
already **54.42**, so the class (`cfg_use_core → rowq[*]`, 11–13 levels) simply
moved within its own draw-to-draw spread.  **The bar was registered on a
CONTROL-only figure and applied to a tree whose placement moved; it is reported
as a MISS and it establishes nothing about the mechanism.**  Registering a
one-draw figure as a stability bar was a mistake in the pre-registration and is
recorded as one.

### 5.2 THE DISPOSITION — **R-a, applied**

> **R-a** — if **either** configuration's worst-of-2 is not improved by
> **≥ 1.5 MHz** over its baseline, **REVERT**.

CONTROL draw 1 read **45.79**, and a worst-of-2 is the **worse** of two draws,
so CONTROL's worst-of-2 could not exceed 45.79 whatever draw 2 showed —
45.54 + 1.5 = **47.04** was out of reach **arithmetically, from draw 1 alone**.
Draw 2 then reproduced 45.79 exactly, and the RETENTION draw came in at
**45.48, BELOW its baseline**.

| | baseline | P2-A | Δ | R-a needs |
|---|---:|---:|---:|---:|
| CONTROL worst-of-2 | 45.54 | **45.79** | **+0.25** | ≥ +1.5 |
| RETENTION (one draw) | 45.57 | **45.48** | **−0.09** | ≥ +1.5 |

**R-a is MISSED on both configurations.  P2-A IS REVERTED** — `9a0b…` below,
a `git revert` whose result is **byte-identical to `1e554257b6`'s RTL**
(`git diff --cached 1e554257b6 -- hdl/rtl/` is empty).

It is reverted with its mechanism **confirmed** (§3.2) and its benefit
**measured at +0.25 / −0.09 MHz** — one sixth of the registered bar in the good
configuration and negative in the other — for **+106 / +88 ALMs**.  That is
exactly the trade the rule exists to refuse, and the rule was written before the
number was known.

**THE REVERT IS NOT A JUDGEMENT ABOUT THE MECHANISM.**  P2-A does what it says:
the prefix halved and `flush_direct` left the pin's cone. It is reverted because
**the cone is tail-limited and the head is therefore not worth 106 ALMs** — a
fact that did not exist before this sitting measured it.

---

## §6 THE ZERO-BEHAVIOUR-CHANGE LADDER — EVERY ROW MET

Run on the P2-A tree `c137e8c105`, i.e. on the RTL that was built.

| gate | registered | measured | |
|---|---|---|---|
| `sw/timing50_p2a_identity.py` | the transcription is an identity | **8,388,608 assignments / 0 mismatches**; non-vacuity control **4,194,304** | ✓ |
| `check_core --core ucore --opcodes all --cases 0` | 169,000/169,000 | **169,000/169,000** | ✓ |
| `check_core --core ucore --opcodes 8F.0 --cases 0` | 500/500 | **500/500** | ✓ |
| HLT `s10-w0` / `s10-w1` / `s13-w2` / `s13-w3` (`--waits 0/1/2/3`) | 97 · 93 · 45 · 44 = 279/283 | **97 · 93 · 45 · 44 = 279/283** | ✓ |
| `v0.1-w0evt` / `w1evt` / `w2evt` / `w3evt` | 200 / 1,200 / 200 / 1,200 | **200 / 1,200 / 200 / 1,200** | ✓ |
| `ulockstep --golden all --cases 50` | 17,350/17,350 | **17,350/17,350 ALL LOCKSTEP** | ✓ |
| `ghost_launch_law.py score` | 200/200 | **200/200 = 100.0 %** | ✓ |
| **`ie_pinfall_cell core`** | 2,200 cells byte-identical | **2,200 / 2,200 — 0 row-byte differences, 0 scalar columns moved** | ✓ |
| `fz2_replay --all-failures --leg ret` | — | **106 seeds, first-bad-row agreement 106/106 = 100 %** across all 15 ledger families (§6.3 caveat) | ✓ |
| `r7_lint.py` | PASS, 0 violations | **PASS** — 20 nets / 1 carrier / 3 tainted / 51 `stop` sites / 0 violations | ✓ |
| `ss_lint.py --core ucore` | 0x8E / 232 / 220 flops / 0 UNMAPPED | **PASS** — 109×2 BIU + 122×2 EU + tag = **232**, **220** flops, 0 UNMAPPED | ✓ |
| `test_artifact.py` | 45/45 | **45/45** | ✓ |
| `gen_ucore_qsf.py --check` | PASS | **PASS on every build** | ✓ |

### 6.1 The identity is the load-bearing proof, and the ie-pinfall column is its witness

`f(P, x) ≡ P ? f(1, x) : f(0, x)` is an identity, so P2-A cannot change a value
— but a *transcription* can.  `sw/timing50_p2a_identity.py` enumerates all
**8,388,608** assignments of the 23 free variables in `flush_direct`,
`qs_e_now` and `ann_kill`, treating correlated variables as independent so the
proof covers a **superset** of the reachable space, and reports **0
mismatches**.  Its non-vacuity control inverts one literal of the `P = 1` branch
and goes red on **4,194,304**.

The empirical witness is the ie-pinfall directed cell: **2,200 cells, 0
row-byte differences** against this tree's own pre-edit column.

### 6.2 ⚠ ERRATUM — the committed ie-pinfall core column is six landings stale

The brief names *"the ie-pinfall banked replay (2,200 rows byte-identical)"* as
the sharpest behaviour gate.  **On the UNMODIFIED tree it does not reproduce**,
and the cause predates this campaign: `sw/testdata/ie-pinfall/core/table.json`
was written by `c0b7d16898`, and **six RTL landings have shipped since** —
`e57c3b4d12` (KM), `9b28b7cb30`, **`26d0d135cd` (ack-wake)**, `98855f782c`
(phantom-T1), `093efbcfc2` and `292f30bcf8` (the 8F ghost launch law and the
ghost split).

Re-measured at HEAD on a freshly built `tb_sys ret`, **8 of 2,200 cells
differ**, all in the HALT leg (`eihlt_w1` ×1, `eihlt_w2` ×7), and six of them
move exactly `ack` 299→291 / `n_inta` 1→2 / `ack_off` 27→19 /
`ack_off_hlt` 23→15 — an acknowledge eight clocks earlier on a HALT wake, which
is **`ack-wake`'s own mechanism**.

The committed file is a true record of its own tree and was left **byte-
untouched** (measured, then `git checkout`).  This phase's reference is HEAD's
own baseline column, `table.json` sha256
**`963a8065eb94b49c9df03e2ba7e1e7797b3256cac6970cfb5e29f2785c9d46a6`**, and the
gate is before-vs-after **on this tree** — which is what a zero-change edit must
satisfy.

*(The `*.raw.json.gz` shards are not a comparator: `gzip.open` stamps an mtime
into the header, so their bytes move every run regardless of content.  The
per-cell `sha256` inside `table.json` is the row-bytes identity.)*

### 6.3 ⚠ A CORPUS EVENT IN THE MAIN CHECKOUT — `fz2_immaterial falsify` IS OWED, NOT CLAIMED

`fz2_immaterial falsify` **hard-stops** on `fz2c/404049` with `CAPTURE SHA
MISMATCH`, and it is right to.  Swept across the whole ledger:

```
ledger failures: 114    capture sha OK: 0    MISMATCH: 107    missing: 7
```

**Not one** of the 114 captures the `f19` ledger names still hashes to the
ledger's `capture_sha256`.  The 107 present files were rewritten in the main
checkout between **2026-08-12 04:56:25 and 05:05:59 PDT** (11:56–12:06 UTC),
i.e. **after** the ledger's own `2026-08-12T08:04:58Z`, and 7 are absent
altogether.

This worktree reaches that corpus through a **read-only symlink** to the main
checkout (the captures are untracked and live only there), so the event is
inherited, not caused: **nothing in this sitting writes to
`sw/testdata/campaigns/`**, and the rewrite timestamps precede this sitting's
first command.

**CONSEQUENCES, stated rather than worked around:**

* `fz2_immaterial falsify` is **OWED**, not claimed, and may not be reported as
  PASS or FAIL from here.
* `fz2_replay --all-failures` **did** run and reports **106/106** first-bad-row
  agreement — but it scored against the **rewritten** socket rows, so it is a
  true statement about **this corpus snapshot** and not about the `f19` era.
  The snapshot is pinned for anyone re-deriving it: 107 present ledger
  captures, rolling sha256
  **`831179770470fe157615b5ab433a6455173af71c4eb4fc5356eff9d2b49f56ed`**.
* **The behaviour claim does not rest on it.**  The identity proof and the
  2,200-cell ie-pinfall byte-identity are both independent of the fz2 corpus.

---

## §7 WHAT PHASE 2 ESTABLISHES, AND WHAT IT HANDS FORWARD

### 7.1 Established

1. **The INT cone is the Fmax-limiting class in both configurations**, and the
   ceiling behind it is **57.35 MHz (CONTROL) / 54.42 (RETENTION)**.  50 MHz is
   inside that ceiling: the cone is the whole gap.
2. **The cone is TAIL-limited.**  Its head is worth **1.938 ns** and the fitter
   reclaims **1.899** of it.  Measured, both directions, one draw each way, and
   the two agree to 0.04 ns.
3. **An SDC exception on this path is impossible** — the launch is free-running,
   the capture is CE-gated, and under the 2026-08-12 Reading-B ruling no
   constraint anywhere may assume the enable train's shape.  **RTL only.**
4. **A slack is not an Fmax.**  `sw/sta_fmax_attrib.tcl` exists now and the
   campaign should rank cones with it, not with `Setup Summary`.

### 7.2 Handed forward, with the blocking term named

**The 21.2 ns tail, and 50 MHz needs ~1.9 ns of it.**  It partitions as:

| | ns | levels | lever |
|---|---:|---:|---|
| BIU next-state, `ann_kill` → `slot_busy` | ~12.0 | ~23 | no lever registered. It is one procedural `always_comb` and the pin is inside it from statement one. |
| EU, `slot_busy` → `row_posted\|d` | ~5.7 | 12 | **`row_posted_n~1 … ~9` is a nine-deep cascade and it is the twelve-position chain's `stop` ladder.** `CHAIN_MAX` 12 → 7 is the named lever; §51.2 derived depth 6 and *declined* to tighten, m72 §3 re-derived depth 6 on four LFSR seeds and runs 7. **It needs its own pre-registration and it is not taken here.** |

**The honest ceiling statement this phase owes the campaign:**

> **50 MHz is reachable in principle — the non-INT ceiling is 54–57 MHz — but
> not by shortening the INT cone's head.  The remaining ~1.9 ns must come out
> of the 35-level tail, and the only lever with a worked precedent is
> `CHAIN_MAX`, which tightens a bound this tree explicitly chose not to
> tighten and therefore needs its own wave.**

### 7.3 Not done, and named

* `fz2_immaterial falsify` — **owed** (§6.3), on a corpus that must first be
  re-conciled with its ledger. That is a main-checkout question, not this
  worktree's.
* RETENTION worst-of-2 on the P2-A tree — **one draw only** (§4.1). R-a was
  already decided arithmetically by CONTROL draw 1, so the second RETENTION
  draw was not spent. **The retention figure is one draw and is NOT a band.**
* `CHAIN_MAX`, `v30u_ucrom` as an M10K, and the `div_cnt → t1_half2` enable arc
  — all three still booked with their own owners, none touched.
