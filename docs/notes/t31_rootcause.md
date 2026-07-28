# Task #31 residue — per-bug root-cause reports

Root-cause of the 22-seed genuine value-bug residue (`sw/t31_residue.py`), one
entry per confirmed bug. Fixes only after coordinator review, per family.

## k=6475 — the LEA mod=11 stale-EA latch, in a RAW seed (NOT a new bug)

**Verdict:** raw, wrand wmax=2. A single MEMW to in-image 0x3efe: chip stores
0x469c, fabric 0x27cc; every other write in the 4063-row trace is byte-identical.

**Root cause (hand-decoded along the executed path):**
- Execution runs the register-preamble at 0xff00 (`MOV DI,0x9465` among the reg
  loads) then far-jumps to 0:0x500 and runs linearly.
- At **PC 0x502 the instruction is `8d fd` = LEA DI, (modrm mod=11, rm=101)** —
  an ILLEGAL register-form LEA. This is the **task #30 stale-EA-latch class**:
  the chip loads its stale EA-offset latch into the dest reg (DI); the behavioural
  core reproduces this exactly only in moffs contexts, residue otherwise.
- DI is written by NOTHING else before the `57` = **PUSH DI at PC 0x51d**, which
  stores DI to SP-2 = 0x3efe. So the push exposes the latch: chip DI = 0x469c
  (stale EA latch), fabric DI = 0x27cc (core residue model). The arch diff is
  CONFINED to DI (the LEA dest) - exactly the `lea_mod3` accept criterion.

**Why it surfaced as FUNCTIONAL (not KNOWN_ACCEPTED/lea_mod3):** the `lea_mod3`
accept rule is **soup-only** - it needs the arch_dump (12-register store stub)
AND the `lea_mod3_pos` provenance, both produced by gen_soup. gen_raw emits none
of that, so a raw seed that RANDOMLY contains an LEA mod=11 (0x8d + a mod=11
modrm from the random byte stream) hits the known residue and is not covered ->
surfaces as a FUNCTIONAL value divergence. This is a **classification/coverage
gap, NOT a new RTL bug and NOT a regression** of the task #30 fix (the core no
longer hangs; it loads its residue value exactly as task #30 designed).

**Proposed disposition (NO RTL change):** extend LEA-mod=11 residue coverage to
raw tier. Options, in preference order:
1. **Raw-aware lea_mod3 acceptance** - detect an executed LEA mod=11 in a raw
   seed (scan the seed / executed stream for 0x8d with a mod=11 modrm at an
   instruction boundary) and accept iff the divergence is confined to that LEA's
   dest register (the same strict fail-safe as the soup rule). Needs a raw-path
   provenance/confirmation that does not rely on the arch_dump.
2. **Scrub LEA mod=11 in gen_raw** - neutralise 0x8d+mod=11 in the raw scrub pass
   (like the existing pair0f/halt/poll scrubs), so raw seeds never exercise the
   known residue. Simpler, but reduces raw breadth over a known class.
3. Book raw LEA mod=11 as an explicitly accepted static class.

Recommend (1) if a robust raw-side LEA-mod=11 confirmation is cheap, else (2).

**Sub-family sizing (linear ilen decode of the executed payloads):** k=6475 is
NOT a singleton - a small **raw mod=11 stale-latch sub-family** exists (the
register-form of the mem-only ops, all task #30 class):
- **k=6475** LEA (0x8d) mod=11 -> DI  (hand-verified)
- **k=3075** LDS (0xc5) mod=11 -> DI  (linear-decode; needs hand-confirm)
- **k=8398** BOUND (0x62) mod=11 -> DX (linear-decode; needs hand-confirm)

Caveat: k=3075/k=8398 are heuristic (linear decode assumes in-order flow). Note
that task #30 characterised BOUND/LES/LDS mod=11 as HALTing on BOTH chip and core
(park correct) - so if k=3075/k=8398 genuinely produce a VALUE divergence rather
than a park, that either contradicts the task #30 whitelist (a residue path the
whitelist missed) or the linear decode mis-identified the store source. Hand-
confirm both before the disposition; the fix in either case is raw-tier coverage
of the mod=11 stale-latch class, sized ~3 seeds (not 22).

