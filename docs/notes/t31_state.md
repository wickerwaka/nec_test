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
| k=862, 2398, 4024, 6407, 7542, 9124, 9312, 9440 | 0x3fe0 cluster: fabric ENTER DROPS the initial PUSH BP (constant 0x3fe0 = the skipped BP); RTL v30_eu.sv:3083 issue_push(rf[5]) | **MECHANISM FOUND** — a SECOND ENTER bug, distinct from the mask; trigger not yet isolated (needs full-image delta-debug), then RTL fix | **ROOT-CAUSE IN PROGRESS** |
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

## Open leads (0x3fe0 cluster)
- All 8 are nesting 2-3 (<32) → PROVABLY unaffected by the nesting-mask fix
  (q_byte[4:0]==q_byte[7:0] for <32). The post-fix "3 of 8 match" quick check was
  CONFOUNDED (whole-trace push count + chip-vs-TB startup delta) — treat as noise;
  all 8 remain open.
- k=862 (nesting=3): campaign capture (chip-vs-board-fabric, no startup delta)
  shows chip 4 pushes / fabric 3 (fabric behaves as nesting=2 = off-by-one).
  Directed isolated ENTER nesting=3 MATCHES (fabric=4) → CONTEXT-dependent.
- Candidate triggers (coordinator lead): prefix/queue state at the ENTER fetch
  (k=862 has REP+DS: prefixes on a preceding TEST), a stale operand byte the
  fabric decodes as the nesting level, or BP/SP entry state. Next step: directed
  reproduction — prepend k=862's preceding context to an ENTER, chip vs fabric.
- CAVEAT: chip-vs-TB has a startup delta at row ~11 that desyncs downstream;
  investigate the cluster via the CAMPAIGN CAPTURES (chip-vs-board-fabric) or
  directed board legs, NOT chip-vs-TB replay.

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
2. Hand-trace one cluster seed → the 0x3fe0 mechanism. **(current)**
3. The 7 singles (k=8398 first).
4. #31 CLOSE-OUT: all 22 dispositioned; memory-worthy summary. Then #32 on go.
