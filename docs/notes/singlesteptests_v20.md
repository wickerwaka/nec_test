# SingleStepTests V20 Test Suite — Format Notes

Research notes on the SingleStepTests V20 (NEC uPD70108) CPU test suite, gathered as
groundwork for building a V30 (uPD70116) hardware test rig and a compatible V30 test suite.

- Repo: https://github.com/SingleStepTests/v20 (branch `main`)
- Suite version: 1.0.3 (metadata.json reports 1.0.2, `syntax_version: 2`)
- Author/generator: Daniel Balsom, Arduino8088 v1.1 hardware interface + MartyPC emulator
- CPU used: "NEC JAPAN V20 8902NX D70108C-8 1984", running in **Maximum mode** with an
  **Intel 8288** bus controller. No wait states. Full 1 MB of writable RAM assumed.
- Directories: `v1_native/` (native instruction set, present), `v1_emulation/` (8080
  emulation mode, planned but not present).

## Repository layout

`v1_native/` contains **360 gzipped JSON test files** plus `metadata.json` and
`metadata.toml` (same content, two formats). File naming:

- `XX.json.gz` — one file per opcode byte (hex, upper case), e.g. `00.json.gz`, `FA.json.gz`.
- `XX.N.json.gz` — group opcodes split by modrm `reg` field (N = 0..7):
  `80 81 82 83 C0 C1 D0 D1 D2 D3 F6 F7 FE FF`.
- `0FXX.json.gz` — V20 extended (two-byte) opcodes: `0F10`–`0F1F`, `0F20`, `0F22`,
  `0F26`, `0F28`, `0F2A`, `0F31`, `0F33`, `0F39`, `0F3B` (all 0F opcodes except BRKEM).

Each file is a JSON array of test objects. Uncompressed sizes range from ~1 MB to
~100+ MB (string ops); compressed 128 KB – 14.6 MB. `test_tools/` has Python helpers
(`extract.py`, `subset.py`, `opcode_info.py`, `histogram_pairs.py`, `calculate_uncompressed.py`).

## Top-level test JSON schema

Each test object has exactly these keys:

| Key       | Type   | Meaning |
|-----------|--------|---------|
| `name`    | string | Human-readable disassembly, e.g. `"add byte [ss:bp+di-64h], cl"` |
| `bytes`   | array  | Raw instruction bytes (including any prefixes). Informational only — the same bytes are also placed in initial RAM. |
| `initial` | object | Full register/memory/queue state before execution (`regs`, `ram`, `queue`). |
| `final`   | object | State **changes** after execution (`regs`, `ram`, `queue`). |
| `cycles`  | array  | Per-cycle bus/pin trace; array of 11-element arrays (see below). |
| `hash`    | string | SHA1 hash of the test JSON; uniquely identifies a test in the suite. |
| `idx`     | int    | Index of the test within its file's JSON array. |

### `initial` / `final` sub-objects

- `regs`: object with keys `ax bx cx dx cs ss ds es sp bp si di ip flags`, all 16-bit
  unsigned integers. `initial.regs` is complete. **`final.regs` is sparse** — it contains
  only registers that changed; the whole `flags` value is included if *any* flag changed.
- `ram`: array of `[physical_address, byte_value]` pairs (20-bit address, 8-bit value).
  `initial.ram` lists every byte the test needs (instruction bytes at CS:IP, operands,
  stack, IVT entries for exception tests, plus 0x90 NOP fill for subsequent prefetch).
  **`final.ram` contains only changed bytes.** Since suite V1, `ram` entries are **not
  sorted by address** — they appear in the order in which they were accessed.
- `queue`: array of bytes in the prefetch queue. In `initial`, either empty `[]`
  (non-prefetched test) or a full 4-byte queue (V20 queue depth = 4). In `final`, the
  queue contents when the next instruction's first byte is read out. All post-instruction
  fetch bytes are 0x90 (NOP, 144), so the final queue is only NOPs, max 3 entries.

Every other test (half the set) executes from a full initial prefetch queue.

## Per-cycle format (`cycles`)

Each cycle entry is an **11-element** array. Note: the V20 README prose lists only 10
field names (it skips the BHE column), but actual data rows have 11 columns. The layout
is identical to the SingleStepTests 8088 V2 / 8086 suites, which document all 11
(index 5 = BHE, carried in the V20 format for 8086/8086-family compatibility and always
0 on the 8-bit-bus V20). Verified by inspecting `FA.json` and `E4.json`: every row has
len 11 and column 5 is always 0.

