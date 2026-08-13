# TIMING50 PHASE 2 — THE `c_int_q → row_posted` CONE: CENSUS + PRE-REGISTRATION

**Branch `master`, HEAD `1e554257b6` (the Phase-1 results commit).  ISOLATED
WORKTREE.  OFFLINE ONLY.  NO BOARD, NO FLASH.**  `flash_log.jsonl` untouched,
no socket command issued, no Codex consulted, no nested task spawned.

**This document is committed BEFORE the RTL edit it scores.**  §1–§4 are what
the tree measured before anything moved; §5 is the pre-registration; §6 is the
ladder the edit must leave unmoved.

The Phase-0 census's **§0 CE/CE_HALF PORTABILITY CONTRACT** (user ruling,
2026-08-12) governs every derivation here, verbatim:

> "With respect to ce/ce_half, you are not allowed to make assumptions based on
> how you are currently setting those clock enables. All you can assume is the
> ce and ce_half will not be asserted at the same time and there will be a one
> cycle gap between each assertion."

### ⚠ A SECOND USER RULING LANDED MID-WAVE — **READING B: THE CONTRACT IS UNIVERSAL**

Recorded here because it arrived **while this document was being drafted and
before any edit was made**, so it governs the pre-registration below rather than
being applied to it afterwards.

`timing50_census_2026-08-12.md` §5.2 booked an open question for the user: does
the contract govern only `v30u_* → v30u_*` arcs (the core's portable surface),
or **every** arc the SDC writes?  **The user has ruled: READING B — universal.
No constraint anywhere in the design, rig side included, may assume the enable
train's shape.**  Three consequences, all of which this document obeys:

1. **A-1 is PERMANENTLY WITHDRAWN and E-1's scope is not to be touched.**
   Nothing in this phase goes near either; the diff does not contain
   `nec_test.sdc`.
2. **E-1 ITSELF IS SLATED FOR REMOVAL IN A SEPARATE WAVE** — its tick-gating
   justification is `div`-based and fails under Reading B.  This tree still
   carries E-1 at HEAD.  That is *correct* for this phase's A/B, because both
   sides of every comparison here carry it — **but every absolute Fmax figure in
   this document and its results is quoted with the caveat: "band includes E-1,
   which is pending removal under Reading B."**  Accordingly the
   pre-registration below is **re-ordered**: the **CONE DELTA is the PRIMARY
   figure** and the **absolute band is SECONDARY**, because the delta survives
   E-1's removal and the band does not.
3. **THE SDC ESCAPE HATCH IS CLOSED BY RULING, not by estimate.**  §3.4's
   derivation said an exception on this path is impossible under the contract;
   the ruling makes that a fact rather than a judgement.  **This cone is
   RTL-only.**

---

## §0 HEADLINE — WHAT THE RE-CENSUS FOUND, AND ONE INSTRUMENT DEFECT IT EXPOSED

| | |
|---|---|
| **The baseline REPRODUCES** | CONTROL **45.54 MHz / +9.403 ns / 12,253 ALMs**, 88-file manifest **`81d833748e3a1c18…`**, receipt `32682e473d4d0453…` — identical to the committed draws 12–13 to the last digit. |
| **⚠ G6's E3 AND E4 ARE SET BY DIFFERENT CONES, AND NOTHING SAID SO** | `E4_worst_setup` **9.403** is the `div_cnt → t1_half2` **half-period** arc; `E3_fmax` **45.54** is the **INT cone**, whose slack is **9.785**. A raw slack is not comparable across multicycle classes and the campaign has been ranking cones by one. §2. |
| **The INT cone IS the Fmax-limiting class** | own-Fmax **46.59 MHz**; every one of the 12 lowest own-Fmax paths in the design is `c_int_q → row_posted`. |
| **THE CEILING IS HUGE** | with `c_int_q` removed as a launch register the next class is **57.35 MHz** (`cfg_use_core → rowq[0]`) and everything else is **≥ 80 MHz**. **50 MHz is inside the ceiling; this one cone is the whole gap.** |
| **THE CONE'S ANATOMY IS NOT WHAT §8 OF THE CENSUS ASSUMED** | the live pin does **not** reach the EU through a recognition path at all. It enters the BIU's next-state function **at its very top**, through a **DISPLAY** signal — `flush_int_live → flush_direct → qs_e_now → ann_kill → kill_l` — and then rides the entire `always_comb` to `slot_busy`. §3. |
| **THE INTERVENTION** | **P2-A**: Shannon-factor the live pin out of the `qs_e_now`/`ann_kill` prefix so it selects at the LAST gate instead of the first. A Boolean identity — **zero behaviour change by construction**, not by argument. §5. |
| **⚠ AND ONE GATE IN THE BRIEF IS STALE** | the committed `sw/testdata/ie-pinfall/core/table.json` is a **PRE-`ack-wake`** artifact, six RTL landings old, and is **8 of 2,200 cells away from HEAD**. It is not a byte-identity reference for this tree. §4. |

---

## §1 THE BASELINE, RE-MEASURED IN THIS WORKTREE

`python3 sw/quartus_gate.py`, Quartus 17.1.0 Lite, 5CSEBA6U23I7, corner
**Slow 1100 mV 100 C**, `divclk` at 31.250 ns.

| config | Fmax | worst setup | TNS s/h | ALMs | manifest | receipt |
|---|---:|---:|---|---:|---|---|
| CONTROL (this sitting) | **45.54** | +9.403 | 0.000 / 0.000 | **12,253** | `81d833748e3a1c18…` | `32682e473d4d0453…` |

**It reproduces the committed band exactly** (`timing50_phase1_results_2026-08-12.md`
draws 12–13: 45.54 / +9.403 / 12,253).  The quoted **baseline worst-of-2 is the
committed band — CONTROL 45.54 / RETENTION 45.57** — and this is a third
agreeing CONTROL draw, not a replacement for it.

⚠ `standing_gates.md` §A governs: agreeing draws are draws, not closure.

---

## §2 ⚠ THE INSTRUMENT FINDING — A SLACK IS NOT AN Fmax, AND THIS DESIGN PROVES IT

`nec_test_ucore.sta.rpt` reports, on the SAME build:

```
Setup Summary   divclk   worst slack   9.403     <- div_cnt[4] -> t1_half2
Fmax Summary    divclk   Fmax         45.54 MHz  <- and this is NOT that path
```

A posedge→**negedge** arc latches at `0.5 × T`, so **its slack shrinks twice as
fast as a full-period path's** when the clock speeds up; a `-setup 4` arc's
shrinks four times as slowly.  Ranking cones by raw slack compares different
quantities.

**NEW INSTRUMENT, `sw/sta_fmax_attrib.tcl`** — for every path it derives the
latch multiple `M` from the path's OWN reported launch/latch times (never from
the SDC, never assumed) and prints the frequency at which that path's own slack
reaches zero:

