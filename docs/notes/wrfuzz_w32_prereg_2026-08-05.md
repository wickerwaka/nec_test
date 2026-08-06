# wrfuzz W3.2 — PRE-REGISTRATION: the trap ENTRY'S LAUNCH, and the suspend it never earns

**Task #41.  Written and committed BEFORE any engine file was edited and
before any post-landing figure was measured.**  Branch `ucsim`, tree
`4bd041117e`.  Board-free so far; no board has been contacted this sitting.

> **Standing principle.**  *"A guiding principal here needs to be simplicity.
> This is 80's era hardware, they aren't wasting silicon on anything that isn't
> necessary.  Complex or confusing behavior that we see is likely to be simple
> systems interacting in ways you do not fully understand yet."*

`wrfuzz_provenance.md` §4.7 booked the second half of the trap-entry family and
named its candidate: *the prefetcher SUSPEND, gated on `irq_take` in the RTL and
on `maskable() && ie_rise_…` in the model, which the trap never satisfies.*
This document states what the analysis measured, what is predicted, and what
would refute it.  New instrument: **`sw/w32_launch.py`**.

---

## §1 THE POPULATION, RE-PARTITIONED ON THIS TREE

W3.1's partition was measured on the PRE-shadow tree.  The shadow landing moved
28 `ucore` seeds out of DIFF_BOUNDARY, and **what was underneath some of them is
this family**, so the class is BIGGER than §4.7's 32, not smaller.  Measured on
`4bd041117e` over the 380 retained `wr1` captures (184 scored, 196 `OPEN_BUS`):

| class | `sim` | `ucore` |
|---|---|---|
| **SAME_BOUNDARY** | **50** | **45** |
| DIFF_BOUNDARY | 7 | 7 |
| NO_ENTRY_DIFF | 126 | 118 |
| COUNT_DIFF | 0 | 12 |
| UNREADABLE | 1 | 2 |

⚠ **This is the same partition key W3.1 registered** — entries paired in order,
first difference in (vector, pushed IP, T1 row) — with ONE instrument change,
written down before it was used: an odd-SP (byte-split) frame publishes no
readable IP, and W3.1's classifier declared the whole capture UNREADABLE the
moment *any* paired entry was one.  `w32_launch` declares it unreadable only if
that pair actually DIFFERS.  Consequence, stated rather than smoothed:
`UNREADABLE` falls and `NO_ENTRY_DIFF` / `COUNT_DIFF` rise.  **`COUNT_DIFF` is
new and is NOT a mechanism claim** — it is "the two sides agree on every paired
entry and one of them has more", which is a window-edge property.

---

## §2 THE GEOMETRY — measured from the two BUS-CYCLE STREAMS, aligned from row 0

`w32_launch` does not open a window.  It aligns the two sides' bus cycles index
by index and reports the FIRST index at which they part, as either a cycle one
side ran and the other did not (`CYCLE`) or the same cycle at a different row
(`SHIFT`).  Inside SAME_BOUNDARY the family splits in two, and the split is the
same on both engines:

| sub-family | `sim` | `ucore` | shape |
|---|---|---|---|
| **P1 — the engine runs ONE EXTRA `CODE` fetch** | **21** | **23** | `delta` +4 / +5 / +6 |
| **P2 — same cycles, engine 2 clocks late** | 16 | 20 | `delta` **+2**, all of them |
| everything else | 13 | 2 | |

### §2.1 P1's invariant — **and it is three numbers, all exact, on both engines**

| measured | `sim` | `ucore` |
|---|---|---|
| the engine's extra cycle is a `CODE` fetch of the **next word** (chip's last `CODE` address **+ 2**) | **21 / 21** | **23 / 23** |
| **the CHIP's vector-read T1 is exactly 12 clocks after the T1 of the last bus cycle before it** | **21 / 21** | **23 / 23** |
| the ENGINE's vector-read T1 is exactly **10** clocks after the T1 of its own extra fetch | **21 / 21** | **23 / 23** |

