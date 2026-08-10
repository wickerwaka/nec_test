# SURVEY FIX #2 — family `B1`, the HALT pseudo-cycle's published address

**PRE-REGISTRATION, and it opens by correcting the brief against the artifact.**
Branch `fuzz-v2-on-relanding`. Offline: no board, no flash. Territory: the
HALT / `ad_oe` / display-address path only. A concurrent sitting owns the QS
announcement path (`A1`) and nothing here touches it.

> **SIMPLICITY: this is 80's era hardware — nothing on the die is wasted.
> Complex or confusing observed behavior is likely simple systems interacting
> in ways not yet understood. A large fitted table, a many-cased rule, or a
> per-opcode special case is a signal of misunderstanding, not a deliverable.**

---

## 0. THE BRIEF'S IDENTIFICATION IS REFUTED. THIS IS NOT F55.

The task brief says F55 was *"booked at FLASH #9 … called 'the obvious next RTL
landing' two campaigns ago and never landed"*, and asks for *"the minimal change
to `halt_hold`/`ad_oe_addr` … that makes the core STOP driving where silicon
retains."*

**F55 LANDED ON 2026-08-05, four days before this sitting**, as commit
`39ac08ccd4` (*"SM3 sitting 20 F55 LANDED: a HALT pseudo-cycle's announced
address stands by RETENTION, not by DRIVE"*), with ten registered bars all MET.
`halt_hold` no longer exists; `v30u_biu.sv` reads

    wire halt_addr = r_run && r_cur_halt && (r_ts == TS_T1);

and `ad_oe_ps` already carries `!r_cur_halt`, so **all three enables are already
LOW for the body of the pseudo-cycle and the pads already retain.** It has been
in fabric since FLASH #10 (`ucore_provenance.md` §88.A), where it is one of the
three landings CONFIRMED. The `CLAUDE.md` line the brief quotes is the FLASH #9
paragraph, which is a sitting-19 snapshot and is superseded by sitting 20 in the
same file. **The artifact wins; the brief's premise does not hold.**

Two further brief clauses are stale for the same reason and are corrected here:

* *"invisible on `tb_v30_core`, whose comparator floats those clocks"* —
  `tb_v30_core.sv`'s composer has keyed on the core's own `AD_OE` port since
  commit `0254d9f23e` (*"F55 part 2 — THE COMPOSER ASKS THE CORE"*), landed at
  the same sitting. This class **is** visible on that TB, and is scored on it
  below.
* *"expect no SSA movement"* — that followed from F55's shape (an enable term).
  The mechanism actually found needs one register, so the save-state map DOES
  move. It is registered as such in §4.

Under the brief's own instruction (*"if the mechanism turns out NOT to be F55,
that is a finding — report it"*), §1 states what the mechanism is instead. It is
a **different, adjacent mechanism**: F55 is about who holds the pads for the
**body** of the pseudo-cycle; `B1` is about the **value published in the
pseudo-cycle's own address phase**, which both silicon and the core do drive.

---

## 1. THE MECHANISM, MEASURED

`B1` is 24 seeds, 25 HALT displays (`fz2c/410048` has two). On every one the
first differing cycle is a `HALT` status on BOTH legs at DIFFERENT addresses.

**What the core publishes.** `v30u_biu.sv` step (e), the HALT display:

    cmt_addr = {data_ps(2'd2), last_fetch_addr};
    cmt_data = last_fetch_addr;

— the last CODE-fetch address, from the prefetcher, with a synthesised segment
nibble. Confirmed on the rows: the core's HALT low-16 is a previous `CODE` T1
address on **24 of 24**.

**What silicon publishes.** The value the CPU's own AD output latch already
holds — on both lanes, and nothing of the HALT's own:

* **AD15-0** = the last value the *core itself* drove there. After a WRITE that
  is the write DATA (the CPU drove it through T2-T4); after a READ it is the T1
  ADDRESS (the memory, not the CPU, drove the data phase); after an INTA it is
  unchanged, because an INTA drives no AD15-0 at all.
* **A19-16** = the last value the core drove there, i.e. the previous cycle's
  segment status `data_ps(seg)`.

**The split is exact and has no residue.** Of the 24 seeds, the 15 whose last
bus cycle was a WRITE (`MEMW` 11, `IOW` 4) show the write data; the 9 whose last
bus cycle was a READ (`MEMR` 9) show that read's T1 address. **15 + 9 = 24, and
the read/write predicate accounts for the split with zero exceptions.**

### 1.1 THE LAW, VALIDATED ON A POPULATION 50× THE ONE THAT SUGGESTED IT

Stated as one predicate — *the HALT pseudo-cycle publishes the AD output latch
as it stands* — and scored **chip-leg only**, on every HALT pseudo-cycle in all
725 retained fz2 captures, by walking the protocol to track what the CPU last
drove on each lane:

    HALT pseudo-cycles scored          1,189
    display row low-16 predicted       1,189 / 1,189
    T1 row, all 20 bits, predicted     1,189 / 1,189
    exceptions                                 0

This is derived from silicon alone; no core leg enters it.

### 1.2 WHY IT SURVIVED THE WHOLE UCORE CAMPAIGN

The two rules **agree exactly when the last bus cycle before the HALT was a
CODE fetch**, because then the last value driven on AD15-0 *is* the last fetch
address. Over the same 1,189 sites:

    last bus cycle before the HALT:  CODE 1,164 · MEMW 12 · MEMR 9 · IOW 4

**1,164 of 1,189 are degenerate.** The four HLT sweeps and the S16 display walk
run the one-byte program `[0xF4]`, so *every* golden that has ever gated this
value sits in the degenerate case and cannot distinguish the two rules. The 25
non-degenerate sites are exactly the 25 HALT displays of the 24 `B1` seeds,
**with nothing left over in either direction.**

---

## 2. THE CHANGE

One register pair, in the idiom `last_ube` already establishes in this file
(*"`last_ube` is pad retention, not a decision: it tracks the pin"*), keyed on
the output enables that already exist:

    reg [3:0]  last_ad_hi;   // loaded when ad_oe_addr || ad_oe_ps
    reg [15:0] last_ad_lo;   // loaded when ad_oe_addr || ad_oe_data

and the HALT display publishes it:

    cmt_addr = {last_ad_hi, last_ad_lo};
    cmt_data = last_ad_lo;

**No opcode is named. No table. No case split.** The read/write asymmetry of §1
is not encoded anywhere — it falls out of which enable is asserted when, which
the core already computes for the pads. `ad_o` does not enter the next-state
cone: the latch reads it on a register's own `D` pin, and the display decision
reads the REGISTERED value.

**Registered falsifier on the rendering** (as distinct from the law): because
the display decision reads the registered value, a HALT display whose only
preceding driven clock is a single-clock WITHDRAWN announcement would publish
one announcement too far back. No such site exists among the 1,189. If one is
ever captured, the *read* moves, not the law.

---

## 3. INSTRUMENT — AND ITS OWN LIMIT, STATED BEFORE ITS NUMBERS

The fz2 corpus was captured on the BOARD (`real` = socketed chip, `sim` =
fabric core). An offline sitting cannot re-take the fabric leg. `sw/b1_rescore.py`
re-runs the CORE leg in Verilator (`tb_v30_core --core ucore`) on the image
regenerated from each seed's stratum overrides — **asserted byte-exact against
the banked `image_sha256`** — and scores it against the BANKED CHIP ROWS with
the campaign's own `fuzz_classify.diff_rows` at each seed's own window. The chip
leg is silicon and never moves.

**IT IS A DIFFERENT INSTRUMENT FROM THE BANKED ONE, measured:** on the 24 `B1`
seeds it reproduces the banked `first_bad` and the banked first-divergence
signature on **21 of 24**, but its `bad_rows` are far larger (278-846 against 4),
because `tb_v30_core` and the fabric disagree downstream on classes unrelated to
this fix. **So `bad_rows == 0` is NOT a usable closure criterion and is not
used.** Two things are scored instead:

* **(A) the mechanism, directly** — every HALT pseudo-cycle *still in lockstep*
  (`i <= first_bad`; past the fork the two legs are not running the same
  program and comparing their HALTs measures nothing);
* **(B) no collateral damage** — the full differing-row SET per seed, before and
  after. Rows may LEAVE; a row that ENTERS is a regression, printed with its
  coordinate.

**DENOMINATOR, STATED HONESTLY: 725 of 3,837 seeds** — the retained-capture
population, which contains all 198 ledger failures and all 3 discards. The other
3,112 have no banked rows and cannot be rescored offline at all. **The banked
headline `SEED MATCH 3,639/3,837` is NOT restated, re-derived or moved by this
sitting; it can only move on a board re-capture.**

---

## 4. REGISTERED BARS

Measured at identification time, stated here as found (§0's honesty clause —
these are reported, not predicted):

| # | bar | registered value |
|---|---|---|
| M1 | chip-leg law, all retained captures | 1,189 / 1,189, 0 exceptions |
| M2 | corpus rescore, HALT sites in lockstep | MISS **21 → 0** |
| M3 | corpus rescore, rows ENTERING the differing set | **0** over 725 seeds |
| M4 | corpus rescore, rows LEAVING it | 96 |
| M5 | `ss_lint` | PASS, `SS_VERSION` **0x8D** / `SS_COUNT` **226** / `SS_TAG` **0x8DE2**, 103 BIU symbols, **214** flops, 0 UNMAPPED |
| M6 | `r7_lint --core ucore` | PASS, 0 undeclared carriers |

Predicted BEFORE measurement, this document committed first:

| # | bar | prediction | why |
|---|---|---|---|
| P1 | `check_core.py --core ucore --opcodes all --cases 0` | **169,000 / 169,000, UNCHANGED** | every golden HLT form follows a CODE fetch (§1.2), so the published value is bit-identical |
| P2 | the four HLT sweeps on `tb_v30_core --core ucore` | **97/97, 93/95, 45/46, 44/45 = 279/283, UNCHANGED**, same four survivors (`w1.INT/8,9` · `w2.INT/12` · `w3.INT/15`) | same reason; the sweeps are the degenerate case |
| P3 | `check_boot.py --core ucore` | 220 and 400 MATCH | boot is fetch-only before any HALT |
| P4 | `sw/test_artifact.py` | 45 / 45 | |
| P5 | `sw/gen_ucore_qsf.py --check` | PASS | no file added to the RTL list |
| P6 | **G6**, `sw/quartus_gate.py`, TWO draws | PASS both: 0 errors, Fmax ≥ 32 MHz, worst setup > 0, setup AND hold TNS 0.000 | +2 leaf registers off `ad_o`, which feeds no logic; the band this tree sits in is ≈ 40-48 MHz, and ONE GREEN BUILD IS NOT CLOSURE, hence two draws |
| P7 | `ulockstep.py --golden all --cases 50` | **NOT A BLOCKING GATE** (user ruling, this sitting: the C++ model is defunct). Run for the record; the model does not carry F58, so a HALT-address cell may move AWAY from it. A move away from the model toward silicon is reported, not fixed. | |

**FAILURE CLAUSE.** Any bar that misses is reported AS REGISTERED, with its
measured value, and is not restated. P1 or P2 missing means the degeneracy
argument of §1.2 is wrong and the landing does not stand.

---

## 5. WHAT THIS DOES NOT CLAIM

* **F55 is not disturbed** and is not re-landed. Its enables are untouched;
  this changes only the value the address phase publishes.
* **No fabric figure is quoted.** No board was contacted and nothing was
  flashed. The fabric prediction — that this closes the same sites there — is
  registered for a later flashed sitting and is NOT evidence now.
* **The banked corpus headline is not moved** (§3).
* `fz2c/407064` is a `B1` first-divergence but re-diverges downstream on a
  missed vector-1 trap (`§38.9`'s `C1` population, of which it is the one `B1`
  member). **It is predicted NOT to become a passing seed**; only its HALT cell
  closes.
* Nothing in `sim/` is touched.
