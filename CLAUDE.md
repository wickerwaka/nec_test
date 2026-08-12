# nec_test — project instructions for Claude

## Execution model (standing rule, user directive 2026-08-02)

**All implementation work is done by Opus subagents.** The main (Fable)
session agent does not implement directly; it:
1. plans and scopes each task,
2. writes the subagent brief (context, gates, discipline),
3. launches the Opus subagent,
4. **reviews the completed work after EVERY task** — independently re-running
   the claimed gates and reading load-bearing code/ledger changes before
   accepting, launching the next task only after acceptance.

Small coordinator-level actions (one-line doc fixes caught in review, memory
updates, task-ledger bookkeeping, git housekeeping) may be done directly by
the main agent.

## Standing design principle (user directive 2026-08-01)

SIMPLICITY: this is 80's era hardware — nothing on the die is wasted.
Complex or confusing observed behavior is likely simple systems interacting
in ways not yet understood. A large fitted table, a many-cased rule, or a
per-opcode special case is a signal of misunderstanding, not a deliverable.
Put this principle verbatim into every modeling subagent brief.

## Correctness target (user directive 2026-08-04 — supersedes the ucore
campaign's RTL-vs-sim governance)

**SILICON MATCH is the only correctness bar.** "Matching the model is no
longer acceptable." The C++ sim remains an instrument (lockstep, census,
attribution) but is NOT the reference: a divergence from silicon is a work
item regardless of whether the model shares it; model-shared residue is no
longer accepted residue. Where the rig or a golden is found defective, fix
the rig and RE-CAPTURE; goldens invalidated by rig defects are DISCARDED
from all gate sets — archived by rename with an invalidation ledger entry
(the w1evt-biased precedent; raw captures stay retained, nothing gates on
them).

## Standing engineering discipline

- Truthful commit messages: never assert a gate that is not met.
- **Verify against the artifact, not against recall**: an agent's absence of
  memory of an event is not evidence the event did not happen — check the
  ledger/commit/task record before "correcting" it; deleting a true record
  corrupts a truthful ledger exactly as badly as inventing one.
- Ratchet gates are monotone; pre-register numeric bars before runs; report
  failures as registered, never restated.
- Survey-then-fix: run the full batch, categorize all failures, then fix —
  mechanism-level only.
