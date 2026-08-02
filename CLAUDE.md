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

- Functional: `python3 sw/ucsim_check.py --suite tests/v30/<suite>`
  (mod3_illegal needs `--residue stale-ea`); full set = v0.1, v0.2, v0.3,
  v20suite, mod3_illegal = 7,341,126 cases.
- Timed: `sw/timed_gate.py` (v0.1 w0 + `-w1 --waits 1` / `-w3 --waits 3`),
  `sw/check_boot.py --timed`, `sw/timed_scenario.py`, `sw/timed_lawcards.py`,
  `sw/timed_ins_replay.py`, `sw/timed_fuzz.py`,
  `sw/check_enter_nesting.py --sim ucsim-timed` (default mode is the
  Verilator/RTL leg — use the --sim modes for the C++ simulator).
- ROM/PLA: `make -C sim test` (disasm byte-exact), `python3 sw/pla3_check.py`.