So the value-bug residue partly COLLAPSES again: ~3 seeds are the known task #30
mod=11 stale-latch class (raw coverage gap), leaving the 0x3fe0 soup cluster (9,
a distinct MOV BP,0x3fe0 + ENTER/stale-latch mechanism - decode in progress) and
~10 singles for the remaining root-cause pass.

## Whitelist question (k=3075 LDS, k=8398 BOUND) — RESOLVED: no contradiction

Coordinator flagged the task #30 park-whitelist (BOUND/LES/LDS mod=11 HALT on
both chip and core) as possibly contradicted by k=3075/k=8398. Resolved
rigorously (ruling 2a hand-trace + 2b board-verify):

- **k=8398 (BOUND) = MIS-DECODE.** The heuristic's BOUND at 0x50e is NOT on the
  path to the divergence: first_bad=160, executed PCs reach only 0x506. Hand-
  decode from 0x500: `8d 3b`=LEA DI,[BP+DI] (valid mem-form, mod=00), `8f fe`=
  POP SI, `c1 46 0a`=ROL word[BP+0x0a]. The divergence is an early read-EA split
  (chip reads out-of-image 0x6bd0a, fabric reads stack 0x3f00) - not BOUND
  mod=11. Revisit as a single.
- **k=3075 (LDS) = MIS-ATTRIBUTION.** `c5 fb`=LDS DI,mod=11 IS on the path (0x50c,
  hand-confirmed), but first_bad=851 is DURING the preceding ENTER (0x508,
  nesting=125), which executes ~row 340-2440 - LONG before the LDS would execute
  (~2440). The divergence is the ENTER, not the LDS.
- **Board-verify (fresh directed chip probe): LDS mod=11 still PARKS.** Clean
  `c5 fb`: chip stops fetching at row 157, no done = PARK (matches the tranche).
  Post-ENTER context (`ENTER 0x1c,1 ; c5 fb`): chip parks at row 176, no done -
  NOT context-dependent. Controls: LEA mod=11 and a NOP sled both run to done.

**Conclusion: the task #30 whitelist STANDS** - LDS/BOUND/LES mod=11 park on the
chip in both the clean and the post-ENTER context. NOT the fourth vacuity
instance. Both heuristic hits were linear-decode artifacts, correctly ruled out
by hand-tracing the executed path.

Consequence: **k=6475 (LEA mod=11) is the SOLE genuine mod=11 stale-latch in the
residue** (a singleton, not a 3-member sub-family). The option-1 raw-aware
`lea_mod3` acceptance therefore covers LEA (0x8d) mod=11 ONLY (LDS/BOUND/LES
park => no value divergence => nothing to accept).

## 0x3fe0 cluster (9 soup) + k=3075 — ENTER lead NOT confirmed; still open

All 9 cluster seeds carry `MOV BP,0x3fe0` + ENTER, and k=3075 diverges during a
nesting-125 ENTER, so ENTER looked like the shared mechanism. BUT a directed
chip-vs-fabric ENTER probe (framesize/nesting 0..31, BP=0x3fe0) shows NO
divergence - ENTER is correct in isolation. So the cluster mechanism is
context-dependent (INTO/OF interaction, LEAVE, stack state, or waits), not plain
ENTER. Decode continues as the next residue family.

## ENTER nesting-level mask — CONFIRMED core bug (6 raw seeds) — RTL, report-first

Directed board probe (ruling 2, sanctioned characterization): `MOV BP,0x3fe0 ;
ENTER 0x0000,nest`, chip vs fabric, counting stack-walk pushes.

| nesting | chip pushes | fabric pushes |
|---|---|---|
| 1,2,...,31 | nest+1 | nest+1 (MATCH) |
| 32 | 33 | 1 |
| 33 | 34 | 2 |
| 63 | 64 | 32 |
| 64 | 65 | 1 |
| 125 | 126 | 30 |
| 255 | 256 | 32 |

