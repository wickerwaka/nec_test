#!/usr/bin/env python3
"""exp_ghost - RR2 E5: ghost second-observer piggyback (POP-PSW boundary race).

The ghost (interrupt_model.md §ghost): on specific pop patterns the INT entry
ALSO fails to clear the internal INT-pending latch, so a LATER IE=1 re-dispatches
a spurious second INTA with the pin already released. E5 measures that observable
per cell and asks whether it tracks the class geography cell-by-cell (the
one-quantity-two-thresholds question), now the key discriminator after E2
(frequency-invariant) and E1 (context-identical).

Positive-control handler protocol (mandatory, per the amended design):
  handler @ HANDLER = EI ; NOP (retiring instr -> the EI one-boundary shadow) ;
  NOP observation sled (capture the spurious 2nd INTA) ; BR far -> store stub.
  The INT pin is asserted with a FINITE hold so it is DEASSERTED before the
  handler's EI -> any INTA after EI is the ghost, not the held pin. No HALT
  anywhere; no early reset/mask/state change.

Ghost observable = extra INTA sequence(s) beyond the entry pair, AFTER the pin
has dropped. Every batch carries one known-ghost (positive) + one known-non-
ghost (negative) control; STOP on either control failing. Capture morphology
is recorded on BOTH positions (socket + core) -> also answers P-I2 (loop-vs-
park) for the IRET design.

SOCKET truth for the observable; core recorded for the rig-morphology gap.
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from v30run import run_test, RunError                  # noqa: E402
import exp_race as R                                   # noqa: E402
from exp_int import txns                               # noqa: E402

HOST = R.HOST
ANCHOR = 0x0500
HANDLER = 0x0700
SS0 = 0x0000
SP_POP = 0x04A0
VEC_INT = 0xFF
N_OBS = 20               # observation-sled NOPs after EI


def ghost_handler_ram(stub_linear):
    """EI ; NOP (EI-shadow retiring) ; N_OBS NOP observation sled ; BR far
    -> store stub. Lets a set pending-latch re-dispatch a 2nd INTA (pin low)."""
    seq = bytes([0xFB, 0x90]) + b"\x90" * N_OBS \
        + bytes([0xEA, stub_linear & 0xFF, stub_linear >> 8, 0x00, 0x00])
    return [(HANDLER + k, b) for k, b in enumerate(seq)]


def measure_ghost(pre7, pop7, delay=5, hold=3, div=8, pop_ie=1, host=HOST,
                  use_core=False):
    """Run the POP-PSW race cell under the EI-observer handler. Returns the
    class + ghost observable (extra INTA after pin drop) + morphology."""
    pre_psw = R.race7_to_psw(pre7, ie=1)
    pop_psw = R.race7_to_psw(pop7, ie=pop_ie)
    instr = bytes([0x9D]) + b"\x90" * 20
    stub = ANCHOR + len(instr)
    ram = ghost_handler_ram(stub)
    ram += [(SP_POP, pop_psw & 0xFF), (SP_POP + 1, pop_psw >> 8)]
    ivt = {VEC_INT: (0x0000, HANDLER)}
    regs = {"PS": 0, "PC": ANCHOR, "SS": SS0, "SP": SP_POP, "PSW": pre_psw}
    res = run_test(regs=regs, instr=instr, host=host, tag="ghost",
                   ram=ram, ivt=ivt, evt=(ANCHOR, delay, hold, 0),
                   use_core=use_core, div=div, stub_linear=stub)
    tx = txns(res["recs"])
    intas = [t for t in tx if t["kind"] == "INTA"]
    # INTA come in pairs (INTA1/INTA2). One entry = 2. A ghost redispatch adds
    # a later pair. First test-loop iteration only: pairs up to the first store.
    inta_t1 = [t["t1"] for t in intas]
    caps = R.psw_captures(res)
    r7s = [R.psw_to_race7(c) for c in caps]
    legit = [v for v in r7s if v in (pre7, pop7)]
    fr = legit[-1] if legit else (r7s[-1] if r7s else None)
    cls = ("A" if fr == pop7 else "B") if fr in (pre7, pop7) else "?"
    # ghost = more than the single entry pair before the first store capture
    n_pairs = len(intas) // 2
    return {"pre7": pre7, "pop7": pop7, "class": cls, "n_inta": len(intas),
            "n_pairs": n_pairs, "ghost": n_pairs >= 2, "inta_t1": inta_t1,
            "ncaps": len(caps), "caps_r7": r7s, "fired": res["evt_fired"]}


def known_controls():
    """positive = a ghost-repair cell (pop {V,DIR,S,Z}); negative = a deep,
    non-ghost class-A cell (pop far from any ghost pattern)."""
    pos = None
    neg = None
    exc = set(R.GRL.EXCEPTIONS)
    for a in exc:
        pre, pop = a >> 7, a & 0x7F
        if R.is_ghost_repair(pre, pop):
            pos = a
            break
    for a in range(16384):
        pre, pop = a >> 7, a & 0x7F
        if pre != pop and not R.is_ghost_repair(pre, pop) \
                and R.margin(a) < -40 and R.expected_class(pre, pop) == "A":
            neg = a
            break
    return pos, neg


def cmd_controls(host, div):
    """Validate the ghost-observer protocol: positive control (known ghost)
    must show the 2nd INTA; negative control (non-ghost) must not. Sweep hold
    to find the window where the pin is deasserted before EI yet recognized."""
    pos, neg = known_controls()
    log = Path(__file__).resolve().parent / "exp_ghost_controls.log"
    open(log, "w").close()

    def out(m):
        print(m, flush=True)
        with open(log, "a") as f:
            f.write(m + "\n")
    out(f"E5 control validation: pos(ghost)={pos:04x} "
        f"pre={pos>>7:02x} pop={pos&0x7f:02x}; neg(non-ghost)={neg:04x} "
        f"pre={neg>>7:02x} pop={neg&0x7f:02x}; div={div}")
    out("hold sweep (find pin-deasserted-before-EI window):")
    for hold in (2, 3, 4, 6, 8):
        rp = measure_ghost(pos >> 7, pos & 0x7F, hold=hold, div=div, host=host)
        rn = measure_ghost(neg >> 7, neg & 0x7F, hold=hold, div=div, host=host)
        ok = rp["ghost"] and not rn["ghost"]
        out(f"  hold={hold}: POS ghost={rp['ghost']} nInta={rp['n_inta']} "
            f"cls={rp['class']} intaT1={rp['inta_t1'][:6]} | "
            f"NEG ghost={rn['ghost']} nInta={rn['n_inta']} cls={rn['class']} "
            f"-> {'CONTROLS OK' if ok else '...'}")
    out("CONTROLS DONE")
    return 0


def _ghost_pop(pop7):
    """Ghost-prone pop region (design: 162/224 ghost cells in pop{V=1,DIR=1,
    AC=0}); a loose proxy for the documented ghost pop patterns."""
    return (pop7 >> 6 & 1) == 1 and (pop7 >> 5 & 1) == 1 and (pop7 >> 2 & 1) == 0


def cmd_correlate(host, div):
    """E5 PATH 1: loop-morphology / ghost correlation, offline from the
    committed E2 sweep (exp_race_sweep.json 'ghost' = capture oscillation =
    the [pop,00,pre] redispatch signature) + the hex. Emits the per-cell table
    across the E2 divs and resolves the circularity confound in the write-up."""
    w = R.GRL.read_rom(R.GRL.DEFAULT_HEX)[1]

    def hexcls(a):
        return "A" if R.GRL.rom_bit(w, a) == 0 else "B"
    sw = json.load(open(Path(__file__).resolve().parent / "exp_race_sweep.json"))
    divs = ["B0_div8", "div4", "div6", "div10", "div12", "div16"]
    keys = list(sw["cells"]["B0_div8"].keys())
    table = []
    for k in keys:
        a = int(k, 16)
        pre, pop = a >> 7, a & 0x7F
        loops = [sw["cells"][d][k]["ghost"] for d in divs
                 if k in sw["cells"].get(d, {})]
        table.append({"addr": a, "pre": pre, "pop": pop, "class": hexcls(a),
                      "ghost_pop": _ghost_pop(pop),
                      "ghost_repair": R.is_ghost_repair(pre, pop),
                      "loop_per_div": loops, "loop": any(loops),
                      "loop_div_stable": len(set(loops)) == 1})
    out_p = Path(__file__).resolve().parent / "exp_ghost_correlation.json"
    out_p.write_text(json.dumps(table, indent=1))
    A = [t for t in table if t["class"] == "A"]
    B = [t for t in table if t["class"] == "B"]
    unstable = [t["addr"] for t in table if not t["loop_div_stable"]]
    A_loop_gp = [t for t in A if t["loop"] and t["ghost_pop"]]
    A_loop_ngp = [t for t in A if t["loop"] and not t["ghost_pop"]]
    A_park = [t for t in A if not t["loop"]]
    print("E5 correlation (from committed exp_race_sweep.json):")
    print(f"  class-A: {len(A)}; loop&ghost-pop={len(A_loop_gp)} "
          f"loop&non-ghost-pop={len(A_loop_ngp)} park(single)={len(A_park)}")
    print(f"  class-B: {len(B)}; loop={sum(1 for t in B if t['loop'])} "
          f"(measurement-coupled: discriminant reads B from the loop)")
    print(f"  loop div-UNSTABLE across {{4,6,8,10,12,16}}: {len(unstable)}/"
          f"{len(table)} (0 => redispatch is frequency-invariant, like class)")
    print(f"  A-loopers all ghost-repair? "
          f"{all(t['ghost_repair'] for t in A_loop_gp)} "
          f"(n={len(A_loop_gp)}); their underlying flag-fight is B")
    print(f"  wrote {out_p.name} ({len(table)} cells x {len(divs)} divs)")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["controls", "batch", "correlate"])
    ap.add_argument("--host", default=HOST)
    ap.add_argument("--div", type=int, default=8)
    args = ap.parse_args()
    if args.cmd == "controls":
        return cmd_controls(args.host, args.div)
    if args.cmd == "correlate":
        return cmd_correlate(args.host, args.div)
    print("batch not yet enabled (validate controls first)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