| Idx | Field | Type | Meaning / encoding |
|-----|-------|------|--------------------|
| 0 | Pin status bitfield | int | Bit 0 = **ALE** (Address Latch Enable, i8288 output; asserted on T1 — the multiplexed bus holds a valid 20-bit address only while ALE=1; consumer must latch it). Bit 1 = **INTR** input (not exercised). Bit 2 = **NMI** input (not exercised). Observed values: 0, 1. |
| 1 | Bus value (multiplexed AD bus) | int | Raw 20-bit state of the multiplexed address/data/status bus this cycle. Valid full address only when ALE asserted; on other cycles contains status/data mix. Consumer latches address on ALE. |
| 2 | Segment status | string | Which segment register is being used for the bus access; represents pins **S3/S4**. Values: `"CS"`, `"DS"`, `"ES"`, `"SS"`, or `"--"` (not valid, e.g. T1/Ti). |
| 3 | Memory status | string | 3 chars, i8288 memory command outputs, pattern `RAW` with `-` for inactive: `R` = **MRDC** (memory read command), `A` = **AMWC** (advanced memory write), `W` = **MWTC** (memory write). Active-low pins; a letter present means asserted. Memory read data is valid on T3 (or last Tw) while MRDC active; write data valid on T3/last Tw while AMWC active. |
| 4 | IO status | string | 3 chars, i8288 IO command outputs, pattern `RAW`: `R` = **IORC**, `A` = **AIOWC** (advanced IO write), `W` = **IOWC**. Same timing semantics as memory status. |
| 5 | BHE status | int | Byte-High-Enable. Not documented in the V20 README prose but present in every row; exists for format compatibility with the 8086 suite. Always 0 in the V20 set (8-bit bus, no BHE/UBE pin). In the 8086 suite this is the active-low BHE pin value indicating the upper data-bus byte is driven. |
| 6 | Data bus | int | Value of the low 8 bits of the multiplexed bus; valid on T3 (or last Tw) of a read/write cycle; represents the byte transferred. (16 bits in the 8086 suite.) |
| 7 | Bus status | string | Decoded m-cycle type from status pins **S0–S2** (octal decode): `"INTA"` (0), `"IOR"` (1), `"IOW"` (2), `"HALT"` (3), `"CODE"` (4, code fetch), `"MEMR"` (5), `"MEMW"` (6), `"PASV"` (7, passive/idle). |
| 8 | T-state | string | `"T1"`, `"T2"`, `"T3"`, `"Tw"` (wait), `"T4"`, or `"Ti"` (idle, no bus cycle). Not a real CPU output — derived from bus activity by the generator. Note: bus status returns to PASV on T3, so a 4-cycle bus transaction shows e.g. CODE,CODE,PASV,PASV across T1..T4. |
| 9 | Queue op status | string | Decoded **QS0/QS1** pins: `"F"` = First byte of an instruction/prefix read from queue; `"S"` = Subsequent byte (modrm/displacement/operand) read; `"E"` = queue Emptied/flushed; `"-"` = no queue op. Reflects an operation that occurred on the **previous** cycle. |
| 10 | Queue byte read | int | The byte read from the queue; valid only when queue op status is not `"-"`. |

Example row (T3 of a memory write, data byte 220 on the bus):

```json
[0, 72924, "SS", "-AW", "---", 0, 220, "PASV", "T3", "-", 0]
```

### Cycle-trace start/end conventions

- A trace **begins** at the cycle where the queue status indicates a First Byte (`F`) has
  been read. Prefixes each produce their own `F`; multiple `F`s appear until the first
  non-prefix opcode byte.
- A trace **ends** when the first byte of the *next* instruction is read from the queue
  (there is no "instruction end" signal, only the start of the next one). If the queue
  was empty at instruction end, extra fetch cycles lengthen the trace beyond documented
  timings; fully-prefetched tests with the next byte already queued should match "best
  case" documented timings.
- Division-exception tests (F6.6/F6.7/F7.6/F7.7): the trace continues until the first
  byte of the exception handler is fetched and read from the queue. The IVT entry for
  INT0 points to 0x0400. The pushed return address is that of the *next* instruction
  (8088/V20 "Type-0 interrupt" convention, unlike later Intel exceptions).

