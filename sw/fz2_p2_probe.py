#!/usr/bin/env python3
"""fz2_p2_probe -- READ THE BANKED ROWS around a seed's first divergence.

A DIAGNOSTIC, NOT A GATE.  It prints the socketed chip's bus cycles and the
core's, side by side, over a window around the failure ledger's
`first_bad_row`, with the CODE fetches resolved back to the seed's own image
bytes so the instruction stream is readable.  Nothing here scores anything.

    python3 sw/fz2_p2_probe.py rows  <seed> [--before N] [--after N]
    python3 sw/fz2_p2_probe.py fork  <seed>            # one-line fork summary
    python3 sw/fz2_p2_probe.py survey <seed>...        # the fork line for many
"""
import argparse
import gzip
import hashlib
import json
import os
import sys
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

import fuzz_campaign as fzc                              # noqa: E402
import fz2_w1 as fz                                      # noqa: E402
import sm3_ackgeom as ag                                 # noqa: E402

KIND = {0: "INTA", 1: "IOR ", 2: "IOW ", 3: "HALT",
        4: "CODE", 5: "MEMR", 6: "MEMW", 7: "PASV"}

_LINES = {}


def lines():
    if not _LINES:
        for cid in ("fz2c", "fz2e"):
            for l in open(ROOT / "sw/testdata/campaigns" / cid / "results.jsonl"):
                r = json.loads(l)
                _LINES[r["seed"]] = r
    return _LINES


def ledger():
    d = ROOT / "sw/testdata/fz2"
    p = os.environ.get("FZ2_LEDGER") or str(
        d / sorted(f for f in os.listdir(d)
                   if f.startswith("fz2_failure_ledger") and f.endswith(".json"))[-1])
    return p, {f["seed"]: f for f in json.load(open(p))["failures"]}


def ov_for(cid, k):
    for st in fz.STRATA:
        if st["cid"] == cid and st["k_lo"] <= k < st["k_lo"] + st["n"]:
            return fz.ov_of(st)
    raise KeyError((cid, k))


def load(seed):
    cid, k = seed.split("/")
    k = int(k)
    line = lines()[seed]
    _, led = ledger()
    cfg = fzc.derive_case(cid, k, ov_for(cid, k))
    image, meta = fzc.compose_case(fzc.build(cfg), cfg)
    sha = hashlib.sha256(bytes(image)).hexdigest()
    drift = sha != line["image_sha256"]
    ent = led.get(seed)
    cap = json.load(gzip.open(ent["capture"])) if ent else None
    return dict(cid=cid, k=k, line=line, cfg=cfg, meta=meta, image=bytes(image),
                drift=drift, led=ent, cap=cap)


def bytes_at(image, addr, n=8):
    return image[addr:addr + n]


def cyc_table(rows, image, lo, hi):
    """(row, kind, addr, data, bytes-at-addr) for every cycle whose T1 is in
    [lo, hi)."""
    out = []
    for kind, t1, end, disp in ag.cycles(rows, len(rows)):
        if not (lo <= t1 < hi):
            continue
        r = rows[t1]
        a = r["ad_addr"] & 0xFFFFF
        # AD is the ADDRESS at T1 and DATA from T2 on; by the last retained row
        # the pads may already be driving the next cycle's address, so the
        # sample is T2 (`sm3_tf_floor_cell._d`).
        d = rows[min(t1 + 1, end)]["ad_data"] & 0xFFFF if end is not None else None
        # the images are 64 KB laid out for the 64 KB-mirrored map
        pre = bytes_at(image, a & 0xFFFF, 6).hex() if kind == 4 else ""
        out.append((t1, KIND[kind], a, d, pre))
    return out


def tb_rows(S):
    """Re-run the seed through the receipted `ucore` TB exactly as
    `fz2_c1_rescore.one()` does (same IVT-2 patch, same window)."""
    import check_seq                                      # noqa: PLC0415

    cfg = S["cfg"]
    evts, _, _ = fzc.term_directive(cfg, S["meta"])
    w = cfg["waits"]
    ip, cs = fzc.TERM_TVEC[1], fzc.TERM_TVEC[0]
    b = bytearray(S["image"])
    b[8] = ip & 0xFF
    b[9] = (ip >> 8) & 0xFF
    b[10] = cs & 0xFF
    b[11] = (cs >> 8) & 0xFF
    return check_seq.run_tb(bytes(b), 4200,
                            waits=0 if w["wrand"] else w["fixed"],
                            evt=evts[fzc.TERM_SCHED],
                            wrand=(w["wmax"], w["wseed"]) if w["wrand"] else None,
                            wvec=fzc.wvec_of(cfg), core="ucore")


