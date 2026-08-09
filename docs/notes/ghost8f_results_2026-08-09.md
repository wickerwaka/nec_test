# THE 8F GHOST FAMILY — RESULTS, reported AS REGISTERED

Pre-registration: `docs/notes/ghost8f_prereg_2026-08-09.md`, committed
`9b7ddec4f3` **before** the first line of RTL.  Read that first; this document
answers it clause by clause and does not restate any of it.

Branch `fuzz-v2-on-relanding`.  Offline: no board, no flash.

---

## §1  THE THREE COLUMNS AND THEIR RECEIPTS

| | what | Verilator receipt |
|---|---|---|
| **A** | baseline — HEAD, no ghost family | `ad20d79bfcfa8771…` |
| **B** | FAITHFUL `5403671558`, live `ready` pin.  **Measured, NOT landed** | `9b1a9614a12fb9b1…` |
| **C** | the §73-TREATED form.  **Measured, and NOT LANDED EITHER — G6 is RED, §9** | `7b022b73b08ab14a…` |

⚠ **HEADLINE, so nothing below is read as a landing.**  Every behavioural gate
is green and the mechanism is worth having (§3, §4), but **G6 is RED at 15.3
MHz with all twelve worst paths launching from `system_large|c_ready_q`** —
both of P8's own refutation conditions — so **NO RTL IS LANDED BY THIS
SITTING**.  The finding is §9.2: getting the live pin off `stop` is NECESSARY
AND NOT SUFFICIENT, because the ghost FEED reaches the loader chain through the
DATA path.  The work is retained as patches (§9.4).

---

## §2  THE GATE TABLE — A, B, C side by side

| gate | A | B (faithful) | C (treated) |
|---|---|---|---|
| `gen_ucore_qsf --check` | PASS | PASS | **PASS** |
| **`r7_lint`** | PASS (1 declared carrier) | **FAIL — 3 undeclared carriers, 7 `stop` sites** | **PASS — 21 BIU→EU nets, 1 declared carrier, 11 tainted, 50 `stop` sites, 0 violations, NO NEW EXCEPTIONS** |
| `ss_lint --core ucore` | PASS 0x8B / 101 / 121 / 223 / 0x8BDF | PASS **0x8E / 101 / 126 / 228 / 0x8EE4** | PASS **0x8E / 101 / 126 / 228 / 0x8EE4** |
| `ss_flopcensus` | 211 (BIU 83; EU 128→126+2) | **216** (BIU 83; EU 133→131+2) | **216** (BIU 83; EU 133→131+2) |
| `test_artifact` | 45/45 | — | **45/45** |
| `check_core 8F.0 --cases 0` | 500/500 | 500/500 | **500/500** |
| `check_core INT.F3AA` | 165/200 | 165/200 | **165/200** |
| `check_core --opcodes all --cases 0` | 168,965/169,000 | 168,965/169,000 | **168,965/169,000** |
| `ulockstep --golden 8F.0 --cases 50` | 50/50 | **45/50** | **45/50** |
| `ulockstep --golden INT.F3AA` | 45/50 | 45/50 | **45/50** |
| `ulockstep --golden all --cases 50` | 17,345/17,350 | 17,340/17,350 | **17,340/17,350** |
| four HLT sweeps | 97·93·45·44 = **279/283** | 279/283 | **279/283** |
| `timed_fuzz --bank fz2c,fz2e --evt-replay` | REG 8/11, EVT 3/3, **COMB 11/14** | REG 9/11, EVT 3/3, **COMB 12/14** | REG 9/11, EVT 3/3, **COMB 12/14** |
| …`BOUND WARNINGS` | **2** (`fz2e/520000`, `fz2e/522003`) | **0** | **0** |
| `fz2_w1 bars` | 8/11 MET (C-1,C-3,C-6 missed) | — | **8/11 MET, every `measured` byte-identical to A** |
| `fz2_w1 lint` | PASS 0 hits / 48 rows | — | **PASS 0 hits / 48 rows** |
| `test_fuzz_classify` / `test_fuzz_accept` | PASS / PASS | — | **PASS / PASS** |

