# race_rom physical mechanism — interpretation, emergent-model feasibility, silicon probes

*Architect (fable), 2026-07-22. Follow-on to race_rom_mechanism_design.md (removal design, verified 0/16384). READ-ONLY campaign; this doc + race_rom_physical_* scratchpad artifacts are the deliverable. Board proposals are DESIGNS ONLY — batched for a user-approved session; worker is mid tail-family campaign. Labels DERIVED (exact, from the table/µcode) / FITTED (from the staircase model) / SPECULATIVE (narrative) enforced throughout.*

## Headlines
1. **The race is decided by a handful of boolean pattern detectors, not fine analog delay** (mixed labels — Codex F7 relabel applied). FITTED-EXACT: canonically extracted per quadrant, only 3-6 pre-classes and 4-7 pop-classes exist; membership predicates are small SOPs with recurring cores — `S&!AC`, `S&Z&!AC` (±P,±CY), `{P,CY}`, and (pop.DIR=1 only) V-splits. DERIVED (raw table, fit-free — robustness run 2026-07-23): the extreme POP classes are representation-invariant CONSTANT COLUMNS — e.g. dt=00/01 always-B pops = `S&!Z&!AC&!P ∪ S&Z&!AC&P` (V,CY free; 8 words), dt=00 always-A pops = `S&Z&!AC&!P`; at dt=10/11 the same S&!AC family flips to the always-A side — so the S&!AC core family IS table-intrinsic. NO constant pre rows exist: every pre-side class is fit-relative. DERIVED (as a statistic): per-quadrant B fractions .786/.807/.239/.277 — pre.DIR flips the default winner; the finer "classes advance/retard by discrete steps" reading is FITTED-EXACT.
2. **Condition-PLA-only hypothesis refuted; narrowed per Codex F8** (DERIVED, raw-table form): words differing only in AC carry identical Jcc condition-line vectors (O; C; Z; C|Z; S; P; S^O; (S^O)|Z read only V,CY,Z,S,P), yet AC-only flips change the measured outcome on 3,904 (pre-side) / 2,552 (pop-side) determinate cells. Therefore **the outcome is not solely a function of the enumerated Jcc line vectors** — representation-invariant, no staircase involved. What this does NOT exclude: mixed mechanisms where the condition PLA contributes S/Z/P/V/CY-derived signals while AC reaches the race through another path, or shared-driver arrangements. "Does not run through the condition evaluator" was an overclaim and is withdrawn; stronger exclusion needs the Axis-3 data.
3. **The 68-cell exception overlay collapses to 8 product blocks ≈ 3 resonance rules** (FITTED-EXACT, robust across both known zero-error fits — Codex F7): resonant-pre-core × resonant-pop-core forces the outcome toward the pop side's core: pre `{S,Z}±V±CY` × pop `{P,CY}±V` → A (all four quadrants); pre `{S,Z}±V±CY` × pop `{V,DIR,S,Z}±CY` → B; pre `{P,CY}` × pop `{Z}±V` → B; plus the 32-cell ghost-repair block (16 pre words × pop `{V,DIR,S,Z}±CY` at dt=11 — the ghost's own pre-set). Robustness: the independent-order fit's 56 exceptions are a strict subset of the shared-order 68; identical 6 pop families ({Z}±V, {P,CY}±V, {V,S,Z}±CY); ghost membership exactly 32 in both. The cores pair adjacent PSW flag bits (S-Z = bits 7-6; DIR-V = bits 10-11 flanking IE=9; CY-P = bits 0-2) and the ghost core is result-inconsistent (Z=1 with S=1 and P=0 cannot come from any real ALU result byte); {P,CY} and {Z} are realizable, so "all anomalies are PLA-contradictory" is FALSE — the precise shared property is *flag-family purity*: cores are pure result-PLA-family subsets ({S,Z}, {Z}) or pure carry-family+parity ({P,CY}), never a generic mixed word (SPECULATIVE as physics, exact as description of the fitted blocks).
4. **Emergent replication in RTL: possible but unearned — negative result recorded** (Axis 2). A two-timer discrete-event model (live-row readiness class(pre|DIR) vs strobe class(pop|DIR-pair) + the 3 override rules) reproduces the table *by construction*, because any staircase is realizable by free choice of integer delays. It compresses (≈30 SOP cubes + ≈10 integers + 3 rules) but adds ZERO independent constraints, so it is a re-parameterization of the fitted tables, not evidence. Recommendation: keep the shipped case-table race_law.svh; the emergent form earns mechanism status only if its parameters transfer to independent observables (Axis 3).
5. **Five silicon probes designed and ranked** (Axis 3), each with a pre-registered prediction matrix (amended per Codex F3-F6/F10): bounded frequency-sensitivity sweep (`v30ctl.py cfg --div` already plumbed; NOT a full analog-vs-discrete decider — invariance leaves subcycle/edge-locked analog open), IRET twin (µ01EA carries the identical `OPR->FLAGS F E` µop — context-transfer and decode-specificity probe, 4 hypotheses), NOP-horizon + condition-agreed flag-consumer arm (refresh topology), interposed-writer matrix with pilot and timing-matched controls (which store each µcode path writes), ghost piggyback (second-observer CORRELATION evidence with full positive-control protocol).

