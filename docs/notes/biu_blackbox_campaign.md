# V30 BIU black-box identification campaign

Status: **PAUSED before Stage C**.  `sw/b4_closure_v2.py` remains a NO-GO
result and is not evidence that `(phase, occupancy, fill)` closes the machine.

`sw/biu_blackbox_probe.py` is the discovery measurement boundary.  Each live
invocation is:

> reset/load → prepare → replay one exact wait vector → observe pins → reset

It forces the socket (`use_core=False`), accepts only the safe 4 MHz and 8 MHz
controls, requires at least five repetitions, checks requested versus observed
Tw per bus access, rejects a busy final capture record, and retains complete
raw 64-bit records plus SHA-256 beside each derived record.  It does not import
CPU state or compare against the RTL.

Repeatability is bit-exact over electrically meaningful fields: control/status
on every row, T1 address, and T3/Tw data. Floating AD samples in TI/T2/T4 are
retained and raw-hashed but excluded from the stability hash.

## ProbeSpec

The JSON fields are:

- `probe_id`, `image` (a 64 KiB composed harness image)
- `preparation`, `challenge`, and optional `setup` (provenance text/data)
- `wait_vector` (exact Tw count for each bus access)
- `boundary_clock` (last preparation clock; the next T1 is the outcome)
- `clock_div` (`8` = 4 MHz, `4` = 8 MHz)
- `repeat_count` (at least five), `capture_records`
- `controlled_eu_request` (`none`, `read`, `write`, `rmw`, etc.)

The derived `StateCertificate` contains only externally reconstructed ordered
queue byte/address tags, depth, next fetch address/parity, current transaction
and T-state, QS consumption position, and the declared controlled request
class.  The `Outcome` is the first post-boundary action, clocks and absolute
clock to T1, address/width, and intervening QS sequence.

## Use

Analysis is offline and does not touch the board:

```sh
python3 sw/biu_blackbox_probe.py analyze probe.json raw-{00..04}.hex
```

Live execution is deliberately locked behind an explicit switch:

```sh
python3 sw/biu_blackbox_probe.py run probe.json artifacts/probe-4mhz --live
```

Run the identical probe at `clock_div=8` and `clock_div=4`; promotion tooling
must require equal derived cycle results across those two independently stable
sets.  Calibration probes must first establish the QS sampling offset using
equal-length old/new self-modifying sentinels.  No certificate is eligible for
closure until two distinct `preparation` histories produce it.  Those campaign
promotion rules are intentionally not automated away by this capture tool.

No CPU RTL changes are authorized during discovery.  A QS calibration failure
routes to capture sampling work.  Inability to independently tag queue bytes
routes to a stimulus-only scripted CODE-response buffer.

## Executed discovery gates (2026-07-28)

- QS calibration:
  `sw/testdata/biu_blackbox/qs-calibration-20260728-v2/summary.json` PASS.
  Seventy socket captures reproduce the stale/new boundary (distance 1–2
  stale, 3–7 new) at both 4 and 8 MHz.
- Certified states:
  `sw/testdata/biu_blackbox/certified-states-20260728-v9/manifest.json` PASS.
  Even fetch alignment reaches depths 0–6; initial odd-byte alignment reaches
  0–5.  Every retained certificate has two pre-flush wait histories and five
  identical repetitions at each frequency.
- Decoder timing:
  `sw/testdata/biu_blackbox/decoder-timing-20260728-v8/summary.json` PASS.
  With the producer in Tw at the final target-byte pop, LEA/MOV-read/MOV-write
  consume no-displacement bytes at offsets `[0,1]`, disp8-zero at `[0,1,3]`,
  and disp16-zero at `[0,1,2,4]`.  NOP is `[0]`; INC word `[BW]` is `[0,1]`.
- No-request collisions:
  `sw/testdata/biu_blackbox/no-request-collision-20260728/summary.json` PASS
  over 276 exact-T1 boundaries.  Active-fetch collision states reach depths
  0–4 and always choose CODE.  Depths 5–6 are producer-idle saturation states,
  so a selected-fetch collision is physically inapplicable there.
- Reservation collisions:
  `sw/testdata/biu_blackbox/reservation-collision-20260728/summary.json` PASS
  over 300 confirmed boundaries.  LEA/no-request always chooses CODE;
  read and RMW choose CODE or MEMR; write chooses CODE or MEMW.  There are 54
  adjacent-wait action changes.  Read and RMW have the same first-request
  table in this population.
