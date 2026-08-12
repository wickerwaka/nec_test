# fz2 WAVE-9 — `M10-SYS`: THE SAVE-STATE FREEZE ON `tb_sys`, AND THE WAVE-8 RE-DERIVATION — PRE-REGISTRATION

Branch `fuzz-v2-on-relanding`, base **`6cbb01a642`** (`git rev-parse HEAD`
verified; the worktree provisioned at `master`/`29dcc5b05f` and was reset).
**Offline throughout — no board, no flash, `sim/` not extended.**

This document is committed **BEFORE `hdl/rtl/system_large.sv` is touched** and
**BEFORE any DERIVE solve is run on the new leg**. Wave-8's frozen split
(`docs/notes/fz2_w8_split.json`, `4f6a2a383f`) governs and is not re-derived.

Read first: `docs/notes/fz2_w8_ghostsel_results_2026-08-11.md` §2 (the
instrument is the blocker) and §3 (`M10-SYS`, designed, with its falsifier).

---

## §0 WHAT THIS WAVE IS, IN ONE PARAGRAPH

Wave-8's derivation was **NOT EVALUABLE at n = 1**, and §2 measured why: the
M10 solve freezes through `tb_v30_core`, which has ONE pin-event scheduler, and
**6 of 13 DERIVE seats are `NOREPRO` on it** for harness reasons — while
`fz2_replay --leg ret` on `tb_sys` reproduces the fabric verdict and the fabric
`first_bad` on **28 of 28** of the same seeds. This wave moves the freeze to the
instrument that can follow the corpus, proves the move with a falsifier before
using it, and then re-runs wave-8's DERIVE solve.

The deliverable is **either a mechanism-level law with a HOLDOUT score, or a
second BOOK that names what is left.** A book is a real result and is
pre-registered as an acceptable outcome.

---

## §1 THE INSTRUMENT — WHAT IS BUILT

`hdl/rtl/system_large.sv:410-413` instantiates the ucore with its save-state
port TIED OFF (`.SS_ADDR(9'b0)`, `.SS_WDATA(16'b0)`, `.SS_WE(1'b0)`,
`.SS_RDATA(core_ss_rdata_unused)`). The three command signals and the read-data
signal already exist; nothing new is designed.

**The probe is a READ-ONLY TERMINAL FREEZE, and all three words are load-bearing.**

* **READ-ONLY.** `SS_WE` is **never asserted**. `ss_mode=6` on `tb_v30_core`
  does `ss_save` → print → `ss_load`; the `ss_load` writes back exactly what it
  read and exists only so the run can RESUME. This probe never resumes, so it
  never writes. That removes the whole `SS_WE`-while-`CE`-high hazard class
  (`v30_core.sv:138`) by construction rather than by discipline.
* **TERMINAL.** `fz2_m10._one_solve` **discards the rows of every freeze run**
  (`_r, ss = replay(seed, ss_at=fb + d)`) — the fork validation is a SEPARATE
  un-frozen replay. So the freeze need not be resumable, and the probe
  `$finish`es after streaming. This is not a shortcut taken to avoid work; it
  is the reason a park that stops only the CORE is sufficient.
* **FREEZE.** `CE`/`CE_HALF` to the core are gated off from the freeze point
  on. `nec_bus` keeps ticking; it cannot move the core, because every
  architectural flop in `v30u_eu`/`v30u_biu` is gated by `ss_we || srst || ce`,
  and the save-state read path (`ss_addr_q`, the two read muxes) is
  `always @(posedge clk)` with **no `CE`**, which is exactly why the stream can
  run while the core is stopped.

**WHERE THE FREEZE POINT IS, DERIVED NOT ASSUMED.** `nec_bus.sv:687` writes one
`cap_record` per CPU clock at the `tick_rise` posedge — the SAME posedge at
which the core's `CE` is high, because `CE == bus_tick_rise`. `tb_v30_core`
emits its row at its own `CE` posedge, recording the cycle just ending. So row
`k` on the two harnesses is the same core clock by construction. The probe
counts `cap_valid` records whose `cap_record[55]` (`rst`) is 0 — which is
`fz2_replay._drop_reset`'s own rule, the rule that makes a `tb_sys` row index
mean what a banked row index means — and parks after that cycle's `tick_fall`
has been delivered and before the next `tick_rise`, so cycle `k` gets both its
`CE` and its `CE_HALF`, exactly as `ss_park` does on `tb_v30_core`.

