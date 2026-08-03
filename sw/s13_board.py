#!/usr/bin/env python3
"""s13_board -- the CLOSING board sitting (ucsim-t addendum #9, provenance 24).

Discipline is S10's (21.0), unchanged and re-asserted in code:
  * SOCKET ONLY -- `use_core=False` on every call, passed explicitly because
    the board's CFG is sticky.  No FPGA flashing anywhere.
  * The DIVIDER IS PINNED on every probe (21.1 / 22.6) and the runner's
    `div_readback` is RECORDED.  An UNPINNED readback is a rig-integrity
    finding and the probe says so out loud.
  * Raw 64-bit capture words retained with a sha256, and the FULL per-clock
    row stream retained beside every digest (the P2 lesson, 13.4).
  * `board_idle()` at the end of the session, result stated.
  * A wedge STOPS the session; it is not nursed along.

Probes (specs + PRE-REGISTERED predictions: ucsim_t_provenance.md 24.0):

  ahsweep  P1b -- the A-H residue band at waits 2 and 3.  The w0/w1 sweep is
           committed and was scored BOARD-FREE first (24.1); this is the
           wait-axis extension that says whether the band's one clock is
           wait-invariant.
  race     P5 -- HLT.INT_w0_d0, the ONE repetition-unstable cell of the 196
           (23.9 item 7), at high repetition.  A measured race, characterised;
           determinism is NOT forced.
  c2ramp   P2a -- C2, LC1's queue-fill RAMP (biu_law_cards.md A.1; 21.0 S3a).
           Repeated far-JMP flushes ahead of a fetch-limited sled, so every
           flush restarts the fill from zero.
  sha      (re)write SHA256SUMS per probe directory.
  idle     board_idle().

The w1evt RE-EMISSION (P4) is NOT here: it is `s10_board.py s1 --waits 1`
verbatim, the committed emission path with the fixed `parse_result`, and
running it through anything else would change the instrument as well as the
parser.  See 24.4.

Usage:
    python3 sw/s13_board.py ahsweep [--reps 5]
    python3 sw/s13_board.py race [--reps 50]
    python3 sw/s13_board.py c2ramp
    python3 sw/s13_board.py sha
    python3 sw/s13_board.py idle
"""
import argparse
import gzip
import hashlib
import json
import random
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

import testimage                                        # noqa: E402
import emit_suite as es                                 # noqa: E402
import v30run                                           # noqa: E402
from v30run import run_image                            # noqa: E402
from t2b_board import HOST, REPS                        # noqa: E402
from t2b_board import capture as t2b_capture            # noqa: E402
from s10_board import (capture, reps_capture, pin_div, cycles,  # noqa: E402
                       halt_status, DIV_OF_RECORD, _evt_image)
from gen_seq import Prog, PC0, SP0, DATA_LO, DATA_HI    # noqa: E402
from check_seq import compose as seq_compose            # noqa: E402
from causal_wrand import accesses, CODE                 # noqa: E402
import timed_wvec_gate as WG                            # noqa: E402

OUT = ROOT / "sw" / "testdata" / "s13"
SIM = ROOT / "sim" / "v30sim"
ROM = ROOT / "docs" / "V20BITS.TXT"
MAXV = 4096

assert es.EMIT_USE_CORE is False, "S13 refuses to run: truth source is not the socket"
assert DIV_OF_RECORD == es.EMIT_DIV, "divider of record disagrees with the emission pin"


