# E-1 UNDER READING B — THE RE-DERIVATION, THE DELETION, AND THE HONEST BAND

**Branch `master`, HEAD `1e554257b6` (isolated worktree, HEAD verified).
OFFLINE ONLY.  NO BOARD, NO FLASH.**  `flash_log.jsonl` untouched, no socket
command issued, no Codex consulted, no nested task spawned.  No RTL is edited
in this wave (a parallel worktree owns the `c_int_q` cone), so the only
functional file this document changes is `hdl/nec_test.sdc`.

**§1-§4 and §7-§8 of this document were committed BEFORE the deletion
(`1b4b3d3f67`) and BEFORE any build that scores it (`5825412dff`).**  That is
the point: a removal with the failed re-derivation written down beats a silent
deletion, a band quoted against predictions registered afterwards is not a
measurement, and a recommendation chosen after seeing the band is not a
recommendation.

---

## §HEADLINE

| | |
|---|---|
| **The re-derivation** | **FAILS, by exactly one fabric clock.** `-setup 2` needs a guaranteed `ce → ce_half` gap of **≥ 3**; the contract guarantees **2**. Four escapes worked and closed (§2.4). |
| **The disposition** | **E-1 DELETED** (`a1c63e78e4`). A-1 permanently withdrawn — the deletion is strictly tighter. |
| **THE HONEST BAND** | **CONTROL 41.18 MHz · RETENTION 42.28 MHz**, worst-of-2, both draws identical, TNS 0.000 setup AND hold. **Cost −4.36 / −3.29 MHz.** |
| **What binds now** | `v30u_eu\|upc_opc[*] → nec_bus\|ad_in_q[*]`, 29-40 levels, single-cycle, **60 of the top 60 in both configurations** — F-2's class, restored to visibility |
| **⚠ `c_int_q` no longer binds** | **+9.233 / +9.374** against the binding +6.964 / +7.600. A Phase-2 wave scoped to it would measure **0.00 MHz**. |
| **The ceiling** | a *perfect* fix of the whole observation class reaches **45.17 / 44.10 MHz** and stops at `div_cnt → t1_half2`, a half-period ENABLE arc. **50 MHz is not reachable by any constraint work.** |
| **Zero-behaviour ladder** | **every row MET** — an SDC edit that moved a behaviour row would have been a STOP |
| **Recommendation** | **(c), PAIRED** — report whole-design Fmax (unchanged as the promotion gate) *and* core-domain Fmax, with the RTL item on the core's `ucrom → assign ad_o` cone named beside it. **(a) rejected; (b) does not exist.** |

---

## §0 THE RULING — BOTH PARTS, VERBATIM

**Part 1 (2026-08-12):**

> "With respect to ce/ce_half, you are not allowed to make assumptions based on
> how you are currently setting those clock enables. All you can assume is the
> ce and ce_half will not be asserted at the same time and there will be a one
> cycle gap between each assertion."

**Part 2 — the scope question, answered "B":** the contract is **UNIVERSAL**.
No constraint anywhere in the design, **rig-side included**, may assume the
enable train's shape.

**THE TWO PREMISES, AND THEY ARE NOW THE ONLY ONES ANY TIMING EXCEPTION IN THIS
FILE MAY REST ON — on a `v30u_*` register, on a `nec_bus` register, on
anything:**

* **C-a** — `ce` and `ce_half` are never asserted on the same fabric clock.
* **C-b** — there is at least one idle fabric clock between any two assertions,
  so **successive enable assertions are ≥ 2 fabric clocks apart**.
* **C-c** (derived from the CORE, not from a train; `timing50_census…` §0.1) —
  `ce → ce` is **≥ 4** fabric clocks, because `ce_half`'s only consumer is
  `t1_half2`, which gates `ad_oe_data`, so the core structurally requires at
  least one `ce_half` between consecutive `ce`s.

**WHAT PART 2 KILLS IMMEDIATELY, before any derivation is attempted:**
`timing50_census_2026-08-12.md` §5.2 and `timing50_phase1_results_2026-08-12.md`
§7.3 left the E-1 question open between a *strict* reading and a *rig-local*
reading, on the ground that `nec_bus` **is** this rig's CE generator and might
therefore be entitled to its own divider as a premise.  **Reading B answers
that: it is not.**  With it:

* **AMENDMENT A-1 IS PERMANENTLY WITHDRAWN** (it scoped E-1's `-from` to
  `$v30u_ce`, +2.41 MHz).  It is not merely un-landed; the question it was the
  answer to is closed, and this deletion supersedes it in both directions —
  removing E-1 entirely is strictly tighter than A-1 was.
* **"Currently true" is not a justification.**  E-1 is fabric-confirmed at
  FLASH #19 (`c59c2caf30`), and that is a statement about the rig as it is
  configured today, not a derivation.  It is retained as a *record*, not as a
  *warrant*.

---

## §1 WHAT E-1 IS, AND WHAT IT CLAIMS

`hdl/nec_test.sdc` (pre-deletion, ~line 245):

```tcl
set_multicycle_path -setup 2 -from $v30u_regs -to $obs_regs
set_multicycle_path -hold  1 -from $v30u_regs -to $obs_regs
```

`$obs_regs` is **28 `nec_bus` registers** — `ad_in_q[19:0]`, `bs_q[2:0]`,
`qs_q[1:0]`, `rd_n_q`, `ube_n_q`, `buslock_n_q` — **plus 20 more**,
`system_large|core_ad_hold[19:0]`, in retention builds only (**48** there,
28 in CONTROL).

**THE MECHANISM THE EXCEPTION RELIES ON, stated exactly.**  These samplers are
**free-running**: `nec_bus.sv:201-209` is an `always_ff @(posedge clk)` with no
clock enable, so they re-capture the same slowly-changing source on **every**
fabric clock.  A `-setup 2` on such a destination does **not** claim the path is
two periods long.  It claims something narrower and checkable:

> **the FIRST sample taken after the source launches may be garbage, because
> nobody ever reads it.**

Let the core launch at posedge **L** (its `ce` was asserted in the cycle before).
The sampler writes at **L+1** (possibly garbage, mid-flight), at **L+2** (by
which time `-setup 2` guarantees arrival), and every clock after.  E-1 is
honest **iff no consumer of `$obs_regs` ever reads the value written at L+1** —
i.e. iff no consumer captures at posedge **L+2**.

**The original derivation, now dead** (`nec_test.sdc` lines 143-166): *"every
large-mode consumer is `tick_rise`/`tick_fall`-gated, the earliest reads the
sample at `E(div/2 − 1)`, and with `div = 8` that is 3 periods; `-setup 2`
claims two of the three."*  Every term in that sentence — `div`, `div/2`,
`E(...)` — is a property of `nec_bus`'s divider.  **Reading B forbids all of
it.**

---

## §2 THE HONEST RE-DERIVATION — FROM C-a/C-b/C-c ALONE

### 2.1 The one structural fact the contract lets us use

`system_large.sv:497-501` wires the core's enables to the rig's strobes:

```systemverilog
.CE        (bus_tick_rise),
.CE_HALF   (bus_tick_fall),
```

So **`tick_rise` IS `ce` and `tick_fall` IS `ce_half`** — that is a wiring fact,
readable in the RTL, and it is not an assumption about the train's shape.  It is
also the fact that makes Reading B bite here: the consumers of `$obs_regs` are
gated by exactly the two signals the contract governs, so the contract's
spacing is *the whole of* what may be assumed about when they fire.

### 2.2 The consumer census — enumerated from the RTL, not assumed

Every read of an `$obs_regs` member reachable at `cfg_use_core = 1`,
`cfg_small_mode = 0`:

| consumer | file:line | gate | reads |
|---|---|---|---|
| `ad_early` / `bs_early` / `qs_early` / `ube_n_early` | `nec_bus.sv:217-224` | **`tick_fall` = `ce_half`** | `ad_in_q`, `bs_q`, `qs_q`, `ube_n_q` |
| `mem_addr` / `mem_be` | `nec_bus.sv:481-486` | **`tick_fall && t_state == ST_T1`** | `ad_in_q`, `ube_n_q` |
| `mem_addr_match` (×`EVT_N`) | `nec_bus.sv:576-578` | **`tick_fall`** | `ad_in_q` |
| `cap_record` | `nec_bus.sv:684-721` | `tick_rise` = `ce` | `ad_in_q`, `bs_q`, `buslock_n_q`, `rd_n_q` |
| `mem_wdata`, `mem_cycle_type`, `drive_en`, `t_state` | `nec_bus.sv:422-475` | `tick_rise` | `ad_in_q`, `bs_q` |
| `ad_in_q2` | `nec_bus.sv:203` | **every clock** | `ad_in_q` |
| sticky accumulators | `nec_bus.sv:233-245` | **every clock** (the `else` arm ORs unconditionally) | `qs_q`, `rd_n_q`, `buslock_n_q` |

Two remarks, both stated rather than leaned on:

* The two **every-clock** readers are the RTL falsifier E-1 wrote for itself
  (*"a read of any register in `$obs_regs` that is NOT gated by `tick_rise` or
  `tick_fall`"*) — a **NEAR MISS**, not a hit, because in large mode
  `ad_in_q2`'s value is consumed only by the small-mode write-data latch
  (`:420`) and the accumulators' values only by the small-mode capture fields
  (`:712-715`).  Their **flops still clock every cycle**; only their *values*
  are masked.  E-1 was never refuted by its own falsifier, which is exactly why
  it needed re-deriving rather than re-checking.
* **`cap_record` is `ce`-gated, and under C-c a `ce`-gated consumer is worth
  THREE periods** (below).  If the `ce_half`-gated consumers did not exist,
  E-1 would be derivable at `-setup 3`.  They do exist, and they bind.

### 2.3 The arithmetic

Convention (the census's, unchanged): an enable asserted in cycle *n* makes a
posedge flop capture at posedge *n+1*.

1. The core's `ce` is asserted in cycle *n*.  Its registers launch at posedge
   **L = n+1**.
2. The free-running sampler writes the first post-launch value at posedge
   **L+1 = n+2**.
3. The earliest **`ce_half`** the contract permits after that `ce` is at cycle
   **n+2** (C-b, and only C-b — nothing about `div`).  The `tick_fall`-gated
   consumer therefore captures at posedge **n+3 = L+2**.
4. A posedge flop capturing at **L+2** reads its input **as it stood before
   L+2** — that is precisely the sample the sampler wrote at **L+1**.

> **THE SAMPLE THAT IS ACTUALLY READ HAD EXACTLY ONE PERIOD TO SETTLE.
> `-setup 1` — no relaxation — is the honest constraint.  `-setup 2` IS NOT
> DERIVABLE UNDER READING B.**

**The gap, stated so it is falsifiable in one number:** `-setup 2` on this path
needs the enable train to guarantee **≥ 3** idle clocks between a `ce` and the
next `ce_half`.  **The contract guarantees 2.**  E-1 is short by exactly one
fabric clock — and it is short of a *guarantee*, not of the *current train*
(this rig's `div = 8` supplies 3, which is why the constraint has always
measured true in fabric and always will on this rig).

### 2.4 The escape routes, worked and closed

The brief asked for a genuine attempt, including whether a
synchronizer-shaped argument survives.  Four were tried:

* **(a) A two-flop chain (`ad_in_q → ad_in_q2`).**  **DOES NOT HELP.**  A
  second free-running stage re-times a *metastable* sample; it does not correct
  a *wrong* one.  `ad_in_q2` captures at L+2 whatever `ad_in_q` holds from
  L+1 — the garbage, faithfully.  Metastability and setup are different
  failures and only one of them is a synchronizer's business.
* **(b) Restrict the exception to `ce`-gated consumers.**  Under C-c the next
  `ce` after the launching one is ≥ 4 clocks later, so a `ce`-gated consumer
  captures at posedge **n+5** and reads the sample written at **n+4 = L+3** —
  **three periods**, and `-setup 3` would be derivable.  **UNUSABLE**: it is a
  property of a *consumer*, and SDC exceptions are written on *paths into the
  destination register*.  Every one of the six `nec_bus` samplers has at least
  one `ce_half`-gated consumer (§2.2), so no member of `$obs_regs` can be
  carved out on this ground.  A register with only `ce`-gated readers would
  qualify; **there is none.**
* **(c) A delayed/registered consumer gate.**  Would buy a period.
  **DOES NOT EXIST**: `tick_fall` is combinational off `div_cnt`
  (`nec_bus.sv:176`) and every consumer in §2.2 uses it directly.
* **(d) `core_ad_hold` on its own argument.**  This one **partially survives**,
  and it is written out in §3 because a re-derivation that only reports its
  failures is not a re-derivation.

### 2.5 ⚠ AND ONE ARC IS WORSE THAN SINGLE-CYCLE — WHICH THE DELETION ALSO FIXES

E-1's `-from` is the full `$v30u_regs`, which includes **`t1_half2`**, the
core's one **negedge** flop.  A negedge source launching at *m+0.5* into a
free-running posedge sampler is a **0.5-period** arc by default; E-1 was
telling the fitter it had **2**.  Deleting E-1 restores the default, which STA
computes correctly from the inverted launch clock without being told.  **The
deletion is therefore strictly stronger than A-1**, which fixed only this arc
(at −2.41 MHz) and left the `ce` arcs at 2.

---

## §3 THE ONE FRAGMENT THAT SURVIVES THE CONTRACT — AND IT IS WORTH NOTHING

`core_ad_hold` (retention builds only, `system_large.sv:583-596`) is not a
sampler of a bus; it is a **last-driven-value retainer**:

```systemverilog
wire [19:0] core_ad_drv = core_ad_oe | {4'b0, {16{c_addrv_q}}};
always_ff @(posedge clk)
    for (int i = 0; i < 20; i = i + 1)
        if (core_ad_drv[i]) core_ad_hold[i] <= core_ad[i];
assign core_ad_eff[i] = core_ad_drv[i] ? core_ad[i] : core_ad_hold[i];
```

While a bit is **driven**, `core_ad_eff` takes the live net and the hold
register is **unobservable**.  **Only the last capture before the driver turns
off is ever read.**  So the honest question is not "when is it captured" but
"which capture survives", and that has a contract-only answer for the
`AD_OE`-only bits:

* the OE flop is `ce`/`ce_half`-gated, so `core_ad_oe` changes only at enable
  edges;
* let the data launch at posedge **P** and the OE deassert at posedge **D**;
  the surviving capture is the one at **D**;
* if **P = D** the survivor holds the *previous* data, launched at an enable
  edge **≤ D − 2** (C-b);  if **P < D** then **P ≤ D − 2** (C-b again).

**Either way the surviving capture had ≥ 2 periods, so `-setup 2` IS derivable
for `core_ad_hold` from C-a/C-b alone.**  And then it fails anyway, for two
reasons, both measured or readable rather than argued:

1. **IT IS NOT TRUE FOR BITS [15:0].**  `core_ad_drv` is `core_ad_oe`
   **OR `c_addrv_q`**, and `c_addrv_q` is a **free-running** re-register of
   `hb_ad_dir` (`system_large.sv:381-382`) — it can fall on a clock that is not
   an enable edge, which puts the surviving capture at **L+1** and returns the
   arc to one period.  The derivation survives only on
   **`core_ad_hold[19:16]`**, the four bits with no harness driver.
2. **IT BUYS NOTHING.**  `core_ad_hold` is one flop **upstream** of `ad_in_q`
   on the same combinational cone (`core → core_ad_eff → hb_ad_sample →
   ad_in_q`).  With E-1 gone, `core → ad_in_q` is single-cycle and is the
   *longer* of the two paths, so it binds first whatever `core_ad_hold` is
   given.  **Registered as R-5 below and measured in §6.**

**DISPOSITION: BOOKED, NOT LANDED.**  A four-bit exception that lives only in
the RETENTION configuration — the one that gets flashed — in exchange for a
predicted zero is the *dangerous* direction of an SDC edit for no return.  It
re-opens only if a build shows `core_ad_hold` binding, and §6 is where that is
checked.

---

## §4 THE VERDICT, AND THE PRE-REGISTRATION

> **VERDICT: NO CONTRACT-ONLY JUSTIFICATION EXISTS FOR E-1 AS WRITTEN.**  The
> binding consumers (`ad_early`, `mem_addr`, `mem_addr_match`) are `ce_half`-
> gated, the contract puts the earliest `ce_half` two clocks after the launching
> `ce`, and that is exactly one clock too few.  **E-1 IS DELETED.**

**Registered BEFORE the builds, and reported as registered afterwards:**

| id | prediction |
|---|---|
| **R-1** | **CONTROL** worst-of-2 lands in **[38.0, 42.0] MHz** — the pre-E-1 baseline was **40.13** (`timing_recovery_results_2026-08-11.md` §2) and the only SDC change since is P-3's −0.07. |
| **R-2** | **RETENTION** worst-of-2 lands in **[36.5, 41.0] MHz** — pre-E-1 baseline **38.82**. ⚠ **This band straddles the campaign's 38.0 STOP.** If RETENTION lands below 38.0 the STOP is reported as fired, **and the constraint is still not restored** — an honest constraint that costs Fmax is still the honest constraint (the P-3 precedent, `timing50_census…` §7.3's revert rule). |
| **R-3** | The binding class returns to **`CORE→ANY`**, launching from `v30u_eu|upc_opc[*]` / `upc_page[*]` and latching on `nec_bus|ad_in_q[*]` — the class `timing_recovery_census_2026-08-11.md` F-2 named, and the one E-1 was written to hide. |
| **R-4** | **TNS 0.000 setup AND hold on every domain**, 0 errors / 0 latches / 0 `lpm_divide`, every stage Successful, on all four draws. |
| **R-5** | `core_ad_hold` is **NOT** on the RETENTION build's binding cone (§3.2): its worst incoming slack is **≥** `ad_in_q`'s. If REFUTED, §3's booked narrowing re-opens with a measured value. |
| **R-6** | The zero-behaviour-change ladder is **unmoved, every row**. `hdl/nec_test.sdc` is read by Quartus and by nothing else; **any delta is a STOP**, not a finding. |

**Worst-of-2 per configuration, from a clean `db`, both draws printed**
(`standing_gates.md` §A: one green build is not closure; the same tree has drawn
19.42 and 45.91 MHz).

---

## §5 THE MEASUREMENT — **THE HONEST BAND IS CONTROL 41.18 / RETENTION 42.28**

All draws from a clean `db` through `sw/quartus_gate.py`, Quartus 17.1.0 Lite,
5CSEBA6U23I7, `divclk` constrained at 31.250 ns (32.0 MHz), corner **Slow
1100 mV 100 C**, on the committed tree `a1c63e78e4`, **88-file input manifest
`837b0c700ac2138b…`** (the baseline's is `81d833748e3a1c18…` — they differ by
`nec_test.sdc` and nothing else, which is the check that the deletion reached
the compiler).

| # | configuration | Fmax | worst setup | TNS setup/hold | ALMs | `.rbf` | receipt |
|---|---|---:|---:|---|---:|---|---|
| 1 | CONTROL | **41.18** | +6.964 | 0.000 / 0.000 | 12,271 (29 %) | `ebae5fbfeb280ab8…` | `f57235437d33ae02…` |
| 2 | CONTROL | **41.18** | +6.964 | 0.000 / 0.000 | 12,271 (29 %) | `ebae5fbfeb280ab8…` | `e0ddd68d0aaf7b38…` |
| 1 | RETENTION | **42.28** | +7.600 | 0.000 / 0.000 | 12,317 (29 %) | `65f10e13d23379cb…` | `f26ea5ae09317125…` |
| 2 | RETENTION | **42.28** | +7.600 | 0.000 / 0.000 | 12,317 (29 %) | `65f10e13d23379cb…` | `f6a5a77611f22e8f…` |

**WORST-OF-2: CONTROL 41.18 MHz · RETENTION 42.28 MHz.**  Both draws in each
configuration are identical in Fmax, worst setup, ALMs **and `.rbf` hash**.
**Every draw PASSED G6** — E1 `gen_ucore_qsf --check` PASS, 0 compile errors,
every stage Successful, 0 latches, 0 `lpm_divide`, and **TNS 0.000 on all four
clock domains, setup AND hold**.  The retention receipts **self-label
`RETENTION (X1_AD_RETENTION=1)`, DERIVED from the reports**, and their `.rbf`
**differs** from the control's — E-6/E-9's check that `--verilog_macro` reached
the compiler.

### 5.1 THE COST, STATED WITHOUT SOFTENING

| | with E-1 (`1e554257b6`) | **E-1 deleted (`a1c63e78e4`)** | Δ |
|---|---:|---:|---:|
| CONTROL worst-of-2 | 45.54 | **41.18** | **−4.36 MHz** |
| RETENTION worst-of-2 | 45.57 | **42.28** | **−3.29 MHz** |
| ALMs (CTL / RET) | 12,253 / 12,213 | 12,271 / 12,317 | +18 / +104 |

**THIS IS THE NUMBER THE 50 MHz CAMPAIGN NOW STARTS FROM, and it is 8.8 MHz
short of its target.**  The gap was always there; E-1 was covering it with a
constraint whose premise could not be derived.

### 5.2 THE PREDICTIONS, SCORED AS REGISTERED

| id | registered | measured | |
|---|---|---|---|
| **R-1** | CONTROL worst-of-2 ∈ [38.0, 42.0] | **41.18** | **MET** |
| **R-2** | RETENTION worst-of-2 ∈ [36.5, 41.0] | **42.28** | ⚠ **MISSED — ABOVE the band by 1.28 MHz.** Reported as registered, not restated. The band was set from the pre-E-1 baseline (38.82 at `98bef5844ced`, `timing_recovery_results_2026-08-11.md` §2); the tree has moved since, and **the 38.0 STOP is not approached in either configuration** (nearest margin +3.18 MHz). |
| **R-3** | binding class returns to `CORE→ANY`, `v30u_eu\|upc_opc[*]` → `nec_bus\|ad_in_q[*]` | **`upc_opc[3]~DUPLICATE → ad_in_q[8]`, 28-40 logic levels, +7.600 (RET) / +6.964 (CTL)** — and it owns **60 of the top 60** | **MET** |
| **R-4** | TNS 0.000 setup AND hold, 0 errors / latches / `lpm_divide`, every stage Successful, all four draws | **as registered on all four** | **MET** |
| **R-5** | `core_ad_hold` NOT on the retention binding cone | **`core_ad_hold` worst incoming +8.145 against `ad_in_q`'s +7.600** — 0.545 ns of slack ABOVE the binding path | **MET.** §3's booked narrowing stays booked and is measured worth **zero**. |
| **R-6** | the zero-behaviour ladder unmoved, every row | **every row** (§5.3) | **MET** |

### 5.3 THE ZERO-BEHAVIOUR-CHANGE LADDER — EVERY ROW MET

Run once at the end, as Phase 1 registered the schedule.  `hdl/nec_test.sdc` is
read by Quartus and by no engine, so **any delta would have been a STOP**.

| gate | registered | measured | |
|---|---|---|---|
| `check_core --core ucore --opcodes all --cases 0` | 169,000/169,000 | **169,000/169,000** | ✓ |
| `check_core --core ucore --opcodes 8F.0 --cases 0` | 500/500 | **500/500** | ✓ |
| HLT sweeps `s10-w0/w1`, `s13-w2/w3` (⚠ `--waits 0/1/2/3`) | 97 · 93 · 45 · 44 = 279/283 | **97 · 93 · 45 · 44 = 279/283** | ✓ |
| `ulockstep --golden all --cases 50` | 17,350/17,350 | **17,350/17,350 ALL LOCKSTEP** | ✓ |
| `ghost_launch_law.py score` | 200/200, exit 0 | **200/200 = 100.0 %**, exit 0 | ✓ |
| `r7_lint.py` | PASS, 0 violations | **PASS** — 0 undeclared carriers, 0 undeclared unresolved, 51 `stop` sites clean | ✓ |
| `ss_lint.py --core ucore` | `SS_VERSION` 0x8E / 232 / 220 flops / 0 UNMAPPED | **PASS** — 0x8E, 109×2 + 122×2 + tag = **232**, **220** flops, **0 UNMAPPED** | ✓ |
| `test_artifact.py` | 45/45 | **45/45** | ✓ |
| `gen_ucore_qsf.py --check` | PASS | **PASS** on every build (it is G6's E1) | ✓ |
| `test_quartus_gate.py` | 75/75 | **75/75** | ✓ |

⚠ **`fz2_replay`, `fz2_immaterial falsify` and every leg reading
`sw/testdata/campaigns/fz2*/captures/` COULD NOT RUN** — that corpus is
untracked and lives only in the main checkout.  **Owed, not claimed**, exactly
as `timing_recovery_results_2026-08-11.md` §4 and Phase 1 §5 booked them.
Nothing in this wave changes a byte any of them reads.

---

## §6 WHAT BINDS NOW — AND THE CEILING BEHIND IT

`sw/sta_census.tcl`, `sw/sta_e1_probe.tcl` and `sw/sta_probe.tcl` on each
build's **own** fitted `db`, corner Slow 1100 mV 100 C.

### 6.1 RETENTION — the class table

| class | with E-1 (Phase 1) | **E-1 deleted** | |
|---|---:|---:|---|
| `CORE→CORE` | +36.355 → +26.976 | **+30.789** (`upc_opc[3] → t1_half2`) | not binding |
| `CORE→ANY` | +25.579 | **+7.600** (`upc_opc[3]~DUPLICATE → ad_in_q[8]`) | **BINDS** |
| `ANY→CORE` | **+8.689** (`c_int_q → row_posted`) — *was the binding cone* | **+8.573** (`div_cnt[4] → t1_half2`, the enable arc) | not binding |
| `ANY→ANY` | +8.689 | **+7.600** | = `CORE→ANY` |

**Top-60 population: `CORE→OUT` 60 of 60**, launch histogram `v30u_eu` **60**,
latch histogram `nec_bus` **60**, slacks +7.600 … +7.820 at **33-40 logic
levels**.  It is one cone, and it is the cone
`timing_recovery_census_2026-08-11.md` F-2 named before E-1 existed.

### 6.1a CONTROL — the same cone, on its own fitted `db`

A **third CONTROL draw** was taken for the census (`d89edb0c6f805abd…`) because
a census needs a fitted `db` and each build deletes the last one.  **It read
41.18 / +6.964 / 12,271 again — three agreeing CONTROL draws.**

| class | with E-1 (Phase 1 / census §4.1) | **E-1 deleted** | |
|---|---:|---:|---|
| `CORE→CORE` | +38.626 | **+30.696** (`upc_opc[4] → t1_half2`) | not binding |
| `CORE→ANY` | +27.751 | **+6.964** (`upc_opc[0]~DUPLICATE → ad_in_q[13]`, 29 levels) | **BINDS** |
| `ANY→CORE` | +8.996 (`div_cnt[4] → t1_half2`) | **+9.114** (same arc) | not binding |
| `ANY→ANY` | +8.892 (the JTAG hub) | **+6.964** | = `CORE→ANY` |

**Top-60 population: `CORE→OUT` 60 of 60**, launch `v30u_eu` **60**, latch
`nec_bus` **60** — identical in kind to RETENTION.  `core_ad_hold` is **absent**
in this configuration, as it must be.

**AND THE CONFIGURATION GAP INVERTED AGAIN**: RETENTION (42.28) is **+1.10 MHz
ABOVE** CONTROL (41.18).  Recorded, **not explained** — the same sign inversion
`standing_gates.md` §A has recorded and declined to explain at FLASH #13
(+0.46), #14, and Phase 1 (+0.03).  The mechanism visible here is *which cone
happens to bind*: with E-1 gone both configurations bind on the same cone, and
the CONTROL fit simply placed it 0.636 ns worse.

### 6.2 ⚠ THE FINDING THAT MATTERS TO PHASE 2: **`c_int_q` NO LONGER BINDS**

Measured on the E-1-less builds, `c_int_q`'s worst path is **+9.374 ns**
(RETENTION, 38 levels, → `v30u_eu|row_posted`) and **+9.233 ns** (CONTROL, 37
levels, same destination); the JTAG hub sits at **+8.739** / **+9.522**.  All
four are **above** the observation cone (+7.600 / +6.964) **and above** the
`div_cnt → t1_half2` enable arc (+8.573 / +9.114).

**So on this tree, closing `c_int_q` completely would move Fmax by ZERO.**  It
was the binding cone *with E-1 in force* (+8.689, 60 of RETENTION's top 60),
which is the basis on which
`timing50_phase1_results_2026-08-12.md` §8 recommended it for Phase 2 —
**that recommendation was correct for the tree it was made on and is not
correct for this one.**  Stated here because a Phase-2 wave scoped to `c_int_q`
would measure a benefit of 0.00 MHz and could easily read that as a failed fix
rather than as a fix of a non-binding cone.

### 6.3 THE CEILING — what the whole observation class is worth

`sta_probe`'s ceiling leg, all observation endpoints excluded — **48** in
RETENTION (28 `nec_bus` + 20 `core_ad_hold`, complement 15,157) and **28** in
CONTROL (complement 15,170).  **Both configurations return the same surviving
path:**

> **`nec_bus|div_cnt[4] → v30u_biu|t1_half2`, at +8.573 ns (RETENTION) and
> +9.114 ns (CONTROL) — the ENABLE arc, a true half period, which no
> constraint can relax (`nec_test.sdc`'s own note) and which is RTL-only.**

**In frequency: a PERFECT fix of the entire observation class takes RETENTION
from 42.28 to 44.10 MHz and CONTROL from 41.18 to 45.17 MHz, and no
further.**  Two consequences, both registered here rather than argued later:

1. **§8(a) is capped at +1.82 MHz** even if its equivalence problem were free.
2. **50 MHz is not reachable by any work on the observation path**, and it is
   not reachable by `c_int_q` either. The next wall after the samplers is a
   half-period enable arc into the core's one negedge flop.

---

## §7 THE READING-B SWEEP — EVERY CONSTRAINT AND EVERY LIVE DERIVATION

**Method: `hdl/nec_test.sdc` read top to bottom (it is the design's ONLY `.sdc`
besides MiSTer's `sys/sys_top.sdc`; `input_files()` returns exactly those two),
and every derivation in it re-checked against C-a/C-b/C-c with the divider
covered up.**  Then the same question asked of the documents that quote a
timing claim as current.

### 7.1 `nec_test.sdc` — the four surviving exceptions

| # | exception | derivation | **under Reading B** |
|---|---|---|---|
| 1 | `derive_pll_clocks` / `derive_clock_uncertainty` | — | **N/A** — no enable assumption of any kind. |
| 2 | `-setup 4 -hold 3`, `$v30u_ce → $v30u_ce` | C-c: `ce → ce ≥ 4` | **STANDS.** C-c is derived from the CORE (`ce_half`'s only consumer is `t1_half2`, `v30u_biu.sv:1089`, verified by grep over the whole `ucore/` tree; `t1_half2` gates `ad_oe_data` and selects `ad_o`, `:1056`/`:1062`/`:1080`), plus C-b. It assumes what a platform must do for the core to *work*, not what any train *does*, and its falsifier is FUNCTIONAL. |
| 3 | `-setup 2 -hold 1`, `$v30u_ce → $v30u_half` | `ce` at *n*, launch *n+1*; earliest `ce_half` at *n+2* (C-b); negedge capture *n+2.5* → **1.5** periods | **STANDS**, and it is C-b and nothing else. Measured latch time **46.875 ns = 1.5 × 31.250** (`timing50_phase1_results…` §4.1) — the analyser's arithmetic agreeing with the derivation. |
| 4 | `-setup 3 -hold 2`, `$v30u_half → $v30u_ce` | `ce_half` at *m*, launch *m+0.5*; earliest `ce` at *m+2* (C-b); capture *m+3* → **2.5** periods | **STANDS**, same premise. |
| 5 | `div_cnt → t1_half2` **deliberately NOT excepted** | an enable must be valid at the negedge inside its own cycle — a true half period | **STANDS**, and it is the *safe* direction: relaxing it would be a false PASS. |

**`hdl/sys/sys_top.sdc` — SWEPT AND CLEAN.**  MiSTer's own file, 50 `set_*`
statements: 1 `set_multicycle_path` pair (`*_osd|osd_vcnt*`, 2/1) and the rest
`set_false_path` on `KEY*` / `BTN_*` / `LED_*` / `VGA_*` / `cfg[*]` / the OSD
counters.  **None of them names a `v30u_*`, a `nec_bus` or a `system_large`
register, and none rests on an enable train.**  Nothing to do.

**No other path in the design carries an exception.**  Everything crossing the
boundary in either direction — `nec_bus`/save-state into the core, the core out
to the capture path — is single-cycle, which is correct precisely because those
launch registers are not CE-gated.

**⚠ ONE MAINTENANCE HAZARD FOUND, BOOKED AND NOT FIXED IN THIS WAVE.**
`$v30u_half` is `[get_registers {*|v30u_biu:*|t1_half2}]` — selected **by
name**.  A second `ce_half`-gated flop added to either core module would fall
into `$v30u_ce` by `remove_from_collection`'s complement and be handed
**`-setup 4`** where the contract warrants **1.5** — the identical defect P-3
just fixed, re-introduced silently.  **No gate would see it**: `r7_lint` does
not model exceptions, Verilator does not, and G6 believes the file.
**FALSIFIER, one line of Tcl or one grep**: the count of synthesised
`negedge`-clocked flops in `hdl/rtl/ucore/**` must be **1**, and
`get_collection_size $v30u_half` must equal it.  It is **not** landed here
because the four G6 draws in §5 are already running against the committed
`.sdc`, and an SDC edit taken after the builds is an SDC edit that was not
measured.

### 7.2 The documents — errata booked, nothing rewritten in place

Grepped for `div/2`, `divider of record`, `cfg_clk_div` across `docs/notes/`.
Historical records of *what was believed when* are left exactly as they are
(this repo's standing habit: a ratchet is only readable against its own
history).  What is booked is every place a **dead derivation is quoted as
CURRENT**:

| document | what it says | disposition |
|---|---|---|
| `hdl/nec_test.sdc` E-1 block | the whole `div/2 − 1` derivation, the declared operating triple, the RTL falsifier, the A-1 note | **DELETED with this wave** (`a1c63e78e4`), replaced by the re-derivation and the deletion's reasoning |
| `standing_gates.md` §A, *"THE BAND MOVED 2026-08-11 — E-1"* | E-1 as the live band-setter, plus *"a decision is owed and it is worth 2.41 MHz"* (A-1) | **ERRATUM** — §7.3 below; the band, the A-1 decision and the fabric bar are all superseded |
| `timing50_census_2026-08-12.md` §5.2 | states the scope question and reserves it for the user | **ANSWERED** — Reading B; the section is now history, not an open item |
| `timing50_phase1_results_2026-08-12.md` §7.3, §8 | *"one decision is owed by the user… worth 2.41 MHz"* | **DISCHARGED** — the decision was taken, and against A-1: the deletion is strictly tighter |
| `ghost_preflash20_results_2026-08-12.md` §6.3 | books an *"E-1 analogue for `c_int_q`"* and prescribes the recipe *"show … no path from it is read before E(div/2 − 1); then a `-setup 2 -hold 1` is the same claim E-1 makes"* | **ERRATUM: THE RECIPE IS VOID TWICE OVER.** It names a divider, and the claim it offers to be "the same as" no longer exists. `c_int_q` is an RTL problem and there is no SDC form of it. |
| `timing_recovery_prereg/census/results_2026-08-11.md` | E-1's original derivation and its measurement | **HISTORY, RETAINED.** Its `chip`-side and Fmax measurements are true of the trees they were taken on. **Its derivation is refuted; its numbers are not.** |
| `fz2_flash19_prereg_2026-08-12.md` §… | *"grants 3 sys periods at the divider of record"* | **HISTORY** — it is a pre-registration for a flash that was taken; it is not restated anywhere as a live warrant |
| `m72_downstream_timing_2026-08-12.md` §1 | *"8 at the divider of record, so `-setup 4 -hold 3` is honest there"* | **STILL TRUE AND NOW REDUNDANT** — `-setup 4` no longer *rests* on the divider (C-c derives it), so the sentence is a corroboration rather than a premise |

### 7.3 THE ERRATUM AGAINST `standing_gates.md` §A

Three of its clauses are superseded by this wave and are itemised rather than
edited away:

1. **"CURRENT BAND … CONTROL 44.72 / RETENTION 45.71"** and its successor
   (CONTROL 45.54 / RETENTION 45.57 at Phase 1) — **superseded by §5 below.**
   Both remain true of the trees they were taken on, and both were taken with
   E-1 in the SDC.
2. **"A DECISION IS OWED AND IT IS WORTH 2.41 MHz" (A-1)** — **DISCHARGED, and
   not by taking A-1.** A-1 is permanently withdrawn; the deletion supersedes it
   in both directions.
3. **"E-1 IS NOT PROMOTED TO A FLASH … the registered fabric bar for the first
   bitstream carrying it"** — **MOOT.** FLASH #19 carried E-1 and met that bar;
   the exception is now gone, so no future bitstream carries it, and no fabric
   debt is owed for it. The bitstream on the board is **still FLASH #19's**,
   which **does** carry E-1: this wave flashes nothing, so the board and the
   tree now disagree about the SDC, and **a fabric figure taken on FLASH #19 is
   a figure taken with E-1 in force.**

---

## §8 THE RECOVERY PATH — PROPOSED, NOT IMPLEMENTED

**What has to be recovered, stated as a circuit and not as a number:** the
core's AD publication is **combinational from `v30u_eu|upc_opc[*]` /
`upc_page[*]` through the microcode ROM and the `assign ad_o` mux at 34-39
logic levels** (`timing_recovery_census_2026-08-11.md` F-2/F-3), and it
terminates on a **free-running** flop.  E-1 hid that with a constraint.  Nothing
else changed: **the cone was always there and it is the core's own.**

### 8.1 (a) REGISTER THE OBSERVATION PATH — **NOT RECOMMENDED**

*The shape*: put a free-running pipeline stage between the core's AD and the
samplers (`system_large`, on `hb_ad_sample`, observation-only — the core, the
pads and the read-data path untouched), and compensate on the comparator side.

**⚠ AND THE FIRST THING TO SAY IS THAT THE OBVIOUS FORM OF IT DOES NOT WORK.**
A stage *after* `ad_in_q` shortens nothing — the long path ends at `ad_in_q`'s
`D` pin.  To break the cone the register must go *inside* it, i.e. between
`ad_o` and `hb_ad_sample`, and then what moves is **not a row index but a
SAMPLING PHASE**: the address-phase sample slides from `E(div/2 − 1)` to
`E(div/2 − 2)` and the end-of-cycle sample from `E(div − 1)` to `E(div − 2)`.

**THE COST, QUANTIFIED.**  A phase change is compensable in a comparator only
where the observed pin is stable across the shifted clock, and the one leg that
cannot be reasoned about is the one that matters: **the socket leg, where a
real V30's pins change with its own propagation delay after the CPU clock
edge.**  So the equivalence cannot be *derived* — and least of all by the
`div = 8` argument that would prove it, which is the argument Reading B just
retired.  It has to be **measured**, and the populations it would have to be
measured against are silicon captures that this wave may not re-take:

| population | size | carries row positions? |
|---|---:|---|
| fuzz-v2 live corpus (`fz2c`/`fz2e`) | **3,839 seeds / 11,322,230 scored rows** | yes — every scored row is a per-CPU-clock sample |
| `check_fuzz_bank` replay set | **621 seeds** (623 files − EXC-1) | yes |
| v1 banks `mc1`/`mc2`/`t30-raw`/`t30-brkem` (SUP-1, superseded) | 3,242 seeds | yes |
| timed suites (`v0.1`, `-w1`, `-w3`, `EB`, the four `evt` cells, `w1evt-biased`) | 169,000 + 1,200 + 1,200 + 200 + 200 + 1,200 + 200 + 1,200 cells | yes |
| HLT delay sweeps + the S16 display walk | 283 + 1,371 cells | yes |
| `b2`/`b3` priority tranches, `check_ab_hw` first light, `check_ab_sim` | 188 + 178 + 800 + 187 rows | yes |

*(sizes as registered in `standing_gates.md` §B and CLAUDE.md; the fz2 capture
corpus is untracked and is not present in this worktree, so these are quoted
from the registry and not re-counted here.)*

**AND IT IS CAPPED AT +1.82 MHz (RETENTION) / +3.99 MHz (CONTROL), MEASURED
(§6.3).**  With every observation endpoint excluded, the worst surviving path in
BOTH configurations is `div_cnt[4] → t1_half2` at **+8.573 / +9.114 ns**, so a
*perfect* fix of the entire class takes the band to **44.10 / 45.17 MHz** and
stops there, against a wall no constraint can move.

**VERDICT: it trades a constraint whose premise was unprovable for an
instrument change whose equivalence is unprovable offline, against an 11.3
million-row silicon corpus and a board this wave may not touch — for a measured
ceiling of +1.82 MHz that still leaves the campaign 5.9 MHz short.  That is the
wrong direction of trade.**

### 8.2 (b) A SYNCHRONIZER CHAIN WITH A CONTRACT-ONLY JUSTIFICATION — **UNAVAILABLE**

**Not "not recommended" — unavailable, and §2.4(a) is the proof.**  A
synchronizer re-times a *metastable* sample; it does not correct a *wrong* one.
The tree already has the two-flop shape (`ad_in_q → ad_in_q2`, free-running)
and it buys nothing: `ad_in_q2` faithfully captures whatever garbage `ad_in_q`
took at L+1.  For a chain to buy a period the *consumer's* gate would have to be
delayed, and every consumer gate is combinational off `div_cnt`
(`nec_bus.sv:176`).  **The only structure that would work is one that makes the
guaranteed `ce → ce_half` gap 3 instead of 2, and that is a change to the
contract, i.e. a question for the user and for M72, not a circuit.**

### 8.3 (c) ACCEPT IT AS THE RIG'S HONEST BOUND AND RE-SCOPE — **RECOMMENDED, WITH ONE QUALIFICATION THAT MATTERS**

*The shape*: stop treating the whole-design worst path as the 50 MHz target's
subject.  Report **two** numbers, both from the same build, both receipted:

* **`WHOLE-DESIGN Fmax`** — what G6 already computes and gates (E3 ≥ 32 MHz, E4
  worst setup > 0, E5 TNS 0.000). **This is unchanged and stays the promotion
  gate.** It is the number the board must satisfy, and the rig runs at 32 MHz.
* **`CORE-DOMAIN Fmax`** — the worst path with both endpoints inside
  `v30u_eu`/`v30u_biu`, the class `sta_census.tcl` already reports as
  `CORE→CORE`. It is what a downstream integration inherits, and on this tree it
  has carried **+36 to +39 ns** while the design bound at **+8.7**.

**Honestly stated, "Fmax" would then mean**: *the ucore's own logic closes at
X MHz; the nec_test RIG closes at Y MHz, bound by cone Z.*  Two numbers, each
with its cone named, and neither standing in for the other.

**THE QUALIFICATION, AND IT IS WHY THIS IS NOT A FREE RE-SCOPING.**  The cone
that binds is **not** wholly the rig's.  Its *latch* register
(`nec_bus|ad_in_q`) is rig-only — M72 replaces `nec_bus` wholesale — but its
*launch* side, the 34-39 levels from `upc_opc` through `ucrom` to `assign
ad_o`, is **the core's own output cone, and every integration inherits it**;
M72 registers the core's AD on its own adapter flops (`v30_bus|addr_neg`,
`ube_neg` — census §6.1) and therefore has a crossing of the same class.  So
(c) is honest **only if it is paired with the RTL item below**; on its own it
would re-scope a real core problem into invisibility.

**THE PAIRED RTL ITEM, named and NOT opened here**: shorten or register the
core's AD publication cone — the `v30u_ucrom` → `assign ad_o` path.  It is the
same item `timing_recovery_results_2026-08-11.md` §7 ends on (*"the band lost
across the campaign went into `assign ad_o`"*) and the same one
`timing50_census_2026-08-12.md` §8 lists as the ucrom-as-M10K lever.  It is
**behaviour-visible** (a registered `ad_o` moves the pins in time), so it needs
its own campaign with a silicon-match bar, not a phase of this one.

**RECOMMENDATION: (c), paired.**  It costs nothing, hides nothing as long as
both numbers are printed with their cones, and it is the only one of the three
that does not spend a silicon corpus or assert something unprovable.  **(a) is
rejected on the re-goldening cost AND on a measured ceiling of +1.82 / +3.99 MHz;
(b) does not exist.**

**AND THE MEASUREMENT MADE THE PAIRING NON-OPTIONAL.**  §6.3's ceiling says the
observation class is worth **1.82 MHz in total** and the next wall behind it —
`div_cnt → t1_half2`, a half-period *enable* arc — is RTL-only as well.  So:

* **50 MHz is not reachable by ANY constraint work, and now that is MEASURED
  rather than argued**: the ceiling behind the whole observation class is
  44.10 / 45.17 MHz.  It was not reachable before this wave either; E-1 made
  the tree *look* 3-4 MHz closer to it.
* **Nor is it reachable by `c_int_q`** (§6.2: +9.374, not binding).
* **The only levers left are the three RTL ones**, in the order the measurement
  ranks them: the core's `ucrom → assign ad_o` cone (worth up to 1.82 RET /
  3.99 CTL before the next wall), then `div_cnt → t1_half2` (register `ce_half`, or retime
  `t1_half2` to a posedge flop — both **behaviour-visible**), then the ucrom as
  an M10K (**a cycle of latency**, banned by the zero-behaviour terms *by their
  terms*).  **Each needs its own campaign with a silicon-match bar, and none is
  opened here.**
