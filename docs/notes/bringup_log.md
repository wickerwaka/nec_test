# Bring-up log

## 2026-07-17 — H-PHASE LANDED + SILICON-CONFIRMED. Chain closed: synth 0-err (setup +5.228ns), flash OK, fabric==TB on RMW 15/15 (even->early/odd->late) + per-cycle-random T1-exact + w2 2260/2260. CODE->MEM RMW cell E->A, census 494.

SYNTH: quartus_sh --flow compile - Full Compilation successful, 0 errors, worst-case SETUP
slack +5.228ns (hold +0.253, recovery +29.497, removal +0.818, pulse +1.196); fresh .sof
13:54 (> RTL 13:29).
FLASH: sw/safe_flash.sh - Configuration succeeded 0 errors, VERIFY ok (cfg 0x1ff0008,
harness reachable, board healthy).
SILICON-CONFIRM (fabric use_core=1 vs TB): RMW cases uniform w1/w2/w3 fabric==TB 15/15,
0 mismatch (even->interval2 EARLY / odd->interval4 LATE on real silicon - the Tw-parity
law transfers with no synth surprise); per-cycle-random (fz90007/10/17/19) fabric==TB
T1-exact every aligned access, 0 resyncs; w2 610/610 (uniform w2, 12 seeds) fabric==TB
2260/2260 T1+bs exact, 0 resyncs.
"w2 610/610" is the FABRIC==TB check (a8fafdb), NOT the check_seq chip-vs-TB fuzz - the
--fuzz 610 --waits 2 diverges 609/610 at an IDENTICAL boot-prefix row (0 EU-writes, fz87284
0 widen fires): a pre-existing harness prefix artifact, NOT this fix. Disregarded.
RESULT: the H-PHASE ext_ok_wr Tw-parity widen is LANDED and SILICON-CONFIRMED. CODE->MEM
RMW-write cell class E -> A. Census 544 -> 494.
PIGGYBACK SKIPPED (session time): pf_starved toggle-census needs its OWN synth+flash+census
cycle (an RTL toggle, not a runtime flag) - deferred per the "skip if tight" option; stays
booked. BOOKED for FRESH PROBES (not widens): CODE->MEMR loads (17u, interval-3) and the 2
odd-parity-early rows. No leaks; board healthy.

## 2026-07-17 — H-PHASE CENSUS: fix WORKS on-scope (RMW-write cell 58u->8u, -50u), goldens hold, DONE-guard 190->190, w0 0/22188. Raw CODE->MEM 26u > 15u target (out-of-scope loads 17u + 4-row residual). Report-and-hold; NO second widening.

ONE census with the landed fix (sw/class5_census_hphase.jsonl.gz, fixed gaperr, per-cycle-
random, seeds 90000-19, wmaxes 0/1/3/7). vs OLD 544b:
  total |ge| 544 -> 494 (-50u).  w0 control 0/22188 (w0-neutral).  no new transition class.
  DONE-guard unpaired CODE->CODE: 190 -> 190 (EXACTLY held).
  CODE->MEM 76 -> 26:
    IN-SCOPE CODE->MEMW RMW-write cell: 58u -> 8u (-50u, the dominant mass removed).
    OUT-OF-SCOPE CODE->MEMR loads: 17u -> 17u UNCHANGED (probe (c) excluded loads - a
      SEPARATE mechanism, not a fix miss; interval-3 class, needs its own probe).
    residual 4 CODE->MEMW rows (8u): board-free inspection - 2 are ODD-parity RMW where
      the CHIP is early (H-PHASE edge cases at random-wait phases the 4-vector probe
      subset did NOT sample; the census prev_tw field even logs them parity-0, a
      chip-vs-model predecessor-frame discrepancy) + 1 NON-RMW even-parity store (a
      different sub-cell, uses ext_ok not ext_ok_wr) + tail.
GATES: w0 169000/169000, w1 1200/1200, w3 1200/1200 (all PASS); model-side even->interval2
/ odd->interval4 confirmed. (w2 gate + uniform-RMW gate NOT yet run - flagged.)

VERDICT: the fix is REAL and CORRECT on its scope - it removed the RMW-write ready-AT-T4
even-parity cell (50u), w0/w1/w3-clean, DONE-guard held, no new class. The raw CODE->MEM
<=15u target is NOT met (26u) but is DOMINATED by out-of-scope MEMR loads (17u) + a small
residual (8u); it is BELOW the pre-registered >30u falsifier, so NOT a partial-mechanism
trip. Per the veto-stacking rule (>30u -> no second widening; here <30u), do NOT stack a
second predicate. The 4-row residual + the MEMR loads each need a FRESH probe, not a
widen. STOPPED before synth/flash: architect rules whether the on-scope success (goldens
+ DONE-guard + 50u) justifies proceeding, or the residual is investigated first. Fix
committed (13933b4); reverting is a one-line un-widen if the architect prefers.

## 2026-07-17 — H-PHASE PARITY HOLDS (30/30, 0 violations, both groups, random+uniform) -> BUILD. Loads excluded (write-handshake-specific). tw_par flop + ext_ok_wr widen.

The architect's finer phase: Tw parity = T4's displacement against the 2-clock bus
microcycle; the RMW write handshake is phase-aligned (even-tw T4 on-phase -> readiness
captured for the deferred commit -> EARLY; odd-tw T4 off-phase -> capture one slot later
-> LATE). Scored the FROZEN prediction (no fitting) board-aligned, random + uniform
w0/w1/w2/w3, 14 seeds. Key = parity of the predecessor CODE fetch's Tw.

SCORE - ready-AT-T4 (rdy_p1 && !rdy_p2) CODE->MEMW RMW writes, n=30:
  chip vs parity: (even, EARLY) 23 / (odd, LATE) 7 - PERFECT SPLIT.
  RANDOM: 0 violations (even-EARLY 10, odd-LATE 4). UNIFORM: 0 violations (even-EARLY 13,
  odd-LATE 3; u1->LATE odd, u2->EARLY even, u0/u3 class-absent). seed-group EVEN: 0 viol
  (n=26). seed-group ODD: 0 viol (n=4). => PARITY HOLDS, 30/30, both groups, both regimes.
  (This retro-explains my earlier "non-monotonic code_tw": 0/2/4 even->EARLY, 1 odd->LATE -
  it was PARITY, read as a threshold.)
(c) MEMR (loads, n=255): does NOT split on parity - all eu_defer_wr=0 (not RMW), interval
  mostly 3 (a different commit class), odd-parity mostly EARLY (107 "violations"). So the
  mechanism is WRITE-HANDSHAKE-SPECIFIC, not kind-independent bus-phase. FIX SCOPE =
  ext_ok_wr ONLY; loads are NOT covered and stay as-is.

BRANCH: PARITY HOLDS -> BUILD (full protocol). RTL observable = one flop `tw_par` (clear
at ST_T1, toggle every ST_TW, sample at the completion eval) - purely local, no wait-
pattern term, no history; NOT grid_phase (erases displacement + post-wait carry landmine),
NOT ph_now (forces T4 phase 1, :1272). Widening: ext_ok_wr gains
`(eu_ready_p1 && !eu_ready_p2 && !tw_par)` (EXACT polarity: even/!tw_par -> accept/early).
ext_ok_wr is consulted ONLY for eu_defer_wr=1 (RMW) so loads are automatically excluded.
The 3 odd-parity random rows STAY LATE (correct). Build steps below.

## 2026-07-17 — UNIFORM-RMW RE-CHECK: BRANCH (ii). ready-AT-T4 RMW is chip-EARLY at w2/random but chip-LATE at w1 — same local observable, opposite behaviour. code_tw is non-monotonic. STOP; architect hunts sub-T4 phase. Do NOT widen, do NOT park.

The one measurement that adjudicates the ext_ok_wr widening (board, read-only, uniform
w1/w2/w3, 12 seeds; freshness + 0 leaks verified). RMW-write (eu_defer_wr=1) CODE->MEMW,
by ready-phase at the eval cycle:
  rdy_p1=0,rdy_p2=0 (not ready)        n=12: chip LATE  12, model LATE  12  (agree)
  rdy_p1=1,rdy_p2=1 (ready ENTERING T4) n=18: chip EARLY 18, model EARLY 18  (control - matches
     the original sweep_rmw fit: ext_ok_wr accepts, both early)
  rdy_p1=1,rdy_p2=0 (READY-AT-T4, the CELL class) n=15: chip EARLY 12 / LATE 3; model LATE all 15
     -> EARLY are ALL uniform w2 (12/12); LATE are ALL uniform w1 (3/3).
DECISIVE: the SAME local observable (ready-AT-T4 RMW) is chip-EARLY at uniform w2 (and in
the random census, 26/29 CODE->MEMW ge=-2) but chip-LATE at uniform w1. Opposite chip
behaviour by wait level -> BRANCH (ii). Widening ext_ok_wr to accept ready-AT-T4 would fix
w2/random (-2 -> 0) but REGRESS the w1 cases (chip late, model already correct -> would go
+2 early). NOT safe to widen.

FINER-PHASE LEAD (for the architect's hunt): at uniform the split is exactly code_tw
(predecessor CODE-fetch Tw): EARLY all code_tw=2, LATE all code_tw=1. BUT code_tw is
NON-MONOTONIC on the random census: the chip-early ge=-2 rows include prev_tw=0 cases (3
CODE->MEMW + 6 CODE->MEMR) as well as prev_tw>=2 (25). So the ordering is code_tw=0 EARLY,
code_tw=1 LATE, code_tw=2 EARLY - code_tw ALONE is NOT the finer phase. The distinguisher
is a finer sub-T4 readiness/CODE-stretch timing that code_tw only proxies at uniform.

PER BRANCH (ii): STOPPED, did not widen. Do NOT park (the architect's pre-registered "one
more level" - sub-T4 readiness timing - has not been exhausted; the non-monotonic code_tw
is evidence a finer local phase MAY exist). Architect re-enters to hunt it before any wall
#3 declaration. If no finer local observable separates chip-early from chip-late at
ready-AT-T4 across BOTH uniform and random -> THEN wall #3 (temporal/observability) and the
~72u CODE->MEM cell parks. Instrumentation (d[68..74]) + sw/class5_hext.py in place; the
uniform-RMW re-check is documented here (board capture, not a committed script - it needs
run_chip).

## 2026-07-17 — H-EXT PROBE: BRANCH A fired, but the denial is EXT_OK_WR (RMW-write rule), not ext_ok. Arithmetic board-confirmed; sweep_rmw contradiction is the open caveat. Report-and-hold.

The CODE→MEM -2 cell mechanism (sw/class5_hext.py + .log). H-EXT (denial composition):
chip commits the MEM at the eval_ext DIRECT slot (T4+1 fire, delta1 -> T1=T4+2); the
model's qualification rejects it -> plain STAGED path (T4+2 fire, delta2 -> T1=T4+4); 2
clocks = one lost slot + one delta.

BOARD-ALIGNED (run_chip + align, 29 confirmed ge=-2 CODE→MEMW across the census combos):
ARITHMETIC CONFIRMED - model interval CODE-T4→MEMW-T1 = 4 (all), CHIP interval = 2 (all),
fired slot TI_PLAIN (all), eval_ext fires in the CODE completion window (all). BUT the
denying clause is NOT ext_ok (rule A/B, as H-EXT assumed) - it is EXT_OK_WR (v30_biu.sv:522
= eu_ready_p1 && eu_ready_p2, "ready ENTERING T4"):
  25/29 RMW writes (eu_defer_wr=1) with ext_ok_wr=0 (rdy_p1=1, rdy_p2=0). Under per-cycle-
    random waits the write-readiness arrives AT T4 (p1=1,p2=0) -> ext_ok_wr denies -> the
    RMW write is placed 2 clocks late; the chip takes the eval_ext direct.
  4/29 NON-RMW minority (eu_defer_wr=0, ext_ok=1 ACCEPTS) - a DIFFERENT mechanism, tagged
    OUT, not averaged (~8u).

BRANCH (pre-registered): eu_ready FIRST-high offset from CODE-T4 = 0 (ready DURING T4, one
cycle BEFORE the T4+1 eval); the chip commits at T4+1 AFTER ready is available -> it does
NOT precede eu_ready -> NOT branch B, NOT the trip-wire. **BRANCH A**: eu_ready live at the
eval with leading eu_req -> fix direction = QUALIFICATION WIDENING of ext_ok_wr to accept
ready-AT-T4 (eu_ready_p1 alone), the same acceptance ext_ok already gives PLAIN stores.

PHASE-CLASS (board-free, goldens): the cell's RMW class is ABSENT from w1/w3 (0 RMW writes;
the suite's opcode-89 is a plain store). NOTABLE: the w1 golden has 64 PLAIN-store commits
at the SAME ready-AT-T4 phase (rdy_p1=1,rdy_p2=0) that PASS via ext_ok accepting -> ready-
AT-T4 -> EARLY is proven CORRECT for plain stores; only ext_ok_wr's extra rdy_p2 makes RMW
writes late. So the widening makes RMW match the already-correct plain-store behaviour.

OPEN CAVEAT (why report-and-hold, architect re-enters): ext_ok_wr was FITTED on sweep_rmw.py
(ADD word[mem],imm, UNIFORM w0-w5), which measured ready-AT-T4 RMW -> chip commits LATE
(plain, rdT1→wrT1=14). The random census measures the OPPOSITE (ready-AT-T4 RMW -> chip
EARLY). Same observable (ready AT T4), opposite chip behaviour by wait regime. EITHER the
architect's readiness-phase-class thesis holds (uniform never generates the random class; a
finer observable phase exists to widen on) OR it is a same-observable RMW wall (park). The
w1/w3 goldens CANNOT adjudicate (no RMW opcodes). A UNIFORM-RMW re-check (sweep_rmw-style,
board, ready-AT-T4) is the missing decisive measurement before any widening - it answers
whether the widening regresses uniform RMW. STOPPED before fix design; architect re-enters
with this caveat. Map status: the CODE→MEM cell (~72u; ~58u RMW ext_ok_wr + ~8u non-RMW +
~6u tail) is now MECHANISM-IDENTIFIED (ext_ok_wr over-strictness), fix gated on the
uniform-RMW adjudication.

> **READ FIRST: [class5_campaign_record.md](class5_campaign_record.md)** — the standalone
> closing record of the class-5 timing campaign (floor table + closure classes, the
> CODE→EU verdict, laws/deletions/kills, the instrument-failure family, method rules, and
> the what-first list). This bring-up log is the chronological detail beneath it.

## 2026-07-17 — CODE→EU PROBE: a key SEPARATES (CODE→MEM ge=-2, ~72u). Block NOT key-exhausted; map has one open fixable cell. Campaign record archived.

The last never-attacked block (CODE→EU, 125u, 23% of census). Form-free, board-free
(sw/class5_codeeu.py + .log), fit(even)->FREEZE->score(odd). RESULT: eu_kind=MEM
SEPARATES - CODE->MEM (MEMW store + MEMR load) is a near-CONSTANT ge=-2 (36/38=95%, model
places the EU access 2 clocks LATE), GENERALISES on both seed groups (even 28/30, odd 8/8
PURE), FLAT across cur_tw 0-5 (wait-INDEPENDENT) and d_cnt@EU-T3. Commit path dominantly
TI_PLAIN (30/36), NOT the eval_ext-deferred ext_ok path (5) - so it is the PLAIN
EU-commit-after-CODE timing that is 2 clks late under random waits (the architect's
ext_ok-A/B hypothesis is partly off; enumerate the plain commit). CODE->IOW scattered
(~47u, asymptote). Per the ruling (key separates -> report cell + STOP before fix design):
architect re-enters at the CODE->MEM -2 cell (~72u, class E attackable). Key-exhaustion
is NOT claimed - a key WAS tried and separated. Campaign record committed:
docs/notes/class5_campaign_record.md (cross-linked above). New: sw/class5_codeeu.py + .log.

## 2026-07-17 — FORECAST PROBE -> KILL. Both candidate signals fail to separate at the commit cycle. The WHOLE MEMW->CODE store-resume cell (~28-34u) PARKS: mechanism-understood, IRREDUCIBLE-BY-CONSTRUCTION. Last named cell CLOSED.

BUILD was decided (board 3/3 chip_occ5), but the fix requires a FORECAST of the off-3
pop available at the off-2 commit cycle. Probed BOTH pre-registered candidates
board-free (sw/class5_forecast.py + .log), on TRUE=20 confirmed pop_first==3 rows (17
random + 3 uniform, must forecast TRUE) vs FALSE=144 pop_first in {1,2} (incl. the 30
pop_first==2 & occ@T4==6 over-fire rows, must forecast FALSE):
  (a) EU-side schedule (pop_want/q_avail/eu_dly, d[51..53]): pop_want==0 holds for all
      20 TRUE but ALSO for the pop_first==1 confound (29 rows) - and as a FIRE rule
      (occ5 && Ti && !eval_ext && pop_want==0) it fires 66x at w0 (NOT w0-safe) and
      false-fires 22x on chip_occ4. eu_dly==0 everywhere (no scheduled-pop countdown
      exposed). FAIL.
  (b) cnt_next@store-T3 + pop cadence: cnt_t3 is {5,6} for BOTH TRUE and FALSE; pop_sr/
      pop_cnt do not separate. FAIL.
The ONLY w0-absent discriminator is pop_first==3 ITSELF (the actual pop at off-3), and
that is NOT observable until AFTER the off-2 commit. THE CHIP COMMITS BEFORE THE ONLY
EVENT THAT DISTINGUISHES THE CASE - a genuine forecast law whose forecast the model
does not expose at the commit cycle.

VERDICT (per the pre-registered rule: neither separates -> STOP): the ~17u pop_first==3
subset PARKS WITH the ~22u residual. The WHOLE store-resume cell (~28-34u, 5% of census)
is CLOSED as mechanism-understood but IRREDUCIBLE-BY-CONSTRUCTION. This is a STRONGER
irreducibility claim than "no key separates": the commit is temporally prior to the
discriminating observation - the model would have to predict a pop it cannot yet see,
using internal EU-scheduler state the RTL does not carry at that cycle. Board-confirmed
real chip behavior, provably unfixable w0-safely with the model's observable state.

STATE: no RTL landed (enable was already reverted). The shadow fields
(last_was_store/recent_evx/store_pf_boost, eudbg d[66..67]) are now inert
instrumentation for a CLOSED cell - may be stripped at the architect's discretion (I
left them: behaviour-neutral, all goldens hold w0 169000 / w1 1200 / w3 1200). The
timing family's map is now COMPLETE: every named cell is either a landed fix, H-SLIP
scatter of a built law, or a mechanism-understood irreducible-by-construction floor.
This store-resume cell is the second kind's sibling - the FIRST cell closed by a
temporal-observability argument. Flag to the architect for the floor restatement.

