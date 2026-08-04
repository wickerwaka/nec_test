# THE SILICON-MATCH RESIDUE CENSUS — session SM3, 2026-08-04

**Branch `ucsim`, from HEAD `369e4953ce`.  Offline only: banked captures,
Verilator and the C++ model.  No board was touched.**

This is the census the silicon-match phase (task #36) is built on.  Its job is
to say **what is still wrong against silicon, how much of it there is, and how
few mechanisms it takes to explain it** — under the 2026-08-04 correctness
target, where *"a divergence from silicon is a work item regardless of whether
the model shares it"*.

> **Standing principle, applied throughout.**  *"This is 80's era hardware, they
> aren't wasting silicon on anything that isn't necessary.  Complex or confusing
> behavior that we see is likely to be simple systems interacting in ways you do
> not fully understand yet."*  A large fitted table, a many-cased rule, or a
> per-opcode special case is a signal of misunderstanding, not a deliverable.
> The hypotheses in §5 are ranked by **population explained per mechanism**, and
> every one of them is one sentence long.

Companions: `ucore_provenance.md` §58-§59 (the phase ledger),
`ucore_gaps_2026-08-04.md` (the dated enumeration this census measures),
`invalidation_ledger.md` (INV-1, closed), `standing_gates.md` (the gate list).

---

## §0 EXECUTIVE SUMMARY

**One mechanism explains 82 % of the ucore's whole-program EVT residue and 76 %
of the model's, and it is the same seeds in both.**  It is new — the population
it lives in did not exist before SM2's re-capture.

| rank | mechanism | ucore seeds | sim seeds | shared | owner | §|
|---|---|---|---|---|---|---|
| **H1** | **the RE-ENTRY acknowledge's lead-in**: the chip idles **2 clocks** between the last prefetch and the INTA it is about to announce, and grants that slot to **nothing**.  The ucore fills it with a prefetch; the model announces immediately.  **LANDED IN `sim/` 2026-08-04 (SM3 sitting 2): EVT 363 -> 780, COMBINED 1,635 -> 2,052; discriminated on the socket by a directed cell that REFUTED both the redirect and the IRET readings — it is the RE-ENTRY, `ucore_provenance.md` §61 / `sm3_h1_prereg_2026-08-04.md`.  THE ucore LEG IS NOT TAKEN.** | **445 / 540** | **491 / 645** | **437** | **shared** — `sim/` first | §5.1 |
| H2 | the `qs -!=F` / `qs E!=-` queue-status pair around an acknowledge (the rest of the EVT column, both engines) — **NOT re-censused; its falsifier is "H1 lands and this family does not shrink" and the re-census belongs after the ucore leg** | 41 / 540 | 57 / 645 | — | shared | §5.2 |
| H3 | `PF_LOST`'s arbitration priority (the largest REGISTERED family, unchanged since ucsim-t) | 107 / 219 | 239 / 430 | 110 | shared | §5.3 |
| H4 | `DATA_SEQ` — F47's shape, *the right cycle, the right address, the wrong word*; **41 in the ucore's own engine against 28 in the model's** | 41 / 219 | 28 / 430 | 28 | mixed | §5.4 |
| H5 | the HALT-display decision edge (**F43**, diagnosed, twice declined) + the `seg`/`bus`-first half that is **not** diagnosed | 13 cells | — | — | ucore | §5.5 |
| H6 | the fabric INTA float-retention class (**X1**, attribution NOT ESTABLISHED, fabric leg BLOCKED) | 116 cells | — | — | harness | §5.6 |

**And one negative result that matters more than a fix would have.**  §T.8's
attribution of the three byte-swap seeds to *"M5b's A0 swapper applied where the
chip does not"* is **REFUTED by measurement** (§6.1).  One of the three has the
**opposite sign** — the chip rotates at an **even** address where the model does
not — so no removal or narrowing of the A0 rotator can close the three, and
M5b's own four-quadrant measurement forbids removing it.  Item 2.1 of this
session's work order is reported as a refutation and **no code was changed.**

---

## §1 WHAT WAS MEASURED, AND WITH WHAT

Everything below was **run on this tree in this session** unless the row says
"cited".  The engine is stated every time, because in the EVT population the two
engines are not doing the same thing (§2.1).

| measurement | tool | population |
|---|---|---|
| the bank, both engines | `timed_fuzz --core {ucore,sim} --evt-replay` | 3,242 banked seeds, 2,710 scored |
| the ucore's REGISTERED families | `s15_census --core ucore --pop reg` | its own 219 |
| **the ucore's EVT families — the first ever taken** | `s15_census --core ucore --pop evt` | its own **540** |
| **the model's EVT families** | `s15_census --core sim --pop evt` | its own **645** |
| the byte-swap seeds, row by row | `sw/sm3_bswap.py` (new) | §49.7's four |
| the novelty-ledger control | `sw/sm3_sigctl.py` (new) | all 3,242 |

**`--core` matches the report's core everywhere.**  That is R4's rule and it is
load-bearing: pointed at a `--core ucore` report with the default engine,
`s15_census` reports the MODEL's families for the ucore's seeds.

---

## §2 THE POPULATIONS, AND THE PARTITION

### §2.1 A caveat that has to come first: the two engines are not symmetric on EVT

On the REGISTERED bank both engines are handed the same thing and a
seed-by-seed partition means what it looks like it means.  **On the EVT
population they are not:**

* the **model** is HANDED the capture's acknowledge positions
  (`tf.evt_directive`) — it does not predict them;
* an **RTL core** is handed the rig's own directive (address / delay / hold /
  pin) and **predicts** them.