**SIMPLICITY, verbatim (standing design principle, user directive 2026-08-01):**
*"SIMPLICITY: this is 80's era hardware — nothing on the die is wasted. Complex
or confusing observed behavior is likely simple systems interacting in ways not
yet understood. A large fitted table, a many-cased rule, or a per-opcode special
case is a signal of misunderstanding, not a deliverable."*

---

## §2 THE INERTNESS CLAIM — REGISTERED WITH ITS PROOF METHOD, BEFORE THE EDIT

Any text change to `system_large.sv` moves the 88-file Quartus manifest. Two
separate claims are made and each has its own check.

### M10S-I1 — THE SYNTHESIS NETLIST IS UNCHANGED, BY PREPROCESSOR IDENTITY

`hdl/nec_test_ucore.qsf:71` and `hdl/nec_test.qsf:60` both set
`VERILOG_MACRO "SYNTHESIS=1"`. Every line the probe adds to the *existing*
text — the five instantiation port connections and the one wire declaration —
is written as

```
`ifdef SYNTHESIS
    <the line exactly as it stands at 6cbb01a642>
`else
    <the probe's line>
`endif
```

and the probe body itself lives inside a single `` `ifndef SYNTHESIS `` block.
**Under `SYNTHESIS=1` the compiler therefore sees character-identical text**,
so the netlist cannot move — this is stronger than "we measured one build and
it looked the same", and it is checkable by reading the diff.

**PROOF, as run:** (a) the diff is exhibited and every `` `ifdef SYNTHESIS ``
arm is shown equal to `6cbb01a642`'s line; (b) `python3 sw/gen_ucore_qsf.py
--check` PASSES; (c) a mechanical check — strip every `` `ifndef SYNTHESIS ``
block and take the `` `ifdef SYNTHESIS `` arm of each guarded region, and the
result must be **byte-identical to `6cbb01a642:hdl/rtl/system_large.sv`**.

**NO RTL BEHAVIOUR CHANGE IS CLAIMED BY THE INSTRUMENT, SO NO G6 BUILD IS
REGISTERED FOR IT.** If — and only if — this wave goes on to land a
behaviour-changing RTL law, the full ladder including **G6, two draws, STOP
below 38.0 MHz** applies to that landing, and the G6 tree will carry the
instrument edit, whose `` `ifdef SYNTHESIS `` arms make it invisible to
Quartus. **If (c) fails, STOP and report before proceeding.**

### M10S-I2 — THE SIMULATION BINARY IS FUNCTIONALLY UNCHANGED WHEN THE PROBE IS UNARMED

With no `+ss_at` the probe's park is constant 0 and nothing is printed.

* **I2a** `python3 sw/fz2_tbsys.py inert` **PASS** — both reference runs
  (`noevent`, `legacy1`, 4,000 records each) **BYTE-IDENTICAL** between the
  `pre` baseline (captured at `6cbb01a642` before the edit, receipt
  `535199e70a46e326…`) and the `post` baseline.
* **I2b** `fz2_replay --leg ret --no-fabric-era-guard` over the 28 split
  seats reproduces, **row for row**, the run taken before the edit: the same
  verdict on 28/28, the same `first_bad` on 28/28, and the same `bad`/`flick`
  counts seed for seed.

**Disclosure:** I2b's population includes the 15 HOLDOUT seats. `fz2_replay`
reads **no register and no address** — it computes a verdict and a first-bad row
against banked socket rows — and wave-8 ran the identical measurement on the
identical 28 (its §2 control). It is a pre-law instrument measurement and it
does not open the HOLDOUT. See §5.

### M10S-I3 — THE ERA GUARD OVERRIDE IS PRINTED, NEVER SILENT

The edit moves `hdl/rtl/system_large.sv`, a declared input of the FLASH #17
bitstream receipt `287665a1027b42dd…`. **Every post-edit `fz2_replay`
invocation therefore carries `--no-fabric-era-guard`, and the override is
printed beside every number it produces.** The next flash re-syncs the era. No
fabric figure is quoted in this wave.

---

## §3 THE INSTRUMENT FALSIFIER — WAVE-8'S, NON-NEGOTIABLE