Every figure was measured this sitting.  Nothing is quoted from `CLAUDE.md`.

---

## §3  A→B — THE MECHANISM'S BENEFIT, seed by seed

**This is the first per-mechanism benefit measurement any of the nineteen has
had.**  Denominator, as registered in §2 of the pre-registration: the SCORED
fuzz column on this branch is **14 seeds** (623 offered, 609 `OPEN_BUS`).  No
percentage of 14 is quoted.

**The scored column moves by ONE seed, and it is named:**

    fz2c/406000    DIVERGE -> EXACT    ndiff 289 -> 0     first_bad 212 -> 523
    REGISTERED 8/11 -> 9/11 ; COMBINED 11/14 -> 12/14

**`BOUND WARNINGS` 2 → 0.**  Both seeds whose completed-read store SATURATED at
the baseline (`fz2e/520000`, `fz2e/522003`) stop saturating with the family in.
That is the ghost's own bookkeeping: the discard token is what keeps an
unmatched tail completion out of `rdq`.

**Twenty-five of the 623 seeds change their row stream at all, and the size of
the change is the real evidence the mechanism is not cosmetic.**  Full table,
sorted by delta; `OPEN_BUS` seeds are EXCLUDED FROM THE SCORE and are reported
because their `ndiff` is still a measurement:

| seed | A cat | C cat | A ndiff | C ndiff | delta |
|---|---|---|---|---|---|
| `fz2e/521006` | OPEN_BUS | OPEN_BUS | 3358 | **0** | −3358 |
| `fz2e/518033` | OPEN_BUS | OPEN_BUS | 3075 | 277 | −2798 |
| `fz2e/522002` | OPEN_BUS | OPEN_BUS | 3055 | 353 | −2702 |
| `fz2e/522029` | OPEN_BUS | OPEN_BUS | 3070 | 382 | −2688 |
| `fz2e/521024` | OPEN_BUS | OPEN_BUS | 3072 | 482 | −2590 |
| `fz2e/520000` | OPEN_BUS | OPEN_BUS | 2820 | 1269 | −1551 |
| `fz2e/519016` | OPEN_BUS | OPEN_BUS | 1459 | 2 | −1457 |
| `fz2e/522003` | OPEN_BUS | OPEN_BUS | 1736 | 401 | −1335 |
| `fz2e/521059` | OPEN_BUS | OPEN_BUS | 2808 | 1629 | −1179 |
| `fz2e/520040` | OPEN_BUS | OPEN_BUS | 943 | 4 | −939 |
| `fz2c/410008` | OPEN_BUS | OPEN_BUS | 916 | 4 | −912 |
| `fz2e/518039` | OPEN_BUS | OPEN_BUS | 1005 | 102 | −903 |
| `fz2e/520066` | OPEN_BUS | OPEN_BUS | 860 | 8 | −852 |
| `fz2e/519072` | OPEN_BUS | OPEN_BUS | 622 | 4 | −618 |
| `fz2e/521016` | OPEN_BUS | OPEN_BUS | 537 | 14 | −523 |
| **`fz2c/406000`** | **DIVERGE** | **EXACT** | **289** | **0** | **−289** |
| `fz2e/521049` | OPEN_BUS | OPEN_BUS | 793 | 544 | −249 |
| `fz2e/518050` | OPEN_BUS | OPEN_BUS | 2793 | 2556 | −237 |
| `fz2c/408068` | OPEN_BUS | OPEN_BUS | 409 | 405 | −4 |
| `fz2e/518022` | OPEN_BUS | OPEN_BUS | 698 | 695 | −3 |
| `fz2e/518053` | OPEN_BUS | OPEN_BUS | 424 | 423 | −1 |
| **`fz2e/520005`** | **DIVERGE** | **DIVERGE** | 2922 | 2935 | **+13** |
| `fz2e/518004` | OPEN_BUS | OPEN_BUS | 360 | 376 | +16 |
| `fz2e/518067` | OPEN_BUS | OPEN_BUS | 3246 | 3273 | +27 |
| `fz2e/518006` | OPEN_BUS | OPEN_BUS | 771 | 816 | +45 |