- String and predecessor controls:
  `sw/testdata/biu_blackbox/string-collision-20260728/summary.json` PASS
  (78 boundaries; CODE/MEMR) and
  `sw/testdata/biu_blackbox/predecessor-collision-20260728/summary.json` PASS
  (96 boundaries).  With no EU request, both MEMR- and MEMW-preceded fetches
  still choose CODE.

These are discovery artifacts, not an RTL closure result.  Stage C remains
paused.

## Prospective oracle STOP (2026-07-28)

`sw/testdata/biu_blackbox/chip-oracle-v1.json` was frozen before held-out
capture from 1,089 chip records.  Its 738 keys use only the pin-derived state
listed in the artifact, including the prospectively tested queue-head modulo
six; 351 observations repeat a key.

Held-out displacement/RMW/branch capture passed its own repetition and
frequency gates:
`sw/testdata/biu_blackbox/oracle-heldout-20260728/summary.json`.
Prospective validation then **FAILED**:
`sw/testdata/biu_blackbox/chip-oracle-v1.validation.json` reports:

- 756 held-out records
- 348 unseen keys
- 184 mismatches on keys that the frozen oracle did contain

The failure is not merely missing branch coverage.  Overlapping disp8/disp16
read, write, RMW, and LEA keys disagree in exact T1/QS timing, and some disagree
on CODE versus MEMR/MEMW action.  Per the registered rule, this reopens state
discovery and is a campaign **STOP**.  The oracle was not refit or extended.
No RTL mapping and no Stage C work are authorized from these results.

The read-only minimal-pair ledger is
`docs/notes/biu_oracle_v1_mismatch_ledger.md` with machine-readable source
`sw/testdata/biu_blackbox/oracle-v1-mismatch-ledger.json`.  It joins records
only by the complete frozen oracle key and reduces the 184 contradictions to
six directed ModRM-versus-displacement-role probe classes.  This ledger is the
starting point for a future prospectively registered byte-role experiment; it
does not modify or supersede the failed oracle.

## Ordinary arbitration closure and prefix-state discovery (2026-07-29)

The byte-role hypothesis was first closed prospectively on directed ledger
cell 2.  The frozen targeted rule and its audit are:

- `sw/testdata/biu_blackbox/case2-micro-oracle-v1.json`
- `sw/testdata/biu_blackbox/case2-prospective-20260729-r2/audit.json`

The rule passed 80 discovery and 80 fresh held-out target records with zero
unseen states and zero action, exact-T1, address/width, or QS mismatches.
Complete registered certificates matched across consumer roles, two unrelated
padding controls, two preparation histories, 4/8 MHz, and five repetitions.

Promoting `consumer_byte_role` into the ordinary key removes every conflict
from the 1,737-record non-flush corpus (1,206 keys).  The resulting frozen
ordinary oracle is `sw/testdata/biu_blackbox/chip-oracle-v2.json`.  Ten fresh
LEA/read/write/RMW variants changed the ModRM register field or RMW operation
and covered ModRM, disp8, and disp16-high consumers.  Prospective validation
in `chip-oracle-v2.validation.json` passed 4,240/4,240 summarized conditions
(21,200 raw repetitions), with zero unseen states or mismatches.

Prefixes expose another EU-side state input.  A boolean `prefix_active` key
predicts all alternate *single*-prefix controls (CS versus ES overrides,
segment versus LOCK RMW, and alternate RMW operation), but fails only on
double prefixes.  A matched prefix-depth factorial then held the same external
key across counts 0 through 8 and found:

- Counts 0, 1, 2, 4, 5, 7, 8: CODE T1 at boundary +2.
- Positive counts divisible by three (3, 6): CODE T1 at boundary +1.

The phase rule was frozen before counts 9 through 14 in
`sw/testdata/biu_blackbox/prefix-phase-oracle-v1.json`.  Prospective validation
`prefix-phase-oracle-v1.validation.json` passed all 240 held-out factorial
records: counts 9/12 choose +1 and 10/11/13/14 choose +2.  Thus the smallest
currently supported prefix-chain state is:

```text
phase = 0                         when no prefix is active
phase = 1 + ((prefix_count-1)%3)  otherwise
```

