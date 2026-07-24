# Clock-Enable (CE) for v30_core — implementation plan

Goal: add a clock-enable so the core runs on the fast fabric `clk` but only
advances state when CE is asserted, decoupling the core's execution rate
from the fabric clock (standard `clk_sys` + `clock_enable` idiom). Coordinator
decisions (2026-07-13): CE locked to the NEC_CLK cadence (`tick_rise`) so the
A/B comparison stays lock-step with the socketed chip; chip NEC_CLK
generation unchanged; explicit `CE_HALF` port for the one negedge process.
Runtime-host-selectable core rate is a deferred additive follow-on (feed the
core CE from a host-controllable divider instead of `tick_rise`).

## Why this is low-risk here
- v30_eu.sv is a SINGLE monolithic `always_ff @(posedge clk)` (~L1365-4560)
  holding all EU state: FSM, rf[0:7], sr[0:3], psw/pc/arch_ip, the iterative
  divider (div_*), the iterative shifter (sh_*), string a4_*, and all pin
  pipelines (int_p/nmi_p/nmi_latch/poll_s1/ie_p/rslot/rep1_abort). Gating this
  one process CE-gates the div/shift step counters automatically (required by
  commits c2beb6a / e7c315a).
- NO synchronous-read BRAM in the core. race_rom (RR1: retired -> combinational race_law, 2026-07-23; was LUT/logic anyway), q_mem (biu L239),
  rf/sr are all combinational-read → no read-latency to keep aligned; the
  classic sync-BRAM CE desync cannot occur.
- Exactly ONE `negedge clk` process: t1_half2 (biu L783) — the T1 write-data
  half-cycle — handled with CE_HALF.

## Ports
- v30_core: add `input CE, input CE_HALF`; pass `.ce(CE), .ce_half(CE_HALF)`
  to u_biu (L100) and u_eu (L154). Combinational assigns below stay ungated.
- v30_biu: add `input ce, input ce_half`.
- v30_eu: add `input ce` (no negedge process; ce_half unused/optional).
- Reset stays UNGATED everywhere: `if (srst) … else if (ce) …`. The
  V30_BACKDOOR bkd_load lives in the srst branch (biu L480-488, eu L1462-1472)
  and must fire on RESET regardless of CE.

## Every sequential process to gate
biu.sv: q_head_dry_q (L248); halt_t1/halt_done (L295-303, keep its guard, gate
the else); MAIN BIU FSM (L440-716); ph_ff (L732); ready_prev (L748);
eu_req_p1/p2 + eu_ready_p1 pulse detectors (L749-753); t1_half2 (negedge,
L783 → `always @(negedge clk) if (ce_half) …`).
eu.sv: the whole monolithic process (L1365-~4560) → gate at the else (L1473).

### THE TWO SUBTLE BUGS TO AVOID (most likely desync sources)
1. Pulse-default collapse. In biu, `eu_started<=0` (L441) sits BEFORE `if(srst)`
   and push_pend/eu_hand/eval_ext clear at the top of the else (L496-498). In
   eu, the "every-state" block (L1366-1395: flush_now<=0, rslot decrement, the
   int_p/nmi_p/poll_s1/ie_p pin pipelines, NMI edge latch, rep1_abort latch,
   popr_pend/rf[4] ghost-pop, iret_pw/psw RETI completion) runs unconditionally
   today. ALL of these must move INSIDE `else if (ce)`. If a clocked default
   runs every fabric clock while its set is CE-gated, one-cycle pulses die
   before the next CE consumer sees them → silent desync. Rule: nothing clocked
   runs unless srst or ce. The srst branch already sets these explicitly, so no
   reset coverage is lost.
2. The negedge t1_half2 must be gated by CE_HALF=tick_fall, not run free.

## Memories
q_mem/rf/sr: registers, combinational read; writes are inside CE-gated
processes; bkd_load writes stay in the ungated srst branch. race_rom:
read-only combinational ROM, CE has no interaction — leave alone (confirm
synthesis keeps it combinational, not registered-read BRAM). [RR1 2026-07-23:
race_rom retired, replaced by combinational race_law (was LUT/logic, never
block ROM); CE analysis unchanged — still stateless.] Harness test_mem
/ capture_buf: sys-clocked, untouched.

## TB / verification gate
tb_v30_core.sv: change ONLY the DUT instantiation (L114-137) — add
`.CE(1'b1), .CE_HALF(1'b1)`. With CE tied high every posedge advances and
t1_half2 fires every negedge = today's behavior exactly. GATE: check_core.py
--build, full regression across all suites → 155,500 BIT- and CYCLE-identical
(expect 155440/155500; 60 residual = 8F.0). Hard gate before any harness change.

