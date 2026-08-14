# THE DE-MUXED BUS INTERFACE — PRE-REGISTRATION

**Written and committed BEFORE the first RTL edit.**  Tree `537637591d`
(`master`), isolated worktree.  **Offline.  NO board, NO flash.**
G6: **one draw per configuration — NOT an Fmax measurement**
(USER RULING 2026-08-13, `standing_gates.md` §A).

> **SIMPLICITY: this is 80's era hardware — nothing on the die is wasted.
> Complex or confusing observed behavior is likely simple systems interacting
> in ways not yet understood. A large fitted table, a many-cased rule, or a
> per-opcode special case is a signal of misunderstanding, not a deliverable.**

---

## §1 WHAT IS BEING BUILT, AND WHY IT IS ONE SENTENCE

The V30 multiplexes one twenty-pin bus three ways because a 40-pin DIP has no
room for sixty pins.  Inside an FPGA that constraint does not exist, and every
downstream integrator (M72's demux adapter,
`docs/notes/m72_downstream_timing_2026-08-12.md` §1) pays for it twice: once to
re-latch the address the core just had in a register, and once more to know
*when* to latch it.

**The whole of the multiplexing law, read off `v30u_biu.sv:1064-1073`, is one
sentence:**

> **A19-16 carries the address's top nibble during the address ONE-SHOT and the
> status nibble otherwise; A15-0 carries the address low during an address
> phase and the write data otherwise.**

That sentence has exactly three operands — an address, a write word, a status
nibble — and every one of them is already a register (or a register-only
lookahead) inside the BIU.  **So the de-mux is a re-slicing of a mux, not a new
mechanism, and it adds NO flop.**  This wave publishes the three operands as
ports and puts the mux itself behind a compile-time define.

### 1.1 USER RULINGS (2026-08-14), binding

1. **A compile-time define, not a parameter** — *"unused ports should be removed
   based on the define."*  With the define OFF the muxed machinery's ports
   (`AD`, `AD_OE`, `CE_HALF`) **do not exist on the module** (`ifdef` in the port
   list).  With it ON everything is present and **byte-identical to today**.
2. **The status bits become a port** — the nibble the muxed view drives on
   A19-16 during data phases (`data_ps`) is its own dedicated output, **always
   present**.

---

## §2 THE PORTS AS THEY WILL LAND

`hdl/rtl/ucore/v30_core.sv` (UPPERCASE, the chip-pin idiom) and
`hdl/rtl/ucore/v30u_biu.sv` (lowercase, the module idiom).

| port | dir | width | present | source |
|---|---|---|---|---|
| `ADDR_O` / `addr_o` | out | 20 | **always** | `r_cur_addr` / `display_addr` / `flush_fast_addr` / `eu_addr` — all registers or register-only sums |
| `DATA_O` / `data_o` | out | 16 | **always** | `cur_data_o` (`r_cur_data`, or the register-only pairing lookahead of `:1058`) |
| `STATUS_O` / `status_o` | out | 4 | **always** | `data_ps(seg)` = `{md8080, psw_ie, seg}` — two EU register bits and a BIU register |
| `DATA_I` | in | 16 | **`ifndef V30_MUXED_AD`** | the read-data path; `AD[15:0]` carries it when the mux exists |
| `AD` | inout | 20 | **`ifdef V30_MUXED_AD`** | unchanged |
| `AD_OE` | out | 20 | **`ifdef V30_MUXED_AD`** | unchanged |
| `CE_HALF` | in | 1 | **`ifdef V30_MUXED_AD`** | unchanged |

**`DATA_I` IS A SURFACED DESIGN DECISION, NOT A SILENT ADDITION.**  The brief's
port list names three OUTPUTS.  `AD` is an `inout` and it is the core's ONLY
read-data path (`v30_core.sv:236`, `.ad_i(AD[15:0])`); removing it removes the
core's ability to receive.  So the de-muxed configuration needs a read-data
input, and by ruling 1's own logic (*remove the ports the define makes unused*)
it is the muxed configuration that does not need `DATA_I` — `AD` carries it
there.  The two are exclusive, exactly as `AD`'s output half and `ADDR_O`/
`DATA_O` are not.

**No new flop is created.**  If any source turns out not to be a register, that
is reported as a surfaced design decision and NOT silently flopped.

### 2.1 THE PORT CONTRACTS (to be written into the module header verbatim)

