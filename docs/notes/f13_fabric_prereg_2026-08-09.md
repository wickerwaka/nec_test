# FLASH #13 AND THE FABRIC CONFIRMATION OF THE TWO POST-FLASH-#12 LANDINGS
## PRE-REGISTRATION — committed BEFORE any board contact of this sitting

Branch `fuzz-v2-on-relanding`.  Written and committed before a single board
probe, a single flash, and every fabric number below.  Nothing in §1–§9 was
edited after a fabric figure existed; §10 onward is appended after the run.

> *"A guiding principal here needs to be simplicity.  This is 80's era
> hardware, they aren't wasting silicon on anything that isn't necessary.
> Complex or confusing behavior that we see is likely to be simple systems
> interacting in ways you do not fully understand yet."*

---

## §1  WHY THIS SITTING EXISTS

FLASH #12's receipt (`27fb750f925c539e…`) says its bitstream was built from
`ce7fa2c073`, and the `fz2c`/`fz2e` campaign manifests pin `gen_git
b629296e3a`.  Both predate:

| landing | commit | what it is |
|---|---|---|
| the **8F mod=3 ghost READ** | `d1d9f168d4` | one flop + one predicate; the unmatched tail completion is dropped |
| the **`INT.F3AA` repair** | `9c98117a03` | `flush_int_live = pin_int`; the asserted pin withdraws the direct arbitration point on EITHER tail |

Both are **Verilator-proven only**.  Under the standing rule a fabric figure
taken on FLASH #12 may not be quoted against this tree.  This sitting puts the
current tree in fabric and confirms both landings there.

## §2  A CORRECTION TO THE BRIEF, STATED BEFORE THE RUN

The brief asks that "the C-6 control legs reproduce (44/44)".  **The artifact
says 51.**  `sw/testdata/fz2/fz2_control.json` — the file committed by
`b5f2b14f05`, byte-identical at HEAD — holds **9 legs and 51 checks, 51 PASS**,
`verdict MET`:

    R1 1 · P1 5 · P2 5 · P3 5 · P4 5 · P5 5 · V1 9 · V2 9 · N1 7   =  51

`b5f2b14f05`'s own commit message says "9 legs, 44 checks, 44 PASS", and 44 is
exactly 51 − 7, i.e. the total without the `N1` negative control.  The message
is wrong about the file it committed; the file is the record.  **The bar
re-registered below is 51/51**, and the discrepancy is reported rather than
quietly resolved in either direction.

## §3  THE BITSTREAM — the retention build at HEAD (already run, before this
## document was committed; it touches no board)

Recorded recipe (`fuzzv2_retention_prereg_2026-08-08.md` §2, `sm3_s27_prereg`
§A.1), from a deleted `db`/`incremental_db`/`output_files_ucore` and a freshly
regenerated `.qsf`, `gen_ucore_qsf --check` green before and after each draw:

    quartus_map --verilog_macro=X1_AD_RETENTION=1 nec_test -c nec_test_ucore
    quartus_fit / quartus_asm / quartus_sta
    python3 sw/quartus_gate.py --parse-only --no-qsf-check

Bars as registered: ≥ 32 MHz, worst setup > 0, TNS 0.000 setup AND hold on
every domain, 0 errors, 0 latches, 0 `lpm_divide`, and the receipt must label
itself **RETENTION** (the `4bb65d2ab6` fix; a receipt still reading CONTROL is a
defect and a stop).  Control-build calibration on this tree: **39.37 MHz**
(`int_f3aa_repair_results` §6, two draws).

**THE TIMING IS STATED RATHER THAN DRESSED UP.**  Draw 1 was compiled BEFORE
this document was written, because it takes ten minutes and touches no board.
Its result is therefore NOT a prediction and is not scored as one — it is
reported in §10 with everything else.  What §6 registers about the bitstream is
the part that is still open when this document is committed: **draw 2**, and the
`.rbf` identity between the draws.

## §4  WHICH INSTRUMENTS REACH THE TWO MECHANISMS — the choice, and why

The two landings are reached by **different populations**, and only one of them
had an instrument.  This was read out of the artifacts, not assumed:

