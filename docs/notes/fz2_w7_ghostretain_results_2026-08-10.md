# fz2 WAVE-7 — THE 8F GHOST-READ **ADDRESS RETENTION** LAW — RESULTS: BOOKED, NOT LANDED

Pre-registration: `docs/notes/fz2_w7_ghostretain_prereg_2026-08-10.md`, committed
`8ce8ae58a9` **before the landed-RTL was scored**.  Read that first; this
document answers it clause by clause.

Branch `fuzz-v2-on-relanding`, base **`f32249a9d0`** (`git rev-parse HEAD`
verified `f32249a9d0d621dd…`; the worktree provisioned at `master`/`29dcc5b05f`
and was reset onto work branch `w7-ghost-retention` at `f32249a9d0`).  Offline
throughout; **no board, no flash, no Quartus** (G6 not run — nothing landed).

⚠ **THE TREE IS BYTE-IDENTICAL TO `f32249a9d0` IN `hdl/`** — `git diff
f32249a9d0 HEAD -- hdl/` is empty.  The probe RTL below was built, scored and
REVERTED.  Every `fz2_replay` figure is offline and `--no-fabric-era-guard`.

---

## §0  HEADLINE — W7-1 MISSED (0 CLOSURES) AND W7-2 VIOLATED (2 LOST): THE IND RAIL IS WORSE THAN THE FITTED SELECTOR

Wave-6 SPECULATED that the correct 8F ghost model is a **retained flop** that
captures the 8F's intended address at issue and thereby subsumes both the
dist-0 (`IND`) and dist-1 (`M_EA`) seats.  **This wave tested it and it is
refuted.**  The strongest form of the "IND at issue" law — the combinational
`ghost_off = ind_now` (§1 of the prereg registered why the flop can only lag
it, never beat it) — measured on `fz2_replay --leg ret` over all 39 address
seats:

| pre-registered bar | measured | verdict |
|---|---|---|
| **W7-1** ≥ 3 fresh HOLDOUT closures (`bad` → 0) | **0 closures**, DERIVE or HOLDOUT | **MISSED** |
| **W7-2** LOST = 0 | **2 LOST** — `fz2e/519016` (0→2), `fz2e/520040` (0→4), both DERIVE | **VIOLATED** |
| **W7-3** no `first` moves earlier | **4 moved earlier** — `fz2c/409077` 820→816, `fz2c/410008` 1198→1192, `fz2e/522029` 785→377, `fz2e/535036` 1716→1708 | **VIOLATED** |

**Per the pre-registered STOP condition (§3.1) — "If HOLDOUT closes fewer than 3
fresh seats, or any seed is LOST, the law is BOOKED and the RTL is NOT landed" —
NO RTL WAS LANDED.**  Both triggers fired.  This is the pre-registered STOP
outcome reported as the result.  G6 was not run: there is no bitstream to time.

---

## §1  WHY IT FAILS — THE STALE SOURCE IS A DIFFERENT PHYSICAL REGISTER PER SEAT, AND CAPTURING AT ISSUE DOES NOT CHANGE THAT

The retention speculation assumed dist-0's `IND` and dist-1's `M_EA` are the
**same value** read at two pipeline stages — "living in two different registers
depending on how long the bus cycle took."  **The register-level measurement
refutes that.**  From the DERIVE solve (`fz2_m10.py solve`, save-state mode 6,
freeze sweep `d ∈ [-12,+1]`):

| seat | class | chip ghost | what fits, at every freeze | `IND` value across the window |
|---|---|---|---|---|
| `fz2c/408021` | dist-0 | `SS:d7c0` | `IND` (= `SP` = d7c0) | d7c0 (stable) — the 8F-era value IS still in `IND` at the fork |
| `fz2e/524030` | dist-0 | `SS:ec50` | `IND` (= `SP` = ec50) at d=-1,0 | 445a until d=-2, then ec50 — `IND` is reloaded TO the 8F value just before the fork |
| `fz2e/518022` | dist-1 | `SS:0000` | **`M_EA` = 0 only** | **a420 (d≤-1), e219 (d≥0) — `IND` reproduces the chip at NO freeze** |