**The 12 is wait-independent** — it holds at `fix1`, `fix2`, `fix3`, `wrand1`,
`wrand2`, `wrand3`, `wrand7` and all four `wvec` shapes — so on the chip the
entry's first read is *not* waiting for a bus: it goes out the clock the
microcode asks for it, and the prefetcher is not in its way.  `delta` follows
arithmetically: the engine's extra fetch is back-to-back with the previous one,
so `delta = (prev cycle length) − 2`, which is `+4` at one wait, `+5` at two,
`+6` at three.  **Nothing here is fitted; the chip supplies 12 and the engine
supplies its own extra cycle.**

The `+ 2` address is the second half of the same statement: the fetch the chip
declines is a LEGAL one — the queue has room and the next word is there for the
taking.  **The chip declines a fetch it could make.**

### §2.2 P2's invariant — a 2-clock handoff, and it is *not* the same measurement

| measured | `sim` | `ucore` |
|---|---|---|
| the CHIP launches the contested cycle **back-to-back** with the previous one (`vecT1 − prevT1 == prev cycle length`) | **16 / 16** | **20 / 20** |
| the ENGINE launches it **exactly 2 clocks later** | **16 / 16** | **20 / 20** |
| the chip's previous cycle is a `CODE` fetch | **16 / 16** | **20 / 20** |

So P2 is not a stolen slot: both sides run the same cycles.  It is that the
engine cannot start the entry's first read in the clock that follows a
completing fetch, and the chip can.

---

## §3 THE MECHANISM — **THE SUSPEND BELONGS TO THE RECOGNITION, NOT TO THE FLOOR IT PAID**

Both engines already suspend the prefetcher for the *maskable* recognition, and
both gate that suspend on the IE floor:

* `hdl/rtl/ucore/v30u_eu.sv`:
  `assign eu_bnd_post = irq_take && !intr_pending && !ie_p[3] && !irq_nmi_lvl;`
  consumed by `v30u_biu.sv:1275` as `if (eu_bnd_take && eu_bnd_post) suspended = 1;`
* `sim/biu_timed.cpp:boundary_no_pop()`:
  `if (post_redirect && live) { wait_ie_floor(); susp(); }` with
  `live = maskable() && ie_rise_ >= 0 && clk_ < ie_rise_ + kIeFloor`.

`bnd_take` is `irq_take || brk_take` since §86, and `at_fire_boundary()` is
`ext_fire() || brk_take_`: **ONE recognition path.**  The suspend is the only
thing on that path that still asks WHICH recognition it is.

> **THE LAW.**  A recognition taken at a retire boundary holds the prefetcher
> off from its take until the entry's own flush.  The BRK/TF trap is such a
> recognition.  The IE floor is what the *maskable* recognition waits for
> before it takes; it is not what the suspend is about.

That is **an asymmetry removed, not machinery added**: one term in each engine,
no flop, no table, no per-opcode case.

### §3.1 THE LANDINGS, named before they are written

* **`sim/biu_timed.cpp`** — `boundary_no_pop` learns whether the boundary is a
  trap take, and the floor wait stays where it is:
  `if (post_redirect && (live || brk)) { if (live) wait_ie_floor(); susp(); }`
* **`hdl/rtl/ucore/v30u_eu.sv`** —
  `assign eu_bnd_post = ((irq_take && !ie_p[3] && !irq_nmi_lvl) || brk_take) && !intr_pending;`

**`sim/` FIRST** (`CLAUDE.md` §64.1): the family is model-shared — P1 is 21 of
`sim`'s SAME_BOUNDARY and 23 of the `ucore`'s, and 21 of the 23 are the SAME
SEEDS.

---

## §4 WHAT IS PREDICTED — registered before the landing

### §4.1 P1, the primary set — **23 named seeds**

`sim`'s 21 are a strict subset of the `ucore`'s 23 (the `ucore` adds `203018`
and `203121`):

```
201055 202058 203018 203060 203121 204007 204092 204143 205000 205133
205144 206034 206087 206097 207106 210011 210038 210114 210130 211068
212046 212091 212122
```

### §4.2 P2, the secondary set — **20 named seeds** (`sim`'s 16 are a subset)

```
200059 200100 200103 201010 201070 202005 202054 204066 205092 205126
206062 207071 207098 209039 212031 212062 217001 218010 220036 220065
```

