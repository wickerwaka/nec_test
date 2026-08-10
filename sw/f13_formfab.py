#!/usr/bin/env python3
"""f13_formfab -- a v0.1 GOLDEN FORM through the board, socket OR fabric core.

WHY THIS EXISTS.  The two landings this sitting puts in fabric are reached by
DIFFERENT populations, and only one of them had an instrument:

  * the **8F ghost READ** (`d1d9f168d4`) is measurable on the fz2 corpus --
    `fz2_w1.py capture` already scores it, chip leg against fabric-core leg;
  * the **`INT.F3AA` repair** (`9c98117a03`) is NOT.  `int_f3aa_repair_results`
    §3 measures that the repaired arm (an empty-tail REP withdrawal with the
    maskable pin still ASSERTED) occurs 35 times in the 200 `INT.F3AA` goldens
    and **zero times anywhere in fz2c+fz2e**.  The corpus cannot see it.  The
    only population that reaches the mechanism is the golden form itself.

`x1_fabric.py` and `sm3_s16_fabric.py` are this file's shape -- re-run a frozen
golden population through `use_core=1` and diff rows against the golden -- but
both are hard-wired to their own EVT sweeps.  This is the same shape applied to
an arbitrary v0.1 form.

THE GOLDENS ARE NOT TOUCHED.  `emit_suite.EMIT_USE_CORE` is the pin that says a
golden comes from the socket and from nothing else; this file flips it for its
own DUT capture and writes into `sw/testdata/f13-formfab/`.  It never writes
`tests/v30/`.

HOW A CASE IS REPRODUCED, AND WHY IT IS CHECKED RATHER THAN ASSUMED.
`emit_suite.cmd_emit` draws case *i* from `random.Random(f"{base}/{op}/{i}")`
and, when a case fails to compose or place, SKIPS TO THE NEXT SEED -- so output
index `idx` and seed index `i` diverge, and `tests/v30/v0.1` predates the
`{op}.seeds.json` sidecar that would record the map.  Worse, the skip condition
("pf assert before window") is a race and `emit_log.txt` holds TWO passes with
DIFFERENT reroll sets, so the map cannot be read off the log either.

`map` therefore recovers it OFFLINE and by content: `gen_case` / `gen_evt_case`
are pure, so every candidate seed is generated and matched against the golden's
own `initial.regs`.  `capture` then re-emits with the mapped seed and CHECKS
that the emitted case's `initial` and `bytes` equal the golden's.  An index
that does not match is `INVALID` and is NOT SCORED -- never quietly rerolled
onto a different case, which is how a comparator ends up scoring two different
programs against each other.

THE 8F.0 GHOST COLUMN.  `check_core.diff_rows` MASKS the 8F /0 mod=3 ghost
read's address and data -- a documented golden-schema don't-care since
2026-07-13 (`closure_checkpoint.md`), which is why `check_core --opcodes 8F.0`
reads 500/500 both before and after the ghost-read landing.  `score --ghost`
lifts the mask on exactly those rows and compares the ghost address/data
UNMASKED, core against socket and core against golden.  That is the only
comparator on this population that can see the mechanism at all.
"""
import argparse
import gzip
import hashlib
import json
import random
import subprocess
import sys
import time
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

import emit_suite as es                                      # noqa: E402
import check_core as cc                                      # noqa: E402
import testimage as ti                                       # noqa: E402
import v30run                                                # noqa: E402
import check_seq                                             # noqa: E402

HOST = "root@mister-nec"
SUITE = ROOT / "tests" / "v30" / "v0.1"
OUT = ROOT / "sw" / "testdata" / "f13-formfab"
SEED_BASE = "v30-v0.1"
REG_KEYS = ("ax", "cx", "dx", "bx", "sp", "bp", "si", "di",
            "cs", "ds", "es", "ss", "flags")


