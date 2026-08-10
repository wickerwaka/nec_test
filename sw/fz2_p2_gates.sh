#!/bin/sh
# fz2 P2 -- the offline gate ladder, cheapest first.  Not a gate itself: it
# just runs them in one place so the results document quotes one transcript.
set -x
cd "$(dirname "$0")/.." || exit 1
python3 sw/gen_ucore_qsf.py --check
python3 sw/r7_lint.py
python3 sw/ss_lint.py --core ucore
python3 sw/test_artifact.py
python3 sw/check_core.py --core ucore --opcodes all --cases 0
python3 sw/check_core.py --core ucore --suite-dir tests/v30/s10-hltsweep-w0 --waits 0
python3 sw/check_core.py --core ucore --suite-dir tests/v30/s10-hltsweep-w1 --waits 1
python3 sw/check_core.py --core ucore --suite-dir tests/v30/s13-hltsweep-w2 --waits 2
python3 sw/check_core.py --core ucore --suite-dir tests/v30/s13-hltsweep-w3 --waits 3
python3 sw/check_core.py --core ucore --suite-dir tests/v30/v0.1-w0evt --waits 0
python3 sw/check_core.py --core ucore --suite-dir tests/v30/v0.1-w1evt --waits 1
python3 sw/check_core.py --core ucore --suite-dir tests/v30/v0.1-w2evt --waits 2
python3 sw/check_core.py --core ucore --suite-dir tests/v30/v0.1-w3evt --waits 3
python3 sw/check_core.py --core ucore --suite-dir tests/v30/v0.1-w1evt-biased --waits 1
python3 sw/check_boot.py --core ucore --timed 220
python3 sw/check_boot.py --core ucore --timed 400
python3 sw/check_fuzz_bank.py
python3 sw/fz2_w1.py lint
