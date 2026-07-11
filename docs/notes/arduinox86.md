# arduinoX86 (dbalsom) — Mechanism Notes for the NEC V30 FPGA Test Rig

Research notes on how https://github.com/dbalsom/arduinox86 initializes CPU register
state, runs a test program, extracts final state, and interprets max-mode bus cycles —
with an eye toward porting the *concepts* to our DE-10 rig (real V30, max mode, FPGA
simulates memory at full clock speed).

Provenance: see [Sources](#sources) at the bottom. Fetched 2026-07-10 from branch `main`.

---

## 1. Big picture

Three components:

- **CPU server** (firmware, `platformio/ArduinoX86/`): clocks the CPU via GPIO, reads
  status/address/data each cycle, runs a *server state machine* that feeds synthesized
  programs to the CPU (there is no real memory at all — every code fetch and memory read
  is answered by the firmware), and speaks a byte-oriented serial protocol.
- **CPU client** (`crates/arduinox86_client`, `crates/arduinox86_cpu`): holds the full
  1MB emulated address space on the PC, drives the server cycle-by-cycle (interactive
  mode) or lets the server run autonomously (automatic mode, uses on-board
  SDRAM/hash-table "bus emulator" as memory).
- Shields (PCBs) per CPU family. The 808X shield handles 8088/8086/V20/V30; V30 support
  needed the BHE pin (shield rev 1.1).

Server state machine (`ServerState` in `CommandServer.h`):

```
Reset → CpuId → (CpuSetup) → JumpVector → Load → LoadDone → (EmuEnter) →
Execute → ExecuteFinalize → ExecuteDone → Store → StoreDone
```

Everything before `Execute` and after `ExecuteFinalize` is "hidden" plumbing; the test
proper happens in `Execute`.

Key insight that makes it all work: **the CPU has no memory; the firmware is the
memory.** Register state is injected by feeding a patched instruction sequence to the
CPU's code fetches, and extracted by feeding a store sequence whose I/O writes and stack
writes are intercepted. Program-flow boundaries are detected via the queue-status lines
(QS0/QS1) which reveal exactly when the execution unit consumes a byte from the
prefetch queue.

---

## 2. Bootstrapping: reset, CPU ID, jump vector

### Reset (`Shield8088.h : resetCpuImpl`)
- Drive TEST=0, INTR=0, NMI=0; clock a few cycles; assert RESET for 8 clocks
  (`RESET_HOLD_CYCLE_COUNT 8`); release; clock until ALE goes high (first fetch at
  FFFF0). Reset takes ~7 cycles.
- During the post-reset clocking the firmware watches:
  - **BHE**: if it ever goes active ⇒ 16-bit bus (8086/V30), else 8-bit (8088/V20).
  - **QS0**: if it reads high during reset, the queue-status lines "appear
    unavailable" ⇒ `result.queueStatus = !qs0_high` (used to pick the NMI-based
    termination path, e.g. for 80186).

### CPU ID (`CPUID_PROGRAM`, `detect_cpu_type()` in `main.cpp`)
Executed at the reset vector before anything else. Intel vs NEC is detected by *timing*
the undocumented opcode `D6`:

```
D6                      ; Intel: SALC (very fast). NEC: undefined alias of XLAT (slow)
D9 3E 00 00             ; fnstcw [0000]  (FPU probe: a write of 0x03FF => 8087 present)
90                      ; wait
90 90                   ; NOPs to absorb fetch while RQ/GT runs
```

`handle_cpuid_state()` counts CPU cycles between the first two QS "first byte" reads;
`detect_cpu_type()`: if `cpuid_cycles > 5` ⇒ NEC (V20 if 8-bit bus, V30 if 16-bit),
else Intel 8088/8086.

### Jump vector (`JUMP_VECTOR`)
The reset vector FFFF:0000 leaves only 16 bytes before address wrap, so the very first
thing fed to the CPU is:

```
EA 00 00 00 D0          ; JMP FAR D000:0000   (LOAD_SEG = 0xD000, patched at offset 3)
```

`handle_jump_vector_state()` feeds this on every CODE fetch and watches ALE: when the
latched address equals `LOAD_SEG << 4`, it transitions to `Load`. (Purpose: avoid
effective-address wraparound during the load routine, and put the load program in a
clean segment.) `STORE_SEG = 0xE000` is reserved similarly for the store routine.

