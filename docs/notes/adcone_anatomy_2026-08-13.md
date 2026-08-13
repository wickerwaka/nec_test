# THE `ucrom → ad_o` LAUNCH CONE — THE ANATOMY, BEFORE ANY DESIGN

**Branch `master`, HEAD `faabb15128` (isolated worktree, HEAD verified).
OFFLINE ONLY.  NO BOARD, NO FLASH.  No Codex consulted, no nested task
spawned.**  Nothing in `hdl/` is edited by this document; it is the
measurement the design must be chosen from, and it is committed **before** the
design.

---

## §0 WHY AN ANATOMY AT ALL, AND WHY ON MORE THAN ONE SEED

`timing50_distribution_2026-08-13.md` established the two facts that make a
naive fix worthless:

* the binding class is `upc_* → observation register` on **15 of 16 draws**, and
* it is a **different endpoint pair on every single draw** — 8 distinct of 8 in
  each configuration.

> **The cone's IDENTITY as a class is a property of the tree.  The individual
> path is a property of the draw.**

So the question an anatomy has to answer is not *"what is the worst path"* — that
is a fact about one placement — but ***"where does the delay accumulate, on the
paths this class always contains"***.  That needs a POPULATION of paths and more
than one seed.

New instrument: **`sw/sta_adcone_anatomy.tcl`** (`quartus_sta -t … <out>
[npaths]`), run on an already-fitted `db`.  It walks the top-N setup paths whose
DESTINATION is an observation register and reports three things:

* **A. a REGION HISTOGRAM** — delay and cell count per region of the design,
  averaged over the population;
* **B. a NET CENSUS** — for every named net, on how many of the N paths it
  appears and what it costs per appearance.  *A net on 60/60 is stable
  sub-structure; a net on 3/60 is that draw.*
* **C. the worst path node by node**, with each node's region tag.

Its observation collection includes the `~DUPLICATE` forms, which
`timing50_distribution_2026-08-13.md` §6 found `sta_truefmax_probe.tcl` missing
by exact name.