## 2026-07-17 — DECISION: BUILD (board-confirmed). Uniform-w1 pop_first==3 store-resumes are chip_occ5 3/3. Fix is a FORECAST+LAG release (not a naive occ==5 boost) - design finding.

The pop-phase probe left one question: are the (fuzz-derived) uniform pop_first==3
rows chip_occ5 (BUILD) or chip_occ4 (PARK)? The chip-captured GOLDEN could not answer:
across ALL 33 w1/w3 golden store-resumes (occ@T4>=5) EVERY one is pop_first==2 ->
chip_occ4 (the exact 14+19 that broke under recent_evx); ZERO are pop_first==3. So the
golden confirms the phase-lock (uniform code phase-locks to pop_first==2) and shows NO
pop_first==3 chip_occ4 counterexample, but it contains no pop_first==3 store to label
the fuzz rows.

TARGETED BOARD CAPTURE (authorized, read-only run_chip, uniform w1, seeds
90009/90017/90018 - the 3 fuzz pop_first==3 rows): chip vs model, aligned:
  seed90009 ka85 occ@T4=5: mg=9 cg=8 ge=-1  -> chip_occ5 EARLY
  seed90017 ka48 occ@T4=5: mg=9 cg=8 ge=-1  -> chip_occ5 EARLY
  seed90018 ka50 occ@T4=5: mg=9 cg=8 ge=-1  -> chip_occ5 EARLY
3/3 chip_occ5. pop_first==3 -> chip resumes early UNIVERSALLY: random waits 17/17,
uniform w1 3/3, ABSENT at w0 (0/348). The mechanism is a real physical pop-PHASE law
(pop in the lag window at T4+3 -> commit at occ5), holding across wait patterns WITH NO
WAIT TERM. DECISION: BUILD the pop_first==3 fix (~17u); the residual pop_first in {1,2}
occ5 (~11-22u) PARKS (genuinely unfixable w0-safely: same local state is chip_occ4 at
w0/uniform-pop_first<=2 and chip_occ5 at random - unobservable context).

FIX-DESIGN FINDING (from the pop_first==3 trace, seed90009 uniform w1):
  st4=544 occ5; off1(545) occ5 EVAL_EXT; off2(546) occ5; off3(547) occ4 POP, model
  fires TIPL here -> T1 549 (cidle 4). Chip commits at off2 (occ5, BEFORE the off3 pop)
  -> T1 548 (cidle 3). So the release is a LATCHED FORECAST + LAG (architect was right):
  at the off2 commit cycle pop_first==3 is NOT yet observable (pop is at off3), and a
  naive "occ==5 && post-store" boost ALSO over-fires on pop_first==2 when occ@T4==6
  (occ==5 then occurs at a committable off2). => the fix needs a FORECAST of the pop
  crossing available at the commit cycle (candidates: EU-side schedule pop_want/dly/
  eu_dly at d[51..53], or cnt_next@store-T3 + the pop cadence), NOT the post-hoc pop
  offset. This is the open design piece before the shadow. Same FAMILY as H-SLIP
  (max/deadline), DIFFERENT CELL - do NOT merge sites.
NEXT: forecast predictor -> shadow (fire the occ5 release on the latched forecast) ->
w0 gate -> w1/w3/w2 with NO wait term -> census (pop_first==3 subset ~17u -> <=4u;
residual unchanged; DONE-guard 190+-10) -> synth/flash/silicon. Standing authorization.

## 2026-07-17 — POP-PHASE PROBE: architect's mechanism CONFIRMED (pop_first==3 -> chip resumes early, w0-ABSENT by arithmetic). PARTIAL: 17/39 occ5 fixable, ~22 alias to w0 -> PARK. Last named cell of the timing map.

sw/class5_poprelease.py + .log (board-free). The architect PRE-REGISTERED (before this
probe) that the chip resumes at DEMAND-CROSSING-FORECAST + LAG, commit-occupancy (5 vs
4) an EPIPHENOMENON of whether a pop lands in the lag window; discriminator = pop@T4+k
relative to the store's completion frame; recent_evx measured wait PRESENCE not pop
PHASE. CONFIRMED.

POPULATION (filter lesson applied): ALL post-MEMW CODE resumes with occ@store-T4>=5,
INCLUDING the matched chip-occ4 rows - 161 rows, 39 chip_occ5 (early, = census ge=-1)
/ 122 chip_occ4 (ge=0, the complete nonzero census record). Real baseline (all-occ4)
75.8%.

