# Design: Register State Injection/Extraction for the V30 Test Harness

Produced 2026-07-11 (planning agent, reviewed). Assumes the RQ/AK0-1 rework
will enable large mode + queue status; stage 1 is still runnable in small
mode for architectural-only results.

## 0. Chosen approach in one paragraph

Adapt the arduinoX86 load/store methodology to a *real-memory* rig: the
runner composes a full 64 KB image per test containing (a) a reset-vector
far jump to a **load routine** in a 256-byte reserved page at physical
`0xFF00-0xFFFF`, (b) the load routine with the test's register values baked
in as immediates, ending in a far jump `BR far PS:PC` that flushes the queue
and starts the test, (c) the test instruction and its operand bytes at their
randomized addresses, (d) a 17-byte **store stub** (6xNOP pad + `OUT` + far
jump) at the *predicted continuation address*, and (e) a fixed **store main
routine** in the reserved page that exfiltrates every register as
`OUT 0FEh,AW` I/O writes — which the FPGA already captures in the trace but
never commits to memory — plus `PUSH PSW` to a scratch stack for flags,
ending in a done-marker `OUT 0FDh` and `HALT`. All extraction is pure trace
parsing; no RTL changes are required for stage 1. FLAGS are injected with an
interception-free `POP PSW` from a pre-placed word in the reserved page. In
small mode we get exact architectural results and bus-transaction traces;
cycle-exact instruction boundaries, queue columns, and prefetched-queue
variants use queue status in large mode.

## 1. Memory map (physical 64 KB, mirrored across 1 MB)

```
0x0000-0x03FF   IVT area — test-owned; per-test entries composed only for
                exception/interrupt tests, otherwise ordinary test memory
0x0400          conventional exception-handler location (division/BRK tests):
                store stub goes here for those tests (V20 suite convention)
0x0000-0xFEFF   test space: instruction bytes, operands, stack, stub
0xFF00-0xFF3F   LOAD routine (53 bytes + prefetch-overrun margin)
0xFF40-0xFF9F   STORE_MAIN routine (~50 bytes)
0xFFC0-0xFFED   scratch: store-phase stack (SP=0xFFEE, PUSH PSW writes 0xFFEC)
0xFFEE-0xFFEF   PSW injection image (word consumed by POP PSW)
0xFFF0-0xFFFF   reset vector: EA 00 FF 00 00 (BR far 0000:FF00) + overrun fill
```

Reserved harness footprint: one 256-byte page (0.4 %). Fill byte everywhere
else is `0x90` (V20 suite convention, matches build_image default).

**Collision policy** (the V20 suite randomizes addresses): the runner is the
generator, so use rejection sampling. Compute the test's physical footprint
(instruction bytes at `(CS*16+IP) mod 64K`, preload bytes, predicted
operand reads/writes, predicted stack writes, IVT entries, the 17-byte stub
at the predicted continuation) and reject/re-randomize if:
1. footprint intersects the reserved page;
2. the stub overlaps the instruction or its operands;
3. **any two distinct linear addresses in the footprint alias mod 64K** —
   unique to our mirrored memory: a consumer emulator with true 1 MB RAM
   would see two independent bytes where our hardware has one, so aliased
   tests are unfaithful and must be re-rolled.

## 2. Load routine

Runs at `0000:FF00` (linear 0x0FF00), reached via the reset-vector far jump.
v30asm template (`{X}` substituted per test):

```asm
    ; ---- LOAD, at 0xFF00, executed with PS=0000 ----
    MOV AW, 0            ; B8 00 00
    MOV SS, AW           ; 8E D0      scratch stack: SS=0
    MOV SP, 0FFEEh       ; BC EE FF   SP -> PSW image word
    POP PSW              ; 9D         PSW := [0:FFEE]  (flags injected)
    MOV AW, {SS}
    MOV SS, AW           ; interrupt shadow covers the next instruction
    MOV SP, {SP}         ; real SP, deliberately in the shadow slot
    MOV AW, {DS0}
    MOV DS0, AW
    MOV AW, {DS1}
    MOV DS1, AW
    MOV BW, {BW}
    MOV CW, {CW}
    MOV DW, {DW}
    MOV BP, {BP}
    MOV IX, {IX}
    MOV IY, {IY}
    MOV AW, {AW}         ; AW last: it was the segment-load shuttle
    DB 0EAh              ; BR far {PS}:{PC} — queue flush = clean test anchor
    DW {PC}
    DW {PS}
    ; at 0xFFEE (placed by the composer): DW {PSW_normalized}
```

