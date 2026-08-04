#!/usr/bin/env bash
# t30_sweep.sh - full standing sweep gate before the task #30 reflash (RR-era
# bar for EU decode-path changes). Runs all lints + standing gates + every
# golden suite against the current RTL. Any non-full suite total or failed
# gate = regression. Detached, logged.
#
# *** THIS IS THE ARCHIVED FSM CORE'S SWEEP (2026-08-04). ***
# Every leg below is FSM-structural: check_race_law / ea_step_lint /
# prefix_clear_lint / check_ff_t4 / check_mod3_illegal all read or mutate
# hdl/rtl/core/*.sv and have no ucore counterpart.  `--core fsm` and
# `--core fsm` on ss_lint are now passed EXPLICITLY so this script keeps its
# meaning after check_core.py's default flipped fsm -> ucore on 2026-08-04.
# It is an ON-DEMAND gate (run before re-activating the FSM core), not part of
# the standing set.  See docs/notes/fsm_core_archive_2026-08-04.md and
# docs/notes/standing_gates.md.
#
# NOTE: the FSM core's v0.1 total on the CORRECTED comparator (the TB's
# composed-AD mask removed at U5) is 168,400/169,000, not 169,000 - the 600
# HLT.INT/HLT.RES/HLT.NMI cases are 0/600 (F51, unfixed here). "Any non-full
# suite total = regression" must be read against that, not against 169,000.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
echo "=== T30 full standing sweep  $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="

step() { echo; echo "### $*"; }

step "lints"
python3 sw/ss_lint.py --core fsm 2>&1 | tail -1
python3 sw/prefix_clear_lint.py  2>&1 | tail -1
python3 sw/ea_step_lint.py       2>&1 | tail -1
python3 sw/check_race_law.py     2>&1 | tail -1
python3 sw/optable.py --selfcheck 2>&1 | tail -1
python3 sw/fuzz_campaign.py lint --n 10000 --raw-n 100000 2>&1 | tail -1

step "standing gates"
python3 sw/check_ff_t4.py        2>&1 | tail -1
python3 sw/check_mod3_illegal.py 2>&1 | tail -1

step "v0.1 w0 (169k, all forms)"
python3 sw/check_core.py --core fsm --suite-dir tests/v30/v0.1 --opcodes all --cases 0 --waits 0 2>&1 | tail -1
step "v0.1-w1"
python3 sw/check_core.py --core fsm --suite-dir tests/v30/v0.1-w1 --opcodes all --cases 0 --waits 1 2>&1 | tail -1
step "v0.1-w3"
python3 sw/check_core.py --core fsm --suite-dir tests/v30/v0.1-w3 --opcodes all --cases 0 --waits 3 2>&1 | tail -1
step "f0lock_tranche"
python3 sw/check_core.py --core fsm --suite-dir tests/v30/f0lock_tranche --opcodes all --cases 0 --waits 0 2>&1 | tail -1
step "f4a_boundary"
python3 sw/check_core.py --core fsm --suite-dir tests/v30/f4a_boundary --opcodes all --cases 0 --waits 0 2>&1 | tail -1
step "v0.3 w0 (3.7M, all forms)"
python3 sw/check_core.py --core fsm --suite-dir tests/v30/v0.3 --opcodes all --cases 0 --waits 0 2>&1 | tail -1

echo; echo "=== T30 sweep DONE  $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
