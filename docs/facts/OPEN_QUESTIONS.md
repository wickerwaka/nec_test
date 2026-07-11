# Open Questions

Living list of unknowns about the NEC V30 (μPD70116) that the discovery process must resolve.
Each entry states the question, why it matters, how we expect to answer it, and its status.
Retire entries by moving them to `docs/facts/` files with provenance (datasheet page or experiment ID).

## Harness-blocking (resolve first)

### Q1: What is the minimum clock frequency (f_CLK min)?
- **Why**: If the CMOS part is fully static, we can single-step or stretch the clock and capture at leisure. If not (some datasheets spec ~2 MHz min), all capture must be free-running with a deep buffer.
- **How**: μPD70116 datasheet DC/AC tables; then verify empirically (stretch clock, check for state loss).
- **Status**: **ANSWERED** — installed chip is a **μPD70116C-8** (standard, not H-series): clock must stay within 2–8 MHz; no single-stepping. All capture must be free-running. See `pins_timing.md`.

### Q2: What are the AC timing relationships of QS0/QS1 and BS0-2 relative to CLK edges?
- **Why**: Determines the FPGA sampling strategy — whether 4 samples per CPU clock (32 MHz sys / 8 MHz CPU) is sufficient, and which edge to sample on.
- **How**: Datasheet timing diagrams; confirm with SignalTap on real chip.
- **Status**: partially answered — see `pins_timing.md`: BS delays 10–65 ns from CLK edges; QS transitions once per cycle at CLK↑ (waveform p104). Level shifters add 5 ns per signal per direction (confirmed) → worst case ~75 ns from internal edge; sample ~3/4 into the cycle, not on the opposite edge. Remaining: confirm sampling margin on real hardware.

### Q3: What is the exact READY setup/hold window for inserting wait states?
- **Why**: Deterministic 0..N wait-state insertion is a core experiment variable.
- **How**: Datasheet + bring-up experiments.
- **Status**: answered on paper — see `pins_timing.md` READY section (verified against scan p101/p103). Remaining: empirical confirmation during bring-up.

### Q4: Which registers can the load/store routines set/read without side effects?
- **Why**: State injection technique (from arduinoX86) needs a known-clean sequence; flags load (POPF equivalent) and segment loads have interrupt-shadow effects.
- **How**: arduinoX86 source mining + experiments.
- **Status**: open

## Behavior discovery (the core research questions)

### Q5: Prefetch queue: exact refill policy?
- Depth is documented as 6 bytes — verify. When does the BIU issue a fetch (queue space threshold)? Does it fetch words always, or a byte when starting at an odd address? What delays refill after a flush?
- **Status**: open

### Q6: Decode time per opcode?
- Datasheets give execution clocks but not decode latency. Measure instruction-start-to-first-effect via queue status + bus activity for every opcode.
- **Status**: open

### Q7: When exactly does a jump flush the queue, and what is the refetch penalty?
- **Status**: open

### Q8: EA calculation timing — flat 2 clocks for all modes as documented?
- **Status**: open

### Q9: MUL/DIV timing — data-dependent? (V30 algorithm differs from Intel's.)
- **Status**: open

### Q10: Division-exception semantics — pushed CS:IP points where? (V20/V30 differ from 8086.)
- **Status**: open

### Q11: Undefined flag behavior per opcode?
- V20 SingleStepTests metadata.json has masks; verify V30 matches V20.
- **Status**: open

### Q12: Undocumented 0F-range opcodes and invalid-form behavior?
- **Status**: open

### Q13: 8080 emulation mode (BRKEM) — entry/exit timing, interrupt behavior during emulation, per-8080-opcode timing?
- **Status**: open

### Q14: Interrupt/NMI/POLL recognition points and priority; string-instruction interruption/resume behavior?
- **Status**: open

### Q15: Self-modifying code vs prefetch queue — at what distance does a write to an already-fetched byte get ignored?
- **Status**: open
