# DOWNSTREAM REPORT — the ucore closing timing in Arcade-IremM72

**Not a nec_test result.** Nothing here was produced by `sw/quartus_gate.py`, no
G6 gate was run, no prediction was pre-registered, and no claim in this file has
been through this tree's evidence discipline. It is a report of what the ucore
did inside a *different* design, written so the findings are not lost.

**OFFLINE ONLY. NO BOARD, NO FLASH.**

| | |
|---|---|
| **Where** | `~/src/Arcade-IremM72_MiSTer`, branch `simulator`, on top of `0fad95b` ("Update V30 to microcode ucore"). Changes uncommitted at the time of writing. |
| **This tree** | `82d7561c4b` (`master`). Nothing in nec_test was modified. |
| **Tool** | Quartus 17.1.0 Lite, 5CSEBA6U23I7, Slow 1100mV 100C, `divclk` at 31.250 ns (32.0 MHz) — the same corner and period as the E-1 work. |

---

## §0 HEADLINE

The ucore did **not** close timing in M72. It does now, at +0.243 ns worst setup
across the whole design, with **no change to the emulated CPU's timing**.

| | before | after |
|---|---:|---:|
| worst setup slack (all clocks) | **−37.433 ns** | **+0.243 ns** |
| setup TNS | −14,333.168 | 0.000 |
| `clk_sys` Fmax | 14.56 MHz | **37.67 MHz** |
| whole design, ALMs | 34,634 (83 %) | **32,168 (77 %)** |

Three edits, in the order they were needed. Two are M72-local. **One is a
finding this tree already owns and deliberately declined to act on, and the
downstream cost of that decision is the point of this note.**

---

## §1 THE CE MULTICYCLE, RE-DERIVED FOR A DIFFERENT DIVIDER (M72-local)

`hdl/nec_test.sdc`'s exception ports directly, but **the multiplier does not.**

`nec_bus` gives the core `cfg_clk_div` sys clocks per CPU cycle, 8 at the
divider of record, so `-setup 4 -hold 3` is honest there. M72 runs the ucore
from an `ce_steady` train (`rtl/m72.v:183`): a free-running reference ticks the
target 8 MHz, and a chasing counter issues the CE and CE_HALF phases **one per
fabric clock** while it is behind, so an SDRAM stall defers CPU cycles instead
of losing them. `ce_cpu` is `~ce_cpu_count[0]` and `ce_cpu_half` is
`ce_cpu_count[0]`, so the phases strictly alternate and **two `ce_cpu` pulses
are never closer than TWO clk_sys periods** — 4 in steady state, 2 at the
catch-up burst rate. The honest exception is therefore `-setup 2 -hold 1`.

Anyone porting the E-1 SDC to another platform should re-derive this number
rather than copy 4. The falsifier is unchanged and worth restating: **a `v30u_*`
state register that can take a new value on a clock where `ce` is low.**

One refinement worth having upstream too. Probing `<reg>|ena` in the post-fit
netlist reported 35 of 1,289 v30u registers without an enable pin. 33 were
`ss_rdata[*]` and `t1_half2`; the other two (`v30u_eu|chg[1]`,
`v30u_biu|last_ube`) were **Quartus folding the enable into a D-side feedback
mux** — same function, no `ena` pin. The `|ena` probe over-reports; confirm any
hit by re-checking that register with the exception removed before acting on it.
Both of those pass single-cycle at +19.3 ns, so nothing rested on them.

### §1.1 A SECOND RELATIONSHIP THE DEFAULT GETS WRONG

