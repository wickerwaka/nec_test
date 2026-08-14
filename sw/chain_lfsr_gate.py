#!/usr/bin/env python3
"""chain_lfsr_gate -- THE STANDING CHAIN-DEPTH FALSIFIER.

WHY.  `v30u_eu.sv`'s `CHAIN_MAX` is a BOUND ON A CLAIM: no more than N of the
model's zero-cost steps ever ride one clock.  Three sources agree the true
maximum occupancy is 6 (`ucore_provenance.md` sec.51.2's transition graph plus
its (position, state) census; `m72_downstream_timing_2026-08-12.md` sec.3's
independent re-derivation; and that report's own LFSR harness, which existed in
neither repo).  **None of those is a gate.**  The gate is the `CHAIN OVERFLOW`
$fatal at `v30u_eu.sv:3763`, and a $fatal is only evidence over stimulus that
could have fired it.

`hdl/tb/tb_chain_lfsr.sv` is that stimulus: an all-LFSR environment -- LFSR
memory, LFSR READY, LFSR INT/NMI/POLL_N, and a CE train whose gaps are
LFSR-drawn, built to the ce/ce_half contract (Reading B) and to nothing
narrower.  It executes ARBITRARY BYTES, not 347 known forms.

USAGE
    python3 sw/chain_lfsr_gate.py                 # the gate: 4 seeds x 400k
    python3 sw/chain_lfsr_gate.py --build         # force a rebuild first
    python3 sw/chain_lfsr_gate.py --nonvacuity    # H-3: CHAIN_MAX=4 must FATAL
    python3 sw/chain_lfsr_gate.py --sig-ref F     # require signatures == F

EXIT
    0  every seed ran, depth <= CHAIN_MAX-1, 0 overflows, train at minimum gap
    1  a registered bar MISSED
    2  the run could not be made (build failure, missing tool)

THE BARS (`docs/notes/timing50_chainmax_prereg_2026-08-12.md` sec.3.1)
    H-1  depth <= 6 on every seed, 0 CHAIN OVERFLOW
    H-2  the CE train reaches the contract MINIMUM gap (g=0) >= 1,000 times per
         seed, and `ce & ce_half` coincide 0 times
    H-3  --nonvacuity: at CHAIN_MAX = 4 the $fatal FIRES
    H-4  --sig-ref: the 64-bit output signature is byte-identical to a named
         reference, seed for seed
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))
import artifact as art                                       # noqa: E402

TB_DIR = ROOT / "hdl" / "tb"
UCORE = ROOT / "hdl" / "rtl" / "ucore"
OBJ = TB_DIR / "obj_dir_chain_lfsr"
BIN = OBJ / "Vtb_chain_lfsr"

RTL = ["v30u_ss_pkg.sv", "v30_core.sv", "v30u_biu.sv",
       "v30u_ucrom.sv", "v30u_eu.sv"]

SEEDS = ["1", "2", "3", "4"]
CLOCKS = 400000

# The declared bound this gate reads out of the RTL, so the gate never carries
# a SECOND copy of the number it is checking.
CHAIN_MAX_RE = re.compile(r"localparam\s+bit\s*\[[^\]]*\]\s*CHAIN_MAX\s*=\s*"
                          r"\d*'d(\d+)\s*;")


def declared_chain_max(src=None):
    txt = (src or (UCORE / "v30u_eu.sv")).read_text()
    m = CHAIN_MAX_RE.search(txt)
    if not m:
        print("chain_lfsr_gate: CANNOT FIND CHAIN_MAX in v30u_eu.sv -- the "
              "gate refuses to guess the bound it is checking", file=sys.stderr)
        sys.exit(2)
    return int(m.group(1))


def verilator_cmd(ucore_dir, objdir, rtl_paths):
    return ["verilator", "--binary", "--timing",
            "-Wall", "-Wno-UNUSEDSIGNAL", "-Wno-VARHIDDEN",
            "-Wno-TIMESCALEMOD", "-Wno-WIDTHEXPAND", "-Wno-BLKSEQ",
            "-Wno-DECLFILENAME", "-Wno-UNUSEDPARAM", "-Wno-MULTIDRIVEN",
            "-Wno-UNOPTFLAT", "-Wno-CASEINCOMPLETE",
            "--top-module", "tb_chain_lfsr",
            "-I" + str(ucore_dir),
            "-Mdir", str(objdir),
            str(TB_DIR / "tb_chain_lfsr.sv")] + [str(p) for p in rtl_paths]


def recipe():
    """WHAT `Vtb_chain_lfsr` IS A FUNCTION OF.  One declaration.

    The .svh includes and the two runtime .hex tables are declared for the
    same reason `check_core.recipe()` declares them: `v30u_ucrom.sv`
    $readmemh's them AT RUN TIME, so they are files the ARTIFACT reads, and a
    number produced against the wrong tables is not this tree's number."""
    rtl = [UCORE / f for f in RTL]
    inputs = ([TB_DIR / "tb_chain_lfsr.sv"]
              + rtl
              + sorted(UCORE.glob("*.svh"))
              + [p for p in sorted(UCORE.glob("*.hex")) if p.is_file()])
    cmd = ["verilator", "--binary", "--timing",
           "-Wall", "-Wno-UNUSEDSIGNAL", "-Wno-VARHIDDEN",
           "-Wno-TIMESCALEMOD", "-Wno-WIDTHEXPAND", "-Wno-BLKSEQ",
           "-Wno-DECLFILENAME", "-Wno-UNUSEDPARAM", "-Wno-MULTIDRIVEN",
           "-Wno-UNOPTFLAT", "-Wno-CASEINCOMPLETE",
           "--top-module", "tb_chain_lfsr",
           "-I" + art.TOK_ROOT + "/" + str(UCORE.relative_to(ROOT)),
           "-Mdir", art.TOK_OUT,
           art.TOK_ROOT + "/hdl/tb/tb_chain_lfsr.sv"] + [
           art.TOK_ROOT + "/" + str(p.relative_to(ROOT)) for p in rtl]
    return art.Recipe(kind="verilator_binary", artifact=BIN,
                      inputs=inputs, command=cmd, tool="verilator",
                      workdir=OBJ, label="tb_chain_lfsr/ucore")


