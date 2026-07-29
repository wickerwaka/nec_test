# Standing gate set (nec_test)

The regression gates re-run after any RTL or generation-stack change. All are
board-free (cached chip refs + Verilator TB) unless noted. A change to the EU
decode path additionally requires the full golden sweep (v0.1 169k + w1/w3 +
f0lock + f4a + v0.3 3.7M) before any reflash (the RR-era bar; see
`sw/t30_sweep.sh`).

| Gate | Command | Proves |
|---|---|---|
| check_ff_t4 | `python3 sw/check_ff_t4.py` | the far-flush direct-commit slots stay reachable (SLOT_FF_T4 non-vacuous) |
| check_lc6_gate | `python3 sw/check_lc6_gate.py` | the Family-5 strio-single uline-1 veto (eu_rsv_strio→pick_t3) is intact — directed non-REP OUTSB gadgets (BIU-rebuild B0; needs current Verilator binary) |
| check_race_law | `python3 sw/check_race_law.py` | the POP-PSW/INT race law is bit-exact |
| prefix_clear_lint | `python3 sw/prefix_clear_lint.py` | `clear_prefixes()` single-source at every retire/exit site (RR4) |
| ss_lint | `python3 sw/ss_lint.py` | the savestate address map is consistent (BIU×2 + EU×2 + tag = SS_COUNT) |
| ea_step_lint | `python3 sw/ea_step_lint.py` | every operand EA step wraps via `ea_step2` (F4a) |
| check_mod3_illegal | `python3 sw/check_mod3_illegal.py` | LEA mod=11 executes chip-exact (task #30); cycle rows + moffs value + arch-confined residue |
| check_enter_nesting | `python3 sw/check_enter_nesting.py` | ENTER walk == chip: MASK tranche (w0 nesting 0..255, no mod-32 mask) AND WAITED tranche (nesting set x waits {0,1,2,3,7}+wrand): walk-stream strict at ALL waits (PUSH-BP-drop guard) + cycle-exact with enumerated known-divergences (task #31, both ENTER bugs) |
| check_fuzz_bank | `python3 sw/check_fuzz_bank.py [--strict]` | the fuzz bank round-trips: regenerate (GEN-DRIFT hard fail) -> TB replay -> re-classify vs banked chip rows, verdicts stable (task #29 Phase 6) |
| fuzz_campaign lint | `python3 sw/fuzz_campaign.py lint` | the soup/raw generators never emit a chip-wedging image |
| optable selfcheck | `python3 sw/optable.py --selfcheck` | the opcode table agrees with fuzz_cov + instructions.json |
| test_fuzz_classify / test_fuzz_accept | `python3 sw/test_fuzz_{classify,accept}.py` | the verdict tree + acceptance rules (offline) |
| ss modes | `python3 sw/check_core.py --ss-sweep ...` | savestate save/restore is cycle/arch clean mid-instruction |
| f4a_boundary_battery | `python3 sw/check_core.py --suite-dir tests/v30/f4a_boundary ...` | the EA FFFF->0000 wrap consumers |

`sw/t30_sweep.sh` runs the lints + gates + every golden suite in one detached
pass (the pre-reflash bar for EU decode-path changes).

## Meta-finding: the vacuous-gate pattern (task #29 campaign)

Three times this campaign a green gate was VACUOUS - it passed while blind to a
real defect, because it only checks what it already knows to look at:

1. **F7a strio-domain assert** (v30_biu.sv): an over-narrow `assert` that had
   never been exercised outside the w0 strio domain; the fuzz soup reached the
   coincident state under waited/interrupt-shifted timing and it fired. Board
   arbitration proved the state chip-correct -> the assert was wrong, downgraded
   to a counter (`cov_f7a_coldarm`).
2. **Terminal-else S_HALT park** (v30_eu.sv): register-form opcodes with no
   dispatch branch silently parked at S_HALT with NO assert. LEA mod=11 wedged
   the core there for the entire task #29 pilot corpus before anyone noticed.
   Fixed with a WHITELIST assert: a park is legal only for board-verified
   chip-halts encodings; anything else fires with opc/modrm.
3. **ss_lint's unmapped-flop blind spot**: ss_lint verifies only symbols ALREADY
   in the map (their read/write arm counts), so it CANNOT see a NEW unmapped
   architectural flop. `last_ea` (task #30) was unmapped and ss_lint passed
   vacuously until the symbol was added.

4. **check_enter_nesting w0-ONLY blind spot** (task #31): the ENTER-nesting
   tranche captured chip goldens at **w0 only**, so it was VACUOUS for the second
   ENTER bug — the PUSH-BP drop that manifests only under waits (w>=2). It passed
   green while every ENTER under waits dropped its BP push. Same root as the
   others: the gate tested only the dimension it already knew (nesting, at the one
   wait it happened to sample). Closed by the WAITED tranche (waits {0,1,2,3,7} +
   wrand); the standing rule generalizes to "sweep the wait axis, not just w0, for
   any bus-timing-sensitive behavior."

Common root: a gate that enumerates the KNOWN and asserts consistency, but has
no census of the UNKNOWN. The mechanization rule the campaign adopted -
"instrument the silent path so the day a golden/fuzz stream first exercises it we
catch it" - closed (1) and (2). For (3) the recommended standing improvement is a
**flop-census-vs-map lint**: enumerate every `reg` declaration in v30_eu / v30_biu,
classify persistent architectural flops, and assert each has an `SSA_` mapping -
so a new unmapped flop fails ss_lint the day it is added, not the day a savestate
restore first reads it. (Deferred; booked here for the campaign close-out.)