---

## 3. The load routine (register state injection)

Files: `platformio/ArduinoX86/asm/load.asm`, `LOAD_PROGRAM` in `src/programs.cpp`,
`patch_load_pgm()` + `handle_load_state()` in `src/main.cpp`.
(Routine originally by Andreas Jonsson, pi8088/VirtualXT.)

The firmware holds this 60-byte template; the 14 client-supplied register words are
patched into the immediate operands before execution:

```
offset  bytes            mnemonic              patched with
------  ---------------  --------------------  -----------
0x00    dw ????                                 FLAGS (data word, not code! see below)
0x02    B8 00 00         mov ax, imm16          0
0x05    8E D0            mov ss, ax
0x07    89 C4            mov sp, ax             ; SS:SP = 0000:0000
0x09    9D               popf                   ; pops FLAGS from 0000:0000
0x0A    BB 00 00         mov bx, imm16          BX   (imm @ 0x0B)
0x0D    B9 00 00         mov cx, imm16          CX   (imm @ 0x0E)
0x10    BA 00 00         mov dx, imm16          DX   (imm @ 0x11)
0x13    B8 00 00         mov ax, imm16          SS   (imm @ 0x14)
0x16    8E D0            mov ss, ax
0x18    B8 00 00         mov ax, imm16          DS   (imm @ 0x19)
0x1B    8E D8            mov ds, ax
0x1D    B8 00 00         mov ax, imm16          ES   (imm @ 0x1E)
0x20    8E C0            mov es, ax
0x22    B8 00 00         mov ax, imm16          SP   (imm @ 0x23)
0x25    89 C4            mov sp, ax
0x27    B8 00 00         mov ax, imm16          BP   (imm @ 0x28)
0x2A    89 C5            mov bp, ax
0x2C    B8 00 00         mov ax, imm16          SI   (imm @ 0x2D)
0x2F    89 C6            mov si, ax
0x31    B8 00 00         mov ax, imm16          DI   (imm @ 0x32)
0x34    89 C7            mov di, ax
0x36    B8 00 00         mov ax, imm16          AX   (imm @ 0x37)
0x39    EA 00 00 00 00   jmp far CS:IP          IP @ 0x3A, CS @ 0x3C
```

How the tricky parts work:

- **FLAGS via POPF from nonexistent memory.** The routine points SS:SP at 0000:0000 and
  executes POPF. The resulting MEMR bus cycle at address 0/1 is intercepted by
  `handle_load_state()`, which feeds back the first two bytes of the load program image
  — which were patched with the desired FLAGS word. (Word 0 of the program doubles as
  the flags data; the CPU never executes it because execution starts at offset 2 —
  the *code fetch* stream is fed from `program->read()` which tracks its own PC, while
  the *memory read* is answered by `LOAD_PROGRAM.read_at(0, addr, width)`.)
- **AX is loaded last** since it is the scratch register for all the segment/pointer
  moves.
- **CS:IP via far jump** as the final instruction. The far jump also flushes the
  prefetch queue, which is used as the load-completion signal.
- Code fetches past the end of the template are answered with NOPs (`0x9090`),
  tagged `ProgramEnd`; they get flushed by the jump anyway.

Flag normalization (server side, `cmd_load()`):

```
flags = (flags & 0xFFD7) | 0xF002     // CPU_FLAG_DEFAULT_CLEAR_8086 / SET_8086
```

