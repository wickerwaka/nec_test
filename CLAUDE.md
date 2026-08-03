# nec_test — project instructions for Claude

## Execution model (standing rule, user directive 2026-08-02)

**All implementation work is done by Opus subagents.** The main (Fable)
session agent does not implement directly; it:
1. plans and scopes each task,
2. writes the subagent brief (context, gates, discipline),
3. launches the Opus subagent,
4. **reviews the completed work after EVERY task** — independently re-running
   the claimed gates and reading load-bearing code/ledger changes before
   accepting, launching the next task only after acceptance.

Small coordinator-level actions (one-line doc fixes caught in review, memory
updates, task-ledger bookkeeping, git housekeeping) may be done directly by
the main agent.

## Standing design principle (user directive 2026-08-01)

SIMPLICITY: this is 80's era hardware — nothing on the die is wasted.
Complex or confusing observed behavior is likely simple systems interacting
in ways not yet understood. A large fitted table, a many-cased rule, or a
per-opcode special case is a signal of misunderstanding, not a deliverable.
Put this principle verbatim into every modeling subagent brief.

## Standing engineering discipline

- Truthful commit messages: never assert a gate that is not met.
- **Verify against the artifact, not against recall**: an agent's absence of
  memory of an event is not evidence the event did not happen — check the
  ledger/commit/task record before "correcting" it; deleting a true record
  corrupts a truthful ledger exactly as badly as inventing one.
- Ratchet gates are monotone; pre-register numeric bars before runs; report
  failures as registered, never restated.
- Survey-then-fix: run the full batch, categorize all failures, then fix —
  mechanism-level only.
- Consult Codex (`codex:rescue`, resumed thread) as critical reviewer at
  campaign phase boundaries and before closing any verdict document.
- Board work: single-writer check first, socket only (`use_core=False`),
  no flashing unless explicitly authorized, pre-register predictions and
  commit before first board contact, retain full per-clock rows + sha256
  (never digests alone), run board_idle and verify after every session.
- /tmp discipline: no large temp files in /tmp (tmpfs quota); use
  `~/.cache/ucsimt-tmp` for big intermediates.
- Provenance ledgers: every modeled behavior tagged ROM / PLA / LAW /
  MEASURED / ASSUMPTION with evidence and falsifiers
  (docs/notes/ucsim_provenance.md, docs/notes/ucsim_t_provenance.md).

## Gate quick reference

(current as of ucsim-t §26, the pre-RTL cleanup. Values are the standing
ratchets: monotone, never re-scored downward without a loud, itemized entry.)

- **ROM/PLA**: `make -C sim test` (disasm byte-exact),
  `python3 sw/pla3_check.py` (21 checks).
- **Functional**: `python3 sw/ucsim_check.py --suite tests/v30/<suite>`
  (mod3_illegal needs `--residue stale-ea`; v20suite needs `--no-mirror`);
  full set = v0.1 169,000 + v0.2 347,000 + v0.3 3,699,998 + v20suite
  3,125,000 + mod3_illegal 128 = **7,341,126 cases**.
- **Timed, per-suite** — `sw/timed_gate.py --suite tests/v30/<suite>
  --forms all [--waits N]`:
  `v0.1` **169,000/169,000** (3 collision-dependent under the 64K mirror;
  `--no-mirror` reproduces the historical 168,997), `v0.1-w1` / `-w3`
  1,200/1,200, `v0.1-w1 --forms EB` 200/200, the four `v0.1-w*evt` cells
  200 / 1,200 / 200 / 1,200, `v0.1-w1evt-biased` 1,200/1,200 (preserved),
  and the four HLT delay sweeps `s10-hltsweep-w{0,1}` **91/97**, **92/95**
  and `s13-hltsweep-w{2,3}` **42/46**, **40/45**.
- **Timed, whole-program**: `sw/check_boot.py --timed 220`,
  `sw/timed_scenario.py` (18/0/9), `sw/timed_enter_replay.py` (154/154 x5),
  `sw/timed_ins_replay.py --raw` (rails 1312/1312, vs-chip 2624/2624),
  `sw/timed_wvec_gate.py` (88/88, +0.0 %), `sw/timed_lawcards.py`
  (**8 GREEN / 0 RED / 3 UNRESOLVED** — C6, C7, C11),
  `sw/timed_fuzz.py --evt-replay` (REGISTERED **1,272/1,702**, EVT
  **709/1,008**, COMBINED **1,981/2,710**),
  `sw/timed_fuzz.py --seeddir sw/testdata/t4/b2-tranche/seeds`
  (**154/188** — V5 is a standing REGISTERED FAILURE, not to be re-opened).
- **Measurement tools, NOT gates** (never quote them as a pass):
  `sw/s11_census.py`, `sw/s12_census.py` (`hltsweep`/`psw`/`regold`/`ackfam`),
  `sw/s14_census.py --band`, `sw/s14_dstar.py`, `sw/s15_census.py`
  (the fuzz-residue taxonomy and `--rmw`, the RMW population).
- **Board discipline**: `s13_board.div_guard()` PINS the divider and asks the
  transport for the readback — an UNPINNED readback is a rig-integrity
  FINDING. Every board probe calls it. Socket only (`use_core=False`,
  explicit — the board's CFG is sticky).
- NOTE: `sw/check_enter_nesting.py` is the VERILATOR/RTL leg only — it takes
  NO arguments (unknown flags are silently ignored), so do not use it to gate
  sim/ work. **General rule: verify a flag exists (`--help`) before trusting a
  run that used it.**
