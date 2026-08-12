#!/usr/bin/env python3
"""ghost_launch_pred -- THE PREDICTED ucore GHOST-ADDRESS COLUMN under the
LAUNCH LAW, built BEFORE the RTL is edited and committed with the
pre-registration.

WHAT IT IS FOR.  `docs/notes/ghost_launch_law_results_2026-08-11.md` measured
the law on the CHIP at 200/200 and booked the RTL relocation.  A landing owes
its own predicted table, cell for cell, registered before the edit -- otherwise
"the core moved towards the chip" is a number chosen after seeing the result.
This file IS that table, and the same code scores it afterwards.

THE MODEL, in three transcribed parts and NO free parameter:

  (1) THE CLASS comes from the law, `dGR -> {SP, AND, BARE}`.
      `dGR` is taken from the committed sweep
      (`launch-law/sweep.json`, 208 cells at BLOCK 2) where it exists, and
      from `dQ` elsewhere.  `dQ` -- the clocks from the last queue op of ANY
      kind to the ghost T1 -- is IDENTICAL on the chip and the core columns
      (2,600 / 2,600 block-instances, measured) and the sweep pins it:

          dQ 4 5 6 7  ->  dGR 0 1 2 3                     (1:1, 20/20/20/2)
          dQ 1        ->  dGR 1 (AND) or 4 (BARE)         THE MULTIPLY ALIAS
          dQ 2        ->  dGR 2 or 5   -- both BARE       class unambiguous
          dQ 3        ->  dGR 3 or 6   -- both BARE       class unambiguous

      so the CLASS is a function of `dQ` alone EXCEPT at `dQ == 1`, and that
      one bin is resolved from the sweep on every cell the sweep covers.  Where
      it is not covered the model takes `dQ == 1 -> AND` and SAYS SO
      (`alias_assumed`), because `dQ mod 4` is measured PURE on 672/672
      non-multiply blocks.

  (2) THE RAIL is `v30u_eu.sv:1481-1493`'s own expression `ghost_off`,
      evaluated on the registers M10-SYS reads out of the core at the ghost
      row (`launch-law/rails_all.json`, all 33 legs, w0/a0/block 2).  It is
      `ghost_pred_cell.ghost_off_of`, unmodified.

  (3) THE ADDRESS is `SS:<offset>` with the offset

          SP    -> the measured `SP` at the ghost row
          AND   -> rail & SP
          BARE  -> rail

DECLARED LIMITS, registered rather than discovered:
  * the rails are measured at ONE (waits, align, block) per leg.  A leg whose
    rail moves with those axes is mispredicted, and `model` below is the
    falsifier that says which legs those are BEFORE the edit.
  * block 0 is the COLD block and the law's own scorer excludes it.  It is
    predicted here anyway, and its misses are reported separately.
  * `ghost_uses_mul_hi` is NOT modelled: the landing leaves that arm alone, so
    a cell where it fires keeps today's address.  `model` finds them.
"""
import argparse
import collections
import gzip
import json
import sys
import time
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

import ghost_pred_cell as G                                    # noqa: E402
import ghost_launch_law as L                                   # noqa: E402

OUT = G.OUT / "launch-law"
RAILS = OUT / "rails_all.json"
SWEEP = OUT / "sweep.json"
PRED = OUT / "pred.json"
SS = G.SEG_BASE["SS"]


