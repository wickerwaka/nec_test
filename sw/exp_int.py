#!/usr/bin/env python3
"""exp_int - Campaign 3 block 4 / Mission L: INT/NMI/POLL/HALT
characterization on the real chip (OPEN_QUESTIONS Q14).

Uses the harness pin-event scheduler (v30ctl set_event via the serve
protocol's RUN evt= option): on a CODE T1 at a trigger linear address,
after `delay` CPU clocks, drive INT/NMI/POLL for `hold` clocks. Per the
scheduler RTL the pin is asserted DURING capture cycle
   idx(trigger T1) + 2 + delay
(match registered at the T1-ending edge, one decrement edge minimum).

Results feed docs/facts/interrupt_model.md and the emit_suite interrupt
tranches.

Usage:
  exp_int.py anatomy|sweep|boundary|shadow|rep|ie0|nmi|poll|halt [--host H]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from v30asm import Assembler                          # noqa: E402
from v30run import run_test, RunError                 # noqa: E402

T_NAMES = {0: "TI", 1: "T1", 2: "T2", 3: "T3", 4: "TW", 5: "T4"}
Q_NAMES = {0: "-", 1: "F", 2: "E", 3: "S"}
BUS_STR = {0: "INTA", 1: "IOR", 2: "IOW", 3: "HALT",
           4: "CODE", 5: "MEMR", 6: "MEMW", 7: "PASV"}

VEC_INT = 0xFF          # harness cfg_int_vector default
VEC_NMI = 2
HANDLER = 0x0700        # far-jump-to-stub handler location
ANCHOR = 0x0500
SP0 = 0x04A0            # scratch stack: pushes land at 0x49A..0x49F


def hx(v, w=4):
    return "-" * w if v is None else f"{v:0{w}x}"


def handler_ram(stub_linear):
    """BR 0x0000:stub at HANDLER, as ram byte placements."""
    h = bytes([0xEA, stub_linear & 0xFF, stub_linear >> 8, 0x00, 0x00])
    return [(HANDLER + k, b) for k, b in enumerate(h)]


def txns(recs):
    """Bus transactions with T-state cycle indexes and raw pin bits."""
    out, cur = [], None
    for r in recs:
        t = r["t"]
        if t == 1:
            cur = {"t1": r["idx"], "kind": BUS_STR[r["bs_early"]],
                   "addr": r["ad_addr"], "data": None, "ube_n": r["ube_n"]}
        elif t in (3, 4) and cur:
            cur["data"] = r["ad_data"]
        elif t == 5 and cur:
            cur["t4"] = r["idx"]
            out.append(cur)
            cur = None
    return out


def trigger_t1(recs, addr):
    """Cycle index of the (first) CODE T1 at the trigger address."""
    for r in recs:
        if r["t"] == 1 and r["bs_early"] == 4 and r["ad_addr"] == addr:
            return r["idx"]
    return None


def pushed_words(tx, sp_lin):
    """PSW/PS/PC push data: the first three MEMW transactions in the
    scratch-stack window (descending addresses), in push order."""
    lo, hi = (sp_lin - 0x20) & 0xFFFFF, (sp_lin + 0x10) & 0xFFFFF
    ws = [t for t in tx if t["kind"] == "MEMW" and lo <= t["addr"] < hi]
    d = {}
    if len(ws) >= 3:
        d["psw"], d["ps"], d["pc"] = (ws[0]["data"], ws[1]["data"],
                                      ws[2]["data"])
        d["sp_top"] = ws[2]["addr"]
    return d


def print_window(recs, i0, i1, note=""):
    print(f"  timeline {note} (idx t bs qs addr data):")
    for r in recs:
        if i0 <= r["idx"] <= i1:
            print(f"    {r['idx']:>4} {T_NAMES[r['t']]:<2} "
                  f"{BUS_STR[r['bs_early']]:<4} {Q_NAMES[r['qs']]} "
                  f"{r['ad_addr']:05x} {r['ad_data']:04x}")


def run_evt(instr, regs, evt, host, tag, ram=None, ivt=None,
            stub_linear=None, pins=None):
    base = {"PS": 0, "PC": ANCHOR, "SS": 0, "SP": SP0, "PSW": 0x0202}
    if regs:
        base.update(regs)
    return run_test(regs=base, instr=instr, host=host, tag=tag, ram=ram,
                    ivt=ivt, evt=evt, pins=pins, stub_linear=stub_linear)


#----------------------------------------------------------------------------
# 1. anatomy: full INT sequence timeline on a NOP sled
#----------------------------------------------------------------------------
def cmd_anatomy(host):
    a = Assembler()
    instr = a.assemble("    NOP\n" * 24, org=ANCHOR)
    stub = ANCHOR + len(instr)
    ram = handler_ram(stub)
    ivt = {VEC_INT: None}  # placed via ram below (compose ivt wants seg,off)
    ivt = {VEC_INT: (0x0000, HANDLER)}
    res = run_evt(instr, None, (ANCHOR, 8, 0, 0), host, "anat",
                  ram=ram, ivt=ivt)
    tx = txns(res["recs"])
    t1 = trigger_t1(res["recs"], ANCHOR)
    assert_cyc = t1 + 2 + 8
    print(f"trigger T1 @ {t1}, INT asserted during cycle {assert_cyc}, "
          f"evt_fired={res['evt_fired']}")
    intas = [t for t in tx if t["kind"] == "INTA"]
    if not intas:
        print("NO INTA CYCLES")
        return 1
    print(f"INTA cycles: " + ", ".join(
        f"T1@{t['t1']} T4@{t['t4']} addr={t['addr']:05x} "
        f"data={t['data']:04x} ube_n={t['ube_n']}" for t in intas))
    print(f"  assert -> first INTA T1: {intas[0]['t1'] - assert_cyc} cycles"
          f" | INTA1 T1 -> INTA2 T1: {intas[1]['t1'] - intas[0]['t1']}")
    # everything from 4 before INTA1 to the first post-flush CODE fetch + 8
    pw = pushed_words(tx, SP0)
    print(f"pushes: PSW={pw.get('psw', -1):04x} PS={pw.get('ps', -1):04x} "
          f"PC={pw.get('pc', -1):04x}")
    ivtr = [t for t in tx if t["kind"] == "MEMR" and
            t["addr"] in (4 * VEC_INT, 4 * VEC_INT + 2)]
    print("IVT reads: " + ", ".join(
        f"T1@{t['t1']} {t['addr']:05x}={t['data']:04x}" for t in ivtr))
    # BUSLOCK check across the sequence (bit 50 raw)
    print_window(res["recs"], intas[0]["t1"] - 4,
                 intas[0]["t1"] + 70, "(INT sequence)")
    print(f"final regs: {res['regs']}")
    return 0


#----------------------------------------------------------------------------
# 2. sweep: recognition boundaries on a NOP sled
#----------------------------------------------------------------------------
def cmd_sweep(host):
    a = Assembler()
    instr = a.assemble("    NOP\n" * 24, org=ANCHOR)
    stub = ANCHOR + len(instr)
    ram = handler_ram(stub)
    ivt = {VEC_INT: (0x0000, HANDLER)}
    print("delay  fired  pushedPC  INTA1_T1  assert  latency")
    for d in range(0, 25):
        res = run_evt(instr, None, (ANCHOR, d, 0, 0), host, f"sw{d}",
                      ram=ram, ivt=ivt)
        tx = txns(res["recs"])
        t1 = trigger_t1(res["recs"], ANCHOR)
        ac = t1 + 2 + d
        intas = [t for t in tx if t["kind"] == "INTA"]
        pw = pushed_words(tx, SP0)
        pc = pw.get("pc")
        i1 = intas[0]["t1"] if intas else None
        lat = i1 - ac if i1 is not None else None
        print(f"{d:>5}  {int(res['evt_fired'])}      "
              f"{hx(pc):>6}    "
              f"{i1 if i1 is not None else '-':>5}   {ac:>5}   "
              f"{lat if lat is not None else '-'}")
    return 0


#----------------------------------------------------------------------------
# 3. boundary: mixed-length stream, fine delay sweep
#----------------------------------------------------------------------------
def cmd_boundary(host):
    a = Assembler()
    src = ("    MOV AW, 0x1111\n"     # 3 bytes, 4 cyc
           "    INC AW\n"             # 1 byte,  2 cyc
           "    MOV BW, 0x2222\n"     # 3 bytes, 4 cyc
           "    NOP\n" * 10)
    instr = a.assemble(src, org=ANCHOR)
    stub = ANCHOR + len(instr)
    ram = handler_ram(stub)
    ivt = {VEC_INT: (0x0000, HANDLER)}
    print("stream: B8@0500(3B) 40@0503 BB@0504(3B) NOPs@0507..")
    print("delay  fired  pushedPC  INTA1-assert")
    for d in range(0, 22):
        res = run_evt(instr, None, (ANCHOR, d, 0, 0), host, f"bd{d}",
                      ram=ram, ivt=ivt)
        tx = txns(res["recs"])
        t1 = trigger_t1(res["recs"], ANCHOR)
        ac = t1 + 2 + d
        intas = [t for t in tx if t["kind"] == "INTA"]
        pw = pushed_words(tx, SP0)
        pc = pw.get("pc")
        lat = intas[0]["t1"] - ac if intas else None
        print(f"{d:>5}  {int(res['evt_fired'])}      "
              f"{hx(pc):>6}    {lat}")
    return 0


#----------------------------------------------------------------------------
# 4. shadow: MOV SS / POP PSW / prefix recognition deferral
#----------------------------------------------------------------------------
def cmd_shadow(host):
    a = Assembler()
    cases = [
        ("MOV SS,AW shadow",
         "    MOV AW, 0x0000\n"       # 0500 (3B)
         "    MOV SS, AW\n"           # 0503 (2B)
         "    MOV SP, 0x04A0\n"       # 0505 (3B)  <- shadowed slot
         "    NOP\n" * 8, None),
        ("MOV DS0,AW shadow",
         "    MOV AW, 0x0000\n"
         "    MOV DS0, AW\n"
         "    MOV BW, 0x1234\n"
         "    NOP\n" * 8, None),
        ("POP PSW shadow",
         "    POP PSW\n"              # 0500 (1B), stack has IE=1 image
         "    INC AW\n"               # 0501
         "    NOP\n" * 8,
         [(SP0, 0x02), (SP0 + 1, 0xF2)]),   # PSW image F202 (IE=1)
        ("prefix chain 26 8B",
         "    NOP\n"
         "    NOP\n"
         "    NOP\n" * 8, "PFX"),     # patched below: 26 8B 07 at 0500
    ]
    for name, src, extra in cases:
        if extra == "PFX":
            instr = bytes([0x26, 0x8B, 0x07]) + b"\x90" * 8   # mov ax,es:[bx]
            ram = [(0x0800, 0x34), (0x0801, 0x12)]
            regs = {"BW": 0x0800, "DS1": 0}
        else:
            instr = a.assemble(src, org=ANCHOR)
            ram = list(extra) if isinstance(extra, list) else []
            regs = None
        stub = ANCHOR + len(instr)
        ram += handler_ram(stub)
        ivt = {VEC_INT: (0x0000, HANDLER)}
        print(f"\n== {name} (bytes @0500: {instr[:8].hex(' ')}) ==")
        print("delay  fired  pushedPC")
        for d in range(0, 16):
            res = run_evt(instr, regs, (ANCHOR, d, 0, 0), host, "sh",
                          ram=ram, ivt=ivt)
            tx = txns(res["recs"])
            pw = pushed_words(tx, SP0)
            pc = pw.get("pc")
            print(f"{d:>5}  {int(res['evt_fired'])}      "
                  f"{hx(pc)}")
    return 0


#----------------------------------------------------------------------------
# 5. rep: REP STM / prefixed REP MOVBK interruption and resume state
#----------------------------------------------------------------------------
def cmd_rep(host):
    ivt = {VEC_INT: (0x0000, HANDLER)}
    print("== REP STM (F3 AB, CW=6, word) interrupted ==")
    instr = bytes([0xF3, 0xAB]) + b"\x90" * 8
    stub = ANCHOR + len(instr)
    ram = handler_ram(stub)
    regs = {"AW": 0xBEEF, "CW": 6, "IY": 0x0800, "DS1": 0, "PSW": 0x0202}
    for d in (0, 4, 8, 12, 16, 20, 24, 28, 32, 40):
        res = run_evt(instr, regs, (ANCHOR, d, 0, 0), host, f"rp{d}",
                      ram=ram, ivt=ivt)
        tx = txns(res["recs"])
        pw = pushed_words(tx, SP0)
        wr = [t for t in tx if t["kind"] == "MEMW" and
              (t["addr"] & 0xFFF00) == 0x00800]
        r = res["regs"]
        print(f"  d={d:>3}: pushedPC={pw.get('pc', -1):04x} "
              f"writes_done={len(wr)} CW={r['CW']:04x} IY={r['IY']:04x} "
              f"PSW={r['PSW']:04x}")
    print("== REP MOVBK with DS1 override (26 F3 A4, CW=4) interrupted ==")
    instr = bytes([0x26, 0xF3, 0xA4]) + b"\x90" * 8
    stub = ANCHOR + len(instr)
    ram = handler_ram(stub)
    ram += [(0x0900 + k, 0x40 + k) for k in range(8)]
    regs = {"CW": 4, "IX": 0x0900, "IY": 0x0A00, "DS0": 0, "DS1": 0,
            "PSW": 0x0202}
    for d in (0, 6, 10, 14, 18, 22, 26, 30, 36, 44):
        res = run_evt(instr, regs, (ANCHOR, d, 0, 0), host, f"rm{d}",
                      ram=ram, ivt=ivt)
        tx = txns(res["recs"])
        pw = pushed_words(tx, SP0)
        r = res["regs"]
        print(f"  d={d:>3}: pushedPC={pw.get('pc', -1):04x} "
              f"CW={r['CW']:04x} IX={r['IX']:04x} IY={r['IY']:04x}")
    return 0


#----------------------------------------------------------------------------
# 6. ie0: IE=0 masks INT; NMI ignores IE
#----------------------------------------------------------------------------
def cmd_ie0(host):
    a = Assembler()
    instr = a.assemble("    NOP\n" * 16, org=ANCHOR)
    stub = ANCHOR + len(instr)
    ram = handler_ram(stub)
    ivt = {VEC_INT: (0x0000, HANDLER), VEC_NMI: (0x0000, HANDLER)}
    for name, psw, pin in (("INT, IE=1", 0x0202, 0), ("INT, IE=0", 0x0002, 0),
                           ("NMI, IE=1", 0x0202, 1), ("NMI, IE=0", 0x0002, 1)):
        res = run_evt(instr, {"PSW": psw}, (ANCHOR, 6, 4, pin), host, "ie",
                      ram=ram, ivt=ivt)
        tx = txns(res["recs"])
        intas = [t for t in tx if t["kind"] == "INTA"]
        ivtr = [t for t in tx if t["kind"] == "MEMR" and
                t["addr"] in (4 * VEC_NMI, 4 * VEC_NMI + 2,
                              4 * VEC_INT, 4 * VEC_INT + 2)]
        pw = pushed_words(tx, SP0)
        print(f"{name}: fired={int(res['evt_fired'])} INTA={len(intas)} "
              f"IVTreads={[f'{t['addr']:03x}' for t in ivtr]} "
              f"pushedPC={pw.get('pc')}")
    return 0


#----------------------------------------------------------------------------
# 7. nmi: anatomy + edge trigger + long-instruction deferral
#----------------------------------------------------------------------------
def cmd_nmi(host):
    a = Assembler()
    instr = a.assemble("    NOP\n" * 24, org=ANCHOR)
    stub = ANCHOR + len(instr)
    ram = handler_ram(stub)
    ivt = {VEC_NMI: (0x0000, HANDLER)}
    print("== NMI anatomy (hold=2, delay=8) ==")
    res = run_evt(instr, None, (ANCHOR, 8, 2, 1), host, "nm",
                  ram=ram, ivt=ivt)
    tx = txns(res["recs"])
    t1 = trigger_t1(res["recs"], ANCHOR)
    ac = t1 + 2 + 8
    intas = [t for t in tx if t["kind"] == "INTA"]
    ivtr = [t for t in tx if t["kind"] == "MEMR" and
            t["addr"] in (4 * VEC_NMI, 4 * VEC_NMI + 2)]
    pw = pushed_words(tx, SP0)
    print(f"asserted @ {ac} hold 2; INTA count={len(intas)}; IVT reads: " +
          ", ".join(f"T1@{t['t1']} {t['addr']:03x}={t['data']:04x}"
                    for t in ivtr))
    print(f"pushes: {pw}")
    if ivtr:
        print(f"assert -> first IVT read T1: {ivtr[0]['t1'] - ac}")
        print_window(res["recs"], ac - 2, ivtr[0]["t1"] + 40, "(NMI entry)")
    print("\n== NMI sweep on NOP sled (hold=2) ==")
    print("delay  fired  pushedPC  IVT1_T1-assert")
    for d in range(0, 13):
        res = run_evt(instr, None, (ANCHOR, d, 2, 1), host, f"nm{d}",
                      ram=ram, ivt=ivt)
        tx = txns(res["recs"])
        t1 = trigger_t1(res["recs"], ANCHOR)
        ac = t1 + 2 + d
        ivtr = [t for t in tx if t["kind"] == "MEMR" and
                t["addr"] == 4 * VEC_NMI]
        pw = pushed_words(tx, SP0)
        pc = pw.get("pc")
        lat = ivtr[0]["t1"] - ac if ivtr else None
        print(f"{d:>5}  {int(res['evt_fired'])}      "
              f"{hx(pc):>6}    {lat}")
    print("\n== NMI edge during DIVU (28cyc) ==")
    src = "    NOP\n" * 4 + "    DIVU CW\n" + "    NOP\n" * 8
    instr = a.assemble(src, org=ANCHOR)
    stub = ANCHOR + len(instr)
    ram = handler_ram(stub)
    for d in (10, 16, 22, 28):
        res = run_evt(instr, {"AW": 9, "DW": 0, "CW": 3},
                      (ANCHOR, d, 2, 1), host, f"nd{d}", ram=ram, ivt=ivt)
        tx = txns(res["recs"])
        pw = pushed_words(tx, SP0)
        print(f"  d={d}: pushedPC={pw.get('pc', -1):04x} "
              f"(DIV @0504, after-DIV=0506) AW={res['regs']['AW']:04x}")
    return 0


#----------------------------------------------------------------------------
# 8. poll: POLL instruction wait/release timing
#----------------------------------------------------------------------------
def cmd_poll(host):
    a = Assembler()
    print("== baseline: POLL with POLL_N already low (host pins=0) ==")
    src = "    NOP\n" * 16 + "    POLL\n" + "    NOP\n" * 8
    try:
        instr = a.assemble(src, org=ANCHOR)
    except Exception:
        # assembler may not know POLL: 0x9B
        instr = a.assemble("    NOP\n" * 16, org=ANCHOR) + b"\x9b" + \
            b"\x90" * 8
    res = run_evt(instr, None, None, host, "pl0")
    ev = [r for r in res["recs"] if r["qs"] == 1]
    # F-gap of instruction 16 (0-based F pops)
    fidx = [r["idx"] for r in ev]
    gaps = [b - a2 for a2, b in zip(fidx, fidx[1:])]
    print(f"  POLL F-gap (pin low): {gaps[16] if len(gaps) > 16 else None} "
          f"(NOP baseline {sorted(gaps[8:15])[3]})")

    print("== POLL waits while POLL_N high; released by event (pin=2) ==")
    print("delay  hold  fired  POLL F-gap  next-F idx")
    poll_addr = ANCHOR + 16
    for d in range(0, 21, 1):
        res = run_evt(instr, None, (poll_addr, d, 4, 2), host, f"pl{d}",
                      pins=4)
        ev = [r for r in res["recs"] if r["qs"] == 1]
        fidx = [r["idx"] for r in ev]
        gaps = [b - a2 for a2, b in zip(fidx, fidx[1:])]
        g = gaps[16] if len(gaps) > 16 else None
        print(f"{d:>5}  4     {int(res['evt_fired'])}      {g}")
    print("hold sensitivity at delay 8:")
    for h in (1, 2, 3, 6):
        res = run_evt(instr, None, (poll_addr, 8, h, 2), host, f"ph{h}",
                      pins=4)
        ev = [r for r in res["recs"] if r["qs"] == 1]
        fidx = [r["idx"] for r in ev]
        gaps = [b - a2 for a2, b in zip(fidx, fidx[1:])]
        g = gaps[16] if len(gaps) > 16 else None
        print(f"  hold={h}: POLL F-gap {g}")
    return 0


#----------------------------------------------------------------------------
# 9. halt: entry shape, wake by INT/NMI, IE=0 behavior
#----------------------------------------------------------------------------
def cmd_halt(host):
    a = Assembler()
    src = "    NOP\n" * 8 + "    HALT\n" + "    NOP\n" * 8
    try:
        instr = a.assemble(src, org=ANCHOR)
    except Exception:
        instr = a.assemble("    NOP\n" * 8, org=ANCHOR) + b"\xf4" + \
            b"\x90" * 8
    stub = ANCHOR + len(instr)
    ram = handler_ram(stub)
    ivt = {VEC_INT: (0x0000, HANDLER), VEC_NMI: (0x0000, HANDLER)}
    halt_addr = ANCHOR + 8

    print("== HALT entry + INT wake (IE=1), delay sweep ==")
    print("delay  fired  HALTcycT1  INTA1_T1  pushedPC")
    for d in (20, 30, 40, 60):
        res = run_evt(instr, {"PSW": 0x0202}, (halt_addr, d, 0, 0), host,
                      f"hw{d}", ram=ram, ivt=ivt)
        tx = txns(res["recs"])
        t1 = trigger_t1(res["recs"], halt_addr)
        ac = (t1 + 2 + d) if t1 is not None else None
        halts = [t for t in tx if t["kind"] == "HALT"]
        intas = [t for t in tx if t["kind"] == "INTA"]
        pw = pushed_words(tx, SP0)
        h1 = halts[0]["t1"] if halts else None
        i1 = intas[0]["t1"] if intas else None
        print(f"{d:>5}  {int(res['evt_fired'])}      {h1}      {i1}     "
              f"{pw.get('pc', -1):04x}  (assert@{ac}, "
              f"wake latency {i1 - ac if i1 and ac else '-'})")
    # detail window around the HALT cycle and the wake
    res = run_evt(instr, {"PSW": 0x0202}, (halt_addr, 40, 0, 0), host,
                  "hd", ram=ram, ivt=ivt)
    tx = txns(res["recs"])
    halts = [t for t in tx if t["kind"] == "HALT"]
    if halts:
        print_window(res["recs"], halts[0]["t1"] - 6, halts[0]["t1"] + 14,
                     "(HALT entry)")
    t1 = trigger_t1(res["recs"], halt_addr)
    ac = t1 + 2 + 40
    print_window(res["recs"], ac - 2, ac + 16, "(INT wake)")

    print("\n== HALT + NMI wake (IE=0, hold=2) ==")
    res = run_evt(instr, {"PSW": 0x0002}, (halt_addr, 40, 2, 1), host,
                  "hn", ram=ram, ivt=ivt)
    tx = txns(res["recs"])
    ivtr = [t for t in tx if t["kind"] == "MEMR" and
            t["addr"] == 4 * VEC_NMI]
    pw = pushed_words(tx, SP0)
    t1 = trigger_t1(res["recs"], halt_addr)
    ac = t1 + 2 + 40
    print(f"assert@{ac}; IVT2 read T1 {ivtr[0]['t1'] if ivtr else None}; "
          f"pushes {pw}")
    print_window(res["recs"], ac - 2, ac + 16, "(NMI wake)")

    print("\n== HALT + INT with IE=0: must stay halted ==")
    try:
        res = run_evt(instr, {"PSW": 0x0002}, (halt_addr, 40, 0, 0), host,
                      "hi", ram=ram, ivt=ivt)
        tx = txns(res["recs"])
        intas = [t for t in tx if t["kind"] == "INTA"]
        after = [t for t in tx if t["t1"] > 0 and t["kind"] == "CODE" and
                 t["addr"] >= stub]
        print(f"fired={int(res['evt_fired'])} INTA={len(intas)} "
              f"stub fetches={len(after)} (expect 0/0)")
    except RunError as e:
        print(f"run aborted as expected (no store marker): {e}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    cmds = {"anatomy": cmd_anatomy, "sweep": cmd_sweep,
            "boundary": cmd_boundary, "shadow": cmd_shadow,
            "rep": cmd_rep, "ie0": cmd_ie0, "nmi": cmd_nmi,
            "poll": cmd_poll, "halt": cmd_halt}
    ap.add_argument("cmd", choices=list(cmds) + ["all"])
    ap.add_argument("--host", default="root@mister-nec")
    args = ap.parse_args()
    if args.cmd == "all":
        for n, fn in cmds.items():
            print(f"\n======== {n} ========")
            fn(args.host)
        return 0
    return cmds[args.cmd](args.host)


if __name__ == "__main__":
    sys.exit(main())
