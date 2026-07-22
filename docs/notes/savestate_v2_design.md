# Save-State v2 — Addressed Register-File Interface (replaces the shadow-shift-register design)

*Architect (fable), 2026-07-21. Supersedes the access mechanism of `docs/notes/savestate_design.md` (S0–S6/G7, closed 2026-07-20). The §2 state inventory of that doc (295 BIU bits + 851 EU bits, field-by-field) remains authoritative and is carried over verbatim into the address map below. RTL referenced at master 3ae6f44: `v30_biu.sv` (SS pack ~:201, shadow ~:288, restore arms at :513/:526/:563/:620/:682/:1218/:1662/:1684/:1734/:1783/:1786/:1867(negedge)/:1919 + sim probes :1710/:1990), `v30_eu.sv` (pack ~:247, shadow ~:370, single restore arm :1832), `v30_core.sv` (ports :53-59, tag/err :116-129, assertions :137-163).*

## 0. Directive and what changes

**User directive (verbatim intent):** "A large packed struct wastes a large amount of registers on the fpga, an input port should be an address and each address corresponds to a different value read or written. Don't pack multiple values into a single address unless it makes sense, like flags. Space efficiency is not super important."

**Change:** delete the ~1,184 shadow flops (304-bit BIU segment + 864-bit EU segment + 16-bit tag word) and the SS_CAPTURE/SS_SHIFT/SS_RESTORE chain. Replace with an **addressed register-file interface**: an address port selects one state element; a read mux returns it on `SS_RDATA`; a write strobe decodes into the **existing** core flops. New state added by this design: ~**60 flops** (command staging + registered read data) vs ~1,184 — a net saving of ≈ **1,120 registers**. The state *list* does not change; only the access mechanism does.

**Granularity rule applied (per directive):** one module-level register per address. No artificial concatenation of unrelated small fields. PSW stays one word because it *is* one 16-bit register (the user's "flags" case is already satisfied by the register itself). `q_mem` gets one byte per address (six independent registers — pairing them would be exactly the artificial packing the user vetoed). `rf[0..7]`/`sr[0..3]` one register per address. Fields wider than 16 bits (`cur_addr`, `nxt_addr`, `ea_save`, `eu_addr` = 20 b; `div_rem` = 17 b) split into two consecutive addresses (`_lo` = [15:0], `_hi` = remaining bits) — the data port stays 16-bit, which keeps the TB/`check_core.py` word-stream machinery and the future MiSTer wrapper on the same 16-bit granularity as today. This yields a strong audit invariant: **every RTL state register ↔ exactly one map symbol ↔ exactly one read-mux arm ↔ exactly one write-decode arm** (greppable; see §7).

## 1. Port interface

### 1.1 `v30_core` ports (replacing SS_CAPTURE/SS_RESTORE/SS_SHIFT/SS_DIN/SS_DOUT)

```systemverilog
    // save-state addressed access (synchronous to CLK; meaningful only while
    // CE==0 && CE_HALF==0; writes additionally illegal during RESET)
    input       [8:0] SS_ADDR,
    input      [15:0] SS_WDATA,
    input             SS_WE,       // 1-clk pulse per write; 1 write/clk max
    output     [15:0] SS_RDATA,    // registered; valid 2 clks after SS_ADDR
    output reg        SS_ERR,      // sticky: last tag write mismatched SS_TAG
    output            SS_BUS_QUIET // unchanged (quiet-bus freeze-point hint)
```

- **Address width 9 bits.** `SS_ADDR[8]` selects the module (0 = core/BIU, 1 = EU). This gives each region 256 slots against current occupancy 83 and 119 — permanent headroom for active campaigns (space efficiency explicitly not a priority; an 8-bit space would leave the EU only 9 spare slots).
- **Reads are free-running** (no read-enable): the read path is a registered mux into dedicated `ss_rdata` staging registers; it never touches core state, so there is nothing a read can perturb. Latency contract: present `SS_ADDR` at posedge N → `SS_RDATA` valid from just after posedge N+1 (sample at N+2). Reads while CE is running are legal but return torn/meaningless data — only reads with CE frozen are meaningful.
- **Registered read is mandatory**, not optional: the BIU mux is 83-way and the EU mux 119-way over 16 bits; registering removes it from every timing graph that matters (see §8, the +3.830 ns history).
- **Writes:** one per clock, `SS_WE` high for the cycle with `SS_ADDR`/`SS_WDATA` valid. Write takes effect internally one cycle later (staging — invisible to the platform except that back-to-back writes simply stream at 1/clk).
- **No negedge hold rule for the platform.** Deliberate improvement over v1: `v30_core` registers `SS_ADDR/SS_WDATA/SS_WE` once into `ss_addr_q/ss_wdata_q/ss_we_q` at posedge N and fans the *registered* copies to both modules. These are stable from just-after-posedge-N through negedge N+½ and until posedge N+1 — so the posedge flops write at N+1 and the `t1_half2` negedge flop writes at N+½ **from the same command**, with no external hold requirement. The old "assert SS_RESTORE at a posedge and hold through the following negedge" platform rule (v1 §4.4, and the TB race it caught in S3) is eliminated by construction. The staging register also solves the strobe-fanout question booked for S7 ("shadow-live strobe-register timing decision") — **that booked decision is mooted**: there is no shadow and the command is already registered once at the core level.
- **CE contract unchanged:** reads/writes only meaningful/legal while the platform has parked the CE train (writes: illegal otherwise). `RESET` low throughout. Sim assertions in `v30_core` (replacing the old strobe assertions):

```systemverilog
`ifndef SYNTHESIS
always @(posedge CLK) begin
    if (SS_WE && CE)    $error("SS_WE asserted while CE high (core not frozen)");
    if (SS_WE && RESET) $error("SS_WE asserted during RESET");
    if (CE   && ss_we_q) $error("CE resumed with SS command staging undrained (ss_we_q high)");
end
`endif
```

(The one-hot and negedge-hold assertions die with the strobes.)

- **Resume-drain contract (A2, platform-facing).** The command staging (`ss_we_q`, one posedge behind `SS_WE`) is the *other half* of the write path: the platform must not re-enable CE until it has drained. Concretely, the last restore write leaves `ss_we_q` high for one more posedge; if CE goes high on that posedge the core's FSM takes its `if (ss_we)` branch and **skips its state advance — a phantom wait cycle on resume** (found and fixed in A2, previously mis-attributed to a free-running grid-phase flop; the mechanical audit confirmed *no raw-clk core-state flop exists*, so the RTL contract was always correct — the tooling simply wasn't honouring this half of it). **Resume sequence the platform (and TB) must follow:** after the final restore write, drop `SS_WE` low, then take **one parked posedge** (CE still 0) so the staging drains `ss_we_q → 0`, then release CE **off a negedge** (mirroring the freeze, which asserts the park at a negedge) so the first resumed posedge sees `ce=1 && ss_we_q==0`. The `if (CE && ss_we_q) $error(...)` assertion above mechanises this rule so the next integration (MiSTer wrapper) cannot repeat the TB's original bug silently.

