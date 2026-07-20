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

## Corrections found during implementation (verified at integration, 2026-07-18)

1. **V20 traces record only T1/T2 rows for IOR cycles** - the returned port byte is
   ABSENT from the cycles data (the V20 trace stops before the data phase). So the iord
   sequence is recovered from `final.ram` (INS writes each port value to ES:IY) with a
   last-writer overlap ambiguity guard, NOT from a cycles data column. Verified on regen:
   **0 ambiguous cases across 130,681 IORs** (6C 66,557 + 6D 64,124).
2. **Every INS port value in the entire SST v20 suite is open-bus 0xFF/0xFFFF** - the
   capture rig had no I/O device on the bus. CONSEQUENCE for our V30 contribution: our
   board harness CAN serve real, varied per-case port data via the iord/iords mechanism,
   so our contributed INS cases can carry meaningful port-read sequences - strictly RICHER
   than upstream. The 6C-6F form-addition plan should vary port data per case and emit the
   `iords` list in the JSON (schema extension above).
3. **Byte-form INS with an ODD port address reads the HIGH data-bus lane** - so served
   `iords` values need both-lane duplication (value v -> v * 0x0101) for byte forms so the
   high lane carries the byte. The board-side iord serving for the future 6C-6F emission
   must apply the same lane duplication (verify against the IN-class E4/E5 board path).

## Emitter build + sim-validation gate (2026-07-18, during the v0.3 10k run)

Built the EMITTER side (the sim-side iords infra - extract_iords.py, check_core, TB -
already existed; the RTL executes INS/OUTS). Committed:

- `emit_suite.py`: SPEC gains `strio` ('ins'|'outs'). OPCODES: 6C/6D/6E/6F singles +
  all four repeat prefixes (F3/F2/65/64) + OUTS seg-override reps (26.6E/2E.6F/36.6E) =
  **23 forms**, `STRIO_OPS`. `gen_case` strio path: OUTS reads DS:IX (seg-overridable),
  INS reads port DW -> ES:IY (dest not overridable), IX/IY step +/-width per DF, REP CW
  distribution small-dominated with a tail into the emit cap window. INS emits the
  per-element `iords` (byte forms both-lane, word forms full 16-bit).
- **Word I/O to an ODD port splits into two byte bus cycles** (like odd-address memory
  words), breaking the one-IOR-per-element `iords` invariant. Word forms are constrained
  to EVEN ports; byte forms keep odd ports (they exercise the high data lane cleanly in
  ONE cycle). Odd-port WORD-split INS/OUTS (2 IORs/element, iords-per-cycle) is a noted
  follow-up if that coverage is wanted.

- `validate_strio_sim.py`: board-free gate. Drives the Verilator TB (which serves the
  iords sequence) with generated cases, checks clean exercise without a golden: retirement,
  REP drains CW to 0, IX/IY advance = sign(DF)*width*count, IO bus-cycle count == count,
  INS-served bytes land at ES:IY. **1380/1380 clean across all 23 forms** (per=60).
  Confirms all four repeat prefixes act identically on non-compare string I/O.

## Pre-registered tranche gate (execute AFTER the v0.3 347-form 10k completes)

1. Deploy the board serve-protocol iords SEQUENCE (v30ctl.py + v30run.py + harness FIFO
   in the bitstream) - a POST-10k bitstream+firmware change per standing constraint. Wire
   `emit_case` -> `run_image` -> `run()` to pass `iords`. Verify byte-lane duplication
   against the IN-class (E4/E5/EC/ED) board path. Re-run byte-identity acceptance after the
   board change.
2. Emit 6C-6F x10000 into v0.3 (seed base v30-v0.2, `--resume`), truth source = socket.
3. `extract_iords.py` sidecars for 6C/6D (ambiguity count must be ~0, as on the v20 regen).
4. Three-way flat-validity pass (check_core --no-mirror vs +mirror) over the new forms.
5. `validate_suite.py` over the whole of v0.3 including 6C-6F (schema/hash/independent
   RAM reconstruction/cold-pf/boundaries all green).
6. Update the v0.3 README: drop 6C-6F from "Known limitations", document the iords schema
   field and INS port-read provenance.

## Split tranche (coordinator decision, 2026-07-19) — OUTS first (no deploy), INS after FIFO deploy

The board serve-protocol iords SEQUENCE is not yet in the harness bitstream, so the
tranche is SPLIT to unblock the board without waiting on the FIFO deploy.

**Premise verified:** OUTS (6E/6F + rep/seg-ovr) needs NO port serving — the chip DRIVES
the IOW data and the harness only OBSERVES it (confirmed: OUT forms E6/E7/EE/EF already
emit on the current board with chip-driven IOW data captured in the cycles). INS (6C/6D)
reads the port and DOES need the harness to serve per-element data (the FIFO).

### Phase A — OUTS tranche ×10k (NOW, no deploy). Pre-registered gate:
- 13 forms: 6E 6F + F3/F2/65/64 x{6E,6F} + 26.6E 2E.6F 36.6E; seed base v30-v0.2, socket.
- G-OUTS-1: validate_suite.py over the 13 forms -> 0 failures.
- G-OUTS-2: three-way flat-validity pass over the 13 forms; mirror-dependent -> confined
  re-emit (--validate); neither -> KEEP + append to v03_divergence_ledger.md.
- No extract_iords (OUTS performs no IOR).

### Phase B — iords-FIFO harness deploy (parallel RTL work, its own phase):
- Add the iords FIFO to the harness RTL per this doc (preloaded per-case sequence,
  consumed one-per-IOR, byte-lane duplication matching the IN-class E4/E5 path).
- Quartus synth; safe_flash.sh; A/B-selectable; verify IN-class lane behavior unchanged.
- Pre-register the deploy gate (byte-identity acceptance re-run) before the flash.

### Phase C — INS tranche ×10k (AFTER Phase B). Pre-registered gate:
- 10 forms: 6C 6D + F3/F2/65/64 x{6C,6D}; varied per-case port data; odd-port BYTE forms
  for high-lane coverage (word forms even-port per the odd-port-word-split note above).
- G-INS-1: validate_suite; G-INS-2: three-way flat-validity; G-INS-3: extract_iords
  sidecars (ambiguity ~0 as on the v20 regen).

### Phase D — finalize:
- validate_suite over complete v0.3 (347 + 23 = 370 forms); README/metadata updates
  (drop 6C-6F from limitations; document iords schema field + INS port provenance).
