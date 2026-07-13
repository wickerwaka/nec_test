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
  shift-imm C0.0-C0.7 + word C1.x + by-1 D0/D1 + CL D2/D3 (full-count
  laws, see f956250/b194cd0); BCD adjusts 27/2F/37/3F (V = signed
  overflow of either fix step; V30 DEVIATION: AC moves the DAA/DAS
  high-fix threshold to >0x9F; ADJBA/ADJBS S/Z/P from the pre-mask
  adjusted byte; slots +3 / +7).
- Serve-v2 DEPLOYED+VALIDATED on-board at the batch-2/3 boundary:
  RUN-vs-DELTA byte-match 8/8, 31 ms/case (9x). Batch-3 emitting on
  the fast path - expect completion within ~1-2 h of 21:00.

## Pending arrival (laws fitted, expect pass; re-check on landing)
- BATCH-2 COMPLETE: all 102 forms fitted+green. Additional laws:
  D4 close imm-pop+13ish (dly 11), D5 dly 4; CVTDB IGNORES its
  immediate base (always AH*10+AL) and V = the final add's signed
  overflow (manual wrong); word acc-imm (05-3D odd) executes AND
  retires on the hi-imm pop edge (B8 pattern, arch_ip = pc+1).
- fitwatch3 KILLED during active fitting (rebuild races); re-arm from
  the checkpoint recipe when idle. Monitor also stopped - use
  fitwatch.log + ls of tests/v30/v0.1 for the to-do queue.
- FITTED since: PUSH sreg/PSW (r16-push staging pattern), the entire
  0F bit-op family 0F10-0F1F (laws: TEST1/SET1/NOT1 CL reg close
  pop+3, CLR1 +4; TEST1 imm-word/SET1/NOT1 imm reg +2, CLR1 imm +3;
  mem wT1 done+7 CLR1 / done+6 SET1-NOT1; SET1/NOT1 imm-mem hold a
  req-not-ready bus reservation from pop+1 - idle-end evals at the
  pop go to the prefetcher, later fetch-T3 evals are blocked).
- FITTED since: full Jcc 70-7F (one condition matrix - the 74/75/7C
  timing laws generalize), E0/E1 (2-cycle decode lead-in, disp pops
  F+4, not-taken retires ON the pop, taken dly4, NO JWAIT
  reservation), E3 (not-taken pop+3, taken dly5 with the E2-style
  reservation exception dly==5), ROR4 (AL takes the WHOLE byte -
  undocumented; reg pop+17, mem done+17), SUB4S/CMP4S laws.
- FITTED since: FPO 66/67/D8-DF x10 (reg: retire ON the modrm pop,
  arch_ip=pc+1; mem: S_NOP after read done), TEST 84/85 (reg: flags+
  retire ON modrm pop; mem: flags at read done + S_NOP), A8/A9,
  F6.0/F7.0 TEST rm,imm (mem imm pops done+3 = one gap MORE than the
  80.x ALU-imm done+2; reg imm pops modrm-pop+2 via the same gap; F7.0
  retires ON the hi-imm pop, B8 pattern), flag ops F5/F8/F9/FC/FD/9F
  (retire in S_DEC = close pop+2), 9E SAHF (pop+3).
- FITTED since: NOT/NEG mem F6.2/3 F7.2/3 (RMW write req at read
  done+3 = S_WREQ; the BIU eu_ready_p1 gate makes the busy-bus slot).
- FITTED since: whole multiply family F6.4/F6.5/F7.4/F7.5/69/6B
  3000/3000. LAWS (undefined_flags.md): signed-MUL S/Z/AC/P = ALU
  flags of an internal lo+lo self-add of the result low half
  (S=bit6/14, Z=low-7/15-bits==0, AC=bit3, P=parity(lo<<1)); timing
  +4 cycles iff operand sign bits differ.
- REMAINING fit queue (bulk-score for current truth): 8F.0 partial, 9A pushes,
  C4/C5 second-read slot, C8 PREPARE (arch 0 - debug), C9/CB/CA/CF/
  CC/CD/CE cold-half decode-reservation (add opcodes to the S_DEC
  eu_req list like C3) + slots, 62 CHKIND slots, EA variant, 68/6A
  push slot cold quarter,
  0F22 sibling residue (parked), 0F26 2-case residue (parked).
- NOT IMPLEMENTED: 60/61 (PUSH R/POP R), INS/EXT 0F31/33/39/3B.
- (batch-2 fully fitted as of this commit)

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
