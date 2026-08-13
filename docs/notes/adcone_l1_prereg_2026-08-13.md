# L1 — THE REGISTERED DECODE.  PRE-REGISTRATION.

**Committed BEFORE the edit, before the first build that scores it, and before
any ladder leg is run against it.**  Branch `master`, worktree HEAD
`05bd462643` (the anatomy commit).  **OFFLINE ONLY.  NO BOARD, NO FLASH.**
Governing measurement: `docs/notes/adcone_anatomy_2026-08-13.md`.

---

## §1 THE EDIT, STATED AS A CIRCUIT

`v30u_ucrom`'s first table is read at

```systemverilog
wire [12:0] dec_addr = {upc_page, upc_opc, upc_loc[3:2]};
```

— **thirteen bits, every one of them a register in the EU's one register bank,
committed by the one condition `if (ss_we || srst || ce)`.**  So the decode of
the micro-address the bank is ABOUT TO COMMIT can be taken on the edge that
commits it:

```systemverilog
wire [12:0] dec_addr_next = (srst && !ss_we)
        ? {upc_page_r, upc_opc_r, upc_loc_r[3:2]}      // the bank's srst arm
        : {upc_page_n, upc_opc_n, upc_loc_n[3:2]};     // the bank's normal arm
...
if (ss_we || srst || ce) dec_q <= {dec_valid_next, dec_bank_next};
```

**THE PIN-IDENTITY ARGUMENT, and it is a construction, not an experiment.**
`dec_addr_next` is *character for character* the selection the register bank
applies to `upc_page` / `upc_opc` / `upc_loc`, under *the same* commit
condition.  Therefore on every clock `c`:

* if the bank commits at `c`, then `upc_*(c)` is what `dec_addr_next` was formed
  from at `c-1`, and `dec_q(c)` is `ucdecode` of that same value;
* if the bank does not commit at `c`, neither `upc_*` nor `dec_q` moves.

so `dec_q(c) ≡ ucdecode[{upc_page(c), upc_opc(c), upc_loc(c)[3:2]}]` for every
clock at or after the first commit.  **No pin moves on any clock.**  This is
*not* retiming across a clock; it is taking a lookup on the edge that already
determines its input — the `g_sp`/`g_bare` pattern, applied to the one table
whose address is wholly registered.  The RTL already said so, at the
enable-form refactor: *"`upc_page_n` / `upc_opc_n` / `upc_loc_n` exist as wires
as a free consequence — the only thing a registered microcode ROM ever needed."*