# --------------------------------------------------------------------------- #
# the UNPINNED readback guard (21.1 / 22.6) -- every probe calls this and
# records what it said.  UNPINNED is not an error; it is the fact that has to
# be recorded, and a probe that records it is reporting a rig finding.
# --------------------------------------------------------------------------- #
def div_guard(tag):
    """Pin the divider and READ THE RUNNER'S OWN STATEMENT of it back.

    22.6 added `ServeRunner.div_readback`; nothing had ever called it.  This
    is the guard the S10 hazard asked for: the probe does not assert that it
    pinned the divider, it asks the transport what it commanded and records
    the answer.  UNPINNED here is a rig-integrity FINDING."""
    pin_div()
    r = v30run._runners.get(HOST)
    rb = (r.div_readback if r is not None
          else "div=UNKNOWN (no live serve runner to ask)")
    state = "PINNED" if "UNPINNED" not in str(rb) and "UNKNOWN" not in str(rb) \
        else "UNPINNED"
    print(f"  [div guard] {tag}: {rb}   -> {state}", flush=True)
    if state != "PINNED":
        print("  [div guard] *** UNPINNED READBACK -- recorded, not smoothed "
              "(21.1) ***", flush=True)
    return {"readback": str(rb), "state": state}


def _sha_dir(d):
    lines = []
    for p in sorted(d.rglob("*")):
        if p.is_file() and p.name != "SHA256SUMS":
            h = hashlib.sha256(p.read_bytes()).hexdigest()
            lines.append(f"{h}  {p.relative_to(d)}")
    (d / "SHA256SUMS").write_text("\n".join(lines) + "\n")
    return len(lines)


# --------------------------------------------------------------------------- #
# P1b -- the A-H band at waits 2 and 3
# --------------------------------------------------------------------------- #
S13_FORMS = ("HLT.INT", "HLT.RES")
# 0..24 brackets the PREDICTED d* at both levels (12 at w2, 16 at w3) with at
# least 8 delays of margin on each side, and stays well inside the w3 capture
# cap (EMIT_CAP = 4096 records at w3; 21.0.5 item 3).
AH_DELAYS = list(range(0, 25))


def cmd_ahsweep(args):
    d = OUT / "p1b-ahsweep"
    d.mkdir(parents=True, exist_ok=True)
    man = {"probe": "P1b -- the A-H residue band at waits 2 and 3",
           "spec": "docs/notes/ucsim_t_provenance.md 24.0 P1b",
           "use_core": False, "host": HOST, "reps": args.reps,
           "delays": AH_DELAYS, "forms": list(S13_FORMS), "cells": {}}
    table = []
    t0 = time.time()
    man["div_guard"] = div_guard("ahsweep")
    for waits in args.waits:
        sd = ROOT / "tests" / "v30" / f"s13-hltsweep-w{waits}"
        sd.mkdir(parents=True, exist_ok=True)
        log = sd / "emit_log.txt"
        with log.open("a") as f:
            f.write(f"# TRUTH SOURCE: SOCKET (real chip, use_core=False)  "
                    f"seed_base=v30-s10-hlt (the S2 sweep's OWN fixed seed, so "
                    f"w2/w3 are the SAME program as w0/w1)  waits={waits}  "
                    f"div={DIV_OF_RECORD} ({32//DIV_OF_RECORD} MHz, PINNED)  "
                    f"guard={man['div_guard']['state']}\n")
        for op in S13_FORMS:
            spec = es.EVT_FORMS[op]
            tests = []
            for di, delay in enumerate(AH_DELAYS):
                rng = random.Random(f"v30-s10-hlt/{op}")
                try:
                    case = es.gen_evt_case(spec, rng)
                except es.ComposeError:
                    continue
                case["delay"] = delay
                image, evt, _ = _evt_image(spec, case)
                rec, rows, raw = reps_capture(image, waits=waits, evt=evt,
                                              tag="s13ah", reps=args.reps,
                                              divs=(8,))
                hs = halt_status(rows)
                cyc = cycles(rows)
                anchor = next((c["t1"] for c in cyc if c["kind"] == "CODE"), None)
                row = {"form": op, "waits": waits, "delay": delay,
                       "fired": rec["fired"],
                       "halt_driven": hs is not None,
                       "halt_first": None if hs is None else hs[0],
                       "halt_len": None if hs is None else hs[1],
                       "anchor_t1": anchor,
                       "n_rows": len(rows),
                       "stable": rec["captures"]["8"]["stable_identical"]}
                table.append(row)
                key = f"{op}_w{waits}_d{delay}"
                man["cells"][key] = rec
                with gzip.open(d / f"{key}.rows.json.gz", "wt") as f:
                    json.dump(rows, f, separators=(",", ":"))
                with gzip.open(d / f"{key}.raw.hex.gz", "wt") as f:
                    f.write("\n".join(raw) + "\n")
                try:
                    t = es.emit_evt_case(spec, case, HOST, tag="s13g",
                                         preload_n=0, waits=waits)
                    t["idx"] = delay
                    tests.append(t)
                except (es.ComposeError, es.RunError) as e:
                    with log.open("a") as f:
                        f.write(f"{key} golden: {e}\n")
                    print(f"    golden {key}: {e}", flush=True)
            if tests:
                with gzip.open(sd / f"{op}.json.gz", "wt") as f:
                    json.dump(tests, f, separators=(",", ":"))
            print(f"  {op} w{waits}: {len(tests)}/{len(AH_DELAYS)} goldens "
                  f"({time.time()-t0:.0f}s)", flush=True)
    man["seconds"] = round(time.time() - t0, 1)
    (d / "manifest.json").write_text(json.dumps(man, indent=1))
    (d / "sweep_table.json").write_text(json.dumps(table, indent=1))
    _ah_report(table)
    print(f"  SHA256SUMS: {_sha_dir(d)} files")
    return 0