DEPTH_RE = re.compile(r"CHAIN_DEPTH_MAX\s+(\d+)\s+entry_st\s+(\d+)")
SIG_RE = re.compile(r"LFSR_SIG\s+([0-9a-f]+)")
GAP_RE = re.compile(r"CE_GAPS\s+(.*)")
BSH_RE = re.compile(r"BS_HIST\s+(.*)")
QP_RE = re.compile(r"QPOPS\s+(\d+)\s+FPOPS\s+(\d+)")
COIN_RE = re.compile(r"CE_COINCIDE\s+(\d+)")
CECLK_RE = re.compile(r"CE_CLOCKS\s+(\d+)")

# max-mode bus status encodings, `tb_v30_core.sv:123`
BS_NAME = {0: "INTA", 1: "IOR", 2: "IOW", 3: "HALT",
           4: "CODE", 5: "MEMR", 6: "MEMW", 7: "PASV"}
# THE LIVENESS FLOOR (per 400,000 fabric clocks).  A depth gate that passes on
# a core that is not executing is vacuous: `CHAIN OVERFLOW` cannot fire in a
# machine that never decodes.
#
# HOW THE NUMBERS WERE CHOSEN, stated plainly because they were chosen AFTER
# seeing a run: they are ~1/3 of the WEAKEST of the four registered seeds at
# `CHAIN_MAX = 12` (seed 2, `fpops` 138 / CODE 175 / MEMR 329 / MEMW 300; the
# strongest, seed 3, is `fpops` 1,366).  The spread is a tenfold property of
# executing random bytes -- some streams loop, some HALT -- so a floor set near
# the mean would fail on stimulus that is working.  This is a DEAD-CORE
# detector and it is not a scored bar of the landing; nothing in sec.4 of the
# pre-registration depends on it.
LIVE_MIN = {"fpops": 50, "b4": 50, "b5": 20, "b6": 20}


