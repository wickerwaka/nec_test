#!/usr/bin/env python3
"""check_seq - Mission S: chip-vs-core sequence fuzzing.

For each seed: generate a program (gen_seq), compose the standard test
image around it, run it on the real chip (serve path, full capture from
RESET release), replay the SAME image in the Verilator TB (+bootimg -
no backdoor, the loader runs in the core), and diff every cycle row
from RESET release to the store's done marker.

Column policy follows check_boot (mission G): qs from release, bs from
release+8, t/ube/addr/data/ps from release+9; addr on T1 rows, data on
T2/T3 rows and T4/Ti status rows of active cycles, ps on T2 rows.

Usage:
  check_seq.py SEED [SEED...]     one-off checks
  check_seq.py --fuzz N [--start K] [--stop-after M]   campaign
  check_seq.py --sim-only SEED    TB-vs-TB plumbing self-test
"""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
import random                                          # noqa: E402
import testimage                                       # noqa: E402
from gen_seq import generate, form_universe, far_int_support  # noqa: E402
from v30run import run_image                           # noqa: E402
from fuzz_cov import Coverage, DEFAULT_COV, DEFAULT_DIV  # noqa: E402


def make_evt(seed, anchor_linear):
    """Seeded pin-event for interrupt injection: fire INT (mostly) or NMI
    at a random point after the anchor. Trigger = the anchor CODE fetch;
    the scheduler asserts at idx(trigger T1)+2+delay. Short hold so a
    level-sensitive INT releases before the handler IRETs (no re-entry).
    Returns (linear, delay, hold, pin)."""
    r = random.Random(f"int/{seed}")
    pin = 1 if r.random() < 0.25 else 0          # 0=INT (IE=1), 1=NMI
    delay = r.randrange(8, 160)
    return (anchor_linear & 0xFFFFF, delay, 2, pin)

ROOT = SW.parent
BIN = ROOT / "hdl" / "tb" / "obj_dir" / "Vtb_v30_core"
T_NAME = {0: "Ti", 1: "T1", 2: "T2", 3: "T3", 4: "Tw", 5: "T4"}
BS_NAME = {0: "INTA", 1: "IOR", 2: "IOW", 3: "HALT",
           4: "CODE", 5: "MEMR", 6: "MEMW", 7: "PASV"}
QS_NAME = {0: "-", 1: "F", 2: "E", 3: "S"}


def compose(g):
    return testimage.compose(regs=g["regs"], instr=g["instr"],
                             ram=g["ram"], ivt=g.get("ivt"))


def run_tb(image, n):
    td = tempfile.mkdtemp(prefix="seq_")
    img = Path(td) / "img.hex"
    out = Path(td) / "out.txt"
    img.write_text("\n".join(f"{b:02x}" for b in image) + "\n")
    r = subprocess.run([str(BIN), f"+bootimg={img}", f"+bootn={n}",
                        f"+out={out}"], capture_output=True, text=True,
                       cwd=ROOT, timeout=300)
    if "BOOT DONE" not in r.stdout:
        raise RuntimeError(f"TB failed: {r.stdout[-300:]} {r.stderr[-200:]}")
    sim = []
    for line in out.read_text().splitlines():
        p = line.split()
        if p and p[0] == "r":
            sim.append({"t": int(p[1]), "bs_early": int(p[2]),
                        "qs": int(p[3]), "ube_n": int(p[4]),
                        "ad_addr": int(p[5], 16), "ad_data": int(p[6], 16),
                        "ps": int(p[7], 16)})
    return sim


def run_chip(image, host, use_core=None, waits=0, evt=None):
    recs = run_image(bytes(image), host, tag="seq", use_core=use_core,
                     waits=waits, evt=evt)
    rel = next(i for i, r in enumerate(recs) if not r["rst"])
    return recs[rel:]


def done_idx(recs, key_addr, key_kind):
    """Index of the done-marker IOW T1 (+ a small tail)."""
    for i, r in enumerate(recs):
        if r.get("t", r.get("t_state")) == 1 and \
                r["bs_early"] == 2 and \
                (r["ad_addr"] & 0xFFFF) == testimage.OUT_PORT_DONE:
            return i
    return None


