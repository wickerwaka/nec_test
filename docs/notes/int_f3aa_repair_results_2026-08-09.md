# `INT.F3AA` — THE REP-WITHDRAWAL FLUSH REPAIR, RESULTS reported AS REGISTERED

Against `docs/notes/int_f3aa_repair_prereg_2026-08-09.md` (`eb11ffe149`),
committed before a single number below was measured.  Offline: no board, no
flash.  **Eleven registered clauses, ELEVEN MET; none of the five refutation
conditions is met.**

---

## §1  HEADLINE

`check_core --core ucore --opcodes INT.F3AA --cases 0` goes **165/200 →
200/200** and `--opcodes all --cases 0` goes **168,965 → 169,000/169,000**.

The mechanism is **NOT reverted and NOT weakened**.  Instrumented after the
repair (a temporary `$fwrite` on the flush rails, since reverted, in a
throw-away worktree so the gated tree was never touched), the REP-withdrawal
direct-T1 arm **still fires 17 times in 17 places** over the whole 623-seed
`fz2c`+`fz2e` population — the identical count, arm for arm, to the baseline:

| | baseline `d1d9f168d4` | after the repair |
|---|---|---|
| empty tail, `flush_fast = 1` | **17** | **17** |
| empty tail, `flush_pre = 1` | 17 | 17 |
| staged tail, `flush_stage = 1` | 8 | 8 |

and the `timed_fuzz` report is **byte-identical** to the baseline's — same
md5, so `ndiff`, `first_bad` and `n` are unmoved seed for seed.  **Zero seeds
gained, zero lost, zero row streams moved.**

## §2  WHAT THE DEFECT WAS

The 35 failures were one signature: the whole withdrawal sequence exactly ONE
CLOCK EARLY (EMPTY on row *n* instead of *n+1*, the redirect's CODE
announcement on the flush row instead of the row after, T1 one clock early).
Instrumented, the 200 cases split **exactly** on `pend_active` at upc `7.40.7`
— the 165 that passed are the STAGED arm, the 35 that failed are the EMPTY-TAIL
arm, where `flush_pre` moved EMPTY one row early and `flush_fast` collapsed the
announcement onto the flush row.  The microcode timing is identical in both
(locs 0,0,1,2,3,5,5,6,7,8 — one clock each); `pend_active` was the only
difference.

**The empty-tail arm took the direct point unconditionally.**  It should not
have: the maskable pin is ASSERTED at the withdrawal in all 200 `INT.F3AA`
cases, and silicon gives every one of them an ordinary idle eval.

## §3  THE LAW, AND THE TWO POPULATIONS THAT FIX IT

> **While the maskable INT pin is still asserted at the withdrawal, the redirect
> takes an ordinary idle eval** — EMPTY stands on the FLUSH row and the
> announcement gets its own clock.  This is true on EITHER tail.

It is not a new predicate: `flush_int_live` is what the STAGED arm has read
since the mechanism landed (`flush_staged_eval`).  The repair makes ONE rail act
the same way on both arms.  Two disjoint populations, each unanimous:

| population | empty-tail withdrawals | pin | silicon says |
|---|---|---|---|
| v0.1 `INT.F3AA` (golden = silicon) | **35 of 35** | ASSERTED | ordinary eval |
| `fz2c`+`fz2e`, 623 seeds | **17 of 17** | RELEASED | direct T1 |

There is no empty-tail withdrawal with an asserted pin anywhere in `fz2`, and
none with a released pin anywhere in `INT.F3AA`.  The predicate separates the
two populations completely, which is why the repair can close 35 golden cases
and move **zero** fuzz rows.

Confirmed after the fact by the same instrument: on `INT.F3AA` the post-repair
counts are **35 empty-tail withdrawals at `intlive=1` with `fast=0`** (they now
take the ordinary eval) plus 21 staged — 56 REP withdrawals in the 200 recorded
windows; the remaining 144 cases take their interrupt after the string has
already retired and never reach `7.40`.

## §4  THE CHANGE — THREE LINES OF LOGIC, NO NEW STATE

`hdl/rtl/ucore/v30u_biu.sv`

```
wire flush_direct = !flush_stage && !flush_nmi_young && !flush_int_live;
wire flush_fast   = flush_rep && flush_idle && flush_direct;
```

