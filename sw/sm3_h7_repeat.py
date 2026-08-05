#!/usr/bin/env python3
"""sm3_h7_repeat -- THE H7 REPETITION RE-CAPTURE.

Pre-registration: `docs/notes/sm3_s20_prereg_2026-08-05.md` §B, committed
BEFORE the board was contacted.  Read it before running this; the four
outcomes and their dispositions were written down first and are not restated
here.

WHAT IS OPEN
------------
Over the 208 banked pin-1 (NMI) seeds the chip's vector-read gap `V - A` has a
floor of **12** on exactly **30** seeds; both engines floor at **13** and the
30 are exactly the seeds they miss (`ucore_provenance.md` §63.2).  Every
DIRECTED board population built since -- §63.3's delay sweep, §65.1's
primed/dry cell, §68.5's ten-opcode cell, §72's IE cell -- floors at **13**,
with zero captures below 12 anywhere.  Wait class, rig delay, bus owner at A,
queue occupancy at A, queue primed vs dry, the composition of the window
`[A, V)` and the instruction at the boundary are all ELIMINATED.  The one
coordinate no directed cell has ever varied is **the capture session itself**,
because each was taken in one sitting on one rig state.

THE QUESTION, AND WHY REPETITION ANSWERS IT
-------------------------------------------
If the 12 is a MECHANISM it is a property of the seed and repeats.  If it is a
sub-clock ARTIFACT -- the electrical margin of the rig's synchronous pin assert
against the chip's internal sampling instant -- it is a property of the
capture, and a re-capture on the current rig either loses it (all 13) or
splits (mixed).  Nothing about the geometry changes; the seed is replayed at
its own banked directive, N times.

WHAT IT IS NOT.  It is not a gate, it scores no engine, and it changes no
engine.  It is a MEASUREMENT, and the disposition it authorises is written in
the pre-registration before the number exists.

SUBCOMMANDS
-----------
  population  the 30, DERIVED and never listed: every banked seed with
              `evt.pin == 1` whose measured gap is 12, computed through
              `sm3_nmigeom.one` itself so the tool and the finding cannot
              drift apart.  Board-free.
  capture     the socket leg (use_core=False).  Per seed the image is
              REGENERATED from (cid, k, ov) and HASH-CHECKED against the banked
              `image_sha256` -- GEN-DRIFT is a hard skip, never a silent
              capture -- then run N times at the banked directive.  Full
              per-clock rows + sha256 per repetition.
  control     the pin-0 leg: banked INT seeds re-captured a few times each,
              whose INTA1 gap must reproduce its banked value EXACTLY.  This
              is the control that says the rig and the `A` derivation are
              sound in THIS session.  It is not a result.
  report      the per-seed repetition table and the outcome class.

Board discipline (CLAUDE.md): single-writer checked by the caller; SOCKET ONLY
(`use_core=False`, explicit -- the board's CFG is sticky); the divider PINNED
by `run_image(div=DIV_OF_RECORD)` on every capture with the `div_guard`
readback RECORDED at both ends; the FULL per-clock rows retained beside their
sha256; `board_idle()` at the close; a run of consecutive transport errors
STOPS the cell rather than grinding on.  NO FLASHING -- the board carries
FLASH #9 and this cell does not use the core.
"""
import argparse
import gzip
import hashlib
import json
import sys
import time
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

import check_seq                                          # noqa: E402
import sm3_nmigeom as ng                                  # noqa: E402
import ucsim_fuzz as uf                                   # noqa: E402
import v30run                                             # noqa: E402
import testimage                                          # noqa: E402

HOST = "root@mister-nec"
BANK = ROOT / "tests" / "v30" / "fuzz_bank"
OUT = ROOT / "sw" / "testdata" / "sm3-h7rep"
STORM = 15                       # consecutive transport errors -> STOP
FLOOR = 12                       # the gap the 30 sit at


def sha(b):
    return hashlib.sha256(b).hexdigest()


def _paths(pin):
    ps = ng.seeds_of(ng.BANKS)
    return [p for p in ps if ng.axis(p) == pin]


