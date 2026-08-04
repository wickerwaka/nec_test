# Standing gate set (nec_test)

The regression gates re-run after any RTL or generation-stack change. All are
board-free (cached chip refs + Verilator TB) unless noted.

**THE STANDING CORE IS `ucore` (`hdl/rtl/ucore/`) SINCE 2026-08-04.** The
trace-fitted FSM core (`hdl/rtl/core/`) was ARCHIVED on that date — see
`docs/notes/fsm_core_archive_2026-08-04.md` and the disposition evidence in
`docs/notes/ucore_campaign_verdict_2026-08-04.md` §(e) item 1. Its gates did not
disappear; they moved to the ON-DEMAND section below, because **they gate an
archived artifact.** `--core fsm` still builds and still runs.

`sw/check_core.py`, `sw/check_boot.py`, `sw/check_ab_sim.py`, `sw/ss_lint.py`
and `sw/ss_flopcensus.py` **now default to `--core ucore`** (they defaulted to
`fsm` before 2026-08-04). The `timed_*` tools still default to `--core sim`, the
C++ reference model — that is the spec engine and it did not change.

---

## A. THE STANDING SET — core-neutral

| Gate | Command | Proves |
|---|---|---|
| ROM disasm | `make -C sim test` | the disassembly is byte-exact vs `V20UC.TXT` |
| PLA | `python3 sw/pla3_check.py` | 21 PLA checks |
| check_ucore_tables (G0) | `python3 sw/check_ucore_tables.py` | the generated `hdl/rtl/ucore/` tables byte-match `sim/`: 1028 ROM rows + 8192 micro-addresses + 768 PLA entries = **9,988**, on an INDEPENDENT re-parse and on the emitted artifacts (`ucore_provenance.md` §4) |
| optable selfcheck | `python3 sw/optable.py --selfcheck` | the opcode table agrees with fuzz_cov + instructions.json |
| fuzz_campaign lint | `python3 sw/fuzz_campaign.py lint` | the soup/raw generators never emit a chip-wedging image |
| test_fuzz_classify / test_fuzz_accept | `python3 sw/test_fuzz_{classify,accept}.py` | the verdict tree + acceptance rules (offline) |
| gen_ucore_qsf | `python3 sw/gen_ucore_qsf.py --check` | `hdl/nec_test_ucore.qsf` is a faithful derivative of `hdl/nec_test.qsf` — the two A/B bitstreams differ by the CORE and nothing else |

## B. THE STANDING SET — the `ucore`

Standing ratchets. Monotone: never re-scored downward without a loud, itemised
entry. Figures are `ucore_provenance.md` §54.4's, re-run 2026-08-04.

| Gate | Command | Standing number |
|---|---|---|
| **G3** | `python3 sw/check_core.py --opcodes all --cases 0` | **169,000 / 169,000** (cycles AND arch) |
| wait axis | `check_core.py --suite-dir tests/v30/v0.1-w1 --waits 1` / `-w3 --waits 3` | 1,200 / 1,200 each |
| `EB` at w1 | `… --suite-dir tests/v30/v0.1-w1 --opcodes EB --waits 1` | 200 / 200 |
| the four `evt` cells | `… --suite-dir tests/v30/v0.1-w{0,1,2,3}evt --waits {0,1,2,3}` | 200 / 1,200 / 200 / 1,200 |
| `w1evt-biased` (preserved) | `… --suite-dir tests/v30/v0.1-w1evt-biased --waits 1` | 1,200 / 1,200 |
| **block I/O (INM/OUTM)** | `… --suite-dir tests/v30/v0.3 --opcodes 6C,6D,6E,6F,F26C,F26D,F26E,F26F,F36C,F36D,F36E,F36F,646C,646D,646E,646F,656C,656D,656E,656F,26.6E,2E.6F,36.6E --cases 0` | **229,999 / 229,999** cycles AND arch, 1 documented pre-existing excluded (`646F/[8988]`).  *First measured against the ucore 2026-08-04.*  This is the ONLY gate that reaches 6C-6F — `v0.1` has none, and `timed_ins_replay`'s 1,312/2,624 is the bit-field INS `0F 31`/`0F 39`, not block I/O |
| f4a boundary battery | `… --suite-dir tests/v30/f4a_boundary --cases 0 --waits 0` | **160 / 160** — the EA FFFF→0000 wrap consumers.  *First measured against the ucore 2026-08-04, at the default flip; identical to the FSM core's 160/160* |
| f0lock tranche | `… --suite-dir tests/v30/f0lock_tranche --cases 0 --waits 0` | **400 / 400** — *same provenance as the row above* |
| boot march | `python3 sw/check_boot.py --timed 220` and `--timed 400` | MATCH / MATCH |
| lockstep vs the model | `python3 sw/ulockstep.py --golden all --cases 50` | **17,350 / 17,350** (`--suite --waits 0,1,2,3` = ALL SCENARIOS LOCKSTEP) |
| wvec silicon freeze | `python3 sw/timed_wvec_gate.py --core ucore` | 88 / 88, **+0.0 %** |
| ENTER replay | `python3 sw/timed_enter_replay.py --core ucore` | 154 / 154 ×5 |
| INS replay | `python3 sw/timed_ins_replay.py --core ucore --raw` | 1,312 / 1,312 and 2,624 / 2,624 |
| the registered fuzz bank | `python3 sw/timed_fuzz.py --core ucore --evt-replay` | REGISTERED **1,483 / 1,702**; EVT 192/1,008; COMBINED 1,675/2,710; `BOUND WARNINGS` 5, `ENGINE ABORTS` 0; denominators 2,710 scored / 532 `OPEN_BUS` |
| the b2 victory tranche | `python3 sw/timed_fuzz.py --core ucore --seeddir sw/testdata/t4/b2-tranche/seeds` | **171 / 188** — V5 is a standing REGISTERED FAILURE, not to be re-opened |
| save-state map | `python3 sw/ss_lint.py` | rc=0; 218 addresses, 201 flops, 0 UNMAPPED, `SS_VERSION` 0x82 |
| save-state sweeps | `check_core.py --ss-sweep …` modes 1 / 2 / 5 | 80/80 · 24/24 · width PASS |
| CE hold | `check_core.py --ce-div 4 --ce-hold-check` | `CE_HOLD_VIOL 0` |
| the core inside the real integration | `python3 sw/check_ab_sim.py` | 187 rows MATCH |
| the MODEL, unmoved | `python3 sw/timed_gate.py --suite tests/v30/v0.1 --forms all` | 169,000 / 169,000, row-diffs 0 |