```
slack(T) = slack(T0) − M·(T0 − T)      T_crit = T0 − slack(T0)/M
```

**MEASURED, 20,000 paths, landed CONTROL tree:**

| own-Fmax | M | slack | levels | path |
|---:|---:|---:|---:|---|
| **46.59** | 1.00 | 9.785 | 38 | `c_int_q → v30u_eu\|row_posted` |
| 46.60 … 47.28 | 1.00 | — | 37–39 | **the same cone — all 12 lowest are `c_int_q`** |
| **57.35** | 1.00 | 13.813 | 12 | `hps_axi_slave\|cfg_use_core → v30u_eu\|rowq[0]` |
| 80.36 | **0.50** | **9.403** | 2 | `nec_bus\|div_cnt[4] → v30u_biu\|t1_half2` ← **E4's path** |
| 84.34 | 0.53 | 10.343 | 3 | the JTAG hub |

**THE `t1_half2` ENABLE ARC IS NOT BINDING Fmax AND NEVER WAS** — at `M = 0.5`
its own-Fmax is **80.36 MHz**.  Census §6.6 and Phase-1 §4.3 booked it as "the
#2 cone in both configurations, RTL only"; that ranking was taken on raw slack
and **it is withdrawn here as a ranking, not as a finding** (the arc is still a
true half period and still may not be relaxed — that part is unaffected).

**CONSEQUENCE FOR THE CAMPAIGN, and it is the good kind:** the census's
`c_int_q` scope was right for a reason it did not state, and the **ceiling
behind it is 57.35 MHz**, not the +9.4 the slack table suggested.

---

## §3 THE CONE, NODE BY NODE — AND IT IS NOT A RECOGNITION PATH

`report_timing -detail full_path -from c_int_q`, 38 levels, **data delay
21.234 ns**, slack +9.785.

### 3.1 Where the pin actually goes

`c_int_q` has exactly **two** consumers inside the core (`v30u_eu.sv`):

* `int_p_n = {int_p_n[2:0], pin_int}` — a **register `D` pin**, 1 level, inert;
* `assign flush_int_live = pin_int;` — the **live** rail published to the BIU.

**The recognition path is not involved at all.**  `irq_pin_int = int_p[2]`,
`irq_int_lvl`, `intr_pending`'s arm and the §64.1 one-bit wall are all
REGISTER-fed and carry no live pin.  Nothing this phase proposes goes near
them.