def run_one(binary, seed, clocks, timeout=3600):
    cmd = [str(binary), "+chaindepth", f"+seed={seed}", f"+clocks={clocks}"]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    out = p.stdout + p.stderr
    depth = 0
    entry = None
    for m in DEPTH_RE.finditer(out):
        d = int(m.group(1))
        if d > depth:
            depth, entry = d, int(m.group(2))
    sig = SIG_RE.search(out)
    gaps = {}
    g = GAP_RE.search(out)
    if g:
        for tok in g.group(1).split():
            k, _, v = tok.partition("=")
            gaps[k] = int(v)
    bsh = {}
    b = BSH_RE.search(out)
    if b:
        for tok in b.group(1).split():
            k, _, v = tok.partition("=")
            bsh[k] = int(v)
    qp = QP_RE.search(out)
    coin = COIN_RE.search(out)
    ceclk = CECLK_RE.search(out)
    return {
        "bs": bsh,
        "qpops": int(qp.group(1)) if qp else 0,
        "fpops": int(qp.group(2)) if qp else 0,
        "seed": seed,
        "rc": p.returncode,
        "depth": depth,
        "entry_st": entry,
        "sig": sig.group(1) if sig else None,
        "gaps": gaps,
        "coincide": int(coin.group(1)) if coin else None,
        "ce_clocks": int(ceclk.group(1)) if ceclk else None,
        "overflow": "CHAIN OVERFLOW" in out,
        "result_ok": "RESULT OK" in out,
        "tail": out[-2000:] if p.returncode != 0 else "",
    }


