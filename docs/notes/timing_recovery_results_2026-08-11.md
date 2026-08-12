# RESULTS — E-1, the observation-path multicycle

Branch `fuzz-v2-on-relanding`. Census `84cec65cfe`
(`timing_recovery_census_2026-08-11.md`), pre-registration `22c6f8b540`
(`timing_recovery_prereg_2026-08-11.md`) — **both committed before the edit was
made and before any build of it.**

**OFFLINE ONLY. NO BOARD, NO FLASH.** `flash_log.jsonl` untouched, no socket
command issued.

---

## §0 HEADLINE

| | |
|---|---|
| **The edit** | **ONE `set_multicycle_path` pair in `hdl/nec_test.sdc`. NO RTL, no gate, no tool.** 91 lines added, 89 of them the derivation and the declared operating triple. |
| **CONTROL** | **40.13 → 44.72 MHz**, worst-of-2, both draws identical. **+4.59** |
| **RETENTION** | **38.82 → 45.71 MHz**, worst-of-2, both draws identical. **+6.89** |
| **THE BAR** | RETENTION worst-of-2 **≥ 41.0 MHz** — **MET at 45.71, +4.71 MHz of margin.** |
| **All four predictions** | **P-1 MET · P-2 MET · P-3 MET · P-4 MET.** |
| **Zero-delta ladder** | **every runnable row unmoved**, and three rows CANNOT run in an isolated worktree — said so rather than claimed. |
| **A confirmation nobody registered** | **The RETENTION penalty DISAPPEARED.** It was −1.31 MHz; it is now **+0.99**. The census attributed that penalty to one LUT on the binding cone; E-1 took that cone off the critical path and the penalty went with it. That is the census's §5.2 attribution confirmed **by intervention**, not by argument. |

---

## §1 THE MEASUREMENTS

All builds from a clean `db` via `sw/quartus_gate.py`, `divclk` constrained at
31.250 ns (32.0 MHz), corner Slow 1100mV 100C.

| build | Fmax | worst setup | TNS setup/hold | ALMs | inputs | receipt |
|---|---:|---:|---|---:|---|---|
| baseline CONTROL | 40.13 | +6.333 | 0.000 / 0.000 | 12,246 | `98bef5844ced…` | `37fcb3691bb39b5a…` |
| baseline RETENTION | 38.82 | +5.492 | 0.000 / 0.000 | 12,276 | `98bef5844ced…` | `638bc4340929d1f0…` |
| **E-1 CONTROL draw 1** | **44.72** | +8.887 | 0.000 / 0.000 | 12,224 | `b2e50a482ca1…` | `a799a8d56d88d9e4…` |
| **E-1 CONTROL draw 2** | **44.72** | +8.887 | 0.000 / 0.000 | 12,224 | `b2e50a482ca1…` | — |
| **E-1 RETENTION draw 1** | **45.71** | +8.081 | 0.000 / 0.000 | 12,200 | `b2e50a482ca1…` | `53b5b9a277003c2a…` |
| **E-1 RETENTION draw 2** | **45.71** | +8.081 | 0.000 / 0.000 | 12,200 | `b2e50a482ca1…` | `36dfd01f383a422a…` |

Every build **PASS** on all five G6 essentials, 0 errors, 0 latches, 0
`lpm_divide`, every stage Successful.

**WORST-OF-2 IS THE FIGURE and in every case the two draws were identical** —
identical Fmax, identical worst setup, identical ALMs, and **byte-identical
`.rbf`**. Four more data points for the census's F-4.

⚠ **HOLD TNS IS 0.000 IN ALL FOUR E-1 BUILDS.** The pre-registration named this
as *"THIS edit's live risk, and it shows up nowhere else"* — a `-hold` companion
that is wrong is invisible to every other check. It is clean.

## §2 THE PREDICTIONS, SCORED AS REGISTERED

| | registered | measured | |
|---|---|---|---|
| **P-1** | CONTROL worst-of-2 in **[43.0, 47.0]** MHz | **44.72** | **MET** |
| **P-2** | RETENTION worst-of-2 in **[42.0, 46.0]** MHz | **45.71** | **MET** |
| **P-3** | the top-60 census is **no longer** `v30u_eu → nec_bus` 60/60 | see §3 — it is 0/60 | **MET** |
| **P-4** | the `.rbf` moves in both configurations | `b1fcbb0e…`→`5b869546…`, `ecda4b90…`→`bcb48f01…` | **MET** |

The point estimates in the pre-registration were CONTROL 45.6 and RETENTION
44.7, derived from the baseline's next-class slack. Measured 44.72 and 45.71 —
**within 0.9 MHz, and on opposite sides**, which is what a placement-noise band
looks like.

## §3 P-3 IN DETAIL — the class really did move

`sw/sta_census.tcl` on each build's own reports:

| worst slack by class | baseline CTL | **E-1 CTL** | baseline RET | **E-1 RET** |
|---|---:|---:|---:|---:|
| `CORE → CORE` | +39.594 | +38.555 | +38.529 | +37.494 |
| `ANY → CORE` | +9.306 | **+8.887** | +8.873 | **+8.081** |
| `CORE → ANY` (the AD cone) | **+6.333** | +28.861 | **+5.492** | +26.531 |
| **binding** | `CORE→ANY` | **`ANY→CORE`** | `CORE→ANY` | **`ANY→CORE`** |

Top-60 population, launch → latch entity:

| | baseline | E-1 CONTROL | E-1 RETENTION |
|---|---|---|---|
| launch | `v30u_eu` **60** | `system_large` 57, `hps_axi_slave` 2, ram 1 | `system_large` 33, `hps_axi_slave` 18, `nec_bus` 6, ram 3 |
| latch | `nec_bus` **60** | `v30u_eu` 57, `v30u_biu` 2, jtag 1 | `v30u_eu` 33, `v30u_biu` 24, jtag 3 |

**The AD cone went from +6.333 to +28.861 — it is not merely off the critical
path, it has more than four times the margin of what now binds.** The new
binding paths are:

* CONTROL: `system_large|c_int_q` → `v30u_eu|row_posted`, **+8.887** — the INT
  pin synchroniser into the EU's row-post decision.
* RETENTION: `nec_bus|div_cnt[3]` → `v30u_biu|t1_half2`, **+8.081** — the bus
  divider into the BIU's half-cycle flag.

Both are genuine single-cycle boundary crossings whose launch registers are
**not** CE-gated, so neither is a candidate for the same treatment. **This is
the fabric's real floor for this design, and it is ~45 MHz.**

### §3.1 The retention penalty vanished — and that is a test result

| | CONTROL | RETENTION | Δ |
|---|---:|---:|---:|
| baseline | 40.13 | 38.82 | **−1.31** |
| E-1 | 44.72 | 45.71 | **+0.99** |

The census (§5.2) attributed the −1.31 MHz to the `core_ad_eff` mux being one
extra LUT on the last hop of the binding cone, and nothing else. **That is a
falsifiable claim and E-1 falsified the alternative**: if the retention cost had
been diffuse — extra registers, extra routing pressure, a second cone — it would
have survived the AD cone leaving the critical path. It did not survive. The
remaining +0.99 is placement noise between two different netlists, and it is the
same sign that five earlier draws showed and nobody could explain.

## §4 THE ZERO-DELTA LADDER

E-1 changes **no RTL**, so every simulation-side row is unchanged *by
construction*. Run anyway, because "by construction" is how a vacuous gate is
born:

| gate | registered | measured | |
|---|---|---|---|
| `check_core --core ucore --opcodes all --cases 0` | 169,000/169,000 | **169,000/169,000** | ✓ |
| `check_core --core ucore --opcodes 8F.0 --cases 0` | 500/500 | **500/500** | ✓ |
| HLT sweep `s10-w0` (`--waits 0`) | 97/97 | **97/97** | ✓ |
| HLT sweep `s10-w1` (`--waits 1`) | 93/95 | **93/95** | ✓ |
| HLT sweep `s13-w2` (`--waits 2`) | 45/46 | **45/46** | ✓ |
| HLT sweep `s13-w3` (`--waits 3`) | 44/45 | **44/45** | ✓ |
| **HLT total** | **279/283** | **279/283** | ✓ |
| `ulockstep --golden all --cases 50` | 17,350/17,350 | **17,350/17,350 ALL LOCKSTEP** | ✓ |
| `r7_lint.py` | PASS, 0 violations | **PASS** — 1 carrier, 3 tainted, 51 `stop` sites, 0 violations | ✓ |
| `ss_lint.py --core ucore` | 0x8D / 226 / 214 flops | **PASS**, 103×2 BIU + 122×2 EU + tag = **226**, **214** flops, **0 UNMAPPED** | ✓ |
| `gen_ucore_qsf.py --check` | PASS | **PASS** on all four E-1 builds (it is G6's E1) | ✓ |
| `ghost_launch_law.py score` (the 528-cell column's law) | 200/200, exit 0 | **200/200 = 100.0 %, exit 0** | ✓ |

⚠ **THREE REGISTERED ROWS CANNOT RUN IN THIS WORKTREE, AND ARE NOT CLAIMED.**
`fz2_replay` (the 110 byte-identical rows), `fz2_immaterial falsify` and
anything else reading the fuzz-v2 **captures** fail with
`FileNotFoundError: sw/testdata/campaigns/fz2c/captures/…`. The reason is
structural, not a regression: **`git ls-files sw/testdata/campaigns/fz2c/captures/`
returns 0** — the capture corpus is untracked and lives only in the main
checkout's working tree, so an isolated worktree has never had it. These rows
are **NOT scored here and must be run in the main checkout before E-1 is
promoted.** They cannot move — E-1 changes no byte any of them reads — but *"it
cannot move"* is exactly the claim a vacuous gate makes, so it is booked as
owed, not as passed.

⚠ **THE ARCHIVED FSM REVISION IS REASONED, NOT MEASURED.** `nec_test.sdc` is an
input of both revisions. The new exception is guarded by
`[get_collection_size $v30u_regs] > 0`, which is the *same* guard the existing
4/3 exception uses and which is empty in the FSM revision, so it is a no-op
there. No FSM build was run to confirm it.

## §5 WHAT E-1 DOES **NOT** ESTABLISH — unchanged from the pre-registration

**A timing exception is a claim about the real circuit and no offline gate can
falsify it.** Verilator does not model it, `check_core` does not model it, and
G6 merely *believes* it. Every number in §1 is Quartus taking the SDC's word.

Therefore, as registered before the run and **not revised after seeing a good
result**:

* **E-1 IS NOT PROMOTED TO A FLASH BY THIS WAVE.**
* **The registered fabric bar for the first bitstream carrying E-1**:
  `check_ab_hw` first light **MATCH 800 ×3**, `x1_fabric baseline` reproducing
  its offline column with **0 PASS/FAIL disagreements and 0 differing
  coordinates**, and the closing `use_core=0` chip proof **MATCH 800**. Any
  deviation is attributed to E-1 **first**, because E-1 is the only thing that
  changed how the capture path is timed.
* **The RTL-side falsifier is in the SDC beside the exception**: a read of any
  register in `$obs_regs` that is not gated by `tick_rise`/`tick_fall` on a path
  reachable with `cfg_use_core=1, cfg_small_mode=0`. One such read makes the
  exception false and it must come back out.
* **The declared operating triple is `cfg_use_core=1, cfg_small_mode=0,
  cfg_clk_div >= 6`** and it is written into `nec_test.sdc`. `div = 4` is
  already a documented-broken capture configuration for an unrelated reason
  (`sw/v30run.py:44`).

## §6 THE GHOST RELOCATION — go/no-go

`ghost_launch_law_results_2026-08-11.md` §7 booked ≈ 44 flops and a **20-bit 3:1
mux on `cmt_addr`**, and refused to land it *"into a tree whose retention band
bottom is 38.82 MHz against a 38.0 STOP"* — 0.82 MHz of margin.

**RECOMMENDATION: GO, with two conditions.**

The margin is no longer 0.82 MHz. It is **7.71 MHz** (45.71 against the 38.0
STOP), and the reason it is that is directly relevant to what the relocation
does:

1. **The relocation's expensive part was the mux on `cmt_addr`, because
   `cmt_addr` feeds `ad_o` feeds the pads.** That cone is exactly the one E-1
   took off the critical path, where it now carries **+26.5 ns of slack**. A
   20-bit 3:1 mux is the same shape as the retention mux, whose *measured* cost
   on that cone was −1.31 MHz **when the cone was binding** and is **+0.99**
   (i.e. nothing) now that it is not.
2. **The ≈ 44 flops are free.** `CORE→CORE` carries +37.5 ns of slack against a
   31.25 ns period.

**Condition A — the relocation still owes its own G6 pair, two draws each, and
its own pre-registration.** Nothing here licenses skipping that; what it changes
is the prior, from *"expect to breach the STOP"* to *"expect to land in the
low 40s"*.

**Condition B — E-1 must clear its fabric bar first, or the relocation must be
landed on a bitstream that does not carry E-1.** These are two independent
claims and bundling them would make the first fabric failure unattributable.
`standing_gates.md`'s own precedent is explicit: *a bundle's benefit is not
evidence for any member of it* — and the same is true of a bundle's failure.

**If the user prefers not to take E-1's fabric risk at all**, the relocation is
*still* not obviously blocked: the design **closes** at its actual 32.0 MHz
constraint with +6.333 ns even on the baseline, and Fmax is a capability figure,
not a requirement. The 38.0 STOP is a self-imposed headroom bar. That framing is
offered, not urged — the STOP is the user's and this document does not move it.

## §7 THE HONEST LEDGER OF THIS WAVE

**What was recovered: +4.59 MHz CONTROL, +6.89 MHz RETENTION, for zero RTL.**

**What was NOT recovered, and why the number is what it is:** the ~8 MHz the
band lost across the campaign went into `assign ad_o` (census F-3), and **E-1
did not give any of it back — it made the place it went stop mattering.** The
`ad_o` cone is still 24.3 ns and still 34–39 levels; it now has two clock
periods to cross instead of one. If the AD cone is ever needed *fast* again —
if, say, `cfg_clk_div` must go to 4 — every one of those mechanisms is still
there and the −6.19 MHz is still real.

**The largest remaining structural lever is booked and untried**: the
combinational LUT microcode ROM is **9.4 ns of the 24.3 ns cone, at its head**
(`v30u_ucrom`: 1,050 ALUTs, **0 registers**). Making it an M10K would be the
single biggest win available and costs a cycle of latency, so it is banned by
this wave's zero-behaviour terms — **by its terms, not by its merits.**

**And the design's real floor is now measured**: ~45 MHz, set by
`c_int_q → row_posted` and `div_cnt → t1_half2`, two single-cycle boundary
crossings whose launch registers are not CE-gated. Neither can be relaxed the
way E-1 relaxed the observation path. **Further Fmax beyond ~45 MHz needs RTL,
not constraints.**