def diff(real, sim, limit=4000, maxprint=10, strict_qs=False):
    """Diff chip vs core per-cycle rows.
    -> (bad, first, n, flick)

    bad   = rows with a real (non-cosmetic) divergence
    flick = rows whose ONLY difference is a 1-cycle F<->S queue-status
            display flicker (Mission S class, classified as a QS-pin
            sampling artifact: any genuine execution divergence also shows
            in t/bs/addr/data/ube/ps, so a QS-only F/S disagreement with
            every other column matching is cosmetic and self-correcting).
    With strict_qs=True the flicker is folded back into bad (for
    investigation / definitive A/B confirmation).
    """
    dend = done_idx(real, None, None)
    n = min(len(real), len(sim), limit,
            (dend + 8) if dend is not None else limit)
    bad, first, flick = 0, None, 0
    for i in range(n):
        r, s = real[i], sim[i]
        rt = r.get("t_state", r.get("t"))
        qs_mm = r["qs"] != s["qs"]
        other = []
        if i >= 8 and r["bs_early"] != s["bs_early"]:
            other.append(f"bs {BS_NAME[r['bs_early']]}!="
                         f"{BS_NAME[s['bs_early']]}")
        if i >= 9:
            if rt != s["t"]:
                other.append(f"t {T_NAME.get(rt)}!={T_NAME.get(s['t'])}")
            if r["ube_n"] != s["ube_n"]:
                other.append(f"ube {r['ube_n']}!={s['ube_n']}")
            active = r["bs_early"] != 7
            # INTA cycle (bs=INTA) drives NO address on T1: AD float-retains
            # the previous bus value (interrupt_model.md), which is
            # history-dependent - the chip retains the prior fetch address,
            # the core drives its modeled vector pointer. Architecturally
            # inert (the vector rides the data lanes), so the INTA-T1 address
            # is a documented don't-care (cf. the 8F.0 ghost-read address).
            if rt == 1 and r["bs_early"] != 0 and \
                    r["ad_addr"] != s["ad_addr"]:
                other.append(f"addr {r['ad_addr']:05x}!={s['ad_addr']:05x}")
            if rt in (2, 3) and r["ad_data"] != s["ad_data"]:
                other.append(f"data {r['ad_data']:04x}!={s['ad_data']:04x}")
            if rt in (0, 5) and active and r["ad_data"] != s["ad_data"]:
                other.append(f"nxta {r['ad_data']:04x}!={s['ad_data']:04x}")
            if rt == 2 and active and r["ps"] != s["ps"]:
                other.append(f"ps {r['ps']:x}!={s['ps']:x}")
        qs_txt = (f"qs {QS_NAME[r['qs']]}!={QS_NAME[s['qs']]}"
                  if qs_mm else None)
        # F<->S queue-status flicker with nothing else wrong on the row
        is_flicker = (qs_mm and not other and not strict_qs and
                      {r["qs"], s["qs"]} == {1, 3})
        if is_flicker:
            flick += 1
            if flick <= maxprint:
                print(f"    row {i}: {qs_txt}  [QS flicker - tolerated]")
            continue
        mm = ([qs_txt] if qs_mm else []) + other
        if mm:
            bad += 1
            if first is None:
                first = i
            if bad <= maxprint:
                print(f"    row {i}: " + ", ".join(mm))
    return bad, first, n, flick


