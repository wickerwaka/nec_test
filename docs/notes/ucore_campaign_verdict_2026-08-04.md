# ucore campaign verdict — 2026-08-04

**The campaign question:** *can the V30 core be regenerated from the mechanism
ledger?*  Not "can an RTL core be made to pass the suites" — the repo already
had one of those — but: **is the ledger a SPEC?**  Is what the ucsim and
ucsim-t campaigns wrote down enough, by itself, to build the hardware from?

Ledger: `docs/notes/ucore_provenance.md` (§0-§56).
Plan as executed: `~/.claude/plans/zippy-swinging-meerkat.md`.
Branch `ucsim`.  Companion verdicts:
`docs/notes/ucsim_campaign_verdict_2026-08-01.md` (architecture),
`docs/notes/ucsim_t_campaign_verdict_2026-08-02.md` (timing).

---

## (a) THE VERDICT

**YES — and the regenerated core is better than the one it was written to
replace, on the axis this project ranks first.**

The answer is not an opinion about the ledger; it is six numbers, every one of
them reproduced by a re-run immediately before this document was committed.

*Reproduction is not passage.*  **One registered bar was MISSED in this
campaign's final stage and it is the largest miss on the record: §55.2 bar 2,
the fabric HLT sweeps, registered at ≥ 249/283 with 259 ± 4 expected, measured
at 143/283** (§56.1).  It is reported as missed in §(b), §(d) open item 0 and
the gate ledger, and its attribution is explicitly NOT ESTABLISHED.

The **FSM core's** 168,400/169,000 and 16/283 are a different kind of thing and
are not counted among the misses: they are §53.4 **bar 3**, a
pre-registered ROUTED FINDING — the bar said in advance that the frozen core
would not be fixed and that its numbers would go to the campaign owner with the
disposition decision.  Conflating the two would flatter this document in one
direction and slander the FSM core in the other.

| the question | the number |
|---|---|
| **Is it right on the deterministic surface?** | **G3 = 169,000 / 169,000.**  `check_core --core ucore --opcodes all --cases 0`, every form, every case, cycle-exact AND architecturally exact against the silicon goldens.  At w0 the reference model carries no registered residue, so this figure is the same with or without it subtracted (§29.2's two-number rule). |
| **Is it right off it?** | **Eleven of thirteen ladder suites land ON the model's own ledger number** — `w1`/`w3` 1,200 each, `EB` 200, the four `evt` cells 200/1,200/200/1,200, `w1evt-biased` 1,200, boot 220 **and** 400, `ulockstep --golden all --cases 50` **17,350/17,350**, wvec **88/88 at +0.0 %**, ENTER **154/154 ×5**, INS **1,312/1,312** and **2,624/2,624**.  The two that do not are the HLT delay sweeps (**259/283** against the model's 272) — itemised in §(d), not excused. |
| **Does it fit, and does it close?** | **G6 GREEN: 27 % ALMs (11,117 / 41,910), Fmax 48.03 MHz against a registered ≥ 32 MHz, worst setup +9.121 ns and TNS 0.000 on EVERY clock domain**, 0 errors, 0 inferred latches, 0 `lpm_divide` — the FINAL (U5) build, §55.1; the U4 pass-3 build it supersedes was 26 % / 45.56 MHz / +8.922 ns.  Two structural passes got it there and the sim ladder was re-scored three times across them **with zero deltas**. |
| **Does it run?** | **First light 800/800 on all three legs** — chip-vs-golden, core-vs-chip, core-vs-golden — after a `use_core=0` chip-path proof of MATCH over 800 rows.  **Three flashes, all from HEAD**, all through `safe_flash.sh` with its VERIFY leg; first light re-proved 800/800 ×3 on the U5 bitstream in its own session. |
| **Does it meet the campaign's victory condition?** | **THE PRIORITY TRANCHE IN FABRIC: 176 / 178 (98.9 %), with V0 through V5 ALL MET** — including V3 at ZERO seeds apart.  200 fresh stratified `wrand` programs, frozen and committed before the first capture, chip-vs-fabric, 0 hard failures in 483 captures with the divider PINNED on every one. |
| **Is the model of the bitstream the bitstream?** | **On the priority tranche, yes: fabric ↔ Verilator pairwise identity 200/200**, for the ucore *and* for the FSM core.  §48.4 registered a fabric-vs-sim gap as *"the MORE important result if it happens"*; on that population it did not happen.  **On the HLT delay sweeps it DID** — 143/283 in fabric against 259/283 under the TB on the same RTL — and §55.2's bar 2 named that consequence in advance.  It is one class, 116 of 116 (the INTA float), it is **NOT ESTABLISHED as the harness's** on the evidence gathered, and it is §(d) open item 0. |

### What that means, stated once

The ucore was written **from a document**, not from traces.  Every mechanism in
it has a name, an evidence line and a falsifier in a ledger that predates the
RTL.  It reached cycle-exactness on 169,000 golden cases, on four wait axes and
four event axes, on whole-program silicon replays, and then in an FPGA against
the socketed part — and on the axis the project ranks first it is **176/178
where the hand-built core it was written to replace is 59/178 from the same
HEAD**.

The honest converse, equally on the record: **the ledger was not sufficient
without measurement.**  Fifty-one findings were needed to get from the document
to the hardware, and a third of them are places where the document was right and
the *transliteration* was wrong in a way only a comparator could see.  The claim
proved is "the ledger is a spec you can build from and grade against", not "the
ledger is a spec you can build from without grading".

### What the answer is NOT

* **Not "the ucore is cycle-exact over whole programs."**  It is 1,483/1,702 on
  the registered fuzz bank and 171/188 on the b2 tranche.  Both beat the
  reference model (1,272 and 154); neither is 100 %.
* **Not "the model is obsolete."**  The model is the spec, and it remains the
  gate for every RTL-vs-sim question.  Where the ucore beats it, that is a
  *silicon* comparison, and the events are routed to the model's ledger — `sim/`
  was not changed by this campaign at any point except to add one read-only
  table dump and one read-only BIU script driver.
