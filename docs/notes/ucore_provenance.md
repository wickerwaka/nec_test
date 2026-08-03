# ucore provenance ledger

Campaign: **ucore** — a new ROM-driven V30 core in `hdl/rtl/ucore/`, written
FROM the spec set the ucsim / ucsim-t campaigns produced, and taken through the
existing comparator stack to in-fabric A/B against the socketed chip.
Branch `ucsim`. Plan of record: `~/.claude/plans/zippy-swinging-meerkat.md`.

Same discipline as `docs/notes/ucsim_provenance.md` and
`docs/notes/ucsim_t_provenance.md`: every modelled behaviour is tagged with a
**provenance class**, carries **evidence**, and carries a **falsifier** — the
concrete observation that would refute it.

Provenance classes used here:

| class | meaning |
|---|---|
| **ROM** | read directly out of `docs/V20BITS.TXT` (microcode) |
| **PLA** | read directly out of `docs/pla3_outputs.txt` / `docs/pla_3.txt` |
| **SPEC** | transliterated from the reference model `sim/` (which is itself ROM/PLA/MEASURED-backed) |
| **MEASURED** | measured on the socketed chip in a prior campaign, cited by section |
| **ASSUMPTION** | not yet evidenced; must carry a falsifier and an owner stage |

---

## §0 GOVERNANCE (the rule every later section is read under)

**The correctness target at every gate is "identical to `sim/` clock-for-clock",
including the model's own registered non-exactnesses versus silicon** — the
907-case REP w0 family, Q2's unmeasured raise, V5's 154/188.

1. RTL-vs-sim divergence = a bug in the RTL. Fix the RTL.
2. RTL-vs-silicon divergence the sim does NOT share = a bug in the RTL. Fix the
   RTL.
3. RTL-vs-silicon divergence the sim DOES share = a **ledger finding**, booked
   here in the inherited taxonomy. Never a local RTL patch: the sim is the
   spec, so such a fix lands in `sim/` first and is re-gated there, and only
   then is regenerated / re-implemented in `hdl/rtl/ucore/`.
   **No ucore landing without the sim landing first.**

Reproducing a known-imperfect sim behaviour is the *pass* condition.

Hard constraints (inherited, must not be re-introduced): §24.8's 2-clock-grid
slot reading; the `d*` straight line; `LC8` / `pf_drain`; per-opcode timing
exceptions ("grep for one" stays true). `ready_prev` is the ONLY wait
mechanism. `R-STALL` is explicitly not implemented.

**SIMPLICITY** (standing user directive, verbatim in spirit): 80's-era
hardware, nothing on the die is wasted; a large fitted table, a many-cased rule
or a per-opcode special case is a signal of misunderstanding, not a
deliverable.

---

# STAGE U0 — clean baseline + scaffolding

## §1 Worktree restoration (the record)

The `biu-rebuild` campaign was retired (`docs/notes/biu_rebuild_retirement_2026-08-01.md`)
with a large uncommitted working tree. Before any ucore RTL work the coordinator
restored the worktree to HEAD. What that means concretely:

| item | disposition |
|---|---|
| tracked-file WIP (RTL, tooling, `v30_ss_pkg.sv` map, `ss_lint.py`) | **reverted** to HEAD; `git status --untracked-files=no` clean at U0 start |
| canonical content of that WIP | checkpoint commit **`62723c79d3`** ("Checkpoint V30 BIU/EU black-box campaign") + archive branch **`biu-rebuild`** (untouched by this campaign) |
| a second copy | `~/.cache/ucsimt-tmp/biu-rebuild-carryover-final-7797dedca6.patch` (1,111,488 B, sha256 `12e8065a16441d148b45beb190700b61bf8bf59426b17eca51db9d279922d3f3`), diff vs `7797dedca6` |
| untracked `docs/notes/biu_*`, `sw/biu_case*` etc. | left in place as **inert archives**; not inputs to ucore |

Branch at U0: `ucsim`, HEAD `7797dedca6` at start.

**Not inherited** (ucsim-t §26.10 part F): the biu-rebuild fitted corpus. None
of it is a ucore input.

## §2 FSM-core CLEAN BASELINE (deliverable 1)

ROADMAP standing rule: *do not cite the TB reference until it is rebuilt from a
clean tree*. Every RTL artifact in the repo before U0 — the Verilator binary and
the last flashed bitstream — was built from the dirty biu-rebuild tree. So the
existing FSM core's numbers were **not citable**. This section re-establishes
them from a clean HEAD.

**Build**: `rm -rf hdl/tb/obj_dir && python3 sw/check_core.py --build`
Verilator 5.032; RTL file list = `v30_ss_pkg.sv`, `tb_v30_core.sv`,
`v30_core.sv`, `v30_biu.sv`, `v30_eu.sv` (HEAD content, defines
`V30_BACKDOOR` + `V30_PFX_ASSERT`).
Binary `hdl/tb/obj_dir/Vtb_v30_core`, sha256
`00c33504d02c861b5fabf437f8493907a3aec2757d0300719d9b695a5e4bb30d`.

### HEAD contents check — the task-#31 ENTER fixes

Memory records two ENTER RTL bugs fixed at the end of task #31 and never
flashed. Both are **ancestors of HEAD** (`git merge-base --is-ancestor`):

- `efdd0b8d08` — "task #31: ENTER nesting-mask RTL fix (full 8-bit walk) + directed tranche"
- `d104673e44` — "task #31: fix ENTER PUSH-BP drop under waits (2nd ENTER bug) + waited tranche"

So the clean-HEAD baseline below INCLUDES both fixes. The standing debt is
therefore **bitstream-only** (the fixes are in RTL and in the TB reference, not
in the flashed part); U4's first ucore flash supersedes it.

### Baseline scoreboard (all on the clean-HEAD binary)

| gate | command | result | vs standing |
|---|---|---|---|
| v0.1 full | `sw/check_core.py --opcodes all` | **169,000 / 169,000 full** (cycles 169,000, arch 169,000) | matches |
| v0.1-w1 | `sw/check_core.py --opcodes all --suite-dir tests/v30/v0.1-w1 --waits 1` | **1,200 / 1,200 full** | matches |
| v0.1-w3 | `sw/check_core.py --opcodes all --suite-dir tests/v30/v0.1-w3 --waits 3` | **1,200 / 1,200 full** | matches |
| boot replay, RTL leg | `sw/check_boot.py` | **BOOT REPLAY MATCHES over 220 rows**, loop period 64 == real | see FINDING F2 |
| boot replay, sim leg | `sw/check_boot.py --timed 220` | **BOOT REPLAY MATCHES over 220 rows**, loop period 64 == real | matches |
| check_ff_t4 | `sw/check_ff_t4.py` | **PASS** — 9/9 seeds, 9 `SLOT_FF_T4` fires, invariant assert armed | matches |
| check_race_law | `sw/check_race_law.py` | **PASS 2/2** — checked-in `race_law.svh` exhaustively matches ROM; regeneration byte-identical (16,384/16,384 bits) | matches |
| check_mod3_illegal | `sw/check_mod3_illegal.py` | **PASS** — 128 goldens cycle-exact 128/128, arch-confined 128/128, moffs-exact 2/2 | matches |
| check_lc6_gate | `sw/check_lc6_gate.py` | **PASS** — 3 strio-single gadgets, `eu_rsv_strio`/`pick_t3` veto intact | matches |
| ss_lint (+ flop census) | `sw/ss_lint.py` | **PASS** — 82×2 BIU + 120×2 EU + tag = 203; 181 architectural flops all SSA-mapped, 0 whitelisted, 0 UNMAPPED | see §3 |
| prefix_clear_lint | `sw/prefix_clear_lint.py` | **PASS** — 20 `S_FIRST` sites, 4 PFX-KEEP, single source, no drift | matches |
| ea_step_lint | `sw/ea_step_lint.py` | **PASS** — all operand steps wrap via `ea_step2` | matches |
| optable selfcheck | `sw/optable.py --selfcheck` | **0 errors** (255 one-byte ops, 26 F0 whitelist forms) | matches |
| check_enter_nesting | `sw/check_enter_nesting.py` | **PASS** — MASK 512 goldens, WAITED 154 goldens, 0 unexpected divergences (§2.1) | matches |
| check_fuzz_bank | `sw/check_fuzz_bank.py` | **PASS** — 3,242 banked seeds, stable 3,242, worse 0, gen_drift 0 (§2.1) | matches |
| ss modes (scramble) | `sw/check_core.py --opcodes 89,8B,B8,E8 --cases 20 --ss-sweep 3 --ss-mode 1` | **80/80 full**; every swept freeze point `PASS first-diverging-k=none` | matches |
| ss modes (idempotence) | `sw/check_core.py --opcodes 89,8B --cases 12 --ss-sweep 3 --ss-mode 2` | **24/24 full**, no diverging k | matches |
| CE hold | `sw/check_core.py --opcodes 89 --cases 8 --ce-div 3 --ce-hold-check` | **8/8 full** (core state frozen on CE-low clocks) | matches |
| f4a_boundary battery | `sw/check_core.py --opcodes all --suite-dir tests/v30/f4a_boundary` | **160/160 full** | matches |
| f0lock tranche | `sw/check_core.py --opcodes all --suite-dir tests/v30/f0lock_tranche` | **400/400 full** | matches |

Sim-leg timed gates re-run on the same tree (second proof that `sim/` is
untouched): `sw/timed_gate.py --suite tests/v30/v0.1 --forms all`
**169,000/169,000 arch, 169,000/169,000 window, rows-exact 169,000,
row-diffs 0**; `v0.1-w1` and `v0.1-w3` **1,200/1,200** each, row-diffs 0;
`v0.1-w1 --forms EB` **200/200**, row-diffs 0.

`tests/v30/e1_iret_race` was attempted via `check_core.py --opcodes all` and
returned **0/0** — the suite has no forms matching that selector, so the run is
**vacuous**. Recorded as skipped, not as a pass (standing rule: a vacuous gate
is never quoted green).

Sim-side standing gates on the same tree (proving `sim/` is touched safely — the
only change is the read-only `dump-tables` subcommand, `3d777b06d1`):

| gate | result |
|---|---|
| `make -C sim test` | **disasm gate: PASS** (byte-exact vs `docs/V20UC.TXT`) |
| `sw/pla3_check.py` | **OK — 21 checks passed** |
| `sw/ucsim_check.py --suite tests/v30/v0.1` | **169,000 / 169,000 ARCH** (17.8 s) |

**Gates NOT run at U0, with reasons**: the `v0.2` (347,000), `v0.3` (3,699,998)
and `v20suite` (3,125,000) golden suites and the `t30_sweep.sh` pre-reflash bar
— those are the EU-decode-path change bar, and U0 changed no RTL. Board gates —
no board contact is authorised before U4. `sw/timed_*` whole-program gates — sim
gates, unchanged by U0 and re-scored under the ucsim-t ledger.

### §2.1 Long-running gates

**`sw/check_enter_nesting.py`** (the task-#31 gate; RTL/Verilator leg only,
takes no arguments) — **PASS**:

```
MASK (w0, nesting 0..255 x2): PASS | 512 goldens | max stack pushes 256 (nest=255=>256) | walk-mismatches 0
WAITED (154 goldens: nesting set x waits[0,1,2,3,7] + wrand x2 ctx): PASS
  walk-stream (value-bug invariant, ALL waits): PASS
  cycle-exact: 0 UNEXPECTED divergence(s); 0 booked #33-interleave cell(s) hit; 0 stale exclusion(s)
```

This is the direct confirmation that **both** task-#31 ENTER fixes are live in
the clean-HEAD RTL: the MASK tranche exercises the full 8-bit nesting walk
(`efdd0b8d08`) and the WAITED tranche's walk-stream leg is the PUSH-BP-drop
guard (`d104673e44`), green at every wait including `wrand`.

**`sw/check_fuzz_bank.py`** (regenerate → TB replay → re-classify vs banked chip
rows; the whole bank, `mc1` + `mc2` + `t30-brkem` + `t30-raw`) — **PASS**:

```
check_fuzz_bank: PASS | 3242 banked seeds | stable 3242 improved 0 worse 0
                | gen_drift 0 regen_err 0 | float-floor 0 | new-sig TIMING 0
```

Run without `--strict`; `--strict` differs only in failing on a new-signature
TIMING, and that count is **0**, so the `--strict` verdict is identical. This is
the heaviest single leg of the baseline (3,242 image regenerations + TB
replays, ~14 min CPU) and it is the one that proves the clean-HEAD RTL
round-trips the banked chip corpus with **zero** drift: `gen_drift 0` means every
regenerated image still hashes to its banked `image_sha256`, and `worse 0` means
no seed's chip-vs-TB verdict degraded.

## §3 ss_lint reconcile (deliverable 2)

**Reported state**: `sw/ss_lint.py`'s `EXPECT` dict was pinned to the retired
campaign's map — `SS_VERSION 0x13`, `SS_BIU_COUNT 88`, `SS_EU_COUNT 138`,
`SS_COUNT 227`, `SS_TAG 0x13E3` — while HEAD's `hdl/rtl/core/v30_ss_pkg.sv` is
`0x03 / 82 / 120 / 203 / 0x03CB`.

**Actual state after the restoration**: the reconcile required **no code
change**, because the mismatch never existed at HEAD. Evidence from the
carryover patch (`biu-rebuild-carryover-final-7797dedca6.patch`): the dirty tree
changed `v30_ss_pkg.sv` *and* `sw/ss_lint.py` **together** (patch lines
3195-3206 and 3810-3850), so the pair was self-consistent in the dirty tree, and
reverting the worktree reverted both. HEAD's package is `0x03 / 82 / 120 / 203`
and HEAD's `EXPECT` is `0x03 / 82 / 120 / 203 / 0x03CB`.

**Verified on HEAD**:

```
BIU: 82 symbols, each x2 in v30_biu.sv -> OK
EU: 120 symbols, each x2 in v30_eu.sv -> OK
ss_lint: PASS (82x2 BIU + 120x2 EU + tag = 203; constants OK)
BIU (v30_biu.sv): 76 architectural flops -> 76 SSA-mapped, 0 whitelisted, 0 UNMAPPED; 9 sim-only exempt
EU  (v30_eu.sv): 105 architectural flops -> 105 SSA-mapped, 0 whitelisted, 0 UNMAPPED; 2 sim-only exempt
ss_flopcensus: PASS (181 architectural flops, all SSA-mapped or whitelisted; 0 whitelist entries)
```

So the correct entry is not "an instrument was pinned to a phantom and was
fixed" but "**the phantom was the dirty worktree, and restoring it was the
reconcile**". Recorded this way deliberately: the campaign's discipline is that
a gate result is only citable together with the tree it was produced from.

*Falsifier*: `sw/ss_lint.py` failing on a clean `ucsim` checkout, or the SS map
in `v30_ss_pkg.sv` diverging from `EXPECT` without a matching commit that bumps
both.

*Owner for ucore*: U3 introduces `v30u_ss_pkg.sv` with a NEW map and an
`SS_VERSION` 0x80-family bit, plus `ss_lint --core ucore`. The FSM map above is
frozen as the reference, not extended.

## §4 Generated tables and GATE G0 (deliverable 3)

### §4.1 What is generated

| artifact | shape | addressed by | class | source |
|---|---|---|---|---|
| `hdl/rtl/ucore/ucrom.hex` | 1028 × 29b | `{bank[8:0], row[1:0]}` | **ROM** | `docs/V20BITS.TXT` |
| `hdl/rtl/ucore/ucdecode.hex` | 8192 × 10b = `{valid, bank[8:0]}` | `{page[2:0], opc[7:0], rowgrp[1:0]}` | **ROM** | `docs/V20BITS.TXT` activation patterns |
| `hdl/rtl/ucore/pla3_tables.svh` | 3 × 256 × 14b + named accessors | `{mode[1:0], opcode[7:0]}` | **PLA** | `docs/pla3_outputs.txt` |
| `hdl/rtl/ucore/ucrom_census.json` | — | — | — | the census |

Generator `sw/gen_ucore_tables.py` (+ helper `sw/ucore_tables.py`, a
transliteration of `sim/ucrom.cpp` `UcRom::load` / `UcRom::build_decode`, whose
own normative source is `docs/V20UCDIS.PAS` procedure `ReadBits`). The `.hex`
files are `$readmemh` word lists (not Intel HEX) and carry **no comments**, so
that Verilator and Quartus read the identical bytes.

Column names and accessor semantics in `pla3_tables.svh` mirror
`sim/pla3_table.h` one-for-one (`PLA3_BYTE_ONLY` … `PLA3_INCDEC_NO_CY`,
`PLA3_XOP_MASK`, the 16 `PLA3_BL1_*` values, `pla3_is_prefix`).
Verilator lints clean (`-Wall`; only `UNUSEDPARAM` on the column constants,
which a stub wrapper does not use).

### §4.2 GATE G0 — RESULT: **GREEN**

`python3 sw/check_ucore_tables.py`, three legs:

- **LEG A** — an *independent* re-parse of `docs/V20BITS.TXT` and
  `docs/pla3_outputs.txt`, written inside the checker from `V20UCDIS.PAS`
  (`ReadBits`, lines 103-160) and **not** importing the generator's helper —
  diffed against `sim/v30sim dump-tables`. This is what stops a bug shared
  between generator and helper from passing by self-consistency.
- **LEG B** — the emitted artifacts read back as data and diffed against the
  same sim dump.
- **LEG C** — `sw/gen_ucore_tables.py --check` (on-disk artifacts are what the
  generator produces today).

```
LEG A:  ucrom rows 1028/1028 · decode(native) 8192/8192 · decode(emu) 8192/8192
        pla3 native 256/256 · mode8080 256/256 · ext 256/256
LEG B:  ucrom.hex 1028/1028 · ucdecode.hex 8192/8192
        pla3_tables.svh native 256/256 · mode8080 256/256 · ext 256/256
LEG C:  4 artifacts current
=> 1028 rows + 8192 micro-addresses + 768 PLA entries = 9988 entries
   byte-identical to sim/, on both legs.
```

Sim-side hook: `sim/main.cpp` gains **one** read-only subcommand,
`v30sim dump-tables` (commit `3d777b06d1`). It re-encodes each row from the
*decoded fields* rather than echoing the stored word, so a field-position drift
in either implementation shows up as a diff instead of cancelling out. No
execution path changed; the sim-side standing gates in §2 were re-run on that
build.

*Falsifier for G0*: any single entry of the 9988 differing, on either leg.

**Toolchain round-trip** (the artifacts are consumable, not just correct): a
throwaway Verilator TB `$readmemh`-ing both files reproduces the expected
contents —

```
ucrom[0]=136b9cb0 (== sim dump `row 0000 136B9CB0`)   ucrom[1027]=1fffffff   nonzero=1028
ucdec[0]=200      ucdec[7176]=278 (= valid | bank 120, the 0x1C08 native resolution)
                  nonzero=1656   valid=1656 (== the mapped count)
```

### §4.3 Census

`ucrom.hex` / `ucdecode.hex` census (from `ucrom_census.json`):

- 257 activation patterns, 1028 rows × 29b.
- 13-bit match space 8192: **1,656 mapped, 6,536 unmapped**, **1 ambiguous** —
  matching `v30sim info` exactly (`unmapped addrs 6536 of 8192`,
  `ambiguous addrs 1 of 8192`).
- 1,275 (page, opcode) pairs have at least one mapping; for **241** of them the
  selected bank varies with `rowgrp`.

**The ambiguous address (A30 / ledger R4)** — the census entry:

| field | value |
|---|---|
| address | `0x1C08` = `111.00000010.00` (page 7, opcode `0x02`, rowgrp 0) |
| first matching bank | 119 → rows `01DC..01DF` |
| second matching bank | 120 → rows `01E0..01E3` |
| **emitted (native)** | **bank 120, rows `01E0..01E3`** — identical to `sim/ucrom.h::bank_of(emu=false)` |
| recorded, not emitted | bank 119 (8080-emulation resolution) |

Provenance: the interrupt-acknowledge vector fetch. Exactly two activation
patterns match and the 13 dumped address bits cannot separate them, so the real
decoder takes a 14th input (8080-emulation mode); the goldens show native mode
running the second bank (two INTA cycles, vector from the second). ucore has no
BRKEM path, so emitting a second table would be dead silicon — SIMPLICITY.

*Falsifier*: a silicon capture in which a native-mode INTA vector fetch follows
the `01DC..01DF` schedule (one INTA, vector off the high lane, AW
saved/restored) rather than `01E0..01E3`.

## §5 FINDINGS

### F1 — the micro-PC is 15 bits, not 13; the flattening is TWO tables

**Class: SPEC.** The plan's architecture note describes flattening the 257
match patterns into "one direct-addressed 8192×30b BRAM". The dumps do not
support a single 8192-entry word ROM. The micro-PC is

```
upc = {page[2:0], opc[7:0], rowgrp[1:0], row[1:0]}      -- 15 bits
```

and the activation patterns are matched against the **low 13 bits only**
(`{page, opc, rowgrp}`); `row` then indexes the winning bank's four rows.
Authority, `sim/exec_impl.h:796`:

```cpp
int bank = rom_.bank_of(m_.upc.page, m_.upc.opc, m_.upc.rowgrp());
...      = &rom_.op(bank * 4 + m_.upc.row());
```

(`sim/state.h:106`: `loc = {rowgrp[1:0], row[1:0]}`.) Evidence that this is not
a formality: for 241 of the 1,275 mapped (page, opcode) pairs the bank actually
changes with `rowgrp`.

So the build-time flattening emits a **decode** table and a **word** table. The
substantive property the plan asked for is preserved exactly: all 257 patterns
and the fixed-priority resolution are resolved at BUILD time and the RTL carries
**zero** match/priority logic.

Resource arithmetic (M10K = 10,240 b):

| layout | bits | M10K (min) |
|---|---|---|
| `ucdecode` 8192×10 + `ucrom` 1028×29 (**emitted**) | 111,732 | **10.9** |
| single fully-flat 32768×30 image over the whole 15-bit upc | 983,040 | 96.0 |

