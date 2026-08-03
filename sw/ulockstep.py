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

Usage:
    ulockstep.py <script>...            diff each script
    ulockstep.py --suite               the built-in stage-U1 bring-up set
    ulockstep.py --waits 0,1,2,3 ...   run each script at each wait level
"""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
SIM = ROOT / "sim" / "v30sim"
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scripts", nargs="*")
    ap.add_argument("--suite", action="store_true",
                    help="run the built-in stage-U1 bring-up set")
    ap.add_argument("--waits", default="0",
                    help="comma list of uniform wait levels for --suite")
    ap.add_argument("--ctx", type=int, default=8)
    ap.add_argument("--utrace", action="store_true",
                    help="enable the RTL +utrace / model EVALTRACE channels")
    args = ap.parse_args()

    if not UBIN.exists():
        sys.exit(f"missing {UBIN}: run `sw/check_core.py --build --core ucore`")

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