def _ah_report(table):
    """The REGISTERED reading: d* per wait level against the prediction."""
    print("\n  --- P1b, the registered threshold reading ---")
    print("  (REGISTERED: d*(w2) = 12, d*(w3) = 16; halt_len = 2 always)")
    for op in S13_FORMS:
        for w in sorted({r["waits"] for r in table}):
            rows = sorted([r for r in table if r["form"] == op and r["waits"] == w],
                          key=lambda r: r["delay"])
            if not rows:
                continue
            drv = [r["delay"] for r in rows if r["halt_driven"]]
            nod = [r["delay"] for r in rows if not r["halt_driven"]]
            dstar = min(drv) if drv else None
            sharp = (not nod or not drv or max(nod) < min(drv))
            lens = sorted({r["halt_len"] for r in rows if r["halt_driven"]})
            hs = sorted({r["halt_first"] for r in rows if r["halt_driven"]})
            anc = sorted({r["anchor_t1"] for r in rows})
            unstable = [r["delay"] for r in rows if not r["stable"]]
            print(f"    {op:8s} w{w}: d*={dstar}  sharp={sharp}  "
                  f"halt_len={lens}  H={hs[:3]}  anchor={anc[:3]}  "
                  f"not-driven={len(nod)}/{len(rows)}  unstable={unstable}")


# --------------------------------------------------------------------------- #
# P5 -- the one repetition-unstable cell, characterised
# --------------------------------------------------------------------------- #
def cmd_race(args):
    """HLT.INT w0 d0 at high repetition.  23.3 measured 195/196 sweep cells
    5-of-5 byte-identical and this ONE cell not.  A race is CHARACTERISED
    (how many outcomes, what separates them, how often) and NOT forced to be
    deterministic -- the POP-PSW lore (RR1) is the precedent."""
    d = OUT / "p5-race"
    d.mkdir(parents=True, exist_ok=True)
    man = {"probe": "P5 -- HLT.INT_w0_d0, the repetition-unstable cell",
           "spec": "docs/notes/ucsim_t_provenance.md 24.0 P5",
           "use_core": False, "host": HOST, "reps": args.reps, "cells": {}}
    t0 = time.time()
    man["div_guard"] = div_guard("race")
    out = {}
    for form, waits, delay in args.cells:
        spec = es.EVT_FORMS[form]
        rng = random.Random(f"v30-s10-hlt/{form}")
        case = es.gen_evt_case(spec, rng)
        case["delay"] = delay
        image, evt, _ = _evt_image(spec, case)
        key = f"{form}_w{waits}_d{delay}"
        variants = Counter()
        keep = {}
        fired = Counter()
        for i in range(args.reps):
            rows, raw, sha, f = capture(image, waits=waits, evt=evt,
                                        tag="s13race")
            variants[sha] += 1
            fired[bool(f)] += 1
            if sha not in keep:
                keep[sha] = (rows, raw)
        man["cells"][key] = {"reps": args.reps,
                             "distinct": len(variants),
                             "counts": dict(variants),
                             "fired": dict(fired)}
        for j, (sha, (rows, raw)) in enumerate(sorted(keep.items())):
            with gzip.open(d / f"{key}.v{j}.rows.json.gz", "wt") as fh:
                json.dump(rows, fh, separators=(",", ":"))
            with gzip.open(d / f"{key}.v{j}.raw.hex.gz", "wt") as fh:
                fh.write("\n".join(raw) + "\n")
        out[key] = (variants, keep)
        print(f"  {key}: {args.reps} reps -> {len(variants)} distinct "
              f"stream(s)  {dict(variants)}  ({time.time()-t0:.0f}s)",
              flush=True)
    man["seconds"] = round(time.time() - t0, 1)
    (d / "manifest.json").write_text(json.dumps(man, indent=1))
    _race_report(out)
    print(f"  SHA256SUMS: {_sha_dir(d)} files")
    return 0


