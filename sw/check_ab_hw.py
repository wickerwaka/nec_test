#!/usr/bin/env python3
"""check_ab_hw - Campaign 4 Mission C: in-silicon A/B first light.

Runs the boot image on the harness board in both A/B positions and diffs:

  1. chip position (CFG.use_core=0) vs the original boot golden
     (sw/testdata/largemode_boot_real.hex) - proves the new bitstream did
     not disturb the known-good chip path.
  2. core position (CFG.use_core=1) vs the chip capture from (1) - the
     first-light comparison: the in-FPGA core against the socketed part,
     same harness, same run.
  3. core position vs the boot golden (cross-check of 2).

Column policy = sw/check_boot.py (mission G): qs from release, bs from
release+8, t/ube/addr/data/ps from release+9; addr on T1 rows, data on
T2/T3 and active T4/Ti rows, ps on active T2 rows. Float-retention rows
are excluded by the policy (the core's internal AD net has no charge
retention, so raw float bytes legitimately differ from the chip's).

Usage: check_ab_hw.py [chip|core|all] [nrows] [--host H]
"""
import argparse
import sys
from pathlib import Path

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
from decode_capture import decode      # noqa: E402
from v30run import run_image           # noqa: E402

GOLD = SW / "testdata" / "largemode_boot_real.hex"
BOOT = SW / "boot.bin"

T_NAME = {0: "Ti", 1: "T1", 2: "T2", 3: "T3", 4: "Tw", 5: "T4"}
BS_NAME = {0: "INTA", 1: "IOR", 2: "IOW", 3: "HALT",
           4: "CODE", 5: "MEMR", 6: "MEMW", 7: "PASV"}
QS_NAME = {0: "-", 1: "F", 2: "E", 3: "S"}


def load_golden():
    recs = [decode(int(l, 16)) for l in GOLD.read_text().split() if l]
    rel = next(i for i, r in enumerate(recs) if not r["reset"])
    return [norm_g(r) for r in recs[rel:]]


def norm_g(r):
    return {"t": r["t_state"], "bs_early": r["bs_early"], "qs": r["qs"],
            "ube_n": r["ube_n"], "ad_addr": r["ad_addr"],
            "ad_data": r["ad_data"], "ps": r["ps"]}


def run_boot(host, use_core):
    recs = run_image(BOOT.read_bytes(), host, tag="abboot",
                     use_core=use_core)
    rel = next(i for i, r in enumerate(recs) if not r["rst"])
    return recs[rel:]


def diff(a, b, n, la, lb, maxprint=12):
    """check_boot column policy; a/b need t/bs_early/qs/ube_n/ad_addr/
    ad_data/ps keys. Returns (bad, first)."""
    n = min(n, len(a), len(b))
    bad, first = 0, None
    for i in range(n):
        r, s = a[i], b[i]
        rt = r.get("t_state", r.get("t"))
        st = s.get("t_state", s.get("t"))
        mm = []
        if r["qs"] != s["qs"]:
            mm.append(f"qs {QS_NAME[r['qs']]}!={QS_NAME[s['qs']]}")
        if i >= 8 and r["bs_early"] != s["bs_early"]:
            mm.append(f"bs {BS_NAME[r['bs_early']]}!={BS_NAME[s['bs_early']]}")
        if i >= 9:
            if rt != st:
                mm.append(f"t {T_NAME.get(rt)}!={T_NAME.get(st)}")
            if r["ube_n"] != s["ube_n"]:
                mm.append(f"ube {r['ube_n']}!={s['ube_n']}")
            active = r["bs_early"] != 7
            if rt == 1 and r["ad_addr"] != s["ad_addr"]:
                mm.append(f"addr {r['ad_addr']:05x}!={s['ad_addr']:05x}")
            if rt in (2, 3) and r["ad_data"] != s["ad_data"]:
                mm.append(f"data {r['ad_data']:04x}!={s['ad_data']:04x}")
            if rt in (0, 5) and active and r["ad_data"] != s["ad_data"]:
                mm.append(f"nxta {r['ad_data']:04x}!={s['ad_data']:04x}")
            if rt == 2 and active and r["ps"] != s["ps"]:
                mm.append(f"ps {r['ps']:x}!={s['ps']:x}")
        if mm:
            bad += 1
            if first is None:
                first = i
            if bad <= maxprint:
                print(f"    row {i:3d}: " + ", ".join(mm) +
                      f"   [{la} {T_NAME.get(rt)} {BS_NAME[r['bs_early']]} "
                      f"{QS_NAME[r['qs']]} {r['ad_addr']:05x}/"
                      f"{r['ad_data']:04x} | {lb} {T_NAME.get(st)} "
                      f"{BS_NAME[s['bs_early']]} {QS_NAME[s['qs']]} "
                      f"{s['ad_addr']:05x}/{s['ad_data']:04x}]")
    return bad, first, n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", nargs="?", default="all",
                    choices=("chip", "core", "all"))
    ap.add_argument("nrows", nargs="?", type=int, default=200)
    ap.add_argument("--host", default="root@mister-nec")
    a = ap.parse_args()

    gold = load_golden()
    rc = 0
    chip = None

    if a.mode in ("chip", "all"):
        print("== chip position (use_core=0): boot vs golden ==")
        chip = run_boot(a.host, use_core=False)
        bad, first, n = diff(gold, chip, a.nrows, "gold", "chip")
        print(f"chip-vs-golden: {'MATCH' if bad == 0 else f'{bad} rows differ (first {first})'} over {n} rows\n")
        rc |= 1 if bad else 0

    if a.mode in ("core", "all"):
        print("== core position (use_core=1): boot ==")
        core = run_boot(a.host, use_core=True)
        if chip is None:
            chip = run_boot(a.host, use_core=False)
        bad, first, n = diff(chip, core, a.nrows, "chip", "core")
        print(f"core-vs-chip:   {'MATCH' if bad == 0 else f'{bad} rows differ (first {first})'} over {n} rows")
        bad2, first2, n2 = diff(gold, core, a.nrows, "gold", "core")
        print(f"core-vs-golden: {'MATCH' if bad2 == 0 else f'{bad2} rows differ (first {first2})'} over {n2} rows")
        rc |= 2 if (bad or bad2) else 0

    return rc


if __name__ == "__main__":
    sys.exit(main())
