# INS/OUTS (6C-6F) implementation design + shared iord-sequence format

Derived from the v20 oracle data (not 8086 docs). These four opcodes are UNIMPLEMENTED
in the core today (no decode -> park/runaway, 100% of all 14000 v20 cases).

## Semantics (v20-derived)

- 6C INSB / 6D INSW: read port DW (I/O read, IOR cycle) -> write ES:IY (mem); IY += step.
- 6E OUTSB / 6F OUTSW: read DS(sov):IX (mem) -> write port DW (I/O write, IOW cycle); IX += step.
- step = (DF ? -width : +width), width = 1 (byte 6C/6E) or 2 (word 6D/6F). 16-bit offset
  arithmetic (wraps in 64K), like the other string ops.
- Flags UNCHANGED (v20 data: only IX/IY, CW on REP, and IP move).
- Segment override applies to the OUTS SOURCE (DS default); INS dest is always ES:IY (no override).
- REP: prefixes F3 (REP), F2 (REPNZ), AND the V20 REPC/REPNC (0x65/0x64) ALL repeat CW
  times for INS/OUTS (the carry/zero condition only gates CMPS/SCAS). CW -> 0; IX/IY += step*CW.
  Non-REP single: one element, CW unchanged.

## RTL plan (model on the existing string micro-loop, S_STR*)

OUTS (do first, immediately gateable - no port-read data needed):
- Add `op_outstr = opc==8'h6E || opc==8'h6F`, fold into `op_str`, `is_word_t` (6F), `wr_dst`.
- New path: read DS(sov):IX first (like LODS/op_lodstr) -> on read done, issue an I/O WRITE
  cycle to port DW with the read data (like OUT op_out, bus status = IO write) -> advance IX
  by str_step -> if REP and CW>1, decrement CW and loop; else retire. Reuse rep_en / the CW=0
  early-out. Timing: fit the element cadence against the 6E/6F goldens (arch gate first).

INS (after the TB iord-sequence extension):
- Add `op_instr = opc==8'h6C || opc==8'h6D`. Path: I/O READ from port DW -> write ES:IY (mem)
  with the read data -> advance IY -> REP loop. The read data comes from the port-serve
  mechanism (below), one value per iteration.

## Shared iord-sequence format (ONE representation for emitter + TB + board image + upstream)

A per-case ORDERED LIST of 16-bit port-read values, consumed one-per-I/O-read in order.
Schema (extends the existing single `iord`): a test case MAY carry
    "iords": [v0, v1, ...]        # 16-bit ints, one per IOR the case performs
Single-IOR cases (IN E4/E5/EC/ED) keep the scalar `iord`; multi-IOR cases (INS, REP INS)
use `iords`. TB backdoor: load the sequence per case; each IOR cycle pops the next value
(byte forms take the low 8 bits). Board harness: serve the same sequence via the same
backdoor path (extends today's single-`iord` IOR serving - see v0.1 README limitation).

RECOVERY from capture data (how consumers, and we-from-v20, reconstruct the sequence):
each INS iteration writes the port value to ES:IY, so `final.ram` at the ES:IY stride IS
the port sequence, in order; cross-check against the IOR data column of the `cycles` rows
(col 6 at IOR read points). For non-overlapping writes these agree exactly; only DF/wrap
cases where writes overlap are ambiguous (count + report if > a handful). This makes INS
fully deterministic and the `iords` field recoverable by any consumer - a stated part of
the V30 upstream schema.

## v0.2/10k form-list addition
6C/6D/6E/6F are absent from v0.1 and v0.2 (core lacked them). BOOKED: add all four to the
v0.2/10k form list once OUTS+INS RTL and the board port-serve extension land - the upstream
suite should ship string-I/O.
