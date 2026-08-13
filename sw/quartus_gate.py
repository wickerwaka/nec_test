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

THE TWO CONFIGURATIONS, AND THE TRAP THAT USED TO SIT BETWEEN THEM.  `G6` is
scored on the CONTROL build; the bitstream that gets FLASHED is the RETENTION
one (`X1_AD_RETENTION=1`).  Until 2026-08-11 this tool could only build the
first: `build()` ran `quartus_sh --flow compile` with no `--verilog_macro` and
never read the environment, so the recipe for the second lived only in prose
across five pre-registrations, and

    X1_AD_RETENTION=1 python3 sw/quartus_gate.py

was **ACCEPTED AND IGNORED** -- it produced a CONTROL build whose `.rbf` was
byte-identical to the control's, under a receipt somebody had labelled
RETENTION by hand.  FLASH #18 §1.2 caught it on the DERIVED `configuration`,
one step before flashing it, and booked the fix.  Now:

  * `--retention` runs the recorded four-step recipe (`build_commands()`), and
  * the environment variable is **REFUSED** -- accepted-and-ignored became
    refused-with-reason, so the variable can no longer reach a run that will
    not honour it.

`configuration` is still DERIVED from the reports and NEVER from the flag: the
flag records what was ASKED for, in `build.configuration_requested`, and the
disagreement between the two is exactly the check that caught FLASH #18.

    python3 sw/quartus_gate.py                 # CONTROL build + gate (~10 min)
    python3 sw/quartus_gate.py --retention     # RETENTION build + gate
    python3 sw/quartus_gate.py --dry-run [--retention]   # print the stages only
    python3 sw/quartus_gate.py --parse-only    # re-gate an existing report set
    python3 sw/quartus_gate.py --tree DIR      # gate a build kept elsewhere

Its own falsifier is `sw/test_quartus_gate.py` (Q1-Q7), which needs no Quartus.