### 1.2 Module ports

`v30_biu`: delete `ss_capture/ss_shift/ss_restore/ss_din_seg/ss_dout_seg`; add `input [8:0] ss_addr, input [15:0] ss_wdata, input ss_we, output reg [15:0] ss_rdata`. Keep `ss_bus_quiet`. `v30_eu`: same (no bus_quiet). The core connects the **staged** copies (`ss_addr_q` etc.), not the raw ports.

### 1.3 Core-level plumbing, tag, and SS_ERR

```systemverilog
// command staging (single registration point; fans out to both modules)
reg [8:0]  ss_addr_q;   reg [15:0] ss_wdata_q;   reg ss_we_q;
reg        ss_sel_eu_q, ss_sel_tag_q;      // aligned with module ss_rdata regs
always_ff @(posedge CLK) begin
    ss_addr_q    <= SS_ADDR;
    ss_wdata_q   <= SS_WDATA;
    ss_we_q      <= SS_WE;
    ss_sel_eu_q  <= ss_addr_q[8];
    ss_sel_tag_q <= (ss_addr_q == SSA_TAG);
end
assign SS_RDATA = ss_sel_tag_q ? SS_TAG
                : ss_sel_eu_q  ? ss_eu_rdata : ss_biu_rdata;

// tag write = integrity check (replaces the old tag-word compare):
// writing SSA_TAG with a mismatching value sets SS_ERR; a matching write
// (or RESET) clears it. Restore tooling writes the tag as its first word.
always_ff @(posedge CLK) begin
    if (RESET) SS_ERR <= 1'b0;
    else if (ss_we_q && ss_addr_q == SSA_TAG)
        SS_ERR <= (ss_wdata_q != SS_TAG);
end
```

Address 0 (`SSA_TAG`) is the version/tag register: **read** returns `SS_TAG = {SS_VERSION, SS_COUNT[7:0]}`; **write** performs the integrity check. Hardware stays dumb: a mismatched restore still writes all state; the platform treats `SS_ERR=1` as fatal (unchanged policy). Delete `ss_tag_sh`.

## 2. The address map (single source of truth)

**Version: `SS_VERSION = 8'h02`** (new scheme; the v1 74-word stream is not representable on this interface, so no compatibility question — bump-by-rule convention continues). **`SS_COUNT = 202`** mapped addresses (1 tag + 82 BIU + 119 EU). **`SS_TAG = 16'h02CA`**.

Regions: `0x000` tag · `0x001–0x052` BIU (dense, 82) · `0x053–0x0FF` reserved · `0x100–0x176` EU (dense, 119) · `0x177–0x1FF` reserved. **Unmapped addresses read as `16'h0000`; writes to them are ignored.** **Append-only rule:** new fields append at the end of their module's dense region (never renumber); any map edit bumps `SS_VERSION` and the counts.

Read data is the field zero-extended to 16 bits; writes take `ss_wdata[w-1:0]` and ignore upper bits.

### 2.1 BIU region (module `v30_biu`, 82 addresses, 295 state bits)

