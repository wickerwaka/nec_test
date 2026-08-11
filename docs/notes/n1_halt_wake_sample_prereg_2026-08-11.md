# N-1 — THE HALT-WAKE RECOGNITION SAMPLE: PRE-REGISTRATION

    booked in     docs/notes/ie_pinfall_cell_results_2026-08-11.md §5 (N-1, N-2)
    branch        fuzz-v2-on-relanding, base `310457b2f7`
                  (+ `2aff7bc844`, the E1 qsf housekeeping — no RTL)
    scope         OFFLINE ONLY.  NO BOARD, NO FLASH.  Quartus IS in scope.
    committed     BEFORE the RTL is touched.  `git diff --stat <this commit>
                  -- hdl/rtl/` is empty at the moment this file lands.

**STANDING DESIGN PRINCIPLE (verbatim, user directive 2026-08-01).**
SIMPLICITY: this is 80's era hardware — nothing on the die is wasted.  Complex
or confusing observed behavior is likely simple systems interacting in ways not
yet understood.  A large fitted table, a many-cased rule, or a per-opcode
special case is a signal of misunderstanding, not a deliverable.

---

## 0. WHAT IS ALREADY MEASURED, AND WHAT IS NOT

The directed cell measured the LAW: a maskable request is taken iff the INT pin
is still high at `t_ei + (T* − 1)`, with `T*(w) = 3 + w` free-running and
`2 + w` at a `HLT`; the ucore is silicon EXACTLY on the free-running leg (876
cells, four waits, zero differing columns) and **one clock early at the HALT
wake** (`T*_ucore = 1 + w`).

What the cell did **not** say is WHICH TERM in `v30u_eu.sv` carries that clock.
This sitting found it with a temporary `$display` probe (added, run, reverted;
`hdl/` is byte-identical to `310457b2f7`), on the divergent cells themselves.

### 0.1 THE MECHANISM, AS PROBED

`sw/testdata/ie-pinfall/` cell `eihlt_w0:r-8:h9` — `t_ei = 170`, pin high on
rows 162…170, `fall = 171`, `t_hlt = 172`.  Probe trace, ucore, `tb_sys ret`:

    c=172  st=S_OPC_POP  int_p=1110  ie_p=0001  ipend=1  iil=0  eu_halt=1
    c=173  st=S_HALTED   int_p=1100  ie_p=0011  ipend=1  iil=0  eu_unhalt=1
    c=174  st=S_OPC_POP  int_p=1000  ie_p=0111  ipend=1  iil=1  irq_take=1  bnd_armed=1
    c=175  st=S_IRQ_D

`int_p[k]` is the pin at clock `c−1−k`.  At the wake's boundary clock `c=174`
**`int_p[2] = 0`** — the pin at 171 is already gone — so the take is **NOT**
carried by the boundary tap.  It is carried by the second disjunct of

```
wire irq_int_lvl = (int_p[2] ||
                    (intr_pending && (rep_kind == REP_NONE) && !ie_p[3])) &&
                   ie_p[2] && psw[FIE];
```

and `intr_pending` was armed at `c = 171` — the clock `ie_now` rises — by

```
if (ie_now && !ie_p_n[0] && int_p[0])
    intr_pending_n = 1'b1;
```

where `int_p[0]` at `c=171` is **the pin at clock 170**.

**So the ucore's HALT-wake threshold is one clock early because the arm's two
operands are not sampled on the same clock.**  `ie_now` is `psw_n[FIE]`, the IE
of clock `c`; `int_p[0]` is the pin of clock `c−1`.  The comment above the arm
already asserts they are *"the two signals sampled on the same preceding
clock"* — **that sentence is not true of the code it sits on**, and making it
true is the whole edit.

Two controls, both probed, both on the same instrument:

* `eihlt_w0:r-8:h10` (`fall = 172`) — at `c=174` `int_p[2] = 1`: the take is
  carried by the ORDINARY boundary tap and silicon agrees.  So the ucore's
  EXTRA clock is exactly and only the `intr_pending` disjunct.
* `eirun_w0:r-8:h10` / `h11` (`fall = 172` / `173`) — the free-running
  boundary lands at `c = 175`, where `ie_p[3] = 1` and the `!ie_p[3]` floor has
  **already killed `intr_pending`**.  The free-running leg's threshold is set
  by `int_p[2]` alone and **cannot move under this edit, by construction.**

That last control is why this is not wave-5's edit.  Wave-5 tried to separate
the populations with a recognition-LEVEL predicate on `eu_susp` and could not.
Here the separation is structural and pre-existing: the three-clock IE floor
`!ie_p[3]` already excludes the free-running population from the term being
changed.  No new gate, no new state, no HALT-specific case.