EXIT 0 = PASS, 1 = RED, 2 = the gate could not run (missing tool / report, or
a REFUSED invocation).
"""
import argparse
import json
import os
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

# --------------------------------------------------------------------------- #
# SIGNALTAP -- OPT-IN, DEFAULT OFF  (timing50 Phase 1 P-1, 2026-08-12)
# --------------------------------------------------------------------------- #
# `hdl/nec_test.qsf` used to carry these three lines unconditionally, naming an
# `stp1.stp` that HAS NEVER EXISTED in this repository.  A CONTROL build with
# them removed measured Fmax 45.61 / +8.892 / 12,282 ALMs -- identical in every
# figure -- and a BYTE-IDENTICAL `.rbf`, so the setting was inert.  They now
# live here and reach a build ONLY via `--signaltap`.
#
# WHY THEY ARE APPENDED TO THE REVISION .qsf RATHER THAN LEFT IN THE SOURCE:
# `gen_ucore_qsf.py --check` (E1) gates that `nec_test_ucore.qsf` is a faithful
# derivative of `nec_test.qsf` -- so the lines cannot be removed from the ucore
# revision alone without failing that gate, and leaving them in one revision
# only would make the A/B bitstreams differ by the DEBUG FABRIC as well as by
# the core, which is precisely what E1 exists to prevent.  Appending happens
# AFTER E1 has run and BEFORE the compile; Quartus rewrites the revision .qsf
# during a build anyway (sec.70.7), and `main()` already regenerates it
# afterwards.
SIGNALTAP_ASSIGNMENTS = (
    "set_global_assignment -name ENABLE_SIGNALTAP ON",
    "set_global_assignment -name USE_SIGNALTAP_FILE stp1.stp",
    "set_global_assignment -name SIGNALTAP_FILE stp1.stp",
)


def enable_signaltap(qsf_path):
    """Append the SignalTap assignments to a revision .qsf.  -> the lines added.

    Returns the list so the caller can put it in the receipt: a build that
    carries debug fabric must SAY SO in its own artifact, because the whole
    point of the default-off policy is that a flashed bitstream's debug
    capability is a recorded decision rather than an inherited default."""
    txt = qsf_path.read_text()
    add = [ln for ln in SIGNALTAP_ASSIGNMENTS if ln not in txt.splitlines()]
    if add:
        with open(qsf_path, "a") as f:
            f.write("\n# --- appended by quartus_gate.py --signaltap ---\n")
            f.write("\n".join(add) + "\n")
    return add


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
# WHAT THE GATE ACTUALLY RUNS -- one function, so a reviewer and a test can
# both read the command list without starting a ten-minute compile.
# --------------------------------------------------------------------------- #
def preflow_command():
    """The project's own `PRE_FLOW_SCRIPT_FILE`, run explicitly.  -> argv

    ⚠ A RIG DEFECT FOUND BY THIS WAVE, AND IT IS NOT THE SWEEP'S.
    `hdl/sys/sys.tcl:211` sets

        set_global_assignment -name PRE_FLOW_SCRIPT_FILE "quartus_sh:sys/build_id.tcl"

    and that hook is honoured by `quartus_sh --flow compile` and by NOTHING
    ELSE.  Any path that invokes `quartus_map` directly skips it, so
    `hdl/build_id.v` -- which `nec_test.sv:200` ``include`s -- is never
    generated and Analysis & Synthesis dies with

        Error (10054): ... can't open Verilog Design File "build_id.v"

    **That defect is in the RECORDED FOUR-STEP `--retention` RECIPE too**, and
    it has been latent since that recipe was first written: `build_id.v` is
    gitignored (`hdl/.gitignore:32`) and left behind by any previous CONTROL
    `--flow compile`, so every retention build ever taken found one already
    there.  On a FRESH tree -- a new clone, a new worktree, or a `db` clean
    that also removed it -- `--retention` fails at map.  Measured here, on this
    worktree, exit 3 in 11 s.  The fix is to run the hook explicitly rather
    than to depend on a leftover.

    `$quartus(args)` 1 and 2 are the project and the revision (index 0 is the
    flow name), which is how `--flow compile` calls it."""
    return [str(QUARTUS_BIN / "quartus_sh"), "-t", "sys/build_id.tcl",
            "preflow", PROJECT, REVISION]


def build_id_state():
    """What `build_id.v` holds -- RECORDED, deliberately NOT in the manifest.

    It is a genuine build input (`nec_test.sv:200` includes it) that
    `input_files()` does not name, and it CANNOT be added without cost: it
    carries `BUILD_DATE` as a `%y%m%d` stamp, so folding it into the manifest
    would move the input hash every midnight and destroy the comparability that
    lets this wave say its 88-file manifest `c23e63aa4cf19684…` is the same one
    the k=0.5 wave and the CHAIN_MAX draws were taken on.  So it is recorded
    beside the manifest instead of inside it, and the gap is named rather than
    closed silently."""
    p = HDL / "build_id.v"
    if not p.is_file():
        return {"present": False, "text": None, "sha256": None,
                "note": "absent -- the PRE_FLOW script has not run"}
    return {"present": True, "text": p.read_text(errors="replace").strip(),
            "sha256": art.sha256_file(p),
            "note": "a build input NOT in input_manifest: it is a %y%m%d date "
                    "stamp and would move the manifest hash daily"}


def build_commands(retention=False):
    """-> [[argv], ...].  The stages, in order, as they will be run.

    CONTROL is `quartus_sh --flow compile`, byte for byte what this gate has
    always run.  RETENTION is the RECORDED four-step manual recipe
    (`fuzzv2_retention_prereg_2026-08-08.md` §2 and §6.1, and four earlier
    pre-registrations in identical words) -- and the macro travels on
    `quartus_map` ONLY, because that is the stage that reads Verilog.

    THIS FUNCTION IS THE WHOLE POINT OF THE `--retention` FLAG.  Before it,
    the recipe lived only in prose across five documents, `build()` had no way
    to express it, and `X1_AD_RETENTION=1 python3 sw/quartus_gate.py` was
    ACCEPTED AND IGNORED -- it produced a CONTROL build whose `.rbf` was
    byte-identical to the control's and whose receipt (`aa3ca3e028dff7d2…`)
    was labelled RETENTION by hand while its DERIVED configuration read
    `CONTROL/DEFAULT`.  FLASH #18 §1.2 caught that on the derived label, one
    step before flashing it."""
    q = lambda n: str(QUARTUS_BIN / n)                        # noqa: E731
    if not retention:
        return [[q("quartus_sh"), "--flow", "compile", PROJECT, "-c", REVISION]]
    # ⚠ THE MACRO IS PASSED **UNQUOTED**, AND THAT IS NOT A DEVIATION FROM THE
    # RECORDED RECIPE.  Every pre-registration writes it as
    # `--verilog_macro="X1_AD_RETENTION=1"` because it is writing a SHELL
    # command line, where the shell strips the quotes.  This runs through
    # `subprocess` with no shell, so quotes here would reach the compiler as
    # literal characters.  Checked against the artifact rather than recall:
    # ALL TWELVE archived retention receipts -- including FLASH #18's
    # `277d5ccf0f8b9398…`, the bitstream on the board -- record
    # `configuration_detail.command_line` as
    #     quartus_map --verilog_macro=X1_AD_RETENTION=1 nec_test -c nec_test_ucore
    # i.e. UNQUOTED is what Quartus actually received, every time.
    #
    # ⚠ THE PRE_FLOW STAGE IS PREPENDED, AND IT IS A FIX, NOT A DEVIATION.
    # The four recorded stages below are UNCHANGED in content and in order.
    # What precedes them is the project's own `PRE_FLOW_SCRIPT_FILE`, which
    # `quartus_sh --flow compile` runs and a direct `quartus_map` does not --
    # see `preflow_command()`.  Without it this recipe cannot build on a tree
    # that has no leftover `hdl/build_id.v`, which every previous retention
    # build silently relied on.
    return [
        preflow_command(),
        [q("quartus_map"), f"--verilog_macro={RETENTION_MACRO}=1",
         PROJECT, "-c", REVISION],
        [q("quartus_fit"), PROJECT, "-c", REVISION],
        [q("quartus_asm"), PROJECT, "-c", REVISION],
        [q("quartus_sta"), PROJECT, "-c", REVISION],
    ]


# --------------------------------------------------------------------------- #
# THE DISTRIBUTION MODE -- map ONCE, fit N times at N distinct fitter seeds.
#
# WHY IT EXISTS.  `ucore_provenance.md` §74.4 asked for a multi-seed worst-of-N
# gate and nobody built one, so every Fmax in this repo from §52 onward is ONE
# DRAW of a distribution nobody had characterised.  The k=0.5 wave measured how
# bad that is: on the BYTE-IDENTICAL 88-file manifest `c23e63aa4cf19684…`,
# CONTROL drew 42.09 where three earlier draws agreed at 39.79, and RETENTION
# drew 39.99 where two agreed at 43.76 -- and the two configurations' ORDER
# flipped.  "Three agreeing draws" turned out to be a property of one session's
# determinism, not of the tree (`t1_half2_results_2026-08-13.md` §5).
#
# MAP ONCE, FIT N TIMES.  `quartus_fit --seed=<value>` sets the fitter's initial
# placement configuration; the mapped atom netlist in `db/` is the SAME netlist
# for every seed, which is exactly what makes the N draws a distribution OF ONE
# TREE rather than N different trees.  Verified two ways per seed, because a
# flag that is accepted and ignored is this repo's most-repeated trap:
#
#   * `<rev>.fit.rpt`'s own `Info: Command:` line must carry `--seed=<S>`, and
#   * the Fitter Settings table's `Seed` row, where Quartus echoes it back,
#
# and a disagreement between EITHER of those and what was ASKED is a hard RED
# (`E8`).  A sweep that silently ran eight identical fits would otherwise report
# a spread of 0.00 MHz and read as a reassuring result.
# --------------------------------------------------------------------------- #
def map_command(retention=False):
    """The ONE map stage the whole sweep shares.  -> argv"""
    q = str(QUARTUS_BIN / "quartus_map")
    argv = [q]
    if retention:
        argv.append(f"--verilog_macro={RETENTION_MACRO}=1")
    return argv + [PROJECT, "-c", REVISION]


def seed_commands(seed, asm=True):
    """The per-seed stages, in order.  -> [[argv], ...]

    NO `quartus_map` HERE, DELIBERATELY: re-mapping per seed would make each
    draw a different netlist and the sweep would measure Analysis & Synthesis
    non-determinism (§74.4a: the COMBINATIONAL counts are not reproducible run
    to run) on top of placement variance, which is two effects reported as one.
    The macro therefore does NOT appear on any stage here -- it travelled on the
    single shared map, and `parse_configuration` reads it back off `map.rpt`.

    ⚠ `--recompile=off` IS PINNED EXPLICITLY, not left to the default.  Rapid
    Recompile reuses the PREVIOUS compilation's placement and routing, and the
    project carries `SMART_RECOMPILE ON`; a sweep in which fit N+1 started from
    fit N's placement would report a spread that is an artefact of the order the
    seeds were run in.  Off is already the default -- pinning it says so in the
    command line that lands in the receipt, where a reader can check it."""
    q = lambda n: str(QUARTUS_BIN / n)                        # noqa: E731
    cmds = [[q("quartus_fit"), f"--seed={seed}", "--recompile=off",
             PROJECT, "-c", REVISION]]
    if asm:
        cmds.append([q("quartus_asm"), PROJECT, "-c", REVISION])
    cmds.append([q("quartus_sta"), PROJECT, "-c", REVISION])
    return cmds


def truefmax_command(outstem):
    """`sta_truefmax_probe.tcl` on the fitted netlist -> the per-k-class
    ceilings.  Not a bar: it is the only instrument that ranks by `slack / k`
    instead of by slack, and `standing_gates.md` §A's erratum says a ceiling
    quoted without `k` is not quotable."""
    return [str(QUARTUS_BIN / "quartus_sta"), "-t",
            str(ROOT / "sw" / "sta_truefmax_probe.tcl"),
            PROJECT, REVISION, str(outstem)]


def parse_fit_seed(tree, log_text=""):
    """-> {'command_line': int|None, 'settings': int|None, 'settings_row': str}
    -- the seed QUARTUS used, read back out of Quartus's own output.

    This is the `want_raw` lesson applied to `--seed`: verify the flag exists
    AND that the callee honoured it.  TWO INDEPENDENT READINGS, and they are
    not the same claim:

      * **`settings`** -- the Fitter Settings row **`Fitter Initial Placement
        Seed`** in `<rev>.fit.rpt`.  This is the STRONG reading: it is Quartus
        reporting the seed it actually placed with.
      * **`command_line`** -- Quartus's own `Info: Command:` echo, which
        `quartus_fit` prints to stdout (so it lands in this gate's transcript,
        NOT in `fit.rpt` -- measured: `fit.rpt` contains no `Info: Command:`
        line at all).  It proves what the binary RECEIVED, which is weaker
        than what it USED, so it is the corroborating reading and never the
        only one relied on.

    ⚠ THE ROW IS NOT CALLED `Seed`.  A first cut of this parser matched
    `; Seed ;` and found nothing, so E8 went RED on a fit that had in fact
    honoured the seed exactly.  That RED was correct behaviour -- absence must
    not read as agreement -- and it is why the bar exists rather than a
    comment."""
    out = {"command_line": None, "settings": None, "settings_row": None}
    rpt = tree / f"{REVISION}.fit.rpt"
    if rpt.exists():
        txt = rpt.read_text(errors="replace")
        m = re.search(r";\s*Fitter Initial Placement Seed\s*;\s*(\d+)\s*;", txt)
        if m:
            out["settings"] = int(m.group(1))
            out["settings_row"] = m.group(0).strip()
    # The LAST quartus_fit echo in the transcript is this seed's: the log is
    # appended stage by stage across the whole sweep.
    hits = re.findall(r"Info: Command: quartus_fit[^\n]*--seed=(\d+)",
                      log_text or "")
    if hits:
        out["command_line"] = int(hits[-1])
    return out


_TF_HEAD = re.compile(r"^---\s+(.*?)\s+---\s*$")
_TF_ROW = re.compile(r"k\s*=\s*([\d.]+)\s+slack\s*=\s*([+-][\d.]+)\s*->\s*"
                     r"T_min\s*([\d.]+)\s*ns\s*=\s*([\d.]+)\s*MHz")


def parse_truefmax(path):
    """-> {class label: {k, slack, t_min_ns, fmax_mhz, from, to}}

    Parses `sta_truefmax_probe.tcl`'s own text artifact.  A class the probe
    could not populate ('(no paths)') is recorded as an entry with `fmax_mhz`
    None rather than dropped -- absence must not read as data."""
    out = {}
    if not Path(path).exists():
        return out
    label = None
    cur = {}
    for ln in Path(path).read_text(errors="replace").splitlines():
        h = _TF_HEAD.match(ln.strip())
        if h:
            if label:
                out[label] = cur
            label, cur = h.group(1), {"from": None, "to": None, "k": None,
                                      "slack": None, "t_min_ns": None,
                                      "fmax_mhz": None}
            continue
        if label is None:
            continue
        if ln.strip().startswith("from  :"):
            cur["from"] = ln.split(":", 1)[1].strip()
        elif ln.strip().startswith("to    :"):
            cur["to"] = ln.split(":", 1)[1].strip()
        else:
            m = _TF_ROW.search(ln)
            if m:
                cur.update(k=float(m.group(1)), slack=float(m.group(2)),
                           t_min_ns=float(m.group(3)),
                           fmax_mhz=float(m.group(4)))
    if label:
        out[label] = cur
    return out


# THE ONE DECLARED EXEMPTION, AND IT IS DECLARED RATHER THAN DISCOVERED.
# Quartus REWRITES the revision `.qsf` it compiles (§70.7) -- that is the whole
# reason E1 must run BEFORE the build and `gen_ucore_qsf.py` is re-run after
# it.  So this file moves on EVERY build, by the compiler, and calling that a
# mid-build input flip would make E7 fire on every green run: a bar that always
# fails is a bar nobody reads.  It is the SAME single exemption the fabric era
# guard already carries ("87/88, the `.qsf` the one §70.7 exemption").
#
# ⚠ IT IS A NAMED LIST OF ONE, NOT A PATTERN.  Anything else moving mid-build
# is a RED, including the OTHER `.qsf` (`hdl/nec_test.qsf` is hand-maintained;
# Quartus does not rewrite it, and if it moved during a compile that is exactly
# the event this bar exists for).
INPUT_FLIP_EXEMPT = ("hdl/nec_test_ucore.qsf",)


def input_stability_bar(pre, post):
    """E7 -- THE INPUT-HASH ORDERING BAR.

    The manifest is hashed BEFORE `quartus_map` (it must be: it has to name
    what the compiler was handed) and re-hashed AFTER the last stage.  If a
    tracked input moved while a ten-to-twenty-minute compile was running, the
    receipt would name a byte set the build only partly read, and every figure
    under it would be attributed to the wrong tree.  The CHAIN_MAX wave found
    exactly this gap: nothing re-read the inputs, so a mid-build RTL flip was
    undetectable after the fact.  A DIFFERENCE IS A RED, not a warning."""
    moved = sorted(k for k in set(pre["files"]) | set(post["files"])
                   if pre["files"].get(k) != post["files"].get(k))
    exempt = [k for k in moved if k in INPUT_FLIP_EXEMPT]
    offend = [k for k in moved if k not in INPUT_FLIP_EXEMPT]
    return {"bar": "no input moved between the hash taken before quartus_map "
                   "and the hash taken after the last stage, except the one "
                   "DECLARED §70.7 exemption (Quartus rewrites the revision "
                   f".qsf it compiles): {', '.join(INPUT_FLIP_EXEMPT)}",
            "value": {"pre_sha256": pre["sha256"], "post_sha256": post["sha256"],
                      "n_moved": len(moved), "moved": moved[:20],
                      "moved_exempt": exempt, "moved_offending": offend[:20],
                      "exemptions": list(INPUT_FLIP_EXEMPT)},
            "pass": not offend}


def seed_honoured_bar(asked, seen):
    """E8 -- the fitter used the seed it was given, read back off its own
    report.  Without this a sweep whose `--seed` was ignored reports a spread
    of 0.00 MHz, which reads as a REASSURING result."""
    cl, st = seen.get("command_line"), seen.get("settings")
    present = [v for v in (cl, st) if v is not None]
    return {"bar": f"quartus_fit honoured --seed={asked}: the `Fitter Initial "
                   f"Placement Seed` row of its own fit.rpt (the seed it USED) "
                   f"must say so, corroborated by Quartus's `Info: Command:` "
                   f"echo (the seed it RECEIVED)",
            "value": {"asked": asked, "command_line": cl, "settings": st,
                      "settings_row": seen.get("settings_row")},
            # The STRONG reading must be present -- a corroborating echo alone
            # says only what the binary was handed, and this bar is about what
            # it did.  And every reading that IS present must agree.
            "pass": (st == asked and bool(present)
                     and all(v == asked for v in present))}


