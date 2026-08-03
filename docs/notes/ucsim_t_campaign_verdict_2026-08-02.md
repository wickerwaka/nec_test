# ucsim-t campaign verdict — 2026-08-02

**The question the campaign asked:** *can the microcode ROM's own
micro-sequencing plus the measured BIU law corpus make the C++ simulator
**cycle-exact** — per-clock row streams matching silicon at arbitrary wait
vectors?*

Companion to `docs/notes/ucsim_campaign_verdict_2026-08-01.md`, which answered
the same sufficiency question for ARCHITECTURE. That one asked whether the
dumps determine *what* the machine computes; this one asks whether they
determine *when*.

**The answer document.** Every number below is a gate run recorded in
`docs/notes/ucsim_t_provenance.md` (cited as §n) or a commit in the gate ledger
of §(f). Nothing here is a new claim. The plan as executed is in the repo
verbatim at `docs/notes/ucsim_t_campaign_plan.md`.

---

## (a) Verdict

**Yes at the instruction scale and at the measured law scale; PARTIALLY at
whole-program scale, and the shortfall is enumerated rather than estimated.**

The simulator reproduces silicon **clock for clock** on the waited golden
tranches (2,400/2,400), the boot from RESET release (220/220), the ENTER waited
socket tranche (154/154), the INS `case250` factorial against its chip capture
(2,624/2,624 rails), the frozen decoder oracles at three wait levels, and seven
of the eleven inherited law cards against silicon; at zero waits it is
**99.45 %** of the single-instruction golden suite, short by exactly two named
families. On whole 1,300-4,000-clock random programs under random per-access
wait vectors it reproduces **62.2 %** of a fresh, never-before-seen tranche
completely — from RESET release to the done marker, every pin of every clock —
with every miss in one of four named families and the largest of them localised
to a single clock. It is **not** exact over whole programs, and the
pre-registered victory clause that demanded that is reported FAILED.

### The gates, as pre-registered

| gate | as defined | measured | § |
|---|---|---|---|
| **v0.1 cycle rows at w0** | the ratchet, `rows_exact`, may only grow | **165,490 / 166,400 (99.45 %)** | 10.6, 12.7, 14.6 |
| **v0.1-w1 / -w3 cycle rows** | 2,400 / 2,400, the T2 exit | **2,400 / 2,400** | 11.11, 14.6 |
| **boot replay from RESET release** | `sw/check_boot.py --timed 220` | **220 / 220 rows, loop period 64 exact on both legs** | 12.1 |
| **ENTER waited tranche** | 154 socket digests replayed in-sim | **154 / 154** on all five levels (pushes, walk, full, active, halt_display) | 11.7, 12.3 |
| **INS `case250` factorial vs the chip capture** | STRICT rails: each rail's T1 from R1's T4 equal to the frozen chip capture's | **2,624 / 2,624** (and the whole-program measure over the same 800 runs is now **173,556 / 173,556** leading accesses agreeing in kind+address, **every one on the same T1** — see §(g) item 10) | 13.3 |
| **L1 oracle replay** (`timed_scenario`) | frozen decoder oracles read as-is, at w0/w1/w3 | **18 PASS / 0 FAIL / 9 honest SKIP** | 11.8 |
| **wvec corpus vs SILICON** | 22 seeds × 4 wait vectors, chip-frozen at T2b/T4 | **access count 88 / 88, whole-program bus cycles +0.0 %, per-cycle digest 63 / 88** | 12.2, 14.3 |
| **law cards, MUST set** | C1-C7, C9-C12 as sim unit gates on silicon references | **7 GREEN / 0 RED / 4 UNRESOLVED** | 14.3 |
| **fuzz-bank cycle gate** (T3) | pre-registered §13.0, four clauses | all four met; **947 / 1,702 (55.6 %)** cycle-exact | 13.0, 14.1 |
| **THE VICTORY TRANCHE** (T4 B2) | pre-registered §14.0, V0-V5 | **V0-V4 PASS, V5 FAIL** | 14.0, 14.4 |
| functional regressions (standing) | 7.34 M architectural cases, zero regression | **7,341,126 / 7,341,126** | 14.6, §(f) |

**The w0 denominator, and the correction that produced it.** T1 wrote its exit
target as 166,800 = 169,000 − 2,200, taking the pin-event exclusion **S9** to be
the eleven forms whose *architecture* the timed path cannot produce. That is the
wrong set: `HLT.RES` and `POLL.REL` are architecturally exact (200/200 each) and
so were never in the 2,200, but both are pin-event forms whose ROWS the model
cannot produce. The reachable-at-w0 denominator is **166,400** (§10.6). This is
a re-labelling of 400 cases that were always pin-event; no case moves from
"should be exact" to "excused" on any ground S9 did not already stand on. The
T1 exit clause **166,800/166,800 was NOT MET** and is reported not met; against
the corrected denominator the campaign closes at 165,490/166,400, **910 short**.

### The law cards

**7 GREEN / 0 RED / 4 UNRESOLVED** (`sw/timed_lawcards.py`), each GREEN scored
against a named silicon capture, not against the RTL:

| GREEN | on what |
|---|---|
| C1 LC1 steady-state resume gap | the frozen Arm-C sled — pause population sim 43 vs chip 43 at N=8, 30 vs 30 at N=12 |
| C3 LC1 `cidle` pin | same sled, `cidle` pinned at 3 at both N |
| C4 / C5 LC2 aged-band PAUSE / GO | `fz90364:ws5:wmax1`, promoted silicon cell |
| C9 LC4 general lead reservation | 2,400/2,400 at w1/w3 + the 4/4 ENTER P1 cells clock-identical to the socket |
| C10 / C12 LC4 late reservation / `pf_rsv_lead` | `fz90270:ws5:wmax1`, promoted silicon cell |

The **four UNRESOLVED cards are STIMULUS gaps, not model failures**, and each is
named with the capture that would resolve it:

* **C2** (LC1 queue-fill ramp) — the ramp needs a queue-fill TRANSIENT; the
  Arm-C sled isolates only the steady state, and no other retained corpus
  carries a controlled fill ramp.
* **C6 and C7** (LC3 RMW-write `Tw` parity) — **board-by-construction**. No
  golden, no fuzz seed and no T2b/T4 capture carries a micro-RMW memory write
  that becomes ready AT T4 with a controlled `Tw` parity. The stimulus has never
  been captured.
* **C11** (LC4 `owns_slot`) — the card names an ENUMERATED source set and no
  directed capture isolates a single source; the `P-LC4-matrix` probe stays
  booked.

LC8 (`pf_drain` / mid-band pause) remains **DELETED** and was never
reimplemented, as the retired campaign's must-not-reimplement note requires.

### The fuzz-bank gate (T3), as pre-registered

The bar was frozen in §13.0 from a 50-seed pilot, **before the first full run**,
and it deliberately claims no absolute pass threshold — the pilot said the model
was not cycle-exact over whole programs, so an absolute threshold would have
been either vacuous or unreachable. What it claims, and what could fail:

| clause | as registered | outcome |
|---|---|---|
| 1 | zero hard failures (`GEN_DRIFT` / `REGEN_ERROR` / `SIM_ERROR`) | **0** |
| 2 | a CLOSED taxonomy — no "unknown" bucket | **met**; every scored seed's first divergence is in a named family |
| 3 | a RATCHET on M1/M2/M3/M4 with the denominator frozen | **met and monotone**: M1 32 → 44 → 136 → 947; and *no seed lost divergence-free prefix at any step* (M8 682 gained / 0 lost, M8b 1,265 / 0, M9 73 / 0) |
| 4 | a falsifiable prediction: the census is dominated by `qs`, with `data` and `bs` the only other families | **PARTIAL MISS, reported as one**: `qs` did dominate the first full run (76 %) and `data`/`bs` were next, but the full run also turned up `ps` (24), `addr` (8) and `ube` (2) — families a 50-seed pilot cannot see |

