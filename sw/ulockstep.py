#!/usr/bin/env python3
"""ulockstep - the ucore campaign's standing bring-up instrument.

Runs the SAME stimulus through the reference model and through the ucore RTL
and diffs the raw per-clock `r` records CLOCK FOR CLOCK, reporting the first
divergent clock with +/-8 clocks of context.

    sim leg   `sim/v30sim biu-script <script>`   (the BIU alone -- no EU on
              either side; see sim/biu_script.cpp for the grammar)
    RTL leg   `hdl/tb/obj_dir_ucore/Vtb_v30_core +scr=<script>`  (the TB's
              engine-neutral scripted-consumer mode)

Governance (hdl/rtl/ucore/README.md): the model is the SPEC.  A divergence
reported here is a bug in the RTL.

COLUMN POLICY -- check_core's, verbatim, and nothing new.  sw/check_core.py's
`diff_rows` compares the bus/data columns only on rows where the pins are
DRIVEN: "cols pins/seg/mem/io/ube/status/tstate/qop/qbyte compared on every
row; col1 (bus) and col6 (data) compared on T1/T2/T3/Tw rows and on T4/Ti rows
that carry a committed next cycle.  Idle-row bus values are float retention of
pre-window history and are not reproducible from an injected start."  The two
legs prime that retention differently BY CONSTRUCTION -- the model replays the
pre-window fetch ADDRESS sequence (`queue_preload`, T0 open item 3) while the
RTL is handed a backdoor state with no history -- so the same rule applies here:

    every row          t, bs, qs, ube_n
    driven rows only   ad_data, ps        (T1/T2/T3/Tw, or bs != PASV)
    address rows only  ad_addr            (T1, or Ti/T4 with bs != PASV)

`ad_addr` is the MID-clock sample and is an ADDRESS only in those places; on a
T2/T3/Tw row of a read the composed bus is whatever the MEMORY drives.

Attribution: `+utrace` on the RTL leg dumps one `u` row per clock (the stall
causes and the eval/QS strobes) next to the `r` rows; V30SIM_EVALTRACE=1 is the
model's own equivalent (`ET`/`QT` lines on stderr).  `--utrace` turns both on
and prints them alongside the context window.

BATCH MODE over the GOLDEN CORPUS (U2 pass 6, the instrument's missing leg).
The scripted scenarios exercise the BIU ALONE; `--golden` runs whole CASES from
a suite directory through BOTH ENGINES -- the model (`v30sim timed-run`) and the
ucore RTL (the TB's `+batch` consumer) -- from the SAME backdoor injection, and
diffs the raw `r` records clock for clock.  The two legs emit the same record
format (sw/check_core.py::parse_out), so no golden is involved: this is a
MODEL-vs-RTL comparison, which is what `check_core` (RTL-vs-golden) and
`timed_gate` (model-vs-golden) cannot see between them -- a column BOTH of them
mask can still differ, and a case both of them pass can still differ off-window.

Governance is unchanged: the model is the SPEC and a divergence here is an RTL
bug -- EXCEPT on the recognition columns of an `evt` case, where the model
REPLAYS (F34 / C5, pin_replay.h) and the GOLDEN is the gate.

Usage:
    ulockstep.py <script>...            diff each script
    ulockstep.py --suite               the built-in stage-U1 bring-up set
    ulockstep.py --waits 0,1,2,3 ...   run each script at each wait level
    ulockstep.py --golden 88,A4,INT.9D [--cases N] [--waits 0]
    ulockstep.py --golden all --cases 5
"""

import argparse
import gzip
import json
import subprocess
import sys
import tempfile
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))
import check_core                                        # noqa: E402
import simbin                                          # noqa: E402

# U1: the C++ model THROUGH THE ARTIFACT/RECEIPT LAYER.  `simbin.SIM` is
# `sim/build/v30sim`, the binary `simbin.recipe()` declares; nothing here
# resolves the model by bare path any more.  See sw/simbin.py.
SIM = simbin.SIM
ROM = ROOT / "docs" / "V20BITS.TXT"
UBIN = ROOT / "hdl" / "tb" / "obj_dir_ucore" / "Vtb_v30_core"

T_STR = {0: "Ti", 1: "T1", 2: "T2", 3: "T3", 4: "Tw", 5: "T4"}
BUS_STR = {0: "INTA", 1: "IOR", 2: "IOW", 3: "HALT",
           4: "CODE", 5: "MEMR", 6: "MEMW", 7: "PASV"}
Q_STR = {0: "-", 1: "F", 2: "E", 3: "S"}