THE DISCRIMINATOR - pop_first (offset of the FIRST pop after the store's T4):
  pop_first==3 -> chip_occ5 PURE: 17/17, 0 false-positives. Generalises on a BALANCED
    split (even seeds 6/6, odd 11/11; the disc/held split is useless here - only 2 occ5
    rows land in disc). And pop_first==3 is ABSENT at w0 (0/348 w0 resumes) and occurs
    only 3x at uniform w1/w3. So arming the occ==5 release on pop_first==3 is w0-neutral
    BY THE KEY'S OWN ARITHMETIC (the pattern never arises at w0) - the mechanism, NOT a
    wait flag. KILL(ii) AVOIDED. This is exactly the architect's pop-in-lag-window at
    T4+3 -> chip commits at occ5.
  pop_first in {1,2} -> MIXED (22 occ5 not separated). These ALIAS to w0: pop_first
    in {1,2} occur at w0 (306 at 1, 42 at 2) and store_tw==0 (which dominates the
    residual occ5) is w0-identical - the same local state is chip_occ4 at w0 and
    chip_occ5 under random waits, so it is UNFIXABLE w0-safely. (This is the same wall
    the recent_evx attempt hit, now explained: it is not that recent_evx was the wrong
    gate for these rows - there IS no w0-safe local gate for them.)

VERDICT: architect's mechanism REAL; the fix is PARTIAL. pop_first==3 cleanly recovers
17u w0-safely (~half the ~28-34u population); the residual ~22 occ5 rows (pop_first
1,2 / store_tw==0) alias to w0 and must be PARKED (economy rule: the whole cell is 5%
of census). This CLOSES the last named cell of the timing family's map either way.

FIX SHAPE (if pursued) + PRE-REGISTERED ACCEPTANCE TEST: arm the occ==5 store-resume
release on pop_first==3 (a latched "first pop after store T4 landed at offset 3"),
NOT recent_evx. The DECISIVE test the architect pre-registered: w1/w3 goldens PASS with
NO wait-pattern term anywhere - the 3 uniform pop_first==3 rows must be chip_occ5 by the
same arithmetic (if they are chip_occ4, pop_first==3 aliases at uniform too and the whole
cell parks). Same FAMILY as H-SLIP (max/deadline), DIFFERENT CELL - do NOT merge fix
sites. Shadow fields (d[66..67]) + sw/class5_poprelease.py are the instrumentation.
HOLDING for the architect's ruling on partial-fix vs full-park before any RTL.

## 2026-07-17 — MEMW->CODE -1 FIX: ENABLE REVERTED at the golden gate. w0 169000/169000 PASS but w1/w3 BROKE (over-fire) -> the -1 is wait-PATTERN-specific, not "any waited regime". Shadow kept. Architect re-enters.

Step 3b under full protocol. Textual enumeration (grep-first): pf_lim (:353) consumed
only by prefetch_ok (:354); prefetch_ok feeds pick_any(:474), prefetch_ext(:545),
selected_plain_pf_grant(:594), legacy_prefetch_grant(:781). The store-resume commits
via req_ti_plain -> pick_plain -> prefetch_ok, so a latched occ==5 boost on prefetch_ok
reaches it. No site found after implementation started.

MECHANISM LOCALISED (traces): the store completes with the queue full (occ 5-6); the
resume is gated by occupied<=pf_lim(4), so the model waits for the decoder to drain a
byte (occ->4) then commits (TI_PLAIN, normal 2-cycle fire->T1). The chip commits ONE
occupancy-level earlier (at occ==5) -> resumes 1 clk sooner. The model behaves
IDENTICALLY at w0 and under waits for the same occ state; eval_ext (fires at the store
deferred completion, never at w0) is the only local w0-vs-waited discriminator, so the
fix was a wait-gated occ==5 pf_lim boost.

FIX (shadow-first, sw/-validated): last_was_store latch (cur_type is cleared to PASV at
the store's T4, so a persistent "last cycle was a MEMW store" latch is needed) +
recent_evx (cycles-since-eval_ext, saturating 0xF at w0) + store_pf_boost = last_was_store
&& recent_evx<=7 && ST_TI && occ==5 && !(eu_req|eu_hold) && q_aged==0 && !q_flush, ORed
into prefetch_ok's occ<=pf_lim.
SHADOW VALIDATION (log-only, before enable): w0 SILENCE 0/176358 w0 cycles; census
MEMW->CODE unpaired 28/28 ge=-1 COVERED, 0 false-flip, projected column 34u -> 6u
(<=10u target MET). recent_evx (not the store's own eval_ext) was needed because 12/28
ge=-1 rows are store_tw=0 stores whose only w0-absent signal is a PRECEDING waited
access's eval_ext at a consistent offset -4.

GOLDEN GATE RESULT:
  w0 169000/169000 PASS (the decisive w0-neutrality gate - the recent_evx=0xF gate holds).
  w1 1200 -> 1186/1200, w3 1200 -> 1181/1200 FAIL. ALL failures in opcode 89
  (MOV r/m,r = a STORE): busstat exp PASV got CODE, tstate exp Ti got T1 - the model
  starts the CODE prefetch 1 cycle EARLY where the chip-reference golden stays IDLE.
DIAGNOSIS: at UNIFORM w1/w3 the chip does NOT resume the post-store prefetch early (it
stays at occ4 like the old model); at RANDOM waits (the census) it DOES (ge=-1). The
-1 turnaround is WAIT-PATTERN-specific, not a function of "any waited regime". recent_evx
fires in both patterns (confirmed: boost fires at uniform w1), so it cannot discriminate
random-wait-early from uniform-wait-late. The occ==5 interpretation over-generalises.

PER PROTOCOL FALSIFIER (goldens must hold): ENABLE REVERTED (prefetch_ok back to
occ<=pf_lim; w1/w3 restored to 1200/1200, w0 re-verified). The SHADOW is KEPT
(last_was_store/recent_evx/store_pf_boost computed, unwired, emitted at eudbg d[66..67])
for the re-derivation. No census run (goldens gate before census, correctly).

FOR THE ARCHITECT (re-entry point): the observable (-1, 28/28 random-wait) is real and
mechanism-confirmed, but it is NOT landable via a wait-regime gate - it needs a
discriminator that separates the random-wait store-resume (chip early) from the
uniform-wait one (chip late). Candidates NOT yet tried: the exact queue-drain PHASE
(pop_sr / pop timing relative to store T4), or the specific preceding-access pattern.
The occ==5-vs-occ==4 commit is the right lever; the ARMING predicate is the open
problem. Tooling: sw/class5_storeanchor.py (mechanism), the shadow fields in the TB.
w0-golden was the RIGHT decisive gate (it passed); the w1/w3 goldens caught the
over-generalisation the census alone would have missed - exactly why goldens are
necessary though not sufficient.

COORDINATOR RULING (revert ACCEPTED, 2026-07-17): execution correct end-to-end - w0
gate passed, w1/w3 caught the over-generalisation BEFORE a census could bless it,
revert per the pre-registered falsifier, shadow kept, no synth/flash spent. The w1/w3
suites just EARNED THEIR KEEP as the UNIFORM-PATTERN GATE: they are NOT a waits-
accuracy gate, but they are the only coverage of the uniform-wait regime - which is
exactly what caught this (the census is random-wait-only). FRAMING CORRECTION: the
-1 is WAIT-PATTERN-specific, not wait-regime-specific (-1 at random waits 28/28, NOT
at uniform w1/w3, NOT at w0). HOLD on further RTL for this fix until the architect
returns a discriminator that separates random-wait store-resume (chip early) from
uniform-wait (chip late). The shadow fields (last_was_store/recent_evx/store_pf_boost
at eudbg d[66..67]) stay as the instrumentation for that discriminator.

## 2026-07-17 — MEMW->CODE -1 MECHANISM CONFIRMED (store-T4->resume turnaround constant, wait-specific). w0 pre-flight: NOT structurally safe -> fix must be wait-gated. Report boundary BEFORE RTL.

sw/class5_storeanchor.py + .log (board-free: model store-anchored fields from the
Verilator TB; chip cidle = model cidle + census ge). Join 31/36 MEMW->CODE census rows
to store-anchored model transitions.

=== MECHANISM CONFIRMED ===
On unpaired MEMW->CODE (n=31 matched): 28/31 at ge=-1 (model resumes 1 clk LATE after a
store), eu_wr=1 (all real stores). Store-T4-anchored:
  model store->resume cidle: dominated by 4 (19 rows); chip cidle: dominated by 3.
  The model's turnaround is a CONSTANT that overshoots the chip by exactly 1 idle clk.
INDEPENDENCE (=> genuine constant, not state-dependent):
  by occ@T4+1 : occ5 -> ALL 20 at ge=-1; occ6 -> ALL 8 at ge=-1 (28/28 at normal
    post-store occupancy). The 3 outliers are the occ4/cnt_next@T3=3 cell (ge +2/-2/-2)
    - a SEPARATE small cell (~5u), not the constant.
  by store Tw : -1 flat across store_tw 0..4  (NOT the store's own waits)
  by pop@T4+2 : -1 flat across pop 0,1        by store parity: -1 flat
  by cnt_next@T3: cnt5 -> all 19 at -1; cnt6 -> all 9 at -1.
CROSS-SEED-GROUP: disc(90007) 2/2 = 100%; held(90008/09/13/17/18/19) 26/29 = 90%.
Holds across both groups and 7 distinct seeds -> generalises.
This is EU-anchored territory the CODE->CODE resume law was never fitted on (Step 1b:
the CC law does NOT transfer to EU->CODE), so it is a genuinely new, small-radius fix.

=== w0-SAFETY PRE-FLIGHT (measured, not assumed - the coordinator's flag) ===
The store->resume path IS exercised at w0: 246 w0 MEMW->CODE transitions in the
fix-target state (occ@T4+1 in {5,6}), model cidle = 4 present (60 rows) - the SAME
value the fix would change - where the model already matches the chip (w0 golden
169000/169000). So an UNGATED -1 fix would MOVE the w0 golden -> NOT STRUCTURALLY SAFE.
The DEFECT is WAIT-SPECIFIC: the model's fixed turnaround is CORRECT at w0 (chip also
takes 4) and 1-late only under waits (chip takes 3). => the fix must be WAIT-GATED
(eval_ext-style, exactly like the class-5 law's w0-neutrality mechanism), and its
w0-neutrality VERIFIED at the golden gate, not assumed. Recoverable ~28u (the 28
ge=-1 rows); acceptance target MEMW->CODE column ~34u -> <=10u per the plan.

NEXT (step 3b, NOT started - report boundary here): textual enumeration of the
store-resume commit path; shadow-first wait-gated -1; w0 golden gate (the decisive one
given the pre-flight); w1/w3/w2 goldens; ONE census with DONE-guard invariant
(unpaired CODE->CODE 190u +-10) + MEMW->CODE ~34u -> <=10u. Then synth/flash/silicon.

## 2026-07-17 — ARC 2 RE-MAP (Tasks 1-3, board-free): DONE re-ratify recommended (H-SLIP-explained scatter); ONE new fixable finding = MEMW->CODE uniform -1 kind-offset. Coordinator's IO-offset guess falsified.

sw/class5_remap.py + sw/class5_remap.log. All board-free on class5_census544b.jsonl.gz
(chip ground truth baked in as ge = chip_gap - model_gap). My greedy matcher is now
authoritative (the lost 288u matcher is disqualified as irreproducible).

=== TASK 1a — AUTHORITATIVE MATCHER + SENSITIVITY (error bars) ===
Definition: greedy nearest-partner opposite-sign match, ONE-TO-ONE, within an
access-ordinal window; each member used once. AUTHORITATIVE = (window=1, exact).
  paired 148u / unpaired 396u  (72/286 rows).
RECONCILIATION: my first-pass flag-based number (161u) double-counted cancellation
CHAINS by 13u/6 rows (a middle impulse cancels two neighbours); the one-to-one greedy
148u is the principled figure. Sweep error bars: exact {148,186,202}u at window
{1,2,3}; loose(|sum|<=1) {226,268,298}u. Pairing is window-sensitive - this is the
error bar the re-map ships with.

=== TASK 1b — DISJOINT ACCOUNTING (every row -> ONE triple) ===
286 rows / 544u, each assigned exactly one (pairing, transition-class, law-cell).
  transition-class x pairing (mass): CODE->CODE 95p/190u (285); EU->CODE 34p/95u
  (129); CODE->EU 19p/106u (125); EU->EU 0p/5u (5).
The old (q_cnt 2-4, MEM) 150u / (q_cnt<=1, MEM) 133u were overlapping-set keyed
marginals - RETIRED as map entries; they are not columns of this disjoint table.

=== TASK 1c — DONE RE-SWEEP on corrected unpaired CODE->CODE (105 rows/190u) ===
Was 79/121u under the lost matcher; the enlarged population's largest SIGN-PURE clean
cell is 8u and largest NET(|sum|) cell is 8u - BOTH < the 10u floor. The apparent
15u cell (1,0,2) is H-SLIP TAIL (6/7 rows have a -2 partner at ordinal di<=3, i.e.
slot-scale pairs the window=1 matcher just missed); (0,3,3) is MIXED-SIGN (total 15u,
net 7u - cancels, not a single fixable cause). VERDICT (my read): RE-RATIFY - the
genuine residual is mixed-sign small-cell scatter, no clean >=10u cell. Window/purity-
sensitive; architect makes the final ratification call.

=== TASK 3 — H-SLIP (paired CODE-successor 129u) ===
(a) |N| histogram: |N|=2 dominant (94u), slot-scale (|N|<=2) = 78%. (b) paired
CODE->CODE (44 rows/95u): 100% land in POPULATED law cells, 82% slot-scale. H-SLIP
SUPPORTED (>=80% fitted): the paired mass is the built resume law's +-1..2 slot
DELIVERY scatter (retry +1s / duration 5-vs-183 misses / decline scatter) wearing the
"ordering" label - not order swaps (which would be access-length scale >=4). Per the
Task-3 outcome rule (>=80% fitted), the resume asymptote is mechanism-explained
scatter and DONE re-ratifies with the documented scatter shape.

=== TASK 2 (1) — EU-anchored resume, KIND-OFFSET CHECK: MEMW BUG, IOW SCATTER ===
Unpaired EU->CODE 54 rows/95u; ge = model-chip cidle offset, grouped by predecessor
kind:
  MEMW->CODE: n=34 mass=39  near-CONSTANT ge=-1 (28/34 = 82%, model resumes 1 clk
    LATE after a store), across 6 seeds / all ws / all wmax / all even successor-parity
    -> KIND-OFFSET BUG candidate (store T4 -> resume turnaround), the TOP deliverable-
    preference and a SMALL-radius fix (advance post-store CODE resume by 1 clk).
  IOW->CODE: n=15 mass=43 net=+3 SCATTER (no dominant offset) -> the coordinator's
    IO-cycle-length guess is FALSIFIED; asymptote candidate.
  MEMR->CODE: weak -2 (4/5), low n (13u).
Confirming the MEMW mechanism needs the EU-anchored dump (occ@EU-T4+1, pop@T4+2, cidle
from EU-T4); step (1) localises the observable offset and gates that as the next step.

=== NET FOR THE ARCHITECT ===
The re-map resolves the resume floor as mechanism-explained: paired 129u = H-SLIP slot
scatter (built law), unpaired CODE->CODE 190u = mixed-sign small-cell scatter (largest
clean cell 8u). DONE re-ratify recommended. The ONE new actionable finding is
MEMW->CODE's uniform -1 offset (~28-33u, small-radius kind-offset fix) - the first
concrete fix candidate to survive the re-map. Carve-outs SETTLED (untouched). No RTL
changed; goldens undisturbed; no tempdir leaks.

## 2026-07-17 — ARC 2 ARBITER-SURFACE PROBE: HARD KILL. The 288u/161u paired mass is NOT the want_eu>prefetch arbitration family (88% is prefetch-timing); no want_eu-demotion discriminator separates it. Blast-radius surgery NO-GO. Rule B DROPPED.

Board-free probe (sw/class5_arbiter_probe.py, sw/class5_arbiter_probe.log). Added 4
APPEND-ONLY commit-slot observability fields to the eudbg dump (tb d[62..65] =
want_eu, slot_fire, slot_id, eu_kind - all existing DUT signals; DUT bit-identical;
TB rebuilt clean, no %Error). The chip ground truth is already in
class5_census544.jsonl.gz; the probe only re-derives the MODEL arbiter state via the
Verilator TB and JOINS on successor-access-only fields (cur_bs/cur_par/cur_tw +
m_state/m_occ/m_qcnt/m_qaged - NOT prev_bs/mti, which are alignment-dependent and
diverge from model-adjacency exactly at the swap sites). Join 259/286 (91%) matched;
that match rate - model signatures from the NEW binary against census fields from the
OLD binary - IS the bit-identical freshness confirmation (a changed DUT would collapse
it). Corollary applied: scored against the REAL arbiter (want_eu), baseline printed.

=== THE HYPOTHESIS IS FALSIFIED BY THE DIRECT want_eu SIGNAL ===
Premise: at the swap sites the model committed the EU access via want_eu, and a
conditional want_eu demotion (starved queue + demand-deadline) recovers the 288u
paired mass. Measuring want_eu directly at every census successor commit:
  - want_eu-decided census mass is only 122u of 544 (22%). The other 344u (78%) are
    prefetch/other commits (want_eu=0) a want_eu demotion CANNOT touch.
  - Of the strict-paired mass (161u, my documented reconstruction; PROBE 1's 288u
    used a lost ad-hoc matcher): 142u (88%) are CODE-successor PREFETCH commits
    (want_eu=0); only ~1u is actually want_eu-committed. Paired transitions are
    dominated by CODE->CODE (50 rows) = prefetch-RESUME timing, not EU/CODE
    arbitration. PROBE 1's label "paired = arbitration-swap family (owns_slot)" was
    itself an inference the direct arbiter signal does NOT support - a re-attribution.

=== GO GATE: HARD KILL ON BOTH CRITERIA (form-free grid, board-free false-flip) ===
Agreeing (ge==0) want_eu denominator = 3883 model want_eu commits NOT joined to a
nonzero census row (board-free). A demotion predicate firing there is a false-flip.
  predicate        cover(want_eu mass)   false-flip(vs 3883 correct orderings)
  q_cnt<=1  (the candidate)   32% (39u)        58.1%   <- inseparable
  q_cnt<=1 & kind=MEM          1% ( 1u)        26.7%   (the "REP-string MEM" guess: the
                                                        q_cnt<=1 want_eu mass is IO, not MEM)
  q_cnt<=1 & kind=IO          31% (38u)        31.4%
  d_cnt<=1 (best cover)       60% (73u)        65.0%
  eval_ext                    38% (46u)        73.1%
NO predicate reaches >=60% cover with <2% false-flip; every coverage-bearing predicate
fires on 7-77% of CORRECT orderings. KILL criteria (coordinator's own): coverage <40%
for the candidate AND false-flip >=2% for ALL -> the paired mass is not one mechanism,
and no separating discriminator exists. The conditional-want_eu-demotion arbiter
surgery (largest-radius surgery of the campaign - every pick_* mux, defer paths,
display laws) is a NO-GO. Do NOT enter the blast radius.

=== RULE B: DROPPED ===
Per the plan, Rule B lands only inside the arbiter fix's commit-series (shared census)
and is dropped if the arbiter probe fails. The probe failed -> Rule B is dropped as a
pipelined change. It remains a documented, derived, validated patch in the prior
log entry (+0.3-0.4pt, fi 0.062%) if ever revisited standalone, but it is NOT pursued.

=== PARALLEL FINDINGS (sized, not acted on) ===
(4) EU-anchored resume, *->CODE with EU predecessor: 110u (IOW->CODE 58u, MEMW->CODE
38u, MEMR->CODE 14u). An INDEPENDENT resume-timing mechanism (successor is a CODE
prefetch, want_eu=0), NOT arbitration. Form-free resume fit is a separate future
investigation; sized here.
(5) Carve-out re-scores vs the REAL baseline: pf_starved fires at 47 census sites /
87u (entangled with live census error); pf_late_rsv 2u, owns_slot 6u, eu_rsv_lead 2u.
These are association counts, not deletion counterfactuals - a real deletion test needs
an RTL toggle + census (behavior-change run, out of this board-free probe's scope).
FREEZE holds: they are real-outcome-fitted; the prior (they STAY) stands.

=== RE-ATTRIBUTION FOR THE ARCHITECT ===
The 544u census is dominated by PREFETCH-timing (want_eu=0): 344u of 466 matched is
prefetch commits, concentrated at (q_cnt 2-4, MEM) 150u and (q_cnt<=1, MEM) 133u.
This is CODE-resume / prefetch-cadence territory (the class-5 resume law's domain,
declared at its honest floor), NOT an arbitration surface. The want_eu>prefetch
priority is not the lever. Architect re-enters to re-attribute the prefetch-timing
mass; the arbiter-surgery arc closes NO-GO here.

## 2026-07-17 — ARC 2 STEP 2 DERIVATION: re-key benefit is ~10x smaller than the audit headline (PROXY ARTIFACT). Pre-shadow findings boundary; enable NOT started.

The Step-2 task hands a benefit premise: *->CODE prefetch grant 93.09% -> 98.85%
(+5.76pt, ~287 flip-correct rows held-out) as the justification for the bus-claim
re-key, with the census target to be "derived from the ~287 attributable rows."
Deriving the exact RTL rule from the shadow corpus (class5_alltrans.jsonl.gz, disc
90000-07 / held 91000-05, the a17dad4/b38e082 dump) BEFORE enable - as the spec
requires - shows that premise is 78% a PROXY ARTIFACT. New analysis:
sw/class5_busclaim_realmodel.py (companion to class5_busclaim_audit.py).

THE BUG IN THE PREMISE (not in RTL - in the counterfactual's model):
class5_busclaim_audit.py scored the model with model_go = !eu_req, IGNORING the rest
of prefetch_ok. The REAL RTL grant is
    prefetch_ok = !(eu_req || eu_hold) && occupied <= pf_lim(=4) && q_aged == 0
so the model ALREADY pauses on occ>4 and q_aged!=0. Those two gates are absent from
the proxy, which therefore scores every occ>4 / q_aged!=0 pause as "model grants ->
model wrong -> table flip-correct." There are 416 rows in the corpus alone with
eu_req=0, occ>4, chip-paused that the proxy mis-attributes this way.

DECOMPOSITION of the audit's 287 *->CODE flip-correct (held), verified reproducible:
  ALREADY correct under the real RTL occ<=pf_lim / q_aged gates : 223 (via occ>4 219,
                                                                  via q_aged!=0 16)
  GENUINELY new (real RTL model also wrong)                     : 64
Of the 64 genuinely-new, most are NOT separable by any readiness key (e.g. signature
eu_ready=0,eu_req_p1=0,q_cnt<=1,occ2,cnt_next2 is 9 chip-pause vs 2928 chip-GO -
catching it injects thousands of false pauses; the pf_lim=2 lesson again). Only the
q_cnt>=5 cell (~10) and the eu_req_p1=1 cells (~7) are clean.

REAL implementable benefit, *->CODE held (real-RTL model semantics), from the two
rule forms the spec's readiness key admits:
  MODEL (real RTL)  : 91.12%    flip-correct   0  flip-incorrect  0
  Rule A REPLACE    : 91.51% (+0.39pt)  fc 25  fi 6 (0.123%)   claim = !eu_ready &&
                      eu_req_p1 && cnt_next>=2   (drops eu_req; the spec's stated key)
  Rule B SURGICAL   : 91.43% (+0.31pt)  fc 18  fi 3 (0.062%)   claim = eu_req &&
                      (eu_ready || (eu_req_p1 && cnt_next>=2))  (keeps eu_req; only
                      re-decides the contested eu_req==1 && eu_ready==0 cell - the
                      exact 446-slot w0 region the spec flagged; w0-safest)
So the genuine attributable held-out benefit is ~15-25 NET rows (~0.3-0.4pt), not
+5.76pt / 287 rows. Flip-incorrect stays far under the 2% no-build bar either way -
the re-key is NOT harmful, just ~10x smaller than advertised. Rule B is the cleaner,
w0-safest, spec-consistent form (it changes behavior ONLY in eu_req==1 && eu_ready==0;
never touches eu_req==0 nor eu_ready==1, so its w0 exposure is bounded to the flagged
446 slots and it does not rely on want_eu priority for correctness).

WHY THIS IS A REPORT-AND-HOLD, NOT A PROCEED: the number the task hands me AS the
benefit is the one shown to be a proxy artifact, and the census ACCEPTANCE target is
to be derived from it. Sizing a census (~40 min) + synth + multi-hour flash pipeline
against 287 when the genuine figure is ~15-64 would mis-set the acceptance bar.
Per the standing rule (thresholds re-derived from CURRENT composition, never carried
forward; report data not direction; do not tune past a freeze). The exact RTL rule
is DERIVED and ready (Rule B, drop-in at v30_biu.sv:354 both ternary branches,
replacing `eu_req` in the claim with `(eu_req && (eu_ready || (eu_req_p1 &&
cnt_next>=2)))`; the enumerated twin prefetch_ext:545 inherits it via prefetch_ok).
Architect re-enters here to re-confirm GO with the corrected benefit and to re-derive
the census acceptance target before the shadow/w0/synth/flash spend. No behavior
change has been landed; goldens untouched.

## 2026-07-16 — LOW-band duration-control ATTEMPT FAILED + harness quota bug fixed

Two findings, both worth not repeating.

(1) HARNESS TEMP-DIR LEAK -> DISK QUOTA -> whole environment wedged (fixed,
commit 1d0a819). run_tb_internal (causal_wrand), run_tb (check_seq) and
class5tax's run_base each did tempfile.mkdtemp() and NEVER cleaned up: one dir
(holding a multi-MB eudbg/out dump) leaked per TB invocation - hundreds per census.
32,209 stale dirs (~9.3 GB) accumulated in /tmp and exceeded the user's disk QUOTA.
Symptom was baffling: EVERY shell command failed (the Bash tool's cwd write got
EDQUOT) while df showed the filesystem had free space; read-only tools still worked,
which is what made it diagnosable (a Write probe returned EDQUOT). All three now use
try/finally + shutil.rmtree, verified 0 leak over a full 400+ vector census.
LESSON: a census that dies with a generic "TB failed"/exit-1 may be the QUOTA, not
the RTL - check writability before blaming the design.

(2) LOW-BAND DURATION CONTROL: attempted (Fable's top recommendation) and REVERTED
- it makes things WORSE. Baseline (the landed simple veto, commit 7f81e90):
|mass| 422, net +100, 192 impulses. With the counted pause + force-grant gating
prefetch_ok: |mass| 580, net -46, 286 impulses (-2 exploded 14->75, -1 40->74).
The suppression genuinely delays the resume past where the chip resumes and the
forced slot does not land on the chip's; the lb_ctr<->cidle calibration is wrong.
STRUCTURAL FINDING (the valuable part): prefetch_ext is consulted ONLY on the
eval_ext cycle - the ordinary-idle commit path uses pick_any -> prefetch_ok. So
gating prefetch_ext alone is a NO-OP from arm+1 onward. That is why three separate
variants (simple veto, +counted pause, +force-grant) produced BYTE-IDENTICAL
censuses (192/+100/422): everything after the arm cycle was dead code. Any resume
DURATION control must gate prefetch_ok (both paths), not prefetch_ext. Also note a
suppress-only gate can NEVER fix the model-LATE (-1) cases - suppression only
delays further (Codex/Fable both said this; it is now measured).
NEXT (do NOT blind-iterate - each census is ~40 min and 4 were burned here):
INSTRUMENT first - dump the model's actual resume slot (successor T1 - pred_T4)
with the FSM active and compare against the verified target table
(occ4 age{1,2}->cidle 4, occ4 age3->3, occ3 age2->3) to calibrate lb_ctr<->cidle,
THEN re-run one census. The landed simple veto (422) remains the best low-band
state; the mid-band fix (d378fe6) remains clean + silicon-confirmed.

## 2026-07-16 — CLASS-5 MID-BAND fix landed (8086 insight; -10% class-5 mass)

The 8086 prefetch-band rule (Ken Shirriff, righto.com: queue 0-2 -> fetch; 3-4 ->
DELAY 2 clocks; 5-6 -> blocked) REOPENED class-5. Band-age replay
(sw/class5_bandage.py over the full CODE->CODE opportunity population) found the
class-5 mid-band 50/50 boundary we had called "irreducible" was TIMER-STATE
ALIASING: for q_cnt in the 3-4 band, band-age (CE clocks continuously in 3-4)
separates chip GO (age 0) from chip PAUSE (age>=5) - 0/169 held-out. So the
earlier "observable floor" conclusion was WRONG for the mid-band (right for the
low-band). w0-GO and waited-PAUSE overlap at the SAME band-age (both age>=5 at
w0 too), so the delay is WAIT-DEPENDENT, not a unified queue policy; and the pause
applies only at the CODE-fetch-completion resume edge (eval_ext && cur_fetch) -
the global and broad-eval_ext forms shattered w1/w3.

Fix (commit d378fe6): band34_age counter; midband_pause = eval_ext && cur_fetch &&
q_cnt in {3,4} && band34_age>=2 && q_aged==0 && !q_flush && !eu_hold; ANDed into
prefetch_ext (same shape as the eu_req=0 pf_rsv_lead). w0-NEUTRAL by the eval_ext
gate. Validation: w0 169000, w1/w3 1200 (bit+cycle exact); random-wait gap-error
census (18 seeds) |mass| 557->501 (-10%), net +267->+233, +3 impulses 67->52, NO
new negative tail (both positive and negative mass down; -4/-5 tail shrank). The
FIRST clean class-5 mass reduction (cf. pf_lim=2 -> -291 blowup, Phase S NO-GO).
RESIDUAL: the low-band (q_cnt 0-2) EU-drain pauses (all eu_consuming=1) remain a
separate mechanism at the observable floor - needs Codex's controlled band-ladder
(tests B/E), not the mid-band timer. Threshold is >=2 (the dump gap is age 1-4,
GO at 0 / PAUSE at >=5, so 2..5 are equivalent on the measured data).

SILICON-CONFIRMED (bitstream flashed, setup slack +6.014 ns): FABRIC(use_core=1)
== TB on all tested class-5 vectors (fz90007/90011/90002/90015, random waits) ->
the -10% improvement transfers to fabric with no synth surprise. (One chip-vs-
fabric diff fz90011 bus80 IOW/CODE is a pre-existing non-mid-band residual;
fabric==TB there confirms it is not synthesis.)

ALSO FIXED - a latent PHASE-R SYNTHESIS bug (Phase R was validated Verilator-only,
never synthesized): the named-field struct assignment pattern
pick_desc = '{bus_type: ..., ube_n: ...} is rejected by Quartus 17.1 A&S
("ube_n is not a constant"). Replaced with the equivalent positional packed-struct
concatenation. w0 169000 preserved (Verilator shadow asserts confirm field
alignment). The whole biu-arb-qcnt design now synthesizes (A&S 0 errors, Full
Compilation successful). LESSON: Verilator acceptance != Quartus synthesizability;
run a Quartus build after structural RTL refactors, not only the Verilator goldens.

## 2026-07-15 — PHASE R: eval_ext/do_commit PATH UNIFICATION landed (behavior-preserving)

Implemented Phase R of the commit-path unification (docs/notes/class5_path_unification_plan.md,
Codex-planned; opus sub-agent executed). The BIU's two commit paths (direct-entry
eval_ext/ff/defer vs staged do_commit) are now canonicalized into ONE slot decision
slot_fire/slot_id/slot_mode/slot_desc; direct-vs-staged is delivery metadata only.
11 stages R1-R7 (commits 2dc1228..be667df on biu-arb-qcnt), one commit each, gated
after every step. BEHAVIOR-PRESERVING - proven:
- w0 169000/169000, w1 1200/1200, w3 1200/1200 bit+cycle exact at every stage
  (independently re-verified at HEAD be667df).
- class-5 control traces fz90007/fz90011 BYTE-IDENTICAL to the R0 baseline at every
  stage (board-free run_tb_internal, uniform wv).
- Extra: --assert binaries built at R5/R6c/R7, full suites + a class-5/flush/interrupt
  spread run with ZERO assertion failures (shadow arbiter == every real branch;
  slot_show_now == ext_show byte-for-byte before switching the display driver).
- R7 handled a Verilator UNOPTFLAT false loop (packed slot_desc pulled pick_wdata<-ad_i
  into the display cone): slot_desc moved to a continuous assign; slot_fire/slot_mode
  depend only on ad_i-independent req_*; QS=E/HALT/INTA rules untouched.
Phase-S HOOK in place (v30_biu.sv:696-698): selected_prefetch_grant =
slot_is_eval_ext ? prefetch_ext : prefetch_ok (declared, inert - Codex noted it is
not yet CONSUMED; S0 would wire it, but see NO-GO below).

PHASE S = NO-GO (opportunity audit, sw/class5_pauseaudit.py, Codex-designed gate).
Codex's Phase-S plan (docs/notes/class5_phase_s_plan.md) was a partial PAUSE-ONLY
veto of the eval_ext resume, gated by a ZERO-FALSE-PAUSE predicate from an
opportunity audit (S3 only if >=10% zero-FP coverage on held-out+fresh). The audit
(discovery/held-out/fresh corpora, uniform+random waits) is DECISIVE: at the q_cnt=2
boundary the model-GO population is overwhelmingly CORRECT (disc 525/540, held
400/419, fresh 337/340 chip-GO); only ~3-5% are chip-PAUSE (the fixable +errors:
15/19/3). Grid search over cad/dage/popc found NO zero-false-pause predicate at the
>=10% bar - the best is 5% AND has a false pause on discovery. The fixable chip-PAUSE
cases are INSEPARABLE from the correct chip-GO cases in predicate space, so any veto
injects ~as many -impulses as it fixes (the pf_lim=2 lesson, now proven at the
boundary). The audit GATE did its job - it prevented an over-correction. CONCLUSION:
class-5's ~15% boundary residual is genuinely IRREDUCIBLE on chip-observable +
model-internal state (it needs the chip's internal fetch-scheduler micro-state,
unobservable from bus+QS past the divergence). The class-5 random-wait residual is
at its OBSERVABLE FLOOR. Phase R (the structural unification) stands as the durable
win; Phase S is closed NO-GO. The eu_req=0 store+MOFFS fixes remain the
silicon-confirmed cycle-accuracy improvements.

## 2026-07-15 — CLASS-5 pivot: prefetch-resume idle-cadence localized (gap-error census)

With store + MOFFS eu_req=0 landed, the whole random-wait residual is class-5
"same bus decisions, WRONG CLOCK" (80% fitting / 90% held-out). Built the signed
inter-T1 gap-error census (sw/class5_gaperr.py, commit 2283046, Codex instrument):
gap_error[i] = (chip_T1[i]-chip_T1[i-1]) - (model_T1[i]-model_T1[i-1]) over the
aligned prefix of every vector, w0 (wmax=0) included as zero-error controls.

Result (18 seeds x 6 ws x wmaxes{0,1,3,7}, 76,000 aligned intervals):
- w0 control: 19,308 intervals, 0 nonzero -> instrument sound, w0 bit-exact.
- 99.6% clock-exact. The 0.4% errors (~213 impulses) are ENTIRELY idle-count:
  gap_error == Ti_delta exactly (not wait counts, not T-state length - purely the
  number of idle Ti cycles inserted between consecutive bus cycles).
- 202/213 impulses are CODE->CODE => a PREFETCH-RESUME cadence defect (the model
  inserts the wrong number of idle cycles before the next prefetch T1). Small
  EU-adjacent set (CODE->MEMW, MEMW->CODE, CODE->IOW).
- prev_tw LAW: after a heavily-waited fetch (prev_tw=6,7) the error is
  systematically POSITIVE (+2:42/+3:12 at tw7; +2:17 at tw6) - model resumes
  2-3 clocks too TIGHT (too early). After light waits (prev_tw=1) it is
  BIDIRECTIONAL (+3:32 and -3:16). net=+267 vs |mass|=557 => ~half the impulses
  cancel (why class5tax first-divergence over-attributed).

Mechanism (working): the model's prefetch resume (occ<=pf_lim + pf_drain
threshold) does not capture the chip's resume delay, which scales with the
predecessor fetch's STRETCHED-GRID geometry (wait count) + queue occupancy/
consumption. This is the long-suspected "prefetch-resume law under waits"
(instantaneous EU state proven insufficient; needs accumulated bus-grid-vs-
consumption phase history).

DENOMINATOR census (12 seeds, sw/class5_gaperr.py --denominators): prev_tw=0 is
PERFECTLY clean (0/24,570) - the resume defect ONLY follows a waited fetch
(necessary). But error rate is only 0.5-1.3% (not sufficient - extra state selects
which waited refills err). Sign structured by wait duration: prev_tw=7 all +ve
(+42/-0), prev_tw=1,2 bidirectional. => cannot blanket-correct; need the
discriminator.

FACTOR-W experiment (sw/class5_factorW.py): at a fixed CODE->CODE anchor, sweep
ONLY the predecessor's wait N via WVEC, measure chip vs model resume_idle. ABSORB-
TO-FLOOR DEADLINE LAW (Codex-formalized, exact for anchor A fz90011):
    gap(N)  = max(D, 4+N+F);  resume_idle(N) = max(D-(4+N), F);  D=12, F=4.
The chip has a scheduled earliest successor-T1 DEADLINE (D); predecessor Tw
consumes the slack before it; once the min post-T4 separation (floor F~3-4) is
hit, extra waits move the successor. anchor A chip_gap CONSTANT 12 for N=0..4
(smoking gun). The model's occupancy resume only ACCIDENTALLY coincides (A N=0..4)
and glitches (A N=5 late, N=6 early = threshold/commit-path aliasing). Anchors B/C
(fz90007/90002) do NOT fit a single (D,F) - deadline+floor are CONTEXT-DEPENDENT,
so "fixed bus-grid slot" is one hypothesis, not proven.

Implementation shape (Codex): a TARGETED resume-slot scheduler (separate
prefetch_eligible from prefetch_resume_slot), choosing among eval_ext / next-idle
/ later-refill slot - must handle BOTH early and late (one-direction delay
inadequate). Do NOT consume grid_phase yet (documented post-wait carry divergence,
inert for good reason).

FACTOR-P (anchor cycle-traces, sw/class5_anchortrace.py): the matched-pop image
construction is UNNECESSARY - the N-sweep already answers the bus-grid-vs-
consumption question. At anchors A (fz90011) and B (fz90007), across N, chip
successor_T1 = predecessor_T4 + 5 (const), INVARIANT to the post-T4 consumption
pop placement (pops at T4+2, or T4+0/+3, or T4+1/+4; successor unmoved). Measuring
relative to T4 factors out the grid shift N introduces, leaving pop placement as
the varying factor which the chip ignores => the resume is BUS-COMPLETION (T4)
anchored, not consumption-anchored. The model instead resumes at the eval_ext
(T4+1) once occ<=pf_lim (more waits -> more consumption during Tw -> lower occ ->
early resume; collapse-to-1). Codex confirmed: skip matched-pop; T4-relative
turnaround is real at these anchors.

CODEX RULING - the fix is NOT a blanket post-waited-fetch counter (Gate-A
falsified it: 17,052 waited CODE->CODE opportunities, chip prefetched IMMEDIATELY
in 16,952 = 99.4%, class-5 idle in only 100 = 0.6%; a 1-cycle block shattered
w1/w3). "Waited CODE fetch" is NOT the arming discriminator, and no blocking
counter fixes both signs (anchor A N=5 needs the model to launch EARLIER). Law
shape: successor_T1 = max(deadline, pred_T4 + Lmin), Lmin = resume_idle_floor + 1.
TWO pieces remain before any RTL:
  (1) Lmin as a collision-free function of FETCH GEOMETRY (Lmin=5 anchor A / =4
      B,C; leading candidate = even/odd physical fetch parity - A succ fetch ODD
      6fee7, B EVEN 69090). Measure a geometry matrix (even/odd pred x even/odd
      succ), sweep N to saturation, extract Lmin per cell.
  (2) The resume/DEADLINE ARMING EVENT that separates the 0.6% delayed cells from
      the 99.4% immediate-CODE controls (retrospective: deadline_candidate =
      successor_T1 when L>Lmin; compare vs last-pop-before-pred-T1, occupancy-
      cross-refill, pred_T1, prior-CODE-T1, queue-push-completion; the
      invariant-offset event is D's physical source). An opportunity census must
      prove the arming event isolates the rare cells (else another Gate-A fit).
Minimal RTL (once 1+2 known): resume_pending / resume_deadline / turnaround_ready
/ higher_priority_clear; commit CODE when all met; UNIFY eval_ext + do_commit into
one slot-selection + common commit (eval_ext = one candidate slot, not a separate
policy - the discontinuity plausibly causes the +/-2/3 glitches). w0-neutral via a
waited-only token (set only when completed cycle is CODE AND saw >=1 Tw; clear on
successor commit / any EU bus commit / flush / discard / reset; bit-identical when
inactive). Codex thread 019f663c consulted at each step.

PIECE 1 (Lmin) MEASURED (sw/class5_lmin.py, 18 anchors): Lmin (resume floor) =
5 if q_cnt(pred_T4)>=3 else 4, for linear even->even resumes (parity REFUTED - my
earlier odd/even claim was a misread of the data-phase bus column; all linear
resumes are even->even; the 2 Lmin=1 anchors are ODD-successor BRANCH REDIRECTS =
separate immediate-fetch machinery, exclude structurally not by parity). CAVEAT
(Codex): the split is CONFOUNDED - the 3 q_cnt=3 anchors are EXACTLY the
non-consuming ones (pred_state S_WAITX/S_FIRST), so q_cnt vs consumption vs
deadline-still-active are entangled; q_cnt=3 is not queue-full (cap 6). q_cnt(T4)
is a DEMAND signal (pre-existing bytes; the waited fetch's own push is deferred
past T4), not a turnaround signal. Do NOT encode q_cnt>=3?5:4 until Factor-Q.

PIECE 2 = FACTOR-Q (the single decisive experiment, Codex): a CONTROLLED,
BIDIRECTIONAL q_cnt(T4) boundary intervention (2<->3) via UPSTREAM WVEC
perturbation, holding fixed the predecessor/successor addresses, predecessor N,
fetch width, sequential/non-flush status, T1/T4 phase, EU req/hold, and local bus
stream. Drive a DELAYED anchor 3->2 (expect L=5->immediate/4) and an IMMEDIATE
control 2->3 (expect L=4->delayed/5), at two N (below-knee + saturated). If the
delay/immediate outcome FOLLOWS the controlled boundary AND one event->successor
offset predicts both -> queue-DEMAND-deadline law confirmed. If identical
reconstructed q_cnt(T4) still yields both outcomes -> history-latched (test
last-pop / threshold-crossing CLOCK, not snapshot fields). Record candidate
deadline events (last QS pop before pred T1/T4; queue-count 4->3/3->2/2->1
transitions; occupied<=4 / <=3 first-true; prior seq CODE T1/T4; pred T1;
pred push clock; first post-T4 q_avl increase; first post-T4 legal no-EU/no-flush
slot; successor T1) and find the invariant offset = D's physical source. The
all-opportunity census is the VALIDATION gate AFTER Factor-Q proposes the law
(census shows separation but cannot establish causality). Gate-A warning: coarse
occupancy at the DECISION edge was NOT collision-free (occ2/consuming gave both
11,488 immediate + 48 delayed); the new candidate uses q_cnt at pred T4 (earlier
edge) - must be tested across the whole population. RTL = LATCHED refill-request/
deadline (not a lower pf_lim - residual is bidirectional, anchor A N=5 needs an
EARLIER launch). Codex thread 019f663c consulted at each step.

FACTOR-Q RESULT (sw/class5_factorQ.py): the resume timing IS governed by
q_cnt(pred_T4) - the queue-demand-deadline hypothesis is causally supported. At a
fixed anchor (N + pred/succ addrs held; predecessor re-located by address each
run), driving q_cnt(pred_T4) via upstream WVEC perturbation moves L monotonically:
fz90013 q0->L2, q1->L4, q3->L5 (fz90011 corroborates q3->L5 stable). DE-CONFOUNDED
within the data: two far-upstream perturbations (acc#100 w0 vs w1) FLIP the pred-T4
grid parity yet both keep q_cnt=1 and both give L=4 -> at fixed q_cnt, grid parity
does NOT change L. So L=f(queue fill at completion), not parity or consumption.
(Near-anchor perturbations confound the deadline: q4->L7-10 decreasing - excluded.)
REMAINING before RTL: (a) map the full L(q_cnt) function (fill q2, q4 - so far
q0->2, q1->4, q3->5, monotonic but not linear); (b) the D deadline-source
retrospective for the absorb regime (which pre-T1 event D is anchored to); (c)
then the latched-deadline RTL + full validation gate.

BIDIRECTIONAL MECHANISM (instrumented traces, sw/class5_anchortrace.py): the
resume is a FIXED T4-relative SLOT, not an occupancy threshold - proven in BOTH
directions. +case fz90007 N=3: model prefetches at eval_ext occ=3<=pf_lim=3, chip
IDLES (chip threshold lower). -case fz90011 N=5: chip prefetches at occ=4, model
waits for occ<=3 then loses a clock to the do_commit path -> model LATE (chip
threshold higher). occ at eval_ext already includes the deferred push (cnt_next),
which is the misleading value. So occ<=pf_lim is wrong in both signs; the
eval_ext-vs-do_commit split adds +/-1 jitter.

RTL DESIGN (Codex-specified, session 019f663c): law =
  successor_T1 = max(prefetch_due_slot, pred_T4 + turnaround_floor)
The chip SEPARATES demand-detection (a queue-demand event LATCHES a pending refill
+ deadline slot) from the commit CLOCK; the model conflates both into
occupied<=pf_lim. Do NOT implement a q_cnt-only T4 countdown: the q0->{L2,L4}
collision proves a second state (DEMAND-AGE: how long ago the queue reached demand
/ emptied) remains. Latch the PRE-PUSH q_cnt at pred T4 (registered value before
the deferred push - NOT cnt_next/occupied/q_avl). Minimal RTL = a small
waited-resume scheduler: state {pf_demand_pending, pf_demand_age/deadline,
waited_resume, resume_pre_qcnt, turnaround_left}; demand tracking runs continuously
(inert at w0); at the waited sequential CODE T4 set waited_resume + latch
pre-push q_cnt + turnaround floor; resume_commit = waited_resume &&
pf_demand_pending && demand_deadline_reached && turnaround_reached && !eu_owner &&
!eu_hold && !q_flush && !fetch_discard && !split_continuation. BOTH the eval_ext
and plain-idle commit sites consume this ONE unified policy result (must SUPPRESS
prefetch_ext when early AND PERMIT commit when occ<=pf_lim is false when late - a
gate that only ANDs into prefetch_ok cannot fix fz90011). w0-neutral via explicit
mux: if(!waited_resume) legacy bit-identical else scheduler; waited_resume sets
only when the completed cycle is CODE + sequential + saw >=1 Tw; clears on
successor commit / any EU bus commit / flush / redirect / discard / reset.
STREAM-CADENCE (sw/class5_streamcadence.py, 1929 CODE->CODE resumes uniform w1-3):
the capacity model - chip fetches BACK-TO-BACK while occ<=4 (q_cnt<=2), PAUSES at
occ>=5 (q_cnt>=3) = exactly the model pf_lim=4, so the model is RIGHT for the bulk.
The class-5 disagreement CONCENTRATES at q_cnt=2 (14/55=25%), boundary discriminator
= eu_consuming/pop_cnt (consuming -> pause). BUT the tractable fixes are RULED OUT:
(1) pf_lim 3->2 in the drain+consuming window: w0/w1/w3 goldens all held, but the
random-wait gap-error census OVER-CORRECTED - 485 impulses (up from ~226), flipped
to negative (CODE->CODE +161/-291), prev_tw=1 err 0.87%->3.48%. Bidirectional
confirmed AGAIN (not a threshold). (2) DECISION-EDGE discriminator: within the
pf_lim=3 boundary the chip go-vs-pause is 23/22 = ~50/50 on EVERY observable
(decision-edge occ/q_avl/q_cnt/pop_now/push_now/recent-pop). => a chip-INTERNAL
fetch-scheduler state (or exact microtiming the model cannot reconstruct past the
divergence point) governs the final decision. THE WALL: class-5's fine structure
needs the chip's demand/deadline state reconstructed PURELY from chip-observable
history (bus + QS F/S pops + fetch widths), INDEPENDENT of the diverged model
(Codex's suggested reconstruction) - a substantial new tool, the principled next
effort. Model-internal discrimination is exhausted (the model==chip only up to the
divergence, which is exactly where the decision differs).
  CORRECTION (the "wall" was premature): the model==chip UP TO the divergence, and
the resume decision IS the divergence, so the state AT/BEFORE the decision is
chip-accurate - the instantaneous 50/50 means a HISTORY variable governs (the
latched demand slot, exactly as Codex said). Adding history variables to
streamcadence resolves the q_cnt=2 boundary FAR better: fetch-cadence MOMENTUM.
cad = clocks between the two prior fetches: cad<=9 (tight/back-to-back burst) ->
GO ~79%; cad>=16 (slow/paused) -> PAUSE ~85%. demand-age agrees: recent demand
(dage 5-13) -> go; old (dage 29+) -> pause. So the chip has PREFETCH MOMENTUM -
it continues a fill burst once started and stays paused once saturated; the q_cnt=2
boundary decision follows the recent cadence, NOT instantaneous occupancy. The
model (occ<=pf_lim, memoryless) lacks this hysteresis. FIX DIRECTION: add
cadence-momentum hysteresis to the boundary prefetch decision (continue if recently
bursting, pause if recently paused), w0-neutral. Still ~80% clean, not yet
bit-exact - needs a cleaner momentum rule (pin the exact cad/dage thresholds +
any second variable) before a bit-exact RTL. This is the tractable next effort,
NOT a wall.

FLOOR-ONLY RTL ATTEMPT (reverted) - a decisive negative result: implemented the
suppression-half scheduler (arm wr_active at the waited-completion !evald T4, latch
wr_L from the surface floor arithmetic q_cnt>=2?5:q_cnt==1?4:age<=3?4:2, and
wr_block = wr_active && wr_ctr+1<wr_L gating prefetch_ok until the slot). w0 held
169000/169000 (w0-neutral confirmed - arms only in !evald), BUT w1/w3 goldens
SHATTERED (347/1200, 350/1200; failures = CODE got PASV = suppressed prefetches
that should happen). ROOT CAUSE: in uniform-wait streams EVERY fetch is waited so
the scheduler is always active and imposes the floor idle even while the queue is
still FILLING toward capacity - but there the chip prefetches BACK-TO-BACK. The
floor arithmetic was measured with an ISOLATED saturated-N predecessor (queue in a
paused/saturated state); it does NOT capture the FILLING-vs-SATURATED distinction
that governs stream cadence. This empirically CONFIRMS Codex's warning: a
q_cnt-only floor countdown is insufficient; the resume timing needs the full
demand/CAPACITY model (prefetch back-to-back while filling toward cap 6; pause per
the demand deadline only when saturated/well-fed). The floor L is the PAUSED-state
slot, not the fill-cadence. REMAINING: measure the resume cadence in STREAM context
(when the chip prefetches back-to-back vs pauses = the demand_slot/capacity rule),
NOT with isolated anchors; then the RTL must gate the slot-idle on the
saturated/well-fed condition (not merely "waited fetch").

NEXT DECISIVE MEASUREMENT (Codex): the fixed-q0 STARVATION-AGE experiment - hold
q_cnt(T4)=0/q_avl=0/geometry fixed, vary only empty_age = pred_T4 - clock(queue
1->0), targets empty_age 0/1,2,3+. If L follows empty_age (newly empty -> L4
scheduled later; long empty -> overdue -> L2 immediate) the deadline event is the
queue-empty transition -> RTL needs a demand-age/slot latch. Then sweep the same
demand-age rule through q1-q4 (may eliminate the L table entirely). More decisive
than filling q2/q4 (a lookup table is meaningless while q0 collides).

## 2026-07-15 — eu_req=0 MOFFS stage: PARITY-GATED S_MLO lead-veto (SILICON-CONFIRMED)

Second stage of the eu_req=0 look-ahead veto (commit 981f3af, bitstream flashed;
setup slack +5.686 ns, hold +0.248 ns). Unlike the disp16 store (a clean blanket
reserve), the MOFFS load is PARITY/WIDTH-DEPENDENT - a genuine bus-grid finding
caught by running the opportunity census BEFORE the RTL (the Gate-A discipline).

Opportunity census (moffs_optcensus.py, chip ground truth, 20 aligned
eval_ext+S_MLO+q_pop cells):
  A1 word load, EVEN addr (aligned, 1 bus cycle): chip PREFETCHES 12/12
  A1 word load, ODD addr  (split,  2 bus cycles): chip RESERVES   4/4
  A0 byte load:                                    chip RESERVES   4/4
The chip reserves at S_MLO for a MOFFS load EXCEPT an ALIGNED WORD load (an
aligned single-cycle read leaves grid room to prefetch; a byte or split read
does not). A blanket S_MLO veto would have wrongly suppressed 12 legal chip
prefetches. Discriminator computable at S_MLO: addr LSB = q_byte[0] (low byte
popping), width = opc[0]; aligned word = opc[0] && !q_byte[0]; veto =
!(aligned word). eu_rsv_lead += (S_MLO && op_moff && q_pop && (!opc[0] ||
q_byte[0])). op_moffw stores (A2/A3) excluded (negative control). Same eval_ext
pf_rsv_lead mechanism -> w0-NEUTRAL.

Validation (chip ground truth):
  w0 169000/169000, w1 1200/1200, w3 1200/1200 (bit+cycle exact).
  eu_req=0 census: MOFFS cases eliminated, 6->4 class-1 (only POP r16 remains).
  fitting census N=300: class-1 42->36 mass; NO over-suppression, NO new class.
  held-out census N=300: IDENTICAL to pre-MOFFS (class-1=0, no under-prefetch) -
    the parity gate did NOT break the aligned-word prefetches.
  SILICON (fabric use_core=1 vs chip use_core=0): fz90063 MOFFS over cases now
    chip==fabric==TB (doomed prefetch gone). fabric==TB on all 7 vectors; the 2
    held-out diffs are byte-identical to the store-flash run (pre-existing
    class-6/7; ZERO new fabric divergence from MOFFS).

eu_req=0 residual now: 4 POP r16 cases (DEFERRED - S_FIRST needs live q_byte
decode). Whole random-wait residual now DOMINATED by class-5 WRONG-CLOCK (80%
fitting / 90% held-out) - the campaign PIVOTS there next (structural bus-slot
scheduling, NOT another eval_ext veto - Codex).

## 2026-07-15 — eu_req=0 STORE stage: wait-dependent BIU look-ahead veto (SILICON-CONFIRMED)

Landed + flashed + silicon-confirmed the first stage of the eu_req=0 onset fix
(commit f145345, bitstream checksum 0x03D40ED0 live in fabric). This corrects a
class of random-wait over-prefetch where the model committed a DOOMED CODE
prefetch one EU-state before its own eu_req rose, while the chip had already
reserved the bus for an imminent store.

KEY DISCOVERY (overturns a prior w0 assumption): the reservation onset is NOT a
fixed EU-state that can be shifted earlier. The first implementation asserted
eu_req at S_DHI unconditionally and REGRESSED the w0 golden 168854/169000, every
failing cell a disp16 store showing exp CODE/T1 at the post-EA cycle. The chip
DOES prefetch at that cycle at w0 (golden = chip ground truth). The correct model
(Codex framing): the BIU has a WAITED-completion (eval_ext) look-ahead veto that
recognizes an imminent store one EU-state before ordinary eu_req; the SAME EU
state does not suppress a legal w0 prefetch. "May use this slot now" (w0
prefetch_ok) vs "must preserve the next grid slot for an imminent access"
(eval_ext). eval_ext is a model proxy for that hardware grid opportunity,
validated for the measured cells (not proven the chip's mechanism).

Implementation: EU exports eu_rsv_lead = (S_DHI && (op_movs8|op_movs16) &&
q_pop); BIU pf_rsv_lead = eval_ext && eu_rsv_lead && q_aged==0 && !q_flush &&
!eu_hold, ANDed as `!pf_rsv_lead` into prefetch_ext. w0-NEUTRAL by construction
(eval_ext never fires at w0). Distinct from pf_late_rsv/owns_slot (those require
eu_req==1; here the reservation LEADS with eu_req==0).

Validation (all chip ground truth):
- Golden chip-vs-TB: w0 **169000/169000**, w1 **1200/1200**, w3 **1200/1200**
  (bit+cycle exact; the -146 w0 regression was the REJECTED unconditional edit).
- eu_req=0 census (board): store case fz90015 ELIMINATED, 7->6 class-1.
- Fitting census N=300: no new divergence, no over-suppression, no new class.
- Held-out census N=300 (91000-91009): class-1=0, no over-suppression.
- **SILICON (fabric use_core=1 vs socketed chip use_core=0)**: fz90015 bus 37
  now MEMW@02608 on chip==fabric==TB (doomed CODE gone; exact idle count/index).
  fabric==TB on all 5 acceptance vectors (faithful synthesis). Setup slack
  +4.795 ns, hold +0.246 ns. The 2 held-out chip-vs-fabric diffs (fz91000 b130
  CODE/CODE addr±1; fz91003 b136 IOW) are PRE-EXISTING class-6/7 residuals, not
  this fix (fabric==TB on both).

Residual now dominated by class-5 "same bus decisions, WRONG CLOCK" (78% fitting,
90% held-out). NEXT: MOFFS stage (S_MLO lead-veto, same mechanism, needs its own
opportunity census); then PIVOT to class-5 as structural bus-slot scheduling (NOT
another eval_ext veto). Codex thread 019f663c consulted (staged GO, this framing).

## 2026-07-15 — MERGE biu-rebuild -> master (BIU rebuild banked to mainline)

The BIU bus-model rebuild campaign merged to master (fast-forward; master was at
the Phase-1 doc commit, biu-rebuild 26 ahead). Rollback tag `biu-rebuild-baseline`
(c0c28f1) retained. Comprehensive pre-merge validation, ALL clean vs baselines:

- **Full golden (chip-vs-TB / check_core)**: w0 **169000/169000**, w1 **1200/1200**,
  w3 **1200/1200** (all 6 forms). NOTE: w1/w3 now report the FULL 1200 (not the
  historically-cited 800/600) because a pre-existing over-strict Stage-1
  grid_phase SVA was `$stop`-aborting the 8B/89/B8 load/MOV-imm forms' sim under
  waits and check_core silently skipped them (masked by prior tail/grep-TOTAL
  reporting). grid_phase is INERT (unconsumed - EU uses bus_phase), so ZERO
  behavioral impact; the strict SVA is now gated behind `GRID_PHASE_STRICT`
  (off) with the abort removed, so those forms VALIDATE cycle-exact. Confirmed
  pre-existing at 01c31e7.
- **waits=0 arbitrary-sequence fuzz** fz20000-20299 chip-vs-TB: **300/300 clean**
  (store/push/reader/callret surface unregressed by the whole rebuild).
- **Interrupt inject gate** fz10000-10499 --inject-int chip-vs-TB: **497/500**.
  The 3 residuals (fz10209/10300/10304) are the DOCUMENTED doomed-prefetch/
  accept-edge interrupt-vectoring class (chip does a doomed CODE prefetch before
  INTA the RTL doesn't model - same class as the deferred fz10175/10460). They
  DIVERGE IDENTICALLY at 01c31e7 (@251/@264/@202), and the session's four fronts
  are w0-neutral (all eval_ext-gated; inject runs at w0 where eval_ext never
  fires) -> the inject gate is bit-identical HEAD-vs-baseline. NOT a regression;
  the 497-vs-documented-498 is gen_seq/corpus evolution surfacing the same class
  on different seeds. Sub-1%, out of scope (deferred interrupt-timing floor).
- **Silicon A/B (this session, bitstream 0f383e0 live in fabric)**: w0 crown
  jewel chip/core/golden MATCH 800 rows; w1/w3 fabric-vs-chip == chip-vs-TB
  EXACTLY per-seed 15/15 both, float-floor 15/15 clean; BUSLOCK exact;
  inject-int fz10000-10049 50/50. The arb/Jcc-flush/far-flush fronts are real
  in fabric.
- **Adjudication ledger**: 0 w0 deltas; every landed front w0-neutral by
  construction (all eval_ext-gated -> inert at w0).

FABRIC == MASTER: the SVA-gating + eudbg-dump + tooling changes are entirely
TB-only / `ifndef SYNTHESIS`; the SYNTHESIZABLE RTL at master HEAD is
bit-identical to the flashed bitstream 0f383e0 (no reflash needed - current best
RTL is already in silicon). Session drift result (silicon-confirmed): w1
459.3->307.3 (-33%, CLEAN 4->18), w3 583.6->475.6 (-18%, CLEAN 15->21) via three
landed fronts (late-reservation arb / near-flush +1 redirect / far-flush
eval_ext E-display); the RESUME third characterized as the irreducible local
floor. Next campaign: the exact-grid-state resume scheduler
(resume_scheduler_design.md; exact-state predictor go/no-go = qualified
greenlight, w0 100% control + w1/w3 big-gap 83-98% on the clean prefix).

## 2026-07-14 — reflash: WAITS>=1 grind round 2 (far-CALL + RMW-narrow)

- SCOPE: two waits>=1 fixes since the prior reflash - far CALL (9A/FF.3) PC
  push marched on eu_wdone (trap-chain law, like PUSHA); RMW deferred-eval
  defer narrowed to op_alui (imm-less RMW forms commit early via rule A -
  the round-1 all-S_WREQ defer had regressed the 0F NOT1 case).
- BUILD: 0 errors. Timing MET: setup slack +5.813 ns, hold +0.267 ns. sof
  fresh (mtime > RTL).
- REFLASH: safe_flash OK, echo-healthy BEFORE and AFTER.
- HARDWARE A/B (real silicon, chip vs fabric):
  * waits=0 fz40000-40199 199/200 (the 1 = fz40173, documented 1-row PS
    transient @ row 754 ps 2!=6, confirmed cosmetic chip-vs-TB - NOT a
    regression). waits=0 surface unregressed.
  * waits=1 fz84000-84049: first-div median 408.5 -> 443.0 (fixes live,
    drift pushed deeper). Still 0/50 fully clean.
  * waits=3 fz84000-84049: clean 4/50 -> 6/50, first-div median 527 -> 558.5.
- Golden 169000/169000 + w1/w3 1200/1200 held (TB); waits=0 chip-vs-TB fuzz
  80/80 clean. 5 contexts now cycle-exact (far-flush, PUSHA, RMW write,
  far-CALL, RMW-narrow); waits>=1 gate NOT met - the remaining tail is the
  shared-path wait-aware reservation FLOOR (biu_model.md / closure_checkpoint).

## 2026-07-14 — reflash: WAITS>=1 RMW-write deferred-eval qualification

- SCOPE: one waits>=1 core-RTL fix (commit d339204) - the RMW mem write
  (S_WREQ) takes the deferred (eval_ext) commit only if readiness was
  registered ENTERING T4 (new eu_defer_wr -> stricter ext_ok_wr in v30_biu).
  Cycle-exact vs chip at w0-w5 (sweep_rmw.py) for ADD/NEG/INC word forms;
  byte forms exact at w1/w3 (gate levels). Context 2 (trailing POP read)
  investigated + found NOT a distinct bug (accumulated drift); remaining is
  a diverse phase tail - characterized + deferred (biu_model.md).
- BUILD: 0 errors. Timing MET: setup slack +4.958 ns, hold +0.265 ns
  (Full Compilation successful). sof fresh (mtime > RTL).
- REFLASH: safe_flash OK (0 errors, VERIFY ok cfg 0x1ff0008). echo-healthy
  BEFORE and AFTER.
- HARDWARE A/B (real silicon, chip vs fabric):
  * waits=0 fz30000-30199 200/200 clean (unregressed - critical gate).
  * waits=1 fz84000-84049: first-divergence median row 385 -> 408.5
    (RMW fix live; drift reduced a touch deeper). Still 0/50 fully clean.
  * waits=3 fz84000-84049: 4/50 clean, first-divergence median 527.
- Golden 169000/169000 + w1/w3 1200/1200 held (TB); waits=0 chip-vs-TB fuzz
  120/120 clean. 3 contexts now generalized (far-flush, PUSHA, RMW write);
  waits>=1 arbitrary-sequence gate still NOT met (diverse phase tail).

## 2026-07-14 — reflash: WAITS>=1 cadence generalization (far-flush + PUSHA)

- SCOPE: two waits>=1 core-RTL cadence fixes (commits 84d59ee far-flush
  ff_t4 gated on evald; de18d78 PUSHA marches inter-write chain on eu_wdone).
- BUILD: 0 errors. Timing MET: setup slack +5.000 ns, hold +0.264 ns
  (Full Compilation successful, 305 warnings). Util 9,776 ALMs (23%),
  5153 regs, 13 DSP. sof fresh (verified mtime > RTL edits).
- REFLASH: safe_flash OK (quartus_pgm 0 errors, VERIFY ok cfg 0x1ff0008,
  use_core=False). echo-healthy BEFORE and AFTER (ECHO TEST PASSED both).
- HARDWARE A/B (real silicon, chip vs fabric):
  * waits=0 fz20000-20199 200/200 clean (unregressed - critical gate).
  * waits=1 fz84000-84049: first-divergence row min 224 / median 385
    (pre-fix the first drift was the loader far-flush at ~row 30 in EVERY
    seed; the fix pushed it to row 385 median - loader + early stream now
    bit-clean in silicon). Not fully closed (RMW-write / trailing-read
    contexts remain deeper - characterized + deferred, biu_model.md).
  * waits=3 fz84000-84049: 4/50 fully clean, first-divergence median 527.
- Golden 169000/169000 + w1/w3 1200/1200 held (TB); waits=0 chip-vs-TB
  fuzz 120/120 clean. PARTIAL closure of the waits>=1 arbitrary-sequence
  surface - drift rate cut, gate not yet met.

## 2026-07-14 — reflash: taken-branch flush + 8C-store recognition fits

- BUILD: 0 errors. Timing MET: setup slack +5.562 ns, hold +0.267 ns.
- safe_flash: Configuration succeeded, VERIFY ok; echo-healthy before/after;
  no wedge. Fabric now carries commit 5568052 (post_flush pin tap + 8C
  sreg-store shadow, on top of the shadow single-boundary fix).
- HARDWARE A/B (chip vs fabric, fz10000-10499 --inject-int): 494 -> 497/500
  (fz10117/10283 branch-flush + fz10317 8C-store now clean in silicon;
  residual 3 = fz10055 float floor + fz10175 NMI + fz10460 REP-LODSB).
- chip-vs-TB (ground truth): 498/500. Regression corpus replay chip-vs-TB
  all d=0 (incl now-closed fz10066/10117/10283/10317/10486, loop/farjmp/
  swint). Added fz10175/fz10460 residual reps to the corpus.

## 2026-07-14 — reflash: recognition-shadow single-boundary fix

- BUILD: 0 errors, 305 warnings. Timing MET: setup slack +4.242 ns, hold
  +0.255 ns.
- safe_flash: quartus_pgm Configuration succeeded (0 errors), VERIFY ok
  (pwr_good/cpu_running/MAGIC). Echo-healthy before/after; no wedge.
- Fabric now carries commit 1a7f601 (shadow cleared at S_FIRST opcode pop).
- HARDWARE A/B (chip vs fabric, fz10000-10499 --inject-int): 488 -> 494/500.
  The 6 shadow-caused seeds now clean in silicon (INT fz10066/10251/10459,
  NMI fz10248/10431/10486); residual 6 = fz10055 (fabric synth float floor)
  + the 5 branch-flush/8C-store recognition-point residuals.
- chip-vs-TB (ground truth): 495/500. Regression corpus replay chip-vs-TB
  all d=0 (inject fz10041/10055/10059/10066/10486, loop fz7203/7207, farjmp
  fz8304, swint fz8007/8032).

## 2026-07-14 — reflash: NMI IVT-read idle-window early commit (Mission-D)

- BUILD: quartus_sh --flow compile, 0 errors, 305 warnings. Timing MET:
  worst-case setup slack +3.829 ns, hold +0.265 ns (recovery +29.171,
  removal +0.944, min-pulse +1.196). All positive.
- safe_flash: PREP ok, quartus_pgm Configuration succeeded (0 errors),
  VERIFY ok (pwr_good/cpu_running/MAGIC). Board echo-healthy BEFORE and
  AFTER; final echo PASSED. No wedge.
- Fabric now carries commit 07f65f6 (eu_soon_ivt + q_cnt<=2 defer_idle arm).
- HARDWARE A/B (chip vs fabric, fz10000-10499 --inject-int): 488/500 (was
  477/500). The 11 NMI IVT-read seeds now clean in silicon; residual 12 =
  fz10055 (fabric synth float floor, chip-vs-TB clean) + the 11 chip-vs-TB
  residuals (7 INT INTA-commit, 4 NMI doomed-prefetch).
- chip-vs-TB (ground truth, socketed chip forced): 489/500. Regression
  corpus replay (chip-vs-TB): inject fz10041/10055/10059, loop fz7203/7207,
  farjmp fz8304, swint fz8007/8032 all d=0 (the flush seeds closed for free
  by 006b257/a9f1468 as anticipated).

## 2026-07-11 — first deployment: harness verified, CPU not driving pins

Deployed the phase-3 harness (4 MHz CPU clock, zero wait states, bring-up
boot image) over JTAG and dumped the capture buffer repeatedly.

**Verified working:**
- JTAG programming, In-System Memory readout of all three instances
  (ME0/ME1/CAPT). Boot image read back byte-perfect from ME0.
- Capture pipeline: reset-tail records (RESET=1, READY=1, 33 records) then
  per-cycle records exactly as designed.
- Power-up sequencing added during debug: ENABLE_N asserted at config, ~131 ms
  rail-settle wait, then 32 CPU-clock RESET pulse (nec_bus.sv).

**Problem: every CPU-driven pin (BS, QS, RD_N, UBE_N, BUSLOCK_N, AD) reads
floating-low through the level shifters — before, during, and after reset.**
The V30 never drove anything. The harness FSM chases the floating status
(000 reads as INTA ≠ PASV) in an endless T1→T2→T3→T4 loop; that loop in the
trace is a harness artifact, not CPU activity.

Evidence and eliminations:
- Reset sequencing correct at the FPGA (captured in-trace).
- Float pattern was high-ish (PASV, AD=207FF) ~8 µs after config, all-low by
  131 ms — consistent with residual charge draining from an unpowered rail.
- ENABLE_N polarity test: inverted to 1 → identical float signature. Both
  polarities leave the CPU dead, suggesting the PMOS power switch is not the
  (only) polarity issue, or power isn't the whole story.
- Schematic: ~CHIP_ENABLE gates a P-MOSFET high-side switch on the V30's 5V;
  AD0-15 behind F_AD_DIR transceivers; A16-19 fixed CPU→FPGA.

**Physical measurements (Martin, 2026-07-11):** VDD = 5 V, CLK = 4 MHz,
READY high, RESET low (post-release), CHIP_ENABLE gating works. Chip is
powered, clocked, and reset correctly — yet drives nothing.

## ROOT CAUSE: RQ/AK0 and RQ/AK1 grounded on the PCB

The PCB netlist ties V30 socket pads 30 and 31 to GND. Correct for
small-mode semantics (HLDRQ active-high input, HLDAK output idles low), but
the harness straps LARGE mode, where pins 30/31 are RQ/AK1 and RQ/AK0 —
**active-low bus-hold request inputs. Grounded = permanent hold request.**
Per datasheet p98-99, the CPU acknowledges and floats the address bus,
AD bus, and all control lines — indefinitely. Matches every observation,
including the lone queue-status blip at startup.

**Fix (chip is socketed):** bend pins 30 and 31 out of the socket and pull
each up to 5 V through 10 k. (The 8086 has internal pull-ups on RQ/GT and
the V30 likely inherits them, but the datasheet doesn't confirm it — use
external pull-ups.)

**Alternative validation path (no rework):** drive S/LG high (FPGA pin
NEC_LG_N) to select small mode, where the grounded pins are electrically
correct — but this loses QS0/QS1 queue status, so it is only a stepping
stone. Harness FSM would need a min-mode decode variant (ASTB as address
strobe, IO/M + RD/WR for cycle type).

## 2026-07-11 (later) — SMALL MODE: CPU EXECUTING, full chain verified

Implemented small-scale mode in nec_bus (cfg_small_mode: transparent ASTB
address latch, RD/WR strobe-driven datapath, IO/M low=I/O). NEC_LG_N=1.
Dual-mode verilator TB passes. Deployed to hardware:

**The V30 executes the boot program.** Captured trace (capture8) shows:
- RESET release → pins go from floating to driven-idle ~8 cycles later;
  **first bus cycle ~9 CPU clocks after reset release** (small mode,
  preliminary — sampling offsets not yet calibrated out).
- First fetch at FFFF0h, FPGA BRAM returns 00EA (far jump) — then prefetch
  overshoot: fetches FFFF2/FFFF4/FFFF6 (8 bytes for a 5-byte instruction)
  while the EU decodes.
- Jump lands: next fetch 00100h. Program bytes stream back exactly as
  loaded (34B8, BB12, 2000, 0789, 00A0, A120...).
- MOV [BW],AW executes: MEMW at 02000h, data 1234h, correct byte enables.
- Loop repeats ~35x across the 4096-cycle trace. 4-cycle bus cycles, zero
  wait states throughout.

Known capture artifacts to fix:
- ASTB pulses fall between the two per-cycle sample points → the record's
  QS[0] bit never shows ASTB high. Make it a sticky-OR over the cycle.
  (The transparent address latch works; only the record bit is affected.)
- Pre-drive float reads as "IOR" in the decoder until the CPU starts
  driving (~8 cycles post-release). Cosmetic.
- JTAG bulk reads still occasionally all-zero; dump_capture.tcl now
  retries aggressively (all-zero chunk = provably bogus since READY bit
  is always set in valid records). capture8 = 4096/4096 valid.

**Milestone: full discovery-loop chain works** — assemble program → load
BRAM → power/reset sequence → real V30 executes → per-cycle capture →
JTAG dump → decode. Next: sticky strobe bits, then the RQ/AK rework to
unlock large mode + queue status.

## 2026-07-11 (later) — HPS bridge: ARM lockup incident + hardening

First deployment of the lightweight-bridge harness control locked up the
DE10's ARM hard (network dead, SSH gone): the first /dev/mem access to
0xFF200000 stalled — an unanswered lw-bridge AXI transaction seizes the L3
interconnect and takes the whole SoC down. Likely cause: the AXI slave was
reset by the MiSTer framework reset (hps_io status/buttons), which is
undefined once MiSTer Main is killed — the slave never asserted ready.

Remote recovery attempts, all failed (documenting for next time):
- Reconfiguring the FPGA with an always-responding slave (hoping the fresh
  fabric would complete the pending transaction): no recovery.
- System Console DAP master: Quartus Lite exposes no HPS master service.
- quartus_hps -o I: DAP IDCODE reads, but "Fail to power up the System and
  Debug power" — the seizure blocks the debug power handshake too.
→ **A physical power cycle is the only way back.**

Hardening now in place (sim-verified, awaiting hardware retest):
- hps_axi_slave reset by a local POR pulse only — always responds,
  regardless of framework/MiSTer state.
- host_attached latch: standalone boots use the framework reset as before;
  after the first CTRL write the host owns the harness lifecycle.
- capture_buf reset is POR-only; trace survives host_reset for readout.
- sw/v30ctl.py `prep` puts the bridges into reset BEFORE FPGA
  reconfiguration (run it every time before quartus_pgm).

Safe flow after every boot: killall MiSTer → v30ctl.py prep → make run →
v30ctl.py status.

## 2026-07-11 (evening) — HPS bridge verified: full discovery loop live

After the power cycle, the hardened bridge worked first try (prep →
flash → status, no lockup). Verified end-to-end on hardware:

- `v30ctl.py run boot.bin`: stop → load 64 KB over the bridge → fast
  restart → capture full → dump, in seconds (vs minutes over JTAG).
  Results identical to the JTAG-era captures (8-clk reset latency,
  64-clk boot loop).
- **Full toolchain loop**: a new program assembled with v30asm
  (MOV CW,0AAAAh; MOV BW,3000h; loop: MOV [BW],CW; INC CW; BR loop),
  loaded and run via the bridge — capture shows 161 iterations with the
  write data incrementing aaaa, aaab, aaac... (live execution proof).
  Loop period: **25 CPU clocks** for MOV [BW],CW + INC CW + BR short.

The write-test → run-on-silicon → measure loop is fully operational.
Remaining before suite-grade data: load/store routines (designed,
docs/notes/loadstore_design.md), RQ/AK rework for large mode + queue
status.

## 2026-07-11 (night) — LARGE MODE LIVE: real queue status

RQ/AK0-1 rework done (pins lifted + pulled up). S/LG̅ strap rewired to
follow CFG.small_mode so mode is host-switchable (change only in
host_reset). First max-mode run: BS status + T-states decode cleanly,
QS0/QS1 report real queue ops, queue-depth reconstruction works (peak 5),
442 instruction boundaries visible, per-instruction F-to-F times
{3,5,7,11,12,12,14} sum to the 64-clock loop measured independently on
the bus side. See docs/facts/measurements.md.

One transient: the first large-mode `v30ctl run` invocation hung in
load_mem (>45 s); an identical retry completed in 0.7 s. Unexplained —
watch for recurrence.

Everything is now in place for the decode/prefetch research program and
the load/store implementation (stage 1+2 together, since queue status
is available).

**Tooling notes:**
- `read_content_from_memory` returns content highest-address-first; bulk
  reads intermittently return all-zeros on Quartus 17.1 even with re-read
  verification (single-word reads are reliable). sw/dump_capture.tcl uses
  64-word chunks + retry; treat all-zero regions in dumps with suspicion —
  a genuine record always has the READY bit (51) set.
- A valid capture record can never be 0x0000000000000000.

## 2026-07-13 — Campaign 4 kickoff: in-FPGA A/B integration + safe-flash

### A/B integration architecture (landed, commit 61185d0)
The v30_core is instantiated inside system_large behind a CFG selector so
nec_bus's pin side drives either the socketed chip or the internal core:

- **CFG.use_core (bit 25)** in hps_axi_slave (default 0 = chip). Change
  only under host_reset, like the other CFG fields.
- **nec_bus AD refactor**: the inout `NEC_AD` port became a unidirectional
  trio `ad_drive` / `ad_drive_en` / `ad_sample`. This removes the
  inout<->inout bridge that a naive A/B mux would need (Verilator flagged
  UNOPTFLAT/circular; Quartus would cut the false loop arbitrarily). The
  chip datapath is bit-identical: `ad_sample` = NEC_AD in chip mode, the
  drive is the same registered `rdata_q` under the same `drive_en`.
  tb_harness passes unchanged; largemode_synth.hex regenerates byte-
  identical; the 155440/155500 core golden regression is untouched.
- **system_large mux**: one-directional status pins (BS/QS/RD_N/UBE_N/
  BUSLOCK_N) mux chip<->core with plain 2:1s; the harness read data is
  injected on the core's shared AD net under `ad_drive_en`; nec_bus's
  outputs fan out to both the physical pins and the core; the socketed
  chip is powered off (ENABLE_N) while the core is selected. The core is
  clocked by NEC_CLK (same 4 MHz cadence the chip sees) and held in reset
  unless selected.

### Sim A/B (Mission A) — tb_ab.sv + sw/check_ab_sim.py
tb_ab drives the real integration (system_large) from the AXI master BFM
only and exercises BOTH selector positions. check_ab_sim runs the core
position, drains the harness capture, and diffs it against the real-chip
boot golden (sw/testdata/largemode_boot_real.hex) with check_boot's column
policy.

- **Chip position**: passes (large-mode BFM vector fetch + write/readback).
- **Core position**: the core boots from the in-memory image behind the
  real capture path, but DESYNCS. This is the current gate.

### FINDING — core<->harness commit-phase desync (gates hardware)
Aligned at the first vector fetch, the harness-core trace is identical to
the `+bootimg` replay (which matches the chip, mission G) for cycles 0-5,
including the fetched data words (00ea/0001/9000). Then it diverges: the
core's EU pops the 2nd queue byte one cycle EARLY (at T3 rather than T4),
loses far-jump alignment, and runs off into spurious MEMR/MEMW at 00000
instead of taking JMP FAR 0000:0100.

Ruled out: READY is clean (1 every cycle, no phantom Tw); read data is
correct (right bytes fetched); boot images are byte-identical
(boot_even/odd.hex == boot.bin). Correlated signal: the harness-core
starts its first fetch one NEC_CLK earlier relative to RESET release
(release+8 vs the +bootimg release+9). Since a deterministic FSM with
matching inputs must match, an input differs at a cycle <=5 — the suspects
are the RESET-release phase (NEC_CLK-domain core vs nec_bus sys-clock
release) and the exact edge at which the BIU consumes ad_i.

BIU read-data contract (v30_biu): `fetch_data <= ad_i` (prefetch) and the
`eu_rdata` latch fire at the SINGLE clock edge that ends T3 or the final
Tw, guarded by `ready` sampled high at that edge (t3_done). `ad_i` and
`ready` must both be valid at that NEC_CLK posedge. An idealized TB drives
read data combinationally through T2/T3/Tw and trivially satisfies this;
nec_bus must present the same stability at the core's sampling edge.

Next step before any new-bitstream flash: align the core's RESET-release
phase / read-data presentation so the harness-core matches the golden in
sim (Mission A's own gate), likely aided by exposing the core's
V30_BACKDOOR dbg state through system_large in a debug build to pinpoint
the first EU/BIU state that diverges. Only then flash (Mission C).

### Safe-flash (Mission B) — sw/safe_flash.sh, TESTED
Atomic prep -> quartus_pgm -> status(magic) verify, per-step timeouts.
Tested once with the CURRENT known-good bitstream
(hdl/output_files/nec_test.sof, built 2026-07-12): prep OK, quartus_pgm
"Configuration succeeded", verify OK (MAGIC confirmed, cfg readback
0x01ff0008 = known-good small-mode design, use_core bit reads 0). Board
echo test passed afterward. On an unreachable board after flashing the
script STOPs and demands a physical power cycle (no retry). This is the
ONLY sanctioned path to reprogram the FPGA.

### 2026-07-13 (cont.) — desync root-cause refinement + review items

Refined hypothesis for the core<->harness desync (leading candidate): a
read-data HOLD-margin race at the core's sampling edge. The BIU latches
fetch/read data at the rising CLK edge that ends T3 (t3_done). nec_bus
drives read data under `drive_en`, which it DEASSERTS entering T4 - i.e.
at essentially the same NEC_CLK edge the core samples on. The real chip
samples with its ~65 ns internal output/again-input delay, so it reads the
data mid-T3 with margin; the synchronous core samples AT the T3->T4 edge,
where nec_bus is simultaneously releasing the drive - zero hold margin, a
phase race that resolves per-fetch depending on micro-alignment (explains
why the first fetches read correct bytes but a later one desyncs the queue
pop by one cycle). Fix direction: hold the harness read-data drive to the
core through (past) its T3->T4 sampling edge - i.e. present read data to
the core the way tb_v30_core does (valid across T2/T3 and stably past the
sampling edge), NOT gated to release exactly at T4. This must hold on
hardware too (the FPGA-internal core sampling the harness-driven bus).
Next iteration: implement the core-side read-data hold, re-run
check_ab_sim to green, THEN proceed to Mission C (flash) / D (disp phase
matrix) via the now-plumbed CFG.use_core. A debug build exposing the
core's V30_BACKDOOR dbg_regs through system_large would pinpoint the first
divergent EU/BIU microstate if the hold fix is insufficient.

Review items folded in (commit 2035cce):
- HOST PATH: CFG.use_core (bit 25) now plumbed through v30ctl.py (set_cfg,
  serve CFG 5th field, cfg --use-core, status), v30run.py
  (ServeRunner.cfg + run_image use_core=). Backward compatible; updated
  v30ctl.py scp'd to the board.
- gen_seq CONTAINMENT: forward branches could land inside a safe-gadget
  (DIV / string), skipping trap-safe setup and escaping via the untouched
  IVT (fz101 -> 0x99xxx). Gadgets are now atomic (emit_atomic + branch
  target snap-forward). 120 seeds clean.
- QS-FLICKER: classified as a queue-status display artifact - check_seq
  separates a 1-cycle F<->S QS-only disagreement into a tolerated `flick`
  count (real divergence always shows in the other columns); --strict-qs
  to investigate; the A/B run is the definitive confirmation.

## 2026-07-13 (block 2) — Mission A2/D/E: laws landed, gate satisfied

Mission A2 (hold fix): the core<->harness desync was the predicted
delta-cycle race - the core's derived CLK posedge saw POST-edge values
of nec_bus outputs (zero hold), where the chip sees pre-edge values via
board propagation. Fix = one sys-clock input pipeline on every
nec_bus->core signal (system_large only). check_ab_sim: core boot now
MATCHES the chip golden in-harness (187 rows, loop-aligned). Chip path
bit-identical (tb_harness 25/25, synth hex byte-identical).

Mission D (three laws, all golden-neutral at 155440/155500 exact):
1. disp-reader final-pop defer: fresh queue head (dry last cycle) + pop
   on fetch T2 -> defer 1 (the 2-cycle read shift is mechanical).
   S_DLO polls dry queues every cycle (old 2-grain was aliased).
2. disp16 store ready @ hi-pop+2 (old @+3 was a phase-aliased fit).
3. split word access at offset FFFFh: 2nd byte at offset 0 of the SAME
   segment (found by fz494; real functional bug, was 20-bit linear +1).
Method: sw/sweep_dispphase.py (168-cell matrix: 4 reader + 3 store EA
modes x 3 prefixes x 8 phases) + tb_v30_core +eudbg state dump; three
law iterations to 168/168. All measured chip-vs-TB through serve -
no flash needed; silicon A/B confirmation rides with Mission C.

Mission E: **Campaign 3 exit gate SATISFIED - 500/500 consecutive
clean (fz600-1099), zero flickers.** Expansions: callret 500/500
(fz1100-1599); sregw/popf gating in progress. Cumulative session fuzz:
~2400 board-vs-TB sequences.

Known open (non-gate): waits>=1 qs_e flush-display timing at far jumps
(2 rows/trace, phase-parity; execution identical) - the only class the
w1 matrix shows; reader/store laws are wait-clean.

## 2026-07-13 (block 3) — synthesis fix + Mission C FIRST LIGHT

### Iterative shifter (second synth anti-pattern, commit e7c315a)
After the iterative divider (c2beb6a) the Quartus build was still slow:
a SECOND 255-deep combinational unroll dominated - the `shrot` shift/
rotate function (D0-D3/C0/C1, all 8 sub-ops), evaluated as one giant
cone at retirement. Replaced with ONE iterative shift stage (the divider
pattern): loaded at each dispatch site, one single-bit shift per clock
through the S_SHWAIT/S_WAITX window already spent, result+flags landing
in sh_res/sh_fl before S_EX/S_RMWX. Full-8-bit-count/no-masking, the
byte sibling-lane shift register, and every fitted flag law preserved
bit-for-bit. GATE: golden 155440/155500 (per-op BYTE-IDENTICAL to
baseline), all shift forms 500/500 (13000/13000), fuzz 30/30 chip-vs-TB.
Also audited the EU: the 255 shifter was the ONLY large combinational
unroll; INS/EXT, ROL4/ROR4, 4S are sequential (burn-counter) machines.

### Quartus build (Task 2) - the spike is GONE
Full compile clean (0 errors, 0 critical warnings), .sof produced:
- **Analysis & Synthesis (quartus_map): 00:03:47** (was ~25 min).
- Fitter 00:03:57, Assembler 12s, STA 5s; total 00:08:01.
- Megafunctions: 2 lpm_divide, BOTH the small 8-bit AAM (D4/CVTBD)
  `/` and `%` (the intended small combinational unit, c2beb6a) - no
  wide/group dividers, no giant combinational cones.
- Fmax emu/core clock 84.82 MHz (FPGA_CLK2_50 137 MHz); worst-case
  setup slack +9.151 ns, hold +0.268 ns - timing MET.
- Utilization 9,835/41,910 ALMs (23%), 5079 registers, 13 DSP (12%).

### Mission C - safe_flash + IN-SILICON FIRST LIGHT
safe_flash.sh hdl/output_files/nec_test.sof: PREP/FLASH/VERIFY all OK
(cfg 0x1ff0008, use_core=False, pwr_good, cpu_running). Board reachable.

check_ab_hw.py all 800 (boot image, both selector positions in silicon):
- **chip position (use_core=0) vs boot golden: MATCH over 800 rows** -
  the new bitstream did NOT disturb the known-good chip path.
- **core position (use_core=1) vs chip: MATCH over 800 rows** - FIRST
  LIGHT: the in-fabric V30 core matches the socketed part, same harness,
  same run, in real silicon.
- core vs golden: MATCH over 800 rows.

In-silicon A/B sequence fuzz (check_seq --hw-ab, chip vs fabric core
BOTH on the FPGA, no Verilator): **fz4000-4039 40/40 clean** - the
definitive in-silicon confirmation of the Mission D disp-reader /
disp16-store / split-wrap laws (previously chip-vs-TB only).

### Campaign 4 A/B done-criterion SATISFIED (2026-07-13)
**In-silicon A/B sequence fuzz, chip (use_core=0) vs fabric core
(use_core=1) both on the same FPGA, no Verilator: fz4040-4539 500/500
clean, zero divergence, zero QS flickers** (with fz4000-4039 = 540
consecutive). This is the true-silicon analogue of the Campaign 3 exit
gate and satisfies the Campaign 4 done-criterion (>=500 zero-divergence
across the corpus). Board echo-healthy after the run. The in-fabric V30
core is now cycle-for-cycle indistinguishable from the socketed chip
across the fuzz corpus in real silicon.

## 2026-07-13 (block 4) — clock-enable (CE) refactor, all gates passed

The in-fabric core was decoupled from NEC_CLK: it now runs on the fast sys
clk and advances only on CE (= nec_bus tick_rise) with CE_HALF (= tick_fall)
for the one negedge process. CE is locked to the NEC_CLK cadence so the A/B
comparison stays lock-step with the chip. Full plan + itemized outcome in
docs/notes/ce_plan.md; commits e15492d / 9716b01 / 6f7cdd2 (+ this doc/build
commit).

- RTL: every sequential process in v30_biu/v30_eu gated `if(srst) ...
  else if(ce)`; reset stays ungated (bkd_load fires on RESET regardless of
  CE). The two desync traps were handled: eu_started moved into the ce
  branch and added to the biu reset; the eu "every-state" pulse/pin block
  moved inside `else if(ce)` with flush_now<=0 added to the eu reset;
  negedge t1_half2 gated by ce_half.
- GOLDEN GATE (CE-high): 155440/155500 bit+cycle-identical (only 8F.0
  residual); w1/w3 1200/1200. CE-HOLD SANITY (+ce_div=N>1, +ce_hold_check):
  rows identical to N=1 and u_eu.state/u_biu.state/q_cnt/div_cnt frozen on
  CE-low clocks (N=3 9940/10000, N=7 5000/5000, zero freeze violations).
- HARNESS: nec_bus exposes tick_rise_o/tick_fall_o (its only change);
  system_large u_core switched to .CLK(clk)/.CE/.CE_HALF. check_ab_sim core
  boot MATCH 287 rows (Mission A2 input pipe carried over unchanged — no
  new phase fix needed, contra the 2026-07-13 boot-desync worry). Chip path
  bit-identical: tb_harness ALL PASSED, largemode_synth.hex byte-identical.
- BUILD: 0 errors, 8m40s total (quartus_map 3m52s, Fitter 4m24s) — no
  synthesis spike. Timing MET: emu/core clock 32 MHz, Fmax 48.09 MHz
  (setup slack +5.227 ns, hold +0.263 ns). Fmax fell from the pre-CE
  84.82 MHz because the core now lives on the 32 MHz fabric domain by
  design; 50% headroom. Util 9,690 ALMs (23%), 5117 regs, 13 DSP; only
  the 2 intended small AAM lpm_divide units. safe_flash'd (VERIFY ok).
- HARDWARE A/B (real silicon): chip position vs golden MATCH 800/800
  (chip path undisturbed by the new bitstream); FIRST LIGHT — CE-driven
  fabric core vs socketed chip MATCH 800/800; in-silicon A/B sequence
  fuzz fz5000-5499 500/500 clean, zero divergence, zero QS flickers.
  Board echo-healthy after. The CE-driven in-fabric core is cycle-for-
  cycle indistinguishable from the socketed chip in real silicon.
- Deferred (as coordinated): a host-selectable independent core-rate CE
  divider (feed the core CE from a host-controllable divider rather than
  tick_rise); the +ce_div plumbing in tb_v30_core is the sim-side seed.

## BIU-rebuild first silicon confirmation (2026-07-14, biu-rebuild @ a5a92a3)

Flashed the biu-rebuild bitstream (coordinator ran safe_flash: Configuration
succeeded 0 errors; VERIFY pwr_good/cpu_running/cap_full True, use_core False
default; harness healthy). Synthesis: 0 errors, timing MET (worst-case setup
slack +4.199ns, hold +0.260ns, all clocks positive). Full hardware A/B:

1. HEALTH echo PASSED (before + after).
2. w0 CROWN JEWEL: boot chip(use_core=0)-vs-fabric(use_core=1) MATCH 200 rows;
   core-vs-golden MATCH. The whole rebuild is w0-EXACT in silicon.
3. w1/w3 DRIFT DROP LIVE: chip-vs-fabric drift is IDENTICAL PER-SEED to the sim
   chip-vs-TB drift (15 seeds 90000-14: w1 both mean 408.1 CLEAN 1/15; w3 both
   596.5 CLEAN 3/15 - every seed value matches exactly). Synth float floor = 0;
   the fabric core is cycle-for-cycle the Verilator TB. The five landed fronts
   (consumption-resume, arb-store, Jcc-w1-flush, load-ext) are REAL in fabric.
4. BUSLOCK live: chip-vs-fabric release-at-write-T4 EXACT, prefetch-transparency
   EXACT (1 fetch inside), no-false-lock EXACT; assert 2-cyc-late (documented
   inert Stage-6 residual). Stage-6 LOCK confirmed in silicon.
5. INTERRUPTS: chip-vs-TB inject-int fz10000-10199 = 200/200 CLEAN (unregressed;
   the flush/arbitration changes are w0-neutral). The 2 chip-vs-FABRIC hw-ab
   flags (fz10000/10018) are chip-vs-TB clean = the inert async-INT-recognition
   float floor (async pin latched 1 cyc differently in fabric), not a bug.

VERDICT: the rebuild's first silicon confirmation is CLEAN. w0 chip-exact in
fabric; the w1/w3 drift drop is real (silicon==sim exactly); BUSLOCK live;
interrupts unregressed. Board healthy on the new bitstream.


## SLOT-FIRE -> T1 LATENCY (canonical; measured, do not re-derive)

Measured over one w1+w3 trace set across fz90000-07, 3068 slot fires. Every
distribution is a SINGLE value - there is no ambiguity to re-litigate:

    slot_mode      slot_id                  n       delta = T1_cycle - fire_cycle
    COMMIT_DIRECT  SLOT_EVAL_EXT         2901       1   (2901/2901)
    COMMIT_DIRECT  SLOT_FLUSH_HOLD          9       1   (9/9)
    COMMIT_STAGED  SLOT_TI_PLAIN          131       2   (131/131)
    COMMIT_STAGED  SLOT_T4_FLUSH_STAGED    27       2   (27/27)

STAGED slots route the descriptor through nxt_* and deliver on the nxt_live
transition, costing one extra cycle; DIRECT slots load cur_* and enter T1 next
cycle. So a commit intended to land T1 at clock X must fire at X-1 (direct) or
X-2 (staged).

CONSEQUENCE (class-5, three encounters with the same wall): a resume that
commits via the STAGED Ti-plain path can never achieve cidle 3. cidle 3 needs
the commit at T4+2, which is exactly where the q_aged push-absorb blocks, so it
slips to 4. This is why (a) the old veto-then-retry quantizer could only ever
produce 4, (b) the flush path DOES reach 3 - it commits direct, and (c) a
staged-path scheduled resume leaves a 100%-armed +1 column.
Reproduce: sw/class5_b1shadow.py instrumentation + the d[62..66] slot fields.


## GOLDENS CANNOT GATE CLASS-5 WORK (read this before trusting a green run)

The class-5 law arms only under waits: **0 arms over 50,388 w0 cycles** (eval_ext
is never asserted at w0). So the w0 golden is STRUCTURALLY UNREACHABLE by it.

Measured, not theorised: a class-5 build that had catastrophically diverged the
waited bus sequence - |mass| 2939 vs 409 baseline, negative tail 1777 vs 263,
and 842 aligned opportunities VANISHED from the corpus join - still scored
**169000/169000 w0, 1200/1200 w1, 1200/1200 w3**.

    A GOLDEN-GREEN CLASS-5 BUILD MEANS ALMOST NOTHING.

The gates with actual power, in order:
  1. n == 16058 on the corpus join. Any drop = the bus sequence changed = the
     build is not a timing candidate at all, whatever its mass looks like.
  2. the class-5 proxy (model cidle vs the 16058 chip labels): mass, signed
     histogram, negative tail, and the armed/unarmed split of each column.
  3. goldens - necessary, never sufficient.

## VERILATOR ASSERTIONS: --assert IS NOW WIRED IN (sw/check_core.py)

Assertions were being SILENTLY COMPILED OUT. A per-arm class-5 SVA was written,
ran green, and reported nothing - because it never executed. An assertion that
cannot fire manufactures false confidence.

--assert is now always passed by check_core.build(). Verified live by inserting
a deliberate always-false probe and confirming it trips with a real %Error +
$stop, then removing it. Re-verify the same way after touching the build.

## PHASE-R INVARIANT: a new COMMIT_DIRECT slot is a new DISPLAY cause

slot_show_now = slot_fire && slot_mode == COMMIT_DIRECT, and the Phase-R
equivalence probe asserts slot_show_now == ext_show. So ANY new direct slot
trips it unless ext_show gains a matching cause with THE SAME GUARDS (including
state == ST_TI && !nxt_live, which ext_show's existing terms get implicitly via
eval_ext). Adding a class-5 resume slot fights this machinery term by term.
The Phase-S hook (selected_prefetch_grant) exists precisely so a demand
scheduler can RE-POINT the grant instead of adding a slot - that is the intended
integration point.


## STALE-BINARY TRAP (campaign rule)

A Fix A+B proxy run reported mass=409, +1=28 and >=+2 columns EXACTLY equal to
the pre-B2 baseline. It was not a pass: the build had FAILED (the TB still
referenced a signal the RTL rewrite had deleted) and the proxy silently ran the
PREVIOUS binary.

    A RESULT THAT REPRODUCES THE BASELINE TO THE ROW IS NOT A PASS, IT IS A SMELL.

RULE: verify the binary is fresh before believing any proxy result - especially a
flattering one. Compare the binary mtime against the run clock:
    ls -la --time-style=+%H:%M:%S hdl/tb/obj_dir/Vtb_v30_core ; date +%H:%M:%S
This is the same failure family as a silently-compiled-out assertion (see the
--assert note above). We have now hit both. Neither is caught by any test - both
present as "everything passed".

Related: `check_core.build()` prints its verilator command but a FAILED build
leaves the old binary in place, so downstream harness code runs happily against
stale RTL. Always grep the build output for %Error, or check the mtime.

## TEMPDIR LEAKS: a `finally` does not survive SIGKILL

90 leaked scratch dirs (999MB) came from ad-hoc inline scripts using mkdtemp with
try/finally, run under an outer `timeout`. When timeout SIGKILLs the interpreter
the finally NEVER RUNS. run_tb_internal's own eud_ dirs leaked zero over the same
period - the harness discipline held; the ad-hoc scripts did not.
RULE: ad-hoc probe scripts get the same cleanup discipline as the harness, or
they write into the session scratchpad instead of mkdtemp. Check all four
prefixes when auditing: eud_ lbcal_ seq_ asrt_.

## SCRATCH SPACE: DELETE ONLY WHAT YOU OWN, BY KNOWN PREFIX — NEVER BY WILDCARD (2026-07-17)

A worker cleaned foreign /tmp accumulation by iterating a generic `/tmp/tmp*`
wildcard (content-guarded on check_core's batch.txt/out.txt, but the `tmp` prefix
is owned by no one - any process uses it). It happened to be harmless (disk at 11%),
but that is not the point: /tmp is SHARED scratch other processes may be using,
nobody asked for the cleanup, and deleting paths you cannot PROVE you created is
never authorized regardless of disk health. Same reasoning class as the freshness
family - an action that looks safe under conditions you have NOT verified.
STANDING RULE: delete ONLY paths you created, by their specific known prefixes
(eud_ / seq_ / lbcal_ / asrt_ + your own named scratch dirs), never by generic
wildcard, never outside your session scratchpad and your own known leak prefixes.
check_core's TemporaryDirectory auto-cleans on normal exit; leaks are only from
timeout-SIGKILL, and you do not hold those specific paths - so you CANNOT clean them
safely. If foreign /tmp accumulation ever looks like a genuine disk risk, REPORT it
(df + the prefixes seen) and let the user decide. Do not delete it yourself.


## FRESHNESS: EVERY ARTIFACT IN THE CHAIN NEEDS A CHECK AGAINST ITS SOURCE

Three self-validating false positives, all in one campaign, all presenting as
"everything passed":

  1. ASSERTION SILENTLY COMPILED OUT. A per-arm SVA was written, ran green, and
     reported nothing - verilator drops every `assert` without --assert. An
     assertion that cannot fire manufactures false confidence.
     CHECK: insert a deliberate always-false probe, confirm %Error + $stop.

  2. STALE VERILATOR BINARY. check_core.build() leaves the OLD binary in place
     when the build FAILS, so the harness runs stale RTL happily. It reported
     mass/+1/>=+2 EXACTLY equal to the baseline - a result that reproduces the
     baseline TO THE ROW is not a pass, it is a smell.
     CHECK: grep the build output for %Error; compare binary mtime to the run
     clock:  ls -la --time-style=+%H:%M:%S hdl/tb/obj_dir/Vtb_v30_core ; date +%H:%M:%S

  3. STALE BITSTREAM (.sof). hdl/output_files/nec_test.sof was 14 HOURS older
     than the RTL it was about to "confirm" - it contained neither the banked
     class-5 law nor even the lowband veto. Flashing it and reporting
     "fabric==TB, silicon confirms the build" would have been a FABRICATED
     CONFIRMATION of a design the FPGA has never held - AND IT WOULD HAVE LOOKED
     CLEAN, because the fabric would genuinely match a TB built from the same
     stale source. A false positive that validates itself.
     CHECK, before EVERY flash:
         ls --time-style=+'%F %H:%M' -la hdl/output_files/nec_test.sof
         git log -1 --format='%ad' --date=format:'%F %H:%M' -- hdl/rtl/core/
     The .sof MUST be newer than every RTL file it claims to contain. The TB
     being green says NOTHING about the bitstream - they are built from the same
     source by different tools, so they agree even when both are stale.

RULE: EVERY ARTIFACT IN THE CHAIN NEEDS A FRESHNESS CHECK AGAINST ITS SOURCE -
not just the one you are currently thinking about. Chain: RTL -> Verilator
binary -> proxy result; RTL -> Quartus .sof -> fabric capture; RTL -> assertion
enablement -> SVA result. Each link can go stale independently and each failure
mode is silent.

NOTE ALSO: the banked class-5 law has NEVER been through Quartus. f43927f exists
because Quartus 17.1 rejected RTL Verilator accepted (named-field struct
assignment). Synthesis is a genuine gate, not a formality: run it as its own
step and treat a synth failure as a FINDING (it would mean the census validates
something unbuildable), never as a step to push through on the way to a flash.


## GATES WHOSE PRECONDITIONS DISSOLVED (the same family as staleness)

Three instruments in this campaign were VALID, then silently stopped being valid
because the thing they were measuring changed underneath them. None of them
failed; they just quietly stopped meaning what they used to.

  1. THE PROXY / CENSUS RATIO. Held at 1.03, 1.04 across two builds, then went
     to 1.72. The proxy only ever saw CODE->CODE ALIGNED opportunities. The
     ratio held ONLY WHILE CODE->CODE DOMINATED THE MASS. Deleting pf_drain
     removed most CODE->CODE mass and promoted the blind spot from negligible to
     44% of proxy mass (measured on the all-transition corpus; the census had
     implied ~22%). Repaired by sw/class5_alltrans.py, which drops the
     CODE->CODE filter - the FILTER excluded those transitions, the CHIP never
     did.

  2. THE n == 16058 HARD GATE. The aligned-prefix population is CONDITIONED ON
     HISTORICAL MODEL QUALITY: it was frozen when the model was worse. Every fix
     extends alignment into regions the old dump never sampled, so a CORRECT
     regeneration SHOULD grow n. Revised gate:
         n >= old n, AND the growth is ATTRIBUTED (extended alignment vs new
         emission), AND any DROP is a hard stop, AND unexplained growth is a stop.
     This immediately caught something a raw n>=old would have passed: net
     growth 8220 -> 8339 CODE->CODE (+199 new, -80 GONE), and the 80 absent rows
     are 3 (seed,w) pairs whose ALIGNED PREFIX SHORTENED - i.e. the model
     diverges EARLIER there. 6 pairs extended, 3 shortened. A net win hiding a
     partial regression.

  3. THE w1/w3 GOLDEN SUITES. 6 mission-H-FITTED forms x 200 cases. They gate
     "fitted-form regression", NOT "waits accuracy" - recent builds change paths
     those forms never exercise. A pass there is NOT waits-accuracy evidence,
     though a FAILURE still means something. A broad RANDOM-FORM w1/w2/w3 suite
     should replace them as the gate (w2 also closes the odd-only coverage gap:
     the only uniform waited suites on disk are w1 and w3, BOTH ODD).

RULE: THRESHOLDS AND GATES ARE COMPOSITION-DEPENDENT. Re-derive acceptance
criteria from the CURRENT composition at every pre-registration; never carry one
forward. "new-negative-tail > 20", ">=+2 within +-5", the 1.03 ratio and n==16058
were all sized against compositions our own fixes destroyed.


## (5th, and the worst) THE ALIGNER CUTOFF CORRUPTED DATA COLLECTION ITSELF

The other dissolved-precondition failures corrupted JUDGEMENT. This one corrupted
COLLECTION - it decided what we were allowed to see.

    D = first index where bus TYPE or ADDRESS differs  -> TRUNCATE EVERYTHING AFTER

Measured on real pairs:
    fz91000 w3   D=116, mismatch run 2, post-D agreement 92/94 = 98%  -> 91 rows binned
    fz90002 r7.7 D=192, mismatch run 2, post-D agreement 47/49 = 96%  -> 46 rows binned
One two-access EU-vs-prefetch ARBITRATION SWAP (chip takes the prefetch first,
model takes the EU first - same two accesses, opposite order) discarded a stream
that then matched the chip EXACTLY.

PERVERSE: it bites HARDEST WHEN THE MODEL IS GOOD ENOUGH TO RE-ALIGN. As the
model improves the corpus SHRINKS. Every corpus ever built here under-sampled the
late-program region.
**EVERY HISTORICAL CORPUS-SIZE NUMBER IN THIS LOG IS A FLOOR, NOT A COUNT.**
(8220 gz, 16058 joined, n==16058 "hard gate" - all floors.)

THE SECOND-ORDER TRAP - I FELL IN IT MYSELF: after finding the cutoff bug I
measured "post-D agreement" POSITION-LOCKED and concluded fz91000 r7.7 was a
GENUINE sustained divergence at 15% agreement. It was not. The model MISSES ONE
CODE FETCH at chip i=130 (shift=-1); everything after is off by one, so a
position-locked comparison reports ~15% while the streams are in fact still
matching. Once shift is tolerated it aligns 205/212 with 4 resyncs.
=> A GAP-LENGTH OR POSITION-LOCKED TEST CANNOT SEPARATE TRANSIENT FROM SUSTAINED.
All three pairs had run==2. Only POST-RESYNC AGREEMENT UNDER A TOLERATED SHIFT
distinguishes them - and it turned out to distinguish nothing, because all three
were transient.

THE FIX: sw/class5_align.py. On mismatch, search shift in [-2,+2] x skip in
[1,8] for a re-sync confirmed by CONFIRM=8 consecutive exact matches; stop only
if none exists. Every resync is RECORDED with its contents - a resync IS a
model-chip divergence, it is data, not noise.
ADVERSARIALLY VALIDATED (mandatory - an aligner that accepts everything recovers
nothing but noise): chip(fz91000) vs model(fz90003), DIFFERENT PROGRAMS ->
37 aligned pairs (the shared boot prefix), 0 resyncs, stop=SUSTAINED at i=37.
The aligner rejects unrelated streams.


## ERROR CLASS: ANY DISAGREEMENT CLAIM MUST TOLERATE A SHIFT FIRST

The cutoff bug (above) and my own "genuine sustained divergence" retraction are
THE SAME BUG AT TWO LEVELS:
  - the ALIGNER declared divergence at the first position-locked mismatch;
  - then I measured "post-D agreement" POSITION-LOCKED and read 15% as a real
    divergence - when the model had simply MISSED ONE FETCH and everything after
    was off by one. With a tolerated shift it was 205/212 aligned.
A position-locked comparison of two streams that differ by an insertion/deletion
reports near-total disagreement while the streams are in fact still matching.

RULE: BEFORE ANY MEASUREMENT CAN CLAIM DISAGREEMENT, IT MUST TOLERATE A SHIFT.
Percentage-agreement, gap-length, first-mismatch-index, diff counts - all are
invalid as disagreement evidence unless computed AFTER a resync search over
shift x skip. This has now bitten twice, at the aligner level and at the
analysis level. It generalises to every "the model diverges here" and every
"X% match" number in the campaign: recompute any that were position-locked.

Corollary: an AGREEMENT claim under a tolerated shift is safe (it found a real
alignment). It is only DISAGREEMENT claims that the shift-intolerance corrupts -
they over-report. So the direction of the historical error is known: every
position-locked "diverges" / "X% mismatch" was an UPPER BOUND on divergence.


## SIGN CONVENTIONS: census and alltrans/proxy are OPPOSITE - do not conflate

    census   (class5_gaperr): ge = chip_interval - model_interval
                              -> ge = -1 means the MODEL is 1 cycle LATE (over-pause)
    alltrans (class5_alltrans): ge = model_idle - chip_idle
                              -> ge = +1 means the MODEL is 1 idle LATE (over-pause)
So the census "-1:117" block and the alltrans "+1" block are THE SAME phenomenon
(model late). The alltrans "-1" rows are the OPPOSITE (model early) and are NOT the
census -1 block. Verified against the census's own cti-mti table (-1:121 = model
MORE idle = late), which agrees with ge=-1 = model late.
I nearly attributed census -1:117 using alltrans -1 rows - the inverted phenomenon.
Caught by cross-checking the two ge definitions before reporting.
RULE: state the sign convention explicitly at every gap-error claim, and when
mapping proxy<->census, map by DIRECTION (model early / model late), never by the
bare sign of ge. This is the eighth instrument-family trap and the second sign/
frame inversion the campaign has caught (the first: position-locked % agreement).


## (9th, and the biggest) THE PRIMARY CENSUS NEVER RAN RANDOM WAITS

The random-wait match is the stated #1 priority. The primary census tool
(class5_gaperr) generated its wait vectors like this:

    wv_of(ws, wmax) = [_r.Random((ws<<8)|wmax).randint(0,wmax) for _ in range(4096)]

A FRESH Random(seed) is constructed PER ELEMENT, so every element is the same
first draw -> the whole 4096-entry vector is a CONSTANT (uniform wait). The
per-(ws,wmax) constants are mostly 0 (= w0). So the ENTIRE gaperr census history
(422, 308, 188, and the sixth-attempt 114) was a DEGENERATE uniform-wait census,
heavily w0-weighted - it NEVER exercised per-cycle-random waits.
Fixed: one Random, drawn 4096 times.
Impact: the real random-wait census is ~5x the degenerate number (direct-path
544 vs degenerate 114; delta-fix 834 vs degenerate 188). Every historical
"census mass" understated the real class-5 error ~5x.

STRUCTURAL RATIO, settled while finding this: gaperr's ge (interval delta) and
its cti-mti (idle delta) are IDENTICAL on every seed set - the T1..T4 active span
is the same chip-vs-model (same accesses, same waits applied identically), so
interval delta == idle delta. The true census/idle-proxy ratio is 1.00. The
recalib-derived 1.47 ratio, "417 baseline", "1/3 non-idle mass", and the ordering
re-sizing built on them were all artifacts of recalib's OWN (separate) mass bug.
recalib had CORRECT random vectors but BROKEN masses (307 != its 169 proxy);
gaperr had CORRECT masses but BROKEN vectors. Both retired/fixed accordingly.

THE SAVING GRACE (why every relative decision survived): the PROXY chain (px.py
over the bandage corpus) used class5_bandage.py's CORRECT wv generation
(one Random per vector, r4.3/r7.7 proper per-cycle random) THROUGHOUT. So every
accept/reject was made on random-wait-inclusive data. 834->544 on the corrected
census confirms those relative decisions generalize to the real metric. The bug
corrupted the ABSOLUTE census numbers and the map's sizing, never the direction
of any call.

## SLOT_LAW_RESUME synthesizes clean on Quartus 17.1 (sixth-attempt build)
0 errors, 0 critical warnings, .sof produced. The direct-commit resume slot is
real hardware, not sim-only - the last structural doubt on the sixth attempt
cleared before flash.


## FRESHNESS RULE - QUARTUS COROLLARY (byte-identical content breaks mtime)

A git checkout that restores byte-identical RTL updates the file MTIME without
changing content. Quartus smart-compile then correctly SKIPS recompilation (its
own checksum sees no change), leaving the .sof older than the RTL by mtime while
the .sof is in fact current. The mtime freshness check flags STALE; it is a false
positive, but do NOT resolve it by reasoning ("I know the content matches").
RESOLUTION: force a full compile - `rm -rf db incremental_db output_files/*.sof`
then recompile - so the .sof is unambiguously regenerated. Confirmed: the forced
full compile produced a fresh .sof (09:10) and the flash then verified clean.
A plain re-run of `quartus_sh --flow compile` is NOT enough - smart-compile skips
it; you must delete the databases.

## SCRIPTS CARRYING THE wv BUG SHAPE (do NOT re-trust their numbers)

The `[_r.Random(seed).randint() for _ in range(4096)]` constant-vector bug (#9)
is pervasive. The CRITICAL class-5 chain is CLEAN (class5_bandage, class5_alltrans,
class5_flushtraj, class5_gaperr[fixed]). These SECONDARY scripts still carry it -
any historical finding of theirs used UNIFORM-wait vectors where it intended
random, and must be re-derived before being relied upon:
  sw/class5_factorW.py, sw/eureq0_char.py, sw/class5_lmin.py,
  sw/flashcheck_store.py, sw/moffs_optcensus.py,
  and many exp_*/cmd_* paths in sw/causal_wrand.py (lines 1022,1135,1206,1382,
  1507,1650,1827,1971,2065,2215,2275,2376,2465, ...).
NOT the bug: causal_wrand:157 (k*7+3)%(wmax+1) is deterministic-by-design.
The proxy (px.py over the bandage corpus) and the corrected census are correct;
this list is about SECONDARY analyses whose absolute numbers are suspect.


## RESUME LAW: DONE PERMANENTLY (falsifiable artifact) — RE-RATIFIED 2026-07-17 on the AUTHORITATIVE one-to-one matcher

The class-5 CODE->CODE resume-duration law (arm: PAUSE iff d_cnt_a>=3 && occ>=2;
duration: cidle_sel per the sixth-attempt direct-path) is DONE, re-ratified after the
lost 288u pairing matcher was disqualified (irreproducible) and replaced by the
AUTHORITATIVE matcher below. Tooling: sw/class5_remap.py.

AUTHORITATIVE PAIRING MATCHER (ships with this artifact): greedy nearest-partner,
opposite-sign, ONE-TO-ONE (each member used once), within an access-ordinal window;
canonical cell = (window=1, exact-cancel). Over the 286-row/544u census
(class5_census544b.jsonl.gz): paired 148u / unpaired 396u.
  SENSITIVITY (error bars): exact {148,186,202}u  loose(|sum|<=1) {226,268,298}u
  over window {1,2,3}. Pairing is window-sensitive; these are the shipped bars.
  DISCIPLINE NOTE: my first-pass FLAG-based matcher reported 161u; it double-counted
  cancellation CHAINS (a middle impulse cancels two neighbours) by 13u/6 rows. The
  one-to-one greedy 148u supersedes it.

CORRECTED DONE SWEEP — unpaired CODE->CODE = 105 rows / 190u (was 79/121u under the
lost matcher; previously-mispaired rows fell back in). Fit disc(90000-07)/test
held(90008-19), key prev_tw,d_cnt_a,m_occ:
  largest SIGN-PURE clean cell 8u; largest NET(|sum|) cell 8u  -> BOTH < 10u floor.
The two largest TOTAL-mass cells are NOT clean fixable causes: (1,0,2) 15u is H-SLIP
TAIL (6/7 rows have a -2 partner at ordinal di<=3 - slot-pairs the window=1 matcher
missed); (0,3,3) 15u is MIXED-SIGN (net 7u, cancels). PRE-REGISTERED CRITERION
(largest clean held-out cell < 10u) -> MET at 8u.

H-SLIP BASIS for the paired mass (paired CODE-successor 129u): pair-magnitude |N|=2
dominant, slot-scale (|N|<=2) 78%; paired CODE->CODE 100% land in POPULATED law cells,
82% slot-scale. >=80%-fitted criterion MET -> the paired mass is the built law's
+-1..2-slot DELIVERY scatter (retry +1s / duration misses / decline scatter), not
order swaps. So the DONE basis is MECHANISM-EXPLAINED, not merely "small residual":
  unpaired CODE->CODE 190u = mixed-sign small-cell scatter (largest clean cell 8u)
  paired  CODE-succ   129u = built-law +-1..2 slot delivery scatter (H-SLIP)

FALSIFIABLE: anyone who finds a key that cleanly separates a SIGN-PURE held-out cell
>=10u in the 105-row/190u unpaired population (on a fresh seed group), OR shows the
paired mass is <80% slot-scale, REFUTES this and reopens the arc. Full row data:
sw/class5_census544b.jsonl.gz (prev_bs==cur_bs==CODE); pairing + cells reproduced by
sw/class5_remap.py. The q_cnt=0 starved rows remain part of the irreducible scatter.

STANDING INVARIANT (DONE-guard): unpaired CODE->CODE mass = 190u +- 10 under the
authoritative matcher. Any future build (e.g. the MEMW->CODE -1 kind-offset fix) must
hold this. This is the FIRST campaign arc formally closed, now on a mechanism-backed,
reproducible-matcher basis.

NOTE (superseded): the earlier 79-row/121u residual list and its 6u figure were drawn
under the lost 288u matcher and are RETIRED; the numbers above supersede them.

## Task #15 emission-blocker isolation (2026-07-17) — "no done marker (runaway)"

Emission (emit_suite.py cmd_emit) was 100% "no done marker in trace (runaway test?)".
Software-first isolation found THREE independent causes:

1. STALE BOARD REGISTER (class-5 leftover): R_WRAND held 0xace10002 (replay=1,
   seed 0xace1) sticky from a class-5 replay run. Random-wait Tw insertion stretched
   every trace far past the capture window. FIX: reset R_WRAND=0 before emission.
   METHOD-RULE: emission MUST assert a clean WRAND/cfg (waits=0, replay=0, enable=0)
   at session start — v30run serve does NOT clear board-side WRAND when spec is None.

2. PARTIAL-CAPTURE REGRESSION (32db59a "serve v2, partial capture"): EMIT_CAP=1536
   returns only the first 1536 of the 4096-record capture buffer, but the done marker
   (OUT 0xFC) for a single-instruction test sits PAST record 1536. -> spurious
   "no done marker". validate() never hit this (uses cap=None). FIX: EMIT_CAP=4096
   (= capture-buffer size). Confirmed: non-preload B8/00/89 pass 15/15 with full cap.
   METHOD-RULE: any capture-prefix cap MUST exceed the completion-marker position;
   a partial cap that truncates the tail silently reads as a runaway.

3. WRONG CORE SELECTED FOR EMISSION (config — RESOLVED, not structural). Initially
   read as a possible structural/bitstream regression; the true cause was config.
   Preloaded cases (0x63C0 preamble) fail 100% ONLY on the internal v30_core
   (use_core=True, left set by the H-PHASE flash), whose still-being-built EU does
   NOT implement the 0x63 undocumented no-op used as the prefetch-queue filler.
   The SOCKETED REAL V20 (use_core=False) runs it fine (preload-cal: 63C0 x8
   side-effect-free, queue fills to 6 bytes; preload+non-preload 24/24 each).
   Golden emission MUST capture from the socket. use_core was added AFTER v0.1
   emission (2035cce > 8b5a7d7), so v0.1 always used the socket and never needed
   pinning; the emission path was never updated when use_core landed. FIX:
   EMIT_USE_CORE=False pinned at all 4 emit call sites (emit_case, emit_evt_case,
   preload-cal x2). NO bitstream A/B / rebuild needed — the same bitstream passes
   preload on the socket, exonerating the fabric. Independently corroborated by the
   v20 arch oracle: opcode 0x63 = 100% arch-fail on the internal core (same gap).
   METHOD-RULE (truth source): golden capture is the socketed chip (use_core=False);
   the internal core is the DUT, not the reference. ENFORCED as: (a) a pin at every
   emit call site (EMIT_USE_CORE=False), AND (b) a per-run assertion in cmd_emit that
   refuses to emit unless the truth source is the socket, AND (c) every emission run
   logs its truth source (socket vs core) to emit_run.log / emit_log.txt. Goldens may
   ONLY ever come from the socket. This exists so the next use_core-style A/B flag
   added to the harness cannot silently redirect truth to the core again -- an
   emission "golden" captured from the internal core is a truth inversion (the DUT
   grading its own homework) and would poison every downstream comparison.

THROUGHPUT (all 3 causes fixed, socketed chip, both variants): ~25 cases/sec
(~40s per 1000-case form). 1k x 347 forms projected ~3.9h; 10k x 347 ~1.6 days.
Per-case disk ~275 B gzipped -> 1k ~95 MB, 10k ~950 MB.

## BCD secondary (sibling-lane) — DEFERRED, plan booked (2026-07-17)

The 4S segment-override PRIMARY defect is fixed (v30_eu commit). Residual 7/6000
large-CL (84-99) failures are a DISTINCT secondary defect in the fitted nibble-serial
sibling-lane WORD logic (bcd_add8/bcd_sub8), which was fitted bit-exact on 1020 golden
byte iterations from our OWN emission. CONFIRMED that emission's 4S generator only
exercises CL 1..6 (`rng.randrange(1, 7)`), so the fit never saw large CL.

PLAN (do NOT start yet, per coordinator):
  (a) After the main v0.2 emission completes, emit a small supplemental large-CL 4S
      mini-tranche from the SOCKET (own seed base e.g. v30-4slarge, a few hundred
      cases each of 0F20/0F22/0F26 with CL biased to 40..127), so we have native-V30
      large-CL captures.
  (b) Re-derive the sibling-lane logic against the JOINT constraint set: v20 large-CL
      cases + native-V30 large-CL captures (avoids trading one dataset's fit for
      another's). PRE-REGISTERED GATE: w0 169000/169000 unchanged AND v20 0F20/0F22/0F26
      files 100% arch-only (minus idx-767-class harness anomalies, folded into the
      F-pop artifact audit).

idx 767 (14-record near-zero-bus anomaly): folded into the item-3 artifact audit.

## 64K-mirror memory aliasing — oracle artifact + emission correctness (2026-07-17)

DISCOVERY (root-causing the "F6.1 TEST-mem PF" sparse divergence): the Verilator TB
`tb_v30_core.sv` memory was 64 KB MIRRORED across the 1 MB space (`mem[lat_addr[15:0]]`).
20-bit addresses aliased to 16 bits, so any v20 case whose footprint contains two
distinct 20-bit addresses that collide mod-64K reads the wrong byte -> HARNESS false
divergence (NOT an RTL bug). idx 6391 proof: operand 0xdac3e and the imm byte 0x7ac3e
both alias 0xac3e, so the operand read returned the imm and flags = f(imm) exactly.
Blast radius: 100% of the sampled sparse (non-F-pop) fails had mod-64K collisions.

FIX: `mem [0:1048575]` full 1 MB flat; all indexing + undo log widened 16->20 bit.
GATE (met): v20 sparse bucket 68 -> 2 on the full 1MB re-sweep (the 66 aliasing
artifacts cleared; the 2 residuals C4/FF.5 are the OTHER artifact class, "fewer than
2 F pops"). w1/w3 1200/1200 unchanged.

w0 = 168997/169000 (NOT a regression): the 3 diffs are COLLISION-DEPENDENT v0.1
GOLDENS - 0F12 idx219, C1.6 idx205, F7.4 idx174, each with 8-9 mod-64K collisions in
their footprint. They were captured on the BOARD's own 64K-mirrored test RAM and are
only valid under mirroring; a flat-1MB sim correctly diverges on them. Proves the board
mirrors too. These 3 want re-emission (collision-free) but are documented, not "fixed".

EMISSION CORRECTNESS (task #17 precondition): testimage.compose's collision check
(ram-vs-ram + instr/stub/ivt footprint) is NECESSARY but NOT SUFFICIENT - it misses
ram-vs-instruction, stack, and prefetch touches. Post-hoc scan of the emitted v0.2:
5.22% of cases (5998/115000, 90 forms) have footprint collisions -> invalid on flat
emulators. FIX: added `_mirror_collision(test)` trace-based guard to emit_suite;
emit_case/emit_evt_case now reroll (ComposeError, seed-deterministic) on any colliding
capture. The already-emitted v0.2 forms need a ~5% re-emission pass (or full re-emit)
before they are upstream-valid.
