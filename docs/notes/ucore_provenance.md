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
that the two engines fail **different cases**, and which ones.

**AND A NUMBERING TRAP, RECORDED BECAUSE IT NEARLY PUT A FALSE FINDING IN THIS
LEDGER.**  A sweep case's **`idx` FIELD IS THE PIN DELAY `d`**, for both forms
and all four sweeps — that is what `check_core --details` and `uscope.py`
report.  It is *not* the case's position in the JSON array: `HLT.RES`'s sweeps
start at `d = 0` so the two coincide, and `HLT.INT`'s start at `d = 1/3/4/5` so
they do not.  A first draft of §43.2 compared the model's failures by ARRAY
POSITION against the ucore's by `idx`, and reported six cells where the ucore
"beat" the model.  **There are none** — the artefact was a one-to-five-case
shift on `HLT.INT` alone.  Caught by re-deriving both lists in one script in
one numbering, which is what §43.3 then did for every cell.  *Any per-case
claim in this campaign must state which numbering it is in.*

### §43.1 THE CENSUS IS A BAND, AND THE BAND MOVES WITH THE WAIT LEVEL

Per-case, both legs, all four sweeps.  **All indices below are the case `idx`
field = the pin delay `d`** (see the trap above).

| sweep | MODEL fails | uCORE fails (entry) | uCORE fails (after F41) |
|---|---|---|---|
| `w0` `HLT.INT` | 2,3,4,5 | 2,3,4,5,6 | 2,3,4,5 |
| `w0` `HLT.RES` | 2,3 | 2,3,5,6 | 2,3,5 |
| `w1` `HLT.INT` | — | 7,8,9,10,11 | 7,8,9,10 |
| `w1` `HLT.RES` | — | 7,9,10,11 | 7,9,10 |
| `w2` `HLT.INT` | 10,11 | 9,10,11,12,13,14 | 9,10,11,12,13 |
| `w2` `HLT.RES` | — | 9,11,12,13,14 | 9,11,12,13 |
| `w3` `HLT.INT` | 12,13,14 | 11,...,17 | 11,12,13,14,15,16 |
| `w3` `HLT.RES` | — | 11,13,...,17 | 11,13,14,15,16 |

**The model's 11 failing cells are a strict SUBSET of the ucore's 34.**  There
is no cell the model fails and the ucore passes, and no cell the ucore fails
for a reason the model does not also have available to it.

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

So, in ONE sentence — and the Codex review (§45, C7) is the reason it is this
sentence and not a longer one: **the HALT-display decision must test the wake
condition visible on its OWN decision edge.**  Not "a one-clock-earlier view of
the pipeline", which was the first draft's wording and which C7 correctly called
out as *"equivalent but risks suggesting duplicated state"* — nothing new is
stored.  The display's existing decision test (`halt_pending && !run &&
!cmt_valid && !set_noeval`) simply has to include the wake, in the same block
that already reads `halt_pending`.

That is F40's shape exactly — *"both taps are `edge - 4`; what changed is the
REFERENCE EDGE"* — and it is one rendering decision, not a search.  The wake
ITSELF must not move: `D = A + 3` is at 100 % on all four `evt` cells and on the
whole out-of-band sweep, so this is a term added to the display's decision, not
a re-tapped pin.

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

### §43.2 THE SCOREBOARD

| sweep | model | ucore, entry | ucore, after F41 | delta |
|---|---|---|---|---|
| `s10-hltsweep-w0` | 91/97 | 88/97 | **90/97** | −1 |
| `s10-hltsweep-w1` | 95/95 | 86/95 | **88/95** | −7 |
| `s13-hltsweep-w2` | 44/46 | 35/46 | **37/46** | −7 |
| `s13-hltsweep-w3` | 42/45 | 32/45 | **34/45** | −8 |
| **total** | **272/283** | 241/283 | **249/283** | **−23** |

Read case by case in ONE numbering (§43.0's trap), the −23 is exactly **23
cells the ucore misses that the model does not, and ZERO the model misses that
the ucore does not**.  The model's 11 failures are a strict subset.  There is
no ucore-beats-sim event on these sweeps, and the first draft of this section
claimed six; the claim is RETRACTED, with the artefact that produced it kept in
§43.0 rather than deleted.

The 23 split by first-divergence column with no remainder:

| | cells | of which ucore-only | mechanism |
|---|---|---|---|
| `seg` (+`bus`/`data`) | 24 | **17** | F42, the instrument ceiling |
| `busstat` | 10 | **6** | F43, M20's cancellation edge |
| | 34 | 23 | |

So the ucore's whole remaining deficit on the HLT sweeps is **17 cells that no
comparator on this TB can score + 6 cells of one named, diagnosed rendering**,
with no unexplained residue at all — which is the state §23.4 asked for and did
not have.

### §43.3 F42 MEASURED ON EVERY CELL, NOT TWO — CODEX C6's FALSIFIER, RUN

The first draft of F42 rested on two `+padtrace` probes and a structural
argument about `cycle_live`.  The Codex review (§45, C6) accepted the reasoning
but named the gap: *"the 23-cell generalization is supported structurally rather
than solely by two probes"*, and specified the falsifying measurement — *"on
any claimed F42 row, sample the DUT's raw AD pins at the comparator's sampling
edge, bypassing `eff_hi`/`eff_lo`, and align that sample with the golden row; a
raw mismatch despite the claimed display/enable falsifies F42."*

**It was run on all of them.**  Every `seg`-family cell in all four sweeps, the
pad-drive stream aligned to the raw `r` stream by its `bs` sequence (unique
offset in every case — 0 ambiguous alignments), the divergent window row mapped
back through `build_rows_sim`'s own `i0`:

```
seg cells: 24   core drives the GOLDEN address with oe_addr asserted: 24
                ambiguous alignment: 0
```

24 of 24, no exceptions — `HLT.INT` driving `57cb4` where the composer reports
`67cb2`, `HLT.RES` driving `9ad8c` where it reports `2ad8a`, with `disp=1` and
`oe_addr=1` on every one.  F42 is now MEASURED on its whole population and the
falsifier did not fire.  (It also swept in the seven cells the retracted
"ucore beats the model" claim had been about: they are `seg` cells where BOTH
engines miss the golden — the model for §26.7.7's pad retention, the ucore for
the composer — and neither is a win.)

### F44 — THE MICROCODE ROM FAILS TO LOAD **SILENTLY**, AND THE RUN LOOKS NORMAL

**Class: VACUITY RISK (build/instrument).  Moves no number today; it is
recorded because U4 is the stage that changes `HEXDIR`.**

`v30u_ucrom.sv` loads both tables with `$readmemh({HEXDIR, ...})`, where

```
parameter string HEXDIR = "hdl/rtl/ucore/"   // sim runs from the repo ROOT;
                                             // a synthesis project overrides it
```

The parameter and its override are by design and are documented in the module.
What is NOT safe is the failure mode.  Run the same frozen binary from any other
working directory:

```
%Warning: hdl/rtl/ucore/ucdecode.hex:0: $readmem file not found
%Warning: hdl/rtl/ucore/ucrom.hex:0: $readmem file not found
DONE 1 cases
    -> 22 `r` rows emitted, exit as normal
```

Two **warnings**, not errors; the core comes up with an all-zero microcode ROM
and an all-zero decode table; the TB still reports `DONE`, still exits 0, and
still produces a full, plausible-looking row stream.  Any harness that scores a
DIGEST, a COUNT, or a self-consistency property rather than a golden would grade
that as a PASS.  This is the vacuous-gate pattern the campaign has already been
bitten by twice (`check_enter_nesting.py`'s silently-ignored flags; the
compiled-out assertion in `check_core.py`'s `build()` comment).

It was found by the U3 ladder work, not by a gate: `sw/tb_bootrun.py` forces
`cwd=ROOT` for exactly this reason.  Every U3 number in §44 was taken with the
tables loaded — `check_ucore_tables.py` is 9988/9988 on the same tree and the
G3 census is 169,000/169,000, neither of which is reachable with a zero ROM.

**THE GUARD IS ONE LINE AND IT IS U4's**, because U4 is where `HEXDIR` is
overridden by a Quartus project and a typo would be invisible: assert a known
ROM word after load (`ucrom[0]`, or any row `check_ucore_tables.py` already
pins) and `$fatal` if it is zero.  A ROM that did not load is not a core.

*Falsifier*: a `$readmemh` failure path that already errors rather than warns,
or a build in which an all-zero ROM cannot produce a completing run.

### F45 — `--ss-mode 4`'s SEED **IS** THE BIT INDEX, AND A SMALL-SEED SWEEP READS AS A BLIND GATE

**Class: INSTRUMENT (interpretation).  Found by running the ucore's first
bit-flip negative control; the instrument is sound and its GUIDANCE was not.**

Save-state mode 4 is the G5' negative control: flip ONE bit of the frozen
stream, restore, resume, and require that a bit mapping to LIVE state perturbs
the continuation.  A gate whose flips never diverge is blind, so this is the
control that proves `--ss-sweep` is not passing by construction.

The ucore had never run it.  Run with seeds 0..25 it reports, 26 times:

```
89 SS4 idx 0: swept=3 perturbed=0 (0%) inert(unexercised)
```

which is exactly what a blind gate looks like.  **It is not blind; the seeds
were.**  `tb_v30_core.sv`:

```
bit_idx = ss_scramble_seed % (SS_COUNT*16);
if (bit_idx < 16) bit_idx = bit_idx + 16;   // skip the tag word
wrd = bit_idx / 16;  bpos = bit_idx % 16;
```

The seed is not a PRNG seed — **it is the bit index itself.**  With
`SS_COUNT` = 211 the space is 3,376 bits, and seeds 0..25 all land in **word 1
and only word 1**.  Consecutive seeds walk consecutive bits of one SS address;
to walk ADDRESSES the seed must step by 16.

Stepping by 16 across the map (`seed = 16*word + 3`, one probe per word, form
`89`, 3 freeze points):

| form | words probed | SENSITIVE | inert |
|---|---|---|---|
| `89` (3 freeze points) | 21 (words 2..205) | **3** (40, 50, 100) | 18 |
| `8B` (6 freeze points) | 8 (words 41..105) | **5** (41, 49, 99, 101, 105) | 3 |

`8B`'s words 99, 101 and 105 perturb at **100 %** — every freeze point — and 41
and 49 at 67 %.  Two forms, thirteen sensitive words, up to 6 of 6 freeze
points each.

**So mode 4 IS live on the ucore** — flips reach live flops and perturb the
continuation — and the control is discharged.

Two corrections to the instrument's own guidance, which is a comment in
`tb_v30_core.sv` and is what a future session will read:

1. *"Run many seeds"* is not enough and is actively misleading: many
   CONSECUTIVE seeds probe one address.  The sweep must step by 16.
2. *"most flips must diverge"* is too strong.  Only 3 of 21 probed words moved,
   and that is expected rather than alarming: at a freeze point three clocks
   into a `MOV`, most of a 211-address map is genuinely not live, and
   `ss_field_width` (§42.2) already establishes that many stream bits are above
   their field's width and are don't-cares by construction.  The honest bar is
   **"some must diverge, and which ones is form- and freeze-point-dependent"** —
   a per-word SENSITIVE/inert census, not a fraction.

Neither correction is made to the TB here (it is frozen for U3 scoring and
shared with the FSM core); both are booked as **U3 open item 3**, together with
the observation that the same seed arithmetic applies to the FSM core's mode-4
runs and any historical "0% perturbed" reading taken with small seeds should be
re-read before it is quoted.

*Falsifier*: a mode-4 seed below 16*`SS_COUNT` that lands outside
`word = seed/16`, or a form/freeze point at which no word in the map is
sensitive.

## §44 THE U3 GATE LADDER

Every number below was taken on **one binary**, rebuilt clean from the
committed tree at the end of the stage
(`sha256 b76b7734a5ecbba36c99e8bf7e9a82c9b3928d1d5dabf19ac7d22d21bf712436`).
That matters: the binary was rebuilt twice mid-session by concurrent scoring,
so the whole ladder was re-run afterwards rather than assembled from runs taken
at different times.  The forced rebuild reproduced the same sha bit for bit.

### §44.1 THE SCRIPTED CORPUS AND THE WHOLE-PROGRAM LADDER

| gate | command | sim / standing | **ucore** |
|---|---|---|---|
| **G3** | `check_core --core ucore --opcodes all --cases 0` | 169,000 | **169,000 / 169,000** |
| `v0.1-w1` | `--suite-dir v0.1-w1 --waits 1` | 1,200 | **1,200/1,200** |
| `v0.1-w3` | `--suite-dir v0.1-w3 --waits 3` | 1,200 | **1,200/1,200** |
| `v0.1-w1 --opcodes EB` | | 200 | **200/200** |
| `v0.1-w0evt` / `w1evt` / `w2evt` / `w3evt` | | 200 / 1,200 / 200 / 1,200 | **200 / 1,200 / 200 / 1,200** |
| **`v0.1-w1evt-biased`** (ucore FIRST) | `--waits 1` | 1,200 | **1,200/1,200** |
| boot march | `check_boot --core ucore 220` | 220 | **220/220 MATCHES** |
| **boot march, deeper** (ucore FIRST) | `check_boot --core ucore 400` | — | **400/400 MATCHES** |
| G0 tables | `check_ucore_tables.py` | 9,988 | **9,988/9,988 PASS** |
| U1 lockstep | `ulockstep --suite --waits 0,1,2,3` | — | **ALL SCENARIOS LOCKSTEP** |
| U2 lockstep | `ulockstep --golden all --cases 5` | — | **1,735/1,735** |
| **U3 lockstep, 10x deeper** | `ulockstep --golden all --cases 50` | — | **17,350/17,350 ALL LOCKSTEP** |
| **`timed_wvec_gate --core ucore`** | 88-program silicon freeze (T2b P2) | 88/88, +0.0 % | **88/88 digest, 88/88 count, 16,048 vs 16,048, +0.0 %** |
| **`timed_enter_replay --core ucore`** | 7 wait slices | 154/154 x5 | **154/154 x5** |
| **`timed_ins_replay --core ucore --raw`** | case250 INS | rails 1,312 / vs-chip 2,624 | **1,312/1,312 and 2,624/2,624** |
| HLT sweeps | `s10-w{0,1}`, `s13-w{2,3}` | 91/97, 95/95, 44/46, 42/45 | **90/97, 88/95, 37/46, 34/45** (§43) |
| ROM disasm | `make -C sim test` | PASS | PASS |
| PLA | `pla3_check.py` | 21 checks | OK |
| the MODEL, unmoved | `timed_gate --suite v0.1 --forms all` | 169,000 | 169,000, row-diffs 0 |
| FSM core, untouched | `check_core --core fsm --opcodes 88,9D,INT.9D,INT.F3AA` | 1,400 | **1,400/1,400** |

**Eleven of thirteen ladder rows land ON the sim's number.** The two that do not
are the HLT sweeps (§43: 17 cells this TB cannot score + 6 of one diagnosed
rendering) — itemised and governed, per the U3 gate.

Three of these are **new legs, not new runs**: `timed_wvec_gate`,
`timed_enter_replay` and `timed_ins_replay` drove the C++ model only.  Each now
takes `--core {sim,ucore,...}` as an **engine swap** — the digest, the
comparison window, the column policy and the scoring are shared,
un-parameterised code, and **each sim leg was re-measured after the refactor and
is unchanged.**  A refactor that moves the sim's number is a bug in the leg, and
that check was run before any ucore number was taken.  The shared `+bootimg`
driver is `sw/tb_bootrun.py`.

**The wvec cross-check is worth its own line.**  The same gate through the
FROZEN FSM core scores **71/88** — 22/22 at `ws0:wmax0` and 17 misses spread
over the three waited configs, with the access COUNT matching the chip in all
88 cells.  The FSM's deficit is therefore pure CADENCE on the wait axis, which
is the axis this project ranks first.  On the silicon wvec freeze the ucore
strictly dominates the frozen core, **88 vs 71**.

### §44.2 THE FUZZ BANK — WHERE THE ucore BEATS THE MODEL, AND ONE RIG FINDING

`sw/timed_fuzz.py` gained the same `--core` engine leg (regeneration + sha gate,
`ucsim_fuzz.window_of`, `fuzz_classify.diff_rows`, `excuse()` and the report
format all shared).  The bar was **pre-registered before any ucore run**
(`~/.cache/ucsimt-tmp/u3-fuzz/PREREG.txt`): the ucore must reach ≥ the sim on
each population, with IDENTICAL denominators.  Denominators held in every run
(2,710 scored / 532 `OPEN_BUS`; 188 / 28), which is the harness-integrity guard,
not a result.

| population | sim | **ucore** | sim `reg8` | **ucore `reg8`** |
|---|---|---|---|---|
| REGISTERED | 1,272/1,702 | **1,394/1,702  (+122)** | 1,272/1,702 | **1,394/1,702** |
| EVT | 709/1,008 | 184/1,008 | 780/1,008 | **866/1,008  (+86)** |
| COMBINED | 1,981/2,710 | 1,578/2,710 | 2,052/2,710 | **2,260/2,710  (+208)** |
| b2 victory tranche | 154/188 | **168/188  (+14)** | — | — |

*(All eight cells re-run independently after the stage's work was reported; the
sim legs reproduce the standing ledger byte for byte.)*

**THE ucore BEATS THE MODEL ON THE REGISTERED POPULATION AND ON THE VICTORY
TRANCHE.**  205 REG seeds and 18 tranche seeds where the model diverges and the
ucore is cycle-exact against the socket capture; the model's first-divergence
families on them are `qs` (145), `bs` (37) and `data` (23) — the QS pin's exact
fetch/execute pop clock and the T4/Ti bus-status arbitration.  Governed exactly
as F39 and §42.1 govern this class: the gate is the SILICON capture, the model
carries a registered residue there that it does not claim to close, and nothing
in `sim/` was changed.  For scale, the same bank through the FROZEN FSM core
scores **18/1,702** on REGISTERED.

**V5 IS REPRODUCED AS REGISTERED, NOT RE-OPENED.**  The tranche's 168/188 is a
PARITY CHECK: V0 (0 hard failures) ✅, V1 89.4 % ≥ 55.6 % ✅, V2 median prefix
fraction 1.000 ✅, V3 100 % named families ✅, V4 wrand-vs-fixed 1.3 points ✅,
and **V5 remains a FAILURE** (168/188 ≠ 188/188).  The registered record stands.

### F46 — THE RIG'S `evt_hold` REGISTER IS 8 BITS, AND 760 EVT SEEDS WERE BANKED ASKING FOR 300

**Class: RIG / BANK INTEGRITY.  It is why the EVT column above needs two
readings, and it is not the ucore's.**

```
hps_axi_slave.sv:275   evt_hold <= wdata[23:16]      // 8 bits
nec_bus.sv:73          input [7:0] evt_hold
```

**760 of the 1,008 EVT seeds bank `hold = 300`.**  The socket was therefore held
for `300 & 0xFF` = **44** clocks, not 300.  The MODEL cannot notice: under
`--evt-replay` it is HANDED the capture's acknowledge positions
(`sim/pin_replay.h`, §42.1).  The ucore PREDICTS them from the directive, so
given a 300-clock INT level it re-enters the handler 2-4 times where the chip
entered once — **545 of 545 INTR trails diverge as "extra INTA pairs", and 540
of those 545 put the FIRST acknowledge on exactly the chip's clock.**  The
recognition is right; the directive was never physically applied.

Feeding both legs the hold the rig could actually apply (`--rig-hold reg8`, a
DRIVER property in §42.2's class) moves the sim's EVT number by **+71** as well
as the ucore's by +682 — so it is **OFF BY DEFAULT** and is NOT applied to the
registered table here.  Re-registering the EVT ratchet against a corrected hold
is a decision for the campaign owner, not a side effect of an RTL stage.
Recorded as **U3 open item 4**, with the note that `check_seq.run_tb` and
`fuzz_campaign.capture_tb` carry the same unmasked hold and are the likely
reason this population was promoted into the banks at all.

*Falsifier*: a capture in the EVT population whose acknowledge pattern is
consistent with a hold longer than 255 clocks.

### F47 — 83 SEEDS: THE RIGHT CYCLE, THE RIGHT ADDRESS, THE WRONG WORD

**Class: RTL, NAMED AND NOT FITTED.  83 REGISTERED seeds + 4 tranche seeds.**

The ucore's whole remaining REG deficit is one shape: a **write cycle it
addresses and times exactly right, carrying the wrong DATA WORD.**  73 of 83
sit inside a `MEMW` (59) or `IOW` (14) cycle; 42 of 83 have a total diff of ≤ 6
rows — one wrong word and nothing else.  `t`, `bs`, `ube`, the address and the
wait pattern all match the socket.

It is not a memory-map artefact: re-running all 83 against the alternative TB
memory model (16×-replicated flat image instead of `+mirror=1`) flips **0 of
83** and costs 1 of 300 controls, so `+mirror=1` stands.  The owning opcode is
diffuse (`FF`/mod3, `F3`, `6A`, `A2`/`A3`, `8F`, `65`, `62`) — **an EU value
path the 169,000-case golden suite does not reach**, which is exactly what a
whole-program bank is for.  Not fitted, not patched; handed to U4 as the first
place to look.

### F48 — TWO EU BOUND ASSERTIONS **FIRE** ON SIX BANKED SEEDS — RISK #2, REALISED

**Class: RTL.  The campaign plan's risk #2 was "absolute-clock longs → bounded
relative counters with SYNTHESIS bound assertions (`rd_done_q` depth ≤ 2 to
prove)".  The proof obligation is NOT discharged: the bound is violated by real
programs.**

Six seeds hard-abort the ucore — `mc1/2123`, `mc1/3613`, `mc2/2244`,
`t30-raw/440`, `t30-raw/446`, `t30-raw/829` — on two assertions:

```
v30u_eu.sv:1594   completed-read store overflow (rdq_n = 2)     x3
v30u_eu.sv:1596   rd_done_cnt saturated                          x3
```

Three of the six are at FIXED w0/w1/w3, so this is not a random-wait-only
corner.  The assertions did their job — this is the bound assertion catching a
real bound violation, which is the outcome the plan asked them to be able to
produce.  Reported, not patched.

**And the harness had been HIDING them.**  `timed_fuzz`'s old `SIM_ERROR` path
returned BEFORE the population was assigned, so a crashing engine silently
shrank its own denominator (1,702 → 1,698).  Fixed: in-population seeds stay in
and score as total divergences, the count prints on its own `ENGINE ABORTS`
line, and it forces a non-zero exit.  The sim leg had zero aborts, so no
standing number moves.  *A gate whose denominator follows the engine is not a
gate.*

### §44.3 THE PLATFORM

| gate | result |
|---|---|
| `ss_lint.py --core fsm` | **PASS, byte-identical to baseline** (82x2 BIU + 120x2 EU + tag = 203; census 181 flops, 0 unmapped), `rc=0` |
| **`ss_lint.py --core ucore`** (NEW) | map audit **PASS** — 96x2 BIU + 115x2 EU + tag = 212, **211 symbols each exactly twice, 0 zero-width**, reproducing §42.4's ad-hoc count independently — and flop census **FAIL**, `rc=1` (see F49) |
| flop census, in the map header | **223 architectural flops** (BIU 83, EU 140), 194 mapped, 24 whitelisted, **5 UNMAPPED** |
| `+ce_div` hold-check, w0 | 9 forms x 7 divisors x 100 cases = **63/63 cells, 100/100 rows, 0 violations** |
| `+ce_div` hold-check, wait axis | 5 forms x 3 divisors x `w1`/`w3` = **30/30 cells, 0 violations** (9,300 case-runs in total) |
| save state, scramble (mode 1) | **80/80**, every freeze point PASS |
| save state, idempotence (mode 2) | **24/24**, no diverging k |
| save state, 10 forms | **10/10 PASS**, 154 freeze points |
| save state, width (mode 5) | **PASS**, 126 freeze points x 211 addresses |
| **save state under RANDOM waits** (ucore FIRST) | `--ss-wrand --ss-wmax 3` seed `ACE1` **10/10**; `--ss-wmax 7` seed `5678` **10/10** |
| **bit-flip negative control** (mode 4, ucore FIRST) | **SENSITIVE** — 13 sensitive words over two forms, three at 100 % (see F45) |
| SYNTHESIS assertions | **13 runtime contract checks enumerated** (not 3); 8 are true SVAs, **6 of 8 LIVE-FIRED inside the frozen binary** |

**THE ASSERTION AUDIT, AND WHY THE BRIEF'S "THREE" WAS WRONG.**  `grep assert
hdl/rtl/ucore/*.sv` misses the `.svh` includes — the same include-vacuity trap
`ss_lint` had.  There are 13 checks: 8 `assert … else $error` and 5 BARE
`$error`.  Six of the eight were fired IN THE FROZEN BINARY, with no RTL
touched, by using `--ss-mode 4`'s targeted bit flip to drive mapped state out of
bounds — that is proof of arming, not inference.  The remaining two
(`v30u_biu.sv:1500` announcement-age saturated, `v30u_eu.sv:1596`
`rd_done_cnt`) are proved COMPILED-IN by the elaborated failure string with
resolved `file:line` in the binary, backed by a build-flag negative control (the
string is present with `--assert`, absent without).  Stated honestly: for those
two the claim is **"present in the model"**, not "observed to fire".

### F49 — FIVE ARCHITECTURAL FLOPS ARE ABSENT FROM THE ucore SAVE-STATE MAP

**Class: RTL / SAVE-STATE.  The census's whole reason for existing, and it found
one on its first run.**

```
v30u_biu.sv:306  r_cur_odd     v30u_biu.sv:324  r_cmt_odd
v30u_biu.sv:374  r_rq_odd[0:1] v30u_biu.sv:367  r_rd_land
v30u_eu.sv :274  rst_ctr
```

Verified independently of the linter by direct inspection: each is a `reg`
assigned with `<=` on the clock edge and read across it, and **none has an
`SSA_*` arm**.  `r_rd_land` drives `eu_rdata_n` — **a completed read's data**.
The three `*_odd` flops carry the split access's ODD BASE, which decides the
byte swap at `v30u_biu.sv:1329`.  `rst_ctr` is F25's four-clock reset march.

**THIS IS THE BLIND SPOT §42.4 AND MODE 5 COULD NOT SEE, AND IT IS STRUCTURAL.**
"211 symbols, each exactly twice" and the width sweep both only visit addresses
that EXIST; the SS1 scramble only scrambles what it can address.  No instrument
that walks the map can find a flop nobody put in the map.  That is precisely why
the census runs the other way — from the RTL to the map — and it is why the
ucore leg was worth building rather than trusting §42.4's ad-hoc count.

Fixing it adds addresses and therefore **bumps `SS_VERSION`**, which is why it
is not done here (the RTL is frozen for U3 scoring and five ladder suites were
being scored against this binary).  **U3 open item 5**, and it is U4's first
platform job — a restore that loses a completed read's data is a real defect,
not a bookkeeping one.

*Falsifier*: a demonstration that any of the five cannot hold a value across a
freeze point on any reachable path.

### F50 — THREE HYGIENE ITEMS THE CENSUS TURNED UP ON THE WAY

1. **`ending` (`v30u_eu.sv:304`) is DEAD RTL** — assigned at reset and at
   `step.svh:398/641/682`, **read nowhere**; F22 replaced it with `poste`.
   Verilator drops it from the generated model.  Confirmed by direct grep.
2. **Two un-converted BARE `$error` remain in `v30u_eu_poste.svh:72,75`** (plus
   three in `v30_core.sv:129,130,135`).  `v30u_biu.sv:1476-1484` documents this
   exact form as having taken `--ss-sweep` DOWN before pass 5 converted the
   BIU's, because **`$assertoff(0)` governs assertions and not ordinary
   statements**, so these are not quiesced during the scramble window.  Latent,
   not active: 10 mode-1 seeds x 4 forms, 0 fires.
3. **The ucore's CE-hold probe has NO EU coverage.**  `tb_v30_core.sv:1204`
   watches `{r_ts, r_q_cnt, r_fetch_ptr[7:0]}` — BIU only — where the FSM probe
   at line 1197 includes `u_eu.state` and `u_eu.div_cnt`.  So §44.3's 93 clean
   `+ce_div` cells are **BIU-state evidence**; the EU-side evidence is the
   100/100 golden row match, not `CE_HOLD_VIOL`.  Reported, not patched (TB
   frozen).  **U3 open item 6.**

The 24 whitelist entries (`sw/ss_flop_whitelist_ucore.txt`) are a fourth item of
the same kind and are honest about it: they exist ONLY because the EU's
block-local working values are declared at module scope.  Declaring them inside
the `always` block would make them automatic and delete both them and the
whitelist file.  Each entry carries a hand-checked dominating write; that check
is lexical dominance, not a dataflow proof.

## §45 THE FOURTH CODEX REVIEW, THE U3 CLOSE, AND THE U4 HANDOFF

### §45.1 THE CODEX REVIEW (2026-08-03, thread `019fc8ba` resumed a fourth time)

Scoped to three asks, with the file set named exactly (§43; `ucsim_t` §23.3/§23.4;
`v30u_biu.sv`'s PIN DRIVE block; `tb_v30_core.sv`'s composed-bus block) — the
wedge lesson from §36 applied.

**C6 — F42 (the instrument ceiling).**  *Sound, "with the 23-cell generalization
supported structurally rather than solely by two probes."*  It named the
falsifying measurement: sample the DUT's raw AD at the comparator's sampling
edge, bypassing `eff_hi`/`eff_lo`, and align it to the golden row.
**RUN, on the whole population: 24 of 24, 0 ambiguous alignments** (§43.3).  The
review's one reservation is discharged by measurement rather than argument.

**C7 — F43 (M20's cancellation edge).**  *Diagnosis sound; not landing it is the
right call* (it "touches the BIU display/eval spine" and §43 has a diagnosis and
a falsifier but no gate proof).  One wording correction, adopted: the first
draft's "a one-clock-earlier VIEW of the pipeline" *"risks suggesting duplicated
state"*; the principled statement is **"the HALT-display decision must test the
wake condition visible on its own decision edge"** — a term added to the
existing decision test, nothing new stored.  §43's F43 now says that.

**C8 — governance.**  Routing-not-patching confirmed: *"patching RTL to
reproduce a model residue would knowingly create an RTL-versus-silicon defect,
contrary to the stated governance."*  The stale-ratchet correction *"strengthens
monotonicity"* — remeasured, both figures recorded, gap recomputed per case
rather than history rewritten.  C8 also correctly noted the `CLAUDE.md` edit
itself was outside the review's permitted file set and so is NOT verified by it.

**The review's practical value this round was C6**, and it was the good kind:
it accepted the conclusion and rejected the strength of the evidence.  Running
the measurement it asked for is also what exposed §43.0's numbering artefact and
produced the retraction — a review that only checked the reasoning would have
left a false finding in two ledgers.

### §45.2 GATE U3 — THE RESULT

**GREEN, with two itemised and governed deltas.**

* **The ladder**: eleven of thirteen suites land ON the sim's ledger number
  (G3 169,000; `w1`/`w3`; `EB`; four `evt` cells; `w1evt-biased`; boot; wvec
  88/88 +0.0 %; ENTER 154/154 x5; INS 1,312/1,312 and 2,624/2,624), and the
  lockstep net was deepened 10x to **17,350/17,350**.
* **Where it BEATS the sim**: REGISTERED fuzz **1,394/1,702** (sim 1,272), the
  b2 victory tranche **168/188** (sim 154), and — under the hold the rig can
  physically apply — EVT **866/1,008** (sim 780) and COMBINED **2,260/2,710**
  (sim 2,052).  Governed as F39/§42.1 govern the class: silicon is the gate,
  `sim/` was not changed, the events are routed to the model's ledger.
* **Delta 1, the HLT sweeps** (−23 cells): **17 cells no comparator on this TB
  can score** (F42, measured 24/24) **+ 6 cells of one diagnosed rendering**
  (F43).  Zero unexplained.
* **Delta 2, the EVT fuzz column**: not the part's.  **F46** — the rig's
  `evt_hold` register is 8 bits and 760 of 1,008 seeds were banked asking for
  300.  Both legs move when it is corrected; the ratchet is therefore NOT
  re-registered here.
* **The platform**: `ss_lint --core ucore` landed (FSM leg byte-identical),
  census documented in the map header, 93 `+ce_div` cells clean over 9,300
  case-runs, save state green in modes 1/2/5 and — a ucore first — under random
  waits, and the bit-flip negative control discharged.  `ss_lint --core ucore`
  **exits 1**, truthfully, on F49.

Findings **F41-F50**.  Two landed (F41; the `timed_fuzz` denominator fix), one
retracted with its artefact preserved (§43.0), and the rest booked with
mechanisms and falsifiers.

### §45.3 THE SIX U3 OPEN ITEMS

| # | item | owner |
|---|---|---|
| 1 | **F42** — the TB's composed-AD drive mask hides a display inside a HALT-typed cycle. Re-latching `lat_type` at a display is a one-term change, but the TB is shared with the frozen FSM core: needs its own pre-registered before/after on BOTH cores | U4 |
| 2 | **F43** — the HALT-display decision must test the wake on its own decision edge (6 cells) | U4 |
| 3 | **F45** — `--ss-mode 4`'s guidance comment: "step the seed by 16", and "most flips must diverge" is too strong | U4 |
| 4 | **F46** — whether to re-register the EVT ratchet against `--rig-hold reg8`; `check_seq.run_tb` / `fuzz_campaign.capture_tb` carry the same unmasked hold | **campaign owner, not an RTL stage** |
| 5 | **F49** — five unmapped architectural flops; fixing bumps `SS_VERSION` | U4, FIRST |
| 6 | **F50** — dead `ending`; the bare `$error` pair in `poste.svh`; the CE-hold probe's BIU-only coverage | U4 |

Carried forward unchanged from §40.1/§42.6: the far-CALL/far-JMP `CS` shadow and
the taken-branch recognition boundary stay documented-but-not-rendered (no
golden reaches either); `opr_free_p`/`set_oprfree` stay PROVABLY VACUOUS (F31).

### §45.4 HANDOFF — WHAT U4 PICKS UP

1. **THE PREREQUISITE NOBODY HAS BUILT YET: `hdl/files_ucore.qip` DOES NOT
   EXIST.**  Only `hdl/files.qip` is in the tree, and it hard-lists
   `rtl/core/v30_{ss_pkg,core,biu,eu}.sv` plus `SEARCH_PATH rtl/core`.  The
   sibling manifest the plan's U4 stage runs Quartus through is still to be
   written; `sw/check_core.py`'s `CORE_RTL["ucore"]` is the file list it needs
   (`v30u_ss_pkg.sv`, `v30_core.sv`, `v30u_biu.sv`, `v30u_ucrom.sv`,
   `v30u_eu.sv`, `SEARCH_PATH rtl/ucore`).
2. **AND THE FIRST THING TO PUT IN IT IS F44's GUARD.**  `v30u_ucrom.sv` takes
   `HEXDIR` as a parameter *"a synthesis project overrides this with its own
   relative path"* — and a wrong path yields two WARNINGS, an all-zero
   microcode ROM, and a run that completes normally (F44, measured).  U4 is the
   stage that overrides `HEXDIR`.  Assert a known ROM word after load and
   `$fatal` if it is zero, BEFORE trusting any synthesis or in-fabric number.
   For Quartus the two `$readmemh` arrays additionally want `.mif`/`.hex`
   initialisation that the fitter will actually honour — verify the initialised
   contents in the post-fit netlist, not just that it compiled.
3. **Synthesis expectations, as the plan registered them**, restated so U4 can
   score them rather than re-derive them: **0 errors**; **map time in the ~4 min
   band** (the FSM core's rail forest takes ~25); **Fmax ≥ 32 MHz with margin**,
   with the one critical cone being the flow-through M10K row fetch (the
   fallback if 17.1 refuses flow-through is a registered output with the F2 tap
   moved one stage); **M10K ≈ 15-24 of ~553**, of which the ROM alone is
   `ucdecode` 8192x10 = 81,920 b plus `ucrom` 1028x29 = 29,812 b ≈ 11-14 M10K,
   both already carrying `(* ramstyle = "M10K" *)`; and **zero `lpm_divide`,
   zero inferred latches** (campaign-4 discipline — the EU has ONE shared
   iterative stepper by construction).
4. **THE PRIORITY GATE IS STILL THE PRIORITY GATE.**  The standing project
   ranking is arbitrary-wait accuracy first; U3 leaves the ucore with **no
   wait-axis debt on any scripted cell**, at **88/88 on the silicon wvec freeze
   where the frozen FSM core is 71/88**, and beating the model on the
   registered fuzz bank.  The fresh random-wait tranche in hardware, A/B against
   the socket, is U4's and is the campaign's victory condition.
5. **F42 IS A TESTABLE PREDICTION FOR U4, NOT JUST AN EXCUSE.**  If the 17
   uncountable HLT cells really are the testbench's composed-AD mask and not the
   core, then **in fabric — where the analyser samples real pins and no drive
   mask exists — those cells must PASS.**  That is a falsifiable, pre-registered
   consequence of F42 and U4 should score it explicitly.
6. **First place to look for a real bug is F47**: 83 registered seeds where the
   ucore gets the write cycle's address and timing exactly right and the DATA
   WORD wrong, on opcodes (`FF`/mod3, `F3`, `6A`, `A2`/`A3`, `8F`, `65`, `62`)
   the 169,000-case golden suite does not reach.  Then **F48**, the two EU bound
   assertions that fire on six banked seeds — the plan's risk #2, whose proof
   obligation is NOT discharged.
7. **Task #31's ENTER debt**: the ucore's ENTER leg is clean at 154/154 x5 over
   all seven wait slices.  Stated honestly, so is the FROZEN FSM core's on this
   same tranche — so `goldens_waited.json.gz` does not exercise the two task-#31
   bugs and CANNOT close them.  What U3 establishes is that the ucore has no
   ENTER waited-tranche debt of its own; the supersession claim still rests on
   U4's first flash, as the plan says.

# STAGE U4 — SYNTHESIS AND IN-FABRIC A/B

## §46 F48 DISCHARGED — THE BOUND IS A THEOREM OVER THE CORPUS AND NOT OVER ARBITRARY CODE

**The work item was the PROOF, not the assertion.**  §44's F48 recorded the two
EU bound assertions firing on six banked whole-program seeds and stated the
obligation plainly: *"the plan's risk #2, whose proof obligation is NOT
discharged"* — prove the real bound from the sim, or find the RTL accounting
error.  The C3 precedent (§27.1) went the RTL's-fault way.  **This one does
not**, and the measurement says so in both directions.

### §46.1 THE POSITIVE PROOF, RE-MEASURED AND EXTENDED TO THE WAIT AXES

`sw/qdepth_probe.py` drives the MODEL — which holds the truth — with
`V30SIM_QDEPTH=1` and reports the deepest either store ever reaches.  §27.1 ran
it on **v0.1 at w0 only**.  That is the gap that mattered, because the wait axis
is the axis this project ranks first, so it was re-run there and extended:

| corpus | `rdq_` max | `rd_done_q_` max | RTL capacity |
|---|---|---|---|
| `v0.1` w0, 347 forms / 169,000 cases | **2** (34 forms; hist 264/49/34) | **1** (245 forms) | 2 / 3 |
| `v0.1-w1` at w1 | **2** (`F7.6`) | **1** (`8B` `F7.6`) | 2 / 3 |
| `v0.1-w3` at w3 | **2** (`F7.6`) | **1** (`8B` `F7.6`) | 2 / 3 |
| `v0.1-w0evt` / `w1evt` / `w2evt` / `w3evt` | **2** | **1** | 2 / 3 |

The w0 row reproduces §27.1's table **form for form and histogram for
histogram** on this tree.  The four wait/evt rows are NEW.  **On every graded
corpus the store bound of two slots is correct and carries margin, and that is
now measured on the wait axis rather than assumed to carry over from w0.**

### §46.2 THE NEGATIVE RESULT — AND §27.1's OWN FALSIFIER IS MET

§27.1 registered the falsifier verbatim: *"any stimulus in which the MODEL's
`rdq_` reaches 3."*  Driven over the six seeds' whole programs, the model's own
stores reach:

| seed | model `rdq_` max | model `rd_done_q_` max | RTL assertion that fired |
|---|---|---|---|
| `mc1/2123` | 1 | **19** | `rd_done_cnt` saturated |
| `mc1/3613` | **8,334** | **8,334** | `rdq_n=2` overflow |
| `mc2/2244` | 1 | **9** | `rd_done_cnt` saturated |
| `t30-raw/440` | **8,334** | **8,334** | `rdq_n=2` overflow |
| `t30-raw/446` | 1 | **4** | `rd_done_cnt` saturated |
| `t30-raw/829` | 2 | 1 | `rdq_n=2` overflow |

**The falsifier is met.**  This is therefore NOT C3's shape: there the model
stayed in bound and the RTL was mis-counting; here **both engines leave the
regime together**, and the deepening is not a discovery about the part.  Both
are already far off the chip when it happens — the model's first divergence row
is 230 / 1,184 / 729 / 328 / 429 / 498 against bound crossings at clk 835 /
1,050 / 1,696 / 4,002 / 3,751 / never, and the model's own row diffs on these
six run 1,540-3,638 of 4,000.  A store depth reached 200-1,200 rows after an
engine left the silicon's trajectory is a property of the runaway, not of the
V30.

*So the capacity is NOT deepened.*  Fitting two more slots to garbage stimulus
would be the large-fitted-table failure the standing design principle names.

### §46.3 WHAT WAS ACTUALLY WRONG — THE COUNTERS WRAP IN THE BITSTREAM

The audit that the proof forced turned up the real defect, and it is a U4
defect rather than a U3 one:

```
hdl/nec_test.qsf:60   set_global_assignment -name VERILOG_MACRO "SYNTHESIS=1"
```

Both assertions live inside `ifndef SYNTHESIS`.  **In the bitstream they do not
exist**, and nothing else stood between an over-deep store and silently-wrong
behaviour: `rd_done_cnt` went `3 -> 0` and **dropped four completions** — its
only consumer is `nr_have = (rd_done_cnt != 0)`, so the EU would then wait
forever on reads that had already landed — and `rdq_n` went `2 -> 3` and handed
`rdq1` out twice.  The in-silicon fuzz of item 7 runs with no assertions at all,
so this is exactly the path U4 is about to drive.

**The BIU already had the house rule and the EU did not.**  Every bounded
counter in `v30u_biu.sv` either saturates or is guarded — `sev` (:1377,
`sev != 2'd3`), `cdage` (:1270, `cdage != 3'd7`), `rq_n` (:957 and :1287, both
`rq_n != 2'd2`).  The EU's did neither.  Applied there, one line each, and the
audit found **two more with no guard of any kind, not even an assertion**:

| counter | site | before | after |
|---|---|---|---|
| `rd_done_cnt` | `v30u_eu.sv` | wraps `3 -> 0` | saturates at 3 |
| `rdq_n` | `v30u_eu.sv` | wraps `2 -> 3` | saturates at 2 |
| `rd_pending` | `v30u_eu_row.svh`, `_step.svh` | wraps, **unasserted** | saturates at 3 |
| `wr_out` | `v30u_eu_row.svh` (`+2` on a split) | wraps, **unasserted** | saturates at 3 |

All four already had an explicit `!= 2'd0` floor on their decrements; this is
the matching ceiling.  Inert on every graded path by §46.1's proof, load-bearing
in fabric.

### §46.4 THE SEVERITY NOW MATCHES THE SCOPE — AND IS RE-ARMED WHERE THE PROOF HOLDS

With the behaviour defined, an unconditional `$stop` is actively harmful: it
makes the Verilator leg differ from the bitstream, and **an aborted seed is not
scored, and an unscored seed is not evidence.**  The two assertions are now
`assert (...) else $warning(...)` — still SVAs, so `$assertoff(0)` still
quiesces them for the save-state scramble (F50 item 2's trap), still counted
among the contracts, no longer fatal.

**A `$warning` nobody counts is a vacuous gate, so it is counted in two places
and the golden gate is re-armed at exactly the scope the proof covers:**

* `sw/check_core.py` — a bound fire on a GOLDEN case is a **hard failure**.
  There the bound is a theorem (§46.1), so a fire is a regression.  Verified
  not to false-fire on the 15 forms that legitimately reach depth 2
  (`A6 A7 CA-CF 61 62 F6.6 F6.7 F7.6 F7.7 HLT.INT`): **7,200/7,200**.
* `sw/timed_fuzz.py` — a new `BOUND WARNINGS` line names and counts the seeds
  that left the regime; they are **scored normally, not excused**.  It reports
  **6**, and they are exactly F48's six — an independent reproduction of the
  finding by the instrument that replaced it.
  (`run_tb` had to carry them out: Verilator writes `$warning` to **stdout**,
  not stderr, and stamps every line with the sim time, so the lines are
  deduplicated on the message.)

### §46.5 THE RE-SCORE — THE ENGINE CHANGED, THE NUMBERS DID NOT

**The scoring engine changed, so the whole ladder was re-run rather than
inherited.**  U3's numbers remain true of commit `06edf0b927`, which rebuilds
bit for bit to `sha256 b76b7734…` (verified at the start of this stage).

| gate | U3 (`b76b7734`) | **U4 post-F48** |
|---|---|---|
| G3 `check_core --core ucore --opcodes all` | 169,000/169,000 | **169,000/169,000** |
| `v0.1-w1` / `-w3` | 1,200 / 1,200 | **1,200 / 1,200** |
| `v0.1-w1 --opcodes EB` | 200 | **200** |
| `w0evt` / `w1evt` / `w2evt` / `w3evt` | 200 / 1,200 / 200 / 1,200 | **200 / 1,200 / 200 / 1,200** |
| `v0.1-w1evt-biased` | 1,200 | **1,200** |
| `check_boot --core ucore` 220 / 400 | MATCHES / MATCHES | **MATCHES / MATCHES** |
| `ulockstep --golden all --cases 50` | 17,350/17,350 | **17,350/17,350** |
| `timed_wvec_gate --core ucore` | 88/88, +0.0 % | **88/88, +0.0 %** |
| `timed_enter_replay --core ucore` | 154/154 x5 | **154/154 x5** |
| `timed_ins_replay --core ucore --raw` | 1,312 / 2,624 | **1,312/1,312 and 2,624/2,624** |
| `timed_fuzz` REGISTERED | 1,394/1,702 | **1,394/1,702** |
| `timed_fuzz` EVT / COMBINED | 184/1,008 / 1,578/2,710 | **184/1,008 / 1,578/2,710** |
| b2 victory tranche | 168/188 | **168/188** |
| the four HLT sweeps | 90/97, 88/95, 37/46, 34/45 | **90/97, 88/95, 37/46, 34/45** |
| FSM core, untouched | 1,400/1,400 | **1,400/1,400** |
| **`ENGINE ABORTS`** | **6** | **0** |
| **`BOUND WARNINGS`** | (did not exist) | **6, named and scored** |

**Every cell reproduces, and the denominators held** (2,710 scored / 532
`OPEN_BUS`; 188 / 28).  That is the intended reading and not a coincidence: on
the golden corpus the saturation is unreachable by §46.1's proof, and on the
bank the six un-aborted seeds all still score as `DIVERGE`, so no `EXACT` count
could move.  **What moved is that six seeds now produce evidence instead of a
crash, and the harness exits 0.**

*Falsifier for the whole finding*: a stimulus on which the ucore's store
saturates while the MODEL's stays within two — that would be C3's shape after
all, and an accounting error to find.  The instrument for it is the
`BOUND WARNINGS` line next to a `qdepth_probe` run on the same seed.

## §47 F49 AND F44 — THE TWO PLATFORM ITEMS U3 ROUTED, BOTH CLOSED

### §47.1 F49 — THE FIVE UNMAPPED FLOPS ARE IN THE MAP; `ss_lint --core ucore` EXITS 0

U3 open item 5, and U4's first platform job because *"a restore that loses a
completed read's data is a real defect, not a bookkeeping one."*  The five
architectural flops the census found are appended per the map's own APPEND-ONLY
rule — at the end of each module's dense region, renumbering nothing:

| flop | what it holds | address | width |
|---|---|---|---|
| `r_cur_odd` | the split access's ODD BASE (byte swap, `v30u_biu.sv:1329`) | `0x061` | 1 |
| `r_cmt_odd` | " | `0x062` | 1 |
| `r_rq_odd[0]` | " | `0x063` | 1 |
| `r_rq_odd[1]` | " | `0x064` | 1 |
| `r_rd_land` | **a completed read's data**, on its way to `eu_rdata_n` | `0x065` | 16 |
| `rst_ctr` | F25's four-clock reset march position | `0x173` | 3 |

`SS_VERSION` **0x81 -> 0x82**, `SS_BIU_COUNT` 96 -> **101**, `SS_EU_COUNT`
115 -> **116**, `SS_COUNT` 212 -> **218**, `SS_TAG` 0x81D4 -> **0x82DA**.  The
version moves because addresses were ADDED: a v1 stream has no words for them
and must not be silently accepted.  `sw/ss_lint.py`'s pinned `EXPECT` moved
with it, v1's values recorded in place rather than overwritten.

| gate | before | **after** |
|---|---|---|
| `ss_lint --core ucore`, map audit | PASS (96x2 + 115x2 + tag = 212) | **PASS (101x2 + 116x2 + tag = 218)** |
| `ss_lint --core ucore`, flop census | **FAIL**, 5 UNMAPPED, `rc=1` | **PASS, 223 flops, 0 UNMAPPED, `rc=0`** |
| `ss_lint --core fsm` | PASS, 203 / 181 flops, `rc=0` | **unchanged, `rc=0`** |
| save state, scramble (mode 1) | 80/80 | **20/20 freeze-point sets, 574 points, 0 diverging k** |
| save state, idempotence (mode 2) | 24/24 | **20/20, 574 points, 0 diverging k** |
| save state, width (mode 5) | PASS | **20/20, 574 points** — the five new addresses round-trip at their declared widths |
| save state under RANDOM waits | 10/10 x2 | **10/10 at `wmax3`/`ACE1` and 10/10 at `wmax7`/`5678`** |

**Mode 5 is the load-bearing row.**  It is the width round-trip, and it now
passes over a map that contains the five addresses — which is precisely what it
could not do before, because *"both instruments only visit addresses that
EXIST"*.  The blind spot is closed by the same instrument that could not see
it, only after the census (which runs RTL -> map) told it where to look.

**KNOWN-RED IS NOW GREEN.**  `CLAUDE.md`'s "KNOWN-RED, deliberately" entry for
`ss_lint --core ucore` is retired, not silenced.

### §47.2 F44 — THE ROM CANNOT LOAD SILENTLY-EMPTY ANY MORE, AND THE GUARD IS PROVED ARMED

F44, measured at U3: a wrong `HEXDIR` yields **two warnings, an all-zero
microcode ROM, and a run that completes normally.**  For a core whose entire
architecture is two tables that is the worst possible failure mode, and U4 is
the stage that overrides `HEXDIR`.

Two halves, because the two tools differ:

1. **The default is now picked per tool** rather than left for a project to
   remember.  `ifdef SYNTHESIS` -> `"rtl/ucore/"` (Quartus runs from `hdl/`);
   otherwise `"hdl/rtl/ucore/"` (simulation runs from the repo root).
2. **Four probes and a `$fatal`**, in a SEPARATE `initial` from the `$readmemh`
   one and under `ifndef SYNTHESIS` — the load block must stay a bare sequence
   of `$readmemh` calls or Quartus can decline to infer the M10Ks and build
   91,732 bits out of registers, which would be a worse outcome than the bug
   being guarded.  The probes test *"did anything load here"*, not *"is this
   the expected word"*: the CONTENT is already gated byte-for-byte by
   `sw/check_ucore_tables.py` (G0, 9,988 checks), and pinning words here would
   only add a second place to update.  `!==` so an X fails exactly as a 0 does.

   * `ucrom[0]`, `ucdecode[0]` — the file is absent or empty
   * `ucrom[1027]` — the file is SHORT (last row, and it is non-zero)
   * `ucdecode[0x1E43]` — the decode table's LAST VALID entry.  Its literal
     last address is a legitimate `0x000`, so probing that would prove nothing.

**PROVED ARMED, not inferred** — §44.3's standard.  Three negative controls,
each a separate Verilator build of `v30u_ucrom` with `-GHEXDIR`:

```
HEXDIR="no/such/dir/"  -> %Fatal ... ucrom.hex did not load ... the ROM is EMPTY (F44)
HEXDIR="shortdir/"     -> %Fatal ... ucrom.hex is SHORT ... row 1027 never loaded (F44)
HEXDIR=<the real path> -> silent, rc=0
```

The two `$readmemh` warnings still appear in the first case — they were the
ONLY signal before, and a warning in a build log is not a gate.

### §47.3 THE SYNTHESIS MANIFEST — AND WHY IT IS A REVISION, NOT A SWITCH

`hdl/files_ucore.qip` is written: the platform files verbatim from `files.qip`,
the ucore's five modules in `CORE_RTL["ucore"]` order, and `SEARCH_PATH
rtl/ucore` so the EU's nine `.svh` includes resolve by basename.

**The first arrangement was wrong and the tool said so.**  A `V30_CORE`
environment switch inside `nec_test.qsf` fails: Quartus reads the `.qsf` with a
restricted settings parser that has no `if` — `Error (125048)` on every line of
the conditional, `Error (125080) Can't open project`.  So the ucore is a
Quartus **REVISION**, `nec_test_ucore`, which is the tool's own mechanism for
exactly this and additionally gives the two-bitstream A/B its own output
directory:

```
quartus_sh --flow compile nec_test -c nec_test_ucore     # -> output_files_ucore/
quartus_sh --flow compile nec_test -c nec_test           # -> output_files/  (FSM, unchanged)
```

`hdl/nec_test_ucore.qsf` is **GENERATED** by `sw/gen_ucore_qsf.py` from
`nec_test.qsf` by changing exactly two lines (the sourced `.qip` and the output
directory) and copying device, pins, timing and every `VERILOG_MACRO` verbatim.
`--check` re-derives and compares.  That is the gate on the A/B's central
claim: **the two bitstreams differ by the CORE and by nothing else.**  A
hand-maintained copy would drift, and a drifted copy turns a controlled
comparison into an uncontrolled one without saying so.

The FSM baseline bitstream was archived BEFORE any of this ran
(`~/.cache/ucsimt-tmp/u4-quartus/fsm-baseline-output_files.tgz`;
`nec_test.rbf` `sha256 2643d8ce…`, `nec_test.sof` `sha256 1cc4bf55…`).

### §47.4 ZERO REGRESSIONS, RE-MEASURED AFTER BOTH

The RTL changed (the map grew, the ROM module gained a guard), so the ladder was
re-run rather than inherited:

G3 **169,000/169,000**; `w1`/`w3` **1,200/1,200**; boot **220 and 400 MATCH**;
fuzz REGISTERED **1,394/1,702**, EVT **184/1,008**, COMBINED **1,578/2,710**,
`BOUND WARNINGS` **6**; b2 tranche **168/188**; wvec **88/88, +0.0 %**; ENTER
**154/154 x5**; `ss_lint --core ucore` **rc=0**; FSM core **1,400/1,400** and
its `ss_lint` leg unchanged.

## §48 THE IN-FABRIC PRE-REGISTRATION — WRITTEN AND COMMITTED BEFORE ANY BOARD CONTACT

Standing discipline (`CLAUDE.md`): *"pre-register predictions and commit before
first board contact."*  Everything in this section is registered BEFORE a
bitstream exists, so none of it can be tuned to a result.

### §48.0 THE STATE OF THE BOARD AT REGISTRATION

`root@mister-nec`, reachable, `up 22 days`; JTAG chain present
(`DE-SoC [1-1.2.4]`, `SOCVHPS` + `5CSEBA6/5CSEMA6`).  **Single-writer check: no
`v30`/serve/python process on the board.**  The FSM baseline bitstream is
archived (`nec_test.rbf sha256 2643d8ce…`, `nec_test.sof sha256 1cc4bf55…`).

### §48.1 THE PRE-FLASH GATE, ALREADY MET

`check_ab_sim --core ucore` puts the ucore inside the REAL integration
(`system_large` + `nec_bus` + the capture path) and diffs its boot against the
chip's own capture.  **MATCHES over 187 rows from RESET release, 0 rows
differ**, with the loop `CODE T1 @00100` recurrence identical to silicon's
(`[26, 90, 154]`).  The FSM leg, restored, gives the same.  A bitstream is not
flashed on a core that has not passed this.

### §48.2 FLASH #1 — `use_core=0` FIRST

The first thing the new bitstream must prove is that it did NOT disturb the
chip path.  `use_core=0`, boot capture, compared against the standing golden.
**Bar: identical.**  A difference here is a PLATFORM finding and stops the
stage — it would mean the ucore revision changed something outside the core,
which `sw/gen_ucore_qsf.py --check` is supposed to make impossible.

### §48.3 F42's FALSIFIABLE PREDICTION, REGISTERED WITH ITS SCORE SHEET

§45.4 item 5, verbatim in substance: if the 17 uncountable HLT cells really are
the TESTBENCH's composed-AD drive mask and not the core, then **in fabric —
where the analyser samples real pins and no drive mask exists — those cells must
PASS.**

* **PREDICTION: all 17 PASS in fabric.**
* Scored explicitly, cell by cell, in the `idx` = pin-delay `d` numbering
  (§43.0's numbering trap: the `idx` FIELD is `d`, not the array position).
* **If any of the 17 fails in fabric, F42 is REFUTED** and the ucore owns those
  cells — that is the honest outcome and it is to be reported as a refutation,
  not re-explained.
* The 6 cells of F43 (the diagnosed HALT-display rendering) are NOT part of
  this prediction and are expected to fail in fabric too.

### §48.4 THE STANDING PRIORITY GATE — THE FRESH RANDOM-WAIT TRANCHE

The project's #1 ranking is arbitrary-wait accuracy, and this is the campaign's
victory condition.  ~200 stratified `wrand` seeds, **frozen before capture**
(seed list + image shas committed before the first capture), chip capture vs
ucore-in-fabric replay.

| # | bar | registered value |
|---|---|---|
| **V0** | hard failures | **0** — no wedge, `div_guard` PINNED readback on EVERY capture, full per-clock rows + sha256 retained (never digests alone) |
| **V1** | ucore-in-fabric cycle-exact vs the socket | **>= 85.0 %** — the BANKED b2 tranche is 89.4 % (168/188) and fresh seeds are not cherry-picked, so the bar is set below it and is still falsifiable |
| **V2** | denominator integrity | the two legs score **identical denominators**; a denominator that follows the engine is not a gate (§44.2's own lesson) |
| **V3** | fabric-vs-Verilator control | the SAME seeds through the Verilator ucore land **within ±2 seeds** of the fabric number. A larger gap is a **FABRIC-vs-SIM finding** — the bitstream and the model of it disagreeing — and is the MORE important result if it happens |
| **V4** | comparative | the ucore beats the FSM core on the SAME seeds (the FSM is 18/1,702 on the registered bank and 71/88 on the wvec freeze, so this should be decisive; a near-tie would itself be a finding) |
| **V5** | residue | every non-exact seed lands in the inherited taxonomy (`qs` / `bs` / `data` / `nxta` / `ps` / `t`), **0 unclassified** |

**V1 is a NEW registration on a NEW population and is NOT the retired
campaign's V5.**  That one — 188/188 on the banked tranche — remains a standing
REGISTERED FAILURE at 168/188 and is not re-opened here (§44.2).

### §48.5 THE RIG WIDENING (F46) IS **DEFERRED**, AND WHY

The optional item was to widen the rig's `evt_hold` register in this same
bitstream so fresh captures use true holds.  **Not taken**, for two reasons and
one measurement:

1. **It would confound the headline comparison.**  The FSM-vs-ucore A/B has to
   differ by the CORE and nothing else — that is the whole point of generating
   `nec_test_ucore.qsf` from `nec_test.qsf` and gating it with `--check`.
   Widening the rig in the ucore bitstream only would put a RIG change inside
   the core comparison.  Widening it in both means rebuilding both, which is a
   different and larger piece of work.
2. **It is not on the priority gate's path.**  §48.4's tranche is the
   random-WAIT axis; its seeds carry no `evt` directive, so a corrected hold
   moves nothing there.  F46's own text routes the EVT ratchet decision to
   *"the campaign owner, not a side effect of an RTL stage."*
3. **Measured, and it is not a one-line widening.**  `hps_axi_slave.sv:273-277`
   packs register `0x20` as `evt_delay[15:0] | evt_hold[23:16] |
   evt_pin[26:24] | evt_arm[31]`.  A 16-bit hold COLLIDES with `evt_delay`.
   The free space is bits `[30:27]` — four bits — so the widest drop-in is a
   **12-bit** hold (`{wdata[30:27], wdata[23:16]}`, max 4,095, which does cover
   the banked 300).  That is a HOST-PROTOCOL change as well as an RTL one:
   `fuzz_campaign._evt_tuple`, `check_seq.run_tb` and `check_seq.run_chip` all
   pack this word and would have to move together.

Recorded as a U5 item with the packing already worked out, so whoever takes it
starts from a measurement rather than a guess.

## §49 F47 CLOSED — `begin_sequence()`'s OTHER LINE WAS NOT TRANSCRIBED AT THE INSTRUCTION BOUNDARY

**Class: RTL BUG (a mechanism rendered half — §16's named class, and F41's
shape exactly).  LANDED: REGISTERED 1,394 -> 1,483 (+89), tranche 168 -> 171.**

§45.4 item 6 sent U4 here first: 83 registered seeds where the ucore *"gets the
write cycle's address and timing exactly right and the DATA WORD wrong"*, on
opcodes the 169,000-case golden suite does not reach.

### §49.1 THE CENSUS, RE-DERIVED, AND THE PREDICATE STATED

Re-derived on the current binary rather than inherited (the seed list is not
U3's).  The predicate is a property of the DIFF, not of the opcode: *the seed is
in the scored REGISTERED population, the ucore diverges, the FIRST diverging
row's only parting column is `ad_data` at a T2/T3 clock, and the chip
transaction containing that row is `MEMW` or `IOW`.*

**95 seeds** (MEMW 81, IOW 14) of 308 ucore divergences; all 104 `data`-first
rows carry exactly one item, 0 mixed.  `ndiff = 2` — just the write's T2+T3 —
in **38**, and `<= 6` in **51**.  28 distinct owning opcodes.  Tranche: 3.

### §49.2 THE DISCRIMINATOR, RUN BEFORE ANY RTL READING

For each family seed: is the MODEL's word at that same row right?

| | REGISTERED | tranche |
|---|---|---|
| **A — model RIGHT, ucore WRONG -> RTL BUG** | **84** (73 of them the model is exact over the whole seed) | 3 |
| B — model diverged EARLIER, cannot discriminate (excluded, not counted against anything) | 7 | 0 |
| **C — model ALSO wrong -> SHARED, ledger not patch** | 4 | 0 |

### §49.3 THE MECHANISM — ONE LINE, AND IT IS A PROPERTY OF THE BOUNDARY

`CpuT::step()` (`sim/exec_impl.h:777`) opens EVERY instruction with
`begin_sequence()` (`:710`):

```cpp
pend_ = Pending{};  rdq_.clear();  opr_fresh_ = false;  rep_elems_ = 0;
```

The RTL transcribes that block **verbatim at the interrupt entry**
(`v30u_eu_step.svh`, comment *"`begin_sequence()`: the pairing latch and the
completed-read store"*) and at reset.  At **`S_INSTR_END`** — the ORDINARY
instruction boundary — only ONE member survived:

```systemverilog
rep_chain = 1'b0;                    // `begin_sequence()`: rep_elems_ = 0
```

So a `-> OPR` write in instruction N left the **pairing latch armed into N+1**,
and `eu_pair` fired on N+1's POSTING row and handed the BIU **N's operand**.
`soup_1008` (`PUSH AX`, `ndiff = 2`) is the whole bug in four clocks:

```
clk 488  upc=0.50.1  post=1 pair=1  a=03efe  wd=0f94  of=1   <- posts MEMW and PAIRS it same clock
clk 489  upc=0.50.2  (M -> OPR)     opr=0f94 of=0            <- the supply row, stalled
clk 490  T1 MEMW a=03efe   chip d=9d00   ucore d=0f94   sim d=9d00
clk 500  upc=0.9c.0                opr=9d00 of=1            <- AX lands, 10 clocks late
```

`0f94` is what the PREVIOUS instruction's row `4.26.13` (`SIGMA -> OPR`) left in
OPR.  **This is why the opcode list is diffuse and why the golden suite cannot
reach it: the leak is a property of the BOUNDARY, not of either instruction, and
a single-instruction case cannot build it.**  It needs a `-> OPR` in N and a
store posted before its own supply row in N+1.

Corroborating state, measured over the 84: **75 have NO architectural
divergence at all before the failing write**; at its T1 `eu_opr_free = 0` in
84/84 and `opr_fresh = 0` in 76/84; and in **67/84 the CORRECT word arrives in
`opr` a few clocks LATER**, on the instruction's own datum-supply row.

### §49.4 THE CAUSAL PROOF — THE MODEL WAS BROKEN THE SAME WAY ON PURPOSE

Not an argument, an experiment, with the bars registered **before** the run: a
scratch copy of `sim/` with **exactly one line commented out of
`begin_sequence()` — `opr_fresh_ = false;`** — and nothing else.

| bar | registered | **measured** |
|---|---|---|
| family seeds reproducing the ucore's EXACT wrong word | **>= 60/84** | **74/84**, and the patched model's first divergence lands on the SAME ROW INDEX in all 74 |
| controls left exact | **>= 180/200** | **200/200** |
| tranche | — | **3/3**, identical `ndiff` |

*Falsifier, and it is honoured*: a family seed whose entry-time `opr_fresh` is
already 0 and whose word is still wrong.  **Four of the 84 are exactly that**,
so mechanism 1 is explicitly NOT claimed to be universal — §49.6 names the rest.

*Registered, not restated*: a cheaper PROXY predicate was pre-registered at 0
hits on the control and came in at 29, and at 3 after its supply-row detector
was corrected to count `-> M` / `-> R`.  **It never reached 0.**  The claim
rests on the patched-model experiment, not on the proxy.

### §49.5 THE FIX, AND WHY IT GOES IN `iend_late`

One line, no table, no per-opcode case, in `v30u_eu_iend_late.svh`:

```systemverilog
opr_fresh = 1'b0;
```

Deferred there rather than in `S_INSTR_END`'s immediate block **by that file's
own stated condition**: the post-`E` row STILL READS `opr_fresh` (the `poste &&
pend_active && (opr_fresh || poste_wr_opr)` arm of `eu_pair`, and `opr_now`),
and the edge-`c` chain never writes it — so the register still holds the
predecessor's value at the discharge and `iend_owed` pays it in the model's
order.  That is F22's rule applied, not a new one.

### §49.6 THE SCORE — AGAINST THE PRE-REGISTERED BAND, INCLUDING WHERE IT OVERSHOT

| gate | before | registered bar | **after** |
|---|---|---|---|
| `check_core --core ucore --opcodes all` | 169,000/169,000 | **0 new failures** | **169,000/169,000** ✅ |
| fuzz REGISTERED | 1,394/1,702 | **>= 1,434**, expected 1,446, **<= 1,464** | **1,483/1,702 (87.1 %)** |
| b2 victory tranche | 168/188 | **171/188** | **171/188 (91.0 %)** ✅ exactly |
| fuzz EVT | 184/1,008 | — | **192/1,008** |
| fuzz COMBINED | 1,578/2,710 | — | **1,675/2,710 (61.8 %)** |
| `BOUND WARNINGS` | 6 | — | **5** |

**THE REGISTERED BAND WAS OVERSHOT AND THAT IS RECORDED AS A DEVIATION, NOT AS
A WIN.**  +89 against a band whose top was +70.  The falsifier (*"if REGISTERED
moves by fewer than 40, the attribution is wrong"*) is not met by a wide margin,
so the attribution stands; but the size estimate was built from three
sub-counts (40 near-certain / 52 whole-diff-equal / 70 model-exact) and all
three under-predicted, which means the leak also converted seeds whose diff the
patched-model experiment did not model exactly.  Named as an open estimate
error rather than smoothed away.

**The ucore now beats the model on the registered bank by 211 seeds**
(1,483 vs 1,272) and on the victory tranche by 17 (171 vs 154).

### §49.7 THE FOUR SHARED SEEDS — A LEDGER FINDING, DELIBERATELY NOT PATCHED

| seed | cycle | chip | **both engines** |
|---|---|---|---|
| `raw_2340_8df9460dd643` | MEMW `0x3efd` (odd) | `35ab` | `ab35` |
| `raw_3868_3995afd408b7` | MEMW `0x3ef8` ube=1 | `b6cd` | `cdb6` |
| `raw_453_99bdf08b95ea` | MEMW `0xb97d` (odd) | `ad00` | `00ad` |
| `raw_624_d20cc1a550cc` | MEMW `0x9998e` | `f206` | `fa87` (not a swap) |

Three of four are an exact **byte swap on an odd-address word write** — M5b's
"one pass through the A0 swapper" (`BiuTimed::mem_write`'s `swap8` on `a & 1`)
applied where the chip does not.  The ucore and the model **agree with each
other and disagree with the socket**, with identical `ndiff` on all four.  Per
governance this is an RTL-vs-silicon question the sim SHARES: a ledger finding,
never a patch.  Patching the ucore's rotation would knowingly create an
RTL-vs-silicon defect that the model would then contradict.

### §49.8 THE RESIDUAL TEN, NAMED

* **6 — `8F`'s write-back drives a stale OPR when the pop lands at or after
  T1.**  `soup_2862`: row `0.8f.3` asserts `eu_pair` at 586-587 with `wd=0000`;
  the pop's `af05` reaches the EU at **591, the write's own T1**.  The model
  gets it free because `rdq_` is filled at ISSUE time, and `deliver_read()`'s
  comment records the measured chip behaviour verbatim: *"`8F.0` mod0 — the
  write-back's cycle is reserved at the load's T3 eval, three clocks before the
  load's data reaches OPR, and drives that data anyway."*  The ucore's
  `opr_now` lookahead covers a completion on the pairing clock ONLY.
  *Falsifier*: an `8F` seed whose completion lands strictly before T1 and whose
  word is still wrong.
* **3 — `10`/ADC, an ALU carry-in.**  `soup_721`: at `0.10.1` the ucore's
  `tmpa/tmpb/tmpc` are byte-identical to the model's and `sigma` differs by
  exactly **1** — CY=1 where the model has CY=0.  Two instructions back are
  `9E` SAHF (AH bit -> CY=1) then `F5` CMC (CY -> 0), both executed by the
  loader with ZERO micro-rows.  **Which of the two fails to land was NOT
  decided**, because both produce CY=1.  *The measurement that decides it*:
  `SSA_E_PSW` is already in the map, so `+ss_at=<clk>` reads PSW out at the
  boundary between them **on the frozen binary, no RTL change**, against
  `PSW=` in `v30sim image --trace`.
* **1 — `raw_15` under `50`**, chip `ffc9` / ucore `ffc7`, off by 2.  Unexplained.

### §49.9 THE OTHER TWO MEMBERS OF `begin_sequence()`, STILL NOT TRANSCRIBED

`pend_*` and `rdq0/rdq1/rdq_n` are the remaining members that `S_INSTR_END`
does not reset.  `pend_active` is provably 0 there (`S_TAIL_W` emits first), but
**`rdq` demonstrably is not** — `soup_2862` carries `rdq=1 rdc=1` across the
boundary into `0.97`, where the model would have dropped it.  Whether that is
load-bearing is its own measurement (re-run the bank with `rdq_n = 0` added and
see whether anything moves **in either direction**).  Not done here; U5 item.

## §50 GATE G6 (SYNTHESIS) — **RED.** THE COMBINATIONAL ROM READ DOES NOT FIT THE DEVICE

**This is the stage's hard result and it stops the fabric half of U4.  There is
no ucore bitstream.  Nothing was flashed.**

### §50.1 THE NUMBERS, AGAINST THE REGISTERED EXPECTATIONS

`quartus_sh` 17.1.0 Lite, revision `nec_test_ucore`, device `5CSEBA6U23I7`.

| gate (§45.4 item 3) | registered expectation | **measured** | |
|---|---|---|---|
| Analysis & Synthesis errors | **0** | **0**, `rc=0` | ✅ |
| `quartus_map` wall | **~4 min band** (not 25) | **772.9 s = 12 min 53 s** | ❌ (the FSM revision's own A&S is **2:49**) |
| **zero `lpm_divide`** | 0 | **0** | ✅ — and strictly better than the FSM core, which instantiates one (`lpm_divide:Div0`) |
| **zero inferred latches** | 0 | **0** | ✅ (the 161 "latch" strings in the report are all Altera IP net names — `address_latch`, `SigmaLatch`, `burstcount_latch`) |
| M10K for the two ROM tables | **~11-14** (of the design's 15-24 / 553) | **0** | ❌ |
| ALMs | the FSM design is 25 % | **28,048 / 41,910 = 67 %** | ❌ |
| Fmax >= 32 MHz with margin | >= 32 MHz | **NOT MEASURED — STA never ran** | ❌ |
| bitstream | a `.sof` | **none produced** | ❌ |

```
Error (11802): Can't fit design in device.
Error (170143): Final fitting attempt was unsuccessful
Fitter Status : Failed        elapsed 00:35:49, CPU 00:56:21, peak VM 3,900 MB
```

**And it did not fail on AREA — it failed on ROUTING.**  67 % of the ALMs were
placed; what broke was the router:

```
Warning (16684): The router is trying to resolve an exceedingly large amount of
congestion.  At the moment, it predicts long routing run time and/or
significant setup or hold timing failures.
```

### §50.2 THE CAUSE, IN QUARTUS'S OWN WORDS

The architecture's one registered risk-#3 was *"BRAM flow-through/Fmax (one
cone)"*, with the fallback stated in advance: *"if 17.1 refuses flow-through,
a registered output with the F2 tap moved one stage."*  **17.1 refuses, and it
says exactly why:**

```
Info (276007): RAM logic "…|v30u_eu:u_eu|v30u_ucrom:u_ucrom|ucrom" is
               uninferred due to ASYNCHRONOUS READ LOGIC     (v30u_ucrom.sv:54)
```

...and the same message for **~37 more arrays**, all of them
`hdl/rtl/ucore/pla3_tables.svh` (lines 110 / 373 / 636).  A Cyclone V M10K read
port is REGISTERED by construction, so `(* ramstyle = "M10K" *)` cannot make an
asynchronously-read array a block RAM — the attribute is a preference, not an
override.  Both microcode tables and the whole PLA3 set therefore became LUT
logic:

| entity | combinational cells | registers | block memory bits |
|---|---|---|---|
| **FSM** `v30_core` | 12,257 | 1,150 | 0 |
| **FSM** `v30_eu` | 11,471 (11,315 own) | 860 | 0 |
| **ucore** `v30_core` | **32,534** | 1,069 | 0 |
| **ucore** `v30u_eu` | **31,647 (30,621 own)** | 675 | 0 |
| **ucore** `v30u_ucrom` | 1,026 | 0 | **0** |

The core is **2.65x the FSM core's combinational logic**, and the design's
`Total block memory bits` is **840,863 — byte-identical to the FSM build's**,
which is the cleanest single proof that not one bit of the microcode went into
a memory block.  (The ROM's own module shows only 1,026 cells because Quartus
flattens the combinational read across the boundary and the giant mux lands in
the EU's own total.)

### §50.3 WHAT THIS MEANS — THE FALLBACK IS NOW REQUIRED, NOT OPTIONAL

The architecture documented both shapes and this is the measurement that
chooses between them.  **The combinational-ROM-read decision is REFUTED by the
tool.**  The registered fallback — *"a registered output with the F2 tap moved
one stage"* — is the way forward, and it is not a synthesis tweak: **it changes
the EU's cadence**, so it must go back through the entire sim ladder (G3's
169,000, the wait axes, lockstep, the silicon replays, the fuzz bank) before it
can be trusted, and the whole of §46/§47/§49's re-scoring would have to be
repeated on it.  That is U5-scale work and it is NOT started here.

Two smaller, independent reductions are worth measuring at the same time,
because the PLA3 arrays are 37 of the ~38 uninferred nodes and were never the
headline:

1. **`pla3_tables.svh`'s arrays are combinationally read too.**  §26.10 calls
   PLA3 *"a combinational generated case ROM (~10.7 Kb)"* — small in BITS, but
   it is 37 uninferred nodes and a large share of the congestion.  Whether they
   want registering, or are simply better written as a `case` the synthesiser
   maps to logic deliberately, is a separate measurement.
2. **`ucdecode` is 8192 x 10 = 81,920 b of which only 1,656 entries are valid**
   (measured).  A direct-addressed 8,192-entry table was chosen so the RTL
   carries *"ZERO match/priority logic"*; at 80 % empty it is also 80 % of the
   mux that will not route.

### §50.4 TWO HYGIENE FINDINGS THE COMPILE TURNED UP

1. **`Warning (10335): Unrecognized synthesis attribute "shape"` at
   `v30u_ucrom.sv(22)`.**  Line 22 is a **COMMENT**: *"(U4 owns the synthesis
   shape; the `ramstyle` hints below are what Quartus is asked for.)"*  Quartus
   parses `synthesis <word>` inside a comment as a PRAGMA.  Harmless here — the
   attribute is unrecognised and ignored — but it is a live hazard: a comment
   that happens to contain `synthesis` followed by a REAL attribute name would
   silently change the build.  Not fixed in this tree because a comment edit
   forces a 13-minute re-map; fix it with the fallback work.
2. **`Warning (10230): truncated value with size 12 to match size of target
   (10)` on EVERY line of `ucdecode.hex`** — 8,192 of them.  The array is
   `[9:0]` and the hex file carries 3 hex digits.  Numerically harmless (the
   words are `{valid, bank[8:0]}`, max `0x3FF`) and Verilator is silent about
   it, but it buries the map log.  Emitting the table as 10 bits (or declaring
   the array 12) removes 8,192 warnings.

### §50.5 WHAT DID **NOT** HAPPEN, AND WHY — STATED PLAINLY

Items 7-10 of the U4 plan are **NOT DONE**, and the reason is a single hard
fact: **the fitter produced no bitstream.**  Nothing was flashed, so:

* **no milestone flash #1** (`use_core=0` chip-path check, then `use_core=1`);
* **no first light**, no in-silicon A/B fuzz;
* **F42's falsifiable prediction (§48.3) is UNSCORED** — the 17 TB-masked HLT
  cells still have no fabric measurement, and it remains a live, registered,
  falsifiable prediction;
* **the standing priority gate (§48.4) is UNRUN** — no fresh random-wait
  tranche was captured;
* **no FSM-vs-ucore two-bitstream A/B**, and therefore **task #31's ENTER flash
  debt is NOT superseded** — it stands exactly as it did.

**The board was left untouched.**  It was checked for reachability and
single-writer status (§48.0) and nothing else; no capture was taken, no
bitstream loaded, `use_core` was never set.  The FSM baseline bitstream is
unchanged on disk and unchanged on the board — `nec_test.rbf sha256 2643d8ce…`,
`nec_test.sof sha256 1cc4bf55…`, re-verified after the compile.

The one in-fabric-shaped result that DOES stand is §48.1's, and it is not
nothing: `check_ab_sim --core ucore` puts the ucore inside the real integration
(`system_large` + `nec_bus` + the capture path) and it **MATCHES the chip's own
boot capture over 187 rows, 0 rows differ**, with the loop `CODE T1 @00100`
recurrence identical to silicon's.  That is the pre-flash gate, met.

## §51 U4 PASS 2 — §50's CAUSE IS **REFUTED BY MEASUREMENT**.  THE AREA WAS THE UNROLLED CHAIN, NOT THE ROM

**The headline: the EU went from 32,534 combinational cells to 12,400 with the
ROM read left exactly as it was, no cadence change, and every ladder number
unmoved.**  §50 read Quartus's `Info (276007) … uninferred due to asynchronous
read logic` as the CAUSE of the blow-up and routed U5-scale work — a registered
microcode ROM, which is a cadence change and therefore a re-derivation of the
whole campaign.  That inference was not measured, and it was wrong.

### §51.1 THE ATTRIBUTION, MEASURED FOUR WAYS

An `Info (276007)` says only *"this array did not become a block RAM."*  It says
nothing about what the array COSTS as logic.  Four `quartus_map` runs on the
same tool and device (17.1.0 Lite, `5CSEBA6U23I7`) answer that; the harness is
`v30u_eu` as its own top with virtual pins, whose baseline (**32,011** logic
cells) reproduces the in-design figure (**30,621** own) closely enough to
attribute with.

| what was measured | how | **logic cells** |
|---|---|---|
| `ucdecode` 8192×10 **and** `ucrom` 1028×29, chained, read asynchronously off a registered 15-bit `upc` — i.e. the exact shape §50 blamed | standalone module | **1,120** |
| the same two, in the design | `v30u_ucrom` own, map report | **1,026** |
| the three `pla3` case ROMs (3×256×14) | baseline − stubbed-`pla3` build (30,264) | **~1,750** |
| **ONE POSITION of the unrolled chain loop** | (17,224 @ `CHAIN_MAX=6` − 8,426 @ `CHAIN_MAX=2`) / 4 | **~2,200** |

`32,011 ≈ 4,000 base + 12 × 2,200`.  **The microcode tables are 3 % of the EU.
The chain loop is 82 % of it.**  The registered-ROM fallback would have bought
about a thousand cells for a cadence change; it is NOT taken, and
`v30u_ucrom.sv`'s header now carries the measurement so the next reader does
not re-derive it from the same `Info` line.

### §51.2 THE MECHANISM — TWELVE COPIES OF THE STEP CASE, ELEVEN OF THEM MOSTLY DEAD

`v30u_eu.sv`'s chain loop is *"how several model steps ride one clock"*: a
bounded `for (chain = 0; chain < 12; …) if (!stop) \`include
"v30u_eu_step.svh"`.  It is UNROLLED by construction — twelve full copies of a
33-arm case containing the whole datapath (`v30u_eu_row.svh`, `_wd1`, `_cond`,
`_1bl`).

But a state can only STAND at chain position ≥ 1 if some arm hands over to it
**without setting `stop`**, and reading the arms, only **nine** do:

```
S_TAKE_OPC  S_DECODE  S_DECODE2  S_EA_CALC  S_BIND
S_ENTER     S_TAIL    S_TAIL_POP S_INSTR_END
```

Every other predecessor stops.  `S_ROW` — the largest arm in the file — is
entered only from `S_ENTER`, `S_ROW_CHG`, `S_RLOOP`, `S_IRQ_D` and `S_RESET`,
and all five set `stop`.  `S_DECODE2` sets `stop` on every path, which makes
`S_MODRM`, `S_NORM_CHG`, `S_HALTED`, `S_1BL_LEAD` and `S_1BL_CHG`
position-0-only.  `S_BIND`'s `if (st != S_ENTER) stop = 1'b1` does the same for
`S_PRERD` and `S_GRPD_CHG`.  And so on for all 24.

**Argued from the transition graph AND measured.**  A `(position, state)` census
instrumented into the chain and run over the golden suite (347 forms × 12) plus
the boot march saw:

| chain position | distinct states seen |
|---|---|
| 0 | 24 |
| 1 | **9** — exactly the nine above |
| 2 | 5 |
| 3 | 3 |
| 4 | 2 |
| 5 | 1 |

and a maximum chain depth of **6**.  The nine observed at position ≥ 1 are
exactly the nine the transition graph predicts — the census did not add a state
the argument missed, and the argument did not permit one the census never saw.

So the 24 arms now open with `if (chain == 4'd0)`, the unroll folds them out of
eleven of the twelve copies, and **`CHAIN_MAX` stays at 12** — the bound is not
tightened, so no new corpus-scoped claim is made about chain depth.

### §51.3 THE TWO FALSIFIERS, BOTH NEW, AND THE TRAP THAT MADE ONE NECESSARY

1. **`CHAIN OVERFLOW`** — the loop now `$fatal`s if it ends with `stop` still
   low.  That fires if a folded state ever stands at position ≥ 1 (the folded
   copy assigns nothing, so `stop` cannot rise), and it fires equally if the
   chain ever genuinely needs more than `CHAIN_MAX` steps.  The bound was a
   silent claim before this line: running out would have pushed the remainder
   into the NEXT clock — a cadence error, not a hang, and invisible.
2. **`st_zero_ok()`** — a fail-safe around the include that spends a clock
   rather than hanging if an impossible state ever did stand there in fabric,
   where there is no assertion.

**It is a FUNCTION and not a wire, and that is F11b's trap for the fourth time
in this campaign.**  `st` is written with BLOCKING assignments inside the chain,
so a `wire st_zero_ok = (st == …)` carries the PRE-EDGE state — it asks about
position 0's state at position 1.  Written that way it scored **392/4,164** on
the golden subset; as a function of the live value, 4,164/4,164.  The module
already warns about this trap three times and it still caught this change.

### §51.4 SYNTHESIS — GATE G6, RE-RUN

| gate (§45.4 item 3) | registered expectation | pass 1 | **pass 2** | |
|---|---|---|---|---|
| Analysis & Synthesis errors | 0 | 0 | **0** | ✅ |
| `quartus_map` wall | ~4 min band | 12:53 | **3:24** | ✅ |
| `v30_core` combinational cells | (FSM: 12,257) | 32,534 | **12,400** | ✅ |
| `v30u_eu` own | (FSM `v30_eu`: 11,315) | 30,621 | **10,481** | ✅ |
| `v30u_biu` own | (FSM: 781) | 883 | **872** | — |
| whole design, logic cells | (FSM: 37,222) | 37,222¹ | **19,469** | ✅ |
| zero `lpm_divide` | 0 | 0 | **0** | ✅ (the FSM core instantiates two) |
| zero inferred latches | 0 | 0 | **0** | ✅ |
| `Warning (10230)` truncations | — | 9,220 | **1,028** | §50.4 item 2, part-fixed |

¹ pass 1's whole-design figure is the same 37,222 because the fitter never ran;
the A&S total is what is being compared.

**The microcode tables are still LUT logic and still `Info (276007)`, ON
PURPOSE** — that is §51.1's measurement, not an oversight, and `ucdecode` is
now declared `[11:0]` so its 8,192 truncation warnings no longer bury the log
(§50.4 item 2).  §50.4 item 1 — the comment Quartus parsed as a `synthesis`
pragma — is fixed, and the hazard is written down where the comment was.

### §51.5 THE FULL LADDER, RE-SCORED ON THE FOLDED RTL — ZERO DELTAS

Everything below was run on ONE binary built from commit `5dce53a1a7`.

| gate | standing | **pass 2** |
|---|---|---|
| **G3** `check_core --core ucore --opcodes all --cases 0` | 169,000 | **169,000/169,000** |
| `v0.1-w1` / `-w3` | 1,200 / 1,200 | **1,200 / 1,200** |
| `v0.1-w1 --opcodes EB` | 200 | **200/200** |
| `w0evt` / `w1evt` / `w2evt` / `w3evt` | 200 / 1,200 / 200 / 1,200 | **200 / 1,200 / 200 / 1,200** |
| `v0.1-w1evt-biased` | 1,200 | **1,200/1,200** |
| HLT sweeps `s10-w{0,1}`, `s13-w{2,3}` | 90/97, 88/95, 37/46, 34/45 | **90/97, 88/95, 37/46, 34/45** |
| `check_boot --core ucore` 220 / 400 | MATCH / MATCH | **MATCH / MATCH** |
| `ulockstep --suite --waits 0,1,2,3` | ALL LOCKSTEP | **ALL LOCKSTEP** |
| `ulockstep --golden all --cases 50` | 17,350 | **17,350/17,350** |
| `timed_wvec_gate --core ucore` | 88/88, +0.0 % | **88/88, 16,048 vs 16,048, +0.0 %** |
| `timed_enter_replay --core ucore` | 154/154 ×5 | **154/154 ×5** |
| `timed_ins_replay --core ucore --raw` | 1,312 / 2,624 | **1,312/1,312 and 2,624/2,624** |
| `timed_fuzz --core ucore --evt-replay` REGISTERED | 1,483/1,702 | **1,483/1,702 (87.1 %)** |
| … EVT / COMBINED | 192/1,008 · 1,675/2,710 | **192/1,008 · 1,675/2,710** |
| … `BOUND WARNINGS` / `ENGINE ABORTS` | 5 / 0 | **5 / 0** |
| `timed_fuzz --seeddir …/b2-tranche/seeds` | 171/188 | **171/188 (91.0 %)** |
| `ss_lint --core ucore` | rc=0, 223 flops, 0 UNMAPPED | **rc=0, 223 flops, 0 UNMAPPED** |
| `check_ab_sim --core ucore` | 187 rows MATCH | **187 rows MATCH** |
| `gen_ucore_qsf --check` | up to date | **up to date** |
| G0 `check_ucore_tables` | 9,988 | **9,988 PASS** |

**Every cell, and the fuzz denominators (2,710 scored / 532 `OPEN_BUS`; 188 /
28) with them.**  That is the intended result: folding a provably unreachable
arm out of an unrolled loop is a synthesis-shape change and nothing else, and
the ladder is the instrument that says so rather than the argument.

### §51.6 GATE G6 — **THE FIT PASSES AND THE TIMING DOES NOT.**  NOTHING WAS FLASHED

`quartus_sh --flow compile nec_test -c nec_test_ucore`, 17.1.0 Lite,
`5CSEBA6U23I7`, wall 25:00 (A&S 3:24, Fitter 20:03, Assembler 0:13).

| gate | registered expectation | pass 1 | **pass 2** | |
|---|---|---|---|---|
| A&S errors | 0 | 0 | **0** | ✅ |
| Fitter | a `.sof` | **`Error (11802) Can't fit`** | **Successful, 0 errors** | ✅ |
| ALMs | FSM = 25 % | 67 % (unfitted) | **12,272 / 41,910 = 29 %** | ✅ |
| routing congestion | — | the failure | **none; routing 6:02** | ✅ |
| `lpm_divide` / latches | 0 / 0 | 0 / 0 | **0 / 0** | ✅ |
| bitstream | a `.sof` | none | **`nec_test_ucore.sof` sha256 `eaf8cd89f6545ee6c279481d7a81fc3c059bc05bc626ef3f90e8bdfd85ec93ce`**, `.rbf` `b184e940ee…` | ✅ |
| **Fmax >= 32 MHz with margin** | >= 32 MHz | NOT MEASURED | **13.99 MHz.  Setup slack −40.233 ns, TNS −46,794** | ❌ |

**THE REGISTERED TIMING BAR IS NOT MET AND THE FABRIC HALF STOPS HERE.  No
bitstream was loaded; the FSM baseline on the board is untouched
(`nec_test.sof 1cc4bf55…`, `nec_test.rbf 2643d8ce…`, re-verified after the
compile).**

### §51.7 WHY IT IS A REAL VIOLATION AND NOT A MISSING EXCEPTION — THE THING THAT WAS TRIED, AND WHY IT WAS TAKEN BACK OUT

The obvious reading is that this is a CONSTRAINT gap.  `nec_bus` divides the
32 MHz sys clock down to the CPU clock — `cfg_clk_div` sys clocks per CPU
cycle, *"even, >= 4"*, and 8 at the divider of record — so the core advances on
one sys clock in eight, and a core register-to-register path ought to have
250 ns rather than 31.25 ns.  `nec_test.sdc` carries no `set_multicycle_path`,
so TimeQuest analyses every one of them as single-cycle.

**A multicycle exception was written, applied, and MEASURED — and it does not
close the design.**

| SDC | worst setup slack | worst path |
|---|---|---|
| as committed (no exception) | **−40.233** | `v30u_eu\|upc_opc[1]` -> `v30u_eu\|m_kind[0]` |
| `-from`/`-to` the EU's registers, `-setup 4` | −30.923 | `v30u_biu\|r_q_cnt[3]` -> `v30u_eu\|m_kind[0]` |
| `-from`/`-to` the whole core, `-setup 4` | **−28.510** | **`nec_bus\|div_cnt[1]`** -> `v30u_eu\|m_kind[0]` |

The residue names the mechanism, and `report_timing -detail full_path` on it is
the measurement that ends the argument:

```
From Node   nec_bus:bus|div_cnt[1]
To Node     …|v30u_eu:u_eu|m_kind[0]~DUPLICATE      (the FF's DATA input)
Data Delay  59.111 ns      Number of Logic Levels  61
```

**`ce` is threaded through the EU's 61-level combinational cone, not presented
at the registers' ENABLE port.**  The path terminates on `datac`/`dataf` LUT
inputs — there is no `ena` node anywhere in it.  So the EU's state registers
are clocked EVERY sys clock and hold by re-selecting themselves in the
datapath; the "core only advances on CE" structure is true of the RTL and false
of the netlist Quartus built from it.

That is decisive twice over:

1. **The violation is real.**  `div_cnt` changes every sys clock, so `ce`
   settles only 31.25 ns before the capturing edge and 59.1 ns of logic hangs
   off it.  The register never sees a settled `D`.
2. **The exception is invalid.**  Its own registered falsifier — *"any core
   register written from another core register OUTSIDE the `ce` branch"* — is
   met by EVERY core register, because the tool did not extract the enable.
   The SDC change was therefore **reverted**, `nec_test.sdc` is byte-identical
   to HEAD, and the −40.233 ns above is the number that stands.

**The fix is structural and it is the same one shape §50 reached for by a
different road.**  Put the chain in an `always_comb` producing `_n` values and
commit them with `always_ff @(posedge clk) if (ce) <state> <= <state>_n;`.
That places `ce` on the enable port, at which point the 61-level cone becomes a
genuine multicycle-4 path, the exception in this section becomes TRUE, and —
as a free consequence — `upc_n` exists as a wire, which is the only thing a
registered microcode ROM ever needed.  It is a large, reviewable change to the
campaign's most delicate file and it is **NOT started here**: this pass's
instruction is to report and stop rather than operate unreviewed.

*Falsifier for §51.7*: an `ena` pin on a `v30u_eu` state register in the
post-fit netlist — that would mean the enable WAS extracted, and the div_cnt
path is then something else.

### §51.8 THE PRIORITY TRANCHE — FROZEN, AND THREE OF ITS FOUR LEGS TAKEN

§48.4's gate needs four legs.  Three of them need no bitstream, and they were
taken; the fourth is the ucore in fabric and it does not exist.

**Frozen first.**  `sw/u4_tranche.py freeze` -> 200 seeds, 40 each at
`wmax` 1/2/3/7/15, `cid mc1` from `k=300000`, no `evt` directive, every image's
sha256 recorded; manifest sha256
`92e3de085bdfdf3063299c6985decbb7152d1be66d99a546871326b065e29167`, committed
in `758d9c1b42` **before** the first capture and before any flash.

| leg | what it is | cycle-exact vs the chip |
|---|---|---|
| `chip` | the socketed V30, `use_core=0` | (the reference) |
| **`vsim_ucore`** | the ucore under Verilator | **176/178 — 98.9 %** |
| `fsmcore` | the FSM core in fabric, `use_core=1`, on the **already-flashed** bitstream | 163/178 — 91.6 % |
| `vsim_fsm` | the FSM core under Verilator | 59/178 — 33.1 % |
| `core` | **the ucore in fabric** | **NOT TAKEN — §51.6** |

Denominators identical on every leg by construction (the `OPEN_BUS` excuse is
computed from the CHIP capture, once, and applied to all of them): 178 scored,
22 excused.  Comparison windows are real — median 1,274 rows, p10 934, max
4,000.  V0 holds: 0 hard failures, 0 transport errors in 800 captures, the
divider PINNED on every one, full per-clock rows plus a `SHA256SUMS` over all
800 files retained.

**Two findings fall out of the legs that do not need a bitstream.**

**(a) A FRESH random-wait population is EASIER than the banked one, so V1's
85 % bar is soft and V4 is the gate that discriminates.**  The banks were built
from seeds where the model already diverged — they are adversarially selected —
and V1 was set at 85 % *"below the banked tranche's 89.4 % because fresh seeds
are not cherry-picked."*  Measured, the direction is the opposite: the FROZEN
core scores **91.6 %** on this fresh population and **18/1,702** on the banked
one.  V1 as registered would be cleared by a core that is barely better than
the one this campaign is replacing.  Recorded as a defect in the
pre-registration, not corrected after the fact.

**(b) THE FLASHED FSM BITSTREAM AND THE FSM RTL AT HEAD ARE NOT THE SAME
MACHINE — 62/178.**  Scored directly against each other on the same seeds,
`fsmcore` (fabric) and `vsim_fsm` (Verilator) agree on only **62 of 178**
(`bs` 81, `qs` 35), and the fabric leg is the one that is CLOSER to silicon
(91.6 % vs 33.1 %).  This is V3's shape — *"a FABRIC-vs-SIM finding, and the
MORE important result if it happens"* — but on the FSM core, not the ucore.
Its consequence for the campaign is procedural: **the FSM leg of the
two-bitstream A/B must be a bitstream built from the SAME HEAD as the ucore's**,
or the A/B compares the ucore against an unidentified artifact.  Task #31's
standing flash debt is the likely cause and is NOT superseded — nothing was
flashed.

**What the taken legs already say about the ucore**, with the fabric leg
missing and therefore claiming nothing about fabric: on 178 fresh random-wait
programs the ucore under Verilator reproduces the socketed chip cycle for cycle
on **176**, residue **2 seeds, both `bs`, 0 unclassified** (V5's taxonomy, met),
against the frozen FSM core's 59.  That is the sim-side half of the victory
condition; the fabric half is unrun for a second stage.

### §51.9 GATE LEDGER AND U5 HANDOFF

| gate | verdict |
|---|---|
| the full sim ladder (§51.5) | **GREEN, zero deltas** |
| G6 A&S / fit / area / bitstream | **GREEN** — 29 % ALMs, `.sof` produced |
| **G6 Fmax** | **RED — 13.99 MHz against a registered >= 32 MHz** |
| §48.1 `check_ab_sim --core ucore` | GREEN, 187 rows |
| §48.2 flash #1 | **NOT RUN** — no timing-clean bitstream |
| §48.3 F42's 17 cells | **UNSCORED** — still a live registered prediction |
| §48.4 priority tranche | **FROZEN + 3 of 4 legs**; the fabric leg unrun |
| FSM-vs-ucore two-bitstream A/B | **NOT RUN**; task #31's flash debt NOT superseded |

**U5 picks up, in this order:**

1. **The enable-form refactor of `v30u_eu` (§51.7).**  `always_comb` -> `_n`,
   `always_ff if (ce)` commit.  It is the one change that makes the 61-level
   cone legal, and it makes `upc_n` a wire for free.  The sim ladder must be
   re-scored on it — but note it is a *structural* change, not a cadence one,
   so the expectation is again zero deltas, and the ladder is the instrument
   that says so.
2. Then re-run G6 **with** §51.7's multicycle exception, which becomes true at
   that point, and require **Fmax >= 32 MHz with margin** before any flash.
3. Then §48.2 / §48.3 / §48.4's fabric leg, unchanged — the tranche is already
   frozen and its chip leg already captured, so the fabric leg is one command.
4. **Build the FSM A/B bitstream from the same HEAD** (§51.8b) before scoring
   V4, and re-register V1 against a fresh-population baseline (§51.8a).
5. `sw/u4_f42_fabric.py` is written and committed and needs only a bitstream.

## §52 U4 PASS 3 — THE ENABLE FORM CLOSES G6, THE ucore RUNS IN SILICON, AND THE PRIORITY GATE IS MET 176/178

**Headline: the campaign's victory condition is met.**  On 178 scored fresh
random-wait programs the ucore INSIDE THE FPGA reproduces the socketed V30
cycle for cycle on **176**, against **59** for the FSM core built from the same
HEAD — and the fabric leg and the Verilator leg agree **row for row on all 200
seeds**, for both cores.  Getting there took two structural changes, not one:
§51.7's enable-form refactor was necessary and NOT sufficient.

### §52.1 THE ENABLE-FORM REFACTOR — DONE, AND THE LADDER DID NOT MOVE

§51.9 item 1, executed.  Both core modules are now a NEXT-STATE FUNCTION plus a
REGISTER BANK:

| | before | after |
|---|---|---|
| `v30u_eu` | one `always @(posedge clk)`, blocking `=`, third arm `else if (ce)` | `always @*` -> `<reg>_n` (117 of them) + `always_ff @(posedge clk) if (ss_we\|\|srst\|\|ce)` |
| `v30u_biu` | `always_comb` + unconditional `always_ff`, `ce` inside the comb | the same `always_comb`, `ce` moved to the bank (two lines) |

**The EU's flops KEEP THEIR NAMES and the BODY was renamed**, not the other way
round.  That is the whole reason the change is inert: every module-level wire
still reads the REGISTER, i.e. the pre-edge view this module is built on (F11b,
and the convention the recognition block states in so many words), so no
combinational reader changes what it sees.  Inside the body, `_n` is exactly
what a blocking write to the register meant.  Derived by measurement, not by
reading: the flop set is *"every module-level `reg` declared in the STATE
region that the clocked body assigns"* = 117, and after the rewrite the body
contains **zero** bare flop references outside the 117 preload lines.

**The simulation-only side effects had to move**, and that is the one part that
is not a rename.  A combinational block fires them once per SETTLE, not once
per clock, and `sw/uscope.py`'s contract is *one `+eutrace` line == one CE
clock*.  The two completed-read SVAs, the eutrace line, the CHAIN OVERFLOW
`$fatal` + depth tracker and `v30u_eu_poste.svh`'s two shape `$error`s now live
in a CLOCKED OBSERVER; the flop-valued fields the trace read MID-EDGE are
snapshotted by comb `trc_*` at exactly that point.  `v30u_biu` already had this
shape and says why in its own contract block — *"the `always_comb` above settles
more than once per clock, so an immediate assertion inside it would report
transients"* — so the precedent was in the file.

**THE LADDER, RE-SCORED THREE TIMES (EU alone; EU+BIU; EU+BIU+reset) — ZERO
DELTAS.**  All 26 gate logs byte-identical to the pre-refactor run, with one
exception named below.  G3 169,000/169,000 · w1/w3 1,200 · EB 200 · the four evt
cells 200/1,200/200/1,200 · w1evt-biased 1,200 · HLT sweeps 90/97, 88/95, 37/46,
34/45 · boot 220 and 400 MATCH · ulockstep suite ALL and golden 17,350/17,350 ·
wvec 88/88 16,048 vs 16,048 +0.0 % · enter_replay 154/154 x5 · ins_replay
1,312/1,312 and 2,624/2,624 · check_ab_sim 187 rows · fuzz REGISTERED 1,483/1,702,
EVT 192/1,008, COMBINED 1,675/2,710, BOUND WARNINGS 5, denominators 2,710/532 ·
tranche 171/188 with 188/28 · G0 9,988 · `gen_ucore_qsf --check` up to date.
Plus the enable form's own falsifier, which the harness already had:
**`--ce-div 4 --ce-hold-check` reports `CE_HOLD_VIOL 0` on all 347 forms** and
694/694 cases, i.e. the state provably freezes on CE-low clocks.

**The one moved cell is an INSTRUMENT GAIN.**  `ss_flopcensus`'s EU
architectural-flop count falls 140 -> 118 and the whole census 223 -> 201,
because **22 of the 24 ucore whitelist entries are discharged BY CONSTRUCTION**.
U3 booked that file as *"A WORKAROUND FOR A DECLARATION, NOT A DESIGN
DECISION — SystemVerilog lets these be declared INSIDE the always block, which
would remove them from the census by construction"*, and left it because the RTL
was frozen; the refactor did the equivalent as a side effect, so `stop`,
`ie_now`, `v1`, `v2`, `bsw`, `pv`, `nloc`, `carry`, `taken`, `bubble`,
`retire_now`, `rep_chained`, `ea`, `rseg`, `rmmod`, `rmreg`, `rmrm`, `tk`, `ti`,
`te`, `ts` and `tb` are combinational by declaration now.  **The MAP is
untouched: SS_COUNT 218, SS_TAG 0x82DA, 0 UNMAPPED, `ss_lint` rc=0.**  The two
survivors (`tsel`, `ending`) are real flops and keep their old justifications.

### §52.2 …AND IT WAS NOT ENOUGH.  THE FIRST FIT SAID SO, AND NAMED THE RESIDUE

`quartus_sh --flow compile`, 17.1.0 Lite, `5CSEBA6U23I7`, with §51.7's
multicycle written into `nec_test.sdc` (4/3, guarded so the FSM revision sees an
empty collection):

| | pass 2 | **enable form only** |
|---|---|---|
| `v30_core` A&S cells | 12,400 | **11,577** |
| ALMs | 12,272 / 29 % | **11,086 / 26 %** |
| registers | 7,135 | **6,048** |
| setup slack | −40.233 | **−20.027** |
| TNS | −46,795 | **−12,979** |

Better on every axis and **still RED**.  §51.7's own falsifier had been answered
in the affirmative — the enable WAS extracted — so the question was which paths
were left, and that is a countable question.  Every violating path in the whole
design, enumerated:

```
  -20.027  n=5733  emu|system_large|c_reset_q
  -19.781  n=267   emu|system_large|hps_axi_slave|cfg_use_core
```

**Two launch nodes, and `system_large.sv:372` says they are ONE signal:**
`wire core_reset = c_reset_q | ~cfg_use_core` — the core's `srst`.  Meanwhile
the core's own register-to-register cone, now covered by the exception, had
**+43.570 ns of slack** (`upc_opc[3]` -> `opc_base[4]`, 81.178 ns of data delay
against a 125 ns requirement).  The design was not slow; one signal was in the
wrong place.

### §52.3 `srst` WAS THE SAME MISTAKE AS `ce`, AND THE SAME MEDICINE FIXED IT

`srst` was an ARM of the same next-state function that computes the run value,
so it sat in the same expression tree as the twelve-position chain and the tool
distributed it through the whole cone — measured, `report_timing -detail
full_path`:

```
From  system_large|c_reset_q
  -> v30u_eu|wb_seg[0]~0 -> v30u_biu|grn_n~1 -> v30u_biu|q_ripe_lead_n~{1,2,4}
  -> v30u_eu|Mux338 … the EU's twelve chain positions … -> opc_base_n~45
To    v30u_eu|opc_base[4]        58.858 ns, latch edge 31.250 ns
```

and it could NOT be excepted, because it **launches outside the core**: no CE
multicycle reaches a path whose launch register is `system_large`'s.  (The path
also shows the BIU and the EU are ONE cone — `srst` enters the EU, comes back
out through the BIU's `q_ripe_lead_n` and re-enters the chain.  That is F7's
contract working as designed, and it is why both modules had to be treated.)

The fix is §51.7's, applied to `srst`: the reset arm is now its OWN
combinational function (`_r` in the EU, `_rst` in the BIU) whose cone is
constants, the pin levels and the backdoor, the run view is **provably
independent of `srst`**, and the register bank picks —
`if (ss_we || srst || ce)` with `D = (srst && !ss_we) ? reset : run`, which is
the original `ss_we > srst > ce` priority exactly.

### §52.4 GATE G6 — **GREEN, WITH MARGIN**

`quartus_sh --flow compile nec_test -c nec_test_ucore`, wall **9:20**.

| gate (§45.4 item 3 / §48) | registered | pass 2 | **pass 3** | |
|---|---|---|---|---|
| A&S errors | 0 | 0 | **0** | ✅ |
| Fitter | a `.sof` | Successful | **Successful, 0 errors** | ✅ |
| ALMs | FSM = 25 % | 12,272 / 29 % | **11,078 / 41,910 = 26 %** | ✅ |
| registers | — | 7,135 | **6,148** | — |
| M10K / RAM blocks | — | 105 | **105 / 553 = 19 %** | — |
| `lpm_divide` / latches | 0 / 0 | 0 / 0 | **0 / 0** | ✅ |
| **Fmax >= 32 MHz WITH MARGIN** | >= 32 MHz | 13.99 / 19.5 MHz | **45.56 MHz (+42 %)** | ✅ |
| worst setup slack | — | −40.233 / −20.027 | **+8.922 ns, TNS 0.000** | ✅ |
| worst hold | — | +0.252 | **+0.247 ns, TNS 0.000** | ✅ |
| map / fit wall | ~4 min band | 3:24 / 20:03 | **2:46 / 8:23** | ✅ |
| bitstream | a `.sof` | `eaf8cd89…` | **`.sof cdf5edee00bfccac6b0f22a08076fe0c3932917123f0327dd8c4114159ec156b`**, `.rbf 91697c83b3…` | ✅ |

**Every clock domain has TNS 0.000.**  The worst path on the CPU clock is
`nec_bus|div_cnt[3]` -> `v30u_biu|t1_half2`, 5.728 ns on a HALF-cycle (negedge)
relationship of 15.625 ns; the core's own reg-to-reg cone is the excepted
81.178 ns one at +43.570.

**§51.7's FALSIFIER, ANSWERED IN THE AFFIRMATIVE.**  It asked for *"an `ena` pin
on a `v30u_eu` state register in the post-fit netlist"*.  The Fitter's Control
Signals table now carries
`v30_core:u_core|v30u_biu:u_biu|always3~0 … 1078 … Clock enable`, plus 30 more
core clock-enable nets.  Before this work the WHOLE DESIGN had **one** "Clock
enable" fanout entry and it was a JTAG node.

*Standing falsifier for the SDC exception, written next to it in
`nec_test.sdc`*: a `v30u_eu` or `v30u_biu` state register with no clock-enable
input.  If one exists the exception is lying about that register.

### §52.5 FLASH #1, AND FIRST LIGHT — THE ucore RUNS IN SILICON

`sw/safe_flash.sh` with its VERIFY leg (MAGIC OK, `pwr_good`/`cpu_running`
true, ledger appended), single-writer checked first.

* **§48.2, taken FIRST: the chip-path proof.**  `use_core=0` boot vs the standing
  golden — **MATCH over 800 rows.**  The new bitstream did not disturb the chip
  path, which is what `gen_ucore_qsf --check` is supposed to make impossible and
  is now measured rather than assumed.
* **First light, the campaign-4 800/800 pattern, all three legs:**
  `chip-vs-golden` MATCH 800, `core-vs-chip` MATCH 800, `core-vs-golden` MATCH
  800.

### §52.6 THE STANDING PRIORITY GATE (§48.4) — **ALL SIX BARS MET**

The frozen tranche (manifest sha `92e3de08…`, committed in `758d9c1b42` before
any capture), its fourth and last leg taken:

| leg | what it is | cycle-exact vs the socket |
|---|---|---|
| **`core`** | **the ucore IN FABRIC** | **176/178 — 98.9 %** |
| `vsim_ucore` | the ucore under Verilator | 176/178 — 98.9 % |
| `fsmhead` | the FSM core in fabric, **rebuilt from the SAME HEAD** | 59/178 — 33.1 % |
| `vsim_fsm` | the FSM core under Verilator | 59/178 — 33.1 % |
| `fsmcore` | the FSM core in fabric, the STALE 2026-07-30 bitstream | 163/178 — 91.6 % |

| # | registered bar | measured | |
|---|---|---|---|
| V0 | 0 hard failures, div PINNED, full rows + sha | **0 errors in 483 tranche captures**, `div_guard` PINNED on every one | ✅ |
| V1 | fabric >= 85.0 % | **98.9 %** (soft, per §51.8a's own defect note) | ✅ |
| V2 | identical denominators | **178 scored / 22 excused on every leg** | ✅ |
| V3 | fabric within ±2 seeds of Verilator | **ZERO seeds apart, 176 vs 176** | ✅ |
| V4 | the ucore beats the FSM core | **176 vs 59** on the same HEAD | ✅ |
| V5 | residue in the taxonomy, 0 unclassified | **`bs`=2, 0 unclassified** | ✅ |

**V3 is the one worth naming.**  §48.4 called a fabric-vs-sim gap *"the MORE
important result if it happens"*.  It did not happen — and the stronger
statement is true: scored DIRECTLY against each other with the same window and
column policy, **`core` and `vsim_ucore` are identical on 200/200 seeds**, and
**`fsmhead` and `vsim_fsm` are identical on 200/200** as well.  The Verilator
model of each bitstream is exact on this population.

### §52.7 THE IN-SILICON A/B FUZZ — 500 FRESH SEEDS, AND V3 HOLDS AT THE BAR

A second population, frozen and committed (manifest sha `72afd71e…`,
commit `de7874ae89`) before its first capture: 500 seeds, 100 each at
`wmax` 1/2/3/7/15, `cid mc1` from a DISJOINT `k=400000`.  1,000 board captures,
**0 errors**.

| leg | cycle-exact |
|---|---|
| `core` (fabric) | **435/449 — 96.9 %**, residue `bs`=11 `qs`=3 |
| `vsim_ucore` | 433/449 — 96.4 %, residue `bs`=11 `qs`=3 `data`=2 |

Registered before capture: within ±3 points of the tranche's 98.9 % (**−2.0**,
met) and within ±2 SEEDS of Verilator (**2**, met at the bar).  At 5x the seeds
V3 is a real constraint rather than a formality — and **the FABRIC leg is the
better one**: the two seeds are `data` divergences the MODEL has and the
BITSTREAM does not.  A fabric-vs-sim finding in the direction that favours the
hardware, booked and not smoothed.

### §52.8 §51.8b CLOSED — IT WAS THE STALE BITSTREAM, AND TASK #31's DEBT IS DISCHARGED

§51.8b measured `fsmcore` (fabric) against `vsim_fsm` (Verilator) at **62/178**
and routed the consequence: *"the FSM leg of the two-bitstream A/B must be a
bitstream built from the SAME HEAD as the ucore's."*  Done — FLASH #2,
`nec_test.sof a4533dfef0…` / `.rbf 92e1c83f2d…` from HEAD `31e96121a5`
(25 % ALMs, setup +4.296 ns, TNS 0, 0 errors), chip-path re-proved MATCH 800 and
first light MATCH 800/800 on it as well.

Scored pairwise, same comparator:

```
fsmhead (fabric, HEAD) vs vsim_fsm (Verilator, HEAD):  200/200 IDENTICAL
core    (fabric)       vs vsim_ucore:                  200/200 IDENTICAL
fsmcore (the 2026-07-30 bitstream) vs vsim_fsm:         76/200
```

**The gap was entirely the stale bitstream.**  Task #31's standing flash debt is
**DISCHARGED** — both flashes in this session were built from HEAD, and the
`flash_log.jsonl` ledger now carries them.

**AND A NEW FINDING FALLS OUT, WHICH IS NOT THE ucore's.**  The 2026-07-30 FSM
bitstream scores **163/178** on this tranche and HEAD's FSM RTL scores
**59/178** — in fabric AND in Verilator, identically.  The FROZEN REFERENCE CORE
HAS REGRESSED BY 104 SEEDS ON THE RANDOM-WAIT AXIS somewhere between that build
and HEAD, and no standing gate sees it: the ladder runs `check_core --core fsm`
on four opcodes only, and the FSM's registered fuzz figure (18/1,702) is so low
that a further loss is invisible there.  Booked as an FSM-side finding for the
campaign owner; it is not diagnosed here and nothing was changed to chase it.
*Falsifier*: a bisect between the 2026-07-30 build and HEAD that does not move
this number.

### §52.9 §48.3 — F42 IS **REFUTED**

The prediction, registered before a bitstream existed: *"if the 17 uncountable
HLT cells really are the TESTBENCH's composed-AD drive mask and not the core,
then in fabric those cells must PASS… If any of the 17 fails in fabric, F42 is
REFUTED and the ucore owns those cells — that is the honest outcome and it is to
be reported as a refutation, not re-explained."*

**In fabric the four sweeps score 29/283, against 249/283 for the same core
under the TB.  The 17 are among the failures.  F42 IS REFUTED.**

The control that makes this a result and not a rig artefact: the SAME driver and
the SAME 49 cells through the SOCKET (`EMIT_USE_CORE=False`, `use_core=0`)
reproduce the golden **49/49**.  The measured signature, identical on
`HLT.RES` w0 `idx` 10 and 20 (the `idx` field is the pin delay `d` — §43.0):

```
row 3  HALT Ti   GOLD bus=0x2AD8A   CORE bus=0x0AD8A
row 4  HALT T1   GOLD bus=0x2AD8A   CORE bus=0x0AD8A
row 5  PASV T2   GOLD bus=0x2AD8A   CORE bus=0x29090  (back at the previous address)
```

Same low 16 bits, a different upper nibble, and the display dropped one row
early.  So the TB's composed-AD mask was **HIDING A REAL DIVERGENCE** rather
than manufacturing one — the opposite of what F42 claimed — and the 254 failures
are the band that mask used to cover.  §43.2's arithmetic (*"17 cells no
comparator on this TB can score"*) does not survive: those cells are scoreable
in fabric and the ucore misses them.  The 6 cells of F43 are unaffected by this
and remain as diagnosed.

### §52.10 GATE LEDGER AND U5 HANDOFF

| gate | verdict |
|---|---|
| the full sim ladder, §52.1 | **GREEN, zero deltas, three runs** |
| `--ce-div 4 --ce-hold-check` | **GREEN, `CE_HOLD_VIOL 0`, 694/694** |
| **G6 fit + Fmax** | **GREEN — 26 % ALMs, 45.56 MHz, TNS 0 on every domain** |
| §48.1 `check_ab_sim --core ucore` | GREEN, 187 rows |
| **§48.2 flash #1 + first light** | **GREEN — chip path MATCH 800, all three legs 800/800** |
| **§48.3 F42's 17 cells** | **REFUTED — 29/283 in fabric, socket control 49/49** |
| **§48.4 priority tranche, all four legs** | **GREEN — V0-V5 all met, 176/178** |
| in-silicon A/B fuzz, 500 fresh seeds | **GREEN — 435/449, V3 at the bar** |
| **FSM-vs-ucore two-bitstream A/B** | **GREEN — 176/178 vs 59/178 from the same HEAD** |
| task #31's flash debt | **DISCHARGED** |
| §48.5 evt_hold widen | **NOT TAKEN** — still §48.5's measured 12-bit drop-in, still a host-protocol change |

**Board left**: the FSM-from-HEAD bitstream (`a4533dfef0…`) is on the fabric, so
the harness is back in its chip-capture role with `use_core=0` proved MATCH 800
on it.  `board_idle` run and a 4,063-row idle capture taken afterwards to
confirm the board is not wedged.  Both flashes are in `sw/testdata/flash_log.jsonl`.

**U5 picks up, in this order:**

1. **F42's refutation is now an RTL item.**  The ucore drives the HALT display's
   upper nibble differently from silicon and drops it a row early; that is a
   named, measured, scoreable divergence in fabric and it is the ucore's.  It is
   also the last unexplained block on the HLT sweeps.
2. **The FSM core's 104-seed random-wait regression (§52.8).**  Not the ucore's,
   but it is the A/B's denominator and no gate sees it.  Bisect
   2026-07-30 -> HEAD.
3. **Re-register V1 against the fresh-population baseline** now that two of them
   exist (98.9 % and 96.9 %), per §51.8a's own defect note.
4. The `evt_hold` widen (§48.5) with the 12-bit packing already worked out, if
   the campaign owner wants the EVT ratchet re-registered.
5. The 2 `bs` seeds of the tranche residue and the 14 of the 500-seed one — the
   last of the ucore's own fabric residue, and the smallest it has ever been.

---

# STAGE U5 — CLOSURE

## §53 THE PRE-REGISTRATION FOR F42's REFUTATION FIX

Written and committed **before** the TB or the RTL is touched, so nothing below
can be tuned to a result.  §52.10 item 1 handed U5 an RTL item: *"the ucore
drives the HALT display's upper nibble differently from silicon and drops it a
row early; that is a named, measured, scoreable divergence in fabric and it is
the ucore's."*

### §53.1 THE MEASUREMENT THAT DEFINES THE ITEM (fabric, already on disk)

`sw/testdata/u4-f42/`, the U4 pass-3 capture, `HLT.RES` w0 `idx 10`
(the `idx` field is the pin delay `d` — §43.0's numbering trap):

| row | tstate/bs | GOLDEN `bus` / `data` | uCORE IN FABRIC |
|---|---|---|---|
| 3 | Ti HALT | `0x2AD8A` / `AD8A` | **`0x0AD8A`** / `AD8A` |
| 4 | T1 HALT | `0x2AD8A` / `AD8A` | **`0x0AD8A`** / `AD8A` |
| 5 | T2 PASV | `0x2AD8A` / `AD8A` | **`0x29090`** / **`9090`** |
| 6 | T3 PASV | `0x2AD8A` / `AD8A` | **`0x29090`** / **`9090`** |

TWO defects, not one.  (a) the upper nibble: the ucore leaves A19-16 UNDRIVEN
across the HALT display and its T1 (`halt_pin` gates both `ad_oe_addr` and
`ad_oe_ps` off and publishes through `ad_oe_data` alone), where the part drives
**a LIVE PS** — M10, and `sim/biu_timed.cpp::note_halt`'s
`acc.addr = (data_ps(2) << 16) | last_fetch_addr`.  (b) the low lane: from T2
the ucore lets AD15-0 go, where the part still shows the announced address.
The SIM reproduces the golden on all four rows exactly
(`timed_gate --sbs HLT.RES:10`, row-diffs 0).

### §53.2 THE MECHANISM, STATED BEFORE THE FIX IS WRITTEN

**The HALT pseudo-cycle has no data phase.**  Every other cycle hands AD15-0
over at the end of T1 — to the write data (`t1_half2`) or to the memory — and
`halt_pin` was written as though a HALT did the same, on the DATA path, with
the upper nibble dropped.  A HALT hands the bus to nobody, so the announced
address is never taken away from it: **the address drive stands for the whole
pseudo-cycle**, upper nibble included, and the upper nibble is `data_ps(2)`
because that is what `note_halt` puts in the access's `addr` (M10).  One term,
no new state, and F41's `!st_rel` term is subsumed — a woken DISPLAY landing
inside the HALT still wins, because `display` precedes it in the pin mux.

### §53.3 THE INSTRUMENT — AND IT HIDES THE SAME DEFECT IN **BOTH** CORES

`hdl/tb/tb_v30_core.sv`:

```
wire drive_hi_a = (com_phase && BS != 3'b011) || (tb_t == ST_T1 && lat_type != 3'b011);
```

`3'b011` is HALT, so on a HALT display and its T1 the composer substitutes
`hold` for A19-16 **whatever the core drives**.  It has always given the right
answer for a reason that is not luck and is not correctness: the retained
nibble is the PREVIOUS cycle's PS, and the previous cycle is a CS fetch with
the same IE, so `hold[19:16] == data_ps(2)` by construction.  Measured over the
committed goldens, the HALT display's upper nibble is **`6` in all 200
`HLT.INT`, `2` in all 200 `HLT.RES`, and `{2,6}` in `HLT.NMI`** — i.e.
`{md, ie, CS}` and NEVER `0`.  Both cores drive `0`/nothing there:
`v30u_biu.sv:583` `{4'h0, r_last_fetch_addr}`, and the FROZEN FSM core's
`v30_biu.sv:1914` `{4'h0, fetch_phys[15:0] - 16'd2}` with `ad_oe_ps` explicitly
excluding `cur_kind != K_HALT`.

The mask is removed for the address phase — `drive_hi_a = com_phase ||
(tb_t == ST_T1)` — which is engine-neutral by construction (it names no core
signal) and is U3 open item 1 discharged with the pre-registered before/after
on BOTH cores that §45.3 required.

### §53.4 THE BARS, REGISTERED

Baselines on the clean-HEAD binaries (`fsm` sha256 `f177d0f67d…`, `ucore`
`2e9e0f6404…`, both rebuilt from HEAD and bit-identical to the tree's):

| leg | `s10-w0` | `s10-w1` | `s13-w2` | `s13-w3` | total |
|---|---|---|---|---|---|
| the MODEL | 91/97 | 95/95 | 44/46 | 42/45 | **272/283** |
| **ucore**, TB as committed | 90/97 | 88/95 | 37/46 | 34/45 | **249/283** |
| **FSM**, TB as committed (FIRST MEASUREMENT) | 86/97 | 80/95 | 27/46 | 23/45 | **216/283** |

1. **With the mask removed and NO RTL fix**: both cores lose every HLT cell
   whose HALT display is scored — `check_core --opcodes all` (v0.1) falls by
   the 600 `HLT.INT`/`HLT.RES`/`HLT.NMI` cases to **168,400** on BOTH cores,
   and both sweep totals fall.  *If either core does NOT fall, §53.3's reading
   of the mask is wrong and the fix is not yet justified.*
2. **With the mask removed AND the ucore fixed**: `check_core --core ucore
   --opcodes all --cases 0` is **169,000/169,000** again and the four sweeps
   are **at or above 249/283**.  *If v0.1 does not return to 169,000 the fix is
   incomplete and is not landed.*
3. **The FSM core is NOT fixed** — this campaign does not touch the frozen
   core's RTL (the flashed FSM A/B bitstream is built from HEAD and must stay
   that way, §52.8).  Its post-mask numbers are recorded as a **finding routed
   to the campaign owner with the disposition decision**, not as a regression
   this stage created: the defect predates the instrument change by every
   commit in the repo.
4. **The whole ucore ladder is re-scored** and the expectation is **zero
   deltas** outside the HLT cells: G3, `w1`/`w3`, `EB`, the four `evt` cells,
   `w1evt-biased`, boot 220/400, both lockstep legs, wvec, ENTER, INS, the fuzz
   bank and the b2 tranche.  A move anywhere else falsifies "one term, no new
   state".
5. **What this gate CANNOT see, stated in advance**: defect (b), the low lane
   from T2.  The TB retains AD15-0 across a HALT-typed cycle
   (`cycle_live` excludes HALT), so rows 5/6 are scored from `hold` and read
   correct whether the core drives them or not.  **Defect (b) is verifiable
   only in fabric.**  It is fixed by the same one term and its offline evidence
   is the `+padtrace` enable pattern, not a scored cell.

## §54 THE RESULT — F51, AND THE INSTRUMENT THAT HID IT IN BOTH CORES

### F51 — THE HALT PSEUDO-CYCLE HAS NO DATA PHASE

**Class: RTL BUG (a mechanism rendered half) — §16's named class one last time,
and F41's shape exactly.  LANDED.**

`halt_pin` rendered the HALT as though it DID have a data phase: it published
`{4'h0, r_last_fetch_addr}` through `ad_oe_data` with BOTH address enables gated
off.  Two consequences, both measured in fabric (§53.1):

* **A19-16 was UNDRIVEN** across the HALT display and its T1, where the part
  drives a LIVE PS — M10, and `note_halt`'s
  `acc.addr = (data_ps(2) << 16) | last_fetch_addr`.  Golden `0x2AD8A`, ucore
  `0x0AD8A`.
* **AD15-0 was LET GO at the status release**, where the golden still shows the
  announced address at T2/T3.  Golden `0x2AD8A`, ucore `0x29090` — the fabric's
  internal `core_ad` tri-state has no pad retention, so a value the part
  *holds* has to be *driven*.

The fix is the mechanism sentence and one wire:

```systemverilog
wire halt_hold = r_run && r_cur_halt;   // no data phase: nothing takes AD away
```

placed in the ORDINARY address path (`ad_o`'s `display` arm still precedes it,
so **F41's `!st_rel` term is subsumed, not dropped** — a woken fetch whose
display lands inside the pseudo-cycle still publishes).  `ad_oe_data`'s
`|| halt_pin` and `ad_oe_ps`'s / `ad_oe_addr`'s `!halt_pin` all disappear with
it: one term REPLACED three exceptions.

*Falsifier*: a HALT pseudo-cycle whose announced address is not on AD for its
whole duration, or any clock inside one on which the part drives a status
nibble rather than A19-16.

### §54.1 THE INSTRUMENT — AND WHY IT HAD ALWAYS READ CORRECT

`tb_v30_core.sv`'s `drive_hi_a` substituted `hold` for A19-16 across a HALT
display and its T1 whatever the core drove, and `com_phase` refused a display at
a HALT-typed cycle's T2/T3/Tw although the goldens carry a full 20-bit address
there (`s10-hltsweep-w0 HLT.RES idx 5` golden row 6: `9ad8c SS ad8c CODE T3`).

**The first mask read correct by construction and not by correctness.**  The
retained nibble is the previous cycle's PS; the previous cycle is a CS fetch
with the same IE; so `hold[19:16] == data_ps(2)` identically.  Measured over the
committed goldens the HALT display's upper nibble is **`6` in all 200
`HLT.INT`, `2` in all 200 `HLT.RES`, `{2,6}` in `HLT.NMI`** — and never `0`,
which is what both cores drove.  In FABRIC there is no retention, which is why
§52.9 saw it and no offline gate ever had.

Both terms removed.  Engine-neutral by construction: neither names a core
signal.  **This discharges U3 open item 1** (§45.3) with the pre-registered
before/after on BOTH cores that it demanded.

### §54.2 THE BARS OF §53.4, SCORED

| # | registered | measured | |
|---|---|---|---|
| 1 | mask off, no RTL fix: BOTH cores fall by the 600 v0.1 HLT cases | **ucore 0/600, FSM 0/600**, `exp 0x28D1E got 0x08D1E` — the upper nibble, 2 → 0; v0.1 **168,400/169,000** on both | ✅ exactly |
| 2 | mask off + fix: G3 back to 169,000, sweeps ≥ 249/283 | **169,000 / 169,000**; sweeps **91/97, 90/95, 40/46, 38/45 = 259/283** | ✅ |
| 3 | the FSM core NOT fixed; its numbers routed, not called a regression this stage created | FSM v0.1 **168,400/169,000**, sweeps **0/97, 4/95, 5/46, 7/45 = 16/283** | recorded |
| 4 | zero deltas everywhere else | see §54.4 — **every cell** | ✅ |
| 5 | defect (b) is offline-INVISIBLE (the TB retains AD15-0 across a HALT-typed cycle) and is fabric-only | stated in advance; unchanged | — |

### §54.3 THE HLT SWEEPS NOW — AND THE ucore-ONLY RESIDUE IS 13, NOT 23

Per case, both legs, in ONE numbering (the `idx` FIELD is the pin delay `d`,
§43.0's trap):

| sweep | model | ucore, entry | **ucore, after F51 + the honest mask** |
|---|---|---|---|
| `s10-hltsweep-w0` | 91/97 | 90/97 | **91/97 — ON the model** |
| `s10-hltsweep-w1` | 95/95 | 88/95 | **90/95** |
| `s13-hltsweep-w2` | 44/46 | 37/46 | **40/46** |
| `s13-hltsweep-w3` | 42/45 | 34/45 | **38/45** |
| **total** | **272/283** | 249/283 | **259/283** |

The model's 11 failures remain a **strict subset** of the ucore's 24, and **at
w0 the two failing sets are now IDENTICAL** — `HLT.INT` d ∈ {2,3,4,5},
`HLT.RES` d ∈ {2,3} on both legs.  The 13 ucore-only cells are:

| sweep | ucore-only failing `idx` |
|---|---|
| `s10-w1` | `HLT.INT` 7,8,9,10 · `HLT.RES` 7 |
| `s13-w2` | `HLT.INT` 9,12,13 · `HLT.RES` 9 |
| `s13-w3` | `HLT.INT` 11,15,16 · `HLT.RES` 11 |

The `busstat`-first half is **F43**, still diagnosed and still not landed for
§43's own stated reason (it touches the BIU's eval instant, the module's spine,
at a closure).  The `seg`/`bus`-first half is residue the corrected instrument
NEWLY EXPOSES and is **NOT diagnosed** — booked, with a falsifier, rather than
absorbed into F43's count.  §43.2's arithmetic ("17 cells no comparator on this
TB can score") is retired: those cells are scoreable now, and 10 of them pass.

### §54.4 THE FULL LADDER, RE-SCORED ON THE FIXED RTL — ZERO DELTAS

One rebuild of each binary from the committed tree; every cell re-run, not
inherited.

| gate | standing | **U5** |
|---|---|---|
| **G3** `check_core --core ucore --opcodes all --cases 0` | 169,000 | **169,000 / 169,000** |
| `v0.1-w1` / `-w3` | 1,200 / 1,200 | **1,200 / 1,200** |
| `v0.1-w1 --opcodes EB` | 200 | **200 / 200** |
| `w0evt` / `w1evt` / `w2evt` / `w3evt` | 200 / 1,200 / 200 / 1,200 | **200 / 1,200 / 200 / 1,200** |
| `v0.1-w1evt-biased` | 1,200 | **1,200 / 1,200** |
| `check_boot --core ucore` 220 / 400 | MATCH / MATCH | **MATCH / MATCH** |
| `ulockstep --suite --waits 0,1,2,3` | ALL LOCKSTEP | **ALL SCENARIOS LOCKSTEP** |
| `ulockstep --golden all --cases 50` | 17,350 | **17,350 / 17,350** |
| `timed_wvec_gate --core ucore` | 88/88, +0.0 % | **88/88 digest, 88/88 count, +0.0 %** |
| `timed_enter_replay --core ucore` | 154/154 ×5 | **154/154 ×5** |
| `timed_ins_replay --core ucore --raw` | 1,312 / 2,624 | **1,312/1,312 and 2,624/2,624** |
| `timed_fuzz --core ucore --evt-replay` REGISTERED | 1,483/1,702 | **1,483/1,702 (87.1 %)** |
| … EVT / COMBINED | 192/1,008 · 1,675/2,710 | **192/1,008 · 1,675/2,710** |
| … `BOUND WARNINGS` / `ENGINE ABORTS` | 5 / 0 | **5 / 0** |
| `timed_fuzz --seeddir …/b2-tranche/seeds` | 171/188 | **171/188 (91.0 %)** |
| denominators (both populations) | 2,710 / 532 · 188 / 28 | **held** |
| `ss_lint --core ucore` | rc=0, 0 UNMAPPED | **rc=0, 201 flops, 0 UNMAPPED** |
| `ss_lint --core fsm` | rc=0 | **rc=0, 203 / 181 flops** |
| `--ce-div 4 --ce-hold-check` | 0 violations | **100/100, 0 violations** |
| save state, modes 1 / 2 | 80/80 · 24/24 | **80/80 · 24/24** |
| `check_ab_sim --core ucore` / `--core fsm` | 187 rows | **187 rows MATCH, both** |
| `gen_ucore_qsf --check` | up to date | **up to date** |
| **G0** `check_ucore_tables` | 9,988 | **9,988 PASS** |
| the MODEL, unmoved | 169,000, row-diffs 0 | **169,000/169,000, row-diffs 0** |
| **the b3 priority tranche, re-scored on the fixed binary** | `core` 176/178 · `vsim_ucore` 176/178 | **176/178 and 176/178, residue `bs`=2 — IDENTICAL** |
| `fsmhead` / `vsim_fsm` on the same tranche | 59/178 | **59/178 and 59/178, residue `bs`=83 `qs`=36** |

That last row is the load-bearing one for "one term, no new state": the fix is
**inert on the victory tranche**, which is what a pin-drive change confined to
the HALT pseudo-cycle must be.

*Artifact note, so the tree says what it holds*: `raw_vsim_ucore/` now carries
the **U5 binary's** 200 replays (regenerated by this re-score); `raw_core/`,
`raw_fsmhead/`, `raw_vsim_fsm/` and `raw_chip/` are untouched and are still the
§52.6 captures.  The scores are identical either way — that is the result — and
the manifest sha `92e3de08…` is unchanged, so the population is the same one.

### §54.5 THE TWO `bs` SEEDS OF THE TRANCHE RESIDUE — CLASSIFIED

§52.10 item 5, answered by the governance rule rather than by a patch.

| seed | waits | ucore first-div | SIM first-div | **ucore vs SIM, pairwise** |
|---|---|---|---|---|
| `mc1_300043` | `wrand wmax 2` | row **403**, ndiff 3,419/4,000 | row **403**, ndiff **3,419/4,000** | **0 / 4,000 rows differ** |
| `mc1_300122` | `wrand wmax 7` | row **402**, ndiff 3,570/4,000 | row **402**, ndiff **3,570/4,000** | **0 / 4,000 rows differ** |

At the divergent row the two engines are byte-identical — `mc1_300043`
`a=0xD6285 d=0x6205 ps=0xD`, `mc1_300122` `a=0xCFC1D d=0xFC1D ps=0xC` on BOTH —
and both issue an EU `MEMR` where the chip issues a `CODE` fetch (chip
`a=0x0050C ps=0`, a T1 code fetch).  Both are in V5's closed taxonomy as `bs`,
and the `bs` family is exactly where the model's own registered bank residue
sits (§44.2: `qs` 145, `bs` 37, `data` 23).

**VERDICT: a divergence the reference model SHARES, bit for bit — §0 governance
rule 3, a ledger finding routed to `sim/`, never a ucore patch.**  Patching the
RTL to beat the model here would create an RTL-vs-model divergence in the
direction the governance forbids, and the sim is the spec.  *Falsifier*: a
re-derivation in which the sim's rows at those clocks differ from the ucore's.

**So the entire residue of the campaign's victory condition is not the RTL's.**

### §54.6 V1's RE-REGISTRATION — A NOTE, NOT A REWRITE

§52.10 item 3.  **The old record stands exactly as written**: V1 was registered
at ≥ 85.0 % before board contact and was MET at 98.9 %.  §51.8a's defect note
stands beside it — the bar was set below the banked tranche's 89.4 % on the
reasoning that fresh seeds are not cherry-picked, and the measured direction is
the opposite (the frozen FSM core: 91.6 % fresh, 1.1 % banked).

Two fresh-population baselines exist, both frozen and committed before capture:
**178 seeds → 176 (98.9 %)** and **449 seeds → 435 (96.9 %)**.

Registered here as the successor bar, for the campaign owner to adopt or amend
(§(e) item 3 of the verdict):

> **V1′** — on a fresh, frozen, stratified `wrand` population of ≥ 150 scored
> seeds, captured after the freeze is committed, the ucore in fabric is
> cycle-exact on **≥ 96.0 %** — one point below the LOWER of the two measured
> baselines — **and** strictly above the FSM core built from the same HEAD on
> the same seeds by **≥ 30 points**.

The second clause is the discriminating one: it is what a barely-better core
cannot clear, and it is what §51.8a found V1 alone could not supply.

## §55 THE FABRIC RE-SCORE — PRE-REGISTERED BEFORE ANY BOARD CONTACT

Standing discipline: *pre-register predictions and commit before first board
contact.*  Nothing below is written after a capture.

### §55.0 THE STATE OF THE BOARD AT REGISTRATION

`root@mister-nec`, reachable, `up 22 days`.  **Single-writer check: no
`v30`/serve/python process on the board.**  On the fabric today is the
FSM-from-HEAD bitstream (`nec_test.sof a4533dfef0…`) left there by §52.10.

### §55.1 THE BITSTREAM UNDER TEST — G6 RE-RUN ON THE FIXED RTL

`quartus_sh --flow compile nec_test -c nec_test_ucore`, 17.1.0 Lite,
`5CSEBA6U23I7`, wall **8:56**.

| gate | registered | U4 pass 3 | **U5 (F51)** | |
|---|---|---|---|---|
| A&S / Fitter errors | 0 | 0 | **0** | ✅ |
| ALMs | FSM = 25 % | 11,078 / 26 % | **11,117 / 41,910 = 27 %** | ✅ |
| registers | — | 6,148 | **6,060** | — |
| M10K / RAM blocks | — | 105 / 19 % | **105 / 553 = 19 %** | — |
| **Fmax >= 32 MHz WITH MARGIN** | >= 32 MHz | 45.56 MHz | **48.03 MHz (+50 %)** | ✅ |
| worst setup slack / TNS | — | +8.922 / 0.000 | **+9.121 ns / 0.000 on EVERY clock domain** | ✅ |
| worst hold | — | +0.247 | **+0.244 ns, TNS 0.000** | ✅ |
| bitstream | a `.sof` | `cdf5edee00…` | **`.sof 924c4a61e0ad235e6257695a775d86cc51735ebba0cf9cf5f9ffb651bcc5105d`**, `.rbf 87882aa8b9…` | ✅ |

F51 cost 39 ALMs and BOUGHT 2.5 MHz.  `gen_ucore_qsf --check` is up to date, so
the two A/B bitstreams still differ by the CORE and by nothing else.

### §55.2 THE PREDICTION, AND ITS FALSIFIER

§52.9 measured the four HLT delay sweeps IN FABRIC at **29/283** with the
signature `0x0AD8A` against the golden's `0x2AD8A` on the HALT display and its
T1, and the display dropped one row early.  F51 is the fix.  Registered:

1. **The F42-refutation SIGNATURE IS GONE: ZERO cells whose first divergence is
   the HALT display's own `bus` or `data`.**  This is the sharp one.  *If any
   cell still reports `0x0AD8A` where the golden has `0x2AD8A`, F51 is
   incomplete and is reported as incomplete.*
2. **The fabric total is >= 249/283** — the ucore's pre-U5 offline number, a
   deliberately conservative floor — and the EXPECTED value is the corrected
   offline number, **259/283 ± 4 cells**.  A fabric result far below the
   offline one would be a FABRIC-vs-SIM finding (V3's shape) and is the more
   important result if it happens.
3. **The socket control must reproduce the golden 49/49** on the identical
   driver (`EMIT_USE_CORE=False`, `use_core=0`).  This is the rig-integrity
   leg, not a result: if it moves, nothing else in this section is readable.
4. **`use_core=0` boot vs the standing golden must MATCH over 800 rows** on the
   new bitstream, taken FIRST, before anything else — §48.2's chip-path proof,
   which is what `gen_ucore_qsf --check` is supposed to make impossible to fail.
5. **The priority tranche is NOT re-captured.**  Its fabric leg was scored at
   §52.6 on the pass-3 bitstream and the RTL change is proved INERT on it
   offline (§54.4: `vsim_ucore` 176/178 with residue `bs`=2, identical before
   and after).  Re-capturing would spend 483 board captures to reproduce a
   number a controlled offline re-score already reproduces.
6. **The board is left with the ucore bitstream on it**, not the FSM one,
   with `use_core=0` re-proved on it — one flash rather than two, and the
   lower-risk choice at a closure.  Recorded as a deliberate deviation from
   §52.10's parting state.

## §56 THE FABRIC RE-SCORE — SCORED AGAINST §55.2, AND F51 HOLDS IN SILICON

FLASH #3, `sw/safe_flash.sh` with its VERIFY leg (MAGIC OK, `pwr_good` /
`cpu_running` true, ledger appended), single-writer checked first.
`nec_test_ucore.sof 924c4a61e0…`.

### §56.1 THE FOUR REGISTERED BARS

| # | registered | **measured** | |
|---|---|---|---|
| 4 | `use_core=0` boot vs the standing golden, taken FIRST | **MATCH over 800 rows** — and first light re-proved on the new bitstream, `chip-vs-golden` / `core-vs-chip` / `core-vs-golden` all **MATCH 800** | ✅ |
| 3 | the socket control reproduces the golden 49/49 | **49 / 49**, 0 misses, on the identical driver | ✅ |
| 1 | **ZERO cells still showing the F42 signature** (`0x0AD8A` where the golden has `0x2AD8A` on the HALT display) | **ZERO.**  No cell's first divergence is the HALT display's own `bus` or `data` any more, at any wait level | ✅ |
| 2 | fabric total ≥ 249/283, expected 259 ± 4 | **143 / 283**, against 29/283 before | ❌ **MISSED — and the miss is ONE CLASS, measured** |

**Bar 2 is reported as MISSED, not re-explained** — that is the F42 rule, and it
is applied to U5's own prediction with the same edge.  What follows is the
measurement, not the excuse.

### §56.2 THE MISS IS ONE CLASS, AND IT IS 116 OF 116

Scored cell by cell against the OFFLINE (TB) result on the same binary's RTL, in
one numbering:

| sweep / form | offline | **fabric** | fabric-only failures | all on an INTA row? | offline failures also fail in fabric? |
|---|---|---|---|---|---|
| `s10-w0` `HLT.INT` | 44/48 | **0/48** | 44 | **yes** | yes |
| `s10-w0` `HLT.RES` | 47/49 | **47/49** | 0 | — | yes |
| `s10-w1` `HLT.INT` | 42/46 | **0/46** | 42 | **yes** | yes |
| `s10-w1` `HLT.RES` | 48/49 | **48/49** | 0 | — | yes |
| `s13-w2` `HLT.INT` | 16/21 | **0/21** | 16 | **yes** | yes |
| `s13-w2` `HLT.RES` | 24/25 | **24/25** | 0 | — | yes |
| `s13-w3` `HLT.INT` | 14/20 | **0/20** | 14 | **yes** | yes |
| `s13-w3` `HLT.RES` | 24/25 | **24/25** | 0 | — | yes |
| **total** | **259/283** | **143/283** | **116** | **116 / 116** | **all** |

Two statements, both exact and both worth reading twice:

1. **`HLT.RES` in fabric is IDENTICAL to `HLT.RES` offline, cell for cell** —
   47/49, 48/49, 24/25, 24/25 on both legs, the same failing `idx` on both.
   That is V3's shape on the sweeps and it is perfect: the Verilator model of
   this bitstream is the bitstream.
2. **Every one of the 116 fabric-only failures is an INTA row**, and there are
   no others; and **no cell fails offline and passes in fabric** — the fabric is
   strictly stricter, never differently strict.

### §56.3 WHAT THE INTA CLASS LOOKS LIKE — AND WHY THAT IS A READING

MEASURED, `HLT.INT` w0 `idx 10`, the first divergent row (16), an INTA **T1**:

```
golden  [T1] bus=0x09090  data=0x9090   INTA T1
ucore   [T1] bus=0x000FF  data=0x00FF   INTA T1
row 17  [T2] bus=0x60003F data=0x00FF   INTA T2   <- IDENTICAL on both
```

`sim/biu_timed.cpp` states the mechanism and both engines agree with it: *"S9a
(`Access::no_addr`): an INTA drives no address.  Freeze the FLOATING AD — the
last data phase, upper nibble 0."*  The chip's AD pads float at an INTA's T1 and
**retain** the previous data phase (`0x9090`).  In the FPGA the core's AD is an
internal `tri` net inside `system_large`; Quartus resolves an undriven internal
tri-state to a mux, **not** to a charge-retaining pad, so there is nothing to
retain and the row reads the harness's INTA vector byte instead.

This is the campaign plan's **risk #4** — *"multiplexed-pad float → G7-only
divergences → ledger open item 1, not patches"* — arriving exactly where it was
predicted to.  It is already the documented column policy of the OTHER fabric
gate: `sw/check_ab_hw.py`'s own docstring reads *"Float-retention rows are
excluded by the policy (the core's internal AD net has no charge retention, so
raw float bytes legitimately differ from the chip's)"*, which is why first light
is 800/800 on the same bitstream in the same session.  `check_core.diff_rows`
carries no such exclusion because it was built for the Verilator TB, which
models retention.

**THE READING — and it is a READING, not a finding.**  On this evidence the
116 cells look like an INTEGRATION property of the A/B harness rather than a
defect in the core: 116 of 116 with no exceptions, a zero-cell
counter-population, `HLT.RES` identical on both legs cell for cell, and a socket
control at 49/49 on the same driver in the same session.  Booked as **U5 open
item 0**, with two candidate fixes named and **NEITHER taken**: give the
harness's `core_ad` a retention model in `system_large.sv` (which changes the
A/B harness and therefore BOTH cores' fabric numbers, so it needs its own
pre-registered before/after), or teach the fabric scorer `check_ab_hw`'s
float-retention exclusion.  The first is a harness change at a closure; **the
second would be choosing a comparator after seeing the result**, which is not a
thing this campaign is allowed to do.

### §56.3a WHY THIS IS "NOT ESTABLISHED" AND NOT "SHOWN" — C11, AND F42's GHOST

The argument in §56.3 has the SAME SHAPE as F42's: *"the failing cells are an
artefact of how the pins are observed, not of the core."*  F42 made that
argument from a structural reading of a mask plus two probes, was accepted as
sound-but-under-evidenced by C6, was measured on its whole population 24/24 —
and was still **REFUTED** in fabric, because a population-wide correlation is
not a causal demonstration.  §56.3's evidence is stronger in every dimension
(116/116, a zero-cell counter-population, an identical-on-both-legs control form,
and a 49/49 socket control) and it is **still the same kind of evidence.**

C11's verdict, adopted verbatim as the ledger's own: **NOT ESTABLISHED.**  The
attribution is a reading, not a finding, and it is recorded as a reading.

**THE MEASUREMENT THAT WOULD SETTLE IT, PRE-REGISTERED AND NOT RUN.**  It is
an INTERVENTION, which is what §56.3's correlation is missing:

* **The intervention**: give `system_large.sv`'s `core_ad` an explicit
  retention model — a register that captures the last DRIVEN value of AD and
  supplies it when no driver is active — so the FPGA's internal net reproduces
  the pad behaviour the chip has.  **Nothing in either core changes, and
  `v30u_biu.sv` in particular must NOT be touched**: its INTA path deliberately
  drives no address (`disp_inta || cur_inta` selecting `20'h0` with `ad_oe_ps`),
  which is `sim/biu_timed.cpp`'s `Access::no_addr` rendered faithfully.  An
  intervention that also changed the core would confound exactly the question
  being asked.
* **The population**: the same four HLT delay sweeps, all 283 cells, same
  driver, same goldens, plus the 49-cell socket control.
* **THE BAR, BOTH HALVES, AND BOTH ARE REQUIRED**:
  1. **ALL 116 fabric-only cells CLOSE** — the fabric total goes to **259/283**,
     equal to the TB's, not merely toward it.  A partial close means the class
     was not one mechanism and the residue is the core's.
  2. **NOTHING ELSE MOVES**: `HLT.RES` stays cell-identical at 47/49, 48/49,
     24/25, 24/25; **every `HLT.INT` cell matches its OFFLINE result cell for
     cell**, not merely in total; no non-INTA row acquires a new first
     divergence; **the F42-signature count stays ZERO**; the socket control
     stays 49/49; and the `use_core=0` chip-path proof stays MATCH over 800 rows
     with first light 800/800 ×3.
* **WHAT REFUTES THE ATTRIBUTION**: any of the 116 still failing with the
  retention model demonstrably supplying the prior driven data phase at the
  INTA's T1, or any fabric-only NON-INTA divergence appearing.  A surviving
  divergence is **reclassified as CORE-OWNED** unless a separately
  pre-registered mechanism is established for it — exactly as F42's 17 turned
  out to be the core's, and it is reported as a refutation and not re-explained.
* **Cost and why it is not run here**: it is a change to the A/B harness that
  both cores' fabric numbers depend on, so it needs its own pre-registered
  before/after on both cores, a Quartus compile and a flash — at a closure, and
  after the campaign's own gates are green.  It is handed on with its mechanism
  named and its bar written, which is the disposition F43 has carried through
  two stages.

*Falsifier for the reading as it stands*: a fabric cell whose first divergence
is an INTA row but whose golden value is NOT the retained previous data phase;
or a non-INTA fabric-only failure at any wait level.

### §56.4 F42's REFUTATION, CLOSED

§48.3's registered prediction was refuted in fabric at U4 (§52.9) and §52.10
item 1 handed U5 the RTL item.  It is closed:

| | U4 pass 3 | **U5** |
|---|---|---|
| the four sweeps, IN FABRIC | **29 / 283** | **143 / 283** |
| cells still showing `0x0AD8A` for `0x2AD8A` | 254 | **0** |
| the socket control, same driver | 49/49 | **49/49** |
| the four sweeps, offline | 249/283 | **259/283** |
| `HLT.RES`, fabric vs offline | different | **IDENTICAL, cell for cell** |

### §56.5 THE BOARD, LEFT

The **ucore** bitstream (`924c4a61e0…`) is on the fabric — §55.2 item 6's
declared deviation from §52.10's parting state, one flash rather than two — with
`use_core=0` proved MATCH 800 on it and the harness back in its chip-capture
role.  `board_idle` run twice; **two consecutive clean 4,063-row idle captures**
afterwards, the divider left at `DIV_OF_RECORD = 8`, `use_core=False`.  The
flash is in `sw/testdata/flash_log.jsonl`.  The priority tranche was NOT
re-captured, as registered.

## §57 GATE U5, AND THE CAMPAIGN CLOSE

### §57.1 GATE U5 — GREEN, WITH ONE REGISTERED MISS AND ONE ROUTED FINDING

| item | verdict |
|---|---|
| **F42's refutation closed as an RTL item** (§52.10 item 1) | **F51 LANDED.**  Offline the sweeps 249 → **259/283** and v0.1 back to **169,000/169,000** on the corrected comparator; in fabric **29 → 143/283** with **ZERO** cells still carrying the signature |
| **the TB's composed-AD mask** (U3 open item 1) | **DISCHARGED** — removed, engine-neutral, with the pre-registered before/after on BOTH cores that §45.3 demanded |
| **the 2 `bs` tranche-residue seeds** (§52.10 item 5) | **CLASSIFIED — not the RTL's.**  ucore ≡ SIM on **4,000/4,000 rows** on both |
| **V1's re-registration** (§52.10 item 3) | **§54.6** — the old record stands, its own defect note stands, and **V1′** is registered for the owner to adopt or amend |
| **the full ladder** | **ZERO DELTAS** (§54.4), including the priority tranche re-scored on the fixed binary at 176/178 with the identical `bs`=2 residue |
| **G6 on the fixed RTL** | **GREEN with MORE margin than before** — 27 % ALMs, **Fmax 48.03 MHz** (was 45.56), setup +9.121 ns, TNS 0.000 on every domain |
| **the board** | FLASH #3, chip path MATCH 800, first light 800/800 ×3, socket control 49/49, `board_idle` ×2, two clean 4,063-row idle captures, divider at `DIV_OF_RECORD` |
| **§55.2 bar 2** | **MISSED — 143/283 against a registered ≥ 249**, reported as missed; the miss is one class, 116/116, and its attribution is **NOT ESTABLISHED** with the settling intervention registered and unrun (§56.3a) |
| **§53.4 bar 3** | the FSM core's numbers on the corrected comparator, **ROUTED to the campaign owner** exactly as the bar said in advance they would be |

### §57.2 EVERY STANDING GATE, RE-RUN AT THE CLOSE

Not inherited — re-run on the closing tree, after both the TB and the RTL
changed.

| gate | result |
|---|---|
| `make -C sim test` | **disasm gate: PASS** (byte-exact vs `V20UC.TXT`) |
| `sw/pla3_check.py` | **OK — 21 checks passed** |
| `sw/ucsim_check.py --suite tests/v30/v0.1` | **169,000 / 169,000 ARCH** |
| `sw/check_ucore_tables.py` (**G0**) | **PASS — 9,988 / 9,988**, both legs |
| `sw/optable.py --selfcheck` | **0 errors** |
| `sw/prefix_clear_lint.py` | **PASS** (20 `S_FIRST` sites, 4 PFX-KEEP, no drift) |
| `sw/ea_step_lint.py` | **PASS** |
| `sw/check_race_law.py` | **PASS 2/2** — regeneration byte-identical, header sha matches |
| `sw/check_lc6_gate.py` | **PASS** |
| `sw/check_mod3_illegal.py` | **PASS** — 128/128 cycle-exact, 128/128 arch-confined, moffs 2/2 |
| `sw/check_ff_t4.py` | **PASS** — 9/9 seeds, 9 `SLOT_FF_T4` fires, invariant armed |
| `sw/check_enter_nesting.py` (the FSM/RTL leg) | **PASS** — MASK 512 goldens, WAITED 154, 0 unexpected divergences |
| **`sw/check_fuzz_bank.py`** (the FSM leg, 3,242 banked seeds) | **PASS — stable 3,242, improved 0, WORSE 0, gen_drift 0, regen_err 0, float-floor 0, new-sig TIMING 0** |
| `sw/ss_lint.py --core ucore` / `--core fsm` | **rc=0** / **rc=0** |
| the whole ucore ladder | **§54.4 — zero deltas** |

**`check_fuzz_bank` is the load-bearing row for the instrument change.**  It
replays the entire 3,242-seed banked chip corpus through the FSM TB and
re-classifies every seed, and it reports **worse 0** — so removing the
composed-AD mask moved **no** banked seed's chip-vs-TB verdict.  The mask's
effect is confined to exactly the rows it was masking, which is what
"engine-neutral" has to mean in practice and not merely in argument.

### §57.3 WHAT THE CAMPAIGN ANSWERED

The verdict is `docs/notes/ucore_campaign_verdict_2026-08-04.md`.  In one line:
**the mechanism ledger IS a spec you can build hardware from — and it is NOT a
spec you can build hardware from without grading.**  Fifty-one findings are the
distance between those two sentences, and about two thirds of them are places
where the document was right and the transliteration was wrong in a way only a
comparator could see.

### §57.4 WHAT IS ROUTED TO THE CAMPAIGN OWNER

Three decisions, evidence laid out both ways in verdict §(e), **none taken
here**: the **FSM core's disposition** (keep as reference / retire / demote to
archive), the **`evt_hold` widen** and the EVT re-banking, and whether **V1′**
becomes the standing bar.  Plus two measurements handed on with their bars
written: **§56.3a** (the `core_ad` retention intervention that settles open
item 0) and the **FSM regression bisect** (2026-07-30 → HEAD).

**GATE U5: GREEN.  CAMPAIGN CLOSED.**

---

## §58 THE SILICON-MATCH PHASE — the governance change, and session SM1

**2026-08-04, branch `ucsim`, session SM1.**  §0-§57 are the ucore campaign,
which closed at U5 under a rule that no longer applies.  This section opens the
phase that replaces it.  **Nothing above is edited**; every finding §0-§57 books
was classified under the OLD rule and a reader needs the rule it was written
against.

### §58.0 THE DIRECTIVE, VERBATIM

The user directive of 2026-08-04, as it stands in `CLAUDE.md`:

> ## Correctness target (user directive 2026-08-04 — supersedes the ucore
> campaign's RTL-vs-sim governance)
>
> **SILICON MATCH is the only correctness bar.** "Matching the model is no
> longer acceptable." The C++ sim remains an instrument (lockstep, census,
> attribution) but is NOT the reference: a divergence from silicon is a work
> item regardless of whether the model shares it; model-shared residue is no
> longer accepted residue. Where the rig or a golden is found defective, fix
> the rig and RE-CAPTURE; goldens invalidated by rig defects are DISCARDED
> from all gate sets — archived by rename with an invalidation ledger entry
> (the w1evt-biased precedent; raw captures stay retained, nothing gates on
> them).

Propagated to `hdl/rtl/ucore/README.md`, whose GOVERNANCE RULE now states the
silicon-first rule and keeps the U0-U5 rule quoted beneath it, marked
HISTORICAL — DO NOT APPLY.

### §58.1 WHAT IT RECLASSIFIES — the itemised list

The partition that changes is the **`model-shared`** row of the gap report's
owner table.  Under §0 rule 3 a model-shared divergence was *a ledger finding*
and the ucore's books were closed on it.  It is now **WORK**, still routed to
`sim/` first where the mechanism is the model's — the dependency direction is
unchanged, and it is still the cheap way to fix a shared mechanism once — but it
stays OPEN on the ucore's books until silicon matches.

| item | was | **is now** |
|---|---|---|
| **T3 — the 210 model-shared registered-bank seeds** | *"seeds the model misses too"*, closed by the inherited seven-family taxonomy | **210 open work items.**  Their families are now measurable in the ucore's OWN engine for the first time (§58.4). |
| **T4 — the 2 `bs` seeds of the priority tranche** | *"never a ucore patch"*, 0/4,000 rows apart from the sim | **open.**  Being byte-identical to the model at the divergent row is now an ATTRIBUTION (the mechanism is the model's), not a disposition. |
| **T8 — the 4 shared seeds of §49.7** | model-shared, *"deliberately not patched"* | **open.**  Three are an exact byte swap on an odd-address word write — M5b's A0 swapper applied where the chip does not.  Both engines agree with each other and disagree with the socket, which is now the definition of a bug rather than of a pass. |
| **I3 — INTA under waits, the second acknowledge's ANCHOR** | model-shared, *"the ucore inherits whichever way it lands"* | **open**, and it needs the directed cell §26.6.4 names.  Its whole-program evidence column was the EVT population, which INV-1 has just suspended — so this item's instrument must be rebuilt before it can be worked. |
| **I5 — the four ucsim-t open-surface items** (§26.10 D) | model-shared, inherited *"because the ledger does"* | **four open work items.**  The withdrawn announcement's pad retention is the whole remaining w2/w3 sweep residue on the model side and is board-free with stimulus already banked. |
| **I1 — the sim's `9D` flag-commit erratum** | *"the one place this campaign owes the model a fix"* | **unchanged in substance and sharper in standing**: here the RTL matches silicon and the MODEL does not, so under the new bar the model is simply wrong and the fix is owed outright. |

**What does NOT change.**  A divergence the ucore has and the model does not is
still a ucore bug (it always was).  `ulockstep` is still the only instrument that
compares the two engines directly, and it is *more* useful now, not less: it
separates "the rendering is wrong" from "the spec is wrong", which is exactly the
question the new bar asks about every open item.

### §58.2 SESSION SM1 — WHAT WAS DONE

1. **Governance propagated** — `hdl/rtl/ucore/README.md`, and this section.
2. **The `evt_hold` widen (R1 / T5), landed and build-proved** — §58.3.
3. **R4 closed: `s15_census` gained an engine**, and the ucore's own family
   census exists for the first time — §58.4.
4. **R3 and R5 closed** — §58.5.
5. **X1's intervention run offline, and it is MET on that leg** — §58.6.
6. **The invalidation sweep, and INV-1** — `docs/notes/invalidation_ledger.md`,
   summarised at §58.7.

### §58.3 THE `evt_hold` WIDEN — LANDED, BUILD-READY, NOT YET IN SILICON

Gap **R1**, verdict §(e) item 2, routed to the owner and now taken.

```
hps_axi_slave.sv   evt_hold  8 -> 12 bits, packed {wdata[30:27], wdata[23:16]}
nec_bus.sv         input [11:0] evt_hold, ev_hold_cnt 8 -> 12
system_large.sv    the wire
v30ctl.py          RIG_EVT_HOLD_BITS = 12, ONE definition; set_event RAISES
                   on an out-of-range hold instead of truncating
fuzz_campaign.py   every new capture banks evt.hold_bits + evt.hold_applied
timed_fuzz.py      --rig-hold gains `applied` (reads the seed's own record)
```

`EVT_CFG (0x20)`'s free space is bits `[30:27]`, so the hold is **split**:
`[23:16]` low, `[30:27]` high.  `evt_pin[26:24]` and `evt_arm[31]` do not move
and a host writing zeros in `[30:27]` reproduces the old behaviour exactly —
which is what makes this a drop-in rather than a protocol break.  The readback
at `0x20` is composed to match.

**The root cause is not the width.**  It is that the rig applied a directive
other than the one it was handed, silently.  `set_event` now raises; that is the
part of this change that prevents the next F46.

**Build state**: `sw/check_ab_sim.py` (the ucore inside the REAL integration)
rebuilt on the widened RTL and is **187 rows MATCH**, unchanged.  The new
`tb_sys` harness (§58.6) drives the widened `EVT_CFG` packing and runs 283 cells
with 0 errors, so the split packing is exercised end-to-end offline.  **No
Quartus run and no flash** — every flashed bitstream is 8-bit-hold silicon
(`flash_log.jsonl` ends at FLASH #3).  **SM2 owns the bitstream.**

### §58.4 R4 — `s15_census` HAS AN ENGINE, AND THE ucore HAS A FAMILY CENSUS

**Gap R4 closed.**  `s15_census.py` called `tf.run_sim` unconditionally and took
only the SEED LIST from `--report`; pointed at a `--core ucore` report it ran
clean and reported the MODEL's families for the ucore's seeds.  It now has
`--core {sim,ucore,fsm}` with `choices=`, dispatching through a single `replay()`
that knows the two engines take DIFFERENT event inputs (the model is HANDED the
capture's acknowledges; an RTL core is handed the rig's directive and predicts
them).  Default stays `sim`, so every historical invocation means what it meant.

**VALIDATION — the 9 / 210 / 220 partition, reproduced exactly.**  Two
`timed_fuzz` runs over the frozen 1,702-seed registered bank, compared seed by
seed:

```
REG: scored 1,702    ucore non-exact 219    sim non-exact 430
     ucore-ONLY  9      sim-ONLY 220      shared 210      net +211
```

and the nine are the same nine §T.2 names: `mc1/412`, `mc1/721`, `mc1/1937`,
`mc1/3325`, `mc2/584`, `mc2/2216`, `mc2/3291`, `t30-raw/84`, `t30-raw/123`.

**Two controls, and the second is the sharp one.**

| leg | result |
|---|---|
| `--core sim` on the SIM's 430 | `PF_LOST` 239 · `SCHEDULE` 79 · `TAIL_EXTRA` 30 · `DATA_SEQ` 28 · `PF_GAINED` 23 · `PF_ADDR` 17 · `PIN` 14 — **§T.3's model column, cell for cell** |
| `--core sim` on the UCORE's 219 | `PF_LOST` 110 · `TAIL_EXTRA` 30 · `DATA_SEQ` 28 · `PF_GAINED` 23 · `SCHEDULE` 12 · `PF_ADDR` 4 · `PIN` 3 — **§T.3's shared-210 column, cell for cell** — *and it reports **9 `NOW_EXACT`***, which are exactly the nine ucore-only seeds.  The model is cycle-exact on them.  That is the old tool's blind spot made visible by the new flag: 9 of the 219 rows in the table it used to print were rows about seeds the replayed engine does not miss. |

**THE ucore's OWN REGISTERED-BANK FAMILY CENSUS — the first one ever taken.**
219 seeds, its own engine, 0 `NOW_EXACT` (a self-consistency control: the census
engine and the report engine agree on every seed):

| family | **ucore, its own 219** | the model's families on the shared 210 | the model's own 430 |
|---|---|---|---|
| `PF_LOST` | **107** | 110 | 239 |
| `DATA_SEQ` | **41** | 28 | 28 |
| `TAIL_EXTRA` | **28** | 30 | 30 |
| `PF_GAINED` | **25** | 23 | 23 |
| `PF_ADDR` | **9** | 4 | 17 |
| `SCHEDULE` | **5** | 12 | 79 |
| `PIN` | **4** | 3 | 14 |
| catch-all | **0** | 0 | 0 |
| **total** | **219** | **210** | **430** |

Read it against the old table and one thing jumps: **`DATA_SEQ` is 41 in the
ucore's own engine against 28 in the model's.**  §T.3 recorded `DATA_SEQ` as one
of three families *"the ucore closed NOTHING in"* — 28 seeds, the same seeds in
both engines — and concluded they are the MODEL's mechanisms.  In the ucore's
own engine the family is **13 seeds LARGER**, which means the shape does not
partition the way the model-replayed table implied: the ucore has `DATA_SEQ`
divergences of its own, on seeds the model misses for a different reason.  That
is F47's shape (the right cycle, the right address, the wrong word) appearing in
a population where it had been invisible.  **Booked, not diagnosed.**

`SCHEDULE` moves the other way — 5 against 12 — so on these seeds the ucore's
arbitration is closer to the chip than the model's even where both miss.

The ucore-only nine, in the ucore's own families: `DATA_SEQ` 4 · `PF_ADDR` 2 ·
`PF_LOST` 1 · `PF_GAINED` 1 · `PIN` 1.

*Falsifier for the `DATA_SEQ` reading*: a re-derivation in which the 13 extra
seeds are `DATA_SEQ` in the model's engine too — i.e. the difference is the
instrument and not the engine.

### §58.5 R3 AND R5

* **R3** — `tb_v30_core.sv`'s mode-4 guidance comment said *"run many seeds:
  most flips must diverge"*.  It now says what F45 actually established: mode
  4's seed IS the bit index, so **step the seed by 16** to walk one bit per
  stream word, and the bar is *some* must diverge, form- and
  freeze-point-dependent.  A reader of the old comment builds a blind gate that
  only ever touches the first stream word.
* **R5** — the CE-hold probe watched the BIU only (`r_ts`, `r_q_cnt`,
  `r_fetch_ptr`), so a clean `+ce_div` cell was BIU-state evidence and the EU
  side rested on the golden row match.  The probe now carries the ucore EU's
  spine — its micro-PC `upc_page` / `upc_opc` / `upc_loc`, which is what
  `u_eu.state` was for the archived core — and the probe word is 64 bits and
  zero-extended for both engines so a widening is not an engine fact.
  **Re-run: `check_core.py --ce-div 4 --ce-hold-check --opcodes all`
  = `CE_HOLD_VIOL 0` on every form, 694/694 full.**  The gate is greener for a
  better reason than it was.

### §58.6 X1 — THE §56.3a INTERVENTION, VERILATED LEG: **MET**

Reported **as registered**.  §56.3a pre-registered the intervention, the
population and a two-half bar, and handed it on unrun.  This session ran its
OFFLINE half.

**The instrument, because it did not exist.**  Neither Verilator harness could
ask X1's question: `tb_v30_core` is the core ALONE behind a TB memory that
**models pad retention** (which is why it scores 259/283 and can never see the
fabric's 116 cells), and `tb_ab` is `system_large` with a FIXED boot image, no
event scheduler and no image load.  **`hdl/tb/tb_sys.sv`** is new: `system_large`
driven exactly as the ARM drives it on the board — image loaded through the AXI
`A_MEM` window under `host_reset`, `CFG` / `PINS` / `EVT_ADDR` / `EVT_CFG`
written through the bridge, `use_core=1`, the real `nec_bus` capture path
drained as the same 64-bit records `decode_words` parses off the board.
`sw/x1_retention.py` drives it through **`emit_suite`'s own driver**, so the
number is on `check_core`'s scale by construction, exactly as `u4_f42_fabric`
does for the FPGA.

**THE ONE DEVIATION FROM THE LETTER OF §56.3a, STATED BEFORE THE RUN** (it is
written into `system_large.sv` beside the code): the retention is applied on the
**observation path** — `hb_ad_sample`, what `nec_bus` captures — and NOT as a
keeper driving `core_ad` itself.  Two reasons, the first decisive: a keeper on
the net needs an "is anyone else driving" term whose only honest source is the
core's own output enable, which is not a port, and manufacturing one in the
harness would be re-deriving the core's OE from its status pins — a fitted rule
in the exact place the intervention must not have one.  Second, it keeps the
core's INPUT untouched, which is the registration's own constraint.  It
therefore tests the claim **as it is actually made** — *"the row READS the
harness's INTA vector byte instead of the retained previous data phase"* — and
no more.  `v30u_biu.sv` is not touched; nothing in either core is.

**THE PRE-CONDITION, AND IT IS THE STRONGEST PART OF THE RESULT.**  Before the
intervention can be scored, the Verilated integration has to BE the fabric on
this population.  It is:

| leg | score |
|---|---|
| `tb_v30_core` offline (models retention) | **259 / 283** |
| **`tb_sys` baseline, `X1_AD_RETENTION` OFF** | **143 / 283** |
| the FABRIC, §56.1 (cited, not re-measured) | **143 / 283** |
| `tb_sys` with the retention model ON | **259 / 283** |

The baseline reproduces the fabric total **exactly**, its 116 base-only failures
are **116**, and **116 of 116** have an **INTA** row as the golden's
first-divergence row.  The Verilated `system_large` is the bitstream on this
population, which is what makes the intervention scoreable offline at all.

**SCORED AGAINST THE REGISTERED BAR:**

* **BAR (i) — all 116 close, and the total reaches 259/283 EXACTLY, not merely
  toward it: MET.**  closed 116, **survived 0**, ret total 259 = offline 259.
* **BAR (ii) — nothing else moves; every cell matching its OFFLINE result cell
  for cell: MET.**  **0** cells differ from offline after the intervention.
  `HLT.RES` is cell-identical (47/49, 48/49, 24/25, 24/25) and no non-INTA row
  acquires a new first divergence.

**WHAT THIS DOES AND DOES NOT SETTLE.**  §56.3a's bar is written on FABRIC
numbers and includes a 49/49 socket control and a `use_core=0` 800-row MATCH —
board measurements, and **no board was touched this session**.  So the
attribution is **not yet ESTABLISHED**; what is established is that the
mechanism §56.3 named is **sufficient, offline, to account for all 116 cells and
for nothing else**, on an integration that reproduces the fabric baseline cell
for cell.  A correlation has become an intervention with a clean result on one
leg.  **The fabric leg is SM2's**, and it needs its own pre-registered
before/after on both cores, a Quartus compile and a flash — the cost §56.3a
already priced.  C11's verdict stands until then.

*What would still refute it*: the fabric leg failing to reproduce this, or any
of the 116 surviving in silicon.

### §58.7 THE INVALIDATION SWEEP — INV-1

Full entry: **`docs/notes/invalidation_ledger.md`**, a file this session opened
because the directive names a register that did not exist.

**INV-1 — the EVT-scored fuzz population, as a gate.**  760 banked seeds carry
`evt.hold = 300` and the rig's register was 8 bits, so the socket was held 44
clocks.  Measured this session: all 760 are inside the 1,008-seed scored EVT
population; the other 248 carry `hold = 2`.  The `chip_rows` are TRUE silicon —
what is false is the **label**, and therefore the directive an engine is handed.

| engine | the poisoned 760 | **the un-poisoned 248** | as banked, 1,008 |
|---|---|---|---|
| ucore | 22 | **170 (68.5 %)** | 192 |
| sim | 565 | **144 (58.1 %)** | 709 |

**On the EVT seeds whose directive the rig actually applied the ucore beats the
model by 26 seeds; as banked it "loses" by 517.**  That is the whole content of
§T.5's 547 ucore-only non-exact seeds.

The exclusion is **derived from the record**, not from a list and not from a
rename (`timed_fuzz.f46_invalidated`): a seed is out iff its banked `hold`
disagrees with what the rig that captured it could hold.  Nothing was moved and
nothing was deleted — the 760 files are still read by `check_fuzz_bank`'s
3,242-seed corpus and by `s15_census --rmw`, and moving them would have silently
changed both.  `timed_fuzz` prints them on an `INVALIDATED` line and sums them
into nothing.

**Gate movement**: `REGISTERED` **unchanged** at ucore 1,483/1,702 and sim
1,272/1,702 (re-run).  `EVT` re-registered at **ucore 170/248, sim 144/248**.
`COMBINED` re-registered at **ucore 1,653/1,950, sim 1,416/1,950**.  **The full
1,008-seed EVT column is SUSPENDED pending an SM2 re-capture** on a bitstream
carrying the 12-bit hold.

The sweep also **cleared** everything else it examined, and the clearances are
recorded so the suspicions are not re-raised: every `tests/v30` golden suite
(the emitter's max declared hold is **6**), the b2 / b3 / b4 tranches (no `evt`
axis at all), the sticky-divider era (retracted before landing; the rig pinned at
§22.6), and the composed-AD mask (a comparator defect — no golden was ever
emitted from a TB, and §57.2's 3,242-seed replay moved no verdict).

**And a correction to the precedent the directive cites**: the w1evt-biased
event was an **archive-by-rename, not an invalidation** — §24.7 says in terms
*"the old suite is not retracted"*, and the biased suite is a live standing gate
today.  It supplies the habit (rename, never delete; keep the evidence with the
artifact; its own commit; report both numbers) and not the disposition.
**INV-1 is this project's first actual invalidation.**

## §59 SESSION SM2 — THE BOARD RE-CAPTURE.  **PRE-REGISTRATION**

Standing discipline: *pre-register predictions and commit before first board
contact.*  Everything in §59.0-§59.6 was written and committed BEFORE any
capture was taken.  §59.7 onward is the record of what happened.

### §59.0 THE STATE OF THE BOARD AND OF THE TREE AT REGISTRATION

`root@mister-nec`, reachable, `up 22 days 19:40`.  **Single-writer check: no
`v30` / `serve` / `python` process on the board** (`ps ax`, empty).  JTAG:
`jtagconfig` sees `1) DE-SoC [1-1.2.4]` with `SOCVHPS` + `5CSEBA6`.

On the fabric today is **FLASH #3**, `nec_test_ucore.sof
924c4a61e0ad235e6257695a775d86cc51735ebba0cf9cf5f9ffb651bcc5105d` — U5's
bitstream, and **8-bit-hold silicon**: every flash in `sw/testdata/flash_log.jsonl`
predates the F46 widen.

Tree: branch `ucsim`, HEAD `e390216132`, **no modified tracked files**.
`sw/gen_ucore_qsf.py --check` is up to date, so the two A/B bitstreams still
differ by the CORE and by nothing else.

**A rig fact recorded before it can be discovered after a failure**: the board's
own copy of the host tool, `/media/fat/v30/v30ctl.py`, is `md5
8eff261e3bfbaf7ef17755aaed7b1ec4` and the repo's is `385de605c220bca84a1a773f5e7517c8`.
The board copy PREDATES the 12-bit widen.  The `serve` session that takes every
capture runs the BOARD's copy (`v30run.ServeRunner.ensure` → `cd /media/fat/v30
&& exec python3 v30ctl.py serve`), so **deploying the repo's `v30ctl.py` to the
board is part of the rig fix, not an afterthought** — a 12-bit bitstream driven
by an 8-bit host is still an 8-bit rig, and it would fail silently in exactly
the way F46 did.

### §59.1 THE POPULATION, RE-COUNTED FROM THE ARTIFACT

Not from the ledger: recomputed here by `f46_invalidated`'s own arithmetic over
every banked seed.

| bank | seeds | `evt` armed | `hold=2, bits=8` | `hold=300, bits=8` | **INVALIDATED** |
|---|---|---|---|---|---|
| `mc1` | 1,295 | 502 | 133 | 369 | **369** |
| `mc2` | 1,294 | 503 | 112 | 391 | **391** |
| `t30-raw` | 568 | 160 | 160 | 0 | 0 |
| `t30-brkem` | 85 | 0 | — | — | 0 |
| **total** | **3,242** | **1,165** | **405** | **760** | **760** |

This reproduces INV-1's 760 = 369 + 391 exactly.

### §59.2 THE EVT RE-CAPTURE — INTEGRITY BARS, REGISTERED

These are bars on **the rig**, and they are the only things about the re-capture
that can be registered in advance.

1. **Every new capture banks `evt.hold_bits = 12`** and **`evt.hold_applied ==
   evt.hold == 300`**.  A capture that banks anything else is not banked.
2. **`timed_fuzz.f46_invalidated` returns False on all 760 by arithmetic**, with
   no list edited and no file renamed, and `timed_fuzz`'s `INVALIDATED` line
   drops to **0**.  This is INV-1's own stated closure mechanism and it is the
   bar, not a description of one.
3. **The wire is proved before the population is captured** (§59.3 item 3): a
   hold > 255 is written through `v30ctl.set_event`, `EVT_CFG` is read back, the
   split packing `[23:16]` + `[30:27]` is confirmed to round-trip, and one
   directed capture demonstrates a hold of 300 clocks actually held on the pin.
   **If the readback does not round-trip, NOTHING is re-captured** and the
   session stops at that point with the finding.
4. **Nothing is deleted.**  The 760 original entries are archived byte-identical,
   with a sha256 manifest, OUTSIDE `tests/v30/fuzz_bank/` — because
   `check_fuzz_bank` globs `*/seeds/*.json.gz` under that root and an archive
   placed inside it would silently grow the 3,242-seed corpus, which is the
   second falsehood INV-1 refused to introduce to record the first.
5. **The image is hash-checked per seed before its capture** against the banked
   `image_sha256`.  A GEN-DRIFT seed is not captured and is reported.

**NO BAR IS REGISTERED ON THE CHIP's CYCLE BEHAVIOUR.**  What the part does with
a *true* 300-clock INT level has never been observed in this project.  It is a
MEASUREMENT and it is registered fresh: whatever `timed_fuzz --evt-replay`
reports over the re-captured 1,008 is the number, for both engines, and the old
`EVT 192/1,008` / `709/1,008` are STRUCK and are not a floor, a ceiling or a
comparison.  In particular **it is NOT registered that the ucore improves.**

*What would make the re-capture itself unreadable*: the socket failing to enter
its handler at all under a 300-clock level (a wedged or runaway image), or
`event_fired` false on a seed whose old capture had it true.  Both are reported
as rig findings, not scored.

### §59.3 THE BITSTREAMS AND THE BOARD LEGS

**BS-A** = HEAD, 12-bit `evt_hold`, **`X1_AD_RETENTION` NOT defined** →
**FLASH #4**.  This is the golden-and-population-capture bitstream and every
item below except §59.5 runs on it.

**BS-B** = BS-A + `X1_AD_RETENTION` → **FLASH #5**, and it exists for the X1
after-leg and nothing else.

**THE RETENTION-vs-SOCKET FINDING, TAKEN FROM THE RTL AND NOT ASSUMED.**
`hdl/rtl/system_large.sv:464`:

```verilog
assign hb_ad_sample  = cfg_use_core ? core_ad_eff : NEC_AD;
```

`core_ad_eff` is the retained signal and it is selected **only when
`cfg_use_core = 1`**.  At `use_core = 0` — every socket capture, every golden,
every emission — `hb_ad_sample` is `NEC_AD`, the physical pins, and the
retention model is not in the path at all.  **So the retention cannot touch a
socket capture.**  Recorded, and *not* used: goldens and the 760 are captured on
**BS-A only** anyway, because a bitstream difference that is inert by reading is
still a bitstream difference, and §55.2 item 5's lesson is that a controlled
substitution must be declared rather than assumed.

**THE INSTRUMENT-INERTNESS GUARD ON BS-B, AND WHY IT IS REGISTERED HERE.**  The
retention model is written with `core_ad[gad] === 1'bz`.  That is a four-state
comparison on an internal `tri` net, and Quartus resolves internal tri-states to
multiplexers.  If synthesis constant-folds `core_ad_z` to 0 then
`core_ad_eff === core_ad`, the `core_ad_hold` register has **no fanout**, and
the fitter deletes it — and BS-B is BS-A wearing a different name.  **A run of
the X1 after-leg on an inert BS-B would report "116 survive", which reads
exactly like a REFUTATION and would be an instrument failure.**  So, registered
before the build:

* **LIVENESS TEST**: the BS-B fit must show the **20 `core_ad_hold[*]`
  registers present** (`g_ad_ret` / `core_ad_hold` in the fitter's node list)
  **and** the Analysis & Synthesis log must carry no warning that the
  `z`-comparison was folded to a constant.
* **If the liveness test fails, the X1 fabric after-leg is NOT RUN and is
  reported as BLOCKED on a synthesis limitation** — with the mechanism named —
  and the C11 attribution stays NOT ESTABLISHED.  It is *not* reported as a
  refutation.  A null instrument produces a null result and this session will
  not launder one into the other.

### §59.4 THE X1 FABRIC BARS — QUOTED, NOT PARAPHRASED

From §56.3a, verbatim:

> * **THE BAR, BOTH HALVES, AND BOTH ARE REQUIRED**:
>   1. **ALL 116 fabric-only cells CLOSE** — the fabric total goes to **259/283**,
>      equal to the TB's, not merely toward it.  A partial close means the class
>      was not one mechanism and the residue is the core's.
>   2. **NOTHING ELSE MOVES**: `HLT.RES` stays cell-identical at 47/49, 48/49,
>      24/25, 24/25; **every `HLT.INT` cell matches its OFFLINE result cell for
>      cell**, not merely in total; no non-INTA row acquires a new first
>      divergence; **the F42-signature count stays ZERO**; the socket control
>      stays 49/49; and the `use_core=0` chip-path proof stays MATCH over 800
>      rows with first light 800/800 ×3.
> * **WHAT REFUTES THE ATTRIBUTION**: any of the 116 still failing with the
>   retention model demonstrably supplying the prior driven data phase at the
>   INTA's T1, or any fabric-only NON-INTA divergence appearing.  A surviving
>   divergence is **reclassified as CORE-OWNED** unless a separately
>   pre-registered mechanism is established for it — exactly as F42's 17 turned
>   out to be the core's, and it is reported as a refutation and not
>   re-explained.

SM1 met both halves on the Verilated leg (§58.6): `tb_sys` baseline **143/283**
— the fabric number exactly, 116 base-only failures, 116/116 with an INTA row as
the golden's first-divergence row — and with `X1_AD_RETENTION` **259/283**,
closed 116, **survived 0**, **0** cells differing from offline.  **This session
runs the leg the bar was actually written on.**

### §59.5 THE PREDICTIONS, WHERE AN HONEST PREDICTION EXISTS

Registered.  Each is falsifiable and each is reported as registered.

1. **BS-A's fabric baseline on the 283 cells is 143/283**, with 116 fabric-only
   failures, 116/116 on an INTA row.  The reasoning is stated so the prediction
   can be wrong for a reason: BS-A differs from FLASH #3 only by the `evt_hold`
   widen, the four HLT sweeps carry `hold = 0` (the invalidation sweep measured
   this and cleared them), bits `[30:27]` of `EVT_CFG` were written as zero by
   the old host, so the widen is **inert on this population by construction**;
   and SM1's `tb_sys` baseline reproduced 143/283 cell for cell.
   *Falsifier*: any total other than 143/283 on BS-A.  A move here is a
   **bitstream-vintage finding** and it invalidates the comparability of the X1
   before/after, which is why it is taken FIRST.
2. **The socket control reproduces the golden 49/49** on BS-A
   (`s10-hltsweep-w0` / `HLT.RES`, `EMIT_USE_CORE=False`, `use_core=0`).  This
   is the rig-integrity leg, not a result: **if it moves, nothing else in §59 is
   readable.**
3. **`use_core=0` boot vs the standing golden MATCHes over 800 rows** on BS-A,
   taken FIRST, before anything else.
4. **X3, the b3 priority tranche re-captured on BS-A**: no prediction is
   registered on the total.  §55.2 item 6 declared its 176/178 a pass-3
   bitstream number carried forward under a controlled offline substitution;
   this session removes the substitution.  The honest statement is that 176/178
   is the number being *checked*, not a bar — a move in either direction is the
   finding, and V0-V5 are re-scored as measured.
5. **R6**: no prediction.  Banking the s10/s13 per-repetition rows makes
   `HLT.INT_w2_d0`'s `stable_identical: false` *verifiable*; whether it verifies
   as the same pad artefact as `HLT.INT_w0_d0` is the measurement.  §26.1's
   caveat is carried: `stable_key` changed at §26.1 and keys stored before it
   are internally valid and **not comparable across the change**, so this
   session compares only keys it computes itself.
6. **The re-captured EVT column**: NO PREDICTION, per §59.2.

### §59.6 SEQUENCING, AND WHY IT IS THIS ORDER

A capture on the wrong bitstream is worthless, so everything BS-A-dependent
precedes FLASH #5:

1. FLASH #4 (BS-A) + `v30ctl.py` deployed to the board + `div_guard` PINNED +
   `use_core=0` 800-row boot MATCH + the 12-bit-hold wire proof (§59.2 item 3).
2. The 760-seed EVT re-capture (socket, `use_core=False`).
3. R6 per-repetition rows (socket).
4. X3 priority tranche (both legs).
5. X1 baseline in fabric (`use_core=1`) + the 49/49 socket control.
6. FLASH #5 (BS-B) — **only if the §59.3 liveness test passes** — and the X1
   after-leg.
7. FLASH #6 back to BS-A if any BS-A capture remains; `board_idle`; the board
   left at `use_core=False` and `DIV_OF_RECORD = 8`.

A wedged board is a STOP with the state documented, not an improvisation.

---

## §59.7 SESSION SM2 — WHAT HAPPENED

Everything below was measured after §59.0-§59.6 was committed (`64641a5644`).
Reported against the registration, never restated.

### §59.7.0 THE TWO BUILDS

`quartus_sh --flow compile nec_test -c nec_test_ucore`, 17.1.0 Lite,
`5CSEBA6U23I7`.

| | **BS-A** (FLASH #4) | **BS-B** (not flashed) |
|---|---|---|
| `X1_AD_RETENTION` | not defined | defined |
| wall | 8:36 | 10:50 |
| A&S / Fitter errors | **0** | **0** |
| inferred latches / `lpm_divide` | **0 / 0** | 0 / 0 |
| ALMs | **11,164 / 41,910 = 27 %** | 11,154 / 41,910 = 27 % |
| registers | 6,129 | 6,105 |
| RAM blocks | 105 / 553 = 19 % | 105 / 553 |
| **Fmax vs the registered ≥ 32 MHz** | **45.19 MHz (+41 %)** | — |
| worst setup / TNS | **+9.123 ns, TNS 0.000 on EVERY clock domain** | — |
| worst hold / TNS | **+0.252 ns, TNS 0.000** | — |
| `.sof` sha256 | **`67ddd59413d58934716260966cfc981f4f0d7065e90b8a8e655010e7687e4320`** | `0d2ef4bfaa8134e7c449101f0b58392b22e9e5976221fb3e7e30799aa686dc1c` |
| `.rbf` sha256 | `30139a991a605eac3327e0d9668ed5c6740e9ecc07111bea7155b361e9c19740` | — |

`gen_ucore_qsf --check` was up to date before each build and is up to date now;
the BS-B macro line was added to `nec_test.qsf`, propagated by
`gen_ucore_qsf.py`, and **reverted** — it is not in the tree.

BS-A is 45.19 MHz where U5's was 48.03; that is placement, not a constraint
change (same SDC, same settings, one register file widened by 4 bits), and the
registered bar is ≥ 32 MHz with margin.

### §59.7.1 THE §59.3 LIVENESS TEST ON BS-B — **FAILED. THE X1 FABRIC
AFTER-LEG IS BLOCKED AND IS *NOT* A REFUTATION.**

Registered before the build, and it fired exactly as registered.

| the test | result |
|---|---|
| the 20 `core_ad_hold[*]` registers present in the fit | **ABSENT — 0 occurrences** in `nec_test_ucore.fit.rpt` AND in `.map.rpt`; `g_ad_ret` likewise 0 |
| the macro actually reached the compiler | **YES** — `Info (293029): New assignment VERILOG_MACRO with value X1_AD_RETENTION=1 has been added` |
| `core_ad` in synthesis | `Warning (13048): Converted tri-state node "…|core_ad[15]" into a selector`, ×16 |

**THE MECHANISM, ISOLATED.** Rather than argue from an absence in a 4 MB
report, the construct was compiled ALONE — a two-driver `tri` net, the same
`=== 1'bz` test, the same hold register, nothing else
(`~/.cache/ucsimt-tmp/sm2/ztest/`):

```
Warning (21074): Design contains 1 input pin(s) that do not drive logic
    Warning (15610): No output dependent on input pin "clk"
Info (21057): Implemented 20 device resources after synthesis
    Info (21061): Implemented 5 logic cells
```

**The clock drives nothing.** Quartus 17.1 folds `net === 1'bz` on an internal
tri-state to a constant, so `core_ad_eff ≡ core_ad`, the hold register loses its
fanout and is deleted at elaboration. **BS-B is BS-A with a different sha256.**

So, per §59.3: **the X1 fabric after-leg was NOT RUN, FLASH #5 was NOT taken,
and C11's `NOT ESTABLISHED` stands.** Running it would have reported
"116 survive", which reads exactly like a refutation and would have been an
instrument failure — the registration exists because that sentence is easier to
write than to retract.

**WHY THE OBVIOUS REPAIR IS NOT TAKEN HERE.** A synthesizable keeper needs an
"is anyone driving" term, and inside `system_large` the only honest source of it
is the core's own output enable — which is not a port. §56.3a forbids
manufacturing it in the harness *by name*, and it is right to: that is a fitted
rule in the exact place the intervention must not have one. Choosing a
different mechanism after seeing this result would also be choosing an
instrument after seeing a result. **It is handed on unrun, with its cause named
and reproduced in nine lines of Verilog** — the disposition F43 and §56.3a have
both carried.

### §59.7.2 FLASH #4, AND THE BOARD SANITY LEGS

`sw/safe_flash.sh hdl/output_files_ucore/nec_test_ucore.sof`, PREP → FLASH →
VERIFY all clean, ledger appended (`sw/testdata/flash_log.jsonl`, sha256
`67ddd59413d5…`). **`/media/fat/v30/v30ctl.py` was replaced with the repo's
12-bit copy first** (the old one preserved on the board as
`v30ctl.py.pre-sm2.bak`, md5 `8eff261e3b…`) — §59.0's recorded rig fact, acted
on rather than discovered later.

| leg | registered | **measured** |
|---|---|---|
| `check_ab_hw all 800` chip-vs-golden | MATCH 800 (§59.5 #3) | **MATCH over 800 rows** |
| core-vs-chip | first light | **MATCH over 800 rows** |
| core-vs-golden | first light | **MATCH over 800 rows** |
| `div_guard` | PINNED | **`div=8 (4 MHz), commanded by this connection` → PINNED**, on every probe |

### §59.7.3 THE WIRE PROOF — §59.2 ITEM 3, **BOTH HALVES**

**The register.** `sw/inv1_recapture.py probe`, run THROUGH THE BOARD's own
`v30ctl.py` (not a host reimplementation — that is the point). Host packing
self-test 63/63; the board reports `RIG_EVT_HOLD_BITS = 12`; and `EVT_CFG`
reads back correctly for every case including the ones the 8-bit rig could not
express:

```
delay=0     hold=256  pin=0  raw=0x88000000 -> hold 256   OK
delay=0     hold=300  pin=0  raw=0x882C0000 -> hold 300   OK
delay=0     hold=4095 pin=0  raw=0xF8FF0000 -> hold 4095  OK
delay=65535 hold=300  pin=2  raw=0x8A2CFFFF -> hold 300   OK
```

`0x882C` is the split doing its job: `[23:16] = 0x2C = 44` — the exact value
F46 truncated to — plus `[30:27] = 1`, i.e. 256. **8/8 round-trip.**

**THE PIN.** A register that carries 300 is not a scheduler that counts to 300,
and INV-1's falsifier is written on the pin. `inv1_recapture.py holdproof`: ONE
seed, ONE image, five directives differing only in `hold`, INTA T1 rows counted:

| `hold` | 2 | 44 | 255 | **300** | 600 |
|---|---|---|---|---|---|
| INTA T1 rows | 2 | **2** | 6 | **6** | **12** |

The seed's OLD banked capture has **2**. So the part entered its handler ONCE
under what the rig actually applied and **three times** under what the bank
asked for, and at 600 it enters six times. **The hold is monotone past 255 and
the widen is on the wire.** This is F46's own mechanism
(`ucore_gaps_2026-08-04.md` §T.5) measured directly on silicon rather than
inferred from a score.

### §59.7.4 THE RE-CAPTURE OF THE 760 — **DONE, 0 ERRORS, 0 GEN-DRIFT**

Socket, `use_core=False`, `div=DIV_OF_RECORD=8`, per-seed image hash-check
against the banked `image_sha256` before every capture.

```
CAPTURE: 760 new, 0 already present, 0 errors, 0 gen-drift, 45s
```

`evt_fired` **760/760**; no seed ran away or failed to enter, so §59.2's
"unreadable" conditions did not arise. Full per-clock rows plus a sha256 per
capture are retained at `sw/testdata/inv1-recapture/raw/`.

**WHAT THE PART DOES UNDER A TRUE 300-CLOCK LEVEL — the measurement §59.2
registered fresh, and it is the whole of INV-1 in one table:**

| INTA T1 rows in the capture | 0 | 2 | 4 | 6 | 8 | 10 |
|---|---|---|---|---|---|---|
| OLD (the 8-bit rig, hold applied 44) | 28 | **732** | 0 | 0 | 0 | 0 |
| **NEW (hold applied 300)** | 21 | 1 | 40 | 125 | **265** | **308** |

Every one of the 760 differs from its predecessor. Under the applied 44 the
socket entered its handler ONCE in 732 of 760 seeds; under the banked 300 it
enters two to five times. **A predicting engine was being scored against the
first table while being handed the second table's directive.** That is the
entire content of §T.5's "547 ucore-only non-exact seeds".

### §59.7.5 THE RE-BANK — IN PLACE, WITH THE ORIGINALS ARCHIVED

**Archive first**: `sw/testdata/inv1-archive/{mc1,mc2}/seeds/` — 760
byte-identical copies with `SHA256SUMS` (sha256
`6f79283222d169fdf1f7a8e599c403faacdd0d8d8801abb55c567d89a392355a`) and a
manifest. **OUTSIDE `tests/v30/fuzz_bank/`**, because `check_fuzz_bank` globs
`*/seeds/*.json.gz` under that root and an archive inside it would have silently
grown the 3,242-seed corpus.

Then the 760 entries were **rewritten in place** — which is INV-1's own stated
closure mechanism, *"the seeds re-enter the gate without anyone editing a list"*
— carrying `evt.hold_bits = 12`, `evt.hold_applied = 300`, and a `recapture`
block naming the bitstream, the flash, the prior `chip_rows` sha256 and the
archive path.

`replay_verdict` was **recomputed**, because leaving it would have made
`check_fuzz_bank` report 700-odd spurious verdict moves, and recomputing it
SILENTLY would have made that gate vacuous on these seeds. So it is recomputed
and the movement is REPORTED — and the movement is itself a result:

| banked replay verdict → re-captured | seeds |
|---|---|
| `FUNCTIONAL` → **`TIMING`** | **372** |
| `FUNCTIONAL` → `FUNCTIONAL` | 348 |
| `FUNCTIONAL` → **`KNOWN_ACCEPTED`** | **18** |
| `TIMING` → `TIMING` | 20 |
| `KNOWN_ACCEPTED` → `KNOWN_ACCEPTED` | 2 |
| **worse** | **0** |

**390 of 760 improved and none got worse.** A capture taken under the directive
the bank records stops looking like a functional divergence, because it never
was one.

### §59.7.6 THE §59.2 INTEGRITY BARS — **ALL MET**

```
=== INV-1 CLOSURE BARS (§59.2) ===
  bar 1  hold=300 entries with hold_bits=12 and hold_applied=300: 760/760   MET
  bar 2  f46_invalidated True over the whole bank: 0                        MET
  bar 4  archived originals: 760                                           MET
  (evt-armed banked seeds: 1165)
```

and `timed_fuzz` no longer prints an `INVALIDATED` line at all, for either
engine — the exclusion self-healed by arithmetic, with no list edited and no
file renamed, exactly as INV-1 said a derivation would.

### §59.7.7 THE RE-OPENED EVT COLUMN — **NEW MEASUREMENTS, NO BAR**

`timed_fuzz --evt-replay`, both engines, 3,242 banked seeds, 2,710 scored,
532 `OPEN_BUS`.

| column | **ucore** | **sim** | status |
|---|---|---|---|
| **REGISTERED** | **1,483 / 1,702 (87.1 %)** | **1,272 / 1,702 (74.7 %)** | **UNCHANGED**, to the seed. The control that says the re-capture touched nothing it should not have. |
| **EVT**, full 1,008 | **468 / 1,008 (46.4 %)** | **363 / 1,008 (36.0 %)** | **NEW.** The gate is UN-SUSPENDED. |
| **COMBINED** | **1,951 / 2,710 (72.0 %)** | **1,635 / 2,710 (60.3 %)** | **NEW.** |
| `INVALIDATED` | **0** | **0** | closed |
| `BOUND WARNINGS` / `ENGINE ABORTS` | 5 / 0 | — | unchanged |

**The column decomposes, and the decomposition is the control:**

| sub-population | ucore | sim |
|---|---|---|
| the **248** never poisoned (`hold = 2`) | **170 / 248** | **144 / 248** |
| the **760** re-captured | **298 / 760** | **219 / 760** |
| **total** | **468 / 1,008** | **363 / 1,008** |

The 248 are **identical to SM1's interim sub-gate, seed for seed** — nothing in
the re-capture moved a seed it did not touch. And on the 760 the ucore went
**22 → 298** while the model went **565 → 219**.

**THE SIGN FLIPPED, AS INV-1 PREDICTED IT WOULD.** As banked, the EVT column
said the ucore LOST to the model by 517 seeds. On captures taken under the
directive the bank actually records, **the ucore beats the model by 105**
(46.4 % vs 36.0 %). SM1 predicted this from the un-poisoned 248 alone, where the
margin was 26; the corrected full column reproduces the sign and widens it.
§T.5's 547 "ucore-only non-exact" seeds were the rig.

### §59.7.8 R6 — **CLOSED, AND VERIFIED**

`sw/r6_perrep.py` (new): the per-repetition rows `reps_capture` never kept.
Every cell in the banked sweeps recorded `stable_identical: false`, plus §26.1's
reference cell, **10 repetitions each, full rows banked per repetition**
(`sw/testdata/r6-perrep/`).

| cell | source | distinct KEYS / 10 | distinct RAW / 10 | rows that differ | at/after the first T1 | columns |
|---|---|---|---|---|---|---|
| `HLT.INT_w0_d0` | `s10/s2-hltsweep` | **1** | 6 | 0-8 | **0** | mux only |
| **`HLT.INT_w2_d0`** | `s13/p1b-ahsweep` | **1** | 10 | 0-8 | **0** | mux only |
| `INT.90_w1_d0` | `s10/s1-tranche` | **1** | 3 | 0-8 | **0** | mux only |
| `NMI.90_w1_d0` | `s10/s1-tranche` | **1** | 2 | 0-8 | **0** | mux only |
| `HLT.INT_w1_d0` | `s10/s1-tranche` | **1** | 6 | 0-8 | **0** | mux only |

The first T1 is row **9** in every cell. Every difference between any two
repetitions lies on rows **0-8** — before the part has driven the bus once — and
only on the MULTIPLEXED pads (`ad_addr`, `ad_data`, `ps`, `ube_n`). The
DEDICATED pins (`t`, `bs_early`, `qs`, `lock_n`, `rst`) differ **nowhere, in any
cell, in any repetition**. That is §26.1's signature exactly.

**`HLT.INT_w2_d0`'s instability IS the same pad artefact as `HLT.INT_w0_d0`'s:
VERIFIED.** And all five cells are `stable_identical: TRUE` under the CURRENT
key — their banked `false` was computed with a PRE-§26.1 key, which §26.1's own
caveat says is not comparable across the change. This probe compared only keys
it computed itself, on rows it captured itself, in one session.

**An independent corroboration fell out of X3** (§59.7.9): of the 200 b3 socket
captures, **27 differ from the pass-3 socket capture of the same seed, and the
differences are on rows 0-8 in the multiplexed pads with ZERO rows at or after
the first T1** — the same artefact, on a different population, across two
bitstreams and two sessions. *Nothing on the die is wasted: a multiplexed pad
with nothing driving it holds the last thing that did, and before the first T1
that is the previous program's residue.*

### §59.7.9 X3 — THE PRIORITY TRANCHE, RE-CAPTURED ON THE SHIPPED BITSTREAM

§55.2 item 6 declared 176/178 a **pass-3 bitstream** number carried forward
under a controlled offline substitution. The substitution is now REMOVED: both
legs re-captured on FLASH #4, into `raw_chip_f4` / `raw_core_f4` beside the
originals (never over them), and scored against the socket capture taken on the
SAME bitstream.

| leg | **FLASH #4** | pass-3 (for reference) |
|---|---|---|
| `core_f4` — the ucore in fabric | **176 / 178 (98.9 %)**, residue `bs = 2`, excused 22 | 176/178, `bs = 2` |
| `chip_f4` — the socket against itself | **178 / 178 (100.0 %)** | — |

**No prediction was registered on this total and none is claimed; it is reported
as measured, and it reproduces.** §X.3's *"one thing NEITHER leg covers"* is
closed: the shipped bitstream's own fabric number is 176/178 with the same
two-seed `bs` residue, so the offline inertness argument was correct.

### §59.7.10 X1 — THE FABRIC **BASELINE**, ON BS-A

§59.5 prediction 1, and it is the one that had to be taken first.

| sweep / form | §56.1 (FLASH #3) | **FLASH #4** | offline |
|---|---|---|---|
| `s10-w0` `HLT.INT` | 0/48 | **0/48** | 44/48 |
| `s10-w0` `HLT.RES` | 47/49 | **47/49** | 47/49 |
| `s10-w1` `HLT.INT` | 0/46 | **0/46** | 42/46 |
| `s10-w1` `HLT.RES` | 48/49 | **48/49** | 48/49 |
| `s13-w2` `HLT.INT` | 0/21 | **0/21** | 16/21 |
| `s13-w2` `HLT.RES` | 24/25 | **24/25** | 24/25 |
| `s13-w3` `HLT.INT` | 0/20 | **0/20** | 14/20 |
| `s13-w3` `HLT.RES` | 24/25 | **24/25** | 24/25 |
| **total** | **143/283** | **143 / 283** | 259/283 |

**PREDICTION 1 MET, cell for cell and form for form.** Fabric-only failures
**116**, and **116 of 116** have an `INTA` / `T1` row as the golden's
first-divergence row — read off the golden's own bus-status field, not off a
name. The `evt_hold` widen is inert on this population, as registered.

**The socket control, §59.5 prediction 2**: `s10-hltsweep-w0` / `HLT.RES`, same
driver, `EMIT_USE_CORE=False`, **49 / 49 vs the golden. MET.** The
rig-integrity leg did not move, so the section is readable.

Captures: `sw/testdata/x1-retention/*.fab_f4.json.gz` and `*.soc_f4.json.gz`,
beside SM1's Verilated `base`/`ret` legs. `sw/testdata/u4-f42/` is untouched and
still holds §56's FLASH #3 capture.

### §59.7.11 A RIG-INTEGRITY FINDING — **`s10_board` / `s13_board` COULD NOT
TAKE A CAPTURE AT HEAD**

Found by running one. `sw/s10_board.py:102`'s `capture()` calls

```python
recs, fired, words = run_image(..., want_fired=True, want_raw=True)
```

and **`sw/v30run.py`'s `run_image` has no `want_raw` parameter** — it never has:
`git log --all -S want_raw -- sw/v30run.py` is EMPTY on every branch. The call
raises `TypeError` immediately. `s10_board.capture()` is the entry point for
`reps_capture`, which is what `s13_board ahsweep`, `s10_board` and every
sweep-emission path go through, so **no s10/s13 probe could run at HEAD on this
branch.** It has been that way since ADDENDUM #6 landed the call
(`400ccbb014`, 2026-08-02); the working tree that took those captures carried a
`v30run.py` that was never committed.

This is the vacuous-gate failure mode the project already has a rule about, in a
place no gate looks: *nothing in `standing_gates.md` runs an s10/s13 probe*, so
the breakage was invisible until something needed the board.

**REPAIRED**, minimally and in the one honest place: `ServeRunner.run` and
`run_image` gain `want_raw`, returning the undecoded 64-bit capture words that
were **already being unpacked and thrown away** two lines above the return. No
behaviour changes for any existing caller. The blackbox retention rule (*full
per-clock rows + sha256, never digests alone*) is what wants those words, and
`r6_perrep.py`'s per-repetition `raw_sha` is computed from them.

*Falsifier for the claim that this is now fixed*: `sw/r6_perrep.py capture`,
which is a live s10/s13-path probe and ran 50 captures through it this session.

### §59.7.12 THE BOARD, LEFT

`board_idle()` run **twice**; `div_guard` **PINNED** at the close; **two
consecutive idle captures, 4,063 rows each, byte-identical**
(sha256 `9a7543ca0358973c…` both times). Final `v30ctl.py status`:
`use_core: False`, `cfg 0x00ff0008` (large mode, `div = 8`),
`ctrl 0x5` = `HOST_RESET | SKIP_PWRUP` — the normal parked state every capture
ends in, with the socketed part held in reset. **The board carries BS-A
(FLASH #4, `67ddd59413d5…`) and is not wedged.** FLASH #5 was not taken and
FLASH #6 was not needed: nothing was ever captured on a bitstream other than
BS-A.

### §59.7.13 `check_fuzz_bank` OVER THE RE-BASED CORPUS — **PASS, WITH ONE
REGISTERED CONSEQUENCE THAT IS NOT SMOOTHED**

The 3,242-seed replay-regression control was re-run over the corpus the
re-capture changed. Nothing about it was adjusted first.

```
check_fuzz_bank: PASS | 3242 banked seeds | stable 3242 improved 0 worse 0
                      | gen_drift 0 regen_err 0 | float-floor 0
                      | new-sig TIMING 166
```

**`stable 3242`, `worse 0`, `gen_drift 0`, `float-floor 0`** — every banked
seed, re-captured and untouched alike, round-trips to the verdict it now
carries, and no image drifted.

**`new-sig TIMING 166` is real and it is registered, not explained away.**
`check_fuzz_bank` WARNS on it and **`check_fuzz_bank --strict` now FAILS on
it.** Attributed by predicate over the artifact:

| where the 166 sit | seeds | distinct signatures |
|---|---|---|
| entries carrying a `recapture` block (the 760) | **166** | **140** |
| every other banked seed | **0** | **0** |

**Zero on any seed this session did not touch**, which is the same control the
248 gave for the EVT column. The cause is mechanical: 372 of the 760 moved
`FUNCTIONAL → TIMING`, and a seed that was never a TIMING seed never had a
TIMING signature in `tests/v30/fuzz_bank/sig_ledger.json` (11,705 signatures,
all of them recorded from captures taken under the truncated hold).

**THE NOVELTY LEDGER WAS NOT EDITED, DELIBERATELY.** Adding 140 signatures to a
NOVELTY register in order to turn a warning green is a change to what "novel"
means for every future campaign, and it would have been made by the session that
caused the warning. It is a decision, and it is routed as one. Until it is
taken, the honest statement of the gate is:

> `check_fuzz_bank` **PASS**; `check_fuzz_bank --strict` **FAILS on
> `new-sig TIMING 166`**, all 166 on re-captured seeds, cause understood,
> ledger admission NOT taken.

## §60 SESSION SM3 — THE RESIDUE CENSUS, AND TWO LANDINGS

**2026-08-04, branch `ucsim`, from HEAD `369e4953ce`.  Offline only — banked
captures, Verilator and the C++ model.  NO BOARD CONTACT.**  The first working
sitting of the silicon-match phase (task #36).  SM1 repaired the rig and opened
the invalidation register; SM2 re-captured the 760 and un-suspended the EVT
column; **SM3 asks what is actually left.**

The census itself is a document of its own — **`docs/notes/sm3_residue_census_2026-08-04.md`** —
because it is the artifact the rest of the phase is planned against.  This
section is the ledger record: what moved, what was landed, and what was refuted.

### §60.1 ITEM 0 — THE `sig_ledger` ADMISSION, WITH ITS CONTROL

§59.7.13 routed the admission as a decision and did not take it.  The decision
was taken by the coordinator; SM3 executed it, **control first**.

**The control is a full re-derivation, not a re-reading of SM2's report.**
`sw/sm3_sigctl.py` (new) replays every one of the 3,242 banked seeds through the
SAME `check_fuzz_bank.replay_classify` the gate uses, and records per seed the
verdict, the signature, whether that signature is already in the ledger, and
whether the seed carries a `recapture` block with `evt.hold == 300` **and**
`evt.hold_bits == 12`:

```
sm3_sigctl: 3242 banked seeds, 11705 known signatures
new-sig TIMING seeds: 166   distinct signatures: 140
  on RE-CAPTURED seeds : 166
  on any OTHER seed    : 0
  failing the control  : 0
errors: 0  gen-drift: 0
```

and, by arithmetic over the same artifact, `stable 3242 improved 0 worse 0`.
**SM2's attribution reproduces exactly.**

**AND THE GATE ITSELF WAS RE-RUN IN FULL AFTER THE ADMISSION, UNMODIFIED:**

```
check_fuzz_bank: PASS | 3242 banked seeds | stable 3242 improved 0 worse 0
                      | gen_drift 0 regen_err 0 | float-floor 0
                      | new-sig TIMING 0
rc = 0   under --strict
```

**A RIG-INTEGRITY FINDING FELL OUT OF TAKING THE CONTROL SERIOUSLY.**
`hdl/tb/obj_dir/Vtb_v30_core` — the FSM TB that `check_fuzz_bank` binds to
through `check_seq.BIN` — was built at 05:43 from a `tb_v30_core.sv` that commit
`5c5fdbf50a` changed at **07:28**.  It was **STALE**, and nothing could see it:
`check_seq` never calls `check_core.build()`, and `check_core.build()` is the
only thing in the tree that carries `tb_v30_core.sv` in a dependency check.  The
binary was **REBUILT** and the control re-run on it, **and it reproduces SM2's
166 / 140 exactly** — so no figure was scored wrong.  This is the vacuous-gate
pattern's fifth incarnation and it is recorded in the census §7 with a suggested
standing fix (have `check_seq` build, or have `check_fuzz_bank` assert the
binary is newer than its dependency set).  *Not taken here; it is a change to an
archived gate's plumbing and it belongs to whoever next opens that path.*

**THE ADMISSION.**  `sw/sm3_sig_admit.py` (new, and deliberately a committed
tool rather than an ad-hoc edit so the act is reproducible and its control is
re-runnable).  It **refuses to write** unless every signature it is about to
admit is reachable only from a true-300 / 12-bit re-captured seed.

* 140 signatures added to `sigs`, in `fuzz_bank._update_ledger`'s own entry
  shape plus one extra `admitted` key, so `check_fuzz_bank`'s reader
  (`set(json["sigs"])`) is unaffected and no other consumer sees a schema change;
* a new top-level **`admissions`** list carries the event once: date, why, the
  control, the gate before and after, the counts, and the full signature list;
* **`sigs` 11,705 → 11,845; 0 removed; every pre-existing entry byte-identical**
  (`sigv` and `legacy_baseline` untouched, verified by comparison against a
  pre-edit copy).

*Why an `admissions` record and not a silent insert*: the ledger is a NOVELTY
register.  A signature that enters it without provenance makes the next
campaign's "this is new" mean something different from this campaign's, and
there would be nothing in the file to say so.

**ADDENDUM, 2026-08-04 (SM3 sitting 5, §64.4).**  Codex found that the control
above could not be re-run after its own admission — `sm3_sigctl.py` read the
LIVE ledger, which by then contained the 140.  `--ledger <path>` was added, the
pre-admission ledger retrieved from git
(`git show 369e4953ce:tests/v30/fuzz_bank/sig_ledger.json`, **11,705**
signatures against the live file's 11,845), and the control re-run on the
current tree: **166 new-sig TIMING seeds / 140 distinct signatures / 166 on
re-captured seeds / 0 on any other / 0 failing the control / 0 errors / 0
gen-drift.**  Reproduced exactly.

### §60.2 THE CENSUS — the headline, and the number that is new

Full tables in `sm3_residue_census_2026-08-04.md`.  The ledger-level facts:

**The EVT partition, measured for the first time on the rebuilt column:**

| population | scored | ucore | sim | ucore-ONLY | sim-ONLY | shared | net |
|---|---|---|---|---|---|---|---|
| REGISTERED | 1,702 | 219 | 430 | **9** | 220 | 210 | +211 |
| **EVT** | 1,008 | **540** | **645** | **5** | 110 | 535 | **+105** |

The REGISTERED row reproduces §58.4 seed for seed.  **The EVT row replaces
SM1's 547 / 269 / 30** — that partition was the rig, and INV-1 struck it; the
ucore's own whole-program event residue that the model does not share is
**FIVE SEEDS**, named in the census §2.2.

**The ucore's EVT family census, its own engine, the first ever taken:**
`PF_GAINED` **463** · `SCHEDULE` 29 · `PF_LOST` 22 · `DATA_SEQ` 14 ·
`TAIL_EXTRA` 5 · `PIN` 4 · `PF_ADDR` 3 = **540**, catch-all EMPTY, 0 `NOW_EXACT`.
The model's, for the same population: `SCHEDULE` **563** · `PF_LOST` 44 ·
`PF_GAINED` 15 · `PIN` 9 · `PF_ADDR` 6 · `DATA_SEQ` 5 · `TAIL_EXTRA` 3 = 645.

**H1 — THE RE-ENTRY ACKNOWLEDGE'S LEAD-IN.  445 ucore seeds + 491 sim seeds,
437 of them the same seed.  The largest single mechanism in the silicon-match
residue, and it is one clock count.**

Of the ucore's 463 `PF_GAINED`, **445 have `INTA` on the chip and `CODE` in the
core at the first cycle the sequences differ**, with `delta = -2` on **445/445**
and the chip's divergent INTA1 T1 exactly **6 clocks after the preceding CODE
fetch's T1** on **445/445**.  A zero-wait fetch is 4 clocks, so **the chip
leaves the bus IDLE for two clocks and then announces the acknowledge.**  The
ucore's prefetcher takes that slot; the model announces on the fetch's own T4.
*Both engines are wrong, in opposite directions, by the same two clocks, on the
same seeds.*

It is not the first acknowledge — the wake from HALT is right in 443/445; it is
acknowledge **#2** in 382 of 445, #3 in 36, #4 in 25.  All wait classes, both
campaigns, `pin = 0` on all 445, no sub-population and no exceptions.

**This is the missing whole-program half of `gaps` §I.3**, whose evidence column
was the EVT population INV-1 suspended.  The column is un-suspended and this is
what it says.  M18 (INTA2's spacing) is unaffected and correct in both engines.

**NOT TAKEN.**  It moves the interrupt-entry anchor, which is spine, and it
needs its own pre-registered before/after on the four `evt` golden cells,
`timed_lawcards`, the b2 tranche and both engines' REGISTERED columns.
Registering it is the next sitting's first job.

*Falsifier*: a seed in the 445 whose chip acknowledge opens at a gap other than
6 clocks after the preceding fetch's T1, or a re-entry acknowledge in which the
chip DOES grant the prefetch slot.

### §60.3 ITEM 2.1 — T8's BYTE-SWAP ATTRIBUTION IS **REFUTED**

`gaps` §T.8 / §49.7 attribute three shared seeds to *"M5b's A0 swapper applied
where the chip does not"*.  Measured row by row (`sw/sm3_bswap.py`, new):

| seed | write | chip | both engines | A0 | UBE_n | model rotation |
|---|---|---|---|---|---|---|
| `mc1/raw_2340_8df9460dd643` | MEMW `03efd` | `35ab` | `ab35` | **1** | 0 | applied |
| `mc2/raw_3868_3995afd408b7` | MEMW `03ef8` | `b6cd` | `cdb6` | **0** | 1 | **NOT applied** |
| `t30-raw/raw_453_99bdf08b95ea` | MEMW `0b97d` | `ad00` | `00ad` | **1** | 0 | applied |
| `t30-raw/raw_624_d20cc1a550cc` | MEMW `9998e` | `f206` | `fa87` | 0 | 0 | n/a (not a swap) |

**`raw_3868` has the OPPOSITE SIGN**: the chip rotates at an EVEN address where
the model does not.  The three do not share a sign, so no removal, narrowing or
inversion of the A0 rotator closes them — and M5b's own four-quadrant
measurement (`88` / `C6.0` / `50`, validated 366/366 over the `88` byte-store
rows) forbids removing it.

What the rows DO establish is better posed: on all three, the chip's driven word
is the rotator applied to **`swap8(OPR_model)`** — *the engines' OPR holds the
same two bytes as the chip's, in the other order.*  **The defect is on the side
that LOADS the datapath, not the side that drives the bus.**  `raw_2340` names
the instruction: `FE F6` (the FE group's undocumented `/6`, mod = 11, `op8 = 1`)
at ROM row **`01CE`**, whose OPR is `35AB` where the chip's is `AB35`; the
seed's own control is two cycles later, where an ordinary `51` PUSH CX (row
`0029`) at an odd stack address splits correctly and both engines agree.

**Reported as a refutation.  NOTHING WAS CHANGED.**  §T.8's sentence should be
read as the observation it is and not as an attribution.

### §60.4 ITEM 2.2 — **I1 LANDED**: the sim's `9D` flag-commit erratum is FIXED

`gaps` §I.1, F39, and the one place this campaign owed the model a fix: the RTL
matches silicon and the MODEL does not.  `sim/exec_impl.h` committed FLAGS when
the micro-row RETIRED; the chip commits at the read's data edge.

**Rendered as the mechanism, naming no opcode.**  A micro-row's destination
write-enable is a LEVEL for as long as the row STANDS, so a destination fed from
the read latch takes the word when the LATCH CLOSES — the T3/Tw → T4 advance,
which is the READY sample.  The BIU is the only thing that knows when that edge
is, so it is the BIU that publishes it (the RTL calls the same edge
`eu_rd_edge`):

```
biu_timed.h    arm_flags_latch(uint16_t* psw)   -- non-null = a standing row
                                                   has FLAGS selected
biu_timed.cpp  in tick(), at ci_ == last_i of a completing EU read and BEFORE
               that same clock's r.ps is composed:  *flags_latch_ = word
biu.h          arm_flags_latch(uint16_t*) {}     -- the functional bus has no
                                                   clock and no T-states
exec_impl.h    the `F` row arms it iff  s1 == OPR && d1 == FLAGS,
               and disarms it after deliver_read()
```

The predicate hits **EXACTLY TWO ROM ROWS** — `007A` (POP PSW) and `01EA`
(RETI), the only rows carrying source `OPR`, destination `FLAGS` and the `F`
interlock; five other rows write FLAGS and none takes OPR through an `F`.  That
is the same pair E1 measured on silicon.  The word is unchanged: `rdq_` is
filled at ISSUE time, so this re-orders the COMMIT and not the data, and
`wr_dst1`'s FLAGS arm writes the identical word again at retire.

**PRE-REGISTERED BAR, and it is met exactly.**  `INT.9D` case 1, row 9 (the
read's own T4), golden vs model:

| | before | **after** |
|---|---|---|
| row 9 composed AD | golden `05FAD2`, model `01FAD2` | golden `05FAD2`, model **`05FAD2`** |

**THE FULL SIM-SIDE REGRESSION, ALL RE-RUN AFTER THE LANDING:**

| gate | registered | **after I1** |
|---|---|---|
| `make -C sim test` (disasm byte-exact) | PASS | **PASS** |
| `timed_gate --suite tests/v30/v0.1 --forms all` | 169,000 / 169,000, row-diffs 0 | **169,000 / 169,000, row-diffs 0** |
| `ulockstep --golden all --cases 50` | 17,350 / 17,350 | **17,350 / 17,350 ALL LOCKSTEP** |
| `timed_wvec_gate` | 88/88, +0.0 % | **88/88, 16,048 vs 16,048, +0.0 %** |
| `timed_enter_replay` | 154/154 ×5 | **154/154 ×5** |
| `timed_ins_replay --raw` | 1,312 / 2,624 | **1,312/1,312 and 2,624/2,624**, 173,556/173,556 same-T1 |
| `timed_lawcards` | 8 GREEN / 0 RED / 3 UNRESOLVED | **8 / 0 / 3** (C6, C7, C11) |
| `timed_fuzz --core sim --evt-replay` | REG 1,272/1,702 · EVT 363/1,008 · COMBINED 1,635/2,710 | **identical, to the seed** |
| `timed_fuzz --core ucore --evt-replay` | REG 1,483/1,702 · EVT 468/1,008 · COMBINED 1,951/2,710 | **identical** (no RTL was touched) |

**Nothing moved except the column the fix is about.**  `ulockstep`'s masked view
was already ALL LOCKSTEP and stays so; what closes is its UNMASKED `9D` T4 PS
nibble, which §42.4 item 4 booked as *"the RTL matches the silicon and the MODEL
does not"*.  **`gaps` §I.1 is CLOSED.**

*Falsifier*: any `OPR -> FLAGS` row whose flag write is NOT visible at its
read's T4, or any third ROM row acquiring that source/destination pair.

### §60.5 WHAT SM3 DID NOT DO, AND WHY

* **No board contact.**  I3's §26.6.4 directed cell — an acknowledge announced
  while another cycle still owns the bus, at more than one wait level — is now
  backed by H1's 445-seed shadow and is the one board request this session
  produces.  **Not taken.**
* **H1 not fixed** (§60.2).  The census's own rule: the session that discovers a
  spine-moving mechanism does not also land it without a pre-registration.
* **The HLT sweeps were not re-run**; the census cites §T.1's 259/283 and its
  13 ucore-only cells rather than re-measuring them.
* **`s15_census` was not modified.**  That it lands 540 EVT seeds in seven
  inherited families with an EMPTY catch-all is evidence the taxonomy
  generalises off the population it was built on.

---

## §61 SESSION SM3, SITTING 2 — H1: MEASURED, DISCRIMINATED ON SILICON, LANDED IN `sim/`

**2026-08-04, branch `ucsim`, from HEAD `6ed8812e18`.  Pre-registration
committed at `72fdaca572` BEFORE the first board contact; the directed cell
then RAN on the socket (FLASH #4, no flashing) and REFUTED the reading that had
been landed, which was re-keyed rather than defended.**  Full record:
`docs/notes/sm3_h1_prereg_2026-08-04.md`.

### §61.1 The chip-side measurement — 2,318 acknowledges, zero exceptions

`sw/sm3_ackgeom.py` (new, a measurement tool) over the 1,008-seed EVT bank.
Every acknowledge that is not the first of its record is preceded on the bus by
a CODE fetch — 2,318 of 2,318 — and

```
    INTA1 T1 = max( F1 + 6 , F1 + L + 1 )
```

with `F1` that fetch's T1 and `L` its length.  The second term is the ordinary
next-cycle slot (M2r's `e+2`) and carries no new number; the first bites at
`L = 4` alone, where it costs exactly **2 clocks**.

Two supporting chip-side measurements, both new and both engine-free:

* `sw/sm3_popgeom.py`, **50,422** flush→pop events over all 3,242 banked seeds:
  the first opcode pop after a flush lands at the refilling fetch's **`e + 3`**
  (`F1 + 5 / 7 / 8 / 9` at `L = 4 / 5 / 6 / 7`).  That is **§11.1 M2r's own law
  re-derived from silicon**, and it says the acknowledge opens BEFORE the byte
  is poppable at every wait level ≥ 1 — so S9a's *"the recognition boundary is
  the retire, not the pop"* STANDS.
* `sw/sm3_ackcmp.py` pairs chip and engine by acknowledge ORDINAL: before this
  sitting the sim was at gap 4 on 1,585 of the 1,597 `L = 4` re-entries and
  EXACT on every `L ≥ 5` one; the ucore inserted a prefetch and landed 2 clocks
  late on 1,117 of 1,289.  **The whole of H1 is the w0 column.**

### §61.2 Two rivals refuted OFFLINE, before the board

* **C0, "`entry = B + 4`"** — the w0 `INT.*` / `NMI.*` goldens are **B-limited
  in 1,266 of 1,800 cases** (measured with `V30SIM_EVTTRACE`) and the model is
  200/200 on them with M14's `B + 2`.  A uniform `+2` moves all of them.
* **C2, "an IE-restoring instruction defers recognition"** — `INT.9D` (POPF)
  and `INT.FB` (STI) are B-limited goldens, 190/200 and 160/200, and exact.

### §61.3 THE DIRECTED CELL — and it REFUTED the landed reading

`sw/sm3_h1_cell.py` (new), socket only, divider pinned with the `div_guard`
readback recorded, **120 captures** retained with full per-clock rows, the raw
64-bit words and `SHA256SUMS` (242 files) in `sw/testdata/sm3-h1cell/`,
`board_idle()` run and OK, single writer confirmed before contact.

Six stimuli: a NOP sled (no redirect at all), `EB 00` near JMPs, far JMPs, a
`CALL next` / `RET` chain, a chain of `CF` IRETs popping PRE-PLANTED frames, and
a `CLI ; POPF` chain.  Assert delay swept, waits 0/1/2/3, hold 16 and 300.

| acknowledge | `nop` | `ebnext` | `farnext` | `callret` | `iretnext` |
|---|---|---|---|---|---|
| **ord 1**, w0, B-limited | 4 | **4** | **4** | **4** | **4** |
| **ord ≥ 2**, w0 / w1 / w2 / w3 | **6 / 6 / 7 / 8** | 6/6/7/8 | 6/6/7/8 | 6/6/7/8 | 6/6/7/8 |

* **C1 (the REDIRECT reading) is REFUTED**: three different queue-flushing
  redirects sit immediately before an ord-1 boundary and pay NO floor.
* **C3 (IRET-specific) is REFUTED**: `iretnext`'s ord-1 acknowledge follows a
  bare IRET with the banked population's own `flush→F1 = 4` spacing and pays
  no floor.
* **What pays it is every acknowledge with an ACKNOWLEDGE BEHIND IT** — in all
  five stimuli, *including a pure NOP sled with no redirect in it anywhere*.
  H1's own name was right: it is the RE-ENTRY.
* `clipopf` produced **NO ACKNOWLEDGE AT ALL** in 24 captures (`fired = True`
  on every one).  The IE-rise question is **NOT ANSWERED**, and *"a `CLI ;
  POPF` chain restoring IE never acknowledges a held INT level"* is booked as
  an open observation.

### §61.4 THE LANDED MECHANISM (`sim/`), and it is one register

**MEASURED.**  `BiuTimed::bnd_pending_` / `bnd_floor_`:

```
   an INTA cycle            ARMS   bnd_pending_
   a flush, while armed     ARMS   the stamp
   the restarted prefetch's GRANT  STAMPS bnd_floor_ = its T1 + 2   (index 2)
   a queue pop              SPENDS bnd_floor_
   boundary_no_pop()        READS  the floor, SUSPENDS the prefetcher,
                                   and CLEARS bnd_pending_
```

i.e. **an acknowledge that has an acknowledge behind it is not recognised
before the restarted prefetcher's INDEX 2** — the cycle-relative instant this
machine already samples the queue counter on (`pf_arm_`; at w0 index 2 IS the
completion eval, M2r).  No new number and no new instant.  The recognition that
pays the floor also holds the prefetcher off, which is the census's two idle
clocks.

**Two bounded claims, both stated because both were TRIED and MEASURED:**

1. the floor is NOT read by the ordinary retire (`opcode_prefetch`).  It is
   unobservable there — after a redirect the pop is byte-limited at `e+3`,
   index 5 or later — and charging the EU to it anyway costs `INT.F3AA` **75 of
   200** at w0.
2. the floor is NOT read by the REP mid-string withdrawal
   (`boundary_no_pop(post_redirect = false)` when `intr_pending`).  A
   withdrawal is not an instruction retire; §26.6.4 already recorded that the
   two populations *"point OPPOSITE WAYS"*.  Flooring it costs `INT.F3AA`
   **26 of 200** at w0.

**THE MECHANISM BEHIND THE ARM IS NOT ESTABLISHED.**  The candidate is the IE
restore — the entry clears IE, the IRET's PSW pop restores it, and a
recognition cannot act on a RISING IE for two clocks — and the cell that would
settle it did not fire.  Recorded as MEASURED with the arm named and the
mechanism OPEN.

*Falsifier*: an acknowledge with a prior acknowledge behind it that opens at a
clock other than `max(F1 + 6, F1 + L + 1)`; a FIRST acknowledge that pays the
floor; or a `clipopf`-shaped cell that acknowledges and pays it.

### §61.5 THE NUMBERS — pre-registered, and reported as registered

**The directed cell, scored against the model on the same 120 captures:**

| | pre-H1 | **after** |
|---|---|---|
| acknowledge clocks reproduced | 249 / 326 | **326 / 326** |

**MOVED UP** (`timed_fuzz --core sim --evt-replay`; bars registered at
`72fdaca572` were EVT ≥ 700 and COMBINED ≥ 1,972):

| column | before | **after** |
|---|---|---|
| EVT | 363 / 1,008 | **780 / 1,008**  (+417) |
| COMBINED | 1,635 / 2,710 | **2,052 / 2,710**  (+417) |

**DID NOT MOVE**, all re-run on the final binary:

| gate | registered | after |
|---|---|---|
| `timed_fuzz --core sim` REGISTERED | 1,272 / 1,702 | **1,272 / 1,702** |
| `make -C sim test` | PASS | **PASS** |
| `timed_gate v0.1 --forms all` | 169,000 / 169,000, row-diffs 0 | **169,000 / 169,000, row-diffs 0** |
| `v0.1-w1` / `-w3` (`--waits 1` / `3`) | 1,200 | **1,200 / 1,200** |
| `v0.1-w1 --forms EB` | 200 | **200** |
| the four `evt` cells | 200 / 1,200 / 200 / 1,200 | **200 / 1,200 / 200 / 1,200** |
| `v0.1-w1evt-biased` | 1,200 | **1,200** |
| the four HLT sweeps | 91/97, 95/95, 44/46, 42/45 | **91/97, 95/95, 44/46, 42/45** |
| `check_boot --timed 220` | MATCH | **MATCH** |
| `timed_scenario` | 18 / 0 / 9 | **18 / 0 / 9** |
| `timed_enter_replay` | 154 / 154 ×5 | **154 / 154** |
| `timed_ins_replay --raw` | 1,312 / 2,624 | **1,312 / 1,312 and 2,624 / 2,624** |
| `timed_wvec_gate` | 88/88, +0.0 % | **88/88, 16,048 vs 16,048, +0.0 %** |
| `timed_lawcards` | 8 GREEN / 0 RED / 3 UNRESOLVED | **8 / 0 / 3** |
| b2 tranche | 154 / 188 | **154 / 188** |

### §61.6 WHAT THIS SITTING DID NOT DO

* **The ucore was NOT changed.**  H1 is landed in `sim/` only.  The RTL leg —
  the same arm and the same index-2 floor in `hdl/rtl/ucore/`, its own full
  regression, `ss_lint`, `ulockstep` and an `SS_VERSION` bump if a flop
  appears — is the next sitting's first job, and `sw/sm3_ackcmp.py --core
  ucore` is the instrument that scores it (the ucore's own before figure is in
  §61.1).
* **H2 was not re-censused.**  Its registered falsifier is *"H1 lands and this
  family does not shrink"*, and the census must be re-taken against the ucore
  after the RTL leg, not against the model now.
* **The `clipopf` question was left open** (§61.3), not explained.

## §62 SESSION SM3, SITTING 3 — H1 IN THE `ucore`: PRE-REGISTRATION

**Written and COMMITTED BEFORE the RTL was touched and before any scoring run.**
Branch `ucsim`, from `56e54dba10`.  **Offline only** — banked captures,
Verilator and the C++ model.  No board contact.

> **Standing principle, applied throughout.**  *"This is 80's era hardware,
> they aren't wasting silicon on anything that isn't necessary.  Complex or
> confusing behavior that we see is likely to be simple systems interacting in
> ways you do not fully understand yet."*

Companions: §61 (the `sim/` landing and the directed board cell),
`sm3_h1_prereg_2026-08-04.md` (the socket measurement and the cell's own
pre-registration), `sm3_residue_census_2026-08-04.md` §5.1/§5.2.

### §62.1 THE BEFORE FIGURES, RE-MEASURED ON THIS TREE (not cited)

`timed_fuzz --core ucore --evt-replay`, 3,242 seeds, 2,710 scored:

| column | before |
|---|---|
| REGISTERED | **1,483 / 1,702** |
| EVT | **468 / 1,008** |
| COMBINED | **1,951 / 2,710** |

`sm3_ackcmp --core ucore`, 3,070 chip acknowledges, 2,759 paired.  The
**RE-ENTRY** table's `L = 4` row — the whole of the H1 population:

| chip prev fetch | chip gap | ucore, before | n |
|---|---|---|---|
| `L = 4` | 6 | **gap 4, from an INSERTED prefetch** | **1,117 / 1,289** |
| `L = 4` | 6 | gap 6 (already right) | 91 |
| `L = 5` | 6 | gap 6 | 333 / 363 |
| `L = 6` | 7 | gap 7 | 157 / 169 |
| `L = 7..19` | L+1 | L+1, exact | — |

The FIRST (wake) table's `L = 4` row is **290 / 310 at gap 4** and must STAY
at gap 4: §61.3's cell says the first acknowledge pays no floor.

### §62.2 WHAT IS BEING LANDED — the same one register, edge for edge

The `sim/` mechanism (§61.4) transliterated into `hdl/rtl/ucore/`, with the
model as the SPEC per the ucore README.  The five edges and where each one
goes:

| the model's edge | `sim/biu_timed.cpp` | the RTL |
|---|---|---|
| an INTA cycle ARMS | `inta_read()`: `bnd_pending_ = true` | `v30u_biu.sv` step (b), the `eu_post` arm, on `eu_bs == BS_INTA` |
| a flush while armed ARMS THE STAMP | `flush()`: `if (bnd_pending_) { bnd_arm_ = true; bnd_floor_ = -1; }` | step (b), inside `if (q_flush)` |
| the restarted prefetch's GRANT STAMPS the floor at that fetch's index 2 | `commit_fetch()`: `bnd_floor_ = cmt_t1_ + 2` | step (d), the fetch-grant arm, and the T1-open block in step (e) starts a bounded 2-clock counter (the RTL cannot predict `cmt_t1_`; it uses the T1 the announcement actually opens) |
| a pop SPENDS it | `pop()`: `bnd_floor_ = -1` | step (b), the `pop_l` arm |
| the recognition boundary READS it, SUSPENDS the prefetcher and CLEARS the arm | `boundary_no_pop()` | `bnd_hold` (a REGISTERED-view BIU output) gates `irq_take` in `v30u_eu.sv`; `eu_bnd_take` / `eu_bnd_post` carry the clear and the SUSP back |

**No new constant.**  Index 2 is `pf_arm_`'s existing instant and at w0 it IS
the completion eval (M2r).  The two bounded claims of §61.4 travel unchanged:
the floor is NOT read by the ordinary retire, and NOT by the REP mid-string
withdrawal (`eu_bnd_post = !intr_pending`).

**THE ONE PLACE THE RTL CANNOT BE LITERAL, STATED BEFORE THE RUN.**  The model
stamps an ABSOLUTE clock at the grant from its own prediction `cmt_t1_`; the
RTL has no wait counter and cannot predict a T1, so it marks the announcement
and starts the counter when that announcement's T1 actually opens.  The two
agree on every announcement that opens the T1 it was granted for, and differ
only for an announcement WITHDRAWN before its T1 (M22 expiry / F2's
`ann_kill`), where the model keeps a floor at a clock that never happened.  In
the RTL the mark goes with the withdrawn announcement, which is why
`ulockstep` is the bring-up instrument and not a formality.

### §62.3 THE BARS — registered before the run, reported as registered

**MUST MOVE UP** (`timed_fuzz --core ucore --evt-replay`):

| column | before | **registered bar** | point estimate |
|---|---|---|---|
| EVT | 468 / 1,008 | **>= 700 / 1,008** | ~845 |
| COMBINED | 1,951 / 2,710 | **>= 2,183 / 2,710** | ~2,328 |

*Where the bar comes from*: the census's ucore H1 class is **445 seeds**, so
the arithmetic ceiling is 468 + 445 = **913**.  The `sim/` leg closed
**417 of its own 491** H1 seeds (85 %); 85 % of 445 is 378, i.e. 846.  The bar
is set well under that, at **700**, so that a partial closure is still reported
as a partial closure and not as a failure.

**MUST MOVE** (`sm3_ackcmp --core ucore`, the RE-ENTRY table): the `L = 4`
row's **1,117 `gap 4` acknowledges drop to <= 100**, and the FIRST (wake)
table's `L = 4` row **stays at 290 gap 4** (a first acknowledge that pays the
floor is a REGISTERED FAILURE of this landing).

**MUST NOT MOVE — the ucore's own ratchets**, itemised:

| gate | registered |
|---|---|
| `timed_fuzz --core ucore` REGISTERED | **1,483 / 1,702** EXACTLY |
| `ulockstep --golden all --cases 50` | **17,350 / 17,350** |
| `check_core --opcodes all --cases 0` | **169,000 / 169,000** |
| `check_core --suite-dir tests/v30/f4a_boundary` / `f0lock_tranche` | 160 / 160, 400 / 400 |
| the 23 `v0.3` block-I/O forms | 229,999 / 229,999 |
| `v0.1-w1` / `-w3` | 1,200 / 1,200 |
| `v0.1-w1 --forms EB` | 200 |
| the four `evt` cells | 200 / 1,200 / 200 / 1,200 |
| `v0.1-w1evt-biased` | 1,200 |
| `check_boot --core ucore` | 220 and 400 |
| `check_ab_sim --core ucore` | MATCH over 187 rows |
| `timed_wvec_gate --core ucore` | 88 / 88, +0.0 % |
| `timed_enter_replay --core ucore` | 154 / 154 x5 |
| `timed_ins_replay --core ucore --raw` | 1,312 / 1,312 and 2,624 / 2,624 |
| `timed_fuzz --core ucore --seeddir .../b2-tranche/seeds` | **171 / 188** |
| the four HLT sweeps (ucore) | **91/97, 90/95, 40/46, 38/45 = 259 / 283** |
| `x1_retention.py` offline baseline / `X1_AD_RETENTION` | 143 / 283 and 259 / 283, 0 survivors |
| `ss_lint.py` (default `--core ucore`) | exit 0, census 0 UNMAPPED |
| `check_core --ce-div 4 --ce-hold-check` | `CE_HOLD_VIOL 0` |
| `gen_ucore_qsf --check` | PASS |

**SAVE-STATE.**  The mechanism adds architectural flops, so `SS_VERSION`
**0x82 -> 0x83** and the BIU count moves with them, per the addressed-register-
file precedent (append-only, never renumber).  `ss_lint` must exit 0 with **0
UNMAPPED**, and the `--ss-sweep` modes must stay clean.

**BOUNDED-COUNTER DISCIPLINE** (campaign risk #2).  The floor is carried as a
2-bit relative counter with a synthesis bound assertion beside the module's
existing ones, never as an absolute clock.

### §62.4 THE FALSIFIERS FOR THIS LEG

1. **`ulockstep --golden all --cases 50` is not 17,350 / 17,350.**  The two
   engines are then not rendering the same mechanism, and per the work order
   the landing STOPS and the divergence is booked with its attribution — it is
   not papered over.
2. A **FIRST** acknowledge that pays the floor (`sm3_ackcmp`'s wake table
   moving off 290 gap-4).
3. Any ucore ratchet in the table above moving DOWN.
4. EVT below the 700 bar.

Reported as registered, never restated.

### §62.5 THE LANDING — where each of the model's edges lives in the RTL

Landed at `2fbbb65101`.  `hdl/rtl/ucore/v30u_biu.sv` carries the register,
because every edge that arms, stamps and spends it is a BUS event; only the
READER is in `v30u_eu.sv`.

| the model (`sim/biu_timed.cpp`) | the RTL |
|---|---|
| `inta_read()`: `bnd_pending_ = true` | step **(b)**, `if (eu_post && (eu_bs == BS_INTA)) bnd_pending = 1'b1;` — set from the REQUEST, exactly as the model sets it before its own `post()` |
| `flush()`: `if (bnd_pending_) { bnd_arm_ = true; bnd_floor_ = -1; }` | step **(b)**, inside `if (q_flush)`, beside M19's `pf_owed` and M7's `pf_arm` |
| `commit_fetch()`: `if (bnd_arm_) { bnd_arm_ = false; bnd_floor_ = cmt_t1_ + 2; }` | step **(d)**, the fetch-grant arm: `if (bnd_arm) begin bnd_arm = 0; bnd_stamp = 1; end` — the grant MARKS the announcement… |
| …that `cmt_t1_` | …and step **(e)**'s T1-open block loads `bnd_cnt = 2`, so the counter reads 2 / 1 / 0 on the fetch's indices 0 / 1 / 2 |
| `pop()`: `bnd_floor_ = -1` | step **(b)**, the `pop_l` arm — `bnd_stamp` and `bnd_cnt` cleared, `bnd_pending` untouched |
| `boundary_no_pop()`'s `wait_bnd_floor()` | `bnd_hold` (register-only, so the EU's act decode may read it) gates `irq_take` in `v30u_eu.sv`.  A `while (…) tick()` renders as a STALL, which is what the EU's boundary window already is |
| its `susp()` and its three clears | step **(b)**, `if (eu_bnd_take) begin if (eu_bnd_post && bnd_pending) suspended = 1'b1; …clear all four; end` |
| `post_redirect = !m_.intr_pending` | `eu_bnd_post = !intr_pending`; the gate is `bnd_hold && !intr_pending` |
| its `if (opc_valid_) return clk_;` early return | free: all three arms of `at_bnd` already imply `!opc_valid` |

**Why the stall cannot be escaped by popping instead** — the one thing that had
to be argued rather than transcribed, and it is arithmetic, not a choice.  The
floor is stamped by the fetch that refills a queue the flush emptied, and that
fetch's first byte is poppable at its **eval + 3** (M2r) = index 5 at w0 and
later under waits, strictly after index 2.  So while `bnd_hold` stands there is
no ripe byte, `pop_now` is false, and the part sits at the boundary exactly as
the model's tick loop sits.

**The two deviations, both registered in §62.2 before the run.**  (a) the floor
is `T1 + 2` from the T1 the announcement ACTUALLY opens, not from the model's
prediction; (b) an announcement WITHDRAWN before its T1 (M22 expiry, F2's
`ann_kill`) gives the arm BACK, where the model keeps a floor at a clock that
never happened.  **`ulockstep --golden all --cases 50` is 17,350 / 17,350**, so
neither deviation is reachable on the golden population; both are written into
`v30u_biu.sv` beside the code.

**Save-state**: four flops, `SS_VERSION` **0x82 → 0x83**, BIU count 101 → 105,
`SS_COUNT` 218 → 222, `SS_TAG` **0x83DE**, addresses **0x066-0x069**, append-only.

**Bounded-counter discipline**: three assertions beside the module's existing
ones — `bnd_cnt <= 2`; `bnd_stamp` and `bnd_cnt` are mutually exclusive; and no
part of the floor outlives the acknowledge that armed it.

### §62.6 PREDICTION vs OUTCOME — reported as registered

**MOVED UP** (`timed_fuzz --core ucore --evt-replay`, 3,242 seeds / 2,710
scored, `BOUND WARNINGS` 5, `ENGINE ABORTS` 0, `INVALIDATED` 0):

| column | before | registered bar | point estimate | **after** |
|---|---|---|---|---|
| EVT | 468 / 1,008 | ≥ 700 | ~845 | **906 / 1,008**  (+438) |
| COMBINED | 1,951 / 2,710 | ≥ 2,183 | ~2,328 | **2,389 / 2,710**  (+438) |

The arithmetic ceiling was 468 + 445 = 913; **438 of the census's 445 H1 seeds
closed.**  The bar is met by 206 and the point estimate beaten by 61.

**AND THE ucore NOW LEADS THE MODEL ON BOTH COLUMNS**: EVT **906 vs 780**,
COMBINED **2,389 vs 2,052**, on a bank where the ucore PREDICTS and the model
REPLAYS.  (`--core sim` re-run on this tree: 1,272 / 780 / 2,052, unchanged to
the seed — `sim/` was not touched.)

**MOVED, as registered** (`sm3_ackcmp --core ucore`; 3,070 chip acknowledges,
paired **2,759 → 3,067**, because fewer sequences part):

| table | row | before | bar | **after** |
|---|---|---|---|---|
| RE-ENTRY | `L = 4`, engine at gap 4 | **1,117** | ≤ 100 | **0** |
| RE-ENTRY | `L = 4`, engine at gap 6 (chip's own) | 91 | — | **1,594 / 1,595** |
| RE-ENTRY | `L = 5` / 6 / 7 | 333/363 · 157/169 · 111/114 | — | **362/363 · 170/170 · 115/115** |
| FIRST (wake) | `L = 4`, engine at gap 4 | 290 | **must stay 290** | **290** |

The whole re-entry table is now exact except two acknowledges whose preceding
fetch the engine gives a different LENGTH — i.e. nothing is left in H1's own
population.  The wake table did not move at all, which is §61.3's board result
holding in RTL.

**DID NOT MOVE — every ucore ratchet, re-run on the final RTL:**

| gate | registered | after |
|---|---|---|
| `ulockstep --golden all --cases 50` | 17,350 / 17,350 | **17,350 / 17,350** |
| `check_core --opcodes all --cases 0` | 169,000 / 169,000 | **169,000 / 169,000** |
| `timed_fuzz --core ucore` REGISTERED | 1,483 / 1,702 | **1,483 / 1,702** (and the 219 residue is identical signature for signature and family for family) |
| `v0.1-w1` / `-w3` | 1,200 / 1,200 | **1,200 / 1,200** |
| `v0.1-w1 --opcodes EB` | 200 | **200** |
| the four `evt` cells | 200 / 1,200 / 200 / 1,200 | **200 / 1,200 / 200 / 1,200** |
| `v0.1-w1evt-biased` | 1,200 | **1,200** |
| `f4a_boundary` / `f0lock_tranche` | 160 / 400 | **160 / 400** |
| the 23 `v0.3` block-I/O forms | 229,999 / 229,999 | **229,999 / 229,999** |
| the four HLT sweeps | 91/97, 90/95, 40/46, 38/45 | **91/97, 90/95, 40/46, 38/45 = 259/283** |
| `check_boot --timed 220` / `400` | MATCH | **MATCH / MATCH** |
| `check_ab_sim` | 187 rows MATCH | **187 rows MATCH** |
| `gen_ucore_qsf --check` | PASS | **up to date** |
| `timed_wvec_gate --core ucore` | 88/88, +0.0 % | **88/88, 16,048 vs 16,048, +0.0 %** |
| `timed_enter_replay --core ucore` | 154 ×5 | **154/154 on all five legs** |
| `timed_ins_replay --core ucore --raw` | 1,312 / 2,624 | **rails 1,312/1,312, vs-chip 2,624/2,624, resolved 800/800** |
| b2 tranche | 171 / 188 | **171 / 188** |
| `ss_lint` | rc 0, 0 UNMAPPED | **PASS, 105×2 BIU + 116×2 EU + tag = 222, 205 flops, 0 UNMAPPED** |
| `--ss-sweep` modes 1 / 2 / 5 | 80/80 · 24/24 · width PASS | **80/80 · 24/24 · PASS** |
| `check_core --ce-div 4 --ce-hold-check` | `CE_HOLD_VIOL 0` | **`CE_HOLD_VIOL 0`** |
| `x1_retention offline` (tb_v30_core) | 259 / 283 | **259 / 283** |
| `x1_retention` tb_sys base / ret | 143 / 259, 116 closed, 0 survivors, 0 differing | **143 / 259, 116 closed, 0 survivors, 0 differing** — and the re-captured `base` cells are **byte-identical after decompression** to the banked ones, so H1 moved no HLT-sweep cell in that leg either |

**No falsifier fired.**  §62.4's four: `ulockstep` is exact; no first
acknowledge pays the floor; no ratchet moved down; EVT cleared the bar by 206.

### §62.7 THE H2 RE-CENSUS — its registered falsifier FIRED

Census §5.2 booked **H2** (`qs -!=F` / `qs E!=-` around an acknowledge) as
*"almost certainly downstream of H1"* with the falsifier *"H1 lands and this
family does not shrink"*.  Re-censused on BOTH engines on fresh reports, with
`--core` matched to the report:

| ucore EVT first-divergence signature | before (540) | **after (102)** |
|---|---|---|
| `bs PASV!=CODE` — **H1's own** | **446** | **4** |
| `qs -!=F` | 25 | **25** |
| `qs E!=-` | 16 | **16** |
| `bs INTA!=PASV` | 6 | **6** |
| `bs PASV!=MEMR` | 5 | **5** |
| `bs PASV!=MEMW` | 3 | **3** |
| `qs -!=E` | 3 | **3** |
| `bs PASV!=HALT` / `qs F!=-` | 2 / 2 | **2 / 2** |
| `data` (any) | 2 | 6 |

**The H2 pair is 41 before and 41 after — not one seed.**  On the model, whose
H1 landed in sitting 2, the same pair went **57 → 101**.  The falsifier is met
on both engines: **H2 is NOT downstream of H1.**

Family × population, `s15_census`, `--core` matched to the report:

| family | ucore REG 219 | ucore EVT **540 → 102** | sim EVT **645 → 228** |
|---|---|---|---|
| `PF_GAINED` | 25 (unchanged) | **463 → 21** | 15 → 15 |
| `PF_LOST` | 107 (unchanged) | 22 → **22** | 44 → **70** |
| `SCHEDULE` | 5 (unchanged) | 29 → **29** | 563 → **114** |
| `DATA_SEQ` | 41 (unchanged) | 14 → **14** | 5 → 5 |
| `PIN` | 4 (unchanged) | 4 → **8** | 9 → 11 |
| `TAIL_EXTRA` | 28 (unchanged) | 5 → **5** | 3 → 3 |
| `PF_ADDR` | 9 (unchanged) | 3 → **3** | 6 → 10 |
| catch-all | **0** | **0** | 0 |

**H1 removed exactly one family and touched no other.**  `PF_GAINED` −442,
`PIN` +4 (four seeds that used to part earlier now part on a pin row), every
other cell identical.  On the model H1 took `SCHEDULE` 563 → 114 and pushed
+26 into `PF_LOST` and +4 into `PF_ADDR`, which is why the two engines' EVT
residues are now shaped differently (102 vs 228).

**AND H2 IS NOT A FAMILY AT ALL — it is a symptom sitting on four of them.**
Cross-tabulating the ucore's 102 EVT seeds, signature × family:

| signature | `PF_GAINED` | `PF_LOST` | `DATA_SEQ` | `SCHEDULE` | total |
|---|---|---|---|---|---|
| `qs -!=F` | **17** | — | 6 | 2 | 25 |
| `qs E!=-` | — | **11** | — | 5 | 16 |

So "H2" names *where the two streams are first seen to part*, not *what
parted*: the queue-status port is simply the earliest-visible pin. **The next
sitting must rank by FAMILY, not by signature** — H2 as written is retired as a
mechanism hypothesis and its 41 seeds are redistributed into H3 (11), H4 (6)
and the two families below.

### §62.8 ONE THING NOBODY WAS LOOKING FOR — the `0x0008` vector class

14 of the ucore's 29 remaining EVT `SCHEDULE` seeds carry the SAME first
divergence: **`bs MEMR!=PASV nxta 0008`** — the CHIP starts a memory read at
`0x0008` and the engine is idle.  `0x0008` is interrupt vector **2**, the NMI
vector, and **all 14 have `evt.pin = 1` (NMI) with `evt.hold = 2`** — a
two-clock NMI pulse.  Across wait classes (fix0 7 · fix3 2 · wrand1 2 · wrand2,
wrand15, wrand7 1 each).  The model has **27** of the same signature.

It was 15 before H1 and 14 after, i.e. **H1 neither caused it nor hides it**.

Booked as an OBSERVATION, not a mechanism: the chip takes an NMI on a pulse
both engines decline (or takes it at a clock at which they have already
declined it).  *Falsifier*: a seed in the 14 whose `evt.pin` is not 1, or whose
chip `0x0008` read is not a vector fetch.  *The measurement that would sharpen
it needs no board*: the NMI edge latch's minimum pulse width against the
engines' `nmi_latch`, over the banked pulses.

### §62.9 THE RANKED LIST FOR THE NEXT SITTING

Post-H1 residue: **ucore 321** (219 REG + 102 EVT), **sim 658** (430 + 228).

| rank | mechanism | ucore | sim | why here |
|---|---|---|---|---|
| **H3** | **`PF_LOST`'s arbitration priority** | **107 REG + 22 EVT = 129** | 239 + 70 = 309 | the largest single family in BOTH engines, and now by a wide margin.  Unchanged since ucsim-t (`ucsim_t_provenance.md` §26.10 D item 4, `gaps` §I.5).  It owns 11 of the 16 `qs E!=-` seeds H2 used to claim |
| **H4** | **`DATA_SEQ`** — the right cycle, the right address, the wrong word | **41 REG + 14 EVT = 55** | 28 + 5 = 33 | the ucore is WORSE than the model here, so it is the largest ucore-owned family.  F47's shape |
| **H7** | the `0x0008` NMI-vector class (§62.8) | 14 EVT | 27 EVT | one signature, one pin value, one hold value, zero exceptions — the sharpest small population in the census |
| **H5** | the 13 ucore-only HLT sweep cells (F43 + the undiagnosed half) | 24 of 283 (11 model-shared) | — | unchanged; `gaps` §T.1 |
| **H6** | the fabric INTA float-retention class | 116 cells | — | harness; attribution NOT ESTABLISHED, fabric leg is SM2's |
| — | ~~**H2**~~ | **RETIRED as a mechanism** (§62.7): it is a signature, not a family, and its seeds belong to H3, H4 and `PF_GAINED` | | |

`TAIL_EXTRA` (28 REG + 5 EVT) and `PF_ADDR` (9 + 3) are the two families no
hypothesis names; they are small, they did not move, and nobody has looked at
them.

### §62.10 WHAT THIS SITTING DID NOT DO

* **No board contact.**  Everything is banked captures, Verilator and the model.
* **No H3 / H4 / H5 work** — the work order scopes them out and they are the
  next sitting's.
* **`sim/` was not touched**, and its three columns were re-measured to say so.
* The `clipopf` question (§61.3) is still open, and the mechanism behind the
  arm is still NOT ESTABLISHED — H1 is carried as MEASURED, not as a law.

## §63 SESSION SM3, SITTING 4 — H7 MEASURED AND BLOCKED; H3 PARTITIONED

**2026-08-04, branch `ucsim`, from HEAD `a23c329792`.  OFFLINE ONLY — banked
captures, the golden suites, Verilator and the C++ model.  NO BOARD CONTACT.
NOTHING WAS LANDED IN EITHER ENGINE, and every standing ratchet is untouched
because no engine source was changed** (one experiment was built, measured and
reverted; see §63.4).

> **Standing principle, applied throughout.**  *"This is 80's era hardware,
> they aren't wasting silicon on anything that isn't necessary.  Complex or
> confusing behavior that we see is likely to be simple systems interacting in
> ways you do not fully understand yet."*

Companions: §62.8/§62.9 (H7's booking and the ranked list),
`sm3_residue_census_2026-08-04.md` §5.3 (H3), `docs/facts/interrupt_model.md`
(the 2026-07-12 chip-side NMI/INT laws), `ucore_gaps_2026-08-04.md` §F.1
(8080 / BRKEM).

New instrument: **`sw/sm3_nmigeom.py`** — a MEASUREMENT tool, never a gate.
It reads the rig's own assert clock out of every banked EVT seed and pairs it
with the recognition the capture shows (the NMI vector read at `0x00008` for
pin 1, INTA1 for pin 0), with an optional `--core` leg through `timed_fuzz`'s
own regeneration path, wait vectors and event directive.

### §63.1 H7 — THE ASSERT CLOCK, AND THE CONTROL THAT MAKES IT USABLE

The rig asserts the pin during capture cycle **`idx(trigger CODE T1) + 2 +
delay`**.  That is not assumed here, it is established four ways:

* it is what `docs/facts/interrupt_model.md` says the scheduler does;
* it is what `hdl/tb/tb_v30_core.sv` says beside its own copy of the scheduler,
  and its `ev_cnt <= ev_delay + 1` countdown produces exactly that row;
* it is what `hdl/rtl/nec_bus.sv`'s `ev_st` FSM produces read edge by edge —
  `mem_addr_match` is latched at the T1 row's `tick_fall`, `ev_match` is read at
  that same row's `tick_rise`, and `EV_DELAY` then costs `delay + 1` more ticks;
* the model's own `biu.assert_clk()`, read out with `V30SIM_EVTTRACE` on
  `mc1/570` (anchor 145, delay 10), returns **A = 157 = 145 + 10 + 2**.

**And the control**: run the same instrument over the **pin-0** population
(929 banked INT seeds) and the chip's minimum assert-to-INTA1-T1 distance comes
out at **7**, with the HALT-limited mass at **8** — i.e. exactly
`interrupt_model.md`'s *"assert → INTA1 T1: minimum 7 (running) ... constant 8
from HALT"*, measured independently three weeks later on a different
population.  The coordinate is right.

### §63.2 H7's INVARIANT — IT IS A FLOOR, AND BOTH ENGINES' FLOOR IS ONE CLOCK TOO HIGH

208 banked seeds carry `evt.pin = 1`.  **Every one of them has `hold = 2`**, so
the part is offered a two-clock pulse and the only free coordinate is where the
pulse lands.  Of the 193 whose capture contains the vector read:

| | chip | `ucore` | `sim` |
|---|---|---|---|
| minimum vector-read T1, measured from A | **A + 12** | **A + 13** | **A + 13** |
| seeds sitting on that minimum | **30** | 27 | 48 |

Restricted to the seeds with **no earlier divergence** (the engine reproduces
the capture up to the vector read), the split is total:

| chip gap `V − A` | seeds | `ucore` exact |
|---|---|---|
| **12** (the chip's floor) | **14** | **0 / 14** |
| ≥ 13 | 147 | **144 / 147** |

**H7 is not a signature and not a `SCHEDULE` accident: it is a FLOOR, and the
census's 14 seeds are exactly the seeds that reach it.**  It is invariant under
wait class (fix0/1/2/3 and wrand1/2/3/7/15 all appear on both sides of the
line), under the rig delay (10 … 813), and under what owns the bus at A.

Read against the model's own decision clock (`V30SIM_EVTTRACE`'s
`A` / `B`, 183 seeds): the chip's answer is `V = max(B, A + 3) + 9` on **136**
of them against **115** for the landed `max(B, A + 4) + 9`, and every seed the
two readings disagree about has `B ≤ A + 3` — i.e. the whole of the difference
is the **pin term**, never the boundary term.

### §63.3 …AND THE GOLDEN SUITES REFUTE THE UNIFORM READING

The obvious mechanism — *"the NMI edge latch matures at edge+2, not edge+3"*,
one register, no new constant — was **BUILT AND MEASURED, AND IT IS REFUTED.**

`sim/timed_runner.cpp`'s NMI pin pipeline set to 3 in both the golden path and
the whole-program path, rebuilt, and the suites re-run:

```
   NMI.90    rows-exact 200 -> 194        (row-diffs 0 -> 858)
   NMI.B8    rows-exact 200 -> 189        (row-diffs 0 -> 1447)
   HLT.NMI   rows-exact 200 -> 200        (unchanged)
```

**17 golden cases break, and they are precisely the 17 the EVTTRACE census
identifies as A-LIMITED** (`B − A = 2` on 4 cases, `= 3` on 13).  The change
was reverted; `NMI.90` / `NMI.B8` / `HLT.NMI` are **600 / 600 rows-exact**
again on the restored binary, and `make -C sim test` is **PASS**.

So two silicon populations disagree by one clock in the same regime, and the
disagreement is **inside the fuzz bank too**: among the 25 clean banked NMI
seeds with `B ≤ A + 3`, **14 fire at `A + 3`** and **7 fire at `A + 4`**.  The
discriminating variable is NOT the wait class, NOT the rig delay, NOT the bus
owner or T-state at A, and NOT the queue occupancy at A — all four were
tabulated and all four cut across the split.

**H7 is therefore BLOCKED, not landed, and it is a sharper statement than the
observation §62.8 booked.**  What was an *"observation, not a mechanism"* is now
a measured floor with a measured refutation attached.

*Falsifiers, registered*: a banked NMI seed whose vector read opens earlier than
`A + 12`; a golden NMI case with `B ≤ A + 3` whose entry is at `A + 12`; or a
whole-program seed with `B ≥ A + 4` that does not sit at `B + 9`.

**THE DIRECTED CELL THAT WOULD DISCRIMINATE** (socket, capture only, no
flashing — NOT taken this sitting).  One fixed instruction stream, the assert
delay swept **one clock at a time** so that A walks through `B − 6 … B − 2`
with everything else held, at waits 0/1/2/3, and the whole sweep run **twice**:
once with the queue PRIMED at the boundary and once with it DRY (the one axis
that separates the golden A-limited cases, which are all cold `fetch`-trigger
cases, from the banked seeds).  The cell reads out where `A + 12` appears and
where `A + 13` does.  If the answer moves with the queue state the extra clock
is on the ENTRY (bus) side and the latch is right; if it does not, the latch
depth is conditional on something neither engine reads and the cell says on
what.  `sw/sm3_nmigeom.py` scores it unchanged.

### §63.4 WHAT WAS BUILT AND REVERTED

`sim/timed_runner.cpp` was edited (NMI `evpipe` and the golden path's `pipe`,
4 → 3), `make -C sim` run, the suites measured (§63.3), and the file restored
with `git checkout` and rebuilt.  The tree carries **no engine change from this
sitting**; the only new file is the measurement tool `sw/sm3_nmigeom.py`.

### §63.5 H3 — `PF_LOST` IS **TWO** FAMILIES, AND THE BIGGER ONE IS NOT ARBITRATION

`s15_census --core ucore` and `--core sim`, each matched to its own post-H1
report, dumped per seed.  `PF_LOST` is 129 (ucore) / 309 (sim).  It splits on a
single, mechanical, board-free criterion — **the address of the chip's cycle at
the first contested slot**:

| class | criterion | `ucore` | `sim` | shared |
|---|---|---|---|---|
| **A — the 8080 landing pad** | chip cell is `CODE 00484` **and** the chip's window contains `CODE:00008` | **92** | **88** | 87 |
| **B — the arbitration residue** | everything else | **37** | **221** | — |

**Class A is one place in the harness, not a law about prefetching.**
`sw/gen_soup.py` points **all 256 IVT vectors** at a bare handler at
**`0x0480`** — `CF` (IRET) with `CB` (RETF) beside it.  So every soup program
that takes any interrupt lands there.  At that `CF`:

* the **chip** pushes a two-byte return address and fetches on at **`0x00008`**
  — `CODE:00008` is present in **92 / 92** and **88 / 88** of the two classes.
  That is the 8080 `RST 1`: the part is in **8080 EMULATION MODE**;
* the **model** does the same thing, cycle for cycle (`mc1/1198`, rows 2636-2647
  side by side: `MEMW a5d47`, `MEMW a5d48`, `CODE 00008`).  Its **only** error is
  that the chip takes **one more prefetch first**;
* the **ucore** executes `CF` as the native **IRET** and issues the three stack
  pops.  It has no 8080 mode — `ucore_gaps_2026-08-04.md` §F.1, already booked.

Each engine's half of class A is exception-free **and they are different
defects**:

| | `sim` (88) | `ucore` (92) |
|---|---|---|
| engine's cell at the contested slot | **`MEMW` 88 / 88** (the RST's own push) | **`MEMR` 92 / 92** (the native IRET's first pop) |
| `delta` (engine T1 − chip T1) | **+2 on 88 / 88** | **+2 on 92 / 92** |
| recovery | `MISS` 87, `NONE` 1 | `NONE` 92 / 92 |

* the **model's** class A is one mechanism with one number: *the chip grants
  exactly ONE MORE PREFETCH between the 8080 opcode pop and the `RST`'s first
  store, and that store's T1 is two clocks later.*  The prefetch is the
  CONSEQUENCE — the chip's EU is two clocks slower to its first store on this
  path — so it is an 8080-path microcode latency, **not** an arbitration
  priority, and it should not be filed under H3 at all;
* the **ucore's** class A is the 8080 gap.  Its `PF_LOST` label is an artefact
  of "the first bus-visible disagreement": the two machines are executing
  different instructions.

All **50** banked seeds carrying the generator's own `has_brkem` flag are in
class A and in **no other family**; 42 more reach it without the flag (18 of
those 42 contain a `0F FF` byte pair in the image, 24 do not — how those 24
enter 8080 mode is **NOT ESTABLISHED** and is booked as an open question, not
guessed at).

**Consequence for the ranked list: 92 of the ucore's 129 H3 seeds — 71 % —
are the already-booked 8080 gap wearing `PF_LOST`'s clothes.  Ranking by
FAMILY misattributes them, exactly as §62.7 found ranking by SIGNATURE did.**

### §63.6 H3 CLASS B — the real arbitration family, partitioned but NOT closed

| | `sim` (221) | `ucore` (37) |
|---|---|---|
| `delta = 0` — both sides launch at the SAME clock | **184 / 221** | 23 / 37 |
| the engine's cell | `MEMW` 106 · `MEMR` 102 · `INTA` 5 · `IOW` 5 · `IOR` 3 | `MEMR` 33 · `HALT` 2 · `INTA` 2 |
| recovery | `NONE` 184 · `EXTRA` 25 · `MISS` 12 | `EXTRA` 25 · `NONE` 11 · `MISS` 1 |

With `delta = 0` on 184 of 221 this is a **GRANT-ORDER SWAP and not a timing
slip**: the two sides open a cycle on the same clock and disagree about *whose*
it is — the chip's prefetcher, the engine's EU.  `mc1/1608` is the family in one
line: chip `CODE:00530@518` then `MEMW:0aabe@524`; model `MEMW:0aabe@518` then
`CODE:00530@524`, and the two realign immediately (`seq_match 1.0`).

**The one candidate the work order names was tested and is NOT the answer.**
Chip-side queue occupancy at the contested slot (counted from the capture:
bytes delivered by completed CODE cycles since the last `QS = E`, minus pops):

```
  contested slots (221)   occ 0:2   2:33   3:76   4:83   5:27
  control, every other chip CODE grant in the same captures (34,832)
                          occ 0:2532  1:48  2:16772  3:8634  4:5664  5:1182
```

The contested slots are strongly skewed to a **full-ish queue** (186 of 221 at
occ 3-5, against a control dominated by occ 2), which is the right shape for
*"the chip prefetches from a fuller queue than the model allows"* — but occ 0
through 5 all occur, so **there is no single threshold and M4's `occ + inflight
≤ 4` boundary is not off by one.**  Reported as a negative result.

**The ucore already closes 184 of the model's 221 class-B seeds** (37 against
221), so on the genuine arbitration axis the ucore is far closer to silicon
than the model is, and class B is overwhelmingly a **`sim/` debt**.

*The directed cells that would discriminate class B* (spec only, not taken):
(a) a fixed instruction whose EU access is issued at a known clock, with the
queue pre-loaded to occ 0…6 in six otherwise identical captures, at waits 0-3 —
this reads the grant priority as a function of occupancy alone; (b) the same
with the EU request arriving one clock EARLIER and one clock LATER than the
prefetcher's eligibility instant, which separates *"the chip's tie-break is
prefetch-first"* from *"the chip's EU request is one clock later than modelled"*.
Class A's own `delta = +2` says the second reading has to be on the table.

### §63.7 WHAT THIS SITTING DID NOT DO

* **No board contact**, and no flashing.  Two directed cells are specified and
  left un-taken (§63.3, §63.6).
* **Nothing was landed.**  No RTL, no `sim/`, no save-state, no `SS_VERSION`
  move; the only tree change is the new measurement tool.  Every standing
  ratchet in §62.3 stands where §62.6 left it, unmeasured this sitting because
  nothing that could move them was touched.
* **H4 / H5 / H6 were not opened** — the work order scopes them out.
* **The 24 class-A seeds with no `0F FF` in the image were not explained.**

## §64 SESSION SM3, SITTING 5 — THE CODEX REMEDIATION PACKAGE

**2026-08-04, branch `ucsim`, from HEAD `a195b06c36`.**  Half A of the sitting:
the six concerns raised by the Codex critical review of the silicon-match phase
(verdict **GO-WITH-CONCERNS**).  Half B — the two directed board cells §63.3 and
§63.6 specify — is §65.

> **Standing principle, applied throughout.**  *"This is 80's era hardware,
> they aren't wasting silicon on anything that isn't necessary.  Complex or
> confusing behavior that we see is likely to be simple systems interacting in
> ways you do not fully understand yet."*

### §64.1 CONCERN 1 — **GOVERNANCE ERRATUM.  H1's RE-KEY WAS POST-HOC.**

**The finding is upheld exactly as Codex stated it, and it is booked as an
erratum against this project's own pre-registration discipline, not explained
away.**

`sm3_h1_prereg_2026-08-04.md` §5 registered P3: *"if `JMPLOOP` and `RETLOOP`
show gap 4 at w0 … **C1 is REFUTED, the `sim/` landing is REVERTED**, and H1 is
re-opened as a per-redirect question — the landing is not defended against its
own falsifier."*  P3 **fired**.  What P3 authorised was the REJECTION of C1.
What §7.2 then did was read the same 120 captures for the coordinate that DOES
separate their two populations — *an acknowledge with an acknowledge behind it*
— install it as the new arm (`bnd_pending_`), and report **326/326 on those same
120 captures** as the landing's evidence.

**That 326/326 is a FIT, not a test.**  The discriminator was selected by
looking at the data it is scored on.  §7.2's own words — *"What was reverted is
the KEY, not the floor"* — describe the manoeuvre accurately and do not make it
legitimate.  The floor's SHAPE (`max(F1+6, F1+L+1)`) was pre-registered and is
untouched by this; the ARM is what was chosen after the fact.

**THE MITIGATION — validation on data that did not select the key.**  The arm
was chosen on `sw/testdata/sm3-h1cell/` (120 directed captures, 5 stimuli).  The
banked EVT population is disjoint from it in every sense that matters: different
programs, different campaign, captured weeks earlier, and **not consulted when
the arm was chosen**.  It splits further into two campaign banks that were
generated and captured independently.  Scoring the arm's own law — *every
acknowledge with an acknowledge behind it opens at `max(F1+6, F1+L+1)` after a
CODE fetch* — over each bank ALONE (`sw/sm3_ackgeom.py`, chip rows only, no
engine in the loop):

| partition | re-entry acknowledges | **law violations** |
|---|---|---|
| `mc1` | 1,129 | **0** |
| `mc2` | 1,188 | **0** |
| `t30-raw` | 1 | **0** |
| all three | **2,318** | **0** |

Two independent populations of over a thousand acknowledges each, neither used
to select the key, and **zero exceptions in either**.  That is what makes the
arm quotable.  **The 326/326 figure is NOT quotable as evidence for the arm**
and is struck in that role; it remains true as a statement about the model's
reproduction of those captures once the arm was in.

**The standing rule this produced** is now in `CLAUDE.md`'s discipline section,
one line: *a refuted key's replacement must be validated on data that was not
used to select it.*

### §64.2 CONCERN 2 — **THE 17-CASE SCREEN, ADJUDICATED.  THE SCREEN IS NOT A
FLOOR DETECTOR, AND THE HYPOTHESIS IS NEITHER CONFIRMED NOR REFUTED BY IT.**

Codex's screen over the full bank — `ord == 1`, `prev_len == 4`, `gap == 6` —
returns **17** hits, reproduced here exactly (`sw/sm3_ackgeom.py`, then the
first-acknowledge slice: gap 4 on **295**, gap 6 on **17**, other on 6).  These
are first acknowledges sitting where H1 says only a RE-ENTRY may sit.

The coordinator's hypothesis was that an **NMI or other non-INTA entry** hides
behind them: `sm3_ackgeom`'s ordinal counts INTA cycles only, so an entry
announced by a vector read leaves an acknowledge behind without incrementing it.

**THE EVENT-AXIS READ.  All 17 carry `evt.pin = 0` (INT), so the rig asserted no
NMI on any of them.**  Reading the chip rows before the first INTA for an IVT
vector fetch (a `MEMR` below `0x00400` — a software `INT`, a trap, or an NMI):

| | seeds |
|---|---|
| an interrupt ENTRY before the first INTA | **3** — `mc1/2672` (vector `0x00000`), `mc1/356` (`0x0000c`), `mc2/3821` (`0x001ac`) |
| **no acknowledge-like event of any kind** | **14** |

Taken at face value that is the brief's second branch — a falsification hit.
**It is not, and the test that decides it is the engines.**

**THE DECIDING TEST.**  Neither engine floors a FIRST acknowledge: both arms are
INTA-only and `bnd_pending_` resets to false.  So if an engine reproduces the
chip's gap-6 clock, that clock is not a floor — it is where the EU retired.
Per seed, first-acknowledge T1, chip vs engine:

| | reproduce the chip's first-acknowledge T1 |
|---|---|
| `ucore` | **14 / 17** |
| `sim` | 11 / 17 |

and the **3 the ucore misses are exactly the 3 with an entry behind them.**
The 14 with nothing behind them are reproduced by an engine that applies no
floor to them, so **they are not exceptions to H1's partition at all.**

**WHY THE SCREEN MISLEADS, and it is the simplicity principle in one line.**
For a RE-ENTRY the boundary is pinned to the preceding fetch — the redirect
flushed the queue and the restarted prefetch IS that fetch — so `gap` measures
the floor.  For a FIRST acknowledge there is no redirect, the recognition
boundary is wherever the current instruction happens to retire, and `gap` 4 vs 6
measures **the length of the instruction that was executing**.  The screen
carries a premise from one population into another where it does not hold.
Nothing about the part is complicated here; one coordinate stopped meaning what
it meant.

**WHAT THE 3 RESIDUAL SEEDS ACTUALLY SHOW — and it is the hypothesis, on the
only cases where it is testable.**  Their chip rows, cycle for cycle:

```
  mc1/2672   MEMR:00000@235 MEMR:00002@239            <- vector 0 (the divide trap)
             MEMW:03efe@247 MEMW:03efc@254 MEMW:03efa@260   <- the entry's frame
             CODE:00480@264 CODE:00482@268            <- gen_soup's handler: CF = IRET
             MEMR:03efa@274 MEMR:03efc@278 MEMR:03efe@282   <- the IRET's three pops
             CODE:00516@286                           <- the RESTARTED prefetch, L = 4
             INTA  T1 @292                            =  286 + 6.  THE FLOOR, PAID.
  mc1/356    identical shape, vector 0x0000c, restart @210, INTA @216 = 210 + 6.
```

**Those two are re-entries in every mechanical sense** — an interrupt entry, a
handler, an IRET, a flush, a restarted prefetch, and the acknowledge at that
prefetch's index 2.  The *only* reason `sm3_ackgeom` calls them ord 1 is that
the entry was announced by a vector read instead of an INTA cycle.  **Both
engines put the acknowledge at gap 4** — the un-floored back-to-back slot — and
are wrong by exactly the 2 clocks the floor costs.

The third, `mc2/3821`, is **not** a floor case: its handler runs
`CODE:00480 → 00482 → 00484 → MEMW → CODE:00008`, i.e. it is the **8080 landing
pad already booked as §63.5 class A**, and both engines diverge long before the
acknowledge for that reason.

**THE POPULATION CONTROL, and why the arm is NOT being widened this sitting.**
Over all 771 first acknowledges in the EVT bank, 12 have both `prev = CODE
L = 4` and an entry behind them.  **Eight of the twelve sit at gap 4 — below the
floor.**  A floor is a minimum; if any prior entry armed it, those eight could
not open at index 0.  Resolving them: the floor is *stamped* by the restarted
prefetch after a flush and *spent* by a pop (§61.4), so it only bites at the
first boundary after the restart.  Measuring the distance from the last vector
read to the acknowledge and testing for the IRET's contiguous stack-pop triple
immediately before the lead-in fetch:

| | seeds | gap |
|---|---|---|
| the entry's IRET returns **immediately** before the acknowledge | **2** (`mc1/2672`, `mc1/356`) | **6 — floored** |
| the entry returned long ago (9-60 bus cycles, pops in between) | 10 | 4 on eight, 6 on the 8080 seed, 161 on one |

which is consistent with an entry-generic arm plus the spend rule, and is
**equally consistent with the arm being INTA-only and those two seeds being
coincidence at n = 2.**  Two seeds cannot separate them.

**THE DISPOSITION — BOOKED, NOT PATCHED.**

* **H1's first-vs-re-entry partition SURVIVES.**  The 17 are not an exception
  class: 14 are ordinary retires and 1 is the 8080 gap.
* **H1a is OPENED as a hypothesis: the arm is the interrupt ENTRY SEQUENCE, not
  the INTA bus cycle.**  Simplicity argues for it directly — the part has ONE
  microcoded entry sequence and an INTA-announced entry and a vector-read entry
  are the same microcode; a machine that armed on the bus cycle would need two.
  **Evidence: 2 seeds.  It is NOT landed.**
* **Widening the arm was considered and REJECTED for this sitting**, on the
  project's own rule that fixes are mechanism-level.  The model's arm sits in
  `BiuTimed::inta_read` (`sim/biu_timed.cpp:1387`); there is **no entry hook in
  the BIU at all**, and the only BIU-visible signature of a vector-read entry is
  its ADDRESS.  Arming on "a `MEMR` below `0x400`" is an address-keyed rule with
  no mechanism behind it — precisely the fitted-table shape the standing
  principle names as a signal of misunderstanding.  §61.4 already carries *"THE
  MECHANISM BEHIND THE ARM IS NOT ESTABLISHED"*; widening it on an address
  match would make that worse, not better.
* ***Registered falsifier for H1a***: a banked or directed capture in which an
  interrupt entry announced by a vector read is followed IMMEDIATELY by its
  IRET's restarted prefetch and an acknowledge, and that acknowledge opens at
  the back-to-back slot rather than `max(F1+6, F1+L+1)`.  Two such would kill
  it; the two that exist both go the other way.
* ***The cell that would settle it***, specified and NOT taken: the
  `sm3_h1_cell` `iretnext` stimulus with the pre-planted frames reached by a
  software `INT n` instead of by the rig's pin, so the entry is real and carries
  no INTA.  It is the same rig, the same driver and the same scorer;
  `sm3_h1_cell.py` needs one new stimulus and no new instrument.
* **Neither engine's arm was changed.  No ratchet moved.**

### §64.3 CONCERN 4 — **THE `f46_invalidated` PREDICATE IS TIGHTENED**

Codex: the predicate tests only REPRESENTABILITY (`h != h & mask`); it never
compares `hold_applied` with `hold`, so a directive that is perfectly
representable and still mis-applied would stay silently SCORED.  Upheld.  INV-1
exists to make exactly that impossible, and the predicate implemented only the
one defect that had been found rather than the property the ledger claims.

`sw/timed_fuzz.py::f46_invalidated` now has **two limbs**:

```python
if h != (h & ((1 << bits) - 1)):                       # (a) representability
    return True
if "hold_applied" in e and int(e["hold_applied"]) != h: # (b) APPLICATION
    return True
return False
```

Limb (a) is a derivation of limb (b) for the one defect we know; it is not the
whole of it.  A record with no `hold_applied` field falls through to (a), which
is the pre-widen behaviour and correct by date.

**CODEX'S OWN EQUIVALENCE TEST — the proof that no current record is
mis-applied.**  If any banked record carried `hold_applied != hold`, the two
`--rig-hold` modes would hand the engine different directives and the totals
would part:

```
  timed_fuzz --core sim --evt-replay --pop evt --rig-hold banked
  timed_fuzz --core sim --evt-replay --pop evt --rig-hold applied
```

The two reports are **BYTE-IDENTICAL** (`diff` clean, including every
by-wait-class and by-bank cell): `EVT 780/1008`, `SCORED 1008`,
`DIVERGE 228 / EXACT 780 / OPEN_BUS 157`, and **no `INVALIDATED` line on either
— the tightened predicate returns False across the whole bank.**

**THE FULL GATES, RE-RUN ON THE TIGHTENED PREDICATE — every figure UNCHANGED:**

| gate | registered | measured |
|---|---|---|
| `timed_fuzz --core sim --evt-replay` REGISTERED | 1,272 / 1,702 | **1,272 / 1,702** |
| … EVT | 780 / 1,008 | **780 / 1,008** |
| … COMBINED | 2,052 / 2,710 | **2,052 / 2,710** |
| `timed_fuzz --core ucore --evt-replay` REGISTERED | 1,483 / 1,702 | **1,483 / 1,702** |
| … EVT | 906 / 1,008 | **906 / 1,008** |
| … COMBINED | 2,389 / 2,710 | **2,389 / 2,710** |
| `INVALIDATED`, both engines | 0 | **0** |
| `BOUND WARNINGS` / `ENGINE ABORTS`, ucore | 5 / 0 | **5 / 0** |

### §64.4 CONCERN 6 — **THE `sig_ledger` ADMISSION CONTROL IS REPRODUCIBLE AGAIN**

Codex: `sm3_sigctl.py` loads the LIVE novelty ledger, so once the 140
signatures were admitted to it the recorded **166 seeds / 140 signatures** could
no longer be reproduced by the tool that produced it.  Upheld — a control that
cannot be re-run is not a control.

`--ledger <path>` added (default unchanged: the live
`tests/v30/fuzz_bank/sig_ledger.json`), and the ledger actually used is now
stamped into the tool's own output and into its report JSON.

**THE REPRODUCTION, from git, on the current tree:**

```
git show 369e4953ce:tests/v30/fuzz_bank/sig_ledger.json > <pre>.json   # 11,705 sigs
                                          (the live file today: 11,845 = +140)
python3 sw/sm3_sigctl.py --jobs 8 --ledger <pre>.json --out …

  sm3_sigctl: 3242 banked seeds, 11705 known signatures from <pre>.json
  new-sig TIMING seeds: 166   distinct signatures: 140
    on RE-CAPTURED seeds : 166
    on any OTHER seed    : 0
    failing the control (not a true-300/12-bit re-capture): 0
  errors: 0  gen-drift: 0
```

**166 / 140 / 0 / 0 / 0 — the admission run of §60.1 reproduces exactly**, on a
tree whose live ledger already contains the admitted signatures.  Recorded as
the addendum §60.1 asks for.

### §64.5 CONCERN 3 — **THE EVT COLUMN IS NOT A HEAD-TO-HEAD**

Codex: the ucore's and the model's EVT figures are quoted side by side and read
as a comparison, but the two engines are handed different information —
`evt_tuple` (the rig's directive alone, a PREDICTION) versus `evt_directive`
(the rig's directive **plus the capture's own acknowledge positions and pushed
CS:IP**, a REPLAY).  Upheld.

The rule is written into `standing_gates.md` §B as its own subsection: each
figure is a valid silicon-match ratchet for its own engine; **no delta, margin
or ranking may be computed between the two columns**, and the REGISTERED column
(1,702 seeds, no `evt` axis, nothing from the capture handed to either engine)
is the column to use when a head-to-head is wanted.  The §B rows that already
say the ucore *"LEADS this column"* are left as written with the correction
attached, because rewriting a recorded claim in place would hide that it was
made.

### §64.6 CONCERN 5 — **H2's SPAN, RE-VERIFIED ON THE CURRENT RESIDUE**

Already satisfied by §62.7's cross-tab; re-measured on this sitting's own fresh
reports so the citation is not to a stale run.  `s15_census --core ucore --pop
evt` over the ucore report above (**102 EVT diverging seeds**, unchanged):

| signature | `PF_GAINED` | `PF_LOST` | `DATA_SEQ` | `SCHEDULE` | total |
|---|---|---|---|---|---|
| `qs -!=F` | 17 | — | 6 | 2 | **25** |
| `qs E!=-` | — | 11 | — | 5 | **16** |
| **the H2 pair** | 17 | 11 | 6 | 7 | **41 across 4 families** |

**≥ 3 families confirmed — 4.**  Identical to §62.7 cell for cell.  H2 stays
RETIRED as a mechanism hypothesis: it names where the streams are first seen to
part, not what parted.

### §64.7 WHAT HALF A DID NOT DO

* **No engine was changed.**  `sim/` and `hdl/rtl/ucore/` are untouched; the
  only code edits are `sw/timed_fuzz.py`'s predicate and `sw/sm3_sigctl.py`'s
  `--ledger` option, both of which were proved inert on every standing figure.
* **The arm was NOT widened** (§64.2), and H1a is carried as a 2-seed
  hypothesis with a registered falsifier and a directed cell, not as a law.
* **No board contact in half A.**  H4 / H5 / H6 and the 8080 work (`gaps` §F.1,
  a pending USER decision) were not opened.

## §65 SESSION SM3, SITTING 5 (half B) — THE TWO DIRECTED CELLS RAN

**2026-08-04, branch `ucsim`, socket only (`use_core=False`), FLASH #4, NO
FLASHING.**  Pre-registration committed at **`8c5fc9750d`** BEFORE the first
board contact: `docs/notes/sm3_h7_h3_prereg_2026-08-04.md`.  Single writer
confirmed before contact (`0 users`, no serve process on `mister-nec`); the
divider PINNED with the `div_guard` readback recorded in both manifests
(`div=8 (4 MHz), commanded by this connection` -> **PINNED**); full per-clock
rows + raw 64-bit words + `SHA256SUMS` retained; `board_idle()` run at the end
and **OK**; no transport error and no stop in either cell.

| cell | captures | retained files | tool | seconds |
|---|---|---|---|---|
| H7 (§63.3) | **160** | 322 (`sw/testdata/sm3-h7cell/`) | `sw/sm3_h7_cell.py` | 15.2 |
| H3 class B (§63.6) | **96** | 194 (`sw/testdata/sm3-h3cell/`) | `sw/sm3_h3_cell.py` | 9.7 |

**NOTHING WAS LANDED.**  Neither cell's authorising outcome fired, and no
engine source was touched, so every standing ratchet stands where §64 left it.

### §65.1 H7 — **Q4 FIRED.  THE CELL IS INCONCLUSIVE, AND THE NEGATIVE RESULT
IS SHARP.**

160 captures: 2 stimuli (`nop` = queue PRIMED, `ebnext` = queue DRY) × waits
0/1/2/3 × delays 4…23, `hold = 2` on every one, **160/160 fired and 160/160
contain the NMI vector read**.

| | w0 | w1 | w2 | w3 |
|---|---|---|---|---|
| chip floor `min(V − A)`, **primed** (`nop`) | **13** | **13** | **13** | **13** |
| chip floor `min(V − A)`, **dry** (`ebnext`) | **13** | **13** | **13** | **13** |

* **Q1 HOLDS.** Cells with `V − A < 12`: **0**.  H7's standing falsifier is not
  met.
* **Q1b HOLDS.** Every (variant, wait) cell has a knee — the gap histograms run
  13…18 — so `A` is the coordinate it is taken to be and the rig is sound.
* **Q2 DID NOT FIRE.** The floor does not move with the queue state.  **No
  landing is authorised**, and none was taken.
* **Q3 DID NOT FIRE** either: the floor is not 12.
* **Q4 FIRED — the pre-registered inconclusive branch.**  This stimulus never
  reaches `A + 12`.  Per §2.4 as written, **that is NOT a refutation of §63.2**;
  those 30 banked seeds are silicon.

**THE ENGINE LEG, on the same 160 captures and the same instrument** (measured
offline BEFORE the board for the ucore, §2.3, and re-run for both engines
after):

| | chip floor | `ucore` floor | `sim` floor | delta |
|---|---|---|---|---|
| all 8 (variant, wait) cells | **13** | **13** | **13** | **+0, everywhere** |

**On this stimulus both engines are EXACTLY right.**  In the coordinate §63.2
uses, the chip's recognition instant here is `A + 4`, with **zero exceptions in
160 captures**, and the bank's `14 at A+3 / 7 at A+4` split has landed entirely
in the `A + 4` camp.

**WHAT THE CELL RULES OUT, AND IT IS THE POINT OF IT.**  Composing the window
`[A, V)` for the cell's 160 captures and for the banked population:

| | cycles in `[A, V)` | EU cycles in the window | `bs` at `A+3` |
|---|---|---|---|
| **the cell**, 160 | 0:1 · 1:111 · 2:45 · 3:3 | **0 on all 160** | CODE 122 · PASV 38 |
| **banked, at the floor `A+12`**, 30 | 0:6 · 1:17 · 2:7 | **0 on all 30** | CODE 23 · PASV 7 |
| banked, `A+13`, 18 | 1:16 · 2:2 | 0 on 16, 1 on 2 | CODE 14 · PASV 4 |

**The cell's population and the bank's floor population are the same population
on every axis measurable in the window — and they disagree by one clock.**
Together with §63.3's four eliminations (wait class, rig delay, bus owner at A,
queue occupancy at A) and this cell's two more (queue PRIMED vs DRY, and the
window's own composition), **essentially everything local to the pin event is
now excluded.**

**THE LEAD THIS HANDS THE NEXT SITTING, and it is where simplicity points.**
The selector is not on the pin side; it is **which instruction's boundary the
recognition lands on.**  The evidence converges from three directions:

* the cell's two stimuli are a NOP sled and an `EB 00` chain — **two opcodes** —
  and both are 100 % `A + 4`;
* the golden NMI forms are `NMI.90` (NOP) and `NMI.B8` (`MOV AW, imm16`) —
  **two opcodes** — and §63.3's refutation is that shortening the pipeline
  breaks exactly their 17 A-limited cases, i.e. **they too are `A + 4`**;
* the `A + 3` camp lives only in `gen_soup`'s random instruction streams.

That reading also **dissolves §63.3's contradiction** without a new number: the
two silicon populations are not disagreeing about the latch, they are running
different instructions.  *The measurement that would take it, and it needs no
board*: the opcode at the recognition boundary for the 30 banked `A+12` seeds
against the 18 `A+13` ones, read out of the model's `V30SIM_EVTTRACE` boundary
against the regenerated image.  **NOT taken here** — it is a new hypothesis, it
belongs in its own pre-registration, and this sitting's scope is the two cells.

*H7 stays BLOCKED*, with its registered falsifiers unchanged and one more
eliminated axis under them.

### §65.2 H3 CLASS B — **R4 MISSED: THE CELL DID NOT REACH THE FAMILY, AND
BOTH ENGINES ARE EXACT ON EVERY SLOT IT DID REACH**

96 captures: 3 variants (`mw` baseline, `mwseg` = ES: override so the EU's
request arrives later, `mr` = no-ModRM read so it arrives earlier) × pads 0…7 ×
waits 0/1/2/3, **3,744 EU accesses**, no pin event.

* **R1 — PARTLY MET, and the part that is not is stated.**  The pad sweep does
  move the achieved occupancy, but only at **w0**, where it spans **{2, 3, 4,
  5}** — 3 or more values in all three variants, as registered.  At **w1/w2/w3
  it spans only {2, 3}**, two values, so §63.6's cell (a) is answered at w0 and
  **is NOT answered at the higher wait levels by this stimulus.**  Reported as
  registered, not restated.
* **R2 — MET, and VACUOUSLY.**  Within every (variant, wait, occupancy) cell
  the chip's grant order is constant — but the constant is the same one
  everywhere: **prefetch-first on 3,744 of 3,744 accesses**, at every
  occupancy from 2 to 5, in all three variants, at all four wait levels.  The
  previous cycle is `CODE` on **312/312** accesses in every (variant, wait)
  cell.  A coordinate that never varies cannot be a function of anything.
* **R3 — the request instant DID move**, which is the one thing that worked as
  designed.  The gap from the preceding fetch's T1, per variant:

  | | w0 | w1 | w2 | w3 |
  |---|---|---|---|---|
  | `mr` (early) | 4:253 · 6:47 · 7:12 | 6:312 | 7:312 | 8:312 |
  | `mw` (baseline) | 4:229 · 6:83 | 6:168 · 8:144 | 7:312 | 8:312 |
  | `mwseg` (late) | 4:206 · 6:106 | 6:168 · 8:144 | 7:312 | 8:312 |

  Three distinct curves at w0 and two at w1, so the EU's request really was
  placed at different instants relative to the prefetcher's eligibility.
* **R4 — MISSED, AND THAT IS THE RESULT.**  §63.6's class-B signature is *the
  two sides open a cycle on the same clock and disagree about whose it is*.
  Scored by ordinal against **both** engines on the same captures:

  | | same-clock, different owner | agreement |
  |---|---|---|
  | `sim` | **0** | **3,744 / 3,744** at every occupancy |
  | `ucore` | **0** | **3,744 / 3,744** at every occupancy |

  **Zero.  The pre-registration says exactly what this means**: *"the cell has
  not reached the family … and no conclusion about the tie-break may be drawn
  from these captures."*  It is honoured.

**WHAT IT ESTABLISHES ANYWAY, and it is not nothing.**  On a controlled
arbitration sweep — a flush, a known refill, occupancy 2 through 5, three EU
request instants, four wait levels, 3,744 accesses — **both engines reproduce
the chip's grant order exactly, without a single exception.**  Class B is
therefore NOT reachable by *"a redirect, then an EU access at varied
occupancy"*, and §63.6's negative result on occupancy is reinforced from the
other side: the coordinate the work order named does not produce the family
even when it is swept deliberately.

**WHY THE CELL MISSED, and the spec that follows from it.**  Every access in
this stimulus is preceded by a `CODE` fetch (312/312) because the `EB 00` flush
resynchronises the refill, and the pad moves the EU request in **whole bytes**
— 2 to 3 clocks at a time — not in clocks.  So the EU request never lands ON
the prefetcher's eligibility instant; it always lands clearly after it, and
there is no tie to break.  The wait sweep does shift the phase by one clock per
level and the engines agree at all four, which is a real four-phase control,
but four phases of a coarse sweep is not the same as the contested slot.

*The cell that would reach it* (spec only, NOT taken): the same body with the
EU request moved in **CLOCK** steps rather than byte steps — a per-access wait
vector on the fetch immediately preceding the access (the mechanism
`timed_wvec_gate` already drives), so the prefetcher's eligibility instant
walks past a fixed EU request one clock at a time.  Alternatively, drive the
access from a queue that is NOT refilling after a flush — the banked family's
contested slots skew to occ 3-5 with the prefetcher steady-state, not
recovering.

**Class B remains open, remains 184-of-221 a `sim/` debt, and nothing was
landed.**

### §65.3 WHAT THIS HALF DID NOT DO

* **No flashing**; FLASH #4 is still on the board and neither cell used the
  core.  `board_idle()` OK.
* **Nothing landed in either engine.**  Neither cell's authorising outcome
  fired (H7's Q2, H3's single pre-registered mechanism), so no ratchet was
  touched and none needed re-measuring.
* **H4 / H5 / H6 and the 8080 work were not opened.**
* **The H7 opcode census was not taken** (§65.1) — it is a new hypothesis and
  needs its own pre-registration.

## §66 SESSION SM3, SITTING 6 — H4 AND H5: THE PRE-REGISTRATION

**2026-08-04, branch `ucsim`, from HEAD `dd73f4147c`.  OFFLINE ONLY — banked
captures, Verilator and the C++ model.  NO BOARD CONTACT, and none is asked
for.**  Targets: the last two unexamined items of §62.9's ranked list —
**H4 (`DATA_SEQ`)** and **H5 (the 13 HLT sweep cells)**.

> **Standing principle, applied throughout.**  *"This is 80's era hardware,
> they aren't wasting silicon on anything that isn't necessary.  Complex or
> confusing behavior that we see is likely to be simple systems interacting in
> ways you do not fully understand yet."*

**This section is written and COMMITTED BEFORE either change is built or
scored.**  §64.1's standing rule is honoured throughout: every key below is
either derived from silicon rows alone or validated on a population that was
not used to select it.

### §66.1 THE BEFORE FIGURES, RE-MEASURED ON THIS TREE (not cited)

`timed_fuzz --evt-replay`, 3,242 seeds, 2,710 scored, both engines, fresh:

| column | `ucore` | `sim` |
|---|---|---|
| REGISTERED | **1,483 / 1,702** | **1,272 / 1,702** |
| EVT | **906 / 1,008** | **780 / 1,008** |
| COMBINED | **2,389 / 2,710** | **2,052 / 2,710** |

(§64.5's rule stands: the two columns are NOT a head-to-head on the EVT axis.
Every partition below that compares the engines is taken on the **REGISTERED**
column, which is the column where the comparison means what it looks like.)

The four HLT delay sweeps, both legs, re-measured:
`ucore` **91/97, 90/95, 40/46, 38/45 = 259/283**;
`sim` **91/97, 95/95, 44/46, 42/45 = 272/283**.

### §66.2 H4 — THE PARTITION, ON THE REGISTERED COLUMN

`s15_census --core {ucore,sim} --pop all` against this sitting's own reports,
`--core` matched to the report (R4's rule).  The ucore's family census
reproduces §58.4 / the census §3 cell for cell (`PF_LOST` 129 · `DATA_SEQ` 55 ·
`PF_GAINED` 46 · `SCHEDULE` 34 · `TAIL_EXTRA` 33 · `PF_ADDR` 12 · `PIN` 12,
catch-all **0**).

**`DATA_SEQ` on the REGISTERED column, partitioned seed by seed:**

| | seeds |
|---|---|
| ucore `DATA_SEQ` | **41** |
| sim `DATA_SEQ` | **28** |
| **sim-ONLY** (the ucore is exact, the model is not) | **0** |
| **ucore-ONLY** (the model is exact, the ucore is not) | **4** — `mc1/1937`, `mc1/3325`, `mc2/3291`, `t30-raw/84` |
| shared, `DATA_SEQ` in BOTH engines | **28** |
| shared, `DATA_SEQ` in the ucore and ANOTHER family in the model | **9** (`PF_LOST` 4 · `SCHEDULE` 3 · `TAIL_EXTRA` 2) |

**So the census's *"41 against 28, the ucore is WORSE"* is 4 defects plus 9
RELABELS, not 13 defects.**

**PARTITION B's INVARIANT, and it is exception-free but for one seed:** on
**27 of the 28** seeds that are `DATA_SEQ` in both engines the two engines'
FIRST DIVERGING ROW is the SAME ROW INDEX with the SAME first-divergence
detail, and `s15_census`'s slot coordinates (`at_cyc`, the chip cell and the
engine cell) agree on **28 of 28**.  The one exception is `mc1/2241`.  *This is
one shared defect seen from two sides, not two.*  Its shape is a wrong
**ADDRESS** at a `MEMR` launch (27 of 28), not a wrong word — so **T8's
load-side byte-swap signature does NOT generalise to `DATA_SEQ`**: only 9 of
the ucore's 55 `DATA_SEQ` seeds have a `data` first-kind at all, and on the 4
ucore-only ones `chip_word != swap8(ucore_word)` (checked; `9090`/`f896`,
`0000`/`3f01`, `0480`/`0499`, `0000`/`8b39`).

### §66.3 H4 — WHAT PARTITION A ACTUALLY IS: **A TESTBENCH DEFECT, NOT THE CORE**

The four ucore-only `DATA_SEQ` seeds were read row by row against the chip and
against the regenerated image (`ucsim_fuzz.regen`).  On all four the divergence
is the DATA PHASE of a read whose T1 address both engines agree on, and:

* the CHIP's word is what the seed's own image holds at that address;
* the ucore's word is **nowhere in the 64 KB image** on 3 of 4;
* on all four, an **`IOW` cycle earlier in the same run wrote that word to a
  PORT whose number equals the memory address later read.**

`hdl/tb/tb_v30_core.sv`'s memory commit is gated on
`lat_write = lat_type == 3'b110 || lat_type == 3'b010` — **`3'b010` is `IOW`** —
so **an I/O write stores into `mem[]`.**  The read side is not symmetric: `IOR`
is served from `iord_ser` and `INTA` from `INT_VECTOR`, neither from `mem`.
The socket harness does not do this (that is exactly why the chip reads the
image), and `sim/` does not (it is exact on all four).

**Chip-side census, engine-free** (chip rows only, over the 2,710 scored
seeds): **37** seeds contain an `IOW` whose port number is later READ as
memory.  The ucore is non-exact on **37 of 37**; the model is exact on **8** of
them, and **7 of those 8 are REGISTERED seeds** — `mc1/412`, `mc1/1937`,
`mc1/3325`, `mc2/2216`, `mc2/3291`, `t30-raw/84`, `t30-raw/123` — i.e.
**seven of the NINE seeds `gaps` §T.2 calls "the ucore's OWN registered-bank
residue".**  The remaining two are `mc1/721` (§49.8's `10`/ADC carry-in) and
`mc2/584` (`qs F!=-`).

**THE FIX (rig, one term).**  The memory commit is for MEMORY writes:
`lat_write` keeps `3'b110` for the commit and drops `3'b010`.  Nothing else
changes; `lat_write` is not used anywhere else that an IOW should reach.

**THE BARS, REGISTERED BEFORE THE RUN.**

* **P1 (the attribution)** — with the commit restricted to `MEMW`, **at least
  6 of the 7** REGISTERED seeds above become **cycle-exact** in the ucore leg.
  Point estimate **7 / 7**.  **Fewer than 5 ⇒ the attribution is REFUTED**, the
  TB change is reverted and the finding is reported as a refutation.
* **P2 (no golden depends on it)** — `check_core --core ucore --opcodes all
  --cases 0` stays **169,000 / 169,000**; `f4a_boundary` **160/160**;
  `f0lock_tranche` **400/400**; and the 23 `v0.3` block-I/O forms stay
  **229,999 / 229,999** (`OUTM` is the one golden family that drives `IOW`, so
  this is the load-bearing cell of P2).
* **P3 (monotone)** — `timed_fuzz --core ucore` REGISTERED **>= 1,483**, EVT
  **>= 906**, b2 tranche **>= 171 / 188**; the four HLT sweeps **unchanged** at
  91/97, 90/95, 40/46, 38/45 (no `IOW` occurs in them).
* **P4 (the model is untouched)** — `timed_fuzz --core sim` is **1,272 / 780 /
  2,052 to the seed**: the model does not use this TB.
* **P5 (the shared instrument)** — the TB is shared with the ARCHIVED FSM core
  and with `check_fuzz_bank` through `check_seq.BIN`.  `check_core --core fsm
  --opcodes all --cases 0` must stay at its corrected **168,400 / 169,000**, and
  `check_fuzz_bank --strict` is re-run and **reported as measured**; if it
  reports `new-sig TIMING > 0` that is a registered outcome to be reported, NOT
  silently admitted (§60.1's admission is not re-opened here).

*Falsifier*: any of the seven still non-exact with the SAME `data` detail after
the change; or a golden cell that moves.

**WHAT IS NOT CLAIMED.**  Partition B (the 28 shared) is NOT explained here.
It is left as a partition with an invariant and a directed instrument
(§66.6).

### §66.4 H5 — THE 13 CELLS, SEPARATED CELL BY CELL

Both legs re-measured per case (`check_core --core ucore --details 100` and a
per-case run of `timed_gate`'s own scorer), by the `idx` FIELD, which is the
pin delay `d` (§43.0's numbering trap):

| sweep | ucore fails `idx` | model fails `idx` | ucore-ONLY |
|---|---|---|---|
| `s10-w0` `HLT.INT` | 2,3,4,5 | 2,3,4,5 | — |
| `s10-w0` `HLT.RES` | 2,3 | 2,3 | — |
| `s10-w1` `HLT.INT` | 7,8,9,10 | — | **7,8,9,10** |
| `s10-w1` `HLT.RES` | 7 | — | **7** |
| `s13-w2` `HLT.INT` | 9,10,11,12,13 | 10,11 | **9,12,13** |
| `s13-w2` `HLT.RES` | 9 | — | **9** |
| `s13-w3` `HLT.INT` | 11,12,13,14,15,16 | 12,13,14 | **11,15,16** |
| `s13-w3` `HLT.RES` | 11 | — | **11** |

**24 ucore / 11 model, the model's a strict subset, 13 ucore-only** — §T.1
reproduced exactly.  Split by FIRST-DIVERGENCE COLUMN, per cell:

| half | cells | which |
|---|---|---|
| **F43, the `busstat` half** | **6** | `HLT.INT` and `HLT.RES` at **`d = 2w + 5`** for w = 1, 2, 3 — i.e. w1 `d=7`, w2 `d=9`, w3 `d=11`, **one cell per form per wait level, exactly as F43 registered**.  All six: `busstat exp 'PASV' got 'HALT'`, the ucore drives the HALT display on a row where the golden never does. |
| **the undiagnosed `seg`/`bus` half** | **7** | `HLT.INT` only: w1 `d=8,9,10`; w2 `d=12,13`; w3 `d=15,16`.  All at the TOP of each sweep's `d` band, immediately above the model's own failing band at w2/w3 (10,11 and 12,13,14).  Signature `seg exp 'CS' got 'SS'` with the composed bus differing by exactly `0x10000` — the S4:S3 segment indicator, `10` (CS) against `01` (SS). |

6 + 7 = 13, no remainder, no catch-all.

### §66.5 H5 — F43 RE-EXAMINED, AND WHY THE DECLINE NO LONGER HOLDS

**The decline, quoted.**  §43 (U3): *"NOT LANDED, for a stated reason.  It
touches the eval instant — the spine of the whole BIU — while `check_core
--core ucore --opcodes all --cases 0` is at 169,000/169,000 and four
whole-program ladders were being scored against this binary."*  Codex C7
concurred: *"Diagnosis sound; not landing it is the right call"* — it *"touches
the BIU display/eval spine"* and §43 had *"a diagnosis and a falsifier but no
gate proof"*.  §54.3 (U5) declined again *"for §43's own stated reason (it
touches the BIU's eval instant, the module's spine, at a closure)"*.

**The reasoning was never about the mechanism.**  Both declines are scheduling
arguments: *a closure is being scored against this binary, do not move the
spine now.*  Neither says the mechanism is wrong; C7 endorsed it and only
corrected its WORDING.  Three things have since changed:

1. the campaign is no longer at a closure — this is the silicon-match phase,
   whose governing directive is that *"a divergence from silicon is a work item
   regardless of whether the model shares it"*;
2. the comparator changed at U5 and **F51 landed in exactly this block**
   (`v30u_biu.sv`'s HALT display), so the spine has already been moved once
   under the current instrument, with a full re-score and zero deltas;
3. §43's own worry — *"no gate proof"* — is answerable now: the sweeps are the
   gate, they are banked, they score in under a second per leg, and the whole
   ucore ladder re-runs offline.

**So the decline is retired on its own terms, and the mechanism is landed.**

**WHAT IS BEING LANDED — one tap, no new state, no new number.**  F43's
sentence is *"the HALT-display decision must test the wake condition visible on
its OWN decision edge."*  M20 threshold 1 says the display at clock `H` is
suppressed when the wake decision `D` satisfies `D <= H`; `D = A + 3` is
MEASURED at 100 % on all four `evt` cells.  The display's decision edge is the
edge ending `H-1`, where `eu_unhalt` reads `int_p[2]` — the pin at `c-3` — and
is therefore true only for `D <= H-1`.  The condition `D == H` is visible at
that same edge one stage further down the SAME pipeline: `int_p[1]`, the pin at
`c-2`.  This is the construction `v30u_eu.sv` already uses, verbatim, for the
REP boundary: *"the two anchors the SPEC records are one clock apart … tap
`c-3` and tap `c-2` … Nothing here is fitted: both taps are `edge - 4`."*

```
v30u_eu.sv    wire hlt_wake_disp = (st == S_HALTED) && !irq_nmi_lvl && int_p[1];
              assign eu_unhalt_disp = hlt_wake_disp || unhalt_pend;
v30_core.sv   one wire
v30u_biu.sv   the display test at the S8/S9 block gains ONE TERM:
                  if (halt_pending && !run && !cmt_valid && !set_noeval
                      && !eu_unhalt_disp)
```

No flop is added, so **`SS_VERSION` stays `0x83` and `SS_COUNT` stays as
mapped**; `ss_lint` must still exit 0 with 0 UNMAPPED.

**THE BARS, REGISTERED BEFORE THE RUN.**

* **Q1 (MUST MOVE UP)** — the four HLT sweeps: the **6 F43 cells close**, i.e.
  `s10-w1` **>= 92/95**, `s13-w2` **>= 42/46**, `s13-w3` **>= 40/45**, total
  **>= 265 / 283** against 259.  The point estimate is exactly **265**.
* **Q2 (w0 IS ALLOWED TO MOVE, IN ONE DIRECTION ONLY)** — `s10-w0` is
  **>= 91/97**.  `HLT.RES d=3` and `HLT.INT d=3` at w0 carry the SAME
  `busstat exp 'PASV' got 'HALT'` signature and are MODEL-SHARED, so they may
  close and take the ucore above the model at w0; they may **not** open.
* **Q3 (the undiagnosed half must not move)** — the 7 `seg`-first cells stay
  failing; if any of them closes, the two halves are not independent and that
  is REPORTED, not absorbed.
* **Q4 (MUST NOT MOVE)** — `check_core --core ucore --opcodes all --cases 0`
  **169,000 / 169,000**; the four `evt` golden cells **200 / 1,200 / 200 /
  1,200**; `v0.1-w1evt-biased` **1,200**; `v0.1-w1`/`-w3` **1,200 / 1,200**;
  `EB` at w1 **200**; `check_boot --core ucore` **220 and 400**;
  `ulockstep --golden all --cases 50` **17,350 / 17,350**;
  `timed_wvec_gate --core ucore` **88/88, +0.0 %**;
  `timed_enter_replay --core ucore` **154/154 x5**;
  `timed_ins_replay --core ucore --raw` **1,312 / 1,312** and **2,624 / 2,624**;
  `timed_fuzz --core ucore` REGISTERED / EVT / b2 **monotone, never down**;
  `ss_lint` exit 0, 0 UNMAPPED; `check_core --ce-div 4 --ce-hold-check`
  `CE_HOLD_VIOL 0`.
* **Q5** — `x1_retention.py`'s offline baseline / `X1_AD_RETENTION` legs are
  re-run and reported; they are the fabric-shaped scorer for these same cells.

*Falsifiers*: `ulockstep` not 17,350 (the two engines are then not rendering the
same mechanism, and the landing STOPS); any Q4 ratchet down; fewer than 6 F43
cells closing; a `seg`-half cell closing.

### §66.6 WHAT THIS SITTING WILL NOT DO

* **No board contact**, and no cell is requested.
* **Partition B (H4's 28 shared `DATA_SEQ` seeds) is not fixed.**  It is a
  model-owned class and the session that measures it does not also land it.
* **The 8080 / `gaps` §F.1 work is not opened** (a pending USER decision).
* **`s15_census` is not modified**; no memory file is touched; Codex is not
  launched.

## §67 SESSION SM3, SITTING 6 — THE RESULTS, REPORTED AS REGISTERED

**2026-08-04, branch `ucsim`.  Offline only, NO BOARD CONTACT.**  §66 is the
pre-registration and was committed before either change was built.  Everything
below is re-run on this tree; nothing is cited.

### §67.1 H4 — **P1 MET AT ITS POINT ESTIMATE, 7 / 7.  THE RIG WAS THE DEFECT.**

`hdl/tb/tb_v30_core.sv`: the memory commit's guard is now `lat_memw`
(`lat_type == 3'b110`) instead of `lat_write`, so an `IOW` no longer stores into
`mem[]`.  `lat_write` is UNCHANGED where it belongs — `core_data_drive` still
hands the data lanes to a write of either kind.  **One term; nothing else in
the TB, and no engine, was touched by this change.**

| bar | registered | **measured** |
|---|---|---|
| **P1** the 7 REGISTERED seeds | **>= 6 / 7**, point estimate 7 | **7 / 7** — `mc1/412`, `mc1/1937`, `mc1/3325`, `mc2/2216`, `mc2/3291`, `t30-raw/84`, `t30-raw/123` are all CYCLE-EXACT |
| — seeds improved / worsened, whole bank | — | **9 improved, 0 worsened** (the 7 above + `mc1/2850`, `mc1/3741` on the EVT axis) |
| **P2** `check_core --core ucore --opcodes all --cases 0` | 169,000 | **169,000 / 169,000** |
| **P2** `f4a_boundary` / `f0lock_tranche` | 160 / 400 | **160 / 160** and **400 / 400** |
| **P2** the 23 `v0.3` block-I/O forms (`OUTM` drives `IOW`) | 229,999 | **229,999 / 229,999** cycles AND arch |
| **P3** `timed_fuzz --core ucore` REGISTERED | >= 1,483 | **1,490 / 1,702** (+7) |
| **P3** … EVT | >= 906 | **908 / 1,008** (+2) |
| **P3** … COMBINED | — | **2,398 / 2,710** (+9) |
| **P3** b2 victory tranche | >= 171 | **172 / 188** (+1) |
| **P3** the four HLT sweeps | unchanged | **91/97, 90/95, 40/46, 38/45** — unchanged, cell for cell |
| **P4** `timed_fuzz --core sim` | 1,272 / 780 / 2,052 | **1,272 / 780 / 2,052, to the seed** |
| **P5** `check_core --core fsm --opcodes all --cases 0` | 168,400 | **168,400 / 169,000** |

**WHAT THIS DOES TO `gaps` §T.2.**  Seven of the nine seeds that document
*"the ucore's OWN registered-bank residue"* were the testbench's.  Re-partitioned
on this sitting's own reports, **the ucore's registered-bank ucore-only residue
is TWO seeds**:

| seed | first divergence | `ndiff` | what it is |
|---|---|---|---|
| `mc1/721` | `data b084 != b085` | **2 / 968** | §49.8 item 2, the `10`/ADC carry-in.  Its deciding measurement (`+ss_at` on `SSA_E_PSW`) is still written down and still un-run |
| `mc2/584` | `qs F != -` | 404 / 1,774 | not `data`, and not covered by any of §49.8's three sub-mechanisms |

**§T.2's *"eight of nine are `data`"* now reads: seven of the eight were the
instrument.**  The remaining `data` seed is `mc1/721` and it is off by ONE.

*Falsifier for the attribution, and it did not fire*: no seed regressed, and
every golden that reaches `IOW` (the 23 block-I/O forms) is unmoved.

**WHY NOTHING WAS SCORED WRONG THAT CANNOT BE RE-SCORED.**  The defect is in a
REPLAY instrument, not in a capture: every chip row in the bank was taken on the
socket, where the harness does not do this — which is exactly how the defect was
found (the chip reads the seed's own image at an address the RTL legs read the
I/O datum from).  No golden and no capture is invalidated, and `INV-1` is not
re-opened.  The figures that move are the RTL legs' own replay scores, and they
move **UP**, itemised above.

### §67.2 H4 — WHAT IS **NOT** CLOSED: PARTITION B, AND ITS DIRECTED INSTRUMENT

§66.2's partition B — the **28** REGISTERED seeds that are `DATA_SEQ` in BOTH
engines, with the SAME first diverging row and the SAME detail on **27 of 28** —
is untouched and is NOT the rig: the two engines agree with each other and
disagree with the socket, which is §49.7's class scaled from 4 seeds to 27.
Its shape, measured: the first parting is a `MEMR` LAUNCH ADDRESS (27 of 28),
`delta = 0` at the slot in most, and `ndiff` in the thousands — the run takes a
different path from there, so it is a FUNCTIONAL divergence with a timing
family label, not a timing family.

Three of the 28 are especially sharp and are the directed instrument this
sitting produces, board-free: `mc2/1718`, `mc2/3061` and `t30-raw/899` have the
chip reading **`0x00004`** — the INT 1 vector — where both engines read a
computed effective address.  *The chip takes an entry the engines do not.*
`t30-raw/962` is the cheapest member (`ndiff = 4` of 4,000).

*The measurement, specified*: replay those four with `v30sim image --trace` and
the ucore's `+ss_at` at the divergent clock and compare the ARCHITECTURAL state
(PSW's trap/break bits above all) at the last agreeing instruction boundary.
**Not run here** — the session that measures a class does not also land it.

### §67.3 H5 — **Q1 MET AT ITS POINT ESTIMATE.  F43 IS LANDED AND THE SIX CELLS CLOSED.**

The landing is §66.5's, exactly: `v30u_eu.sv` publishes `eu_unhalt_disp` —
the same wake read one stage further down the same pin pipeline (`int_p[1]`
against `eu_unhalt`'s `int_p[2]`) — `v30_core.sv` carries one wire, and
`v30u_biu.sv`'s S8/S9 display test gains ONE TERM.  **No flop was added.**

| bar | registered | **measured** |
|---|---|---|
| **Q1** `s10-hltsweep-w1` | >= 92 / 95 | **92 / 95** |
| **Q1** `s13-hltsweep-w2` | >= 42 / 46 | **42 / 46** |
| **Q1** `s13-hltsweep-w3` | >= 40 / 45 | **40 / 45** |
| **Q1** total | >= 265 / 283 | **265 / 283** (was 259) |
| **Q2** `s10-hltsweep-w0` | >= 91 / 97 | **91 / 97**, failing set unchanged (`HLT.INT` 2,3,4,5 · `HLT.RES` 2,3) |
| **Q3** the 7 `seg`-first cells | must NOT close | **none closed** — `HLT.INT` w1 8,9,10 · w2 12,13 · w3 15,16 still fail |

**Exactly the six F43 cells closed and nothing else moved on these sweeps.**
The ucore's failing set is now `HLT.INT` w0 2,3,4,5 · w1 8,9,10 · w2 10,11,12,13
· w3 12,13,14,15,16 and `HLT.RES` w0 2,3 — **18 cells against the model's 11,
so the ucore-only count is 13 -> 7**, and every one of the 7 is the undiagnosed
`seg`/`bus` half.  `HLT.RES` is now **PERFECT at w1, w2 and w3** (49/49, 25/25,
25/25); its only failures are the two model-shared w0 cells.

**AND THE ucore DID NOT MOVE AWAY FROM THE MODEL.**  The model already passes
all six of these cells (it is 95/95 at w1), so F43 brought the RTL TO the
reference, not away from it — which is why `ulockstep` is untouched.

**Q4 — THE FULL LADDER, RE-RUN ON THE FINAL BINARY:**

| gate | registered | **after F43** |
|---|---|---|
| `check_core --core ucore --opcodes all --cases 0` | 169,000 | **169,000 / 169,000** |
| `v0.1-w1` / `-w3` | 1,200 / 1,200 | **1,200 / 1,200** |
| `v0.1-w1 --opcodes EB` | 200 | **200 / 200** |
| the four `evt` cells | 200 / 1,200 / 200 / 1,200 | **200 / 1,200 / 200 / 1,200** |
| `v0.1-w1evt-biased` | 1,200 | **1,200 / 1,200** |
| `f4a_boundary` / `f0lock_tranche` | 160 / 400 | **160 / 160** and **400 / 400** |
| the 23 `v0.3` block-I/O forms | 229,999 | **229,999 / 229,999** |
| `check_boot --core ucore` 220 / 400 | MATCH | **MATCH / MATCH** |
| **`ulockstep --golden all --cases 50`** | 17,350 | **17,350 / 17,350 ALL CASES LOCKSTEP** |
| `timed_wvec_gate --core ucore` | 88/88, +0.0 % | **88/88, 16,048 vs 16,048, +0.0 %** |
| `timed_enter_replay --core ucore` | 154/154 ×5 | **154 / 154** (full, active, halt_display) |
| `timed_ins_replay --core ucore --raw` | 1,312 / 2,624 | **1,312 / 1,312** and **2,624 / 2,624**, 173,556/173,556 same-T1 |
| `timed_fuzz --core ucore` REGISTERED | >= 1,490 | **1,490 / 1,702** |
| … EVT | >= 908 | **910 / 1,008** (+2 more) |
| … COMBINED | — | **2,400 / 2,710** |
| b2 victory tranche | >= 172 | **172 / 188** |
| `BOUND WARNINGS` / `ENGINE ABORTS` | 5 / 0 | **5 / 0** |
| `ss_lint.py` | rc 0, 0 UNMAPPED | **rc 0, 205 flops, 0 UNMAPPED, `SS_VERSION` 0x83 unchanged** |
| `check_core --ce-div 4 --ce-hold-check` | `CE_HOLD_VIOL 0` | **`CE_HOLD_VIOL 0`** on all cells |
| `check_ab_sim --core ucore` | 187 rows MATCH | **MATCH over 187 rows** |
| **Q5** `x1_retention offline` (the same TB column) | 259 / 283 | **265 / 283** — it IS the `tb_v30_core` column |
| **Q5** `x1_retention` `tb_sys` legs | 143 / 259 | **see §67.6 — the binaries were STALE and the run is NOT a measurement of this tree** |

**No falsifier fired.**  `ulockstep` is exact; no Q4 ratchet moved down; six
cells closed, not fewer; no `seg`-half cell closed.

### §67.4 THE RATCHETS THAT MOVED, ITEMISED

| ratchet | before | **after** | which change |
|---|---|---|---|
| `timed_fuzz --core ucore` REGISTERED | 1,483 / 1,702 | **1,490 / 1,702** | the TB (§67.1) |
| `timed_fuzz --core ucore` EVT | 906 / 1,008 | **910 / 1,008** | TB +2, F43 +2 |
| `timed_fuzz --core ucore` COMBINED | 2,389 / 2,710 | **2,400 / 2,710** | both |
| b2 victory tranche | 171 / 188 | **172 / 188** | the TB |
| the four HLT sweeps | 259 / 283 | **265 / 283** | F43 |
| `x1_retention offline` | 259 / 283 | **265 / 283** | F43 (it is the same TB column) |
| the ucore's REGISTERED ucore-only residue | 9 seeds | **2 seeds** | the TB |

Everything else in `standing_gates.md` §B is unmoved and was re-measured, not
inherited.

### §67.5 WHAT THIS SITTING DID NOT DO

* **No board contact**, and no cell is requested.  §67.2's directed instrument
  is offline.
* **Partition B is not fixed** (§67.2), and the 7 `seg`/`bus` HLT cells are
  still **NOT DIAGNOSED** — their signature is `seg exp 'CS' got 'SS'` with the
  composed bus differing by exactly `0x10000` (the S4:S3 indicator), all on
  `HLT.INT`, all at the top of each sweep's `d` band.  Booked, not absorbed.
* **The 8080 / `gaps` §F.1 work was not opened** (a pending USER decision).
* **No memory file was touched and Codex was not launched.**

### §67.6 A RIG-INTEGRITY FINDING NOBODY WAS LOOKING FOR — **THE VACUOUS-GATE PATTERN, SIXTH INCARNATION**

`x1_retention.py capture` binds to `hdl/tb/obj_dir_sys{,_ret}/tb_sys` and
**checks only that the file EXISTS** (`if not _LEG["bin"].exists(): sys.exit`).
Nothing in the tree rebuilds it, and there is no build script for it at all —
`tb_sys` was built ad hoc when §58.6 created it.  Both binaries date from
**07:04 / 07:05 on 2026-08-04**, i.e. before this sitting's RTL.

Run as-is after F43 the tool reported **`ret` 259 vs offline 265, 6 SURVIVORS,
BAR (i) NOT MET**, and the six survivors were **exactly the six F43 cells with
exactly the F43 signature** (`first = (5|6|7, 'busstat', 'PASV')`).  That is not
a refutation of anything; it is a **stale binary scoring old RTL against a new
reference column.**  Reported here rather than quoted anywhere as a result.

This is the same failure mode as `sm3_residue_census` §7 item 1 (the stale
`Vtb_v30_core` that `check_seq` never rebuilds) and it is the FIFTH and SIXTH
instances of *a gate that binds to a binary nothing in the tree owns*.
**A standing fix is routed, not taken here** (it belongs with whoever next opens
the `tb_sys` path): give `x1_retention` a `build()` with `tb_sys.sv`,
`system_large.sv` and `CORE_RTL["ucore"]` in its dependency set, exactly as
`check_core.build()` already does for `tb_v30_core`.

**THE RE-RUN, PRE-REGISTERED BEFORE THE REBUILD.**  Both legs are rebuilt from
this tree and re-captured.  Predicted, from the arithmetic of the old run
(`base` 140 failing = 24 offline failures + 116 INTA-class; offline is now 18):

| leg | before (stale) | **predicted** |
|---|---|---|
| `tb_sys` base | 143 / 283 | **149 / 283** |
| `tb_sys` ret | 259 / 283 | **265 / 283**, equal to `offline` |
| bar (i) | 116 closed, 6 survivors | **116 closed, 0 survivors** |
| bar (ii) | 6 differing | **0 differing** |

**AND A CONSEQUENCE THAT MUST BE STATED WHATEVER THE RESULT.**  The fabric
baseline that §58.6 and §59.7.1 record — *"`tb_sys` base reproduces the fabric's
143/283 exactly"* — is a statement about the RTL **the bitstream carries**.
FLASH #3 does not carry F43.  If `base` moves to 149 the Verilated integration
and the flashed bitstream no longer agree, **and that is correct**: the
correspondence is re-established by a re-flash, not by keeping the RTL still.
**No board was touched this sitting and none is asked for.**

### §67.7 THE REBUILT `tb_sys` LEGS — **BOTH X1 BARS MET, 0 SURVIVORS, AND THE `base` NUMBER MISSED ITS PREDICTION BY 3**

Both legs rebuilt from this tree (the stale directories archived by rename to
`hdl/tb/obj_dir_sys{,_ret}.stale-070{4,5}` — nothing deleted) and re-captured,
283 cells each, **0 errors**.  Reported as registered:

| | §67.6 predicted | **measured** |
|---|---|---|
| `tb_sys` base | 149 / 283 | **146 / 283** — **MISSED by 3** |
| `tb_sys` ret | 265 / 283 | **265 / 283** ✅ |
| `offline` (`tb_v30_core`) | 265 / 283 | **265 / 283** |
| base-only failures | 116 | **119** |
| …of which the golden's first-divergence row is an **INTA** row | 116 | **119 of 119** |
| **BAR (i)** all base-only close, total == offline exactly | MET | **119 closed, 0 SURVIVED, 265 == 265 — MET** |
| **BAR (ii)** nothing else moves | MET | **0 cells differing from offline — MET** |

**THE MISS, AND WHAT IT MEANS.**  The prediction assumed all six F43 cells
would pass in the retention-FREE integration once F43 landed.  Three of them do;
**the other three ALSO carry an INTA-row failure in `base`**, so they moved out
of "fails everywhere" and into the **base-only INTA class** instead — which is
why `base` rose by 3 rather than 6 (140 → 137 failing) and the INTA class rose
by 3 (116 → 119).  The arithmetic closes exactly: `137 = 18 + 119`.
**The class got PURER, not weaker: 119 of 119, still no counter-population.**

**AND THE STALE RUN IS RETRACTED IN ITS ENTIRETY.**  §67.6's "6 SURVIVORS /
BAR (i) NOT MET" was a stale binary scoring pre-F43 RTL against a post-F43
reference column.  On the rebuilt instrument there are **ZERO** survivors.  The
survivors were the F43 cells and nothing else, which is itself the check that
the rebuild is the only variable.

**THE FABRIC CORRESPONDENCE IS NOW BROKEN, DELIBERATELY AND ON THE RECORD.**
§58.6's *"`tb_sys` base reproduces the fabric's 143/283 exactly"* was true of the
RTL FLASH #3 carries.  With F43 in the tree the Verilated integration is
**146/283** and the flashed bitstream is still 143.  **That is a re-flash item,
not a defect**, and until a re-flash happens **no fabric figure may be quoted
against this tree's `tb_sys`**.  C11's `NOT ESTABLISHED` on the X1 attribution
is UNCHANGED — this leg was never able to establish it, and §56.3a's bar is
written on fabric numbers plus a socket control.  **No board was touched.**

**A SECOND RIG DEBT, ROUTED.**  `tb_sys` has no build recipe anywhere in the
tree; the rebuild above reconstructed one from
`hdl/tb/obj_dir_sys/Vtb_sys__ver.d`'s dependency list and `check_core.build()`'s
flag set (plus `-Wno-MULTIDRIVEN -Wno-PINCONNECTEMPTY`, which `tb_sys.sv`'s AXI
task-driven handshake needs).  It belongs in `x1_retention.build()` with a
dependency check, and it is **not taken here**.

### §67.8 THE POST-FIX `DATA_SEQ` CENSUS — H4's FAMILY, RE-TAKEN

`s15_census --core ucore --pop reg` on this sitting's own post-landing report
(`--core` matched to the report):

```
  212 non-exact REG seeds (was 219)
  PF_LOST 106 · DATA_SEQ 36 · TAIL_EXTRA 29 · PF_GAINED 24 · PF_ADDR 8 ·
  SCHEDULE 5 · PIN 4      catch-all 0
```

**`DATA_SEQ` on the REGISTERED column is 41 -> 36** against the model's 28, and
**the ucore-only part of it is now ZERO** — the two remaining ucore-only REG
seeds are `mc1/721` (`PIN`) and `mc2/584` (`PF_ADDR`), neither of them
`DATA_SEQ`.  What is left of H4 is **§67.2's partition B and the relabels**:
seeds the model misses too, on 27 of 28 of which the two engines' first
divergence is byte-identical.  **H4 is no longer a place where the ucore is
worse than the model in its own right.**

### §67.9 P5's SECOND HALF — `check_fuzz_bank --strict`, REPORTED AS REGISTERED

§66.3's P5 registered this as *"re-run and reported as measured; if it reports
`new-sig TIMING > 0` that is a registered outcome to be reported, NOT silently
admitted."*  It did.

```
  IMPROVED mc1/1937 : FUNCTIONAL -> TIMING
  IMPROVED mc1/3325 : FUNCTIONAL -> TIMING
  IMPROVED mc1/3741 : FUNCTIONAL -> TIMING
  IMPROVED mc1/412  : TIMING -> KNOWN_ACCEPTED
  IMPROVED t30-raw/123 : FUNCTIONAL -> TIMING

check_fuzz_bank: FAIL | 3242 banked seeds | stable 3237 improved 5 worse 0
                | gen_drift 0 regen_err 0 | float-floor 0
                | new-sig TIMING 3 (strict-fail)
```

**`worse` is ZERO and `gen_drift` is ZERO.**  The gate's `FAIL` is entirely the
`--strict` novelty clause: three signatures that were never in the ledger
appeared, because five seeds now replay to a BETTER verdict and a better verdict
has a different signature.  All five are in this sitting's own `IOW` population
(§66.3), which is the corroboration that matters: **`check_fuzz_bank` binds to
the ARCHIVED FSM core, so the TB fix improves the FSM leg on the same seeds it
improves the ucore's.  A defect in the shared instrument is exactly what that
looks like; a defect in the ucore is not.**

**THE ADMISSION IS NOT TAKEN AND IS ROUTED TO THE COORDINATOR**, per §60.1's
precedent (`sw/sm3_sig_admit.py` exists, refuses to write without a control, and
records an `admissions` entry).  A signature admitted without provenance changes
what "new" means for the next campaign.  Nothing was written to
`tests/v30/fuzz_bank/sig_ledger.json` this sitting; `sigs` is still **11,845**.
The decision is: admit the 3 with an `admissions` record naming this sitting's
TB fix as their cause, or leave `--strict` red until someone does.

*The control that would go with the admission, if it is taken*: the 3 must be
reachable ONLY from the 5 improved seeds — `sw/sm3_sigctl.py --ledger <pre>`
already computes exactly that.

## §68 SESSION SM3, SITTING 7 — FLASH #5, AND THE THREE DIRECTED CELLS

**2026-08-04, branch `ucsim`, from HEAD `2e93cd0499`.  Task #36.  A BOARD
SITTING WITH FLASHING AUTHORISED.**  Pre-registration committed at
**`8339740709`** BEFORE the first board contact:
`docs/notes/sm3_s7_prereg_2026-08-04.md`.  Single writer confirmed before
contact (`0 users`, no serve process on `mister-nec`) and again before the
flash; the divider PINNED with `div_guard`'s readback recorded in every
manifest (`div=8 (4 MHz), commanded by this connection` -> **PINNED**); full
per-clock rows + raw 64-bit words + `SHA256SUMS` retained for every cell;
`use_core` was **False** as found and is **False** as left, verified on the
board; `board_idle()` run at the end and **OK**; **0 transport errors in the
whole sitting**.

> **Standing principle, applied throughout.**  *"This is 80's era hardware,
> they aren't wasting silicon on anything that isn't necessary.  Complex or
> confusing behavior that we see is likely to be simple systems interacting in
> ways you do not fully understand yet."*

**NO ENGINE WAS CHANGED.**  `git diff 2e93cd0499 -- hdl/rtl hdl/tb sim/` is
EMPTY at the close of this sitting, so every ratchet in `standing_gates.md` §B
is unmoved **by construction and not by assumption**.  The only tree changes
are `sw/` instruments, retained captures, and (§68.8) the novelty ledger.

### §68.1 THE BITSTREAM — **ALL QUARTUS BARS MET; FLASH #5**

`gen_ucore_qsf.py --check` green first (`nec_test_ucore.qsf` is up to date),
then `quartus_sh --flow compile nec_test -c nec_test_ucore`, 17.1.0 Lite,
`5CSEBA6U23I7`, top `sys_top`.

| bar | registered | **measured** |
|---|---|---|
| errors, A&S / Fitter / Assembler / TimeQuest | 0 | **0 / 0 / 0 / 0** |
| latches as a RESOURCE | 0 | **0** (no latch line in the A&S resource summary) |
| `lpm_divide` | 0 | **0** |
| Fmax, core clock `emu\|pll\|…\|divclk` | >= 32 MHz | **45.67 MHz** |
| worst setup slack | > 0 | **+9.355 ns** (`divclk`); tck +9.226, CLK2_50 +13.510, audio +24.433 |
| TNS, every domain, setup AND hold | 0.000 | **0.000 on all eight** (worst hold +0.249) |
| ALMs | — | **11,167 / 41,910 (27 %)**, 6,087 registers, 105/553 RAM blocks, 9/112 DSP, 2/6 PLL, 107/314 pins |

Against U4 pass 3 (11,078 ALMs / 45.56 MHz / +8.922 ns) the design is 89 ALMs
larger, 0.11 MHz faster and 0.43 ns slacker — three landings' worth of change
and no timing cost.

**The 23 `Warning (10240)` "inferring latch(es)" lines are pre-existing** and
are not the bar: all 23 name block-local temporaries (`ie_now`, `v1`, `bsw`,
`carry`, `taken`, …) inside `v30u_eu.sv`'s next-state `always @*` at line 2096,
which is the ucore's combinational spine and predates every landing in this
campaign.  The bar is the LATCH RESOURCE and it is zero.

**FLASH #5**, `sw/safe_flash.sh` with its VERIFY leg, appended to
`sw/testdata/flash_log.jsonl`:

```
  sof   hdl/output_files_ucore/nec_test_ucore.sof
  sha256 315de4bc9e304596b9c56a6cf36bde9fa2291e222d5548e927306de7d9fce98f
  ts    2026-08-04T22:36:55Z   git_describe 8339740709-dirty   verify OK
  (the `-dirty` is the sitting's own retained captures, not source)
```

**FIRST LIGHT — the prediction MET.**  `sw/check_ab_hw.py all 800`:
**chip-vs-golden MATCH over 800 rows**, **core-vs-chip MATCH over 800**,
**core-vs-golden MATCH over 800** — **800 / 800 on all three legs.**
`div_guard` **PINNED** on the first probe.

### §68.2 THE FABRIC RE-SCORE — **146 / 283, THE PREDICTION EXACTLY, AND THE FAILING SET IS IDENTICAL TO `tb_sys` BASE'S CELL FOR CELL**

`sw/u4_f42_fabric.py capture` (283 cells, **0 errors**, 8 s) then `score`:

| | §2 predicted | **measured** |
|---|---|---|
| total | **146 / 283** | **146 / 283** |
| `s10-hltsweep-w0` `HLT.INT` / `HLT.RES` failing | 48 / 2 | **48 / 2** |
| `s10-hltsweep-w1` `HLT.INT` / `HLT.RES` | 46 / **0** | **46 / 0** |
| `s13-hltsweep-w2` `HLT.INT` / `HLT.RES` | 21 / **0** | **21 / 0** |
| `s13-hltsweep-w3` `HLT.INT` / `HLT.RES` | 20 / **0** | **20 / 0** |
| the failing SET vs `tb_sys` base's 137 | — | **IDENTICAL, all 137 cells (set equality, not a count match)** |
| first divergence on an INTA row | 119 | **119 of 137**, and `137 = 18 + 119` closes exactly against the offline TB's 18 |

**§67.7's arithmetic is confirmed in silicon**: the Verilated integration and
the fabric now agree at 146, which is what the re-flash was for.  The
correspondence §67.7 deliberately broke is RE-ESTABLISHED.

**THE SIX F43 CELLS, WHICH IS WHERE A DISPLAY-NIBBLE CLAIM DIES (F42's lesson).**
On FLASH #4 all six failed in fabric with F43's own `busstat` signature.  On
FLASH #5:

| cell | FLASH #4 | **FLASH #5** | predicted |
|---|---|---|---|
| `s10-hltsweep-w1/HLT.RES` idx 7 | `row5:busstat` | **PASS** | PASS ✅ |
| `s13-hltsweep-w2/HLT.RES` idx 9 | `row6:busstat` | **PASS** | PASS ✅ |
| `s13-hltsweep-w3/HLT.RES` idx 11 | `row7:busstat` | **PASS** | PASS ✅ |
| `s10-hltsweep-w1/HLT.INT` idx 7 | `row5:busstat` | **`row13:bus`, golden row = `INTA T1`** | `row12:bus` — class ✅, INDEX MISSED by 1 |
| `s13-hltsweep-w2/HLT.INT` idx 9 | `row6:busstat` | **`row15:bus`, golden row = `INTA T1`** | `row14:bus` — same |
| `s13-hltsweep-w3/HLT.INT` idx 11 | `row7:busstat` | **`row17:bus`, golden row = `INTA T1`** | `row16:bus` — same |
| the `busstat` signature at `d = 2w+5`, w = 1,2,3 | 6 cells | **0 of 283 — EXTINCT** | EXTINCT ✅ |

**F43 IS IN FABRIC AND DOES IN FABRIC WHAT IT DOES OFFLINE.**  The three
`HLT.INT` cells did not close because they carry a SECOND, independent failure
on an INTA T1 row — the float class — which is exactly §67.7's reading of why
`tb_sys` base rose by 3 and not by 6, now confirmed on real pads.

**TWO REGISTERED MISSES, reported as registered and not restated:**

1. **the row INDEX** of the three `HLT.INT` cells is **13 / 15 / 17** where the
   prediction, taken from `tb_sys` base, said **12 / 14 / 16**.  The offset is
   **+1 on every one of the 119 INTA-class cells** and 0 on the other 18 — a
   systematic one-row phase difference between the two instruments' first
   -divergence COORDINATE, not a difference in which cells pass.  The failing
   SETS are identical.
2. **`s10-hltsweep-w0` idx 3, both forms**, was predicted UNCHANGED and its
   first-divergence row moved **`row3:busstat` -> `row4:busstat`**.  The cells
   still FAIL and still fail in the same column; one earlier display row is
   suppressed and the cell does not close.  The four w0 `busstat` cells
   (`HLT.INT` idx 2,3 and `HLT.RES` idx 2,3) remain the only `busstat` cells in
   the whole sweep, and they are the MODEL-SHARED pair (§66.5's Q2 allowed them
   to close; they did not, in fabric as offline).

**C11's `NOT ESTABLISHED` on the X1 attribution is UNCHANGED.**  This scorer
does not re-litigate it and was not used to.

**A RIG DEBT, ROUTED (the same class as §67.6/§67.7).**  `u4_f42_fabric` has no
LEG NAMING: `capture` writes `sw/testdata/u4-f42/*.core.json.gz` and a
re-capture on a new bitstream OVERWRITES the previous one's record.  Nothing
was lost — the files are tracked, so FLASH #4's capture was recovered from
`HEAD` and **archived by rename to `*.core_f4.json.gz`** (nothing deleted) —
but the tool should carry `--leg` the way `u4_tranche` does.  **Not taken here.**

### §68.3 THE b3 PRIORITY TRANCHE ON FLASH #5 — REPORTED AS MEASURED

New legs `chip_f5` / `core_f5`, written BESIDE the `_f4` pair and never over
it, each scored against the socket capture taken on its OWN bitstream.
200 cells per leg, **0 errors in 400 captures**, 13 s each.

| leg | FLASH #4 | **FLASH #5** |
|---|---|---|
| `chip_f5` (the socket, the reference) | 178 / 178 | **178 / 178 (100.0 %)**, excused 22 |
| `core_f5` (the ucore in fabric) | 176 / 178 (98.9 %) | **176 / 178 (98.9 %)**, excused 22, residue `bs = 2` |

Predicted `>= 176`; **MET**, and identical to FLASH #4 to the seed.  V0-V5's
margins are unmoved by three landings.

### §68.4 CELL (a) — **H1a: THE ARM IS NOT THE INTA CYCLE.  A2 IS REFUTED, AND NOTHING IS LANDED.**

240 captures (`swintnext` + `iretnext` × waits 0-3 × delays 6…35, `hold = 300`),
482 files with `SHA256SUMS` in `sw/testdata/sm3-h1acell/`, 26.9 s, 0 errors.

**THE SHAPE CONTROL IS PERFECT AND IT IS WHAT MAKES THE CELL READABLE.**
`entry_shape` classifies every first acknowledge's lead-in off the retained
rows with no engine: **`swintnext` 30/30 `swint-entry` at every wait level**
(a vector read below `0x400`, the bare handler at `0x0480`, the IRET's three
stack pops, the restarted prefetch, and NO INTA behind it) and **`iretnext`
30/30 `iret-only`** (the same IRET and restart, popping planted frames, no
entry of any kind).  The stimulus does exactly what it was built to do.

**THE CHIP, w0 — where the two candidates differ by TWO clocks:**

| stimulus | `refill L -> gap` | reading |
|---|---|---|
| `swintnext` | **L4 -> gap 6, 30 / 30** | **FLOORED** at `max(F1+6, F1+L+1)` |
| `iretnext` | **L4 -> gap 4 on 25 / 30** (min 4; 1 at 6, 3 at 8, 1 at 10 — later boundaries) | **UNFLOORED**, the back-to-back slot |

**THE ENGINE LEG ON THE SAME CAPTURES, AND IT IS THE DECIDER** (both engines
implement the INTA-only arm today, i.e. candidate A2):

| | chip | `ucore` | `sim` | agreement |
|---|---|---|---|---|
| `swintnext` ord 1, w0 | **gap 6** | **gap 4** | **gap 4** | **0 / 30, BOTH engines** |
| `iretnext` ord 1, w0 | gap 4 | gap 4 | gap 4 | **30 / 30** |
| `iretnext` ord **2+**, w0 (an INTA IS behind it now) | gap 6 | gap 6 | gap 6 | 99/101 and 101/101 |

*The same stimulus, the same boundary, un-floored at ordinal 1 and floored at
ordinal 2+ — and the engines get ordinal 2+ right and ordinal 1 wrong only when
a SOFTWARE ENTRY sits behind it.*  That is A1's signature and A2 cannot produce
it.  **§64.2's two banked seeds are reproduced at 30/30 on a directed
population that did not exist when the hypothesis was written**, which is
§64.1's rule satisfied.

**A2 IS REFUTED.**  §3's registered refuting outcome — *">= 95 % of
`swint-entry` first acknowledges UNFLOORED"* — did not fire; **0 of 30** are
unfloored.

**AND YET NOTHING IS LANDED, BECAUSE THE AUTHORISING OUTCOME IS NOT MET AS
WRITTEN.**  §3 required BOTH halves at `>= 95 %` **at every wait level**, and
the CONTROL half fails at w1/w2/w3, where `iretnext` sits at `L+1` (6, 7, 8).
The reason is a defect in the bar, and it is booked as one rather than
corrected after the fact: at `w >= 1` the floor `max(6, L+1)` COLLAPSES onto
`L+1`, so the coordinate cannot express "unfloored" there at all — and both
engines reproduce the chip exactly at those levels with an INTA-only arm, which
says the `L+1` term is structural and not the entry.  **The discriminating
regime is w0 alone, and the right statistic is the MINIMUM (a floor is a
minimum), not a proportion over all four levels.**  Re-reading a registered bar
onto a better statistic after seeing the data is exactly the manoeuvre §64.1
booked as an erratum, and it is not done here.

**DISPOSITION.**  H1a is **MEASURED AND DISCRIMINATED, NOT LANDED.**  The
landing §3 specifies — the arm becomes *"the EU's interrupt-entry microcode
started"*, published by the EU and consumed by the BIU, one wire, no address
match, strictly generalising today's arm — is carried to the next sitting with
its bar rewritten on w0 and on minima, and with §3's full must-not-move ladder
unchanged.  **No engine source was touched and no ratchet moved.**

### §68.5 CELL (b) — **H7: THE OPCODE AT THE BOUNDARY DOES NOT SELECT THE FLOOR.  §65.1's LEAD IS REFUTED FROM TWO SIDES.**

**THE BOARD-FREE CENSUS THAT CHOSE THE OPCODES** (`sw/sm3_h7_opcode.py`, a
MEASUREMENT tool, never a gate; chip-side, no engine, the opcode read off the
`QS` port with a single address pointer): 208 banked NMI seeds, **193 with a
recognition, 0 unplaced pops**.

* the `gap = V − A` histogram reproduces §63.2 exactly — **12 : 30, 13 : 18**;
* **no opcode partitions the two camps** — `B9`, `CF`, `EA`, `E9` appear at
  both;
* **`90` (NOP) sits at gap 12 on FOUR banked seeds.**  Hand-verified on
  `mc1/raw_3571`: the image is a solid `90` sled, `A = 316`, `V = 328`.  §65.1's
  own directed NOP-sled cell floors at **13** over 40 captures and the golden
  `NMI.90` is A-limited at 13.  **Same opcode, same sled, two floors.**
* a coordinate the lead did not predict: the floor population is
  **BANK-ASSOCIATED** — `mc2` **0 of 75** at gap 12, `mc1` **26 of 85**,
  `t30-raw` **4 of 33**.  `gen_git` tracks the bank exactly and `banked_ts` is
  the same day for all 193, so it is a property of the two GENERATORS' programs
  and not of a capture era.  **Booked, not chased.**

**THE BOARD CELL**: `sm3_h7_cell.py` with §63.3's geometry unchanged (assert
delay swept one clock at a time, `hold = 2`, waits 0-3, `d0 = 6`, 16 delays)
and the STIMULUS as the only new axis — ten one-instruction sleds.
**640 captures**, 1,282 files with `SHA256SUMS` in `sw/testdata/sm3-h7opcell/`,
62.5 s, 0 errors.

| | result |
|---|---|
| the floor `min(V − A)`, **every one of the 10 variants × 4 wait levels** | **13, all 40 cells** |
| **Q1 falsifier**, cells with `V − A < 12` | **0** — the floor holds |
| the engine leg, `ucore` and `sim`, on the SAME 640 captures | **13 on all 40 cells, both engines, delta +0 everywhere** |

**O2 AT ITS POINT ESTIMATE.**  Ten opcodes — including both golden NMI forms'
own opcodes, a Jcc not taken and the same Jcc taken (a redirect at every
instruction) — and the floor does not move by one clock.  **§65.1's lead is
REFUTED**, from the bank (a gap-12 NOP) and from the board (a gap-13 NOP), and
**H7 stays BLOCKED with the opcode axis added to the eliminated list**
(wait class, rig delay, bus owner at A, queue occupancy at A, queue primed vs
dry, the window's composition, and now the instruction at the boundary).
The bank association of §68.5's census is the only live lead it leaves.

### §68.6 CELL (c) — **H3 CLASS B: THE WAIT-VECTOR WALK RAN, AND S3 FIRED**

`sm3_h3_cell.py wrun`, §65.2's own spec taken: a PERIODIC, phase-swept
per-access wait vector that puts `+extra` waits on the access `r` bus cycles
before every EU access, with `period` MEASURED off a uniform-waits baseline in
the same cell.  3 variants × 4 waits × (baseline + 2 extras × `period` phases).
**186 captures, 7,254 EU accesses**, 374 files with `SHA256SUMS` in
`sw/testdata/sm3-h3wvec/`, 20.6 s, 0 errors.

**THE RIG COULD EXPRESS IT** — `cfg_wait_replay` + `wvec_buf` in
`hdl/rtl/nec_bus.sv`, `v30run.Runner.replay()` on the host — and the only
missing piece was `s10_board.capture()`'s passthrough, added here.

| bar | registered | **measured** |
|---|---|---|
| **R0** the chip's ACHIEVED per-cycle waits vs the vector it was handed | `>= 95 %` | **45,699 / 45,699 = 100.0 %** |
| **S1** distinct lead-in `gap` values per (variant, wait) | `>= 3` | **3 to 5 in all 12 cells** (§65.2's byte-step sweep gave 2-3) |
| **S2** same-clock / different-owner pairs | `>= 1` would reach the family | **0 against `sim`, 0 against `ucore`** |
| agreement, paired by ordinal | — | **7,254 / 7,254 against BOTH engines** |

**S3 — THE REGISTERED NEGATIVE — FIRES.**  R0 met, S1 met, S2 zero over 7,254
paired accesses against a `>= 3,000` bar.  **Class B is not reachable by a
clock-resolution walk of the prefetcher's eligibility instant either**, which
is the second stimulus §63.6 named and the second one to miss.  Both engines
reproduce the chip's grant order EXACTLY at every occupancy from 2 to 5, at
every wait level, with a one-clock-resolution phase sweep — that is a stronger
control than §65.2's and it says the same thing.  **Nothing landed.**

**AND R0 IS A RESULT IN ITS OWN RIGHT.**  100.0 % over 45,699 bus cycles is the
first DIRECT, per-cycle proof on this bitstream that the harness's `wvec_buf`
index and the engines' bus-cycle ordinal are the same index.
`timed_wvec_gate`'s 88/88 was evidence about a frozen corpus's digests; this is
the vector, cycle by cycle, on 186 fresh captures.

**WHERE CLASS B IS NOT**: not at a queue-occupancy threshold (§63.6), not in a
byte-step sweep of the request instant (§65.2), and not in a clock-step sweep
of the eligibility instant (here).  All three stimuli share one property — the
access is reached through an `EB 00` flush and a cold refill.  **The spec that
follows, NOT taken**: drive the access from a prefetcher in STEADY STATE, never
flushed, which is §65.2's own second suggestion and the only one of its two not
yet tried.

### §68.7 WHAT MOVED, AND WHAT DID NOT

| | before | **after** |
|---|---|---|
| the board's bitstream | FLASH #4 `67ddd59413d5…` | **FLASH #5 `315de4bc9e30…`** |
| the fabric HLT sweeps | 143 / 283 | **146 / 283** (and the failing SET is now identical to `tb_sys` base's) |
| the fabric F43 signature | 6 cells | **0** |
| `sig_ledger.json` `sigs` | 11,845 | **11,848** (§68.8) |
| `check_fuzz_bank --strict` | FAIL | **rc 0** (§68.8) |
| **everything in `standing_gates.md` §B** | — | **UNMOVED, and `git diff 2e93cd0499 -- hdl/rtl hdl/tb sim/` is EMPTY** |

### §68.8 THE STRICT ADMISSION — **THE CONTROL HOLDS, AND IT IS A NEW CONTROL RATHER THAN A WEAKER ONE**

§67.9 routed the decision; the coordinator's decision was ADMIT WITH CONTROL.

**THE CONTROL, run FIRST and pre-registered in §6.**  New tool
**`sw/sm3_iowpop.py`** derives §66.3's `IOW` population from the CAPTURES
ALONE — no engine, no testbench, because the defect WAS a replay instrument and
a population defined by it would be circular.  Over the full 3,242-seed bank:
**47 seeds** whose chip rows contain an `IOW` whose port number is later read as
memory (§66.3's 37 was over the 2,710 SCORED seeds; all seven seeds §66.3 names
cross-check as members).

`sw/sm3_sigctl.py --jobs 6` over the whole bank against the live ledger:
`new-sig TIMING seeds: 3, distinct signatures: 3, errors 0, gen-drift 0` —
**`mc1/1937`, `mc1/3325`, `t30-raw/123`**.

| registered control | **measured** |
|---|---|
| all **5** improved seeds in the `IOW` population | **5 / 5** (`mc1/412`, `mc1/1937`, `mc1/3325`, `mc1/3741`, `t30-raw/123`) |
| all **3** new-signature seeds in it | **3 / 3** |
| any improved or new-signature seed OUTSIDE it | **0** |

**THE ADMISSION.**  `sm3_sig_admit.py`'s existing control is INV-1's and is
hard-wired to a `recapture` block with `evt.hold == 300` / `hold_bits == 12`.
These three signatures fail that control **correctly** — they are not INV-1
consequences.  The right response to a new cause is a NEW CONTROL, not a weaker
one, so the tool gained `--cause {inv1,iow}`: `inv1` is unchanged to the line,
and `iow` gates on membership of `sm3_iowpop`'s population, with its own `why`
naming §66.3's testbench fix and its own `waits_class` (`tb-iow-fix`).  The two
controls are computed by two different tools over two different artifacts, so
neither can be quietly substituted for the other.


**THE GATE, BEFORE AND AFTER:**

```
  before (rebuilt FSM TB, live ledger 11,845):
    IMPROVED mc1/1937 : FUNCTIONAL -> TIMING       IMPROVED mc1/412  : TIMING -> KNOWN_ACCEPTED
    IMPROVED mc1/3325 : FUNCTIONAL -> TIMING       IMPROVED t30-raw/123 : FUNCTIONAL -> TIMING
    IMPROVED mc1/3741 : FUNCTIONAL -> TIMING
    check_fuzz_bank: FAIL | 3242 banked seeds | stable 3237 improved 5 worse 0
                   | gen_drift 0 regen_err 0 | float-floor 0
                   | new-sig TIMING 3 (strict-fail)          rc = 1

  admitted: 3 signatures over 3 seeds, sigs 11,845 -> 11,848,
            0 pre-existing entries touched
            b98079550c897a09  bb7f08a4adb12327  cea29561559cf048

  after (same tree, same TB, ledger 11,848):
    check_fuzz_bank: PASS | 3242 banked seeds | stable 3237 improved 5 worse 0
                   | gen_drift 0 regen_err 0 | float-floor 0
                   | new-sig TIMING 0                        rc = 0
```

`worse` is **0** and `gen_drift` is **0** on both sides of the admission, which
is the property that makes admitting legitimate at all: nothing regressed, five
seeds replay to a BETTER verdict, and a better verdict carries a signature the
novelty register has never seen.

### §68.9 WHAT THIS SITTING DID NOT DO

* **No engine was changed.**  `git diff 2e93cd0499 -- hdl/rtl hdl/tb sim/` is
  EMPTY.  H1a's landing was AUTHORISED BY THE EVIDENCE AND NOT BY THE BAR, and
  the bar is what governs (§68.4).
* **The 8080 / `gaps` §F.1 work was not opened** — a pending USER decision.
* **The X1 OE-port work was not opened** — a pending USER decision, and C11's
  `NOT ESTABLISHED` is unchanged.
* **No memory file was touched and Codex was not launched.**
* **The `u4_f42_fabric` leg-naming debt and the `x1_retention` build debt
  (§67.6, §67.7) were routed, not taken.**

### §68.10 THE LEADS THIS SITTING HANDS THE NEXT ONE

1. **H1a's landing, with the bar rewritten.**  The mechanism is §3's: the arm
   becomes *"the EU's interrupt-entry microcode started"*, published by the EU
   and consumed by the BIU — one wire, no address match, strictly generalising
   today's INTA-only arm.  The bar must be written on **w0 alone** (the only
   regime where the two candidates differ by two clocks) and on the **MINIMUM**
   `refill_gap`, not on a proportion at all four wait levels.  The evidence is
   banked: `sw/testdata/sm3-h1acell/`, 240 captures, and the chip-vs-engine
   split is 0/30 against 30/30 with a 100 %-clean shape control.
2. **H7's only surviving lead is the BANK ASSOCIATION** (`mc2` 0/75 at the
   floor, `mc1` 26/85, `t30-raw` 4/33, with `gen_git` tracking the bank and
   `banked_ts` identical).  It is a property of the two GENERATORS' programs
   and it is board-free to chase: what does `mc2`'s generator never emit?
3. **H3 class B: the steady-state prefetcher.**  All three stimuli that have
   missed reach the access through an `EB 00` flush and a cold refill.
   §65.2's own second suggestion — *"drive the access from a queue that is NOT
   refilling after a flush"* — is the only untried one.
4. **The `u4_f42_fabric` `--leg` debt**, so the next re-flash does not
   overwrite the previous bitstream's fabric record.

## §69 SESSION SM3, SITTING 8 — THE `AD_OE` PORT, AND THE X1 FABRIC LEG **NOT TAKEN**

**2026-08-04, branch `ucsim`, from HEAD `3047c2158d`.  Task #37.  A BOARD
SITTING WITH FLASHING AUTHORISED — AND NO FLASH WAS TAKEN.**  Pre-registration
committed at **`8133c13382`** BEFORE the first board contact:
`docs/notes/sm3_s8_prereg_2026-08-04.md`.  Single writer confirmed before
contact (`0 users`, no serve process on `mister-nec`); `div_guard` **PINNED**;
`use_core` **False** as found and **False** as left, verified on the board;
`board_idle()` run at the end and clean; **0 transport errors in the whole
sitting**; `sw/testdata/flash_log.jsonl` is **unchanged at 8 entries**.

> **Standing principle, applied throughout.**  *"This is 80's era hardware,
> they aren't wasting silicon on anything that isn't necessary.  Complex or
> confusing behavior that we see is likely to be simple systems interacting in
> ways you do not fully understand yet."*

**THE ONE-LINE RESULT.**  §59.7.1's blocker is **REMOVED** — the retention
model now synthesises, and it is measured doing so.  It is replaced by a
different and much more specific one: **the retention build MISSES the
registered Fmax bar by 12 MHz**, so no bitstream was flashed, the fabric leg
was not run, and **C11's `NOT ESTABLISHED` stands.**

### §69.1 THE CHANGE — ONE OUTPUT PORT ON EACH CORE

The user's decision, verbatim: ***"Okay, add the output enable."***

```
    output [19:0] AD_OE
    assign AD_OE = {{4{ad_oe_addr | ad_oe_ps}}, {16{ad_oe_addr | ad_oe_data}}};
```

The right-hand side is character-for-character the enable term the two
`assign AD[...]` statements already used.  It is published, not computed.  The
ARCHIVED FSM core gets the same one port and the same one wire — the A/B
discipline requires the two bitstreams to differ by the CORE alone — recorded
as a user-authorised exception in `fsm_core_archive_2026-08-04.md` **§6a**.

`system_large.sv`'s `X1_AD_RETENTION` model is re-keyed onto it:

```
    wire [19:0] core_ad_drv = core_ad_oe | {4'b0, {16{c_addrv_q}}};
```

and the `=== 1'bz` construct is GONE.  §56.3a's prohibition was on the HARNESS
manufacturing an OE; the core stating its own is not that, which is the whole
content of the user's decision.  The OBSERVATION-PATH deviation is unchanged
and its rationale stays written beside the code.

### §69.2 THE OFFLINE EQUIVALENCE PROOF — **EXACT, TO THE CLOCK**

| leg | §67.7 (`=== 1'bz`) | **this tree (`AD_OE`)** |
|---|---|---|
| `tb_sys` base | 146 / 283 | **146 / 283** |
| `tb_sys` ret | 265 / 283 | **265 / 283** |
| `offline` (`tb_v30_core`) | 265 / 283 | **265 / 283** |
| base-only failures, all INTA | 119 of 119 | **119 of 119** |
| BAR (i) | MET | **119 closed, 0 survived, 265 == 265 — MET** |
| BAR (ii) | MET | **0 cells differing from offline — MET** |

And not merely in total: **the 283 `ret` capture records are BYTE-IDENTICAL to
HEAD's, 283/283, and so are the 283 `base` records.**  The re-key is equivalent
in every retained clock, not just in the score.

The rest of the ladder, all re-run on this tree: `check_core` **ucore
169,000/169,000**, **fsm 168,400/169,000**; `ulockstep --golden all --cases 50`
**17,350/17,350**; `check_ab_sim` **MATCH 187** on both cores; `check_boot
--timed 220`/`400` **MATCH**; `ss_lint` **rc 0** on both (222/205 flops ucore,
203/181 fsm — an output port is not a flop); `gen_ucore_qsf --check` green.
**The port is dead weight offline, as registered.**

Both `tb_sys` legs were REBUILT: §67.6/§67.7's routed rig debt is **TAKEN** —
`x1_retention.py` has a `build()` with a real dependency set and `capture`
calls it.  §68.2's `--leg` debt on `u4_f42_fabric` is **TAKEN** as well
(default `core`, so every past invocation still means what it meant; FLASH #5's
record duplicated to `*.core_f5.json.gz`, verified reproducing 146/283, and
`--leg core_f4` verified reproducing FLASH #4's 143/283).

### §69.3 THE LIVENESS BAR — **MET.  §59.7.1's BLOCKER IS GONE.**

§4 of the pre-registration wrote the bar as *"the retention registers named and
counted in the fit report of the retention build, or NO flash."*  **The bar's
LETTER is not measurable on this report and that is said plainly**: a control
run first shows `nec_test_ucore.fit.rpt` does not name ordinary internal
registers at all — `c_ready_q`, `c_addrv_q`, `hb_ad_dir`, `core_ad_eff`,
`bus_tick_rise` are **0 occurrences each in FLASH #5's own fit report**.  A
grep for a register name is a weak instrument, which is why §59.7.1 did not
rest on it either.  The bar's SUBSTANCE — named and counted — is measured two
ways, and both are decisive:

| test | result |
|---|---|
| **`system_large`'s OWN dedicated logic registers, `Fitter Resource Utilization by Entity`** | **27 → 47.  Exactly +20**, the model's own count, in the entity that declares it |
| A&S `Total registers`, whole design | 4,797 → **4,817.  Exactly +20** |
| **§59.7.1's ISOLATED CONSTRUCT, both forms, compiled alone** (`~/.cache/ucsimt-tmp/s8/ztest/`) | the `=== 1'bz` form: `Warning (15610): No output dependent on input pin "clk"`, **Total registers 0** — §59.7.1 reproduced exactly.  The `AD_OE` form: no such warning, 40 logic cells against 17, **Total registers 20** |
| `core_ad_hold` in `Registers Removed During Synthesis` | **absent** (and that table does name `system_large`-level registers — `nec_bus:bus|cap_record[59..63]`, `v30_core:u_core|ss_addr_q[0..8]` are in it) |

**0 registers versus 20, on the identical construct, keyed on the net versus
keyed on the port.**  That is the whole of what the user's decision bought, and
it is bought.

### §69.4 THE QUARTUS BARS — **Fmax MISSED BY 12 MHz.  REPORTED AS REGISTERED.**

`gen_ucore_qsf --check` green first, then
`quartus_map --verilog_macro="X1_AD_RETENTION=1"` + `fit` + `asm` + `sta`.

| bar | registered | **measured** |
|---|---|---|
| errors, A&S / Fitter / Assembler / TimeQuest | 0 | **0 / 0 / 0 / 0** |
| latches as a RESOURCE | 0 | **0** (the 23 `Warning (10240)` lines are the pre-existing `v30u_eu.sv` block-local temporaries) |
| `lpm_divide` | 0 | **0** |
| ALMs | — | 11,279 / 41,910 (27 %), 6,139 registers |
| **Fmax, `emu\|pll\|…\|divclk`** | **>= 32 MHz** | **20.25 MHz — MISSED** |
| **worst setup slack** | **> 0** | **−18.132 ns — MISSED** |
| **TNS, setup, `divclk`** | **0.000** | **−11,049.741 — MISSED** |

Hold is clean on every domain (worst +0.255, TNS 0.000).  **The setup bars are
missed and they are reported as missed, not restated.**

### §69.5 THE CONTROL THAT SAYS WHOSE THE MISS IS — **NOT THE PORT'S**

A miss on a registered bar names a cost; it does not name a cause.  So the
**same tree** was rebuilt with `quartus_sh --flow compile` and the macro OFF —
one variable, the `ifdef`:

| | FLASH #5 (§68.1) | **control: this tree, retention OFF** | **retention ON** |
|---|---|---|---|
| ALMs | 11,167 (27 %) | **11,167 (27 %)** | 11,279 (27 %) |
| fitter registers | 6,087 | **6,087** | 6,139 |
| A&S registers | — | 4,797 | **4,817 (= +20)** |
| Fmax `divclk` | 45.67 MHz | **45.67 MHz** | **20.25 MHz** |
| worst setup | +9.355 ns | **+9.355 ns** | −18.132 ns |
| TNS `divclk` | 0.000 | **0.000** | −11,049.741 |
| the SDC's v30u multicycle collection, at STA | 2,220 | **2,220** | **2,139** |

**THE `AD_OE` PORT COSTS NOTHING — the control reproduces FLASH #5's numbers to
the ALM, to the register and to 0.01 MHz.**  The whole of the miss is the
retention model, and it is 20 flops.

### §69.6 WHY 20 FLOPS COST 25 MHz — **A NAME-SCOPED TIMING EXCEPTION, AND IT
IS A FINDING ABOUT THE SIGN-OFF, NOT ABOUT THE MODEL**

> **ERRATUM, entered 2026-08-04 by SM3 sitting 9 — READ §70 BEFORE USING THIS
> SUBSECTION.**  The paragraph below beginning *"And the SDC's exception
> collection moves with it: **2,220 → 2,139, 81 fewer**"* is **WRONG, and with
> it R7's whole premise.**  The two numbers are read at DIFFERENT STAGES of the
> flow: 2,220 is the control's POST-FIT figure and 2,139 is the retention
> build's MID-FITTER figure.  Compared stage for stage the collection **GREW**
> — 2,075 → 2,139 mid-fitter and 2,220 → **2,251** post-fit.  The exception is
> not under-applying; nothing escaped it; **no register left the collection.**
> The rest of this subsection — the worst path, the control's absence of it,
> the fitter being where the difference is made — reproduces exactly and
> stands.  The text is left as written, with this marker, because a ledger that
> deletes its own errors is not a ledger.  §70 has the measurement.

Synthesis is IDENTICAL between the two builds apart from the model itself
(4,797 → 4,817 registers, exactly +20).  Everything else happens in the FITTER.

The retention build's worst path, all five of its worst five:

```
  From : emu|system_large|c_ready_q
  To   : emu|system_large|v30_core:u_core|v30u_eu:u_eu|wb_kind[1]
  Relationship 31.250   Data Delay 48.720   Skew −0.532   Slack −18.132
```

**In the control that path DOES NOT EXIST.**  Measured, not inferred:
`report_timing -from c_ready_q -to wb_kind` on the control netlist returns
**no paths**, with both collections non-empty (1 and 3).  The control's worst
paths into `wb_kind` launch from `cfg_use_core` / `cfg_clk_div` at **8.3 ns,
slack +22.2**, and its worst core path overall is
`v30u_eu|upc_opc[3]~DUPLICATE → nec_bus|qs_q[1]` at 21.68 ns, slack +9.355.

And the SDC's exception collection moves with it: **2,220 → 2,139, 81 fewer.**
`nec_test.sdc` collects the CE multicycle **BY NAME** —
`get_registers {*|v30u_eu:*|*}` and `{*|v30u_biu:*|*}` — and the fitter's
physical synthesis DUPLICATES registers across the core boundary.  A duplicate
that lands inside the `v30u_*` name scope is inside the exception; the same
register duplicated at the parent level is outside it, single-cycle, and 4×
over-constrained.

**So FLASH #5's timing sign-off depends on where the fitter happened to name
its duplicates.**  Perturb the design by 20 flops on a capture path and the
duplication changes, 81 registers leave the exception, and a genuinely
CE-gated path is scored against one sys clock instead of four.  The SDC's own
falsifier is written for the opposite failure (*"a `v30u_eu` or `v30u_biu`
state register with no clock-enable input"* — the exception lying by
over-applying); **this is the exception failing by UNDER-applying, which no
falsifier in the file covers and which no gate would have shown.**

**IT IS BOOKED AND NOT FIXED HERE, DELIBERATELY.**  Widening the collection
after seeing a timing result is choosing a timing exception to make a bar pass
— the same manoeuvre as choosing a comparator after seeing a score.  The fix,
routed: collect the CE-gated registers **structurally** (registers whose `ena`
port is driven by the core's clock-enable) rather than by hierarchical name,
and re-sign-off BOTH revisions against it, with the before/after on both cores
that any change to a shared harness needs.

### §69.7 THE DISPOSITIONS, TAKEN AS §8 WROTE THEM

* **NO FLASH.**  A registered bar was missed and the design's own sys clock is
  32 MHz, which the retention build cannot make.  A fabric number taken off a
  bitstream that fails setup by 18 ns is not a measurement of anything, and
  §59.7.1 exists because *"119 survive"* is easier to write than to retract.
  **`flash_log.jsonl` is unchanged at 8 entries.**
* **THE FABRIC LEG WAS NOT RUN.**  Not attempted, not partially scored, not
  quoted.
* **C11's `NOT ESTABLISHED` STANDS**, and the reason it stands has changed:
  it is no longer *"the model cannot be synthesised"* (§59.7.1 — that is
  CLOSED) but *"the model synthesises and does not close timing"*.
* **THE BOARD IS UNTOUCHED AND STILL CARRIES FLASH #5.**  The resting-bitstream
  decision is therefore not a decision: nothing was flashed, so nothing is
  restored.  `sw/check_ab_hw.py chip 800` on it: **chip-vs-golden MATCH over
  800 rows**, `div_guard` **PINNED**, `use_core` **False**, `board_idle()`
  clean, `cfg = 0xff0008` (`clk_div` 8, `DIV_OF_RECORD`).

### §69.8 WHAT MOVED, AND WHAT DID NOT

| | before | **after** |
|---|---|---|
| `hdl/rtl/*/v30_core.sv` port list | no `AD_OE` | **`output [19:0] AD_OE`, both cores** |
| `system_large.sv`'s retention key | `core_ad === 1'bz` (unsynthesisable) | **`core_ad_oe`, and it synthesises: +20 registers, measured** |
| §59.7.1's blocker | OPEN | **CLOSED** |
| the X1 fabric leg | BLOCKED (cannot build) | **BLOCKED (builds, misses Fmax)** |
| C11 | NOT ESTABLISHED | **NOT ESTABLISHED** |
| the board's bitstream | FLASH #5 `315de4bc9e30…` | **FLASH #5 `315de4bc9e30…`, untouched** |
| `x1_retention.py` | no build recipe anywhere in the tree | **`build()` + dependency check; `capture` calls it** |
| `u4_f42_fabric.py` | one fixed filename, overwrites on re-capture | **`--leg`, default `core`** |
| **everything in `standing_gates.md` §B** | — | **UNMOVED, and re-measured rather than inherited** |

### §69.9 WHAT THIS SITTING DID NOT DO

* **No flash, no fabric capture, no golden re-emitted.**
* **H1a's landing was not opened** (§68.10 lead 1) — still queued.
* **The 8080 / `gaps` §F.1 work was not opened** — a pending USER decision.
* **No memory file was touched and Codex was not launched.**
* **`nec_test.sdc` was NOT edited** (§69.6).
* **`timed_lawcards`' `C11` was NOT touched, and it is a DIFFERENT C11** —
  that one is the BIU law card *"LC4 `owns_slot` (enumerated)"* and it remains
  `UNRESOLVED` on its own grounds.  The C11 this sitting is about is the
  **Codex review item** in `ucore_campaign_verdict_2026-08-04.md` §(g), *"the
  INTA classification: NOT ESTABLISHED"*.  The two share a label and nothing
  else; conflating them would close a card no evidence here touches.

### §69.10 THE LEADS THIS SITTING HANDS THE NEXT ONE

1. **THE SDC's NAME-SCOPED CE EXCEPTION (§69.6)** — now the only thing between
   the retention model and a fabric answer, and a fragility in *every* bitstream
   this project has signed off.  Board-free, and it has a control ready-made:
   the same tree builds at 45.67 MHz with the macro off and 20.25 MHz with it
   on, so any structural collection can be scored on both.
2. **Then the X1 fabric leg**, unchanged: §56.3a's two halves, the population
   restated at **119** and **265** in the pre-registration's §6, the 18
   survivors named cell by cell in its §7, and the socket control at 49/49.
3. **H1a's landing** with the bar rewritten on w0 and on minima (§68.10 lead 1).
4. **H7's bank association** and **H3's steady-state prefetcher** (§68.10
   leads 2 and 3), both board-free to open.

## §70 SESSION SM3, SITTING 9 — **R7 IS REFUTED.  NOTHING ESCAPED THE EXCEPTION, AND THE SDC IS NOT EDITED**

**2026-08-04, branch `ucsim`, from HEAD `7de3a347ae`.  Task #37.  A BOARD
SITTING WITH FLASHING AUTHORISED — AND NO BOARD WAS TOUCHED, because the
offline item it was contingent on did not survive its own first measurement.**

> **Standing principle, applied throughout.**  *"A guiding principal here needs
> to be simplicity.  This is 80's era hardware, they aren't wasting silicon on
> anything that isn't necessary.  Complex or confusing behavior that we see is
> likely to be simple systems interacting in ways you do not fully understand
> yet."*

**THE ONE-LINE RESULT.**  The sitting was commissioned to make the CE multicycle
collection STRUCTURAL because §69.6 measured 81 registers escaping the
hierarchical name scope.  **They did not escape.  The collection GREW.**  The
"81 fewer" is a stage-mismatch inside a single Quartus log, and once it is read
stage for stage the retention build's collection is 64 LARGER mid-fitter and 31
LARGER post-fit.  **`nec_test.sdc` is therefore NOT edited**, no structural
collection is shipped, no bitstream was built for flashing, and **C11's `NOT
ESTABLISHED` stands** — for a third and again different reason.

### §70.1 THE REPRODUCTION — the retention build is deterministic

`gen_ucore_qsf --check` green first, then `quartus_map --verilog_macro=
X1_AD_RETENTION=1` + `fit` + `sta` from HEAD, unchanged SDC.  Against §69.4:

| | §69.4 | **this sitting** |
|---|---|---|
| ALMs | 11,279 (27 %) | **11,279 (27 %)** |
| fitter registers | 6,139 | **6,139** |
| worst setup, `divclk` | −18.132 ns | **−18.132 ns** |
| TNS, setup, `divclk` | −11,049.741 | **−11,049.741** |

Every number reproduces to the digit.  Nothing in what follows is a different
build; it is the same build, interrogated.

### §70.2 **R7's PREMISE, REFUTED — READ THE COLLECTION SIZE AT ONE STAGE**

The SDC prints its own collection size every time Quartus reads it, and Quartus
reads it EIGHT times per flow.  §69.6 compared the control's LAST print with the
retention build's FIFTH.  Aligned by flow position — the `Info` lines are in the
same order in both logs, at the same `Info (170189)/(170191)/(11801)` stage
boundaries:

| flow stage | control (macro OFF) | retention (macro ON) |
|---|---|---|
| fitter start (×3) | 1,081 | **1,081** |
| fitter preparation end | 2,075 | **2,139** |
| placement preparation | 2,075 | **2,139** |
| after placement | 2,075 | **2,139** |
| **post-fit (`fit.rpt`)** | **2,220** | **2,251** |
| **STA (`sta.rpt`)** | **2,220** | **2,251** |

**+64 mid-fitter, +31 post-fit.  The exception did not under-apply, no register
left the collection, and the mechanism §69.6 named — "a duplicate that lands at
the parent level is outside the name scope" — did not happen in this build.**
Corroborating: the pre-fitter figure is **1,081 in both**, i.e. the netlist the
fitter starts from is the same one, as A&S said (4,797 → 4,817 registers, the
model's +20 and nothing else).

### §70.3 WHAT ACTUALLY FAILS — **ONE LAUNCH REGISTER, AND IT IS NOT CE-GATED**

`get_timing_paths -setup -less_than_slack 0` on the retention netlist, first
20,000 paths:

* **launch register: `emu|system_large|c_ready_q` on 20,000 of 20,000.**
* **capture: inside `v30u_eu` on 20,000 of 20,000.**
* worst ten: −18.132 … −18.086 ns, **55–56 logic levels**, all to
  `v30u_eu|wb_kind[1]`.

And `c_ready_q` is, in full (`system_large.sv:363`):

```
always_ff @(posedge clk) begin
    c_ready_q <= hb_ready;      // no enable, no ce, every sys clock
```

**No collection of CE-gated registers — name-scoped, structural, generated or
hand-written — can contain it**, and §52 registered exactly that in advance:
*"Paths that CROSS the boundary … are NOT excepted and stay single-cycle, which
is correct: their launch registers are not CE-gated."*  **The fix R7 asks for
cannot move this path.**  That is the whole reason the SDC is left alone: not
discipline about widening after seeing a result — though that rule holds too —
but that the widening is measurably powerless.

The retention model's OWN paths are not the problem either, measured on the same
netlist: worst path INTO `core_ad_hold[*]` is **+4.818 ns** (from
`v30u_eu|upc_opc[2]`, 20 levels), worst path OUT of it **+29.583 ns** (to
`nec_bus|ad_in_q[10]`, 1 level).

### §70.4 THE CONTROL, SAME QUERIES — and §69.6's live half

On the macro-OFF netlist (FLASH #5's, 2,220 / 45.67 MHz / +9.355, restored from
`~/.cache/ucsimt-tmp/sm3s9/ctrl_flash5/`):

| query | control | retention |
|---|---|---|
| `-from c_ready_q -to *wb_kind*` | **0 paths** | −18.132, 55–56 levels |
| worst `-from c_ready_q` | +11.540, **20 levels**, → `v30u_eu|row_posted` and `v30u_eu|row_slot_wait~0_OTERM2375` | −18.132, 56 levels |
| worst core path overall | `v30u_eu|upc_opc[3]~DUPLICATE → nec_bus|qs_q[1]`, 19 levels, **+9.355** | — |

§69.6's *"in the control that path does not exist"* is **CONFIRMED**, and
`row_posted`'s `d`-pin fanin does contain `c_ready_q` while `wb_kind[1]`'s does
not, so the READY cone reaches the EU in the control too — it is 20 levels deep
there and 56 deep in the retention build.  Synthesis is the same netlist
(§70.2), so **the whole of the difference is made inside the fitter**:
`Retimed Register` rows in `fit.rpt` go 2,041 → **2,263** and `Duplicated`
304 → **272**.  WHY physical synthesis restructured that one cone differently is
**NOT established here** and is not guessed at.

### §70.5 THE FRAGILITY IS REAL — IT IS JUST NOT IN THE SDC

Restated as measured, and it is simpler than R7 was: **`READY` reaches the EU's
next-state logic through a 55–56 level SINGLE-CYCLE combinational cone, and the
signed-off build meets timing on it only because the fitter's physical synthesis
happens to break that cone.**  Perturb the design and the fitter may not.  No
gate in the tree sees this, which is the one thing R7 got right.

**THE LEAD, NAMED AND NOT TAKEN.**  `hb_ready` is `nec_bus`'s `NEC_READY`
output, and that is `ready_pin`, which updates only `if (tick_fall)`
(`nec_bus.sv:541`).  So `c_ready_q` changes only on the sys clock AFTER
`tick_fall`, and the core samples it at `tick_rise`, `cfg_clk_div/2` sys clocks
later.  A multicycle on the harness→core input pipe is therefore arguable — but
only if the divider is pinned, and **at the documented minimum `cfg_clk_div = 4`
the margin is exactly ONE clock**, so at the minimum divider it buys nothing.
It is a design decision (pin the divider, or CE-gate the input pipe, or shorten
the cone) that needs its own pre-registration, its own falsifier and its own
before/after on BOTH revisions.  **Choosing it now, after a failed bar, is the
manoeuvre CLAUDE.md forbids by name.**  Handed on.

### §70.6 A SECOND, SMALLER FINDING — **THE SDC's OWN FALSIFIER HAS NEVER BEEN RUN, AND IT NEEDS AN INSTRUMENT**

`nec_test.sdc` has carried, since §52, the falsifier *"a `v30u_eu` or
`v30u_biu` state register with no clock-enable input"*.  It has never been
checked mechanically.  Attempted here on the control netlist and **NOT
COMPLETED — reported as an instrument gap, not as a result**:

* of the 2,220 collected registers, **1,014** expose an `ena` pin and **1,719** a
  `d` pin under `get_pins`; **1,291** expose neither, because a Cyclone V ALM
  register can take its data through `asdata`/`sload` and its enable as a data
  feedback mux instead of the `ena` port.  A checker must handle all those forms
  or it reports absence of evidence as evidence.
* of the **929** that could be classified, **915** show CE evidence (`div_cnt`
  in the `ena` fanin, or self-feedback on `d`) and **14** do not — all 14 are
  `~DUPLICATE` nodes.  **This is not a finding in either direction.**
* incidentally: **1,295 of the retention build's 2,251 collected names are
  physical-synthesis artefacts** (`_OTERM…`, `~DUPLICATE`).  Reasoning about
  that collection by name is fragile on its face — it simply did not fail in the
  direction R7 predicted.

`get_fanouts <src> -no_logic -through [get_pins *|ena]`, the recipe TimeQuest's
own `help get_fanouts` gives for this, returns an EMPTY collection on this
netlist and is recorded here as tried and non-working in 17.1 Lite.

### §70.7 THE DISPOSITIONS

* **`nec_test.sdc` is NOT EDITED.**  No structural collection, no generated
  register list, no widening.  §70.3 is the reason and it is a measurement.
* **NO BUILD WAS MADE FOR FLASHING and NO BOARD WAS TOUCHED.**  Zero board
  contact in the sitting: no single-writer probe, no `div_guard`, no capture,
  no `board_idle` — there was nothing to idle.  `sw/testdata/flash_log.jsonl`
  is **unchanged at 8 entries**.  The board still carries **FLASH #5**.
* **THE X1 / §56.3a FABRIC LEG WAS NOT RUN.**  Not attempted, not partially
  scored, not quoted.  Its blocker is unchanged from §69: the retention build
  misses Fmax.  What changed is that the ROUTE OUT of that blocker named in
  §69.10 lead 1 is now known not to lead anywhere.
* **C11 `NOT ESTABLISHED` STANDS.**
* **R7 IS REFUTED AND RECLASSIFIED**, in `ucore_gaps_2026-08-04.md` and
  `standing_gates.md`, to what §70.5 measures.
* **EVERY STANDING GATE IS UNMOVED** — no RTL, no tool and no golden was
  touched this sitting, so none was re-run and none is re-quoted.  The only
  tracked file changed besides the notes is `hdl/nec_test_ucore.qsf`,
  regenerated after Quartus materialised its sourced assignments into it
  (`gen_ucore_qsf --check` green), which is the documented behaviour.

### §70.8 EVIDENCE

`docs/notes/sm3_s9_r7/` — the three TimeQuest probes and their outputs on both
netlists.  Both netlists preserved whole under
`~/.cache/ucsimt-tmp/sm3s9/{ctrl_flash5,ret_oldsdc}/` (db + incremental_db +
reports), so every number above is re-queryable without a rebuild.

### §70.9 THE LEADS THIS SITTING HANDS THE NEXT ONE

1. **§70.5's READY cone** — the real fragility, board-free, with both netlists
   preserved and a control ready-made.  It is an RTL/harness question, not an
   SDC one, and it needs a pre-registration before any timing run.
2. **§70.6's falsifier instrument** — small, board-free, and it would be the
   first mechanical check of a claim the SDC has asserted since §52.
3. **Then the X1 fabric leg**, unchanged and still blocked (§69.10 lead 2).
4. **H1a's landing**, **H7's bank association**, **H3's steady-state
   prefetcher** — all still queued (§68.10).

## §71 SESSION SM3, SITTING 10 — **THE H1a LANDING WAS BUILT, IT IS PERFECT ON THE CELL, AND THE DISJOINT BANK REFUTES IT.  IT IS REVERTED, AND WHAT IT LEAVES BEHIND IS SHARPER THAN WHAT IT SET OUT TO LAND.**

Pre-registration: `docs/notes/sm3_s10_prereg_2026-08-04.md`, committed at
`15442b14d2` from HEAD `587d523637`, **before either engine was touched**
(`git diff` against `sim/` and `hdl/rtl/` empty at that commit).  **No board
contact anywhere in the sitting.**

### §71.1 WHAT WAS LANDED, AND WHY IT IS ONE WIRE

§68.4's carried disposition, taken verbatim: the recognition floor's arm
becomes *"the EU's interrupt-entry microcode started"*, published by the EU and
consumed by the BIU — one wire, no address match, strictly generalising the
INTA-only arm.

**THE ENTRY FUNNEL IS ONE PLACE AND THE ROM SAYS SO.**  Read off
`./sim/v30sim disasm docs/V20BITS.TXT`: the interrupt-entry routine is the
page-7 block **`111.0001?000`** (`01EC`…), and the `?` is the **ROM's own
statement** that `INT` (far target 2) and `INTEM` (3) are the same rows.  The
only door into it is the `FARJMP` micro-op, and **all twelve entry sites in the
part go through that one door**:

| site | entry | | site | entry |
|---|---|---|---|---|
| `0105` | `CC` — `INT 3` | | `01D9` | hardware `[-00-]` row 0 — **BRK / TF** |
| `0108` | `CD` — `INT n` | | `01DB` | hardware `[-00-]` row 2 — **NMI** |
| `010F` | `CE` — `INTO` | | `01DF` | hardware `02` bank A — **INTA vector fetch** |
| `0195` | `F6`/`F7` — the DIVIDE trap | | `01E3` | hardware `02` bank B — **INTA vector fetch** |
| `01A9` | `IDIV2` — the same trap | | `0349`, `0401` | `BRKEM`, via `FARJMP INTEM` |
| `0283` | `62` — `CHKIND` / `BOUND` | | | |

**THE GENERALISATION IS STRICT, PROVED ON THE ROM AND NOT ASSUMED.**  The whole
ROM contains exactly **THREE** `[-05-]` (INTA) rows — `01DC`, `01E0`, `01E2` —
and **all three sit inside blocks that terminate in `FARJMP INT`, with no
`FLUSH` row between**.  So every case the old condition armed is armed by the
new one, in the same order relative to both consumers (`flush()`'s re-arm and
`boundary_no_pop()`'s spend).  A machine that armed on the bus cycle would need
two mechanisms for one microcode.

`sim/` was landed as one hook on `CpuT::run_micro`'s FARJMP branch
(`(op.far_loc() >> 1) == 1`) plus `BiuTimed::note_int_entry()`, with the arm
REMOVED from `inta_read()`.  **`hdl/rtl/` was never touched** — the sitting is
sim-first by its own work order and the sim leg decided it.

### §71.2 THE BAR, REWRITTEN — WHAT CHANGED AGAINST §3 AND WHY

§3 of `sm3_s7_prereg_2026-08-04.md` demanded `>= 95 %` on BOTH halves **at every
wait level**.  §68.4 booked its CONTROL half as **defective, structurally**: the
floor is `max(F1+6, F1+L+1)` and at `w >= 1` the restart's `L` is 5/6/7, so the
floor **collapses onto `L+1`** and *"unfloored" is inexpressible in the
coordinate*.  Three changes, each named in the pre-registration before any run:

1. **the discriminating regime is w0 ALONE** (w1-w3 remain must-not-move, but
   carry no information about the arm);
2. **the statistic is the MINIMUM, not a proportion** — a floor is a minimum;
3. **the bar scores the ENGINE leg, not the chip leg** — §68.4 closed the chip
   question (chip `swintnext` w0 30/30 floored, `iretnext` unfloored at the
   minimum), so what was left to show is that an engine reproduces it.

§3's full must-not-move ladder was carried unchanged.

### §71.3 THE AUTHORISING LEG — **MET, AT THE POINT ESTIMATE, EXACTLY**

`sm3_h1_cell.py score --hold 300 --out sm3-h1acell`, 240 banked captures, no
board.  Baselines re-measured on HEAD before the source was touched.

| leg | registered | baseline | **measured after** |
|---|---|---|---|
| `ord1 swintnext w0`, `sim` | **30 / 30** (floor `>= 29`) | 0 / 30 | **30 / 30** |
| `ord2+ swintnext w0`, `sim` | **90 / 90** | 0 / 90 | **90 / 90** |
| `ord1 iretnext` w0/w1/w2/w3 (CONTROL) | 30 each, unmoved | 30 each | **30 each — UNMOVED** |
| `ord2+ iretnext` w0/w1/w2/w3 (CONTROL) | 101/87/60/60, unmoved | same | **UNMOVED** |
| `swintnext` w1/w2/w3 | unmoved | 30/30 each | **UNMOVED** |
| **cell TOTAL, `sim`** | **791 / 791** | 671 / 791 | **791 / 791** |

**Every cell, at the point estimate, with the control untouched.**  The
mechanism does exactly what §68.4 said it would.  The `ucore` baseline is
667/791 (its four extra misses are `LNone` — the engine produces no
acknowledge at that ordinal — a separate pre-existing defect); it was never
landed, so it stands at 667/791.

### §71.4 THE DISJOINT VALIDATION — **AND IT REFUTES THE ARM.  THE CLASS IS THE PIN.**

§64.1's rule was honoured by construction: the `sm3-h1acell` captures SELECTED
the mechanism, so the 3,242-seed fuzz bank — a different generator, a different
sitting, a different bitstream, and no shared capture — is the **DISJOINT
VALIDATION POPULATION**.  §64.2's two named seeds are members of it.

| `timed_fuzz --core sim --evt-replay` | registered | baseline | **measured** |
|---|---|---|---|
| REGISTERED | **EXACTLY 1,272** | 1,272 | **1,272 — the equality HELD** |
| EVT | `>= 780` | 780 | **777 — REGISTERED FAILURE, −3** |
| COMBINED | `>= 2,052` | 2,052 | **2,049** |
| b2 tranche | `>= 154` | 154 | **154 — unmoved** |
| seeds WORSENED | **0** | — | **5 — REGISTERED FAILURE** |

**The REGISTERED equality is a result in its own right** and it was predicted
from the code rather than from a run: the arm's only readers are reached
through `at_fire_boundary()`, so a population with no `evt` axis cannot observe
it.  1,272 of 1,702, to the seed.

**THE MOVEMENT, ITEMISED — 2 improved, 5 worsened, and nothing else moved
verdict:**

```
  IMPROVED  mc1/2672  EVT  pin=0  DIVERGE(first_bad 289, "bs PASV!=INTA") -> EXACT
  IMPROVED  mc1/356   EVT  pin=0  DIVERGE(first_bad 213, "bs PASV!=INTA") -> EXACT
  WORSENED  mc1/1241  EVT  pin=1  EXACT -> DIVERGE  first_bad 267  "bs MEMR!=PASV nxta 0008"
  WORSENED  mc1/2258  EVT  pin=1  EXACT -> DIVERGE  first_bad 654  "bs CODE!=PASV nxta 0536"
  WORSENED  mc1/3052  EVT  pin=1  EXACT -> DIVERGE  first_bad 269  "bs MEMR!=PASV nxta 0008"
  WORSENED  mc2/1157  EVT  pin=1  EXACT -> DIVERGE  first_bad 539  "bs CODE!=PASV nxta 0482"
  WORSENED  mc2/2932  EVT  pin=1  EXACT -> DIVERGE  first_bad 411  "bs MEMR!=PASV nxta 0008"
```

**§4's PREDICTION FIRED EXACTLY.**  `mc1/2672` and `mc1/356` — the two seeds
§64.2 called *"re-entries in every mechanical sense"*, on which both engines
were *"wrong by exactly the 2 clocks the floor costs"* — go **EXACT**.  That is
a prediction written into a committed file and then met on a population the
mechanism was not selected on.  It is the strongest single piece of evidence
this hypothesis has ever had.

**AND THE FIVE ARE THE SAME SHAPE, CYCLE FOR CYCLE.**  Read chip-side off the
banked rows with no engine, every one of the five carries `mc1/2672`'s geometry
exactly — an IVT vector read below `0x400`, the three-word frame, the `0x0480`
handler, the IRET's three contiguous stack pops, the restarted prefetch — and
then the next recognition.  `mc1/3052`, from the entry that precedes it:

```
  MEMR:0000c MEMR:0000e        <- vector 3, a software INT3 entry (no INTA)
  MEMW:03efe MEMW:03efc MEMW:03efa
  CODE:00480 CODE:00482        <- the bare CF handler
  MEMR:03efa MEMR:03efc MEMR:03efe   <- the IRET's three pops
  CODE:00535 ...               <- the RESTARTED prefetch
  ... and the NEXT recognition is an NMI, and the chip does NOT floor it.
```

**THE PARTITION IS PERFECT AND IT IS ONE COORDINATE.**  All five worsened seeds
are **`evt.pin = 1` (NMI)**.  Both improved seeds are **`evt.pin = 0` (INT)**.
**ZERO INT seeds regressed.**  Same shape, same arm, opposite answer, split by
whether the recognition that follows is MASKABLE.

`V30SIM_BNDTRACE=1` — a new env-gated stderr diagnostic in `boundary_no_pop`,
one line per recognition boundary carrying the clock, the arm and whether the
floor is LIVE — reads it directly.  On `mc1/3052` the seed's ONLY boundary is
`BND clk=261 post=1 pend=1 floor=263 live=1`: the entry armed it, the IRET's
flush re-armed it, the restart stamped 263, no pop spent it, and the model paid
two clocks the chip does not pay.

### §71.5 THE DISPOSITION — **REVERTED, BECAUSE THE BAR IS WHAT GOVERNS**

The pre-registration says, in §5.2 and §6: `EVT >= 780`, `worsened = 0`, and
*"Any of them down and the landing is REVERTED, not defended."*  EVT is 777 and
five seeds are worse.  **The landing is REVERTED.**

This is §68.4's rule applied in mirror image.  There, the evidence authorised a
landing the bar did not; the bar won.  Here, the bar's authorising leg is met
**perfectly** — 791/791, every control unmoved — and the ladder fails; the bar
wins again.  A landing that makes the model **worse against silicon** on the
disjoint validation population is refuted by the correctness target itself
(CLAUDE.md: *silicon match is the only correctness bar*), net −3, and no
argument from the cell can buy it back.

**WHAT IS IN THE TREE AFTER THE REVERT** (`git diff` against `587d523637`,
non-comment lines, is exactly five):

* `sim/biu_timed.cpp` — the **`V30SIM_BNDTRACE`** diagnostic, kept.  It is the
  instrument the finding rests on and the finding has to stay reproducible.
  Env-gated `fprintf`, reads no state the block below it does not, nothing
  reads it back.
* comments only, in `sim/biu_timed.h` (the refutation, at the arm's own
  declaration, so the next agent to propose this reads it first),
  `sim/biu_timed.cpp` and `sim/exec_impl.h` (the entry funnel recorded as a
  fact, with "nothing arms from it today" beside it).
* **`hdl/` is byte-identical.**  The ucore was never touched.

### §71.6 WHAT SURVIVES — **THE ARM MAY NOT BE AN ENTRY FLOP AT ALL.  IT MAY BE THE IE RESTORE, AND THAT IS THIS FILE'S OWN OLDER CANDIDATE.**

`biu_timed.h` has carried, since §61.4 and long before any of this:

> *"The MECHANISM behind the arm is NOT ESTABLISHED.  The candidate is the IE
> restore: the entry clears IE, the IRET's PSW pop restores it, and a
> recognition cannot act on a RISING IE for two clocks."*

**It accounts for every population on the table, with no cases:**

| population | IE at the boundary | chip | the IE-rise reading |
|---|---|---|---|
| `swintnext` w0 (INT pin) | entry cleared IE (`CITF`, `01F5`); the IRET's PSW pop RAISES it | **FLOORED 30/30** | an IE-gated recognition cannot act on a rising IE — held |
| `iretnext` ord1 (INT pin) | a PLANTED frame pops IE = 1 into IE = 1 — **no rise** | **UNFLOORED**, min 4 | nothing to wait for |
| `iretnext` ord2+ / every INTA re-entry | entry cleared IE, the handler's IRET raised it | **FLOORED** | held |
| `mc1/2672`, `mc1/356` (INT pin) | same | **FLOORED** | held |
| §64.2's "protected eight" | the rise is long past; pops in between | **UNFLOORED**, gap 4 | spent |
| **the five NMI seeds** | IE rose at the IRET — but the recognition is **NON-MASKABLE** | **UNFLOORED** | an NMI is not gated by IE and has **nothing to wait for** |

The entry-generic arm reaches the same place only by adding *"…and NMI is
exempt"* — a second case for one microcode, which is exactly the shape the
standing principle names as a signal of misunderstanding.  The IE reading needs
no second case, and it needs no new flop: the recognition pipeline **already
reads IE** (`psw_ie` is an existing `v30u_eu` port; the model already models
`kFlagIE`'s early commit at `007A`/`01EA` under I1/F39, which is the same
signal at the same edge).  *"Nothing on the die is wasted"* cuts directly for
it: one rising-edge condition on a wire that is already there, against a
dedicated flop plus an exemption.

**IT IS NOT LANDED AND MUST NOT BE LANDED FROM HERE.**  It was selected on the
BANK, in this sitting, so §64.1 forbids the bank from validating it.  What it
needs is written down instead:

* **its falsifier**: an NMI recognition **FLOORED** after an entry+IRET restart,
  or an IE-gated recognition **UNFLOORED** after one;
* **the cell that would settle it, and it is the one `sm3_h1_cell.py` already
  failed to land**: `--variants clipopf` (a `CLI ; POPF` chain — IE RISING at a
  boundary with **no entry and no acknowledge behind it**).  As first run it
  produced NO ACKNOWLEDGE AT ALL (§61.4 records this as its own open question),
  and **that is now the first thing to fix**, because it is the ONE stimulus
  that separates "IE rose" from "an entry returned".  A `swintnmi` variant —
  `swintnext`'s software entry with the rig asserting **NMI** instead of INT —
  is its board-side twin and would confirm the five bank seeds on directed
  captures;
* **its disjoint validation**, which must be neither the h1a cell nor the
  banked fuzz corpus.

### §71.7 WHAT MOVED, AND WHAT DID NOT

| | before | **after** |
|---|---|---|
| every gate in `standing_gates.md` §B | — | **UNMOVED, all of them** |
| `timed_fuzz --core sim` REG / EVT / COMBINED | 1,272 / 780 / 2,052 | **1,272 / 780 / 2,052** |
| `timed_fuzz --core ucore` REG / EVT / COMBINED | 1,490 / 910 / 2,400 | **1,490 / 910 / 2,400** |
| b2, `sim` / `ucore` | 154 / 172 | **154 / 172** |
| the h1a cell, `sim` / `ucore` | 671 / 667 of 791 | **671 / 667 of 791** |
| `hdl/` | — | **byte-identical** |

**THE REVERT IS PROVED AT THE SEED, NOT AT THE TOTAL.**  Per-seed reports were
banked before the landing and re-run after the revert, and compared on
`exact`, `first_bad`, `kind`, `cat`, `n`, `ndiff`, `sim_rows`:
**0 of 3,242 seeds differ, on BOTH engines.**  A total can agree by
cancellation; this cannot.

Re-run and green after the revert: `make -C sim test` (disasm byte-exact),
`pla3_check`, `check_ucore_tables` 9,988, `timed_gate --suite v0.1 --forms all`
**169,000/169,000 row-diffs 0**, `check_core --core ucore --opcodes all`
**169,000/169,000**, `ulockstep --golden all --cases 50` **17,350/17,350**,
`check_boot --timed 220` and `--timed 400` MATCH, `check_ab_sim` 187 rows MATCH,
`timed_wvec_gate --core ucore` 88/88 **+0.0 %**, `timed_enter_replay --core
ucore` 154/154 ×5, `timed_ins_replay --core ucore --raw` 1,312 / 2,624,
`timed_lawcards` 8 GREEN / 0 RED / 3 UNRESOLVED, `timed_scenario` 18/0/9,
`ss_lint` rc 0 / 222 addresses / 205 flops / 0 UNMAPPED / `SS_VERSION` 0x83.
**No `SS_VERSION` bump was needed** — the landing added no flop to either
engine, as §1 of the pre-registration predicted.

### §71.8 WHAT THIS SITTING DID NOT DO

* **No board contact of any kind.**  `flash_log.jsonl` unchanged at 8 entries;
  the board still carries FLASH #5.  No `div_guard`, no capture, no
  `board_idle` — there was nothing to idle.
* **The `ucore` was never touched.**  The landing is sim-first by the work
  order and the sim leg decided it; building the RTL half of a refuted arm
  would have been work spent on a result already in hand.
* **The 8080 / `gaps` §F.1 work, R7′, and the X1 OE-port work were not
  opened** — all pending USER decisions or their own pre-registration.
* **No memory file was touched and Codex was not launched.**
* No comparator, scorer, golden or ledger figure was changed.  **Nothing in
  `standing_gates.md` §B moved, and nothing was re-scored downward.**

### §71.9 THE LEADS THIS SITTING HANDS THE NEXT ONE

1. **The IE-RESTORE reading of H1's arm (§71.6).**  It is the sharpest lead the
   H1 line has produced: one condition on a wire both engines already have, no
   flop, no cases, and it explains a partition the entry reading has to
   special-case.  **Its blocker is an instrument, not a decision**: `clipopf`
   must be made to produce an acknowledge.  Board cell, needs its own
   pre-registration, and its validation population must be neither of the two
   this sitting used.
2. **`sm3_nmigeom.py` deserves a first-acknowledge census like
   `sm3_ackgeom`'s.**  `sm3_ackgeom` counts INTA cycles, so **every NMI
   recognition in the bank is invisible to it** — which is precisely why the
   class that refuted this landing had never been seen.  A vector-read-keyed
   ordinal over the 208 banked NMI seeds would have predicted the five.
3. **§70.5's READY cone**, **§70.6's SDC falsifier instrument**, the X1 fabric
   leg, **H7's bank association** and **H3's steady-state prefetcher** — all
   unchanged and still queued.

## §72 SESSION SM3, SITTING 11 — **THE IE RESTORE IS THE ARM.  IT IS AUTHORISED BY A NEW BOARD CELL, LANDED IN BOTH ENGINES, AND IT DELETES MORE THAN IT ADDS.**

Pre-registration: `docs/notes/sm3_s11_prereg_2026-08-04.md`, committed at
`0ceeb2f8cb` from HEAD `7fb3e5518b`, **before the first board contact and
before either engine was touched** (`git diff` against `sim/` and `hdl/rtl/`
empty at that commit; the only source change was the instrument).

### §72.1 THE `clipopf` DIAGNOSIS — **THE STIMULUS WAS NEVER BROKEN.  ITS SILENCE IS THE HYPOTHESIS'S OWN PREDICTION.**

§61.3 booked *"a `CLI ; POPF` chain restoring IE never acknowledges a held INT
level"* as an open observation and §71.9 made fixing it the blocker on the
whole IE line.  It is not a rig defect.  Read off the **24 RETAINED captures**
in `sw/testdata/sm3-h1cell/`, chip side, no engine, **no board contact**:

* the popped word is **`0xF202` on every POPF** — IE **is** set in the image;
* the chain **runs to completion** — 81 stack reads at `0x3F00`, `0x3F02`, …
  stepping by 2, then the harness epilogue and `HALT`.  It does not wedge;
* `hold = 300` and `fired = True` on all 24 (`manifest.json`) — the rig DID
  drive the pin, for ~25 iterations of the 12-clock loop;
* the whole capture contains **0 INTA cycles and 0 memory writes** — nothing was
  serviced between the `CLI` and the `POPF` either.

**`FA 9D FA 9D …` has exactly two boundaries per iteration: after the POPF (IE
has just RISEN) and after the CLI (IE is CLEAR).**  A law that forbids the
boundary at which IE rose, and tests IE live at the next one, recognises
**never**.  The fix is PADDING, and that is the cell below.

**AND THE BANKED GOLDENS ALREADY CARRIED HALF THE ANSWER**, unread until now.
`tests/v30/v0.1/INT.9D.json.gz` and `INT.FB.json.gz`, 400 silicon cases, scored
with no engine on `pushed_IP − initial_IP − instruction length`:

| golden | population | extra 1-byte NOPs before the entry |
|---|---|---|
| `INT.9D` (POPF), IE **1 → 1**, no rise | 111 | **0** in 104, 1 in 7 |
| `INT.9D` (POPF), IE **0 → 1**, a RISE | **89** | **1 in 89 of 89 — never 0** |
| `INT.FB` (STI), always a rise | **200** | 1 in 160, 2 in 40 — **never 0** |
| `INT.8ED0` / `8ED8` (`MOV SS,r`), IE already 1 | 400 | never 0 — a SEPARATE, opcode-set shadow (`irq_shadow`) |
| `INT.90` / `INT.B8`, IE already 1 | 400 | 0 occurs freely |

On silicon **an IE RISE costs the raising instruction's own boundary and an
unchanged IE costs nothing.**  What the goldens cannot say — they are
single-instruction tests with a NOP sled behind them — is what happens at the
*next* boundary when IE has gone down again.  That is the cell's question, and
it is why the cell was still needed.

### §72.2 THE CELL — 768 CAPTURES, AND THE OBSERVABLE IS THE PUSHED FRAME

`sw/sm3_h1_cell.py run --out sm3-s11cell`, socket only (`EMIT_USE_CORE` False),
`div_guard` **PINNED** (`div=8 (4 MHz), commanded by this connection`), 768
captures, **`fired = True` on all 768**, 0 transport errors, 79 s, full
per-clock rows + raw 64-bit words + **1,538 files under `SHA256SUMS`**,
`board_idle()` run and OK.  **NO FLASHING — the board carries FLASH #5.**

Four sleds, every instruction one byte, so the byte period is the boundary
period: `iepop` = `CLI ; POPF ; NOP ; NOP`, `iesti` = `CLI ; STI ; NOP ; NOP`,
`iehot` = `POPF ; NOP ; NOP ; NOP` with IE already up and the popped word
popping IE up (**no rise** — the control), and `clipopf` = §61.3's, unchanged.
Both pins, four wait levels, 24 delays.

**THE OBSERVABLE IS READ OFF THE PINS WITH NO ENGINE.**  Every entry pushes
three words with SP descending — PSW, CS, **IP** — and no sled contains another
memory write, so a run of three MEMW cycles stepping down by 2 IS an entry and
its third word is the **boundary the part chose**.  It reads identically for a
maskable acknowledge (INTA pair in front) and an NMI (none), which is the only
reason the two pins are comparable.  `phase = (pushed_IP − 0x0500) mod period`.
The reader was **VALIDATED ON RETAINED SILICON BEFORE ANY NEW CAPTURE**:
`nop_w0_d12` → `ip = 0x0504`, `iretnext_w0_d12` → `0x0501`, `callret_w0_d12` →
`0x0503`, each sled's correct return address, and `psw = 0xF202` (IE **SET**)
on all of them — which independently says silicon pushes the PSW **before**
`CITF` clears IE.

### §72.3 THE RESULT — **ALL EIGHT REGISTERED OUTCOMES MET AT THE POINT ESTIMATE**

w0, the discriminating regime, 24 captures per cell:

| # | leg | registered (IE) | **measured** | NOFLOOR | INHIBIT |
|---|---|---|---|---|---|
| S1 | `iepop` p0, OWN (p2) | **= 0** | **0** | ≥ 1 ✗ | = 0 ✓ |
| S2 | `iesti` p0, OWN (p2) | **= 0** | **0** | ≥ 1 ✗ | = 0 ✓ |
| S3 | `iepop` p0, DEAD (p1) | **= 0** | **0** | — | ≥ 1 ✗ |
| S4 | `iesti` p0, DEAD (p1) | **= 0** | **0** | — | ≥ 1 ✗ |
| S5 | `clipopf` p0, no entry | **24 / 24** | **24 / 24** | 0 ✗ | 0 ✗ |
| S6 | `iehot` p0, OWN (p1) — CONTROL | **≥ 1** | **9** | ≥ 1 ✓ | ≥ 1 ✓ |
| S7 | `iepop` p1 (**NMI**), OWN (p2) | **≥ 1** | **9** | ≥ 1 ✓ | = 0 ✗ |
| S8 | `clipopf` p1 (**NMI**), entries | **≥ 20 / 24** | **24 / 24** | ≥ 20 ✓ | 0 ✗ |

**The maskable histograms at w0 are `{p0: 6, p3: 18}` and NOTHING ELSE** — never
the boundary at which IE rose, never the boundary at which IE is clear — and
they repeat identically at w1, w2 and w3, which the bar did not ask for.
**NOFLOOR is refuted by S1/S2/S5; INHIBIT by S3/S4/S7/S8.**  §64.1 is satisfied:
the reading was selected on the bank in §71.4 and this population is a directed
board cell that did not exist when it was written.

**AND THE FLOOR'S SIZE FALLS OUT OF THE SAME CAPTURES**, chip side, no engine,
w0, measured from the POP that commits IE to the entry's announcement:

| population | IE at that pop | min |
|---|---|---|
| `iehot` p0 (POPF, IE 1 → 1) | **no rise** | **8** |
| `iretnext` ord1 (planted frame, IE 1 → 1) | **no rise** | **8** |
| `swintnext` ord1 (the IRET raises IE) | **a RISE** | **10** |

**+2, and it is H1's own two clocks re-anchored from "an INTA behind us" to "IE
just rose".**  No new number and no new instant, on a coordinate that needs no
engine to read.

### §72.4 THE LANDING — `sim/`

**DELETED**: `bnd_pending_` (the INTA arm in `inta_read`), `bnd_arm_` (the
flush re-arm), `bnd_floor_` (the restart-grant stamp), `wait_bnd_floor()`, the
pop's spend, and the boundary's three clears — six hook sites.
**ADDED**: `ie_rise_` / `ie_prev_`, `sample_ie()`, `wait_ie_floor()`,
`maskable()` and `kIeFloor = 2`.  Net state **1 long + 2 bools → 1 long + 1
bool**.  A non-maskable recognition bypasses **by construction** — it never
reads the stamp — and there is no exemption clause anywhere in the law.

`sample_ie()` is called from `tick()` **and** from the top of
`boundary_no_pop()`: a recognition boundary is asked for on a clock whose tick
has not run yet, and the rise this floor is about (the IRET's PSW restore
committing at its own retire) happens on exactly that clock.  `V30SIM_IETRACE`
is the new instrument that established it; `V30SIM_BNDTRACE` is re-pointed.

| `timed_fuzz --core sim --evt-replay` | before | **after** |
|---|---|---|
| REGISTERED | 1,272 | **1,272 — the equality HELD, to the seed** |
| EVT | 780 | **782** |
| COMBINED | 2,052 | **2,054** |
| b2 tranche | 154 | **154** |
| **seeds WORSENED** | — | **0** |

**PROVED AT THE SEED, NOT AT THE TOTAL**, over all 3,242 on
`exact`/`first_bad`/`kind`/`cat`/`n`/`ndiff`/`sim_rows`: **IMPROVED 2, WORSENED
0**, and the two improved are `mc1/2672` and `mc1/356` — §64.2's two named
seeds, the same two the REFUTED entry-generic arm fixed in §71.4, and this time
**the five NMI seeds do not move at all**.  Six further seeds move `ndiff`
alone, same verdict and same `first_bad`.  `sm3_h1_cell.py score --core sim`
goes **671 → 791/791**, the `swintnext` w0 column **0/30 → 30/30**, every
`iretnext` control UNMOVED.

### §72.5 THE LANDING — `hdl/rtl/ucore/`, AND IT IS A NET DELETION

**The change is two wires:**

```
  irq_int_lvl = int_p[2] && ie_p[2] && psw[FIE]            (was: no psw[FIE])
  eu_bnd_post = !intr_pending && !ie_p[3] && !irq_nmi_lvl  (was: !intr_pending)
```

Everything else is removal: `bnd_pending` / `bnd_arm` / `bnd_stamp` /
`bnd_cnt` (**4 registers, 5 flops**), the `bnd_hold` output port and its EU
input, the INTA arm, the flush re-arm, the grant stamp, the T1 counter, the pop
spend, the withdrawal and expiry un-stamps, three SVAs, and `SSA_B_BND_*`
**0x066-0x069**.  `SS_VERSION` **0x83 → 0x84**, `SS_BIU_COUNT` 105 → 101,
`SS_COUNT` 222 → 218, `SS_TAG` 0x83DE → **0x84DA**; the vacated codes are
**RETIRED, NOT REUSED**.  `ss_lint` PASS, census **201 flops** (was 205), **0
UNMAPPED**.

**WHY THE DELETION IS LEGITIMATE.**  A gate that demands IE up NOW *and* up
three clocks ago cannot act on a rising IE, and that IS the floor.  With the
live-IE term in place `bnd_hold` was **MEASURED INERT**: forced to zero, the
whole 3,242-seed bank scores REGISTERED 1,490 / EVT 910 / COMBINED 2,400 — to
the seed.  Four rivals were measured beside it and every one is recorded in the
RTL next to the term it justifies:

| variant tried | EVT |
|---|---|
| gate weakened to `ie_p[1]`, floor deleted outright | **822** |
| floor re-anchored on the IE rise but gating NMI too | **908** — and the two lost seeds are BOTH `evt.pin = 1`, one of them `mc1/3052`, one of §71.4's five |
| prefetcher suspend forced unconditional | **897** |
| suspend without `!irq_nmi_lvl` | EVT fine, but `NMI.B8` **200 → 188** (12 cases, all `row 6 busstat: exp CODE got PASV`) |
| **as landed** | **912** |

| `timed_fuzz --core ucore --evt-replay` | before | **after** |
|---|---|---|
| REGISTERED | 1,490 | **1,490 — to the seed** |
| EVT | 910 | **912** |
| COMBINED | 2,400 | **2,402** |
| b2 tranche | 172 | **172** |
| **seeds WORSENED** | — | **0** |

**IMPROVED 2, WORSENED 0**, proved at the seed over all 3,242 — and they are the
SAME two seeds the model gained.  Only 2 of 3,242 differ in any scored field.
`sm3_h1_cell.py score --core ucore --hold 300` goes **667 → 789/791**, the
`swintnext` w0 column **0/30 → 30/30**; the 2 residual cells are `iretnext`
ord2+ w0 `LNone`, the pre-existing defect §71.3 named (it was 4).

**AND ON THE AUTHORISING CELL THE ucore IS NOW THE CHIP, CELL FOR CELL.**  All
seven w0 legs, **168/168 captures** (it was 136/168): `iepop`/`iesti` p0
`{p0: 6, p3: 18}` with OWN and DEAD at **zero**, `clipopf` p0 **NO ENTRY
24/24**, and `iehot` p0 plus all three NMI legs unchanged — they were already
exact, which is the control that says the change touched only what it claimed.

**NOTE FOR THE NEXT AGENT — `sm3_h1_cell.py score` DEFAULTS TO `--hold 16`.**
The banked `sm3-h1acell` captures were taken at `hold = 300`.  The `sim` leg
REPLAYS the chip's acknowledge positions and does not care; the `ucore` leg
PREDICTS and does, and at the default it scores **89/791** because the pin has
dropped before the second boundary.  §71.3's figures are `--hold 300` figures.
Quote the flag or do not quote the number.

### §72.6 WHAT MOVED, ITEMISED

| gate | before | **after** |
|---|---|---|
| `timed_fuzz --core sim --evt-replay` REG / EVT / COMBINED | 1,272 / 780 / 2,052 | **1,272 / 782 / 2,054** |
| `timed_fuzz --core ucore --evt-replay` REG / EVT / COMBINED | 1,490 / 910 / 2,400 | **1,490 / 912 / 2,402** |
| `ss_lint` addresses / flops / `SS_VERSION` | 222 / 205 / 0x83 | **218 / 201 / 0x84** |
| the h1a cell, `sim` / `ucore` (`--hold 300`) | 671 / 667 of 791 | **791 / 789 of 791** |

**UNMOVED, all re-run on the final binaries**: `make -C sim test`;
`pla3_check` 21; `check_ucore_tables` 9,988; `timed_gate --suite v0.1 --forms
all` **169,000/169,000 row-diffs 0** (`INT.9D` and `INT.FB` included);
`check_core --core ucore --opcodes all --cases 0` **169,000/169,000**;
`v0.1-w1`/`-w3` 1,200; `EB` 200; the four `evt` cells 200/1,200/200/1,200;
`w1evt-biased` 1,200; block I/O **229,999/229,999**; f4a 160; f0lock 400;
`check_boot --timed 220` and `--timed 400` MATCH on both engines;
`ulockstep --golden all --cases 50` **17,350/17,350**;
`timed_wvec_gate` 88/88 **+0.0 %** on both;
`timed_enter_replay` 154/154 ×5 on both;
`timed_ins_replay --raw` 1,312 / 2,624 on both;
`timed_scenario` 18/0/9; `timed_lawcards` **8 GREEN / 0 RED / 3 UNRESOLVED**;
`check_ab_sim` 187 rows MATCH; `ss-sweep` modes 1/2/5 4/4;
`CE_HOLD_VIOL 0`; `gen_ucore_qsf --check`; `optable --selfcheck`;
`test_fuzz_classify` / `test_fuzz_accept`;
the four HLT sweeps **91/97, 92/95, 42/46, 40/45 = 265/283** (`ucore`) and
**91/97, 95/95, 44/46, 42/45 = 272/283** (`sim`); b2 **154** / **172**.

### §72.7 THE LAW, AND ITS FALSIFIER

> ⚠ **ERRATUM — "two clocks" IS A MEASURED MINIMUM, NOT AN ESTABLISHED
> MECHANISM.  READ §72.7b BEFORE QUOTING THIS AS A TIMER.**  What sitting 11
> established is IE gating, maskability and a floor of at least +2; the
> sitting-11 geometry cannot distinguish a clock count from a boundary count.
> The statement below is left exactly as it was written.

> **A MASKABLE recognition may not act until two clocks after PSW.IE's RISING
> EDGE.  A NON-MASKABLE one is not IE-gated and waits for nothing.**

MEASURED: the sitting-11 board cell (§72.3, S1-S8, 768 captures); §68.4's
`swintnext` 30/30 floored against `iretnext` unfloored; §61.1's 2,318 banked
re-entries with zero exceptions; the 289 golden IE-rise cases of §72.1; and
§71.4's five NMI seeds, which are now explained rather than special-cased.

*Falsifier*: an NMI recognition FLOORED after an entry + IRET restart; an
IE-gated recognition UNFLOORED after one; a maskable acknowledge on silicon
whose **pushed PSW has IE = 0**; or an `iepop`/`iesti`-shaped cell in which the
raising instruction's own boundary is taken by the INT pin.

### §72.7b **ERRATUM (SM3 sitting 13, Codex phase-review concern 4a) — WHAT §72.7 ESTABLISHES, AND WHAT IT ASSUMES**

**ESTABLISHED by the sitting-11 cell, and none of it is retracted:**

1. **IE GATING** — the boundary at which IE is CLEAR is never taken by a
   maskable recognition (S3/S4, 0 of 24 on both sleds).
2. **MASKABILITY** — the NMI pin takes every boundary freely, including the one
   at which IE rose (S7 = 9, S8 = 24/24).  A non-maskable recognition is not
   IE-gated.
3. **A FLOOR OF AT LEAST ONE BOUNDARY** — the raising instruction's OWN boundary
   is never taken by a maskable recognition (S1/S2, 0 of 24), while the same
   instruction with NO rise gives that boundary up freely (S6 = 9).
4. **A MINIMUM OF +2 CLOCKS** on the pop→announcement coordinate: 8 with no
   rise, 10 with one.

**NOT ESTABLISHED — and §72.7's wording asserts it:** that the floor is a
**COUNT OF CLOCKS**.  A boundary-sampling pipeline that simply REJECTS THE FIRST
BOUNDARY AFTER THE RISE, whatever its distance, produces the identical
`{p0: 6, p3: 18}` histogram and the identical +2, because on `CLI ; POPF ; NOP ;
NOP` the first boundary after the rise happens to sit about two clocks away.
**The two readings coincide at that spacing and only at that spacing**, and
sitting 11 had no other spacing.

**AND THE LANDED RTL IS NOT A TIMER.**  What is in `hdl/rtl/ucore/v30u_biu.sv`
is

```
    irq_int_lvl = int_p[2] && ie_p[2] && psw[FIE]
```

— a three-clock-old PIN, a three-clock-old IE, and the LIVE IE.  That is a
**pipelined level test**: it cannot act on a rising IE because it demands IE up
*now* and up three clocks ago, and the delay is the pipeline's, not a counter's.
It MATCHES the measured law; it is not the unique mechanism that does, and it
contains no register that counts to two.  There is likewise no such counter in
`sim/` — `kIeFloor = 2` is a comparison against a stamp, which is the same
ambiguity written in C++.

**THE QUESTION IS THEREFORE OPEN, WITH BOTH RENDERINGS NAMED:**

* **CLOCK / LEVEL** — a maskable recognition is permitted at any boundary two or
  more clocks after the rise.  Both engines implement this.
* **BOUNDARY QUANTISATION** — a maskable recognition is refused at the first
  boundary after the rise and permitted at the next, regardless of how many
  clocks separate them.

**They are separated by a cell that moves the first boundary after the rise FAR
AWAY IN CLOCKS**, which is what SM3 sitting 13 built and ran (`sm3_s13_prereg_
2026-08-05.md` §2; the result is §74.3).  Read that before restating this law.

### §72.7a ONE STANDING GATE WAS **NOT RE-RUN**, AND IT IS BOOKED AS NOT RUN

`python3 sw/fuzz_campaign.py lint` (standing_gates §A) **did not complete in
this session** and no result for it is claimed.  Four attempts each sat in
`State: S / do_wait` at **0 % CPU with an open socket on fd 10** — it is
blocked waiting on a child, not computing — and §A describes the §A set as
board-free, so this is a discrepancy worth someone's attention in its own
right.  Every attempt was killed and `board_idle()` was re-run and OK after the
last one.

It is listed here rather than quietly omitted.  It lints the SOUP and RAW
IMAGE GENERATORS (`_lint_soup` / `_lint_raw` — "the generators never emit a
chip-wedging image"); this sitting changed `sim/biu_timed.{h,cpp}`,
`sim/exec_impl.h`, `hdl/rtl/ucore/` and `sw/ss_lint.py`, none of which the
generators read.  **That is a reason to expect it green, not evidence that it
is.**

### §72.8 WHAT THIS SITTING DID NOT DO

* **No flashing.**  `flash_log.jsonl` unchanged; the board still carries
  FLASH #5.  No synthesis was run — the RTL change is a net deletion of 5 flops
  and a port, and its Quartus leg belongs to whichever sitting next needs a
  bitstream.
* **The fabric legs were not re-taken** (they are FLASH #5's and this change is
  not in any bitstream).
* No Codex launch, no memory file touched, no R7′, no 8080 / `gaps` §F.1.
* No comparator, golden or scorer was changed; nothing was re-scored downward.

### §72.8a ERRATUM — A COUNT IN ONE COMMIT MESSAGE

Commit `deeb18bbbf` (the `sim/` landing) says *"THE CELL, 672 captures"*.  **The
cell took 768.**  672 was the planned figure written into the pre-registration's
§2.2, which excluded `iehot` on the NMI pin as a maskable-only control; the run
took that leg anyway (`--pins 0,1` applies to every variant) and the extra 96
captures are retained and scored like the rest.  `manifest.json` says 768, this
section says 768, and the leg is reported in §72.3's table (`iehot` p1, OWN 9 —
identical to `iehot` p0, which is itself a result: the control behaves the same
on both pins because it contains no rise for either to be gated by).  Recorded
rather than left standing: a commit message that undercounts its own population
is still a commit message that does not match the artifact.

### §72.9 THE ucore's REGISTERED-BANK FAMILY CENSUS, RE-TAKEN

`sw/s15_census.py --core ucore --pop reg` on this sitting's own report (the
`--core` matches the report's core, per the standing rule):

```
  PF_LOST 106 · DATA_SEQ 36 · TAIL_EXTRA 29 · PF_GAINED 24 · PF_ADDR 8 ·
  SCHEDULE 5 · PIN 4  = 212        (= 1,702 − 1,490, catch-all empty)
```

**This sitting did not move it** — REGISTERED held at 1,490 to the seed, and the
two seeds that moved are both EVT.  It is recorded because CLAUDE.md still
quotes §58.4's `107 · 41 · 28 · 25 · 9 · 5 · 4 = 219`, which is the **1,483**-era
table: the difference is SM3 sitting 6's testbench fix (§67.1), not anything
here.  Quote 212 with the report it came from, or quote 219 with §58.4's.

## §73 SESSION SM3, SITTING 12 — **R7′ IS REAL, IT HAD SWAPPED SIDES, IT IS CLOSED BY ONE MUX, AND C11 IS ESTABLISHED IN FABRIC**

**2026-08-04/05, branch `ucsim`, from HEAD `144e67416b`.  Task #37.  A BOARD
SITTING WITH FLASHING AUTHORISED, AND THE FLASH WAS TAKEN.**  Two
pre-registrations, both committed before the work they govern:
`docs/notes/sm3_s12_prereg_2026-08-04.md` at **`d2f413b8c3`**, BEFORE the first
board contact of the sitting, and `sm3_s12b_prereg_2026-08-04.md` at
**`2f39fafb2a`**, BEFORE the second form was built.  Single writer confirmed
before contact (`0 users`, no serve process on `mister-nec`); `div_guard`
**PINNED** on both sides of the fabric legs; `use_core` **False** as found and
**False** as left, verified on the board; **0 transport errors in the whole
sitting**; `sw/testdata/flash_log.jsonl` **8 → 9 entries**.

> **Standing principle, applied throughout.**  *"A guiding principal here needs
> to be simplicity.  This is 80's era hardware, they aren't wasting silicon on
> anything that isn't necessary.  Complex or confusing behavior that we see is
> likely to be simple systems interacting in ways you do not fully understand
> yet."*

**THE ONE-LINE RESULT.**  `READY` reached the EU's next-state chain through
**one AND gate feeding one mux at the head of a twelve-position unrolled
chain**; moving that mux onto the `psw` register's own `D` pin takes the cone
from **62–63 logic levels to 19**, takes the DEFAULT build from **19.42 MHz back
to 45.89**, costs **no flop and no ladder delta anywhere**, and the retention
bitstream built on top of it scores **265/283 in fabric — the offline column
exactly, 119 of 119 closed, 0 survivors, 0 cells differing.  §56.3a's both
halves are MET and C11 is ESTABLISHED.**

### §73.1 THE MEASUREMENT THAT CHANGED THE SITTING — **THE DEFAULT BUILD WAS THE ONE THAT MISSED**

Both configurations rebuilt from HEAD, and then **both rebuilt again from a
DELETED `db`/`incremental_db`**, because a claim this size may not rest on an
incremental compile:

| | §69.4/§70.1 (FLASH #5's tree) | **HEAD, incremental** | **HEAD, CLEAN db** |
|---|---|---|---|
| **control** (macro OFF) Fmax `divclk` | **45.67 MHz** | **19.42** | **19.42** |
| control worst setup / TNS | +9.355 / 0.000 | **−20.254 / −13,129.815** | **identical** |
| control ALMs / A&S registers | 11,167 / 4,797 | **11,123 / 4,793** | **identical** |
| **retention** (macro ON) Fmax | **20.25 MHz** | **44.20** | **44.20** |
| retention worst setup / TNS | −18.132 / −11,049.741 | **+8.626 / 0.000** | **identical** |
| retention ALMs / A&S registers | 11,279 / 4,817 | **10,681 / 4,813** | **identical** |

**The two builds had exchanged places on the same 20-flop difference**, which is
what §70.5 said the fragility would look like if it were real.  The failing-path
census on the control is R7′ verbatim: **20,000 of 20,000 launch from
`emu|system_large|c_ready_q`, 20,000 of 20,000 capture inside `v30u_eu`**, worst
ten at **62–63 logic levels, 51.2 ns against 31.25**, all to
`v30u_eu|opc_base[3]` — character for character the endpoint §52.3 recorded for
the `srst` cone it took out of the same chain.

**So G6 was RED at HEAD for the configuration every bitstream is built from, and
no gate in the tree saw it**: sitting 11 landed RTL (a net DELETION of five
flops) and declared that it ran no synthesis (§72.8), which is allowed, and the
standing gate set carries no Quartus leg.  That absence is the finding, not the
sitting's conduct.

### §73.2 WHERE THE CONE WAS — **ONE TERM, FOUND BY ELIMINATION AND CONFIRMED TWICE**

`READY` enters `v30u_biu`'s next-state in exactly three places: `ready_prev`
(straight to a flop), `rd_data_edge` (published as `eu_rd_edge`), and the
`case (ts)` READY sample.  From the third, the post-advance `ts` is read once
more — M22's expiry test — and what that reaches on the EU's side is
`eu_slot_busy_n` and nothing else; `q_ripe_lead_n`, `eu_rd_done_n`,
`eu_wr_done_n`, `eu_rdata_n` and `eu_rd_edge_d` are REGISTER-ONLY.
`eu_slot_busy_n` has ONE consumer, `S_PRERD`'s `chain == 0` arm, and **every
branch of it sets `stop`**, so its cone ends at `row_posted_n`/`rd_pending_n`.

**By elimination the 62-level cone had to be `eu_rd_edge`, whose single consumer
seeded `psw_n` in block (a) — at the head of the twelve-position chain.**  Both
observed endpoints (§70.3's `wb_kind[1]`, this sitting's `opc_base[3]`) are
chain outputs, and the surviving `c_ready_q` path after the fix lands on
`row_posted` / `row_slot_wait`, which is the `eu_slot_busy_n` path the
elimination predicted would remain.  Two independent confirmations of a reading
taken from the source.

### §73.3 FORM 1 — **BUILT, IT WORKED, AND ITS OWN FALSIFIER REFUTED IT**

The data-edge PSW load moved to the `psw` register's `D` pin, block (a)'s write
deleted, with a pre-registered assertion beside it.  It did what it was built
to do — control **19.42 → 42.37 MHz**, **0** failing paths, worst `c_ready_q`
path **19 levels**; retention **45.30 MHz** — and the ladder was **ZERO-DELTA on
all 34 comparable gates**, fuzz reports included.

**And the assertion FIRED**, on 1 seed of 3,242, `mc2/2788`:

```
  row_blocked=0  poste=0  iend_owed=0
  f_wait=0  nr_wait=0  opr_free_now=1
  rd_done_cnt=1  rd_pending=2  rdq_n=1  st=S_ROW  upc=7.08.6
```

A SECOND read outstanding while an EARLIER one already sits in the completed-read
store, so `nr_have` holds, `nr_wait` is 0, **the row is NOT blocked** — and the
`OPR -> FLAGS` row RUNS on the same clock the second read's data edge fires,
writing `opr_live` (the EARLIER word) where the data edge wants `eu_rd_edge_d`
(the CURRENT one).  Different values, and the order decides.  `ENGINE ABORTS`
moved **0 → 1**, itself a reported-field delta.

**REVERTED, per `sm3_s12_prereg` §9, which named this outcome in advance.**  The
H1a precedent (§71) is the shape: a form that is perfect on its authorising leg
and refuted by its own disjoint check comes out.

### §73.4 FORM 2 — **`&& row_blocked`, AND IT IS EXACT IN BOTH CASES**

Registered before it was built (`sm3_s12b_prereg`).  One term added to the take:

```
  wire rd_edge_take_raw  = eu_rd_edge && (st == S_ROW) && e_f &&
                           (e_s1 == 5'd6) && (e_d1 == 5'd15);
  wire rd_edge_psw_take  = rd_edge_take_raw && row_blocked;

  psw <= (srst && !ss_we)             ? psw_r
       : (rd_edge_psw_take && !ss_we) ? rd_edge_psw
       :                                psw_n;
```

`row_blocked` is REGISTER-ONLY (`st`, `e_f`, `f_wait`), so the cone is
unaffected.  The two cases partition the clock:

* **`row_blocked` holds** — `S_ROW`'s `chain == 0` arm sets `stop` and assigns
  nothing, positions 1-11 are skipped, `psw_n` reaches the commit equal to its
  preload, and the `D`-pin write is the same clocked value.  Guarded by
  **falsifier (A)**: `take_raw && row_blocked ⟹ !poste && !iend_owed`.
* **`row_blocked` does not hold** — the row is a pure register transfer, so
  `row_acts_ok` holds and the step performs `dest1 = FLAGS`, overwriting `psw_n`
  entirely.  The deleted block-(a) write was DEAD.  Guarded by **falsifier (B)**:
  `take_raw && !row_blocked ⟹ row_acts_ok && e_have1`.

**BOTH FALSIFIERS ARE SILENT OVER THE WHOLE LADDER** — 169,000 golden cases,
17,350 lockstep, 3,242 fuzz seeds, every suite — **and both STAY in the tree.**

### §73.5 THE ZERO-DELTA BAR — **MET, AT THE SEED**

The BEFORE leg was measured on this tree at HEAD before anything changed
(`~/.cache/ucsimt-tmp/sm3s12/ladder_before.log`), not quoted from the ledger.
**38 of 38 steps identical**, and at the seed:

| report | entries | differing |
|---|---|---|
| `timed_fuzz --core ucore --evt-replay` | 3,242 | **5 — and every one of them is a LINE NUMBER inside a pre-existing `$warning` text** (`v30u_eu.sv:2551` → `:2620`), no scored field |
| `timed_fuzz --core ucore --seeddir b2-tranche` | 216 | **0** |
| `timed_fuzz --core sim --evt-replay` | 3,242 | **0** |

Reproduced unmoved: `check_core --opcodes all --cases 0` **169,000/169,000**;
`v0.1-w1`/`-w3` **1,200** each; `EB` **200**; the four `evt` cells
**200/1,200/200/1,200**; `w1evt-biased` **1,200**; block I/O
**229,999/229,999**; `f4a` **160**; `f0lock` **400**; `check_boot --timed
220`/`400` MATCH; `ulockstep --golden all --cases 50` **17,350/17,350**;
`timed_wvec_gate` **88/88 +0.0 %**; `timed_enter_replay` **154/154** on all five
legs; `timed_ins_replay --raw` **1,312 / 2,624**; `check_ab_sim` **187 MATCH**;
`CE_HOLD_VIOL 0`; `timed_scenario` **18/0/9**; `timed_lawcards` **8 GREEN / 0
RED / 3 UNRESOLVED**; `timed_gate v0.1 --forms all` **169,000, row-diffs 0**;
`--ss-sweep` modes 1/2/5 **80/80 · 24/24 · 2,776/2,776**; `ss_lint` **rc 0, 218
addresses, 201 flops, `SS_VERSION` 0x84**; `make -C sim test`; `pla3_check`;
`check_ucore_tables` **9,988**; `optable --selfcheck`; both fuzz self-tests;
`x1_retention offline` **265/283**.  `ENGINE ABORTS` **0**.

### §73.6 THE QUARTUS RESULT — **BOTH BUILDS, BOTH BARS, AND THE DEFAULT IS ABOVE FLASH #5's OWN BAND**

| bar | registered | **control (macro OFF)** | **retention (macro ON)** |
|---|---|---|---|
| errors, A&S / Fitter / Assembler / TimeQuest | 0 | **0 / 0 / 0 / 0** | **0 / 0 / 0 / 0** |
| latches as a RESOURCE | 0 | **0** | **0** |
| `lpm_divide` | 0 | **0** | **0** |
| **Fmax `divclk`** | **≥ 32 MHz** | **45.89** | **45.87** |
| worst setup | > 0 | **+8.493** | **+8.802** |
| TNS, setup AND hold, every domain | 0.000 | **0.000** | **0.000** |
| ALMs | — | 11,133 (27 %) | 11,122 (27 %) |
| failing paths from `c_ready_q` | — | **0** | **0** |
| worst `c_ready_q` path | — | **19 levels, → `row_slot_wait`** | **19 levels, +12.595** |

**AND NO FLOP MOVED.**  Across ALL SIX builds of this sitting (before / form 1 /
form 2, × control / retention) the A&S per-entity register counts are
**IDENTICAL**: `v30_core` **1,077**, `v30u_eu` **675**, `v30u_biu` **402**,
`nec_bus` **309**, `system_large` **2,044** (control) / **2,065** (retention).

> **A CORRECTION TO §69.3's LIVENESS ARITHMETIC, MADE HERE RATHER THAN LEFT.**
> §69.3 reports the retention model as **+20** on the whole-design A&S total.
> Measured per entity on six builds, `system_large`'s own A&S registers are
> **25 → 46, i.e. +21**, in every pair.  The whole-design total wobbles by ±1
> across builds in `mcp23009` — a MiSTer I2C expander this change cannot reach —
> which is what made +21 read as +20 once.  **Quote the per-entity figure.**
> §8's liveness bar is MET either way, and `core_ad_hold` is absent from
> `Registers Removed During Synthesis` on every retention build.

### §73.7 THE X1 OFFLINE RE-PROOF — AND **THE VACUOUS-GATE PATTERN, SEVENTH INCARNATION**

`x1_retention.BIN` named `hdl/tb/obj_dir_sys{,_ret}/**tb_sys**`, which is what
sitting 6's ad-hoc hand-rebuild happened to call its output (§67.7).  The
`build()` added at **sitting 8 to close §67.6's SIXTH incarnation** runs plain
`verilator --binary --top-module tb_sys`, and that writes **`Vtb_sys`**.  So
`build()` compiled the current RTL into a file `capture` never opened, printed
`REBUILT`, and `capture` ran the 14:53 binary from sitting 6.  Measured, not
inferred: the two files differ, `Vtb_sys.mk` says `default: Vtb_sys`, and
`tb_sys`'s mtime did not move across two `build()` runs.

**WHAT THIS RETRACTS.**  §69.2's *"the 283 `ret` capture records are
BYTE-IDENTICAL to HEAD's, and so are the 283 `base` records"* was **a binary
compared with ITSELF** — the `AD_OE` re-key had never been exercised in
simulation at all.  §2 of `sm3_s8_prereg_2026-08-04.md` is vacuous the same way.

**WHAT IT DOES NOT RETRACT.**  Sitting 8's BEFORE-leg argument, which was right
by accident: the 14:53 binary is built from sitting 6's RTL, and that is exactly
the RTL FLASH #5 carries, so the `base` column it produced is a faithful model
of FLASH #5 and the failing-set equality §68.2 established stands.

**FIXED**: `BIN` points at `Vtb_sys`; `build()` now exits with a message if the
binary does not exist or was not written by the compile that just ran; the two
stale files are archived by rename to `tb_sys.stale-s6`, nothing deleted.

**RE-PROVED on the rebuilt instrument, twice — once at HEAD and once on the
form-2 tree — with identical results:**

| leg | §69.2 (stale binary) | **HEAD, rebuilt** | **form-2 tree** |
|---|---|---|---|
| `offline` (`tb_v30_core`) | 265 / 283 | **265 / 283** | **265 / 283** |
| `tb_sys` base | 146 / 283 | **146 / 283** | **146 / 283** |
| `tb_sys` ret | 265 / 283 | **265 / 283** | **265 / 283** |
| base-only failures, all INTA | 119 / 119 | **119 / 119** | **119 / 119** |
| BAR (i) / BAR (ii) | MET | **MET / MET** | **MET / MET** |

and **566 of 566 capture records byte-identical** to the sitting-8 record — which
THIS time is a real measurement, because the binaries genuinely differ.  It says
three things at once: **the `AD_OE` re-key IS exactly equivalent to the
`=== 1'bz` form** (sitting 8's claim is true; its proof was not), **the
sitting-11 IE-restore landing moved no HLT-sweep cell in either leg**, and **the
R7′ structural pass moved none either.**  So FLASH #5's fabric **146/283** is
still the BEFORE, **one flash and not two**, argued from a measurement.

### §73.8 **FLASH #6, AND THE FABRIC LEG — §56.3a's BOTH HALVES MET**

> ⚠ **ERRATUM — THIS HEADING AND §73.9's ARE OVERSTATED.  READ §73.9a BEFORE
> QUOTING EITHER.**  §56.3a registered **116 cells / 259 of 283**; what was
> executed is **119 cells / 265 of 283**.  The registered numerical bars were
> **SUPERSEDED** by F43, which landed at sitting 6 and moved the offline
> reference — they were not met, because they were no longer the bars.  The
> section's text is left exactly as it was written; the correction is beside it.

`gen_ucore_qsf --check` green FIRST, then the retention bitstream rebuilt from
that clean `.qsf` (Fmax 45.87, +8.802, TNS 0.000).  **FLASH #6** through
`sw/safe_flash.sh` with its VERIFY leg: `nec_test_ucore.sof`
**`626fb30ebee2ad979bdef5ba6e6c013281c901282cd28defc53501200de1ef46`**,
`.rbf` `460a71907f877e99092a2b985622ee24c70e09d645ae5f719c3da61c3e661878`,
VERIFY OK, `flash_log.jsonl` 8 → **9 entries**.

| | predicted (`sm3_s12_prereg` §7.1) | **MEASURED on FLASH #6** |
|---|---|---|
| first light, `check_ab_hw all 800`, three legs | MATCH 800 ×3 | **MATCH / MATCH / MATCH over 800 rows** |
| `x1_fabric baseline --leg fab_f6` | **265 / 283** | **265 / 283** |
| failing cells | 18 | **18** |
| the 119-cell INTA class | all CLOSED, 0 survivors | **119 closed, 0 survivors** |
| the survivors | the SAME 18, named in advance | **the same 18, and the same first-divergence coordinate on every one** |
| socket control, same driver, `use_core=False` | 49 / 49 | **49 / 49** |
| `use_core=0` chip proof, after everything | MATCH 800 | **MATCH over 800 rows** |
| transport errors | 0 | **0** |

Per suite, and it is the OFFLINE column cell for cell: `s10-w0` `HLT.INT`
**44/48** `HLT.RES` **47/49**; `s10-w1` **43/46** and **49/49**; `s13-w2`
**17/21** and **25/25**; `s13-w3` **15/20** and **25/25**.

**And scored strictly rather than by total** — every one of the 283 cells
compared between the fabric leg and the `tb_sys ret` leg:

* **0 PASS/FAIL disagreements**,
* **0 failing cells whose first-divergence coordinate differs**,
* the base-only class is **119**, and **119 of 119 pass in fabric**.

**BAR (i) MET.  BAR (ii) MET.  §56.3a's registered refutation — "any of the
class still failing, or any fabric-only NON-INTA divergence" — did not occur in
any cell.**

**THE RESTING BITSTREAM — FLASH #6 STAYS, AND THE DECISION IS TAKEN ON THE
MEASUREMENT AND NOT ON THE ARGUMENT.**  The argument is that the retention model
is applied to `hb_ad_sample` under `cfg_use_core ? core_ad_eff : NEC_AD`, so
with `use_core = 0` it is not in the observation path at all.  The measurement
is `sw/check_ab_hw.py chip 800` run AFTER the whole sitting: **chip-vs-golden
MATCH over 800 rows**, `use_core` **False**, `cfg 0xff0008` (`clk_div` 8,
`DIV_OF_RECORD`), `board_idle()` clean.  The socket-capture role — which is what
every golden in this project comes from — is therefore unaffected, and there is
no reason to spend a flash returning the board to a bitstream that scores 146
where this one scores 265.  **FLASH #5's `.sof` remains available under
`~/.cache/ucsimt-tmp/s8/flash5/` if a return is ever wanted.**

### §73.9 **C11 IS ESTABLISHED**

> ⚠ **ERRATUM — see §73.9a.**  C11 is established at the **MECHANISM** level.
> The sentence *"§56.3a's both halves are MET"* is literally false: the bars
> §56.3a registered were 116 and 259/283, and 119 and 265/283 were executed.

The reading §56.3 offered and §56.3a refused to promote without an intervention
— *at an INTA's T1 the chip's AD pads float and RETAIN the previous data phase,
and the 119 fabric-only HLT-sweep failures are that and nothing else* — is now
**a FINDING**.  The intervention was run **in fabric, on a bitstream that meets
every registered timing bar**, against a BEFORE established by measurement, with
the socket control at 49/49 and the chip path unmoved at 800 rows.

**THIS IS THE CODEX REVIEW ITEM `C11` in `ucore_campaign_verdict_2026-08-04.md`
§(g).  IT IS NOT `timed_lawcards`' `C11`**, which is the BIU law card *"LC4
`owns_slot` (enumerated)"* and remains `UNRESOLVED` on its own grounds — this
sitting did not touch it, and the two share a label and nothing else.

**WHAT REMAINS, STATED PLAINLY.**  The 18 survivors are NOT explained by this
and were never claimed to be: 4 `w0` `busstat` cells (the model-shared pair
§68.2 names, ×2 forms) and 14 `seg`/`bus` cells at the top of each sweep's `d`
band — §67.3's undiagnosed half.  They are core-owned and they are the next
HLT-sweep item.

### §73.9a **ERRATUM (SM3 sitting 13, Codex phase-review concern 3a) — C11's RECORD MISSTATES ITS BAR.  THE BARS WERE SUPERSEDED, NOT MET.**

Written beside §73.8/§73.9 rather than over them, per this project's standing
rule that deleting a true record corrupts a ledger exactly as badly as inventing
one.  **Nothing about the measurement is retracted.**  What is corrected is the
sentence that says a registered bar was met.

**THE ARITHMETIC.**

| | §56.3a REGISTERED (2026-08-04) | EXECUTED (§73.8, 2026-08-05) |
|---|---|---|
| the fabric-only class | **116 cells** | **119 cells** |
| the fabric total the intervention must reach | **259 / 283** | **265 / 283** |
| the offline reference it must EQUAL | 259 (the TB's, then) | 265 (the TB's, now) |

**WHY THEY DIFFER, AND WHY IT IS NOT A MOVED GOALPOST.**  **F43 landed at SM3
sitting 6**, between the registration and the execution, and it closed six
`busstat` cells offline (`standing_gates.md` §B, known-RED table: the four HLT
sweeps went **259 → 265** on the ucore).  §56.3a's bar is written as *"equal to
the TB's, not merely toward it"* — a RELATIVE bar with an absolute number
attached for convenience — and when the TB's number moved, the absolute number
in the text stopped naming the same claim.  **The relative form was met exactly;
the absolute form was superseded before it could be.**  This is transparent and
dated, not retrospective: F43's move is recorded in the gate document, in the
standing ratchet and in §67, all before FLASH #6 was built.

**WHAT IS ESTABLISHED, STATED AT THE LEVEL THE EVIDENCE SUPPORTS.**

> **C11 is ESTABLISHED at the MECHANISM level.**  The intervention closed
> **exactly** the base-only class — 119 of 119 — with **nothing else moving**:
> 0 PASS/FAIL disagreements and 0 differing first-divergence coordinates against
> the offline reference over all 283 cells on the same tree, the same 18
> survivors with the same coordinates, the socket control 49/49, and the
> `use_core=0` chip path MATCH over 800 rows.  §56.3a's registered
> **REFUTATION** — *"any of the class still failing, or any fabric-only NON-INTA
> divergence"* — did not occur in any cell.

**WHAT IS NOT ESTABLISHED BY THE NUMBERS AS WRITTEN.**  A claim of the form
*"the registered bar 259/283 was met"*.  It was not; a different and larger
number was reached against a reference that had moved for a documented and
unrelated reason.  Anyone re-deriving §56.3a's bar from its own text will get
116/259 and must be able to see, here, why the executed figures are 119/265.

**AND THE MECHANISM CLAIM ITSELF STILL RESTED ON A CROSS-BITSTREAM INFERENCE**
until SM3 sitting 13 ran the confound control §74.2 registers — FLASH #5 → #6
changed the macro *and* 90 lines of `v30u_eu.sv` *and* a whole fit.  The
disposition of C11 after that control is §74.2's, not this section's.

**Corrected in the same terms**: `standing_gates.md` §B (the fabric-HLT-sweeps
row) and `ucore_gaps_2026-08-04.md`.  **Concern 5 of the same review is cited
here as it was returned: NO ACTION — form 2 is confirmed** (§73.4's two
falsifiers are in the tree and silent over the whole ladder).

### §73.10 `fuzz_campaign lint` — **THE §72.7a NOT-RUN DEBT IS DISCHARGED, AND THERE WAS NEVER A HANG**

`python3 sw/fuzz_campaign.py lint` ran to completion:
**`LINT PASS: soup hits=0 compose_err=0; raw hits=0 compose_err=0`**, 10,000
soup + 100,000 raw seeds.

**The diagnosis is that it is silent, not stuck.**  `--report-every` defaults to
**0**, so nothing at all is printed until each phase ENDS, and the raw phase is
**100,000 seeds at ~69/s ≈ 25 minutes**.  §72.7a's *"State: S / do_wait at 0 %
CPU with an open socket on fd 10"* is the WRAPPER SHELL waiting on its Python
child, not the worker: measured here, the worker sits at **99.8 % CPU, STAT
`RN`**, for the whole run.  No instrument is needed and no defect exists; the
gate wants `--report-every 5000` on the command line, which is now written down.

### §73.11 WHAT MOVED, AND WHAT DID NOT

| | before | **after** |
|---|---|---|
| `v30u_eu.sv` block (a)'s data-edge PSW write | at the head of the 12-position chain | **on the `psw` register's `D` pin, gated `row_blocked`, with two falsifiers** |
| **control build Fmax** | **19.42 MHz (RED against a registered ≥ 32)** | **45.89 MHz** |
| retention build Fmax | 44.20 MHz | **45.87 MHz** |
| worst `c_ready_q` cone | 62–63 levels, 20,000 failing paths | **19 levels, 0 failing paths** |
| **R7′** | OPEN, aimed but unfixed | **CLOSED** |
| `x1_retention.BIN` / `build()` | named a file the compiler never wrote | **`Vtb_sys`, with a post-condition that exits on a mismatch** |
| the board's bitstream | FLASH #5 `315de4bc9e30…` | **FLASH #6 `626fb30ebee2…`, the retention build** |
| `flash_log.jsonl` | 8 entries | **9** |
| **the fabric HLT sweeps** | **146 / 283** | **265 / 283** |
| **C11** (the Codex review item) | NOT ESTABLISHED | **ESTABLISHED** |
| `fuzz_campaign lint` | BOOKED NOT RUN (§72.7a) | **PASS, and the "hang" explained** |
| every ratchet in `standing_gates.md` §B | — | **UNMOVED, and re-measured twice rather than inherited** |

### §73.12 WHAT THIS SITTING DID NOT DO

* **`nec_test.sdc` was NOT edited.**  §70.3's measurement — no CE collection can
  contain `c_ready_q` — still stands, and the fix was never an SDC one.
* **No latency was added** and no pipeline stage was inserted anywhere.
* **The 18 survivors were not investigated**; they are booked, not absorbed.
* **The b3 priority tranche was NOT re-captured on FLASH #6** — it was not in
  either pre-registration and a new leg pair belongs to whoever needs it.
* **No golden was re-emitted**, no comparator or scorer was changed, and
  nothing was re-scored downward.
* **No memory file was touched, Codex was not launched, and the 8080 /
  `gaps` §F.1 work was not opened** — a pending USER decision.

### §73.13 EVIDENCE

`docs/notes/sm3_s12_r7p/` — `cone.tcl` and four probe outputs (`CTRL_cone.txt`
and `RET_cone.txt` before the pass, `CTRL_cone_after.txt`/`RET_cone_after.txt`
for form 1, `RET_cone_form2.txt` for the landed form).  All six Quartus
netlists preserved whole under `~/.cache/ucsimt-tmp/sm3s12/{ctrl,ctrl_clean,ret,
ctrl_after,ret_after,ctrl_after2,ret_after2,flash6}/`, plus the two ladder
transcripts and the six per-seed `timed_fuzz` reports.  Fabric captures:
`sw/testdata/x1-retention/*.fab_f6.json.gz`, `*.soc_f6.json.gz`,
`score_fab_f6.json`, `score_soc_f6.json`.

### §73.14 THE LEADS THIS SITTING HANDS THE NEXT ONE

1. **THE STANDING GATE SET HAS NO QUARTUS LEG, AND THAT IS WHY G6 WENT RED
   UNSEEN.**  A ladder that never synthesises cannot see a 26 MHz regression
   introduced by a net deletion of five flops.  The cheapest honest fix is a
   `--core ucore` control build gated on Fmax and TNS, run at every RTL landing
   that touches `hdl/rtl/ucore/` — and it is the sixth instance of this file's
   own vacuous-gate pattern, this time by ABSENCE rather than by blindness.
2. **The 18 HLT-sweep survivors** — 4 `w0` `busstat` (model-shared) and 14
   `seg`/`bus` at the top of each `d` band (§67.3).  Now the ONLY fabric
   residue on this population, and the fabric and the TB agree on them cell for
   cell, so they are diagnosable entirely offline.
3. **The b3 priority tranche on FLASH #6** — a new `chip_f6`/`core_f6` leg pair
   beside `_f5`, board work, uncontroversial.
4. **H7's bank association** and **H3's steady-state prefetcher** (§68.10 leads
   2 and 3), both still board-free to open.

## §74 SESSION SM3, SITTING 13 — **THE CODEX PHASE REVIEW'S FIVE CONCERNS EXECUTED.  THE C11 CONFOUND CONTROL IS CLEAN, BOUNDARY QUANTISATION IS REFUTED AT FOUR SPACINGS, AND THE NEW QUARTUS GATE'S FIRST ACT IS TO REFUTE ITS OWN NON-VACUITY PREDICTION AND EXPOSE A 26 MHz BUILD-TO-BUILD SWING.**

**2026-08-05, branch `ucsim`, from HEAD `7debefcebd`.  A BOARD SITTING WITH
FLASHING AUTHORISED, AND TWO FLASHES WERE TAKEN.**  Pre-registration
`docs/notes/sm3_s13_prereg_2026-08-05.md` at **`d687a36f0c`**, committed
**before the first board contact and before either engine was touched** —
`git diff` against `sim/` and `hdl/rtl/` is EMPTY at that commit and **NO ENGINE
WAS TOUCHED AT ANY POINT IN THIS SITTING**.  Single writer confirmed before
contact (`0 users`, no serve process on `mister-nec`); `div_guard` **PINNED** on
every probe; `use_core` **False** as found and **False** as left, verified;
**0 transport errors in the whole sitting**; `flash_log.jsonl` **9 → 11
entries**.

> **Standing principle, applied throughout.**  *"A guiding principal here needs
> to be simplicity.  This is 80's era hardware, they aren't wasting silicon on
> anything that isn't necessary.  Complex or confusing behavior that we see is
> likely to be simple systems interacting in ways you do not fully understand
> yet."*

**THE ONE-LINE RESULT.**  Concerns 3(a) and 4(a) are corrected in place with
errata (§73.9a, §72.7b); concern 3(b)'s control puts the macro-OFF bitstream
back on the board **inside one session, on one tree, through one fit flow**, and
it reproduces **146/283 with the same 119-cell class and the same 18 survivors
at identical coordinates — the FLASH #5 → #6 inference carries no RTL or fit
confound**; concern 4(b)'s cell shows the **first boundary after an IE rise is
free at 2, 3, 13 and 24 clocks, at ZERO cost against a no-rise control**, which
**REFUTES boundary quantisation** and leaves §72.7's rendering standing; and
concern 2's gate is built, is PASS at HEAD, is proved RED on a real preserved
artifact — **and its registered non-vacuity prediction FAILED, which is how the
26 MHz build-to-build swing of §74.4 was found.**

### §74.1 CONCERN 3(a) AND 4(a) — THE TWO WORDING CORRECTIONS

Both taken erratum-style, original text preserved with a marker beside it,
because deleting a true record corrupts a ledger exactly as badly as inventing
one.

* **§73.9a** — C11's registered bars were **116 cells / 259 of 283**; what ran
  is **119 / 265 of 283**, because F43 landed at sitting 6 and moved the offline
  reference the bar is written RELATIVE to.  **The bars were SUPERSEDED, not
  met.**  C11 is established at the **MECHANISM** level, on the ground that
  §56.3a's registered REFUTATION did not occur in any cell.  Corrected in the
  same terms in `standing_gates.md` §B and `ucore_gaps_2026-08-04.md`.
* **§72.7b** — what sitting 11 established is IE gating, maskability, a floor of
  at least one boundary and a +2 minimum.  What §72.7's wording ASSUMES is that
  the floor is a count of CLOCKS.  The landed RTL is `int_p[2] && ie_p[2] &&
  psw[FIE]` — a pipelined LEVEL test with no counter in it — and both
  renderings were named with the question booked OPEN pending §74.3.
* **Concern 5** is cited as it was returned: **NO ACTION, form 2 confirmed.**
  §73.4's two falsifiers are in the tree and silent over the whole ladder.

### §74.2 CONCERN 3(b) — **THE CONFOUND CONTROL, AND IT IS CLEAN**

FLASH #7 is the CONTROL build (`X1_AD_RETENTION` **OFF**) produced by
`sw/quartus_gate.py` at HEAD — the same build that is concern 2's PASS proof —
`nec_test_ucore.sof` **`b29c35df24de0cb5bfa3fb9249997da726884cbf99afe3a685db8369c7e5e142`**,
`.rbf` `44f17467ebd636ad9972d4a12ca6c72d19605da111749c3d7455417e3ce6777a`.
FLASH #8 is the restore of **`626fb30ebee2…`**.  Both through `sw/safe_flash.sh`
with its VERIFY leg.  Sitting 12's `ctrl_after2` was NOT reused: it predates
`c7198e210f`, so its fit record is not current for HEAD.

| # | registered | **measured on FLASH #7** |
|---|---|---|
| **C1** | **146 / 283** | **146 / 283 — exact** |
| **C2** | the base-only class is exactly **119**, the SAME names | **119**, and `fabric base-only class == offline base-only class` is **True**; **119 / 119** have an **INTA** first-divergence row, read off the GOLDEN's bus status and not off a name |
| **C3** | first-divergence **row AND column** identical to the offline `tb_sys base` record | ⚠ **MISSED — see below** |
| **C4** | the SAME **18** survivors, same coordinates | **18**, and **0** whose coordinate moved |
| **C5** | socket control **49 / 49** | **49 / 49** |
| **C6** | FLASH #8 first light MATCH ×3 over 800 rows | **MATCH / MATCH / MATCH** |
| **C7** | 0 transport errors | **0** |

**AND THE PAIR THAT MATTERS IS `fab_f7` vs `fab_f8` — ONE TREE, ONE FIT FLOW,
ONE BOARD SESSION, THE MACRO AND NOTHING ELSE:** 146/283 → 265/283, **119
closed, 0 survivors, 0 of the 18 moved**, all 119 INTA.  `fab_f8` is
**cell-for-cell identical to `fab_f6`** — the same bitstream, two flashes apart —
which is the control that says the board and the rig did not drift across the
session.  **The FLASH #5 → #6 inference contains no RTL or fit confound, and
§73.9a's mechanism-level C11 is now supported by an intervention that varies ONE
INPUT.**

**C3 IS MISSED, AND IT IS REPORTED AS REGISTERED RATHER THAN RESTATED.**  On all
**119** cells the fabric's first divergence is **exactly one row LATER** than the
offline `tb_sys base` record's — `(+1, same column)` on 119 of 119, column `bus`
in every case, and the golden's bus status is **INTA at BOTH coordinates**.  The
18 survivors are at delta **0**, in this comparison and in `fab_f6` vs the
offline `ret` leg alike, so the shift is confined to the class.  What is
therefore established is that **the failing SET is identical between fabric and
the offline base leg — 137 = 137, cell for cell, 0 either-only** — and that the
two disagree by one row on WHERE inside the same INTA cycle the divergence first
shows.  The natural reading is that Verilator's resolution of the internal
tri-state and Quartus's mux resolution of it differ on the first affected row;
**it is NOT diagnosed here, it is booked**, and it is a lead for whoever next
touches `tb_sys`.

### §74.3 CONCERN 4(b) — **THE DISCRIMINATING CELL.  BOUNDARY QUANTISATION IS REFUTED AT FOUR SPACINGS.**

`sw/sm3_h1_cell.py run --out sm3-s13cell`, **3,840 captures**, socket only
(`EMIT_USE_CORE` False and the module refuses to load otherwise), `div_guard`
**PINNED** (`div=8 (4 MHz), commanded by this connection`), **`fired = True` on
all 3,840**, 0 transport errors, 429 s, full per-clock rows + raw 64-bit words +
**7,682 files under `SHA256SUMS`**, `board_idle()` run and OK.

Ten sleds in matched pairs — `pad<k>` = `CLI ; POPF ; PAD<k> ; NOP ; NOP` (IE
RISES at the POPF) and `hot<k>` = `POPF ; PAD<k> ; NOP ; NOP ; NOP` (IE already
up, popped word up: **NO RISE**, the control) — with `PAD<k>` chosen for CLOCK
LENGTH and nothing else.  **THE READER WAS VALIDATED ON RETAINED SILICON BEFORE
ANY NEW CAPTURE**: over `sw/testdata/sm3-s11cell/` it reproduces §72.3 exactly
(`iepop` pin 0 w0 **OWN 0, DEAD 0, B1 18, B2 6**; pin 1 **OWN 9**).

**THE RESULT, pin 0, w0, 48 delays per cell:**

| pad | `L_pad` on the NO-RISE control | `pad*` **B1** | `pad*` OWN | `pad*` DEAD | `min(ann−pop)` at B1: rise / no-rise |
|---|---|---|---|---|---|
| `CLD` | **2 clocks** | **30 / 48** | 0 | 0 | **10 / 10** |
| `NOP` | 3 | **31 / 48** | 0 | 0 | **11 / 11** |
| `XCHG AW,BW` | 3 | **31 / 48** | 0 | 0 | **11 / 11** |
| `ROL AL,CL` (CL=3) | **13** | **36 / 48** | 0 | 0 | **21 / 21** |
| `MUL BL` | **24** | **42 / 48** | 0 | 0 | **32 / 32** |

`L_pad := min(ann−pop | B1) − min(ann−pop | OWN)`, both on the control, where
`ann−pop` is the clocks from the POPF's own stack read (IE's commit, on the
pins) to the entry's announcement — §72.3's own coordinate.

**READ IT.**  The FIRST boundary after the rise is TAKEN at spacings of **2, 3,
13 and 24 clocks**, and at a `min(ann−pop)` **IDENTICAL to the no-rise
control's** in every case — i.e. **at ZERO cost.**  A sampler that rejects the
first boundary after the rise, whatever its distance, would have refused all
four and pushed every entry to B2.  **BOUNDARY QUANTISATION IS REFUTED.**

**WHAT IS REFUSED IS EXACTLY TWO THINGS, ON ALL FIVE GEOMETRIES:** the rise's
**OWN** boundary (spacing 0) — **0 of 48 on every pad** — and the boundary at
which IE is **CLEAR** — **0 of 48 on every pad**.  So the floor is a small
CLOCK/level quantity, not a boundary count, and this cell bounds it: **strictly
greater than 0 and at most 2**, because `CLD`'s B1 sits 2 clocks out and is free.
§72.7's *"two clocks"* is **the upper end of that interval and it survives**;
what §72.7b booked as OPEN is now closed in §72.7's favour.

**THE CONTROLS.**  **P1** (`hot<k>` B1 ≥ 1): 4 · 7 · 7 · 24 · 31 ✓.  **P1b**
(`hot<k>` OWN ≥ 1 — the geometry control the pre-registration wrote in because
the engine baseline exposed the risk): **17 · 17 · 17 · 8 · 8 ✓** — the 48-delay
sweep reaches the OWN window on every pad, which sitting 11's 24-delay sweep
would not have on the long ones, so **P2 is scored on all five**.  **P4**
(`L_pad(mul) ≥ 8`): **24 ✓**.  **P6** (NMI, pin 1, `pad<k>` OWN ≥ 1): **18 · 19
· 18 · 8 · 8 ✓** — the non-maskable recognition takes the rise's own boundary
freely on every geometry, so maskability is reproduced on a sled set that did
not exist when §72.7 was written.

**P7 — THE ENGINE, AND IT IS EXACT.**  `sm3_h1_cell.py s13-engine --core ucore
--wait 0 --hold 300`: the ucore is handed the identical images and the identical
`(anchor, delay, hold, pin)` and **PREDICTS** the boundary; scored cell for cell
over all **960** w0 captures it is **AGREE 960 / 960, DIFFER 0**, with its own
histograms and its own `min(ann−pop)` values identical to the chip's on every
leg — **on a geometry it was never fitted to, including a 24-clock pad.**  The
registered outcome is MET and there is **no registered failure to report on this
concern.**  The `sim` leg is structurally vacuous on this observable (§4.3 of the
sitting-11 pre-registration) and was not scored.

**WHAT THIS CELL CANNOT DO, AS REGISTERED IN ADVANCE**: separate a 1-clock floor
from a 2-clock one.  No instruction retires in one clock, so no boundary exists
at spacing 1, and the announcement offset jitters by ±1 across labels.  **The
question it answers is CLOCKS vs BOUNDARIES**, and no number should be taken out
of it that it did not carry.

### §74.4 CONCERN 2 — **THE STANDING QUARTUS GATE, AND ITS FIRST ACT IS TO REFUTE ITS OWN REGISTERED PREDICTION**

`sw/quartus_gate.py` is built to the review's design and written up in
`standing_gates.md` §A: `gen_ucore_qsf --check` (E1, before the build, because
Quartus rewrites the .qsf it compiles), one clean CONTROL/DEFAULT build from a
deleted `db`, and only the registered G6 essentials as bars — 0 errors (E2),
`divclk` Fmax ≥ 32 MHz (E3), worst setup > 0 (E4), TNS 0.000 setup AND hold
(E5).  Resources are RECORDED, never gated.  The receipt is
`artifact_receipt_layer.md` §3's schema.

**Q1 — PASS AT HEAD, and the registered BAND is MISSED.**  `verdict PASS`;
E2 0 errors, E3 **43.59 MHz**, E4 **+8.308**, E5 clean, ALMs 11,126 (27 %),
latches 0, `lpm_divide` 0, 524 s.  The pre-registration wrote the band as
**45.5 – 46.2 MHz** (sitting 12's 45.89) and **43.59 is below it.**  Reported as
registered.  The GATE passes — its bar is ≥ 32, deliberately, and that is why.

**Q2 — REGISTERED FAILURE.**  Registered: *the gate goes RED on a worktree of
`144e67416b`, reproducing §73.1's 19.42 MHz.*  **It came back
`Fmax 45.91 MHz / +6.489 / TNS 0.000 / PASS`, 534 s.**  The 19.42 MHz state
**did not reproduce at the commit where it was measured.**  Not restated, not
re-run for a better draw.

**NON-VACUITY IS PROVED ANOTHER WAY, ON A REAL ARTIFACT.**  The 19.42 MHz report
set itself is retained under §73.13 (`~/.cache/ucsimt-tmp/sm3s12/ctrl_clean/`).
Gated with `--parse-only --tree`, `quartus_gate.py` **exits 1** and goes **RED at
E3 (19.42), E4 (−20.254) and E5 (TNS −13,129.815)** with E2 still green.  The
scoring is non-vacuous on precisely the state it was built to catch — proved on
the historical artifact rather than by fishing for a re-draw, which would have
been choosing a run after seeing the result.

**AND HERE IS WHAT Q2 ACTUALLY FOUND.**  The receipts' input manifests differ in
**exactly one file** — `rtl/ucore/v30u_eu.sv`, the R7′ form-2 change — which is
`artifact_receipt_layer.md` §5's delta manifest doing its job on its first day.
Four CONTROL builds of those two trees:

| tree | the `.qsf` the build actually read | **`divclk` Fmax** | worst setup |
|---|---|---|---|
| `144e67416b` (pre-form-2) | **materialised** (sitting 12) | **19.42** | −20.254 |
| `144e67416b` (pre-form-2) | **generated** (sitting 13) | **45.91** | +6.489 |
| form 2 / HEAD | **materialised** (sitting 12) | **45.89** | +8.493 |
| form 2 / HEAD | **generated** (sitting 13) | **43.59** | +8.308 |

**THE DEFAULT BUILD'S Fmax IS NOT A FUNCTION OF THE RTL ALONE.**  §73.1's
*"reproduced to the digit from a DELETED `db`"* established that ONE DRAW
repeats, not that the outcome is determined; and on the generated `.qsf` the
pre-form-2 tree is **faster** than HEAD.  Two consequences, both booked:

1. **§73's R7′ before/after may not be quoted as "19.42 → 45.89".**  What is NOT
   retracted is the STRUCTURAL result, which is independent of any Fmax draw:
   the `c_ready_q` cone went from **62–63 logic levels to 19**, measured on the
   netlist, with 0 failing paths and zero ladder delta.  That is why R7′ stays
   CLOSED.  What is retracted is the reading that the pre-form-2 tree *is* a
   19.42 MHz tree.
2. **A single green Quartus build does not establish closure on this design**,
   and the gate must not be quoted as if it did.  Its value is that it makes a
   26 MHz swing VISIBLE at the landing instead of three sittings later.  A
   multi-seed form (`--seed`, N fits, gate the WORST) is the obvious next
   version and is **NOT** built here.

### §74.4a **THE MECHANISM OF THE SWING, MEASURED — ANALYSIS & SYNTHESIS ITSELF IS NOT REPRODUCIBLE, AND `.qsf` MATERIALISATION IS REFUTED AS THE CAUSE**

Post-hoc and EXPLORATORY — generated after seeing §74.4's result, labelled as
such, and carrying no registered outcome.  Two candidate causes were named and
one was tested directly.

**CANDIDATE 1, `.qsf` MATERIALISATION — REFUTED.**  Sitting 12's builds all read
a `.qsf` Quartus had rewritten with ~180 sourced assignments appended (§70.7);
sitting 13's read the generated one, because `c7198e210f` had un-materialised it.
`144e67416b` was therefore rebuilt a THIRD time, with the materialised `.qsf`
restored byte for byte from `c7198e210f^`.  Result: **Fmax 45.91 MHz, worst
setup +6.489, ALMs 11,148 — identical to the generated-`.qsf` build to the
digit.**  The `.qsf` variant does not move this build.

**CANDIDATE 2, THE FLOW'S OWN REPRODUCIBILITY — CONFIRMED, AND IT IS UPSTREAM OF
THE FITTER.**  Analysis & Synthesis reports, four CONTROL builds:

| build | Fmax | `v30u_eu` REG | `v30u_biu` REG | `v30_core` REG | **`v30u_eu` ALUT** | `v30u_biu` ALUT |
|---|---|---|---|---|---|---|
| s12 `ctrl_clean`, `144e67416b` | **19.42** | 675 | 402 | 1077 | **10,686** | 834 |
| s13 `wt144`, `144e67416b` | **45.91** | 675 | 402 | 1077 | **10,711** | 830 |
| s12 `ctrl_after2`, form 2 | 45.89 | 675 | 402 | 1077 | 10,756 | 795 |
| s13 `flash7`, form 2 / HEAD | 43.59 | 675 | 402 | 1077 | 10,773 | 793 |

**READ THE TWO HALVES SEPARATELY.**

* **The REGISTER counts are IDENTICAL in all four** — `v30u_eu` **675**,
  `v30u_biu` **402**, `v30_core` **1077** — which is §73.6's "AND NO FLOP MOVED"
  reproduced across a further sitting and two more builds.  **That claim stands
  entirely.**  It also proves the two `144e67416b` builds really are of that
  tree: sitting 12's `ctrl_clean` and sitting 13's `wt144` synthesise the same
  flop set, and the form-2 pair its own.  **The 19.42 measurement was of the
  tree it was labelled with.**
* **The COMBINATIONAL counts differ between every pair, INCLUDING the two builds
  of the SAME COMMIT from a deleted `db`**: `v30u_eu` **10,686 vs 10,711**,
  `v30u_biu` **834 vs 830**.  **Analysis & Synthesis is not reproducible run to
  run on this flow.**  A different netlist is a different fitter problem, and on
  a design whose critical path sits on a cliff — which is what §70.5 predicted
  and §73.2 located — a ~25-ALUT difference in the EU is enough to decide
  whether the long path gets broken.

**SO THE SWING IS NOT "FITTER LUCK" IN THE LOOSE SENSE; IT IS A MEASURED
UPSTREAM NON-DETERMINISM WITH A MEASURED DOWNSTREAM CLIFF.**  Simplicity, applied
to the tooling: two simple systems interacting — a synthesiser that does not
repeat itself exactly, and a path that is marginal — and the confusing behaviour
is their product, not a third thing.

**WHAT THIS DOES AND DOES NOT LICENCE.**  It does NOT licence re-running a build
until it passes; that is choosing a run after seeing the result, and the gate
must be quoted on the run it was given.  It DOES mean a single build is a SAMPLE,
and §74.8 lead 1's multi-seed form is the fix.  **Every timing figure in this
ledger from §52 onward is one sample of a distribution nobody has characterised.**

### §74.5 WHAT MOVED, AND WHAT DID NOT

| | before | **after** |
|---|---|---|
| C11's record | "§56.3a's both halves are MET" | **ESTABLISHED AT THE MECHANISM LEVEL, bars SUPERSEDED not met** (§73.9a) |
| the C11 attribution's evidence | a cross-bitstream inference (macro + 90 lines of RTL + a whole fit) | **an intervention varying ONE INPUT, in one board session** (§74.2) |
| §72.7's "two clocks" | asserted as the mechanism | **a MEASURED interval `(0, 2]`, with boundary quantisation REFUTED at four spacings** (§72.7b, §74.3) |
| the standing gate set's Quartus leg | **ABSENT** — §73.14 lead 1 | **`sw/quartus_gate.py`, triggered, with a receipt** (`standing_gates.md` §A) |
| the DEFAULT build's Fmax | quoted as a property of the tree | **NOT a function of the RTL alone: 19.42 and 45.91 from one commit** (§74.4) |
| the board's bitstream | FLASH #6 `626fb30ebee2…` | **FLASH #8, the SAME `626fb30ebee2…`** — #7 was the control and it was taken back off |
| `flash_log.jsonl` | 9 entries | **11** |
| the fabric HLT sweeps, macro OFF | 146/283 on FLASH #5 (a different tree) | **146/283 on FLASH #7, THIS tree** |
| the fabric HLT sweeps, macro ON | 265/283 on FLASH #6 | **265/283 on FLASH #8, cell for cell identical** |

**UNMOVED, AND DELIBERATELY**: every ratchet in `standing_gates.md` §B. **NO
ENGINE WAS TOUCHED** — `sim/` and `hdl/rtl/` are byte-identical to `7debefcebd`
at the close of this sitting, so no ladder gate can have moved and none is
re-claimed.  The only tree changes are instruments (`sw/sm3_h1_cell.py`,
`sw/quartus_gate.py`), documents, and retained captures.

### §74.6 WHAT THIS SITTING DID NOT DO

* **The artifact/receipt layer was SPEC'd and NOT BUILT** — concern 1, routed to
  its own sitting.  `docs/notes/artifact_receipt_layer.md`, with the receipt
  schema, atomic build-and-promote, the A/B delta manifest, the layer's own
  non-vacuity proof and a migration order costed against the seven recorded
  incarnations of the identity bug.  `quartus_gate.py`'s receipt is written to
  that schema and is its first instance.
* **The 18 HLT survivors were not investigated**; they are booked, not absorbed.
* **The multi-seed form of the Quartus gate was not built** (§74.4 consequence 2).
* **§74.2's one-row C3 shift was not diagnosed**, only measured and bounded.
* No Codex launch, no memory file touched, no 8080 / `gaps` §F.1, no comparator
  or golden or scorer changed, nothing re-scored downward.

### §74.7 EVIDENCE

* Pre-registration `docs/notes/sm3_s13_prereg_2026-08-05.md` at `d687a36f0c`.
* The cell: `sw/testdata/sm3-s13cell/` — 3,840 captures, `manifest.json`,
  `cells.json`, per-clock rows + raw 64-bit words, **7,682 files under
  `SHA256SUMS`**, and `s13_engine_ucore_w0.json` (the 960/960).
* The fabric legs: `sw/testdata/x1-retention/*.fab_f7.json.gz`,
  `*.soc_f7.json.gz`, `*.fab_f8.json.gz`, `score_fab_f7.json`,
  `score_soc_f7.json`, `score_fab_f8.json`, plus `score_base.json` /
  `score_ret.json` (the offline legs re-scored on `x1_fabric`'s OWN comparator so
  the fabric and offline columns are on one scale).
* The gate receipts, under `~/.cache/ucsimt-tmp/sm3s13/`:
  `receipt_head.json` (Q1, PASS 43.59), `receipt_144e6741.json` (Q2, PASS 45.91
  — the registered failure), `receipt_s12_ctrl_clean.json` (the non-vacuity
  proof, RED at E3/E4/E5), with the four build transcripts beside them.  The
  FLASH #7 output tree is preserved whole at `~/.cache/ucsimt-tmp/sm3s13/flash7/`
  and FLASH #6/#8's at `flash6_outdir_backup/`.

### §74.8 THE LEADS THIS SITTING HANDS THE NEXT ONE

1. **THE BUILD-TO-BUILD Fmax SWING (§74.4) IS THE BIGGEST OPEN ITEM.**  A design
   that draws 19.42 or 45.91 MHz from one commit is not closed by any single
   build, and every timing figure in this ledger from §52 onward is one draw.
   The cheap first move is `quartus_gate.py --seed N` gating the WORST of N
   fits; the honest second is to find what the long path actually is when the
   fitter loses it, since §73.2's elimination was done on a losing draw.
2. **The one-row C3 shift (§74.2)** — fabric vs `tb_sys base`, +1 on all 119,
   same column, INTA at both coordinates.  Entirely offline to diagnose.
3. **The 18 HLT-sweep survivors** — unchanged from §73.14 lead 2, and now
   measured identical on FLASH #7 and #8 as well.
4. **The IE floor's exact size** is bounded to `(0, 2]` clocks by §74.3 and is
   not resolvable on this instrument.  It needs a boundary at spacing 1, which
   needs an instruction that retires in one clock — if one exists.
5. **The b3 priority tranche on FLASH #6/#8** — still not re-captured
   (§73.14 lead 3), still uncontroversial.

## §75 SESSION SM3, SITTING 14 — **THE SHARED ARTIFACT / RECEIPT LAYER IS BUILT, IT REJECTS 45 THINGS IT MUST REJECT, AND THE FIRST TRANCHE OF GATES IS MIGRATED WITH ZERO NUMBERS MOVED — BECAUSE EVERY BINARY IN THE TREE WAS ALREADY THE RIGHT ONE AND IT IS NOW POSSIBLE TO SAY SO**

`docs/notes/artifact_receipt_layer.md` was written at sitting 13 as a SPEC with
an explicit instruction not to build it.  This sitting built it, migrated the
first tranche, and re-ran every migrated gate at its standing figure.  The spec
document is UNEDITED except for a status banner and **four ERRATUM boxes beside
the sections the implementation deviates from** — E-1 and E-2 at §3, E-3 at §4,
E-4 at §7.  Nothing deviates silently.

**No engine changed.**  `git diff -- hdl/rtl sim` is EMPTY.  No board was
touched.  No bitstream was built (`quartus_gate` was exercised `--parse-only`
against the tree already on disk).

### §75.1 WHAT IT IS — three files, and it is a postcondition and a hash

| file | lines | what it is |
|---|---|---|
| `sw/artifact.py` | 559 | `Recipe` / `build` / `require` / `ensure` / `diff_receipts` |
| `sw/receipt_diff.py` | 127 | §5's A/B delta manifest, as a command |
| `sw/test_artifact.py` | 359 | §6's non-vacuity proof, as a runnable gate |

Three entry points and no more:

* **`build(recipe)`** — the PRODUCER.  Content-keyed, builds into a staging
  directory, asserts every DECLARED output was written by THIS command, hashes,
  writes the receipt, promotes.
* **`require(artifact)`** — the SCORER POSTCONDITION.  Re-hashes the receipt's
  declared inputs AND outputs from the tree, re-probes the tool version, and
  raises `ArtifactError` with both hashes in it.  **It needs no `Recipe`** — the
  receipt is self-describing, so any tool anywhere can assert it on any path it
  is about to execute.  **It does not rebuild** (§8): an automatic rebuild here
  is how incarnation 2 stayed invisible for six days.
* **`ensure(recipe)`** — build-if-needed then require.  What a gate calls.

**The build key is CONTENT, not mtime**:
`build_key = sha256(inputs.sha256 | tool | command | env)`, and a build is
skipped only if the key matches AND every declared output still hashes to what
the receipt says.  Touching a file without changing it does not rebuild;
reverting a file to an already-built state does not rebuild; upgrading Verilator
does.  **Every freshness check this tree had before today compared mtimes, and
mtime is exactly what incarnation 2 defeated** — the compiler wrote a different
file, so the file the scorer opened kept an old mtime, and an old mtime is
indistinguishable from "up to date" when nothing forces the comparison.

The receipt is `artifact_receipt_layer.md` §3's schema, written **atomically
beside the artifact** as `<artifact>.receipt.json` and **appended to
`sw/testdata/receipts/<kind>.jsonl`** — which matters because `hdl/tb/.gitignore`
ignores `obj_dir*/`, so a receipt that lived only beside its binary would be a
history of exactly one entry that no clone ever sees.

### §75.2 THE SEVEN INCARNATIONS, AND WHICH ONE EACH MECHANISM CLOSES

| # | where | what the layer does about it |
|---|---|---|
| 1 | §67.6 | `x1_retention` had no `build()`.  `capture` now calls `build()` which ends in `require()`; a receipt-less binary is a hard error |
| 2 | §73.7 | compiler wrote `Vtb_sys`, scorer opened `tb_sys`.  **`outputs` is DECLARED**, and `build()` stats the staging directory: a command that writes another name ABORTS and promotes nothing.  From the other side, `tb_sys` has no receipt, so `require()` refuses it |
| 3 | `standing_gates.md` §C | `check_seq` never called `check_core.build()`.  `check_seq.run_tb` now resolves through `tb_bin()`, which is `ensure(check_core.recipe("fsm"))` — and `check_fuzz_bank`, `check_mod3_illegal` and `check_enter_nesting` all reach the TB through `run_tb`, so **all four inherit the fix at once** |
| 4 | §73.1 | no Quartus leg existed.  `quartus_gate` closed that at s13; this sitting put its receipt on the shared writer, with hashed `outputs` and a `.jsonl` history that survives the gate's own next clean build |
| 5 | `CLAUDE.md` | `s15_census` ran the model against a ucore report.  **NOT closed by this layer** — it is an engine-selection bug, not an artifact-identity one, and it was already fixed by gap R4.  Named here so the list stays honest |
| 6 | §72.7a | a gate whose liveness nobody could read.  **NOT closed** — `--report-every` is the fix and it is already written down |
| 7 | INV-1 | a capture whose conditions were not part of its identity.  **NOT closed** — that is spec §7 step 6, the golden suites, and it is its own project |

**Four of seven have a mechanism now.  Three do not, and two of those three are
not this layer's kind of bug.**

### §75.3 THE LAYER'S OWN NON-VACUITY PROOF — `sw/test_artifact.py`, **45/45**

> *"A receipt layer that has never rejected anything is incarnation 8."*
> — the spec, §6

It runs entirely inside a throw-away directory outside the repo, builds nothing
real, and needs no tool but `python3`.  **It makes the layer fail, on purpose,
in every way it is supposed to fail:**

| | it must | and it does |
|---|---|---|
| MUTATION (a) | perturb one byte of one DECLARED input → the **SCORER** refuses, naming the file and BOTH hashes | `STALE` |
| MUTATION (b) | perturb a genuinely IRRELEVANT file → the scorer **RUNS**, and no rebuild is triggered | a producer that HASHES THE WORLD fails here |
| STALE | restore a known-old binary under the current name → refuse | **on `hdl/tb/obj_dir_sys/tb_sys.stale-s6`, the real artifact a real scorer really ran for six days** (§73.7).  The spec named this fixture; the test uses it |
| NO RECEIPT | an artifact the layer never built → refuse | `NO RECEIPT` |
| ABSENT | nothing at the path → refuse | `ARTIFACT ABSENT` |
| WRONG NAME | command writes `Vout.bin`, recipe declares `out.bin` → **build ABORTS**, names what the command DID write, and **the previous artifact and its receipt survive byte-identical** | incarnations 2 and 7, as a unit test |
| rc != 0 | abort, promote nothing | ✓ |
| MISSING INPUT | a declared input that does not exist → abort | ✓ |
| TOOL | a receipt built by a different tool version → refuse | erratum E-2 |
| CONTENT KEY | `utime` an input without changing it → **do NOT rebuild**, id unmoved | ✓ |
| §5 | identical inputs + differing command → command delta reported, `receipt_diff` exits **1** without `--expect-command` and **0** with it; a one-file input delta reports exactly one file | ✓ |

`python3 sw/test_artifact.py` → **45/45 checks pass**, exit 0.

### §75.4 THE MEASUREMENT THAT MADE THE MIGRATION SAFE — **VERILATOR IS BYTE-REPRODUCIBLE HERE, AND EVERY BINARY IN THE TREE WAS ALREADY CURRENT**

A migration that rebuilds every binary in the ladder is a migration that can
move every number in the ladder.  So this was MEASURED before anything was
migrated, by rebuilding each binary into a scratch `-Mdir` outside the repo and
comparing sha256 against what was on disk:

| binary | on disk (pre-migration) | fresh scratch rebuild |
|---|---|---|
| `obj_dir/Vtb_v30_core` (fsm) | `49dbd7f5d7b28144…` | **identical** |
| `obj_dir_ucore/Vtb_v30_core` | `ac57c4dfbca764ca…` | **identical** |
| `obj_dir_sys/Vtb_sys` | `d82741c7bdea1cd1…` | **identical** |
| `obj_dir_sys_ret/Vtb_sys` | `712b1a8454469a96…` | **identical** |

Two facts fall out, and both are load-bearing:

1. **Verilator 5.032 is byte-reproducible on this tree**, including across
   different `-Mdir` locations.  So a rebuild through the layer produces the
   same bytes by construction, and the migration **cannot** move a number
   through a rebuild.
2. **Nothing in the tree was stale at HEAD.**  §C's standing warning
   ("rebuild the FSM TB before quoting `check_fuzz_bank`") was true when it was
   written and is not true today — but *the only reason anyone can say so is
   that it was just measured*, which is the entire argument for the layer.

Re-hashed after every migrated build, all **six** artifacts are byte-identical
to their pre-migration selves:

| receipt | id | inputs | output sha256 |
|---|---|---|---|
| `tb_v30_core/ucore` | `6babd479d1ce5c92…` | 18 | `ac57c4dfbca764ca…` |
| `tb_v30_core/fsm` | `88d42f2d77aadf6d…` | 7 | `49dbd7f5d7b28144…` |
| `tb_ab/ucore` | `38f3d77a8ee18143…` | 25 | `abef13e787739f7d…` |
| `tb_ab/fsm` | `98d5aa90def0dc0f…` | 14 | `928ce77107c7bd33…` |
| `tb_sys/base` | `a6a88b1c779e0c26…` | 25 | `d82741c7bdea1cd1…` |
| `tb_sys/ret` | `c957bf54d9e702d2…` | 25 | `712b1a8454469a96…` |

### §75.5 THE MIGRATION TABLE — every migrated gate re-run at its standing figure

**The bar was: the migration must not move a number.  It did not move one.**

| gate | how it now binds | re-run figure | standing figure |
|---|---|---|---|
| `check_core.py --opcodes all --cases 0` | `ensure(recipe(core))` — **the single declaration**; `build()` is `ensure` | **169,000 / 169,000** (cycles AND arch) | 169,000 / 169,000 ✓ |
| `ulockstep.py --golden all --cases 50` | `require(UBIN)` (was `if not UBIN.exists()`) | **17,350 / 17,350** ALL CASES LOCKSTEP | 17,350 / 17,350 ✓ |
| `check_ab_sim.py` (ucore) | `ensure(recipe(core))` | **MATCH over 187 rows** | 187 ✓ |
| `check_ab_sim.py --core fsm` | same | **MATCH over 187 rows** | 187 ✓ |
| `check_core.py --core fsm --opcodes all --cases 0` (ARCHIVED leg) | `ensure(recipe("fsm"))` | **168,400 / 169,000** (cycles; arch 169,000) | 168,400 / 169,000 ✓ — `CLAUDE.md`'s corrected-comparator figure, to the case |
| `timed_fuzz.py --core ucore --evt-replay` | `require(tb_bin)` | **REGISTERED 1,490/1,702 · EVT 912/1,008 · COMBINED 2,402/2,710 · BOUND WARNINGS 5 · ENGINE ABORTS 0** | identical, to the seed ✓ |
| `timed_fuzz.py --core ucore --seeddir …/b2-tranche/seeds` | same | **172 / 188** | 172 / 188 ✓ |
| `check_boot.py 220` / `400` (RTL leg) | `require` in `_bin()` | **MATCH / MATCH** | MATCH ✓ |
| `timed_wvec_gate.py --core ucore` | `require` in `tb_bin()` | **88 / 88, bus cycles 16,048 vs 16,048, +0.0 %** | 88/88 +0.0 % ✓ |
| `timed_enter_replay.py --core ucore` | `require` in `tb_bootrun.tb_bin()` | **154/154 ×5** (pushes, walk, full, active, halt_display) | 154/154 ×5 ✓ |
| `timed_ins_replay.py --core ucore --raw` | same choke point | **rails 1,312/1,312 · vs-chip 2,624/2,624** | 1,312 / 2,624 ✓ |
| `x1_retention.py score` | `build()` = `ensure(recipe(leg))`; the hand-rolled §73.7 falsifier DELETED | **offline 265/283 · base 146/283 · ret 265/283 · 119 base-only, 119 INTA · BAR (i) MET · BAR (ii) MET, 0 moved** | §73.7's table, cell for cell ✓ |
| `check_fuzz_bank.py --strict` | `check_seq.run_tb` → `ensure(check_core.recipe("fsm"))` | **PASS · 3,242 banked seeds · stable 3,237 improved 5 worse 0 · gen_drift 0 · regen_err 0 · float-floor 0 · new-sig TIMING 0**, rc 0 | PASS, rc 0 ✓ |
| `check_mod3_illegal.py` (ARCHIVED, via `check_seq`) | same | **PASS · 128 goldens cycle-exact 128/128 · arch-confined 128/128 · moffs-exact 2/2** | PASS ✓ |
| `quartus_gate.py --parse-only` | shared receipt writer | **PASS · 88 files · E3 43.59 MHz · E4 +8.308 · E5 TNS 0.000 · ALMs 11,126 (27 %) · latches 0 · lpm_divide 0** | the bars, unchanged ✓ |

### §75.5a `check_fuzz_bank` — RUN TWICE, PRE AND POST, AND THE OUTPUT IS BYTE-IDENTICAL

This is the gate incarnation #3 lived in, so it is the one worth being careful
about.  It was run **before** the migration (on the binary as found) and
**after** (on the binary the layer built), 3,242 seeds each, ~23 minutes each,
and the two transcripts `diff` to **zero lines** — the same five IMPROVED seeds
(`mc1/1937`, `mc1/3325`, `mc1/3741`, `mc1/412`, `t30-raw/123`), the same
`stable 3237 improved 5 worse 0`, `new-sig TIMING 0`, rc 0.

**Which is the expected result and is stated as a control, not as a triumph**:
§75.4 measured that the binary was already byte-identical to a fresh build, so
the two runs executed the same bytes.  What the pair actually proves is that the
migration introduced **no behavioural change of its own** — no altered TB
argument, no changed working directory, no per-seed rebuild — over the longest
run in the standing set.

One line was added to `check_fuzz_bank.check()` AFTER those two runs and the
gate was then run a THIRD time with the code exactly as committed: the TB
binary is now resolved EAGERLY, before the seed loop.  It has to be, because
both `replay_classify` and the loop catch `Exception`, and `ArtifactError` is a
`RuntimeError` — so a stale binary would have been swallowed 3,242 times as a
per-seed `regen_err`/`ASSERT_PARK` instead of once as a sentence naming the
stale file.  The gate would still have FAILED; it would have failed unreadably.
**The third run is identical to the other two line for line** (modulo the new
`TB leg` header), rc 0, 22 m 58 s.

`receipt_diff` was exercised on both §5 shapes:

* **the X1 A/B pair** — `tb_sys/base` vs `tb_sys/ret`: **input manifests
  IDENTICAL (25 files, same `inputs.sha256`)**, command delta exactly
  `-DX1_AD_RETENTION`, outputs differ.  Exit **0** with `--expect-command`,
  **1** without it.  *This is the build-side half of the claim §56.3a's whole
  reading rests on, and it is now one command instead of a board sitting.*
* **the two cores** — `tb_ab/fsm` vs `tb_ab/ucore`: the delta is **exactly 23
  files, all of them `hdl/rtl/core/**` or `hdl/rtl/ucore/**`**, and NOTHING from
  the shared integration.  Exit **1** unexpected, as it should be without a
  declared axis.

### §75.6 TWO FINDINGS THAT CAME OUT OF DECLARING THE INPUTS

**(a) THE ucore's ENTIRE ARCHITECTURE WAS OUTSIDE EVERY IDENTITY IN THE TREE.**
`hdl/rtl/ucore/v30u_ucrom.sv` `$readmemh`s `ucrom.hex` (1,028 rows) and
`ucdecode.hex` (8,192 entries) **at RUN TIME**.  Verilator never opens either
file.  So under the spec's own wording — "every file the command reads" — the
two tables the whole core is made of would have sat outside the identity of
every number ever scored against it, and `v30u_ucrom.sv`'s F44 block exists
precisely because a wrong `HEXDIR` gives an all-zero ROM and *a run that
completes normally*.  The same holds for the FSM core's `int9d_race.hex`.
**The rule as built is: `inputs` is what the ARTIFACT is a function of, not what
the COMMAND reads.**  Recorded as erratum **E-1**.  `check_ucore_tables` (G0)
already checked those bytes against `sim/`; nothing tied them to a SCORED
NUMBER, and now every ucore receipt carries both hashes.

**(b) `quartus_gate`'s manifest was keyed on HDL-RELATIVE names**, so its 88
hashes could not be compared against any other receipt in the tree.  Re-keyed to
repo-relative through the shared writer.  The file COUNT and the discovery rule
are unchanged at **88**; the manifest `sha256` moved because the KEYS gained
their `hdl/` prefix.  **Nothing consumed the old hash** — there were no
`quartus_gate.json` files on disk at HEAD, and `standing_gates.md`'s narrative
citation of "exactly one file, `rtl/ucore/v30u_eu.sv`" now reads
`hdl/rtl/ucore/v30u_eu.sv`.

### §75.7 WHAT IS **NOT** MIGRATED — itemised, with the risk each still carries

Partial coverage stated plainly beats completeness implied.  **The line drawn is:
every tool that executes a VERILATOR TB BINARY and is a STANDING GATE asserts
the postcondition.**  Everything below is outside that line.

| # | what | risk it still carries |
|---|---|---|
| **U1** | **`sim/v30sim`** — the C++ model, built by `make -C sim`, consumed by **17 tools** (`timed_gate`, `timed_fuzz --core sim`, `ulockstep`'s model leg, `check_boot --timed`, `ucsim_check`, `timed_lawcards`, …) | **THE LARGEST REMAINING HOLE, and it is the same shape as all seven.**  Every `--core sim` figure in this ledger — including `timed_gate`'s 169,000 and the model's whole fuzz column — is scored against a binary with no receipt, whose relationship to `sim/*.cpp` is a `make` timestamp.  A stale `v30sim` is indistinguishable from a fresh one today |
| **U2** | `sw/safe_flash.sh` → `flash_log.jsonl` (spec §7 **step 2**, *"highest value per line in the whole list"*) | "what is on the board" still resolves to a sha256 of a `.sof`, not to the inputs that produced it.  **Excluded deliberately: it is the one item that ends at the board and this sitting is board-free.**  The build-side half now exists — `quartus_gate`'s receipt has an `id` and hashed `outputs` — so this is a one-field change on the next board sitting |
| **U3** | `gen_ucore_tables.py` / the generated tables (spec **step 5**) | `check_ucore_tables`' 9,988 is still "9,988", not "9,988 against receipt `<id>`".  **Partly mitigated by E-1**: the two `.hex` tables are now inside every ucore TB receipt, so a table change invalidates the binaries even though the GENERATOR has no receipt |
| **U4** | `emit_suite` / the golden suites / the fuzz bank (spec **step 6**) | **incarnation 7 (INV-1) is not closed.**  A golden's capture conditions are still not part of its identity.  The spec says this is its own project and must not be attempted with the others; it was not |
| **U5** | the ARCHIVED FSM gates that do NOT go through `check_seq.run_tb`: `check_ff_t4` (own `BIN` constant), `check_race_law`, `check_lc6_gate` | they gate an archived artifact and are on-demand only.  `check_ff_t4` in particular has its own hardcoded path to `obj_dir` and would happily run a stale binary |
| **U6** | the MEASUREMENT tools that execute a TB: `sweep_popa`, `sweep_dispphase`, `causal_wrand`, `uscope`, `pi1a_trace`, `repro_segleak`, `s11`–`s16` censuses | not gates, and `CLAUDE.md` already forbids quoting them as passes.  A wrong-binary measurement still misleads the agent reading it |
| **U7** | the BOARD legs: `x1_fabric`, `u4_f42_fabric`, `u4_tranche`, `check_ab_hw`, `s10_board`, `s13_board` | they execute the BITSTREAM, not a local binary.  Their identity question is U2's, and U2 is the answer |
| **U8** | `ss_lint` / `ss_flopcensus` | they parse RTL text rather than run a binary, so they have no artifact to vouch for.  Listed for completeness, not as a risk |

### §75.8 DEVIATIONS FROM THE SPEC — four, all recorded beside the text they deviate from

| | where | what |
|---|---|---|
| **E-1** | §3 | `inputs` includes files the COMMAND never reads (the runtime `$readmemh` tables).  §75.6(a) |
| **E-2** | §3 | the tool version is CHECKED by `require()`, not merely recorded, and it is inside `build_key` |
| **E-3** | §4 | the promote is TWO renames, not one — POSIX cannot rename a directory onto a non-empty one.  The guarantee is recovered more strongly by `require()` re-hashing `outputs` |
| **E-4** | §7 | the migration order moved: step 3 became the single declaration and six more consumers were migrated with it, because a receipt beside a binary that six gates still open by path is worth nothing |

One addition, not a deviation: **`build_key`** — the brief's content-addressed
key — is a field the schema did not have.  `id` is still §3's content hash of
the whole object.

### §75.9 WHAT THIS SITTING DID NOT DO

* **No engine changed.**  `git diff -- hdl/rtl sim` is EMPTY.
* **No board.**  No capture, no flash, no `use_core` flip.
* **No bitstream built.**  `quartus_gate` ran `--parse-only` against the tree
  already in `hdl/output_files_ucore/`; its **43.59 MHz** is §74.4a's
  "form 2 / HEAD, generated `.qsf`" draw and is not a new measurement.
* **No Codex.**  No memory file touched.
* **No gate figure moved**, and none was re-scored in either direction.

### §75.10 EVIDENCE

* `sw/artifact.py`, `sw/receipt_diff.py`, `sw/test_artifact.py`.
* `sw/testdata/receipts/verilator_binary.jsonl` and
  `sw/testdata/receipts/quartus_bitstream.jsonl` — the repo-level receipt
  history, which is what survives a `rm -rf` of any `obj_dir`.
* `<artifact>.receipt.json` beside each of the six binaries (gitignored with
  their `obj_dir`s, which is why the `.jsonl` exists).
* `docs/notes/artifact_receipt_layer.md` — the spec, unedited, with the four
  erratum boxes and a status banner.

## §76 SESSION SM3, SITTING 15 — **U1 IS CLOSED: THE C++ MODEL IS ON THE RECEIPT LAYER, AND THE ONE THING IT IS A FUNCTION OF THAT NOBODY WOULD HAVE DECLARED IS THE MICROCODE ROM.  THE FABRIC `+1` IS DIAGNOSED AND IT IS NOT A SCORER ARTIFACT.**

**2026-08-05, branch `ucsim`, from HEAD `b0d7dc20c3`.  OFFLINE ONLY — NO BOARD
CONTACT, no flash, no `use_core` flip, no capture.**

> **Standing principle, applied throughout.**  *"A guiding principal here needs
> to be simplicity.  This is 80's era hardware, they aren't wasting silicon on
> anything that isn't necessary.  Complex or confusing behavior that we see is
> likely to be simple systems interacting in ways you do not fully understand
> yet."*

### §76.A U1 — `sim/v30sim` ONTO THE LAYER

§75.7 named the C++ model **THE LARGEST REMAINING HOLE**: seventeen tools ran
it, every `--core sim` figure in this ledger was scored against it, and its
relationship to `sim/*.cpp` was a `make` timestamp.  `sw/simbin.py` is now to
the model what `check_core.recipe()` is to `Vtb_v30_core` — one declaration,
all consumers.

#### §76.A.1 WHAT THE BINARY IS A FUNCTION OF — **37 files, and the 37th is the surprise**

| what | n | why it is in the identity |
|---|---|---|
| `sim/*.cpp` | 16 | the sources |
| `sim/*.h` | 19 | including `pla3_table.h`, which is GENERATED from `docs/pla3_outputs.txt` but CHECKED IN — so the generator is a U3-shaped gap and the table itself is not |
| `sim/Makefile` | 1 | it carries `CXX`/`CXXFLAGS`; a flag change is a different binary |
| **`docs/V20BITS.TXT`** | **1** | **THE MICROCODE ROM, READ AT RUN TIME.**  `v30sim` takes it as `argv[1]`; all seventeen consumers pass this file and nothing else |

**THE ROM IS THE E-1 CASE, AND THIS TIME IT IS MEASURED RATHER THAN ARGUED.**
§75.6a established the rule — *`inputs` is what the ARTIFACT is a function of,
not what the COMMAND reads* — on the ucore's `$readmemh` tables.  The model has
exactly the same shape one layer over: the entire EU is `docs/V20BITS.TXT`, and
`g++` never opens it.

The measurement that makes the rule non-negotiable was taken here.  One byte of
`docs/V20BITS.TXT` was flipped, the model rebuilt, and the byte flipped back:

| | compiled output sha256 | `build_key` |
|---|---|---|
| before | `cd2735e645a1cc35…` | `3e2569007dbc…` |
| ROM perturbed by ONE byte | **`cd2735e645a1cc35…` — IDENTICAL** | `04947522f16d…` — MOVED |
| ROM restored | `cd2735e645a1cc35…` | **`3e2569007dbc…` — RETURNED** |

**The bytes do not move and the identity does.**  A freshness check that
compares the artifact — any hash of the binary, any mtime on it, any
`diff` of a rebuild — is *structurally incapable* of seeing a microcode change.
`sw/simbin.py --require` sees it and refuses, naming the file and both hashes;
the run is in this sitting's transcript.  (Reverting the byte also returns
`build_key` to its exact prior value, which is §C's content-key claim
demonstrated on a real input rather than in the self-test.)

**NOT inputs**: the per-invocation data files — `--wvec`, `--evt`, the image, a
`biu-script`.  Those are the QUESTION, not the instrument.

*Read the history file accordingly*: `sw/testdata/receipts/cxx_binary.jsonl`'s
**middle** entry is the perturbation itself and records a `docs/V20BITS.TXT`
hash of `b4fdcc34ef4c0fd7…`, which is not a state this tree was ever in for a
scored number.  It is left in place because the `.jsonl` is an append-only
record of what was built, and deleting a true entry corrupts a ledger exactly
as badly as inventing one.  **No gate figure in §76.A.3 was taken under it** —
every one of them ran before the perturbation or after the restore, and the
restored `build_key` is bit-identical to the pre-perturbation one.

**A residual, stated rather than implied**: `sim/Makefile` declares `CXX` and
`CXXFLAGS` with `?=`, so an environment variable would win over it and would
not appear in the receipt.  `CXX=g++` is pinned on the make command line (a
command-line assignment beats both), and `CXXFLAGS`/`LDFLAGS` in the
environment are **REFUSED** by `simbin._guard_env()` rather than silently
omitted.

#### §76.A.2 TWO STRUCTURAL DECISIONS, BOTH FORCED

**(a) THE BINARY MOVED TO `sim/build/v30sim`.**  `artifact.build()` promotes by
renaming its workdir, and the workdir is the artifact's parent.  With the
artifact at `sim/v30sim` a build would have renamed the SOURCE TREE.  So the
receipted binary lives in a directory of its own.  `make -C sim` still writes
`sim/v30sim`; **that binary is on no scorer's path any more**, and the ROM/PLA
disasm gate moved with everything else (`sw/simbin.py --disasm`, **1,285 rows
byte-exact**, printing the receipt id).

**(b) THE BUILD IS `make -B`.**  The layer's key is CONTENT; `make`'s is MTIME.
If the layer decides to build it must not hand the decision back to a weaker
test — a source whose content changed under an unchanged mtime would move the
build key, run `make`, and `make` would skip the object.  `-B` removes the seam
for **2.9 seconds**, which is the whole cost of a full rebuild here.

**AND THE §75.4 CONTROL WAS RE-TAKEN BEFORE ANYTHING WAS MIGRATED**: a full
`make -B` into a scratch directory OUTSIDE the repo reproduced the `sim/v30sim`
that was on disk **byte for byte** (`cd2735e645a1cc35…`).  g++ 15.2.0 is
byte-reproducible on this tree and output-path-independent, and nothing in the
tree was stale at HEAD — so, exactly as at sitting 14, **the migration could
not move a number through a rebuild, and it did not.**

#### §76.A.3 THE MIGRATION TABLE — 18 FILES, AND EVERY FIGURE RE-RUN

`SIM = ROOT / "sim" / "v30sim"` was the model's identity in **16** files.  All
16 now read `SIM = simbin.SIM` and call `simbin.ensure()` **eagerly at the top
of `main()`** — eagerly for §75.5a's reason: `ArtifactError` is a
`RuntimeError`, and a per-case `except Exception` would turn one sentence
naming a stale binary into N unreadable case failures.  `timed_scenario` and
`s15_census` reach the model through an imported module and were migrated with
them: **18 files.**

| gate | re-run figure | standing figure |
|---|---|---|
| `timed_gate.py --suite tests/v30/v0.1 --forms all` | **arch 169,000/169,000 · window 169,000/169,000 · rows-exact 169,000 · row-diffs 0** | 169,000, row-diffs 0 ✓ |
| `ucsim_check.py --suite tests/v30/v0.1` | **169,000 / 169,000** | 169,000 ✓ |
| `timed_fuzz.py --evt-replay` (`--core sim`) | **REGISTERED 1,272/1,702 · EVT 782/1,008 · COMBINED 2,054/2,710** | 1,272 / 782 / 2,054 ✓, to the seed |
| `timed_fuzz.py --seeddir …/b2-tranche/seeds` | **154 / 188** | 154/188 ✓ (V5 still the standing REGISTERED FAILURE) |
| `timed_wvec_gate.py` | **88/88, bus cycles 16,048 vs 16,048, +0.0 %** | 88/88 +0.0 % ✓ |
| `timed_enter_replay.py` | **154/154 ×5** (pushes, walk, full, active, halt_display) | 154×5 ✓ |
| `timed_ins_replay.py --raw` | **rails 1,312/1,312 · vs-chip 2,624/2,624**, 173,556/173,556 same-T1 | 1,312 / 2,624 ✓ |
| `timed_lawcards.py` | **GREEN 8 / 11 scored, 3 UNRESOLVED, 0 RED** | 8/0/3 ✓ |
| `timed_scenario.py` | **18 PASS, 0 FAIL, 9 SKIP** | 18/0/9 ✓ |
| `check_boot.py --timed 220` | **BOOT REPLAY MATCHES over 220 rows** | MATCH ✓ |
| `ulockstep.py --golden all --cases 50` (BOTH engines) | **17,350 / 17,350 ALL CASES LOCKSTEP** | 17,350 ✓ |
| `check_ucore_tables.py` (G0) | **PASS — 9,988 entries byte-identical on both legs** | 9,988 ✓ |
| `simbin.py --disasm` (the ROM/PLA gate) | **PASS, 1,285 rows** | byte-exact ✓ |
| `pla3_check.py` | **OK (21 checks)** | 21 ✓ |
| `test_artifact.py` (the layer's own falsifier) | **45/45** | 45/45 ✓ |

**NOT ONE NUMBER MOVED.**  Which is the expected result and is stated as a
control: §76.A.2's measurement says the binary was already the right one, so
these runs prove the migration introduced no behavioural change of its own —
no altered argument, no changed working directory, no per-invocation rebuild.

`check_ucore_tables` deserves a line of its own: its freshness test was
`if not SIM.exists()`, and **existence is not identity** — G0 compared the
ucore's 9,988 generated entries against whatever binary happened to be on disk.
It is `simbin.ensure()` now.

#### §76.A.4 THE §75.7 REMAINDER, SHRUNKEN

**U1 is CLOSED.**  What is left is **U2-U8, unchanged in substance**: U2 the
flash log (ends at the board; still a board sitting's one-field change), U3 the
table generator (`pla3_table.h` joins the ucore's `.hex` files as *generated,
checked in, hashed into consumers, generator unreceipted*), U4 the golden
suites / INV-1, U5 the three archived FSM gates with their own `BIN` constants,
U6 the measurement tools, U7 the board legs, U8 `ss_lint`.

Two NEW items are booked honestly rather than left implied:

| # | what | risk |
|---|---|---|
| **U1a** | `s13_board.py` is migrated at `main()` only.  A board script that IMPORTS it and calls its functions directly never reaches the postcondition | a board sitting could still run an unasserted model.  `simbin.require_bin()` is the one-line fix at the point of use |
| **U1b** | the model reads `V30SIM_*` environment variables at RUN time (`QDEPTH`, `FLUSHTRACE`, `EVALTRACE`, `TICKTRACE`, `IETRACE`, `BNDTRACE`, `EVTTRACE`).  They are trace-only today, and RUN-time environment is not part of an artifact's identity in this layer at all | a future behavioural env var would be invisible to every receipt.  The rule to hold is: **the model must not grow a behavioural environment variable** |

### §76.B THE 18 SURVIVORS — RE-DERIVED PER CELL, AND THEY ARE **TWO FAMILIES, NO THIRD**

Re-derived from the banked sweeps (`sw/testdata/x1-retention/offline.json` and
the per-cell `*.ret.json.gz` rows) and re-measured on THIS tree with
`check_core.py --core ucore --suite-dir tests/v30/<sweep> --opcodes all
--cases 0 --waits <w>`:

| sweep | measured here | |
|---|---|---|
| `s10-hltsweep-w0` | **91 / 97** | `HLT.INT` 44/48 · `HLT.RES` 47/49 |
| `s10-hltsweep-w1` | **92 / 95** | `HLT.INT` 43/46 · `HLT.RES` 49/49 |
| `s13-hltsweep-w2` | **42 / 46** | `HLT.INT` 17/21 · `HLT.RES` 25/25 |
| `s13-hltsweep-w3` | **40 / 45** | `HLT.INT` 15/20 · `HLT.RES` 25/25 |
| **total** | **265 / 283** | 18 survivors |

> ⚠ **ERRATUM, SAME SITTING, AGAINST MYSELF.**  This box first said
> *"`CLAUDE.md` quotes 91/90/40/38 = 259/283 and is stale"*.  **THAT WAS FALSE
> AND IS RETRACTED.**  `CLAUDE.md` on disk carries **91/97, 92/95, 42/46,
> 40/45 = 265/283** and has since sitting 6; the 259 figure came from a stale
> in-context snapshot of the file, not from the file.  The rule this breaks is
> the standing one — *verify against the artifact, not against recall* — and it
> is left in place rather than deleted for exactly the reason that rule gives.
> What stands is the measurement: **265/283, re-measured on this tree, with
> §67.3's coordinates cell for cell.**

| # | cell | w | delay | first div | signature | golden busstat/tstate | family |
|---|---|---|---|---|---|---|---|
| 1-2 | `s10-w0/HLT.INT/2,3` | 0 | 2,3 | (4, `busstat`) | `exp 'CODE' got 'PASV'` | CODE / Ti | **B** |
| 3-4 | `s10-w0/HLT.RES/2,3` | 0 | 2,3 | (4, `busstat`) | `exp 'CODE' got 'PASV'` | CODE / Ti | **B** |
| 5-6 | `s10-w0/HLT.INT/4,5` | 0 | 4,5 | (7, `bus`) | `exp 0x67CB4 got 0x57CB4`, Δ **+0x10000** | CODE / T4 | **A** |
| 7-8 | `s10-w1/HLT.INT/8,9` | 1 | 8,9 | (9, `seg`) | `exp 'CS' got 'SS'` | CODE / Tw | **A** |
| 9 | `s10-w1/HLT.INT/10` | 1 | 10 | (10, `bus`) | Δ **+0x10000** | CODE / T4 | **A** |
| 10-12 | `s13-w2/HLT.INT/10,11,12` | 2 | 10-12 | (10\|11, `seg`) | `exp 'CS' got 'SS'` | CODE / Tw | **A** |
| 13 | `s13-w2/HLT.INT/13` | 2 | 13 | (12, `bus`) | Δ **+0x10000** | CODE / T4 | **A** |
| 14-17 | `s13-w3/HLT.INT/12,13,14,15` | 3 | 12-15 | (11\|12\|13, `seg`) | `exp 'CS' got 'SS'` | CODE / Tw | **A** |
| 18 | `s13-w3/HLT.INT/16` | 3 | 16 | (14, `bus`) | Δ **+0x10000** | CODE / T4 | **A** |

**FAMILY A — 14 cells.**  The `seg` cells and the `bus` cells are ONE family:
`check_core` blanks the decoded `seg` column on T4, so the same defect reports
as `seg` where the row is a `Tw` and as `bus` where it is a `T4`.  Every
divergence row's golden `busstat` is **CODE** — **not one is INTA**, so this
family has nothing to do with §56's INTA class.

**FAMILY B — 4 cells.**  `busstat exp 'CODE' got 'PASV'` on a `Ti` row: the
golden asserts the post-HALT CODE status one capture row before the ucore does.
All four at **w0, delays 2 and 3**, two in each form, and **byte-identical to
the model's** — same cells, same rows, same mismatch counts.

#### §76.B.1 THE OCCUPANCY MAP — FIVE CONTIGUOUS RUNS, EVERY ONE STRICTLY INTERIOR

`-` absent from the golden, `.` pass, `X` fail; delay index 0 leftmost.

```
s10-hltsweep-w0/HLT.INT  w0  -.XXXX.....................   44/48
s10-hltsweep-w0/HLT.RES  w0  ..XX......................    47/49
s10-hltsweep-w1/HLT.INT  w1  ---.....XXX...............    43/46
s10-hltsweep-w1/HLT.RES  w1  ..........................    49/49
s13-hltsweep-w2/HLT.INT  w2  ----......XXXX............    17/21
s13-hltsweep-w3/HLT.INT  w3  -----.......XXXXX.........    15/20
```

Both immediate neighbours of every run exist in the golden and **PASS** (w0.INT
1 and 6; w0.RES 1 and 4; w1.INT 7 and 11; w2.INT 9 and 14; w3.INT 11 and 17).
Nothing sits at an end of the delay axis, so this is not a boundary effect of
the sweep.

**AND THE RUNS ARE PINNED TO A STRUCTURAL LANDMARK.**  Let `H` be the first
delay whose golden capture contains a `HALT`-status row (4 / 8 / 10 / 12 at
w0 / w1 / w2 / w3):

| sweep | family A band | relative to `H` | width |
|---|---|---|---|
| w0.INT | 4, 5 | `H` … `H+1` | **2 = waits + 2** |
| w1.INT | 8, 9, 10 | `H` … `H+2` | **3 = waits + 2** |
| w2.INT | 10-13 | `H` … `H+3` | **4 = waits + 2** |
| w3.INT | 12-16 | `H` … `H+4` | **5 = waits + 2** |

**Family A occupies exactly `waits + 2` consecutive delays, starting at the
first delay that produces a HALT display, at every wait level.**  Family B is
the two delays immediately BEFORE that, and only at w0.

*Two instrument caveats, both load-bearing.*  (a) Family A is `HLT.INT`-only
**because the `HLT.RES` capture windows are too short to contain the row** (5-23
rows, ending at the display's T2, against `HLT.INT`'s 59-119) — `HLT.RES`'s
49/49 at w1 is not evidence that the form is clean.  (b) The four
`v0.1-w*evt` suites carry **800 HALT-display rows each at w1/w3** and the golden
segment indicator is **CS on all 800** (`0x6` on every `HLT.INT`, `0x2` on every
`HLT.RES`) — but their `evt.delay` minima are **18** and **24**, far outside the
`H … H+waits+1` bands, so **their 1,200/1,200 is no evidence at all about this
defect.**  A second population needs new cases emitted AT the band.

#### §76.B.2 ENGINE vs ENGINE — §T.1 REFINED, NOT REPEATED

Model re-measured this session: **91/97 + 95/95 + 44/46 + 42/45 = 272/283.**

| | model | ucore |
|---|---|---|
| w0.INT | 2,3,4,5 | 2,3,4,5 |
| w0.RES | 2,3 | 2,3 |
| w1.INT | — | 8,9,10 |
| w2.INT | 10,11 | 10,11,12,13 |
| w3.INT | 12,13,14 | 12,13,14,15,16 |
| | **11** | **18** |

**The model's 11 are a STRICT SUBSET of the ucore's 18** (model-only = ∅), and
on all 11 shared cells the model's full mismatch SET is a subset of the ucore's
with **0 model-only entries**.  **But the model carries the family-A signature
NOWHERE**: on `w0.INT/4,5` the model's first divergence is `row 17 busstat
INTA→PASV` and on `w2/w3` it is `ube 0→1`, several rows LATER than the ucore's
`seg`/`bus`.  So:

* the 4 family-B cells are **genuinely model-shared, same mechanism, same rows**;
* the other 7 shared cells fail on both engines for a **different and later**
  reason that the ucore inherits, and the ucore adds family A on top at an
  EARLIER row — which is what moves the reported first-divergence column;
* **all 14 family-A cells are ucore-OWNED BY SIGNATURE**, though 7 of them are
  model-shared as cells.

**The sentence for the ledger is therefore**: *at w0 the failing cell SETS are
identical but the first-divergence SIGNATURES are not* — `w0.INT/4,5` is the
counterexample, and §T.1's "the failing sets are NOT identical between engines"
is true at w1/w2/w3 and false at w0.

### §76.C **F52 — THE PRE-REGISTRATION.  WRITTEN AND COMMITTED BEFORE THE RTL WAS TOUCHED.**

#### §76.C.1 THE MECHANISM, AND WHY IT IS ONE LINE

The `seg` label is a **decoder artefact and not a segment fact.**  `check_core`
reads the segment indicator as `SEG_STR[ps & 3]` off the composed A19-16
nibble.  The wake code fetch's address is `0x57CB4`, so its own A19-16 is
`0x5`, and `0x5 & 3 == 1 == "SS"`.  The status nibble at the same instant is
`data_ps(CS) = {md8080, IE, 2'b10} = 0x6`, and `0x6 & 3 == 2 == "CS"`.
**`seg exp 'CS' got 'SS'` is literally "the golden shows STATUS here and the
ucore is still showing the ADDRESS".**  Δ`bus` = `+0x10000` is the same
sentence in arithmetic.

Measured across the wake fetch on the banked rows, the A19-16 = `0x5` run is:

| | golden | ucore |
|---|---|---|
| every PASSING cell | **2 rows** (the display + its T1) | 2 rows — identical |
| every FAMILY-A cell | **1 row** | **2, 3 or 4 rows** |

**AND THE RTL ALREADY SAYS WHY, IN ITS OWN COMMENT, ABOUT THE OTHER HALF OF THE
SAME MUX.**  `v30u_biu.sv`'s **M23**:

> *"the address one-shot is fired by the DISPLAY and is ONE CLOCK LONG; where
> the bus made the T1 wait it has already expired and A19-16 is back on the
> segment status while A15-0 holds the address by pad retention."*

M23 is enforced on the **T1** side (`t1_addr`, gated by `cur_late_t1`) and
**NOWHERE ON THE DISPLAY SIDE**.  `display = r_cmt_valid && !ann_kill`, and
`cmt_valid` is cleared only when its T1 opens (M2) — so when the announced
cycle must wait for a busy bus, **`display` stays asserted for every waiting
clock** and `ad_o`'s `display ? r_cmt_addr` republishes the full 20-bit address
on all of them.  The one-shot is one clock long on one side of the mux and
unbounded on the other.

That is the whole defect, and it explains the band without any extra
assumption: the family-A delays are exactly those at which the wake fetch's
display lands INSIDE the HALT pseudo-cycle's tail, which is `waits + 2` clocks
long — **the observed band width at every wait level.**

*Simplicity, as the standing principle requires*: there is no segment logic
here, no stack operation, no second HALT display and no per-cell table.  There
is one multiplexed pin group, an address one-shot that silicon fires for one
clock, and a term that was written on one side of the mux and not the other.

#### §76.C.2 THE CHANGE

One term in `ad_o`: on a display clock that is **not the first**
(`r_cdage != 0`), A19-16 carries the ANNOUNCED cycle's own status nibble
`data_ps(r_cmt_seg)` — the same group as `bs`, which already switches to
`r_cmt_bs` at the display — while A15-0 continues to hold `r_cmt_addr[15:0]`.
No flop is added; nothing else in the BIU, and no engine but the ucore, is
touched.

#### §76.C.3 THE REGISTERED PREDICTIONS

| | bar | point estimate |
|---|---|---|
| **P1** | the four HLT sweeps ≥ **273 / 283** (≥ 8 of the 14 family-A cells close) | **279 / 283** = `93/97 · 95/95 · 46/46 · 45/45`, and **the ONLY survivors are the four family-B cells** (`w0.INT/2,3` and `w0.RES/2,3`) |
| **P2** | `check_core --core ucore --opcodes all --cases 0` | **169,000 / 169,000**, cycles AND arch |
| **P3** | the ucore ladder, every cell unmoved: `v0.1-w1`/`-w3` 1,200 · `EB` 200 · the four `evt` cells 200/1,200/200/1,200 · `w1evt-biased` 1,200 · `f4a_boundary` 160 · `f0lock_tranche` 400 · `check_boot` 220 and 400 · `ulockstep --golden all` 17,350 · `timed_wvec_gate` 88/88 +0.0 % · `timed_enter_replay` 154×5 · `timed_ins_replay --raw` 1,312/2,624 · `timed_fuzz --core ucore` REGISTERED ≥ 1,490, EVT ≥ 910, b2 ≥ 172 · `ss_lint` rc 0 | identical |
| **P4** | the MODEL is not touched: `git diff -- sim` EMPTY, and §76.A.3's `--core sim` column stands unre-run except where a shared gate re-runs it anyway | identical |

**THE FALSIFIERS, and they are conditions to REVERT ON, not to explain:**

1. **any currently-PASSING sweep cell fails** → revert.  The change touches
   every waiting display in the corpus, not only the HALT's, so this is the
   real risk and it is registered as such.
2. **`check_core` drops below 169,000** → revert.
3. **the four FAMILY-B cells CLOSE** → the ATTRIBUTION is wrong even if the
   score improves, because family B is a different mechanism and is
   model-shared.  Report and revert.
4. fewer than 8 of the 14 family-A cells close → the mechanism is not the whole
   story; revert and book the partition.

### §76.D **F52 — THE RESULT.  P1 IS A REGISTERED FAILURE; THE CHANGE IS CORRECT AND INSUFFICIENT, AND IT IS REVERTED AS REGISTERED.**

| | registered | **measured** |
|---|---|---|
| **P1** the four HLT sweeps | ≥ **273 / 283**, point estimate **279** | **268 / 283** — `91/97 · 93/95 · 43/46 · 41/45`.  **MISSED.** |
| **P1** family-A cells closed | ≥ **8** of 14 | **3** of 14 (`w1.INT/10`, `w2.INT/13`, `w3.INT/16`) |
| **P2** `check_core --core ucore --opcodes all --cases 0` | 169,000 | **169,000 / 169,000**, cycles AND arch — **MET** |
| **P2b** `ulockstep --golden all --cases 50` | 17,350 | **17,350 / 17,350 ALL CASES LOCKSTEP** — **MET** |
| falsifier 1 | any currently-PASSING sweep cell fails | **DID NOT FIRE** — every sweep moved UP or stayed level; 0 cells regressed |
| falsifier 3 | the four family-B cells close | **DID NOT FIRE** — all four still fail at `(4, busstat)`, unmoved |
| **falsifier 4** | fewer than 8 of 14 close → *"the mechanism is not the whole story; revert and book the partition"* | **FIRED** |

**REPORTED AS REGISTERED, NOT RESTATED.  Falsifier 4 fired and its registered
disposition is taken: the change is REVERTED.**  §71's precedent governs — a
landing that is built, measured and reverted leaves behind something sharper
than what it set out to land, and that is what happened here.

#### §76.D.1 WHAT THE INTERVENTION ESTABLISHED ANYWAY — AND IT IS NOT SMALL

**THE FAMILY-A SIGNATURE IS GONE FROM ALL 14 CELLS.**  Not one residual cell's
first divergence is `seg 'CS'→'SS'` or a `bus` Δ of `+0x10000` any more; every
surviving first divergence moved LATER in the capture (w1 row 9 → 11, w2 row 10
→ 12/13, w3 row 11 → 14/15) and changed column.  The diagnosis in §76.C.1 is
therefore **supported**: the address one-shot really is one clock long, M23's
law really was enforced on only one side of its mux, and re-enforcing it
removes exactly the observable it predicts and nothing else.

**WHAT IT DID NOT DO is close the cells**, because 11 of the 14 carry a SECOND,
LATER divergence underneath the one that was masking it.  That is why the score
moved by 3 and not by 14, and it is the honest content of falsifier 4.

#### §76.D.2 THE RESIDUE, RE-PARTITIONED — 15 CELLS, FOUR FAMILIES

Measured with `--details 20` on the F52 tree before the revert.  **This is the
directed-cell spec the next sitting starts from, and it replaces "14
undiagnosed `seg` cells" entirely.**

| family | n | cells | signature (first divergence) |
|---|---|---|---|
| **B** (unchanged, **model-shared**) | 4 | `w0.INT/2,3` · `w0.RES/2,3` | `(4, busstat)` `exp 'CODE' got 'PASV'` — the post-HALT CODE status one row late |
| **C** — *A19-16 UNDRIVEN* | 2 | `w0.INT/4,5` | `(11, bus)` `exp 0x69090 got 0x09090` — the golden carries the STATUS nibble `0x6` and the ucore drives **`0x0`**, i.e. it is not driving A19-16 at all where silicon does.  Then `(17, busstat)` `INTA→PASV`, which is the model-shared later divergence |
| **D** — *T1 ONE ROW EARLY* | 4 | `w1.INT/8,9` · `w2.INT/12` · `w3.INT/15` | `(r, pins)` `exp 0 got 1` with `tstate exp 'Ti' got 'T1'` — the ucore opens the wake fetch's T1 one capture row before silicon |
| **E** — *UBE* | 5 | `w2.INT/10,11` · `w3.INT/12,13,14` | `(r, ube)` `exp 0 got 1` on two consecutive rows — UBE held where silicon drops it |

4 + 2 + 4 + 5 = **15**, and the catch-all is empty.  **Family C is the same law
as F52 one step further on** — A19-16 must carry the status group whenever it
is not carrying the address, and there is a window at w0 where the ucore drives
neither.  **Family D is the F43/H1 shape** (*"the decision that opens a cycle is
taken on the wrong edge relative to an external level"*) and is the family
resemblance §5.5 of the residue census already flagged.

#### §76.D.3 THE DIFF, PRESERVED, AND WHAT WOULD RE-LAND IT

The change is two hunks in `hdl/rtl/ucore/v30u_biu.sv` and adds no flop:

```systemverilog
wire [19:0] disp_addr = (r_cdage == 3'd0)
                      ? r_cmt_addr
                      : {data_ps(r_cmt_seg), r_cmt_addr[15:0]};
...
assign ad_o = ... : display ? disp_addr : ...      // was: display ? r_cmt_addr
```

**A RE-LAND MUST NOT RE-USE §76.C's BAR, AND MUST NOT SCORE ITSELF ON THIS
SITTING'S SWEEPS** — those numbers are now known, and a bar written after
seeing them is not a bar.  What a re-land owes is the FULL ladder this sitting
did not run (`v0.1-w1`/`-w3`, `EB`, the four `evt` cells, `w1evt-biased`,
`f4a_boundary`, `f0lock_tranche`, the 23 `v0.3` block-I/O forms, `check_boot`,
`timed_wvec_gate`, `timed_enter_replay`, `timed_ins_replay`, `timed_fuzz
--core ucore`, `ss_lint`, `check_ab_sim`), pre-registered as unmoved, with
**268/283 and 169,000/169,000 carried forward as ALREADY-MEASURED FACTS, not as
predictions.**  The two heavy legs are already in hand and both are clean.

### §76.E **§74.2's `+1` ROW — SETTLED.  IT IS A REAL ONE-CLOCK INSTRUMENT DIFFERENCE, NOT A SCORER ARTEFACT, AND THE FABRIC IS THE STRONGER INSTRUMENT.**

§74.2 booked it: on all **119** cells the fabric's first divergence is exactly
one row LATER than the offline `tb_sys base` record's, same column, `INTA` at
both coordinates.  *"It is NOT diagnosed here, it is booked."*  It is diagnosed
now, offline, on the banked captures, with **no board contact**.

#### §76.E.1 THE TWO SCORERS ARE THE SAME CODE, AND THE ROW ORIGIN IS CONTENT-ADDRESSED

Both legs call the identical driver and the identical comparator:
`x1_retention.py:261` and `x1_fabric.py:82` (and `u4_f42_fabric.py:89`) all call
`emit_suite.emit_evt_case(...)`; the offline leg only swaps `es.run_image` for
`vsys_run` at `x1_retention.py:241`.  **Row 0 is defined by observed BUS
CONTENT, not by an index**: `emit_suite.py:1513-1516` finds the anchor code
fetch (`t==1 && ad_addr==anchor_linear && bs_early==4`) and
`emit_suite.py:1544` takes `i0 = fpop_is[n_skip_f]`.  A lead-in, arming or
reset-release difference in a capture buffer therefore *cannot* shift the
numbering — it would have to change the anchor match.  The first-divergence
index is `check_core.py:425`'s `for i in range(n)` in `diff_rows`, read out at
`x1_fabric.py:135` and `x1_retention.py:338`; `score_base.json` and
`score_fab_f7.json` were produced by literally the same function.

(For contrast `check_ab_hw.py:54` DOES use an index origin — `rel = next(i for
i,r in enumerate(recs) if not r["rst"])` plus its `i>=8`/`i>=9` skips.  It plays
no part in this comparison and is a different scale entirely.)

#### §76.E.2 THE LANDMARK CONTROLS — ALL 283 CELLS, ALL BY THE IDENTICAL CODE PATH

| control | result |
|---|---|
| row 0 identical, golden = base = ret = `fab_f6` = `fab_f7` | **283 / 283** |
| capture LENGTH `base` == `fab_f7` | **283 / 283** |
| the 18 survivors, δ(`fab_f7` − `base`) | **0 on 18 / 18** |
| the 18 survivors, δ(`fab_f6` − `ret`) | **0 on 18 / 18** |
| **offline `ret` vs fabric `fab_f6`, RAW ROWS** | **0 differing rows out of 15,351 — BIT-IDENTICAL** |
| rows where `base` matches the golden and fabric does NOT | **0** |
| rows where fabric matches the golden and `base` does not | **2,766** |
| an AD-LAG artefact (`fab[i] == base[i-1]` on rows where they differ) | **0 of 6,569** |
| the class, δ(`fab_f7` − `base`) | **+1 on 119 / 119**, `bus` → `bus` |

**The `ret` vs `fab_f6` line is decisive on its own**: with the retention macro
ON, the Verilated `system_large` and the fabric emit the SAME ROWS, cell for
cell, over 15,351 rows.  A row-origin offset would appear there too, and it does
not appear anywhere.

#### §76.E.3 THE DIRECTION, AND IT IS THE OPPOSITE OF WHAT "AN OFFSET" WOULD MEAN

At the offline base's first-divergence row `r`, **the fabric equals the golden
exactly on 119 / 119** and the base differs on 119 / 119; the fabric then
diverges at `r+1` on 119 / 119.  Golden T-state at `r` is `INTA/T4` on 44 cells
and `INTA/Ti` on 75; at `r+1` it is `INTA/T1` on **119 / 119**.  At `r+1` the
fabric's value is the NEXT data phase arriving one row early —
`fab[r+1].data == golden[r+2].data` on **119/119**.

```
s10-hltsweep-w0/HLT.INT/1,  r = 6
row 6  golden INTA/T4   G bus=0x09090  | base 0x00000 | fab 0x09090   <- fab MATCHES
row 7  golden INTA/T1   G bus=0x09090  | base 0x00000 | fab 0x000ff   <- fab diverges
row 8  golden INTA/T2   G bus=0x600ff  | base 0x600ff | fab 0x600ff
```

#### §76.E.4 THE MECHANISM — TWO SIMPLE SYSTEMS, EXACTLY AS THE PRINCIPLE PREDICTS

`core_ad` has exactly two drivers: the core's `AD` under `AD_OE`, and
`system_large.sv:379`'s `core_ad[15:0] = c_addrv_q ? c_rdata_q : 16'hzzzz`.
Verilator resolves the net to `z` the instant both enables drop and the capture
records **0**.  Quartus has nowhere to put a `z` on an internal tri-state — it
builds a MUX — and the evidence says the mux passes `c_rdata_q` whenever the
core's OE is off.  `c_rdata_q` is `nec_bus`'s `rdata_q`, loaded FREE-RUNNING and
independently of `drive_en` at `nec_bus.sv:468`:

```systemverilog
rdata_q <= mem_cycle_type == BS_INTA ? {8'h00, cfg_int_vector} : mem_rdata;
```

So at the `T4`/`Ti` row it still holds the PREVIOUS read's data — which is
exactly what the chip's floating pads retain, so the fabric gets one row of
accidental, free retention — and at the following `INTA T1` it has ALREADY been
reloaded with `{8'h00, vector}`, one row before the chip's pads receive it.
**That is the whole `+1`: a harness read-data register that reloads early, and a
synthesis tool with nowhere to put a `z`.**

#### §76.E.5 THE VERDICT, AND THE BOOKKEEPING CONSEQUENCE

**REAL ONE-CLOCK INSTRUMENT DIFFERENCE.  NOT a scorer or row-indexing
artefact.**  §74.2's "natural reading" was correct and is now measured, with one
refinement that must be recorded because it inverts the usual assumption:
**the difference is not symmetric noise — on the affected row the FABRIC agrees
with silicon and the Verilated `base` leg does not, on 119 / 119, and there is
no row anywhere in the 283-cell population where `base` is right and the fabric
is wrong.**  `tb_sys --leg base` is the WEAKER instrument of the two, by exactly
one row per INTA turnaround.  This does not move any number: the `ret` leg,
which is the one every X1 result is scored on, is bit-identical to the fabric.

*The single confirming measurement, if anyone wants it, is offline and is
specified*: a third `tb_sys` leg modelling the Quartus resolution rather than
the pad — `core_ad_eff = core_ad_oe ? core_ad : {4'b0, c_rdata_q}` — must
reproduce the fabric base leg EXACTLY: **146/283, the same 137 failing cells,
first divergence at `r+1` on all 119, and 0 rows differing from `fab_f7` over
all 283 cells.**  A build and a re-score, no board.  **Not run here.**

### §76.F WHAT THIS SITTING DID NOT DO, AND THE STATE IT LEAVES

* **NO BOARD CONTACT.**  No capture, no flash, no `use_core` flip, no
  transport opened.  Nothing in this section was measured on silicon; every
  fabric number quoted in §76.E is read off BANKED captures.
* **NO ENGINE CHANGED, NET.**  `git diff <the F52 pre-registration commit> --
  hdl/rtl sim` is **EMPTY** at the close.  F52 was built, scored and reverted
  inside the sitting; the RTL is byte-identical to what it was before it.
* **The ucore is re-proved on the reverted tree**: `check_core --core ucore
  --opcodes all --cases 0` **169,000 / 169,000**, the four sweeps **265 / 283**
  at §67.3's coordinates.
* **Not opened**, as scoped: the 8080 work, H3-B, H7.  **No memory file
  touched.  Codex not launched.**
* **Not run**: the ucore's full ladder (it was not needed — nothing landed).
  §76.D.3 states what a re-land owes.

## §77 SESSION SM3, SITTING 16 — **F52's RE-LAND IS F53, AND IT IS ONE LAW, NOT THREE: FAMILIES A, C AND E ARE THE SAME SENTENCE ON THREE PINS.  AUTHORISED ON A NEW BOARD POPULATION THAT DID NOT EXIST WHEN ANYTHING WAS SCORED, ON WHICH IT CLOSES 72 + 5 SIGNATURE CELLS AND BREAKS NOTHING.**

**2026-08-05, branch `ucsim`, from HEAD `dc820e8569`.  BOARD CONTACT: yes —
socket only, `use_core=False`, divider PINNED at both ends of the session, NO
FLASHING, `board_idle()` at the close.**

> **Standing principle, applied throughout.**  *"A guiding principal here needs
> to be simplicity.  This is 80's era hardware, they aren't wasting silicon on
> anything that isn't necessary.  Complex or confusing behavior that we see is
> likely to be simple systems interacting in ways you do not fully understand
> yet."*

The pre-registration is `docs/notes/sm3_s16_prereg_2026-08-05.md`, committed as
`aa31eb2f0f` **before the board was touched**, and this section reports against
it and does not restate it.

### §77.A THE DIAGNOSIS — §76.D.2's FOUR FAMILIES ARE **TWO MECHANISMS AND ONE INSTRUMENT CLASS**

§76.D.2 partitioned the 15-cell residue into **B**(4) · **C**(2) · **D**(4) ·
**E**(5) and called family C *"the same law as F52 one step further on"*.  That
reading is CONFIRMED and it goes further than one step: **A, C and E are one
law.**

`check_core`'s `bus` column is `ad_addr` on a T1 row and `{ps, ad_data}`
everywhere else, so the A19-16 sample is directly readable on every other row.
Read that way, `s10-hltsweep-w0 HLT.INT idx 4` states the whole thing:

| row | T | status | GOLDEN A19-16 | ucore | |
|---|---|---|---|---|---|
| 6 | T3 | CODE | **5** — the ADDRESS | 5 | the wake fetch's DISPLAY clock |
| 7 | T4 | CODE | **6** = `data_ps(CS)` | **5** | **family A** |
| 8 | T1 | CODE | 6 (a LATE T1) | 6 | M23's `t1_addr`, already correct |
| 10 | T3 | INTA | **0** — the "address" | 0 | the acknowledge's DISPLAY clock |
| 11 | T4 | INTA | **6** | **0** | **family C** |
| 12 | T1 | INTA | 6 (a LATE T1) | **0** | **family C** |

M23 already wrote the law down — *"the address one-shot is fired by the DISPLAY
and is ONE CLOCK LONG; where the bus made the T1 wait it has already expired and
A19-16 is back on the segment status"* — and `v30u_biu.sv` enforced it on the
**T1** side alone.  `display ? r_cmt_addr` republished the whole 20-bit address
on every waiting clock (family A, F52's diagnosis, correct); and
`(disp_inta || cur_inta) ? 20'h0` did the IDENTICAL thing one cycle-type over
(family C).  **An INTA has an address phase too; its value is simply zero,
because it announces no address.**

**And UBE is the same one-shot's third pin.**  `ube_n`'s middle term was
`r_run ? r_cur_ube_n` — a *running* cycle re-drives its UBE on every clock of
its body.  That is invisible for an ordinary cycle (it re-drives the value its
own T1 latched) and wrong the instant an announcement that has already put its
UBE on the pin is **WITHDRAWN**: the chip keeps the withdrawn announcement's
UBE by pad retention and the running HALT pseudo-cycle painted its own `1` over
it.  Family E — and it is **ucsim-t §26.7.7's open item** (*"after a WITHDRAWN
multi-clock announcement the pads retain the WITHDRAWN cycle's address and
UBE"*), seen from the RTL side and now **CLOSED**.

#### §77.A.1 THE LAW — F53

> **The address phase is ONE CLOCK, on both sides of the pin mux and for both
> kinds of address.**  A19-16 carries the announced cycle's address-phase value
> for exactly the display clock (`r_cdage == 0`) — the address's own A19-16 for a
> cycle that has one, `0` for an INTA, which does not — and `data_ps(seg)` on
> every clock after it, up to and including a LATE T1.  **UBE is loaded by the
> address phase and then HELD**; it is not re-driven by a cycle that is merely
> running, so a withdrawn announcement's UBE stands on the pads.

Two `wire [3:0]` selectors, one changed term in `ube_n`, one re-spelled mux in
`ad_o` — **no flop added, mux PRIORITY unchanged, nothing outside the pin group
touched, and no engine but the ucore.**  There is no segment logic here, no
per-cell table and no second HALT display.

#### §77.A.2 FAMILY D IS NOT THIS LAW — IT IS **THE ANALYSER'S SECOND SAMPLE**, AND THE MEASUREMENT IS 217 MILLION ROWS WIDE

`nec_bus.sv` samples `BS` **twice** per CPU clock: `bs_early` at the FALLING
edge (line 188-197), which is the value that lands in the row's status column,
and `bs_q`, registered every system clock, so at `tick_rise` it is the
END-of-clock value and it is what `next_t_state` reads (lines 297, 339-345).  On
family D's four cells the golden carries `bs_early != PASV` on the last clock of
a withdrawn window **and** `t == Ti` on the row after: **silicon's announcement
status is present at mid-clock and gone by the end of the same clock.**

The ucore's `bs` is a whole-clock level, so the analyser's two samples see the
same value and the pattern is unreachable.  Counted over **every committed
golden suite — 217,507,379 rows** (`v0.1` 4,547,843 · `v0.2` 9,990,517 · `v0.3`
108,053,378 · `v20suite` 94,438,658 · the four sweeps · the evt tranches ·
`f4a_boundary` · `f0lock_tranche` · `mod3_illegal`) — the pattern
`bs(r) != PASV ∧ t(r) ∈ {T4,Ti} ∧ t(r+1) == Ti` occurs **4 times**, and they are
**exactly the four family-D cells**: `w1.INT/8` row 10, `w1.INT/9` row 10,
`w2.INT/12` row 12, `w3.INT/15` row 14.  Nowhere else, in any suite.

**And `tb_v30_core.sv` has only ONE sample**, used both as the recorded column
and as its own tracker's `bs_active` — so on the default TB these four cells are
unfixable **by construction**: any half-clock status release that produced the
golden's `t == Ti` would also flip the recorded status column and break the row
it was fixing.  On `tb_sys` and in fabric, where the analyser IS `nec_bus`, a
half-clock release WOULD be scoreable.  **BOOKED, NOT LANDED** — it is a
different mechanism (*when within the clock the status register releases on a
withdrawal*, the F43/H1 shape), it owes its own authorising evidence, and folding
it into F53 would be fitting.
**Its falsifier, registered here**: land a negedge status release and `tb_sys` /
fabric must close all four while `tb_v30_core` must NOT.

#### §77.A.3 FAMILY B STAYS BOOKED, AND IT GREW BY TWO CELLS' WORTH OF MEANING

4 cells, `w0.INT/2,3` · `w0.RES/2,3`, `(4, busstat) CODE→PASV` — the whole
capture one row late.  **Model-shared** (§76.B.2), so `sim/` owns it and this
sitting did not open it.  What F53 added is that `w0.INT/4,5`, which §76.D.2
called family C, are **family B underneath**: with the nibble signature gone
their first divergence is `(17, busstat) INTA→PASV` — the SECOND acknowledge one
capture row late, the same "an announcement fires one row later than silicon"
sentence at a different announcement.  So the sweeps' post-F53 residue is
**6 family-B cells and 4 family-D cells, and the catch-all is empty.**

### §77.B THE DIRECTED CELL — S16, THE DISPLAY WALK

`sw/sm3_s16_cell.py`.  **It did not exist when anything was scored**, which is
what §76.D.3 requires of a re-land's authorising population.

* **3 forms** — `HLT.INT` (ie=1, status nibble `0x6`), `HLT.RES` (ie=0, `0x2`),
  `HLT.NMI` (ie drawn per program).  `HLT.NMI` is in **no** HLT delay sweep.
* **6 programs per form**, each ONE frozen RNG draw, printed by `plan` and
  written into the pre-registration.  **The s10/s13 sweeps run ONE program per
  form and its wake-fetch linear address is `0x57CB4`**, whose top nibble `5` is
  a legal segment-status code — ucsim-t §26.7's confound.  The 18 S16 programs
  split **7 IMPOSSIBLE** (wake nibble ≥ 8: it sets the 8080 emulation-mode bit,
  which no segment status can carry in a capture that is not in emulation mode,
  so the nibble NAMES ITSELF as the address), **9 legal-diff**, **2 SAME** (the
  confounded control the sweeps are).
* **4 wait levels × 21 delays** (0..20), containing `H … H+waits+1` at every
  level with margin on both sides.
* **1,512 planned cells; 1,371 emitted; 141 not composable** — every one of
  them at a LOW delay where the pin event fires before the HALT is reached
  (`no F pop from close addr` / `recognition off-window`), i.e. the case does
  not exist, not a capture that failed.
* **303 s of board time, 2 capture runs, `div_guard` PINNED on all four
  probes (open and close of each run), 0 transport errors, no wedge.**  Raw
  64-bit words + full per-clock rows retained for all 1,512, `SHA256SUMS` over
  **3,025 files** in `sw/testdata/sm3-s16cell/`.
* Emitted through the STANDARD path (`es.emit_evt_case`), so the goldens are
  `tests/v30/s16-dispwalk-w<w>-p<p>/<form>.json.gz` and `check_core` scores them
  with no new machinery.

**AND IT ENLARGES THE POPULATION THE LAW CAN BE TESTED ON BY 26×.**  ucsim-t
§26.7.2 found **42 multi-clock display windows in the entire banked corpus**.
This one cell contains **1,095**, out of 10,693 windows.

### §77.C THE FIVE REGISTERED PREDICTIONS ABOUT SILICON — **ALL MET, ALL AT 100 %**

Read off the captured GOLDEN rows alone: no model, no core.
(`sm3_s16_cell.py measure`, `sw/testdata/sm3-s16cell/measure.json`.)

| | registered | **measured** |
|---|---|---|
| **S1** A19-16 on the display clock is the announced cycle's own address nibble | 100 % | **84 / 84** — and **42 / 42** of them are IMPOSSIBLE-class, i.e. a nibble ≥ 8 that no segment status can carry |
| **S2** every clock of the window AFTER the display clock carries `data_ps(seg)` | 100 % | **3,079 / 3,079** |
| **S3** a LATE INTA T1 carries `data_ps(seg)`; the INTA display clock carries `0` | 100 % | **12 / 12** and **12 / 12** |
| **S4** every UBE transition sits on an address phase | 100 % | **2,937 / 2,937** |
| **S5** the §77.A.2 two-sample signature exists in this population too | ≥ 1 | **24** |

**No exception anywhere.**  S1's IMPOSSIBLE half is the load-bearing one: it is
the first time the address/status separation has been made on a population
chosen for it rather than on the single `HLT.RES` program §26.7 happened to have
banked.

### §77.D THE LANDING, REPORTED AS REGISTERED

| | registered bar | **measured** |
|---|---|---|
| **L1** ZERO family-A/C nibble signatures on S16 | 0 | **0** — **MET** (it was **72** before the change) |
| **L2** ZERO family-E `ube` signatures on S16 | 0 | **0** — **MET** (it was **5**) |
| **L3** every cell carrying neither booked shape PASSES | 0 exceptions | **52** — **MISSED.  A REGISTERED FAILURE** (§77.E) |
| **L4** the four HLT sweeps move UP or stay level | ≥ 265/283 | **273 / 283** = `91/97 · 93/95 · 45/46 · 44/45` — **MET.**  Validation only; it authorises nothing |
| **L5** the standing ladder unmoved | — | **MET**, itemised in §77.F |
| falsifier 1 | any currently-PASSING cell fails | **DID NOT FIRE** — on S16, cell for cell, **GAINED 45, LOST 0** |
| falsifier 2 | `check_core` below 169,000 | **DID NOT FIRE** — 169,000 / 169,000 |
| falsifier 3 | L1 or L2 non-zero | **DID NOT FIRE** |
| falsifier 4 | the four family-B cells CLOSE | **DID NOT FIRE** — all four still fail at `(4, busstat)`, unmoved |
| falsifier 5 | `ulockstep` below 17,350 | **DID NOT FIRE** — 17,350 / 17,350 |

**No falsifier fired, so the change STANDS.**  L3 is a bar and not a falsifier;
it is missed, and §77.E says what it is made of rather than explaining it away.

#### §77.D.1 THE CONTROL — THE SAME POPULATION, THE PRE-F53 BINARY

The RTL was reverted to `dc820e8569`, rebuilt, and the whole cell re-scored;
then restored and re-scored again.  **This is the attribution, and it is the
number the landing rests on:**

| | pre-F53 | **F53** |
|---|---|---|
| S16 total | 1,207 / 1,371 | **1,252 / 1,371** |
| w0 · w1 · w2 · w3 | 340 · 311 · 289 · 267 | 340 · **316** · **306** · **290** |
| family-A/C nibble signatures | **72** | **0** |
| family-E `ube` signatures | **5** | **0** |
| architectural failures | 33 | **33 — IDENTICAL** |
| cells gained / lost, cell for cell | — | **+45 / −0** |

The 33 architectural failures being bit-identical on both legs is the control
that says a PIN change changed pins: F53 cannot reach architecture and did not.
All 45 gained cells are `HLT.INT`, at w1/w2/w3, which is where a waiting display
window can be multi-clock.

### §77.E **L3 IS A REGISTERED FAILURE, AND ITS 52 CELLS ARE TWO MECHANISMS THE SWEEPS COULD NOT SHOW**

`busstat_other` **52**, IDENTICAL on both legs — F53 neither caused nor touched
one of them.  They are not one family:

| n | cells | what the golden says |
|---|---|---|
| **42** | `HLT.NMI` — **w0 d0 · w1 d3,4 · w2 d5,6 · w3 d7,8**, every one of them on all six programs | **the chip does not HALT at all** — the ucore drives the HALT status and the chip goes straight to the NMI vector read at `0x00008`.  This is the recognition-floor / `0x0008` NMI-vector class (**H7**), which this sitting was scoped OUT of.  *And the band SCALES WITH THE WAIT LEVEL* — `0`, `3-4`, `5-6`, `7-8` — which is a new, free observation: it is a fixed number of CLOCKS, not of delays, and no banked population could show it because **`HLT.NMI` is in no HLT delay sweep** |
| **6** | `HLT.RES` d2/d3 at w0 | the family-B shape itself, reproduced in the new programs |
| **4** | `HLT.INT` d2 at w0 | the chip runs a wake CODE fetch (`0x6DE0A` on p0) that the ucore **never runs at all** — it goes straight to the acknowledge.  Same regime as family B (the w0 wake-race at d2/d3), opposite outcome: the ucore SKIPS the fetch instead of running it one row late |

**`HLT.NMI` is in no HLT delay sweep**, so **42 of the 52** are residue no
banked population had ever exposed.  That is what a new population is for, and
booking them is the honest result: the bar was written to be missable and it was
missed.

### §77.F THE LADDER — EVERY CELL RE-RUN ON THE FINAL BINARY

`Vtb_v30_core` receipt `94c6b83edaed9bee…`.

| gate | standing | **measured** |
|---|---|---|
| `check_core --core ucore --opcodes all --cases 0` | 169,000 | **169,000 / 169,000** |
| `v0.1-w1` / `-w3` | 1,200 each | **1,200 / 1,200** |
| `EB` at w1 | 200 | **200 / 200** |
| the four `evt` cells | 200 / 1,200 / 200 / 1,200 | **identical** |
| `w1evt-biased` | 1,200 | **1,200 / 1,200** |
| `f4a_boundary` / `f0lock_tranche` | 160 / 400 | **160 / 160** and **400 / 400** |
| the 23 `v0.3` block-I/O forms | 229,999 | **229,999 / 229,999** cycles AND arch |
| `check_boot --timed 220` / `--timed 400` | MATCH | **MATCH over 220 rows** / **over 400 rows** |
| `ulockstep --golden all --cases 50` | 17,350 | **17,350 / 17,350 ALL CASES LOCKSTEP** |
| `timed_wvec_gate --core ucore` | 88/88, +0.0 % | **88/88, 16,048 vs 16,048, +0.0 %** |
| `timed_enter_replay --core ucore` | 154 ×5 | **154/154 ×5** |
| `timed_ins_replay --core ucore --raw` | 1,312 / 2,624 | **rails 1,312/1,312 · vs-chip 2,624/2,624**, 173,556/173,556 same-T1 |
| `timed_fuzz --core ucore --evt-replay` | REGISTERED 1,490 · EVT 912 · COMBINED 2,402 | **1,490** · **913** · **2,403** — EVT/COMBINED **RAISED by one seed** |
| `timed_fuzz … b2-tranche` | 172/188 | **172 / 188** (V5 still the standing REGISTERED FAILURE) |
| `timed_lawcards` | 8 GREEN / 0 RED / 3 UNRESOLVED | **GREEN 8 / 11 scored, 3 UNRESOLVED, 0 RED** |
| `ss_lint` | rc 0, 201 flops, 0 UNMAPPED | **PASS — 201 architectural flops, 0 UNMAPPED, 2 whitelisted** |
| `check_core --ce-div 4 --ce-hold-check` | `CE_HOLD_VIOL 0` | **`CE_HOLD_VIOL 0` on all 347 forms, 169,000/169,000** |
| `check_ab_sim` | 187 rows MATCH | **MATCH over 187 rows**, loop `CODE T1 @00100` `[26,90,154]` both sides |
| `check_ucore_tables` (G0) | 9,988 | **PASS, 9,988 byte-identical on both legs** |
| `pla3_check` · `simbin --disasm` · `test_artifact` | 21 · 1,285 · 45/45 | **OK (21)** · **PASS (1,285 rows)** · **45/45** |
| the four HLT sweeps | 265/283 | **273 / 283** — RAISED by 8 |
| **the MODEL** | — | **NOT TOUCHED.  `git diff -- sim` EMPTY.** |

### §77.G THE RATCHETS THAT MOVED, ITEMISED

| ratchet | before | **after** | which change |
|---|---|---|---|
| the four HLT delay sweeps | 259 → **265** (§67.4) | **273 / 283** | F53 |
| `timed_fuzz --core ucore` EVT | 912 / 1,008 | **913 / 1,008** | F53 |
| `timed_fuzz --core ucore` COMBINED | 2,402 / 2,710 | **2,403 / 2,710** | F53 |
| **NEW** — the S16 display walk | did not exist | **1,252 / 1,371** (pre-F53 1,207) | the cell |
| ucsim-t §26.7.7's open item (withdrawn-announcement UBE retention) | MEASURED, MECHANISM OPEN | **CLOSED — F53's UBE half** | F53 |

Everything else in `standing_gates.md` §B was re-measured, not inherited.

### §77.H WHAT THIS SITTING DID NOT DO, AND THE STATE IT LEAVES

* **NO FLASHING.**  No bitstream was loaded; `use_core` was never set; the
  board carries the same image it did at the open.  **Nothing here has been
  measured in fabric** — the ucore in fabric is still FLASH #6's, which predates
  F53.  A fabric leg is the obvious next confirmation and it is NOT claimed.
* **G6, THE QUARTUS LEG, RAN AND IS GREEN.**  `standing_gates.md` triggers it on
  any commit touching `hdl/rtl/ucore/**`, and F53 does.
  `sw/quartus_gate.py --label "SM3-s16 F53"`, ONE clean CONTROL/DEFAULT build
  from a deleted `db`/`incremental_db`, **compile rc 0 in 523 s**:

  | | bar | **measured** |
  |---|---|---|
  | **E1** `gen_ucore_qsf --check` | green | **PASS** — `nec_test_ucore.qsf` up to date |
  | **E2** 0 errors, every stage `Successful` | 0 | **PASS** — 0 stage errors, 0 error lines; map, fit and asm all Successful |
  | **E3** `divclk` Fmax | ≥ 32 MHz | **PASS — 45.57 MHz** (the other three domains 142.98 / 61.72 / 65.94) |
  | **E4** worst setup slack | > 0 | **PASS — +6.974 ns** |
  | **E5** TNS, setup AND hold, every domain | 0.000 | **PASS — 0.000 on all four domains, both directions** (worst holds +0.251 / +0.274 / +0.359 / +0.422) |

  RECORDED, NOT BARRED: **ALMs 11,058 / 41,910 (26 %)**, 6,111 fit registers,
  **0 latches, 0 `lpm_divide`**.  Receipt `02a71f69e4d58df1…`
  (`hdl/output_files_ucore/quartus_gate.json`, appended to
  `sw/testdata/receipts/quartus_bitstream.jsonl`), input manifest **88 files
  sha256 `1a20fd543311a4cb…`**.
  *Two things must be said plainly about it.*  (a) The receipt records the
  working tree as **`aa31eb2f0f-dirty`**.  The dirt was this section's own doc
  edits and the not-yet-committed S16 artifacts; **`hdl/` — which is what the
  88-file manifest covers — was byte-identical to `aa31eb2f0f` and is
  byte-identical to HEAD** (`git diff aa31eb2f0f HEAD -- hdl/` is EMPTY), so the
  figures are this RTL's.  (b) **A bitstream WAS PRODUCED and was NOT FLASHED**:
  `nec_test_ucore.sof f2c1b471ceb58ded…`, `.rbf 6dbbc687c3c6ca3d…`.  The board
  still carries FLASH #6, which predates F53.  **§74.4 still governs any single
  Fmax figure**: one green build establishes repeatability of one draw, not
  closure.
* **Family D is BOOKED, not landed** (§77.A.2), with its falsifier written down.
* **Family B is left to `sim/`** — it is model-shared and the mechanism is the
  model's.
* **H7 was not opened**, as scoped, although §77.E's `HLT.NMI` cells are H7's
  and are now visible in a golden suite for the first time.
* **The 8080 work and H3-B were not opened.  No memory file was touched.
  Codex was not launched.**

## §78 SESSION SM3, SITTING 17 — **THE 42 CELLS ARE NOT H7.  THEY ARE THE MISSING NMI HALF OF F43's HALT-DISPLAY SUPPRESSION, AND THE LAW IS ONE SENTENCE WITH ONE CONSTANT PER PIN: `A <= H - K`, `K = 3` ON INT AND `K = 6` ON NMI.  LANDED IN THE ucore WITH NO FLOP ADDED, +42 / −0 CELL FOR CELL.**

**2026-08-05, branch `ucsim`, from HEAD `6e4c60cce6`.  NO BOARD CONTACT — the
authorising population is sitting 16's S16 walk, captured before any of this
existed; `use_core` was never set, nothing was flashed, and no capture was
taken.**

> **Standing principle, applied throughout.**  *"A guiding principal here needs
> to be simplicity.  This is 80's era hardware, they aren't wasting silicon on
> anything that isn't necessary.  Complex or confusing behavior that we see is
> likely to be simple systems interacting in ways you do not fully understand
> yet."*

The pre-registration is `docs/notes/sm3_s17_prereg_2026-08-05.md`, committed as
`d6e2d852cb` **before `hdl/rtl/ucore/**` was touched**, and this section reports
against it and does not restate it.

### §78.A THE INSTRUMENT — `sw/sm3_haltsupp.py`, and it asks ONE question

New MEASUREMENT tool (never a gate).  It reads the S16 cell's retained
per-clock rows (`sw/testdata/sm3-s16cell/`, 1,512 captures) and the emitted
goldens, and puts every cell in one coordinate:

    arm   the capture row of the CODE T1 at the case's anchor -- the row the
          rig's `ev_st` FSM arms on (`nec_bus.sv` 486-527)
    A     the row the pin goes HIGH on = arm + delay + 2
    H     the row the HALT status appears on.  H is a property of the
          (form, program, wait level) and NOT of the delay: **8 / 12 / 14 / 16**
          at w0 / w1 / w2 / w3, on all 18 programs.

### §78.B THE SILICON LAW — F54, AND IT IS **ONE CONSTANT PER PIN**

A `HLT` whose pin event arrives early enough **never puts a HALT status on the
bus at all**.  The part still executes the HALT — the pushed frame is the one
AFTER the `F4`, which is exactly why `emit_evt_case`'s `recognition off-window`
guard composes these cases instead of rejecting them — and the ANNOUNCEMENT is
cancelled.

| form | pin | ie | largest `A − arm` that suppresses, w0 · w1 · w2 · w3 | **K = H − that** |
|---|---|---|---|---|
| `HLT.INT` | INT | 1 | 5 · 9 · 11 · 13 | **3** |
| `HLT.RES` | INT | 0 | 5 · 9 · 11 · 13 | **3** |
| `HLT.NMI` | NMI | either | 2 · 6 · 8 · 10 | **6** |

> **F54.  The HALT announcement at clock `H` is cancelled iff the pin event's
> assert clock `A` satisfies `A <= H − K`, with `K = 3` on the INT pin and
> `K = 6` on the NMI pin.**

**Invariant over the wait level** (4), **over the program** (6 per form,
spanning all three S16 nibble classes) and **over IE** (`HLT.INT` ie=1 and
`HLT.RES` ie=0 share `K = 3`).  126 cells behind every table entry, **no
exception in 1,512**.  There is no per-delay table here and no second HALT
rule: two integers, one per pin.

*Falsifier, registered*: a silicon capture whose HALT announcement fires with a
pin event at `A <= H − K`, or is cancelled with one at `A >= H − K + 1`.

### §78.C **§77.E's H7 ATTRIBUTION IS WITHDRAWN**, and the proof is one row index

§77.E read the 42 `HLT.NMI` cells as *"the recognition-floor / `0x0008`
NMI-vector class (**H7**)"*.  That is wrong, and the measurement that says so
needs no board:

* the FIRST divergence is `(row, busstat) PASV -> HALT` on **42 / 42**;
* on **36 / 42** the golden and the ucore put the NMI vector read (`MEMR` T1 at
  `0x00008`) at the **IDENTICAL row index** and the captures are the **same
  length**.  The 6 exceptions are ALL `w3 d7` (one per program): there the
  ucore's window is one row longer and the vector read is pushed past the
  window close, which is the spurious HALT's own displacement and not a
  different recognition instant — the first divergence on those six is the same
  `PASV -> HALT`;
* on the same population the NMI vector read is **`A + 14` on 372 / 372**
  halted cells with no exception, and 13 or 14 on the 132 suppressed/running
  ones — i.e. the S16 population's NMI floor is **13**, which is where BOTH
  engines already are.

So the recognition timing was never in question on these cells; only whether
the announcement fires.  **H7's evidence set LOSES 42 cells and GAINS a fourth
directed population** (1,512 captures at floor 13/14, alongside `sm3_h7_cell`'s
160 and `sm3_h7_opcode`'s 640).  **H7 stays BLOCKED**, untouched otherwise.

> **ERRATUM against the pre-registration, and the prereg is LEFT AS COMMITTED.**
> `sm3_s17_prereg_2026-08-05.md` §2.3 states the identical-row / same-length
> result *"on the band cells"* without qualification.  It holds on **36 of 42**,
> as measured above; the six `w3 d7` cells are the exception and are stated
> there.  The document is NOT edited — it is the record of what was believed
> before the RTL was touched — and the correction lives here.  The load-bearing
> half of the claim, the first divergence being `PASV -> HALT`, is **42 / 42**
> and is unaffected.

### §78.D WHY NO POPULATION HAD EVER SHOWN IT

`HLT.NMI` is in no HLT delay sweep (§77.E).  The three standing `HLT.NMI`
golden suites are `v0.1` **200** · `v0.2` **1,000** · `v0.3` **10,000** =
**11,200 cases**, every one at `delay >= 8`, and **every one of them carries a
HALT status**.  At w0 the band is `d <= 0`.  The S16 cell is the first
population in the tree to sample `d <= 8` on this form — which is also why the
landing cannot move them.

### §78.E THE ucore's DEFECT, DERIVED BEFORE IT WAS TOUCHED

The INT half is already right, and it is right in TWO places: `eu_unhalt`
clears the BIU's `halt_pending` outright (`v30u_biu.sv`, `if (eu_unhalt)`),
covering every `A <= H − 4`, and F43's `eu_unhalt_disp` covers the single
remaining `D == H` clock.  **`sm3_haltsupp.py engine --core ucore` scores the
INT half at 0 disagreements over 1,008 cells, all four wait levels, both
forms.**

The NMI wake reaches NEITHER path until `unhalt_pend`, which `S_IRQ_D` sets at
`c0 + 2` and which therefore reads true only from `c0 + 3 = A + 7`
(`c0` = the first `S_HALTED` clock with `nmi_latch` up, and `nmi_latch` reads
true from `A + 4`).  Suppression then needs `A + 7 <= H − 1`, i.e. **`A <= H − 8`
— which is exactly the measured ucore threshold.**  The arithmetic was checked
against the data *before* anything was changed, and it is what the two
candidates were written on.

### §78.F **CANDIDATE V-A — BUILT TO BE REVERTED, AND ITS PREDICTION IS HALF MET AND HALF MISSED.  REPORTED AS REGISTERED.**

`hlt_wake_disp = (st == S_HALTED) && (int_p[1] || nmi_latch)`.  §3.3 registered:
*"closes all 42 AND breaks exactly 24 currently-PASSING cells — `HLT.NMI` at
w0 d1 · w1 d5 · w2 d7 · w3 d9, all six programs"*.

| | registered | **measured** |
|---|---|---|
| breaks exactly 24, at `A = H − 5` | 24 at those coordinates | **24, at exactly `w0 d1 · w1 d5 · w2 d7 · w3 d9`, all six programs** — **MET** |
| closes all 42 | 42 | **0** — **MISSED** |

**P1 is a REGISTERED FAILURE as a conjunction**, and the half that missed is
the informative one.  `eu_unhalt_disp` is a ONE-CLOCK test taken at the edge
ending `H − 1`, and `(st == S_HALTED) && irq_nmi_lvl` is true for exactly one
clock (`c0`) because the EU leaves `S_HALTED` on that very edge.  So the term
can only ever fire when `c0 == H − 1`, i.e. at `A == H − 5` and nowhere else —
which is precisely the 24 cells it broke and the reason it closed none of the
42.  The clock arithmetic of §78.E is therefore **confirmed to the clock**, and
what it corrected is the MECHANISM assumption: the durable suppression for INT
is `halt_pending` being cleared, not the one-clock display test.  Total row
failures went 92 → 116; the RTL was restored.

### §78.G **THE LANDING — F54, AND IT ADDS NO FLOP**

`hdl/rtl/ucore/v30u_eu.sv` only:

```systemverilog
wire hlt_wake_nmi_disp = eu_halted && (st != S_HALTED);
assign eu_unhalt_disp  = hlt_wake_disp || unhalt_pend || hlt_wake_nmi_disp;
```

`eu_halted` and `st <= S_HALTED` are written in the **SAME arm** (`S_DECODE2`),
so the term is false everywhere before the HALT; and the INT wake clears
`eu_halted` in the same arm that leaves `S_HALTED`, so it is false there too.
**It is NMI-specific by construction, not by a pin test.**  It is true across
`c0+1 .. c0+2` and `unhalt_pend` takes over at `c0+3`, so the union is
`c >= c0+1` with no gap: the display decided at the edge ending `H − 1` is
cancelled iff `c0 + 1 <= H − 1`, i.e. `A + 5 <= H − 1`, i.e. **`A <= H − 6`**.
No flop, no pin tap, no constant, no state.

### §78.H THE RESULT, REPORTED AS REGISTERED

| | registered bar | **measured** |
|---|---|---|
| **P2** V-B closes 42, breaks 0 | 42 / 0 | **42 / 0** — **MET** |
| **P3** engine's suppressing-`d` set identical to the golden's, 12 (form, wait) cells | 0 disagreements | **0**, all three forms, all four wait levels — **MET** |
| **L1** all 42 band cells PASS | 42 | **42** — **MET** |
| **L2** zero currently-PASSING S16 cell fails | 0 | **0** — **MET** |
| **L3** S16 total >= 1,294 | 1,294 | **1,294 / 1,371** — **MET at the point estimate** |
| **L4** the four HLT sweeps >= 273 | 273 | **273 / 283** = `91/97 · 93/95 · 45/46 · 44/45` — **MET, unmoved** (they carry no `HLT.NMI`) |
| **L5** the standing ladder unmoved | — | **MET**, itemised in §78.J |
| **L6** `sm3_haltsupp engine` 0 disagreements | 0 | **0** |
| falsifier 1 | any currently-PASSING cell fails | **DID NOT FIRE** |
| falsifier 2 | `check_core` below 169,000 | **DID NOT FIRE** — **169,000 / 169,000** |
| falsifier 3 | `ulockstep` below 17,350 | **DID NOT FIRE** — **17,350 / 17,350** |
| falsifier 4 | the four HLT sweeps below 273 | **DID NOT FIRE** |
| falsifier 5 | `NMI.90` / `NMI.B8` move | **DID NOT FIRE** — **200 / 200 each**, cycles AND arch |

**No falsifier fired, so the change STANDS.**

#### §78.H.1 THE CONTROL — THE SAME POPULATION, THE PRE-F54 BINARY

The RTL was reverted, rebuilt, the whole cell re-scored with `--save`, then
restored, rebuilt and re-scored again.  **This is the attribution:**

| | pre-F54 | **F54** |
|---|---|---|
| S16 total | 1,252 / 1,371 | **1,294 / 1,371** |
| w0 · w1 · w2 · w3 | 340 · 316 · 306 · 290 | **346 · 328 · 318 · 302** |
| §77.E's L3 residue (`busstat_other`) | **52** | **10** |
| family-A/C nibble signatures (L1) | 0 | **0** |
| family-E `ube` signatures (L2) | 0 | **0** |
| architectural failures | 33 | **27** |
| **cells gained / lost, cell for cell** | — | **+42 / −0** |

The 42 gained are, exactly: `w0 HLT.NMI d0` · `w1 d3,4` · `w2 d5,6` ·
`w3 d7,8`, six programs each.  **Nothing else in 1,371 cells moved in either
direction.**  Six of the 42 were also architectural failures (the `w0 d0` cell,
whose pushed frame the spurious HALT displaced), which is why the arch column
falls 33 → 27; no arch failure was created.

### §78.I **THE MODEL — MEASURED, BOOKED, NOT LANDED**

`sm3_haltsupp.py engine --core sim`, scored through `timed_gate`'s own
`case_result` so the dontcare mask is the standing one:

| form | silicon's largest suppressing `d`, w0·w1·w2·w3 | the MODEL's | gap |
|---|---|---|---|
| `HLT.RES` | 3 · 7 · 9 · 11 | **3 · 7 · 9 · 11** | **EXACT** |
| `HLT.INT` | 3 · 7 · 9 · 11 | **2 · 4 · 5 · 6** | short by 1 · 3 · 4 · 5 |
| `HLT.NMI` | 0 · 4 · 6 · 8 | **none at any composable delay** | the whole law |

`sim/` was **NOT TOUCHED** (`git diff -- sim` EMPTY), and the model additionally
lacks F53, so its S16 row score is dominated by the display nibble and is not a
usable bar for this.  **The next sitting has a bar it can write on this table.**
That the model gets the ie=0 form exactly right and the ie=1 form wrong at every
wait level is itself the lead: whatever it does, it is not one rule for the pin.

### §78.I.1 **FAMILY B, RE-DIAGNOSED — IT IS ONE SENTENCE WITH TWO OUTCOMES, AND IT IS THE WAKE'S FIRST PREFETCH, ONE CLOCK LATE**

The scope allowed family B as a bonus if the NMI law landed cleanly.  It was not
opened, but it WAS diagnosed, and the diagnosis is sharper than §77.A.3's:

The post-F54 residue is **77 cells**: 50 row-failing (first-divergence classes
`busstat_other` **10** · `B_late` **16** · `D_tstate` **24**) and 27
architectural.  **Fourteen of the 50 are ONE divergence at ONE row**, and they
carry ALL TEN of the `busstat_other` residue plus four of the `B_late`: they are
`HLT.INT` w0 d2 and d3 (p0,p3,p4,p5) and `HLT.RES` w0 d2 and d3 (p1,p3,p5) —
i.e. the TOP TWO delays of the INT suppression band at w0, `A − arm` in
{4, 5} = {H−4, H−3}.  On every one of the fourteen the golden's row 4 carries a
**`CODE` display clock** — the wake's first prefetch announcement — and the
ucore's row 4 is `PASV`:

| cells | golden row 4-6 | ucore row 4-6 | n diffs |
|---|---|---|---|
| `HLT.RES` d2/d3, 6 cells | `CODE Ti` … | `PASV Ti`, then the SAME fetch one clock later | **3** |
| `HLT.INT` d3, 4 cells | `CODE Ti · CODE T1 · CODE T2` | `PASV Ti · CODE Ti · CODE T1` | 158-212 |
| `HLT.INT` d2, 4 cells | `CODE Ti · CODE T1 · CODE T2` | `PASV Ti · PASV Ti · INTA Ti` | 179-245 |

**One mechanism, two outcomes**: the wake's prefetch announcement is issued ONE
CLOCK LATE, and at `d2` that one clock puts it past the acknowledge's own slot,
so the fetch is not late — it is LOST, and the ucore goes straight to `INTA`.
§77.E read two of those groups as *"the same regime, opposite outcome"*; they
are the same clock.  The regime is specifically **the suppressed-announcement
one**
— these are cells where F54's law cancelled the HALT display, so there is no
HALT pseudo-cycle for the wake to come out of, and it is at **w0 only**.

It is **MODEL-SHARED** (§76.B.2), so `sim/` owns the mechanism, and it is
**BOOKED, NOT LANDED**: it is a prefetch-release clock, a different mechanism
from F54's display cancel, and folding it in after the ladder had been run would
be exactly the fitting this campaign forbids.
*Falsifier for whoever takes it*: move the wake's prefetch release one clock
earlier in this regime and all 14 must close while the four HLT sweeps and the
11,200 `HLT.NMI` goldens do not move.  **The remaining 36 row-failing cells are
NOT this** — they are `HLT.INT` at w0 d4,d5 · w1 d8,d9 · w2 d12 · w3 d15, the
family-D two-sample class §77.A.2 booked with its own falsifier, and they are
untouched here.

### §78.J THE LADDER — EVERY CELL RE-RUN ON THE FINAL BINARY

`Vtb_v30_core` **inputs sha `9fb97ea436e55177…`** (receipt id
`445d1add69509624…` for the ladder run; a later identical rebuild is
`a385f54004f51536…`, same inputs hash, so the two are the same function of the
same files — the id carries the timestamp, the inputs hash carries the tree).

| gate | standing | **measured** |
|---|---|---|
| `check_core --core ucore --opcodes all --cases 0` | 169,000 | **169,000 / 169,000** |
| — of which `NMI.90` · `NMI.B8` · `HLT.NMI` · `HLT.INT` · `HLT.RES` | 200 each | **200 / 200 each**, cycles AND arch |
| `v0.1-w1` / `-w3` | 1,200 each | **1,200 / 1,200** each |
| `EB` at w1 | 200 | **200 / 200** |
| the four `evt` cells | 200 / 1,200 / 200 / 1,200 | **identical** |
| `w1evt-biased` | 1,200 | **1,200 / 1,200** |
| `f4a_boundary` / `f0lock_tranche` | 160 / 400 | **160 / 160** and **400 / 400** |
| the 23 `v0.3` block-I/O forms | 229,999 | **229,999 / 229,999** cycles AND arch |
| `check_boot --timed 220` / `--timed 400` | MATCH | **MATCH over 220 rows** / **over 400 rows** |
| `ulockstep --golden all --cases 50` | 17,350 | **17,350 / 17,350 ALL CASES LOCKSTEP** |
| `timed_wvec_gate --core ucore` | 88/88, +0.0 % | **88/88, 16,048 vs 16,048, +0.0 %** |
| `timed_enter_replay --core ucore` | 154 ×5 | **154/154 ×5** |
| `timed_ins_replay --core ucore --raw` | 1,312 / 2,624 | **rails 1,312/1,312 · vs-chip 2,624/2,624**, 173,556/173,556 same-T1 |
| `timed_fuzz --core ucore --evt-replay` | REGISTERED 1,490 · EVT 913 · COMBINED 2,403 | **1,490 · 913 · 2,403**, `BOUND WARNINGS` 5, `ENGINE ABORTS` 0 |
| `timed_fuzz … b2-tranche` | 172/188 | **172 / 188** (V5 still the standing REGISTERED FAILURE) |
| `ss_lint` | rc 0, 201 flops, 0 UNMAPPED | **PASS — 201 architectural flops (BIU 83, EU 118), 0 UNMAPPED, 2 whitelisted.**  NO FLOP WAS ADDED, so `SS_VERSION` / `SS_COUNT` / the map do not move |
| save-state sweeps, modes 1 / 2 / 5 | 80 · 24 · PASS | **80/80 · 24/24 · 4/4** |
| `check_core --ce-div 4 --ce-hold-check` | `CE_HOLD_VIOL 0` | **`CE_HOLD_VIOL 0` on all 347 forms, 169,000/169,000** |
| `check_ab_sim` | 187 rows MATCH | **MATCH over 187 rows** |
| `check_ucore_tables` (G0) | 9,988 | **PASS, 9,988 byte-identical on both legs** |
| `pla3_check` · `simbin --disasm` · `test_artifact` | 21 · 1,285 · 45/45 | **OK (21)** · **PASS (1,285 rows)** · **NON-VACUOUS (45/45)** |
| the four HLT sweeps | 273/283 | **273 / 283** — unmoved |
| **the MODEL** | — | **NOT TOUCHED.  `git diff -- sim` EMPTY**; `timed_gate` on the five HLT/NMI forms **1,000 / 1,000, row-diffs 0** |

### §78.J.1 **G6, THE QUARTUS LEG — RAN AND IS GREEN**

`standing_gates.md` triggers it on any commit touching `hdl/rtl/ucore/**`, and
F54 does.  `sw/quartus_gate.py --label "SM3-s17 F54"`, ONE clean CONTROL/DEFAULT
build from a deleted `db`/`incremental_db`, **compile rc 0 in 524 s**:

| | bar | **measured** |
|---|---|---|
| **E1** `gen_ucore_qsf --check` | green | **PASS** — `nec_test_ucore.qsf` up to date |
| **E2** 0 errors, every stage `Successful` | 0 | **PASS** — 0 stage errors, 0 error lines; map, fit and asm all Successful |
| **E3** `divclk` Fmax | ≥ 32 MHz | **PASS — 45.49 MHz** (the other three domains 144.40 / 71.37 / 59.96) |
| **E4** worst setup slack | > 0 | **PASS — +9.146 ns** |
| **E5** TNS, setup AND hold, every domain | 0.000 | **PASS — 0.000 on all four domains, both directions** (worst holds +0.256 / +0.278 / +0.390 / +0.601) |

RECORDED, NOT BARRED: **ALMs 11,126 / 41,910 (27 %)** — it was 11,058 (26 %) at
F53, i.e. **+68 ALMs**, which is what a term added to one mux costs and is the
only resource move — 6,110 fit registers (F53: 6,111), **0 latches, 0
`lpm_divide`**.  Receipt `d7e27e7c4fe810bc…`
(`hdl/output_files_ucore/quartus_gate.json`, appended to
`sw/testdata/receipts/quartus_bitstream.jsonl`), input manifest **88 files
sha256 `567b11fffd6414a6…`**.

*Two things must be said plainly.*  (a) The receipt records the tree as
**`d6e2d852cb-dirty`** — `d6e2d852cb` is this sitting's own pre-registration
commit and the dirt is F54's one file plus these docs; the 88-file manifest
covers `hdl/`, and the only tracked `hdl/` change in the tree is
`hdl/rtl/ucore/v30u_eu.sv`, i.e. F54 itself.  (b) **A bitstream WAS PRODUCED and
was NOT FLASHED**: `nec_test_ucore.sof b4e818965e2bee59…`, `.rbf
fc3cb1816ff3b007…`.  **The board still carries FLASH #6**, which predates both
F53 and F54.  **§74.4 still governs any single Fmax figure**: one green build
establishes repeatability of one draw, not closure.

### §78.K THE RATCHETS THAT MOVED, ITEMISED

| ratchet | before | **after** | which change |
|---|---|---|---|
| the S16 display walk | 1,252 / 1,371 (§77.D.1) | **1,294 / 1,371** | F54 |
| — per wait level | 340 · 316 · 306 · 290 | **346 · 328 · 318 · 302** | F54 |
| §77.E's L3 residue | 52 | **10** | F54 |
| S16 architectural failures | 33 | **27** | F54 |
| **everything else in `standing_gates.md` §B** | — | **re-measured, not inherited; not one figure moved** | — |

### §78.L WHAT THIS SITTING DID NOT DO, AND THE STATE IT LEAVES

* **NO BOARD CONTACT, NO FLASHING, `use_core` NEVER SET.**  Nothing here has
  been measured in fabric; the board still carries FLASH #6, which predates
  both F53 and F54.  A fabric leg is the obvious next confirmation and it is
  **NOT claimed**.
* **H7 IS STILL BLOCKED.**  §78.C removes 42 cells from its evidence set and
  adds a fourth directed population at floor 13; the bank's 30 `A + 12` seeds
  are untouched.  Two axes were eliminated this sitting and are booked here so
  they are not re-run: **(i)** the arm is not ambiguous — of the 30 gap-12
  seeds **28 have exactly ONE CODE T1 at the anchor** in the whole capture, so
  "the rig armed on a different occurrence than the analysis" is REFUTED;
  **(ii)** the divider is not it — `check_seq.run_chip` and `emit_suite` both
  pin `DIV_OF_RECORD = 8`, and `NEC_NMI` is combinational off `ev_drive`, which
  moves only on `tick_rise`.  **The live statement is now sharper than it was**:
  three directed populations totalling **2,312 captures** floor at 13 and the
  banked soup is the ONLY population in the tree that reaches 12.
* **The bank cannot test F54**: of 1,165 banked `evt` seeds, **693** carry a
  HALT status in-window and **exactly ONE of them is a pin-1 seed**.  The law's
  independent validation has to come from a new population or from fabric.
* **`sim/` was not touched**; §78.I's model gaps are booked with their numbers.
* **Family B, family D, the 8080 work and H3-B were not opened.  No memory file
  was touched.  Codex was not launched.**

## §79 SESSION SM3, SITTING 18 — **THE MODEL'S F54 LEG IS ONE INTEGER, AND TWO THIRDS OF §78.I's "THREE WRONG WAYS" WERE A RIG DEFECT.  THE MODEL HAD THE INT CONSTANT EXACT ALL ALONG; ITS NMI CONSTANT WAS `K = 7` AGAINST SILICON'S `K = 6`.  +24 / −0 CELL FOR CELL, AND FAMILY B IS PARTITIONED AND BOOKED.**

**2026-08-05, branch `ucsim`, from HEAD `918fa67b57`.  NO BOARD CONTACT — every
population here is banked; `use_core` was never set, nothing was flashed, no
capture was taken.  NO `hdl/` FILE WAS TOUCHED, so G6 is not triggered and is
not claimed.**

> **Standing principle, applied throughout.**  *"A guiding principal here needs
> to be simplicity.  This is 80's era hardware, they aren't wasting silicon on
> anything that isn't necessary.  Complex or confusing behavior that we see is
> likely to be simple systems interacting in ways you do not fully understand
> yet."*

The pre-registration is `docs/notes/sm3_s18_prereg_2026-08-05.md`, committed as
`c7b9ff409e` **before `sim/` was touched**, and this section reports against it.

### §79.A **THE RIG DEFECT — AND IT IS WHY §78.I's MODEL COLUMN IS WITHDRAWN**

`v30sim timed-run` keys its record stream by the **array position** of the case
it was handed (`sim/timed_runner.cpp` 658-662).  `check_core.compose_batch`
keys the RTL batch by the golden's own **`idx`** (`check_core.py` 218).  Every
suite in the tree before S16 runs `idx = 0,1,2,…`, so the two agree and nothing
is visible.

**The S16 walk is the first population where they do not.**  There `idx` is the
pin-event DELAY; 141 of 1,512 cells are not composable; the surviving sets start
at **0** (`HLT.RES`), **1** (`HLT.INT`) and as late as **4** (`HLT.NMI` at w3),
with gaps.  `sw/sm3_haltsupp.py` used the RTL lookup on BOTH legs, so on the
model leg it read the WRONG CASE — and that is the instrument §78.I's model
column was measured through.

**The control, run before the fix was trusted**: the old lookup, replayed
against today's binary, reproduces §78.I's table exactly.

| form | §78.I as booked | the OLD lookup, replayed | **the CORRECTED instrument** |
|---|---|---|---|
| `HLT.RES` | 3 · 7 · 9 · 11 (EXACT) | 3 · 7 · 9 · 11 | **3 · 7 · 9 · 11 — EXACT** |
| `HLT.INT` | 2 · 4 · 5 · 6 | 2 · 4 · 5 · 6 | **3 · 7 · 9 · 11 — EXACT** |
| `HLT.NMI` | none at any delay | none at any delay | **3 · 5 · 7** at w1·w2·w3 |

`HLT.RES` escaped because its `idx` starts at 0 — for that form alone, position
**is** `idx`.  That is the whole of §78.I's "the model gets the ie=0 form exactly
right and the ie=1 form wrong at every wait level".

> **ERRATUM against §78.I.  §78.I IS LEFT AS COMMITTED** — it is the record of
> what was believed — **and the correction is here.**  Two of its three rows are
> INSTRUMENT ARTEFACTS.  The model does NOT get `HLT.INT` wrong at any wait
> level and does NOT lack the NMI law entirely.  **§78.I's lead — *"whatever it
> does, it is not one rule for the pin"* — is WITHDRAWN.  It is one rule for the
> pin, with one constant per pin, and one of the two constants was off by one
> clock.**  Fixed in `sw/sm3_haltsupp.py` and in the new `--core sim` leg of
> `sw/sm3_s16_score.py`; both re-key the model's stream to `idx` once, and
> everything downstream is engine-neutral.

*Falsifier for the fix, registered*: any suite on which the two legs' case
ordering differs and the re-keyed model leg does not reproduce the RTL leg's
per-case association.

### §79.B THE MODEL'S FIRST S16 FIGURE, AND THE RESIDUE PARTITION

`sw/sm3_s16_score.py --core sim` is new (the model had never been scored on the
authorising population).  It runs the model through `timed_gate.run_form` and
then **the identical code the RTL legs use** — `cc.check_case`, `cc.diff_rows`,
`classify_first` — so the PASS definition is the same on both legs.  The control
that says so: the ucore leg re-run today reproduces **1,294 / 1,371** and its
per-cell map agrees with `check_core`'s own `N/M full` count.

| | **the MODEL, before** | **the MODEL, after F54** | the ucore |
|---|---|---|---|
| S16 total | **1,225 / 1,371** | **1,249 / 1,371** | 1,294 / 1,371 |
| w0 · w1 · w2 · w3 | 337 · 325 · 294 · 269 | **343 · 331 · 300 · 275** | 346 · 328 · 318 · 302 |
| `busstat_other` | **34** | **10** | **10** |
| `B_late` | 16 | 16 | 16 |
| `D_tstate` | 0 | 0 | 24 |
| `qop` | 39 | 39 | 0 |
| `E_ube` | 30 | 30 | 0 |
| `ARCH` | 30 | 30 | 27 |

Read across, the two engines' S16 residues are **the same 26-cell family B, plus
one class each that the other does not have**: the ucore's 24 `D_tstate` are
§77.A.2's two-sample analyser class (unreachable for the model's row stream),
and the model's **39 `qop` + 30 `E_ube`** are its own — `E_ube` is **F53's UBE
half, which the model does not carry**, and it is 5 of the model's 11 HLT-sweep
misses.  Both are **BOOKED HERE, NOT OPENED**.

### §79.C THE LAW, AND THE MODEL ALREADY HAD HALF OF IT

F54 (§78.B): *the HALT announcement at clock `H` is cancelled iff the pin
event's assert clock `A` satisfies `A <= H − K`, with `K = 3` on the INT pin and
`K = 6` on the NMI pin.*

The model renders the cancellation as M20 already says it: the announcement is a
**queued write** to the display register (`biu_timed.cpp` 329,
`halt_pending_ && !run_ && !cmt_valid_ && c != no_eval_`) and `unhalt()` cancels
the queued write, so **the release clock IS the threshold**.

* the INT arms — masked (`HLT.RES`) and vectored (`HLT.INT`) alike — release at
  **`a + 3` = `A + K`, `K = 3`.  Exact, 1,008 cells, 0 disagreements.**
* the NMI arm released at **`a + 7`, i.e. `K = 7`** — one clock late, at every
  wait level, on all six programs.  **24 cells**, and they are the TOP delay of
  the NMI band at each level: `w0 d0 · w1 d4 · w2 d6 · w3 d8`.

**Why no banked population had ever shown it** is §78.D's sentence again: the
11,200 standing `HLT.NMI` goldens are all at `delay >= 8` and all carry a HALT
status, and `HLT.NMI` is in no HLT delay sweep.  Only the S16 walk reaches
`d <= 8` on this form.

### §79.D THE LANDING — TWO LINES, AND `halted_` IS DELIBERATELY NOT TOUCHED

```cpp
// biu_timed.h -- the ucore's `eu_unhalt_disp` in the model's idiom
void cancel_halt_disp() { halt_pending_ = false; }
```
```cpp
// timed_runner.cpp, run_evt, the halted branch, the NMI arm
biu.charge_to(a + 6);      // F54: A + K, K = 6 on the NMI pin
biu.cancel_halt_disp();    // the ANNOUNCEMENT only
biu.charge_to(a + 7);      // B = a+5, entry at B+2 -- UNCHANGED
```

This is the ucore's own shape: F54 lives on the **display path alone**
(`eu_unhalt_disp`), and the EU's real unhalt sequencing (`unhalt_pend`, at
`c0 + 3 = A + 7`) is left where it was.  So the model's `halted_` — the prefetch
park — and the whole `A + 7` wake schedule are untouched.  **The wake's prefetch
release is a different mechanism (family B) and is not folded in here.**  No new
constant that F54 does not already name, no per-delay table, no per-program
case, no new state.

### §79.E THE RESULT, REPORTED AS REGISTERED

| | registered bar | **measured** |
|---|---|---|
| **P1** | `sm3_haltsupp engine --core sim` 24 → 0 disagreements | **0**, all three forms, all four wait levels, all 12 (form, wait) cells — **MET** |
| **P2** | exactly 24 close, 0 break; S16 1,225 → **1,249**; per wait **343 · 331 · 300 · 275** | **+24 / −0 cell for cell**, and the 24 are exactly `HLT.NMI` `w0 d0 · w1 d4 · w2 d6 · w3 d8` × 6 programs; **1,249 / 1,371**, **343 · 331 · 300 · 275** — **MET** |
| **P3** | `busstat_other` 34 → 10, and they are the ucore's 10 | **10**, and they are the ucore's 10 cell for cell (`w0 HLT.INT d2` ×4, `w0 HLT.RES d2,d3` ×6) — **MET** |
| **P4** | the four HLT sweeps UNMOVED at 272/283 | **91/97 · 95/95 · 44/46 · 42/45 = 272 / 283** — **MET** |
| **P5** | the 11,200 `HLT.NMI` goldens unmoved | **200 / 1,000 / 10,000 = 11,200 / 11,200**, arch AND rows, **row-diffs 0** — **MET** |
| **P6** | `ulockstep` 17,350 | **17,350 / 17,350 ALL CASES LOCKSTEP** — **MET.  This is the evidence that the model's rendering matches the ucore's edge for edge**, because the ucore has carried F54 since §78 |
| **P7** | residue exactly `B_late` 16 · `busstat_other` 10 · `qop` 39 · `E_ube` 30 · `ARCH` 30 | **identical** — the NMI class is GONE and **no class grew** — **MET** |
| f1 … f6 | any falsifier | **NONE FIRED** |

**No falsifier fired, so the change STANDS.**

### §79.F THE LADDER — EVERY CELL RE-RUN ON THE FINAL BINARY

`sim/build/v30sim` receipt **`7dda28c3005e80c0…`**, artifact sha256
`9411e211f5723e8f…`, build key `1523681df4d81899…`.

| gate | standing | **measured** |
|---|---|---|
| `timed_gate --suite v0.1 --forms all` | 169,000, row-diffs 0 | **169,000 / 169,000, row-diffs 0** (3 collision-dependent under the mirror) |
| `v0.1-w1` / `-w3` (with `--waits`) | 1,200 each | **1,200 / 1,200** each, row-diffs 0 |
| `EB` at w1 | 200 | **200 / 200** |
| the four `evt` cells | 200 / 1,200 / 200 / 1,200 | **identical**, row-diffs 0 |
| `w1evt-biased` | 1,200 | **1,200 / 1,200** |
| the four HLT sweeps | 272 | **272 / 283** |
| the 11,200 `HLT.NMI` goldens | — | **11,200 / 11,200**, row-diffs 0 |
| `ucsim_check`, the full functional set | 7,341,126 | **169,000** · **347,000** · **3,699,998** · **3,125,000** (`v20suite --no-mirror`) · **128** (`mod3_illegal --residue stale-ea`) = **7,341,126 / 7,341,126** |
| `check_boot --timed 220` | MATCH | **MATCH over 220 rows**, loop period 64 both sides |
| `timed_scenario` | 18 / 0 / 9 | **18 PASS, 0 FAIL, 9 SKIP** |
| `timed_enter_replay` | 154 ×5 | **154/154 ×5** |
| `timed_ins_replay --raw` | 1,312 / 2,624 | **rails 1,312/1,312 · vs-chip 2,624/2,624**, 173,556/173,556 same-T1 |
| `timed_wvec_gate` | 88/88, +0.0 % | **88/88, 16,048 vs 16,048, +0.0 %** |
| `timed_lawcards` | 8 GREEN / 0 RED / 3 UNRESOLVED | **GREEN 8 / 11 scored, 3 UNRESOLVED, 0 RED** |
| `timed_fuzz --core sim --evt-replay` | 1,272 · 782 · 2,054 | **1,272 / 1,702 · 782 / 1,008 · 2,054 / 2,710**, `INVALIDATED` 0 |
| `timed_fuzz … b2-tranche` | 154 / 188 | **154 / 188** (V5 still the standing REGISTERED FAILURE) |
| `ulockstep --golden all --cases 50` | 17,350 | **17,350 / 17,350** |
| `simbin --disasm` · `pla3_check` | 1,285 · 21 | **PASS (1,285 rows)** · **OK (21)** |
| **the ucore** | — | **NOT TOUCHED.  `git diff -- hdl` EMPTY**; re-measured on the same populations at **1,294 / 1,371** and **273 / 283** |

### §79.G **FAMILY B — PARTITIONED AND BOOKED, AND THE DIAGNOSIS IS SHARPER THAN §78.I.1's**

The pre-registration offered **B1** (a one-term mechanism closing all 26 S16 and
all 6 sweep cells in both engines) and **B2** (partition and book).  **The
outcome is B2, and it is reported as registered, not explained away.**

**(a) IT IS THE SAME MECHANISM IN BOTH ENGINES, TO THE DIFF.**  On the four HLT
sweeps the w0 residue is identical in the C++ model and in the RTL — the same
six cells, the same first divergences, the same totals:

| cell | first divergence | n diffs, **both engines** |
|---|---|---|
| `HLT.INT` d2 | `(4, busstat) CODE -> PASV` | **179** |
| `HLT.INT` d3 | `(4, busstat) CODE -> PASV` | **158** |
| `HLT.INT` d4 · d5 | `(17, busstat) INTA -> PASV` | **128** each |
| `HLT.RES` d2 · d3 | `(4, busstat) CODE -> PASV` | **3** each |

§78.I.1 called family B "model-shared" from a census; this is the measurement
that says it is the same mechanism to the diff count, and it is **26 cells on
S16** (`busstat_other` 10 + `B_late` 16) and **6 on the sweeps**, **at w0 only**.

**(b) IT IS TWO SIGNATURES, NOT ONE, AND BOTH ARE MEASURED OFF THE GOLDENS
ALONE.**

*Signature 1 — the wake's first prefetch, in the CANCELLED regime (`d2`, `d3`).*
Silicon's post-wake schedule there is a function of `H`, not of `A`: **`d2` and
`d3` produce byte-identical captures.**  Reading the golden announcement rows,
the rule that fits w0 AND w1, both forms, is one sentence:

> the wake's prefetch is granted at the RUNNING cycle's own eval if the wake
> arrived by that cycle's index-2 arm sample — display at `eval + 1` — and
> otherwise at the CANCELLED HALT's own slot, display at **`H + 1`**.

w0: the running `CODE` cycle's eval is at `T3` (row 1), display 2, and the arm
sample is at row 1, so `d0,d1 -> 2` and `d2,d3 -> H + 1 = 4`.  w1: the eval is at
`T4` (row 3), display 4, arm sample at row 1, so `d0..d3 -> 4` and
`d4..d7 -> H + 1 = 6`.  **Both groups measured, no exception.**  The model gets
the first group right at both wait levels **and the second group right at w1**;
at w0 it puts the second group at `H + 2` (`d3 -> 5`), and at `d2` that one
clock puts the fetch past the acknowledge's own slot, so it is not late — it is
**LOST**, and the model goes straight to `INTA`.  *That is §78.I.1's "same
regime, opposite outcome", now with the arithmetic and with the w1 control that
says the model is not uniformly wrong.*

*Signature 2 — the SECOND acknowledge (`d4`, `d5`), and it is NOT the same
sentence.*  Here the announcement IS made and the HALT pseudo-cycle runs; what
is late is the second `INTA`.  Measured on `w0 p0 HLT.INT`:

| | INTA1 announce | INTA2 announce | gap |
|---|---|---|---|
| golden `d5` | 10 | **17** | **7** |
| golden `d6` | 11 | **18** | **7** |
| model `d5` | 10 | **18** | 8 |
| model `d6` | 11 | **18** | 7 |

**Silicon spaces the acknowledge pair 7 clocks ANNOUNCEMENT to ANNOUNCEMENT.**
The model reaches the same answer whenever the first display is one clock long
and is one clock late when the display WAITS — the two coincide because a
1-clock display puts `T4` at `disp + 4`.  Traced further, the divergence is the
clock the EU posts the second request: silicon grants it at the idle eval one
clock after the first acknowledge's READ COMPLETES (`d5` grant 16, `d6` grant
17), the model grants at 17 in both.  **This is an EU data-dependency question,
not a display-register question**, and folding it into signature 1 would be
exactly the fitting this campaign forbids.

**(c) WHY NOTHING WAS LANDED.**  Both signatures sit in the model's prefetch /
eval arbitration — M1, M2r, M7, M21, M22 — which is the most heavily measured
surface in `biu_timed.cpp` and which the whole 7.3M-case ladder rides on.
Signature 1 needs the grant cadence after a cancelled display at w0 alone (the
model is already right at w1, so it is not a missing rule but a wrong one clock
in one regime); signature 2 needs the acknowledge pair's spacing to be taken
from the announcement.  **Two mechanisms, two authorising arguments, and neither
is one term.**  B1's bar was written to be missable and is **NOT MET**; B2 is the
registered outcome and no code was written for either.

*Falsifiers, registered for whoever takes it.*  **B-1**: make the wake's grant
after a cancelled HALT display land at `H + 1` at w0 and all 13 signature-1
cells (10 S16 + 3 sweeps) must close while w1/w2/w3, the four HLT sweeps' other
cells, the 11,200 `HLT.NMI` goldens and the whole §79.F ladder do not move.
**B-2**: take the acknowledge pair's spacing from the first acknowledge's
ANNOUNCEMENT and all 13 signature-2 cells (16 S16 `B_late` at `d3,d4,d5` minus
the `d3` overlap, plus 3 sweeps) must close under the same conditions.  A
partial close, or a close that moves any other cell, is a REGISTERED FAILURE and
is reverted.

### §79.H THE RATCHETS THAT MOVED, ITEMISED

| ratchet | before | **after** | which change |
|---|---|---|---|
| **NEW** — the S16 walk, **the MODEL's leg** | never scored | **1,249 / 1,371** (pre-F54 **1,225**) | F54's model leg |
| — per wait level | 337 · 325 · 294 · 269 | **343 · 331 · 300 · 275** | F54's model leg |
| the model's S16 `busstat_other` | 34 | **10** | F54's model leg |
| §78.I's model column | 3 wrong ways | **WITHDRAWN — one wrong integer**, §79.A | the rig fix |
| **everything else in `standing_gates.md` §B** | — | **re-measured, not inherited; not one figure moved** | — |

### §79.I WHAT THIS SITTING DID NOT DO, AND THE STATE IT LEAVES

* **NO BOARD CONTACT, NO FLASHING, `use_core` NEVER SET.**  The board still
  carries FLASH #6, which predates F53 and F54.
* **NO `hdl/` FILE WAS TOUCHED** (`git diff -- hdl` EMPTY), so **G6 is not
  triggered and no Quartus figure is claimed**.  The ucore's numbers here are
  re-measurements of §78's binary, not new builds.
* **Family B is PARTITIONED and BOOKED** (§79.G) with two falsifiers and no code.
* **The model's `qop` (39) and `E_ube` (30) S16 classes are BOOKED, NOT OPENED.**
  `E_ube` is F53's UBE half — the address phase loads UBE and then HOLDS it —
  which the ucore has and the model does not; it is **5 of the model's 11 HLT
  sweep misses** and it is the obvious next model landing.
* **H7, family D, the 8080 work and H3-B were not opened.  No memory file was
  touched.  Codex was not launched.**

## §80 SESSION SM3, SITTING 19 — **THE MODEL'S F53 LEG: FAMILY E IS THE ONE-SHOT'S THREE PINS, NOT ONE, AND +30 S16 / +5 SWEEP CELLS FALL OUT OF TWO SENTENCES THAT WERE ALREADY WRITTEN DOWN.  AND THE FLASH MILESTONE, WHOSE OWN RE-PROOF FOUND THAT F53's ADDRESS HALF IS NOT IN THE ucore AT ALL — IT IS IN `tb_v30_core`'s COMPOSER.**

**2026-08-05, branch `ucsim`, from HEAD `d02671fbe4`.**  The pre-registration is
`docs/notes/sm3_s19_prereg_2026-08-05.md`, committed as `96a9e782c9` **before
`sim/` was touched**, and §B's is `sm3_s19b_prereg_2026-08-05.md`, committed
**before board contact**.  This section reports against both and does not
restate them.

> **Standing principle, applied throughout.**  *"A guiding principal here needs
> to be simplicity.  This is 80's era hardware, they aren't wasting silicon on
> anything that isn't necessary.  Complex or confusing behavior that we see is
> likely to be simple systems interacting in ways you do not fully understand
> yet."*

---

## §80.A THE MODEL'S F53 LEG

### §80.A.1 THE BASELINE, AND WHY §79.I's BOOKING WAS TOO NARROW

§79.I booked the model's 30-cell `E_ube` S16 class as *"F53's UBE half, which
the ucore has and the model does not"*.  Measured per cell before anything was
written, the class is **35 cells — 30 S16 + 5 sweeps — and every one of them has
the IDENTICAL SIX-DIFF SIGNATURE**:

* S16, form `HLT.INT` only, all six programs: **w2 `d10`,`d11`** (12) and
  **w3 `d12`,`d13`,`d14`** (18).
* sweeps, form `HLT.INT`: **`s13-hltsweep-w2` `idx 10,11`**,
  **`-w3` `idx 12,13,14`** (5) — i.e. **5 of the model's 11 sweep misses**, as
  §79.I said, and the other 6 are family B.
* first divergence `(12, ube, 0, 1)` at w2 and `(14, ube, 0, 1)` at w3; the
  remaining five diffs are `ube` on the next row and **`bus`/`data` on the two
  rows after that**.

**Those `bus`/`data` diffs are the half §79.I missed.**  Read off
`s13-hltsweep-w2 HLT.INT idx 10`, golden `G` against the model `M`:

| row | | bus | ube | data | busstat | T |
|---|---|---|---|---|---|---|
| 9 | G=M | `057CB4` | 1 | `7CB4` | CODE | T3 |
| 10 | G=M | `067CB4` | **0** | `7CB4` | CODE | Tw |
| 11 | G=M | `067CB4` | 0 | `7CB4` | CODE | Tw |
| 12 | **G** | **`067CB4`** | **0** | **`7CB4`** | PASV | T4 |
| 12 | **M** | `067CB2` | **1** | `7CB2` | PASV | T4 |
| 13 | **G** | `007CB4` | 0 | `7CB4` | INTA | Ti |
| 13 | **M** | `007CB2` | 1 | `7CB2` | INTA | Ti |

Rows 9-11 are the wake fetch's ANNOUNCEMENT, a multi-clock display window
because the HALT pseudo-cycle still owns the bus: row 9 is its display clock
(A19-16 = its own nibble `5`), rows 10-11 are `data_ps(CS)` = `6` — F53's
address one-shot, which the model already had at M23 — and UBE turns 0 on row
10, one clock after the status (M2).  **Then the announcement is WITHDRAWN**,
and on row 12 — the HALT pseudo-cycle's own T4 — silicon shows the withdrawn
cycle's **three** pins still standing.  The model repainted all three with the
HALT's own, and row 13 follows because an INTA freezes the FLOATING AD into its
access on its display clock (`biu_timed.cpp` 357), so the wrong retention
propagates a cycle further.

### §80.A.2 THE LAW — TWO SENTENCES, NEITHER OF THEM NEW, AND THEY ARE ONE MECHANISM

> **(i) F53b.**  UBE is loaded by the ADDRESS PHASE and then HELD; it is not
> re-driven by a cycle that is merely running.
> **(ii) F51.**  A HALT pseudo-cycle has NO DATA PHASE; after its address phase
> it drives nothing and the pads hold.

`r.ube_n = (ci_ == 0) ? cur_.ube_n : last_ube_` and one `else if
(!cur_.is_halt)` on the body branch.  No new constant, no per-delay table, no
per-program case, **no new state** — the `last_*` retention registers already
existed and the idle branch already used them.  Where no announcement
intervenes, "hold" and "re-drive" are the SAME VALUE by construction, which is
why 168,997 w0 goldens cannot see either.

### §80.A.3 THE RESULT, REPORTED AS REGISTERED

`sim/build/v30sim` inputs `cec517328db68299…`, artifact
`c564a9c775b1307b…`.

| | registered bar | **measured** |
|---|---|---|
| **P1** | the 35 `E_ube` cells CLOSE | **S16 30 → 0, sweeps 5 → 0** — **MET** |
| **P2** | S16 **1,249 → 1,279**, +30/−0, per wait **343 · 331 · 312 · 293** | **1,279 / 1,371**, **gained 30, lost 0** cell for cell, **343 · 331 · 312 · 293** — **MET** |
| **P3** | the four HLT sweeps **272 → 277** = `91/97 · 95/95 · 46/46 · 45/45` | **277 / 283**, exactly those four — **MET** |
| **P4** | residue exactly `busstat_other` 10 · `B_late` 16 · `qop` 39 · `ARCH` 30 | **identical, `E_ube` absent, no class grown** — **MET** |
| **P5** | `ulockstep --golden all --cases 50` 17,350 | **17,350 / 17,350 ALL CASES LOCKSTEP** — **MET** |
| **P6** | the §79.F ladder unmoved | **MET except `timed_fuzz`'s EVT column, §80.A.4** — itemised in §80.A.5 |
| **P7** | the ucore NOT TOUCHED | **`git diff -- hdl` EMPTY** — **MET** |
| f1 f2 f3 f4 f5 f7 | — | **DID NOT FIRE** |
| **f6** | — | **FIRED.  §80.A.4.** |

### §80.A.4 **f6 FIRED, AND IT IS REPORTED AS FIRED — WITH THE ERRATUM THAT IT WAS BADLY WRITTEN**

`timed_fuzz --core sim --evt-replay` moved **EVT 782 → 783** and **COMBINED
2,054 → 2,055**.  REGISTERED is **1,272 to the seed** and `b2-tranche` is
**154 / 188**, both unmoved.

**The control — the pre-change source restored, rebuilt, re-run, and the
artifact hashes chained back (`ab4bd9cd…`/`9411e211…` = sitting 18's exactly,
then `cec51732…`/`c564a9c7…` again) — puts the whole move at ONE SEED.**
`mc2/672`, an EVT seed: `DIVERGE → EXACT`, `ndiff 2 → 0`, and its
first-divergence `kind` was **`ube`** — the law's own signature.  **3,241 of
3,242 report records are byte-identical; 1 gained, 0 lost.**  For scale, F53's
ucore landing moved the ucore's own EVT column by exactly one seed too (§77.G);
whether it is the same seed was not measured here.

> **ERRATUM against my own pre-registration.**  f6 was written as *"moves off
> `1,272 / 782 / 2,054` by a single seed"* — **symmetrically**, so it cannot
> tell a monotone gain from collateral damage, which is the only thing a
> falsifier in that slot is for.  It fired on a **+1 with 0 lost**.  The
> wording is left as committed and the correction is here; the disposition is
> taken on the per-seed control and not on the total, and **the change
> STANDS**.  The falsifier that should have been written, registered here for
> whoever takes the next model landing: **any seed LOST, on either column.**

### §80.A.5 THE LADDER — EVERY CELL RE-RUN ON THE FINAL BINARY

| gate | standing | **measured** |
|---|---|---|
| `timed_gate v0.1 --forms all` | 169,000 | **169,000 / 169,000, row-diffs 0** |
| `v0.1-w1` / `-w3` | 1,200 each | **1,200 / 1,200** each, row-diffs 0 |
| `EB` at w1 | 200 | **200 / 200** |
| the four `evt` cells | 200 / 1,200 / 200 / 1,200 | **identical**, row-diffs 0 |
| `w1evt-biased` | 1,200 | **1,200 / 1,200** |
| **the four HLT sweeps** | 272 | **277 / 283** — RAISED by 5 |
| the 11,200 `HLT.NMI` goldens | — | **200 / 1,000 / 10,000**, row-diffs 0 |
| `check_boot --timed 220` | MATCH | **MATCH over 220 rows** |
| `timed_scenario` | 18 / 0 / 9 | **18 PASS, 0 FAIL, 9 SKIP** |
| `timed_enter_replay` | 154 ×5 | **154/154 ×5** |
| `timed_ins_replay --raw` | 1,312 / 2,624 | **rails 1,312/1,312 · vs-chip 2,624/2,624**, 173,556/173,556 same-T1 |
| `timed_wvec_gate` | 88/88, +0.0 % | **88/88, 16,048 vs 16,048, +0.0 %** |
| `timed_lawcards` | 8 GREEN / 0 RED / 3 UNRESOLVED | **GREEN 8 / 11 scored, 3 UNRESOLVED, 0 RED** |
| `timed_fuzz --core sim --evt-replay` | 1,272 · 782 · 2,054 | **1,272 · 783 · 2,055**, `INVALIDATED` 0 — §80.A.4 |
| `timed_fuzz … b2-tranche` | 154 / 188 | **154 / 188** |
| `ulockstep --golden all --cases 50` | 17,350 | **17,350 / 17,350** |
| `simbin --disasm` · `pla3_check` | 1,285 · 21 | **PASS (1,285 rows)** · **OK (21)** |
| **the ucore** | — | **NOT TOUCHED.  `git diff -- hdl` EMPTY** |

### §80.A.6 THE RATCHETS THAT MOVED, ITEMISED

| ratchet | before | **after** | which change |
|---|---|---|---|
| the four HLT delay sweeps, **the MODEL** | 272 / 283 | **277 / 283** | the model's F53 leg |
| the S16 walk, **the MODEL's leg** | 1,249 / 1,371 | **1,279 / 1,371** | the model's F53 leg |
| — per wait level | 343 · 331 · 300 · 275 | **343 · 331 · 312 · 293** | the model's F53 leg |
| the model's S16 `E_ube` class | 30 | **0 — the class is GONE** | the model's F53 leg |
| `timed_fuzz --core sim` EVT | 782 / 1,008 | **783 / 1,008** | the model's F53 leg (`mc2/672`) |
| `timed_fuzz --core sim` COMBINED | 2,054 / 2,710 | **2,055 / 2,710** | the model's F53 leg |
| **NEW** — S16, `tb_v30_core`, **ROWS ONLY** | did not exist | **1,321 / 1,371** (`sm3_s16_fabric.py offline`) | the instrument, §80.B |

---

## §80.B THE FLASH MILESTONE — **F53 AND F54 ARE IN FABRIC, AND SO IS F55**

**FLASH #9, 2026-08-05.**  Board contact: the reachability + single-writer check
(recorded in the pre-registration as having happened), then one flash and five
capture legs.  `div_guard` **PINNED** on every probe, both ends; **0 transport
errors**; no wedge; `board_idle()` clean at the close.

### §80.B.1 THE PROMOTION RULE, MET FIRST

`quartus_gate.py` at HEAD, ONE clean CONTROL/DEFAULT build from a deleted
`db`/`incremental_db`, compile rc 0 in **571 s**: **E1 PASS · E2 PASS** (0 stage
errors, 0 error lines, map/fit/asm all Successful) **· E3 45.49 MHz** (bar ≥ 32)
**· E4 +9.146 ns · E5 TNS 0.000**, setup AND hold, every domain.  RECORDED, not
barred: **ALMs 11,126 / 41,910 (27 %)**, 0 latches, 0 `lpm_divide`.  Receipt
**`2bf170fa9eee15f7…`**, input manifest **88 files `567b11fffd6414a6…`**, which
is **byte-identical to sitting 17's** — the check that says `hdl/` has not moved
since F54.  The receipt records the tree `96a9e782c9-dirty`; the dirt was §A's
`sim/biu_timed.cpp` and docs, and `hdl/` was clean.

The FLASHED bitstream is the **RETENTION** build from the same regenerated
`.qsf` (`quartus_gate` puts the `.qsf` back after its own build, §70.7):
`quartus_map --verilog_macro="X1_AD_RETENTION=1"` + `fit` + `asm` + `sta`.
**0 errors, Fmax 44.99 MHz, worst setup +9.023 ns, TNS 0.000 on every domain,
ALMs 11,205 / 41,910 (27 %), 0 latches, 0 `lpm_divide`**; recorded as
`~/.cache/ucsimt-tmp/sm3s19/quartus_gate_retention.json`, receipt
`fdce0639299276c9…`.  *Its 88-file manifest hash is NOT the control's, because
Quartus had appended pin assignments to the revision `.qsf` by the time it was
parsed; the GATE is the control build, and this row is RECORDED.*

**FLASH #9** through `sw/safe_flash.sh` with its VERIFY leg:
`nec_test_ucore.sof` **`01aca4c0b1e7d75514dd9a41c9b81b82fdc3af1c77b4d2c6a0413228974e58f2`**,
`.rbf` `58154c546dbad34880f82ea1afe03f79f7a2d5413c3cb0b3472b9dd4487a94de`,
VERIFY **OK**, `flash_log.jsonl` 11 → **12 entries**.

### §80.B.2 THE RESULTS, REPORTED AS REGISTERED

| | prediction | **measured** |
|---|---|---|
| **Q1** first light `check_ab_hw all 800` | MATCH ×3 | **MATCH / MATCH / MATCH over 800 rows** — **MET** |
| **Q2** `x1_fabric baseline --leg fab_f9` | **268 / 283**, = `tb_sys ret` cell for cell | **268 / 283**, and against `tb_sys ret` over all 283: **0 PASS/FAIL disagreements, 0 differing first-divergence coordinates** — **MET** |
| **Q2a** the 15 failing cells, NAMED IN ADVANCE | the list in §B.3 | **exactly that list, coordinate for coordinate** — **MET** |
| **Q3** socket control `use_core=False` | 49 / 49 | **49 / 49** — **MET** |
| **Q4** **the S16 population's FIRST fabric leg**, rows only | **1,291 / 1,371**, 0 disagreements vs `vsys_ret` | **1,291 / 1,371**, **0 PASS/FAIL disagreements and 0 differing coordinates over all 1,371** — **MET** |
| **Q4a** its socket control | identical to the golden | **41 / 41** — **MET** |
| **Q5** b3 priority tranche | `chip_f9` 178/178, `core_f9` 176/178, `bs = 2` | **178 / 178** and **176 / 178 (98.9 %)**, residue **`bs = 2`**, 0 errors in 400 captures — **MET** |
| **Q6** `use_core=0` chip proof AFTER everything | MATCH 800 | **MATCH over 800 rows** — **MET** |
| **Q7** `div_guard` | PINNED both ends of every leg | **PINNED, every probe** — **MET** |
| **Q8** transport | 0 errors, `board_idle` clean | **0 errors, no wedge, `board_idle()` clean** — **MET** |

Per suite the fabric sweeps are the offline `system_large` column cell for cell:
`s10-w0` `HLT.INT` **44/48** `HLT.RES` **47/49**; `s10-w1` **44/46** and
**49/49**; `s13-w2` **18/21** and **25/25**; `s13-w3` **16/20** and **25/25**.

### §80.B.3 **WHAT IS NOW ESTABLISHED IN FABRIC**

**(a) F53 AND F54 ARE IN SILICON'S INSTRUMENT AND THEY HOLD THERE.**  The
sweeps were **265/283** on FLASH #6, which predates both; they are **268/283**
now, and the whole `ube` column is correct on all 35 family-E cells where it was
wrong on every one before.  F54's 42-cell `HLT.NMI` band and F53's 72 family-A/C
nibble cells carry **no** signature in fabric on the S16 leg either — the 80
residual S16 cells are 26 family-B, 24 family-D and the 30 of §80.B.3(b), and
the catch-all is empty.

**(b) F55 IS CONFIRMED IN FABRIC, ON A DIRECTED PREDICTION.**  The 35 cells were
named in advance, from an instrument-vs-instrument disagreement found while
re-proving `tb_sys`, and **all 35 failed in fabric with the predicted
first-divergence coordinate and no others did.**  `halt_hold` keeps
`ad_oe_addr` asserted for the whole HALT pseudo-cycle and publishes
`r_cur_addr` on every clock of it; silicon leaves that address there by
**retention**, not by **drive**.  `tb_v30_core.sv`'s `cycle_live` floats those
clocks, so the DEFAULT TB has been scoring the cells green **on the
instrument's authority, not the core's** — `standing_gates.md`'s meta-finding
#5, exactly one law later, and this time caught by prediction rather than by
accident.  **F53's UBE half is in the RTL; its ADDRESS half never was.**
The fix is ONE TERM and is deliberately **NOT LANDED** (it would have put an
unregistered change into the milestone's bitstream); its falsifier is in
`sm3_s19b_prereg_2026-08-05.md` and it is **the obvious next RTL landing**.

**(c) A THIRD INSTRUMENT IS NOW ON THE LADDER AND IT AGREES WITH FABRIC TO THE
CELL.**  `tb_sys ret` predicted **268/283** and **1,291/1,371** before the board
was touched and was right on **1,654 of 1,654 cells** across the two
populations, PASS/FAIL and coordinate alike.  Where `tb_v30_core` and `tb_sys`
disagree, **fabric sides with `tb_sys` every time** — which is the general rule
this sitting establishes, and it is worth more than either number.

### §80.B.4 THE RESTING STATE

The board carries **FLASH #9**, the retention build, `use_core` **False**,
`cfg 0xff0008` (`clk_div` 8 = `DIV_OF_RECORD`), `ctrl 0x5`, `board_idle()`
clean.  The disposition is §73.8's and it is taken on the measurement: the
retention model is on the OBSERVATION path (`hb_ad_sample`) under
`cfg_use_core ? core_ad_eff : NEC_AD`, so the socket position is unaffected by
construction, and `check_ab_hw chip 800` run AFTER the whole sitting is
**MATCH over 800 rows**.  FLASH #6's `.sof 626fb30ebee2…` remains on disk.

### §80.B.5 THE RATCHETS THAT MOVED, ITEMISED

| ratchet | before | **after** | which change |
|---|---|---|---|
| the fabric HLT sweeps | 265 / 283 (FLASH #6) | **268 / 283 (FLASH #9)** | F53 + F54 reaching fabric |
| `tb_sys` `ret`, the Verilated integration | 265 / 283 (s6) | **268 / 283** | same |
| `tb_sys` `base` | 146 / 283 | **146 / 283 — unmoved** | control |
| `tb_v30_core` offline, the four sweeps | 265 (s12) | **273 / 283** | F53 + F54, unchanged since s17 |
| **NEW** — S16, ROWS ONLY, `tb_v30_core` | did not exist | **1,321 / 1,371** | the instrument |
| **NEW** — S16, ROWS ONLY, `tb_sys ret` | did not exist | **1,291 / 1,371** | the instrument, and F55 |
| **NEW** — **S16 IN FABRIC**, ROWS ONLY | **never captured** | **1,291 / 1,371** | FLASH #9 |
| the b3 priority tranche | `chip_f5` 178, `core_f5` 176 | **`chip_f9` 178 / 178, `core_f9` 176 / 178** | FLASH #9; §73.9's re-capture debt for #6/#7/#8 is DISCHARGED at #9 |
| the board's bitstream | FLASH #6/#8 `626fb30ebee2…` | **FLASH #9 `01aca4c0b1e7…`** | this sitting |

`sm3_s16_score.py --core ucore` was re-measured, not inherited: **1,294 / 1,371**,
per wait **346 · 328 · 318 · 302**, census `busstat_other` 10 · `B_late` 16 ·
`D_tstate` 24 · `ARCH` 27 — identical to §78's.

### §80.C WHAT THIS SITTING DID NOT DO, AND THE STATE IT LEAVES

* **NO `hdl/` FILE WAS TOUCHED** — `git diff -- hdl` is EMPTY for the whole
  sitting.  **F55 is BOOKED, NOT LANDED**, with its falsifier written down.
* Family B stays **PARTITIONED and BOOKED** (§79.G); its two falsifiers are
  unclaimed.  The model's `qop` 39 S16 class is untouched.
* Family D, H7, H3-B and the 8080 work were not opened.
* **No memory file was touched.  Codex was not launched.**

---

## §81 SESSION SM3, SITTING 20 — **F55 IS LANDED AND THE 273-vs-268 INSTRUMENT SPLIT IS CLOSED FROM BOTH ENDS: THE CORE STOPS DRIVING, AND THE COMPOSER STOPS GUESSING.  AND H7's FLOOR DOES NOT REPRODUCE — 0 OF 30, WHILE 162 OF 163 NON-FLOOR SEEDS DO.**

**2026-08-05, branch `ucsim`, from HEAD `6bc0656231`.**  The pre-registration is
`docs/notes/sm3_s20_prereg_2026-08-05.md`, committed as `222392bfa9` **before
any `hdl/` file was touched and before the board was contacted**.  This section
reports against it and does not restate it.

> **Standing principle, applied throughout.**  *"A guiding principal here needs
> to be simplicity.  This is 80's era hardware, they aren't wasting silicon on
> anything that isn't necessary.  Complex or confusing behavior that we see is
> likely to be simple systems interacting in ways you do not fully understand
> yet."*

---

## §81.A F55 — DRIVE BECOMES RETENTION

### §81.A.1 THE BASELINE, MEASURED BEFORE ANYTHING WAS WRITTEN

`tb_sys` receipts `77ec467566976452…` (base) / `f28decf4a59471d4…` (ret), both
`up to date` against HEAD — i.e. **byte-identical to the pair §80.B ran**, which
is the check that `hdl/` had not moved since the milestone.

| leg | measured before |
|---|---|
| `x1_retention offline` (`tb_v30_core`) | **273 / 283** |
| `x1_retention` `base` / `ret` | **146** / **268** / 283 |
| `x1_retention score` BAR (i) / BAR (ii) | **NOT MET** — 5 survivors, 5 cells differing from offline |
| `sm3_s16_fabric offline` / `vsys_ret` | **1,321** / **1,291** of 1,371, **30** disagreements, **0** differing coordinates |

The 5 + 30 are §80.B.3(b)'s F55 cells exactly, and the same 35 the model closed
at §80.A.

### §81.A.2 THE CHANGE — TWO TERMS, AND THE SECOND ONE IS THE POINT

> **F51.**  A HALT pseudo-cycle has NO DATA PHASE.  After its address phase it
> **drives nothing**, and the pads hold whatever was last put on them.

`v30u_biu.sv` rendered the second clause as a **DRIVE**:
`halt_hold = r_run && r_cur_halt` held `ad_oe_addr` asserted for the whole
pseudo-cycle and republished `r_cur_addr` on every clock of it.  A pad that is
DRIVEN and a pad FLOATING at its last driven value are the same value **by
construction** — until a multi-clock announcement takes the pads in between and
is then WITHDRAWN.  That is the whole of family E's address half, and it is the
same sentence as F53b one pin over: *a pad is loaded by a PHASE and held
otherwise.*

1. `halt_hold` → `halt_addr = r_run && r_cur_halt && (r_ts == TS_T1)`.  The
   one-shot ends with the address phase.  Its `ad_oe_addr` contribution is then
   wholly subsumed by the existing `r_ts == TS_T1` term, and its `ad_o` branch
   leaves the HALT's own T1 byte-identical.
2. **`ad_oe_ps` gains `!r_cur_halt`.**  Without it, (1) merely swaps one drive
   for another — the PS/data drive would take the pads at the HALT's T2.  With
   it, **all three enables are LOW for the body of a HALT**, `AD` floats, and
   what the pads show is retention.

No new flop, no new constant, no per-case anything.  `ss_lint` confirms it:
dropping an enable is combinational.

### §81.A.3 THE COMPOSER — **A3b, PRE-REGISTERED AS CONDITIONAL AND EARNED**

The RTL change alone closed the split (`ret` 268 → 273, `vsys_ret` 1,291 →
1,321, `tb_v30_core` unmoved), so the two instruments AGREE.  A3b asked the
second question: **do they agree for the right reason?**

`tb_v30_core.sv`'s composer inferred the core's drive from the bus protocol —
eight wires, one of which (`cycle_live`'s `lat_type != 3'b011`) floated a
HALT-typed cycle's body **whatever the core did there**.  That is
`standing_gates.md`'s meta-finding #5 in the flesh: *a comparator that
substitutes a value is asserting a mechanism.*  It is why this TB scored the 35
cells green for eleven sittings on the INSTRUMENT'S authority.

The composer now keys on **`AD_OE`** — the core's own pad output enable (task
#37), the wire `system_large` already uses and the fabric agrees with on 1,654
of 1,654 cells.  **Two lines replace eight wires.**  Engine-neutral: `AD_OE` is
a port of `v30_core`, so the archived `fsm` core publishes it too.  `mem_drive`
stays, because the TB's MEMORY is the bus's other real driver — that is the
harness's own truth, not an inference about the core.

**It was landed ONLY on a zero-delta**, as registered: sweeps **273/283 cell for
cell**, S16 **1,321/1,371 with 0 differing coordinates**, `check_core --opcodes
all` **169,000/169,000**, and the whole ladder of §81.A.5.  **Not one cell
moved.**  That is the only form in which an instrument may be rewritten.

### §81.A.4 THE RESULT, REPORTED AS REGISTERED

| | registered bar | **measured** |
|---|---|---|
| **P1** | the 35 F55 cells CLOSE | **5 sweeps + 30 S16, all** — **MET** |
| **P2** | `ret` **268 → 273**, BAR (i) and BAR (ii) MET | **273/283, 127 of 127 closed, 0 survivors, 0 cells differing from offline, VERDICT MET** — **MET** |
| **P3** | `vsys_ret` **1,291 → 1,321**, 0 disagreements | **1,321/1,371, 0 PASS/FAIL disagreements and 0 differing coordinates over all 1,371** — **MET** |
| **P4** | `tb_v30_core` does **NOT MOVE** | **273 / 283 and 1,321 / 1,371, the SAME failing cells** — **MET.**  *The term was not cut wider than the law.* |
| **P5** | `sm3_s16_score --core ucore` **1,294** | **1,294 / 1,371**, per wait **346 · 328 · 318 · 302**, census `busstat_other` 10 · `B_late` 16 · `D_tstate` 24 · `ARCH` 27 — **MET** |
| **P6** | `ulockstep` **17,350** | **17,350 / 17,350 ALL CASES LOCKSTEP** — **MET** |
| **P7** | the ladder unmoved | **MET** — §81.A.5 |
| **P8** | `ss_lint` rc 0, 201 flops | **rc 0, 201 flops, 0 UNMAPPED, SS_COUNT 218** — **MET** |
| **P9** | **G6** E1-E5 | **PASS.  E1 PASS · E2 0 errors · E3 47.15 MHz · E4 +9.335 ns · E5 TNS 0.000 setup AND hold, every domain.**  ALMs **11,104 / 41,910 (26 %)**, 0 latches, 0 `lpm_divide`.  Receipt **`2f73672c179d278b…`**, inputs 88 files **`c1cae4f64cc35759…`** — **MET** |
| **P10** | `git diff -- sim` EMPTY | **EMPTY** — **MET** |
| f1 … f8 | — | **NONE FIRED** |

**Fmax went UP (45.49 → 47.15 MHz) and ALMs went DOWN (11,126 → 11,104).**
Deleting a drive is a net simplification, in the fitter as well as in the
sentence.

### §81.A.5 THE LADDER — EVERY CELL RE-RUN, TWICE (F55, THEN THE COMPOSER)

`check_core --opcodes all --cases 0` **169,000 / 169,000** cycles AND arch ·
`f4a_boundary` **160** · `f0lock_tranche` **400** · the 23 `v0.3` block-I/O
forms **229,999 / 229,999** · `v0.1-w1` / `-w3` **1,200** each · `EB` at w1
**200** · the four `evt` cells **200 / 1,200 / 200 / 1,200** · `w1evt-biased`
**1,200** · `check_boot --core ucore --timed 220` and `--timed 400` **MATCH** ·
`ulockstep --golden all --cases 50` **17,350** · `timed_wvec_gate --core ucore`
**88/88, +0.0 %** (16,048 vs 16,048) · `timed_enter_replay --core ucore`
**154/154 ×5** · `timed_ins_replay --core ucore --raw` rails **1,312/1,312**,
vs-chip **2,624/2,624**, same-T1 **173,556/173,556** ·
`timed_fuzz --core ucore --evt-replay` REGISTERED **1,490** / EVT **913** /
COMBINED **2,403** **TO THE SEED** (every wait-class and per-bank sub-total
identical), `INVALIDATED` 0, `ENGINE ABORTS` 0, `BOUND WARNINGS` 5 ·
b2 tranche **172 / 188** · `check_core --ce-div 4 --ce-hold-check`
`CE_HOLD_VIOL 0` · `check_ab_sim --core ucore` **187 rows MATCH** ·
`timed_lawcards` **8 GREEN / 0 RED / 3 UNRESOLVED** · `gen_ucore_qsf --check`
PASS · `check_ucore_tables` **9,988** · `pla3_check` **21** ·
`simbin --disasm` **1,285** · `test_artifact` **45/45**.

### §81.A.5a **A STALE QUICK-REFERENCE FIGURE, CORRECTED UPWARD — AND IT IS NOT A MOVEMENT**

`standing_gates.md` and `CLAUDE.md` quote the ucore's b2 tranche as
**171 / 188**, citing §44.2.  It measures **172 / 188**, and §66.3 **RAISED it
171 → 172 at SM3 sitting 6** (the TB `IOW` fix); every sitting since §69 has
reported 172.  The quick reference predates that raise.  **F55 did not move it**
— this is the §26.11 / U3 pattern again: the quick reference disagreeing with
the ledger's own delta row, corrected against the artifact and not against
recall.  V5 remains the standing REGISTERED FAILURE.

### §81.A.6 A CONSEQUENCE FOR §56.3a

`x1_retention score`'s own **BAR (i)** and **BAR (ii)** now report **MET** on
the Verilated leg.  They had been NOT MET with exactly 5 survivors, and the 5
were these cells.  §73.9a's erratum about the fabric bars is untouched; what
moved is the offline leg's own verdict.

### §81.A.7 THE FABRIC PREDICTION, REGISTERED AND NOT TESTED

**No board was flashed and no bitstream was put on the board this sitting.**
Registered for FLASH #10: `x1_fabric baseline` **268 → 273** and
`sm3_s16_fabric fabric` **1,291 → 1,321**, the same 35 cells closing and no
others moving.  §80.B.3(c) is the ground: `tb_sys ret` has predicted fabric on
**1,654 of 1,654** cells, PASS/FAIL and coordinate alike.

### §81.A.8 THE RATCHETS THAT MOVED, ITEMISED

| ratchet | before | **after** | which change |
|---|---|---|---|
| `tb_sys ret`, the four HLT sweeps | 268 / 283 | **273 / 283** | F55 |
| `tb_sys ret`, S16 rows only | 1,291 / 1,371 | **1,321 / 1,371** | F55 |
| `x1_retention` BAR (i) / BAR (ii) | NOT MET, 5 survivors | **MET / MET, 0 survivors** | F55 |
| `tb_v30_core`, the four HLT sweeps | 273 / 283 | **273 / 283 — UNMOVED** | P4, the bar |
| `tb_v30_core`, S16 rows only | 1,321 / 1,371 | **1,321 / 1,371 — UNMOVED** | P4, the bar |
| **the two offline instruments** | disagreed on 35 cells | **AGREE on all 1,654** | F55 + A3b |
| G6 Fmax | 45.49 MHz | **47.15 MHz** | F55 (a deleted drive) |
| G6 ALMs | 11,126 | **11,104** | F55 |
| the ucore's b2 tranche, AS QUOTED | 171 / 188 (stale) | **172 / 188** | §81.A.5a — a correction, not a move |

---

## §81.B H7 — THE REPETITION RE-CAPTURE.  **THE FLOOR DOES NOT REPRODUCE, AND THE POPULATION THAT DOES NOT REPRODUCE *IS* THE FLOOR.**

### §81.B.0 THE BOARD

`root@mister-nec` reachable, `up 23 days 18:30`.  **Single-writer check: no
`v30` / serve / python process on the board.**  The board carries **FLASH #9**
(`01aca4c0b1e7d755…`); **NOTHING WAS FLASHED**, `use_core` **False** explicitly
on every capture, `div_guard` **PINNED** (`div=8`, 4 MHz, commanded by this
connection) at both ends of every leg, `board_idle()` at both ends,
**0 transport errors, 0 wedges** in **1,089 captures**.

### §81.B.1 THE CELL

`sw/sm3_h7_repeat.py`.  The population is **DERIVED, never listed** — every
banked seed with `evt.pin == 1` whose measured gap is 12, computed through
`sm3_nmigeom.one` itself.  30 seeds, **mc1 26 / t30-raw 4 / mc2 0**, reproducing
§68.5's bank association exactly.  Per seed the image is REGENERATED from
`(cid, k, ov)` and **HASH-CHECKED** against the banked `image_sha256`; **0
GEN-DRIFT**.  Four legs:

| leg | population | reps | captures |
|---|---|---|---|
| **C1**, the pin-0 control | 10 banked INT seeds across all three banks | 3 | 30 |
| **the floor** | the 30 at banked gap 12 | 10 | 300 |
| **C2**, ADDED (§81.B.4) | the 18 at banked gap 13 | 10 | 180 |
| **C3**, ADDED (§81.B.4) | the whole pin-1 population, 193 with a recognition | 3 | 579 |

### §81.B.2 THE RESULT, REPORTED AS REGISTERED

**THE REGISTERED OUTCOME IS (iv), AND IT IS REPORTED AS (iv).**  Outcome (ii)
was *"every repetition of every seed reads gap 13"*; 14 of the 30 do and **16
read ABOVE 13** (14, 15, 16, 17, 20, 21, 22, 23, 34, 91).  Per the
pre-registration that is *"reported AS MEASURED and NOT folded into (i)-(iii)"*,
and **no invalidation is written on it** — see §81.B.5.

| | |
|---|---|
| **C1**, the pin-0 control | **30 of 30 repetitions reproduce the banked INTA1 gap EXACTLY** — banked gaps 7, 8, 9, 11 and 12, *including two seeds banked at 12 which read 12 on every repetition*.  The rig and the `A` derivation are sound in this session |
| **DETERMINISM** | **193 of 193 seeds are identical across all their repetitions.  ZERO within-seed variance anywhere, in 1,089 captures.**  Outcome (iii) — sub-clock marginality WITHIN a session — is **REFUTED at its point estimate** |
| **the floor** | **0 of 30 reproduce.**  Not one repetition of any of them reads 12 |
| **C2 / C3** | **162 of 163 NON-floor seeds reproduce their banked gap exactly.**  The single exception is `mc1/soup_2468`, banked 13 |
| **the minimum** | over **579** fresh repetitions of the whole pin-1 population the minimum gap is **13**.  **Repetitions reading 12 or less: 0** |
| **the direction** | **31 movers, all 31 LATER, none earlier** |

**THE COORDINATE IS SOUND, AND THIS IS THE CHECK THAT MAKES THE ABOVE
READABLE.**  On all 30 floor seeds the fresh capture reproduces `arm` and `A`
**EXACTLY**.  Only `V` — the chip's recognition — moved.  A moved `arm` can
never be read here as a moved `gap`.

### §81.B.3 **THE ROW-LEVEL PICTURE, AND IT IS TWO CLEAN CLASSES**

Diffed against the banked `chip_rows` with the project's own `fuzz_classify.
diff_rows`, the fresh run is **identical to the banked run up to the pin event's
consequences** on every one of the 30 — never earlier — and the first divergence
takes exactly two values:

| class | seeds | first divergence | fresh gap |
|---|---|---|---|
| **one clock late** | **14** | **`A + 11`** | **13** on 12 of them, 14 on 2 |
| **boundary slid** | **16** | **`A + 3`** | 14 … 91 |

* **The 14** (12 at gap 13, 2 at 14).  Rows are byte-identical through
  `A + 10`.  At `A + 11` the banked
  capture shows the NMI vector read's DISPLAY and the fresh one is still PASV;
  the fresh display comes one clock later and its T1 at `A + 13`.  **The entire
  difference is ONE CLOCK at the recognition and nothing else** — the missing
  clock between the bank's 12 and both engines' 13, isolated.
* **The 16.** The first divergence is the **queue status `qs` at `A + 3`** —
  which is §63.2's own *recognition-instant* coordinate, the axis on which the
  bank split `14 at A+3 / 7 at A+4`.  The trajectories then re-converge and the
  vector read lands at the next boundary, wherever that is.

### §81.B.4 **THE TWO ADDED CONTROLS, DECLARED AS ADDED**

C2 and C3 were **NOT pre-registered**; they were run **after** the floor result
was seen, and they are declared as such.  Their purpose was to answer the one
question that would have made the floor result unreadable: *does the current rig
reproduce the banked pin-1 population at all?*

| banked gap | seeds | reproduce | rate |
|---|---|---|---|
| **12** | **30** | **0** | **0 %** |
| 13 | 18 | 17 | 94 % |
| 14 … 409 | 145 | 145 | **100 %** |
| **total** | **193** | **162** | 84 % |

**The population that fails to reproduce IS the floor population, plus one.**

### §81.B.5 THE READING, AND WHY IT IS A READING

The simplest thing that produces this whole table is **one clock in the `A`
coordinate**, not a mechanism in the part:

> `A` is **DERIVED** (`arm + delay + 2`), never measured.  If the rig's actual
> pin-assert instant is one clock later now than in the era those 30 were
> banked, then every **A-LIMITED** recognition moves one clock later in the gap
> coordinate — and every **BOUNDARY-LIMITED** one does not move at all, because
> the boundary has not moved.  A-limited seeds are exactly the ones sitting on
> the floor.

It predicts, and the measurement shows: only floor seeds move (0/30 vs 162/163);
every mover moves LATER and none earlier (31/31); a mover that then misses its
boundary slides to the next one (the 16); and the pin-0 leg, whose INT
recognition is level-driven and not edge-latched, is untouched (30/30).  It also
dissolves §68.5's **BANK ASSOCIATION** without a new number, and it is
consistent with every directed cell ever run — §63.3, §65.1's 160 captures,
§68.5's 640, §72's 768 — all of which floor at **13** because all of them were
captured on the current-era rig.

**IT IS NOT ESTABLISHED.**  What would establish it is a DIRECT measurement of
the assert instant rather than a derivation of it — the pin's own state in the
capture, or an `inv1_recapture holdproof`-shaped directed pulse — and it is
**NOT TAKEN HERE**: it is a new hypothesis and it belongs in its own
pre-registration.  Registered as its falsifier: *if the current rig's assert
clock is measured to be `arm + delay + 2` after all, this reading is refuted and
the 30 are back.*

### §81.B.6 THE DISPOSITION — **INV-2 IS NOT WRITTEN, AND THAT IS THE
PRE-REGISTRATION'S OWN ANSWER**

The pre-registration tied INV-2 to outcomes (ii) and (iii).  The measured
outcome is **(iv)**, whose disposition is *report, do not fold*.  Re-reading a
registered bar onto a better statistic after seeing the data is the manoeuvre
§64.1 booked as an erratum, and it is not done here.

**NOTHING IN THE BANK WAS TOUCHED.**  No file was renamed, no entry edited, no
label changed.  The 1,089 fresh captures are retained with their `sha256` under
`sw/testdata/sm3-h7rep/` beside the banked ones.

**WHAT IS ESTABLISHED, AND IT IS NOT NOTHING:**

* **H7's floor of `A + 12` has NO LIVE EVIDENCE.**  The 30 captures that were
  its entire evidentiary basis do not reproduce, on the rig as it stands, in 300
  repetitions, while 162 of 163 of their neighbours do.
* **Both engines' floor of 13 is silicon's number** on every measurement anyone
  can take today: 579 fresh repetitions of the whole banked population, minimum
  **13**, plus the four directed cells' thousands of captures.
* **Outcome (iii) is refuted**: the effect is not sub-clock jitter *within* a
  session.  Every seed is perfectly deterministic.
* **H7 remains BLOCKED, not CLOSED** — and the reason it is not closed is now a
  named, testable, one-measurement question (§81.B.5) instead of an eliminated
  axis list.

### §81.B.7 THE RESTING STATE

The board carries **FLASH #9**, `use_core` **False**, the divider **PINNED**,
`board_idle()` clean, no serve process left running.  Nothing was flashed.

---

### §81.C WHAT THIS SITTING DID NOT DO

* Family B stays **PARTITIONED and BOOKED** (§79.G); family D, H3-B and the 8080
  work were not opened.
* `sim/` was not touched — `git diff -- sim` is EMPTY for the whole sitting.
* **No bitstream was flashed.**  F55's fabric leg is registered (§81.A.7) and
  belongs to the next flash.
* **INV-2 was not written** (§81.B.6), and the direct assert-instant measurement
  §81.B.5 names was not taken.
* **No memory file was touched.  Codex was not launched.**

## §82 SESSION SM3, SITTING 21 — **FAMILY B IS CLOSED IN BOTH ENGINES, AND BOTH HALVES ARE DELETIONS OR RELOCATIONS, NOT ADDITIONS.  M6 IS REFUTED BY ITS OWN FIRING CENSUS AND IS GONE; THE READ'S COMPLETION CLOCK MOVES TO THE EVAL WHERE EVERY OTHER EVAL-KEYED QUANTITY ALREADY LIVES.  THE MODEL'S HLT SWEEPS ARE 283/283 AND THE ucore's S16 w0 IS 372/372.**

**2026-08-05, branch `ucsim`, from HEAD `cba14841d2`.**  Two pre-registrations,
two landings, four commits: `sm3_s21a_prereg_2026-08-05.md` (`b9c85a4a45`) and
`sm3_s21b_prereg_2026-08-05.md` (`27901d6ef7`), each committed **before its own
diff**.  This section reports against them and does not restate them.

> **Standing principle, applied throughout.**  *"A guiding principal here needs
> to be simplicity.  This is 80's era hardware, they aren't wasting silicon on
> anything that isn't necessary.  Complex or confusing behavior that we see is
> likely to be simple systems interacting in ways you do not fully understand
> yet."*

---

### §82.0 ITEM 0 — THE USER'S DISPOSITIONS, RECORDED FIRST (`53ba661082`)

`ucore_gaps_2026-08-04.md` **FIFTH UPDATE** and the owner rows of
`sm3_residue_census_2026-08-04.md` now carry the 2026-08-05 user decisions:
**family B PURSUE** (this sitting) · **H4-B PURSUE** (next) · **H3-B DEFERRED**
(booked, not worked; *deferred, NOT refuted*) · **`TAIL_EXTRA` SURVEY
authorised** · **the ucore's last two own registered-bank seeds — closers
authorised** · **family D = SCORE VIA `tb_sys`** (the 4 cells move to the
`tb_sys`/fabric instrument column; not patched, not scored on `tb_v30_core`) ·
**the MODEL's own residual debt — ~220 model-only seeds and its 39-seed `qop`
S16 class — FROZEN.**  The freeze is on the model-ONLY residue; shared
mechanisms still land `sim/` first, which is how both halves below were worked.

### §82.1 **THE SURVEY, AND IT CORRECTS §79.G's OWN CELL COUNTS**

New MEASUREMENT tool (**not a gate**): `sw/sm3_famb_survey.py`.  It reads both
regimes **off the GOLDEN alone** — B-1 is *"the golden carries no `HALT` status
row"*, B-2 is *"it does, and the observable is the INTA pair's
announcement-to-announcement gap"* — so the partition is a property of the
population, not of the engine.

| | sweeps | S16 | **per engine** |
|---|---|---|---|
| **B-1** the wake's first prefetch, CANCELLED-display regime | **4** | **14** | **18** |
| **B-2** the acknowledge pair's spacing, display-PRESENT regime | **2** | **12** | **14** |

The 26 S16 cells are `busstat_other` 10 + `B_late` 16, and `B_late` splits
**4 at `(4, busstat)`** (B-1) and **12 at `(17, busstat)`** (B-2).  **The model
and the ucore carry the same 26 cells, cell for cell.**

> **ERRATUM against §79.G's falsifier text.**  It registered B-1 at *"13
> signature-1 cells (10 S16 + 3 sweeps)"* and B-2 at *"13 signature-2 cells …
> minus the `d3` overlap, plus 3 sweeps"*.  **There is no `d3` overlap**, the
> sweeps split **4 / 2** and not 3 / 3, and S16 splits **14 / 12**.  §79.G is
> LEFT AS COMMITTED; this is its correction, and the sitting's bars were
> written on the measurement.

### §82.2 **B-1 = F56.  M6 IS DELETED.**

The clock, derived before anything was touched (`V30SIM_EVALTRACE`; `ET N` is
the eval at the END of clock `N`; capture row = clock − 7):

| clock | |
|---|---|
| end of 8 | the running fetch's COMPLETION eval — refused, `halted_` |
| 9 | its `T4`; `pf_land_from_ = pf_land_to_ = 10` |
| 10 | the bus is free — **for `d ≥ 4` the HALT display takes the register here** (`H = 10`) |
| **end of 10** | the first idle eval — **`.M`, refused by M6** |
| end of 11 | granted; display at 12 = row 5.  **The golden is row 4.** |

§79.G's *"display at `H + 1`"* is the eval M6 refuses.  And **`no_eval_` (M2r)
already covers M6's window at every wait level above zero** — the completion
eval IS at `T4` there, so `no_eval_ == T4 + 1` — which is why family B was a
w0-only residue: not a wait-dependent law, but the one wait level at which the
branch was reachable at all.

**THE FIRING CENSUS — the argument for DELETING rather than narrowing.**
Counted on the branch itself, across every timed population in the tree:

| population | evals reaching the branch and BLOCKED |
|---|---|
| `v0.1`, **169,000** cases | **0** |
| `v0.1-w1` · `-w3` · `w1evt` | **0** |
| `timed_scenario` (18 procs) | **0** |
| `timed_enter_replay` (154) | **0** |
| `timed_ins_replay --raw` (800) | **0** |
| `timed_wvec_gate` (88) | **0** |
| **`timed_lawcards` (228 procs)** — including **C1/C2/C3, the Arm-C sled that MEASURED M6 in T2b 12.1** | **0** |
| the registered + EVT fuzz bank, **3,242 seeds** | **3**, in ONE seed, verdict unmoved |
| the four HLT sweeps + the S16 walk | **19** — every one a cell silicon contradicts |

**M6's own authorising populations no longer reach it.**  This is not a claim
that the T2b measurement was wrong; it is the claim that the rule it authorised
is redundant where it agrees with silicon and wrong where it does not, and that
12.1's consequence (`T4+2` / `T4+4`) falls out of M2r's eval geometry alone.
The refutation is written at the deleted fields' own declaration in
`sim/biu_timed.h`.

**THE LANDING.**  `sim/` (`78c1a7ab39`) loses `pf_land_from_` / `pf_land_to_`
and their three sites — **two fields fewer, none added.**  The `ucore`
(`e0b71ee5e3`) loses the `else if (pl_now)` arm and, with its only reader gone,
`pf_land` / `r_pf_land` / `pl_now` / `set_land` / `pf_land_rst` — **one flop
fewer, none added.**

**THE FIRST MID-REGION SAVE-STATE RETIREMENT.**  `9'h038` held `pf_land`.
s11's precedent retired addresses from the END of the BIU region, where
shortening the dense range suffices; this one is in the middle and the map's
APPEND-ONLY rule forbids renumbering the tail.  So **`9'h038` becomes a HOLE**:
`ss_addr_of` steps over it with one `+1` term, **no symbol changes address**,
and `SS_VERSION` moves **0x84 → 0x85**, `SS_COUNT` **218 → 217**, `SS_TAG`
**0x84DA → 0x85D9**, so a v4 stream can never be read as a v5 one.  The package
says out loud that a SECOND hole is the signal to re-think the region rather
than add a second term.

**THE RESULT, REPORTED AS REGISTERED.**  P1-P7 **ALL MET**, f1-f7 **NONE
FIRED**:

| | registered | **measured** |
|---|---|---|
| **P1** model | sweeps 277 → **281**, S16 1,279 → **1,293**, 14 closed 0 broken | **MET**, cell for cell; `busstat_other` 10 → 0, `B_late` 16 → 12, `qop` 39 and `ARCH` 30 unmoved |
| **P2** ucore | sweeps 273 → **277**, S16 1,294 → **1,308** | **MET**, the SAME 14 cells; `D_tstate` 24 and `ARCH` 27 unmoved |
| **P3** | `ulockstep` **17,350** | **17,350 / 17,350 ALL LOCKSTEP** |
| **P4** | the ladder unmoved, both engines, fuzz **to the seed** | **MET — 0 of 3,242 seeds differ on EITHER engine** |
| **P5** | `ss_lint` 217 / 200 / 0x85 | **rc 0, 217 addresses, 200 flops, 0 UNMAPPED** |
| **P6** | G6 E1-E5 | **PASS.  E3 43.94 MHz · E4 +8.493 ns · E5 TNS 0.000 every domain.**  ALMs 11,131 (27 %), 0 latches, 0 `lpm_divide`.  Receipt `000cc32bc90ff270…`, manifest 88 files `3420a2e63226472f…` |
| **P7** | `git diff -- hdl` empty at the `sim/` commit | **EMPTY** |

### §82.3 **B-2 = F57.  THE READ'S COMPLETION CLOCK MOVES TO THE EVAL.**

Measured off the model's own commit trace (`V30SIM_FLUSHTRACE`):

| cell | INTA1 display | INTA1 T1 | INTA2 display, model | golden |
|---|---|---|---|---|
| `idx 5` — **FAILS** | 17 | **19** (= disp + 2) | **25** | **24** |
| `idx 6` — passes | 18 | 19 (= disp + 1) | 25 | 25 |
| `idx 7` — passes | 19 | 20 (= disp + 1) | 26 | 26 |

**Silicon's second acknowledge is `display + 7`.  The model's was `T1 + 6`.**
They are the same number for every cycle whose T1 opens the clock after its
display and part only where a T1 WAITED — the acknowledge after a woken HALT,
and nothing else in the corpus.  It is M22's `cmt_expire_` sentence one
mechanism over.

**WHERE THE CLOCK WAS LOST.**  `wait_next_read()` blocks until a completion
stamp EXISTS and then until the clock it names.  The stamp's VALUE is `e + 2`
— eval-keyed, M22's second consequence — but it was PUSHED in the `T4` block.
On `idx 5` the eval is at clock 20, the stamp names **22**, it is not pushed
until clock 22, and the wait cannot leave before **23** — one clock after the
instant the model had itself computed.

> **F57.**  A read's completion clock is stamped **at the cycle's own eval**.
> The value is unchanged; what moves is the clock the EU can first SEE it on.

**W0-NEUTRAL BY CONSTRUCTION** for every ordinary cycle (the wait's second stage
is untouched, so the EU still leaves at `e + 2`) and identical under waits
(`eval_i == last_i`, one clock, one site).  In the `ucore` (`660b19c405`) the
arm is `done_ctr = 2'd2` at the eval and the byte composition moves with it so
`rd_land` is registered before the pulse that delivers it; it sits AFTER the
T-state advance because the advance is what captures `cur_data = ad_i` at T2 —
and a cycle whose display waited has its eval AT T2.  **NO NEW FLOP**:
`sev_now` already distinguishes "the eval is this T4" from "the eval was
earlier".  The old `(land_ttl == 0) ? 1 : land_ttl` clamp IS the defect — a
counter armed at T4 cannot fire before `T4 + 1`, so `e + 2 < T4 + 1` was
inexpressible.

**THE RESULT, REPORTED AS REGISTERED.**

| | registered | **measured** |
|---|---|---|
| **P1** model | sweeps 281 → **283 / 283**, S16 1,293 → **1,305**, 12 closed 0 broken | **MET.**  `B_late` 12 → **0**, catch-all EMPTY.  *The model's first perfect HLT-sweep score.* |
| **P2** model fuzz | REGISTERED **1,272 unchanged**, EVT 783 → **788**, COMBINED **2,060**, exactly 5 named seeds gained / 0 lost, b2 **154** | **MET**, and the five are `mc1/1383`, `mc2/594`, `mc2/1052`, `mc2/1068`, `mc2/3530` |
| **P3** ucore, S16 + fuzz | S16 1,308 → **1,320**, `B_late` 12 → 0; fuzz up-only | **MET.**  Per wait **372 · 328 · 318 · 302** — **w0 IS 372/372**.  REGISTERED 1,490 unchanged, EVT 913 → **918**, COMBINED **2,408**, b2 **172** |
| **P3** ucore, sweeps | 277 → **283 / 283** | ⚠ **NOT MET AS WRITTEN — 279 / 283.**  See §82.4. |
| **P4** | `ulockstep` 17,350 | **17,350 / 17,350 ALL LOCKSTEP** |
| **P5** | the ladder unmoved, both engines | **MET** |
| **P6** | `ss_lint` UNCHANGED at 217 / 200 / 0x85 | **MET — no new state, which was the claim** |
| **P7** | G6 E1-E5 | **PASS.  E3 45.83 MHz · E4 +8.402 ns · E5 TNS 0.000 every domain.**  ALMs 11,118 (27 %), 0 latches, 0 `lpm_divide`.  Receipt `a9f07afaa667de51…`, manifest `9d917dddab4bfdf7…` |
| **f1 … f7** | — | **NONE FIRED** |

**f7 — *"the ucore needing a DIFFERENT sentence from the model's"* — did not
fire, and the proof is not an argument**: on the 3,242-seed bank the ucore
gains **exactly the same five seeds** the model gained, and loses none.

### §82.4 **P3's SWEEP FIGURE WAS MIS-DERIVED.  REPORTED AS REGISTERED, NOT RESTATED.**

`sm3_s21b_prereg_2026-08-05.md` §2 registered the ucore's four HLT sweeps at
**283 / 283**.  They measure **279 / 283**, and the bar was **arithmetically
wrong when it was written**: 283 was carried across from the MODEL's leg, which
has no family-D residue on its comparator.  The ucore's four survivors are
`w1.INT/8,9` · `w2.INT/12` · `w3.INT/15` — **family D, not family B** — they
are unfixable on `tb_v30_core` by construction (it samples `BS` once), and they
are precisely the cells the user's own item-0 disposition moves to the
`tb_sys`/fabric column.  **279 IS "the two B-2 sweep cells close and nothing
else moves."**  The cell-level bar the number was meant to express is MET,
`f1` and `f2` did not fire, and the landing stands — but the number is recorded
as a MISS, because a bar that is quietly re-derived after the run is not a bar.

### §82.5 THE RATCHETS THAT MOVED, ITEMISED

| ratchet | before | **after** | which change |
|---|---|---|---|
| **the MODEL's four HLT sweeps** | 277 / 283 | **283 / 283** | F56 (+4) then F57 (+2) |
| **the MODEL's S16 walk** | 1,279 / 1,371 | **1,305 / 1,371** | F56 (+14) then F57 (+12) |
| the MODEL's S16 census | `busstat_other` 10 · `B_late` 16 · `qop` 39 · `ARCH` 30 | **`qop` 39 · `ARCH` 30** — family B GONE, catch-all EMPTY | F56 + F57 |
| **the MODEL's fuzz EVT column** | 783 / 1,008 | **788 / 1,008** | F57 |
| **the MODEL's fuzz COMBINED** | 2,055 / 2,710 | **2,060 / 2,710** | F57 |
| **the ucore's four HLT sweeps** | 273 / 283 | **279 / 283** | F56 (+4) then F57 (+2) |
| **the ucore's S16 walk** | 1,294 / 1,371 | **1,320 / 1,371** | F56 (+14) then F57 (+12) |
| — per wait level | 346 · 328 · 318 · 302 | **372 · 328 · 318 · 302** | w0 is PERFECT |
| the ucore's S16 census | `busstat_other` 10 · `B_late` 16 · `D_tstate` 24 · `ARCH` 27 | **`D_tstate` 24 · `ARCH` 27** | F56 + F57 |
| **the ucore's fuzz EVT column** | 913 / 1,008 | **918 / 1,008** | F57 |
| **the ucore's fuzz COMBINED** | 2,403 / 2,710 | **2,408 / 2,710** | F57 |
| `SS_VERSION` / `SS_COUNT` / `SS_TAG` | 0x84 / 218 / 0x84DA | **0x85 / 217 / 0x85D9** | F56 — a flop DELETED |
| `ss_lint` flops | 201 | **200** | F56 |
| G6 Fmax / ALMs | 47.15 MHz / 11,104 | **45.83 MHz / 11,118** | recorded, not barred; §74.4 governs |
| the two REGISTERED fuzz columns | 1,272 (sim) / 1,490 (ucore) | **UNCHANGED TO THE SEED through both landings** | — |

### §82.6 WHAT THIS SITTING DID NOT DO, AND THE STATE IT LEAVES

* **NO BOARD CONTACT, NO FLASHING, `use_core` NEVER SET.**  The board still
  carries **FLASH #9**, which predates F55, F56 and F57.  Every fabric figure
  in this document and in `standing_gates.md` remains a FLASH #9 figure.
* **Family B is CLOSED in both engines.**  §79.G's booking is discharged; its
  cell counts are corrected by §82.1 and its two falsifiers are met by §82.2
  and §82.3.
* **The residue that is left on the S16 walk is TWO classes and no third**: the
  ucore's **24 `D_tstate`** (family D — the analyser's second `BS` sample, now
  a `tb_sys` item by user disposition) and **27 `ARCH`**; the model's **39
  `qop`** and **30 `ARCH`**, both inside the FROZEN model-only debt.
* **H4-B, `TAIL_EXTRA`, H3-B and the 8080 work were not opened.  No memory file
  was touched.  Codex was not launched.**
* **Registered for FLASH #10, unchanged and now larger**: §81.A.7's F55
  prediction still stands, and F56 and F57 join it — the fabric legs have never
  seen any of the three.

---

## §83 SESSION SM3, SITTING 22 — **H4 PARTITION B IS NOT ONE CLASS AND IT IS NOT A TIMING CLASS.  THE THREE SHARP SEEDS ARE A GENUINE INT-1 ENTRY: THE CHIP SINGLE-STEPS AND NEITHER TIMED ENGINE IMPLEMENTS THE BRK/TF TRAP AT ALL.  THE ARCHITECTURAL MODEL DOES, AND ITS SEQUENCE IS THE CHIP'S WITH ONE EXTRA TRAP AT THE HEAD.  NOTHING IS LANDED, AND THAT IS THE REGISTERED OUTCOME.**

**2026-08-05, branch `ucsim`.  Offline only, NO BOARD CONTACT, no flashing,
`use_core` never set.  No engine file changed; the only code edited is a
scorer.**

### §83.0 ITEM 0 — THE X1 `tb_sys` LEGS WERE TWO LANDINGS STALE (`2cd8412026`)

The coordinator's review finding, confirmed and closed before any target work.
`x1_retention score` was reading **`ret 273/283` against `offline 279/283`,
"6 SURVIVED", "BAR (i) NOT MET"** — and every word of it was TRUE OF THE FILES
AND FALSE OF THE TREE.  The `base`/`ret` columns were captured in the F55 era;
`offline.json` had been re-taken after F56 and F57.  **The six "survivors" were
exactly the six w0 cells F56/F57 had already closed.**

Both legs rebuilt through the receipt layer and all three columns re-taken so
they are of one era:

| column | before | **this tree** |
|---|---|---|
| `offline` `tb_v30_core` (models pad retention) | 279 / 283 | **279 / 283** (unchanged) |
| `base` `tb_sys`, `X1_AD_RETENTION` **OFF** | 146 / 283 | **34 / 283** |
| `ret` `tb_sys`, `X1_AD_RETENTION` **ON** | 273 / 283 | **279 / 283 — `offline` EXACTLY** |
| BAR (i) | 6 SURVIVED, NOT MET | **245 closed, 0 SURVIVED, MET** |
| BAR (ii) | 6 cells differing, NOT MET | **0 cells differing, MET** |
| VERDICT (this leg) | NOT MET | **MET** |

**The `base` column moving DOWN by 112 is REGISTERED, not an error.**  It is the
diagnostic column, never a ratchet, and **F55 is precisely the landing that took
the pad retention out of the core's DRIVE** (§81.A) — so a harness without
retention must now miss far more rows.  For the same reason the INTA share of
base-only failures falls **129 → 21**: the class is no longer INTA-dominated
because it is no longer INTA-only.  §81's "the two offline instruments agree"
rule therefore holds again, at **279**, on the pair `tb_v30_core` / `tb_sys ret`.
Superseded columns ARCHIVED BY COPY as `…-pre-f56` beside the existing
`…-pre-f53`; nothing moved, nothing deleted.

### §83.0a THE ERA GUARD — **THE VACUOUS-GATE PATTERN, EIGHTH INCARNATION, AND THIS ONE IS STRUCTURAL**

A capture recorded WHAT it measured and never WHICH TREE.  Every capture now
embeds `_meta.tree` = the artifact layer's **input manifest hash** for the
binary that produced it.  It is deliberately **command-free**, so it is
IDENTICAL across the `base`/`ret` A/B pair by construction — the pair differs by
one `-D`, and a guard that fired on that would be useless.  `offline.json`
carries the same stamp on `check_core`'s own input set, because it is bar (ii)'s
REFERENCE column and its staleness is exactly as silent.  `score` **REFUSES,
naming both hashes**, on any mismatch.

NON-VACUITY, DEMONSTRATED IN THREE MODES, not asserted:

| mode | result |
|---|---|
| **ABSENT** — the pre-guard captures | fires, `rc=1` |
| **MIXED** — one file of a column re-stamped | fires AND names the third failure mode: *the column's own files DISAGREE (half re-captured)* |
| **MISMATCH** — a whole column re-stamped | fires, naming both hashes |
| clean tree | `rc=0`, VERDICT **MET** |

The mutated files were restored and `sha256sum -c SHA256SUMS` is clean.
`--no-era-guard` is the single documented escape and it is for reading an
ARCHIVED column as history, which is not a statement about this tree.

### §83.0b **THE SAME STALENESS, ONE INSTRUMENT OVER — THE ENTIRE S16 OFFLINE/vsys PAIR WAS PRE-F56, AND IT WAS INVISIBLE BECAUSE BOTH HALVES WERE**

Found while checking that item 0's guard had no other consumer to break.
`sw/testdata/sm3-s16fab/` holds two SOFTWARE columns, and both were written at
**07:00 / 06:33 on 2026-08-05** — while **F56 landed in the ucore at 08:45 and
F57 at 09:07**.  §82 re-measured the S16 walk on `sm3_s16_score`'s scale
(1,308 → **1,320**) and did **not** re-take these two, so `standing_gates.md`
and §81 have been quoting **1,321 / 1,371** for both.

**Why nothing caught it**: the two columns are compared with EACH OTHER, and
they were stale TOGETHER.  "0 PASS/FAIL disagreements, 0 differing coordinates"
was true, and was a statement about two captures of the same dead tree.  *A
cross-check between two instruments is only as current as the older of them.*

Re-taken on this tree, with the expectation written down before the second
number was read (*"if the two offline instruments still agree, `vsys_ret`
reaches whatever `offline` reaches, with 0 disagreements and 0 differing
coordinates; anything else is a finding"*):

| column | banked (pre-F56) | **this tree** |
|---|---|---|
| `sm3_s16_fabric offline` (`tb_v30_core`, rows only) | 1,321 / 1,371 | **1,347 / 1,371** |
| `sm3_s16_fabric vsys_ret` (`tb_sys`, `X1_AD_RETENTION`) | 1,321 / 1,371 | **1,347 / 1,371** |
| the two against each other | 0 / 0 | **0 PASS/FAIL disagreements, 0 differing coordinates over all 1,371** |

**+26 per instrument, which is F56's +14 and F57's +12 exactly** — the same two
numbers §82 measured on the other scale.  §81's "the two offline instruments
agree" rule holds, and now holds on a live tree.  The expectation was **MET**.

`fab_f9` **1,291 / 1,371** is untouched and remains a **FLASH #9** figure: its
DUT is a bitstream that predates F55, F56 and F57, and its era is the flash log,
not the tree.  Its "30 disagreements vs `vsys_ret`" was measured against the
PRE-F56 `vsys` column and must be re-derived, not restated, at the next flash.

**THE STAMP, extended one instrument**: `sm3_s16_fabric vsys` now records the
same `tree` key in its manifest and `score` REFUSES for a `vsys*` leg whose
stamp is absent or stale.  **A FABRIC leg is deliberately NOT stamped this way**
— its DUT is a bitstream and its provenance is the flash log, so a tree hash
would be the wrong question and a wrong answer.  Its own non-vacuity was
demonstrated by accident and is the better for it: the first re-capture was
started before the stamp was written, `score` refused it by name, and it was
re-taken.

Superseded columns archived by copy as `…-pre-f56`.

### §83.1 THE BASELINES, RE-MEASURED ON THIS TREE (not cited)

`timed_fuzz --evt-replay`, 3,242 seeds, 2,710 scored, both engines, fresh:

| column | `ucore` | `sim` |
|---|---|---|
| REGISTERED | **1,490 / 1,702** | **1,272 / 1,702** |
| EVT | **918 / 1,008** | **788 / 1,008** |
| COMBINED | **2,408 / 2,710** | **2,060 / 2,710** |

`BOUND WARNINGS 5`, `ENGINE ABORTS 0`.  Identical to `standing_gates.md` **to
the seed**; nothing in this sitting moved a ratchet in either direction.

`s15_census --core <engine> --pop reg`, `--core` matched to the report:
ucore `PF_LOST 106 · DATA_SEQ 36 · TAIL_EXTRA 29 · PF_GAINED 24 · PF_ADDR 8 ·
SCHEDULE 5 · PIN 4`, catch-all 0; sim `DATA_SEQ 28`.  §67.8's census reproduces
cell for cell.  **Partition B is 28 seeds, `DATA_SEQ` in BOTH engines, and on
28 of 28 the first-divergence coordinate AND detail are byte-identical between
the two engines** (§66.2 measured 27 of 28, with `mc1/2241` the exception; on
this tree `mc1/2241` agrees too.  **No cause is attributed** — three landings
separate the two measurements and nothing here isolates one; the seed's `ndiff`
still differs sharply between the engines, 2,193 against 120, so the two runs
part company downstream even where their first divergence does not).  The
ucore-only column is **0** and the sim-only column is **0**; the
remaining 8 ucore `DATA_SEQ` seeds are RELABELS (`PF_LOST` 4 · `SCHEDULE` 3 ·
`TAIL_EXTRA` 1).

### §83.2 THE THREE-SEED ADJUDICATION — **IT IS A GENUINE INT-1 ENTRY.  THE ROW GEOMETRY SETTLES IT WITH NOTHING LEFT OVER.**

§67.2 asked whether the chip's `0x00004` read is an interrupt ENTRY or a data
artifact, and said the answer is in the rows.  It is.  On all three seeds the
chip's launches from the divergence are:

```
mc2/1718   MEMR:00004  MEMR:00006  MEMW:02e0c  MEMW:02e0a  MEMW:02e08  CODE:00480
mc2/3061   MEMR:00004  MEMR:00006  MEMW:03f00  MEMW:03efe  MEMW:03efc  CODE:00480
t30-raw/899 MEMR:00004 MEMR:00006  MEMW:03efc  MEMW:03efa  MEMW:03ef8  CODE:00480
```

**The vector PAIR at `4` and `6`, then three descending word pushes, then a code
fetch at the SAME handler address `0x00480` on all three.**  That is an
interrupt entry and nothing else is: an effective-address read is one cycle with
no push train and no transfer.  **The artifact reading is REFUTED.**  The
engines at the same instant launch `MEMW 794fc` / `MEMR db129` / `MEMR 9bd32` —
an ordinary computed EA — and run straight on.

*The chip takes an entry the engines do not*, exactly as §67.2 wrote it.

### §83.3 THE MECHANISM — **NEITHER TIMED ENGINE IMPLEMENTS THE BRK/TF SINGLE-STEP TRAP.  IT IS AN ABSENCE, NOT AN ERROR.**

Vector 1 is the BRK/TF single-step trap.  Read where the trap is raised:

* `sim/image_runner.cpp:279` — **the ARCHITECTURAL model has it**:
  `bool tf = tf_model && (m.psw & kFlagBRK) != 0;` … `cpu.interrupt(Cpu::kEvtBrk)`.
* `sim/timed_runner.cpp` — **the TIMED model, which is what `timed_fuzz --core
  sim` scores, never tests the flag.**  `kEvtBrk` has exactly ONE caller in the
  whole tree and it is `image_runner.cpp`.
* the `ucore` — `FBRK` exists as a PSW bit and is CLEARED on entry
  (`v30u_eu_row.svh` `I_CITF`, `v30u_eu_poste.svh` vector 1), and **nothing
  anywhere READS it to raise anything.**

So this is not a wrong rule in the timed engines; it is a **missing feature**,
and it is missing in both.  That is why partition B's two engines agree with
each other to the byte and disagree with the socket — §49.7's class, and the
reason a functional fork wears a `DATA_SEQ` label.

**THE CONTROLLED TEST, engine-free on the chip side.**  Detect interrupt entries
structurally (vector pair at `4V`/`4V+2` followed by three word pushes) in the
chip's `chip_rows` and in the architectural model's transaction stream, with
`tf` ON and OFF, and compare the VECTOR SEQUENCES:

| seed | chip vector-1 entries | arch `tf=1` | arch `tf=0` |
|---|---|---|---|
| `mc2/1718` | 32 | 544 | **0** |
| `mc2/3061` | 11 | 366 | **0** |
| `t30-raw/899` | 37 | 363 | **0** |
| `mc2/2361` | **1** | 1 | **1** |

and over all **30** scored REGISTERED seeds whose chip stream contains a
vector-1 entry: with `tf` ON the architectural model produces vector-1 entries
in **30 of 30**; with `tf` OFF it produces **ZERO in 29 of 30**.

**`mc2/2361` IS THE CONTROL AND IT IS THE SHARPEST FACT IN THE SITTING.**  It is
the ONE seed of the 30 whose vector-1 entry SURVIVES with `tf` OFF — i.e. a
software `INT 1`, not a trap — and it is the ONE seed of the 30 that **both
timed engines already score EXACT**.  The only vector-1 entry the engines
reproduce is the only one that is not a TF trap.

### §83.3a THE POPULATION — **145 REGISTERED SEEDS CONTAIN A CHIP-SIDE VECTOR-1 ENTRY; 29 OF THEM ARE SCORED AND ALL 29 DIVERGE, IN BOTH ENGINES**

Chip-side, engine-free, over the whole 3,242-seed bank: **197 seeds** (145
REGISTERED) contain a vector-1 entry.  Of the 145: **115 are EXCUSED
(`OPEN_BUS`)**, **29 DIVERGE — identically in both engines** — and **1 is
EXACT**, and the exact one is `mc2/2361`.

On all 29 the first divergence lands **9 to 10 rows BEFORE** the vector read's
T1, and its kind is **`qs` on 28 of 29** — the trap's own queue FLUSH, which is
the first thing the trap does that reaches a pin.  The family LABEL is
`PF_GAINED` on 24 of them and `DATA_SEQ` on only 3: after a fork the label
records what happened next, not what happened.  **The three seeds §67.2 singled
out are one tenth of their own class, and the class crosses four families.**

*The ratchet headroom this names, for each engine:* **29 REGISTERED seeds**,
plus whatever the EVT column holds.  It is NOT claimed here and nothing is
landed on it.

### §83.3b `has_tf` IS UNINFORMATIVE — MEASURED, AND WORTH RECORDING

`gen_soup.emit_tf` sets `has_tf` when it deliberately emits `PUSH 0x0100; POPF`.
**`has_tf` is `False` on all 197 seeds.**  TF in this corpus is set
INCIDENTALLY — a `POPF`/`IRET` restoring a random word with bit 8 — not by the
generator's deliberate arm.  Any future selection that filters on `has_tf` to
find single-stepping would find none of it.

### §83.4 THE LAW CANDIDATE — **THE ARCHITECTURAL MODEL'S TRAP SEQUENCE IS THE CHIP'S WITH ONE EXTRA TRAP AT THE HEAD.  ONE INTEGER, NOT A TABLE.**

The third push of an entry carries the return **IP**, so the pushed-IP sequence
across a step storm is a direct readout of *which instruction boundary the trap
was taken at*, in silicon, thousands of times, board-free.  Extracted from the
chip rows and from the architectural model's transactions:

```
mc2/1718    arch 0x519 0x51b 0x51c 0x520 0x524 0x527 0x529 0x52b …
            chip       0x51b 0x51c 0x520 0x524 0x527 0x529 0x52b …
t30-raw/899 arch 0x5c9a 0x5c9b 0x5c9d 0x5c9e 0x2402 0x2403 0x2404 …
            chip        0x5c9b 0x5c9d 0x5c9e 0x2402 0x2403 0x2404 …
mc2/3061    arch 0x51b 0x51c 0x51d 0x520 0x523 0x525 0x528 …
            chip       0x51c 0x51d 0x520 0x523 0x525 0x528 …
```

**`chip == arch[1:]`, element for element.**  Over the 30 seeds, on the prefix:
**18 SHIFT-1**, **2 identical**, **1 too short** (`mc2/2361`, the software-INT
control), and **9 where the chip-side pushed value read back as `0` in the
scratch extractor** — a dump artifact, not a finding, and they are reported as
unreadable rather than counted either way.

**What this says**: the RECOGNITION DEPTH is the same in both — after the head
the two sequences advance by the same number of instructions per trap, so the
storm cadence is one instruction per trap in silicon as in the model.  What
differs is the **ARM**: the model takes its first trap **one instruction too
early**.  Its own comment states the rule it implements — *"TF is sampled at the
START of the instruction, so the instruction that SETS it does not trap"* — and
against silicon that grants one instruction of grace too few.

### §83.5 THE PARTITION OF THE 28, WITH ITS INVARIANT

The discriminator is **engine-free and architectural**: run `ucsim_fuzz` (the
chip against the ARCHITECTURAL model) on each seed and ask whether the
architecture ALREADY disagrees.

| class | n | invariant | who owns it |
|---|---|---|---|
| **B1 — the TF trap** | **3** (`mc2/1718`, `mc2/3061`, `t30-raw/899`) | chip takes an INT-1 entry at the first divergence; arch with `tf` ON reproduces the entry sequence, with `tf` OFF produces none | **both timed engines, as an ABSENT FEATURE**; and the arch model's ARM is one instruction early (§83.4) |
| **B2a — architecture-exact, timing-divergent** | **12** (`mc1/1543`, `mc1/2241`, `mc1/2512`, `mc2/1104`, `mc2/2438`, `mc2/2648`, `mc2/3569`, `mc2/3805`, `t30-raw/428`, `t30-raw/508`, `t30-raw/563`, `t30-raw/962`) | `ucsim_fuzz` is **1/1 OK**: the architectural transaction stream matches the chip exactly, and only the TIMED replay parts | **the BIU.**  This is the genuine partition-B target and it is 12 seeds, not 27 |
| **B2b — architecture-divergent for a non-TF reason** | **13** | `ucsim_fuzz` reports `STREAM=1`: the ARCHITECTURAL model already disagrees with the chip, before any timing question is asked | **the architectural ledger**, i.e. inherited functional residue.  It is not a BIU class and no BIU landing can close it |

3 + 12 + 13 = 28.  **`t30-raw/962` is the cheapest B2a member** (`ndiff` 4 of
4,000, both engines identical, arch-exact) and is the right first instrument for
B2a: at row 522 the chip launches `MEMR 0ca00` where both engines launch
`MEMR 0ef1c`, with every surrounding row — code fetches, cycle positions, queue
status — identical, and the run resynchronises four rows later.

**§67.2's headline figure is therefore corrected, not restated**: partition B is
not "27 seeds with a wrong `MEMR` launch address" as one class.  It is three
classes with three owners, and only **12** of the 28 are a BIU question.

### §83.6 WHY NOTHING IS LANDED — THE REGISTERED OUTCOME

The brief authorises "the honest partition + the discriminating cell spec" when
the evidence under-determines a landing.  It does, and here is exactly where:

1. **The mechanism is established; the LAW is not.**  §83.4 measures that the
   model's arm is one instruction early.  It does NOT establish *whose* set gets
   the extra instruction of grace.  The obvious reading — a uniform extra clock
   of delay on the recognition — is **REFUTED by the storm cadence**: a uniform
   delay makes the storm two instructions per trap, and silicon's is one.  So
   the grace attaches to the SETTER (the `POPF` that arms TF) and not to the
   `IRET` that re-arms it inside the storm, and *that asymmetry is not yet
   measured*.  Landing a trap on an unmeasured arm is landing a guess.
2. **Running `ucsim_fuzz` over the 30 confirms the arch model is divergent on 27
   of 30 even with `tf` ON**, so "port the architectural rule into the timed
   engines" would port a rule that is itself wrong.
3. The standing rule stands: the session that measures a class does not also
   land it.

### §83.7 THE DISCRIMINATOR FOR THE NEXT SITTING — BOARD-FREE, AND THE DATA IS ALREADY BANKED

The asymmetry in §83.6 item 1 is decidable OFFLINE from the 197 banked seeds,
because every trap entry publishes its own return IP on the pads:

* Re-run `v30sim image` with `ilog=1` on the 29 scored seeds.  The instruction
  log gives `(CS, PC)` per instruction, so the pushed-IP sequence can be turned
  into *"how many instructions elapsed between the setter and the first trap"*
  and *"how many between the handler's `IRET` and the next trap"*, per seed.
* **The two registered candidates** — (a) the grace is on the SETTER only, so
  `POPF` gets one instruction and `IRET` gets none; (b) the grace is on any
  0→1 transition of TF, so both get one and the storm cadence must then be two.
  **(b) is already refuted by the chip's cadence**, and this measurement either
  confirms (a) exactly or produces a third shape, which is the result.
* *Falsifier for the whole mechanism*: any of the 29 seeds where the chip's
  first divergence is NOT at the trap's flush, or any seed where the chip takes
  a vector-1 entry the architectural model does not take with `tf` ON.

Only after that instant is fixed does the landing become pre-registerable:
`sim/timed_runner.cpp` first, the `ucore` second, edge for edge, with
`ulockstep --golden all --cases 50` **17,350 / 17,350** as the gate that the two
engines are rendering the same sentence.

### §83.8 THE RATCHETS — **NONE MOVED, IN EITHER DIRECTION**

| gate | before | this sitting |
|---|---|---|
| `timed_fuzz --core ucore` REGISTERED / EVT / COMBINED | 1,490 / 918 / 2,408 | **1,490 / 918 / 2,408** |
| `timed_fuzz --core sim` REGISTERED / EVT / COMBINED | 1,272 / 788 / 2,060 | **1,272 / 788 / 2,060** |
| `x1_retention` `offline` | 279 / 283 | **279 / 283** |
| `x1_retention` `ret` | 273 / 283 (**STALE — F55 era**) | **279 / 283**, bars (i) and (ii) both **MET** |
| `x1_retention` `base` | 146 / 283 (**STALE — F55 era**) | **34 / 283** (diagnostic column, never a ratchet) |
| `sm3_s16_fabric offline` | 1,321 / 1,371 (**STALE — pre-F56**) | **1,347 / 1,371** |
| `sm3_s16_fabric vsys_ret` | 1,321 / 1,371 (**STALE — pre-F56**) | **1,347 / 1,371**, 0 disagreements / 0 differing coordinates vs `offline` |

The four re-taken columns are **CORRECTIONS OF STALE RECORDS, not movements**:
every one of them is the number the tree already had at the end of sitting 21
and nobody had asked it for.

No RTL changed, no `sim/` changed, no golden moved, no bitstream built, no board
touched.

### §83.9 WHAT THIS SITTING DID NOT DO

* **NO BOARD CONTACT, NO FLASHING, `use_core` NEVER SET.**  The board still
  carries **FLASH #9**.
* **Nothing landed.**  §83.6 states why, as a registered outcome.
* **`TAIL_EXTRA`, the last-2-seeds closers, H3-B and the 8080 work were not
  opened.  No memory file was touched.  Codex was not launched.**
* **B2a's 12 seeds are booked, not diagnosed.**  `t30-raw/962` is named as the
  cheapest instrument and is not run to the bottom here.
* **B2b's 13 seeds are ROUTED OUT of the timing census** as inherited
  architectural residue.  That is a re-attribution, not a fix, and it does not
  change any number.

## §84 SESSION SM3, SITTING 23 — **THE BRK/TF ARM LAW, MEASURED: ONE ARM BIT, SAMPLED AT EVERY INSTRUCTION BOUNDARY, AND A PREFIX IS A BOUNDARY**

### §84.1 THE PRE-REGISTRATION — **WRITTEN AND COMMITTED BEFORE THE HELD-OUT POPULATION WAS TOUCHED**

§83.7 registered a board-free discriminator and named two candidate arms.  It
was run.  **Both registered candidates are REFUTED and a third shape came out**,
which §83.7 explicitly allowed for ("or produces a third shape, which is the
result").  The refuted-key rule applies in full, so the population split is
stated first and the law second.

**THE SELECTING POPULATION — 30 seeds** (the 29 scored+divergent vector-1 seeds
of §83.3a, reproduced on this tree seed-for-seed from `chip_v1.json` × the
sitting-22 `timed_fuzz` reports, plus the software-INT control `mc2/2361`).
Every clause of the law below was read OFF these 30.  Nothing here is a
prediction; this is the fit.

**THE LAW.**

> There is ONE arm bit for the single-step trap.  At every instruction
> boundary the machine first TAKES the trap if the arm bit is set (and the
> entry clears it), and then SAMPLES `TF` into the arm bit.  **A PREFIX BYTE
> ENDS AN INSTRUCTION BOUNDARY** for this purpose.  `IRET`'s PSW write lands
> BEFORE its own boundary's sample; `POPF`'s lands AFTER it.

Nothing in it is per-opcode: the whole POPF/IRET asymmetry is *where in the
instruction the PSW write falls relative to one fixed sample point*, which is a
property the microcode ROM already has.  The prefix clause is not an assumption
either — the ROM carries the REPX withdrawal and the prefix-chain PC rewind
(0223, 0225-0227) precisely because a request can be taken between a prefix and
its opcode.  It is the same shape as §72's IE-restore law: a flag written by an
instruction is not visible to recognition until after a fixed instant.

**WHAT IT PREDICTS**, in `ilog` instruction indices with `S` the setter:

| setter | prefixes on `S+1` | trap taken at | pushed IP |
|---|---|---|---|
| `POPF` | 0 | end of `S+2` | `ilog[S+3].pc` |
| `POPF` | 1 | end of `S+1` | `ilog[S+2].pc` |
| `POPF` | ≥ 2 | inside `S+1`'s prefix chain | `ilog[S+1].pc` (ROM rewind) — **COROLLARY, UNEXERCISED** |
| `IRET` | 0 | end of `S+1` | `ilog[S+2].pc` |
| `IRET` | ≥ 1 | inside `S+1`'s prefix chain | `ilog[S+1].pc` (ROM rewind) — **COROLLARY, UNEXERCISED** |

and, for the storm, **grace 0 on every consecutive trap pair** (the handler is a
bare `IRET`, measured, on 30 of 30 seeds).

**ON THE SELECTING POPULATION** (`sw/sm3_tf_law.py`, the fit, not a gate):
`LAW verdict` **HIT 29 / NO_SETTER 1**, the `NO_SETTER` being `mc2/2361` — the
software `INT 1` control, which has no PSW load that sets TF and must NOT be
explained by a trap law.  Split by branch: `(POPF, 0 prefixes)` **26 HIT**,
`(POPF, 1 prefix)` **2 HIT**, `(IRET, 0 prefixes)` **1 HIT**.  Storm cadence
**0 on 606 of 606** pairs.  Corollary branches exercised: **0**.

**THE PRE-REGISTERED HELD-OUT BAR.**  The remaining **167** of the 197 chip-side
vector-1 seeds (§83.3a) were NOT looked at while the law was being written.
They are the validation population.  Registered, before the run:

* **(V-1)** On every held-out seed whose head is readable, `predict_head` HITS —
  the predicted `(cs, ip)` is the chip's first pushed `(cs, ip)`, exactly.
  **Bar: ≥ 95 % of scoreable heads HIT, and ZERO MISSES whose setter is `POPF`
  with an unprefixed `S+1`** (the branch the law is most constrained on).
* **(V-2)** Storm grace is **0** on every measurable pair.  **Bar: zero pairs
  with grace ≠ 0.**
* **(V-3)** Any seed exercising a COROLLARY branch is reported separately and
  is not counted toward V-1 either way, since the law's prediction there was
  never tested.
* **FALSIFIER, whole mechanism**: a `POPF` setter with an unprefixed `S+1` whose
  chip trap is anywhere but the end of `S+2`; or a `POPF` and an `IRET` setter
  in the same branch-shape disagreeing about grace; or a storm pair with grace
  ≠ 0.  Any of those and the law is booked REFUTED and NOTHING is landed.

**THE INSTRUMENT DEFECT §83.4 REPORTED AS A POPULATION PROPERTY.**  §83.4 said
9 of 30 seeds' pushed values "read back as `0` in the scratch extractor — a dump
artifact".  It is not a dump artifact and it is not 9 seeds' property: those
seeds have an **ODD SP**, so each push is two BYTE cycles and the captured
`ad_data` is the AD pattern rather than the pushed word.  Read through the
COMMITS — `sw/ucsim_fuzz._commits`, the repo's own lane rule — the frames are
perfectly legible: `mc2/1698`'s first push reads `0x1d05` through `data` and
**`0x051d`** through the commits, and `0x51d` is where that seed's code
actually was.  **All 30 heads are readable; `unreadable` is 0.**  A second
defect in the same extractor: a bare `4`/`6` read pair plus any three
descending writes counted as an entry, which gave one seed 22 phantom entries;
§83.2's signature has a FIFTH part, the TRANSFER to the handler the vector just
named, and it is load-bearing.

### §84.2 THE HELD-OUT RUN — **THE REGISTERED BAR V-1 WAS NOT MET, AND THAT IS THE RESULT AS REGISTERED**

167 seeds, none of them looked at while §84.1 was being written.

| registered bar | outcome |
|---|---|
| **V-1** rate ≥ 95 % of scoreable heads | **139 HIT / 148 scoreable = 93.9 %** — **NOT MET** as written; **96.5 %** (139/144) once V-3's 4 corollary seeds are set aside as V-3 itself directs |
| **V-1** ZERO misses on `(POPF, unprefixed S+1)` | **NOT MET — 3 misses** (`mc1/323`, `t30-raw/714`, `t30-raw/920`) |
| **V-2** storm grace 0 on every pair | **MET — 1,136 / 1,136** held-out, **1,742 / 1,742** with the selecting set |
| **V-3** corollary branches reported apart | **4 seeds**, all reported, none counted |

**The falsifier fired.**  It is recorded here as it was registered and it is not
restated.  What the misses then turned out to be is a separate statement:

**ALL NINE MISSES ARE `OPEN_BUS`-EXCUSED SEEDS.**  Stratified by the repo's own
pre-existing scoring class (`fuzz_accept.open_bus_escape_metrics`), over all 177
scoreable heads of both populations:

| stratum | conform | not |
|---|---|---|
| `DIVERGE` / REGISTERED (the 29) | **29** | 0 |
| `DIVERGE` / EVT (**held out, never used in the fit**) | **9** | 0 |
| `OPEN_BUS` | 131 | **8** |

**On every seed where the ruler is VALID the law is exact, 38 of 38**, and 9 of
those 38 are held-out EVT seeds.  `OPEN_BUS` means the chip LEFT THE IMAGE and
read bus feedthrough while the model did not, so the model's instruction log is
not the chip's instruction stream there — the ruler is invalid by construction,
not by excuse.  **THIS STRATIFICATION IS POST-HOC**: it was chosen after seeing
which seeds missed, and it is a mitigation of a failed bar, not a rescue of it.
It is written down as such, and the landing below does not rest on it: a landing
is scored against silicon per clock, with no ruler in the loop, so **the landing
is its own falsifier**.

One more thing the held-out run found and one seed decides it, so it is an
OBSERVATION and NOT a clause of the law: on `t30-raw/920` the `0F`
two-byte-opcode ESCAPE behaves as a boundary exactly as a prefix does.

### §84.3 WHAT THE LAW ACTUALLY IS — **ONE FLOOR, NOT TWO OPCODES**

§84.1 wrote the POPF/IRET asymmetry as *"`IRET`'s PSW write lands before its own
boundary's sample; `POPF`'s lands after it."*  Landing it exposed that as a
DESCRIPTION, not a mechanism — and the ROM refutes the obvious reading of it:
**007A and 01EA are BOTH `OPR -> FLAGS  F E` rows, both the `E` row of their
sequence, both followed by exactly one post-`E` row.**  The geometry is
identical.  The difference is CLOCKS, and it is §72's shape:

> **The arm does not see a `TF` that rose too recently.**  Sampled at the
> instruction's retire, a rise fewer than **3 clocks** earlier is not there yet.

and that single floor produces the asymmetry with neither opcode named, because

* `9D` retires **AT** its own flag write — 007A is its `E` row and nothing
  follows but `SIGMA -> SP`;
* `CF` **FLUSHED THE QUEUE** at 01E8, so it cannot retire until a refill lands.

MEASURED, over the 29 scored seeds, as *clocks from the rise to the retire that
samples it* — and **the only two opcodes that ever raise TF in the whole
population are `9D` and `CF`**, which is the law's premise verified rather than
assumed:

| opcode | clocks rise → retire | n |
|---|---|---|
| `9D` `POPF` | **1** (×16), **2** (×12) | 28 |
| `CF` `IRET` | **6 … 26** | 813 |

**Nothing in between.**  The floor is bounded by the data to **[3, 6]** and no
value in that interval is separable on this population.  **3 is taken because it
is not a new constant**: it is the depth the INT LEVEL already pays to reach
this same decision (`timed_runner.cpp`'s `evpipe`, `docs/facts/interrupt_model.md`).

*Falsifier*: any instruction whose TF rise is 3, 4 or 5 clocks before the retire
that must sample it — that case separates [3, 6] and this tree has none.  Any
third opcode raising TF falsifies the premise.

### §84.4 THE LANDING IN THE C++ TIMED ENGINE, AND ITS PRE-REGISTERED BAR

`sim/exec_impl.h` (the arm, the floor, the take at retire), `sim/biu_timed.{h,cpp}`
(`brk_rise_`, sampled by the SAME `sample_ie()` call that already reads the live
PSW — one more comparison on a word in hand), `sim/timed_runner.cpp` (the entry;
program replay only).  It is **the existing recognition**: `at_fire_boundary()`
gains one term, so the trap rides `boundary_no_pop` and the M14 entry like every
other recognised boundary.  Nothing names an opcode anywhere.

**MEASURED ON THE 30-SEED CELL** (`--seeddir`, the 29 + the control):
`EXACT` **1 → 11**.  **Ten of the 29 close cycle-exact**; `mc2/2361`, the
software-INT control, is **unmoved and still EXACT**; **no seed regressed** and
every seed's first divergence moved LATER or stayed.

**PRE-REGISTERED, before the full ladder is run:**

* `timed_fuzz --core sim --evt-replay`: REGISTERED **≥ 1,282** (1,272 + the ten),
  EVT **≥ 788**, COMBINED **≥ 2,070**; and **no seed that was EXACT may become
  non-EXACT** — that is the real bar, and it is checked seed-by-seed, not by the
  totals.
* MUST NOT MOVE, `--core sim` / model legs: `make -C sim test`, `pla3_check`
  (21), the `ucsim_check` suites, `timed_gate v0.1 --forms all` 169,000,
  `v0.1-w1`/`-w3` 1,200, `EB` 200, the four `evt` cells 200/1,200/200/1,200,
  `w1evt-biased` 1,200, `check_boot --timed 220`, `timed_scenario` 18/0/9,
  `timed_enter_replay` 154×5, `timed_ins_replay` 1,312 / 2,624, `timed_wvec_gate`
  88/88, `timed_lawcards` 8/0/3, the four HLT sweeps 91/95/44/42, and
  `--seeddir b2-tranche` 154/188.
* **FALSIFIER**: any of those moving DOWN by one cell is a REGRESSION and the
  landing is reverted, not renegotiated.

### §84.5 THE LADDER — **EVERY REGISTERED CELL RE-RUN ON THE FINAL BINARY**

| gate | registered | this sitting |
|---|---|---|
| `timed_fuzz --core sim --evt-replay` REGISTERED | ≥ 1,282 | **1,282 / 1,702** (was 1,272) |
| … EVT | ≥ 788 | **789 / 1,008** (was 788) |
| … COMBINED | ≥ 2,070 | **2,071 / 2,710** (was 2,060) |
| … seed-by-seed | no `EXACT` may be lost | **0 lost, 11 gained** |
| `make -C sim test` | PASS | **PASS** (disasm byte-exact) |
| `pla3_check` | 21 | **21** |
| `ucsim_check v0.1` | 169,000 | **169,000 / 169,000** |
| `ucsim_check mod3_illegal --residue stale-ea` | 128 | **128 / 128** |
| `timed_gate v0.1 --forms all` | 169,000 | **169,000 / 169,000**, row-diffs 0 |
| `timed_gate v0.1-w1 / -w3` | 1,200 | **1,200 / 1,200** each |
| `timed_gate v0.1-w1 --forms EB` | 200 | **200 / 200** |
| the four `evt` cells | 200 / 1,200 / 200 / 1,200 | **200 / 1,200 / 200 / 1,200** |
| `v0.1-w1evt-biased` | 1,200 | **1,200 / 1,200** |
| the four HLT sweeps | model 283/283 | **97 + 95 + 46 + 45 = 283 / 283** |
| `check_boot --timed 220` | MATCH | **MATCH over 220 rows** |
| `timed_scenario` | 18 / 0 / 9 | **18 PASS, 0 FAIL, 9 SKIP** |
| `timed_enter_replay` | 154 ×5 | **154 / 154** on every leg |
| `timed_ins_replay --raw` | 1,312 / 2,624 | **1,312 / 1,312** and **2,624 / 2,624** |
| `timed_wvec_gate` | 88/88, +0.0 % | **88 / 88, +0.0 %** |
| `timed_lawcards` | 8 / 0 / 3 | **8 GREEN / 0 RED / 3 UNRESOLVED** |
| `--seeddir b2-tranche` | 154 / 188 | **154 / 188** |

**NOT ONE CELL MOVED DOWN.**  The single-instruction legs cannot move by
construction and it is worth saying why rather than only that they didn't:
`set_brk_enable(true)` appears at exactly ONE call site in the tree
(`timed_runner.cpp`'s whole-program replay), so the case runner's arm is off and
a case with `TF` injected has no successor boundary to trap at anyway.

### §84.6 PART B — **THE B2a SURVEY: 12 OF 12 ARE THE `8F` mod-3 GHOST READ, AND IT IS THE ONE DOCUMENTED DON'T-CARE**

`sw/sm3_b2a_survey.py`, scoring through `fuzz_classify.diff_rows` (the repo's own
column policy, not a hand-rolled one).  §83.5 booked these 12 as "the BIU's real
residue".  **They are not a BIU class.**

| seed | waits | first row | ins at the divergence | detail | resync | ndiff |
|---|---|---|---|---|---|---|
| `mc1/1543` | fix? | 424 | **`8F C0`** | `nxta 0994!=1e94` | 4 | 3,384 |
| `mc1/2241` | wrand7 | 1,717 | **`8F C2`** | `nxta aab6!=8d40` | 4 | 120 |
| `mc1/2512` | fix0 | 607 | **`8F E6`** | `nxta 0334!=3f00` | 4 | 3,009 |
| `mc2/1104` | fix0 | 164 | **`8F ED`** | `nxta 5559!=3f00` | 2 | 3,807 |
| `mc2/2438` | fix0 | 162 | **`8F DC`** | `nxta 2980!=3f00` | 5 | 3,490 |
| `mc2/2648` | wrand3 | 315 | **`8F DC`** | `nxta 327c!=3efe` | 5 | 2,990 |
| `mc2/3569` | fix0 | 162 | **`8F E9`** | `nxta 0000!=3f00` | 4 | 1,334 |
| `mc2/3805` | fix2 | 260 | **`8F CB`** | `nxta 0100!=3f00` | 4 | 3,710 |
| `t30-raw/428` | fix0 | 652 | **`8F FA`** | `nxta 14d2!=3c54` | 4 | 3,242 |
| `t30-raw/508` | fix0 | 156 | **`8F E3`** | `nxta 0500!=3f00` | 4 | 3,570 |
| `t30-raw/563` | wrand2 | 232 | **`8F CA`** | `nxta 3f00!=3f02` | 2 | 3,595 |
| `t30-raw/962` | fix0 | 521 | **`8F F8`** | `nxta ca00!=ef1c` | 4 | 4 |

**THE INVARIANT IS UNANIMOUS AND IT IS ONE OPCODE.**  Every ModR/M above is
≥ `0xC0`: all twelve are `8F` with **mod == 3**, the undocumented
register-destination `POP` — and the divergent columns are always the same three
in the same order on ONE bus cycle (`nxta`, then `addr` at that cycle's T1, then
`data`), after which the run resynchronises in 2 to 5 rows.  Across all 12 the
divergence-run census is **457 runs, of which exactly 12 are headed by an `8F`
mod3 — one per seed, and always the FIRST**.

**AND THE LEDGER ALREADY WROTE THIS DOWN**, from the other end.
`tests/v30/v0.1/metadata.json` `8F.0.dont_care`: *"it writes NO register, only
`SP += 2`, and issues one stack read whose word is discarded … that read's
committed ADDRESS and its data are stale internal EA/address-latch state carried
in from pre-window execution history … no `(seg<<4)+reg+const` formula fits it
and only PS/CS (fetch-stream shape) perturbs it.  A backdoor-injected core has
no such history and drives the modeled SS:SP."*  **Which is exactly what the
survey measures**: the model drives `0x3f00` — `SS:SP` — on 6 of the 12, and on
`t30-raw/563` it drives `3f02` where the chip drives `3f00`, i.e. the model has
already applied `SP += 2` and the chip's latch still holds the pop's own address.

So B2a is **the ONE documented architectural don't-care being scored by an
instrument that has no don't-care**: `ucsim_fuzz` honours it (`_ghost_8f`), which
is precisely why these 12 are arch-exact, and `timed_fuzz` compares every column
of every row and cannot.

**CANDIDATES, RANKED BY POPULATION EXPLAINED**

1. **The address latch is a RETAINED REGISTER and the `8F` mod3 form does not
   write it** — the ghost read re-issues from whatever `IND` last held.  Covers
   the invariant on 12/12 and covers `t30-raw/563`'s `3f00` vs `3f02` exactly.
   **What is NEW here and is the reason this is worth a cell**: the metadata's
   "no formula fits it" verdict was reached on **INJECTED single-instruction
   cases, where by construction there is no history** — the note says so in as
   many words.  A whole-program replay **runs the image's own loader stub from
   RESET**, so the model has the same history available to it and the question
   has never been asked in that regime.
2. *The ghost read issues from the PRE-increment SP.*  Exact on `t30-raw/563`
   and **refuted on the other 11** (`mc2/1104` would need `3efe` and the chip
   drives `5559`).  Recorded as refuted, not carried.
3. *A BIU launch-timing law.*  **Refuted by the geometry**: the cycle's position,
   its T-states, the surrounding fetches and the queue status are all identical;
   only the ADDRESS differs.  Nothing about this class is timing.

**DISPOSITION — SURVEYED, NOT LANDED, and the honest reason is a number.**
Closing the ghost would close **`t30-raw/962` outright** (`ndiff` 4, the ghost
run and nothing else) and plausibly `mc1/2241` (120 rows, 7 runs).  On the other
ten the ghost is the FIRST run of 8 to 134, and **this survey does not establish
that the remaining 445 runs are its cascade** — they are not headed by an `8F`
mod3 and no attribution is claimed for them here.  A landing sold as "closes
B2a" would therefore be selling 12 seeds when the evidence supports 1, maybe 2.

**THE CELL, SPECIFIED.**  (a) Make `IND` a retained register in the timed model
and issue the `8F` mod3 ghost read from it; (b) pre-register the prediction
per seed — the exact address the chip drove is already banked in the table above,
so this is a 12-cell prediction with no free parameters; (c) score, and
separately measure whether the downstream runs on the ten cascade seeds close
too.  **Falsifier**: any seed where the retained `IND` reproduces neither the
chip's address nor the model's.  The alternative disposition — giving the timed
comparator the same don't-care the architectural one already has — is a
COMPARATOR change after seeing a result and is NOT taken here.

### §84.7 THE `ucore` LEG — **SPECIFIED, NOT LANDED, AND THE SPEC IS THE C++ EDGE FOR EDGE**

The RTL leg is NOT in this sitting and is booked as the next one's first item.
It is small and it is already named by the core's own structure:

* `v30u_eu.sv` already pipelines `psw[FIE]` through **`ie_p[3:0]`** and demands
  "IE up NOW **and** up three clocks ago" at `at_bnd`.  **§84.3's floor is the
  same three clocks on the same kind of pipeline**, so the arm is `brk_p[3:0]`
  built the same way from `psw[FBRK]`, and the take is `at_bnd && brk_p[3]`.
* `FBRK` already exists and is already CLEARED on entry (`I_CITF`,
  `v30u_eu_poste.svh` vector 1); nothing reads it, which is the whole gap.
* The entry is the existing one — the vector-1 door §71 already routes.
* **THE ONE PLACE THE TWO ENGINES DO NOT ALREADY AGREE** is the PREFIX
  boundary: `v30u_eu.sv` states outright that it distinguishes `S_OPC_POP` from
  the one a prefix hands over, "which is the measured *no sample between 26 and
  8B*".  §84's arm needs the prefix boundary to SAMPLE (it is what makes
  `mc2/1354` and `t30-raw/65` trap one boundary early) while the ucore's INT
  recognition needs it not to TAKE.  **Those are consistent — sample and take
  are different events at the same boundary** — but the RTL must say so
  explicitly rather than inherit `bnd_armed`.
* Gates owed with it: `ulockstep --golden all --cases 50` 17,350/17,350 as the
  same-mechanism proof, the whole ucore ladder, `ss_lint` (**an `SS_VERSION`
  bump is owed** — `brk_p` is 4 architectural-adjacent flops and the census is
  a gate), and a G6 receipt.

### §84.8 THE RATCHETS THAT MOVED

| gate | before | after |
|---|---|---|
| `timed_fuzz --core sim` REGISTERED | 1,272 / 1,702 | **1,282 / 1,702** |
| `timed_fuzz --core sim` EVT | 788 / 1,008 | **789 / 1,008** |
| `timed_fuzz --core sim` COMBINED | 2,060 / 2,710 | **2,071 / 2,710** |

Everything else in §84.5 is UNMOVED.  **The `ucore`'s columns are untouched and
are still 1,490 / 918 / 2,408** — the model now BEATS the ucore on 11 seeds it
did not before, and that gap is §84.7's work item, not a ucore regression.

The eleven closers: `mc1/2034`, `mc1/2952` (EVT), `mc1/3090`, `mc2/1107`,
`mc2/1718`, `mc2/1738`, `mc2/2960`, `t30-raw/682`, `t30-raw/736`, `t30-raw/750`,
`t30-raw/768` — and `mc2/1718` is one of §83.2's three sharp seeds.

### §84.9 WHAT THIS SITTING DID NOT DO

* **NO BOARD CONTACT, NO FLASHING, `use_core` NEVER SET.**  The board still
  carries FLASH #9.
* **The `ucore` RTL was not touched.**  §84.7 specifies it.
* The architectural model's own `tf` rule (`image_runner.cpp`) was NOT touched:
  it is model-only work, it is frozen, and §83.4 already refuted it.  It is now
  **known wrong in a named way** — it arms at the setter's own boundary where
  silicon needs three clocks — and closing it is a separate item.
* B2a is surveyed and NOT landed; §84.6 gives the number that says why.
* `TAIL_EXTRA` / the last-2 closers, H3-B, and the 8080 work were not opened.
  No memory file was touched.  Codex was not launched.

## §85 SESSION SM3, SITTING 24 — **THE FLOOR, MEASURED: THE ERRATUM, THE DIRECTED CELL, AND THE DISPOSITION**

### §85.0 THE ERRATUM — **§84's LANDING WAS SCORED ON THE POPULATION THAT SELECTED IT, AND THAT SCORE IS STRUCK**

Stated plainly, because a truthful ledger is worth more than a clean one.

§84.1 pre-registered candidate law **A** and a held-out bar.  §84.2 ran it and
**the registered falsifier FIRED** — V-1's zero-miss clause failed with 3
misses on the branch the law was most constrained on.  The disposition law A had
bought, in its own words, was *"the law is booked REFUTED and NOTHING is
landed"*.

§84.3 then re-read **THE SAME 29 SCORED SEEDS** plus the microcode ROM and
produced law **B** — one floor, neither opcode named.  Law B is a better law:
it is simpler, it names no opcode, and the ROM evidence (007A and 01EA are both
`OPR -> FLAGS  F E` rows with identical geometry) is real.  **But its landing
was then SCORED on that same 30-seed cell**, `EXACT 1 → 11`.

That is the §64.1 pattern exactly — the H1-re-key precedent, and Codex concern
1: *a key re-fitted on the population that refuted its predecessor, then graded
on it.*  A held-out bar consumed by law A does not carry over to law B.

**THE RULING (coordinator, this sitting).**

1. **The `EXACT 1 → 11` figure is STRUCK as evidence for law B.**  It is not
   deleted and it is not restated: it happened, it is reproducible, and it is a
   FIT statistic, not a validation.  §84.5's ladder is unaffected — it is a
   non-regression check, not a confirmation.
2. **The landing stands PROVISIONALLY**, on two things that are not the struck
   figure: (a) the full-corpus non-regression, **0 `EXACT` lost over 3,242
   seeds**, which no re-fit can manufacture; and (b) **this sitting's cell**,
   which is a population that did not exist when law B was written.
3. **§85.1's cell is the required disjoint validation.**  Its dispositions —
   confirm-and-lift, correct-the-constant, or REVERT — were registered before
   the first board contact, in `docs/notes/sm3_s24_prereg_2026-08-05.md` §6.

**AND THE ERRATUM IS ALSO A FINDING ABOUT THE METHOD, NOT ONLY ABOUT §84.**  The
reason law B could be scored on its selecting population without anyone noticing
is that the SCORE CHANGED INSTRUMENT: law A was graded by a RULER (`predict_head`
against the model's `ilog`) and law B by a LANDING (per-clock rows against
silicon).  Two different numbers, both honest, and the population underneath
them never moved.  **A change of instrument is not a change of population**, and
that sentence is the general lesson.

### §85.1 THE CELL — pre-registered at `sm3_s24_prereg_2026-08-05.md`

**What is undetermined**: §84.3 bounds the floor to **[3, 6]** and says so
itself; 3 was CHOSEN as `evpipe`'s existing depth, not measured.  Its own
falsifier is *"any instruction whose TF rise is 3, 4 or 5 clocks before the
retire that must sample it — this tree has none"*.

**The cell manufactures exactly those.**  `sw/sm3_tf_floor_cell.py`: periodic
sleds `9D ; <PAD> ; 90 ×5` with a planted `0xF102` (BRK set, **IE clear**), the
pad's clock length walking `dist(rise → B1)` over **2, 3, 4, 5** at w0 and
**3, 4, 5, 6** at w3 — the whole undetermined interval from both sides — plus
13/20/25/26 as saturated controls.  The observable is the vector-1 entry's third
push, i.e. **the boundary the part chose**, read off the pins with NO ENGINE
(§72's reader, one vector over).  The handler CLEARS `TF` in the frame it
returns through, so one capture carries ~40 independent repeats.  Controls:
three TF-CLEAR sleds that must trap ZERO times, an `iret` sled that differs from
`popfnone` by the setter alone, and a `storm` sled for the cadence.

**All seven candidate floors have DISTINCT predicted signatures**; the tightest
pair, 3 vs 4, still separates on three independent cells.  The `V30SIM_BRKFLOOR`
env knob (default the landed 3, read by no gate) is what lets the engine be
wrong on purpose so that the prediction table can exist at all.

### §85.2 THE RUN — **THE BARS AS REGISTERED, AND THE ONE THAT FAILED IS AN INSTRUMENT DEFECT THE CELL'S OWN CONTROLS FOUND**

**BOARD SESSION.**  `sw/sm3_tf_floor_cell.py run`, socket only
(`EMIT_USE_CORE` False), `div_guard` **PINNED** (`div=8 (4 MHz), commanded by
this connection`), **90 captures** (15 sleds × 2 waits × 3 repeats), 4,063 rows
each, 0 transport errors, ~10 s of board time, full per-clock rows + raw 64-bit
words, **184 files under `SHA256SUMS`**, `board_idle()` run and OK.  **NO
FLASHING** — the board carries FLASH #9.  **NO PIN WAS DRIVEN AT ALL**: the trap
is internal, so `evt` is `None`, there is no hold and no `fired`, and INV-1's
directive-truncation exposure does not exist here.

| bar | registered | measured |
|---|---|---|
| **W-0a** the TF-clear null | 0 vector-1 entries | **0**, over 18 captures — **MET** |
| **W-0b** the clock ruler | 0 row-diffs chip vs engine on the law-free controls | **0 / 24,378 rows** — **MET** |
| **W-1** determinism | 3 repeats identical | **every one of the 30 cells identical** — **MET** |
| **W-2** the floor | \|S\| == 1 | **S = ∅.  NOT MET.** |
| **W-3** the asymmetry | `iret` phase 2, `popfnone` phase 3, both waits | **iret [2, 2], popfnone [3, 3]** — **MET** |
| **W-4** no take at a prefix boundary | 0 | **0**, and **0** pushed IPs that are not an instruction start — **MET** |
| **W-5** storm grace 0 | every consecutive pair | **90 / 90 pairs** — **MET** |

**W-2 IS REPORTED AS REGISTERED AND IT IS NOT RESTATED.**  What its failure
LOOKS like is a separate statement: **floor 3 matches 21 of the 22 scored cells
and the single miss is `popfclc` at w0** — the same sled at w3 HITS.  Scored the
sharper way the cell also registered (W-6, per clock, chip vs engine, every
capture) — **these are the AS-REGISTERED figures, on the instrument as it stood
before §85.2a; the corrected column is in §85.2b**:

| floor | rows | row-diffs (as registered) |
|---|---|---|
| 1 | 121,890 | 71,324 |
| 2 | 121,890 | 33,951 |
| **3** | **121,890** | **3,602 — and ALL 3,602 are `popfclc` w0; the other 29 captures are 0** |
| 4 | 121,890 | 14,580 |
| 5 | 121,890 | 40,226 |
| 6 | 121,890 | 61,049 |
| 7 | 121,890 | 68,011 |

### §85.2a THE DEFECT — **ONE CLOCK, ONE OPCODE, AND THE CELL'S OWN REGISTERED CONTROLS ARE WHERE IT IS VISIBLE**

**W-0b had the RIGHT POPULATION AND THE WRONG STATISTIC, and the run is what
says so.**  Its control sleds carry `TF` clear, so they contain no law at all —
that is why they are the ruler check.  But the statistic registered for them was
BUS row-diffs, and `F8` (`CLC`) makes no bus cycle: a one-clock error in a
bus-free instruction's *retire instant* cannot reach any column of any row.  It
is invisible to every gate in the tree.

The right statistic on the SAME registered population is the one the chip
publishes: **`QS = 1`, the opcode pop.**  Pairing every `brk_retire` clock with
the chip's own next pop in the same capture:

| opcode | retire − successor's pop | n |
|---|---|---|
| `90` `9D` `8B` `8E` `B8` `E7` `CF` | **+1** | **459 of 459** |
| **`F8`** | **+0** | **70 of 70, at BOTH wait levels** |

**Unanimous, and it is one opcode.**  `F8` is `ONE_BYTE_LOGIC` in
`loader_impl.h`: its accounting is `wait_retire_lead()` — which lands on the
clock BEFORE the successor's pop, where the flag write commits, exactly as that
file's own MEASURED comment says — plus `charge(1)`, so it stops **at** the pop.
A ROM form's stops **one past** it.  The two retire paths did not agree about
where a boundary is, and the single-step arm is the only thing in the tree that
reads that instant.

**THE CORRECTION** (`sim/exec_impl.h`, `brk_retire(op, predecode)`): on the
pre-decode-executed path the arm's sample instant is `biu_.clock() + 1`.
Nothing is charged — charging would move the bus, and the bus is already exact.

**ITS ACCEPTANCE TEST IS NOT THE FLOOR VERDICT**, which is the whole point:
it is *"every opcode's `brk_retire` clock is exactly one past the chip's next
`QS = 1` pop, on a capture with `TF` clear"*.  Measured after the fix over
**2,900 boundaries** on the six control captures: **0 violators** (one retire
falls past the capture window's last pop and is excluded as a window edge).
The pre-registered prediction table regenerated on the corrected instrument
differs in **`popfclc` and nothing else** — 2 cells of 30 move, and they are the
only two containing an `F8`.

### §85.2b THE VERDICT — **THE FLOOR IS 3, AND IT IS NOW MEASURED RATHER THAN CHOSEN**

Re-scored on the corrected instrument, and **both scores are reported; the
registered one is not replaced**:

| W-2, scored against | surviving floors | floor 3 |
|---|---|---|
| `predictions.json` — **THE PRE-REGISTERED TABLE** | **∅ — the registered bar, NOT MET** | 21 / 22 cells |
| `predictions_corrected.json` — the same table, §85.2a's instrument | **{3}** | **22 / 22 cells** |

and per clock, chip vs engine, **every capture in the cell**:

> **floor 3: 121,890 rows, 0 row-diffs.  EXACT on all 30 captures.**
> Floors 1, 2, 4, 5, 6, 7 are 71,324 / 33,951 / 11,032 / 40,226 / 61,049 /
> 68,011.  **No other value in [1, 7] is within four orders of magnitude.**

**§84.3's own falsifier is EXERCISED AND DOES NOT FIRE.**  It asked for *"any
instruction whose TF rise is 3, 4 or 5 clocks before the retire that must sample
it"*; this cell supplies rises at **2, 3, 4, 5** clocks at w0 and **3, 4, 5, 6**
at w3, forty times per capture, and every one of them behaves as a floor of 3
says it must.  The bound §84.3 could only write as **[3, 6]** is now **{3}**.

**AND THE `evpipe` JUSTIFICATION IS RETIRED AS A JUSTIFICATION.**  §84.3 took 3
*"because it is not a new constant"*.  That was a reason to prefer it, never
evidence for it.  It is now measured, and the fact that it coincides with the
INT level's depth is a RESULT — two recognitions reaching the same decision
through the same three clocks — not an argument.

**WHAT THE OTHER BARS ADD, and they are not decorations:**

* **W-3 refutes the boundary-count reading outright.**  `iret` and `popfnone`
  have the SAME 6-byte period, the same NOP run, and differ only in the setter.
  A rule of the form *"the setter's own boundary never samples"* — which fits
  all twenty `popf*` cells perfectly — predicts `iret` at phase 3.  **The chip
  says 2, at both waits.**  Only a CLOCK floor gets both, because `CF` flushed
  the queue and its own retire is 6 (w0) / 11 (w3) clocks past its rise.  §84.1
  wrote this asymmetry as an opcode rule; here it is a consequence, measured on
  a population built for it.
* **W-4** puts a number on the take-at-retire clause: `popfpfx`'s period offset
  2 is the prefixed opcode and is NOT an instruction start, so a trap taken AT
  the prefix boundary would push exactly that address.  **Zero did**, and zero
  pushed IPs anywhere in the cell failed to be an instruction start.
* **W-5** re-runs §84's V-2 on a directed storm: **90 / 90 consecutive pairs at
  grace 0.**

### §85.2c WHAT IS STILL OWED, STATED PLAINLY

The registered bar W-2 **FAILED** and was re-scored only after an instrument
fix.  The fix is small, it is mechanism-level, its acceptance test is
engine-free and independent of the floor, and it was found in the cell's OWN
REGISTERED CONTROL POPULATION rather than in the failing cell — but it was
applied **after** the failure was seen, and that is written here rather than
smoothed.  Two things stop it being §84.2's pattern repeated:

1. **The fix cannot manufacture the verdict.**  It moves exactly two of the
   thirty cells, both `popfclc`, and floor 3 was already 0 row-diffs on the
   other twenty-eight *before* it.  The 4-vs-3 decision is carried by
   `popfinc` w0 and `popftest` w0, which contain no `F8` and did not move.
2. **The correction is falsifiable on its own terms**, by a test that never
   looks at a trap: `sim/exec_impl.h`'s falsifier beside it.

The **§85.0 provisional status** is therefore recommended LIFTED on this
evidence, and the recommendation is flagged for review rather than asserted.

> **COORDINATOR RULING, 2026-08-05 (review of sitting 24): LIFTED.**  The
> disjoint-validation requirement §85.0 imposed is met: the cell's population
> did not exist at selection; the law shape held on every bar that bears it
> (W-0a/0b, W-1, W-3, W-4, W-5); the floor is MEASURED at 3 with the per-clock
> table decisive (0 row-diffs at 3 over 121,890 rows against ≥11,032 at every
> other value); and the W-2 instrument correction is firewalled from the
> verdict by both of §85.2c's arguments (the discriminating cells contain no
> `F8` and did not move; the correction carries its own trap-free acceptance
> test at 0 violators / 2,900 boundaries).  §84's sim landing is no longer
> provisional.  Its evidentiary basis is THIS cell + the full-corpus
> non-regression; the struck 1→11 selecting-cell figure stays struck.  The
> ucore leg proceeds from §85.3's corrected spec (arm flop + floor pipeline +
> prefix sample-not-take), not §84.7's refuted one.

### §85.3 THE `ucore` LEG — **NOT LANDED, AND THE CELL REFUTED THE SPEC IT WAS GOING TO BE LANDED FROM**

§84.7 wrote the RTL leg as small and already named by the core's own structure:

> `v30u_eu.sv` already pipelines `psw[FIE]` through **`ie_p[3:0]`** and demands
> "IE up NOW **and** up three clocks ago" at `at_bnd`.  §84.3's floor is the same
> three clocks on the same kind of pipeline, so the arm is `brk_p[3:0]` built the
> same way from `psw[FBRK]`, and **the take is `at_bnd && brk_p[3]`**.

**THE TAKE IS NOT `at_bnd && brk_p[3]`, AND THIS CELL IS WHAT SAYS SO.**  That
form is a PURE COMBINATIONAL GATE at the boundary — which is exactly right for
the IE recognition, because a level-sensitive request is still there at the next
boundary if it was not taken at this one.  **A trap is not a request.**  The
single-step arm is a bit that is SAMPLED at one boundary and TAKEN at the NEXT,
and the difference is one whole boundary on every sled in the cell.

Under any pure gate — *take at the first boundary at which `TF` has been up for
at least `N` clocks*, for **any** `N` — the fitting values of `N` are, per cell:

| sled (w0) | walk `B0..B4` | chip phase | `N` that fit a pure gate |
|---|---|---|---|
| `popfnone` | 1, 4, 7, 10, 13 | 3 | 5, 6, 7 |
| `popfclc` | 1, 3, 6, 9, 12 | 3 | 4, 5, 6 |
| `popfmemr` | 1, **13**, 16, 19, 22 | 4 | 14, 15, 16 |
| `popfmul` | 1, **25**, 28, 31, 34 | 4 | 26, 27, 28 |
| `iret` | 6, 10, 13, 16, 19 | 2 | 7, 8, 9, 10 |

**The sets are DISJOINT — `{5,6,7}` against `{26,27,28}` — so no `N` exists.**
The two sleds that kill it are the SATURATED CONTROLS, `popfmemr` and `popfmul`,
whose `B1` sits 13 and 25 clocks after the rise: any floor worth the name is
long since satisfied there, and the chip STILL waits one more boundary.  That is
an arm bit, not a gate, and it is measured.  (The landed C++ shape — sample at
`B_j`, take at `B_{j+1}` — fits every cell at `N = 3`: W-6, 0 row-diffs on
121,890 rows.)

**SO THE `ucore` LEG NEEDS, and this is the corrected spec:**

* `brk_p[3:0]`, `psw[FBRK]` through the same three flops as `ie_p` — **this part
  of §84.7 stands**, and it supplies the FLOOR term `brk_seen = psw[FBRK] &&
  brk_p[2]`;
* **plus a real ARM FLOP** that crosses boundaries: at every sampling boundary,
  `if (take) arm <= 0; else arm <= brk_seen;` and `take = at_bnd && arm`.  It is
  ONE flop and it is the thing §84.7 did not have;
* the SAMPLING boundaries are the retire boundaries **and** the prefix
  hand-over, which the RTL currently and deliberately excludes: `bnd_armed` is
  what separates the `S_OPC_POP` a prefix hands over from a real boundary,
  "which is the measured *no sample between 26 and 8B*".  §84.7 already flagged
  this as the one place the two engines do not agree, and **W-4 confirms the
  half of it that constrains the RTL**: 0 traps taken at a prefix boundary,
  0 pushed IPs that are not an instruction start, over 108 entries.
  Sample and take are different events at the same boundary and the RTL must
  say so explicitly rather than inherit `bnd_armed`.
* the entry is the existing vector-1 door §71 routes; `FBRK` is already cleared
  on entry by `I_CITF` (`v30u_eu_poste.svh` vector 1).

**GATES OWED WITH IT** (unchanged from §84.7, plus one): `ulockstep --golden all
--cases 50` 17,350/17,350 — and it is worth saying that **lockstep on the golden
set is VACUOUS for this trap**, because a single-instruction case has no
successor boundary to trap at and the case runner leaves the arm off, exactly as
in the C++; the cross-engine proof is this cell's 30 captures scored against
BOTH engines.  Plus the whole ucore ladder, an `SS_VERSION` bump (`brk_p` and
the arm are 5 architecture-adjacent flops and the census is a gate), a G6
receipt — **and `sw/sm3_tf_floor_cell.py` re-scored with the ucore as the
engine, which is now the sharpest gate the trap has: 121,890 rows, and the model
is at 0.**

**NOTHING WAS LANDED IN `hdl/rtl/` THIS SITTING.**  `git diff` against it is
empty.  Landing the corrected spec, with its own ladder and receipt, is the next
sitting's first item — and it is now a landing against a MEASURED spec instead
of an inferred one.

### §85.4 THE RATCHETS

**NOTHING MOVED.**  §85.2a's correction is read by the single-step arm and by
nothing else, and the arm exists only in whole-program replay.  Re-run on the
final binary:

| gate | registered | this sitting |
|---|---|---|
| `timed_fuzz --core sim --evt-replay` REGISTERED | 1,282 | **1,282 / 1,702** |
| … EVT | 789 | **789 / 1,008** |
| … COMBINED | 2,071 | **2,071 / 2,710** |
| `--seeddir b2-tranche` | 154 / 188 | **154 / 188** |
| `make -C sim test` | PASS | **PASS** |
| `pla3_check` | 21 | **21** |
| `ucsim_check v0.1` | 169,000 | **169,000 / 169,000** |
| `ucsim_check mod3_illegal --residue stale-ea` | 128 | **128 / 128** |

**NEW, and it is this sitting's own:**

| gate | value |
|---|---|
| `sm3_tf_floor_cell score` W-6, **floor 3** | **121,890 rows, 0 row-diffs, all 30 captures** |
| … the same at floors 1, 2, 4, 5, 6, 7 | 71,324 / 33,951 / 11,032 / 40,226 / 61,049 / 68,011 |
| W-0a the TF-clear null | **0 entries, 18 captures** |
| W-1 determinism | **30 / 30 cells identical across 3 repeats** |
| W-3 the `iret`/`popfnone` asymmetry | **phase 2 vs 3, both waits** |
| W-4 traps taken at a prefix boundary | **0 of 108 entries** |
| W-5 storm grace | **0 on 90 / 90 pairs** |

## §86 SESSION SM3, SITTING 25 — **THE `ucore`'s BRK/TF LEG IS LANDED AND IT IS FIVE FLOPS. THE SAMPLING BOUNDARY TURNED OUT TO BE ONE PREDICATE, NOT TWO — IT IS THE `QS = 1` POP — AND THE DEPTH IS 4 BECAUSE THE COORDINATE IS ONE CLOCK OVER, WHICH SILICON AND THE TWO ENGINES SAY INDEPENDENTLY. AND `TAIL_EXTRA` IS THE ILLEGAL-FORM HALT THE LEDGER ALREADY WROTE DOWN, ONE FAMILY WIDER.**

Pre-registration: `docs/notes/sm3_s25_prereg_2026-08-05.md`, committed at
`4cca409483` **before any RTL was edited and before any figure below was
measured**.

> ### ⚠ §86 ERRATUM — **THE SAMPLING BOUNDARY IS NOT THE `QS = 1` POP, IN EITHER DIRECTION** (`KM`, 2026-08-11)
>
> *This ledger is CLOSED at §88 and is not appended to. This block is an
> ERRATUM, not an addition: it is written here because §86's own sentence is
> refuted by later silicon and a closed ledger with an unmarked refuted claim in
> it is worse than one with an erratum in it. Nothing of §86 is deleted.*
>
> §86.A registers the sample as *"`q_pop && q_ripe && q_first`"* and reasons
> that this is ONE predicate because *"a prefix retires as its own two-clock
> instruction with its own F pop … **and so does the `0F` escape's first
> byte**"*, concluding **"the sampling boundaries are simply the opcode pops the
> `QS = 1` pins announce."** The directed board cell
> (`docs/notes/tf0f_cell_results_2026-08-11.md`; prereg `f08a597ed5`, amendment
> `c13ec814f3`; FLASH #17, 512 cells over 4 waits × 4 alignments, **2,880 scored
> traps per engine**, derivation **16/16** and a **DISJOINT validation 14/14**)
> corrects it as follows.
>
> * **RIGHT IN KIND, WRONG IN COUNT — the prefix half.** A prefix STACK
>   contributes **ONE** extra boundary unit whatever its depth. `pfx1 … pfx4`
>   (`2e01d8`, `2e3e01d8`, `2e3e2601d8`, `2e3e263601d8`) read `pushed_off`
>   7 · 8 · 9 · 10 — **two units at every depth** — on **both engines**, 384
>   traps, no exception. "Four prefixes contribute four boundaries" is false.
> * **NEVER IMPLEMENTED, AND THE WRONG BYTE — the `0F` half.** *"…and so does
>   the `0F` escape's first byte"* was **not in the RTL**: `S_EXT_CHG1` set
>   nothing, and `pop_is_first` is read only when `st == S_OPC_POP`, so the
>   sentence could not have been true of this core. It is also the wrong byte:
>   what silicon counts is the escape's **SECOND** byte — the opcode, popped in
>   `S_EXT_POP` — which the pins announce **SUBSEQUENT** (`QS = 3`) on both
>   engines. Measured: the eleven bare-`0F` legs are the whole divergence, the
>   chip one unit earlier on every one of them, **176 of 512 cells**, same
>   direction, every wait, every alignment.
> * **THEREFORE THE QUOTED SENTENCE IS REFUTED IN BOTH DIRECTIONS, AND
>   ENGINE-FREE** (cell §6, measured off the pins with no engine in the loop):
>   on a prefix stack the pins announce **MORE** than the boundary uses (`pfx4`:
>   five `QS = 1`, two units), and on a bare `0F` silicon uses a boundary the
>   pins do **NOT** announce. The QS streams of chip and core are identical on
>   **480 of 480** compared cells, so the divergence was never in the queue, the
>   pop or the decode front end — only in what CONSUMES the stream.
>
> **WHAT §86 GOT RIGHT AND IS NOT TOUCHED.** The sample INSTANT (one clock past
> the pop), `brk_arm` as ONE flop holding a LEVEL, the TAKE at `bnd_fire`, the
> `01D8` row-0 / row-2 door, the depth-4 pipeline, and the five flops. **The
> saturation `KM` requires was ALREADY structural in this core** and needed
> nothing added: the arm is a bit and the take is gated by `bnd_armed`, which is
> set only at a RETIRE, so extra samples inside an instruction cannot move its
> trap earlier than its own boundary. That is why `pfx1 … pfx4` were already
> right.
>
> **THE CORRECTION IS ONE TERM**, landed 2026-08-11 with no flop, no save-state
> address and no opcode named — `wire q_bnd_pop = q_first || (st == S_EXT_POP);`
> feeding `brk_smp_n` alone, with the `QS` pins, `eu_halt` and `first_pop_seen`
> deliberately left on `q_first`. Pre-registration
> `docs/notes/tf0f_km_landing_prereg_2026-08-11.md`, results
> `docs/notes/tf0f_km_landing_results_2026-08-11.md`.
>
> ⚠ **WHAT THIS DOES NOT RESOLVE.** `pushed_off` measures the COUNT of units a
> probe contributes (1 vs 2), **not WHERE the second one sits**. *"The second
> boundary is at the opcode byte"* remains an INTERPRETATION of the count; the
> `IRET`-setter cell that would measure it is **not built** (cell §5.2,
> registered in its amendment A-1.2a before the validation data existed).
>
> ### ⚠ §86 ERRATUM-2 — **THE `IRET`-SETTER CELL IS BUILT, AND THE POSITION
> QUESTION HAD A FALSE PRESUPPOSITION** (`KR`/`KS`, 2026-08-11, coordinator
> booking of `docs/notes/iret_tf_cell_results_2026-08-11.md`; prereg
> `53242e3865`, derivation `22151f64c7`, disjoint validation `457694f5de`;
> FLASH #17, 1,072 cells, 0 transport errors)
>
> * **KR (silicon): the TF trap is TAKEN at an instruction RETIRE and at
>   nothing else.** A prefix hand-over and an `0F` escape's re-decode are
>   SAMPLE events only — never a place the trap can land. Proved
>   constructively with a NOP-filler instrument that separates the four
>   candidate hand-over positions by 3-7 bytes: all four are EMPTY
>   (`P1_p4x` reads 13, the retire, where the hand-over rules predict
>   6/9/10). At filler 0 — the `tf0f` geometry — all candidates collapse to
>   one number, which is why `tf0f` could not see this. The 20-rule
>   pre-registered product collapses to ONE rule (`S1.*.B0`), **49/49
>   derivation + 14/14 disjoint = 63/63**.
> * **KS (silicon): a `popf` setter arms on the SECOND boundary pop after
>   it; an `IRET` setter arms on the FIRST.** No new mechanism — §86.B's
>   existing 4-clock floor explains both (a `popf` rise lands inside the
>   floor of its own retire; an `IRET`'s is cleared of it by the flush and
>   refetch). §86.C's "W-3 asymmetry" is ANSWERED by this.
> * **`KM`'s COUNT law is VALIDATED on the disjoint setter** (24 IRET-set
>   legs hold it); **`KM`'s INTERPRETATION `Bd` ("the second boundary is at
>   the opcode byte") is REFUTED** (31/49 derivation, 2/14 validation).
> * **The ucore already implements KR** (`bnd_armed` is set only at a
>   retire): chip vs core **0 of 1,072 cells differ**, QS streams identical
>   1,072/1,072. **No RTL candidate arises from this cell.** It also
>   EXCLUDES a take-position defect as the explanation for `fz2c/404041`'s
>   pre-KM residue — that residue is elsewhere.

### §86.A THE LANDING — the arm, and the one thing §85.3 asked for twice that is really once

`v30u_eu.sv` + `v30u_eu_step.svh` + `v30u_eu_row.svh` + the two save-state
includes. **Five flops, no opcode named anywhere:**

* **`brk_p[3:0]`** — `psw[FBRK]` frozen at the same instant and shifted in the
  same block (g) as `ie_p`, so the floor term is `psw[FBRK] && brk_p[3]`:
  `ie_p`'s own sentence one bit over.
* **`brk_arm`** — THE ARM.  §84.7's pure gate is refuted (§85.3); this is a bit
  SAMPLED at one boundary and TAKEN at the next.
* **`brk_smp`** — the sample instant, one clock past the boundary's own F pop.
* **`irq_sel_brk`** — which of the three doors `S_IRQ_D` walks through.

and two events:

* **TAKE** — `bnd_fire = at_bnd && brk_arm`, on the EXISTING boundary wire, at
  the five sites that already reach `S_IRQ_D`, which also clear the arm.  The
  entry is the door that was already there: **`01D8` is `CONST 1` at row 0 and
  `CONST 2` at row 2**, so the single-step vector and the NMI vector are the
  SAME ROM entry two rows apart and the trap needs a `loc` of 0 where NMI takes
  2.  `FBRK` is cleared on the way in by `I_CITF`, exactly as `FIE` is.
* **SAMPLE** — on the clock after an **F pop** (`q_pop && q_ripe && q_first`).

**AND THAT SECOND LINE IS THE SITTING'S SIMPLIFICATION.**  §85.3 asked for "the
retire boundaries **and** the prefix hand-over", and §84.7 called the prefix
boundary "THE ONE PLACE THE TWO ENGINES DO NOT ALREADY AGREE".  In this core it
is **ONE PREDICATE, NOT TWO**: a prefix retires as its own two-clock instruction
with its own F pop (`prefix_retire()` → `pop_is_first`), and so does the `0F`
escape's first byte, so *"A PREFIX BYTE ENDS AN INSTRUCTION BOUNDARY"* is
already what the pop stream says.  **The sampling boundaries are simply the
opcode pops the `QS = 1` pins announce.**  Nothing was added to say it.  The
contrast is worth keeping in view: `bnd_armed` exists precisely to EXCLUDE the
prefix hand-over from the INT recognition ("the measured *no sample between 26
and 8B*") — sample and take are different events at the same boundary, and the
RTL now says so in two different wires instead of one commented exception.

Two divergences from the model were **booked in the pre-registration, not
discovered afterwards**: the trap is not shadowed behind a segment-register load
(neither engine shadows it; silicon is documented to, this tree has no cell,
falsifier written down), and `eu_bnd_post` gains an `irq_take` term because the
prefetcher suspend belongs to the recognition that PAYS the IE floor and the
trap never pays it.  The second is provably inert: that wire is only ever
consumed as `eu_bnd_take && eu_bnd_post`, and the old `eu_bnd_take` already
implied `irq_take`.

### §86.B THE COORDINATE, MEASURED TWICE AND FROM BOTH ENDS — **the depth is 4 and it IS the measured floor of 3**

§85.2b measured the floor at **3 clocks from the rise to the sample instant**.
It did not say which RTL clock either end of that is.  Both ends were measured
here, each by a test with **no trap in the loop**, and each was registered
before it was run.

**(A-0), THE SAMPLE END — the registered bar, and it is §85.2a's own statistic
on §85.2a's own population.**  On the six TF-CLEAR control captures
(`notfnone` / `notfclc` / `iretnotf` × w0, w3):

| | measured |
|---|---|
| RTL sample clocks that are not exactly one past an emitted `QS = 1` row | **0 of 1,268** |
| RTL sample stream vs the MODEL's `brk_retire` stream, element for element | **0 mismatches over 1,262 boundaries** |
| traps taken (TF is clear) | **0** |

The RTL stream is the model's **exactly**, plus ONE extra element at the head —
the first opcode pop after RESET, where the RTL has a boundary and the model has
no predecessor instruction to retire.  It samples an arm that reads a cleared
`FBRK` and it is inert.

**THE RISE END — and this is where the 4 comes from.**  The model stamps the
rise inside `sample_ie()`, which is called at the TOP of `tick()`, so a PSW bit
that is up during clock `c` is stamped `rise = c`; block (a) here freezes
`brk_now` off the same register at the same instant and it reaches `brk_p[0]`
one flop later.  MEASURED, engine against engine on the cell's own sleds:

> **`rise_sim = rise_rtl + 1` on 8 of 8 first rises** (`popfnone` / `popfclc` /
> `popfmul` / `iret` × w0, w3).

so the model's `c >= rise + 3` **is** this module's `c >= rise + 4`.  **It is
not a new constant, and the proof that it is not is already in the tree**: the
INT gate reads `ie_p[2]` — three flops — where the model's `kIeFloor` is **2**.
The same offset, on the same kind of pipeline, landed and silicon-validated
three sittings ago.

**AND SILICON SAYS 4 INDEPENDENTLY, BY §85.2b's OWN METHOD.**  `V30_BRK_FLOOR`
is the RTL counterpart of `V30SIM_BRKFLOOR` — a compile-time knob that lets the
engine be wrong on purpose so the table can exist — and the cell was re-scored
with the `ucore` as the engine at every candidate depth in [1, 7], per clock,
against all 30 RETAINED captures (**no board contact; the trap is internal and
the captures are deterministic from RESET**):

| depth | rows | row-diffs |
|---|---|---|
| 1 | 121,860 | 71,304 |
| 2 | 121,860 | 71,304 |
| 3 | 121,860 | 33,941 |
| **4** | **121,860** | **0 — EXACT on all 30 captures** |
| 5 | 121,860 | 14,630 |
| 6 | 121,860 | 43,762 |
| 7 | 121,860 | 61,033 |

**One value is exact and nothing else is within four orders of magnitude** — the
same shape, on the same captures, that gave the model its 3.  *Falsifier,
written beside the define*: any capture on which a depth other than 4 scores
fewer row-diffs against silicon than 4 does.

**THE ORDER THIS HAPPENED IN IS STATED PLAINLY, because §85.0's lesson is this
campaign's.**  The leg was built at depth 3 (§85.3's literal wording), the fuzz
bank was scored at depth 3 and came in at REGISTERED **1,496** against a
registered **≥ 1,500** with **2 seeds lost**, and THAT is what sent the cell's
floor scan out.  The cell did not choose 4 because the bank asked it to: the
cell was **pre-registered as an owed gate at the landed depth** (A-5 / A-6), it
would have failed at depth 3 with 33,941 row-diffs whatever the bank said, and
the rise-coordinate measurement above is independent of both.  The depth-3
figures are recorded here rather than smoothed.

### §86.C THE CELL, `ucore` LEG — the sharpest gate the trap has, and the model's number is the bar

`python3 sw/sm3_tf_floor_cell.py score --core ucore` (new leg; the `--core sim`
leg is byte-for-byte what it was and reproduces §85.2b exactly).

| bar | model (§85.2b) | **`ucore`** |
|---|---|---|
| **W-6** per clock, every capture | 121,890 rows, **0** row-diffs | **121,860 rows, 0 row-diffs, EXACT on all 30** |
| **W-2** surviving depths, on that engine's own prediction table | **{3}**, 22 / 22 cells | **{4}**, **22 / 22 cells** |
| **W-0a** the TF-clear null | 0 entries / 18 captures | **0 / 18** |
| **W-0b** the clock ruler on the law-free controls | 0 / 24,378 rows | **0 / 24,372 rows** |
| **W-1** determinism | 30 / 30 cells | **30 / 30** |
| **W-3** `iret` vs `popfnone` | 2 vs 3, both waits | **2 vs 3, both waits** |
| **W-4** traps taken AT a prefix boundary · pushed IPs that are not a start | 0 · 0 | **0 · 0** |
| **W-5** storm grace 0 | 90 / 90 pairs | **90 / 90** |

**W-2's 22/22 includes `popfmemr` and `popfmul`** — the two SATURATED controls
whose first boundary sits 13 and 25 clocks past the rise and which are what
refuted §84.7's pure gate.  The RTL reproduces the chip's *one more boundary*
there, which is the arm being an arm.

### §86.D THE FUZZ BANK — **the prediction was the ELEVEN and the outcome is a PROPER SUPERSET, with ZERO lost over all 3,242**

| gate | before | registered bar | **after** |
|---|---|---|---|
| `timed_fuzz --core ucore --evt-replay` REGISTERED | 1,490 / 1,702 | ≥ 1,500 | **1,502 / 1,702** |
| … EVT | 918 / 1,008 | ≥ 919 | **920 / 1,008** |
| … COMBINED | 2,408 / 2,710 | ≥ 2,419 | **2,422 / 2,710** |
| … seed by seed, all 3,242 | — | **no EXACT may be lost** | **0 lost, 65 gained** |
| `mc2/2361`, the software-`INT 1` control | EXACT | unmoved | **EXACT** |

**ALL ELEVEN PREDICTED SEEDS CLOSED** — `mc1/2034`, `mc1/2952` (EVT),
`mc1/3090`, `mc2/1107`, `mc2/1718`, `mc2/1738`, `mc2/2960`, `t30-raw/682`,
`t30-raw/736`, `t30-raw/750`, `t30-raw/768` — the exact set the model gained at
§84.8, named in the pre-registration off the model's own gains and off a ucore
baseline re-measured this sitting to the seed.  **THREE MORE SCORED SEEDS CLOSED
THAT WERE NOT PREDICTED** (`mc2/1567`, `mc2/3278` EVT, `t30-raw/542`) and 51
`OPEN_BUS` seeds moved to EXACT; the gained set is a PROPER SUPERSET of the
prediction and it is reported as measured, per A-4.  `BOUND WARNINGS` **5 → 4**,
`ENGINE ABORTS` **0**, `INVALIDATED` **0**.

**THE FAMILY CENSUS MOVED, AND ONE FAMILY ALMOST VANISHED**
(`s15_census --core ucore --pop reg`, matched to the report's core):

| family | §58.4 / baseline | **after** |
|---|---|---|
| `PF_LOST` | 107 | 111 |
| `DATA_SEQ` | 41 | 33 |
| `TAIL_EXTRA` | 28 | 29 |
| `SCHEDULE` | 5 | 13 |
| `PF_ADDR` | 9 | 8 |
| `PIN` | 4 | 4 |
| **`PF_GAINED`** | **25** | **2** |
| total | 219 | **200** |

catch-all **EMPTY** in both.  `PF_GAINED` 25 → 2 is the landing's own signature:
the ucore was running prefetches the chip did not, because the chip had trapped
and flushed and the ucore had not.

### §86.E THE LADDER — **NOT ONE CELL MOVED DOWN**

| gate | registered | this sitting |
|---|---|---|
| `check_core --opcodes all --cases 0` | 169,000 | **169,000 / 169,000** |
| `v0.1-w1` / `-w3` | 1,200 each | **1,200 / 1,200** each |
| `v0.1-w1 --opcodes EB` | 200 | **200 / 200** |
| the four `evt` cells | 200 / 1,200 / 200 / 1,200 | **200 / 1,200 / 200 / 1,200** |
| `v0.1-w1evt-biased` | 1,200 | **1,200 / 1,200** |
| `f4a_boundary` · `f0lock_tranche` | 160 · 400 | **160 / 160** · **400 / 400** |
| the 23 `v0.3` block-I/O forms | 229,999 | **229,999 / 229,999** |
| `check_boot --timed 220` / `--timed 400` | MATCH | **MATCH over 220 rows** / **MATCH** |
| `ulockstep --golden all --cases 50` | 17,350 | **17,350 / 17,350** |
| `timed_wvec_gate --core ucore` | 88 / 88, +0.0 % | **88 / 88, +0.0 %** |
| `timed_enter_replay --core ucore` | 154 ×5 | **154 / 154** on every leg |
| `timed_ins_replay --core ucore --raw` | 1,312 / 2,624 | **1,312 / 1,312** and **2,624 / 2,624** |
| `--seeddir b2-tranche` | 172 / 188 | **172 / 188** |
| the four HLT sweeps | 279 / 283 | **97 + 93 + 45 + 44 = 279 / 283** |
| S16 `--core ucore` | 1,320 / 1,371 | **1,320 / 1,371** (the 4 family-D cells, unchanged) |
| `check_ab_sim` | 187 rows MATCH | **MATCH over 187 rows** |
| `check_core --ce-div 4 --ce-hold-check` | `CE_HOLD_VIOL 0` | **0 on every form** |
| `--ss-sweep` modes 1 / 2 / 5 | 80 / 24 / PASS | **80 / 80 · 24 / 24 · 4 / 4 PASS** |
| G0 `check_ucore_tables` | 9,988 | **9,988, PASS** |
| `pla3_check` · `simbin --disasm` | 21 · 1,285 | **21** · **1,285 PASS** |
| `gen_ucore_qsf --check` · `test_artifact` | PASS · 45/45 | **PASS** · **PASS** |
| the MODEL, unmoved | 1,282 / 789 / 2,071 | **1,282 / 789 / 2,071** (`sim/` was not touched) |

**`ulockstep` IS VACUOUS FOR THIS TRAP and was registered as such before it was
run**: a single-instruction case has no successor boundary to trap at and the
case runner leaves the arm off in both engines.  It is a non-regression check.
The cross-engine proof is §86.C's 30 captures scored against both engines and
§86.D's seed-level agreement.

**SAVE STATE.**  `ss_lint` rc = 0.  `SS_VERSION` **0x85 → 0x86**, `SS_COUNT`
**217 → 218**, `SS_EU_COUNT` **116 → 117**, `SS_TAG` **0x85D9 → 0x86DA**, census
**204 architectural flops, 0 UNMAPPED** (was 200).  ONE address is appended —
`SSA_E_BRK` at `0x174`, seven bits carrying `brk_p[3:0]`, `brk_arm`, `brk_smp`
and `irq_sel_brk` — which is the append-only rule as written.  A first form
borrowed the three spare bits of `SSA_E_PIN_PIPE` and three more in
`SSA_E_IRQ_LATCH` to avoid adding an address; it was **abandoned before it was
scored**, because packing five flops of one mechanism into two unrelated words
to save a map code is exactly the cleverness the package's own note says to
refuse.

**G6 (SYNTHESIS) IS GREEN, AND IT WAS RUN TWICE.**  One clean CONTROL/DEFAULT
build on the DIRTY working tree and a second on the COMMITTED one
(`e38405ab68`, clean), compile rc 0 in 573 s and 531 s: **E1 PASS · E2 PASS**
(0 errors, map/fit/asm all Successful) **· E3 47.01 MHz** (bar ≥ 32) **· E4
+8.97 ns · E5 TNS 0.000 on every domain, setup AND hold** — **the same figures
to the digit on both**, which is a repeatability control §74.4 says this design
does not always give.  RECORDED, not barred: **ALMs 11,286 / 41,910 (27 %)** —
**+160** on sitting 17's 11,126, which is what an arm, a four-deep pipeline and
a third vector door cost — **0 latches, 0 `lpm_divide`**.  The gating receipt is
the CLEAN-TREE one: **`0d9539f945271a99…`**, input manifest 88 files
`6d436d6df0b26ff4…`, git `e38405ab68` (the dirty-tree run was
`c26b887ecf34dec5…` / `9f7125caf51ddc91…`).
**A bitstream was produced and NOT flashed.**  The board still carries FLASH #9
and `use_core` was never set: **NO BOARD CONTACT THIS SITTING.**

### §86.F PART B — **`TAIL_EXTRA` IS THE ILLEGAL-FORM HALT, AND THE LEDGER ALREADY WROTE IT DOWN FROM THE OTHER END**

29 shared REGISTERED seeds (`s15_census`'s definition: the cycle sequences agree
over the whole common prefix, the times agree, and one side launched MORE bus
cycles).  Surveyed with `fuzz_classify`'s own column policy.

**THE INVARIANT IS UNANIMOUS AND IT IS THREE SENTENCES.**

| | 29 seeds |
|---|---|
| the CHIP's last bus cycle is a **`CODE` fetch** | **29 / 29** |
| the ENGINE's first extra cycle is a **`MEMR`** | **29 / 29** |
| either side ever drove the **HALT status** | **0 / 29** |
| the chip's idle tail (`bs = PASV`, **`qs = 0`**, pads frozen) | **957 – 3,906 rows**, to the end of every capture |

So the chip's **EU stops entirely** — it stops popping the queue, the queue
fills, the prefetcher stops, and the part makes no bus cycle for the rest of the
window — **without driving `HALT`**.  And what it stops on is one family:

| the form the engine executes across the chip's stop | n |
|---|---|
| `62` `CHKIND`/BOUND, `mod == 3` | 8 |
| `C4` `LES`, `mod == 3` | 6 |
| `FF` group `/3` (CALL FAR) and `/5` (JMP FAR), `mod == 3` | 5 |
| `C5` `LDS`, `mod == 3` | 4 |
| `FE` group `/3` and `/5`, `mod == 3` | 4 |
| not resolved by this extractor (it names `9D` / `78`, which carry no ModR/M) | 2 |

**`mod == 3` on 27 of 27 resolvable seeds, with no exception**, and every one of
the five opcodes is a form whose microcode must read a **multi-word operand from
memory** — a four-byte bound pair, a four-byte far pointer — which a register
operand cannot supply.

**AND THE LEDGER ALREADY WROTE THIS DOWN**, from the other end and from the
socket, on 2026-07-27.  `tests/v30/mod3_illegal/metadata.json`, verbatim:

> "BOUND(62)/LES(C4)/LDS(C5) mod3 **HALT on BOTH chip and core** (V20
> illegal-form halt, ~row 190) - core-correct, NOT fixed."

**What the survey ADDS is `FE` and `FF` at `/3` and `/5`** — the FAR CALL/JMP
group forms, memory-only for exactly the same reason — which are 9 of the 29 and
which that metadata does not name.  What it also adds is that the two TIMED
engines do NOT reproduce the halt (the archived FSM core did), which is the
whole of `TAIL_EXTRA`.

**CANDIDATES, RANKED BY POPULATION EXPLAINED**

1. **The illegal-form halt: a memory-mandatory microcode sequence given a
   register operand has no exit, and the part parks with the queue full.**
   Covers the invariant on 27 / 27 resolvable seeds, is already MEASURED on
   silicon by task #30, and explains all four columns of the table above
   including the absence of a `HALT` status (the part is not in HALT; it is
   stuck).
2. *A `POLL`/`WAIT` stall.*  **Refuted**: `0x9B` is not the executing form on
   any of the 29, and the stop is unanimous on a set of five opcodes that share
   a decode property.
3. *A capture-window or rig artefact.*  **Refuted by the chip's own rows**: the
   pads freeze mid-window with `qs = 0` for up to 3,906 further rows and the
   functional event stream is TRUNCATED (`compare_functional`), so the part
   really stopped executing.

**DISPOSITION — SURVEYED, NOT LANDED, and the reason is scope, not evidence.**
One mechanism covers the population, which is the bar the pre-registration set
for a landing.  It is not taken here because the landing is a change to the
**SPEC ENGINE's TERMINATION behaviour** — both engines must learn to park
forever on decode of a named form set — and that needs its own pre-registration
with its own bars (which suites and goldens contain these forms; what "park"
means for the model's row emission; whether the archived FSM core's halt row is
the same instant), plus a full ladder on both engines.  Landing it at the end of
a sitting that already carries an RTL landing would be exactly the rushed change
this campaign's method exists to prevent.  **REGISTERED PREDICTION for whoever
takes it: 29 REGISTERED seeds close, in BOTH engines, and `TAIL_EXTRA` goes to
0.**  Nothing in `sim/` or `hdl/rtl/` was changed for it.

### §86.G PART C — **`mc1/721` IS DECIDED, AND IT IS A THIRD OUTCOME: BOTH WRITES LAND, IN THE WRONG ORDER**

§49.8 asked which of `9E` SAHF and `F5` CMC fails to land, "because both produce
CY=1", and named the measurement: *"`SSA_E_PSW` is already in the map, so
`+ss_at=<clk>` reads PSW out at the boundary between them on the frozen binary,
no RTL change, against `PSW=` in `v30sim image --trace`."*  **It was run as
written** (`ss_mode=6`, a new READ-ONLY save-state mode that prints the addressed
stream and restores it), and the PSW walk over clocks 294-315 shows **exactly
one change in the window: CY 0 → 1**.  That does not separate the two, so the
two writes were instrumented directly:

```
1BL clk=303  pre=f202 post=f203                 <- F5 CMC, flipping CY 0 -> 1
PE  clk=304  pre=f203 post=f203  upc=9e2        <- 9E SAHF's post-E row 007E,
                                                   `tmpa -> FLAGS`, ONE CLOCK LATER
```

**NEITHER WRITE IS LOST.  THEY COMMIT IN THE WRONG ORDER.**  `9E`'s flag write
is not on its `E` row at all — the ROM is

```
007C AL:AH  -> tmpaL          007D FLAGS -> tmpaH   E          007E tmpa -> FLAGS
```

so the write lives on the **POST-`E` row**, and the model runs the post-`E` row
BEFORE the successor's step — `v30u_eu_poste.svh`'s own header says so in as
many words.  Here the successor's `ONE_BYTE_LOGIC` strobe gets there first, and
the post-`E` then writes the same value back on top of it.  Model **CY = 0**
(`f202`), ucore **CY = 1** (`f203`) — §49.8's *"CY=1 where the model has CY=0"*,
exactly, and the `sigma` that differs by 1 two instructions later follows.

**THE MECHANISM, NAMED.**  Block (b) discharges `poste` at the TOP of an edge.
On the **E-row PRE-POP path** (`row_epop`) `poste_n` is raised INSIDE the chain,
and the successor's zero-cost loader steps — `S_TAIL → S_INSTR_END →
S_TAKE_OPC → S_DECODE → S_DECODE2` and its 1BL write — ride the SAME edge, after
block (b) has already run.  The post-`E` therefore slips to the next clock.
**The golden suite cannot see it**: with no pre-pop the successor's steps ride
the NEXT clock and block (b) gets there first, which is why `9E` is
169,000 / 169,000 arch-exact.

*Falsifier*: any `<ROM form whose post-`E` row writes a register>` followed by a
`<1BL form that writes the same register>` with a PRE-POPPED successor, where
the ucore's final value is the successor's write rather than the post-`E`'s.

**THE FIX IS SPECIFIED AND NOT TAKEN.**  Discharge `poste` inline at the point
it is raised when the chain continues in the same edge.  Predicted effect:
`mc1/721` closes (`ndiff` 2).  It is not taken this sitting because it moves the
**chain's discharge order**, which is the most load-bearing ordering in the
module (F11 / F11b / F22 / F23 all live on it), and it needs its own
pre-registration and its own ladder rather than a same-sitting patch.

### §86.H PART C — **`mc2/584` IS NOT DIAGNOSED, AND THAT IS THE BOOKED STATE**

`wrand wmax=15`.  The first divergence is a **MISSED `F` POP at row 1135**,
inside an eight-clock wait run of a `CODE` fetch: the chip pops a first byte
there and **so does the model**; the `ucore` does not.  Seven rows later the
`ucore`'s next fetch redirects to `0x00535` where the chip continues
sequentially to `0x00538`, and the run parts for 404 rows.  It is a
queue-availability difference under a long wait run — the `qs` / `PF_LOST`
family — and it is **NOT the trap and NOT §86.G's post-`E` order**.  No
mechanism is named and none is guessed.

**SO THE `ucore`'s OWN REGISTERED RESIDUE IS STILL TWO, NOT ZERO.**  `mc1/721`
is now diagnosed to the clock with a named mechanism and a specified fix;
`mc2/584` is not.  The sitting's own bar was "closing them takes the ledger to
ZERO", and it did not.

### §86.I THE RATCHETS THAT MOVED

| gate | before | after |
|---|---|---|
| `timed_fuzz --core ucore` REGISTERED | 1,490 / 1,702 | **1,502 / 1,702** |
| … EVT | 918 / 1,008 | **920 / 1,008** |
| … COMBINED | 2,408 / 2,710 | **2,422 / 2,710** |
| `ss_lint` `SS_VERSION` / `SS_COUNT` / flops | 0x85 / 217 / 200 | **0x86 / 218 / 204** |
| G6 Fmax · ALMs | 45.49 MHz · 11,126 | **47.01 MHz · 11,286 (27 %)** |
| **NEW** `sm3_tf_floor_cell score --core ucore` W-6 | — | **121,860 rows, 0 row-diffs, depth 4, all 30 captures** |
| **NEW** … the same at depths 1, 2, 3, 5, 6, 7 | — | 71,304 / 71,304 / 33,941 / 14,630 / 43,762 / 61,033 |

Everything else in §86.E is UNMOVED.  **The MODEL's columns are untouched**
(1,282 / 789 / 2,071): `sim/` was not edited this sitting.

### §86.J WHAT THIS SITTING DID NOT DO

* **NO BOARD CONTACT, NO FLASHING, `use_core` NEVER SET.**  The board still
  carries FLASH #9; a G6 bitstream was produced and not flashed.
* **`TAIL_EXTRA` is SURVEYED and NOT landed** (§86.F gives the mechanism and the
  reason).  `mc1/721`'s fix is SPECIFIED and NOT landed (§86.G).
* H3-B, the `8F` mod-3 ghost cell (§84.6), model-architecture work and the
  8080/BRKEM gap were not opened.  No memory file was touched.  Codex was not
  launched.

---

## §87 SESSION SM3, SITTING 26 — **`TAIL_EXTRA` IS LANDED IN BOTH ENGINES AND IT IS ONE PREDICATE ON ONE REGISTER. THE FAMILY GOES TO ZERO, 34 OF 34 AND 33 OF 33, PLUS 32 SEEDS EACH FROM `PF_LOST` THAT NOBODY PREDICTED. AND `mc1/721` IS *NOT* LANDED, BY ITS OWN PRE-REGISTERED RULE: §86.G's FIX NEEDS A SECOND MICRO-ROM READ.**

Pre-registration: `docs/notes/sm3_s26_prereg_2026-08-05.md`, committed
`dbc30beecf` **before any edit to `sim/` or `hdl/rtl/`**.  Parent `caf95583e0`.
No board contact, no flashing, `use_core` never set.  No memory file touched.
Codex not launched.  H3-B, the `8F` ghost cell, model-architecture work and the
8080/BRKEM gap were not opened.

### §87.A PART A — **THE MECHANISM: `F` IS THE OPR INTERLOCK, AND AT `mod == 3` IT HAS NOTHING TO WAIT FOR**

§86.F surveyed the family and named the FORM SET.  This sitting names the
**predicate that generates the set**, which is a much smaller object and is the
whole landing:

> `OPR` is the EU's read-data register and the `F` bit is the interlock that
> waits for the access that fills it (`biu_timed.h`: *"THE F INTERLOCK IS THE
> **OPR** INTERLOCK"*).  A micro-row that **SOURCES** `OPR` under an `F` is
> therefore waiting for a read.  The decoder issues its operand pre-read only
> for `has_rm && mod != 3 && !MODRM_STORE`, so at `mod == 3` nothing has filled
> `OPR` — and if the microcode has posted no read of its own yet, **that row is
> waiting for an access that will never exist.  The EU parks on it.**

It is not a HALT: no `HLT` row runs, no `HALT` status is driven, the prefetcher
is not frozen.  The BIU goes on fetching until the queue is full and then sits
`PASV` with `qs = 0` — **which is §86.F's measured invariant, all four columns,
without naming an opcode.**

**THE PREDICATE IS EXACT, AND IT WAS SWEPT BEFORE THE PRE-REGISTRATION WAS
WRITTEN.**  Native page AND `0F` page, every opcode × every ModR/M `reg`,
`mod == 3` and memory — **8,192 forms**, traced through the model's own
micro-row execution:

| | fires on |
|---|---|
| `mod == 3` | **`62` CHKIND (all `reg`), `C4` LES (all), `C5` LDS (all), `FE` `reg`∈{3,5}, `FF` `reg`∈{3,5}** |
| memory (`mod == 0`, `rm == 6`), native **and** `0F` | **NOTHING** |
| `mod == 3`, `0F` page | **NOTHING** |

§86.F's family, cell for cell, **including the `FE`/`FF` `/3`,`/5` the survey
ADDED and the 2026-07-27 `mod3_illegal` metadata does not name** — and they fall
out of the predicate rather than being put in by hand, because `FE` and `FF`
share micro-page 3 (the group dispatch puts the ModR/M byte in the opcode slot),
so the byte form runs the word form's ROM.

**THE TWO CONTROLS ARE THE PROOF THAT THIS IS NOT A TABLE.**  `FF /7` at
`mod == 3` — an equally undefined group form, and one that carries **2,477
`v20suite` goldens** — does **not** fire, because its row `0FE0.2` is
`M -> OPR`, a WRITE.  `8D` LEA does not fire either.  **That is exactly why the
archived FSM core's `S_HALT` wedge was CORRECT on `62`/`C4`/`C5` and a BUG on
LEA** (`tests/v30/mod3_illegal/metadata.json`, SOCKET, 2026-07-27) — the old
core keyed on `mod == 3`, which is half the predicate.

**CONFIRMED AT THE SEEDS' OWN STOP CLOCK.**  `V30SIM_ROWTRACE` against the
chip's LAST bus-cycle `T1`.  `t30-raw/72`, chip's last `T1` at row 680, a `CODE`
fetch of `0x00538`:

```
RT 680 01C8 OPR    -> tmpb    SIGMA  -> tmpa    F    ALU INC2   tmpa
RT 681 01C9 SIGMA  -> IND                            CTL SUSP   MEMR
```

Row 680 IS `FF /5` JMP FAR's OPR-source `F` row, on the chip's stop clock to the
clock; row 681 is the `MEMR` the census calls the first extra cycle.

### §87.A.1 THE LANDING — **ONE SITE PER ENGINE, AND THE ARCH ENGINE INHERITS IT**

**`sim/`**: `Machine::stalled` (`state.h`) plus `CpuT::opr_loaded_`
(`exec_impl.h`) — set by the loader's `ld.preread`, by `deliver_read`'s
delivery, by a `-> OPR` transfer and by the memory-operand staging; cleared by
`begin_sequence()`.  The predicate sits in the `F` block of `run_micro`, which
is the SHARED interpreter, so `v30sim run` / `image` / `timed-boot` all inherit
it from ONE site.  `timed_runner` renders the park with the ORDINARY tick (the
prefetcher is not frozen — that is the difference from the HALT path);
`image_runner` reports `"stall":1` and ends the transaction log where the chip's
ends; `case_runner` says `illegal-form stall` instead of `micro-sequence did not
terminate`, which is a truthfulness fix and not a scoring one.

**`hdl/rtl/ucore/`**: `opr_loaded`, ONE flop, with the same set/clear sites, and
ONE new wire beside `f_wait`:

```systemverilog
wire opr_starved = row_reads_opr && !opr_loaded && !nr_have &&
                   (rd_pending == 2'd0) && (rdq_n == 2'd0);
wire f_wait = row_reads_opr ? (nr_wait || opr_starved || !opr_free_now)
                            : !opr_free_now;
```

`nr_wait` waits for the next OUTSTANDING read; when nothing is outstanding it is
0 and the row runs.  `opr_starved` is the missing half: **a wait needs something
to wait for.**  No state machine, no new state, no HALT path — the row simply
never releases.

**SAVE-STATE MAP, DECLARED (not discovered).**  `SSA_E_OPR_LOADED` at `0x175`,
one bit, appended at the end of the EU's dense region under the append-only
rule.  `SS_VERSION` **0x86 → 0x87**, `SS_EU_COUNT` 117 → **118**, `SS_COUNT`
218 → **219**, `SS_TAG` **0x87DB**; `ss_lint` PASS, census **205 architectural
flops (was 204), 0 UNMAPPED**.  A freeze taken inside a parked machine that did
not carry this bit would restore a part that resumes an instruction silicon
never finishes.

### §87.A.2 THE OUTCOME — **THE REGISTERED PREDICTION IS MET IN FULL AND THE NUMBERS ARE ABOVE IT**

| | `sim` before | after | `ucore` before | after |
|---|---|---|---|---|
| REGISTERED | 1,282 / 1,702 | **1,338** | 1,502 / 1,702 | **1,557** |
| EVT | 789 / 1,008 | **798** | 920 / 1,008 | **931** |
| COMBINED | 2,071 / 2,710 | **2,136** | 2,422 / 2,710 | **2,488** |
| `s15_census` `TAIL_EXTRA` | 33 (30 REG + 3 EVT) | **0** | 34 (29 REG + 5 EVT) | **0** |
| `--seeddir b2-tranche` | 154 / 188 | **159** | 171 / 188 | **177** |

**A-1 / A-2 / A-3 MET, seed by seed: ALL 33 of the model's and ALL 34 of the
ucore's `TAIL_EXTRA` seeds closed, including the 29 shared REGISTERED seeds
§86.F named and the three §87.A named IN ADVANCE as the likely misses
(`t30-brkem/185`, `t30-raw/496`, `t30-raw/638`).  ZERO SEEDS LOST over all
3,242, checked seed by seed, in BOTH engines.**

**A-4 IS EXCEEDED, AND THE REASON IS ONE MECHANISM, NOT TWO.**  The registered
figures (1,312 / 792 / 2,104 and 1,531 / 925 / 2,456) assumed only
`TAIL_EXTRA` would move.  **32 further seeds closed in EACH engine — 26 REG +
6 EVT, and every one of them was `PF_LOST`.**  Same defect, different
first-divergence classification: the engine ran on past the chip's stop, and on
those seeds the first row that parted was a prefetch the chip never made rather
than a bus cycle count.  `PF_LOST` 315 → 283 (`sim`) and 134 → 102 (`ucore`).
**The over-shoot is reported as measured; the registered bar was the floor and
it is not restated.**

**A-7 MET**: `BOUND WARNINGS` **4 → 4** (`ucore`), `ENGINE ABORTS` **0**.  The
park is not an abort — three `STEP-ABORT` lines the model used to print are
gone, replaced by nothing, because a stall now terminates the run cleanly and
still emits rows to the clock budget.  No new stderr class appeared in either
engine.

**A-6, the arch engine.**  `s15_census`'s "functional stream TRUNCATED" column
is where the arch leg's inheritance shows; the architectural ladder is UNMOVED
(below), which is the bar that matters.

### §87.A.3 THE MUST-NOT-MOVE LADDER — **NOT ONE CELL MOVED DOWN**

| gate | measured |
|---|---|
| `simbin --disasm` | **1,285 rows** byte-exact |
| `pla3_check` · `check_ucore_tables` | **21** · **9,988** |
| `ucsim_check` `v0.1`/`v0.2`/`v0.3`/`v20suite`/`mod3_illegal` | **169,000 · 347,000 · 3,699,998 · 3,125,000 · 128 = 7,341,126** |
| `check_core --core ucore --opcodes all` | **169,000 / 169,000** |
| `f4a_boundary` · `f0lock_tranche` | **160 / 160** · **400 / 400** |
| `check_boot --core ucore --timed 220` / `400` | **MATCH** / **MATCH** |
| `ulockstep --golden all --cases 50` | **17,350 / 17,350** |
| `v0.1-w1` / `-w3` · `EB` · the four `evt` cells · `w1evt-biased` | **1,200 / 1,200 · 200 · 200/1,200/200/1,200 · 1,200** |
| the 23 `v0.3` block-I/O forms | **229,999 / 229,999** cycles AND arch |
| `timed_gate --suite v0.1 --forms all` (model) | **169,000 / 169,000, row-diffs 0** |
| the four HLT sweeps, model | 97/97 · 95/95 · 46/46 · 45/45 = **283 / 283** |
| the four HLT sweeps, `ucore` | 97/97 · 93/95 · 45/46 · 44/45 = **279 / 283** |
| `timed_wvec_gate --core ucore` | **88 / 88, +0.0 %** |
| `timed_enter_replay --core ucore` | **154 / 154** ×3 legs |
| `timed_ins_replay --core ucore --raw` | resolved **800/800**, rails **1,312 / 1,312**, vs-chip **2,624 / 2,624** |
| `check_ab_sim --core ucore` | **MATCH over 187 rows** |
| `timed_scenario` · `timed_lawcards` | **18 / 0 / 9** · **8 GREEN / 0 RED / 3 UNRESOLVED** |
| `sm3_s16_score --core ucore` | **1,320 / 1,371**, census `D_tstate` 24 + `ARCH` 27 |
| … `--core sim` | census `qop` 39 + `ARCH` 30 — **identical to the booked residue** |
| `ss_lint` (default leg) | **PASS**, and see the DECLARED map bump above |
| `test_artifact` · `gen_ucore_qsf --check` | **45 / 45** · up to date |

**The `ucore`'s OWN registered residue is 14, and it was 9.**  Nothing
regressed — the ucore lost no seed — but the MODEL closed five seeds the ucore
does not (`mc1/1023`, `mc2/640`, `mc2/887`, `mc2/2808`, `t30-raw/15`), so the
model-exclusive column grew by five.  Booked here rather than left to be
rediscovered.  In the other direction the ucore is still exact on **366** seeds
the model is not.

> ⚠ **ERRATUM (verdict finalization, 2026-08-05) — `timed_enter_replay`'s LEG
> COUNT IN THE LADDER TABLE ABOVE.**  The row reads **`154 / 154` ×3 legs**.  It
> is **×5**.  **THE TABLE IS LEFT AS COMMITTED** — this ledger is append-only and
> rewriting a recorded claim in place would hide that it was made.
> `standing_gates.md` §B has registered **154 / 154 ×5** throughout, and
> `sw/timed_enter_replay.py` prints **five** counters — `pushes`, `walk`, `full`,
> `active`, `halt_display` — each **154 / 154**, on TB receipt
> `cede73e73a318753…`.  Verified against the ARTIFACT: the five are five distinct
> accumulators in the scorer's own source.  **NO NUMBER MOVES; the LEG COUNT
> does.**  §88.B.1 carries the same mis-statement and the same erratum; the
> sitting-27 census's §1.3 is corrected in place with its own erratum note.
> Found by `sm3_verdict_2026-08-05.md`'s cross-check (appendix item 1).

### §87.B PART B — **`mc1/721` IS NOT LANDED, AND THE REASON IS THE ONE B-5 REGISTERED IN ADVANCE**

**B-4, MEASURED FIRST.**  The MODEL is `EXACT` on `mc1/721` **and** on
`mc2/584`, before and after A.  `sim/` does not share the defect; no `sim/`
edit was made for B.

**§86.G's fix, as specified, is: "discharge `poste` inline at the point it is
raised when the chain continues in the same edge."  IT CANNOT BE DONE ON ONE
MICRO-ROM READ, and that is a finding.**

The post-`E` row's body (`v30u_eu_poste.svh`) reads the `e_*` wires, and those
stand on `row` — `v30u_ucrom`'s **combinational read off the REGISTERED `upc`**.
At the raise site `upc_loc_n` has already advanced to the post-`E` row, but the
ROM word for it does not exist until the next edge, because the module presents
**one row per clock, which is what the die does** (`v30u_ucrom.sv`: *"the two
lookups stand on its output exactly as the die's PLA + ROM stand on the
micro-address register"*).  And it is not a low-bit re-select of the same
4-row bank either: the post-`E` row **crosses a bank boundary** in the general
case — `FF /5`'s `0FAC.3` (`E`) is followed by `0FAD.0` — so it needs a second
FULL lookup, `ucdecode` 8192×10 **and** `ucrom` 1028×29.  **B-5 named "a second
micro-ROM read port" as a disqualifier before the run, and it is one: an 80s
die does not read its microcode ROM twice in a clock.**

**WHAT IS ESTABLISHED BEYOND §86.G.**  The two writes are on DIFFERENT EDGES in
the `ucore` (the successor's `ONE_BYTE_LOGIC` strobe on the edge ending clock
303, the post-`E` on the edge ending 304) and on the SAME edge in the model, in
the order post-`E` → successor.  **Each of the `ucore`'s two placements is
INDEPENDENTLY MEASURED AGAINST SILICON** — §35.3's 1BL execute strobe on
`FA idx 4` (*"the golden's status nibble is already 2 on clock 1"*), and the
post-`E` row's own one-clock cost.  `mc1/721` shows the two cannot both be
honoured in the current structure.  **That is a collision between two measured
laws, not a scheduling slip**, and moving either one on the strength of a single
seed is exactly the fitted-fix this campaign's method exists to prevent.

**WHAT IT NEEDS NEXT** (specified, not taken): §86.G's own falsifier run as a
DIRECTED CELL — `<a ROM form whose post-`E` row writes register R>` followed by
`<a 1BL form that writes R>` with a PRE-POPPED successor, swept over the wait
axis, against silicon.  That population decides which of the two placements is
the one that moves.  One seed cannot.

**B-2 is MET and it was measured, not assumed**: `check_core --core ucore
--opcodes all` is 169,000 / 169,000 and `timed_gate v0.1` is 169,000 / 169,000
— which is what "the golden suite cannot see it" predicts, and it is now a
measurement rather than a construction argument.

**B-6.**  `mc2/584` is UNCHANGED by A (`ndiff` 404 before and after) and stays
booked and undiagnosed (§86.H).  `mc1/721` is likewise unchanged (`ndiff` 2).
**The `ucore`'s two named own-residue seeds are still two.**

### §87.C THE RATCHETS THAT MOVED

| gate | before | after |
|---|---|---|
| `timed_fuzz --core sim` REGISTERED | 1,282 / 1,702 | **1,338 / 1,702** |
| … EVT | 789 / 1,008 | **798 / 1,008** |
| … COMBINED | 2,071 / 2,710 | **2,136 / 2,710** |
| `timed_fuzz --core ucore` REGISTERED | 1,502 / 1,702 | **1,557 / 1,702** |
| … EVT | 920 / 1,008 | **931 / 1,008** |
| … COMBINED | 2,422 / 2,710 | **2,488 / 2,710** |
| `timed_fuzz --seeddir b2-tranche`, model | 154 / 188 | **159 / 188** |
| … `--core ucore` | 171 / 188 | **177 / 188** |
| `s15_census` `TAIL_EXTRA`, both engines | 33 / 34 | **0 / 0** |
| `s15_census` `PF_LOST`, model / `ucore` | 315 / 134 | **283 / 102** |
| `ss_lint` `SS_VERSION` / `SS_COUNT` / flops | 0x86 / 218 / 204 | **0x87 / 219 / 205** |
| G6 Fmax · ALMs | 47.01 MHz · 11,286 | **47.85 MHz · 11,147 (27 %)** |

**G6 IS GREEN ON THE RTL LANDING** (A-8's requirement, and it was run, not
assumed): E1 `gen_ucore_qsf --check` PASS, **E2 0 errors, every stage
Successful**, **E3 `divclk` Fmax 47.85 MHz** against a registered ≥ 32,
**E4 worst setup +8.602 ns**, **E5 TNS 0.000 setup AND hold on every domain**,
0 latches, 0 `lpm_divide`, 88 input files `2d259c06167d1fa3…`, receipt
`78683e26618b9e61…`.  One flop and one wire cost **nothing**: the ALM count
went DOWN (11,286 → 11,147) and Fmax UP.  **No bitstream was flashed.**

Everything else in §87.A.3 is UNMOVED.  **This is the first sitting since U5 in
which the MODEL's columns moved**, and they moved for the same one-line reason
the `ucore`'s did.

### §87.C.1 THE ERA GUARDS FIRED, AND THAT IS THE POINT OF THEM

The landing moves the `ucore`'s binary, so §83.0's era guard REFUSED both
software instruments by name and hash — `x1_retention score` ("ERA MISMATCH --
REFUSING TO SCORE") and `sm3_s16_fabric score --leg vsys_ret`.  Both columns
were RE-CAPTURED on this tree, with the expectation registered first (the HLT
sweeps do not move, so neither should these):

| | before (F57 era) | re-captured on this tree |
|---|---|---|
| `x1_retention` `offline` / `base` / `ret` | 279 / 34 / 279 | **279 / 34 / 279**, BAR (i) and BAR (ii) **MET**, 0 survivors, 0 cells differing from offline |
| `sm3_s16_fabric` `offline` / `vsys_ret` | 1,347 / 1,347 | **1,347 / 1,347 / 1,371**, over **1,371 common cells: 0 PASS/FAIL disagreements, 0 differing first-divergence coordinates** |

`fab_f9` is UNTOUCHED and remains a FLASH #9 figure — its DUT is a bitstream
and its era is the flash log, not the tree.

**AND ONE INSTRUMENT DEFECT WAS FOUND BY WALKING INTO IT.**
`sm3_s16_fabric.py score --leg offline` writes `score_offline.json` from the
per-cell `*.offline.json.gz` files — **which do not exist**, because
`cmd_offline` is what produces that file directly.  Running it therefore
silently OVERWRITES the reference with `{"exact": 0, "total": 0, "cells": {}}`,
after which `score --leg vsys_ret --ref offline` reports **"over 0 common
cells: 0 disagreements"** — a cross-check that passes because it compares
nothing.  It happened here and was caught by the number 0 appearing where 1,371
belongs.  Recovered by re-running `offline`; the cross-check above is the
non-vacuous one.  **`offline` is a REFERENCE leg, not a scoreable `--leg`**, and
the pattern is this document's own: a comparison between two instruments is
worth nothing until you have looked at its DENOMINATOR.

> ⚠ **ERRATUM / NUMBERING (verdict finalization, 2026-08-05) — THIS IS THE
> **NINTH** INCARNATION OF THE VACUOUS-GATE PATTERN, AND IT WAS RECORDED WITHOUT
> A NUMBER.**  §83.0a numbers the era guard the **EIGHTH**; the defect above is
> the same pattern one turn later — *"the gate ran against bytes nobody proved
> were the bytes it named"*, here degenerating to *the gate ran against no bytes
> at all* — and it was written with the framing and the lesson but no place in
> the chain.  **It is INCARNATION NINE.**  The chain, in full:
> §60.1 (5, the stale `Vtb_v30_core`) · §67.6 (6, `x1_retention` bound to a
> binary nothing in the tree owned) · §73.7 (7, `build()` wrote `Vtb_sys` and the
> scorer opened `tb_sys`) · §83.0a (8, a capture that recorded WHAT and never
> WHICH TREE) · **§87.C.1 (9, a `--leg` that overwrites its own reference with an
> empty one and then agrees with it perfectly)**.
> **The ninth's rule, stated as a rule**: *a comparison between two instruments
> is worth nothing until you have looked at its DENOMINATOR* — and, generally,
> **a cross-check that reports zero disagreements over zero common cells is a
> FAILED cross-check, not a passing one.**  `standing_gates.md`'s meta-finding
> section is updated from seven to nine with the same chain.  Flagged by
> `sm3_verdict_2026-08-05.md` appendix item 4.

### §87.D WHAT THIS SITTING DID NOT DO

* **NO BOARD CONTACT, NO FLASHING, `use_core` NEVER SET.**
* **`mc1/721` is DIAGNOSED FURTHER and NOT LANDED** (§87.B), by B-5's own rule.
  `mc2/584` is untouched.
* H3-B, the `8F` mod-3 ghost cell (§84.6), model-architecture work and the
  8080/BRKEM gap were not opened.  No memory file was touched.  Codex was not
  launched.

---

## §88 SESSION SM3, SITTING 27 — **FLASH #10: FIVE LANDINGS REACH FABRIC AT ONCE, AND EVERY REGISTERED PREDICTION IS MET CELL FOR CELL. THE HLT SWEEPS' FABRIC RESIDUE IS NOW EXACTLY THE FOUR FAMILY-D CELLS, S16's IS EXACTLY THOSE FOUR × SIX PROGRAMS, AND THE b3 PRIORITY TRANCHE IS 178/178 IN SILICON'S OWN INSTRUMENT.**

Pre-registration: `docs/notes/sm3_s27_prereg_2026-08-05.md`, committed
`f3f7b6b20d` **before any bitstream was loaded and before any board capture was
taken**.  Parent `6b232b9afa`.  Nothing was landed this sitting: `git diff` over
`hdl/rtl/` and `sim/` is EMPTY.  No memory file touched.  Codex not launched.

## §88.A PART A — THE FLASH MILESTONE

### §88.A.0 THE BOARD

`root@mister-nec` reachable, `up 24 days 03:27`.  **Single-writer check: no
`v30` / serve / python process on the board**, made twice — at registration and
again immediately before the flash.  JTAG chain present (`DE-SoC [1-1.2.4]`,
`SOCVHPS` + `5CSEBA6/5CSEMA6`).  `div_guard` **PINNED on every probe, both
ends**; **0 transport errors** in 2,394 captures; no wedge; `board_idle()` clean
at the close and the board still runs an image after it.

### §88.A.1 THE PROMOTION RULE, MET FIRST

`quartus_gate.py` at HEAD, ONE clean CONTROL/DEFAULT build from a deleted
`db`/`incremental_db`, compile rc 0 in **544 s**: **E1 PASS · E2 PASS** (0 stage
errors, 0 error lines, map/fit/asm all Successful) **· E3 47.85 MHz** (bar ≥ 32)
**· E4 +8.602 ns · E5 TNS 0.000**, setup AND hold, every domain.  RECORDED, not
barred: **ALMs 11,147 / 41,910 (27 %)**, 0 latches, 0 `lpm_divide`.  Receipt
**`3cdd586554780bb4…`**, tree **`6b232b9afa`** (clean), input manifest **88 files
`2d259c06167d1fa3…`** — **byte-identical to sitting 26's (§87.A.3)**, the check
that says `hdl/` has not moved since the illegal-form stall landed.  The figures
reproduce sitting 26's **to the digit** on a different receipt id, which §74.4
says this design does not guarantee.

The FLASHED bitstream is the **RETENTION** build from the same regenerated
`.qsf`: `quartus_map --verilog_macro="X1_AD_RETENTION=1"` + `fit` + `asm` +
`sta`, 0 errors, **Fmax 45.72 MHz, worst setup +7.181 ns, TNS 0.000 on every
domain, ALMs 11,165 / 41,910 (27 %)**, 0 latches, 0 `lpm_divide`; receipt
**`a2d605a47f61af37…`**, recorded as
`~/.cache/ucsimt-tmp/sm3s27/quartus_gate_retention.json`.  *Its 88-file manifest
hash is NOT the control's, because Quartus had appended pin assignments to the
revision `.qsf` by the time it was parsed — the same artefact §80.B.1 records.
The GATE is the control build; this row is RECORDED.*  The `.qsf` was restored
from the generator afterwards and `gen_ucore_qsf --check` is green.

**FLASH #10** through `sw/safe_flash.sh` with its VERIFY leg:
`nec_test_ucore.sof`
**`1a01a6975e4aca6fe9cefe83002034789dfee5c728cd72c59ea2acbc7f7a9498`**,
`.rbf` `9e3f0ceaa4f192f7fd6dac50d06c8a29b9355ce7173b8f6a6c00b00a1637f195`,
VERIFY **OK**, `flash_log.jsonl` 12 → **13 entries**.

### §88.A.2 THE OFFLINE RE-PROOF, RUN FIRST — AND THIS TIME IT REPRODUCED

§83.0/§83.0b's lesson was applied rather than re-learned: **both `tb_sys`
columns were RE-CAPTURED on this tree before the board was touched**, not
inherited.

| column | figure | reproduction |
|---|---|---|
| `x1_retention ret` (283 cells, 59 s, DUT receipt `c5bfeffe0f60f2e6…`) | **279 / 283** | **byte-identical to the banked column on all 283 cells** — the only key that moves in any of the eight files is `_meta` |
| `sm3_s16_fabric vsys_ret` (1,371 cells, 302 s) | **1,347 / 1,371** | **byte-identical on all 72 files**, 0 PASS/FAIL disagreements and 0 differing coordinates vs `offline` |
| `x1_retention` BAR (i) / BAR (ii) | **MET / MET** | 245 closed, 0 survivors, 0 cells differing from `offline` |

### §88.A.3 **THE OLD FLASH-#10 PREDICTIONS ARE SUPERSEDED, NOT MISSED**

§81.A.7 and `standing_gates.md` carried **`x1_fabric` 273/283** and
**`sm3_s16_fabric` 1,321/1,371** as the registered FLASH #10 predictions.  They
were written at **sitting 20, when F55 was the ONLY landing ahead of FLASH #9**.
**Four further landings have gone in since** — F56, F57, the ucore's BRK/TF leg
and the illegal-form stall — and the offline references moved with them
(273 → **279**, 1,321 → **1,347**; +6 and +26, which is F56's +4/+14 and F57's
+2/+12 exactly).  The superseded numbers stay in the ledger verbatim; the
sitting-27 pre-registration replaces them **from the current offline columns**
and states the supersession.  *A prediction stated against a stale reference is
§83.0's defect one sitting later.*

### §88.A.4 **WHAT FABRIC COULD AND COULD NOT EXERCISE — DERIVED BEFORE THE RUN**

Read off the populations, not argued: **all 1,654 goldens of the four HLT sweeps
and the S16 walk are the SAME ONE-BYTE PROGRAM `[0xF4]` (`HLT`), and `PSW.TF` is
CLEAR in every one of the 1,654 initial states.**  So

* **the BRK/TF single-step trap is NOT reachable there** (it arms on `PSW.TF`),
* **the illegal-form stall is NOT reachable there** (it fires only on
  `62`/`C4`/`C5`/`FE`,`FF` `/3`,`/5` at `mod == 3`, §87.A's 8,192-form sweep, and
  none of those bytes is in the image),
* so **the whole predicted fabric delta on those two populations is F55 + F56 +
  F57 and nothing else.**

The trap's silicon evidence is a **socket** population already banked
(`sw/sm3_tf_floor_cell.py`, 30 retained captures, internal trap, drives no pin,
deterministic from RESET) and **no board contact was taken for it**.  The two
landings reach fabric only through the **b3 priority tranche**, which is
random-soup images — and that is exactly where the sitting's second result is.

### §88.A.5 THE RESULTS, REPORTED AS REGISTERED

| | prediction | **measured** |
|---|---|---|
| **P0** G6 at HEAD | E1-E5 green, receipt read | **PASS**, §88.A.1 — **MET** |
| **P1** first light `check_ab_hw all 800` | MATCH ×3 | **MATCH / MATCH / MATCH over 800 rows** — **MET** |
| **P2** `x1_fabric baseline --leg fab_f10` | **279 / 283**, = `tb_sys ret` cell for cell | **279 / 283**, and against `ret` over all 283: **0 PASS/FAIL disagreements, 0 differing first-divergence coordinates** — **MET** |
| **P2a** the four failing cells, NAMED IN ADVANCE | `w1.INT/8,9` · `w2.INT/12` · `w3.INT/15` at rows 11/11/13/15, col `pins` | **exactly those four, exactly those coordinates, and no others moved** — **MET** |
| **P3** socket control `soc_f10`, `use_core=False` | 49 / 49 | **49 / 49** — **MET** |
| **P4** `sm3_s16_fabric fabric --leg fab_f10`, ROWS ONLY | **1,347 / 1,371**, 0 disagreements vs `vsys_ret` | **1,347 / 1,371**, **0 PASS/FAIL disagreements and 0 differing coordinates over all 1,371** — **MET** |
| **P4a** its 24 failing cells, NAMED IN ADVANCE | the four family-D coordinates × six programs | **exactly those 24** — **MET** |
| **P4b** S16 socket control | 41 / 41 | **41 / 41** — **MET** |
| **P5** b3 priority tranche | `chip_f10` 178/178, **`core_f10` 178/178, residue EMPTY** | **178 / 178** and **178 / 178 (100.0 %)**, residue EMPTY, 0 errors in 400 captures — **MET** |
| **P6** `use_core=0` chip proof AFTER everything | MATCH 800 | **MATCH over 800 rows** — **MET** |
| **P7** `div_guard` | PINNED both ends of every leg | **PINNED, every probe** — **MET** |
| **P8** transport | 0 errors, `board_idle` clean | **0 errors, no wedge, `board_idle()` clean** — **MET** |
| **P9** resting state | FLASH #10 retention, `use_core` False, `cfg 0xff0008` | **exactly that**, `ctrl 0x5` — **MET** |

**EVERY REGISTERED PREDICTION IS MET.  NONE IS RESTATED.**

Per suite the fabric sweeps, against FLASH #9's:

| suite | FLASH #9 | **FLASH #10** |
|---|---|---|
| `s10-w0` `HLT.INT` | 44 / 48 | **48 / 48** |
| `s10-w0` `HLT.RES` | 47 / 49 | **49 / 49** |
| `s10-w1` `HLT.INT` | 44 / 46 | **44 / 46** |
| `s10-w1` `HLT.RES` | 49 / 49 | **49 / 49** |
| `s13-w2` `HLT.INT` | 18 / 21 | **20 / 21** |
| `s13-w2` `HLT.RES` | 25 / 25 | **25 / 25** |
| `s13-w3` `HLT.INT` | 16 / 20 | **19 / 20** |
| `s13-w3` `HLT.RES` | 25 / 25 | **25 / 25** |
| **total** | **268 / 283** | **279 / 283** |

### §88.A.6 **WHAT IS NOW ESTABLISHED IN FABRIC**

**(a) F55, F56 AND F57 ARE IN SILICON'S INSTRUMENT AND THEY HOLD THERE.**  +11
sweep cells and +56 S16 cells, and the FABRIC RESIDUE ON BOTH POPULATIONS IS NOW
**EXACTLY FAMILY D AND NOTHING ELSE** — four cells on the sweeps, the same four
coordinates × six programs on S16.  Family B is gone in fabric as it is offline;
the catch-all is **EMPTY on both populations in fabric**.

**(b) §80.B.3(c)'s GENERAL RULE SURVIVES ITS THIRD TEST AND IS NOW 3,308 OF
3,308.**  *Where `tb_v30_core` and `tb_sys` disagree, fabric sides with
`tb_sys`.*  It was 1,654 of 1,654 at FLASH #9; this sitting adds another 1,654
cells across the same two populations, PASS/FAIL and coordinate alike, on a
bitstream five landings newer.  **`tb_sys` predicted fabric exactly, twice, from
a tree that had never been near the board.**

**(c) THE b3 PRIORITY TRANCHE IS 178 / 178 IN FABRIC — V3 IS ZERO SEEDS APART.**
`core_f9` was 176/178 with residue `bs = 2` (`mc1_300043`, `mc1_300122`) and had
been 176 on FLASH #4, #5 and #9 alike.  It is **178 / 178 (100.0 %) on FLASH
#10**, and the offline `vsim_ucore` column measured on this tree **before the
board was touched** said 178/178 first — so this was a REGISTERED PREDICTION,
not a discovery after the fact.  `chip_f10` is 178/178, the socket reference for
its own bitstream.

**AND `gaps` §T4 IS EMPTY.**  *"the 2 `bs` seeds of the priority tranche — ucore
≡ SIM on 4,000/4,000 rows on both — model-shared, decisively"* has no members
left in the ucore, offline or in fabric.  **The ATTRIBUTION to a particular
landing is NOT ESTABLISHED and is not guessed at**: the banked `vsim_ucore`
column reproduces 176/178 on the same scorer in the same run that scores HEAD at
178/178 (and `core_f5`/`core_f9` at 176), so the scorer is not what moved — but
five landings separate the banked column from HEAD and this sitting did not
bisect them.  Booked as measured, with the question named.

### §88.A.7 THE RESTING STATE

The board carries **FLASH #10**, the retention build,
`nec_test_ucore.sof 1a01a6975e4a…`, `use_core` **False**, `cfg 0xff0008`
(`clk_div` 8 = `DIV_OF_RECORD`), `ctrl 0x5`, `board_idle()` clean.  The
disposition is §73.8's, taken on the measurement: the retention model is on the
OBSERVATION path (`hb_ad_sample`) under `cfg_use_core ? core_ad_eff : NEC_AD`,
so the socket position is unaffected by construction, and `check_ab_hw chip 800`
run AFTER the whole sitting is **MATCH over 800 rows**.  FLASH #9's
`.sof 01aca4c0b1e7…` remains on disk.

### §88.A.8 THE RATCHETS THAT MOVED

| ratchet | before | **after** | which change |
|---|---|---|---|
| the fabric HLT sweeps | 268 / 283 (FLASH #9) | **279 / 283 (FLASH #10)** | F55 + F56 + F57 reaching fabric |
| **S16 IN FABRIC**, rows only | 1,291 / 1,371 (FLASH #9) | **1,347 / 1,371 (FLASH #10)** | same |
| the b3 priority tranche, core leg | `core_f9` 176 / 178 | **`core_f10` 178 / 178** | see §88.A.6(c); attribution open |
| the b3 priority tranche, offline | `vsim_ucore` 176 / 178 (banked) | **178 / 178 at HEAD** | same |
| the board's bitstream | FLASH #9 `01aca4c0b1e7…` | **FLASH #10 `1a01a6975e4a…`** | this sitting |
| G6 Fmax · ALMs (control) | 47.85 · 11,147 | **47.85 · 11,147 — unmoved** | `hdl/` did not move |


## §88.B PART B — **THE VERDICT-INPUT CENSUS: THE CATCH-ALL IS NINE SEEDS, AND FIVE OF THE NINE HAVE NEVER BEEN NAMED IN THIS REPOSITORY**

**`docs/notes/sm3_s27_residue_census_2026-08-05.md`** — one tree
(`f3f7b6b20d`, the tree FLASH #10 was built from), one census, both engines,
every population.  **NO fix, NO landing, NO proposal**: `git diff` over
`hdl/rtl/` and `sim/` is empty for the whole sitting.

### §88.B.1 EVERY PER-POPULATION TOTAL REPRODUCED, TO THE SEED

`timed_fuzz` `ucore` **1,557 / 931 / 2,488**, `sim` **1,338 / 798 / 2,136**,
`INVALIDATED` 0, `ENGINE ABORTS` 0, `BOUND WARNINGS` 4; b2 tranche **177 / 188**
and **159 / 188**; the four HLT sweeps **279 / 283** (`ucore`) and **283 / 283**
(model); S16 **1,320 / 1,371** and **1,305 / 1,371**; the b3 tranche in fabric
**178 / 178**.  The whole structural ladder green on this tree —
`simbin --disasm` 1,285 rows, `pla3_check` 21, `check_ucore_tables` 9,988,
`ss_lint` 205 flops / 0 UNMAPPED, `check_core --opcodes all` **169,000 /
169,000**, `check_boot` 220 and 400 MATCH, `ulockstep` **17,350 / 17,350**,
`timed_wvec_gate` 88/88 +0.0 %, `timed_enter_replay` 154/154 ×3,
`timed_ins_replay` 800/800 · 1,312/1,312 · 2,624/2,624, `check_ab_sim` 187 rows
MATCH, `test_artifact` 45/45, the model's `v0.1` timed wall **169,000 / 169,000
row-diffs 0**, and the BRK/TF floor cell **EXACT at depth 4 (`ucore`) and 3
(`sim`) and at no other depth in [1,7]**.  The 7,341,126-case functional set was
**NOT re-run** and is cited from §87.A.3 on an identical `hdl/` manifest and
`sim/` receipt — stated as a citation, not restated as a measurement.

> ⚠ **ERRATUM (verdict finalization, 2026-08-05) — `timed_enter_replay 154/154
> ×3` ABOVE IS `×5`.**  **THE PARAGRAPH IS LEFT AS COMMITTED** (append-only).
> `standing_gates.md` §B registers **154 / 154 ×5**, and the scorer prints five
> counters — `pushes`, `walk`, `full`, `active`, `halt_display` — each
> **154 / 154**, on TB receipt `cede73e73a318753…`.  **NO NUMBER MOVES; the LEG
> COUNT does.**  Same erratum at §87.A.3.  See
> `sm3_verdict_2026-08-05.md` appendix item 1.

### §88.B.2 THE FAMILY CENSUS, `--core` MATCHED TO THE REPORT

`ucore` **222** = `PF_LOST` 102 · `SCHEDULE` 44 · `DATA_SEQ` 41 · `PF_GAINED` 15
· `PF_ADDR` 11 · `PIN` 9, **`TAIL_EXTRA` 0**, taxonomy catch-all EMPTY.
`sim` **574** = `PF_LOST` 282 · `SCHEDULE` 196 · `DATA_SEQ` 30 · `PF_ADDR` 27 ·
`PIN` 26 · `PF_GAINED` 13, **`TAIL_EXTRA` 0**, catch-all EMPTY.
Cross-engine: **shared 208 · `ucore`-only 14 · model-only 366** — an INDEPENDENT
reproduction of §87.A.3's own two numbers, derived from two fresh dumps rather
than carried.

### §88.B.3 THE PARTITION BY DISPOSITION — **EVERY DISPOSITION CARRIED, NONE RE-LITIGATED**

| layer | REG | EVT | total | disposition |
|---|---|---|---|---|
| **L1** 8080 / BRKEM class A | 81 | 11 | **92** | DEFERRED BY USER DECISION 2026-08-05 |
| **L2** H3-B, the grant-order swap | 4 | 6 | **10** | DEFERRED BY USER DECISION.  *Not refuted* |
| **L3** spec'd, awaiting a directed cell | 2 | 0 | **2** | `mc1/721` (§87.B), `mc2/584` (§86.H) |
| **L4** model-shared — `sim/` FIRST | 54 | 55 | **109** | the shared-mechanism ROUTING rule, not an exemption |
| **L6** instrument-class, family D | 0 | 0 | **0** | 4 sweep + 24 S16 cells, on the `tb_sys` column by user disposition |
| ⚠ **CATCH-ALL** | **4** | **5** | **9** | **`ucore`-only, NO disposition of any kind** |
| | **145** | **77** | **222** | |
| **FROZEN** — the model-only residue | | | **366** | USER DECISION: no model-only work |

**L1 WAS COUNTED FRESH, NOT INHERITED, AND IT IS STILL EXCEPTION-FREE.**  §63.5's
mechanical criterion (chip cell `CODE 00484` **and** `CODE:00008` in the chip's
window) re-applied at HEAD gives **92 — §63.5's number exactly**, four sittings
and five landings later; the whole 50-seed `t30-brkem` bank is inside it; the
engine's cell at the contested slot is **`MEMR` 92/92**, `delta` **+2 on 92/92**,
recovery **`NONE` 92/92**.

### §88.B.4 **THE CATCH-ALL, ENUMERATED SEED BY SEED**

Definition stated before the count: a banked seed on which the `ucore` diverges
from silicon, **the model does not**, and which carries no user decision, no
booked mechanism, no specified cell and no named hypothesis.

```
mc1/1023   REG DATA_SEQ  nxta            row 874  ndiff 2605/4000 wrand15  chip MEMR 053b7  eng MEMR 053b8
mc2/640    REG DATA_SEQ  data            row 451  ndiff  354/4000 fix0     chip MEMW 0eaa7  eng MEMW 0eaa8
t30-raw/15 REG DATA_SEQ  data            row 539  ndiff  123/4000 fix0     chip MEMR aa576  eng MEMR aa574
mc2/887    REG PF_ADDR   nxta            row 436  ndiff    8/4000 wrand1   chip CODE 0ddfe  eng CODE 041de
mc1/2468   EVT PF_GAINED qs -!=F         row 319  ndiff  760/1140 wrand7   chip MEMR 00008  eng CODE 00510
mc1/3034   EVT PF_GAINED bs PASV!=CODE   row 484  ndiff   88/4000 fix0     chip INTA 0f4fb  eng CODE 0050a
mc2/327    EVT DATA_SEQ  t Ti!=T1        row 270  ndiff 1370/1709 fix2     chip INTA 00506  eng PASV 60506
mc1/1629   EVT PIN       data            row 3419 ndiff    2/3628 wrand7
mc1/3072   EVT PIN       data            row 903  ndiff    2/1100 fix0
```

**Four of the nine** are §87.A.3's already-booked *"the model closed five seeds
the `ucore` does not"* (the fifth, `mc2/2808`, is H3-B and sits at L2).
**FIVE — `mc1/1629`, `mc1/2468`, `mc1/3034`, `mc1/3072`, `mc2/327` — appear in
NO ledger in this repository**; a grep of `docs/notes/` for each returns zero
hits.  That is what a catch-all is for, and it is why the census was taken
rather than assembled from the ledgers.

**ONE OBSERVATION, RECORDED AS AN OBSERVATION.**  On `mc1/1023`, `mc2/640` and
`t30-raw/15` the two sides open **the same cycle, of the same type, at the same
clock**, and the ADDRESS differs by **±1 or ±2 in the low bits**.  That is the
shape `gaps` §T8 describes for a different, model-shared population (*"an exact
byte swap on an odd-address word write — M5b's `A0` swapper applied where the
chip does not"*).  **NOT CLAIMED**: §T8's seeds were model-shared and these three
are `ucore`-only, so they cannot be the same defect without a measurement nobody
has taken.  Its falsifier is written into the census.

### §88.B.5 THE ONE NON-BANK ITEM WITH NO DISPOSITION

The `ucore`'s S16 residue is **24 family-D + 27 `ARCH`**, and the 27 `ARCH` cells
(architectural read-back on `HLT.RES` at `w1`/`w2`: `sp`/`bp`, `ax`/`dx`,
`sp`/`si`/`flags`) are **booked and undispositioned**.  They are not inside the
9 — that count is defined over the fuzz corpus — and the census says so
explicitly, so that "catch-all = 9" is never read as "nine unexplained things in
the whole project".  **The honest total undispositioned surface is 9 banked
seeds plus 27 S16 `ARCH` cells, and nothing else.**

### §88.C WHAT THIS SITTING DID NOT DO

* **Nothing was landed.**  `git diff` over `hdl/rtl/` and `sim/` is empty.  The
  only tool change is `u4_tranche --leg` gaining `chip_f10`/`core_f10`.
* **No fix was proposed in half B** — the two observations above are recorded
  with falsifiers and explicitly not claimed.
* H3-B, the 8080 gap, the `8F` ghost cell, family D, H7 and the model-only
  residue were **not opened** — each is carried as its owner's named exclusion.
* **No memory file was touched.  Codex was not launched** — the closing review
  is the coordinator's, against this census.

---

## SUCCESSOR — THIS LEDGER IS CLOSED AT §88

The silicon-match phase closed with the user's acceptance of
`docs/notes/sm3_verdict_2026-08-05.md` on 2026-08-05, and the user directed a
successor campaign focused on **fuzz testing with random waits**.

**That campaign's ledger is `docs/notes/wrfuzz_provenance.md`** (task #38); its
plan is `docs/notes/wrfuzz_campaign_plan.md` and its corpus pre-registration is
`docs/notes/wrfuzz_corpus_prereg_2026-08-05.md`.  Nothing above this line is
modified by it: this file is CITED by the successor and is not appended to
beyond this pointer.