**The V30 chip does NOT mask the ENTER nesting level** - it walks the full 8-bit
count (pushes = nesting+1, up to 256). **The fabric core MASKS nesting mod 32**
(80186/286 semantics): fabric pushes = (nesting & 0x1f) + 1. For nesting >= 32
they diverge. Chip is the oracle => **the CORE is WRONG**.

Explains 6 raw residue seeds (all ENTER nesting >= 32): k=3075(125), k=3897(123),
k=4677(239), k=5586(75), k=5699(186), k=6436(60). (k=3075 was the LDS red-herring
- its real divergence is this ENTER, mid-nesting-125-walk, exactly where fb=851
sits.)

**Proposed disposition: RTL fix** - remove the mod-32 mask on the ENTER nesting
byte in the core's ENTER microcode/state machine; use the full 8-bit count like
the chip. This is a genuine behavioural bug (V30 differs from 186/286 here), and
the mod3_illegal-style vacuity applies: no existing green test exercises ENTER
nesting >= 32. Gates on fix: a directed ENTER-nesting tranche (0..255 x contexts,
chip goldens), cycle+push-count exact; standing sweeps; coverage artifact per the
LEA precedent. Root-cause report FIRST (this touches RTL) - awaiting review.

## 0x3fe0 soup cluster (8, nesting 2-3) — ENTER-adjacent, still OPEN

The 8 soup cluster seeds show an ENTER push-count divergence at LOW nesting
(k=862 nesting=3: chip 4 pushes, fabric 3), but a directed low-nesting ENTER
probe MATCHES chip=fabric - both clean (w0) AND with wrand (wmax 2/7), nesting
1..5. So the cluster divergence is context-dependent (preceding instructions,
the walked frame-pointer memory content, or a different instruction than the
ENTER), NOT reproducible in isolation. Distinct from the nesting-mask class.
Remains open for the next characterization pass.

## ENTER nesting-mask FIX LANDED (task #31, RTL)

Fix (v30_eu.sv S_PREP_L): the nesting level is loaded FULL 8-bit -
`a4_k <= q_byte[7:0]` (was `{3'd0, q_byte[4:0]}` - the mod-32 mask), and the
level==0 / level==1 dispatch checks use `q_byte[7:0]`. The 8-bit copy loop
(a4_cnt 1..a4_k-1) already handled the full range; only the load was masked.

**Savestate: NO map change.** a4_k and a4_cnt are already `reg [7:0]` and already
SS-mapped at full 8-bit width (SSA_E_A4_K / SSA_E_A4_CNT). The bug was purely the
5-bit mask on the value loaded into the already-8-bit flop, so no flop widening,
no SS_VERSION bump. ss_lint PASS (203 symbols, unchanged).

**Verification (TB rebuilt):** the fixed core now pushes nesting+1 for the whole
0..255 range (was (nest&0x1f)+1): nest 32->33, 63->64, 125->126, 255->256, all
matching the chip. nest=255 (256 pushes) fits the 4200-row w0 window (~4199 rows,
verified). The 6 residue seeds' ENTER divergence disappears (k=4677/6436 SUCCESS,
k=5586/5699 TIMING; k=3075/3897 reduce to the pre-existing chip-vs-TB startup
delta at row ~11, unrelated to ENTER).

**Tranche:** tests/v30/enter_nesting/ - 512 chip goldens (nesting 0..255 x 2
BP/stack contexts, sw/char_enter.py, EMIT_USE_CORE socket truth). Standing gate
sw/check_enter_nesting.py replays each in the TB and asserts the stack-region
ENTER walk (push/copy count + ordered addr/data stream) matches the chip.

Quartus/reflash: the fabric on the board is UNCHANGED (masked). The fix rides the
NEXT Quartus batch; no reflash needed until a board-comparison campaign wants the
fixed fabric. TB replay (chip goldens) is the gate until then.

