# THE 8F GHOST **READ**, ALONE — PRE-REGISTRATION, committed BEFORE the RTL

Branch `fuzz-v2-on-relanding`, base `751735d73f`.  Offline: no board, no flash.
Quartus IS in scope; **G6 decides the outcome**.

The previous sitting measured the WHOLE 8F ghost family (read + feed + hold) and
did **not** land it: G6 RED at 15.3 MHz on both draws, every worst path
launching from `system_large|c_ready_q`
(`docs/notes/ghost8f_results_2026-08-09.md`, commit `751735d73f`).  Its §9.3
named the next experiment and refused to assume its result:

> **NOT ESTABLISHED, and NOT ATTEMPTED**: whether a read-only landing (ghost
> READ + rails, no feed, no hold) closes timing.  […] it needs its own
> pre-registration and its own G6.  Nothing in this sitting licenses assuming
> it passes.

This is that pre-registration.

---

## §0  STANDING DESIGN PRINCIPLE (verbatim)

> SIMPLICITY: this is 80's era hardware — nothing on the die is wasted.
> Complex or confusing observed behavior is likely simple systems interacting
> in ways not yet understood.  A large fitted table, a many-cased rule, or a
> per-opcode special case is a signal of misunderstanding, not a deliverable.

---

## §1  TWO CORRECTIONS TO THE BRIEF, MADE BEFORE ANY WORK

**(1a) The brief asks which mechanism the results doc ATTRIBUTED
`fz2e/521006`'s 3358 → 0 to.  It attributes it to NEITHER.**  Verified against
the artifact: `ghost8f_results_2026-08-09.md` §3 is an **A → C** table — no-ghost
baseline against the whole treated family — and it contains exactly one
per-mechanism attribution sentence in the entire document, and it is about a
DIFFERENT figure:

> **`BOUND WARNINGS` 2 → 0.** […] That is the ghost's own bookkeeping: the
> discard token is what keeps an unmatched tail completion out of `rdq`.

The discard token IS the read.  So the doc attributes `BOUND WARNINGS` to the
read and attributes **nothing at all** to any mechanism for `fz2e/521006` or
for `fz2c/406000`.  The attribution the brief asks for therefore has to be
DERIVED and REGISTERED here, not looked up — §5 does that from the baseline's
own divergence signatures, which are measurable without the change.

**(1b) `sim/` does not implement this family** — established last sitting and
re-verified: `grep -n ghost sim/*.h sim/*.cpp` returns prose comments only.
The behavioural reference is the SILICON goldens (`check_core`), and
`ulockstep` is an RTL-vs-model comparison in which the model is the one MISSING
the mechanism.  §6 registers what that means numerically **before** it is
measured.

---

## §2  THE BASELINE, RE-MEASURED THIS SITTING

RTL at `751735d73f` is **byte-identical** to the previous sitting's column A and
to the last PASSING Quartus tree on this branch.  Proved two ways, not recalled:

* `git diff a22f9b02fd HEAD -- hdl/rtl/ucore/ hdl/nec_test*.qsf hdl/nec_test.sdc`
  is **empty**.
* The rebuilt Verilator binary receipt `2b448eecda7c97ac…` has `inputs`
  **equal, key for key**, to the previous sitting's column-A receipt
  `ad20d79bfcfa8771…`; only the `git` provenance differs (`4d5d007c5a-dirty`
  → `751735d73f`, clean).

| baseline figure | value | where from |
|---|---|---|
| `ss_lint --core ucore` | PASS `0x8B` / 101 / 121 / 223 / `0x8BDF` | measured this sitting |
| `ss_flopcensus` | PASS **211** flops, 0 UNMAPPED | measured this sitting |
| `r7_lint` | **PASS** — 17 BIU→EU nets, 1 declared carrier, 3 tainted, **51** `stop` sites, 0 violations | measured this sitting |
| `timed_fuzz --bank fz2c,fz2e --evt-replay --core ucore` | REG **8/11**, EVT **3/3**, **COMBINED 11/14**, SCORED 14, `BOUND WARNINGS` **2** | measured this sitting |
| G6 CONTROL | **PASS 41.80 MHz**, worst setup **+7.325 ns**, setup+hold TNS **0.000**, two draws to the digit | receipts `b6a76f1acdb06a35…` / `7d6c5da3b1d1d92b…` |
| ALMs at that build | **11,917** | quoted from `ghost8f_prereg_2026-08-09.md`; NOT re-measured (the output dir now holds the RED family build at 11,995) |

