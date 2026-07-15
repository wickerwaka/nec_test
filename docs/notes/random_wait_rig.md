# Random per-access wait-state rig (Phase 1 of the cycle-accuracy campaign)

Goal: a fuzz rig that inserts a RANDOM number of wait states per bus access,
applied IDENTICALLY to the socketed chip and the fabric core, so a
chip-vs-fabric (and chip-vs-TB) comparison is valid cycle-for-cycle under
aperiodic waits. This is the measurement foundation for characterizing (and
eventually closing) the waits>=1 core-vs-chip cadence drift.

## The shared seeded generator (identical-sequence guarantee)

The SAME algorithm is implemented byte-for-byte in two places:

- `hdl/rtl/nec_bus.sv` — drives NEC_READY for whichever A/B position is
  selected (chip when cfg_use_core=0, fabric core when =1). One nec_bus
  instance serves both, so both positions get the identical READY sequence.
- `hdl/tb/tb_v30_core.sv` — mirrors it for the Verilator chip-vs-TB path.

Algorithm (keep the two copies in sync):

- 16-bit Galois LFSR, poly 0xB400 (maximal length, period 65535).
    `next = {1'b0, l[15:1]} ^ (l[0] ? 16'hB400 : 0)`
- Seeded at reset from the seed register/plusarg; a 0 seed is substituted by
  0xACE1 (an all-zero LFSR would lock).
- Advanced EXACTLY ONCE per bus cycle, at T1 entry (`next_t_state==ST_T1` /
  `tb_t_next==ST_T1`) — the same point the uniform path loads wait_cnt.
- Per-access Tw count is a bounded reduction of the LFSR low byte:
    `n = (l[7:0] * (wmax+1)) >> 8`   (range 0..wmax, ~uniform; verified 0 and
    wmax both hit, near-flat buckets for wmax=1,3,5,7,15).

Why the sequence is identical chip vs core vs TB:
- The LFSR is reset-seeded to the same value at the start of every run
  (harness_reset / nec_reset_q in nec_bus; the reset branch in the TB).
- It advances once per bus cycle, keyed to bus-cycle INDEX, not absolute
  clock. Both positions execute the same program, so the k-th bus cycle is
  the same access and draws the same count — even though the whole point of
  the rig is that the cycle CADENCE around that access may differ. Divergence
  in bus-cycle COUNT is itself the bug under measurement and shows up as a
  cycle divergence at/before that point.

Scope: random waits are applied in LARGE mode only. Every board A/B / fuzz /
waited-golden run forces small=0; small mode keeps the uniform
cfg_wait_states path. The uniform path is completely unchanged when random
mode is off (the default).

## Mode select / registers

New AXI register (hps_axi_slave.sv):

    0x24  WRAND   [0] enable   [7:4] wmax (Tw/access)   [31:16] seed

- enable=0 (reset default): uniform CFG.wait_states path (unchanged golden
  behavior). enable=1: seeded random waits, overriding CFG.wait_states.
- Wired system_large -> nec_bus as cfg_wait_rand / cfg_wmax[3:0] /
  cfg_wseed[15:0].

## Tooling

- `sw/v30ctl.py`: R_WRAND (0x24), `Harness.set_wrand(enable, wmax, seed)`, a
  serve command `WRAND <enable> <wmax> <seed>` ('-' keeps a field), and
  `cfg --wrand/--wmax/--wseed`. For back-compat with a serve that predates
  WRAND, the client emits nothing until random is first requested.
- `sw/v30run.py`: `ServeRunner.wrand(spec)` (spec=None uniform, or
  (wmax, seed)); `run_image(..., wrand=...)` threads it before the run.
- `sw/check_seq.py`: `--wrand SEED --wmax K`. Random pattern applied to BOTH
  A/B positions and the TB. Per fuzz seed k the effective LFSR seed is
  `SEED ^ k` (distinct pattern per program, reproducible); explicit seeds use
  `--wrand` as the literal effective seed, so a div-file entry
  `"wrand": [wmax, seed]` reproduces bit-for-bit. Works with `--hw-ab`
  (chip vs fabric) and the default chip-vs-TB path.