### 3.2 The prefix — six levels, and the first one is a DISPLAY

```
c_int_q|q                          8.197 ns
  -> flush_direct~0 / ~1           8.913 / 9.269      wire flush_direct =
                                                        !flush_stage && !flush_nmi_young
                                                        && !flush_int_live;      (:632)
  -> qs_e_now~6 / ~8              10.046 / 10.782     wire qs_e_now = ...        (:799)
  -> ann_kill~0 / ~1              11.081 / 11.448     wire ann_kill  = ... qs_e_now ... (:510)
                                                       fanout 31
```

**`qs_e_now` IS THE QS-EMPTY DISPLAY** — `assign qs = qs_e_now ? QS_EMPTY : …`,
the queue-status pins.  It re-enters the machine's STATE through exactly one
reader:

```systemverilog
// v30u_biu.sv:510
wire ann_kill = (q_flush || ((eu_susp || eu_post) &&
                             !(r_cmt_was_owed && qs_e_now))) &&
                r_cmt_valid && r_cmt_fetch && (r_cdage == 3'd0);
// ...and :1644, the FIRST statement of the next-state function
kill_l = ann_kill;      qse_l = qs_e_now;
```

`kill_l` is captured at the **top of block (a)** and spent at :1676
(`if (kill_l) cmt_valid = 1'b0;`).  **So the live INT pin is in the block's
state from its first statement**, and rides every subsequent stage.

### 3.3 The tail — where the 21.234 ns is

