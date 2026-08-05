#!/usr/bin/env python3
"""quartus_gate -- THE STANDING QUARTUS LEG (G6), the gate the ladder did not have.

WHY IT EXISTS.  `ucore_provenance.md` §73.1: SM3 sitting 11 landed RTL (a net
DELETION of five flops), ran no synthesis -- which was allowed, because no
standing gate demanded one -- and the DEFAULT `nec_test_ucore` build silently
went from **45.67 MHz to 19.42 MHz** with 20,000 failing paths.  Nothing in the
tree saw it, because the standing set is board-free by design and had no
Quartus leg at all.  That is the sixth incarnation of `standing_gates.md`'s own
vacuous-gate pattern, this time by ABSENCE rather than by blindness.

WHAT IT GATES.  Exactly the registered G6 essentials (`ucore_provenance.md`
§52.1, quoted in CLAUDE.md), on ONE clean CONTROL/DEFAULT build -- macro OFF,
the configuration every bitstream is derived from:

    E1  `sw/gen_ucore_qsf.py --check` is green BEFORE the build
        (a stale revision file is a build comparing two things that differ by
        more than the core; and it must be checked BEFORE, because Quartus
        REWRITES the .qsf it compiles -- §70.7)
    E2  0 compile errors, every stage `Successful`
    E3  `divclk` Fmax >= 32.0 MHz          (the registered bar)
    E4  worst setup slack > 0, on every clock domain
    E5  TNS == 0.000, SETUP **and** HOLD, on every clock domain

Everything else the sitting-12 record quotes -- ALMs, registers, latches,
`lpm_divide`, the per-entity register census -- is PARSED AND RECORDED IN THE
RECEIPT but is NOT a bar.  A gate that asserts a resource number fails on
noise; a gate that RECORDS one lets the next agent see drift.

THE RECEIPT (`--receipt`, default `hdl/output_files_ucore/quartus_gate.json`)
is the deliverable: input manifest hash, tool version, the exact command, the
parsed figures, and the verdict.  `docs/notes/artifact_receipt_layer.md` §3
specifies the shared schema this one is the first instance of.

    python3 sw/quartus_gate.py                 # clean build + gate  (~10 min)
    python3 sw/quartus_gate.py --parse-only    # re-gate an existing report set
    python3 sw/quartus_gate.py --tree DIR      # gate a build kept elsewhere

EXIT 0 = PASS, 1 = RED, 2 = the gate could not run (missing tool / report).
"""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HDL = ROOT / "hdl"
QUARTUS_BIN = Path.home() / "intelFPGA_lite" / "17.1" / "quartus" / "bin"
PROJECT = "nec_test"
REVISION = "nec_test_ucore"
OUTDIR = "output_files_ucore"

# --- the registered bars ---------------------------------------------------- #
FMAX_MIN_MHZ = 32.0
FMAX_CLOCK = "emu|pll|pll_inst|altera_pll_i|general[0].gpll~PLL_OUTPUT_COUNTER|divclk"

GATE_NAME = "quartus_gate"
GATE_VERSION = 1


# --------------------------------------------------------------------------- #
# the input manifest -- what this build is a function of
# --------------------------------------------------------------------------- #
def _qip_files(qip):
    """The RTL/SDC files a .qip names, project-relative."""
    out = []
    pat = re.compile(r'-name\s+(?:SYSTEMVERILOG_FILE|VERILOG_FILE|VHDL_FILE|'
                     r'SDC_FILE|QIP_FILE|MIF_FILE|HEX_FILE)\s+(\S+)')
    for ln in qip.read_text().splitlines():
        if ln.lstrip().startswith("#"):
            continue
        m = pat.search(ln)
        if m:
            out.append(m.group(1).strip('"'))
    return out


def input_manifest():
    """Every file the CONTROL build reads, hashed.  Missing files are recorded
    as such rather than skipped -- a vanished input must change the hash."""
    files = set()
    for p in ("nec_test.qsf", "nec_test_ucore.qsf", "files_ucore.qip",
              "nec_test.sdc", "nec_test.sv"):
        files.add(p)
    qip = HDL / "files_ucore.qip"
    if qip.exists():
        files.update(_qip_files(qip))
    # the ucore itself, its includes and its generated tables
    for p in sorted((HDL / "rtl" / "ucore").rglob("*")):
        if p.is_file():
            files.add(str(p.relative_to(HDL)))
    # the MiSTer platform the .qsf sources
    for p in sorted((HDL / "sys").rglob("*")):
        if p.is_file() and p.suffix in (".v", ".sv", ".vhd", ".tcl", ".qip",
                                        ".sdc", ".qsf"):
            files.add(str(p.relative_to(HDL)))
    ent = []
    for rel in sorted(files):
        f = HDL / rel
        if f.is_file():
            ent.append((rel, hashlib.sha256(f.read_bytes()).hexdigest()))
        else:
            ent.append((rel, "MISSING"))
    blob = "\n".join(f"{h}  {r}" for r, h in ent).encode()
    return {"n_files": len(ent),
            "sha256": hashlib.sha256(blob).hexdigest(),
            "files": dict(ent)}