## 0x3fe0 cluster — MECHANISM: fabric drops the ENTER initial PUSH BP

Rigorous re-analysis (campaign captures = chip vs board-fabric, no startup delta;
`sw/t31_residue.py` + per-seed walk). All 8 cluster seeds (k=862/2398/4024/6407/
7542/9124/9312/9440, ENTER nesting 1-3) show ONE mechanism: **the fabric core's
ENTER omits its initial PUSH BP** - the chip pushes BP (=0x3fe0 from the seeds'
`MOV BP,0x3fe0`) to SP-2, the fabric skips straight to the frame-pointer walk. The
"constant chip=0x3fe0 store" signature IS that skipped PUSH BP. Example k=862
(nesting=3) row 316: chip does MEMW 0x3efc=0x3fe0 (PUSH BP) while the fabric has
already fetched past to 0x512 - one push short.

DISTINCT from the nesting mask (these are nesting<32, provably mask-invariant;
the fix does not touch them). This is a SECOND ENTER bug.

RTL location: v30_eu.sv line ~3083 `issue_push(rf[5])` (PUSH BP, issued at the
framesize hi-pop; acceptance tracked by prep_acc + held in S_PREP_L via
`eu_req=!prep_acc`). The push is dropped under a context-dependent condition.

TRIGGER: NOT isolated. Directed repros of the local sequence (FPU-ESC / PUSH DX /
REP DS: TEST / MOV BP, all preceding an ENTER) MATCH chip=fabric - even the full
k=862 preamble in isolation matches. The full k=862 image reproduces the skip
(the campaign capture proves it), so the trigger is accumulated machine/BIU/queue
state not replicated by a short directed program. It reproduces at w0 too (NOT
wait-triggered; k=862 is fixed w2, corrected from an earlier misread).

NEXT: delta-debug minimize a cluster seed's FULL image (NOP instructions while the
PUSH-BP-skip persists, chip=oracle) to isolate the trigger, then RTL root-cause
the BP-push-drop condition. Proposed as a second ENTER RTL fix (root-cause report
first). Likely a preceding-bus-op / queue-fill interaction with the hi-pop BP
push issue.

## 0x3fe0 cluster — ROOT-CAUSED + BOARD-CONFIRMED: ENTER drops PUSH BP under WAITS

**The trigger is WAIT STATES, not accumulated context.** The prior "context-
dependent / only the full image reproduces" reading was an artifact of testing
the directed repros at w0 only. Board + TB now prove the drop is a pure function
of the wait count, universal across nesting and context.

**Minimal reproducer (fully isolated, no preamble):** `MOV SP,0x3f00 ; MOV
BP,0x3fe0 ; ENTER 0x000a,nest` (rest NOP). Delta-debug of the current-gen mc1/862
FULL image with a WAIT-DIFFERENTIAL oracle (w0 push-count minus w2 push-count ==
1, robust to NOP-induced SP shifts) minimized to exactly {MOV BP, ENTER} — no
context needed.

**TB wait sweep (clean directed, nest=3, fsz=0x0a):**
| waits | ENTER pushes | BP push (0x3efe=0x3fe0) |
|---|---|---|
| w0, w1 | 4 | PRESENT (correct) |
| w2..w7 | 3 | DROPPED |
Drops for ALL nesting 0..31 at w2 (nest=0: w0=1 push, w2=0 pushes).

**BOARD-CONFIRMED (chip use_core=0 vs fabric use_core=1, clean directed image):**
| case | CHIP pushes | FABRIC pushes |
|---|---|---|
| nest=3 w0 | 4 (BP present) | 4 (match) |
| nest=3 w2 | 4 (BP present) | **3 (BP 0x3efe=0x3fe0 DROPPED)** |
| nest=0 w0 | 1 (BP present) | 1 (match) |
| nest=0 w2 | 1 (BP present) | **0 (DROPPED)** |
The chip ALWAYS pushes BP (w0 and w2); the fabric drops it under waits. Genuine
chip-vs-fabric bug; the Verilator TB reproduces it bit-for-bit (faithful model).

