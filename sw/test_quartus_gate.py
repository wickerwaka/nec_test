#!/usr/bin/env python3
"""test_quartus_gate -- THE `--retention` FLAG'S OWN FALSIFIER.  NO QUARTUS.

WHY IT EXISTS.  `docs/notes/fz2_flash18_results_2026-08-11.md` §1.2: the first
FLASH #18 retention attempt was

    X1_AD_RETENTION=1 python3 sw/quartus_gate.py

and it was **ACCEPTED AND IGNORED**.  `build()` ran `quartus_sh --flow compile`
with no `--verilog_macro` and never read the environment, so the run produced a
CONTROL build -- Fmax, worst setup, ALM count and `.rbf` all byte-identical to
the control taken minutes earlier -- under a receipt whose *label* said
RETENTION.  Only the receipt's **derived** `configuration` disagreed, and that
disagreement is the only reason the build was not flashed.

That is CLAUDE.md's `want_raw` trap in its second incarnation: *"verify a flag
exists AND that the callee accepts it"*.  The fix is `--retention` plus a
REFUSAL on the environment form, and **a fix with no falsifier is how the trap
comes back**.  So:

  Q1  --retention produces EXACTLY the recorded four-stage recipe, in order,
      with the macro on `quartus_map` and nowhere else.
  Q2  the DEFAULT path is UNCHANGED, byte for byte -- a fix that quietly
      alters the CONTROL build would invalidate every G6 figure on the branch.
  Q3  the env var WITHOUT --retention exits 2 and the message names the
      variable, the flag and the finding.  THE TRAP, AS A UNIT TEST.
  Q4  the env var WITH --retention does NOT refuse (the macro travels on the
      command line, so the variable is harmless there).
  Q5  with the variable unset, the default path does not refuse -- a refusal
      that fires on every run is a different kind of broken.
  Q6  --retention --parse-only is REFUSED: it would gate whatever reports are
      on disk while claiming a configuration it never compiled.
  Q7  the receipt's `configuration` is still DERIVED FROM THE REPORTS and is
      NOT an echo of the flag, demonstrated on a synthetic report tree --
      including the case that matters, a CONTROL report set, which must read
      CONTROL no matter what the flag said.
  Q8  (asked on EVERY subprocess, not as its own section) the append-only
      receipt history does not grow by a single byte.  See `_DISARM`.

WHY NO COMPILE.  The RECIPE is already proved: FLASH #18's retention receipt
`277d5ccf0f8b9398…` self-labels `RETENTION (X1_AD_RETENTION=1)` with an `.rbf`
differing from the control's, and it is the bitstream on the board.  Twelve
archived retention receipts record the same command line.  A ten-minute
compile would re-prove Quartus.  **What was unproved is this tool's plumbing**,
and that is what is tested here.

    python3 sw/test_quartus_gate.py        # exit 0 = the flag does what it says
    python3 sw/test_quartus_gate.py -v     # show every assertion

EXIT 0 = all checks pass, 1 = a check failed.
"""
import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))
import quartus_gate as qg                                    # noqa: E402

VERBOSE = False
FAILS = []
NCHECK = 0


def check(what, ok, detail=""):
    global NCHECK
    NCHECK += 1
    if not ok:
        FAILS.append(f"{what}   {detail}")
    if VERBOSE or not ok:
        print(f"  [{'ok ' if ok else 'FAIL'}] {what}"
              + (f"   {detail}" if detail and (VERBOSE or not ok) else ""))


# ⚠ THE TOOLCHAIN IS DISARMED IN EVERY SUBPROCESS THIS FILE STARTS, AND THAT
# IS A SAFETY PROPERTY, NOT A CONVENIENCE.  Every invocation below is *meant*
# to stop at a refusal or a `--dry-run` before `build()` -- but a test whose
# safety depends on the very code it is trying to falsify is not safe.  If the
# refusal is ever broken, an undisarmed `run_gate([], {X1_AD_RETENTION: "1"})`
# would `shutil.rmtree` hdl/db, hdl/incremental_db and hdl/output_files_ucore
# and then start a ten-minute compile -- **measured, on this tree, while this
# file was being written**.  So `QUARTUS_BIN` is pointed at a path that cannot
# exist: `build()` checks every stage binary BEFORE it deletes anything, so the
# worst case becomes exit 2 with nothing touched.
#
# The cost is that exit 2 stops discriminating on its own -- a missing tool and
# a refusal both give 2 -- so every refusal check below ALSO requires the
# refusal's own words and requires the missing-tool message to be ABSENT.
#
# `artifact.RECEIPT_DIR` IS REDIRECTED FOR THE SAME REASON, and it is the same
# lesson learned twice in one afternoon: on a null run the gate went RED at E1
# and `_finish()` APPENDED TEN JUNK ENTRIES to the repo's real
# `sw/testdata/receipts/quartus_bitstream.jsonl` -- the append-only history
# every G6 figure on this branch is quoted from.  A test must not be able to
# write there under ANY perturbation, so it is pointed at a temp dir it owns.
_DISARM = ("import sys, pathlib, tempfile; sys.path.insert(0, {sw!r});\n"
           "import artifact as art, quartus_gate as qg\n"
           "qg.QUARTUS_BIN = pathlib.Path('/nonexistent-quartus/bin')\n"
           "art.RECEIPT_DIR = pathlib.Path(tempfile.mkdtemp(prefix='qgtest-rcpt-'))\n"
           "sys.argv = ['quartus_gate.py'] + {args!r}\n"
           "sys.exit(qg.main())\n")
