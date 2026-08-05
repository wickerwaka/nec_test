# SM3 sitting 12 — the R7′ cone measurement, on BOTH configurations

Evidence for `ucore_provenance.md` **§73** and
`docs/notes/sm3_s12_prereg_2026-08-04.md` §1-§2.

`cone.tcl` is `sm3_s9_r7/tprobe.tcl` with one thing added that the sitting-9
probe did not have: **the full arrival-point node list of the worst
`c_ready_q` path**, so the cone is read structurally instead of inferred from
its endpoint.

    quartus_sta -t cone.tcl <outfile>

against a post-fit netlist.  Both netlists are preserved whole (db +
incremental_db + reports) under

    ~/.cache/ucsimt-tmp/sm3s12/ctrl/        macro OFF, incremental
    ~/.cache/ucsimt-tmp/sm3s12/ctrl_clean/  macro OFF, CLEAN db  — identical
    ~/.cache/ucsimt-tmp/sm3s12/ret/         macro ON            — the flashable one

| file | netlist | headline |
|---|---|---|
| `CTRL_cone.txt` | control, macro OFF | **20,000 / 20,000 failing paths launch from `c_ready_q` and capture in `v30u_eu`**; worst 62–63 levels, 51.2 ns, → `v30u_eu\|opc_base[3]`; slack −20.254 |
| `RET_cone.txt` | retention, macro ON | **0 failing paths**; worst `c_ready_q` path 19–20 levels, +11.372, → `v30u_eu\|row_posted` |

**The two builds have exchanged places against §69/§70**, where the control was
the one at 45.67 MHz and the retention build the one at 20.25.  Same RTL
difference (20 flops on the capture path), opposite outcome — which is what
§70.5 predicted the fragility would look like.
