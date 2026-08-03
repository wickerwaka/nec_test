#!/usr/bin/env python3
"""timed_fuzz -- the fuzz bank's `chip_rows`, replayed CLOCK BY CLOCK through
the TIMED simulator (campaign `ucsim-t`, stage T3).

`sw/ucsim_fuzz.py` replays the same banks FUNCTIONALLY: it regenerates each
image, verifies its sha, runs the architectural simulator and compares the
ordered bus TRANSACTION stream.  This harness runs the same seeds through
`v30sim timed-boot` from RESET and compares the PER-CLOCK PIN ROWS against the
socket capture the bank stores.

Three things are inherited rather than re-invented, deliberately:

  * the REGENERATION path (`ucsim_fuzz.regen`) and its sha256 gate -- a drift
    is a hard failure, because the image the simulator would run is then not
    the image the chip ran;
  * the COMPARISON WINDOW (`ucsim_fuzz.window_of`) -- the done-shrunk window
    the banks themselves were built with;
  * the COLUMN POLICY (`fuzz_classify.diff_rows`) -- byte for byte the policy
    the banks' own `first_bad` / `bad_rows` were computed with, which is the
    same masking family as `check_core` / `timed_gate` (`bs_late` and `rd_n`
    are WITHIN-CYCLE pulses read at a fixed sampling edge and carry no
    independent content -- T2b 12.1 -- so neither side compares them; AD is
    compared as an ADDRESS at T1 and as DATA at T2/T3 only, never on a TI or
    T4 clock, where the multiplexed pins are sampled at a different
    half-cycle).

WAIT VECTORS are rebuilt from the bank's own `waits` record: a fixed level
goes to `--waits`, and a random one to `--wmax/--wseed`, which drives the
model's copy of the rig's Galois LFSR (poly 0xB400, drawn once per bus cycle
at T1 entry -- ucsim_t_provenance.md 11.1, validated end to end by the ENTER
wrand slices).

Usage:
  timed_fuzz.py [--bank mc1,mc2,t30-raw,t30-brkem] [--limit N] [--jobs N]
                [--pilot N] [--report out.json] [--details N] [--all]
"""

import argparse
import gzip
import hashlib
import json
import os
import random
import subprocess
import sys
import tempfile
import time
from collections import Counter, defaultdict
from multiprocessing import Pool
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

SIM = ROOT / "sim" / "v30sim"
ROM = ROOT / "docs" / "V20BITS.TXT"
BANK = ROOT / "tests" / "v30" / "fuzz_bank"

import fuzz_classify as fc                            # noqa: E402
import ucsim_fuzz as uf                               # noqa: E402

BANKS = ["mc1", "mc2", "t30-raw", "t30-brkem"]


# --------------------------------------------------------------------------- #
# the scored population (see the PRE-REGISTRATION in ucsim_t_provenance.md 13)
# --------------------------------------------------------------------------- #
def excuse(entry, recs, win, evt_replay=False):
    """Why this seed is OUT of the scored population, or None.

    Both exclusions are declared BEFORE the run and are properties of the
    CAPTURE, not of the model's answer on it.

    S9b: with `evt_replay` the EVT exclusion becomes a POPULATION TAG rather
    than an exclusion -- the seed is scored and reported in its own addendum
    table, and the REGISTERED 1,702-seed denominator is what the default
    (flag off) run still produces, byte for byte.  OPEN_BUS is untouched: it
    stays an exclusion in BOTH populations, and it is tested FIRST for an EVT
    seed so the two tables cannot overlap."""
    if entry.get("evt") and not evt_replay:
        # Interrupt / INTA timing under waits is an explicit scope exclusion
        # of the whole campaign (plan, T1..T4) -- no law for it is measured
        # and no gate may pretend one is.
        return "EVT"
    if fc._open_bus_escaped_before(recs, win, win):
        # The program escaped the image and the chip is reading the rig's
        # OPEN BUS (ad_data == ad_addr feedthrough).  The simulator's memory
        # is the 64 KB-mirrored image the board is wired as, so it reads
        # image bytes there: the divergence is the RIG, not the model.
        # Detected with the bank's OWN detector.
        return "OPEN_BUS"
    return None


def wait_args(entry, td):
    w = entry.get("waits") or {}
    if w.get("wrand"):
        return [f"--wmax={int(w.get('wmax', 0))}",
                f"--wseed={int(w.get('wseed', 0))}"]
    return [f"--waits={int(w.get('fixed') or 0)}"]


