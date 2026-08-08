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

THREE THINGS THE RECEIPT LEARNED (the ucore RE-LANDING campaign, whose evidence
for nineteen mechanisms is nothing BUT receipts from this tool):

  * **A receipt only ever exists as the output of a completed run.**  Any file
    at `receipt_path` is UNLINKED before the gate starts, and the default path
    is gitignored -- it used to be TRACKED, so every branch switch resurrected
    a fossil receipt beside a newer build's reports and it read as that build's
    result.  The history that survives a clean build is
    `sw/testdata/receipts/quartus_bitstream.jsonl`, not this file.
  * **`configuration` is DERIVED, never asserted.**  It used to be a hardcoded
    "CONTROL/DEFAULT" string, so every RETENTION receipt ever written was
    mislabelled as a control build -- and the retention build is the one that
    gets flashed.  It is now read out of the reports themselves: the `.qsf`
    macros off `<rev>.flow.rpt` and the command-line `--verilog_macro=` off
    `<rev>.map.rpt`'s `Info: Command:` line (which is how a retention build is
    actually made, §sm3-s19b).  **Where the report that would carry the answer
    is absent, the value is `UNDETERMINED`** -- a default that names a specific
    configuration is absence reading as data.
  * `reports` carries the sha256 of every report the gate PARSED, so a receipt
    written against a stale report set is mechanically detectable instead of an
    argument about mtimes.  It is the artifact layer's own rule applied to the
    gate's own inputs.

    python3 sw/quartus_gate.py                 # clean build + gate  (~10 min)
    python3 sw/quartus_gate.py --parse-only    # re-gate an existing report set
    python3 sw/quartus_gate.py --tree DIR      # gate a build kept elsewhere

EXIT 0 = PASS, 1 = RED, 2 = the gate could not run (missing tool / report).
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "sw"))
import artifact as art                                       # noqa: E402
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


def input_files():
    """Every file the CONTROL build reads, as HDL-relative names."""
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
    return sorted(files)


def input_manifest():
    """Every file the CONTROL build reads, hashed, THROUGH THE SHARED LAYER.

    SM3 sitting 14: this used to be a private copy of `artifact.manifest()`
    keyed on HDL-RELATIVE names.  It is now the shared writer, keyed on
    REPO-RELATIVE names like every other receipt in the tree, so
    `sw/receipt_diff.py` can compare a bitstream receipt against a Verilator
    one.  The file COUNT and the discovery rule are unchanged; the KEYS gained
    their `hdl/` prefix and the hash therefore moved.  Nothing consumed the old
    hash (`ucore_provenance.md` §75)."""
    return art.manifest([HDL / f for f in input_files()])


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


def _hier_count(value):
    """Parse Quartus' ``total (own)`` hierarchy-cell notation."""
    m = re.fullmatch(r"([\d,]+)(?:\s+\(([\d,]+)\))?", value.strip())
    if not m:
        return None
    total = int(m.group(1).replace(",", ""))
    own = int(m.group(2).replace(",", "")) if m.group(2) else total
    return {"total": total, "own": own}


def parse_hierarchy(tree):
    """Selected ucore map hierarchy counts -- informational, never bars."""
    rpt = tree / f"{REVISION}.map.rpt"
    wanted = {"v30_core", "v30u_eu", "v30u_biu", "v30u_ucrom"}
    out = {}
    if not rpt.exists():
        return out
    for ln in rpt.read_text(errors="replace").splitlines():
        cols = [x.strip() for x in ln.split(";")]
        # Hierarchy rows are: node, ALUTs, registers, ..., entity, library.
        if len(cols) < 11 or cols[9] not in wanted:
            continue
        aluts = _hier_count(cols[2])
        registers = _hier_count(cols[3])
        if aluts is not None and registers is not None:
            out[cols[9]] = {"combinational_aluts": aluts,
                            "dedicated_logic_registers": registers}
    return out


