# fz2 WAVE-7 — THE 8F GHOST-READ **ADDRESS RETENTION** LAW — PRE-REGISTRATION

**SIMPLICITY: this is 80's era hardware — nothing on the die is wasted. Complex
or confusing observed behavior is likely simple systems interacting in ways not
yet understood. A large fitted table, a many-cased rule, or a per-opcode special
case is a signal of misunderstanding, not a deliverable.**

Branch `fuzz-v2-on-relanding`, worktree **reset to `f32249a9d0`** before any
measurement (`git rev-parse HEAD` verified `f32249a9d0d621dd…`; the worktree had
provisioned at `master`/`29dcc5b05f` and was reset onto a work branch
`w7-ghost-retention` at `f32249a9d0`).  Territory:
**`hdl/rtl/ucore/v30u_eu.sv`** (the `ghost_off` rail selector, lines 1481–1493,
and the ghost consumer) **and `hdl/rtl/ucore/v30u_ss_pkg.sv`** (one new SSA
address).  Offline; Quartus in scope (G6 gates); **no board**; the C++ model is
defunct on this branch and `ulockstep` is INFORMATIONAL here.

**This document is committed BEFORE the landed-RTL is scored.**  The fresh
DERIVE/HOLDOUT split below was frozen with **no dependence on any address** (a
hash of the seed id salted `"w7"`), committed in `docs/notes/fz2_w7_split.json`.
The DERIVE derivation (`fz2_m10.py solve`) has been run on DERIVE and is quoted
in §2; the HOLDOUT score (`fz2_replay`) has NOT and is the deliverable.

Rescore instrument: **`sw/fz2_replay.py --leg ret --no-fabric-era-guard`**
(faithful `tb_sys`; every post-landing figure is offline and cross-era and says
so).  Derivation instrument: **`sw/fz2_m10.py solve`** (save-state mode 6 on the
receipted `--core ucore` `tb_v30_core`).  Ledger:
**`sw/testdata/fz2/fz2_failure_ledger_f16_2026-08-10.json`** (116 failures,
denominator 3,838); every invocation passes `--ledger` explicitly.

---

## 0.  WHERE WAVE-6 LEFT THIS, AND WHAT THIS WAVE IS

Wave-6 (`fz2_w6_ghostrail_results_2026-08-10.md`) **REFUTED the single static
rail**: the 8F ghost read's fitting register tracks the retired-8F pipeline
distance — `near_dist == 0` → **`IND`** (the BIU live index), `near_dist == 1` →
**`M_EA`** (the retained ModR/M EA).  It SPECULATED (§3) that the correct model
is a **retained flop** capturing the 8F's intended address at issue, which would
"subsume both the dist-0 and dist-1 seats," and left that outside its charter.

**THIS WAVE TESTS THAT SPECULATION.**  The candidate is: capture the 8F's
intended stack address **at issue** (where `ghost_read_stale_alu`,
`v30u_eu.sv:915`, gates exactly the dist-0 issue point) into a retained flop
`ghost_addr_hold`, and have the ghost read source it instead of the fitted
`ghost_off` selector — deleting `ghost_uses_ea`/`ghost_ea_off`/the `8E`
case/the low-bit mask.  The register captured at issue is **`IND` (`ind_now`)**,
which the DERIVE solve names (§2).

## 1.  THE CANDIDATE LAW — SHAPE, NOT FITTED CONSTANTS

```verilog
// one retained flop, loaded at the 8F ghost-read issue with the live index
reg  [15:0] ghost_addr_hold;                 // SSA_E_GHOST_ADDR = 9'h17E
// ... ghost_addr_hold_n = ghost_read_stale_alu ? ind_now : ghost_addr_hold;
wire [15:0] ghost_off = ghost_addr_hold;     // replaces the 3-case selector
```

with the wave-4 unconditional AND (`ghost_bus_off = … : (ghost_off & gpr[R_SP])`)
UNTOUCHED — this wave is the rail source only.

**⚠ AN IMPLEMENTATION HONESTY NOTE, REGISTERED HERE BEFORE THE BUILD.**  The
ucore EU is cycle-accurate: `ghost_read_stale_alu` asserts on the 8F's own
discarded stack-read row and the BIU samples `eu_addr` on that same clock, so
`ind_now` at that row **already is** the issue value, and the BIU's request
latch **already provides the retention** across any bus delay.  A flop loaded
and read on one clock is one cycle stale.  So the faithful cycle-accurate form
of "IND at issue" is the **combinational** `ghost_off = ind_now`; the retained
`ghost_addr_hold` flop is the silicon abstraction and, if it lags the read by a
cycle, is the WRONG implementation of the same mechanism.  **The mechanism under
test is `ghost_off = IND`.**  If the combinational form is the faithful one, the
SSA bump in §5 is NOT taken and that is reported as a deviation from this brief,
not hidden.  Both forms are scored; the SS-writer bump is pre-registered in case
a genuine one-cycle retention proves necessary and correct.