**Known-RED, standing and registered** (reproduce as exactly this; they are not
passes and must not be quoted as any):

| | number | where it is written down |
|---|---|---|
| the four HLT delay sweeps | **91/97, 90/95, 40/46, 38/45 = 259/283** (the model is 272/283) | `ucore_gaps_2026-08-04.md` §T1 |
| the fabric HLT sweeps | **143/283** — the 116-cell INTA class, attribution **NOT ESTABLISHED** | `ucore_provenance.md` §56.3a |
| the b2 tranche | 171/188 — V5, REGISTERED FAILURE | `ucore_provenance.md` §44.2 |

The complete, itemised list of what is **not** yet functional or timing-accurate
is `docs/notes/ucore_gaps_2026-08-04.md`.

---

## C. ARCHIVED — ON DEMAND (the FSM core)

**These gate an ARCHIVED artifact.** They are not part of the standing set and a
green run of them says nothing about the ucore. Run the whole block before
re-activating the FSM core for anything (`fsm_core_archive_2026-08-04.md` §6);
otherwise, on demand only.

Every one is FSM-structural — it reads or mutates `hdl/rtl/core/*.sv`, or it
binds to the FSM `obj_dir` through `sw/check_seq.py`'s `BIN` constant — and has
no ucore counterpart.

