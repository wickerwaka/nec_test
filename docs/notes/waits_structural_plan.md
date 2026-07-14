# EU BUS-GRID-AWARE TIMING — structural refactor plan (Phase 0 design)

Authorized structural campaign to close the waits>=1 arbitrary-sequence
chip-vs-TB drift. Root cause (established, see closure_checkpoint.md
"ARCHITECTURAL READ" + biu_model.md): the chip's prefetch / EU-access /
reservation / retire / branch-resolution timing tracks the BUS GRID (each
bus cycle 4+N clocks under N waits); the EU issues these events off FIXED
CPU-cycle offsets (dly countdowns, per-state eu_req reservations, eu_done-
keyed multi-access transitions). At w0 the two coincide (fitted there);
under waits the grid stretches but the fixed offsets do not, so EU events
land on the wrong bus slot -> accumulating drift.

THE INVARIANT: the full 169000-case w0 golden stays bit+cycle-identical
after EVERY change. Every conversion is W0-NEUTRAL BY CONSTRUCTION — at
zero waits the bus-completion strobe / bus-cycle count coincides exactly
with the fixed CPU-cycle offset it replaces.

Baselines (HEAD, re-verified this session, board healthy):
- w0 golden 169000/169000; w1 golden 1200/1200; w3 golden 1200/1200.
- w1 drift (120 cached-chip seeds): bad-rows mean 818.3 median 743.0,
  CLEAN 1/120, addrMM 27, cumdrift mean 30.9, net@80 mean 1.0.
- w3 drift (60 cached-chip seeds): bad-rows mean 922.9 median 811.0,
  CLEAN 7/60, addrMM 4, cumdrift mean 39.7, net@80 mean 0.3.
Gate cost: full w0 golden = ~57s incl. build. Drift measure = measure.py.

--------------------------------------------------------------------------
## The measured strobes already in the BIU (what we build on)

- `eu_done` (eu_hand): handover follows the completion eval by one cycle.
  w0 = the T4 cycle; waited access = the cycle after T4 (eval_ext). This
  is the fixed CPU-cycle keystone that stretches +1 per waited access and
  causes the drift when multi-access transitions march on it.
- `eu_wdone` (biu line ~469): the WRITE zero-wait completion strobe,
  `eu_completing && cur_wr && ((TW && !tw_any) || (T4 && evald))`. Fires at
  the write's T4 at w0 (== eu_done there) and at the FIRST Tw under waits
  (one cycle earlier than eu_done, at the zero-wait completion point). This
  is the PROVEN pattern: PUSHA + far-CALL push chains march on it.
- `ext_ok` / `ext_ok_wr` (eu_ready_p1/p2 registered-readiness qualifiers):
  the T4-registration eval qualifier the RMW-write fix uses.
- `eu_rd_now` / `eu_rdata_now` (biu line ~392): a COMB read-data strobe at
  the read's final data edge (end of T3/Tw) with the assembled data. Fires
  once per non-split EU read. At w0 it is the T3 edge (one cycle before the
  read's eu_done/T4); under waits it is the LAST Tw edge (the cycle the
  read data actually lands). ALREADY EXISTS — 9D POP-PSW uses it.

--------------------------------------------------------------------------
## The bus-grid-aware primitives (this campaign adds)

### P1. `eu_rdone` — read-completion strobe (mirror of eu_wdone)
    assign eu_rdone = eu_completing && !cur_wr &&
                      ((state == ST_TW && !tw_any) || (state == ST_T4 && evald));
Identical form to eu_wdone but gated on `!cur_wr` (reads). w0-NEUTRALITY:
at w0 there is no Tw, so eu_rdone == (T4 && evald); at w0 evald is set at
the T3->T4 edge (READY high), so eu_rdone fires during T4 — EXACTLY where
eu_done (eu_hand, also set at eval_at_t3) fires. So at w0 eu_rdone coincides
with eu_done bit-for-bit; any transition re-keyed eu_done->eu_rdone is w0-
identical. Under waits eu_rdone fires at the FIRST Tw — one cycle earlier
than eu_done — keeping the next access's request+reservation up in time for
the BIU deferred completion eval to place it on the bus grid contiguously.