**RTL ROOT CAUSE (v30_eu.sv):** ENTER entry (op_prep, ~L3080) does
`issue_push(rf[5])` (BP push; rf[4]=SP decremented HERE), `prep_acc<=0`, `dly<=3`,
-> S_PREP_L. The combinational hold `S_PREP_L: eu_req=!prep_acc` (~L1587) keeps the
request asserted, and `if (eu_started) prep_acc<=1` (~L3294) latches acceptance.
BUT the SEQUENTIAL EXIT of S_PREP_L (~L3297) advances on `dly==0 && q_pop` WITHOUT
requiring prep_acc. The `dly<=3` was fitted at w0, where the BIU accepts the BP
push within 3 cycles (eudbg: eu_started=1 on the 2nd S_PREP_L cycle, BEFORE the
level byte pops). Under w2 the busy BIU has not yet started the push (eu_started=0
through all of S_PREP_L) when the level byte pops (dly already 0); the FSM leaves
to S_WAITX, eu_req falls (request WITHDRAWN, never accepted), and the walk's next
`issue_push` overwrites eu_addr/eu_wdata. rf[4] was already decremented at entry,
so the walk lands at 0x3efc/0x3efa/0x3ef8 (same addrs as w0) — exactly one push
short. eudbg w0-vs-w2 diff of S_PREP_L is the smoking gun (eu_started fires pre-
pop at w0, post-exit at w2).

**SCOPE — far broader than 8 seeds.** This is a UNIVERSAL ENTER-under-waits bug
(every ENTER with >=2 waits drops its BP push), not a cluster of 8. mc1 surfaced
only 8 because most ENTERs ran at w0; the enter_nesting golden tranche
(sw/char_enter.py) captured the CHIP at **w0 ONLY**, blind to this. Other push-
issuing states (S_REQ/S_WREQ/S_CALLPUSH/traps) advance on eu_started, so they are
NOT affected — the vulnerability is unique to S_PREP_L's fixed-dly + q_pop exit.

**PROPOSED FIX (report-first; NOT yet applied):** gate the S_PREP_L exit on push
acceptance — do not consume the level byte / leave S_PREP_L until `prep_acc ||
eu_started`. e.g. `else if (q_pop && (prep_acc || eu_started))`. Transparent at
w0 (prep_acc already set by pop time), holds under any wait count. Savestate: no
new flop (prep_acc already SSA_E_PREP_ACC-mapped). Gate additions on fix: extend
sw/char_enter.py + tests/v30/enter_nesting to capture chip goldens at w1..w7 (and
wrand), and assert push count == nest+1 under waits; the current w0-only tranche
is vacuous for this bug.

## ENTER PUSH-BP fix — APPLIED (staged) + AUDIT + a w2 cadence RESIDUAL found

**Fix applied (v30_eu.sv, staged/uncommitted):** gate `pop_want` for S_PREP_L on
acceptance — `(state==S_PREP_L && dly==6'd0 && (prep_acc || eu_started))`. NOTE:
the fix goes on `pop_want` (the queue-pop enable), NOT only the S_PREP_L exit. A
first attempt gating just the sequential exit FAILED: `q_pop = pop_want &&
q_avail` and `pop_want` for S_PREP_L was `(dly==0)`, so the queue byte is CONSUMED
every cycle dly==0 regardless of the sequential body — holding without gating
pop_want burned through queue bytes and latched a NOP as the nesting level
(runaway: 24 pushes). Gating pop_want holds the level byte un-popped until the BP
push is accepted, keeping the level-pop and the push in sync. TB rebuilt: push
count == nest+1 at EVERY wait w0..w7 for all nesting, BP push (0x3efe=0x3fe0)
present. Board-confirmed bug + TB-confirmed fix.

