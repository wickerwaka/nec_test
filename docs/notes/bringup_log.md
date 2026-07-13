# Bring-up log

## 2026-07-11 — first deployment: harness verified, CPU not driving pins

Deployed the phase-3 harness (4 MHz CPU clock, zero wait states, bring-up
boot image) over JTAG and dumped the capture buffer repeatedly.

**Verified working:**
- JTAG programming, In-System Memory readout of all three instances
  (ME0/ME1/CAPT). Boot image read back byte-perfect from ME0.
- Capture pipeline: reset-tail records (RESET=1, READY=1, 33 records) then
  per-cycle records exactly as designed.
- Power-up sequencing added during debug: ENABLE_N asserted at config, ~131 ms
  rail-settle wait, then 32 CPU-clock RESET pulse (nec_bus.sv).

**Problem: every CPU-driven pin (BS, QS, RD_N, UBE_N, BUSLOCK_N, AD) reads
floating-low through the level shifters — before, during, and after reset.**
The V30 never drove anything. The harness FSM chases the floating status
(000 reads as INTA ≠ PASV) in an endless T1→T2→T3→T4 loop; that loop in the
trace is a harness artifact, not CPU activity.

Evidence and eliminations:
- Reset sequencing correct at the FPGA (captured in-trace).
- Float pattern was high-ish (PASV, AD=207FF) ~8 µs after config, all-low by
  131 ms — consistent with residual charge draining from an unpowered rail.
- ENABLE_N polarity test: inverted to 1 → identical float signature. Both
  polarities leave the CPU dead, suggesting the PMOS power switch is not the
  (only) polarity issue, or power isn't the whole story.
- Schematic: ~CHIP_ENABLE gates a P-MOSFET high-side switch on the V30's 5V;
  AD0-15 behind F_AD_DIR transceivers; A16-19 fixed CPU→FPGA.

**Physical measurements (Martin, 2026-07-11):** VDD = 5 V, CLK = 4 MHz,
READY high, RESET low (post-release), CHIP_ENABLE gating works. Chip is
powered, clocked, and reset correctly — yet drives nothing.

## ROOT CAUSE: RQ/AK0 and RQ/AK1 grounded on the PCB

The PCB netlist ties V30 socket pads 30 and 31 to GND. Correct for
small-mode semantics (HLDRQ active-high input, HLDAK output idles low), but
the harness straps LARGE mode, where pins 30/31 are RQ/AK1 and RQ/AK0 —
**active-low bus-hold request inputs. Grounded = permanent hold request.**
Per datasheet p98-99, the CPU acknowledges and floats the address bus,
AD bus, and all control lines — indefinitely. Matches every observation,
including the lone queue-status blip at startup.

**Fix (chip is socketed):** bend pins 30 and 31 out of the socket and pull
each up to 5 V through 10 k. (The 8086 has internal pull-ups on RQ/GT and
the V30 likely inherits them, but the datasheet doesn't confirm it — use
external pull-ups.)

**Alternative validation path (no rework):** drive S/LG high (FPGA pin
NEC_LG_N) to select small mode, where the grounded pins are electrically
correct — but this loses QS0/QS1 queue status, so it is only a stepping
stone. Harness FSM would need a min-mode decode variant (ASTB as address
strobe, IO/M + RD/WR for cycle type).

## 2026-07-11 (later) — SMALL MODE: CPU EXECUTING, full chain verified

Implemented small-scale mode in nec_bus (cfg_small_mode: transparent ASTB
address latch, RD/WR strobe-driven datapath, IO/M low=I/O). NEC_LG_N=1.
Dual-mode verilator TB passes. Deployed to hardware:

**The V30 executes the boot program.** Captured trace (capture8) shows:
- RESET release → pins go from floating to driven-idle ~8 cycles later;
  **first bus cycle ~9 CPU clocks after reset release** (small mode,
  preliminary — sampling offsets not yet calibrated out).
- First fetch at FFFF0h, FPGA BRAM returns 00EA (far jump) — then prefetch
  overshoot: fetches FFFF2/FFFF4/FFFF6 (8 bytes for a 5-byte instruction)
  while the EU decodes.
- Jump lands: next fetch 00100h. Program bytes stream back exactly as
  loaded (34B8, BB12, 2000, 0789, 00A0, A120...).
- MOV [BW],AW executes: MEMW at 02000h, data 1234h, correct byte enables.
- Loop repeats ~35x across the 4096-cycle trace. 4-cycle bus cycles, zero
  wait states throughout.

