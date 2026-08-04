# BIU Cases 55-57: request-age closure and next counterexamples

## Scope and epistemic status

This note records a narrow, prospective result.  It does **not** claim a
complete BIU/EU model.  Case 56 closes one BRK3 first-IVT timing
counterexample; the untouched Case 57 bank immediately exposes three more
discrepancies.

## Case 55: aligned immediate INS read-to-write deadline

The chip-only two-dimensional CODE/read-wait factorials for `fz1317` and the
independent `fz127` control establish an externally visible deadline:

```
first write T1 = max(last immediate-byte QS pop + 44,
                     operand-read completion floor)
```

Both programs and both preparation histories match over the retained wait
cross-products after adding `ie_imm_age` and `ie_r2_late`.  The rule is scoped
to the measured aligned immediate INS off=3/len=4 geometry; it is not evidence
that every INS geometry shares the same constant.

Evidence:

- `sw/case55_ins_qs_deadline_alignment.log`
- `sw/case55_fz1317_code_read_2d_post_{a,b}.log`
- `sw/case55_fz127_code_read_2d_post_{a,b}.log`

## Case 56: BRK3 first-IVT request age

`fz1269` originally launched the first IVT MEMR at chip clock 248 and RTL
clock 250.  Holding the program fixed and sweeping only the final CODE wait
showed that Tw=3 was the sole mismatch.  A predecessor-wait intervention then
separated two outcomes with the same Tw class and queue certificate:

- a BRK3 IVT request that becomes ready on the fetch-completion evaluation
  clock declines that slot and launches at `CODE T4+4`;
- a request already ready for at least one clock owns the direct slot and
  launches at `CODE T4+2`.

The RTL already retains this causal history as `eu_ready_p1`; qualifying the
existing `swint_cc_w3` veto with `!eu_ready_p1` removes the false delay without
adding a seed, ordinal, or wait-history fingerprint.

Prospective evidence:

- `fz1269`, histories A/B, selected CODE waits 0-7 and 15: exact.
- Two independent BRK3 sites in `fz689`, histories A/B, waits 0-7 and 15:
  exact.
- Former discovery bank `fz1220..fz1319`, random wait base `0xd34f`, maximum
  Tw=3: 100/100 exact (previously 98/100).
- Full core suite: 169000/169000.
- Savestate lint: PASS, 88 BIU and 129 EU fields, tag count 218.
- Prefix-clear lint: PASS.

Evidence:

- `sw/case56_fz1269_fetch_factorial_{a,b}.log`
- `sw/case56_fz1269_fetch_post_{a,b}.log`
- `sw/case56_fz1269_predecessor_factorial_{a,b}.log`
- `sw/case56_fz689_controls_post.log`
- `sw/case56_fresh_bank_1220_post.log`
- `sw/case56_check_core.log`
- `sw/case56_ss_lint.log`
- `sw/case56_prefix_clear_lint.log`

## Case 57: untouched-bank counterexample ledger

The fresh `fz1320..fz1419` bank uses a new random-wait base (`0x6b91`) and
scores 97/100.  These are retained contradictions, not exclusions:

1. `fz1320`: the chip's first vector-3 IVT MEMR begins two clocks later than
   the RTL after CODE fetch 148.  The subsequent interrupt sequence remains
   shifted.  This is a software-interrupt scheduling boundary.
2. `fz1336`: chip and Verilator issue the first vector-3 IVT read at the same
   clock and address, but the Verilator harness supplies `0x045e` from
   `0x000c` instead of the loaded `0x0480`, redirecting execution.  A physical
   chip/fabric comparison also diverges, but earlier at the far-transfer stack
   write sequence.  Therefore this seed contains both a real RTL discrepancy
   and a separate TB-memory/capture problem; neither may explain away the
   other.
3. `fz1337`: after CODE fetch 160 the chip chooses another CODE fetch before a
   memory read, while the RTL chooses the memory read first.  Later accesses
   reconverge.  This is a direct CODE-versus-MEMR arbiter decision.

