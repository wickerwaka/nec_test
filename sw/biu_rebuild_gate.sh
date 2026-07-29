#!/usr/bin/env bash
# biu_rebuild_gate.sh - the FULL standing gate battery for the BIU prefetch/
# bus-grid rebuild campaign (task #34). Board-free. Run at every substage and
# stage boundary (plan: jiggly-zooming-harbor.md, Verification section).
# Superset of t30_sweep.sh: adds check_enter_nesting (MASK+WAITED), check_fuzz
# _bank, the offline fuzz verdict/accept tests, and a bounded savestate sweep.
# Builds a FRESH Verilator binary first (class5 method rule: a stale binary
# that reproduces the baseline to the row is a SMELL, not a pass).
# Detached usage: nohup setsid bash sw/biu_rebuild_gate.sh > sw/<log> 2>&1 &
# then watch the log MTIME until the DONE marker appears.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
echo "=== BIU-REBUILD gate battery  $(date -u +%Y-%m-%dT%H:%M:%SZ)  HEAD=$(git rev-parse --short HEAD) branch=$(git branch --show-current) ==="

step() { echo; echo "### $*"; }

step "build fresh Verilator binary"
python3 sw/check_core.py --build --suite-dir tests/v30/v0.1 --opcodes all --cases 1 --waits 0 2>&1 | tail -2

step "lints (ss_lint now includes ss_flopcensus)"
python3 sw/ss_lint.py             2>&1 | tail -4
python3 sw/prefix_clear_lint.py   2>&1 | tail -1
python3 sw/ea_step_lint.py        2>&1 | tail -1
python3 sw/check_race_law.py      2>&1 | tail -1
python3 sw/optable.py --selfcheck 2>&1 | tail -1
python3 sw/fuzz_campaign.py lint --n 10000 --raw-n 100000 2>&1 | tail -1

step "offline verdict/accept unit gates"
python3 sw/test_fuzz_classify.py  2>&1 | tail -1
python3 sw/test_fuzz_accept.py    2>&1 | tail -1

step "standing gates"
python3 sw/check_ff_t4.py         2>&1 | tail -1
python3 sw/check_mod3_illegal.py  2>&1 | tail -1
python3 sw/check_enter_nesting.py 2>&1 | tail -3
python3 sw/check_fuzz_bank.py     2>&1 | tail -3

step "v0.1 w0 (169k, all forms)"
python3 sw/check_core.py --suite-dir tests/v30/v0.1 --opcodes all --cases 0 --waits 0 2>&1 | tail -1
step "v0.1-w1 (1200)"
python3 sw/check_core.py --suite-dir tests/v30/v0.1-w1 --opcodes all --cases 0 --waits 1 2>&1 | tail -1
step "v0.1-w3 (1200)"
python3 sw/check_core.py --suite-dir tests/v30/v0.1-w3 --opcodes all --cases 0 --waits 3 2>&1 | tail -1
step "f0lock_tranche"
python3 sw/check_core.py --suite-dir tests/v30/f0lock_tranche --opcodes all --cases 0 --waits 0 2>&1 | tail -1
step "f4a_boundary"
python3 sw/check_core.py --suite-dir tests/v30/f4a_boundary --opcodes all --cases 0 --waits 0 2>&1 | tail -1
step "savestate sweep (mode 5 round-trip width, bounded cases)"
python3 sw/check_core.py --suite-dir tests/v30/v0.1 --opcodes all --cases 8 --waits 0 --ss-sweep 1 --ss-mode 5 2>&1 | tail -2
step "v0.3 w0 (3.7M, all forms)"
python3 sw/check_core.py --suite-dir tests/v30/v0.3 --opcodes all --cases 0 --waits 0 2>&1 | tail -1

echo; echo "=== BASELINE_BATTERY_DONE  $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
