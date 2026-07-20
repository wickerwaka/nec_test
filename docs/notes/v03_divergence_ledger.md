# v0.3 divergence ledger — chip-vs-RTL residuals

62 cases in the v0.3 suite (347 forms × 10,000) where the socket-captured golden
(chip = truth) is **not reproduced by the internal RTL core** (the DUT), and the
mismatch is **memory-model-independent** — the case fails on both flat-1MB *and*
64K-mirrored replay, so it is not a mirror-collision artifact (those 62 were
separately re-emitted to flat-valid). Per the suite's flat-validity policy these are
**retained as valid suite content**: the chip behavior is real, and the RTL is what is
behind.

**Status: new intake for the next RTL campaign.** These are NOT residuals of a closed
investigation — the class-5 branch merged and the V20 architectural oracle closed 100%.
They are new, real chip-vs-RTL divergences at ~1-2 per 10,000 rates that only native
10k-deep sampling exposes — exactly what this suite was built to find. Booked as its own
task by the coordinator.

Found by `sw/check_core.py --suite-dir tests/v30/v0.3 --opcodes all` (three-way flat/
mirror pass); indices re-extracted on the settled post-re-emit suite. `cyc` = cycle-row
(bus-timing) divergence only; `arch` = final architectural state (regs/flags/ram) only;
`both` = fails on both axes.

## Families

### 1. `0F31` INS bit-field — pure timing, busstat @ cycle 9-10 (25 cases, largest family)
BIU/queue-adjacent bus-status timing. arch state matches exactly; only the cycle-row
bus-status column diverges at cycles 9-10.
idx (all `cyc`): 116, 547, 549, 759, 825, 1554, 1793, 1977, 2271, 2333, 2733, 3207,
3337, 3930, 4581, 4606, 5303, 6004, 6332, 6349, 7027, 7289, 7526, 7844, 8463

### 2. BCD string-4S functional residuals (24 cases)
`sub4s`/`cmp4s`/`add4s`. **NOTE: these are NOT the large-CL story** — the 4S generator
uses CL 1-6, so this is a genuinely new low-CL functional divergence, not a known count
limit. `0F22`/`0F26` are pure `arch` (final-state) misses; `0F20` is mixed.
- `0F26` cmp4s (10, `arch`): 279, 1022, 1406, 1455, 2829, 3135, 4217, 7202, 7885, 8474
- `0F22` sub4s (5, `arch`): 2526, 2852, 3415, 9381, 9460
- `0F20` add4s (9): 1938/3766/3941/6195/6785/8489 (`arch`), 1209/4493/7815 (`cyc`)

### 3. Pin-event functional residuals (10 cases, all `arch`)
- `HLT.RES` HALT masked-INT resume (6): 1973, 4366, 4870, 5710, 5820, 9308
- `IE0.90` masked INT (4): 1064, 3586, 4464, 7142

### 4. Single mixed bus-timing residuals (3 cases, all `both`)
- `0F1B` (1): 3917
- `83.5` (1): 8683
- `FF.3` (1): 7685

## Total
25 (0F31) + 24 (BCD-4S) + 10 (pin-event) + 3 (single) = **62 cases** across 9 forms.
Cycle-only: 28; arch-only: 31; both: 3.

These ship with the suite (chip truth). They do not block the campaign and are not suite
defects; each is an RTL work item.

## Family 5 — OUTS single-form prefetch ordering (~29,892 cases, RICHEST intake)

Added with the OUTS tranche (Phase A). By far the largest divergence family; a
**fittable BIU prefetch-ordering law with a ~30k-case characterization set** — same
methodology as class-5.

**What it is:** for a SINGLE (non-REP) OUTS, the golden and the RTL execute the
*identical set of bus cycles* (opcode CODE fetch, DS:IX MEMR source-read, port IOW,
then the next-instruction CODE fetch) with *identical arch state* (si/ip/final regs
match) — but the RTL **prefetches the next-instruction CODE fetch EARLY** (right after
the OUTS opcode) whereas the chip prefetches it **LATE** (after the MEMR + IOW). Pure
cycle-ORDERING divergence; chip is truth, the RTL BIU is behind. Confirmed row-by-row
(golden vs sim) and by G-OUTS-1 (3,600,000/3,600,000 structural-clean, so the goldens
are not defective) and by arch equality on the diverging cases.

