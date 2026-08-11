# fz2 WAVE-6 — THE 8F GHOST-READ **ADDRESS RAIL** LAW — PRE-REGISTRATION

**SIMPLICITY: this is 80's era hardware — nothing on the die is wasted. Complex
or confusing observed behavior is likely simple systems interacting in ways not
yet understood. A large fitted table, a many-cased rule, or a per-opcode special
case is a signal of misunderstanding, not a deliverable.**

Branch `fuzz-v2-on-relanding`, worktree **reset to `3999f0d669`** before any
measurement (`git rev-parse HEAD` verified `3999f0d669960368…`; the worktree had
provisioned at `master`/`29dcc5b05f` and was reset).  Territory:
**`hdl/rtl/ucore/v30u_eu.sv`, lines 1481–1493 only** (the `ghost_off` rail
selector).  Offline; Quartus in scope (G6 gates); **no board**; the C++ model is
defunct on this branch and `ulockstep` is INFORMATIONAL here.

**This document is committed BEFORE the rail solve is run** (the derivation).
The seat list and the DERIVE/HOLDOUT split below were frozen with **no
dependence on any address** — the split is a hash of the seed id.  The survey
(which prints chip/core addresses) is prior art from M10/wave-4; the RAIL SOLVE,
the actual derivation, has NOT been run on this population and is run only on
DERIVE after this commit.

Rescore instrument: **`sw/fz2_replay.py --leg ret`** (faithful `tb_sys`).
Derivation instrument: **`sw/fz2_m10.py solve`** (save-state mode 6 on the
receipted `--core ucore` `tb_v30_core`; reads architectural register VALUES,
which the `ghost_off` edit does not change).  Ledger:
**`sw/testdata/fz2/fz2_failure_ledger_f16_2026-08-10.json`** (116 failures,
denominator 3,838).  ⚠ `fz2_ledger.CURRENT` points at F15; every invocation
passes `--ledger` explicitly.

⚠ **EVERY POST-RTL `fz2_replay` FIGURE IS OFFLINE AND CROSS-ERA** and carries
**`--no-fabric-era-guard`**, said so beside every number.  No fabric figure may
be quoted against the landed tree until a re-flash.

---

## 0.  WHAT WAVE-4 SETTLED, AND WHAT THIS WAVE IS

M10 (`fz2_m10_diagnosis_2026-08-10.md` §5.2) found the ucore's ghost read makes
**two** free choices badly: (1) *whether the AND with SP happens* and (2)
*which retained rail it reads*.  **Wave-4** (`fz2_w4_ghostaddr_results…`) settled
(1) — deleting the four-constant `ghost_relax` mask and making the AND
unconditional (`ghost_bus_off = … : (ghost_off & gpr[R_SP])`).  **This wave is
(2), the RAIL, and nothing else.**

The rail selector in the tree now (`v30u_eu.sv:1481-1493`):

```verilog
wire        ghost_uses_ea = (ea_residue != tmpa);
wire [15:0] ghost_ea_off  = (pe_opc_reg == 8'h8e) ? ea_residue
                                                  : {ea_residue[15:1], 1'b0};
wire [15:0] ghost_off     = ghost_uses_ea ? ghost_ea_off : tmpa;
```

Three fitted cases: a comparator select (`ea_residue != tmpa`), a per-opcode
special case (`8E`), and a low-bit mask.  `ea_residue` is the ALU residue —
`v30u_eu.sv:3234`, `if (tmpa_n != tmpa) ea_residue_n = tmpa_n`, i.e. a retained
copy of the last ALU result.

## 1.  THE CANDIDATE LAW — SHAPE, NOT FITTED CONSTANTS

M10's register-file solve named the rail on its cheap subset: on `fz2e/530034`
the chip drives **`SS:M_EA` (= `SS:WB_EA`) plain**, and on `fz2e/519072`
**`SS:(SP & M_EA)`**, where the core takes `SS:EA_RESIDUE` on both.  `M_EA` is the
**retained ModR/M effective-address register** (`v30u_eu.sv:366`, `m_ea`); an
`8F` mod==3 (POP r/m16, register form) has no memory EA of its own, so its ghost
stack read reuses whatever address the datapath last latched — the previous
instruction's ModR/M address, physically still sitting in `m_ea`.  **A single
retained address register is a simple system; the ALU-residue comparator plus an
`8E` case plus a low-bit mask is what you write when you have not found it.**

**THE CANDIDATE SHAPE (one rail, replacing the three-case selector):**

```verilog
wire [15:0] ghost_off = m_ea;      // the retained ModR/M EA rail
```

deleting `ghost_uses_ea`, `ghost_ea_off`, the `8E` special case, and the
low-bit mask.  The wave-4 AND (`ghost_bus_off = … : (ghost_off & gpr[R_SP])`) is
UNTOUCHED — this wave is the rail only.

