# THE 8F GHOST FAMILY — PRE-REGISTRATION, committed BEFORE the RTL is written

Branch `fuzz-v2-on-relanding`, base `4d5d007c5a`.  Offline: no board, no flash.
Quartus IS in scope; G6 is the final gate.

The last 3 of the 19 mechanisms of `5403671558`.  L1 (`944b6b3c39`) landed the
other 16 and named these three as withheld, with the reason MEASURED, not
suspected (relanding SPIKE `539c6f8406`).  This document registers what will be
built, what is predicted, and what refutes it, **before any of it is measured**.

---

## §0  STANDING DESIGN PRINCIPLE (verbatim)

> SIMPLICITY: this is 80's era hardware — nothing on the die is wasted.
> Complex or confusing observed behavior is likely simple systems interacting
> in ways not yet understood.  A large fitted table, a many-cased rule, or a
> per-opcode special case is a signal of misunderstanding, not a deliverable.

---

## §1  A CORRECTION TO THE BRIEF, MADE BEFORE ANY WORK — `sim/` DOES **NOT**
## IMPLEMENT THE 8F GHOST FAMILY

The brief states, twice, that "`sim/` already implements all three and is the
behavioural reference here".  **It does not.**  Verified against the artifact,
not recall:

* `git show 5403671558 --stat` touches exactly ONE file under `sim/`:
  `sim/exec_impl.h`, 22 lines.