def parse_uninferred_ram(tree):
    """Count uninferred-RAM fragments and retain their source attribution."""
    rpt = tree / f"{REVISION}.map.rpt"
    out = {"total": None, "by_source": {}, "by_entity": {}}
    if not rpt.exists():
        return out
    txt = rpt.read_text(errors="replace")
    found = re.search(r"Found\s+(\d+)\s+instances of uninferred RAM logic", txt)
    rows = re.findall(
        r'RAM logic "([^"]+)" is uninferred[^\n]*?File:\s+(\S+)\s+Line:\s+(\d+)',
        txt)
    out["total"] = int(found.group(1)) if found else len(rows)
    for hierarchy, source, line in rows:
        key = f"{Path(source).name}:{line}"
        out["by_source"][key] = out["by_source"].get(key, 0) + 1
        entity = ("v30u_ucrom" if "v30u_ucrom:" in hierarchy else
                  "v30u_eu" if "v30u_eu:" in hierarchy else
                  "v30u_biu" if "v30u_biu:" in hierarchy else
                  "v30_core" if "v30_core:" in hierarchy else "other")
        out["by_entity"][entity] = out["by_entity"].get(entity, 0) + 1
    return out


def parse_durations(tree):
    """Map/fitter elapsed and CPU durations as printed by Quartus."""
    out = {}
    for stage in ("map", "fit"):
        rpt = tree / f"{REVISION}.{stage}.rpt"
        if not rpt.exists():
            continue
        txt = rpt.read_text(errors="replace")
        elapsed = re.findall(r"Info: Elapsed time:\s*([^\n]+)", txt)
        cpu = re.findall(r"Info: Total CPU time \(on all processors\):\s*([^\n]+)",
                         txt)
        out[stage] = {"elapsed": elapsed[-1].strip() if elapsed else None,
                      "cpu": cpu[-1].strip() if cpu else None}
    return out


# --------------------------------------------------------------------------- #
# WHICH BUILD IS THIS -- derived, never asserted
# --------------------------------------------------------------------------- #
RETENTION_MACRO = "X1_AD_RETENTION"


def _macro_name_value(tok):
    n, _, v = tok.partition("=")
    return n.strip(), (v.strip() or "1")


def parse_configuration(tree):
    """-> (configuration string, detail dict) read OUT OF THE REPORTS.

    Two sources, because a build has two ways to be given a macro and the
    retention build uses the second one:

        <rev>.flow.rpt   `VERILOG_MACRO` rows -- what the .qsf set
        <rev>.map.rpt    `Info: Command:`     -- what the command line passed,
                         i.e. `quartus_map --verilog_macro="X1_AD_RETENTION=1"`

    A macro seen in EITHER source is set.  Saying it is NOT set requires having
    read BOTH sources: with one missing the honest answer is UNDETERMINED, not
    CONTROL."""
    flow = tree / f"{REVISION}.flow.rpt"
    mapr = tree / f"{REVISION}.map.rpt"
    detail = {"qsf_macros": None, "cmdline_macros": None, "macros": None,
              "command_line": None, "retention": None,
              "sources": {art.relpath(flow): flow.is_file(),
                          art.relpath(mapr): mapr.is_file()}}
    macros = set()
    if flow.is_file():
        rows = re.findall(r";\s*VERILOG_MACRO\s*;\s*(\S+)\s*;",
                          flow.read_text(errors="replace"))
        detail["qsf_macros"] = sorted(set(rows))
        macros.update(rows)
    if mapr.is_file():
        cmd = None
        with open(mapr, errors="replace") as f:
            for ln in f:
                if ln.lstrip().startswith("Info: Command:"):
                    cmd = ln.split("Command:", 1)[1].strip()
                    break
        detail["command_line"] = cmd
        cl = re.findall(r'--verilog_macro[= ]"?([^"\s]+)', cmd or "")
        detail["cmdline_macros"] = sorted(set(cl))
        macros.update(cl)

    ret = [t for t in macros if _macro_name_value(t)[0] == RETENTION_MACRO
           and _macro_name_value(t)[1] != "0"]
    missing = sorted(k for k, ok in detail["sources"].items() if not ok)
    if ret:
        detail["macros"] = sorted(macros)
        detail["retention"] = True
        return (f"RETENTION ({', '.join(sorted(ret))}) -- DERIVED from "
                f"{', '.join(sorted(k for k, ok in detail['sources'].items() if ok))}"), detail
    if missing:
        # No macro seen, but a source that could have carried one was not read.
        return (f"UNDETERMINED -- absent: {', '.join(missing)}; "
                f"nothing read says whether {RETENTION_MACRO} is set"), detail
    detail["macros"] = sorted(macros)
    detail["retention"] = False
    return (f"CONTROL/DEFAULT (no {RETENTION_MACRO}) -- DERIVED from "
            f"{', '.join(sorted(detail['sources']))}"), detail


