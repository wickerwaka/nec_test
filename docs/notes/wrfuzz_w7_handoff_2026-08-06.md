# wrfuzz W7 — HANDOFF (sitting interrupted by usage limit, 2026-08-06)

**Status**: the W7 sitting (task #42, USER-DIRECTED successor-queue item 1 —
"the write-gap's mechanism from ROM geometry") was terminated mid-analysis by
an external usage limit. **No commits were made, no tracked file was modified,
no board was contacted** — the tree at `15b7a9b1cc` is exactly the pre-sitting
state. This document is the complete restart package; the successor agent
starts from the brief below and owes nothing to the dead sitting except one
lead.

## The one lead recovered from the interrupted sitting

The agent's final visible state, verbatim: *"M13's own scope note anticipated
this exact ambiguity. Let me test the candidate predicate's falsifier across
all emulation-mode stores."*

Read before restarting: **M13** (`ucsim_t_provenance.md` — the 8080/emulation-
mode OPR release rides retire) and specifically its **scope note**. The
interrupted agent had (a) formed a candidate predicate for the paired-write
gap mechanism, (b) found that M13's scope note bears on an ambiguity in it,
and (c) was about to run the predicate's falsifier over the emulation-mode
store population as a cross-check. The successor should re-derive the
candidate rather than guess it — but knowing that the trail runs through
M13's OPR-release machinery (i.e. the mechanism likely involves WHERE the
engines release/serialize the first write's OPR, which is exactly the
over-serialization shape the brief hypothesized) should shorten the walk.

## The task (the original brief, in full force)

Find the MECHANISM behind the paired-write gap. The measured fact
(`wrfuzz_provenance.md` §5, W3.2 half B): the part leaves EXACTLY 4 idle
clocks between the two writes of a paired-write form — 21/21 seeds, every
wait level, completing-cycle lengths 5→19 — while both engines' gap MOVES
with that length (1 at ≥6, 3 at 5). Control: on the 99 cycle-exact seeds,
MEMW→MEMW gap 4 occurs on 0 of 2,819 opportunities. This answered
`ucsim_t_provenance` §26.10 D item 4's discriminator (fixed index, not
bus-keyed); the CONSTANT must not be landed as a constant (the forbidden
fitted table) — the mechanism is the deliverable.

1. **ROM check first (offline, free)**: identify the forms in the 21-seed
   population + the tranche's SCHEDULE 7 (`wrfuzz_provenance` §9.5); walk
   their microcode in `docs/V20UC.TXT`; count rows between the two
   memory-write micro-ops per form. Hypothesis: the 4 is the ROM's row count
   under the one-row-per-clock cadence, and the engines' moving gap is an
   INVENTED stall (over-serializing on the first write's completion — see
   the M13 lead above) that the die does not have. The mechanism may be a
   deletion.
2. **Cross-check**: the mechanism must explain BOTH the 21 and the
   0-of-2,819 control (different row geometry there, or a stall the law
   predicts).
3. **Pre-registered landing** if 1-2 authorize: sim first (model-shared),
   ucore second; the wr1 guard (`sw/wrfuzz_wr1_guard.py`, floors model
   ≥84/184 / ucore ≥91/184, 0 lost, 0 earlier) stays green and its floors
   RAISE; the paired-write-heavy gates are load-bearing (ENTER 154×5, INS
   1,312/2,624, block-I/O 229,999); full ladders, lockstep, SS/G6 as state
   demands. Ledger §10, headed as post-verdict successor-queue work.
4. If the ROM refuses: the directed cell per W3.2's spec (BIU-slot vs
   EU-row-cost), per-candidate predictions committed before board contact,
   full board discipline, socket only, no flashing.

Scope: one mechanism, one sitting. Not the +2 mode, not raw-tier statistics,
not mc1/721. Standing user principle verbatim in force: "A guiding principal
here needs to be simplicity. This is 80's era hardware, they aren't wasting
silicon on anything that isn't necessary. Complex or confusing behavior that
we see is likely to be simple systems interacting in ways you do not fully
understand yet."

## State inventory for the successor

- HEAD `15b7a9b1cc` (the finalized wrfuzz verdict; awaiting user acceptance).
- Board: FLASH #11 (`82b49350…`), idle, `use_core=0`, last verified at W4
  close. No board contact since.
- All gates green at the figures in `standing_gates.md`; the wr1 guard green
  (coordinator re-ran it at W6 review).
- The untracked `hdl/output_files_ucore/*`, `*.log` files at repo root
  predate W7 and are not its debris.
