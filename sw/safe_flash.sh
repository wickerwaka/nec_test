#!/usr/bin/env bash
#
# safe_flash.sh - the ONLY sanctioned way to reprogram the harness FPGA.
#
# Atomic prep -> quartus_pgm -> status-verify, each step with a timeout:
#   1. PREP   : over ssh, kill MiSTer Main and put the HPS<->FPGA bridges in
#               reset (v30ctl.py prep). An in-flight bridge access during JTAG
#               reconfiguration hard-locks the ARM, so this MUST run first.
#   2. FLASH  : quartus_pgm loads the .sof over JTAG (same invocation as the
#               Makefile's `run` target: p;<sof>@<device>).
#   3. VERIFY : over ssh, v30ctl.py status. Harness() re-enables the bridges
#               and checks the R_MAGIC value (0x56333031) on connect, raising
#               if it is wrong, so a clean `status` is the magic check.
#
# If VERIFY fails the board is presumed unreachable: the script STOPs and tells
# you a physical power cycle is required. Do NOT retry a flash into an
# unreachable board.
#
# Usage: sw/safe_flash.sh [path/to.sof]
#   env: HOST (default root@mister-nec), CABLE (1), DEVICE (2),
#        REMOTE_DIR (/media/fat/v30)
#
set -uo pipefail

SW_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SW_DIR/.." && pwd)"

HOST="${HOST:-root@mister-nec}"
CABLE="${CABLE:-1}"
DEVICE="${DEVICE:-2}"
REMOTE_DIR="${REMOTE_DIR:-/media/fat/v30}"
SOF="${1:-$ROOT/hdl/output_files/nec_test.sof}"

PREP_TIMEOUT="${PREP_TIMEOUT:-40}"
FLASH_TIMEOUT="${FLASH_TIMEOUT:-240}"
VERIFY_TIMEOUT="${VERIFY_TIMEOUT:-40}"
VERIFY_RETRIES="${VERIFY_RETRIES:-3}"

SSH="ssh -o ConnectTimeout=8 -o BatchMode=yes"

log() { printf '[safe_flash] %s\n' "$*"; }
die() { printf '[safe_flash] FATAL: %s\n' "$*" >&2; exit 1; }

[ -f "$SOF" ] || die "sof not found: $SOF"
command -v quartus_pgm >/dev/null 2>&1 || die "quartus_pgm not on PATH"

log "sof   = $SOF"
log "host  = $HOST   cable=$CABLE device=$DEVICE"

# --- 1. PREP -----------------------------------------------------------------
log "step 1/3 PREP: kill MiSTer, hold bridges in reset"
if ! timeout "$PREP_TIMEOUT" $SSH "$HOST" \
        "killall MiSTer >/dev/null 2>&1; cd '$REMOTE_DIR' && python3 v30ctl.py prep"; then
    die "PREP failed (ssh/prep). Board state unchanged; NOT flashing."
fi

# --- 2. FLASH ----------------------------------------------------------------
log "step 2/3 FLASH: quartus_pgm p;<sof>@$DEVICE"
if ! timeout "$FLASH_TIMEOUT" quartus_pgm -c "$CABLE" -m jtag \
        -o "p;${SOF}@${DEVICE}"; then
    printf '[safe_flash] STOP: quartus_pgm failed. The FPGA may be in an\n' >&2
    printf '            indeterminate state. Verify JTAG, then re-run this\n' >&2
    printf '            script. Do NOT poke the bridge until VERIFY passes.\n' >&2
    exit 2
fi

# --- 3. VERIFY ---------------------------------------------------------------
log "step 3/3 VERIFY: v30ctl.py status (re-enables bridges, checks MAGIC)"
ok=0
for try in $(seq 1 "$VERIFY_RETRIES"); do
    if out=$(timeout "$VERIFY_TIMEOUT" $SSH "$HOST" \
                "cd '$REMOTE_DIR' && python3 v30ctl.py status" 2>&1) \
            && printf '%s' "$out" | grep -q "pwr_good"; then
        log "VERIFY ok (try $try):"
        printf '%s\n' "$out" | sed 's/^/    /'
        ok=1
        break
    fi
    log "VERIFY try $try/$VERIFY_RETRIES did not confirm; retrying..."
    sleep 2
done

if [ "$ok" -ne 1 ]; then
    printf '\n' >&2
    printf '[safe_flash] STOP: board did NOT respond after flashing.\n' >&2
    printf '            The magic check failed on all %s tries.\n' "$VERIFY_RETRIES" >&2
    printf '            A PHYSICAL POWER CYCLE is required. Do NOT retry the\n' >&2
    printf '            flash and do NOT issue any bridge access until the\n' >&2
    printf '            board has been power-cycled.\n' >&2
    exit 3
fi

log "DONE: FPGA reprogrammed and harness reachable."
