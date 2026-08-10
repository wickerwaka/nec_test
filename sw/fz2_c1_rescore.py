#!/usr/bin/env python3
"""fz2_c1_rescore -- THE C1 OFFLINE RESCORE INSTRUMENT (survey fix #3).

WHY IT HAD TO EXIST.  `sw/fz2_a1_rescore.py` is STRUCTURALLY BLIND TO THE `C1`
FAMILY and this is a property of its window, not a bug: its `cut()` ends the
comparison at the chip's first `MEMR` T1 at linear `0x00008`/`0x0000A` at or
after the terminating NMI's assertion -- the read the RIG SUBSTITUTES from its
`TVEC` register (`fuzz_campaign.TERM_TVEC`, `vecsub_en` on `TERM_SCHED` only).
`tb_v30_core` has no `TVEC`, so past that read the two legs would be executing
different code.  MEASURED on `fz2c/400007`: the A1 window is 3,346 rows, the
banked window is 3,736, and the family's whole divergence is at row 3,378.
The A1 instrument reads that seed `bad = 0` before AND after any change.

WHAT THIS ONE DOES INSTEAD, and it is ONE line of difference.  The rig's
substitution is a CONSTANT -- `TERM_TVEC = (0x0000, testimage.TERM_AT)`, the
same CS:IP for every seed in the corpus, applied to the terminating NMI's entry
and to nothing else.  So the substitution is EMULATED IN THE IMAGE: bytes 8..11
(IVT entry 2) are overwritten with that same `IP, CS` pair before the image is
handed to the TB, and the comparison then runs over the seed's OWN BANKED
WINDOW (`results.jsonl`'s `win`), with no cut at all.

THE PATCH IS APPLIED AFTER THE `image_sha256` ASSERTION, never before: the seed
still has to regenerate byte-exact to its banked hash, and the four patched
bytes are a property of the INSTRUMENT.

THREE WAYS IT CAN BE UNFAITHFUL, all of them stated in advance and all of them
IDENTICAL in the before and after legs, so they can hide a gain and can never
manufacture one:
  (a) a seed that reads linear 0x8..0xB as DATA sees four different bytes;
  (b) a seed with a STIMULUS pin event never gets it -- the TB has one
      scheduler and it is spent on the terminator (this is A1's own limit too);
  (c) a seed that WRITES linear 0x8..0xB before the terminator fires scribbles
      the patch, where the rig's register cannot be scribbled.

THE VALIDATION RULE, AND IT IS FIXED BEFORE ANY RTL IS TOUCHED.  A seed is
`SCOREABLE` iff the BEFORE leg's first divergence lands on the value the
FAILURE LEDGER recorded for it chip-vs-FABRIC (`first_bad_row`), or -- for a
seed the ledger does not name -- iff the BEFORE leg is row-clean over its
banked window.  Any other seed is `OUT` and is not counted in either
direction.  That is a falsifiable statement about the replay's fidelity
through the terminating NMI's entry, measured against a number taken on the
board with a different instrument.

NOT A SILICON-MATCH RATE.  Like A1's, it is a DELTA instrument: the same
instrument runs before and after an RTL change and the readable quantity is
which seeds moved.
"""
import gzip, hashlib, json, os, sys
from concurrent.futures import ProcessPoolExecutor
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import check_seq, fuzz_campaign as fzc, fuzz_classify as fc, fz2_w1 as fz
import fz2_ledger as fzl

ROOT = str(__import__("pathlib").Path(__file__).resolve().parent.parent) + "/"
# WAS a hard-coded `fz2_failure_ledger_2026-08-09.json` -- the F13 ledger, i.e.
# the wrong measurement to validate a post-FLASH-#14 replay against.  It now
# defaults to `fz2_ledger.CURRENT` and is overridable with `--ledger PATH`;
# `ledger()` prints the file it read.
LEDGER = None
LINES = {}


def _lines():
    if LINES:
        return LINES
    for cid in ("fz2c", "fz2e"):
        for l in open(ROOT + f"sw/testdata/campaigns/{cid}/results.jsonl"):
            r = json.loads(l)
            LINES[r["seed"]] = r
    return LINES


def ledger():
    d = fzl.load(LEDGER, why="fz2_c1_rescore BEFORE-leg validation")
    return {f["seed"]: f for f in d["failures"]}


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


def patch_ivt2(image):
    """The rig's `TVEC` substitution, emulated in memory.  One constant, the
    same for every seed in the corpus."""
    cs, ip = fzc.TERM_TVEC
    b = bytearray(image)
    b[8] = ip & 0xFF
    b[9] = (ip >> 8) & 0xFF
    b[10] = cs & 0xFF
    b[11] = (cs >> 8) & 0xFF
    return bytes(b)


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
        rows = check_seq.run_tb(patch_ivt2(image), 4200,
                                waits=0 if w["wrand"] else w["fixed"],
                                evt=evts[fzc.TERM_SCHED],
                                wrand=(w["wmax"], w["wseed"]) if w["wrand"] else None,
                                wvec=fzc.wvec_of(cfg), core="ucore")
    except Exception as e:                                    # noqa: BLE001
        return {"seed": seed, "err": str(e)[:120]}
    cap = json.load(gzip.open(path))
    R = cap["real"]
    win = int(line["win"])
    dr = fc.diff_rows(R, rows, window=win)
    bad = [r for r in dr.rows if not r.flicker]
    return {"seed": seed, "win": dr.n, "bad": len(bad),
            "first": bad[0].i if bad else None,
            "sig": (bad[0].qs_txt or ";".join(bad[0].other)) if bad else None}


def scoreable(res, led):
    """The validation rule of the module docstring, applied to a BEFORE leg."""
    ok, out = [], []
    for r in res:
        s = r["seed"]
        if r.get("err"):
            out.append((s, "err:" + r["err"]))
            continue
        want = led[s]["first_bad_row"] if s in led else None
        got = r["first"]
        if want == got:
            ok.append(s)
        else:
            out.append((s, f"ledger={want} tb={got}"))
    return ok, out


if __name__ == "__main__":
    argv = sys.argv[1:]
    if "--ledger" in argv:
        i = argv.index("--ledger")
        LEDGER = argv[i + 1]
        del argv[i:i + 2]
    out = argv[0]
    only = set(argv[1:])
    jobs = [j for j in caps() if not only or f"{j[0]}/{j[1]}" in only]
    print(f"{len(jobs)} captures  ->  {out}", flush=True)
    res = []
    with ProcessPoolExecutor(max_workers=6) as ex:
        for i, r in enumerate(ex.map(one, jobs)):
            res.append(r)
            if (i + 1) % 100 == 0:
                print(f"  {i+1}/{len(jobs)}", flush=True)
    json.dump(res, open(out, "w"))
    clean = sum(1 for r in res if r.get("bad") == 0)
    err = sum(1 for r in res if r.get("err"))
    ok, bad = scoreable(res, ledger())
    print(f"CLEAN {clean} / {len(res)}   errors {err}")
    print(f"SCOREABLE (BEFORE-leg validation) {len(ok)} / {len(res)}")
    import artifact as art                                    # noqa: PLC0415
    print("  DUT " + str(check_seq.tb_bin("ucore")) + "  receipt "
          + str(art.receipt_id(check_seq.tb_bin("ucore")))[:16] + "…")
