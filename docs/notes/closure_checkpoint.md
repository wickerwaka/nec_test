# Campaign 3 closure block — final checkpoint

Closure block complete (2026-07-13). Board = root@mister-nec (health:
`python3 sw/v30run.py echo`; last verified this date). NEVER reprogram
the FPGA; one board user at a time. No background chains are running.
Serve v2 (delta/partial-capture) is DEPLOYED and validated (31 ms/case).

## GRAND REGRESSION (311 forms x 500/200, zero waits)

TOTAL: 155500/155500 cycle-exact (100.0%); arch 155500/155500 (100.0%).
Wait-state suites (v0.1-w1, v0.1-w3): 1200/1200 each.
(Was 155440/155500; the final 60 = 8F.0 mod3, RESOLVED below 2026-07-13.)

All 311 forms are now 100% cycle- AND state-exact.

### 8F.0 mod3 ghost-read address — RESOLVED (2026-07-13, don't-care)

The last 60 residual cases (33 pf mod3 + 27 cold-pop@4 mod3) were the
undocumented 8F /0 mod3 register-destination POP alias (8F C0-C7, e.g.
8F C7 = "POP IY"). Closed as a documented golden-schema DON'T-CARE after
walking the resolution ladder to rung 3 (history-dependent latch state);
NO RTL change, NO reflash (the bitstream stands - only the golden
schema/comparison changed).

Evidence chain:
1. **Diff table (all 60)**: the ONLY mismatch is the committed ADDRESS
   (bus col) + read data (col 6) on the single MEMR row of the window
   (pf: row 5; cold-pop@4: row 8). In all 60 the core drives exactly
   SS:SP; the chip drives some other value (no (seg<<4)+reg+const
   formula fits - reconfirmed).
2. **The read is architecturally inert.** Across ALL 130 mod3 cases in
   the suite the destination register is NEVER written - 8F /0 mod3 only
   does SP += 2 and issues one stack read whose word is DISCARDED. So the
   read's address/data have zero architectural effect (that is why arch
   was already 500/500).
3. **Ladder rung 2 (nondeterminism) - RULED OUT.** Re-ran 8 of the 60 on
   the socketed chip (use_core=0), N=4 each: the ghost address is STABLE
   run-to-run (deterministic silicon behavior, not an uninitialised-latch
   coin-flip). Tooling: sw/rerun_ghost.py. 5/6 sampled reproduced the
   golden address exactly; 1 (idx 5) reproduced a stable-but-different
   value - i.e. it depends on pre-window history, not the injected state.
4. **Ladder rung 3 (history dependence) - CONFIRMED.** (a) A per-register
   load-routine mutation sweep on idx 25: perturbing ax/cx/dx/bp/si/di/
   ds/es leaves the ghost UNCHANGED; only PS/CS (which reshapes the fetch
   stream / queue alignment) moves it. So it is not a function of the
   architectural operands. (b) The ghost value appears in the full
   capture ONLY as that MEMR itself (txn 39), i.e. it is stale internal
   EA/address-latch state, not a copy of an earlier real bus cycle.
5. **Ladder rung 4 (RTL) - NOT satisfiable.** The address is
   pre-window microarchitectural latch state set by the harness injection
   stub (load routine + 63 C0 preload + prefetch stream). A
   backdoor-injected core never executes that stub, so it has no such
   history and legitimately drives the modeled SS:SP. This is a
   golden(stub-injected chip) vs replay(backdoor core) injection-mechanism
   artifact, not a core defect - and there is no modelable deterministic
   law tying the stale value to anything the core can reproduce.

