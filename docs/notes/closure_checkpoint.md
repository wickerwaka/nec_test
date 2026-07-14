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

## Golden-coverage audit + B0-B7/C6/C7 deadlock fix (2026-07-13, this session)

Bounded correctness pass. Fixed the two breadth-fuzz deadlocks, audited the
golden suite against docs/facts/instructions.json for ALL silently-omitted
documented forms, added them, reflashed once, and re-confirmed on hardware.

### AUDIT - every documented form NOT previously in the golden suite
Cross-checked emit_suite's OPCODES matrix (form granularity) vs the 288
instructions.json entries. Findings:

- **B0-B7 MOV reg8,imm8** - NO core dispatch -> DEADLOCK. FIXED + golden (B0).
- **C6/C7 MOV r/m,imm** (reg + mem) - NO core dispatch -> DEADLOCK. FIXED +
  golden (C6.0, C7.0).
- **24 ALU word/direction forms** (X1 rm16,r16 / X2 r8,rm8 / X3 r16,rm16 for
  all 8 of ADD/OR/ADC/SBB/AND/SUB/XOR/CMP: 01/02/03 ... 39/3A/3B). The core
  IMPLEMENTED these (Mission S, op_alu=(opc&C4)==0) but no golden tranche
  ever existed - the suite only had the rm8,r8 representative (00/08/../38).
  ADDED all 24; every one passed 500/500 cycle+arch with ZERO RTL change.
- DEFERRED / not added (documented, out of the bounded scope):
  * **INM/OUTM 6C-6F** (INS/OUTS string I/O) - no core dispatch (would
    deadlock). Needs IOR-data config + a string-port engine; the whole
    IN/OUT port area is excluded from the suite/fuzz. Not fuzz-reachable.
    DEFERRED to a dedicated I/O-string campaign.
  * **BUSLOCK F0** (LOCK prefix) - no core dispatch (would deadlock). Needs
    the BUSLOCK-pin behavior characterized. Not in suite/fuzz. DEFERRED.
  * **BRKEM 0F FF** - 8080-emulation entry; project policy parks it (needs
    the RETEM recovery path). DEFERRED.
  * **0x82** (ALU r/m,imm8, the 100000SW S=1/W=0 alias of 0x80) - latent
    deadlock on an UNDOCUMENTED alias, NOT reachable by gen_seq (only
    documented opcodes emitted). Parked per the standing undocumented-
    encoding policy (same class as FE/7, 8F mod3).
  * bare REP/REPC prefixes (F3/F2/65/64), HALT (F4), POLL (9B) - false
    positives: covered as composite/EVT forms, core handles them.

### RTL fixes (v30_eu.sv) - cadence laws
- **B0-B7**: new S_IMM8. Law: the byte-imm reg load inserts ONE extra idle
  cycle before the next opcode pops (S_NOP), unlike two-byte B8-BF which
  retire ON the imm-hi pop. Absorbed on a dry queue, visible on prefetched
  variants (the "~1 cycle off" the predecessor saw).
- **C6/C7 (op_movri)**: write-only store, imm popped after the modrm/disp
  (no operand read). C6 reg8 shares B0's one-idle tail; C7 reg16 retires on
  the imm-hi pop like B8. Mem: mod0 reg-EA latches in a single S_EA1 cycle
  (no read -> the extra S_EA2 read-setup cycle is skipped; imm pops at
  modrm-pop+2). Byte store: dly=1 -> S_RSV (reservation) -> S_REQ. Word
  store: reserves at the imm-hi pop and issues straight to S_REQ so the
  write is ready at that pop's T3 eval (an S_RSV lead-in put it one eval /
  two cycles late). **Byte-store data law**: the 16-bit internal value is
  the SIGN-EXTENDED imm8 - the unused byte lane on a byte write is
  {8{imm8[7]}} (00 for positive, FF for negative imm; measured on the C6.0
  goldens). Word store drives {imm_hi, imm_lo}.

### Results
- **Sim (Verilator, zero waits): 169000/169000 cycle- AND arch-exact**
  (155500 prior + 13500 new, 347 tranches). No regression; every new form
  passes. Committed (352fa85) before the reflash.