def population(jobs=8, gap=FLOOR, limit=0):
    """The 30, DERIVED.  Never a list.

    `gap` is parametric ONLY so that the same predicate can select the
    NON-floor pin-1 seeds as a control (SM3 s20 sec.81.B.4, an ADDED control
    taken after the floor result was seen and declared as such).  The floor
    population is `gap=12` and nothing else."""
    paths = _paths(1)
    with Pool(jobs) as pool:
        res = pool.map(ng.one, [(p, "") for p in paths], chunksize=4)
    out = sorted((r for r in res
                  if (r.get("gap") == gap if gap >= 0
                      else (r.get("gap") is not None
                            and (gap == -2 or r["gap"] > FLOOR + 1)))),
                 key=lambda r: r["path"])
    return out[:limit] if limit else out


def controls(jobs=8, n=10):
    """Pin-0 (INT) seeds with a clean banked recognition, spread over the
    banks, taken in path order so the choice is not a choice."""
    paths = _paths(0)
    with Pool(jobs) as pool:
        res = pool.map(ng.one, [(p, "") for p in paths], chunksize=8)
    ok = [r for r in res
          if not r.get("err") and r.get("gap") is not None and r["arm"] >= 0
          and r.get("nvec", 0) >= 1]
    by = {}
    for r in sorted(ok, key=lambda r: r["path"]):
        by.setdefault(r["path"].split("fuzz_bank/")[1].split("/")[0],
                      []).append(r)
    out = []
    i = 0
    while len(out) < n and any(len(v) > i for v in by.values()):
        for b in sorted(by):
            if len(by[b]) > i and len(out) < n:
                out.append(by[b][i])
        i += 1
    return out


def _entry(path):
    return json.loads(gzip.decompress(Path(path).read_bytes()))


def _legs(entry, meta):
    w = entry.get("waits") or {}
    wrand = (w.get("wmax"), w.get("wseed")) if w.get("wrand") else None
    fixed = 0 if w.get("wrand") else (w.get("fixed") or 0)
    e = entry["evt"]
    evt = (meta["anchor_linear"] & 0xFFFFF, int(e["delay"]), int(e["hold"]),
           int(e["pin"]))
    return fixed, wrand, evt


def gap_of(recs, meta, entry):
    """`sm3_nmigeom`'s own coordinate, on a FRESH capture.  Returns the whole
    triple so a moved `arm` can never be read as a moved `gap`."""
    pin = int((entry.get("evt") or {}).get("pin", -1))
    win = uf.window_of(recs)
    anchor = int(meta["anchor_linear"]) & 0xFFFFF
    arm = ng.first_t1(recs, ng.CODE, anchor, win)
    A = arm + int(entry["evt"]["delay"]) + 2 if arm >= 0 else -1
    kind, vaddr = ((ng.MEMR, ng.NMI_VEC) if pin == 1 else (ng.INTA, None))
    V = ng.first_t1(recs, kind, vaddr, win)
    nv, i = 0, 0
    while True:
        j = ng.first_t1(recs, kind, vaddr, win, i)
        if j < 0:
            break
        nv += 1
        i = j + 1
    return {"win": win, "arm": arm, "A": A, "V": V, "nvec": nv,
            "gap": (V - A) if (V >= 0 and A >= 0) else None,
            "bus_A": ng.bus_at(recs, A, win)}


def div_guard(tag, rec):
    """s13_board.div_guard's contract: PIN the divider and ask the TRANSPORT
    what it commanded.  An UNPINNED readback is a rig-integrity FINDING and is
    recorded, not smoothed."""
    r = v30run._runners.get(HOST)
    rb = (r.div_readback if r is not None
          else "div=UNKNOWN (no live serve runner to ask)")
    state = "PINNED" if ("UNPINNED" not in str(rb)
                         and "UNKNOWN" not in str(rb)) else "UNPINNED"
    print(f"  [div guard] {tag}: {rb}   -> {state}", flush=True)
    rec[tag] = {"readback": str(rb), "state": state}
    return state


def board_idle():
    img0, _ = testimage.compose(regs={}, instr=bytes([0x90]))
    check_seq.run_chip(img0, HOST, use_core=False)