| Addr | Field | W | Notes |
|---|---|---|---|
| 0x001 | `state` | 3 | T-state machine (plain reg, no cast) |
| 0x002 | `cur_type` | 3 | |
| 0x003 | `cur_addr_lo` | 16 | `cur_addr[15:0]` |
| 0x004 | `cur_addr_hi` | 4 | `cur_addr[19:16]` |
| 0x005 | `cur_fetch` | 1 | |
| 0x006 | `cur_wr` | 1 | |
| 0x007 | `cur_swap` | 1 | |
| 0x008 | `cur_split1` | 1 | |
| 0x009 | `cur_split2` | 1 | |
| 0x00A | `cur_wrap` | 1 | |
| 0x00B | `cur_wdata` | 16 | |
| 0x00C | `cur_seg` | 2 | |
| 0x00D | `cur_ube_n` | 1 | |
| 0x00E | `cur_kind` | 2 | |
| 0x00F | `nxt_valid` | 1 | |
| 0x010 | `nxt_type` | 3 | |
| 0x011 | `nxt_addr_lo` | 16 | `nxt_addr[15:0]` |
| 0x012 | `nxt_addr_hi` | 4 | `nxt_addr[19:16]` |
| 0x013 | `nxt_fetch` | 1 | |
| 0x014 | `nxt_wr` | 1 | |
| 0x015 | `nxt_swap` | 1 | |
| 0x016 | `nxt_split1` | 1 | |
| 0x017 | `nxt_split2` | 1 | |
| 0x018 | `nxt_wrap` | 1 | |
| 0x019 | `nxt_wdata` | 16 | |
| 0x01A | `nxt_seg` | 2 | |
| 0x01B | `nxt_ube_n` | 1 | |
| 0x01C | `nxt_kind` | 2 | |
| 0x01D | `ube_n` | 1 | output reg |
| 0x01E | `eu_started` | 1 | output reg |
| 0x01F | `eu_hand` | 1 | |
| 0x020 | `eu_rdata` | 16 | output reg |
| 0x021 | `tw_any` | 1 | eval/wait-law group |
| 0x022 | `evald` | 1 | |
| 0x023 | `defer_t4` | 1 | |
| 0x024 | `defer_idle` | 1 | |
| 0x025 | `eval_ext` | 1 | |
| 0x026 | `flush_hold` | 1 | |
| 0x027 | `ext_flushed` | 1 | |
| 0x028 | `ready_prev` | 1 | own block :1782 |
| 0x029 | `eu_req_p1` | 1 | pipes block :1785 |
| 0x02A | `eu_req_p2` | 1 | |
| 0x02B | `eu_ready_p1` | 1 | |
| 0x02C | `eu_ready_p2` | 1 | |
| 0x02D | `tw_par` | 1 | own block :681 |
| 0x02E | `t1_half2` | 1 | **negedge/`ce_half` domain** — write decode in the negedge process from the staged command (§4.3) |
| 0x02F | `ph_ff` | 1 | free-toggling; restore exactly |
| 0x030 | `gph_ff` | 1 | |
| 0x031 | `lock_active` | 1 | |
| 0x032 | `lock_done` | 1 | |
| 0x033 | `q_mem0` | 8 | one byte per address (independent regs; do not pair) |
| 0x034 | `q_mem1` | 8 | |
| 0x035 | `q_mem2` | 8 | |
| 0x036 | `q_mem3` | 8 | |
| 0x037 | `q_mem4` | 8 | |
| 0x038 | `q_mem5` | 8 | |
| 0x039 | `q_rd` | 3 | |
| 0x03A | `q_wr` | 3 | |
| 0x03B | `q_cnt` | 3 | |
| 0x03C | `q_avl` | 3 | |
| 0x03D | `q_aged` | 2 | |
| 0x03E | `q_head_dry_q` | 1 | own block :562 |
| 0x03F | `fetch_discard` | 1 | |
| 0x040 | `fetch_cs` | 16 | |
| 0x041 | `fetch_off` | 16 | |
| 0x042 | `fetch_data` | 16 | in-flight fetch data |
| 0x043 | `push_pend` | 2 | |
| 0x044 | `push_pend_hi` | 1 | |
| 0x045 | `e_wait` | 1 | |
| 0x046 | `halt_t1` | 1 | block :619 — **see §5 free-running-clear fix** |
| 0x047 | `halt_done` | 1 | |
| 0x048 | `occ34_age` | 4 | |
| 0x049 | `pop_sr` | 8 | |
| 0x04A | `recent_evx` | 4 | own block :512 |
| 0x04B | `last_was_store` | 1 | own block :525 |
| 0x04C | `law_tw_cnt` | 4 | law block :1918 |
| 0x04D | `law_dtw` | 4 | |
| 0x04E | `law_dcnt` | 3 | also mirrors into sim probe (§5.2) |
| 0x04F | `law_window` | 1 | |
| 0x050 | `law_ctr` | 3 | |
| 0x051 | `law_sel` | 3 | |
| 0x052 | `law_prov` | 1 | |

### 2.2 EU region (module `v30_eu`, 119 addresses, 851 state bits)