NO_TOOL = "not found -- the gate CANNOT RUN"
HISTORY = ROOT / "sw" / "testdata" / "receipts" / "quartus_bitstream.jsonl"


def run_gate(args, env_extra=None):
    """-> (rc, combined output), with the toolchain and the receipt history
    both disarmed.  See above."""
    env = dict(os.environ)
    env.pop(qg.RETENTION_MACRO, None)
    env.update(env_extra or {})
    before = HISTORY.stat().st_size if HISTORY.exists() else None
    r = subprocess.run([sys.executable, "-c",
                        _DISARM.format(sw=str(SW), args=list(args))],
                       capture_output=True, text=True, env=env, timeout=120)
    after = HISTORY.stat().st_size if HISTORY.exists() else None
    check(f"the receipt history is untouched by `{' '.join(args) or '(default)'}`",
          before == after, f"{before} -> {after}")
    return r.returncode, r.stdout + r.stderr


def check_refused(tag, rc, out):
    """A REFUSAL, distinguished from the disarmed toolchain's own exit 2."""
    check(f"{tag}: exits 2", rc == 2, f"rc={rc}")
    check(f"{tag}: says REFUSING", "REFUS" in out.upper())
    check(f"{tag}: is a REFUSAL, not the missing toolchain", NO_TOOL not in out)
    check(f"{tag}: built nothing", "compile rc=" not in out)


# --------------------------------------------------------------------------- #
def q1_retention_commands():
    print("\nQ1  --retention builds the RECORDED four-stage recipe")
    cmds = qg.build_commands(retention=True)
    check("four stages", len(cmds) == 4, f"got {len(cmds)}")
    names = [Path(c[0]).name for c in cmds]
    check("stages in order: map, fit, asm, sta",
          names == ["quartus_map", "quartus_fit", "quartus_asm", "quartus_sta"],
          str(names))
    macro = f"--verilog_macro={qg.RETENTION_MACRO}=1"
    check("the macro is on quartus_map", macro in cmds[0], str(cmds[0]))
    # UNQUOTED, because this runs without a shell.  Checked against the
    # artifact: all twelve archived retention receipts record
    # `--verilog_macro=X1_AD_RETENTION=1` as what Quartus received.
    check("the macro is UNQUOTED (no shell in the loop)",
          all('"' not in tok for tok in cmds[0]), str(cmds[0]))
    check("the macro is on NO other stage",
          not any(any("verilog_macro" in t for t in c) for c in cmds[1:]))
    for c in cmds:
        check(f"{Path(c[0]).name} names the project and revision",
              c[-3:] == [qg.PROJECT, "-c", qg.REVISION], str(c))
    # ...and the dry run prints exactly that.
    rc, out = run_gate(["--dry-run", "--retention"])
    check("--dry-run --retention exits 0", rc == 0, out.strip()[-200:])
    check("--dry-run prints the macro", macro in out)
    check("--dry-run says RETENTION", "RETENTION" in out)
    check("--dry-run builds nothing",
          "stage(s)" in out and "compile rc=" not in out)


def q2_control_unchanged():
    print("\nQ2  the DEFAULT (CONTROL) command list is UNCHANGED")
    cmds = qg.build_commands()
    expected = [[str(qg.QUARTUS_BIN / "quartus_sh"), "--flow", "compile",
                 qg.PROJECT, "-c", qg.REVISION]]
    check("exactly one stage, and it is the historical one",
          cmds == expected, f"{cmds} != {expected}")
    check("no verilog_macro anywhere on the control path",
          not any("verilog_macro" in t for c in cmds for t in c))
    check("build_commands(False) == build_commands()",
          qg.build_commands(False) == cmds)
    rc, out = run_gate(["--dry-run"])
    check("--dry-run exits 0", rc == 0)
    check("--dry-run says CONTROL/DEFAULT", "CONTROL/DEFAULT" in out, out[:200])
    check("--dry-run shows no macro", "verilog_macro" not in out)