def _race_report(out):
    print("\n  --- P5, the race characterised ---")
    for key, (variants, keep) in out.items():
        if len(variants) < 2:
            print(f"    {key}: SINGLE stream over every repetition -- the "
                  f"instability of 23.3 is NOT reproduced at this rep count")
            continue
        shas = sorted(keep)
        base = keep[shas[0]][0]
        for s in shas[1:]:
            other = keep[s][0]
            n = min(len(base), len(other))
            first = next((i for i in range(n) if base[i] != other[i]), None)
            print(f"    {key}: variants {shas[0][:8]} vs {s[:8]}  "
                  f"lengths {len(base)}/{len(other)}  first differing row "
                  f"{first}")
            if first is not None:
                for i in range(max(0, first - 2), min(n, first + 3)):
                    m = "*" if base[i] != other[i] else " "
                    print(f"      {m} {i:5d}  A {base[i]}")
                    print(f"        {'':5s}  B {other[i]}")


# --------------------------------------------------------------------------- #
# P2a -- C2, LC1's queue-fill RAMP
# --------------------------------------------------------------------------- #
C2_WVECS = [(0, 0), (5, 1), (7, 3), (11, 7)]      # the four corpus vectors


def c2_image(flush_period, sled, nblocks=12):
    """Repeated `far JMP next` flushes, each followed by a fetch-limited NOP
    sled.  The far JMP is `gen_seq`'s own contained construct (the sled corpus
    uses it), so the queue is emptied to ZERO every `flush_period` and the
    fill restarts from empty -- which is exactly the transient C2 names and
    the Arm-C steady-state sled does not isolate."""
    rng = random.Random(f"s13-c2/{flush_period}/{sled}")
    p = Prog(rng)
    for _ in range(nblocks):
        p.emit_farjmp_next()
        for _ in range(sled):
            p.emit([0x90])
        for _ in range(max(0, flush_period - sled)):
            p.emit([0x90])
    instr = p.assemble()
    regs = {"PS": 0, "PC": PC0, "SS": 0, "SP": SP0,
            "DS0": 0, "DS1": 0, "PSW": 0xF202,
            "AW": 0x1234, "BW": 0x2345, "CW": 0x0003, "DW": 0x0040,
            "BP": 0x3456, "IX": 0x2500, "IY": 0x2A00}
    ram = [(a, rng.getrandbits(8)) for a in range(DATA_LO, DATA_HI + 0x100)]
    image, _ = seq_compose(dict(seed=0, instr=instr, regs=regs, ram=ram,
                                ivt=None))
    return image