* **Not "the FSM core is wrong."**  It is 169,000/169,000 on v0.1 as it always
  was, on the comparator it was always graded with.  What this campaign found is
  that on the wait axis, in fabric, against fresh programs, it is 59/178 — and
  that two separate defects in it were invisible to every standing gate.

---

## (b) THE FINDINGS LEDGER — F1-F51, IN SUMMARY

**Fifty-one numbered findings (F1-F51, plus F11's sub-items F11a/F11b), TWELVE
Codex review findings across FIVE reviews — C1-C3 (§26), **D1** (§32, which is
labelled D1 in the ledger and is easy to lose out of a C-numbered count),
C4-C5 (§36), C6-C8 (§45.1) and C9-C11 (§(g), the review of this document) —
and the retractions.**  Every one carries evidence and a falsifier in
`ucore_provenance.md`.

Grouped below by what KIND of thing each was, because that is the transferable
part.  **The partition is EXHAUSTIVE over F1-F51 and the four groups are
disjoint: 32 + 3 + 8 + 8 = 51.**  (An earlier draft of this section grouped
loosely, double-counted `F51` and `F41`, omitted `F9` entirely, and printed
counts that summed to 46 — caught by C9.)

### A. The document was right and the RENDERING was wrong — 32

The largest class, and the campaign's central lesson.
`F4` (`e_from` is a term of the flush clock, not a flop) · `F8` (the post-`E`
row cannot own a state) · `F11` + `F11a`/`F11b` (**the demand and the take are
one event** — the single most-repeated error, six instances) · `F12` (a split is
one access; a read hands over once) · `F13` (the iterative stepper's terminator
read one clock early — sixteen forms hung) · `F14` `F15` `F16` `F17` `F18` (a
row's acts are computed from the row's own transfers) · `F19` `F20` · `F21`
`F22` `F23` (the post-`E` row runs on the machine it belongs to; the debt is
eighteen bits) · `F24` (a row that flushes cannot pop) · `F25` (power-on reset
is a MICROCODE MARCH, not a state) · `F26` `F27` `F28` · `F29` (M5b's
`odd_base`) · `F30` (the BCD adjust unit was computed and discarded) · `F31`
(**OPR ownership is one counter and it is the BIU's** — +4,436 cases, the
largest single move) · `F32` (the restoring divider's compare is one bit wider
than its operands) · `F33` · `F35` (three first verifications of code that had
never fired) · `F36` `F37` `F38` · `F41` (M21 was rendered for the status and
not for the pads) · `F47` (`begin_sequence()`'s `opr_fresh` line was never
transcribed at the instruction boundary — +89 fuzz seeds) · `F51` (**the HALT
pseudo-cycle has no data phase** — U5).

### B. The document did not say it, and SILICON did — 3

Where the SIM has no rendering to diverge from, so the gate is the golden and
`ulockstep` is informative only — governance §42.1, and the exception was never
abused (`ulockstep --golden all` is 17,350/17,350 on the same tree).
`F34` (**recognition is causal and the boundary is a WINDOW**, not a clock — the
last unimplemented-by-design block, +2,232 cases at w0 and +1,654 across the
`evt` cells, which were 0 to a case) · `F39` (the flag register is fed by the
data latch, not by the row — and it hits **exactly two ROM rows**, `007A` and
`01EA`, which is the same pair E1 measured on silicon) · `F40` (the REP abort
has **two anchors**, which is why the tap-depth scan had no fit).

### C. The INSTRUMENT was the defect — 8

`F2` (`check_boot`'s RTL leg was stale vs the TB — found by the ROADMAP's own
"rebuild from a clean tree before citing" rule) · `F7` and `F10` (a gate that
names an internal signal is only as current as that signal's meaning) · `F9`
(`dbg_regs`' IP slot is the LIVE `pc`, not a retire snapshot — the TB read a
stale value in 500/500 `B8` cases) · `F42` → **REFUTED**, see below · `F44` (the
microcode ROM fails to load **silently**, and the run looks normal — a vacuity
risk, closed with four probes and a `$fatal`, proved armed by three negative
controls) · `F45` (`--ss-mode 4`'s seed **is** the bit index, so a small-seed
sweep reads as a blind gate) · `F46` (the rig's `evt_hold` register is 8 bits,
and 760 EVT seeds were banked asking for 300).

### D. Structural design inputs, proofs, and platform — 8

`F1` (the micro-PC is 15 bits, so the flattening is TWO tables) · `F3` (the boot
capture is not a BIU-only stream, so the U1 boot gate was VACUOUS and was routed
whole to U2) · `F5` and `F6` (**the eval instant needs no wait knowledge**, and
one number initialises all three landing windows — the RTL is SHORTER than the
model here) · `F43` (M20's cancellation is one edge late — diagnosed,
**not landed**, twice) · `F48` (the two EU bound assertions fire on six banked
seeds; the bound PROVED over every graded corpus, its own falsifier MET on
runaway stimulus, the capacity deliberately NOT deepened, and the harness's
self-shrinking denominator fixed) · `F49` (five architectural flops absent from
the save-state map, found by the census that runs RTL→map, which is the only
instrument that could) · `F50` (three hygiene items).

### THE RETRACTIONS AND SELF-CORRECTIONS — the complete set

1. **F42 is REFUTED, by its own pre-registered falsifier.**  §45.4 registered:
   *"if the 17 uncountable HLT cells really are the TESTBENCH's composed-AD mask
   and not the core, then in fabric those cells must PASS…  If any of the 17
   fails in fabric, F42 is REFUTED and the ucore owns those cells — that is the
   honest outcome and it is to be reported as a refutation, not re-explained."*
   In fabric the sweeps scored **29/283**; the socket control on the identical
   driver reproduced the golden **49/49**.  Reported as a refutation (§52.9) and
   then **fixed** (F51, §53-§56): in fabric on the fixed bitstream the sweeps are
   **143/283** and **ZERO cells still carry the signature**.  The mask was
   hiding a real divergence rather than manufacturing one — the opposite of what
   F42 claimed.
1b. **U5's OWN bar 2 was MISSED, and is reported as missed (§56).**  The fabric
   total was registered at ≥ 249/283 and came in at **143/283**.  The miss is one
   class, measured rather than argued: **116 of 116** fabric-only failures are
   INTA rows, there is no counter-population, no cell fails offline and passes in
   fabric, and `HLT.RES` in fabric is identical to `HLT.RES` offline cell for
   cell.  It is the plan's registered **risk #4** (multiplexed-pad float) — the
   chip's pads retain the previous data phase at an INTA's T1 and the core's AD
   inside `system_large` is an internal tri-state Quartus resolves to a mux, so
   there is nothing to retain.  **That attribution is recorded as NOT ESTABLISHED**
   (C11) with the settling intervention pre-registered and unrun — it is F42's
   argument one population over, and F42 was population-complete at 24/24 and
   still wrong.  Neither candidate fix was taken, and the reason the *scorer* was
   not swapped is stated in the ledger: **that would be choosing a comparator
   after seeing the result.**
2. **"The ucore beats the model on six HLT cells" — RETRACTED (§43.2).**  A
   numbering artefact: the model's failures were compared by ARRAY POSITION and
   the ucore's by the `idx` FIELD, and **the `idx` field is the pin delay `d`**.
   `HLT.RES`'s sweeps start at `d=0` so the two coincide; `HLT.INT`'s start at
   `d=1/3/4/5` so they do not.  There were no such cells.  The artefact is kept
   in §43.0 rather than deleted, and the rule it produced — *any per-case claim
   must state which numbering it is in* — is a standing one.
3. **§50's cause was REFUTED BY MEASUREMENT (§51.1).**  Quartus's
   `Info (276007) … uninferred due to asynchronous read logic` was read as the
   cause of a 32,534-cell EU and routed U5-scale work (a registered microcode
   ROM = a cadence change = a re-derivation of the campaign).  Measured four
   ways: the two microcode tables are **3 %** of the EU and the unrolled chain
   loop is **82 %**.  The EU went 32,534 → 12,400 cells with the ROM read left
   exactly as it was.  *An `Info (276007)` says only "this array did not become a
   block RAM"; it says nothing about what the array costs as logic.*
4. **F23's "nine bits" was WRONG (Codex D1).**  The post-`E` row's opcode shadow
   is TEN bits, not nine; `op8` is overwritten by the successor's `S_DECODE2`
   exactly as `opc_reg` is.  No v0.1 case reaches the divergent path, so the
   census did not move.  **A finding whose fix moves no number is still a
   finding** — the shape recurs at F22, C4 and §42.2.
5. **§35.4's reading was HALF WRONG, and said so.**  It booked *"what is wrong is
   the CONDITION, not the `stop`"*.  F38: the condition is right and the `stop`
   is right; three separate F11s were wrong.  The falsifying experiment that
   produced the mis-reading (5 forms improve, 8 regress) is in the ledger with
   its numbers.
6. **The REP tap-depth scan was a NEGATIVE result that was negative FOR A
   REASON.**  §40 recorded `int_p[0]` 174, `[1]` 178, `[2]` 179, `[3]` 175 and
   **declined to fit one** — four cases left on the table rather than fitted.
   §42/F40 then showed why no single depth fits: the two boundaries are anchored
   to different edges, and both taps are `edge − 4`.  Declining to fit was what
   made the mechanism findable.
7. **§43.0: the standing HLT ratchet in `CLAUDE.md` was STALE** — 91/97, **92/95**,
   **42/46**, **40/45** were pre-§26.7.6 figures; the model is 91/97, **95/95**,
   **44/46**, **42/45**.  The gap was 31 cells, not 24.  Corrected UPWARD, with
   the staleness recorded in place rather than silently overwritten.
8. **§49.6: the registered band was OVERSHOT and that is recorded as a
   DEVIATION, not as a win.**  F47 moved REGISTERED by +89 against a band whose
   top was +70.  The falsifier ("fewer than 40 and the attribution is wrong") was
   not met by a wide margin, so the attribution stands — but all three sub-counts
   under-predicted, which is an open estimate error and is named as one.
9. **§51.8a: V1's own pre-registration was DEFECTIVE.**  It was set at 85 %
   *"below the banked tranche's 89.4 % because fresh seeds are not cherry-picked"*.
   Measured, the direction is the opposite: a fresh population is EASIER than an
   adversarially-selected bank.  Recorded as a defect in the pre-registration,
   not corrected after the fact; the successor registration is §(e) item 3.
10. **§49.4's cheap PROXY predicate never reached 0** on its control (registered
    at 0, came in at 29, then 3).  The claim rests on the patched-model
    experiment, not on the proxy, and the proxy's failure is recorded beside it.

---

## (c) THE COMPARISON THE PROJECT EXISTS FOR

Two cores, one repo, one HEAD, one harness, one comparator stack.  This is the
only controlled A/B of a mechanism-derived core against a trace-fitted one that
this project will ever get, and it is why the campaign was worth running.

| | **ucore** (mechanism-derived) | **FSM core** (trace-fitted) |
|---|---|---|
| **Fresh random-wait tranche, IN FABRIC** (§48.4, 178 scored) | **176 / 178 — 98.9 %** | **59 / 178 — 33.1 %** |
| the same, under Verilator | 176 / 178 | 59 / 178 |
| fabric ↔ Verilator pairwise | **200 / 200 identical** | **200 / 200 identical** |
| **wvec silicon freeze** (`timed_wvec_gate`) | **88 / 88, +0.0 %** | **71 / 88** |
| **registered fuzz bank** (`timed_fuzz`, 1,702 seeds) | **1,483 / 1,702 (87.1 %)** | **18 / 1,702 (1.1 %)** |
| b2 victory tranche | **171 / 188 (91.0 %)** | — (the model is 154) |
| v0.1 golden suite, **corrected comparator** (§54) | **169,000 / 169,000** | 168,400 / 169,000 |
| four HLT delay sweeps, corrected comparator | **259 / 283** | **16 / 283** |
| RTL, code lines (blank/comment stripped, generated tables excluded) | **4,785** | 5,919 |
| RTL, total lines including the ledger commentary | 7,911 | 8,970 |
| ALMs | 11,117 / 41,910 = **27 %** (U5 build; 11,078 / 26 % at U4 pass 3) | 25 % |
| Fmax | **48.03 MHz** (U5 build; 45.56 at U4 pass 3) | (its own build: setup +4.296 ns, TNS 0) |
| `lpm_divide` instances | **0** | 2 |
| save-state map | 218 addresses, 201 flops, 0 UNMAPPED | 203 addresses, 181 flops, 0 UNMAPPED |
| per-opcode timing exceptions | **0** ("grep for one" stays true) | the class-5 unified law, `race_law.svh`, the IRET arm |

**The wvec line is the one to read first.**  The FSM's 71/88 is 22/22 at
`ws0:wmax0` and 17 misses spread over the three WAITED configs, with the access
COUNT matching the chip in all 88 cells.  Its deficit is pure CADENCE on the wait
axis — which is the axis this project ranks first, and the axis a trace-fitted
core cannot generalise on because there is no trace to fit for an arbitrary wait
sequence.  The ucore has no wait-keyed term anywhere: `ready_prev` is the only
wait mechanism, and the eval instant is `dage >= 3 && ready_prev` (F5).

### THE FSM REGRESSION FINDING — booked, with its falsifier

**The frozen reference core has REGRESSED BY 104 SEEDS on the random-wait axis
and no standing gate sees it.**  Measured, §52.8: the 2026-07-30 FSM bitstream
scores **163/178** on this tranche; HEAD's FSM RTL scores **59/178** — in fabric
and in Verilator, identically, so it is not a bitstream artefact.  Scored
pairwise, the stale bitstream against HEAD's Verilator model is 76/200 while both
same-HEAD pairs are 200/200: **the gap was entirely the stale bitstream**, which
is what §51.8b's 62/178 had been.

Why no gate sees it: the ladder runs `check_core --core fsm` on **four opcodes**,
and the FSM's registered fuzz figure (18/1,702) is so low that a further loss is
invisible there.

*Falsifier*: a bisect between the 2026-07-30 build and HEAD that does not move
this number.  Not diagnosed here, and nothing was changed to chase it.

### THE SECOND FSM FINDING — U5's, and it is the same defect the ucore had

The HALT pseudo-cycle's upper nibble.  `v30_biu.sv:1914` drives
`{4'h0, fetch_phys[15:0] - 16'd2}` and `ad_oe_ps` explicitly excludes
`cur_kind != K_HALT`, so the FSM core drives **nothing** on A19-16 across a HALT
display and its T1 — where the goldens carry `data_ps(2)` = `{md, ie, CS}`, `6`
in all 200 `HLT.INT`, `2` in all 200 `HLT.RES`.  The testbench's composed-AD mask
substituted the retained nibble there, and the retained nibble is the previous
cycle's PS on a CS fetch with the same IE, so it read correct **by construction
and not by correctness**.  In fabric there is no retention and it does not.

The mask is removed (§53.3, engine-neutral — it names no core signal), the ucore
is fixed (F51), and **the FSM core is not**: this campaign does not touch the
frozen core's RTL, because the flashed FSM A/B bitstream is built from HEAD and
§52.8 established that it must stay that way.  Its numbers on the corrected
instrument are in the table above.  **The defect predates the instrument change
by every commit in the repo**; nothing was made worse, something was made
visible.

---

## (d) OPEN ITEMS — COMPLETE

Nothing below is hidden in a subsection.  Where an item has a mechanism it is
named; where it does not, that is said.

### 0. The INTA float in fabric — 116 cells, and it is the HARNESS, not the core

The one bar U5 registered and missed (§56).  On the fixed bitstream the four HLT
sweeps score **143/283 in fabric** against **259/283** offline, and the whole
116-cell gap is a single class with no exceptions: at an INTA's T1 the chip's AD
pads float and RETAIN the previous data phase, and the core's AD inside
`system_large` is an internal `tri` net that Quartus resolves to a mux — there
is nothing to retain.  The plan registered this as **risk #4** before any RTL
existed (*"multiplexed-pad float → G7-only divergences → ledger open item 1, not
patches"*), and `sw/check_ab_hw.py` already excludes float-retention rows for
exactly this reason, which is why first light is 800/800 on the same bitstream in
the same session.

Two candidate fixes, **neither taken**: give the harness's `core_ad` a retention
model in `system_large.sv` (changes the shared A/B harness and therefore BOTH
cores' fabric numbers — needs its own pre-registered before/after), or teach the
fabric scorer `check_ab_hw`'s exclusion (**would be choosing a comparator after
seeing the result**).  *Falsifier*: a fabric cell whose first divergence is an
INTA row whose golden value is NOT the retained previous data phase, or any
non-INTA fabric-only failure.

### 1. The HLT delay sweeps — 24 cells, 13 of them the ucore's alone

On the corrected comparator: the model 272/283, the **ucore 259/283**, the FSM
core 16/283.  Read case by case in ONE numbering (the `idx` field = the pin delay
`d`), the model's 11 failures remain **a strict subset** of the ucore's 24, and
**at w0 the two failing sets are IDENTICAL** (`HLT.INT` d ∈ {2,3,4,5},
`HLT.RES` d ∈ {2,3}).  The 13 ucore-only cells are all at w1/w2/w3:

| sweep | ucore-only failing `idx` |
|---|---|
| `s10-w1` | `HLT.INT` 7,8,9,10 · `HLT.RES` 7 |
| `s13-w2` | `HLT.INT` 9,12,13 · `HLT.RES` 9 |
| `s13-w3` | `HLT.INT` 11,15,16 · `HLT.RES` 11 |

The `busstat`-first half is **F43**, diagnosed and deliberately not landed: *the
HALT-display decision must test the wake condition visible on its own decision
edge* (M20's threshold-1, "the HALT displays unless the wake is already visible
to the microcode on or before the display clock").  It touches the BIU's eval
instant — the spine of the whole module — and §43 declined to land it while the
ladder was being scored; U5 declines for the same reason, at a closure.  The
`seg`/`bus`-first half is **residue the corrected instrument newly exposes and is
NOT diagnosed.**  *Falsifier for the pair*: a cell in the band whose first
divergence is neither the HALT display's own decision edge nor a woken display
inside the pseudo-cycle.

### 2. The two `bs` seeds of the priority tranche — CLASSIFIED, and NOT the ucore's

§52.10 item 5.  Both are in V5's closed taxonomy (`bs`), and the classification
against the sim is decisive:

| seed | first divergence | ucore | SIM | **ucore vs SIM, pairwise** |
|---|---|---|---|---|
| `mc1_300043` (wmax 2) | row **403** | ndiff 3,419/4,000 | row **403**, ndiff **3,419/4,000** | **0 / 4,000 rows differ** |
| `mc1_300122` (wmax 7) | row **402** | ndiff 3,570/4,000 | row **402**, ndiff **3,570/4,000** | **0 / 4,000 rows differ** |

At the divergent row the two engines are byte-identical — same address, same
data, same status nibble (`0xD6285/0x6205/ps=D` and `0x850973…/0xFC1D/ps=C`) —
and both issue an EU `MEMR` where the chip issues a `CODE` fetch.  **The entire
residue of the campaign's victory tranche is a divergence the reference model
SHARES, bit for bit.**  Per §0 governance rule 3 that is a ledger finding routed
to `sim/`, never a ucore patch: patching the RTL to beat the model here would
knowingly create an RTL-vs-model divergence in the direction the governance
forbids.  It is the same `bs` family the model's own registered bank residue
falls into (§44.2: `qs` 145, `bs` 37, `data` 23).

### 3. The ucore's own remaining residue, named

* **219 registered fuzz seeds** (1,483/1,702).  §49.8's residual ten are named:
  6 = `8F`'s write-back driving a stale OPR when the pop lands at or after T1
  (the model gets it free because `rdq_` is filled at ISSUE time); 3 = `10`/ADC's
  carry-in, where **which of `9E` SAHF and `F5` CMC fails to land was NOT
  decided** and the deciding measurement is written down (`+ss_at=<clk>` on
  `SSA_E_PSW`, no RTL change); 1 = `raw_15` under `50`, off by 2, **unexplained**.
* **17 b2-tranche seeds** (171/188).  V5 remains a standing REGISTERED FAILURE
  at 171/188 ≠ 188/188 and is not re-opened.
* **14 seeds of the 500-seed in-silicon population** (435/449, residue `bs` 11
  `qs` 3).  The FABRIC leg is the better one there: two `data` divergences the
  MODEL has and the BITSTREAM does not.
* **4 shared seeds (§49.7)**, three of them an exact byte swap on an odd-address
  word write — M5b's A0 swapper applied where the chip does not.  The ucore and
  the model agree with each other and disagree with the socket: a ledger finding,
  deliberately not patched.
* **5 `BOUND WARNINGS`** — seeds whose EU completed-read store saturated, i.e.
  ran outside the regime `qdepth_probe.py` proves.  Scored normally, not excused;
  `ENGINE ABORTS` is 0.  §46 proved the two-slot bound over every graded corpus
  *and* met its own falsifier on runaway stimulus, so the capacity was NOT
  deepened — fitting two more slots to garbage would be the large-fitted-table
  failure the standing principle names.

### 4. Carried forward unchanged, documented-but-not-rendered

The far-CALL / far-JMP `CS` recognition shadow and the taken-branch recognition
boundary (`post_flush`): no golden reaches either.  `opr_free_p` / `set_oprfree`
stay **PROVABLY VACUOUS** (F31).  The 8080 loader / BRKEM path is ledger R4; the
A30 ambiguous micro-address is emitted at the sim's fixed-priority bank-B winner
with the alternative recorded and a falsifier attached.

### 5. Platform

* **`evt_hold` widen (§48.5)** — NOT TAKEN, with the packing already measured:
  register `0x20` packs `evt_delay[15:0] | evt_hold[23:16] | evt_pin[26:24] |
  evt_arm[31]`, the free space is bits `[30:27]`, so the widest drop-in is a
  **12-bit** hold (max 4,095, which covers the banked 300).  It is a
  HOST-PROTOCOL change as well as an RTL one — `fuzz_campaign._evt_tuple`,
  `check_seq.run_tb` and `check_seq.run_chip` all pack this word.
* **F45's guidance comment** in `tb_v30_core.sv` still says *"run many seeds"*
  and *"most flips must diverge"*; the correct guidance is **step the seed by
  16** and *"some must diverge, and which ones is form- and
  freeze-point-dependent"*.  The TB was frozen for scoring; unfixed.
* **F50 item 3**: the ucore's CE-hold probe has **no EU coverage** — it watches
  `{r_ts, r_q_cnt, r_fetch_ptr}` where the FSM probe also watches `u_eu.state`.
  So the clean `+ce_div` cells are BIU-state evidence; the EU-side evidence is
  the golden row match.
* **The sim's 9D flag-commit erratum (§42.6 item 4)** — on `ulockstep`'s UNMASKED
  view the `9D` T4 PS nibble is a real, non-retention difference in which **the
  RTL matches the silicon and the MODEL does not** (`sim/exec_impl.h` commits
  FLAGS at the `OPR -> FLAGS` row; F39 says the chip commits at the read's data
  edge).  Booked, not patched: it is a one-line change to `wr_dst1`'s FLAGS arm
  plus the `F` wait's ordering, it moves a column both gates mask, and the model
  is at 169,000/169,000 today.  **It belongs to whoever next opens
  `biu_timed`** — and it is the one place this campaign owes the model a fix.
* **The FSM regression bisect** (§(c)) — 2026-07-30 → HEAD, not started.

---

## (e) WHAT U5 ROUTES TO THE USER

Three decisions.  U5 presents the evidence and does **not** take any of them.

### 1. The FSM core's disposition — KEEP AS REFERENCE, or RETIRE

*Presented both ways, deliberately.*

**The case for KEEPING it:**
* It is a genuinely independent second implementation, and independence is what
  made this campaign's A/B meaningful at all.  Every "the ucore is right"
  statement in this document is stronger because a differently-built core
  disagreed somewhere and the golden adjudicated.
* It is 169,000/169,000 on v0.1 as graded for its whole life, boots, has a clean
  save-state map, and its bitstream is on the board today.
* It predicts the interrupt boundary from the pins alone, which is what told
  §36/C5 that the model's `max` was a replay artefact.  **A second
  implementation is a falsifier generator.**
* Retiring it removes the only control on a future ucore change.

**The case for RETIRING it:**
* **It is 59/178 in fabric on fresh random-wait programs** — the axis the project
  ranks first — against the ucore's 176/178, from the same HEAD.
* **It has regressed 104 seeds and no standing gate saw it** (§(c)).  A reference
  that can silently regress is not a reference.
* **It carries a second, older defect nothing saw** — the HALT pad drive — which
  is 0/600 on v0.1's HLT forms and 16/283 on the sweeps once the comparator is
  honest.
* Its 18/1,702 on the registered fuzz bank means it cannot function as a
  whole-program control at all.
* It is a rail forest: the class-5 unified law, `race_law.svh`, the IRET arm, two
  `lpm_divide` instances, and per-opcode timing exceptions — the shape the
  standing SIMPLICITY directive names as a signal of misunderstanding.
* Maintaining it means re-flashing it whenever HEAD moves, or the A/B is
  uncontrolled (§51.8b, measured).

**A third option, stated because it is cheap:** keep the RTL, delete the *claim*.
Demote it from "reference implementation" to "archived first attempt", drop its
standing ratchets from `CLAUDE.md`, and stop building its bitstream.  That keeps
the falsifier-generator value at zero maintenance cost and stops the repo
asserting numbers that a corrected comparator no longer supports.

### 2. `evt_hold` / the EVT ratchet re-banking

F46: the rig's `evt_hold` register is 8 bits and **760 of 1,008 EVT seeds were
banked asking for 300**, so the socket was held for `300 & 0xFF` = 44 clocks.
The model cannot notice (it is HANDED the acknowledge positions); the ucore
predicts them and re-enters the handler 2-4 times — **545 of 545 INTR trails
diverge as "extra INTA pairs", and 540 of those 545 put the FIRST acknowledge on
exactly the chip's clock.**  The recognition is right; the directive was never
physically applied.

`--rig-hold reg8` moves the **model's** EVT number too (+71) as well as the
ucore's (+682), so it is OFF by default and the EVT ratchet is NOT re-registered
against it.  **The decision is whether to widen the rig to 12 bits and re-bank
the EVT population.**  Cost: an RTL change plus a host-protocol change in three
call sites, plus a re-capture; and it must go into BOTH bitstreams or it
confounds the core A/B.  Benefit: the EVT column becomes a real gate instead of
two readings.

### 3. V1's re-registration — a REGISTRATION NOTE, not a rewrite

**The old record stands exactly as written**: V1 was registered at *"≥ 85.0 %"*
before any board contact and was **MET at 98.9 %**.  §51.8a's defect note stands
beside it: the bar was set below the banked tranche's 89.4 % on the reasoning
that fresh seeds are not cherry-picked, and the measured direction is the
opposite — a fresh population is EASIER, because the banks were built from seeds
where the model already diverged.  The frozen FSM core scored 91.6 % on the fresh
population and 1.1 % on the banked one.

Two fresh-population baselines now exist, both frozen and committed before their
first capture:

| population | seeds scored | ucore in fabric |
|---|---|---|
| §48.4 priority tranche (manifest `92e3de08…`) | 178 | **176 — 98.9 %** |
| §52.7 in-silicon A/B fuzz (manifest `72afd71e…`, disjoint `k`) | 449 | **435 — 96.9 %** |

**Registered here as the successor bar, for the user to adopt or amend:**

> **V1′** — on a fresh, frozen, stratified `wrand` population of ≥ 150 scored
> seeds, captured after the freeze is committed, the ucore in fabric is
> cycle-exact on **≥ 96.0 %** — set one point below the *lower* of the two
> measured baselines, not below the higher — **and** strictly above the FSM core
> built from the same HEAD on the same seeds by **≥ 30 points**.  The second
> clause is the discriminating one §51.8a said V4 has to supply, and it is the
> clause a barely-better core cannot clear.

---

## (f) GATE LEDGER

Every gate, its number, and the commit that established it.  Every number was
REPRODUCED by a re-run immediately before the closing commit.  *Reproduction is
not passage*: the rows marked RED / NOT MET reproduce as exactly that.

| stage | gate | number | commit |
|---|---|---|---|
| U0 | FSM clean baseline re-established from a clean HEAD | every gate on its standing number; binary `00c33504d0…`; the only deviation was **F2**, an instrument defect | `c3afe2b90a` |
| U0 | F2 — `check_boot`'s RTL leg was missing `+mirror=1` | both legs **220/220** | `378621e900` |
| U0 | **G0** — generated tables byte-match the sim, three legs | **9,988 / 9,988** (1,028 rows + 8,192 micro-addresses + 768 PLA entries) | `0bfea2bfd0` |
| U0 | ss_lint / ss_flopcensus on HEAD | PASS; the "phantom" was the dirty worktree | `c3afe2b90a` |
| U1 | **GATE U1** — BIU lockstep vs the model, scripted set × 4 wait levels | **32 / 32 scenarios, every clock** | `4bf0bc51c5` |
| U1 | boot parity, BIU-only | **NOT MET and VACUOUS** (F3: the reset is a microcode march) | `4bf0bc51c5` |
| U2 p1-p2 | the rung ladder, module contract (F7), store path (F11), split loads (F12) | 7 forms 500/500; recon 7,775 / 20,820 | `7ebc7e49ac` … `9d5dc35965` |
| U2 p3 | the four families as ONE statement (F14-F28), the boot march | **G3 159,348**; boot **220/220** | `4af352b0d8`, `5f288664ad` |
| U2 p4 | F31 (the OPR hold), F32 (the divider), F33 (the QS=E guard) | **G3 164,787** | `91a37f2fa2` |
| U2 p5 | the interrupt and HALT rung (F34-F36), the 1BL strobe (F37), the string tail (F38) | **G3 168,886**; the four `evt` cells 0 → 167/1,050/174/1,063 | `cc8e79f87e` |
| U2 p6 | F39 (the flag register's data edge), F40 (the REP abort's two anchors) | **G3 169,000 / 169,000**; all four `evt` cells 100 %; `ulockstep --golden` **1,735/1,735** | `7f7f12bde5` |
| U3 | F41 (M21's pad half) landed; the HLT sweeps triaged | sweeps 241 → **249/283**; G3 unmoved | `5cd60d89fe` |
| U3 | the stale `CLAUDE.md` HLT ratchet corrected UPWARD; the "beats the model" claim RETRACTED | model 91/97, 95/95, 44/46, 42/45 | `e9d283bc05` |
| U3 | F44 (silent ROM load), F45 (mode-4 seeds) — two vacuity findings, neither moving a number | — | `0833f53ea7` |
| U3 | **GATE U3** — the ladder, the fuzz TB leg, the platform, the fourth Codex review | 11 of 13 on the sim's number; `ulockstep --golden --cases 50` **17,350/17,350**; wvec **88/88** (FSM 71/88); REG fuzz **1,394/1,702** (sim 1,272) | `180cca16d7` |
| U4 | F48 DISCHARGED — the bound proved over the corpus, refuted as universal, counters made to saturate | `ENGINE ABORTS` 6 → **0**; `BOUND WARNINGS` **6**, named and scored | `2ddf6fa0b6` |
| U4 | F49 (five unmapped flops) + F44's guard, proved armed by three negative controls | `SS_VERSION` 0x81 → **0x82**, `SS_COUNT` **218**, `ss_lint --core ucore` **rc=0** | `e6d15db258` |
| U4 | `check_ab_sim` restored (unbuildable since 2026-07-13) with a `--core ucore` leg | **187 rows MATCH**, both cores | `4bc4a17b2e` |
| U4 | in-fabric bars PRE-REGISTERED before any board contact | V0-V5 + F42's falsifiable prediction | `371edc5287` |
| U4 | F47 CLOSED — `begin_sequence()`'s `opr_fresh` line | REG **1,394 → 1,483**, tranche **168 → 171**; band OVERSHOT and recorded as a deviation | `fd9fcbd94b` |
| U4 p1 | **G6 (synthesis)** | **RED — `Error (11802) Can't fit`**, no bitstream, nothing flashed | `f90a9f0a7b` |
| U4 p2 | §50's cause REFUTED by measurement; the unrolled chain folded | EU 32,011 → **12,496** cells; ladder re-scored, **zero deltas** | `5dce53a1a7`, `853982a4a0` |
| U4 p2 | the priority tranche FROZEN before any board contact | 200 seeds, manifest `92e3de08…` | `758d9c1b42` |
| U4 p2 | **G6 fit / Fmax** | fit **GREEN** 29 % ALMs; **Fmax RED — 13.99 MHz**; nothing flashed | `00289c4396` |
| U4 p3 | the ENABLE-FORM refactor (`ce` onto the register enable) | ladder re-scored **three times, zero deltas**; `--ce-div 4 --ce-hold-check` `CE_HOLD_VIOL 0` | `293ca60430` |
| U4 p3 | `srst` taken out of the next-state cone | **G6 GREEN — 26 % ALMs, Fmax 45.56 MHz, TNS 0.000 on every domain** | `a17933359e` |
| U4 p3 | **FLASH #1 + FIRST LIGHT + THE PRIORITY GATE** | chip path MATCH 800; first light **800/800 ×3**; **tranche 176/178, V0-V5 ALL MET**, V3 at ZERO seeds apart | `56019be9c1` |
| U4 p3 | the in-silicon A/B fuzz, 500 fresh seeds, frozen before capture | **435/449 (96.9 %)**, 1,000 captures, **0 errors** | `de7874ae89`, `31e96121a5` |
| U4 p3 | FLASH #2 — the FSM A/B bitstream rebuilt from the SAME HEAD; §51.8b closed | fabric ↔ Verilator **200/200 for BOTH cores**; task #31's flash debt **DISCHARGED** | `31e96121a5` |
| U4 p3 | **§48.3 — F42's registered prediction** | **REFUTED — 29/283 in fabric**, socket control 49/49 | `7b4027ff34` |
| U4 p3 | the FSM core's 104-seed random-wait regression | 163/178 (2026-07-30 build) vs **59/178** (HEAD), fabric and Verilator alike | `7b4027ff34` |
| **U5** | the F42-refutation fix PRE-REGISTERED before the TB or the RTL was touched | four bars, including the prediction that removing the mask costs BOTH cores 600 v0.1 cases | `ee0bb4148c` |
| **U5** | **F51 — the HALT pseudo-cycle has no data phase**, and the TB mask removed | bar 1 MET exactly (both cores 0/600, nibble 2 → 0); bar 2 MET (**ucore back to 169,000/169,000**, sweeps 249 → **259/283**); bar 3 the FSM at **168,400** and **16/283**, routed; bar 4 **zero deltas** on the whole ladder | `ce8b6bcdb6` |
| **U5** | the two `bs` tranche seeds CLASSIFIED | **ucore ≡ SIM on 4,000/4,000 rows** on both — a shared divergence, ledger not patch | `24d8aac922` |
| **U5** | the fabric re-score PRE-REGISTERED before board contact; **G6 re-run** on the fixed RTL | **0 errors, 27 % ALMs, Fmax 48.03 MHz** (up from 45.56), setup **+9.121 ns**, TNS **0.000 on every domain**, hold +0.244; `.sof 924c4a61e0…` | `24d8aac922` |
| **U5** | **FLASH #3 + the fabric re-score** | chip path **MATCH 800**, first light **800/800 ×3**, socket control **49/49**; sweeps **29/283 → 143/283**; bar 1 (zero F42-signature cells) **MET absolutely**; **bar 2 MISSED** at 143 vs a registered ≥ 249, the miss **116/116 one class** | `99c77a61fe` |
| **U5** | verdict, ROADMAP, `CLAUDE.md`, ledger §53-§56; every standing gate re-run | §(a) | this commit |

---

## (g) THE FIFTH CODEX REVIEW — ON THIS DOCUMENT, AND WHAT IT CHANGED

Scoped to three asks with the file set named exactly (§36's wedge lesson), on
the thread that carried C1-C8.  It returned a verdict line on each and **two of
the three went against me.**

**C9 — the document FAILED the S4r standard on four counts.  All four fixed
before the closing commit.**

1. **Stale G6 numbers.**  §(a) and §(c) quoted **26 % ALMs / 45.56 MHz /
   +8.922 ns** — the U4 pass-3 build — while the bitstream this campaign closes
   on is the U5 one at **27 % / 48.03 MHz / +9.121 ns** (§55.1).  Corrected, with
   the superseded figures kept beside them rather than deleted.
2. **The missed bar was misidentified — the S4r defect that mattered.**  §(a)
   said *"where a bar was missed it is recorded as missed, and the largest of
   those (**the FSM core's own numbers**)"*.  Wrong on both halves.  The largest
   — and only — **missed registered bar** is §55.2 **bar 2**, the fabric HLT
   sweeps: registered ≥ 249/283, measured 143/283.  The FSM core's
   168,400/169,000 and 16/283 are §53.4 **bar 3**, a *pre-registered ROUTED
   FINDING*: the bar said in advance that the frozen core would not be fixed.
   Calling a routed finding "the largest missed bar" flatters the document (it
   hides the real miss) and slanders the FSM core (it books a declared
   disposition as a failure).  §(a) now separates them explicitly.
   **And a second instance of the same defect, found while fixing the first**:
   §(a)'s "is the model of the bitstream the bitstream?" row asserted *"It did
   not happen"* of a fabric-vs-sim gap while §56 documents a 116-cell one — true
   of the priority tranche (200/200), false in general — and §55.2's bar 2 had
   **named that consequence in advance** (*"a fabric result far below the offline
   one would be a FABRIC-vs-SIM finding … and is the MORE important result if it
   happens"*).  A registration contained a clause, the clause fired, and the
   report did not invoke it.  The row now says which population each half is true
   of and points at open item 0.
3. **The F1-F51 / review-finding accounting was incomplete.**  §(b) grouped
   loosely, printed counts that did not sum to 51, double-counted `F51`, split
   `F48` across two groups, buried `F25` inside `F3`'s entry, omitted **`F9`**
   entirely, and said "five Codex review findings (C1-C8)" — a count and a range
   that contradict each other.  §(b) is now an **exhaustive, disjoint partition
   — 32 + 3 + 8 + 8 = 51** — verified mechanically by regexing the section text
   rather than by eye.  The review count is corrected to **twelve findings across
   five reviews**, which required noticing that the second review's finding is
   labelled **D1**, not `C`-anything, and had been dropped from every count in
   the document.
4. **The ledger citation omitted §55-§56.**  Corrected in the header and the
   footer.

**C10 — the U5 mask call: SOUND.**  The three things that could have been wrong
were put to it explicitly: removing a comparator mask at a closure at all; not
fixing the frozen FSM core when the fix is one line; and presenting a ratchet
moving DOWN as a corrected-instrument re-score rather than as a regression.
None was called wrong, and the ledger's framing of the FSM numbers was accepted
as honest.

**C11 — the INTA classification: NOT ESTABLISHED.**  The one that matters, and
it is the review earning its keep for the second campaign running.  §56 argued
that the 116-cell fabric gap is a harness property and not a core defect.  That
is **F42's argument one population over** — and F42 was accepted as sound by
C6, measured population-complete at 24/24, and REFUTED in fabric anyway.  116/116
is a correlation over a population; it is not an intervention.  Adopted verbatim:
the attribution is now recorded as a READING and the claim as NOT ESTABLISHED,
with the settling measurement pre-registered and unrun in §56.3a — a `core_ad`
retention model, both bar halves required, and *any* of the 116 still failing
means those cells are the core's.

**What the five reviews are actually worth, stated once**: C3 asserted a bound
that then FIRED and turned out to be right about the bound and wrong about the
blame; C5 stopped a forward-looking term being fitted into hardware that cannot
have one; C6 accepted a conclusion and rejected the strength of its evidence,
and running the measurement it demanded is what exposed the numbering artefact
that produced this campaign's one retraction; and C11 has just done C6's job
again, on this document, about a claim I was about to publish as settled.  **The
recurring value is not catching errors of fact — it is catching the moment a
reading gets promoted to a finding.**

---

*Campaign closed 2026-08-04.  Ledger: `docs/notes/ucore_provenance.md` (§0-§56).
Branch `ucsim`.  Governance: RTL-vs-sim = a bug in the RTL; RTL-vs-silicon the
sim does not share = a bug in the RTL; RTL-vs-silicon the sim DOES share = a
ledger finding, and no ucore landing without the sim landing first.*
