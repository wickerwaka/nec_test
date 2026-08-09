#!/usr/bin/env python3
"""sm3_h7_opcode -- WHICH INSTRUCTION'S BOUNDARY the NMI recognition lands on,
over the banked NMI population.

A MEASUREMENT tool (session SM3 sitting 7, hypothesis H7); it is never a gate.

§65.1's lead, verbatim: *"The selector is not on the pin side; it is WHICH
INSTRUCTION'S BOUNDARY the recognition lands on."*  The measurement it names --
*"the opcode at the recognition boundary for the 30 banked `A+12` seeds against
the 18 `A+13` ones"* -- is taken here, CHIP-SIDE ONLY, with no engine in the
loop at all.

HOW THE OPCODE IS READ, and there is no queue model in it.  The V30's `QS`
port announces every queue transaction on the pins: `E` (2) flushes, `F` (1)
pops the FIRST byte of an instruction, `S` (3) pops a subsequent byte.  Queue
bytes are consumed in strictly ascending address order from the fetch that
followed the last flush, so a single POINTER -- set to the first CODE T1's
address after every `E`, advanced one byte per pop -- names the image byte each
pop consumed.  The image is the seed's own regenerated one (`ucsim_fuzz.regen`,
sha-checked), so the opcode is read out of the program, not guessed from a
disassembly of the bus.

Reported per seed:

  op_A     the opcode of the instruction whose first byte was popped most
           recently at or before row `A` -- i.e. what the part was EXECUTING
           when the pin went high
  op_V     the opcode of the last `F` pop strictly before `V` -- the last
           instruction started before the entry
  n_F      how many `F` pops fall in the window [A, V)

Usage:
  sm3_h7_opcode.py [--pin 1] [--jobs N] [--report out.json]
"""
import argparse
import gzip
import json
import os
import sys
from collections import Counter, defaultdict
from multiprocessing import Pool
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

import ucsim_fuzz as uf                                   # noqa: E402
import sm3_nmigeom as ng                                  # noqa: E402

BANK = ROOT / "tests" / "v30" / "fuzz_bank"
CODE, MEMR, INTA = 4, 5, 0
NMI_VEC = 0x00008


def pops(rows, image, win):
    """[(row, kind, addr, byte)] for every queue pop the pins announce.

    kind is 'F' or 'S'.  `addr` is None while the pointer is unset (a pop
    before the first CODE T1 after a flush cannot be placed, and is reported
    rather than invented)."""
    out = []
    ptr = None
    need = True                      # pointer must be (re)set at the next CODE T1
    n = min(win, len(rows))
    for i in range(n):
        r = rows[i]
        t = r.get("t_state", r.get("t"))
        if t == 1 and r["bs_early"] == CODE and need:
            ptr = r["ad_addr"] & 0xFFFFF
            need = False
        q = r["qs"]
        if q == 2:                   # E -- flush
            ptr = None
            need = True
        elif q in (1, 3):
            if ptr is None:
                out.append((i, "F" if q == 1 else "S", None, None))
            else:
                b = image[ptr] if ptr < len(image) else None
                out.append((i, "F" if q == 1 else "S", ptr, b))
                ptr += 1
    return out


def one(path):
    entry = json.loads(gzip.decompress(Path(path).read_bytes()))
    e = entry.get("evt") or {}
    out = {"path": str(path), "pin": int(e.get("pin", -1))}
    try:
        image, meta, g, sha = uf.regen(entry)
    except Exception as ex:                                   # noqa: BLE001
        out["err"] = str(ex)[:120]
        return out
    if sha != entry["image_sha256"]:
        out["err"] = "GEN_DRIFT"
        return out
    recs = entry["chip_rows"]
    win = uf.window_of(recs)
    anchor = int(meta["anchor_linear"]) & 0xFFFFF
    arm = ng.first_t1(recs, CODE, anchor, win)
    if arm < 0:
        out["err"] = "NO ARM"
        return out
    A = arm + int(e.get("delay", 0)) + 2
    kind, vaddr = ((MEMR, NMI_VEC) if out["pin"] == 1 else (INTA, None))
    V = ng.first_t1(recs, kind, vaddr, win)
    out.update({"A": A, "V": V, "gap": (V - A) if V >= 0 else None})
    if V < 0:
        return out
    pp = pops(recs, image, win)
    fs = [p for p in pp if p[1] == "F"]
    at_A = [p for p in fs if p[0] <= A]
    bef_V = [p for p in fs if p[0] < V]
    out["op_A"] = at_A[-1][3] if at_A else None
    out["op_A_row"] = at_A[-1][0] if at_A else None
    out["op_A_addr"] = at_A[-1][2] if at_A else None
    out["op_V"] = bef_V[-1][3] if bef_V else None
    out["op_V_row"] = bef_V[-1][0] if bef_V else None
    out["n_F_win"] = sum(1 for p in fs if A <= p[0] < V)
    out["n_pop_win"] = sum(1 for p in pp if A <= p[0] < V)
    out["unplaced"] = sum(1 for p in pp if p[2] is None)
    return out