def evt_directive(entry, meta, recs, win):
    """S9b -- the `timed-boot` pin-event replay directive, or None.

    Two coordinates and nothing else, both of them INPUTS:

      the RIG's schedule   the seed's own `evt` axis (pin / delay / hold) plus
                           the fetch anchor `meta["anchor_linear"]` the rig
                           arms on -- exactly the tuple check_seq.run_chip
                           handed the board (`fuzz_campaign._evt_tuple`).
      the CAPTURE's        the ordered bus position of each acknowledge and the
      boundaries           CS:IP the chip's own pushed frame recorded, computed
                           by `ucsim_fuzz.entry_points` / `frame_of` -- the
                           SAME functions the functional replay uses, imported
                           rather than forked.

    `pins` is the rig's static PINS register, which check_seq.run_chip never
    writes: it holds its reset value 0 (hps_axi_slave.sv `poll_n_out <= 0`), so
    POLL_N sits statically LOW and 9B is never busy -- the model's standing
    behaviour with no event at all.
    """
    evt = entry.get("evt")
    if not evt:
        return None
    pin = int(evt.get("pin", 0))
    cstream = uf.chip_stream(recs, win)
    fires = uf.entry_points(cstream, pin)
    frames = [uf.frame_of(cstream, i) for i in fires]
    # A frame the capture window cut short cannot name a boundary; drop it and
    # everything after it rather than guessing one.
    keep = 0
    while keep < len(fires) and frames[keep][0] >= 0:
        keep += 1
    fires, frames = fires[:keep], frames[:keep]
    return {"pin": pin,
            "addr": int(meta["anchor_linear"]) & 0xFFFFF,
            "delay": int(evt.get("delay", 0)),
            "hold": int(evt.get("hold", 0)),
            "pins": 0,
            "at": fires,
            "cs": [f[0] for f in frames],
            "ip": [f[1] for f in frames]}


def run_sim(image, entry, nrows, td, evt=None):
    img = Path(td) / "img.bin"
    img.write_bytes(bytes(image))
    argv = [str(SIM), "timed-boot", str(ROM), str(img),
            f"--clocks={nrows}", "--ndjson"] + wait_args(entry, td)
    if evt is not None:
        ep = Path(td) / "evt.json"
        ep.write_text(json.dumps(evt))
        argv.append(f"--evt={ep}")
    p = subprocess.run(argv, capture_output=True)
    rows = []
    for l in p.stdout.decode().splitlines():
        if not l.startswith("{"):
            continue
        o = json.loads(l)
        if "t" in o:
            rows.append(o)
    return rows, p.stderr.decode()


def first_kind(d):
    """One-word family for a RowDiff -- what parted FIRST, on the first row
    that parted at all."""
    if d.other:
        return d.other[0].split()[0]
    return "qsflicker" if d.flicker else "qs"


def one(path, evt_replay=False):
    entry = json.loads(gzip.decompress(Path(path).read_bytes()))
    out = {"path": str(path), "cid": entry.get("cid"), "k": entry.get("k"),
           "verdict": entry.get("verdict"), "reason": entry.get("promoted_reason"),
           "waits": entry.get("waits"), "evt": entry.get("evt")}
    try:
        image, meta, g, sha = uf.regen(entry)
    except Exception as e:                                    # noqa: BLE001
        out["cat"] = "REGEN_ERROR"
        out["detail"] = str(e)[:200]
        return out
    if sha != entry["image_sha256"]:
        out["cat"] = "GEN_DRIFT"
        out["detail"] = f"{sha[:16]} != {entry['image_sha256'][:16]}"
        return out

    recs = entry["chip_rows"]
    win = uf.window_of(recs)
    ex = excuse(entry, recs, win, evt_replay)
    evt = evt_directive(entry, meta, recs, win) if (evt_replay and not ex) \
        else None
    if evt is not None:
        out["fires"] = len(evt["at"])
    with tempfile.TemporaryDirectory() as td:
        rows, err = run_sim(image, entry, len(recs), td, evt)
    out["stderr"] = err.strip()[:200]
    if not rows:
        out["cat"] = "SIM_ERROR"
        return out
    dr = fc.diff_rows(recs, rows)
    out["n"] = dr.n
    out["ndiff"] = len(dr.rows)
    out["chip_rows"] = len(recs)
    out["sim_rows"] = len(rows)
    if dr.rows:
        d0 = dr.rows[0]
        out["first_bad"] = d0.i
        out["kind"] = first_kind(d0)
        out["detail"] = (d0.qs_txt or "") + " " + " ".join(d0.other)
        # a diff stream that is nothing but the documented F/S QS flicker
        out["flicker_only"] = all(r.flicker for r in dr.rows)
    else:
        out["first_bad"] = dr.n
        out["kind"] = "-"
        out["flicker_only"] = False
    out["exact"] = not dr.rows
    out["cat"] = ex or ("EXACT" if out["exact"] else "DIVERGE")
    out["excused"] = ex
    # S9b population tag: which of the two tables this seed belongs to.  The
    # REGISTERED population is exactly the seeds with no `evt` axis.
    out["pop"] = "EVT" if entry.get("evt") else "REG"
    return out