**(a) The 8F ghost read → the fz2 fabric-core leg, plus a directed 60-cell
golden probe.**
`check_core --opcodes 8F.0 --cases 0` is **500/500 both before and after the
landing** (`ghost8f_read_results` §2), so the ordinary golden comparator cannot
see the mechanism: `check_core.diff_rows` MASKS the 8F /0 mod=3 ghost read's
address and data as a documented golden-schema don't-care
(`closure_checkpoint.md`, "8F.0 mod3 ghost-read address — RESOLVED
2026-07-13").  The populations that CAN see it are
  * **fz2c+fz2e**, where the read moved 25 of 623 seeds
    (`ghost8f_read_results` §5) — and the fz2 core-leg re-capture is already
    this sitting's step 5, so it costs no extra board time; and
  * the **60 `8F.0` golden cases that are mod=3 AND carry exactly one MEMR row
    in the window** — measured offline from `tests/v30/v0.1/8F.0.json.gz`; they
    are exactly `closure_checkpoint`'s 60 residuals, and on **all 60** the
    golden (silicon) ghost address differs from `SS:SP`.  With the mask lifted
    this is a 60-cell, address-by-address probe of the mechanism.

**(b) The `INT.F3AA` repair → a directed golden-form fabric leg, and nothing
else.**  `int_f3aa_repair_results` §3 measures that the repaired arm — an
empty-tail REP withdrawal with the maskable pin still ASSERTED — occurs **35
times in the 200 `INT.F3AA` goldens and ZERO times anywhere in fz2c+fz2e**.
The corpus cannot reach it.  Neither can `x1_fabric` (HLT sweeps),
`sm3_s16_fabric` (the display walk), `u4_tranche` (random-wait seeds) or
`check_ab_hw` (boot).  So the cheapest instrument that actually reaches the
mechanism is the golden form itself, replayed through `use_core=1`.

**The new instrument is `sw/f13_formfab.py`** — `x1_fabric.py` /
`sm3_s16_fabric.py`'s shape applied to an arbitrary v0.1 form.  It does not
touch `tests/v30/`; it flips `emit_suite.EMIT_USE_CORE` for its own DUT capture
only and writes into `sw/testdata/f13-formfab/`.

### §4.1  HOW A GOLDEN CASE IS REPRODUCED, AND WHY IT IS CHECKED

`emit_suite.cmd_emit` skips to the NEXT seed when a case fails to place, so
output index and seed index diverge; `tests/v30/v0.1` predates the
`{op}.seeds.json` sidecar; and `emit_log.txt` holds **two passes with different
reroll sets** (INT.F3AA: {3,6,15,22,43,74,89,112,123,148,157,172,209,210} and
{3,6,15,22,43,74,77,90,105,112,123,148,157,166,209,210,215}) because the skip
condition is a race.  The map is therefore recovered **offline and by content**
— `gen_case`/`gen_evt_case` are pure, so every candidate seed is generated and
matched against the golden's own `initial.regs`.  Result, already computed and
retained (`sw/testdata/f13-formfab/*.seedmap.json`):

| form | mapped | ambiguous | unmatched |
|---|---|---|---|
| `INT.F3AA` | **186 / 200** | 0 | 14 |
| `8F.0` | **472 / 500** | 0 | 28 |

`capture` re-emits with the mapped seed and CHECKS that the emitted case's
`initial` and `bytes` equal the golden's.  **An index that fails that check is
`INVALID` and is NOT SCORED** — never rerolled onto a different case, which is
how a comparator ends up scoring two different programs against each other.
Every score below carries its own denominator.

### §4.2  THE OFFLINE COLUMNS — computed BEFORE the flash, on the CURRENT RTL

Both from the receipted Verilator ucore binary, this tree:

* **`INT.F3AA`, rows-only vs the golden, on the 186 mapped indices: 186/186.**
* **`8F.0` mod=3 ghost row, MASK LIFTED, on the 60 cells:** the ucore's
  (address, data) equals the golden's on **0 of 60** — the landing does **not**
  close the don't-care, and it is not registered to.  What it does is drive an
  address that is neither the golden's nor `SS:SP`; the 60 (idx, ucore addr,
  golden addr, `SS:SP`, ucore data, golden data) rows are retained in
  `sw/testdata/f13-formfab/ghost_offline.json`.

  **THIS OFFLINE TABLE IS NOT THE FABRIC PREDICTION, AND THE REASON IS WRITTEN
  IN `check_core.dontcare_cells`' OWN DOCSTRING**: the chip drives that read at
  *"a STALE internal EA/address-latch value carried in from pre-window
  execution history (the harness injection stub: load routine + 63 C0 preload +
  prefetch stream)"*, and *"a backdoor-injected core, which never executes the
  injection stub, legitimately drives the modeled `SS:SP` instead."*  The
  Verilator TB injects by backdoor; **the core in fabric executes the same
  loader image the chip does**.  So the fabric core's latch history is the
  chip's history and its ghost address need not equal the TB's.  Quoting the
  offline table as the fabric bar would be a comparator error, and §7.2 is
  written around the DELTA across the flash instead.