**AUDIT (RR4-pattern, coordinator-required) — S_PREP_L is the UNIQUE site.**
Scanned every bus-op issuer (issue_push + eu_wr<=1) and its landing-state exit:
- S_REQ/S_WREQ, S_PREP_RD/PW2/W3, S_CALLPUSH, S_FCALLP1/P2, S_STRW/R/S,
  S_OUTS_W/INS_W, S_IE_WR, S_A4_DST/WR, S_INT_A1/A2, S_TRAP_PSW/PS: advance on
  `eu_started`/`eu_done` (acceptance) — SAFE.
- S_WAITX→S_REQ issuers (2668 ADD4S, 4520/4555 RET/CALL): exit into S_REQ which
  COMPLETES THE SAME pending op (no different op issued) — SAFE.
- Trap chain (S_TRAP_W1/PSWW/W2, dly-timed next-push): each push is followed by an
  `if(eu_started)` wait (S_TRAP_PSW, S_TRAP_PS) BEFORE the next issue; the dly only
  TIMES the next issue, prior push always accepted first — SAFE.
- ADD4S gaps (S_A4_G1/G2/END, dly): prior access accepted (eu_done in *_W) before
  the gap; the gap times the next issue into an eu_started-gated *_W — SAFE.
- All q_pop-exit states other than S_PREP_L (S_FIRST/S_DEC/S_IMM*/S_JD*/S_DISP*/
  S_MLO/MHI/S_0F/S_DEC2/S_IN_PORT): pure decode-phase byte pops with NO pending
  bus op — SAFE.
Distinguishing factor of the bug: S_PREP_L exits (on q_pop, non-acceptance) while
holding an UNACCEPTED request, into a state that issues a DIFFERENT bus op (the
walk), dropping the pending one. No other site matches. Per-site verdicts go in
the commit message.

**RESIDUAL FOUND — w2 ENTER-walk vs prefetch INTERLEAVE (board-confirmed, NOT the
value bug; separate cadence item, report-first).** With the fix, the tranche's
cycle-exactness bar (chip-vs-TB, single-instruction ENTER, uniform waits) holds at
w0/w1/w3/w7 for all nesting, and at w2 for nest=0 — but FAILS at **w2 for nest>=1**
by ONE prefetch transposition. The chip holds the bus through the ENTER's ENTIRE
push/walk sequence at w2, then prefetches the next opcode (CODE 0x50c); the fixed
TB lets ONE prefetch (CODE 0x50c) sneak in BETWEEN the BP push and the rest of the
walk. It is wait-specific chip behavior: at w1 the chip DOES prefetch mid-walk
(TB matches), at w3+ it does not (TB matches) — only w2 the chip holds and the TB
does not. Example w2 nest=3 (T1 txns from entry): pos6 MEMW 0x3efe=0x3fe0 (BP push,
CORRECT) then chip=MEMR 0x3fde walk.. / tb=CODE 0x50c prefetch, walk shifted one
slot. Architectural result identical (push count + all push data exact); this is a
pure prefetch-arbitration/cadence ordering nuance, #33-class (prefetch/queue
split), exposed by the fix's w2 retiming. Root cause is the ENTER walk's post-
level-pop reservation window (dly<=6 -> S_WAITX -> S_PREP_RDGO) not pinning the
bus slot at w2 the way the chip does; matching it is prefetch-cadence fitting, not
a push-drop guard. REPORTED for a ruling (chase w2 cadence now vs land value fix +
book residual). The coordinator's "cycle-exact per v0.1-w1/w3 precedent" assumption
holds at w0/w1/w3/w7 but NOT at w2 nest>=1 — a genuine correction.

## ENTER PUSH-BP fix — LANDED (coordinator OPTION A) + waited tranche + w2 to #33