# --------------------------------------------------------------------------- #
# board discipline
# --------------------------------------------------------------------------- #
def div_guard(tag, rec=None):
    """s13_board.div_guard's contract, in fz2_w1's words: PIN the divider, then
    ask the TRANSPORT what it commanded and record the answer.  UNPINNED is a
    rig-integrity FINDING -- recorded, not smoothed."""
    img, _ = ti.compose(regs={}, instr=bytes([0x90]))
    v30run.run_image(bytes(img), HOST, tag="f13div", waits=0, use_core=False,
                     div=v30run.DIV_OF_RECORD)
    r = v30run._runners.get(HOST)
    rb = (r.div_readback if r is not None
          else "div=UNKNOWN (no live serve runner to ask)")
    state = "PINNED" if ("UNPINNED" not in str(rb)
                         and "UNKNOWN" not in str(rb)) else "UNPINNED"
    print(f"  [div guard] {tag}: {rb}   -> {state}", flush=True)
    if state != "PINNED":
        print("  [div guard] *** UNPINNED READBACK -- recorded, not smoothed "
              "***", flush=True)
    d = {"tag": tag, "readback": str(rb), "state": state,
         "rig": getattr(r, "rig_readback", None),
         "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    if rec is not None:
        rec.append(d)
    return d


def board_idle():
    img, _ = ti.compose(regs={}, instr=bytes([0x90]))
    check_seq.run_chip(img, HOST, use_core=False)


def git_head():
    return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True).stdout.strip()


# --------------------------------------------------------------------------- #
# the goldens, and the seed map
# --------------------------------------------------------------------------- #
def golden(form):
    return json.load(gzip.open(SUITE / f"{form}.json.gz"))


def spec_of(form):
    is_evt = form in es.EVT_FORMS
    return (es.EVT_FORMS[form] if is_evt else es.OPCODES[form]), is_evt


def gen_of(form, sd):
    spec, is_evt = spec_of(form)
    rng = random.Random(sd)
    return es.gen_evt_case(spec, rng) if is_evt else es.gen_case(spec, rng)


def build_map(form, extra=120, rerolls=16):
    """{idx: seed-string}, recovered by CONTENT.  Ambiguous and unmatched
    indices are returned separately and are never guessed."""
    g = golden(form)
    n = len(g)
    sig = {}
    cands = [f"{SEED_BASE}/{form}/{i}" for i in range(n + extra)]
    for idx in range(n):
        cands += [f"{SEED_BASE}/{form}/{idx}/{r}" for r in range(1, rerolls + 1)]
    for sd in cands:
        try:
            c = gen_of(form, sd)
        except Exception:                                     # noqa: BLE001
            continue
        key = tuple(c["regs"][k] for k in REG_KEYS)
        sig.setdefault(key, []).append(sd)
    m, amb, miss = {}, [], []
    for t in g:
        key = tuple(t["initial"]["regs"][k] for k in REG_KEYS)
        v = sig.get(key)
        if not v:
            miss.append(t["idx"])
        elif len(v) > 1:
            amb.append(t["idx"])
        else:
            m[t["idx"]] = v[0]
    return m, amb, miss


def map_path(form):
    return OUT / f"{form}.seedmap.json"


def cmd_map(a):
    OUT.mkdir(parents=True, exist_ok=True)
    for form in a.form:
        m, amb, miss = build_map(form)
        map_path(form).write_text(json.dumps(
            {"form": form, "seed_base": SEED_BASE, "n_golden": len(golden(form)),
             "map": m, "ambiguous": amb, "unmatched": miss}, indent=1) + "\n")
        print(f"{form}: {len(m)} of {len(golden(form))} indices mapped, "
              f"{len(amb)} ambiguous, {len(miss)} unmatched -> "
              f"{map_path(form).name}")
    return 0


def load_map(form):
    p = map_path(form)
    if not p.exists():
        raise SystemExit(f"f13_formfab: no seed map for {form}; run `map` first")
    d = json.loads(p.read_text())
    return {int(k): v for k, v in d["map"].items()}


# --------------------------------------------------------------------------- #
# capture
# --------------------------------------------------------------------------- #
def _emit(form, idx, sd, host, waits):
    spec, is_evt = spec_of(form)
    pn = 2 if idx % 2 == 1 else 0
    case = gen_of(form, sd)
    if is_evt:
        t = es.emit_evt_case(spec, case, host, tag=f"f13{form}",
                             preload_n=pn, waits=waits)
    else:
        t = es.emit_case(spec, case, host, tag=f"f13{form}",
                         preload_n=pn, waits=waits)
    t["idx"] = idx
    return t