---

## §5  THE ORDER OF OPERATIONS

1. `fz2_w1.py preflight --board` — single writer asked of the board, div_guard,
   era/flash pin.  (It will report the flash pin as SATISFIED, because FLASH #12
   is still resident; that is the pre-flash state.)
2. **BEFORE-LEGS ON FLASH #12** — `f13_formfab capture` ×2 legs:

       python3 sw/f13_formfab.py capture --leg soc_f12  --use-core 0 \
           --form INT.F3AA
       python3 sw/f13_formfab.py capture --leg soc_f12  --use-core 0 \
           --form 8F.0 --idxs <the 60>
       ... and the same two with --leg core_f12 --use-core 1

   over `INT.F3AA` (the 186 mapped indices) and `8F.0` (the 60 mod3
   single-MEMR cells, FROZEN in `sw/testdata/f13-formfab/8F.0.mod3_idxs.json`
   before any board contact).  The socket leg is the instrument's own validity
   control and is read FIRST.
3. **FLASH #13** through `sw/safe_flash.sh` with its VERIFY leg.
4. First light `check_ab_hw all 800`; RBCHECK; the C-6 control legs.
5. **AFTER-LEGS ON FLASH #13** — the same four `f13_formfab` captures,
   `--leg soc_f13` / `--leg core_f13`.
6. The fz2 core-leg re-capture (§8).
7. `board_idle()` and a `use_core=0` chip proof.

`div_guard()` on every probe; UNPINNED is a FINDING and a stop.  Socket legs are
`use_core=False` explicit.  Full rows + sha256 retained on every capture.

---

## §6  THE PREDICTIONS — BITSTREAM AND FIRST LIGHT

| # | clause | registered |
|---|---|---|
| **B1** | retention G6 — **draw 2** (draw 1 predates this document, §3) | PASS; ≥ 32 MHz; worst setup > 0; TNS 0.000 setup AND hold; 0 errors / latches / `lpm_divide`; receipt reads **RETENTION** |
| **B2** | draw 2 reproduces draw 1 | Fmax, worst setup and ALMs **to the digit**, on a DIFFERENT receipt id (two real compiles, not one result read twice) |
| **B3** | the `.rbf`s | byte-identical across the two draws (prediction, not a bar — §74.4 governs: two draws is two draws, and this design has drawn 19.42 and 45.91 MHz) |
| **B4** | the macro reached the compiler | the retention `.rbf` ≠ the CONTROL draws' `.rbf`; `core_ad_hold` absent from `Registers Removed During Synthesis`; A&S registers ≈ +21 |
| **B5** | `c_ready_q` | **0 occurrences** in either `.sta.rpt` (R7′ stays closed under the macro) |
| **F1** | `safe_flash.sh` VERIFY | OK; `flash_log.jsonl` gains ONE entry (15 → 16) |
| **F2** | first light `check_ab_hw all 800` | **chip-vs-golden MATCH 800, core-vs-chip MATCH 800, core-vs-golden MATCH 800**.  Neither landing is reachable by the boot program: it contains no 8F mod=3 and takes no interrupt during a REP string.  Anything less is a HARD STOP. |
| **F3** | RBCHECK | **8 registers** round-trip: `EVT_ADDR[0..2]`, `EVT_CFG[0..2]`, `TVEC`, `VECCTL` |
| **F4** | the C-6 control legs | **9 legs, 51 checks, 51 PASS, verdict MET** (§2), with `holds_proved [2, 20, 300]`, `pins_proved [pin_int, pin_nmi]`, `tvecs_proved [[0,48896],[3056,8]]`, and the P1–P5 measured run lengths 2 · 300 · 2 · 300 · 20 reproduced **to the clock**.  These are SOCKET-only directed probes and the rig RTL did not move, so they must reproduce EXACTLY; any movement is a rig-integrity FINDING and a stop. |
| **F5** | `use_core=0` chip proof after everything | `check_ab_hw chip 800` MATCH 800 |
| **F6** | transport | 0 `RigMismatch`, 0 unpinned div readbacks, `board_idle()` clean |