def build(tree, keep_db, logpath, retention=False):
    cmds = build_commands(retention)
    for c in cmds:
        if not Path(c[0]).exists():
            print(f"quartus_gate: {c[0]} not found -- the gate CANNOT RUN "
                  f"(this is exit 2, not a PASS and not a RED)")
            return None, 2
    if not keep_db:
        for d in ("db", "incremental_db", OUTDIR):
            shutil.rmtree(HDL / d, ignore_errors=True)
    t0 = time.time()
    stages, rc = [], 0
    # ONE log, appended stage by stage, because `report_manifest()` hashes it
    # into the receipt and a gate whose transcript is split across files has a
    # receipt that does not name what it read.
    with open(logpath, "w") as lf:
        for c in cmds:
            print(f"quartus_gate: {' '.join(c)}   (cwd {HDL})", flush=True)
            lf.write(f"\n=== quartus_gate stage: {' '.join(c)}\n")
            lf.flush()
            s0 = time.time()
            src = subprocess.run(c, cwd=HDL, stdout=lf,
                                 stderr=subprocess.STDOUT).returncode
            stages.append({"cmd": c, "rc": src,
                           "seconds": round(time.time() - s0, 1)})
            print(f"quartus_gate:   rc={src} in {time.time()-s0:.0f}s",
                  flush=True)
            if src != 0:
                # A LATER STAGE MUST NOT RUN ON AN EARLIER ONE'S FAILURE.  It
                # would read the PREVIOUS build's database and emit reports
                # that look like this run's.
                rc = src
                print(f"quartus_gate: stage failed -- remaining "
                      f"{len(cmds) - len(stages)} stage(s) NOT run", flush=True)
                break
    print(f"quartus_gate: compile rc={rc} in {time.time()-t0:.0f}s "
          f"(log {logpath})", flush=True)
    cmd = cmds[0] if len(cmds) == 1 else cmds
    return {"cmd": cmd, "rc": rc, "seconds": round(time.time() - t0, 1),
            "configuration_requested": ("RETENTION" if retention
                                        else "CONTROL/DEFAULT"),
            "stages": stages, "log": str(logpath)}, 0


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


