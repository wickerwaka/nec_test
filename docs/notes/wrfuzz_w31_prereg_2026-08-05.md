# wrfuzz W3.1 — PRE-REGISTRATION: the BRK/TF trap's ENTRY, and the shadow

**Task #41.  Written and committed BEFORE any engine file was edited and
before any post-landing figure was measured.**  Branch `ucsim`, tree
`f22f888feb`.  Board-free so far; no board has been contacted this sitting.

> **Standing principle.**  *"A guiding principal here needs to be simplicity.
> This is 80's era hardware, they aren't wasting silicon on anything that isn't
> necessary.  Complex or confusing behavior that we see is likely to be simple
> systems interacting in ways you do not fully understand yet."*

The survey (`wrfuzz_survey_2026-08-05.md` §8 item #1) ranked the single-step
trap's entry first: **75 of 136 scored misses.**  This document states what the
analysis found, what is predicted, and what would refute it.

---

## §1 THE PARTITION — the 136 fabric-census misses, by ENTRY GEOMETRY

Measured with `sw/w31_shadow.py`'s entry detector (§83.2's own: a vector pair
at `4V` / `4V+2` followed by three descending word pushes) applied to BOTH
sides of every retained capture, then pairing entries in order and taking the
first that differs in `(vector, pushed IP, T1 row)`.

| class | n | what it is |
|---|---|---|
| **DIFF_BOUNDARY** | **50** | the two sides trapped at **different instruction boundaries** |
| **SAME_BOUNDARY** | **32** | same boundary; the `ucore`'s vector read is **2 … 6 clocks LATE** |
| NO_ENTRY_DIFF | 53 | no interrupt entry differs — the non-trap residue |
| UNREADABLE | 1 | odd-SP (byte-split) frame |

⚠ **THE SURVEY'S §4.1 READING IS CORRECTED, NOT RESTATED.**  It read `PF_LOST`'s
30 `MEMR 00004` seeds as *"the SAME event with the owners swapped"* as
`PF_GAINED`'s 18.  They are **two different mechanisms**: `PF_GAINED` 18/18 sit
in SAME_BOUNDARY (an entry-timing question) and the `PF_LOST` 30 sit in
DIFF_BOUNDARY (a recognition-class question).  Same family label, same
contested address, different cause.

---

## §2 THE LAW — **THE SINGLE-STEP TRAP RIDES THE RECOGNITION SHADOW, AND THE SHADOW IS TWO MICROCODE ENTRIES**

### §2.1 Measured on silicon alone, with no engine in the loop

`sw/w31_shadow.py` turns each capture's **chip** storm into instruction counts:
consecutive vector-1 entries publish their return IPs on the pads, and the
GENERATOR'S OWN instruction layout (`fuzz_campaign.build(cfg)['ins']` plus
`testimage.compose`'s store stub) says where instructions start.  `grace` is
the number of instruction boundaries the part ran PAST between one trap and the
next; §84/§85 measured the storm cadence at grace **0** on 1,742 + 90 pairs and
landed it in both engines.

**Over the 380 retained `wr1` captures — 3,411 chip vector-1 entries, 1,363
consecutive pairs ruled:**

| class | opcodes | grace 0 | grace ≥ 1 |
|---|---|---|---|
| **`MOV` sreg** | `8C` `8E` | **0** | **69** (68 × g1, 1 × g2) |
| **`POP` sreg** | `07` `17` | **0** | **6** |
| `PUSH` sreg | `06` `16` | **5** | 0 |
| `LES` / `LDS` | `C4` `C5` | **11** | 0 |
| everything else | 195 distinct opcodes | **1,277** | **0** |

**75 of 75 grace-≥1 pairs are in the two classes; 1,288 of 1,288 grace-0 pairs
are outside them.  There is not one exception in either direction.**  The
single `g2` is two consecutive `8E`s — the shadow COMPOSING, which is a
consequence and not an exception.

### §2.2 The law, stated

> **An instruction of the shadow class does not permit a single-step trap to be
> TAKEN at its own retire boundary.  The arm is unchanged (the boundary still
> SAMPLES); the take moves to the next boundary.**
>
> **The class is two MICROCODE ENTRIES, not a list of opcodes:**
> `00?.100011?0.00` (`8C`, `8E` — `R -> M`, the `MOV` sreg entry) and
> `00?.000??111.00` (`07`, `0F`, `17`, `1F` — `OPR -> R`, the `POP` sreg
> entry).  `PUSH` sreg is a DIFFERENT entry (`00?.000??110.00`) and does not
> shadow; `LES`/`LDS` are their own entries and do not shadow.

