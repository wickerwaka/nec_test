# V30 BIU/EU identification session summary

Date range: 2026-07-28 through 2026-08-01  
Repository: `/home/wickerwaka/src/nec_test`  
Objective: discover the complete BIU and EU model required to resolve all
READY/wait discrepancies.

## Executive status

The objective is **not complete**.  This session replaced an invalid
long-trace closure argument with controlled socket-chip experiments, built a
reproducible chip-only measurement system, identified several real pieces of
BIU/EU state, and mapped a substantial set of measured timing laws into RTL.
The latest RTL validation still fails four of 640 retained records in the
current INS tranche.  Savestate integration and fresh prospective-bank
validation are also outstanding.

The strongest current result is narrower:

- A frozen, chip-derived oracle predicts all 800 retained cells from four new
  INS failures exactly.
- The RTL exactly matches the 160-cell `fz12302` family.
- The RTL matches 636/640 records and 1,148/1,152 write rails across the other
  three families.
- The four remaining failures are deterministic instances of one aligned
  offset-one, length-seven phase condition.  RTL starts the write one clock
  early at selected wait counts 12 and 14 under both preparation histories.

This is useful localization, not architectural closure.

## Why the original approach was rejected

The session began by auditing the earlier B4 closure claim.  It was not an
acceptable proof of state closure:

- `sw/b4_closure_v2.py` defines any violation as a NO-GO, and its retained log
  reports 21 violations and NO-GO.
- Its match key contains program `seed` and structural `eu_ord`, preventing
  distinct preparation histories from being compared as the same observable
  state.
- It excludes 9,936 non-EU events.
- Reclassifying `w0` failures using RTL knowledge shows that additional state
  exists, but does not prove that `(phase, occupancy, fill)` is sufficient.

Accordingly, the reported `w1/w3 0/988` result is treated only as
within-history repeatability.  Stage C was paused and long-trace
chip-versus-RTL classification was removed from the discovery boundary.

## Methodological reset

The replacement method is a physics-style experiment:

```text
reset -> prepare a certified observable state -> change one input
      -> observe one bus decision -> reset
```

The discovery boundary is `sw/biu_blackbox_probe.py`.  It forces use of the
socketed chip, replays an exact access-indexed wait vector, checks requested
against observed Tw counts, retains raw captures and SHA-256 hashes, and
derives state only from external pins.  RTL internals, program seed, and
structural access ordinal are excluded from the chip-state key.

The retained interface consists of:

- `ProbeSpec`: image/setup, preparation and challenge, exact wait vector,
  clock divider, boundary, request class, and repetition count.
- `StateCertificate`: externally reconstructed queue bytes/address tags,
  depth, fetch address/parity, bus transaction/T-state, QS consumption
  position, and controlled request class.
- `Outcome`: first action, exact T1 clock, address/width, and intervening QS.
- Complete raw trace plus content hash beside each derived record.

The physical acceptance rules used five bit-identical repetitions, exact Tw
agreement, no capture overflow, and equivalent cycle behavior at 4 and 8 MHz.
The CPU clock remained free-running; it was never stopped or single-stepped.

## Chip-only discovery completed during the campaign

The detailed cumulative ledger is
`docs/notes/biu_blackbox_campaign.md`.  The major results established during
this session are summarized here.

### Calibration and certified queue states

- QS/self-modifying-sentinel calibration passed in
  `sw/testdata/biu_blackbox/qs-calibration-20260728-v2/summary.json`.
- Seventy socket captures reproduced the stale/new queue boundary at both
  frequencies.
- Certified queue-state generation passed in
  `sw/testdata/biu_blackbox/certified-states-20260728-v9/manifest.json`.
- Even-aligned fetches reached reconstructed depths 0-6; initial odd fetches
  reached 0-5.
- Every retained certificate was reproduced by two different preparation
  histories.

### Decoder and ordinary arbitration

- Decoder-byte timing passed in
  `decoder-timing-20260728-v8/summary.json` for NOP, LEA, MOV read/write,
  displacement forms, and an RMW form.
- No-request collisions covered 276 exact-T1 boundaries.
- Reservation collisions covered 300 boundaries and found 54 adjacent-wait
  action changes among CODE, MEMR, and MEMW outcomes.
- String and predecessor controls added 78 and 96 boundaries respectively.
- The first frozen general oracle failed prospectively: 184 mismatches among
  contained held-out keys.  It was not refit or declared closed.
- Minimal-pair analysis identified `consumer_byte_role` as missing state.
- After promoting that observable role, the frozen ordinary oracle v2 passed
  4,240/4,240 summarized held-out conditions, representing 21,200 raw
  repetitions.

### Prefix-chain state

Single-prefix controls were insufficient for double prefixes.  A matched
prefix-depth factorial identified a three-phase EU decode state:

```text
phase = 0                         when no prefix is active
phase = 1 + ((prefix_count-1)%3)  otherwise
```

The rule was frozen before counts 9-14 and passed all 240 held-out records.
It remains a tested prefix transition, not a complete prefix/request model.

### String-I/O completion state

Single and REP string-I/O probes showed that the successor CODE gap is
predicted by QS consumption overlapping the completing transfer, rather than
by input/output direction, byte/word width, or REP alone:

```text
gap = 1 + (wait != 0)  when the final transfer has zero QS pops
gap = 4 + (wait != 0)  when the final transfer has one QS pop
```

The unchanged v2 transition was validated across single INSB, INSW,
CS-prefixed OUTSW, prior REP OUTSB captures, and new REP INSW/OUTSW controls.
These results close the measured completion transition only; string
iteration, reservation, and retirement remain broader state-machine work.

### Successor-request maturity and later case campaign

The campaign continued with directed read/write/RMW, string, branch/flush,
software-interrupt, BCD-string, and INS families.  Each discovered mismatch
was converted into a small factorial around the responsible bus transfers,
then represented as an external timing rule before any RTL mapping.  The
large collection of `sw/biu_case*_*.py`, `sw/case*_*.json`, and raw directories
under `sw/testdata/biu_blackbox/` is the retained experimental ledger.

These cases materially expanded regression coverage, but their existence is
not itself proof of a complete finite-state transducer.  The current stopping
point is the prospective seed bank 12120-12619.

## Latest prospective-bank tranche

The 500-program bank 12120-12619 exposed four deterministic failures.  The
effective generated seeds and geometries are:

| Program | Effective seed | Geometry | Retained cells |
| --- | ---: | --- | ---: |
| `fz12302` | `0x85e9` | aligned immediate INS, off=2, len=9 | 160 |
| `fz12466` | `0x8555` | split immediate INS, off=1, len=7 | 256 |
| `fz12547` | `0x84e4` | split immediate INS, off=1, len=8 | 256 |
| `fz12569` | `0x84fe` | aligned immediate INS, off=1, len=7 | 128 |

Every original failure repeated identically five times.  The physical
factorials vary one selected read or write wait from 0 through 15, use two
preparation histories, and retain 800 raw chip cells in:

- `sw/case250_fz12302_factorial.json`
- `sw/case250_fz12466_factorial.json`
- `sw/case250_fz12547_factorial.json`
- `sw/case250_fz12569_factorial.json`
- `sw/testdata/biu_blackbox/case250_fz*/`

The per-family counts differ because split word accesses expose independently
controllable low/high halves.

## Frozen INS oracle

`sw/biu_case251_ins_deadline_oracle_v1.py` accepts only instruction geometry
and externally observed completion facts.  It does not accept seed, access
ordinal, preparation history, or RTL state.

The measured rule is the maximum of two independent deadlines:

```text
write.T1 = max(final_R1.T4 + decoder_delta,
               final_R2.T4 + completion_delta)
```

The deltas are:

| Geometry | R1 w0 / waited | R2 w0 / waited |
| --- | --- | --- |
| aligned immediate off2 len9 | 63 / 64 | 31 / 32 |
| split immediate off1 len7 | 54 / 55 | 25 / 26 |
| split immediate off1 len8 | 57 / 58 | 27 / 28 |
| aligned immediate off1 len7 | 54 / 55 | 25 / 26 |

For split reads, `final_R1.T4` and `final_R2.T4` mean the high-half completion.
`sw/case256_ins_deadline_validation.json` is PASS: 800/800 predictions, zero
mismatches.

This oracle is a closed description of the retained four-family experiment.
It has not yet passed held-out instruction geometries, so it cannot be called
the complete INS model.

## RTL work performed

### Instrumentation

A diagnostic `z` trace row was added to `hdl/tb/tb_v30_core.sv` and decoded by
`sw/dumpeu.py`.  It exposes EU completion/read-completion, bus T4/read,
deferred-length state, prior-Tw state, and the new deadline counter.  Existing
split/half trace fields were also printed.

The boundary traces established:

- A split read's low-half T4 occurs while `want_half2=1`.
- Its high-half/final T4 occurs while `want_half2=0`.
- `eu_done` is one clock after split final T4 but four clocks after aligned
  final T4, so `eu_done` is not a geometry-independent architectural anchor.
- The EU can reconstruct final split completion by counting two read T4s at
  an odd destination; no BIU-internal signal is required for that fact.

Representative logs are:

- `sw/case265_fz12466_boundary.log`
- `sw/case265_fz12569_boundary.log`
- `sw/case267_fz12466_deadline.log`
- `sw/case274_fz12569_c1_w12.log`
- `sw/case274_fz12569_c1_w13.log`
- `sw/case274_fz12569_c1_w14.log`

### EU state and timing logic

