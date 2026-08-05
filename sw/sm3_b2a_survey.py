#!/usr/bin/env python3
"""sm3_b2a_survey -- the B2a class, surveyed (ucore_provenance §83.5).

B2a is the 12 seeds on which `ucsim_fuzz` is 1/1 OK -- the ARCHITECTURAL
transaction stream matches the chip exactly -- and only the TIMED per-clock
replay parts.  They are the BIU's real residue.  This prints, per seed, the
GEOMETRY of the first divergent launch: the two sides' rows either side of it,
what each launched, the queue state, the wait axis, and the ARCH model's own
instruction at that point (found through the functional event index, so the
ruler is the same one §84 used and is valid here BY CONSTRUCTION -- these seeds
are arch-exact).

Usage: sm3_b2a_survey.py [--seeds a,b] [--json out.json] [--win 6]
"""
import argparse, gzip, json, sys, tempfile
from collections import Counter
from pathlib import Path
SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
import sm3_tf_law as T                                  # noqa: E402
import timed_fuzz as tf                                 # noqa: E402
import fuzz_classify as fc                              # noqa: E402

B2A = ["mc1/1543", "mc1/2241", "mc1/2512", "mc2/1104", "mc2/2438", "mc2/2648",
       "mc2/3569", "mc2/3805", "t30-raw/428", "t30-raw/508", "t30-raw/563",
       "t30-raw/962"]
COLS = ("t", "bs_early", "ad_addr", "ad_data", "ube_n", "qs", "rd_n", "wr_n")


def row(r):
    d = {}
    for c in COLS:
        d[c] = r.get(c) if c in r else (r.get("t_state") if c == "t" else None)
    return d


def survey(sid, win):
    ent = json.loads(gzip.decompress(T.seed_path(sid).read_bytes()))
    image, g, sha = T.regen(ent)
    chip = ent["chip_rows"]
    n = min(len(chip), 4000)
    with tempfile.TemporaryDirectory(dir=str(Path.home() / ".cache/ucsimt-tmp")) as td:
        sim, err = tf.run_sim(image, ent, n + 40, td)
    # THE REPO'S OWN COLUMN POLICY, not a hand-rolled one: `diff_rows` is what
    # every gate in the tree scores with, so a survey that invents its own
    # comparator is surveying a different question.
    dr = fc.diff_rows(chip, sim, window=n)
    m = dr.n
    bad = dr.rows[0].i if dr.rows else None
    out_rows = {r.i: r for r in dr.rows}
    out = {"seed": sid, "waits": ent.get("waits"), "first_bad": bad,
           "chip_rows": len(chip), "sim_rows": len(sim), "err": err[:200]}
    if bad is None:
        return out
    out["detail"] = ((out_rows[bad].qs_txt or "") + " " +
                     " ".join(out_rows[bad].other)).strip()
    out["window"] = [{"i": i, "chip": row(chip[i]), "sim": row(sim[i]),
                      "diff": ((out_rows[i].qs_txt or "") + " " +
                               " ".join(out_rows[i].other)).strip()
                      if i in out_rows else ""}
                     for i in range(max(0, bad - win), min(m, bad + win + 1))]
    # the two launches, named
    ct = fc.extract_txns(chip[:m])
    st = fc.extract_txns(sim[:m])

    def at(txns, i):
        for t in txns:
            if t["start"] <= i <= t.get("end", t["start"] + 3):
                return t
        return None
    tc, ts = at(ct, bad), at(st, bad)
    out["chip_txn"] = tc and {"kind": fc.KIND[tc["kind"]],
                              "addr": tc["addr"], "start": tc["start"]}
    out["sim_txn"] = ts and {"kind": fc.KIND[ts["kind"]],
                             "addr": ts["addr"], "start": ts["start"]}
    # resync distance
    k = bad
    while k in out_rows:
        k += 1
    out["resync_after"] = k - bad
    out["ndiff"] = len(dr.rows)
    out["flicker_only"] = all(r.flicker for r in dr.rows)
    # the ARCH instruction covering that functional event
    ev = sum(1 for t in ct if t["start"] < bad and fc.KIND[t["kind"]] != "CODE")
    o0 = T.run_arch(image, g.get("fill", 0x90), False, ev + 512)
    il = o0.get("ilog") or []
    at0 = T.arch_txns(o0)
    ii = T.ins_index_of_ev(il, ev)
    if ii is not None:
        out["arch_ins"] = {"i": ii, "cs": il[ii][1], "ip": il[ii][2],
                           "bytes": ["%02x" % b for b in il[ii][3:]]}
        out["arch_prev"] = ["%02x" % b for b in il[ii - 1][3:]] if ii else None
    out["_at0_len"] = len(at0)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default=",".join(B2A))
    ap.add_argument("--json", default="")
    ap.add_argument("--win", type=int, default=5)
    a = ap.parse_args()
    rows = []
    for sid in [s for s in a.seeds.split(",") if s]:
        r = survey(sid, a.win)
        rows.append(r)
        print(f"== {sid}  waits={r['waits']}  first_bad={r['first_bad']} "
              f"resync_after={r.get('resync_after')} ndiff={r.get('ndiff')}")
        print(f"   chip {r.get('chip_txn')}")
        print(f"   sim  {r.get('sim_txn')}")
        print(f"   arch {r.get('arch_ins')}  prev={r.get('arch_prev')}")
        print(f"   detail {r.get('detail')}")
    print("\n== rollup")
    print("resync distance:", Counter(r.get("resync_after") for r in rows))
    print("chip kind:", Counter((r.get("chip_txn") or {}).get("kind")
                                for r in rows))
    print("sim  kind:", Counter((r.get("sim_txn") or {}).get("kind")
                                for r in rows))
    if a.json:
        Path(a.json).write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