# --------------------------------------------------------------------------- #
def rails_all(dgr_of_leg=None):
    """The leg's RAIL, read at the clock the GHOST ROW IS CURRENT.

    ⚠ `ghost_pred_cell rails` calibrates its freeze on the ghost's **T1**
    (`biu == ghost addr`), and the whole point of this wave is that the T1 is
    `dGR` clocks AFTER the row.  `TMPA` / `EA_RESIDUE` move in between on every
    leg with a memory predecessor, so the T1 freeze reads the WRONG rail there
    -- measured: it gives `0000` on `mem1`/`memw`/`mempop`/`pfxmem`/`pfxpro`/
    `popmem` while the core's own posted address says the masked rail is
    `c040`/`b080`.  The walk is retained over `d in [-12,+1]`, so the rail is
    taken at `d = -dGR` instead, which is the row's own clock."""
    d = json.loads(RAILS.read_text())
    out = {}
    for r in d["rows"]:
        if not r.get("ok"):
            continue
        want = -(dgr_of_leg or {}).get(r["leg"], 0)
        terms = r["terms"]
        for w in r.get("walk", []):
            if w["d"] == want:
                terms = w["terms"]
                break
        out[r["leg"]] = {"rail": G.ghost_off_of(terms, r["leg"]),
                         "sp": G.SP_AT_PROBE[r["leg"]],
                         "d": want, "terms": terms}
    return out


def sweep_dgr():
    if not SWEEP.exists():
        return {}
    return {G.cell_key(r["leg"], r["waits"], r["align"]):
            L.dgr_of(r["loc"], r["opc"])
            for r in json.loads(SWEEP.read_text())["rows"]}


def column(which):
    """{(cell, block): (dQ, measured 20-bit ghost address)} off the RETAINED
    raw words of `board` or `core` -- the same walk `_blocks` makes."""
    tab = {r["cell"]: r for r in G._load(which)}
    out = {}
    for leg in G.LEG_ORDER:
        for w in G.WAITS:
            f = G.OUT / which / f"{G.stratum_key(leg, w)}.raw.json.gz"
            if not f.exists():
                continue
            with gzip.open(f, "rt") as fh:
                sh = json.load(fh)
            for ck, ws in sh.items():
                r = tab.get(ck)
                if not r or not r.get("ok"):
                    continue
                rows = G._rows_from_words([int(x, 16) for x in ws])
                for n, g in enumerate(r["ghost"]):
                    i = g["row"]
                    ops = [j for j in range(max(0, i - 60), i) if rows[j]["qs"]]
                    out[(ck, n)] = ((i - ops[-1]) if ops else None, g["addr"])
    return out


CLASS_OF_DQMOD4 = {0: "SP", 1: "AND", 2: "BARE", 3: "BARE"}
DGR_OF_DQ = {1: 1, 2: 2, 3: 3, 4: 0, 5: 1, 6: 2, 7: 3}


def _dgr_w0a0(core):
    """dGR at each leg's own `w0 a0` cell -- the cell `rails_all` was taken on.
    From the sweep where it exists; from `dQ` (the 1:1 map above) elsewhere."""
    SWD = sweep_dgr()
    out = {}
    for leg in G.LEG_ORDER:
        ck = G.cell_key(leg, 0, 0)
        if ck in SWD and SWD[ck] is not None:
            out[leg] = SWD[ck]
        elif (ck, 2) in core and core[(ck, 2)][0] is not None:
            out[leg] = DGR_OF_DQ.get(core[(ck, 2)][0], 0)
    return out


def _rail_of_cell(r, cur, sp):
    """The cell's OWN rail.  Its masked half is MEASURED -- today's core posts
    `SS:(rail & SP)` -- and only the bits OUTSIDE the mask come from the leg's
    walk.  A cell whose current address is `SS:SP` (wave-4's V2 arm, the one
    this landing replaces) has no measured masked half and takes the leg's."""
    if cur is None:
        return None, "no-cur"
    off = (cur - SS) & 0xFFFFF
    if off == sp:
        return r["rail"], "leg (SP arm fired today)"
    if off & ~sp & 0xFFFF:
        return None, "cur is not SS:(x & SP)"
    return (off | (r["rail"] & ~sp & 0xFFFF)), "cell"