def parse_seed_spec(spec):
    """`--seeds 8` -> [1..8];  `--seeds 1,7,99` -> [1, 7, 99].  -> sorted, unique

    An integer count means seeds 1..N so that a sweep is REPRODUCIBLE by name:
    `worst-of-8@seeds{1..8}` says exactly which eight fits it is."""
    spec = spec.strip()
    if re.fullmatch(r"\d+", spec):
        n = int(spec)
        if n < 1:
            raise ValueError("--seeds N needs N >= 1")
        return list(range(1, n + 1))
    toks = [x for x in re.split(r"[,\s]+", spec) if x]
    if not toks or not all(re.fullmatch(r"\d+", t) for t in toks):
        raise ValueError(f"--seeds {spec!r} is not a count or a list of "
                         f"non-negative integers")
    seeds = sorted({int(t) for t in toks})
    if any(s < 1 for s in seeds):
        raise ValueError("--seeds: a fitter seed must be >= 1")
    return seeds


def _stat(vals):
    """min / median / max over the draws that produced a number.

    The median of an even N is the mean of the two middle ORDER STATISTICS, so
    it is a number no seed drew; `sorted` is carried beside it so a reader can
    always see the draws themselves rather than a summary of them."""
    s = sorted(v for v in vals if v is not None)
    if not s:
        return {"n": 0, "min": None, "median": None, "max": None,
                "spread": None, "sorted": []}
    n = len(s)
    med = s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0
    return {"n": n, "min": s[0], "median": med, "max": s[-1],
            "spread": round(s[-1] - s[0], 4), "sorted": s}