Resolution applied: address (bus col) + data (col 6) on the 8F /0 mod3
MEMR row are a documented don't-care. Implemented in
sw/check_core.py dontcare_cells() (gated tightly on 8F + mod3; the
mem-operand forms mod 0/1/2 keep full address comparison), documented in
tests/v30/v0.1/metadata.json (8F.0 dont_care field + a top-level note)
and sw/emit_suite.py (8F.0 spec comment). Golden data files are
UNCHANGED (the chip's address stays recorded, just flagged).

Result: 8F.0 500/500 (cycles 500, arch 500); grand regression
155500/155500 cycles + 155500/155500 arch; w1/w3 still 1200/1200 each.

## Closure-block results (this session, commits 793c61a..HEAD)

- **INS/EXT (0F 31/33/39/3B) implemented**: all four forms 500/500.
  Full semantics + timing laws in the v30_eu.sv decode comment
  (op_insext) and state comments: offset-reg-update-before-source
  aliasing, EXT AL/AH-offset degenerate modes incl. the 256*len
  runaway, flags from s=off+len, the split-access chain laws, and
  0F39's mid-flow imm pop (mrm+6 / read-done+4+off).
- **0F22/0F26 (SUB4S/CMP4S) resolved**: 500/500 each. High-adjust
  fires additionally at dec==9 with an invalid low nibble gated on
  !c1 (pre-adjust >99h DAS threshold); SUB4S driven sibling =
  dst_o - src_o - braw - badj + 1 (byte-boundary borrows of the raw
  subtract and the -6/-60h adjust step).
- **FF.2/FF.6 resolved**: 500/500 each. The parked "carried-phase
  artifact" was an aliased fit - the reg-form push slot is a constant
  ready=pop+4 (no bus_phase term).
- **8F.0 reservation laws fixed** (440/500, arch 500/500): mod3 ghost
  pop reserves from pop+1 with ready at the pop-phase slot; the mem
  mod0 form does NOT reserve during EA compute. Remaining 60 = the
  address residual above.
- **C8 PREPARE resolved**: 500/500. level 0 retires at
  max(level-pop+4, push done); level>=2's first pointer-copy read is
  ready at level-pop+7 (address staged in the preceding wait cycle)
  behind a one-cycle reservation at level-pop+6. The suspected
  T4-end-eval BIU rule is NOT needed - no BIU change landed.
- POP-PSW boundary race and REP-abort flush slot: resolved by the
  predecessor (see interrupt_model.md); confirmed in this grand
  regression (INT.9D / INT.F3AA 200/200).

## Board / pipeline state

- All tranches (batches 1-3 + addenda) LANDED in tests/v30/v0.1
  (ground truth). No emissions pending. Board echo-verified, no jobs.
- sw/v30ctl.py on-board = serve v2 ("OK SERVE v2" banner).

## Notes for the next agent (Mission S was reassigned)

- Mission S (sequence fuzz, sw/gen_seq.py + sw/check_seq.py) was
  reassigned by the coordinator and NOT run in this block. The fuzz
  generator must respect: forbidden opcodes (0F >= 40h / 0F 34), and
  should be aware that EXT with offset reg AH and len<16 burns
  256*len cycles (case timeouts), and that INS/EXT mem-mod (mod!=3)
  encodings are PARKED (S_HALT) in the core - exclude them from
  sequences until characterized on silicon.
- Untested extrapolations (no tranche coverage, flagged in-code):
  0F31 (reg-len INS) with off=0 AND len=16 - implemented as
  read+write-at-41 (the reg-form s=16 path), but 0F39 measurements
  show a no-read lone write for the imm form; silicon likely skips
  the read for the reg form too. One targeted board measurement
  would settle it.
- Fit-loop recipe unchanged: `python3 sw/check_core.py --opcodes X
  --keep`, diff via build_rows_sim/diff_rows, adjust dly constants,
  rebuild, rescore; commit per family; keep neighbors green.
- Infrastructure notes (defer_t4/bus_phase/flush_fast etc.) unchanged
  from the predecessor block - see git history of this file.

## Mission S — sequence fuzz (2026-07-13, this session)

Pipeline validated end-to-end (sw/gen_seq.py + sw/check_seq.py): sim-only
plumbing OK, board side newly exercised and working. Ran ~110 random
sequence seeds (10-99 ins) + ~150 isolated single/paired repros on the
real board. THREE divergence classes found and FIXED (committed, each
with the full 155440/155500 golden regression re-verified unchanged):

1. **ALU r/m word + direction forms (24 opcodes) - UNIMPLEMENTED**
   (commit 84a7d2b). op_alu was (opc&C7)==0 -> only rm8,r8 (00,08,..,38).
   The word (rm16,r16) and both direction-reversed forms (r8,rm8 /
   r16,rm16) for all 8 ops parked S_HALT and deadlocked the BIU. The
   golden suite only ever had "ALU rm8,r8 x8" so the gap was invisible.
   Fix: op_alu=(opc&C4)==0; direction-aware operands (opc[1]); width via
   new ex_alu16; d=0 mem->S_RMWX (word path), d=1 mem->S_LD_W1/W2 load-op,
   CMP->flags. All 64 new forms verified cycle-exact vs chip.

2. **PUSH reservation phase** (commit 159fc51). PUSH r16 whose
   S_PUSH_CALC cycle lands on a prefetch T3 eval let the prefetch steal
   the slot -> stack write 2 cycles late. Fix: assert eu_req (reservation)
   in S_PUSH_CALC. Pre-existing; golden injection phase never hit it.

3. **reg-EA reader commit-at-T4** (commit 3142e97). A mod0 register-EA
   reader (ALU RMW / MOV load) whose read becomes ready (S_REQ) on a
   prefetch T4 missed that fetch's T3 eval and read 2 cycles late. The
   chip commits back-to-back off the T4. Fix: assert eu_soon in S_EA2
   (the BIU defer_t4 path then commits at T4). Clean, no regression.

### OPEN — gate NOT reached. Remaining taxonomy (measured fz100-139,
23/40 divergent with the 3 fixes in place = 42.5% clean):