| segment | ns | levels | what |
|---|---:|---:|---|
| `c_int_q` → `ann_kill` | **3.251** | 6 | the prefix above — **this is what P2-A attacks** |
| `ann_kill` → `slot_busy` | **12.034** | ~23 | the whole BIU next-state: `Add40/Add39` (the eval's `occ` sum) · `pf_arm` · `rmw_yield` · `cmt_valid` · `cmt_noaddr` · `cdage` · `LessThan19` · `rq_bs` · `r_rq_data` · `slot_accept` |
| `slot_busy` → `row_posted\|d` | **5.674** | 12 | the EU: `Selector969~0..2` then **`row_posted_n~1 … ~9`**, a nine-deep cascade — the twelve-position chain's `stop` mux ladder |
| **total** | **21.234** | 38 | |

**`slot_busy` is `eu_slot_busy_n`**, one of `r7_lint`'s two DECLARED UNRESOLVED
procedural carriers, and the EU reads it at `S_PRERD` — a position-0-only arm
(`st_zero_ok` excludes `S_PRERD`), which is why the pin does not release chain
positions and why `r7_lint` is green.

### 3.4 What this rules OUT, before it is proposed

* **An SDC exception is impossible under the contract.**  The launch (`c_int_q`)
  is free-running on the fabric clock; the capture is `ce`-gated.  C-b bounds
  the gap between two *assertions* and says nothing about where an assertion
  sits relative to a pin change, so the guaranteed window is **1 period**.  The
  Phase-0 §5.1 derivation applies unchanged.
* **Re-piping the pin is a behaviour change.**  `int_p[0]` is the pin at `c−1`;
  `flush_int_live` is the pin at `c`.  The BIU reads it on two ADJACENT clocks
  (`flush_pre` one row early, `q_flush` on the flush row), so a stage shift
  moves both reads.  Not proposed.
* **A second `system_large` pipe stage is a behaviour change.**  `c_int_q` exists
  to hand the core the pre-edge value at its sampling edge; another stage delays
  the pin by one fabric clock relative to the chip.  Not proposed.
* **`CHAIN_MAX` 12 → 7 is worth ~5 of the 9 `row_posted_n~*` levels** and is
  **NOT taken here**: §51.2 explicitly declined to tighten that bound and
  Phase-1 §8 books it as needing its own pre-registration.  Named so the
  remaining headroom is visible, not claimed.

---

## §4 ⚠ AN ERRATUM AGAINST THE BRIEF'S SHARPEST GATE — THE ie-pinfall CORE COLUMN IS STALE

The brief names *"the ie-pinfall banked replay (2,200 rows byte-identical)"* as
the sharpest behaviour gate.  **Run on the UNMODIFIED tree it does not
reproduce**, and the reason is not this campaign's:

* the committed `sw/testdata/ie-pinfall/core/table.json` was written by
  `c0b7d16898` (the cell's own pre-registration);
* **six RTL landings have shipped since** — `e57c3b4d12` (KM), `9b28b7cb30`,
  **`26d0d135cd` (ack-wake — "a WITHDRAWN announcement is RELEASED on its own
  clock")**, `98855f782c` (phantom-T1), `093efbcfc2` and `292f30bcf8` (the 8F
  ghost launch law and the ghost split);
* re-measured at HEAD on a freshly built `tb_sys ret`, **8 of 2,200 cells
  differ**, all in the HALT leg (`eihlt_w1` ×1, `eihlt_w2` ×7), and **6 of them
  move exactly `ack` 299→291, `n_inta` 1→2, `ack_off` 27→19,
  `ack_off_hlt` 23→15** — an acknowledge arriving 8 clocks earlier on a HALT
  wake, which is `ack-wake`'s own mechanism.

**DISPOSITION.**  The committed file is a true record of ITS tree and is left
byte-untouched (`git checkout` after the measurement; the working tree is
clean).  **This phase's behaviour reference is HEAD's own baseline column**,
measured before the edit and retained outside the repo:

```
ie-pinfall core @ 1e554257b6 :  2,200 cells,  table.json sha256
    963a8065eb94b49c9df03e2ba7e1e7797b3256cac6970cfb5e29f2785c9d46a6
```

The gate is **before-vs-after ON THIS TREE**, which is what a zero-change edit
must satisfy; comparing against a six-landing-old column would have reported a
failure this phase did not cause, and reporting one would have been false.

(The `*.raw.json.gz` shards are **not** a comparator: `gzip.open` stamps an
mtime into the header, so their bytes move on every run regardless of content.
The per-cell `sha256` field inside `table.json` is the row-bytes identity and
is what is compared.)

---

## §5 THE PRE-REGISTRATION — **P2-A, THE LATE-PIN FACTORING**

### 5.1 The edit, exactly

**ONE Boolean identity, applied at ONE place: `f(P, x) ≡ P ? f(1, x) : f(0, x)`.**

`flush_int_live` (call it `P`) reaches `ann_kill` through four gate levels of
`flush_direct` and `qs_e_now`.  Both are evaluated at each of `P`'s two values —
each branch is **pin-free**, so each is launched from core registers and covered
by the 4-period CE multicycle — and `P` selects between them at the **last**
gate:

```systemverilog
wire fd_nopin      = !flush_stage && !flush_nmi_young;   // flush_direct with P = 0
wire flush_direct  = fd_nopin && !flush_int_live;        // unchanged in VALUE

wire qs_e_now_p1   = <qs_e_now with flush_direct := 0, flush_src_live := 1>;
wire qs_e_now_p0   = <qs_e_now with flush_direct := fd_nopin,
                                    flush_src_live := flush_nmi>;
wire qs_e_now      = flush_int_live ? qs_e_now_p1 : qs_e_now_p0;

wire ann_kill_p1   = <ann_kill with qs_e_now := qs_e_now_p1>;
wire ann_kill_p0   = <ann_kill with qs_e_now := qs_e_now_p0>;
wire ann_kill      = flush_int_live ? ann_kill_p1 : ann_kill_p0;
```

**Nothing else moves.**  `flush_src_live`, `flush_staged_eval`, `flush_fast`
and the `e_pend` site at :1875 already have `P` within one gate of their own
consumer and are left alone.  No flop is added or removed; no save-state
address; no signal changes meaning; no opcode is named.

**WHY IT IS ZERO-BEHAVIOUR BY CONSTRUCTION, not by argument.**  Shannon
expansion is an identity over the two-valued domain of `P`.  The ladder in §6 is
the empirical check on the transcription, not on the identity.

**WHY IT IS THE R7′ SHAPE.**  R7′ closed the live `READY` pin by moving its one
consumer off the head of a cone onto a register's own `D` pin, gated by
register-only terms — *"one mux"*.  This moves the live `INT` pin off the head
of the BIU's next-state cone onto the last gate of its own prefix, with both
branches register-only.  Same disease, same medicine, same cost.

### 5.2 The registered predictions

**PRIMARY — the CONE, which survives E-1's removal:**

| id | prediction | bar |
|---|---|---|
| **T-1** | the pin's prefix — `c_int_q` → its first fanout into the next-state cone — **shrinks** | **≤ 2 logic levels and ≤ 1.6 ns**, from 6 levels / 3.251 ns |
| **T-2** | the INT cone's **data delay** falls | **≤ 19.6 ns**, from 21.234 |
| **T-3** | the INT cone's **own-Fmax** rises | **≥ 50.0 MHz**, from 46.59 |
| **T-8** | the class behind the cone is unchanged | after the edit, the lowest own-Fmax NOT launched by `c_int_q` is still **≥ 57.0 MHz** |

**SECONDARY — the absolute band.  ⚠ Every figure below includes E-1, which is
pending removal under Reading B, and will move when that wave lands:**

| id | prediction | bar |
|---|---|---|
| **T-4** | **CONTROL worst-of-2 Fmax** | **≥ 47.0 MHz** (the phase bar), point prediction **≥ 48.5** |
| **T-5** | **RETENTION worst-of-2 Fmax** | **≥ 47.0 MHz** (the phase bar) |
| **T-6** | TNS **0.000 setup AND hold** on every domain, 0 errors, 0 latches, 0 `lpm_divide`, `gen_ucore_qsf --check` PASS, on **every** draw | as stated |
| **T-7** | ALMs | **≤ 12,353** (+100 on 12,253) |

The A/B is like-with-like: **both sides carry E-1**, so R-a's ≥ 1.5 MHz
improvement is a property of the edit and not of the constraint set.

**REVERT RULES, registered before the build:**

* **R-a** — if **either** configuration's worst-of-2 is not improved by
  **≥ 1.5 MHz** over its baseline (CONTROL 45.54, RETENTION 45.57), **REVERT**.
* **R-b** — **any** delta on the §6 ladder, **REVERT**. A zero-behaviour edit
  that moves a gate is not a transcription error to be patched, it is a refuted
  claim.
* **R-c** — non-zero hold TNS on any domain, **REVERT**.
* **R-d** — if **T-1 is MISSED** the transform did not survive synthesis
  (Quartus re-merged the branches). That is a REFUTATION of the mechanism, not
  a tuning opportunity: it is reported as a miss and the landing reverts even if
  T-4/T-5 happen to pass, because a band that moved for an unexplained reason is
  `§74.4`'s problem, not a result.

**WHAT MAY NOT BE CLAIMED.**  `standing_gates.md` §A governs: **worst-of-2 from
a clean `db` per configuration, both draws printed**, and one green build is not
closure — the same tree has drawn 19.42 and 45.91 MHz.

---

## §6 THE ZERO-BEHAVIOUR-CHANGE LADDER

Unlike Phase 1, this edit is **RTL that every engine reads**, so the ladder runs
in full, once, on the landed tree.

| gate | registered value |
|---|---|
| `check_core --core ucore --opcodes all --cases 0` | **169,000/169,000** |
| `check_core --core ucore --opcodes 8F.0 --cases 0` | **500/500** |
| HLT sweeps `s10-w0/w1`, `s13-w2/w3` (⚠ **`--waits 0/1/2/3`**) | 97 · 93 · 45 · 44 = **279/283** |
| the four `evt` cells `v0.1-w{0,1,2,3}evt` | **200 / 1,200 / 200 / 1,200** |
| `ulockstep --golden all --cases 50` | **17,350/17,350, ALL LOCKSTEP** |
| `ghost_launch_law.py score` | **200/200**, exit 0 |
| **`ie_pinfall_cell core`** | **2,200 cells, `table.json` sha256 `963a8065eb94b49c…` — BYTE-IDENTICAL to HEAD's own baseline (§4)** |
| `fz2_replay` (the 106-seed leg) | **byte-identical**, era override stated |
| `fz2_immaterial falsify` | **PASS G1–G8** |
| `r7_lint.py` | **PASS** — 20 nets / 1 carrier / 3 tainted / 51 `stop` sites / 0 violations |
| `ss_lint.py --core ucore` | **PASS** — `SS_VERSION` **0x8E** / `SS_COUNT` **232** / `SS_TAG` **0x8EE8** / **220** flops / 0 UNMAPPED (**no flop is expected and none is registered**) |
| `test_artifact.py` | **45/45** |
| `gen_ucore_qsf.py --check` | **PASS** (it is G6's E1) |

All twelve were measured GREEN on the unmodified tree in this worktree before
the edit, except the four that need a run to be quoted; `r7_lint`, `ss_lint` and
`test_artifact` are already confirmed at HEAD here
(PASS 20/1/3/51/0 · PASS 232/220 · 45/45).

---

## §7 WHAT PHASE 2 DOES **NOT** DO

* It does not touch `int_p`, `nmi_p`, `ie_p`, `intr_pending`, `irq_int_lvl`,
  `brk_*` or any recognition predicate. The §64.1 one-bit wall is not read, not
  moved and not mentioned by the diff.
* It does not touch `nec_test.sdc`. No new exception is derived, so §0's
  contract has nothing to rule on.
* It does not touch `CHAIN_MAX`, `v30u_ucrom`, or the `div_cnt → t1_half2`
  enable arc. Each is booked with its own owner in Phase-1 §8 and each needs its
  own pre-registration.
* It takes no board action of any kind.