## metadata.json structure

Top-level keys: `github`, `version` ("1.0.2"), `syntax_version` (2), `cpu` ("V20"),
`cpu_detail`, `generator` ("arduino8088 v1.1"), `author`, `date`, and `opcodes`.

`opcodes` is an object with 282 entries, keyed by 2-char (`"00"`) or 4-char (`"0F10"`)
upper-case hex opcode strings. Each entry may contain:

- `status`: one of `extension` (the 0F escape byte itself), `normal`, `prefix`, `alias`,
  `undocumented`, `undefined`, `invalid` (causes the V20 to halt), `fpu` (ESC opcode).
  Observed counts: normal 243, fpu 10, prefix 10, extension 1, undocumented 1; 17 entries
  (the modrm-group opcodes) have no top-level `status` and carry a `reg` object instead.
- `arch`: architecture where the instruction was introduced: `"86"` (221), `"186"` (10),
  `"v30"` (32). Convention: "full-size" CPU name is used, so V20 instructions are tagged
  `v30`, 8088-era ones `86`.
- `flags`: 8-char string over the pattern `odiszapc` (O D I S Z A P C, MSB-first). A
  letter means that flag is **undefined** after the instruction; `.` means defined.
  E.g. shift-by-CL rotates: `"o......."`; MUL: `"...szap."`; DIV: `"o..szapc"`.
- `flags-mask`: 16-bit AND-mask that clears the undefined flag bits (e.g. 63487 =
  0xF7FF clears OF; 65519 = 0xFFEF clears AF; 63274 = 0xF72A clears O/S/Z/A/P/C).
  To ignore undefined flags: apply the mask to both the test's final `flags` and the
  emulator's flags before comparing. 40 entries carry `flags`/`flags-mask`.
- `reg`: for modrm-group opcodes (80–83, C0, C1, D0–D3, F6, F7, FE, FF): an object keyed
  by single-digit strings `"0"`–`"7"` (the modrm `reg` / opcode-extension field), each
  value having the same shape as a top-level opcode entry (`status`, `arch`, `flags`,
  `flags-mask`). Example: `F6` reg 1 is `alias` (of TEST, reg 0); `FE` reg 2–7 are
  `undefined`.

metadata.json does **not** store per-opcode test counts; counts follow the conventions
below.

## Initial queue state: the suspend-prefetch-until-empty rule

How consumers should run a test:

1. Override the emulated CPU's reset vector (normally FFFF:0000) to the test's initial
   CS:IP, load initial registers/RAM, and reset.
2. **Non-prefetched test** (`initial.queue == []`): just run; the instruction is fetched
   normally after reset.
3. **Prefetched test** (`initial.queue` has 4 bytes): install the given queue bytes after
   the reset routine flushes the queue (e.g. pass a byte vector into `cpu.reset()`).
   Because the queue is now full, the emulator must **suspend prefetching**. Add the
   queue length to PC/PFP (or adjust the reset-vector IP) so fetching resumes at the
   correct address. When the first instruction byte is read out of the queue, prefetch
   resumes (room is available). It takes **two cycles** to begin a fetch after reading
   from a full queue, so prefetched tests always start with **two `Ti` cycle states**.

## Test generation conventions

- **10,000 tests per opcode** by default. Exceptions:
  - String instructions: 5,000 (CX masked to 7 bits — see below).
  - Shift/rotate with CL count (D2, D3) or immediate count (C0, C1): 5,000.
  - ENTER (C8): 2,000 (large stack frames); nesting-level immediate masked mod 32
    (the V20, unlike Intel docs, does not take the modulus itself).
  - INC/DEC with fixed register operand: 1,000 (trivial).
  - Flag instructions (F5, F8–FD): 1,000 (trivial). (Confirmed: FA.json has 1,000 tests.)
- **Segment override prefixes** randomly prepended to a percentage of instructions,
  including where they have no effect (has caught real bugs).
- **String prefixes**: string instructions may be prepended with REP, REPE, REPNE, and
  the V20-specific **REPC/REPNC**. CX is masked to 7 bits for string ops (A4–A7, AA–AF)
  to bound test length. Non-V20 emulator consumers should filter out REPC/REPNC tests.
  On INS/OUTS (6C, 6D), REPC/REPNC act as plain REP.