| Addr | Field | W | Notes |
|---|---|---|---|
| 0x100 | `rf0` (AW) | 16 | explicit case arm per index, not indexed decode |
| 0x101 | `rf1` (CW) | 16 | |
| 0x102 | `rf2` (DW) | 16 | |
| 0x103 | `rf3` (BW) | 16 | |
| 0x104 | `rf4` (SP) | 16 | |
| 0x105 | `rf5` (BP) | 16 | |
| 0x106 | `rf6` (IX) | 16 | |
| 0x107 | `rf7` (IY) | 16 | |
| 0x108 | `sr0` (ES) | 16 | |
| 0x109 | `sr1` (CS) | 16 | |
| 0x10A | `sr2` (SS) | 16 | |
| 0x10B | `sr3` (DS) | 16 | |
| 0x10C | `psw` | 16 | the "flags as one word" case — already one register |
| 0x10D | `pc` | 16 | |
| 0x10E | `arch_ip` | 16 | |
| 0x10F | `state` | 7 | **`state_e'()` cast on write** |
| 0x110 | `wnext` | 7 | cast |
| 0x111 | `dret` | 7 | cast |
| 0x112 | `dly` | 6 | |
| 0x113 | `div_rem_lo` | 16 | `div_rem[15:0]` |
| 0x114 | `div_rem_hi` | 1 | `div_rem[16]` |
| 0x115 | `div_quo` | 16 | |
| 0x116 | `div_den` | 16 | |
| 0x117 | `div_cnt` | 6 | |
| 0x118 | `div_busy` | 1 | |
| 0x119 | `div_word` | 1 | |
| 0x11A | `div_signed` | 1 | |
| 0x11B | `div_nsign` | 1 | |
| 0x11C | `div_dsign` | 1 | |
| 0x11D | `div_pend` | 1 | |
| 0x11E | `div_late` | 1 | |
| 0x11F | `sh_r` | 16 | |
| 0x120 | `sh_x` | 8 | |
| 0x121 | `sh_oth` | 8 | |
| 0x122 | `sh_cy` | 1 | |
| 0x123 | `sh_op` | 3 | |
| 0x124 | `sh_wf` | 1 | |
| 0x125 | `sh_n` | 8 | |
| 0x126 | `sh_busy` | 1 | |
| 0x127 | `sh_fbase` | 16 | |
| 0x128 | `sh_res` | 16 | |
| 0x129 | `sh_fl` | 16 | |
| 0x12A | `opc` | 8 | |
| 0x12B | `opc2` | 8 | |
| 0x12C | `mrm` | 8 | |
| 0x12D | `immb` | 8 | |
| 0x12E | `disp` | 16 | |
| 0x12F | `a4_cnt` | 8 | |
| 0x130 | `a4_k` | 8 | |
| 0x131 | `a4_src` | 16 | |
| 0x132 | `a4_carry` | 1 | |
| 0x133 | `a4_z` | 1 | |
| 0x134 | `mem_op` | 16 | |
| 0x135 | `ivt_off` | 16 | |
| 0x136 | `ivt_seg` | 16 | |
| 0x137 | `trap_psw` | 16 | |
| 0x138 | `seg_ovr_en` | 1 | |
| 0x139 | `seg_ovr` | 2 | |
| 0x13A | `lock_en` | 1 | |
| 0x13B | `rep_en` | 1 | |
| 0x13C | `rep_kind` | 2 | |
| 0x13D | `flush_now` | 1 | |
| 0x13E | `str_wr` | 1 | |
| 0x13F | `rslot` | 6 | |
| 0x140 | `rep1_abort` | 1 | |
| 0x141 | `str_done` | 1 | |
| 0x142 | `cmp1` | 16 | |
| 0x143 | `cmp_r2s` | 1 | |
| 0x144 | `fl_cs` | 16 | |
| 0x145 | `fl_ip` | 16 | |
| 0x146 | `ea_save_lo` | 16 | `ea_save[15:0]` |
| 0x147 | `ea_save_hi` | 4 | `ea_save[19:16]` |
| 0x148 | `ea_save_seg` | 2 | |
| 0x149 | `ldp2` | 1 | |
| 0x14A | `fret_ph` | 2 | |
| 0x14B | `facc` | 2 | |
| 0x14C | `iret_pw` | 1 | |
| 0x14D | `popr_pend` | 1 | |
| 0x14E | `prep_acc` | 1 | |
| 0x14F | `pracc` | 3 | |
| 0x150 | `w4skip` | 1 | |
| 0x151 | `prep_bpd` | 1 | |
| 0x152 | `shw` | 9 | |
| 0x153 | `popm_hold` | 6 | |
| 0x154 | `ie_off` | 4 | |
| 0x155 | `ie_len` | 5 | |
| 0x156 | `ie_fld` | 16 | |
| 0x157 | `ie_w0` | 16 | |
| 0x158 | `ie_mode` | 2 | |
| 0x159 | `ie_ph2` | 1 | |
| 0x15A | `ie_dly` | 12 | |
| 0x15B | `ie_chain` | 1 | |
| 0x15C | `ie_rdyhold` | 1 | |
| 0x15D | `ie_lgot` | 1 | |
| 0x15E | `int_p` | 4 | pin pipeline — restore exactly |
| 0x15F | `nmi_p` | 5 | |
| 0x160 | `nmi_latch` | 1 | |
| 0x161 | `poll_s1` | 1 | |
| 0x162 | `shadow` | 1 | |
| 0x163 | `ie_pend` | 1 | |
| 0x164 | `ie_val` | 1 | |
| 0x165 | `psw_old` | 16 | |
| 0x166 | `pop_pend` | 1 | |
| 0x167 | `ie_p` | 4 | |
| 0x168 | `waits_seen` | 1 | |
| 0x169 | `post_flush` | 1 | |
| 0x16A | `insn_ip` | 16 | |
| 0x16B | `ivt_vec` | 8 | |
| 0x16C | `hwake_ie0` | 1 | |
| 0x16D | `irq_disp` | 1 | |
| 0x16E | `irq_nmi_ivt` | 1 | |
| 0x16F | `eu_wr` | 1 | BIU-side output regs group |
| 0x170 | `eu_word` | 1 | |
| 0x171 | `eu_addr_lo` | 16 | `eu_addr[15:0]` |
| 0x172 | `eu_addr_hi` | 4 | `eu_addr[19:16]` |
| 0x173 | `eu_seg` | 2 | |
| 0x174 | `eu_wdata` | 16 | |
| 0x175 | `eu_kind` | 2 | |
| 0x176 | `halt_disp` | 1 | output reg |

Sanity totals the worker must re-verify mechanically before freezing the package: 82 BIU addresses = 80 fields + 2 splits (295 bits); 119 EU addresses = 116 fields + 3 splits (851 bits); grand total 202 mapped addresses including the tag.

## 3. The package (`v30_ss_pkg.sv`) — rewritten

Delete `ss_biu_t`/`ss_eu_t` (the packed structs go with the shadow). The package becomes the map's single home:

```systemverilog
package v30_ss_pkg;
  localparam int          SS_ADDR_W    = 9;
  localparam int          SS_VERSION   = 8'h02;
  localparam logic [8:0]  SSA_TAG      = 9'h000;
  localparam logic [8:0]  SS_BIU_BASE  = 9'h001;
  localparam int          SS_BIU_COUNT = 82;
  localparam logic [8:0]  SS_EU_BASE   = 9'h100;
  localparam int          SS_EU_COUNT  = 119;
  localparam int          SS_COUNT     = 1 + SS_BIU_COUNT + SS_EU_COUNT; // 202
  localparam logic [15:0] SS_TAG       = {8'(SS_VERSION), 8'(SS_COUNT)};

  // ---- one localparam per table row, both regions ----
  localparam logic [8:0] SSA_B_STATE       = 9'h001;
  /* ... */
  localparam logic [8:0] SSA_E_HALT_DISP   = 9'h176;

  // dense-iteration helper for tooling (TB/harness): stream index -> address
  function automatic logic [8:0] ss_addr_of(input int i);
    if (i == 0)                   return SSA_TAG;
    else if (i <= SS_BIU_COUNT)   return SS_BIU_BASE + 9'(i - 1);
    else                          return SS_EU_BASE  + 9'(i - 1 - SS_BIU_COUNT);
  endfunction

  // field width per address (TB mode-5 round-trip check; 0 = unmapped)
  function automatic int ss_field_width(input logic [8:0] a);
    case (a)
      SSA_TAG:            return 16;
      SSA_B_STATE:        return 3;
      /* ... one line per address ... */
      default:            return 0;
    endcase
  endfunction
endpackage
```

Both functions used only by TB/tooling (Quartus never elaborates a call), but they live HERE, co-located with the addresses — ONE file to touch when the map changes.

**What replaces the `$bits` width guard** — three layers:
1. **TB mode 5 "round-trip width sweep"** (new; §7.2): per address, write FFFF then 0000, read back, check readback mask equals `ss_field_width`. Dynamically verifies per address: write arm exists, read arm exists, both touch the same correctly-sized slice. The v1 unpack blind spot is now dynamically detectable. Joins the standing regression set.
2. **Lint-grep invariant:** every `SSA_B_*` symbol appears exactly twice in v30_biu.sv (one read arm, one write arm), every `SSA_E_*` exactly twice in v30_eu.sv; symbol counts equal SS_BIU_COUNT/SS_EU_COUNT. Ten-line check script.
3. **Residual gap (same as v1):** a register absent from the map entirely is invisible to both dynamic checks; catchers remain the inventory audit + behavioral scramble where live.

Width drift also caught by lint: read arms use explicit zero-extension (`{13'b0, state}`), write arms explicit slices (`ss_wdata[2:0]`) — a widened register fires Verilator width warnings.

## 4. Per-module implementation pattern (Quartus-17.1-safe)

### 4.1 Read mux (each module; registered)

```systemverilog
always_ff @(posedge clk) begin
    case (ss_addr)
        SSA_B_STATE:        ss_rdata <= {13'b0, state};
        SSA_B_CUR_ADDR_LO:  ss_rdata <= cur_addr[15:0];
        SSA_B_CUR_ADDR_HI:  ss_rdata <= {12'b0, cur_addr[19:16]};
        SSA_B_Q_MEM0:       ss_rdata <= {8'b0, q_mem[0]};
        /* ... one arm per address, explicit zero-extension ... */
        default:            ss_rdata <= 16'h0000;
    endcase
end
```

Plain `case` with `default` (no `unique`, no `'{}` aggregates). EU identical; enum sources read as `{9'b0, state}` (or `{9'b0, 7'(state)}` if Quartus objects).

### 4.2 Write decode into existing flops

The `if (ss_restore)` arm in each of the ~12 BIU blocks and the single EU block becomes an addressed arm **in the same position (top of the if-chain, above `srst`)**:

Single-field block:
```systemverilog
always_ff @(posedge clk)
    if (ss_we && ss_addr == SSA_B_TW_PAR) tw_par <= ss_wdata[0];
    else if (srst) tw_par <= 1'b0;
    else if (ce) begin ... end
```

Multi-field block (BIU main FSM, law block, EU giant block):
```systemverilog
always_ff @(posedge clk) begin
    if (ss_we) begin
        case (ss_addr)
            SSA_B_STATE:       state           <= ss_wdata[2:0];
            SSA_B_CUR_ADDR_LO: cur_addr[15:0]  <= ss_wdata;
            SSA_B_CUR_ADDR_HI: cur_addr[19:16] <= ss_wdata[3:0];
            /* ... only fields owned by THIS block ... */
            default: ;                        // not mine / other module
        endcase
    end else if (srst) begin ...
    end else if (ce) begin ...
end
```

`if (ss_we)` swallowing the whole cycle for foreign addresses is harmless by contract (CE=0 → skipped branches are no-ops) and keeps the pattern uniform. EU enum casts: `SSA_E_STATE: state <= state_e'(ss_wdata[6:0]);` (same wnext/dret). rf/sr/q_mem get explicit per-index arms (no indexed decode).

### 4.3 `t1_half2` negedge flop — rule re-derived

```systemverilog
always @(negedge clk)
    if (ss_we && ss_addr == SSA_B_T1_HALF2) t1_half2 <= ss_wdata[0];
    else if (ce_half) t1_half2 <= (state == ST_T1);
```

`ss_we/ss_addr/ss_wdata` here are the **core-staged** registers — change only just after a posedge, therefore stable at every negedge by construction. Write accepted at posedge N lands at negedge N+½ (posedge flops at N+1). No platform hold rule; the S3 race class is structurally impossible.

## 5. Coherence contract, and the one RTL fix

### 5.1 Atomicity moves to the CE contract — one audited exception