So "shared" on EVT means *both engines diverge from silicon on this seed*, not
*both engines have the same defect*.  §5.1 is the case where it happens to be
the same defect seen from two sides, and that is established by looking at the
rows, not by the partition.

### §2.2 The partition, measured

| population | scored | **ucore non-exact** | **sim non-exact** | ucore-ONLY | sim-ONLY | shared | net |
|---|---|---|---|---|---|---|---|
| **REGISTERED** | 1,702 | **219** | **430** | **9** | 220 | 210 | **+211** |
| **EVT** (rebuilt by SM2) | 1,008 | **540** | **645** | **5** | 110 | 535 | **+105** |
| COMBINED | 2,710 | 759 | 1,075 | 14 | 330 | 745 | +316 |

The REGISTERED row reproduces §58.4's 9 / 210 / 220 **exactly**, seed for seed.
The EVT row is **new** — SM1 measured 547 / 269 / 30 on the poisoned column and
INV-1 struck it; on the rebuilt column the ucore-only count is **5**, not 547.

**The 5 ucore-only EVT seeds, named** (the complete set on which the model is
cycle-exact and the ucore is not, on the whole-program event axis):

| seed | family | first-div signature | waits | `ndiff` |
|---|---|---|---|---|
| `mc1/soup_1629_7310be164394` | `PIN` | `data` | wrand7 | **2** |
| `mc1/soup_2468_33163af77a68` | `PF_GAINED` | `qs -!=F` | wrand7 | 760 |
| `mc2/raw_549_c9c3fdc79100` | `PF_LOST` | `qs F!=-` | wrand3 | 3,707 |
| `mc2/soup_327_69333036edc4` | `DATA_SEQ` | `t Ti!=T1` | fix2 | 1,370 |
| `mc2/soup_596_bff73eb0db4b` | `PF_LOST` | `bs PASV!=HALT` | fix1 | 1,221 |

All five are **waited or fixed-wait ≥ 1**; none is at w0.  `soup_1629` with
`ndiff = 2` is the cheapest open ucore-only seed in the tree.

---

## §3 FAMILY × POPULATION — the ucore, its own engine

| family | **REGISTERED (219)** | **EVT (540)** | total |
|---|---|---|---|
| `PF_GAINED` | 25 | **463** | 488 |
| `PF_LOST` | **107** | 22 | 129 |
| `DATA_SEQ` | **41** | 14 | 55 |
| `SCHEDULE` | 5 | 29 | 34 |
| `TAIL_EXTRA` | 28 | 5 | 33 |
| `PF_ADDR` | 9 | 3 | 12 |
| `PIN` | 4 | 4 | 8 |
| catch-all | **0** | **0** | **0** |
| **total** | **219** | **540** | **759** |