Two things make this a mechanism rather than a fit:

1. **The `MOV` half is ALREADY IN THE TREE, as a class, for the OTHER
   recognition.**  `hdl/rtl/ucore/v30u_eu.sv:270` — `irq_shadow`, *"a
   segment-register write skips ONE boundary"* — is set from
   `pla3_sreg_mov(pv)` and gates `irq_take`.  **It does not gate the trap:**
   `wire bnd_take = irq_take || brk_arm;`.  §86.A booked exactly this as a
   divergence — *"the trap is not shadowed behind a segment-register load
   (neither engine shadows it; silicon is documented to, this tree has no cell,
   falsifier written down)"*.  **This is that falsifier firing, with a
   population.**
2. **It explains why `8C` — a segment-register READ — shadows.**  §84.7's
   write-derived rendering was already refuted in the RTL comment; a per-ENTRY
   shadow gets `8C` for free, because `8C` and `8E` are the same ROM entry.
   And it predicts the two NEGATIVES measured above: `PUSH` sreg and `LES` /
   `LDS` are different entries and do not shadow.

**WHAT IS NEW versus the tree**: (a) the trap must ride the shadow at all;
(b) the **`POP` sreg entry is not in the class in either engine** — no PLA
column carries it, and the ucore's `irq_shadow` is `pla3_sreg_mov` alone.

---

## §3 WHAT IS PREDICTED — registered before the landing

### §3.1 The predicted set — **39 named seeds**

The `wr1` scored misses whose FIRST divergent trap entry is a shadow-class
boundary, and on all 39 of which the CHIP trapped LATER than the engine:

```
200024 200059 200078 200103 201055 201099 202000 202005 202058 202100
203027 203058 203060 205049 205057 205092 205126 205130 206062 206092
206136 207098 208038 208066 208080 208096 208129 209039 209060 210019
210029 210049 210058 210091 210114 210132 211053 212033 212085
```

All 39 are **DIVERGE in the `sim` leg as well** (measured on the pre-landing
binary: `timed_fuzz --seeddir <wr1 seeds> --core sim` = **48 / 184 EXACT**), so
the mechanism bar below is evaluable on both engines.

### §3.2 The BARS

* **A-1 — THE MECHANISM BAR.**  On each of the 39, the engine's first
  divergence must move **strictly later**, or the seed must become EXACT.
  **Zero exceptions permitted.**  This is checked seed by seed, not by a total.
* **A-2 — NO LOSS.**  No seed that is EXACT before may be non-EXACT after, on
  **any** population, for **either** engine: the 380 `wr1` captures and the
  standing 3,242-seed bank.
* **A-3 — THE RATCHETS MAY ONLY GO UP.**
  `timed_fuzz --core sim --evt-replay` REGISTERED **≥ 1,282**, EVT **≥ 789**,
  COMBINED **≥ 2,071**;
  `--core ucore --evt-replay` REGISTERED **≥ 1,502**, EVT **≥ 920**,
  COMBINED **≥ 2,422**; `--seeddir b2-tranche` sim **≥ 154**, ucore **≥ 172**.
* **A-4 — THE SM TRAP CELLS MUST NOT MOVE, AT ALL.**
  `sm3_tf_floor_cell.py score --core sim` **121,890 rows, 0 row-diffs, 30/30
  captures**; `--core ucore` **121,860 rows, 0 row-diffs, 30/30**; W-0a **0
  entries / 18 captures**, W-1 **30/30**, W-3 **phase 2 vs 3 at both waits**,
  W-4 **0 · 0**, W-5 **90/90**.  *(No sled or handler in that cell contains
  `8C`, `8E`, `07`, `17` or `1F` — checked before landing — so the prediction
  is that it cannot move.  If it moves, the landing is wrong.)*
* **A-5 — THE MUST-NOT-MOVE LADDER**, both engines, every cell of §84.5 /
  §86.E, re-run on the final binaries.
* **A-6 — `ulockstep --golden all --cases 50` 17,350 / 17,350**, `ss_lint`
  exit 0 with an `SS_VERSION` bump if any flop is added, and a G6 receipt if
  the RTL changes.