def run_sweep(a, tree, receipt_path, logpath):
    """THE G6 DISTRIBUTION GATE.  One mapped netlist, N fits, N receipts, one
    distribution record.  -> exit code

    THE QUOTING RULE THIS IMPLEMENTS (`standing_gates.md` §A):
      * the quotable figure is `worst-of-N@seeds{...}` -- the MINIMUM over the
        N draws, with N and the seed set named;
      * a single fit is `draw@seed<S>` and is NOT promotion evidence;
      * G6 PASS for a PROMOTION needs N >= 5.  N = 2 stays acceptable for an
        intermediate wave measurement, WITH the caveat printed.
    """
    seeds = parse_seed_spec(a.seeds)
    art_dir = Path(a.artifact_dir) if a.artifact_dir else (
        ROOT / "sw" / "testdata" / "g6dist" /
        (a.label or time.strftime("sweep-%Y%m%dT%H%M%SZ", time.gmtime())))
    art_dir.mkdir(parents=True, exist_ok=True)
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    for c in [map_command(a.retention)] + seed_commands(seeds[0], not a.no_asm):
        if not Path(c[0]).exists():
            print(f"quartus_gate: {c[0]} not found -- the gate CANNOT RUN "
                  f"(exit 2, not a PASS and not a RED)")
            return 2

    # --- E1, before anything is compiled ----------------------------------- #
    e1 = {"pass": None, "note": "skipped (--no-qsf-check)"}
    if not a.no_qsf_check:
        r = subprocess.run([sys.executable, str(ROOT / "sw" / "gen_ucore_qsf.py"),
                            "--check"], capture_output=True, text=True)
        e1 = {"bar": "hdl/nec_test_ucore.qsf is a faithful derivative of "
                     "hdl/nec_test.qsf",
              "rc": r.returncode, "out": (r.stdout + r.stderr).strip(),
              "pass": r.returncode == 0}
        print(f"quartus_gate: E1 gen_ucore_qsf --check -> "
              f"{'PASS' if e1['pass'] else 'RED'}: {e1['out']}", flush=True)
        if not e1["pass"]:
            print("quartus_gate: RED at E1 -- nothing built, no sweep run.")
            return 1

    # --- the inputs, hashed BEFORE quartus_map (E7's `pre`) ----------------- #
    mf_pre = input_manifest()
    tv = tool_version()
    print(f"quartus_gate: sweep over {len(seeds)} seed(s) {seeds}, "
          f"{'RETENTION' if a.retention else 'CONTROL/DEFAULT'}, "
          f"inputs {mf_pre['n_files']} files sha256 {mf_pre['sha256'][:16]}…",
          flush=True)

    if not a.keep_db:
        for d in ("db", "incremental_db", OUTDIR):
            shutil.rmtree(HDL / d, ignore_errors=True)
    tree.mkdir(parents=True, exist_ok=True)

    t_all = time.time()
    stages_log = []

    def stage(cmd, lf, tag):
        print(f"quartus_gate: [{tag}] {' '.join(cmd)}", flush=True)
        lf.write(f"\n=== quartus_gate {tag}: {' '.join(cmd)}\n")
        lf.flush()
        t0 = time.time()
        rc = subprocess.run(cmd, cwd=HDL, stdout=lf,
                            stderr=subprocess.STDOUT).returncode
        el = round(time.time() - t0, 1)
        print(f"quartus_gate:   [{tag}] rc={rc} in {el:.0f}s", flush=True)
        stages_log.append({"tag": tag, "cmd": cmd, "rc": rc, "seconds": el})
        return rc

    # --- THE PRE_FLOW HOOK, THEN THE SINGLE SHARED MAP ---------------------- #
    # `quartus_map` invoked directly does NOT run PRE_FLOW_SCRIPT_FILE, so
    # `hdl/build_id.v` would be missing and A&S would die at nec_test.sv:200.
    # See `preflow_command()`.
    with open(logpath, "w") as lf:
        rc = stage(preflow_command(), lf, "preflow")
        if rc == 0:
            rc = stage(map_command(a.retention), lf, "map")
    bid = build_id_state()
    print(f"quartus_gate: build_id.v {bid['text']!r} "
          f"(recorded beside the manifest, not inside it)", flush=True)
    if rc != 0:
        print(f"quartus_gate: the shared preflow/map FAILED (rc={rc}) -- no "
              f"seed was "
              f"fitted.  (exit 1)  log {logpath}")
        return 1

    # --- N FITS ------------------------------------------------------------ #
    per_seed = []
    for i, seed in enumerate(seeds, 1):
        print(f"\nquartus_gate: === seed {seed}  ({i}/{len(seeds)}) ===",
              flush=True)
        t0 = time.time()
        seed_rc = 0
        with open(logpath, "a") as lf:
            for cmd in seed_commands(seed, not a.no_asm):
                seed_rc = stage(cmd, lf, f"seed{seed}:{Path(cmd[0]).name}")
                if seed_rc != 0:
                    break
            tf_path = None
            if seed_rc == 0 and not a.no_truefmax:
                stem = tree / f"g6dist_seed{seed}"
                if stage(truefmax_command(stem), lf,
                         f"seed{seed}:truefmax") == 0:
                    tf_path = Path(f"{stem}.truefmax.txt")

        log_text = logpath.read_text(errors="replace") if logpath.exists() else ""
        cfg, cfg_detail = parse_configuration(tree)
        bars, figs = score(tree, log_text, a)
        seen = parse_fit_seed(tree, log_text)
        bars["E8_seed_honoured"] = seed_honoured_bar(seed, seen)
        truefmax = parse_truefmax(tf_path) if tf_path else {}

        rec = {"schema": art.SCHEMA, "schema_version": art.SCHEMA_VERSION,
               "kind": "quartus_bitstream",
               "name": art.relpath(tree / f"{REVISION}.sof"),
               "label": f"{a.label or 'g6dist'}-seed{seed}",
               "inputs": mf_pre,
               "command": seed_commands(seed, not a.no_asm),
               "env": {},
               "tool": tv, "tool_name": "quartus_sh", "tool_probe": None,
               "tool_sha256": None,
               "outputs": {},
               "git": art.git_state(),
               "started": started, "completed": None, "rc": seed_rc,
               "figures": figs, "verdict": None,
               "gate": GATE_NAME, "gate_version": GATE_VERSION,
               "ts": started, "tool_version": tv, "input_manifest": mf_pre,
               "configuration": cfg, "configuration_detail": cfg_detail,
               "reports": report_manifest(tree, logpath),
               "tree": str(tree),
               "E1_gen_ucore_qsf": e1,
               # WHAT MAKES THIS RECEIPT A DISTRIBUTION DRAW AND NOT A BUILD.
               # It SELF-LABELS both axes -- the configuration (derived, as
               # always, from the reports) and the seed (asked AND echoed) --
               # so a figure lifted out of the history can never be re-attached
               # to the wrong config or the wrong draw.
               "sweep": {"seed": seed, "seed_index": i, "seed_set": seeds,
                         "n_seeds": len(seeds),
                         "seed_echo": seen,
                         "map_shared": True,
                         "map_command": map_command(a.retention),
                         "asm": not a.no_asm,
                         "configuration_requested": ("RETENTION" if a.retention
                                                     else "CONTROL/DEFAULT")},
               "truefmax": truefmax,
               "build_id": bid,
               "seconds": round(time.time() - t0, 1),
               "build": {"note": "one shared quartus_map; this receipt is ONE "
                                 "FIT of the sweep",
                         "stages": [s for s in stages_log
                                    if s["tag"].startswith(f"seed{seed}:")],
                         "configuration_requested": ("RETENTION" if a.retention
                                                     else "CONTROL/DEFAULT"),
                         "log": str(logpath)}}
        for ext in (".sof", ".rbf", ".sta.summary", ".fit.summary"):
            f = tree / f"{REVISION}{ext}"
            if f.is_file():
                rec["outputs"][art.relpath(f)] = art.sha256_file(f)
        ok = all(v["pass"] for v in bars.values()) and (
            a.no_qsf_check or e1["pass"])
        rec["bars"] = bars
        rec["verdict"] = "PASS" if ok else "RED"
        rp = art_dir / f"seed{seed}_quartus_gate.json"
        _finish(rec, rp)

        # The durable copies.  `hdl/output_files_ucore/` is deleted by the
        # gate's own next clean build, so an artifact that lived only there
        # would be a distribution of exactly one run.
        for src, dst in ((tf_path, art_dir / f"seed{seed}.truefmax.txt"),
                         (tree / f"{REVISION}.sta.summary",
                          art_dir / f"seed{seed}.sta.summary")):
            if src and Path(src).is_file():
                shutil.copyfile(src, dst)

        fm = bars["E3_fmax"]["value"]
        print(f"quartus_gate: seed {seed}: {rec['verdict']}  "
              f"Fmax {fm}  setup {bars['E4_worst_setup']['value']}  "
              f"ALMs {figs['status'].get('alms')}  "
              f"receipt {rec['id'][:16]}…", flush=True)
        per_seed.append({"seed": seed, "verdict": rec["verdict"],
                         "receipt_id": rec["id"],
                         "receipt": art.relpath(rp),
                         "fmax_mhz": fm,
                         "worst_setup_ns": bars["E4_worst_setup"]["value"],
                         "tns_violations": bars["E5_tns"]["value"],
                         "alms": figs["status"].get("alms"),
                         "seed_honoured": bars["E8_seed_honoured"]["pass"],
                         "seed_echo": seen,
                         "configuration": cfg,
                         "outputs": rec["outputs"],
                         "truefmax": {k: v.get("fmax_mhz")
                                      for k, v in truefmax.items()},
                         "truefmax_full": truefmax,
                         "seconds": rec["seconds"]})

    # --- E7: the inputs, re-hashed AFTER the last stage --------------------- #
    mf_post = input_manifest()
    e7 = input_stability_bar(mf_pre, mf_post)
    print(f"\nquartus_gate: E7 input stability -> "
          f"{'PASS' if e7['pass'] else 'RED'}  "
          f"({e7['value']['n_moved']} file(s) moved during the sweep; "
          f"exempt {e7['value']['moved_exempt']}, "
          f"OFFENDING {e7['value']['moved_offending']})", flush=True)

    subprocess.run([sys.executable, str(ROOT / "sw" / "gen_ucore_qsf.py")],
                   capture_output=True, text=True)

    # --- THE DISTRIBUTION RECORD ------------------------------------------- #
    fmaxes = [p["fmax_mhz"] for p in per_seed]
    classes = sorted({k for p in per_seed for k in p["truefmax"]})
    by_class = {c: _stat([p["truefmax"].get(c) for p in per_seed])
                for c in classes}
    # DOES THE BINDING CONE FLIP?  The probe names the worst path per class; the
    # question the k=0.5 wave leaves open is whether the IDENTITY of the binding
    # cone is a property of the tree or of the draw.  Both are recorded: the
    # CLASS that binds, and the endpoint PAIR inside it.
    binding = []
    for p in per_seed:
        d = p["truefmax_full"].get("DEFAULT (whole-design worst, expect k=1)", {})
        binding.append({"seed": p["seed"], "from": d.get("from"),
                        "to": d.get("to"), "k": d.get("k"),
                        "fmax_mhz": d.get("fmax_mhz")})
    ok_fm = [f for f in fmaxes if f is not None]
    worst = min(ok_fm) if ok_fm else None
    worst_seed = (min(per_seed, key=lambda p: (p["fmax_mhz"] is None,
                                               p["fmax_mhz"]))["seed"]
                  if ok_fm else None)
    n = len(seeds)
    dist = {"schema": art.SCHEMA, "schema_version": art.SCHEMA_VERSION,
            "kind": "quartus_distribution",
            "name": art.relpath(art_dir / "distribution.json"),
            "label": a.label,
            "inputs": mf_pre, "inputs_post": mf_post,
            "command": [map_command(a.retention)] + seed_commands(
                seeds[0], not a.no_asm),
            "env": {}, "tool": tv, "tool_name": "quartus_sh",
            "tool_probe": None, "tool_sha256": None,
            "outputs": {}, "git": art.git_state(),
            "started": started, "completed": None, "rc": 0,
            "gate": GATE_NAME, "gate_version": GATE_VERSION, "ts": started,
            "tool_version": tv, "input_manifest": mf_pre,
            "configuration": (per_seed[0]["configuration"] if per_seed
                              else "UNDETERMINED -- no seed completed"),
            "tree": str(tree), "artifact_dir": art.relpath(art_dir),
            "E1_gen_ucore_qsf": e1, "build_id": bid,
            "seeds": seeds, "n_seeds": n,
            "per_seed": per_seed,
            "fmax": _stat(fmaxes),
            "worst_setup_ns": _stat([p["worst_setup_ns"] for p in per_seed]),
            "alms": sorted({p["alms"] for p in per_seed}),
            "by_class": by_class,
            "binding_path_per_seed": binding,
            "binding_class_flips": len({(b["from"], b["to"]) for b in binding}),
            "bars": {"E7_input_stability": e7,
                     "E8_all_seeds_honoured": {
                         "bar": "every fit used the seed it was given",
                         "value": [p["seed"] for p in per_seed
                                   if not p["seed_honoured"]],
                         "pass": all(p["seed_honoured"] for p in per_seed)},
                     "E9_all_seeds_pass": {
                         "bar": f"every one of the {n} draws is a G6 PASS "
                                f"(E1-E5)",
                         "value": [p["seed"] for p in per_seed
                                   if p["verdict"] != "PASS"],
                         "pass": all(p["verdict"] == "PASS" for p in per_seed)},
                     "E10_promotion_width": {
                         "bar": "N >= 5 for a PROMOTION figure (N = 2 is an "
                                "intermediate-wave measurement and prints its "
                                "own caveat)",
                         "value": n,
                         "pass": n >= 5}},
            "worst_of_n": {"n": n, "seeds": seeds, "fmax_mhz": worst,
                           "seed": worst_seed,
                           "quotable_as": (f"worst-of-{n}@seeds{{"
                                           f"{','.join(map(str, seeds))}}} "
                                           f"= {worst} MHz"
                                           if worst is not None else None),
                           "promotion_grade": n >= 5}}
    # THE VERDICT IS THE WORST DRAW'S, NOT THE BEST'S, AND NOT THE MEAN'S.
    dist["verdict"] = "PASS" if (
        dist["bars"]["E7_input_stability"]["pass"]
        and dist["bars"]["E8_all_seeds_honoured"]["pass"]
        and dist["bars"]["E9_all_seeds_pass"]["pass"]) else "RED"
    dist["seconds"] = round(time.time() - t_all, 1)
    dist["stages"] = stages_log
    _finish(dist, art_dir / "distribution.json")
    art._write_json_atomic(Path(receipt_path), dist)

    print("\n  --- quartus_gate (G6) DISTRIBUTION ---")
    print(f"  tool     : {tv}")
    print(f"  config   : {dist['configuration']}")
    print(f"  inputs   : {mf_pre['n_files']} files, "
          f"sha256 {mf_pre['sha256'][:16]}…   E7 "
          f"{'PASS' if e7['pass'] else 'RED'}")
    print(f"  seeds    : {seeds}   (one shared quartus_map, {n} fits)")
    print(f"  {'seed':>6}  {'Fmax':>8}  {'setup':>8}  {'ALMs':>16}  verdict")
    for p in per_seed:
        print(f"  {p['seed']:>6}  {str(p['fmax_mhz']):>8}  "
              f"{str(p['worst_setup_ns']):>8}  {str(p['alms']):>16}  "
              f"{p['verdict']}")
    f = dist["fmax"]
    print(f"  Fmax     : min {f['min']}  median {f['median']}  max {f['max']}"
          f"   SPREAD {f['spread']} MHz")
    for c in classes:
        s = by_class[c]
        print(f"    class   {c[:46]:<46} min {s['min']}  med {s['median']}  "
              f"max {s['max']}  spread {s['spread']}")
    print(f"  binding cone distinct endpoint pairs over {n} draws: "
          f"{dist['binding_class_flips']}")
    print(f"\n  *** THE QUOTABLE FIGURE: {dist['worst_of_n']['quotable_as']} "
          f"(worst seed {worst_seed}) ***")
    if n < 5:
        print(f"  ⚠ N = {n} < 5: this is an INTERMEDIATE-WAVE measurement and "
              f"is NOT promotion evidence.")
    print(f"  record   : {art.relpath(art_dir / 'distribution.json')}  "
          f"id {dist['id'][:16]}…")
    print(f"=== quartus_gate DISTRIBUTION: {dist['verdict']}   "
          f"{dist['seconds']:.0f}s")
    return 0 if dist["verdict"] == "PASS" else 1


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
    ap.add_argument("--retention", action="store_true",
                    help=f"build the RETENTION configuration: the recorded "
                         f"four-step manual recipe with "
                         f"--verilog_macro={RETENTION_MACRO}=1 on quartus_map. "
                         f"Without this flag the gate builds CONTROL, and the "
                         f"environment variable of that name is REFUSED.")
    ap.add_argument("--signaltap", action="store_true",
                    help="build WITH the SignalTap debug fabric.  DEFAULT OFF: "
                         "G6 and flash builds carry no debug fabric, and the "
                         "three assignments are appended to the revision .qsf "
                         "for this build only (and recorded in the receipt).  "
                         "Needs an hdl/stp1.stp, which does not exist yet.")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the stages this invocation would run, and "
                         "exit 0.  Builds nothing, writes no receipt.")
    ap.add_argument("--seeds", default="",
                    help="THE DISTRIBUTION GATE.  `N` means seeds 1..N; a "
                         "comma list means exactly those seeds.  Runs ONE "
                         "quartus_map and then N quartus_fit --seed=S, so the "
                         "N draws are a distribution of ONE mapped netlist.  "
                         "The quotable figure is worst-of-N@seeds{...}; a "
                         "single draw is not promotion evidence.")
    ap.add_argument("--artifact-dir", default="",
                    help="where the per-seed receipts, .sta.summary and "
                         "truefmax artifacts are kept (they must outlive "
                         "hdl/" + OUTDIR + ", which the next clean build "
                         "deletes).  Default sw/testdata/g6dist/<label>.")
    ap.add_argument("--no-asm", action="store_true",
                    help="sweep only: skip quartus_asm.  Faster, but the draw "
                         "then has no .sof/.rbf to hash and is a TIMING "
                         "measurement rather than a candidate bitstream.")
    ap.add_argument("--no-truefmax", action="store_true",
                    help="sweep only: skip sta_truefmax_probe.tcl, i.e. record "
                         "no per-k-class ceilings for the draw.")
    a = ap.parse_args()

    # --- THE ENV-VAR REFUSAL ------------------------------------------------ #
    # FLASH #18 §1.2.  `X1_AD_RETENTION=1 python3 sw/quartus_gate.py` was
    # ACCEPTED AND IGNORED: `build()` never read the environment and never
    # passed `--verilog_macro`, so it silently produced a CONTROL build whose
    # `.rbf` was byte-identical to the control's.  Only the receipt's DERIVED
    # `configuration` caught it, one step before that build was flashed.
    # ACCEPTED-AND-IGNORED IS NOW REFUSED-WITH-REASON: the variable can no
    # longer reach a run that will not honour it.
    env_ret = os.environ.get(RETENTION_MACRO)
    if env_ret not in (None, "") and not a.retention:
        print(f"quartus_gate: REFUSING TO RUN.\n"
              f"  {RETENTION_MACRO}={env_ret!r} is set in the environment, and "
              f"THIS GATE HAS NEVER READ IT.\n"
              f"  The macro reaches the compiler ONLY via --retention, which "
              f"puts it on quartus_map's\n"
              f"  command line.  Without that flag the variable reaches "
              f"nothing and the build would be\n"
              f"  a CONTROL build silently labelled by whatever you called "
              f"it.  That happened at\n"
              f"  FLASH #18 (receipt aa3ca3e028dff7d2…, label RETENTION / "
              f"derived CONTROL/DEFAULT) and\n"
              f"  it was caught by the derived label one step before the flash "
              f"-- see\n"
              f"  docs/notes/fz2_flash18_results_2026-08-11.md §1.2.\n"
              f"  Do one of:\n"
              f"    python3 sw/quartus_gate.py --retention     "
              f"# the RETENTION build, macro passed on the command line\n"
              f"    unset {RETENTION_MACRO}; python3 sw/quartus_gate.py    "
              f"# the CONTROL build\n"
              f"  (this is exit 2 -- the gate could not run.  Not a PASS and "
              f"not a RED.)")
        return 2
    if a.retention and a.parse_only:
        print(f"quartus_gate: REFUSING TO RUN.  --retention BUILDS and "
              f"--parse-only does not build;\n"
              f"  a run that is both would gate whatever reports happen to be "
              f"on disk while\n"
              f"  claiming a configuration it never compiled.  Use "
              f"--retention alone, or --parse-only\n"
              f"  --no-qsf-check to re-gate a retention tree built earlier.  "
              f"(exit 2)")
        return 2
    if a.seeds and a.parse_only:
        print("quartus_gate: REFUSING TO RUN.  --seeds BUILDS (one map, N "
              "fits) and --parse-only\n"
              "  does not build.  A run that is both would report a "
              "DISTRIBUTION over N draws while\n"
              "  having taken exactly one -- a spread of 0.00 MHz that reads "
              "as a reassuring\n"
              "  result.  Use --seeds alone.  (exit 2)")
        return 2
    if a.seeds:
        try:
            parse_seed_spec(a.seeds)
        except ValueError as e:
            print(f"quartus_gate: REFUSING TO RUN.  --seeds: {e}  (exit 2)")
            return 2
    if (a.no_asm or a.no_truefmax or a.artifact_dir) and not a.seeds:
        print("quartus_gate: REFUSING TO RUN.  --no-asm / --no-truefmax / "
              "--artifact-dir are\n"
              "  SWEEP-ONLY flags and this invocation has no --seeds, so they "
              "would be\n"
              "  ACCEPTED AND IGNORED -- the exact trap `--retention` was "
              "built to close\n"
              "  (docs/notes/fz2_flash18_results_2026-08-11.md §1.2).  "
              "(exit 2)")
        return 2

    if a.dry_run:
        if a.seeds:
            seeds = parse_seed_spec(a.seeds)
            print(f"quartus_gate --dry-run: DISTRIBUTION, "
                  f"{'RETENTION' if a.retention else 'CONTROL/DEFAULT'}, "
                  f"{len(seeds)} seed(s) {seeds}, cwd {HDL}")
            print("  " + " ".join(preflow_command())
                  + "     # ONCE (PRE_FLOW_SCRIPT_FILE; a direct "
                    "quartus_map does not run it)")
            print("  " + " ".join(map_command(a.retention)) + "     # ONCE")
            for c in seed_commands(seeds[0], not a.no_asm):
                print("  " + " ".join(c) + "     # per seed")
            if not a.no_truefmax:
                print("  " + " ".join(truefmax_command("<tree>/g6dist_seed<S>"))
                      + "     # per seed")
            print(f"  (nothing built, no receipt written.  The quotable "
                  f"figure would be\n"
                  f"   worst-of-{len(seeds)}@seeds"
                  f"{{{','.join(map(str, seeds))}}}"
                  + ("" if len(seeds) >= 5 else
                     "  -- N < 5, NOT promotion evidence") + ".)")
            return 0
        cmds = build_commands(a.retention)
        print(f"quartus_gate --dry-run: "
              f"{'RETENTION' if a.retention else 'CONTROL/DEFAULT'}, "
              f"{len(cmds)} stage(s), cwd {HDL}")
        for c in cmds:
            print("  " + " ".join(c))
        print("  (nothing built, no receipt written.  The receipt's "
              "`configuration` is still DERIVED\n"
              "   from the reports after a real run -- never from this flag.)")
        return 0

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

    if a.seeds:
        return run_sweep(a, tree, receipt_path, logpath)

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
           # Only ever non-empty on the `--retention` path, where the variable
           # is ALLOWED (harmless -- the macro travels on the command line) and
           # RECORDED.  Without `--retention` a set variable is refused above,
           # so this key can never silently describe a build that ignored it.
           "env": ({RETENTION_MACRO: env_ret} if env_ret else {}),
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
        # AFTER E1, BEFORE THE COMPILE.  E1 must see the tree's own faithful
        # derivation; the compiler must see the debug fabric this run asked
        # for.  Recorded either way -- `[]` is "asked for nothing", and the
        # key is always present so a receipt can never be silent about it.
        rec["signaltap"] = {"requested": a.signaltap, "assignments_added": []}
        if a.signaltap:
            added = enable_signaltap(HDL / f"{REVISION}.qsf")
            rec["signaltap"]["assignments_added"] = added
            print(f"quartus_gate: --signaltap -> appended {len(added)} "
                  f"assignment(s) to {REVISION}.qsf", flush=True)
        b, rc = build(tree, a.keep_db, logpath, retention=a.retention)
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
    # ⚠ `--retention` IS **NOT** AN INPUT HERE, DELIBERATELY.  What the flag
    # asked for is recorded in `build.configuration_requested`; what the build
    # actually did is DERIVED from the reports, and only the derived value goes
    # in `configuration`.  A flag that asserted its own configuration would be
    # the `4bb65d2ab6` defect the derived label was built to catch, and it is
    # precisely the disagreement between the two that caught FLASH #18's
    # mis-invocation.  Keeping them independent keeps that check alive.
    rec["configuration"], rec["configuration_detail"] = parse_configuration(tree)
    rec["reports"] = report_manifest(tree, logpath)
    print(f"quartus_gate: configuration {rec['configuration']}", flush=True)

    bars, figs = score(tree, log_text, a)
    # E7 -- THE INPUT-HASH ORDERING BAR.  `mf` above was taken BEFORE the
    # compile, which is the only order that can name what the compiler was
    # handed; this re-reads the same closed list AFTER the last stage.  Only on
    # a path that actually built: with `--parse-only` there is no interval to
    # bracket, and a bar that passes vacuously is worse than an absent one.
    if not a.parse_only:
        rec["inputs_post"] = input_manifest()
        bars["E7_input_stability"] = input_stability_bar(mf, rec["inputs_post"])
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