DATA CAVEAT (the "address/data decoupling" the checkpoint names): under
waits eu_rdone (first Tw) fires BEFORE the read data lands (eu_rd_now, last
Tw). So a read->read transition keyed on eu_rdone may issue the next
ADDRESS early but MUST latch the current read's DATA separately at
eu_rd_now. At w0 the order is reversed (eu_rd_now at T3 precedes eu_rdone at
T4), so the decoupling must capture data at eu_rd_now regardless of state —
the capture is armed by "the current EU read is <this operand>" flag, not
by the state we happen to be in when the data edge fires.

### P2. `bus_tw` — "bus stretched this cycle" tick suppressor
    assign bus_tw = (state == ST_TW);
Exactly the N extra wait cycles a waited bus cycle inserts (bus_ts folds
T3+TW together, so a dedicated signal is needed). w0-NEUTRALITY: at w0
there are ZERO Tw states, so bus_tw is identically 0 — any dly countdown
gated `if (!bus_tw) dly <= dly-1` decrements every cycle exactly as today
=> bit-identical at w0. Under waits a bus-grid-aware dly pauses during the
Tw stretch, so a dly of D elapses after D non-wait cycles — staying at the
same bus-grid position as w0 instead of firing early. This is the primitive
for the dly families (S_JWAIT resolution, S_WAITX/S_EX retire + prefetch-
resume, the S_A4_G*/ie_dly inter-access gaps). Some contexts also stretch
across the eval_ext deferral cycle; those get `bus_tw || eval_ext` — also
w0-zero — decided per context.

--------------------------------------------------------------------------
## Inventory + classification of every fixed-CPU-cycle mechanism

Legend: [STROBE]=convert via eu_rdone/eu_wdone; [BUSDLY]=convert via bus_tw
tick; [DATADEP]=data-dependent, correctly STAYS eu_done-keyed (not a gap);
[RSV]=eu_req reservation, wait-aware reservation timing; [OK]=already bus-
grid friendly (chains on eu_started / bus strobe), no change.

### A. eu_done-keyed multi-access transitions (v30_eu sequencing)
- S_A4_SRCW  read->read (src done -> issue dst addr): [STROBE eu_rdone +
  decouple a4_src via eu_rd_now]. "drifts FIRST per byte" (checkpoint).
- S_A4_DSTW  read->write (dst done -> compute -> write mem_op): [DATADEP]
  write data = BCD compute of the read; STAYS eu_done. Correct, not a gap.
- S_A4_WRW   write->read (write done -> issue next src addr): [STROBE
  eu_wdone] pure PUSHA pattern, no decoupling.
- S_IE_R1W / S_IE_R2W (INS/EXT reads): transition eu_done then enter
  S_IE_WAIT with an `ie_dly` gap before the next read/write. [BUSDLY on
  ie_dly] + the read-data merges (eu_wdata = f(eu_rdata)) are [DATADEP].
- S_IE_WRW  write->read (split word-1): chains on eu_started [OK] or via
  ie_dly [BUSDLY].
- S_CMPW1->S_CMPW2 (CMPBK first->second read): eu_done chain. Second read
  is issued as a fixed reservation; [STROBE eu_rdone] candidate; the
  compare itself is [DATADEP] (flags = f(both reads)).
- S_CMPW2 / S_SCASW next-iteration: eu_done then dly=3 wnext=S_RSV ->
  S_WAITX. [BUSDLY on the S_WAITX dly] (the inter-iteration gap).
- S_FRETW (RETF/IRET 2-3 word stack reads): address chains on eu_started
  [OK]; data on eu_done [DATADEP for fl_ip/fl_cs, but no early-address gap].