def cmd_rows(a):
    S = load(a.seed)
    fb = S["led"]["first_bad_row"] if S["led"] else 0
    lo, hi = max(0, fb - a.before), fb + a.after
    print(f"{a.seed}  first_bad {fb}  win {S['line'].get('win')}  "
          f"gen_drift {S['drift']}  family {S['led']['family'] if S['led'] else '-'}")
    ch = cyc_table(S["cap"]["real"], S["image"], lo, hi)
    src = tb_rows(S) if a.tb else S["cap"]["sim"]
    co = cyc_table(src, S["image"], lo, hi)
    print("\n--- CHIP (socket) ---")
    for t1, k, ad, d, pre in ch:
        print(f"  {t1:5d} {k} {ad:05x} <- {d if d is None else format(d,'04x')}  {pre}")
    print("\n--- CORE (%s) ---" % ("live TB" if a.tb else "fabric, banked"))
    for t1, k, ad, d, pre in co:
        print(f"  {t1:5d} {k} {ad:05x} <- {d if d is None else format(d,'04x')}  {pre}")


def vec1_reads(rows, lo=0, hi=10**9):
    """Every IVT read of vector 1 (linear 0x4 / 0x6) -- the trap's own."""
    out = []
    for kind, t1, end, disp in ag.cycles(rows, len(rows)):
        if kind != 5 or not (lo <= t1 < hi):
            continue
        a = rows[t1]["ad_addr"] & 0xFFFFF
        if a in (0x00004, 0x00006):
            out.append((t1, a))
    return out


def cmd_fork(a):
    for seed in a.seeds:
        try:
            S = load(seed)
        except Exception as e:                                # noqa: BLE001
            print(f"{seed}  ERR {str(e)[:80]}")
            continue
        fb = S["led"]["first_bad_row"]
        img = S["image"]
        # the last CODE fetch on the CHIP at or before the fork, and the byte
        # the part would decode there
        ch = ag.cycles(S["cap"]["real"], len(S["cap"]["real"]))
        last_code = None
        for kind, t1, end, disp in ch:
            if t1 > fb + 40:
                break
            if kind == 4:
                last_code = (t1, S["cap"]["real"][t1]["ad_addr"] & 0xFFFFF)
        v1c = vec1_reads(S["cap"]["real"], fb - 200, fb + 400)
        v1o = vec1_reads(S["cap"]["sim"], fb - 200, fb + 400)
        op = ""
        if last_code:
            op = img[last_code[1]:last_code[1] + 2].hex()
        print(f"{seed:14s} fam={S['led']['family'][:30]:30s} fb={fb:5d} "
              f"lastCODE={last_code[1] if last_code else -1:05x}@{last_code[0] if last_code else -1:5d} "
              f"bytes={op}  chipV1={len(v1c)} coreV1={len(v1o)}")


def _trace_lines(seed, nrows=4200):
    import shutil
    import subprocess
    import tempfile

    import check_seq                                      # noqa: PLC0415

    S = load(seed)
    cfg = S["cfg"]
    evts, _, _ = fzc.term_directive(cfg, S["meta"])
    w = cfg["waits"]
    ip, cs = fzc.TERM_TVEC[1], fzc.TERM_TVEC[0]
    b = bytearray(S["image"])
    b[8] = ip & 0xFF
    b[9] = (ip >> 8) & 0xFF
    b[10] = cs & 0xFF
    b[11] = (cs >> 8) & 0xFF
    image = bytes(b) * 16
    td = tempfile.mkdtemp(prefix="p2trace_")
    try:
        img = Path(td) / "img.hex"
        out = Path(td) / "out.txt"
        img.write_text("\n".join(f"{x:02x}" for x in image) + "\n")
        args = [str(check_seq.tb_bin("ucore")), f"+bootimg={img}",
                f"+bootn={nrows}",
                f"+waits={0 if w['wrand'] else w['fixed']}", f"+out={out}",
                "+brktrace"]
        wv = fzc.wvec_of(cfg)
        if wv is not None:
            f = Path(td) / "wvec.hex"
            f.write_text("\n".join(f"{min(255, max(0, int(x))):02x}" for x in wv)
                         + "\n")
            args += [f"+wvec={f}"]
        elif w["wrand"]:
            args += ["+wrand=1", f"+wmax={w['wmax']}", f"+wseed={w['wseed']:04x}"]
        ev = evts[fzc.TERM_SCHED]
        if ev is not None:
            ad, d, ho, p = ev
            args += [f"+evaddr={ad:05x}", f"+evdelay={d}", f"+evhold={ho}",
                     f"+evpin={p}"]
        r = subprocess.run(args, capture_output=True, text=True, cwd=ROOT,
                           timeout=600)
    finally:
        shutil.rmtree(td, ignore_errors=True)
    out = []
    for l in r.stdout.splitlines():
        if l.startswith(("BRKR", "BRKS", "BRKT")):
            try:
                out.append((int(l.split("clk=")[1].split()[0]), l))
            except (IndexError, ValueError):
                pass
    return S, out


