#!/usr/bin/env python3
"""fz2_c2_rescore -- THE STIMULUS-ARMED OFFLINE RESCORE INSTRUMENT.

WHY IT EXISTS, and it is not a duplicate of `sw/fz2_a1_rescore.py`.
`tb_v30_core` has ONE pin-event scheduler.  The board rig has three, and every
fz2 capture uses at least two of them: the seed's own STIMULUS event (scheduler
0) and the campaign's TERMINATING NMI (scheduler `TERM_SCHED`).  `fz2_a1_rescore`
spends the TB's single scheduler on the TERMINATOR, which is right for a family
whose mechanism is reached without a pin -- and it means **the stimulus pin is
never asserted there, so a family whose whole mechanism IS that pin is
invisible to it.**  369 of the 725 retained captures carry a stimulus event
(252 on INT, 117 on NMI); this instrument spends the scheduler on THAT event
and stops before the terminator exists.

THE WINDOW, and it is a RULE FIXED IN ADVANCE.  The comparison window is

    min( the banked `win`, the TERMINATING NMI's own assertion row )

taken from the banked line's `term.hold_rows.pin_nmi[-1][0]` -- the last NMI
run in the capture is the terminator by construction (`fuzz_campaign`
`term_directive` puts it on `TERM_SCHED` and it is the last event of the run).
Past that row the TB has no terminator armed and is not a replay of the board.
Everything past the cut is INSTRUMENT, not core, and is not scored.

NOT A SILICON-MATCH RATE.  Like `fz2_a1_rescore` it is a DELTA instrument: the
same instrument runs before and after an RTL change and the readable quantity
is WHICH SEEDS MOVED.  The absolute `bad` counts are smaller than the banked
ones because the window is shorter, and they are not comparable to the corpus
bars.

    python3 sw/fz2_c2_rescore.py OUT.json [--seeds a,b,c] [--jobs N]
"""
import gzip
import hashlib
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

import check_seq                                        # noqa: E402
import fuzz_campaign as fzc                             # noqa: E402
import fuzz_classify as fc                              # noqa: E402
import fz2_w1 as fz                                     # noqa: E402

LINES = {}


def _lines():
    if LINES:
        return LINES
    for cid in ("fz2c", "fz2e"):
        for l in open(ROOT / f"sw/testdata/campaigns/{cid}/results.jsonl"):
            r = json.loads(l)
            LINES[r["seed"]] = r
    return LINES


def ov_for(cid, k):
    for st in fz.STRATA:
        if st["cid"] == cid and st["k_lo"] <= k < st["k_lo"] + st["n"]:
            return fz.ov_of(st)
    raise KeyError((cid, k))


def caps():
    out = []
    for cid in ("fz2c", "fz2e"):
        d = ROOT / f"sw/testdata/campaigns/{cid}/captures"
        if not d.is_dir():
            continue
        for f in sorted(os.listdir(d)):
            out.append((cid, int(f.split("_")[1]), str(d / f)))
    return out


def cut(line, nrows):
    """The comparison window -- the banked window, truncated at the
    TERMINATING NMI's own assertion row."""
    w = int(line["win"])
    hr = (line.get("term") or {}).get("hold_rows") or {}
    runs = hr.get("pin_nmi") or []
    if runs:
        w = min(w, int(runs[-1][0]))
    return max(0, min(w, nrows))


def one(job):
    cid, k, path = job
    seed = f"{cid}/{k}"
    line = _lines()[seed]
    try:
        cfg = fzc.derive_case(cid, k, ov_for(cid, k))
        image, meta = fzc.compose_case(fzc.build(cfg), cfg)
        sha = hashlib.sha256(bytes(image)).hexdigest()
        if sha != line["image_sha256"]:
            return {"seed": seed, "err": "GEN_DRIFT"}
        evts, _, _ = fzc.term_directive(cfg, meta)
        stim = evts[0]                       # scheduler 0 -- the SEED's event
        w = cfg["waits"]
        rows = check_seq.run_tb(image, 4200,
                                waits=0 if w["wrand"] else w["fixed"],
                                evt=stim,
                                wrand=(w["wmax"], w["wseed"]) if w["wrand"] else None,
                                wvec=fzc.wvec_of(cfg), core="ucore")
    except Exception as e:                                    # noqa: BLE001
        return {"seed": seed, "err": str(e)[:120]}
    R = json.load(gzip.open(path))["real"]
    win = cut(line, min(len(R), len(rows)))
    dr = fc.diff_rows(R, rows, window=win)
    bad = [r for r in dr.rows if not r.flicker]
    return {"seed": seed, "stim": stim, "win": dr.n, "bad": len(bad),
            "first": bad[0].i if bad else None,
            "sig": (bad[0].qs_txt or ";".join(bad[0].other)) if bad else None}


def main():
    out = sys.argv[1]
    sel = None
    jobs_n = 6
    a = sys.argv[2:]
    while a:
        if a[0] == "--seeds":
            sel = set(a[1].split(",")); a = a[2:]
        elif a[0] == "--jobs":
            jobs_n = int(a[1]); a = a[2:]
        else:
            raise SystemExit(f"unknown arg {a[0]}")
    jobs = [j for j in caps() if sel is None or f"{j[0]}/{j[1]}" in sel]
    print(f"{len(jobs)} captures  ->  {out}", flush=True)
    res = []
    with ProcessPoolExecutor(max_workers=jobs_n) as ex:
        for i, r in enumerate(ex.map(one, jobs)):
            res.append(r)
            if (i + 1) % 50 == 0:
                print(f"  {i+1}/{len(jobs)}", flush=True)
    json.dump(res, open(out, "w"))
    clean = sum(1 for r in res if r.get("bad") == 0)
    err = sum(1 for r in res if r.get("err"))
    print(f"CLEAN {clean} / {len(res)}   errors {err}")
    import artifact as art                                    # noqa: PLC0415
    print("  DUT " + str(check_seq.tb_bin("ucore")) + "  receipt "
          + str(art.receipt_id(check_seq.tb_bin("ucore")))[:16] + "…")


if __name__ == "__main__":
    main()