Known capture artifacts to fix:
- ASTB pulses fall between the two per-cycle sample points → the record's
  QS[0] bit never shows ASTB high. Make it a sticky-OR over the cycle.
  (The transparent address latch works; only the record bit is affected.)
- Pre-drive float reads as "IOR" in the decoder until the CPU starts
  driving (~8 cycles post-release). Cosmetic.
- JTAG bulk reads still occasionally all-zero; dump_capture.tcl now
  retries aggressively (all-zero chunk = provably bogus since READY bit
  is always set in valid records). capture8 = 4096/4096 valid.

**Milestone: full discovery-loop chain works** — assemble program → load
BRAM → power/reset sequence → real V30 executes → per-cycle capture →
JTAG dump → decode. Next: sticky strobe bits, then the RQ/AK rework to
unlock large mode + queue status.

## 2026-07-11 (later) — HPS bridge: ARM lockup incident + hardening

First deployment of the lightweight-bridge harness control locked up the
DE10's ARM hard (network dead, SSH gone): the first /dev/mem access to
0xFF200000 stalled — an unanswered lw-bridge AXI transaction seizes the L3
interconnect and takes the whole SoC down. Likely cause: the AXI slave was
reset by the MiSTer framework reset (hps_io status/buttons), which is
undefined once MiSTer Main is killed — the slave never asserted ready.

Remote recovery attempts, all failed (documenting for next time):
- Reconfiguring the FPGA with an always-responding slave (hoping the fresh
  fabric would complete the pending transaction): no recovery.
- System Console DAP master: Quartus Lite exposes no HPS master service.
- quartus_hps -o I: DAP IDCODE reads, but "Fail to power up the System and
  Debug power" — the seizure blocks the debug power handshake too.
→ **A physical power cycle is the only way back.**

Hardening now in place (sim-verified, awaiting hardware retest):
- hps_axi_slave reset by a local POR pulse only — always responds,
  regardless of framework/MiSTer state.
- host_attached latch: standalone boots use the framework reset as before;
  after the first CTRL write the host owns the harness lifecycle.
- capture_buf reset is POR-only; trace survives host_reset for readout.
- sw/v30ctl.py `prep` puts the bridges into reset BEFORE FPGA
  reconfiguration (run it every time before quartus_pgm).

Safe flow after every boot: killall MiSTer → v30ctl.py prep → make run →
v30ctl.py status.

## 2026-07-11 (evening) — HPS bridge verified: full discovery loop live

After the power cycle, the hardened bridge worked first try (prep →
flash → status, no lockup). Verified end-to-end on hardware:

- `v30ctl.py run boot.bin`: stop → load 64 KB over the bridge → fast
  restart → capture full → dump, in seconds (vs minutes over JTAG).
  Results identical to the JTAG-era captures (8-clk reset latency,
  64-clk boot loop).
- **Full toolchain loop**: a new program assembled with v30asm
  (MOV CW,0AAAAh; MOV BW,3000h; loop: MOV [BW],CW; INC CW; BR loop),
  loaded and run via the bridge — capture shows 161 iterations with the
  write data incrementing aaaa, aaab, aaac... (live execution proof).
  Loop period: **25 CPU clocks** for MOV [BW],CW + INC CW + BR short.

The write-test → run-on-silicon → measure loop is fully operational.
Remaining before suite-grade data: load/store routines (designed,
docs/notes/loadstore_design.md), RQ/AK rework for large mode + queue
status.

## 2026-07-11 (night) — LARGE MODE LIVE: real queue status

RQ/AK0-1 rework done (pins lifted + pulled up). S/LG̅ strap rewired to
follow CFG.small_mode so mode is host-switchable (change only in
host_reset). First max-mode run: BS status + T-states decode cleanly,
QS0/QS1 report real queue ops, queue-depth reconstruction works (peak 5),
442 instruction boundaries visible, per-instruction F-to-F times
{3,5,7,11,12,12,14} sum to the 64-clock loop measured independently on
the bus side. See docs/facts/measurements.md.

One transient: the first large-mode `v30ctl run` invocation hung in
load_mem (>45 s); an identical retry completed in 0.7 s. Unexplained —
watch for recurrence.

Everything is now in place for the decode/prefetch research program and
the load/store implementation (stage 1+2 together, since queue status
is available).

**Tooling notes:**
- `read_content_from_memory` returns content highest-address-first; bulk
  reads intermittently return all-zeros on Quartus 17.1 even with re-read
  verification (single-word reads are reliable). sw/dump_capture.tcl uses
  64-word chunks + retry; treat all-zero regions in dumps with suspicion —
  a genuine record always has the READY bit (51) set.
