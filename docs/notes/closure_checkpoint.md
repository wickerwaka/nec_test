# Campaign 3 closure block — live checkpoint (handoff document)

Updated at every commit. Successor: read this + ROADMAP.md, then continue
the fit loop below. Board = root@mister-nec (health: `python3 sw/v30run.py
echo`). NEVER reprogram the FPGA; one board user at a time.

## Pipeline state (background, survives this session)
- **Batch-2 emission running** on the board: 102 forms x 500 cases
  (list: scratchpad/batch2.txt), log
  `<scratchpad>/emit_batch2.log`, ~143 s/form. Order: compare strings
  (done), ALU-imm 80/81/83 (done), shifts C0/C1/D0-D3 (in flight), BCD
  27/2F/37/3F/D4/D5 (last). Scratchpad =
  /tmp/claude-1000/-home-wickerwaka-src-nec-test/87d2c09e-.../scratchpad.
- **chain2.sh armed** (same scratchpad): when `chain.log` gains
  "CHAIN: batch-2 emission complete" it deploys sw/v30ctl.py (serve v2)
  to the board, runs `validate_v2.py` (RUN-vs-DELTA byte-match burst;
  auto-reverts device script from scratchpad/v30ctl_v1.py on failure),
  then launches **batch-3**: 135 forms (batch3.txt) + addendum F6.6
  (batch3_addendum.txt - NOT yet in batch3.txt; emit it separately).
- **fitwatch3.sh** scores each landed tranche with check_core, appends
  to `<scratchpad>/fitwatch.log`; done-list `fitwatch.done` (remove a
  form to re-score). It skips while verilator runs but can still race
  a rebuild - CHECK-ERROR lines = re-queue the form.
- If the scratchpad is gone (new session): re-arm equivalents; suite
  files in tests/v30/v0.1 are the ground truth of what has landed.

## Status: validated (cycle+state exact, committed)
- Whole legacy corpus 36500/36500 (Mission P complete: F3AA pop-anchored
  abort law, INT.9D race table = int9d_race.hex, INT.FB patched,
  ghost-INT documented in interrupt_model.md).
- OUT E6/E7/EE/EF; all strings (singles, REP byte/word, REP LODS,
  compare strings x16 incl. REPC/REPNC); ALU-imm 80.0-80.6/81.x/83.x;
  shift-imm C0.0-C0.7 (major laws: full 8-bit count, no 5-bit masking;
  linear count timing; byte-RMW other-lane shift-register semantics -
  see f956250 commit message and shrot() header).

## Pending arrival (laws fitted, expect pass; re-check on landing)
- 80.7, C1.x (word shift-imm), D0.0-D0.7/D1.x (by-1), D2/D3 (CL, routed
  through S_SHWAIT; BASE SLOTS UNFITTED - will need the C0-style fit:
  extract pop->write/close deltas, adjust S_SHWAIT dispatch constants
  which currently assume the C0 anchor).
- BCD 27/2F/37/3F/D4/D5 (skeletons + documented flag laws; timing
  guesses dly1/15/6 in S_DEC + S_BCD_IMM).

## Pending fit (batch-3, skeletons in core, timing guessed)
acc-imm ALU (04..3D), TEST (84/85/A8/A9/F6.0/F7.0), XCHG 91-97,
LAHF/SAHF, flag ops F5/F8/F9/FA/FB/FC/FD, PUSH/POP sreg, PUSHF,
PUSH imm 68/6A, PUSH R/POP R 60/61 (NOT implemented in EU - only
emitter!), NOT/NEG, MULU16/IMUL8/16, IMUL 69/6B, INC/DEC FE.1/FF.0/1,
PUSH mem FF.6, POP mem 8F.0, CALL/BR rm FF.2-5, LDS/LES C4/C5, far
transfers CB/CA/9A/EA/CF, software INT CC/CD/CE, CHKIND 62, PREPARE/
DISPOSE C8/C9, DIVU8 F6.6, 0F bit ops (0F10-1F CL/imm variants beyond
0F18), ROR4 0F2A, SUB4S/CMP4S 0F22/26, FPO D8-DF/66/67, prefixed
strings 26.A4/2E.A5/36.A6/3E.AC, Jcc full set + E0/E1/E3 (branch
machinery exists; taken-timing for new cc codes shares Jcc laws).
NOT in core at all: INS/EXT 0F31/33/39/3B (build from traces when the
tranches land), PUSH R/POP R execution.

## Fit-loop recipe (per form, as fitwatch flags it)
1. `python3 sw/check_core.py --opcodes X --keep` then diff rows via
   build_rows_sim (see the session's inline scripts; row cols:
   7=busstat 8=tstate 9=qop).
2. Extract the timing anchor law from ALL golden cases (Counter over
   pop/done/write deltas), adjust the dly constants marked "fit
   pending" in v30_eu.sv, rebuild
   (verilator --binary --timing -DV30_BACKDOOR -Wall
   -Wno-UNUSEDSIGNAL -Wno-VARHIDDEN --top-module tb_v30_core -Mdir
   hdl/tb/obj_dir hdl/tb/tb_v30_core.sv hdl/rtl/core/v30_core.sv
   hdl/rtl/core/v30_biu.sv hdl/rtl/core/v30_eu.sv), rescore.
3. Commit per family with the law in the message; keep neighbors green
   (spot: `--opcodes legacy --cases 100`).

## Handoff plan (coordinator directive)
When every documented form is validated or pending-arrival with fitted
laws: STOP. Do NOT start Mission S (fuzz campaign) - a fresh agent
takes S and R. Mission S tooling is ready: sw/gen_seq.py +
sw/check_seq.py (TB-vs-TB self-test passes; board side untested; only
run fuzz AFTER Q complete). Serve-v2 (delta/partial-capture protocol)
is coded+unit-tested, deploys at the batch-2/3 boundary via chain2.
