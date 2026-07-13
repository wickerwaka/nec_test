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
- NO synchronous-read BRAM in the core. race_rom (L390), q_mem (biu L239),
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
synthesis keeps it combinational, not registered-read BRAM). Harness test_mem
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
inference. All caught by the golden gate + CE-hold sanity + hardware A/B.