## §7  THE PREDICTIONS — THE TWO LANDINGS, DIRECTED

### §7.1  `INT.F3AA` (the repair)

| # | clause | registered |
|---|---|---|
| **I1** | socket control, FLASH #12 | `soc_f12` rows-only vs the golden ≥ **180 / 186** valid.  This is the instrument's validity gate: below it, nothing else in §7.1 is readable and the leg is reported as NOT SCOREABLE. |
| **I2** | socket control, FLASH #13 | `soc_f13` **identical to `soc_f12`**, cell for cell.  The socket path does not contain the FPGA core; a difference is a rig or chip finding, not a result. |
| **I3** | core leg, FLASH #12 (the DEFECT present) | `core_f12` rows-only vs the golden in **[145, 168]** of 186 — materially below the socket control, the deficit being the 35-case empty-tail arm scaled onto the mapped subset (35/200 → ≈ 32.5/186). |
| **I4** | core leg, FLASH #13 (the REPAIR present) | `core_f13` = **186 / 186** valid, i.e. equal to the offline Verilator column of §4.2 AND equal to `soc_f13`. |
| **I5** | the gain | `core_f13` − `core_f12` ≥ **+25 cells**, with **0 cells lost** (no index passing on `core_f12` may fail on `core_f13`). |
| **I6** | the signature | every `core_f12` failure's first divergence is in the withdrawal window and of the ONE-CLOCK-EARLY family the repair names; a `core_f12` failure whose first divergence is somewhere else is reported, not absorbed. |

**REFUTED IF**: I4 comes in below 186 with any failure NOT attributable to a
named fabric-only class; or I5 shows any cell lost.

### §7.2  `8F.0` mod=3 (the ghost read)

The registered claim is about the **DELTA ACROSS THE FLASH**, not about
agreement with an offline table (§4.2) or with the golden.

| # | clause | registered |
|---|---|---|
| **G1** | masked score (the `check_core` scale: `diff_rows` + `dontcare_cells`) | **unchanged across the flash** on the 60 cells, on BOTH the socket and the core leg.  The documented don't-care makes this comparator blind to the mechanism, which is exactly why `check_core --opcodes 8F.0` reads 500/500 before and after.  A change here would be a finding in the OTHER direction and must be reported. |
| **G2** | ghost row, MASK LIFTED, `core_f12` | MEASURED and retained: (addr, data) per cell, plus its agreement with the golden, with `SS:SP`, and with the socket leg.  No bar — this is the baseline the delta is taken against. |
| **G3** | **the mechanism is present in fabric** | `core_f13`'s ghost (addr, data) **differs from `core_f12`'s on ≥ 50 of the 60 cells**.  The landing changes where that read's address comes from; if fabric shows no change, the landing is not in the bitstream or not reachable, and that is the refutation. |
| **G4** | it does not get worse against silicon | `core_eq_golden` on `core_f13` **≥** `core_eq_golden` on `core_f12`.  The landing is **not** registered to close the don't-care — `check_core --opcodes 8F.0` is 500/500 in Verilator on this tree — and a low absolute agreement **must not be reported as a regression**. |
| **G5** | the socket control | `soc_f12` and `soc_f13` ghost rows are **identical to each other** (the socket path holds no FPGA core); their agreement with the golden is the history-dependence ceiling and is REPORTED, not barred (`closure_checkpoint` measured 5/6 reproducing on a re-run). |

**REFUTED IF**: G3 comes in below 50/60 changed cells, or G4 falls.

## §8  THE PREDICTIONS — THE fz2 FABRIC-CORE RE-CAPTURE

**SCOPE, STATED BEFORE CAPTURING**: the **FULL population, 3,840 seeds**
(`fz2c` 960 + `fz2e` 2,880), not a sub-population.  The C-9 record measures the
whole 48-stratum capture at **664 s of board time** and the stability leg proves
both legs bit-reproducible (192 seeds × 3 reps, **192 stable / 0 unstable / 0
errors**), so a partial re-capture would save ~10 minutes and cost the ability
to say anything population-wide.  It is not disproportionate and it is taken in
full.

**ARCHIVE BY RENAME, NOTHING DELETED** — the A-6 precedent (`fz2c-A5-archive`,
`fz2e-A5-archive`).  `sw/testdata/campaigns/fz2c` → `fz2c-F12-archive` and
`fz2e` → `fz2e-F12-archive` before `fuzz_campaign new` re-pins the manifests to
FLASH #13.  The cid is preserved because the population is derived from
`cfg/<cid>/<k>` and a new cid would be a different corpus.

