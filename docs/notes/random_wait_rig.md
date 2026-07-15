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