# --------------------------------------------------------------------------- #
def cmd_population(a):
    pop = population(a.jobs, a.gap, a.limit)
    print(f"== the H7 pin-1 population, DERIVED: {len(pop)} seeds at gap "
          f"{a.gap if a.gap >= 0 else ('ALL (the whole pin-1 population)' if a.gap == -2 else '>13 (the non-floor CONTROL)')}")
    print("  by bank:", dict(Counter(
        r["path"].split("fuzz_bank/")[1].split("/")[0] for r in pop)))
    print("  by wait class:", dict(Counter(r["wc"] for r in pop)))
    for r in pop:
        print(f"  {r['path'].split('fuzz_bank/')[1]:<46} "
              f"{r['wc']:<8} delay={r['delay']:<4} arm={r['arm']:<5} "
              f"A={r['A']:<5} V={r['V']:<5} gap={r['gap']}")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "population.json").write_text(json.dumps(pop, indent=1) + "\n")
    return 0


def _capture_one(a, r, reps, tag, guards, log):
    """N repetitions of one banked seed at its own banked directive."""
    entry = _entry(r["path"])
    name = f"{entry['cid']}_{entry['tier']}_{entry['k']}_{entry['cfg_hash']}"
    try:
        image, meta, _g, s = uf.regen(entry)
    except Exception as ex:                                # noqa: BLE001
        print(f"  GEN-ERR {name}: {str(ex)[:120]}", flush=True)
        return "drift", None
    if s != entry["image_sha256"]:
        print(f"  GEN-DRIFT {name}: {s[:16]} != "
              f"{entry['image_sha256'][:16]}", flush=True)
        return "drift", None
    fixed, wrand, evt = _legs(entry, meta)
    out = {"name": name, "path": r["path"].split("fuzz_bank/")[1],
           "cid": entry["cid"], "k": entry["k"], "tier": entry["tier"],
           "seed": entry.get("seed"), "image_sha256": s,
           "banked": {"arm": r["arm"], "A": r["A"], "V": r["V"],
                      "gap": r["gap"], "wc": r["wc"],
                      "evt": entry["evt"], "waits": entry.get("waits")},
           "banked_rows_sha256": sha(json.dumps(entry["chip_rows"]).encode()),
           "captured_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "reps": []}
    consec = 0
    for rep in range(reps):
        try:
            recs, fired = v30run.run_image(
                bytes(image), HOST, tag=tag, use_core=False, waits=fixed,
                evt=evt, wrand=wrand, want_fired=True,
                div=v30run.DIV_OF_RECORD)
            rel = next(j for j, x in enumerate(recs) if not x["rst"])
            recs = recs[rel:]
            consec = 0
        except Exception as ex:                            # noqa: BLE001
            consec += 1
            print(f"  ERR {name} rep{rep}: {str(ex)[:120]}", flush=True)
            out["reps"].append({"rep": rep, "err": str(ex)[:200]})
            if consec >= STORM:
                return "wedge", out
            continue
        if not guards:
            div_guard("first capture", log)
            guards.append(1)
        g = gap_of(recs, meta, entry)
        g.update({"rep": rep, "fired": bool(fired), "n_rows": len(recs),
                  "rows_sha256": sha(json.dumps(recs).encode())})
        out["reps"].append(g)
        fn = OUT / "raw" / f"{name}_rep{rep}.json.gz"
        fn.write_bytes(gzip.compress(json.dumps(
            {"name": name, "rep": rep, "image_sha256": s, "evt": entry["evt"],
             "waits": entry.get("waits"), "evt_fired": bool(fired),
             "geom": g, "rows": recs}).encode()))
        (OUT / "raw" / f"{name}_rep{rep}.sha256").write_text(
            sha(fn.read_bytes()) + "\n")
    gaps = [x.get("gap") for x in out["reps"] if "gap" in x]
    print(f"  {out['path']:<46} banked={r['gap']}  reps={gaps}", flush=True)
    return "ok", out


def cmd_capture(a):
    pop = population(a.jobs, a.gap, a.limit)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "raw").mkdir(exist_ok=True)
    log = {"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "host": HOST, "reps": a.reps, "n_seeds": len(pop),
           "flash": a.flash, "use_core": False, "gap_selector": a.gap}
    print(f"capture: {len(pop)} seeds x {a.reps} reps, socket leg "
          f"(use_core=False), FLASH {a.flash}", flush=True)
    board_idle()
    guards, res = [], []
    t0 = time.time()
    for r in pop:
        st, out = _capture_one(a, r, a.reps, "h7rep", guards, log)
        if out:
            res.append(out)
        if st == "wedge":
            print("=== H7REP_WEDGE_STOP ===", flush=True)
            log["wedge"] = True
            break
    div_guard("last capture", log)
    board_idle()
    log["elapsed_s"] = round(time.time() - t0, 1)
    (OUT / a.out).write_text(json.dumps(
        {"log": log, "seeds": res}, indent=1) + "\n")
    print(f"CAPTURE: {len(res)} seeds, {log['elapsed_s']}s -> {OUT/a.out}")
    return 0


