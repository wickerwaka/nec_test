# THE DE-MUXED BUS INTERFACE — RESULTS

Pre-registration `5232d516ca` (`docs/notes/demux_bus_prereg_2026-08-14.md`),
committed **before the first edit**.  Landing `b7083b45a5`.  Branch `master`
from `537637591d`, isolated worktree.  **Offline.  NO board, NO flash.**
G6 is **one draw per configuration and is not an Fmax measurement**.

> **SIMPLICITY: this is 80's era hardware — nothing on the die is wasted.
> Complex or confusing observed behavior is likely simple systems interacting
> in ways not yet understood. A large fitted table, a many-cased rule, or a
> per-opcode special case is a signal of misunderstanding, not a deliverable.**

---

## §1 THE HEADLINE

**The whole of the V30's AD multiplexing is one sentence with three operands,
and all three were already registers.**

> A19-16 carries the **address**'s top nibble during the address ONE-SHOT and
> the **status** nibble otherwise; A15-0 carries the address low during an
> address phase and the **write data** otherwise.

`v30u_biu.sv`'s nine-way `ad_o` mux — M23's late-T1 substitution, F53's three
nibble wires, F51/F55's HALT term, the `t1_half2` turnaround, the
vector-follow preview — is now **two phase bits over three ports**:

```systemverilog
assign ad_o = {bus_ph_hi ? addr_o[19:16] : status_o,
               bus_ph_lo ? addr_o[15:0]  : data_o};
```

Nothing was fitted and no case was added.  **No flop was created or destroyed**
(`ss_lint` 232 / 221, unchanged) and **the whole ladder is zero-delta**, down
to `chain_lfsr` signatures and 2,728 directed `tb_sys` cells byte-identical by
content.

**P-1, P-2, P-3, P-4, P-5 and P-6 are ALL MET.**

---

## §2 THE PORTS AS LANDED

| port | dir | width | present | source |
|---|---|---|---|---|
| `ADDR_O` / `addr_o` | out | 20 | **always** | `r_cur_addr` · `display_addr` · `flush_fast_addr` · `eu_addr` |
| `DATA_O` / `data_o` | out | 16 | **always** | `cur_data_o` |
| `STATUS_O` / `status_o` | out | 4 | **always** | `data_ps(seg)` = `{md8080, psw_ie, seg}` |
| `DATA_I` | in | 16 | **`ifndef V30_MUXED_AD`** | read data |
| `AD` | inout | 20 | **`ifdef V30_MUXED_AD`** | unchanged |
| `AD_OE` | out | 20 | **`ifdef V30_MUXED_AD`** | unchanged |
| `CE_HALF` | in | 1 | **`ifdef V30_MUXED_AD`** | unchanged |

### 2.1 THE CONTRACTS (verbatim in `v30_core.sv`'s header, THE BUS SHAPE)

