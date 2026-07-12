# Empirical measurements from the real μPD70116C-8

Facts measured on the harness, with provenance to capture files
(sw/testdata/) and harness conditions. These are the ground truth the
documentation claims get checked against. Conventions: CPU clock = 4 MHz
(cfg_clk_div=8), zero wait states, small-scale mode, boot image from
sw/make_boot.py unless stated.

## Reset behavior (small mode)

- **Reset release → first bus cycle: 8 CPU clocks** (ASTB of the FFFF0h
  fetch; the pins transition from float to driven-idle during those
  cycles). First data transfer completes 3 clocks later.
  - Source: `smallmode_boot_sticky.hex` (2026-07-11), reset released at
    record 33, first T1 at record 41.
  - Caveat: sampling offsets not yet calibrated to ±1 clock; datasheet
    says nothing to compare against (measured value, not documented).
- First fetch address is FFFF0h, word access (UBE̅ low, even address).

## Bus cycle shape (small mode, zero waits)

- **Every observed bus cycle is 4 CPU clocks** (T1-T4, no idle between
  back-to-back cycles during straight-line prefetch).
- Word fetches march at 4-clock intervals during pure prefetch: bus
  bandwidth-limited fetch rate = 2 bytes / 4 clocks.

## Prefetch (small mode — no queue status visible)

- After the reset-vector fetch at FFFF0h, the BIU fetched FFFF2, FFFF4,
  FFFF6 (8 bytes total) before the far jump redirected it — i.e. it
  overshot a 5-byte instruction by 3 bytes while the EU decoded.
- Before the backwards short jump in the boot loop (JMP at 0010F/0110),
  prefetch reached 00112 — 2 bytes beyond the jump's last byte.
- Queue depth/refill policy not measurable without QS (large mode).

## Odd-address word access (small mode)