Driver: **`sw/run_adcone_anatomy.sh <outdir> <seed>…** — one pre-flow, one
`quartus_map`, then `quartus_fit --seed=S --recompile=off` per seed, i.e.
`quartus_gate.py --seeds` stage for stage, with the anatomy probes run after
each fit instead of the gate's own.  It carries the same single-writer guard
(`pgrep -x`) `sw/run_g6dist_n8.sh` carries.  **It is not a gate and writes no
receipt**; the quotable numbers come from `quartus_gate.py`.

⚠ **THE REGION CLASSIFIER UNDER-REPORTS `EU` AND `BIU`, AND THAT IS STATED
RATHER THAN CORRECTED.**  Quartus names post-fit *register* nodes with the full
`v30u_eu:u_eu|…` form but post-fit *combinational* nodes with the instance name
alone (`emu|system_large|u_core|u_eu|Mux277~12`).  The classifier's `EU`/`BIU`
patterns therefore match only the registers, and every EU/BIU combinational cell
falls into `SYS`.  `UCROM` is unaffected — it matches on `u_ucrom`.  **§2's
per-segment table is read off the node list (§C) directly and does not use the
region column**; the region column is reported as the tool produced it.

---

## §1 THE DRAW — SEED 5, CONTROL, AND IT REPRODUCES THE DISTRIBUTION EXACTLY

`sw/testdata/adcone/anat-ctl/`, CONTROL, corner Slow 1100 mV 100 C, `divclk` at
31.250 ns.

| | recorded in `timing50_distribution_2026-08-13.md` §4.1 | measured here |
|---|---|---|
| CONTROL seed 5 Fmax | **38.97** | **38.97** |
| worst setup | **+5.592** | **+5.592** |
| binding cone | `upc_opc[7]~DUP → ad_in_q[14]` | `upc_opc[7]~DUP → ad_in_q[14]` |

**The map is a different map and the draw is the same draw to the digit**, which
is the distribution gate's §7 determinism finding reproduced a third time and is
the control that makes this anatomy the anatomy of the tree's own worst draw.

`sta_fmax_attrib.tcl` on the same `db`: **all twelve lowest-own-Fmax paths are
`k = 1.00`, all `upc_opc[*] → ad_in_q[14]`, 27-28 levels, 38.97-39.17 MHz.**
There is no second class within 0.2 MHz of it.

---

## §2 WHERE THE DELAY IS — THE WORST PATH, SEGMENT BY SEGMENT

Read off `seed5.adcone.txt` §C.  The launch register's clock arrives at cum
**8.389 ns** (5.547 of PLL network + 2.273 routing + 0.569 clk→q), so the
**DATA PATH is 33.420 − 8.389 = 25.031 ns**.

| # | segment | nodes | ns | % of data path | cells |
|---|---|---|---:|---:|---:|
| 1 | **`ucdecode`** — the 8192 × 12 LUT ROM | `ucdecode~448 · ~216 · ~220 · ~228 · ~238` | **4.770** | **19.1 %** | 5 |
| 2 | **`ucrom`** — the 1028 × 29 LUT ROM | `ucrom~788 · ~457 · ~108 · ~112` | **5.051** | **20.2 %** | 4 |
| | **the ucrom HEAD, both tables** | | **9.821** | **39.2 %** | **9** |
| 3 | **the EU's rails** | `r_farjmp~0 · e_ectl[0]~0 · comb~15 · Mux277~12 · Mux277~1 · Mux277~6 · s1_now[0]~32 · ind_now[0]~1 · retire_ok_e~0 · eu_bnd_take` | **6.985** | **27.9 %** | 10 |
| 4 | **the BIU's queue / announcement rails** | `pop_now~5 · qs_e_now~7 · ann_kill~0 · ann_kill~1` | **3.110** | **12.4 %** | 4 |
| 5 | **`assign ad_o`** — the pin mux itself | `ad_o[9]~6 · ad_o[9]~16 · ad_o[14]~109 · ad_o[14]~111` | **3.629** | **14.5 %** | 4 |
| 6 | **out of the core into the rig's sampler** | `core_ad[14]~23` + `ad_in_q[14]` setup | **1.486** | **5.9 %** | 2 |
| | **TOTAL** | | **25.031** | | **29** |

*(Quartus's own `-num_logic_levels` for this path is 28; the 29 above is this
tool's count of `cell`-type arrival points, which includes the destination
register.  The two are the same measurement counted from different ends.)*

**THE HEADLINE: the microcode head is 39.2 % of the launch cone's delay and 9 of
its 29 levels, and it is TWO SERIAL LUT ROMS, not one.**

---

## §3 WHAT IS STABLE — THE NET CENSUS OVER 60 PATHS

The class is one chain, and **fifteen nets are on 60 of 60 paths**:

| paths | ns / hit | net |
|---:|---:|---|
| **60** | **4.691** | `u_eu│u_ucrom│ucdecode` |
| **60** | **4.285** | `u_eu│u_ucrom│ucrom` |
| 60 | 1.836 | `u_eu│Mux277` |
| 60 | 1.574 | `u_biu│qs_e_now` |
| 60 | 1.218 | `u_biu│ad_o[9]` |
| 60 | 0.920 | `u_biu│ann_kill` |
| 60 | 0.746 | `u_eu│retire_ok_e` |
| 60 | 0.628 | `u_eu│s1_now[0]` |
| 60 | 0.616 | `u_biu│pop_now` |
| 60 | 0.565 + 0.344 | `u_eu│eu_bnd_take` |
| 60 | 0.291 | `u_eu│ind_now[0]` |
| 56 | 2.203 | `u_biu│ad_o[14]` |
| 56 | 1.224 | `system_large│core_ad[14]` |
| 32 | 3.371 | `u_eu│s1_val` |
| 28 | 1.246 | `u_eu│r_farjmp` |

Averaged over the 60 paths the tool reports **`UCROM` 8.976 ns/path and 8.3
cells/path** — 36 % of the ~24.8 ns average data path — against a total of
33.221 ns/path including the 8.389 ns clock arrival.

**So the STABLE sub-structure the class always contains is:**

```
upc_page/upc_opc/upc_loc  ->  ucdecode  ->  ucrom  ->  [EU row decode: r_farjmp,
   e_ectl, comb, Mux277, s1_now, ind_now, retire_ok_e]  ->  eu_bnd_take
   ->  [BIU: pop_now -> qs_e_now -> ann_kill]  ->  assign ad_o  ->  core_ad
   ->  nec_bus|ad_in_q
