#!/usr/bin/env python3
"""f13_formfab -- a DIRECTED opcode form through the board, SOCKET vs FABRIC CORE.

WHY THIS EXISTS.  The two landings this sitting puts in fabric are reached by
DIFFERENT populations, and only one of them had an instrument:

  * the **8F mod=3 ghost READ** (`d1d9f168d4`) moves 25 of the 623 banked fz2
    seeds, so `fz2_w1.py capture` already scores it;
  * the **`INT.F3AA` repair** (`9c98117a03`) is NOT reachable by fz2 at all.
    `int_f3aa_repair_results` §3 measures that its arm -- an empty-tail REP
    withdrawal with the maskable pin still ASSERTED -- occurs 35 times in the
    200 `INT.F3AA` goldens and ZERO times anywhere in fz2c+fz2e.  Neither
    `x1_fabric` (HLT sweeps), `sm3_s16_fabric` (the display walk),
    `u4_tranche` (random-wait seeds) nor `check_ab_hw` (boot) reaches it.

WHAT IT DOES.  It generates cases for one `emit_suite` form from a FROZEN seed
namespace and runs **the same image twice** -- `use_core=0` (the socketed chip,
silicon truth) then `use_core=1` (the ucore in fabric) -- then diffs the two
row streams.  That is `fuzz_campaign.capture_board`'s A/B, applied to a
directed form instead of a random program.

WHY NOT COMPARE AGAINST THE v0.1 GOLDENS.  It was tried, on the board, and the
premise is REFUTED BY MEASUREMENT: fuzz-v2 T1/T2 changed `testimage.compose`
(the image is now 0xCC-filled with four carve-outs, and the body anchor moved),
so re-emitting `INT.F3AA` idx 0 today yields `ip 15116` where the golden has
`13105`, fill byte 0xCC where the golden has 0x90, and an anchor of 0x88CCC
where the golden's is 0x884F1.  **The current emitter cannot reproduce a v0.1
golden's image**, which is `sw/retired_v1.py`'s reason verbatim.  The seed maps
and offline columns from that attempt are retained beside this file as record;
nothing scores against them.

AND THE A/B IS THE BETTER COMPARATOR FOR THE GHOST READ ANYWAY.
`check_core.dontcare_cells` masks the 8F /0 mod=3 ghost address because the
chip drives it from *"a STALE internal EA/address-latch value carried in from
pre-window execution history (the harness injection stub)"* and *"a
backdoor-injected core, which never executes the injection stub, legitimately
drives the modeled SS:SP instead"*.  That don't-care is a property of the
Verilator TB's backdoor injection.  **In fabric both legs execute the same
loader from the same image**, so the ghost address is directly comparable and
the mask does not apply.  `--ghost` scores it.
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
OUT = ROOT / "sw" / "testdata" / "f13-formfab"
# The seed namespace is FROZEN here and in the pre-registration.  It is not the
# v0.1 suite's (`v30-v0.1/...`) because these are not goldens and must never be
# mistaken for them.
SEED_NS = "f13"


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
# the frozen population
# --------------------------------------------------------------------------- #
def spec_of(form):
    is_evt = form in es.EVT_FORMS
    return (es.EVT_FORMS[form] if is_evt else es.OPCODES[form]), is_evt


def gen_of(form, i):
    spec, is_evt = spec_of(form)
    rng = random.Random(f"{SEED_NS}/{form}/{i}")
    return (es.gen_evt_case(spec, rng) if is_evt
            else es.gen_case(spec, rng)), spec, is_evt


def is_mod3(case):
    b = case["instr"]
    return len(b) >= 2 and (b[1] >> 6) == 3


def freeze(form, n, mod3_only):
    """The seed indices this form's population uses.  BOARD-FREE and
    deterministic: `gen_case` is pure, so `mod3_only` is decided offline and
    the board never sees a case that is going to be thrown away."""
    out = []
    i = 0
    while len(out) < n and i < n * 20:
        try:
            case, _, _ = gen_of(form, i)
        except Exception:                                     # noqa: BLE001
            i += 1
            continue
        if (not mod3_only) or is_mod3(case):
            out.append(i)
        i += 1
    return out


def cmd_freeze(a):
    OUT.mkdir(parents=True, exist_ok=True)
    for form in a.form:
        ks = freeze(form, a.n, a.mod3)
        p = OUT / f"{form}.pop.json"
        p.write_text(json.dumps({"form": form, "seed_ns": SEED_NS,
                                 "n": len(ks), "mod3_only": bool(a.mod3),
                                 "k": ks}, indent=1) + "\n")
        print(f"{form}: {len(ks)} seeds frozen (mod3_only={bool(a.mod3)}) "
              f"-> {p.name}")
    return 0


def load_pop(form):
    p = OUT / f"{form}.pop.json"
    if not p.exists():
        raise SystemExit(f"f13_formfab: no frozen population for {form}; "
                         "run `freeze` first")
    return json.loads(p.read_text())["k"]


# --------------------------------------------------------------------------- #
# capture -- SOCKET FIRST, then the fabric core, SAME IMAGE
# --------------------------------------------------------------------------- #
def _emit(form, i, host, waits, use_core):
    case, spec, is_evt = gen_of(form, i)
    pn = 2 if i % 2 == 1 else 0
    es.EMIT_USE_CORE = bool(use_core)
    if is_evt:
        return es.emit_evt_case(spec, case, host, tag=f"f13{form}",
                                preload_n=pn, waits=waits)
    return es.emit_case(spec, case, host, tag=f"f13{form}",
                        preload_n=pn, waits=waits)


def cmd_capture(a):
    OUT.mkdir(parents=True, exist_ok=True)
    rec = {"leg": a.leg, "host": a.host, "git": git_head(), "waits": a.waits,
           "seed_ns": SEED_NS,
           "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "div_guards": [], "forms": {}}
    div_guard(f"{a.leg}-start", rec["div_guards"])
    rc = 0
    for form in a.form:
        ks = load_pop(form)
        out, errs = {}, []
        t0 = time.time()
        div_guard(f"{a.leg}-{form}-pre", rec["div_guards"])
        for i in ks:
            try:
                chip = _emit(form, i, a.host, a.waits, 0)
                core = _emit(form, i, a.host, a.waits, 1)
            except Exception as e:                            # noqa: BLE001
                errs.append([i, str(e)[:160]])
                print(f"  ERR {form}/{i}: {str(e)[:110]}", flush=True)
                continue
            finally:
                es.EMIT_USE_CORE = False
            out[i] = {"chip": chip, "core": core}
        div_guard(f"{a.leg}-{form}-post", rec["div_guards"])
        blob = json.dumps({str(k): v for k, v in out.items()}).encode()
        fn = OUT / f"{form}.{a.leg}.json.gz"
        fn.write_bytes(gzip.compress(blob))
        sha = hashlib.sha256(blob).hexdigest()
        rec["forms"][form] = {"n_asked": len(ks), "n_pairs": len(out),
                              "errors": errs, "rows_file": fn.name,
                              "sha256": sha,
                              "seconds": round(time.time() - t0, 1)}
        print(f"  {form}: {len(out)}/{len(ks)} A/B pairs, {len(errs)} errors, "
              f"{time.time()-t0:.0f}s  sha256 {sha[:16]}…", flush=True)
        if errs:
            rc = 1
    div_guard(f"{a.leg}-end", rec["div_guards"])
    rec["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    rec["div_guards_unpinned"] = [d["tag"] for d in rec["div_guards"]
                                  if d["state"] != "PINNED"]
    p = OUT / f"capture_{a.leg}.json"
    if p.exists():
        old = json.loads(p.read_text())
        old["forms"].update(rec["forms"])
        old["div_guards"] += rec["div_guards"]
        old["div_guards_unpinned"] = sorted(
            set(old.get("div_guards_unpinned", []))
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
def _load(form, leg):
    fn = OUT / f"{form}.{leg}.json.gz"
    if not fn.exists():
        raise SystemExit(f"f13_formfab: missing {fn}")
    return {int(k): v for k, v in
            json.loads(gzip.decompress(fn.read_bytes())).items()}


def _memr(t):
    return [(i, r[1], r[6]) for i, r in enumerate(t["cycles"]) if r[7] == "MEMR"]


def cmd_score(a):
    summary = {"leg": a.leg, "forms": {}}
    for form in a.form:
        d = _load(form, a.leg)
        tot = ok = 0
        fails = []
        for i in sorted(d):
            chip, core = d[i]["chip"], d[i]["core"]
            tot += 1
            mm, _m = cc.diff_rows(chip["cycles"], core["cycles"])
            if not mm:
                ok += 1
            else:
                fails.append([i, mm[0][0],
                              cc.COL_NAME.get(mm[0][1], str(mm[0][1])),
                              len(mm)])
        print(f"=== {form} [{a.leg}] CORE vs CHIP, rows: {ok}/{tot} identical")
        f = {"exact": ok, "total": tot, "first_div": fails}
        if a.ghost:
            gr = {"n": 0, "eq": 0, "core_eq_sssp": 0, "chip_eq_sssp": 0,
                  "per_seed": {}}
            for i in sorted(d):
                chip, core = d[i]["chip"], d[i]["core"]
                gc, cc_ = _memr(chip), _memr(core)
                if len(gc) != 1 or len(cc_) != 1:
                    continue
                gr["n"] += 1
                r0 = chip["initial"]["regs"]
                sssp = ((r0["ss"] << 4) + r0["sp"]) & 0xFFFFF
                eq = ((cc_[0][1] & 0xFFFFF, cc_[0][2])
                      == (gc[0][1] & 0xFFFFF, gc[0][2]))
                gr["eq"] += int(eq)
                gr["core_eq_sssp"] += int((cc_[0][1] & 0xFFFFF) == sssp)
                gr["chip_eq_sssp"] += int((gc[0][1] & 0xFFFFF) == sssp)
                gr["per_seed"][i] = {"chip": [gc[0][1], gc[0][2]],
                                     "core": [cc_[0][1], cc_[0][2]],
                                     "ss_sp": sssp, "eq": eq}
            print(f"    GHOST row (addr+data), core vs chip: "
                  f"{gr['eq']}/{gr['n']}   "
                  f"core==SS:SP {gr['core_eq_sssp']}, "
                  f"chip==SS:SP {gr['chip_eq_sssp']}")
            f["ghost"] = gr
        summary["forms"][form] = f
    (OUT / f"score_{a.leg}.json").write_text(json.dumps(summary, indent=1)
                                             + "\n")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    s = ap.add_subparsers(dest="cmd", required=True)

    c = s.add_parser("freeze", help="the frozen seed population (BOARD-FREE)")
    c.add_argument("--form", action="append", required=True)
    c.add_argument("--n", type=int, required=True)
    c.add_argument("--mod3", action="store_true",
                   help="keep only mod=3 encodings (the 8F ghost population)")
    c.set_defaults(fn=cmd_freeze)

    c = s.add_parser("capture", help="one A/B leg: socket then fabric core")
    c.add_argument("--form", action="append", required=True)
    c.add_argument("--leg", required=True)
    c.add_argument("--host", default=HOST)
    c.add_argument("--waits", type=int, default=0)
    c.set_defaults(fn=cmd_capture)

    c = s.add_parser("score", help="core vs chip, rows (+ --ghost)")
    c.add_argument("--form", action="append", required=True)
    c.add_argument("--leg", required=True)
    c.add_argument("--ghost", action="store_true")
    c.set_defaults(fn=cmd_score)

    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
