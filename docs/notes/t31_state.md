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
| k=862, 2398, 4024, 6407, 7542, 9124, 9312, 9440 | 0x3fe0 cluster: fabric ENTER DROPS the initial PUSH BP **under wait states (w>=2)**. RTL: S_PREP_L exit (v30_eu.sv ~L3297) advances on `dly==0 && q_pop` without gating on `prep_acc`; the fitted `dly<=3` masks it at w0/w1, fails at w2+ when the busy BIU accepts the BP push after the level pop. TB + BOARD confirmed; UNIVERSAL ENTER-under-waits bug (not 8 seeds). Proposed fix: gate exit on `prep_acc\|\|eu_started`. | **ROOT-CAUSED + BOARD-CONFIRMED** — report delivered; RTL fix awaiting coordinator review (report-first) | **ROOT-CAUSE DONE** |
| k=1627, 2035, 2062, 2925, 4951, 8398, 8649 | singles (mixed) | not yet root-caused | **OPEN** (k=8398 = early read-EA split, partially analyzed; k=2062/2925 have ENTER nesting=1) |

Counts: 1 fixed-by-rule + 6 fixed-by-ENTER + 8 cluster-open + 7 singles = 22.

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

## Process rule (standing)
Long jobs: detached `nohup`/`setsid` + **LOG-MTIME polling** (until-loop on the log
file), NEVER process-wait / in-context waiter (two stalls). Board etiquette: leave
`use_core=0`.

## Remaining plan
1. Rigorous cluster re-analysis (done: fix is mask-invariant for nesting<32).
2. 0x3fe0 cluster → root-cause: DONE + board-confirmed (wait-triggered ENTER
   PUSH-BP drop; S_PREP_L exit not gated on prep_acc). Report delivered; RTL fix
   awaiting coordinator review (report-first).
3. The 7 singles (k=8398 first). **(current)**
4. #31 CLOSE-OUT: all 22 dispositioned; memory-worthy summary. Then #32 on go.
