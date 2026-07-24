#!/usr/bin/env python3
"""exp_iret - RR2 E1: IRET twin of the POP-PSW boundary race.

microPD70116 microcode: IRET's flag transfer mu01EA `OPR->FLAGS F E` is
bit-identical in mu-op form to POP PSW's mu007A, but the surrounding context
differs (3-pop stack sequence, FLUSH-terminated far transfer, different
interval to dispatch). E1 asks whether the SAME race table governs IRET's
own-boundary flag commit -> a decode-specificity + context-transfer probe.

Rig (amended design):
 - pre-image live (pre-IE=1), settled >=3 instructions before IRET (loader
   POPF + NOP pad; an explicit POP PSW lead-in can be enabled if the loader
   image proves insufficient).
 - IRET (CF) with a crafted 6-byte frame at [SS:SP]: IP=TARGET, CS=0,
   PSW=frame(pop) image (IE=1). IRET pops IP/CS/PSW, FLUSH-jumps to CS:IP.
 - INT recognized at IRET's own boundary (flush-anchored; CODE-T1-anchored
   scheduler, delay swept to the boundary).
 - class = STEADY-STATE final live PSW's 7 race flags == frame/pop (A) or
   pre (B) (same discriminant as E2; iteration-1 cold-queue frame discarded).
 - INVARIANT check: the INT-entry PUSHED PSW must equal the frame image in
   BOTH classes (deviation = new physics = STOP).

Four live hypotheses: H-identical (same table) / H-shifted (context phase,
ordering preserved) / H-schedule (FLUSH/dispatch restructures the race) /
H-decode (9D-specific -> no race / unrelated).

SOCKET truth only. Subcommands: pilot (delay sweep >=5 cells, find boundary),
batch (100-cell stratified, after the boundary is fixed).
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from v30run import run_test, RunError                  # noqa: E402
import exp_race as R                                   # noqa: E402
from exp_int import txns, pushed_words                 # noqa: E402
import gen_race_law as GRL                             # noqa: E402

HOST = R.HOST
ANCHOR = 0x0500
TARGET = 0x0600          # IRET landing (CS=0); store stub sits here
HANDLER = 0x0700
SS0 = 0x0000
SP_FRAME = 0x04A0        # 6-byte IRET frame at 0x04A0..0x04A5
VEC_INT = 0xFF


def handler_ram(stub_linear):
    h = bytes([0xEA, stub_linear & 0xFF, stub_linear >> 8, 0x00, 0x00])
    return [(HANDLER + k, b) for k, b in enumerate(h)]


def measure_iret(pre7, pop7, delay, div=8, pop_ie=1, host=HOST, lead_pop=False,
                 use_core=False):
    """One IRET race cell. Returns measured class + pushed-frame invariant.
    use_core=False = socket (truth); True = internal v30_core (RTL DUT)."""
    pre_psw = R.race7_to_psw(pre7, ie=1)
    frame_psw = R.race7_to_psw(pop7, ie=pop_ie)
    # IRET at ANCHOR (+ pad). Optional POP-PSW lead-in >=3 instr earlier to
    # (re)establish the pre-image in the live flag row before the IRET window.
    body = bytes([0xCF]) + b"\x90" * 6
    instr = body
    frame = [(SP_FRAME, TARGET & 0xFF), (SP_FRAME + 1, TARGET >> 8),
             (SP_FRAME + 2, 0x00), (SP_FRAME + 3, 0x00),
             (SP_FRAME + 4, frame_psw & 0xFF), (SP_FRAME + 5, frame_psw >> 8)]
    ram = handler_ram(TARGET) + frame
    ivt = {VEC_INT: (0x0000, HANDLER)}
    regs = {"PS": 0, "PC": ANCHOR, "SS": SS0, "SP": SP_FRAME, "PSW": pre_psw}
    res = run_test(regs=regs, instr=instr, host=host, tag="iret",
                   ram=ram, ivt=ivt, evt=(ANCHOR, delay, 0, 0),
                   use_core=use_core, div=div, stub_linear=TARGET)
    # steady-state final live PSW (store epilogue)
    caps = R.psw_captures(res)
    r7s = [R.psw_to_race7(c) for c in caps]
    legit = [v for v in r7s if v in (pre7, pop7)]
    fr = legit[-1] if legit else (r7s[-1] if r7s else None)
    meas = ("A" if fr == pop7 else "B") if fr in (pre7, pop7) else "?"
    # INT-entry pushed PSW invariant (must equal the frame image both classes)
    tx = txns(res["recs"])
    pw = pushed_words(tx, SP_FRAME)
    pushed = pw.get("psw")
    pushed_r7 = None if pushed is None else R.psw_to_race7(pushed)
    frame_ok = pushed_r7 == pop7
    return {"pre7": pre7, "pop7": pop7, "delay": delay, "meas": meas,
            "fr": fr, "fired": res["evt_fired"], "pushed_r7": pushed_r7,
            "pushed_pc": pw.get("pc"), "frame_ok": frame_ok,
            "exp": R.expected_class(pre7, pop7), "ncaps": len(caps)}


def pilot_cells():
    """>=5 representative cells: both DIR modes, both classes, non-ghost,
    clear margin."""
    w = GRL.read_rom(GRL.DEFAULT_HEX)[1]
    exc = set(GRL.EXCEPTIONS)
    picks = []
    seen = set()
    allm = sorted(((abs(R.margin(a)), a) for a in range(16384)
                   if (a >> 7) != (a & 0x7F) and a not in exc
                   and not R.is_ghost_repair(a >> 7, a & 0x7F)), reverse=True)
    for _, a in allm:
        pre, pop = a >> 7, a & 0x7F
        q = (((pre >> 5) & 1) << 1) | ((pop >> 5) & 1)
        cls = R.expected_class(pre, pop)
        key = (q, cls)
        if key not in seen:
            seen.add(key)
            picks.append(a)
        if len(picks) >= 8:
            break
    return picks


def cmd_pilot(host, div):
    cells = pilot_cells()
    log = Path(__file__).resolve().parent / "exp_iret_pilot.log"
    open(log, "w").close()

    def out(m):
        print(m, flush=True)
        with open(log, "a") as f:
            f.write(m + "\n")
    out(f"E1 IRET pilot: delay sweep, div={div}, socket; cells="
        + str([f"{a:04x}({R.expected_class(a>>7,a&0x7f)},q{((a>>7>>5)&1)*2+((a&0x7f)>>5&1)})"
               for a in cells]))
    for delay in range(0, 22):
        row = []
        nmatch = 0
        nrace_B = 0
        frame_bad = 0
        for a in cells:
            pre, pop = a >> 7, a & 0x7F
            try:
                r = measure_iret(pre, pop, delay, div=div, host=host)
            except RunError as e:
                row.append(f"{a:04x}:ERR")
                out(f"  d={delay} {a:04x}: {str(e)[:80]}")
                continue
            ok = r["meas"] == r["exp"]
            nmatch += ok
            if r["meas"] == "B":
                nrace_B += 1
            if not r["frame_ok"]:
                frame_bad += 1
            row.append(f"{a:04x}:{r['meas']}/{r['exp']}"
                       f"{'' if ok else '!'}{'' if r['frame_ok'] else 'F!'}")
        tag = "ALL-MATCH" if nmatch == len(cells) else "         "
        out(f"d={delay:>2}: {tag} match={nmatch}/{len(cells)} B={nrace_B} "
            f"frameBad={frame_bad}  " + "  ".join(row))
    out("PILOT DONE")
    return 0


def cmd_batch(host, div, delay):
    """100-cell stratified IRET batch (after the boundary is fixed by pilot).
    Reuses the validated E2 108-cell stratified set (68 exc + 30 margin + 10
    bulk) so IRET class is directly comparable to POP PSW's hex. Ghost-repair
    cells scored A by the stored-A convention (their observable is E5).
    Compares IRET class to int9d_race.hex per the four hypotheses; the
    pushed-PSW==frame invariant is checked on every cell (any deviation is new
    physics -> STOP)."""
    if delay < 0:
        delay = 5
    cells = R.select_cells()
    log = Path(__file__).resolve().parent / "exp_iret_batch.log"
    jout = Path(__file__).resolve().parent / "exp_iret_batch.json"
    open(log, "w").close()

    def out(m):
        print(m, flush=True)
        with open(log, "a") as f:
            f.write(m + "\n")
    out(f"E1 IRET batch: {len(cells)} cells, div={div}, delay={delay}, socket; "
        f"IRET class vs int9d_race.hex (POP PSW table)")
    match = 0
    mism = []
    frame_bad = []
    weird = []
    data = {}
    t0 = time.time()
    for i, (addr, tag) in enumerate(cells):
        pre, pop = addr >> 7, addr & 0x7F
        try:
            r = measure_iret(pre, pop, delay, div=div, host=host)
        except RunError as e:
            mism.append((addr, tag, f"ERR {str(e)[:60]}"))
            continue
        if not r["frame_ok"]:
            frame_bad.append((addr, tag, f"pushed_r7={r['pushed_r7']} "
                              f"frame={pop} class={r['meas']}"))
        gate = "A" if R.is_ghost_repair(pre, pop) else r["meas"]
        if gate == r["exp"]:
            match += 1
        else:
            mism.append((addr, tag, f"iret={gate} pop-psw-hex={r['exp']} "
                         f"meas={r['meas']} fr={r['fr']}"))
        if not R.is_ghost_repair(pre, pop) and r["meas"] in ("?", None):
            weird.append((addr, tag))
        data[f"{addr:04x}"] = {"iret": gate, "meas": r["meas"], "hex": r["exp"],
                               "frame_ok": r["frame_ok"], "tag": tag,
                               "ghost": R.is_ghost_repair(pre, pop)}
        if (i + 1) % 20 == 0:
            out(f"  {i+1}/{len(cells)} ({(time.time()-t0)/(i+1):.2f}s/cell)")
    jout.write_text(json.dumps(data, indent=1))
    out("")
    if frame_bad:
        out(f"*** STOP: pushed-PSW != frame image on {len(frame_bad)} cell(s) "
            f"(new physics): {frame_bad[:8]} ***")
    out(f"IRET batch: {match}/{len(cells)} match POP-PSW hex; "
        f"{len(mism)} mismatch; {len(weird)} weird; frame-invariant "
        f"{'CLEAN' if not frame_bad else 'VIOLATED'}")
    for a, t, d in mism[:40]:
        out(f"  MISMATCH {a:04x} {t}: {d}")
    # hypothesis verdict
    if not frame_bad and match == len(cells):
        verdict = ("H-IDENTICAL: IRET's own-boundary flag commit obeys the SAME "
                   "race table as POP PSW, bit-for-bit (108/108), context-"
                   "independent -> strong fabric-mechanism evidence; decode-"
                   "specificity (H-decode) refuted; pushed PSW == frame image "
                   "both classes (no new physics).")
    elif not frame_bad and match >= 0.6 * len(cells):
        verdict = ("PARTIAL: ordering may be preserved with a phase/schedule "
                   "shift (H-shifted / H-schedule) -- inspect mismatch structure "
                   "vs class-ordering before concluding; NOT decode evidence "
                   "without the same-context non-9D control.")
    else:
        verdict = ("race weak/absent or restructured -- classify against "
                   "H-schedule/H-decode; a bare 'no race' needs the non-9D "
                   "same-context control before any decode conclusion.")
    out(f"VERDICT: {verdict}")
    return 1 if frame_bad else 0


def cmd_vsrtl(host, div, delay):
    """Run the 108 E1 cells on BOTH positions -- socket (truth) and internal
    v30_core (RTL DUT) -- and quantify the latent RTL gap (pop_pend armed only
    for opc==9D, v30_eu.sv:2090-2094, so the RTL cannot race at IRET's
    boundary). Preserves the socket captures as canonical goldens with full
    provenance in tests/v30/e1_iret_race/. Expect class-B cells to diverge
    (RTL commits the frame image -> A; silicon lets pre survive -> B)."""
    if delay < 0:
        delay = 5
    cells = R.select_cells()
    gdir = R.GRL.ROOT / "tests" / "v30" / "e1_iret_race"
    gdir.mkdir(parents=True, exist_ok=True)
    log = Path(__file__).resolve().parent / "exp_iret_vsrtl.log"
    open(log, "w").close()

    def out(m):
        print(m, flush=True)
        with open(log, "a") as f:
            f.write(m + "\n")
    import v30run as _v30
    out(f"E1 vs RTL: {len(cells)} cells, div={div}, delay={delay}; "
        f"socket (truth) vs internal v30_core (RTL DUT)")
    goldens = []
    div_socket = {"A": 0, "B": 0}
    diverge = []
    t0 = time.time()
    for i, (addr, tag) in enumerate(cells):
        pre, pop = addr >> 7, addr & 0x7F
        gh = R.is_ghost_repair(pre, pop)
        try:
            rs = measure_iret(pre, pop, delay, div=div, host=host,
                              use_core=False)
            rc = measure_iret(pre, pop, delay, div=div, host=host,
                              use_core=True)
        except RunError as e:
            out(f"  {addr:04x}: ERR {str(e)[:70]}")
            continue
        s_cls = "A" if gh else rs["meas"]
        c_cls = "A" if gh else rc["meas"]
        div_socket[s_cls if s_cls in ("A", "B") else "A"] += 1
        if s_cls != c_cls:
            diverge.append((addr, tag, s_cls, c_cls, gh))
        goldens.append({"addr": addr, "pre7": pre, "pop7": pop, "delay": delay,
                        "div": div, "socket_class": s_cls,
                        "socket_meas": rs["meas"], "final_race7": rs["fr"],
                        "pushed_frame_ok": rs["frame_ok"],
                        "core_class": c_cls, "ghost_repair": gh,
                        "hex_class": rs["exp"], "tag": tag})
        if (i + 1) % 20 == 0:
            out(f"  {i+1}/{len(cells)} ({(time.time()-t0)/(i+1):.2f}s/cell)")
    rig = getattr(_v30._runners.get(host), "rig_readback", "?")
    meta = {"experiment": "E1 IRET boundary race", "rig": "sw/exp_iret.py",
            "truth_source": "SOCKET (real chip, use_core=False)",
            "wait_rig": rig, "div": div, "delay": delay, "waits": 0,
            "discriminant": "steady-state final live PSW 7 race flags "
                            "== frame/pop (A) or pre (B); ghost-repair scored A",
            "date": "2026-07-23", "n_cells": len(goldens),
            "note": "canonical goldens for the IRET race-arm RTL fix "
                    "(pop_pend currently opc==9D only, v30_eu.sv:2090-2094). "
                    "socket_class validated == int9d_race.hex 108/108."}
    (gdir / "goldens.json").write_text(json.dumps(goldens, indent=1))
    (gdir / "metadata.json").write_text(json.dumps(meta, indent=1))
    # divergence breakdown by socket class
    by_cls = {"A": 0, "B": 0}
    for _, _, s, _, _ in diverge:
        by_cls[s] = by_cls.get(s, 0) + 1
    out("")
    out(f"socket class distribution: A={div_socket['A']} B={div_socket['B']}")
    out(f"RTL DIVERGENCES: {len(diverge)}/{len(cells)} "
        f"(socket-A diverging={by_cls['A']}, socket-B diverging={by_cls['B']})")
    ball = all(s == "B" for _, _, s, _, _ in diverge)
    out(f"pattern: {'ALL divergences are class-B cells (RTL commits frame->A; '
        'silicon pre-survives->B) -- exactly the pop_pend opc==9D gap' if ball and diverge else 'mixed -- inspect'}")
    for addr, tag, s, c, gh in diverge[:50]:
        out(f"  {addr:04x} {tag}: socket={s} core={c}{' (ghost)' if gh else ''}")
    out(f"goldens preserved: {gdir}/goldens.json ({len(goldens)} cells) + metadata.json")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["pilot", "batch", "vsrtl"])
    ap.add_argument("--host", default=HOST)
    ap.add_argument("--div", type=int, default=8)
    ap.add_argument("--delay", type=int, default=-1)
    args = ap.parse_args()
    if args.cmd == "pilot":
        return cmd_pilot(args.host, args.div)
    if args.cmd == "batch":
        return cmd_batch(args.host, args.div, args.delay)
    if args.cmd == "vsrtl":
        return cmd_vsrtl(args.host, args.div, args.delay)


if __name__ == "__main__":
    sys.exit(main())
