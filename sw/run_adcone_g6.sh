#!/bin/bash
# The wave's G6 legs: `--seeds 5`, BOTH configurations, back to back.
# Each invocation carries its own single-writer guard inside quartus_gate.py's
# sweep path; this script waits for any stage binary to be idle first so the
# two sweeps cannot overlap each other or an anatomy run.
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# ⚠ WAIT FOR THE *DRIVER*, NOT FOR A STAGE BINARY.  Between an anatomy run's
# `quartus_sta` invocations there is a window in which no stage binary is
# running at all, and a guard that polls only the binaries would step into it
# and put two writers on one `hdl/db` -- the exact defect
# `timing50_distribution_2026-08-13.md` §12 found in flight.
while pgrep -f run_adcone_anatomy.sh >/dev/null 2>&1; do sleep 30; done
for b in quartus_map quartus_fit quartus_sta quartus_asm; do
    while pgrep -x "$b" >/dev/null 2>&1; do sleep 30; done
done
python3 sw/quartus_gate.py --seeds 5 --label adcone-l1-control-n5 \
    --log sw/testdata/adcone/l1/g6_control_n5.log
python3 sw/quartus_gate.py --seeds 5 --retention --label adcone-l1-retention-n5 \
    --log sw/testdata/adcone/l1/g6_retention_n5.log
echo "G6 BOTH CONFIGURATIONS DONE"
