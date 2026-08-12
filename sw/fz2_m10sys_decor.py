#!/usr/bin/env python3
"""fz2_m10sys_decor -- M10S-Q1: WHAT SILICON CONSUMED, AS (RAIL, DECORATION).

Wave-8's closing instruction was that the open question is NOT "which rail" but
**whether the AND happens at all** -- its one usable seat measured silicon
taking `SS:SP` UNDECORATED where the core applied `ghost_ea_off & SP`.  This
file asks that question of every DERIVE seat at once, off `fz2_m10.py solve`'s
own output, and it asks it as a PARTITION so it can come out either way:

    for each seat, at the FORK FREEZE (the last freeze before the BIU latches
    the forking cycle's own address), is there an UNDECORATED fit -- a bare
    `SEG:TERM` with no `&` and no `|` -- for the CHIP's address?  for the
    CORE's?

The fork freeze is IDENTIFIED FROM THE DATA, not assumed: it is the largest
`d` at which `biu_addr` is still the PREVIOUS cycle's address, i.e. the last
`d` before `biu_addr == core_addr`.  A seat whose sweep never shows the core's
own address is reported and not scored -- `fz2_m10.py`'s own rule.

A DEGENERATE fit is flagged rather than counted twice: two named registers
holding the SAME 16-bit value at a freeze produce two fits that are one
measurement.  Wave-8 stopped on exactly this (`IND == SP` on its only seat)
and it is why the rail question is separate from the decoration question.
"""
import argparse
import json
import sys
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))


def bare(fits):
    """The UNDECORATED fits: `SEG:TERM`, no bitwise operator.  `+1` is kept --
    `acc_phys2 = acc_phys_base + 1` is the part's own split-word arithmetic
    (fz2_m10.fits_at), not a decoration."""
    return [f for f in fits if "&" not in f and "|" not in f]


def fork_freeze(rec):
    """The last freeze at which the BIU has NOT yet latched the forking
    cycle's address.  Derived from `biu_addr`, which the solve prints at every
    freeze for exactly this reason."""
    fs = sorted(rec.get("freezes", []), key=lambda f: f["delta"])
    land = [f for f in fs if f["biu_addr"] == rec["core_addr"]]
    if not land:
        return None
    first = min(f["delta"] for f in land)
    pre = [f for f in fs if f["delta"] < first]
    return pre[-1] if pre else None


def degen(f, fits):
    """{value: [terms holding it]} for the terms named in `fits` -- the
    discrimination the rail question needs and the decoration question does
    not."""
    names = set()
    for x in bare(fits):
        names.add(x.split(":", 1)[1].removesuffix("+1"))
    out = {}
    for n in names:
        v = f["terms"].get(n)
        out.setdefault(v, []).append(n)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--solve", required=True)
    ap.add_argument("--survey", required=True)
    ap.add_argument("--out")
    a = ap.parse_args()

    sv = {r["seed"]: r for r in json.load(open(a.survey))["rows"]}
    rows = json.load(open(a.solve))["rows"]

    print("=== M10S-Q1: (rail, decoration) AT THE FORK FREEZE ===")
    print(f"{'seat':<14} {'pkg@d':<7} {'d':>3} {'chip':>6} {'core':>6}  "
          f"{'CHIP undecorated':<34} {'CORE undecorated':<24}")
    tab, nu_chip, nu_core, nspoke = [], 0, 0, 0
    for r in sorted(rows, key=lambda x: x["seed"]):
        v = sv[r["seed"]]
        pk = f"{v['near_package']}@{v['near_dist']}"
        if r["status"] != "SOLVED":
            print(f"{r['seed']:<14} {pk:<7} {'':>3} {'':>6} {'':>6}  "
                  f"*{r['status']}*")
            continue
        f = fork_freeze(r)
        if f is None:
            print(f"{r['seed']:<14} {pk:<7} {'':>3}  *no freeze lands on the "
                  f"core's own address*")
            continue
        cb, kb = bare(f["chip_fits"]), bare(f["core_fits"])
        spoke = bool(f["chip_fits"])
        nspoke += spoke
        nu_chip += bool(cb)
        nu_core += bool(kb)
        e = {"seed": r["seed"], "pkg": pk, "d": f["delta"],
             "chip_addr": r["chip_addr"], "core_addr": r["core_addr"],
             "chip_fits_n": len(f["chip_fits"]), "core_fits_n": len(f["core_fits"]),
             "chip_bare": cb, "core_bare": kb,
             "chip_degen": {f"{k:04x}" if k is not None else "?": s
                            for k, s in degen(f, f["chip_fits"]).items()},
             "chip_spoke": spoke}
        tab.append(e)
        print(f"{r['seed']:<14} {pk:<7} {f['delta']:>+3d} "
              f"{r['chip_addr']:06x} {r['core_addr']:06x}  "
              f"{(', '.join(cb) or '-- none --'):<34} "
              f"{(', '.join(kb) or '-- none --'):<24}")

    spoke = [e for e in tab if e["chip_spoke"]]
    und = [e for e in spoke if e["chip_bare"]]
    kund = [e for e in spoke if e["core_bare"]]
    print(f"\n  seats scored at the fork freeze            {len(tab)}")
    print(f"  ...with ANY chip fit there                 {len(spoke)}")
    print(f"  ...whose CHIP fit is UNDECORATED           {len(und)}/{len(spoke)}")
    print(f"  ...whose CORE fit is UNDECORATED           {len(kund)}/{len(spoke)}")
    print("\n  THE RAIL, per seat that speaks -- degenerate groups shown "
          "because two registers holding one value are ONE measurement:")
    for e in spoke:
        print(f"    {e['seed']:<14} {e['chip_degen']}")
    if a.out:
        Path(a.out).write_text(json.dumps(
            {"rows": tab, "n_scored": len(tab), "n_spoke": len(spoke),
             "chip_undecorated": len(und), "core_undecorated": len(kund)},
            indent=1))
        print(f"\nwrote {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