def predict():
    core = column("core")
    chip = column("board")
    R = rails_all(_dgr_w0a0(core))
    SWD = sweep_dgr()
    rows = []
    for (ck, n), (dq, cur) in sorted(core.items()):
        leg = ck.split("_w")[0]
        # THE NULL CONTROLS HAVE NO GHOST.  `n_pop` is a documented `POP AW`
        # and `n_mod0` is `8F /0` with a real ModR/M memory operand, so
        # `ghost_read_stale_alu` is FALSE on both and the relocation cannot
        # reach them BY CONSTRUCTION.  The read this cell records there is the
        # POP's own stack read, and it must not move.  (Found by this model's
        # first run, which predicted 24 of them would BREAK.)
        if leg in G.NULLS:
            rows.append({"cell": ck, "block": n, "dq": dq, "dgr": None,
                         "klass": "NULL", "pred": cur, "cur": cur,
                         "chip": chip.get((ck, n), (None, None))[1],
                         "alias_assumed": False,
                         "why": "null control: no ghost, no relocation"})
            continue
        r = R.get(leg)
        d_sweep = SWD.get(ck) if n == 2 else None
        alias = False
        if d_sweep is not None:
            klass = L.law(d_sweep)
        elif dq is None:
            klass = None
        else:
            klass = CLASS_OF_DQMOD4[dq % 4]
            alias = (dq == 1)
        rail, how = (None, "no rail") if r is None \
            else _rail_of_cell(r, cur, r["sp"])
        if rail is None or klass is None:
            rows.append({"cell": ck, "block": n, "dq": dq, "dgr": d_sweep,
                         "klass": klass, "pred": None, "cur": cur,
                         "chip": chip.get((ck, n), (None, None))[1],
                         "alias_assumed": alias, "why": how})
            continue
        sp = r["sp"]
        off = sp if klass == "SP" else (rail & sp) if klass == "AND" else rail
        rows.append({"cell": ck, "block": n, "dq": dq, "dgr": d_sweep,
                     "klass": klass, "rail": f"{rail:04x}", "rail_src": how,
                     "sp": f"{sp:04x}",
                     "pred": (SS + off) & 0xFFFFF, "cur": cur,
                     "chip": chip.get((ck, n), (None, None))[1],
                     "alias_assumed": alias})
    return rows


# --------------------------------------------------------------------------- #
def cmd_model(a):
    """THE PRE-EDIT FALSIFIER.  Today's core posts `ghost_off & SP` on every
    ghost except where the `(eu_ghost_idle && !q_ripe) ? SP` arm or
    `ghost_uses_mul_hi` fires.  If the rail this file uses is the rail the RTL
    uses, EVERY measured core address must be `SS:(rail & SP)` or `SS:SP`.
    Whatever is left over is where the model is blind, and it is named HERE,
    before the edit, not explained afterwards."""
    core = column("core")
    R = rails_all(_dgr_w0a0(core))
    c = collections.Counter()
    odd = collections.Counter()
    for (ck, n), (_dq, cur) in sorted(core.items()):
        leg = ck.split("_w")[0]
        r = R.get(leg)
        if r is None:
            c["NO_RAIL"] += 1
            odd[leg] += 1
            continue
        off = (cur - SS) & 0xFFFFF
        if off == r["sp"]:
            c["SP (today's V2 arm)"] += 1
        elif not (off & ~r["sp"] & 0xFFFF) and off < 0x10000:
            c["AND (SS:(x & SP))"] += 1
        else:
            c["UNMODELLED"] += 1
            odd[f"{leg} b{n}"] += 1
    print("  today's core column against `SS:(rail&SP)` / `SS:SP`:")
    for k, v in c.most_common():
        print(f"     {k:<12} {v}")
    if odd:
        print("\n  where the model is blind (leg or leg+block):")
        for k, v in sorted(odd.items()):
            print(f"     {k:<16} {v}")
    return 0


