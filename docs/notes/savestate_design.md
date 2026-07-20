# Save-State Support for the V30 Core — Design Document

*(Architect-authored (fable), 2026-07-19, designed against the RTL at HEAD: `hdl/rtl/core/v30_core.sv` (260 l), `v30_biu.sv` (1741 l), `v30_eu.sv` (5118 l). USER DECISIONS APPENDED AT END.)*

---

## 0. Requirements and the bar

- Save and restore the **full** processor state.
- During save/restore the platform suspends CE/CE_HALF; the core is frozen mid-execution and state is streamed while nothing advances.
- Core-level ports stream state in/out in fixed-size **16-bit** chunks.
- Project bar: a save→restore cycle must be **perfectly invisible** — the post-restore cycle stream (all pins, all internal law state) must be bit-identical to an uninterrupted run, including under random wait states (the #1 project priority).

## 1. Save semantics: arbitrary-cycle full-state freeze (recommended)

**Recommendation: arbitrary-cycle freeze — save every architectural and micro-architectural flop.** Quiesce-to-boundary is rejected:

- Quiescing perturbs timing (it must insert or wait out cycles), which violates the invisibility bar by construction. Worse, this core's *whole verification methodology* depends on unperturbed cycle streams; a savestate that is only boundary-safe cannot be verified with the existing golden equivalence machinery.
- "Boundary" is ill-defined here anyway: the prefetch queue, the BIU law machinery (`law_window`, `occ34_age`, `recent_evx`, `pop_sr`), and pin pipelines (`int_p`/`nmi_p`) carry history *across* instruction boundaries. A boundary save would still have to capture nearly everything below.
- Feasibility is confirmed by the actual count (Section 2): total core state is **~1,146 bits ≈ 72 sixteen-bit words**. This is tiny. There are **no inferred RAMs that need special handling** (see 2.3).

## 2. State inventory

Method: every `reg`/`output reg`/enum register in the two modules (v30_core itself has zero flops; its `bkd_*` tie-offs are constants). Synthesis-guarded sim probes are excluded but addressed in 2.4.

### 2.1 `v30_biu.sv` — 295 bits (19 words after padding)

| Group | Fields (width) | Bits | Notes |
|---|---|---|---|
| T-state machine | `state`(3) | 3 | plain `reg [2:0]`, no enum cast needed |
| Current bus cycle | `cur_type`(3) `cur_addr`(20) `cur_fetch` `cur_wr` `cur_swap` `cur_split1` `cur_split2` `cur_wrap` `cur_wdata`(16) `cur_seg`(2) `cur_ube_n` `cur_kind`(2) | 50 | mid-bus-cycle identity |
| Staged commit | `nxt_valid` `nxt_type`(3) `nxt_addr`(20) `nxt_fetch` `nxt_wr` `nxt_swap` `nxt_split1` `nxt_split2` `nxt_wrap` `nxt_wdata`(16) `nxt_seg`(2) `nxt_ube_n` `nxt_kind`(2) | 51 | committed-next descriptor |
| Pin/handshake flops | `ube_n` `eu_started` `eu_hand` `eu_rdata`(16) | 19 | output regs |
| Eval machinery | `tw_any` `evald` `defer_t4` `defer_idle` `eval_ext` `flush_hold` `ext_flushed` `ready_prev` `eu_req_p1` `eu_req_p2` `eu_ready_p1` `eu_ready_p2` `tw_par` | 13 | wait-state law state; **must** be exact or waited resumes diverge |
| **`t1_half2`** | (1) | 1 | **negedge flop, `ce_half` domain** — see 4.4 |
| Grid parity | `ph_ff` `gph_ff` | 2 | free-toggling — restore exactly, never re-derive |
| LOCK | `lock_active` `lock_done` | 2 | |
| Prefetch queue | `q_mem[0..5]`(48) `q_rd`(3) `q_wr`(3) `q_cnt`(3) `q_avl`(3) `q_aged`(2) `q_head_dry_q` | 63 | see 2.3 — flops, not RAM |
| Fetch pointer / in-flight | `fetch_discard` `fetch_cs`(16) `fetch_off`(16) `fetch_data`(16) `push_pend`(2) `push_pend_hi` | 52 | includes in-flight fetch data + pending push |
| Display law | `e_wait` `halt_t1` `halt_done` | 3 | |
| Class-5 / heuristic history | `occ34_age`(4) `pop_sr`(8) `recent_evx`(4) `last_was_store` | 17 | consumption/age history — part of the decision laws |
| Class-5 unified law | `law_tw_cnt`(4) `law_dtw`(4) `law_dcnt`(3) `law_window` `law_ctr`(3) `law_sel`(3) `law_prov` | 19 | freezing mid-`law_window` must restore exactly |
| **Total** | | **295** | pad to 304 = **19 words** |

### 2.2 `v30_eu.sv` — 851 bits (54 words after padding)

| Group | Fields (width) | Bits | Notes |
|---|---|---|---|
| Architectural | `rf[0..7]`(128) `sr[0..3]`(64) `psw`(16) `pc`(16) `arch_ip`(16) | 240 | |
| Sequencer | `state`(7) `wnext`(7) `dret`(7) `dly`(6) | 27 | **`state_e` enums — explicit `state_e'()` cast on restore** |
| Divider unit | `div_rem`(17) `div_quo`(16) `div_den`(16) `div_cnt`(6) `div_busy` `div_word` `div_signed` `div_nsign` `div_dsign` `div_pend` `div_late` | 62 | mid-divide freeze supported |
| Shift/rotate unit | `sh_r`(16) `sh_x`(8) `sh_oth`(8) `sh_cy` `sh_op`(3) `sh_wf` `sh_n`(8) `sh_busy` `sh_fbase`(16) `sh_res`(16) `sh_fl`(16) | 94 | |
| Instruction latches | `opc`(8) `opc2`(8) `mrm`(8) `immb`(8) `disp`(16) | 48 | |
| ADD4S loop | `a4_cnt`(8) `a4_k`(8) `a4_src`(16) `a4_carry` `a4_z` | 34 | |
| Operand/trap latches | `mem_op`(16) `ivt_off`(16) `ivt_seg`(16) `trap_psw`(16) | 64 | |
| Prefix latches | `seg_ovr_en` `seg_ovr`(2) `lock_en` `rep_en` `rep_kind`(2) | 7 | |
| Flush/string/REP | `flush_now` `str_wr` `rslot`(6) `rep1_abort` `str_done` `cmp1`(16) `cmp_r2s` `fl_cs`(16) `fl_ip`(16) | 59 | mid-REP freeze (S_STRR/S_STRS/S_STRW/S_OUTS/S_INS) covered by `state`+these |
| Mem-form microstate | `ea_save`(20) `ea_save_seg`(2) `ldp2` `fret_ph`(2) `facc`(2) `iret_pw` `popr_pend` `prep_acc` `pracc`(3) `w4skip` `prep_bpd` `shw`(9) `popm_hold`(6) | 50 | |
| INS/EXT bit-field | `ie_off`(4) `ie_len`(5) `ie_fld`(16) `ie_w0`(16) `ie_mode`(2) `ie_ph2` `ie_dly`(12) `ie_chain` `ie_rdyhold` `ie_lgot` | 59 | |
| Interrupt machinery | `int_p`(4) `nmi_p`(5) `nmi_latch` `poll_s1` `shadow` `ie_pend` `ie_val` `psw_old`(16) `pop_pend` `ie_p`(4) `waits_seen` `post_flush` `insn_ip`(16) `ivt_vec`(8) `hwake_ie0` `irq_disp` `irq_nmi_ivt` | 64 | pin pipelines and inhibit shadows — restore exactly |
| BIU-side output regs | `eu_wr` `eu_word` `eu_addr`(20) `eu_seg`(2) `eu_wdata`(16) `eu_kind`(2) `halt_disp` | 43 | set in the FSM, held across cycles — state, not Moore |
| **Total** | | **851** | pad to 864 = **54 words** |

Not state (verified): `eu_req/eu_ready/eu_soon` (always_comb Moore), `q_pop/q_first/q_flush/flush_fast/eu_fwd/eu_wrap/eu_rsv_*/eu_lock` (assigns), all `pick_*`/slot arbiter wires, `race_rom[0:1023]` (write-never ROM loaded by `$readmemh` — constant, excluded; must *stay* a ROM after this change, see gate G6).

**Grand total: 295 + 851 = 1,146 bits → with padding and 1 tag word: 74 stream words (148 bytes).**

### 2.3 Inferred-RAM audit

- `q_mem[0:5]` (6×8): dual same-cycle writes (`push_now==2`) + async read — infers as registers today. Flopped; chains normally.
- `rf[0:7]`, `sr[0:3]`: many async read ports — registers. Chains normally.
- `race_rom[0:1023]` (16b): constant ROM (M10K/MLAB). **Excluded from the chain.** Gate G6 verifies it still infers as ROM after the edit.
- No other memories. **Nothing needs RAM-style sequenced readout.**

### 2.4 Sim-only registers (excluded, but must be handled)

`law_dcnt_probe` and `cyc_saw_tw` (both under `ifndef SYNTHESIS`) mirror chain state. After a restore they would be stale and SVA4 could fire spuriously. **Rule: inside their existing `ifndef SYNTHESIS` blocks, add the same `ss_restore` branch loading them from the same shadow slices as their mirrored registers** (`law_dcnt`, and `cyc_saw_tw <= restored tw_any`-equivalent, i.e. clear on restore is acceptable since `GRID_PHASE_STRICT` is off — document the choice in a comment). Chain *width* must not depend on `ifdef`s: these probes read the shadow, they do not add to it.

**Implementation-phase audit item:** the EU FSM declares block-local `logic` temps inside the `always_ff` (e.g. `cont`, `early*`, `den8` at lines ~1780–4441). SV block-locals are static; if any is read before written on some path it is hidden state. The worker must lint each (they all appear to be write-before-read temps) and note the audit result in the doc. Any that turns out to be real state gets promoted to a module-level reg and added to the chain.

## 3. Mechanism: per-module shadow segment with parallel capture/restore (recommended)

Three candidates were weighed:

1. **Scan chain through the core flops themselves** (rotate to read out). Rejected: while rotating, every pin (BS, AD, `ad_oe_*`) is a function of garbage state — the AD inout could actively fight the external bus; an aborted save corrupts state; and it still needs a mux on every flop's D input, so it saves nothing over option 3.
2. **MiSTer `SaveStateBus` register wrappers** (FPGAzumSpass idiom: every reg re-declared through an `eReg_SavestateV` instance on an address/data bus). Rejected for the *core*: it would rewrite every verified `always_ff` — unacceptable churn against RTL whose value is its verified-exactness. (The MiSTer *wrapper* can still adapt our stream onto that ecosystem's 64-bit savestate bus later — 4 chunks per word.)
3. **Shadow segment (recommended):** each module owns a dedicated shadow shift register of its padded width. `SS_CAPTURE` parallel-copies all state into the shadow in one clk (read-only on core flops — zero impact on core logic cones); `SS_SHIFT` moves 16-bit words along the shadow toward `SS_DOUT` / from `SS_DIN`; `SS_RESTORE` parallel-loads all core flops from the shadow in one clk.

Why 3 wins:

- **Save is non-destructive and abort-safe**; save→restore→save idempotence is trivial; pins never move during shifting (core state untouched, CEs off).
- **Cost:** ~1,168 shadow flops + capture/shift muxes ≈ 600–700 ALMs on the Cyclone V SE (5CSEBA6, 41,910 ALMs) — under 2%. Acceptable.
- **Timing:** the only touch on normal paths is the restore branch: one 2:1 mux at the head of each state flop's D input (`if (ss_restore) x <= u.x; else` prefixed to the existing if-chain). Worst case +1 LUT level (~0.3–0.5 ns on CV) against the current ~+5 ns slack; capture paths are single-LUT shadow loads. Gate G6 pre-registers the slack check. Fallback if it ever bites: Quartus maps this pattern to ALM synchronous-load naturally; no redesign anticipated.
- **Quartus 17.1 safety:** everything is plain `always_ff`, member-wise struct assigns, positional concatenation. **Never** the `'{field: value}` aggregate pattern (known synth bug, commit f43927f).

### 3.1 Single-source layout (anti-drift by construction)

New file `hdl/rtl/core/v30_ss_pkg.sv`:

```systemverilog
package v30_ss_pkg;
  localparam int SS_VERSION   = 8'h01;
  localparam int SS_BIU_WORDS = 19;
  localparam int SS_EU_WORDS  = 54;
  localparam int SS_WORDS     = 1 + SS_BIU_WORDS + SS_EU_WORDS;  // + tag
  localparam logic [15:0] SS_TAG = {8'(SS_VERSION), 8'(SS_WORDS)};

  typedef struct packed {           // field order below == Section 2 tables
    logic [2:0]  state;
    logic [2:0]  cur_type;  logic [19:0] cur_addr;  /* ... every BIU field ... */
    logic [8:0]  pad;               // explicit pad to 19*16
  } ss_biu_t;

  typedef struct packed {
    logic [15:0] rf0, rf1, /* ... */ ;
    logic [6:0]  state;  logic [6:0] wnext;  logic [6:0] dret;  /* ... */
    logic [12:0] pad;               // explicit pad to 54*16
  } ss_eu_t;
endpackage
```

Per module (sketch, BIU shown; EU identical in shape):

```systemverilog
import v30_ss_pkg::*;
localparam int BIU_W = SS_BIU_WORDS*16;

ss_biu_t ss_pack;                       // capture image (comb)
always_comb begin
  ss_pack = '0;                         // pads zeroed; then member-wise:
  ss_pack.state    = state;
  ss_pack.cur_type = cur_type;
  /* ... one line per field, NAMED ... */
end

reg  [BIU_W-1:0] ss_sh;                 // shadow segment
always_ff @(posedge clk) begin
  if (ss_capture)      ss_sh <= ss_pack;
  else if (ss_shift)   ss_sh <= {ss_din_seg, ss_sh[BIU_W-1:16]};
end
wire [15:0]     ss_dout_seg = ss_sh[15:0];
ss_biu_t        ss_u;
assign ss_u = ss_biu_t'(ss_sh);         // restore view

// elaboration-time width guard: any drift fails the BUILD, loudly
generate if ($bits(ss_biu_t) != BIU_W) ss_width_mismatch_biu fatal(); endgenerate
```

Restore is distributed into the **existing** sequential blocks (BIU has ~12: main FSM, `recent_evx`, `last_was_store`, `tw_par`, `q_head_dry_q`, `ph_ff`, `gph_ff`, lock, `ready_prev`, req/ready pipes, law block, `t1_half2`; the EU has exactly **one** giant `always_ff`, so its entire restore is a single branch at its top):

```systemverilog
always_ff @(posedge clk) begin
  if (ss_restore) begin
    x <= ss_u.x;  y <= ss_u.y;          // only fields owned by THIS block
  end else if (srst) begin ...
  end else if (ce) begin ...
```

`ss_restore` takes priority over `srst` (contract forbids co-assertion; add a Verilator-only assertion). EU enum fields restore with explicit casts: `state <= state_e'(ss_u.state);` (same for `wnext`, `dret`) — implicit enum assignment from a bit-slice is illegal SV and Quartus 17.1 would object.

**Why drift cannot be silent:** (a) width guard fails the build if a struct edit and the word-count constant disagree; (b) a field added to the RTL but forgotten in pack/unpack is caught deterministically by the scramble-restore gate (Section 6) — which becomes part of the standard golden gate set, run every campaign; (c) the stream self-describes via the tag word (version + word count) and restore raises `SS_ERR` on mismatch. Rule: **any edit to `ss_biu_t`/`ss_eu_t` bumps `SS_VERSION`** (review-checked; the width guard forces the editor into the package file where the version sits two lines up).

## 4. Port-level interface

### 4.1 New `v30_core` ports (always present — synthesized, not ifdef'd; MiSTer is the point)

```systemverilog
    // save-state (all synchronous to CLK; only legal while CE==0 && CE_HALF==0)
    input             SS_CAPTURE,  // 1-clk pulse: shadow <= live core state
    input             SS_RESTORE,  // 1-clk pulse held through the following
                                   // negedge: core state <= shadow
    input             SS_SHIFT,    // word-shift enable, one 16-bit word / clk
    input      [15:0] SS_DIN,
    output     [15:0] SS_DOUT,     // registered tail of the chain
    output            SS_ERR,      // sticky: tag word mismatch at last restore
    output            SS_BUS_QUIET // quiet-bus window predicate (see §5) [USER-APPROVED ADDITION]
```

Widths/word count exported via `v30_ss_pkg::SS_WORDS` (TB, harness, and later the MiSTer wrapper import it). The harness/synth top that doesn't use savestate ties `SS_CAPTURE/SS_RESTORE/SS_SHIFT/SS_DIN` to 0 — with strobes low, every added branch is untaken and behavior is bit-identical by construction (gate G1 proves it).

### 4.2 Chain topology and stream order

`SS_DIN → [EU segment: words 73..20] → [BIU segment: words 19..1] → [tag word 0] → SS_DOUT`.

Word `i` of the stream = position `i` from the DOUT end. A full shift-out emits words 0,1,…,73; feeding that identical sequence into `SS_DIN` with 74 shifts lands every word back at its original position (FIFO property) — **the save stream is the restore stream, verbatim**. Within a segment, word `k` = `ss_sh[16k +: 16]`; field order inside the packed structs is authoritative (Section 2 table order, pads at segment tail).

Word map:

| Words | Content |
|---|---|
| 0 | `SS_TAG` = `{version[7:0], word_count[7:0]}` (constant, captured by v30_core's 1-word head segment) |
| 1–19 | BIU segment (`ss_biu_t`) |
| 20–73 | EU segment (`ss_eu_t`) |

### 4.3 Sequences (platform side; "pulse" = one CLK)

**Freeze:** stop the CE train *only at a CPU-cycle boundary* — never between a CE posedge and its partner CE_HALF negedge (at `ce_div>1` the TB/platform parks `ce_cnt`). Wait ≥1 clk.

**Save:** pulse `SS_CAPTURE`; then repeat `SS_WORDS` times { sample `SS_DOUT`; pulse `SS_SHIFT` }.

**Restore:** repeat `SS_WORDS` times { drive `SS_DIN = stream[i]`; pulse `SS_SHIFT` }; pulse `SS_RESTORE` (assert at a posedge, hold high through the following negedge, deassert at the next posedge); check `SS_ERR==0`.

**Resume:** wait ≥1 clk; restart the CE train. `RESET` must be 0 throughout; strobes are mutually exclusive; behavior with `CE==1` is undefined (sim assertion).

Who gates CE: **the platform.** The core needs nothing — CE=0 freezes it; the savestate machinery runs on raw `CLK` with its own strobes. This is exactly the MiSTer idiom (CE-gated core, savestate manager pauses CE and streams; the wrapper later packs 4 chunks per 64-bit DDR savestate word).

### 4.4 The `t1_half2` negedge flop

`t1_half2` (BIU, `always @(negedge clk) if (ce_half)`) is the one non-posedge state bit. Restore: extend its process to

```systemverilog
always @(negedge clk)
  if (ss_restore)      t1_half2 <= ss_u.t1_half2;   // SS_RESTORE held through this negedge
  else if (ce_half)    t1_half2 <= (state == ST_T1);
```

— hence the "hold SS_RESTORE through the following negedge" rule in 4.3. Capture on the posedge is safe: the flop is stable across the posedge (CE_HALF off).

### 4.5 Tag/err in `v30_core`

v30_core owns a 1-word shadow at the chain head that `SS_CAPTURE` loads with `SS_TAG`. On `SS_RESTORE`, compare the word sitting in that position against `SS_TAG`; mismatch sets sticky `SS_ERR` (cleared by `SS_CAPTURE` or `RESET`). Restore still writes the state (hardware stays simple); the **platform** must treat `SS_ERR=1` as fatal and reset the core instead of resuming.

## 5. Restore contract (external-bus coherence)

The core saves everything it owns, including mid-bus-cycle identity (`state`, `cur_*`, in-flight `fetch_data`, `push_pend`, `t1_half2`, req/ready history). Invisibility after restore therefore reduces to: **the platform must reproduce, from cycle k+1 onward, exactly the input sequence the uninterrupted run would have seen.** Concretely, the platform owns at restore time:

1. **Memory and I/O device contents** (its own savestate).
2. **The external address/UBE latch state** (addresses latch at T1's falling edge; a restore mid-T2/T3 means the address was driven in the past — the latch contents must be restored on the bus side, exactly as `hdl/rtl/nec_bus.sv` and any MiSTer memory adapter hold them).
3. **Wait-state generator state** — uniform counter position, random-wait LFSR (`wlfsr`) and bus index (`wbus_idx`), or wait-vector index. Mandatory: wait-state accuracy is priority #1, and a resumed run must draw the same Tw sequence.
4. **Pin levels**: INT (level-sensitive), POLL_N, NMI level (edge already latched internally, but the pipeline `nmi_p` continues sampling the pin on resume).
5. **Any in-flight read-data source** (in the TB/harness, data is combinational from latch+mem, so 1+2 suffice).

In a fully CE-gated MiSTer system this falls out automatically: the whole system freezes at the same instant and the wrapper savestates its own side. For platforms that *cannot* save their bus adapter, the fallback policy is to trigger saves only in a **quiet-bus window**: `bus_ts==0 (Ti) && BS==PASV && !nxt_valid && push_pend==0 && q_aged==0 && !eval_ext`. That is platform policy, **not** a core requirement — the core supports arbitrary-cycle freeze. This predicate is exported as **`SS_BUS_QUIET`** (user-approved). Quiet windows occur whenever the queue is full and the EU is executing, and always in HALT; they are not guaranteed within bounded time under adversarial REP+wait patterns, which is another reason the primary contract is "save the bus side too."

Contrast with the existing `V30_BACKDOOR` (`tb_v30_core.sv` ~line 579): `bkd_load` injects only architectural registers + queue image *at reset* and cannot express mid-instruction/mid-bus state. The backdoor stays as-is for case setup; savestate is the strict superset and is orthogonal to it (`scr_en` scripted-consumer mode is also unaffected).

## 6. Verification plan (pre-registered gates)

All driven through the existing `sw/check_core.py` + `hdl/tb/tb_v30_core.sv` flow against `tests/v30/v0.1`, `v0.1-w1`, `v0.1-w3`, and the wrand rig (`+wrand=1 +wseed=…`), with `tests/v30/v0.3` rows available for the wider coarse sweep.

**TB additions** (plusargs): `+ss_at=<cpu_cycle_k>`, `+ss_mode=<0|1|2>`, `+ss_scramble_seed=<n>`, optional `+ss_file=<path>`.

- **mode 1 — scramble-restore equivalence** (the workhorse): run the case; at CPU cycle k park the CE train; `SS_CAPTURE`; shift the 74 words out to a local array; shift in a full-toggle scramble pattern (seeded LFSR alternated with A5A5/5A5A) and pulse `SS_RESTORE` — this *deliberately corrupts every core flop through the restore datapath itself*; then shift the saved stream back in, `SS_RESTORE`, resume CE. Recording continues; the TB's own per-cycle observer is already CE-gated (Campaign-4 CE refactor), so its state does not advance during the operation. Any flop missing from pack **or** unpack leaves scrambled residue and diverges — this is the chain-completeness guard.
- **mode 2 — idempotence**: `SS_CAPTURE`; out→A; in A; `SS_RESTORE`; `SS_CAPTURE`; out→B; TB compares A==B word-for-word, prints PASS/FAIL.
- `check_core.py` grows `--ss-sweep[=stride]` / `--ss-cases=<list>`: per k it re-invokes the sim with `+ss_at=k` and diffs cycle rows exactly as today (row synthesis/diff code is unchanged).

**Pre-registered gates:**

| Gate | Content | Pass criterion |
|---|---|---|
| **G1** (no-op invariance) | Strobes tied 0; full existing goldens: v0.1 w0 (169000 rows), w1 (1200), w3 (1200), wrand baseline seeds; Verilator `--assert` on | bit-identical, 0 mismatches, 0 assertion fires |
| **G2a** (w0 full-k sweep) | 10 pre-registered forms, every k in the recorded window: ALU RMW mem (81), MOV store (89), REP MOVBK (F3 A4/A5, CW>1), CALL-far/RETF, Jcc taken (7x), DIVU trap (F7/6), IDIV (F7/7), HALT+NMI wake, INT dispatch (evt_mode 1), prefix chain (seg-ovr+LOCK+REP) | rows k+1…end byte-identical to golden, all k, all 10 |
| **G2b** (uniform waits) | same 10 forms × full-k under v0.1-w1 and v0.1-w3 — freezes land on Tw, `eval_ext`, `defer_*`, `law_window` cells by construction | 0 mismatches |
| **G2c** (coarse breadth) | 100 v0.1 cases + 50 v0.3 rows, k stride 7 | 0 mismatches |
| **G3** (idempotence) | mode 2 at 3 k values per case over the G2a/G2b sets | A==B always |
| **G4** (negative tests) | corrupt tag word → `SS_ERR=1`; flip 1 random non-pad stream bit in 20 trials → divergence or visible state delta detected (sensitivity check of the gate itself) | as stated |
| **G5** (random waits) | same 10 forms × full-k × 5 wrand seeds (the established 90000/90003/90007/90008/90018 family), plus one run with `+ce_div=4` and one with a 10,000-fabric-clk freeze dwell (proves CE-independence and strobe operation at arbitrary `ce_cnt` phase) | 0 mismatches |
| **G6** (synthesis) | Quartus 17.1 build of the synth top with SS tied off: ALM/reg delta reported; `race_rom` still infers as ROM; no inferred latches; setup slack ≥ +4.0 ns (from ~+5) | as stated |
| **G7** (silicon regression) | one physical A/B run (existing check_ab_hw flow) on the post-savestate bitstream | unchanged vs pre-savestate |

Per project convention, each phase closes with a Codex critical-review pass (challenge: "which flop is not in the chain?", "which freeze point wasn't swept?").

## 7. Scope split and phased plan

**RTL** (`hdl/rtl/core/`): `v30_ss_pkg.sv` (new), segments + restore branches in `v30_biu.sv`/`v30_eu.sv`, port threading + tag/err in `v30_core.sv`.
**TB** (`hdl/tb/tb_v30_core.sv`): ss modes, CE parking, scramble, stream dump.
**Harness** (`sw/check_core.py`): `--ss-sweep`, case selection, gate reporting.
**MiSTer wrapper** (later, out of scope now): adapter from the 16-bit chunk ports onto the MiSTer savestate bus/DDR format + platform-side bus/memory savestate.

| Phase | Content | Size | Gate |
|---|---|---|---|
| S0 | Commit this doc; `v30_ss_pkg.sv` skeleton (typedefs, widths, tag, width guards); no consumers | S | builds |
| S1 | BIU segment: pack comb, shadow, restore branches in all ~12 blocks incl. `t1_half2` negedge + sim-probe sync (2.4) | M | G1 full |
| S2 | EU segment (single-block restore, enum casts), block-local-temp audit (2.4), core threading, ports, tag/err | M–L (field lists are long but mechanical) | G1 full |
| S3 | TB modes 1/2 + check_core.py options | M | G2a + G3 at w0 |
| S4 | Waits coverage | M | G2b, G2c, G5 |
| S5 | Negative tests | S | G4 |
| S6 | Quartus synth + timing/ALM report + one board A/B run | M | G6, G7 |
| S7 | MiSTer wrapper + platform-side savestate | L (deferred) | — |

## 8. Risks

1. **Stale chain after future RTL edits** (the silent-corruption hazard). Mitigations: elaboration-time `$bits` width guard (build fails), named member-wise pack/unpack (no positional offsets anywhere), version-bump rule co-located with the guard, and — decisive — the scramble-restore gate joins the standard golden gate set, so a missing field diverges deterministically in CI, not silently in the field. Residual: a field present in both pack and unpack but *in different structs' positions* is impossible by construction (one struct, named members).
2. **Layout churn from active RTL campaigns**: any BIU/EU edit is a version bump. (Original architect note recommended landing after the class-5 branch merge — class-5 has since merged; the residual concern is the active suite campaign's small RTL surface. USER DECISION: implement after the string-I/O tranche completes.)
3. **Quartus 17.1 struct quirks**: use only member-wise assigns and positional concatenation; never `'{field: value}` (known bug, f43927f); explicit `state_e'()` casts. G6 is the backstop.
4. **Timing**: restore mux at the head of deep BIU cones (`prefetch_ok`/law logic). Expected ≤1 LUT level against +5 ns slack; G6 pre-registers ≥ +4.0 ns. Fanout of the three strobes (~1200 loads) is left to Quartus duplication; register per-module copies only if G6 says so (would add one cycle to the sequences — a spec change, so decide at G6, not silently).
5. **Pin behavior at the restore edge**: pins are stable at frozen values throughout shifting (core untouched); they step once at the `SS_RESTORE` edge to the restored cycle's values, including `ad_oe_*` possibly turning on. The platform must have the external bus consistent *before* resuming CE (Section 5). No extra gating needed in the core; document in the wrapper.
6. **Hidden state in EU block-local temps** — audit item 2.4; promoted to the chain if any is real.
7. **Sim-only probe desync** (SVA4 spurious fire) — handled per 2.4.

## 9. USER DECISIONS (2026-07-19, resolving the design's open questions)

1. **Version guard**: manual version byte (8-bit version + word count, bump-by-rule) — NOT a generated layout hash.
2. **`SS_BUS_QUIET`**: YES — add the output to `v30_core` now (reflected in §4.1).
3. **TB file-based cross-session restore**: NOT this campaign — in-session scramble-restore verification only.
4. **Sequencing**: implement AFTER the string-I/O (6C–6F) tranche completes (task #23, blocked by #18).