- A valid capture record can never be 0x0000000000000000.

## 2026-07-13 — Campaign 4 kickoff: in-FPGA A/B integration + safe-flash

### A/B integration architecture (landed, commit 61185d0)
The v30_core is instantiated inside system_large behind a CFG selector so
nec_bus's pin side drives either the socketed chip or the internal core:

- **CFG.use_core (bit 25)** in hps_axi_slave (default 0 = chip). Change
  only under host_reset, like the other CFG fields.
- **nec_bus AD refactor**: the inout `NEC_AD` port became a unidirectional
  trio `ad_drive` / `ad_drive_en` / `ad_sample`. This removes the
  inout<->inout bridge that a naive A/B mux would need (Verilator flagged
  UNOPTFLAT/circular; Quartus would cut the false loop arbitrarily). The
  chip datapath is bit-identical: `ad_sample` = NEC_AD in chip mode, the
  drive is the same registered `rdata_q` under the same `drive_en`.
  tb_harness passes unchanged; largemode_synth.hex regenerates byte-
  identical; the 155440/155500 core golden regression is untouched.
- **system_large mux**: one-directional status pins (BS/QS/RD_N/UBE_N/
  BUSLOCK_N) mux chip<->core with plain 2:1s; the harness read data is
  injected on the core's shared AD net under `ad_drive_en`; nec_bus's
  outputs fan out to both the physical pins and the core; the socketed
  chip is powered off (ENABLE_N) while the core is selected. The core is
  clocked by NEC_CLK (same 4 MHz cadence the chip sees) and held in reset
  unless selected.

### Sim A/B (Mission A) — tb_ab.sv + sw/check_ab_sim.py
tb_ab drives the real integration (system_large) from the AXI master BFM
only and exercises BOTH selector positions. check_ab_sim runs the core
position, drains the harness capture, and diffs it against the real-chip
boot golden (sw/testdata/largemode_boot_real.hex) with check_boot's column
policy.

- **Chip position**: passes (large-mode BFM vector fetch + write/readback).
- **Core position**: the core boots from the in-memory image behind the
  real capture path, but DESYNCS. This is the current gate.

### FINDING — core<->harness commit-phase desync (gates hardware)
Aligned at the first vector fetch, the harness-core trace is identical to
the `+bootimg` replay (which matches the chip, mission G) for cycles 0-5,
including the fetched data words (00ea/0001/9000). Then it diverges: the
core's EU pops the 2nd queue byte one cycle EARLY (at T3 rather than T4),
loses far-jump alignment, and runs off into spurious MEMR/MEMW at 00000
instead of taking JMP FAR 0000:0100.

Ruled out: READY is clean (1 every cycle, no phantom Tw); read data is
correct (right bytes fetched); boot images are byte-identical
(boot_even/odd.hex == boot.bin). Correlated signal: the harness-core
starts its first fetch one NEC_CLK earlier relative to RESET release
(release+8 vs the +bootimg release+9). Since a deterministic FSM with
matching inputs must match, an input differs at a cycle <=5 — the suspects
are the RESET-release phase (NEC_CLK-domain core vs nec_bus sys-clock
release) and the exact edge at which the BIU consumes ad_i.

BIU read-data contract (v30_biu): `fetch_data <= ad_i` (prefetch) and the
`eu_rdata` latch fire at the SINGLE clock edge that ends T3 or the final
Tw, guarded by `ready` sampled high at that edge (t3_done). `ad_i` and
`ready` must both be valid at that NEC_CLK posedge. An idealized TB drives
read data combinationally through T2/T3/Tw and trivially satisfies this;
nec_bus must present the same stability at the core's sampling edge.

