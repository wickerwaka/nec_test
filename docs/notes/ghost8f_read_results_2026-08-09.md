# THE 8F GHOST **READ**, ALONE — RESULTS, reported AS REGISTERED

Pre-registration: `docs/notes/ghost8f_read_prereg_2026-08-09.md`, committed
`60443102ff` **before the first line of RTL**.  Read that first; this document
answers it clause by clause and does not restate it.

Branch `fuzz-v2-on-relanding`, base `751735d73f`.  Offline: no board, no flash.

---

## §1  HEADLINE

**G6 IS GREEN AND THE READ IS LANDED.**  PASS on both CONTROL draws, **TNS
0.000 on every domain, setup and hold**, and **the string `c_ready_q` does not
occur anywhere in either draw's timing report** — the previous sitting's
refutation signature is not merely absent from the failing set, there is no
failing set and no occurrence.

**And the mechanism's whole measured benefit survives the amputation.**  The
read ALONE reproduces the full family's fuzz result seed for seed: `BOUND
WARNINGS` **2 → 0**, `fz2c/406000` **DIVERGE → EXACT**, COMBINED **11/14 →
12/14**, and **25,200 improved rows against the full family's 25,188 — 100.0 %
retained, on a bar registered at ≥ 70 %.**  The registered attribution — *the
READ owns the address, the FEED owns the cadence* — is **CONFIRMED**, and it is
confirmed in the strong direction: the feed was buying **nothing measurable** on
this population.

**Two clauses MISSED and both are reported as misses, not restated**: the ALM
budget (§7.2) and the Fmax band (§7.3).

---

## §2  THE GATE TABLE — baseline vs the READ-ONLY landing

| gate | baseline `751735d73f` | READ-ONLY | verdict |
|---|---|---|---|
| `gen_ucore_qsf --check` | PASS | **PASS** | as registered |
| **`r7_lint`** | PASS — 17 nets, 1 carrier, 3 tainted, 51 `stop` sites | **PASS — 20 nets, 1 carrier, 3 tainted, 51 `stop` sites, NO new exception** | as registered, to the digit |
| `ss_lint --core ucore` | PASS `0x8B`/101/121/223/`0x8BDF` | **PASS `0x8C`/101/122/224/`0x8CE0`** | as registered |
| `ss_flopcensus` | PASS 211 | **PASS 212** | as registered |
| `test_artifact` | 45/45 | **45/45** | as registered |
| **`check_core 8F.0 --cases 0`** | 500/500 | **500/500** | **the silicon bar HOLDS** |
| `check_core INT.F3AA` | 165/200 | **165/200** | as registered |
| `check_core --opcodes all --cases 0` | 168,965/169,000 | **168,965/169,000** | as registered |
| **`ulockstep --golden 8F.0 --cases 50`** | 50/50 | **45/50**, first div `ad_data,ps,ad_addr` at idx 5, 6, 16 | **as registered — see §6** |
| `ulockstep --golden all --cases 50` | 17,345/17,350 | **17,340/17,350**, exactly TWO diverging forms | as registered |
| four HLT sweeps | 97·93·45·44 = 279/283 | **97·93·45·44 = 279/283** | as registered |
| `timed_fuzz --bank fz2c,fz2e --evt-replay` | REG 8/11, EVT 3/3, **COMB 11/14** | REG **9/11**, EVT 3/3, **COMB 12/14** | as registered |
| …`BOUND WARNINGS` | **2** (`fz2e/520000`, `fz2e/522003`) | **0** | as registered |
| `fz2_w1 lint` | PASS 0 hits / 48 rows | **PASS 0 hits / 48 rows** | as registered |
| `fz2_w1 bars` | 8/11 MET (C-1, C-3, C-6) | **8/11 MET, same three** | as registered — §10.1 |
| `test_fuzz_classify` / `test_fuzz_accept` | PASS / PASS | **PASS / PASS** | as registered |
| **G6 CONTROL, two draws** | PASS 41.80 / 41.80 MHz | **PASS 39.57 / 39.57 MHz** | **§7** |

Verilator receipts: baseline **`2b448eecda7c97ac…`**, landing
**`84c6c45192f83d16…`**.  Both figures in every row above were measured this
sitting; nothing is quoted from `CLAUDE.md`.

---

## §3  THE EXTRACTION, AND IT IS CHECKABLE BY GREP

The pre-registration's rule was mechanical: DROP any construct referencing
`ghost_rd_feed`, `ghost_rd_ready`, `opc_rm_valid`, `opc_rm_byte`, `eu_rd_wait`,
`eu_ghost_preview` or `eu_rd_edge`.  Verified on the landed tree:

```
ghost_rd_feed 0 · ghost_rd_ready 0 · opc_rm_valid 0 · opc_rm_byte 0
eu_rd_wait 0 · eu_ghost_preview 0 · ghost_preread_epop 0
ghost_preread_late 0 · ghost_row_tail 0 · ghost_rm_pop 0      code hits
```

**And the brief's open question is answered from the RTL, not assumed.**
`eu_rd_edge`'s consumers inside `v30u_eu.sv` are now exactly the port
declaration and `rd_edge_take_raw` — §73's ONE admitted consumer, feeding the
`psw` register's own `D` pin.  **The read rides registered state only**;
`S_PRERD` and `S_MODRM` are byte-identical to `751735d73f`.

`r7_lint -v` says the same thing independently: the three new BIU→EU nets
`eu_ghost_full` / `eu_ghost_idle` / `eu_ghost_stack_first` are each classified
**`register-only`**, the carrier count stays at 1, and the `stop`-site count
stays at **51** — the read adds no `stop` site at all.

---

## §4  WHAT THE READ IS, IN THE END — ONE FLOP AND ONE PREDICATE

The full family's completion block is a five-way `if`/`else if` chain.  Four of
its five branches exist only to hand the token and the maturity bit to the FEED.
With the feed gone the whole thing collapses to:

```
if (rd_pending_n != 2'd0) rd_pending_n = rd_pending_n - 2'd1;
if (ghost_rd_discard_n && (rd_pending_n == 2'd0)) ghost_rd_discard_n = 1'b0;
else begin <the ordinary completion store, unchanged> end
```

The bus has no result tags and returns words in order, so every completion is
taken by the oldest requester still waiting — the **one-place displacement** —
and exactly one completion at the end of the chain has nobody waiting for it.
`rd_pending_n == 0` after the decrement **is** that condition.

**This is not a re-invention: it is what L1 wrote into `v30u_ss_pkg.sv` when it
reserved `0x176`**, verbatim — *"the bit follows the resulting one-place
displacement through an overlapping read chain so the unmatched tail completion
is dropped."*  The mechanism arrived at the address its own reservation
described.  One flop, one predicate, no counter, no table.

**The §73 treatment survives in both halves**, and both are load-bearing:
P2a (the three rails on the BIU's registered READY, zero flops, zero addresses)
and P2b (`acc_split_wr`, the write accounting's ghost-free split — exact, since
`row_wr_add` is gated on `row_is_wr || row_is_wb` and `ghost_read_stale_alu`
requires `row_is_read`).

---

## §5  THE FUZZ DELTA — §5's ATTRIBUTION CONFIRMED, AND MORE STRONGLY THAN
## REGISTERED

| | registered | measured | verdict |
|---|---|---|---|
| **F1** | `BOUND WARNINGS` 2 → 0 | **0**, and the two named seeds both stop saturating | **MET** |
| **F2** | `fz2c/406000` DIVERGE → EXACT; REG 9/11, COMB 12/14 | **EXACT**, ndiff 289 → **0**; REG **9/11**, COMB **12/14** | **MET** |
| **F3** | ≥ 70 % of the 25,188 gross improved rows retained | **25,200 — 100.0 %** | **MET, and exceeded** |
| **F4** | `fz2e/521006` ndiff ≤ 100 | **0** | **MET** |
| **F5** | SCORED stays 14, no seed lost | **14**, none lost | **MET** |

The same **25 of 623** seeds move, and 21 of them land on the full family's
`ndiff` **to the row**:

| seed | A | READ-ONLY | delta | full family C |
|---|---|---|---|---|
| `fz2e/521006` | 3358 | **0** | −3358 | 0 |
| `fz2e/518033` | 3075 | 277 | −2798 | 277 |
| `fz2e/522002` | 3055 | 353 | −2702 | 353 |
| `fz2e/522029` | 3070 | 382 | −2688 | 382 |
| `fz2e/521024` | 3072 | 482 | −2590 | 482 |
| `fz2e/520000` | 2820 | 1269 | −1551 | 1269 |
| `fz2e/519016` | 1459 | 2 | −1457 | 2 |
| `fz2e/522003` | 1736 | **400** | −1336 | 401 |
| `fz2e/521059` | 2808 | 1629 | −1179 | 1629 |
| `fz2e/520040` | 943 | 4 | −939 | 4 |
| `fz2c/410008` | 916 | 4 | −912 | 4 |
| `fz2e/518039` | 1005 | 102 | −903 | 102 |
| `fz2e/520066` | 860 | 8 | −852 | 8 |
| `fz2e/519072` | 622 | 4 | −618 | 4 |
| `fz2e/521016` | 537 | 14 | −523 | 14 |
| **`fz2c/406000`** | **289** | **0** | **−289** | **0** |
| `fz2e/521049` | 793 | 544 | −249 | 544 |
| `fz2e/518050` | 2793 | **2548** | −245 | 2556 |
| `fz2c/408068` | 409 | 405 | −4 | 405 |
| `fz2e/518006` | 771 | **768** | −3 | 816 |
| `fz2e/518022` | 698 | 695 | −3 | 695 |
| `fz2e/518053` | 424 | 423 | −1 | 423 |
| `fz2e/520005` | 2922 | 2935 | +13 | 2935 |
| `fz2e/518004` | 360 | **379** | +19 | 376 |
| `fz2e/518067` | 3246 | 3273 | +27 | 3273 |

**Only FOUR seeds differ from the full family at all**, all `OPEN_BUS`, and the
net is in the read-only column's favour: `518006` −48, `518050` −8, `522003` −1,
`518004` +3.  That is the §3.3 KNOWN DIFFERENCE registered in advance — with no
feed the discard token is held for more clocks, so `ghost_preread_tail`'s
`pr_seg2` / `eu_word` overlays can assert on clocks the full family did not.
**It was registered as a possible cost; measured, it is a small net benefit.**

**THE FINDING THIS PRODUCES.**  On the measurable population the ghost FEED —
the mechanism that cost 26.5 MHz of Fmax and blocked the whole family — bought
**nothing**: not one scored seed, not one `BOUND WARNING`, and a net **−54 rows**
across four `OPEN_BUS` streams.  Every benefit §3 of the previous sitting's
results doc measured is the READ's.  That is a per-mechanism attribution the
campaign did not have, and it is the reason the feed's non-landing costs nothing
that has been measured.

`fz2e/520005` — the one scored seed that WORSENS — worsens by the same +13 as in
the full family, to the same 2935.  It was registered as not-a-refutation and it
is named here rather than absorbed into a total.

---

## §6  `ulockstep 8F.0` — THE REGISTERED FALL, WITH THE REGISTERED SIGNATURE

    8F.0: 45/50  5 DIVERGE  first: idx 5@5:ad_data,ps,ad_addr,
                                   idx 6@8:ad_data,ps,ad_addr,
                                   idx 16@8:ad_data,ps,ad_addr

Predicted 45/50, `ad_data,ps,ad_addr` — **met on the count, on the signature and
on the three named indices, which are the full family's three.**  This is the
mechanism BEING PRESENT: `sim/` has no 8F ghost family, so an RTL that is right
must lose against a model that is not.

The control that makes it readable is `check_core --opcodes 8F.0 --cases 0`,
which compares against the SILICON goldens and **HOLDS at 500/500**.  The ghost
address is a documented don't-care there (`closure_checkpoint.md`, "8F.0 mod3
ghost-read address — RESOLVED 2026-07-13").  **This is not a silicon-match
regression and must not be reported as one.**

`ulockstep --golden all` over **347 forms** has exactly **two** non-perfect
cells: `8F.0` at 45/50 (new, the ghost address) and `INT.F3AA` at 45/50
(pre-existing at the baseline, `qs`).  **All five new losses are inside `8F.0`**
and no other form moved a case — the registered clause, verified against the
full listing rather than inferred from the total.

---

## §7  G6 — **PASS ON BOTH DRAWS**

CONTROL/DEFAULT build (no `X1_AD_RETENTION`), clean `db`, tree
`60443102ff-dirty`, inputs `632c8c20dd811c90…` (88 files).

| draw | verdict | Fmax | worst setup | setup TNS | worst hold | hold TNS | ALMs | registers | compile | receipt |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **PASS** | **39.57 MHz** | **+5.978 ns** | **0.000** | +0.250 ns | 0.000 | 12,325 / 41,910 (29 %) | 6,291 | 599 s | `bcc4e46e6a6a6501…` |
| 2 | **PASS** | **39.57 MHz** | **+5.978 ns** | **0.000** | +0.250 ns | 0.000 | 12,325 / 41,910 (29 %) | 6,291 | 584 s | `b9599cd271b20c05…` |

**The two draws agree to the digit on Fmax, slack, TNS, ALMs and registers**,
from a clean `db` each time, on the same 88-file input manifest
`632c8c20dd811c90…`.  (The two `reports` hashes differ — `769df59baf4ed8ba…`
vs `f127556617da7b98…` — because the reports carry their own timestamps.)

`E2_zero_errors` PASS on both — 0 stage errors, 0 error lines, map/fit/asm all
Successful, **0 latches, 0 `lpm_divide`**.

**Two draws is not a distribution**, and `standing_gates.md` §A still says the
same tree has drawn 19.42 and 45.91 MHz.  What two identical draws DO establish
here is the negative: the cone that produced the family's 15.3/15.3 pair is
gone, and it is gone in both draws.

### §7.1  THE REFUTATION CONDITIONS — NONE MET

1. *"Fmax < 32 MHz"* — **39.57**, against a 32.0 MHz bar.  **Not met.**
2. *"non-zero setup or hold TNS"* — **0.000 on every domain, both directions**;
   recovery and removal 0.000; 0 illegal paths.  **Not met.**
3. *"any failing path launching from `system_large|c_ready_q`"* — **the string
   `c_ready_q` occurs ZERO times in the entire `.sta.rpt`, on BOTH draws**, and
   there is no failing set for it to be in.  **Not met.**

### §7.2  MISS #1 — THE ALM BUDGET, REPORTED AS A MISS

Registered: **11,917 + 0…120**, i.e. ≤ 12,037.  Measured: **12,325**, which is
**+408** over the registered baseline and **+330** over the RED full family's
11,995.  **THIS IS A MISS AND IS NOT EXPLAINED AWAY.**

Two things are recorded beside it because they were recorded BEFORE the run, not
invented after:

* the 11,917 baseline was **quoted from `ghost8f_prereg_2026-08-09.md`, not
  re-measured this sitting** — the pre-registration says so in its own baseline
  table, because the output directory then held the RED family's build.
* `ucore_provenance.md` §74.4 / §74.4a records that Quartus Analysis & Synthesis
  is **not reproducible run to run, and that the REGISTER counts are while the
  COMBINATIONAL counts are not**.  ALMs are a combinational-inclusive figure.

Neither observation makes the clause met.  A budget that is checked against a
number nobody re-measured is a weak clause, and the correct repair is to
re-measure the baseline ALM figure on a clean `db` before quoting an ALM budget
again — **booked, not done here**, because doing it now would be choosing the
comparison after seeing the result.

### §7.3  MISS #2 — THE Fmax BAND, REPORTED AS A MISS

Registered: **≥ 38 MHz** (the bar, MET at 39.57) with an **expected band of
41–42 MHz**.  Measured **39.57**, so the band is missed on the low side.

Against the baseline on **byte-identical RTL** — 41.80 MHz, two draws to the
digit — **the read costs 2.23 MHz.**  The registered arithmetic, from the
relanding spike, was **~0.4 MHz**.  **The spike under-estimated the read's own
cost by roughly five-fold**, and that is a finding about the spike's method
(it measured the read by REMOVAL from a tree that was already collapsing at
15.56 MHz, where a 2 MHz cone is invisible), not about this landing.

It is worth exactly what it is: the read is **not** timing-free, it costs about
five per cent of the margin, and it still closes with **+5.978 ns** of slack
against a 31.25 ns period.

---

## §8  THE VERDICT AGAINST EACH REGISTERED PREDICTION

| | prediction | verdict |
|---|---|---|
| **SSA** | `0x8C` / 101 / 122 / 224 / `0x8CE0`, census 212, `0x176` fills, `0x17A-D` vacant, hole term removed, one bump | **MET, to the digit** |
| **`r7_lint`** | PASS, no new exception, 20 nets, 1 carrier, 51 `stop` sites | **MET, to the digit** |
| **`check_core 8F.0`** | 500/500 MUST HOLD | **MET** |
| **`INT.F3AA`** | 165/200 | **MET** |
| **`check_core all`** | 168,965 | **MET** |
| **`ulockstep 8F.0`** | 45/50, `ad_data,ps,ad_addr` | **MET** |
| **`ulockstep all`** | 17,340, all five losses inside `8F.0` | **MET** |
| **HLT sweeps** | 279/283 | **MET** |
| **fz2 offline** | lint PASS, bars 8/11, classify/accept PASS | **MET** |
| **F1–F5 (fuzz)** | see §5 | **ALL FIVE MET** |
| **G6 verdict** | PASS on both draws, no refutation condition | **MET** |
| **G6 ALMs** | 11,917 + 0…120 | **MISSED — 12,325 (§7.2)** |
| **G6 Fmax band** | ≥ 38, band 41–42 | **bar MET at 39.57; BAND MISSED (§7.3)** |

**Thirteen clauses: eleven met, two missed, and neither miss is a refutation
condition.**

---

## §9  THE BOOKING — THE FEED AND THE HOLD ARE **UNLANDABLE-AS-DESIGNED**

This is the durable ledger entry the disposition owes.  It is written into the
RTL and the lint as well as here, so it cannot be lost with a document:

* `hdl/rtl/ucore/v30u_ss_pkg.sv`, at the reserved codes `0x17A`–`0x17D`
* `hdl/rtl/ucore/v30u_eu.sv`, at the ghost block
* `hdl/rtl/ucore/v30u_biu.sv`, at the absent fourth rail `eu_rd_wait`
* `sw/ss_lint.py`, in the version-history comment

### §9.1  THE 8F GHOST FEED — `ghost_rd_feed`, `ghost_rd_ready`, `eu_rd_wait`,
### `eu_ghost_preview`, the `S_PRERD` `ghost_preread_*` arms.  SSA `0x17A`–`0x17B`.

**STATUS: UNLANDABLE-AS-DESIGNED.  NOT rejected, and NOT refuted as a
mechanism.**

**The block, characterised.**  Measured, two draws, `ghost8f_results_2026-08-09.md`
§9: **15.3 MHz** against a 32 MHz bar, worst setup **−34.094 ns**, TNS
**−10,443.096**, with **all twelve** worst setup paths launching from
`system_large|c_ready_q` and landing on `v30u_eu|opc_base[4]`.  The netlist route
is retained at `sw/testdata/relanding/ghost8f_worst_paths.rpt`:

    c_ready_q -> u_biu|eu_rd_edge -> u_eu|ghost_preread_epop -> q_demand
              -> rd_done_cnt_n -> rdq0_n -> opr_n -> v1 -> ... -> opc_base[4]

**Why it is a DESIGN block and not a fitting accident.**  §73 admitted
`eu_rd_edge` as the ONE live-READY carrier *"only because its single consumer is
the `psw` register's own `D` pin … NOT the head of the loader chain"*.  The feed
gives it a SECOND consumer and that consumer IS the loader chain.  No re-timing
removes it, because the mechanism's whole content is *"the successor pops at the
data edge"* and READY at clock *c* is not knowable before clock *c*.
**`r7_lint` PASSES on the feed's treated form and is right to** — the route is
through register `D` pins, outside its `stop` charter.  A structural lint cannot
be the falsifier here; only Quartus can.

**What would re-open it, stated so a future campaign does not have to
re-derive it.**  (a) A fabric with enough margin to absorb a 55–63-level
single-cycle cone — the same tree has drawn 19.42 and 45.91 MHz, so the
distribution matters.  (b) **A REFORMULATION in which the successor's pop does
not ride the data edge** — a feed that fires one clock later is a different
mechanism and must be measured as one, against silicon, on its own
pre-registration.  (c) Evidence that it buys something: **§5 of this document is
the first measurement of that question and the answer is currently NOTHING** on
the 623-seed population, so a re-opening should carry a population on which the
feed's benefit is separable from the read's.

### §9.2  THE PF_LOST MODR/M HOLD — `opc_rm_valid`, `opc_rm_byte`, `ghost_rm_pop`,
### the `S_MODRM` restructure.  SSA `0x17C`–`0x17D`.

**STATUS: UNLANDABLE-AS-DESIGNED, and DEAD BY CONSTRUCTION WITHOUT §9.1.**

Re-verified against the artifact this sitting rather than recalled:
`opc_rm_valid_n = 1'b1` has **exactly one setter**, inside `if (ghost_rm_pop)`,
and `ghost_rm_pop = ghost_rd_ready && …`.  With the feed absent the arm can
never be set, so landing it would add two save-state addresses and one decoder
latch that no execution can reach.

**It re-opens if and only if §9.1 re-opens**, and it should be re-derived from
`5403671558` at that time rather than resurrected from this record.

### §9.3  THE CAMPAIGN CLOSES AT **17 OF 19**

L1 (`7647e604e0`) landed 16.  This sitting lands the 17th.  Two are booked
above, with the block characterised and the mechanism not condemned.

---

## §10  BOOKED, NOT DONE — and one instrument note against myself

### §10.1  `fz2_w1 bars` is engine-independent, and that is how it was checked

The registered clause was *"every `measured` byte-identical to baseline"*.  It
was checked LITERALLY: re-running `fz2_w1 bars` rewrote
`sw/testdata/fz2/fz2_bars.json` with **a one-line diff, the `ts` field**, and
nothing else.  That IS the byte-identity proof, and the file was restored so the
landing commit does not carry a timestamp churn.  Separately,
`grep -n 'check_core\|Vtb_v30_core\|--core' sw/fz2_w1.py` returns only prose
comments, so the tool never invokes an RTL core and the identity is structural,
not lucky.

### §10.2  AN INSTRUMENT ERROR I MADE, RECORDED BECAUSE IT LOOKED LIKE A RESULT

The first HLT-sweep run scored **97 · 0 · 0 · 0 = 97/283**, with all three
failures showing `(1, 'seg')` — which reads exactly like a catastrophic
regression.  It was not.  `check_core --suite-dir` takes `--waits` and
**defaults to 0**; the w1/w2/w3 suites need `--waits 1/2/3`.  With the waits
matched the sweeps are **97 · 93 · 45 · 44 = 279/283**, the registered figure.
Recorded so the next agent does not spend the same twenty minutes, and because a
mis-invoked instrument that produces a plausible catastrophe is exactly the
class this repo keeps a ledger for.

### §10.3  STILL BOOKED FROM THE PREVIOUS SITTING, AND NOT FIXED HERE

* **`docs/notes/standing_gates.md`'s save-state row is now stale by THREE
  landings.**  Line 295 still reads *"219 addresses, 205 flops, `SS_VERSION`
  0x87"*; the tree is `0x8C` / 224 / 212.  Named rather than edited, on the
  previous sitting's own precedent — the file is the authoritative standing list
  and rewriting a cell of it is coordinator territory.
* **`sim/` still does not implement the 8F ghost family.**  While that is true,
  `ulockstep --golden 8F.0` scores 45/50 BY CONSTRUCTION and no ucore/model
  head-to-head on `8F.0` means anything.  The model leg is a separate landing.
* **FOUR standing ratchets in `CLAUDE.md` cannot run on this branch**
  (`timed_scenario`, `timed_ins_replay`, `timed_wvec_gate`,
  `timed_enter_replay`) — they die in `image_of(seed)` on
  `gen_seq._v1_anchor_stop` because fuzz-v2 moved the image anchor and their
  goldens are frozen at the v1 one.  Engine-independent; they fail identically
  on the baseline.  Unchanged by this landing.
* **The scored fuzz column is 14 seeds wide.**  A benefit measurement with a
  denominator of 14 is the best instrument the branch has; rebuilding a
  replayable corpus is SUP-1's open item.
* **The ALM baseline should be re-measured on a clean `db`** before any future
  pre-registration quotes an ALM budget (§7.2).

---

## §11  EXTRA DILIGENCE, not on the gate list

Run on the landed tree (receipt `84c6c45192f83d16…`), all green:

* `check_boot.py --core ucore` — **MATCH over 220 rows**
* `check_boot.py --core ucore --timed 400` — **MATCH over 400 rows**
* `check_core --core ucore --opcodes 8F.0 --ss-sweep --ss-mode 5` — the
  round-trip width sweep that walks every address in the map, on the form that
  reaches the mechanism: **500/500, `first-diverging-k = none` on all 500
  indices.**  This is what exercises the newly-occupied `0x176` and the
  `ss_addr_of` hole removal end to end.