**21 improved, 4 worsened, 0 seeds lost from the scored column.**  The one
scored seed that gets WORSE is `fz2e/520005`: it was DIVERGE and stays DIVERGE,
+13 rows.  It is named here rather than absorbed into a total.

---

## §4  A→B ON THE GOLDENS — P3a is CONFIRMED, AND IN THE OPPOSITE DIRECTION
## TO THE BRIEF

The brief predicted "the ghost read is the predicted owner of the original
45/50" at `ulockstep --golden 8F.0`.  **Measured, the baseline is 50/50** — so
there was nothing at the baseline for the family to own, and the
pre-registration therefore registered the other direction: with the family in,
`8F.0` should FALL below 50/50 because `ulockstep` scores the RTL against
`sim/`, and **`sim/` does not implement this family** (prereg §1).

**It fell to exactly 45/50**, in both B and C, and the divergence columns name
the mechanism:

    8F.0: 45/50  5 DIVERGE  first: idx 5@5:ad_data,ps,ad_addr,
                                   idx 6@8:ad_data,ps,ad_addr,
                                   idx 16@8:ad_data,ps,ad_addr

`ad_addr` / `ad_data` / `ps` on the stack-read cycle IS the ghost address.  The
brief's "original 45/50" is the WITH-family figure, not the baseline's.