### 0.2 THE FITTING HAZARD, STATED BEFORE THE RUN

The mechanism was selected by probing the very cells the ie-pinfall replay leg
scores.  **The ie-pinfall replay is therefore a CONSISTENCY check, not
independent evidence, and is reported as one.**  The independent validation is
the disjoint population that did not select the edit: the 3,837-seed fz2 corpus
(§3) and the standing ladder (§4).  A closure on the 30 cells with any loss in
§3 is a REFUTATION, not a trade.

---

## 1. THE EDIT

ONE token, in `hdl/rtl/ucore/v30u_eu.sv`, in block (a) of the next-state
function:

```
-    if (ie_now && !ie_p_n[0] && int_p[0])
+    if (ie_now && !ie_p_n[0] && pin_int)
         intr_pending_n = 1'b1;
```

`pin_int` is the module's own INT pin input, already read combinationally in
this file (`assign flush_int_live = pin_int;` and the pipeline shift
`int_p_n = {int_p_n[2:0], pin_int};` twelve lines below the arm).  **NO FLOP IS
ADDED, no signal is created, no state is added, no opcode is named, and `HLT`
appears nowhere in the change.**

If the honest edit turns out to need a flop, this pre-registration is void and
a new one is written first.  (`9'h17A`–`9'h17D` are the unassigned SSA codes at
HEAD; `SS_VERSION` is `0x8D`, `SS_BIU_COUNT` 103, `SS_EU_COUNT` 122,
`SS_COUNT` 226.)

---

## 2. THE DIRECTED-CELL REPLAY LEG — THE CONSISTENCY CHECK

`python3 sw/ie_pinfall_cell.py core` then `score`.  `core` is fully offline
(`tb_sys ret`); `score` puts it beside the BANKED board table, which is
untouched silicon.

**The leg is validated before it is used.**  Re-run at `310457b2f7` on a
freshly built binary it reproduced the banked ucore column on **2,200 / 2,200
cells, every scored column AND the raw-word `sha256` identical** (the banked
`core/table.json` is byte-identical to the re-derived one).  The receipt id
differs (`5ea26900f6…` banked vs a fresh build) because the Verilator link is
not byte-reproducible; the FUNCTION is.

Baseline at HEAD, re-measured this sitting and identical to the banked score:

    leg      w | board T* | core T* | delta
    eirun  0-3 |  3/4/5/6 | 3/4/5/6 |  0 0 0 0
    eihlt  0-3 |  2/3/4/5 | 1/2/3/4 | +1+1+1+1

    board vs core, 57 distinct differing cells of 1,920 compared,
    in FIVE signature groups:

      G1  30  taken · n_inta · ack_off · ack_off_hlt   the take flip
      G2  10  ack_off · ack_off_hlt                    eihlt_w1 r=+6, core 1 EARLY
      G3   6  n_halt · halt_first · halt_off           hold=1, n_halt (2,0)
      G4   6  n_inta · ack_off · ack_off_hlt           eihlt_w2 r=+10, core 8 LATE
      G5   5  n_halt                                   hold=1, n_halt (4,2)

    columns with ZERO differences: wake_prefetch · rise · fall · t_ei ·
    anchor_t1 · n_rows  (0/1,920 each)

### 2.1 REGISTERED PREDICTIONS — the cell

| id | bar |
|---|---|
| **N1-A** | **G1 → 0.** All 30 take-flip cells close. `taken` differs on **0** cells. |
| **N1-B** | **`eirun` stays 876/876 identical** at all four waits, every column — the free-running leg does not move by so much as one cell. |
| **N1-C** | **`eihlt` T\* becomes 2/3/4/5** and `board T* − core T*` is **0 at all eight (leg, wait) strata**. |
| **N1-D** | **G2, G3, G4, G5 DO NOT MOVE — 27 cells, still differing, same columns.** They are rise-side or park-side; at their `rise_off > 0` the pin is LOW at the arm clock under either tap, so the edit cannot reach them. Total distinct differing cells **57 → 27**. |
| **N1-E** | `wake_prefetch`, `rise`, `fall`, `t_ei`, `anchor_t1`, `n_rows` stay **0 / 1,920**. |
| **N1-F** | the `ierun` / `iehlt` controls keep their §1 shape: no cell gains a `taken` where the board has none. |

**REGISTERED FALSIFIER (from the booking, unchanged): any silicon take at
`fall_off == T*_ucore` on a HALT leg.** Zero exist in 876 `eihlt` cells; if the
post-edit score shows the ucore now MISSING a take silicon makes, N-1 is
refuted and reverts.

