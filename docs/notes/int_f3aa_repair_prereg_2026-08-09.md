# `INT.F3AA` — THE REP-WITHDRAWAL FLUSH REPAIR, PRE-REGISTERED

Branch `fuzz-v2-on-relanding`, base `d1d9f168d4`.  Offline: no board, no flash.
Written and committed **BEFORE** any of the numbers below were measured.  The
RTL is written; nothing on this page has been run.

---

## §1  THE DIAGNOSIS, AND IT IS NOT A GUESS

`check_core --core ucore --opcodes INT.F3AA --cases 0` reads **165/200**
(cycles; arch 200/200).  The 35 failures are one signature — the whole
withdrawal sequence is exactly **ONE CLOCK EARLY**:

| | golden (silicon) | ucore at `d1d9f168d4` |
|---|---|---|
| row *n* | `PASV Ti  -` | `PASV Ti  E`   ← `flush_pre` |
| row *n+1* | `PASV Ti  E` | `CODE Ti  -`   ← `flush_fast` |
| row *n+2* | `CODE Ti  -` | `CODE T1` (ALE) |
| row *n+3* | `CODE T1` (ALE) | … |

Instrumented (a temporary `$display` on the flush rails, since reverted) the
split across the 200 cases is **exact and total**:

* **165 PASS** — `pend_active = 1` at upc `7.40.7`, so `flush_stage = 1`,
  `flush_fast = 0`, `flush_pre = 0` (it carries `!pend_active`).  EMPTY stands
  on the flush row.  This is the STAGED arm and it already matches silicon.
* **35 FAIL** — `pend_active = 0`, so `flush_stage = 0` and the EMPTY-TAIL arm
  fires: `flush_pre` moves EMPTY one row early and `flush_fast` puts the
  redirect's CODE announcement on the flush row itself.

The microcode timing is identical in both (`7.40` locs 0,0,1,2,3,5,5,6,7,8 —
one clock each).  The ONLY difference is `pend_active`.

**And the maskable pin is ASSERTED at the withdrawal in all 200.**

## §2  THE OTHER POPULATION, AND WHY IT IS THE ANSWER

The same instrument over the whole measurable fuzz population on this branch —
`timed_fuzz --bank fz2c,fz2e --evt-replay --core ucore`, **623 seeds** — counts
every `7.40` withdrawal:

| arm | instances | `flush_int_live` |
|---|---|---|
| empty tail, `flush_fast = 1` | **17** | **0 in 17 of 17** |
| empty tail, `flush_pre = 1` | 17 | (rail gated on `q_flush`, uninformative) |
| staged tail, `flush_stage = 1` | 8 | 0 in 8 of 8 |

There is **no empty-tail withdrawal with an asserted pin anywhere in fz2**, and
**no empty-tail withdrawal with a released pin anywhere in `INT.F3AA`.**  The
two populations are disjoint, each is unanimous, and one predicate separates
them — the one the STAGED arm has read since the mechanism landed:

> **while the maskable INT pin is still asserted at the withdrawal, the redirect
> takes an ordinary idle eval.**  EMPTY stands on the FLUSH row and the
> announcement gets its own clock.

## §3  THE CHANGE — ONE PREDICATE, NO NEW STATE, NO OPCODE NAMED

`hdl/rtl/ucore/v30u_biu.sv`

```
wire flush_direct = !flush_stage && !flush_nmi_young && !flush_int_live;
wire flush_fast   = flush_rep && flush_idle && flush_direct;
```

and the same `flush_direct` replaces the two open-coded copies of its first two
terms inside `qs_e_now` (the `flush_pre` early-EMPTY enable, twice, and the
flush-row suppression's empty disjunct).  **Three sites collapse to one name.**

`hdl/rtl/ucore/v30u_eu.sv` — `flush_int_live` is published RAW:

```
assign flush_int_live = pin_int;        // was: q_flush && pin_int
```

The gate was redundant at both original readers (`flush_staged_eval` carries
`flush_stage`, `flush_fast` carries `flush_rep`; both contain `q_flush`) and
wrong for the third: the empty arm must read the pin on the withdrawal's
PRECEDING row, where `q_flush` is still low.

**No flop.  No save-state address.  No opcode named.  Zero lines of per-case
logic.**

**FALSIFIER, written beside the code:** an empty-tail withdrawal whose maskable
pin CHANGES between `7.40.6` and `7.40.7` — the two reads then disagree and
EMPTY is shown twice or not at all.  No instance exists in either population.

## §4  THE REGISTERED NUMBERS

| # | gate | baseline `d1d9f168d4` | PREDICTED |
|---|---|---|---|
| 1 | `gen_ucore_qsf --check` | PASS | PASS |
| 2 | `r7_lint` | PASS 20 nets / 1 carrier / 3 tainted / 51 `stop` | **identical, no new exception** |
| 3 | `check_core --build --core ucore` | — | builds |
| 4 | `ss_lint --core ucore` | PASS `0x8C`/101/122/224/`0x8CE0` | **UNCHANGED — no SSA moves** |
| 4b | `ss_flopcensus` | 212 | **212** |
| 5 | `test_artifact` | 45/45 | 45/45 |
| 6 | `check_core INT.F3AA --cases 0` | 165/200 | **200/200** |
| 7 | `check_core 8F.0 --cases 0` | 500/500 | **500/500** |
| 8 | `check_core --opcodes all --cases 0` | 168,965/169,000 | **169,000/169,000** |
| 8b | `ulockstep --golden all --cases 50` | 17,340/17,350 | **17,345/17,350** — `INT.F3AA` closes, `8F.0` STAYS DOWN (`sim/` has no ghost family; 45/50 is that landing's registered fall and is not this repair's to fix) |
| 9 | four HLT sweeps | 97·93·45·44 = **279/283** | **279/283** — no HLT golden contains a REP withdrawal |
| 10 | `timed_fuzz --bank fz2c,fz2e --evt-replay --core ucore` | DIVERGE 2 / EXACT 12 / OPEN_BUS 609, REG 9/11, EVT 3/3, COMB 12/14, SCORED 14 | **BYTE-IDENTICAL report — ZERO seeds move, gained 0, lost 0.**  All 17 empty-tail instances are at pin low, which is the side of the predicate that is unchanged |
| 11 | G6, two draws | 39.57 MHz / +5.978 / TNS 0.000 | **PASS, Fmax ≥ 32, no `c_ready_q`** |

### §4.1  REFUTATION CONDITIONS — what would say I am wrong

* **R1** `INT.F3AA` below 200/200 ⇒ the pin is not the discriminator, or is not
  the whole discriminator.  Report the residue and STOP.
* **R2** ANY seed moves in gate 10 ⇒ the change is not confined to the asserted-
  pin side and the "17 of 17 at pin low" count is wrong.  Report seed by seed.
* **R3** `check_core --opcodes all` below 169,000 ⇒ some other form has an
  empty-tail withdrawal with an asserted pin that silicon takes DIRECT.  That
  would be the golden-vs-golden contradiction the brief says to STOP on.
* **R4** any SSA address, `SS_VERSION`, `SS_COUNT`, `SS_TAG` or flop-census
  figure moves ⇒ the repair added state and is suspect on its face.
* **R5** G6 below 32 MHz, or `c_ready_q` present in a timing report.

None of R1–R5 is expected.  Reported as registered either way.