- S_STRR/S_STRW/S_STRS (MOVBK/STM): chain on eu_started [OK] already.
- S_LD_W1/W2, S_MHI/S_MLO (two-word reads): done+N chains — inspect;
  likely [STROBE eu_rdone] for the read->read and [BUSDLY] for the +N.
- S_BUSW: PUSHA/far-CALL already on eu_wdone [DONE]; A0/A1 moffs data
  [DATADEP]; RET/RETF retire [eu_done, fine].

### B. dly countdowns (reg `dly`, 6-bit; reg `ie_dly`, 12-bit burn)
Every `S_WAITX`-driven wait and every explicit `dly<=K` gap:
- S_WAITX generic wait (wnext=S_EX / S_REQ / S_JDISP / S_RSV / IVT): the
  general dispatch/retire/pre-access wait. [BUSDLY] where the wait spans a
  bus grid the chip tracks; some are pure EU-internal compute (DIVU/MUL
  burn, wait-insensitive) and must NOT be gated (they are correct as fixed
  CPU cycles — EU-bound ops are wait-insensitive, biu_model exp 5). Split
  needed: bus-facing waits (retire->prefetch-resume, pre-read/pre-write
  lead-in) get bus_tw; compute burns (DIVU 28, MUL, IDIV, ie runaway,
  ROL4/4S nibble-serial) do NOT.
- S_JWAIT branch/loop resolution (op_jcc/op_loopf/EB/E9/CALL): [BUSDLY]
  the chip's flush tracks the bus grid (~2 cyc later under waits). HIGH
  golden risk (branch tranches are the most w0-fitted family). Gate hard.
- S_A4_G1/S_A4_G2 (ADD4S inter-access gaps): [BUSDLY] the +2/+4 gaps.
- S_PREP_* dly gaps (PREPARE pointer-copy): [BUSDLY].
- S_RMWX dly (write ready pop+2/pop+4): [BUSDLY]/[RSV] — already partly
  handled by eu_defer_wr; the dly gap to the write is bus-facing.
- ie_dly (INS/EXT inter-access + tail): [BUSDLY] for the bus-facing legs;
  the field-shift tail (IE_TAIL, 256*len runaway) is a compute burn, NOT
  gated.

### C. eu_req reservations (always_comb, per state)
Most reservations key on `dly==1` (the cycle before S_REQ/write) — these
are ALREADY bus-grid-relative (they lead the request by one cycle and only
matter when a prefetch competes; w0-neutral no-ops otherwise). The PREMATURE
-under-waits reservations flagged by the checkpoint:
- S_EA1/S_EA2 reg-EA reader reservation (eu_soon/defer_t4): fitted at w0;
  shares path with fitted 8B/disp readers. [RSV wait-aware] — risky.
- S_DISP8/S_DHI disp-reader reservation: [RSV] premature under waits
  (blocks a prefetch the chip lets through). Shares S_REQ with fitted
  readers. Narrow-phase shared-path floor (grind round 3). DEFER.
- S_JWAIT/S_JDISP/... branch reservations: coupled to the S_JWAIT dly.
These are the hardest (no wait-independent form to distinguish); attempt
LAST, only if the strobe+dly families leave a reservation-shaped residual.

### D. Confirmed NOT gaps (leave as-is)
- Data-dependent writes (ADD4S mem_op, INS/EXT merged eu_wdata, string
  fwd): STAY eu_done/eu_fwd. Correct.
- EU-bound compute burns (DIVU/MUL/IDIV/ROL4/4S-nibble/ie-runaway): wait-
  insensitive by measurement; fixed CPU cycles are CORRECT.
- String read->write/next chains already on eu_started (S_STRR/W/S).

--------------------------------------------------------------------------
## Conversion order (most w0-neutral / least risky first)