`flush_direct` also replaces the two open-coded copies of its first two terms
inside `qs_e_now` (the `flush_pre` early-EMPTY enable, twice, and the flush-row
suppression's empty disjunct).  **Three sites that had to agree now read one
name.**

`hdl/rtl/ucore/v30u_eu.sv` — `assign flush_int_live = pin_int;` (was
`q_flush && pin_int`).  The gate was redundant at both original readers
(`flush_staged_eval` carries `flush_stage`; `flush_fast` carries `flush_rep`;
both contain `q_flush`) and wrong for the third: the empty arm reads the rail on
the withdrawal's PRECEDING row, where the flush strobe is still low.

**No flop.  No save-state address.  No port added or removed.  No opcode named.
No case split.**  Net logic delta: two `wire` lines and one `assign`.

**FALSIFIER, in the RTL beside the code:** an empty-tail withdrawal whose
maskable pin CHANGES between `7.40.6` and `7.40.7` — the two reads then
disagree and EMPTY is shown twice or not at all.  No instance exists in either
population above.

## §5  THE GATE TABLE — every figure measured this sitting

| # | gate | baseline `d1d9f168d4` | registered | **measured** | verdict |
|---|---|---|---|---|---|
| 1 | `gen_ucore_qsf --check` | PASS | PASS | **PASS** — *"nec_test_ucore.qsf is up to date"* | MET |
| 2 | `r7_lint` | 20 nets / 1 carrier / 3 tainted / 51 `stop` | identical, no new exception | **PASS — 20 / 1 / 3 / 51, no new exception** | MET |
| 3 | `check_core --build --core ucore` | — | builds | **PASS**, receipt `0bb9b821dee96e1d…` | MET |
| 4 | `ss_lint --core ucore` | PASS `0x8C`/101/122/224/`0x8CE0` | UNCHANGED | **PASS 101×2 + 122×2 + tag = 224; `v30u_ss_pkg.sv` UNTOUCHED** | MET |
| 4b | `ss_flopcensus` | 212 | 212 | **PASS 212** (BIU 83, EU 129 → 127 mapped + 2 whitelisted, 0 UNMAPPED) | MET |
| 5 | `test_artifact` | 45/45 | 45/45 | **45/45** | MET |
| 6 | `check_core INT.F3AA --cases 0` | 165/200 | **200/200** | **200/200 full (cycles 200, arch 200)** | **MET** |
| 7 | `check_core 8F.0 --cases 0` | 500/500 | 500/500 | **500/500** | MET |
| 8 | `check_core --opcodes all --cases 0` | 168,965/169,000 | **169,000** | **169,000/169,000**, 348 forms, **zero non-perfect** | **MET** |
| 8b | `ulockstep --golden all --cases 50` | 17,340/17,350 | 17,345, `8F.0` stays down | **17,345/17,350**, the ONLY non-perfect form `8F.0` 45/50 (`idx 5@5, 6@8, 16@8 : ad_data,ps,ad_addr`) | MET |
| 9 | four HLT sweeps | 97·93·45·44 = 279/283 | 279/283 | **97 · 93 · 45 · 44 = 279/283** | MET |
| 10 | `timed_fuzz --bank fz2c,fz2e --evt-replay --core ucore` | DIVERGE 2 / EXACT 12 / OPEN_BUS 609, REG 9/11, EVT 3/3, COMB 12/14, SCORED 14 | BYTE-IDENTICAL, 0 moved | **BYTE-IDENTICAL** — md5 `5b50b2ccfd2ce8bf69a701728e490271` before and after; **0 gained, 0 lost, 0 seeds moved** | **MET** |
| 11 | G6, two draws | 39.57 / 39.57 MHz | PASS, ≥ 32, no `c_ready_q` | **§6** | **MET** |

`8F.0`'s `ulockstep` 45/50 is the ghost-READ landing's own registered fall
(`ghost8f_read_results_2026-08-09.md` §6 — `sim/` has no ghost family) and is
NOT this repair's to fix; it is quoted here only to show it did not move.

### §5.1  THE FIVE REFUTATION CONDITIONS — NONE MET

| | condition | measured |
|---|---|---|
| **R1** | `INT.F3AA` < 200/200 | 200/200 |
| **R2** | ANY seed moves in gate 10 | byte-identical report |
| **R3** | `--opcodes all` < 169,000 | 169,000/169,000 |
| **R4** | any SSA / `SS_VERSION` / `SS_COUNT` / `SS_TAG` / census figure moves | none; `v30u_ss_pkg.sv` untouched |
| **R5** | G6 < 32 MHz or `c_ready_q` present | 39.37 / 39.37 MHz; `c_ready_q` occurs **0 times** in both `.sta.rpt` |

## §6  G6 — PASS ON BOTH DRAWS

Clean `db` each time (the gate deletes it), CONTROL/DEFAULT configuration
DERIVED from the flow/map reports, inputs **88 files `7027399279a804fe…`**.

| draw | verdict | Fmax | worst setup | setup TNS | ALMs | latches | `lpm_divide` | receipt |
|---|---|---|---|---|---|---|---|---|
| 1 | **PASS** | **39.37 MHz** | **+5.853 ns** | **0.000** (E5 `[]`) | 12,340 / 41,910 (29 %) | 0 | 0 | `ab9c5de161457bc9…` |
| 2 | **PASS** | **39.37 MHz** | **+5.853 ns** | **0.000** (E5 `[]`) | 12,340 / 41,910 (29 %) | 0 | 0 | `4f7483a65515307d…` |

**Identical to the digit on both draws** (the reports differ — draw 1
`78278fd3ec49a5cb…`, draw 2 `2309656ec83e65a9…` — so these are two real
compiles, not one result read twice).  E2 zero errors on both: `stage_errors` 0,
`error_lines` 0, map/fit/asm all Successful.  **`c_ready_q` occurs ZERO times in
either `.sta.rpt`** — the R7′ signature is not merely out of the failing set,
there is no failing set.

Against the baseline's 39.57 / 39.57 MHz on this same CONTROL configuration the
repair costs **0.20 MHz** and **+15 ALMs**, which is one AND term on a rail the
same cone already carried.  Both draws are
**7.4 MHz above the 32 MHz bar**.  Per `ucore_provenance.md` §74.4a the
COMBINATIONAL counts are not run-to-run reproducible, so the ALM figure is
reported, not defended.

## §7  METHOD NOTES, recorded because they bear on how the result was reached

1. **The diagnosis was instrumented, not inferred.**  A temporary `$display` /
   `$fwrite` on `flush_pre / flush_rep / flush_stage / flush_pend / flush_nmi /
   flush_nmi_young / flush_int_live / flush_idle / flush_fast`, plus an EU-side
   dump of `upc_page.opc.loc`, `st`, `pend_active` and `pin_int`, was added,
   built, read, and **reverted** (`git checkout`) before any gate ran.  The
   post-repair fire count was taken in a **throw-away `git worktree`** so the
   gated tree was never modified while G6 was in flight.
2. **The `mc1`/`mc2` socket rows the mechanism's own comment cites are NOT
   replayable on this branch** — SUP-1 (`6b044475c7`) retired the v1 corpus by
   status and every one of those seeds categorises `GEN_DRIFT` since fuzz-v2's
   plan D9.  Their `line.evt` records are still readable and were read: three of
   the four cited "empty/direct" instances (`mc1/874`, `mc2/700`, `mc2/3758`)
   are `pin 0, hold 300`, i.e. a HELD maskable pin.  **That is the one piece of
   evidence pointing the other way**, and it cannot be re-measured here: the
   captures cannot be replayed, so what the pin was doing at those particular
   withdrawal clocks is not recoverable offline.  Booked, not resolved.  The
   evidence that IS measurable on this branch — 35 golden cases and 17 live
   fuzz instances — is unanimous and points one way.
3. **The 623-seed comparison is byte-level, not summary-level.**  Comparing the
   headline counters would have hidden a compensating pair of moves; the md5 of
   the full per-seed report is what is quoted.

## §8  WHAT IS NOT CLAIMED

* No board, no flash, no fabric figure.  The bitstream from these draws is a
  gate artifact only; the board still carries FLASH #10 and **no fabric number
  may be quoted against this tree.**
* The `mc1`/`mc2` tension in §7.2 is BOOKED and unresolved.  If a future
  campaign re-derives the v1 corpus on a pre-fuzz-v2 generator and finds an
  empty-tail withdrawal that goes DIRECT with the pin held, this law is
  falsified and the RTL comment's falsifier says where to look.