- **timing-shift (16/23, DOMINANT): disp8/disp16 reader commit-phase.**
  A disp-form reader whose read becomes ready EXACTLY on a prefetch T3
  commits there on the core (want_eu) but the chip DEFERS ~2 cycles
  (fetch completes + push absorb, read at the 2nd following Ti). Strongly
  phase- and segment-prefix-dependent: no-prefix disp16 matches at ALL
  phases 0-7; 3e:disp16 and 3e:mod1-disp8 diverge; even no-prefix reg-EA
  diverged at the 2NOP phase before fix 3. NOT the same direction as the
  reg-EA case (that read LATE; disp reads EARLY), so eu_soon does NOT
  apply - tried eu_soon at S_DHI/S_DISP8: regressed 30 to 396/500.
  Tried gating the T3-eval EU commit on ext_ok (registered readiness,
  mirroring the eval_ext rule): regressed goldens to 2071/3000 - the
  exact deferral (how many Ti before the read) is a multi-phase fit
  entangled with push-absorb/q_aged that needs real A/B measurement, not
  a blind BIU edit. This is the gate blocker.
- **qs-flicker (6/23, minor): QS pin (F/S) 1-cycle display flicker**,
  self-correcting - both chip and core reach done at the SAME cycle;
  only the queue-status pin momentarily disagrees (odd-fetch-after-branch
  regions). Cosmetic-ish but counts as a divergence.
- **generator escape (1/23, TOOLING not core): fz101 ran wild into
  0x99xxx on BOTH chip and core** (done=None both). gen_seq's safety
  constraints (forward-bounded branches, no CALL/RET) do NOT fully
  contain control flow - a program escaped its window into uninitialized
  memory and executed garbage. Tighten gen_seq containment (or filter
  escaped seeds) before counting these against the core.