* **`ADDR_O[19:0]` — the linear address of the cycle that owns the bus.**
  VALID-FROM the announcement clock (the DISPLAY, where it carries the
  *announced* cycle's address) and VALID-THROUGH the whole of that cycle's T1,
  T2, Tw, T3, T4 (where it carries the *running* cycle's address).  It is never
  meaningless: with no cycle running it holds the last running cycle's address
  (`r_cur_addr`), which is what the pads show by retention on the real part.
  An INTA announces no address and `ADDR_O` reads `20'h0` there — the part's
  own `Access::no_addr`.
* **`DATA_O[15:0]` — the write word of the cycle that owns the bus**, in bus
  byte order (swapped on an odd address, `:1059-1061`).  MEANINGFUL whenever
  the current cycle is a write (`BS == MEMW/IOW`), from its T1 through T4.  On
  a read cycle it holds the previous write's word and is **declared
  meaningless** — the muxed view never publishes it there either.
* **`STATUS_O[3:0]` — `{md8080, psw_ie, seg[1:0]}`**, the nibble A19-16 carries
  whenever it is not carrying an address.  MEANINGFUL for the whole of the
  owning cycle.  It follows the same owner the address does: the ANNOUNCED
  cycle's segment while a display is on the pins, the RUNNING cycle's segment
  otherwise.
* **`DATA_I[15:0]`** — read data, sampled by the existing `ad_i` path and on
  the existing schedule.  Nothing about *when* the core samples changes.

There is **no new "address valid" strobe.**  The real part in max mode
announces with `BS` (S0-S2) and the bus controller derives everything else;
this interface does the same, with `BS`, `RD_N` and `UBE_N` unchanged.  Adding
a strobe would be a pin the die does not have.

---

## §3 THE DEFINE

**`V30_MUXED_AD`.**  Positive polarity: the RIG defines it, so **every rig build
site must be edited and the audit is a registered deliverable** (a missed site
fails LOUDLY — a `.AD` connection to a non-existent port is a Verilator/Quartus
error, not a silent behaviour change).

* It is **orthogonal to `SYNTHESIS`**: `SYNTHESIS` selects fabric-vs-sim;
  `V30_MUXED_AD` selects the bus shape.  Both are set for the Quartus build.
* It follows the **`X1_AD_RETENTION` idiom** for reaching Quartus — a
  `set_global_assignment -name VERILOG_MACRO` in `hdl/nec_test.qsf` (which
  `gen_ucore_qsf.py` copies verbatim into the ucore revision, so `--check`
  keeps the A/B honest).  ⚠ **Not** the `--verilog_macro` command-line form:
  that one is `quartus_gate.py --retention`'s, is per-invocation, and would make
  the define invisible to any other build path.  A `.qsf` macro is the right
  home for a define that is part of the configuration rather than part of an
  experiment.
* **`t1_half2` and its save-state arm go under the same define.**  `t1_half2`
  is the T1 address→data turnaround and has ZERO consumers in the core's
  next-state logic (`t1_half2_anatomy_2026-08-13.md` §1.3): it is muxed-bus
  machinery entire.  With the define OFF it does not exist, and neither does
  `CE_HALF`, which is its only enable.
* **The C-a / S-1 contract asserts go with it.**  Both name `CE_HALF`; with no
  such pin **C-a is vacuous by construction** and S-1 has nothing to require.
  This will be stated in the assert block's own comment rather than left to be
  inferred.

### 3.1 THE SAVE-STATE CONSEQUENCE, STATED AND NOT PAPERED OVER

`SSA_B_T1_HALF2` (`9'h001`) is one bit of the ucore map.  With the define ON —
**the rig configuration, and the only one any standing gate scores** — the flop
exists, the address reads it, and **`SS_VERSION`/`SS_COUNT`/`SS_TAG` and the
flop census do not move** (`0x8E` / `232` / `221` flops).  `v30u_ss_pkg.sv` is
**not edited**: the map is a compile-time table and the wave adds and removes
nothing from it.

With the define OFF the flop does not exist, address `9'h001` falls to the
`default` arm and reads `16'h0000`, and **a define-OFF build is therefore a
DIFFERENT save-state stream by construction.**  It is not stream-compatible
with the rig's and must never be loaded into one.  This is documented, not
worked around: `SS_VERSION` is not bumped, because bumping it would move the
rig configuration's tag for a flop the rig configuration still has.

---

## §4 THE LOAD-BEARING FALSIFIER — THE RECONSTRUCTION ASSERT

The risk this wave carries is **drift**: two derivations of the same pins that
agree today and diverge on the next edit.  The registered mitigation is
structural first and asserted second.

**STRUCTURAL.**  With the define ON, `ad_o` is **COMPOSED FROM THE NEW PORTS**:

```systemverilog
assign ad_o = { bus_ph_hi ? addr_o[19:16] : status_o,
                bus_ph_lo ? addr_o[15:0]  : data_o };
```

— the §1 sentence, rendered.  There is then no parallel derivation to drift,
because the muxed view has no operands of its own.

**ASSERTED.**  The historical nine-way `ad_o` mux is retained VERBATIM as a
sim-only reference `ad_o_ref` (with its four helper nibbles `t1_addr`,
`disp_hi`, `dinta_hi`, `cinta_hi`, which the composed form no longer needs),
and

```systemverilog
always @(posedge clk) if (ad_o !== ad_o_ref) $fatal(...);
```

runs **every fabric clock of every define-ON simulation leg in §6**.  This is
STRONGER than reconstructing forward from the ports and comparing to `ad_o` —
that comparison is a tautology once `ad_o` is composed from them — because it
checks the composition against the pin law that 169,000 golden cases, 17,350
lockstep forms and every fabric bitstream to date were scored on.

* ⚠ **ONE STATED HOLE**: the compare is skipped while `ad_o_ref` carries an `X`
  (`^ad_o_ref === 1'bx`), because two X-pessimistic expressions over the same
  registers may differ in X-ness without differing in value.  This confines the
  hole to the pre-reset era.
* **NON-VACUITY IS A REGISTERED DELIVERABLE (P-N).**  In a scratch copy, ONE
  term of the composition is perturbed and the assert must **FIRE**.  The
  perturbation is thrown away; the demonstration is reported.

**WHAT THE ASSERT DOES NOT COVER, stated in advance**: `DATA_O` during a read
and `STATUS_O` during an address phase are not carried by the muxed view, so
the mux cannot check them.  They are register taps whose value there is
declared meaningless (§2.1).

---

## §5 THE DEFINE-OFF PROOF (P-OFF) — PROVEN, NOT ASSUMED

A configuration nothing compiles is a configuration nothing knows is broken.

* **P-OFF-1.**  A new minimal testbench `hdl/tb/tb_demux_min.sv` instantiates
  `v30_core` with **no `AD`, no `AD_OE`, no `CE_HALF`**, serves fetches and
  reads from a memory addressed by **`ADDR_O`** into **`DATA_I`**, commits
  writes from **`DATA_O`** with **`STATUS_O`** recorded, and runs ≥ 100,000
  fabric clocks.  It must COMPILE, ELABORATE and RUN, and its census must show
  the core actually executing: **`FPOPS > 0`** (instructions started) and
  **≥ 4 distinct `BS` codes exercised** including at least one **write**.
* **P-OFF-2 — the ports are TRULY GONE.**  A scratch build of the same TB with
  a `.AD(...)` connection added must FAIL to elaborate, naming the pin.  A
  compile that merely warns is not evidence.
* **P-OFF-3.**  `sw/ss_flopcensus.py`'s notion of a synthesised region must not
  be perturbed by the new `ifdef`: `ss_lint --core ucore` reads **232 / 221 / 0
  UNMAPPED**, unchanged.

---

## §6 THE LADDER — REGISTERED BARS (define ON, the rig configuration)

Every figure below is the CURRENT standing value and is registered to be
**UNMOVED**.  A miss is reported as registered, never restated.

| leg | registered |
|---|---|
| `check_core --opcodes all --cases 0` **at `--ce-div 4` and `--ce-div 2`** | **169,000 / 169,000** each |
| `check_core --opcodes 8F.0` | 500 / 500 |
| `s10-hltsweep-w0 --waits 0` | 97 / 97 |
| `s10-hltsweep-w1 --waits 1` | 93 / 95 |
| `s13-hltsweep-w2 --waits 2` | 45 / 46 |
| `s13-hltsweep-w3 --waits 3` | 44 / 45 |
| **the four sweeps** | **279 / 283** |
| `f4a_boundary --waits 0` / `f0lock_tranche --waits 0` | 160 / 160 · 400 / 400 |
| `v0.1-w1` / `-w3` | 1,200 / 1,200 each |
| `v0.1-w1 --opcodes EB` | 200 / 200 |
| the four `evt` cells | 200 · 1,200 · 200 · 1,200 |
| `v0.1-w1evt-biased` | 1,200 / 1,200 |
| `check_boot --timed 220` / `400` | MATCH / MATCH |
| `ulockstep --golden all --cases 50` | **17,350 / 17,350** |
| `sm3_s16_score --core ucore` | `busstat_other` **24** · `ARCH` **27** |
| `check_ab_sim --core ucore` | MATCH **187** rows |
| `ghost_launch_law score` | **200 / 200 = 100.0 %** |
| `chain_lfsr_gate` | **PASS**, depth [6], 0 overflows, signatures **UNMOVED** |
| `r7_lint` | **PASS** — 20 nets / 1 carrier / 3 tainted / 51 `stop` / 0 violations |
| `ss_lint --core ucore` | **PASS**, 232 / 221 flops / 0 UNMAPPED |
| `test_artifact` | **45 / 45**, non-vacuous |
| `test_quartus_gate` | **254 / 254** (255 with a build tree on disk) |
| `gen_ucore_qsf --check` | clean |
| `ucrom_mif_check` (after G6) | **PASS**, 8,192 / 8,192 and 1,028 / 1,028 |
| `ie_pinfall_cell core` (2,200 cells) | **data files BYTE-IDENTICAL** by content |
| `ghost_pred_cell core` (528 cells) | **data files BYTE-IDENTICAL** by content |
| `fz2_replay --all-failures --pass-sample 200 --leg ret` | **AGREEMENT 100 %**, `first_bad` identical |

**`fz2_immaterial falsify`**: the KNOWN F21-era `G6`/`G7` document-lag FAIL is
carried forward and **is NOT re-derived in this wave** (`standing_gates.md`;
`ce_contract_correction_results_2026-08-13.md` §7.2a).  G1-G5 and G8 are
registered to PASS.  Re-deriving a census inside an unrelated wave is how a
number stops being readable against its own history.

**ERA OVERRIDES**: `fz2_replay`'s fabric-era guard WILL refuse (this wave moves
`v30_core.sv`, `v30u_biu.sv`, `system_large.sv`, `nec_test.qsf` and
`nec_test_ucore.qsf`).  It is run with `--no-fabric-era-guard` and **no fabric
claim is made from it.**  The fz2 captures are gitignored and main-only; this
worktree reaches them by **read-only symlink**, and `tb_sys` is **rebuilt**.

### 6.1 G6 — ONE DRAW PER CONFIGURATION, NOT AN Fmax MEASUREMENT

| | registered |
|---|---|
| CONTROL | PASS; near **38.01 MHz** / +6.618 ns / 10,155 ALMs |
| RETENTION (`--retention`) | PASS; near **39.62 MHz** / +7.277 ns / 10,162 ALMs |
| both | TNS **0.000** setup AND hold on every domain; **0 errors, 0 latches, 0 `lpm_divide`**; `.rbf`s differ |

**THE EXPECTATION, REGISTERED IN ADVANCE**: `ADDR_O`, `DATA_O` and `STATUS_O`
are **UNCONNECTED in `system_large`**, so Quartus prunes them and the added
logic is zero.  The netlist may shift slightly (fitter churn) but the
functional figures should hold near the values above.  **Any latch, any error,
or a non-zero TNS is a STOP.**  ⚠ Per the quoting rule these are
`draw@seed<S>`, **not** a band and **not** an Fmax claim.

---

## §7 THE REGISTERED PREDICTIONS

* **P-1.**  The whole §6 ladder is **ZERO-DELTA**.  The composition is provably
  the same function (§4) and the reconstruction assert proves it clock by
  clock; anything else is a defect in this wave.
* **P-2.**  The reconstruction assert is **NON-VACUOUS** (§4, P-N).
* **P-3.**  `P-OFF-1`, `P-OFF-2` and `P-OFF-3` all MET.
* **P-4.**  **No flop is added or removed on any entity**, in either
  configuration, and `ss_lint` reads 232 / 221 unchanged with the define ON.
* **P-5.**  G6 PASSES on both configurations at one draw each, with 0 latches.
* **P-6.**  **The build-site audit is COMPLETE**: every site that compiles the
  ucore (or the archived FSM core, which shares `v30_core`'s module name and
  is NOT edited) is enumerated and either carries the define or is stated not
  to need it.

## §8 WHAT THIS WAVE DOES NOT DO

* It does **not** touch `hdl/rtl/core/` (the ARCHIVED FSM core).  That core's
  `AD`/`AD_OE`/`CE_HALF` stay unconditional, so it is buildable **only** with
  the define ON — which every FSM build site has, because the define is added
  to the shared commands.  Stated as a limitation, not fixed.
* It does **not** flash, touch a board, or make any fabric claim.
* It does **not** delegate to Codex and spawns no nested task.
* It does **not** change `nec_test.sdc`.  `ce_half → ce` still exists in the
  rig configuration; a define-OFF build simply has no `ce_half` domain.
