//============================================================================
//
//  hps_axi_slave - harness control over the lightweight HPS-to-FPGA bridge
//
//  AXI3 slave (single outstanding transaction, INCR bursts) behind the
//  cyclonev_hps_interface_hps2fpga_light_weight primitive. From the ARM the
//  2 MB window appears at physical 0xFF200000:
//
//    +0x000000  64 KB   test memory, byte-packed (host access only while
//                       CTRL.host_reset holds the harness in reset)
//    +0x100000  32 KB   capture buffer, 4096 x 64-bit records as pairs of
//                       32-bit words (little end first), read-only
//    +0x140000  4 KB    wait-vector replay RAM, 4096 x 8-bit Tw entries packed
//                       4-per-word (host write-only; applied when WRAND.replay)
//    +0x180000          registers:
//        0x00  MAGIC     RO  0x56333031 "V301"
//        0x04  CTRL      RW  [0] host_reset  [1] cpu_power_off
//                            [2] skip_pwrup (short rail-settle wait)
//        0x08  CFG       RW  [5:0] clk_div  [11:8] wait_states
//                            [23:16] int_vector  [24] small_mode
//                            [25] use_core (A/B: 1 = internal v30_core,
//                                 0 = socketed chip) — Campaign 4
//                            (change only while host_reset is set)
//        0x0C  PINS      RW  [0] int_req  [1] nmi_req  [2] poll_n
//        0x18  IORD      RW  [15:0] data returned for I/O reads (dflt FFFF)
//        0x1C  EVT_ADDR  RW  [19:0] fetch-address trigger for pin-event
//                            scheduler 0 (CODE T1 linear-address match)
//        0x20  EVT_CFG   RW  [15:0] delay (CPU clocks after match)
//                            [23:16] hold low 8 / [30:27] hold high 4
//                            (CPU clocks; 0 = until disarmed)
//                            [26:24] pin (0=INT 1=NMI 2=POLL_N active-low;
//                                   3-7 undefined -- fires, drives nothing)
//                            [31] arm (STATUS[3] = fired; disarm deasserts)
//                            EVERY BIT OF THIS WORD IS SPOKEN FOR.
//        0x30  EVT2_ADDR RW  scheduler 1, layout identical to EVT_ADDR
//        0x34  EVT2_CFG  RW  scheduler 1, layout identical to EVT_CFG
//        0x38  EVT3_ADDR RW  scheduler 2, layout identical to EVT_ADDR
//        0x3C  EVT3_CFG  RW  scheduler 2, layout identical to EVT_CFG
//                            The three pairs share ONE unpacker below, so the
//                            host packs one layout for all three.  A forked
//                            packer is how INV-1 happened; a forked unpacker
//                            would be the same defect on this side of the wire.
//        0x40  TVEC      RW  [15:0] IP  [31:16] CS -- the words served for the
//                            NMI vector reads at linear 0x00008 / 0x0000A while
//                            the overlay is armed (see nec_bus.sv)
//        0x44  VECCTL    RW  [2:0] vecsub_en, bit n = scheduler n's FIRE arms
//                            the NMI vector-read overlay
//        0x24  WRAND     RW  per-access wait insertion (large mode; overrides
//                            CFG.wait_states). [0] rand-enable  [1] replay-enable
//                            (replay > rand > uniform)  [7:4] wmax  [31:16] seed
//                            replay applies the +0x140000 wait-vector RAM
//        0x10  STATUS    RO  [0] pwr_good  [1] cpu_running  [2] cap_full
//                            [5:3] evt_fired, one bit per scheduler
//                            [6] vec_used (sticky: the NMI vector-read overlay
//                                actually served a CS half)
//        0x14  CAPCOUNT  RO  records captured
//        0x28  IORDS_CTL RW  [0] reset (clear write ptr + count, pulse)
//                            [1] enable (serve the sequence on IOR cycles)
//                            RO readback: [0] enable  [7:1] count
//        0x2C  IORDS_PUSH WO [15:0] append one 16-bit value to the sequence
//                            (byte forms: host pre-duplicates into both lanes);
//                            the per-case INS/REP-INS I/O-read data, served one
//                            per IOR in order (see iords_buf.sv)
//
//============================================================================