53 code bytes. Key points:
- MOV never touches PSW, so POP PSW first; injected flags survive to test
  start. AW is the only shuttle and is loaded last.
- Host holds INT/NMI/POLL inactive during load (PINS register), so IE being
  set mid-load is harmless. Consequence: INT-pin tests can NOT pre-assert
  INT; they need the pin-event scheduler (see section 9).
- The final far jump atomically sets PS:PC and flushes the queue — the first
  fetch at linear PS*16+PC is the unambiguous test-start anchor.
- Prefetch overruns past the far jump (~6-8 bytes measured) fetch reserved-
  page bytes; harmless, parser tolerates.

## 3. FLAGS injection

Interception-free POP PSW is sufficient: memory is real BRAM, so place the
flags word at 0xFFEE and pop it. V30 PSW layout: 15=MD, 14-12=1, 11=V,
10=DIR, 9=IE, 8=BRK, 7=S, 6=Z, 5=0, 4=AC, 3=0, 2=P, 1=1, 0=CY.

```
psw_injected = (psw_requested & 0x0FD5) | 0xF002
# generator never sets bit 8 (BRK/TF)
```

Forcing MD=1 is mandatory (if POP PSW can clear MD in native mode, a zero
bit 15 would drop into 8080-emulation mode mid-load — top risk). Whether the
reserved bits truly read back as constants is itself an early experiment.

## 4. Store routine

**Channel: OUT to dummy port 0xFE** (arduinoX86-style). test_mem drops I/O
writes while nec_bus captures them — zero memory pollution, no segment
setup, trivially parseable (fixed-order IOW records at port 0xFE).

**(a) Store stub — 17 bytes at the predicted continuation**
(physical `(PS_final*16 + IP_final) mod 64K`; for exception tests, at the
handler address):

```asm
    DB 90h,90h,90h,90h,90h,90h  ; pad: prefetch window stays 0x90
    OUT 0FEh, AW                ; word #1: AW (dump before clobbering)
    MOV AW, PS
    OUT 0FEh, AW                ; word #2: PS (before the jump changes it)
    DB 0EAh                     ; BR far 0000:FF40 -> STORE_MAIN
    DW 0FF40h
    DW 0
```

**(b) STORE_MAIN — fixed at 0xFF40:** dumps SS, SP (words #3-4), repoints
SS:SP to the scratch stack, `PUSH PSW` (MEMW @0:FFEC = final PSW), dumps
DS0, DS1, BW, CW, DW, BP, IX, IY (words #5-12), writes a sentinel to port
0xFD (done marker), then HALT (bus quiet, capture fills, cap_full pollable).

- FLAGS: PUSH PSW is the only full-word PSW-to-memory path.
- PS:PC: PS from word #2; **IP_final = (stub_linear - PS_final*16) mod 64K**.
  The stub fetch address alone is NOT sufficient: (i) fetch addresses are
  linear (conflate PS:PC), (ii) the BIU prefetches the stub bytes before the
  test instruction retires — the EU-side IOW is the real store anchor
  (in large mode, the queue-tag F-op on a stub byte is the precise marker).

## 5. Termination / what small mode delivers vs large mode

Small mode (stage 1): exact architectural results (registers, flags, PS:PC,
final memory) and full bus-transaction traces; cycle counts are
regression-grade only (anchor..first-IOW envelope overstates by pad+OUT
overhead; prefetch attribution ambiguous by 0-8 bytes). Large mode restores:
queue-op/queue-byte columns, exact first-byte-pop trace start/end,
suite-grade cycle counts, CODE-vs-MEMR certainty, prefetched variants.

## 6. Runner flow and trace attribution

New `sw/testimage.py` (composer) + `sw/v30run.py` (runner on v30ctl.Harness):

```
per test: predict continuation & footprint -> reject/re-roll on collision ->
compose image (fill 0x90; vector; LOAD patched; STORE_MAIN; stub; insn;
operands; IVT/preload as needed) -> stop/load/start (skip_pwrup) ->
poll cap_full -> stop -> dump -> parse -> emit JSON (quarantine anomalies)
```

Trace attribution (extends analyze_capture.py): boot phase (fetch @0xFFFF0)
-> load phase (fetch stream in 0x0FF00-3x, MEMR @0x0FFEE) -> TEST ANCHOR =
first transaction at linear CS*16+IP (20-bit match; tolerate odd-address
byte-fetch form) -> test phase until first IOW @0xFE = STORE ANCHOR ->
12 fixed-order register words + PSW from MEMW @0x0FFEC + IP from stub
placement -> done marker IOW @0xFD -> final.ram = image + test-phase MEMWs
(honoring byte enables), cross-checked against BRAM readback diff.

## 7. Prefetched vs non-prefetched variants

- Non-prefetched is native: the load far jump flushes the queue.
- Prefetched (large mode only): dbalsom's NEC preload — `63 C0` (undefined
  multi-cycle no-op with no register effects on NEC) at CS:IP-2n, far-jump
  there; the BIU fills the queue while the EU grinds. Calibrate repetitions
  vs queue depth with QS. Verify `63 C0` is truly side-effect-free on this
  stepping first. Architectural results are identical, so prefetched
  variants are pure large-mode deliverables.

## 8. Interrupt/exception tests

- Division error / BRK / BRKV / FPO: compose IVT entry -> 0000:0400, stub at
  0x0400. Exception stack frame lands in the test's own stack (test
  behavior, captured naturally). V20/V30 push PC-of-NEXT-instruction.
