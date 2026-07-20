# Family 5 & 6: Law Derivation and Fix Design

*(Architect-authored (fable), 2026-07-20, from the measured characterization in docs/notes/v03_family5_6_characterization.md + the V20 microcode disassembly docs/V20UC.TXT. Intended landing spot: docs/notes/v03_family5_6_law_design.md.)*

## Part 1 — Family 5: the internal-model explanation (microcode ground truth, not inference)

`docs/V20UC.TXT` (the V20 microcode disassembly, same microcode family as the V30) contains the actual 6C–6F routines, and they settle the mechanism outright:

**Single INS (µaddr 0294) and single OUTS (µaddr 02A0) issue their bus request on the FIRST micro-instruction of the routine:**

```
<norep> 6C,6D:  0294  DX  -> IND          CTL  MEMR IO    <- bus request, µline 1
                0295  dir*sz->tmpa, DI->tmpb
                0296  DI  -> IND       E  CTL  MEMW ES    <- chained write, routine ends (E)
<norep> 6E,6F:  02A0  SI  -> IND          CTL  MEMR       <- bus request, µline 1
```

**REP INS (0298) and REP OUTS (02A4) have a 3-µline preamble with NO bus request** (CX→COUNT, CX=0 test `JMP Z`, dir*sz setup) before the first MEMR at 029B/02A7.

**Every classic string single has a 1-µline preamble** — MOVS (008C), STOS (00B8), LODS (00C4), SCAS (00D0) all do the `dir*sz -> tmpc / ALU ADD` pointer arithmetic first and issue MEMR/MEMW on µline 2. INS/OUTS need no address arithmetic before the access (DX and SI/DI feed IND directly), so NEC front-loaded the bus op.

The chip's BIU is purely demand-arbitrated: at each slot evaluation, a pending EU request wins; otherwise, if the queue has room, a prefetch takes the slot. There is **no deferral logic on the chip at all**. Every observed constraint falls out of this single rule:

1. **Single defers, REP doesn't (the CW=1 discriminator):** singles have the request pending at the very first post-dispatch slot-eval → EU wins → the element's read and write run back-to-back (the write is issued while the read is in flight — note the `E` early-end flag on 0296/02A2) → the bus is never free until the element completes → continuation fetch lands after it. REP's 3-µline preamble (present regardless of CW, including CW=1) leaves the first slot idle → the starved prefetcher takes it → early fetch, identical to our RTL.
2. **2-vs-3 scaling:** the first free slot is after ALL element data cycles: byte or even-pointer word = MEMR/IOR + IOW/MEMW = 2; odd-pointer word = the split memory access adds one bus cycle = 3. No law parameter — it's just "bus busy until the element ends."
3. **Cold-only:** with a warm queue no fetch is due in the dispatch window (occupancy above the fetch threshold), so neither chip nor RTL fetches there — bit-identical. The characterization confirms pf cases carry no in-window continuation fetch. No cold conditioning belongs in the fix.
4. **Why MOVS/LODS/STOS/SCAS singles are clean in our RTL:** their one preamble µline (2 clocks = 1 slot) is exactly enough for the chip's prefetcher to win the slot — matching our RTL's early grant. The entire family-5 phenomenon is **one microinstruction of bus-request onset**, unique to string-I/O singles.

## Part 2 — Family 5 RTL fix design

**Where "always early" originates.** In `hdl/rtl/core/v30_eu.sv`, the strio single dispatch (S_DEC, lines 2726–2760) goes `dly<=1; state<=S_RSV` — and `eu_req` first rises in S_RSV (line 1342). So the EU pipeline is: opcode pop in S_FIRST (cycle P, line 2209), dispatch in S_DEC (P+1), `eu_req=1` from S_RSV (P+2). During P and P+1 the BIU sees `eu_req==0` with a cold queue, and `prefetch_ok` (`hdl/rtl/core/v30_biu.sv` line 540) grants the continuation CODE fetch. That grant path is w0-active (not eval_ext-gated), which is required — these are w0 socket captures.

**The fix: extend `eu_hold`, not `eu_req`.** `eu_hold` (v30_eu.sv line 5386) is precisely the chip-semantics mechanism: "blocks prefetch without counting as request history" — a bus *claim*, not a request, already consulted in `prefetch_ok`, `pf_starved`, `pf_late_rsv`, `pf_rsv_lead`, and `law_grant` (so it behaves correctly under waits too). It is a **pure Moore function of existing state: zero new flops, no `v30_ss_pkg` change, no SS_VERSION bump** (still run the scramble regression as pre-registered). Add:

```systemverilog
// Family-5: single string-I/O bus claim from dispatch (V20 µcode
// 0294/02A0: request on µline 1; the REP routines 0298/02A4 have a
// 3-µline preamble and must NOT claim — CW=1 REP is chip-verified early)
|| ((state == S_DEC)   && (op_instr || op_outstr) && !rep_en)
|| ((state == S_FIRST) && q_pop && !rep_en &&
    (q_byte[7:2] == 6'b011011))          // 6C..6F at the pop cycle itself
```

Do **not** touch: the REP dispatch (`dly<=2; wnext<=S_RSV` — its non-reserving preamble is measured-correct and now microcode-confirmed), `eu_rsv_lead`/`pf_late_rsv`/`owns_slot` (silicon-confirmed, and they gate on `eu_req && !eu_req_p1` which this never feeds), and the S_RSV `dly` values (warm cases are bit-identical, so element request timing is already right — a `dly` change would break them).

**Mid- and post-element need nothing:** the chained S_REQ→S_OUTS_W/S_INS_W write-while-read-in-flight machinery (MOVBK pattern, silicon-verified) already keeps `eu_req` up through the element, including the odd-word split inside the BIU — deferral 2 and 3 both emerge with no added logic. After retire, the normal prefetcher emits the continuation exactly where the chip has it.

**Pre-registered probe P1 (sim-only, before any tranche run):** run check_core with a cycle dump (EU state, prefetch grant, eu_req/eu_hold) on ~10 cold divergent cases — 6C, 6E, 6D even/odd IY, 6F even/odd SI, 26.6E, 2E.6F. Confirm (a) the doomed grant fires at P or P+1 (both covered above), and (b) post-fix traces are **bit-identical to the chip goldens in absolute rows**, not just cycle order. Two stop conditions: if for the seg-override forms the grant fires during *prefix* processing (before opc registers), STOP and report — the hold needs a head-byte-peek design decision, don't improvise one; if post-fix the MEMR lands a slot late vs chip, the request-onset (not just the claim) needs moving, which is a different, riskier change — report first.

## Part 3 — Family 6: mechanism + fix sketch

Decode of the signature: qop `F` is the QS "first byte of next instruction" pop (`Q_STR = {1:"F"}` in `sw/emit_suite.py`), and the capture window ends at the second F pop (`v30_core.sv` header). So Family 6 says: **the chip pops the continuation's first byte one cycle earlier than our RTL, at the first idle after the final MEMW; every bus cycle row matches. Our word REP INS is exactly one cycle long at the close.**

Where the cycle lives in RTL: last-element S_INS_W → S_BUSW → `eu_done` → the op_instr branch (v30_eu.sv lines 4260–4265) takes `rep_en → state <= S_EX` — a **+1-cycle close that was assumed by analogy** ("REP takes S_EX's +1-cycle close, like STM/MOVBK — timing is out of scope, arch only" — the comment says it was never fitted). S_EX does nothing for op_str except fall to `retire()` (the 4773 branch is the CW=0 early-out no-op), so it is a pure +1.

The measured law: **word REP INS closes at done (no +1); byte REP INS keeps +1 (clean); REP OUTS keeps +1 both widths (clean).** The microcode loop (029B–029F) is width-blind, so the width dependence is a BIU boundary-pipeline effect — exactly the precedent of the fitted STM/MOVBK close law, which is likewise width/split-conditioned within one micro-routine ("split (odd word) writes close at done directly", line 4244–4252). Family 6 is uniform across IY parity (so it is width-, not split-conditioned), across all CW (so it is anchored at termination, not the loop), and confined to qop/length (so the loop itself is clean). Fix, one line at 4264:

```systemverilog
if (rep_en && !opc[0]) state <= S_EX;   // byte REP INS keeps the +1 close
else                   retire();        // word REP INS closes at done (Family 6)
```

**Pre-registered probe P2 (zero cost, do first):** dump the RTL EU state on the sim's extra row for one F36D CW=1 case. If it is S_EX → the close fix is confirmed; apply and check ~6 cases (even/odd IY, CW=1/2/8, all four prefixes) for bit-identity. If it is S_FIRST stalled on `q_avl` → this is a queue-delivery (q_avl one-cycle-lag) effect instead — STOP and re-characterize; that fix would touch the BIU delivery path and has a much larger blast radius.

## Part 4 — Pre-registered gates (both fixes)