- **Prefetch fill**: all bytes fetched beyond the instruction bytes are 0x90 (NOP).
- **Undefined-flag handling**: tests record the real hardware's flag results, including
  officially-undefined flags; use `metadata.json` `flags-mask` to ignore them. During
  IDIV exceptions, the flags word pushed to the stack contains undefined flags —
  consumers need a strategy to mask stacked flag words or skip memory-value validation
  when an exception is detected (heuristic: four successive reads from 0x00000–0x00003).
- **IO reads** always return 0xFF (6C, 6D, E4, E5, EC, ED).
- **Not exercised / omitted**: INTR, NMI, trap flag, wait states, LOCK (F0/F1), WAIT (9B),
  HLT (F4). BOUND (62) register-operand form (halts CPU), 8E with CS destination, 8F with
  reg!=0, r,r forms of LEA/LES/LDS (8D/C4/C5), FE.2–7, FF.3/FF.5 register forms (halt),
  0F31/0F33/0F39/0F3B memory-operand forms, 0F33/0F3B with AL/AH first operand, and
  CL of 0/255 for 0F20/0F22/0F26 (loop-counter underflow, ~1M cycles) are all excluded.
- REP prefixes prepended to 10% of IDIV tests (no effect on V20, sign-inverting on 8088).
- Note for the rig: when the V20 halts on an illegal form, **no HALT bus state is
  emitted**.
- In the sibling 8086 suite (relevant precedent): registers randomized with a 2% chance
  of any register being 0, and a 2% chance per test of memory being all 0x00 or 0xFF,
  to exercise zero/edge cases. The 8086 suite uses only 2,000 tests/opcode, treating
  itself as supplemental to the 8088 set for bus-behavior validation.

## Extending to V30 (uPD70116, 16-bit bus)

The 8086 suite (https://github.com/SingleStepTests/8086) is the direct precedent: it is
the 16-bit-bus sibling format and the V20 format already carries the extra column for it.
What changes and what stays:

### Stays identical
- Top-level schema: `name`, `bytes`, `initial`, `final`, `cycles`, `hash`, `idx`.
- Register set and representation (`ax..di, ip, flags`, 16-bit values); sparse `final`.
- `ram` as `[20-bit address, byte]` pairs, byte-granular even on a 16-bit bus (the 8086
  suite keeps byte-granular RAM entries; word transfers are expressed in the cycle
  data, not in `ram`).
- **Architectural results must match the V20 suite exactly**: for a given instruction and
  initial state, final registers, flags (including undefined-flag values — same microcode
  family), and memory bytes are the same on V20 and V30. The existing V20 `final` states
  are a cross-check for a V30 rig; only bus timing/cycle traces differ.
- metadata.json structure (`status`/`arch`/`flags`/`flags-mask`/`reg`) can be reused
  as-is; undefined-flag masks carry over.
- Queue op statuses (QS0/QS1: F/S/E/-), queue-byte-read field, cycle start/end
  conventions, the two-`Ti`-cycle start for prefetched tests, 0x90 prefetch fill.
- Bus status mnemonics INTA/IOR/IOW/HALT/CODE/MEMR/MEMW/PASV — the V30's raw status
  pins (NEC naming **BS0–BS2** in large/maximum mode, equivalent to Intel S0–S2) decode
  to the same octal table and drive an i8288-compatible bus controller, so the decoded
  string representation can stay. The rig captures BS0–BS2 raw and decodes on export.

### Changes for a 16-bit bus
- **Column 5 (BHE) becomes live**: the V30's **UBE** (Upper Byte Enable, active-low,
  NEC's equivalent of the 8086's BHE, multiplexed with status like BHE/S7) must be
  captured per cycle. Semantics per the 8086 suite: even address + BHE/UBE active =
  16-bit transfer; odd address + BHE/UBE active = 8-bit transfer on the high byte;
  even address + BHE/UBE inactive = 8-bit transfer on the low byte. Validators must
  mask the inactive half of the data bus.
- **Data bus (column 6) becomes 16-bit** (low 16 bits of the multiplexed bus).
- **Multiplexed bus (column 1)**: still 20 bits, but now AD0–AD15 + A16–A19/PS0–PS3
  (segment status pins). Address only valid under ALE, as before.
