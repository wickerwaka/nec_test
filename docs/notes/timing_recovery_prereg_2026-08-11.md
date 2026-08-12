# PRE-REGISTRATION — E-1, the observation-path multicycle

Branch `fuzz-v2-on-relanding`, base **`84cec65cfe`** (the census commit).
Census: `timing_recovery_census_2026-08-11.md`.

**COMMITTED BEFORE THE EDIT IS MADE AND BEFORE ANY BUILD OF IT.**
**OFFLINE ONLY. NO BOARD, NO FLASH.**

---

## §1 WHAT THE EDIT IS

**One `set_multicycle_path` pair in `hdl/nec_test.sdc`. No RTL. No gate.**

The census (F-2) found that Fmax is set entirely by paths from the ucore's
registers to the **free-running input-registration flops in `nec_bus`** — the
test harness's *observation* of the bus — and that this class is checked
**single-cycle** because the existing 4/3 CE multicycle only covers
`v30u_* → v30u_*`.

The edit tells the analyser what the RTL already does:

```tcl
set_multicycle_path -setup 2 -from $v30u_regs -to $obs_regs
set_multicycle_path -hold  1 -from $v30u_regs -to $obs_regs
```

where `$obs_regs` is `nec_bus`'s `ad_in_q[*]`, `bs_q[*]`, `qs_q[*]`, `rd_n_q`,
`ube_n_q`, `buslock_n_q` (28 registers in the CONTROL build) plus
`core_ad_hold[*]` (20 more, present only under `X1_AD_RETENTION`).

## §2 WHY IT IS TRUE — derived from the RTL, not asserted

Let `div = cfg_clk_div` (`nec_bus.sv`; documented *"even, >= 4"*, **reset
default 8**, `DIV_OF_RECORD = 8` in `sw/v30run.py`, and PINNED by
`s13_board.div_guard()` on every board probe).

* `tick_rise` is true when `div_cnt == div-1`; the core's `CE` **is**
  `bus_tick_rise` (`system_large.sv:497-501`). Call the sys edge on which the
  core's registers update **E0**; after it `div_cnt == 0`, and after `Ek`,
  `div_cnt == k`.
* `tick_fall` is true when `div_cnt == div/2 - 1`, so the edge that ACTS on it
  is **E(div/2)**.
* The observation registers sample on **every** sys edge, with no enable
  (`nec_bus.sv:201-209`).

**Every consumer of those registers in LARGE mode is tick-gated**, enumerated
exhaustively:

| consumer | line | gate | reads the sample taken at |
|---|---|---|---|
| `ad_early`, `bs_early`, `qs_early`, `ube_n_early` | 217-223 | `tick_fall` | `E(div/2 - 1)` |
| `mem_addr`, `mem_be` | 482-484 | `tick_fall && t_state == ST_T1` | `E(div/2 - 1)` |
| `mem_addr_match` | 577 | `tick_fall` | `E(div/2 - 1)` |
| `mem_wdata` | 467 | `tick_rise` | `E(div - 1)` |
| `cap_record` (the whole capture word) | 700-721 | `tick_rise` | `E(div - 1)` |
| `astb_seen` / `rd_low_seen` / … | 233-239 | `tick_rise` | `E(div - 1)` |
| `ad_in_q2` | 203 | *every clock* | its only consumer is line 420, **SMALL MODE ONLY** |

**So the earliest sample any large-mode consumer reads is the one taken at
`E(div/2 - 1)`, which has had `div/2 - 1` sys periods to settle.**

| `div` | periods actually available | maximum safe `-setup` |
|---|---|---|
| 4 | 1 | 1 (no relaxation) |
| 6 | 2 | 2 |
| **8 (the divider of record)** | **3** | **3** |

**REGISTERED CHOICE: `-setup 2`, NOT 3.** Two of the three periods available at
the divider of record. It is deliberately one period short of what the RTL
grants, so the claim survives `div = 6` as well as `div = 8`, and so a future
change to `tick_fall`'s phase has a whole sys clock of margin before it makes
the constraint a lie. `-hold 1` is the canonical `setup-1` companion, the same
pairing the existing 4/3 exception uses.

