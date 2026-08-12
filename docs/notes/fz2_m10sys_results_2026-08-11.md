# fz2 WAVE-9 — `M10-SYS` — RESULTS: **THE INSTRUMENT IS BUILT AND PROVED; THE DERIVATION IS BOOKED AGAIN, AT A SHARPER PLACE**

Pre-registration: `docs/notes/fz2_m10sys_prereg_2026-08-11.md`, committed
**`fd68408937`**, before `hdl/rtl/system_large.sv` was touched and before the
first DERIVE solve on the new leg. Read it first; this document answers it
clause by clause.

Branch `fuzz-v2-on-relanding`, base **`6cbb01a642`** (`git rev-parse HEAD`
verified; the worktree provisioned at `master`/`29dcc5b05f` and was reset).
**Offline throughout — no board, no flash, no Quartus, `sim/` not extended.**

---

## §0 HEADLINE

| | |
|---|---|
| **The instrument** | **BUILT, INERT AND PROVED.** Wave-8's falsifier is **MET with ZERO offset: 1,050 of 1,050 register values byte-identical** across 3 seats × 14 freezes, and `SSA_B_CUR_ADDR` identical 42/42. |
| **What it bought** | **The DERIVE solve goes from 7/13 to 13/13 SOLVED. All SIX of wave-8 §2's NOREPRO seats are repaired.** The blocker was the instrument, exactly as §2 said, and that is now measured rather than argued. |
| **The yield** | **5 usable by the registered definition — the bar is MET at its floor**, against wave-8's expected 6-9. ⚠ And the registered definition **OVER-COUNTS**: see erratum **E-M10S-2**. The population that actually speaks about the ghost address is **TWO**. |
| **The question** | **ANSWERED, in the direction wave-8's n=1 pointed, now at n=2 and BIT-EXACT.** Where the core's own ghost arm demonstrably forms the address, **silicon takes the rail UNDECORATED and the core ANDs it** — and the core's value is reproduced to the bit as `ghost_off & gpr[R_SP]` on 2 of 2. |
| **The law** | **NOT REGISTERED. BOOKED.** The rail stays undetermined — degenerate `{SP, TMPB, IND}` on BOTH speaking seats, the SAME degeneracy wave-8 stopped on — and *"delete the AND"* is refuted before it can be proposed by `v30u_eu.sv:1531`'s own artifact. |
| **HOLDOUT** | **SEALED.** Not solved, not scored, not inspected. |
| **G6** | **NOT RUN, AND NOT REGISTERED.** No RTL behaviour changed; the instrument is `` `ifndef SYNTHESIS ``, proved by preprocessor identity (§2). |

---

## §1 THE INSTRUMENT — WHAT WAS BUILT

`hdl/rtl/system_large.sv` gains one `` `ifndef SYNTHESIS `` block and five
guarded port connections. `sw/fz2_tbsys.py::run_tb` gains `ss_at=`;
`sw/fz2_m10.py` gains `--tb {core,sys}` (default `core`, so every historical
invocation still means what it meant) and `replay_tbsys()`. Two new files:
`sw/fz2_m10sys_falsify.py` (the falsifier) and `sw/fz2_m10sys_decor.py`
(§4's partition).

**It is a READ-ONLY TERMINAL FREEZE.** `SS_WE` stays tied to `1'b0` — the
port is never written — so the whole `SS_WE`-while-`CE`-high hazard class
(`v30_core.sv:138`) is gone by construction. `fz2_m10._one_solve` **discards
the rows of every freeze run**, so the freeze need not resume; the probe
streams the 226-word map and `$finish`es. That is why parking only the core's
`CE`/`CE_HALF` is sufficient and `nec_bus` is left running: every
architectural flop in `v30u_eu`/`v30u_biu` is gated by `ss_we || srst || ce`,
while the save-state read path is `always @(posedge clk)` with **no `CE`**.

The freeze row is `nec_bus`'s own `cap_record` count with leading `RESET`
records skipped (`cap_record[55]`) — `fz2_replay._drop_reset`'s rule, the one
that makes a `tb_sys` row index mean what a banked row index means. The park
waits for that cycle's `tick_fall`, so cycle *k* gets both its `CE` and its
`CE_HALF`, mirroring `ss_park`. **No offset was needed** (§3).

---

## §2 INERTNESS — ALL THREE CLAUSES MET

| id | registered | outcome |
|---|---|---|
| **M10S-I1a** | the diff is `` `ifdef SYNTHESIS <today's line> `else <the probe's> `` | **HELD** — five port connections and one wire declaration, each guarded |
| **M10S-I1b** | `gen_ucore_qsf --check` PASSES | **HELD** — *"nec_test_ucore.qsf is up to date"* |
| **M10S-I1c** | strip the `` `ifndef `` blocks, take the `` `ifdef `` arms, **byte-identical to `6cbb01a642`** | **MET.** `sha256` **`3cb6199cc827af4610cd1089fe83b91cf21d561248d548447be11539f7018db9`** on both sides, `diff` empty. Both QSFs set `VERILOG_MACRO "SYNTHESIS=1"` (`nec_test_ucore.qsf:71`, `nec_test.qsf:60`), so **Quartus compiles character-identical text and the netlist cannot move.** |
| **M10S-I2a** | `fz2_tbsys.py inert` PASS | **MET** — `noevent` and `legacy1`, **4,000 records each, BYTE-IDENTICAL** between `pre` (receipt `535199e70a46e326…`, taken at `6cbb01a642` before the edit) and `post` (receipt `d4aa6353a38d2fd4…`). The two binaries are different artifacts and their output is the same bytes. |
| **M10S-I2b** | the 28 split seats replay identically pre vs post | **MET** — **28/28 seeds identical FIELD FOR FIELD** (`n`, `nrows`, `bad`, `flick`, `first`, `fired`, `vecused`); fabric-verdict agreement **28/28** and `first_bad` **28/28** on both runs, reproducing wave-8 §2's control |
| **M10S-I3** | the era override is printed, never silent | **HELD** — every `fz2_replay` run in this wave carries `--no-fabric-era-guard` and prints *"OVERRIDDEN"*. `hdl/rtl/system_large.sv` is a declared input of FLASH #17's receipt `287665a1027b42dd…`; the next flash re-syncs. **No fabric figure is quoted anywhere in this document.** |

**No G6 build was run and none was registered.** M10S-I1 says why: the
instrument claims no behaviour change and the synthesis text is provably
unmoved. Hygiene gates re-measured on the edited tree anyway: **`r7_lint`
PASS** (0 undeclared carriers, 0 undeclared unresolved, 0 `stop` violations, 51
`stop` sites) · **`ss_lint` PASS, `103×2 + 122×2 + tag = 226`, `ss_flopcensus`
214 flops / 0 UNMAPPED — UNMOVED** (the probe adds no core flop; it is in
`system_large`, not in `v30_core`) · **`test_artifact` 45/45, NON-VACUOUS**.

---

## §3 THE FALSIFIER — MET, WITH ZERO OFFSET

Reference column taken **before the edit** on `tb_v30_core` (`--core ucore`
receipt `5ef6eb3dc44ff23e…`), all three seats SOLVED, `d ∈ [-12,+1]`.
New leg: `tb_sys ret` receipt `d4aa6353a38d2fd4…`.
`python3 sw/fz2_m10sys_falsify.py`:

```
  M10S-F1  register values IDENTICAL   1050/1050   over 42 freezes   MET
  M10S-F2  SSA_B_CUR_ADDR IDENTICAL   42/42                          MET
  M10S-F3  non-vacuity: distinct SP 6 (>=20), distinct biu_addr 11 (>=20)   MISSED
  derived cross-check: chip_fits/core_fits sets identical 84/84
```

* **M10S-F1 MET at 1,050/1,050 with `--offset 0`.** The one permitted repair
  (M10S-F1a, a single integer row offset) **was not needed and was not used**.
  The row↔core-clock correspondence derived in §1 is correct as derived.
* **M10S-F2 MET 42/42.**
* **M10S-F3 MISSED, and it is reported as MISSED.** **ERRATUM E-M10S-1:** the
  bar was arithmetically unmeetable when it was written, and that is the
  author's error, not a finding. The 42 freezes are fourteen CONSECUTIVE core
  clocks on each of three seats, and a stack pointer is *supposed* to be nearly
  constant over fourteen adjacent clocks; asking for 20 distinct `SP` values
  across them could not have succeeded. The falsifier tool's exit code is
  therefore **F1 ∧ F2 — wave-8's registered falsifier, verbatim and
  unwidened** — and F3 is computed, printed and never gates. The erratum is
  written into `sw/fz2_m10sys_falsify.py` itself.
* F3's *intent* — "the probe is reading, not emitting a constant" — is carried
  by F1: 1,050 values matched a reference taken on a **different harness**, and
  a constant-emitting probe fails that catastrophically. **POST-HOC and
  labelled as such** (not a bar): one whole stream at `fz2e/524030`, `d = -1`,
  is **226 words, `SS_TAG` `0x8DE2`** (= `SS_VERSION` 0x8D / `SS_COUNT` 226,
  `ss_lint`'s own constants), **47 distinct values, 115 non-zero**.

**INSTRUMENT VERDICT: the port measures what `tb_v30_core` measures, and it is
accepted.**

---

## §4 THE RE-DERIVATION

### §4.1 What the new leg bought — the whole point, measured

`fz2_m10.py solve --tb sys` on the 13 frozen DERIVE seats: **SOLVED 13 / 13.**
On `tb_v30_core` it is **7 / 13** (wave-8 §2, reproduced on this tree).
**All SIX of wave-8's NOREPRO seats are repaired** — `fz2e/524007`,
`fz2e/531018`, `fz2e/533025`, `fz2e/529067`, `fz2e/518004`, `fz2e/518053` —
so **M10S-Y3 is answered: the NOREPRO class was the harness, seat for seat, and
not one seed.** Three waves were funded on a derivation population one
instrument was shrinking by ~46 %; that is now closed.

### §4.2 The per-seat solve table (M10S-Y2 — all 13, failures included)

`d` is the FORK FREEZE, identified from the data as the last freeze before
`biu_addr` becomes the core's own forking address. "decoration" is what fits
the CHIP's address there: `UNDEC` = a bare `SEG:TERM`, no `&` and no `|`.

| seat | pkg@dist | div | bytes | on wave-8 | chip / core | `--tb sys` | freezes w/ any chip fit | decoration at the fork freeze |
|---|---|---:|---|---|---|---|---:|---|
| `fz2e/501069` | --@- | 1960 | `ac` | SOLVED | `00004` / `00004` | SOLVED | 0 | EMPTY |
| `fz2e/510043` | --@- | 2259 | `aa` | SOLVED | `00004` / `00004` | SOLVED | 0 | EMPTY |
| `fz2e/518004` | P4@1 | 388 | `30 01` | NOREPRO | `90904` / `909ce` | SOLVED | 8 | AND-only |
| `fz2e/518006` | P4@1 | 479 | `81 42 3c bc 54` | SOLVED | `c2c39` / `c2c39` | SOLVED | 5 | UNDEC IND,M_EA,WB_EA |
| `fz2e/518053` | P4@1 | 3413 | `32 2c` | NOREPRO | `f27e2` / `f2762` | SOLVED | 1 | EMPTY |
| `fz2e/518067` | P4@1 | 3278 | `6a 83` | SOLVED | `55a39` / `56230` | SOLVED | 0 | EMPTY |
| `fz2e/524007` | P4@1 | 2257 | `79 d7` | NOREPRO | `a1ceb` / `93640` | SOLVED | 0 | EMPTY |
| `fz2e/524030` | P4@0 | 2611 | `8f cb` | SOLVED | `33f00` / `2df00` | SOLVED | 14 | **UNDEC SP,TMPB,IND** |
| `fz2e/529067` | P4@0 | 16 | `8f db` | NOREPRO | `7b0a7` / `7a8a6` | SOLVED | 14 | **UNDEC SP,TMPB,IND** |
| `fz2e/530001` | --@- | 20 | `86 79 68` | SOLVED | `e0ed2` / `d86c1` | SOLVED | 0 | EMPTY |
| `fz2e/531018` | P4@1 | 2212 | `7c 48` | NOREPRO | `36f64` / `26fc1` | SOLVED | 0 | EMPTY |
| `fz2e/533025` | P4@1 | 1041 | `6a 2c` | NOREPRO | `b5fb9` / `b3f98` | SOLVED | 14 | UNDEC M_EA,WB_EA |
| `fz2e/535027` | --@- | 3226 | `a4` | SOLVED | `f202c` / `93f02` | SOLVED | 14 | no freeze lands on the core's own address |

### §4.3 THE YIELD, AND AN ERRATUM AGAINST THIS WAVE'S OWN PRE-REGISTRATION

**M10S-Y1: usable = 5.** The registered rule — *"usable ≥ 5 → derive;
≤ 4 → BOOK"* — is **MET at its exact floor**, against wave-8's expected
**6-9**. The five are `518004`, `518053`, `524030`, `529067`, `533025`. The
derivation was therefore run, as registered.

> **ERRATUM E-M10S-2 — THE REGISTERED `usable` DEFINITION OVER-COUNTS, AND IT
> IS DISCLOSED RATHER THAN REPAIRED.** It asked for *"at least one freeze in
> `[-12,+1]` yields a NON-EMPTY `chip_fits` set"*. That admits a seat whose only
> hit is at a freeze standing on some **earlier** cycle's address:
> **`fz2e/518053`'s single hit is at `d = -7`, where `biu_addr` is `33616` —
> six freezes before the forking cycle's address is in the BIU — and it is
> EMPTY at the fork freeze.** The right clause would have said *"at the fork
> freeze"*, which yields **4**, below the bar. Repairing the definition after
> seeing the count is what a pre-registration exists to forbid, so the number
> reported against M10S-Y1 is **5** and this erratum stands beside it. Both
> readings are in §4.2 and a reader may apply either.

### §4.4 M10S-Q1 — WHAT SILICON CONSUMED, AND WHICH SEATS MAY SAY SO

`sw/fz2_m10sys_decor.py` partitions every seat at its fork freeze. The
attribution that matters is **whether the core's ghost arm is the thing forming
the core's address at all** — because a seat whose fork is some other cycle
cannot speak about the ghost. That is a bit-exact test against the RTL's own
expression, `ghost_bus_off = … : (ghost_off & gpr[R_SP])` (`v30u_eu.sv:1540`),
evaluated from the frozen registers:

| seat | pkg@dist | `core == ghost_off & SP` | chip's decoration |
|---|---|---|---|
| `fz2e/524030` | P4@0 | **YES, bit-exact** | **UNDECORATED** |
| `fz2e/529067` | P4@0 | **YES, bit-exact** | **UNDECORATED** |
| `fz2e/524007` | P4@1 | **YES, bit-exact** | EMPTY (M10 reading (i): upstream value divergence) |
| `fz2e/518004` | P4@1 | no | AND-only, and DEGENERATE — every fit is `SS:AW&X` with **`AW = 0x0005`**, a three-bit mask |
| `fz2e/518053` | P4@1 | no | EMPTY |
| `fz2e/518067` | P4@1 | no | EMPTY |
| `fz2e/531018` | P4@1 | no | EMPTY |
| `fz2e/533025` | P4@1 | no | UNDEC `M_EA`/`WB_EA` — but the core's address here is `SP & M_EA`, **not** `ghost_off & SP` (`0x0028` ≠ `0x4018`), so this fork is **not the core's ghost arm** and it does not enter the count |
| `fz2e/518006` | P4@1 | no | chip **==** core: no address to explain (wave-8's exclusion, unchanged) |

**THE ANSWER, on the population entitled to give one:**

> Of the three seats where the core's ghost arm demonstrably forms the address,
> **two have a chip address reproducible from named state, and BOTH are
> UNDECORATED — a segment base plus ONE named register, no `&`, no `|`.**
> **2 of 2.** The core's value on the same two is reproduced **to the bit** as
> `ghost_off & gpr[R_SP]`.

Worked, so it can be checked (`SS` base, fork freeze):

```
fz2e/524030   SS=252b   chip 33f00-252b0 = ec50 = SP = TMPB = IND      undecorated
                        core 2df00-252b0 = 8c50 = 8d56 & ec50 = ghost_off & SP
fz2e/529067   SS=7239   chip 7b0a7-72390 = 8d17 = SP = TMPB = IND      undecorated
                        core 7a8a6-72390 = 8516 = c596 & 8d17 = ghost_off & SP
```

Wave-8's single seat is now **two**, and the second is one wave-8 could not
reach at all. **Wave-8's closing question — "whether the AND happens" — is
answered on this population: it does not.**

### §4.5 WHY THAT IS NOT YET A LAW, AND THE TWO REASONS ARE INDEPENDENT

**(a) "DELETE THE AND" IS REFUTED BEFORE IT CAN BE PROPOSED — by the tree's own
artifact, not by this wave's data.** `v30u_eu.sv:1531` records wave-4's
measurement in the OPPOSITE direction: on `fz2c/410008`, `fz2e/519016` and
`fz2e/520040` **the CHIP performs the AND and the core did not**, and
`SS:(ghost_off & SP)` reproduced the chip exactly. Its own closing sentence is
the state of play and this wave does not move it:

> *"The two free choices left standing are WHICH RAIL and WHETHER THE AND
> HAPPENS; only the second is settled here, and only in the direction 'not by a
> mask'."*

So the AND is **real on some seats and absent on others**, and the deliverable
is a **PREDICATE**, not a deletion. The core already carries the arm the
predicate would select — `(eu_ghost_idle && !q_ripe) ? gpr[R_SP]`, wave-4's V2,
measured at **+2 closed / 1 LOST** (`fz2c/410034`). On `524030` and `529067`
that arm's answer is the right one and **the arm did not fire**. *That* is the
open mechanism, and it is one predicate over registered state, naming no
opcode.

**(b) THE RAIL IS STILL UNDETERMINED, AND IN EXACTLY WAVE-8's WAY.** On both
speaking seats the undecorated value is held **simultaneously by `SP`, `TMPB`
and `IND`** — `ec50` on one, `8d17` on the other. Two seats with the SAME
three-way degeneracy discriminate no better than one did. Wave-8 wrote *"one
seat, with two candidate rails degenerate on it, is not a derivation — it is a
coincidence with a receipt"*; two seats with three degenerate rails is the same
sentence with a bigger number.

**M10S-Q3, the SIMPLICITY STOP, was registered before the data was seen and it
applies here.** A predicate chosen now would be selected on two seats and
scored on a HOLDOUT whose closeable population is **one seat** (`fz2e/521059`,
wave-8 erratum E-W8-2). That is §64.1's pattern exactly, and the standing rule
is that its score would not be evidence.

**THE DISPOSITION IS THEREFORE: BOOK. NO LAW IS REGISTERED, NOTHING IS BUILT,
NOTHING IS LANDED, AND THE HOLDOUT IS HANDED ON SEALED.**

---

## §5 THE REGISTERED PREDICTIONS, ANSWERED

| id | registered | outcome |
|---|---|---|
| **M10S-I1a/b/c** | preprocessor identity, `gen_ucore_qsf`, mechanical byte-compare | **ALL MET** — `sha256 3cb6199cc827af46…` identical |
| **M10S-I2a** | `fz2_tbsys inert` PASS | **MET** — 4,000 × 2 records BYTE-IDENTICAL |
| **M10S-I2b** | 28 seats identical pre/post | **MET** — field for field, 28/28; verdict 28/28; `first_bad` 28/28 |
| **M10S-I3** | era override printed | **HELD** — no fabric figure quoted |
| **M10S-F1** | 1,050 values byte-identical | **MET, 1,050/1,050, offset 0** |
| **M10S-F1a** | the one permitted repair | **NOT USED** — no offset was needed |
| **M10S-F2** | `SSA_B_CUR_ADDR` identical | **MET, 42/42** |
| **M10S-F3** | ≥ 20 distinct `SP` and `biu_addr` | **MISSED — 6 and 11.** Erratum **E-M10S-1**: unmeetable when written; reported, never gating |
| **M10S-Y1** | usable ≥ 5 → derive | **MET AT THE FLOOR, 5.** ⚠ erratum **E-M10S-2**: the definition over-counts; at the fork freeze it is **4** |
| **M10S-Y2** | per-seat table, failures included | **HELD** — §4.2, all 13 |
| **M10S-Y3** | NOREPRO repair reported seat by seat | **HELD — 6 of 6 REPAIRED**, 13/13 SOLVED against 7/13 |
| **M10S-Q1** | (rail, decoration) per usable seat | **HELD** — §4.4 |
| **M10S-Q2** | one mechanism-level predicate | **NOT REACHED** — see §4.5 |
| **M10S-Q3** | SIMPLICITY STOP | **TAKEN** |
| **M10S-C1** | cascade honesty | **HELD** — no closure claimed for any seat; 10 of the 13 DERIVE seats carry `div` from 388 to 3,413 |
| **M10S-C2** | no closure count registered in advance | **HELD** — and none was needed, because no law reached the point of predicting one |
| **M10S-H1/H2/H3** | HOLDOUT sealed | **HELD.** No `solve` was run against any HOLDOUT seat and no register value from one was read. The only thing that touched them is I2b's `fz2_replay` verdict/first-bad measurement, disclosed in the pre-registration before it ran |
| **§6 ladder / G6** | applies only to a behaviour landing | **NOT APPLICABLE** — nothing landed. `r7_lint` PASS, `ss_lint` 226/214 UNMOVED, `test_artifact` 45/45, `gen_ucore_qsf --check` up to date, all re-measured on the edited tree |

---

## §6 WHAT THE NEXT WAVE INHERITS

1. **A WORKING INSTRUMENT.** `fz2_m10.py solve --tb sys` reaches **13/13**
   where the old leg reached 7/13, and it is proved against the old leg at
   1,050/1,050. Every future ghost question is asked on it.
2. **A CLEAN, UNBURNED HOLDOUT of 15.** Still never solved, scored or
   inspected. Its closeable population remains **one seat** (`fz2e/521059`) —
   which is the honest reason no closure bar should be registered against it
   again without saying so.
3. **THE QUESTION, NARROWED TO ONE PREDICATE.** Not *"which rail"* and no
   longer *"whether the AND happens"* — **"when does it happen?"** The RTL
   already carries the arm (`(eu_ghost_idle && !q_ripe) ? gpr[R_SP]`,
   `v30u_eu.sv:1541`); on `fz2e/524030` and `fz2e/529067` its answer is right
   and it did not fire, and on `fz2c/410034` it fired and should not have.
4. **THE FALSIFIER THE NEXT WAVE OWES.** A predicate must be selected on a
   population that includes BOTH polarities — the two undecorated seats here
   AND wave-4's three ANDed seats (`fz2c/410008`, `fz2e/519016`,
   `fz2e/520040`, which the wave-4 landing has since CLOSED, so they are not in
   the F17 ledger and must be re-reached deliberately) — and then validated on
   data that did not select it. **§64.1 governs.**
5. **A MEASUREMENT WORTH TAKING FIRST, AND CHEAPLY:** `SSA_B_Q_CNT` is in the
   map at `9'h02E`. `q_ripe` is the term the existing arm gates on and it is
   *not* directly mapped; deciding whether it should be is a smaller question
   than the law, and it is answerable offline on the instrument this wave
   built.

---

## §7 DISCIPLINE NOTES

* **The pre-registration was committed at `fd68408937`, and the ORDER is the
  evidence**: `hdl/` was untouched at that commit, the falsifier's reference
  column was taken on the pre-edit tree, and the first `--tb sys` DERIVE solve
  ran afterwards.
* **Two errata are reported against this wave's own pre-registration**
  (E-M10S-1, E-M10S-2), **both in the direction that makes the wave look
  worse**, and neither is repaired after the fact.
* **The yield rule was met at its floor and the wave still books.** Meeting a
  bar entitles you to run the derivation; it does not entitle you to a law.
* **Nothing was built to score.** Wave-6's and wave-8's precedent: a DERIVE
  that cannot found a law ends the wave. A probe built and scored anyway would
  have produced a HOLDOUT number with nothing behind it.
* **No board, no flash, no Quartus, `sim/` not extended.** The board carries
  FLASH #17 and this wave did not touch it. No fabric figure is quoted, and
  every `fz2_replay` number here was taken under `--no-fabric-era-guard`, which
  is printed beside it.
* **Capture files are gitignored in the main checkout and were reached through
  symlinks in `sw/testdata/campaigns/{fz2c,fz2e}/captures`, removed before this
  commit.**

## §8 RE-RUNNING THIS

```bash
git rev-parse HEAD                                   # 6cbb01a642 + wave-9's commits
python3 sw/check_core.py --build --core ucore        # the reference leg
python3 sw/x1_retention.py build --leg ret           # the M10-SYS leg
# link the gitignored captures into sw/testdata/campaigns/{fz2c,fz2e}/captures first
L=sw/testdata/fz2/fz2_failure_ledger_f17_2026-08-11.json
python3 sw/fz2_m10.py survey --ledger $L --out /tmp/m10_survey_f17.json
D=fz2e/501069,fz2e/510043,fz2e/518004,fz2e/518006,fz2e/518053,fz2e/518067,\
fz2e/524007,fz2e/524030,fz2e/529067,fz2e/530001,fz2e/531018,fz2e/533025,fz2e/535027
python3 sw/fz2_m10.py solve --ledger $L --survey /tmp/m10_survey_f17.json \
        --seeds fz2e/524030,fz2e/518006,fz2e/518067 --tb core --out /tmp/ref.json
python3 sw/fz2_m10.py solve --ledger $L --survey /tmp/m10_survey_f17.json \
        --seeds fz2e/524030,fz2e/518006,fz2e/518067 --tb sys  --out /tmp/new.json
python3 sw/fz2_m10sys_falsify.py --core-solve /tmp/ref.json --sys-solve /tmp/new.json \
        --stream-seat fz2e/524030            # -> F1 1050/1050, F2 42/42, PASS
python3 sw/fz2_m10.py solve --ledger $L --survey /tmp/m10_survey_f17.json \
        --seeds $D --tb sys --jobs 7 --out /tmp/derive.json     # -> SOLVED 13/13
python3 sw/fz2_m10sys_decor.py --solve /tmp/derive.json --survey /tmp/m10_survey_f17.json
python3 sw/fz2_tbsys.py inert                        # after `baseline --tag pre/post`
python3 sw/fz2_replay.py --ledger $L --seeds <the 28> --leg ret --no-fabric-era-guard
```