---

## §3  WHAT IS LANDED — THE EXTRACTION RULE, STATED SO A REVIEWER CAN CHECK IT
## BY GREP

The starting material is the retained `sw/testdata/relanding/ghost8f_landing.patch`
(column C, the §73-treated full family; verified to still `git apply --check`
clean at `751735d73f`), cross-read against `git show 5403671558`.

**THE RULE, and it is mechanical:** a construct is DROPPED iff it references any
of

    ghost_rd_feed   ghost_rd_ready   opc_rm_valid   opc_rm_byte
    eu_rd_wait      eu_ghost_preview eu_rd_edge

— i.e. the feed's two flops, the hold's two flops, the feed's two BIU rails, and
**the live READY pin's one declared carrier**.  Everything else is KEPT.

### §3.1  KEPT — the read and its rails

| construct | what it is |
|---|---|
| `ghost_rd_discard` (+ `_r`/`_n`/flop/reset) | the read's ONE flop; SSA `0x176` |
| `eu_ghost_full`, `eu_ghost_idle`, `eu_ghost_stack_first` | the three published BIU rails, **on `r_ready_prev`** (P2a) |
| `ghost_read_stale_alu` | the select — the mod3 8F POP's discarded stack read |
| `ghost_uses_ea`, `ghost_ea_off`, `ghost_off`, `ghost_prev_pla`, `ghost_uses_mul_hi`, `ghost_next_pla`, `ghost_next_byte`, `ghost_relax`, `ghost_bus_off` | the stale address, off the already-landed `ea_residue` |
| `acc_off` / `acc_phys_base` / `ghost_stack_phys` / `acc_phys` / `acc_phys2` / `acc_split` ghost terms | where the stale address reaches the bus |
| `acc_off_nog` / `acc_phys_nog` / `acc_split_wr` (P2b) | the write accounting's ghost-free split |
| `ghost_lost_io` | the successor's bus-space select (`bs IOR!=MEMR`) |
| `ghost_preread_tail` → `pr_seg2` / `eu_seg2` / `eu_word` | the stale word-lane and segment rails overlaying the successor pre-read |
| `ghost_edge_pair` → `opr_now` | the write-pairing collision (reads `eu_rd_edge_d`, which `r7_lint` classes **register-only**, not the pin) |
| the completion **discard** (§3.3) | the unmatched tail completion is dropped |

### §3.2  NOT LANDED — feed, hold, and every live-pin route

`ghost_rd_feed`, `ghost_rd_ready`, `eu_rd_wait`, `eu_ghost_preview` (and its
four BIU consumers: `bs`, `ad_o`, `ad_oe_data`, the run-restart arm),
`ghost_row_tail`, `ghost_preread_epop`, `ghost_preread_edge_lag`,
`ghost_preread_late`, the whole `S_PRERD` restructure, the `eu_post_hold`
addition, the `S_ROW` `e_f` feed-clear, `ghost_rm_pop`, `opc_rm_valid`,
`opc_rm_byte`, the `S_MODRM` restructure, `q_demand`'s two ghost terms and
`q_first`'s one.

**`S_PRERD` and `S_MODRM` are therefore left EXACTLY as `751735d73f` has them.**
That is the point of the experiment: the previous sitting's refutation route was

    c_ready_q -> eu_rd_edge -> ghost_preread_epop -> q_demand -> rd_done_cnt_n
              -> rdq0_n -> opr_n -> v1 -> … -> st_n -> opc_base[4]

and its FIRST hop after the pin, `ghost_preread_epop`, is a feed construct.  With
the feed absent **`eu_rd_edge` has no ghost consumer at all**, so the read
answers the brief's open question by construction: *it does not need the live
READY pin.*  This is derived from the RTL, not assumed —
`grep -n '^+.*eu_rd_edge' ghost8f_landing.patch` gives five sites and all five
are `ghost_preread_*` (three) or the treatment comment (two).

**The HOLD is provably dead without the feed** and is re-verified rather than
recalled: `opc_rm_valid_n = 1'b1` has exactly ONE setter, inside
`if (ghost_rm_pop)`, and `ghost_rm_pop = ghost_rd_ready && …`.

### §3.3  THE ONE PLACE THE MECHANISM HAD TO BE RE-DERIVED, NOT COPIED