### §4.3 THE BARS

* **B-1 — THE MECHANISM BAR (P1).**  On **each** of the 23, on the engine that
  put it in P1, the seed's SAME_BOUNDARY *insert* must be gone after the
  landing: either the seed leaves SAME_BOUNDARY (it becomes `NO_ENTRY_DIFF` /
  `EXACT`) or its `n_ins` is **0**.  **Zero exceptions permitted**, checked
  seed by seed.
  ⚠ *The bar is written on the CONTESTED ENTRY, not on the engine's global
  first divergence.*  W3.1's A-1 was written on the latter and 6 seeds missed
  it because a DIFFERENT, upstream divergence owned that coordinate; the bar
  that matches the claim is registered here instead of repeating that error.
* **B-2 — P2 IS A SECONDARY PREDICTION AND IS REPORTED AS REGISTERED.**  The
  candidate says the same suspend removes P2's 2 clocks (the prefetch grant the
  EU's request must take back never happens).  **Registered prediction: ≥ 15 of
  the `ucore`'s 20 lose the +2.**  It is NOT a condition of the landing; a miss
  is reported and P2 stays booked as its own family.
* **B-3 — NO LOSS.**  No seed EXACT before may be non-EXACT after, on **any**
  population, for **either** engine — the 380 `wr1` captures, the standing
  3,242-seed bank and the 188-seed `b2-tranche` — and no seed's first
  divergence may move EARLIER.  Checked seed by seed against a baseline
  measured on THIS tree before the edit.
* **B-4 — THE RATCHETS MAY ONLY GO UP.**  From `standing_gates.md`, current:
  `timed_fuzz --core sim --evt-replay` REGISTERED **≥ 1,339**, EVT **≥ 799**,
  COMBINED **≥ 2,138**, `--seeddir b2-tranche` **≥ 161**;
  `--core ucore --evt-replay` REGISTERED **≥ 1,559**, EVT **≥ 934**,
  COMBINED **≥ 2,493**, `--seeddir b2-tranche` **≥ 181**.
  The `wr1` survey baseline: `sim` **≥ 73 / 184**, `ucore` **≥ 77 / 184**
  (survey-baseline movement, NOT a ratchet — `wrfuzz_provenance.md` §4.9).
* **B-5 — THE SM TRAP CELLS MUST NOT MOVE, AT ALL.**
  `sm3_tf_floor_cell.py score --core sim` **121,890 rows, 0 row-diffs, 30/30**,
  floor 3; `--core ucore` **121,860 rows, 0 row-diffs, 30/30**, floor 4;
  W-0a **0 / 18**, W-1 **30/30**, W-2 **22/22**, W-3, W-4 **0·0**, W-5 **90/90**.
* **B-6 — THE SHADOW LAW'S POPULATIONS MUST NOT MOVE.**  `sw/w31_shadow.py`
  re-run: **75 / 75** grace-≥1 pairs inside the class and **1,288 / 1,288**
  grace-0 pairs outside it, over 1,363 ruled pairs.  *(This leg is engine-free
  — it reads chip rows and the generator's layout only — so it CANNOT move; it
  is registered as the control that says the instrument still says it.)*
  And the DIFF_BOUNDARY count must not RISE above 7 on either engine.