1. **Ledger shrinkage:** Family 5 → 0 of 44,935 (7 forms); Family 6 → 0 of 16,342 (4 forms); three-way re-pass over all 23 strio forms — byte REP INS (x46C) and all REP OUTS must stay at 0.
2. **w0 golden 169000/169000** (verify whether it predates strio; must stay perfect either way).
3. **w1/w3 goldens 1200/1200.**
4. **v20 oracle 3.125M** — caveat: if it cycle-compares V20 REP 6D, the V20 (8-bit BIU) may genuinely differ at the close; adjudicate before reverting the V30-socket-fitted law, don't auto-revert.
5. **wrand:** class-5 census re-run on the standard seeds; DONE-guard invariant unpaired CODE→CODE = 190u ± 10; total census must not regress from 494u.
6. **Savestate scramble regression** (expect no struct change — confirm the final diff adds no flops).
7. **Full v0.3 370-form three-way re-pass: ledger 61,339 → 62 (Families 1–4 only), zero new divergences.**
8. **Quartus 17.1 synth clean** — both edits are plain next-state/wire changes (no struct assignments, per the Phase-R synth-bug rule); note `eu_hold` fanout grows slightly.

## Part 5 — Phasing and risk

**Fix F6 first** (one line, EU-local, only word-REP-INS close path, probe P2 is minutes), gate it, then **F5** (conceptually bigger: eu_hold extension, BIU-visible). Land and gate separately so ledger attribution stays clean. Risks: F5 — the seg-override prefix-window grant location (probe stop-condition above) and the wrand census interaction of eu_hold in the new window (covered by gate 5); F6 — the delivery-mechanism alternative (probe P2 discriminates) and the v20-oracle adjudication caveat. Neither fix touches `eu_rsv_lead`, the class-5 law block, the REP dispatch path, or any savestate struct.

Key files: `hdl/rtl/core/v30_eu.sv` (lines 1342, 2209, 2726–2760, 4260–4265, 5386), `hdl/rtl/core/v30_biu.sv` (line 540), `docs/V20UC.TXT` (µaddrs 0294/0298/02A0/02A4, 008C/00B8/00C4/00D0), `docs/notes/v03_family5_6_characterization.md`.

---
## ADDENDUM (architect fable, revised F6, 2026-07-20)

The first F6 close law (`rep_en && !opc[0]`) was wrong — the extra close row is single-
valued but conditioned on DESTINATION PARITY, not word-vs-byte. Measured on all 40k cases of
the 4 word-REP-INS forms: delta = (continuation qop=F row) − (final MEMW T4 row) is **2 when
DI even (extra close row), 1 when DI odd (close at done)** — 100% per form×DF×cold/warm, NO
CW dependence. The worker's "CW-parity mixed cell" was CW=0 early-outs (elementless, no close
row) polluting the even bins. Clincher identity: DI-odd CW≥1 = 4051+4090+4109+4092 = **16,342
= the ledger count**. The law IS the already-fitted STM/MOVBK split-close law (v30_eu:~4249
`if (opc[0] && eu_addr[0]) retire(); else state <= S_EX;`) which the op_instr branch never
received. Uses eu_addr[0] (physical write-address parity, valid at eu_done; == initial-DI
parity, loop-invariant under ±2 stepping). Byte stays S_EX (never splits); word-aligned stays
S_EX (protects DI-even). OUTS branch untouched (even-port constraint => no split final IOW in
v0.3; follow-up if odd-port word OUTS is ever emitted).

---
# F5 FINAL DESIGN: decision-time-scoped T3-eval veto (not a raw onset move)