| # | clause | registered |
|---|---|---|
| **C1** | the socket-derived columns reproduce | over all 3,840 seeds, `bus_cycles`, `arch_ok`, `arch_words`, `wrote_term`, `wrote_term_at`, `stalled`, `mech`, `ps3_8080`, `image_sha256`, `n_ins` and the whole `term` block are **IDENTICAL** to the FLASH #12 bank.  Bar: **100 %**.  C-9's precedent is that both legs are bit-reproducible; the socket leg does not contain the FPGA core, so a socket-column move is a chip/rig FINDING and a stop. |
| **C2** | `fz2c/406000` — the headline | banked at `FUNCTIONAL / func:R@6`, `bad_rows` 3265, `first_bad` 212.  It **LEAVES the FUNCTIONAL class** (`func_mismatch` False).  This is the ghost read's one scored fabric seed and it is named in advance. |
| **C3** | the FUNCTIONAL class does not grow | currently **28 seeds** carry `verdict = FUNCTIONAL` (4 `done_mismatch`, 3 `func:INTA@*`, 21 `func:R@*`/`func:W@*`).  Registered: ≤ 28 after, and `fz2c/406000` is out of it. |
| **C4** | the 21 improving seeds | of the 21 seeds whose Verilator `ndiff` FELL in `ghost8f_read_results` §5, at least **16** show a fall in the fabric leg's own `bad_rows`.  (The two comparators differ — Verilator `ndiff` over the `timed_fuzz` window vs fabric `bad_rows` over `win` — so this is registered as a directional majority, not a cell-for-cell claim.) |
| **C5** | `fz2e/520005` | registered in advance as **NOT a refutation** if its fabric `bad_rows` rises: it is the one seed the landing worsens, by +13 rows in Verilator, and it was named as such in the landing's own results. |
| **C6** | capture integrity | 0 `RigMismatch`, 0 quarantine storms, every stratum writes the seeds it was asked for, `_capped` behaviour unchanged, and the era block on every line names FLASH #13's `.sof` sha256 and its receipt. |

**NOT RUN, BY INSTRUCTION**: `fz2_w1.py bars`.  `sw/testdata/fz2/fz2_bars.json`
is owned by a concurrent offline agent and is NOT written by this sitting.  The
bars rescore happens after both sittings finish.  Note for that rescore: the
banked corpus underneath it is REPLACED by this capture, which is the intended
consequence of putting the current tree in fabric.

## §9  HARD STOPS, as registered

`safe_flash` VERIFY failure (→ physical power cycle, no blind retry) · any
`div_guard` UNPINNED · any `RigMismatch` · first light below MATCH 800 on any of
the three legs · the C-6 control legs moving · C1 failing · any prereg
contradiction.  Halt and report.

---

---

# §9A  AMENDMENT A-F13-1 — THE GOLDEN-COMPARISON INSTRUMENT IS REFUTED ON THE
# BOARD, AND REPLACED.  Written and committed BEFORE the replacement's first leg.

**THE TIMING, STATED FIRST.**  Between §1–§9 being committed (`edb67a1cb1`) and
any scored leg, ONE board action was taken: `fz2_w1.py preflight --board`
(reported in §10) and a **5-case smoke of `f13_formfab` on the SOCKET**.  The
smoke refuted the instrument's premise.  No scored figure existed when this
amendment was written and none of §6–§8's clauses is weakened by it; §7.1 and
§7.2 are RE-EXPRESSED on the replacement comparator and the old wording is left
above, struck by this section rather than edited away.

## §9A.1  WHAT WAS MEASURED

`f13_formfab capture --leg smoke --use-core 0 --form INT.F3AA --idxs 0,1,2,4,6,8`
returned **4 pairs captured, 0 VALID**, and the validity check said why.  For
`INT.F3AA` idx 0, re-emitted today against the golden:

| | re-emitted | golden |
|---|---|---|
| `initial.regs.ip` | 15116 | **13105** |
| image fill byte | **0xCC** | 0x90 |
| instruction anchor | 0x88CCC | **0x884F1** |