**THE ONE PLACE IT IS NOT IDENTICAL, NAMED IN ADVANCE:** the clocks BEFORE the
first commit.  At power-up `dec_q` is 0 (`dec_valid` = 0 → `row_nop` = 1, the
model's NOP-CTL substitution, the safe direction) where the combinational read
would give `ucdecode[{0,0,0}]`, which F44's own probe proves is non-zero.  Every
harness in the ladder asserts `srst` before it observes anything, and `srst`
forces the commit; **the ladder is the falsifier and a delta there is a STOP.**

`ucrom`'s SECOND table (1028 × 29) admits the identical construction and is
**deliberately NOT in this edit** — the anatomy puts the decode alone at
4.770 ns of the worst path against 3.811 ns of room below seed 5's own
whole-class ceiling, and *a bundle's benefit is not evidence for any member of
it*.

**NO SDC EDIT.**  `dec_q` is declared in `v30u_eu.sv`, so its post-fit node name
is `…|v30u_eu:u_eu|dec_q[*]`, which `nec_test.sdc`'s `$v30u_regs` glob
`{*|v30u_eu:*|*}` already selects.  It is `ce`-gated exactly as every other EU
register, so the 4/3 CE multicycle covers it under the SAME derivation (C-c),
and no new claim is made.

---

## §2 THE REGISTERED PREDICTIONS

Scored as registered, reported as registered, never restated.

| id | prediction |
|---|---|
| **P-1 — THE FLOOR, AND THE REVERT CONDITION** | `worst-of-5@seeds{1,2,3,4,5}` improves by **≥ 2.0 MHz on at least one configuration** against the baseline `worst-of-5@seeds{1..5}` read off `timing50_distribution_2026-08-13.md` §4 — **CONTROL 38.97** (seed 5) and **RETENTION 39.74** (seed 5). **If P-1 is MISSED the edit is REVERTED**, whatever else is green. |
| **P-1a — the expectation, which is NOT the floor** | CONTROL `worst-of-5` lands in **[42.0, 46.5] MHz** and RETENTION in **[41.0, 46.0]**. Derived from the anatomy (4.691 ns/path removed on 60 of 60 paths) capped per draw by that draw's own `rung 1a` ceiling (43.59 … 51.23 CTL). A MISS here is a FINDING, not a revert. |
| **P-2 — PIN IDENTITY. A MISS IS A STOP, NOT A FINDING.** | Every leg below byte-identical / unmoved: `check_core --opcodes all` **169,000/169,000**; `check_core --opcodes 8F.0` **500/500**; HLT sweeps **97 · 93 · 45 · 44 = 279/283** (⚠ `--waits 0/1/2/3`); `ulockstep --golden all --cases 50` **17,350/17,350 ALL LOCKSTEP**; `ghost_launch_law score` **200/200**; `check_boot --core ucore` **220** and **400**; `check_ab_sim --core ucore` **MATCH 187 rows**; the four `evt` cells **200/1,200/200/1,200**, `v0.1-w1`/`-w3` **1,200**, `EB` **200**, `w1evt-biased` **1,200**. |
| **P-3 — the two whole-program pin falsifiers, byte-identical** | (a) `chain_lfsr_gate` PASS **and all four per-seed `sig` values identical** to `sw/testdata/adcone/base/chain_lfsr.txt` (4 × 400,000 clocks of arbitrary bytes, LFSR memory / READY / INT); (b) `fz2_replay --all-failures --pass-sample 200 --leg ret` — **all 306 rows' `sys` blocks** (`n`, `nrows`, `bad`, `flick`, `first`, `fired`, `vecused`) **byte-identical** to `sw/testdata/adcone/base/fz2_replay_base.json`. Both run with `--no-fabric-era-guard`, **stated**: this tree is already a cross-era read (`v30u_eu.sv`, `nec_test.sdc`, `nec_test.qsf` have moved since FLASH #20), so what these two legs measure is **before-vs-after on ONE tree** and nothing about fabric. |
| **P-4 — `r7_lint`** | PASS, **0 violations**, counts unchanged: 20 nets / 1 carrier / 3 tainted / 51 `stop` sites. |
| **P-5 — `ss_lint --core ucore`** | `SS_COUNT` **232 UNCHANGED** (no SSA address is added), architectural flops **220 → 221**, whitelist entries **2 → 3**, **0 UNMAPPED**. ⚠ **THE NEW ENTRY IS A NEW CLASS AND IS DECLARED AS ONE.** The file's existing two are *"written before read on every clock, no value survives the edge"*; `dec_q` **does** survive the edge and is admitted on a different ground — **DERIVED: a pure function of mapped state, recomputed from the same next-state expression on the same commit, so a restore that writes `SSA_E_UPC_*` reconstructs it on that very edge.** Mapping it would create a second source of truth for one fact. The class gets its own heading in `sw/ss_flop_whitelist_ucore.txt`, not a line hidden under the old one. |
| **P-6 — the CE collection** | `nec_test.sdc`'s own `post_message` reads **1805 → 1815** ce-gated v30u registers (10 new flops), with **no SDC edit**. Fitter duplication may raise it; reported as measured. |
| **P-7 — the k=4 class does not become binding** | `sta_census`'s `CORE→CORE` worst slack stays above the k=1 class's on every draw examined. Registered because this edit moves `ucdecode` INTO the next-state cone — but it also removes `ucdecode` **and** `ucrom` from the existing `upc → ucdecode → ucrom → chain → upc_n` path, so the k=4 cone is predicted to get **shorter**, not longer. If REFUTED, the finding is that the EU's own chain has become the wall and L1 stands or falls on P-1 alone. |
| **P-8 — every draw a G6 PASS** | E1-E5 on all 10 draws: Fmax ≥ 32, worst setup > 0, **TNS 0.000 setup AND hold on every domain**, 0 errors / 0 latches / 0 `lpm_divide`, every stage Successful, E7 `n_moved` ≤ 1 with `moved_offending` 0, E8 seed honoured 10/10. |
| **P-9 — RECORDED, NOT PREDICTED** | whether Quartus now infers an **M10K** for the registered-output `ucdecode` (it declines today for *asynchronous read logic*, `v30u_ucrom.sv`). Either outcome is legal — this edit puts the LOOKUP one clock early and the OUTPUT on time, so it is **not** the banned M10K conversion, which puts the output one clock LATE. ⚠ **If an M10K IS inferred, a fabric bar is OWED before any bitstream carrying it is flashed** (F44's failure mode is a silently-empty table), and this wave flashes nothing. |
| **P-10 — area** | ALMs move by **less than ±2 %** against the same-configuration baseline. The table is not resized; only its output is registered. |

---

## §3 THE LADDER, AND WHEN EACH LEG RUNS

**Fast set, immediately after the edit and before any Quartus time is spent**:
`r7_lint` · `ss_lint` · `check_core 8F.0` · `check_core all` · the four HLT
sweeps · `ulockstep` · `ghost_launch_law` · `chain_lfsr_gate`.
**A MISS ON ANY OF THESE REVERTS THE EDIT WITHOUT A BUILD.**

**Full pin-sensitive set, at wave end**: the `evt` cells · `w1`/`w3`/`EB`/
`w1evt-biased` · `check_boot` · `check_ab_sim` · `fz2_replay` byte-identical ·
`fz2_immaterial falsify` G1-G8.

**G6 `--seeds 5`, BOTH configurations**, worst-of-5 quoted with its seed set
named, against the recorded worst-of-5 baseline.

⚠ **THE BASELINE IS A DIFFERENT MAP AND THAT IS STATED.**  The before-figures
are `timing50_distribution_2026-08-13.md`'s seeds 1-5; the after-figures come
from this tree's own map.  An RTL edit necessarily re-maps, so a map-matched A/B
does not exist for this comparison.  The distribution gate's §7 is the mitigation
and the caveat at once: the fit is DETERMINISTIC given (netlist, seed) and
CONTROL seeds 1-8 reproduced to the digit across two independently produced
maps — **and seed 5 reproduced 38.97 / +5.592 a third time on this wave's own
map** (`adcone_anatomy_2026-08-13.md` §1) — but MAP variance is real, historically
~2.3 MHz, and is not eliminated. **P-1's floor of 2.0 MHz is at the edge of that
band and is registered knowing so.**
