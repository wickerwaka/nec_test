# fz2 WAVE-8 — THE 8F GHOST-READ **PREDECESSOR-TYPE SELECTION** LAW — RESULTS: BOOKED, NOT LANDED

Pre-registration: `docs/notes/fz2_w8_ghostsel_prereg_2026-08-11.md`, committed
**`5a74906d1f`**, after the split (**`4f6a2a383f`**) and **before the DERIVE
solve**. Read them first; this document answers the prereg clause by clause.

Branch `fuzz-v2-on-relanding`, base **`292d898837`** (`git rev-parse HEAD`
verified; the worktree provisioned at `master`/`29dcc5b05f` and was reset).
**Offline throughout — no board, no flash, no Quartus, `sim/` not extended.**

⚠ **`git diff 292d898837 HEAD -- hdl/` IS EMPTY.** No RTL was written, built or
scored. **No probe was built**, deliberately: the derivation stopped before a
law existed to score, and building one anyway would have been the third guess
this wave was told not to make.

---

## §0 HEADLINE — W8-D IS **NOT EVALUABLE**: THE DERIVATION POPULATION IS **n = 1**, AND THE BLOCKER IS THE INSTRUMENT, NOT THE DIE

The pre-registered STOP for *"if the mechanism can't be found from the RTL +
banked data, BOOK it with the precise missing measurement"* is the outcome, and
the missing measurement is now named, designed, and **offline** — it is not a
board cell.

| | |
|---|---|
| **W8-D** the derivation | **NOT EVALUABLE.** Of the 13 DERIVE seats, **9** are 8F-ghost seats (`near_package == P4`); of those 9 the solve reproduces **3**; of those 3 one has **no address fork at the fork row** and one is **EMPTY over 21 terms + 190 pairs at all 14 freezes**. **Usable DERIVE ghost-address evidence: ONE seat.** |
| **W8-1** ≥ 2 HOLDOUT closures | **NOT REACHED** — no law reached HOLDOUT scoring. HOLDOUT was **not looked at**, which is the point of freezing it. |
| **W8-2 / W8-3** LOST = 0 / none earlier | **VACUOUSLY HELD** — `hdl/` byte-identical. |
| **W8-13** G6 two draws ≥ 38.0 | **NOT RUN** — there is no bitstream to time. The 38.0 STOP is moot. |

**And the one seat argues AGAINST C-W8, in the direction that matters.**

## §1 THE ONE DATA POINT, TO THE BIT — AND WHY IT IS NOT A LAW