module hps_axi_slave #(
    // Number of pin-event schedulers.  Passed from system_large's single
    // localparam so this module, nec_bus and the harness cannot disagree.
    // NOTE: the EVTn register OFFSETS below are an explicit table (0x1C/0x20
    // then 0x30 + 8*(n-1)); a fourth scheduler needs two more case arms.
    parameter int EVT_N = 3
)
(
    input             clk,
    input             reset,           // sys reset only (not host_reset)

    // AXI3 slave (signals named from the master's perspective)
    input      [11:0] awid,
    input      [20:0] awaddr,
    input       [3:0] awlen,
    input             awvalid,
    output reg        awready,
    input      [31:0] wdata,
    input       [3:0] wstrb,
    input             wvalid,
    input             wlast,
    output reg        wready,
    output reg [11:0] bid,
    output      [1:0] bresp,
    output reg        bvalid,
    input             bready,
    input      [11:0] arid,
    input      [20:0] araddr,
    input       [3:0] arlen,
    input             arvalid,
    output reg        arready,
    output reg [11:0] rid,
    output reg [31:0] rdata,
    output      [1:0] rresp,
    output reg        rlast,
    output reg        rvalid,
    input             rready,

    // harness control outputs
    output reg        host_attached,   // set on first CTRL write: host owns
                                       // the harness lifecycle from then on
    output reg        host_reset,
    output reg        cpu_power_off,
    output reg        skip_pwrup,
    output reg  [5:0] cfg_clk_div,
    output reg  [3:0] cfg_wait_states,
    output reg  [7:0] cfg_int_vector,
    output reg        cfg_small_mode,
    output reg        cfg_use_core,    // Campaign 4 A/B: 1 = internal core
    output reg        cfg_wait_rand,   // 1: seeded random per-access waits
    output reg  [3:0] cfg_wmax,        // max Tw per access in random mode
    output reg [15:0] cfg_wseed,       // random-wait PRNG seed
    output reg        cfg_wait_replay, // 1: replay host wait-vector (Phase 2a)
    output reg  [9:0] h_wvec_addr,     // wait-vector RAM write port (word idx)
    output reg        h_wvec_wr,
    output reg [31:0] h_wvec_wdata,
    output reg        int_req,
    output reg        nmi_req,
    output reg        poll_n_out,
    output reg [15:0] cfg_iord,

    // iords sequence buffer load (INS / REP INS per-element port serving).
    // IORDS_CTL(0x28): [0] reset (clear write ptr + count) [1] enable.
    // IORDS_PUSH(0x2C): [15:0] append one value (host pre-duplicates byte forms
    // into both lanes). h_iords_* drive iords_buf; cfg_iords_* feed the serve mux.
    output reg  [5:0] h_iords_addr,
    output reg        h_iords_wr,
    output reg [15:0] h_iords_wdata,
    output reg  [6:0] cfg_iords_cnt,
    output reg        cfg_iords_en,
    output reg [EVT_N*20-1:0] evt_addr,
    output reg [EVT_N*16-1:0] evt_delay,
    // 12 bits since 2026-08-04 (F46 / gap R1).  It was 8, and 760 banked EVT
    // seeds asked for hold=300, which the register truncated to 300&0xFF = 44
    // SILENTLY -- the rig applied a hold the bank does not record.  The width
    // is now the widest drop-in EVT_CFG (0x20) has room for: the low 8 bits
    // stay at [23:16] and the high 4 take the free space at [30:27], so
    // evt_pin[26:24] and evt_arm[31] do not move and an old host that writes
    // zeros there gets exactly the old behaviour.
    output reg [EVT_N*12-1:0] evt_hold,
    output reg [EVT_N*3-1:0]  evt_pin,
    output reg [EVT_N-1:0]    evt_arm,
    output reg [EVT_N-1:0]    evt_vecsub_en,  // VECCTL: arms the NMI overlay
    output reg [31:0]         cfg_tvec,       // TVEC: {CS, IP}
    input      [EVT_N-1:0]    evt_fired,
    input                     vec_used,

    // harness status inputs
    input             pwr_good,
    input             cpu_running,
    input             cap_full,
    input      [12:0] cap_count,

    // test memory port (valid while host_reset)
    output reg [19:0] h_mem_addr,
    output reg        h_mem_wr_req,
    output reg [15:0] h_mem_wdata,
    output reg  [1:0] h_mem_be,
    input      [15:0] h_mem_rdata,

    // capture buffer read port
    output reg [11:0] h_cap_addr,
    input      [63:0] h_cap_rdata
);

localparam bit [31:0] MAGIC = 32'h56333031;

assign bresp = 2'b00;
assign rresp = 2'b00;