```

### 3.1 ⚠ THE CONE REACHES `ad_o` THROUGH ITS **SELECT**, NOT THROUGH A DATA TERM

`ann_kill` feeds `display` (`v30u_biu.sv:516`), and `display` is a **SELECT** of
the `assign ad_o` priority mux — not one of its data inputs.  The chain that
gets there is `eu_bnd_take` (the EU's queue-pop / boundary take) → `pop_now` →
`qs_e_now` (the queue's EMPTY-this-clock rail) → `ann_kill`.

Two consequences, both of which bear directly on the candidate designs:

* **Candidate (a) — "precompute the mux SELECTS onto registers that already
  exist" — is UNAVAILABLE for this select.**  `ann_kill` is a function of the
  EU's acts ON THIS CLOCK (`q_flush`, `eu_susp`, `eu_post`) via `qs_e_now`,
  which is the queue status the same clock's pop produces.  There is no clock
  earlier at which it is defined.  The R7′ landing's pattern worked because
  `row_blocked` was a function of *registers*; this is not.
* **Candidate (d) — `flush_fast_addr`'s 20-bit adder and `eu_addr`'s liveness —
  is REFUTED BY MEASUREMENT.**  Neither `flush_fast_addr`, nor `flush_cs`, nor
  `flush_ip`, nor `eu_addr` appears **anywhere** in the 60-path census, and
  `flush_fast` does not appear as a select either.  On this tree they are not on
  the cone.  ⚠ **This is an erratum against the E-1 re-derivation's §8 reading**,
  which named *"`flush_fast_addr` — a 20-bit adder, live `eu_addr`, the
  rewritten `ann_kill`"* as the terms the band-fall went into: of those three
  **only `ann_kill` is measured on the cone**, and its own cost is 0.920 ns of
  25.031.

### 3.2 WHAT `assign ad_o` ITSELF COSTS — CANDIDATE (b), MEASURED

The pin mux is **4 cells and 3.629 ns**, 14.5 % of the data path, and the
fitter has already flattened its eight-arm priority chain into two shared
select cells (`ad_o[9]~6`, `ad_o[9]~16`) plus two per-bit cells
(`ad_o[14]~109`, `ad_o[14]~111`).  A one-hot rewrite could plausibly recover
**one level, ~0.5-0.9 ns**, and it would have to carry a disjointness proof for
eight selects that are currently ordered by construction.  **It is a quarter of
the ucrom head's cost for the whole of the ucrom head's risk, and it is not
taken.**

---

## §4 WHAT THE ANATOMY SAYS THE DESIGN IS

The one block that is (i) large, (ii) on 60 of 60 paths, and (iii) removable
**without moving a single pin on a single clock**, is the microcode head — and
the reason it is removable is written into `v30u_eu.sv` already, at the
enable-form refactor:

> *"`upc_page_n` / `upc_opc_n` / `upc_loc_n` exist as wires as a free
> consequence — **the only thing a registered microcode ROM ever needed**."*
> — `hdl/rtl/ucore/v30u_eu.sv`, THE COMMIT

`ucdecode`'s address is `{upc_page, upc_opc, upc_loc[3:2]}` — **thirteen bits,
every one of them a register in the same bank, committed by the same
`if (ss_we || srst || ce)`**.  So the decode of the micro-address the bank is
ABOUT TO COMMIT can be taken on the edge that commits it, and the value standing
on the ROM's output at every clock is then, by construction, the same value the
combinational read would have produced on that clock.

**That is not retiming across a clock.  It is taking a lookup on the edge that
already determines its input** — the `g_sp`/`g_bare` pattern (capture at the
defining event, consume registered), applied to the one table whose input is
wholly registered.

⚠ **M10K CONVERSION REMAINS FORBIDDEN AND THIS IS NOT IT.**  An M10K would put
the ROM's output one clock LATE, which costs a cycle; this puts the LOOKUP one
clock early and the OUTPUT on time.  Whether Quartus chooses to infer an M10K
for a registered-output ROM is a synthesis outcome, not a behaviour, and the
measurement will say what it did.

**The ROW table (`ucrom`, 1028 × 29) admits the identical construction** — its
address is `{dec_bank, upc_loc[1:0]}` and `dec_bank` would then be a register
too — but §2 says the decode alone is 4.770 ns of the worst path and
`timing50_distribution_2026-08-13.md` §4.1 puts seed 5's whole-class ceiling
(`rung 1a`) at **45.77 MHz**, i.e. **3.811 ns of slack above the binding path**.
**Removing the decode alone is already more than the class has room to gain on
this draw.**  So the decode goes first and alone, and the row table's own
landing is decided by the measurement rather than bundled into it — the
re-landing campaign's precedent: *a bundle's benefit is not evidence for any
member of it*.

---

## §5 THE SECOND AND THIRD SEEDS

Seeds 6 and 8 were run on the same map by the same driver; their artifacts are
`sw/testdata/adcone/anat-ctl/seed{6,8}.adcone.txt` and their findings are §6
below.  The design in §4 is chosen from **seed 5 plus the distribution gate's
own 16-draw class evidence**, and the later seeds are the check that the STABLE
sub-structure is stable — not the source of the choice.

## §6 SEEDS 6 AND 8 — THE STABILITY CHECK

*(filled in when the two fits complete; see the same file's §6 in the tree.)*