# the reports this gate PARSES.  Hashed into the receipt so a run against a
# stale report set is detectable without appealing to mtimes.
PARSED_REPORTS = (".sta.rpt", ".sta.summary", ".map.summary", ".fit.summary",
                  ".asm.rpt", ".fit.rpt", ".flow.rpt", ".map.rpt")


def report_manifest(tree, logpath):
    """{n_files, sha256, files} over every report the gate reads.

    `MISSING` is a value (spec §3 rule 2): a report that vanished must move the
    hash, not silently drop out of it."""
    paths = [tree / f"{REVISION}{ext}" for ext in PARSED_REPORTS]
    if logpath is not None:
        paths.append(Path(logpath))
    return art.manifest(paths)


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
    hierarchy = parse_hierarchy(tree)
    uninferred_ram = parse_uninferred_ram(tree)
    durations = parse_durations(tree)

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
                  "ucore_hierarchy": hierarchy,
                  "uninferred_ram_fragments": uninferred_ram,
                  "durations": durations,
                  "stages": logf["stages"],
                  "error_lines": logf["error_lines"]}


def _finish(rec, receipt_path):
    """Stamp, id, write atomically, and append the repo-level history.

    The `.jsonl` copy is the reason this matters: `hdl/output_files_ucore/` is
    deleted by the gate's own next clean build, so a receipt that lived only
    beside its artifact would be a history of exactly one entry."""
    rec["completed"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    rec["id"] = art.canonical_id(rec)
    art._write_json_atomic(Path(receipt_path), rec)
    art.append_history(rec)
    return rec


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

    # A RECEIPT ONLY EVER EXISTS AS THE OUTPUT OF A COMPLETED RUN.  Anything
    # already at this path is a PREVIOUS run's -- or, when the path was still
    # tracked in git, a fossil that a branch switch put back beside a newer
    # build's reports.  Remove it now, so a failed or interrupted run leaves NO
    # receipt rather than leaving the old one to be read as this run's.
    if receipt_path.exists() or receipt_path.is_symlink():
        print(f"quartus_gate: removing pre-existing receipt {receipt_path} "
              f"(a receipt is an OUTPUT; the history is "
              f"{art.RECEIPT_DIR / 'quartus_bitstream.jsonl'})", flush=True)
        receipt_path.unlink()

    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    mf = input_manifest()
    tv = tool_version()
    # --- THE SHARED §3 SCHEMA (docs/notes/artifact_receipt_layer.md) -------- #
    # SM3 sitting 14.  The s13 receipt was written TO this schema by hand; it is
    # now written BY the shared layer, so `sw/receipt_diff.py` reads it, the
    # `.jsonl` history keeps it after `hdl/output_files_ucore/` is deleted, and
    # `id` is content-derived (two identical builds COLLIDE, and that collision
    # is information -- §74.4a's 26 MHz swing is exactly a case where two
    # receipts with the same `inputs.sha256` and different `outputs` is the
    # finding).
    #
    # SCHEMA VERSIONING: every key the SM3-s13 shape carried is still present
    # and still means what it meant (`gate`, `gate_version`, `ts`,
    # `tool_version`, `input_manifest`, `configuration`, `tree`, `bars`,
    # `figures`, `verdict`, `E1_gen_ucore_qsf`, `build`).  The §3 keys are
    # ADDED beside them.  Nothing that read the old shape breaks.
    rec = {"schema": art.SCHEMA, "schema_version": art.SCHEMA_VERSION,
           "kind": "quartus_bitstream",
           "name": art.relpath(tree / f"{REVISION}.sof"),
           "label": a.label,
           "inputs": mf,
           "command": None,                       # filled by build()/parse-only
           "env": {},
           "tool": tv, "tool_name": "quartus_sh", "tool_probe": None,
           "tool_sha256": None,
           "outputs": {},
           "git": art.git_state(),
           "started": started, "completed": None, "rc": None,
           "figures": {}, "verdict": None,
           # --- the SM3-s13 keys, retained verbatim ------------------------ #
           "gate": GATE_NAME, "gate_version": GATE_VERSION,
           "ts": started,
           "tool_version": tv,
           "input_manifest": mf,
           # DERIVED after the build, off the reports actually gated.  Until
           # then -- and on any path that gates no reports at all -- it stays
           # UNDETERMINED.  It must never DEFAULT to naming a configuration.
           "configuration": "UNDETERMINED -- no reports gated",
           "configuration_detail": None,
           "reports": None,
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
            _finish(rec, receipt_path)
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
        rec["command"] = b["cmd"]
        rec["rc"] = b["rc"]
        rec["seconds"] = b["seconds"]
        # Quartus REWRITES the revision .qsf it compiles (§70.7).  Put it back
        # so the tree is not left dirty by its own gate; recorded, not hidden.
        subprocess.run([sys.executable, str(ROOT / "sw" / "gen_ucore_qsf.py")],
                       capture_output=True, text=True)
        rec["qsf_regenerated_post_build"] = True

    log_text = ""
    if logpath.exists():
        log_text = logpath.read_text(errors="replace")

    # WHICH BUILD THIS RECEIPT DESCRIBES -- read out of the reports, and hashed
    # so the next reader can check the reports have not moved underneath it.
    rec["configuration"], rec["configuration_detail"] = parse_configuration(tree)
    rec["reports"] = report_manifest(tree, logpath)
    print(f"quartus_gate: configuration {rec['configuration']}", flush=True)

    bars, figs = score(tree, log_text, a)
    rec["bars"] = bars
    rec["figures"] = figs
    ok = all(v["pass"] for v in bars.values())
    if not a.no_qsf_check:
        ok = ok and rec["E1_gen_ucore_qsf"]["pass"]
    rec["verdict"] = "PASS" if ok else "RED"
    # THE OUTPUTS, HASHED.  §8: the layer does NOT try to make Quartus
    # bit-reproducible -- two builds from identical inputs may differ, the
    # receipt records both hashes, and THAT DIFFERENCE IS DATA (§74.4a's 26 MHz
    # swing is a finding a reproducibility requirement would have suppressed).
    for ext in (".sof", ".rbf", ".sta.summary", ".fit.summary"):
        f = tree / f"{REVISION}{ext}"
        if f.is_file():
            rec["outputs"][art.relpath(f)] = art.sha256_file(f)
    _finish(rec, receipt_path)

    print("\n  --- quartus_gate (G6) ---")
    print(f"  tool     : {rec['tool_version']}")
    print(f"  config   : {rec['configuration']}")
    print(f"  inputs   : {rec['input_manifest']['n_files']} files, "
          f"sha256 {rec['input_manifest']['sha256'][:16]}…")
    print(f"  reports  : {rec['reports']['n_files']} files, "
          f"sha256 {rec['reports']['sha256'][:16]}…")
    print(f"  git      : {rec['git']['describe']}"
          f"{'  (tree DIRTY)' if rec['git']['dirty_tracked'] else ''}")
    for k in sorted(bars):
        v = bars[k]
        print(f"  {'PASS' if v['pass'] else 'RED '} {k:<16} {v['value']}")
    print(f"  ALMs {figs['status'].get('alms')}   "
          f"latches {figs['resources'].get('latches')}   "
          f"lpm_divide {figs['resources'].get('lpm_divide')}")
    print(f"  receipt id : {rec['id'][:16]}…   "
          f"(history {art.RECEIPT_DIR / (rec['kind'] + '.jsonl')})")
    print(f"=== quartus_gate: {rec['verdict']}   receipt {receipt_path}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
