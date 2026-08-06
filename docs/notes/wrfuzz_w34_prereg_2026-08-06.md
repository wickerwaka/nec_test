# wrfuzz W3.4 — PRE-REGISTRATION: **the P1 GRANT LAW**

**Task #43.  Written and committed BEFORE the first line of the sitting's
measurement was run** — including the OFFLINE legs, which read RETAINED silicon
and are therefore measurements in the full sense (`wrfuzz_provenance.md` §6.6's
own erratum: *"an offline leg that reads RETAINED silicon is a board-free
measurement and must be pre-registered before it is run"*).  Branch `ucsim`,
tree `40800bf6f0`.

> **Standing principle.**  *"A guiding principal here needs to be simplicity.
> This is 80's era hardware, they aren't wasting silicon on anything that isn't
> necessary.  Complex or confusing behavior that we see is likely to be simple
> systems interacting in ways you do not fully understand yet."*

New instrument: **`sw/w34_grant.py`**.

---

## §0 THE QUESTION, AND WHY IT IS NOW A GRANT QUESTION

Three sittings narrowed it:

* **§5.3 (W3.2)** — P1 is 23 `wr1` seeds on which the ENGINE runs one extra
  `CODE` fetch at the chip's last `CODE` address **+ 2** and the CHIP does not.
  Three exact numbers, wait-independent: the chip's vector-read T1 is
  **previous bus cycle's T1 + 12**; the engine's is **its own extra fetch's
  T1 + 10**; `delta = (previous cycle length) − 2`.  **The chip declines a
  fetch it could legally make.**
* **§5.4 / §5.4a** — three suspend forms were tried and NONE was taken; the
  bound test refuted *"a hold beginning at the recognition boundary"*.
* **§6.6 (W3.3)** — on 563 DIRECTED vector-1 entries where both engines are
  cycle-exact, `vec − take` is **9 on 500 / 10 on 63**, and the chip runs a
  `CODE` prefetch INSIDE the take→vector window on **121 of 563**.  The take
  does NOT suspend the prefetcher.  §6.6's closing sentence sets this sitting's
  question verbatim: **"P1 is a GRANT question at the contested slot, not a
  recognition question."**

So the discriminating variable between **granted (121 directed)** and
**declined (23 P1)** is the law.  Expect ONE predicate, and expect it to be a
settled law evaluated at a clock, not new machinery.

---

## §1 THE POPULATIONS, NAMED BEFORE THEY ARE MEASURED

| # | population | n | source | role |
|---|---|---|---|---|
| **P** | the P1 seeds — chip DECLINES, engine GRANTS | **23** (`ucore`; `sim`'s 21 are a strict subset) | `w32_part_ucore.json`, `cls = SAME_BOUNDARY ∧ geom.n_ins = 1` | the class to be explained |
| **G** | directed entries where the chip GRANTED a `CODE` in the window | **121** | `sw/testdata/sm3-s24tfcell/`, 20 (sled, wait) cells | the positive control |
| **N** | directed entries with NO `CODE` in the window | **442** | same | must be SPLIT into *no-opportunity* and *declined* |
| **S** | the `vec − take` split | 9 ×500 / 10 ×63 | same | its own selector may be the same variable |

**⚠ THESE ARE ALL THE POPULATIONS THERE ARE, AND THAT IS REGISTERED HERE.**
Any predicate found on them is SELECTED on them.  Per `CLAUDE.md` §64.1 a
landing's authorization needs either a new cell or a population not used to
select — see §4.

---

## §2 THE CANDIDATE PREDICATES, WITH PER-CANDIDATE PREDICTIONS

All quantities are chip-side unless the row says otherwise.  `take` for the
directed cells is the engine's take clock on a capture where the engine is
cycle-exact (§6.6's instrument, unchanged).  For **P** the chip's take is NOT
directly observable and is taken two ways, both reported: `take_vec9 :=
chip_vec − 9` (§6.6's measured constant) and `take_eng :=` the engine's own
`brktrace` take.  **If those two disagree on P, that disagreement is itself a
finding and is reported as G-D.**

| id | predicate | mechanism it names | prediction on **G** (121) | prediction on **P** (23) | prediction on **N** (442) |
|---|---|---|---|---|---|
| **G-A** | **ROOM — M4 at the take.**  Grant ⟺ `occ + inflight ≤ 4` evaluated at the take clock | already-landed M4 (`ucore_provenance.md` §63.6 / M4), evaluated at a clock the engines evaluate elsewhere | ≤ 4 on **121 / 121** | **≥ 5 on 23 / 23** chip-side, and **≤ 4** engine-side (the engine grants) | ≥ 5 wherever there is no grant |
| **G-B** | **ARM-BEFORE-TAKE.**  The prefetcher's launch decision is made at the clock the previous bus cycle RELEASES the bus (its T4, or T4 + 1).  A decision clock **strictly before** the take proceeds; **at or after** the take it does not | one gate: the take masks a NEW request but does not cancel a latched one — the 80s-silicon shape of a `pf_req` flop | decision clock **< take** on 121 / 121 | decision clock **≥ take** on 23 / 23 | mixed: no-room OR decision ≥ take |
| **G-C** | **PHASE.**  The separating variable is `take − prev_T1` (or `take − prev_end`), a fixed phase inside the previous bus cycle | H3-B's old territory | one contiguous phase band | a DISJOINT phase band | — |
| **G-D** | **THE TAKE IS MISPLACED ON P.**  `take_eng ≠ take_vec9` on P, by `prev_len − 2` | P1 is a recognition-clock question after all and §6.6's T-A does not transfer to it | (n/a — exact there by construction) | `take_eng − take_vec9 = prev_len − 2` on 23 / 23 | — |
| **G-E** | **ENGINE MIS-EVALUATION.**  The engine's OWN `occ + inflight` at the take differs from the chip's reconstructed value at the same clock | an already-landed law evaluated on a wrong operand — **a BUG, not a new mechanism** | equal | **differs by ≥ 1** on 23 / 23 | — |

**Registered null.**  If **no** predicate separates **G** from **P** with zero
exceptions, the answer is NOT forced into one: §5.6b's precedent
(*"the `+2` mode's discriminator is NOT the surface geometry and this sitting
does not have it"*) is followed and the sitting closes on the honest partition
plus the directed-cell spec.

---

## §3 THE OFFLINE LEG — WHAT IS COMPUTED, PER ENTRY

`sw/w34_grant.py`, for every entry of **P**, **G**, **N**:

1. `take` (both readings on **P**), `vec`, `vec − take`.
2. The previous bus cycle: status, address, T1, active length, T4 row, end.
3. `occ` and `inflight` chip-side at each of `take − 2 … vec`, by §63.6's rule
   (`sm3_h3_cell.occ_at`: bytes delivered by `CODE` cycles completed since the
   last `QS = E`, minus the `QS ∈ {F,S}` pops since), reported as a trajectory,
   not as a single number.
4. The same engine-side, from the engine's own rows.
5. `room`: the idle clocks between the previous cycle's T4 and `vec` — the
   window in which a fetch would have to fit.  **`N` is split by this**: an
   entry with `room` too small for a fetch is *no-opportunity*, not *declined*.
6. Whether a `CODE` T1 falls in `(take, vec)`; its address relative to the
   previous `CODE`.

**INTEGRITY BARS (these ARE bars, and they can fail):**

* **I-1** every directed cell used must re-report `exact = YES`; an entry on a
  non-exact capture is EXCLUDED and counted, never scored.
* **I-2** the two engine legs (`sim`, `ucore`) must agree cell for cell on
  every chip-side quantity — they read the same silicon and a disagreement is
  an instrument defect.
* **I-3** the totals must reproduce §6.6's published 500/63 and 442/121
  exactly.  A different total means the instrument moved and the sitting stops
  to find out why.
* **I-4** every distribution is reported whatever it is, including the ones
  that refute a candidate of mine.

---

## §4 THE LANDING, AND WHAT AUTHORIZES IT

Branches, decided before the run:

1. **If the separating predicate is G-E** (an already-landed law evaluated on a
   wrong operand — a BUG), the fix's validation is the STANDING CORPUS: the bug
   was not selected on `wr1`, the corpus is disjoint from the selection in the
   sense §64.1 requires, and B-1…B-8 below are the bars.
2. **If the predicate is G-A / G-B / G-C** (a mechanism selected on P ∪ G ∪ N,
   i.e. on every population there is), the landing is authorized ONLY with a
   disjoint validation.  The registered disjoint population is the **`sm3-s24tfcell`
   `iret` / `iretnotf` / `notfnone` / `notfclc` / `storm` variants** — retained
   silicon, 10 (sled, wait) cells NOT used by §6.6's `popf*` measurement and NOT
   used to select — plus, if those under-determine, a directed board cell
   (socket only, `use_core=False`, pre-registered predictions committed before
   contact, `div_guard` pinned, `board_idle` after).
3. **If nothing separates**, NOTHING IS LANDED and the sitting closes on the
   partition + spec.  The victory sitting proceeds regardless.

### THE BARS FOR ANY LANDING

| bar | statement |
|---|---|
| **B-1** | **P's 23 lose the inserted fetch**, zero exceptions, on the engine the landing is taken in |
| **B-2** | **NO LOSS on any population, either engine** — the bar that refused v1/v2/v3 at W3.2.  `wr1` baseline `sim` **73 / 184**, `ucore` **77 / 184** |
| **B-3** | ratchets MONOTONE.  `sim` REGISTERED **1,339** / EVT **799** / COMBINED **2,138**; `ucore` **1,559 / 934 / 2,493**.  Re-measured on this tree BEFORE the first edit |
| **B-4** | the W3.1 shadow law's populations unmoved: 75/75 grace-≥1 inside the class, 1,288/1,288 grace-0 outside, DIFF_BOUNDARY 7 on both engines |
| **B-5** | the SM trap cells unmoved: `sm3_tf_floor_cell score` floor **3** / 121,890 rows / 0 row-diffs (`sim`), depth **4** / 121,860 / 0 (`ucore`), EXACT on all 30 |
| **B-6** | the must-not-move ladder of §4.6a, both engines, as written there |
| **B-7** | `ss_lint` exit 0 and `ulockstep --golden all --cases 50` 17,350/17,350 if any RTL file changes |
| **B-8** | **G6** if and only if an RTL leg lands |

**B-5 / B-6 / B-8 are VACUOUS if no engine file changes, and will be reported
as vacuous, never as green.**

---

## §5 SCOPE, DECIDED BEFORE THE RUN

* **The victory reserve (`k ≥ 300000`) is NOT touched.**
* **NO FLASHING.**  The board carries FLASH #10; any `ucore` figure this
  sitting produces is a Verilator figure.
* Board contact is authorized (socket only) and taken ONLY if §3's offline leg
  under-determines the predicate.  If taken: single-writer probe first,
  `use_core=False` explicit, `div_guard()` pinned and recorded, full per-clock
  rows + `SHA256SUMS` retained, `board_idle()` after and verified.
* No memory file is touched and Codex is not launched.
* `mc1/721`, `mc2/584`, the `MEMW`→4-idle→`MEMW` mode (§5.6a), the `CODE`→gap+2
  mode (§5.6b) and the 8080/BRKEM family are NOT opened.