This is a pin-derived EU decode-phase result, not yet a complete BIU/EU model.
It still requires promotion across all request classes and held-out prefix
families.  String iterations, branch/flush, interrupt/vectoring, and final RTL
mapping remain open.  CPU RTL and Stage C were not changed during discovery.

## Single string-I/O completion transition (2026-07-30)

Cases 26 and 27 isolate the final bus transfer of non-REP byte string-I/O and
observe the first successor bus decision.  Both use two preparation histories,
4/8 MHz controls, five repetitions, waits 0–7 and 15, raw capture retention,
and socket-only execution:

- `case26-single-outs-completion-chip-v1`: after the final OUTSB IOW, successor
  CODE starts one clock after T4 at w0 and two clocks after T4 for every
  positive wait.
- `case27-single-ins-completion-chip-v1`: the held-out INSB sibling initially
  distinguishes the provisional instruction classes.  After its final MEMW,
  successor CODE starts four clocks after T4 at w0 and five clocks after T4
  for every positive wait.  Case 28 below later attributes that distinction to
  overlapping QS consumption rather than opcode identity.

The frozen transition table is
`sw/testdata/biu_blackbox/strio-completion-oracle-v1.json`.  Validation against
360 chip records / 72 summarized conditions passes with zero action, address,
or exact-T1 mismatches in
`strio-completion-oracle-v1.validation.json`.

This closes one architectural case rather than the complete string-I/O
machine: word width, REP retirement, and held-out opcode/prefix families remain
separate prospective gates.

The first word-width control rejected the provisional operation-class
interpretation.  `case28-single-strio-word-completion-chip-v1` contains held-out
single INSW and CS-prefixed OUTSW completions.  Both have zero QS pops during the selected
final transfer and both follow the OUTSB law (CODE at T4+1 for w0, T4+2 for
positive waits), while the INSB fixture has one overlapping pop and follows
the T4+4/T4+5 law.  The smaller frozen rule therefore uses:

```text
gap = 1 + (wait != 0)  when the completing transfer has zero QS pops
gap = 4 + (wait != 0)  when it has one QS pop
```

`strio-completion-oracle-v2.json` was frozen before the full Case 28 control.
Its validation passes 540 chip records / 108 conditions across INSB, INSW, and
CS-prefixed OUTSW with zero next-action or exact-T1 mismatches.  This promotes an
externally observable EU-consumption overlap into the string-I/O completion
state and shows that byte/word width and input/output direction are not needed
for this tested transition.  The CS override also does not split this
completion transition.

The same already-frozen rule was then applied offline to all 360 retained raw
captures from the earlier REP OUTSB overlap experiment (Case 22).  The final
IOW was located from pins, its actual QS-pop count was reconstructed, and the
next bus decision was derived without using the old summary outcome.  The
prospective result in
`strio-completion-oracle-v2.case22-validation.json` passes all 72 conditions:
the final transfer has zero overlapping pops and successor CODE follows at
T4+1 for w0 or T4+2 for a positive wait.  Producer waits 0/1, both histories,
both frequencies, and waits 0–7/15 do not change the rule.  REP OUTSB
retirement therefore merges with the same completion state; a REP bit is not
required for this transition.

Case 29 adds independent REP INSW and REP OUTSW word-width fixtures.  The
unchanged v2 oracle passes all 360 new captures / 72 conditions: each final
transfer has zero overlapping QS pops and successor CODE follows at T4+1 for
w0 or T4+2 for positive waits.  The consolidated v2 validation now covers 900
chip captures / 180 conditions across single INSB, single INSW, CS-prefixed
OUTSW, REP INSW, and REP OUTSW with zero next-action or exact-T1 mismatches.

## Successor-request maturity (2026-07-30)

The v2 rule is closed only when no successor request is mature at the
completion boundary.  Case 30 supplies the minimal counterexample:
`SS: REP OUTSB; POP AW`.  Its final IOW has the same depth 6 and one
overlapping QS pop as the no-request population, but the queued POP has already
raised a mature stack-read reservation.  All 180 records choose MEMR, at T4+5
for w0 or T4+6 for positive waits.  The registered v2 oracle therefore fails
180/180 records; the failure is retained in
`strio-completion-oracle-v2.case30-counterexample.json`.

