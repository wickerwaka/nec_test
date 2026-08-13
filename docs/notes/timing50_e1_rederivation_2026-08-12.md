# E-1 UNDER READING B — THE RE-DERIVATION, THE DELETION, AND THE HONEST BAND

**Branch `master`, HEAD `1e554257b6` (isolated worktree, HEAD verified).
OFFLINE ONLY.  NO BOARD, NO FLASH.**  `flash_log.jsonl` untouched, no socket
command issued, no Codex consulted, no nested task spawned.  No RTL is edited
in this wave (a parallel worktree owns the `c_int_q` cone), so the only
functional file this document changes is `hdl/nec_test.sdc`.

**§1-§4 of this document are written BEFORE the deletion is made and BEFORE any
build is taken.**  That is the point: a removal with the failed re-derivation
written down beats a silent deletion, and a band quoted against predictions
registered afterwards is not a measurement.

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

`$obs_regs` is **28 registers**: `nec_bus|ad_in_q[19:0]`, `bs_q[2:0]`,
`qs_q[1:0]`, `rd_n_q`, `ube_n_q`, `buslock_n_q` — and, only when
`X1_AD_RETENTION` is defined, `system_large|core_ad_hold[19:0]`.

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

## §5 THE MEASUREMENT

*(filled in after the builds — see §5.1)*

---

## §6 WHAT BINDS NOW

*(filled in after the builds)*

---

## §7 THE READING-B SWEEP OF THE REST OF THE TREE

*(filled in — see below)*

---

## §8 THE RECOVERY PATH FOR THE OBSERVATION CROSSING

*(filled in — see below)*