**This is NOT a silicon-match regression and must not be reported as one.**
The silicon bar for `8F.0` is `check_core --opcodes 8F.0 --cases 0`, which
compares against the SILICON goldens and **HOLDS at 500/500** in all three
columns — the ghost address is a documented don't-care in that comparator
(`closure_checkpoint.md`, "8F.0 mod3 ghost-read address — RESOLVED
2026-07-13").  `ulockstep --golden all` falls 17,345 → 17,340 and **the whole
five is `8F.0`'s**; no other form moved a case.

P3b (reachability) is met by the same evidence: the family fires.

---

## §5  B→C — THE TREATMENT'S COST, AND IT IS NOT ZERO

**Every gate in §2 is identical between B and C**, including the scored fuzz
column, all 169,000 golden cases, all 17,350 lockstep cases and all 283 HLT
sweep cells.

**But B and C are NOT bit-identical.**  Six seeds' row streams differ, all six
`OPEN_BUS` and therefore off the scored column:

| seed | B ndiff | C ndiff | B first_bad | C first_bad |
|---|---|---|---|---|
| `fz2c/410008` | 4 | 4 | 1198 | 1192 |
| `fz2e/518004` | 369 | 376 | — | — |
| `fz2e/519016` | 0 | **2** | 2248 | 236 |
| `fz2e/520000` | 1257 | 1269 | 2113 | 642 |
| `fz2e/520040` | 0 | **4** | 1370 | 253 |
| `fz2e/522029` | 354 | 382 | 785 | 377 |

**P9 IS THEREFORE A PARTIAL MISS AND IS REPORTED AS ONE.**  It registered "B
and C are predicted identical on every gate in §7", which is MET; it did not
register that they would be identical off-gate, and they are not.  Two seeds
that the faithful form drove to `ndiff 0` (`fz2e/519016`, `fz2e/520040`) come
back at 2 and 4 rows under the treatment.

**This is exactly the trade P2c registered in advance**, and it is the whole
finding of the sitting:

> `ghost_preread_late` is built from `eu_rd_edge`, §73's ONE declared READY
> carrier — and `r7_lint` check (b) deliberately does not except it.  In
> `5403671558` the arm sits at the head of `S_PRERD`'s `if`/`else if` chain, so
> when it fires it takes `stop` from **1 to 0**: the live READY pin RELEASES
> eleven more loader-chain positions.  That is R7′ **by construction**, not a
> lint artifact, and **no re-timing removes it, because READY at clock *c* is
> not knowable before clock *c*.**

Under the treatment the arm keeps everything that is DATA — OPR takes the
data-edge word on the SAME clock, `st` advances on the SAME clock — and gives
up the one thing that is CONTROL: the chain does not CONTINUE, so `S_ENTER`
runs on the following clock in the two branches where the original released it.
Six seeds can see that one clock; none of them is on a gate.

**The conflict is REAL, it is one clock wide, and it is priced.**  Taking the
faithful form back would mean re-opening R7′, which the spike measured at
**15.56 MHz against a 32 MHz bar** (`539c6f8406`).

---

## §6  THE TREATMENT, AND WHY IT IS NOT A TRICK PLAYED ON THE LINT

Three parts, all pre-registered, all documented in the RTL beside the code.

**P2a — the four published rails read `r_ready_prev`, not the pin.**  This is
`v30u_biu.sv`'s OWN discipline: M2r, in its header, says "the CPU registers
READY at the end of every clock" and "`ready_prev` is the registered READY
pin".  `eval_inst` already obeys it; the only bare-pin readers left were the
`ts` advance itself and `rd_data_edge` (§73's declared carrier).
`5403671558`'s three ghost rails were the anomaly.  **Cost: zero flops, zero
save-state addresses, no BIU version bump** — `r_ready_prev` is an existing
mapped flop.  Predicted before measuring, from the rig's own READY law:
`eu_ghost_stack_first` exactly unchanged, `eu_ghost_full` and `eu_rd_wait`
differing on one clock each.

**P2b — `acc_split_wr`, the write accounting's own ghost-free split.**  The
ghost rails reached `stop` through
`acc_split → row_wr_add → wr_after → retire_ok_e → bnd_row → at_bnd → bnd_fire`
(the two `v30u_eu_row.svh` sites `r7_lint` names).  They cannot MATTER there:
`row_wr_add` is gated on `row_is_wr || row_is_wb` and `ghost_read_stale_alu`
requires `row_is_read`.  Disjoint in VALUE, joined only in TEXT.  The write
side now computes its own value, which is what this expression computed before
the family landed — **exact, not an approximation**, and it removes a real cone
as well as a lint edge.

**P2c — S_PRERD's ghost-late arm writes only register `D` pins.**  §5 above.

**What the treatment does NOT do.**  It does not add an exception to either of
`r7_lint`'s declared lists — both are exactly as L1 left them.  It does not
move a `stop` assignment textually while leaving the physical dependence; on
every clock where the ghost arm can change `st_n` relative to the ordinary
path, `stop` is already 1 at chain position 0, so no later position runs and
`st_n`'s taint is inert.  In the one branch that does continue
(`rd_done_cnt != 0`, `!ld_grpd`) both paths set `st_n` to the same state and
only `opr_n` differs.

**One thing to carry forward, stated because it is a cone the lint's charter
does not cover.**  `r7_lint` now reports `q_demand` / `q_first` / `q_pop` and
`eu_post_hold` as TAINTED — `ghost_preread_epop` reads `eu_rd_wait` and
`eu_rd_edge`, and those four are EU OUTPUTS.  They land on the BIU's queue and
request registers' `D` pins, which is §73's admitted shape and not a chain
control, and G6 is the authority on whether that costs anything.  It is named
here so the next sitting does not discover it.

---

## §7  THE SAVE-STATE MAP — as pre-registered, to the digit

`SS_VERSION` **0x8B → 0x8E**, `SS_BIU_COUNT` **101** (unchanged),
`SS_EU_COUNT` **121 → 126**, `SS_COUNT` **223 → 228**,
`SS_TAG` **0x8BDF → 0x8EE4**, flop census **211 → 216**.

`0x176` takes `SSA_E_GHOST_DISCARD` — the occupant the code was RESERVED for,
by name, in `v30u_ss_pkg.sv` — so **no skip is owed**, `ss_addr_of`'s EU hole
term is REMOVED and nothing is renumbered: `0x177`–`0x179` sat one step past
the hole and now sit one step past the occupant, which is the same address.
`0x17A`/`0x17B` are the feed, `0x17C`/`0x17D` the ModR/M hold.  Three bumps,
one per appended group.  The BIU's `0x038` is again the map's only hole.

⚠ **0x8E is also `5403671558`'s version for this same set, and that is
arithmetic coincidence, not compatibility.**  L1 spent a version on the
`SSA_E_IRQ_LATCH` widening that commit did not spend.  The two v14 streams are
NOT interchangeable.

**A gate found a defect in the first draft of this landing, correctly.**
`ss_lint` FAILed with *"`SSA_B_READY_PREV` referenced 3x (expected 2)"* — the
third reference was a COMMENT in `v30u_biu.sv` naming the symbol in prose.  The
audit counts SSA_ names by text and is right to; the comment was reworded.
Recorded because a lint that catches its own author is worth the record.

---

## §8  THE VERDICT AGAINST EACH REGISTERED PREDICTION

| | prediction | verdict |
|---|---|---|
| **P1** | `8F.0` holds 500/500 in B and C | **MET** |
| **P2** | `INT.F3AA` not worse than 165/200 | **MET** (165/200 in both) |
| **P3a** | `8F.0` ulockstep FALLS below 50/50, and that is expected | **MET** — 45/50, and `check_core 8F.0` holds |
| **P3b** | the family is reachable | **MET** — 25 seeds move, one flips DIVERGE→EXACT, `BOUND WARNINGS` 2→0 |
| **P4** | `check_core all` ≥ 168,965 and `ulockstep all` ≥ 17,345 except `8F.0` | **MET** — 168,965; 17,340 with all five losses inside `8F.0` |
| **P5** | HLT sweeps 279/283 | **MET** |
| **P6** | no fz2 bar moves | **MET** — 8/11, every `measured` byte-identical |
| **P7** | fuzz COMBINED ≥ 11/14 | **MET, RAISED to 12/14** |
| **P8** | G6 PASS, ≥ 32 MHz, no `c_ready_q` launch | **REFUTED, on BOTH conditions — §9** |
| **P9** | B and C identical on every gate | **MET on the gates; PARTIAL MISS off them** — six `OPEN_BUS` seeds differ (§5) |

**Nine predictions, eight met (one of them partially), one REFUTED — and the
refuted one is the gate that decides whether this lands.**

---

## §9  G6 — **RED.  P8 IS REFUTED, ON BOTH OF ITS OWN CONDITIONS, AND THE
## FAMILY IS THEREFORE NOT LANDED**

CONTROL/DEFAULT build (no `X1_AD_RETENTION`), clean `db`, tree
`9b7ddec4f3-dirty` = the §73-treated form, inputs `f81e40c12728d546…`
(88 files).

| draw | verdict | Fmax | worst setup | TNS | ALMs | compile | receipt |
|---|---|---|---|---|---|---|---|
| 1 | **RED** | **15.3 MHz** | **−34.094 ns** | **−10,443.096** | 11,995 / 41,910 (29 %) | 741 s | `6bb7cbda05d7569f…` |
| 2 | **RED** | **15.3 MHz** | **−34.094 ns** | **−10,443.096** | 11,995 / 41,910 (29 %) | 755 s | `104b51e33fd753b1…` |

`E2_zero_errors` PASS on both — 0 errors, 0 error lines, map/fit/asm all
successful, 0 latches, 0 `lpm_divide`.  The compile is clean; the TIMING is not.

**The two draws agree to the digit on Fmax, slack, TNS and ALMs.**  Two draws
is not a distribution and `standing_gates.md` §A still says the same tree has
drawn 19.42 and 45.91 MHz — but a 15.3/15.3 pair whose failing set is 100 %
`c_ready_q` launches is a CONE, not a draw, and the spike's RED tree measured
15.14 and 15.56 on the same signature.

**P8 registered two refutation conditions and BOTH are met:**

1. *"measured Fmax below 32 MHz"* — **15.3 MHz.**
2. *"any failing path launching from `system_large|c_ready_q`"* — **all twelve
   worst setup paths do**, and they land on `v30u_eu|opc_base[4]`, which is the
   SAME endpoint the two earlier R7′ collapses landed on (§73's own note in
   `v30u_eu.sv`: *"`c_ready_q` → `v30u_eu|opc_base[3]` at 62-63 logic levels,
   51.2 ns against 31.25, on 20,000 of 20,000 failing paths, Fmax 19.42 MHz"*).

### §9.2  THE FINDING — GETTING THE PIN OFF `stop` WAS NECESSARY AND **NOT
### SUFFICIENT**

The route is read off the netlist, not inferred
(`sw/testdata/relanding/ghost8f_worst_paths.rpt` is the full path):

    c_ready_q -> u_biu|eu_rd_edge -> u_eu|ghost_preread_epop -> q_demand
              -> rd_done_cnt_n -> rdq0_n -> opr_n -> v1 -> Add57* -> Mux348*
              -> ld_b_n -> st_n -> ... -> opc_base[4]

**`stop` is not on it.**  `r7_lint` PASSES on this tree, with no new
exceptions, and it is right to: no `stop` assignment sits under a live-READY
condition.  The ghost FEED reaches the loader chain through the **DATA** path —
register `D` pins the whole way — and `st_n` **is** a `D` pin that the next
chain position reads.  `r7_lint`'s charter is `stop`; this cone is outside it.

**§10's third booked item called this in advance and it was the right thing to
watch.**  `q_demand` / `q_first` / `q_pop` went from untainted to tainted in
this landing, and `q_demand` is the second hop of the failing path.

**The deeper statement, and it is the sitting's real deliverable.**  §73
admitted `eu_rd_edge` as the ONE live-READY carrier on an explicit condition,
written in `v30u_eu.sv`:

> it is admitted only because its single consumer is the `psw` register's own
> `D` pin … NOT the head of the loader chain — which is exactly what R7′ moved.

**The 8F ghost feed gives `eu_rd_edge` a SECOND consumer, and that consumer is
the loader chain.**  That breaks the exception's own terms even though the
`stop` lint cannot see it.  `ghost_preread_epop`'s `!ghost_rd_discard` arm
reads `eu_rd_edge` directly, and from there the pin selects `q_demand`, the
completion store's pops and `opr_n` — i.e. the decode's own input.

**No re-timing removes it** for the same reason P2c gave: READY at clock *c* is
not knowable before clock *c*, and the mechanism's whole content is *"the
successor pops at the data edge"*.  A feed that fires one clock later is a
different mechanism, and it would be measured as one.

### §9.3  WHAT IS AND IS NOT ESTABLISHED

* **ESTABLISHED**: the family is real, reachable and worth having — §3's 25
  seeds, the `DIVERGE → EXACT` flip, `BOUND WARNINGS` 2 → 0, and §4's `8F.0`
  ghost address appearing in `ad_addr`/`ad_data`/`ps` exactly where `sim/` has
  nothing.
* **ESTABLISHED**: the READ's and the HOLD's own cost is not what breaks
  timing — the spike already measured the READ as worth ~0.4 MHz
  (`539c6f8406`), and P2a/P2b take its two `stop` routes out exactly.
* **REFUTED**: that §73's treatment, defined as "get the live pin off the
  control cone / off `stop`", is enough for the FEED.  It is not.
* **NOT ESTABLISHED, and NOT ATTEMPTED**: whether a read-only landing (ghost
  READ + rails, no feed, no hold) closes timing.  It is the obvious next
  experiment — the hold is provably dead without the feed, so it would be
  READ-alone — and it needs its own pre-registration and its own G6.  Nothing
  in this sitting licenses assuming it passes.

### §9.4  THE DISPOSITION

**The RTL is NOT landed.**  `CLAUDE.md`'s standing rule is that an RTL landing
is not accepted without a PASSING Quartus receipt, and there is none.  The work
is retained, complete and re-runnable, as two patches beside the spike's:

    sw/testdata/relanding/ghost8f_landing.patch     apply    -> column C
    sw/testdata/relanding/ghost8f_treatment.patch   apply -R -> column B
    sw/testdata/relanding/ghost8f_worst_paths.rpt   the refutation's evidence

Both apply to `9b7ddec4f3`.  Every figure in this document is re-derivable from
them.

---

## §10  BOOKED, NOT DONE

* **`docs/notes/standing_gates.md`'s save-state row is STALE and this landing
  did not fix it.**  Line 295 still reads *"219 addresses, 205 flops,
  `SS_VERSION` 0x87"*, which is the pre-branch state — it was already stale by
  L1 (`0x8B` / 223 / 205), and it is now stale by two landings (`0x8E` / 228 /
  216).  Named rather than edited, because the file is the authoritative
  standing list and rewriting a cell of it is coordinator territory.
* **`sim/` still does not implement the 8F ghost family** (prereg §1).  While
  that is true, `ulockstep --golden 8F.0` scores 45/50 BY CONSTRUCTION and no
  ucore/model head-to-head on `8F.0` means anything.  The model leg is a
  separate landing and is not attempted here.
* **The four newly-tainted EU outputs** (`q_pop` / `q_demand` / `q_first` and
  `eu_post_hold`) put READY into the BIU's queue and request registers' `D`
  pins.  §73's shape, not a chain control, and outside `r7_lint`'s charter —
  G6 is the authority.  Named so it is not rediscovered.
* **The fuzz column is 14 seeds wide on this branch** and that is a corpus
  problem, not this landing's.  A benefit measurement with a denominator of 14
  is the best instrument the branch currently has; rebuilding a replayable
  corpus is the standing work item SUP-1 left open.
* **TWO MORE STANDING GATES ARE BROKEN AT HEAD ON THIS BRANCH, AND NEITHER IS
  THIS LANDING'S DOING.**  `sw/timed_wvec_gate.py --core ucore` and
  `sw/timed_enter_replay.py --core ucore` both die inside `image_of(seed)` on
  `sw/gen_seq._v1_anchor_stop` — fuzz-v2 moved the image anchor and their
  goldens are frozen at the v1 anchor, so the tools REFUSE rather than score v2
  images against v1 silicon.  That refusal is correct and the tools say so in
  as many words ("Do NOT relax this check to get a green").  They are
  engine-independent and fail identically on the baseline.  This is the same
  class L1 booked for `timed_scenario.py` and `timed_ins_replay.py`: a standing
  ratchet in `CLAUDE.md` that nothing on this branch can run.  **Four of them
  now.**  Booked, not fixed here — the fix is a board re-capture and a USER
  DECISION.

---

## §11  EXTRA DILIGENCE, not on the brief's list

Run on the landed tree (receipt `7b022b73b08ab14a…`), all green:

* `check_boot.py --core ucore` — **MATCH over 220 rows**
* `check_boot.py --core ucore --timed 400` — **MATCH over 400 rows**
* `check_core --core ucore --opcodes 8F.0 --ss-sweep --ss-mode 5` (round-trip
  width sweep, the one that walks every address in the map) — **4/4 PASS**,
  `first-diverging-k = none` on all four
* `--ss-mode 2` (idempotence) — **4/4 PASS**; `--ss-mode 1` (scramble) —
  **3/3 PASS**

The mode-5 leg matters here specifically: it is what exercises the five NEW
addresses and the `ss_addr_of` hole removal end to end, and `8F.0` is the form
that reaches the family.