### §2.1 `core_ad_hold` — a separate argument, stated separately

`core_ad_hold[i] <= core_ad[i]` **when `core_ad_drv[i]`**
(`system_large.sv:594-596`). It is a transparent-latch-style retainer: it
re-captures on every sys clock the driver is on, and only the LAST capture
before the driver turns off is ever read back through `core_ad_eff`.
`core_ad_drv` is `core_ad_oe | {4'b0,{16{c_addrv_q}}}`, and `core_ad_oe` is the
`ad_oe_*` expressions — functions of CE-gated BIU registers — so when a bit is
driven at all in a CPU cycle it is driven for essentially the whole cycle
(`div - 1` sys clocks), not for one. The surviving capture is therefore at
`E(div-1)`, far beyond `-setup 2`.

### §2.2 SMALL MODE — the one place the derivation does not reach, and why it
### does not matter

In `cfg_small_mode`, `mem_addr`/`mem_be` capture on the `sm_astb` **level**
(`= qs_q[0]`) and `mem_wdata` on an edge of `sm_wr_n` (`= buslock_n_q`) — not
on a tick. Three facts, each checked against the artifact:

1. **`cfg_use_core=1 && cfg_small_mode=1` is never commanded.** `sw/v30run.py`
   `cfg()` sends `CFG <div> <waits> - 0 <use_core>` with the comment *"keep
   vector, force large mode (small=0)"* — **every** rig run forces large mode.
2. **The ucore has no small-mode pin behaviour at all**: `grep -rn 'ASTB\|astb'
   hdl/rtl/ucore/` is **empty**. With the core selected, small mode decodes
   queue-status bits as strobes and produces garbage independent of any timing
   constraint.
3. Even if it were commanded, `sm_astb` is a level held for ~half a CPU cycle,
   so `mem_addr` is a transparent latch frozen at ASTB's fall — the same
   argument as §2.1, and the surviving capture is late.

**This is a DECLARED LIMIT, not a hidden one**: the exception is written for
`cfg_use_core=1, cfg_small_mode=0, cfg_clk_div >= 6`, and that triple is stated
in the SDC beside it.