---

## 3. THE DISJOINT POPULATION — THE EVIDENCE THAT COUNTS

`sw/fz2_replay.py`, `tb_sys ret`, scored against the banked FLASH #17 SOCKET
rows with the corpus's own column policy.

**⚠ THE FABRIC ERA GUARD WILL FAIL AFTER THE EDIT AND MUST BE OVERRIDDEN.**
`hdl/rtl/ucore/v30u_eu.sv` is a declared input of the FLASH #17 bitstream
receipt, so the guard is doing its job: it is saying the tree is no longer the
socket's tree. Every post-edit number below is taken with
`--no-fabric-era-guard` and **is said with that beside it**. The comparison
being made is *modified core vs banked silicon rows*, which is the point; what
it is NOT is a fabric measurement, and no fabric figure is claimed.

**THE BASELINE IS MEASURED AND COMMITTED WITH THIS FILE**
(`sw/testdata/fz2/_n1_base_all.json`, `_n1_base_named.json`, era guard **PASS**,
`tb_sys` receipt `f4472a1c27ab07e2…`, git `310457b2f7`):

    population 233 = the 113 F17 ledger failures + 120 deterministically
                     sampled fabric-PASS seeds (--sample-seed 20260810)
    fabric PASS 120 -> replay PASS 120,  fabric FAIL 113 -> replay FAIL 113
    AGREEMENT 233 / 233 = 100.0 %,  first_bad IDENTICAL on 113 / 113
    + the two named non-movers fz2c/404040 and fz2e/531000: replay PASS 2 / 2

An offline instrument that reproduces the fabric verdict AND the
first-divergence row on 233 of 233 is the strongest one this branch has, and it
is the one the seats are scored on.

### 3.1 REGISTERED PREDICTIONS — the corpus