### §3.3 THE FALSIFIERS

1. **A-1 with any exception**: a seed whose first divergence does NOT move
   later is a seed the shadow does not own, and the class is wrong.
2. **Any A-3 cell moving DOWN by one seed** — the landing is REVERTED, not
   renegotiated.
3. **The `POP`-sreg half specifically**: it is added to the SHARED class
   (silicon has one class), so it also reaches the maskable/NMI recognition.
   **If any INT / EVT leg moves DOWN, the `POP` half is reverted and booked as
   trap-only**, with the number that says so.
4. **The class boundary**: any capture in which `PUSH` sreg or `LES`/`LDS`
   shows grace ≥ 1, or in which `8C`/`8E`/`07`/`17`/`1F` shows grace 0.

---

## §4 THE SECOND HALF, BOOKED NOT LANDED — the entry's LAUNCH (SAME_BOUNDARY 32)

Same instruction boundary, and the `ucore`'s vector read is late by
**+2 (×12), +4 (×11), +5 (×3), +6 (×5)**, with one outlier at −6.  On **19 of
the 32** the engine runs **one extra `CODE` prefetch** the chip does not; on
the rest it runs the same fetches and is still 2 clocks late.  `PF_GAINED`
18/18 live here.

*The mechanism candidate is the OTHER half of the same wire.*
`v30u_eu.sv`: `assign eu_bnd_post = irq_take && …` — the prefetcher SUSPEND is
gated on `irq_take`, so the trap does not carry it, and the RTL says so in as
many words (§86.A: *"the prefetcher suspend belongs to the recognition that
PAYS the IE floor and the trap never pays it"*).  The model's is the same
statement: the suspend sits inside `live = maskable() && …`, and `maskable()`
is `ev_pin_ == 0`, which is every seed a trap fires in.

**It is NOT landed in this sitting** and no figure is claimed for it.  Its own
cell and pre-registration are owed.

---

## §5 THE RIDERS

### §5.1 The 12 zero-`0F FF` 8080 landings — **ANSWERED, and it is a CORE behaviour, not a generator hole**

Chip-side and engine-free: on each of the 12, the row where the `PS3` pin
first goes high is inside an interrupt entry, and the instruction that entry
returns to is three bytes long and begins with `0F`.  **On 10 of the 12 the
THIRD byte IS the vector the entry read** — which is `BRKEM`'s `imm8`
semantics exactly.  The other two have byte-split (odd-SP) frames whose pushed
CS reads back as garbage and are reported unreadable, not as counterexamples.

The ten second bytes are `90 90 90 4A 77 F5 73 CA 7E 53` — **not one of them is
`FF`**, and none is a documented `0F` form.

> **The `0F` extension page's PLA does not fully decode its second byte: the
> undecoded rows fall through to `BRKEM`.**  A `0F FF`-free image is therefore
> not an 8080-free image, which is §7.1's open question answered.  **It is
> routed to the CORE (the `0F` page's don't-care), not to the generator**, and
> it joins the 8080 / BRKEM family, which is **DEFERRED BY USER DECISION**.
> Counted and reported; not worked.

### §5.2 The `wvec-edge` 5/5 — **the registered falsifier's PREMISE fails, and the directed cell is not needed**

§4.5 rested on a matched control *inside* the corpus: `soup/wrand15` with "the
same median `n_ins` (24), the same `nmax_eff` (24) and the same median
bus-cycle count (146 vs 145)".  **Those are STRATUM medians.  Restricted to the
TF seeds — the population the 5/5 is about — the two do not overlap at all:**

| stratum | TF seeds | `n_ins` | **bus cycles** |
|---|---|---|---|
| `soup/wvec-edge` | 5 (all EXACT) | 24 – 26 | **144 – 204** |
| `soup/wrand15` | 6 (all MISS) | 24 – 25 | **291 – 326** |

The control is not matched on the quantity that decides exposure — how far the
run gets — and the Fisher p = 0.0022 is confounded by exactly the length
coupling the survey named and then believed it had controlled.

And the mechanism this document establishes has **no wait term at all**: it is
a microcode-entry class.  That is consistent with §4.4's own measurement (at
`fix0`, no waits, the TF seeds already fail 6 of 7).  **The
intermediate-wait hypothesis is UNNECESSARY and its directed cell is NOT run.**
Recorded as a negative with its numbers, per the refuted-key rule.
