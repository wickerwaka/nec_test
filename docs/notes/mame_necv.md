# MAME NEC V-series CPU core — survey notes

Purpose: use MAME as a *functional* (not cycle-exact) oracle for the V30 FPGA
recreation. This documents where everything lives in MAME's `src/devices/cpu/nec`
core, how it models timing, what V30-specific behavior it implements, and how we
could drive it headless.

Surveyed from `mamedev/mame` master, commit `2f09baf036f4c95b6a86407f7e826e6ca7dbaf78`
(committed 2026-07-11), fetched 2026-07-10. See Provenance section for URLs.

---

## 1. File map (`src/devices/cpu/nec/`)

| File | Contents |
|---|---|
| `nec.cpp` | Device glue: constructors for V20/V30/V33/V33A, reset/start state, interrupt entry (`nec_interrupt`, `nec_brk`, `nec_trap`), the prefetch-queue approximation (`do_prefetch`, `fetch`, `fetchop`), main loop `execute_run()` (nec.cpp:633-673), flag compress/expand for the debugger. |
| `nec.h` | `nec_common_device` class: register state, flag storage (lazy flags: `m_CarryVal`, `m_ZeroVal`, `m_SignVal`, `m_ParityVal`, `m_AuxVal`, `m_OverVal` as raw values, not a PSW word), prototypes for all 256 native handlers `i_*` plus 256 8080-mode handlers `i_*_80`, the three dispatch tables (`s_nec_instruction[256]`, `s_nec80_instruction[256]`, `s_GetEA[192]`), prefetch config fields (nec.h:113-120). |
| `necinstr.h` | The two 256-entry opcode dispatch tables (member-function-pointer arrays), one entry per first opcode byte, native mode and 8080-emulation mode. |
| `necinstr.hxx` | Bodies of all native-mode instruction handlers, one `OP(0xNN, i_name)` block per opcode, plus the REP machinery (`start_rep`, `cont_rep`, `do_repc/repnc/repe/repne`, necinstr.hxx:5-147) and the entire `0F` NEC-extension decoder inside `i_pre_nec` (necinstr.hxx:165-285). Cycle counts are inline in every handler via `CLK*` macros. |
| `nec80inst.hxx` | Bodies of the 8080-emulation-mode handlers (used after BRKEM sets MD=0), including `CALLN` (ED ED = native INT, ED FD = RETEM) at nec80inst.hxx:234-243. |
| `necea.h` | EA calculation: 24 `EA_xxx()` functions (one per mod/rm combination) and the 192-entry `s_GetEA` table indexed directly by the ModRM byte (mod 0/1/2 x rm 0-7; ModRM >= 0xC0 short-circuits to register access in `necmodrm.h`). Also computes `m_EO` (effective offset) separately from `m_EA` (linear address) — useful reference for our EA unit. |
| `necmodrm.h` | ModRM helper macros: `GetRMByte/Word`, `PutRM*`, `PutbackRM*`, `DEF_br8/wr16/r8b/r16w/ald8/axd16` operand-setup macros, and the `Mod_RM` reg/rm lookup tables built in `device_start()`. |
| `necmacro.h` | ALU/flag macros (ADD/SUB/ADC/SBB/logic, INC/DEC, rotates/shifts, ADJ4/ADJB for DAA-family, ADD4S/SUB4S/CMP4S BCD strings) and the four division macros `DIVUB/DIVB/DIVUW/DIVW` with the divide-overflow register/flag semantics (necmacro.h:169-232). |
| `necpriv.ipp` | Core-private defines: chip-type constants (`V33_TYPE=0, V30_TYPE=8, V20_TYPE=16` — steps of 8 for the cycle-table bit-shift trick), vector numbers, register enums, flag test macros, memory/IO access macros, `PUSH/POP`, `BRKEM`/`BRKXA` macros, `CompressFlags`/`ExpandFlags` (PSW bit layout incl. always-1 bits), and the five cycle-count macros `CLK/CLKS/CLKW/CLKM/CLKR` (necpriv.ipp:100-115). |
| `necdasm.cpp/.h` | Disassembler (copyright Aaron Giles), mode-aware (native vs 8080 via `config::get_mode()`); used by `unidasm`. |
| `v25*.{h,cpp,hxx,ipp}` | V25/V35 (uPD70320/70330) core — a *separate copy* of the interpreter with register banks in on-chip RAM, SFRs, and V25 extras (BRKCS, TSKSW, MOVSPA/MOVSPB, BTCLR, STOP...). Not needed for V30 work but shares macro structure. |
| `v5x.{h,cpp}` | V40/V50 (uPD70208/70216): nec_common_device plus on-chip peripherals (ICU/DMAU/TCU/SCU). |