`testimage.compose` is **not the composer the v0.1 goldens were emitted with**:
fuzz-v2 T1/T2 moved the body anchor and made the image `0xCC`-filled outside
four carve-outs (`testimage.py` §57-78, `CODE_FILL = 0xCC`).  **The current
emitter cannot reproduce a v0.1 golden's image**, which is `sw/retired_v1.py`'s
stated reason for retiring a dozen tools, and it applies to this route too.
The seed-map work of §4.1 is sound and is retained as record; it is simply not
usable to compare against a golden any more.

## §9A.2  THE REPLACEMENT — AND IT IS THE BETTER COMPARATOR, NOT A FALLBACK

The instrument becomes a **same-image A/B**: generate the form's cases from a
frozen seed namespace (`f13/<form>/<i>`), run each image **twice** — `use_core=0`
(the socketed chip, silicon truth) then `use_core=1` (the ucore in fabric) — and
diff the two row streams.  That is `fuzz_campaign.capture_board`'s A/B applied
to a directed form, and no golden is involved.

**For the ghost read this is strictly stronger than the golden route.**
`check_core.dontcare_cells` masks the 8F /0 mod=3 ghost address *because* the
chip drives it from a stale EA latch carried in from the loader stub and *"a
backdoor-injected core, which never executes the injection stub, legitimately
drives the modeled `SS:SP` instead."*  That don't-care is a property of the
Verilator TB's backdoor injection.  **In fabric both legs execute the same
loader from the same image**, so the ghost address is directly comparable and
the mask does not apply.  The A/B can therefore ask the question the golden
comparator was built to refuse.

**FROZEN BEFORE ANY BOARD CONTACT** (`sw/testdata/f13-formfab/*.pop.json`,
committed with this amendment):

* `INT.F3AA` — **200 seeds**, `f13/INT.F3AA/0..199`.
* `8F.0` — **130 seeds**, the first 130 of `f13/8F.0/*` whose ModRM is **mod=3**,
  decided OFFLINE from the pure generator so the board never runs a case that is
  going to be discarded.

## §9A.3  §7.1 RE-EXPRESSED — `INT.F3AA`

| # | clause | registered |
|---|---|---|
| **I1′** | **reachability, and it is the FLASH #12 leg's job** | on `f12`, core-vs-chip must show **≥ 10 divergent cases of 200**.  The repaired arm hit 35 of the 200 GOLDENS; these are fresh cases under a changed composer, so the rate may differ.  **If `f12` is 200/200 the mechanism is NOT REACHED by this population and the leg is reported NOT SCOREABLE — not as a confirmation.** |
| **I2′** | the repair closes it | on `f13`, core-vs-chip is **200/200 identical**.  Any residual divergence must be NAMED and attributed, not absorbed. |
| **I3′** | nothing is lost | **0** cases identical on `f12` and divergent on `f13`. |
| **I4′** | the signature | every `f12` divergence's first bad row lies in the interrupt-withdrawal window.  A divergence elsewhere is reported separately and does not count toward I1′. |

## §9A.4  §7.2 RE-EXPRESSED — `8F.0` mod=3

With no mask, the pre-landing core cannot agree with the chip on the ghost row
by construction: the chip drives a stale-EA value, the core drove the modeled
`SS:SP`.  So the row score itself is the instrument.

| # | clause | registered |
|---|---|---|
| **G1′** | the mechanism is ABSENT on FLASH #12 | `f12` core-vs-chip rows identical on **≤ 20 of 130**. |
| **G2′** | **the landing's claim** | `f13` core-vs-chip rows identical on **≥ 90 of 130**.  This is the strong form: one term is either the law or it is not.  A rise that falls short of 90 is evidence the mechanism is present and evidence the law is incomplete, and will be reported as exactly that — not as a pass. |
| **G3′** | the ghost row itself | on the single-MEMR subset, `core == chip` on (addr, data) rises from `f12` to `f13`, and the core's address **stops being `SS:SP`**: `core_eq_sssp` falls to **≤ 10 %** of that subset on `f13`. |
| **G4′** | nothing is lost | **0** cases identical on `f12` and divergent on `f13`. |

## §9A.5  WHAT THIS AMENDMENT DOES NOT TOUCH

§6 (bitstream, first light, RBCHECK, C-6 at **51/51**, chip proof) and §8 (the
fz2 re-capture, C1–C6) stand exactly as committed at `edb67a1cb1`.  The §4.2
offline columns are retained as record and **no longer bar anything**; the
reason is §9A.2 and it was found by measurement, not by preference.
