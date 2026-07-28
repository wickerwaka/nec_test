# mc1 survey - rough failure categorization

Campaign `mc1`: 10003 seeds, 6140 non-SUCCESS (61%).

Verdicts: SUCCESS=3863, KNOWN_ACCEPTED=2864, TIMING=2470, FUNCTIONAL=806

## Signature families (non-SUCCESS)

| family | n | tiers | waits-classes | first-div character | rep seed |
|---|---|---|---|---|---|
| TIMING/timing | 2470 | soup:2257,raw:213 | w0:699,wr1:442,wr2:354,wr3:300 | data, addr, bus | mc1/0 |
| KNOWN_ACCEPTED/cadence | 1846 | soup:1696,raw:150 | wr1:497,wr2:382,wr3:244,wr7:212 | addr, bus, data | mc1/30 |
| KNOWN_ACCEPTED/open_bus | 1018 | raw:1018 | w0:346,wr1:166,wr2:135,wr7:94 | addr, data, bus | mc1/3 |
| FUNCTIONAL/done_mismatch | 542 | soup:542 | wr2:94,wr3:85,wr1:79,wr7:72 | bus, data, addr | mc1/15 |
| FUNCTIONAL/func:W@N | 134 | soup:95,raw:39 | wr7:19,w2:19,wr15:18,wr2:18 | addr, data, bus | mc1/169 |
| FUNCTIONAL/func:R@N | 101 | raw:79,soup:22 | w0:32,wr1:18,wr3:13,wr2:10 | addr, bus, data | mc1/68 |
| FUNCTIONAL/func:INTA@N | 29 | soup:27,raw:2 | w0:6,wr7:6,wr1:5,wr2:5 | data, addr, bus | mc1/874 |

## Waited-TIMING drift distribution (1771 surfaced TIMING)

- |final_off| p50=4 p90=18 p99=91 max=545
- worst changepoint step p50=39 p90=174 max=1998  (cadence floor max_step=9)

## w0 escalation walk-bys (strict-mode STOPs absorbed)

- w0 FUNCTIONAL: 52  (reps: mc1/169, mc1/410, mc1/444, mc1/607, mc1/874, mc1/1224)
- w0 TIMING: 699  (reps: mc1/28, mc1/34, mc1/35, mc1/49, mc1/51, mc1/65)

## Wrand threshold sample

- wrand seeds: 4972 (>=500 -> calibration verdict below)

---

## Per-family mechanism (guess unless marked)