Coherence over a multi-cycle save/restore holds iff nothing changes core state while CE==0 except SS writes. Audit result:
- EU: single always_ff, strict ss/srst/ce gating — clean (pulse defaults inside ce branch confirmed at :2033).
- BIU: every block ss/srst/ce-gated EXCEPT `halt_t1/halt_done` (:619) which clears on `srst || !halt_disp` — **free-running**. Harmless in v1 (single-cycle restore); real hazard now (clears against partially-restored live `halt_disp`).
- t1_half2: ce_half-gated — clean. Sim-only coverage counters free-run but are not core state and not mapped (pre-existing).

**Required fix (the one semantic touch):** gate the clear with `ce`:

```systemverilog
always_ff @(posedge clk) begin
    if (ss_we && ss_addr == SSA_B_HALT_T1)        halt_t1   <= ss_wdata[0];
    else if (ss_we && ss_addr == SSA_B_HALT_DONE) halt_done <= ss_wdata[0];
    else if (srst) begin
        halt_t1 <= 1'b0;  halt_done <= 1'b0;
    end else if (ce) begin
        if (!halt_disp) begin
            halt_t1 <= 1'b0;  halt_done <= 1'b0;
        end else begin
            halt_t1 <= halt_show;
            if (halt_show) halt_done <= 1'b1;
        end
    end
end
```

Equivalence: `halt_disp` only changes on CE edges (EU is CE-gated), so the free-running clear's earliest observable effect is the next CE — exactly when the gated version clears. Gated by full G1′ (incl. ce_div=4) + G7′ silicon — not taken on faith. (Rejected alternative: EU-before-BIU restore-order contract — works today but converts a local RTL property into a fragile permanent tooling contract.)

With the fix: **while CE==0, core state changes only via SS writes** — reads form a coherent snapshot at any point, writes in any order, idempotence exact. Put verbatim in the core SS port comment.

### 5.2 Sim-only probes
- `law_dcnt_probe` (:1990): `if (ss_we && ss_addr == SSA_B_LAW_DCNT) law_dcnt_probe <= ss_wdata[2:0];`
- `cyc_saw_tw` (:1709): `if (ss_we && !ss_addr[8]) cyc_saw_tw <= 1'b0;` (clear-on-restore, documented acceptable).
- Neither mapped.

### 5.3 Outputs during operations
- During save: core state untouched → pins frozen. Identical to v1.
- During restore: pins/SS_BUS_QUIET/EU Moore outputs wander through intermediate values as fields land. Contract: **all core outputs undefined from first restore write until last mapped address written; platform must isolate/ignore and not resume CE until complete.** No internal corruption possible (all state ce-gated per §5.1). SS_BUS_QUIET is a pre-freeze predicate only.
- Comb reachability probes historically don't trip on garbage-live state (S3-S5 scramble history); contingency if a future pattern trips one mid-restore: TB-driven sim-only quiesce flag on that probe.

## 6. Deleted vs carried over

**Deleted:** BIU ss_pack comb (:209-292), ss_sh (304 flops) + capture/shift mux, ss_dout_seg/ss_u, width-guard generate (:308-313), strobe ports; EU same shape (pack, 864-flop shadow, guard, ports); core ss_tag_sh (16 flops), tag-compare-on-restore, strobe assertions, SS_CAPTURE/SS_RESTORE/SS_SHIFT/SS_DIN/SS_DOUT ports; both packed structs. Net **−1,184 dedicated flops**.

**Carries over unchanged:** state inventory; SS_BUS_QUIET + predicate; CE-parking; restore-priority position (ss arm above srst); EU enum casts; block-local-temp audit result; bkd_load backdoor; race_rom exclusion (G6′ re-checks); v1 §5 platform restore contract (bus-side state, wait-gen state, pins); verification investment (interface-layer changes only).

**Touched semantically (one item):** halt_t1/halt_done free-running clear (§5.1), gated by G1′/G7′.

**Tie-offs to update:** system_large.sv (:396-399 → SS_ADDR=0, SS_WDATA=0, SS_WE=0, SS_RDATA unconnected) and tb_ab.sv. With SS_WE=0 and SS_RDATA unloaded, Quartus sweeps the feature — tied-off build no-op by construction (G1′).

## 7. Verification: gates G1′–G7′ and TB rework

### 7.1 TB interface layer (tb_v30_core.sv)

Replace strobe regs and ss_save/ss_load tasks; CE parking, +ss_at/+ss_mode/+ss_scramble_seed/+ss_dwell plusargs, ss_controller structure stay:

```systemverilog
task automatic ss_write(input logic [8:0] a, input logic [15:0] d);
    ss_addr_r = a;  ss_wdata_r = d;  ss_we_r = 1'b1;
    @(posedge clk);
    ss_we_r = 1'b0;
endtask
task automatic ss_read(input logic [8:0] a, output logic [15:0] d);
    ss_addr_r = a;
    @(posedge clk); @(posedge clk); @(negedge clk);  // 2-cycle latency
    d = ss_dout;
endtask
task automatic ss_save_all(output logic [15:0] s [0:SS_COUNT-1]);
    for (int i = 0; i < SS_COUNT; i++) ss_read(ss_addr_of(i), s[i]);
endtask
task automatic ss_load_all(input logic [15:0] s [0:SS_COUNT-1]);
    for (int i = 0; i < SS_COUNT; i++) ss_write(ss_addr_of(i), s[i]);
endtask
```

Arrays resize 74 → SS_COUNT(202) via package import. check_core.py --ss-sweep/--ss-cases needs NO logic change.

### 7.2 Gates (pre-registered)

