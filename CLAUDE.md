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
- Consult Codex (`codex:rescue`, resumed thread) as critical reviewer at
  campaign phase boundaries and before closing any verdict document.
- Board work: single-writer check first, socket only (`use_core=False`),
  no flashing unless explicitly authorized, pre-register predictions and
  commit before first board contact, retain full per-clock rows + sha256
  (never digests alone), run board_idle and verify after every session.
- /tmp discipline: no large temp files in /tmp (tmpfs quota); use
  `~/.cache/ucsimt-tmp` for big intermediates.
- Provenance ledgers: every modeled behavior tagged ROM / PLA / LAW /
  MEASURED / ASSUMPTION with evidence and falsifiers
  (docs/notes/ucsim_provenance.md, docs/notes/ucsim_t_provenance.md).

## Gate quick reference

(current as of ucsim-t §26, the pre-RTL cleanup. Values are the standing
ratchets: monotone, never re-scored downward without a loud, itemized entry.)

- **ROM/PLA**: `make -C sim test` (disasm byte-exact),
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
  and the four HLT delay sweeps `s10-hltsweep-w{0,1}` **91/97**, **95/95**
  and `s13-hltsweep-w{2,3}` **44/46**, **42/45**.  (These were STALE here at
  92/95, 42/46, 40/45 — the pre-§26.7.6 figures — from the S15 cleanup until
  ucore U3 re-measured the model leg and found the quick reference disagreeing
  with `ucsim_t_provenance.md` §26.11's own delta row.  Corrected UPWARD.)
- **Timed, whole-program**: `sw/check_boot.py --timed 220`,
  `sw/timed_scenario.py` (18/0/9), `sw/timed_enter_replay.py` (154/154 x5),
  `sw/timed_ins_replay.py --raw` (rails 1312/1312, vs-chip 2624/2624),
  `sw/timed_wvec_gate.py` (88/88, +0.0 %), `sw/timed_lawcards.py`
  (**8 GREEN / 0 RED / 3 UNRESOLVED** — C6, C7, C11),
  `sw/timed_fuzz.py --evt-replay` (REGISTERED **1,272/1,702**, EVT
  **709/1,008**, COMBINED **1,981/2,710**),
  `sw/timed_fuzz.py --seeddir sw/testdata/t4/b2-tranche/seeds`
  (**154/188** — V5 is a standing REGISTERED FAILURE, not to be re-opened).
- **The `ucore` RTL twin** (`--core ucore`, stage U3 close; these are the
  ucore's OWN ratchets, not the model's — see `ucore_provenance.md` §44):
  `check_core.py --core ucore --opcodes all --cases 0` **169,000/169,000**;
  `v0.1-w1`/`-w3` 1,200; `EB` 200; the four `evt` cells 200/1,200/200/1,200;
  `v0.1-w1evt-biased` 1,200; `check_boot.py --core ucore` 220 and 400;
  `ulockstep.py --golden all --cases 50` **17,350/17,350**;
  `timed_wvec_gate.py --core ucore` **88/88, +0.0 %** (the FSM core is 71/88);
  `timed_enter_replay.py --core ucore` **154/154 x5**;
  `timed_ins_replay.py --core ucore --raw` **1,312/1,312** and **2,624/2,624**;
  `timed_fuzz.py --core ucore --evt-replay` REGISTERED **1,483/1,702** (the sim
  is 1,272) and `--seeddir …/b2-tranche/seeds` **171/188** (the sim is 154)
  — both RAISED by U4/F47 from 1,394 and 168, which were the U3 close's figures;
  the four HLT sweeps **91/97, 90/95, 40/46, 38/45** = 259/283 (below the model
  by **13** cells, all at w1/w2/w3 — at w0 the two failing sets are IDENTICAL).
  These were 90/97, 88/95, 37/46, 34/45 = 249/283 through **U5**, and the move is
  two changes at once: **F51** landed (the HALT pseudo-cycle has no data phase)
  and the TB's composed-AD mask stopped hiding it.  §43.2's "17 cells no
  comparator on this TB can score" is RETIRED — F42 was refuted in fabric
  (§52.9), the cells are scoreable, and 10 of them now pass.
  **`--rig-hold reg8`** exists because the rig's `evt_hold` register is 8 bits;
  it moves the SIM's EVT number too (+71), so it is OFF by default and the EVT
  ratchet is NOT re-registered against it (F46).
- **`sw/ss_lint.py --core ucore` exits 0** (U4/F49). It was KNOWN-RED through
  U3 because five architectural flops were absent from the ucore's save-state
  map; they are mapped now, `SS_VERSION` **0x82** / `SS_COUNT` **218** /
  `SS_TAG` **0x82DA**, census **201 flops, 0 UNMAPPED** (it was 223 until U4
  pass 3: the enable-form refactor made 22 of the 24 whitelisted per-edge
  temporaries combinational BY DECLARATION, which is exactly the fix U3 booked
  and could not take while the RTL was frozen — the MAP did not move). The
  `--core fsm` leg is unchanged and still exits 0.
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
  `ad_oe_ps` and it is deliberately NOT taken — see the disposition decision
  routed to the user in `ucore_campaign_verdict_2026-08-04.md` §(e).
- **U4 additions**: `sw/check_ab_sim.py --core {fsm,ucore}` — the core inside
  the REAL integration (system_large) vs the chip's own boot capture; both legs
  **MATCH over 187 rows**. (It had been unbuildable since 2026-07-13; three
  files had drifted out of its RTL list.) `sw/gen_ucore_qsf.py --check` gates
  that `hdl/nec_test_ucore.qsf` is a faithful derivative of `nec_test.qsf`, i.e.
  that the two A/B bitstreams differ by the CORE and nothing else.
- **SYNTHESIS: G6 IS GREEN AND THE ucore HAS RUN IN SILICON (U4 pass 3, §52).**
  The ENABLE-FORM refactor put `ce` on the register enable ports, and a second
  structural pass took `srst` out of the next-state cone as well (it launched
  outside the core, so no multicycle could cover it — §52.2/52.3). Result:
  **26 % ALMs (11,078/41,910), Fmax 45.56 MHz against a registered ≥ 32 MHz,
  worst setup +8.922 ns and TNS 0.000 on EVERY clock domain**, 0 errors, 0
  latches, 0 `lpm_divide`. `nec_test.sdc` carries the 4/3 CE multicycle with its
  falsifier written beside it. Bitstream `nec_test_ucore.sof cdf5edee00…`,
  `.rbf 91697c83b3…`. **The whole sim ladder was re-scored THREE times across
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
- **TWO FINDINGS OUT OF THE FABRIC LEGS.** (a) **F42 is REFUTED** — its
  registered prediction was that the 17 uncountable HLT cells would PASS in
  fabric; they fail, the sweeps score 29/283 there, and the socket control on
  the identical driver reproduces the golden 49/49. The ucore drives the HALT
  display's upper nibble differently from silicon (`0x0AD8A` where the golden
  has `0x2AD8A`) and drops it a row early. (b) **the FROZEN FSM CORE HAS
  REGRESSED 104 SEEDS** on the random-wait axis between the 2026-07-30 build
  (163/178) and HEAD (59/178, in fabric and in Verilator alike). Not the
  ucore's, and no standing gate sees it.