- **ONE reflash**: quartus compile 0 errors, timing MET (tightest setup
  slack +4.185 ns on the emu/core clock; holds all positive); safe_flash
  VERIFY ok, use_core=False, cfg 0x1ff0008.
- **Hardware A/B (zero waits)**: chip-vs-golden boot MATCH 400; core-vs-chip
  FIRST LIGHT MATCH 400; core-vs-golden MATCH 400. Direct chip-vs-core
  spot-check B0/C6.0/C7.0 = 6/6 each. **A/B sequence fuzz fz11000-11499
  500/500 clean** (zero divergence) now exercising the fixed forms
  (mov_imm8 x335, mov_ri_r x156, mov_ri_m x167 instances). gen_seq _gen_mov
  re-enabled B0-B7 and C6/C7.

### Still DEFERRED (unchanged, separately-scoped future campaigns)
- Wait-state timing generalization (waits>=1 across arbitrary sequences).
- Interrupt recognition/vectoring/INTA timing generalization in random
  contexts (fz10000-10499 was 476/500).
- The 3 cadence-marginal families: swint, farjmp, loop (execution correct,
  display cadence 1-2 off at ~3% of phases).
- INM/OUTM, BUSLOCK, BRKEM/8080-mode, 0x82 alias (audit finds above).

## Campaign 5 breadth-fuzz (2026-07-13, this session) — surprise hunt

Aggressively widened opcode/addressing/operand coverage of the A/B
sequence fuzz and ran high volume on the CURRENT bitstream (chip vs fabric
core, --hw-ab, waits=0, no interrupts) to hunt UNEXPECTED correctness bugs.
Board = root@mister-nec, NO reflash this session (find-only). >13000 A/B
seed-pairs run.

### Generator expansion (gen_seq.py, commit c221596)
Coverage-driven: cross-checked fuzz_cov's UNEXERCISED/opsig axes against
docs/facts/instructions.json and added every remaining SAFE documented form
the generator could not emit.
- **Addressing modes (_windowed_ea): the whole mod/rm/disp space** — was
  ONLY mod0/rm6 direct + mod3 register. Now register-indirect, based,
  indexed, BP-relative (SS-default), disp8/disp16, odd alignment, and
  segment-wrap (0xFFFF) reads, with the EA forced into the data window by
  pre-loading base/index regs (writes stay contained; reads may straddle).
- **_imm_biased**: operand boundary biasing (0/1/-1/0x8000/0x7FFF/byte
  carry+overflow edges) across ALU/MOV/shift/mul immediates.
- **14 new families**: earich (rich-EA ops + 0-3 stacked seg prefixes),
  unary (NOT/NEG F6-F7/2,3), incdec8 (FE/FF/0,1), testimm (A8/A9,F6-F7/0),
  xchgacc (91-97), pushimm (68/6A), pushapopa (60/61), flagops
  (F5/F8/F9/FA/FB/9E/9F), brnear (E9), inout (E4-E7/EC/EE/EF; 0xED avoided
  so no accidental CALLN/RETEM 8080-escape), sregmem (8C/8E), divbound
  (DIV at the quotient boundary, no trap), indirect (FF/2,4 near CALL/JMP
  reg). jcxz (E3) added to the base branch generator.

**Coverage before -> after**: 2500 -> 6000 A/B seeds; 153006 -> 365164
instrs; **50 forms (2 UNEXERCISED: jcxz, loop) -> 65 forms (0 UNEXERCISED)**;
**405 -> 465 opsigs** (154 distinct memory-operand signatures); prefix axis
now es/cs/ss/ds/rep/none.

### FINDINGS
1. **No functional/correctness bugs.** Every divergent seed (430+
   arch-checked, incl. all 368 from a 1500-seed run and all 62 from a
   2000-seed strict-set run) is ARCH-MATCH: identical architectural
   register output chip vs core. Zero deadlocks (after the tooling fix
   below), zero wrong results, zero wrong flags across all newly-exercised
   forms. High-confidence clean.

2. **TOOLING BUG FIXED — loop-family containment hang** (commit 19c649f).
   _gen_loop's bounded-iteration guarantee relied on LOOP decrementing CW
   from a small count, but the loop BODY drew its INC/DEC register from all
   8 regs — so it could emit INC CW on the counter, cancelling the LOOP's
   decrement -> infinite spin (both chip and core hang identically -> no
   done marker -> spurious "divergence"). ~9.5% of loop-only seeds. Fixed:
   body regs from {AW,DW,BW,BP,IX,IY} only. Hang rate 0/300 after. This
   was the sole containment defect; the 14 new families never escape.