def git_state():
    def sh(*a):
        try:
            return subprocess.run(a, cwd=ROOT, capture_output=True,
                                  text=True, check=True).stdout.strip()
        except Exception:                                    # noqa: BLE001
            return "unknown"
    # TRACKED modifications only: `output_files_ucore/` is untracked build
    # output and its presence is not tree drift.
    return {"head": sh("git", "rev-parse", "HEAD"),
            "describe": sh("git", "describe", "--always", "--dirty"),
            "dirty": bool(sh("git", "status", "--porcelain", "-uno", "--", "hdl"))}


def tool_version():
    exe = QUARTUS_BIN / "quartus_sh"
    if not exe.exists():
        return None
    try:
        out = subprocess.run([str(exe), "--version"], capture_output=True,
                             text=True, timeout=60).stdout
        for ln in out.splitlines():
            if "Version" in ln:
                return ln.strip()
    except Exception:                                        # noqa: BLE001
        pass
    return None


# --------------------------------------------------------------------------- #
# the parsers -- ONLY the registered essentials are bars
# --------------------------------------------------------------------------- #
def parse_sta(tree):
    """-> (fmax dict, setup list, hold list) off <rev>.sta.rpt / .sta.summary"""
    rpt = tree / f"{REVISION}.sta.rpt"
    summ = tree / f"{REVISION}.sta.summary"
    fmax = {}
    if rpt.exists():
        txt = rpt.read_text(errors="replace")
        i = txt.find("; Fmax Summary")
        if i >= 0:
            for ln in txt[i:i + 4000].splitlines():
                m = re.match(r";\s*([\d.]+)\s*MHz\s*;\s*([\d.]+)\s*MHz\s*;\s*'?(\S+)",
                             ln)
                if m:
                    fmax[m.group(3)] = float(m.group(1))
    setup, hold = [], []
    if summ.exists():
        blocks = re.findall(r"Type\s*:\s*(\w[\w ]*?)\s*'([^']+)'\s*\n"
                            r"Slack\s*:\s*(\S+)\s*\nTNS\s*:\s*(\S+)",
                            summ.read_text(errors="replace"))
        for kind, clk, slack, tns in blocks:
            rec = {"clock": clk, "slack": float(slack), "tns": float(tns)}
            if kind.strip() == "Setup":
                setup.append(rec)
            elif kind.strip() == "Hold":
                hold.append(rec)
    return fmax, setup, hold


def parse_status(tree):
    """Stage status + resources off the .summary files (informational except
    for the Successful/errors bar)."""
    out = {}
    for stage, fn in (("map", f"{REVISION}.map.summary"),
                      ("fit", f"{REVISION}.fit.summary")):
        f = tree / fn
        if not f.exists():
            continue
        for ln in f.read_text(errors="replace").splitlines():
            if ":" not in ln:
                continue
            k, v = ln.split(":", 1)
            k, v = k.strip(), v.strip()
            if k.endswith("Status"):
                out[f"{stage}_status"] = v
            elif k == "Logic utilization (in ALMs)" and v != "N/A":
                out["alms"] = v
            elif k == "Total registers":
                out[f"{stage}_registers"] = v
    asm = tree / f"{REVISION}.asm.rpt"
    if asm.exists():
        t = asm.read_text(errors="replace")
        out["asm_successful"] = "Assembler was successful" in t
    return out


def parse_log(log_text):
    """Compile errors, latches and lpm_divide, off the compile transcript."""
    errs = [ln for ln in log_text.splitlines() if ln.startswith("Error ")
            or ln.startswith("Error(")]
    stages = re.findall(r"Quartus Prime (.+?) was successful\. (\d+) errors?, "
                        r"(\d+) warnings?", log_text)
    return {"error_lines": errs[:40],
            "n_error_lines": len(errs),
            "stages": [{"stage": s, "errors": int(e), "warnings": int(w)}
                       for s, e, w in stages]}


