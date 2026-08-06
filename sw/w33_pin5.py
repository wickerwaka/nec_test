#!/usr/bin/env python3
"""w33_pin5 -- the `ucore`-only `PIN` FIVE, diagnosed from the BANKED ROWS.

> *"A guiding principal here needs to be simplicity.  This is 80's era
> hardware, they aren't wasting silicon on anything that isn't necessary.
> Complex or confusing behavior that we see is likely to be simple systems
> interacting in ways you do not fully understand yet."*

`wrfuzz_survey_2026-08-05.md` sec.5 enumerated five seeds on which the `ucore`
diverges from silicon in fabric AND in the TB while the model does not.  All
five are family `PIN` -- the bus SCHEDULES are identical over the window and no
cycle moved.  Four part on the `data` lanes at the row immediately after a
write T1; the fifth parts on `ps`.

This tool prints, per seed and with NO fitting: the diverging rows, the bus
cycle each one sits in, the cycle's status/address, the EU's micro-state around
it as the two engines report it, and -- for the `data` partings -- **which of
the two candidate write orders the observed word matches**.  It is the
banked-evidence half of W3.3; the directed cell (`w33_poste_cell`) is the
silicon half.

Usage:
    python3 sw/w33_pin5.py rows   [--seeds ...] [--core ucore]
    python3 sw/w33_pin5.py ctx    [--seeds ...]
"""
import argparse
import gzip
import json
import sys
import tempfile
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

import fuzz_classify as fc                                  # noqa: E402
import timed_fuzz as tf                                     # noqa: E402
import ucsim_fuzz as uf                                     # noqa: E402

CACHE = Path.home() / ".cache" / "ucsimt-tmp" / "wrfuzz_w2" / "seeds"

# survey sec.5's table, verbatim -- the five, plus sec.5.1's two model-shared
# `PIN` members so the family is printed entire.
FIVE = ["200127", "203092", "205145", "207147", "209095"]
SHARED = ["215017", "225009"]

BS_NAME = {0: "INTA", 1: "IOR", 2: "IOW", 3: "HALT",
           4: "CODE", 5: "MEMR", 6: "MEMW", 7: "PASV"}


def seed_paths(ks):
    out = []
    for k in ks:
        hits = sorted(CACHE.glob(f"*_{k}_*.json.gz"))
        if not hits:
            raise SystemExit(f"seed {k}: no banked capture in {CACHE}")
        out.append((k, hits[0]))
    return out


def load(p):
    return json.loads(gzip.decompress(Path(p).read_bytes()))


def engine_rows(entry, core):
    image, meta, g, sha = uf.regen(entry)
    if sha != entry["image_sha256"]:
        raise ValueError("GEN_DRIFT")
    n = len(entry["chip_rows"])
    with tempfile.TemporaryDirectory() as td:
        if core == "sim":
            rows, err = tf.run_sim(image, entry, n, td)
        else:
            rows, err = tf.run_tb(image, entry, n, td, core)
    return rows, err, image, g


def t_of(r):
    return r.get("t_state", r.get("t"))


def launches(rows, n):
    """(row, bs, addr) of every bus cycle T1 in [0, n)."""
    out = []
    for i in range(min(n, len(rows))):
        if t_of(rows[i]) == 1 and rows[i]["bs_early"] != 7:
            out.append((i, rows[i]["bs_early"], rows[i]["ad_addr"] & 0xFFFFF))
    return out


def cycle_of(lc, row):
    prev = None
    for (r, bs, a) in lc:
        if r > row:
            break
        prev = (r, bs, a)
    return prev


def cmd_rows(a):
    ks = a.seeds.split(",") if a.seeds else (FIVE + SHARED if a.all else FIVE)
    for k, p in seed_paths(ks):
        e = load(p)
        chip = e["chip_rows"]
        rows, err, image, g = engine_rows(e, a.core)
        if not rows:
            print(f"\n== wr1/{k}: ENGINE ERROR {err[:200]}")
            continue
        d = fc.diff_rows(chip, rows)
        lc_c = launches(chip, d.n)
        lc_e = launches(rows, d.n)
        same_sched = [x[:3] for x in lc_c] == [x[:3] for x in lc_e]
        print(f"\n== wr1/{k}  {e.get('stratum_label')}  core={a.core}  "
              f"n={d.n}  ndiff={len(d.rows)}  "
              f"schedule_identical={'YES' if same_sched else 'NO'} "
              f"(chip {len(lc_c)} cycles, engine {len(lc_e)})")
        for rd in d.rows[: a.limit]:
            i = rd.i
            cy = cycle_of(lc_c, i)
            off = i - cy[0] if cy else None
            prev = None
            for j, (r, bs, ad) in enumerate(lc_c):
                if r == (cy[0] if cy else -1) and j:
                    prev = lc_c[j - 1]
            print(f"  row {i:5d}  t={t_of(chip[i])} "
                  f"in {BS_NAME[cy[1]]:>4}@{cy[2]:05x}+{off} "
                  f"prev={BS_NAME[prev[1]]+'@%05x' % prev[2] if prev else '-'} "
                  f"| {' '.join(rd.other) or rd.qs_txt}")
            print(f"          chip ad_data={chip[i]['ad_data']:04x} "
                  f"eng ad_data={rows[i]['ad_data']:04x} "
                  f"chip ps={chip[i]['ps']:x} eng ps={rows[i]['ps']:x} "
                  f"chip qs={chip[i]['qs']} eng qs={rows[i]['qs']}")
        if len(d.rows) > a.limit:
            print(f"  ... {len(d.rows) - a.limit} more")
    return 0


def cmd_ctx(a):
    """The instruction in flight at the parting, from the GENERATOR's own
    listing -- no disassembly guess.  Prints the write's address, the value the
    chip put on the lanes, the value the engine put there, and the bytes of the
    program around the point."""
    ks = a.seeds.split(",") if a.seeds else FIVE
    for k, p in seed_paths(ks):
        e = load(p)
        chip = e["chip_rows"]
        rows, err, image, g = engine_rows(e, a.core)
        if not rows:
            print(f"\n== wr1/{k}: ENGINE ERROR {err[:200]}")
            continue
        d = fc.diff_rows(chip, rows)
        lc = launches(chip, d.n)
        print(f"\n== wr1/{k}  {e.get('stratum_label')}  ndiff={len(d.rows)}")
        ins = g.get("ins") if isinstance(g, dict) else None
        if ins:
            print(f"   generator listing: {len(ins)} instructions")
        # the WRITE the parting sits after
        for rd in d.rows[:4]:
            cy = cycle_of(lc, rd.i)
            if not cy:
                continue
            print(f"   parting row {rd.i}: cycle {BS_NAME[cy[1]]} "
                  f"@{cy[2]:05x}, chip word {chip[rd.i]['ad_data']:04x}, "
                  f"engine word {rows[rd.i]['ad_data']:04x}, "
                  f"xor {chip[rd.i]['ad_data'] ^ rows[rd.i]['ad_data']:04x}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in (("rows", cmd_rows), ("ctx", cmd_ctx)):
        p = sub.add_parser(name)
        p.add_argument("--seeds", default=None)
        p.add_argument("--core", default="ucore")
        p.add_argument("--limit", type=int, default=20)
        p.add_argument("--all", action="store_true")
        p.set_defaults(fn=fn)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