> *"On the three seats `tb_v30_core` already solves — `fz2e/524030`,
> `fz2e/518006`, `fz2e/518067` — the `tb_sys` freeze must return
> **byte-identical register terms at every freeze `d`**. A port that disagrees
> with the working instrument on the seats both can do is measuring itself."*
> — `fz2_w8_ghostsel_results_2026-08-11.md` §3

**REFERENCE COLUMN, TAKEN BEFORE THE EDIT** and frozen:
`fz2_m10.py solve` on `tb_v30_core`, `--core ucore` receipt
`5ef6eb3dc44ff23e…`, ledger `fz2_failure_ledger_f17_2026-08-11.json`, all three
seats **SOLVED**, `d ∈ [-12, +1]` (14 freezes each).

* **M10S-F1 (PRIMARY).** For each of the 3 seats and each of the 14 freezes,
  the `tb_sys` leg's `terms` dict (21 named values) and `segs` dict (4 segment
  registers) must be **EQUAL, VALUE FOR VALUE**, to the `tb_v30_core`
  reference. That is **3 × 14 × 25 = 1,050 exact 16-bit comparisons**.
  The `chip_fits` / `core_fits` sets, being functions of those values, must
  then agree too and are reported as a derived cross-check, not as the bar.
* **M10S-F1a (THE ONE PERMITTED REPAIR, REGISTERED IN ADVANCE SO IT CANNOT BE
  INVENTED AFTERWARDS).** If F1 fails, the only repair this wave may take is a
  **single integer row offset `c`**, the SAME `c` for all three seats and all
  fourteen freezes, applied to the probe's row counter and justified from the
  two harnesses' own definitions. With `c` applied, F1 must then hold on all
  1,050 values. **Any per-seat, per-`d`, or per-term adjustment is a REFUSAL:
  book the instrument as divergent and stop.** One integer cannot fake 1,050
  exact matches, which is what keeps the bar with teeth after the repair.
* **M10S-F2.** The two harnesses must also agree on `SSA_B_CUR_ADDR`
  (`biu_addr`) at all 42 freezes. This is the BIU's own statement of which
  cycle it is standing on, and it is the coordinate the solve is quoted against.
* **M10S-F3 (NON-VACUITY).** The probe must be shown to be *reading*, not
  emitting a constant: across the 42 freezes at least 20 distinct `SP` values
  and at least 20 distinct `biu_addr` values must appear, and the stream must
  carry the correct `SS_TAG` (`0x8DE2`, `SS_COUNT` 226) at address `0x000`.
  A probe that returned zeros would satisfy nothing else here, but it would
  pass a comparison against a reference that was also zero, and this is the
  clause that says so.

**IF THE FALSIFIER FAILS AND F1a DOES NOT REPAIR IT: FIX OR BOOK, NEVER DERIVE
ON A DIVERGENT INSTRUMENT.**

---

## §4 THE RE-DERIVATION — WAVE-8's REGISTERED YIELD RULE

Definitions, fixed here **before the DERIVE solve is run on the new leg**:

* **`SOLVED`** — `fz2_m10._one_solve` status `SOLVED`: the offline replay puts
  the fork at the board's row AND reproduces the board's core address.
* **`USABLE ghost-address seat`** — `SOLVED` **and** `near_package == P4`
  **and** `chip_addr != core_addr` **and** at least one freeze in `[-12, +1]`
  yields a NON-EMPTY `chip_fits` set. (These are exactly wave-8's three
  exclusions: NOREPRO, no address fork, EMPTY over 21 terms + 190 pairs.)

