# fz2 WAVE-4 — THE 8F GHOST-READ **ADDRESS** CONE — PRE-REGISTRATION

**SIMPLICITY: this is 80's era hardware — nothing on the die is wasted. Complex
or confusing observed behavior is likely simple systems interacting in ways not
yet understood. A large fitted table, a many-cased rule, or a per-opcode special
case is a signal of misunderstanding, not a deliverable.**

Branch `fuzz-v2-on-relanding`, worktree **reset to `32128b57b4`** before any
measurement (`git rev-parse HEAD` verified; the worktree had provisioned at
`master`/`29dcc5b05f` and was reset).  Territory: **`hdl/rtl/ucore/v30u_eu.sv`,
lines 1481–1536 only.**  Offline; Quartus in scope; **no board**; the C++ model
is defunct on this branch and `ulockstep` is INFORMATIONAL here.

Rescore instrument: **`sw/fz2_replay.py --leg ret`** (the faithful `tb_sys`
replay, 266/266 against fabric at F16).  **NOT** the single-scheduler
rescorers.  Ledger: **`sw/testdata/fz2/fz2_failure_ledger_f16_2026-08-10.json`**
(116 failures, denominator 3,838, era `.sof fed558c0e611…`).  ⚠ Note
`fz2_ledger.CURRENT` still points at **F15**; every invocation in this package
passes `--ledger` explicitly.

⚠ **THE BASELINE COLUMN IS FABRIC-ERA-VALID; EVERY POST-RTL COLUMN IS NOT.**
At `32128b57b4` the FABRIC ERA GUARD **PASSES** (87/88 inputs hash identical,
the 88th being the Quartus-rewritten `.qsf`, exempt) — no RTL has moved since
FLASH #16 (`git diff ddaed64457 HEAD -- hdl/` is empty).  The moment the RTL
moves, the tree is ahead of the flash and every `fz2_replay` run carries
**`--no-fabric-era-guard`**; **SAID SO** beside every number.  No fabric figure
may be quoted against the post-landing tree until a re-flash.

---

## 0.  ⚠ THE TIMING PRECEDENT GOVERNS THIS PACKAGE

The 8F ghost family has collapsed Fmax before.  The full ghost **feed** drew
**15.3 MHz / −34.094 ns / TNS −10,443.096** on two draws
(`ghost8f_results_2026-08-09.md` §9) and was booked **UNLANDABLE AS DESIGNED**;
only the ghost READ landed.  **`r7_lint` PASSING IS NECESSARY AND NOT
SUFFICIENT** — the feed passed it, and is why (its route to the loader chain is
register `D` pins, outside the `stop` charter).

**The branch's CONTROL band is 39.16 · 39.37 · 39.47 · 39.63 · 39.81 · 40.11 ·
40.42 MHz.  THE STOP THRESHOLD IS 38.0 MHz: any draw materially below it is a
STOP-and-report, not an iterate.**  G6 **two draws**; if they disagree, that
disagreement is itself the finding.

---

## 1.  THE SEAT LIST — RE-DERIVED FROM THE F16 LEDGER, AND THE BRIEF'S "~34"
## IS CORRECTED UPWARD

