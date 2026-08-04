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
  and the four HLT delay sweeps `s10-hltsweep-w{0,1}` **91/97**, **95/95**
  and `s13-hltsweep-w{2,3}` **44/46**, **42/45**.  (These were STALE here at
  92/95, 42/46, 40/45 — the pre-§26.7.6 figures — from the S15 cleanup until
  ucore U3 re-measured the model leg and found the quick reference disagreeing
  with `ucsim_t_provenance.md` §26.11's own delta row.  Corrected UPWARD.)
- **Timed, whole-program**: `sw/check_boot.py --timed 220`,
  `sw/timed_scenario.py` (18/0/9), `sw/timed_enter_replay.py` (154/154 x5),
  `sw/timed_ins_replay.py --raw` (rails 1312/1312, vs-chip 2624/2624),
  `sw/timed_wvec_gate.py` (88/88, +0.0 %), `sw/timed_lawcards.py`
  (**8 GREEN / 0 RED / 3 UNRESOLVED** — C6, C7, C11),
  `sw/timed_fuzz.py --evt-replay` (REGISTERED **1,272/1,702**, EVT
  **709/1,008**, COMBINED **1,981/2,710**),
  `sw/timed_fuzz.py --seeddir sw/testdata/t4/b2-tranche/seeds`
  (**154/188** — V5 is a standing REGISTERED FAILURE, not to be re-opened).
- **The `ucore` RTL twin** (`--core ucore`, stage U3 close; these are the
  ucore's OWN ratchets, not the model's — see `ucore_provenance.md` §44):
  `check_core.py --core ucore --opcodes all --cases 0` **169,000/169,000**;
  `v0.1-w1`/`-w3` 1,200; `EB` 200; the four `evt` cells 200/1,200/200/1,200;
  `v0.1-w1evt-biased` 1,200; `check_boot.py --core ucore` 220 and 400;
  `ulockstep.py --golden all --cases 50` **17,350/17,350**;
  `timed_wvec_gate.py --core ucore` **88/88, +0.0 %** (the FSM core is 71/88);
  `timed_enter_replay.py --core ucore` **154/154 x5**;
  `timed_ins_replay.py --core ucore --raw` **1,312/1,312** and **2,624/2,624**;
  `timed_fuzz.py --core ucore --evt-replay` REGISTERED **1,394/1,702** (the sim
  is 1,272) and `--seeddir …/b2-tranche/seeds` **168/188** (the sim is 154);
  the four HLT sweeps **90/97, 88/95, 37/46, 34/45** (below the model by 23
  cells: 17 the TB cannot score + 6 diagnosed — §43).
  **`--rig-hold reg8`** exists because the rig's `evt_hold` register is 8 bits;
  it moves the SIM's EVT number too (+71), so it is OFF by default and the EVT
  ratchet is NOT re-registered against it (F46).
- **KNOWN-RED, deliberately**: `sw/ss_lint.py --core ucore` exits **1**. That is
  truthful, not broken — five architectural flops are absent from the ucore's
  save-state map (F49). The `--core fsm` leg is unchanged and still exits 0.
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
