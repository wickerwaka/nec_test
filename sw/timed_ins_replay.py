#!/usr/bin/env python3
"""timed_ins_replay -- the L2 oracle replay: the case250 INS factorial planes
reproduced END-TO-END THROUGH THE TIMED SIMULATOR.

The offline pilot (sw/ins_ucode_pilot.py) reads the FROZEN chip records and
checks its micro-march laws against the chip's own t1/t4/tw.  That proves the
LAWS; it does not prove the MODEL, because the pilot is handed every access's
measured timing.  This harness instead:

  1. regenerates the fuzz program image for the seed (sw/gen_seq.generate +
     sw/check_seq.compose -- offline, no board),
  2. rebuilds the run's per-access wait vector from the recorded LFSR seed
     (the rig's own generator, sw/biu_case165_...wait_vector), applies the
     history permutation and the cell's selected-access wait,
  3. drives `v30sim timed-boot --wvec` from RESET with that vector, and
  4. resolves the same semantic roles the CAPTURE SCRIPT does (by bus kind
     and address) and evaluates the pilot's own predicates on the sim's
     accesses.

So a cell passes only if the simulator put the bus cycles of a ~4000-clock
program where the chip did, closely enough for the target access chain to be
found and the rails to land.  Two verdicts are reported per cell:

  PILOT PARITY  the micro-march laws hold on the SIM's own t1/t4/tw -- the
                form the T2 gate is stated on, directly comparable to
                sw/ins_ucode_pilot.py's 1312/1312 and 782/800.
  vs-CHIP       the STRICT form: each rail's T1 measured from R1's T4 equals
                the frozen chip capture's same difference.  (Absolute clocks
                differ by a constant reset-frame offset, so the anchor is
                subtracted; this is the harder gate and the one that still
                has a residual.)

Usage:
    python3 sw/timed_ins_replay.py                 # all four seeds, both forms
    python3 sw/timed_ins_replay.py --seeds 12302 --roles R1 --waits 0,3,15
"""

import argparse
import json
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

from causal_wrand import accesses                                # noqa: E402
from biu_case165_ins_split_write_factorial import wait_vector    # noqa: E402
import ins_ucode_pilot as pilot                                  # noqa: E402

SIM = ROOT / "sim" / "v30sim"
ROM = ROOT / "docs" / "V20BITS.TXT"

# Straight out of sw/biu_case249_new_ins_factorial.py::CASES -- the capture
# script that produced sw/case250_fz*_factorial.json.  `lfsr` is the run's
# wrand seed, `roles` are BUS-ACCESS ORDINALS from the run's start.
CASES = {
    12302: {"lfsr": 0x85E9, "family": "ALIGNED_IMMEDIATE_INS_OFF2_LEN9",
            "target": 0x02B3C,
            "roles": {"R1": 164, "C1": 165, "C2": 166, "R2": 167, "W1": 168}},
    12466: {"lfsr": 0x8555, "family": "SPLIT_IMMEDIATE_INS_OFF1_LEN7",
            "target": 0x02CCF,
            "roles": {"R1L": 53, "R1H": 54, "C1": 55, "C2": 56,
                      "R2L": 57, "R2H": 58, "W1": 59, "W2": 60}},
    12547: {"lfsr": 0x84E4, "family": "SPLIT_IMMEDIATE_INS_OFF1_LEN8",
            "target": 0x02B79,
            "roles": {"R1L": 47, "R1H": 48, "C1": 49, "C2": 50,
                      "R2L": 51, "R2H": 52, "W1": 53, "W2": 54}},
    12569: {"lfsr": 0x84FE, "family": "ALIGNED_IMMEDIATE_INS_OFF1_LEN7",
            "target": 0x02A70,
            "roles": {"R1": 107, "C1": 108, "R2": 109, "W1": 110}},
}
# geometry, as the pilot names it (off = bit offset, ln = field length)
GEOM = {12302: (2, 9, False), 12466: (1, 7, True),
        12547: (1, 8, True), 12569: (1, 7, False)}


def image_for(seed, _cache={}):
    if seed not in _cache:
        from check_seq import compose
        from gen_seq import generate
        exts = tuple(x for x in (SW / "case31_all_exts.txt").read_text()
                     .strip().split(",") if x)
        _cache[seed] = compose(generate(f"fz{seed}", exts=exts))[0]
    return _cache[seed]


def run_sim(seed, vector, clocks, td):
    img = Path(td) / f"fz{seed}.bin"
    img.write_bytes(image_for(seed))
    wv = Path(td) / "wvec.txt"
    wv.write_text("\n".join(str(x) for x in vector) + "\n")
    r = subprocess.run([str(SIM), "timed-boot", str(ROM), str(img),
                        f"--clocks={clocks}", "--ndjson", f"--wvec={wv}"],
                       capture_output=True)
    rows = [json.loads(l) for l in r.stdout.decode().splitlines()
            if l.startswith("{")]
    return [x for x in rows if "t" in x]   # drop the trailing finals record