## Axis 1 — physical interpretation of the fitted structure

**Canonical classes (FITTED-EXACT — exact properties of the frozen shared-order staircase, one of ≥2 zero-error decompositions; Codex F7 relabel. Raw-table invariants called out inline as DERIVED. Full predicate dump in race_rom_physical_classes.py output).** Per quadrant (dt = {pre.DIR, pop.DIR}):
- dt=00: pre 3 classes (A-most: `S&Z&!AC&P&CY` n=2; then `S&!AC&!P | S&Z&!AC&!CY` n=10; bulk n=52), pop 4 classes (B-forced: `S&!Z&!AC&!P | S&Z&!AC&P` n=8; near-B `!S&!Z&!AC&P&CY` (={P,CY}) n=2; bulk n=50; A-forced: `S&Z&!AC&!P` n=4). Note the A-forcing defender pop {S,Z,!AC,!P} IS the ghost core minus V/DIR.
- dt=01/11 (pop.DIR=1): pop classes split on V (`V&S&AC`, `V&!S&Z&!AC`, ... — the disturbed-region signature); at dt=11 the {S,Z}-core word family flips from strongest defender (dt=00, thr=64) to weakest (V&S&Z&!AC&!P at thr=2) — the thr phrasing is FITTED-EXACT, but the core of the claim is DERIVED in raw-table form: {S,Z}±CY words are constant-A columns at pop.DIR=0 in both pre.DIR modes, while their V=1 variants DROP OUT of the constant-A column set whenever pop.DIR=1 (robustness run): **the V,DIR neighbors of IE remove the {S,Z} core's unconditional defense**.
- dt=10/11 (pre.DIR=1): pre bulk is A-leaning (default A), with a B-most class `!S&!Z&!P | S&!Z&!AC&P | S&Z&AC&!P` n=16.
- Condition-PLA test, narrowed (Codex F8): the fitted-class version (12-21/32 line-vector ambiguity per side/quadrant) is FITTED-EXACT; the DERIVED raw-table form is stronger and fit-free — AC-only word flips (identical Jcc line vectors) change the outcome on 3,904 pre-side / 2,552 pop-side determinate cells, so the outcome is not solely a function of the enumerated Jcc line vectors. Mixed hypotheses (PLA contributes line-derived signals, AC arrives via another path; shared drivers) remain OPEN — full exclusion of the condition evaluator is NOT established and is exactly what E1/E4 context transfer would probe.
- Flag-family reading (DERIVED observation, interpretation SPECULATIVE): using the 8086-family circuit taxonomy — S/Z/P derived from the result byte via PLA, CY/AC/V from the carry chain (NMOS 8086 per Shirriff; V20 is NEC's own CMOS reimplementation, analogy only) — every special core is family-pure or family-pure+P; the modifiers that move a word between classes are P and CY (one bit from each family). A refresh/strobe fight in a flag row whose drive strength differs per circuit family, with P as the parity odd-man-out, would produce exactly family-structured classes. This maps cleanly. What does NOT map cleanly (honest ledger): (i) WHY `S&Z&!AC&P&CY` is the extreme pre word in three quadrants; (ii) the exact V-split predicates at pop.DIR=1 (17/31-member classes with 4-8 cube SOPs — no crisp physical reading); (iii) AC's role (biggest special-core requirement is AC=0, but AC has no adjacency to S/Z in PSW bit order; if the physical row packs the 9 flags contiguously — CY,P,AC,Z,S,TF,IE,DIR,V — then AC-Z ARE neighbors and every core is a contiguous run: {CY,P}, {(AC=0),Z,S}, {DIR,V}. This contiguous-run reading is attractive but UNVERIFIED — no V20 die-level flag-row layout is public; the public V20 die work (VCF microcode-ROM thread) covers the µROM, not the flag row.)

## Axis 2 — emergent-model feasibility (verdict: re-parameterization, not mechanism)

Formulation tested: live-row readiness time T_live = L_d(pre6) (the pre-class index), strobe/refresh arrival T_strobe = M_dq(pop6) (pop-class index), class B iff T_live ≥ T_strobe, then apply the 3 resonance rules + ghost-repair block as coupling overrides. This is algebraically THE staircase+EXC decomposition (verified identical, 0/16384 — race_rom_emit_sv.py). Assessment against the coordinator's criterion:
- Parameters: ~30 SOP cubes (class predicates) + 10 class-level integers + 3 override rules + the 16-word ghost pre-set. Far fewer than 16,384 bits — genuine compression.
- BUT the integers are order-realizations, not physics: no measurement in the corpus constrains "delay" beyond the ordering the table itself defines. An RTL discrete-event version would simulate two counters racing to reproduce a comparison we can compute combinationally — added state (counters ⇒ savestate v2 impact), added risk, zero added fidelity. **Plainly: the emergent model needs exactly as much fitted information as the tables and earns nothing until Axis-3 data constrains it independently.** RTL recommendation unchanged: ship the case-table race_law.
- What WOULD promote it: E3/E4 outcomes fixing the refresh topology (on-demand vs strobe-race) and E2 fixing discrete-vs-analog. Then delays become measurable quantities (clock-edge counts or settle windows) instead of free parameters.

## Axis 3 — discriminating silicon experiments (DESIGNS ONLY; user green-light + batch with a later board session; worker executes; forbidden-opcode rules apply — no BRKEM; per-case timeouts per house rule)

Competing mechanisms under test: **M-strobe** (two stores; CITF-strobe vs refresh race at dispatch — primary narrative), **M-demand** (two stores; live row syncs only when a consumer/writer touches flags), **M-static** (one store; analog settle sampled at a fixed node; table is a static function), **M-decode** (9D-decode-specific artifact, not a FLAGS-fabric property). Cell-selection note (Codex F7): "staircase margin" and class labels used to pick cells are FITTED-EXACT quantities from the frozen decomposition — legitimate for stratified SELECTION, but any margin-ORDERED prediction (e.g. E2's flip ordering) is a prediction about the fitted representation and is labeled as such.

**E2 — bounded frequency-sensitivity sweep (RANK 1: highest information per board-hour; pure CFG). Scope downgraded per Codex F3 — this is NOT an analog-vs-discrete decider.** Harness: `v30ctl.py cfg --div N` → NEC_CLK = 32 MHz/div (nec_bus.sv:34,145-166; system_large.sv:102; pll.v outclk_0=32 MHz); baseline div=8 = 4 MHz; sweep {4,6,8,10,12,16} = 8→2 MHz, floor-limited by the known min-clock gotcha (memory note) — worker confirms the floor with a NOP-sled smoke run before sweeping. Geometry caveat stated precisely: the scheduler counts CPU clocks, so EVENT-COUNT geometry is div-invariant — but event matching and delay advancement occur on tick_rise (nec_bus.sv:491-526), whose WALL-CLOCK spacing scales with div (nec_bus.sv:145-166); pin-to-CLK phase, duty, and FPGA↔V30 setup/hold margins all change with div. Cells: 68 exceptions + 30 staircase-margin neighbors + 10 deep-bulk controls = 108 × 6 divs; controls per Codex F3: (a) repeat baselines — every cell run 3× at div=8 interleaved through the session (not once up front); (b) matched NON-RACE controls at every div (same geometry, pre-IE=0 cells — must stay class-A everywhere; plus a no-INT arm verifying flag state) to expose board-margin artifacts; (c) one anatomy run per div. Pre-registered hypotheses (all four live): H-freq-sensitive-race (class flips ordered by staircase margin, monotone in div, non-race controls clean); H-subcycle-analog (settle ≪ 125 ns or edge-locked precharge → INVARIANT despite being analog); H-board-artifact (flips also hit non-race controls or are non-monotone/non-margin-ordered); H-discrete (invariant). Interpretation rules: invariance = "no detectable frequency dependence over 2-8 MHz at this board timing" — it does NOT exclude analog settling (H-subcycle-analog survives); flips attributable to the CPU require clean non-race controls AND margin-ordering AND baseline-repeat stability. STOP: any flip on a div=8 interleaved repeat, or any non-race control failure → halt, report, do not interpret. If CPU-attributed flips → the shipped table is a 4 MHz contract (document in interrupt_model.md). Optional temperature leg flagged user-hands-only.

**E1 — IRET twin (RANK 2: cheap, probes decode-specificity AND context transfer; hypothesis set widened per Codex F5).** µ01EA `OPR->FLAGS F E` is bit-identical in µop form to POP PSW's µ007A (V20UC) — but the surrounding context differs (3-pop stack sequence, FLUSH-terminated, different interval to dispatch), so an identical µop does NOT entail an identical race phase. Rig: load pre-image flags early (POP PSW ≥3 instructions before, outside any race window), execute IRET (CF) with crafted 6-byte frame (IP, CS, PSW_pop with IE=1), INT landing on IRET's boundary (flush-anchored recognition, taken-branch law). Geometry: sweep delay across ≥5 representative cells spanning both DIR modes and both classes (NOT one cell — a single cell cannot distinguish "no race" from "wrong delay for this cell family") before fixing the 100-cell batch. Cells: 100 stratified — the 34 non-diagonal exception cells + 2 representatives per (pre-class × pop-class) per quadrant + 20 margin cells. Pre-registered hypotheses (four, was two): H-identical (fabric mechanism, context-independent → same table); H-shifted (same fabric, context-dependent phase/recovery → table related by class-ordering with a phase offset — compare by rank/threshold ORDERING and fitted offset, not a flat ≥95% identity score); H-schedule (F-handshake outcome set by the FLUSH/dispatch schedule → race present but restructured, orderings NOT preserved); H-decode (9D-specific → race absent or unrelated). Interpretation rules: identity → strong fabric evidence; ordering-preserved shift → fabric with context phase (NOT decode evidence); "no race" or unrelated table is NOT M-decode evidence on its own — it requires the same-context non-9D control: a third flag-image-committing context at matched dispatch distance (candidate: the E4 SAHF arm geometry, or POPF-via-IRET-frame variants) before any decode-specific conclusion. Secondary observable: pushed PSW must equal the frame image in both classes — any deviation is new physics, STOP and report. STOP: no race at any delay on all 5 sweep cells → record, run the non-9D control, do not force.

**E3 — NOP-horizon + flag-consumer arm (RANK 3: separates M-strobe / M-demand / M-static).** Base: 24 stratified class-B cells + 6 class-A controls; interposed NOP count k = 0..6 between POP PSW and the recognized boundary (pre-IE=1 AND popped-IE=1 so the IE@B-3 tap — which sees the popped IE from k≥2 — never masks recognition; pushed-PC check per k confirms geometry). Measured so far: k≤1 same law (7/7). Predictions — M-strobe with background refresh: finite horizon k* where all cells → A; M-demand: NO horizon from NOPs alone (NOP neither reads nor writes flags); M-static: no horizon. Consumer arm (branch-direction confound closed per Codex F4): interpose one flags-READING, non-writing instruction at k=1 — **cells RESTRICTED to those where pre and pop AGREE on the tested condition bit** (JNC arms only on CY_pre==CY_pop cells, JNS only on S_pre==S_pop), so the branch direction is invariant to which image the reader observes; use BOTH complementary encodings (JNC and JC picked per the agreed value) where the cell allows. Untaken-ness is VERIFIED per run, not assumed: pushed PC and the captured bus trace must show fall-through with no flush; any taken branch is logged as a separate observable (it would itself be evidence about which image the condition evaluator read!) and excluded from the sync analysis. Controls: (a) timing-matched non-flag-reading interposer of the same length/queue profile (e.g. MOV reg,reg) — separates elapsed-time effects from read effects; (b) one deliberate taken-branch control arm (known flush topology) to bound what a flush does to the table. Predictions: M-demand → agreed-condition reader forces sync → cells flip to A while the timing-matched non-reader does NOT; M-strobe → reader and non-reader both leave the table unchanged; M-static → unchanged. STOP: any k where INTA fails to appear → geometry broke; fix before interpreting.

**E4 — interposed-writer matrix (RANK 4: maps which store each µcode path writes; run after E1-E3).** Arms between POP PSW and the raced boundary: SAHF (µ007E `tmpa->FLAGS`, no F — writes S,Z,AC,P,CY from AH=W3), CMC (carry-family only), OR AL,AL (ALU W-tag PLA write: S,Z,P from AL, CY=V=0), LAHF (read-only null arm). ~24 cells covering each core family on both sides; W3 chosen to differ from both pre and pop on all 5 low flags. Three observables per run: pushed PSW (which image the dispatch µ01F4 read), final live PSW (class), and ghost bit (E5). Hypothesis space widened per Codex F6 — the three-way grid is NOT exhaustive. Pre-registered per arm: H-bus (writes bus row only), H-live (writes live row only), H-both (both, same µcycle), H-staged (transient staging latch → one store updated at the writer's retire, the other at a later event), H-perbit (per-flag-bank writes → HYBRID images; expected images defined bit-by-bit per arm below), H-elapsed (no store interaction; the writer's execution time alone lets a background refresh mature). Expected pushed/live images: H-bus {W3-merged | class from table(pre, W3-merged)}, H-live {popped | table(W3-merged-pre, popped)}, H-both {W3-merged | table(W3-merged, W3-merged)≈diagonal→A}; for H-perbit the merged words are computed per flag bank (SAHF: S,Z,AC,P,CY replaced, V,DIR retained; CMC: CY only; OR AL,AL: S,Z,P from AL, CY=V=0, AC per its undefined-flag law — worker takes the measured undefined-AC behavior from docs/facts/undefined_flags.md, not an assumption). Controls per arm (Codex F6): (a) a timing-matched NON-writer of the same execution/queue profile (calibrates H-elapsed for THAT arm's length — LAHF only matches SAHF; CMC and OR AL,AL get their own length-matched controls); (b) a LOOKUP-NEUTRAL writer arm: cells chosen so the written image maps to the SAME table class as the unwritten one (any class change then indicts timing/staging, not the image). Phasing: a discriminating PILOT (2 arms × 6 cells, all controls) runs and is interpreted BEFORE the full matrix is spent. Outside-grid outcomes are classified against H-staged/H-perbit/H-elapsed first; only after those fail → STOP, report (genuinely new store or ordering). This experiment also directly tests the µcode F-tag asymmetry (SAHF no-F vs POP-PSW F): if F marks the bus-row port, SAHF must land H-live.

**E5 — ghost second-observer piggyback (RANK 5: ~free, attach to E1/E2 cells). Conclusions weakened to correlation evidence per Codex F10.** Positive-control handler protocol (mandatory, not just no-HALT): the stub executes EI, then a RETIRING instruction (the EI shadow defers recognition one boundary — interrupt_model.md:28-30 — so redispatch is observable only after the following instruction retires), then a NOP observation sled long enough to capture the spurious INTA; the capture must include (a) proof the INT pin is physically deasserted before EI (pin-event schedule + trace), (b) the second INTA cycle itself; no HALT anywhere (masked-INT fall-through), no early reset/mask/state change (the documented post-entry loop corruption, interrupt_model.md:286-297, shows this observer is protocol-sensitive). Every batch carries one known-ghost cell (positive control) and one known-non-ghost cell (negative control); STOP on either control failing before interpreting that batch. Correlations pre-registered, with honest limits: (i) ghost determinism under repeats at baseline; (ii) under E2, lockstep movement of class and ghost boundaries is CORRELATION EVIDENCE consistent with (not proof of) a shared upstream quantity — two independent nodes with similar sensitivity also produce lockstep; divergent movement shows the observers are separable downstream but does not localize the split. The two-observer question is INFORMED, not closed, by this probe; closure needs a manipulation that moves one observer while pinning the other (candidate for a future battery, out of scope here).

Cost sketch (board-hours, rough; updated for the F3-F6/F10 amendments): E2 ≈ 650 base + ~320 interleaved div=8 repeats + ~120 non-race/no-INT controls ≈ 1,100 runs; E1 ≈ 110 + 5-cell delay sweep (~40) + non-9D control arm if triggered (~60); E3 ≈ 240 + timing-matched non-reader and taken-branch controls (~80); E4 pilot ≈ 25 first, full matrix ≈ 100 + per-arm length-matched controls (~40) only if the pilot discriminates; E5 amortized + 2 control cells per batch. Total ≈ 1,800 runs ≈ two long sessions (was one); if a session is short run E2's div={4,8,16} skeleton + E1's sweep+pilot — they bound frequency-sensitivity and context-transfer, the two cheapest high-information results.

## Phasing
| Phase | Content | Size | Depends |
|---|---|---|---|
| P0 | This doc + artifacts reviewed; user green-light on board battery | — | — |
| P1 | E2 frequency-sensitivity sweep (interleaved baselines + non-race controls) + E5 piggyback | board M-L | P0 |
| P2 | E1 IRET twin: 5-cell geometry sweep, then 100-cell batch (+E5) | board S-M | P0 |
| P3 | E3 horizon + condition-agreed consumer arm + matched controls | board M | P1/P2 read-out |
| P4 | E4 PILOT (2 arms × 6 cells), interpret, then full writer matrix | board S then M | P3 |
| P5 | Synthesis: promote narrative elements to MEASURED where the amended interpretation rules allow; interrupt_model.md update; decide if emergent model is now earned | S | P1-P4 |

Risks: min-clock floor eats the low end of E2 (mitigate: confirm floor first; even {4,6,8,10} = 8→3.2 MHz spans 2.5×); E2 board-margin artifacts masquerading as CPU effects (mitigated: non-race controls + interleaved baselines, F3); IRET race geometry may not exist or be phase-shifted (4-hypothesis set + non-9D control, F5 — absence is a finding, not decode evidence); E4 hypothesis space still not provably exhaustive (pilot-first + staged/per-bit/elapsed alternatives bound the spend, F6); temperature leg needs user hands (optional, flagged); all board work waits on the tail-family campaign — nothing here touches the tree.

Artifacts (scratchpad): race_rom_physical_classes.py (canonical classes, minimal SOPs, condition-PLA test — 8-minute run, output preserved in the session log), the axis-2 product-block formalization (inline session run), plus the prior campaign's race_rom_* set (frozen model, emitter, verified .svh). Sources: [Shirriff, silicon RE of the 8086 flag circuitry](http://www.righto.com/2023/02/silicon-reverse-engineering-intel-8086.html) (flags mid-ALU, phase-transparent mux-recirculating latches — the fight-prone structure; NMOS 8086, analogy only), [Shirriff, 8086 ALU](http://www.righto.com/2020/08/reverse-engineering-8086s.html), [VCF: The NEC V20 Microcode ROM](https://forum.vcfed.org/index.php?threads%2Fthe-nec-v20-microcode-rom.1254770%2F=) (public V20 die-level µROM provenance; no public flag-row layout), [µPD70108/70116 datasheet](https://datasheets.chipdb.org/NEC/V20-V30/IC-3552A.PDF).

## Axis-3 MEASURED RESULTS (E-battery; RR2 execution 2026-07-23, socket, use_core=False)

Rig: sw/exp_race.py (reconstructed POP-PSW boundary-race cell rig; the original
was scratchpad, lost). Cell = (pre7<<7)|pop7, 7-bit {V,DIR,S,Z,AC,P,CY}; pre-image
live (pre-IE=1), POP PSW pops the pop-image, INT at the own boundary (exp_int
CODE-T1-anchored scheduler, delay=5), class = STEADY-STATE (warm-loop) final live
PSW's 7 race flags == pop (A) or pre (B). Iteration-1 is a cold-queue anomaly
(always reads pop) and is discarded. Validation gate: 108/108 == int9d_race.hex at
div=8 (76 cells independently measured; 32 ghost-repair cells pop∈{0x78,0x79}∧pre.DIR=1
scored A by the shipped stored-A convention — their underlying flag-fight measures B,
recorded for E5; the ghost OBSERVABLE is E5's, not this class discriminant).
Min-clock-floor NOP-sled smoke first: all divs {4,6,8,10,12,16} FLOOR-OK (sw/e2_floor_smoke.py).

### E2 — bounded frequency-sensitivity sweep — VERDICT: total invariance
**No detectable frequency dependence over 2-8 MHz at this board timing.** The 108-cell
class table (68 exceptions + 30 staircase-margin + 10 deep-bulk) is INVARIANT across
divs {4,6,8,10,12,16} = 8→2 MHz: **0 class flips vs the div=8 baseline at every div.**
Three interleaved div=8 baseline repeats STABLE (0 flips vs B0 — rig-stability confirmed,
no baseline drift). pre-IE=0 non-race controls all class A and no-INT popped-image sanity
clean at every div (no board-margin artifact). Artifacts: sw/exp_race_sweep.{log,json}.

Interpretation (amended conclusions-ladder, per Codex F3): all TESTABLE analog predictions
are NULL; a **discrete/synchronous mechanism is favored**. This does NOT formally exclude a
**sub-cycle / edge-locked settle** — H-subcycle-analog survives invariance by construction
(settle ≪ 125 ns or precharge phase-locked to an edge → div-invariant despite being analog).
"Invariance" here means exactly "no detectable frequency dependence 2-8 MHz at this board
timing", not "analog excluded".

E2 prediction-matrix outcome (the four pre-registered hypotheses):
| Hypothesis | Prediction | Measured |
|---|---|---|
| H-freq-sensitive-race (M-static's testable form: analog settle sampled at a fixed node) | class flips ordered by staircase margin, monotone in div | **REFUTED** — 0 flips |
| H-discrete (synchronous, div-invariant event geometry) | invariant | **CONFIRMED** |
| H-board-artifact | flips also hit non-race controls / non-monotone | **EXCLUDED** — controls clean, baselines stable |
| H-subcycle-analog (edge-locked/sub-cycle settle) | invariant despite analog | **NOT EXCLUDED** (survives) |

Mechanism bearing: **M-strobe and M-demand predictions CONFIRMED** — both make the class a
data-property over div-invariant (CPU-clock-counted) event geometry, hence frequency-invariant.
**M-static's testable (frequency-sensitive-settle) form REFUTED**; its edge-locked variant is
the surviving H-subcycle-analog and is not separated by E2 (needs E3/E4 topology). E5 ghost
piggyback rides these cells (underlying-B + ghost flag captured per cell in the sweep JSON).

### E1 — IRET twin — VERDICT: H-IDENTICAL (context-independent fabric race)
Rig sw/exp_iret.py: pre-image live (pre-IE=1, loader-settled), IRET (CF) with a crafted 6-byte
frame [IP=TARGET, CS=0, PSW=frame(pop) image, IE=1], INT at IRET's flush-anchored own boundary;
same steady-state final-live-PSW discriminant. Geometry pilot (8 cells, both DIR modes + both
classes, delay 0-21): the IRET own boundary is a WIDE stable plateau — **delay 1-21 ALL-MATCH**
(A-cells→A, B-cells→B, == hex), delay 0 pre-trivial (INT before IRET completes). Batch (108-cell
stratified, delay=5): **108/108 == int9d_race.hex, 0 mismatch, pushed-PSW==frame-image invariant
CLEAN in both classes** (no new physics).

Interpretation (four pre-registered hypotheses): **H-identical CONFIRMED** — the µ01EA
`OPR->FLAGS F E` flag commit obeys the SAME race table as POP PSW's µ007A, bit-for-bit, despite
the different context (3-pop FLUSH-terminated far transfer vs single pop). **H-decode REFUTED**
(the race is present and identical, not a 9D-specific artifact). H-shifted (context phase) and
H-schedule (FLUSH/dispatch restructures) are not needed — the table is reproduced without any
ordering shift or phase offset. Bearing: the race lives in the shared FLAGS **fabric**
(µop-level, context-independent), not in decode; combined with E2 this is a discrete/synchronous
fabric commit whose per-cell outcome is a pure function of the two flag words. Secondary
observable clean: pushed PSW = frame image in both classes (µ dispatch reads the frame/pop image
regardless of class), matching POP PSW's "pushed = popped image both classes".

### E5 — ghost second-observer (loop-morphology correlation; PATH 1) — INFORMED, NOT CLOSED
Rig sw/exp_ghost.py. The clean-2nd-INTA positive-control protocol did NOT fire in this
harness (control-gate log exp_ghost_controls.log): the socket ghost is a LOOP-redispatch
phenomenon, not an isolated in-window second INTA (the isolated-INTA manipulation stays
booked as future work, alongside the design's separating-manipulation note). So E5's
observable is the capture-loop morphology; analysis is offline from the committed E2 sweep
(exp_ghost.py correlate -> exp_ghost_correlation.json; loop = the [pop,00,pre] capture
oscillation = the redispatch signature).

Circularity confound (addressed before any correlation claim): the steady-state class
discriminant READS class B from a later loop iteration, so "B <=> loop" is partly
measurement-coupled, not pure physics.
- Candidate "loop = ordinary universal harness re-entry" REFUTED: looping is SELECTIVE --
  34/108 cells park with a single capture (ncaps=1); not every cell re-enters.
- B-cells (42/42 loop): the loop is MEASUREMENT-COUPLED (discriminant reads B from the loop's
  pre-capture) -> excluded from any physics claim.
- Redispatch is FREQUENCY-INVARIANT: 0/108 cells have a div-varying loop flag across
  {4,6,8,10,12,16} -- same as the class (E2).
- Non-circular window = the class-A cells (class fixed A, so looping is not coupled to a
  B-reading): redispatch is confined to the ghost-family pop patterns -- all 32 looping A-cells
  are exactly the ghost-repair cells (pop in {0x78,0x79}); ALL 34 class-A cells at non-ghost-pop
  patterns park (0 non-ghost-pop A-cells loop). So there is NO redispatch without a ghost-family
  pop pattern. (Non-circular direction, honest: A-cell -> park UNLESS at a ghost-family pop.)

Residual entanglement (why this does not close the question): the 32 looping A-cells ARE the
ghost-repair cells, whose UNDERLYING flag-fight is B -- so redispatch and the flag-fight
coincide on exactly those cells; this rig cannot separate "ghost" from "flag-fight" there.
VERDICT (correlation-evidence-only ladder): the one-quantity-two-thresholds question is
INFORMED but NOT CLOSED. Redispatch is a real, selective, pop-pattern-confined,
frequency-invariant observable, entangled in this harness with both the class-measurement
(B-cells) and the flag-fight (ghost-repair A-cells). This RECONCILES with the original
224/16,384-cell ghost subset at specific pop patterns: the physical ghost is pop-pattern-
confined (consistent), NOT all-B-cells -- the "all 42 B loop" is the measurement artifact, not
the ghost. Closure needs the design's manipulation that moves one observer while pinning the
other (booked, future work). Artifact: sw/exp_ghost_correlation.json (108 cells x 6 divs).

## RR2/RR3 CLOSE-OUT (session 2026-07-23/24)

**Campaign summary (Axis-3 E-battery + the IRET RTL landing it produced):**
- **E2 (frequency sweep): total invariance** 2-8 MHz (0 class flips across divs
  {4,6,8,10,12,16}, 3 interleaved div=8 baselines stable, controls clean).
  Discrete/synchronous mechanism favored; testable analog forms refuted;
  sub-cycle/edge-locked settle NOT excluded (H-subcycle-analog survives).
- **E1 (IRET twin): H-IDENTICAL** — IRET's own-boundary flag commit obeys the
  SAME race table as POP PSW (108/108 == int9d_race.hex on the socket), pushed
  PSW == frame image both classes. The race lives in the shared FLAGS fabric
  (µop-level), not decode.
- **E5 (ghost second-observer): INFORMED, NOT CLOSED** (correlation-only). The
  redispatch/loop observable is real, selective, pop-pattern-confined, and
  frequency-invariant, but entangled in this harness with the class-measurement
  (B-cells) and the flag-fight (ghost-repair A-cells). Closure needs a
  pin-one-move-other manipulation (**PATH-2, booked as future work**).
- **P-I1 (vs-RTL): loop alias.** E1's apparent 107/108 core match was a
  steady-state-discriminant loop/data-as-code alias, NOT the race: P-I1b (board
  capture-morphology) + P-I1a (my +racedbg TB trace, sw/pi1a_trace.py) both show
  the race_law consumer never fired on the IRET path (pop_pend=0 / psw_old !=
  pre at every S_TRAP_IVT2W). The lone 0x11a8 "divergence" was a per-cell loop-
  trajectory skew, not a law/hex issue. -> Branch B (real arming fix).

**IRET boundary-race arm — LANDED + reflashed (Branch B).**
- RTL: v30_eu.sv iret_pw commit block now `psw_old <= psw; pop_pend <= 1'b1`,
  arming the shared consumer at IRET's boundary (mirrors 9D). Reuses SS-mapped
  flops — no new flop, no SS_VERSION bump, no ss_lint delta.
- Gates: E1 sim 108/108 == hex; **all 13 v0.3 pin-event flip-guards +
  CF/IRET-non-race + v0.1 INT.9D/INT.FB bit-identical** (cycles+arch, zero
  regression); check_race_law PASS (law untouched); ss_lint PASS (202 symbols).
- Quartus 17.1.0 Build 590 (2026-07-24), full `sys_top` compile: 0 errors;
  race_law stays LOGIC (Ram0-5 uninferred); block memory 840,863 bits UNCHANGED;
  0 new core latches; worst-case setup slack **+4.282 ns** (>= +3.83 floor,
  +0.452 headroom), hold +0.273 ns; ALM 10,208 (+3, noise); registers 5,099
  (-49, in ±70 noise band; no new state).
- safe_flash.sh reflash (2026-07-24): device 5CSEBA6U23 configured, MAGIC
  verify OK, internal-core boot sanity PASS. **This brought the FPGA fabric
  current with master (race_law swap + all tail fixes + IRET arm) — the
  deferred-reflash note is RETIRED.**
- **Gate (a) board vsrtl re-score (first-capture): PRE-fix 42/108 divergences
  (all 42 socket-B cells) -> POST-fix 0/108, 108/108 socket==core.** 0x11a8
  among the 42 now-correct. Goldens: tests/v30/e1_iret_race/.

**Deferred / booked:** E3 (NOP-horizon / consumer arm) and E4 (interposed-writer
matrix) DEFERRED to a future session (budget spent on the IRET resolution).
E5's separating manipulation and the IRET one-NOP-late / pre-IE=0 silicon
addenda BOOKED. The emergent Axis-2 model remains unearned (E2/E1 constrain but
do not promote it).

## Codex adversarial-review response ledger (2026-07-23, task-mrxfbkxa; findings 1-10)
Findings 1,2,9 concern the removal design — changes landed in race_rom_mechanism_design.md; listed for completeness.

| # | Severity | Disposition | Change |
|---|---|---|---|
| 1 | Critical (.svh drift) | **ACCEPTED** (design doc) | Standing sw/check_race_law.py gate: checked-in-artifact equivalence + regenerate/byte-compare + header hex-digest; see design doc gates §5. |
| 2 | High (Quartus late) | **ACCEPTED** (design doc) | Pre-R1 Quartus spike P-R0b with inferred-memory / block-bits / ALM / latch / race_B→psw gates; "Quartus-safe"/"ROM-freed" downgraded to predictions. |
| 3 | High (E2 overreach) | **ACCEPTED** | E2 rewritten as bounded frequency-sensitivity: 4 pre-registered hypotheses incl. subcycle/edge-locked analog (invariance does NOT exclude analog) and board-margin artifacts; tick_rise wall-clock-spacing caveat (nec_bus.sv:491-526/:145-166) stated; interleaved div=8 baselines ×3 + non-race pre-IE=0 controls + no-INT arm at every div; CPU attribution requires clean controls AND margin-ordering AND repeat stability. |
| 4 | High (E3 branch confound) | **ACCEPTED** | Reader arms restricted to cells with pre/pop agreement on the tested condition; both complementary encodings; untaken-ness proven per run (pushed PC + bus trace, no flush); taken branches logged as a separate observable and excluded; timing-matched non-reader + deliberate taken-branch control arms added. |
| 5 | High (E1 phase conflation) | **ACCEPTED** | Hypothesis set widened to 4 (H-identical / H-shifted context-phase / H-schedule / H-decode); flat ≥95% identity replaced by class-ordering + fitted-phase-offset comparison; geometry sweep across ≥5 representative cells before the batch; "no race"/shifted table ruled insufficient for M-decode without a same-context non-9D control (candidate contexts named). |
| 6 | Med-high (E4 grid) | **ACCEPTED** | Hypothesis space extended (H-staged / H-perbit with bit-level expected images incl. measured undefined-AC law / H-elapsed); per-arm length-matched non-writer controls (LAHF only matches SAHF); lookup-neutral writer arm; 2-arm × 6-cell pilot interpreted before the matrix; outside-grid outcomes classified against the alternatives before any "new store" claim. |
| 7 | Med-high (DERIVED vs FITTED-EXACT) | **ACCEPTED, robustness RUN** | Headlines 1-3, canonical-classes header, Axis-3 preamble relabeled. Robustness executed (2026-07-23): 56-exception independent fit ⊂ 68-exception shared fit (intersection 56), same 6 pop families, ghost membership 32 in both. Newly promoted to DERIVED because they are raw-table invariants: the constant always-B/always-A pop COLUMNS per quadrant (the S&!AC family, incl. its side-flip between pre.DIR modes) and the absence of any constant pre row; per-quadrant B-fraction statistics .786/.807/.239/.277. Pre-side class structure and the product-block reduction remain FITTED-EXACT (robust across the two known fits). |
| 8 | Medium (condition-PLA wording) | **ACCEPTED (sharpened)** | Overclaim withdrawn; replaced by the representation-invariant raw-table statement: AC-only flips (identical Jcc line vectors) change the outcome on 3,904/2,552 cells → outcome not solely a function of the enumerated line vectors. Mixed PLA+AC and shared-driver hypotheses explicitly open; headline 2 rewritten. This also corrects the same overclaim in the coordinator-facing summary of the previous session. |
| 9 | Medium (P-R4 disposition) | **ACCEPTED** (design doc) | Three-way disposition: reproduce / stable contradiction → separately-reviewed provenance correction / nondeterminism → cells marked unresolved, deterministic-mechanism claims barred. |
| 10 | Medium (E5 controls) | **ACCEPTED** | Conclusions weakened to correlation evidence (lockstep ≠ proof of shared quantity; divergence ≠ localization); full positive-control handler protocol specified (EI + retiring instruction per interrupt_model.md:28-30 + observation sled + proven pin deassertion + second-INTA capture; no HALT; no early state change); known-ghost + known-non-ghost controls per batch with STOP on control failure; "closes the two-observer question" replaced by "informs" with the closing manipulation booked as future work. |

No findings REJECTED. One coordinator-read amendment: F8's replacement claim was strengthened rather than merely narrowed — the AC-dependence is provable at raw-table level (fit-free), which the original fitted-class phrasing obscured.