`fz2e/524030`, `8f cb` at `near_dist == 0`, `wrand`, fork row 352.
`fz2_m10.py solve`, save-state freeze sweep `d ∈ [-12,+1]` on the receipted
`--core ucore` `tb_v30_core` — receipt **`14b9d836de2800da…`**, declared inputs
`b16240a6264ecac8…` over 18 files, every one of them hashing to `292d898837`'s
bytes (`v30u_eu.sv 4c4f24da…`, `v30u_eu_step.svh 716bf63d…`,
`tb_v30_core.sv eb2befff…`, checked against the tree). *(Its `git.dirty_tracked`
reads true only because the concurrently-finishing `tb_sys` build had just
appended to the tracked receipt ledger; no RTL or tool file was modified — the
declared input hashes are the check that matters and they are HEAD's.)*
At the fork freeze: `SS = 252b`, `EA_RESIDUE =
8d56`, `TMPA = 803f`, `SP = ec50`, `IND = ec50`, `M_EA = 445a`.

```
  ghost_uses_ea = (ea_residue != tmpa)      = 1          the tree's value proxy says EA
  ghost_ea_off  = {ea_residue[15:1],1'b0}   = 8d56
  ghost_bus_off = ghost_off & SP            = 8c50   ->  SS:8c50 = 2df00   == the CORE leg, exactly
  SP undecorated                            = ec50   ->  SS:ec50 = 33f00   == the CHIP leg, exactly
```

**Silicon took `SS:SP` undecorated. It used neither rail and it did not
perform the AND.** The last-writer bit — C-W8's whole content — reads EA on
this seat, and a bit that selects *between two rails* cannot produce *no rail
and no AND*. So C-W8 does not describe the only seat that can speak.

**⚠ AND THE SEAT CANNOT DISCRIMINATE EVEN THAT.** `IND == SP == ec50` at this
freeze, so `SS:SP` and `SS:IND` are the same number here; the solve reports
both. One seat, with two candidate rails degenerate on it, is not a
derivation — it is a coincidence with a receipt. **A law chosen on it and then
scored on the frozen HOLDOUT would be fitting to a single seat, and its
HOLDOUT number would not be evidence.** That is exactly the trap §64.1 exists
to prevent, and it is why nothing was built.

`fz2e/518067` (`8f f3` @1) is the second solvable ghost fork and it is
**EMPTY**: chip `55a39` = `SS:5009`, and no term or bitwise pair reproduces
`5009` at any of its 14 freezes. That is M10's reading (i) — upstream value
divergence — and it belongs to the earlier instruction's package, not to the
ghost address. `fz2e/518006` solves but `chip == core == c2c39` at its fork
row (`t1_addr_differs` false): there is no address to explain.

## §2 THE INSTRUMENT IS THE BLOCKER, AND IT IS MEASURED, NOT ASSERTED

`fz2_m10.py solve` refuses any seat whose offline replay does not put the fork
at the board's row with the board's core address (`NOREPRO`) — correctly: *an
address solved at the wrong clock is a fitted number*. It freezes through
**`tb_v30_core`**, which has ONE pin-event scheduler. **Six of thirteen DERIVE
seats are NOREPRO, and every cause is the harness's, not the seed's:**

| seat | waits | pkg@dist | board fork row / core addr | offline | cause |
|---|---|---|---|---|---|
| `fz2e/524007` | `wrand` | P4@1 | 319 / `a1d64` | 319 / **`93640`** | offline core address ≠ board core address |
| `fz2e/531018` | `wrand` | P4@1 | 1510 / `27003` | 1510 / **`26fc1`** | ditto |
| `fz2e/533025` | `wrand` | P4@1 | 1678 / `b5fb8` | 1678 / **`b3f98`** | ditto |
| `fz2e/529067` | fixed w2 | P4@0 | 611 / `7e8a6` | 611 / **`7a8a6`** | ditto |
| `fz2e/518004` | fixed w0 | P4@1 | 739 | **207** | replay diverges at a different row |
| `fz2e/518053` | fixed w0 | P4@1 | 571 | **567** | ditto |

**THE CONTROL THAT MAKES THIS READABLE.** On the identical 28 seats,
`fz2_replay --leg ret --no-fabric-era-guard` on `tb_sys`
(`Vtb_sys` receipt `09e75c03751e6d85…`, tree `3caf766688960339…`) reproduces
the fabric verdict on **28/28** and the fabric `first_bad` row on **28/28** —
including **8/8 `wrand`** and **3/3 `wvec`**. The seeds are reproducible
offline. `tb_v30_core` is the thing that cannot follow them, and the standing
rule already says so: *where `tb_v30_core` and `tb_sys` disagree, fabric sides
with `tb_sys` — 1,654 of 1,654 cells.*

Wave-6 hit the same wall on its own split (8 of 16 DERIVE and 11 of 23 HOLDOUT
NOREPRO) and attributed it to the single scheduler. **Three waves have now been
funded on a derivation population the instrument shrinks by ~60 %.** That is
the finding.

## §3 THE MISSING MEASUREMENT — `M10-SYS`, DESIGNED

**It is not a board cell.** No silicon question is open that the banked
captures cannot answer; what is missing is the ability to *read the core's
registers* while replaying them faithfully.

> **`M10-SYS` — move the M10 save-state freeze from `tb_v30_core` to `tb_sys`.**

**The port already exists in the DUT and is tied off.**
`hdl/rtl/system_large.sv:410-413` instantiates the core with
`.SS_ADDR(9'b0)`, `.SS_WE(1'b0)`, `.SS_RDATA(core_ss_rdata_unused)`. The three
signals are present; nothing new is designed. The work is:

1. bring `SS_ADDR` / `SS_WE` / `SS_RDATA` up to `tb_sys` beside the existing
   `hb_ad_sample` observation tap — **observation-path only**, exactly the
   deviation `system_large.sv` already documents for `X1_AD_RETENTION`, so the
   `use_core = 0` socket position is unaffected by construction;
2. give `sw/fz2_m10.py solve` a `--tb sys` leg that drives them at a CE-clock
   offset **measured** the way the present one measures it
   (`SSA_B_CUR_ADDR == core_addr` at the fork), not assumed;
3. re-run the identical 21-term / 190-pair expression search. No new search
   space, no new free parameter.

**FALSIFIER FOR THE PORT ITSELF (register it before running it).** On the three
seats `tb_v30_core` already solves — `fz2e/524030`, `fz2e/518006`,
`fz2e/518067` — the `tb_sys` freeze must return **byte-identical register terms
at every freeze `d`**. A port that disagrees with the working instrument on the
seats both can do is measuring itself.

**WHAT IT BUYS, PRE-REGISTERED SO IT CAN MISS.** DERIVE goes from **1** usable
ghost-address seat to an expected **6-9** (the 9 P4 seats minus whatever stays
EMPTY). **If it lands below 5, the next wave must say so and book again rather
than fit** — the whole point of this document is that a law derived on one or
two seats is not a law.

**AND THE QUESTION IT SHOULD THEN ASK IS NOT "WHICH RAIL".** §1's seat says the
open free choice is the one `v30u_eu.sv:1531` already names out loud —
*"WHICH RAIL and WHETHER THE AND HAPPENS; only the second is settled here, and
only in the direction 'not by a mask'"*. On `524030` the AND does not happen at
all and the address is the plain stack address. The ucore already carries an
arm for exactly that (`(eu_ghost_idle && !q_ripe) ? gpr[R_SP]`) and it did not
fire; wave-4 measured that arm at **+2 closed / 1 LOST** (`fz2c/410034`).
**The next wave's question is therefore: on a solvable population of ≥ 5, what
distinguishes a ghost whose address is `SS:SP` undecorated from one that is
`SS:(rail & SP)`?** That is one predicate over registered state, it names no
opcode, and it is answerable entirely offline once `M10-SYS` exists.

## §4 THE POPULATION, AND TWO THINGS THE PRE-REGISTRATION GOT WRONG

The split (`docs/notes/fz2_w8_split.json`, `4f6a2a383f`) is
`sha256(seed_id + "w8")[0] < '8'` over F17 family `E1` (39) minus its 11
IMMATERIAL members: **13 DERIVE / 15 HOLDOUT**. It reads the seed id only.

**ERRATUM E-W8-1 — `E1` IS NOT THE GHOST FAMILY, AND THE PRE-REGISTRATION
TREATED IT AS ONE.** The M10 survey run *after* the prereg partitions the 28:
**18 are `near_package == P4`** (an `8F` mod==3 one to three pops back) and
**10 are not**. The 10 non-ghost seats include **all six of M10's LEA-mod3
six** plus `fz2e/501069`, `fz2e/510043`, `fz2e/535027` and `fz2c/406006`.
Waves 6 and 7 selected on `near_package == P4 && t1_addr_differs` from the F16
ledger; this wave selected on the F17 ledger's `E1` family, which is broader.
The error is disclosed, not repaired: **repairing the population after seeing
it is what a frozen split exists to forbid.** It does not change the verdict —
the derivation is starved on the P4 subset itself (9 seats, 1 usable).

**ERRATUM E-W8-2 — ONE OF THE TWO REGISTERED CLOSEABLE HOLDOUT SEATS IS NOT A
GHOST SEAT.** W8-1 named `fz2c/406006` and `fz2e/521059` as the closeable
HOLDOUT population, chosen from the baseline `bad` counts before the ghost
partition was measured. `fz2c/406006` is `pkg None` (`0f 3b 2a 8c`) and no
ghost-address law can be expected to touch it; `fz2e/521059` is `P4@2`
(`59` = POP CX behind `8f d1`) and stands. **The honest reading is that W8-1's
closeable population was really ONE seat**, which strengthens rather than
weakens the STOP: a bar of "2 closures" was already generous and a law would
have had a single seat to prove itself on.

### §4.1 The baseline, and the cascade partition (measured before the prereg, disclosed there)

`fz2_replay --leg ret` over the 28: 28/28 replay-FAIL, `first_bad` identical to
fabric 28/28. Only **4 of 28** carry a `bad` a ghost-address fix could zero:
`fz2c/406006` 16 · `fz2e/529067` 16 · `fz2e/521059` 20 · `fz2e/530001` 20.
The other 24 run from 194 to 3,479 bad rows. **This is W7 §4.2's warning
confirmed on a fresh split and it is the reason W8-1 asked for 2 and not 3:
"≥ 3 fresh HOLDOUT closures" is unmeetable on this population by any law
whatsoever.**

| | DERIVE (13) | HOLDOUT (15) |
|---|---|---|
| `near_package == P4` (ghost) | 9 | 9 |
| not a ghost seat | 4 | 6 |
| `bad ≤ 40` | 2 (`529067`, `530001`) | 2 (`406006`, `521059`) |
| M10 LEA-mod3 six | 1 (`530001`) | 5 |
| solve reproduces | 7 | *not measured — frozen* |
| usable ghost-address evidence | **1** | *not measured — frozen* |

**HOLDOUT WAS NEVER SOLVED, SCORED OR INSPECTED.** No `fz2_m10.py solve` was
run against it and no register value from it was read. It remains a clean,
unburned population for `M10-SYS`'s wave — which is the only asset this wave
hands forward, and it is a real one.

## §5 THE REGISTERED PREDICTIONS, ANSWERED

| id | registered | outcome |
|---|---|---|
| **W8-D** | the derivation names a mechanism | **NOT EVALUABLE — n = 1.** Registered falsifier ("two seats, same bit, different rails") never became askable. The one seat argues against C-W8 (§1) but one seat is not a refutation either, and it is reported as neither |
| **W8-1** | **≥ 2 HOLDOUT closures (the deliverable)** | **NOT REACHED.** No law reached HOLDOUT. The pre-registered STOP ("book, land nothing") is taken. See E-W8-2: the closeable population was really 1 |
| **W8-1a** | 13 HOLDOUT seats are registered NON-CLOSURES | **HELD** — nothing claimed |
| **W8-1b** | row improvement ≠ closure | **N/A** — nothing built, nothing improved, nothing claimed |
| **W8-2** | LOST = 0 | **VACUOUSLY HELD** — `git diff 292d898837 HEAD -- hdl/` empty |
| **W8-3** | no `first` earlier | **VACUOUSLY HELD** — same |
| **W8-4** | named non-movers unmoved | **HELD** — no RTL change; nothing claimed for the LEA-mod3 six, either §64.1 list, or `fz2c/404040` |
| **W8-5** | `fz2_immaterial falsify` PASS, 21 of 113 | **HELD — PASS.** members **21**, non-members 92, `COSMETIC 19 · TRANSIENT 2`; G1-G8 all PASS, C-ROW 113/113, C-ARCH 113/113 |
| **W8-6** | no new flop; `ss_lint` unmoved | **HELD** — `ss_lint: PASS`, 103×2 BIU + 122×2 EU + tag = **226**; `ss_flopcensus: PASS`, **214** flops, 0 UNMAPPED. `v30u_ss_pkg.sv` untouched |
| **W8-7 / W8-8 / W8-9** | `check_core` 169,000 + 8F.0 500, sweeps 279/283, `ulockstep` 17,350 | **VACUOUSLY HELD — AND NOT RE-RUN.** `hdl/` is byte-identical to `292d898837`; quoting them here would be quoting a number with no run behind it |
| **W8-10** | `r7_lint` / `gen_ucore_qsf` / `test_artifact` | **HELD, RE-MEASURED** — `r7_lint: PASS`, 0 undeclared carriers, 0 undeclared unresolved, 0 `stop` violations, tainted set unchanged (`eu_rd_edge`, `rd_edge_psw_take`, `rd_edge_take_raw`); `gen_ucore_qsf --check` up to date; `test_artifact` **NON-VACUOUS**, passes |
| **W8-11** | DERIVE and HOLDOUT reported separately | **HELD** — §4.1, and HOLDOUT is reported as *not measured* |
| **W8-12** | non-vacuity of any closure | **N/A** — no closure claimed |
| **W8-13** | **G6 two draws ≥ 38.0 MHz** | **NOT RUN — nothing was built to land.** The 38.0 STOP is moot |

## §6 DISCIPLINE NOTES

* **Pre-registration held, and the ORDER is the evidence.** The split was
  committed at `4f6a2a383f` — derived through `fz2_materiality.measure_all` and
  `fz2_immaterial.partition`, never a list — **before** the prereg document,
  and both **before** the first `fz2_m10.py solve`. The baseline replay that
  set W8-1's bar reads no address and no register and is disclosed in the
  prereg as a pre-law measurement.
* **The bar was lowered on purpose and the reason was written down first.**
  W6 and W7 both registered "≥ 3 fresh HOLDOUT closures"; §2 of the prereg
  shows that bar is arithmetically unmeetable on this population. Registering
  a bar you know cannot be met is not rigour.
* **Two errata are reported against this wave's own pre-registration** (§4),
  both in the direction that makes the wave look worse, and neither is
  repaired after the fact.
* **No probe was built.** W6's precedent: a DERIVE that cannot found a law ends
  the wave. Building and scoring one anyway would have produced a HOLDOUT
  number with nothing behind it.
* **No board, no flash, `sim/` not extended, no Quartus.** The board carries
  FLASH #17 and this wave did not touch it. No fabric figure is quoted.
* **Capture files are gitignored in the main checkout and were reached through
  symlinks in `sw/testdata/campaigns/{fz2c,fz2e}/captures`, removed before this
  commit.**
* **Artifacts for re-run**: `docs/notes/fz2_w8_split.json`,
  `sw/fz2_w8_split.py`. The solve and survey columns are re-derivable by §7.

## §7 RE-RUNNING THIS

```bash
git rev-parse HEAD                                   # 292d898837 + the wave-8 commits
python3 sw/check_core.py --build --core ucore        # the solve instrument
python3 sw/x1_retention.py build --leg ret           # tb_sys ret (the baseline scorer)
# link the gitignored captures into sw/testdata/campaigns/{fz2c,fz2e}/captures first
python3 sw/fz2_w8_split.py                           # reproduces the frozen split
L=sw/testdata/fz2/fz2_failure_ledger_f17_2026-08-11.json
python3 sw/fz2_replay.py --ledger $L --seeds <the 28> --leg ret --no-fabric-era-guard
python3 sw/fz2_m10.py survey --ledger $L             # the P4 partition
python3 sw/fz2_m10.py solve  --ledger $L --seeds <DERIVE 13>
#   -> SOLVED 7 / 13; usable ghost-address forks: 1 (fz2e/524030)
```