def parse_resources(tree):
    """Latches and `lpm_divide` -- RECORDED, not gated.

    Quartus OMITS the latch row from the resource summary when the count is
    zero, so "no row" is 0 and not unknown -- but only if the report is there
    at all, which is why `None` survives for a missing file."""
    out = {"latches": None, "lpm_divide": None, "fit_registers": None}
    fit = tree / f"{REVISION}.fit.rpt"
    if not fit.exists():
        return out
    txt = fit.read_text(errors="replace")
    mm = re.search(r";\s*Total registers\s*;\s*([\d,]+)", txt)
    if mm:
        out["fit_registers"] = mm.group(1)
    lat = re.findall(r";\s*[-\w ]*latch[\w ]*\s*;\s*([\d,]+)\s*;", txt,
                     re.IGNORECASE)
    out["latches"] = sum(int(x.replace(",", "")) for x in lat) if lat else 0
    out["lpm_divide"] = txt.count("lpm_divide")
    return out


# --------------------------------------------------------------------------- #
def build(tree, keep_db, logpath):
    exe = QUARTUS_BIN / "quartus_sh"
    if not exe.exists():
        print(f"quartus_gate: {exe} not found -- the gate CANNOT RUN "
              f"(this is exit 2, not a PASS and not a RED)")
        return None, 2
    if not keep_db:
        for d in ("db", "incremental_db", OUTDIR):
            shutil.rmtree(HDL / d, ignore_errors=True)
    cmd = [str(exe), "--flow", "compile", PROJECT, "-c", REVISION]
    print(f"quartus_gate: {' '.join(cmd)}   (cwd {HDL})", flush=True)
    t0 = time.time()
    with open(logpath, "w") as lf:
        rc = subprocess.run(cmd, cwd=HDL, stdout=lf,
                            stderr=subprocess.STDOUT).returncode
    print(f"quartus_gate: compile rc={rc} in {time.time()-t0:.0f}s "
          f"(log {logpath})", flush=True)
    return {"cmd": cmd, "rc": rc, "seconds": round(time.time() - t0, 1),
            "log": str(logpath)}, 0