def q3_env_refused():
    print("\nQ3  the env var WITHOUT --retention is REFUSED  (THE TRAP)")
    for val in ("1", "0", "yes"):
        tag = f"{qg.RETENTION_MACRO}={val}"
        rc, out = run_gate([], {qg.RETENTION_MACRO: val})
        check_refused(tag, rc, out)
        check(f"{tag} names the variable", qg.RETENTION_MACRO in out)
        check(f"{tag} names the flag", "--retention" in out)
        check(f"{tag} names the finding",
              "FLASH #18" in out or "flash18" in out)
        check(f"{tag} did not even reach E1",
              "quartus_gate: E1" not in out)
    # An EMPTY value is not "set" -- it names no configuration and must not
    # block a control build.
    rc, out = run_gate(["--dry-run"], {qg.RETENTION_MACRO: ""})
    check("an EMPTY value does not refuse", rc == 0, f"rc={rc}")
    # ...and the refusal must beat --parse-only too, which touches no compiler
    # and would otherwise look like a safe way to ignore the variable.
    rc, out = run_gate(["--parse-only"], {qg.RETENTION_MACRO: "1"})
    check_refused("with --parse-only", rc, out)


def q4_env_with_flag_ok():
    print("\nQ4  the env var WITH --retention does NOT refuse")
    rc, out = run_gate(["--dry-run", "--retention"], {qg.RETENTION_MACRO: "1"})
    check("exits 0", rc == 0, out.strip()[-200:])
    check("does not refuse", "REFUS" not in out.upper())
    check("still prints the four stages", out.count("quartus_") >= 4)


def q5_unset_ok():
    print("\nQ5  with the variable unset, the default path does not refuse")
    rc, out = run_gate(["--dry-run"])
    check("exits 0", rc == 0)
    check("does not refuse", "REFUS" not in out.upper())


def q6_retention_parse_only_refused():
    print("\nQ6  --retention --parse-only is REFUSED")
    rc, out = run_gate(["--retention", "--parse-only"])
    check_refused("--retention --parse-only", rc, out)
    check("explains why", "parse-only" in out and "BUILD" in out.upper())


def q7_configuration_still_derived():
    print("\nQ7  `configuration` is DERIVED FROM THE REPORTS, never from the flag")
    with tempfile.TemporaryDirectory(prefix="qgtest-") as d:
        tree = Path(d)
        flow = tree / f"{qg.REVISION}.flow.rpt"
        mapr = tree / f"{qg.REVISION}.map.rpt"

        # (a) a CONTROL report set -- both sources present, no macro anywhere.
        flow.write_text("; Some Setting ; value ;\n")
        mapr.write_text("Info: Command: quartus_map nec_test -c nec_test_ucore\n")
        cfg, det = qg.parse_configuration(tree)
        check("a control report set derives CONTROL/DEFAULT",
              cfg.startswith("CONTROL/DEFAULT"), cfg)
        check("...and says so via `retention` False", det["retention"] is False)

        # (b) THE ONE THAT MATTERS.  A control report set is still CONTROL no
        #     matter what any flag said -- `parse_configuration` takes no
        #     argument that could carry the flag, which is the structural
        #     guarantee, and this is its unit test.
        check("parse_configuration takes only the tree",
              qg.parse_configuration.__code__.co_argcount == 1,
              str(qg.parse_configuration.__code__.co_varnames[:2]))

        # (c) a RETENTION report set -- the macro on the map command line, the
        #     way `--retention` puts it there.
        mapr.write_text("Info: Command: quartus_map "
                        f"--verilog_macro={qg.RETENTION_MACRO}=1 "
                        "nec_test -c nec_test_ucore\n")
        cfg, det = qg.parse_configuration(tree)
        check("a retention report set derives RETENTION",
              cfg.startswith("RETENTION"), cfg)
        check("...and names the macro", qg.RETENTION_MACRO in cfg, cfg)
        check("...and says so via `retention` True", det["retention"] is True)

        # (d) a MISSING source is UNDETERMINED, not CONTROL.  Absence must
        #     never read as data -- the rule the derived label was built on.
        mapr.unlink()
        cfg, _ = qg.parse_configuration(tree)
        check("a missing map.rpt is UNDETERMINED, not CONTROL",
              cfg.startswith("UNDETERMINED"), cfg)


def main():
    global VERBOSE
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("-v", "--verbose", action="store_true")
    VERBOSE = ap.parse_args().verbose

    print("== test_quartus_gate: the --retention flag's falsifier "
          "(no Quartus binary required)")
    q1_retention_commands()
    q2_control_unchanged()
    q3_env_refused()
    q4_env_with_flag_ok()
    q5_unset_ok()
    q6_retention_parse_only_refused()
    q7_configuration_still_derived()

    print(f"\n{NCHECK - len(FAILS)} / {NCHECK} checks pass")
    for f in FAILS:
        print(f"  FAIL  {f}")
    print(f"=== test_quartus_gate: {'PASS' if not FAILS else 'FAIL'}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