def cmd_control(a):
    ctl = controls(a.jobs, a.n)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "raw").mkdir(exist_ok=True)
    log = {"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "host": HOST, "reps": a.reps, "n_seeds": len(ctl),
           "flash": a.flash, "use_core": False, "pin": 0}
    print(f"control (pin 0): {len(ctl)} seeds x {a.reps} reps, socket leg",
          flush=True)
    board_idle()
    guards, res = [], []
    for r in ctl:
        st, out = _capture_one(a, r, a.reps, "h7ctl", guards, log)
        if out:
            res.append(out)
        if st == "wedge":
            print("=== H7REP_WEDGE_STOP ===", flush=True)
            log["wedge"] = True
            break
    div_guard("last control", log)
    board_idle()
    (OUT / "control.json").write_text(json.dumps(
        {"log": log, "seeds": res}, indent=1) + "\n")
    ok = bad = 0
    for s in res:
        for x in s["reps"]:
            if "gap" not in x:
                continue
            if x["gap"] == s["banked"]["gap"]:
                ok += 1
            else:
                bad += 1
                print(f"  CONTROL MOVED {s['path']} rep{x['rep']}: "
                      f"{x['gap']} vs banked {s['banked']['gap']}")
    print(f"CONTROL: {ok} reproduce the banked INTA gap, {bad} do not")
    return 0 if bad == 0 else 1


def cmd_report(a):
    cap = json.loads((OUT / a.out).read_bytes())
    seeds = cap["seeds"]
    print(f"== H7 REPETITION RE-CAPTURE -- {len(seeds)} seeds, "
          f"{cap['log']['reps']} reps each, FLASH {cap['log'].get('flash')}")
    allrep = Counter()
    det12 = det13 = mixed = other = 0
    for s in seeds:
        gaps = [x.get("gap") for x in s["reps"] if "gap" in x]
        allrep.update(gaps)
        u = set(gaps)
        cls = ("DET-12" if u == {FLOOR} else
               "DET-13" if u == {FLOOR + 1} else
               "MIXED" if u <= {FLOOR, FLOOR + 1} else "OTHER")
        det12 += cls == "DET-12"
        det13 += cls == "DET-13"
        mixed += cls == "MIXED"
        other += cls == "OTHER"
        n12 = sum(1 for g in gaps if g == FLOOR)
        print(f"  {s['path']:<46} banked={s['banked']['gap']}  "
              f"{cls:<7} 12-rate {n12}/{len(gaps)}  gaps={sorted(u)}")
    print(f"\n  per-repetition gap histogram: "
          f"{dict(sorted(allrep.items(), key=lambda x: (x[0] is None, x[0])))}")
    print(f"  seeds DET-12 {det12} · DET-13 {det13} · MIXED {mixed} · "
          f"OTHER {other}")
    outcome = ("(i) DETERMINISTIC -- H7 RE-OPENS" if det12 else
               "(ii) ALL 13 -- capture-era artifact" if (det13 and not mixed
                                                         and not other) else
               "(iii) MIXED -- sub-clock marginality" if (mixed and not other)
               else "(iv) SOMETHING ELSE -- report as measured")
    print(f"  REGISTERED OUTCOME: {outcome}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for nm, fn in (("population", cmd_population), ("capture", cmd_capture),
                   ("control", cmd_control), ("report", cmd_report)):
        p = sub.add_parser(nm)
        p.add_argument("--jobs", type=int, default=8)
        p.add_argument("--reps", type=int, default=10)
        p.add_argument("--n", type=int, default=10)
        p.add_argument("--flash", default="#9")
        p.add_argument("--gap", type=int, default=FLOOR,
                       help="the DERIVED population's gap; -1 = the non-floor "
                            "control (gap > 13)")
        p.add_argument("--limit", type=int, default=0)
        p.add_argument("--out", default="capture.json")
        p.set_defaults(fn=fn)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
