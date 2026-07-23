# v0.3 divergence ledger — chip-vs-RTL residuals

> **STATUS 2026-07-23: 62 → 52.** Family 3 (pin-event, 10 cases) RESOLVED as a capture/
> convention artifact (no RTL bug) — the no-fire pin-event sub-species: no interrupt is taken,
> so flags are architecturally unchanged from initial and the store-stub `final.flags` is
> unreliable on both sides. check_core pin-event gate extended with a no-fire branch (drop
> flags when SP unchanged), emit_suite convention extended (drop the store-stub flags delta
> for no-fire), and the 10 v0.3 goldens re-derived host-side (final.flags removed → defaults
> to initial; now uniform with the other 9994/9996 no-fire cases). Gate: HLT.RES/IE0.90
> 10000/10000, all 13 pin-event forms 130000/130000, v0.1 pin-event 2600/2600, w0 169000/
> 169000 — zero changes elsewhere. **Remaining: 52 (F1 25 + F2 24 + F4 3).** F1/F2/F4 held
> for the tail-family law designs (docs/notes/v03_tail_family_law_design.md).

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

## Phase 1 characterization (2026-07-22) — measured, on-disk (zero board cost)

Re-verified on master f8a9a55: all 62 reproduce EXACTLY (full-sweep indices match to the
case). No regressions, no new divergences — the string-I/O and v2-savestate landings did not
touch these. Harness: `sw/char_divergence.py` (reuses check_core; `python3 sw/char_divergence.py FORM idx,idx` dumps per-case row/arch diffs; bare FORM sweeps).

| family | forms | cases | nature | discriminator (measured, single-valued) | fix locus |
|---|---|---|---|---|---|
| F1 | 0F31 INS | 25 | cyc-only, arch-clean | **offset==0 ∧ width==15** (exact: 25/25, 0 clean) | BIU RMW bus scheduling |
| F2 | 0F26/0F22/0F20 BCD-4S | 24 | arch (Z/P) + 3 cyc | decimal wrap-to-zero via invalid nibble; **V30-specific** (RTL matches V20, both ≠ V30 chip) | EU BCD-4S Z/P flag path |
| F3 | HLT.RES/IE0.90 | 10 | arch (flags) | **CAPTURE ARTIFACT** — no-interrupt-fired store-stub final.flags | check_core/emitter convention, NOT RTL |
| F4 | FF.3 | 1 | both | EA offset wrap at 0xFFFF (RTL reads linear, no wrap) | BIU EA offset wrap |
| F4 | 0F1B | 1 | cyc-only | undoc INS-sibling DS-operand RMW scheduling (F1-kin) | BIU RMW scheduling |
| F4 | 83.5 | 1 | both | PF flag delta (chip PF=0 correct for 0x62, RTL PF=1) + operand-RMW bus divergence | architect triage |

### F1 — 0F31 INS (25): offset=0 ∧ width=15
INS reg8,reg8 inserts a `width`-bit field at bit `offset` into ES:DI (offset=rm-field reg8,
width=reg-field reg8, each 0–15). Divergence ⟺ **offset=0 AND width=15** — exactly the 25
cases, zero clean; word-crossing ruled out (149/400 clean cases cross a word boundary and
pass). Arch identical. Signature: RTL performs an extra ES-segment MEMR read-modify-write
(23/25) that the chip renders PASV/Ti idle, chip MEMW shifted later (2/25 show only the
shifted-MEMW half). Start row 9 (17×) or 10 (8×).

### F2 — BCD-4S (24): V30-specific Z/P on decimal-wrap-to-zero
All 24 = the {Z,P} pair flipping together (chip⊕rtl low-flags 0x44; CY/AC/S/high identical).
- CMP4S(10)+SUB4S(5): chip Z=1,P=1 vs RTL Z=0,P=0. Exact discriminator: result borrow-wraps
  to all-zeros while `dst != src` (source carries an invalid nibble ≥10 = dst_digit+10).
  V30 sets Z/P on the wrapped zero; RTL does not. 15/15 exact; near-miss control = byte-
  identical dst==src strings (RTL correct there).
