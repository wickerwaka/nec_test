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