def sim_rows_image(image, wv, nrows):
    with tempfile.TemporaryDirectory() as td:
        img = Path(td) / "img.bin"
        img.write_bytes(bytes(image))
        wvf = Path(td) / "wv.txt"
        wvf.write_text("\n".join(str(x) for x in wv) + "\n")
        r = subprocess.run([str(SIM), "timed-boot", str(ROM), str(img),
                            f"--clocks={nrows}", "--ndjson", f"--wvec={wvf}"],
                           capture_output=True)
        rows = [x for x in (json.loads(l)
                            for l in r.stdout.decode().splitlines()
                            if l.startswith("{")) if "t" in x]
        return rows[:nrows]


def _norm(rows):
    """chip rows and sim rows into one shape for `accesses`."""
    out = []
    for r in rows:
        if "bs_early" in r:
            out.append(dict(t=r["t"], bs_early=r["bs_early"], qs=r["qs"],
                            ad_addr=r["ad_addr"], ad_data=0))
        else:
            out.append(dict(t=r["t"], bs_early=r["bs"], qs=r["qs"],
                            ad_addr=r["addr"], ad_data=0))
    return out


def ramp_gaps(rows):
    """(post-flush gaps, steady-state gaps).

    A FLUSH is the chip's own queue-clear on the QS port (QS = E = 2).  The
    POST-FLUSH gap is the idle-clock count ahead of the FIRST CODE access
    whose T1 is after that clear; every other CODE->CODE gap is STEADY.
    Both are `class5_armc.pauses()` verbatim (timed_lawcards.cidle_events),
    only partitioned."""
    nr = _norm(rows)
    flushes = [i for i, r in enumerate(nr) if r["qs"] == 2]
    acc = accesses(nr)
    post, steady = [], []
    for i in range(1, len(acc)):
        if acc[i]["bs"] != CODE or acc[i - 1]["bs"] != CODE:
            continue
        if acc[i - 1]["t4"] is None:
            continue
        gap = sum(1 for r in range(acc[i - 1]["t4"] + 1, acc[i]["t1"])
                  if nr[r]["t"] == 0)
        # was there a queue-clear between the previous access's T4 and this T1?
        if any(acc[i - 1]["t4"] < f < acc[i]["t1"] for f in flushes):
            post.append(gap)
        else:
            steady.append(gap)
    return post, steady


def cmd_c2ramp(args):
    d = OUT / "p2a-c2ramp"
    d.mkdir(parents=True, exist_ok=True)
    man = {"probe": "P2a -- C2, LC1's queue-fill ramp",
           "spec": "docs/notes/ucsim_t_provenance.md 24.0 P2a; "
                   "biu_law_cards.md A.1 (C2)",
           "use_core": False, "host": HOST, "cells": {}}
    t0 = time.time()
    man["div_guard"] = div_guard("c2ramp")
    results = []
    for period in args.periods:
        for sled in args.sleds:
            image = c2_image(period, sled)
            for ws, wmax in C2_WVECS:
                wv = WG.wv_of(ws, wmax)
                key = f"p{period}s{sled}:ws{ws}:wmax{wmax}"
                # t2b_board.capture is the wvec-carrying primitive and its row
                # semantics are `run_chip`'s exactly (21.0.0 item 2), so this
                # cell is comparable to every banked t2b/t4 record.
                rows, raw, sha = t2b_capture(image, waits=0, wvec=wv,
                                             tag="s13c2")
                cp, cs = ramp_gaps(rows)
                srows = sim_rows_image(image, wv, len(rows))
                sp, ss = ramp_gaps(srows)
                r = {"key": key, "period": period, "sled": sled,
                     "ws": ws, "wmax": wmax, "sha": sha,
                     "chip_rows": len(rows), "sim_rows": len(srows),
                     "chip_post": dict(sorted(Counter(cp).items())),
                     "chip_steady": dict(sorted(Counter(cs).items())),
                     "sim_post": dict(sorted(Counter(sp).items())),
                     "sim_steady": dict(sorted(Counter(ss).items()))}
                results.append(r)
                man["cells"][key] = {"sha": sha, "rows": len(rows)}
                with gzip.open(d / f"{key.replace(':','_')}.rows.json.gz", "wt") as f:
                    json.dump(rows, f, separators=(",", ":"))
                with gzip.open(d / f"{key.replace(':','_')}.raw.hex.gz", "wt") as f:
                    f.write("\n".join(raw) + "\n")
                print(f"  {key}: chip post {r['chip_post']} steady "
                      f"{r['chip_steady']} | sim post {r['sim_post']} steady "
                      f"{r['sim_steady']}  ({time.time()-t0:.0f}s)", flush=True)
    man["seconds"] = round(time.time() - t0, 1)
    (d / "manifest.json").write_text(json.dumps(man, indent=1))
    (d / "c2_table.json").write_text(json.dumps(results, indent=1))
    _c2_report(results)
    print(f"  SHA256SUMS: {_sha_dir(d)} files")
    return 0