**CONSTANTS ARE NOT FITTED HERE.**  The one degree of freedom the SHAPE leaves —
`m_ea` vs its measured equal `wb_ea` — is resolved on DERIVE by the solve
(§2.2), before any HOLDOUT number is read.  If `m_ea` and `wb_ea` diverge on any
DERIVE seat and only one fits the chip, that one is named with the seat that
distinguished them; if they never diverge on DERIVE, `m_ea` is chosen by fiat
(the read-EA rail) and that fiat is stated.

## 2.  THE CIRCULARITY GUARD — THE FROZEN SPLIT (§64.1 governs)

**Population**: the **39 ADDRESS seats** — `near_package == "P4"` and
`t1_addr_differs` on the F16 ledger, re-derived by `fz2_w4_ghostaddr_prereg` §7's
script (`fz2_m10.survey_one` over every family).  The list is frozen in
`fz2_w6_split.json` beside this document.

**Split rule (address-independent, frozen):**
`sha256(seed_id).hexdigest()[0] < 8` → **DERIVE**, else **HOLDOUT**.

* **DERIVE (16):** `fz2c/408021 fz2c/409025 fz2e/517046 fz2e/518004
  fz2e/518022 fz2e/519072 fz2e/520000 fz2e/522029 fz2e/524030 fz2e/524055
  fz2e/528010 fz2e/530017 fz2e/530070 fz2e/533025 fz2e/534062 fz2e/535036`
* **HOLDOUT (23):** `fz2c/406063 fz2c/408068 fz2c/409077 fz2c/410008
  fz2e/518033 fz2e/518039 fz2e/518053 fz2e/518067 fz2e/519016 fz2e/520005
  fz2e/520040 fz2e/520066 fz2e/521059 fz2e/524007 fz2e/526054 fz2e/527037
  fz2e/529067 fz2e/530020 fz2e/530034 fz2e/531018 fz2e/532000 fz2e/534060
  fz2e/535004`

The rail is DERIVED (the solve, §2.2) on **DERIVE only**.  It is SCORED (§3,
`fz2_replay`) on **HOLDOUT**, which chose nothing.  **The HOLDOUT closure count
is the deliverable; the DERIVE fit is not evidence** (`CLAUDE.md` §64.1, the H1
re-key).

**Prior-art disclosure (honesty, not a loophole):** M10 already named `M_EA`
using `fz2e/530034` (now in HOLDOUT) and `fz2e/519072` (DERIVE).  So HOLDOUT
closures split into **M10-prior-art seats** — `fz2e/530034`, `fz2c/410008`,
`fz2e/519016`, `fz2e/520040`, `fz2e/526054`, `fz2e/518033` — whose shape was
partly informed by M10's own solve, and **fresh HOLDOUT seats** the rail was
never derived against.  **Both are reported; the fresh-HOLDOUT closures are the
strongest claim.**  `fz2e/530034` in particular needs the AND *removed* (M10:
plain `M_EA`, no AND), which is wave-4's OTHER free choice, not this one, so it
is predicted NOT to close under rail+unconditional-AND (§3, W6-4).

### 2.2  THE DERIVATION STEP (DERIVE only, run after this commit)

`fz2_m10.py solve --seeds <DERIVE>` sweeps the save-state freeze across each
DERIVE seat's fork and reports every named term that fits the CHIP address.
**The mechanical acceptance rule, fixed here:**

> Over the DERIVE seats that (a) pass NOREPRO and (b) are arch-solvable address
> forks, if a **single rail expression** (`m_ea` or its equal `wb_ea`, with or
> without the settled `& SP`) fits the CHIP on **every** such seat, that rail is
> the law.  **If DERIVE itself needs two or more distinct rails, the mechanism
> is not understood — book it, land nothing.**  A 2-case rail rule to close 39
> seats is a fitted table wearing a law's clothes and is explicitly forbidden.

## 3.  THE REGISTERED PREDICTIONS

