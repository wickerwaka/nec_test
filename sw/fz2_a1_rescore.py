#!/usr/bin/env python3
"""fz2_a1_rescore -- THE A1 OFFLINE RESCORE INSTRUMENT (prereg `docs/notes/fz2_a1_prereg_2026-08-10.md` sec.4).

WHAT IT IS.  For every RETAINED fz2 capture (725), regenerate the seed's own
image through the campaign's own generator (image sha256 ASSERTED against the
banked result line), replay it on the TREE's receipted `--core ucore`
`tb_v30_core` binary with the campaign's own wait source AND the campaign's own
TERMINATING NMI armed on the TB's single scheduler, and compare the resulting
rows against the BANKED SOCKET (chip) rows with `fuzz_classify.diff_rows`.

THE WINDOW, and it is a RULE fixed in advance, not a choice made after seeing a
result.  The TB has ONE event scheduler and NO TVEC vector-substitution
overlay, so it is a faithful replay of the board only up to two points:
  (a) the first row at which the chip reads the SUBSTITUTED NMI vector
      (a `MEMR` T1 at linear 0x00008 / 0x0000A) -- past it the two legs are
      executing different code by construction;
  (b) the first row at which the seed's STIMULUS pin event asserts (a run in
      the banked `term.hold_rows` that is not the terminator's own), which the
      TB cannot arm beside the terminator.
The comparison window is `min(banked win, (a), (b))`.  Everything past it is
INSTRUMENT, not core, and is not scored.

NOT A SILICON-MATCH RATE.  It is a DELTA instrument: the same instrument runs
before and after an RTL change and the readable quantity is which seeds moved.
"""
import gzip, hashlib, json, os, sys
from concurrent.futures import ProcessPoolExecutor
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import check_seq, fuzz_campaign as fzc, fuzz_classify as fc, fz2_w1 as fz

ROOT = str(__import__("pathlib").Path(__file__).resolve().parent.parent) + "/"
LINES = {}

def _lines():
    if LINES: return LINES
    for cid in ("fz2c", "fz2e"):
        for l in open(ROOT + f"sw/testdata/campaigns/{cid}/results.jsonl"):
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
        d = ROOT + f"sw/testdata/campaigns/{cid}/captures"
        for f in sorted(os.listdir(d)):
            out.append((cid, int(f.split("_")[1]), os.path.join(d, f)))
    return out

def cut(R, line):
    """The comparison window -- ERRATUM E-1, prereg sec.E-1, applied to BOTH
    legs and with the baseline RE-MEASURED under it.

    The cut is the point at which the TB stops being a faithful replay of the
    board, and there is exactly ONE such point: the chip's first read of the
    vector the rig SUBSTITUTES, which is a `MEMR` T1 at linear 0x00008/0x0000A
    AT OR AFTER THE TERMINATING NMI'S OWN ASSERTION ROW.  The `at or after`
    clause is the erratum: a raw seed is 64 K of random bytes and legitimately
    READS ADDRESS 8 AS DATA long before the terminator exists, and the first
    form cut six seeds' windows at such a read (`fz2e/518065` at row 1,593).

    THE STIMULUS-EVENT CUT IS REMOVED, and its removal is CONSERVATIVE.  The
    TB has one scheduler and must spend it on the terminator, so a seed whose
    stimulus event matters diverges -- and that divergence is IDENTICAL in the
    before and after legs, so it can only ever hide a gain, never manufacture
    one.  Cutting at the assertion row instead threw away six windows on the
    mere possibility (`fz2c/409066` at row 156, whose scored divergence is at
    3,321 and whose replay is exact to that row)."""
    w = int(line["win"])
    hr = line.get("term", {}).get("hold_rows") or {}
    nmi_runs = hr.get("pin_nmi") or []
    term_at = nmi_runs[-1][0] if nmi_runs else 0
    for i in range(term_at, min(w, len(R))):
        x = R[i]
        if fc._tstate(x) == 1 and x["bs_early"] == 5 and \
           (x["ad_addr"] & 0xFFFFF) in (0x00008, 0x0000A):
            w = i; break
    return max(0, w)

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
        w = cfg["waits"]
        rows = check_seq.run_tb(image, 4200,
                                waits=0 if w["wrand"] else w["fixed"],
                                evt=evts[fzc.TERM_SCHED],
                                wrand=(w["wmax"], w["wseed"]) if w["wrand"] else None,
                                wvec=fzc.wvec_of(cfg), core="ucore")
    except Exception as e:                                    # noqa: BLE001
        return {"seed": seed, "err": str(e)[:120]}
    cap = json.load(gzip.open(path))
    R = cap["real"]
    win = cut(R, line)
    dr = fc.diff_rows(R, rows, window=win)
    bad = [r for r in dr.rows if not r.flicker]
    return {"seed": seed, "win": dr.n, "bad": len(bad),
            "first": bad[0].i if bad else None,
            "sig": (bad[0].qs_txt or ";".join(bad[0].other)) if bad else None}

if __name__ == "__main__":
    out = sys.argv[1]
    jobs = caps()
    print(f"{len(jobs)} retained captures  ->  {out}", flush=True)
    res = []
    with ProcessPoolExecutor(max_workers=6) as ex:
        for i, r in enumerate(ex.map(one, jobs)):
            res.append(r)
            if (i + 1) % 100 == 0:
                print(f"  {i+1}/{len(jobs)}", flush=True)
    json.dump(res, open(out, "w"))
    clean = sum(1 for r in res if r.get("bad") == 0)
    err = sum(1 for r in res if r.get("err"))
    print(f"CLEAN {clean} / {len(res)}   errors {err}")
    import artifact as art                                    # noqa: PLC0415
    print("  DUT " + str(check_seq.tb_bin("ucore")) + "  receipt "
          + str(art.receipt_id(check_seq.tb_bin("ucore")))[:16] + "\u2026")