def cmd_pred(a):
    rows = predict()
    n_hit = sum(1 for r in rows if r["pred"] is not None
                and r["pred"] == r["chip"])
    n_now = sum(1 for r in rows if r["cur"] == r["chip"])
    # per-CELL (all 5 blocks must agree), which is what `ghost_pred_cell score`
    # counts
    by = collections.defaultdict(list)
    for r in rows:
        by[r["cell"]].append(r)
    cells_now = sum(1 for c, rs in by.items()
                    if all(x["cur"] == x["chip"] for x in rs))
    cells_pred = sum(1 for c, rs in by.items()
                     if all(x["pred"] is not None and x["pred"] == x["chip"]
                            for x in rs))
    out = {"tool": "ghost_launch_pred pred", "git": G._git_head(),
           "rails": str(RAILS.relative_to(ROOT)),
           "sweep": str(SWEEP.relative_to(ROOT)),
           "n_rows": len(rows), "n_cells": len(by),
           "blocks_identical_now": n_now,
           "blocks_identical_predicted": n_hit,
           "cells_identical_now": cells_now,
           "cells_identical_predicted": cells_pred,
           "alias_assumed": sum(1 for r in rows if r["alias_assumed"]),
           "rows": rows,
           "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    PRED.write_text(json.dumps(out, indent=1) + "\n")
    print(f"  {len(rows)} block-instances over {len(by)} cells")
    print(f"  block-instances chip==core   now {n_now}   predicted {n_hit}")
    print(f"  CELLS          chip==core   now {cells_now}   "
          f"predicted {cells_pred}   (this is `ghost_pred_cell score`'s number)")
    print(f"  alias-assumed block-instances (dQ==1 outside the sweep): "
          f"{out['alias_assumed']}")
    # the LAW POPULATION: block 2 of the 13 swept legs
    lawrows = [r for r in rows if r["block"] == 2 and r["dgr"] is not None]
    lh = sum(1 for r in lawrows if r["pred"] == r["chip"])
    print(f"  THE LAW POPULATION (block 2, swept dGR): {lh}/{len(lawrows)} "
          f"predicted to match the chip")
    print(f"  -> {PRED}")
    return 0


def cmd_score(a):
    """After the landing: the MEASURED core column against the REGISTERED
    prediction, block-instance for block-instance."""
    p = json.loads(PRED.read_text())
    core = column("core")
    hit = miss = nopred = 0
    misses = []
    for r in p["rows"]:
        k = (r["cell"], r["block"])
        if k not in core:
            continue
        got = core[k][1]
        if r["pred"] is None:
            nopred += 1
            continue
        if got == r["pred"]:
            hit += 1
        else:
            miss += 1
            misses.append((r["cell"], r["block"], r["klass"], r["pred"], got,
                           r["chip"]))
    print(f"  PREDICTED vs MEASURED core: {hit} hit / {miss} miss / "
          f"{nopred} unpredicted")
    for m in misses[:60]:
        print(f"    MISS {m[0]:<18} b{m[1]} law={m[2]:<5} "
              f"pred={m[3]:05x} got={m[4]:05x} chip={m[5]:05x}")
    if len(misses) > 60:
        print(f"    ... {len(misses) - 60} more")
    # and the law population separately
    law = [r for r in p["rows"] if r["block"] == 2 and r["dgr"] is not None]
    lh = sum(1 for r in law
             if (r["cell"], 2) in core and core[(r["cell"], 2)][1] == r["pred"])
    print(f"  THE LAW POPULATION (block 2, swept dGR): {lh}/{len(law)}")
    lc = sum(1 for r in law
             if (r["cell"], 2) in core and core[(r["cell"], 2)][1] == r["chip"])
    print(f"     of which core == CHIP: {lc}/{len(law)}")
    return 0 if miss == 0 else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    s = ap.add_subparsers(dest="cmd", required=True)
    for nm, fn in (("model", cmd_model), ("pred", cmd_pred),
                   ("score", cmd_score)):
        c = s.add_parser(nm)
        c.set_defaults(fn=fn)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
