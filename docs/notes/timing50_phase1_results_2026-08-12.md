# TIMING50 PHASE 1 — RESULTS

**Branch `master`.  Census + pre-registration `6eee1c0b67`
(`timing50_census_2026-08-12.md`), committed BEFORE any edit here; the edits at
`f17102066f`, committed BEFORE every build that scores them.**
**OFFLINE ONLY.  NO BOARD, NO FLASH.**  `flash_log.jsonl` untouched, no socket
command issued, no Codex consulted, no nested task spawned.

The census's §0 records the **CE/CE_HALF portability contract** (user ruling,
2026-08-12) verbatim.  It governs every derivation here.

---

## §0 HEADLINE

| | |
|---|---|
| **The band did not reach 50 MHz, and the census said so before Phase 1 ran** | CONTROL **45.61 → 45.54**, RETENTION **44.32 → 45.57**, worst-of-2, all pairs identical |
| **What Phase 1 actually delivered** | **a CORRECTNESS FIX the ruling exposed**: the SDC's uniform CE multicycle was **optimistic by two full periods** on the one `ce_half`-gated flop. It is landed, and it costs **0.07 MHz**. |
| **P-1 (SignalTap)** | **LANDED as policy. Measured effect on the bitstream: ZERO — byte-identical `.rbf`.** |
| **P-2 (E-1 `-setup 3`)** | **WITHDRAWN by the ruling**, not scored, not built. |
| **P-3 (the CE-phase split)** | **LANDED. Bar MET** — cost **0.07 MHz** against a < 0.50 bar. |
| **A-1 (E-1's `-from` scoping)** | **BUILT, MEASURED AT −2.41 MHz, AND WITHDRAWN** — it took a decision §5.2 of the census explicitly reserved for the user. |
| **Zero-behaviour-change ladder** | **every row MET** (§5) |
| **Phase-2 recommendation** | **GO, on `c_int_q → row_posted`** — it is the binding cone in both configurations and it is RTL, not SDC (§6) |

---

## §1 THE THREE ITEMS, AS DISPOSITIONED

| item | brief's form | **as landed** |
|---|---|---|
| **1** | SignalTap OFF for G6/flash, behind a flag for board debug | **LANDED as POLICY** — measured at **exactly zero** effect on the bitstream (§3) |
| **2** | E-1 observation multicycle `-setup 2` → `-setup 3` | **WITHDRAWN by the ruling** — its premise was `div/2 − 1`; under the contract the guaranteed window is **1 period** (census §5) |
| **3** | "the negedge modelling correction" | **BECAME A CORRECTNESS FIX, and it is the sitting's real result** (§4) |

---

## §2 EVERY DRAW TAKEN THIS SITTING

All builds from a clean `db` via `sw/quartus_gate.py`, Quartus 17.1.0 Lite,
`divclk` at 31.250 ns (32.0 MHz), corner Slow 1100 mV 100 C.

| # | configuration | tree | Fmax | worst setup | TNS s/h | ALMs | receipt |
|---|---|---|---:|---:|---|---:|---|
| 1 | CONTROL | HEAD `82d7561c4b` | **45.61** | +8.892 | 0.000/0.000 | 12,282 | `c0610ca34053a9d3…` |
| 2 | RETENTION | HEAD | **44.32** | +8.689 | 0.000/0.000 | 12,245 | `15a901c4cce28c69…` |
| 3 | CONTROL | HEAD, **SignalTap stripped** (scratch, reverted) | **45.61** | +8.892 | 0.000/0.000 | 12,282 | `1820d66c0f23f784…` |
| 4 | CONTROL | P-1 + P-3 + **A-1**, draw 1 | 43.13 | +8.063 | 0.000/0.000 | 12,279 | `367175a449d25792…` |
| 5 | CONTROL | P-1 + P-3 + **A-1**, draw 2 | 43.13 | +8.063 | 0.000/0.000 | 12,279 | `85ee837bc4e3daa1…` |
| 6 | RETENTION | P-1 + P-3 + **A-1**, draw 1 | 42.88 | +7.928 | 0.000/0.000 | 12,225 | `26e0842e126f31e2…` |
| 7 | RETENTION | P-1 + P-3 + **A-1**, draw 2 | 42.88 | +7.928 | 0.000/0.000 | 12,225 | `af003a588ae02d01…` |
| **8** | **CONTROL** | **P-1 + P-3, A-1 withdrawn — THE LANDED TREE**, draw 1 | **45.54** | +9.403 | 0.000/0.000 | **12,253** | `cc878e4019cbdcd3…` |
| **9** | **CONTROL** | **THE LANDED TREE**, draw 2 | **45.54** | +9.403 | 0.000/0.000 | **12,253** | `e01e03ee28109e0e…` |
| **10** | **RETENTION** | **THE LANDED TREE**, draw 1 | **45.57** | +8.868 | 0.000/0.000 | **12,213** | `428ae804577cabf8…` |
| **11** | **RETENTION** | **THE LANDED TREE**, draw 2 | **45.57** | +8.868 | 0.000/0.000 | **12,213** | `60d6bf83dc6da055…` |
| **12** | **CONTROL** | **THE COMMITTED TREE** (CRLF-corrected), draw 1 | **45.54** | +9.403 | 0.000/0.000 | **12,253** | `4ae475f76b890cef…` |
| **13** | **CONTROL** | **THE COMMITTED TREE**, draw 2 | **45.54** | +9.403 | 0.000/0.000 | **12,253** | `0748dbeb61450a41…` |
| **14** | **RETENTION** | **THE COMMITTED TREE**, draw 1 | **45.57** | +8.868 | 0.000/0.000 | **12,213** | `6341372c8768247a…` |
| **15** | **RETENTION** | **THE COMMITTED TREE**, draw 2 | **45.57** | +8.868 | 0.000/0.000 | **12,213** | `12350cc8bbf9e46b…` |

**Every draw PASSED G6** — 0 errors, 0 latches, 0 `lpm_divide`, every stage
Successful, TNS 0.000 setup **and** hold on every domain.  **Every pair of draws
was identical in Fmax, worst setup and ALMs.**

### 2.0 ⚠ ERRATUM E-1 — DRAWS 4-9 WERE TAKEN ON AN LF-NORMALISED `.qsf`

`hdl/nec_test.qsf` has **CRLF** line terminators (it is MiSTer's file).  The
Python edit that removed the SignalTap lines rewrote the whole file with **LF**,
so draws 4-9 were taken on a `.qsf` that differs from the committed one **in
every line terminator and in nothing else**.  Draws 1-3 were taken on the
original CRLF file, and draws 10-11 were re-taken on the corrected one.

**IT CANNOT HAVE CHANGED A BUILD, AND THAT IS NOW MEASURED RATHER THAN
ARGUED.**  Draws **12-15** re-take both pairs on the committed CRLF tree
(input manifest `81d833748e3a1c18…`) and reproduce draws 8-11 **exactly** —
45.54 / +9.403 / 12,253 and 45.57 / +8.868 / 12,213, to the last digit in
every figure.  Quartus's settings parser is line-ending-agnostic and the
four draws say so.

**BUT IT DOES CHANGE `input_manifest`,** which hashes bytes — so a receipt from
draws 4-9 will not match a rebuild of the committed tree, and that is the whole
point of the manifest.  **The line endings are restored** (the file's diff
against `master` is now the intended 3 removed + 28 added lines and nothing
else), and **the quoted band is draws 12-15, taken on the committed tree**,
not inherited from draws 8-11.  Stated rather than hidden; the attribution figures in §7.2 are
deltas between builds and are unaffected either way.

⚠ **`standing_gates.md` §A governs**: identical pairs are two draws, not
closure.  The same tree has drawn 19.42 and 45.91 MHz.

### 2.1 THE LANDED BAND

| | before (HEAD) | **after (landed)** | Δ |
|---|---:|---:|---:|
| CONTROL worst-of-2 | 45.61 | **45.54** | **−0.07** |
| RETENTION worst-of-2 | 44.32 | **45.57** | **+1.25** |

**Against the campaign target of 50.0 MHz: NOT MET, and not close.**  The gap
is ~2 ns of slack and it is the same gap the census named before Phase 1 ran.

⚠ **RECORDED, NOT EXPLAINED: RETENTION GAINED 1.25 MHz FROM A TIGHTENING.**
P-3 removes budget; it cannot make a path faster.  The band moved because the
fitter's allocation moved — and on the landed tree **RETENTION (45.57) is now
ABOVE CONTROL (45.54)**, the sign inversion this repo has recorded and declined
to explain several times (`standing_gates.md` §A; FLASH #13's +0.46, FLASH
#14's 40.97 above every CONTROL draw of its branch).  ALMs fell in both
configurations (12,282 → 12,253 and 12,245 → 12,213).  **Reported as measured;
§74.4 governs — the same tree has drawn 19.42 and 45.91 MHz.**

---

## §3 P-1 — THE SIGNALTAP POLICY: **LANDED, AND WORTH EXACTLY ZERO**

**Bar**: CONTROL worst-of-2 ≥ 45.61 **and** ALMs ≤ 12,282.  **MET** (draw 3:
45.61, 12,282 — equal on both).

**The measurement** (census §3.4, predictions S-1/S-2/S-3 registered before the
draw): stripping `ENABLE_SIGNALTAP` / `USE_SIGNALTAP_FILE` / `SIGNALTAP_FILE`
changed **nothing** — Fmax, worst setup, ALMs and all four class worsts
identical, and **`nec_test_ucore.rbf` BYTE-IDENTICAL at `277e7de5f8fcfcde…`**.

**All three predictions MET, including S-1**: `sld_mod_ram_rom →
sld_jtag_hub|tdo` **survives** the strip, because the hub is the In-System
Memory Content Editor's — three `ENABLE_RUNTIME_MOD` `lpm_hint`s in
`capture_buf.sv` and `test_mem.sv` — and not SignalTap's.

### 3.1 ⚠ THE CONSEQUENCE, STATED PLAINLY FOR THE USER

The brief asked for this to be stated explicitly, and the measurement makes it
short: **no debug capability is given up, because there was none.**

* `hdl/stp1.stp` **has never existed in this repository** — `git log --all` on
  that path and on `*.stp` are both empty.  The `.qsf` named an instance file
  that was never there.
* The bitstream is byte-identical with and without the setting.
* **`sw/dump_capture.tcl` and the In-System Memory Content Editor are
  UNAFFECTED** — that path is `ENABLE_RUNTIME_MOD`'s and survives.
* To build with SignalTap: **`python3 sw/quartus_gate.py --signaltap`**, which
  appends the three assignments to the revision `.qsf` after E1 and before the
  compile, and records what it added in the receipt.  It will also need an
  `stp1.stp`.

**It may not be quoted as a timing result of any size.**

### 3.2 Why the lines came out of `hdl/nec_test.qsf` and not the ucore revision

`gen_ucore_qsf.py --check` (G6's E1) gates that `nec_test_ucore.qsf` is a
faithful derivative of `nec_test.qsf`.  Removing the lines from the ucore
revision alone would fail that gate **by construction**, and would make the A/B
bitstreams differ by the **debug fabric** as well as by the core — precisely
what E1 exists to prevent.  Both revisions therefore lose them together.
`gen_ucore_qsf --check` **PASS**; `sw/test_quartus_gate.py` **75/75 PASS**.

---

## §4 P-3 — THE CE-PHASE SPLIT: **THE SITTING'S REAL RESULT**

**Bar**: CONTROL worst-of-2 ≥ 45.11 MHz (cost < 0.50) **and** setup *and* hold
TNS 0.000 on every domain.

**MEASURED: 45.54 MHz, twice.  COST 0.07 MHz.  TNS 0.000 setup and hold.
BOTH CLAUSES MET, and the point prediction ("≤ 0.1 MHz cost") was right.**

### 4.1 What was wrong

`hdl/nec_test.sdc` applied `-setup 4 -hold 3` to **all** `v30u_*` registers
uniformly.  The core has **two enable phases**: 1,976 `ce`-gated posedge flops
and **one** `ce_half`-gated **negedge** flop, `v30u_biu|t1_half2` — the only
synthesised negedge flop in the design (10 `negedge` lines over all 88 declared
build inputs; 8 are comments, async resets, or inside
`system_large.sv`'s `` `ifndef SYNTHESIS ``).  It sat in **both** the `-from`
and the `-to` collection.

Derived from the contract's premises alone:

| arc | true distance | was | **is** |
|---|---:|---|---|
| `ce → ce` | 4.0 periods | `-setup 4` | `-setup 4` (unchanged) |
| `ce → ce_half` (into `t1_half2`) | **1.5** | `-setup 4` = 3.5 ❌ | **`-setup 2` = 1.5** ✓ |
| `ce_half → ce` (out of `t1_half2`) | **2.5** | `-setup 4` = 3.5 ❌ | **`-setup 3` = 2.5** ✓ |

**MEASURED by `sw/sta_negedge_probe.tcl`, in both configurations, before and
after** — the analyser's arithmetic, not this document's:

```
                                          BEFORE            AFTER
  dest clock inverted (negedge)          :      1                1
  setup multicycle start/end             :  1 / 4            1 / 2
  latch time                             : 109.375 ns       46.875 ns
                                           = 3.5 x 31.250    = 1.5 x 31.250
```

**The contract warrants 46.875 ns.  The constraint was optimistic by two full
periods**, and by one on the way back out.

**NO STANDING GATE COULD SEE IT.**  `r7_lint` does not model timing exceptions,
Verilator does not see them, and G6 *believes* the SDC.  It became visible only
because the ruling forced the arc to be re-derived from premises that exclude
this rig's divider.

### 4.2 `ce → ce` is still ≥ 4, and that is DERIVED

`ce_half` is the CPU clock's **half-cycle marker**; the only thing it enables
is `t1_half2`, which gates `ad_oe_data`, so with no `ce_half` between two `ce`s
the BIU drives the wrong thing on AD for a whole bus cycle.  **The core
therefore requires ≥ 1 `ce_half` between consecutive `ce`s** — a correctness
requirement of the core, not a scheduling preference of a platform — and with
the contract's ≥ 2 spacing that forces `ce → ce ≥ 4`.

**STRICT ALTERNATION IS NOT ASSUMED**: extra `ce_half`s in a gap are harmless,
`t1_half2`'s update being idempotent.  **The falsifier is FUNCTIONAL, not a
timing one**: a platform issuing two `ce`s with no `ce_half` between has already
broken the core, so this premise is no weaker than the core's own operating
requirement.  Census §6.4 sizes what it is worth: roughly **20 ns of budget**,
corroborated by m72's independently measured **−13.756 ns** on the same cone at
a 2-period budget.

### 4.3 The arc that is deliberately left alone

`nec_bus|div_cnt[*] → t1_half2` reaches that flop **only** through `ce_half` at
its **enable pin**, never in its data cone, and an enable must be valid at the
negedge inside the cycle it is asserted — a **true half period**, exactly the
default, measured at `setup_end_multicycle = 1`.  A relaxation there would be a
false **pass**, the dangerous direction.  It is the **#2 cone in both
configurations** and it is an **RTL** problem (§6).

---

## §5 THE ZERO-BEHAVIOUR-CHANGE LADDER — **EVERY ROW MET**

Run once at the end of Phase 1, as registered (census §7.0), against the
`f17102066f` tree.

| gate | registered | measured | |
|---|---|---|---|
| `check_core --core ucore --opcodes all --cases 0` | 169,000/169,000 | **169,000/169,000** | ✓ |
| `check_core --core ucore --opcodes 8F.0 --cases 0` | 500/500 | **500/500** | ✓ |
| HLT sweep `s10-w0` (`--waits 0`) | 97/97 | **97/97** | ✓ |
| HLT sweep `s10-w1` (`--waits 1`) | 93/95 | **93/95** | ✓ |
| HLT sweep `s13-w2` (`--waits 2`) | 45/46 | **45/46** | ✓ |
| HLT sweep `s13-w3` (`--waits 3`) | 44/45 | **44/45** | ✓ |
| **HLT total** | **279/283** | **279/283** | ✓ |
| `ulockstep --golden all --cases 50` | 17,350/17,350 | **17,350/17,350 ALL LOCKSTEP** | ✓ |
| `ghost_launch_law.py score` | 200/200, exit 0 | **200/200 = 100.0 %** | ✓ |
| `r7_lint.py` | PASS, 0 violations | **PASS** — 0 undeclared carriers, 0 undeclared unresolved, 0 `stop` sites | ✓ |
| `ss_lint.py --core ucore` | 0x8E / 232 / 220 flops / 0 UNMAPPED | **PASS** — 109×2 BIU + 122×2 EU + tag = **232**, **220** flops, **0 UNMAPPED** | ✓ |
| `test_artifact.py` | 45/45 | **45/45** | ✓ |
| `gen_ucore_qsf.py --check` | PASS | **PASS** on every build (it is G6's E1) | ✓ |

**No engine reads `hdl/nec_test.sdc`**, so this was expected by construction —
which is exactly why it was run rather than asserted.

⚠ **`fz2_replay`, `fz2_immaterial falsify` and every leg reading
`sw/testdata/campaigns/fz2*/captures/` COULD NOT RUN** — that corpus is
untracked and lives only in the main checkout, so an isolated worktree has
never had it.  **Owed, not claimed**, exactly as
`timing_recovery_results_2026-08-11.md` §4 booked them.  Nothing in this
sitting changes a byte any of them reads.

---

## §6 THE CENSUS RE-RUN — WHICH CONES DIED, WHICH NOW BIND

`sw/sta_census.tcl` on the **P-1 + P-3 + A-1** retention build.  ⚠ **THAT IS
NOT THE LANDED TREE** — it is the most constrained tree this sitting built, and
it is quoted here because it is where the movement is largest and therefore
most readable.  The landed tree keeps P-3 and drops A-1, so its `CORE→ANY` row
returns to E-1's coverage; **the binding class is the same in both**, which is
the point the table makes:

| class | HEAD | **after** | what happened |
|---|---:|---:|---|
| `CORE→CORE` | +36.355 (`upc_opc[7] → r_kind[0]`) | **+26.976** (`upc_opc[5] → t1_half2`) | **P-3's arc became the core's worst** — as predicted (~+26.5 from +89.958). **Still not binding.** |
| `CORE→ANY` | +25.579 (`upc_opc[7] → ad_in_q[7]`) | **+10.413** (`t1_half2 → ad_in_q[0]`) | **A-1's arc.** Still not binding. |
| `ANY→CORE` | +8.689 (`c_int_q → row_posted`) | **+7.928** (`c_int_q → rd_done_cnt_n` / `row_posted`) | **binds, before and after** |
| top-60 population | `OUT→CORE` 60/60 | **`OUT→CORE` 60/60**, launch `system_large` 60, latch `v30u_eu` 60 | unchanged in kind |

**THE DECISIVE READING: NEITHER TIGHTENED ARC BINDS.**  The binding path is
`c_int_q → v30u_eu`, before and after, and it moved by **−0.761 ns** — which no
constraint in this sitting touches.  **The Fmax cost is fitter pressure**: two
previously-slack arcs now demand real effort, and the INT cone gave up 0.76 ns
of routing to pay for it.  That is a placement effect, not a violated
constraint, and it is why the cost is small for P-3 and large for A-1.

**WHAT NOW BINDS, in one line: `system_large|c_int_q → v30u_eu|row_posted` /
`rd_done_cnt_n`, 46–48 logic levels, ANY→CORE, single-cycle, and it owns 60 of
the top 60 paths in RETENTION and 48 of 60 in CONTROL.**

---

## §7 A-1 — BUILT, MEASURED, **WITHDRAWN**, AND BOOKED AS A USER DECISION

### 7.1 What A-1 was

E-1's `-from` collection was also `$v30u_regs`, so E-1's 2-period relaxation
reached `t1_half2` as well — and `t1_half2` does reach the observation
registers, through `ad_oe_data` → `ad_o` → the pads → `ad_in_q`.  A-1 scoped
that `-from` to `$v30u_ce`.

### 7.2 THE SPLIT — because a bundle's cost is not evidence for any member of it

`standing_gates.md`'s own precedent is *"a bundle's benefit is not evidence for
any member of it"*, and the same is true of a bundle's cost.  Two extra CONTROL
draws were taken with **A-1 reverted and P-3 kept**:

| tree | CONTROL worst-of-2 | worst setup | ALMs | **attributed cost** |
|---|---:|---:|---:|---:|
| HEAD | 45.61 | +8.892 | 12,282 | — |
| **P-3 only** | **45.54** | +9.403 | 12,253 | **P-3: −0.07 MHz** |
| P-3 + A-1 | 43.13 | +8.063 | 12,279 | **A-1: −2.41 MHz** |

**A-1 owns 2.41 of the 2.48 MHz.**  Without the split, P-3 — a genuine
correctness fix — would have been reported as costing 2.48 MHz, and that would
have been false.

### 7.3 Why it is WITHDRAWN

**Because it takes a decision the census explicitly reserved for the user.**
`timing50_census_2026-08-12.md` §5.2 wrote, before any of this was built:

> **This document does not change E-1.**  It is landed, it is fabric-confirmed
> (`c59c2caf30`, FLASH #19) … and reverting a fabric-confirmed constraint on a
> reading of a ruling would be the campaign making a decision that is the
> user's.

**A-1 changes E-1.**  It narrows the exception's `-from`.  That is inconsistent
with the position this campaign had already taken, and the split is what made
the inconsistency visible by putting a price on it.

**And the underlying question is genuinely open, in both directions:**

* **Strict reading** (the contract governs every arc): `t1_half2 → obs` gets
  **0.5** periods, and E-1's `-setup 2` is **optimistic**.  A-1 is right.
* **Rig-local reading** (the contract governs the core's portable surface;
  `nec_bus` *is* the CE generator and is not shipped downstream): on this rig's
  divider that arc has **3.5** periods available — a `ce_half` write at `E3.5`
  is not read by the `E4` `tick_fall` consumer at all (that one reads the
  sample written at `E3`) but by the `E8` `tick_rise` one, reading the sample
  written at `E7`.  E-1's `-setup 2` is **conservative**.  A-1 is over-tight by
  three periods.

**The two readings differ by 2.41 MHz.**  The SDC now carries this measurement
and the derivation beside the exception, with the exact one-line change needed
to take A-1 if the user rules the strict reading applies.

---

## §8 PHASE-2 RECOMMENDATION — **GO**, on one named cone

**Phase 1 could not reach 50 MHz and the census said so in advance.**  The
landed band is CONTROL 45.54 / RETENTION 45.57 against a 50.0
target; the gap is ~2 ns of slack.

**RECOMMENDATION: GO for Phase 2, scoped to `c_int_q → v30u_eu|row_posted` /
`rd_done_cnt_n`, and to nothing else in the first wave.**  It is the binding
cone in **both** configurations, it owns 60 of RETENTION's top 60, and it is
**structurally the same class R7′ closed on `READY`** — a live pin carrier
crossing single-cycle into the EU's chain, on the INT pin instead.  R7′ closed
it with **one mux**, moving the take onto the destination register's own `D`
pin, with zero flops added and a zero-delta ladder.  That is a worked precedent
in this tree for this exact shape.

**Three conditions, and the first two are not negotiable:**

1. **It must be RTL, not SDC.**  `ghost_preflash20_results_2026-08-12.md` §6.3
   booked an "E-1 analogue for `c_int_q`" and required a derivation first —
   and **under the §0 ruling that derivation is now harder, not easier**,
   because it may not appeal to `div/2 − 1`.  Widening the SDC here would be
   asserting something unproven about interrupt recognition, which is the
   mechanism this campaign has spent the most measurements on.
2. **Its own pre-registration, with a zero-behaviour-change ladder**, since
   unlike Phase 1 it touches RTL that every engine reads.
3. **Two draws per configuration**, `standing_gates.md` §A.

**Booked but NOT recommended for the first wave**, in descending order of
likely value:

* **`div_cnt → t1_half2`'s enable arc** (#2 in both configurations, a true half
  period).  The RTL answers — register `ce_half`, or retime `t1_half2` to a
  posedge flop — both change the core's clocking and are **behaviour-visible**,
  so both need their own campaign, not a phase.
* **`v30u_ucrom` as an M10K** — 1,050 ALUTs, 0 registers, 9.4 ns at the head of
  the `CORE→ANY` cone.  The single biggest structural lever, and it costs a
  cycle of latency, so it is banned by the zero-behaviour terms **by their
  terms, not by its merits**.
* **`CHAIN_MAX` 12 → 7** — §51.2 derived depth 6 and *declined* to tighten the
  bound; m72 §3 re-derived depth 6 independently on four LFSR seeds and
  measured that the untightened bound **costs depth, and depth is not recovered
  by the fold**.  It has a worked precedent and a measured benefit in another
  fit, and it tightens a bound this tree explicitly chose not to tighten — so
  it needs this tree's treatment and its own pre-registration.

**One decision is owed by the user before any of this**: §7.3's E-1 reading,
worth **2.41 MHz** — more than any single Phase-2 lever is likely to return.