1. **TIMING/timing (2470)** - two sub-populations:
   - **w0 sub-family (699)**: NOT cadence drift (|final_off| = 0). A 60-seed
     sample shows **100%** have the chip running out-of-image (addr 0x60000+)
     after first_bad; both legs escape the 64K image and then DESYNC on their
     out-of-image path (a hard split, not gradual drift) - the SOUP analog of the
     raw open-bus escape (k=16). Mechanism GUESS: post-program fall-through -
     after the strict-soup program's last instruction, execution wanders out of
     the image and chip vs core take different out-of-image paths. An ESCAPE
     artifact, not a mainline cycle bug.
   - **waited sub-family (~1771 wrand/fixed)**: cadence divergences beyond the
     max_step=9 floor, a smooth HEAVY tail (maxstep p90=61, p99=1419). Part
     genuine wait-state BIU/prefetch cadence (the #1-priority category), part
     desync from escapes (189+ code_mism = fetch streams fail to align). CONFIRMED
     the floor surfaces them; the clean-aligned large-maxstep subset is the real
     wait-state investigation target.
2. **KNOWN_ACCEPTED/cadence (1846)** - CONFIRMED benign: the frozen floor working
   (documented odd-parity + small drift).
3. **KNOWN_ACCEPTED/open_bus (1018)** - CONFIRMED: raw seeds far-jump out of the
   image and run open-bus feedthrough (the k=16 class), typed by the new rule.
4. **FUNCTIONAL/done_mismatch (542)** - soup fall-through where chip and core
   disagree on reaching the done marker; the same ESCAPE root as the w0-TIMING
   sub-family, classified functional because the done markers differ (k=9192 is a
   member - it wandered into port 0xFC with junk). GUESS: fall-through escape.
5. **FUNCTIONAL/func:W|R|INTA (264)** - the genuine arch/bus functional
   divergences (a write/read/INTA where chip and core differ in data or presence).
   HIGHEST-value residue: after escape-typing, these are the real mainline-bug
   candidates. GUESS: a mix of escape-space artifacts and possibly real in-image
   functional differences - needs per-seed triage (reps k=169, k=68, k=874).

## Meta-finding: the ESCAPE phenomenon dominates non-SUCCESS

open_bus (1018) + w0-TIMING soup-escapes (~699) + fall-through done_mismatch
(~542) = ~2260 of 6140 non-SUCCESS (**~37%**) are the SAME root: strict-soup and
raw programs LEAVE the loaded 64K image and execute out-of-image garbage /
open-bus feedthrough, where chip and fabric core legitimately diverge. This
DISPROVES the "soup stays in-image by construction" assumption (mc1 k=9192 forced
the point - it tripped the provenance STOP) and is a coverage-vacuity issue: a
large slice of campaign budget tests out-of-image execution, not the loaded
program, and the escapes pollute the TIMING/FUNCTIONAL families with artifacts.

## Proposed ranked fix plan (report-only; RTL/generator changes need your ruling)

1. **[HIGH impact, tractable] Contain or type the escape phenomenon.** Either
   (a) fence strict-soup fall-through with a HLT after the program so execution
   cannot wander out-of-image, or (b) extend the open_bus_escape accept rule to
   soup so escapes are typed out of the FUNCTIONAL/TIMING signal. Underlying-bug
   mainline-reachability LOW (no real program runs out-of-image), but the
   signal-cleaning impact is HIGH (removes ~37% artifact load). This is the
   single biggest lever on campaign signal quality.
2. **[HIGH value, needs triage] Triage the in-image func:W/R/INTA residue (264).**
   After escape-typing, separate escape-space artifacts from real in-image
   functional divergences (reps k=169/k=68/k=874). Any confirmed in-image
   functional chip-vs-core difference is a real mainline bug (severity HIGH,
   tractability MEDIUM - per-seed forensics like the k=16 method).
3. **[#1-priority, harder] Characterize the clean waited-TIMING cadence tail.**
   The non-code_mism large-maxstep (16-127) wrand seeds are candidate wait-state
   BIU/prefetch cadence bugs - the cycle-accuracy mandate. Severity HIGH,
   tractability LOW (touches the prefetch/wait-law / biu_rebuild territory).
4. **[CLOSED] EU-duration gap (k=16 thread).** Board-confirmed cycle-exact
   in-image across shift/rotate-by-CL and MUL/IMUL/DIV/IDIV/AAM/AAD operand
   extremes; k=16 was pure open-bus. No RTL fix; folded into the open_bus class.

## Wrand cadence-floor threshold VERDICT: RETIRE the widening

Over **3326 wrand divergent seeds** (>> the 500 gate; sw/cadence_recal_mc1.py):
maxstep histogram [0-9]=1735 [10-15]=397 [16-30]=431 [31-63]=443 [64-127]=164
[128+]=156; p50=8 p90=61 p95=109 p99=1419 max=3233. Accept-rate @ frozen
(max_step=9) = 49.1%; @ proposed (15) = 60.5%. Safety: 0 non-step rejects are
swallowed by a step widening (code_mism/skip/rate/pre_tw always surface).

**Verdict: RETIRE the proposed max_step 9->15 widening.** (1) There is NO cliff
at 15 - the tail is smooth (10-15:397 is SMALLER than 16-30:431 and 31-63:443),
so 15 is an arbitrary mid-slope cut. (2) 15 reaches only 60.5% accept, far below
the 90% calibration gate - the wrand TIMING population is NOT dominated by
floor-drift but by genuine larger divergences. (3) The floor's #1 risk is masking
real wait-state bugs; the 10-63 maxstep band (1271 seeds) is exactly the
candidate-bug population (fix-plan #3) that must SURFACE, not be swallowed. The
48-seed re-cal that suggested p95=14 was unrepresentative. **Keep max_step=9
(v1.0) frozen.**

## QUARANTINE enumeration + the k=9192 driver-death incident

Final run: **0 QUARANTINE** (after the provenance fix). The single quarantine of
the campaign was mc1 **k=9192** in the pre-fix session: a strict-soup fall-through
escaped the image and OUT'd junk (0x00c5) to the done port 0xFC on the CHIP only
(from linear 0x600c5), tripping the `done_data` provenance alarm as if the store
stub were corrupt. It was a clean armed STOP (NOT a driver crash - the detached
log shows a full summary + board cleanup; verdict is a string in all lines). Root
cause = a classifier false-positive that would recur at scale. FIXED (commit
1a26352): the done_data alarm now fires only when BOTH legs agree on a
non-sentinel done value (a shared/deterministic store corruption) and neither
escaped; a one-sided junk done write is a functional divergence, not an integrity
STOP. k=9192 re-classifies FUNCTIONAL/done_mismatch. Driver also gained a
heartbeat.json beacon (MTIME liveness) so a stall is never missed by process-wait.

## #33 datapoint (banked from task #31): ENTER-walk-vs-prefetch bus-hold law

While root-causing the #31 ENTER PUSH-BP-drop (fixed), a precise, board-evidenced
prefetch-arbitration datapoint fell out for the #33 (prefetch/queue-split, wait-
state cadence) campaign. In a DIRECTED harness (MOV SP,0x3f00; MOV BP,0x3fe0;
ENTER 0xa,nest; NOP-sled at PS:PC=0:0x500), the chip's prefetch-vs-ENTER-walk
arbitration is NON-MONOTONIC in the wait count: at w1 the chip prefetches the
next opcode MID-walk; at w2 it HOLDS the bus through the ENTIRE ENTER walk before
prefetching; at w3+ it again does not prefetch mid-walk. The fixed V30 core
matches w1 and w3+ but at w2 lets ONE CODE prefetch in between the BP push and the
walk (walk/value identical; pure ordering). It is LAYOUT-SPECIFIC: the compose-
harness ENTER tranche (PS:PC=0:0x100) is cycle-exact at every wait, so the
interleave depends on the surrounding code stream / queue state. A clean starting
law for the wait-state cadence work. Repro + evidence: docs/notes/t31_rootcause.md.