* **M10S-Y1 (WAVE-8's BAR, QUOTED).** *"DERIVE goes from **1** usable
  ghost-address seat to an expected **6-9** … **If it lands below 5, the next
  wave must say so and book again rather than fit.**"* So:
  **usable ≥ 5 → derive. usable ≤ 4 → BOOK, and name what is left.**
* **M10S-Y2.** The per-seat solve table is reported for all 13 DERIVE seats,
  including the failures and their reason, whatever the yield.
* **M10S-Y3.** Wave-8's §2 NOREPRO table names 6 seats. Whether the new leg
  repairs them is reported **seat by seat**, and a seat that is NOREPRO on
  `tb_sys` too is a finding about the seed, not the harness.

### The question, if the yield allows it

Not *"which rail"*. Wave-8's one usable seat measured silicon taking `SS:SP`
**UNDECORATED** — no rail, no AND — where the core applied `ghost_ea_off & SP`.
So:

* **M10S-Q1.** For each usable seat, solve what silicon consumed as a pair:
  **(rail identity, decoration)**, where decoration ∈ {none, `& X`, `| X`}.
* **M10S-Q2.** Then look for **ONE mechanism-level predicate** over registered
  state or the predecessor's ROM row that separates *undecorated* from
  *decorated* seats. Refuted already and not to be re-proposed: **no single
  static rail** (wave-6) and **no retention-at-issue** (wave-7).
* **M10S-Q3 (SIMPLICITY STOP).** If the separator needs a per-opcode case, a
  per-seat constant, or a table with more rows than it has seats, it is **not a
  law** and this wave books it. Stated before the data is seen.

### Cascade honesty

* **M10S-C1.** A seat whose baseline `bad` runs to the hundreds or thousands is
  a **registered NON-CLOSURE** even if its ghost address is fixed. Row
  improvement without closure is mechanism evidence and is reported as such,
  never as a closure. Wave-8 measured the genuinely closeable population at
  **four seats** — `fz2c/406006` 16, `fz2e/529067` 16, `fz2e/521059` 20,
  `fz2e/530001` 20 — of which two are DERIVE and two are HOLDOUT, and one of
  the HOLDOUT two (`fz2c/406006`, `pkg None`) is not a ghost seat at all
  (wave-8 erratum E-W8-2). **So the closeable HOLDOUT population is ONE seat,
  `fz2e/521059`.**
* **M10S-C2.** Because of C1, **no HOLDOUT-closure count is registered as this
  wave's deliverable.** Registering "≥ 2 closures" against a population of one
  is the mistake E-W8-2 already caught. If a law is registered, the HOLDOUT
  bar is stated **at that moment, in its own amendment, before HOLDOUT is
  scored**, and it will be stated as a prediction PER SEAT, not as a count.

---

## §5 THE HOLDOUT

**The 15 HOLDOUT seats are UNBURNED** — wave-8 never solved, scored or
inspected them. That is the only asset wave-8 handed forward.

* **M10S-H1.** No `fz2_m10.py solve` is run against any HOLDOUT seat, and no
  register value from one is read, until a law is registered in a committed
  amendment naming its shape and its per-seat predictions.
* **M10S-H2.** The pre-law `fz2_replay` verdict/first-bad measurement of §2's
  I2b is the ONLY thing touching HOLDOUT before that point. It reads no
  register and no address, it is wave-8's own §2 control re-run for an
  instrument-regression purpose, and it is disclosed here rather than left to
  be noticed.
* **M10S-H3.** If no law is registered, HOLDOUT is handed on still sealed and
  this document says so.

---

## §6 THE LADDER, IF RTL LANDS

Registered now so it cannot be trimmed later. Applies **only** to a
behaviour-changing landing, not to the instrument:

`gen_ucore_qsf --check` · `r7_lint` · rebuild + receipt ·
`ss_lint` **0x8D / 226 / 214** or a pre-registered bump ·
`test_artifact` **45/45** · `check_core --opcodes all --cases 0`
**169,000/169,000** and `8F.0` **500/500** · the four HLT sweeps **279/283**
(⚠ `--waits 0/1/2/3`) · `ulockstep --golden all --cases 50` **17,350/17,350** ·
`fz2_replay` full 113 with **DERIVE and HOLDOUT reported separately**,
**0 lost / 0 first-bad earlier** · `fz2_immaterial falsify` PASS ·
**G6 two draws, STOP below 38.0 MHz**, with the CONTROL build compared against
this branch's band.

**Named NON-MOVERS, unchanged:** `fz2c/404040`; the §64.1 four (`527`, `1331`,
`636`, `1475`); KM's three at 0; the 21 IMMATERIAL; the LEA-mod3 six.

---

## §7 DISCIPLINE

* This document is committed before `hdl/` is touched and before the first
  DERIVE solve on the new leg. The reference column of §3 was taken **before**
  the edit, on the pre-edit tree, and is frozen.
* Failures are reported **as registered**, never restated.
* A booked *"yield still below 5"* names what is left; that is a real result and
  is a pre-registered acceptable outcome of this wave.
* No board, no flash, no `sim/` change. Quartus only if behaviour lands.
* Capture files are gitignored in the main checkout and are reached through
  symlinks in `sw/testdata/campaigns/{fz2c,fz2e}/captures`; they are removed
  before any commit.
