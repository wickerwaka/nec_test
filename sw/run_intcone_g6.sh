#!/bin/bash
# THE WAVE-END G6 LEGS: `--seeds 5`, BOTH configurations, back to back, on the
# final tree -- and they are the first sweeps to report the PAIRED figure
# (`standing_gates.md` §A, adopted 2026-08-13).
#
# `sw/run_adcone_g6.sh` with this wave's labels and one addition: after the
# RETENTION sweep it re-fits that sweep's own map at the seed that bound the
# RETENTION `worst-of-5` and runs the INT-cone probes on it.  Re-fitting on the
# retained map costs one fit instead of a map plus a fit, and it keeps the
# anatomy on the SAME netlist the quoted figure was drawn from.
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
Q="$HOME/intelFPGA_lite/17.1/quartus/bin"
cd "$ROOT"
OUT=sw/testdata/intcone
mkdir -p "$OUT"

# ⚠ WAIT FOR THE *DRIVER*, NOT FOR A STAGE BINARY (run_adcone_g6.sh's own
# note): between an anatomy run's `quartus_sta` invocations no stage binary is
# running at all, and a guard that polls only the binaries steps into that
# window and puts two writers on one `hdl/db`.
while pgrep -f run_intcone_anatomy.sh >/dev/null 2>&1; do sleep 30; done
while pgrep -f run_adcone_anatomy.sh  >/dev/null 2>&1; do sleep 30; done
for b in quartus_map quartus_fit quartus_sta quartus_asm; do
    while pgrep -x "$b" >/dev/null 2>&1; do sleep 30; done
done

python3 sw/quartus_gate.py --seeds 5 --label intcone-control-n5 \
    --log "$OUT/g6_control_n5.log"
python3 sw/quartus_gate.py --seeds 5 --retention --label intcone-retention-n5 \
    --log "$OUT/g6_retention_n5.log"
echo "G6 BOTH CONFIGURATIONS DONE"

# --- the RETENTION INT-cone anatomy, on the sweep's own map ----------------- #
# The seed is passed in ($1); it is the seed that bound the RETENTION
# worst-of-5, read off that sweep's distribution record.
SEED="${1:-2}"
mkdir -p "$OUT/anat-ret"
"$Q/quartus_fit" --seed="$SEED" --recompile=off nec_test -c nec_test_ucore \
    > "$OUT/anat-ret/fit$SEED.log" 2>&1
"$Q/quartus_sta" nec_test -c nec_test_ucore > "$OUT/anat-ret/sta$SEED.log" 2>&1
cp hdl/output_files_ucore/nec_test_ucore.sta.summary \
   "$OUT/anat-ret/seed$SEED.sta.summary"
grep -E "Fitter Initial Placement Seed" \
    hdl/output_files_ucore/nec_test_ucore.fit.rpt | head -2 \
    > "$OUT/anat-ret/seed$SEED.seedecho.txt" || true
"$Q/quartus_sta" -t sw/sta_intcone_anatomy.tcl nec_test nec_test_ucore \
    "$OUT/anat-ret/seed$SEED" 60 > "$OUT/anat-ret/intanat$SEED.log" 2>&1 \
    || echo "intanat rc=$? seed $SEED"
"$Q/quartus_sta" -t sw/sta_intcone_probe.tcl nec_test nec_test_ucore \
    "$OUT/anat-ret/seed$SEED" > "$OUT/anat-ret/intcone$SEED.log" 2>&1 \
    || echo "intcone rc=$? seed $SEED"
"$Q/quartus_sta" -t sw/sta_truefmax_probe.tcl nec_test nec_test_ucore \
    "$OUT/anat-ret/seed$SEED" > "$OUT/anat-ret/truefmax$SEED.log" 2>&1 \
    || echo "truefmax rc=$? seed $SEED"
echo "RETENTION ANATOMY (seed $SEED) DONE"
