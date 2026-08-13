#!/bin/bash
# ANATOMY DRIVER for the `c_int_q -> v30u_eu` launch-cone wave.
#
# The `sw/run_adcone_anatomy.sh` driver, aimed at the other rig<->core
# single-cycle crossing.  Replicates `quartus_gate.py --seeds` exactly -- ONE
# pre-flow, ONE `quartus_map`, then `quartus_fit --seed=S --recompile=off` per
# seed -- and runs the INT-cone probes after each fit.  It is NOT a gate and
# writes no receipt; the quotable numbers come from `quartus_gate.py --seeds`.
# This exists because the gate deletes each fit's `db` before the next one and
# an anatomy needs the fitted netlist.
#
#   sw/run_intcone_anatomy.sh <outdir> [--retention] <seed> [<seed> ...]
set -e
Q="$HOME/intelFPGA_lite/17.1/quartus/bin"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$1"; shift
MACRO=""
if [ "$1" = "--retention" ]; then MACRO="--verilog_macro=X1_AD_RETENTION=1"; shift; fi
mkdir -p "$ROOT/$OUT"

# single-writer guard (distribution gate §12): match stage binaries by EXACT
# name, never by argv -- `pgrep -f` would match this script itself.
for b in quartus_map quartus_fit quartus_sta quartus_asm; do
    if pgrep -x "$b" >/dev/null 2>&1; then
        echo "REFUSING: $b is already running -- two writers on one hdl/db" >&2
        exit 9
    fi
done

cd "$ROOT/hdl"
rm -rf db incremental_db
"$Q/quartus_sh" -t sys/build_id.tcl preflow nec_test nec_test_ucore
# shellcheck disable=SC2086
"$Q/quartus_map" $MACRO nec_test -c nec_test_ucore > "$ROOT/$OUT/map.log" 2>&1
echo "MAP done (${MACRO:-CONTROL})"

for S in "$@"; do
    "$Q/quartus_fit" --seed="$S" --recompile=off nec_test -c nec_test_ucore \
        > "$ROOT/$OUT/fit$S.log" 2>&1
    "$Q/quartus_sta" nec_test -c nec_test_ucore > "$ROOT/$OUT/sta$S.log" 2>&1
    cp output_files_ucore/nec_test_ucore.sta.summary "$ROOT/$OUT/seed$S.sta.summary"
    grep -E "Fitter Initial Placement Seed" \
        output_files_ucore/nec_test_ucore.fit.rpt | head -2 \
        > "$ROOT/$OUT/seed$S.seedecho.txt" || true
    "$Q/quartus_sta" -t "$ROOT/sw/sta_intcone_anatomy.tcl" \
        nec_test nec_test_ucore "$ROOT/$OUT/seed$S" 60 \
        > "$ROOT/$OUT/intanat$S.log" 2>&1 || echo "intanat rc=$? seed $S"
    "$Q/quartus_sta" -t "$ROOT/sw/sta_intcone_probe.tcl" \
        nec_test nec_test_ucore "$ROOT/$OUT/seed$S" \
        > "$ROOT/$OUT/intcone$S.log" 2>&1 || echo "intcone rc=$? seed $S"
    "$Q/quartus_sta" -t "$ROOT/sw/sta_truefmax_probe.tcl" \
        nec_test nec_test_ucore "$ROOT/$OUT/seed$S" \
        > "$ROOT/$OUT/truefmax$S.log" 2>&1 || echo "truefmax rc=$? seed $S"
    echo "SEED $S done"
done
echo "ALL DONE"
