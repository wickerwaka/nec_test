# Ledger tail-family campaign — law derivations + fix designs (F1, F2, F4a/b/c)

*Architect (fable), 2026-07-22. See the architect's full deliverable in the coordinator conversation; this file is the worker's execution copy, verbatim content. Intended landing: docs/notes/v03_tail_family_law_design.md. RTL refs at master f8a9a55. NONE of the fixes adds a flop — no savestate-v2 map change, no SS_VERSION bump; standing SS regressions run as usual.*

## Headlines
1. **F1 (0F31 ×25)**: full-word aligned insert (offset==0 ∧ length==16) skips the ES:IY RMW read. The 0F39 imm form ALREADY has this branch (v30_eu.sv:3498 "full-word insert: NO read"); the 0F31 reg form never received it. V20UC corroborates (offset-0 JMP Z at µ031A before the ES MEMR at µ031B). Fix = extend the existing branch + one fitted delay constant.
2. **F2 (BCD-4S ×24)**: **V30 accumulates Z (and P=Z) over the ADJUSTED (written) bytes; V20 over the PRE-adjust raw bytes.** Both measured polarities pin this uniquely; the RTL's own comment (:1104 "Z accumulates on this, not on the adjusted result") confirms it implements the V20 stage. One-line fix + computed oracle-exception predicate. Plus F2b: the ×3 cyc cases = driven sibling-lane formula refit (bus-image only).
3. **F4a (FF.3 ×1)**: sequential multi-word operands step their 16-bit offset mod 64K. Same principle as the fitted intra-word eu_wrap (fz494), one level up. Helper function at 6 enumerated sites; IVT site deliberately linear.
4. **F4b + F4c: STOP — PROVENANCE FIRST.** Both golden vectors show the chip operating on memory that CONTRADICTS the JSON's initial.ram at the EA, with the same word 0x63C0 as execution-time operand in two unrelated forms, both EAs abutting the code bytes. Suspected sticky/displaced RAM seeding — 3rd instrument-failure occurrence (after sticky-WRAND ×2). The F4c "PF-only" puzzle dissolves under this (RTL-from-JSON computes PF=1 on 0xA4A6; chip PF=0 on 0xC062; all other flags coincide). NO RTL work until the provenance probe reports.

## F1 fix (EU-local, Quartus-safe)
In S_IE_SET reg-form arm (~:3438):
```systemverilog
if (o == 4'd0 && l == 5'd16) begin
    // F1: full-word aligned insert - chip skips the ES:IY RMW read
    // (V20UC 0318-031B offset-0 Z-branch; 0F39 imm twin at :3498)
    eu_wdata <= awn;                 // mask FFFF: field = whole AW image
    ie_dly   <= 12'(IE_W16R);        // NEW constant, fitted on the 25 goldens
end else begin
    ie_dly <= (o == 4'd0 && ss < 6'd16) ? 12'(IE_R1D0) : 12'(IE_R1D);
end
```
Tail wnext mux (:3473) gains: `(ie_ins && !ie_immf && o==0 && l==16) ? S_IE_WR`. Downstream = existing 0F39-proven machinery (S_IE_WAIT → S_IE_WR → S_IE_WRW retire, rf[7]+=2, psw <= ie_psw_ins). Fitted constant: measure chip's lone-MEMW position across the 25 (anchor = mrm pop; check odd-IY members for a split adjustment). Prior: with-read s==16 writes at R1+41; imm IEI_W16 = imm+34.

**Probe P-F1**: cycle-dump + trace diff on 4 full-pattern (even+odd IY), both half-pattern (2333-class), controls: off0/len<16, off>0/len16, word-crossing s>16, 0F39 off0/len16 (bit-identical), EXT 0F33. STOP: (a) any control deviates (scope leak); (b) one constant (+split adj) can't make all 25 bit-identical (queue-state dependence → BIU component; report residuals, no EU state chasing); (c) half-pattern shows a different mechanism.

