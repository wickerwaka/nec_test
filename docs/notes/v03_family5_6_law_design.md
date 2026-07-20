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