def cmd_capture(a):
    OUT.mkdir(parents=True, exist_ok=True)
    es.EMIT_USE_CORE = bool(a.use_core)
    print(f"leg {a.leg}: emit_suite.EMIT_USE_CORE = {es.EMIT_USE_CORE} "
          f"({'the FPGA core' if a.use_core else 'the SOCKET -- rig control'})"
          f", NOT a golden emission", flush=True)
    rec = {"leg": a.leg, "use_core": bool(a.use_core), "host": a.host,
           "git": git_head(), "waits": a.waits,
           "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "div_guards": [], "forms": {}}
    div_guard(f"{a.leg}-start", rec["div_guards"])
    rc = 0
    for form in a.form:
        g = {t["idx"]: t for t in golden(form)}
        m = load_map(form)
        idxs = sorted(m) if not a.idxs else [i for i in a.idxs if i in m]
        out, valid, invalid, errs = {}, [], [], []
        t0 = time.time()
        div_guard(f"{a.leg}-{form}-pre", rec["div_guards"])
        for idx in idxs:
            try:
                t = _emit(form, idx, m[idx], a.host, a.waits)
            except Exception as e:                            # noqa: BLE001
                errs.append([idx, str(e)[:160]])
                print(f"  ERR {form}/{idx}: {str(e)[:110]}", flush=True)
                continue
            ok = (t["initial"] == g[idx]["initial"]
                  and list(t["bytes"]) == list(g[idx]["bytes"]))
            (valid if ok else invalid).append(idx)
            t["_valid"] = ok
            out[idx] = t
        div_guard(f"{a.leg}-{form}-post", rec["div_guards"])
        blob = json.dumps({str(k): v for k, v in out.items()}).encode()
        fn = OUT / f"{form}.{a.leg}.json.gz"
        fn.write_bytes(gzip.compress(blob))
        sha = hashlib.sha256(blob).hexdigest()
        rec["forms"][form] = {"n_asked": len(idxs), "n_captured": len(out),
                              "valid": len(valid), "invalid": invalid,
                              "errors": errs, "rows_file": fn.name,
                              "sha256": sha,
                              "seconds": round(time.time() - t0, 1)}
        print(f"  {form}: {len(out)}/{len(idxs)} captured, {len(valid)} valid, "
              f"{len(invalid)} invalid, {len(errs)} errors, "
              f"{time.time()-t0:.0f}s  sha256 {sha[:16]}…", flush=True)
        if errs:
            rc = 1
    div_guard(f"{a.leg}-end", rec["div_guards"])
    rec["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    rec["div_guards_unpinned"] = [d["tag"] for d in rec["div_guards"]
                                  if d["state"] != "PINNED"]
    # One leg may be captured in several invocations (one per form, because
    # `--idxs` is a single list).  MERGE rather than overwrite, so the record
    # of a leg is the record of the whole leg.
    p = OUT / f"capture_{a.leg}.json"
    if p.exists():
        old = json.loads(p.read_text())
        old["forms"].update(rec["forms"])
        old["div_guards"] += rec["div_guards"]
        old["div_guards_unpinned"] = sorted(set(old.get("div_guards_unpinned", []))
                                            | set(rec["div_guards_unpinned"]))
        old["finished"] = rec["finished"]
        rec = old
    p.write_text(json.dumps(rec, indent=1) + "\n")
    if rec["div_guards_unpinned"]:
        print("*** UNPINNED div readback(s): "
              f"{rec['div_guards_unpinned']} -- RIG-INTEGRITY FINDING ***")
        return 3
    return rc


# --------------------------------------------------------------------------- #
# score
# --------------------------------------------------------------------------- #
def _load_leg(form, leg):
    fn = OUT / f"{form}.{leg}.json.gz"
    if not fn.exists():
        raise SystemExit(f"f13_formfab: missing {fn}")
    return {int(k): v for k, v in
            json.loads(gzip.decompress(fn.read_bytes())).items()}


def _ghost_rows(t):
    """The MEMR rows of a capture's window, as (row, addr, data)."""
    out = []
    for i, r in enumerate(t["cycles"]):
        if r[7] == "MEMR":
            out.append((i, r[1], r[6]))
    return out


def cmd_score(a):
    summary = {"leg": a.leg, "ref": a.ref, "forms": {}}
    for form in a.form:
        g = {t["idx"]: t for t in golden(form)}
        dut = _load_leg(form, a.leg)
        ref = _load_leg(form, a.ref) if a.ref else None
        tot = ok = 0
        fails = []
        for idx in sorted(dut):
            t = dut[idx]
            if not t.get("_valid"):
                continue
            tot += 1
            mm, _m = cc.diff_rows(g[idx]["cycles"], t["cycles"])
            # the SAME documented don't-care filter `check_core.check_case`
            # applies, so this column is on `check_core`'s scale.  `--ghost`
            # below is the one that lifts it.
            dc = cc.dontcare_cells(g[idx])
            if dc:
                mm = [m for m in mm if (m[0], m[1]) not in dc]
            if not mm:
                ok += 1
            else:
                fails.append([idx, mm[0][0],
                              cc.COL_NAME.get(mm[0][1], str(mm[0][1]))])
        print(f"=== {form} [{a.leg}] rows-only vs the GOLDEN: {ok}/{tot}")
        f = {"exact": ok, "total": tot, "first_div": fails}
        if a.ghost:
            gr = {"n": 0, "core_eq_golden": 0, "core_eq_ref": 0,
                  "ref_eq_golden": 0, "dut_eq_sssp": 0, "per_idx": {}}
            for idx in sorted(dut):
                t = dut[idx]
                if not t.get("_valid"):
                    continue
                gg = _ghost_rows(g[idx])
                dd = _ghost_rows(t)
                if len(gg) != 1 or len(dd) != 1:
                    continue
                gr["n"] += 1
                rr = None
                if ref is not None and idx in ref and ref[idx].get("_valid"):
                    r2 = _ghost_rows(ref[idx])
                    rr = r2[0] if len(r2) == 1 else None
                eq_g = (dd[0][1], dd[0][2]) == (gg[0][1], gg[0][2])
                gr["core_eq_golden"] += int(eq_g)
                if rr is not None:
                    gr["core_eq_ref"] += int((dd[0][1], dd[0][2])
                                             == (rr[1], rr[2]))
                    gr["ref_eq_golden"] += int((rr[1], rr[2])
                                               == (gg[0][1], gg[0][2]))
                r0 = g[idx]["initial"]["regs"]
                sssp = ((r0["ss"] << 4) + r0["sp"]) & 0xFFFFF
                gr["dut_eq_sssp"] += int((dd[0][1] & 0xFFFFF) == sssp)
                gr["per_idx"][idx] = {
                    "golden": [gg[0][1], gg[0][2]], "dut": [dd[0][1], dd[0][2]],
                    "ref": ([rr[1], rr[2]] if rr else None), "ss_sp": sssp}
            print(f"    GHOST (mask lifted): {gr['n']} single-MEMR cases; "
                  f"dut==golden {gr['core_eq_golden']}, "
                  f"dut==ref {gr['core_eq_ref']}, "
                  f"ref==golden {gr['ref_eq_golden']}, "
                  f"dut==SS:SP {gr['dut_eq_sssp']}")
            f["ghost"] = gr
        summary["forms"][form] = f
    (OUT / f"score_{a.leg}.json").write_text(json.dumps(summary, indent=1)
                                             + "\n")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    s = ap.add_subparsers(dest="cmd", required=True)

    c = s.add_parser("map", help="recover idx->seed OFFLINE, by content")
    c.add_argument("--form", action="append", required=True)
    c.set_defaults(fn=cmd_map)

    c = s.add_parser("capture", help="one board leg")
    c.add_argument("--form", action="append", required=True)
    c.add_argument("--leg", required=True)
    c.add_argument("--use-core", type=int, required=True, choices=(0, 1))
    c.add_argument("--host", default=HOST)
    c.add_argument("--waits", type=int, default=0)
    c.add_argument("--idxs", type=lambda s: [int(x) for x in s.split(",")],
                   default=None)
    c.set_defaults(fn=cmd_capture)

    c = s.add_parser("score", help="rows-only vs the golden (+ --ghost)")
    c.add_argument("--form", action="append", required=True)
    c.add_argument("--leg", required=True)
    c.add_argument("--ref", default="", help="a second leg, for --ghost")
    c.add_argument("--ghost", action="store_true")
    c.set_defaults(fn=cmd_score)

    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