// region select from a latched address. The old cap region (a[20]&~a[19]) is
// split by a[18]: capture stays at 0x100000 (a[18]=0), the wait-vector RAM is
// added at 0x140000 (a[18]=1). mem/reg decodes are unchanged.
function automatic bit sel_mem (input [20:0] a); return ~a[20]; endfunction
function automatic bit sel_cap (input [20:0] a); return a[20] & ~a[19] & ~a[18]; endfunction
function automatic bit sel_wvec(input [20:0] a); return a[20] & ~a[19] &  a[18]; endfunction
function automatic bit sel_reg (input [20:0] a); return a[20] & a[19]; endfunction

typedef enum logic [3:0] {
    IDLE,
    W_DATA,     // wait for a W beat
    W_MEM0,     // low-half memory sub-write
    W_MEM1,     // high-half memory sub-write
    W_WVEC,     // wait-vector word write
    W_NEXT,     // advance to next W beat or respond
    B_RESP,
    R_SETUP,    // present address to mem/capture, start latency counter
    R_WAIT,
    R_DATA,     // rvalid asserted, wait for rready
    R_NEXT
} state_t;

state_t st;

reg [11:0] axid;
reg [20:0] addr;
reg  [3:0] beats_left;
reg [31:0] wdata_q;
reg  [3:0] wstrb_q;
reg        wlast_q;
reg  [1:0] lat;
reg [15:0] rd_lo;
reg  [6:0] iords_wptr;    // iords buffer host write pointer / running count

//----------------------------------------------------------------------------
// EVTn register-pair decode.  Scheduler 0 keeps its historical offsets
// (EVT_ADDR 0x1C / EVT_CFG 0x20), so a host that knows nothing about the extra
// schedulers is bit-for-bit unchanged; schedulers 1..EVT_N-1 sit at
// 0x30 + 8*(n-1).  Everything downstream of this decode -- the write unpack
// and the readback pack -- is written ONCE and indexed, so the three pairs
// cannot drift apart from each other.
//
// `addr` is the latched AXI address and is the same register on the write and
// the read path, so one decode serves both.
//----------------------------------------------------------------------------
reg [1:0] ev_sel;
reg       ev_is_addr, ev_is_cfg;

always_comb begin
    ev_sel     = 2'd0;
    ev_is_addr = 1'b0;
    ev_is_cfg  = 1'b0;
    case (addr[7:0])
    8'h1C: begin ev_sel = 2'd0; ev_is_addr = 1'b1; end
    8'h20: begin ev_sel = 2'd0; ev_is_cfg  = 1'b1; end
    8'h30: begin ev_sel = 2'd1; ev_is_addr = 1'b1; end
    8'h34: begin ev_sel = 2'd1; ev_is_cfg  = 1'b1; end
    8'h38: begin ev_sel = 2'd2; ev_is_addr = 1'b1; end
    8'h3C: begin ev_sel = 2'd2; ev_is_cfg  = 1'b1; end
    default: ;
    endcase
end

`ifndef SYNTHESIS
initial if (EVT_N != 3)
    $fatal(1, "hps_axi_slave: the EVTn offset table enumerates exactly 3 scheduler pairs; EVT_N=%0d needs matching case arms", EVT_N);
`endif

