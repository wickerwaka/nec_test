# V20/V30 EU micro-sequencer ROM — analysis (informs the resume scheduler B2)

Source: `docs/V20UC.TXT` (1285-line disassembly of the µPD70108/70116 EU
micro-sequencer ROM) + `docs/v20_microcode_04.xlsx`. Read-only analysis to
confirm WHAT the microcode governs vs what is separate BIU hardware — the
distinction that decides whether the prefetch-resume law can be read off the
ROM (it cannot) and what EU-side signals the resume scheduler (B2) keys on.

## VERDICT — the prefetch/queue/resume machinery is NOT in the microcode

The ROM is the EU micro-sequencer ONLY. The prefetch queue, the bus grid, the
refill/resume decision, and the wait-state handling are **separate BIU
hardware**, absent from the ROM:

- **Zero** tokens for `prefetch` / `queue` / `refill` / `resume` / `idle` in the
  entire ROM (grep = 0). The queue-fill/resume law is therefore NOT microcoded —
  it is a hardware BIU state machine. This is the decisive confirmation that the
  resume scheduler must MODEL BIU hardware; there is no ROM shortcut and no
  microcode table to transcribe.

The ROM governs the EU datapath (register/ALU moves, SIGMA→PC branches, operand
sequencing) and exposes a small set of interface signals the BIU hardware reacts
to. Those signals — NOT any resume micro-op — are the scheduler's inputs.

## EU↔BIU interface signals (USE THESE as the B2 decision inputs)

1. **Queue-byte consumption (the `Q` source read).** The EU consumes queue bytes
   unconditionally as a datapath source (`Q` appears 79×) — 1 byte per micro-op
   that reads it, plus the E-flag opcode-fetch boundary (the `E` column marks
   the micro-op that closes an instruction / pops the next opcode). This is the
   EU-side of the queue drain the BIU's occupancy tracks. The scheduler's
   `occupied` is driven down by these consumption events.

2. **EU bus requests MEMR / MEMW** (113× READ/WRITE/MEMR/MEMW, `SS`/segment
   qualified). These are the EU data-access requests the BIU arbitrates against
   prefetch — already modeled (eu_req/eu_kind/eu_wr and the landed arbitration
   overrides). The microcode issues them via the OPR/IND operand path.

3. **SUSP (suspend-prefetch), used surgically 28×.** SUSP is asserted ONLY
   before a FLUSH (e.g. Jcc `0038 …CTL SUSP` → `0039 SIGMA→PC …CTL FLUSH`) and on
   stack-read / INTA sequences (`00E6 SP→IND … CTL SUSP MEMR SS`, etc.). It is
   the EU telling the BIU to stop issuing prefetches ahead of a resolution /
   stack access — a discrete, per-opcode-deterministic signal, NOT a general
   resume knob. The resume scheduler must honor SUSP as a hard prefetch bar
   (distinct from the phase-based resume pacing).

4. **FLUSH — EU-deterministic per opcode (26×).** The flush point is a fixed ROM
   micro-address per control-transfer opcode: Jcc `0039`, near-JMP/others `0073`,
   E8 near-CALL `0150`, EB short-JMP `0157`, RET/far `015B/0161/01C4/01CB`, REP
   `0227`. This CONFIRMS the biu_model flush law (flush is EU-deterministic,
   per-opcode) and the landed `flush_hold` fits — the BIU sees FLUSH at a fixed
   EU cycle per opcode; the +1-late redirect is a BIU-grid timing law layered on
   that deterministic EU flush.

5. **The `F`-flag / OPR data-ready interlock — the ONLY EU↔BIU bus sync.** The
   `F` column marks a micro-op that reads/writes `OPR` (the bus-transfer operand
   register) and STALLS the EU until the bus transfer completes (e.g. `000B
   OPR→R  F`, `002F OPR→M  F`, `00EA OPR→PC  F …FLUSH`). This F/OPR interlock is
   the entire EU-side bus synchronization: the EU marches its microcode freely
   until it needs OPR data, then waits on `F`. This is WHY EU-bound ops are
   wait-insensitive (DIVU stays 28 cycles at all waits — no OPR dependency in
   the compute burn) and why the BIU wait-state stretch is invisible to the EU
   except through the F/OPR handshake. The scheduler models bus-grid timing; the
   EU's only coupling to it is F/OPR — so the resume decision is a pure BIU-grid
   function gated by SUSP/FLUSH/MEMR-MEMW/consumption, not by EU micro-timing.

## Confirmations (contradicts nothing in biu_model.md)

- **Flush is EU-deterministic per-opcode** (fixed FLUSH micro-address) — matches
  the flush law + `flush_hold`.
- **LOCK is a decode-time prefix latch, no LOCK micro-op** — matches the BUSLOCK
  model (F0 latched at decode, cleared at the locked write's T4; no ROM entry).
- **Wait-states are 100% BIU hardware** — the EU is wait-agnostic via the F/OPR
  interlock; no wait/ready token in the ROM. Matches "EU-bound ops are
  wait-insensitive" (exp5) and the bus-grid-only wait model.
- **REP strings are mid-loop interruptible** — `0223 JMP INTR` inside the REP
  loop (`0220-0228`, FLUSH at `0227`) — matches the interrupt_model REP
  interruptibility and the deferred REP-abort accept-edge class.

## Implication for the resume scheduler (B2)

The resume-issue decision is a BIU-hardware function of: the queue occupancy
trajectory (driven by EU `Q`-consumption + the fetch pushes), the bus-grid phase
(the corrected `grid_phase`, B1), and the hard prefetch bars (SUSP before
flush/stack, FLUSH redirect). The EU side contributes only these discrete
signals — consumption, MEMR/MEMW, SUSP, FLUSH, F/OPR — NOT a resume micro-op.
The scheduler therefore models the BIU grid/occupancy crossing keyed on
grid_phase + occupied (the exact-state predictor's 83-98% inputs), honoring SUSP
as a hard bar and the per-opcode FLUSH as the redirect trigger. No microcode
resume table exists to fit against — the fit is from the RTL's own internal
signals against the chip, as B2 specifies.