Case 31 factorially separates request existence from maturity in the same
preparation.  Equal-length `LEA AW,[BW]` and `MOV AW,[BW]` successors both
retain depth 6 and one selected-transfer pop.  LEA has no request and MOV has
an immature read; both choose CODE at T4+4/T4+5 in all 360 captures.  Thus a
declared future read is insufficient—its maturity at the boundary is the
distinguishing state.

The v3 oracle adds `request_maturity = none | immature | mature`.  It was
frozen before Case 32, an independent `REP INSB; POP DI` fixture with a
different final bus type and stack address.  Case 32 prospectively passes all
180 captures: the mature read chooses MEMR at T4+5/T4+6.  Consolidated v3
validation covers 720 captures / 108 conditions over no request, immature
read, and mature read, with zero next-action or exact-T1 mismatches:
`strio-completion-oracle-v3.validation.json`.

This is a behavioral state variable, not an RTL signal name.  Reservation-age
boundaries for writes, RMW, and strings remain open, as do completion states
with two or more overlapping QS pops.

### Write/RMW maturity and two-pop decoder drain

Case 33 uses the same matched preparation to compare an immature
`MOV [BW],AW` reservation with mature one-byte `PUSH AW`.  The immature write
continues to lose to CODE at T4+4/T4+5.  The mature write wins as MEMW at
T4+6/T4+7—one clock later than a mature read.  The v4 rule was frozen before
held-out PUSH CX/DX/BX; Case 34 passes all 540 new captures.  Consolidated v4
validation covers 1,620 captures / 180 conditions with zero mismatches.

Case 35 adds an equal-length `INC word [BW]` successor.  Its RMW reservation is
immature at this boundary and follows the CODE T4+4/T4+5 rule in all 180
prospective captures.  This agrees with the earlier ordinary reservation
collision corpus, where read and RMW have identical first-request tables.
The v5 completion oracle passes 1,800 captures / 216 conditions.  A mature RMW
completion collision remains open.

The first two-pop completion state exposed an EU decoder distinction that pop
count alone hides.  With the same depth 6 and no request:

```text
successor NOP:
  positive wait: F at T4+2, F at T4+5, CODE at T4+7
successor INC/DEC register:
  positive wait: F at T4+2, F at T4+4, CODE at T4+6
```

w0 shifts every listed event one clock earlier.  The decoder-drain oracle was
frozen from NOP versus INC AW, then passed 1,260 held-out captures spanning
INC CX/DX/BX and DEC AX/CX/DX/BX, with zero QS-sequence or exact-T1
mismatches.  This promotes one-byte EU execution class into the state model;
the next CODE decision is consistently two clocks after the final F pop in
this population.

A broader one-byte census splits that execution state into three measured
decoder-drain classes:

```text
fast:     F at +2,+4; CODE +6
standard: F at +2,+5; CODE +7
long:     F at +2,+7; CODE +9
```

Offsets are from the completing transfer's T4 for positive waits; w0 shifts
all offsets one clock earlier.  The fast class contains INC/DEC register,
CLC/STC/CMC, CLD/STD, CLI/STI, CBW, and LAHF.  Standard contains NOP, XCHG
AX,CX, and SAHF.  CWD is the measured long class.  The frozen decoder-drain v2
oracle passes 2,160 captures / 108 conditions, including two histories, both
frequencies, five repetitions, and waits 0–7/15, with zero QS-sequence or
exact-T1 mismatches.

These classes describe externally measured future byte demand; they do not
assert that the chip implements three literal internal states.  Multi-byte
register forms, immediate forms, branches, and BCD-adjust instructions still
require classification.

The first multi-byte decoder-drain oracle now closes four additional byte-role
classes at the same certified boundary (positive-wait offsets shown):

```text
generic register ModRM: F +2, S +3, F +5; CODE +5
TEST register:          F +2, S +3, F +4; CODE +5
word immediate:         F +2, S +4, S +5, F +6; CODE +6
short JMP:              F +2, S +4, E +7; redirected CODE +9
```

w0 again shifts the complete schedule one clock earlier.  The rule was frozen
from MOV/ADD/XOR register, TEST AX, MOV/ADD immediate, and short JMP +0.  It
then passed 1,260 held-out captures / 144 conditions spanning SUB/AND/OR
register, TEST CX, SUB/XOR immediate, and short JMP +2.  Validation includes
the complete QS sequence and exact next-T1 clock; address redirection remains
derived from the controlled branch target rather than treated as a timing
class.