def _c2_report(results):
    print("\n  --- P2a, C2's registered reading ---")
    print("  (REGISTERED: the post-flush gap is STRICTLY SMALLER than the "
          "steady-state cidle of 3, and the sim reproduces the ramp's "
          "distribution.  A post-flush distribution CENTRED ON 3 refutes the "
          "CARD, not the model.)")
    cp, cs, sp, ss = Counter(), Counter(), Counter(), Counter()
    for r in results:
        cp += Counter({int(k): v for k, v in r["chip_post"].items()})
        cs += Counter({int(k): v for k, v in r["chip_steady"].items()})
        sp += Counter({int(k): v for k, v in r["sim_post"].items()})
        ss += Counter({int(k): v for k, v in r["sim_steady"].items()})

    def mode(c):
        return None if not c else max(c.items(), key=lambda x: x[1])[0]
    print(f"    chip post-flush  {dict(sorted(cp.items()))}  mode={mode(cp)}  n={sum(cp.values())}")
    print(f"    chip steady      {dict(sorted(cs.items()))}  mode={mode(cs)}  n={sum(cs.values())}")
    print(f"    sim  post-flush  {dict(sorted(sp.items()))}  mode={mode(sp)}  n={sum(sp.values())}")
    print(f"    sim  steady      {dict(sorted(ss.items()))}  mode={mode(ss)}  n={sum(ss.values())}")
    if not cp:
        print("    VERDICT: no post-flush CODE->CODE pair was produced at all "
              "-- the stimulus did not isolate the transient.  C2 stays "
              "UNRESOLVED and this is a PROBE-DESIGN finding (21.0 S3's "
              "registered third outcome), not a pass.")
        return
    ramp_smaller = mode(cp) is not None and mode(cs) is not None and mode(cp) < mode(cs)
    print(f"    ramp transient EXISTS on silicon: {ramp_smaller} "
          f"(chip post mode {mode(cp)} vs steady mode {mode(cs)})")
    print(f"    sim reproduces the split: "
          f"{mode(sp) == mode(cp) and mode(ss) == mode(cs)}")


# --------------------------------------------------------------------------- #
def cmd_sha(args):
    for d in sorted(OUT.glob("*")):
        if d.is_dir():
            print(f"  {d.name}: {_sha_dir(d)} files")
    return 0


def cmd_idle(args):
    import b1_recapture
    r = b1_recapture.board_idle()
    print(f"board_idle -> {r}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("ahsweep")
    p.add_argument("--reps", type=int, default=REPS)
    p.add_argument("--waits", type=lambda s: [int(x) for x in s.split(",")],
                   default=[2, 3])
    p.set_defaults(fn=cmd_ahsweep)

    p = sub.add_parser("race")
    p.add_argument("--reps", type=int, default=50)
    p.set_defaults(fn=cmd_race, cells=[("HLT.INT", 0, 0)])

    p = sub.add_parser("c2ramp")
    p.add_argument("--periods", type=lambda s: [int(x) for x in s.split(",")],
                   default=[6, 10, 16])
    p.add_argument("--sleds", type=lambda s: [int(x) for x in s.split(",")],
                   default=[2, 6])
    p.set_defaults(fn=cmd_c2ramp)

    sub.add_parser("sha").set_defaults(fn=cmd_sha)
    sub.add_parser("idle").set_defaults(fn=cmd_idle)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
