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
