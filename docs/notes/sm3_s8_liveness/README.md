# SM3 sitting 8 — the LIVENESS evidence for the `AD_OE`-keyed retention model

`ucore_provenance.md` §69.3.  This directory holds §59.7.1's isolated-construct
test, re-run in both forms on the same machine and the same Quartus
(17.1.0 Build 590 Lite, `5CSEBA6U23I7`), because a grep for a register name in
`nec_test_ucore.fit.rpt` is a weak instrument — that report does not name
ordinary internal registers at all (`c_ready_q`, `c_addrv_q`, `hb_ad_dir`,
`core_ad_eff`, `bus_tick_rise` are **0 occurrences each** in FLASH #5's own fit
report, and they all exist).

Both files are the SAME construct — a two-driver internal `tri` net, a 20-bit
hold register, nothing else — differing only in how "is anyone driving" is
asked.

    quartus_map top --family="Cyclone V" --part=5CSEBA6U23I7 --source=top.sv

| | `zform.sv.attempt` (asks the NET, `=== 1'bz`) | `oeform.sv.attempt` (asks the PORT) |
|---|---|---|
| `Total registers` | **0** | **20** |
| logic cells | 17 | 40 |
| `Warning (15610)` | **`No output dependent on input pin "clk"`** | — |

**0 against 20 is the whole of what the user's decision bought.**  §59.7.1's
finding is reproduced exactly in the left column, so the right column is a
measurement against a working control and not against an assumption.

Corroborated in the real design: `system_large`'s OWN dedicated logic registers
in `Fitter Resource Utilization by Entity` go **27 → 47** between the
retention-OFF and retention-ON builds of the same tree, and whole-design A&S
`Total registers` go **4,797 → 4,817**.  Exactly +20, twice, independently.

These are `.attempt` files by the `class5_*.sv.attempt` precedent: retained
evidence, never in any build's file list.