Examples:
- chip-vs-fabric random-wait fuzz:
    `python3 sw/check_seq.py --fuzz 500 --start 20000 --hw-ab --wrand 0x1234 --wmax 3 --exts <strict> --no-cov`
- chip-vs-TB random-wait fuzz:
    `python3 sw/check_seq.py --fuzz 500 --start 20000 --wrand 0x1234 --wmax 3 --exts <strict> --no-cov`
- reproduce a recorded divergence: `--wrand <seed> --wmax <wmax>` on the seed.

## Validation status

- Uniform golden path unchanged: check_core waits=0 169000/169000,
  waits=1 1200/1200 (re-run after the edit).
- TB random generator exercised (sim-only): Tw states inserted, counts in
  0..wmax, different seeds -> different sequences, wmax scales the range.
- Full RTL (system_large + nec_bus + hps_axi_slave + core) lints clean;
  bitstream build for FLASH-READY.

## Phase 2a: explicit wait-vector REPLAY mode (rig enhancement, needs reflash)

Codex's Phase-1 review WITHDREW the old "unbounded aperiodic history" verdict
but flagged the "bounded 5-access local window" conclusion as EXPLORATORY /
CONFOUNDED (LFSR seeds are correlated whole streams, not controlled
interventions; the window included a non-causal forward field; one program;
resume events pooled). Phase 2 must switch to EXPLICIT CONTROLLED INTERVENTIONS.
The enabler is a REPLAY mode: the host specifies the EXACT Tw-per-bus-cycle
sequence, applied identically to chip and core, so two runs are byte-identical
except ONE selected access's wait (a clean impulse).

Design (third wait source; uniform-N and LFSR modes retained):
- `hdl/rtl/wvec_buf.sv` - a 1024x32 (= 4096-byte-entry) dual-port RAM. Host
  writes whole 32-bit words (4 Tw entries) over the HPS bridge at 0x140000;
  nec_bus reads the byte for the current bus-cycle index.
- `nec_bus.sv` - a `bus_idx` counter increments once per bus cycle (at T1,
  same point the LFSR advances) and resets each run. In replay mode
  (`cfg_wait_replay`) the access's Tw = wvec byte[bus_idx]; priority is
  replay > random > uniform. bus_idx keeps replay and LFSR aligned to the same
  access index on chip and core - the identical-sequence guarantee extends to
  replay for free.
- `hps_axi_slave.sv` - new 0x140000 wvec region (carved from the old cap
  region by a[18]; capture base 0x100000 unchanged), WRAND[1] = replay-enable.
- `tb_v30_core.sv` - `+wvec=<hex byte file>` loads the same vector, indexed by
  its own bus-cycle counter; byte-for-byte the same replay algorithm.
- Tooling: `v30ctl.py` load_wvec + serve `WVEC`/`WRAND ... <replay>`;
  `v30run.py` ServeRunner.replay + `run_image(wvec=...)`; `check_seq.run_tb/
  run_chip(wvec=...)`.

TB-validated offline (no board): replay reproduces the LFSR sequence EXACTLY
(182/182 accesses on fz90003), and flipping ONE vector entry yields EXACTLY ONE
differing access (bus-cycle 40, Tw 0->1) - the controlled single-wait impulse.
Golden 169000/169000 held (default path untouched); full harness lints clean.

Phase 2b (post-flash) will use this for impulse-response causal-radius discovery
per the review: narrow per-class resume events, single-wait flips at relative
offsets -1..-K, queue-history orthogonalization, tail-ordinal falsification,
wmax 2..15, pre-decision-only context - stopping analysis at the first bus-
stream divergence (generator-desync guard).

## Phase 1 BASELINE RESULTS (in silicon, flashed 3ddcf00, board root@mister-nec)

Rig proven in hardware (`baseline_wrand.py rigproof`, fz90000 wmax=3): the
per-access (bs, Tw-count) sequence is IDENTICAL chip vs fabric vs TB over all
201 accesses, writes byte-identical. The load-bearing property holds: the same
seed drives the identical random wait pattern to both A/B positions.

