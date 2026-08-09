#!/usr/bin/env python3
"""AMENDMENT A-2's control: the `ps3_8080` comparator decision, re-runnable.

Finding O-1 is that `fuzz_campaign._ps3_8080`, asked of BOTH board legs as
pre-registration §3.4 registers it, fires on every board capture -- because a
`CODE` T1's `ps` column is the STATUS nibble on the SOCKET leg but the ADDRESS
nibble A19-16 on the FABRIC-CORE leg, and the reset fetch at 0xFFFF0 is in
every capture by construction.

This tool measures the two candidate forms against each other on the two
populations that can decide between them, and asserts the falsifier the
coordinator registered: whichever form is chosen must still return True on a
seed that GENUINELY enters 8080 mode.

  CONTROL   382 archived board capture pairs -- `wr1` (380, v1 era) plus
            `fz2c-prereg-A1-archive` (2, v2 era), both tiers.  No seed in it is
            known to enter 8080 mode on both legs, so a leg that fires here and
            nowhere else is firing on the instrument.

  FALSIFIER the `t30-brkem` bank (116 pairs) -- `timed_fuzz.native_exclusion`'s
            own 8080 population, which it short-circuits by `cid`.  This is
            where true positives exist.

It is a MEASUREMENT TOOL and a falsifier, not a standing gate.  It reads only
checked-in captures; it touches no board and builds nothing.

    python3 sw/fz2_a2_replay.py
"""
import glob
import gzip
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CAMP = ROOT / "sw" / "testdata" / "campaigns"


def _load(p):
    with gzip.open(p) as f:
        return json.loads(f.read())


def _win(d, recs):
    w = (d.get("line") or {}).get("win")
    return min(w, len(recs)) if isinstance(w, int) and w > 0 else len(recs)


def _fire(recs, win, tstate, code_only=True):
    """First row matching the form, or None.  `code_only` off is the form
    WITHOUT the `CODE` term, kept so the tool can show what that term is
    actually buying."""
    for i, r in enumerate(recs[:win]):
        if r.get("t_state", r.get("t")) != tstate:
            continue
        if code_only and r.get("bs_early") != 4:
            continue
        if int(r.get("ps", 0)) & 8:
            return i, r
    return None


FORMS = {"T1+CODE": (1, True), "T2+CODE": (2, True),
         "T1 any-cycle": (1, False), "T2 any-cycle": (2, False)}
LEG = {"real": "socket (use_core=0)", "sim": "fabric core (use_core=1)"}


def measure(paths):
    hit = {(leg, f): set() for leg in LEG for f in FORMS}
    row = {}
    for p in paths:
        nm = pathlib.Path(p).name
        d = _load(p)
        for leg in LEG:
            recs = d.get(leg) or []
            if not recs:
                continue
            w = _win(d, recs)
            for f, (ts, co) in FORMS.items():
                r = _fire(recs, w, ts, co)
                if r:
                    hit[(leg, f)].add(nm)
                    row[(nm, leg, f)] = r
    return hit, row


def report(label, paths):
    print(f"\n{'='*76}\n{label}  --  n = {len(paths)} capture pairs\n{'='*76}")
    hit, row = measure(paths)
    n = len(paths)
    print(f"  {'leg':22s} " + "".join(f"{f:>16s}" for f in FORMS))
    for leg in LEG:
        print(f"  {LEG[leg]:22s} "
              + "".join(f"{len(hit[(leg,f)]):>10d}/{n:<5d}" for f in FORMS))

    a, b = hit[("real", "T1+CODE")], hit[("real", "T2+CODE")]
    same = a == b
    print(f"\n  SOCKET leg, T1 vs T2 : identical set = {same}  "
          f"(T1-only {len(a-b)}, T2-only {len(b-a)})")
    if same and a:
        off = {row[(nm, 'real', 'T2+CODE')][0] - row[(nm, 'real', 'T1+CODE')][0]
               for nm in a}
        print(f"                         first-firing row offset T2-T1 = "
              f"{sorted(off)} over all {len(a)}")

    for ts in (1, 2):
        for leg in LEG:
            any_ = hit[(leg, f"T{ts} any-cycle")]
            code = hit[(leg, f"T{ts}+CODE")]
            extra = sorted(any_ - code)
            print(f"  what `CODE` removes at T{ts}, {LEG[leg]:22s}: "
                  f"{len(extra)} {extra[:3]}")

    ca, cb = hit[("real", "T2+CODE")], hit[("sim", "T2+CODE")]
    print(f"\n  T2+CODE, socket vs core: both {len(ca&cb)}, "
          f"socket-only {len(ca-cb)}, core-only {len(cb-ca)}")
    return hit


def main():
    wr1 = sorted(glob.glob(str(CAMP / "wr1" / "captures" / "*.json.gz")))
    fz2c = sorted(glob.glob(
        str(CAMP / "fz2c-prereg-A1-archive" / "captures" / "*.json.gz")))
    brk = sorted(glob.glob(str(CAMP / "t30-brkem" / "captures" / "*.json.gz")))
    ctrl = wr1 + fz2c
    print(f"CONTROL   = wr1 {len(wr1)} + fz2c {len(fz2c)} = {len(ctrl)}")
    print(f"FALSIFIER = t30-brkem {len(brk)}")

    c = report("CONTROL: archived board capture pairs, no known 8080 entry",
               ctrl)
    f = report("FALSIFIER: t30-brkem, where 8080 entry EXISTS", brk)

    nb = len(brk)
    print(f"\n{'='*76}\nTHE FALSIFIER\n{'='*76}")
    print("  A predicate that no longer detects 8080 entry is not a fix, it is"
          "\n  a deletion.  On the t30-brkem bank each candidate must fire.\n")
    checks = []
    sock_t1 = len(f[("real", "T1+CODE")])
    sock_t2 = len(f[("real", "T2+CODE")])
    core_t1 = len(f[("sim", "T1+CODE")])
    core_t2 = len(f[("sim", "T2+CODE")])
    print(f"  socket T1+CODE (A-2's CHOSEN form) : {sock_t1}/{nb}")
    print(f"  socket T2+CODE                     : {sock_t2}/{nb}")
    print(f"  core   T1+CODE                     : {core_t1}/{nb}"
          "   <- O-1's artifact, fires on everything")
    print(f"  core   T2+CODE                     : {core_t2}/{nb}"
          "   <- detects NOTHING")
    checks.append(("the chosen socket-leg form still detects 8080 entry",
                   sock_t1 > 0))
    checks.append(("socket T1 and socket T2 are the same predicate here",
                   f[("real", "T1+CODE")] == f[("real", "T2+CODE")]))
    checks.append(("the core leg at T2 detects NO 8080 entry, so keeping it "
                   "would be a false-positive-only clause", core_t2 == 0))
    checks.append(("O-1 reproduces: the core leg at T1 fires on every "
                   "control pair", len(c[("sim", "T1+CODE")]) == len(ctrl)))
    checks.append(("a T2 sample does NOT close O-1 on the control",
                   len(c[("sim", "T2+CODE")]) > 0))

    print()
    bad = 0
    for what, ok in checks:
        print(f"  {'ok  ' if ok else 'FAIL'} {what}")
        bad += not ok
    print(f"\n{'PASS' if not bad else 'FAIL'}: {bad} failure(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