The current `hdl/rtl/core/v30_eu.sv` adds:

- `ie_c251_r1_low`, which records the first half of an odd split R1 read.
- `ie_c251_deadline[6:0]`, a final-R1-anchored decoder deadline.
- Qualifiers for aligned off2/len9 and off1 len7/len8 INS geometries.
- A provisional length-eight deadline loaded at the observable final R1 T4.
- A four-clock correction when the deferred immediate length resolves to
  seven.
- A write-release gate that composes the decoder deadline with the existing
  completion-relative rail.
- One-clock adjustments to existing aligned/split length-seven R2 rails.

The `fz12302` mapping is fully exact in the retained plane:

- `sw/case262_fz12302_rtl.json`: PASS, 160/160 records.
- `sw/case263_fz12302_origin.json` and the associated w0/w1/w3 controls match.
- `sw/case264_prior_new_ins_regression.json`: PASS, 352/352 prior INS records.
- The savestate lint result at that earlier point passed, before the later
  off1 state was added.

The current off1 mapping has a passing 50-record smoke result in
`sw/case272_rtl_smoke.json`.

## Exact current failure

`sw/case273_off1_full_rtl.json` is the authoritative current gate:

```text
gate:         FAIL
records:      640
record match: 636
write checks: 1,152
exact writes: 1,148
delta -1:     4
```

All four failures are `fz12569`, role `C1`, aligned off1/len7:

| History | Selected wait | Chip T1 | RTL T1 | Delta |
| --- | ---: | ---: | ---: | ---: |
| A | 12 | 1517 | 1516 | -1 |
| B | 12 | 1517 | 1516 | -1 |
| A | 14 | 1517 | 1516 | -1 |
| B | 14 | 1517 | 1516 | -1 |

Wait 13 is the adjacent exact control.  Internal traces show that waits 12
and 14 enter write launch with `ie_r2_late != 0`, while wait 13 has
`ie_r2_late == 0`.  The new absolute deadline has already expired in all
three.  This localizes the missing behavior to a one-clock aligned
length-seven phase hold composed with the existing R2-late rail.

No final fix for this four-cell residual was implemented during the session.
A permanent predicate would deadlock; the next implementation must be a
one-shot causal hold, then be tested against the entire 640-record plane.

## Worktree and integration cautions

The worktree is intentionally dirty and contains many pre-existing changes and
generated artifacts.  No commit was made.  The session did not assume that all
modified files belong to this tranche.

The two new EU state fields are not yet represented in the addressed savestate
map.  Before claiming integration, add and verify their save/restore entries in
`hdl/rtl/core/v30_ss_pkg.sv` and the EU savestate read/write cases.  Patch those
files carefully because they already contain unrelated worktree changes.

Physical-board scripts must never run concurrently.  After physical use, the
known cleanup command is:

```sh
PYTHONPATH=sw python3 -c \
  'import b1_recapture; b1_recapture.board_idle(); print("board idle; use_core=0")'
```

At the end of the recorded work, no physical capture process was active and
the board had been returned to idle/socket mode.  The latest diagnostic work
used Verilator only.

## Required next steps

1. Implement a one-shot release hold for the aligned immediate off1/len7 case
   when the current R2 phase-late condition is present.  Do not encode waits
   12 and 14 as special cases.
2. Rebuild and run a 50-record smoke test.
3. Run the targeted 32-cell `fz12569 C1` plane.
4. Run all 640 off1 records and require zero mismatches.
5. Run `sw/biu_case253_rtl_ins_deadline_validate.py` over all 800 Case 250
   records and require zero decision, T1, address, and write mismatches.
6. Add both new state fields to savestate and pass `sw/ss_lint.py` plus the
   relevant save/restore equivalence gates.
7. Re-run origins and uniform w0/w1/w3 controls for all four seeds.
8. Re-run the 352-record prior INS regression and the broader retained BIU/EU
   regression set.
9. Re-run prospective bank 12120-12619; require 500/500.
10. Run the untouched bank 12620-13119.  Any mismatch reopens state discovery
    and must become a controlled factorial, not a seed-specific exception.
11. Continue held-out opcode, addressing, parity, prefix, string, flush, and
    interrupt families until one frozen finite-state oracle passes every
    prospective gate.

## Acceptance boundary

The overall objective is achieved only when a frozen chip-derived transition
system predicts the next action, exact T1, address/width, and QS sequence with
zero mismatches across different preparation histories, held-out instruction
families, even/odd alignments, waits 0-7 and 15, uniform waits, and fresh
explicit/random wait vectors; and when the corresponding RTL passes the full
golden, fuzz, savestate, and long-trace regressions.

Current evidence does not meet that boundary.  The session produced a sounder
experimental foundation, several prospectively validated transition laws, and
a nearly closed four-family INS mapping, while leaving the full BIU/EU model
explicitly open.