3. **Cadence-generalization gaps at waits=0 (all ARCH-EXACT, resync to
   done) — a Mission-D-scale fit + reflash, DEFERRED.** These are the same
   class as the pre-documented swint/farjmp/loop cadence-marginals, now
   extended/quantified. Per-family divergence rate (250 isolated seeds):
   - **pushapopa / POP R (61): 102/250 (41%)** — the one prevalent NEW
     gap. Mechanism (NOP-phase sweep, fz20003/fz20011): POPA's 8-word read
     burst STARTS 2 cycles late on the core at some prefetch phases (the
     dispatch's existing `bus_phase ? S_61G : S_61W` 2-way split — pop+2 vs
     pop+3 — does not capture the full queue-fill-phase law). PUSH R (60) is
     clean at all phases. Reads/addresses/registers identical; done off by
     2. This is the highest-value RTL target: route S_61 read-start through
     the Mission-D q_fresh/queue-fill law instead of the single bus_phase
     bit, measure via the +eudbg matrix, then reflash.
   - **loop 8.4%, farjmp 3.2%, swint 1.2%** — pre-known deferred class.
   - Everything else NEW is 0-3% (earich itself 0/250) — the same ~0.4%
     background rate present even in shipped base families (callret/sregw/
     popf all 1/250). The low-rate contributors are reg-EA RMW store /
     stack-push / near-indirect-flush commit-phase (unary 6, pushimm 7,
     indirect 7, incdec8 4 per 250): the register-indirect/based/indexed EA
     store & reader commit phase (newly exercised by the addressing-mode
     expansion) is the Mission-D disp-law path not fully generalized to
     reg-EA. Exemplars fz60035/fz60249 (multi-row store/fetch shift),
     fz60221/fz30297 (single-cycle PS/parity status-bus display).

### Regression corpus (sw/testdata/fuzz_divergences.jsonl, now 18)
Added curated cadence exemplars: fz20003/fz20011 (POPA read-start,
--exts pushapopa), fz60249/fz60035/fz60221 (reg-EA store+fetch / single-row
PS, --exts <strict set>). Replay: check_seq <seed> --hw-ab --exts <...>.
Re-check after any commit-phase RTL fit.

### NEXT (recommended dedicated fit+reflash mini-campaign)
The POPA read-start law is the cleanest, most prevalent target. Fit it with
the +eudbg phase matrix (as Mission D did the disp laws), batch with the
reg-EA store/reader commit-phase generalization, rebuild, validate cycle-
exact at all phases + full golden 169000/169000, then safe_flash ONCE.

## Campaign 5 fit+reflash mini-campaign (2026-07-13, this session)

Closed the ranked waits=0 cycle-cadence commit-phase gaps from the
Campaign 5 breadth hunt. Board = root@mister-nec; ONE reflash this session
(the new full-RTL A/B bitstream, safe_flash'd, cfg 0x1ff0008, use_core=0,
VERIFY MAGIC ok). Three commit-phase fits landed, each golden-verified
169000/169000 cycle+arch-exact before the reflash. New phase-matrix tools:
sw/sweep_popa.py, sw/sweep_regea.py, sw/sweep_push.py (chip-vs-TB/-fabric
per-phase MEMR/MEMW anchor + the +eudbg bus_phase/bus_ts/q_fresh/eu_started
columns added to tb_v30_core).

### Fits (all cycle-exact after fix; golden held 169000/169000)
1. **POPA (61) read-start - the ~41% prize.** Measured law: the chip's POPA
   first stack read commits via the NATURAL BIU eval mechanism, cycle-
   identical to a plain POP r16 (S_REQ) at EVERY prefetch phase (proven by
   sweeping both: same MEMR T1 at all 12 phases). The old
   `bus_phase ? S_61G : S_61W` split forced a +1 lead-in on every odd-parity
   S_DEC, correct only when S_DEC lands on a fetch T4; at T2/Ti it read 1-2
   cycles late (d=+1/+2 at phases 1,5,6,11). Fix: dispatch straight to
   S_61W. Cycle-exact across 28 swept phases; seeds fz20003/fz20011 MATCH.