`fz2e/518022` is the decisive seat.  Its chip ghost is `SS:0000`, which only
`M_EA = 0` reproduces; `IND` is a420 through the whole window and e219 at the
fork; **`SP` is a420 too, so it is not `SS:SP` either**, and no bus cycle in the
seat's history ever addressed 69ae0, so it is not a stale MAR value either.  The
8F's stale source here is a retained ModR/M EA that happens to be 0 — a
DIFFERENT physical register from the dist-0 seats' `IND`.  **Capturing `IND` at
the 8F issue gives a420; the chip reads `SS:0`.  The retention framing does not
rescue the single-register hypothesis, because which register mirrors the 8F's
stale address depends on the PREDECESSOR instruction's type, not on WHEN it is
read.**  A POP-family predecessor leaves the address in `IND`/`SP`; a ModR/M
predecessor leaves it in `M_EA`.  "Whichever register the last memory op wrote"
is a MUX over instruction type — the fitted selector the current RTL already
carries, incompletely fitted, and NOT a single retained flop.

This is the SIMPLICITY principle cutting the other way: the "simple system" is a
shared internal address latch the die has and the ucore does not expose as any
one save-state register; the exposed registers (`IND`, `M_EA`, `EA_RESIDUE`, …)
are DIFFERENT copies, and no one of them is "the latch."

## §2  THE PROBE, AND WHY IT IS THE STRONGEST FORM

`v30u_eu.sv:1493` `ghost_off = ghost_uses_ea ? ghost_ea_off : tmpa` →
`ghost_off = ind_now`, everything else untouched, `tb_sys` ret rebuilt, 39 seats
scored, then REVERTED.  The prereg §1 registered — before the build — that the
ucore EU is cycle-accurate: `ghost_read_stale_alu` asserts on the 8F's own
stack-read row and the BIU samples `eu_addr` that same clock, so `ind_now` at
that row **is** the issue value and the BIU request latch **is** the retention.
A flop loaded and read on one clock is one cycle stale, so it can only lag the
combinational form.  **The combinational form is therefore the best case for the
IND mechanism, and it closes 0 and loses 2.**  The flop + its SSA address
(`SSA_E_GHOST_ADDR = 9'h17E`, `0x8E/227/0x8EE3`) were pre-registered in case a
genuine one-cycle retention proved necessary and correct; it did not, so the
SS-writer bump was **NOT taken** and `v30u_ss_pkg.sv` is untouched (W7-10's
UNMOVED branch: `0x8D / 226 / 0x8DE2 / 214`, `ss_lint` PASS).

The change reaches the ghost path — 21 of 39 seats moved their `bad` count, and
`fz2e/519016`/`fz2e/520040` flipped PASS→FAIL — so the probe is live and the
verdict is the mechanism's, not a dead wire's.  Even `fz2c/408021`, the cleanest
dist-0 `IND` seat, went `bad` 26 → 22, **not** → 0: on `tb_sys` its divergence
is a ~22-row cascade, not the single ghost row, so fixing the ghost address
cannot zero it.  Every dist-0/`IND` seat that wave-6 named (`524030`, `527037`,
`534060`) carries a `bad` in the thousands from an unrelated cascade and is
uncloseable by any ghost-address rail.

## §3  THE REGISTERED PREDICTIONS, ANSWERED

| id | registered | outcome |
|---|---|---|
| **W7-D** | DERIVE names a single rail `IND` | **HELD** (§2 prereg) — IND:2, EMPTY:2, NOREPRO:11; a single rail on the arch-solvable non-EMPTY DERIVE seats |
| **W7-1** | ≥ 3 fresh HOLDOUT closures **(the deliverable)** | **MISSED — 0 closures.** STOP taken |
| **W7-1a** | the dist-1/`M_EA` HOLDOUT seats do NOT close by `IND` | **HELD** — `518022`/`519072`/`530034` all still fail; §1 shows `IND` reproduces `518022` at no freeze |
| **W7-2** | LOST = 0 | **VIOLATED — 2 LOST** (`519016`, `520040`), both the wave-4-AND M_EA seats |
| **W7-3** | no `first` moves earlier | **VIOLATED — 4 moved earlier** |
| **W7-4** | §64.1 four unmoved, `404040` bad=0, LEA-mod3 six not claimed | **HELD** — no landing; nothing claimed |
| **W7-5..W7-9** | 8F.0 500/500, all 169,000, sweeps 279/283, evt cells, `check_fuzz_bank` 621 | **VACUOUSLY HELD** — `hdl/` byte-identical to `f32249a9d0` |
| **W7-10** | `ss_lint` PASS, UNMOVED (no flop taken) | **HELD** — `0x8D / 226 / 0x8DE2 / 214`, PASS; `v30u_ss_pkg.sv` untouched |
| **W7-11** | `r7_lint` PASS, no new exception | **HELD** — PASS, 0 violations, tainted set unchanged |
| **W7-12/13** | `gen_ucore_qsf`/`test_artifact`; `ulockstep` informational | **VACUOUSLY HELD** — no RTL change |
| **W7-14** | non-vacuity | **N/A** — no closed seat |
| **W7-15** | **G6 two draws ≥ 38.0 MHz** | **NOT RUN — no RTL was built to land.** The 38.0 STOP is moot |

