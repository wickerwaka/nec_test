#!/bin/bash
# fz2 FLASH #14 sitting -- RETENTION build draw, manual recipe.
# Reproduces the command sequence recorded in hdl/quartus_gate_f13_ret_draw1.log.
# Usage: _s14_ret_draw.sh <drawname>
set -u
DRAW="${1:?draw name}"
Q=/home/wickerwaka/intelFPGA_lite/17.1/quartus/bin
ROOT=/home/wickerwaka/src/nec_test
LOG="$ROOT/hdl/quartus_gate_s14_${DRAW}.log"
cd "$ROOT/hdl" || exit 2

rm -rf db incremental_db output_files_ucore
: > "$LOG"
for step in "quartus_map --verilog_macro=X1_AD_RETENTION=1 nec_test -c nec_test_ucore" \
            "quartus_fit nec_test -c nec_test_ucore" \
            "quartus_asm nec_test -c nec_test_ucore" \
            "quartus_sta nec_test -c nec_test_ucore"; do
    bin="$Q/${step%% *}"
    args="${step#* }"
    echo "=== COMMAND: $bin $args ===" >> "$LOG"
    # shellcheck disable=SC2086
    "$bin" $args >> "$LOG" 2>&1
    rc=$?
    echo "=== RC: $rc ===" >> "$LOG"
    if [ $rc -ne 0 ]; then
        echo "STEP FAILED rc=$rc: $step" | tee -a "$LOG"
        exit $rc
    fi
done
echo "BUILD OK -> gating" | tee -a "$LOG"
cd "$ROOT" || exit 2
python3 sw/quartus_gate.py --parse-only --no-qsf-check \
        --label "fz2 FLASH#14 RETENTION ${DRAW}" \
        --log "hdl/quartus_gate_s14_${DRAW}_gate.log" 2>&1 | tee -a "$LOG"