The brief says *"family E1/M10 + P4′ address seats, ~34 seats"*.  Re-derived
here with **the RTL's own predicate** — `fz2_m10.package_of`, i.e. opcode `8F`
with `mod == 3` (`v30u_eu.sv:915`'s `upc_opc == 8'h8f` with `m_kind ==
OK_REG`/`wb_kind == OK_REG`) — scanned back **six `F` pops** from each fork,
over **every family in the ledger, not just `E1`**:

```
total failures 116   8F-mod3-within-6-pops: 51
   31  E1 same-status data cycle, different address
    6  D1 chip fetched, core did not
    3  D2 core fetched, chip did not
    3  A3 cycle-time slip (non-qs)
    3  E2 different-status data cycle
    2  D3 both fetched, different address
    1  C3 NMI(vec2) entry     1  C1 vector-1 trap MISSED     1  C4 other-vector
```

* **51 ghost-proximate seats**, of which **39 are ADDRESS seats** (the forking
  cycle's own `T1` address differs between chip and core) and **12 are
  same-address** seats that fork on another column and are **NOT claimed by this
  package**.
* **`E1` reproduces M10's F15 partition exactly on F16**: 41 seats, 31 P4′, 10
  residual, distance histogram `[(0,8),(1,18),(2,3),(3,2)]` — the same
  "arrives one `F` pop after its issuer" signature.  The **20 further seats
  outside `E1`** are new to this package and were not available to M10, whose
  survey is `E1`-only by construction.
* **Base rate, stated so the count is readable**: M10's control A measures the
  `8F` mod==3-within-6-pops coincidence at **5.84 %** on random rows inside the
  same seeds.  At that rate ≈ **6.8** of 116 failures would be ghost-proximate
  by chance; **51 are**.  Roughly seven of the 51 are expected to be
  coincidence and **this package does not claim to know which**.

The full table (seat, family, fork row, diverging rows, arch, chip/core `T1`
address, delta, pops-back, retired `8F` bytes) is
`ghost_seats_f16.json`, regenerated from the ledger by the script in §7; nothing
in it is typed by hand.

**Baseline, measured before this document was written** (`fz2_replay --leg ret`,
654 seeds, **ERA GUARD PASS**, `tb_sys` receipt `9b659ba3edb81c7f…`):
**all 51 ghost seats FAIL, 538 of 603 non-ghost seeds PASS, 0 errors.**

---

## 2.  THE LAW — ONE TERM, AND WHAT IT DELETES

### 2.1  What is in the tree now: a FIVE-CASE FITTED MASK

`v30u_eu.sv:1481-1509`:

```verilog
wire        ghost_uses_ea     = (ea_residue != tmpa);
wire        ghost_uses_mul_hi = (pla3_native(pe_opc_reg) == 14'h0104) && !tmpc[15];
wire [15:0] ghost_ea_off      = (pe_opc_reg == 8'h8e) ? ea_residue
                                                      : {ea_residue[15:1], 1'b0};
wire [15:0] ghost_off         = ghost_uses_ea ? ghost_ea_off : tmpa;
wire [15:0] ghost_relax = eu_ghost_full ? 16'hFFFF
                        : eu_ghost_idle ? ((pe_op8 ? 16'hC000 : 16'h8000) |
                                           (ghost_next_byte ? 16'h0080 : 16'h0000))
                        : 16'h0000;
wire [15:0] ghost_bus_off = ghost_uses_mul_hi          ? (tmpa & opr)
                          : (eu_ghost_idle && !q_ripe) ? gpr[R_SP]
                          :                              (ghost_off & (gpr[R_SP] | ghost_relax));
```

Four magic constants (`FFFF`/`C000`/`8000`/`0080`), one per-opcode special case
(`pe_opc_reg == 8'h8e`), one per-PLA-class special case (`14'h0104`), and a
three-way `ghost_bus_off`.  **That shape is the misunderstanding the standing
principle names**, and the ~39 address seats are its evidence.

### 2.2  The candidate, and WHO chose it (not this package)

M10's **register-file solve** — an independent wave-3 instrument, save-state
mode 6 read at 14 freezes over a 3,208-named-expression space with **no free
parameter** (expected accidental fits ≈ 0.003 per freeze) — reports on the
`P4′` cheap subset (`fz2_m10_diagnosis_2026-08-10.md` §5.1/§5.2):

> on `410008`, `519016`, `520040` **the chip performs the AND and the core does
> not** — `ghost_relax` was non-zero across the differing bits and should have
> been **0**

and the direct predicate test — `SS:(ghost_off & SP)` evaluated with the RTL's
**own** `ghost_off` — reproduces the chip **exactly** on those three at freezes
`−3` and `−2`.  Every chip-side fit on those seats is a **wired AND**; not one
is a single term and not one is an OR.

**THE ONE TERM IS THEREFORE:**

```verilog
wire [15:0] ghost_bus_off = ghost_off & gpr[R_SP];
```

*A wired-AND of two live drivers on one internal bus is a simple system; a
four-constant relax mask is what you write when you have not found it.*

**This law was selected on M10's 9-seat solve.  It is scored here on 39 address
seats and 654 replayed seeds, of which 36 seats and all 654 did not select it** —
which is the discipline `CLAUDE.md` requires of a refuted key's replacement.

### 2.3  THE LADDER — four variants, each DELETING one fitted case

| | change, cumulative | what it deletes |
|---|---|---|
| **V1** | `ghost_relax` → gone; the AND is **unconditional**: `(ghost_off & gpr[R_SP])` | 4 magic constants, the `pe_op8` case, the `eu_ghost_full`/`eu_ghost_idle` three-way inside the mask |
| **V2** | V1 + drop the `(eu_ghost_idle && !q_ripe) ? gpr[R_SP]` arm | 1 case |
| **V3** | V2 + drop the `ghost_uses_mul_hi ? (tmpa & opr)` arm → **`ghost_bus_off = ghost_off & gpr[R_SP]`, ONE TERM** | 1 case + the `14'h0104` PLA-class constant, from the address path |
| **V4** | V3 + drop the `pe_opc_reg == 8'h8e` special case: `ghost_ea_off = {ea_residue[15:1], 1'b0}` always | the per-opcode special case P4′ named |

**Out of scope, deliberately**: `acc_split` (line 1532) and `acc_phys2` (1526)
also read `ghost_uses_ea` / `ghost_uses_mul_hi` / `eu_ghost_idle`.  They decide
the **split**, not the **address**, and this package is the address cone.  Where
a variant leaves a selector alive only for `acc_split`, that is **stated, not
hidden**.

### 2.4  THE SELECTION RULE — MECHANICAL, FIXED BEFORE ANY VARIANT IS BUILT

> Build and score **all four**.  Land the **DEEPEST** `Vk` such that
> **(a) LOST = 0** over the 654-seed population **and (b) net closures ≥ net
> closures of V1**.  If no variant has LOST = 0, **land none** and book the law
> with the evidence.  Deeper deletion at equal-or-better closure always wins,
> **because the deletion of fitted cases is the deliverable.**

*A partial close that DELETES fitted cases beats a full close that adds one.*
No fifth arm will be added under any measurement.

---

## 3.  THE REGISTERED PREDICTIONS

| id | prediction | how it is refuted |
|---|---|---|
| **W-1** | **M10's OWN FALSIFIER.** Under **V1**, `fz2c/410008`, `fz2e/519016` and `fz2e/520040` all CLOSE (`bad_rows` → 0). | any of the three still failing.  **This is the deciding prediction: it is the test of the whole law, registered by M10 before this package existed.** |
| **W-2** | **NOT CLAIMED, and named so the absence is honest**: `fz2e/518033`, `fz2e/519072`, `fz2e/524055`, `fz2e/526054`, `fz2e/528010`, `fz2e/530034`.  M10 says three need the **rail** changed, one needs the **segment sample** moved, and two are solve-EMPTY. | — (a closure here is a bonus and will be reported as unregistered) |
| **W-3** | **LOST = 0** over the 654 replayed seeds, on the landed variant. | any seed with `bad_rows == 0` at baseline and `!= 0` after |
| **W-4** | **No still-failing seed's `first_bad` moves EARLIER.** | any decrease |
| **W-5** | Net closures over the **39 ADDRESS seats** ≥ **3** on the landed variant. | fewer than 3 |
| **W-6** | **No claim of any kind** on the **12 same-address ghost seats**, nor on the ~7 of 51 the base rate says are coincidence. | — |
| **W-7** | `ss_lint --core ucore` **PASS and UNMOVED**: `SS_VERSION` **0x8D**, `SS_BIU_COUNT` **103**, `SS_EU_COUNT` **122**, `SS_COUNT` **226**, `SS_TAG` **0x8DE2**, **214** architectural flops, 0 UNMAPPED.  **NO new flop and NO new SSA address** — `SSA_E_GHOST_DISCARD` `0x176` already exists and nothing is appended.  ⚠ **This package is NOT the save-state single-writer this wave**; if a variant needed a flop it would be STOPPED and the bump coordinated, not taken. | any constant moving, or a `reg` appearing in the diff |
| **W-8** | `r7_lint` **PASS, 0 violations, NO NEW EXCEPTION**, and the tainted set **unchanged or smaller** than the baseline's `3 (eu_rd_edge, rd_edge_psw_take, rd_edge_take_raw)`.  The deletion removes only register-only BIU state (`eu_ghost_full`/`eu_ghost_idle` are `r_run`/`r_cur_fetch`/`r_ts` — no live READY). | a violation, a new exception, or a larger tainted set |
| **W-9** | `gen_ucore_qsf --check` up to date. | anything else |
| **W-10** | `test_artifact` **45/45**, non-vacuous. | anything else |
| **W-11** | **THE 8F GOLDEN HOLDS**: `check_core --core ucore --opcodes 8F.0 --cases 0` = **500/500**. | anything below |
| **W-12** | `check_core --core ucore --opcodes all --cases 0` = **169,000/169,000**, cycles AND arch. | anything below |
| **W-13** | the four HLT sweeps **97 · 93 · 45 · 44 = 279/283** (run with `--waits 1/2/3` — the mis-invocation of `ghost8f_read_results` §10.2). | anything below |
| **W-14** | the four `evt` cells **200 / 1,200 / 200 / 1,200**, biased **1,200/1,200**, `check_core --opcodes INT.F3AA` **200/200**. | anything below |
| **W-15** | `check_fuzz_bank` **PASS, 621 seeds, stable 621 / improved 0 / worse 0**, `gen_drift` 0. | anything else |
| **W-16** | **INFORMATIONAL, NOT A BAR — the model is defunct on this branch.** `ulockstep --golden 8F.0 --cases 50` is **PREDICTED TO FALL BELOW 50/50**, because the ghost address is exactly what `sim/` does not carry this law for.  Per `ghost8f_results_2026-08-09.md` §4 that is **not a silicon-match regression**; `check_core 8F.0` (W-11) is the silicon bar. | — (reported, not gated) |
| **W-17** | **NON-VACUITY**: `fz2_replay --perturb 1` diverges every seat W-1 closes, N of N. | any closed seat surviving its own perturbation |
| **W-18** | **G6 — THE GATE THAT DECIDES THIS LANDING.** CONTROL/DEFAULT build, clean `db`, **TWO DRAWS**: both **≥ 38.0 MHz** (the STOP threshold), predicted band **39–42 MHz**, worst setup **> 0**, **TNS 0.000 on every domain setup AND hold**, 0 errors / 0 latches / 0 `lpm_divide`.  Mechanistically the change **removes** a 16-bit OR-with-mask and two mux levels from the head of the 20-bit `acc_phys` adder, so it is predicted **neutral-to-positive**. | **any draw < 38.0 MHz, or the two draws disagreeing materially** |

### 3.1  THE STOP CONDITION, WRITTEN BEFORE THE BUILD

**If G6 collapses — either draw below 38.0 MHz — the law is booked
`UNLANDABLE AS DESIGNED` with the timing evidence and the RTL is NOT landed,
exactly as the ghost FEED was at 15.3 MHz.  That is a legitimate outcome and
will be reported as the result, not iterated around.**  No re-formulation will
be attempted inside this sitting; a feed/mask that fires on a different clock is
a different mechanism and must be measured as one.

---

## 4.  WHAT WOULD MAKE THIS WRONG

* **Choosing the variant after seeing the seat list.**  §2.4 is mechanical and
  fixed here; the four variants are enumerated before any is built.
* **Adding a sixth arm to close a seat.**  Explicitly forbidden above.
* **Quoting a fabric number against the post-landing tree.**  Every post-RTL
  column carries `--no-fabric-era-guard` and says so.
* **Quoting `ulockstep` as a correctness bar.**  W-16.
* **Reading `r7_lint` PASS as a timing claim.**  §0.

## 5.  WHAT IS NOT DONE

* **No board, no flash.**  Offline throughout.
* **`sim/` is not extended** (defunct on this branch).
* **`acc_split` / `acc_phys2` are not re-derived** — §2.3.
* **The 10 residual M10 seats** (`406006`, `406054`, `408019`, `501069`,
  `510043`, `518038`, `522019`, `524034`, `530001`, `535027`) are **not this
  package's**; M10 §5.4 books them EMPTY with two readings it could not
  separate, and its §6.0 step zero is still the next thing to run on them.

## 6.  PROVENANCE

| thing | id |
|---|---|
| tree | `32128b57b4` (`fuzz-v2-on-relanding`) |
| ledger | `sw/testdata/fz2/fz2_failure_ledger_f16_2026-08-10.json` |
| era | `.sof fed558c0e611…`, `flash_git ddaed64457-dirty`, receipt `f88783b66cf4a1ee…` |
| `tb_sys ret` | `hdl/tb/obj_dir_sys_ret/Vtb_sys`, receipt `9b659ba3edb81c7f…` |
| baseline column | 654 seeds, ERA GUARD **PASS**, 0 errors, 51/51 ghost seats FAIL |
| seat derivation | `fz2_m10.survey_one` over every family (§7) |

## 7.  THE SEAT-DERIVATION SCRIPT (so a reviewer re-runs it, not re-types it)

```python
import json, sys; sys.path.insert(0, "sw"); import fz2_m10 as m
led = json.load(open("sw/testdata/fz2/fz2_failure_ledger_f16_2026-08-10.json"))
rows = [dict(m.survey_one(e), family=e["family"]) for e in led["failures"]]
ghost = [r for r in rows if r["near_package"] == "P4"]          # 51
addr  = [r for r in ghost if r["t1_addr_differs"]]              # 39
```