- ADD4S(6 arch): opposite polarity — RTL falsely reports zero; trigger = decimal-adjust/carry
  through invalid-or-carrying nibbles. ADD4S(3 cyc): result word differs by one BCD adjust
  step (0x2160 vs 0x2060, 0x7260 vs 0x7160, 0x6224 vs 0x6223).
- **V20 cross-check DECISIVE:** shared vector idx652 (CL=1,dst=3,src=13) — V20 oracle Z=0,P=0;
  V30 chip Z=1,P=1; our RTL Z=0,P=0. RTL implements the V20/8086 result; needs a V30-specific
  Z/P path for the invalid-nibble decimal-wrap case. (The V20-only oracle held the vector but
  could never flag the V30 difference.)

### F3 — pin-event (10): CAPTURE ARTIFACT (no RTL bug)
HLT.RES(6): 1973,4366,4870,5710,5820,9308; IE0.90(4): 1064,3586,4464,7142. All differ in
`final.flags` ONLY. RTL `final.flags == initial flags` exactly (architecturally correct — no
interrupt fires: SP/SS unchanged, no INTA/stack push — so flags cannot change), while the
chip store-stub field shows impossible changes. The **"no-fire sub-species"**: task #21's
pushed-PSW substitution is gated on interrupt-fired, so it doesn't apply and the comparison
falls back to the contaminated store-stub. Same root cause as the resolved 7 (INT.90/FB/9D).
Fix = convention extension (see task #21 CLOSED in v02_suspected_divergences.md), not RTL.

### F4 — singletons (3)
- **FF.3/7685 — DEFINITIVE segment-offset-wrap.** CALLF DWORD[BX+DI+0x34], EA offset=0xFFFF.
  Golden placed the far pointer at offset-wrapped addresses (DS:0xFFFF,0x0000–0x0002 =
  0x33b8:0x8b30 = chip's loaded CS:IP); RTL reads linear-forward without wrapping the 16-bit
  offset, hits unset memory → CS=0x9090. Single-valued: multi-byte memory-operand EA must
  wrap at offset 0xFFFF→0x0000.
- **0F1B/3917 — cyc-only.** Undocumented 0F INS-family read-modify-write byte form; DS operand
  MEMR/MEMW access scheduling diverges — likely the same mechanism as F1.
- **83.5/8683 — SUB word[BX],1, both.** Memory result matches (0xC062) but final PF diverges
  (chip PF=0 correct for 0x62, RTL PF=1) alongside an operand-RMW bus divergence (recurring
  0x63C0/0x83C0/0x62C0 DS-operand data). Anomalous — needs architect triage.

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

**SPLIT (Phase 2, 2026-07-20):** on characterization the 44,935 resolved into two
distinct signatures, NOT one law:
- **Family 5a — COLD (queue empty at the strio issue, 27,424 cases):** the RTL grants
  the next-instruction CODE prefetch EARLY, in the T3-eval slot right after the strio
  opcode fetch, ahead of the DS:IX/ES:IY element MEMR + port I/O. Chip defers that
  speculative grant. This is the pure request-arbitration-timing population. **RESOLVED**
  by the decision-time-scoped T3-eval veto (see resolution log).
- **Family 7 — WARM (queue non-empty at issue, 17,511 cases):** the element MEMR itself
  lands one bus slot late relative to the chip; the next-CODE grant is not the
  discriminator. The chip commits the element at the S_REQ instant (first eu_ready); the
  RTL one cycle later. Two exact sub-populations (Probe P4 step-0, measured):
  - **plain forms (6C/6D/6E/6F) diverge at initial qlen6 — pure idle window, 9,970**
    (2481+2528+2515+2446). No in-flight fetch; the late commit is via the plain staged
    idle path. Resolved by the **defer_idle main arm** (see resolution log).
  - **prefix forms (26.6E/36.6E/2E.6F) diverge at initial qlen5 — bridging-fetch window,
    7,541** (2482+2549+2510). The segment-override prefix's extra pop shifts occupancy so
    a bridging CODE fetch is in flight; the element commit is a missed defer_t4 pickup at
    that fetch's T4. Resolved by the **defer_t4 contingent arm** (general eu_soon at S_RSV).
  - **9,970 + 7,541 = 17,511 EXACTLY, zero stragglers.** The architect's earlier "~82
    window-edge stragglers" were the artifact of counting the prefix sub-class at qlen6
    (7,459); at the correct qlen5 it is 7,541 (+82) and the composition closes exactly.

**Method note (mis-characterization, recorded honestly):** Phase-1 characterization
measured only the next-instruction CODE-grant *position* and reported Family 5 as a
single cold-style "early-prefetch" family. That was wrong: it never sampled the element
MEMR position, so the warm population (which diverges in the MEMR slot, not the CODE
grant) was folded in under the wrong signature. The eu_hold experiment exposed it —
making COLD bit-identical while shifting every WARM case's MEMR one slot late (stop
condition #2). The corrected split above separates the two populations.

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
- **Family 5 (44,935, single string-I/O prefetch): eu_hold claim HELD at stop condition #2,
  then SPLIT + partially resolved.** The eu_hold claim (S_FIRST head-byte-peek + S_DEC) made
  COLD cases bit-identical but shifted the WARM/pf MEMR one slot late (all warm cases broken).
  Per the pre-registered stop condition, reverted. Root insight: cold and warm are two
  signatures, not one law (see SPLIT note under Family 5). Cold got a narrower, safer change:
- **Family 5a (27,424, COLD single string-I/O early-CODE-grant): RESOLVED** 2026-07-20 (commit
  below). Decision-time-scoped **T3-eval veto**: a new EU→BIU wire `eu_rsv_strio` (asserted for
  a non-REP strio single at S_FIRST head-byte-peek `q_byte[7:2]==011011` and at S_DEC
  `op_instr||op_outstr`) removes only `prefetch_ok` from the T3-eval pick at that decision
  instant (`pick_t3 = want_half2 || want_eu || (prefetch_ok && !eu_rsv_strio)`), so the
  speculative next-CODE grant is deferred to after the element MEMR + port I/O — matching the
  chip. Scoped to the T3-eval decision only; `req_ti_plain`/`prefetch_ok`/`eu_hold`/T4-flush
  slots keep `pick_any`. Gate: **cold 0/27,424**; flip-guards bit-identical — warm population
  (Family 7, ~17.5k), cold-prefix-T4 classes, classic strings A4–AF + prefixed, all REP strio,
  byte/word both (pre.txt==post.txt row-diff). Standing gates: w0 169000/169000, w1/w3 1200/1200;
  **wrand class-5 census 240/240 census-model configs bit-identical veto-vs-noveto → total 494u
  + DONE-guard 190u preserved**; v20 oracle 6C/6D 2000/2000 + A4/A5 5000/5000 arch; scramble 0
  failures; Quartus 17.1 A&S 0 errors, no inferred latch on `eu_rsv_strio`. **No new flops, no
  savestate struct change** (only wires/assigns + one EU→BIU port; BIU input gated to 0 under
  `scr_en`). Ledger 44,997 → 17,573 (Family 7 17,511 + Families 1–4 62).
- **Family 7a (9,970, plain-form qlen6 pure-idle element-late): RESOLVED** 2026-07-20 (commit
  below). **defer_idle main arm**: a new EU→BIU wire `eu_soon_strio` (`(state==S_RSV) &&
  (op_instr||op_outstr) && !rep_en`) arms the existing idle-window early-commit (`defer_idle`)
  alongside the reg-EA (`eu_soon_ea`) and IVT (`eu_soon_ivt`) sources, gated `q_aged==2'd0`. At
  S_RSV eu_ready is guaranteed next cycle (S_REQ) — the documented eu_soon contract, honored
  unconditionally. Brings the pure-idle element commit one cycle forward to the chip's S_REQ
  instant. Gate: plain 6C/6D/6E/6F **0/10,000** (9,970 qlen6 divergences → 0); flip-guards
  unchanged — prefix forms still 7,541 (contingent arm not yet landed), plain-qlen5 0, all cold
  0/5000 (F5a untouched), classics A4–AD 3000/3000, REP untouched by construction (`!rep_en`).
  No new flops (only wires/assigns + one gated EU→BIU port); `defer_idle` is an existing
  savestate flop, no struct change. Ledger 17,573 → 7,603 (Family 7 prefix 7,541 + Families 1–4 62).
  **Wait-suite note (coda correction):** F7a's arm (`ST_TI && eu_soon_strio && q_aged==0`) is
  independent of the eval path and fires under waits too (`cov_f7a_idle_arm` = 125 at both w0
  and w2), so its w1/w3 1200/1200 cleanliness is **EMPIRICAL, not structural** (unlike the F5a
  veto, which is structurally inert under uniform waits — `cov_f5a_t3_veto` 250→0 w0→w2).
- **Family 7b (7,541, prefix-form qlen5 bridging-fetch element-late): RESOLVED** 2026-07-20
  (commit below). **defer_t4 contingent arm** (architect-ratified): the general `eu_soon` is now
  set at S_RSV for a strio single (`eu_soon = (op_instr||op_outstr) && !rep_en`). Its single BIU
  consumer, the fetch-T3 `defer_t4` arm (`cur_fetch && eu_req && eu_soon && !eu_ready`, v30_biu
  :1481), catches the prefix-qlen5 bridging-fetch element read — a missed T3-eval pickup — and
  commits it mid-T4, matching the chip's element-status-on-the-fetch-T4 signature. Bus-state
  exclusive with the defer_idle main arm (defer_idle needs ST_TI at S_RSV; defer_t4 needs a
  fetch-T3). **Prefix-qlen6 stays clean** (double pop reaches occupancy 4 a pop-slot later → the
  bridge is granted 2 cycles later → its T3-eval lands after S_REQ, where the plain `want_eu`
  pickup already succeeds — architect). Gate: prefix 26.6E/36.6E/2E.6F **0/10,000** (7,541 qlen5
  → 0); flip-guards bit-identical — prefix-qlen6 clean, plain-qlen6 re-run 0 (joint with
  defer_idle), plain-qlen5 0, all cold 0/5000, classics incl. prefixed, all REP strio. general
  `eu_soon` has exactly one BIU consumer (:1481); eu_soon_ea stays S_EA2-qualified, eu_soon_ivt
  independent; scr_en gating covers scramble. No new flops (comb term only), no savestate struct
  change. **Family 7 → 0/17,511. Ledger 7,603 → 62 (Families 1–4 only) — string-I/O saga closed.**
- **Family 7 SILICON-CONFIRMED on hardware** 2026-07-20 (board A/B). Pre-flash the FPGA fabric
  was a pre-F7 build and diverged from the socketed chip with the exact Family-7 element-late
  signature (seed fz3 @ row 250); after flashing the F7 `.sof`, chip==fabric (fz3 MATCH, strio
  A/B 6/6 clean at w0). The before/after is a mini-A/B confirming the fix in silicon.
- **Random-wait note (coda, board):** at wmax=1 the strio corpus diverges chip-vs-fabric 17/25
  vs a no-strio baseline 7/25 — the PRE-EXISTING wait-accuracy gap (bus-heavy strio hits it 2.4x),
  NOT a coda regression (the F5a/F7 arms are cov-dormant at wmax=1, so they cannot drive it).
  Booked as premium census input for the future random-wait campaign. Limit: dormancy is
  sim-cov-based; the definitive pre-F7 A/B was declined on wedge-risk/value grounds.
- **NEW OPEN ITEM — Family 8 (LOCK-prefixed strio F0.6C-6F prefetch-ordering).** Leg-(c) chip
  tranche (100/form, socket) shows **F0.6C-6F 0/400 cycle (arch 400/400 clean)** — 100% divergent
  across all queue states, first-div partitioning by queue (cold→row5 / qlen5→row8 / qlen6→row10).
  It is the **Family-5/7 single-string-I/O prefetch-ordering divergence reappearing for the
  LOCK-prefixed forms**: the F0 prefix's extra decode cycle shifts the alignment so the F5a/F7
  arms mis-fire (cov for locked F0.6C: `f7a_idle_arm=0` vs 27, `f5a_t3_veto=27` vs 50) and the RTL
  reverts to the un-fixed early element commit; the chip commits late. **`!lock_en` gating REJECTED**
  (tested: cycle divergence unchanged 0/400, arch hurt 400→306). Fix = EXTEND the strio arms to the
  F0-prefix alignment (architect, like the seg-prefix qlen5 extension), NOT disable them under lock.
  Gate for the future fix = the F0.6C-6F captures + all standing strio flip-guards. Routed to the
  coordinator/architect; not landed. SPECs `F0.6C/6D/6E/6F` + `lockpfx` are in emit_suite.
- **Family 8 (LOCK-prefixed strio F0.6C-6F): NOT A LAW — a CAPTURE ARTIFACT (VOID)** 2026-07-20.
  The "LOCK-window bus-cycle STRETCH law" (+3 cold/+1 warm Tw) was an artifact of **stale wait-rig
  state (sticky-WRAND, 2nd occurrence)**: the f0lock tranche was captured 16:10 with R_WRAND still
  enabled from the F7-side leg-b wrand fuzz, minting phantom Tw in a waits=0 golden. Diagnosed by
  board evidence: (a) the F8 flash (17:11) wiped the rig → a live re-capture showed **0 Tw**; (b)
  within-build repeatability 10/10 deterministic (no flicker); (c) the capture path (nec_bus/nec_test
  /qsf/pins) was **identical** across the F7-golden and F8-live builds; (d) enabling WRAND on the
  clean board **reproduces phantom Tw** on F0.6C, the guard force-clean removes them. The SIM "fix"
  (commit eae1ecf, S1/S2/S3 + BUS_STRETCH + 4 flops + SS_VERSION 0x02) **REVERTED in full**; F5a/F7
  arms untouched, SS_VERSION back to 0x01, scramble re-run 60 PASS. **Re-captured CLEAN (0 Tw); the
  post-revert RTL passes F0.6C-6F 400/400 (cyc+arch)** — the string-I/O ordering was already correct,
  there is NO LOCK timing law. Guard MECHANIZED (v30run force-cleans R_WRAND+replay at every serve
  connect; emit_log records the wait-rig readback per emission). See the instrument-failure family
  entry below. Ledger stays 62.

## Instrument-failure family / provenance rules (task #24)

- **Stale wait-rig state (sticky-WRAND) — 2nd occurrence, now MECHANIZED.** A prior
  process leaves R_WRAND (seeded random per-access waits) enabled; a later capture that
  does not explicitly request waits inherits it and mints phantom Tw. First occurrence was
  handled by prose; the prose didn't survive. Family 8 (LOCK-strio) was the second victim —
  the f0lock tranche captured 16:10 with the F7-side leg-b fuzz's R_WRAND still live. **Now
  code:** `v30run.ServeRunner.ensure()` force-cleans the rig (WRAND 0 + replay 0,
  UNCONDITIONALLY) at every serve connect, defeating the sticky-None skip in
  `wrand()`/`replay()`; emit_suite logs the wait-rig readback per emission.
- **STANDING RULE: a Tw in a waits=0 golden is a PROVENANCE ALARM, not a law to fit.** Any
  wait state in a nominally zero-wait capture means the wait rig was dirty (or a genuine,
  separately-provenanced wait spec) — re-verify the rig state before characterizing.
