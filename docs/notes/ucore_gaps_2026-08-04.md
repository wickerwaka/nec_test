# `ucore` — WHAT IS NOT YET FULLY FUNCTIONAL OR TIMING-ACCURATE

**2026-08-04, branch `ucsim`, HEAD `6a4b13da64` + this session's mechanical
changes.** Companion to `docs/notes/ucore_campaign_verdict_2026-08-04.md` (the
verdict), `docs/notes/ucore_provenance.md` §0-§57 (the ledger) and
`docs/notes/fsm_core_archive_2026-08-04.md` (the other core's disposition).

> **STATUS BANNER, added 2026-08-04 by session SM1 — READ BEFORE ACTING ON ANY
> ITEM BELOW.** This document is a DATED SNAPSHOT and is deliberately not
> rewritten. Six of its items have moved; `ucore_provenance.md` **§58** is the
> current state.
>
> | item | now |
> |---|---|
> | **R1 / T5** — `evt_hold` is 8 bits | **FIXED in RTL** (12 bits, §58.3). Not yet in any bitstream. |
> | **T5** — "the EVT column is rig-poisoned and is not a gate" | **ACTED ON**: `INV-1`, `docs/notes/invalidation_ledger.md`. The 1,008-seed column is a SUSPENDED gate; the 248-seed un-poisoned sub-gate is registered at ucore **170/248**, sim **144/248**. |
> | **R3** — the F45 guidance comment | **FIXED** (§58.5) |
> | **R4** — `s15_census` cannot classify an RTL core's residue | **CLOSED**: it has `--core`, and §T.3's table is superseded by the ucore's OWN census (§58.4) |
> | **R5** — the CE-hold probe has no EU coverage | **FIXED** (§58.5), gate re-run green |
> | **X1** — the `core_ad` retention intervention, pre-registered and unrun | **RUN OFFLINE, BOTH BARS MET** (§58.6). Fabric leg outstanding; attribution still NOT ESTABLISHED. |
> | **T3 / T4 / T8 / I3 / I5** — "model-shared" | **RECLASSIFIED AS WORK** by the 2026-08-04 correctness-target directive (§58.1). The owner column below is the OLD partition. |
>
> **SECOND UPDATE, session SM2 (2026-08-04) — `ucore_provenance.md` §59 is the
> current state.** Five more items moved, and one of them moved the other way.
>
> | item | now |
> |---|---|
> | **R1 / T5** — `evt_hold`, and the poisoned EVT column | **CLOSED.** FLASH #4 (`67ddd59413d5…`) carries the 12-bit register; the board's host tool was replaced too; the register AND the pin were proved; **all 760 re-captured**, 0 errors, 0 GEN-DRIFT.  The 1,008-seed column is **UN-SUSPENDED** at ucore **468/1,008**, sim **363/1,008** — *the ucore now LEADS by 105 where as banked it trailed by 517.*  **SM3 sitting 3, after H1 in both engines: ucore 906/1,008, sim 780/1,008.**  `invalidation_ledger.md` §CLOSURE. |
> | **R6** — the s10/s13 per-repetition rows | **CLOSED, and the answer is YES.**  10 reps × 5 cells, full rows banked: every difference is on rows 0-8 (before the first T1) in the multiplexed pads, none on a dedicated pin.  §59.7.8 |
> | **X3** — the tranche not re-captured on the shipped bitstream | **CLOSED.**  Re-captured on FLASH #4: **176/178**, same `bs = 2` residue, socket leg 178/178.  §59.7.9 |
> | **X1** — the fabric leg of the retention intervention | **ATTEMPTED AND BLOCKED, NOT REFUTED.**  The BASELINE reproduces on FLASH #4 (**143/283**, 116 fabric-only, 116/116 INTA, socket control 49/49) but the INTERVENTION cannot be synthesised: Quartus folds `core_ad === 1'bz` to a constant and deletes the hold register.  Pre-registered as a liveness test (§59.3) and reported as registered (§59.7.1).  **C11's NOT ESTABLISHED stands.** |
> | **NEW — a rig-integrity finding** | **`s10_board` / `s13_board` could not take a capture at HEAD** and had not been able to since 2026-08-02: `want_raw=True` was passed to a `run_image` that never had the parameter, on any branch.  No standing gate runs an s10/s13 probe, so nothing saw it.  REPAIRED, §59.7.11 |

> **THIRD UPDATE, session SM3 (2026-08-04) — the measured census is
> `docs/notes/sm3_residue_census_2026-08-04.md` and `ucore_provenance.md` §60 is
> the current state.**  Four more items moved.
>
> | item | now |
> |---|---|
> | **I1** — the sim's `9D` flag-commit erratum | **CLOSED — FIXED in `sim/`** (§60.4).  Rendered as F39's mechanism and naming no opcode: the BIU publishes the read data-latch edge and a STANDING `OPR -> FLAGS ... F` row's destination takes it there.  Hits exactly `007A` and `01EA`.  `INT.9D` case 1 row 9 is now `05FAD2` against the golden's `05FAD2`; the full sim ladder re-run with **zero** other movement. |
> | **T8** — "three are an exact byte swap … M5b's A0 swapper applied where the chip does not" | **THE ATTRIBUTION IS REFUTED** (§60.3).  `raw_3868` has the OPPOSITE SIGN — the chip rotates at an EVEN address where the model does not — so the three do not share a sign and no change to the A0 rotator closes them.  What the rows establish is that the engines' **OPR** holds the chip's two bytes in the other order: the defect is on the LOAD side, not the drive side.  **Nothing was patched.**  The observation stands; the mechanism is NOT named. |
> | **T5 / the EVT partition** — "547 ucore-only non-exact seeds" | **SUPERSEDED BY MEASUREMENT.**  On SM2's rebuilt column the partition is **ucore-only 5 / shared 535 / sim-only 110**, net +105.  The five are named in the census §2.2; all five are at waits ≥ 1. |
> | **I3** — INTA under waits, the second acknowledge's ANCHOR | **its whole-program evidence column is REBUILT and it speaks.**  Census **H1**: the chip idles **2 clocks** between the last prefetch and a RE-ENTRY acknowledge's announcement and grants the slot to nothing — 445/445 of the ucore's INTA cell, 6-clock CODE-T1-to-INTA-T1 gap on all of them.  The ucore prefetches into it; the model announces 2 clocks early.  **The largest single mechanism in the residue.  CLOSED 2026-08-04**: pre-registered, discriminated on the socket (the directed cell REFUTED both the redirect and the IRET readings — it is the RE-ENTRY, armed by the PREVIOUS acknowledge), landed in `sim/` at SM3 sitting 2 and in `hdl/rtl/ucore/` at SM3 sitting 3 as ONE register.  ucore EVT **468 → 906 / 1,008**, sim **363 → 780**; `sm3_ackcmp`'s re-entry `L = 4` row 1,117 wrong → **0**, the wake row unmoved.  `ucore_provenance.md` §61-§62. |

> **FOURTH UPDATE, session SM3 sitting 6 (2026-08-04) — `ucore_provenance.md`
> §66-§67 is the current state.**  Two more items moved, and one of them was
> **the instrument, not the part**.
>
> | item | now |
> |---|---|
> | **T2** — "the ucore's OWN registered-bank residue is NINE seeds" | **SEVEN OF THE NINE WERE A TESTBENCH DEFECT.**  `hdl/tb/tb_v30_core.sv` committed `IOW` cycles into `mem[]`, so an I/O write to port P corrupted memory at address P — on the RTL legs only (the socket harness and `sim/` do not, which is why the chip reads the seed's own image where the RTL legs read the I/O datum).  Chip-side census: 37 scored seeds contain an `IOW` whose port is later READ as memory.  Fixed (`lat_memw`), and `mc1/412`, `mc1/1937`, `mc1/3325`, `mc2/2216`, `mc2/3291`, `t30-raw/84`, `t30-raw/123` are all cycle-exact.  **The ucore's registered-bank ucore-only residue is TWO seeds**: `mc1/721` (§49.8's `10`/ADC carry-in, off by ONE) and `mc2/584` (`qs F!=-`).  §T.2's *"eight of nine are `data`"* now reads: seven of the eight were the instrument.  `timed_fuzz --core ucore` REGISTERED **1,483 → 1,490**, EVT **906 → 908**, b2 **171 → 172**. |
> | **T1** — "the four HLT delay sweeps: 259/283 … 13 ucore-only cells" | **F43 LANDED; the six `busstat` cells are CLOSED and the sweeps are 265/283** (91/97, 92/95, 42/46, 40/45).  F43's twice-declined disposition was re-examined and retired **on its own terms**: both declines were scheduling arguments ("a closure is being scored against this binary"), not objections to the mechanism, and F51 has since moved this very block under the current comparator.  The landing is one tap — the display's decision reads the wake one stage further down the SAME pin pipeline (`int_p[1]` against `eu_unhalt`'s `int_p[2]`), published as `eu_unhalt_disp`; no flop added, `SS_VERSION` unchanged.  **The 13 ucore-only cells are now 7, and all 7 are the `seg`/`bus` half, still NOT DIAGNOSED**: `HLT.INT` only, w1 `d=8,9,10` · w2 `d=12,13` · w3 `d=15,16`, signature `seg exp 'CS' got 'SS'` with the composed bus differing by exactly `0x10000` (the S4:S3 indicator).  `HLT.RES` is now PERFECT at w1/w2/w3. |
> | **NEW — a second rig-integrity finding** | **`sw/x1_retention.py capture` binds to `hdl/tb/obj_dir_sys{,_ret}/tb_sys` and rebuilds NOTHING**, and there is no build recipe for `tb_sys` anywhere in the tree.  Run on the day-old binaries after F43 it reported a false *"6 survivors, BAR (i) NOT MET"*.  Rebuilt by hand: base **146/283**, ret **265/283**, **119 base-only, 119/119 INTA, 119 closed, 0 survivors, 0 differing — BOTH BARS MET.**  The vacuous-gate pattern's sixth incarnation.  Note that `base` no longer equals the fabric's 143: FLASH #3 does not carry F43, so **no fabric figure may be quoted against this tree's `tb_sys` until a re-flash**. |

**This document is measurement and enumeration only.** No mechanism was
proposed, no RTL was changed, nothing was fixed. Where a number could be stale
it was **re-run**, and where a re-run disagreed with the ledger that is stated
in place. §Z lists every measurement taken this session, including the four that
are new and the three ledger statements they correct.

**Owner column, defined once** — this is the governance partition
(`ucore_provenance.md` §0 rule 3), not an opinion:

| owner | means |
|---|---|
| **ucore** | the RTL diverges from silicon and the reference model does NOT share the divergence. A bug, and the ucore's to fix. |
| **model-shared** | the RTL diverges from silicon and the model diverges identically. A LEDGER finding routed to `sim/`; patching the RTL here would knowingly create an RTL-vs-model divergence in the direction governance forbids. |
| **harness — NOT ESTABLISHED** | the evidence reads as an integration property of the A/B harness, and that reading is explicitly **not** established as a finding. Presented exactly as registered. |
| **rig** | the capture/replay apparatus, not either engine. |
| **coverage** | nothing is known to be wrong; nothing has ever looked. |

---

## §0 EXECUTIVE SUMMARY

| # | area | item | size | owner | closer |
|---|---|---|---|---|---|
| **F1** | functional | **8080 / BRKEM execution is STRUCTURALLY UNREACHABLE in the ucore** — the loader never selects `pla3_mode8080` and `ld_page_n` never emits pages 5/6 — while `sim/` DOES implement it | 192 ROM rows + the BRKEM/RETEM/CALLN entries; 116 of 1,028 ROM rows never executed | **ucore** (undeclared RTL-vs-model gap) | render the 8080 page select + entry/exit path, **or** register an explicit scope exclusion so a gate can assert it. Today neither exists. |
| **F2** | functional | **Three of the four golden suites have never been run against the ucore** — `v0.2` (347,000), `v0.3` (3,699,998), `v20suite` (3,125,000). A U0-era deferral never revisited. **And `v0.2` cannot be run at all**: `check_core.py:709` reads a `metadata.json` `opcodes` map that `v0.2`'s emitter schema does not have (`KeyError`, either core) | 7,172,126 cases un-run of 7,341,126 | **coverage** + **rig** | run `v0.3` / `v20suite`; for `v0.2`, fall back to `flags_mask = 0xFFFF` when the manifest carries no `opcodes` map, or re-emit a compatible manifest |
| **F3** | functional | **INM/OUTM (6C-6F) block I/O was rendered but ungated.** Measured this session: **229,999 / 229,999 cycles AND arch** over all 23 `v0.3` block-I/O forms | **CLOSED** | — | — (registered in `standing_gates.md` §B and `CLAUDE.md`) |
| **F4** | functional | far-CALL / far-JMP `CS` recognition shadow and the taken-branch recognition boundary (`post_flush`) — documented, **not rendered**; no golden reaches either | 2 mechanisms | **ucore** (deliberate) | a golden that reaches them. None exists in any emitted suite. |
| **F5** | functional | `opr_free_p` / `set_oprfree` are **PROVABLY VACUOUS** (F31) | 2 signals | ucore (benign) | none needed — recorded so it is not re-derived |
| **F6** | functional | the **A30 ambiguous micro-address** `111.00000010.00` is emitted at the sim's fixed-priority bank-B winner, alternative recorded with a falsifier | 1 micro-address | model-shared | a golden reaching page 7 opcode 02. None exists. |
| **F7** | functional | opcodes/forms **absent from every suite the ucore has run**: the `0F` space beyond the 20 whitelisted forms, `82`, `8F.1-.7`, `C6.1-.7`, `C7.1-.7`, `D6`, `F1`, register-set expansions | not counted | **coverage** | rides F2 |
| **T1** | timing, offline | **the four HLT delay sweeps: 259/283, against the model's 272/283** — 24 failing cells, **13 of them the ucore's alone**, all at w1/w2/w3 | 13 cells | **ucore** | the `busstat`-first half is **F43**, diagnosed and twice declined; the `seg`/`bus`-first half is **NOT diagnosed** |
| **T2** | timing, offline | **the ucore's own registered-fuzz-bank residue is NINE seeds** — the complete set on which the model is cycle-exact and the ucore is not. Measured this session, engine against engine | 9 of 1,702 | **ucore** | §49.8's three sub-mechanisms; the `10`/ADC deciding measurement is written down and un-run |
| **T3** | timing, offline | the other **210** of the ucore's 219 registered non-exact seeds are seeds **the model misses too** | 210 of 1,702 | **model-shared** | the inherited seven-family closers, `ucsim_t_provenance.md` §26.10 C |
| **T4** | timing, offline | **the 2 `bs` seeds of the priority tranche** — ucore ≡ SIM on 4,000/4,000 rows on both | 2 of 178 | **model-shared** | a `sim/` landing first; never a ucore patch |
| **T5** | timing, offline | **CLOSED (SM2) — re-captured; the column is a gate again.  RE-SCORED at SM3 sitting 3 (H1): ucore 906/1,008, sim 780/1,008.**  ~~the EVT column is RIG-POISONED and is not a gate~~ — 547 of the 1,008 EVT seeds are ucore-only non-exact, and F46 explains them: 760 seeds banked `hold = 300` into an **8-bit** register | 547 of 1,008 | **rig** (F46) | widen `evt_hold` to 12 bits + re-bank + re-capture — a decision routed to the owner |
| **T6** | timing, offline | **the b2 victory tranche: 171/188.** V5 is a standing REGISTERED FAILURE | 17 of 188 | mixed | **not re-opened, not re-scored** |
| **T7** | timing, offline | **5 `BOUND WARNINGS`** — seeds whose EU completed-read store saturated, i.e. ran outside the regime `qdepth_probe.py` proves | 5 seeds | ucore (scoped) | none taken — deepening the capacity would be the large-fitted-table failure the standing principle names |
| **T8** | timing, offline | the **4 shared seeds** of §49.7 — three are an exact byte swap on an odd-address word write (M5b's A0 swapper applied where the chip does not) | 4 seeds | **model-shared** | `sim/` |
| **T9** | timing, offline | the **14 seeds** of the 500-seed in-silicon population (435/449) | 14 of 449 | mixed (`bs` 11, `qs` 3) | as reported §52.7 |
| **X1** | timing, fabric | **STILL OPEN; the fabric intervention is BLOCKED (SM2, §59.7.1) — baseline reproduces at 143/283 on FLASH #4.**  the 116 fabric-only INTA-retention cells. 116/116, one class, no counter-population — and **the attribution is NOT ESTABLISHED** | 116 of 283 | **harness — NOT ESTABLISHED** | the `core_ad` retention intervention, **pre-registered and unrun**, §56.3a. *Any* of the 116 still failing reclassifies those cells as the CORE's. |
| **X2** | timing, fabric | **the fabric scorer is strictly stricter than the TB**: 143/283 in fabric vs 259/283 offline on the same RTL. §55.2 bar 2 was registered at ≥ 249 and is reported **MISSED** | 116 cells | see X1 | see X1 |
| **X3** | timing, fabric | **CLOSED (SM2) — re-captured on FLASH #4: 176/178, residue `bs`=2.**  ~~the priority tranche was NOT re-captured on the U5 bitstream~~ (registered as a deliberate deviation); its 176/178 is the pass-3 bitstream's, with the RTL change proved inert offline | 483 captures not spent | rig (declared) | a re-capture, if the A/B is re-run |
| **I1** | inherited | **the sim's `9D` flag-commit erratum** — the RTL matches silicon and the MODEL does not. **The one place this campaign owes the model a fix.** | 2 ROM rows | **model** | one line in `wr_dst1`'s FLAGS arm + the `F` wait's ordering; belongs to whoever next opens `biu_timed` |
| **I2** | inherited | **the SIM does NOT carry F51's HALT defect** — verified two ways this session | **CLOSED** | — | — |
| **I3** | inherited | **INTA under waits** is closed as a law for the single-instruction population (M18) and the ucore is 200/1,200/200/1,200 on all four `evt` cells — but the **second acknowledge's ANCHOR** is still open and the whole-program EVT column is T5-poisoned | 1 open rule | model-shared | §26.6.4's directed cell: an acknowledge announced while another cycle still owns the bus, at more than one wait level |
| **I4** | inherited | **law cards C6 / C7 / C11 remain UNRESOLVED** (re-run this session: 8 GREEN / 0 RED / 3 UNRESOLVED). They bear on the ucore's spec completeness: C11's `owns_slot` is an EU micro-state the ucore renders from an enumerated source set that no silicon capture isolates | 3 cards | model-shared | C6/C7 need a pin-observable signature for `ext_ok_wr` / `tw_par`; C11 needs an instrument, not board time |
| **I5** | inherited | the four remaining items of the ucsim-t **open surface** (§26.10 D): the withdrawn announcement's pad retention, `PF_LOST`'s arbitration priority, `SCHEDULE`'s `-3`, the `A − H ≤ −3` regime | 4 items | model-shared | as written in §26.10 D |
| **R1** | rig | **CLOSED (SM2) — 12 bits in RTL, in the host tool, in FLASH #4 and on the board; proved on the wire and on the pin.**  ~~`evt_hold` is 8 bits. Decision OPEN.~~ The 12-bit drop-in is measured; it is a host-protocol change in three call sites AND must go into both bitstreams | 760 of 1,008 seeds | **rig** | the owner's decision (verdict §(e) item 2) |
| **R2** | rig | **the TB still models pad FLOAT RETENTION and the fabric does not.** That asymmetry is exactly X1's mechanism, and it is the remaining scope of the U5 mask work | whole TB | rig | rides X1's intervention |
| **R3** | rig | **F45's guidance comment in `tb_v30_core.sv` is still wrong** — it says *"Run many seeds: most flips must diverge"*; the correct guidance is *step the seed by 16* | 1 comment | rig | one comment edit; TB was frozen for scoring |
| **R4** | rig | **`s15_census.py` cannot classify an RTL core's residue.** It takes only the SEED LIST from `--report` and unconditionally replays the C++ model (`s15_census.py:169`). Pointed at a `--core ucore` report it silently reports the MODEL's families | the whole taxonomy leg | **rig** | give it `timed_fuzz.run_tb`; until then there is **no instrument that classifies the ucore's own fuzz residue by the seven families** |
| **R5** | rig | the ucore's **CE-hold probe has no EU coverage** (F50 item 3) — it watches BIU state only | 1 probe | rig | add `u_eu` state to `tb_v30_core.sv:1204`'s digest |
| **R6** | rig | **CLOSED (SM2) — VERIFIED as the same pad artefact; 10 reps × 5 cells banked.**  ~~the s10/s13 sweep retention gaps~~: `HLT.INT_w2_d0`'s `stable_identical: false` is NOT verified as the same pad artefact as `HLT.INT_w0_d0` — the per-repetition rows were never banked | 1 cell | rig | needs the board: bank per-rep rows |
| **R7** | doc | **`ROADMAP.md` carries stale U4 pass-3 figures** (26 % ALMs / 45.56 MHz, "two flashes") where the campaign closed on the U5 build (27 % / 48.03 MHz, three flashes) | 2 statements | doc | **FIXED this session** in `ROADMAP.md`; recorded in §Z.3 item 3 |

---

# THE DETAIL

## §F FUNCTIONAL

### §F.0 WHAT IS COMPLETE — stated plainly, because the gaps only mean something against it

Every figure below was **re-run on this tree on 2026-08-04**, not inherited.

| | |
|---|---|
| **G3 — the v0.1 golden suite** | **169,000 / 169,000 `full`, `cycles` 169,000, `arch` 169,000.** Every form, every case, cycle-exact AND architecturally exact against the silicon goldens. There are no forms unimplemented by design in this suite and no forms excluded. At w0 the reference model carries no registered residue, so §29.2's two-number rule gives the same figure with or without it subtracted. |
| the wait axis | `v0.1-w1` 1,200/1,200 · `-w3` 1,200/1,200 · `EB` at w1 200/200 |
| the event axes | all four `evt` cells **200 / 1,200 / 200 / 1,200**, plus the preserved biased tranche 1,200/1,200 |
| **block I/O (6C-6F)** | **229,999 / 229,999 cycles AND arch** over 23 `v0.3` forms — *measured this session, the ucore's first* (§F.3) |
| the EA-wrap battery | `f4a_boundary` **160/160** — *ucore's first, this session* |
| BUSLOCK | `f0lock_tranche` **400/400** — *ucore's first, this session* |
| boot | `check_boot` **220 rows MATCH** and **400 rows MATCH**, loop period 64 on both legs |
| RTL-vs-model lockstep | `ulockstep --golden all --cases 5` **1,735/1,735 ALL LOCKSTEP**; at `--cases 50`, 17,350/17,350 |
| the silicon wvec freeze | **88/88 digest, 88/88 access count, 16,048 vs 16,048 bus cycles, +0.0 %** |
| whole-program replays | ENTER **154/154 ×5** (incl. `halt_display` 154/154) · INS rails **1,312/1,312** and vs-chip **2,624/2,624**, with bus-stream agreement 173,556/173,556 leading accesses, all same-T1 |
| the real integration | `check_ab_sim` **187 rows MATCH** |
| the save-state map | `ss_lint` rc=0 — 218 addresses, **201 architectural flops, 0 UNMAPPED**, 2 whitelist entries, `SS_VERSION` 0x82 |
| the generation stack | **G0 9,988/9,988** both legs · disasm byte-exact · 21 PLA checks · optable 0 errors |
| **in fabric** | the priority tranche **176/178 (98.9 %)**, V0-V5 all met, V3 at ZERO seeds apart; a second frozen population **435/449 (96.9 %)**; first light **800/800 ×3**; fabric ↔ Verilator **200/200 identical** |
| per-opcode timing exceptions | **zero.** "grep for one" stays true. |

**And what "fully functional" still excludes**, which is the rest of this
section: 8080/BRKEM (§F.1), three of the four golden suites (§F.2), and the
recognition shadows nothing reaches (§F.4).

### §F.1 8080 / BRKEM — STRUCTURALLY UNREACHABLE, AND `sim/` IMPLEMENTS IT

**Owner: ucore. This is the largest functional gap and it is the only one that
is also an undeclared RTL-vs-model divergence.**

> **AND IT IS NOW COSTED, 2026-08-04 (SM3 sitting 4, `ucore_provenance.md`
> §63.5).**  This gap was carried as functional-only.  Measured against the
> banked bus captures it is **92 seeds of the ucore's timed residue** — 71 % of
> the `PF_LOST` family the ranked list called *"H3, arbitration priority"*.  The
> mechanism is one place: `sw/gen_soup.py` points **all 256 IVT vectors** at a
> bare handler at `0x0480` (`CF` IRET / `CB` RETF), so every soup program that
> takes an interrupt lands there; in 8080 mode the chip and the model execute
> that `CF` as **`RST 1`** (two-byte push, then fetch on at `0x00008` — present
> in 92/92 of the chip windows) and the ucore executes it as the native IRET's
> three stack pops.  Engine cell at the contested slot: **`MEMR` on 92/92** for
> the ucore, **`MEMW` on 88/88** for the model.  All **50** banked `has_brkem`
> seeds are in this class and in no other family; 42 more reach it without the
> flag (18 of those contain a `0F FF` pair, **24 do not, and how those 24 enter
> 8080 mode is NOT ESTABLISHED**).

The tables carry 8080 mode. `ucrom.hex` holds BRKEM at `0348-034B`, the 8080
main page `110` at `034C-03FB`, the 8080 `ED` page `101` at `03FC-0403` (RETEM
`03FC-03FE`, CALLN `0400-0401`); `ucdecode.hex` is a full 8,192-entry
`{page[2:0], opc[7:0], rowgrp[1:0]}` table that addresses those pages.

The RTL renders the *state*: `mode8080` is written by `I_MFS`/`I_MFC`/`I_ENDEM`
rows (`v30u_eu_row.svh:117-119`), published on the status pins as S6
(`v30u_biu.sv:400-402`, M9), save-state mapped (`SSA_E_MODE8080` 0x134,
`SSA_E_OPC8080` 0x133), and the 8080 ALU-opcode permutation is rendered
(`v30u_eu.sv:775-787`). M13's 8080 arm of `wait_opr_free` was landed as Codex
finding **C4** and flagged unreachable at the time.

**But the loader never selects the 8080 decode page.** `v30u_eu_step.svh:77`
and `:126` — the only two decode sites — read

```systemverilog
pv = ld_ext_n ? pla3_ext(ld_b_n) : pla3_native(ld_b_n);
```

`pla3_mode8080` is never called from the loader (its one live caller is the
queue-byte HALT predicate at `v30u_eu.sv:1441`), and `ld_page_n`'s only two
writers (`v30u_eu_step.svh:172`, `:313`) emit pages 0-4 only. Pages `110` and
`101` are therefore **structurally unreachable**. `opc8080_n` is likewise only
ever assigned `1'b0`, so the ALU permutation is dead.

The generator recorded the decision at the time and it was a reasonable one —
`ucrom_census.json:40`: *"ucore has no BRKEM path at U0 and a second table would
be dead silicon."*

**What makes it a gap rather than a scope decision is the asymmetry.** The
`ucore`'s governing rule is *"identical to `sim/` clock-for-clock"*, and `sim/`
**does** implement 8080 mode — `ucsim_provenance.md` §55, with row-execution
results BRKEM 2/4, the 8080 page 153/176, the 8080 `ED` page 5/8 against 0/4,
0/176, 0/8 in the other column. So the ucore and its own spec differ, by
construction, on 192 ROM rows, **and no gate can see it**:

* `v0.1` contains no `0F FF`, `ED FD` or `ED ED`;
* in the fuzz bank the gap is *covered by a standing acceptance rule* —
  `sw/fuzz_accept.py`'s `BrkemGapRule`, `klass = "8080-gap"`. **Measured this
  session: it fires on exactly 50 REGISTERED seeds, and on the SAME 50 for both
  engines.** The rule is honest (it refuses when the first divergence precedes
  the BRKEM fetch), but it means the bank cannot grade this;
* `sim/coverage_report.txt:37` — `UNION : 912/1028 executed, **116 never
  executed**`, and `:285` names the residue as *"the INTEM bank, the BRKEM entry
  and 158 of the 192 8080-mode rows."*

Wider exposure than `0F FF` alone: `docs/facts/undocumented_0f.md:27,31,45-51`
records that **every probed `0F xx` with `xx ≥ 0x40` is a BRKEM alias with full
BRKEM semantics.** `ROADMAP.md:590` already books that *"`has_brkem`
under-reports — 189 of 3,242 seeds put emulation mode on the bus"*, against the
50 the accept rule fires on.

**Closer**: either render the 8080 loader page select and the BRKEM / RETEM /
CALLN entry-exit path, **or** register an explicit, gated scope exclusion. Today
there is neither — the gap is real and it is undeclared, which is the part that
matters. Blocked upstream on the same thing `OPEN_QUESTIONS.md` Q13 is blocked
on: the RETEM/CALLN recovery-path infrastructure, listed in `ROADMAP.md:268` as
standing infrastructure never built.

*Falsifier for "unreachable"*: any stimulus that puts `ld_page_n` at 5 or 6.

### §F.2 THREE OF THE FOUR GOLDEN SUITES HAVE NEVER BEEN RUN AGAINST THE ucore

**Owner: coverage.** The ucore was graded on `tests/v30/v0.1` (169,000) at every
stage U0-U5. The deferral is on the record, from U0 (`ucore_provenance.md`
§ "Gates NOT run at U0"):

> *"the `v0.2` (347,000), `v0.3` (3,699,998) and `v20suite` (3,125,000) golden
> suites and the `t30_sweep.sh` pre-reflash bar — those are the EU-decode-path
> change bar, and U0 changed no RTL."*

U0 changed no RTL. **U1 through U5 changed a great deal of it**, and the
deferral was never revisited. Of the model's 7,341,126-case functional corpus,
the ucore has been graded on **169,000** — 2.3 % — plus this session's 229,999
(§F.3), the two small batteries in §F.0, and the whole-program banks.

| suite | cases | ucore |
|---|---|---|
| `v0.1` | 169,000 | **169,000 / 169,000** |
| `v0.2` | 347,000 | **never run, and CANNOT BE RUN by `check_core.py` today** — see below |
| `v0.3` | 3,699,998 | **never run in full**; its 23 block-I/O forms measured this session at 229,999/229,999 |
| `v20suite` | 3,125,000 | **never run** |

*Why this is a gap and not bookkeeping*: `v0.3` is the only suite carrying
block I/O, and `v20suite` is the independent µPD70108 architectural oracle. A
core graded only on `v0.1` is graded on the population it was DEBUGGED against.

**AND `v0.2` IS BLOCKED ON A TOOLING DEFECT, not on time — measured this
session.** `sw/check_core.py --suite-dir tests/v30/v0.2` dies on the first form
with `KeyError: 'opcodes'` at `check_core.py:709`, **for either core**:

```
tests/v30/v0.1/metadata.json      keys: [... 'opcodes' ...]   <- the SST schema
tests/v30/v20suite/metadata.json  keys: [... 'opcodes' ...]
tests/v30/v0.2/metadata.json      keys: ['FIXED_seed_base_note', 'capture',
     'cases_per_form', 'cpu', 'date', 'emitter_commit', 'forms', 'seed_base',
     'source', 'suite', 'use_core', 'variants', 'waits']   <- the EMITTER schema
```

`v0.2` was emitted with the emitter's own manifest schema and `check_core`'s
flags-mask resolution reads the SingleStepTests `opcodes` map unconditionally.
So the suite has **never been runnable** through this checker — which is a
better explanation of the un-revisited U0 deferral than "nobody got to it", and
it means the gap cannot be closed by simply starting a long run. *Closer*: teach
`check_core.py:709` to fall back to `flags_mask = 0xFFFF` when the manifest
carries no `opcodes` map (and say so loudly), or emit a compatible manifest.
**Not fixed here — this session changes no behaviour.**

### §F.3 INM / OUTM (6C-6F) — MEASURED THIS SESSION, AND IT IS GREEN

**CLOSED.** The mechanism was rendered — `pla3_tables.svh:219-222` gives
`8'h6C..8'h6F` the non-null native entry `14'h1006` (`xop` nibble `0110` = block
I/O), and `v30u_eu.sv:496-498` renders `exec_impl.h::sr_is_io`'s block-I/O arm:

```systemverilog
wire row_io  = (e_sr == 2'd1) && ((xop == 4'hF) || (xop == 4'h6));
```

…but **`ucore_provenance.md` never mentions the forms**, because `v0.1` has none
and `v0.3` was never run. Measured on this tree, `--core ucore`, all 23 `v0.3`
block-I/O forms:

```
6C 6D 6E 6F · F26C F26D F26E F26F · F36C F36D F36E F36F
646C 646D 646E 646F · 656C 656D 656E 656F · 26.6E 2E.6F 36.6E
TOTAL: 229,999 / 229,999 full (cycles 229,999, arch 229,999)
                                   [1 documented pre-existing excluded: 646F/[8988]]
```

**Registered as a ucore ratchet.** *Disambiguation, because the names collide*:
`timed_ins_replay`'s 1,312/2,624 is the **bit-field INS** (`0F 31` / `0F 39`,
ROM rows `0318-0347`) and says nothing about block I/O. The two were conflated
nowhere in the ledger, but the names invite it.

### §F.4 CARRIED FORWARD, DOCUMENTED-BUT-NOT-RENDERED

Unchanged from verdict §(d) item 4; re-stated so this document is complete.

* **the far-CALL / far-JMP `CS` recognition shadow** and **the taken-branch
  recognition boundary (`post_flush`)** — documented in the ledger, not rendered
  in the RTL. **No golden reaches either.** The `post_flush` boundary was a
  fuzz-seed refinement in the archived FSM core.
* **`opr_free_p` / `set_oprfree`** — **PROVABLY VACUOUS** (F31), recorded so it
  is not re-derived.
* **the A30 ambiguous micro-address** `111.00000010.00` — two banks match,
  first-match-wins; emitted at the sim's fixed-priority bank-B winner, with the
  alternative recorded and a falsifier attached. No scoped form reaches page 7
  opcode 02.

### §F.5 WHAT NO SUITE THE ucore HAS RUN CONTAINS

There is **no single document that enumerates this**, which is itself worth
recording. Derived from `tests/v30/v0.1`'s 347 forms against `sw/optable.py`:
`6C-6F` (closed by §F.3), `82` (the undocumented ALU-imm alias), `8F.1-.7`,
`C6.1-.7`, `C7.1-.7`, `D6`, `F1`, the `0F` space beyond the 20 whitelisted
forms, `0F FF` / `ED FD` / `ED ED` and the whole 8080 page, and the register-set
expansions (`41-47`, `49-4F`, `51-57`, `59-5F`, `91-97`, `B1-B7`, `B9-BF` — the
suite treats reg-field variation as within-form randomisation). `F0` BUSLOCK is
covered by `f0lock_tranche` (§F.0). `tests/v30/v0.1/README.md`'s own "Known
limitations" list is stale in both directions.

---

## §T TIMING — OFFLINE

### §T.1 THE HLT DELAY SWEEPS — 259/283, and 13 cells are the ucore's alone

**Owner: ucore.** Re-run this session on both legs; both reproduce exactly.

| sweep | **model** | **ucore** |
|---|---|---|
| `s10-hltsweep-w0` | 91 / 97 | **91 / 97 — ON the model** |
| `s10-hltsweep-w1` | 95 / 95 | **90 / 95** |
| `s13-hltsweep-w2` | 44 / 46 | **40 / 46** |
| `s13-hltsweep-w3` | 42 / 45 | **38 / 45** |
| **total** | **272 / 283** | **259 / 283** |

The model's 11 failures are a **strict subset** of the ucore's 24, and **at w0
the two failing sets are IDENTICAL**. The 13 ucore-only cells, by failing `idx`
(the `idx` FIELD is the pin delay `d` — §43.0's numbering trap, and the source
of this campaign's one retraction):

| sweep | ucore-only failing `idx` | n |
|---|---|---|
| `s10-w1` | `HLT.INT` 7, 8, 9, 10 · `HLT.RES` 7 | 5 |
| `s13-w2` | `HLT.INT` 9, 12, 13 · `HLT.RES` 9 | 4 |
| `s13-w3` | `HLT.INT` 11, 15, 16 · `HLT.RES` 11 | 4 |

**The first-divergence column census, measured this session** (this is new — the
ledger states the split in prose and never printed the columns):

| sweep | `HLT.INT` first-div | `HLT.RES` first-div |
|---|---|---|
| w0 | `(7,'bus')`×2, `(4,'busstat')`×1, `(3,'busstat')`×1 | `(4,'busstat')`×1, `(3,'busstat')`×1 |
| w1 | `(9,'seg')`×2, `(5,'busstat')`×1, `(10,'bus')`×1 | `(5,'busstat')`×1 |
| w2 | `(10,'seg')`×2, `(6,'busstat')`×1, `(11,'seg')`×1 | `(6,'busstat')`×1 |
| w3 | `(11,'seg')`×2, `(7,'busstat')`×1, `(12,'seg')`×1 | `(7,'busstat')`×1 |

Two mechanisms, no third and no catch-all:

* **the `busstat`-first half is F43** — *the HALT-display decision must test the
  wake condition visible on its own decision edge* (M20's threshold-1). It is
  **diagnosed and deliberately not landed, twice** (U4 and U5), for a stated
  reason: it touches the BIU's **eval instant**, the module's spine, and both
  stages declined to move it while the ladder was being scored.
* **the `seg`/`bus`-first half is residue the corrected instrument NEWLY EXPOSES
  and is NOT diagnosed.** Booked with a falsifier rather than absorbed into
  F43's count.

*Falsifier for the pair*: a cell in the band whose first divergence is neither
the HALT display's own decision edge nor a woken display inside the pseudo-cycle.

**Retired, so it is not re-quoted**: §43.2's *"17 cells no comparator on this TB
can score"*. F42 was refuted in fabric; the cells are scoreable and 10 of them
now pass.

### §T.2 THE ucore's OWN REGISTERED-BANK RESIDUE IS **NINE** SEEDS

**Owner: ucore. This is the sharpest number in the document and it is new.**

`timed_fuzz` was run twice on this tree over the same frozen 1,702-seed
registered population — once `--core ucore`, once `--core sim` — and the two
reports compared **seed by seed**:

```
REG: scored 1,702      ucore non-exact 219      sim non-exact 430
     ucore-ONLY (the sim is cycle-exact, the ucore is not)      9
     sim-ONLY   (the ucore is cycle-exact, the sim is not)    220
     shared non-exact                                        210
```

Net +211, which reproduces §49.6's *"the ucore beats the model on the registered
bank by 211 seeds"* exactly, and decomposes it for the first time.

**The nine, named, with their first divergence:**

| seed | first-div | detail | `ndiff` | first_bad | waits |
|---|---|---|---|---|---|
| `mc1/412` | `data` | `0000 != 00de` | 666/1,352 | 634 | wrand2 |
| `mc1/721` | `data` | `b084 != b085` | **2/968** | 357 | wrand3 |
| `mc1/1937` | `data` | `9090 != f896` | 42/4,000 | 1,955 | fix1 |
| `mc1/3325` | `data` | `0000 != 3f01` | 1,318/4,000 | 2,661 | fix0 |
| `mc2/584` | `qs` | `F != -` | 404/1,774 | 1,135 | wrand15 |
| `mc2/2216` | `data` | `9090 != ff90` | 2,320/4,000 | 1,573 | wrand1 |
| `mc2/3291` | `data` | `0480 != 0499` | 240/4,000 | 1,981 | fix3 |
| `t30-raw/84` | `data` | `0000 != 8b39` | 2,952/4,000 | 974 | wrand2 |
| `t30-raw/123` | `data` | `0cd7 != 9090` | 2,124/4,000 | 1,843 | wrand1 |

**Eight of nine are `data`** — F47's shape exactly: *the right cycle, the right
address, the wrong word* — and three are at FIXED waits, so this is not a
random-wait-only corner. `mc1/721` with `ndiff = 2` is §49.8's `10`/ADC
carry-in seed (`sigma` differs by exactly 1).

**The named sub-mechanisms** (§49.8, unchanged and still un-landed):

1. **`8F`'s write-back drives a stale OPR when the pop lands at or after T1.**
   The model gets it free because `rdq_` is filled at ISSUE time; the ucore's
   `opr_now` lookahead covers a completion on the pairing clock ONLY.
   *Falsifier*: an `8F` seed whose completion lands strictly before T1 and whose
   word is still wrong.
2. **`10`/ADC's carry-in.** Two instructions back are `9E` SAHF (AH bit → CY=1)
   then `F5` CMC (CY → 0), both executed by the loader with ZERO micro-rows, and
   **which of the two fails to land was NOT decided** because both produce CY=1.
   **The deciding measurement is written down and un-run**: `SSA_E_PSW` is
   already in the map, so `+ss_at=<clk>` reads PSW out at the boundary between
   them **on the frozen binary, no RTL change**, against `PSW=` in
   `v30sim image --trace`.
3. **one unexplained.**

**A ledger correction.** §49.8 is titled *"THE RESIDUAL TEN"* and its third item
is *"`raw_15` under `50`, chip `ffc9` / ucore `ffc7`, off by 2."* Measured today,
**`t30-raw/15` is a seed the SIM misses too** (`bs CODE!=PASV nxta 0fe4!=78ed`),
so by the governance partition it is **model-shared, not ucore-only** — and the
ucore's own residue is **nine**, not ten. The divergence §49.8 describes is real
and is the ucore's; the *seed* is not exclusively the ucore's. Net +211 is
unaffected. Recorded here rather than edited into §49.8, per the standing rule.

### §T.3 THE OTHER 210 ARE SEEDS THE MODEL MISSES TOO

**Owner: model-shared.** Their families, against the inherited seven-family
taxonomy (`ucsim_t_provenance.md` §26.10 C), measured this session:

| family | the **model's** REG residue (430) | of which the **ucore also misses** (210) | the ucore closed |
|---|---|---|---|
| `PF_LOST` | 239 | 110 | 129 |
| `SCHEDULE` | 79 | 12 | 67 |
| `TAIL_EXTRA` | 30 | **30** | **0** |
| `DATA_SEQ` | 28 | **28** | **0** |
| `PF_GAINED` | 23 | **23** | **0** |
| `PF_ADDR` | 17 | 4 | 13 |
| `PIN` | 14 | 3 | 11 |
| **total** | **430** | **210** | **220** |

The catch-all is EMPTY, as it is for the model. **Three families the ucore
closed NOTHING in — `TAIL_EXTRA`, `DATA_SEQ`, `PF_GAINED`, 81 seeds, the same
seeds in both engines** — which is the sharpest possible statement that those
three are the MODEL's mechanisms and not renderings. The four the ucore
improved are all arbitration/schedule families: `PF_LOST` −129 and `SCHEDULE`
−67 carry the whole +211.

**READ THIS BEFORE QUOTING THE TABLE.** The family labels come from
`sw/s15_census.py`, and **`s15_census` replays the C++ MODEL unconditionally**
(`s15_census.py:169`, `tf.run_sim(...)`) — it takes only the SEED LIST from
`--report`. So the right-hand column is *"the model's family, on the seeds the
ucore also misses"*, **not a census of the ucore's own divergence shape.** That
distinction is the honest one and it is booked as **R4**. What the table does
establish, and establishes exactly, is the seed-level partition 9 / 210 / 220 of
§T.2, which is computed from the two `timed_fuzz` reports directly and does not
involve `s15_census` at all.

**The ucore's own verdict census** of its 219 REG non-exact seeds, which does
come from its own engine: `TIMING` 107 · `FUNCTIONAL` 61 · `KNOWN_ACCEPTED` 51
(of which **50** are the `brkem_gap` rule, §F.1, and 1 `cadence_sample`). The
model's, for scale: `TIMING` 285 · `FUNCTIONAL` 91 · `KNOWN_ACCEPTED` 54 (the
same 50 `brkem_gap` + 4 `cadence_sample`). `FUNCTIONAL` here is the functional
EVENT-STREAM comparison, which a timing divergence truncates — it is not a
register-file claim, and no instrument in the tree makes a register-file claim
about the ucore over this bank.

### §T.4 THE TWO `bs` SEEDS OF THE PRIORITY TRANCHE — model-shared, decisively

**Owner: model-shared.** §54.5:

| seed | waits | ucore first-div | SIM first-div | **pairwise** |
|---|---|---|---|---|
| `mc1_300043` | `wrand wmax 2` | row **403**, ndiff 3,419/4,000 | row **403**, ndiff **3,419/4,000** | **0 / 4,000 rows differ** |
| `mc1_300122` | `wrand wmax 7` | row **402**, ndiff 3,570/4,000 | row **402**, ndiff **3,570/4,000** | **0 / 4,000 rows differ** |

At the divergent row the two engines are byte-identical — same address, same
data, same status nibble — and both issue an EU `MEMR` where the chip issues a
`CODE` fetch. **The entire residue of the campaign's victory tranche is a
divergence the reference model SHARES, bit for bit.** Both are in V5's closed
`bs` taxonomy, which is where the model's own registered bank residue sits.

*Falsifier*: a re-derivation in which the sim's rows at those clocks differ from
the ucore's.

### §T.5 THE EVT COLUMN IS RIG-POISONED AND IS NOT A GATE

> **CLOSED 2026-08-04, session SM2.**  The 760 were re-captured on FLASH #4 at
> their banked hold of 300 and the column is a gate again: **ucore 468/1,008
> (46.4 %), sim 363/1,008 (36.0 %)**, `INVALIDATED` 0.  *(SM3 sitting 3,
> after H1 landed in BOTH engines: **ucore 906/1,008 (89.9 %), sim
> 780/1,008 (77.4 %)** — the ucore now leads by 126.)*  The "547 ucore-only
> non-exact seeds" below were the rig: on the corrected captures the ucore
> LEADS the model by 105 seeds where as banked it appeared to trail by 517.
> The falsifier stated at the foot of this item was answered directly on the
> pin — 2 INTA T1 rows at `hold=44`, 6 at 300, 12 at 600.
> See `docs/notes/invalidation_ledger.md` §CLOSURE and
> `ucore_provenance.md` §59.7.3-§59.7.7.  **The reading below is retained as
> written, because it was right.**

**Owner: rig (F46).** Measured this session, same two-report comparison:

```
EVT: scored 1,008   ucore non-exact 816   sim non-exact 299
     ucore-ONLY 547     sim-ONLY 30     shared 269
```

**547 ucore-only** is not a core defect; it is F46 arriving exactly where F46
said it would. `hps_axi_slave.sv:275` stores `evt_hold <= wdata[23:16]` — **8
bits** — and **760 of the 1,008 EVT seeds bank `hold = 300`**, so the socket was
held for `300 & 0xFF = 44` clocks, not 300. The MODEL cannot notice: under
`--evt-replay` it is HANDED the capture's acknowledge positions. The ucore
PREDICTS them from the directive, so given a nominal 300-clock INT level it
re-enters the handler 2-4 times where the chip entered once — **545 of 545 INTR
trails diverge as "extra INTA pairs", and 540 of those 545 put the FIRST
acknowledge on exactly the chip's clock. The recognition is right; the directive
was never physically applied.**

`--rig-hold reg8` moves the **model's** EVT number too (+71) as well as the
ucore's (+682), so it is OFF by default and the EVT ratchet is **not**
re-registered against it. The standing figures are therefore two readings, not
one: EVT 192/1,008 as banked.

*Falsifier*: a capture in the EVT population whose acknowledge pattern is
consistent with a hold longer than 255 clocks.

### §T.6-§T.9 THE REST OF THE OFFLINE RESIDUE

* **§T.6 — the b2 victory tranche: 171/188.** Re-run this session:
  `DIVERGE 17 · EXACT 171 · OPEN_BUS 28`, denominators held. **V5 remains a
  standing REGISTERED FAILURE** (171 ≠ 188) and is **not re-opened, not
  re-scored and not to be quietly restated.** The model is 154.
* **§T.7 — 5 `BOUND WARNINGS`.** Seeds whose EU completed-read store saturated,
  i.e. ran outside the regime `sw/qdepth_probe.py` proves (`rdq_` ≤ 2,
  `rd_done_q_` ≤ 1 on v0.1 at w0 and on w1/w3 and all four evt suites). Scored
  normally, **not excused**; `ENGINE ABORTS` is **0**. §46 proved the two-slot
  bound over every graded corpus *and* met its own falsifier on runaway
  stimulus, so the capacity was deliberately **NOT** deepened — fitting two more
  slots to garbage is the large-fitted-table failure the standing SIMPLICITY
  principle names. A bound fire on a GOLDEN case is a hard failure in
  `check_core.py`; that is where the bound is a theorem.
* **§T.8 — the 4 shared seeds (§49.7).** Three are an exact **byte swap on an
  odd-address word write** — M5b's A0 swapper applied where the chip does not.
  The ucore and the model **agree with each other and disagree with the
  socket**, with identical `ndiff` on all four. **model-shared**; deliberately
  not patched.
* **§T.9 — 14 of the 500-seed in-silicon population** (435/449, residue `bs` 11 ·
  `qs` 3). Note the direction: the FABRIC leg is the BETTER one there — two
  `data` divergences the MODEL has and the BITSTREAM does not.

---

## §X TIMING — FABRIC

### §X.1 THE 116 INTA-RETENTION CELLS — presented exactly as registered

**Owner: harness — NOT ESTABLISHED.** This is verdict §(d) open item 0, ledger
§56.1-§56.3a, and Codex review finding **C11**. It is reproduced here verbatim in
substance because paraphrasing it is how a reading becomes a finding.

**The measurement.** On the U5 bitstream the four HLT sweeps score **143/283 in
fabric** against **259/283** offline on the same RTL. §55.2 bar 2 was registered
at **≥ 249/283, expected 259 ± 4**. It is reported as **MISSED**.

| sweep / form | offline | **fabric** | fabric-only failures | all on an INTA row? |
|---|---|---|---|---|
| `s10-w0` `HLT.INT` | 44/48 | **0/48** | 44 | **yes** |
| `s10-w0` `HLT.RES` | 47/49 | **47/49** | 0 | — |
| `s10-w1` `HLT.INT` | 42/46 | **0/46** | 42 | **yes** |
| `s10-w1` `HLT.RES` | 48/49 | **48/49** | 0 | — |
| `s13-w2` `HLT.INT` | 16/21 | **0/21** | 16 | **yes** |
| `s13-w2` `HLT.RES` | 24/25 | **24/25** | 0 | — |
| `s13-w3` `HLT.INT` | 14/20 | **0/20** | 14 | **yes** |
| `s13-w3` `HLT.RES` | 24/25 | **24/25** | 0 | — |
| **total** | **259/283** | **143/283** | **116** | **116 / 116** |

Two exact statements: **`HLT.RES` in fabric is IDENTICAL to `HLT.RES` offline,
cell for cell** — the Verilator model of this bitstream IS the bitstream on that
form — and **no cell fails offline and passes in fabric**: the fabric is
strictly stricter, never differently strict.

**The reading, and it is a READING.** At an INTA's T1 the chip's AD pads float
and RETAIN the previous data phase; in the FPGA the core's AD is an internal
`tri` net inside `system_large` which Quartus resolves to a mux, so there is
nothing to retain and the row reads the harness's INTA vector byte instead. This
is the campaign plan's registered **risk #4**, and it is already the documented
column policy of the OTHER fabric gate (`check_ab_hw.py` excludes float-retention
rows and is 800/800 on the same bitstream in the same session).

**Why it is NOT ESTABLISHED (C11).** The argument has the SAME SHAPE as F42's:
*"the failing cells are an artefact of how the pins are observed, not of the
core."* F42 was accepted as sound by C6, measured **population-complete at
24/24**, and **REFUTED in fabric anyway** — because a population-wide
correlation is not a causal demonstration. §56.3's evidence is stronger in every
dimension and is **still the same kind of evidence.**

**THE SETTLING MEASUREMENT — PRE-REGISTERED AND NOT RUN (§56.3a).** It is an
INTERVENTION, which is what the correlation is missing.

* **The intervention**: give `system_large.sv`'s `core_ad` an explicit retention
  model — a register capturing the last DRIVEN value of AD, supplied when no
  driver is active. **Nothing in either core changes, and `v30u_biu.sv` in
  particular must NOT be touched**: its INTA path deliberately drives no address
  (`disp_inta || cur_inta` selecting `20'h0` with `ad_oe_ps`), which is
  `sim/biu_timed.cpp`'s `Access::no_addr` rendered faithfully. An intervention
  that also changed the core would confound the question being asked.
* **The population**: the same four sweeps, all 283 cells, same driver, same
  goldens, plus the 49-cell socket control.
* **THE BAR, BOTH HALVES, BOTH REQUIRED**: (i) **all 116 close** and the fabric
  total reaches **259/283 exactly**, not merely toward it; (ii) **nothing else
  moves** — `HLT.RES` cell-identical at 47/49, 48/49, 24/25, 24/25; every
  `HLT.INT` cell matching its OFFLINE result cell for cell; no non-INTA row
  acquiring a new first divergence; the F42-signature count still ZERO; the
  socket control 49/49; `use_core=0` MATCH over 800 rows with first light
  800/800 ×3.
* **WHAT REFUTES IT**: any of the 116 still failing with the retention model
  demonstrably supplying the prior driven data phase, or any fabric-only
  NON-INTA divergence. A surviving divergence is **reclassified as CORE-OWNED**
  unless a separately pre-registered mechanism is established for it, and is
  **reported as a refutation and not re-explained.**
* **Cost**: a change to the A/B harness both cores' fabric numbers depend on, so
  it needs its own pre-registered before/after on both cores, a Quartus compile
  and a flash.

> **SM2, 2026-08-04 — THE FABRIC LEG WAS ATTEMPTED AND IS *BLOCKED*, NOT
> REFUTED.**  The BASELINE re-measured on FLASH #4 reproduces this table
> **cell for cell and form for form: 143/283, 116 fabric-only, 116/116 on an
> INTA T1 row**, with the socket control at 49/49 and the `use_core=0` boot at
> MATCH 800 ×3 — so the population is intact on the new bitstream.  The
> INTERVENTION could not be built: `core_ad === 1'bz` is a four-state test on
> an internal tri-state, and Quartus 17.1 folds it to a constant, deletes the
> hold register for want of fanout, and hands back a bitstream identical in
> function to the baseline (**demonstrated in isolation**: the same construct
> alone synthesises to 5 logic cells and *"No output dependent on input pin
> clk"*).  Running the after-leg on it would have reported "116 survive",
> which reads like a refutation and would have been an instrument failure.
> **Pre-registered as a liveness test in `ucore_provenance.md` §59.3 and
> reported as it was registered, in §59.7.1.  C11's NOT ESTABLISHED stands.**
> A synthesizable keeper needs an "is anyone driving" term whose only honest
> source is the core's own output enable — not a port, and forbidden by this
> registration to manufacture — so the item is handed on with its cause named
> rather than re-scoped after the fact.

**Two candidate fixes, NEITHER taken.** The retention model above, or teaching
the fabric scorer `check_ab_hw`'s exclusion — **which would be choosing a
comparator after seeing the result**, and is not a thing this campaign is
allowed to do.

*Falsifier for the reading as it stands*: a fabric cell whose first divergence is
an INTA row whose golden value is NOT the retained previous data phase, or any
non-INTA fabric-only failure at any wait level.

### §X.2 F42's fixed-but-fabric-rescore state

F42 is **CLOSED as an RTL item and REFUTED as a claim.** Its registered
prediction was that the 17 "uncountable" HLT cells would PASS in fabric; they
failed (29/283), and the mask had been **hiding a real divergence rather than
manufacturing one** — the opposite of what F42 claimed. F51 fixed it:

| | U4 pass 3 | **U5** |
|---|---|---|
| the four sweeps, IN FABRIC | 29 / 283 | **143 / 283** |
| cells still showing `0x0AD8A` for `0x2AD8A` | 254 | **0** |
| the socket control, same driver | 49/49 | **49/49** |
| the four sweeps, offline | 249/283 | **259/283** |
| `HLT.RES`, fabric vs offline | different | **IDENTICAL, cell for cell** |

So bar 1 of §55.2 was **MET absolutely** and bar 2 **MISSED**, and the residue
of the miss is entirely §X.1.

### §X.3 WHAT EACH LEG COVERS THAT THE OTHER DOES NOT

**The fabric covers what offline cannot:**

* **pad-level behaviour** — float retention, multiplexed-pad drive, the real
  `system_large` integration. §X.1 exists only because the fabric sees it, and
  **F42 was refuted only because the fabric sees it**;
* **the socketed part as the adjudicator in the same session** (the 49/49
  control, the `use_core=0` 800-row chip path);
* **real clocking and the CE path at speed** — G6's 27 % ALMs, Fmax 48.03 MHz,
  worst setup +9.121 ns, TNS 0.000 on every domain, hold +0.244.

**Offline covers what the fabric does not:**

* **scale** — 169,000 golden cases + 229,999 block-I/O cases + 17,350 lockstep
  cases + 2,710 whole-program seeds. The fabric legs are 283 sweep cells, 178 +
  449 tranche seeds and 800 boot rows;
* **the architectural column** — `check_core`'s `arch` compare and the
  save-state sweeps have no fabric equivalent;
* **RTL-vs-MODEL lockstep** (`ulockstep`), which is the only instrument that
  compares the two engines directly rather than each against a golden;
* **internal state** — `+ss_at`, `+eutrace`, `uscope --rowtrace`, the bound
  assertions. The deciding measurement for §T.2 item 2 is one of these.

**And one thing NEITHER covers** — **CLOSED 2026-08-04 (SM2)**: the priority
tranche was re-captured on FLASH #4, both legs, and the ucore in fabric scores
**176/178 (98.9 %) with the same two-seed `bs` residue**, against a socket leg
that is 178/178 against itself.  The controlled substitution is removed and the
number reproduces.  `ucore_provenance.md` §59.7.9.  **The original statement of
the gap follows.**

*(as originally written)* the priority tranche was **not re-captured on
the U5 bitstream** (§55.2 item 6, a declared deviation). Its 176/178 is the
pass-3 bitstream's number, with the F51 change proved INERT on that population
offline (`vsim_ucore` 176/178, residue `bs` = 2, identical before and after).
That is a controlled substitution and it is stated as one, but it is not a
fabric measurement of the shipped bitstream.

---

## §I INHERITED AND CROSS-MODEL

### §I.1 THE SIM's `9D` FLAG-COMMIT ERRATUM — the one fix this campaign owes the model

**Owner: model. Booked, not patched, and it is owed.**

On `ulockstep`'s UNMASKED view the `9D` T4 PS nibble is a real, non-retention
difference in which **the RTL matches the silicon and the MODEL does not.**
`sim/exec_impl.h`'s `wr_dst1` FLAGS arm (`case 15: m_.set_flags(v)`) runs when
the micro-row RETIRES — three clocks later than the chip. F39 says the chip
commits at the read's data edge, and `docs/facts/interrupt_model.md` says so
verbatim: *"POP PSW consumes the popped image at its read's data edge (the new
IE shows in the PS bits during the read's own T4)."*

**The rule hits EXACTLY TWO ROM rows** — `007A` (POP PSW) and `01EA` (RETI), the
only rows carrying source `OPR`, destination `FLAGS` **and** the `F` interlock.
Five other rows write FLAGS and none takes `OPR` through an `F`. That is the
same pair E1 measured on silicon.

Why it has not been taken: it moves a column **both gates mask**, and the model
is at 169,000/169,000 today. It is a ONE-LINE change to `wr_dst1`'s FLAGS arm
plus the `F` wait's ordering. **It belongs to whoever next opens `biu_timed`.**

### §I.2 THE HALT DATA PHASE IN THE **SIM**'s RENDERING — checked explicitly, and it is CLEAN

**The task this document answers asked for this specifically, because the TB
masked BOTH RTL cores and the sim leg had to be checked on its own.** It was,
two ways, and the answer is that the sim does **not** carry F51's defect.

1. **Direct inspection.** `sim/biu_timed.cpp::note_halt` renders M10's live PS
   explicitly, and its comment records the measurement that put it there:

   ```cpp
   // M10 (T4): the HALT display's upper nibble is a LIVE PS, not a constant.
   // It was hard-coded to the bare segment code (CS = 2).  MEASURED on the
   // re-captured wvec corpus ... of 139 and 187 accesses in the two directed
   // law cells, EXACTLY ONE differs -- the closing HALT -- and only in this
   // nibble: chip 0x6, model 0x2 ...
   acc.addr = (uint32_t(data_ps(2)) << 16) | (last_fetch_addr_ & 0xFFFFu);
   ```

   It is `data_ps(2)`, not a constant. This is the exact expression F51 put into
   `v30u_biu.sv` and that `v30_biu.sv:1914` still lacks.
2. **The instrument argument, which is the stronger one.** The composed-AD mask
   lived in `hdl/tb/tb_v30_core.sv` — the **Verilator TB**. The sim leg
   (`timed_gate.py` → `v30sim timed-run`) never goes through it. So the model was
   always scored on the honest columns for these rows, and **its sweep numbers
   did not move at U5**: 91/97, 95/95, 44/46, 42/45 before and after, which this
   session re-ran and reproduced cell for cell. A masked engine's numbers move
   when the mask is removed; the model's did not.

**Booked as CLOSED.** No fix is owed to `sim/` on this axis.

### §I.3 INTA UNDER WAITS — closed as a law, open in two narrow places

* **CLOSED for the single-instruction population.** M18 — `INTA2's T1 = (INTA1's
  COMPLETION EVAL) + 5` at every wait level, 2,339/2,339 at N = 0,1,2,3 — and
  the ucore renders it: all four `evt` cells are **200 / 1,200 / 200 / 1,200**,
  where they were 0-to-a-case before F34/F40. `ucsim_t_provenance.md` §21.2:
  *"INTA UNDER WAITS IS NO LONGER AN OPEN LAW."*
* **OPEN — the second acknowledge's ANCHOR** (§26.6.4). The chip anchors it on
  the first acknowledge's DISPLAY (`+7/9/10/11` at `N = 0..3`, **135/135**), the
  model on its T1; the two separate on exactly 2 cells. **NOT LANDED**, because
  the sweep cells and §26.6.2's seven `bs PASV!=INTA` fuzz seeds point opposite
  ways. *The directed cell that separates them*: an acknowledge announced while
  another cycle still owns the bus (display-to-T1 gap of 2), at more than one
  wait level. **model-shared** — the ucore inherits whichever way it lands.
* **POISONED, not open** — the whole-program EVT column, §T.5.
* **UNKNOWN in fabric** — every `HLT.INT` cell fails in fabric at every wait
  level (§X.1), so the fabric says nothing yet about INTA under waits either way.

### §I.4 THE PARKED LAW-CARD PROBES — C6, C7, C11 still UNRESOLVED

Re-run this session: **8 GREEN / 0 RED / 3 UNRESOLVED.** They bear on the
ucore's spec completeness because the ucore is built from these cards.

* **C6 / C7 — LC3, the Tw-parity RMW commit.** The obstacle CHANGED at §26.5 and
  the change is the point: the corpus is no longer empty of RMW cycles, it is
  **full** of them (10,516 one-prefetch-gap RMW pairs at both Tw parities). What
  is missing is a **pin-observable signature for `ext_ok_wr` / `tw_par`** — the
  corpus is stratified, not controlled. Board-free from here. *A card is not
  GREENed by weakening what it asserts.*
* **C11 — LC4 `owns_slot`.** The reservation SOURCE is an EU micro-state and is
  **not observable on the pins**; `owns_slot` is an ENUMERATED source set
  (`S_DHI`, `S_PUSH_CALC@q>=2`) and no directed silicon capture isolates a single
  source. **Needs an instrument, not board time.** §26.4.1's 309 `PF_LOST` seeds
  are its pin-side shadow — and `PF_LOST` is the ucore's largest surviving
  model-shared family (§T.3, 110 seeds).

**The ucore renders all three cards as written.** If a card resolves differently,
the ucore changes with it — which is the correct dependency direction, and it is
why these are listed as spec-completeness gaps rather than as RTL bugs.

### §I.5 THE ucsim-t OPEN SURFACE, still four items

`ucsim_t_provenance.md` §26.10 D, unchanged. All **model-shared**; the ucore
inherits them because the ledger does.

1. **The WITHDRAWN announcement's pad retention** (§26.7.7) — after a withdrawn
   multi-clock announcement the chip's pads hold the WITHDRAWN cycle's address
   and UBE and the model reverts to the HALT's. 6 diffs × 5 cells, one uniform
   signature, board-free, stimulus already banked. This is the whole remaining
   w2/w3 sweep residue on the model side.
2. ~~**The second acknowledge's ANCHOR** — §I.3.~~  **CLOSED 2026-08-04 by
   H1** in both engines (§I.3 above; `ucore_provenance.md` §61-§62).
3. **The `A − H ≤ −3` regime** (§26.6.3) — 4 cells, all at w0. The chip's `d2`
   and `d3` rows are BYTE-IDENTICAL and the model's are not; any mechanism must
   make the model delay-insensitive across the pair FIRST.
4. **`PF_LOST`'s arbitration priority** and **`SCHEDULE`'s `-3`** — both
   MEASURED, both explicitly **NOT fitted**. These are the two families that
   carry the ucore's +211 (§T.3), so a mechanism here would move both engines.
   **SM3 sitting 3 promotes `PF_LOST` to the #1 open mechanism (H3)**: with H1
   closed it is 107 REG + 22 EVT = **129** ucore seeds and 239 + 70 = **309**
   model seeds, the largest single family in both engines
   (`ucore_provenance.md` §62.9).

---

## §R RIG AND HARNESS

* **§R.1 — `evt_hold` (F46). THE DECISION IS OPEN and it is the user's**
  (verdict §(e) item 2). The packing is already measured: register `0x20` packs
  `evt_delay[15:0] | evt_hold[23:16] | evt_pin[26:24] | evt_arm[31]`, free space
  is bits `[30:27]`, so the widest drop-in is a **12-bit** hold (max 4,095,
  covering the banked 300). It is a **HOST-PROTOCOL change as well as an RTL
  one** — `fuzz_campaign._evt_tuple`, `check_seq.run_tb` and `check_seq.run_chip`
  all pack this word — plus a re-capture, **and it must go into BOTH bitstreams
  or it confounds the core A/B.** Benefit: the EVT column becomes a real gate
  instead of two readings.
* **§R.2 — the TB mask removals' remaining scope.** Two terms were removed at U5
  (`drive_hi_a`'s HALT exclusion and `com_phase`'s refusal of a display at a
  HALT-typed cycle's T2/T3/Tw), both engine-neutral, and `check_fuzz_bank`
  proved the removal moved **no** banked seed's verdict (3,242 seeds, worse 0).
  **What REMAINS is the retention model itself**: `tb_v30_core.sv:305-333` still
  composes the bus from a `hold` register whenever no driver is active
  (`eff_lo`/`eff_hi`), because that is what the chip's PADS do — and the FPGA's
  internal `core_ad` net does not. **That asymmetry is §X.1's mechanism**, and
  the pre-registered intervention is to give the harness the retention the TB
  already models. Removing it from the TB instead would be wrong: the TB models
  the PART.
* **§R.3 — F45's guidance comment is still wrong.** `tb_v30_core.sv:645` says
  *"Run many seeds: most flips must diverge → the gate is NOT blind."* The
  correct guidance, from F45, is **step the seed by 16** (mode 4's seed IS the
  bit index, so a small-seed sweep only ever touches the first word) and *"some
  must diverge, and which ones is form- and freeze-point-dependent"*. The TB was
  frozen for scoring; unfixed. Anyone reading that comment will build a blind
  gate.
* **§R.4 — `s15_census.py` cannot classify an RTL core's residue. NEW this
  session.** `s15_census.py:169` calls `tf.run_sim(image, entry, ...)`
  unconditionally; the tool has no `--core` and takes only the seed LIST from
  `--report`. Pointed at a `--core ucore` report it runs cleanly and reports the
  **MODEL's** families for the ucore's failing seeds — the accepted-and-ignored
  shape that `ss_lint --core` had before U3 and that `check_enter_nesting` still
  has. It is not wrong today (§T.3 reads it correctly), but **there is no
  instrument in the tree that classifies the ucore's own fuzz residue by the
  seven families**, which is the gap. Closer: give it `timed_fuzz.run_tb` and a
  `--core` flag with `choices=`.
* **§R.5 — the ucore's CE-hold probe has no EU coverage** (F50 item 3).
  `tb_v30_core.sv:1204` watches `{r_ts, r_q_cnt, r_fetch_ptr}` — BIU only —
  where the archived core's probe also watches `u_eu.state` and `u_eu.div_cnt`.
  So the clean `+ce_div` cells are **BIU-state evidence**; the EU-side evidence
  is the golden row match, not `CE_HOLD_VIOL`. Reported, not patched.
* **§R.6 — the s10/s13 sweep retention gaps.  CLOSED 2026-08-04 (SM2), and
  the answer is YES.**  `sw/r6_perrep.py` banked 10 repetitions of FULL rows
  for all five cells the sweeps record as `stable_identical: false`, plus
  §26.1's reference cell.  In every cell the first T1 is row 9 and **every**
  difference between **any** two repetitions lies on rows **0-8**, in the
  MULTIPLEXED pads only (`ad_addr`, `ad_data`, `ps`, `ube_n`), with the
  DEDICATED pins (`t`, `bs_early`, `qs`, `lock_n`, `rst`) differing **nowhere**.
  `HLT.INT_w2_d0` is the SAME pad artefact as `HLT.INT_w0_d0`: **VERIFIED.**
  All five are `stable_identical: TRUE` under the CURRENT key — their banked
  `false` was computed with a pre-§26.1 key, which is exactly what the caveat
  below says is not comparable.  Independently corroborated by X3: 27 of 200 b3
  socket captures differ from their pass-3 counterparts, all on rows 0-8, zero
  at or after the first T1.  `ucore_provenance.md` §59.7.8.  **The original
  statement of the gap follows.**

* *(as originally written)* **§R.6 — the s10/s13 sweep retention gaps.** `HLT.INT_w2_d0`'s
  `stable_identical: false` is **NOT verified** as the same pad artefact as
  `HLT.INT_w0_d0` — `s13/p1b-ahsweep` banks only ONE rows stream per cell beside
  five per-rep raw shas, so the other four repetitions' keys cannot be
  recomputed. Corroboration exists offline (in that sweep `w2_d0..d3` differ only
  on rows 0-8; 50/100 p1b groups have all-distinct raw shas) but **verification
  needs per-rep rows banked, which needs the board.** Related standing caveat:
  `stable_key` changed at §26.1 and keys stored in manifests before it are
  internally valid and **not comparable across the change**.
* **§R.7 — `--core` hygiene, audited at this session's default flip.** Two tools
  (`uarch.py:32`, `uscope.py:56`) declare `--core` with **no `choices=`**, so a
  typo silently yields a nonexistent `obj_dir_<typo>`; `check_boot.py`'s parser
  is hand-rolled with the same property. `check_core.RTL` and `check_core.BIN`
  are module-level constants pinned to the FSM layout with no consumers —
  annotated as traps rather than deleted. Full audit in
  `docs/notes/standing_gates.md` §D.

---

## §Z WHAT WAS MEASURED THIS SESSION

Everything in §0's table that carries a number was either re-run here or is
cited to a ledger section that states it. This is the list of re-runs, so a
future reader can tell measurement from inheritance.

### §Z.1 Reproduced exactly — no drift

| gate | ledger | **re-run 2026-08-04** |
|---|---|---|
| **G3**, `--core ucore --opcodes all --cases 0` | 169,000 | **169,000/169,000 full, cycles 169,000, arch 169,000** |
| the four HLT sweeps, ucore | 91/97, 90/95, 40/46, 38/45 = 259/283 | **identical**, and the ucore-only failing `idx` sets match §54.3 cell for cell |
| the four HLT sweeps, model | 91/97, 95/95, 44/46, 42/45 = 272/283 | **identical** |
| `timed_fuzz --core ucore --evt-replay` | REG 1,483/1,702 · EVT 192/1,008 · COMBINED 1,675/2,710 · BOUND 5 · ABORTS 0 | **identical**, denominators 2,710/532 held |
| `timed_fuzz` (sim) | REG 1,272/1,702 · EVT 709/1,008 · COMBINED 1,981/2,710 | **identical** |
| b2 tranche, ucore | 171/188 | **DIVERGE 17 · EXACT 171 · OPEN_BUS 28** |
| `timed_wvec_gate --core ucore` | 88/88, +0.0 % | **88/88 digest, 88/88 count, 16,048 vs 16,048, +0.0 %** |
| `timed_enter_replay --core ucore` | 154/154 ×5 | **154/154 full, active, halt_display** |
| `timed_ins_replay --core ucore --raw` | 1,312 / 2,624 | **1,312/1,312 and 2,624/2,624**; 173,556/173,556 leading accesses, all same-T1 |
| `ulockstep --golden all --cases 5` | 1,735 | **1,735/1,735 ALL LOCKSTEP** |
| `check_boot` 220 / 400 | MATCH / MATCH | **MATCH / MATCH**, loop period 64 both legs |
| `check_ab_sim` | 187 rows | **187 rows MATCH** |
| `ss_lint --core ucore` / `--core fsm` | rc=0 / rc=0 | **rc=0** (218 addr, 201 flops, 0 UNMAPPED) / **rc=0** (203 addr, 181 flops, 0 UNMAPPED) |
| **G0** `check_ucore_tables` | 9,988 | **PASS, 9,988, both legs** |
| `pla3_check` / `optable --selfcheck` | 21 checks / 0 errors | **identical** |
| `timed_lawcards` | 8 GREEN / 0 RED / 3 UNRESOLVED | **identical** (C6, C7, C11) |
| `gen_ucore_qsf --check` | up to date | **up to date** |

### §Z.2 NEW numbers — first measurement of the ucore on these

| | result |
|---|---|
| **`v0.3` block I/O, 23 forms** (§F.3) | **229,999 / 229,999** cycles AND arch, 1 documented pre-existing excluded |
| **`f4a_boundary`** | **160 / 160** full (the archived core: also 160/160) |
| **`f0lock_tranche`** | **400 / 400** full (the archived core: also 400/400) |
| **the ucore-only registered-bank residue** (§T.2) | **9 seeds**, named, 8 of 9 `data`-first |
| **the model-shared split** (§T.3) | 9 ucore-only / 210 shared / 220 model-only, net +211 |
| **the family split of the shared 210** | `PF_LOST` 110 · `TAIL_EXTRA` 30 · `DATA_SEQ` 28 · `PF_GAINED` 23 · `SCHEDULE` 12 · `PF_ADDR` 4 · `PIN` 3, catch-all EMPTY |
| **the EVT split** (§T.5) | 547 ucore-only / 269 shared / 30 model-only |
| **the HLT-sweep first-divergence columns** (§T.1) | printed for the first time |
| **the `brkem_gap` acceptance rule's reach** (§F.1) | **50 REGISTERED seeds, the same 50 for both engines** |

### §Z.3 THREE LEDGER STATEMENTS CORRECTED BY MEASUREMENT

1. **§49.8's "THE RESIDUAL TEN" is NINE.** `t30-raw/15` — its third item — is a
   seed the SIM also misses, so by the governance partition it is model-shared.
   The divergence §49.8 describes is real and is the ucore's; the seed is not
   exclusively the ucore's. Net +211 unaffected. (§T.2)
2. **`s15_census` cannot do what it was used for here without a caveat.** It
   replays the MODEL unconditionally. Any past or future "the ucore's family
   census" produced by pointing it at a `--core ucore` report is the MODEL's
   families on the ucore's seeds. (§R.4)
3. **`ROADMAP.md` carries U4 pass-3 figures at a U5 close.** It says *"26 %
   ALMs, Fmax 45.56 MHz"* and *"two flashes from HEAD"*; the campaign closed on
   the U5 build at **27 % ALMs, Fmax 48.03 MHz, worst setup +9.121 ns** after
   **three** flashes (§55.1, §56). The same staleness Codex C9 caught in the
   verdict's §(a)/§(c) and that was fixed there and not here. (§R.7 / §0 R7)

### §Z.4 What was NOT re-run, and why

* **Every fabric number** (§X) — no board contact this session. The standing
  board discipline requires a single-writer check, a pre-registration and a
  commit before first contact, and the campaign is closed. §X's figures are
  §56's, cited not re-measured.
* **G6 / synthesis** — no Quartus run. 27 % ALMs / 48.03 MHz / +9.121 ns / TNS
  0.000 are §55.1's.
* **`v20suite`** (3,125,000) — not started.
* **`v0.2`** (347,000) — **attempted and BLOCKED**, `KeyError: 'opcodes'` at
  `check_core.py:709`. That is the §F.2 tooling finding, and it is a result: the
  suite has never been runnable through this checker, for either core.
* **The full `v0.3`** (3,699,998) — launched at the end of this session. If it
  is not recorded in §Z.2 it did not finish inside the session, and §F.2 stands
  as written. Its 23 block-I/O forms DID complete and are §F.3.
* **The FSM regression bisect** (2026-07-30 → HEAD) and the **§56.3a retention
  intervention** — both carried forward with their bars written, both unrun, as
  registered.