# --------------------------------------------------------------------------- #
def seeds_of(banks):
    out = []
    for b in banks:
        d = BANK / b / "seeds"
        if not d.is_dir():
            continue
        out += sorted(str(p) for p in d.glob("*.json.gz"))
    return out


def axes_of(path):
    """(pop, pin, wait-class) for a banked seed, read from the record itself.
    Used only to SELECT a population / a stratified pilot -- never to score."""
    e = json.loads(gzip.decompress(Path(path).read_bytes()))
    ev, w = e.get("evt"), (e.get("waits") or {})
    wc = f"wrand{w.get('wmax')}" if w.get("wrand") else f"fix{w.get('fixed') or 0}"
    return ("EVT" if ev else "REG", int(ev["pin"]) if ev else -1, wc)


def stratify(paths, n, seed=20260802, keys=None):
    """A stratified pilot: proportional over the strata, deterministic.

    Default strata = the bank.  `keys` (path -> tuple) refines them; the S9b
    EVT pilot uses (bank, pin, wait class) so the pilot cannot miss the NMI or
    the waited slices."""
    strata = defaultdict(list)
    for p in paths:
        b = Path(p).parent.parent.name
        if keys:
            b = (b,) + tuple(keys[p])
        strata[b].append(p)
    rr = random.Random(seed)
    picked = []
    if keys:
        # Refined strata are many and small, so a concatenation truncated at
        # `n` would return the first stratum only: draw ROUND-ROBIN, which
        # keeps every stratum represented at any n.  (The default, unrefined
        # path below is untouched -- it is the T3 pre-registration's own.)
        pools = []
        for b in sorted(strata, key=repr):
            pool = sorted(strata[b])
            rr.shuffle(pool)
            pools.append(pool)
        # ...and the STRATUM ORDER is shuffled too, so that a pilot smaller
        # than the number of strata is not just the alphabetically first ones
        # (which is one bank).
        rr.shuffle(pools)
        i = 0
        while len(picked) < n and any(len(p) > i for p in pools):
            for p in pools:
                if i < len(p):
                    picked.append(p[i])
                    if len(picked) >= n:
                        break
            i += 1
        return picked[:n]
    for b in sorted(strata, key=repr):
        take = max(1, round(n * len(strata[b]) / len(paths)))
        pool = sorted(strata[b])
        rr.shuffle(pool)
        picked += pool[:take]
    return picked[:n]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bank", default=",".join(BANKS))
    # T4: the victory tranche is scored by THIS harness, unchanged -- same
    # regeneration path and sha gate, same window, same column policy.  The
    # only thing --seeddir changes is which directory the records come from.
    ap.add_argument("--seeddir", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--pilot", type=int, default=0)
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 4)
    ap.add_argument("--report", default="")
    ap.add_argument("--details", type=int, default=0)
    # S9b.  OFF by default: `python3 sw/timed_fuzz.py` with no flags is the
    # REGISTERED gate (sec.13.0's population, denominator and policy) and is
    # not touched by this session.  With the flag the EVT seeds are scored too
    # and reported as their OWN table plus a combined figure.
    ap.add_argument("--evt-replay", action="store_true",
                    help="score the EVT seeds through the pin-event replay "
                         "(reported separately; the registered table is "
                         "unchanged)")
    ap.add_argument("--pop", default="all", choices=("all", "reg", "evt"),
                    help="restrict to the registered (no-evt) or the EVT "
                         "population; selection only, scoring is unchanged")
    args = ap.parse_args()

    paths = sorted(str(x) for x in Path(args.seeddir).glob("*.json.gz")) \
        if args.seeddir else seeds_of([b for b in args.bank.split(",") if b])
    # Selection only.  With --pop all (the registered gate) NOTHING here runs,
    # so the default path -- including the T3 pilot's own stratification -- is
    # byte for byte what it was.
    keys = None
    if args.pop != "all":
        with Pool(args.jobs) as pool:
            ax = pool.map(axes_of, paths, chunksize=16)
        keys = dict(zip(paths, ax))
        want = "EVT" if args.pop == "evt" else "REG"
        paths = [p for p in paths if keys[p][0] == want]
    if args.pilot:
        paths = stratify(paths, args.pilot, keys=keys)
    elif args.limit:
        paths = paths[:args.limit]

    t0 = time.time()
    with Pool(args.jobs) as pool:
        res = pool.starmap(one, [(p, args.evt_replay) for p in paths],
                           chunksize=4)

    cat = Counter(r["cat"] for r in res)
    all_scored = [r for r in res if r["cat"] in ("EXACT", "DIVERGE")]
    reg = [r for r in all_scored if r.get("pop") != "EVT"]
    evtp = [r for r in all_scored if r.get("pop") == "EVT"]
    print(f"== timed_fuzz -- fuzz-bank chip_rows through the TIMED sim "
          f"({len(paths)} seeds, {time.time()-t0:.0f} s)")
    print("  categories      " + "  ".join(f"{k}={v}" for k, v in
                                           sorted(cat.items())))
    if args.evt_replay:
        for lbl, grp in (("REGISTERED", reg), ("EVT-unlocked", evtp),
                         ("COMBINED", all_scored)):
            if not grp:
                continue
            ex = sum(1 for r in grp if r["exact"])
            fl = sum(1 for r in grp if r.get("flicker_only"))
            print(f"  {lbl:<14}  cycle-exact {ex}/{len(grp)} "
                  f"({100.0*ex/len(grp):.1f} %)   "
                  f"+flicker {ex+fl}/{len(grp)} "
                  f"({100.0*(ex+fl)/len(grp):.1f} %)")
    # The detail block below always describes the SCORED set of this run.
    scored = all_scored
    exact = [r for r in scored if r["exact"]]
    flick = [r for r in scored if r.get("flicker_only")]
    print(f"  SCORED          {len(scored)}")
    if scored:
        print(f"  cycle-exact     {len(exact)}/{len(scored)} "
              f"({100.0*len(exact)/len(scored):.1f} %)")
        print(f"  ...+flicker     {len(exact)+len(flick)}/{len(scored)} "
              f"({100.0*(len(exact)+len(flick))/len(scored):.1f} %)")
        fr = sorted(r["first_bad"] / max(1, r["n"]) for r in scored)
        med = fr[len(fr)//2]
        print(f"  prefix fraction median {med:.3f}   "
              f">=0.5 {sum(1 for x in fr if x >= .5)}/{len(fr)}   "
              f">=0.9 {sum(1 for x in fr if x >= .9)}/{len(fr)}")
        fb = sorted(r["first_bad"] for r in scored)
        print(f"  first divergence rows: median {fb[len(fb)//2]}, "
              f"p10 {fb[len(fb)//10]}, p90 {fb[9*len(fb)//10]}")
        print("  first-divergence family: " +
              "  ".join(f"{k}={v}" for k, v in
                        Counter(r["kind"] for r in scored
                                if not r["exact"]).most_common()))
        wc = defaultdict(lambda: [0, 0])
        for r in scored:
            w = r["waits"] or {}
            key = f"wrand{w.get('wmax')}" if w.get("wrand") else \
                  f"fix{w.get('fixed') or 0}"
            wc[key][0] += 1
            wc[key][1] += 1 if r["exact"] else 0
        print("  by wait class:  " + "  ".join(
            f"{k} {v[1]}/{v[0]}" for k, v in sorted(wc.items())))
        bc = defaultdict(lambda: [0, 0])
        for r in scored:
            bc[r["cid"]][0] += 1
            bc[r["cid"]][1] += 1 if r["exact"] else 0
        print("  by bank:        " + "  ".join(
            f"{k} {v[1]}/{v[0]}" for k, v in sorted(bc.items())))

    if args.details:
        for r in sorted((r for r in scored if not r["exact"]),
                        key=lambda r: r["first_bad"])[:args.details]:
            print(f"    {r['cid']}/{r['k']:<6} first_bad={r['first_bad']:>5} "
                  f"n={r['n']:>5} ndiff={r['ndiff']:>5} {r['kind']:<10} "
                  f"{r.get('detail','')[:70]}")
    if args.report:
        Path(args.report).write_text(json.dumps(res))
        print(f"  report -> {args.report}")
    bad = cat.get("GEN_DRIFT", 0) + cat.get("REGEN_ERROR", 0) + \
        cat.get("SIM_ERROR", 0)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