The REGISTERED column reproduces §58.4 cell for cell (`PF_LOST` 107 ·
`DATA_SEQ` 41 · `TAIL_EXTRA` 28 · `PF_GAINED` 25 · `PF_ADDR` 9 · `SCHEDULE` 5 ·
`PIN` 4), re-measured rather than inherited.  **The catch-all is empty in both
columns**, which is the taxonomy's own self-test.

**The EVT column is a different machine from the REGISTERED one.**  `PF_GAINED`
goes from 11 % of the residue to 86 %; `PF_LOST`, which owns the registered
bank, is 4 % here.  That is not a new prefetcher — it is one arbitration slot,
§5.1.

### §3.1 The same table for the model

**The EVT column was measured this session; the REGISTERED column is CITED**
(§58.4 / §T.3 — `s15_census --core sim --pop reg` was not re-run here, and the
seed-level partition in §2.2 that reproduces it does not involve `s15_census`).

| family | **REGISTERED (430, cited)** | **EVT (645, measured)** |
|---|---|---|
| `SCHEDULE` | 79 | **563** |
| `PF_LOST` | **239** | 44 |
| `PF_GAINED` | 23 | 15 |
| `TAIL_EXTRA` | 30 | 3 |
| `DATA_SEQ` | 28 | 5 |
| `PF_ADDR` | 17 | 6 |
| `PIN` | 14 | 9 |
| **total** | **430** | **645** |

`SCHEDULE` 563 against the ucore's 29 is the same fact wearing the other
engine's clothes: the model runs **the same cycles at the wrong clock** where
the ucore runs **a different cycle**.  §5.1.

### §3.2 Severity

| | ucore REG (219) | ucore EVT (540) | sim EVT (645) |
|---|---|---|---|
| functional event stream PARTS | 159 | 364 | 27 |
| functional stream TRUNCATED only | 57 | 63 | 404 |
| architectural state AGREES | 1 | **413** | 507 |
| architectural state DIFFERS | 1 | **2** | 0 |
| no arch dump inside the window | 217 | 125 | 138 |

**On EVT the ucore is architecturally right on 413 of 540 and wrong on 2**
(one `PSW`, one `AW`).  The residue is overwhelmingly a *timing* residue with a
truncated functional stream behind it, which is what a mis-timed acknowledge
produces: the streams part because one side entered the handler at a different
clock, not because either computed a different answer.

---

## §4 THE OTHER RESIDUE POPULATIONS, FOR SCALE

Cited, not re-measured this session, except where stated.

| population | size | ucore residue | where |
|---|---|---|---|
| REGISTERED fuzz bank | 1,702 | **219** | §3, re-measured |
| EVT fuzz bank | 1,008 | **540** | §3, re-measured |
| the four HLT delay sweeps, offline | 283 | **24** (13 ucore-only) | `gaps` §T.1 |
| the four HLT delay sweeps, **in fabric** | 283 | **140** (116 the INTA class) | `prov` §56.1, §59.7.10 |
| the b2 victory tranche | 188 | **17** — V5, a standing REGISTERED FAILURE | `prov` §44.2 |
| the b3 priority tranche, in fabric | 178 | **2** (`bs`) | §59.7.9 |
| the 500-seed in-silicon population | 449 | **14** (`bs` 11 · `qs` 3) | §52.7 |
| §49.7's shared seeds | 4 | **4** | §6.1, **re-measured, attribution REFUTED** |

---

## §5 MECHANISM HYPOTHESES, RANKED BY POPULATION EXPLAINED

### §5.1 H1 — THE RE-ENTRY ACKNOWLEDGE'S LEAD-IN. **445 ucore + 491 sim seeds, 437 of them the same seed.**

**This is the single largest mechanism in the whole silicon-match residue, and
it is one clock-count.**

The EVT population is what it is because `fuzz_campaign` injects `hold = 300`
on its `has_halt` branch: the part halts, an INT level is raised for 300 clocks,
and — now that the rig can actually apply 300 (INV-1) — **the part enters its
handler four or five times**, IRET-ing out and being re-recognised each time.
430 of the 445 seeds carry exactly one HALT cycle and 4-5 acknowledge sequences.