**Scope (6 of 13 OUTS forms; the 7 REP forms are CLEAN):**
- `6E` outsb  : 7,481 / 10,000
- `6F` outsw  : 7,446 / 10,000
- `36.6E` ss: : 5,055 / 10,000
- `26.6E` es: : 4,985 / 10,000
- `2E.6F` cs: : 4,924 / 10,000
- `646F` repnc-prefixed word (single-like path edge): 1 / 10,000
- Total: **29,892 cases**.

REP OUTS (F3/F2/65/64 × 6E/6F) shows the ordering matches — the loop keeps the BIU busy,
so no speculative early prefetch of the next instruction. The single-vs-REP split is the
key discriminator for fitting the ordering law.

**Disposition (coordinator, 2026-07-19):** SHIP the OUTS goldens (chip truth); this is the
KEEP branch, not held hostage to an RTL campaign. Booked as the primary BIU-ordering
intake. INS (Phase C) is expected to show the SAME single-vs-REP pattern; if singles
diverge identically it is this same family, same disposition (no re-ask).

## Family 5 extension — INS single forms (Phase C/D, prefetch ordering)

INS singles 6C/6D show the IDENTICAL prefetch-ordering signature as the OUTS singles
(confirmed row-by-row: RTL prefetches the next-instruction CODE fetch EARLY at ~cycle 2,
where the chip performs the port IOR first and prefetches late). Pre-dispositioned to
this family by the coordinator; confirmed matching. Chip truth, RTL BIU behind.
- `6C` insb : 7,528 / 10,000 (5,000 cold cases fail cyc+arch; 2,528 cyc-only)
- `6D` insw : 7,515 / 10,000 (5,000 cold cases fail cyc+arch; 2,515 cyc-only)
- Subtotal: 15,043 cases.

Family 5 total (OUTS singles 29,892 + INS singles 15,043) = **44,935 cases** — the
single-string-I/O BIU prefetch-ordering law. REP string-I/O never shows it (the loop keeps
the BIU busy, no speculative early next-instruction prefetch). The single-vs-REP split is
the discriminator for fitting the law.

## Family 6 — word REP INS queue-status (QS) point-sample timing (NEW, Phase D)

Word REP INS only (646D/656D/F26D/F36D; byte REP INS 646C/656C/F26C/F36C are CLEAN, and
non-REP handled by Family 5). The divergence is **cycle-only, arch-CLEAN** (final regs/ram
match exactly): the QS (queue-status) point sample reports a queue-FETCH (qop=F) one cycle
differently between chip and RTL at the same bus address/T-state (e.g. golden qop=F where
sim qop=-). A queue-status *reporting-timing* difference during the word-wide REP-INS fetch
interleave, not a functional or address divergence. (Related to the documented "QS reports
one cycle late" point-sample caveat, here surfacing as a chip-vs-RTL delta specific to the
word REP-INS pattern.)
- `646D` repnc insw : 4,051 / 10,000
- `656D` repc  insw : 4,090 / 10,000
- `F26D` repne insw : 4,109 / 10,000
- `F36D` rep   insw : 4,092 / 10,000
- Total: **16,342 cases**, all cycle-only (qop column), arch-clean.

Disposition: KEEP (chip truth); ledgered as its own family. A fittable QS-timing law with
a 16k-case set. Word-vs-byte and REP-only scope are the discriminators.

## RESOLUTION LOG (task #24)
- **Family 6 (16,342, word-REP-INS qop timing): RESOLVED** 2026-07-20 (commit below). The
  op_instr INS-close branch now mirrors the silicon-fitted STM/MOVBK split-close law
  (`if (opc[0] && eu_addr[0]) retire(); else state <= S_EX;` at v30_eu). Word REP INS at an
  odd ES:IY closes at done (delta 1); aligned word + all byte keep the +1 S_EX close (delta
  2). Gate: 4 forms 0/16,342; byte REP INS / REP OUTS / DI-even / CW=0 unchanged; w0
  169000/169000, w1/w3 1200/1200; scramble 0; v20 6D arch 2000/2000. No new flops, no
  savestate struct change. Ledger 61,339 -> 44,997 (Family 5 44,935 + Families 1-4 62).
- **Family 5 (44,935, single string-I/O prefetch): HELD at stop condition #2.** The eu_hold
  claim (S_FIRST head-byte-peek + S_DEC) makes COLD cases bit-identical but shifts the WARM/pf
  MEMR one slot late (all warm cases broken). Per the pre-registered stop condition, reverted;
  the request-onset (not just the claim) must move — a different, riskier change. Back to the
  architect.
