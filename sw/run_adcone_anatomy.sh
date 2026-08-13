#!/bin/bash
# ANATOMY DRIVER for the `ucrom -> ad_o` launch-cone wave.
#
# Replicates `quartus_gate.py --seeds` exactly -- ONE pre-flow, ONE
# `quartus_map`, then `quartus_fit --seed=S --recompile=off` per seed -- and
# runs the ANATOMY probes after each fit instead of (only) the gate's own.
# It is NOT a gate and produces no receipt: the quotable numbers come from
# `quartus_gate.py --seeds`.  This exists because the gate deletes each fit's
# `db` before the next one and an anatomy needs the fitted netlist.
#
#   sw/run_adcone_anatomy.sh <outdir> <seed> [<seed> ...]
set -e
Q="$HOME/intelFPGA_lite/17.1/quartus/bin"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$1"; shift
mkdir -p "$ROOT/$OUT"

# single-writer guard (sec.12 of the distribution gate): match stage binaries by
# EXACT name, never by argv -- `pgrep -f` would match this script itself.
for b in quartus_map quartus_fit quartus_sta quartus_asm; do
    if pgrep -x "$b" >/dev/null 2>&1; then
        echo "REFUSING: $b is already running -- two writers on one hdl/db" >&2
        exit 9
    fi
done

cd "$ROOT/hdl"
rm -rf db incremental_db
"$Q/quartus_sh" -t sys/build_id.tcl preflow nec_test nec_test_ucore
"$Q/quartus_map" nec_test -c nec_test_ucore > "$ROOT/$OUT/map.log" 2>&1
echo "MAP done"

for S in "$@"; do
    "$Q/quartus_fit" --seed="$S" --recompile=off nec_test -c nec_test_ucore \
        > "$ROOT/$OUT/fit$S.log" 2>&1
    "$Q/quartus_sta" nec_test -c nec_test_ucore > "$ROOT/$OUT/sta$S.log" 2>&1
    cp output_files_ucore/nec_test_ucore.sta.summary "$ROOT/$OUT/seed$S.sta.summary"
    grep -E "Fitter Initial Placement Seed|--seed=" \
        output_files_ucore/nec_test_ucore.fit.rpt | head -4 \
        > "$ROOT/$OUT/seed$S.seedecho.txt" || true
    "$Q/quartus_sta" -t "$ROOT/sw/sta_adcone_anatomy.tcl" \
        nec_test nec_test_ucore "$ROOT/$OUT/seed$S" 60 \
        > "$ROOT/$OUT/anat$S.log" 2>&1 || echo "anatomy rc=$? seed $S"
    "$Q/quartus_sta" -t "$ROOT/sw/sta_fmax_attrib.tcl" \
        nec_test nec_test_ucore "$ROOT/$OUT/seed$S" 400 \
        > "$ROOT/$OUT/attrib$S.log" 2>&1 || echo "attrib rc=$? seed $S"
    echo "SEED $S done"
done
echo "ALL DONE"