* **B-7 — THE MUST-NOT-MOVE LADDER**, both engines, at their registered values
  (`wrfuzz_provenance.md` §4.6a): `make -C sim test`, `pla3_check` 21,
  `ucsim_check v0.1` 169,000, `mod3_illegal --residue stale-ea` 128,
  `timed_gate v0.1 --forms all` 169,000 / `v0.1-w1` / `-w3` 1,200 each, the four
  HLT sweeps **97 + 95 + 46 + 45 = 283**, `check_boot --timed 220`,
  `timed_scenario` 18/0/9, `timed_enter_replay` 154 ×5,
  `timed_ins_replay --raw` 1,312 and 2,624, `timed_wvec_gate` 88/88 +0.0 %,
  `timed_lawcards` 8 GREEN / 0 RED / 3 UNRESOLVED;
  `check_core --opcodes all --cases 0` **169,000**, `v0.1-w1 --waits 1` /
  `-w3 --waits 3` **1,200** each, `EB --waits 1` **200**, the four `evt` cells
  **200 / 1,200 / 200 / 1,200**, `w1evt-biased` **1,200**, `f4a_boundary`
  **160**, `f0lock_tranche` **400**, the four `ucore` HLT sweeps
  **97 + 93 + 45 + 44 = 279**, `timed_wvec_gate --core ucore` 88/88,
  `timed_enter_replay --core ucore` 154 ×5,
  `timed_ins_replay --core ucore --raw` 1,312 / 2,624, `check_ab_sim --core
  ucore` MATCH over 187 rows, `ulockstep --golden all --cases 50` **17,350**,
  `ss_lint` exit 0 with **no `SS_VERSION` bump** (the landing is a WIRE).
* **B-8 — G6**, the CONTROL/DEFAULT Quartus build, if and only if the RTL leg
  lands: `gen_ucore_qsf --check` PASS, 0 compile errors, `divclk` Fmax
  **≥ 32 MHz**, worst setup > 0, TNS **0.000** setup and hold on every domain.

### §4.4 THE FALSIFIERS

1. **The `evt` / INT column.**  The suspend is added to a wire the MASKABLE
   recognition also reads (`eu_bnd_post`), so an `INT` / `NMI` / `EVT`
   regression means the shape is wrong and the landing reverts.  Specifically:
   the four `evt` cells and `w1evt-biased` must stay **200 / 1,200 / 200 /
   1,200 / 1,200** and the bank's EVT column must not fall.
2. **A `CODE` fetch the chip DOES run and the engine now does not.**  The
   suspend is `until the entry's own flush`; if it is too long the engine will
   go quiet where the chip prefetches.  Registered signature:
   `bs CODE!=PASV` appearing as a NEW first-divergence family, and B-3 catches
   it as a loss.
3. **The trap's suspend is really the IE floor's after all.**  If the landing
   closes P1 only on seeds whose PSW.IE happened to have just risen, the term
   is a coincidence.  Checked: P1's 23 span `fix1..fix3`, four `wrand` levels
   and all four `wvec` shapes, and the §2.1 invariant is wait-independent.

---

## §5 WHAT THIS SITTING WILL NOT DO

* **The `PIN` five (survey queue item #3 / W3.3) is NOT opened.**
* **The victory reserve (`k >= 300000`) is NOT touched.**
* No memory file is touched and Codex is not launched.
* A directed board cell is **specified in §6** and run only if the banked
  corpus does not decide the law.  Board discipline if it runs: single-writer
  check first, socket only (`use_core=False`), `div_guard()` PINNED, full
  per-clock rows + sha256 retained, `board_idle` after, wedge = STOP, own id
  space, predictions committed BEFORE first contact.

## §6 THE DIRECTED CELL, SPECIFIED

The cell §4.7 owes: a TF-armed entry with the PREFETCHER'S STATE CONTROLLED at
the take.  Per-candidate predictions, committed here:

| arm | at the take the queue is | **suspend earned (predicted chip)** | **no suspend (predicted engine, pre-landing)** |
|---|---|---|---|
| **C-1** | has room, next word available | no `CODE` between the take and the vector read; vector T1 = last T1 **+ 12** | one `CODE` at the next word; vector T1 = extra T1 + 10 |
| **C-2** | full (no fetch owed) | no `CODE`; vector T1 = last T1 + 12 | **identical** — nothing to steal |
| **C-3** | a fetch already in flight at the take | that fetch COMPLETES (the suspend withdraws only an un-displayed grant), then the vector read **back-to-back** | the vector read **2 clocks later** (P2's shape) |

**C-2 is the control**: an arm in which the candidate predicts NO difference.
A cell that shows a difference on C-2 refutes the account.

**IT IS NOT RUN IF THE BANK DECIDES IT** — W3.1's precedent (§4.9): the corpus
determined the shadow law and no board time was needed.  The bars above are
evaluable entirely offline; the cell is what makes an UNMET B-1 actionable.