* That hunk is the **REP+TF withdrawal** (`cond_true`'s `again` restructure),
  and L1 already landed it — `944b6b3c39`'s manifest names it: *"the REP+TF
  withdrawal — BOTH halves, `v30u_eu_cond.svh` AND `sim/exec_impl.h`"*.
* `grep -n 'ghost' sim/*.h sim/*.cpp` returns six hits, all of them prose
  comments predating this campaign (`biu_timed.h:930`, `exec_impl.h:1417`,
  `state.h:177`, `loader_impl.h`), and **no mechanism**: there is no
  `ghost_rd_discard`, no feed, no ModR/M hold, no stale-address rail in the
  model.

**Consequence for the method.**  The semantic reference for these three
mechanisms is `5403671558`'s own RTL plus the silicon goldens — there is no
model column to check a re-timing against, and the brief's instruction to
"check against the model's semantics" cannot be executed as written.  The
substitute, which is stronger, is an **RTL-vs-RTL A/B**: build the FAITHFUL
transliteration of `5403671558` and the §73-TREATED form from the same tree and
score both on every measurable population.  That is what §5 registers.

It also means `ulockstep --golden 8F.0` compares an engine that HAS the
mechanism against a model that does NOT — see P3a in §4.

---

## §2  WHAT IS MEASURABLE ON THIS BRANCH — the fuzz column is 14 seeds wide

Registered before the change, because a denominator discovered after a result
is not a denominator.  Measured this sitting, receipt `ad20d79bfcfa8771…`:

| corpus | seeds offered | seeds SCORED | why |
|---|---|---|---|
| `timed_fuzz` default banks (mc1, mc2, t30-raw, t30-brkem) | 3,242 | **0** | SUPERSEDED (SUP-1); `--include-superseded` returns the seeds, not the replay |
| `--seeddir sw/testdata/t4/b2-tranche/seeds` | 216 | **0** | `GEN_DRIFT=216` — plan D9's unconditional `0F` scrub moved every v1 image sha256 |
| `--bank fz2c,fz2e` (the C-11 promoted bank) | 623 | **14** | `OPEN_BUS=609`, `EXACT=11`, `DIVERGE=3` |
| `fz2_w1 bars` census / enriched | 3,840 lines | n/a | FROZEN BOARD CAPTURES.  `results.jsonl` is what the board wrote on FLASH #12; no RTL edit can move a bar, and one that moves is an instrument finding |

**So the per-mechanism benefit measurement the brief asks for — the first any
of the 19 has ever had — has a denominator of FOURTEEN.**  It is reported
seed-by-seed anyway, because 14 named seeds is a fact and a percentage of 14 is
not.  The b2 tranche and the v1 banks are reported as NOT MEASURABLE, not as
zero.

---

## §3  BASELINE, THIS TREE, THIS SITTING (all figures re-measured, not quoted)

Verilator receipt `ad20d79bfcfa8771…` throughout.

| gate | baseline |
|---|---|
| `gen_ucore_qsf --check` | up to date |
| `r7_lint` | **PASS** — 17 BIU→EU nets, 1 carrier (`eu_rd_edge`, declared), 3 tainted signals, 51 `stop` sites, 0 violations |
| `ss_lint --core ucore` | **PASS** — 101×2 BIU + 121×2 EU + tag = **223**, `SS_VERSION` **0x8B**, `SS_TAG` **0x8BDF** |
| `ss_flopcensus` | **211** architectural flops — BIU 83/83 mapped; EU 128 → 126 mapped + 2 whitelisted, 0 UNMAPPED |
| `test_artifact` | **45/45** |
| `check_core --opcodes 8F.0 --cases 0` | **500/500** (cycles 500, arch 500) |
| `check_core --opcodes INT.F3AA` | **165/200** — first-div `(17,'qop')`×19, `(19,'qop')`×16 |
| `check_core --opcodes all --cases 0` | **168,965/169,000** |
| `ulockstep --golden 8F.0 --cases 50` | **50/50 LOCKSTEP** |
| `ulockstep --golden INT.F3AA --cases 50` | **45/50** |
| `ulockstep --golden all --cases 50` | **17,345/17,350** (the 5 are INT.F3AA's) |
| four HLT sweeps (`check_core --suite-dir … --waits N`) | **97/97 · 93/95 · 45/46 · 44/45 = 279/283** |
| `timed_fuzz --core ucore --bank fz2c,fz2e --evt-replay` | REGISTERED **8/11**, EVT **3/3**, COMBINED **11/14**; `OPEN_BUS` 609; BOUND WARNINGS 2 (`fz2e/520000`, `fz2e/522003`) |
| `fz2_w1 lint` | PASS, 0 hits, 48 stratum rows |
| `fz2_w1 bars` | **8/11 MET**, missed C-1, C-3, C-6; census rows-exact 94.17 / arch-exact 87.71 / unscoreable 92; enriched 94.48 / 88.61 / 273 |
| `test_fuzz_classify` / `test_fuzz_accept` | PASS 0 / PASS 0 |
| `check_fuzz_bank` | PASS, 623 banked, stable 623, gen_drift 0 |
| G6 (L1's own, `944b6b3c39`) | PASS 42.02 MHz, worst setup +7.454 ns, TNS 0.000 setup AND hold, ALMs **11,917/41,910 (28 %)**, receipt `d0e67ffea7edbff4…` |

---

## §4  WHAT WILL BE BUILT — the §73 treatment, in three parts

The family is landed in its dependency order (read → feed → hold), plus
`eu_seg2` / `pr_seg2`, which L1 dropped as provably-equal-without-the-feed and
which the feed makes live again.  `tb_v30_core.sv`'s `V30_UCORE` observer stays
REFUSED on L1's evidence and is NOT part of this landing.

### P2a — the four published rails move onto the BIU's OWN registered READY

`5403671558` published `eu_ghost_full`, `eu_ghost_stack_first` and `eu_rd_wait`
off the **live `ready` pin**.  That is the R7′ shape and `r7_lint` check (a)
refuses it.  The treatment is not a new mechanism: the BIU's header already
declares its own discipline —

> "the CPU registers READY at the end of every clock" … "`ready_prev` is the
> registered READY pin" (M2r, `v30u_biu.sv` header)

— and `r_ready_prev` is an existing, already-SSA-mapped flop
(`SSA_B_READY_PREV`).  The three ghost rails were the ONLY place in the module
reading the pin directly.  Putting them on `r_ready_prev` costs **ZERO new
flops, ZERO new SSA addresses and no BIU version bump**, and `r7_lint`'s walk
terminates on it because it is a flop.

Registered predictions about what that costs, derived from the rig's READY law
("READY is low from T1 entry and high from the LAST Tw", `v30u_biu.sv` header)
BEFORE measuring:

* **`eu_ghost_stack_first` is EXACTLY unchanged.**  It samples at `TS_T3`, and
  on a fetch `ready@T2 == ready@T3` under that law (both `(w == 0)`).
* **`eu_ghost_full` differs on exactly one clock** — the LAST `Tw` of a waited
  fetch, where the live form falls to 0 and the registered form is still 1.
* **`eu_rd_wait` differs on exactly one clock** — the clock READY rises during
  a non-fetch access.
* `eu_ghost_idle` was already register-only (`r_ts == TS_T4`) and does not move.

### P2b — `acc_split` splits into a bus value and a write-accounting value

The ghost terms reach `stop` through the ADDRESS path
(`eu_ghost_full → ghost_relax → acc_off → acc_phys → acc_split → row_wr_add →
wr_after → retire_ok_e → bnd_row → at_bnd → bnd_fire → stop`, 2 sites in
`v30u_eu_row.svh`).  `row_wr_add` is gated on `row_is_wr || row_is_wb` and
`ghost_read_stale_alu` requires `row_is_read`, so the two are disjoint IN VALUE
and only joined IN TEXT.  A ghost-free `acc_split_wr` off a ghost-free
`acc_phys_nog` drives the write accounting; the ghost-aware `acc_split` drives
`eu_split` / `eu_pair2` only.  **This is exact, not an approximation**, and it
removes a real cone as well as a lint edge.

### P2c — S_PRERD's ghost-late arm writes ONLY register `D` pins

This is the one place where §73 and the mechanism genuinely trade, and it is
registered as a deliberate difference from `5403671558`, not hidden.

`ghost_preread_late` is built from `eu_rd_edge` — §73's ONE declared carrier,
which `r7_lint` check (b) deliberately does NOT except ("if it ever gates
`stop`, R7′ is re-opened").  In `5403671558` the late arm sits at the head of
`S_PRERD`'s `if / else if` chain, so when it fires it takes `stop` from 1 to 0
and the loader chain CONTINUES into `S_ENTER` on the same clock.  **That is
R7′ by construction, not a lint artifact**: the live pin releases eleven more
chain positions.  No re-timing removes it, because READY at clock *c* is not
knowable before clock *c*.

The treatment: the late arm is moved BELOW the ordinary arms and writes only
`opr_n`, `opr_loaded_n`, `row_posted_n`, `ghost_rd_discard_n` and `st_n` — all
register `D` pins, which is exactly what §73 admitted `eu_rd_edge` for.  No
`stop` assignment sits under it, and the ordinary arms' side effects are
suppressed by a guard that contains no `stop`.

**REGISTERED CONSEQUENCE, stated before measurement:** OPR takes the data-edge
word on the SAME clock as `5403671558`, and `st` advances on the SAME clock,
but the chain does not continue — `S_ENTER` runs on the FOLLOWING clock instead
of the same one.  If that costs a seed, it is a FINDING about the mechanism and
will be reported as one, not patched around.

---

## §5  THE A/B — the faithful form is BUILT and MEASURED, not assumed

Because there is no model column (§1), the treatment is checked against a
FAITHFUL transliteration of `5403671558` built from this same tree.  The
faithful form is **not landed** (it fails `r7_lint` by construction) but its
diff is retained at `sw/testdata/relanding/ghost8f_faithful.patch`, in the same
role as the spike's `build1_noghost.patch`, and every §3 gate is run on it.

Columns reported, seed by seed and cell by cell:

    A = baseline (HEAD, no family)          — §3 above
    B = FAITHFUL 5403671558 form            — measured, not landed
    C = §73-TREATED form                    — the deliverable

**A→B is the mechanism's benefit.  B→C is the treatment's cost.**  This is the
first per-mechanism benefit measurement any of the 19 has had; the original
landed all nineteen at once with no ledger entry.

---

## §6  THE SAVE-STATE MAP — pre-registered constants

| constant | before | after |
|---|---|---|
| `SS_VERSION` | `0x8B` | **`0x8E`** |
| `SS_BIU_COUNT` | 101 | **101** (unchanged — P2a adds no flop) |
| `SS_EU_COUNT` | 121 | **126** |
| `SS_COUNT` | 223 | **228** |
| `SS_TAG` | `0x8BDF` | **`0x8EE4`** |
| `ss_flopcensus` total | 211 | **216** (BIU 83; EU 128 → 133, 131 mapped + 2 whitelisted) |

Addresses, and the derivation of the version:

* `0x176` `SSA_E_GHOST_DISCARD` — the reserved occupant taking the code it was
  reserved for.  `v30u_ss_pkg.sv` says so in as many words, so **the address
  never means two things and no skip is owed for it**; `ss_addr_of`'s
  `>= 9'h176 → +1` hole is REMOVED and no symbol above it is renumbered
  (`0x177`–`0x179` keep their addresses by arithmetic).
* `0x17A` `SSA_E_GHOST_FEED`, `0x17B` `SSA_E_GHOST_READY`.
* `0x17C` `SSA_E_OPC_RM_VALID`, `0x17D` `SSA_E_OPC_RM_BYTE`.

**Three bumps, one per appended GROUP** — read (`0x8B→0x8C`), feed
(`0x8C→0x8D`), hold (`0x8D→0x8E`) — which is the numbering rule L1 wrote down
and used.  The arrival at the same `0x8E` that `5403671558` reached is a
coincidence of arithmetic and is not a claim of stream compatibility: L1's map
is not `5403671558`'s (L1 spent a version on the `SSA_E_IRQ_LATCH` widening
that `5403671558` did not), and the two v14 streams are NOT interchangeable.

---

## §7  THE GATES, cheapest falsifier first — STOP AT THE FIRST RED

```
 1. gen_ucore_qsf --check
 2. r7_lint                     MUST PASS, NO NEW EXCEPTIONS.  If it cannot
                                pass without one: STOP and report.
 3. check_core --build --core ucore   (+ receipt id)
 4. ss_lint --core ucore        against §6
 5. test_artifact               45/45
 6. check_core 8F.0 --cases 0   500/500 must HOLD
    check_core INT.F3AA         165/200 must NOT WORSEN
 7. ulockstep --golden 8F.0,INT.F3AA --cases 50
 8. check_core --opcodes all --cases 0   >= 168,965
    ulockstep --golden all --cases 50    >= 17,345
 9. the four HLT sweeps         >= 279/283
10. fz2 offline legs: fz2_w1 lint; bars (NO bar's measured may change);
    test_fuzz_classify; test_fuzz_accept
11. the fuzz delta, §5, seed by seed
12. G6, TWO draws, receipts retained
```

---

## §8  PREDICTIONS AND THEIR REFUTATION CONDITIONS

**P1 — `8F.0` holds.**  `check_core --opcodes 8F.0 --cases 0` stays 500/500 in
both B and C.  *Refuted by* any cell lost.  The 8F.0 goldens are silicon and
the ghost address is a documented don't-care in the comparator
(`closure_checkpoint.md`, "8F.0 mod3 ghost-read address — RESOLVED
2026-07-13"), so the family should be invisible to them.

**P2 — `INT.F3AA` does not worsen.**  165/200 in both B and C.  *Refuted by*
164 or fewer.

**P3a — `ulockstep --golden 8F.0` MAY DIVERGE, and if it does it is EXPECTED.**
The brief predicts the ghost read owns the original 45/50.  Measured today it
is **50/50**, so there is nothing for the ghost to "own" at the baseline: the
prediction to register is therefore the OTHER direction — with the family in,
`8F.0` is predicted to **FALL BELOW 50/50**, because `ulockstep` compares the
RTL against `sim/`, and `sim/` does not have the mechanism (§1).  A fall here
is NOT a silicon-match regression and must not be reported as one; the silicon
bar for `8F.0` is gate 6, which must hold.  *Refuted by* `8F.0` staying 50/50
**while** `check_core 8F.0` also holds and the family is provably reachable —
which would say the mechanism is inert on this population.

**P3b — reachability.**  At least one of the family's five flops must be
observed non-zero on some scored case; an unreachable mechanism is a landing
that proves nothing.  *Refuted by* every gate matching the baseline cell for
cell in BOTH B and C, which would make the landing vacuous.

**P4 — `check_core all` and `ulockstep all` do not worsen.**  >= 168,965 and
>= 17,345 respectively, EXCEPT for `8F.0`'s ulockstep cells under P3a, which
are reported separately and named.  *Refuted by* any other form losing a case.

**P5 — HLT sweeps unmoved.**  279/283.  *Refuted by* 278 or fewer.

**P6 — no fz2 bar moves.**  The lines are frozen board captures.  *A bar that
moves is a RIG-INTEGRITY FINDING*, not a result, and stops the sitting.

**P7 — the fuzz column.**  COMBINED >= 11/14.  Registered honestly: with a
denominator of 14 this gate has almost no power, and no percentage computed on
it will be quoted.  *Refuted by* 10/14 or fewer.

**P8 — G6.**  PASS on the CONTROL build, TWO draws, receipts retained.
Predicted band **>= 38 MHz** (L1's own tree drew 42.02 twice; the spike's
family-removed tree drew 41.89), required bar **>= 32 MHz**, worst setup > 0,
setup AND hold TNS 0.000, 0 errors, 0 latches, 0 `lpm_divide`.  ALMs predicted
**11,917 + 0…350** (the family is real logic, not the spike's constant tie-off,
so the spike's 5-ALM delta between its two tied-off builds is NOT the
prediction).  **REFUTATION CONDITIONS, any one of which says the treatment
FAILED:**
  * measured Fmax below **32 MHz**; or
  * any failing path launching from `system_large|c_ready_q` — the RED tree's
    own signature (`539c6f8406`: 63.65 ns against a 31.25 ns relationship into
    `v30u_eu|r_kind[1]`); or
  * setup or hold TNS non-zero on any domain.
  A materially lower Fmax with no `c_ready_q` launch is NOT automatically the
  treatment failing — `standing_gates.md` §A and §74.4a say the same tree has
  drawn 19.42 and 45.91 MHz and that A&S combinational counts are not
  reproducible run to run — but it IS reported as registered and not restated.

**P9 — the treatment's own cost.**  B and C are predicted **identical on every
gate in §7**.  *Refuted by* any cell where they differ — which, if it happens,
is the precise statement of the conflict §2c anticipates and is the deliverable
in its own right.

---

## §9  DISCIPLINE FOR THIS SITTING

* Commit forward only; no amendments.  This document is committed BEFORE the
  first line of RTL.
* Report as registered, never restated.  Every number carries its denominator
  and every artifact carries its receipt id.
* If `r7_lint` cannot pass without a new exception, or if B and C differ
  behaviourally, **STOP AND REPORT** — a precisely-stated conflict is a better
  deliverable than a forced landing.