**Gate**: 25→0 three-way; flip-guard ~400 clean 0F31 incl. 149 word-crossing + off>0/len16; 0F39/0F33/0F3B 10k each 0 div; w0/w1/w3; v20 oracle (0F31 arch 100% — skip changes no arch result); wrand census ≤494u/190u±10; SS G1′+scramble+round-trip (no flops — verify diff); Quartus; full v0.3 re-pass zero new.

## F2 fix
**F2a (one line, :3694)**: `a4_z <= a4_z && (s[7:0] == 8'h00);  // V30 Z/P stage = ADJUSTED bytes (V20 = prez)`. bcd_add8/bcd_sub8 NOT modified (result lanes silicon-confirmed; prez stays, unconsumed). S_A4_END P=Z mirror untouched.

**F2b (sibling-lane refit, ×3 cyc)**: write-row DATA lane diff with matching final RAM = the driven sibling image (mem_op[15:8] formula at :3696-3698). Candidates in order: sibling picks up wrap/second-rail carries `fire` misses; sibling uses adjusted rather than raw carries; off-by-one in the −1 under sibx. Probe P-F2b: dump (a4_src, eu_rdata, s, mem_op) + golden write lanes for idx 1209/4493/7815 + 10 passing carrying-add controls; fit; regression = every passing 0F20/0F22 write-row lane bit-identical. STOP if no single expression covers 3+regression (state history → report, no flops).

**F2.4 oracle amendment (the crux)**: V30 wins in RTL. v20 oracle 4S gate amended via COMPUTED exception predicate (Python lane mirror computes Z/P under both stage laws per vector; agreeing vectors keep hard 100% V20 requirement; differing vectors asserted to match the V30 prediction). idx 652 MUST fall inside the predicate by construction — pre-registered falsifier; if not, the law is wrong, stop. Report predicate fire-count over v20 4S files. Document in oracle notes + memory; upstream V30 contribution emits V30 behavior (this fix is a prerequisite).

**Gate**: 24→0 (0F26×10, 0F22×5, 0F20 arch×6 F2a + cyc×3 F2b); flip-guards all passing 4S bit-identical incl. cycle rows + near-miss controls; v20 oracle 4S 100% under amended predicate, non-4S untouched 100%; standing gates; zero new divergences.

### F2 resolution (L1/L2, landed) — the unified law U

The original one-line "V30 Z over the fully-adjusted result byte (`s[7:0]==0`)" law was
**incorrect** (it zeroed no form and regressed the suite — flip-guard caught it). It was
reverted, the residue partition characterized (every candidate over-predicted zero — one-sided
false-zeros on carry/adjust bytes), and the architect derived the **unified law U** (not fitted):

> At the µline-2 (ADJD/W) sample, the per-byte Z term tests the 9-bit digit-serial intermediate
> **`{ripple_pending, hi_raw_c1, dlo_adjusted} == 0`**, where `ripple_pending` is the low-adjust's
> carry/borrow into the high digit that µline 3 has not yet consumed.

Per-direction collapse (provable over the whole domain, not fitted):
- **SUB/CMP**: `ripple_pending == wrapb`, and `wrapb=1 ⇒ dlo = dlo0+10 ≠ 0`, so the rail bit is
  identically vacuous ⇒ U ≡ **`(dec[3:0]==0) && (dlo==0)`**. `dec[3:0]` is the µ-intermediate
  (raw high nibble, raw low borrow `c1` only, before `wrapb`/`-6`); it includes `wrapb` where
  `dhi0` does — do NOT "fix" it to `dhi0`. All 15 wrap divergents have `c1` activity, so a naïve
  `c1`-activity gate is dead on sub; it is the *ripple* that gates.
