# SM3 sitting 9 — the R7 measurement

Evidence for `ucore_provenance.md` **§70** (R7 refuted; `nec_test.sdc` NOT
edited).  Everything here is a TimeQuest query against a POST-FIT netlist —
no build is needed to re-run any of it, because both netlists are preserved
whole (db + incremental_db + reports) under:

    ~/.cache/ucsimt-tmp/sm3s9/ctrl_flash5/   macro OFF  — FLASH #5's numbers
    ~/.cache/ucsimt-tmp/sm3s9/ret_oldsdc/    macro ON   — the retention build

To re-query: copy one of those `db/`, `incremental_db/` and
`output_files_ucore/` into `hdl/`, then from `hdl/`

    quartus_sta -t <probe>.tcl <outfile>

## The probes

| file | what it asks |
|---|---|
| `tprobe.tcl` | worst setup paths; `-from c_ready_q`; paths to/from `core_ad_hold`; and a census of the launch register and capture module of every failing path |
| `fanin3.tcl` | which pins a register actually exposes (`d` / `ena` / `asdata` / `sclr` / `sload`) and whether `c_ready_q`, `div_cnt` or the register itself appear in each pin's fanin |
| `overapply.tcl` | the SDC's own falsifier — for every collected register, is there evidence of a clock enable?  **Incomplete by construction; see §70.6** |

## The outputs

| file | netlist |
|---|---|
| `ret_tprobe.txt` | retention.  20,000 of 20,000 failing paths launch from `system_large\|c_ready_q`; 20,000 of 20,000 capture in `v30u_eu` |
| `ctrl_tprobe.txt` | control.  `-from c_ready_q -to *wb_kind*` = **0 paths**.  The run ends with a Tcl error, which is expected and harmless: the control has no `core_ad_hold` registers, so `get_timing_paths -to <empty collection>` raises.  Everything before that point is complete, and the control's failing-path census is empty by definition (TNS 0.000) |
| `ctrl_fanin3.txt` | control.  `wb_kind[1]` has no `c_ready_q` in its fanin; `row_posted` does |
| `ctrl_overapply.txt` | control.  1,014 of 2,220 expose an `ena` pin, 1,719 a `d` pin, 1,291 neither — the instrument gap §70.6 books |

## Gotchas paid for here

* **`get_fanins` on a REGISTER node returns nothing.**  It must be given the
  register's PIN (`…|d`, `…|ena`).  Two probes were written and discarded
  before this was noticed.
* **`get_fanins -no_logic` does not traverse combinational logic.**  It is the
  wrong flag for "what registers feed this one".
* **`get_fanouts <src> -no_logic -through [get_pins *|ena]`** — the recipe
  TimeQuest's own `help get_fanouts` prints for exactly this job — returns an
  **empty collection** in 17.1 Lite on this netlist.  Recorded as tried.
* **The SDC's collection-size `Info` line is printed EIGHT times per flow.**
  Comparing two builds means comparing the same occurrence.  Not doing so is
  what R7 was.
