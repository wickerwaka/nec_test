#!/bin/bash
# THE WAVE-END CENSUS.
#
#   sw/run_adcone_census.sh ret          -- probe the db the RETENTION sweep left
#   sw/run_adcone_census.sh ctl <seed>   -- re-map CONTROL, fit <seed>, probe it
#
# The retention leg costs nothing: the last sweep's fitted `db` is still on
# disk and a probe cannot change it.  The control leg costs one map + one fit,
# because `quartus_gate` deletes `db` at the start of every sweep and the
# CONTROL one ran first.
set -e
Q="$HOME/intelFPGA_lite/17.1/quartus/bin"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LEG="$1"
OUT="$ROOT/sw/testdata/adcone/l1/census-$LEG"
mkdir -p "$OUT"
while pgrep -f run_adcone_g6.sh >/dev/null 2>&1; do sleep 30; done
for b in quartus_map quartus_fit quartus_sta quartus_asm; do
    while pgrep -x "$b" >/dev/null 2>&1; do sleep 30; done
done
cd "$ROOT/hdl"

if [ "$LEG" = "ctl" ]; then
    SEED="$2"
    rm -rf db incremental_db
    "$Q/quartus_sh" -t sys/build_id.tcl preflow nec_test nec_test_ucore
    "$Q/quartus_map" nec_test -c nec_test_ucore > "$OUT/map.log" 2>&1
    "$Q/quartus_fit" --seed="$SEED" --recompile=off nec_test -c nec_test_ucore \
        > "$OUT/fit.log" 2>&1
    "$Q/quartus_sta" nec_test -c nec_test_ucore > "$OUT/sta.log" 2>&1
    cp output_files_ucore/nec_test_ucore.sta.summary "$OUT/sta.summary"
fi

"$Q/quartus_sta" -t "$ROOT/sw/sta_adcone_anatomy.tcl" \
    nec_test nec_test_ucore "$OUT/x" 60 > "$OUT/anat.log" 2>&1 || echo "anat rc=$?"
"$Q/quartus_sta" -t "$ROOT/sw/sta_census.tcl" \
    nec_test nec_test_ucore "$OUT/x" > "$OUT/census.log" 2>&1 || echo "census rc=$?"
"$Q/quartus_sta" -t "$ROOT/sw/sta_fmax_attrib.tcl" \
    nec_test nec_test_ucore "$OUT/x" 400 > "$OUT/attrib.log" 2>&1 || echo "attrib rc=$?"
python3 "$ROOT/sw/ucrom_mif_check.py" | tee "$OUT/mifcheck.txt"
echo "CENSUS $LEG DONE"
