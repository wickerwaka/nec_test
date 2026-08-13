#!/bin/sh
# The N=8 baseline characterisation, both configurations, SEQUENTIALLY.
# They share hdl/db and hdl/output_files_ucore, so they cannot overlap.
set -x
cd "$(dirname "$0")/.." || exit 1

# ⚠ SINGLE WRITER.  Both sweeps compile in the SAME hdl/ tree and share
# hdl/db + hdl/output_files_ucore, so a second sweep running concurrently
# would interleave its reports with this one's and BOTH sets of figures would
# be attributed to the wrong fits.  Measured: an orphaned run survived a
# `pkill` and was found fitting alongside a fresh one.  This is the board
# discipline's single-writer check, applied to the build tree.
# The stage binaries are checked by EXACT NAME (`pgrep -x`), never by command
# line: a `pgrep -f 'quartus_gate.py --seeds'` matches its OWN argv and so
# refuses every run, which is a guard that is broken in the safe direction and
# therefore never noticed.
for stage in quartus_map quartus_fit quartus_asm quartus_sta; do
    if pgrep -x "$stage" >/dev/null; then
        echo "REFUSING: $stage is already running against this tree --"
        echo "  two sweeps sharing hdl/db would interleave their reports and"
        echo "  BOTH sets of figures would be attributed to the wrong fits."
        pgrep -a -x "$stage"
        exit 2
    fi
done
python3 sw/quartus_gate.py --seeds 8 --label g6dist-control-n8 \
    --log hdl/g6dist_control.log
echo "CONTROL sweep exit $?"
python3 sw/quartus_gate.py --seeds 8 --retention --label g6dist-retention-n8 \
    --log hdl/g6dist_retention.log
echo "RETENTION sweep exit $?"