`v30u_biu|t1_half2` and (M72's adapter) `v30_bus|addr_neg` / `ube_neg` are
**negedge** flops enabled by `ce_half`. `ce_half` lands one fabric clock after
the `ce` that launched their data and they capture on the negedge *inside* that
clock, so the true launch-to-latch distance is **1.5 periods**, not the 0.5 a
posedge→negedge default assumes. For a negedge destination the Nth latch edge is
at N−0.5 periods, so that is `-setup 2 -hold 1`.

This is corrected modelling, not a relaxation, and `t1_half2` is upstream's —
whether it bites depends on what feeds it in a given design. In M72 it did: at
−2.380 ns it was the worst path in the design once the chain was fixed.

---

## §2 `ss_we` IN THE NEXT-STATE FUNCTION — §52.3's FINDING, ONE SIGNAL OVER

**This is the one that generalises, and it is a straight repeat of the `srst`
extraction, so `v30u_biu.sv`'s own header already argues it.**

§52.3 pulled `srst` out of the BIU next-state function because it *"sat in the
same expression tree as the whole BIU and the whole EU chain that consumes this
module's `_n` view"*, and measured the damage as
`c_reset_q` → `v30u_eu|wb_seg[0]~0` → `v30u_biu|grn_n` → `q_ripe_lead_n` → the
twelve chain positions, 58.9 ns.

**`ss_we` was still an arm of that same function, and it does the same thing.**
The BIU's save-state write assigns the next-state names (`grn_ttl`, `grn_n`,
`q_cnt`), and those three are exactly what `q_ripe_lead_n` reads:

```
wire [3:0] poppable_n = (grn_ttl != 2'd0) ? (q_cnt - {2'b0, grn_n}) : q_cnt;
assign q_ripe_lead_n  = (poppable_n != 4'd0) || ((grn_ttl == 2'd1) && (q_cnt != 4'd0));
```

MEASURED in M72, with the CE multicycle already in place: all 500 of the worst
paths launched at `v30_core|ss_addr_q[*]` and ran
`u_biu|grn_ttl` → `q_ripe_lead_n` → the whole EU chain, **52.0 ns against
31.250 ns**. Like §52.3's, it **could not be excepted** — `ss_addr_q` is not
CE-gated, so no CE multicycle reaches it.

The fix is §52.3's fix: the save-state write moved from the next-state function
to the register bank, in both modules. It is cycle-identical for the same reason
the `srst` move was — the write is a pure `ss_wdata` fan-out with no next-state
term in it, so on an `ss_we` clock the bank writes the ONE addressed register
and every other one holds, which is precisely what the discarded `<x>_n = <x>`
defaults produced when the arm sat in the comb block.

Files touched: `v30u_biu.sv`, `v30u_eu.sv`, `v30u_eu_ss_write.svh` (the
generated arm now targets the registers, `<x> <= v` rather than `<x>_n = v`).

**Whether this is worth landing here is a judgement for this tree**, and it
depends on whether anything in `nec_bus`'s SS path reaches the `_n` view the way
M72's `ss_addr_q` does. The structural defect is present either way: after the
change, `ss_we`/`ss_addr` appear in no `always @*` block in either module.

---

## §3 `CHAIN_MAX` — THE BOUND THIS TREE DERIVED AND CHOSE NOT TO TIGHTEN

**§51.2 already owns this result and got there first.** The transition-graph
argument, the nine states, the per-position census (24 / 9 / 5 / 3 / 2 / 1) and
**maximum chain depth 6** are all §51.2's. I re-derived the graph independently
before reading it and reached the same nine states and the same depth 6, which
is a replication, not a discovery.

§51.2's disposition was explicit: *"`CHAIN_MAX` stays at 12 — the bound is not
tightened, so no new corpus-scoped claim is made about chain depth."* For area
that is nearly free; §51.1 already showed the fold recovers most of the cells.

**What the M72 fit adds is that the untightened bound costs DEPTH, and depth is
not recovered by the fold.** A position that can never be *occupied* still sits
in the critical path, because the chain is one combinational expression — the
`if (chain == 4'd0)` guard removes 24 arms from a copy but does not remove the
copy. With §1 and §2 in place, the last violating class in M72 was:

