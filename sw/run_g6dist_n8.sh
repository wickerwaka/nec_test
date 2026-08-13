#!/bin/sh
# The N=8 baseline characterisation, both configurations, SEQUENTIALLY.
# They share hdl/db and hdl/output_files_ucore, so they cannot overlap.
set -x
cd "$(dirname "$0")/.." || exit 1
python3 sw/quartus_gate.py --seeds 8 --label g6dist-control-n8 \
    --log hdl/g6dist_control.log
echo "CONTROL sweep exit $?"
python3 sw/quartus_gate.py --seeds 8 --retention --label g6dist-retention-n8 \
    --log hdl/g6dist_retention.log
echo "RETENTION sweep exit $?"