- `MOV AW,[2001h]` (odd word read) executes as **two byte bus cycles**:
  MEMR @02001 (upper lane, UBE̅=0, A0=1) then MEMR @02002 (lower lane,
  UBE̅=1, A0=0), 4 clocks each. Matches the documented split-access rule
  (User's Manual p98 table).

## Instruction-sequence timing (small mode)

- The boot loop (MOV AW,imm; MOV BW,imm — first iteration only —
  then per iteration: MOV [BW],AW; MOV AL,[2000h]; MOV AW,[2001h]; NOP;
  JMP short back) runs at **64 CPU clocks per iteration**, comprising 14
  bus transactions (11 fetch, 3 data).
  - Source: `smallmode_boot_sticky.hex`, loop analysis by
    sw/analyze_capture.py --loops.
  - Not yet decomposed into per-instruction times (needs queue
    visibility or single-instruction tests).

## Large (max) mode — first queue-status measurements (2026-07-11, post RQ/AK rework)

Source: `sw/testdata/largemode_boot_real.hex` (boot image, 4 MHz, zero waits,
max mode via CFG.small_mode=0 → S/LG̅ low).

- **Queue status works**: QS reports F/S/E ops; 442 instruction first-byte
  ops in the trace; queue flush (E) once per loop iteration (the short jump).
- **Reconstructed queue depth peaks at 5** (documented depth 6; this loop
  never lets it saturate — dedicated queue-limit experiment pending).
- **Per-instruction times from F-to-F spacing** (queue-supply constrained,
  not yet decomposed into EU vs BIU bound): the 7-instruction loop
  (MOV AW,imm / MOV BW,imm / MOV [BW],AW / MOV AL,dmem / MOV AW,odd-dmem /
  NOP / BR short) shows gaps {3, 5, 7, 11, 12, 12, 14} clocks, sum = 64 —
  matching the bus-side loop measurement exactly. Attribution of each gap
  to its instruction awaits the shadow-queue parser (loadstore_design.md
  stage 2).
- Float-window artifact: the ~8 cycles between reset release and first
  drive decode as phantom INTA transactions in max mode (BS floats to 000),
  analogous to the small-mode phantom reads. Parser must tolerate.

## State injection/extraction verified (2026-07-11, max mode)

- **Register echo test passes**: all 8 GPRs, all 4 segment registers, PSW,
  and PC injected via the load routine (POP PSW + MOV sequence +
  terminal far jump) and extracted via OUT-port stores read back exactly
  (sw/v30run.py echo).
- **PSW writable bits**: patterns exercising V/DIR/IE/S/Z/AC/P/CY all echo
  with zero diff after normalization (psw = (req & 0x0ED5) | 0xF002).
  Reserved bits (15:12 forced 1, 5/3 forced 0, 1 forced 1) read back as
  forced. NOT yet probed: whether bit 15 (MD) can be cleared by POP PSW in
  native mode — deferred until a recovery path for accidental
  8080-emulation entry exists.
- **Word OUT to an odd port splits into two byte I/O cycles** (measured:
  OUT 0xFD,AW produced byte writes at 0xFD and 0xFE, operand low byte
  first on the upper lane) — same split rule as odd memory words. Harness
  convention: keep exfiltration ports even.

## V20-baseline cross-validation (2026-07-11, pilot)

sw/pilot_v20.py runs V20 SingleStepTests cases (non-prefetched variants)
on the real V30 and compares architectural results. **60/60 passed**:
20 cases each of B8 (MOV AX,imm), 00 (ADD r/m8,r8 — modrm, memory
operands, arithmetic flags), 37 (AAA — undefined flags masked per suite
metadata). Registers, flags (documented bits), and final memory
(byte-lane-accurate) all match the V20 hardware baseline, consistent
with the documented architectural equivalence of the V20/V30 execution
cores. Throughput ~2-3 s/case over SSH (unbatched); suite-scale
campaigns need the batching work from loadstore_design.md stage 3.

## MUL/MULU timing characterization (2026-07-11, Campaign 2 mission 1)

Method: saturated-queue F-spacing (sw/sweep_timing.py mul), max mode,
4 MHz, 0 waits; 42 measurements in docs/facts/timing_measured.json.

- **MULU (unsigned) is data-independent**: reg8 = 24 cycles, reg16 = 31,
  mem8 [BW] = 34, mem16 [BW] even = 41 — identical across operand sets
  including 0, 1, and all-ones.
- **MUL (signed) = MULU + 10, plus exactly +4 when the operand sign bits
  differ** (zero counts as positive; the product's own sign is
  irrelevant): reg8 = 34/38, reg16 = 41/45, mem8 = 44, mem16 = 51,
  reg16,reg16,imm8 = 40/44, reg16,reg16,imm16 = 40.
- vs documentation: MULU reg forms +1..3 (like other reg ops), MULU mem
  forms +5..6; all signed-MUL measurements fall inside the manual's
  "according to data" ranges EXCEPT **MUL reg16,reg16,imm8: measured
  40/44 vs documented 28-34** — a genuine documentation error.
- The earlier "MULU CW = 31 vs 21-22 (+9)" open item was a doc-lookup
  error: 21-22 is MULU reg8; MULU reg16 is documented 29-30.

## Per-opcode timing sweep, 113 forms (2026-07-11, Campaign 2 mission 2)

sw/sweep_timing.py sweep; all data with operands and provenance in
docs/facts/timing_measured.json. Conditions: max mode, 4 MHz, 0 waits,
even-aligned code/data, saturated-queue F-spacing. 113 measured + 7
verification re-runs (different registers / SP) — every value reproduced
exactly; 0 forms unassemblable. 84/113 deviate from the User's Manual.

**Deviations are class-consistent** (every op in a class shows the same
delta):

| Form class | Measured | Documented | Delta |
|---|---|---|---|
| No-modrm reg/imm forms (NOP, MOV reg,imm, acc,imm ALU, INC/DEC reg16, XCH AW,r, CY/DIR flag ops) | doc | — | **0** |
| ALU/MOV reg,reg (modrm) | 3 | 2 | +1 |
| ALU reg,imm (group 80/81/83) | 6 | 4 | +2 |
| Unary reg: NOT/NEG reg, INC/DEC reg8 (F6/FE groups) | 4 | 2 | +2 |
| Loads reg,mem [BW] (MOV/ALU/CMP) | 13 | 11 | +2 |
| TEST mem,reg | 12 | 10 | +2 |
| Stores mem,reg / mem,imm / mem16,sreg | **all 11** | 9 / 11 / 10 | +2 / 0 / +1 |
| MOV acc,dmem (direct load) | 10 | 10 | 0 |
| MOV dmem,acc (direct store) | 10 | 9 | +1 |
| RMW mem,reg (ALU), XCH mem,reg | 19 | 16 | +3 |
| RMW unary mem (INC/DEC/NEG), ALU mem,imm | 20 / 22 | 16 / 18 | +4 |
| Shift/rotate reg,1 (all 8 ops, byte+word) | **6** | 2 | **+4** |
| Shift/rotate reg,CL or reg,imm8, n≥1 | 10+n | 7+n | +3 |
| Shift reg,CL with CL=0 | 9 | 7 | +2 |
| Shift/rotate mem,1 | 22 | 16 | +6 |
| PUSH/POP reg16/sreg/PSW (SP even) | 9 | 8 | +1 |
| PUSH imm8 / imm16 | 9 / 10 | 7 / 8 | +2 |
| PUSH R (even) | **52** | 35 | **+17** |
| POP R (even) | **33** | 43 | **-10** (only negative deviation) |
| Bit ops SET1/NOT1 reg,CL and reg,imm | 6 | 4 / 5 | +2 / +1 |
| CLR1 reg,CL and reg,imm3 | 7 | 5 / 6 | +2 / +1 |
| DIVU reg16 | 28 | 25 | +3 |
| MULU reg8/reg16, mem8/mem16 | 24/31/34/41 | 21-22/29-30/27-28/35-36 | +2/+1/+6/+5 |

Notable structure:

- **Silicon is uniform where the manual is not.** All three 2-byte-EA
  store forms measure 11 though the manual says 9/10/11; SET1/NOT1
  CL-forms and imm-forms measure identically though the manual charges
  the imm forms +1; all eight shift/rotate ops match each other exactly.
- **TEST reg,reg (2), XCH reg,reg (3), MOV sreg,reg16 / reg16,sreg (2)
  match documentation** while every other modrm reg,reg op takes 3 —
  TEST and the sreg MOVs are genuinely 1 cycle faster than ADD reg,reg
  on silicon (verified across register choices).
- Shift-by-1 at 6 cycles (vs documented 2) is the largest relative
  register-form deviation; shift-by-CL measures 10+n (n>=1), 9 (n=0).
- PUSH R/POP R: 52/33 vs documented 35/43. POP R (reads) runs near the
  4-cycle/word bus floor (33 ~= 8x4+1); PUSH R (writes) at 52 ~= 6.5
  cycles/word matches the writes-do-not-overlap-fetch arbitration
  pattern (biu_model.md exp 4).
- Direct-address loads (MOV acc,dmem) are the only memory reads with
  zero deviation; modrm EA loads all pay +2.

## Timing sweep part 2: control flow, strings, BCD, I/O (2026-07-11, mission 4)

sw/sweep_timing.py flow/string/misc (+ REP probes); 63 more records in
timing_measured.json. Taken-branch times are F-pop-to-target-first-F,
i.e. they INCLUDE the queue flush + refetch — the real effective cost.

| Form class | Measured | Documented | Delta |
|---|---|---|---|
| Bcond taken (BZ/BNZ/BC/BNC) | **13** | 14 | **-1** |
| Bcond not-taken | 4 | 4 | 0 |
| BCWZ / DBNZ taken | 15 | 13 | +2 |
| DBNZE / DBNZNE taken | 16 | 14 | +2 |
| BCWZ / DBNZ / DBNZE/NE not-taken | 5 | 5 | 0 |
| BR short / BR far / BR [BW] (memptr16) | 12 / 15 / 20 | same | 0 |
| BR near (disp16) | 13 | 12 | +1 (even or odd target) |
| BR DW (regptr16) | 12 | 11 | +1 |
| CALL near / CALL DW | 18 / 16 | 16 / 14 | +2 |
| CALL [BW] (memptr16) / CALL far | 26 / 27 | 23 / 21 | +3 / +6 |
| RET | 16 | 15 | +1 |
| RET pop-value | **17** | 20 | **-3** |
| MOVBKB/W, LDMB/W, STMB/W single | 13 / 9 / 9 | 11 / 7 / 7 | +2 |
| CMPBKB/W single | 13 | 13 | 0 |
| REP prefix (own F pop, retires separately) | 2 | 2 | 0 |
| REP STMW (n=1,2,3,5) | **9+4n** | 7+4n | slope exact, +2 |
| REP MOVBKB/W | **9+8n** | 11+8n | slope exact, **-2** |
| REPE CMPBKW | **11+14n** | 7+14n | slope exact, +4 |
| REP xxx with CW=0 | 12 | 7 | +5 (uniform early-out) |
| ADJ4A / ADJ4S (DAA/DAS) | 3 / **3** | 3 / 7 | 0 / **-4** |
| ADJBA / ADJBS (AAA/AAS) | **7** / 7 | 3 / 7 | **+4** / 0 |
| CVTBD (AAM) / CVTDB (AAD) | 15 / 8 | 15 / 7 | 0 / +1 |
| CVTBW / CVTWL | 2 / 5 | 2 / "4 or 5" | 0 (CVTWL data-independent at 5) |
| TRANS | 9 | 9 | 0 |
| IN/OUT, all 8 forms | **all 9** | 8 or 9 by form | 0..+1 |
| Shift/rotate mem,CL | 25+n | 19+n | +6 (same class as mem,1) |

Notable:

- **Conditional taken branches beat their documentation** (13 vs 14) —
  the first systematic negative deviation; not-taken times are exact.
- **The manual's ADJBA/ADJ4S values appear transposed**: silicon groups
  by family (decimal ADJ4A=ADJ4S=3, ASCII ADJBA=ADJBS=7), the manual
  by direction (A=3, S=7). Data-independent on both paths tested.
- **REP per-iteration slopes match documentation exactly** (4/8/14);
  only the setup intercepts deviate, REP MOVBK actually 2 BELOW doc.
  The REP prefix retires as its own instruction (own F pop, 2 cycles).
- Taken-branch target parity does not matter (even/odd targets timed
  identically for BR short and BZ) — matches the exp-2 flush result.
- IN/OUT: silicon charges 9 uniformly; the manual's 8-cycle rows
  (DW-indirect, all OUT) are 1 low.

## Alignment penalties (2026-07-11, mission 5)

sw/sweep_timing.py odd; 25 records (timing_measured.json: odd_operand /
anchor fields).

**Odd word operands: +4 cycles per split access, exactly and uniformly.**
Every word load, store, push, pop, and string access at an odd address
costs its even-aligned time +4 (one extra 4-cycle bus cycle); RMW forms
(ADD/INC/XCH/SHL mem) cost +8 (both accesses split). 15/15 cases fit:

| Case (odd vs even measured) | even | odd | delta |
|---|---|---|---|
| MOV reg,[BW] / ADD reg,[BW] | 13 | 17 | +4 |
| MOV [BW],reg | 11 | 15 | +4 |
| MOV acc,dmem / dmem,acc | 10 | 14 | +4 (odd load = doc 14 exact) |
| ADD/XCH [BW],reg RMW | 19 | 27 | +8 |
| INC word [BW] | 20 | 28 | +8 |
| SHL word [BW],1 | 22 | 30 | +8 |
| MULU word [BW] | 41 | 45 | +4 |
| PUSH/POP (SP odd) | 9 | 13 | +4 |
| STMW / LDMW (odd ptr) | 9 | 13 | +4 |
| MOV DL,byte [odd] | 13 | 13 | 0 (bytes never split) |

Relative deviations vs the manual's odd-address rows keep the same
class pattern as the even rows (+2 loads, +3..+4 RMW, +1 push/pop).

**Odd code anchor (PC=0x0501): EU-bound forms identical; memory forms
shift +-1.** NOP/MOV imm/INC/ADD reg,reg/DIVU/MULU/SHL reg,1 all time
exactly as at even anchors. But ADD reg,mem measured 12 (vs 13 even),
MOV mem,reg 10 (vs 11), PUSH 10 (vs 9): the code-fetch phase relative
to the EU's bus slot moves data-access arbitration by one cycle. A
per-instruction cycle model must account for fetch-phase alignment,
not just the instruction itself.

## instructions.json uncertainty probes (2026-07-11, mission 6)

sw/probe_uncertain.py: architectural hardware tests retiring 17 of the
53 _uncertain transcription items (each entry now carries a RESOLVED
note in docs/facts/instructions.json). Highlights:

- **SHR shifts the LSB into CY** (AL=80h -> CY=0, AL=01h -> CY=1,
  multi-bit consistent). The manual's operation formulas print
  "CY <- MSB" on six pages — systematic misprint; prose/diagrams right.
- **BRK imm8 is 2 bytes** ("Bytes: 1" misprint): a RETI handler resumes
  past the immediate; the imm byte does not execute.
- **Divide traps**: quotient == FFH exactly does NOT trap DIVU reg8
  ("<= FFH" reading confirmed); signed DIV traps only when the quotient
  exceeds the signed range (printed '< 7FFFH' is a misprint for '>').
  On trap, registers are preserved (matches MAME PR #15620) and the
  **pushed PC is the address AFTER the divide instruction** (0502 for a
  2-byte DIV at 0500; pushed PS=0, PSW pushed pre-trap) — answers
  OPEN_QUESTIONS Q10 for the unprefixed case.
- **MUL CY/V rule**: CY=V=0 iff the high half equals the sign extension
  of the low half (the "sign extension of AH" texts are typos).
- **ADJ4A adjusts when low nibble > 9** (0Ah -> 10h with AC=1; 09h
  unchanged); printed '< 9' is a misprint.
- **RORC V-flag U/X inconsistency is an erratum**: reg,imm8 and
  mem,imm8 forms produce identical results and identical data-dependent
  V on the same inputs — both behave as X.
- The four scan-illegible bit-op encodings (TEST1/NOT1/CLR1 mem16,imm4;
  SET1 mem8,CL with displacement) execute correctly as transcribed —
  encodings verified architecturally, including the disp8 form.
- ROLC reg,CL '7 = n' misprint: measures 14 at CL=4, same as sibling
  rotates -> '7 + n'.

## PUSH R / POP R bus decomposition; prefixed divide traps (2026-07-11, mission 7)

Bus-level capture of the 52/33 vs documented 35/43 anomaly:

- **PUSH R (52 cycles)**: 8 MEMW on a strict 6-cycle cadence (4-cycle
  write + 2 idle cycles between writes — EU-paced, not bus-limited),
  3 idle cycles lead-in after the preceding fetch. Push order AW, CW,
  DW, BW, **original SP value**, BP, IX, IY at descending addresses
  SP-2..SP-16. Documented 35 ~= 8x4+3, i.e. the value the instruction
  would have if the writes were back-to-back; silicon inserts 2 idles
  per write.
- **POP R (33 cycles)**: only **7 bus reads** — the SP slot is
  physically skipped (never read and discarded; address sequence
  F00,02,04,08,0A,0C,0E). Reads are back-to-back 4-cycle. 7x4+5 = 33,
  10 BELOW the documented 43. The documentation also inverts the real
  ordering (real: POP R faster than PUSH R).

**Prefixed divide traps (Q10 closed)**: the pushed PC always points
after the WHOLE instruction including prefixes — DIV CW overflow with
no prefix / DS0: / REP(F3) / DS0:+REP pushes 0502/0503/0503/0504 for
the instruction starting at 0500. No restart semantics on V30 divide
traps, prefixes are not dropped from the accounting.

## Timing sweep part 3: 0F set, prefixes, stack/trap paths (2026-07-11, mission 10)

sw/sweep_timing.py more; 56 records into timing_measured.json (0F
extension timings, prefix costs, trap paths, HALT). Same conditions.

| Form class | Measured | Documented | Delta |
|---|---|---|---|
| TEST1 reg,CL / reg,imm (byte=word) | 6 | 3 / 4 | +3 / +2 (joins the uniform 6-cycle reg-bit-op class) |
| TEST1 mem, all 4 forms | **14** | 12 / 13 | +2 / +1 |
| NOT1 mem,CL / mem,imm | 21 | 18 / 19 | +3 / +2 |
| SET1 mem,CL / mem,imm | 21 | 13 / 14 | **+8 / +7** |
| CLR1 mem,CL / mem,imm | 21 / 23 | 14 / 15 | +7 / +8 |
| ROL4 / ROR4 reg8 | 16 / 20 | 25 / 29 | **-9 both** |
| ROL4 / ROR4 mem8 | 27 / 31 | 28 / 33 | -1 / -2 |
| INS reg,reg / reg,imm4 (len 3-4) | 51 / 54 | 31-117 / 67-87 | in range / **-13 below range** |
| EXT reg,reg / reg,imm4 (len 4-7) | 43 / 43 | 26-55 / 21-44 | in range |
| ADD4S/SUB4S/CMP4S (n byte pairs) | **13+22n** | 7+19n | slope +3, intercept +6 (ADD4S 35/57/79 at n=1/2/3; SUB4S 56, CMP4S 55 at n=2) |
| PUSH mem16 / POP mem16 | 21 / 15 | 18 / 17 | +3 / -2 |
| PUSH sreg (PS) / POP sreg (DS0) | 9 | 8 | +1 (= PUSH/POP reg class) |
| LDEA [BW+IX] / direct dmem | 3 / 5 | 4 | **-1 / +1 — LDEA is EA-mode-dependent** (unlike loads) |
| PREPARE imm8=0 / 1 / 2 | 12 / 22 / 30 | 12 / (no row) / 27 | 0 / manual gap filled / +3 |
| DISPOSE | 9 | 6 | +3 |
| CHKIND in-bounds | 22 | 18 | +4 |
| CHKIND trap (to handler F) | 63 | 53-56 | +8 |
| RETI (frame pop + flush) | 22 | 27 | **-5** (negative like RET pop-value) |
| BRK 3 trap (to handler F) | 43 | 38 | +5 |
| BRKV V=1 trap / V=0 fall-through | 44 / 3 | garbled 52/40 rows | see note |
| HALT (F-pop to HALT bus cycle T1) | 4 | 2 | +2, different metric; bus then idle forever, done marker never arrives |

**NEW CLASS — prefix cost is context-dependent.** A segment override
retires as its own instruction (own F pop, 2 cycles — same as REP), and
the following instruction's own time can absorb it:

- DS0:/DS1:/SS: + MOV AW,[BW]: prefix 2 + MOV **11** = 13 total = the
  unprefixed time. **Net cost of one segment prefix on an EA load: 0.**
- Stacked DS1: DS0: + MOV AW,[BW]: 2+2+12 = 16 (net +3).
- DS0: + ADD BW,DW (no memory ref): 2+3 = 5 (net +2).
- BUSLOCK + NOP: 2+3 (net +2; doc charges BUSLOCK 2).

The absorption means per-instruction cycle models must treat prefixes as
pipeline events, not additive constants.

Other structure: silicon again uniform where the manual is not (all four
TEST1 mem forms = 14; SET1/NOT1/CLR1 mem,CL all = 21); ROL4/ROR4 reg
beat their documentation by 9 cycles — the largest negative deviation
yet; INS reg,imm4 at 54 is below the manual's own 67-87 range.
**CHKIND bounds comparison is SIGNED**: upper bound 0xFFFF (=-1) traps
DW=5, caught when the first "in bounds" attempt ran away through
unhooked vector 5.

## Throughput: persistent serve runner (2026-07-11, mission 13)

Profile of the legacy per-case path (sw/v30run.py profile,
sw/testdata/profile_run.out): 2263 ms/case = scp image 315 + ssh cfg 667
+ ssh run 964 + scp capture 316 — dominated by per-case ssh handshakes
and remote python start-ups, not data volume.

Fix: `v30ctl.py serve` (persistent stdin/stdout batch mode on the HPS,
base64 image in / base64 capture records out over ONE ssh connection)
plus a ServeRunner client in v30run.py (reader thread, per-response
timeouts, reconnect-once then legacy-path fallback; V30_NO_SERVE=1
forces the old path). Every RUN still performs the full
stop/load/start/host-reset cycle, so board-recovery semantics are
unchanged.

Result: **307 ms/case over a 50-case fully-verified echo burst**
(compose+run+parse+register compare each case, 0 failures; 3.3 cases/s;
first-connect overhead 607 ms once) — 7.4x over legacy, at the <300 ms
target within noise. Remaining cost is the server-side width-exact
4-byte word loops (16K writes to load, 8K reads to dump, ~C-loop
candidates via memoryview.cast if suite emission needs more; bulk
memcpy is deliberately avoided — alignment faults on device memory).

## instructions.json uncertainties: list closed (2026-07-11, mission 11)

sw/probe_uncertain.py batch2 (15 probes, sw/testdata/uncertain_batch2.out)
plus mission 10 timing data retire the remaining 36 _uncertain entries —
**all 53 are now resolved** (19 hardware/citation, 17 cosmetic). Notable:

- **CMPBK odd-address repeat clocks confirmed 7+22/rep** (35/57/79 at
  CW=1/2/3, slope exactly 22 — the garbled manual line read correctly).
- **INS reg,reg even max 117 is NOT a misprint**: worst case (offset 15,
  len 16) measures 120 = 117 + the 0F-class +3; the even range really
  exceeds the odd max.
- INM updates IY (prose says IX — typo); DIVU mem16 quotient goes to AW;
  MUL mem8 performs 1 data transfer ('Transfers: None' misprint); XOR
  mem,imm wire order is disp-then-imm; SUBC reg,reg destination is the
  reg-field operand; RETI restores CY; EI sets IE; SHRA/ROR/RORC mem-form
  formula typos verified behaviorally.
- CALLN's 'SP <- PS - 6' noted as cosmetic (8080-mode only; not runnable
  without the recovery path).

## Undefined-flag survey (2026-07-11, mission 8)

sw/probe_flags.py: 53 cases / 275 runs covering every U-flag class in
instructions.json; full classification in docs/facts/undefined_flags.md
(provenance: sw/testdata/flags_log.jsonl, flags_report.json). Headlines:

- **MULU preserves its four undefined flags** (S/Z/AC/P pass through);
  signed MUL overwrites them with microcode residue matching no simple
  function of the result (e.g. Z=1 with product C080h).
- **DIVU forces S=1 AC=1 CY=1 Z=0 V=0; DIV forces S=AC=CY=V=0 P=1 and
  Z=(quotient==0)** — complementary constant patterns.
- **Shift/rotate undefined V follows the single-step OF formula on the
  final state** (left: MSB^CY; right: top-two-bits XOR); count=0
  preserves all flags; shifter AC is always 0, as is logic-op AC.
- **NOT1/CLR1/SET1 (CY and 0F reg forms): "undefined" = untouched.**
- **TEST1 sets S/Z/P of the masked test value.**
- **ADD4S/SUB4S/CMP4S: S=AC=CY(out), P=Z(out), V=0** (7 configurations).

## Undocumented 0F survey (2026-07-11, mission 9)

sw/probe_0f.py (all + followup): 16 spread second bytes + raw-capture
classification; docs/facts/undocumented_0f.md (provenance:
sw/testdata/0f_log.jsonl). Headlines:

- 0F 00/04/08/0C/21/27: 2-byte no-ops. 0F 24: CMP4S-like string read
  (2 bytes); 0F 2C / 0F 30: modrm-consuming ops that RMW a byte at [IY]
  (INS/ROR4-family siblings). 0F 34: **silent lockup**, no HALT bus state.
- **0F 40/60/80/A0/C0/E4 are BRKEM aliases** (`0F xx imm8`): push
  PSW/PS/PC+3, vector = imm8, clear MD, enter 8080 emulation mode —
  proven by the stub byte E7 executing as 8080 RST 4 (push to BP-stack,
  jump 0020h). No invalid-opcode trap exists in the 0F space.

## Divide-overflow semantics (prior work, large context)

- MAME's divide-overflow behavior for V30 (CY/V = !overflow, registers
  preserved) is already grounded in hardware testing by Martin (MAME PR
  #15620) — see docs/notes/mame_necv.md.

## IDIV (signed divide) timing law (2026-07-12, Campaign 3 mission I)

Fitted on the F6.7/F7.7 golden tranches (500 cases each, both queue
variants and all EA forms; anomaly-free trap-predicate over all 1000
cases) and verified cycle-exact by the RTL core replay 1000/1000 with
raw flags.

Relative to the dispatch cycle (the cycle after the modrm pop for reg
forms; the cycle after the operand-read handover for mem forms, which
adds +1 like DIVU), with s = 3 extra cycles iff the dividend is
negative:

| path | condition | byte (F6.7) | word (F7.7) |
|---|---|---|---|
| early trap (IVT read ready) | den=0 or \|num_hi\| >= \|den\| | 21+s | 21+s |
| late trap (IVT read ready)  | unsigned \|q\| > 2^(n-1)-1 (symmetric) | 36+s | 44+s |
| non-trap (EX/writeback)     | otherwise | 37+s | 44+s |

- The early-trap magnitude pre-check runs at the SAME time for byte and
  word forms; only the divide loop differs (8 fewer iterations for the
  byte form: 36 vs 44).
- The only data-dependent term is the dividend negate (+3); divisor
  sign and quotient/remainder sign fixups cost nothing observable.
- Architectural/flag law in undefined_flags.md (mission F): early trap
  leaves the SUB(|num_hi|, |den|) compare residue at operand width;
  late-trap and non-trap paths leave S/Z/P of the unsigned quotient
  magnitude with CY=AC=V=0; quotient truncates toward zero, remainder
  sign follows the dividend; trap = vector 0 with the standard push
  sequence.
