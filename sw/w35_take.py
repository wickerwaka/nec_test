#!/usr/bin/env python3
"""w35_take -- THE ucore's LEG OF W3.4's TAKE-CLOCK LAW: where is the BRK/TF
arm AVAILABLE, and where does the take FIRE, on the ONE_BYTE_LOGIC path?

Spec: `docs/notes/wrfuzz_provenance.md` §7.8 (the `ucore` leg, booked with its
structural half named) and §7.5 (the model's landing).  Pre-registration for
this sitting: `docs/notes/wrfuzz_w35_prereg_2026-08-06.md`.

> *"A guiding principal here needs to be simplicity.  This is 80's era
> hardware, they aren't wasting silicon on anything that isn't necessary.
> Complex or confusing behavior that we see is likely to be simple systems
> interacting in ways you do not fully understand yet."*

WHAT §7.8 LEFT OPEN, VERBATIM: *"the model's gate is `brk_arm_` and a
`ONE_BYTE_LOGIC` form is never in the shadow class, so there
`brk_arm_ == brk_take_`; in the RTL `irq_shadow` is a FLOP that may carry the
PREVIOUS instruction's set, so `brk_arm` and `brk_take` are not interchangeable
there.  **Measure it; do not assume it.**"*

THIS TOOL IS THAT MEASUREMENT, and it is engine-internal on purpose: it reads
the `ucore`'s OWN `+brktrace` stream -- `BRKR` (the TF rise), `1BLD` (every
ONE_BYTE_LOGIC decode, with the four bits a lead gate could be written on),
`1BL` (the flag write), `BRKS` (the sample instant, §85.2a's pop + 1) and
`BRKT` (the take) -- and pairs them with the CHIP's own take, which is the
capture's vector-read row minus the constant 9 that §6.6 and §7.4 measured on
563 directed entries and all 23 P1 seeds.

NOTHING IS FITTED.  Every column is a clock number out of a trace or a capture.

Usage:
    python3 sw/w35_take.py arm  [--core ucore] [--jobs 8]
"""
import argparse
import gzip
import json
import re
import subprocess
import sys
import tempfile
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

W2 = Path.home() / ".cache/ucsimt-tmp/wrfuzz_w2"
OUT = ROOT / "sw" / "testdata" / "w34-grant"

RE_CLK = re.compile(r"^(BRKR|BRKS|BRKT|1BL|1BLD) clk=(\d+)(.*)$")
RE_KV = re.compile(r"(\w+)=(-?\w+)")


def trace(image, entry, nrows, core):
    """The `ucore` TB under the seed's OWN wait directive, `+brktrace` on.
    -> the list of (tag, clk, {k: v}) events, in clock order."""
    import timed_fuzz as tf
    with tempfile.TemporaryDirectory() as td:
        img = Path(td) / "img.hex"
        img.write_text("\n".join(f"{b:02x}" for b in bytes(image)) + "\n")
        argv = [str(tf.tb_bin(core)), f"+bootimg={img}", f"+bootn={nrows}",
                "+mirror=1", f"+out={td}/out.txt", "+brktrace"] \
            + list(tf.tb_wait_args(entry, td))
        p = subprocess.run(argv, capture_output=True, timeout=900, cwd=ROOT)
    ev = []
    for ln in p.stdout.decode().splitlines():
        m = RE_CLK.match(ln)
        if not m:
            continue
        ev.append((m.group(1), int(m.group(2)),
                   {k: v for k, v in RE_KV.findall(m.group(3))}))
    return ev


