#!/usr/bin/env python3
"""mc1_survey - rough failure categorization over a campaign's results.jsonl
(task #29 P7). Board-free. Clusters every non-SUCCESS seed into signature
families, characterizes the first-divergence column character from the gzipped
captures, computes the waited-TIMING drift distribution, and emits the survey
markdown. Analysis only - proposes nothing that touches RTL.

    python3 sw/mc1_survey.py mc1 [--out docs/notes/mc1_survey.md]
"""
import argparse
import glob
import gzip
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
import fuzz_classify as fc                                  # noqa: E402
CAMPAIGNS = SW / "testdata" / "campaigns"


def waits_class(r):
    w = r["waits"]
    if w.get("wrand"):
        return f"wr{w.get('wmax')}"
    return "w0" if (w.get("fixed") or 0) == 0 else f"w{w.get('fixed')}"


def norm_sub(s):
    return re.sub(r"\d+", "N", s or "")


def capture_for(cdir, r):
    fs = glob.glob(str(cdir / "captures" /
                       f"{r['tier']}_{r['k']}_{r['cfg_hash']}.json.gz"))
    if not fs:
        return None
    return json.load(gzip.open(fs[0], "rt"))


COLS = {"bus": ("bs_early", "bs_late"), "addr": ("ad_addr",),
        "data": ("ad_data",), "queue": ("qs",), "ctrl": ("rd_n", "lock_n"),
        "tstate": ("t",)}


def first_div_character(cap, first_bad):
    """Which column GROUPS differ at/near first_bad -> the divergence character
    (bus vs arch/addr vs data vs queue-state vs tstate/duration)."""
    if cap is None or first_bad is None:
        return None
    real, sim = cap["real"], cap["sim"]
    if first_bad >= min(len(real), len(sim)):
        return None
    groups = Counter()
    for i in range(first_bad, min(first_bad + 6, len(real), len(sim))):
        for g, cols in COLS.items():
            if any(real[i].get(c) != sim[i].get(c) for c in cols):
                groups[g] += 1
    return groups


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cid")
    ap.add_argument("--out")
    a = ap.parse_args()
    cdir = CAMPAIGNS / a.cid
    rows = [json.loads(l) for l in (cdir / "results.jsonl").read_text().splitlines()
            if l.strip()]
    nonsucc = [r for r in rows if r["verdict"] != "SUCCESS"]

    L = [f"# mc1 survey - rough failure categorization\n\n",
         f"Campaign `{a.cid}`: {len(rows)} seeds, {len(nonsucc)} non-SUCCESS "
         f"({100 * len(nonsucc) / max(1, len(rows)):.0f}%).\n\n"]
    vc = Counter(r["verdict"] for r in rows)
    L.append("Verdicts: " + ", ".join(f"{k}={v}" for k, v in vc.most_common())
             + "\n\n")

    # families: (verdict, normalized sub)
    fam = defaultdict(list)
    for r in nonsucc:
        fam[(r["verdict"], norm_sub(r["sub"]))].append(r)

    L.append("## Signature families (non-SUCCESS)\n\n")
    L.append("| family | n | tiers | waits-classes | first-div character | rep seed |\n")
    L.append("|---|---|---|---|---|---|\n")
    fam_rows = sorted(fam.items(), key=lambda kv: -len(kv[1]))
    char_cache = {}
    for (verdict, sub), rs in fam_rows:
        tiers = Counter(r["tier"] for r in rs)
        wcs = Counter(waits_class(r) for r in rs)
        rep = rs[0]
        # character from up to 3 representatives with captures
        gc = Counter()
        for r in rs[:8]:
            cap = capture_for(cdir, r)
            ch = first_div_character(cap, r.get("first_bad"))
            if ch:
                gc.update(ch)
        char = ", ".join(f"{g}" for g, _ in gc.most_common(3)) or "-"
        char_cache[(verdict, sub)] = char
        tstr = ",".join(f"{k}:{v}" for k, v in tiers.most_common())
        wstr = ",".join(f"{k}:{v}" for k, v in wcs.most_common(4))
        L.append(f"| {verdict}/{sub} | {len(rs)} | {tstr} | {wstr} | {char} "
                 f"| {rep['cid']}/{rep['k']} |\n")

    # waited-TIMING drift distribution (the #1-priority wait-state channel)
    tim = [r for r in nonsucc if r["verdict"] == "TIMING" and r.get("drift")]
    if tim:
        finals = sorted(abs((r["drift"] or {}).get("final", 0)) for r in tim)
        maxsteps = sorted((r["drift"] or {}).get("changepoints") and
                          max((abs(d) for _, d in r["drift"]["changepoints"]),
                              default=0) or 0 for r in tim)
        def pct(a, p):
            return a[min(len(a) - 1, int(p * len(a)))] if a else 0
        L.append("\n## Waited-TIMING drift distribution "
                 f"({len(tim)} surfaced TIMING)\n\n")
        L.append(f"- |final_off| p50={pct(finals,.5)} p90={pct(finals,.9)} "
                 f"p99={pct(finals,.99)} max={finals[-1]}\n")
        L.append(f"- worst changepoint step p50={pct(maxsteps,.5)} "
                 f"p90={pct(maxsteps,.9)} max={maxsteps[-1]}  "
                 f"(cadence floor max_step=9)\n")

    # w0 escalation walk-bys: what strict mode would have STOP'd but
    # accumulate-mode absorbed (w0 = no wrand and fixed==0).
    def is_w0(r):
        w = r["waits"]
        return not w.get("wrand") and (w.get("fixed") or 0) == 0
    w0f = [r for r in nonsucc if is_w0(r) and r["verdict"] == "FUNCTIONAL"]
    w0t = [r for r in nonsucc if is_w0(r) and r["verdict"] == "TIMING"]
    L.append(f"\n## w0 escalation walk-bys (strict-mode STOPs absorbed)\n\n"
             f"- w0 FUNCTIONAL: {len(w0f)}  (reps: "
             + ", ".join(f"{r['cid']}/{r['k']}" for r in w0f[:6]) + ")\n"
             f"- w0 TIMING: {len(w0t)}  (reps: "
             + ", ".join(f"{r['cid']}/{r['k']}" for r in w0t[:6]) + ")\n")

    # wrand budget for the threshold sample
    wrand = [r for r in rows if r["waits"].get("wrand")]
    L.append(f"\n## Wrand threshold sample\n\n- wrand seeds: {len(wrand)} "
             f"(>=500 -> calibration verdict below)\n")

    Path(a.out).write_text("".join(L)) if a.out else print("".join(L))
    if a.out:
        print(f"wrote {a.out} ({len(fam_rows)} families)")


if __name__ == "__main__":
    main()