i.e. reserved bits 1, 12–15 forced to 1, bits 3 and 5 forced to 0. **Caveat:** you
cannot load arbitrary reserved-bit patterns; and loading TF would derail everything
(the store phase treats an unexpected stack write at address 4 as "TRAP detected …
Invalid flags?" and errors out).

Termination of Load → transition to Execute:

- CPUs with queue status: a `QUEUE_FLUSHED` QS code during Load ⇒ `LoadDone`. Then the
  first ALE with `bus_state == CODE` (the fetch at the new CS:IP) ⇒ `Execute` (or
  `EmuEnter` for 8080-emulation runs).
- CPUs without QS (80186 path): watch for ALE whose latched address equals
  `(CS<<4)+IP` and jump straight to Execute.

The whole load takes on the order of a few hundred CPU cycles (`LOAD_TIMEOUT 1000`).
`cmd_load` runs the cycle loop internally on the server; the client just sends the 28
register bytes and waits for OK.

Client-side register buffer order (V1, 28 bytes, little-endian words —
`registers_v1.rs::write_buf`, matches server `registers1_t`):

```
AX BX CX DX IP CS FLAGS SS SP DS ES BP SI DI
```

### Prefetch-queue preloading (optional, V20/V30-specific variant)

To start a test with a *full* prefetch queue (needed to test fetch-starved timing
paths), the client prepends a "preload program" ahead of the user program and adjusts
the loaded registers so the architectural state at the test start is what was asked for
(`arduinox86_cpu/src/lib.rs`):

- Intel 8088/8086: `AA AA AA AA` (4× STOSB). Side effect: DI moves — so the client
  pre-compensates DI by ∓4 depending on the Direction flag, and rewinds the loaded IP
  by the preload length (+1 possible odd-alignment fill byte on 16-bit CPUs).
- **NEC V20/V30: `63 C0`** (`NECVX0_PRELOAD_PGM`) — an undefined opcode on NEC with
  **no register side effects** (on NEC, unknown opcodes execute as multi-cycle no-ops
  rather than trapping). Only the IP rewind is needed. (`0x63` is 8086 territory that
  NEC leaves as a no-op; note this differs from later CPUs where 63 = ARPL.)
- Bytes fetched for the preload are tagged `QueueDataType::Preload` in the client's
  shadow queue; when the first *non*-preload byte is consumed as a first instruction
  byte, the run state advances Preload → Program (that's the actual test start point).

There is also a vestigial server-side `CmdPrefetch` (0x1A) that just sets a
`do_prefetch` flag for V20/V30 (`ServerState::Prefetch` is currently a placeholder in
the platformio firmware; the client-driven preload described above is the live path).

---

## 4. Execute state: running the test

Two modes:

**Interactive (classic)** — the client sends `CmdCycle`/`CmdGetCycleState` to step the
CPU and inspects the returned per-cycle state; on each T3/Tw of a read cycle *the
client* must resolve the data bus:

- CODE fetch inside program bounds → client sends `CmdWriteDataBus` with the next
  program word from its emulated memory;
- CODE fetch out of bounds → client sends `CmdPrefetchStore` (see §6);
- MEMR → client sends memory contents (`CmdWriteDataBus`);
- MEMW/IOW → client reads the captured value with `CmdReadDataBus` and commits it to
  its emulated memory.

**Automatic** (`FLAG_EXECUTE_AUTOMATIC`) — the server resolves all bus cycles itself
against its on-board bus emulator (hash-table or SDRAM backend); the client uploads
memory with `CmdSetMemory` beforehand and just polls `CmdGetProgramState`. Termination
here is via HALT detection or jump-out-of-bounds detection with HALT injection
(`FLAG_HALT_AFTER_JUMP`), then NMI → store. This mode exists because serial round-trips
per cycle are extremely slow (and is closest to what our FPGA will do natively).

---

## 5. Bus-cycle interpretation (max mode)

### Status byte layout
`readCpuStatusLines()` packs one byte, used identically on client and server:

```
bit 0-2 : S0-S2      (bus cycle type, valid from T1/ALE until it goes passive)
bit 3-4 : S3-S4      (segment: 00=ES 01=SS 10=CS 11=DS; valid T2+)
bit 5   : S5
bit 6-7 : QS0-QS1    (queue status, describes queue activity of the *previous* cycle)
```

S0–S2 decode for 808x/V20/V30 (`BusTypes.h`, `decode_status()`):

```
0 INTA   1 IOR   2 IOW   3 HALT   4 CODE   5 MEMR   6 MEMW   7 PASV
```

QS decode (`arduinoX86.h`, `get_queue_op!`):

```
00 Idle   01 First (first byte of new instruction popped)
10 Flush  11 Subsequent (operand/modrm byte popped)
```

### 8288 command lines
The shield reads a real (or emulated — `i8288Emulator.h`) 8288: MRDC, AMWC, MWTC, IORC,
AIOWC, IOWC, INTA (all active-low), packed with BHE into a command byte:

```
bit0 MRDC, bit1 AMWC, bit2 MWTC, bit3 IORC, bit4 AIOWC, bit5 IOWC, bit6 INTA, bit7 BHE
```

The firmware conditions all bus handling on these rather than on raw S0-S2, since the
command lines carry the proper timing (active T2→T4).

### T-state tracking (`cycle()` in `main.cpp`, `getNextCycleImpl` in `Shield8088.h`)
The firmware does not see T-states directly; it reconstructs them:

- **ALE high ⇒ this cycle is T1.** Latch the address bus now (only valid moment), latch
  `bus_state` (S0-S2) for the whole bus cycle (`bus_state_latched` — needed because
  status goes PASV at T3), compute data width from BHE + A0, clear
  `data_bus_resolved`.
- T1→T2 when latched status ≠ PASV; T2→T3 always.
- **T3→Tw always** ("we can't tell if the read/write is done yet on T3"); at the top of
  the next cycle, if the relevant command line has deasserted (`is_transfer_done()`:
  MRDC for CODE/MEMR, MWTC for MEMW, IORC/IOWC for I/O, READY otherwise), the Tw is
  retroactively promoted to **T4**; otherwise stay Tw.
- On T4 of a CODE cycle, push the data-bus word into the server's shadow queue.

Data width per transfer (`set_data_bus_width()`), critical for V30:

```
BHE active + even addr  → 16-bit transfer
BHE active + odd addr   → 8-bit high half (odd byte)
BHE inactive            → 8-bit low half (even byte)
```

### When must read data be driven?
`WRITE_CYCLE` is defined as **T3** for the 808x shield: for CODE/MEMR/IOR the firmware
(or the client, in interactive mode) drives the data bus when the command line is
active and `bus_cycle == T3` (and continues into Tw), guarded by the per-cycle
`data_bus_resolved` flag so the bus is driven exactly once per m-cycle. Writes are
sampled whenever MWTC/IOWC are active.

### Shadow instruction queue
Both server (`InstructionQueue.h`) and client (`queue.rs`) mirror the CPU's prefetch
queue: push on T4 of code fetches (1 or 2 bytes per data width), pop on QS=First/
Subsequent, clear on QS=Flush. Every queue byte carries a *tag*
(`Program` vs `ProgramEnd`/`Finalize`, client adds `Preload`, `EmuEnter`, `Fill`), and
the client also records the fetch address per byte. Queue depth: 4 bytes (8088/V20),
6 bytes (8086/V30) — V30 fetches 16 bits at a time (2 pushes per fetch).

The tag mechanism is the heart of program-end detection (next section).

Misc: HALT bus state (with address bit patterns distinguishing HALT vs 286 SHUTDOWN) is
detected to end programs; on 286 a missed-ALE heuristic exists (not relevant to V30).

---

## 6. Program termination detection

**Queue-status method (8088/8086/V20/V30 — the primary path):**

1. The client knows the linear byte range of the test program (`start_addr..end_addr`).
2. When the CPU *prefetches past the end* of the program, the client stops feeding user
   bytes and instead issues `CmdPrefetchStore`: the server feeds the next byte(s) of the
   STORE program tagged `QueueDataType::ProgramEnd` (client tags its copy `Finalize`).
   Execution has *not* ended yet — these are just prefetched.
3. When a tagged byte is **popped from the queue as the first byte of a new instruction**
   (QS=First, `CPU.q_ff && qt == ProgramEnd`), the previous instruction — the last real
   test instruction — has fully retired. The client calls `CmdFinalize`
   (`Execute → ExecuteFinalize`), and the server transitions to `ExecuteDone` on that
   same tagged-byte fetch. This is exact to the cycle, including instructions that
   themselves fetch/flush (jumps land within bounds again and reset `s_pc`).
4. Store-PC bookkeeping: if the queue is flushed while store bytes were already
   prefetched, `s_pc` is rewound by the queue length so no store bytes are skipped
   (`cycle()` flush handling); `cmd_write_data_bus` on a CODE cycle also resets
   `prefetching_store`/`s_pc` (a flow-control instruction jumped back in bounds).
5. IP fixup: the client records queue length at finalize and
   `program_end_offset` (NOP padding fills), and rewinds the stored IP so the reported
   IP corresponds to the end of the test program (`regs.rewind_ip(...)`).

**NMI method (no queue status — 80186; also HALT handling):** raise NMI; when the CPU
reads the NMI vector at 0:0008 the server enters `ExecuteFinalize`, feeds a patched NMI
vector `{00 00, 00 E0}` → STORE_SEG:0000, captures the flags/CS/IP frame the CPU pushes
(stack writes land in `NMI_STACK_BUFFER`), and later replays that buffer when the store
program pops it. HALT in Execute also raises NMI to break out.

---

## 7. The store routine (register state extraction)

Files: `asm/store.asm` (inline variant), `asm/store_nmi.asm` (NMI variant),
`STORE_PROGRAM_INLINE` / `STORE_PROGRAM_NMI` in `programs.cpp`,
`handle_store_state()` in `main.cpp`.

Core idea: registers that can be moved to AX are emitted with `OUT 0xFE, AX` — a dummy
I/O port; the firmware intercepts each IOW at port 0xFE and appends the word into a
`registers1_t` struct via a running pointer (`readback_p`) whose field order matches the
emission order. FLAGS and IP have no `OUT`-able form, so they are captured from
intercepted *stack writes* to a fake stack at 0000:0000-0003. `OUT 0xFD, AL` (AL=0xFF)
signals completion → `StoreDone`.

`STORE_PROGRAM_INLINE` (queue-status termination path), bytes + disassembly:

```
90 x6                    ; 6 NOPs padding — hides store prefetch from client cycle traces
E7 FE                    ; out 0xFE, ax        → AX
89 D8, E7 FE             ; mov ax,bx; out      → BX
89 C8, E7 FE             ; mov ax,cx; out      → CX
89 D0, E7 FE             ; mov ax,dx; out      → DX
8C D0, E7 FE             ; mov ax,ss; out      → SS
89 E0, E7 FE             ; mov ax,sp; out      → SP
B8 00 00, 8E D0          ; mov ax,0; mov ss,ax
B8 04 00, 89 C4          ; mov ax,4; mov sp,ax ; 4-byte fake stack at 0:0
9C                       ; pushf               → FLAGS (captured via MEMW @ 0:0002)
E8 00 00                 ; call +0             → IP    (captured via MEMW @ 0:0000)
8C C8, E7 FE             ; mov ax,cs; out      → CS
8C D8, E7 FE             ; mov ax,ds; out      → DS
8C C0, E7 FE             ; mov ax,es; out      → ES
89 E8, E7 FE             ; mov ax,bp; out      → BP
89 F0, E7 FE             ; mov ax,si; out      → SI
89 F8, E7 FE             ; mov ax,di; out      → DI
B0 FF, E6 FD             ; mov al,0xFF; out 0xFD, al  → DONE marker
```

Notes/caveats documented in the source:

- SS and SP are dumped *first*, before the routine clobbers them for the fake stack.
- FLAGS can only be read via PUSHF; IP only via the return address pushed by CALL. Both
  arrive as intercepted memory *writes* below address 0x0004. Server checks the write
  address: a write at 0x0004 means a TRAP/interrupt fired mid-store ⇒ error ("Invalid
  flags?").
- The captured IP is the address of the byte after `CALL _ip` inside the *store
  segment*; it must be adjusted by a constant (historical comment: `ip -= 0x24` (+6 for
  the NOP pad)) and further rewound by the client (queue length at finalize) to yield
  the test-final IP. In the current code the raw IP is reported and the *client* does
  the rewinding.
- The store routine, like everything else, is fed purely through code-fetch
  interception at STORE_SEG (or wherever prefetch happened to be); an early queue flush
  during store resets/rewinds `s_pc`.
- Registers are accumulated into `registers2_t` order for the inline routine
  (`AX BX CX DX SS SP FLAGS IP CS DS ES BP SI DI`), then `convert_inline_registers()`
  swaps fields into `registers1_t` order before sending to the client
  (`AX BX CX DX IP CS FLAGS SS SP DS ES BP SI DI`, little-endian words, prefixed by a
  format byte 0x00 = V1).

`STORE_PROGRAM_NMI` differs: runs as the NMI handler, so it starts by dumping
AX/BX/CX/DX, then does `58 (pop ax); E7 FE` three times to pull **IP, CS, FLAGS off the
NMI stack frame** (the server feeds those pops from `NMI_STACK_BUFFER`), then dumps
SS/SP/DS/ES/BP/SI/DI; termination marker identical. No CALL trick needed.

---

## 8. V20/V30-specific handling

- **Detection:** timing of undocumented `D6` (§2). V30 vs V20 = 16-bit vs 8-bit bus,
  from BHE during reset. (Debug string quirk: 8-bit NEC detection prints "V30H" but
  sets `necV20`.)
- **BHE / odd-address transfers:** all the ActiveBusWidth handling in §5 exists for the
  8086/V30. Odd-addressed byte transfers use the *high* half of the data bus; the
  16-bit queue pushes 2 bytes per fetch; an odd jump target causes a single
  high-half fetch first (`EightHigh`), and `read_program`/`read_at` reconstruct the
  containing word (low byte = previous program byte, "doesn't really matter" but fed
  for realism).
- **Prefetch preload program `63 C0`** — NEC-only no-op used to fill the queue without
  architectural side effects (§3). Intel needs STOSB + DI compensation instead.
- **8080 emulation mode (BRKEM/RETEM)** — unique to V20/V30, fully supported:
  - `FLAG_EMU_8080` set via `CmdSetFlags`; after LoadDone the server enters `EmuEnter`
    instead of Execute and feeds `EMU_ENTER_PROGRAM`:
    `[ip_lo ip_hi cs_lo cs_hi] 0F FF 00` — the first 4 bytes are the interrupt-vector
    contents for vector 0 (patched with target CS:IP), followed by `BRKEM 0`
    (`0F FF imm8`). The vector *read* (MEMR at 0-3) is answered from the program image;
    the flags word that BRKEM pushes is captured (`pre_emu_flags`) from the stack write.
    Queue flush at the mode switch ⇒ LoadDone ⇒ Execute (now `in_emulation`).
  - Termination while in emulation: tagged fetch ⇒ `EmuExit` state, feeding
    `EMU_EXIT_PROGRAM`: 6 NOP pad, `F5` (8080 PUSH PSW — the 8080 flags are captured
    from the resulting stack write), `33 33` (INX SP ×2 to rebalance), `ED FD`
    (**RETEM**). The IP/CS/FLAGS pops performed by RETEM are *faked* by the firmware:
    IP←0, CS←the originally loaded CS (CS can't change inside emulation), FLAGS←the
    captured pre-BRKEM flags. Then normal Store; during store, the low byte of the
    pushed FLAGS word is *substituted* with the captured 8080 PSW so the client sees
    8080 flags.
- No other NEC-specific bus differences are handled — V30 rides the 8086 code paths.

---

## 9. Serial protocol (operation set)

Byte-oriented; client sends 1 command byte + fixed-length params; server executes and
replies with data (if any) + terminal status byte 0x01 OK / 0x00 FAIL. Commands are only
processed every 64 server ticks. `VERSION_NUM = 3`.

The interesting subset (`ServerCommand`, `CommandServer.h`):

| code | command | notes |
|------|---------|-------|
| 0x01 | Version | returns version |
| 0x02 | ResetCpu | full reset sequence + CPU ID |
| 0x03 | Load | 1 type byte (0=V1 8088-186, 1=286 LOADALL, 2=386, 3=SMM) + 28-byte V1 register blob; server resets CPU, runs JumpVector+Load internally until Execute; flags normalized |
| 0x04 | Cycle | param: count; clock the CPU N cycles |
| 0x05 | ReadAddressLatch | 3 bytes, address latched at last ALE |
| 0x17 | ReadAddress | 3 bytes, live address bus |
| 0x06 | ReadStatus | status byte (S0-S5 + QS0-QS1) |
| 0x07/0x08 | Read8288Command/Control | command byte (§5) / control (ALE…) |
| 0x09 | ReadDataBus | 2 bytes |
| 0x0A | WriteDataBus | 2 bytes; drives bus for the current read cycle |
| 0x16 | PrefetchStore | drive next STORE/EmuExit byte(s), tagged ProgramEnd |
| 0x0B | Finalize | Execute→ExecuteFinalize, cycles until ExecuteDone |
| 0x0D | Store | runs store program internally; returns format byte + register blob |
| 0x0E/0x0F | QueueLen / QueueBytes | shadow queue inspection |
| 0x10/0x11 | WritePin / ReadPin | READY(0), TEST(1), INTR(2), NMI(3) |
| 0x12 | GetProgramState | server state byte |
| 0x14 | GetCycleState | optional cycle-first flag; returns 11 bytes: state, T-state, status, control, command, addr(4), data(2) — the workhorse for cycle stepping (1 round trip/cycle) |
| 0x19 | SetFlags | u32: EMU_8080, EXECUTE_AUTOMATIC, HALT_AFTER_JUMP, USE_SDRAM_BACKEND, LOG_CYCLES, RESOLVE_BUS_STEP, … |
| 0x1A | Prefetch | V20/V30 only; sets do_prefetch (legacy) |
| 0x1D–0x25 | SetRandomSeed / RandomizeMem / SetMemory / ReadMemory / EraseMemory / GetCycleStates / SetMemoryStrategy | automatic-mode memory management + bulk cycle log retrieval |
| 0x28/0x29 | SetProgramBounds / SetJumpHint | automatic-mode termination aids |

---

## 10. Porting to the FPGA rig

What carries over directly (concept level):

- **The load/store instruction sequences and their interception contract.** Nothing
  about them is Arduino-specific. We need, in FPGA logic (or soft-CPU/NIOS/HPS
  assistance):
  1. Reset sequencing + reset-vector far jump to a load segment.
  2. A patchable 60-byte load image (patch offsets in §3) served on code fetches, with
     the MEMR at 0/1 answered with the FLAGS word.
  3. A store image served at STORE_SEG whose IOW at 0xFE/0xFD and MEMW below 0x0004 are
     captured. Register order fixed ⇒ a simple capture FIFO/RAM suffices.
- **Max-mode decode tables** (S0-S2, QS0-QS1, 8288 command timing, BHE/A0 width rules)
  as-is; V30 uses the 8086 encodings.
- **Queue mirroring + byte tagging** for exact termination: tag rule "fetch outside
  program bounds ⇒ tagged; tagged byte popped with QS=First ⇒ previous instruction
  retired" is the single most valuable trick to replicate. Tags live alongside a
  4/6-deep shadow queue — trivial in HDL.
- **Preload with `63 C0`** for full-queue test starts; only IP compensation needed on
  NEC.
- Flag normalization masks (set 0xF002 / clear 0xFFD7) and the "TF ⇒ store trap"
  hazard.
- IP fixups: rewind stored IP by queue length at finalize (+ store-routine constant),
  DI/IP adjustments when preloading.

What changes at full speed with on-FPGA memory:

- **No serial-per-cycle bottleneck ⇒ the interactive mode disappears.** Our design is
  effectively arduinoX86's *automatic mode* done right: memory (BRAM/SDRAM) answers
  every cycle at speed; the state machine (JumpVector/Load/Execute/Finalize/Store) runs
  in hardware; the host only uploads {registers, program, memory image} and downloads
  {registers, memory writes, cycle trace}.
- **T-state tracking simplifies.** ArduinoX86 reconstructs T-states and retro-promotes
  Tw→T4 because it samples asynchronously via GPIO; a synchronous FPGA sampling on
  CPU-clock edges can track T-states exactly (T1 = ALE, T2, T3, T4; Tw only if we
  ourselves deassert READY). We also control READY, so Tw is a feature (wait-state
  testing), not an inference problem.
- **Data-bus turnaround timing becomes real.** The Arduino drives read data lazily
  "sometime during T3"; at 4–8 MHz we must meet actual tDS setup before the T3 falling
  edge — drive the bus from ALE-latched address as soon as MRDC/IORC asserts (T2), and
  tri-state on MRDC deassert. The `data_bus_resolved` once-per-m-cycle guard is
  irrelevant when memory is combinational/1-cycle BRAM.
- **Dynamic-logic constraint disappears** (README: NMOS 8088s hang below minimum clock;
  CMOS recommended). At full speed a plain NMOS/CMOS V30 is happy — but conversely we
  can't pause mid-cycle to think; everything the firmware does "while stopped" must be
  pipelined or precomputed (patched program images in BRAM before starting).
- **CPU ID is unnecessary** (we know it's a V30) but the D6-timing trick is a nice
  self-check that the rig clocks/QS decode work.
- **Termination:** keep the queue-tag method (V30 has QS lines in max mode — wire them).
  The NMI path is only a fallback. HALT detection (S0-S2 = 3) should still route to a
  "raise NMI, then store" recovery path if we want to survive tests that halt.
- Watch **8288 semantics**: if we don't put a real 8288 on the board we must emulate its
  command timing from S0-S2 + CLK (the repo has `i8288Emulator.h` for exactly this),
  since all the interception logic keys off MRDC/MWTC/IORC/IOWC rather than raw status.
- The client's 1MB memory model + IVT setup (every vector pointing at IRET stubs in a
  dedicated ISR segment, `setup_ivt()`) is worth copying for interrupt-producing tests.
- Address wrap: keep the load/store segments (0xD000/0xE000) away from 0xFFFF0 and from
  the test program's CS; bounds checks are on 20-bit physical addresses.

Open questions to verify on real silicon:

- Exact V30 QS timing skew vs 8086 (arduinoX86 treats them identically).
- Whether the V30 tolerates our READY/Tw insertion the same way (the firmware's wait
  state hooks are half-disabled in current code).
- `63 C0` behavior — confirmed as a no-op by dbalsom's V20 test-suite work, but worth
  re-validating on our specific V30 stepping at speed.

---

## Sources

All fetched 2026-07-10 (branch `main`, repo `dbalsom/arduinoX86`):

- README: https://raw.githubusercontent.com/dbalsom/arduinoX86/main/README.md
  (project overview; blog: https://martypc.blogspot.com/2023/06/hardware-validating-emulator.html)
- Load/store asm:
  - https://raw.githubusercontent.com/dbalsom/arduinoX86/main/platformio/ArduinoX86/asm/load.asm
  - https://raw.githubusercontent.com/dbalsom/arduinoX86/main/platformio/ArduinoX86/asm/store.asm
  - https://raw.githubusercontent.com/dbalsom/arduinoX86/main/platformio/ArduinoX86/asm/store_nmi.asm
- Firmware:
  - https://raw.githubusercontent.com/dbalsom/arduinoX86/main/platformio/ArduinoX86/src/main.cpp (cycle(), state handlers, detect_cpu_type)
  - https://raw.githubusercontent.com/dbalsom/arduinoX86/main/platformio/ArduinoX86/src/programs.cpp (all InlineProgram byte listings)
  - https://raw.githubusercontent.com/dbalsom/arduinoX86/main/platformio/ArduinoX86/src/CommandServer.cpp (cmd_load, cmd_store, cmd_prefetch_store, cmd_finalize, cmd_set_flags)
  - https://raw.githubusercontent.com/dbalsom/arduinoX86/main/platformio/ArduinoX86/include/CommandServer.h (ServerState, ServerCommand, flags)
  - https://raw.githubusercontent.com/dbalsom/arduinoX86/main/platformio/ArduinoX86/include/BusTypes.h, .../InstructionQueue.h, .../Cpu.h, .../registers.h, .../arduinoX86.h
  - https://raw.githubusercontent.com/dbalsom/arduinoX86/main/platformio/ArduinoX86/include/shields/Shield8088.h (reset, WRITE_CYCLE=T3, getNextCycle)
- Client:
  - https://raw.githubusercontent.com/dbalsom/arduinoX86/main/crates/arduinox86_cpu/src/lib.rs (RemoteCpu, preload programs, cycle loop, finalize)
  - https://raw.githubusercontent.com/dbalsom/arduinoX86/main/crates/arduinox86_cpu/src/queue.rs, .../remote_program.rs
  - https://raw.githubusercontent.com/dbalsom/arduinoX86/main/crates/arduinox86_client/src/lib.rs (status decode, protocol), .../cycle_state.rs, .../registers/registers_v1.rs
  - https://raw.githubusercontent.com/dbalsom/arduinoX86/main/crates/exec_program/src/main.rs (end-to-end flow)
- Related: pi8088 validator (origin of load/store routines):
  https://github.com/andreas-jonsson/virtualxt/tree/develop/tools/validator/pi8088
