#!/usr/bin/env python3
"""M10 STEP ZERO -- `docs/notes/fz2_m10_diagnosis_2026-08-10.md` §6.0.

M10's register-file solve came back EMPTY on 6 of the 8 residual `E1` seats:
no segment x (register, bitwise pair, `+1` split half) in a 3,208-expression
space reproduces the CHIP's address at any freeze in `[-12, +1]`, while the
ARCHITECTURALLY-CORRECT ModR/M effective address reproduces the CORE's exactly.
§6.0 registered a free, offline step that decides between

  (i) UPSTREAM VALUE DIVERGENCE -- the chip's registers at the fork already
      differ from the ucore's, and the fork is the first moment one of them is
      USED; and
  (ii) A RAIL THE UCORE DOES NOT MODEL -- not in the save-state map, so no
      readout can find it.

The step: solve `chip = seg:(base + d)` for a single named base and ask whether
`d` is what an EARLIER instruction's result would explain.

This tool does exactly that and nothing else.  It adds no free parameter beyond
the single `d` §6.0 authorises, it decodes the forking instruction's ModR/M with
the part's own addressing table rather than a fitted one, and it reports its own
background rate.

SIMPLICITY: this is 80's era hardware -- nothing on the die is wasted.  Complex
or confusing observed behavior is likely simple systems interacting in ways not
yet understood.  A large fitted table, a many-cased rule, or a per-opcode
special case is a signal of misunderstanding, not a deliverable.

  python3 sw/fz2_m10_step0.py step0            # the 8 residual seats
  python3 sw/fz2_m10_step0.py control          # background rate, all 116
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sw"))

import fz2_failview as fv                                        # noqa: E402

LEDGER = ROOT / "sw/testdata/fz2/fz2_failure_ledger_f16_2026-08-10.json"
RESIDUAL = ROOT / "sw/testdata/fz2/fz2_m10_solve_residual.json"
OUT = ROOT / "sw/testdata/fz2/fz2_m10_step0.json"

# save-state term name -> the 8086/V30 ModR/M register index it is.
# `sw/fz2_m10.py` reads these out of `v30u_ss_pkg.sv` at run time; the residual
# JSON carries them already resolved, under the part's own NEC names.
NEC = ["AW", "CW", "DW", "BW", "SP", "BP", "IX", "IY"]
INTEL = ["ax", "cx", "dx", "bx", "sp", "bp", "si", "di"]

# the 16-bit ModR/M addressing table, verbatim: rm -> the registers summed.
RM16 = {0: ("BW", "IX"), 1: ("BW", "IY"), 2: ("BP", "IX"), 3: ("BP", "IY"),
        4: ("IX",), 5: ("IY",), 6: ("BP",), 7: ("BW",)}
SEG_PREFIX = {0x26: "ES", 0x2E: "CS", 0x36: "SS", 0x3E: "DS"}

# opcodes that take a ModR/M byte immediately after the opcode byte.  This is
# the 8086 map; only the entries the residual seats actually dispatch matter,
# but the whole map is here so the control below is not opcode-picked.
MODRM_1B = set(range(0x00, 0x04)) | set(range(0x08, 0x0C)) | \
    set(range(0x10, 0x14)) | set(range(0x18, 0x1C)) | \
    set(range(0x20, 0x24)) | set(range(0x28, 0x2C)) | \
    set(range(0x30, 0x34)) | set(range(0x38, 0x3C)) | \
    {0x62, 0x63, 0x69, 0x6B} | set(range(0x80, 0x8F)) | \
    {0xC0, 0xC1, 0xC4, 0xC5, 0xC6, 0xC7} | set(range(0xD0, 0xD4)) | \
    set(range(0xD8, 0xE0)) | {0xF6, 0xF7, 0xFE, 0xFF}

# how many bytes of displacement `mod` carries.
DISP = {0: 0, 1: 1, 2: 2, 3: 0}


def modrm_disp_len(mod, rm):
    return 2 if (mod == 0 and rm == 6) else DISP[mod]


def decode_ea(bs):
    """(seg_default, regs, disp, mod, rm) for a group's bytes, or None.

    `bs` is ONE retired group -- one instruction, prefixes excluded, because a
    prefix retires with its own `QS = F` pop on this part.  The segment
    OVERRIDE therefore arrives as its own group and is handled by the caller.
    """
    i = 0
    while i < len(bs) and bs[i] in (0xF0, 0xF2, 0xF3, 0x0F) and i < 2:
        # LOCK/REP retire separately too; `0F` is the two-byte page and this
        # tool does not decode it -- it reports NONE and is counted as such.
        if bs[i] == 0x0F:
            return None
        i += 1
    if i >= len(bs):
        return None
    op = bs[i]
    if op not in MODRM_1B or i + 1 >= len(bs):
        return None
    mrm = bs[i + 1]
    mod, rm = mrm >> 6, mrm & 7
    if mod == 3:
        return None                       # register form: no memory EA at all
    regs = () if (mod == 0 and rm == 6) else RM16[rm]
    n = modrm_disp_len(mod, rm)
    d = 0
    if n == 1:
        if i + 2 >= len(bs):
            return None
        d = bs[i + 2]
        d = d - 256 if d & 0x80 else d
    elif n == 2:
        if i + 3 >= len(bs):
            return None
        d = bs[i + 2] | (bs[i + 3] << 8)
    seg = "SS" if ("BP" in regs) else "DS"
    return {"seg": seg, "regs": list(regs), "disp": d & 0xFFFF,
            "mod": mod, "rm": rm, "op": op, "mrm": mrm}


def lea_mod3(bs):
    """(dest_nec_name, rm_nec_name) if this group is `8D /r` with `mod == 3`.

    The predicate is the ISA's, not a fit: opcode `0x8D`, ModR/M top two bits
    set.  `tests/v30/mod3_illegal` is this form's socket characterisation and
    `sw/ucsim_check.py::stale_ea_confined` is the gate that ACCEPTS the model's
    divergence on exactly this destination register.
    """
    i = 0
    while i < len(bs) and bs[i] in (0xF0, 0xF2, 0xF3) + tuple(SEG_PREFIX):
        i += 1
    if i + 1 >= len(bs) or bs[i] != 0x8D:
        return None
    mrm = bs[i + 1]
    if (mrm & 0xC0) != 0xC0:
        return None
    return NEC[(mrm >> 3) & 7], NEC[mrm & 7]


def groups_and_fork(entry):
    """(groups, fork_row, chip_rows) with the capture sha256-gated."""
    cap = fv.read_capture(fv.cap_path(entry, ""), entry["capture_sha256"])
    real = cap["real"]
    pops, _bmap = fv.shadow(real)
    return fv.groups_of(pops), entry["first_bad_row"], real


def group_at(groups, row):
    """The group in dispatch at `row`: the last `QS = F` pop at or before it."""
    cur = None
    for g in groups:
        if g["f_row"] <= row:
            cur = g
        else:
            break
    return cur


def seg_override_before(groups, gi):
    """A segment-override prefix retired immediately before group `gi`."""
    if gi <= 0:
        return None
    b = groups[gi - 1]["bytes"]
    if len(b) == 1 and b[0] in SEG_PREFIX:
        return SEG_PREFIX[b[0]]
    return None


def phys(seg_val, off):
    return ((seg_val << 4) + (off & 0xFFFF)) & 0xFFFFF


def solve_seat(seed, resid, entry):
    """Step zero for one seat.  Returns a dict; asserts nothing."""
    groups, fork, _rows = groups_and_fork(entry)
    gi = None
    for j, g in enumerate(groups):
        if g["f_row"] <= fork:
            gi = j
        else:
            break
    out = {"seed": seed, "fork_row": fork,
           "chip_addr": resid["chip_addr"], "core_addr": resid["core_addr"]}
    if gi is None:
        out["status"] = "NO-DISPATCH"
        return out
    fg = groups[gi]
    out["dispatch_bytes"] = " ".join(f"{b:02x}" for b in fg["bytes"])
    ea = decode_ea(fg["bytes"])
    ovr = seg_override_before(groups, gi)

    # the ucore's own registers at the fork, freeze 0, from the banked solve.
    f0 = [f for f in resid["freezes"] if f["delta"] == 0][0]
    terms, segs = f0["terms"], f0["segs"]

    # every `8D` mod3 retired before the fork, nearest last.
    leas = []
    for j in range(gi + 1):
        m = lea_mod3(groups[j]["bytes"])
        if m:
            leas.append({"gi": j, "dist": gi - j, "f_row": groups[j]["f_row"],
                         "bytes": " ".join(f"{b:02x}"
                                           for b in groups[j]["bytes"]),
                         "dest": m[0], "rm": m[1]})
    out["lea_mod3"] = leas
    out["n_lea_mod3"] = len(leas)

    if ea is None:
        out["status"] = "EA-NOT-DECODED"
        return out
    seg = ovr or ea["seg"]
    out["ea"] = {"seg": seg, "seg_override": ovr, "regs": ea["regs"],
                 "disp": ea["disp"], "mod": ea["mod"], "rm": ea["rm"]}

    sv = segs.get(seg)
    off_core = sum(terms[r] for r in ea["regs"]) + ea["disp"]
    pred = phys(sv, off_core)
    out["core_ea_reproduced"] = (pred == resid["core_addr"])
    out["core_ea_offset"] = off_core & 0xFFFF

    # THE STEP-ZERO SOLVE: one base, one displacement `d`, nothing else.
    need = (resid["chip_addr"] - (sv << 4)) & 0xFFFFF
    out["chip_offset_needed"] = need if need <= 0xFFFF else None
    d = None
    if need <= 0xFFFF:
        d = (need - off_core) & 0xFFFF
    out["delta"] = d
    out["delta_signed"] = None if d is None else (d - 0x10000 if d & 0x8000
                                                  else d)
    # which of the EA's OWN registers, shifted by `d`, reproduces the chip.
    cand = []
    for r in ea["regs"]:
        cand.append(r)
    out["delta_carriers"] = cand
    out["status"] = "SOLVED" if out["core_ea_reproduced"] and d is not None \
        else "PARTIAL"
    return out


def taint_note(seat):
    """Whether an `8D` mod3 destination is one of the forking EA's registers.

    Reported, not fitted: the two are either the same register or they are not,
    and where they are not this says so and names both.
    """
    ea = seat.get("ea")
    if not ea or not seat.get("lea_mod3"):
        return {"direct": False, "dest": None, "carriers": ea["regs"]
                if ea else None}
    for m in seat["lea_mod3"][::-1]:
        if m["dest"] in ea["regs"]:
            return {"direct": True, "dest": m["dest"], "dist": m["dist"],
                    "carriers": ea["regs"]}
    m = seat["lea_mod3"][-1]
    return {"direct": False, "dest": m["dest"], "dist": m["dist"],
            "carriers": ea["regs"]}


def cmd_step0(a):
    led = json.loads(LEDGER.read_text())
    by = {f["seed"]: f for f in led["failures"]}
    res = json.loads(RESIDUAL.read_text())
    rows = []
    for r in res["rows"]:
        s = solve_seat(r["seed"], r, by[r["seed"]])
        s["taint"] = taint_note(s)
        rows.append(s)
    json.dump({"tool": "fz2_m10_step0", "ledger": str(LEDGER),
               "residual": str(RESIDUAL), "n": len(rows), "rows": rows},
              open(a.out, "w"), indent=1)
    print(f"STEP ZERO on {len(rows)} residual seats "
          f"-> {Path(a.out).name}\n")
    hdr = (f"{'seat':<14}{'dispatch':<14}{'EA':<22}{'core EA ok':<11}"
           f"{'delta':>8}  8D-mod3 (dest, dist)")
    print(hdr)
    print("-" * len(hdr))
    for s in rows:
        ea = s.get("ea")
        eatxt = "-" if not ea else \
            f"{ea['seg']}:{'+'.join(ea['regs']) or '0'}+{ea['disp']:#06x}"
        leatxt = "none"
        if s["lea_mod3"]:
            m = s["lea_mod3"][-1]
            leatxt = f"{m['bytes']} -> {m['dest']} (-{m['dist']})"
        d = s.get("delta_signed")
        print(f"{s['seed']:<14}{s.get('dispatch_bytes','')[:13]:<14}"
              f"{eatxt:<22}{str(s.get('core_ea_reproduced')):<11}"
              f"{'' if d is None else d:>8}  {leatxt}")
    n_lea = sum(1 for s in rows if s["n_lea_mod3"])
    n_dir = sum(1 for s in rows if s["taint"]["direct"])
    print(f"\n  seats with an `8D` mod3 retired before the fork: "
          f"{n_lea}/{len(rows)}")
    print(f"  ... whose DESTINATION is one of the forking EA's own registers: "
          f"{n_dir}/{len(rows)}")


def cmd_control(a):
    """The background rate, two ways, on the same reconstruction and rule."""
    led = json.loads(LEDGER.read_text())
    res = json.loads(RESIDUAL.read_text())
    resid = {r["seed"] for r in res["rows"]}
    rng = random.Random(a.seed)
    A = {"n": 0, "lea": 0, "direct": 0}      # random rows, the SAME seeds
    B = {"n": 0, "lea": 0, "direct": 0}      # the other ledger failures' forks
    per = []
    for f in led["failures"]:
        try:
            groups, fork, rows = groups_and_fork(f)
        except Exception as e:                                   # noqa: BLE001
            per.append({"seed": f["seed"], "error": str(e)[:80]})
            continue
        win = f.get("compare_window") or 4000
        # -- control B: this failure's OWN fork row
        rec = _score_row(groups, fork)
        rec["seed"] = f["seed"]
        rec["in_residual"] = f["seed"] in resid
        rec["family"] = f["family"]
        per.append(rec)
        if f["seed"] not in resid:
            B["n"] += 1
            B["lea"] += bool(rec["lea"])
            B["direct"] += bool(rec["direct"])
        # -- control A: random rows inside the same seed's scored window
        lo = groups[0]["f_row"] if groups else 0
        hi = min(win, len(rows) - 1)
        if hi > lo + 8:
            for _ in range(a.rows):
                r = _score_row(groups, rng.randrange(lo, hi))
                A["n"] += 1
                A["lea"] += bool(r["lea"])
                A["direct"] += bool(r["direct"])
    json.dump({"tool": "fz2_m10_step0.control", "seed": a.seed,
               "rows_per_seed": a.rows, "A": A, "B": B, "per": per},
              open(a.out, "w"), indent=1)
    print(f"control -> {Path(a.out).name}")
    print(f"  A  random rows in the same {len(led['failures'])} seeds' windows:"
          f"  8D mod3 before the row {A['lea']}/{A['n']} = "
          f"{100.0 * A['lea'] / max(A['n'], 1):.2f} %"
          f"   ... dest IS an EA register of the row's own dispatch "
          f"{A['direct']}/{A['n']} = {100.0 * A['direct'] / max(A['n'], 1):.2f} %")
    print(f"  B  the other {B['n']} ledger failures at THEIR own fork rows:"
          f"  8D mod3 {B['lea']}/{B['n']} = "
          f"{100.0 * B['lea'] / max(B['n'], 1):.2f} %"
          f"   ... dest is an EA register {B['direct']}/{B['n']} = "
          f"{100.0 * B['direct'] / max(B['n'], 1):.2f} %")


def _score_row(groups, row):
    """The predicate, evaluated at ONE row: is there an `8D` mod3 retired at
    or before it, and is its destination a register of the EA the instruction
    in dispatch at that row actually forms?"""
    gi = None
    for j, g in enumerate(groups):
        if g["f_row"] <= row:
            gi = j
        else:
            break
    if gi is None:
        return {"row": row, "lea": None, "direct": False, "ea": None}
    leas = [(j, lea_mod3(groups[j]["bytes"])) for j in range(gi + 1)]
    leas = [(j, m) for j, m in leas if m]
    ea = decode_ea(groups[gi]["bytes"])
    ovr = seg_override_before(groups, gi)
    direct = False
    dest = None
    if leas and ea:
        for j, m in leas[::-1]:
            if m[0] in ea["regs"]:
                direct, dest = True, m[0]
                break
    return {"row": row, "lea": bool(leas), "n_lea": len(leas),
            "direct": direct, "dest": dest,
            "ea": None if not ea else {"seg": ovr or ea["seg"],
                                       "regs": ea["regs"]}}


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("step0")
    s.add_argument("--out", default=str(OUT))
    s.set_defaults(fn=cmd_step0)
    s = sub.add_parser("control")
    s.add_argument("--out", default=str(OUT).replace(".json", "_control.json"))
    s.add_argument("--seed", type=int, default=20260810)
    s.add_argument("--rows", type=int, default=200)
    s.set_defaults(fn=cmd_control)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