```
upc_page / upc_opc → ucdecode → ucrom → the chain → r_kind / modrm_reg
    75.5 ns data path, ~71 logic levels, 52.6 ns of it CELL delay
    against a 62.5 ns budget (2 clk_sys periods)          slack −13.756
```

Cell-dominated, so no fitter effort, seed or setting was going to find 13.8 ns.
The ucrom head is only 8.0 ns of it; the chain is the rest.

M72 now runs **`CHAIN_MAX = 7`** — §51.2's derived 6 plus one spare position,
because fabric has no assertion. That closed it: ALMs 83 % → 77 % and the class
disappeared entirely.

**This tightens the bound, which is exactly the claim §51.2 declined to make**,
so it is registered here as an M72-local change and nothing more. If it is ever
wanted here it needs this tree's treatment, not mine. Two things may help if so:

1. **A third, independent corroboration of depth 6.** A Verilator harness
   driving `v30_bus` from an LFSR environment — LFSR memory, LFSR `READY`/`INT`,
   and an m72-shaped CE train with LFSR stalls — reports `CHAIN_DEPTH_MAX 6`,
   entry state 25 (`S_EPOP`), on **four independent seeds**. That is a stimulus
   distribution with nothing in common with the golden suite: it executes
   arbitrary bytes, not 347 known forms. It agrees with §51.2's census exactly.
2. **`CHAIN OVERFLOW` is the falsifier and it stayed silent** at
   `CHAIN_MAX = 7` across all four seeds, 420,000 fabric clocks each. §51.3
   built that assertion for precisely this question.

The longest zero-cost path, for the record, is five positions and it is the
one that reaches `S_DECODE2`:

```
S_TAIL / S_TAIL_POP → S_INSTR_END → S_TAKE_OPC → S_DECODE → S_DECODE2 (stops)
```

with `S_TAIL` / `S_TAIL_POP` enterable zero-cost only from `S_EPOP` and `S_ROW`,
both position-0-only, so they stand no deeper than position 1. Deepest occupied
position 5, six iterations.

---

## §4 HOW THE RTL CHANGES WERE CHECKED

`sim/` in the M72 tree could not build (four unrelated breakages, since fixed),
so equivalence was established with a purpose-built harness rather than
`check_core`. **It is not a substitute for this tree's gates** and no claim is
made that it is.

It drives `v30_bus` from the LFSR environment of §3, accumulates a 64-bit
signature over every core output on every fabric clock, and mid-run freezes the
core and runs a full save-state read-out → pattern-write → read-back →
restore → verify over the ssbus, signing that too.

| | |
|---|---|
| §2 + §3 vs untouched RTL | **bit-identical** signature, save-state signature and probe, on **4 seeds × 420,000 clocks** |
| save-state round trip | original state survives; `ss_mismatch` 0 |
| sensitivity control | deleting ONE arm from `v30u_eu_ss_write.svh` **does** move the probe — the harness is not vacuous |

The harness is a scratch artifact in the M72 session, not in either repo. Say so
if it is worth keeping and it can be added under `sim/` there.

---

## §5 WHAT M72 DELIBERATELY DID NOT DO

The cheap alternative to §3 was to buy the chain a third clock by inserting one
idle fabric clock after each CE_HALF, making `ce_cpu` pulses ≥ 3 apart and
`-setup 3` honest. ~6 lines, closes with ~17 ns of margin.

**Rejected, by the user, on accuracy grounds.** It would have dropped the
post-stall catch-up burst from 16 MHz to 10.67 MHz, and the CPU only holds its
8 MHz average while sustained `cpu_stall` duty stays under ~33 % (it is ~50 %
today). `ch3` is the lowest-priority SDRAM channel and that could not be ruled
out analytically. Worth recording because it is the same trade any other
platform integrating this core will be offered, and it is the wrong one to take
by default: **the chain depth was real, and removable, and the timing model did
not have to move at all.**