- **ADD**: `ripple_pending == c2`, and the conjunction collapses algebraically
  (`c2=0 ∧ dlo==0 ⇒ dlo0==0 ⇒ c1=0 ⇒ hi_raw_c1==0 ⇒ a_hi+b_hi==0`) ⇒ U ≡ **`(a + b + cin) == 9'd0`**
  (the raw 9-bit byte sum literally zero). The chip never calls an add byte zero if anything
  happened. Validated 0/10000 on 0F20 (KILL-SHOT: 0 chip-Z=1 cases with a nonzero byte; caveat:
  chip-Z=1 count is 0 in v0.3, so the law is exercised only in the Z=0 direction — the Z=1
  direction is µcode-grounded, not suite-tested).

RTL: `bcd_add8`/`bcd_sub8` each gain a top-of-bundle `zq` at `s[13]`; consumer `a4_z <= a4_z && s[13]`.
No new intermediate signals, no flop, SS map unchanged. Landed as two attributable commits
(CMP/SUB, then ADD); F2b (×3 cyc) is a separate landing (L3).

**Bookkeeping — why the fallback sweep could not find U:** the pre-registered fallback space
(quantity × accumulation) was correctly designed but *provably* could not contain U — U includes
the **rail bit** (`ripple_pending`/the 9-bit carry), not a rendering of the digit pair, and the
sweep enumerated only digit-pair renderings. The residue partition's one-sided structure
(false-zeros confined to activity bytes) is exactly what identified the missing dimension. The
idx-652 falsifier premise earlier was a digit-level mis-reading corrected by the 130 CL=1 byte-
level chip cases — recorded per the provenance discipline.

*Mechanism (offered, not load-bearing):* the µ-ALU Z line appears to test the whole digit-serial
intermediate register including the carry rail, at the ADJD/W µline before µline 3 consumes the
ripple — which is why "the digits read zero but a carry/adjust happened" reads non-zero.

## F4a fix
```systemverilog
// F4a: sequential multi-word operands step the 16-bit OFFSET mod 64K
function automatic [19:0] ea_step2(input [19:0] a, input [1:0] sg);
    logic [15:0] off;
    off = a[15:0] - {sr[sg][11:0], 4'h0};
    ea_step2 = {sr[sg], 4'h0} + {4'h0, off + 16'd2};
endfunction
```
Sites (all `eu_addr + 20'd2` — grep-verified exhaustive): :4405 (FF/3,/5 far ptr word 2 — the witness), :4442 (CHKIND upper bound), :4476 (LDS/LES seg word), :3559 (EXT/INS word-1 read), :3625 (INS split w0-write→w1 read), :3639 (INS w1 access). :5159 IVT = physical page-0, deliberately linear (comment why). Identity outside off∈{0xFFFE,0xFFFF} → structurally zero blast radius. Seg-liveness audited per site (base unchanged between accesses at all six). No flops.

**Probe P-F4a**: directed TB battery per consumer, offset ∈ {0xFFFC..0xFFFF} (0xFFFD composes split-wrap+step-wrap); global `ifndef SYNTHESIS` assertion: every EU access's (eu_addr − seg base) fits 16 bits — catches missed consumers globally. Golden diff idx 7685 bit-identical (wrapped reads at 414319→348784/5/6). STOP: assertion fires outside the six sites (missed consumer — extend table, re-review); or 7685 cycle rows still deviate post-fix (timing component — re-characterize).