2. **reg-EA store commit-phase.** mod0 reg-indirect/based/indexed stores
   whose S_REQ ready lands on a fetch T4 (phases 2/8/14/20...) wrote 2 late:
   a 2nd prefetch slips ahead of the not-yet-armed write. Fix: a bare eu_req
   reservation in S_EA2 (NOT eu_soon - eu_soon would defer to the fetch's
   own T4, 2 cycles too early; the bare reservation blocks the 2nd fetch so
   the write commits at the following idle eval). All 4 store forms clean
   phases 0-23.
3. **PUSH imm16 (0x68) idle commit-phase.** PUSH r16/imm8/mem were clean;
   only 0x68's `bus_phase ? S_REQ : S_PUSH_CALC` split diverged (+1 at ph
   4/10). A phase-0 imm pop in a bus-idle window (ts=0) has no fetch for
   S_PUSH_CALC to block - the extra calc cycle wrote late. Fix: commit pop+1
   when `bus_phase || bus_ts==0`. All PUSH forms clean 0-15; resolves
   fz60035 (that seed's push was a 0x68).

### Verification
- Golden (Verilator, zero waits): 169000/169000 cycle+arch after each fit.
- ONE reflash: quartus 0 errors, timing MET (setup slack +4.924 ns, all
  hold/recovery/removal/pulse positive); safe_flash VERIFY ok.
- **Deterministic core gate - chip vs Verilator TB (the ground truth):
  1500/1500 clean.** fz71000-71499 500/500 (the exact set the hw-ab gate
  ran, incl. all 23 hw-ab-flagged seeds) PLUS a fresh fz72000-72999
  **1000/1000, zero divergent seeds**. POPA (pushapopa) exercised
  throughout with 0 real divergences. This satisfies the >=1000-seed
  clean-run criterion for core correctness.
- **In-silicon A/B (chip use_core=0 vs fabric core use_core=1),
  fz71000-71499: 477/500 raw clean.** The 23 flagged seeds are NOT core
  divergences: ALL 23 MATCH chip-vs-TB. Since the TB and the fabric core
  are the same RTL, any divergence on a defined signal (T-state, active bus
  status, real transaction addr/data) would show in both; none do.

### STRETCH characterized: the hw-ab background is a fabric-synth-vs-chip
### floor, NOT a fittable core law.
The residual hw-ab-only divergences are two inert artifact classes, both
confirmed absent from the deterministic TB (chip-vs-TB 500/500):
- **Passive-cycle bus-float (deterministic).** During a bus-idle (Ti,
  bs=PASV) stretch the fabric core drives its internal prefetch address on
  AD (e.g. 29090/9090) while the chip AND the TB float-retain the last real
  value (e.g. 2ff7a/ff7a). Architecturally inert (passive = no transaction;
  T-state/status/qs/ps all match). Same don't-care class as the documented
  8F.0 ghost-read and INTA-T1 float-retained address. An undefined AD value
  that resolves differently in synth vs sim - no core-logic law to fit.
- **Capture-alignment transients (the "11-row" signature).** A fixed ~11-
  row window where a store/fetch appears reordered then resyncs; present in
  hw-ab, absent in the deterministic TB. A serve-harness A/B capture-start
  effect between the two consecutive board captures, not a core timing
  difference (the same image on the TB is cycle-identical to the chip).
Neither is a commit-phase law; both are documented floors, resolved the
same way as 8F.0 (comparison-level don't-care), NOT an RTL/reflash change.

### Still DEFERRED (unchanged, separately-scoped future campaigns)
- waits>=1 generalization across arbitrary sequences (Mission-H-scale).
- interrupt recognition/vectoring/INTA timing in random contexts.
- loop doomed-prefetch (chip issues one speculative fetch during the
  backward-branch flush the core does not model - a flush-MODELING gap, a
  different law than commit-phase; fz7207. fz7203 incidentally now MATCHes).
  farjmp post-flush cadence, swint vectoring - same deferred flush class.
- reg-EA READER idle-window +1: the mod0 reg-EA reader commits 1 cycle late
  when its whole 2-cycle EA compute (S_EA1->S_EA2->S_REQ) falls in bus idle
  (no in-flight fetch for eu_soon's T4-defer). Rare in dense code; a clean
  fix needs restructuring the EA-addr settle, risking the reader-heavy
  suite - characterized, not forced.
- fz60249: RESOLVED as the inert chip-vs-FABRIC floor, NOT a chip-vs-TB
  divergence (see the fz60249 STEP-0 section below). No RTL change, no
  reflash.
- INM/OUTM 6C-6F, BUSLOCK F0, BRKEM/8080-mode, 0x82 alias.

## fz60249 reg-EA store/fetch reorder — STEP-0 verdict: INERT FLOOR (2026-07-13)

Dedicated pass to fit "fz60249 / reg-EA STORE-FETCH REORDER". STEP 0
(reproduce + confirm it is a REAL deterministic chip-vs-TB divergence, not
merely the chip-vs-fabric floor) DISPROVED the divergence. NO RTL change,
NO reflash. HEAD 8998f8e; board root@mister-nec, echo-verified; single
writer; nothing flashed.

### Measured facts (all reproducible)
- **chip-vs-TB (deterministic, HEAD): MATCH.** fz60249 (94 ins, full strict
  ext set) compared clean 3x, 1324 rows, incl. --strict-qs (the 3 old
  QS-flickers are gone too). bad=0.
- **chip-vs-TB at commit 1358b3b (the EXACT commit where fz60249 was
  recorded as an 875-row chip-vs-TB divergence, corpus first_row 371):
  rebuilt that RTL's Verilator TB in an isolated worktree, re-ran vs the
  chip TODAY -> MATCH, 1324 rows.** gen_seq is unchanged since c221596
  (before 1358b3b), so the seed emits the identical program. Since the TB
  is deterministic given RTL, and BOTH the current AND the recording-commit
  RTL match the chip today, the ONLY variable vs the old 875-row record is
  the CHIP capture. => the recorded chip-vs-TB divergence was a chip-side
  capture-alignment transient, not a model/transaction-order divergence.
- **chip-vs-FABRIC (hw-ab, HEAD): DIVERGE@371, 875 rows, 3 flickers** -
  reproduces the corpus signature EXACTLY. Rows 371-380: a MEMW (reg-EA
  store, addr 02996) and the adjacent CODE prefetch issue ~2 cycles shifted
  in the fabric bitstream vs the chip, cascading to the done marker. This
  is the documented synth-vs-chip floor: the fabric bitstream (synthesized
  ~1358b3b) diverges from the chip on a store/fetch boundary in a way the
  TB (same RTL) does NOT - so it is a synthesis artifact, not a core-logic
  law. Reflashing would reproduce the same synth-vs-sim gap (RTL identical);
  same don't-care class as 8F.0 ghost-read and the passive-bus-float floor.

### Verdict
fz60249 is the INERT chip-vs-fabric floor. The RTL model reproduces the
chip cycle-exactly on this seed. The corpus's hw_ab:false (chip-vs-TB)
entries for fz60249 were chip-capture transients that do not reproduce
across 4 fresh chip captures (3 at HEAD + 1 at 1358b3b), all MATCH.

### reg-EA STORE cadence class is already cycle-exact chip-vs-TB
sweep_regea.py --tb, all 12 prefetch phases: st_bx/st_bxsi/st_si/st8_bx =
0 divergent (the 848250b S_EA2 bare-eu_req reservation baseline holds at
every phase). Fresh deterministic gate fz73000-73039 (full strict ext set,
reg-EA stores heavily exercised via earich/indirect/addressing-mode
expansion): **40/40 chip-vs-TB clean** (on top of the predecessor's
fz72000-72999 1000/1000). Nothing to fit for the store class.

### reg-EA READER idle-window +1 — still deferred (unchanged)
sweep_regea.py --tb still shows the one documented chip-vs-TB reader
residual: rd_bx / rd_bxsi at phase 7 read +1 late (d=+1). This is the
separately-scoped reg-EA-reader idle-window case (needs an EA-addr-settle
restructure that risks the reader-heavy suite) - LEFT DEFERRED per scope,
NOT folded into this pass. It is orthogonal to fz60249 (which is
fabric-only; this reader case is a genuine but rare chip-vs-TB residual).