Related, outside this directory:

- `src/devices/cpu/v30mz/v30mz.{cpp,h}` — separate V30MZ core (see section 6).
- `src/tools/unidasm.cpp` — standalone disassembler; arch `"nec"` registered at unidasm.cpp:568 (mode configurable native/8080 via `nec_unidasm_t` config at :351).

## 2. Timing model for V30

- Every instruction handler charges cycles inline with `CLK*` macros
  (necpriv.ipp:100-115). There is no central cycle table; the "table" is the
  triplet arguments embedded at each opcode site in `necinstr.hxx`:
  - `CLK(n)` — same count for all chips.
  - `CLKS(v20,v30,v33)` — per-chip counts packed into one word, selected by
    `>> m_chip_type` (hence chip-type constants in steps of 8 bits).
  - `CLKW(...)` — word memory access, different counts for odd vs even address
    (V30's 16-bit bus penalty for odd addresses); takes 6 counts + the address.
  - `CLKM(...)` — reg vs mem forms of a ModRM instruction.
  - `CLKR(...)` — reg vs mem, mem further split odd/even address.
- The values are NEC-datasheet cycle counts (uPD70108/70116 user's manual
  numbers) as entered by Bryan McPhail circa 2000-2003; the header comment
  claims "99% accurate cycle counts" but flags known odd/even-operand cases as
  wrong (nec.cpp:75-103). Several 0F-range instructions (INS/EXT bit-field)
  carry comments that hardware cycle behavior is undocumented and the max
  datasheet value is charged (necinstr.hxx:200-278).
- Prefetch: modeled only approximately. V30 is constructed with
  `prefetch_size=6` bytes, `prefetch_cycles=2` per byte (nec.cpp:148-151;
  V20 is 4 bytes at 4 cycles). Each `fetch()` decrements a byte counter;
  after each instruction `do_prefetch()` (nec.cpp:226-255) refills the counter
  out of the cycles the instruction already consumed, charging extra cycles
  only when the queue ran dry. The code comments explicitly say it is "not
  accurate" — it does not fetch words, has no bus-arbitration with data
  accesses, and `CHANGE_PC` / `EMPTY_PREfetch()` (necpriv.ipp:72,86) simply
  zeroes the counter on any branch. Bus wait states and odd-address PUSH/POP
  penalties are not emulated (necpriv.ipp:107-108).
- Conclusion for our project: MAME/nec is usable as a *functional* oracle and a
  rough datasheet-cycle cross-check, but is **not** a cycle-accurate reference;
  our silicon measurements supersede it everywhere they disagree.

## 3. V30/NEC-specific instructions and behaviors implemented

- **0F-prefix NEC extensions** — decoded by a `switch(fetch())` inside
  `i_pre_nec` (necinstr.hxx:165-285). Implemented second bytes:
  - `10/11` TEST1, `12/13` CLR1, `14/15` SET1, `16/17` NOT1 (CL-count forms);
    `18-1F` same with imm4 count. TEST1 clears CY/V and sets Z from the bit.
  - `20` ADD4S, `22` SUB4S, `26` CMP4S — packed-BCD string ops (necmacro.h:234-316);
    note MAME computes Z as "any nonzero digit" accumulated per byte, CY as
    decimal borrow/carry.
  - `28` ROL4, `2A` ROR4 (4-bit rotates through AL).
  - `31/33/39/3B` INS/EXT reg,reg and reg,imm4 bit-field insert/extract
    (necinstr.hxx:190-279) — with comments listing measured/datasheet min-max
    cycle ranges per chip.
  - `E0/F0` BRKXA/RETXA (V33 only; logged as error on V20/V30 — necpriv.ipp:95),
    `FF` BRKEM (V20/V30 only, rejected on V33 — necpriv.ipp:96).
  - Any other second byte: logged "Unknown V20 instruction", no exception —
    real-hardware undefined-opcode behavior is *not* modeled.
- **BRKEM / 8080 emulation mode**: `nec_brk()` (nec.cpp:353-366) clears MD,
  pushes PSW/PS/IP, vectors like an interrupt. While `m_MF==0`, `execute_run`
  dispatches through `s_nec80_instruction` (nec.cpp:666-669), a full 8080
  interpreter (`nec80inst.hxx`) where H/L maps to BW, SP(8080) maps to BP, and
  8080 PUSH/POP use DS0:BP (`PUSH80/POP80`, necpriv.ipp:92-93). `CALLN`
  (ED ED xx = native interrupt from emulation mode) and `RETEM` (ED FD) are in
  nec80inst.hxx:234-243. 8080-mode cycle counts are placeholder `CLK(1)`s —
  useless for timing. MD is bit 15 of the PSW (`CompressFlags`,
  necpriv.ipp:118-120); `ExpandFlags` ORs in `m_em` so POPF can't clear MD
  outside emulation mode (necpriv.ipp:133).
- **REPC (65h) / REPNC (64h)**: full implementations `do_repc/do_repnc`
  (necinstr.hxx:37-91), looping string ops while CY set / clear. The REP
  machinery is interruptible: state is parked in `m_rep_params`/`m_rep_ip`
  and resumed by `cont_rep()` — note MAME decrements CW per iteration and
  re-enters, rather than re-fetching the prefix like real hardware.
- **Undefined/x86-differing opcodes**: `63h, 66h, 67h, F1h` etc. dispatch to
  `i_invalid` (CLK(10), log only). `D6h` is SETALC (implemented,
  necinstr.hxx:714). `D8-DFh` FPO1/FPO2 consume ModRM and 2 clocks (`i_fpo`).
  `C0/C1` are the shift-imm forms; `0x30 /6` shift subcode ("SHLA") logged as
  undefined. ARPL/`63h` does not exist (correct for NEC).
- **Division semantics** (necmacro.h:169-232): on divide overflow the V-series
  pushes vector 0 *and* — per the `m_has_div_quirk` flag, true for V20/V30 —
  sets CY and V to `!overflow` (i.e. flags say whether it did *not* overflow);
  destination registers are left unchanged on overflow for V30/V35 ("confirmed
  by testing"), while V33 stores a truncated result. The comment at
  necmacro.h:169-172 cites testing *by wickerwaka* (this project) and MAME PR
  #15620 — i.e. this area is already partially synced with our measurements.
  Divide-by-zero clears CY/V then raises vector 0 without touching registers
  (necinstr.hxx:750-757). AAM (`D4h`) does not divide-check (immediate byte
  fetched and ignored, always /10 — necinstr.hxx:712).
- **Flags**: PSW bits 12-14 always read 1, bit 1 always 1, bit 15 = MD
  (necpriv.ipp:118-120). NEC-correct flag results are claimed vs i86
  (nec.cpp:80-81): e.g. AAA/AAS adjust AH by ±2 in the >0xF9/<6 edge cases
  (necinstr.hxx:330,339), rotates set V from `src^dst` MSB on 1-bit forms
  (necinstr.hxx:654-676), MUL/IMUL leave Z/S/P unset (only CY/V computed),
  shifts by CL don't mask the count to 5 bits (NEC behavior: full 8-bit count,
  see `c=Breg(CL)` loops, necinstr.hxx:680-710). *Undefined* flag values after
  MUL/DIV/etc are not deliberately modeled beyond this — another area where
  silicon measurement wins.
- **Interrupt niceties**: POP SS and MOV sreg set `m_no_interrupt=1`
  (necinstr.hxx:294,524); the un-interruptible shadow also follows prefixes
  implicitly (prefix handlers re-dispatch inline). TF trap executes one
  instruction then vectors (`nec_trap`, nec.cpp:347-351). POLL pin (`9Bh WAIT`)
  supported via input line (nec.cpp:539).

## 4. Decode structure (test-coverage checklist)

Dispatch is a flat 256-entry function-pointer table on the first byte
(`necinstr.h`), with second-level `switch` decoding on:

- `0Fh` + second byte (NEC extension group, list in section 3).
- ModRM `reg` field (`/r` groups): `80/81/82/83` (ALU-imm group),
  `8Ch/8Eh` (sreg moves), `C0/C1/D0/D1/D2/D3` (shift/rotate group, subcode
  `/6` undefined), `F6/F7` (TEST/NOT/NEG/MULU/MUL/DIVU/DIV; `/1` undefined),
  `FE` (INC/DEC only), `FF` (INC/DEC/CALL/CALL FAR/JMP/JMP FAR/PUSH; `/7`
  undefined).
- Prefix bytes handled by re-dispatch: `26/2E/36/3E` segment overrides
  (set `m_seg_prefix` + `m_prefix_base`, then call next handler inline),
  `F0` LOCK (no-op + no_interrupt), `F2/F3/64/65` REP family (only valid over
  `6C-6F`, `A4-A7`, `AA-AF`; anything else logged and executed bare).
- EA: 192-entry table on full ModRM byte for mod<3 (necea.h), 24 distinct
  functions = {BW+IX, BW+IY, BP+IX, BP+IY, IX, IY, d16|BP, BW} x
  {disp0, disp8, disp16}; default segment SS for BP-based forms, DS0 otherwise,
  override only replaces DS0/SS defaults (`DefaultBase`, necpriv.ipp:76).

Enumerating test vectors directly off `s_nec_instruction[]` plus the
sub-switches above gives a complete opcode-form checklist; the table entries
map 1:1 to handler names that encode the form (e.g. `i_add_br8` = ADD r/m8,r8).

## 5. Running MAME headless as an oracle

- **Disassembly**: build the standalone tool `unidasm` (`make TOOLS=1` builds
  it, or `make unidasm`); `unidasm file.bin -arch nec [-mode 1 for 8080 mode]`.
  Arch `"nec"` at unidasm.cpp:568. Good for cross-checking our decoder tables
  and for labeling captured traces. (`v25`/`v30mz` share the same
  disassembler; there is no separate arch entry needed.)
- **No built-in single-instruction harness**: MAME has no per-CPU instruction
  test runner in-tree. Realistic options, in increasing effort:
  1. **Lua scripting**: run any V30-based driver headless
     (`mame <driver> -video none -sound none -nothrottle -autoboot_script test.lua`);
     Lua can read/write memory spaces, set registers (`manager.machine.devices[":maincpu"].state`),
     step (`emu.step()` / debugger `cpu:debug():step()`), and dump state —
     enough to build a JSON-in/JSON-out single-step oracle without touching C++.
  2. **Thin C++ driver**: a minimal machine in MAME (V30 + 1 MB RAM +
     stub IO handlers) that loads a test blob, runs N instructions, and prints
     state. The nec core has no dependencies beyond the usual `emu.h` device
     framework, so this is a small driver file; pairing it with the Lua console
     is the most robust route.
  3. Extracting `nec.cpp` out of MAME to run standalone is *not* practical:
     it is welded to `cpu_device`, `address_space`, `memory_access` caches, and
     the save-state system.
- **Existing external test corpora** worth knowing about: the SingleStepTests /
  ProcessorTests project publishes hardware-generated per-instruction JSON test
  sets for 8088 and V20 (and a V30MZ set exists, generated from WonderSwan
  hardware). These test the same instruction space and can be replayed against
  both MAME and our RTL. (Verify current repo names before depending on them.)
- Caveats when using MAME as oracle: prefetch/queue timing is approximate
  (section 2); REP interruption granularity differs from hardware; undefined
  opcodes just log; undefined flag bits after MUL/DIV not modeled. Compare
  architectural state (registers, flags per documented mask, memory), not
  cycle counts.

## 6. The separate v30mz core (`src/devices/cpu/v30mz/`)

- `v30mz.cpp` (~3.5k lines) + `v30mz.h`; license BSD-3-Clause, copyright
  Wilbert Pol, Bryan McPhail. Written for the WonderSwan's V30MZ (a
  re-implemented, much faster pipeline — different microarchitecture from V30).
