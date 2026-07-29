# BIU class-5 / waited-cadence LAW CARDS — v2

*Stage-A1 deliverable of the BIU prefetch/bus-grid rebuild (task #34). **v2**
rewrite after the Codex critical review (task-ms5d1r7j-bfc7bp, VERDICT: No; 3
Critical / 9 High / 2 Medium). v1's "17/21-case MUST set" was not a sufficient
E1-E3 acceptance basis; v2 makes the acceptance basis an explicit, versioned,
executable-gated, mutation-proven manifest and separates silicon fact from
TB reference from inference.*

## How to read this document (provenance discipline — Codex demand)

Every case carries a **provenance class**:
- **SIL** — silicon-captured: a controlled chip I/O measurement (board `run_chip`
  or a banked fabric==chip capture). The strongest.
- **CEN** — census-derived: measured on the class5 causal_wrand corpus via the
  disjoint-accounting matcher (chip = ground truth, TB = model); a real
  chip-vs-model result but aggregated over a corpus, not a single directed case.
- **TBR** — TB-reference: the CURRENT silicon-validated RTL is the reference; the
  case pins the model's I/O so a rebuild that changes it is caught. Used where no
  standalone directed chip capture exists yet (the mutation battery proves these
  are non-vacuous — a break is detected).
- **INF** — inference/design-doc: a modeling conclusion, NOT a measured I/O case.
  These are **removed from the MUST acceptance basis** (they may inform design).

Every MUST case maps to an **executable detection gate** (§B) and an **owning
E-stage**. **PROVISIONAL** cases (silicon domain not yet closed) are held OUT of
the gating basis until a booked Stage-B board probe closes them — they may not
block E-stage acceptance while unproven, and they may not silently pass either.

**Baseline revision:** `biu-rebuild` @ HEAD (master `8598887`); v30_biu.sv = 2051
lines, v30_eu.sv = 5603 lines. Line refs are generated from this revision. The
audit/unification docs cite a stale 952-line BIU — not used.

**Prose-matches-assertion rule (Finding 14):** every numeric bound quoted here
matches the *executable* SVA/gate, not a stale RTL comment. Where an RTL *comment*
disagrees with its own assertion, that is flagged as a booked RTL-comment cleanup
(Stage A does not modify RTL); the card quotes the assertion.

---

## §A — The MUST acceptance manifest (versioned)

Honest recount after demoting metrics/aggregates/inferences (Findings 2, 7, 13):
v1 counted 17-21 "cases," several of which were metrics (190u), consequences
(−50u, write-scoped), or inferences (≤2-valued phase). v2's independent directed
I/O cases:

| Case | Law | Provenance | Stimulus (identity) | Expected observable | Gate (§B) | E-stage | Status |
|---|---|---|---|---|---|---|---|
| **C1** | LC1 resume: steady-state gap | SIL (biu_model exp4) | fetch-limited stream (NOP/reg sled), waited | prefetch resumes after ~3 idle bus slots (11-cyc/write steady state) | wvec + w1/w3 | E1 | MUST |
| **C2** | LC1 resume: queue-fill ramp | SIL (biu_model two-rhythm) | queue-fill ramp, waited | prefetch resumes immediately at the fill threshold | wvec | E1 | MUST |
| **C3** | LC1 cidle=3 high-N pin | SIL (Arm C sled) | fetch sled at N=8 and N=12 | resume gap 22:12 (N=8), 28:2 (N=12); cidle pins at 3 | wvec/directed | E1 | MUST |
| **C4** | LC2 aged-band PAUSE | CEN (class5_bandage) | q_cnt 3-4, band aged (age≥2), waited resume | chip PAUSEs the prefetch | wvec | E1 | MUST |
| **C5** | LC2 fresh-band GO | CEN (class5_bandage) | q_cnt 3-4, fresh in band (age<2), waited resume | chip GOes (resumes) | wvec | E1 | MUST |
| **C6** | LC3 even-parity RMW-write early | SIL (board 15/15) | RMW mem-write ready AT prefetch T4, EVEN Tw parity | chip commits EARLY (eval_ext direct slot, T4+2) | wvec + uRMW‡ | E3 | MUST |
| **C7** | LC3 write-scoped (loads don't split) | SIL (30/30) | MEMR load ready AT T4, either parity | chip does NOT split on parity (keeps ext_ok) | wvec + uRMW‡ | E3 | MUST |
| **C8** | LC3 odd-parity RMW-write late | SIL-partial | RMW mem-write ready AT T4, ODD Tw parity | chip commits LATE (T4+4) — **2 edge rows unresolved** | uRMW‡ | E3 | **PROVISIONAL** |
| **C9** | LC4 general lead reservation (WRITE) | SIL (biu_model store-vs-prefetch) | store ready 1 cyc after a completing prefetch's T4 | chip blocks the prefetch; store takes the slot | w1/w3 + wvec | E3 | MUST |
| **C10** | LC4 late reservation yields (pf_late_rsv) | CEN (REP-string seeds) | reservation first asserts AT eval (eu_req && !eu_req_p1), q_cnt=1 | chip commits refill CODE prefetch, string next slot | wvec | E3 | MUST |
| **C11** | LC4 owns_slot (enumerated) | CEN | S_DHI final-disp-pop / S_PUSH_CALC@q≥2 coincident reservation | chip idles/reserves (prefetch loses) — **enumerated source set only** | wvec | E3 | MUST (enum) |
| **C12** | LC4 pf_rsv_lead (eu_req=0 onset) | CEN (eureq0_char) | disp16 store reserves at S_DHI, model eu_req=0 at eval | chip has reserved; suppress doomed prefetch (7/7) | wvec | E3 | MUST |
| **C13** | LC4 pf_starved refill override | TBR | deferred eval, queue EMPTY, mem access only reserving | chip prefetches to refill BEFORE the EU access | wvec | E1/E3 | **PROVISIONAL**† |
| **C14** | LC6 Family-5 T3-veto | TBR/SIL-partial | strio-single uline-1 reservation at T3 completion eval | successor-fetch prefetch is vetoed (pick_t3) | w0 + wvec/strio | E3 | **PROVISIONAL** |
| **C15** | LC6 Family-5 TI-exemption | TBR/SIL-partial | warm-1/warm-2-prefix strio at TI grant | prefetch survives (chip grants pop-1/pop+0) | w0 + strio | E3 | **PROVISIONAL** |
| **C16** | LC6 Family-7 idle arm | TBR | strio-single idle-window lead | defer_idle path arms | w0 + strio | E2/E3 | **PROVISIONAL** |

**MUST-now basis = C1-C7, C9-C12** (11 cases, all SIL or CEN). **PROVISIONAL =
C8, C13, C14, C15, C16** (5 cases) — held OUT of the E-stage gating basis until
booked Stage-B probes close them (§A.1).

**GATE-COVERAGE REALITY (from the mutation battery, §B — reported honestly, not
assumed):** of the MUST-now cases, only **C1 (LC1, via wvec), C9/C10 (LC4
pf_late_rsv + general-lead, via wvec/w1/w3)** are currently caught by a board-free
gate. **C4/C5 (LC2), C6/C7 (LC3), C12 (LC4 pf_rsv_lead)** have **NO working
board-free detection gate yet** — their mutation was SILENT on all standing gates
(narrow laws that don't fire on the 20-seed random-soup corpus, or need RMW/strio
opcodes absent from the goldens). These cases are **GATE-PENDING**: they remain
MUST by silicon provenance but cannot gate an E-stage until their directed gate
(§B: G-LC2/G-LC4a/G-LC3-uRMW) is built. So the honest tally is **3 MUST cases
board-free-gated today, 4 MUST cases gate-pending (directed gates booked), 5
PROVISIONAL (board probes booked)** — a precise status, replacing v1's unqualified
"17-case" claim.

‡ **uRMW** = the RMW-class gate of record: a self-supplied uniform-RMW
fabric/chip capture, MANDATORY for any RMW-touching change (no golden suite
carries RMW opcodes — campaign record §5). Board work → Stage B/E3.
† C13 `pf_starved`: the toggle census is BOOKED-OUTSTANDING (campaign record
§6 PIGGYBACK). Provisional until it lands.

### §A.1 — Booked Stage-B board probes (close the PROVISIONAL cases)
- **P-C8** (LC3 odd-parity edge, Finding 6): directed board capture of the 2
  odd-parity-early rows + neighboring Tw histories, logging BOTH pin-derived Tw
  parity AND RTL `tw_par`. Either refine the invariant domain or prove the old
  rows were frame/parser errors. Until then the universal "odd→late" is restricted
  to its proven subset (C6/C7 even + write-scope stand as MUST).
- **P-C13** (LC4 pf_starved toggle census, Finding 9): the booked toggle census
  (own synth+flash+census cycle).
- **P-C14/15/16** (LC6 strio provenance, Findings 4/5): frozen chip/fabric
  captures covering the Family-5 veto, the TI exemptions, the Family-7 idle arm,
  and the cold-arm waited/interrupt cases, with exact expected bus rows. Also an
  **LC6-specific w0 activation census** (LC6 is w0-ACTIVE — see Finding 4).
- **P-LC4-matrix** (Finding 9): a reservation-source matrix (source × q_cnt ×
  lead-age → chip decision + held-out negative controls) so C9-C12 are separate
  gates with disjoint accounting.

---

## §B — E1/E2/E3 as executable gates + the mutation battery (Findings 3, 6, 13)

**E-stage gate definitions (board-free unless noted):**
- **E1** (resume predicate, plan Stage E1 `selected_prefetch_grant`): acceptance =
  {C1-C5, C13} silicon/reference I/O + `wvec` random A/B (`biu_rebuild_wvec_
  freeze.py --check`) + w1/w3 1200 + w0 169k neutrality.
- **E2** (commit/eval collapse, plan Stage E2 eval_ext/defer_*/ff_*): acceptance =
  w0 v0.1 169k (these paths are w0-ACTIVE, §D#2,3,5,6,7) + w1/w3 + `check_ff_t4`.
- **E3** (arbitration re-expression, plan Stage E3 ext_ok/ext_ok_wr/tw_par):
  acceptance = {C6-C12, C14-16} + w1/w3 + `wvec` + the **uRMW** capture + a
  directed strio gate (to build). MUST reproduce H-PHASE (C6/C7).

**The mutation battery** (`sw/biu_law_mutation.py`, board-free) is the
non-vacuity proof of the entire acceptance basis: it deliberately breaks each
law's predicate in a git-restored scratch RTL, rebuilds the Verilator TB, runs
the board-free detection gate set, and records which gates flip red. A law whose
break is caught by ≥1 gate is independently detectable; the CONTROL mutation
(store_pf_boost, an unused shadow wire) must leave EVERY gate green (non-spurious
proof). Detection gate set: `w0` (v0.1 bounded), `w1`, `w3` (uniform), `wvec`
(random A/B), `ff_t4`, `race`.

**MUTATION × GATE MATRIX** (harvested from `sw/biu_law_mutation.log`; the wvec
digest is timing-sensitive — includes the inter-T1 cycle gap, the cadence metric
the laws move; PASS = green, FAIL = the mutation was caught):

| mutation | law | w0 | w1 | w3 | wvec | ff_t4 | race | detected by |
|---|---|---|---|---|---|---|---|---|
| M-LC1  | LC1 resume (law_arm off)      | PASS | PASS | PASS | **FAIL** | PASS | PASS | **wvec** |
| M-LC2  | LC2 low-band (lowband off)    | PASS | PASS | PASS | PASS | PASS | PASS | **NONE** → directed gate |
| M-LC3  | LC3 H-PHASE (ext_ok_wr strict)| ERR* | ERR* | ERR* | PASS | PASS | PASS | **NONE** → uRMW (board) |
| M-LC4a | LC4 pf_rsv_lead off           | PASS | PASS | PASS | PASS | PASS | PASS | **NONE** → directed gate |
| M-LC4b | LC4 pf_late_rsv off           | PASS | PASS | PASS | **FAIL** | PASS | PASS | **wvec** |
| M-LC6  | LC6 strio pick_t3 → pick_any  | PASS | PASS | PASS | PASS | PASS | PASS | **NONE** → directed strio gate |
| M-FFT4 | far-flush ff_t4 off           | PASS | PASS | PASS | PASS | **FAIL** | PASS | **ff_t4** |
| M-EVEXT| eval_ext ext_ok off           | PASS | **FAIL** | **FAIL** | PASS | PASS | PASS | **w1,w3** |
| M-RACE | race_law ROM bit             | –    | –    | –    | –    | –    | **FAIL** | **race** |
| M-CTRL | store_pf_boost (unused)       | PASS | PASS | PASS | PASS | PASS | PASS | **NONE (correct — control)** |

*M-LC3 w0/w1/w3 = ERR: the golden-harness summary line was unparseable for that
one mutated build (wvec/ff_t4/race ran normally). Immaterial to the finding — no
golden suite carries RMW-at-T4-parity opcodes, so LC3's gate is the board uRMW
capture by construction (campaign record §5); the ERR is not a detection.

**What the battery proves (honest condition-6 status):**
1. **Non-spurious:** the CONTROL (M-CTRL, unused shadow wire) is SILENT on every
   gate ⇒ the gate set does not fire on a behavior-neutral change. ✓
2. **Independently detected board-free:** LC1 resume (wvec), LC4 pf_late_rsv
   (wvec), far-flush ff_t4 (check_ff_t4), eval_ext A/B (w1/w3), race (check_race).
   Each maps to a DISTINCT gate ⇒ independence for these. ✓
3. **HOLES the battery exposed (the deliverable earning its keep, NOT hidden):**
   **M-LC2, M-LC3, M-LC4a, M-LC6 are caught by NO current board-free gate.** Root
   cause = CORPUS coverage, not digest sensitivity (the timing-sensitive digest
   was verified to catch LC1's cycle shift; LC2/LC4a simply do not fire — or fire
   masked — on the 20-seed random-soup corpus, and v0.1-w0 carries no strio (LC6)
   or RMW-at-T4-parity (LC3) opcodes). So the corresponding MUST/PROVISIONAL cases
   **C4, C5 (LC2), C6, C7, C8 (LC3), C12 (LC4 pf_rsv_lead), C14-16 (LC6) do NOT yet
   have a working detection gate** and are DOWNGRADED accordingly (§A status
   column) until their directed gate is built.

**Directed gates BOOKED to close the holes (each plugs into this battery — its
mutation must then flip it):**
- **G-LC2** (board-free, buildable): a directed stimulus that forces q_cnt≤2 with
  occupancy aged in the 3-4 band at a waited resume; assert the PAUSE. Add to the
  wvec corpus or a standalone directed check.
- **G-LC4a** (board-free): a disp16-store onset (S_DHI reserve, model eu_req=0 at
  eval) directed case; assert the prefetch suppression.
- **G-LC6** (board-free directed + board provenance): a strio-gadget stimulus
  (opcodes 6C-6F) — v0.1/wvec carry none, exactly the task-#29 F7a vacuous-gate
  lesson; assert the T3-veto + TI-exemption. (LC6 is also w0-ACTIVE, Finding 4.)
- **G-LC3 = the uRMW capture** (BOARD, Stage B/E3): no golden carries RMW opcodes;
  the RMW-parity gate of record is the self-supplied uniform-RMW fabric/chip
  capture (campaign record §5). Board-only by construction.

**Bottom line for the acceptance basis:** the machinery (executable gates +
mutation battery + non-spurious control) EXISTS and is proven; **5 laws are
board-free independently gated today; 4 (LC2/LC3/LC4a/LC6) need the directed gates
above before their MUST/PROVISIONAL cases can gate an E-stage.** This is a precise,
actionable gap list, not a completeness claim — the mutation battery converted
Finding 3's "no answer for which gate fails" into an exact per-law answer.

**B0 UPDATE (Stage-B opening work, gate-search `sw/biu_law_gatesearch.py`):**
G-LC2 and G-LC4a are now CLOSED board-free — the search found discriminating
seeds (**G-LC2 = fz90364, G-LC4a = fz90270**, both ws5/wmax1) where breaking the
law changes the observable model bus stream; added to the wvec corpus
(`DIRECTED_SEEDS`), so M-LC2/M-LC4a are now caught by wvec (targeted-confirmed;
control still silent, 88 cases). **Remaining: G-LC6** (no discriminator in 400
seeds → hand-built non-REP strio gadget, booked) and **G-LC3-uRMW** (board, rides
B1). Matrix is 7-green/2-pending; full re-run when the last two land (before P1).

---

## §C — Cards LC1-LC8 (revised)

### LC1 — Unified resume / demand-deadline (SLOT_LAW_RESUME) — MUST (C1-C3)
**Intervention.** DIRECT-path resume (SLOT_LAW_RESUME, COMMIT_DIRECT, delta=1) at
T4+`cidle_sel`, bypassing the q_aged blackout, replacing the staged delta-2 path.
**Silicon I/O cases (MUST):** C1 (steady-state ~3-idle gap), C2 (fill ramp
immediate), C3 (cidle=3 pin at N=8 22:12 / N=12 28:2). **DEMOTED from MUST
(Findings 7, 13):** "190u±10" is a **regression METRIC** (corpus aggregate,
non-localizing — kept as a standing DONE-guard, NOT an independent I/O case);
"≤2-valued function of leading grid phase" is **INF** (design-doc inference from
the exp_resume sweep, which had 10 WANDER cells and no complete truth table
[biu_rebuild_design.md:154-181]; the older SW predictor was only 70.7-81.7% on
big gaps [biu_model.md:761-790]) — informs the Stage-C grid design, does not gate.
**Predicate (MAY-discard):** `law_arm` v30_biu.sv:768; `law_sel`/cidle
:1969-1993; `law_due` :789; SLOT fire :963. **Executable bounds (Finding 14):**
the SVAs assert `law_ctr ∈ [law_sel-2, law_sel]` (SVA1 :2043) and window lifetime
`law_ctr ≤ law_sel` (SVA5/6 :2031). *RTL-comment cleanup booked:* the comments at
:2030 ("≤ cidle_sel+2") and :2039 ("[sel-1,sel+1]") are stale vs their own
assertions — fix when that RTL is next touched (Stage E). **Corpus:** class5
causal_wrand 90000-90019; Arm C sled. **Detection:** wvec (mutation M-LC1).

### LC2 — Low-band pause — MUST (C4, C5)
**Intervention.** Delay the waited prefetch while occupancy has AGED in the 3-4
band at q_cnt≤2 (Intel-8086 polarity). **Silicon invariant (CEN, Finding 8
resolved):** the SEPARATING state is **band-entry age**, not instantaneous
occupancy — identical q_cnt=3/4 gives BOTH GO and PAUSE, fully separated by age:
**fresh-in-band (age<2) → chip GO; aged-in-band (age≥2) → chip PAUSE** (held-out
3588 opportunities, GO ~96% / PAUSE ~4%, 0 mislabels;
`docs/notes/class5_bandage_findings.md`, data `sw/class5_bandage.jsonl.gz`). The
**two age frames** (Finding 8): the DISCOVERY frame is `band-age` (CE clocks since
the occupancy entered the 3-4 band; threshold ≥2). The IMPLEMENTED predicate
(`lowband_pause` :743, MAY-discard) re-expresses this as `occ34_age` windows
(occ4 age 1-3, occ3 age 1-2) scoped to q_cnt≤2 — a fitted window over the same
aged-band signal; it is the predicate, not the invariant. **MUST = the age-based
GO/PAUSE separation (C4/C5)**, not the exact window numbers. **Detection:** wvec
(mutation M-LC2). **Durable artifact:** class5_bandage.jsonl.gz preserved.

### LC3 — Tw-parity H-PHASE RMW-write commit — MUST (C6, C7); PROVISIONAL (C8)
**Intervention.** `tw_par` observable widens `ext_ok_wr` so an even-Tw-parity
ready-AT-T4 RMW write takes the eval_ext direct slot. **Silicon I/O (SIL):** C6
even→early + C7 write-scoped (loads don't split), **board-confirmed fabric==TB
15/15 / 30/30, both seed groups, random+uniform**. **PROVISIONAL (Finding 6):**
C8 odd→late holds for the sampled phases but **2 odd-parity-EARLY edge rows** the
4-vector probe subset didn't sample remain unresolved — so the UNIVERSAL "odd→late"
is NOT yet a silicon invariant; restricted to its proven subset pending probe
P-C8. "−50u (58→8)" and "write-scoped" are CONSEQUENCES of the one parity change
(Finding 13), NOT independent cases — "−50u" is a metric. **Predicate
(MAY-discard):** `tw_par` :651, `ext_ok_wr` :660. **Detection:** wvec + the uRMW
gate of record (mutation M-LC3; if wvec's corpus lacks RMW-at-T4 phases the
detector is uRMW-only — reported by the matrix).

### LC4 — eu_req=0 reservation family — MUST (C9-C12), PROVISIONAL (C13)
**Intervention.** eval_ext-window vetoes so a doomed CODE prefetch doesn't win a
slot the chip reserves for an EU mem access. **Findings 9/13 resolved:** these are
**SEPARATE laws with separate gates**, not one bundle — C9 general-lead (SIL,
biu_model:198-220), C10 late-reservation-yields (CEN, biu_model:439-456 +
REP-string seeds), C11 owns_slot (CEN, **enumerated source set** S_DHI +
S_PUSH_CALC@q≥2 — every other source keeps baseline yield; a rebuild making
reservation uniform refutes), C12 pf_rsv_lead (CEN, eureq0_char 7/7). C13
pf_starved refill is **PROVISIONAL** (TBR only; the toggle census is
BOOKED-OUTSTANDING, campaign record §6). **Booked:** the reservation-source matrix
P-LC4-matrix (source × q_cnt × lead-age + held-out negatives). **Predicate:**
pf_rsv_lead :727, pf_late_rsv :713, owns_slot :711, pf_starved :685, all into
prefetch_ext :747. **Detection:** wvec (mutations M-LC4a/M-LC4b).

### LC5 — H-ARB eu_ready arbitration — CHARACTERIZED; RETEST on grid state (Finding 10)
**Finding 10 accepted:** the NO-GO rejected ONE predicate search (want_eu
demotion + the tested discriminators), NOT the underlying arbitration problem for
a from-scratch arbiter with NEW grid state. v1's "reproduce the outcome as
residual" was contradictory. **v2 disposition:** CHARACTERIZED-PENDING-RETEST. The
queue-split transposition (k=15) is NOT accepted as architectural residual until
the Stage-D retest (§E). **Retest plan (§E LC5).** Evidence for the OLD NO-GO
stands (paired mass 88% want_eu=0; no discriminator ≥60%/<2%). **Detection:** the
±1-slot pair shows in wvec; but LC5 does not gate E-stages until the retest
verdict.

### LC6 — Family-5/7 strio vetoes — PROVISIONAL (C14-16); w0-ACTIVE (Finding 4)
**Finding 4 accepted — the global w0-neutral claim is FALSE for LC6.** Family-5
modifies the ORDINARY T3 completion-eval via `pick_t3` (:676), dispatched from
`eval_at_t3` (:916) — a w0-ACTIVE path, NOT eval_ext-gated. LC6 is **removed from
the global waited-only proof** and gets its own preservation gate (w0 activation
census + directed strio traces). **Finding 5 accepted:** "counters nonzero" is
**COVERAGE, not an invariant** — demoted; C14/15/16 need frozen chip/fabric
captures with exact expected bus rows (booked P-C14/15/16). Provenance today is
task#24 + fuzz (weak) → PROVISIONAL. **Finding 14 fix:** there are **FOUR**
coverage counters (`cov_f7a_idle_arm`, `cov_f7a_eval_ext`, `cov_f5a_t3_veto`,
`cov_f7a_coldarm`; v30_biu.sv:1050-1053), not three. **Predicate:** pick_t3 :676.
**Detection:** w0 (LC6 is w0-active) + a directed strio gate to build (mutation
M-LC6 — the matrix shows whether v0.1 w0 exercises strio or a directed gate is
required).

### LC7 — store_pf_boost / MEMW→CODE−1 — RETEST on grid state (Finding 11)
**Finding 11 accepted:** "irreducible-by-construction" proves the CURRENT LOCAL
signals can't forecast the off-3 pop — it does NOT transfer to a rebuild that adds
grid/beat state (which LC7 itself names as a possible discriminator). **v2
disposition:** class-C-PENDING-RETEST. ~30u is NOT accepted as a ceiling until the
Stage-F shadow-log retest on rebuilt precommit grid state (§E LC7). **Silicon
I/O (SIL, stands):** occ==5 resume −1, 28/28 unpaired MEMW→CODE rows, random 17/17
uniform 3/3, w0-absent. **Predicate (shadow, unused):** store_pf_boost :513 (NOT
wired). **Detection:** M-CTRL (the control mutation — store_pf_boost is unwired, so
breaking it MUST be silent; this doubles as the mutation battery's own
non-spurious control).

### LC8 — mid-band + pf_drain DELETED — subsumption artifact (Finding 12)
**Finding 12 accepted:** "656/656 covered on two corpora" is **empirical
subsumption on those traces**, not a logical strict-superset. **v2 resolution
(two parts):** (1) **Durable artifact preserved:** `sw/class5_bandage.jsonl.gz`
(the mid-band discovery data) + the derivation in `class5_bandage_findings.md`.
(2) **Strictness by domain-containment (a proof, not a trace count):**
`midband_pause`'s firing domain was the q_cnt 3-4 aged band; `law_arm`'s domain is
`occupied ∈ [2,4] && law_dcnt≥3` (:768-771) — which strictly CONTAINS the 3-4 band
AND extends to occ==2 and the q_cnt≤2 starved cases `midband_pause` never covered.
An LC1 arm firing at occ==2 (outside midband_pause's 3-4 domain) exhibits the
strict superset. **pf_drain** deletion: 98.4% chip-GO where active, TP-coverage
100% subsumed by the resume law, residue pure harm (:450-462). **Booked:** if the
reviewer requires the literal 656-row firing table, it is reproducible from the
class5 corpus by re-instantiating the deleted `midband_pause` predicate as a
shadow probe and censusing LC1 coverage (board-free) — method documented, not yet
re-run. **MUST NOT re-implement** pf_lim=3 drain or a separate mid-band pause.

---

## §D — Omitted-law coverage (Finding 1: cards or explicit exemptions)

Every scheduling/display/handshake mechanism in the rebuild blast radius, mapped
to its current RTL, w0-activity, and detecting standing gate (verified sweep):

| # | Mechanism | RTL:lines | w0? | Encodes | Gate / disposition |
|---|---|---|---|---|---|
| 1 | eval_ext + ext_ok/ext_ok_wr A/B | biu 621/660, 1171/1651 | waited | deferred-completion eval; RMW-write "ready ENTERING T4" widen | **w1/w3** (+ C6/C7, uRMW) |
| 2 | defer_t4 reader commit | biu 1165,1534,968 | **w0** | fetch-T3 eu_soon reader reserved into T4 | **w0 169k** |
| 3 | defer_idle (eu_soon_ea/ivt) | biu 1166,1467,908 | **w0** | idle-window reg-EA / IVT-read early commit | **w0 169k** |
| 4 | near-flush flush_hold/defer | biu 806,1185,1450 | waited | near-flush redirect +1-late under waits | **w1/w3** |
| 5 | far-flush ff_t4/ff_show/ff_evalext | biu 578,1834,1839 | w0 (ff_evalext waited) | far-flush mid-cycle redirect + E display | **check_ff_t4 + w0**; ff_evalext → w1/w3 |
| 6 | QS=E display (e_wait/qs_e) | biu 548,568,579 | **w0** | E code appears on QS pins per deferral law | **w0 169k** |
| 7 | queue push/pop/q_aged/q_fresh | biu 401,422,534,1348 | **w0** | push-to-pop latency; q_aged absorb blackout | **w0 169k** |
| 8 | eu_wdone/eu_rdone | biu 1210,1221; eu 3813,4352… | w0 (==eu_done at w0) | march from zero-wait completion (first Tw) | **w1/w3** (distinct only waited) |
| 9 | ph_ff/bus_phase/grid_phase | biu 1676,1684,1697 | bus_phase w0; grid_phase INERT | 2-cycle grid parity; grid_phase = stretched-grid scaffold | bus_phase→**w0**; **grid_phase EXEMPT (inert/unconsumed scaffold)** — becomes gated when Stage-C consumes it |
| 10 | reset 7-cyc boot reservation | **eu** 428,1555,1996 | w0 | 7-cyc bus reservation post-RESET → FFFF:0000 | **EXEMPT (EU-owned)**; BOOKED: promote `sw/check_boot.py` to a standing gate |
| 11 | BUSLOCK/lock_active/buslock_n | biu 1751,1783,139 | w0 | LOCK pin low span brackets the locked RMW | **BOOKED directed gate** (`exp_lock.py` is a probe, not standing) — or exempt as additive/isolated (design §6) |
| 12 | want_half2 split-half priority | biu 607,669,1891 | **w0** | split-word 2nd half continues next cycle, top priority | **w0 169k** |

**Exemptions declared:** #9 grid_phase (inert, unconsumed — a Stage-1 scaffold,
bit-identical to bus_phase at w0; gated once Stage-C/D consumes it), #10 boot
(EU-owned, not a BIU law; check_boot promotion booked), #11 BUSLOCK (additive/
isolated per design §6; directed gate booked). All others map to an existing
standing gate. The mutation battery (§B) spot-proves #5 (M-FFT4→ff_t4), #1
(M-EVEXT→w1/w3), and the queue/eval w0-active paths via w0.

---

## §E — LC5 & LC7 retest plans (Finding 10, 11 — re-verifiable post-rebuild)

**LC5 retest (Stage D, when grid state is first-class):** directed fresh-chip
sweep of the k=15 queue-split geometry over {queue occupancy × Tw history ×
EU-ready lead × RMW phase}, with held-out neighboring forms (t33 leaves this
occ×Tw sweep open, :280-288). Shadow-log the rebuilt arbiter's grid-slot decision
alongside. **Verdict rule:** UPGRADE LC5 to MUST if the transposition outcome
closes over the new grid state; retain CHARACTERIZED only if the expanded sweep
remains non-separable (then the ±1-slot pair is an encoded expected residual, with
the sweep as evidence). Board: Stage-D/M-milestone.

**LC7 retest (Stage F, when beat_at_cross/fill_state exist):** shadow-log the
rebuilt PRECOMMIT grid state (grid_phase, beat_at_cross, occ, fill) at the occ==5
post-store resume on RANDOM and UNIFORM waits; train the occ==5 −1 decision on the
discovery seeds, FREEZE, score on held-out seeds. **Verdict rule:** UPGRADE to
MUST (wire the boost keyed on the new observable) if it separates prospectively;
retain class-C only if the expanded grid state STILL fails to forecast the off-3
pop before the commit cycle. The w1/w3 golden remains the falsifier (the v1 enable
broke it via recent_evx over-fire).

---

## §F — Findings-resolution appendix (all 14)

| # | Sev | Resolution in v2 |
|---|---|---|
| 1 | Crit | §D added: every KB/KE mechanism mapped to a card/gate or an explicit exemption (grid_phase/boot/BUSLOCK). |
| 2 | Crit | §A: versioned manifest; honest recount to **11 MUST-now (C1-C7,C9-C12) + 5 PROVISIONAL**; metrics/consequences/inferences demoted; the "21" line deleted. |
| 3 | Crit | §B: E1/E2/E3 defined as executable gates; mutation battery maps each case→detecting gate and proves independence. |
| 4 | High | LC6 removed from the global w0-neutral claim (it is w0-ACTIVE via pick_t3); own preservation gate (w0 census + strio) booked. |
| 5 | High | LC6 counter-nonzero demoted to COVERAGE; C14-16 need frozen captures (booked); provenance labeled TBR/provisional. |
| 6 | High | LC3 odd→late made PROVISIONAL (C8); universal rule restricted to the proven even/write-scope subset; board probe P-C8 booked. |
| 7 | High | LC1 "190u" → regression METRIC (not a case); "≤2-valued phase" → INF (design inference, 10 WANDER cells); both removed from MUST. |
| 8 | High | LC2: two age frames documented (discovery band-age≥2 vs implemented occ34_age window); MUST = the age GO/PAUSE separation; class5_bandage_findings.md + .jsonl.gz cited/preserved. |
| 9 | High | LC4 split into 4 separate gated cases (C9-C12) + C13 provisional; owns_slot enumerated set flagged; reservation-source matrix + pf_starved toggle census booked. |
| 10 | High | LC5 → CHARACTERIZED-PENDING-RETEST; §E retest plan on grid state; not accepted as residual until the sweep. |
| 11 | High | LC7 → class-C-PENDING-RETEST; §E shadow-log plan on rebuilt precommit grid state; ~30u not accepted until it fails prospectively. |
| 12 | High | LC8: durable artifact preserved (jsonl.gz + findings doc); strictness by domain-containment proof; literal 656-row reproduction method documented. |
| 13 | Med | §A demotes coupled/aggregate entries; §B mutation battery + case-to-gate matrix give unique stimulus/expected per case; residuals/counters are secondary gates. |
| 14 | Med | LC6 "three"→FOUR counters; LC1 SVA bounds quoted from the ASSERTION ([sel-2,sel], ≤sel); stale RTL comments flagged as booked cleanup; line refs from the baseline revision; prose-matches-assertion rule adopted (header). |

**Verdict-condition coverage (honest):**
1. **Cards/exemptions for omitted laws** — §D ✓ (every KB/KE mapped to gate or
   exemption).
2. **Explicit versioned manifest, 17→precise recount** — §A ✓ (11 MUST + 5
   PROVISIONAL, provenance-classed; metrics/inferences demoted).
3. **E1-E3 executable gates + which-gate-fails** — §B ✓ for the answer; the
   mutation battery gives the exact per-law answer, INCLUDING that 4 laws lack a
   board-free gate today (gate-pending, directed gates booked).
4. **LC5/LC7 retest plans on grid state** — §E ✓.
5. **LC8 durable subsumption artifact** — §F/LC8 ✓ (jsonl.gz + domain-containment
   proof).
6. **Mutation testing / independent detection** — §B ✓ as a PROVEN FRAMEWORK with
   a working non-spurious control: 5 laws independently detected board-free; **4
   laws (LC2/LC3/LC4a/LC6) exposed as NOT board-free-detectable today** →
   directed gates G-LC2/G-LC4a/G-LC6 (board-free, buildable) + G-LC3-uRMW (board)
   booked, each to plug into the battery. This is the battery's core value:
   converting "which gate fails?" into an exact, honest per-law answer rather than
   an unverified completeness claim.

**Net P0 status:** the acceptance-basis MACHINERY is built and proven
non-vacuous; the basis is NOT yet complete (4 directed gates + 5 board probes
outstanding). Routed to the coordinator/Codex to decide whether the directed
board-free gates (G-LC2/G-LC4a/G-LC6) must land before Stage B, or fold into
Stage B's directed-probe measurement (plan Stage B).
