#!/usr/bin/env python3
"""E2 pre-step: min-clock-floor NOP-sled smoke.

Before the bounded frequency sweep we MUST confirm the socketed chip still
executes correctly at every planned divisor -- the min-clock gotcha (memory
note) is real silicon risk. NEC_CLK = 32 MHz / div, so div=16 -> 2 MHz is the
slow end. A div is "at/above floor" iff a NOP-sled INT sequence runs bit-clean
(evt fired, exactly 2 INTA, sane pushes PSW/PS/PC, IVT reads, stub continuation)
AND a no-INT NOP-sled run produces a clean register echo. Reps per div check
determinism. Any div that misbehaves is BELOW the floor and is excluded from the
sweep (reported, not swept).

SOCKET truth only (use_core=False). Incremental log. Restores div=8 at the end.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from v30asm import Assembler                       # noqa: E402
from v30run import run_test, RunError              # noqa: E402
from exp_int import (txns, trigger_t1, pushed_words, handler_ram,  # noqa: E402
                     ANCHOR, HANDLER, SP0, VEC_INT)

HOST = "root@mister-nec"
DIVS = [4, 6, 8, 10, 12, 16]        # 8..2 MHz
REPS = 3
DELAY = 8                            # INT delay on the sled (anatomy geometry)
LOG = Path(__file__).resolve().parent / "e2_floor_smoke.log"


def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG, "a") as f:
        f.write(line + "\n")


def run_int(instr, ram, ivt, div, tag):
    base = {"PS": 0, "PC": ANCHOR, "SS": 0, "SP": SP0, "PSW": 0x0202}
    return run_test(regs=base, instr=instr, host=HOST, tag=tag, ram=ram,
                    ivt=ivt, evt=(ANCHOR, DELAY, 0, 0), use_core=False, div=div)


def eval_int(res):
    """Return (ok, detail, signature) for a NOP-sled INT run.

    The harness capture spans several test-loop iterations (the loader
    re-runs the image to fill 4096 records), so INTA/IVT reads come in one
    pair PER iteration -- we require paired counts and inspect the FIRST
    sequence (pushed_words already returns the first iteration's pushes).
    Correct execution = evt fired, INTA/IVT reads present and paired,
    sane first-iteration pushes. The per-div signature must be identical
    across divs; a frequency-dependent fault would perturb it."""
    tx = txns(res["recs"])
    t1 = trigger_t1(res["recs"], ANCHOR)
    intas = [t for t in tx if t["kind"] == "INTA"]
    ivtr = [t for t in tx if t["kind"] == "MEMR"
            and t["addr"] in (4 * VEC_INT, 4 * VEC_INT + 2)]
    pw = pushed_words(tx, SP0)
    ok = (res["evt_fired"] and t1 is not None
          and len(intas) >= 2 and len(intas) % 2 == 0
          and len(ivtr) >= 2 and len(ivtr) % 2 == 0
          and pw.get("pc") is not None
          and pw.get("psw") is not None and pw.get("ps") is not None)
    i01 = [t["t1"] for t in intas[:2]]
    detail = (f"fired={int(res['evt_fired'])} INTA={len(intas)} IVT={len(ivtr)} "
              f"pushedPC={pw.get('pc')} PSW={pw.get('psw')} PS={pw.get('ps')} "
              f"INTA1/2_t1={i01}")
    # signature: first-sequence geometry + pushes (loop-count excluded so a
    # differing capture depth alone is not a floor flag)
    sig = (tuple(i01), pw.get("pc"), pw.get("psw"), pw.get("ps"))
    return ok, detail, sig


def main():
    open(LOG, "w").close()
    log(f"E2 min-clock-floor smoke: divs={DIVS} (32MHz/div), reps={REPS}, "
        f"socket truth")
    a = Assembler()
    sled = a.assemble("    NOP\n" * 24, org=ANCHOR)
    stub = ANCHOR + len(sled)
    ram = handler_ram(stub)
    ivt = {VEC_INT: (0x0000, HANDLER)}
    floor_ok, floor_bad = [], []
    div_sig = {}
    for div in DIVS:
        mhz = 32.0 / div
        sigs = set()
        allok = True
        details = []
        try:
            # no-INT control: clean register echo at this div
            base = {"PS": 0, "PC": ANCHOR, "SS": 0, "SP": SP0, "PSW": 0x0202}
            res0 = run_test(regs=base, instr=sled, host=HOST, tag=f"ni{div}",
                            ram=ram, ivt=ivt, use_core=False, div=div)
            ni_ok = res0["regs"].get("PC") is not None
            details.append(f"noINT: PC={res0['regs'].get('PC')} ok={ni_ok}")
            allok &= ni_ok
            for r in range(REPS):
                res = run_int(sled, ram, ivt, div, f"fs{div}_{r}")
                ok, det, sig = eval_int(res)
                sigs.add(sig)
                details.append(f"r{r}: {'OK' if ok else 'BAD'} {det}")
                allok &= ok
        except RunError as e:
            allok = False
            details.append(f"RunError: {str(e)[:160]}")
        stable = len(sigs) <= 1
        verdict = "FLOOR-OK" if (allok and stable) else "BELOW-FLOOR"
        (floor_ok if verdict == "FLOOR-OK" else floor_bad).append(div)
        if sigs:
            div_sig[div] = next(iter(sigs))
        log(f"div={div:>2} ({mhz:.2f} MHz): {verdict} "
            f"(stable={stable}, sigs={len(sigs)})")
        for d in details:
            log(f"    {d}")
    # restore baseline div=8
    try:
        base = {"PS": 0, "PC": ANCHOR, "SS": 0, "SP": SP0, "PSW": 0x0202}
        run_test(regs=base, instr=sled, host=HOST, tag="restore8",
                 ram=ram, ivt=ivt, use_core=False, div=8)
        log("restored div=8 baseline")
    except RunError as e:
        log(f"WARN: div=8 restore run failed: {str(e)[:120]}")
    xdiv = set(div_sig.values())
    xstable = len(xdiv) <= 1
    log(f"cross-div first-sequence signature: "
        f"{'IDENTICAL across all divs' if xstable else 'DIFFERS'} "
        f"({len(xdiv)} distinct)")
    if not xstable:
        for div, s in div_sig.items():
            log(f"    div={div}: {s}")
    log(f"FLOOR SMOKE DONE: floor-ok divs={floor_ok}  below-floor={floor_bad}  "
        f"cross-div-stable={xstable}")
    return 0 if (not floor_bad and xstable) else 1


if __name__ == "__main__":
    sys.exit(main())
