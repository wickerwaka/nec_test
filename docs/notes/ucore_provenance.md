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
| **G3** | `check_core.py --core ucore --opcodes all --cases 0` | **156,123 / 169,000 — NOT MET** |

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
| rung 10 (M5b `odd_base`, F29) | **18,832** | **310** | **306** | 5 |

**No form regressed at any step** — every rung was scored by a form-by-form
diff of the two whole-suite censuses, not by the total.

### §29.2 G3, stated honestly, BOTH numbers

The work order asked for two numbers because the sim carries registered
residue against SILICON.  At **w0 it does not**: `timed_gate.py` over the whole
v0.1 suite reports **169,000/169,000 arch, 169,000/169,000 window, 169,000
rows-exact, row-diffs 0**.  So at w0 there is nothing to subtract, and the two
numbers coincide:

* G3 through the golden comparator: **156,123 / 169,000** (92.4 %).
* G3 minus the sim's registered w0 residue: **156,123 / 169,000** — the same
  number, because that residue is empty at w0.

**41 RED forms**, of which **12 (2,400 cases) are unimplemented by design**
(`INT.*`, `NMI.*`, `HLT.*`).  Excluding those, the RTL is
**156,123 / 166,600 = 93.7 %** of what it is currently built to do.

(The 907+3 residue rows named in the pass-3 brief are a WAIT-AXIS quantity —
they belong to U3, not to this gate.  Re-derive them there; do not carry the
figure forward from memory.)

## §30 WHAT IS LEFT — 41 RED FORMS, ENUMERATED

Not a family: a tail.  Grouped by first divergence, with the case count each
costs out of 169,000.  (`0F 10-1F`, the word string moves and `8F.0` were in
this table when it was first written and were closed by rung 10 — see §28's
F29 and M5b's `odd_base`.  What follows is the list AFTER that.)

| group | forms | cost | reading |
|---|---|---|---|
| **interrupt / HLT entries** | `INT.*` (7), `NMI.*` (2), `HLT.*` (3) | 2,400 | **UNIMPLEMENTED BY DESIGN** (§19.3): no interrupt entry, `eu_unhalt` tied 0, the POLL pipeline is the static level only, `intr_pending` has no writer.  A work list, not a bug list |
| **BCD adjust + BCD strings** | `27` `2F` `37` `3F` `0F20` `0F22` `0F26` | 3,225 | `27`/`2F`/`37`/`3F` are CYCLE-EXACT and arch-red, so it is the adjust unit ALONE (`sim/alu.cpp::bcd_adjust`) — the tightest-scoped item left.  `0F20`/`0F22` add the string loop |
| **multi-cycle pushes** | `60` (PUSHA) `62` (BOUND) `CC` `CD` `CE` | 2,182 | `busstat`: the RTL runs consecutive stores BACK TO BACK where the golden has idle `Ti` between them.  Task #33's multi-push bus-hold datapoint, now reproducible in RTL |
| **CALL and the flush display** | `E8` `FF.2` `FF.3` `9A` | 1,686 | `qop`: the flush's `E` blip is ONE CLOCK EARLY in about half the cases.  The row order is right; this is the BIU's `e_pend` / "a ready-but-not-yet-started EU request owns the next slot" term (F1(c)), not the EU |
| **DIV** | `F6.6` `F6.7` `F7.6` `F7.7` | 1,571 | the iterative divider: `busstat` |
| **strings / ENTER** | `C8` `F3A4` `F3A5` `F3AA` `F3AB` `F2AA` | 1,601 | the REP continuation and ENTER's nesting walk |
| **the rest** | `FA` `FB` `POLL.LO` | 212 | `FA`/`FB` are 88-90 % green (the 1BL execute strobe's late-queue edge) |

## §31 HANDOFF — what pass 4 picks up

1. **The order is by cost and by confidence**: BCD adjust first — `27` `2F`
   `37` `3F` are CYCLE-EXACT and arch-red, so the whole difference is inside
   one function and the microscope is not even needed (`sw/uarch.py 27,2F,37,3F`
   is the entire instrument).  Then the multi-cycle pushes (5 forms, 2,182),
   then DIV (4, 1,571), then CALL's flush display (4, 1,686).
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
4. **REGISTERED RESIDUE, booked and not patched**: a successor that is a PREFIX
   increments `pfxcnt` in S_DECODE on edge `c`, and F22's deferred reset then
   zeroes it on edge `c+1`.  No v0.1 case reaches it (the injected successor is
   always `90`); it is a real hazard for whole-program replay and must be
   settled before U3's image work.
5. **The structural lesson of §28.1 is a constraint on every future fix**:
   nothing the EU's act decode reads may be computed inside the BIU's single
   next-state process.  If a fact is needed there, give it a flop.
6. **Still not run**: `ulockstep` batch mode over golden cases, the wait axes
   (U3), the second Codex review (this pass ended at a rung boundary before it).
