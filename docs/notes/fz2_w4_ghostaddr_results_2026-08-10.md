# fz2 WAVE-4 — THE 8F GHOST-READ **ADDRESS** CONE — RESULTS, AS REGISTERED

Pre-registration: `docs/notes/fz2_w4_ghostaddr_prereg_2026-08-10.md`, committed
`0cdbb9394a` **before the first line of RTL**.  Read that first; this document
answers it clause by clause and does not restate it.

Branch `fuzz-v2-on-relanding`, base **`32128b57b4`** (the worktree provisioned
at `master`/`29dcc5b05f` and was reset; `git rev-parse HEAD` verified).
Offline throughout; **no board, no flash**.

⚠ **EVERY POST-RTL `fz2_replay` FIGURE BELOW IS OFFLINE AND CROSS-ERA** and
carries `--no-fabric-era-guard`, which is **said so** beside every number.  The
BASELINE is the exception: at `32128b57b4` the **FABRIC ERA GUARD PASSES**
(87/88 inputs identical, the 88th the Quartus-rewritten `.qsf`, exempt) because
no RTL had moved since FLASH #16.  No fabric figure may be quoted against the
landed tree until a re-flash.

---

## §0  HEADLINE

**WHAT LANDED: ONE deletion in `hdl/rtl/ucore/v30u_eu.sv` — `ghost_relax` is
GONE and the AND is UNCONDITIONAL.**

```
-wire [15:0] ghost_relax = eu_ghost_full ? 16'hFFFF
-                         : eu_ghost_idle ? ((pe_op8 ? 16'hC000 : 16'h8000) |
-                                            (ghost_next_byte ? 16'h0080 : 16'h0000))
-                         : 16'h0000;
 wire [15:0] ghost_bus_off = ghost_uses_mul_hi ? (tmpa & opr)
                             : (eu_ghost_idle && !q_ripe) ? gpr[R_SP]
-                            : (ghost_off & (gpr[R_SP] | ghost_relax));
+                            : (ghost_off & gpr[R_SP]);
```

**Four magic constants and two cases deleted.  No flop, no signal, no
save-state address, no `sw/` change, no new arm.**  This is the brief's
preferred outcome stated in its own terms — *a partial close that DELETES
fitted cases beats a full close that adds one* — and its cost is reported in
§3, not buried.

**G6, THE GATE THAT DECIDES IT: PASS ON BOTH DRAWS — 39.05 MHz, +5.64 ns, TNS
0.000, identical to the digit, the second on a CLEAN tree.**  Clear of the
38.0 MHz STOP.  §5.

**EIGHTEEN registered predictions: 13 MET, 1 PARTIAL, 1 MISSED, 2 REFUTED
(one of them favourably), 1 held-as-a-non-claim.**  The misses are reported as
registered and are not restated:

| | |
|---|---|
| **W-1 PARTIAL** | the ADDRESS closes **3 of 3** of M10's named seats; the SEED closes **2 of 3** |
| **W-4 REFUTED** | 19 still-failing seeds' first divergence moves EARLIER |
| **W-5 MISSED** | 2 net closures on the 39 address seats; the bar was ≥ 3 |
| **W-16 REFUTED** | favourably — `ulockstep 8F.0` did **not** fall; it holds 50/50 |
| **the cost** | Σ diverging rows **123,015 → 124,856 (+1,841)**, of which **1,801 are two seeds that W-2 named IN ADVANCE as seats the AND does not govern** |

---

## §1  THE SEAT LIST — THE BRIEF'S "~34" IS CORRECTED UPWARD TO 51 / 39

Re-derived from `fz2_failure_ledger_f16_2026-08-10.json` with the **RTL's own
predicate** (`8F` with `mod == 3`) over **every family**, not just `E1`:

* **51 of 116 ledger failures** are 8F-ghost-proximate within six `F` pops;
* **39 are ADDRESS seats** (the forking cycle's own `T1` address differs);
* **12 are same-address** and were **NOT claimed** (prereg W-6);
* `E1` reproduces M10's F15 partition **exactly** on F16 — 41 seats, 31 P4′,
  10 residual, distance histogram `[(0,8),(1,18),(2,3),(3,2)]`;
* **20 of the 51 lie outside `E1`** and were unavailable to M10, whose survey
  is `E1`-only by construction;
* base rate 5.84 % predicts ≈ 6.8 coincidences among 116; **this package does
  not claim to know which 7 of the 51 they are** (and §3.3 finds one).

---

## §2  THE LADDER — ALL FOUR BUILT AND SCORED, AND THE RULE PICKED V1

654 replayed seeds, `--leg ret`, `--no-fabric-era-guard` on V1–V4:

| | cumulative change | Verilator receipt | CLOSED | **LOST** | Σ diverging rows |
|---|---|---|---:|---:|---:|
| **base** | HEAD | `9b659ba3edb81c7f…` | — | — | 123,015 |
| **V1** | `ghost_relax` deleted, AND unconditional | `504cb67960bce1f9…` | **2** | **0** | 124,856 |
| **V2** | V1 + drop `(eu_ghost_idle && !q_ripe) ? SP` | `c79b37d4a774e5d9…` | 2 | **1** | 126,927 |
| **V3** | V2 + drop `ghost_uses_mul_hi` → **ONE TERM** | `9ccbb41f547aabb1…` | 2 | **1** | 126,927 |
| **V4** | V3 + drop the `pe_opc_reg == 8'h8e` case | `08762085ebeac268…` | 2 | **1** | 126,927 |

**§2.4's mechanical rule — fixed before any variant was built — selects V1**:
it is the deepest with `LOST = 0`.  V2's loss is `fz2c/410034` (0 → 4 rows).

### §2.1  TWO FITTED CASES ARE MEASURED **INERT**, AND ARE DELIBERATELY LEFT IN

**V3 and V4 score BYTE-IDENTICALLY to V2 on all 654 seeds.**  So the
`ghost_uses_mul_hi` arm (the `14'h0104` PLA class, fitted on the v1 `mc2` banks
that **SUP-1** retired and which cannot be replayed on this branch) **and** the
`pe_opc_reg == 8'h8e` special case are **both unreachable by this corpus**.

They are **NOT deleted.**  "Inert on 654 seeds" is not "dead", and deleting a
case on the strength of a population that never reaches it would be the same
mistake in the other direction — a claim with no evidence under it.  **This is
booked, with the measurement, as the cheapest next deletion the moment a
population that reaches them exists.**  It is written into the RTL beside the
expression so the next sitting does not re-run the ladder.

### §2.2  THE ONE TERM IS MEASURED, AND IT IS NOT UNIVERSAL

`ghost_bus_off = ghost_off & gpr[R_SP]` (V3) is reachable and costs nothing
that V2 did not already cost.  But **the AND is not universal and this landing
does not claim it is**: M10 §5.2 measures `fz2e/530034` performing **no AND at
all** on a **different rail**, and `fz2e/526054` forking on the **segment**
with identical offsets.  What is settled here is only the second of M10's two
free choices — *whether the AND happens* — and only in the direction **"not by
a mask"**.  *Which rail* is untouched and remains M10's.

---

## §3  THE PER-SEAT RESULT ON THE LANDED TREE

`fz2_replay --leg ret --all-failures --pass-sample 550 --no-fabric-era-guard`,
654 seeds, **0 errors**, `tb_sys` receipt **`3abecb7b6ef8cb2a…`**
(the landed tree's own binary — the artifact layer **refused** an earlier run
against the V4 binary and was right to; §6).

### §3.1  CLOSED — 2, both ghost ADDRESS seats

```
+ fz2e/519016   2 -> 0 rows      + fz2e/520040   4 -> 0 rows
```

### §3.2  W-1 — **THE ADDRESS CLOSES 3 OF 3; THE SEED CLOSES 2 OF 3**

M10's registered falsifier named `fz2c/410008`, `fz2e/519016`, `fz2e/520040`.

| seat | ledger fork row | `bad_rows` | `first_bad` |
|---|---:|---|---|
| `fz2e/519016` | 236 | 2 → **0** | 236 → none |
| `fz2e/520040` | 253 | 4 → **0** | 253 → none |
| `fz2c/410008` | **1192** | 4 → 4 | **1192 → 1198** |

**`fz2c/410008`'s ghost row IS fixed** — `first_bad` moves *past* the fork row,
which by the definition of `first_bad` means row 1192 now MATCHES — and the
seed keeps failing from row **1198**, six rows later, on something this package
does not own.  So the honest reading, and the one this document stands on:

> **the ADDRESS prediction is MET 3/3; the SEED-closure prediction is MET 2/3.**

It is reported as **W-1 PARTIALLY MET**, not restated as met.

### §3.3  W-3 MET / W-4 REFUTED / W-5 MISSED — reported as registered

| id | registered | measured |
|---|---|---|
| **W-1** | 3 seats close | **PARTIAL** — address 3/3, seed **2/3** (§3.2) |
| **W-2** | six seats NOT claimed | **held** — none of the six closed; two of them are §3.4's cost |
| **W-3** | **LOST = 0** over 654 | **MET — 0** |
| **W-4** | no still-failing seed's `first_bad` moves earlier | **REFUTED — 19 do** |
| **W-5** | ≥ 3 net closures on the 39 address seats | **MISSED — 2** |
| **W-6** | no claim on the 12 same-address seats | held (5 of them move, none closes) |

### §3.4  THE COST, STATED IN FULL AND NOT NETTED AWAY

**Σ diverging rows over 654 seeds: 123,015 → 124,856 (+1,841).**  The landing
is **NEGATIVE on the row metric** and that is not hidden behind the two
closures.

**1,801 of the 1,841 are TWO seeds**, and both were **named in advance by
W-2/M10 as seats the AND does not govern**:

| seat | family | rows | why it was predicted not to close |
|---|---|---|---|
| `fz2e/518039` | **C1 vector-1 trap MISSED by core** | 102 → 1,587 | its two ghost addresses are `0x00004` and `0x00006` — **IVT entries**.  M10 §5.3 files exactly this signature as **trap-delivery timing, not an address**, and it is a strong candidate for one of the ~7 coincidence seats §1 predicts |
| `fz2e/526054` | E1 | 4 → 320 | **M10 §5.2: the offsets are IDENTICAL and the fork is the SEGMENT** (silicon samples `SS` one clock later).  ANDing an already-correct offset with `SP` can only break it |

**The other 23 movers account for +40 rows between them.**

### §3.5  THE SCOPING PROOF — 100 % OF MOVERS ARE GHOST SEATS

Of 654 seeds, **629 are byte-identical to the baseline**.  Of the **25** whose
score record changes, **25 of 25 are 8F-ghost-proximate** (19 address seats,
6 same-address) and **0 are not**.  A landing that touches only the mechanism
it names, scored on a population that did not select it, is what a correct
scoping predicts — and it independently corroborates the §1 seat derivation.

### §3.6  W-17 — NON-VACUITY

`fz2_replay --perturb 1` on the two closed seats: **2 of 2 DIVERGENT once
perturbed (PASS)**.  The comparator is not vacuous on them.

---

## §4  THE STANDING GATES — EVERY ONE RE-MEASURED ON THE LANDED TREE

| id | gate | result |
|---|---|---|
| **W-9** | `gen_ucore_qsf --check` | **PASS** — up to date |
| **W-8** | `r7_lint` | **PASS** — 1 carrier (`eu_rd_edge`, declared), 3 tainted, 51 `stop` sites, **0 violations, NO NEW EXCEPTION**; tainted set **unchanged** |
| **W-7** | `ss_lint --core ucore` | **PASS and UNMOVED** — `SS_VERSION` **0x8D**, `SS_BIU_COUNT` **103**, `SS_EU_COUNT` **122**, `SS_COUNT` **226**, `SS_TAG` **0x8DE2**; `ss_flopcensus` **214 flops, 0 UNMAPPED**.  **No flop and no SSA address added** — this package was not the save-state single-writer and did not need to be |
| **W-10** | `test_artifact` | **45/45**, non-vacuous |
| **W-11** | `check_core --core ucore --opcodes 8F.0 --cases 0` | **500/500** (cycles 500, arch 500) — **THE 8F GOLDEN HOLDS** |
| **W-12** | `check_core --core ucore --opcodes all --cases 0` | **169,000/169,000** cycles AND arch |
| **W-13** | four HLT sweeps (`--waits 0/1/2/3`) | **97 · 93 · 45 · 44 = 279/283** |
| **W-14** | four `evt` cells / biased / `INT.F3AA` | **200 · 1,200 · 200 · 1,200**, biased **1,200/1,200**, `INT.F3AA` **200/200** |
| **W-16** | `ulockstep --golden 8F.0 --cases 50` (INFORMATIONAL) | **50/50 LOCKSTEP — W-16 REFUTED, in the favourable direction** (§4.1) |
| *extra* | `ulockstep --golden all --cases 50` | **17,350/17,350** — the standing ratchet, unmoved |
| **W-15** | `check_fuzz_bank` | **PASS — 621 banked seeds, stable 621 / improved 0 / worse 0**, `gen_drift` 0, `regen_err` 0, float-floor 0, new-sig TIMING 0 |
| **W-18** | **G6, CONTROL, TWO DRAWS** | **MET — §5** |

### §4.0  THE REPLAY INSTRUMENT'S OWN FIDELITY, BOTH COLUMNS

| | agreement vs the FABRIC verdict | `first_bad` identical | `fabric PASS / replay FAIL` |
|---|---|---|---|
| **baseline** (era guard **PASS**) | **654 / 654 = 100.0 %** | **116 / 116** | **0** |
| **landed** (`--no-fabric-era-guard`) | 652 / 654 | 92 / 114 | **0** |

The baseline column is a **perfect** 654/654 with every first divergence on the
same row — a stronger statement than the brief's 266/266, on a larger
population.  The landed column's **only** two disagreements are
`fz2e/519016` and `fz2e/520040`, both `fabric FAIL / replay PASS`, i.e. exactly
the two seats this landing closes.  **`fabric PASS / replay FAIL` is 0**, which
is the cell a regression would appear in.

### §4.1  W-16 IS REFUTED AND THE REASON IS ALREADY ON RECORD

The prereg predicted `ulockstep 8F.0` would FALL below 50/50 because `sim/`
does not carry this law.  **It did not: 50/50, and `--golden all` is
17,350/17,350.**  The reason is the FLASH #13 note's own: *"`ulockstep 8F.0` is
50/50 because a golden case has **no predecessor**, and all three unported
terms are predecessor effects."*  `ghost_relax` is one of those three.  A
prediction that assumed the model leg could see this change was wrong about the
INSTRUMENT, not about the mechanism, and is reported refuted.

---

## §5  W-18 — G6, **THE GATE THAT DECIDES THIS LANDING.  MET.**

CONTROL/DEFAULT build (no `X1_AD_RETENTION`, **DERIVED** by the gate from the
reports, not asserted), `db`/`incremental_db` deleted first on both draws.

| | draw 1 | draw 2 |
|---|---|---|
| receipt | `6abc26437ad2d33d…` | **`a69ae0098bdebf36…`** |
| tree | `0cdbb9394a`-**dirty** (the RTL edit uncommitted) | **`aa34be3296`, CLEAN** |
| **Fmax** | **39.05 MHz** | **39.05 MHz** |
| **worst setup** | **+5.64 ns** | **+5.64 ns** |
| **TNS** | **0.000 on every domain, setup AND hold** | same |
| ALMs | 12,230 / 41,910 (**29 %**) | 12,230 / 41,910 (29 %) |
| errors / latches / `lpm_divide` | 0 / 0 / 0 | 0 / 0 / 0 |
| 88-file input manifest | `a4b26250bf73e393…` | `a4b26250bf73e393…` (**identical**) |
| compile | 712 s | 669 s |

**Both draws PASS, both are 39.05 MHz to the digit, and both clear the 38.0 MHz
STOP the pre-registration set.**  The draws do not disagree, so the §0
"disagreement is itself the finding" clause does not fire.

### §5.1  THE ONE THING TO REPORT AND NOT EXPLAIN

**39.05 sits 0.11 MHz BELOW the lowest CONTROL draw this branch had taken**
(39.16 · 39.37 · 39.47 · 39.63 · 39.81 · 40.11 · 40.42).  It is inside the
registered 39–42 band and well clear of the STOP, and the change removes a
16-bit OR-with-mask and two mux levels from the head of the `acc_phys` adder —
so the *mechanistic* prediction was neutral-to-positive and the *measurement*
is flat-to-marginally-down.

**`standing_gates.md` §A governs: ONE GREEN BUILD IS NOT CLOSURE, two identical
draws are two draws and not a distribution, and the same tree has drawn 19.42
and 45.91 MHz.**  0.11 MHz is not distinguishable from draw noise on a
distribution nobody has characterised, and no claim is made either way.
**Recorded, not explained.**

### §5.2  WHAT THE TIMING PRECEDENT SAID, AND WHAT HAPPENED

The 8F ghost **feed** drew **15.3 MHz** on two draws with **all twelve worst
paths launching from `system_large|c_ready_q`**.  This landing is the ghost
**address**, it touches no `READY` carrier, `r7_lint` is unchanged, and it
draws **39.05 twice**.  **The family's timing collapse is a property of the
FEED, not of the ghost address cone** — which is now measured, where before it
was only assumed.

---

## §6  DISCIPLINE NOTES

* **The artifact layer earned its keep.**  A `--perturb` run was attempted
  against a `tb_sys` binary built from the V4 RTL and the layer **REFUSED**,
  naming `hdl/rtl/ucore/v30u_eu.sv` as the moved input.  The whole landed
  column was rebuilt (`3abecb7b6ef8cb2a…`) and re-scored; **every number in §3
  is the landed tree's own**, not V1-without-its-comment's.
* **`fz2_ledger.CURRENT` still points at F15.**  Every invocation in this
  package passes `--ledger …_f16_…` explicitly.  Booked, not edited — moving
  the pointer is coordinator territory.
* **Capture files are gitignored** and live only in the shared checkout; this
  worktree read them through symlinks, which were removed before the commit.
* **`sim/` was not extended**, no board was touched, `acc_split` / `acc_phys2`
  were not re-derived (prereg §2.3), and **no sixth arm was added** under any
  measurement.

## §7  BOOKED, NOT DONE

1. **The two INERT fitted cases** (`ghost_uses_mul_hi`, `pe_opc_reg == 8'h8e`)
   — §2.1.  Deleting them is the cheapest remaining simplification and needs a
   population that reaches them; the v1 `mc2` banks that fitted `mul_hi` are
   SUP-1-retired and cannot be replayed on this branch.
2. **WHICH RAIL** — M10's other free choice, untouched here.  `fz2e/530034`
   takes `M_EA` where the core takes `EA_RESIDUE`, and `fz2e/519072` ANDs `SP`
   with `M_EA`.  Neither is a mask question.
3. **`fz2e/526054`'s SEGMENT sample** — silicon samples `SS` one clock later
   than the ucore after a `MOV SS`/`POP SS`.  It is now a **measured 320-row
   cost** of this landing rather than a 4-row curiosity, which raises its
   priority.
4. **`fz2e/518039` should be re-triaged out of the ghost family** — §3.4.
5. **W-4's 19 seeds.**  The landing moves 19 still-failing seeds' first
   divergence earlier.  None is a loss and none is claimed; the signature (a
   `+4`-row cluster whose `first_bad` moves 6–8 rows earlier) is one mechanism
   and is worth one look before the next ghost landing.
6. **`fz2c/410008` from row 1198** — the ghost address is fixed and the seed is
   not; four rows, owner unknown.

---

## §8  RE-RUNNING THIS, END TO END

```bash
git rev-parse HEAD                       # must be the wave-4 landing
L=sw/testdata/fz2/fz2_failure_ledger_f16_2026-08-10.json

# the seat list (51 ghost-proximate, 39 ADDRESS) -- prereg §7 is the 5-line script
python3 sw/fz2_m10.py survey --ledger $L --out /tmp/m10_f16.json

# the scored column.  --no-fabric-era-guard because the tree is AHEAD of FLASH #16
python3 sw/fz2_tbsys.py build --leg ret
python3 sw/fz2_replay.py --ledger $L --all-failures --pass-sample 550 \
        --leg ret --jobs 8 --no-fabric-era-guard --out /tmp/landed.json
python3 sw/fz2_replay.py --ledger $L --seeds fz2e/519016,fz2e/520040 \
        --leg ret --perturb 1 --no-fabric-era-guard        # W-17, 2/2

# the gates, cheapest first
python3 sw/gen_ucore_qsf.py --check
python3 sw/r7_lint.py
python3 sw/ss_lint.py --core ucore
python3 sw/test_artifact.py
python3 sw/check_core.py --build --core ucore
python3 sw/check_core.py --core ucore --opcodes 8F.0    --cases 0   # 500/500
python3 sw/check_core.py --core ucore --opcodes INT.F3AA --cases 0  # 200/200
python3 sw/check_core.py --core ucore --opcodes all     --cases 0   # 169,000
for w in 0 1; do python3 sw/check_core.py --core ucore \
    --suite-dir tests/v30/s10-hltsweep-w$w --waits $w; done          # 97, 93
for w in 2 3; do python3 sw/check_core.py --core ucore \
    --suite-dir tests/v30/s13-hltsweep-w$w --waits $w; done          # 45, 44
for w in 0 1 2 3; do python3 sw/check_core.py --core ucore \
    --suite-dir tests/v30/v0.1-w${w}evt --waits $w; done             # 200/1200/200/1200
python3 sw/check_core.py --core ucore --suite-dir tests/v30/v0.1-w1evt-biased --waits 1
python3 sw/ulockstep.py --golden all --cases 50                      # 17,350
python3 sw/check_fuzz_bank.py                                        # PASS 621
python3 sw/quartus_gate.py                                           # G6, run it TWICE
```

⚠ **`check_core --suite-dir` takes `--waits` and it DEFAULTS TO 0.**  Without
it the sweeps read `97 · 0 · 0 · 0` and look like a catastrophe with every
failure at `(1, 'seg')`.

⚠ **Capture files are gitignored** (`sw/testdata/campaigns/*/captures/`) and
exist only in the shared checkout.  A fresh worktree must link or copy them
before any `fz2_*` tool can read a seed.