| Gate | Command | Proves | binds to FSM via |
|---|---|---|---|
| check_race_law | `python3 sw/check_race_law.py` | the POP-PSW/INT race law is bit-exact | `rtl/core/race_law.svh`, `int9d_race.hex` — no ucore equivalent exists |
| check_ff_t4 | `python3 sw/check_ff_t4.py` | the far-flush direct-commit slots stay reachable (`SLOT_FF_T4` non-vacuous) | its own `hdl/tb/obj_dir/Vtb_v30_core` constant |
| check_lc6_gate | `python3 sw/check_lc6_gate.py` | the Family-5 strio-single uline-1 veto (`eu_rsv_strio`→`pick_t3`) is intact | `biu_law_lc6_gadget` mutates `rtl/core/v30_biu.sv` |
| prefix_clear_lint | `python3 sw/prefix_clear_lint.py` | `clear_prefixes()` single-source at every retire/exit site (RR4) | greps `rtl/core/v30_eu.sv` |
| ea_step_lint | `python3 sw/ea_step_lint.py` | every operand EA step wraps via `ea_step2` (F4a) | greps `rtl/core/v30_eu.sv` |
| check_mod3_illegal | `python3 sw/check_mod3_illegal.py` | LEA mod=11 executes chip-exact (task #30) | `check_seq.BIN` |
| check_enter_nesting | `python3 sw/check_enter_nesting.py` | ENTER walk == chip: MASK tranche + WAITED tranche (task #31, both ENTER bugs) | `check_seq.BIN`; **takes NO arguments** — unknown flags are silently ignored |
| check_fuzz_bank | `python3 sw/check_fuzz_bank.py [--strict]` | the 3,242-seed banked corpus round-trips: regenerate → TB replay → re-classify, verdicts stable (task #29 phase 6) | `check_seq.BIN` |
| ss_lint, FSM leg | `python3 sw/ss_lint.py --core fsm` | the archived core's save-state map is consistent (203 addresses, 181 flops, 0 UNMAPPED) | `--core fsm` |
| the full FSM sweep | `sw/t30_sweep.sh` | the RR-era pre-reflash bar: the lints + gates + every golden suite, **explicitly `--core fsm` on every leg since 2026-08-04** | pinned |

**`check_fuzz_bank` keeps a value the disposition does not touch**: it is the
load-bearing control for the U5 comparator change (3,242 banked seeds replayed
and re-classified, **worse 0** — `ucore_provenance.md` §57.2). Cite it for that.

**READ BEFORE QUOTING ANY FSM NUMBER.** On the corrected comparator (the TB's
composed-AD mask removed at U5) the archived core is **168,400 / 169,000** on
v0.1 and **16 / 283** on the HLT sweeps. `t30_sweep.sh`'s "any non-full suite
total = regression" rule must be read against 168,400, not 169,000.

---

## D. The default flip of 2026-08-04 — what was checked

The flip was `fsm → ucore` on the five tools named at the top. Everything that
consumed the old default was found and made EXPLICIT rather than left to inherit
the new one:

* `sw/t30_sweep.sh` — six `check_core.py` calls and one `ss_lint.py` call, all
  now `--core fsm`. This is the one place where a silent flip would have
  changed a whole regression sweep's meaning.
* `sw/biu_law_mutation.py`, `sw/biu_law_lc3_gadget.py`,
  `sw/biu_law_lc6_gadget.py`, `sw/biu_law_lc3_seedsearch.py` — all four mutate
  `rtl/core/v30_biu.sv`; all four now pass `--core fsm`.
* `sw/sweep_parallel.py` — gained an explicit `--core` (default `ucore`) and
  passes it to `check_core.build()`.
* `sw/check_core.py`'s module-level `RTL` and `BIN` constants stay pinned to the
  FSM layout and have **no consumers** in the tree; annotated as traps.
* The two suites that the flip newly points at the ucore were **measured
  rather than assumed**: `f4a_boundary` **160/160** and `f0lock_tranche`
  **400/400**, identical to the FSM core's, and they are now registered in §B.

---

## Meta-finding: the vacuous-gate pattern (task #29 campaign, and after)

Five times now a green gate was VACUOUS — it passed while blind to a real
defect, because it only checks what it already knows to look at:

1. **F7a strio-domain assert** (`v30_biu.sv`): an over-narrow `assert` that had
   never been exercised outside the w0 strio domain; the fuzz soup reached the
   coincident state under waited/interrupt-shifted timing and it fired. Board
   arbitration proved the state chip-correct → the assert was wrong, downgraded
   to a counter (`cov_f7a_coldarm`).
2. **Terminal-else S_HALT park** (`v30_eu.sv`): register-form opcodes with no
   dispatch branch silently parked at S_HALT with NO assert. LEA mod=11 wedged
   the core there for the entire task #29 pilot corpus before anyone noticed.
   Fixed with a WHITELIST assert.
3. **ss_lint's unmapped-flop blind spot**: ss_lint verifies only symbols ALREADY
   in the map, so it CANNOT see a NEW unmapped architectural flop. `last_ea`
   (task #30) was unmapped and ss_lint passed vacuously until the symbol was
   added. **CLOSED** — `sw/ss_flopcensus.py` now runs RTL→map for both cores and
   is invoked by `ss_lint`; on its first ucore run it found five unmapped flops
   (F49), which is exactly the class no map-walking instrument can see.
4. **check_enter_nesting w0-ONLY blind spot** (task #31): the ENTER-nesting
   tranche captured chip goldens at **w0 only**, so it was VACUOUS for the
   PUSH-BP drop that manifests only under waits (w≥2). Closed by the WAITED
   tranche. The standing rule generalises to *"sweep the wait axis, not just w0,
   for any bus-timing-sensitive behavior."*
5. **The composed-AD mask** (ucore U5, F51): `tb_v30_core.sv` substituted the
   RETAINED A19-16 nibble across a HALT display, and the retained nibble happens
   to equal the correct value by construction — so a gate that BOTH cores failed
   read green for the life of the project, and only the fabric (where pads do
   not retain) could see it. The rule this produced: **a comparator that
   substitutes a value is asserting a mechanism, and the mechanism needs its own
   falsifier.** Mask removed; the ucore fixed, the archived core not.

Common root: a gate that enumerates the KNOWN and asserts consistency, but has
no census of the UNKNOWN.