**The measurement.**  Of the ucore's 463 `PF_GAINED` seeds, **445 have `INTA` on
the chip and `CODE` in the core at the first cycle the two sequences differ**,
with **`delta = -2` on all 445** and the divergence sitting **3 rows before the
chip's INTA T1** on all 445.  It is not the first acknowledge: it is at
acknowledge **#2 in 382 of the 445**, #3 in 36, #4 in 25, and the FIRST
acknowledge — the wake from HALT — is right in 443 of 445.

**And 445 of 445 have the chip's divergent INTA1 T1 exactly 6 clocks after the
preceding CODE fetch's T1.**  A zero-wait fetch is 4 clocks, so there are **two
idle clocks** between the fetch and the acknowledge's announcement.

`mc1/soup_1047_dcd0e4dff22a`, one row per clock, all three engines:

```
 clk   CHIP                UCORE               SIM
 363   T1 CODE 00509       T1 CODE 00509       T1 CODE 00509
 364   T2 CODE             T2 CODE             T2 CODE
 365   T3 PASV             T3 PASV             T3 PASV
 366   Ti PASV   <- idle   Ti CODE 0050a  <-   Ti INTA 081f4   <-
 367    ? PASV   <- idle   T1 CODE 0050a       T1 INTA
 368    ? INTA (display)   T2 CODE             T2 INTA 00ff
 369   T1 INTA 081f4       T3 PASV             T3 PASV
 370   T2 INTA 00ff        Ti INTA 0453e       ...
 371   T3 PASV             T1 INTA
```

**The chip leaves the bus idle for two clocks and then announces the
acknowledge.  Neither engine has those two clocks.**  The ucore's prefetcher
takes the slot (so it runs an extra CODE cycle and its acknowledge is 2 clocks
late); the model announces on the fetch's own T4 (2 clocks early).  *Both
engines are wrong, in opposite directions, by the same two clocks, on the same
437 seeds.*

**The mechanism, stated once and naming no opcode**: an interrupt recognised at
an INSTRUCTION BOUNDARY costs two clocks before its acknowledge can be
announced, and the prefetcher does not get the bus in them.  A wake from HALT
does not pay it — which is why the first acknowledge is right in 443/445 and
why all four `v0.1-w*evt` golden cells (200 / 1,200 / 200 / 1,200, single
instruction, first entry) see nothing of this.

**The obvious alternative reading, and why it does not survive.**  *"The model's
−2 is an artefact of the replay coordinate, not of its entry law."*  It is not:
`timed_fuzz.evt_directive` hands the model the acknowledge's **ordered bus
position** and the CS:IP of the chip's own pushed frame — i.e. it is told WHICH
boundary and in what ORDER, and it computes the acknowledge's **clock** itself.
That is exactly why these seeds land in `SCHEDULE` (same cycles, same order,
different clock) and not in a sequence family.  The −2 is the model's own entry
timing measured against a boundary it was handed correctly.  The ucore's half
needs no such argument: it is handed only the rig's pin directive and predicts
everything.

**Why the census believes it is one thing and not two.**  445/445 on the
6-clock gap, 445/445 on `delta = -2`, 445/445 on `pin = 0`, across every wait
class (fix0 342 · wrand1 54 · wrand2 28 · wrand3 16 · wrand7 5) and both
campaigns.  No sub-population, no catch-all, no exceptions.

**Relation to what is already booked.**  This is the missing whole-program half
of **I3** (`gaps` §I.3): INTA under waits is closed as a law for the
*single-instruction* population (M18, `INTA2's T1 = INTA1's completion eval + 5`,
2,339/2,339), and INTA2's spacing is right in both engines here (+7 in all
three columns above).  What is open is the **sequence's own start anchor on a
re-entry**, and I3 records that its evidence column *"was the EVT population,
which INV-1 has just suspended"*.  The column is un-suspended and this is what
it says.