Evidence:

- `sw/case56_fresh_bank_1320.log`
- `sw/case57_fz1320_fz1336_fz1337_context.log`
- `sw/case57_fz1336_hwab.log`

The next discovery order is `fz1336` chip/fabric/TB triangulation first
(because it reveals an independent harness-data defect), then the simpler
`fz1320` IVT launch factorial and `fz1337` CODE/MEMR collision factorial.

## Cases 57-59 resolution

The three retained contradictions above were resolved without seed or ordinal
rules:

1. `fz1336` was a testbench memory-model defect.  The TB's `lat_write` includes
   both MEMW and IOW for bus observation, but the RAM-update block also used
   that combined predicate.  An IOW to port `000c` at CPU clock 337 therefore
   overwrote the vector-3 IVT entry with output data.  Restricting RAM mutation
   to `lat_type == MEMW` eliminates the low-memory write.  Current RTL matches
   the physical chip on `fz1336`; a chip/fabric run after flashing the then
   current source also matched.
2. `fz1320` proves that the BRK3 completion-slot veto depends on a newly-ready
   IVT request, not specifically on Tw3.  Its Tw2 cell becomes ready exactly on
   the completion evaluation and takes the delayed slot; Case56's Tw3 request
   was already ready and takes the direct slot.  `eu_ready_p1` predicts both.
3. `fz1337` reaches the known q2 final-displacement boundary as registered
   `q_cnt=3` plus a same-clock non-fresh QS pop.  Silicon launches retained
   CODE before MEMR.  The rule now uses the semantic post-consumption depth for
   this collision without feeding generic `cnt_next` back through
   `qpop_law_hold` (which would create a combinational loop).

Prospective gates:

- `fz1320` and `fz1337`: histories A/B, waits 0-7 and 15 exact.
- `fz1320..fz1419`: 100/100 (previously 97/100).
- Regression `fz1220..fz1319`: 100/100.
- Full core: 169000/169000.
- Savestate and prefix-clear lints: PASS.
- Fresh `fz1420..fz1519`, wait base `0xa217`: 100/100.

Evidence:

- `sw/case57_fz1336_lowmem_writes.log`
- `sw/case57_fz1336_lowmem_post.log`
- `sw/case57_fz1336_post.log`
- `sw/case58_fz1320_{fetch_factorial,post}_{a,b}.log`
- `sw/case59_fz1337_{factorial,post}_{a,b}.log`
- `sw/case59_fresh_bank_1320_post.log`
- `sw/case59_bank_1220_regression.log`
- `sw/case59_check_core.log`
- `sw/case59_ss_lint.log`
- `sw/case59_prefix_clear_lint.log`
- `sw/case60_fresh_bank_1420.log`

## Case 60 large-bank result and next mechanism

The larger untouched `fz1520..fz2019` bank (wait base `0xc45b`) scores
485/500.  The fifteen contradictions cluster into a smaller set:

- three `CD imm8` first-IVT timing cells (`fz1547`, `fz1807`, `fz1972`);
- several one-clock INS/EXT or memory write-deadline cells;
- several post-write CODE-resume cells;
- a smaller redirect/fetch group.

`fz1547` is the first active Case61 probe.  Its two-history selected-CODE
factorial shows:

- waits 1 and 3-7/15: exact;
- Tw2: chip first IVT T1 is one clock later;
- Tw0 changes the intervening-fetch decision and is a separate collision
  surface, not suitable for folding into the Tw2 correction.

Evidence:

- `sw/case60_fresh_bank_1520_500.log`
- `sw/case60_counterexample_clusters.log`
- `sw/case61_fz1547_{a,b}.log`

The currently flashed FPGA image predates the final Case58/59 source changes.
It must be rebuilt and safely flashed before any further chip/fabric
triangulation; chip-versus-current-Verilator probes remain valid.