def seeds_of(banks):
    # ⚠ Its default banks are the v1 corpus, `status: SUPERSEDED` since
    # 2026-08-09 (SUP-1).  MEASUREMENT TOOL, NOT A GATE, and the banks
    # are named on the command line; nothing was moved or deleted.
    out = []
    for b in banks:
        d = BANK / b / "seeds"
        if d.is_dir():
            out += sorted(str(p) for p in d.glob("*.json.gz"))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bank", default=",".join(ng.BANKS))
    ap.add_argument("--pin", type=int, default=1)
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 4)
    ap.add_argument("--report", default="")
    a = ap.parse_args()

    paths = seeds_of([b for b in a.bank.split(",") if b])
    with Pool(a.jobs) as pool:
        ax = pool.map(ng.axis, paths, chunksize=16)
    paths = [p for p, x in zip(paths, ax) if x == a.pin]
    with Pool(a.jobs) as pool:
        res = pool.map(one, paths, chunksize=4)

    ok = [r for r in res if not r.get("err") and r.get("gap") is not None]
    print(f"== sm3_h7_opcode -- {len(res)} seeds pin={a.pin}, "
          f"{len(ok)} with a recognition")
    bad = [r for r in res if r.get("err")]
    if bad:
        print("  ERRORS:", dict(Counter(r["err"] for r in bad)))
    print("  unplaced pops (pointer unset):",
          sum(r.get("unplaced", 0) for r in ok))
    print("  chip gap V-A:",
          dict(sorted(Counter(r["gap"] for r in ok).items())))

    for field in ("op_A", "op_V"):
        print(f"\n  --- {field}: the opcode, by chip gap ---")
        tab = defaultdict(Counter)
        for r in ok:
            tab[r["gap"]][r[field]] += 1
        for gp in sorted(tab):
            items = sorted(tab[gp].items(), key=lambda x: -x[1])
            print(f"    gap {gp:>3} (n={sum(tab[gp].values()):>3}):  " +
                  "  ".join(f"{('%02X' % k) if k is not None else 'none'}:{v}"
                            for k, v in items[:14]))
        # the marginal: for each opcode, the gap distribution
        by = defaultdict(Counter)
        for r in ok:
            by[r[field]][r["gap"]] += 1
        pure12 = [k for k in by if k is not None and set(by[k]) == {12}]
        pure13 = [k for k in by if k is not None and set(by[k]) == {13}]
        mixed = [k for k in by if k is not None and len(set(by[k])) > 1]
        print(f"    opcodes seen only at gap 12: "
              f"{' '.join('%02X' % k for k in sorted(pure12) if k is not None)}")
        print(f"    opcodes seen only at gap 13: "
              f"{' '.join('%02X' % k for k in sorted(pure13) if k is not None)}")
        print(f"    opcodes seen at BOTH:        "
              f"{' '.join('%02X' % k for k in sorted(mixed) if k is not None)}")

    print("\n  --- F pops inside the window [A, V) ---")
    tab = defaultdict(Counter)
    for r in ok:
        tab[r["gap"]][r["n_F_win"]] += 1
    for gp in sorted(tab):
        print(f"    gap {gp:>3}: " +
              " ".join(f"{k}:{v}" for k, v in sorted(tab[gp].items())))

    if a.report:
        Path(a.report).write_text(json.dumps(res))
        print(f"  report -> {a.report}")


if __name__ == "__main__":
    main()