FIELDS = ["t", "bs", "qs", "ube_n"]


def parse_rows(text):
    out = []
    for line in text.splitlines():
        p = line.split()
        if p and p[0] == "r":
            out.append({"t": int(p[1]), "bs": int(p[2]), "qs": int(p[3]),
                        "ube_n": int(p[4]), "ad_addr": int(p[5], 16),
                        "ad_data": int(p[6], 16), "ps": int(p[7], 16)})
    return out


def run_sim(script):
    r = subprocess.run([str(SIM), "biu-script", str(script)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"sim leg failed: {r.stdout}\n{r.stderr}")
    return parse_rows(r.stdout)


def run_rtl(script, utrace=False):
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "out.txt"
        args = [str(UBIN), f"+scr={script}", f"+out={out}"]
        if utrace:
            args.append("+utrace")
        r = subprocess.run(args, capture_output=True, text=True)
        if "SCRIPT DONE" not in r.stdout:
            sys.exit(f"rtl leg failed: {r.stdout}\n{r.stderr}")
        if utrace:
            for ln in r.stdout.splitlines():
                if ln.startswith("u "):
                    print("    " + ln)
        return parse_rows(out.read_text())


def fmt(row):
    if row is None:
        return "        (no row)"
    return (f"{T_STR.get(row['t'], '??'):>2} {BUS_STR[row['bs']]:>4} "
            f"{Q_STR[row['qs']]} ube={row['ube_n']} "
            f"a={row['ad_addr']:05x} d={row['ad_data']:04x} ps={row['ps']:x}")


def cmp_row(a, b):
    """-> list of differing field names, under the documented column policy."""
    bad = [f for f in FIELDS if a[f] != b[f]]
    driven = a["t"] in (1, 2, 3, 4) or a["bs"] != 7
    if driven:
        for f in ("ad_data", "ps"):
            if a[f] != b[f]:
                bad.append(f)
        if (a["t"] == 1 or a["t"] in (0, 5)) and a["ad_addr"] != b["ad_addr"]:
            bad.append("ad_addr")
    return bad


def diff(name, sim, rtl, ctx=8):
    n = min(len(sim), len(rtl))
    first = None
    nbad = 0
    for i in range(n):
        bad = cmp_row(sim[i], rtl[i])
        if bad:
            nbad += 1
            if first is None:
                first = (i, bad)
    lenmm = len(sim) != len(rtl)
    if first is None and not lenmm:
        print(f"  {name}: LOCKSTEP {n} clocks")
        return True
    if first is None:
        print(f"  {name}: rows agree over {n} clocks but LENGTH differs "
              f"(sim {len(sim)}, rtl {len(rtl)})")
        return False
    i, bad = first
    print(f"  {name}: DIVERGES at clock {i} ({nbad}/{n} clocks differ), "
          f"fields {','.join(bad)}")
    lo, hi = max(0, i - ctx), min(n, i + ctx + 1)
    print(f"      clk | {'sim':<38} | rtl")
    for k in range(lo, hi):
        mark = "<<" if cmp_row(sim[k], rtl[k]) else "  "
        print(f"    {k:5d} | {fmt(sim[k]):<38} | {fmt(rtl[k])} {mark}")
    return False


#---------------------------------------------------------------------------
# The stage-U1 bring-up set.  Each scenario is one script; `--waits` sweeps
# the eval instant over it (M2r: at w0 the eval sits at T3, at w>0 at T4, and
# every landing window is a fixed offset from it).
#---------------------------------------------------------------------------
NOPS = "\n".join(f"mem {0x10000 + i:05x} {(0x90 if i % 2 else 0xB8):02x}"
                 for i in range(64))

SUITE = {
    # the prefetcher free-running from an empty queue: the fetch scheduler,
    # the refill threshold (M4/M7), the landing block (M6) and the queue
    # filling to 6 with nothing consuming it
    "fill-from-empty": """
cs 1000
ip 0000
q 0
ops
w 40
end
""",
    # a byte consumed every clock: the pop is byte-limited, so every pop rides
    # its deliverer's e+3 (M3's latency pipeline) and the scheduler resumes as
    # soon as the threshold allows (M7/M7b)
    "starved-pops": """
cs 1000
ip 0000
q 0
ops
w 2
f s s s s s s s s s s s s s s s s s s s
end
""",
    # a FULL injected queue then a burst of pops: the M4/M7 resume decision is
    # taken with the queue draining under the threshold
    "preloaded-drain": """
cs 1000
ip 0000
q 6 b8 90 b8 90 b8 90
ops
f s s s s s
w 20
end
""",
    # pops paced one every three clocks: the demand, not the byte, is the
    # binding deadline (M8's max) and the queue stays near the threshold
    "paced-pops": """
cs 1000
ip 0000
q 4 b8 90 b8 90
ops
f w 3 s w 3 s w 3 s w 3 s w 3 s w 3 s w 3 s
end
""",
    # an ODD fetch pointer: the single upper-lane byte fetch (+1) and the
    # even/odd alternation of the fetch width
    "odd-base": """
cs 1000
ip 0001
q 0
ops
w 8
f s s s s s s s
end
""",
    # FLUSH while a fetch is in flight: F1's parked QS=E, F3's flush-only T4
    # eval point, M12's latch invalidation and M19's standing request
    "flush-inflight": """
cs 1000
ip 0000
q 2 b8 90
ops
f s
e 1000 0020
w 24
end
""",
    # FLUSH on an idle bus: the E takes the port at once and the redirect
    # commits at the end of the flush clock (M12)
    "flush-idle": """
cs 1000
ip 0000
q 6 b8 90 b8 90 b8 90
ops
f s s s s s
w 12
e 1000 0040
w 20
end
""",
    # two flushes back to back: the second lands while the first redirect is
    # still in flight (the doomed-fetch path, both sides of the announcement)
    "flush-double": """
cs 1000
ip 0000
q 2 b8 90
ops
f s
e 1000 0020
w 3
e 1000 0060
w 24
end
""",
}


def write_suite(td, waits):
    out = []
    for name, body in SUITE.items():
        text = f"waits {waits:x}\nfill 90\n{NOPS}\n" + body.strip() + "\n"
        p = Path(td) / f"{name}_w{waits}.scr"
        p.write_text(text)
        out.append((f"{name} w{waits}", p))
    return out


#---------------------------------------------------------------------------
# BATCH MODE: whole golden CASES through both engines
#---------------------------------------------------------------------------
def _recs_to_rows(recs):
    """parse_out's record dicts -> this module's row dicts (same fields)."""
    return [{"t": r["t"], "bs": r["bs_early"], "qs": r["qs"],
             "ube_n": r["ube_n"], "ad_addr": r["ad_addr"],
             "ad_data": r["ad_data"], "ps": r["ps"]} for r in recs]


def run_model_batch(cases, waits):
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "rows.txt"
        with open(out, "wb") as fo:
            r = subprocess.run([str(SIM), "timed-run", str(ROM),
                                f"--waits={waits}"],
                               input=json.dumps(cases).encode(), stdout=fo)
        if r.returncode != 0:
            sys.exit(f"model leg exited {r.returncode}")
        return check_core.parse_out(out)


def run_rtl_batch(cases, waits):
    with tempfile.TemporaryDirectory() as td:
        batch, out = Path(td) / "b.txt", Path(td) / "o.txt"
        check_core.compose_batch(cases, batch)
        r = subprocess.run([str(check_core.core_bin("ucore")),
                            f"+batch={batch}", f"+out={out}",
                            f"+waits={waits}", "+ce_div=1"],
                           cwd=ROOT, capture_output=True, text=True)
        if not out.exists():
            sys.exit(f"rtl leg produced no output: {r.stdout[-800:]}")
        return check_core.parse_out(out)


def golden_jobs(suite, forms, ncases, waits, ctx, quiet):
    """-> (ok, per-form summary lines)."""
    if forms == "all":
        names = sorted(p.name.split(".json")[0] for p in suite.glob("*.json.gz"))
    else:
        names = [f.strip() for f in forms.split(",") if f.strip()]
    ok = True
    tot_cases = tot_bad = 0
    for name in names:
        f = suite / f"{name}.json.gz"
        if not f.exists():
            print(f"  {name}: no suite file")
            continue
        cases = json.load(gzip.open(f))
        if ncases:
            cases = cases[:ncases]
        msim = run_model_batch(cases, waits)
        mrtl = run_rtl_batch(cases, waits)
        bad = []
        for c in cases:
            i = c["idx"]
            a, b = msim.get(i), mrtl.get(i)
            if a is None or b is None:
                bad.append((i, "no output"))
                continue
            nc = check_core.n_fpops(c) - 1
            _x, ea, ia0, ia1 = check_core.build_rows_sim(
                a["recs"], c["initial"]["queue"], n_close=nc)
            _y, eb, ib0, ib1 = check_core.build_rows_sim(
                b["recs"], c["initial"]["queue"], n_close=nc)
            if ia0 is None or ib0 is None:
                bad.append((i, (0, ["no-window"])))
                continue
            # THE WINDOW, not the raw stream: both engines are driven past the
            # case's close and record a different number of trailing clocks,
            # which is a property of the two DRIVERS and not of the part.  The
            # window is check_core's own -- [first F .. F #n_close].
            sr = _recs_to_rows(a["recs"][ia0:ia1 + 1])
            rr = _recs_to_rows(b["recs"][ib0:ib1 + 1])
            n = min(len(sr), len(rr))
            first = next(((k, cmp_row(sr[k], rr[k]))
                          for k in range(n) if cmp_row(sr[k], rr[k])), None)
            if first is None and len(sr) != len(rr):
                first = (n, ["len"])
            if first is not None:
                bad.append((i, first))
                if not quiet and len(bad) == 1:
                    diff(f"{name} idx {i}", sr, rr, ctx)
        tot_cases += len(cases)
        tot_bad += len(bad)
        status = "LOCKSTEP" if not bad else f"{len(bad)} DIVERGE"
        print(f"  {name}: {len(cases) - len(bad)}/{len(cases)} {status}"
              + ("" if not bad else "  first: "
                 + ", ".join(f"idx {i}@{d[0]}:{','.join(d[1])}"
                             for i, d in bad[:3])))
        ok &= not bad
    print(f"\n  TOTAL {tot_cases - tot_bad}/{tot_cases} cases lockstep")
    return ok


def main():
    # U1 / P-2.  EAGERLY, before any loop: `ArtifactError` is a
    # `RuntimeError`, and a per-case `except Exception` would turn one
    # sentence naming a stale binary into N unreadable case failures.
    simbin.ensure(why=__name__)
    ap = argparse.ArgumentParser()
    ap.add_argument("scripts", nargs="*")
    ap.add_argument("--suite", action="store_true",
                    help="run the built-in stage-U1 bring-up set")
    ap.add_argument("--waits", default="0",
                    help="comma list of uniform wait levels for --suite")
    ap.add_argument("--ctx", type=int, default=8)
    ap.add_argument("--utrace", action="store_true",
                    help="enable the RTL +utrace / model EVALTRACE channels")
    ap.add_argument("--golden", metavar="FORMS",
                    help="BATCH MODE: comma list of suite forms (or 'all') run "
                         "through BOTH engines and diffed against each other")
    ap.add_argument("--cases", type=int, default=0,
                    help="--golden: cases per form (0 = all)")
    ap.add_argument("--suite-dir", default=str(ROOT / "tests" / "v30" / "v0.1"))
    ap.add_argument("--quiet", action="store_true",
                    help="--golden: summary lines only, no context window")
    args = ap.parse_args()

    # THE SCORER POSTCONDITION (sw/artifact.py; artifact_receipt_layer.md §2).
    # This used to be `if not UBIN.exists()`, and EXISTENCE IS NOT IDENTITY --
    # that test passes against a binary of any age, which is the whole of the
    # vacuous-gate pattern in one line.  `require()` does NOT rebuild (spec §8):
    # a mismatch is an error with two hashes in it and the decision is the
    # agent's, because an automatic rebuild here is how incarnation 2 stayed
    # invisible for six days.
    import artifact as art                                  # noqa: PLC0415
    if not UBIN.exists():
        sys.exit(f"missing {UBIN}: run `sw/check_core.py --build --core ucore`")
    art.require(UBIN, why="ulockstep RTL leg")
    print(f"ulockstep: RTL leg {art.relpath(UBIN)}  receipt "
          f"{str(art.receipt_id(UBIN))[:16]}…")

    if args.golden:
        w = int(args.waits.split(",")[0])
        ok = golden_jobs(Path(args.suite_dir), args.golden, args.cases, w,
                         args.ctx, args.quiet)
        print("\nULOCKSTEP-GOLDEN: "
              + ("ALL CASES LOCKSTEP" if ok else "DIVERGENCES"))
        return 0 if ok else 1

    ok = True
    with tempfile.TemporaryDirectory() as td:
        jobs = []
        if args.suite:
            for w in [int(x) for x in args.waits.split(",") if x != ""]:
                jobs += write_suite(td, w)
        jobs += [(Path(s).name, Path(s)) for s in args.scripts]
        if not jobs:
            sys.exit("nothing to do: pass scripts or --suite")
        for name, path in jobs:
            sim = run_sim(path)
            rtl = run_rtl(path, args.utrace)
            ok &= diff(name, sim, rtl, args.ctx)
    print("\nULOCKSTEP: " + ("ALL SCENARIOS LOCKSTEP" if ok else "DIVERGENCES"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
