# V30 test harness FPGA core

MiSTer-template Quartus project (DE10-Nano / Cyclone V) that drives a real
NEC V30 (μPD70116C-8) in maximum mode, simulates its memory, and captures its
bus behavior cycle-by-cycle. See `docs/facts/pins_timing.md` for the
electrical constraints this design is built around.

## Module structure

```
sys_top (MiSTer framework, sys/)
 └── emu (nec_test.sv)
      └── system_large (rtl/system_large.sv)  - harness top
           ├── nec_bus     (rtl/nec_bus.sv)     - CPU clock/reset, T-state
           │                                      tracker, AD drive, READY/
           │                                      wait states, capture records
           ├── test_mem    (rtl/test_mem.sv)    - 64 KB BRAM, byte lanes,
           │                                      mirrored across 1 MB
           └── capture_buf (rtl/capture_buf.sv) - 4096 x 64-bit trace ring
```

Static configuration (in `system_large.sv`, until the HPS bridge exists):
CPU clock = 32 MHz / 8 = **4 MHz**, zero wait states, INTA vector FFh.

Hardware constraints encoded in `nec_bus`:
- μPD70116C-8 clock must stay within 2–8 MHz (not static) — free-running only.
- `AD[19:16]` are input-only at the FPGA (fixed-direction shifters on the
  adapter; they carry CPU segment status PS3–PS0 during T2–T4). Only
  `AD[15:0]` are driven, via `NEC_AD_DIR`.
- CPU outputs are sampled twice per CPU clock: address-phase signals at the
  falling CLK edge, data-phase signals at the end of the cycle.

## Capture record format (64 bits, one per CPU clock)

| Bits  | Field |
|-------|-------|
| 19:0  | AD, address-phase sample (falling CLK edge) |
| 35:20 | AD[15:0], data-phase sample (end of cycle) |
| 39:36 | A19–A16 / PS3–PS0, data-phase sample |
| 42:40 | BS0–BS2, address phase |
| 45:43 | BS0–BS2, end of cycle |
| 47:46 | QS0–QS1 point sample (large mode) / {INTAK̅ not-seen-low, ASTB seen-high} sticky (small mode) |
| 48    | RD_N: point sample (large) / not-seen-low sticky (small) |
| 49    | UBE_N (address phase) |
| 50    | BUSLOCK_N point sample (large) / WR_N not-seen-low sticky (small) |
| 51    | READY as driven |
| 52    | INT as driven |
| 53    | NMI as driven |
| 54    | POLL_N as driven |
| 55    | RESET as driven |
| 58:56 | T-state (0=TI 1=T1 2=T2 3=T3 4=TW 5=T4) |
| 63:59 | reserved |

The buffer arms when the CPU leaves reset and stops when full (4096 cycles
= ~1 ms at 4 MHz), so reset release and first fetch are always in the trace.

## JTAG readout (no IO board / HPS bridge required)

All three RAMs are runtime-modifiable over the same JTAG cable used for
programming (In-System Memory Content Editor):

| Instance ID | Contents |
|---|---|
| `CAPT` | capture buffer, 4096 x 64 |
| `ME0`  | test memory, even byte lane, 32768 x 8 |
| `ME1`  | test memory, odd byte lane, 32768 x 8 |

- Dump a trace: `quartus_stp -t sw/dump_capture.tcl capture.hex`, then
  `python3 sw/decode_capture.py capture.hex -n 100`
- Load a test program without recompiling: write `ME0`/`ME1` from the
  In-System Memory Content Editor (GUI or `write_content_to_memory` in a
  quartus_stp Tcl script), then re-arm by resetting the core.

`LED_USER` carries the capture-full flag but is not observable without a
MiSTer IO board.

## Boot image

`rtl/boot_even.hex` / `rtl/boot_odd.hex` hold the 64 KB memory image
(even/odd byte lanes). Regenerate with `python3 sw/make_boot.py`. The
bring-up program far-jumps from the reset vector to 0000:0100 and loops
through a word write, byte read, and odd-address word read.

## Build / simulate

- `make` — Quartus compile (`output_files/nec_test.sof`)
- `make run` — program the FPGA over JTAG
- Simulation smoke test (bus-functional V30 model, no real CPU needed):
  ```
  verilator --binary --timing -Wno-fatal --top-module tb_harness \
    hdl/tb/tb_harness.sv hdl/rtl/nec_bus.sv hdl/rtl/test_mem.sv \
    hdl/rtl/capture_buf.sv -o tb_harness -Mdir obj_dir
  ./obj_dir/tb_harness    # run from the repo root (hex paths)
  ```

## Not yet implemented

- HPS/Avalon bridge (host control of config, memory load, capture drain)
- SDC constraints for the NEC pins (sampling margins analyzed but not
  constrained; see pins_timing.md)
- DDRAM trace spill for captures longer than 4096 cycles