Note also that `div = 4` is **already** a documented-broken capture
configuration for an unrelated reason (`sw/v30run.py:44`: *"at div=4 the
address-phase sampling edge lands before the status pulse and the DISPLAY CLOCK
disappears from `bs_early` — two S10 readings were produced by it and
retracted"*). The exception does not newly restrict a configuration anyone uses.

## §3 THE PREDICTION — registered before the build

From the census's per-class worst slacks at the 31.250 ns constraint:

| | CONTROL | RETENTION |
|---|---:|---:|
| binding class today (`CORE→ANY`) | +6.333 | +5.492 |
| next class behind it (`ANY→CORE`) | +9.306 | +8.873 |
| implied delay of that next path | 21.944 ns | 22.377 ns |
| **predicted Fmax after E-1** | **45.6 MHz** | **44.7 MHz** |

**REGISTERED PREDICTION BANDS** (wider than the point estimates, because
relaxing a constraint changes placement and the next path may move):

* **P-1** CONTROL worst-of-2 lands in **[43.0, 47.0] MHz**.
* **P-2** RETENTION worst-of-2 lands in **[42.0, 46.0] MHz**.
* **P-3** After E-1, the top-60 census is **no longer** `v30u_eu → nec_bus`
  60/60. If it still is, E-1 did not reach the paths it names and the figure is
  not attributable to it.
* **P-4** The `.rbf` differs from the baseline's in both configurations.

## §4 THE BAR, AND THE REVERT RULE

**THE BAR (the wave's registered target): RETENTION worst-of-2 ≥ 41.0 MHz.**

**REVERT RULE — E-1 is reverted, not argued, if ANY of these:**

* **R-1** RETENTION worst-of-2 **< 41.0 MHz**. The edit is a constraint claim
  about correctness; it is only worth making if it buys the registered target.
  Buying less than the target is not a reason to keep a claim.
* **R-2** Any G6 essential goes RED in either configuration (E1 qsf check,
  0 errors/all stages Successful, Fmax ≥ 32, worst setup > 0, setup **and**
  hold TNS 0.000). ⚠ **Hold TNS is the live risk of this specific edit** — a
  `-hold` that is wrong shows up here and nowhere else.
* **R-3** Any row of the zero-delta ladder (§5) moves.
* **R-4** `P-3` fails, i.e. the class census shows the exception did not
  actually reach the named paths.

**Two draws per configuration, and the WORST draw is the figure.** If two draws
disagree by more than 1.0 MHz, a third is taken and the worst of three is the
figure.

## §5 THE ZERO-DELTA LADDER

E-1 changes **no RTL**, so every Verilator-side row is unchanged *by
construction*. It is run anyway, because "by construction" is how a vacuous
gate is born:

| gate | registered value |
|---|---|
| `check_core.py --core ucore --opcodes all --cases 0` | 169,000/169,000 |
| `check_core.py --core ucore --suite-dir tests/v30/8F.0` (via `--opcodes`) | 500/500 |
| the four HLT sweeps (⚠ `--waits 0/1/2/3`) | 97 · 93 · 45 · 44 = **279/283** |
| `ulockstep.py --golden all --cases 50` | 17,350/17,350 |
| `r7_lint.py` | PASS, 0 violations |
| `ss_lint.py --core ucore` | `SS_VERSION` 0x8D / 226 / `SS_TAG` 0x8DE2 / 214 flops |
| `gen_ucore_qsf.py --check` | PASS (it is E1 of G6 and runs on every build) |

⚠ **`hdl/nec_test.sdc` is an input of BOTH the `ucore` and the archived `fsm`
revision.** The exception's `-from` collection is `v30u_*` only, which is
**empty** in the FSM revision — the same guard the existing 4/3 exception uses,
and the reason it is a no-op there rather than a warning.

## §6 WHAT E-1 CANNOT ESTABLISH, STATED BEFORE IT IS RUN

**A timing exception is a CLAIM ABOUT THE REAL CIRCUIT that no offline gate can
falsify.** Verilator does not model it; `check_core` does not model it; G6
merely *believes* it. The falsifier for E-1 is **fabric**, and this wave is
forbidden the board.

Therefore, whatever E-1 measures:

* **E-1 IS NOT PROMOTED TO A FLASH BY THIS WAVE.** The next bitstream built on
  it owes a fabric confirmation leg, and the natural one already exists and is
  cheap: `check_ab_hw` first light (**MATCH 800 ×3**) reads the capture path
  end to end, and `x1_fabric baseline` scores 283 cells of it. **If E-1's
  constraint were false, the capture path is exactly what breaks**, and those
  two legs are exactly what would show it.
* **The registered fabric bar for the first bitstream carrying E-1**: first
  light MATCH 800 ×3, `x1_fabric baseline` reproducing its offline column with
  0 PASS/FAIL disagreements, and the closing `use_core=0` chip proof MATCH 800.
  Any deviation is attributed to E-1 first, because E-1 is the only thing that
  changed how the capture path is timed.
* **`nec_test.sdc` gains the derivation and the declared triple in comments
  beside the exception**, in the form the existing 4/3 exception uses —
  including its own falsifier — because `standing_gates.md`'s own repeated
  lesson is that a comment is not a gate but an *underived* constraint is worse
  than either.

## §7 WHAT IS NOT BEING TRIED, AND WHY

* **Registering `ad_o` in the BIU** — a cycle of latency on the pins. Timing
  behaviour change. Banned by the wave's terms.
* **Making the microcode ROM an M10K** — 9.4 ns of the 24.3 ns cone is the
  combinational LUT ROM, and a block RAM would be the single biggest win
  available. It costs a cycle of latency. Banned by the wave's terms, and
  **booked here as the largest known structural lever** should the terms ever
  change.
* **Shortening the `eu_bnd_take → pop_now → qs_e_now → ann_kill → ad_o` chain**
  — real, but it is the announcement machinery F54/F58 landed, and every
  restructuring of it is a behavioural risk on a mechanism that is currently
  confirmed in fabric. Not a zero-behaviour edit.
* **Reverting any re-landed mechanism** — they are silicon-match landings
  confirmed in fabric. The census attributes the cost to them; it does not
  condemn them.