| id | bar |
|---|---|
| **N1-1 (the seats)** | the three C2 HALT-wake seats **`fz2c/404071` · `fz2e/514044` · `fz2e/516001`** — F17 ledger `first_bad_row` **244 · 235 · 584**, `diverging_rows` **906/1204 · 1263/1587 · 1156/2611**, all three `family = C2 INTA-vectored delivery`, `arch_match = True`, `mech = REACHED` — **CLOSE: replay verdict PASS, `bad = 0`.** Registered at **3 of 3**. A partial close (1 or 2) is reported as a MISS, itemised, and the landing is re-argued, not restated. |
| **N1-2 (wave-5's falsifier)** | **`fz2c/404040` MUST STAY PASS, `bad = 0`.** This is the seed that refuted wave-5's `eu_susp` gate. |
| **N1-3 (the §64.1 four)** | **`fz2c/405002` · `fz2c/405013` · `fz2c/405072` · `fz2e/512056` MUST NOT MOVE** — same verdict FAIL and the SAME `first_bad_row` (527 · 1331 · 636 · 1475). The directed cell proved their mechanism is not HALT-adjacent (0 of 5 have a `BS = HALT` row in the 40 clocks before the divergence); an edit that moved them would be evidence the edit is not what it says it is. |
| **N1-4 (the other C2)** | `fz2e/531000` stays PASS; `fz2e/513019`, `fz2e/516065`, `fz2c/410047` may move in EITHER direction and are reported, not predicted. |
| **N1-5 (0 lost)** | over the whole 233 + 2: **0 seeds go PASS → FAIL**, and **0 seeds that stay FAIL get an EARLIER `first_bad_row`.** This is the hard bar. Any single loss REFUTES the landing and it reverts. |
| **N1-6 (the census)** | `python3 sw/fz2_immaterial.py falsify` **PASS**, and the 21 immaterial entries do not shift class (G8 `0 / 113`). ⚠ the ledger is a FABRIC artifact and does not move offline; this bar is that the CENSUS TOOLING stays self-consistent, not that the ledger was re-derived. |

---

## 4. THE STANDING LADDER

Cheapest first.  Every one of these is a MUST-NOT-REGRESS.

| gate | registered value |
|---|---|
| `gen_ucore_qsf --check` | PASS (green as of `2aff7bc844`; it was RED at `310457b2f7` for a reason that has nothing to do with this landing — see that commit) |
| `r7_lint` | PASS, **0 violations**, and **no new declared exception**. At HEAD: 20 nets / 1 carrier / 3 tainted / 51 `stop` sites. `pin_int` is not a `READY` carrier, so this gate is expected to be untouched. |
| `x1_retention build --leg ret` | REBUILT, receipt printed and quoted |
| `ss_lint` | exit 0, and **UNCHANGED**: `SS_VERSION` **0x8D**, `SS_BIU_COUNT` **103**, `SS_EU_COUNT` **122**, `SS_COUNT` **226**, census **214 architectural flops, 0 UNMAPPED, 2 whitelisted**. A retime of an existing sample adds no flop; if this moves, the edit is not what §1 says it is. |
| `test_artifact` | **45/45** |
| `check_core --core ucore --opcodes all --cases 0` | **169,000 / 169,000** |
| the four HLT sweeps (⚠ `--waits 1/2/3`) | **97 · 93 · 45 · 44 = 279/283**, and the four survivors stay the four family-D cells (`s10-w1` at `(10,busstat)` and `(11,pins)`; `s13-w2` at `(13,pins)`; `s13-w3` at `(15,pins)`); `HLT.RES` **49 · 49 · 25 · 25** PERFECT |
| `ulockstep --golden all --cases 50` | **17,350 / 17,350** |
| **G6, `quartus_gate.py`, TWO DRAWS, BOTH QUOTED** | Fmax **≥ 32.0 MHz** is the standing bar; **this sitting registers a HARD STOP at 38.0 MHz** — a draw below 38.0 stops the landing and is reported as registered. Predicted band **38.4 – 42.0 MHz** (this branch's CONTROL draws: 39.16 · 39.37 · 39.47 · 39.63 · 39.81 · 40.11). Worst setup **> 0**, TNS **0.000 setup AND hold on every domain**, 0 errors, 0 latches, 0 `lpm_divide`. **One green build is not closure** (`standing_gates.md` §A). |

**G6 prediction, stated as a prediction.** The edit replaces one register bit
(`int_p[0]`) with one input pin (`pin_int`) in a two-term AND that already
feeds a register `D` pin. `pin_int` already fans out to `int_p_n`'s shift and
to `flush_int_live` on this same tree, so no new pin-to-EU route is created and
no combinational depth is added. **Predicted: within noise of the control band,
no structural change.** If G6 lands below 38.0, the landing STOPS regardless of
how green everything above it is — that is what the 8F ghost FEED's 15.3 MHz
bought this project.

---

## 5. N-2 — ASSESSED, AND WHY IT IS NOT LANDED HERE

N-2 is the 11 cells of groups **G3 + G5**: silicon announces a HALT the ucore
does not, on a **one-clock** request at the park (`n_halt` `(2,0)` ×6 and
`(4,2)` ×5).

**IT IS NOT THE SAME PREDICATE, AND THE ARGUMENT IS STRUCTURAL RATHER THAN
NUMERICAL.**  Every one of the 11 sits at `rise_off ∈ {+2,+4,+6,+8,+10,+12}` —
the pin arrives AFTER `t_ei`, in the park window.  N-1's arm fires at the clock
`ie_now` rises, one clock after `t_ei`; at that clock the pin is **LOW on all
11 cells under either tap**.  So the edit in §1 **cannot reach them**, in
either direction.  Three of the 11 are on `iehlt`, where IE never rises at all
and the arm therefore never fires — which is the same statement from the other
side, and is why the results document calls N-2 IE-independent.

They are also a DIFFERENT observable: N-1 moves `taken`, N-2 moves `n_halt`
with `taken = False` on both engines in all 11.

**N-2 IS THEREFORE BOOKED, NOT LANDED**, and it is registered here as a
NON-MOVER (bar **N1-D**): if the §1 edit moves any of the 11, the mechanism
account in §0.1 is wrong and the landing is re-argued from the probe up.

*What N-2 needs, booked for its successor:* it is a HALT-ANNOUNCEMENT question
in the F43/F54 zone (`hlt_wake_disp` / `eu_unhalt_disp`), not a recognition
question, and its stimulus axis is one clock wide — the cell swept `hold` and
only `hold = 1` fires it.  Its falsifier is unchanged from the booking: **any
`hold ≥ 2` cell with an `n_halt` difference.**  None exists in 2,200 cells.  A
successor should widen the park-window stimulus first, because 11 cells at one
stimulus width is not enough to name a mechanism with, and a rule fitted to
them would be exactly the fitted table the standing principle forbids.

---

## 6. DISPOSITION IF REFUTED

If **N1-A** misses, or **N1-5** loses a single seed, or G6 draws below 38.0:
the edit is REVERTED and N-1 is re-booked wave-5 style — with the block
characterised, the mechanism NOT condemned, and the probe trace of §0.1
retained, because that trace is a true measurement of the ucore whatever
happens to the edit built on it.

Nothing in this sitting touches the board, and `flash_log.jsonl` must have the
same entry count before and after.