*(Architect (fable), 2026-07-20, third iteration after the eu_hold claim experiment hit stop condition #2. Intended landing: addendum to docs/notes/v03_family5_6_law_design.md. Extraction evidence: scratchpad f5_window.py / f5_window2.py.)*

## 1. What the goldens say (new chip-side measurement, all seven forms)

Extracted the chip's dispatch-window bus signatures (rows from opcode-pop−1 to the first element-access T1) for every strio single form, cold and warm, plus the classic-string calibration forms. Every population is 100% signature-pure:

| population | signature (pop-relative) | chip's in-window CODE grant? |
|---|---|---|
| 6E/6C/6D/6F cold (5000/5000 each) | pop@fetch-T3 → T4, Ti, elem-status, T1 | **NO** (the deferral) |
| prefix cold, T2-pop class (~2500/form) | pop@fetch-T2 → T3, T4, Ti, elem-status | **NO** — the divergent prefix cases |
| prefix cold, T4-pop class (~2500/form) | pop@fetch-T4, successor CODE T1 at pop+1 (decided pre-pop), elem rides behind | **YES** — never divergent |
| warm-1 (~2500/form) | CODE status at pop+0 or pop+1 (TI grant), T1 pop+1/+2, elem back-to-back after it | **YES** — the hold killed these |
| warm-2 (~2500/form) | idle, elem-status at pop+2/+3 from TI | none due |
| **A4/AA/AC cold (5000/5000, calibration)** | pop@fetch-T3 → **successor CODE granted at T4**, elem behind it | **YES** |

The A4-vs-6E cold contrast is the microcode made visible in silicon: same pop position (fetch T3), same queue state; the only difference is INS/OUTS's µline-1 bus request (V20UC 0294/02A0) versus MOVS's µline-2 request (008C) — one µcycle of request-onset flips the successor-fetch decision.

**The unified chip rule (all populations, zero exceptions):** every fetch-grant decision is vetoed iff the strio-single's µline-1 request is visible at the *decision instant*; the request becomes visible at **pop+1**. Grant decisions sit at: pop−1/pop+0 for TI grants whose status row is pop+0/pop+1 (warm-1, warm-2-prefix, cold-prefix-T4 — all granted, all < pop+1), and at the T4-entry boundary (= pop+1 for a pop@T3 fetch, pop+2 for pop@T2) for back-to-back successors (cold plain, cold-prefix-T2 — all vetoed, all ≥ pop+1).

## 2. Why the raw onset move is rejected

**Why warm MEMR is on time with `eu_req` rising at S_RSV:** warm element accesses are serviced by decision points at/after pop+2 — the TI `want_eu` path, or `defer_t4`/T3-eval `want_eu` of the warm TI-granted CODE fetch — and S_RSV's `eu_req` (pop+2) is already visible there. The *only* eval the RTL misses is the opcode fetch's own completion eval (`req_t3_eval`, firing at pop+0 for pop@T3, pop+1 for pop@T2), which exists only when the pop rides a live fetch — i.e., precisely the cold configurations.

**Why raising `eu_req` at S_DEC/S_FIRST would re-break warm:** at w0, `eu_req` and `eu_hold` are interchangeable inside `prefetch_ok`'s `!(eu_req || eu_hold)` (v30_biu.sv:540), and `prefetch_ok` feeds **both** `req_t3_eval` (via `pick_any`, :929) and `req_ti_plain` (via `pick_plain`, :926). The warm-1 TI grants stage at pop+0/pop+1 (`stage_commit` at ST_TI, delivering T1 one cycle later) — an early `eu_req` kills them exactly as the hold did. The RTL's TI path *decides one cycle later than the chip's* (chip decision pop−1 → status pop+0; RTL stage pop+0 → same T1), so any pop-cycle-wide suppression collides with grants the chip had already committed pre-pop. Additionally a moved `eu_req` edge shifts `eu_req_p1/p2` and every fitted law gating on `eu_req && !eu_req_p1`. The onset move is strictly dominated. **No cold conditional is needed** — the correct rendering is a veto scoped to the one decision point whose chip-equivalent instant is ≥ pop+1: the T3-eval prefetch grant.

## 3. The exact design

**v30_eu.sv** — one new output, pure combinational (Moore state + q_byte peek), zero flops, no savestate change; place beside `eu_rsv_dhi`/`eu_rsv_lead` (~line 1633) with the naming idiom of the reservation-class hints:

```systemverilog
// strio-single µline-1 request lead (V20 µcode 0294/02A0: INS/OUTS singles
// issue their bus request on the routine's FIRST µline; MOVS/LODS/STOS/SCAS
// issue on µline 2 - measured cold A4 vs 6E, 5000/5000 each). Visible to the
// BIU's fetch-successor completion eval only (T3-eval); REP forms (3-µline
// preamble, 0298/02A4) and classic strings must NOT assert.
assign eu_rsv_strio = ((state == S_FIRST) && q_pop && !rep_en &&
                       (q_byte[7:2] == 6'b011011)) ||      // 6C-6F, pop cycle
                      ((state == S_DEC) && !rep_en &&
                       (op_instr || op_outstr));            // dispatch cycle
```

**v30_biu.sv** — consume it at exactly one slot; `req_ti_plain`, `prefetch_ok` itself, all eval_ext/law paths, `eu_hold`, and every history pipe stay untouched:

```systemverilog
// T3-eval-scoped pick: the completion eval's successor-fetch grant sees the
// strio µline-1 reservation (its chip decision instant is T4-entry >= pop+1);
// TI grants (chip decision pop-1/pop+0) are exempt - warm-1/warm-2-prefix
// populations, chip-granted, must survive (measured f5_window2).
wire pick_t3     = want_half2 || want_eu || (prefetch_ok && !eu_rsv_strio);
wire req_t3_eval = eval_at_t3 && pick_t3;
```

plus, in the ST_T3/TW branch: the `SLOT_CHK(slot_fire == pick_any)` at :1453 and the `if (pick_any) ... else if (...) defer_t4` priority chain at :1460–1465 change `pick_any` → `pick_t3` (so a vetoed eval stages nothing and arms nothing; `eu_req`=0 there, so the `defer_t4` arm is naturally false). The T4 flush slots (`req_ff_t4`, `req_t4_flush_staged`) keep `pick_any` — flush contexts, unreachable in these windows. Port plumbing through v30_core.sv. No new flops → no `v30_ss_pkg` change, no SS_VERSION bump.

**Why each population comes out right:** cold plain — T3-eval at pop+0 (S_FIRST pop, veto term 1) stages nothing; T4→TI; S_RSV's real `eu_req` blocks TI prefetch from pop+2; `want_eu` services the MEMR — the identical cold service path the hold experiment already proved **bit-exact** (the hold's cold effect was a superset of this veto; in cold the bus is in T3/T4 at pop/pop+1, so no TI grant existed there for the hold to wrongly kill). Cold-prefix-T2 — T3-eval at pop+1 (S_DEC, term 2) vetoed ✓. Cold-prefix-T4 — successor decided at pop−1, veto not yet asserted ✓ (stays granted, as the chip does). Warm-1/warm-2 — TI path untouched ✓. Classic strings — `q_byte` ≠ 6C–6F, never asserts ✓. REP — `rep_en` excludes ✓. Under uniform w1/w3 the veto is structurally inert: `eval_at_t3` requires ready at two consecutive edges, which a waited opcode fetch never has — the T3-eval slot doesn't exist there. Under wrand it can fire only at zero-wait strio-single opcode-fetch evals; the census adjudicates (do NOT pre-extend to the eval_ext window — no data).