- Differences from the nec core:
  - Single giant `switch` per opcode byte inside the execute loop instead of
    function-pointer tables.
  - **Real byte-FIFO prefetch queue** (8 bytes modeled; docs say 8 words) with
    per-byte bus fetches and `init_prefetch()` on branches — closer in spirit
    to what our RTL needs, though tuned to V30MZ bus behavior, not V30.
  - Cycle counts are V30MZ counts (mostly 1-3 clocks per op, `clk(1)` style) —
    **not** applicable to V30.
  - No 8080 emulation mode; `0Fh` treated as a 1-clock nop-ish prefix
    (v30mz.cpp:1561) — the V30MZ drops the NEC 0F extensions; `REPC/REPNC`
    hit `fatalerror` (v30mz.cpp:2095,2136).
- Useful to us mainly as a second functional implementation and as an example
  of a modeled prefetch FIFO; the nec core is the right oracle for V30.

## 7. Licensing

- All surveyed core files carry SPDX-style headers `// license:BSD-3-Clause`:
  `nec.cpp`, `nec.h`, `necinstr.h/.hxx`, `nec80inst.hxx`, `necea.h`,
  `necmacro.h`, `necmodrm.h`, `necpriv.ipp` (copyright-holders: Bryan McPhail),
  `necdasm.cpp/.h` (Aaron Giles), `v30mz.cpp/.h` (Wilbert Pol, Bryan McPhail).
