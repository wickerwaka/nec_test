# μPD70116 (V30) Electrical & Timing Facts

Source: **1991 NEC 16-bit V-Series Microprocessor Data Book** (`docs/raw/1991_16_bit_V-Series_Microprocessor_Data_Book.pdf`),
μPD70116/70116H datasheet section = PDF pages 94–125. Text extracted via `pdftotext`; table values below
should be double-checked against the scanned tables before being treated as final (OCR of tables is imperfect).
Extracted 2026-07-10.

## Part variants and clock limits (PDF p94, p101)

| Part | Max clock | Min clock | Note |
|---|---|---|---|
| μPD70116-8 (C8/L8/GC8) | 8 MHz | **2 MHz** (tCYK max = 500 ns) | NOT static |
| μPD70116-10 (C10/L10/GC10) | 10 MHz | **2 MHz** (tCYK max = 500 ns) | NOT static |
| μPD70116H (HC10/HC12/HC16) | 10/12/16 MHz | **DC — fully static** | "no restriction on minimum clock frequency from dc to 16 MHz" (p94) |

**Installed chip: μPD70116C-8** (confirmed by Martin from chip marking, 2026-07-11).
- Standard (non-H) part → **NOT static. Clock must stay within 2–8 MHz at all times; no single-stepping or clock-stretching.**
  All capture must be free-running (answers OPEN_QUESTIONS Q1).
- Clock cycle tCYK: 125–500 ns. The current FPGA harness drives NEC_CLK = 32 MHz/4 = **8 MHz (125 ns)** — exactly at the
  spec minimum cycle time, zero margin. Timing budget below must use the −8 column.

## DC characteristics (PDF p100) — ⚠ two hardware flags

- VDD = +5 V ± 5%.
- Normal inputs: VIH min **2.2 V**, VIL max 0.8 V; **CLK input is special: VKH min = 3.9 V, VKL max = 0.6 V**.
- Outputs: VOH min = 0.7 × VDD ≈ **3.5 V**, up to VDD (5 V CMOS rail-to-rail).
- **Adapter PCB (confirmed by Martin, 2026-07-11): the clock is driven at 5 V and ALL inputs and outputs are level-shifted.**
  Both VKH and 5 V-tolerance concerns are resolved in hardware.
  **Assume a 5 ns propagation delay through the level shifters on every signal, each direction.** Every AC number in this
  file must be budgeted with +5 ns when seen from the FPGA: CPU output delays become (datasheet + 5 ns) at the FPGA pin;
  FPGA-driven setup times need (datasheet + 5 ns) earlier launch. FPGA→CPU→FPGA round trips (e.g. CLK out → QS back) carry 10 ns total.
- Supply: 45–80 mA @ 8 MHz (-8); standby mode 6–12 mA.

## AC characteristics, TA −10..70 °C (PDF p101–102) — values as (−8 part / −10 part)

Clock:
- tCYK (clock cycle): 125–500 / 100–500 ns
- tKKH (CLK high width): ≥44 / ≥41 ns (at VKH = 3.0 V)
- tKKL (CLK low width): ≥60 / ≥49 ns (at VKL = 1.5 V)
- tKR/tKF (CLK rise/fall 1.5↔3.0 V): ≤10 / ≤5 ns

READY (the wait-state control — OPEN_QUESTIONS Q3) — verified against scan p101:
- tSRYLK (READY inactive setup to CLK↓): **−8 / −10 ns** (negative — READY may go inactive up to 8/10 ns *after* the edge)
- tHKRYH (READY inactive hold after CLK↑): 20 / 20 ns
- tSRYHK (READY active setup to CLK↑): tKKL−8 / tKKL−10 ns
- tHKRYL (READY active hold after CLK↑): 20 / 20 ns
- Waveform note (scan p103): wait states insert between T3 and T4 (T1 T2 T3 TW… T4); "READY input level must not be changed during this interval" (the window between the sample points).

CPU reading data (FPGA must meet these when driving AD during reads):
- tSDK (data setup to CLK↓): 20 / 10 ns
- tHKD (data hold after CLK↓): 10 / 10 ns

Interrupt-class inputs:
- tSIK (NMI, INT, POLL setup to CLK↑): 15 / 15 ns

CPU outputs, small-scale (minimum) mode:
- tDKA (address delay from CLK↓): 10–60 / 10–48 ns
- tDKSTH/tDKSTL (ASTB↑/↓ delay from CLK): ≤50–60 / ≤40–55 ns
- tDKRL / tDKRH (RD↓/↑ delay from CLK↓): 10–80 / 10–70(60) ns
- tDKD (data out delay from CLK↓): 10–60 / 10–50 ns
- tWW (WR low width): 2·tCYK−40 / 2·tCYK−35 ns

CPU outputs, large-scale (maximum) mode — the mode our harness uses:
- tDKBL (BS↓ delay from CLK↑): 10–60 / 10–50 ns
- tDKBH (BS↑ delay from CLK↓): 10–65 / 10–50 ns
- tDBST (ASTB delay from BS↓): ≤15 / ≤15 ns
- Address/PS/data delays same class as small-scale (10–60 ns from CLK edge)
- tDKAK (INTAK delay from CLK↓): ≤50 / ≤40 ns
- QS0/QS1: no separate delay parameter in the AC table; the Read/Write Timing [Large Scale] waveforms (scan p104) show QS1–QS0 transitioning once per CLK cycle at the **rising** edge, same delay class as address outputs. Sample QS on (or safely after) CLK↑ + ~60 ns.

**Sampling implication (OPEN_QUESTIONS Q2):** with NEC_CLK = 8 MHz (125 ns cycle, 62.5 ns half-cycle) from a 32 MHz sys
clock, worst-case CPU output validity at the FPGA pin is datasheet max + 5 ns shifter + 5 ns CLK-launch skew ≈ **75 ns
after the internal CLK edge** (e.g. tDKBH ≤ 65 ns). That is *more than a half-cycle*: sampling on the opposite CLK edge is
NOT safe. Sample each output group just before the next same-polarity CLK edge (≈ 3/4 into the cycle, i.e. the 3rd 32 MHz
tick after the edge). A 64 MHz sampling clock would give finer resolution but is not required for correctness.

**FPGA output launch budget:** data the CPU reads must be valid tSDK(20) + 5 ns = **25 ns before CLK↓** at the FPGA pin;
READY must meet tSRYHK (tKKL−8 ≈ 52 ns before CLK↑) + 5 ns; NMI/INT/POLL need 15 + 5 = 20 ns before CLK↑.

## RESET behavior (PDF p97)

- Active high; priority over all other operations.
- **Must be held high ≥ 4 clock cycles.**
- After RESET returns low, execution begins at **FFFF0H**.
- RESET also exits standby mode.
- (Reset-to-first-fetch cycle count: not stated here — measure in bring-up experiment; OPEN_QUESTIONS.)

## Misc facts picked up (same section)

- The V30 can execute the entire 8080 instruction set (emulation mode via BRKEM/RETEM/CALLN; MD flag, PDF p107–113).
- Standby mode released by RESET/NMI/INT (p112, p115).
- Bit processing, packed BCD, high-speed MUL/DIV are NEC additions vs 8086 (p94).