* **`ADDR_O`** — the LINEAR ADDRESS of the cycle that owns the bus.  **VALID
  FROM** the announcement clock (carrying the ANNOUNCED cycle's address)
  **THROUGH** the whole of that cycle's T1 / T2 / Tw / T3 / T4 (carrying the
  RUNNING cycle's).  **Never meaningless**: with nothing running it holds the
  last running cycle's address, which is what the real part's pads show by
  retention.  An INTA announces no address and it reads **zero** there — that
  zero is the part's own `Access::no_addr`, not a placeholder.
* **`DATA_O`** — the WRITE WORD of the cycle that owns the bus, in bus byte
  order (swapped on an odd address).  **MEANINGFUL** from the owning WRITE
  cycle's T1 through its T4.  On a READ cycle it holds the previous write's
  word and is **DECLARED MEANINGLESS** — the multiplexed view never published
  it there either, so nothing has ever depended on it.
* **`STATUS_O`** — `{md8080, psw_ie, seg[1:0]}`, the nibble A19-16 carries
  whenever it is not carrying an address.  **MEANINGFUL for the whole of the
  owning cycle**, and it follows the SAME owner the address does: the
  ANNOUNCED cycle's segment while a display holds the bus, the RUNNING cycle's
  otherwise.
* **`DATA_I`** — read data.  Nothing about *when* the core samples changes;
  it is the existing `ad_i` path with a different source.

**NO NEW FLOP AND NO NEW STATE.**  Every source is a register or the
register-only pairing lookahead already documented at `v30u_biu.sv`'s
`cur_data_o`.  **There is deliberately no "address valid" strobe** — the real
part in max mode announces with `BS` (S0-S2) and the bus controller derives the
rest; this interface does the same, with `BS` / `RD_N` / `UBE_N` unchanged.
A strobe would be a pin the die does not have.

### 2.2 `DATA_I` — A SURFACED DESIGN DECISION

The brief's port list names three OUTPUTS.  `AD` is an `inout` and it is the
core's ONLY read-data path, so removing it removes the core's ability to
receive.  `DATA_I` is that path in the de-muxed configuration, and it is
`ifndef V30_MUXED_AD` **by ruling 1's own logic**: it is the muxed
configuration that does not need it, because `AD` carries it there.  The two
are exclusive in exactly the way `AD`'s output half and `ADDR_O`/`DATA_O` are.

---

## §3 TWO FINDINGS

### 3.1 THE AD OUTPUT LATCH IS NOT PRESENTATION — F58 MAKES IT MACHINE STATE

**The define-OFF build refused to elaborate, and that is what the leg is for.**

```
%Error: v30u_biu.sv:2866: Can't find definition of variable: 'ad_oe_addr'
 2866 |     else if (ce && (ad_oe_addr || ad_oe_ps)) last_ad_hi <= ad_o[19:16];
```

`last_ad_hi` / `last_ad_lo` are the **AD output latch**, and they are not an
observation aid: **F58** (silicon, 1,189 HALT pseudo-cycles, no exception)
makes a HALT pseudo-cycle **PUBLISH** them — they feed `cmt_addr` / `cmt_data`
in step (e).  So the shared-pad drive is machine state with a functional
consumer, and a core that presented a de-muxed bus while dropping it would be
**a different machine from the one silicon measured**.

**Disposition, stated rather than worked around**: `V30_MUXED_AD` removes the
**PORTS** (`ad_o`/`ad_oe_*` on the BIU, `AD`/`AD_OE` on the top) and **not the
drive**.  A de-muxed build still computes what the core *would* put on shared
pads; it simply has no pads to put it on.  This is written into `v30u_biu.sv`
at THE AD OUTPUT LATCH and into both module headers.

### 3.2 `t1_half2` EQUALS `(bus_t1 || vfp)` AT EVERY `ce` — DERIVED, THEN ASSERTED

The latch's input needs the T1 phase, and §3.1 means a de-muxed build needs it
too — while ruling 1 removes `CE_HALF`, the flop's only enable.  The way out is
not a new flop:

> `t1_half2` is loaded at the cycle's `ce_half` from
> `(r_run && (r_ts == TS_T1)) || vector_follow_preview` — registers that do not
> move within a CPU clock — and **S-1** says at least one `ce_half` falls
> between consecutive `ce`s.  **So at every `ce`, `t1_half2` IS that
> expression**, and `ce` is the only instant the latch loads.

That is one wire, `bus_half`, `ifdef`-selected between the flop and the
expression.  **It is ASSERTED, NOT ASSUMED**: a sim-only check fires on any CE
clock where the two disagree, and it runs on every simulation leg in §5.

---

## §4 THE FALSIFIERS, AND THEIR NON-VACUITY

### 4.1 THE RECONSTRUCTION ASSERT

The historical nine-way mux is retained **VERBATIM** as the sim-only
`ad_o_ref` (with its four helper nibbles `t1_addr`, `disp_hi`, `dinta_hi`,
`cinta_hi`, which the composed form no longer needs) and compared against the
composed `ad_o` every fabric clock.

⚠ This is deliberately **not** the briefed "reconstruct from the ports and
compare to `ad_o`" — `ad_o` **is** that reconstruction now, so that comparison
would be a tautology.  This form compares the composition against the pin law
that 169,000 golden cases, 17,350 lockstep forms and every bitstream to date
were scored on, which is strictly stronger.
⚠ **ONE STATED HOLE**, as registered: the compare is skipped while the
reference carries an `X`, a pre-reset artefact of X-pessimism.

**NON-VACUITY (P-2), MEASURED.**  Scratch copy, ONE term perturbed —
`bus_ph_lo`'s T1 turnaround forced to 1 — driven by `tb_chain_lfsr`:

```
[29905000] %Fatal: v30u_biu.sv:1333: DE-MUX RECONSTRUCTION FAILED at 29905000
  -- composed AD d4c86, muxed law dfffb
     (addr_o d4c86 data_o fffb status_o 3 hi 1 lo 1)
```

### 4.2 THE `bus_half` EQUIVALENCE ASSERT

**NON-VACUITY, and ISOLATED.**  A second scratch copy moved `t1_half2`'s enable
from `ce_half` to `ce` — a perturbation that leaves the reconstruction assert
satisfied, because both sides of it read the same flop:

```
[1985000] %Fatal: v30u_biu.sv:1286: bus_half EQUIVALENCE FAILED at 1985000
  -- t1_half2 0 but (bus_t1 || vfp) 1 at a CE instant
```

It fires **first and alone**, which is what makes it an independent falsifier
rather than a second view of the same one.

### 4.3 THE MACRO GUARD — `SYNTHESIS` WITHOUT `V30_MUXED_AD` IS REFUSED

**This one is a hazard the wave found in itself.**  The rig's entire
observation path is multiplexed pins (`nec_bus` samples `core_ad` twice per CPU
clock; the X1 model keys on `core_ad_oe`).  Had the macro been dropped from
`hdl/nec_test.qsf`, `system_large`'s `ifdef`s and the core's would have **agreed
with each other**, the build would have SUCCEEDED, and the rig would have
observed an undriven bus — the accepted-and-ignored class the FLASH #18
`X1_AD_RETENTION` finding (**E-6**) records.

So the combination is refused at ELABORATION by naming a module that does not
exist, and the error message is the diagnosis:

```
%Error: hdl/rtl/system_large.sv:506: Cannot find file containing module:
        'V30_MUXED_AD_IS_REQUIRED_TO_SYNTHESISE_system_large'
```

**Non-vacuous both ways**: it fires with `-DSYNTHESIS` alone and is silent with
`-DSYNTHESIS -DV30_MUXED_AD`.

**AND THE MACRO IS PROVED TO HAVE REACHED QUARTUS POSITIVELY**, not by "it
compiled" — the CONTROL build's `nec_test_ucore.map.rpt` port-connectivity
table for `v30_core:u_core` carries `AD_OE`, which does not exist without it:

```
; AD_OE    ; Output ; Info ; Connected to dangling logic...
; ADDR_O   ; Output ; Info ; Explicitly unconnected
; DATA_O   ; Output ; Info ; Explicitly unconnected
; STATUS_O ; Output ; Info ; Explicitly unconnected
```

— which is also **§6's pruning expectation, met exactly as registered**.

---

## §5 THE DEFINE-OFF PROOF (P-3) — `sw/demux_off_gate.py`, THREE LEGS

New harness `hdl/tb/tb_demux_min.sv`: `v30_core` with **no `AD`, no `AD_OE`, no
`CE_HALF`**, fed from a 1 MiB LFSR memory addressed by **`ADDR_O` read LIVE in
the data phase** (no T1 latch — that is the point), read data on **`DATA_I`**,
stores committed from **`DATA_O`**, `STATUS_O` recorded.  It is **not** a
scorer: there are no goldens for a bus this shape and inventing some would be
fitting.  Its bars ask only that the core is really running.

| leg | result |
|---|---|
| **RUN** 200,000 fabric clocks | `FPOPS` **2,742** ≥ 1 · `BS_KINDS` **7** ≥ 4 · `WRITES` **1,390** ≥ 1 · `ADDR_MOVES` **7,729** ≥ 1 — **all four MET**, `RESULT OK`, clean build |
| | `BS_HIST` INTA 4 · IOR 86 · IOW 55 · HALT 4 · CODE 3,201 · MEMR 2,754 · MEMW 1,873; `PS_SEEN` `00ff` (all eight nibble values) |
| **GONE** | `.AD`, `.AD_OE`, `.CE_HALF` each spliced back into the instantiation → **REFUSED, pin named**, 3 of 3 |
| **ON** (the control) | the same TB built WITH the define → **REFUSED, `DATA_I` named** — so the first leg's success is the define's doing |

**P-OFF-3**: `ss_lint --core ucore` is unmoved at **232 / 221 flops / 0
UNMAPPED** with the define ON, so the new `ifdef` does not perturb
`ss_flopcensus`'s notion of a synthesised region.

### 5.1 THE SAVE-STATE CONSEQUENCE, DOCUMENTED NOT PAPERED OVER

With the define **ON** — the rig configuration, and the only one any standing
gate scores — the flop exists, `SSA_B_T1_HALF2` reads it, and `SS_VERSION` /
`SS_COUNT` / `SS_TAG` and the flop census **do not move**.  `v30u_ss_pkg.sv` is
**not edited**.

With the define **OFF** the flop does not exist, that address falls to the
`default` arm and reads `16'h0000`, and **a define-OFF build is a DIFFERENT
save-state stream by construction**.  It is not stream-compatible with the
rig's and must not be loaded into one.  `SS_VERSION` is deliberately **not**
bumped: bumping it would move the tag of a configuration that still has the flop.

---

## §6 THE LADDER — ZERO DELTA (P-1)

| leg | registered | measured | Δ |
|---|---|---|---|
| `check_core --opcodes all --cases 0` (div **4**) | 169,000 / 169,000 | **169,000 / 169,000** | **0** |
| `check_core --opcodes all --cases 0` (div **2**) | 169,000 / 169,000 | **169,000 / 169,000** | **0** |
| `--opcodes 8F.0` | 500 / 500 | **500 / 500** | 0 |
| `s10-hltsweep-w0 --waits 0` | 97 / 97 | **97 / 97** | 0 |
| `s10-hltsweep-w1 --waits 1` | 93 / 95 | **93 / 95** | 0 |
| `s13-hltsweep-w2 --waits 2` | 45 / 46 | **45 / 46** | 0 |
| `s13-hltsweep-w3 --waits 3` | 44 / 45 | **44 / 45** | 0 |
| **the four sweeps** | 279 / 283 | **279 / 283** | **0** |
| `f4a_boundary --waits 0` | 160 / 160 | **160 / 160** | 0 |
| `f0lock_tranche --waits 0` | 400 / 400 | **400 / 400** | 0 |
| `v0.1-w1` / `-w3` | 1,200 each | **1,200 / 1,200** each | 0 |
| `v0.1-w1 --opcodes EB` | 200 / 200 | **200 / 200** | 0 |
| the four `evt` cells | 200 · 1,200 · 200 · 1,200 | **200 · 1,200 · 200 · 1,200** | 0 |
| `v0.1-w1evt-biased` | 1,200 / 1,200 | **1,200 / 1,200** | 0 |
| `check_boot --core ucore --timed 220` / `400` | MATCH / MATCH | **MATCH 220** / **MATCH 400** | 0 |
| `ulockstep --golden all --cases 50` | 17,350 / 17,350 | **17,350 / 17,350** | **0** |
| `sm3_s16_score --core ucore` | `busstat_other` 24 · `ARCH` 27 | **24 · 27** | 0 |
| `check_ab_sim --core ucore` | MATCH 187 rows | **MATCH 187 rows** | 0 |
| `ghost_launch_law score` | 200 / 200 = 100.0 % | **200 / 200 = 100.0 %** | 0 |
| `qdepth_probe` | `rdq` 0:264 1:49 2:34 · `rd_done` 0:102 1:245 | **identical** | 0 |
| `chain_lfsr_gate` | PASS, depth [6], 0 overflows | **PASS**, `CHAIN_MAX` 7, depth [6], 0 overflows, `coincide` 0 | 0 |
| — its four signatures | committed `chain_lfsr_sig.json` | **BYTE-IDENTICAL, 4 / 4** | **0** |
| `r7_lint` | PASS 20 / 1 / 3 / 51 / 0 | **PASS** — 20 nets / 1 carrier / 3 tainted / 51 `stop` / 0 violations | 0 |
| `ss_lint --core ucore` | 232 / 221 flops / 0 UNMAPPED | **PASS, 232 / 221 / 0** | **0** |
| `test_artifact` | 45 / 45 | **45 / 45**, non-vacuous | 0 |
| `test_quartus_gate` | 254 / 255 | **254 / 254** bare, **255 / 255** with a build tree | 0 |
| `gen_ucore_qsf --check` | clean | **clean** | 0 |
| `ucrom_mif_check` | PASS 8,192 / 1,028 | **PASS**, `ucdecode` 8,192 / 8,192 and `ucrom` 1,028 / 1,028 identical | 0 |

### 6.1 THE `tb_sys` LEGS — 2,728 DIRECTED CELLS BYTE-IDENTICAL BY CONTENT

| leg | result |
|---|---|
| `ie_pinfall_cell core` | **2,200 cells**, **13 / 13 data files IDENTICAL by decompressed content**; `manifest.json` moved on `receipt`, `seconds`, `ts` only |
| `ghost_pred_cell core` | **528 cells**, **133 / 133 data files IDENTICAL**; `manifest.json` moved on `git`, `receipt`, `seconds`, `ts` only |
| `fz2_replay --all-failures --pass-sample 200 --leg ret` | **307 seeds** (107 fabric-FAIL, 200 fabric-PASS), **AGREEMENT 307 / 307 = 100.0 %**, `first_bad` **IDENTICAL on 107 / 107**, 0 errors |

⚠ **COMPARED BY DECOMPRESSED CONTENT, NOT BY `.gz` BYTES** — gzip embeds an
mtime, so a `.gz` `sha256` diff is not evidence of a data change.
`ghost-pred/core/SHA256SUMS` differs for exactly that reason: it is a list of
`.gz` hashes.  **Both directories were then REVERTED to their committed bytes**
(the precedent is `ce_contract_correction_results_2026-08-13.md` §7.1): they
carry no new information, and committing 147 files whose only change is an
embedded mtime would put unreadable churn in front of the next diff.

⚠ **ALL THREE WERE RE-RUN ON THE FINAL TREE.**  They were measured once before
the §4.3 macro guard landed in `system_large.sv` and re-measured after, with
identical results, rather than argued from the guard being inside
`ifdef SYNTHESIS`.

⚠ **THE `fz2_replay` ERA OVERRIDE IS STATED, NOT WORKED AROUND**, exactly as
pre-registered: this wave moves `v30_core.sv`, `v30u_biu.sv`, `system_large.sv`
and both `.qsf`s, so the fabric-era guard refuses.  Run with
`--no-fabric-era-guard` against `fz2_failure_ledger_f21_2026-08-13.json`;
**no fabric claim is made from it.**  The fz2 captures are gitignored and
main-only and were reached by **read-only symlink**; `tb_sys` was **rebuilt**.

### 6.2 ⚠ ONE LEG DID NOT COME BACK CLEAN, AND IT IS NOT THIS WAVE'S

**`fz2_immaterial falsify` — G6 and G7 FAIL; G1-G5 and G8 PASS**, exactly as
pre-registered and **character for character the same failure**
`ce_contract_correction_results_2026-08-13.md` §7.2a recorded:

```
G6 THE CENSUS   : 3 / 8 registered cells disagree with the derivation
                  FUNCTIONAL doc 44 != derived 46
                  TIMING     doc 30 != derived 29
                  total      doc 106 != derived 107
G7 THE DOCUMENT : WORKING-RESIDUE headline (84, 106, 22) != derived (85, 107, 22)
```

These clauses compare a **census document's** numbers against the **ledger's**.
This wave edited neither — nothing in its diff can reach a markdown census or a
JSON ledger.  **BOOKED as pre-existing and deliberately NOT re-derived here**:
re-deriving a census inside an unrelated wave is how a number stops being
readable against its own history.

⚠ The DEFAULT ledger still cannot be scored in a worktree (`CAPTURE SHA
MISMATCH fz2c/404049`), so the F21 ledger was named explicitly.  An environment
property, stated, not a defect of the wave.

---

## §7 G6 — ONE DRAW PER CONFIGURATION (P-5)

⚠ **Per the quoting rule these are `draw@seed<S>` figures and NOT an Fmax
claim, and not a band.**  `standing_gates.md` §A governs; one green build is
not closure.

| | registered (near) | **measured `draw@seed<default>`** | worst setup | ALMs | receipt |
|---|---|---:|---:|---:|---|
| **CONTROL** | 38.01 / +6.618 / 10,155 | **39.64 MHz** | **+7.825 ns** | **10,190 (24 %)** | `0ba1454e2baf30ec…` |
| **RETENTION** | 39.62 / +7.277 / 10,162 | **40.49 MHz** | **+7.311 ns** | **10,143 (24 %)** | `fbf0c7e7b0835423…` |

**BOTH PASS.**  TNS **0.000 setup AND hold on every domain** of both · **0
errors · 0 latches · 0 `lpm_divide`** · `E7_input_stability` clean with the one
declared §70.7 exemption (`hdl/nec_test_ucore.qsf`, which Quartus rewrites; it
was regenerated afterwards and `gen_ucore_qsf --check` is clean).

**THE TWO CHECKS THAT THE MACROS REACHED THE COMPILER, BOTH MET:**

* **E-9** — the `.rbf`s **DIFFER**: `5cecb4ccf4e05b97…` (CONTROL) vs
  `bde7607b56a7a6d3…` (RETENTION), on an **IDENTICAL 88-file input manifest
  `5c64c1e38182b2e2…`** — so the only difference is the compiler flag.
* **E-6** — the retention receipt **self-labels `RETENTION
  (X1_AD_RETENTION=1)`, DERIVED from the reports** and not from the flag.
* and for **`V30_MUXED_AD`** specifically, §4.3's positive evidence from the map
  report, which no flag can fake.

The live manifest recomputed after the landing commit is **`5c64c1e38182b2e2…`,
88 files — identical to both receipts**, so these figures are this tree's.

**THE PRUNING EXPECTATION IS MET AS REGISTERED** — §4.3's port table:
`ADDR_O` / `DATA_O` / `STATUS_O` are *"Explicitly unconnected"*, so the added
ports cost nothing in the rig integration.

⚠ **RECORDED, NOT EXPLAINED**: CONTROL drew **+1.63 MHz / +35 ALMs** and
RETENTION **+0.87 MHz / −19 ALMs** against the figures this tree last recorded.
Analysis & Synthesis is not reproducible run to run — the REGISTER counts are,
the COMBINATIONAL counts are not (`ucore_provenance.md` §74.4a) — and the
composed `ad_o` is a different netlist SHAPE from the nine-way mux even though
it is the same FUNCTION.  Both draws are green on every bar.

⚠ **THE RETENTION-VS-CONTROL SIGN IS POSITIVE AGAIN (+0.85 MHz)**, where the
ce-contract pair read +1.61 and FLASH #18 read −1.31.  Reported, not explained;
`standing_gates.md` §A governs and **one green build is not closure**.

---

## §8 THE BUILD-SITE AUDIT (P-6) — COMPLETE

| site | what it builds | disposition |
|---|---|---|
| `sw/check_core.py` | `tb_v30_core`, **both cores** | **`-DV30_MUXED_AD` added** |
| `sw/check_ab_sim.py` | `tb_ab` → `system_large`, both cores | **`-DV30_MUXED_AD` added** |
| `sw/chain_lfsr_gate.py` | `tb_chain_lfsr` (two call sites) | **`-DV30_MUXED_AD` added to both** |
| `sw/x1_retention.py` | `tb_sys` → `system_large`, `base` **and** `ret` | **`-DV30_MUXED_AD` added to BOTH legs**, so the pair still differs by ONE token and `receipt_diff --expect-command` still holds |
| `hdl/nec_test.qsf` | Quartus, FSM revision | **`VERILOG_MACRO "V30_MUXED_AD=1"`** |
| `hdl/nec_test_ucore.qsf` | Quartus, ucore revision | **derived**; `gen_ucore_qsf --check` clean |
| `sw/check_race_law.py` | `race_law_equiv_tb` | **no change needed** — it compiles `sw/race_law_equiv_tb.sv` and `race_law.svh` only; it does not instantiate the core |
| `sw/biu_law_*.py` (4 tools) | — | **no change needed** — all four shell out to `sw/check_core.py --build` |
| `sw/check_seq.py`, `sw/fz2_tbsys.py`, `sw/fz2_m10sys` | — | **no change needed** — they bind to the binaries the above build |

⚠ **A MISSED SITE WOULD HAVE FAILED LOUDLY**, which is why positive polarity
was chosen: a `.AD` connection to a port that does not exist is a
Verilator/Quartus **error**.  The one place that is *not* true — `system_large`,
whose own `ifdef`s would have agreed with the core's — is covered by §4.3's
guard.

---

## §9 WHAT M72 (OR ANY DOWNSTREAM INTEGRATOR) WOULD CHANGE

`docs/notes/m72_downstream_timing_2026-08-12.md` §1's demux adapter is
**obsoleted**, and the changes are subtractions:

1. **Build without `V30_MUXED_AD`.**  Drop `.AD`, `.AD_OE` and `.CE_HALF` from
   the instantiation; connect `.DATA_I` to the read word.
2. **Delete the address latch.**  The `ce_half`-negedge (or T1-falling)
   latch that reconstructed A19-0 from the shared pins has nothing to do:
   `ADDR_O` is a register output valid for the whole cycle.  Read it live.
3. **Delete the write-data capture.**  `DATA_O` is valid from the write
   cycle's T1; there is no turnaround to wait for and no odd-address swap to
   redo — the port is already in bus byte order.
4. **Delete the PS-nibble extraction.**  `STATUS_O` is `{md8080, psw_ie, seg}`
   directly, with no one-shot to track.
5. **Delete the half-phase generator.**  The catch-up train needs only `CE`.
   The C-a / S-1 contract goes with `CE_HALF`: **C-a is vacuous by
   construction** with one enable, and S-1 protected `t1_half2`, which a
   de-muxed bus does not have.
6. **Keep `BS` / `RD_N` / `UBE_N` and the T-state reconstruction unchanged** —
   that is the part's own max-mode protocol and it is what `tb_demux_min.sv`
   demonstrates.
7. ⚠ **Do not reuse a muxed save-state stream** (§5.1), and note the ONE
   behavioural difference the de-muxed shape carries: the split-read
   **vector-follow preview** publishes `ADDR_O` for the whole clock rather than
   from the T1 half, because the half exists only to share pins.

---

## §10 WHAT THIS WAVE DOES NOT DO

* It does **not** touch `hdl/rtl/core/` (the ARCHIVED FSM core).  Its
  `AD`/`AD_OE`/`CE_HALF` stay unconditional, so it is buildable **only** with
  the define ON — which every FSM build site has, because the define was added
  to the shared commands.  Stated as a limitation, not fixed.
* It makes **no fabric claim**.  Nothing was flashed and no board was touched;
  the FLASH #21 debt is unchanged.
* It does **not** change `nec_test.sdc`.
* It does **not** delegate to Codex and spawned no nested task.
* The de-muxed configuration has **no silicon evidence of its own** and cannot
  have any until something is built from it.  What is proved here is that it
  elaborates, runs a real instruction stream, and computes the same pin drive —
  not that a de-muxed integration is correct against the part.