Next step before any new-bitstream flash: align the core's RESET-release
phase / read-data presentation so the harness-core matches the golden in
sim (Mission A's own gate), likely aided by exposing the core's
V30_BACKDOOR dbg state through system_large in a debug build to pinpoint
the first EU/BIU state that diverges. Only then flash (Mission C).

### Safe-flash (Mission B) — sw/safe_flash.sh, TESTED
Atomic prep -> quartus_pgm -> status(magic) verify, per-step timeouts.
Tested once with the CURRENT known-good bitstream
(hdl/output_files/nec_test.sof, built 2026-07-12): prep OK, quartus_pgm
"Configuration succeeded", verify OK (MAGIC confirmed, cfg readback
0x01ff0008 = known-good small-mode design, use_core bit reads 0). Board
echo test passed afterward. On an unreachable board after flashing the
script STOPs and demands a physical power cycle (no retry). This is the
ONLY sanctioned path to reprogram the FPGA.

### 2026-07-13 (cont.) — desync root-cause refinement + review items

Refined hypothesis for the core<->harness desync (leading candidate): a
read-data HOLD-margin race at the core's sampling edge. The BIU latches
fetch/read data at the rising CLK edge that ends T3 (t3_done). nec_bus
drives read data under `drive_en`, which it DEASSERTS entering T4 - i.e.
at essentially the same NEC_CLK edge the core samples on. The real chip
samples with its ~65 ns internal output/again-input delay, so it reads the
data mid-T3 with margin; the synchronous core samples AT the T3->T4 edge,
where nec_bus is simultaneously releasing the drive - zero hold margin, a
phase race that resolves per-fetch depending on micro-alignment (explains
why the first fetches read correct bytes but a later one desyncs the queue
pop by one cycle). Fix direction: hold the harness read-data drive to the
core through (past) its T3->T4 sampling edge - i.e. present read data to
the core the way tb_v30_core does (valid across T2/T3 and stably past the
sampling edge), NOT gated to release exactly at T4. This must hold on
hardware too (the FPGA-internal core sampling the harness-driven bus).
Next iteration: implement the core-side read-data hold, re-run
check_ab_sim to green, THEN proceed to Mission C (flash) / D (disp phase
matrix) via the now-plumbed CFG.use_core. A debug build exposing the
core's V30_BACKDOOR dbg_regs through system_large would pinpoint the first
divergent EU/BIU microstate if the hold fix is insufficient.

Review items folded in (commit 2035cce):
- HOST PATH: CFG.use_core (bit 25) now plumbed through v30ctl.py (set_cfg,
  serve CFG 5th field, cfg --use-core, status), v30run.py
  (ServeRunner.cfg + run_image use_core=). Backward compatible; updated
  v30ctl.py scp'd to the board.
- gen_seq CONTAINMENT: forward branches could land inside a safe-gadget
  (DIV / string), skipping trap-safe setup and escaping via the untouched
  IVT (fz101 -> 0x99xxx). Gadgets are now atomic (emit_atomic + branch
  target snap-forward). 120 seeds clean.
- QS-FLICKER: classified as a queue-status display artifact - check_seq
  separates a 1-cycle F<->S QS-only disagreement into a tolerated `flick`
  count (real divergence always shows in the other columns); --strict-qs
  to investigate; the A/B run is the definitive confirmation.

## 2026-07-13 (block 2) — Mission A2/D/E: laws landed, gate satisfied

Mission A2 (hold fix): the core<->harness desync was the predicted
delta-cycle race - the core's derived CLK posedge saw POST-edge values
of nec_bus outputs (zero hold), where the chip sees pre-edge values via
board propagation. Fix = one sys-clock input pipeline on every
nec_bus->core signal (system_large only). check_ab_sim: core boot now
MATCHES the chip golden in-harness (187 rows, loop-aligned). Chip path
bit-identical (tb_harness 25/25, synth hex byte-identical).

Mission D (three laws, all golden-neutral at 155440/155500 exact):
1. disp-reader final-pop defer: fresh queue head (dry last cycle) + pop
   on fetch T2 -> defer 1 (the 2-cycle read shift is mechanical).
   S_DLO polls dry queues every cycle (old 2-grain was aliased).
2. disp16 store ready @ hi-pop+2 (old @+3 was a phase-aliased fit).
3. split word access at offset FFFFh: 2nd byte at offset 0 of the SAME
   segment (found by fz494; real functional bug, was 20-bit linear +1).
Method: sw/sweep_dispphase.py (168-cell matrix: 4 reader + 3 store EA
modes x 3 prefixes x 8 phases) + tb_v30_core +eudbg state dump; three
law iterations to 168/168. All measured chip-vs-TB through serve -
no flash needed; silicon A/B confirmation rides with Mission C.

Mission E: **Campaign 3 exit gate SATISFIED - 500/500 consecutive
clean (fz600-1099), zero flickers.** Expansions: callret 500/500
(fz1100-1599); sregw/popf gating in progress. Cumulative session fuzz:
~2400 board-vs-TB sequences.

Known open (non-gate): waits>=1 qs_e flush-display timing at far jumps
(2 rows/trace, phase-parity; execution identical) - the only class the
w1 matrix shows; reader/store laws are wait-clean.