CE-hold sanity: add a `+ce_div=N` plusarg that generates a 1-in-N CE train AND
GATES THE TB'S OWN clocked observer (posedge L225, negedge latches L184/L213)
on the same CE (else the observer runs N× faster and records garbage). Assert:
per-CPU-cycle rows identical to N=1, and internal state (u_eu.state,
u_biu.state, div_cnt, q_cnt) does NOT change across CE-low fabric clocks.
Default N=1 keeps the golden path untouched.

## Harness integration
Today: core is `.CLK(hb_clk)` where hb_clk=NEC_CLK (nec_bus L120-131). Change:
1. nec_bus.sv: expose existing internal wires `tick_rise` (L117) and
   `tick_fall` (L118) as two NEW OUTPUTS. This is the ONLY nec_bus change; its
   logic and the socketed-chip path stay bit-identical.
2. system_large.sv u_core (L339-353): `.CLK(hb_clk)`→`.CLK(clk)`, add
   `.CE(bus_tick_rise)`, `.CE_HALF(bus_tick_fall)`.
Captures stay aligned because the CE-gated core advances on the same sys
posedge (tick_rise) and mid-cycle negedge (tick_fall) as the old core-on-NEC_CLK
design, so nec_bus's samplers (ad_early @tick_fall, addr latch @tick_fall &
T1, capture @tick_rise) see identical values. Re-confirm input hold-margin /
boot-match after the clock-source switch (the 2026-07-13 boot desync class).

## Order
1. RTL: ports + gate all §processes + move pulse defaults inside CE.
2. Verilator golden gate CE-high → 155,500 bit+cycle-identical (HARD GATE).
3. CE-hold sanity (+ce_div=N>1): rows identical, state freezes at CE=0.
4. Harness: expose tick_rise/tick_fall; switch u_core to clk+CE.
5. Quartus build; hardware A/B re-confirm (first light + A/B fuzz 500/500).

## Risks (highest first)
t1_half2 CE_HALF timing (write-data AD phase) → validate on write-heavy fuzz;
pulse-default collapse (bug #1 above); pin edge detectors at fabric rate;
input hold-margin re-validation on clock-source switch; race_rom BRAM
inference [RR1 2026-07-23: moot — race_rom retired for combinational race_law;
it was LUT/logic, never BRAM]. All caught by the golden gate + CE-hold sanity + hardware A/B.

## Outcome (2026-07-13, IMPLEMENTED — all gates passed)

The refactor landed exactly as planned; both subtle bugs were handled
(eu_started moved into the ce branch + added to biu reset; the eu
every-state block moved inside `else if(ce)` with flush_now<=0 added to eu
reset; t1_half2 gated by ce_half). Commits e15492d / 9716b01 / 6f7cdd2.

1. GOLDEN GATE (CE-high, N=1): bit- AND cycle-identical to baseline.
   v0.1 155440/155500 full (cycles 155440, arch 155500) — the only
   residual is the pre-existing 8F.0 (60 cycles); wait suites w1/w3 both
   1200/1200. No new divergence from the gating.
2. CE-HOLD SANITY (+ce_div=N>1, +ce_hold_check): N=3 over a 20-opcode
   spread = 9940/10000, BIT-identical to N=1 (same 8F.0 residual), zero
   freeze violations; N=7 on the iterative machines (div/shift/REP/PREP/
   ROL4/ADD4S) 5000/5000, zero violations. Per-CPU-cycle output is
   independent of the fabric/CE ratio; u_eu.state / u_biu.state / q_cnt /
   div_cnt do not change on CE-low clocks.
3. HARNESS: nec_bus exposes tick_rise_o / tick_fall_o (only change);
   system_large u_core → .CLK(clk)/.CE(bus_tick_rise)/.CE_HALF(bus_tick_fall).
   check_ab_sim: core boot MATCHES chip golden over 287 rows (no phase
   adjustment needed — the A2 input pipe carried over unchanged).
   tb_harness ALL PASSED; largemode_synth.hex byte-identical.
4. BUILD: full compile 0 errors, 8m40s total (quartus_map 3m52s, Fitter
   4m24s) — no synthesis spike. Timing MET: emu/core clock target 32 MHz,
   Fmax 48.09 MHz (setup slack +5.227 ns, hold +0.263 ns). Fmax fell from
   the pre-CE 84.82 MHz because the core now lives on the 32 MHz fabric
   domain by design (its cones close within a sys-clock period, with 50%
   headroom). Util 9,690 ALMs (23%), 5117 regs, 13 DSP; only the 2 intended
   small AAM lpm_divide units. safe_flash'd (VERIFY ok, use_core=False).
5. HARDWARE A/B (real silicon): chip position (use_core=0) vs golden
   MATCH 800/800 (chip path undisturbed); FIRST LIGHT — CE-driven fabric
   core (use_core=1) vs socketed chip MATCH 800/800; in-silicon A/B
   sequence fuzz fz5000-5499 500/500 clean, zero divergence, zero QS
   flickers. Board echo-healthy after the run. The CE-driven in-fabric
   core is cycle-for-cycle indistinguishable from the socketed chip.