## 4. Probe P3 (sim-only, before any tranche) with stop conditions

Cycle-dump (`eu_rsv_strio`, slot_id/slot_fire, EU state, pick_t3) plus full-trace diff on: cold 6E/6C/6D-odd/6D-even/6F; cold 26.6E both phase classes (select by pop-row tstate T2 vs T4); warm-1 and warm-2 of 6E and 26.6E; cold+warm A4 and AA controls; F36E CW=1 REP control. Verify: (a) the veto asserts only at {pop, pop+1} of strio singles; (b) cold = chip bit-identical; (c) warm and all controls = **baseline-RTL bit-identical** (diff against pre-fix traces, not just chip). **STOP conditions:** any warm case deviating from baseline (⇒ an in-corpus warm T3-eval grant exists — re-characterize, do not widen); any cold case still granting the doomed CODE (⇒ a cold TI-grant variant — report its stage cycle, do not extend the veto to TI without redoing the decision-time analysis); any A4/AA/REP control deviation.

## 5. F5 gate (pre-registered)

1. Family 5 → 0 of 44,935 across the 7 divergent forms; three-way re-pass over all 23 strio forms.
2. Flip-guards, all bit-identical: warm populations (~20k), cold-prefix-T4 classes (~7.5k), classic strings A4–AF + 26.A4/2E.A5/36.A6, all REP strio forms, byte/word both.
3. w0 169000/169000; w1/w3 1200/1200 (structurally invulnerable per §3, run anyway); v20 oracle 3.125M.
4. wrand class-5 census: total must not regress from 494u; DONE-guard unpaired CODE→CODE = 190u ± 10.
5. Scramble regression; confirm final diff adds no flops. Quartus 17.1 synth clean (plain wires; one new EU→BIU port).
6. Full v0.3 370-form three-way re-pass: ledger 44,997 → 62 (Families 1–4 only), zero new divergences.

Key locations: `v30_eu.sv` :1633 (new assign site), :2209/:2257 (S_FIRST/S_DEC), :1342 (S_RSV eu_req — untouched); `v30_biu.sv` :540 (prefetch_ok — untouched), :926/:929 (req_ti_plain/req_t3_eval), :1453/:1460 (T3 dispatch chain).
