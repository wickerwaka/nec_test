#!/usr/bin/env python3
"""wrfuzz_smoke -- the OFFLINE plumbing proof for the per-access wait-vector
axis (task #38, W0).  **NON-GATE.  IT MEASURES NOTHING ABOUT SILICON.**

WHAT IT IS FOR.  Before W1 buys board time, the whole path
`generation -> vector application -> scoring` must be shown to work end to
end, on BOTH offline engines, with no board anywhere.  A vector axis has four
independent places to fail silently (see `sw/wvec_shapes.py`'s properties
(1)-(4)), so this harness asserts the one thing that catches all four at once:

    THE WAITS THE ENGINE ACTUALLY TOOK, READ OFF ITS OWN PIN ROWS, ARE THE
    WAITS THE VECTOR ASKED FOR -- per bus cycle, in both engines.

That is `ucore_provenance.md` §68.6's bar R0 (45,699/45,699 = 100.0 % on the
socket), computed offline against the model and the RTL core instead of the
chip.  It needs no golden and no capture: the vector is the reference.

WHAT IT IS NOT.  It is **not** a comparison of the two engines against each
other and **not** a correctness measurement of either.  The engine-vs-engine
row agreement is printed as an OBSERVATION with its denominator, because a
number printed without one is how a plumbing script turns into a quoted
result.  These seeds are marked NON-GATE in the report and no ratchet, no
`standing_gates.md` entry and no verdict may cite them.

Usage:
    python3 sw/wrfuzz_smoke.py --cid wrsmoke --n 20 [--core ucore]
                               [--report out.json]
"""
import argparse
import json
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

import fuzz_campaign as fzc                               # noqa: E402
import simbin                                             # noqa: E402
import timed_fuzz as tf                                   # noqa: E402
import wvec_shapes as wv                                  # noqa: E402

ROWS = 4200


def run_sim(image, vec, nrows, td):
    img = Path(td) / "img.bin"
    img.write_bytes(bytes(image))
    argv = [str(simbin.SIM), "timed-boot", str(tf.ROM), str(img),
            f"--clocks={nrows}", "--ndjson",
            f"--wvec={wv.write_sim(Path(td) / 'wvec_sim.txt', vec)}"]
    p = subprocess.run(argv, capture_output=True, timeout=600)
    rows = []
    for line in p.stdout.decode().splitlines():
        if line.startswith("{"):
            o = json.loads(line)
            if "t" in o:
                rows.append(o)
    return rows, p.stderr.decode()[-200:]


def run_tb(image, vec, nrows, td, core):
    """The RTL leg, invoking the NAMED core's binary DIRECTLY.

    ⚠ IT DOES NOT GO THROUGH `check_seq.run_tb`, AND THE FIRST VERSION OF THIS
    FILE DID.  `check_seq.CORE` is **`"fsm"`**, pinned there deliberately
    (`check_seq.py` §60: the gates that reach the TB through it are ARCHIVED
    on-demand gates whose registered figures are FSM figures, so migrating the
    plumbing must not move the engine).  So `check_seq.run_tb` builds and runs
    the **archived FSM core** whatever `--core` this harness was given, while
    this harness asserted and PRINTED the `ucore`'s receipt beside it.  That is
    `standing_gates.md`'s own meta-pattern -- *the gate ran against bytes
    nobody proved were the bytes it named* -- and it was caught in the sitting
    that wrote it, by the receipt line disagreeing with the binary the build
    log had just rebuilt.  See `wrfuzz_provenance.md` §1.4 F-4.

    The postcondition below is the part that makes the fix non-vacuous: the
    binary this function ran is asserted to BE the one the caller named."""
    binp = tf.tb_bin(core)
    img = Path(td) / "img.hex"
    outp = Path(td) / "out.txt"
    img.write_text("\n".join(f"{b:02x}" for b in bytes(image)) + "\n")
    argv = [str(binp), f"+bootimg={img}", f"+bootn={nrows}", "+mirror=1",
            f"+out={outp}",
            # HEX: the TB reads +wvec with $readmemh.  The model's file is
            # DECIMAL and the two are not interchangeable (wvec_shapes (1)).
            f"+wvec={wv.write_tb(Path(td) / 'wvec_tb.hex', vec)}"]
    p = subprocess.run(argv, capture_output=True, timeout=600)
    so = p.stdout.decode()
    if "BOOT DONE" not in so:
        raise RuntimeError(f"TB failed: {so[-200:]} {p.stderr.decode()[-160:]}")
    rows = []
    for line in outp.read_text().splitlines():
        f = line.split()
        if f and f[0] == "r":
            rows.append({"t": int(f[1]), "bs_early": int(f[2]),
                         "qs": int(f[3]), "ube_n": int(f[4]),
                         "ad_addr": int(f[5], 16), "ad_data": int(f[6], 16),
                         "ps": int(f[7], 16)})
    return rows, ""