Scored population **1,702** (EVT 1,165, OPEN_BUS 375, both exclusions declared
in advance and both properties of the CAPTURE, not of the model's answer). The
denominator is identical in every run in the campaign, so none of the movement
is a shrinking denominator.

Final: **947 / 1,702 (55.6 %) cycle-exact**, median divergence-free prefix
**1,068 rows**, median prefix FRACTION **1.000**, ≥0.5 / ≥0.9 = **1,192 / 950**.
A median prefix fraction of 1.000 means the median banked seed is exact through
its entire multi-thousand-row capture.

### THE VICTORY TRANCHE — V0-V5 exactly as registered

216 fresh seeds, never-before-seen **by construction** (three generators × nine
wait classes × eight seeds, drawn deterministically from `k >= 100000`, strictly
outside every banked range), population frozen and committed
(`sw/testdata/t4/b2-tranche/population.json`, sha256 `08ec6dc4…`) BEFORE the
first capture. Socket only, 3 repetitions per cell, raw 64-bit words and full
per-clock rows retained with a sha256 beside each.

| | metric | bar | measured | |
|---|---|---|---|---|
| **V0** | hard failures | 0 | **0** | **PASS** |
| **V1** | scored seeds cycle-exact over the whole window | ≥ 55.6 % | **117 / 188 = 62.2 %** | **PASS** |
| **V2** | median divergence-free prefix FRACTION | ≥ 1.000 | **1.000** | **PASS** |
| **V3** | every non-exact seed's first divergence in a NAMED family | 100 % | **100 %** (Q2 42, `qs` 18, arbitration 10, `data` 1) | **PASS** |
| **V4** | cycle-exact rate, five `wrand` strata vs four fixed strata | within 10 points | **wrand 71/107 = 66.4 % vs fixed 46/81 = 56.8 %** — 9.6 points, random-wait side BETTER | **PASS** |
| **V5** | the campaign's literal victory phrasing, "fresh random-wait tranche **cycle-exact**" | V1 = 100 % | **62.2 %** | **FAIL** |

Population 216, scored 188, excluded 28 OPEN_BUS (declared in advance, detected
with the bank's own detector), 0 UNSTABLE, 0 EVT (excluded at GENERATION, so
the denominator could not move after the fact).

**V5 FAILS.** It was registered in §14.0 precisely so that it could not be
quietly redefined, with the expectation of failure written down in advance:
*"the campaign's victory will be reported as PARTIAL with V1-V4 scored as
written. No post-hoc restatement of 'cycle-exact' is permitted; if V5 fails it
is reported failed."* It is reported failed. **The campaign's victory condition
is PARTIAL.**

**What 62.2 % means, stated exactly.** The median seed is exact through its
ENTIRE capture — V2's median prefix fraction is 1.000, so more than half of the
tranche diverges nowhere at all. The 71 misses are not 71 shapeless failures:
they are **four families**, and the largest (Q2, 42 seeds) is a single clock
whose PORT half is measured 293/293 and whose EU half is unmeasured (§14.2).
Every one of the 188 seeds runs from RESET release through a 24-80 instruction
random program under a random per-access wait vector, compared on every pin of
every clock.

**The pre-registered falsifiable prediction was CONFIRMED**: the fresh
unselected tranche scores 62.2 % against the adversarially-selected fuzz bank's
55.6 %, for the reason predicted in advance — every seed in the bank was
PROMOTED for diverging against an earlier model.

**V4 is the project's #1 priority written as a gate**, and it inverted: the
wait axis is no longer the weak axis, it is the STRONG one. At **T4 entry**
(= T3 close) the banked whole-program figure was 2.6 %; at T3 entry it was
1.0 % (17/1,702). See §(g) item 12 — §14.4 attributes the 2.6 % to "T3 entry".

### Deviations from pre-registration — the complete set

Recorded here rather than left in the stage sections, because a gate presented
as pre-registered must carry its deviations with it.

1. **The law-card MUST-set clause moved T1 → T2** (§9.6, §10.0, coordinator-
   approved). Read the cards' own Stimulus/Gate columns: every one of C1-C7 and
   C9-C12 is stated on a WAIT VECTOR, and at w0 there is no `Tw`, no aged band
   and no deferred eval, so nine of the eleven have no stimulus at all. T1 is
   not credited with them. It then moved again in practice: T2a could not gate
   them either, for PROVENANCE (§11.10) — the only reference was an RTL
   baseline, half of which was vacuous — and they became scoreable only when
   T2b banked the chip captures (§12.6), at which point six of them scored RED.
2. **The T1 exit denominator was corrected 166,800 → 166,400** (§10.6), stated
   above.
3. **The T3 gate declares no absolute pass threshold** (§13.0), stated above.
4. **The B2 stability projection was changed after capture** (§14.4). The first
   pass flagged 84 of 216 cells "unstable" under the T2b blackbox projection.
   Diagnosed on the board before anything was scored: over four cells × three
   repetitions, every differing row is in indices 0-8 and NOT ONE row from 9 on
   differs — and rows 0-8 are the capture's reset settling, excluded by
   `fuzz_classify.diff_rows`, the frozen T3 column policy this gate is scored
   with. The projection was changed to the gate's OWN window; the stricter T2b
   number is retained beside it. **This is a post-capture change to a registered
   criterion and is recorded as one.** With it, 0 cells excluded for instability;
   a direct check of the 12 promotion cells at 5 repetitions each is 12/12
   stable at 4 MHz and 12/12 at 8 MHz.
5. **Two capture-side field exclusions, measured not assumed** (§12.1): `rd_n`
   and the raw `bs_late` are within-cycle pulses read at a fixed sampling edge,
   so they move when the clock divider halves. `rd_n` was checked for
   independent content and has none (an exact function of `(t_state, bs)` at
   div=8, one ambiguous cell at div=4). Both excluded from the stability
   projection, and the exclusion is in the ledger rather than buried in the tool.
6. **T2b P3's prediction 2 was FALSIFIED and is reported falsified** (§12.3):
   the HALT pseudo-cycle DOES take wait states (T1..T4 = 4/5/7 clocks at
   w0/w1/w3). What is wait-independent is the CPU's side, the 2-clock status
   display.
7. **B3 (A30) was registered best-effort and did not consume board time**
   (§14.5); it was settled to a datapoint from the banks instead. Recorded, not
   hidden.

### What the answer is NOT

* **Nothing here is claimed for interrupt/INTA timing under waits.** It is an
  explicit scope exclusion of the whole campaign, inherited from the RTL
  campaign, and it is excluded from every gate — post hoc at T3 (1,165 of 3,242
  banked seeds are EVT) and **by construction** at T4 (`no_evt` set at
  GENERATION, so the victory tranche's denominator could not move).
* **Nothing here is claimed for 8080-mode timing.** No gate in this campaign
  separates it. The `t30-brkem` bank scores 5/62 cycle-exact — visibly the worst
  bank — and that number is reported, not explained.
* **The 2,600 v0.1 pin-event rows are outside the w0 denominator**, not passed.
  The HALT display is now modelled and measured (§12.3), but the INT/NMI/RESET
  event scheduler and the POLL pin's 5-clock sampling are not, so those thirteen
  forms' ROWS are still unproduced; arch through the timed path stands at
  166,800/169,000 for the same reason.
* **The per-cycle wvec digest is 63/88, not 88/88.** The access count and the
  whole-program bus-cycle count are exact; the per-cycle digest is not.

---

## (b) THE MECHANISM LEDGER — the campaign's scientific product

This is what the campaign found, and it is the deliverable a successor
inherits. **Every entry is a register, a threshold, or a fixed cycle index.**
There is no fitted table anywhere in `sim/biu_timed.{h,cpp}` and no per-opcode
timing exception anywhere in `sim/` — the claim is checkable by `grep`.

### The eval instant — the object everything else hangs off

**`e = (N == 0) ? 2 : 3 + N`** — one instant per bus cycle: T3 at zero waits,
T4 otherwise. Derived from the RIG's own READY generator (`hdl/rtl/nec_bus.sv`,
the `tick_rise` branch), not fitted: the READY *line* is high for exactly the
clocks the T-state machine may leave for T4, the CPU registers it at the end of
every clock, and one clock later does two things at once — releases the status
register and runs the completion eval. Every other quantity is a FIXED OFFSET
from it:

| offset | what happens |
|---|---|
| `e` | status goes passive; OPR is released to a `-> OPR` row |
| `e+1` | the DISPLAY clock — the winner's status / address / PS |
| `e+2` | the winner's T1, **and** `eu_done` (read hand-over, store retire) |
| `e+3` | a fetched byte becomes POPPABLE |

*Evidence:* §11.1; `B8` case 0 at w1 (before it, every pop in the case is
exactly one clock early and the bus geometry is already right). *What it
replaced:* mission-H's **three separately fitted laws** — completion-eval
deferral, queue-push defer, and "post-access EU schedules stretch by exactly one
cycle per waited access" — are the same offset seen from three places. The
apparent `N = 0` discontinuity is entirely the rig's counter short-circuiting at
zero; the CPU only ever waits one clock after a level.

### The mechanisms

| # | one sentence | evidence |
|---|---|---|
| **M1** | A bus cycle is `T1 T2 T3 (Tw×N) T4`; the next cycle is chosen at a COMPLETION EVAL, its status is displayed on the clock after, and its T1 opens the clock after that. | §7.1 — `B8` case 0 (back-to-back CODE, no idle clock) and case 1 (the same rule on an idle clock instead of T3) |
| **M2** | The status output is a REGISTER, loaded at the eval and released exactly one clock before the next display clock — so every bus cycle is followed by exactly ONE passive clock and there was never a `w==0 ? 2 : 3+w` conditional. | §7.2, generalised to all N by the eval instant (§11.1) |
| **M2r** | The wait-state conditional lives in the RIG, not in the part: one register plus one READY-sampling instant. | §11.1 |
| **M3** | Six-byte queue; word fetch from an even address, single upper-lane byte from an odd one; a completed fetch pushes at `e+1` and its byte is poppable at `e+3`; a POP is a point sample riding a clock that already exists. | §7.3 — `B8` case 0, where every pop lands on the first clock the latency allows |
| **M4** | The prefetch resume predicate is an OCCUPANCY THRESHOLD and nothing else: at an eval, with no EU request and no SUSP outstanding, fetch iff `occupancy + bytes-in-flight <= 4`. | §7.4 — no table, no phase key, no fill history, no `(phase, occ, fill)` tuple; survives the whole campaign unchanged |
| **M5** | A WRITE drives the whole 16-bit datapath value and lets UBE/A0 select the lane, so both byte cycles of a split word write show the same word. | §7.5 — `50` case 1, `PUSH AX` at an odd SP drives `0BCD` on both halves |
| **M5b** | One 8-bit rotator, applied on BOTH sides of the bus, is the whole "companion byte" folklore: the register file has no byte read port, memory presents the whole ALIGNED WORD, and the AD display is always the datapath value rotated by A0. | §8.1 — `88` byte-store T1 rows 366/366; 19,237 read cases with 747 explained RMW exceptions; the `58` split-POP discriminator |
| **M6** | A fetch's bytes are written into the queue on **T4+1**, and that clock is not a prefetch-grant point — so the earliest eval that may resume a prefetch after a pushing fetch is T4+2 at EVERY wait level. | §12.1 — the P1 socket capture: chip and sim clock-identical for 197 clocks, parting on one eval |
| **M7** | The prefetch-eligibility test is SAMPLED AT A FIXED CYCLE INDEX (2) and latched; the completion eval only applies what that clock decided. | §13.1 — the Arm-C silicon sled, 2,252 aligned evals: index 2 gives 4 / 0 errors at N=8 / N=12, the eval instant gives 15 / 12 |
| **M7b** | The "a fetch is out" term clears one clock LATER than the queue counter takes its bytes, so across the two landing clocks the scheduler counts them twice and the unchanged `<= 4` threshold bites two bytes early. | §13.2 — 53 aligned declined evals, `q <= 2` grants and `q = 3,4` waits with ZERO exceptions |
| **M8** | The queue pop is a plain **`max(demand, ready + pen)`** in three role classes — and there is NO re-run. | §14.1 — every cell single-valued on the goldens AND the chip captures, at w0 and at every wait level |
| **M8a** | The ready clock steps by exactly ONE when the delivering fetch was waited — flat from `Tw` 1 to 15, not proportional. | §14.1, all 3,242 banked captures; already free from M2r |
| **M8b** | The DEFERRED instruction boundary (an instruction whose write was still staged in the pairing latch) was one clock short: the E-row path pre-pops and then charges, the deferred path popped at the tail of `step()` after the charge had gone by. | §14.1 — invisible to every gate, because v0.1 runs ONE instruction per case from an injected queue |
| **M9** | PS3 on the pins is the EMULATION-MODE bit (MD), live on every cycle including CODE fetches. | §14.1 — all 73 `ps d!=5` first-divergences begin at an opcode `0F xx`; PS3 comes up between the PSW push and the CS push |
| **M10** | The HALT display's upper nibble is a LIVE PS, not a constant — the chip carries IE on it like any other cycle. | §14.3 — of 139 + 187 accesses in the two directed wvec cells, exactly ONE parts, the closing HALT, in its PS nibble alone |

Alongside them, three flush mechanisms (**F1** the QS port is an arbitration,
**F2** the ROM's bus-control field is decoded one row early, **F3** the
flush-only prefetch-T4 eval commits the REDIRECT ONLY — §8.2), the **OPR
interlock** (`F` marks the row that touches OPR; which way it touches picks
which half of the interlock applies — §9.2, §9.3), and one defect that was never
a law at all (**R-STALL**, a leaked OPR hold; §13.3 — worth 852 chip-exact INS
rails, `timed_ins_replay` 1,772 → 2,624 / 2,624).

### The shape of it, and why it is the point

**FOUR fitted constructs were RETRACTED when the real machine was found. The
model SHRANK as it got more exact.**

| retracted | what it was | what replaced it | net |
|---|---|---|---|
| **the T0 retention rule** — "undriven byte lanes retain" (§2.6) | a plausible bus law, read off a golden | **M5b**: the system presents the whole ALIGNED WORD. The retention rule was an alias of the RIG's 0x90 NOP fill (§8.1) | one law deleted; a whole "companion byte" folklore family (C4, ~6,000 cases) closed by ONE rotator |
| **the §10.4 "literal F2 lookahead" framing** — *the SUSP lead*. (F2 itself, §8.2's one-row-early bus-control DECODE, stands and is listed above; what is retracted is §10.4's extension of it into an EU-side row lookahead.) | three whole-program legs — the boot loop, `0F39`, the ENTER store stub — all seemed to want the EU's bus-control field to reach the BIU one ROW earlier than 169,000 goldens permit; a literal lookahead was measured at −3,446 v0.1 cases and recorded, not landed | **M6**: the socket capture showed the `F` and `S` pops on the SAME ABSOLUTE CLOCKS in chip and sim through the whole divergence window. **The EU was exactly where the model put it; the PREFETCHER was one eval early.** (§12.1) | the premise was wrong, not the constant. All three legs closed together, the w0 ratchet went UP, and w1/w3 did not move |
| **M3c's re-run** (§9.1) — `pop = min{demand + k·step : demand + k·step >= ready}` with a march STRIDE carried in a new field | fitted with four role classes POOLED, where the cells `ready 3 -> pop 4` and `ready 4 -> pop 4` cannot both be a max, so a re-run was invented to hold them together | **M8**: split by ROLE, each class is a plain `max` and every cell is single-valued. `last_dec_` and the stride are **DELETED** | the model is literally smaller. This is the campaign's sharpest case: a wrong law survived a 165,490-case w0 gate (the goldens never sample the discriminating cells) and still owned **87 %** of the fuzz bank's first divergences |
| **the grid-is-eval-cadence hypothesis** (§11.2) | the T2 brief's own hypothesis: that the stretched `grid_phase` might BE the eval cadence — a genuine 2-clock grid | **nothing**. Tested first and FALSIFIED at w0: the strong form costs the ratchet 165,481 → 119,311. Idle evals run on EVERY clock. What survives is the narrow measured statement that the COMPLETION eval's display clock is not an eval point | a proposed mechanism deleted before it could be fitted, and recorded so nobody re-derives it |

Three further retractions of the same kind, for completeness: **B4 = GO** was
retracted at T0 (§0.1 — `(grid_phase, occ, fill)` may not be assumed to close
the machine, and it never had to be); **§11.9's whole-program cadence numbers**
were retracted at §12.2 (a missing mechanism plus a broken reference, not a
Round-3 A2 signature); and **§13.5's PS3-on-an-SS-write reading** was retracted
by M9 (§14.1 — it was reading a flag).

**The simplicity principle's empirical vindication, with the numbers.** The
campaign's standing directive was that *a large fitted table or a many-cased
rule is a SIGNAL OF MISUNDERSTANDING, not a deliverable.* What the numbers say:

* **Fitted constructs deleted and not replaced by anything larger: 4.** In three
  of the four the replacement is strictly smaller than what it replaced; in the
  fourth (the grid) the replacement is nothing at all.
* **Fitted law tables that never had to be written: the enter pilot's 7
  constants** (the grant law's `busfree+1` / `busfree+3` slots are the eval
  geometry read off a timeline, and the sim encodes neither number — §11.7a),
  the per-form **`S_RSV` reservation table** and the per-opcode "reservation
  starts at the final-pop cycle" rule (**one** mechanism, F2, replaced **two**
  fitted laws — §8.2), and the **MUL/DIV compute-burn model** (category C6,
  1,254 cases, booked as "wait-insensitive compute burns"), which turned out to
  need **no burn model at all** — the length was the R-loop's stores waiting on
  OPR (§9.2).