- **`timed_fuzz` now prints `BOUND WARNINGS`** — seeds whose EU completed-read
  store SATURATED, i.e. ran outside the regime `sw/qdepth_probe.py` proves
  (`rdq_` ≤ 2, `rd_done_q_` ≤ 1 on v0.1 at w0 **and**, U4, on w1/w3 and all four
  evt suites). It reports **6**, they are scored normally and not excused, and
  `ENGINE ABORTS` is **0**. A bound fire on a GOLDEN case is a hard failure in
  `check_core.py` — that is where the bound is a theorem.
- **Measurement tools, NOT gates** (never quote them as a pass):
  `sw/s11_census.py`, `sw/s12_census.py` (`hltsweep`/`psw`/`regold`/`ackfam`),
  `sw/s14_census.py --band`, `sw/s14_dstar.py`, `sw/s15_census.py`
  (the fuzz-residue taxonomy and `--rmw`, the RMW population).
- **Board discipline**: `s13_board.div_guard()` PINS the divider and asks the
  transport for the readback — an UNPINNED readback is a rig-integrity
  FINDING. Every board probe calls it. Socket only (`use_core=False`,
  explicit — the board's CFG is sticky).
- NOTE: `sw/check_enter_nesting.py` is the VERILATOR/RTL leg only — it takes
  NO arguments (unknown flags are silently ignored), so do not use it to gate
  sim/ work. **General rule: verify a flag exists (`--help`) before trusting a
  run that used it.**
