# Campaign 3 closure block — final checkpoint (handoff document)

Successor: read this + ROADMAP.md. Board = root@mister-nec (health:
`python3 sw/v30run.py echo`). NEVER reprogram the FPGA; one board user
at a time. NO background chains are running (batch-3 emission finished;
fitwatch/chain scripts stopped). Serve v2 (delta/partial-capture) is
DEPLOYED and validated on the board (31 ms/case).

## MISSION Q FINAL STATUS (grand regression, 311 forms x 500/200)
TOTAL: 153003/155500 cycle-exact (98.4%); arch 153402 (98.65%).
Excluding the 4 unimplemented INS/EXT forms: 153003/153500 = 99.68%.

Every documented-opcode form is validated 100% cycle-exact EXCEPT:
- 0F31/33/39/3B INS/EXT — NOT IMPLEMENTED (see below for a running
  start; tranches in tests/v30/v0.1).
- Parked residuals (laws documented in the RTL headers + git log):
  - 8F.0 413/500 (arch 473): pop-end occupancy off-by-one class +
    mod3 ghost-read ADDRESS from an unmodeled internal latch (final
    captured row only). QUIRK validated: 8F/0 mod3 discards the
    popped data (SP+2 only).
  - C8 276/500 (arch 432): level>=1 frame-push slot bimodality;
    suspected T4-end-eval-after-blocked-T3 BIU rule (see a1240b8).
    Arch semantics = 186 ENTER, 100% verified.
  - FF.2 489, FF.6 473: pre-first-T1 carried-phase artifact (TB
    pre-capture grid alignment, not a core law).
  - 0F22 354 (arch 499), 0F26 498: SUB4S/CMP4S siblings, parked since
    campaign start (one ±1 law + 2-case discriminator).

## INS/EXT decoded so far (running start for the implementer)
0F31 /r = INS reg8(rm), reg8(reg); 0F39 = INS reg8, imm4;
0F33 /r = EXT reg8(rm), reg8(reg); 0F3B = EXT reg8, imm4.
Verified on 0F31 idx0: bit-string INSERT at ES:IY, bit offset =
rm-reg (low 4 bits, UPDATED += len), field length = reg/imm low 4
bits + 1, source = AW low bits. Bus shape (byte-aligned case): read
word at ES:IY, ~20-cycle burn, RE-READ same word, ~25-cycle burn,
byte write of the modified byte; offset reg advances by len (mod 16
with IY carry). EXT mirrors into AW. Burns are data-dependent (EXT
worst case 1069 cycles - internal bit loop). Cross-byte fields span
two bytes (IY advances). Suggested approach: structural first pass
with a shift loop burn state (S_SHWAIT pattern), then fit the burn
laws from Counter() sweeps like the shift family.

## Board / pipeline state
- All planned tranches (batches 1-3 + addenda) are LANDED and in
  tests/v30/v0.1 (ground truth). No emissions pending.
- sw/v30ctl.py on-board = serve v2 ("OK SERVE v2" banner); v1 is in
  git history if a revert is ever needed.

## Infrastructure notes for the successor
- New BIU machinery added this block: defer_t4 (+eu_soon), bus_phase
  (2-cycle grid parity, committed-pending idle = phase-1), bus_t4,
  bus_ts (full T-state export), flush_fast (mid-cycle far-flush
  commit). EU: eu_fwd now also used by the 8F.0/C8 pipelined copy
  writes; ghost-access latches iret_pw/popr_pend + dbg_pend export;
  the TB has a 16-cycle post-case settle window that re-latches the
  final registers (except IP) when dbg_pend was up at the close.
- Fit-loop recipe: `python3 sw/check_core.py --opcodes X --keep`,
  diff via build_rows_sim/diff_rows (cols 7=busstat 8=tstate 9=qop),
  adjust dly constants, rebuild
  (verilator --binary --timing -DV30_BACKDOOR -Wall
  -Wno-UNUSEDSIGNAL -Wno-VARHIDDEN --top-module tb_v30_core -Mdir
  hdl/tb/obj_dir hdl/tb/tb_v30_core.sv hdl/rtl/core/v30_core.sv
  hdl/rtl/core/v30_biu.sv hdl/rtl/core/v30_eu.sv), rescore; commit
  per family; keep neighbors green.

## Handoff plan (coordinator directive)
Mission Q is COMPLETE except the INS/EXT implementation + the parked
residuals above. Missions S (sequence fuzz: sw/gen_seq.py +
sw/check_seq.py, self-tested, board side untested) and R (ROADMAP
update, campaign close-out report) go to the fresh agent, per the
standing directive. Suggested order for the successor: INS/EXT
build, then Mission S, then R.