1. PRIMITIVES (Phase 1): add eu_rdone + bus_tw, wire through v30_core.
   Prove w0-neutral by the 169000 golden with the first strobe conversion
   present (eu_rdone==eu_done, eu_wdone==eu_done, bus_tw==0 all at w0).
2. ADD4S read-loop (Phase 2 first family): S_A4_WRW write->read on
   eu_wdone (pure PUSHA pattern); S_A4_SRCW read->read on eu_rdone with
   a4_src decoupled to eu_rd_now; S_A4_DSTW->write STAYS eu_done (DATADEP).
   w0-neutral: all three strobes == eu_done at w0; a4_src latched at the
   src read data edge (same value). Niche (2-4 seeds) but the cleanest
   eu_rdone exemplar and lowest golden entanglement outside the branch
   family.
3. bus_tw on the ADD4S inter-access gaps (S_A4_G1/G2) — same family, tests
   the bus_tw primitive on a low-risk dly.
4. String/CMP/SCAS next-iteration inter-access (S_WAITX dly) via bus_tw.
5. S_WAITX retire -> prefetch-resume (the ~3-idle bus-grid prefetch-resume
   law, op99 CWD etc.) via bus_tw — broad but shared; measure carefully.
6. INS/EXT ie_dly bus-facing legs via bus_tw.
7. (RISKIEST, LAST) S_JWAIT branch/loop resolution via bus_tw; then the
   S_EA/S_DISP disp-reader reservations. Only if a residual remains and a
   wait-aware form can be distinguished without regressing the branch/reader
   golden tranches. May be the genuine floor.

Per family: FULL 169000 golden bit+cycle-identical (INVARIANT) AND w1/w3
drift measured (bad-rows mean/median, CLEAN count, cumdrift, net@80). Commit
per converted family (RTL + this doc + biu_model.md). Reflash only after a
batch of families is banked.

--------------------------------------------------------------------------
## Progress log (this campaign)

### Round 1 (this session) — primitives landed + ADD4S characterized + empirical retarget

**Phase 1 primitives LANDED + PROVEN w0-neutral (committed):**
- `eu_rdone` (v30_biu): read-completion mirror of eu_wdone, `!cur_wr` gated.
- `bus_tw` (v30_biu): `state==ST_TW`, the wait-cycle stretch tick.
- Wired BIU->core->EU. Full w0 golden 169000/169000 held with them present;
  w1 drift EXACTLY baseline (mean 818.3 median 743.0), w3 baseline — the
  primitives are present-but-inert, zero behavior change (the clean Phase-1
  proof). Available infrastructure for the family conversions.

**Phase 2 first family — ADD4S read-loop via strobes: ATTEMPTED, REVERTED
(valuable NEGATIVE finding).** Converted S_A4_SRCW read->read to eu_rdone
(with a4_src decoupled to eu_rd_now) and S_A4_WRW write->read to eu_wdone.
w0 golden held 169000/169000 (w0-neutral by construction, as designed). BUT
w1/w3 drift got WORSE, not better:
- read->read on eu_rdone: w1 mean 818->845, median 743->801, net@80 1.0->2.9.
- write->read on eu_wdone alone: w1 mean 818->814 (marginal +) but w3 mean
  923->934, median 811->837 (net negative).
ROOT CAUSE of the negative: the drift is core-FASTER-than-chip (net@80 > 0,
core runs FEWER cycles). The strobes (eu_rdone/eu_wdone) fire EARLIER than
eu_done under waits -> issue the next access even earlier -> core faster ->
OVERSHOOTS the gap. The strobe pattern is RIGHT for a context where the core
is inserting a SPURIOUS extra bus cycle (PUSHA/far-CALL: eu_done let a
prefetch splice in, so marching early REMOVED a core bus cycle = faster =
matched). It is WRONG for ADD4S, where the chip's measured "dst @ srcdone+2,
write @ dstdone+4" laws track the STRETCHED src/dst completion (eu_done),
NOT a bus-grid-early point, and the core is not inserting a spurious cycle.
Reverted to eu_done (kept as a documented code comment in S_A4_SRCW).

