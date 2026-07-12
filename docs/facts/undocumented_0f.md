# Undocumented 0F-space opcodes on the real μPD70116C-8 (Campaign 2 mission 9)

Survey of 16 undocumented second bytes of the 0F extension space, spread
across 0x00-0xE4. Method: `sw/probe_0f.py all` — execute `0F xx` followed by
four 1-byte markers (INC AW/CW/DW/BW at offsets 2..5); the incremented
markers give the consumed length, register/PSW deltas and non-code bus
transactions give side effects. Runaways were then classified from raw
4096-record captures (`sw/probe_0f.py followup`). Conditions: max mode,
4 MHz, 0 waits; inject AW=1000 CW=2000 DW=3000 BW=0800 BP=0900 IX=0010
IY=0020 SP=0F00, code at 0000:0500. Data: `sw/testdata/0f_log.jsonl`,
`sw/testdata/0f_run.out` (2026-07-11).

Documented bytes excluded (verified against instructions.json): 10-1F
(TEST1/NOT1/CLR1/SET1), 20/22/26 (ADD4S/SUB4S/CMP4S), 28/2A (ROL4/ROR4),
31/33/39/3B (INS/EXT), FF (BRKEM). 0F E0/F0 (V33 BRKXA/RETXA) not risked.

## Results

| 2nd byte | Class | Length | Observed behavior |
|---|---|---|---|
| 00, 04, 08, 0C | no-op | 2 | no register, flag, or bus effect |
| 21, 27 | no-op | 2 | no register, flag, or bus effect |
| 24 | CMP4S-like string op | 2 | reads CL/2 bytes from [IX] and [IY] (byte accesses, ascending), writes nothing, IX/IY/CW/flags unchanged on tested operands. With CL=0 it under-flows into a ~256-digit loop that outruns the capture window — same CL=0 edge the V20 suite excludes for the documented 4S ops |
| 2C | ROR4/EXT-neighborhood hybrid | 4 (modrm+disp8 consumed) | reads modrm EA ([BW+IX+disp8] = 00851), then byte read-read-write at **[IY]** (00020); no flag/register change |
| 30 | INS-like | 4 (modrm+disp8 consumed) | byte read-read-write at [IY]; no EA access, no flag/register change (documented INS = 0F 31 writes a bit field at [IY]; this behaves like a byte-form sibling) |
| 34 | **silent lockup** | n/a | 5 code fetches after the anchor, then the bus goes permanently quiet — no HALT bus state (matches the V20 "halts on illegal form with no HALT cycle" precedent). Host reset required |
| 40, 60, 80, A0, C0, E4 | **BRKEM alias** | 3 (0F xx imm8) | full BRKEM semantics: reads IVT entry `imm8` (2 MEMR), pushes PSW, PS, PC=addr+3 (3 MEMW at SP-2/4/6), clears MD and **enters 8080 emulation mode** at the vector target |

## The BRKEM-alias finding (0F 40-0xE4 sampled)

Every probed second byte >= 0x40 decodes exactly like BRKEM (documented
encoding 0F FF imm8):

- Bus signature: MEMR IVT[4*imm8], IVT[4*imm8+2]; MEMW PSW@SP-2, PS@SP-4,
  PC@SP-6. With third byte 0x40 all six read IVT 0x100 (vector 64); with
  third byte 0x06 the read moves to 0x18 (vector 6) — **the vector is the
  third byte**, and pushed PC = instruction address + 3 in both cases (no
  modrm decoding of the third byte).
- Post-trap execution is in 8080 emulation mode, proven from the capture:
  the store stub's `E7 FE` (x86 OUT 0xFE,AW) executed as 8080 **RST 4** —
  pushed 0x050D (return address after a 1-byte RST) to the **8080 stack at
  BP-2** (write at 008FE with BP=0900; V30 8080-mode SP maps to BP) and
  jumped to 8080 vector 0x0020. NOP fill (0x90 = 8080 NOP) then sleds until
  the per-run host reset.
- Implication: the V30 decodes BRKEM as `0F [second byte in a large
  don't-care class] imm8`; 0F FF is just the documented encoding. There is
  no invalid-opcode trap in this space — unknown 0F bytes either no-op,
  alias a neighbor family, lock up (0F 34), or fall into BRKEM.
- These runs are the first (accidental) 8080-mode entries on this harness;
  they were survivable only because `v30ctl` host-resets between runs.
  Deliberate 8080-mode work stays blocked on the recovery-path
  infrastructure (ROADMAP standing item; OPEN_QUESTIONS Q13).

## Length-inference notes

Marker arithmetic was consistent in every executed case (trailing markers
only), and the 0F 2C/30 length of 4 matches modrm 0x40 = mod01 (+disp8).
The BRKEM aliases' length of 3 comes from the pushed return PC, which is
the authoritative measure when execution never returns to the markers.

## Not yet probed

Second-byte coverage is 16 of ~215 undocumented values; the trap class was
sampled at 6 points and the no-op class at 6. A denser sweep (especially
0x00-0x3F fine structure: which bytes take modrm, where the no-op/string/
INS/EXT/lockup boundaries sit, and whether 0x35-0x3F lock like 0x34) is
mechanical with `probe_0f.py` but was out of scope for this pass.