| Gate | Content (delta vs v1) | Pass criterion |
|---|---|---|
| **G1′** no-op invariance | SS_WE tied 0: full goldens — w0 (169000), w1/w3, wrand baseline seeds, **plus ce_div=4** (halt_t1 fix makes this first-class), --assert | bit-identical, 0 mismatches, 0 fires |
| **G2′** scramble sweep | mode 1 rebuilt: ss_save_all → corrupt-tag write (SS_ERR sets, valid tag clears) → scramble-write every state address (LFSR⊕A5A5/5A5A, tag valid) → ss_load_all(saved) → resume. Same forms × full-k × w0/w1/w3 × wrand seeds as S3/S4 (G2a/G2b/G2c/G5 sets incl. 10,000-clk +ss_dwell) | rows k+1…end byte-identical, all k; SS_ERR==0 after valid restore |
| **G3′** idempotence | mode 2: read-all A → write-all A → read-all B | A==B always |
| **G4′** round-trip width sweep (**NEW**) | mode 5: save-all; per mapped address ≠ tag: write FFFF, read r1, write 0000, read r0; check r0==0 and r1 == mask(ss_field_width(a)); then restore saved and resume to end | exact mask match on all 201 state addresses; post-restore rows identical |
| **G5′** negative | corrupt-tag → SS_ERR (in G2′); mode-4 bit-flip sensitivity retained | as v1 G4 |
| **G6′** synthesis | Quartus 17.1, SS tied off: 0 errors, no latches, race_rom still ROM, ALM/**register** delta vs v1-shadow baseline reported, slack ≥ **+3.8 ns** (parity with accepted S6 baseline) | **PASS — see G6′ actuals below** |
| **G7′** silicon | one A/B (check_ab_hw) + byte-identity re-emission set — **mandatory** (halt_t1 edit) | identical to reference |

Mode 3 (FIFO self-test) moot — no FIFO; slot taken by mode 5. **Standing regression set: G1′ + G2′ + G4′ + lint-grep symbol counts** (`sw/ss_lint.py`) — strictly dominates v1's (unpack blind spot now covered dynamically).

#### G6′ actuals (A4) — Quartus 17.1 Lite, Cyclone V 5CSEBA6U23I7, HEAD at A3 (cb9564f)

**Full `sys_top` compile, SS tied off (the shipping build):**

| Metric | v2 | v1-shadow (S6 baseline) | Verdict |
|---|---|---|---|
| Compilation | 0 errors, 306 warnings | 0 errors | PASS |
| Inferred latches | 0 | 0 | PASS |
| race_rom inference | ROM; block mem 840,863 (unchanged) | ROM 840,863 | PASS |
| Worst-case setup slack | **+4.191 ns** | +3.830 ns | PASS — **clears the original +4.0 ns gate v1 could only meet via a documented deviation** |
| ALM (tied-off) | 10,269 / 41,910 (25%) | 10,232 (+149 vs pre-SS base 10,083) | +37 vs v1 (rounding noise on a 41,910-ALM part) |
| Registers (tied-off) | 5,174 | not recorded (DCE'd) | — |

The race_rom `Warning (10030)` lines are only the unused write port (`waddr_a/data_a/we_a` defaulting to 0) — expected for a read-only ROM; block-memory bits are byte-identical to the v1 baseline, confirming it still maps to block RAM.

**Live register-delta headline — core-only, `v30_core` as top (SS ports on pins, nothing DCE'd):**

| Metric | v1-shadow | v2-addressed | Delta |
|---|---|---|---|
| Registers (A&S dedicated) | 2,331 | 1,207 | **−1,124 flops** |
| ALM (A&S estimate) | 7,913 | 7,910 | −3 (neutral) |

**DCE caveat (why the live delta, not the tied-off one, is the real number):** in the tied-off top both builds dead-code-eliminate their SS logic (v1's shadow has no observable output when `SS_*` are constants; v2's read-mux/write-decode collapse when `ss_we_q`/`SS_RDATA` are constant/unused), so the tied-off ALM/register deltas are near-zero and *understate* the saving. Driving the ports — here by making `v30_core` the synthesis top so `SS_ADDR/WDATA/WE`→pins and `SS_RDATA/ERR`→pins — preserves the full SS mechanism. The core-state flops are identical between the two builds, so the **−1,124** is essentially the mechanism itself (v1's ~1,168-flop shadow shift-register vs v2's ~44 net read-mux + command-staging registers). This lands on the design's predicted **net ≈ −1,120 flops** — the directive's register-economy objective, met.

#### G7′ actuals (A5) — in-silicon A/B: SS v2 INVISIBLE ON HARDWARE (2026-07-22)

Flashed the v2 build (`nec_test.sof`, SS tied off) via `safe_flash.sh` (quartus_pgm 0 errors; VERIFY `pwr_good`+MAGIC ok). This also brought the board current off the F8-era bitstream.

- **G7′-1 `check_ab_hw all`**: chip-vs-golden MATCH, **core-vs-chip MATCH**, core-vs-golden MATCH (200 rows each) — the v2 SS logic did not disturb the known-good chip or core boot path.
- **G7′-2 byte-identity**: re-emitted **150/150 byte-identical** vs the committed **v0.3** goldens (seed base `v30-v0.2`, socket truth-source, wait-rig commanded clean, 0 rerolls) across the same 10 diverse forms as v1's G7 — `00, 89, F7.7, F3A5, E4, EC, 6C, 6D, 6E, F36C` — **incl. FIFO-served INS (6C/6D/F36C): port-serving still works on the new build.**

**The save-state v2 feature is invisible on silicon exactly as G1′ proved in sim.** Save-state v2 (task #23 re-architecture) A0–A6 COMPLETE and green. Deferred (unchanged from v1): S7 — the MiSTer savestate-bus wrapper (now a pure adapter over `ss_addr_of`; the shadow-live strobe-register decision is mooted by the addressed interface).

**Verdict methodology (A3) — sim-vs-sim transparency, never a cross-wait-regime golden compare.** The save-state property under test is *transparency*: a freeze+restore run must reproduce the **uninterrupted run at the same wait config**, bit-for-bit. The reference is therefore a no-freeze baseline sim sharing the ss run's waits — **not** the recorded silicon golden. The golden compare only coincides with transparency at w0 (where golden==baseline); at w1/w3/wrand the cycle rows are per-T-state, so a w0 golden has fewer rows than a w1 sim and the compare is meaningless. `check_core.sim_transparent(base, ss)` implements the correct test: identical `r`-record streams and identical finals. It is wait-agnostic because the observer FSM (incl. the wrand wait-LFSR) is `ce`-gated, so the CE-park emits no records and does not advance the wait generator — the freeze is invisible to the record stream, and the wrand pattern is shared between baseline and freeze runs at the same `+wseed`. RTL-vs-golden correctness stays a *separate* concern, checked by the main pass. A3 dimensions (all via `sim_transparent`): **w1** (`--waits 1`), **w3** (`--waits 3`), **dwell** (`--ss-dwell 10000`, park-only, reuses the uniform baseline), **wrand** (`--ss-wrand --ss-wmax 3` × several `--ss-wseed`, dedicated wrand baseline per case). **G5′ negatives** (`--ss-mode 4 --ss-neg`): the same transparency test inverted — a live-state bit-flip left un-restored *must* perturb the continuation; swept across `--ss-scramble-seed` (bit index = seed mod SS_COUNT·16), most flips must diverge (blindness alarm at <50%).

Codex critical-review per phase ("which register has no address?", "which write arm slices wrong bits?", "what changes while CE==0?").

### 7.3 MiSTer S7 note

Addressed interface = MiSTer savestate-bus idiom natively. Wrapper packs 4 map indices per 64-bit DDR word via ss_addr_of, or one per word — no shift sequencing, no chunk framing; the "shadow-live strobe-register timing decision" no longer exists. S7 remains deferred and shrinks.

## 8. Costs and timing

- **Registers:** −1,184 + ~60 ≈ **net −1,120 flops** live-build. The directive's objective.
- **LUTs:** read muxes ~600–900 ALUTs ≈ 300–450 ALMs, comparable to/below the shadow's capture/shift fabric. Write decode ≈ 200 shared 9-bit comparators feeding the same D-mux position v1's restore mux occupied. Net ALM neutral-to-better; G6′ reports actuals.
- **Timing:** read mux registered → never on a core path. Only core-path touch = per-flop write-mux select (`ss_we_q & (ss_addr_q == CONST)`) — shallow decode from dedicated staging regs with a full cycle of slack. Vs +3.830 ns baseline: expect neutral; the live build no longer carries v1's unmeasured shadow-fanout risk. G6′ ≥ +3.8 ns.

## 9. Phased implementation plan

| Phase | Content | Size | Gate |
|---|---|---|---|
| A0 | Rewrite v30_ss_pkg.sv: delete structs, add SSA_* map, counts, tag, ss_addr_of, ss_field_width. Mechanically re-verify §2 totals (295/851 bits, 82/119/202 counts) | S | builds standalone |
| A1 | Coordinated RTL swap (one commit): BIU read mux + write arms all ~12 blocks + negedge rule + halt_t1 fix + sim probes; EU read mux + case-ified restore arm (enum casts); core staging/tag/err/assertions/ports; tie-offs; minimal TB port fix to compile | M–L | G1′ full (incl. ce_div=4) |
| A2 | TB rework: tasks, modes 1/2/4 rebuilt, mode 5 new, mode 3 retired; lint-grep script | M | G2′ @ w0 full-k + G3′ + G4′ |
| A3 | Waits/breadth re-run (G2′ under w1/w3/wrand/dwell), negatives | M | G2′ complete, G5′ |
| A4 | Quartus build + report (register-delta headline) | S–M | G6′ |
| A5 | Silicon A/B + byte-identity set | S | G7′ |
| A6 | Doc close-out: supersession note in savestate_design.md; memory updates | S | — |

Worker rules: never '{field: value}' aggregates (the f43c-series Quartus 17.1 bug — "Phase-R commit_desc_t assignment not synthesizable"); member-wise assigns and explicit concatenation only; explicit enum casts; sim-only code under ifndef SYNTHESIS never changes mapped widths/counts.

## 10. Risks

1. **Map drift**: append-only rule + version bump + G4′ round-trip + lint-grep counts + inventory audit; residual (register absent entirely) caught by audit + scramble where live.
2. **halt_t1 gating edit**: per-CE equivalence §5.1; proven by G1′ (all regimes, ce_div∈{1,4}) + G7′. Fallback: revert edit, adopt EU-before-BIU restore-order contract (documented inferior but sound).
3. **Comb probes firing mid-restore** on pathological patterns: not observed S3–S5; contingency = sim-only quiesce gating of that probe.
4. **Quartus 17.1 case scale**: 119-arm cases ordinary; the 17.1 hazard is aggregate assignment, never used here. G6′ backstop.
5. **Longer undefined-output window during restore** (~200 cycles vs 1): platform contract §5.3; MiSTer freezes whole system anyway.
6. **2-cycle read latency in tooling**: contract in §1.1; TB tasks encode it once.

## 11. User decisions (resolved)

(a) Strict one-register-per-address including single-bit descriptor flags — chosen for one-symbol-two-arms auditability. (b) halt_t1/halt_done CE-gating edit — equivalence-argued, gate-protected, fallback documented. User approved proceeding 2026-07-21.