def nonvacuity(seeds, clocks):
    """H-3.  Copy the ucore to scratch, force CHAIN_MAX below the observed
    maximum, and REQUIRE the $fatal.  The shipped RTL is never touched."""
    tmp = Path(tempfile.mkdtemp(prefix="chainlfsr-nv-",
                                dir=str(Path.home() / ".cache")))
    try:
        d = tmp / "ucore"
        shutil.copytree(UCORE, d)
        eu = d / "v30u_eu.sv"
        txt = eu.read_text()
        new, n = CHAIN_MAX_RE.subn("localparam bit [3:0] CHAIN_MAX = 4'd4;",
                                   txt, count=1)
        if n != 1:
            print("NONVACUITY: could not rewrite CHAIN_MAX", file=sys.stderr)
            return 2
        eu.write_text(new)
        assert declared_chain_max(eu) == 4
        objdir = tmp / "obj"
        cmd = verilator_cmd(d, objdir, [d / f for f in RTL])
        b = subprocess.run(cmd, capture_output=True, text=True)
        if b.returncode != 0:
            print(b.stdout[-4000:] + b.stderr[-4000:], file=sys.stderr)
            print("NONVACUITY: build FAILED", file=sys.stderr)
            return 2
        fired = 0
        for s in seeds:
            r = run_one(objdir / "Vtb_chain_lfsr", s, clocks)
            got = r["overflow"] or r["rc"] != 0
            print(f"  NV seed {s}: rc={r['rc']} overflow={r['overflow']} "
                  f"depth_seen={r['depth']}")
            fired += 1 if got else 0
        if fired == len(seeds):
            print(f"H-3 NON-VACUITY: **MET** -- CHAIN OVERFLOW fired on "
                  f"{fired}/{len(seeds)} seeds at CHAIN_MAX = 4")
            return 0
        print(f"H-3 NON-VACUITY: **MISSED** -- fired on only {fired}/"
              f"{len(seeds)} seeds. The assertion is not reachable by this "
              f"stimulus and H-1 therefore says NOTHING.", file=sys.stderr)
        return 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--build", action="store_true",
                    help="force a rebuild before running")
    ap.add_argument("--seeds", default=",".join(SEEDS))
    ap.add_argument("--clocks", type=int, default=CLOCKS)
    ap.add_argument("--nonvacuity", action="store_true",
                    help="H-3 only: force CHAIN_MAX=4 in a scratch copy and "
                         "require the $fatal")
    ap.add_argument("--sig-ref", default=None,
                    help="H-4: a JSON file of {seed: sig} the run must "
                         "reproduce byte for byte")
    ap.add_argument("--sig-out", default=None,
                    help="write this run's {seed: sig} for a later --sig-ref")
    a = ap.parse_args()
    seeds = [s for s in a.seeds.split(",") if s]

    cmax = declared_chain_max()
    print(f"chain_lfsr_gate: CHAIN_MAX = {cmax} (read from v30u_eu.sv), "
          f"{len(seeds)} seeds x {a.clocks} fabric clocks")

    if a.nonvacuity:
        return nonvacuity(seeds, a.clocks)

    art.ensure(recipe(), force=a.build, quiet=False, why="chain_lfsr_gate")
    rid = art.receipt_id(BIN)
    print(f"  binary receipt {rid}")

    rows = [run_one(BIN, s, a.clocks) for s in seeds]

    fails = []
    for r in rows:
        gz = r["gaps"].get("g0", 0)
        print(f"  seed {r['seed']}: rc={r['rc']} CHAIN_DEPTH_MAX={r['depth']} "
              f"entry_st={r['entry_st']} ce_clocks={r['ce_clocks']} "
              f"g0={gz} coincide={r['coincide']} sig={r['sig']}")
        if r["gaps"]:
            print("      gaps " + " ".join(f"{k}={v}" for k, v in
                                           sorted(r["gaps"].items())))
        print("      live  fpops=%d qpops=%d " % (r["fpops"], r["qpops"]) +
              " ".join(f"{BS_NAME[int(k[1:])]}={v}"
                       for k, v in sorted(r["bs"].items()) if v))
        # the LIVENESS floor -- a depth gate on a dead core proves nothing
        scale = a.clocks / 400000.0
        for key, floor in LIVE_MIN.items():
            got = r["fpops"] if key == "fpops" else r["bs"].get(key, 0)
            if got < floor * scale:
                fails.append(f"seed {r['seed']}: LIVENESS {key}={got} below "
                             f"floor {floor * scale:.0f} -- the core was not "
                             f"executing, so the depth result says nothing")
        if r["rc"] != 0 or r["overflow"]:
            fails.append(f"seed {r['seed']}: CHAIN OVERFLOW or non-zero exit "
                         f"(rc={r['rc']})")
            if r["tail"]:
                print(r["tail"], file=sys.stderr)
        # H-1: the bound must EXCEED the observed depth, not merely equal it --
        # CHAIN_MAX is the derived maximum PLUS ONE SPARE, and a run that
        # reaches the declared bound has consumed the spare.
        if r["depth"] > cmax - 1:
            fails.append(f"seed {r['seed']}: depth {r['depth']} > "
                         f"CHAIN_MAX-1 ({cmax - 1})")
        if r["coincide"]:
            fails.append(f"seed {r['seed']}: ce & ce_half coincided "
                         f"{r['coincide']} times -- clause (a) VIOLATED")
        if gz < 1000:
            fails.append(f"seed {r['seed']}: minimum-gap pattern reached only "
                         f"{gz} times (H-2 asks >= 1000) -- the train is not "
                         f"exercising the contract's minimum")
        if not r["result_ok"]:
            fails.append(f"seed {r['seed']}: TB did not print RESULT OK")

    sigs = {r["seed"]: r["sig"] for r in rows}
    # THE SIGNATURE'S OWN FALSIFIER.  A signature that is the same on every
    # seed is a CONSTANT, and a constant reproduces across any RTL change --
    # which would make H-4 vacuous.  This clause is not decoration: the first
    # form of the TB's mixer was singular (`rotl1 ^ rotl32`) and returned one
    # value on four seeds whose BS_HIST differed fivefold. It was caught HERE.
    if len(seeds) > 1 and len(set(sigs.values())) == 1:
        fails.append(f"SIGNATURE DEGENERATE: all {len(seeds)} seeds returned "
                     f"{rows[0]['sig']}. Different stimulus must produce a "
                     f"different trace, or --sig-ref proves nothing.")
    if a.sig_out:
        Path(a.sig_out).write_text(json.dumps(sigs, indent=1, sort_keys=True))
        print(f"  signatures written to {a.sig_out}")
    if a.sig_ref:
        ref = json.loads(Path(a.sig_ref).read_text())
        for s in seeds:
            if ref.get(s) != sigs.get(s):
                fails.append(f"H-4 seed {s}: signature {sigs.get(s)} != "
                             f"reference {ref.get(s)}")
        if not any(f.startswith("H-4") for f in fails):
            print(f"  H-4: signatures IDENTICAL to {a.sig_ref} on "
                  f"{len(seeds)}/{len(seeds)} seeds")

    depths = sorted({r["depth"] for r in rows})
    if fails:
        print("\nchain_lfsr_gate: **FAIL**")
        for f in fails:
            print("  - " + f)
        return 1
    print(f"\nchain_lfsr_gate: PASS -- CHAIN_MAX {cmax}, observed depth "
          f"{depths}, 0 overflows, {len(seeds)} seeds x {a.clocks} clocks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