* **The one tabulated thing in the model** — the decoder's byte-demand schedule
  — went from five bare numbers (§7.6) to a march (§9.1, wrong) to **three role
  classes each with a `demand` and a `pen`** (§14.1), and the field the march
  needed was deleted.
* **LC1's steady-state gap and LC2's aged band were deliberately NOT
  implemented** from §7.4 onward, on the grounds that inventing them before a
  golden demanded them would be exactly the failure mode. They score GREEN at
  §14.3 — the sled's `cidle` pin and pause population fall out of M6 + M7 + M7b,
  three mechanisms none of which is a resume table.
* The mechanisms that DID land are, without exception, one register (M2, M7),
  one threshold (M4, M7b), one fixed cycle index (M6, the OPR release, the
  `F3AA` closing pop), one rotator (M5b), one adder pass (§10.1's BCD), or one
  arithmetic form (M8's `max`).

The one place the principle was applied AGAINST a better score, twice, and the
model reverted: §10.7's store-row release (bought +25 cases for 213 new diffs)
and §14.2's Q2 port correction (measured 293/293 on its own half, but landing it
alone costs 947 → 753 cycle-exact seeds because the over-long port hold was
MASKING an EU-side raise clock that is too early). **A better score for a worse
model is reverted.** Both are recorded with their evidence rather than landed.

---

## (c) Open items — complete and honest

Ordered as a successor should take them.

1. **Q2's EU-RAISE half — the first item for any successor.** The redirect
   family is the largest named residual in both corpora (381 of 1,702 banked
   seeds, 42 of 188 fresh). Half of it is MEASURED: over the 293 seeds whose
   first divergence is `qs E!=- bs CODE!=PASV`, the chip shows the flush `E` and
   the redirect's status at the previous cycle's **T4+2** in 293 of 293 and the
   model showed them at T4+3 in 293 of 293, with every clock before and after
   identical and `Tw >= 1` in all 293 — so under waits **the queue port frees at
   T4+2**. Half is NOT: over the whole corpus both T4+2 and T4+3 occur (`tw=1`:
   65 vs 112; `tw=2`: 51 vs 57; `tw=3`: 35 vs 18), so the display is
   `max(EU raise, port free)` and solving the census for the EU half gives a
   raise clock of `last pop + a` with **`a` varying 4..7 by microcode path —
   UNMEASURED**. Landing the port half alone costs 194 cycle-exact seeds, so it
   must be landed WITH the raise clock, not before it. **The experiment is a
   directed factorial over the branch forms (`70-7F`, `E9`, `EB`, and the
   trap/flush paths) at controlled wait levels.** (§14.2)
2. **The `qs` successor family** — 324 banked seeds, `qs -!=F` dominant: a pop
   display one clock out, downstream of Q2's neighbourhood. Very likely the same
   mechanism seen from the other side; do it WITH Q2, not separately. (§14.7)
3. **The four UNRESOLVED law cards** — C2, C6, C7, C11, each a stimulus gap
   named in §(a) with the capture that resolves it. C6/C7 are
   board-by-construction.
4. **The 907-case `F3AA cx >= 2` w0 family** — the last family inside the w0
   suite. It is NOT a second OPR release point (ruled out by the wait axis,
   §11.4) and the closing pop rides a FIXED cycle index, not the eval (measured
   on the socket at w0/w1/w3, §12.4 — the pre-registered reading B). It is
   **w0-only**: at w1 and w3 the model lands on the silicon index by itself,
   because the bus is slow enough that the row engine's free-run is no longer
   the binding deadline. The discriminating pair `F3AA` cases 16 and 10 is
   named and captured.
5. **The remaining w0 tails — 3 cases**, one each in `0F12`, `C1.6`, `F7.4`: an
   address on one cycle, unexamined. (`0F39`'s 9, booked with them at §10.6,
   closed at §12.1.) 907 + 3 = the 910-case w0 shortfall exactly.
6. **The fuzz-bank tails — 50 seeds** (`data` 25, `addr` 21, `ube` 4): control
   flow downstream of an earlier displacement, plus the **arbitration tail**
   (~10 of the fresh tranche's 52 `bs` misses) — an EU access and a fetch
   swapping the same slot.
7. **S9 pin-event rows — 2,600 v0.1 cases in thirteen forms**, outside the w0
   denominator. Needs the INT/NMI/RESET event scheduler in the timed path and
   the POLL pin's 5-clock sampling (`interrupt_model.md`). The HALT half is now
   modelled and measured (§12.3).
8. **8080-mode timing — NEVER GATED.** No gate in this campaign separates it;
   the `t30-brkem` bank's 5/62 is the only number that touches it and it is not
   diagnosed. M9 makes MD readable straight off the pins, which is the
   instrument a successor would start from.
9. **INTA / interrupt timing under waits — SCOPED OUT** of every gate, by
   inheritance from the RTL campaign, and excluded by construction from the
   victory tranche. Un-measured, not merely un-modelled.
10. **A30** — the bank-A/bank-B question for the ROM's one ambiguous
    micro-address. **n = 1 datapoint**, uncontaminated for the first time
    (M9 made MD pin-readable): `t30-raw/raw_3821` rows 969-981, two complete
    INTA cycles both carrying `ps = 0xE` = MD | IE | CS, in emulation mode. It
    points at **bank B / fixed priority** — the emulation-mode-input hypothesis
    predicts a SINGLE acknowledge and that is not what the chip did. **A
    datapoint, not a closure.** The settling experiment is the ledger's own
    directed capture (a contained program that runs `BRKEM`, stays in 8080 mode
    with IE set, and takes an INTR) and it is now cheap to score. (§14.5)
11. **The un-run parked probes**, recorded rather than hidden (§14.5): the
    ALU **status-latch persistence** probe (its ROM-sweep precondition was not
    verified offline in T4, and must be first), **R6** (`0F 20/22/26` with
    `CL = 0`, uninterrupted), the two **POLL BUSY** split probes, **R7**
    (CMP4S sweep-or-unobservable), and **F1 BUSLOCK** — `ClockRow::lock_n` is
    still a constant and no non-S9 v0.1 form exercises it.
12. **The one sled cell left**: `fz90002` at N=8, event 72, where a pop lands
    ON the index-2 sample clock and the chip behaves as though it had not been
    seen — the "occupancy is a register" reading that §12.1 falsified at w0,
    alive in exactly one waited cell. A directed capture (same program, a pop
    forced onto the sample clock) decides it. (§13.7)
13. **§7.6's EA stage** — why the byte-displacement step is the long one is
    described (M8's `pen = 1` on the byte that COMPLETES a displacement) but
    still not DERIVED from a two-clock EA machine. The economical reading — the
    adder stands one stage behind the decode port and reads the byte the clock
    after the queue can give it up — is offered, not relied on.
14. **`sw/biu_rebuild_wvec_freeze.py` and the `Vtb_v30_core` binary are NOT a
    controlled reference** and must not be cited as one until rebuilt from a
    clean tree (§12.8). The wvec corpus in use is the SILICON freeze.
15. **The wvec per-cycle digest is 63 / 88** (belongs with items 1-2 by
    importance, listed here because it is the same mechanism seen through a
    different instrument). The ACCESS COUNT is 88/88 and the whole-program
    bus-cycle total is exact to one cycle (16,048 vs 16,048), so the model gets
    the bus-cycle identity and count right on all 22 programs at all 4 wait
    vectors; 25 cells still differ somewhere in their per-cycle cadence digest.
    The B1 re-capture attached the per-access `parts` gradient (§14.3), so those
    25 are gradable — the instrument exists and was not spent on them.

### The v0.1 w0 non-exact rows, enumerated by family

166,400 reachable − 165,490 exact = **910**:

| family | cases | status |
|---|---|---|
| `F3AA F3A5 F3A4 F2AA F3AB` REP strings, `cx >= 2` | **907** | open item 4; w0-only, wait-axis answer attached, discriminating pair named |
| `0F12`, `C1.6`, `F7.4` | **3** | open item 5; one case each, an address on one cycle, unexamined |

Plus the 2,600 pin-event cases excluded by S9 (open item 7), which are not part
of the 166,400.

---

## (d) The `has_brkem` under-report — routed to the FUNCTIONAL campaign

**A finding of this campaign that belongs to the other one.** Recorded here,
and an erratum note is added to `docs/notes/ucsim_provenance.md` so the
functional ledger carries it too.

M9 (§14.1) established that PS3 on the pins is the emulation-mode bit. Reading
MD directly off the pins across all 3,242 banked captures shows that **the
`has_brkem` flag the fuzz banks carry UNDER-REPORTS 8080-mode excursions**: the
flag counts only the documented `0F FF` encoding, while the chip's PLA decodes a
wide spread of undefined `0F xx` second bytes as BRKEM as well — `0F F7`,
`0F FD`, `0F D3`, `0F 40`, `0F 73`, `0F 90`, `0F 65`, `0F 8D`, `0F 7C`, `0F C2`,
and more — each taking the NEXT byte as its vector. Measured consequence:
**189 of 3,242 banked seeds put MD = 1 on the pins at some point**, far more
than the flag reports.

**What this means for the functional campaign, stated as a scope of impact and
not as a re-scored gate:** any statistic keyed on `has_brkem` is understated.
That includes the `t30-brkem` bank's own membership, the F-B report's 76/85, and
the ucsim verdict's 8080-mode counts (including its statement that A30's bank A
is "unreached even with 8080 mode live", which was evaluated over a set that is
now known to be too small). **No functional gate result changes** — the
architectural comparisons are per-seed and do not depend on the flag — and
nothing in `docs/notes/ucsim_campaign_verdict_2026-08-01.md` is retracted here.
What is claimed is that the flag is the wrong instrument and the right one now
exists: **MD is observable on PS3 and any such statistic should be re-derived
from the pins.**

---

## (e) Cross-campaign synthesis

**What the two campaigns together establish.**

| | question | answer | bound |
|---|---|---|---|
| ucsim (functional) | is the dumped ROM + PLAs sufficient to build the architectural EU? | **YES**, with 41 numbered standing assumptions of which 6 are free choices | 7.34 M single-instruction cases on two parts, raw PSW included; 2,125/2,125 anchored program replays |
| ucsim-t (timing) | is the ROM + the measured law corpus sufficient to make it cycle-exact? | **YES to the measured bounds** — instruction windows, the full wait axis, boot, the frozen oracles, the law cards — and **PARTIALLY** at whole-program scale (62.2 % of a fresh random-wait tranche) | the gates of §(a); V5 FAILS and is reported failed |

Stated as one sentence: **the ROM plus the PLAs determine WHAT the machine
computes; the ROM plus a SMALL MECHANISM SET — fifteen entries, every one a
register, a threshold or a fixed cycle index — determine WHEN, to the bounds
this repo can measure.**

Two structural facts make the pair worth more than the sum:

1. **The architectural answer cannot drift between them.** The interpreter is
   one `template <class Bus> class CpuT` body; the functional and timed models
   are two instantiations of it, and the split was verified codegen-preserving
   with `nm -C` (§1.1). Every architectural mechanism this campaign found —
   `rb16`, the read-side byte swapper, the 16-bit shifter lanes, the one-pass
   BCD adder — rode the full 7.34 M sweep before it landed, and the corpus is
   byte-identical across the whole campaign.
2. **Both models are derived from the ROM, and the timing model is now
   silicon-referenced end to end.** Every law card that scores GREEN scores
   against a chip capture, not against the RTL. The one place the campaign
   leaned on an RTL reference (§11.9's wvec baseline), it found the reference
   half-vacuous and replaced it with a socket freeze — and retracted its own
   conclusions from it (§12.2).

**What the RTL-regeneration campaign would inherit.**

* **The mechanism ledger IS the RTL spec.** Fifteen mechanism entries plus the eval
  instant, each with its evidence pointer, its falsifier, and — for the ones
  that replaced something — the fitted construct it retired. A BIU written from
  §(b) is a T-state FSM, a status register, a 6-byte queue with two latency
  flops, one occupancy comparator sampled at cycle index 2, one landing-window
  pair keyed to T4, one 8-bit rotator, and the three flush rules. That is a
  small module.
* **Every `v30_eu.sv` / `v30_biu.sv` rail forest now has a documented mechanism
  replacement.** The two 2026-08-01 pilots showed it for INS (≈8 per-geometry
  qualifier families and ≈79 fitted rail constants → 4 global integers) and
  ENTER (6 FSM states, three fitted delays, two patch flags → the ROM row
  sequence plus 7 integers); this campaign extends it to the BIU: the per-form
  `S_RSV` reservation table → F2; the per-opcode "reservation starts at the
  final-pop cycle" rule → F2; the loop family's `dly<=3 blocked / dly>=4 free`
  cutoff → the SUSP row's position; mission-H's three wait laws → the eval
  instant; the enter pilot's grant law → the eval geometry; the MUL/DIV burn
  table → the OPR interlock; the resume `(phase, occ, fill)` truth table that
  BLOCKED the retired campaign → M4's single threshold plus M6/M7/M7b.
* **The retired campaign's own blocker is dissolved, not solved.** biu-rebuild
  was blocked on capturing `resume_slot[phase][occ][fill]` per wait level. That
  table does not exist in the answer: the resume decision is `occupancy +
  in-flight <= 4`, sampled at cycle index 2, with one landing window keyed to
  T4. The Stage-C sled was never needed.
* **A standing regression suite the RTL can be graded against without board
  time**: `timed_gate` (w0/w1/w3), `check_boot --timed`, `timed_scenario`,
  `timed_enter_replay`, `timed_ins_replay`, `timed_wvec_gate`,
  `timed_lawcards`, `timed_fuzz` (banked + the frozen victory tranche), plus
  four read-only instruments (`timed_probe`, `qcensus`/`q1census`, `wchain`,
  `q1diff`) that turn "N cases fail" into "one mechanism is missing here".
* **And the honest caveat it must carry**: the model is not cycle-exact over
  whole programs. An RTL regenerated from this ledger inherits Q2's unmeasured
  EU-raise clock, the four UNRESOLVED cards' missing stimuli, the 907-case w0
  REP family, and the untouched interrupt/8080 timing axes. It would be a better
  starting point than the current rail forest, not a finished core.

---

## (f) Gate ledger

Every gate, its number, and the commit that established it. Every number
below was REPRODUCED by a re-run immediately before the T5 commit (§15 of
the provenance ledger); reproduction is not passage — the victory tranche's
V5 clause is a registered FAILURE (§(a)) and reproduces as exactly that.

| stage | gate | number | commit |
|---|---|---|---|
| T0 | biu-rebuild retirement + B4 adjudication | `B4 = GO` RETRACTED; 988/988 re-derived as within-history repeatability only | `4576f28` |
| T0 | policy split codegen-preserving | v0.1 169,000/169,000 and v0.2 347,000/347,000 before AND after; wall time inside noise | `4576f28` |
| T0 | row emitter format-identical | `build_rows_sim` located the golden window in 4,000/4,000; rows exact 0/4,000, pre-stated | `4576f28` |
| T1 | the w0 timing core (grid, queue, scheduler, cadence) | ratchet 0 → 50,207 | `cdd380e` |
| T1 | the datapath, the flush, the two requesters | ratchet 50,207 → 155,011; 282/347 forms 100 % | `619c426` |
| T1 | one decode march, one OPR | ratchet 155,011 → 164,320; 319/347 forms | `2265c2d` … `81a9e35` |
| T1 | L1 oracle replay adapter lands | `timed_scenario` 6 PASS / 0 FAIL / 12 SKIP | `2265c2d` |
| T1 | `timed-boot` — the RESET entry point | boot replay 205/220 rows, loop period exact | `6095211` |
| T1 | T1 close-out | ratchet **165,481**; 325/347 forms; `kSegZero` ASSUMPTION → MEASURED (4,800 rows) | `0c43d9b` |
| T2a | the eval instant, and the wait axis | **w1 1,200/1,200, w3 1,200/1,200**; Milestone A MET; w0 unmoved at every step | `2aad3ce` |
| T2a | L2 replays land | INS `case250` 800/800 cells, rails 1,312/1,312; ENTER walk 154/154; `timed_scenario` 18 PASS / 0 FAIL / 9 SKIP | `9122072` |
| T2b | board pre-registration (P1-P5) | written and committed BEFORE board contact | `9448070` |
| T2b | P1 the SUSP conflict + P3 the HALT | **M6**; ratchet 165,481 → **165,490**; boot **220/220**; ENTER full 130 → 152/154, `halt_display` 0 → 154/154; S8/S9 removed | `a1e4c8a` |
| T2b | P2 the wvec corpus re-frozen against SILICON | 22 distinct digests in all four configs (TB baseline: 1 in two of them) | `a1e4c8a` |
| T2b | P4 `F3AA` / P5 the Arm-C sled | reading B confirmed at w0/w1/w3; sled frozen, bit-identical to the 2026-07-17 log | `a1e4c8a` |
| T2b | law cards, first scored on silicon | **1 GREEN / 6 RED / 4 UNRESOLVED** | `a1e4c8a` |
| T3 | fuzz-gate pre-registration | population, comparison policy and bar frozen from a 50-seed pilot BEFORE the first full run | `91184a8` |
| T3 | M7 / M7b / R-STALL | sled 3,768/3,769; wvec count 87/88; INS vs-chip rails **2,624/2,624**; law cards **3 GREEN / 4 RED / 4 UNRESOLVED** | `5d57104` |
| T3 | **the fuzz-bank cycle gate, run** | 0 hard failures; M1 44/1,702; closed taxonomy; the rig has no I/O (4,594/4,594 chip `IOR` rows are 0xFFFF) | `56fa002` |
| T4 | Q1 — **M8** / **M8a** | M3c RETRACTED; M1 44 → 136 | `fd997b6` |
| T4 | Q1b — **M8b** | M1 136 → **947 / 1,702 (55.6 %)**, median prefix fraction 1.000 | `224cd55` |
| T4 | **M9** — PS3 is the emulation-mode bit | PS3 family closed; §13.5's reading retracted; `has_brkem` under-report found | `f8bbbf3` |
| T4 | board pre-registration (B1, B2, B3) | written and committed BEFORE board contact | `224800e` |
| T4 | victory-tranche population freeze | 216 seeds, sha256 `08ec6dc4…`, committed BEFORE the first capture | `8b6ecd6` |
| T4 | B1 — the wvec corpus re-captured WITH its parts; **M10** | 88/88 cells reproduce their T2b digest exactly; law cards **7 GREEN / 0 RED / 4 UNRESOLVED**; wvec digest 0/88 → **63/88** | `0dc0e9a` |
| T4 | **B2 — THE VICTORY TRANCHE** | **V0-V4 PASS, V5 FAIL**; 117/188 = 62.2 % | `0dc0e9a` |
| T4 | A30 settled to a datapoint | 1 uncontaminated two-cycle INTA pair in emulation mode; favours bank B / fixed priority; n = 1 | `a515bf7` |
| T5 | every standing gate re-run; verdict, ROADMAP, README, ledger §15 | §15 | this commit |

---

## (g) Inconsistencies found while consolidating

Recorded rather than papered over. None of them changes a gate result.

1. **The "12 w0 tails" figure was stale by one closure.** §10.6 booked the w0
   tails as 12 cases — `0F39` (9) plus `0F12`, `C1.6`, `F7.4` (1 each) — and
   §11.13 restated "the 12 w0 tails and the 907-case REP residual are unchanged
   at 165,481". §12.1 then closed `0F39` (491 → 500/500, the +9 that took the
   ratchet to 165,490) but the 12 was never restated. **The w0 tails are 3, not
   12**, and 907 + 3 = 910 = 166,400 − 165,490 exactly. §(c) carries the
   corrected figure.
2. **The T3 fuzz "tails = 15" figure was superseded and never restated.** §13.5's
   taxonomy gives tails as 9 `addr` + 4 `data` + 2 `ube` = 15; §14.1's delta
   table gives 50 at T4 close. Both are correct for their stage — the family
   grows because seeds that used to stop at Q1 now reach further — but the
   T5-current figure is **50** (`data` 25, `addr` 21, `ube` 4), re-measured in
   this stage's gate run.
3. **The T3 harness prints `bs` where the ledger writes `Q2` plus
   `arbitration`.** `timed_fuzz`'s first-divergence census is by COLUMN family,
   so §14.1's "Q2 381" and §14.4's "Q2 42 + arbitration 10" are sub-splits of
   the tool's `bs=381` and `bs=52`. Both readings are in the ledger; neither
   says it is a sub-split. Stated here so a re-runner does not read a
   discrepancy into it.
4. **The R2-issue figure regressed at T2b and no section says so.** §11.6 scored
   `R2 issue 782/800` — full parity with the offline pilot; §12.7's gate line
   reads **780/800**, so **M6 cost two cells** and the T2b section does not
   mention it; §13.3 then reports `780 → 782` and calls it "= the offline pilot
   exactly", which reads as an improvement rather than as a restoration. The net
   over the campaign is zero and the current figure is **782/800**, whose
   residue is the pilot's own recorded grid-parity class, reproduced rather than
   fixed. A 2-cell regression that no ratchet covered is exactly the kind of
   movement a stage section should have named.
5. **`docs/notes/biu_blackbox_campaign.md` is untracked and is a governing
   statement.** §0.1 correctly names it "NOT an erratum: it is the current
   governing statement" — but it lives in the working tree unstaged, as a
   retired-campaign file. Anyone who cleans the tree loses the document that
   adjudicates B4. Flagged; not moved, because retired-campaign files stay
   unstaged by this stage's own rules.
6. **The biu-rebuild campaign memory file still asserts `B4 = GO`.** §0.1
   flagged it as the highest-priority stale artifact "since it is what a future
   session loads first", and it was not amended during this campaign. Still
   stale as of this commit. The governing statement is §0.1 of the timing
   ledger: **B4 closure is NOT ESTABLISHED**, and the campaign never needed it.
7. **The campaign plan was not in the repo until this stage.** The functional
   campaign's S4r lesson is that the plan must be committed in-repo
   (`docs/notes/ucsim_campaign_plan.md` exists for that reason). The ucsim-t
   plan lived only in `~/.claude/plans/`. Committed at T5 as
   `docs/notes/ucsim_t_campaign_plan.md`, verbatim.
8. **`sim/README.md`'s timed-mode section described T0.** It said "At T0 the
   rows are NOT yet timing-exact" and listed the T0 scaffolding as current, six
   stages after they were removed. Refreshed as part of this stage — the same
   defect the functional campaign found at its own close (§(g) item 8 there),
   recurring.
9. **`sw/timed_lawcards.py`'s C1/C3 explanation string is stale and contradicts
   its own numbers.** It still carries the T2b RED text — *"the PAUSE POPULATION
   is not reproduced — sim 43 vs chip 43 events at N=8, 30 vs 30 at N=12: the
   model still resumes far more eagerly than the part"* — beside a **GREEN**
   verdict and beside numbers that are now IDENTICAL (43 vs 43, 30 vs 30; they
   were 38/43 and 26/30 at T3, which is what the sentence was written for). The
   VERDICT is computed and correct; only the human-readable rationale is stale.
   Reported, not edited, because editing a gate tool's output text during the
   closure gate re-run would be a change to a green gate for cosmetic reasons.
10. **The INS whole-program agreement figure was never re-measured after T4 and
    has since closed completely.** §11.6 recorded 56,736 of 173,556 leading bus
    cycles agreeing in kind+address (55,936 also same-T1) and §13.3 improved it
    to 127,712 / 173,556 (127,584 same-T1); §14 never re-ran it. Re-measured in
    this stage's gate run, `timed_ins_replay --raw` reports **173,556 / 173,556
    leading accesses agreeing in kind and address, of which 173,556 also land
    on the same T1** across all 800 captures. The Q1 mechanisms (M8/M8a/M8b)
    closed it and the ledger did not notice. **This is an improvement the
    campaign under-reported**, and it is now recorded in §15.
11. **§13.3's headline is off by four.** The section is titled *"R-STALL — a
    LEAKED OPR hold, and it was worth **856** chip-exact INS rails"*, but its own
    table gives 1,772 → 2,624, which is **852**. 856 is the move from the T2b
    baseline (1,768), and M7 had already bought 4 of those before R-STALL landed.
    The correct attribution is **R-STALL = 852, M7 = 4**. §(b) uses 852.
12. **§14.4 attributes the 2.6 % figure to "T3 entry"; it is T3 CLOSE.** §13.5's
    own progression is T2b 17 → +R-STALL 32 → +the I/O constant 44, so
    44/1,702 = 2.6 % is where T3 ENDED (and T4 began); T3 ENTRY was
    17/1,702 = 1.0 %. The rhetorical point — 2.6 % → 62.2 % — is unaffected in
    magnitude and understated if anything.
13. **The `mod3_illegal` suite's status flipped twice without a controlled
   comparison.** §7.10 recorded `0/128 (0.0s)` and flagged it "unverified either
   way — confirm against a pre-T1 binary"; §8.7 found it needs `--residue
   stale-ea` and is 128/128, and added it to the standing set. The pre-T1
   comparison §7.10 asked for was never run. It does not matter — the flag
   explains the whole discrepancy and the suite is green — but the recorded
   falsifier was dropped rather than executed.

---

*Campaign closed 2026-08-02. Ledger: `docs/notes/ucsim_t_provenance.md`
(§0-§15). Plan as executed: `docs/notes/ucsim_t_campaign_plan.md` (verbatim
in-repo copy). Companion architectural verdict:
`docs/notes/ucsim_campaign_verdict_2026-08-01.md`. Branch `ucsim`; the retired
biu-rebuild campaign's disposition is `docs/notes/biu_rebuild_retirement_2026-08-01.md`.*

---

# ADDENDUM — 2026-08-02, post-closure: the REP re-entry mechanism

**This is an ADDENDUM.  §(a)-§(g) above are the REGISTERED record and are not
edited by it.  V0-V5 stand exactly as scored; V5 remains a registered FAILURE.**
The provenance for everything here is `docs/notes/ucsim_t_provenance.md` §16.

## What was open, and what closed

§(c) open item 4 was the REP string family at `cx >= 2` — 907 cases, the entire
non-tail w0 shortfall, w0-only, with a named discriminating pair and a
wait-axis answer attached.  It is **closed**, offline, with two mechanisms and
one correction, and without board contact (authorised, not used):

* **M10 — one request slot.**  The EU has a single bus-request register; a
  micro-row cannot hand a new request over while the previous one is still in
  it.  The register frees when the BUS TAKES the request — the accepted cycle's
  own T1 — and the blocked row issues on that clock.  A split word access is
  ONE request, taken once and freed at the LAST of its two cycles' T1.
* **M11 — the redirect bubble is not paid on a jump back by one row.**  §7.7's
  taken-micro-JMP bubble stands everywhere except a jump to the immediately
  preceding row, where no new ROM read is needed.  Scope is thin and stated as
  such: the corpus contains exactly one such site.
* **M5b unification.**  The OPR-shadow store now rotates on the ACCESS's own
  address, as `mem_write` already did — the chip drives one rotation on both
  halves of a split (`F3AB` case 0: `52B8` on all six cycles).

## The bars, RE-SCORED (the registered numbers, and today's)

| bar | registered (§(a), 2026-08-02) | re-scored, this addendum |
|---|---|---|
| v0.1 cycle rows at w0 | 165,490 / 166,400 (**99.45 %**) | **166,397 / 166,400 (99.998 %)** |
| the five REP forms at w0 | 1,593 / 2,500 | **2,500 / 2,500** |
| v0.1-w1 / -w3 | 1,200 / 1,200 each | unchanged |
| boot from RESET release | 220 / 220 | unchanged |
| ENTER waited tranche | 154 / 154 | unchanged |
| INS `case250` vs chip | 2,624 / 2,624 rails | unchanged |
| INS whole-program leading accesses | 173,556 / 173,556, same T1 | unchanged |
| wvec vs silicon — count / cycles / **digest** | 88/88, +0.0 %, **63 / 88** | 88/88, +0.0 %, **69 / 88** |
| law cards | 7 GREEN / 0 RED / 4 UNRESOLVED | unchanged |
| `timed_fuzz`, banked | **947 / 1,702 (55.6 %)** | **1,002 / 1,702 (58.9 %)** |
| `timed_fuzz`, prefix >= 0.5 / >= 0.9 | 1,192 / 950 | **1,221 / 1,005** |
| **THE VICTORY TRANCHE (V1)** | **117 / 188 (62.2 %)** | **117 / 188 (62.2 %)** |
| functional corpus | 7,341,126 / 7,341,126 | unchanged |

**The victory tranche did not move.**  That is the honest headline of this
addendum as much as the w0 number is.  The REP mechanism buys +55 seeds on the
banked population and **zero** on the frozen 188-seed tranche, because the
tranche's misses are not REP: 42 of its 71 are Q2, which this session
re-measured and did **not** land.  **V5 is still FAILED and V1 is still 62.2 %.**
Nothing in the registered victory record changes.

**Monotonicity.**  Of the 347 forms in the v0.1 suite, exactly five moved and
all five upward.  Arch (166,800), window-located (168,720), and every standing
gate are unchanged or better.

## Open items, updated

* **Item 4 (REP `cx >= 2`): CLOSED.**
* **Item 5 (the three tails `0F12` / `C1.6` / `F7.4`): still open.**  Checked
  against the new mechanism; they did not close for free and were not chased.
* **Item 1 (Q2, the redirect one clock late): still open, and RE-DIAGNOSED.**
  H1's prediction that the EU-raise clock would become mechanism-derived once
  the row cadence was bus-derived is **FALSIFIED**: with M10/M11 landed, the
  port half in its correct (T4-keyed, w0-neutral) expression still costs w1
  1,200 -> 1,143 and `timed_fuzz` 1,002 -> 796.  But the two populations agree
  on a rule the ledger had not stated: in Q2's 293 seeds AND in the 57 `EB` w1
  cases the port change breaks, **the chip shows the flush `E` on the same
  clock as the redirect fetch's status**.  Q2 is therefore a **redirect-commit**
  question, not a QS-port question; the port half is a symptom.  The directed
  branch-form factorial §14.2 asked for is still the capture that would close
  it.  Reverted; the model is left in the state that maximises the ratchet.

## One correction to the closed record

§(a) and §10.7 describe the REP residual as `cx >= 2`.  The census shows the
`cx = 1` band was also short — `F3A4` 60/119 and `F3A5` 73/123, 109 cases
inside the same 907 — a fact §10.7's table did not report because it tabulated
only the three STOS-family forms at `cx = 1`.  The total (907) was always
right; its decomposition in §10.7 was not.  Both bands are now exact.

---

# ADDENDUM — the post-closure trajectory, 2026-08-03

*Appended, not edited: nothing in §(a)-§(g) or in the R1 addendum above is
changed. Ten post-closure addenda have run since this document was registered
(ledger §16-§25). Every number below cites the ledger section it was measured
in.*

## Where the registered bars stand today

| bar, as registered in §(a) | at closure | **today** | § |
|---|---|---|---|
| **v0.1 cycle rows at w0** | 165,490 / 166,400 (99.45 % of reachable) | **168,997 / 169,000** — the 2,600-case pin-event exclusion **S9 no longer exists**, so the denominator is the whole suite | 16, **19**, 24.12, 25.7 |
| ...and its remaining cases | 12 tails, carried as an open BIU question | **3**, and **RE-CATEGORISED**: zero `tstate`, zero `busstat` — an EMISSION/HARNESS residue, not a model residue | 10.6, 24.11 |
| v0.1-w1 / -w3 | 2,400 / 2,400 | 2,400 / 2,400 | 25.7 |
| **the four `v0.1-w*evt` cells** | did not exist | **200 / 1,200 / 200 / 1,200** | 22.9, 24.7 |
| **whole-program, COMBINED** | 947 / 1,702 banked only | **1,980 / 2,710** (REGISTERED 1,272/1,702, EVT-unlocked 708/1,008) | 20.8, 24.12, 25.7 |
| wvec vs SILICON, per-cycle digest | 63 / 88 | **88 / 88** (count 88/88, cycles +0.0 %) | 17, 18 |
| law cards | 7 GREEN / 0 RED / 4 UNRESOLVED | **8 GREEN / 0 RED / 3 UNRESOLVED** — C2 closed on its own silicon and re-runnable board-free | 24.9 |
| INS `case250` vs chip | 2,624 / 2,624 | unchanged | 25.7 |
| boot / ENTER / scenario | 220 rows; 154/154 ×5; 18-0-9 | unchanged | 25.7 |
| **THE VICTORY TRANCHE (V5)** | **FAILED**, 117 / 188 | **STILL FAILED**, re-scored **154 / 188** on the same frozen tranche. V5's clause demanded whole-program exactness; 34 seeds still miss. **The registered verdict does not change.** | 24.12, 25.7 |
| functional corpus | 7,341,126 | unchanged, re-run in full before every commit | 25.7 |

## The mechanism ledger

*(Numbering below is the PROVENANCE LEDGER's, which §(b)'s table above does not
share — §(b) renumbered the closure set for this document and stops there.)*

**Ledger M1-M9 at closure (§15) → M1-M13 by addendum #3 (§18) → M1-M22 today**,
plus M2r and M5b throughout: +M10/M11 (§16), +M12 (§17), +M13 (§18),
+M14/M15/M16 (§19), +M17 (§20), +M18 (§21), +M19 (§22), +M20/M21 (§23),
**+M22 (§25)**. Two numbered mechanisms have been **retracted** across the whole
campaign — M3b (§8.4) and M3c (§9.1) — alongside §(b)'s four retracted fitted
constructs; and three post-closure READINGS were withdrawn before landing: the
post-write turnaround (§18), the acknowledge-gap hypothesis for the 44 waited
`ACK` seeds (§22.5), and the `d*` series as a 2-clock grid slot (§25.5).
§24.15's three "silicon in hand" mechanisms are all closed in §25; group A of
the open surface is now empty.

## What the rig gave back

Three instrument findings, each caught by the ledger's own discipline rather
than by a gate:

* **the STICKY CLOCK DIVIDER** (§21.1) — a rig-integrity hazard in the emission
  path; two readings retracted, fixes made in §22.6 and **actually exercised for
  the first time in §24.12** (`div_readback` said PINNED on every S13 probe);
* **`parse_result`'s PSW** (§23.1) — read from the wrong pass of the capture;
  it was never a chip question, and it is why `HLT.INT` at w1 produced 0 of 49
  goldens;
* **the BIASED `v0.1-w1evt` TRANCHE** (§23.1) — 706 draws rejected for a reason
  with no physics in it, selecting the sample on program length. Re-emitted
  unbiased in §24.7: **0 such rerolls, and the model still scores 1,200/1,200**,
  so §22's headline survives the removal of its own selection effect. The old
  tranche is preserved by rename and also scores 1,200/1,200.

## The honest shape of it

The w0 number moved by **+3,507**, and only **+907** of that is a mechanism —
R1's REP re-entry (§16). The other **+2,600** is the pin-event forms becoming
PRODUCIBLE at all (S9a, §19): the stimulus moved, not the model. The
whole-program number moved because a population was **UNLOCKED** (§20), and the
residue inside it has barely moved since — **1,950 → 1,980** across §20 to §25.
Every mechanism landed after closure was landed on a directed cell or a census,
and the last board session spent **5 min 43 s** of wall time against a
45-minute budget (§24.12). **V5 is still a registered FAILURE and this addendum
does not re-score it.**
