# WAITS>=1 residual drift — magnitude in CLOCK-CYCLE / instruction terms

Reflash-free measurement on current mainline (master, fabric 0f383e0) via
`sw/timing_magnitude.py`: cached chip refs vs the Verilator core, 70 fuzz seeds
(fz90000-90069) at w0/w1/w3. Each capture row = one CPU clock. The offset is
measured WRITE-ANCHORED (the clock delta between the chip's and the core's k-th
memory write) — memory writes are architectural events with no speculation, so
this is the true architectural timing gap (the per-fetch offset inflates a few
seeds by speculative-prefetch/window-boundary alignment artifacts; writes do
not). The bad-rows metric (w1 ~307 / w3 ~476) counts every momentarily
out-of-phase ROW and is NOT the timing magnitude — the actual accumulated clock
divergence is tiny.

## Results (70 seeds, write-anchored architectural offset)

| wait | |final offset| median / mean / WORST | peak excursion (worst) | drift rate | direction | fully cycle-clean |
|---|---|---|---|---|---|---|
| **w0** | **0 / 0.0 / 0 clk** | 0 | 0 | — | **CYCLE-EXACT** | **40/40** |
| **w1** | **0 / 1.1 / 6 clk** | 6 clk | 0.0-0.3 cyc/100 fetch, 0.12 cyc/1000 clk | +16/-18 = **bidirectional, self-cancelling** | 35/70 |
| **w3** | **2 / 1.8 / 7 clk** | 7 clk | 1.2 cyc/100 fetch, 0.48 cyc/1000 clk | +38/-3 = **mostly one-directional (core marginally faster/ahead)** | 29/70 |

(+ offset = the chip reaches the write at a LATER clock = chip slower = core
faster/ahead. Window ~145-200 fetches / up to the ~4063-clock capture.)

## The six questions, answered concretely

1. **Total cycle divergence per block.** Over the ~4000-clock capture window: w0
   **0 clocks** (identical). w1 **median 0, mean 1.1, worst 6 clocks** (~0.15%
   of the window worst-case). w3 **median 2, mean 1.8, worst 7 clocks** (~0.2%).
   Half the w1 seeds and ~40% of w3 seeds are perfectly cycle-identical end to end.

2. **Drift rate.** w1 ~0.12 clk / 1000 clocks (≈0.3 clk / 100 fetches); w3 ~0.48
   clk / 1000 clocks (≈1.2 clk / 100 fetches). Roughly linear in program length
   at w3, but SMALL and, at w1, self-limiting (the excursions re-sync).

3. **Direction / sign.** w1 is **bidirectional** (+16/-18): a +N excursion is
   later cancelled by a -N, so the NET stays ~0 (mean |final| 1.1 vs peak
   excursions up to 6). w3 is **mostly one-directional** (+38/-3): the core runs
   marginally FEWER clocks (faster) and the small offset persists — but only
   ~2 clocks over the whole window (it does not run away).

4. **Cascade vs re-sync.** w1: predominantly LOCAL BLIPS that RE-SYNC — many
   seeds swing to +/-3..5 clocks mid-window then return to 0 by the end (final
   0, half the seeds fully clean). w3: a small PERSISTENT one-directional shift
   (~2 clocks) that does not re-sync but does not cascade either — it saturates
   at a handful of clocks, bounded by the queue depth / refill dynamics.

5. **Worst-case and typical (over the ~4063-clock window).** w1 typical 0 /
   worst 6 clocks. w3 typical 2 / worst 7 clocks. No seed exceeds 7 clocks of
   true architectural divergence at any wait level.

6. **Functional confirmation.** **Memory writes (addr + data) are BYTE-IDENTICAL
   for every seed at every wait level (w0/w1/w3).** The retired fetch-address
   stream is identical (modulo speculative/doomed prefetches, which legitimately
   differ by 1 near branches without an execution divergence). The divergence is
   PURELY TIMING — the architectural result is identical.

## BOTTOM LINE

Over a ~150-fetch (~4000-clock) block at **w3**, the core and chip differ by
**~2 clocks typically (worst 7, ~0.2%)**, accumulating at **~1.2 clocks per 100
fetches (~0.5 clk/1000 clocks)**, **mostly one-directional** (core marginally
faster), and are **FUNCTIONALLY IDENTICAL** (all memory writes byte-identical).
At **w1** it is **~0-1 clock (worst 6), bidirectional/self-cancelling** (half the
seeds cycle-perfect). At **w0 — zero wait states, the normal MiSTer operating
mode — the core is CYCLE-EXACT (0 divergence).**

Practical verdict: the residual waits>=1 timing drift is **negligible for a real
deployment**. It is a handful of clocks (<=7) over a full capture, never
architecturally visible (writes/state identical), zero at w0, and self-cancelling
at w1. The ~307/476 "bad-rows" figure is a phase-alignment row count, not a
timing magnitude; the real magnitude is <=7 clocks. This confirms the resume
floor is a cosmetic sub-cycle phase residual, not a functional or practically
significant timing error.