def one(cid, k, ov, core, td):
    cfg = fzc.derive_case(cid, k, ov)
    g = fzc.build(cfg)
    image, _meta = fzc.compose_case(g, cfg)
    vec = fzc.wvec_of(cfg)
    out = {"seed": f"{cid}/{k}", "tier": cfg["tier"], "cfg_hash": cfg["cfg_hash"],
           "wvec": cfg["wvec"], "wvec_sha256": wv.sha256_of(vec),
           "nmax_eff": cfg["nmax_eff"],
           "bad_0f_pairs": fzc.bad_0f_pairs(image), "nongate": True}
    for name, fn in (("sim", lambda: run_sim(image, vec, ROWS, td)),
                     (core, lambda: run_tb(image, vec, ROWS, td, core))):
        t0 = time.time()
        try:
            rows, err = fn()
        except Exception as e:                             # noqa: BLE001
            out[name] = {"error": str(e)[:200]}
            continue
        m, n, first_bad = wv.applied_score(rows, vec)
        out[name] = {"rows": len(rows), "cycles": wv.bus_cycle_bound(rows),
                     "applied": m, "applied_of": n,
                     "first_bad": first_bad, "err": err.strip()[:120],
                     "secs": round(time.time() - t0, 2)}
    # OBSERVATION ONLY: how far the two engines agree, with its denominator.
    a, b = out.get("sim", {}), out.get(core, {})
    if "rows" in a and "rows" in b:
        out["obs_engine_rows"] = [a["rows"], b["rows"]]
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cid", default="wrsmoke")
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--core", default="ucore", choices=("ucore", "fsm"))
    ap.add_argument("--shapes", default=",".join(wv.SHAPES))
    ap.add_argument("--report", default="")
    a = ap.parse_args()
    if a.n > 20:
        sys.exit("wrfuzz_smoke: the smoke population is capped at 20 seeds -- "
                 "it is a plumbing proof, not a measurement")
    simbin.ensure(why="wrfuzz_smoke")
    import artifact as art                                 # noqa: PLC0415
    binp = tf.tb_bin(a.core)
    art.require(binp, why=f"wrfuzz_smoke --core {a.core}")
    # THE POSTCONDITION (F-4): the receipt printed below must belong to the
    # binary this run will actually execute.  `.exists()` is the test the
    # vacuous-gate pattern passes; naming the path that `run_tb` invokes is
    # the one it does not.
    assert str(binp).endswith(
        "obj_dir/Vtb_v30_core" if a.core == "fsm"
        else f"obj_dir_{a.core}/Vtb_v30_core"), binp
    print(f"wrfuzz_smoke: NON-GATE.  {a.n} seeds, engines = the timed model "
          f"and the {a.core} RTL core")
    print(f"  RTL leg {art.relpath(binp)} receipt "
          f"{str(art.receipt_id(binp))[:16]}…  "
          f"(invoked DIRECTLY -- check_seq.CORE is pinned to 'fsm')",
          flush=True)

    ov = {"wvec_shapes": [s for s in a.shapes.split(",") if s],
          "no8080": True, "no_evt": True}
    res = []
    with tempfile.TemporaryDirectory() as td:
        for k in range(a.n):
            r = one(a.cid, k, ov, a.core, td)
            res.append(r)
            s, c = r.get("sim", {}), r.get(a.core, {})
            print(f"  {r['seed']:<14} {r['tier']:<4} "
                  f"{r['wvec']['shape']:<6} "
                  f"sim {s.get('applied')}/{s.get('applied_of')} "
                  f"{a.core} {c.get('applied')}/{c.get('applied_of')} "
                  f"cyc {s.get('cycles')}/{c.get('cycles')} "
                  f"brkem {r['brkem_pairs']}", flush=True)

    def tot(name, key):
        return sum((r.get(name) or {}).get(key) or 0 for r in res)

    print("\n== THE PLUMBING BARS (offline; NON-GATE seeds) ==")
    ok = True
    for name in ("sim", a.core):
        m, n = tot(name, "applied"), tot(name, "applied_of")
        errs = sum(1 for r in res if "error" in (r.get(name) or {}))
        pct = 100.0 * m / max(1, n)
        print(f"  {name:<6} vector APPLIED {m}/{n} = {pct:.2f} %   "
              f"engine errors {errs}")
        ok &= (m == n and n > 0 and errs == 0)
    over = [r["seed"] for r in res
            if max((r.get(nm) or {}).get("cycles") or 0
                   for nm in ("sim", a.core)) >= wv.NWVEC]
    print(f"  bus-cycle bound (< {wv.NWVEC}): "
          f"{'OK' if not over else 'EXCEEDED ' + str(over)}")
    ok &= not over
    pairs = sum(r["brkem_pairs"] for r in res)
    print(f"  BRKEM `0F FF` pairs in the composed images: {pairs}")
    ok &= (pairs == 0)
    print(f"  shapes exercised: "
          f"{dict(Counter(r['wvec']['shape'] for r in res))}")
    print(f"  tiers exercised:  {dict(Counter(r['tier'] for r in res))}")
    print(f"\nSMOKE {'PASS' if ok else 'FAIL'}  "
          f"(NON-GATE: this proves the path, not the part)")
    if a.report:
        Path(a.report).write_text(json.dumps(
            {"nongate": True, "cid": a.cid, "core": a.core, "ov": ov,
             "note": "plumbing proof for task #38 W0; not a measurement of "
                     "silicon and not citable as a ratchet",
             "seeds": res}, indent=1))
        print(f"  report -> {a.report}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