## §4  WHAT THE NEXT WAVE SHOULD KNOW (and why it is NOT done here)

1. **The single-register/single-flop 8F-ghost rail is now refuted from BOTH
   directions** — wave-6 refuted the static rail read at the fork; wave-7
   refutes the retained rail captured at issue.  The stale source is
   PREDECESSOR-TYPE-INDEXED (POP→`IND`/`SP`, ModR/M→`M_EA`), which is a
   selector, not a retention.  Any future landing must model the SELECTION, and
   the current fitted `ghost_uses_ea = (ea_residue != tmpa)` is that selector's
   best current form — incompletely fitted, not wrong in shape.
2. **The closeable population is small and is NOT the dist-0/`IND` seats.**  Of
   the 39, only ~7 have a `bad` small enough (≤ 20 on `tb_sys`) that a ghost
   address fix could zero them, and those are `M_EA`/EMPTY/upstream, not `IND`.
   The dist-0/`IND` seats all carry thousand-row cascades from unrelated causes.
   A future wave should FIRST partition the 39 by "is the ghost row the only
   divergence" on `tb_sys`, and only then derive a rail on the small-`bad`
   subset — deriving on the solve tool's arch-solvable seats (which are `IND`)
   pointed at a population the deliverable instrument cannot close.
3. **The EMPTY seats** (`524055`, `528010`, and the M10 reading-(i) class) are
   upstream value divergence and belong to the earlier instruction's package,
   not the ghost address (wave-6 §5.3).

## §5  DISCIPLINE NOTES

* **Pre-registration held.**  Split frozen by an address-independent salted hash
  and committed (`8ce8ae58a9`) before the landed-RTL was scored; the DERIVE
  derivation ran first and named `IND`; the STOP triggered on the HOLDOUT/loss
  score, not on a re-reading of DERIVE.
* **The fresh split moved 20 of 39 seats vs wave-6** and, in particular, moved
  every dist-1/`M_EA` seat to HOLDOUT — which is exactly why DERIVE looked
  unanimous for `IND` and why the disjoint HOLDOUT was the necessary test.  Had
  the law been scored only where it was derived, it would have looked like a
  clean single rail.  §64.1 earned its keep.
* **No board, no flash, `sim/` not extended, no Quartus** — nothing was built to
  land, so G6 was not drawn (the prereg's 38.0 STOP is moot).
* **Capture files are gitignored** and were read through symlinks removed before
  the commit.
* **Artifacts banked for re-run**: `docs/notes/fz2_w7_split.json`, and the two
  DERIVE solve columns re-derivable by
  `fz2_m10.py solve --ledger sw/testdata/fz2/fz2_failure_ledger_f16_2026-08-10.json --seeds <DERIVE 22>`
  → `fz2_w6_railcheck.py --solve …`.

## §6  RE-RUNNING THIS

```bash
git rev-parse HEAD                      # f32249a9d0 + the two wave-7 doc commits
python3 sw/check_core.py --build --core ucore          # the solve instrument
python3 sw/x1_retention.py build --leg ret             # tb_sys ret (the scorer)
# link the gitignored captures from a full checkout into
#   sw/testdata/campaigns/{fz2c,fz2e}/captures first
L=sw/testdata/fz2/fz2_failure_ledger_f16_2026-08-10.json
python3 sw/fz2_m10.py solve --ledger $L --seeds <DERIVE 22> --out /tmp/d.json
python3 sw/fz2_w6_railcheck.py --solve /tmp/d.json     # -> IND:2 EMPTY:2 NOREPRO:11
# the probe: v30u_eu.sv:1493  ghost_off = ind_now;  rebuild ret; then
python3 sw/fz2_replay.py --ledger $L --seeds <39 addr seeds> --leg ret \
        --no-fabric-era-guard                          # -> 0 closed, 2 lost
```