def resolve(bus, case, split):
    """The INS roles, resolved the way the CAPTURE SCRIPT resolves them
    (sw/biu_case249_new_ins_factorial.py::resolve): by BUS KIND AND ADDRESS,
    not by ordinal.  The ordinals in CASES select the intervention (which
    wvec entry to overwrite); they are an INPUT, not an identification -- at
    high C1 waits the chip itself reorders R2 ahead of the second prefetch,
    so an ordinal-keyed resolver would call the CHIP unresolvable too."""
    tgt = case["target"]
    # ...but BOUNDED to the intervention's neighbourhood.  The capture script
    # takes "the LAST write to the target" over a 4063-clock capture, which is
    # unambiguous there only because the chip does not reach a second INS to
    # the same address inside the window.  The sim covers more of the program
    # in the same clock budget, so an unbounded search resolves a LATER
    # instruction while the near-window `codes` still name the first.
    lo = min(case["roles"].values()) - 3
    hi = max(case["roles"].values()) + 3
    bus = bus[:hi + 8]
    w1s = [i for i, a in enumerate(bus) if a["bs"] == 6 and a["addr"] == tgt]
    if not w1s:
        return None, "target low write missing"
    w1 = w1s[-1]
    got = {"W1": bus[w1]}
    if split:
        w2s = [i for i, a in enumerate(bus[w1:], w1)
               if a["bs"] == 6 and a["addr"] == tgt + 1]
        if not w2s:
            return None, "target high write missing"
        got["W2"] = bus[w2s[0]]
        reads = [i for i, a in enumerate(bus[:w1])
                 if a["bs"] == 5 and a["addr"] in (tgt, tgt + 1)]
        if len(reads) < 4:
            return None, f"target split reads missing: {reads}"
        for n, i in zip(("R1L", "R1H", "R2L", "R2H"), reads[-4:]):
            got[n] = bus[i]
    else:
        reads = [i for i, a in enumerate(bus[:w1])
                 if a["bs"] == 5 and a["addr"] == tgt]
        if len(reads) < 2:
            return None, f"target reads missing: {reads}"
        got["R1"], got["R2"] = bus[reads[-2]], bus[reads[-1]]
    # the CODE accesses of the near window, as the pilot's `codes` list
    got["_codes"] = [a for a in bus[lo:hi] if a["bs"] == 4]
    return got, None