def _one(args):
    rec, core = args
    import ucsim_fuzz as uf
    seeds = sorted(Path(W2 / "seeds").glob(f"*_{rec['k']}_*.json.gz"))
    entry = json.loads(gzip.decompress(seeds[0].read_bytes()))
    image, meta, g, sha = uf.regen(entry)
    if sha != entry["image_sha256"]:
        return {"seed": rec["seed"], "error": "GEN_DRIFT"}
    n = len(entry["chip_rows"])
    ev = trace(image, entry, n, core)
    erow = rec["geom"]["erow"]
    crow = rec["geom"]["crow"]
    o = {"seed": rec["seed"], "k": rec["k"], "stratum": rec["stratum"],
         "delta": rec["geom"]["delta"], "chip_take": crow - 9}
    tk = [c for t, c, _ in ev if t == "BRKT" and c < erow]
    if not tk:
        o["error"] = "NO_TAKE"
        return o
    o["take"] = tk[-1]
    # the ONE_BYTE_LOGIC decode this take belongs to: the last 1BLD at or
    # before it (the decode always precedes its own instruction's boundary).
    d = [(c, kv) for t, c, kv in ev if t == "1BLD" and c <= o["take"]]
    if not d:
        o["error"] = "NO_1BL_DECODE"
        return o
    o["dec"], kv = d[-1]
    o["ripe_lead"] = int(kv["ripe_lead"])
    o["seen"] = int(kv["seen"])
    o["arm"] = int(kv["arm"])
    o["smp"] = int(kv["smp"])
    o["shd"] = int(kv.get("shd", -1))
    w = [c for t, c, _ in ev if t == "1BL" and o["dec"] <= c <= o["take"]]
    o["write"] = w[-1] if w else None
    s = [(c, kv2) for t, c, kv2 in ev if t == "BRKS" and o["dec"] < c <= o["take"]]
    o["smp_clk"] = s[0][0] if s else None
    o["smp_seen"] = int(s[0][1]["seen"]) if s else None
    r = [c for t, c, _ in ev if t == "BRKR" and c <= o["dec"]]
    o["rise"] = r[-1] if r else None
    return o


def cmd_arm(a):
    import w34_grant as w34
    recs = w34.p1_seeds(a.core)
    with Pool(a.jobs) as pool:
        res = pool.map(_one, [(r, a.core) for r in recs])
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"w35_arm_{a.core}.json").write_text(json.dumps(res, indent=1))
    print(f"== w35_take arm --core {a.core} -- {len(res)} P1 seeds\n")
    print(f"{'seed':<12}{'rise':>6}{'dec':>6}{'ripe':>5}{'seen':>5}{'arm':>4}"
          f"{'smp':>4}{'smpclk':>7}{'write':>6}{'take':>6}{'chip':>6}"
          f"{'gap':>5}{'dec+2':>6}{'pred':>6}")
    ok = Counter()
    for r in res:
        if r.get("error"):
            print(f"{r['seed']:<12} {r['error']}")
            ok["ERROR"] += 1
            continue
        gap = r["take"] - r["chip_take"]
        pred = "MATCH" if r["dec"] + 2 == r["chip_take"] else "MISS"
        ok[pred] += 1
        ok[f"arm@dec={r['arm']}"] += 1
        ok[f"seen@dec={r['seen']}"] += 1
        ok[f"smp@dec={r['smp']}"] += 1
        ok[f"shadow@dec={r['shd']}"] += 1
        ok[f"smpclk-dec={r['smp_clk'] - r['dec'] if r['smp_clk'] else None}"] += 1
        print(f"{r['seed']:<12}{r['rise'] if r['rise'] is not None else -1:>6}"
              f"{r['dec']:>6}{r['ripe_lead']:>5}{r['seen']:>5}{r['arm']:>4}"
              f"{r['smp']:>4}{str(r['smp_clk']):>7}{str(r['write']):>6}"
              f"{r['take']:>6}{r['chip_take']:>6}{gap:>+5d}"
              f"{r['dec'] + 2:>6}{pred:>6}")
    print("\n  " + "  ".join(f"{k}={v}" for k, v in sorted(ok.items())))
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("arm")
    p.add_argument("--core", default="ucore", choices=("ucore",))
    p.add_argument("--jobs", type=int, default=8)
    p.set_defaults(fn=cmd_arm)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