- MAME as a whole is GPL-2.0+, but these files are individually BSD-3-Clause.
  BSD-3-Clause is one-way compatible with GPLv2: we may port/derive code from
  these files into our GPLv2 repo, provided we retain the BSD copyright notice
  and attribution for derived portions. (Summaries/facts in these notes need no
  license carriage; only literal or closely-derived code does.)
- If we ever pull from other MAME files, re-check each header — some MAME
  sources are GPL-2.0+ per-file and would also be fine for us, but attribution
  requirements differ.

## 8. Provenance

- Repo: https://github.com/mamedev/mame — branch `master`, commit
  `2f09baf036f4c95b6a86407f7e826e6ca7dbaf78` (2026-07-11 UTC).
- Directory listing: https://api.github.com/repos/mamedev/mame/contents/src/devices/cpu/nec
- Files fetched 2026-07-10 via `https://raw.githubusercontent.com/mamedev/mame/master/src/devices/cpu/nec/<file>`:
  `nec.cpp`, `nec.h`, `necinstr.h`, `necinstr.hxx`, `nec80inst.hxx`, `necea.h`,
  `necmacro.h`, `necmodrm.h`, `necpriv.ipp`, `necdasm.cpp`, `necdasm.h`;
  plus `src/devices/cpu/v30mz/v30mz.{cpp,h}` and `src/tools/unidasm.cpp`.
- Line references in this document are against that commit.
