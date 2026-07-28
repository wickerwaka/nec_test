# Task #31 — durable handoff state (resume-from-cold)

Enough for a fresh worker to resume #31 without prior context. Updated at each
boundary. Companion detail: `docs/notes/t31_rootcause.md` (per-bug root-causes),
`docs/notes/t31_family_map.md` (family map + collapse).

## What #31 is
Root-cause + disposition the **genuine in-image value-bug residue** of the mc1
FUNCTIONAL population. The 806 FUNCTIONAL collapse into: escape (~dominant, →#32),
prefetch/queue split (117, →#33, k=15 head, datapoint captured), and a **22-seed
genuine value-bug residue** (this task). "Genuine" = identical code-fetch stream
in both legs + differing store data (neither escape nor prefetch) — the
`sw/t31_residue.py` discriminator.

## The 22 residue seeds + dispositions
| seeds | class | disposition | status |
|---|---|---|---|
| k=6475 | LEA (0x8d) mod=11 stale-EA latch (task #30 class, raw) | raw-aware `lea_mod3` accept rule | **FIXED-BY-RULE** (commit c5b92d8) |
| k=3075, 3897, 4677, 5586, 5699, 6436 | ENTER nesting-mask, nesting≥32 (fabric masked mod 32, chip full 8-bit) | RTL fix v30_eu.sv S_PREP_L | **FIXED-BY-ENTER-RTL** (commit efdd0b8; TB-verified, tranche green; board reflash rides next Quartus batch) |
| k=862, 2398, 4024, 6407, 7542, 9124, 9312, 9440 | 0x3fe0 cluster: fabric ENTER DROPS the initial PUSH BP **under wait states (w>=2)**, ALL nesting. RTL fix (v30_eu.sv): gate `pop_want` for S_PREP_L on `(prep_acc\|\|eu_started)` so the level byte is not popped / walk not started until the BP push is accepted. No flop (ss_lint 203 unchanged, no SS bump). | **FIXED-BY-RTL (LANDED)** — waited tranche (154 chip goldens, waits{0,1,2,3,7}+wrand) + extended check_enter_nesting; board+TB PASS. A w2-nest>=1 walk-vs-prefetch INTERLEAVE (layout-specific, directed-0x500 harness only; tranche cycle-exact) booked to #33. | **FIXED** |
| k=1627 | ENTER nesting=46 (@0x583) — the mask bug, missed by the earlier 6 | RTL nesting-mask fix (efdd0b8) | **FIXED-BY-ENTER-MASK** (fixed-TB matches chip 151/151) |
| k=4951 | ENTER nesting=150 (@0x50d), wrand w1 — the mask bug | RTL nesting-mask fix (efdd0b8) | **FIXED-BY-ENTER-MASK** (fixed-TB matches chip 526/526) |
| k=2925 | MOV BP,0x3fe0; ENTER 0,1 @ w3 — the PUSH-BP drop | RTL pop_want fix (d104673) | **FIXED-BY-PUSHBP** (BP push 0x3efe restored in fixed-TB) |
| k=2062 | PUSHA (0x60) @ wrand w2 — chip holds bus through the 8 pushes, fabric interleaves ONE prefetch | none (cadence) | **BOOKED #33** (multi-push bus-hold-vs-prefetch interleave; same class as ENTER-w2) |
| k=8398 | undoc 0x8f reg=7 (POP-group /7) @ 0x502 — board-confirmed: chip reads modrm-EA (~DI), fabric plain POP | none (undoc) | **BOOKED raw-undoc** (core doesn't replicate undoc opcodes, by design; optional gen_raw scrub / accept-rule deferred) |
| k=2035 | execution wandered below 0x500 + 17 out-of-image open-bus MEMR (0x71bd8 etc.) | none (escape) | **ACCEPTED escape** (discriminator gap) |
| k=8649 | execution wandered to 0x4c0 + out-of-image MEMR (0x6b559) feeding the divergent EA | none (escape) | **ACCEPTED escape** (discriminator gap) |

Counts: **1 fixed-by-rule + 8 fixed-by-ENTER-mask + 9 fixed-by-PUSHBP-RTL + 1
booked-#33 + 1 booked-raw-undoc + 2 accepted-escape = 22.** ALL 22 DISPOSITIONED;
ZERO new mainline bugs. The residue collapses almost entirely into the two ENTER
RTL fixes (17 of 22). Mask family is really 8 (6+k=1627+k=4951); PUSHBP family is
9 (8 cluster + k=2925). Discriminator gap booked: t31_residue mis-typed 2 escapes
(k=2035/8649, below-0x500 wander + near-image open-bus) as genuine value bugs.

## Key mechanisms confirmed
- **ENTER nesting mask**: V30 chip does NOT mask nesting (pushes = nesting+1, all
  0..255); fabric masked mod 32 ((nesting&0x1f)+1). Directed probe + 512-golden
  tranche (tests/v30/enter_nesting). Fix: `a4_k <= q_byte[7:0]` (was
  `{3'd0,q_byte[4:0]}`) + ==0/==1 checks full-byte. a4_k/a4_cnt were already 8-bit
  SS-mapped → no savestate change.
- **Whitelist re-confirmed** (task #30): LDS/BOUND/LES mod=11 PARK on chip (clean
  AND post-ENTER); only LEA executes. k=3075/8398 heuristic "LDS/BOUND" hits were
  mis-attributions.

## 0x3fe0 cluster — CLOSED to root-cause (see t31_rootcause.md)
RESOLVED: the trigger is WAIT STATES, not context. The prior "context-dependent /
only-full-image" reading came from testing directed repros at w0 only. Minimal
repro = `MOV BP,0x3fe0 ; ENTER 0xa,nest` (no preamble); drops at w2..w7 for ALL
nesting 0..31; correct at w0/w1. BOARD-confirmed chip pushes BP at both w0 and w2,
fabric drops at w2 (nest=3: chip4/fab3; nest=0: chip1/fab0). RTL root cause =
S_PREP_L exit not gated on prep_acc. UNIVERSAL ENTER-under-waits bug. Prior "w0
too" note in this file was a misread — CORRECTED. Fix proposed, report-first,
awaiting coordinator review. NOTE: char_enter.py / enter_nesting tranche is
w0-ONLY and vacuous for this bug — the fix must add waited chip goldens.

## Tool inventory (all sw/, board-free unless noted)
- `t31_residue.py` — the genuine-value-bug discriminator (identical code path +
  differing store data). Emits the 22 + chip-value clusters.
- `t31_family_map.py`, `t31_root_signal.py` — FUNCTIONAL clustering / routing.
- `char_enter.py` (board) — ENTER-nesting tranche capture; `check_enter_nesting.py`
  — standing gate (replays tranche in TB).
- `char_mod3.py` (board) / `check_mod3_illegal.py` — LEA/mod3 tranche + gate.
- `min_hang.py` — soup delta-debug minimizer. `fuzz_campaign._raw_lea_mod3_pos` —
  raw LEA-mod=11 detector.
- Reconstruct any seed: `fuzz_campaign.derive_case(cid,k[,ov]) → build → check_seq.compose`. Captures: `sw/testdata/campaigns/mc1/captures/<tier>_<k>_<cfghash>.json.gz`.

## Commits (this task)
adf236c collapse+residue • c209819 k6475 root-cause • c49eb84 whitelist resolved •
c5b92d8 raw lea_mod3 rule • bff914b ENTER root-cause • efdd0b8 ENTER RTL fix+tranche

## Fuzz-bank re-freeze — OWED (both ENTER fixes; not a regression)
check_fuzz_bank on the PUSH-BP fix: **worse 0, gen_drift 0** (non-strict PASS), but
`--strict` fails on **138 improved + 64 new-sig TIMING**. Root: the bank was last
frozen at **b532a6e (07-27 19:09)**, BEFORE both #31 ENTER RTL fixes (nesting-mask
efdd0b8 07-28 05:06 AND the PUSH-BP fix) — so the 138 improvements are the combined
effect of both fixes on a stale bank (many `t30-raw/*` FUNCTIONAL->TIMING/KA/SUCCESS,
i.e. ENTER-under-waits value bugs now cadence-only). NO regression. OWED follow-up:
re-freeze the bank + add the 64 new TIMING sigs to sig_ledger.json (the "queue
retire" workflow), covering BOTH ENTER fixes. Deferred as scoped bank-maintenance
(don't silently mutate 138 goldens); non-strict gate is green so it does not block
the fix landing. Do at/with the #31 close-out or when the coordinator rules.

## Process rule (standing)
Long jobs: detached `nohup`/`setsid` + **LOG-MTIME polling** (until-loop on the log
file), NEVER process-wait / in-context waiter (two stalls). Board etiquette: leave
`use_core=0`.

## Remaining plan
1. Rigorous cluster re-analysis (done: fix is mask-invariant for nesting<32).
2. 0x3fe0 cluster → FIXED (RTL pop_want gate) + waited tranche + gates green;
   coordinator OPTION A landed. w2 interleave banked to #33. DONE.
3. The 7 singles: ALL DISPOSITIONED (3 fixed by the ENTER RTL fixes, 1 #33, 1
   raw-undoc, 2 escape; zero new bugs). DONE.
4. #31 CLOSE-OUT **(current)**: all 22 dispositioned (done); memory-worthy summary;
   fuzz-bank re-freeze (owed, both ENTER fixes); ONE Quartus+safe_flash batch
   carrying both ENTER fixes (sanctioned for close-out, standard wedge protocol,
   flash_log pins the build). Then #32.