def check_seed(seed, host, sim_only=False, strict_qs=False, exts=(),
               hw_ab=False, waits=0, cov=None, div_file=None,
               inject_int=False):
    g = generate(seed, exts=exts)
    evt = None
    if inject_int:
        # force a composed IVT + IRET/RETF handler so the injected INT/NMI
        # returns cleanly and the sequence continues; fire on BOTH positions
        if g.get("ivt") is None:
            ivt, handler = far_int_support()
            g["ivt"] = ivt
            g["ram"] = g["ram"] + handler
        image, meta = compose(g)
        evt = make_evt(seed, meta["anchor_linear"])
    else:
        image, meta = compose(g)
    if hw_ab:
        # True in-silicon A/B: BOTH positions on the board (same FPGA,
        # same image). "real" = socketed chip (use_core=0); "sim" = the
        # fabric core (use_core=1). No Verilator involved.
        real = run_chip(image, host, use_core=False, waits=waits, evt=evt)
        sim = run_chip(image, host, use_core=True, waits=waits, evt=evt)
    else:
        if sim_only:
            real = run_tb(image, 4200)
            real = [dict(r, t_state=r["t"]) for r in real]
        else:
            real = run_chip(image, host, waits=waits)
        sim = run_tb(image, 4200)
    bad, first, n, flick = diff(real, sim, strict_qs=strict_qs)
    if cov is not None:
        cov.add_program(g["forms"], g["ins"], waits=waits)
        cov.add_trace(real)
    status = "MATCH" if bad == 0 else f"DIVERGE@{first}"
    extra = ""
    if bad:
        extra += f" ({bad} rows)"
    if flick:
        extra += f" [+{flick} qs-flicker]"
    print(f"seed {seed}: {g['n_ins']} ins, {n} rows compared -> {status}"
          f"{extra}")
    if bad and div_file is not None:
        # persist the divergence-triggering seed for regression
        with open(div_file, "a") as fh:
            fh.write(json.dumps({
                "seed": seed, "exts": list(exts), "waits": waits,
                "inject_int": inject_int, "hw_ab": hw_ab,
                "n_ins": g["n_ins"], "first_row": first,
                "bad_rows": bad, "flick": flick}) + "\n")
    return bad == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("seeds", nargs="*")
    ap.add_argument("--host", default="root@mister-nec")
    ap.add_argument("--fuzz", type=int, default=0)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--stop-after", type=int, default=0,
                    help="stop after M divergent seeds (0 = never)")
    ap.add_argument("--sim-only", action="store_true")
    ap.add_argument("--hw-ab", action="store_true",
                    help="true in-silicon A/B: chip (use_core=0) vs "
                         "fabric core (use_core=1), both on the board, "
                         "same image - no Verilator TB (Mission C)")
    ap.add_argument("--strict-qs", action="store_true",
                    help="count F<->S queue-status flickers as divergences "
                         "(default: classified as QS-pin sampling artifacts)")
    ap.add_argument("--exts", default="",
                    help="comma list of gen_seq EXT_MENU families "
                         "(staged expansion gates)")
    ap.add_argument("--waits", type=int, default=0,
                    help="wait-state setting for the run (0-3); with "
                         "--waits-sweep this is ignored")
    ap.add_argument("--waits-sweep", action="store_true",
                    help="vary waits 0-3 across fuzz seeds (seed k -> k%%4)")
    ap.add_argument("--cov-file", default=str(DEFAULT_COV),
                    help="coverage accumulator JSON (persists across runs)")
    ap.add_argument("--no-cov", action="store_true",
                    help="disable coverage accumulation")
    ap.add_argument("--cov-report", action="store_true",
                    help="print the coverage report from --cov-file and exit")
    ap.add_argument("--cov-reset", action="store_true",
                    help="start coverage fresh (ignore existing --cov-file)")
    ap.add_argument("--div-file", default=str(DEFAULT_DIV),
                    help="append divergence-triggering seeds here (corpus)")
    ap.add_argument("--inject-int", action="store_true",
                    help="fire a seeded INT/NMI mid-sequence on BOTH A/B "
                         "positions (composed IVT + IRET handler); stresses "
                         "recognition/REP-abort/POP-PSW-race in random ctx")
    a = ap.parse_args()

    if a.cov_report:
        c = Coverage.load(a.cov_file)
        print(c.report(universe={"form": form_universe()}))
        return 0

    exts = tuple(x for x in a.exts.split(",") if x)
    cov = None
    if not a.no_cov:
        cov = Coverage() if a.cov_reset else Coverage.load(a.cov_file)
    div_file = a.div_file
    fails = []
    if a.fuzz:
        for k in range(a.start, a.start + a.fuzz):
            w = (k % 4) if a.waits_sweep else a.waits
            ok = check_seed(f"fz{k}", a.host, a.sim_only, a.strict_qs,
                            exts, a.hw_ab, waits=w, cov=cov,
                            div_file=div_file, inject_int=a.inject_int)
            if not ok:
                fails.append(f"fz{k}")
                if a.stop_after and len(fails) >= a.stop_after:
                    break
        print(f"\nfuzz: {a.fuzz - len(fails)}/{a.fuzz} clean; "
              f"divergent seeds: {fails}")
        if cov is not None:
            cov.save(a.cov_file)
            print(f"coverage -> {a.cov_file} "
                  f"({cov.seeds} seeds, {cov.instrs} instrs, "
                  f"{len(cov.form)} forms, {len(cov.opsig)} opsigs)")
        return 1 if fails else 0
    ok = True
    for s in a.seeds:
        w = a.waits
        ok &= check_seed(s, a.host, a.sim_only, a.strict_qs, exts, a.hw_ab,
                         waits=w, cov=cov, div_file=div_file,
                         inject_int=a.inject_int)
    if cov is not None:
        cov.save(a.cov_file)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