**LANDED IN `sim/` ON 2026-08-04, SM3 SITTING 2 — AND THE READING ABOVE IS NOT
THE ONE THAT LANDED.**  The directed board cell (`sw/sm3_h1_cell.py`, socket,
FLASH #4) REFUTED both "it is the redirect" and "it is the IRET": the FIRST
acknowledge of a record pays no floor after a near JMP, a far JMP, a CALL/RET
pair or a bare IRET chain, while EVERY acknowledge from the second on pays it in
all five stimuli, *including a pure NOP sled*.  The law that landed is
`INTA1 T1 = max(F1 + 6, F1 + L + 1)` ARMED BY THE PREVIOUS ACKNOWLEDGE —
`ucore_provenance.md` §61, `sm3_h1_prereg_2026-08-04.md`.  Sim EVT
**363 -> 780**, COMBINED **1,635 -> 2,052**, nothing else moved; the ucore leg
is NOT taken.  Original disposition, for the record:
**NOT TAKEN THIS SESSION** — it moves the
interrupt-entry anchor, which is spine, and it needs its own pre-registered
before/after on the four `evt` golden cells, `timed_lawcards`, the b2 tranche
and both engines' REGISTERED columns.  Registering it is the next session's
first job.

*Falsifier*: a seed in the 445 whose chip acknowledge opens at a gap other than
6 clocks after the preceding fetch's T1, **or** a re-entry acknowledge in which
the chip DOES grant the prefetch slot.

*The one directed measurement that would sharpen it, and it needs the board*:
§26.6.4's cell — an acknowledge announced while another cycle still owns the
bus, at more than one wait level — now has a 445-seed shadow to be checked
against.  **Not taken; no board contact this session.**

### §5.2 H2 — the queue-status pair around an acknowledge.  41 ucore + 57 sim seeds.

With H1's 445 removed, the ucore's EVT residue is **95 seeds**, and its
first-divergence signatures collapse to a short list dominated by the queue
status: `qs -!=F` 25 · `qs E!=-` 16 (41 together), then `bs MEMR!=PASV nxta` 14
and `bs INTA!=PASV` 6.  The model's remaining 154 have the same head:
`qs -!=F` 42 · `qs E!=-` 15 · `qs -!=E` 12.

The `F`/`E` pair is the queue's FIRST-BYTE and EMPTY strobes, so this is *when
the queue was cleared and re-primed around the entry*, not a bus-arbitration
question.  **Almost certainly downstream of H1** — a handler entered two clocks
early or late clears the queue two clocks early or late — so it is ranked below
it and should be **re-censused after H1 lands rather than attacked first.**

*Falsifier*: H1 lands and this family does not shrink.

### §5.3 H3 — `PF_LOST`'s arbitration priority.  107 ucore / 239 sim REGISTERED seeds.

Unchanged and inherited: `ucsim_t_provenance.md` §26.10 D item 4, `gaps` §I.5.
It is the largest single family on the registered bank in both engines and the
ucore already closed 129 of the model's 239, which is where most of its +211
comes from.  **MEASURED, explicitly NOT fitted**, and C11's `owns_slot` is its
pin-side shadow (`gaps` §I.4).  No new information this session; listed so the
ranking is complete and so H1 is not mistaken for the biggest thing overall.

### §5.4 H4 — `DATA_SEQ`, and the 13 seeds the model-replayed table could not see.

41 in the ucore's own engine against 28 in the model's, on the registered bank —
§58.4's finding, reproduced here.  §T.3 read `DATA_SEQ` as one of three families
*"the ucore closed NOTHING in"*; in its own engine the family is **13 seeds
LARGER**, so the ucore has `DATA_SEQ` divergences of its own on seeds the model
misses for a different reason.  That is F47's shape — *the right cycle, the
right address, the wrong word* — and it is where 4 of the 9 ucore-only
REGISTERED seeds sit (`gaps` §T.2, §49.8's three sub-mechanisms).

**The cheapest open measurement in the whole census is here and it is
board-free**: §49.8 item 2's `10`/ADC carry-in on `mc1/721` (`ndiff = 2`) —
`SSA_E_PSW` is already in the save-state map, so `+ss_at=<clk>` reads the PSW
out at the `9E` SAHF / `F5` CMC boundary on the frozen binary, no RTL change,
against `PSW=` in `v30sim image --trace`.  **Written down and still un-run.**

### §5.5 H5 — the 13 ucore-only HLT sweep cells.

Cited from `gaps` §T.1, not re-run this session (the sweeps need their own
driver and the census budget went to the EVT column).  Two mechanisms, no third:
the `busstat`-first half is **F43** — *the HALT-display decision must test the
wake condition visible on its own decision edge* — **diagnosed and deliberately
not landed twice**, because it touches the BIU's eval instant; the `seg`/`bus`-first
half is **NOT diagnosed**.  Offline 259/283 against the model's 272/283.

Note the family resemblance to H1: both are *"the decision that opens a cycle is
taken on the wrong edge relative to an external level"*.  Whether they are one
mechanism is **not established** and is not asserted here.

### §5.6 H6 — the 116 fabric INTA cells.

Cited.  **Attribution NOT ESTABLISHED** (Codex C11) and the fabric leg of the
§56.3a intervention is **BLOCKED, not refuted** — Quartus 17.1 folds
`core_ad === 1'bz` to a constant and deletes the hold register, so the "after"
bitstream is the "before" one (§59.7.1).  The Verilated leg met both bars
(§58.6).  Listed for completeness; it is a harness question and no offline work
moves it.

---

## §6 THE SHARP NEGATIVE RESULTS

### §6.1 T8's byte-swap attribution is **REFUTED**

§T.8 and §49.7 record four banked seeds on which the ucore and the model agree
with each other and disagree with the socket, and attribute three of them to
*"M5b's A0 swapper applied where the chip does not"*.  **Measured row by row
this session (`sw/sm3_bswap.py`), that attribution does not survive.**

| seed | the divergent write | chip drives | both engines | A0 | UBE\_n | the model's rotation |
|---|---|---|---|---|---|---|
| `mc1/raw_2340_8df9460dd643` | MEMW `03efd`, single cycle | `35ab` | `ab35` | **1** | 0 | applied |
| `mc2/raw_3868_3995afd408b7` | MEMW `03ef8`, single cycle | `b6cd` | `cdb6` | **0** | 1 | **not applied** |
| `t30-raw/raw_453_99bdf08b95ea` | MEMW `0b97d`, single cycle | `ad00` | `00ad` | **1** | 0 | applied |
| `t30-raw/raw_624_d20cc1a550cc` | MEMW `9998e` | `f206` | `fa87` | 0 | 0 | n/a — not a swap |

**Read the sign column.**  On `raw_2340` and `raw_453` the model rotates at an
odd address and the chip does not.  On `raw_3868` the model does **not** rotate
(the address is even) and **the chip does** — the byte the chip puts on AD7-0 is
OPR's HIGH byte.  The three do not have one sign, so **no removal, narrowing or
inversion of the A0 rotator closes them**, and M5b's own measurement (four
quadrants, `88` / `C6.0` / `50`, validated 366/366 over the `88` byte-store
rows) forbids removing it outright.

**What the rows do establish**, and it is a better-posed question: on all three
the chip's driven word equals the rotator applied to **`swap8(OPR_model)`** —
i.e. *the two engines' OPR holds the same two bytes as the chip's, in the other
order.*  The defect is on the side that **loads** the datapath, not on the side
that drives the bus.

`raw_2340` names the instruction: `FE F6` — the FE group's undocumented `/6`
with mod = 11, `op8 = 1`, entering at micro-address `0FD8` / ROM row **`01CE`**
(`M -> OPR   SIGMA -> IND   E   CTL   MEMW SS`).  Its OPR is `35AB` where the
chip's is `AB35`, and the write is a **single-cycle byte write at an odd stack
address**.  The seed's own control is two bus cycles later: the **ordinary**
`51` PUSH CX (row `0029`, which fills OPR on the row *after* the write) at odd
`03efb` splits correctly and **both engines agree with the chip**.

**Disposition: reported as a refutation, NOTHING CHANGED.**  The population is
3 seeds and the mechanism is not named.  §T.8's sentence should be read as the
*observation* it is and not as an attribution.

*Falsifier for the refutation*: a re-derivation in which `raw_3868`'s divergent
write is the second cycle of a split word write from an odd base (which would
make the model's rotation "applied" and restore the single sign).  It is not:
the model emits it as one cycle and there is no cycle at `03ef7` or `03ef9`.

### §6.2 The novelty-ledger control, and what it proves

SM2 left `check_fuzz_bank --strict` failing on `new-sig TIMING 166` and routed
the admission as a decision.  **Independently re-derived here** over all 3,242
banked seeds with the same `replay_classify` the gate uses
(`sw/sm3_sigctl.py`), on a **freshly rebuilt** FSM TB (SM2's binary predated
`tb_v30_core.sv` by two commits — see §7):

```
new-sig TIMING seeds: 166   distinct signatures: 140
  on RE-CAPTURED seeds (evt.hold == 300 AND evt.hold_bits == 12) : 166
  on any OTHER banked seed                                       :   0
errors 0   gen-drift 0   stable 3242   improved 0   worse 0
```

**Zero from any seed SM2 did not touch.**  The 140 were admitted with a
per-signature provenance record and a top-level `admissions` entry
(`sw/sm3_sig_admit.py`), with pre-existing entries proved byte-identical
(`sigs` 11,705 → 11,845, 0 removed, `sigv` and `legacy_baseline` untouched).
The gate was then re-run in full, unmodified:

```
check_fuzz_bank: PASS | 3242 banked seeds | stable 3242 improved 0 worse 0
                      | gen_drift 0 regen_err 0 | float-floor 0
                      | new-sig TIMING 0            <- rc = 0 under --strict
```

---

## §7 THINGS THIS CENSUS FOUND THAT NOBODY WAS LOOKING FOR

1. **The FSM TB binary was STALE, and no gate could see it.**
   `hdl/tb/obj_dir/Vtb_v30_core` was built at 05:43 from a `tb_v30_core.sv` that
   commit `5c5fdbf50a` changed at 07:28.  `check_fuzz_bank` binds to that binary
   through `check_seq.BIN` and **`check_seq` never calls `check_core.build()`**,
   so nothing in the archived-gate path rebuilds it — only tools that go through
   `check_core.build()` (which *does* carry `tb_v30_core.sv` in its dependency
   list) would have caught it.  It is the vacuous-gate pattern in its fifth
   incarnation: *a gate that enumerates the KNOWN and asserts consistency, but
   has no census of the UNKNOWN*.
   **Rebuilt, and the control re-run on the new binary reproduces SM2's 166 / 140
   exactly** — so nothing was scored wrong, and that is a measurement and not an
   assumption.
   *Suggested standing fix (not taken here)*: have `check_seq` call
   `check_core.build(core="fsm")`, or have `check_fuzz_bank` assert the binary
   is newer than its RTL+TB dependency set.

2. **The EVT column's shape is nothing like the registered bank's.**  `PF_GAINED`
   11 % → 86 %, `PF_LOST` 49 % → 4 %.  Anyone carrying intuitions from the
   ucsim-t seven-family work into the whole-program event axis will be wrong
   about which family matters.

3. **The ucore is architecturally correct on 413 of its 540 EVT seeds and wrong
   on 2.**  The whole-program event residue is a timing residue.

---

## §8 WHAT THIS CENSUS DELIBERATELY DID NOT DO

* **No board contact.**  Two directed cells are named and left un-taken: I3's
  §26.6.4 acknowledge-under-waits cell (§5.1) and nothing else.
* **H1 was not fixed.**  It is the largest mechanism in the residue and it moves
  the interrupt-entry anchor; taking it inside the session that discovered it,
  without a pre-registered before/after, is the failure mode this project has a
  rule about.
* **The HLT sweeps were not re-run** (§5.5 is cited).
* **§49.7's byte-swap seeds were not patched** (§6.1).
* **`s15_census` was not modified.**  Its taxonomy is the inherited one and the
  EVT column is the first population it has been pointed at that it was not
  designed around; that it lands 540 seeds in seven families with an EMPTY
  catch-all is itself evidence the taxonomy generalises.