Baseline sweep (`baseline_wrand.py sweep`, fz90000-90199 = 200 seeds, base menu,
write-anchored normalized offset, tools = sw/baseline_wrand.py):

| config | |final| med/mean/WORST | peak-excursion worst | fully-cycle-clean | writes |
|---|---|---|---|---|---|
| uniform w1 | 0 / 1.08 / 11 clk | 11 | 102/200 (51%) | 200/200 identical |
| uniform w3 | 2 / 2.00 / 11 clk | 11 | 83/200 (42%) | 200/200 identical |
| random 0..3 (wmax3) | 2 / 1.67 / 8 clk | **15** | 67/200 (34%) | 200/200 identical |
| random 0..7 (wmax7) | 2 / 1.97 / 10 clk | **15** | 64/200 (32%) | 200/200 identical |

- chip-vs-FABRIC == chip-vs-TB EXACTLY in every config and every statistic
  (the fabric core and the Verilator TB are the same RTL; the TB is a faithful
  reflash-free proxy).
- FUNCTIONAL IDENTITY holds under random waits (all 800 runs writes-identical);
  random waits change ONLY timing, never the architectural result.
- Random waits are WORSE than uniform on the honest metrics: peak instantaneous
  excursion 15 clk (vs 11 uniform) and fewer fully-clean seeds (~33% vs ~46%).
  The old "<=7 clk" uniform figure was a 70-seed small-sample; at 200 seeds even
  uniform hits 11, and random hits 15. Per the reframed rules this is a real
  failure surface (not cosmetic), and the random dimension exposes more of it.

## Minimal-pair tractability (Phase 2 tool) - TRACTABLE (sw/minpair_wrand.py)

One program (fz90003), 48 wait-seeds at wmax=1 on the chip; EU data accesses
(MEMR/MEMW) are the stable architectural anchor; resume gap = idle clocks from a
data access T4 to the next CODE-fetch T1.

- The chip's resume gap tracks a BOUNDED LOCAL wait window: grouping runs by the
  5-cycle local Tw context around a resume point, every context group has a
  CONSISTENT gap (identical local window => identical gap, regardless of the
  global pattern). So minimal pairs are ABUNDANT and clean - 48 wait-seeds
  already give full Hamming-1 coverage of the local window. Concrete pairs:
  e.g. ord 10 gap 6->7, ord 21 gap 11->12 as the resume access's own wait flips
  0->1 (delta +1.0, low spread). A minority of resume points (ord 4, 15) need a
  wider window (spread ~2), i.e. predominantly-local with a few longer-memory
  tails.
- `--compare-core` runs the fabric core on the same wait-seeds and LOCALIZES the
  model's error: for fz90003, ordinal 16 diverges in 18/48 wait patterns (chip
  resumes in 1-2 clocks, the model over-delays to 4-5), plus +/-1 errors at ords
  19-24. This is the direct Phase-2 payoff: the random-wait rig pinpoints WHICH
  resume decisions the model gets wrong and under WHICH local wait context - the
  thing the 9 uniform-wait refutations could not isolate.

## Post-flash validation plan (Phase 1 steps 3-4, coordinator-gated flash)

1. Sanity: at wrand seed S, wmax K, dump the chip's captured T-state stream
   and confirm the per-access Tw counts match the LFSR sequence the TB
   produced for the same seed (identical-sequence proof in silicon).
2. Baseline characterization: chip-vs-fabric AND chip-vs-TB random-wait
   divergence over a fuzz span, in TRUE cycle terms (write-anchored, per
   timing_magnitude.py). Compare against the uniform-N <=7-clock baseline;
   random waits are expected to expose larger/more divergence (aperiodic
   history is exactly what breaks the resume model).
3. Minimal-pair assessment: from the random-wait captures, look for two runs
   whose wait patterns differ in exactly ONE inserted wait near a resume
   decision, and watch the resume gap shift — the key Phase 2 tool.