| id | prediction | how it is refuted |
|---|---|---|
| **W6-D** | The DERIVE solve names a **single rail** (`m_ea`/`wb_ea`) fitting the chip on every arch-solvable DERIVE address fork. | two distinct rails needed → **book, land nothing** |
| **W6-1** | **THE DELIVERABLE.** On HOLDOUT (`fz2_replay --leg ret`), the landed rail law closes **≥ 3** address seats that are NOT M10-prior-art (`bad_rows` → 0), OR — if fewer — the closures are named and the shortfall reported as registered. | fewer than 3 fresh closures **and** no coherent single-rail story → booked, not landed |
| **W6-2** | **LOST = 0** over the full replayed population (DERIVE ∪ HOLDOUT ∪ pass-sample). | any seed `bad_rows == 0` at baseline, `!= 0` after |
| **W6-3** | **No still-failing seed's `first_bad` moves EARLIER.** | any decrease |
| **W6-4** | `fz2e/530034` (HOLDOUT) is **NOT** closed by rail-alone (it needs the AND removed — wave-4's other choice). If it closes anyway, reported as an unregistered bonus. | — (non-claim) |
| **W6-5** | The **§64.1 four** unmoved in `first_bad_row` (`fz2c/406063` 3149 · `fz2c/410047` 3589 · `fz2e/518053` 3413 · `fz2e/535027` 3226), and `fz2c/404040` stays `bad == 0`. `406063`/`518053` are in the population but are arch-DIFF upstream-divergence seats; the rail law is predicted not to move them. | any move |
| **W6-6** | `ss_lint --core ucore` **PASS and UNMOVED**: `SS_VERSION` **0x8D**, `SS_BIU_COUNT` **103**, `SS_EU_COUNT` **122**, `SS_COUNT` **226**, `SS_TAG` **0x8DE2**, 214 flops, 0 UNMAPPED. **NO new flop, NO new SSA address** — this is a pure combinational rail swap; if a variant needed a flop it would be STOPPED and coordinated. | any constant moving, or a `reg` in the diff |
| **W6-7** | `r7_lint` **PASS, 0 violations, NO NEW EXCEPTION**, tainted set **unchanged** (`eu_rd_edge` + 2). `m_ea` is register-only ModR/M state, no live READY. | a violation / new exception / larger tainted set |
| **W6-8** | `gen_ucore_qsf --check` up to date. | anything else |
| **W6-9** | `test_artifact` **45/45**, non-vacuous. | anything else |
| **W6-10** | **8F.0 GOLDEN HOLDS**: `check_core --core ucore --opcodes 8F.0 --cases 0` = **500/500** (cycles AND arch). | anything below |
| **W6-11** | `check_core --core ucore --opcodes all --cases 0` = **169,000/169,000**. | anything below |
| **W6-12** | four HLT sweeps **97 · 93 · 45 · 44 = 279/283** (run with `--waits 0/1/2/3`). | anything below |
| **W6-13** | four `evt` cells **200 / 1,200 / 200 / 1,200**, biased **1,200/1,200**, `check_core --opcodes INT.F3AA` **200/200**. | anything below |
| **W6-14** | `check_fuzz_bank` **PASS, 621 seeds, stable 621 / improved 0 / worse 0**, `gen_drift` 0. | anything else |
| **W6-15** | `ulockstep --golden 8F.0 --cases 50` INFORMATIONAL (model defunct; predecessor-effect law `sim/` cannot see). `--golden all --cases 50` = **17,350/17,350**. | (not gated) |
| **W6-16** | **NON-VACUITY**: `fz2_replay --perturb 1` diverges every seat W6-1 closes, N of N. | any closed seat surviving perturbation |
| **W6-17** | **G6 — THE GATE THAT DECIDES THIS LANDING.** CONTROL/DEFAULT build, clean `db`, **TWO DRAWS**: both **≥ 38.0 MHz** (STOP), worst setup **> 0**, **TNS 0.000** every domain setup AND hold, 0 errors / 0 latches / 0 `lpm_divide`. Ghost neighbourhood; wave-4 drew 39.05 twice; band ~38.4–40.5. Mechanistically the change swaps a 3-mux rail select for a single register read at the head of the `acc_phys` adder — predicted **neutral-to-positive**. | **any draw < 38.0 MHz, or the two draws disagreeing materially** |

### 3.1  THE STOP CONDITION, WRITTEN BEFORE THE BUILD

**If G6 collapses — either draw below 38.0 MHz — the law is booked
`UNLANDABLE AS DESIGNED` with the timing evidence and the RTL is NOT landed,
exactly as the ghost FEED was at 15.3 MHz.**  No re-formulation inside this
sitting.  **If DERIVE needs 2+ rails, land nothing and book "no single rail".**
A booked negative beats a fitted land.

## 4.  WHAT WOULD MAKE THIS WRONG

* **Deriving the rail on the seats it is scored on.**  §2 is the guard: the
  split is address-independent and frozen; the solve runs on DERIVE, the score
  on HOLDOUT.
* **Choosing `m_ea` vs `wb_ea` after seeing the HOLDOUT result.**  §1/§2.2
  resolve it on DERIVE first.
* **Adding a second rail case to close a seat.**  Forbidden (§2.2, §3.1).
* **Quoting a fabric number against the post-landing tree** (`--no-fabric-era-guard`).
* **Quoting `ulockstep` as a correctness bar** (W6-15).

## 5.  WHAT IS NOT DONE

* **No board, no flash.**  Offline throughout.
* **`sim/` is not extended** (defunct on this branch).
* **`acc_split` / `acc_phys2` are not re-derived** — this is the address rail,
  not the split.  Where they read `ghost_uses_ea`, that is noted, not hidden.
* **The AND free choice is not touched** — wave-4 settled it; `fz2e/530034`'s
  no-AND is booked, not fixed here.

## 6.  PROVENANCE

| thing | id |
|---|---|
| tree | `3999f0d669` (`fuzz-v2-on-relanding`) |
| ledger | `sw/testdata/fz2/fz2_failure_ledger_f16_2026-08-10.json` |
| population | 39 address seats, `fz2_w6_split.json` |
| split rule | `sha256(seed_id)[0] < 8` → DERIVE (16), else HOLDOUT (23) |
| derivation | `fz2_m10.py solve`, DERIVE only, save-state mode 6 |
| score | `fz2_replay.py --leg ret --no-fabric-era-guard` |