- **A refuted key's REPLACEMENT must be validated on data that was not used to
  select it.** Rejecting a pre-registered candidate on a directed capture is
  what pre-registration is for; choosing its successor by scanning the same
  capture and then scoring the successor on that capture is fitting, and the
  score is not evidence. State the erratum, then validate on a disjoint
  population before the replacement is quoted. (Written after Codex found the
  pattern in H1's re-key; the worked mitigation is `ucore_provenance.md` §64.1.)
- Consult Codex (`codex:rescue`, resumed thread) as critical reviewer at
  campaign phase boundaries and before closing any verdict document.
- Board work: single-writer check first, socket only (`use_core=False`),
  no flashing unless explicitly authorized, pre-register predictions and
  commit before first board contact, retain full per-clock rows + sha256
  (never digests alone), run board_idle and verify after every session.
- **RTL promotion needs a Quartus receipt**: `python3 sw/quartus_gate.py` (G6:
  `gen_ucore_qsf --check`, one clean CONTROL build, Fmax ≥ 32 MHz, worst setup
  > 0, setup AND hold TNS 0.000) must PASS and its receipt exist before any RTL
  landing is accepted or any bitstream flashed. The fast ladder does not wait
  on it; the promotion does. **One green build is not closure** — the same tree
  has drawn 19.42 and 45.91 MHz (`standing_gates.md` §A, `ucore_provenance.md`
  §74.4).
- **A number with no artifact id is not quotable** (SM3 sitting 14). Every
  Verilator TB binary on a standing gate's path now carries a RECEIPT naming
  the bytes it was built from (`sw/artifact.py`, spec
  `docs/notes/artifact_receipt_layer.md`, migration `ucore_provenance.md` §75),
  and the gate REFUSES to run against a binary whose declared inputs or outputs
  no longer hash to the tree. Rebuild with
  `python3 sw/check_core.py --build --core <core>`; the layer never rebuilds
  behind your back, because an automatic rebuild is how the sixth incarnation
  stayed invisible for six days. `python3 sw/test_artifact.py` (**45/45**) is
  the layer's own falsifier and must stay green. **U1 IS CLOSED (SM3 sitting
  15, §76.A)**: the C++ model is `sim/build/v30sim`, declared by
  `sw/simbin.py` and rebuilt with `python3 sw/simbin.py --build`. **`sim/v30sim`
  is no longer on any scorer's path** — the binary moved because `build()`
  promotes by renaming its workdir and the old workdir was the source tree.
  `docs/V20BITS.TXT` is a DECLARED INPUT of the model (erratum E-1: the ROM is
  read at RUN time, exactly as the ucore's `ucrom.hex` is), so perturbing it
  invalidates every `--core sim` receipt even though the compiled bytes do not
  move. §75.7's remainder is now U2-U8 minus U1; §76.A restates it.
- /tmp discipline: no large temp files in /tmp (tmpfs quota); use
  `~/.cache/ucsimt-tmp` for big intermediates.
- Provenance ledgers: every modeled behavior tagged ROM / PLA / LAW /
  MEASURED / ASSUMPTION with evidence and falsifiers
  (docs/notes/ucsim_provenance.md, docs/notes/ucsim_t_provenance.md).

## Gate quick reference

### ⚠ READ FIRST IF YOU ARE ON `fuzz-v2-on-relanding` (2026-08-10, tip `399ba6729d`)

Two campaigns closed on this branch and **the authoritative re-registration is
`docs/notes/standing_gates.md` §A (the `r7_lint` section) and §B (the ucore
table, *THE fuzz-v2 CORPUS*, and *THE RE-LANDING CAMPAIGN*)**. The headlines a
fresh session needs before it quotes anything:

* **Re-measured on this branch and GREEN**: `check_core --core ucore --opcodes
  all --cases 0` **169,000/169,000** · `ulockstep --golden all --cases 50`
  **17,350/17,350** · the four HLT sweeps **97 · 93 · 45 · 44 = 279/283** ·
  `ss_lint` **PASS, `SS_VERSION` 0x8C / 224 addresses / 212 flops / `SS_TAG`
  0x8CE0** · **`r7_lint` PASS** · `check_fuzz_bank` **PASS 621 / stable 621 /
  worse 0 / gen_drift 0 / regen_err 0 / float-floor 0 / new-sig TIMING 0**
  (⚠ RED at `09ec85e4bb` — 531/90, the old PASS was vacuous — and GREEN again
  at `a54cc27454` by RE-DERIVING the derived column, not by a repair; **it is a
  different PASS from the pre-RED one and the 90 are not erased**, see its own
  bullet) ·
  `fz2_w1 lint` **PASS** · `fz2_w1 bars` **11/11 MET** (was 10/11; **A-14**
  re-registered E-1c's MEANING by USER RULING — read the ⚠ below before quoting
  it).
* **⚠ FOUR RATCHETS IN THIS FILE CANNOT RUN HERE AT ALL** — `timed_scenario`,
  `timed_ins_replay`, `timed_wvec_gate`, `timed_enter_replay`. They die in
  `image_of(seed)` on `gen_seq._v1_anchor_stop`: fuzz-v2 moved the image anchor
  and their goldens are frozen at the v1 one. **Engine-independent** (they fail
  identically on the baseline), so no landing here is gated by them and none may
  be quoted from here. This is *separate from* the SUP-1/D9 caveat below, which
  is about the v1 fuzz **banks**.
* **⚠ THE SCORED WHOLE-PROGRAM FUZZ COLUMN ON THIS BRANCH IS 14 SEEDS WIDE**
  (`timed_fuzz --bank fz2c,fz2e --evt-replay`). A benefit measurement with a
  denominator of 14 is the best instrument the branch has. Rebuilding a
  replayable corpus is SUP-1's open item.
* **The board carries FLASH #14 since 2026-08-10** (below, superseding the
  FLASH #13 and FLASH #10 lines). It is the first bitstream to carry **F58, A1,
  C1, C2 and D1**, and all five are **CONFIRMED in fabric**: 46 of 46 registered
  seats closed plus 10 more, corpus **3,639 → 3,692 of 3,837** (like-for-like
  denominator). **P-7 MISSED — three seeds entered the ledger**; one
  (`fz2e/517043`) is a `PSW.TF` seed and is `C1`'s, the first measured cost of
  `C1`'s registered directed-cell debt. `fz2_f14_results_2026-08-10.md`.
  **A FABRIC FIGURE TAKEN ON FLASH #13 OR EARLIER MAY NOT BE QUOTED AGAINST
  THIS TREE.**
* **`ulockstep` dipped to 17,340 and recovered within one day** — the 8F ghost
  READ landed in RTL before `sim/` had it. See `standing_gates.md` §B for the
  erratum against `int_f3aa_repair_results_2026-08-09.md` row 8b.

**THE STANDING CORE IS `ucore` SINCE 2026-08-04.** The trace-fitted FSM core
(`hdl/rtl/core/`) was **ARCHIVED** by user decision on that date —
`docs/notes/fsm_core_archive_2026-08-04.md`, evidence in
`ucore_campaign_verdict_2026-08-04.md` §(e) item 1. Nothing moved or was
deleted; `--core fsm` still builds and runs. What changed:

* `check_core.py`, `check_boot.py`, `check_ab_sim.py`, `ss_lint.py` and
  `ss_flopcensus.py` now **default to `--core ucore`** (they defaulted to `fsm`).
  The `timed_*` tools still default to `--core sim`, the C++ model.
* The FSM-specific gates moved to an **"ARCHIVED — on demand"** section of
  `docs/notes/standing_gates.md`: `check_race_law`, `check_ff_t4`,
  `check_lc6_gate`, `prefix_clear_lint`, `ea_step_lint`, `check_mod3_illegal`,
  `check_enter_nesting`, `check_fuzz_bank`, `ss_lint --core fsm`, and
  `sw/t30_sweep.sh` (now `--core fsm` on every leg). They gate an archived
  artifact; a green run of them says nothing about the ucore.
* `docs/notes/standing_gates.md` is the authoritative list; **§D of it records
  the default-flip audit** — every consumer of the old default was made
  explicit rather than left to inherit the new one.
* **What the ucore does NOT yet do is enumerated in
  `docs/notes/ucore_gaps_2026-08-04.md`** — read that before assuming a gap is
  unknown. Headlines: 8080/BRKEM is structurally unreachable while `sim/`
  implements it (and it is **DEFERRED BY USER DECISION 2026-08-05** — not to be
  tested or considered until a later campaign); three of the four golden suites
  have never been run against the ucore (and `v0.2` cannot be,
  `KeyError: 'opcodes'`).  ⚠ **That document's residue headline is a 2026-08-04
  snapshot and is SUPERSEDED**: it said *"the ucore's own registered-fuzz residue
  is 9 seeds (210 of its 219 are model-shared)"*.  The current partition is
  `sm3_s27_residue_census_2026-08-05.md`: total banked-corpus residue **222**
  seeds of 2,710 scored, `ucore`-ONLY **14**, model-shared raw intersection
  **208** (of which 99 fall in L1-L3 and **109** remain in the `sim/`-first
  routing layer), and the **UNDISPOSITIONED CATCH-ALL IS NINE SEEDS** — a
  DIFFERENT nine from §T.2's, disjoint from it seed for seed.

(The ratchets below are current as of ucsim-t §26 plus the ucore campaign U5.
Values are monotone: never re-scored downward without a loud, itemized entry.)

- **ROM/PLA**: `python3 sw/simbin.py --disasm` (disasm byte-exact, **1,285
  rows**, on the RECEIPTED binary and printing its receipt id — this replaces
  `make -C sim test`, which built an unreceipted `sim/v30sim` by mtime and is
  kept only as a developer convenience),
  `python3 sw/pla3_check.py` (21 checks).
- **Functional**: `python3 sw/ucsim_check.py --suite tests/v30/<suite>`
  (mod3_illegal needs `--residue stale-ea`; v20suite needs `--no-mirror`);
  full set = v0.1 169,000 + v0.2 347,000 + v0.3 3,699,998 + v20suite
  3,125,000 + mod3_illegal 128 = **7,341,126 cases**.
- **Timed, per-suite** — `sw/timed_gate.py --suite tests/v30/<suite>
  --forms all [--waits N]`:
  `v0.1` **169,000/169,000** (3 collision-dependent under the 64K mirror;
  `--no-mirror` reproduces the historical 168,997), `v0.1-w1` / `-w3`
  1,200/1,200, `v0.1-w1 --forms EB` 200/200, the four `v0.1-w*evt` cells
  200 / 1,200 / 200 / 1,200, `v0.1-w1evt-biased` 1,200/1,200 (preserved),
  and the four HLT delay sweeps `s10-hltsweep-w{0,1}` **97/97**, **95/95**
  and `s13-hltsweep-w{2,3}` **46/46**, **45/45** = **283/283 — PERFECT since
  SM3 sitting 21**, `ucore_provenance.md` §82: **F56** deleted M6 (+4) and
  **F57** moved the read's completion clock to the cycle's own eval (+2).  It
  was 277/283 (RAISED from
  272 at SM3 sitting 19 by the MODEL's F53 leg, `ucore_provenance.md` §80.A —
  family E is the display one-shot's THREE pins, not just UBE, and the model
  had neither half: `E_ube` 30 → 0 on S16 and 5 → 0 on the sweeps).  Its S16
  leg is **1,305/1,371** (`sm3_s16_score.py --core sim`) — RAISED from 1,279 at
  SM3 sitting 21 by F56 (+14) and F57 (+12), leaving **39 `qop` + 30 `ARCH`**,
  both inside the model-only debt the USER FROZE 2026-08-05, with family B gone
  and the catch-all EMPTY; it was 1,279 with per wait 343 · 331 · 312 · 293.  (These were STALE here at
  92/95, 42/46, 40/45 — the pre-§26.7.6 figures — from the S15 cleanup until
  ucore U3 re-measured the model leg and found the quick reference disagreeing
  with `ucsim_t_provenance.md` §26.11's own delta row.  Corrected UPWARD.)
- **Timed, whole-program**: `sw/check_boot.py --timed 220`,
  `sw/timed_scenario.py` (18/0/9), `sw/timed_enter_replay.py` (154/154 x5),
  `sw/timed_ins_replay.py --raw` (rails 1312/1312, vs-chip 2624/2624),
  `sw/timed_wvec_gate.py` (88/88, +0.0 %), `sw/timed_lawcards.py`
  (**8 GREEN / 0 RED / 3 UNRESOLVED** — C6, C7, C11),
  `sw/timed_fuzz.py --evt-replay` (REGISTERED **1,339/1,702**, EVT
  **799/1,008**, COMBINED **2,138/2,710**, `INVALIDATED` **0** — RAISED again at
  wrfuzz W3.1 (the trap rides the recognition shadow) after the SM3
  sitting 26 by the **ILLEGAL-FORM STALL** (`ucore_provenance.md` §87.A: `F` is
  the OPR interlock and at `mod == 3` it has nothing to wait for, so the EU
  parks; ONE predicate, no opcode named, swept exact over 8,192 forms), 65 seeds
  gained and **ZERO lost over all 3,242**.  It was 1,282 / 789 / 2,071, and
  1,272 / 788 / 2,060 before SM3 sitting 23's BRK/TF trap; EVT/COMBINED had been
  RAISED by FIVE seeds at sitting 21 by **F57**, and the ucore gained the SAME
  FIVE, which is that landing's same-mechanism proof; they were 783 / 2,055.  The
  EVT and COMBINED figures moved TWICE on 2026-08-04 (INV-1's re-registration,
  then SM2's re-capture re-opening the full column at 363), then TWICE more:
  **+417 when H1 landed** (SM3 sitting 2, the re-entry recognition floor) and
  **+2 when the IE-restore law replaced it** (sitting 11); see below),
  `sw/timed_fuzz.py --seeddir sw/testdata/t4/b2-tranche/seeds`
  (**161/188** — RAISED to 161 at wrfuzz W3.1, from 159 at SM3 sitting 26; V5 is a
  standing REGISTERED FAILURE, not to be re-opened).
- **The `ucore`** (now the DEFAULT `--core`; these are the ucore's OWN ratchets,
  not the model's — see `ucore_provenance.md` §44 and §54.4):
  `check_core.py --opcodes all --cases 0` **169,000/169,000**;
  **`--suite-dir tests/v30/f4a_boundary` 160/160** and
  **`--suite-dir tests/v30/f0lock_tranche` 400/400** (both first measured
  against the ucore 2026-08-04, at the default flip; identical to the archived
  core's); **the 23 `v0.3` block-I/O forms (6C-6F + REP/segment variants)
  229,999/229,999 cycles AND arch** (2026-08-04, the ucore's first — this is
  where INM/OUTM is gated, and `timed_ins_replay`'s 1,312/2,624 is the bit-field
  INS `0F 31`/`0F 39`, not block I/O);
  `v0.1-w1`/`-w3` 1,200; `EB` 200; the four `evt` cells 200/1,200/200/1,200;
  `v0.1-w1evt-biased` 1,200; `check_boot.py --core ucore` 220 and 400;
  `ulockstep.py --golden all --cases 50` **17,350/17,350** (RE-MEASURED
  2026-08-10 at `399ba6729d`, every form LOCKSTEP, RTL receipt
  `0bb9b821dee96e1d…`; ⚠ it read **17,340** for part of 2026-08-09 while the
  RTL carried the 8F ghost READ and `sim/` did not, and **17,345** in
  `int_f3aa_repair_results_2026-08-09.md` row 8b, which was measured
  CONCURRENTLY with `077e10ac53` against a model that did not yet carry it —
  `standing_gates.md` §B has the erratum);
  ⚠ **THE NEXT THREE CANNOT RUN ON `fuzz-v2-on-relanding`** (with
  `timed_scenario`) — `gen_seq._v1_anchor_stop`, engine-independent, see the
  branch banner above:
  `timed_wvec_gate.py --core ucore` **88/88, +0.0 %** (the FSM core is 71/88);
  `timed_enter_replay.py --core ucore` **154/154 x5**;
  `timed_ins_replay.py --core ucore --raw` **1,312/1,312** and **2,624/2,624**;
  ⚠ **NOT MEASURABLE ON `fuzz-v2-on-relanding` — READ THIS BEFORE QUOTING THE
  NEXT FOUR FIGURES.**  Every v1 fuzz-bank figure below (`mc1`, `mc2`,
  `t30-raw`, `t30-brkem` = 3,242 seeds) requires REGENERATING each seed's image
  and hash-checking it against the banked `image_sha256`.  Plan **D9** makes the
  `0F` scrub UNCONDITIONAL at all three build sites, so on that branch every v1
  image regenerates to a different sha256: **3,157 GEN-DRIFT + 85 refused, 0
  scored** (measured; `--bank mc1 --limit 40` gives `GEN_DRIFT=40 SCORED 0`).
  The four banks are retired **by status, not by location** — nothing moved or
  deleted, `--include-superseded` still selects all 3,865 seeds — but the flag
  returns the SEEDS, **not the REPLAY**.  Re-deriving these numbers needs a
  checkout of a PRE-fuzz-v2 generator (`7e949925b7` or `master`), not a flag.
  `docs/notes/invalidation_ledger.md` **§ SUP-1**; `standing_gates.md` carries
  the corrected rows.  This is a SUPERSESSION, not an invalidation: no rig
  defect is alleged and the v1 `chip_rows` remain true silicon.
  `timed_fuzz.py --core ucore --evt-replay` REGISTERED **1,559/1,702**, EVT
  **934/1,008**, COMBINED **2,493/2,710** — **RAISED at wrfuzz W3.1 (the
  recognition-shadow law, +28 wr1 DIFF_BOUNDARY seeds) after SM3 SITTING 26's
  ILLEGAL-FORM STALL** (`ucore_provenance.md` **§87.A**, the SAME predicate as
  the model's leg: ONE new wire beside `f_wait` plus ONE flop, `opr_loaded`,
  SS-mapped at `0x175`; **66 seeds gained, ZERO lost over all 3,242** — all 34
  `TAIL_EXTRA` and 32 `PF_LOST`).  It was **1,502 / 920 / 2,422**, **RAISED at
  SM3 SITTING 25 by the
  ucore's BRK/TF SINGLE-STEP LEG** (`ucore_provenance.md` **§86**): five flops,
  no opcode named, the take on the existing boundary wire into the existing
  vector-1 door (`01D8` row 0 is `CONST 1`, row 2 is `CONST 2` — the trap and
  NMI are the SAME ROM entry two rows apart), and the SAMPLING boundary is ONE
  predicate, the `QS = 1` opcode pop, because a prefix retires with its own F
  pop.  The pipeline is FOUR deep and that IS the model's MEASURED floor of 3:
  `rise_sim = rise_rtl + 1` (8/8, engine vs engine) and silicon says 4
  independently at 0 row-diffs against ≥ 14,630 everywhere else in [1,7].  ALL
  ELEVEN PREDICTED SEEDS CLOSED and **0 were lost over all 3,242**.  It was
  1,490 / 918 / 2,408 (EVT had been RAISED from 913 by F57 at SM3 sitting 21,
  the same five seeds the model gained).  The ucore and sim columns are scored
  under DIFFERENT information and no lead is established
  — `standing_gates.md` §B.  Historically EVT read 913 (the sim was 782 — ~~on the REBUILT column the
  ucore beats the model by 105 seeds~~ **STRUCK as a comparison, see the rule
  below**; as banked it appeared to lose by 517, which was INV-1, now CLOSED by
  the SM2 re-capture; 910→913 = the IE law's +2 at sitting 11 + F53's +1 at
  sitting 16), COMBINED **2,403/2,710**,
  and `--seeddir …/b2-tranche/seeds` **181/188** (the sim is 161) — RAISED at wrfuzz W3.1, previously from
  172 at SM3 sitting 26 by the illegal-form stall.
  REGISTERED / EVT / COMBINED / b2 were **1,483 / 906 / 2,389 / 171** until
  **SM3 sitting 6** (`ucore_provenance.md` §66-§67) raised them by fixing a
  **TESTBENCH** defect, not an engine — `tb_v30_core.sv` committed `IOW` cycles
  into `mem[]`, so an I/O write to port P corrupted memory at address P on the
  RTL legs only; **seven of the NINE seeds `gaps` §T.2 calls "the ucore's own
  registered-bank residue" were the instrument, and that residue is now TWO
  seeds** (`mc1/721`, `mc2/584`).  EVT took a further +2 from F43.
  The four HLT sweeps are **97/97, 93/95, 45/46, 44/45 = 279/283** — **RE-MEASURED
  2026-08-10 at `399ba6729d`, unmoved, and the four survivors are the four
  family-D cells and nothing else** (`s10-w1/HLT.INT` at `(10, busstat)` and
  `(11, pins)`; `s13-w2/HLT.INT` at `(13, pins)`; `s13-w3/HLT.INT` at
  `(15, pins)`; **`HLT.RES` is 49 · 49 · 25 · 25, PERFECT at every wait**).
  ⚠ **`check_core --suite-dir` TAKES `--waits` AND IT DEFAULTS TO 0** — run the
  w1/w2/w3 suites with `--waits 1/2/3` or the sweeps read `97 · 0 · 0 · 0` and
  look like a catastrophic regression with every failure at `(1, 'seg')`. That
  mis-invocation cost a sitting twenty minutes and is recorded in
  `ghost8f_read_results_2026-08-09.md` §10.2. They have been 279/283 since SM3
  sitting 21** (F56 +4, F57 +2; `ucore_provenance.md` §82), and its S16 walk is
  **1,320/1,371** with **w0 at 372/372, PERFECT**.  **FAMILY B IS CLOSED IN
  BOTH ENGINES.**  The FOUR survivors on the sweeps are `w1.INT/8,9` ·
  `w2.INT/12` · `w3.INT/15` — **family D, which by USER DISPOSITION of
  2026-08-05 is SCORED VIA `tb_sys` and not on `tb_v30_core`**, where it is
  unfixable by construction.  §82.4 records that the sitting's own registered
  283/283 for the ucore was a MIS-DERIVED bar and is reported as a MISS.
  They were **273/283** —  They were 259/283 until SM3 sitting 6
  landed **F43** (the HALT display's decision tests the wake one stage further
  down the same pin pipeline, `int_p[1]` / `eu_unhalt_disp`; closed six
  `busstat` cells, 265), and 265 until sitting 16 landed **F53** — the display
  one-shot's three pins (address nibble / status nibble / UBE) as ONE law,
  authorized by the S16 display-walk cell (S1-S5 all 100 %), which closed
  families A (14 `seg`/`bus` cells), C (2) and E (5).  The 10 residual cells
  are 6 family-B (model-shared, one row late — the model owns the mechanism)
  + 4 family-D (a `nec_bus` two-sample-per-clock instrument class the default
  TB cannot score by construction — §77, falsifier recorded; NOT patched).
  Its standing figure AT THAT SITTING was **S16 display walk 1,294/1,371**
  (superseded — the current figure is 1,320/1,371, above) (`tests/v30/
  s16-dispwalk-*`).  It was 1,252 until sitting 17 landed **F54** — the NMI
  half of the HALT-announcement CANCELLATION law (silicon, 1,512 captures, no
  exception: the announcement at clock `H` is cancelled iff the pin rise
  `A <= H - K`, **K=3 on INT, K=6 on NMI**; invariant over waits, programs and
  IE) — which closed the 42-cell band **+42/−0** with no flop added.  §77.E's
  H7 attribution of that band is **WITHDRAWN**: it was never a recognition-
  timing question (the NMI vector read sits at the identical row on 36/42; the
  band scales with waits because `H` does).  **THE MODEL'S LEG LANDED AT SM3
  SITTING 18 (§79), AND §78.I's "three wrong ways" IS WITHDRAWN AS A RIG
  DEFECT**: `v30sim timed-run` keys its records by ARRAY POSITION and
  `compose_batch` keys the RTL batch by the golden's `idx`, which first differ
  on the S16 suites (`idx` is the DELAY, 141 cells non-composable, sets start
  at 0/1/4 with gaps).  Corrected, the model had `HLT.INT` **and** `HLT.RES`
  EXACT at all four wait levels and its NMI constant was `K=7` against
  silicon's `K=6` — **one clock, 24 cells**, closed by a display-only
  `cancel_halt_disp()` at `A+6` (the ucore's `eu_unhalt_disp` in the model's
  idiom; `halted_` and the `A+7` wake schedule untouched).  **The MODEL's S16
  leg at THAT SITTING was 1,249/1,371** (superseded — the current figure is
  1,305/1,371, above) (`sm3_s16_score.py --core sim`,
  343·331·300·275; it was 1,225, +24/−0 cell for cell).  **Family B is
  PARTITIONED and BOOKED** (§79.G): it is IDENTICAL in both engines cell for
  cell AND diff for diff, and it is TWO signatures — the wake's prefetch after
  a CANCELLED display (silicon puts it at `H+1`; the model is right at w1 and
  one clock late at w0) and the acknowledge pair's spacing (silicon spaces it
  7 clocks ANNOUNCEMENT to ANNOUNCEMENT).  Two falsifiers registered, no code
  written.  The model's other S16 classes, BOOKED not opened: `qop` 39 and
  `E_ube` 30 — **`E_ube` is F53's UBE half, which the model does not carry,
  and it is 5 of the model's 11 HLT-sweep misses.**
  These were 90/97, 88/95, 37/46, 34/45 = 249/283 through **U5**, and the move is
  two changes at once: **F51** landed (the HALT pseudo-cycle has no data phase)
  and the TB's composed-AD mask stopped hiding it.  §43.2's "17 cells no
  comparator on this TB can score" is RETIRED — F42 was refuted in fabric
  (§52.9), the cells are scoreable, and 10 of them now pass.
- **THE EVT COLUMN IS NOT A HEAD-TO-HEAD** (SM3 sitting 5, Codex concern 3;
  the rule is `standing_gates.md` §B, "HOW THE EVT COLUMN MAY AND MAY NOT BE
  QUOTED"). Under `--evt-replay` the model is handed `evt_directive` — the rig's
  schedule **plus the capture's own acknowledge positions and pushed CS:IP** —
  and REPLAYS; the RTL core is handed `evt_tuple`, the rig's directive alone,
  and PREDICTS. Each figure is a valid silicon-match ratchet for its own engine.
  **No delta, margin or ranking may be computed between the two EVT columns**;
  use REGISTERED (1,702 seeds, nothing from the capture handed to either) when a
  head-to-head is wanted. Every "the ucore beats the model by N" written of the
  EVT column anywhere in this repo is struck in that role.
  **The rig's `evt_hold` register is 12 bits since 2026-08-04** (F46 / gap R1)
  — in RTL, in the host tool, **in FLASH #4 and on the board** since SM2, proved
  on the wire (`EVT_CFG` round-trips 256 / 300 / 4,095) and ON THE PIN (2 INTA
  T1 rows at `hold=44`, 6 at 300, 12 at 600). `--rig-hold` keeps `reg8` to
  reproduce the 8-bit era and gains `applied`, which reads the seed's own
  `evt.hold_bits`.
- **INV-1 — THE FIRST INVALIDATION** (`docs/notes/invalidation_ledger.md`,
  opened 2026-08-04; the register the correctness-target directive names did not
  exist before). 760 banked EVT seeds asked for a pin hold of 300 that the rig's
  8-bit register truncated to 44, so a PREDICTING engine was scored against a
  capture taken under a directive it is never given. Their `chip_rows` are true
  silicon and are RETAINED; **nothing gates on them**. The exclusion is DERIVED
  from the record (`timed_fuzz.f46_invalidated`), not from a list or a rename —
  nothing was moved and nothing was deleted, because the same files are the
  `check_fuzz_bank` 3,242-seed corpus. **CLOSED 2026-08-04 by session SM2**
  (`invalidation_ledger.md` § CLOSURE, `ucore_provenance.md` §59.7): all 760
  re-captured on FLASH #4 at their banked hold of 300 — 0 errors, 0 GEN-DRIFT,
  `evt_fired` 760/760 — the originals archived byte-identical at
  `sw/testdata/inv1-archive/`, and the entries rewritten IN PLACE so
  `f46_invalidated` goes False by arithmetic with no list edited. The column is
  **UN-SUSPENDED**. Under the applied 44 the part entered its handler ONCE in
  732 of 760 seeds; under the banked 300 it enters two to five times.
  Note also: the **w1evt-biased precedent is an archive-by-rename, NOT an
  invalidation** — §24.7 says the old suite is *not retracted* and it is still a
  live gate. It supplies the habit, not the disposition.
- **THE THREE-REGISTER LEDGER — `INV-n` / `SUP-n` / `EXC-n`**
  (`docs/notes/invalidation_ledger.md`). Filing one as another says something
  untrue, so the vocabulary is fixed: an **INVALIDATION** needs a NAMED RIG
  DEFECT and leaves every gate set permanently (`timed_fuzz.f46_invalidated`);
  a **SUPERSESSION** alleges NO defect, is per campaign, and comes back with
  `--include-superseded` (`bank_status.is_superseded`); an **EXCLUSION** alleges
  NO defect, is **per seed**, and takes the seed out of every scored rate's
  **numerator AND denominator** and out of the replayed bank, back with
  `--include-excluded` (`bank_status.excluded_of`). Live entries: INV-1
  (CLOSED), INV-2, SUP-1, **EXC-1** (two banked runtime-8080 captures in `fz2e`),
  **EXC-2** (the three in the FLASH #13 corpus, no manifest record — the reason
  is `fz2_corpus_prereg_2026-08-08.md` §34.6). **Every drop is PRINTED, never
  silent**, and that is itself a falsifier.
- **`sw/check_fuzz_bank.py` is GREEN AGAIN since 2026-08-11 (`a54cc27454`):
  `PASS / 621 / stable 621 / improved 0 / worse 0 / gen_drift 0 / regen_err 0 /
  float-floor 0 / new-sig TIMING 0`, ~266 s — BY RE-DERIVING THE BANK'S
  DERIVED COLUMN, NOT BY A REPAIR.** One-line history: it was `PASS 621`
  **vacuously** (banker and checker shared one defect) → **RED `FAIL / 621 /
  stable 531 / worse 90` at `09ec85e4bb`** when the classifier was fixed →
  **green at `a54cc27454`** when the column that defect wrote was recomputed by
  the fixed classifier. **The three `stable` counts are three different
  measurements and two of them share a string — quote the instrument AND the
  column, never the string.** The re-derivation is pre-registered at
  `537c6697c5` (`docs/notes/cfb_rederive_prereg_2026-08-11.md`), archived
  byte-identical BEFORE touch at `77ecf565d9`
  (`sw/testdata/cfb-tier-archive/`), applied by `sw/cfb_rederive.py --apply`,
  and dispositioned as `invalidation_ledger.md` **ERR-1 — a FOURTH register
  opened for DERIVED columns** (not an INV: no rig defect, `gen_drift 0`,
  `regen_err 0`, `chip_rows` hash IDENTICAL to the archive; not a SUP:
  something WAS wrong with the column; not an EXC: no seed left any
  population). **The gate is green BY ARITHMETIC — no list edited, no seed
  excused** — and **the 90 movers are NOT erased**: they stay itemized in
  `cfb_tier_prereg_2026-08-11.md` §R.2 and in each entry's own `rederive`
  block. Both registered clauses MET, scored on a full dry run BEFORE the
  apply: the 90 land EXACTLY on §R.2's committed after-column (0 extra, 0
  missing; cross-checked 90/90 against the RED run's own `WORSE` lines) and the
  531 non-movers' verdicts are byte-identical (subs byte-identical on 521, the
  10 exceptions registered in advance). Untouchable fields proved identical
  621/621 by two independent checks. ⚠ **The SUPERSEDED v1 banks (3,242 seeds)
  STILL carry the defective column and cannot be re-derived on this branch
  (D9) — their `replay_verdict` may not be quoted as anything else.**
  *The RED registration follows, kept because a ratchet is only readable
  against its own history.* The tier-domain fix (banked `"soup"/"raw"`
  was fed into `fc.Ctx`, whose domain is `'A'/'B'`, so every tier branch in the
  replay was DEAD, arch-dump comparison included) revealed that
  `fuzz_bank.py:261` wrote the banked `replay_verdict` by calling the SAME
  defective `replay_classify` — banker and checker shared the defect, so
  `stable 621` measured the defect's determinism, not the bank. The 90 movers
  are itemized in `cfb_tier_prereg_2026-08-11.md` §R.2 (55 soup
  `done_mismatch` come-alive, 35 raw window come-alive = `float-floor 35`);
  `gen_drift 0 / regen_err 0` — no rig defect. The live arch column is CLEAN:
  123 soup seeds reach the dump comparison, 0 differ. `new-sig TIMING 148` is
  the registered instrument effect (tier is hashed into the signature).
  ~~Re-deriving the banked verdicts on the mapped classifier is BOOKED, not
  taken~~ — **TAKEN 2026-08-11 under its own pre-registration, exactly as this
  clause required; the condition was MET, not waived.** ⚠ **Three numbers are
  all true and they are not the same number**:
  **623** banked FILES on disk (`fz2c` 480 + `fz2e` 143), **−2** EXC-1
  exclusions, **= 621** REPLAYED; and **3,865** is the pre-SUP-1 population,
  still one flag away and still FAILING for D9's reason. *(Superseded: the
  2026-08-10 registration at `399ba6729d` read `PASS / stable 621 / worse 0`;
  `6b044475c7`'s "PASS/623" predates EXC-1.)*
- **`sw/fz2_w1.py bars` is the fuzz-v2 standing scorer — 11/11 MET since A-14**
  (`sw/testdata/fz2/fz2_bars.json`, 2026-08-10T02:50:20Z, offline,
  ~25 s), with `sw/fz2_w1.py lint` **PASS / 0 hits / 48 stratum rows** beside it
  (it cross-checks the campaign document against the code — **if a doc edit
  trips it, fix the doc**). It was **10/11, C-1 MISSED on E-1c alone** at
  `undispositioned` **25** of 3,840.
  ⚠ **E-1c IS 0 BY A RE-REGISTRATION OF ITS MEANING, NOT BECAUSE THE 25 STARTED
  DUMPING** — **AMENDMENT A-14**, on the USER's ruling of 2026-08-09: *"If these
  seeds are matching between real CPU and core, then it doesn't matter if they
  aren't producing the final state dump."* UNDISPOSITIONED now means *no dump
  AND no explanation **AND the two legs do not agree***, and the sixth
  disposition `ROW_MATCHED` (`sw/fz2_rowmatch.py`, its own falsifier) took all
  25 — each at `win = 4000`, `bad_rows` 0, `flick` 0. **THE REACHED RATE DID NOT
  MOVE**: 3,513 dumps, all four rate cells byte-identical (98.54 / 83.92 /
  98.89 / 84.23). The 25 are **DISPOSITIONED, NOT EXPLAINED**; `mech_census`
  still carries `BUDGET` 12 · `NEAR` 9 · `OTHER` 4. Prereg §36–§37.
  C-1's two RATE clauses read **MET and VALIDATED**
  on the disjoint `fz2v`/960 — soup **98.12 %** ≥ 90.0, raw **80.83 %** ≥ 75.0 —
  ⚠ **and neither clears the ORIGINAL bar (99.0 / 95.0)**: what is validated is
  that the *re-registered* bars hold on a population that did not set them.
  **C-3 reads MET** (A-11 → A-12 → **A-13**), **C-6 reads MET** on the FLASH #13
  corpus (`hold_rows_exact` 4,638 / `hold_rows_off` **0**, against 4,636 / 2 on
  the F12 one). Full table, the **six** dispositions (the five declared discard
  classes plus A-14's `ROW_MATCHED`) with their falsifiers, and the corpus's own
  caveats: `standing_gates.md` §B, *THE fuzz-v2 CORPUS*.
- **`python3 sw/r7_lint.py` IS A STANDING GATE (always-on, 0.2 s, exit 0/1/2).**
  It checks that the shape §73 closed R7′ with is still the shape in the tree:
  **(a)** no undeclared live-`READY` carrier crosses BIU → EU (one declared
  exception, `eu_rd_edge`; two declared unresolved, `eu_slot_busy_n` and
  `q_ripe_lead_n`), and **(b)** no `stop` in the EU's twelve-position chain is
  gated by one — and (a)'s exception is deliberately **NOT** excepted in (b).
  At `399ba6729d`: **PASS — 20 nets / 1 carrier / 3 tainted / 51 `stop` sites /
  0 violations.** It exists because a comment is not a gate: `5403671558`
  crossed the invariant in three places with the comment still standing and no
  gate saw it. ⚠ **It has a KNOWN FALSE-POSITIVE MODE on constant-folded code** —
  it traces TEXT, not values, so a tie-off that makes a carrier constant-0 still
  trips (b) where the name survives (5 such artifacts measured on the spike's
  build 1). Over-reports, never under-reports; **Quartus is the authority on a
  folded tree**. ⚠ **AND A `r7_lint` PASS IS NOT A TIMING CLAIM**: the 8F ghost
  FEED passes it — its route to the loader chain is register `D` pins, outside
  the `stop` charter — and **G6 measured 15.3 MHz on it**.
- **`sw/ss_lint.py --core ucore` exits 0** — ⚠ **CURRENT, RE-MEASURED 2026-08-11
  on `fuzz-v2-on-relanding` at the KM landing: `SS_VERSION` 0x8D / `SS_COUNT`
  226 / `SS_TAG` 0x8DE2, 214 flops, 0 UNMAPPED** (the 0x8D bump is the wave-4
  landings'; KM itself added no flop). *(Superseded: 2026-08-10 at
  `399ba6729d` read `SS_VERSION` 0x8C / 224 / `SS_TAG` 0x8CE0, 212 flops)* (`SS_BIU_COUNT` 101, `SS_EU_COUNT` 122; BIU 83 flops → 83
  mapped, EU 129 → 127 mapped + 2 whitelisted, 1 sim-only exempt). The map
  reached 0x8C/224 at the **8F ghost READ** (`d1d9f168d4`: SSA `0x176` plus the
  `ss_addr_of` hole removal, 0x8B/223/211 → 0x8C/224/212), and `9c98117a03`'s
  `INT.F3AA` repair left `v30u_ss_pkg.sv` untouched. *The superseded text
  follows, because a ratchet is only readable against its own history:* since
  SM3 sitting 26 at
  **`SS_VERSION` 0x87 / `SS_COUNT` 219 / `SS_TAG` 0x87DB, 205 flops, 0
  UNMAPPED** (§87.A APPENDS one address, `SSA_E_OPR_LOADED` at `0x175` — ONE
  BIT, the OPR-valid interlock that decides whether an `F` row sourcing OPR has
  anything to wait for; `SS_EU_COUNT` 117 → 118).  It was, since SM3 sitting 25,
  **`SS_VERSION` 0x86 / `SS_COUNT` 218 / `SS_TAG` 0x86DA, 204 flops, 0
  UNMAPPED** (§86 APPENDS one address, `SSA_E_BRK` at `0x174`, carrying the
  BRK/TF arm's five flops).  It was, since SM3 sitting 21,
  **`SS_VERSION` 0x85 / `SS_COUNT` 217 / `SS_TAG` 0x85D9, 200 flops, 0
  UNMAPPED** (F56 DELETED `pf_land`; `SSA_B_PF_LAND` / `9'h038` is the map's
  **first MID-REGION retirement** — a HOLE `ss_addr_of` steps over, with NO
  symbol renumbered).  The history below is the U4/F49 state and is superseded
  in its numbers, not in its reasoning. (U4/F49). It was KNOWN-RED through
  U3 because five architectural flops were absent from the ucore's save-state
  map; they are mapped now, `SS_VERSION` **0x83** / **222** addresses /
  `SS_TAG` **0x83DE** (bumped at SM3 sitting 3 by F52, the H1 floor's four
  BIU flops at 0x066-0x069), census **205 flops, 0 UNMAPPED** (it was 223 until U4
  pass 3: the enable-form refactor made 22 of the 24 whitelisted per-edge
  temporaries combinational BY DECLARATION, which is exactly the fix U3 booked
  and could not take while the RTL was frozen — the MAP did not move). It is now
  the DEFAULT leg (`sw/ss_lint.py`, no flag). The `--core fsm` leg is unchanged,
  still exits 0 (203 addresses, 181 flops, 0 UNMAPPED), and is now an on-demand
  archived gate. The two maps are NOT stream-compatible.
- **THE COMPARATOR CHANGED AT U5, AND IT MOVED THE FROZEN FSM CORE'S NUMBERS
  DOWN.  Read this before quoting any FSM RTL figure.**  `tb_v30_core.sv`'s
  composed-AD mask used to substitute the retained nibble for A19-16 across a
  HALT display and its T1, whatever the core drove there.  The goldens carry
  `data_ps(2)` = `{md, ie, CS}` on those rows — **`6` in all 200 `HLT.INT`, `2`
  in all 200 `HLT.RES`** — and **both cores drive `0`**; the mask read correct
  only because the retained nibble is the previous CS fetch's PS, which is the
  same value by construction.  In fabric there is no retention and it does not
  (§52.9).  Mask removed (engine-neutral, it names no core signal), **the ucore
  FIXED (F51)** and **the frozen FSM core NOT** — this campaign does not touch
  its RTL, because its flashed A/B bitstream is built from HEAD and §52.8 says
  it must stay that way.  On the corrected comparator:
  `check_core.py --core fsm --opcodes all --cases 0` is **168,400 / 169,000**
  (it was 169,000; the delta is exactly the 600 `HLT.INT`/`HLT.RES`/`HLT.NMI`
  cases, 0/600) and its four HLT sweeps are **0/97, 4/95, 5/46, 7/45 = 16/283**
  (they were 216/283, measured for the first time at U5).  **The defect predates
  the instrument change by every commit in the repo**; nothing was made worse,
  something was made visible.  It is a ONE-LINE fix in `v30_biu.sv`'s `ad_o` /
  `ad_oe_ps` and it is deliberately NOT taken.  **THE DISPOSITION IS NOW TAKEN:
  the FSM core is ARCHIVED** (2026-08-04) with this defect present and unfixed —
  `docs/notes/fsm_core_archive_2026-08-04.md`.  Quote **168,400 / 169,000** and
  **16 / 283**, with the comparator named, or do not quote it.
- **U4 additions**: `sw/check_ab_sim.py --core {fsm,ucore}` — the core inside
  the REAL integration (system_large) vs the chip's own boot capture; both legs
  **MATCH over 187 rows**. (It had been unbuildable since 2026-07-13; three
  files had drifted out of its RTL list.) `sw/gen_ucore_qsf.py --check` gates
  that `hdl/nec_test_ucore.qsf` is a faithful derivative of `nec_test.qsf`, i.e.
  that the two A/B bitstreams differ by the CORE and nothing else.
- **THE RE-LANDING CAMPAIGN IS CLOSED AT 17 OF 19 (2026-08-09).** `5403671558`
  was a 19-mechanism landing that took G6 to **19.42 MHz**; it was re-landed
  mechanism by mechanism, each with its own pre-registration, gates and control
  build. L1 (`7647e604e0`) landed 16 and the **8F ghost READ** (`d1d9f168d4`)
  landed the 17th. **The two that did not land are booked with the block
  characterised and the mechanism NOT condemned**: (i) **the 8F ghost FEED is
  UNLANDABLE AS DESIGNED** — it gives §73's one declared live-`READY` carrier a
  SECOND consumer and that consumer is the loader chain, which breaks the
  exception's own terms; `r7_lint` PASSES on it and is right to, and **G6 is the
  falsifier at 15.3 MHz**. It re-opens on (a) a fabric with margin for a 55–63
  level single-cycle cone, (b) **a REFORMULATION in which the successor's pop
  does not ride the data edge — a different mechanism, to be measured as one**,
  or (c) evidence it buys something, which is currently NOTHING. (ii) **the
  `PF_LOST` MODR/M hold is DEAD BY CONSTRUCTION WITHOUT (i)** and re-opens iff
  (i) does, to be re-derived from `5403671558` rather than resurrected.
  **THE PRECEDENT: PER-MECHANISM BENEFIT, MEASURED BEFORE THE BUNDLE IS
  BELIEVED.** The READ alone reproduces **100.0 % of the full family's measured
  benefit** (`BOUND WARNINGS` 2 → 0, `fz2c/406000` DIVERGE → EXACT, COMBINED
  11/14 → 12/14, **25,200 improved rows against the family's 25,188**) on a
  retention bar registered at ≥ 70 % **before the amputation was scored**. *A
  bundle's benefit is not evidence for any member of it.*
- **SYNTHESIS: G6 IS GREEN — BUT READ §73 BEFORE QUOTING ANY Fmax.**
  ⚠ **CURRENT BAND ON `fuzz-v2-on-relanding`: CONTROL 39.37 MHz / +5.853 ns /
  ALMs 12,340 (29 %) (receipts `ab9c5de161457bc9…`, `4f7483a65515307d…`) and
  RETENTION 39.83 MHz / +6.143 ns / ALMs 12,182 (29 %) (receipts
  `69f8614f379d1ba8…`, `4c39c7928d31576c…`), TNS 0.000 on every domain setup
  AND hold, 0 errors, 0 latches, 0 `lpm_divide`, two draws each.** This
  SUPERSEDES the SM3-sitting-27 band quoted below (47.85 / 45.72 at 27 %) — the
  ucore has grown across the re-landing campaign and the band fell ~6 MHz.
  Three structural passes now stand between the ucore and timing closure, and
  each one was a cone that had to come out of the EU's twelve-position chain:
  the ENABLE-FORM refactor (`ce` onto the register enable ports), `srst` out of
  the next-state cone (§52.2/52.3), and — **SM3 sitting 12, §73** — the read's
  DATA-EDGE PSW load off the head of that chain onto the `psw` register's own
  `D` pin. **Without the third, HEAD measured Fmax 19.42 MHz on the DEFAULT
  build**, worst setup −20.254 ns, TNS −13,129.815, with 20,000/20,000 failing
  paths launching from `system_large|c_ready_q` into `v30u_eu` at 62–63 logic
  levels. **G6 WAS RED AT HEAD AND NO GATE SAW IT: the standing set has no
  Quartus leg.** Run a control build after any `hdl/rtl/ucore/` landing.
  **CURRENT BAND (SM3 sitting 27, 2026-08-05, both configurations, from a clean
  `db`): control 47.85 MHz / +8.602 ns / ALMs 11,147 (27 %), receipt
  `3cdd586554780bb4…`; retention 45.72 MHz / +7.181 ns / ALMs 11,165 (27 %); TNS
  0.000 on every domain setup AND hold, 0 errors, 0 latches, 0 `lpm_divide`.**
  It was control 45.89 / +8.493 and retention 45.87 / +8.802 at sitting 12
  (11,133 / 11,122 ALMs), and the earlier U4
  figures (26 % ALMs, 45.56 MHz, `.sof cdf5edee00…`, `.rbf 91697c83b3…`) are
  that era's and are not this tree's — for the CURRENT bitstream see the board
  line below. ⚠ **ONE GREEN BUILD IS NOT CLOSURE and the multi-seed worst-of-N
  gate is NOT BUILT**: every timing figure in this ladder from §52 onward is ONE
  DRAW of a distribution nobody has characterised, and the same tree has drawn
  19.42 and 45.91 MHz (§74.4, §74.4a — Analysis & Synthesis is not reproducible
  run to run; the REGISTER counts are, the COMBINATIONAL counts are not).
  `nec_test.sdc` carries the 4/3 CE multicycle with its
  falsifier written beside it. **The whole sim ladder was re-scored THREE times across
  the two structural passes with ZERO DELTAS**, plus `--ce-div 4
  --ce-hold-check` = `CE_HOLD_VIOL 0` on all 347 forms.
- **IN FABRIC (U4 pass 3, §52.5-52.8).** FLASH #1 + FLASH #2, both from HEAD,
  both through `sw/safe_flash.sh` with its VERIFY leg; task #31's flash debt is
  **DISCHARGED**. First light **800/800 on all three legs** (chip-vs-golden,
  core-vs-chip, core-vs-golden). **The §48.4 priority tranche, all four legs:
  the ucore in fabric is 176/178 (98.9 %) against 59/178 for the FSM core built
  from the same HEAD — V0 through V5 ALL MET**, including V3 at ZERO seeds
  apart. A second frozen 500-seed population scores **435/449 (96.9 %)** in
  fabric with 0 errors in 1,000 captures. Scored pairwise, fabric and Verilator
  are **identical on 200/200** for BOTH cores, which closes §51.8b: its 62/178
  was entirely the stale 2026-07-30 bitstream.
- **TWO FINDINGS OUT OF THE FABRIC LEGS.** (a) **F42 was REFUTED** — its
  registered prediction was that the 17 uncountable HLT cells would PASS in
  fabric; they failed, the sweeps scored 29/283 there, and the socket control on
  the identical driver reproduced the golden 49/49. The ucore drove the HALT
  display's upper nibble differently from silicon (`0x0AD8A` where the golden
  has `0x2AD8A`) and dropped it a row early. **CLOSED at U5 by F51** — in fabric
  on FLASH #3 the sweeps are **143/283** and **ZERO cells still carry the
  signature**. (b) **the FROZEN FSM CORE HAS REGRESSED 104 SEEDS** on the
  random-wait axis between the 2026-07-30 build (163/178) and HEAD (59/178, in
  fabric and in Verilator alike). Not the ucore's, and no standing gate sees it.
- **THE FABRIC SCORER IS STRICTER THAN THE TB, BY ONE CLASS — the INTA float
  (U5 §56).** `sw/u4_f42_fabric.py` scores **143/283** where the TB scores
  259/283 on the same RTL, and **116 of 116** fabric-only failures are INTA
  rows: the chip's pads RETAIN the previous data phase at an INTA's T1 and the
  core's AD inside `system_large` is an internal tri-state Quartus resolves to a
  mux, so there is nothing to retain. The plan's registered **risk #4**.
  `sw/check_ab_hw.py` already excludes float-retention rows for this reason and
  is 800/800 on the same bitstream. **Do not "fix" this by swapping scorers** —
  that would be choosing a comparator after seeing a result. `HLT.RES` in fabric
  is IDENTICAL to `HLT.RES` offline cell for cell, which is the control that
  makes the class readable.
  **X1's §56.3a INTERVENTION RAN OFFLINE 2026-08-04 AND BOTH BARS ARE MET**
  (`ucore_provenance.md` §58.6). New instrument `hdl/tb/tb_sys.sv` — the
  Verilated `system_large`, image loaded and event armed through the AXI bridge
  exactly as the ARM does it — driven by `sw/x1_retention.py` through
  `emit_suite`'s own driver. **Its baseline was 143/283, the FABRIC number
  exactly, with 116 base-only failures all on INTA rows**; with
  `X1_AD_RETENTION` the total was **259/283**, 116 closed, **0 survivors**, and
  **0** cells differing from their offline result.
  **RE-MEASURED ON REBUILT BINARIES AT SM3 SITTING 6 (§67.6-§67.7): base
  146/283, ret 265/283, 119 base-only, 119/119 INTA, 119 closed, 0 survivors,
  0 differing — BOTH BARS STILL MET.**  Two things to carry: (a)
  `x1_retention.py capture` **binds to `hdl/tb/obj_dir_sys{,_ret}/tb_sys` and
  rebuilds NOTHING** — the binaries were stale by a day and the tool reported a
  false "6 survivors" until they were rebuilt by hand — ⚠ **BOTH CLAUSES ARE
  SUPERSEDED**: `tb_sys` gained a real `build()` with a declared dependency set at
  §69.2 and an ERA GUARD at §83.0, and the era guard REFUSES to score a column
  taken on another tree, which is the structural answer to both; (b) with F43 in
  the RTL the Verilated
  integration was 146 where **FLASH #3's bitstream was 143**, so **no fabric
  figure could be quoted against that tree's `tb_sys` until a re-flash** —
  ⚠ **DISCHARGED**: FLASH #6, #9 and #10 have been taken since, and on FLASH #10
  the `tb_sys ret` column and fabric agree on **all 1,654 cells across both
  populations, PASS/FAIL and coordinate alike** (see the board line below). The attribution is still NOT
  ESTABLISHED — §56.3a's bar is written on fabric numbers plus a socket control,
  and no board was touched. **The fabric leg is SM2's.** The retention is
  applied on the OBSERVATION path (`hb_ad_sample`), not as a keeper on
  `core_ad`; the deviation and why is written into `system_large.sv` beside it.
  **THE FABRIC LEG WAS ATTEMPTED IN SM2 AND IS `BLOCKED`, NOT REFUTED**
  (`ucore_provenance.md` §59.7.1). The BASELINE reproduces on FLASH #4 —
  **143/283, cell for cell and form for form, 116 fabric-only, 116/116 on an
  INTA T1 row**, socket control **49/49**, boot MATCH 800 ×3 — but the
  INTERVENTION cannot be SYNTHESISED: `core_ad === 1'bz` is a four-state test on
  an internal tri-state and Quartus 17.1 folds it to a constant, deletes the
  hold register for want of fanout, and returns a bitstream identical in
  function to the baseline. Demonstrated in isolation (the construct alone gives
  *"No output dependent on input pin clk"*). A §59.3 liveness test was
  PRE-REGISTERED for exactly this, so the after-leg was NOT RUN and FLASH #5 was
  NOT taken — an inert instrument would have reported "116 survive", which reads
  like a refutation. **C11 stays NOT ESTABLISHED.**
  **THE BLOCKER IS GONE AND THE LEG IS RUN — SM3 SITTING 12, §73.8/§73.9.**
  Both cores carry **`output [19:0] AD_OE`** (the pads' own output enable, a
  wire off the expression the `assign AD[...]` statements already used;
  user-approved 2026-08-04; the ARCHIVED FSM core's exception is
  `fsm_core_archive_2026-08-04.md` §6a), the retention model is keyed onto it,
  `=== 1'bz` is GONE, and **it synthesises**: `system_large`'s own A&S
  registers **25 → 46 (+21, measured per entity on six builds; §69.3's "+20" is
  the whole-design figure and that wobbles by ±1 in an unrelated MiSTer
  module)**, `core_ad_hold` absent from `Registers Removed During Synthesis`.
  Sitting 8's TIMING blocker (retention at 20.25 MHz) is **CLOSED by §73's R7′
  pass**: on this tree the retention build is **45.87 MHz / +8.802 / TNS
  0.000**.  **FLASH #6 TAKEN 2026-08-05** and the fabric leg RUN:
  **`x1_fabric baseline --leg fab_f6` = 265/283, the OFFLINE COLUMN EXACTLY —
  119 of 119 INTA-class cells CLOSED, 0 survivors, the 18 remaining cells the
  SAME 18 named in the pre-registration with the SAME first-divergence
  coordinate, and 0 PASS/FAIL disagreements and 0 differing coordinates against
  the `tb_sys ret` leg over all 283.**  Socket control **49/49**, first light
  **MATCH 800 ×3**, `use_core=0` chip proof **MATCH 800** after everything.
  **BOTH §56.3a BARS MET.  C11 IS ESTABLISHED** — the INTA pad-float
  attribution is a FINDING.  Note **C11 is ambiguous in this repo**: this one is
  the Codex review item (`ucore_campaign_verdict_2026-08-04.md` §(g));
  `timed_lawcards`' `C11` is the unrelated BIU card *LC4 `owns_slot`* and is
  untouched.  **What is still unexplained is the 18 survivors** — 4 `w0`
  `busstat` (model-shared) and 14 `seg`/`bus` at the top of each sweep's `d`
  band (§67.3) — now the ONLY fabric residue on this population, core-owned,
  and diagnosable offline because fabric and TB agree on them cell for cell.
- **R7 / R7′ — BOTH CLOSED (§70, §73).**  R7 (*"the CE multicycle is collected
  by hierarchical name and 20 flops moved 81 registers out of it"*) was
  **REFUTED at sitting 9**: the two figures were different STAGES of one flow,
  the collection GREW stage for stage, and **`nec_test.sdc` was NOT edited and
  must not be widened on R7's account.**  **R7′** — the real thing — was
  *`READY` reaches the EU's next-state cone single-cycle at 55–63 logic levels
  and closure depends on whether physical synthesis happens to break it*.  At
  HEAD it had **SWAPPED SIDES**: the DEFAULT build measured **19.42 MHz /
  −20.254 / TNS −13,129.815**, 20,000/20,000 failing paths from
  `system_large|c_ready_q` into `v30u_eu`.  **CLOSED at sitting 12 BY ONE MUX**:
  `eu_rd_edge` is the only carrier of the live READY pin into the EU and its
  single consumer seeded `psw_n` at the head of the twelve-position chain; it is
  now on the `psw` register's own `D` pin, gated by the register-only
  `row_blocked`, with TWO `ifndef SYNTHESIS` falsifiers kept beside it.  Ladder
  **ZERO-DELTA at the seed**, no flop added or removed on any entity.  A first
  form without `row_blocked` was built, worked, and was **REVERTED by its own
  pre-registered falsifier** — `mc2/2788`, where a second read is outstanding
  while an earlier one already sits in the completed-read store, so the row is
  NOT blocked and runs on the same clock.
- **THE BOARD CARRIES FLASH #18 SINCE 2026-08-11** (pre-registration
  `7c4a639ca4` + scorer/amendment-A-1 `30b46f07d3`, both committed **before
  board contact**; results `docs/notes/fz2_flash18_results_2026-08-11.md`) —
  `nec_test_ucore.sof` **`b2a1fe5f83167fbf…`**, `.rbf` **`ecda4b90c646ba49…`**,
  built from `30b46f07d3` **WITH `X1_AD_RETENTION=1`**, through
  `sw/safe_flash.sh` with its VERIFY leg (ok try 1); `flash_log.jsonl`
  **20 → 21 entries**.  **IT IS THE FIRST BITSTREAM TO CARRY `KM` AND
  `phantom-T1`, AND BOTH ARE CONFIRMED SEAT FOR SEAT.**  KM's three seats
  **CLOSED 3/3** (`fz2c/404041` 2,437 → 0, `fz2e/501066` 572 → 0,
  `fz2e/513019` 2,843 → 0); phantom-T1's three **COLLAPSED 3/3 to
  `bad_rows == 1`, `flick 0`, `first_bad` exactly 243 / 234 / 583** — the POINT
  prediction, **and `bad_rows == 0` was registered as a FINDING, not a
  success**, because the ucore has ONE status value per CPU clock where silicon
  has TWO.  Corpus **113 → 110 failures of 3,839** = the registered primary
  point TO THE SEED; **ZERO unregistered ledger membership flips** against a
  10-seed budget (F17 used 7); `fz2c/404040` absent; **14/14** named non-movers
  unmoved; **0** unregistered first-divergence moves in either direction.
  **G6: CONTROL 40.13 MHz / +6.333 ns / 12,246 ALMs (29 %), receipt
  `6d07f59376f86196…`; RETENTION 38.82 MHz / +5.492 ns / 12,276 ALMs, receipt
  `277d5ccf0f8b9398…`**, TNS 0.000 setup AND hold every domain, 0 errors /
  0 latches / 0 `lpm_divide`.  **The fabric era guard PASSES without the
  bypass** (87/88, the `.qsf` the one §70.7 exemption) and the closing control
  is **260/260 = 100.0 %**, `first_bad` identical on 110/110.  Directed-cell
  spot-checks: **0 chip-column movers** on `tf0f` (48 cells) and `ie-pinfall`
  (40), `tf0f score` **chip == core 0/512 on all six columns**, ie-pinfall
  `n_inta` **30** / `ack_off` **40** / `ack_off_hlt` **40** reproducing
  ack-wake's prediction exactly, six invariant columns **0/1,920**.
  ⚠ **AN E-6 HARD STOP FIRED AND WAS OBEYED — `quartus_gate.py` COULD NOT MAKE
  A RETENTION BUILD.**  Its `build()` ran `quartus_sh --flow compile` with **no
  `--verilog_macro`** and **never read `X1_AD_RETENTION` from the
  environment**: `X1_AD_RETENTION=1 python3 sw/quartus_gate.py` was
  **accepted-and-ignored** and silently yielded a CONTROL build whose `.rbf` is
  byte-identical to the control's.  The receipt's DERIVED label caught it
  (`aa3ca3e028dff7d2…` — label says RETENTION, configuration says
  `CONTROL/DEFAULT`) and **nothing was flashed on it**.  The bad receipt is
  RETAINED and named.
  ✅ **CLOSED 2026-08-11 — `sw/quartus_gate.py --retention` EXISTS AND THE
  ENV-VAR FORM IS REFUSED** (prereg `a05af666aa`,
  `fz2_f18_housekeeping_results_2026-08-11.md`).  The flag runs the recorded
  four-stage recipe (`quartus_map --verilog_macro=X1_AD_RETENTION=1` →
  `quartus_fit` → `quartus_asm` → `quartus_sta`, then the existing parse);
  `--dry-run` prints the stages without building; and
  `X1_AD_RETENTION=1 python3 sw/quartus_gate.py` **now exits 2 naming this
  finding** — accepted-and-ignored became refused-with-reason.  `configuration`
  is still **DERIVED from the reports and never from the flag** (what the flag
  asked for lands in `build.configuration_requested`), which is what keeps the
  FLASH #18 check alive.  Falsifier **`python3 sw/test_quartus_gate.py`
  (75/75, no Quartus needed)**, non-vacuous on six nulls including
  *"--retention accepted and ignored"*.
  ⚠ **THE MACRO IS PASSED UNQUOTED** — the documents' `--verilog_macro="…"` is
  SHELL syntax and `subprocess` has no shell; all twelve archived retention
  receipts record the compiler receiving `--verilog_macro=X1_AD_RETENTION=1`.
  ⚠ **THE FLAG IS TESTED, NOT YET EXERCISED**: no bitstream has been built with
  it.  *Falsifier for the next retention build*: its receipt must self-label
  `RETENTION (X1_AD_RETENTION=1)` with an `.rbf` differing from the control's
  (E-6 and E-9, unchanged).
  ⚠ **THE RETENTION-VS-CONTROL SIGN INVERTED BACK: −1.31 MHz**, after five
  consecutive draws above (#13 +0.46, #14 +1.50, #15 +2.24, #16 +0.12,
  #17 +0.71).  The flashed build clears this sitting's own 38.0 STOP by only
  **+0.82 MHz**.  Reported, not explained; `standing_gates.md` §A governs.
  ⚠ **ERRATUM AGAINST FLASH #17 §5.3 — its "unexplained one-sided +1..+5
  residue" IS `flick`.**  `sw/fz2_ledger.py:219` writes each entry's
  `diverging_rows = bad_rows + flick` while `:209` accumulates the corpus total
  as `bad_rows` alone, and `fz2_replay`'s `fabric_bad` is `bad_rows`; the F17
  prereg predicted in one unit and its results scored in the other.  Σ over the
  F17 ledger: **119,258 − 119,192 = 66 = Σ`flick`**, on exactly the 25
  discrepant seeds — `fz2e/510043`, F17's one "off by more" at +21, has `flick`
  21.  **F17 §5.3's "18/43 EXACT" would read 43/43 on `bad_rows`.**
  ⚠ **`fz2_immaterial falsify` reported G6/G7 FAIL** against
  `fz2_materiality_census_2026-08-11.md` (an F17-era snapshot, 113/21/92, vs
  the F18 derivation **110 / 24 / 86**); **G1-G5 and G8 PASSED**.
  Re-derivation BOOKED, deliberately not done in the sitting that measured it.
  ✅ **CLOSED 2026-08-11 — `fz2_immaterial falsify` is PASS, G1-G8** (prereg
  `a05af666aa`, `fz2_f18_housekeeping_results_2026-08-11.md`).  Both documents
  now carry the FLASH #18 derivation as **PART I, the live era**, with the
  FLASH #17 tables retained verbatim as **PART II, history and not a claim**.
  **THE LIVE PARTITION IS `FUNCTIONAL 45 · TIMING 30 · TRANSIENT 5 ·
  COSMETIC 19 · UNSCOREABLE 11 = 110`, `IMMATERIAL` **24**, and the quoting
  form is *"86 material-or-unproven of 110 diverging of 3,839"* — never
  `86 / 3,839` alone, and **the residue did not shrink by being re-read**.
  The 24 are the F17 twenty-one with **ZERO leavers** plus **phantom-T1's three
  seats**, each admitted on **all six clauses measured** (S-STARTS `0 / 0`,
  `done_delta` 0, `bad_rows` 1) — a third instrument agreeing the residue is
  one status cell.  **`TIMING_RECONVERGED` is 8, not 7** — `fz2e/530020`
  joined, not a seat and **not attributed**; the 2026-08-11 user ruling
  (*"timing reconvergence seeds are material"*) is a rule about a PREDICATE and
  **carries to the new member without being re-asked**.  ⚠ **G6/G7 NOW PARSE
  ONLY BETWEEN ANCHORS** in each document (`CENSUS-PARTITION-*`,
  `IMMATERIAL-MEMBERS-*`) — unanchored, one regex took the LAST match and two
  took the FIRST, so no placement of a history section satisfied both.  A
  MISSING anchor is a FAIL; demonstrated on P6-P9, including the control that a
  PART II edit does **not** move the gate.
  ⚠ **`verdict`/`sub` LABELS MAY NOT BE DIFFED ACROSS F17 → F18**: the
  `open_bus` accept rule was retired at `80075d049a`, which is **not** an
  ancestor of the F17 flash commit.  No scored quantity depends on `verdict`.
  ⚠ **`fz2_ledger`'s printed diff is NOT the previous era** — its default is the
  committed `fz2_failure_ledger_2026-08-09.json` (198 failures, F13 era), so it
  prints `LEFT 95 / ENTERED 7` where the F17 → F18 movement is **LEFT 3 /
  ENTERED 0**.
  **A FABRIC FIGURE TAKEN ON ANY EARLIER FLASH MAY NOT BE QUOTED AGAINST THIS
  TREE.**
  *Superseded, kept because a fabric figure is only readable against its own
  bitstream.*  ⚠ **NOTE THE GAP: this file never carried FLASH #15, #16 or #17
  lines** — they are in `fz2_f15_results_2026-08-10.md`,
  `fz2_f16_results_2026-08-10.md` and `fz2_flash17_results_2026-08-11.md`.  The
  entry below jumps from #18 to #14; that is a documentation gap, not a missing
  flash.
- **THE BOARD CARRIED FLASH #14 FROM 2026-08-10** (`15029cdfb3`;
  pre-registration `1e2a6e7a96` + erratum `b89f9aa2ea` + addendum `12650eb073`,
  all three committed **before board contact**) — `nec_test_ucore.sof`
  **`060215e43c5de9b3…`**, `.rbf` **`7d4e887639d021ba…`**, built from
  `2fa3dd33b3` **WITH `X1_AD_RETENTION=1`** (draw 2), through
  `sw/safe_flash.sh` with its VERIFY leg (ok on try 1); `flash_log.jsonl`
  **16 → 17 entries**.  **G6 RETENTION, TWO DRAWS, IDENTICAL**: **40.97 MHz**,
  worst setup **+6.843 ns**, **TNS 0.000 setup AND hold on every domain**,
  12,256 ALMs (29 %), 0 errors / 0 latches / 0 `lpm_divide`, the same 88-file
  manifest **`16293f271829d5e5…`**, and the **`.rbf` BYTE-IDENTICAL across both
  draws**; receipts `1d15ef2d82971ade…` and `eb8ef16c420977fb…`, both
  **self-labelling RETENTION**.  ⚠ 40.97 sits **above** every CONTROL draw this
  branch has taken (39.16 · 39.37 · 39.47 · 39.63 · 39.81 · 40.11) — reported,
  **not explained**; `standing_gates.md` §A governs and one green build is not
  closure.
  **IT IS THE FIRST BITSTREAM TO CARRY F58, A1, C1, C2 AND D1** — five landings
  at once, none previously in fabric — **and all five are CONFIRMED**
  (`fz2_f14_results_2026-08-10.md`): first light **MATCH 800 ×3**, RBCHECK
  **8 registers**, C-6 **9 legs / 51 checks / 51 PASS** (P1-P5 at
  2 · 300 · 2 · 300 · 20 to the clock, INTA vector `0xFF`), capture **3,840
  seeds in 11.1 min, 48/48 strata**, **63 div guards / 0 UNPINNED**, 0
  `RigMismatch`, 0 quarantines, `use_core=0` chip proof **MATCH 800** after
  everything, `board_idle()` clean.
  **EVERY REGISTERED SEAT CLOSED — A1 6/6 · F58 23/23 · C1 12/12 · C2 2/2 ·
  D1 3/3 — PLUS TEN UNREGISTERED**, seven of them `C1`-family (so `C1` closed
  **19 of 29** in fabric where its offline instrument could show only 12).
  **CORPUS: SEED `3,639 → 3,692 / 3,837` = 94.8397 % → 96.2210 %** and **ROW
  `11,159,527 → 11,171,232 / 11,322,230` = 98.5630 % → 98.6664 %**, both on the
  registered denominator; as derived on the new denominator, **3,694 / 3,839 =
  96.2230 %**, failures **198 → 145**.  `bars` **11/11 MET**, leaf-diffed, no
  verdict moved.  §38.9's missed-trap overlay **40 → 21**.
  ⚠ **THREE THINGS THIS SITTING MISSED, ALL REPORTED AS REGISTERED.**
  (a) **P-7 — three seeds ENTERED the ledger** (`fz2e/517043`, `fz2e/531009`,
  `fz2e/532032`), all core-side.  `517043` is a **`PSW.TF`** seed and is
  **`C1`'s**: of the corpus's 101 TF seeds, 12 failed on #13 and 7 on #14 — six
  closed, one newly failed — so `C1` is net **+5** on the population it
  exercises and its one loss is inside its own mechanism.  It is the **first
  measured cost of `C1`'s registered debt** (`sm3_tf_floor_cell.py` still cannot
  run on this branch).  The other two are **escaped raw seeds**.
  (b) **THE DENOMINATOR MOVED 3,837 → 3,839**: two of the three A-12 `ps3_8080`
  discards (`fz2c/408029`, `fz2e/523042`) stopped entering 8080 at runtime.
  `_ps3_8080` is a **SOCKET-leg** predicate (A-2), so this is a chip movement.
  (c) **`C-CHIP` FAILED AS REGISTERED**, and the registered form of its row leg
  was wrong: 401 of the 402 raw movers differ **only at row indices ≤ 8**, the
  column policy's own pipeline prefix (`addr`/`data`/`ps` are scored from
  release+9 and nothing in this tree scores rows 0-8).  **On the scored rows the
  chip reproduces 673 / 674.**  The one true mover (`fz2e/527051`) and the two
  scalar movers are **all ESCAPED seeds**, none appears in any seat prediction,
  and attribution stands for the other 3,837.
  **A FABRIC FIGURE TAKEN ON ANY EARLIER FLASH MAY NOT BE QUOTED AGAINST THIS
  TREE.**
  *Superseded, kept because a fabric figure is only readable against its own
  bitstream:*
- **THE BOARD CARRIED FLASH #13 FROM 2026-08-10** (`0ac4c2a83a`; pre-registration
  `edb67a1cb1` + amendment `f18ad478b9`, both committed before the legs they
  govern) — `nec_test_ucore.sof` **`e4a2056a2de53c1f…`**, `.rbf`
  **`c5886e14acb56b26…`**, built from `f18ad478b9` **WITH `X1_AD_RETENTION=1`**,
  through `sw/safe_flash.sh` with its VERIFY leg (ok on try 1);
  `flash_log.jsonl` **16 entries**. **G6 RETENTION receipt `4c39c7928d31576c…`
  (draw 2 of 2; draw 1 `69f8614f379d1ba8…`): 39.83 MHz, worst setup +6.143 ns,
  TNS 0.000 setup AND hold on all four domains, 0 errors, 0 latches, 0
  `lpm_divide`, ALMs 12,182/41,910 (29 %)**, 88-file manifest
  `ec2dd5698f04cb35…` identical on both draws, `.rbf` byte-identical across
  them, `c_ready_q` **0 occurrences**, A&S registers 5,039 → 5,060 (**+21**).
  **G6 CONTROL at HEAD first, receipts `ab9c5de161457bc9…` / `4f7483a65515307d…`:
  39.37 MHz, +5.853 ns, TNS 0.000, ALMs 12,340 (29 %)**, `.rbf`
  `2c4af805dfbe7179…` — **DIFFERENT** from the retention one, which is the check
  that `--verilog_macro` reached the compiler.
  ⚠ **RECORDED, NOT EXPLAINED: the retention build is +0.46 MHz FASTER and −158
  ALMs than the control.** Every historical control→retention pair COST
  0.02–2.13 MHz; this is the first with the sign reversed.
  ⚠ **AND THE BAND FELL ~6 MHz ACROSS THE RE-LANDING CAMPAIGN** — FLASH #11 was
  47.31 / 46.74 at 27 % ALMs; this is 39.37 / 39.83 at 29 %. Green on every draw
  (≥ 32), booked, not explained; **§74.4 governs — the same tree has drawn 19.42
  and 45.91 MHz.**
  **FABRIC CONFIRMATIONS**: 17 registered clauses MET, 3 MISSED, 1 NOT
  EVALUABLE. `INT.F3AA` same-image A/B, 200 frozen seeds, 64 chip-leg runaways
  (identical seed set both bitstreams) → 136 scoreable pairs: **FLASH #12
  109/136 → FLASH #13 136/136, 27 gained / 0 lost, ALL 27 ONE SIGNATURE** (`qop`
  at row 17 or 19, EMPTY one clock early). `8F.0` mod=3 ghost A/B: ghost row
  `core == chip` **0/29 → 22/31**, `core == SS:SP` **29/29 → 2/31** (**G3′ MET**),
  rows identical 31/60 → 52/61 (**G2′ MISSED**, asked ≥ 90/130), **G1′ MISSED**
  (asked ≤ 20/130 on f12, measured 31), **G4′ NOT EVALUABLE** (disjoint pair
  sets). C-6 board legs **9 legs / 51 checks / 51 PASS** (⚠ `b5f2b14f05`'s
  message says 44/44; its own `fz2_control.json` holds 51 — 44 is 51 minus the
  N1 negative control). First light **MATCH 800 ×3**, `div_guard` PINNED on
  100 % of probes, `use_core=0` chip proof **MATCH 800** after everything.
  ⚠ **ONE BAR MIS-REGISTERED AND REPORTED AS SUCH**: the C-6 legs' retained ROW
  BYTES were registered to reproduce and did not — run twice in a row on FLASH
  #13, **0 of 8 identical row `sha256`s with 51/51 PASS both times**. *The raw
  stream of a 4,063-row spin capture is not a reproducible quantity.*
  ⚠ **AN OPEN ITEM NO STANDING GATE SEES — 69 of 130 DIRECTED `8F` mod=3 CASES
  RUN THE ucore AWAY IN FABRIC WHILE THE CHIP COMPLETES** (70 before the
  ghost-read landing, 69 after — it neither causes nor closes it). Post-hoc
  control, labelled as one: `mod != 3`, 130 seeds, **130/130 identical, 0
  errors**, so the residue is **mod=3-specific and core-owned**. Booked with a
  falsifier, not closed: `check_core 8F.0` is 500/500 and `ulockstep 8F.0` is
  50/50 because a golden case has **no predecessor**, and all three unported
  terms (`ghost_uses_ea`/`ea_residue`, `ghost_uses_mul_hi`, `ghost_relax`) are
  predecessor effects.
  *Superseded, kept because a fabric figure is only readable against its own
  bitstream (and note CLAUDE.md never carried the FLASH #11 or #12 lines —
  `standing_gates.md` §B does):* **THE BOARD CARRIED FLASH #10 FROM SM3 SITTING
  27** — `nec_test_ucore.sof`
  **`1a01a6975e4a…`**, `.rbf` **`9e3f0ceaa4f1…`**, built from `f3f7b6b20d` WITH
  `X1_AD_RETENTION=1`, through `sw/safe_flash.sh` with its VERIFY leg,
  `flash_log.jsonl` **13 entries**.  G6 green on the CONTROL build at HEAD first
  (receipt `3cdd586554780bb4…`, **47.85 MHz, +8.602 ns, TNS 0.000, ALMs 11,147
  (27 %)**, 88-file manifest `2d259c06167d1fa3…`); the retention build measured
  **45.72 MHz, +7.181 ns, TNS 0.000, ALMs 11,165 (27 %)**.  **IT IS THE FIRST
  BITSTREAM TO CARRY F55, F56, F57, THE BRK/TF LEG AND THE ILLEGAL-FORM STALL**
  — five landings at once — and every registered prediction was met cell for
  cell (`ucore_provenance.md` §88.A): first light **MATCH 800 ×3**,
  `x1_fabric baseline --leg fab_f10` **279/283** = the `tb_sys ret` column with
  **0 PASS/FAIL disagreements and 0 differing coordinates over all 283** and its
  four failures NAMED IN ADVANCE, the S16 walk in fabric **1,347/1,371 rows-only**
  with **0 / 0** against `vsys_ret` and its 24 failures named in advance, the b3
  priority tranche **178/178 on both legs**, socket controls **49/49** and
  **41/41**, `use_core=0` chip proof **MATCH 800** after everything, `div_guard`
  PINNED on every probe, **0 transport errors in 2,394 captures**, `board_idle()`
  clean.  ⚠ **THREE of the five are CONFIRMED in fabric (F55, F56, F57); the
  BRK/TF trap and the illegal-form stall are IN the bitstream but were NOT
  REACHABLE by the two scored populations** — all 1,654 of their goldens are the
  one-byte program `[0xF4]` with `PSW.TF` clear — which was derived BEFORE the
  run, not after (§88.A.4).  **A FABRIC FIGURE TAKEN ON ANY EARLIER FLASH MAY NOT
  BE QUOTED AGAINST THIS TREE.**
  *Superseded, kept because a fabric figure is only readable against its own
  bitstream:* **FLASH #9, SM3 SITTING 19** (`nec_test_ucore.sof
  **01aca4c0b1e7…**, `.rbf 58154c546dba…`, built from `134249a2ad` WITH
  `X1_AD_RETENTION=1`; G6 green on the CONTROL build at HEAD first — receipt
  `2bf170fa9eee15f7…`, 45.49 MHz, +9.146 ns, TNS 0.000, 88-file manifest
  `567b11fffd6414a6…` identical to sitting 17's; the retention build 44.99 MHz,
  +9.023 ns, TNS 0.000, 27 % ALMs).  **IT IS THE FIRST BITSTREAM TO CARRY F53
  AND F54**, and the fabric legs are `ucore_provenance.md` §80.B: first light
  **MATCH 800 ×3**, `x1_fabric baseline --leg fab_f9` **268/283** (it was 265 on
  FLASH #6, which predates both) with the 15 failing cells NAMED IN ADVANCE and
  **0 PASS/FAIL disagreements / 0 differing coordinates** against the fresh
  `tb_sys ret` column, socket control **49/49**, the S16 walk's FIRST fabric leg
  **1,291/1,371 rows-only** with **0 disagreements over all 1,371** against
  `vsys_ret`, b3 **`chip_f9` 178/178 / `core_f9` 176/178**, `use_core=0` chip
  proof **MATCH 800** after everything, `div_guard` PINNED throughout, 0
  transport errors, `board_idle()` clean, `flash_log.jsonl` **12 entries**.
  ⚠ **THE NEXT CLAUSE IS THE FLASH #9 SNAPSHOT AND IS STALE TWICE OVER — F55
  LANDED at SM3 sitting 20 (`39ac08ccd4`, ten registered bars met, in fabric
  since FLASH #10), and the F58 landing (`b245334d7c`, fuzz-v2 survey family
  B1) closed the ADJACENT mechanism: the HALT pseudo-cycle announces nothing
  of its own — it publishes the AD output latch as it stands (write data
  after a write, T1 address after a read), measured 1,189/1,189 HALT cycles
  with zero exceptions.  A survey brief was misled by reading this paragraph
  as current; it is kept as history, not as state.**
  **AND IT PRODUCED F55, BOOKED NOT LANDED**: `halt_hold` keeps `ad_oe_addr`
  asserted for the whole HALT pseudo-cycle, so the ucore DRIVES an address
  silicon leaves there by RETENTION — invisible on `tb_v30_core` (whose
  `cycle_live` floats those clocks) and worth 5 sweep + 30 S16 cells on
  `tb_sys` and in fabric.  **F53's UBE half is in the RTL; its ADDRESS half
  never was.**  Falsifier in `standing_gates.md`; it is the obvious next RTL
  landing.  **General rule established: where `tb_v30_core` and `tb_sys`
  disagree, fabric sides with `tb_sys` — 1,654 of 1,654 cells.**
  *Superseded, kept because a fabric figure is only readable against its own
  bitstream:* the board carried `nec_test_ucore.sof
  **626fb30ebee2…**, `.rbf 460a71907f87…`, **FLASH #6**, SM3 sitting 12
  2026-08-05 — built from `536e207c76` **WITH `X1_AD_RETENTION=1`**; 27 % ALMs
  (11,122/41,910), Fmax **45.87 MHz**, worst setup **+8.802 ns**, TNS 0.000 on
  every setup AND hold domain, 0 errors, 0 latches, 0 `lpm_divide`), with first
  light **800/800 on all three `check_ab_hw` legs**.  **IT IS THE RETENTION
  BITSTREAM**: §56.3a's pad-float model is compiled in, on the OBSERVATION path
  (`hb_ad_sample`) only, so the `use_core=0` socket position is unaffected by
  construction and measured unaffected (`check_ab_hw chip 800` MATCH after the
  whole sitting).  FLASH #5 was `315de4bc9e30…`, FLASH #4 `67ddd59413d5…`,
  FLASH #3 `924c4a61e0…`; the FSM A/B bitstream is `nec_test.sof a4533dfef0…`.
  **A FABRIC FIGURE TAKEN ON ANY EARLIER FLASH MAY NOT BE QUOTED AGAINST THIS
  TREE.**  On FLASH #6 `x1_fabric` scores **265/283** (it was 146 on #5, 143 on
  #3/#4) and the F43 `busstat` signature at `d = 2w+5` stays EXTINCT.  Left
  verified: `check_ab_hw chip 800` **MATCH over 800 rows**, `div_guard`
  **PINNED** on both sides of the fabric legs, `use_core` **False**,
  `cfg = 0xff0008`, `board_idle()` clean, **0 transport errors**,
  `flash_log.jsonl` **9 entries**.
- **`timed_fuzz` now prints `BOUND WARNINGS`** — seeds whose EU completed-read
  store SATURATED, i.e. ran outside the regime `sw/qdepth_probe.py` proves
  (`rdq_` ≤ 2, `rd_done_q_` ≤ 1 on v0.1 at w0 **and**, U4, on w1/w3 and all four
  evt suites). It reports **4** on the ucore leg (`standing_gates.md` §B; it was
  **5** until SM3 sitting 25's BRK/TF leg took one out, and **6** in this file
  until SM3 sitting 12 corrected it against the artifact), they are
  scored normally and not excused, and `ENGINE ABORTS` is **0**. A bound fire on a GOLDEN case is a hard failure in
  `check_core.py` — that is where the bound is a theorem.
- **Measurement tools, NOT gates** (never quote them as a pass):
  `sw/s11_census.py`, `sw/s12_census.py` (`hltsweep`/`psw`/`regold`/`ackfam`),
  `sw/s14_census.py --band`, `sw/s14_dstar.py`, `sw/s15_census.py`
  (the fuzz-residue taxonomy and `--rmw`, the RMW population).
  **`s15_census.py` HAS AN ENGINE SINCE 2026-08-04** (gap R4, closed):
  `--core {sim,ucore,fsm}`, default `sim` so every historical invocation means
  what it meant. It used to call `tf.run_sim` unconditionally, so pointed at a
  `--core ucore` report it ran clean and reported the MODEL's families for the
  ucore's seeds. **MATCH `--core` TO THE REPORT's core.** The ucore's own
  bank-wide family census, **CURRENT** (SM3 sitting 27, `ucore_provenance.md`
  §88.B.2 / `sm3_s27_residue_census_2026-08-05.md` §2.1): `PF_LOST` **102** ·
  `SCHEDULE` **44** · `DATA_SEQ` **41** · `PF_GAINED` **15** · `PF_ADDR` **11** ·
  `PIN` **9** = **222**; **`TAIL_EXTRA` is 0** and the taxonomy catch-all is
  EMPTY.  The model's, same run: `PF_LOST` 282 · `SCHEDULE` 196 · `DATA_SEQ` 30 ·
  `PF_ADDR` 27 · `PIN` 26 · `PF_GAINED` 13 = **574**, `TAIL_EXTRA` 0.
  *The superseded text — the ucore's FIRST such census, `ucore_provenance.md`
  §58.4:* `PF_LOST` 107 · `DATA_SEQ` **41** · `TAIL_EXTRA` 28 · `PF_GAINED` 25 ·
  `PF_ADDR` 9 · `SCHEDULE` 5 · `PIN` 4 = 219, catch-all empty. `DATA_SEQ` is 13
  seeds LARGER than the model-replayed table showed, which retires §T.3's
  reading that the ucore "closed nothing" in that family.
- **A RIG-INTEGRITY FINDING, SM2**: `sw/s10_board.py` / `sw/s13_board.py` COULD
  NOT TAKE A CAPTURE at HEAD, and had not been able to since 2026-08-02. Their
  `capture()` passes `want_raw=True` to `v30run.run_image`, which had no such
  parameter on ANY branch (`git log --all -S want_raw -- sw/v30run.py` is
  empty), so the first capture raised `TypeError`. **No standing gate runs an
  s10/s13 probe**, so nothing saw it until something needed the board. REPAIRED
  (`ucore_provenance.md` §59.7.11): the parameter returns the undecoded 64-bit
  words that were already being unpacked and discarded. The live falsifier is
  `sw/r6_perrep.py capture`, an s10/s13-path probe. **Verify a flag exists AND
  that the callee accepts it — this is the accepted-and-ignored trap's mirror
  image, and it hid in a place with no gate.**
- **Board discipline**: `s13_board.div_guard()` PINS the divider and asks the
  transport for the readback — an UNPINNED readback is a rig-integrity
  FINDING. Every board probe calls it. Socket only (`use_core=False`,
  explicit — the board's CFG is sticky).
- NOTE: `sw/check_enter_nesting.py` is the VERILATOR/RTL leg only, and since
  2026-08-04 it is an **ARCHIVED, on-demand** gate: it binds to the FSM core
  through `check_seq.BIN` and takes NO arguments (unknown flags are silently
  ignored), so do not use it to gate `sim/` work or ucore work. **General rule:
  verify a flag exists (`--help`) before trusting a run that used it** — and
  that it is not merely accepted-and-ignored.