- INT-pin tests: cannot pre-assert INT (recognized during load once IE set).
  Needs the stage-1.5 pin-event scheduler: assert int_req on fetch-address
  match + programmable delay. INTA vector already works (cfg_int_vector).
- NMI: same trigger mechanism (clean synchronous edge; NMI is
  edge-sensitive). NMI-as-rescue for runaway tests is a later option.

## 9. FPGA/RTL additions (ranked; stage 1 needs NONE)

1. Configurable IOR data (currently 0x0000; suite convention 0xFF) — before
   IN tests. Trivial.
2. Store-done latch: sticky STATUS bit + last-IOW-data register for port
   0xFD (faster completion detection than cap_full).
3. Pin-event scheduler: {fetch-address match or cycle count -> set/clear
   int_req/nmi_req/poll_n} — required for INT/NMI/POLL tests.
4. Capture trigger/window (start on test-anchor address match) — needed for
   wait-state sweeps; budget is fine otherwise (~500 records overhead,
   ~3500 for test; worst case string ops ~2500).
5. Large mode: nothing new (QS already captured; --large analysis exists).

Toolchain: v30asm needs far-immediate `BR far seg:off` (or keep the DB/DW
idiom); multiple `org` directives don't gap-fill — the composer places
separately assembled fragments (better: assemble once with sentinel
immediates, record patch offsets, byte-patch per test — fast for 10k-test
campaigns).

## 10. Risk list (ordered by likelihood of surprising us)

1. POP PSW reserved/MD-bit semantics (8080-mode trap if MD writable).
   First stage-1 experiment.
2. Continuation misprediction (undocumented opcodes, halt-on-invalid) —
   missing 0xFD marker -> quarantine trace; partly the point of the project.
3. Prefetch overrun length differing from the measured 6-8 bytes (pad
   sizing, phase-parser tolerances). Measure early.
4. `63 C0` preload behavior unverified on this silicon (gates prefetched
   variants only).
5. Interrupt shadow subtleties around POP PSW/segment loads on NEC parts.
6. HALT-in-small-mode bus signature — rely on marker-then-quiet, not HALT
   status.
7. Odd-address anchors (single upper-lane byte first fetch) — matcher and
   stub placement handle both parities.
8. Capture depth for long tests with waits — RTL item 4.
9. Bridge/JTAG read glitches — keep READY-bit validation in dump paths.
10. Trace vs BRAM final.ram disagreement — the dual extraction catches
    byte-enable parser bugs.

## 11. Staged implementation plan

**Stage 1 — architectural results in small mode (no RTL changes):**
testimage.py composer -> v30run.py runner -> phase-splitting extractor in
analyze_capture.py -> bring-up experiments in order: register echo test,
PSW reserved-bit probe (retires risk 1), prefetch-overrun measurement
(risk 3), pilot opcodes (MOV reg,imm + one ALU op) cross-checked against
V20-suite final states -> division-exception pilot.

**Stage 1.5 — small RTL conveniences:** IOR data config, store-done latch,
pin-event scheduler -> interrupt tests.

**Stage 2 — large mode (after RQ/AK rework):** validate QS capture;
shadow-queue reconstruction (pushes from CODE T4s, pops/flushes from QS) ->
exact first-byte-pop boundaries, all 11 suite columns; calibrate prefetched
variants; capture windowing if wait-state sweeps demand it.

**Stage 3 — suite generation at scale:** randomizer with V20 suite
conventions (counts, prefix salting, CX masking, 2% zero-bias), JSON/MOO
export, throughput work (batch image patching, capture windowing).