- **Segment status**: on the V30 the S3/S4-equivalents are PS0/PS1 (A17/A16 pins during
  T2–T4); same 2-bit ES/SS/CS/DS decode, same `"CS"/"DS"/"ES"/"SS"/"--"` strings.
- **Queue depth 6, not 4** (V30 = 6-byte queue like 8086; V20 = 4-byte like 8088). Code
  fetches are word-wide from even addresses, so a "full" initial queue depends on
  alignment: following the 8086 suite, instructions starting at odd addresses prefetch
  5 bytes, even addresses 6 bytes ("as full a queue as possible"). Final queue holds up
  to 5 NOPs (one read out). Consumers add the queue length to PC/PFP as before.
- **Fetch cadence differs**: word code fetches halve the number of CODE bus cycles;
  cycle traces will be shorter/differently-shaped than V20 traces for the same
  instruction. Odd-address word data accesses split into two byte transfers.
- **Address wrap**: physical address space wraps at 0xFFFFF (noted explicitly in the
  8086 README) — relevant for odd word accesses at the top of memory.
- Test counts: could follow the 8086 precedent (2,000/opcode, supplemental to the
  byte-bus set) or match V20 counts; decide based on rig throughput.
- The 8086 suite also ships a chunked binary format, **MOO** (Machine Opcode Operation,
  https://github.com/dbalsom/moo), for consumers without good JSON support — worth
  considering for the V30 suite alongside JSON.
- V20-specific content that carries over unchanged in scope: REPC/REPNC prefixes, 0F
  extended opcodes (with BRKEM still a special case), the F6.7/F7.7 REP-on-IDIV
  no-effect behavior, and the halt-on-invalid forms (still no HALT bus state emitted).

## Provenance

Fetched 2026-07-10 via curl:

- https://raw.githubusercontent.com/SingleStepTests/v20/main/README.md (V20 V1, version 1.0.3)
- https://raw.githubusercontent.com/SingleStepTests/v20/main/CHANGELOG.md (1.0.0 2024/05/25 … 1.0.3 2025/08/19)
- https://api.github.com/repos/SingleStepTests/v20/contents/ and .../contents/v1_native (file listing)
- https://raw.githubusercontent.com/SingleStepTests/v20/main/v1_native/metadata.json (and metadata.toml header)
- https://raw.githubusercontent.com/SingleStepTests/v20/main/v1_native/FA.json.gz (CLI, 1,000 tests — sample schema)
- https://raw.githubusercontent.com/SingleStepTests/v20/main/v1_native/E4.json.gz (IN AL,imm8 — IO-cycle and column-5 verification)
- https://raw.githubusercontent.com/SingleStepTests/8088/main/README.md (V2 format — names all 11 cycle fields incl. BHE)
- https://raw.githubusercontent.com/SingleStepTests/8086/main/README.md (16-bit-bus precedent: BHE semantics, queue 5/6, 2,000 tests/opcode, MOO format)

License: MIT (per repo LICENSE).

## Upstream data-quality finding — mirror-dependent cases (to report to dbalsom)

While using the SST v20 suite as an architectural oracle against our flat-1MB V30 sim
we found a small class of v20 cases that are INVALID on a flat 1 MB address space: their
operand reads land on 20-bit addresses that are NOT loaded in `initial.ram`, but alias
mod-64K onto addresses that ARE loaded. The capture rig evidently used 64 KB memory
mirrored across the 1 MB space, so the aliased (mirror-served) byte was returned; a
flat-memory consumer reads uninitialised memory instead and diverges.

Confirmed instances (arch-only, our sim): C4 idx 9495 (`les cx,[ds:bx+di]` - ES reads
0x9c6f-region unloaded, aliases 0x99c6f/0x89c70..), FF.5 idx 1611 (`jmpf [ss:bx+si]` -
the far-jump TARGET fetch aliases onto loaded bytes). For FF.5 (and far-control-flow
generally) this is widespread: the random 20-bit jump target aliases the loaded operand
mod-64K in ~all cases, so those forms are largely mirror-dependent by construction.

Count is small for straight-line memory ops (order 1-2 per 10-20k for LES/LDS-class) but
structural for indirect far transfers. Worth: (a) flagging to the maintainer as a
flat-memory-validity caveat, and (b) motivating our V30 contribution's stated
collision-freedom property (see tests/v30/*/README.md) as a differentiator. Detection is
cheap and host-side: two distinct 20-bit footprint addresses sharing their low 16 bits.