### For the next agent / Campaign 4
- The dominant blocker (disp reader T3-defer) is the right first target
  for the in-FPGA A/B harness: run identical images on core+silicon,
  sweep the reader's ready phase against the prefetch grid, and measure
  the exact deferred-Ti count per (EA-mode, prefix, queue-fill). That
  gives the law directly instead of guessing dly/commit gates.
- Repro recipe: sw/check_seq.py SEED for a full seed; for isolation use
  the /tmp repro pattern (compose a short instr with N leading NOPs to
  sweep bus phase, diff via check_seq.diff). A temporary EU/BIU state
  dump gated on +eudbg in tb_v30_core's bootimg loop (see this session's
  git history if re-adding) trivializes phase debugging.
- The 3 fixes are orthogonal and safe; the ALU-forms fix in particular
  closes a real 24-opcode functional gap (not just timing).

## Campaign 4 Mission D — the disp commit-phase laws (2026-07-13, RESOLVED)

The Mission S blocker is retired. Measured via sw/sweep_dispphase.py (the
(EA-mode x prefix x queue-fill-phase x waits) micro-sequence matrix, chip
via serve vs core via TB, with the new +eudbg per-cycle EU/BIU state dump
in tb_v30_core):

**Reader law (the 16/23 class):** the FINAL displacement pop (S_DISP8 /
S_DHI) defers exactly one cycle iff (a) the queue-head byte became
poppable THIS cycle (head was dry the cycle before - a freshly-landed
fetch word), and (b) that cycle is an in-flight fetch's T2 (the next
fetch started back-to-back). The 2-cycle read shift the fuzz saw is
mechanical: the deferred pop's read misses the prefetch T3 eval and waits
through idle-entry. The disp16 LOW pop (S_DLO) is never blocked and
re-polls a dry queue EVERY cycle - the old "2-cycle dry-retry grain" was
an aliased fit of block+availability. Implemented as q_fresh (BIU export)
gating pop_want. Discovery: 3 law iterations against the 96-cell matrix
(pure-T2 block -2/+14; avl<3 gate -6; fresh-head gate 96/96).

**Store law (found by the resumed fuzz, fz151):** the disp16 store's
write is ready at hi-pop+2 (dly=1), same as the disp8 store schedule.
The old rdy@hi+3 ("d2 stores rdy @ 7") was a phase-aliased golden fit -
at the fz151 phase the chip's write catches a T3 eval at hi+2 that the
core missed. 72-cell store matrix (st8/st16/st8bx): 0 divergent after
the fix; disp8 stores were already correct.

Verification: 168/168 matrix cells (4 reader + 3 store EA modes x 3
prefixes x 8 phases, waits=0); at waits=1 the disp-reader matches in all
96 reader cells; full golden regression 155440/155500 (exact baseline);
fz100-139: 40/40 MATCH (was ~42% clean).

**New (pre-existing) class, LOW priority:** at waits=1, a qs_e
flush-display timing artifact at the store stub's far jump (chip shows
QS=E one row earlier than the core in phase-parity-dependent cells;
2 rows per affected trace, execution identical). Not covered by the
golden windows (they close before the stub). Untouched by the disp laws.

## Campaign 3 EXIT GATE — SATISFIED (2026-07-13)

500/500 consecutive sequence-fuzz seeds clean (fz600-fz1099, fresh seeds,
all post-fix laws in): zero divergence, zero QS flickers, on the real
board via the serve pipeline vs the Verilator TB. Two additional laws
found and fixed on the way to the gate (beyond the disp-reader class):
disp16 store-ready @ hi+2 (fz151) and the split-access segment wrap
(fz494, a REAL functional bug - second byte of a word access at offset
FFFFh must wrap to offset 0 of the same segment). Full history: fz100-139
40/40 after the reader law; fz140-493 clean; fz494 wrap; fz600-1099
500/500. Generator expansions (callret/sregw/popf) re-gating separately.

## fz2263 (popf-ext gate run) — undocumented-encoding park, NOT timing