The full family's completion block is a five-way `if`/`else if` chain whose
branches exist to hand the token and the maturity bit to the FEED.  With the
feed gone, four of the five collapse and what is left is **one predicate**:

```
if (rd_pending_n != 2'd0) rd_pending_n = rd_pending_n - 2'd1;
if (ghost_rd_discard_n && (rd_pending_n == 2'd0)) ghost_rd_discard_n = 1'b0;
else begin <the ordinary completion store, unchanged> end
```

`rd_pending_n == 2'd0` after the decrement is the definition of an **unmatched
tail**: a completion arriving with no read left outstanding.  The bus has no
result tags and returns words in order, so every earlier completion in the chain
is delivered to the previous requester — the **one-place displacement** — and
only the last one has nobody waiting for it.

This is not a re-invention.  It is what L1 wrote into `v30u_ss_pkg.sv` when it
RESERVED `0x176`, in as many words: *"the bit follows the resulting one-place
displacement through an overlapping read chain so the unmatched tail completion
is dropped."*  One flop, one predicate, no counter, no table.

**REGISTERED AS A KNOWN DIFFERENCE FROM COLUMN C, not discovered after:** in the
full family the token is released EARLY in the `ghost_preread_tail` /
`ghost_row_tail` branches, so it can be held for fewer clocks there than here.
Because `ghost_preread_tail` gates `pr_seg2` and `eu_word`, the read-only form
can assert those overlays on clocks column C did not.  If that costs a seed it
is a FINDING and is reported as one; it is not patched.

---

## §4  THE SAVE-STATE MAP — PRE-REGISTERED TO THE DIGIT

| | baseline | after |
|---|---|---|
| `SS_VERSION` | `0x8B` | **`0x8C`** |
| `SS_BIU_COUNT` | 101 | **101** (unchanged) |
| `SS_EU_COUNT` | 121 | **122** |
| `SS_COUNT` | 223 | **224** |
| `SS_TAG` | `0x8BDF` | **`0x8CE0`** = `(0x8C << 8) | 224` |
| `ss_flopcensus` | 211 | **212** |

`0x176` fills with `SSA_E_GHOST_DISCARD` — **the occupant it was reserved for,
by name, in this tree's own `v30u_ss_pkg.sv`**.  `0x17A`–`0x17D` stay VACANT and
stay reserved in prose for the feed (`0x17A`–`0x17B`) and the ModR/M hold
(`0x17C`–`0x17D`).

**The map rule says an address never means two different things, and a reserved
code taken by its named occupant owes no skip.  What IS needed is four things:**

1. `ss_addr_of`'s EU hole term (`if (a >= 9'h176) a = a + 9'd1;`) is **REMOVED**.
   Nothing is renumbered by its removal: `0x177`–`0x179` sat one step past the
   hole and now sit one step past the occupant, which is the same address.  The
   EU region becomes dense, `0x100`–`0x179`, 122 symbols; the BIU's `0x038`
   becomes the map's ONLY hole.
2. **Exactly ONE version bump** — one appended group, one bump.  (The full
   family took three, one per group.)
3. The reserved-code COMMENT in `v30u_ss_pkg.sv` becomes a `localparam`, and it
   may only do so now, because `ss_lint` check (1) requires every declared
   `SSA_` symbol to appear **exactly twice** in the RTL and an unoccupied symbol
   fails it — correctly.  The two references are the `ss_read`/`ss_write`
   includes.
4. `sw/ss_lint.py`'s constants table is updated to the five figures above.

**AND ONE PROHIBITION, from the previous sitting's own recorded near-miss:** no
new PROSE may name an `SSA_` symbol anywhere in the RTL.  `ss_lint` counts those
names by text and a symbol named in a comment is a third reference and a FAIL.

**`SS_BIU_COUNT` does not move** because the three published rails are
COMBINATIONAL off the BIU's registered READY, which already has an address.
Zero new flops on the BIU side; the read costs **exactly one flop**, in the EU.

---

## §5  THE FUZZ DELTA — THE ATTRIBUTION, REGISTERED BEFORE IT IS MEASURED

Denominator, unchanged and registered again: the scored column on this branch is
**14 seeds** (623 offered, 609 `OPEN_BUS`).  No percentage of 14 is quoted.

**The evidence the prediction is built from is the BASELINE's own first-
divergence signatures** — available without the change, measured this sitting
from the column-A report.  Of the 25 seeds that moved A → C:

* **24 of 25 have `kind = nxta`** — a next-ADDRESS divergence.  The stale
  address is the READ's, and it is the read's ONLY bus-visible product.
* the 25th, `fz2e/520066`, is `kind = bs`, `bs IOR!=MEMR` — which is
  `ghost_lost_io`, **also in the read set** (§3.1).
* exactly ONE mover has a PHASE-shaped first divergence: `fz2e/521059`,
  `kind = t`, `t T2!=T1 … ps 6!=3`, worth 1,179 of the 25,188 improved rows.
  Phase/cadence is the FEED's shape.

So the registered attribution is: **the READ owns the address; the FEED owns the
cadence.**  From it:

| | prediction | refutation |
|---|---|---|
| **F1** | `BOUND WARNINGS` **2 → 0**.  The two saturating seeds are `fz2e/520000` and `fz2e/522003`; the discard token is the read's and is exactly what keeps the unmatched tail out of `rdq` | either seed still warns ⇒ the doc's own attribution of `BOUND WARNINGS` to the discard is WRONG |
| **F2** | `fz2c/406000` **DIVERGE → EXACT**, so REGISTERED **8/11 → 9/11** and COMBINED **11/14 → 12/14**.  Its baseline divergence is ` nxta ff04!=3f04` at row 212 — an address, and the differing bits are the upper ones `ghost_relax` exists to relax | it stays DIVERGE ⇒ that flip was the feed's, and the read alone buys no scored seed |
| **F3** | of the 25,188 gross improved rows A → C, the read alone retains **≥ 70 %** (≥ 17,632).  The bar is set conservatively BELOW the 95.3 % that first-divergence shape alone would suggest, because a first divergence does not determine a whole row stream | **< 50 %** retained ⇒ the improvement is mostly cadence and the attribution above is refuted |
| **F4** | `fz2e/521006` (3358 → 0 in column C; baseline ` nxta 6db1!=3f06`) comes back at **ndiff ≤ 100** | ≥ 1,000 ⇒ that seed's collapse was the feed's |
| **F5** | **SCORED stays 14** and **no seed leaves the scored column**; the one seed that WORSENED A → C (`fz2e/520005`, +13) may worsen again and that is not a refutation | a seed leaves the scored column |

---

## §6  THE OTHER GATES — WHAT IS PREDICTED, INCLUDING THE ONE THAT MUST FALL

| gate | prediction |
|---|---|
| `gen_ucore_qsf --check` | PASS |
| **`r7_lint`** | **PASS, and with NO new exception.**  20 BIU→EU nets (the three ghost rails append), still **1** declared carrier, still 3 tainted, and the `stop` count unchanged at 51 — the read adds no `stop` site.  **If it cannot pass without an exception, the run STOPS and reports** |
| `ss_lint --core ucore` | PASS at §4's five constants |
| `ss_flopcensus` | PASS **212** |
| `test_artifact` | **45/45** |
| `check_core --core ucore --opcodes 8F.0 --cases 0` | **500/500 — MUST HOLD.**  This is the SILICON bar |
| `check_core --core ucore --opcodes INT.F3AA` | **165/200**, not worse |
| `check_core --core ucore --opcodes all --cases 0` | **168,965/169,000**, not worse |
| **`ulockstep --golden 8F.0 --cases 50`** | **45/50 — a FALL from the baseline's 50/50, and it is the prediction, not a regression.**  See below |
| `ulockstep --golden all --cases 50` | **17,340/17,350**, with all five losses inside `8F.0` and no other form moving a case |
| four HLT sweeps | **279/283** |
| `fz2_w1` lint + bars | PASS 0 hits / 48 rows; 8/11 MET with every `measured` byte-identical to baseline |
| `test_fuzz_classify` / `test_fuzz_accept` | PASS / PASS |

### §6.1  `ulockstep 8F.0` — REGISTERED AS A FALL, WITH ITS SIGNATURE, BEFORE
### IT IS MEASURED

`ulockstep` scores the RTL against `sim/`, and **`sim/` has no 8F ghost family**
(§1b).  The baseline is 50/50 because neither side has the mechanism.  Putting
the read in makes the RTL right and the model unchanged, so the comparison MUST
fall — and the ghost ADDRESS is the read's only bus-visible product, so:

* **PREDICTED: 45/50, with first divergences of the form `ad_data,ps,ad_addr`** —
  the same five cases and the same signature the full family produced, because
  the address is the read's and the full family's other two mechanisms are not
  bus-address mechanisms.
* **A drop matching that signature IS THE MECHANISM BEING PRESENT.**  It is not
  a silicon-match regression, and the control that proves it is
  `check_core --opcodes 8F.0`, which compares against the SILICON goldens and
  must HOLD at 500/500.  The ghost address is a documented don't-care in that
  comparator (`closure_checkpoint.md`, "8F.0 mod3 ghost-read address — RESOLVED
  2026-07-13").
* **`50/50` IS A FAILURE OF THIS EXPERIMENT, NOT A SUCCESS**: it would mean the
  extracted read never fires, i.e. the mechanism is unreachable, and §5's
  benefit measurement would be meaningless.
* **Below 45/50, or 45/50 with a signature that is NOT `ad_addr`-shaped**, is a
  finding: the read is doing something the full family did not.

---

## §7  G6 — THE PREDICTION AND ITS REFUTATION CONDITIONS

CONTROL/DEFAULT build (no `X1_AD_RETENTION`), clean `db`, **TWO DRAWS**,
receipts retained.  Registered arithmetic: the relanding SPIKE (`539c6f8406`)
measured the read's own cost at **~5 ALMs and ~0.4 MHz**, and the previous
sitting established that the FEED, not the read, is what launches from
`c_ready_q`.

**PREDICTED:**

* verdict **PASS on both draws**
* Fmax **≥ 38 MHz**, expected band **41–42 MHz** (baseline 41.80 minus the
  spike's ~0.4)
* worst setup **> 0**, setup **and** hold TNS **0.000** on every domain
* ALMs **11,917 + 0…120**
* **no failing path launching from `system_large|c_ready_q`**

**REFUTED by ANY of:**

1. Fmax **< 32 MHz** on either draw;
2. non-zero setup or hold TNS;
3. **any** failing path launching from `system_large|c_ready_q`.

**AND, per the brief, registered as a MISS-but-not-refutation:** a PASS at
≥ 32 MHz but **materially below the 38 MHz band** is reported AS A MISS, with
the worst-paths report attached, and its meaning is stated in advance —
**the read has its own READY route nobody has found, and that is the finding.**

**ONE DERIVATION, ONE LANDING, TWO DRAWS.  There is no iterate-to-green leg in
this plan**, and if G6 comes back RED the disposition is §8's second column, not
another RTL edit.

---

## §8  THE DISPOSITION, REGISTERED IN ADVANCE FOR BOTH OUTCOMES

| | G6 PASS | G6 RED |
|---|---|---|
| the READ | LANDED | not landed; retained as a patch beside the family's |
| the FEED | **booked UNLANDABLE-AS-DESIGNED** | booked UNLANDABLE-AS-DESIGNED |
| the HOLD | **booked UNLANDABLE-AS-DESIGNED** (dead without the feed) | booked UNLANDABLE-AS-DESIGNED |
| the re-landing campaign | closes at **17 of 19**, two booked | closes at **16 of 19**, three booked |

**"UNLANDABLE-AS-DESIGNED" is not "rejected".**  The ledger entry must carry the
timing evidence (`ghost8f_results_2026-08-09.md` §9 + `ghost8f_worst_paths.rpt`)
and must be phrased so a future campaign with a faster fabric, or with the
mechanism REFORMULATED so the successor's pop does not ride the data edge, can
re-open it on its own evidence.  The block is characterised, not the mechanism
condemned: §3 of the results doc measured the family as real, reachable and
worth having.

---

## §9  GATE ORDER — CHEAPEST FALSIFIER FIRST, STOP AT THE FIRST RED

```
 1. gen_ucore_qsf --check
 2. r7_lint                     PASS, no new exceptions -- else STOP
 3. check_core --build --core ucore
 4. ss_lint --core ucore        against §4
 5. test_artifact               45/45
 6. check_core 8F.0 -> 500/500 MUST HOLD ; INT.F3AA -> 165/200
 7. ulockstep --golden 8F.0 --cases 50   -> against §6.1
 8. check_core --opcodes all --cases 0   -> 168,965 ; ulockstep --golden all
 9. the four HLT sweeps                  -> 279/283
10. fz2 offline legs
11. the fuzz delta               -> against §5
12. G6, TWO draws, receipts retained
```