def score(tree, log_text, a):
    fmax, setup, hold = parse_sta(tree)
    status = parse_status(tree)
    logf = parse_log(log_text)
    res = parse_resources(tree)

    fm = fmax.get(FMAX_CLOCK)
    if fm is None:                       # tolerate a renamed PLL instance
        cand = {k: v for k, v in fmax.items() if k.endswith("divclk")
                and "audio" not in k}
        fm = min(cand.values()) if cand else None
    worst_setup = min((r["slack"] for r in setup), default=None)
    tns_bad = [r for r in setup + hold if r["tns"] != 0.0]
    stage_errs = sum(s["errors"] for s in logf["stages"])
    all_ok = all(status.get(k, "").startswith("Successful")
                 for k in ("map_status", "fit_status"))

    bars = {
        "E2_zero_errors": {"bar": "0 compile errors, every stage Successful",
                           "value": {"stage_errors": stage_errs,
                                     "error_lines": logf["n_error_lines"],
                                     "map": status.get("map_status"),
                                     "fit": status.get("fit_status"),
                                     "asm": status.get("asm_successful")},
                           "pass": (stage_errs == 0
                                    and logf["n_error_lines"] == 0
                                    and all_ok
                                    and status.get("asm_successful") is True)},
        "E3_fmax": {"bar": f"divclk Fmax >= {FMAX_MIN_MHZ} MHz",
                    "value": fm,
                    "pass": fm is not None and fm >= FMAX_MIN_MHZ},
        "E4_worst_setup": {"bar": "worst setup slack > 0 on every domain",
                           "value": worst_setup,
                           "pass": worst_setup is not None and worst_setup > 0},
        "E5_tns": {"bar": "TNS == 0.000, setup AND hold, every domain",
                   "value": [f"{r['clock']}={r['tns']}" for r in tns_bad],
                   "pass": (len(tns_bad) == 0
                            and len(setup) > 0 and len(hold) > 0)},
    }
    return bars, {"fmax": fmax, "setup": setup, "hold": hold,
                  "status": status, "resources": res,
                  "stages": logf["stages"],
                  "error_lines": logf["error_lines"]}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--receipt", default="")
    ap.add_argument("--tree", default="",
                    help="a build output dir to gate instead of hdl/"
                         + OUTDIR)
    ap.add_argument("--parse-only", action="store_true",
                    help="do not build; gate the reports already present")
    ap.add_argument("--keep-db", action="store_true",
                    help="do NOT delete db/incremental_db first "
                         "(an incremental compile is NOT the gate)")
    ap.add_argument("--log", default="")
    ap.add_argument("--label", default="",
                    help="free-text tag recorded in the receipt")
    ap.add_argument("--no-qsf-check", action="store_true",
                    help="skip E1.  Only for gating a tree captured earlier.")
    a = ap.parse_args()

    tree = Path(a.tree).resolve() if a.tree else (HDL / OUTDIR)
    receipt_path = Path(a.receipt) if a.receipt else (tree / "quartus_gate.json")
    logpath = Path(a.log) if a.log else (tree.parent / "quartus_gate_build.log")

    rec = {"gate": GATE_NAME, "gate_version": GATE_VERSION,
           "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "label": a.label, "git": git_state(),
           "tool_version": tool_version(),
           "input_manifest": input_manifest(),
           "configuration": "CONTROL/DEFAULT (no X1_AD_RETENTION) -- the "
                            "configuration every bitstream is derived from",
           "tree": str(tree)}

    # --- E1: the revision file, BEFORE the build --------------------------- #
    if a.no_qsf_check:
        rec["E1_gen_ucore_qsf"] = {"pass": None, "note": "skipped (--no-qsf-check)"}
    else:
        r = subprocess.run([sys.executable, str(ROOT / "sw" / "gen_ucore_qsf.py"),
                            "--check"], capture_output=True, text=True)
        rec["E1_gen_ucore_qsf"] = {"bar": "hdl/nec_test_ucore.qsf is a faithful "
                                          "derivative of hdl/nec_test.qsf",
                                   "rc": r.returncode,
                                   "out": (r.stdout + r.stderr).strip(),
                                   "pass": r.returncode == 0}
        print(f"quartus_gate: E1 gen_ucore_qsf --check -> "
              f"{'PASS' if r.returncode == 0 else 'RED'}: "
              f"{(r.stdout + r.stderr).strip()}", flush=True)
        if r.returncode != 0:
            rec["verdict"] = "RED"
            rec["red_at"] = "E1"
            receipt_path.parent.mkdir(parents=True, exist_ok=True)
            receipt_path.write_text(json.dumps(rec, indent=1) + "\n")
            print(f"quartus_gate: RED at E1.  receipt {receipt_path}")
            return 1

    # --- the build --------------------------------------------------------- #
    if a.parse_only:
        rec["build"] = {"note": "--parse-only: reports gated as found"}
    else:
        tree.parent.mkdir(parents=True, exist_ok=True)
        b, rc = build(tree, a.keep_db, logpath)
        if b is None:
            return rc
        rec["build"] = b
        # Quartus REWRITES the revision .qsf it compiles (§70.7).  Put it back
        # so the tree is not left dirty by its own gate; recorded, not hidden.
        subprocess.run([sys.executable, str(ROOT / "sw" / "gen_ucore_qsf.py")],
                       capture_output=True, text=True)
        rec["qsf_regenerated_post_build"] = True

    log_text = ""
    if logpath.exists():
        log_text = logpath.read_text(errors="replace")

    bars, figs = score(tree, log_text, a)
    rec["bars"] = bars
    rec["figures"] = figs
    ok = all(v["pass"] for v in bars.values())
    if not a.no_qsf_check:
        ok = ok and rec["E1_gen_ucore_qsf"]["pass"]
    rec["verdict"] = "PASS" if ok else "RED"

    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(rec, indent=1) + "\n")

    print("\n  --- quartus_gate (G6), the CONTROL/DEFAULT build ---")
    print(f"  tool     : {rec['tool_version']}")
    print(f"  inputs   : {rec['input_manifest']['n_files']} files, "
          f"sha256 {rec['input_manifest']['sha256'][:16]}…")
    print(f"  git      : {rec['git']['describe']}"
          f"{'  (hdl DIRTY)' if rec['git']['dirty'] else ''}")
    for k in sorted(bars):
        v = bars[k]
        print(f"  {'PASS' if v['pass'] else 'RED '} {k:<16} {v['value']}")
    print(f"  ALMs {figs['status'].get('alms')}   "
          f"latches {figs['resources'].get('latches')}   "
          f"lpm_divide {figs['resources'].get('lpm_divide')}")
    print(f"=== quartus_gate: {rec['verdict']}   receipt {receipt_path}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