fz2263 (exts=callret,sregw,popf; the seed's program contains only a
callret gadget) wanders into deterministic-but-skewed execution (both
chip and core agree bit-for-bit: same XOR AX,E705, same DEC byte
[BP+DI+disp16] RMW at 001e5) until the stream reaches FE /7 - an
UNDOCUMENTED group-FE encoding. The core parks (S_HALT) by the standing
Campaign 3 policy; the chip executes it and continues. Classified into
the existing "undocumented encodings parked pending characterization"
residual - the fix is to characterize/implement undocumented grp-FE
(and friends) on silicon, not a containment or timing change. Repro:
check_seq fz2263 --exts callret,sregw,popf; eudbg shows the park at the
FE/7 modrm pop.

## Mission E expansion gates — ALL PASSED (2026-07-13)

base 500/500 (fz600-1099) | callret 500/500 (fz1100-1599) |
callret+sregw 500/500 (fz1600-2099) | callret+sregw+popf 500/500
(fz2264-2763). Single non-clean seed across all runs: fz2263, classified
above (undocumented FE /7 park - the pre-existing residual, not timing).
Next expansion candidates (still excluded): IN/OUT in sequences, REP
randomization, far CALL/RET, undocumented encodings (need silicon
characterization first), 8080-mode.

## Campaign 4 Mission C — synthesis + IN-SILICON FIRST LIGHT (2026-07-13)