def cmd_classify(a):
    """For each seed: the core's BRK events in [fb-60, fb+20], and the chip's
    own vector-1 read after `fb`.  Mechanism A (`no sample at the firing
    boundary`) shows a `BRKT ... arm=0 irq=1` with NO `BRKS` between the last
    `BRKR` and it; mechanism B (`HLT parks over an armed trap`) shows a `BRKS
    seen=1` and then nothing."""
    for seed in a.seeds:
        try:
            S, tr = _trace_lines(seed)
        except Exception as e:                                # noqa: BLE001
            print(f"{seed:14s} ERR {str(e)[:70]}")
            continue
        fb = S["led"]["first_bad_row"]
        fam = S["led"]["family"][:2]
        win = [l for c, l in tr if fb - 70 <= c <= fb + 25]
        rise = [c for c, l in tr if l.startswith("BRKR") and c <= fb + 25]
        last_rise = rise[-1] if rise else None
        after = [(c, l) for c, l in tr
                 if last_rise is not None and c > last_rise and c <= fb + 25]
        kind = "?"
        if after:
            first = after[0][1]
            if first.startswith("BRKT") and "arm=0" in first and "irq=1" in first:
                kind = "A no-sample-at-fire"
            elif first.startswith("BRKS") and "seen=1" in first:
                kind = "B armed-then-parked"
        elif last_rise is not None:
            kind = "B? armed nowhere"
        print(f"{seed:14s} {fam} fb={fb:5d} rise={last_rise} -> {kind}")
        for c, l in after[:3]:
            print(f"        {l}")


def cmd_trace(a):
    """Re-run the seed through the ucore TB with `+brktrace` and print the
    BRKR / BRKS / BRKT lines whose `ce_clk` falls in the window.  `ce_clk` and
    the row index are the same counter (v30u_eu.sv's contract)."""
    import shutil
    import subprocess
    import tempfile

    import check_seq                                      # noqa: PLC0415

    S = load(a.seed)
    fb = S["led"]["first_bad_row"] if S["led"] else 0
    cfg = S["cfg"]
    evts, _, _ = fzc.term_directive(cfg, S["meta"])
    w = cfg["waits"]
    image = S["image"]
    # the same IVT-2 patch fz2_c1_rescore applies
    ip, cs = fzc.TERM_TVEC[1], fzc.TERM_TVEC[0]
    b = bytearray(image)
    b[8] = ip & 0xFF
    b[9] = (ip >> 8) & 0xFF
    b[10] = cs & 0xFF
    b[11] = (cs >> 8) & 0xFF
    image = bytes(b) * 16
    td = tempfile.mkdtemp(prefix="p2trace_")
    try:
        img = Path(td) / "img.hex"
        out = Path(td) / "out.txt"
        img.write_text("\n".join(f"{x:02x}" for x in image) + "\n")
        args = [str(check_seq.tb_bin("ucore")), f"+bootimg={img}", "+bootn=4200",
                f"+waits={0 if w['wrand'] else w['fixed']}", f"+out={out}",
                "+brktrace"]
        wv = fzc.wvec_of(cfg)
        if wv is not None:
            f = Path(td) / "wvec.hex"
            f.write_text("\n".join(f"{min(255, max(0, int(x))):02x}" for x in wv)
                         + "\n")
            args += [f"+wvec={f}"]
        elif w["wrand"]:
            args += ["+wrand=1", f"+wmax={w['wmax']}", f"+wseed={w['wseed']:04x}"]
        ev = evts[fzc.TERM_SCHED]
        if ev is not None:
            ad, d, ho, p = ev
            args += [f"+evaddr={ad:05x}", f"+evdelay={d}", f"+evhold={ho}",
                     f"+evpin={p}"]
        r = subprocess.run(args, capture_output=True, text=True, cwd=ROOT,
                           timeout=600)
    finally:
        shutil.rmtree(td, ignore_errors=True)
    lo, hi = fb - a.before, fb + a.after
    print(f"{a.seed}  first_bad {fb}   window [{lo},{hi})")
    for l in r.stdout.splitlines():
        if not l.startswith(("BRKR", "BRKS", "BRKT", "1BLD")):
            continue
        try:
            clk = int(l.split("clk=")[1].split()[0])
        except (IndexError, ValueError):
            continue
        if lo <= clk < hi:
            print("  " + l)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("rows")
    p.add_argument("seed")
    p.add_argument("--before", type=int, default=120)
    p.add_argument("--after", type=int, default=200)
    p.add_argument("--tb", action="store_true",
                   help="re-run the seed through the receipted ucore TB "
                        "instead of reading the banked fabric leg")
    p.set_defaults(fn=cmd_rows)
    p = sub.add_parser("fork")
    p.add_argument("seeds", nargs="+")
    p.set_defaults(fn=cmd_fork)
    p = sub.add_parser("classify")
    p.add_argument("seeds", nargs="+")
    p.set_defaults(fn=cmd_classify)
    p = sub.add_parser("trace")
    p.add_argument("seed")
    p.add_argument("--before", type=int, default=200)
    p.add_argument("--after", type=int, default=200)
    p.set_defaults(fn=cmd_trace)
    a = ap.parse_args()
    a.fn(a)