always_ff @(posedge clk) begin
    if (reset) begin
        st        <= IDLE;
        awready   <= 1'b0;
        wready    <= 1'b0;
        bvalid    <= 1'b0;
        arready   <= 1'b0;
        rvalid    <= 1'b0;
        rlast     <= 1'b0;
        h_mem_wr_req <= 1'b0;

        host_attached   <= 1'b0;
        host_reset      <= 1'b0;
        cpu_power_off   <= 1'b0;
        skip_pwrup      <= 1'b0;
        cfg_clk_div     <= 6'd8;      // 4 MHz
        cfg_wait_states <= 4'd0;
        cfg_int_vector  <= 8'hFF;
        cfg_small_mode  <= 1'b1;      // board runs small mode until RQ/AK rework
        cfg_use_core    <= 1'b0;      // default: socketed chip (known-good path)
        cfg_wait_rand   <= 1'b0;      // default: uniform cfg_wait_states path
        cfg_wmax        <= 4'd0;
        cfg_wseed       <= 16'hACE1;
        cfg_wait_replay <= 1'b0;
        h_wvec_wr       <= 1'b0;
        h_iords_wr      <= 1'b0;
        h_iords_addr    <= 6'd0;
        h_iords_wdata   <= 16'd0;
        cfg_iords_cnt   <= 7'd0;
        cfg_iords_en    <= 1'b0;
        iords_wptr      <= 7'd0;
        int_req         <= 1'b0;
        nmi_req         <= 1'b0;
        poll_n_out      <= 1'b0;
        cfg_iord        <= 16'hFFFF;
        evt_addr        <= '0;
        evt_delay       <= '0;
        evt_hold        <= '0;
        evt_pin         <= '0;
        evt_arm         <= '0;
        evt_vecsub_en   <= '0;
        cfg_tvec        <= '0;
    end else begin
        awready      <= 1'b0;
        arready      <= 1'b0;
        h_mem_wr_req <= 1'b0;
        h_wvec_wr    <= 1'b0;
        h_iords_wr   <= 1'b0;

        case (st)
        IDLE: begin
            if (arvalid) begin
                axid       <= arid;
                addr       <= araddr;
                beats_left <= arlen;
                arready    <= 1'b1;
                st         <= R_SETUP;
            end else if (awvalid) begin
                axid       <= awid;
                addr       <= awaddr;
                beats_left <= awlen;
                awready    <= 1'b1;
                st         <= W_DATA;
            end
        end

        //--------------------------------------------------------------
        // write path
        //--------------------------------------------------------------
        W_DATA: begin
            wready <= 1'b1;
            if (wvalid && wready) begin
                wready  <= 1'b0;
                wdata_q <= wdata;
                wstrb_q <= wstrb;
                wlast_q <= wlast;

                if (sel_reg(addr)) begin
                    case (addr[7:0])
                    8'h04: begin
                        host_attached <= 1'b1;
                        host_reset    <= wdata[0];
                        cpu_power_off <= wdata[1];
                        skip_pwrup    <= wdata[2];
                    end
                    8'h08: begin
                        cfg_clk_div     <= wdata[5:0];
                        cfg_wait_states <= wdata[11:8];
                        cfg_int_vector  <= wdata[23:16];
                        cfg_small_mode  <= wdata[24];
                        cfg_use_core    <= wdata[25];
                    end
                    8'h0C: begin
                        int_req    <= wdata[0];
                        nmi_req    <= wdata[1];
                        poll_n_out <= wdata[2];
                    end
                    8'h18: cfg_iord <= wdata[15:0];
                    8'h24: begin
                        cfg_wait_rand   <= wdata[0];
                        cfg_wait_replay <= wdata[1];
                        cfg_wmax        <= wdata[7:4];
                        cfg_wseed       <= wdata[31:16];
                    end
                    8'h28: begin                       // IORDS_CTL
                        if (wdata[0]) begin            // reset the sequence
                            iords_wptr    <= 7'd0;
                            cfg_iords_cnt <= 7'd0;
                        end
                        cfg_iords_en <= wdata[1];      // enable FIFO serving
                    end
                    8'h2C: begin                       // IORDS_PUSH: append one
                        if (iords_wptr < 7'd64) begin  // DEPTH guard
                            h_iords_addr  <= iords_wptr[5:0];
                            h_iords_wdata <= wdata[15:0];
                            h_iords_wr    <= 1'b1;
                            iords_wptr    <= iords_wptr + 7'd1;
                            cfg_iords_cnt <= iords_wptr + 7'd1;
                        end
                    end
                    8'h40: cfg_tvec      <= wdata;             // TVEC {CS, IP}
                    8'h44: evt_vecsub_en <= wdata[EVT_N-1:0];  // VECCTL
                    // EVT_ADDR / EVT_CFG for every scheduler, one unpacker
                    default: begin
                        if (ev_is_addr)
                            evt_addr[ev_sel*20 +: 20] <= wdata[19:0];
                        if (ev_is_cfg) begin
                            evt_delay[ev_sel*16 +: 16] <= wdata[15:0];
                            evt_hold [ev_sel*12 +: 12] <= {wdata[30:27],
                                                           wdata[23:16]};
                            evt_pin  [ev_sel*3  +:  3] <= wdata[26:24];
                            evt_arm  [ev_sel]          <= wdata[31];
                        end
                    end
                    endcase
                    st <= W_NEXT;
                end else if (sel_mem(addr)) begin
                    st <= W_MEM0;
                end else if (sel_wvec(addr)) begin
                    st <= W_WVEC;
                end else begin
                    st <= W_NEXT;   // capture region is read-only
                end
            end
        end

        W_MEM0: begin
            if (wstrb_q[1:0] != 0) begin
                h_mem_addr   <= {addr[19:2], 2'b00};
                h_mem_wdata  <= wdata_q[15:0];
                h_mem_be     <= wstrb_q[1:0];
                h_mem_wr_req <= 1'b1;
            end
            st <= W_MEM1;
        end

        W_MEM1: begin
            if (wstrb_q[3:2] != 0) begin
                h_mem_addr   <= {addr[19:2], 2'b10};
                h_mem_wdata  <= wdata_q[31:16];
                h_mem_be     <= wstrb_q[3:2];
                h_mem_wr_req <= 1'b1;
            end
            st <= W_NEXT;
        end

        W_WVEC: begin
            // whole 32-bit word = 4 packed Tw entries; addr[11:2] = word index
            h_wvec_addr  <= addr[11:2];
            h_wvec_wdata <= wdata_q;
            h_wvec_wr    <= 1'b1;
            st           <= W_NEXT;
        end

        W_NEXT: begin
            if (wlast_q || beats_left == 0) begin
                bid    <= axid;
                bvalid <= 1'b1;
                st     <= B_RESP;
            end else begin
                beats_left <= beats_left - 4'd1;
                addr       <= addr + 21'd4;
                st         <= W_DATA;
            end
        end

        B_RESP: begin
            if (bready) begin
                bvalid <= 1'b0;
                st     <= IDLE;
            end
        end

        //--------------------------------------------------------------
        // read path
        //--------------------------------------------------------------
        R_SETUP: begin
            h_mem_addr <= {addr[19:2], 2'b00};   // low half first
            h_cap_addr <= addr[14:3];
            lat        <= 2'd3;
            st         <= R_WAIT;
        end

        R_WAIT: begin
            lat <= lat - 2'd1;
            if (lat == 1) begin
                if (sel_mem(addr)) begin
                    if (h_mem_addr[1] == 1'b0) begin
                        rd_lo      <= h_mem_rdata;      // low half done,
                        h_mem_addr <= {addr[19:2], 2'b10}; // start high half
                        lat        <= 2'd3;
                    end else begin
                        rdata <= {h_mem_rdata, rd_lo};
                        st    <= R_DATA;
                    end
                end else if (sel_cap(addr)) begin
                    rdata <= addr[2] ? h_cap_rdata[63:32] : h_cap_rdata[31:0];
                    st    <= R_DATA;
                end else begin
                    case (addr[7:0])
                    8'h00: rdata <= MAGIC;
                    8'h04: rdata <= {29'd0, skip_pwrup, cpu_power_off, host_reset};
                    8'h08: rdata <= {6'd0, cfg_use_core, cfg_small_mode,
                                     cfg_int_vector,
                                     4'd0, cfg_wait_states, 2'd0, cfg_clk_div};
                    8'h0C: rdata <= {29'd0, poll_n_out, nmi_req, int_req};
                    8'h10: rdata <= {25'd0, vec_used, evt_fired,
                                     cap_full, cpu_running, pwr_good};
                    8'h14: rdata <= {19'd0, cap_count};
                    8'h18: rdata <= {16'd0, cfg_iord};
                    8'h24: rdata <= {cfg_wseed, 8'd0, cfg_wmax, 2'd0,
                                     cfg_wait_replay, cfg_wait_rand};
                    8'h28: rdata <= {23'd0, cfg_iords_cnt, 1'd0, cfg_iords_en};
                    8'h40: rdata <= cfg_tvec;
                    8'h44: rdata <= {{(32-EVT_N){1'b0}}, evt_vecsub_en};
                    // EVERY new register has a readback: INV-1's root cause was
                    // that the rig silently applied a directive other than the
                    // one it was handed, and the readback is what makes that
                    // checkable.  One packer, indexed, for all EVT_N pairs.
                    default: begin
                        if (ev_is_addr)
                            rdata <= {12'd0, evt_addr[ev_sel*20 +: 20]};
                        else if (ev_is_cfg)
                            rdata <= {evt_arm[ev_sel],
                                      evt_hold [ev_sel*12 + 8 +: 4],
                                      evt_pin  [ev_sel*3      +: 3],
                                      evt_hold [ev_sel*12     +: 8],
                                      evt_delay[ev_sel*16     +: 16]};
                        else
                            rdata <= 32'hDEADBEEF;
                    end
                    endcase
                    st <= R_DATA;
                end
            end
        end

        R_DATA: begin
            rid    <= axid;
            rlast  <= beats_left == 0;
            rvalid <= 1'b1;
            st     <= R_NEXT;
        end

        R_NEXT: begin
            if (rvalid && rready) begin
                rvalid <= 1'b0;
                rlast  <= 1'b0;
                if (beats_left == 0) begin
                    st <= IDLE;
                end else begin
                    beats_left <= beats_left - 4'd1;
                    addr       <= addr + 21'd4;
                    st         <= R_SETUP;
                end
            end
        end

        default: st <= IDLE;
        endcase
    end
end

endmodule