Coordinator ruling: OPTION A — land the value fix; the w2 interleave is clean
prefetch-arbitration cadence (#33), not chased now.

**The w2 residual is LAYOUT-SPECIFIC — it does NOT appear in the tranche harness.**
The w2 nest>=1 interleave reproduces in the DIRECTED harness (MOV SP,0x3f00; MOV
BP,0x3fe0; ENTER; NOP-sled at PS:PC=0:0x500). But the standing tranche uses the
compose harness (reg-load preamble far-jumps to PS:PC=0:0x100, queue flushed,
then MOV BP; ENTER; store stub). Board-measured there, the fixed core is
**cycle-exact at EVERY wait and nesting** (w0/w1/w2/w3/w7, nest 0..63, + wrand) —
0 divergences. So the interleave is a function of the surrounding code stream /
queue state, not the ENTER itself; the tranche carries NO known_divergences.

**Waited tranche (tests/v30/enter_nesting/goldens_waited.json.gz):** 154 chip
goldens = nesting {0,1,2,3,4,5,8,16,31,32,63} x waits {0,1,2,3,7} x 2 ctx + a
wrand slice {(3,0x1234),(7,0x5678)}. sw/char_enter.py --waited --freeze. Each
golden stores the full txn stream (kind,addr16,data,dur) from the test anchor +
active-cycle count. Gate sw/check_enter_nesting.py now runs BOTH tranches:
- MASK (w0 0..255): walk-stream strict (the nesting-mask gate) — PASS 512/0.
- WAITED: (a) WALK-STREAM STRICT at ALL waits (stack-region MEMW/MEMR order/addr/
  data == chip) — the value-bug invariant; (b) CYCLE-EXACT (full stream + active
  count == chip) strict everywhere, with an enumerated known_divergences set
  (EMPTY here) that the checker counts/reports and treats an unexpected cyc
  divergence as a HARD FAIL. Board+TB: PASS, 0 unexpected, 0 booked cells.

**#33 bank (prefetch/queue-split cadence campaign):** the wait-count-dependent
ENTER-walk-vs-prefetch bus-hold is a precise, board-evidenced non-monotonic
arbitration law: at the directed-0x500 harness the chip prefetches the next
opcode MID-walk at w1, HOLDS the bus through the whole ENTER walk at w2, and does
NOT prefetch mid-walk at w3+. The fixed core matches w1 and w3+ but at w2 lets one
prefetch in between the BP push and the walk. Repro: sw = the directed harness
above; compare chip(use_core=0) vs TB full txn stream at w1/w2/w3, nest>=1. Booked
for #33 as a starting datapoint.

**CORRECTION to the record:** "single-instruction contexts are cycle-exact under
uniform waits (v0.1-w1/w3 precedent)" is now measurement-qualified — it holds at
w0/w1/w3/w7 universally and at w2 in the compose harness, but FAILS at w2 nest>=1
in the directed-0x500 harness (the prefetch interleave). Cycle-exactness under
waits is code-stream/queue-state dependent, not purely a function of the single
instruction.

**RTL fix form (the negative evidence matters):** gate `pop_want` for S_PREP_L on
`(prep_acc || eu_started)` — NOT the sequential exit alone. First attempt gated
only the S_PREP_L exit and RAN AWAY (24 pushes, NOP latched as the level): because
`q_pop = pop_want && q_avail` and pop_want was `(dly==0)`, the queue byte is
consumed every cycle dly==0 regardless of the sequential body — an ungated hold
burns through queue bytes. Gating pop_want holds the level byte un-popped until
the BP push is accepted, syncing level-pop and push. No new flop (prep_acc already
SSA_E_PREP_ACC-mapped); ss_lint 203 unchanged; no SS_VERSION bump.

**AUDIT verdict (unique site):** S_PREP_L is the ONLY bus-op issuer that exits on a
non-acceptance (q_pop) condition while holding an unaccepted request, into a state
issuing a DIFFERENT bus op. All others advance on eu_started/eu_done/facc/pracc,
or exit into S_REQ completing the SAME op, or (trap/ADD4S) dly-time the next issue
only after the prior push is accepted. Full per-site list in the commit message.

**Quartus/reflash:** both ENTER fixes (nesting-mask + PUSH-BP-drop) are sim-proven
and ride ONE Quartus batch at #31 close; the on-board fabric needs them before any
future hw-ab campaign (the board fabric is currently the pre-fix bitstream).

## The 7 singles — ALL DISPOSITIONED (item 2); ZERO new mainline bugs

Method: raw seeds regenerate byte-exact (only cfg_hash metadata drifted; image
sha256 matches the capture), so decode/replay is direct. Compared the FIXED TB
(both ENTER fixes) against the capture CHIP leg (ground truth) per seed.

- **k=1627** (raw w0): ENTER at 0x583, **nesting=46** (>=32). The nesting-mask bug
  (pre-fix fabric walked 46&0x1f=14). Fixed-TB now MATCHES the chip (151/151 txns,
  no divergence). -> FIXED-BY-ENTER-MASK (efdd0b8). The earlier 6-seed mask family
  missed this one; it is the 7th.
- **k=4951** (raw wrand w1): ENTER at 0x50d, **nesting=150**. Same mask bug; fixed-
  TB MATCHES chip (526/526). -> FIXED-BY-ENTER-MASK (8th mask seed).
- **k=2925** (soup w3): MOV BP,0x3fe0; ENTER 0x0000,1. The PUSH-BP drop (chip MEMW
  0x3efe=0x3fe0, pre-fix fabric skipped it). Fixed-TB w3 now emits MEMW
  0x3efe=0x3fe0. -> FIXED-BY-PUSHBP (d104673; 9th pushbp seed).
- **k=2062** (soup wrand w2): PUSHA (0x60) at 0x500. The chip holds the bus through
  all 8 PUSHA pushes; the fabric interleaves ONE CODE prefetch (0x504) after the
  3rd push (fixed-TB still shows F0504 mid-push - my ENTER-only fix correctly does
  not touch PUSHA). Verdict was done_mismatch (the interleave shifted the done
  marker). SAME cadence class as the ENTER-w2 walk-vs-prefetch interleave. ->
  BOOKED #33: the multi-push bus-hold law now spans PUSHA AND ENTER.
- **k=8398** (raw w0): `8d 3b`=LEA DI,[BP+IY] (DI=BP+IY=0xcd05); `8f fe`=0x8F POP-
  group with **reg=7** - an UNDOCUMENTED POP encoding (optable 0x8F is group, only
  /0 defined). Execution stays in-program (0 PCs below 0x500). Board probe
  (directed): chip `8f fe` reads memory at the modrm-derived EA (~0xcd05=DI),
  fabric does a plain POP (stack read). Genuine undoc-opcode divergence; the core
  intentionally does not implement undoc opcode semantics (same basis as the soup
  p_undoc suppression and the raw-LEA-mod3 gap). -> BOOKED raw-undoc (no RTL fix;
  optional gen_raw scrub of 0x8F reg!=0 or a raw accept-rule, deferred).
- **k=2035** (raw w0) & **k=8649** (raw w0): ESCAPE/wander. Execution left the
  intended 0x500 program (k=8649 down to 0x4c0 via a backward transfer; k=2035
  below 0x500 too) and did OUT-OF-IMAGE open-bus MEMR (k=2035: 17 of them incl
  0x71bd8; k=8649: 0x6b559 which feeds the divergent 0x82-RMW EA - chip 0x63db0 vs
  fabric 0x68f17). Open-bus returns address feedthrough that differs chip-vs-fabric
  -> register/EA divergence downstream. The KNOWN escape phenomenon (mc1 survey
  dominant class). -> ACCEPTED escape. NOTE: t31_residue mis-typed these as
  genuine value bugs (its escape check missed the below-0x500 wander + near-image
  open-bus sub-forms) - a discriminator refinement is booked (non-blocking).

**Result:** all 22 residue seeds dispositioned. Final tally: 1 LEA-mod3 rule + 8
ENTER-mask (RTL, efdd0b8) + 9 PUSH-BP (RTL, d104673) + 1 PUSHA-interleave (#33) +
1 raw-undoc 0x8F + 2 escape = 22. **No new mainline bug in the entire residue** -
it collapsed into the two ENTER RTL fixes (17/22) plus known/accepted classes.