## 2.  THE DERIVATION — DERIVE ONLY (run, and quoted here before HOLDOUT)

`fz2_m10.py solve --seeds <DERIVE 22>` → classified by `fz2_w6_railcheck.py` at
the fork clock `d=0`:

```
fz2c/408021  chip=13ef0 core=06b70  IND    (IND fits; IND=SP=d7c0)
fz2e/524030  chip=33f00 core=2df00  IND    (IND fits; IND=SP=ec50 at d=0)
fz2e/524055  chip=3a400 core=3a3c0  EMPTY  (upstream divergence, out of scope)
fz2e/528010  chip=8b92d core=863a8  EMPTY  (upstream divergence, out of scope)
  … 11 NOREPRO (need tb_sys; not arch-solvable on tb_v30_core)
classes: EMPTY:2, IND:2, NOREPRO:11
```

**On the arch-solvable non-EMPTY DERIVE seats a SINGLE rail — `IND` — fits the
chip (2/2).**  So DERIVE names one rail and the wave-6 mechanical STOP ("if
DERIVE itself needs 2+ rails, book") does NOT fire here.  This is BECAUSE the
fresh split moved every dist-1/`M_EA` seat to HOLDOUT (§4 discloses this).  **The
test therefore MOVES TO HOLDOUT**, exactly as §64.1 intends.

## 3.  THE REGISTERED PREDICTIONS

| id | prediction | how it is refuted |
|---|---|---|
| **W7-D** | The DERIVE solve names a **single rail** `IND` on every arch-solvable non-EMPTY DERIVE seat. | **already run, HELD** (§2). |
| **W7-1** | **THE DELIVERABLE.** On HOLDOUT (`fz2_replay --leg ret`), `ghost_off = IND` closes **≥ 3** address seats that are NOT wave-6/M10 prior-art (`bad` → 0), OR — if fewer — the closures are named and the shortfall reported as registered. | fewer than 3 fresh closures → booked, not landed. |
| **W7-1a** | **THE HONEST REFUTATION TEST.** The dist-1/`M_EA` HOLDOUT seats — `fz2e/518022`, `fz2e/519072`, `fz2e/530034` — are predicted **NOT** to close by an `IND` rail (register-level evidence: `IND` reproduces `518022`'s chip address at **no** freeze; the chip reads `SS:M_EA=0` while `IND`=a420/e219). If the IND law closed them it would contradict the derivation. | any of the three closing (would reopen the mechanism, not condemn it). |
| **W7-2** | **LOST = 0** over DERIVE ∪ HOLDOUT ∪ a pass-sample. Especially `fz2e/519016` and `fz2e/520040`, which PASS at baseline on `tb_sys` (`bad`=0). | any seed `bad == 0` at baseline, `!= 0` after. |
| **W7-3** | **No still-failing seed's `first` moves EARLIER.** | any decrease. |
| **W7-4** | The **§64.1 four** unmoved (`fz2c/406063`, `fz2c/410047`, `fz2e/518053`, `fz2e/535027`), `fz2c/404040` stays `bad == 0`, and the **M10 LEA-mod3 six** are not claimed. | any move / any claim. |
| **W7-5** | `check_core --core ucore --opcodes 8F.0 --cases 0` = **500/500** (cycles AND arch). | anything below. |
| **W7-6** | `check_core --core ucore --opcodes all --cases 0` = **169,000/169,000**. | anything below. |
| **W7-7** | four HLT sweeps **97 · 93 · 45 · 44 = 279/283** (`--waits 0/1/2/3`). | anything below. |
| **W7-8** | four `evt` cells **200 / 1,200 / 200 / 1,200**, biased **1,200/1,200**, `check_core --opcodes INT.F3AA` **200/200**. | anything below. |
| **W7-9** | `check_fuzz_bank` **PASS, 621 seeds, stable 621 / improved 0 / worse 0**, `gen_drift 0`. | anything else. |
| **W7-10** | `ss_lint --core ucore` **PASS**. IF a flop is added: `SS_VERSION` **0x8E**, `SS_EU_COUNT` **123**, `SS_COUNT` **227**, `SS_TAG` **0x8EE3**, **215 flops**, `SSA_E_GHOST_ADDR = 9'h17E`, 0 UNMAPPED. IF combinational (§1 note): **UNMOVED at 0x8D/226/0x8DE2/214**. | any OTHER constant, or a `reg` unaccounted for. |
| **W7-11** | `r7_lint` **PASS, 0 violations, NO NEW EXCEPTION**, tainted set unchanged (`eu_rd_edge` + 2). `ind_now`/`ghost_addr_hold` carry no live READY. | a violation / new exception / larger tainted set. |
| **W7-12** | `gen_ucore_qsf --check` up to date; `test_artifact` **45/45**. | anything else. |
| **W7-13** | `ulockstep --golden all --cases 50` = **17,350/17,350** INFORMATIONAL (predecessor-effect law `sim/` cannot see). | (not gated). |
| **W7-14** | **NON-VACUITY**: `fz2_replay --perturb 1` diverges every seat W7-1 closes, N of N. | any closed seat surviving perturbation. |
| **W7-15** | **G6 — ONLY IF W7-1 IS MET.** CONTROL build, clean `db`, **TWO DRAWS**: both **≥ 38.0 MHz** (STOP), worst setup **> 0**, **TNS 0.000** every domain setup AND hold, 0 errors / 0 latches / 0 `lpm_divide`. The change swaps a 3-mux rail select for a single register read at the head of the `acc_phys` adder — predicted neutral-to-positive; band ~38.4–40.5 this branch. | any draw < 38.0, or the two draws disagreeing materially. |

### 3.1  THE STOP CONDITION, WRITTEN BEFORE THE SCORE

**If HOLDOUT closes fewer than 3 fresh seats, or any seed is LOST, the law is
BOOKED and the RTL is NOT landed.**  If it is landed and G6 collapses (either
draw < 38.0 MHz), it is booked `UNLANDABLE AS DESIGNED` with the timing
evidence, exactly as the ghost FEED was at 15.3 MHz.  **A booked negative beats
a fitted land.**

## 4.  §64.1 — THE FRESH SPLIT AND THE PRIOR-ART DISCLOSURE

**Population**: the 39 address seats of `fz2_w6_split.json` (`near_package==P4` &
`t1_addr_differs`).  **Fresh split** (`fz2_w7_split.json`):
`sha256(seed_id + "w7").hexdigest()[0] < 8` → DERIVE (22), else HOLDOUT (17);
**20 of 39 seats change side vs wave-6's `sha256(seed_id)`**, so the two splits
are disjoint in partition.

**Prior-art disclosure (honesty, not a loophole):** wave-6 already inspected all
39 seats and named `IND` (dist-0: `408021`, `524030`, `527037`, `534060`) and
`M_EA` (dist-1: `518022`, `519072`, `530034`).  So a HOLDOUT closure on
`527037`/`534060` is **prior-art-informed**; a closure on any OTHER HOLDOUT seat
is a **fresh** closure and is the strong claim.  The dist-1/`M_EA` HOLDOUT seats
are predicted NON-closures (W7-1a).

## 5.  THE SSA BUMP (pre-registered, taken ONLY if a flop is added — §1)

`SSA_E_GHOST_ADDR = 9'h17E` (16-bit), `SS_VERSION 0x8D→0x8E`,
`SS_EU_COUNT 122→123`, `SS_COUNT 226→227`, `SS_TAG 0x8DE2→0x8EE3`, flops 214→215.
0x17E is the next free code (0x17A-0x17D are booked for the feed/hold, §
`v30u_ss_pkg.sv:505`).

## 6.  WHAT IS NOT DONE

* **No board, no flash.**  Offline throughout.  `sim/` is not extended (defunct).
* **The AND free choice is not touched** — wave-4 settled it.
* **`acc_split`/`acc_phys2` are not re-derived** — this is the rail source only.

## 7.  PROVENANCE

| thing | id |
|---|---|
| tree | `f32249a9d0` (`fuzz-v2-on-relanding`, work branch `w7-ghost-retention`) |
| ledger | `sw/testdata/fz2/fz2_failure_ledger_f16_2026-08-10.json` |
| population | 39 address seats, `fz2_w7_split.json` |
| split rule | `sha256(seed_id + "w7")[0] < 8` → DERIVE (22), else HOLDOUT (17) |
| derivation | `fz2_m10.py solve`, DERIVE only, save-state mode 6 |
| score | `fz2_replay.py --leg ret --no-fabric-era-guard` |