**Gate**: 7685→0 three-way; full v0.3 zero new; w0/w1/w3; v20 oracle; wrand; SS; Quartus. BOOKED (gating the LAW's generality, not landing): directed silicon wrap mini-tranche — FF.3, FF.5, C4, C5, 62, 0F31, 0F33 ~40/form, offsets 0xFFFC-0xFFFF, socket, mechanized rig guard. Any post-fix tranche divergence = stop-and-characterize, not refit.

## F4b/c provenance probe (NO RTL until it reports)
**Evidence**: 83.5/8683 — JSON initial.ram EA word 0xA4A7 but chip consumed 0xC063 (split MEMR T2 lanes 0x63C0/0x83C0), wrote 0xC062 = 0xC063−1, self-consistent; 0F1B/3917 — JSON EA word 0x1189 but chip did CLR1 bit-5 on 0x63C0 (already clear, wrote back unchanged). Same 0x63C0 in two unrelated forms; both EAs abut code bytes (EA+2/EA+3 = code start) — adjacency/claim-guard displacement signature. Rule generalizes: **a chip read returning bytes the vector places elsewhere is a provenance alarm, not a law to fit.**

**Step 0 (sim, minutes)**: check_core data dump on 8683/3917 — what did the RTL read/write/flags? Expected: 8683 reads 0xA4A7 writes 0xA4A6 PF-only flag diff; 3917 reads 0x1189 writes same. If RTL reads 0xC063/0x63C0 instead → hypothesis DEAD for replay side → branch B. Also resolve where "matching memory result 0xC062" claim came from.
**Step 1 (software)**: seed-consistency sweep — reconstruct execution-time memory from golden read rows for all 62 + 200 passing sample, diff vs initial.ram. Expected flags: 3917+8683 only (F1 structurally immune — stale operand would corrupt written field; F2 coherent 15/15; 7685 manually verified sane). Any additional flagged case joins F4bc. Grep emit_suite/gen_case for 0x63C0 as generator constant + adjacency/claim guards near CS:IP.
**Step 2 (board, one session, mechanized rig guard)**: re-emit both with POST-SETUP RAM READBACK before execution. Outcomes: readback≠JSON → instrument failure #3 CONFIRMED (fix setup, re-capture, VOID or re-characterize; READBACK VERIFICATION MECHANIZED into emit_suite per house rule); readback==JSON + chip still displaced → extraordinary genuine behavior, directed geometry sweeps, no fix from n=2; readback==JSON + re-capture matches RTL → transient corruption, VOID, re-emit.
**Branch B (only if step 0 kills it)**: F4c = real flag hunt (discriminators pre-computed: parity(0x63)=1 and parity(0xC0)=1 both fit; S=1 rules out whole-flag-set-from-swapped-image; anchor :5087-5088, flags+write from same mem_op same NBA cycle → PF-only with matching RAM needs post-write clobber; enumerate psw writers after S_WREQ). F4b branch B: re-characterize vs CLR1 µcode (µ02C0-02C3, unconditional 4-µline RMW — NOT F1-kin under any branch).

## Phasing
| Phase | Content | Size | Depends |
|---|---|---|---|
| L0 | F4bc probe steps 0-1 (software) | S | — |
| L1 | F2a + oracle predicate + gate | S+M | — |
| L2 | F1 skip + fitted constant + gate | M | P-F1 |
| L3 | F2b sibling refit + gate | S | P-F2b |
| L4 | F4a wrap helper + battery + gate | M | — |
| L5 | F4bc board session (readback re-capture) + verdict | S board | L0 |
| L6 | F4a wrap mini-tranche (silicon confirm) | S board | L4; share L5 session |

Ledger: 62 = 25(F1)+24(F2)+10(F3, in flight separately)+3(F4). Target after campaign: 0 + F4bc residue (expected 0).

Risks: F4bc readback logistics (readback BEFORE execution); F2 predicate drift (generate from the maintained Python lane mirror + idx-652 falsifier); F1 constant queue-dependence (stop b, low probability); F4a unwitnessed consumers (assertion probe + mini-tranche); nothing touches BIU arbitration/class-5/strio arms/savestate-mapped flops.

Anchors: v30_eu.sv :3428-3475/:3498/:1104/:1122/:1162/:3690-3698/:3750-3756/:1293-1300/:4405/:4442/:4476/:3559/:3625/:3639/:5159/:5087-5088; V20UC µ0318-0343 (INS), µ02CC-02EB (4S), µ02C0-02C3 (CLR1); emit_suite.py (seeding audit); v0.3 idx 3917/8683/7685.