**DIRECTION LAW (this round's key structural insight).** The residual drift
is core-faster-than-chip. To CLOSE it the core must run MORE cycles (slower)
under waits, i.e. STRETCH a fixed offset via `bus_tw` (the dly counts bus
cycles, pausing during Tw). The `eu_rdone`/`eu_wdone` strobes move the other
way (earlier=faster) and only help the narrow class where the core inserts a
spurious extra bus cycle at eu_done (PUSHA/far-CALL, already landed). So the
GENERAL closing lever is `bus_tw` on dly countdowns, NOT more strobe
conversions. eu_rdone stays available for any future spurious-cycle read
context but is not the general tool.

**EMPIRICAL RETARGET — drift-context histogram (localize.py, 60 w1 seeds,
drift cycles attributed to the EU-state-set active in each divergent inter-
fetch interval).** Top contexts (state names decoded):
| drift | states | meaning |
|---|---|---|
| 217 | S_FIRST,S_DEC,S_NOP | basic retire -> next-opcode cadence (DOMINANT) |
| 183 | S_FIRST,S_DEC,S_IMM_LO,S_IMM_HI | MOV reg,imm16 imm-pop cadence |
| 118 | S_FIRST,S_DEC,S_WAITX,S_EX | dispatch-wait + execute-retire |
|  76 | S_FIRST,S_DEC,S_NOP,S_EX | retire + post-op idle |
|  75 | S_FIRST,S_DEC,S_NOP,S_JDISP,S_JWAIT,S_JNT | branch resolution |
|  73 | S_DLO,S_DGAP,S_DHI,S_REQ,S_BUSW,S_WAITX | disp16 reader |
|  68 | S_AIGAP,S_DLO,S_DGAP,S_DHI,S_REQ,S_BUSW | disp reader (imm) |
|  56 | S_FIRST,S_DEC,S_JDLO,S_JDHI | E8/E9 disp-jump |
ADD4S states (S_A4_*, 49-58) do NOT appear in the top 25 — it is genuinely
niche (confirming the ADD4S strobe move was low-value AND wrong-direction).

The DOMINANT drift is the retire / prefetch-resume / decode cadence shared by
EVERY instruction (S_FIRST/S_DEC/S_NOP + S_WAITX/S_EX retire). This is the
bus-grid prefetch-resume law (biu_model exp4: "prefetch resumes after 3 idle
cycles" after an EU access; closure_checkpoint: "~3 idle cycles the TB does
not model under waits"). It is a [BUSDLY]/BIU-prefetch-cadence problem, not a
strobe problem, and it is the highest-value target.

**Round 2 conversion order (empirically retargeted, measure-first):**
1. Retire -> prefetch-resume cadence (the S_FIRST/S_DEC/S_NOP + S_WAITX/S_EX
   mass). LOCALIZE this context cycle-by-cycle FIRST (dumpctx/+eudbg on a
   fetch-limited seed) to find whether the fix is a `bus_tw`-gated EU retire
   dly (S_NOP/S_EX) or a BIU prefetch-resume stretch. Highest value, shared
   by all instructions -> gate w0 golden hard after every micro-step.
2. MOV reg,imm16 imm-pop cadence (S_IMM_LO/HI) via bus_tw — contained, high
   count, medium risk.
3. disp16 reader (S_DLO/DGAP/DHI) — the reservation/reader; shares path with
   fitted readers (grind-round-3 floor). Attempt only after 1-2.
4. Branch/Jcc resolution (S_JWAIT) via bus_tw — highest golden risk, last.
Each: full 169000 w0 golden bit+cycle-identical AND w1/w3 drift SHRINKS
(bad-rows mean/median down, net@80 toward 0). The DIRECTION LAW says every
correct conversion here stretches a fixed offset (slower core), reducing the
core-faster gap.