The emitted split sits at/below the plan's own ~15-24 M10K envelope; the
fully-flat single-read alternative is 4-6× over it and is 32× redundant against
the 1028 rows the die actually holds — which the SIMPLICITY directive rules out
as a default.

*Consequence routed to U1*: the fetch path performs a decode lookup and a word
lookup. They are NOT both on the per-row critical path — `bank` only changes
when `{page, opc, rowgrp}` changes, whereas `row` advances every row — which is
also how the part is organised (a match PLA feeding a 1028-row ROM). U1 owns the
BRAM pipelining decision (flow-through vs registered) against this shape.

*Falsifier*: a demonstration that `bank_of(page, opc, rowgrp)` is equal to
`bank_of(page, opc, row)` for every reachable micro-PC — which would collapse
the two tables into one.

### F2 — `check_boot.py`'s RTL leg was stale vs the TB (instrument failure)

**Class: instrument.** On the freshly built clean-HEAD binary the default
(Verilated RTL) leg of `sw/check_boot.py` reported **206 rows differ over 220**.
Root cause: the leg launched the TB without `+mirror=1`. The TB memory became 1
MB **flat** in `c78421fe07` ("flat 1MB TB memory + emission mirror-collision
guard"; `amask` defaults to `FFFFF`), but the boot capture comes from the 64
KB-wired capture board, so the reset vector at `FFFF0` must alias into the 64 KB
image. Without the alias the core fetched unwritten memory from release+9 on.

The sim leg was never affected — it has always been explicit
(`sim/timed_runner.cpp`: `biu.set_mirror(true); // the capture board's 64 KB
wiring`).

Fixed in `378621e900` (one plusarg). Both legs then land on the standing
number: **BOOT REPLAY MATCHES over 220 rows**, loop period 64 == real, on both
the RTL and the `--timed` engine.

This is a fresh instance of the standing meta-finding in
`docs/notes/standing_gates.md` (§"the vacuous-gate pattern"): a gate that fails
loudly is not the danger; a gate whose *harness* drifted away from the RTL it
grades is. Booked because the ROADMAP's "rebuild from a clean tree before
citing" rule is exactly what surfaced it.

*Falsifier*: `sw/check_boot.py` (either leg) reporting anything other than 220
matching rows on a clean build with an unchanged `sw/testdata/largemode_boot_real.hex`.

## §6 U0 gate ledger

| gate | bar | result |
|---|---|---|
| **U0.1** FSM clean baseline recorded | numbers on record, deviations booked | **PASS** — §2. Every re-scored gate landed on its standing number; the only deviation was F2, an instrument defect, now fixed and green. The FSM core itself showed **zero** regressions on a clean-HEAD build. |
| **U0.2** ss_lint / ss_flopcensus green on HEAD | exit 0 | **PASS** (§3) |
| **U0.3 = G0** generated tables byte-match the sim | 8192 + 1028 + 768 entries, all legs | **PASS — 9988/9988** (§4.2) |
| **U0.4** sim-side standing gates green | `make -C sim test`, `pla3_check`, a functional v0.1 run | **PASS** (§2) |
| **U0.5** `hdl/rtl/ucore/` exists with the governance rule at the top of its README | — | **PASS** |

**GATE U0: GREEN.**

## §7 U1 handoff

Open items U1 inherits from this stage:

1. **F1 is a design input, not a defect.** `v30u_ucrom.sv` gets the two
   build-time tables (`ucdecode` → `ucrom`), not one. The bank lookup is NOT on
   the per-row critical path (it re-evaluates only when
   `{page, opc, rowgrp}` changes); the plan's flow-through-vs-registered M10K
   decision should be taken against that shape, and F2's lesson applies —
   re-verify against the sim rather than against the plan's prose.
2. **The FSM baseline in §2 is the reference to beat**, and it is now citable:
   it was produced from a clean HEAD tree with a binary whose sha256 is
   recorded. Any ucore number is compared to it, never to a pre-U0 figure.
3. **`sw/check_ucore_tables.py` is a standing gate** (registered in
   `docs/notes/standing_gates.md`) and must stay green through every later
   stage; `sw/gen_ucore_tables.py --check` is its staleness leg.
4. **Task-#31 debt restated precisely**: both ENTER fixes are in HEAD RTL and
   are proven live by `check_enter_nesting`. What is outstanding is only the
   **bitstream**. U4's first ucore flash supersedes it — record the
   supersession there.
5. **Not yet done, by design**: no `v30u_*.sv`, no `sw/ulockstep.py`, no
   `hdl/files_ucore.qip`, no `--core {fsm,ucore}` switch in `check_core.py`.
   U0 added no RTL to the build and no core RTL to `hdl/rtl/ucore/`.

---

# STAGE U1 — the BIU, and the lockstep instrument

## §8 What U1 built

| artifact | what it is |
|---|---|
| `hdl/rtl/ucore/v30u_biu.sv` | the mechanism BIU — a transliteration of `sim/biu_timed.{h,cpp}`, M1-M23 + M2r/M5b + F1/F2/F3, each carrying its ledger tag |
| `hdl/rtl/ucore/v30_core.sv` | the top: port list byte-compatible with HEAD `hdl/rtl/core/v30_core.sv` (chip pins, CE/CE_HALF, SS group, V30_BACKDOOR incl. `scr_en`/`scr_qop` + `dbg_*`), SS staging + tag + the three SYNTHESIS assertions |
| `hdl/rtl/ucore/v30u_eu.sv` | the stage-U1 placeholder: every output tied to its inert value, no state, no SS addresses |
| `hdl/rtl/ucore/v30u_ss_pkg.sv` | the new map, `SS_VERSION 0x80`, **94 BIU addresses**, `SS_EU_COUNT 0`, `SS_COUNT 95` |
| `sim/biu_script.cpp` + `v30sim biu-script` | the model's BIU driven ALONE by a script — the missing oracle leg (see §11) |
| `sw/ulockstep.py` | the standing instrument: same script through both legs, raw `r`-records diffed clock-for-clock, first divergence ±8 |
| `sw/check_core.py --core {fsm,ucore}` | engine selection: RTL file list + include path + obj_dir + one define.  `fsm` is the default |
| `sw/check_boot.py --core {fsm,ucore}` | the same switch on the boot leg, plus a "matching prefix" report |

**The package name is deliberately `v30_ss_pkg` in both cores.** The two cores
are drop-in alternatives selected by the FILE LIST; `hdl/tb/tb_v30_core.sv`
imports the package by name and must not be parameterised on the engine.

## §9 GATE U1 — RESULT: **GREEN on the scripted set; the boot leg is VACUOUS**

`python3 sw/ulockstep.py --suite --waits 0,1,2,3` — **32 / 32 scenarios
LOCKSTEP**, i.e. every clock of every scenario identical to the model under the
column policy of §10:

| scenario | what it exercises | w0 | w1 | w2 | w3 |
|---|---|---|---|---|---|
| `fill-from-empty` | the fetch scheduler from an empty queue; M4/M7 refill threshold; M6 landing block; the queue filling to 6 | 64 | 64 | 64 | 64 |
| `starved-pops` | a byte consumed every clock: M3's latency pipeline (poppable at e+3), M7/M7b resume | 45 | 65 | 75 | 85 |
| `preloaded-drain` | a FULL injected queue then a burst of pops: the resume decision with the queue crossing the threshold | 38 | 38 | 38 | 38 |
| `paced-pops` | pops every 3 clocks: M8's `pop = max(demand, ready)` with the DEMAND binding | 29 | 29 | 29 | 29 |
| `odd-base` | an odd fetch pointer: the single upper-lane byte fetch (+1) and the even/odd width alternation | 34 | 34 | 39 | 44 |
| `flush-inflight` | F1's parked QS=E, F3's flush-only T4 eval point, M12's latch invalidation, M19's standing request | 39 | 39 | 39 | 39 |
| `flush-idle` | a flush on an idle bus: the E takes the port at once and the redirect commits at the end of the flush clock (M12) | 57 | 57 | 57 | 57 |
| `flush-double` | two flushes back to back, the second while the first redirect is in flight (doomed on both sides of the announcement) | 43 | 43 | 43 | 43 |

(the numbers are the clock counts compared, all identical on both legs).

The wait sweep is what makes this a test of the SPINE rather than of w0: at w0
the eval instant sits at T3 and at w>0 at T4, so every landing window
(`grn`/`infl`/`absorb`) and every status release moves with it.  The same eight
scripts pass at all four wait levels with no wait-keyed term in the RTL.

**Sim-side and FSM-side gates on the same tree**: `make -C sim test` disasm
gate **PASS**; `sw/pla3_check.py` **OK, 21 checks**; `sw/check_ucore_tables.py`
**PASS — G0 GREEN, 9988/9988**; `sw/check_core.py --opcodes all` (FSM)
**169,000 / 169,000 full**, matching §2's clean-HEAD baseline number for number;
`sw/check_boot.py` (FSM, both legs) **220 rows**; `sw/ss_lint.py` **PASS**;
`--ce-div 3 --ce-hold-check` **0 violations** on the rewritten engine-neutral
probe.

## §10 FINDINGS

### F3 — the boot capture is NOT a BIU-only stream; `check_boot --core ucore` is VACUOUS at U1

**Class: SPEC.** The stage brief asked for `check_boot.py --core ucore` at
220/220 and, failing that, for the maximal EU-free prefix.  Measured, with the
EU stubbed: **204 of 220 rows differ, and the matching prefix is 7 rows.**

That prefix is **vacuous**, and this is the honest reading rather than a
7-row pass: `check_boot`'s own column policy compares `bs` only from
release+8 and `t`/`ube`/`addr`/`data`/`ps` only from release+9, so rows 0-6
carry no compared content beyond `qs`, which is idle on both legs.

The cause is structural, not a defect.  The chip's reset sequence is a
MICROCODE MARCH: the ROM rows load CS=FFFF / IP=0000 and end in a **FLUSH**,
and the capture shows exactly that — QS=**E** at release+7, the first CODE
status at release+8, the first CODE T1 at release+9.  Those three clocks are
M19's standing request being raised by the flush and granted at the flush
clock's eval.  With no sequencer there is no march, no flush, and the ucore BIU
instead free-runs its prefetcher from reset and is ~2 fetches ahead by
release+9.

*Consequence*: the boot gate is **routed in full to U2**, where the sequencer
runs the reset march out of `ucrom.hex`.  It is not booked as a ucore
divergence — the two legs are not running the same machine.

*Falsifier*: a demonstration that the release+7 `E` and the release+9 first T1
can be produced by the BIU alone from the reset state, without a micro-row
asserting the flush.

### F4 — `e_from` is a term of the FLUSH CLOCK, not a flop

**Class: SPEC (RTL bug, found and fixed by the instrument).**  The model's F1
computes `e_from_ = (a fetch owns the port) ? clk+1 : clk` and then tests
`c >= e_from_`.  The first RTL cut carried that as a one-clock flop set at the
flush edge — which blocks the clock AFTER the flush instead of the flush clock
itself.  `flush-double` at **w1** is the one scenario in the set that separates
the two: the second flush lands on the redirect fetch's T4, and the chip shows
its `E` on T4+1 while the flopped version pushed it to T4+2.

The fix is also the simplification: for every clock after the flush the test
`c >= e_from` is vacuously true, so the term is purely combinational on the
flush clock and the flop is deleted (SS map 95 → 94 addresses).

*Falsifier*: any flush whose `E` is deferred by more than the flush clock
itself while no fetch owns the queue port.

### F5 — the eval instant needs no wait knowledge: `dage >= 3 && ready_prev`

**Class: SPEC.**  The model computes the completion-eval instant from the wait
count it knows (`eval_i = w==0 ? 2 : 3+w`, plus M22's `max(disp+3, ...)` branch
at zero waits and M21's index-1 HALT case).  The RTL has no wait count, and
does not need one: with `dage` = the cycle's age counted from its own DISPLAY
clock and `ready_prev` = the registered READY pin,

```
eval instant  ==  the first clock with  dage >= 3  and  ready_prev
```

reproduces all three of the model's branches at once — at w0 that is T3, at
w>0 it is T4 (READY is high only from the last Tw), and M22's
"counted from the DISPLAY, not from the T1" IS `dage >= 3`.  The HALT
pseudo-cycle keeps its own measured index-1 release (`dage >= 2`,
wait-independent) and is the ONLY exception in the module.

This is the campaign's SIMPLICITY directive paying out: the RTL is SHORTER
than the model here because the model has to reconstruct what the hardware
simply has.  Validated by the wait sweep in §9 (32/32 at w0-w3).

### F6 — one number initialises all three landing windows

**Class: SPEC.**  M3 (`ready = e+3`), M7b (`infl to = e+2`) and F1(b)
(`absorb = e+1..e+2`) are three separately-measured windows.  In the RTL they
are three TTL counters loaded at T4 from the SAME value, `2 - sev`, where `sev`
is the distance from this cycle's eval to its T4 (1 at w0, 0 under waits, 2 in
M22's delayed-T1 corner).  `eu_done` (e+2) is the same number again.  No wait
term, no table.

## §11 THE OBSERVATIONS THAT NEEDED NEW TOOLING (and what did not change)

1. **`v30sim biu-script`** (`sim/biu_script.cpp`, one new subcommand, plus a
   forward declaration and a dispatch line in `main.cpp`).  `timed-run` and
   `timed-boot` both run the interpreter, so neither can be the oracle for a
   BIU-only RTL.  The subcommand instantiates `sim::BiuTimed` and calls the Bus
   concept's own methods in the order a script names.  **It adds NOTHING to the
   model**: no BiuTimed source line changed, and the sim-side standing gates
   were re-run on the resulting build (§9).

2. **The TB's scripted-consumer driver** (`+scr=<file>`).  ENGINE-NEUTRAL by
   construction: it drives `scr_en` / `scr_qop` and the V30_BACKDOOR injection
   group only — ports BOTH cores already carry — and records the ordinary `r`
   stream.  It reads the SAME script file as the sim leg.

3. **The TB's in-DUT probes are now `` `ifdef V30_FSM_PROBES ``.**  This was
   FORCED: the `d` / `g` / `p` dumps, the coverage readout and the CE-hold
   check reach inside the DUT by hierarchical reference (`dut.u_eu.state`,
   `dut.u_biu.cov_*`, ~75 signals) and are bound to the FSM core's internal
   names, so the TB would not ELABORATE against any other engine.  The TB
   itself is engine-neutral — it drives and samples chip pins plus the backdoor
   group.  `--core fsm` passes the define, so the FSM build is unchanged; the
   CE-hold check was additionally rewritten as one probe CONCATENATION per
   engine so the RULE stays identical for both.  **The FSM baseline was fully
   re-verified afterwards** (§9: 169,000/169,000, boot 220, ss_lint, CE-hold).

4. **The scripted-consumer protocol gained a FLUSH command.**  The FSM top ties
   `q_flush` low under `scr_en`, so its scripted mode cannot reach the F1 /
   F3 / M12 / M19 family at all.  ucore spends the otherwise-unused `2'b10`
   (E) `scr_qop` encoding on "flush + redirect to `bkd_cs`:`bkd_fetch_ip`".
   Recorded here because it is a divergence between the two cores' BACKDOOR
   contracts, not between their machines.

5. **A phase contract in the TB driver, learned the hard way.**  The first cut
   assigned `scr_qop` in the same time slot as the recording posedge and raced
   the recorder, making the RTL leg look exactly one clock fast on every
   scenario.  Control between ops now always sits just after a NEGEDGE, and the
   service test reads a `qs_p` flop carrying the row's own QS.  This is the
   §"vacuous-gate pattern" again in miniature: the harness, not the DUT.

6. **ONE interface contract, booked for U2.** The model's `note_halt` /
   `unhalt` land in `tick(c)`'s PRE-ROW block, which in RTL is the edge ending
   `c-1`.  `eu_halt` / `eu_unhalt` are therefore specified to LEAD by one
   clock — the same one-row-early control decode F2 already measures for SUSP.
   Nothing else in the interface leads.  HALT is not reachable from the
   scripted-consumer protocol, so this is UNVERIFIED at U1 and is U2's first
   HALT gate.

## §12 The ulockstep column policy (and why it is not "all fields")

`sw/ulockstep.py` applies `sw/check_core.py::diff_rows`'s policy verbatim —
bus/data compared only on rows where the pins are DRIVEN:

```
every row          t, bs, qs, ube_n
driven rows only   ad_data, ps      (T1/T2/T3/Tw, or bs != PASV)
address rows only  ad_addr          (T1, or Ti/T4 with bs != PASV)
```

Two reasons, both pre-existing:

* **Idle-row retention.** The model REPLAYS the pre-window fetch address
  sequence (`queue_preload`, T0 open item 3) so its idle pins carry the
  pre-window data phase; the RTL is handed a backdoor state with no history.
  check_core has masked exactly this since the FSM core's first gate.
* **`ad_addr` is the MID-clock sample.** It is an ADDRESS only at T1 and on an
  announcing row; on a T2/T3/Tw row of a read the composed bus is whatever the
  MEMORY drives, which the model does not model and no golden samples.

*Falsifier for the policy*: a golden row whose verdict depends on a field this
tool masks.

## §13 SS map state

`v30u_ss_pkg.sv`, `SS_VERSION 0x80` (the 0x80 family bit, so a ucore stream can
never be mistaken for an FSM one).  **94 BIU addresses**, each `SSA_B_*` symbol
appearing EXACTLY TWICE in `v30u_biu.sv` (one write-decode arm, one read-mux
arm) — the inherited audit invariant, honoured from the first commit.
`SS_EU_COUNT` is 0 and `SS_COUNT` is 95; U2 seeds the EU region and the map is
append-only from there.  `sw/ss_lint.py` still targets the FSM map (frozen
reference); a `--core ucore` mode is U3's deliverable per §3.

## §14 U2 handoff

1. **The sequencer is the gate-opener.** F3 says the boot stream needs the
   microcode reset march; the 220-row boot parity and every batch-mode gate
   wait on it.  `ucdecode.hex` → `ucrom.hex` (F1's two tables) is the fetch
   path; `upc = {page[2:0], opc[7:0], rowgrp[1:0], row[1:0]}`.
2. **The BIU's EU-facing port set is what U2 must drive**: `q_pop`/`q_first`/
   `q_flush`(+cs/ip), `eu_post`/`eu_bs`/`eu_addr`/`eu_seg`/`eu_word` against
   `eu_slot_busy` (M10), `eu_pair`/`eu_wdata` (S5 + M5b), `eu_rd_done`/
   `eu_wr_done`/`eu_opr_free` (the F/OPR interlock), `eu_susp`/`eu_resume`
   (F2, one row early) and `eu_halt`/`eu_unhalt` (§11.6, one clock early).
3. **Unexercised at U1, by construction**: everything behind an EU request —
   M10's slot, M13's MD-selected OPR release, M5b on a paired store, M15's
   INTA, M16/M17/M20/M21's HALT, M22's expiry (reachable only through a woken
   HALT), M23's late-T1 address one-shot.  They are IMPLEMENTED and lint-clean
   but have never fired; U2 must gate each as its rung lands, and the standing
   assertion set in `v30u_biu.sv` (`sev` bound, announcement-age saturation,
   queue overflow, green-count) is armed for all of them.
4. **`sw/ulockstep.py` is the standing bring-up tool**, and `--utrace` is its
   attribution channel: one `u` row per clock naming the eval-instant terms and
   the QS-port arbiter's inputs, to be read against the model's own
   `V30SIM_EVALTRACE` `ET`/`QT` lines.  Risk #1 (the pumped-clock inversion) is
   what it exists for.
5. **Standing gates U2 must keep green**: `sw/ulockstep.py --suite --waits
   0,1,2,3` (32/32), `sw/check_ucore_tables.py`, and the whole FSM baseline of
   §2 after any shared-file change.

## §15 U1 gate ledger

| gate | bar | result |
|---|---|---|
| **U1.1** ucore top + BIU elaborate against the UNMODIFIED-in-substance TB | Verilator 0 errors | **PASS** — the TB needed only the engine-specific probes guarded (§11.3), which is engine-neutral |
| **U1.2** `--core {fsm,ucore}` swaps the engine | both build, `fsm` default | **PASS** |
| **U1.3 = GATE U1** lockstep vs the model on the scripted set | 100 %, waits 0-3 | **PASS — 32/32 scenarios, every clock** (§9) |
| **U1.4** boot parity 220 rows | 220/220 | **NOT MET — and VACUOUS at U1** (finding F3); routed in full to U2 |
| **U1.5** FSM baseline re-verified after the shared-TB change | the §2 numbers | **PASS — 169,000/169,000 full**, boot 220 both legs, ss_lint, CE-hold 0 |
| **U1.6** sim-side standing gates green | disasm, pla3, G0 | **PASS** |
| **U1.7** SS map seeded, exactly-twice from the first commit | lint-grep | **PASS** — 94×2, `SS_VERSION 0x80` (§13) |

**GATE U1: GREEN on its own bar (the scripted lockstep set), with the boot leg
booked as F3 and carried to U2.**

---

# STAGE U2 — the EU: sequencer, loader march, datapath, ALU

**STATUS: IN FLIGHT.  Gate U2 (G3) is NOT met.**  Two rungs of the ladder are
green; the report below is the state as it stands, with every number
re-runnable.

## §16 What U2 built

| artifact | what it is |
|---|---|
| `hdl/rtl/ucore/v30u_ucrom.sv` | the two build-time tables of F1 (`ucdecode` 8192×10 → `ucrom` 1028×29), read COMBINATIONALLY off the `upc` flop |
| `hdl/rtl/ucore/v30u_eu.sv` | the EU: the five stall wires, the datapath muxes, the ALU (combinational ops + the ONE shared iterative stepper), the combinational act outputs |
| `…/v30u_eu_step.svh` | the model's program as states — `loader_decode` + `run_micro`'s control |
| `…/v30u_eu_row.svh` / `_poste.svh` / `_wd1.svh` / `_cond.svh` | one micro-row's body, the post-`E` row, `wr_dst1`, `cond_true` |
| `…/v30u_eu_ss_write.svh` / `_ss_read.svh` | the SS arms, generated; each `SSA_E_*` exactly twice |
| `v30u_biu.sv` (delta) | the three EU-facing gaps U1 left UNEXERCISED: split accesses, the read-side A0 swapper, `opr_held` as a count, `q_ripe_lead` |

### The inversion, stated once

The model pumps the clock; the RTL cannot.  So:

* every port the BIU samples is a COMBINATIONAL function of EU REGISTERS
  ONLY — the state, the row standing on `upc`, the datapath;
* `charge(n)` = "this state occupies n clocks";
* every `while (…) tick()` = a STALL (the state is re-entered, its acts
  withheld): `stall_q` / `stall_opr` / `stall_slot` / `stall_retire` /
  `stall_pin`;
* a model step that charges NOTHING is a ZERO-COST state executed inside the
  edge that computed it, by a bounded chain loop.  **That loop is the whole
  answer to "several model steps ride one clock"** — the pre-popped opcode,
  the pure-decode logic, the EA adder, the operand binding and `step()`'s own
  return all cost nothing, and if any of them were given a clock the whole
  decoder schedule would slip.  Getting a `stop` wrong on a zero-cost arm is
  the single most common bug class found in bring-up.

## §17 THE RUNG LADDER — as it stands

`python3 sw/check_core.py --core ucore --opcodes <form>`, v0.1 at w0,
500 cases per form.

| rung | form | full | note |
|---|---|---|---|
| 1 | `B8` | **500/500** | GREEN — immediate loads: the sequencer, the loader's no-ModR/M schedule, the E-row pre-pop |
| 2a | `8A` | **500/500** | GREEN — ModR/M + EA + disp8/disp16 + the pre-decode operand read + `wait_opr` |
| 2b | `8B` | 302/500 | split (unaligned) word loads outstanding |
| 2c | `88` | 134/500 | the store path |
| 2d | `89` | 121/500 | the store path |

Standing gates on the same tree: `check_ucore_tables` **9988/9988 (G0)**,
`ulockstep.py --suite --waits 0,1,2,3` **32/32 LOCKSTEP**, FSM spot-check on
the same five forms **2500/2500**.

## §18 FINDINGS

### F7 — the EU reads the BIU's BLOCKING state from a second process
### *(RESOLVED at U2 pass 2 — the contract is in §20)*

**Class: instrument / composition.**  `v30u_biu` is one process whose
registers change meaning inside the edge (that IS its transliteration of
`tick()`).  `v30u_eu` is a second process reading them on the same edge, so
what it observes is a SCHEDULING fact, not a contract.

MEASURED, both ways round:

* read LIVE (the levels `q_ripe` / `q_byte` / `q_cnt` / `eu_slot_busy` and the
  pulses `eu_rd_done` / `eu_wr_done` / `eu_opr_free` alike) — B8 500/500,
  8A 500/500;
* LATCHED into clock-c flops in the EU — B8 **500 → 123**, every pop one clock
  late, all four MOV forms to zero.

So the levels a Verilated edge presents ARE the clock-c values.  **REFUTED:**
"the EU must latch the BIU's levels".  Booked, not patched: the composition
wants an explicit clock-c handshake published by the BIU (a `q_popped` strobe,
a `slot_free` level) rather than shared blocking registers, and until it has
one this is a dependency on Verilator's ordering that Quartus need not share.
*Falsifier*: any simulator or synthesis flow in which the same RTL puts the
first pop on a different clock.

### F8 — the post-`E` row overlaps the successor's decode, so it cannot own a state

**Class: SPEC.**  `exec_impl.h`'s cadence note says the `E` row and the row
after it are charged by the SUCCESSOR's decode.  Concretely: the `E` row's
`charge(1)` lands the clock, the post-`E` row then acts on that clock with
`row_clocks = 0`, and the successor's first loader step rides the SAME clock.
A state machine that gives the post-`E` row a state of its own puts every
successor one clock late.  It is therefore carried as a one-bit debt
(`poste`) discharged at the TOP of the next edge, before the successor's
step — the model's own order.  Asserted: a post-`E` row carries no bus cycle
and no queue pop.

### F9 — `dbg_regs`' IP slot is the LIVE `pc`, not a retire snapshot

**Class: instrument.**  The TB latches `fin_regs` at the window-closing `F`
pop.  `opcode_prefetch` does NOT advance `m_.pc`, so at that clock the live
`pc` IS the retired-instruction IP; a snapshot register written at the E row's
edge is one edge too late and the TB reads the stale value (B8: `ip` off by
the instruction length in 500/500 cases).  The snapshot flop was deleted.

## §19 OPEN — what the next session picks up

1. **The store path (88/89).**  First divergence is a `qop` at the row where
   the successor's opcode is popped: the RTL retires early or the row stalls
   on the M10 slot after its own post.  The instrument is `+eutrace` on the
   ucore TB binary (one line per CE clock: state, upc, row word, the queue
   view, `eu_post`/`eu_pair`/`wr_out`) read against `V30SIM_ROWTRACE=1`.
2. **Split word accesses (8B).**  The BIU now manufactures the second cycle
   from one post; the read-side composition is in but unproven.
3. **Unimplemented by design so far**: the REP/string continuation
   (`intr_pending` is a flop with no writer), the interrupt entries, `eu_unhalt`,
   the POLL pin pipeline (`poll_pipe` samples the static level only), the 8080
   loader (no BRKEM path — ledger R4).
4. **Not yet run**: the boot march (`check_boot --core ucore`, F3's routed
   gate), `ulockstep` batch mode over golden cases, the Codex reviews.

# STAGE U2 — PASS 2

## §20 F7 CLOSED — the EU/BIU handshake is a MODULE CONTRACT

Pass 1 left the composition standing on Verilator's block order, which Quartus
does not share.  Pass 2 replaced it.  Nothing in this section is a new
mechanism: it is the SAME model, rendered so that the rendering is the same in
every tool.

### §20.1 What the measurement actually was

Reading the Verilated schedule (`obj_dir_ucore/…DepSet…cpp`) settled the
question pass 1 left open — and refined F7's own wording.  The EU's clocked
step was reading the BIU **in two different timings at once**, decided by
nothing but whether Verilator had chosen to materialise a signal or inline it:

| what the EU's clocked step read | the value it got |
|---|---|
| `q_ripe`, `q_byte` (materialised, assigned after both bodies) | the level **DURING the clock that is ending** |
| `slot_busy`, `rd_done_p`, `wr_done_p`, `opr_free_p`, `rd_val`, `halted`, `q_ripe_lead` (inlined onto the BIU's mid-edge registers) | the level **DURING the clock the edge OPENS** |

That mixture is not arbitrary, and that is the finding: **each half was right,
for its own reason.**

* the byte the step consumes is the one the BIU handed over on the clock that
  is ending — the clock the pop rode.  It must be the ENDING clock's queue;
* every other fact the step consults is a fact about the machine it is
  stepping INTO, because the step's product is the EU's state for the clock the
  edge opens.  It must be the OPENING clock's BIU.

And the EU's COMBINATIONAL act decode (`q_pop`, `eu_post`, `eu_pair`,
`q_flush`, `eu_susp`, `eu_halt`) already read the BIU as an ordinary registered
output — Verilator settles those assigns after the edge, which is exactly a
level read during the clock the act names.  That direction was never at risk.

So the composition wanted **two named views**, not one latch.  Pass 1's
refutation stands and is now explained: latching in the EU delayed the WHOLE
view, including the half that was already right, which is why B8 went 500->123.

### §20.2 The contract, as built

`v30u_biu` is now ONE next-state function and ONE register bank:

* `r_<x>` **is** the register — the state the model has at the start of
  `tick(c)`.  Written only by the single `always_ff`;
* `<x>` (unprefixed) is that register's NEXT value — the state at the start of
  `tick(c+1)` — computed by the single `always_comb`, whose body is pass 1's
  program **verbatim**, blocking assignments and all.  They are still the
  model's sequential semantics; they are now confined to one combinational
  process, so no consumer can observe an intermediate.

The module then publishes, in ONE place (`THE EU CONTRACT` block):

| view | signals | who reads it |
|---|---|---|
| REGISTERED | `q_byte` `q_ripe` `q_cnt_o` `eu_slot_busy` `eu_wr_done` `eu_opr_free` `halted_o` | the EU's combinational act decode; and the clocked step for the queue pair |
| NEXT (`_n`) | `eu_slot_busy_n` `eu_rd_done_n` `eu_wr_done_n` `eu_opr_free_n` `eu_rdata_n` `q_ripe_lead_n` | the EU's clocked step ONLY |

The EU derives the same split for the four stall terms that mix EU state with a
BIU level — `opr_free_now`/`_n`, `retire_ok`/`_n`, `f_wait`/`_n`,
`row_blocked`/`_n`, `row_pre_wait`/`_n` — one expression each, differing only in
which view it reads.

**No `_n` signal FROM THE NEXT-STATE CONE reaches a combinational output of
`v30u_eu`.**  (Corrected after the Codex review — see §26/C1.  The rule was
first written without the qualifier, and `eu_wr_done_n` is a standing
counter-example to the unqualified form: it does reach `q_pop`, legitimately,
because it is register-only lookahead, F11a.)  That is the loop rule, and it is
what keeps the EU->BIU direction a registered boundary:
`eu_post` is qualified by the REGISTERED `eu_slot_busy`, so `slot_busy`'s
next-state (which depends on `eu_post`) closes nothing.  Verilator reports no
`UNOPTFLAT` and no inferred latch on the whole build.

### §20.3 The result — behaviour preserved BIT FOR BIT

Everything below is the same tree, before and after, on the same command lines.

| gate | before F7 | after F7 |
|---|---|---|
| `check_core --core ucore --opcodes B8 --cases 500` | 500/500 | **500/500** |
| `… --opcodes 8A` | 500/500 | **500/500** |
| `… --opcodes 8B` | 302/500 | **302/500** |
| `… --opcodes 88` | 134/500 | **134/500** |
| `… --opcodes 89` | 121/500 | **121/500** |
| `ulockstep.py --suite --waits 0,1,2,3` | 32/32 LOCKSTEP | **32/32 LOCKSTEP** |
| `check_ucore_tables.py` (G0) | 9988/9988 | **9988/9988** |
| FSM spot, same five forms | 2500/2500 | **2500/2500** |

The three RED forms reproducing their exact pass-1 scores is the strongest
statement available: the change is a rendering change and touches no mechanism.

### §20.4 F10 — the CE-hold gate was watching the wrong signal

**Class: instrument.**  `tb_v30_core.sv`'s non-FSM `ce_probe` named
`dut.u_biu.ts / q_cnt / fetch_ptr`.  After the split those are the
next-state view, which tracks the pins and therefore moves on CE-low clocks BY
DESIGN; the gate reported `CE_HOLD_VIOL 2629` for a core that had not advanced
at all.  The probe now names `r_ts / r_q_cnt / r_fetch_ptr` — the state — and
reads **0** at `--ce-div 3`, as it did before the change.  *Falsifier*: any
ucore state element the probe cannot see moving on a CE-low clock.

The general rule this is the second instance of (F2 was the first): **a gate
that names an internal signal is only as current as that signal's meaning.**

## §21 RUNGS 2c/2d — THE STORE PATH.  `88` and `89` 500/500

### F11 — THE DEMAND AND THE TAKE ARE ONE EVENT

**Class: SPEC (composition).**  This is the whole store-path bug, and it is
one rule, not four fixes.

The EU asks for a queue byte in TWO places that must never disagree:

* `q_demand` / `q_pop` — a COMBINATIONAL wire.  It is what puts the pop on the
  bus: the BIU consumes it inside the clock it names, and the byte is gone;
* the CLOCKED STEP — `v30u_eu_row.svh`'s cadence block, `S_EPOP`,
  `S_TAIL_POP` — which is what CONSUMES the byte into `opc_byte`.

If the wire is true on a clock the step does not take the byte, the BIU pops a
byte nobody keeps.  If the step takes on a clock the wire was false, the EU
keeps a byte the BIU never handed over.  Pass 1 had **both**, and the census of
`88`'s first divergences (`qop` at the successor's pop, 366/500) was the sum:

| where | what pass 1 had | why it is wrong |
|---|---|---|
| `row_epop` | `retire_ok` off the PRE-EDGE `wr_out` | the step reads `wr_out` AFTER its own increment, so the E row's retire deadline counted every store EXCEPT the one this very row is posting.  Measured: `88 idx 3`, the F pop fired at the code fetch's T3 (row 5), nine clocks before the golden's row 11 |
| `row_epop` | no slot / pre-pair term | the step will not reach its cadence block at all on a clock it stalls on `stall_slot` or `deliver_read`; the wire fired anyway |
| `q_demand` | `(st == S_EPOP) \|\| (st == S_TAIL_POP)` UNCONDITIONAL | both states exist precisely to WAIT past the retire deadline.  They demanded a byte on every clock of that wait and took one only at the end -- the bytes in between were popped and dropped |

The fix is the rule: **every term the step applies is a term of the demand.**
`row_epop` now carries all four stalls and `retire_ok_e`, which reconstructs
combinationally exactly what the step will see -- `wr_out` PLUS this row's own
post (`acc_split ? 2 : 1`) -- and the two deferred-pop states carry
`retire_ok_n`.  Nothing was added to the model; a fitted term would have been
the wrong answer here by construction, because the two sides are the same event.

### F11a — a one-view corollary, and why it is loop-free

The retire deadline now exists in ONE view, `retire_ok_n`, read by the act
decode AND the step.  That looks like it breaks §20.2's loop rule -- an `_n`
signal reaching a combinational output.  It does not, and the reason is a
mechanism statement: **`done_ctr` IS the deadline**, so the pulse the next clock
will carry is a function of the REGISTERS alone —

```
wire done_fire   = (r_done_ctr == 2'd1);
wire rd_done_nxt = done_fire && !r_done_wr;
wire wr_done_nxt = done_fire &&  r_done_wr;
```

— published directly and used by the BIU's own next-state body, so there is one
expression and it never enters the next-state cone.  Verilator still reports no
`UNOPTFLAT`.  The registered `eu_wr_done` port is gone: one fact, one view.

### F11b — the trap that cost a build

`retire_ok_n` is a WIRE off the REGISTER `wr_out`.  Inside the clocked step,
`wr_out` is a LIVE blocking variable that the row has already incremented.
Substituting the wire for the expression inside `v30u_eu_row.svh` silently
moved the test back onto the pre-edge count: `88` went cycles-exact 500/500 but
`ip` came out ONE HIGH in 366/500 (the successor's decode started nine clocks
early while the pop stayed put).  Booked because it will recur: **in this EU a
wire named like a step variable is not that step variable.**

### §21.1 The rung table now

| rung | form | full | note |
|---|---|---|---|
| 1 | `B8` | **500/500** | GREEN (pass 1) |
| 2a | `8A` | **500/500** | GREEN (pass 1) |
| 2b | `8B` | 302/500 | split (unaligned) word loads — next |
| 2c | `88` | **500/500** | GREEN — the store path, F11 |
| 2d | `89` | **500/500** | GREEN — the store path, F11 |

Standing gates on the same tree: `check_ucore_tables` **9988/9988 (G0)**,
`ulockstep.py --suite --waits 0,1,2,3` **32/32 LOCKSTEP**, `--ce-div 3
--ce-hold-check` **0 violations**, FSM spot on the five forms **2500/2500**.

## §22 RUNG 2b — SPLIT LOADS.  `8B` 500/500

### F12 — A SPLIT IS ONE ACCESS, AND A READ HANDS OVER ONCE

**Class: SPEC.**  The BIU's T4 block armed `done_ctr` — the `eu_done`
one-shot — on **every** completing EU cycle.  For a split READ that is two
cycles, so OPR was handed over at the FIRST half's `e+2`, carrying half a word
and releasing `wait_opr` four clocks early.  Measured on `8B idx 7`
(`mov bp, word [si]`, `si` odd): the successor's F pop landed at row 12, the
second `MEMR`'s T3, where the golden has it at row 16.

`sim/biu_timed.cpp` says it in one line and the RTL now says the same:

```
} else if (rd_pending_ && cur_.rd_last) --rd_pending_;
if (cur_.rd_last && !is_write(cur_.bs)) rd_done_q_.push_back(e + 2);
```

A WRITE reports both halves — `wr_pending_` is a COUNT (the EU adds 2 for a
split, `acc_split ? 2 : 1`) and the retire deadline is a MAX, so both are
correct and neither is early.  A READ hands OPR over exactly once, on the cycle
that completes the word, which is the same cycle the byte-lane composition
two lines below already keys on (`rd_was_split`).  So the guard is
`if (cur_wr || cur_rd_last)` — one term, no split-specific path.

### §22.1 The rung table now

| rung | form | full | note |
|---|---|---|---|
| 1 | `B8` | **500/500** | GREEN (pass 1) |
| 2a | `8A` | **500/500** | GREEN (pass 1) |
| 2b | `8B` | **500/500** | GREEN — split loads, F12 |
| 2c | `88` | **500/500** | GREEN — the store path, F11 |
| 2d | `89` | **500/500** | GREEN — the store path, F11 |
| — | `8C` `8E` | **500/500** | incidentally green, not a claimed rung |

## §23 THE CENSUS — where the ladder actually stands

F11 + F12 are not local: they are in the sequencer's pop discipline and the
BIU's completion, which every form uses.  A reconnaissance sweep of the WHOLE
v0.1 suite at 60 cases (`check_core.py --core ucore --opcodes all --cases 60`,
20,820 cases over 347 forms) now reads:

* **7,767 / 20,820 cases full**
* **136 forms cycle-exact** at 60/60; **102 of those also arch-exact**

**This is reconnaissance, not a gate.**  The rung bar is unchanged: 500/500
full on the form's own v0.1 tranche.  What it buys the next session is the
shape of what is left, and the shape is FOUR FAMILIES, not a hundred forms:

| family | forms (examples) | first divergence | reading |
|---|---|---|---|
| **A — the non-ModR/M address source** | `50` `58` `9C` `9D` `C2` `C3` `A0` `A1` `A4` `AA` `D7` `8F.0` | `bus` at the first EU access (row 4-8) | every form whose address comes from something other than a ModR/M EA — the stack pointer, the direct address, the string pointers, XLAT. `50 idx 2` posts `0x982D0` where the golden has `0x9CF2E`, and its write data is 0 where the golden has `AX`. ONE mechanism (the row's `ind`/OPR source), not twelve |
| **B — arch only, cycles already exact** | `40` `48` (INC/DEC reg, 1BL) `8D` (LEA) `84` `85` (TEST) | none in the rows; regs differ | the sequencer and the bus are right; the ALU/write-back path is not. `8D idx 2` writes `0000` for an EA of `de60` |
| **C — the write DATA** | `86` `87` (XCHG r/m) | `data` at the store's T1 | the pairing latch's content, not its timing |
| **D — the redirect** | `EB` `E9` `E8` `74`..`7F` `FF.2` `FF.4` `F6.4` `F7.6` | `qop` | the taken-JMP / FLUSH family (M11's bubble). `74` is already 30/60 — the NOT-taken half passes |
| — | `D0.4` `0F20` | `fewer than 2 F pops in sim` | the case never closes its window: a hang, to triage FIRST (rig integrity) |

Family A is the next rung by the ladder's own order (push/pop/split stores) and
is the one with the most leverage; family D is the boot march's prerequisite.

### F13 — THE ITERATIVE STEPPER'S TERMINATOR, READ ONE CLOCK EARLY

**Class: RTL bug — and the FIFTH instance of §16's named class** ("getting a
`stop` wrong on a zero-cost arm is the single most common bug class found in
bring-up"; this is its loop-terminator cousin).  Found by following §23's own
rule that a case which never closes its window is triaged before anything is
scored.

`S_RLOOP` decremented `rloop_n` and THEN tested `rloop_n == 1`.  The model is
`while (m_.count != 0) { ++iters; --count; … }` — exactly COUNT iterations — so
the test belongs after the decrement against **0**.  Reading it against 1 runs
COUNT-1 iterations, and at COUNT==1 runs none: the counter wraps at 0 and the
state never leaves.

**All sixteen `D0.x` / `D1.x` forms are shift/rotate BY ONE**, so COUNT is
always 1 and all sixteen hung — 60/60 cases each reported `fewer than 2 F pops
in sim`, which is what a hang looks like from the comparator.  `D2.x`/`D3.x`
(by CL) hung only on the cases where CL happened to be 1.  One character:

```
if (rloop_n == 16'd0) begin      // this was the last iteration
```

After it, the sixteen forms run: `D0.0` 56/200 cycle-exact, `D0.4` 44/200,
`D1.4` 50/200, with the remaining divergence a `data` field — family C, the
pairing latch's CONTENT, not this mechanism.  No green rung moved.

*Falsifier*: any `R` row whose iteration count differs from `count` at entry.

## §26 THE CODEX REVIEW (2026-08-03, session `019fc8ba`)

Briefed on §§20-23, the three RTL files, and `sim/biu_timed.{h,cpp}` +
`sim/exec_impl.h`, with the SIMPLICITY principle verbatim and the governance
rule, and asked to attack the contract hardest-first.  Three findings landed;
all three are FOLDED, none was cosmetic.

**C1 — §20.2's loop rule was stated too broadly.**  UPHELD.  `eu_wr_done_n`
does reach a combinational output: `eu_wr_done_n -> retire_ok_n/retire_ok_e ->
row_epop/q_demand -> q_pop`.  The EXEMPTION is sound (its cone terminates in
`r_done_ctr`/`r_done_wr` and touches no next-state variable, so the path never
returns to its source), but the RULE as written did not carry the exemption.
Corrected in §20.2: the invariant is *no `_n` from the NEXT-STATE CONE*;
register-only lookahead is an explicit, named exception.  A rule with a silent
exception is a rule that will be violated by the next person, including me.

**C2 — F11 was still a reconstruction, and the reconstruction was incomplete.**
UPHELD, and it was a live bug.  `row_epop` tested the PRE-EDGE `pend_active`,
while the step tests it AFTER the row's own `emit_pending`
(`exec_impl.h:1095`, immediately before the cadence).  With `pend_active=1` and
`opr_fresh=1` entering an E row: the demand is false, the step clears the
latch, and the cadence then takes a byte the bus was never asked for — F11's
forbidden case, in F11's own fix.

The repair is not another reconstruction.  `pend_after` and `retire_ok_e` are
now WIRES, and `v30u_eu_row.svh`'s cadence reads THOSE WIRES instead of
recomputing the same predicates from its live blocking copies.  **The demand
and the take are now literally the same expressions**, which is what F11 said
and what pass 2 had not yet actually built.  Codex's simplicity note named this
exactly: "duplicates the E-row transition in two representations… this is
reconstruction, not one shared event predicate."

**C3 — the completed-read store bound was an unproved claim.**  UPHELD.  The
model's `rd_done_q_` is an unbounded deque; this EU has `rdq0`/`rdq1` and no
full check.  Per campaign risk #2 (bounded counters carry SYNTHESIS bound
assertions), the bound is now ASSERTED, where both values are the live ones:

```
if (rdq_n == 2'd2) $error("v30u_eu: completed-read store overflow (rdq_n=2)");
if (rd_done_cnt == 2'd3) $error("v30u_eu: rd_done_cnt saturated");
```

**It fires.**  `F3A4` / `F3A5` (REP MOVS) trip it immediately; `C8` (ENTER)
trips it within 60 cases.  Those three forms now report `SIM FAILED` where they
previously reported 0/60 — that is the instrument working, not a regression,
and it is a REGISTERED finding for the strings/REP rung: **either the microcode
never has three completed reads outstanding and the RTL is mis-counting, or the
store must be deeper.**  The assertion decides which, and it decides it loudly
instead of silently dropping a word.

Codex declined to propose a single mechanism behind more than one of §23's four
families, as briefed.  It also flagged, correctly, that "synthesis-correct
under Quartus 17.1" is not established by any evidence in-repo — U4 owns that,
and §20 should not be read as more than "conventional register/next-state
topology, race-free by construction".

### §26.1 Re-measured after folding C1-C3

No green rung moved, and no form regressed (form-by-form diff of the two
whole-suite censuses):

| | before C1-C3 | after |
|---|---|---|
| the seven green forms at 500 | 3500/3500 | **3500/3500** |
| whole-suite `--cases 60` | 7,767 full | **7,775 full** |
| forms cycle-exact | 136 | **141** |
| forms fully green | 102 | **102** |
| forms reporting a hang | 18 | **17** (`0F20` + the string/HLT/0F group) |
| forms regressed | — | **none** |

## §24 U2 PASS-2 GATE LEDGER

All on the same tree, `--core ucore`, v0.1 at w0 unless stated.

| gate | command | result |
|---|---|---|
| rung 1 | `check_core.py --core ucore --opcodes B8 --cases 500` | **500/500** |
| rung 2a | `… --opcodes 8A` | **500/500** |
| rung 2b | `… --opcodes 8B` | **500/500** |
| rung 2c | `… --opcodes 88` | **500/500** |
| rung 2d | `… --opcodes 89` | **500/500** |
| (not claimed) | `… --opcodes 8C` / `8E` | 500/500 each |
| G0 | `check_ucore_tables.py` | **9988/9988 PASS** |
| U1 lockstep | `ulockstep.py --suite --waits 0,1,2,3` | **32/32 LOCKSTEP** |
| CE hold | `check_core.py --core ucore --opcodes 88 --cases 100 --ce-div 3 --ce-hold-check` | **0 violations** |
| FSM spot (shared TB touched) | `check_core.py --opcodes B8,8A,8B,88,89 --cases 500` | **2500/2500** |
| G3 | ALL of v0.1 w0 row-identical | **NOT MET** — see §23 |

## §25 HANDOFF — what pass 3 picks up

0. **DONE in pass 2 — F13, the hang.**  See below.  `0F20` is the only
   `fewer than 2 F pops` case left; triage it first, before scoring anything.
2. **Family A, the non-ModR/M address source** — the ladder's own next rung
   (push/pop).  The evidence is already reduced: `50 idx 2` (`push ax`) is
   ROW-ALIGNED with the golden for all 12 clocks (`ts`/`bs` identical) and
   wrong in exactly two fields — it posts `0x982D0` where the golden posts
   `0x9CF2E`, and its write data is `0` where the golden has `AX`.  So the
   sequencer, the slot and the retire are right and the row's ADDRESS and OPR
   SOURCE are not.  Read `v30u_eu.sv`'s `row_seg` / `acc_off` / `s1_val`
   against `exec_impl.h::sr_segment` and the `50` micro-rows
   (`upc 0.50.0 = 1c6ffcea`, `0.50.1 = 14e25bea`).  Twelve forms, one
   mechanism — do NOT let it become twelve cases.  **Sharpened in pass 2:**
   for `50 idx 2` the SEGMENT is already right — the RTL posts `0x982D0`,
   which is `SS(0x982D) * 16 + 0`, against the golden's `0x9CF6E` =
   `SS*16 + (SP-2)`.  So `ind` is simply NEVER LOADED, and the write data is
   `0` for the same reason OPR is never loaded.  The failure is the E-row
   TRANSFERS of `upc 0.50.0` (`s1=28 d1=13 s2=1 d2=3`, a CTL row with
   `ictl=7 ectl=2 sr=2`), i.e. `rd_src1`/`rd_src2`/`wr_dst1` decode — not the
   address arithmetic and not the segment.
2. **Then C3's registered finding**: `F3A4`/`F3A5`/`C8` trip the
   completed-read-store assertion (§26/C3).  Decide it before the strings/REP
   rung: mis-count, or a deeper store.
4. **Then families B, C, D** in the ladder's order (B is INC/DEC/1BL, which is
   the ladder's next named rung after push/pop; D is the boot march's
   prerequisite).
5. **The microscope** used throughout pass 2 is worth rebuilding in three
   lines: compose a ONE-case batch with `check_core.compose_batch`, run the
   ucore TB with `+eutrace`, and print `c["cycles"]` (golden) next to
   `check_core.build_rows_sim(...)` (RTL).  Row index == CE clock index ==
   `+eutrace` line number, so a divergence at row N is read directly off
   trace line N+1.  That correspondence is what made F11 and F12 one-shot
   diagnoses.
6. **Still not run**: the boot march (`check_boot --core ucore`, F3's routed
   gate), `ulockstep` batch mode over golden cases, the wait axes (U3).
7. **Still unimplemented by design**: the REP/string continuation
   (`intr_pending` has no writer), the interrupt entries, `eu_unhalt`, the POLL
   pin pipeline beyond the static level, the 8080 loader (ledger R4).
8. **The HLT one-clock-lead contract** (`eu_halt`/`eu_unhalt` LEAD by one
   clock, §11.6) is still unverified — it is reached when the ladder gets to
   the 1BL forms, which is family B.

# STAGE U2 — PASS 3

**STATUS: the four families of §23 are CLOSED as families.  Gate U2 (G3) is
still NOT met — 149,214 / 169,000 — but the shape has changed: what is left is
a named, enumerated tail, not a family.**

## §27 TRIAGE — the two items pass 2 routed, both answered from the SIM

### §27.1 C3's fired assertion: THE BOUND WAS RIGHT AND THE RTL WAS MIS-COUNTING

§26/C3 asserted a bound it had not proved, and it fired.  The model holds the
truth, so it was asked.  `V30SIM_QDEPTH=1` (new, `sim/exec_impl.h` +
`sim/biu_timed.cpp`, one stderr line per NEW maximum carrying the ROM row that
pushed it) driven by the new `sw/qdepth_probe.py` over the WHOLE v0.1 suite at
w0 — 347 forms, 169,000 cases:

| store | max depth | reached by |
|---|---|---|
| `rdq_` (EU-side completed reads) | **2** | 34 forms (`A6` `A7` `CA`..`CF` `61` `62` `F6.6`/`.7` `F7.6`/`.7` `HLT.INT` …); 264 forms never exceed 0 |
| `rd_done_q_` (BIU-side completion clocks) | **1** | 245 forms; **never 2** |

and on the three forms that tripped the assertion — `F3A4`, `F3A5`, `C8` — the
model's `rdq_` never exceeds **1**.

**VERDICT: the architecture's risk-#2 bound of TWO SLOTS IS CORRECT.**  The
assertion stays exactly as written; the RTL was accumulating completed reads it
never took out.  Two machines were behind it, and both are §16's named class:

* **F19 — both counting conditions read the terminator one clock early.**
  `count` is a LIVE BLOCKING variable in `v30u_eu_cond.svh`, so after
  `count = count - 1` it IS the post-decrement value — what the model tests
  against 0.  Testing it against 1 made `REP MOVS` with CX==1 take the loop
  back where the model falls through, running a SECOND element and issuing a
  read nobody consumed.  `CNTZ` (ENTER's level walk) had the same off-by-one
  the other way.  F13's bug, third and fourth instance.
* **F20 — the pre-pair flush is a `deliver_read()`, not just a wait.**  The
  model's `bus_read`/`bus_write` open with
  `if (pend_.active) { if (!opr_fresh_) deliver_read(); emit_pending(); }`;
  the EU had only the wait, and only its `wait_opr_free` half.  Nothing popped
  the store, nothing paired, `pend_active` never cleared.  That is where a REP
  string's every-iteration store is paired — by the NEXT iteration's read row —
  and it is what filled `rdq` at CX==3.

*Falsifier for the bound*: any stimulus in which the MODEL's `rdq_` reaches 3.

### §27.2 The `0F20` hang: the same F19

`ADD4S`'s digit loop is a `CNTZ` loop.  It fell with F19 and needed nothing of
its own.  Forms reporting `fewer than 2 F pops` went **17 → 5**, and three of
the five are `HLT.*`, where `eu_unhalt` is unimplemented by design.

## §28 THE FAMILIES — one statement, seven renderings

Everything below is the SAME sentence in different clothes, and stating it once
is the whole of pass 3:

> **A row's ACTS are computed from the row's own transfers, on the row's own
> clock; and the machine a row runs on is the machine it belongs to.**

The EU already contained that rule — `opr_now`, "the value this row is about to
put there".  It had been applied to ONE destination, on ONE state.

### F14 — the row's own transfers (family A)

`exec_impl.h::run_micro` does the two parallel transfers FIRST and issues the
bus cycle afterwards off `m_.ind`, so a row that writes IND posts the address IT
JUST WROTE.  That is how every non-ModR/M address in the ROM is formed
(`50`: `SIGMA -> SP  SIGMA -> IND  E  CTL MEMW SS`); the ModR/M forms take IND
from the loader, which is why they were green and this was invisible for two
passes.  `ind_now` is `opr_now`'s mirror, dest2 winning over dest1 because the
model writes dest2 second.  The same rule reaches the REDIRECT: `flush(cs, pc)`
runs after the transfers, so `pc_now`/`cs_now`; without them every taken jump
refilled from `target - disp`.

### F15 — the post-`E` row is a row with a CLOCK (family A)

F8 gave it no STATE; it still has ACTS.  `exec_impl.h:1095`'s pairing fires on
it like any other row — `50`'s store is paired by exactly that.  `eu_pair` now
carries a `poste` term.  And the pairing is a MID-CLOCK fact (`biu_timed` fills
`cur_.data` inside `mem_write`; the row that same `tick()` emits already carries
the word), so the AD data lanes read it through a register-only lookahead.

### F16 — `stall_slot` was F11's own bug, one dimension over (family A)

`BiuTimed::post` waits on the slot and THEN takes it, both inside the row, so
the demand (`eu_post`, registered slot) and the take (the step,
`eu_slot_busy_n`) read DIFFERENT views and the row ran one clock long.
Invisible on an aligned store, fatal on a SPLIT one, where the extra clocks
pushed the pairing past the FIRST half's T1.  One view now, the demand's.

### F17 — M5b: ONE rotation per ACCESS, not per CYCLE (family A)

Both halves of a split store drive the same rotated word; the fill computed A0
per cycle.  `pair_odd` is captured on the first half a pairing fills.

### F18 — `wait_next_read` is a DEADLINE, like `wait_bus` (family A)

The write side already read its completion as register-only lookahead
(`eu_wr_done_n`, F11a); the read side did not, so every `F` row waiting on a
read ran one clock late.  `nr_have` now carries `|| eu_rd_done_n`.  **This one
term moved the whole POP/RET/direct-address family to cycle-exact.**

### F21 / F22 / F23 — the post-`E` row runs on the machine it belongs to (family B)

Family B was never "the ALU/write-back path"; it was ONE ordering fact seen
three ways.  The model runs the post-`E` row inside `run_micro` and only THEN
returns and lets the successor's `loader_decode` touch anything.  In the EU the
two land on DIFFERENT EDGES — the successor's decode is chained zero-cost into
the `E` row's own edge (it must be: `st` has to be S_MODRM/S_NORM_CHG during
the decoder's clock or the ModR/M byte is demanded one clock late), while the
post-`E` row is F8's one-bit debt discharged at the top of the NEXT edge.

* **F21** — `opr` is a LIVE BLOCKING variable: the `F` interlock's delivery
  writes it just above the row body, and `s1_val` is a WIRE off the REGISTER.
  `58`'s `OPR -> M` wrote AX = 0000 in 500/500 cases.  F11b's trap, third
  instance.
* **F22** — the four latches the post-`E` row reads and `loader_decode`'s
  prologue RESETS (`pfxcnt`, the operand kinds, the `ALU OPC` base, the ALU
  latch) are simply deferred past the discharge — `v30u_eu_iend_late.svh`.
* **F23** — ...and the opcode latch was OVERWRITTEN, not reset, so deferral
  cannot reach it: by the post-`E` row's clock the EU held the SUCCESSOR's
  opcode and every `ALU OPC` row resolved against it.  The whole
  accumulator-immediate block executed the operation the injected `90` selects
  — index 2, ADC — and `14` (ADC AL,imm8) was the ONE form of its group that
  passed.  The decoder's opcode latch loads at the END of its clock and the
  post-`E` row reads it before that, so the row's own opcode context travels
  with the debt: **9 bits**.

### F24 — a row that FLUSHES cannot POP (family D)

`exec_impl.h`'s CTL block calls `biu_.flush()` BEFORE the cadence reaches
`opcode_prefetch`, so on a redirect row the queue has already been emptied and
the pop waits for the refill.  The EU took the byte the flush was about to
discard and then decoded a byte that did not exist.  `!row_flush` is a term of
BOTH the demand and the take; adding it to one only, as the first attempt did,
left the machine visibly split (F11, again).

### F25 — power-on reset is a MICROCODE MARCH, not a state (the boot gate)

`CpuT::reset()` runs the ROM's own sequence at page 7 opcode 00000011 — 01D0
`ZEROS -> DS`, 01D1 SUSP, 01D2 `ONES -> CS`, 01D3 `ZEROS -> PC` FLUSH, 01D4 `E`
MFS, 01D5 `ZEROS -> SS` — and only THEN does the decoder see its first byte.
The EU came out of reset in S_OPC_POP and the whole boot was seven clocks
early.  Two facts, both already stated by `run_timed_boot` and both pinned by
the capture, not fitted: the part comes out of reset with the PREFETCHER
SUSPENDED, and the internal dispatch is FOUR CLOCKS (01D0 at release+4, the
FLUSH at release+7 where the capture shows its `E` blip, the first CODE T1 at
release+9).  A backdoor-loaded case starts mid-stream and must not run it —
that is what `bkd_load` selects, and it is why no v0.1 rung moved (form-by-form
diff of the two whole-suite censuses: 14,112 → 14,112, zero forms either way).

### F26 — an `R` row keeps the sequencer while it iterates (family C)

The loop is `while (m_.count != 0) { … wr_dst1(op.d1, …) }` INSIDE the row's own
iteration, so every step writes THE R ROW'S Dest1.  Advancing `upc` before
entering S_RLOOP handed the loop its SUCCESSOR's row word: `D1.4`'s
`0116 SIGMA -> tmpb  W R ALU OPC` wrote through `0117`'s `SIGMA -> M`, so
`shl bx,1` returned BX unchanged.  §16's named class, sixth instance.

### F27 — a pre-decode read does not arm the pairing latch (family C)

`loader_impl.h:495` assigns `m.opr = biu.mem_read(…)` DIRECTLY and never
touches `opr_fresh_`, which `begin_sequence()` left false: the latch is armed by
a `-> OPR` TRANSFER, not by a read.  S_PRERD set it, so `86`/`87`'s write-back
row emitted its store the instant it posted — handing the bus the operand the
pre-read had just brought IN instead of the register the post-`E` row is about
to swap OUT.

### F28 — a row suppresses its own write-back

`suppress_commit` is set INSIDE the row body, on the very row whose `[-06-]` it
cancels (CMP), so the act decode must reconstruct it.  `38`/`39`/`80.7` posted
a store that never happened and the successor's F landed one clock late.

### §28.1 THE FIRST TIME §20.2's LOOP RULE ACTUALLY BIT

`eu_rdata_n` was `rd_val`, the SHARED OPR shadow that a pairing also writes, so
reading it back from the EU's act cone (F14's `pc_now` off an `F` row's
delivered word — `C3`'s `00F3 OPR -> PC  F E  CTL FLUSH`) closed
`eu_wdata -> rd_val -> eu_rdata_n -> opr_live -> opr_now -> eu_wdata`.
Verilator named it (UNOPTFLAT on `s1_now`) and two intermediate attempts to
break it structurally failed for the same reason: **anything computed inside
the single next-state process is in the next-state cone, because Verilator (and
synthesis) treats that process as one node.**  That is the price of §20.2's
"ONE next-state function", and it is worth writing down.

The fix is what the model says: `rdq_` holds READ words, `last_wval_` holds the
last write.  One fact, one register — `rd_land` / `r_rd_land`, and
`eu_rdata_n` is that flop.  No UNOPTFLAT and no inferred latch on the build.

## §29 THE RUNG TABLE AND THE GATE LEDGER

All on the same tree, `--core ucore`, v0.1 at w0.

| gate | command | result |
|---|---|---|
| rungs 1–2d | `check_core.py --core ucore --opcodes B8,8A,8B,88,89 --cases 500` | **2500/2500** |
| (not claimed) | `… --opcodes 8C,8E` | 1000/1000 |
| rung 3 — family A | `… --opcodes 50,A4 --cases 500` | **1000/1000** |
| rung 6 — family D | `… --opcodes EB,74 --cases 500` | **1000/1000** |
| rung 8 — family C | `… --opcodes D1.4,86 --cases 500` | **1000/1000** |
| rung 9 | `… --opcodes C3 --cases 500` | **500/500** |
| rung 10 | `… --opcodes A5,0F12 --cases 500` | **1000/1000** |
| **boot march (F3's routed gate)** | `check_boot.py --core ucore 220` | **220/220 MATCHES** |
| G0 | `check_ucore_tables.py` | **9988/9988 PASS** |
| U1 lockstep | `ulockstep.py --suite --waits 0,1,2,3` | **32/32 LOCKSTEP** |
| CE hold | `check_core.py --core ucore --opcodes 88 --cases 100 --ce-div 3 --ce-hold-check` | **0 violations** |
| FSM spot (shared TB touched) | `check_core.py --opcodes B8,8A,8B,88,89 --cases 500` | **2500/2500** |
| the MODEL, unmoved | `timed_gate.py --suite tests/v30/v0.1 --forms all` | **169,000/169,000, row-diffs 0** |
| **G3** | `check_core.py --core ucore --opcodes all --cases 0` | **159,348 / 169,000 — NOT MET** |

### §29.1 The census, pass by pass

Reconnaissance (`--cases 60`, 20,820 cases over 347 forms), not a gate:

| after | cases full | forms cycle-exact | forms fully green | forms hanging |
|---|---|---|---|---|
| pass 2 (start) | 7,775 | 141 | 102 | 17 |
| family A (F14–F18) | 8,856 | 186 | 118 | 16 |
| triage (F19, F20) | 8,986 | 188 | 118 | **5** |
| family B (F21–F23) | 13,114 | 204 | 191 | 5 |
| family D (F24) | 14,112 | 231 | 218 | 5 |
| family C (F26, F27) | 17,591 | 285 | 277 | 5 |
| F28 + the redirect's OPR | 18,000 | 293 | 285 | 5 |
| rung 10 (M5b `odd_base`, F29) | 18,832 | 310 | 306 | 5 |
| rung 11 (F30, the BCD adjust) | **19,221** | **313** | **313** | 5 |
| review fold D1 (`op8` in the shadow) | 19,221 | 313 | 313 | 5 |

**No form regressed at any step** — every rung was scored by a form-by-form
diff of the two whole-suite censuses, not by the total.

### §29.2 G3, stated honestly, BOTH numbers

The work order asked for two numbers because the sim carries registered
residue against SILICON.  At **w0 it does not**: `timed_gate.py` over the whole
v0.1 suite reports **169,000/169,000 arch, 169,000/169,000 window, 169,000
rows-exact, row-diffs 0**.  So at w0 there is nothing to subtract, and the two
numbers coincide:

* G3 through the golden comparator: **159,348 / 169,000** (94.3 %).
* G3 minus the sim's registered w0 residue: **159,348 / 169,000** — the same
  number, because that residue is empty at w0.

**34 RED forms**, of which **12 (2,400 cases) are unimplemented by design**
(`INT.*`, `NMI.*`, `HLT.*`).  Excluding those, the RTL is
**159,348 / 166,600 = 95.6 %** of what it is currently built to do.

(The 907+3 residue rows named in the pass-3 brief are a WAIT-AXIS quantity —
they belong to U3, not to this gate.  Re-derive them there; do not carry the
figure forward from memory.)

## §30 WHAT IS LEFT — 41 RED FORMS, ENUMERATED

Not a family: a tail.  Grouped by first divergence, with the case count each
costs out of 169,000.  (`0F 10-1F`, the word string moves and `8F.0` were in
this table when it was first written and were closed by rung 10 — see §28's
F29 and M5b's `odd_base`.  What follows is the list AFTER that.)

(The BCD group left this table with rung 11 — F30, §31.0's first item, landed.
`27` `2F` `37` `3F` `0F20` `0F22` `0F26` are all 500/500.)

| group | forms | cost | reading |
|---|---|---|---|
| **interrupt / HLT entries** | `INT.*` (7), `NMI.*` (2), `HLT.*` (3) | 2,400 | **UNIMPLEMENTED BY DESIGN** (§19.3): no interrupt entry, `eu_unhalt` tied 0, the POLL pipeline is the static level only, `intr_pending` has no writer.  A work list, not a bug list |
| **multi-cycle pushes** | `60` (PUSHA) `62` (BOUND) `CC` `CD` `CE` | 2,182 | `busstat`: the RTL runs consecutive stores BACK TO BACK where the golden has idle `Ti` between them.  Task #33's multi-push bus-hold datapoint, now reproducible in RTL |
| **CALL and the flush display** | `E8` `FF.2` `FF.3` `9A` | 1,686 | `qop`: the flush's `E` blip is ONE CLOCK EARLY in about half the cases.  The row order is right; this is the BIU's `e_pend` / "a ready-but-not-yet-started EU request owns the next slot" term (F1(c)), not the EU |
| **DIV** | `F6.6` `F6.7` `F7.6` `F7.7` | 1,571 | the iterative divider: `busstat` |
| **strings / ENTER** | `C8` `F3A4` `F3A5` `F3AA` `F3AB` `F2AA` | 1,601 | the REP continuation and ENTER's nesting walk |
| **the rest** | `FA` `FB` `POLL.LO` | 212 | `FA`/`FB` are 88-90 % green (the 1BL execute strobe's late-queue edge) |

## §31 HANDOFF — what pass 4 picks up

0. **ONE ITEM IS ALREADY DIAGNOSED — do not re-derive it.**  (The other,
   the BCD adjust unit, was diagnosed and then LANDED as F30/rung 11; it is
   kept below because the reading is the template for the next one.)

   * **The BCD adjust unit was COMPUTED AND DISCARDED — FIXED, rung 11.**  `v30u_eu.sv` builds
     `adj_lo` / `adj_hi` / `adj_corr` / `adj_sum` / `adj_val8` / `adj_rhi` /
     `adj_flags` — a faithful transliteration of `sim/alu.cpp::bcd_adjust` —
     and then the `case (eff_op)` for `A_ADD` / `A_SUB` never consults
     `al_adjust`, so all three outputs sit in the module's `_unused_eu` sink.
     `27 idx 3` is the whole proof: `exp e369 got e368`, i.e. exactly
     `tmpb + ONES` with the decimal correction missing.  The model's armed pass
     (`alu.cpp:127`) is one override — the corrected byte on the LOW lane,
     `av_hi ± B_hi ± carry-out-of-the-low-lane` on the high one, `ARITH_MASK`
     flags.  Four forms, 2,000 cases, and `0F20`/`0F22` sit behind it.
   * **The multi-cycle pushes are an OPR-HOLD question, not a bus-hold one.**
     `60`'s ROM alternates `SIGMA -> tmpb  SIGMA -> IND  CTL MEMW SS` with
     `<reg> -> OPR  F  CTL`, and the `F` on the OPR-LOADING row is
     `wait_opr_free` (it does not READ OPR, so `deliver_read(false)`).  The
     model's own row schedule shows the gap: 023A at clock 11, 023B at 12,
     023C at **22**.  So the idle `Ti` clocks the golden shows between
     consecutive stores are the EU waiting for the store to LET GO OF OPR, and
     the RTL granting the next cycle back-to-back means `opr_owned` /
     `opr_free_now` releases too early.  That sharpens task #33's
     "multi-push bus-hold" datapoint: it is `wait_opr_free`, and `CC`/`CD`/`CE`
     (the INT frame pushes) and `62` are the same chain.

1. **The order is by cost and by confidence**: the multi-cycle pushes first
   (5 forms, 2,182 cases, and §31.0 already names the mechanism — `opr_owned`
   releases too early against `wait_opr_free`), then CALL's flush display
   (4, 1,686), then DIV (4, 1,571), then the strings/ENTER group.
2. **The interrupt entries are the biggest single block (2,400 cases) and are
   NOT bugs.**  They are `eu_unhalt`, the interrupt entry vectors, the POLL
   pin pipeline and `intr_pending`'s missing writer.  Build them as a rung,
   not as fixes.
3. **The instruments**, all new in pass 3 and all cheap:
   * `sw/uscope.py FORM IDX [--rowtrace] [--full]` — the microscope of §25.5,
     built.  Golden row, RTL row and the EU's own per-CE-clock state line on
     ONE index, plus the MODEL's micro-row schedule.  Every diagnosis in this
     section is one invocation of it.
   * `sw/uarch.py FORMS` — the FINAL-REGISTER field histogram, which is what a
     cycle-exact / arch-red form needs and what `check_core` does not print.
   * `sw/ucore_census.py LOG [BASELINE]` — the census + the form-by-form
     REGRESSED/IMPROVED diff.  Run it on every rung; the total is not evidence.
   * `sw/qdepth_probe.py` + `V30SIM_QDEPTH=1` — the model's own bound prover.
   * `+eutrace` now carries `ind opr opr_fresh pend poste rdq rd_done tmpa tmpb
     tmpc sigma` and `eu_wdata`, which is what made F14/F21/F23 one-shot reads.
4. **REGISTERED RESIDUE, booked and not patched**: F22's deferred reset can
   only collide with a write the SAME edge's decode chain makes to one of the
   four deferred latches, and an audit of that chain finds EXACTLY ONE:
   S_DECODE's `pfxcnt = pfxcnt + 1`, taken by a successor that is a PREFIX or
   the `0F` escape (both use that arm).  S_TAKE_OPC, S_DECODE2, S_PFX_CHG and
   S_EXT_CHG1 write nothing in the deferred set.  So the residue is exactly one
   field on exactly one class of successor.  No v0.1 case reaches it (the
   injected successor is always `90`); it is a real hazard for whole-program
   replay and must be settled before U3's image work.
5. **The structural lesson of §28.1 is a constraint on every future fix**:
   nothing the EU's act decode reads may be computed inside the BIU's single
   next-state process.  If a fact is needed there, give it a flop.
6. **Still not run**: `ulockstep` batch mode over golden cases, the wait axes
   (U3), the second Codex review (this pass ended at a rung boundary before it).

## §32 THE SECOND CODEX REVIEW (2026-08-03, thread `019fc8ba` resumed)

Briefed on §§20-31, the six RTL files and the SPEC (`sim/exec_impl.h`,
`sim/loader_impl.h`, `sim/biu_timed.{h,cpp}`), with the SIMPLICITY principle
verbatim and the governance rule, and asked to attack the pass-3 findings
hardest-first and to say plainly where I was wrong.  It reviewed the tree at
`93f9074254` — before F30 landed.

**D1 — F23's "nine bits" was WRONG.  UPHELD, and folded.**  `op8` is
OVERWRITTEN by the successor's `S_DECODE2` on edge `c` exactly as `opc_reg`
is, and the post-`E` row reads it in three places: `al_byte = op8` when it
latches an ALU op, `SIGNTGL`'s `tmpb[7]` vs `tmpb[15]`, and `dir*sz` as a
Source1.  The shadow is TEN bits, not nine.  Folded (`pe_op8` / `op8_eff`).
No v0.1 case at w0 reaches the divergent path — the census is 19,221 → 19,221,
zero forms either way — so this is a LATENT correctness fix of the same shape
as §31.4's registered `pfxcnt` residue, and Codex was right that the CLAIM was
wrong even though the score did not move.  *A finding whose fix moves no number
is still a finding.*

**F30 — the BCD adjust unit, independently confirmed.**  Codex reached the
same reading from the source alone ("RTL computes `adj_*` but ordinary
`A_ADD/A_SUB` ignores `al_adjust`") and confirmed the SPEC has ONE mechanism
for all four native forms.  Landed before the review returned; §31.0 has the
evidence.

**The multi-push grouping — CONFIRMED as one mechanism.**  "Non-OPR-reading
`F` rows call `wait_opr_free()` in the SPEC", matching §31.0's 023A/023B/023C
schedule.

**Not defects, checked and cleared:** §28.1's `rd_land` split ("matches the
SPEC separation between EU `rdq_` and the BIU OPR shadow `last_wval_`"), and
the audit that the only `_n` signals still reaching the act cone —
`eu_rd_done_n`, `eu_wr_done_n`, `eu_rdata_n` — all terminate in BIU registers
(`r_done_ctr` / `r_done_wr` / `r_rd_land`), while `eu_slot_busy_n`,
`eu_opr_free_n` and `q_ripe_lead_n` stay clocked-step-only.  F16 (the
registered slot view: "using `eu_slot_busy_n` made the take observe the busy
bit caused by its own post"), F18/F14's lookahead, and F26 (the `R` row keeping
`upc`) were each upheld against the SPEC line by line.

**Declined, correctly:** the claim that CALL's one-clock `E` blip is
specifically `e_pend` rather than another announcement-state term — "source
alone does not verify it", the per-case traces are needed.  It is carried in
§30 as a reading, not as a diagnosis.  And it found no single mechanism joining
BCD, multi-push and CALL into a larger family, as briefed.

# STAGE U2 — PASS 4

**STATUS: the costed tail of §30 is FOUR-FIFTHS CLOSED and its remaining
members are named, not grouped.  Gate U2 (G3) is still NOT met —
164,787 / 169,000 — but 2,400 of the 4,213 red cases are the interrupt and
HALT entries, which are still UNIMPLEMENTED BY DESIGN and are a RUNG, not a
bug list.  Of what the RTL is currently built to do the score is
164,787 / 166,600 = 98.9 %.**

Pass 3 said its own remainder was "a tail, not a family".  That was half
right.  Three of §30's five groups fell to ONE finding (F31), which is the
pass's whole lesson: a tail enumerated by FIRST DIVERGENCE is not the same
thing as a tail enumerated by MECHANISM, and §30 was the former.

## §33 THE FOUR FINDINGS

### F22 SETTLED — deferral and travel are ONE rule, and the field decides which

§31.4 booked a REGISTERED RESIDUE: `loader_decode`'s per-instruction latch
reset is DEFERRED past the post-`E` row's discharge
(`v30u_eu_iend_late.svh`), and an audit found EXACTLY ONE field the
successor's edge-`c` decode chain also writes — `pfxcnt`, incremented by
S_DECODE's prefix arm.

The settlement is not a patch to the deferral; it is the observation that
F22 and F23/D1 were never two mechanisms.  Both are §28's one sentence —
*the post-`E` row runs on the machine it belongs to* — and **which
RENDERING a field takes is decided by exactly one question: does the
successor's decode chain WRITE this field on edge `c`?**

| answer | rendering | why |
|---|---|---|
| no | DEFER the successor's reset past the discharge | the register still holds the predecessor's value at the discharge, so no copy is needed |
| yes | the value must TRAVEL with F8's debt | the register has already moved on; a deferred reset lands ON TOP of the successor's own write |

`pfxcnt` is the ONE field in both sets, so deferring it was wrong in both
directions at once: the post-`E` row read `pfxcnt + 1` (the successor
prefix's increment stacked on the predecessor's count), and the deferred
reset then landed on edge `c+1` and DESTROYED that increment.

The second is the one that matters.  `PFXCNT` is read on exactly ONE ROM row
in the whole part — `0225 PFXCNT -> tmpa`, the REPX withdrawal's
`PC := PC - PFXCNT - 1` — and a `REP` string is BY CONSTRUCTION reached
through a prefix.  Under whole-program replay every mid-string interrupt
would have resumed at the opcode instead of at the first prefix: **the 8086
lost-prefix bug the V30's ROM exists to avoid**, reintroduced by an RTL
rendering artefact.

`pfxcnt` therefore joined the debt (`pe_pfxcnt` / `pfxcnt_eff`, captured at
all three `poste` raises) and its reset went back into S_INSTR_END's
IMMEDIATE block, where `loader_decode`'s prologue puts it.  **The debt is
EIGHTEEN bits.**

MEASURED, directed — no v0.1 case reaches the residue (the injected
successor is always `90`), so the falsifier had to be built.  `pfxcnt` is
now on `+eutrace` as `pfx=`; the stimulus is a `poste`-raising instruction
followed by a prefixed one (`B8 34 12` / `F3 A4`, CX=2):

| | `pfx` through the REP string, incl. the REPX exit rows 7.40.x |
|---|---|
| deferred reset (the residue) | **0** |
| the debt (F22 settled) | **1** |

*Falsifier*: any other ROM row that reads PFXCNT, or any edge-`c`
decode-chain write to one of `iend_late`'s remaining fields.

**...and the debt was EU state the SS map did not carry.**  `SSA_E_POSTE`
was already mapped, so a freeze at `poste = 1` was representable and NOT
restorable.  Appended `SSA_E_PE_OPC_REG` / `_PE_PFXCNT` / `_PE_FLAGS`
(`{iend_owed, pe_op8, pe_opc8080}`), each symbol exactly twice.

### F31 — OPR OWNERSHIP IS ONE COUNTER, AND IT IS THE BIU'S

**Class: SPEC (composition).  F11's named error, third instance, and the
single largest finding of the pass: +4,436 cases and three of §30's five
groups.**

The EU kept its own `opr_owned` count of the stores it had paired and
tested it against the BIU's release PULSE.  The BIU kept `opr_held`, which
IS `BiuTimed::opr_held_`.  One event, two reconstructions — and the EU's
copy was wrong in BOTH of its parts.

* **THE VIEW.**  `opr_free_now_n` read `eu_opr_free_n`, the release computed
  DURING the T2 clock, so the `F` row completed at the end of T2.  The
  model's instant is `opr_free_clk_ = T2 + 1` and the row runs ON that
  clock.  Every non-OPR-reading `F` row therefore ran ONE CLOCK EARLY.
  That is the whole multi-cycle-push group: `60`'s ROM alternates
  `SIGMA -> tmpb  SIGMA -> IND  CTL MEMW SS` with `<reg> -> OPR  F  CTL`,
  and **the idle `Ti` the golden shows between consecutive stores IS that
  clock**.  `60` was green on push #1 only, and only by accident — the
  FARJMP bubble after 023B put the clock back, which is exactly why the
  reading in §30 said "back to back" and not "one clock early".
* **THE COUNT.**  The model's `++opr_held_` is CONDITIONAL —
  `if (!(r == &cur_ && run_ && ci_ > 1))`, a fact about the BIU's own
  running cycle — so **an EU-side count can never be faithful**, whatever
  it is fitted to.  `opr_owned += (pend_split ? 2 : 1)` also over-counted a
  split against the pulse test.  MEASURED after fixing the view alone:
  ALL 96 odd-SP `60` cases failed and ALL 104 even-SP cases passed, 200/200
  on the split/aligned line.

The fix is the F11 rule and nothing else: the BIU publishes the model's own
predicate off the REGISTER —

```
assign eu_opr_free = (r_opr_held == 2'd0);      // `while (opr_held_ > 0) tick()`
```

— and the EU's counter, the `_n` port, and with them `opr_free_now_n`,
`f_wait_n`, `row_pre_wait_n` and `row_blocked_n` are DELETED.  One
expression, both views; the demand and the take cannot drift.

`opr_free_p` / `set_oprfree` stay as the model's `opr_free_clk_` and are
documented as PROVABLY VACUOUS: `opr_free_clk_` is only ever set to `c + 1`
inside `tick()` for clock `c`, which leaves `clk_ == c + 1`, so the second
`wait_opr_free` loop's guard is false on entry in every reachable state.

SS: `SSA_E_OPR_OWNED` retired, `SSA_E_PE_FLAGS` moved into the hole,
`SS_EU_COUNT` 114 → 113, EU region contiguous 0x100–0x170.

**What it moved** (form-by-form, whole-suite censuses):
`60` 0→500, `62` 81→500, `CC` 0→500, `CD` 0→500, `CE` 237→500 (the
multi-cycle pushes), `9A` 0→500, `FF.3` 0→500 (half of CALL),
`F6.7` 123→500, `F7.7` 126→500, `F6.6` 105→353, `F7.6` 75→330 (DIV).
Zero regressions.

### F32 — THE RESTORING DIVIDER'S COMPARE IS ONE BIT WIDER THAN ITS OPERANDS

**Class: RTL bug.**  F31 left all four DIV forms CYCLE-EXACT 500/500 and
ARCH red, which is the cleanest possible statement that what remained was a
value.

`alu.cpp::kDiv` computes `hi = (a << 1) | (lo >> (w-1))` in a `uint32_t`
and does **not** mask it before `if (hi >= divisor)`.  The bit shifted OUT
of the high half is exactly what decides the subtract — that extra bit IS
the restoring step.  The RTL built `div_hi0` as `{it_a[6:0], lo[7]}` (byte)
and `{it_a[14:0], lo[15]}` (word), dropping it, so every dividend whose
high half reached the top bit took the wrong branch.  `div_hi0` was already
declared `[16:0]`; only the two concatenations were short.

MEASURED: `F6.6 idx 2` (0x9151 / 179) `exp ax=94cf got 5100`.
`F6.6` 353→500, `F7.6` 330→500.

### F33 — THE QS=E GUARD READ THE REQUEST QUEUE A CLOCK BEHIND

**Class: SPEC (view).**  §30 carried CALL's one-clock `E` blip as a READING
("the BIU's `e_pend` / F1(c) term, not the EU") and §32 records that Codex
declined to confirm it from source alone — "the per-case traces are
needed".  The traces confirm the term and name the defect, and it is not a
new rule.

F1(c): the flush display waits for a ready-but-not-yet-started EU request's
STATUS clock.  The model tests `req_` **live** inside `record()`, and by
then the row's own `post()` has already run — the row body precedes the
row's `charge(1)`.  The RTL tested the REGISTER `r_rq_n`, one clock behind,
so a flush row that ALSO posts saw an empty request queue and took the QS
port on its own clock.

MEASURED, `E8 idx 1` — the flush row 0.e8.4 stands on clock 6, the push row
0.e8.5 posts on clock 7, the MEMW announcement is clock 8:

| clock | model | RTL (before) |
|---|---|---|
| 6 | blocked by the push-absorb hold [5,6] | same |
| 7 | `req_` NOT empty → deferred | `r_rq_n == 0` → **E fired** |
| 8 | the announcement stands → **E** | (already spent) |

`E8 idx 0`, whose flush row does not share its clock with a post, was green
before and after — which is why this only ever showed on CALL.  Fix:
`(r_rq_n == 2'd0) && !eu_post`, where `eu_post` is the EU's ordinary
combinational request line, already read by `ann_kill` two blocks above.

`E8` 140→500, `FF.2` 174→500.

## §34 THE CENSUS AND THE GATE LEDGER

### §34.1 The census, step by step

Whole-suite `--cases 0` (169,000 cases over 347 forms), scored by a
form-by-form diff at every step.  **No form regressed at any step.**

| after | cases full | cycle-exact forms | fully green forms |
|---|---|---|---|
| pass 3 (start) | 159,348 | 313 | 313 |
| F22 settled | 159,348 | 313 | 313 |
| F31 (the OPR hold) | 163,784 | 324 | 322 |
| F32 (the divider) | 164,101 | 326 | 324 |
| F33 (the QS=E guard) | **164,787** | **326** | **326** |

F22 moving nothing is the finding, not a disappointment: it is D1's shape —
*a finding whose fix moves no number is still a finding* — and its
falsifier had to be built by hand because the corpus cannot reach it.

### §34.2 The gate ledger

All on the same tree, `--core ucore`, v0.1 at w0.

| gate | command | result |
|---|---|---|
| rungs 1–2d | `check_core.py --core ucore --opcodes B8,8A,8B,88,89 --cases 500` | **2500/2500** |
| rung 3 — family A | `… --opcodes 50,A4` | **1000/1000** |
| rung 6 — family D | `… --opcodes EB,74` | **1000/1000** |
| rung 8 — family C | `… --opcodes D1.4,86` | **1000/1000** |
| rung 12 — the multi-cycle pushes (F31) | `… --opcodes 60,62,CC,CD,CE` | **2500/2500** |
| rung 13 — DIV (F32) | `… --opcodes F6.6,F6.7,F7.6,F7.7` | **2000/2000** |
| rung 14 — CALL (F33) | `… --opcodes E8,FF.2,FF.3,9A` | **2000/2000** |
| **boot march** | `check_boot.py --core ucore 220` | **220/220 MATCHES** |
| G0 | `check_ucore_tables.py` | **9988/9988 PASS** |
| U1 lockstep | `ulockstep.py --suite --waits 0,1,2,3` | **ALL SCENARIOS LOCKSTEP** |
| CE hold | `check_core.py --core ucore --opcodes 88 --cases 100 --ce-div 3 --ce-hold-check` | **0 violations** |
| the MODEL, unmoved | `timed_gate.py --suite tests/v30/v0.1 --forms all` | **169,000/169,000, row-diffs 0** |
| **G3** | `check_core.py --core ucore --opcodes all --cases 0` | **164,787 / 169,000 — NOT MET** |

G3 stated honestly, both numbers, as §29.2 requires: at w0 the sim carries
NO registered residue against silicon (`timed_gate.py` reports
169,000/169,000 arch, 169,000/169,000 window, row-diffs 0), so the two
numbers coincide — **164,787 / 169,000 (97.51 %)** through the golden
comparator, and the same figure minus the (empty) w0 residue.  Excluding
the 12 forms that are unimplemented by design, **164,787 / 166,600 =
98.91 %** of what the RTL is currently built to do.

## §35 WHAT IS LEFT — 21 RED FORMS, 4,213 CASES

Enumerated by MECHANISM this time, not by first divergence.

| group | forms | cost | reading |
|---|---|---|---|
| **the interrupt and HALT entries** | `INT.*` (7), `NMI.*` (2), `HLT.*` (3) | **2,400** | **UNIMPLEMENTED BY DESIGN, and the last such block.**  No interrupt entry, `eu_unhalt` tied 0, no `intr_pending` writer, the POLL pipeline is the static level only.  A RUNG — see §35.1 |
| **strings / ENTER** | `C8` `F3A4` `F3A5` `F3AA` `F3AB` `F2AA` | **1,601** | TWO signatures, and they may be one mechanism: (a) the final `F` pop is LATE because the RTL's `pend_active` is still set at the `E` row (`F3AA idx 2`: golden pops at row 24, RTL at 27, and the window is 3 clocks long); (b) the store DATA is wrong on the middle iterations (`F3A4 idx 1` row 14 `exp 37032 got 0`).  Both live in the every-iteration staging/pairing chain F20 opened |
| **the 1BL status nibble** | `FA` `FB` | 112 | **DIAGNOSED — see §35.3.**  The ONLY divergence is the IE bit of the status nibble (`data_ps`'s `psw_ie`), and the RTL's 1BL flag write is ONE CLOCK LATE, always; it is visible only where a data phase samples the nibble on exactly that clock |
| **`POLL.LO`** | `POLL.LO` | 100 | `qop` at row 3.  `9B`'s `JMP INTR` at `006F` needs the POLL pin pipeline, so it belongs with the interrupt rung |

### §35.1 THE INTERRUPT RUNG — what it is, and the ONE question to settle first

The BIU has carried M14/M15/M18 (INTA) and M16/M17/M20/M21 (HALT) since U1
and they have never fired; `row_is_inta`, `BS_INTA`, `eu_halt`/`eu_unhalt`
and the `poll_pipe` shift register are all already in the EU.  What is
missing is the RECOGNITION and the ENTRY:

1. `CpuT::interrupt()` — the hardware micro-PC force to page 7 opcode 0x00
   (loc 0 = BRK, loc 2 = NMI) or 0x02 (INT), with the loader bypassed and
   every latch it would have written presented explicitly (`xop` MUST be
   cleared — ledger A24 — and `op8`/`imm8`/`bus_word` false, or the vector
   arithmetic at 01EC truncates `2*vector`).
2. `bus_inta` — an ordinary read that carries NO address and NO segment and
   must not go through `sr_segment()` / `sr_is_io()`.
3. `eu_unhalt` and the wake.
4. `intr_pending`'s writer, which is also what `POLL.LO` and the REP
   withdrawal (`0223 JMP INTR`) read.

**Settle this before writing any of it.**  `sim/timed_runner.cpp` states the
firing geometry as MEASURED on all 800 running INT/NMI goldens —

>  `D = max(B, A + pipe)`, pipe = 3 (INT level) / 4 (NMI edge latch),
>  entry = `D + 2`, and at the boundary the successor's opcode pop is RUN
>  BUT SUPPRESSED

— where `A` is the pin assert clock and `B` the boundary's would-pop clock.
But **the sim does not PREDICT `B`: it REPLAYS it**, from the golden's own
pushed frame (`derive_replay`, `set_fire_pc`).  The frozen FSM core *does*
predict it from the pins alone and is 169,000/169,000, so the geometry is
predictable — but its recognition block is a large fitted machine (`int_p`,
`nmi_p`/`nmi_latch`, `shadow`, `ie_p`, the POP-PSW boundary-race law, the
IRET arm, a deeper REP sampling stage), which is precisely the shape the
SIMPLICITY principle says to distrust.

The question the rung opened with was: **what holds the boundary when the
pin has not asserted by `B`?**  **ANSWERED by the third Codex review — see
§36/C5.  Nothing does, and the `max` must NOT be rendered.**  It is an
artefact of the replay driver: `derive_replay()` / `set_fire_pc()` PIN `B`
to the golden's pushed frame first, and only then is that already-selected
boundary delayed by the `max`; the late-assert branch is therefore the
replay compensating for having chosen a boundary the part had already run
past, not a rule the part obeys.  Nothing can selectively hold a boundary
for a pin that has not asserted without foreknowledge, and holding EVERY
boundary against a possible future pin would stall ordinary execution.

**So the ucore's rule is the causal one, and it is small**: pipeline the
INT LEVEL and edge-latch NMI; test the MATURED event at each eligible
boundary; suppress the pop only at the FIRST boundary where the condition
is already true; otherwise pop and go on to the next boundary.  That is
what the frozen FSM core does (`v30_eu.sv`: `pop_want = S_FIRST &&
!irq_take`), and it is what makes it 169,000/169,000 from the pins alone.
The `(A, B)` census `timed_runner.cpp` describes is still worth running —
but as a CHECK on the causal rule, not as the thing being fitted.

### §35.2 Residue booked, not patched

* **The BIU's `opr_held` increment may still carry an off-by-one.**  The
  model holds unless `r == &cur_ && run_ && ci_ > 1`, i.e. it DOES hold at
  `ci_ ∈ {0,1}` = T1 **and T2**; `v30u_biu.sv`'s pairing block increments
  the running cycle's hold only `if (ts == TS_T1)`.  Now that F31 has made
  everything depend on that counter this matters, and no current stimulus
  reaches it (G3 is unchanged either way, and all five push forms are
  500/500).  Registered, with the falsifier: any pairing that lands on a
  running write cycle's T2.
* **The ucore save-state sweep does not pass** (`--ss-sweep` aborts at
  `v30u_biu.sv:1372` `$stop`).  Pre-existing, and `sw/ss_lint.py --core
  ucore` is U3's deliverable per §3/§13; the map changes this pass made
  (three appends, one retirement) are therefore unverified by any sweep and
  are asserted only by the exactly-twice grep.

### §35.3 `FA` / `FB` — DIAGNOSED, NOT LANDED

The 1BL execute strobe is stated by the SPEC and MEASURED there, 250/250
each half (`sim/loader_impl.h`, the `one_byte_logic` block):

> These forms have no ROM row and no `E`.  **The EXECUTE STROBE — the clock
> the flag write COMMITS ON — is the instruction's LAST clock, and that is
> the clock BEFORE the successor's opcode pop.**
>
> even `ip`: the successor's byte is already queued, its pop is at pop+2,
> and the golden shows the NEW IE at **pop+1** — 250/250
> odd `ip`: the pop waits for the next fetch's T4+2, and the golden still
> shows the OLD IE at pop+1 — 250/250

MEASURED on the RTL, `FA idx 4` (an even-`ip` case): the pop rides clock 0,
the golden's successor `F` is at clock 2, and the golden's nibble is
already `2` (IE=0) at **clock 1**.  The EU trace shows `st = S_1BL_LEAD`
STANDING on clock 1 — so the RTL's `psw` write lands on the edge ENDING
clock 1 and the new IE is only visible from clock 2.

The cause is one `stop`, and it is §16's named class for the seventh time.
`S_DECODE2`'s one-byte-logic arm does `st = S_1BL_LEAD; stop = 1'b1;`, so
the earliest edge on which the write can happen is the end of clock 1 —
one clock after "commits on clock 1" requires.  The strobe's WAIT is real
(it is what makes the odd-`ip` half show the OLD value), so the arm cannot
simply be made zero-cost: the retire-lead test has to be taken in
S_DECODE2's OWN edge, with S_1BL_LEAD kept for the case where it is not yet
satisfied.

NOT LANDED, deliberately: `FA`/`FB` are 89.8 % / 87.8 % green and every
other `one_byte_logic` form (`F5` `F8` `F9` `FC` `FD` …) is 500/500, so a
structural change to this arm has more to lose than to gain until it is
made under the same measurement.  The bar for pass 5 is pre-registered:
**`FA` 500/500 and `FB` 500/500 with no other 1BL form moving.**

### §35.4 The strings / ENTER group — where the clocks are, MEASURED

`F3AA idx 2` (`rep stosb`, CX=3) is the sharpest member: **every bus row is
IDENTICAL to the golden through the last store**; only the closing `F` pop
is late, by three clocks (golden row 24, RTL row 27), and the window is
28 rows against 25.  So nothing about the loop's bus behaviour is wrong —
the whole cost is in `run_micro`'s TAIL.

Read against the SPEC, the model's tail costs exactly:

```
if (pend_.active) { if (!opr_fresh_) deliver_read(); emit_pending(); }
   deliver_read()   -- a WAIT: zero clocks when the condition already holds
   emit_pending()   -- ZERO clocks, always (it fills a reserved slot)
biu_.opcode_prefetch(cs);      -- wait_bus(), then the pop rides one clock
if (deferred) biu_.charge(1);  -- M8b
```

The RTL's tail is `S_TAIL` → `S_TAIL_W` → `S_TAIL_POP`, and `S_TAIL`
charges a clock UNCONDITIONALLY (`if (st != S_INSTR_END) stop = 1'b1;`)
where the model charges only for the waits.  `S_TAIL_W` charges another on
its way to `S_TAIL_POP`, against a zero-cost `emit_pending()`.

MEASURED, the falsifying experiment (`S_TAIL` made fully zero-cost,
whole-suite recon at 60 cases, form-by-form diff):

| | forms |
|---|---|
| IMPROVED | `F3A4` 17→32, `F3A5` 15→29, `F3AA` 30→53, `F3AB` 45→51, `F2AA` 36→42 |
| REGRESSED | `50` 60→3, `6A` 60→0, `86` 60→19, `87` 60→19, `A2` 60→1, `A3` 60→1, `EE` 60→0, `EF` 60→1 |

REVERTED.  The result is the finding: **`S_TAIL`'s charge is not one event.**
It is right for the eight forms that regressed and wrong for the string
tail, so what is wrong is the CONDITION, not the `stop` — which is §16's
named class yet again, and the same shape as F11: a state that charges for
two different reasons will be fitted to one of them.  The next pass should
derive the tail's clocks from the model's three terms above
(`deliver_read`'s wait, `opcode_prefetch`'s wait + pop clock, M8b's
`charge(1)`) rather than from the state graph, and the pre-registered bar
is: **the six strings/ENTER forms green and none of those eight moving.**

The group's SECOND signature — a wrong store DATA on middle iterations
(`F3A4 idx 1` row 14 `exp 37032 got 0`) — is NOT yet shown to be the same
mechanism and must be triaged separately.  Note for that triage: reading
the SPEC, `pend_.active` is TRUE at the `E` row in the MODEL too for
`REP STOS` (the last iteration's write is staged and never paired, because
`emit_pending` fires only when `opr_fresh_` and a string loop refreshes OPR
once), so the DEFERRAL itself is faithful and must not be "fixed".

## §36 THE THIRD CODEX REVIEW (2026-08-03, thread `019fc8ba` resumed again)

**A note on the method first, because it cost 43 minutes.**  The review was
first asked as ONE prompt carrying seven questions and the whole of §33-§35.
It read the tree, made four source greps, and then WEDGED — no output for
39 minutes, cancelled at 43.  Re-asked as two SHORT prompts naming exactly
what to read, it answered both in 37 and 44 seconds.  Booked as a working
rule: **a review prompt is not a brief.  Ask one question, name the files,
demand a verdict line.**

Two findings, both UPHELD, and the second is the one that matters.

### C4 — M13's 8080 arm of `wait_opr_free` was never rendered.  **LANDED.**

Q: F31 collapsed the OPR interlock to ONE view (the registered level) while
F18 had insisted the READ side needs a register-only LOOKAHEAD.  Both are
"a deadline the row runs on".  Is one of them now wrong?

A: **"PRINCIPLED BUT FRAGILE."**  The asymmetry is correct, and Codex stated
the distinction in one line that is worth keeping verbatim:

> read completion is a future eval-derived timestamp becoming due on this
> edge; OPR release is a T2 ownership transition whose post-edge registered
> level defines T3.

`wait_next_read` waits `while (clk_ < rd_done_q_.front())` on a deadline
PUSHED at `e + 2` — a timestamp, so the row must see it becoming due, which
is the lookahead.  `wait_opr_free` waits on a LEVEL whose T2 decrement makes
the registered zero visible during T3.  Two different kinds of fact, two
different views, and F18 and F31 are both right.

The FRAGILITY is the finding: `wait_opr_free()` opens with
`if (md8080_ && *md8080_) { wait_bus(); return; }` — M13, "in 8080 emulation
mode the store does not let go until it has RETIRED", stretching with the
eval — and **the EU had no mode term at all**, in F31's rendering or in the
pulse rendering it replaced.  Pre-existing, not F31's; but F31 made
`opr_free_now` the one place it can live, so it lives there now:

```
wire opr_free_now = mode8080 ? retire_ok_n : eu_opr_free;
```

`retire_ok_n` IS the RTL's `wait_bus` deadline, so the arm is the SPEC's own
line and nothing is fitted.  UNREACHABLE on the current stimulus (`mode8080`
is set only by an `MFC` row; the 8080 loader / BRKEM path is ledger R4), so
the census proves the no-op — G3 164,787 either way, zero forms moved.
D1's shape again.  *Falsifier*: the first 8080-mode store the ucore
executes, which is R4's gate.

### C5 — the interrupt boundary's `max` is a REPLAY ARTEFACT.  **DECISIVE.**

Q: is `D = max(B, A + pipe)` renderable as hardware — what holds the
boundary when the pin has not asserted by `B`?

A: **it is not, and nothing does.**

> Nothing can selectively hold boundary `B` for a pin that has not yet
> asserted without foreknowledge; holding every boundary awaiting a possible
> future pin would stall ordinary execution.

The evidence is the order of operations in the driver itself:
`derive_replay()` and `set_fire_pc(rp.resume_ip)` PIN `B` to the golden's
pushed frame FIRST, and only afterwards is that already-selected boundary
delayed by the `max`.  The late-assert branch is the replay compensating for
having chosen a boundary the part had already run past — not a rule the part
obeys.  And the frozen FSM core, which scores 169,000/169,000 from the pins
alone, contains no such term: at `S_FIRST` it suppresses the pop only when
the pipelined event is ALREADY recognised (`pop_want = S_FIRST && !irq_take`)
and otherwise pops and continues to the next boundary.

**This is the most valuable answer of the three reviews**, because it stops
pass 5 from fitting a forward-looking term into hardware that cannot have
one.  §35.1 is rewritten around it: pipeline the INT LEVEL, edge-latch NMI,
test the matured event at each eligible boundary, suppress only the FIRST
boundary where the condition is already true.  The `(A, B)` census stays —
as a CHECK on that causal rule, not as the thing being fitted.

### Not reached

The wedged first attempt also carried questions on `opr_free_p`'s
vacuity, the BIU's `opr_held` T2 increment (§35.2), F33's `!eu_post`
equivalence, the SS-map retirement, and whether the strings' two signatures
share a mechanism.  **None of those were answered**; they stand as I left
them, and they are the natural opening for the fourth review.

## §37 HANDOFF — what pass 5 picks up

**The order is by cost, and every item below is already diagnosed to a
named mechanism or to a named question.  Nothing here is a search.**

1. **THE INTERRUPT AND HALT RUNG — 2,400 cases, the last
   unimplemented-by-design block.**  Open with §35.1's question and do the
   `(A, B)` census BEFORE writing a line of recognition logic.  The entry
   itself (`CpuT::interrupt()`'s micro-PC force + latch presentation,
   `bus_inta`, `eu_unhalt`) is fully specified by the SPEC and is
   mechanical; only the RECOGNITION is open.  This is also what fires the
   BIU's M14/M15/M18 and M16/M17/M20/M21, unfired since U1, and what gives
   the `eu_halt` one-clock-lead contract (§11.6) its first verification.
   `POLL.LO` (100 cases) closes with it — `9B`'s `JMP INTR` at `006F` reads
   the same latch.
2. **The strings / ENTER tail — 1,601 cases, §35.4.**  `S_TAIL`'s charge is
   two events wearing one `stop`.  Derive the tail's clocks from the
   model's three terms, not from the state graph; the falsifying experiment
   and its 5-improve / 8-regress split are already recorded, so the next
   attempt starts from evidence.  Then triage the group's SECOND signature
   (the middle-iteration store DATA) separately — and do NOT "fix" the
   deferral, which is faithful.
3. **`FA` / `FB` — 112 cases, §35.3.**  One `stop` in `S_DECODE2`'s
   one-byte-logic arm; the bar is pre-registered.
4. **The two booked residues of §35.2**: the BIU's `opr_held` T2 increment,
   and the ucore save-state sweep (U3 owns `ss_lint --core ucore`).
5. **The WAIT AXES are NOT untouched — MEASURED at the close of this pass,
   and the news is good.**  The standing wait-axis cells of the gate quick
   reference, run on the ucore for the first time:

   | cell | command | ucore |
   |---|---|---|
   | `v0.1-w1` all forms | `check_core.py --core ucore --suite-dir tests/v30/v0.1-w1 --waits 1 --opcodes all --cases 0` | **1200/1200** |
   | `v0.1-w3` all forms | `… --suite-dir tests/v30/v0.1-w3 --waits 3` | **1200/1200** |
   | `v0.1-w1 --forms EB` | `… --opcodes EB` | **200/200** |
   | `v0.1-w0evt` | `… --suite-dir tests/v30/v0.1-w0evt --waits 0` | 0/200 — the interrupt rung |
   | `v0.1-w1evt` | `… --suite-dir tests/v30/v0.1-w1evt --waits 1` | 0/800 — the interrupt rung |

   So F31's OPR-release instant — which the SPEC states does NOT stretch
   with the eval (11.4, the FIXED index 2) — **is** exercised at w1 and w3
   and holds, and the three non-evt wait cells are GREEN on the same tree
   that scores 164,787 at w0.  The evt cells are exactly the interrupt
   rung and nothing else.  U3 still owns the wait axes proper (the random-
   wait tranche gate is the campaign's victory condition); what this pass
   adds is that the ucore does not enter U3 with a wait-axis debt on the
   scripted cells.  **Re-derive any residue there; do not carry a figure
   forward from memory.**
6. **Still not run**: `ulockstep` batch mode over golden cases.
7. **The method that produced this pass**, for the record: every rung was
   scored by a form-by-form diff of two whole-suite censuses
   (`sw/ucore_census.py LOG BASELINE`), never by the total; every fix was
   traced to a single model line with `sw/uscope.py FORM IDX --rowtrace`
   before it was written; and the two findings that moved no number (F22)
   or were reverted (§35.4) are in the ledger with the same weight as the
   ones that did.

## §38 THE FOUR FINDINGS OF PASS 5

### F34 — RECOGNITION IS CAUSAL, AND THE BOUNDARY IS A WINDOW

**Class: SPEC (composition).  The last unimplemented-by-design block, and the
largest single move of the campaign: +2,232 cases at w0 and +1,654 across the
four `evt` wait cells, which were 0 to a case.**

§36/C5 settled what NOT to build: `timed_runner.cpp`'s `D = max(B, A + pipe)`
is an artefact of the replay driver and no hardware term can hold a boundary
for a pin that has not asserted.  What is left is small, and every piece of it
is a sentence of `docs/facts/interrupt_model.md` transliterated:

* the INT LEVEL and the IE GATE through **three flops** ("the decision at B
  sees the pin level of cycle B-3"), the NMI EDGE latched at edge+3 ("latest
  catching edge = B-4").  The IE pipeline is why there is no separate EI
  shadow flag, and `INT.FB` needs nothing of its own.
* **THE BOUNDARY IS A WINDOW, NOT A CLOCK.**  `boundary_no_pop()` returns the
  RETIRE deadline; the part then SITS at the pop point until the byte arrives
  and `irq_take` is a LEVEL sampled on every clock of that wait.  That is the
  plain reading of the frozen FSM's `pop_want = (S_FIRST && !irq_take)`, and
  it is what the goldens show — MEASURED, `INT.90 idx 14`: the retire is met
  on row 3 with a dry queue, the pin matures on row 4, and the chip's row-4
  pop is SUPPRESSED.  A one-clock boundary declines it and pops.
  The window is also what makes the replay's `max` *look* right: the replay
  had already chosen a boundary that fires.
* the POP is what CLOSES the window, so the pop is what SPENDS the sreg
  shadow — "the chip re-enables the boundary sample at the shadowed
  instruction's successor pop", verbatim.
* the shadow is a **DECODE-TIME CLASS** (`pla3_sreg_mov`), not a sreg WRITE.
  The write-derived rendering was built first and is REFUTED by the model's
  row order: `8E`'s sreg write is on the POST-`E` row (`0.8e.1`), which runs
  AFTER the cadence, so at the boundary no write has happened yet and the
  golden still skips the sample (`INT.8ED0 idx 16` row 4).
* the ENTRY is `CpuT::interrupt()` verbatim — page 7 opcode `0x00` loc 0/2
  (BRK/NMI) or `0x02` (INT), the loader bypassed and every latch it would have
  written presented explicitly (`xop` cleared or the vector fetch's `SR = IO`
  re-classifies; `op8` false or 01EC's `2*vector` truncates) — one internal
  decision clock after the boundary, so the first ROM row runs at **B + 2**.
* THE WAKE.  A halted part has no boundary, so the decision clock D is the
  first clock the pipeline has matured the event; the would-pop clock is D+1
  and the entry is two past that.  `timed_runner.cpp`'s three HALT numbers
  fall straight out: `HLT.RES` pop at A+4, `HLT.INT` entry at A+6 with the
  prefetcher restarting at the DECISION, `HLT.NMI` entry at A+7 with the bus
  HELD until the entry clock.  The INT wake is IE-INDEPENDENT (where the V30
  differs from the 8086); a masked INT is the same `S_OPC_POP` with `irq_take`
  false.
* `intr_pending` has exactly the writer the SPEC gives it and no other: the
  REP iteration boundary, sampled one flop deeper, latched so the withdrawal
  path's own `0223 JMP INTR` reads it back.

There is EXACTLY ONE boundary evaluation per pop point, and every pop point is
one: the `E` row's cadence, `S_EPOP`, `S_TAIL_POP`, the tail's zero-cost
fall-through (`tailw_go`), and the cold `S_OPC_POP` of a pre-decode-executed
predecessor (`bnd_armed` — which is also what keeps a PREFIX's pop from being
a boundary, because the model's prefix loop is inside `loader_decode`).

**GOVERNANCE, as the review scoped it:** recognition timing differences
against the SIM on `evt` cases are EXPECTED — the sim replays — so the gate for
this rung is the GOLDEN (`check_core`), with `ulockstep` informative only.  In
practice the exception was never exercised: `ulockstep`'s scenarios carry no
pin events and it is ALL SCENARIOS LOCKSTEP on the same tree.

### F35 — THREE FIRST VERIFICATIONS OF CODE THAT HAD NEVER FIRED

The BIU's M14/M15/M18 and M16/M17/M20/M21 had been carried since U1 and never
run.  Firing them found three faults, and none of them is the rung's:

* **M16: `halted` was applied to the prefetch grant IN THE SAME EDGE as
  `eu_halt`.**  `note_halt` sets `halt_pending_` and `halted_` together in the
  model, but the two are read from opposite ends of `tick(c)` — the DISPLAY
  block is at the TOP and claims clock `c` itself (which is why `eu_halt`
  leads), while `halted_` is read by the prefetch eligibility at the END, and
  the model's `note_halt` runs at `clk_ = pop+1`, i.e. after `tick(pop)` has
  already granted.  So only `halt_pending` belongs at the top of the edge;
  `halted` is applied past the grant.  MEASURED, `HLT.RES idx 1`: the golden's
  CODE display / T1-T4 on rows 1-5 and the HALT only on row 6, where the RTL
  refused the fetch outright.  300 of the 600 HALT cases.
* **the backdoor preload did not walk the injected bytes for
  `last_fetch_addr`**, as `queue_preload` does, so every HALT display in the
  corpus drove address 0.
* **the `sev` bound assertion is wrong for the HALT pseudo-cycle**, found by
  the WAIT AXIS: by M21's own arithmetic the HALT's status release is at index
  1 while its T4 is at `3 + waits`, so `sev = 3` is correct there at any wait
  level above zero.  `HLT.INT` / `HLT.RES` went from SIM FAILED to 200/200 at
  w1 and w3.

...and `poll_pipe` comes out of reset holding the PIN, not ones, which is the
`POLL.LO` half that failed at row 3 (`poll_busy()` reads a statically low
POLL_N as not-busy on clock 0).

### F36 — A PURE-ALIAS WIRE IS NOT THE PRE-EDGE VIEW.  F11b's trap, third form

This module's convention is that a WIRE read inside the clocked block still
holds the clock the edge CLOSES, which is what lets block (a) update registers
with blocking assignments at the top of the edge.  **That is true of a wire
with logic in it and FALSE of `wire w = r;`** — a pure alias is substituted,
so the step reads the register LIVE.

MEASURED: `HLT.NMI` woke one clock early on every case (entry at A+6 where the
golden has A+7) because `S_HALTED` read `nmi_latch` the moment block (a) set
it.  The fix is structural, not a rename: the pin pipelines advance at the
**END** of the edge (block (g)), so those registers carry the clock-`c` view
for the whole edge and nothing depends on read order.  They are read from BOTH
sides of the module — the combinational act decode gates `q_pop` with
`irq_fire` — and the two MUST see the same clock or the demand and the take
drift, which is F11 again.

### F37 — THE 1BL EXECUTE STROBE IS THE HANDING-OVER EDGE (§35.3, LANDED)

Pre-registered bar MET: `FA` 500/500, `FB` 500/500, and no other
one-byte-logic form moved (`F5` `F8` `F9` `FC` `FD` all 500/500).  `INT.FB`
closed with them, 139 → 200 — it was never an interrupt fault.

The model is `charge(1); wait_retire_lead(); <write>; charge(1);`, so the write
commits at `clk_ = pop+1`: it is VISIBLE DURING the clock `S_DECODE2` hands
over to, and therefore has to be MADE ON THE EDGE THAT HANDS OVER.  The wait's
condition is available there — `q_ripe_lead_n` is the next-state view and IS
`wait_retire_lead`'s test at `clk_ = pop+1`, exactly.  `S_1BL_LEAD` becomes a
PURE WAIT for the case where it is not yet satisfied and `S_1BL_CHG` is the
trailing `charge(1)` both paths owe; the write itself moved to
`v30u_eu_1bl.svh`, one expression for both arms.

### F38 — THE STRING TAIL WAS THREE F11s, AND `S_TAIL`'s CHARGE WAS NOT ONE

§35.4 booked "`S_TAIL`'s charge is not one event ... what is wrong is the
CONDITION, not the `stop`".  **The condition is right and the `stop` is
right**: `S_TAIL`'s `stop` IS the `E` row's own `charge(1)` on every path into
it (the E-row cadence, the `S_EPOP` pop, and the `pend_after` hand-over), which
is why pass 4's zero-cost experiment regressed eight forms.  What was wrong is
three separate things, and each is F11 — one event, two reconstructions:

1. **`emit_pending()` IS ZERO CLOCKS** (it fills a slot the bus has already
   reserved) and `deliver_read()` is a WAIT.  `S_TAIL_W` charged a clock on its
   way to `S_TAIL_POP` regardless.  The satisfied arm now falls through inside
   the same edge — and the act decode needs `tailw_go`, because the first
   attempt without it ate a byte the BIU was never asked for (the three string
   forms' ARCH fell to their cycle counts while nothing timed moved: a
   REGRESSION `ucore_census` does not see, since it scores `full` only).
2. **THE `stall_slot` ARM PAIRED IN THE ACT AND NOT IN THE STEP.**  `bus_write`
   is `if (pend_.active) { deliver_read(); emit_pending(); } write_request()`
   — the staged write is paired BEFORE the slot is waited on.  `eu_pair`
   carried no slot term (correctly), so the BIU took the word while
   `pend_active` stayed set; the row then re-ran `row_pre_wait` against an OPR
   the pairing had just re-taken and cost TWO extra clocks.  MEASURED, `F3AA
   idx 2`: the third store row stands on rows 13-17 where the model stands on
   13-15, with `eu_pair` already asserted on 13 and `pnd` still 1.
3. **F11a's READ-SIDE RULE WAS MISSING FROM `opr_now`.**  When the completion
   IS the lookahead the word is not in the store yet — block (a) puts it there
   in the same edge — so the act decode must read `eu_rdata_n` directly.
   `opr_live` had this for the `F` row and `opr_now`'s pre-deliver arm did not,
   so every `REP MOVS` middle iteration whose read landed on the pairing clock
   drove the STALE OPR: `F3A4 idx 1` row 14, exp 37032 got 0.

That third one is §35.4's booked SECOND SIGNATURE, and it closed `C8`, `F3A4`
and `F3A5` together — **the two signatures were one mechanism after all**, and
the deferral was never touched, exactly as §35.4 required.  Pre-registered bar
MET: the six strings/ENTER forms green and none of the eight moving.

## §39 THE CENSUS AND THE GATE LEDGER

### §39.1 The census, step by step

Whole-suite `--cases 0` (169,000 cases over 347 forms), scored by a
form-by-form diff at every step.  **No form regressed at any step.**

| after | cases full | cycle-exact forms | fully green forms |
|---|---|---|---|
| pass 4 (start) | 164,787 | 326 | 326 |
| F34/F35/F36 — the interrupt and HALT rung | 167,019 | 335 | 335 |
| F37 + F38 — the 1BL strobe and the string tail | 168,815 | 345 | 345 |
| the tail's own boundary | **168,886** | **345** | **345** |
| the two §35.2 residues (no-ops, as predicted) | 168,886 | 345 | 345 |

**Twenty-one forms moved and two are left.**

### §39.2 The gate ledger

All on the same tree, `--core ucore`.

| gate | command | result |
|---|---|---|
| **G3** | `check_core.py --core ucore --opcodes all --cases 0` | **168,886 / 169,000 (99.93 %)** |
| **boot march** | `check_boot.py --core ucore 220` | **220/220 MATCHES** |
| G0 | `check_ucore_tables.py` | **9988/9988 PASS** |
| U1 lockstep | `ulockstep.py --suite --waits 0,1,2,3` | **ALL SCENARIOS LOCKSTEP** |
| CE hold | `… --opcodes 88 --cases 100 --ce-div 3 --ce-hold-check` | **0 violations** |
| **save state** | `… --ss-sweep` over 10 forms | **PASS, 616 freeze points** |
| the MODEL, unmoved | `timed_gate.py --suite tests/v30/v0.1 --forms all` | **169,000/169,000, row-diffs 0** |
| `v0.1-w1` all forms | `… --suite-dir tests/v30/v0.1-w1 --waits 1` | **1200/1200** |
| `v0.1-w3` all forms | `… --suite-dir tests/v30/v0.1-w3 --waits 3` | **1200/1200** |
| `v0.1-w1 --forms EB` | `… --opcodes EB` | **200/200** |
| `v0.1-w0evt` | `… --waits 0` | 167/200 (INT.F3AA only) |
| `v0.1-w1evt` | `… --waits 1` | **1050/1200** |
| `v0.1-w2evt` | `… --waits 2` | 174/200 (INT.F3AA only) |
| `v0.1-w3evt` | `… --waits 3` | **1063/1200** |
| HLT delay sweeps (FIRST ucore measurement) | `s10-hltsweep-w{0,1}`, `s13-hltsweep-w{2,3}` | 88/97, 86/95, 35/46, 32/45 |

G3 stated honestly, both numbers, as §29.2 requires: at w0 the sim carries NO
registered residue against silicon, so the two numbers coincide — **168,886 /
169,000 through the golden comparator**, and the same figure minus the (empty)
w0 residue.  **There are no longer any forms unimplemented by design**, so the
second figure §34.2 quoted (excluding 12 such forms) no longer exists: 99.93 %
is of everything the part does in this suite.

Every `evt` cell was **0** at the start of this pass.  The quick-reference
numbers for the four HLT delay sweeps are the FSM's ratchets and are NOT a
ucore ratchet; these are the ucore's first.

## §40 WHAT IS LEFT — 2 RED FORMS, 114 CASES

> **SUPERSEDED BY §42 (pass 6): both forms are CLOSED and G3 is
> 169,000/169,000.**  The diagnoses below were both correct and are kept
> verbatim — including the tap-depth scan booked here as a negative result,
> which §42/F40 then showed was negative *for a reason*.  §40.1's residue
> list is carried forward in §42.6 minus `ss_field_width`, which §42.2 closed.

| form | cost | mechanism, diagnosed |
|---|---|---|
| `INT.9D` | 89 | **ALL of them pre-IE=0.**  The chip's flag register takes the popped image at the READ'S DATA EDGE — "the new IE shows in the PS bits during the read's own T4" — three clocks before the `OPR -> FLAGS` row writes it, so the following boundary's `ie_p[2]` sees IE=1 and this rendering's does not.  MEASURED, `idx 1`: the golden's PS nibble is 5 from row 9 and the RTL's is 1 until row 12.  The 111 pre-IE=1 cases PASS, which is the reason the POP-PSW boundary race law is **not** needed here: "pre-IE=0 pops never race, 89/89 class A in the tranche". |
| `INT.F3AA` | 25 | the REP abort's **ANCHORING** law, not the pin pipeline: the first boundary is POP-anchored (a fixed opcode-pop+7 decision edge, flush at pop+16), chained ones are WRITE-ACCEPT-anchored, and "a next-iteration write issued but not yet committed at the edge is withdrawn (no bus activity)" — the RTL issues that withdrawn store (`idx 0` row 14, exp PASV got MEMW).  **A DEPTH SCAN OF THE REP TAP IS RECORDED AS A NEGATIVE RESULT**: `int_p[0]` 174, `[1]` 178, `[2]` 179, `[3]` 175.  There is no clean fit, so the tap stays at the depth `interrupt_model.md` MEASURES (pin@edge-4 = `int_p[3]`) and the four cases `int_p[2]` would buy are left on the table rather than fitted. |

### §40.1 Residue booked, not patched

* **The far-CALL / far-JMP `CS` shadow** is documented ("the sreg-load /
  far-CALL recognition shadow") and is NOT in the ucore's decode class; no
  golden combines it with a pin event.
* **The taken-branch recognition boundary** (`post_flush`, tapping one clock
  earlier at a flush) is a fuzz-seed refinement in the FSM and is not
  rendered; no golden reaches it.
* **`ss_field_width` has no EU entries**, so save-state mode 5 (the round-trip
  width sweep) still treats the whole EU region as unmapped.  SS1 passes;
  mode 5 is U3's, with `ss_lint --core ucore`.
* **`opr_free_p` / `set_oprfree`** stay documented as PROVABLY VACUOUS (F31),
  and the `opr_held` T2 fix is visible only through them.

## §41 HANDOFF — what U3 picks up

> **SUPERSEDED BY §42.6.**  Items 2 (the two red forms), 3 (`ss_field_width`'s
> EU half) and 4 (`ulockstep` batch mode) were closed in pass 6; the U3 handoff
> that stands is §42.6.

1. **The ucore enters U3 with no wait-axis debt on the scripted cells** and
   with the whole `evt` axis measured for the first time.  The random-wait
   tranche gate is the campaign's victory condition and is U3's.
2. **The two red forms above**, both diagnosed to a named mechanism.  Neither
   is a search; `INT.9D` is one rendering decision (where the flag register
   takes a popped image from) and `INT.F3AA` is the abort's anchoring law,
   which the FSM has and the SPEC does not (the sim REPLAYS it, so there is no
   transliteration available — it would have to be fitted, and this pass
   declined to).
3. **`ss_lint --core ucore`** (§3/§13) now has a working SS1 sweep to build on,
   and owes `ss_field_width` its EU half.
4. **Still not run**: `ulockstep` batch mode over golden cases.
5. **The method, unchanged and still the thing that worked**: every rung scored
   by a form-by-form diff of two whole-suite censuses, never by the total;
   every fix traced to a single model line with `uscope.py FORM IDX` before it
   was written; and the two experiments that were REVERTED or came out NEGATIVE
   (the write-derived shadow, the REP tap depth scan) are in this ledger with
   the same weight as the ones that landed.
   One addition: **`ucore_census.py` scores `full` only.**  The zero-cost
   `S_TAIL_W` attempt regressed three forms' ARCH by 836 cases and the delta
   read "REGRESSED: none".  Read the `arch` column too.

## §42 PASS 6 — THE G3 CLOSE, AND THE U2 CLOSE STATEMENT

**`check_core.py --core ucore --opcodes all --cases 0` = 169,000 / 169,000.**
Both of §40's diagnosed forms closed on the mechanism §40 named; no form
regressed on either the `full` or the `arch` column; and all four `evt` cells
went to 100 % with them.

### §42.1 The governance call, made FIRST, because it decided the method

§40 handed pass 6 two forms with the instruction "verify the diagnosis against
the sim first — the sim passes these goldens, so the mechanism IS in the sim
somewhere".  **It is not, and that is the finding that governs both.**
`sim/pin_replay.h` is explicit about it:

* the firing BOUNDARY is read out of *the golden's own pushed frame* at
  `SS:SP` (`derive_replay`: `resume_ip = word(sp)`), and
* the REP ELEMENT COUNT is read out of *the golden's own bus trace*
  ("Counted as MEMW cycles ahead of the first INTA row").

`CpuT::at_fire_boundary()` is a comparison against those two replayed
coordinates; the model has **no IE pipeline, no pin tap and no anchoring law
at all**.  So neither form is an RTL-vs-sim divergence: there is no sim
rendering to diverge from.  Both are **RTL-vs-silicon, on an axis the sim does
not share** — exactly F34's scoped exception ("the gate for this rung is the
GOLDEN, with `ulockstep` informative only"), and both were therefore built from
`docs/facts/interrupt_model.md` and scored on `check_core`.

The exception was again never *abused*: `ulockstep --golden all` is **1,735 /
1,735 ALL CASES LOCKSTEP** on the same tree (§42.4).

### F39 — THE FLAG REGISTER IS FED BY THE DATA LATCH, NOT BY THE ROW

**Class: SPEC (transliteration).  `INT.9D` 111 → 200; and the masked column it
also fixes is the confirmation.**

`interrupt_model.md`, verbatim: *"POP PSW consumes the popped image at its
read's data edge (the new IE shows in the PS bits during the read's own T4)."*

The rendering is one sentence and it names no opcode: **a micro-row's
destination write-enable is a LEVEL for as long as the row STANDS.**  A row
blocked on its `F` interlock has its control decoded and its destination
selected; a destination fed from the read latch therefore takes the word the
instant the latch closes, not when the row finally releases.  For every other
destination that is invisible — nothing runs between the row's arrival and its
release — but FLAGS is wired to the outside world twice over (S5 on the status
pins, and the IE gate of the recognition pipeline), so there the early load
SHOWS.

The BIU publishes the edge (`eu_rd_edge` / `eu_rd_edge_d`): the T3/Tw → T4
advance, which *is* the READY sample and *is* the edge the data latch closes
on, with `cur_data` holding the word since the end of T2.  Register-only plus
`ready`, exactly like `done_fire`, so it closes no loop.  The EU takes it in
block (a), after `ie_now` is frozen, so the pipeline still sees the OLD IE on
the edge that writes.

MEASURED, `INT.9D idx 1`.  The read's T3 is row 8, its T4 row 9:

| clock | golden | RTL before | RTL after |
|---|---|---|---|
| 9 (T4) | PS nibble **5** | 1 | **5** |
| 10 | pop `90` | pop `90` | pop `90` |
| 13 (the boundary) | pop **SUPPRESSED**, INTA follows | pops the next `90` | pop **SUPPRESSED** |

`ie_p[2]` is IE at c-3, the boundary stands on row 13, so IE has to be up by
row 10 — which the T3→T4 write gives and the row's own release (edge 10) does
not.  All 89 failing cases were pre-IE=0 pops; the 111 pre-IE=1 ones never
needed it, which is why the POP-PSW boundary RACE law is not in the ucore
("pre-IE=0 pops never race", 89/89 class A in the tranche).

**The rule hits EXACTLY TWO ROM rows.**  `OPR -> FLAGS ... F` is `007A`
(POP PSW) and `01EA` (RETI) and nothing else — which is the same pair E1
measured on silicon ("µ01EA's flag commit obeys the SAME race table as POP
PSW's µ007A", 108/108 H-IDENTICAL).  The frozen FSM core renders this as
`opc == 8'h9D && eu_rd_now` plus a second copy inside `iret_pw`; this is that
behaviour with the opcode test and the duplication removed.

**INDEPENDENT CONFIRMATION, on a column the comparator MASKS.**  `check_core`
compares col 1 only on driven rows, so the T4 PS nibble is scored by neither
gate — yet the RTL now reproduces the golden's `5fad2` on row 9 bit for bit.
The fix was fitted to the recognition and the display came out right by itself.

*Falsifier*: any `OPR -> FLAGS` row whose flag write is NOT visible at its
read's T4, or any third ROM row acquiring that source/destination pair.

### F40 — THE REP ABORT HAS TWO ANCHORS, AND THAT IS WHY THE TAP SCAN HAD NO FIT

**Class: SPEC (transliteration).  `INT.F3AA` 175 → 200 at w0, and the whole
`evt` wait axis with it: 167/1050/174/1063 → 200/1200/200/1200.**

§40 recorded a tap-depth scan as a NEGATIVE result — `int_p[0]` 174, `[1]` 178,
`[2]` 179, `[3]` 175 — and declined to fit one.  **It was right to decline: no
single depth is correct, because the two boundaries are anchored to DIFFERENT
EDGES.**  `interrupt_model.md` says so in one paragraph:

> the boundary-1 decision edge sits at a fixed **opcode-pop+7** ... its flush is
> invariant at pop+16 = edge+9 ... Chained boundaries (>= 2) are
> **write-accept-anchored**: decision at the accept edge, flush at accept+9.

The `JMP REP` row (`00C0`) stands at opcode-pop+6.  So, measured from the row's
own clock `c`:

| boundary | decision edge | pin tap (edge-4) | flush |
|---|---|---|---|
| 1 (pop-anchored) | `c + 1` = pop+7 | `int_p[2]` | `c + 10` — the row cadence, unchanged |
| ≥ 2 (accept-anchored) | `c + 2` = the write's accept | `int_p[1]` | `c + 11` — **one extra clock** |

**Both taps are `edge - 4`.**  Nothing is fitted; what changed is the reference
edge, and the SAME one clock moves the pin sample AND the flush.  That second
half is the model's own line — `if (rep_elems_ >= 2) biu_.charge(1 + ...)`,
whose comment already said "A CHAINED REP ABORT'S DECISION EDGE IS ONE CLOCK
LATER THAN THE LOOP ROW'S" — and the ucore had never rendered it.

WHY the chained edge is later, in one sentence: **on a chained iteration the
element's own store is still PENDING at the loop row** (after the first
iteration nothing refreshes OPR, so the cycle only runs when the next one is
registered — the model's own note in `kCondRep`), so its accept has not
happened yet and the boundary waits for it.

MEASURED over all 56 `INT.F3AA` mid-string aborts, before any change:

* golden flush − opcode-pop = **16 in ALL 35** one-element aborts;
* golden flush − (last completed element's write T1) = **8 in ALL 21** chained
  ones (14 at two elements, 7 at three) = accept + 9.

That is the two-anchor law read straight off the corpus, and it is uniform —
no floating term, no per-case residue.

The RTL carries a one-bit `rep_chain` (the boundary's anchor selector, the
model's `rep_elems_ >= 2`), reset by `begin_sequence()` and read BEFORE its own
update, exactly as the model reads its counter after the increment.  The extra
clock is `bubble = 1` on the not-taken arm, i.e. the sequencer's existing
`S_ROW_CHG`; no new state machine.

*Falsifier*: any chained abort whose flush is not at the loop row + 11, or any
one-element abort that needs it — the same falsifier the model already carries,
now with the pin tap inside it.

### §42.2 The two owed instruments

**`ss_field_width` had no EU entries for a MECHANICAL reason.**  The function
was placed BEFORE the EU localparams, so every `SSA_E_*` (and the two
`SSA_B_*` declared after it) fell through to `default: 0` and mode 5 silently
skipped them — §40.1's "no EU entries" was the symptom, not the cause.  Moved
to the END of the package and filled in: **211 entries**, each derived from the
read mux's own slice and cross-checked against the write decode's — 0
mismatches over 96 BIU + 115 EU arms.

**Its first EU-enabled run found a real one**: `SSA_B_OPR_HELD` was declared 1
bit and `opr_held` is a 2-bit counter (M13 / 11.4 / F31).  Mode 5 exists
exactly to catch a hand-written width table drifting from the RTL, and it
caught the only entry that had drifted.  This is a D1-shaped result: a latent
save-state fault that moved no functional number.

**`ulockstep --golden`** is the standing instrument's missing leg (§37 item 6,
§41 item 4).  Whole golden CASES through BOTH engines from the same backdoor
injection — `v30sim timed-run` and the ucore TB's `+batch` consumer — diffed
clock for clock over `check_core`'s own window `[first F .. F #n_close]`, under
`ulockstep`'s documented column policy.  No golden is involved: this is the
MODEL-vs-RTL comparison that `check_core` (RTL-vs-golden) and `timed_gate`
(model-vs-golden) cannot make between them.

The window is load-bearing and is not a mask: the two DRIVERS record a
different number of trailing clocks past the case's close, which is a property
of the drivers and not of the part.

### §42.3 The census

Whole-suite `--cases 0` (169,000 cases over 347 forms), scored by a form-by-form
diff of two censuses on **both** the `full` and the `arch` column (§41's
lesson).  **No form regressed at either step.**

| after | cases full | cycle-exact forms | fully green forms |
|---|---|---|---|
| pass 5 (start) | 168,886 | 345 | 345 |
| F39 — the flag register's data edge | 168,975 | 346 | 346 |
| F40 — the REP abort's two anchors | **169,000** | **347** | **347** |

**Two forms moved and NONE are left.**

### §42.4 The gate ledger — all on this tree, `--core ucore`

| gate | command | result |
|---|---|---|
| **G3** | `check_core.py --core ucore --opcodes all --cases 0` | **169,000 / 169,000 (100 %)** |
| **boot march** | `check_boot.py --core ucore 220` | **220/220 MATCHES** (loop period 64 both legs) |
| G0 | `check_ucore_tables.py` | **9988/9988 PASS** |
| U1 lockstep | `ulockstep.py --suite --waits 0,1,2,3` | **ALL SCENARIOS LOCKSTEP** |
| **U2 lockstep (NEW)** | `ulockstep.py --golden all --cases 5` | **1735/1735 ALL CASES LOCKSTEP** (347 forms) |
| CE hold | `… --opcodes 88 --cases 100 --ce-div 3 --ce-hold-check` | **100/100, 0 violations** |
| save state, scramble | `… --opcodes 89,8B,B8,E8 --cases 20 --ss-sweep 3 --ss-mode 1` | **80/80**, every freeze point `PASS` |
| save state, idempotence | `… --opcodes 89,8B --cases 12 --ss-sweep 3 --ss-mode 2` | **24/24**, no diverging k |
| save state, 10 forms | `… --cases 1 --ss-sweep` over 10 forms | **10/10 PASS, 333 freeze points** |
| **save state, WIDTH (NEW)** | `… --ss-mode 5` over 8 forms | **PASS, 210 freeze points x 211 addresses** |
| ss map audit (ucore) | 211 symbols, each exactly twice | **PASS, 0 zero-width** |
| the MODEL, unmoved | `timed_gate.py --suite tests/v30/v0.1 --forms all` | **169,000/169,000, row-diffs 0** |
| `v0.1-w1` all forms | `… --suite-dir tests/v30/v0.1-w1 --waits 1` | **1200/1200** |
| `v0.1-w3` all forms | `… --suite-dir tests/v30/v0.1-w3 --waits 3` | **1200/1200** |
| `v0.1-w1 --forms EB` | `… --opcodes EB` | **200/200** |
| **`v0.1-w0evt`** | `… --waits 0` | **200/200** (was 167) |
| **`v0.1-w1evt`** | `… --waits 1` | **1200/1200** (was 1050) |
| **`v0.1-w2evt`** | `… --waits 2` | **200/200** (was 174) |
| **`v0.1-w3evt`** | `… --waits 3` | **1200/1200** (was 1063) |
| HLT delay sweeps | `s10-hltsweep-w{0,1}`, `s13-hltsweep-w{2,3}` | **88/97, 86/95, 35/46, 32/45** (pass 5's ratchet, held) |
| ROM disasm | `make -C sim test` | **PASS** (byte-exact vs `V20UC.TXT`) |
| PLA | `pla3_check.py` | **OK, 21 checks** |
| FSM core, untouched | `check_core.py --core fsm --opcodes 88,9D,INT.9D,INT.F3AA` | **1400/1400** |

G3 stated honestly, both numbers, as §29.2 requires: at w0 the sim carries no
registered residue against silicon, so the two coincide — **169,000 / 169,000
through the golden comparator**, and the same figure minus the (empty) w0
residue.  100 % is of everything the part does in this suite; there are no
forms unimplemented by design and no forms excluded.

### §42.5 THE U2 CLOSE

**Stage U2 is closed.  The ucore is cycle-exact on the whole scripted corpus at
every wait level the corpus carries, including all four `evt` cells.**

| pass | what it was | G3 after | recorded in |
|---|---|---|---|
| 1 | the EU skeleton, the module contract (F7), the first rungs | not yet censused | §15 |
| 2 | the store path, split loads, the four families named | 7,767/20,820 at 60 cases — RECONNAISSANCE, not a gate | §23, §24 |
| 3 | the families as ONE statement, seven renderings | **159,348** | §29 |
| 4 | the OPR hold (F31), the divider (F32), the QS=E guard (F33) | **164,787** | §34 |
| 5 | the interrupt and HALT rung, the 1BL strobe, the string tail | **168,886** | §39 |
| **6** | **the flag register's data edge, the REP abort's two anchors** | **169,000** | §42 |

Passes 1 and 2 have no whole-suite G3 figure because none was taken: the bar
then was the rung ladder (500/500 on a form's own tranche), and §23's 60-case
sweep is labelled reconnaissance in its own text.  It is not restated here as
a gate.

Findings **F1–F40** plus the three Codex reviews (§26 → C1–C3, §32, §36 →
C4–C5) are in this
document with their evidence and their falsifiers, and so are the ones that
moved no number (F22, F31's provable vacuity), the ones that were REVERTED
(§35.4's zero-cost experiment, the write-derived sreg shadow) and the ones that
came out NEGATIVE (the REP tap-depth scan — which pass 6 then showed was
negative *for a reason*, and the reason was the finding).

**What the method was, one more time, because it is the transferable part:**
every rung scored by a form-by-form diff of two whole-suite censuses on BOTH
the `full` and the `arch` column, never by the total; every fix traced to a
single model line or a single SPEC sentence with `uscope.py FORM IDX
--rowtrace` before it was written; every numeric bar pre-registered; and the
negative results kept in the ledger with the same weight as the positive ones.

### §42.6 HANDOFF — what U3 picks up

1. **The random-wait tranche gate is the campaign's victory condition and it is
   U3's.**  The ucore enters it with no wait-axis debt anywhere in the scripted
   corpus: `w1`/`w3` full, all four `evt` cells at 100 %, and the four HLT
   delay sweeps at pass 5's ratchet.
2. **The HLT delay sweeps (88/97, 86/95, 35/46, 32/45) are the one place the
   ucore is below the standing figure.**  `CLAUDE.md`'s quick reference records
   91/97, 92/95, 42/46 and 40/45 for `timed_gate.py` — i.e. for the MODEL — so
   the gap is ucore-vs-model, 3+6+7+8 = 24 cells, and it has never been
   triaged.  These are the ucore's own first measurement (§39.2) and are its
   ratchet, not the model's; closing the 24 is the obvious next census.
3. **`ss_lint --core ucore` still lints the FSM core**: the flag is accepted and
   ignored (`ss_lint.py` has no `--core`), so the ucore's map is audited only by
   the ad-hoc check in §42.4 and by mode 5.  Teaching `ss_lint` the ucore file
   set is a small job and it now has both a working SS1 sweep and a working
   width sweep to sit on top of.
4. **`ulockstep --golden` is now the cheap regression net**: it runs the whole
   347-form corpus at 5 cases each in a couple of minutes and needs no goldens
   to be right.  Its UNMASKED view (all columns, every row) is NOT a gate —
   idle-row `ad_addr`/`ps` are float retention and the two legs prime it
   differently by construction — but it exposes one real, non-retention
   difference: the `9D` T4 PS nibble, where **the RTL matches the silicon and
   the MODEL does not** (`sim/exec_impl.h` commits FLAGS at the `OPR -> FLAGS`
   row; F39 says the chip commits at the read's data edge).  Booked, not
   patched: `data_ps` reads `psw_` live, so teaching the model F39 would move a
   column both gates mask, and the model is at 169,000/169,000 today.  It is a
   ONE-LINE change to `wr_dst1`'s FLAGS arm plus the `F` wait's ordering, and
   it belongs to whoever next opens `biu_timed`.
5. **Residue booked, not patched, carried forward from §40.1**: the far-CALL /
   far-JMP `CS` shadow and the taken-branch recognition boundary
   (`post_flush`) are still documented-but-not-rendered — no golden reaches
   either.  `opr_free_p` / `set_oprfree` stay PROVABLY VACUOUS (F31).
6. **`SS_VERSION` did not move in pass 6.**  `rep_chain` rides bit 5 of the
   `SSA_E_IRQ_LATCH` word that was already in the map — no address added, no
   count changed — and a v1 stream restores it as 0, which is the value
   `begin_sequence()` writes anyway.  The next field that needs its own address
   is the one that bumps it.

---

# STAGE U3 — the wait/event axes, the whole-program ladder, and the platform

## §43 THE HLT-SWEEP TRIAGE — §42.6's ONE GAP, ANSWERED

§42.6 item 2 handed U3 the only place the ucore stood below the model: the four
HLT delay sweeps at **88/97, 86/95, 35/46, 32/45**, *"never triaged"*.  It is
now triaged, to **two mechanisms and nothing else** — the whole residue, all 34
cells, falls into exactly two first-divergence columns with no third and no
catch-all.

### §43.0 FIRST, THE RATCHET ITSELF WAS WRONG — AND IT WAS WRONG THE CHEAP WAY

§42.6 compared against `CLAUDE.md`'s quick reference (91/97, **92/95**, **42/46**,
**40/45**) and computed the gap as 3+6+7+8 = 24 cells.  **Those are the
pre-§26.7.6 figures.**  Re-measuring the model leg from scratch on this tree:

```
timed_gate.py --suite tests/v30/s10-hltsweep-w{0,1} --forms all --waits {0,1}
timed_gate.py --suite tests/v30/s13-hltsweep-w{2,3} --forms all --waits {2,3}
    ->  91/97,  95/95,  44/46,  42/45
```

which is what `ucsim_t_provenance.md` §26.11's own delta row says, and the quick
reference had simply never been updated when the S15 cleanup copied it forward.
The real gap is therefore **31 cells, not 24**.  Corrected in `CLAUDE.md` (with
the staleness recorded in place, not silently overwritten) and routed to the
model's own ledger as `ucsim_t_provenance.md` §27.2.

*Method note, because it is the transferable part:* the gap was computed from a
PER-CASE pass/fail list on both legs, not from the two totals.  The totals hide
that the two engines fail **different cases** — and in particular they hide
that the ucore was already beating the model on six of them.

### §43.1 THE CENSUS IS A BAND, AND THE BAND MOVES WITH THE WAIT LEVEL

Per-case, both legs, all four sweeps.  The sweep coordinate is the pin delay
`d` (`HLT.RES` idx = `d`; `HLT.INT` idx = `d - 1`).

| sweep | MODEL fails | uCORE fails (entry) |
|---|---|---|
| `w0` `HLT.INT` | idx 1,2,3,4 | idx 2,3,4,5,6 |
| `w0` `HLT.RES` | idx 2,3 | idx 2,3,5,6 |
| `w1` `HLT.INT` | — | idx 7,8,9,10,11 |
| `w1` `HLT.RES` | — | idx 7,9,10,11 |
| `w2` `HLT.INT` | idx 6,7 | idx 9,10,11,12,13,14 |
| `w2` `HLT.RES` | — | idx 9,11,12,13,14 |
| `w3` `HLT.INT` | idx 7,8,9 | idx 11,12,13,14,15,16,17 |
| `w3` `HLT.RES` | — | idx 11,13,...,17 |

The ucore's failures are a **contiguous band with exactly one hole**, and the
hole is `d*` — §23.3's threshold-1 delay coordinate (4 at w0, 8 at w1, and 10 /
12 at w2 / w3).  Below the band the wake beats the display cleanly; above it
the part is properly halted and `D = max(A + 4, H + 3)` is in its linear
`A + 4` regime.  The band is the threshold-1 neighbourhood, exactly where
§23.4 booked the model's own residue — the ucore's was simply WIDER.

### F41 — M21 WAS RENDERED FOR THE STATUS AND NOT FOR THE PADS

**Class: RTL BUG (a mechanism rendered half).  LANDED: +8 cells,
88/86/35/32 -> 90/88/37/34, and G3 unmoved at 169,000/169,000.**

M21, verbatim (§23.4): *"the HALT pseudo-cycle holds the bus only until its
STATUS RELEASE (20.5's index-1 eval).  From the release on, every clock is an
ordinary IDLE eval, exactly as when the bus is parked."*

`v30u_biu.sv` had that term on the status and nowhere else:

```
assign bs     = display ? r_cmt_bs : (r_run && !st_rel) ? r_cur_bs : BS_PASV;
wire   halt_pin = (display && r_cmt_halt) || (r_run && r_cur_halt);
```

`halt_pin` forces `ad_o = {4'h0, r_last_fetch_addr}` and explicitly gates
`ad_oe_addr` off (`&& !halt_pin`).  So a woken fetch whose DISPLAY landed
inside the HALT pseudo-cycle's own T2..T4 — which is the entire band — had its
address one-shot suppressed and published the HALT's retained
`last_fetch_addr` instead.  The status was right; the pads were a clock-count
behind a mechanism that had already been stated.

The fix is the SAME TERM, not a new one:

```
wire halt_pin = (display && r_cmt_halt) || (r_run && r_cur_halt && !st_rel);
```

MEASURED, `HLT.RES` w0 `idx 6`: golden row 7 `9ad8c`, RTL `0ad8c` before,
`9ad8c` after.  Every case whose woken display lands on a clock the comparator
can SEE the pads on (T4 / Ti / T1) closed — two per sweep, eight in all — and
no case anywhere else moved.

*Falsifier*: any HALT pseudo-cycle that drives its retained address past its own
status release, or any woken display inside one that does not publish.

### F42 — THE REMAINING `seg` FAMILY IS AN INSTRUMENT CEILING: THE uCORE IS RIGHT ON THE PINS AND THE TB CANNOT SEE IT

**Class: INSTRUMENT (comparator asymmetry).  23 of the 29 ucore-only cells.
NOT an RTL fault, and therefore NOT patched.**

After F41 the residue splits into exactly two first-divergence columns:

| family | cells | of which the model ALSO fails |
|---|---|---|
| `seg` (with `bus` / `data`) | 24 | 1 |
| `busstat` | 10 | 4 |

The `seg` family is every case whose woken display lands on a clock the TB's
T-state tracker calls **T2 or T3**.  `hdl/tb/tb_v30_core.sv` does not read the
core's pins directly: it composes the observed AD from a **protocol-inferred
drive mask** with float retention —

```
com_phase    = bs_active && (tb_t == ST_T4 || tb_t == ST_TI);
drive_hi_a   = (com_phase && BS != PASV) || (tb_t == ST_T1 && lat_type != PASV);
cycle_live   = tb_t != ST_TI && lat_type != BS_PASV && lat_type != 3'b011;  // 011 = HALT
core_ps_drive= cycle_live && (tb_t inside {T2,T3,TW,T4});
eff_hi       = (drive_hi_a || core_ps_drive) ? AD[19:16] : hold[19:16];
```

`lat_type` is the LATCHED status of the cycle in progress, and for a HALT
pseudo-cycle that is `HALT` — which `cycle_live` excludes — so for the whole
duration of a HALT-typed cycle the composer substitutes `hold` for the pads at
T2/T3 **whatever the core drives**.  The GOLDEN has no such mask: it is a raw
silicon pin capture.  And the MODEL has no such mask either: `sim/rows.cpp`
writes `r.ad_addr` directly.  The mask exists on exactly one of the three legs.

**PROVED, not inferred.**  A `+padtrace` line was added to `v30u_biu.sv`
(guarded `ifndef SYNTHESIS`, gated on the plusarg, one row per clock naming the
three pad enables and the value on `ad_o` — the pad-drive counterpart of the
`u` line's eval terms).  It says the core is right:

```
HLT.RES w0 idx 5, the divergent row (TB tstate T3):
  P 13 ad=9ad8c oe_addr=1 oe_ps=0 oe_data=0 disp=1 strel=1 haltpin=0 curhalt=1 bs=4
  golden row 6:  9ad8c  SS  ad8c  CODE T3      <- IDENTICAL
  TB `r` row 6:  2ad8a  CS  ad8a  CODE T3      <- the composer's `hold`

HLT.RES w2 idx 11, the divergent row (TB tstate T3):
  P 19 ad=9ad8c oe_addr=1 oe_ps=0 oe_data=0 disp=1 strel=1 haltpin=0 curhalt=1 bs=4
  golden row 9:  9ad8c  SS  ad8c  CODE T3      <- IDENTICAL
```

Two forms, two wait levels: the ucore drives the golden's address, with the
address enable asserted, on the golden's own clock, and the comparator reports
the retained value.  **The cells are unreachable through this TB, not wrong in
this core.**

GOVERNANCE.  This is risk #4 of the campaign plan (*"multiplexed-pad float →
ledger open item 1, not patches"*) arriving from the instrument side, and it is
booked, not fixed, for a stated reason: `tb_v30_core.sv` is SHARED with the
frozen FSM core and with every standing RTL ratchet in `CLAUDE.md`.  Re-latching
`lat_type` at a display so the pads become visible after a status release is a
one-term change with a plausible shape, but it would move the FSM core's scores
too, so it needs its own pre-registered before/after on both cores and it is
not U3's to make on the way past.  **Recorded as U3 open item 1.**

*Falsifier*: a `+padtrace` row inside the band where `oe_addr` is low, or where
`ad_o` differs from the golden's captured address at the display clock.

### F43 — M20's CANCELLATION IS ONE EDGE LATE, BECAUSE THE ucore's HALT DISPLAY IS REGISTERED

**Class: RTL, DIAGNOSED AND BOOKED — 6 of the 29 ucore-only cells, exactly one
per form per wait level at w1/w2/w3.  Not fitted, not patched.**

M20 (§23.4): *"`halt_pending_` is the HLT row's write WAITING for the status
register.  A wake decided before that write happens takes the part out of HALT
and the write never happens."*  Threshold 1: **the HALT status is driven iff
`A - H >= -2`**, i.e. *the HALT displays unless the wake is already visible to
the microcode on or before the display clock.*

MEASURED, `HLT.RES` w1 `idx 7`: the golden never drives HALT at all — rows 5
and 6 are `PASV`, `PASV`, then the woken `CODE` — and the ucore drives `HALT`
at row 5 and stands its T1 at row 6.  The wake beat the display on silicon and
did not in the ucore, by ONE CLOCK.

The reason is the register boundary, and it is F35's seam one step further on:

* the MODEL's display block sits at the **top of `tick(c)`** and both decides
  and displays on clock `c` (`if (halt_pending_ && !run_ && !cmt_valid_ ...)
  { cmt_ = halt_acc_; }`), so `unhalt()` called before `tick(c)` cancels it;
* the ucore's display is **REGISTERED**: the same test runs at the end of the
  edge ending clock `c-1`, sets `cmt_*`, and `display = r_cmt_valid && !ann_kill`
  shows it at `c`.  `eu_unhalt` clears `halt_pending` in block (a) at the top of
  edge `c` — one edge too late to un-decide a display already committed.

So the cancellation must be evaluated against the display's **DECISION EDGE**,
not against its display clock.  That is F40's shape exactly — *"both taps are
`edge - 4`; what changed is the REFERENCE EDGE"* — and it is one rendering
decision, not a search: the wake itself must stay at `D = A + 3` (it is at
100 % on all four `evt` cells and on the whole out-of-band sweep), so the
cancellation needs its own one-clock-earlier view of the same pin pipeline
rather than a moved tap.

**NOT LANDED, for a stated reason.**  It touches the eval instant — the spine of
the whole BIU — while `check_core --core ucore --opcodes all --cases 0` is at
169,000/169,000 and four whole-program ladders were being scored against this
binary.  It is handed to U4 with its mechanism named and its falsifier written,
which is the same way §40 handed pass 6 its two forms.  **Recorded as U3 open
item 2.**

*Falsifier*: any sweep cell where the golden drives the HALT status although the
wake was visible to the microcode on or before the display's DECISION edge; or
any cell that needs the cancellation at the display clock rather than one edge
earlier.

### §43.2 THE SCOREBOARD, AND THE SIX CELLS WHERE THE ucore BEATS THE MODEL

| sweep | model | ucore, entry | ucore, after F41 | delta |
|---|---|---|---|---|
| `s10-hltsweep-w0` | 91/97 | 88/97 | **90/97** | −1 |
| `s10-hltsweep-w1` | 95/95 | 86/95 | **88/95** | −7 |
| `s13-hltsweep-w2` | 44/46 | 35/46 | **37/46** | −7 |
| `s13-hltsweep-w3` | 42/45 | 32/45 | **34/45** | −8 |
| **total** | **272/283** | 241/283 | **249/283** | **−23** |

Read case by case rather than by the totals, the −23 is **29 cells the ucore
misses that the model does not, minus SIX the model misses that the ucore does
not**: `s10-hltsweep-w0` `HLT.INT` idx 1, `s13-hltsweep-w2` `HLT.INT` idx 6, 7
and `s13-hltsweep-w3` `HLT.INT` idx 7, 8, 9.  All six carry the model's
`bus`/`data`/`ube` signature — §26.7.7's withdrawn-announcement pad retention —
and the ucore reproduces the golden on all of them.

Per the campaign's governance that is a **ucore-BEATS-sim event**, governed on
F39's precedent: the sweeps are scored against SILICON captures, the model
carries a registered residue there that it does not claim to close, and the
ucore's rendering is the one the capture agrees with.  It is a MEASUREMENT
routed to the model's ledger (`ucsim_t_provenance.md` §27.2), not a claim that
the model is broken, and nothing in `sim/` was changed for it.

And the −23 that remains is now **23 instrument-ceiling cells (F42) + 6 cells of
one named, diagnosed rendering (F43)** — with no unexplained residue at all,
which is the state §23.4 asked for and did not have.