Board = root@mister-nec, now on the NEW full-RTL A/B bitstream
(hdl/output_files/nec_test.sof, safe_flash'd; cfg 0x1ff0008). Health via
`python3 sw/v30run.py echo`. Single writer.

**Synthesis anti-pattern #2 fixed (commit e7c315a).** After the iterative
divider (c2beb6a), quartus_map was still slow: the 255-deep combinational
`shrot` shift/rotate unroll (D0-D3/C0/C1, all 8 sub-ops) was the second
giant cone. Replaced with one iterative shift stage (divider pattern):
loaded at dispatch, one single-bit shift per clock through the existing
S_SHWAIT/S_WAITX window, result+flags into sh_res/sh_fl before S_EX/
S_RMWX. All shift semantics/flag laws preserved bit-for-bit. Golden
155440/155500 (per-op byte-identical to baseline); shifts 13000/13000;
mem operand loads from eu_rdata (mem_op NBA not yet visible at read-done).
Audit: the 255 shifter was the ONLY large combinational unroll (INS/EXT,
ROL4/ROR4, 4S are burn-counter sequential machines).

**Build (Task 2).** Analysis&Synthesis (quartus_map) 00:03:47 (was
~25 min); Fitter 00:03:57; total 00:08:01. Megafunctions: 2 lpm_divide,
BOTH the small 8-bit AAM (D4/CVTBD) - no wide/group dividers, no giant
cones. Fmax 84.82 MHz emu/core clock, setup slack +9.151 ns (timing met);
9,835/41,910 ALMs (23%), 5079 regs, 13 DSP; 0 errors.

**First light (Task 3).** check_ab_hw.py all 800: chip-vs-golden MATCH/800
(known-good chip path undisturbed); **core-vs-chip MATCH/800 (the
in-fabric core matches the socketed part in real silicon)**; core-vs-gold
MATCH/800. In-silicon A/B sequence fuzz (check_seq --hw-ab, chip vs
fabric core both on the FPGA): **fz4000-4539 540/540 clean, zero
divergence** - confirms the Mission D disp/split laws in silicon and
**SATISFIES the Campaign 4 A/B done-criterion (>=500 zero-divergence,
fz4040-4539 500/500)**. The core is cycle-for-cycle indistinguishable
from the chip across the fuzz corpus in real silicon.

Residuals: 8F.0 ghost-read address RESOLVED 2026-07-13 (documented
golden-schema don't-care; grand regression now 155500/155500 - see the
"8F.0 mod3 ghost-read address" section at the top of this file);
undocumented encodings parked (FE/7 etc.); waits>=1 qs_e flush-display
artifact at far jumps (execution identical).

## Campaign 4 breadth expansion (2026-07-13, this session)

Widened the in-silicon A/B fuzz corpus per ROADMAP Campaign 4 priorities
1-2. Board = root@mister-nec, unchanged post-CE bitstream (NO reflash this
session). Two tools + generator work; two REAL core bugs found.

### Priority 1 - coverage tracking (DONE, commit 18d9ec6)
sw/fuzz_cov.py: 5-axis coverage accumulator (form / opsig / prefix / qfill
/ waits) persisted to sw/testdata/fuzz_coverage.json; --cov-report renders
it and flags UNEXERCISED/undersampled corners. gen_seq tags each gadget
(forms) and exposes per-instruction bytes; check_seq accumulates + persists
a divergence-seed corpus (sw/testdata/fuzz_divergences.jsonl). Base A/B
re-gate fz6000-6499 500/500.

### Priority 2 - instruction-family expansion (generator)
Added the remaining SAFE families to gen_seq EXT_MENU, grouped per roadmap
(a)-(f): bitops (0F 10-1F), rol4 (0F 28/2A), bcd4s (0F 20/22/26), insext
(0F 31/33/39/3B reg-form), adjust (27/2F/37/3F/D4/D5/98/99), ldsxlat
(D7/C4/C5), muls (F6/F7 /4-5, 69/6B), shifts (D0-D3/C0/C1 all 8 sub-ops),
pushpopm (FF/6, 8F/0, PUSH/POP sreg), prepare (C8/C9), bound (62), farcall
(9A+RETF), swint (CC/CD/CE via a composed IVT+IRET handler), farjmp (EA),
loop (E0-E3). Gadgets are self-containing (windowed pointers, bounded
counts, IVT handler for INT/BOUND, SP re-window for PREPARE).

**GATE: fz9000-9499 500/500 zero-divergence in silicon** on the
strictly-cycle-exact set: callret, sregw, popf, bitops, rol4, bcd4s,
insext, adjust, ldsxlat, muls, shifts, pushpopm, prepare, bound, farcall.
Coverage after: 1500 A/B seeds, 91430 instrs, 47 forms, 395 opsigs, qfill
q0-q6.

### TWO REAL CORE BUGS FOUND (unimplemented instructions -> HANG)
Both are ubiquitous instructions ABSENT from the golden 155500 suite (never
tested), so invisible until the fuzz emitted them. Both DEADLOCK the core
(TB and fabric): the decode falls through with no dispatch case.

1. **B0-B7 (MOV reg8, imm8)** - `opc[7:3]==5'b10110` has no case in the
   v30_eu no-modrm dispatch (only B8-BF `10111` -> S_IMM_LO exists). Minimal
   repro: `MOV BL,3` alone hangs; chip completes. Every earlier "shift/4S/
   insext hang" was collateral (those gadgets set CL/reg8 via B0-B7).
2. **C6/C7 (MOV rm8/rm16, imm8/imm16)** - reg AND mem forms hang. Minimal
   repro: `C7 06 00 21 34 12` (MOV word[2100],0x1234) hangs; chip completes.
   Was collateral for LES/LDS/BOUND (C7-built pointer/bounds).

**Proven fix direction for B0-B7** (implemented + reverted this session to
keep tree==flashed): add S_IMM8 (mirror of S_IMM_HI, one imm byte ->
wr_reg8, retire on the pop edge) + dispatch case `opc[7:3]==5'b10110`. It
is FUNCTIONALLY correct and golden-NEUTRAL (rebuilt TB ran 155500/155500),
and cycle-exact at flush-aligned phases, BUT the opcode-pop-after-retire
cadence is ~1 cycle off at queued phases (the fresh-head/T2 defer guard did
NOT fix it) - needs a Mission-D-style commit-phase fit before reflashing.
C6/C7 is a larger similar job (modrm + EA + imm-pop + mem-write timing).
These are the recommended next dedicated fit+reflash mini-campaign. Repro
harness: compose a 2-3 byte image, diff run_chip(use_core=False) vs
run_tb (chip-vs-TB) via check_seq.diff (all in this session's git history).

### THREE characterized cadence-marginal families (NOT gated; execution
correct, done-cycle within 1-2, prefetch/flush/vectoring DISPLAY cadence
off at ~3% of phases - same class as the documented far-jump qs_e artifact):
- **swint** (software-INT vectoring): the IVT-read/push/handler-fetch
  commit is 1-2 cycles off vs the chip at some queue phases (CC/CD/CE are
  not in the golden). Corpus: fz8007, fz8032.
- **farjmp** (EA far jump): post-flush prefetch cadence 1 cycle off at some
  phases (the zero-wait analogue of the known waits>=1 far-jump artifact).
  Corpus: fz8304.
- **loop** (E0-E2 taken backward): the chip issues one doomed speculative
  prefetch during the backward-branch flush that the core does not model;
  discarded, execution + done-cycle IDENTICAL. Corpus: fz7203, fz7207.
All three need the same commit-phase RTL fit + reflash to gate strictly.

### Priority 3 - interrupt injection (DONE infra + characterized finding)
check_seq --inject-int fires a seeded INT (IE=1) or NMI mid-sequence on
BOTH A/B positions via the pin-event scheduler, with far_int_support's IVT
+ IRET handler (vectors 2/3/4/0x20/0xFF -> 0x0480) so delivery returns
cleanly and the sequence continues. Added a documented differ don't-care:
the INTA-cycle T1 address (bs=INTA) is float-retained/history-dependent
(interrupt_model.md) and architecturally inert - the chip retains the
prior fetch addr, the core drives its modeled vector pointer; masked like
the 8F.0 ghost-read. With that, injection on the base corpus is clean.
GATE (inject + clean exts, fz10000-10499): 476/500. The 24 divergences are
interrupt RECOGNITION / VECTORING / INTA-ARBITRATION timing in RANDOM
contexts (NMI IVT-read commit, INTA-vs-CODE recognition-point, doomed-
prefetch during the INT flush) - the fitted interrupt laws (fitted on
NOP-sled geometries, INT.* tranches) do not fully generalize; 1-2 cycle,
execution otherwise correct. Corpus: fz10041 (NMI), fz10059 (INTA recog),
fz10055 (prefetch). Needs a deeper interrupt-timing fit + reflash.

### Priority 4 - wait-state variation (characterized, NOT gated)
check_seq --waits N / --waits-sweep threads waits through the A/B path.
The ENTIRE fuzz corpus (base AND expanded) diverges at waits>=1: real
mid-program timing divergences (done delta +-1, hundreds of rows, first
divergence well before the store stub). The wait-state deferred-completion-
eval laws (biu_model mission H) were fitted only for a handful of single
forms (B8/8B/89/F7.6/EB/E8) and do NOT hold across arbitrary multi-
instruction sequences. This is a Mission-H-scale wait-state RTL fit +
reflash - out of this session's safe (no-reflash) scope. Corpus: fz9700
(waits=1). The zero-wait path remains the verified one.

### Priorities 5-6 (IN/OUT, deeper/prefixes) - NOT reached
IN/OUT still excluded (needs port-config wiring into the fuzz). Deeper/
stacked-prefix sequences deferred.

### Regression corpus (sw/testdata/fuzz_divergences.jsonl)
9 curated representative divergence-triggering seeds, one/two per class
(swint/farjmp cadence, loop doomed-prefetch, inject recognition/vectoring,
waits-sequence). Replay: check_seq <seed> --hw-ab [--inject-int|--waits N]
--exts <...>. Re-check these after any interrupt/wait/flush RTL fit.