def cell(seed, role, wait, history, R):
    """The pilot's own cell dict, built from the SIM's resolved accesses."""
    off, ln, split = GEOM[seed]
    return dict(seed=seed, off=off, S=off + ln, split=split, role=role,
                wait=wait, hist=history,
                R1=R["R1H"] if split else R["R1"],
                R2=R["R2H"] if split else R["R2"],
                R1L=R.get("R1L"), R2L=R.get("R2L"),
                W1=R["W1"], W2=R.get("W2"),
                codes=R["_codes"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default=",".join(str(s) for s in CASES))
    ap.add_argument("--roles", default="all")
    ap.add_argument("--waits", default=",".join(str(i) for i in range(16)))
    ap.add_argument("--histories", default="A,B")
    # The chip captures are 4063 CPU clocks and the roles are resolved by
    # "the LAST write to the target", so the sim must be stopped in the same
    # window -- run it longer and a later instruction hijacks the resolution.
    ap.add_argument("--clocks", type=int, default=4063)
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--raw", action="store_true",
                    help="also load the frozen RAW captures and report the "
                         "whole-program bus-stream agreement prefix")
    args = ap.parse_args()

    waits = [int(x, 0) for x in args.waits.split(",") if x]
    hists = [x for x in args.histories.split(",") if x]
    frozen = {}
    for s in CASES:
        p = SW / f"case250_fz{s}_factorial.json"
        if p.exists():
            for rec in json.load(open(p))["records"]:
                frozen[(rec["seed"], rec["history"], rec["role"],
                        rec["wait"])] = rec

    raw = {}
    if args.raw:
        import gzip
        import glob
        for rec in [r for s_ in CASES
                    for r in (json.load(open(SW / f"case250_fz{s_}_"
                                             "factorial.json"))["records"]
                              if (SW / f"case250_fz{s_}_factorial.json"
                                  ).exists() else [])]:
            p_ = ROOT / rec["raw_capture"]
            if p_.exists():
                raw[(rec["seed"], rec["history"], rec["role"],
                     rec["wait"])] = json.load(gzip.open(p_))
        del glob

    r2_bad = []
    tot = Counter()
    per = {}
    with tempfile.TemporaryDirectory() as td:
        for seed in (int(x) for x in args.seeds.split(",") if x):
            case = CASES[seed]
            base = wait_vector(case["lfsr"])
            roles = (tuple(case["roles"]) if args.roles == "all"
                     else tuple(x.strip().upper()
                                for x in args.roles.split(",")))
            s = per.setdefault(seed, Counter())
            for history in hists:
                prepared = list(base)
                if history == "B":
                    prepared[5], prepared[6] = prepared[6], prepared[5]
                for role in roles:
                    if role not in case["roles"]:
                        continue
                    sel = case["roles"][role]
                    for w in waits:
                        vec = list(prepared)
                        vec[sel] = w
                        bus = accesses(run_sim(seed, vec, args.clocks, td))
                        s["cells"] += 1
                        R, why = resolve(bus, case, GEOM[seed][2])
                        if R is None:
                            s["unresolved"] += 1
                            if args.verbose:
                                print(f"  fz{seed} {history} {role} w{w:02d}"
                                      f"  UNRESOLVED: {why}")
                            continue
                        s["resolved"] += 1
                        # (i) the rig delivered the requested Tw
                        if bus[sel]["tw"] != w:
                            s["wait_mismatch"] += 1
                        c = cell(seed, role, w, history, R)
                        # (ii) pilot-parity: the laws hold on the SIM's numbers
                        s["w1"] += (c["W1"]["t1"] == pilot.w1_pred(c))
                        s["w1_n"] += 1
                        if c["W2"]:
                            s["w2"] += (c["W2"]["t1"] == pilot.w2_pred(c))
                            s["w2_n"] += 1
                        p_, a_ = pilot.r2_pred(c)
                        s["r2"] += (a_ == p_)
                        s["r2_n"] += 1
                        if a_ != p_:
                            r2_bad.append((seed, history, role, w, a_ - p_))
                        # (iii) strict: the same rails as the frozen CHIP,
                        # measured relative to R1's T4 so the frames align
                        # (iv) the BUS-STREAM agreement prefix: how many
                        # leading bus cycles of the whole ~4000-clock program
                        # the sim reproduces in kind+address, and how many of
                        # those also land on the same absolute T1 (modulo the
                        # constant reset-frame offset).  This is the honest
                        # whole-program measure, and the T3 input.
                        if raw and (seed, history, role, w) in raw:
                            cb = accesses(raw[(seed, history, role, w)])
                            d = None
                            n_kind = n_clk = 0
                            for x, y in zip(bus, cb):
                                if x["bs"] != y["bs"] or x["addr"] != y["addr"]:
                                    break
                                n_kind += 1
                                if d is None:
                                    d = y["t1"] - x["t1"]
                                if y["t1"] - x["t1"] == d:
                                    n_clk += 1
                                else:
                                    break
                            s["stream_kind"] += n_kind
                            s["stream_clk"] += n_clk
                            s["stream_chip"] += len(cb)
                            s["stream_n"] += 1
                        f = frozen.get((seed, history, role, w))
                        if f:
                            fr, _ = resolve(f["chip_near"], case,
                                            GEOM[seed][2])
                            if fr is None:
                                s["chip_unres"] += 1
                            else:
                                anchor = "R1H" if GEOM[seed][2] else "R1"
                                bs_, bc_ = R[anchor]["t4"], fr[anchor]["t4"]
                                for n in ("W1", "W2", "R2", "R2H", "R2L"):
                                    if n not in fr or n not in R:
                                        continue
                                    s["chip_n"] += 1
                                    s["chip"] += ((R[n]["t1"] - bs_) ==
                                                  (fr[n]["t1"] - bc_))
            tot += s

    print("== L2 replay through the timed sim (case250 INS factorial) ==")
    for seed in sorted(per):
        s = per[seed]
        print(f"  fz{seed}: cells {s['cells']}  resolved {s['resolved']}"
              f"  W1 {s['w1']}/{s['w1_n']}  W2 {s['w2']}/{s['w2_n']}"
              f"  R2issue {s['r2']}/{s['r2_n']}"
              f"  vs-chip {s['chip']}/{s['chip_n']}")
    rails = tot["w1"] + tot["w2"]
    rails_n = tot["w1_n"] + tot["w2_n"]
    print(f"  TOTAL   resolved {tot['resolved']}/{tot['cells']}"
          f"  write rails {rails}/{rails_n}"
          f"  R2-issue {tot['r2']}/{tot['r2_n']}"
          f"  vs-chip rails {tot['chip']}/{tot['chip_n']}")
    if tot["stream_n"]:
        print(f"  bus-stream agreement: kind+addr "
              f"{tot['stream_kind']}/{tot['stream_chip']} leading accesses, "
              f"of which same-T1 {tot['stream_clk']}"
              f"  ({tot['stream_n']} captures)")
    print("  (offline pilot for reference: rails 1312/1312, R2-issue 782/800)")
    if r2_bad:
        print("  R2-issue residual cells (seed, history, role, wait, delta):")
        for x in sorted(r2_bad):
            print("   ", x)
    return 0


if __name__ == "__main__":
    sys.exit(main())
