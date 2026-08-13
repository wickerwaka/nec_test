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
  Q16 THE PAIRED FIGURE (adopted 2026-08-13).  G6's registered output is a
      PAIR -- whole-design worst-of-N (the promotion gate, unchanged) beside
      core-domain worst-of-N (what an integration inherits) -- so the falsifier
      has to hold BOTH halves: that core-domain is the min over exactly the
      three core-INTERNAL SDC classes and not over `k=0.5` (whose launch side
      is outside the core) or `DEFAULT` (which is the whole design); that a
      missing class yields NO figure rather than a min over the survivors; and
      **that no BAR reads the core-domain number** -- a pairing whose second
      half quietly became the gate would re-scope the promotion onto the very
      figure that excludes both binding cones.

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
    print("\nQ1  --retention builds the RECORDED four-stage recipe, "
          "PRECEDED by the PRE_FLOW hook")
    cmds = qg.build_commands(retention=True)
    # ⚠ THE RECIPE GAINED A STAGE ON 2026-08-13, AND THE FOUR RECORDED ONES ARE
    # UNCHANGED.  `hdl/sys/sys.tcl:211` sets PRE_FLOW_SCRIPT_FILE, which
    # `quartus_sh --flow compile` honours and a direct `quartus_map` does not --
    # so on a tree with no leftover `hdl/build_id.v` the recorded four-step
    # recipe CANNOT BUILD (measured: A&S Error 10054, exit 3 in 11 s).  Every
    # retention build ever taken found a `build_id.v` left behind by an earlier
    # CONTROL `--flow compile`.  The hook now runs explicitly.
    check("five stages: the PRE_FLOW hook + the recorded four",
          len(cmds) == 5, f"got {len(cmds)}")
    names = [Path(c[0]).name for c in cmds]
    check("the PRE_FLOW hook runs FIRST",
          names[0] == "quartus_sh" and "sys/build_id.tcl" in cmds[0],
          str(cmds[0]))
    check("the RECORDED four are unchanged and in order: map, fit, asm, sta",
          names[1:] == ["quartus_map", "quartus_fit", "quartus_asm",
                        "quartus_sta"], str(names))
    check("the PRE_FLOW hook is the project's own script, not a reimplementation",
          (ROOT / "hdl" / "sys" / "build_id.tcl").is_file()
          and "sys/build_id.tcl" in " ".join(cmds[0]))
    macro = f"--verilog_macro={qg.RETENTION_MACRO}=1"
    check("the macro is on quartus_map", macro in cmds[1], str(cmds[1]))
    # UNQUOTED, because this runs without a shell.  Checked against the
    # artifact: all twelve archived retention receipts record
    # `--verilog_macro=X1_AD_RETENTION=1` as what Quartus received.
    check("the macro is UNQUOTED (no shell in the loop)",
          all('"' not in tok for tok in cmds[1]), str(cmds[1]))
    check("the macro is on NO other stage",
          not any(any("verilog_macro" in t for t in c)
                  for c in cmds[:1] + cmds[2:]))
    for c in cmds[1:]:
        check(f"{Path(c[0]).name} names the project and revision",
              c[-3:] == [qg.PROJECT, "-c", qg.REVISION], str(c))
    check("the PRE_FLOW hook names the project and revision too",
          cmds[0][-2:] == [qg.PROJECT, qg.REVISION], str(cmds[0]))
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


# =========================================================================== #
# THE DISTRIBUTION GATE (`--seeds N`) -- Q9-Q15.
#
# Same charter as Q1-Q7 and the same reason: the sweep's whole claim is that
# its N numbers are N DIFFERENT FITS OF ONE MAPPED NETLIST.  Every way that
# claim can be false while the tool still prints a tidy table is a check here.
# =========================================================================== #
def q9_sweep_commands():
    print("\nQ9  --seeds builds ONE map and N fits, and the seed is ON THE FIT")
    mp = qg.map_command()
    check("the shared map is quartus_map",
          Path(mp[0]).name == "quartus_map", str(mp))
    check("the CONTROL map carries no macro", "verilog_macro" not in " ".join(mp))
    mpr = qg.map_command(retention=True)
    check("the RETENTION map carries the macro",
          f"--verilog_macro={qg.RETENTION_MACRO}=1" in mpr, str(mpr))
    check("...unquoted (no shell in the loop)",
          all('"' not in t for t in mpr), str(mpr))

    cmds = qg.seed_commands(7)
    names = [Path(c[0]).name for c in cmds]
    check("per-seed stages are fit, asm, sta",
          names == ["quartus_fit", "quartus_asm", "quartus_sta"], str(names))
    check("the seed is on quartus_fit", "--seed=7" in cmds[0], str(cmds[0]))
    # PINNED, not defaulted: the project carries SMART_RECOMPILE ON, and a fit
    # that started from the previous fit's placement would make the measured
    # spread an artefact of seed ORDER.
    check("--recompile=off is PINNED on the fit",
          "--recompile=off" in cmds[0], str(cmds[0]))
    check("the seed is on NO other stage",
          not any(any("--seed=" in t for t in c) for c in cmds[1:]))
    # ⚠ THE ONE THAT WOULD SILENTLY RUIN THE SWEEP.  A macro on a per-seed
    # stage would mean each draw re-elaborated -- N trees, not N fits of one.
    check("NO stage re-maps, on either configuration",
          not any(Path(c[0]).name == "quartus_map"
                  for s in (qg.seed_commands(1), qg.seed_commands(1, asm=False))
                  for c in s))
    check("no verilog_macro on any per-seed stage",
          not any("verilog_macro" in t for c in cmds for t in c))
    check("--no-asm drops exactly quartus_asm",
          [Path(c[0]).name for c in qg.seed_commands(7, asm=False)]
          == ["quartus_fit", "quartus_sta"])
    for c in cmds:
        check(f"{Path(c[0]).name} names the project and revision",
              c[-3:] == [qg.PROJECT, "-c", qg.REVISION], str(c))
    # ...and the DEFAULT single-build path is still untouched by all of this.
    check("build_commands() is still the historical one-stage compile",
          qg.build_commands() == [[str(qg.QUARTUS_BIN / "quartus_sh"),
                                   "--flow", "compile", qg.PROJECT, "-c",
                                   qg.REVISION]])

    rc, out = run_gate(["--dry-run", "--seeds", "8"])
    check("--dry-run --seeds 8 exits 0", rc == 0, out.strip()[-200:])
    cmdlines = [ln for ln in out.splitlines() if "/bin/quartus_" in ln]
    check("...prints the map ONCE",
          sum(1 for ln in cmdlines if "bin/quartus_map" in ln) == 1,
          "\n".join(cmdlines))
    check("...and the PRE_FLOW hook ONCE, before it",
          [i for i, ln in enumerate(cmdlines) if "sys/build_id.tcl" in ln]
          == [0], "\n".join(cmdlines))
    check("...says worst-of-8", "worst-of-8@seeds{1,2,3,4,5,6,7,8}" in out, out)
    check("...builds nothing", "compile rc=" not in out and "[map]" not in out)
    rc, out2 = run_gate(["--dry-run", "--seeds", "2"])
    check("--dry-run --seeds 2 prints the N<5 caveat",
          "NOT promotion evidence" in out2, out2)
    check("--dry-run --seeds 8 does NOT print it",
          "NOT promotion evidence" not in out)


def q10_seed_spec():
    print("\nQ10 --seeds parses to a NAMED seed set (so a sweep is reproducible)")
    check("`8` means 1..8", qg.parse_seed_spec("8") == list(range(1, 9)))
    check("`1` means [1]", qg.parse_seed_spec("1") == [1])
    check("a list is taken literally",
          qg.parse_seed_spec("1,7,99") == [1, 7, 99])
    check("a list is de-duplicated and sorted",
          qg.parse_seed_spec("9,3,3,1") == [1, 3, 9])
    for bad in ("0", "-3", "", "   ", "abc"):
        try:
            qg.parse_seed_spec(bad)
            check(f"--seeds {bad!r} is refused", False, "it was accepted")
        except ValueError:
            check(f"--seeds {bad!r} is refused", True)
        except Exception as e:                               # noqa: BLE001
            check(f"--seeds {bad!r} is refused with ValueError", False, repr(e))


def q11_e7_input_ordering():
    print("\nQ11 E7: the inputs are re-hashed AFTER the build and must match")
    pre = {"sha256": "aaa", "files": {"hdl/a.sv": "1", "hdl/b.sv": "2"}}
    same = {"sha256": "aaa", "files": dict(pre["files"])}
    b = qg.input_stability_bar(pre, same)
    check("identical manifests PASS", b["pass"] is True, str(b["value"]))
    check("...and report 0 moved", b["value"]["n_moved"] == 0)

    # --- THE ONE DECLARED EXEMPTION, AND ITS LIMITS ------------------------ #
    # Quartus REWRITES the revision .qsf it compiles (§70.7), so that file
    # moves on EVERY build.  Treating it as a flip would fire E7 on every green
    # run, and a bar that always fails is a bar nobody reads.
    check("the exemption list is exactly the revision .qsf",
          qg.INPUT_FLIP_EXEMPT == ("hdl/nec_test_ucore.qsf",),
          str(qg.INPUT_FLIP_EXEMPT))
    base = {"sha256": "aaa", "files": {"hdl/nec_test_ucore.qsf": "1",
                                       "hdl/nec_test.qsf": "1",
                                       "hdl/rtl/ucore/v30u_eu.sv": "1"}}
    qsf = {"sha256": "zzz", "files": dict(base["files"],
                                          **{"hdl/nec_test_ucore.qsf": "REWRITTEN"})}
    b = qg.input_stability_bar(base, qsf)
    check("the revision .qsf moving alone is a PASS", b["pass"] is True,
          str(b["value"]))
    check("...and it is REPORTED as moved-but-exempt, not hidden",
          b["value"]["moved_exempt"] == ["hdl/nec_test_ucore.qsf"]
          and b["value"]["n_moved"] == 1, str(b["value"]))
    # ⚠ THE EXEMPTION IS ONE NAME, NOT A PATTERN.  The hand-maintained
    # nec_test.qsf is NOT exempt, and neither is any RTL file.
    other = {"sha256": "yyy", "files": dict(base["files"],
                                            **{"hdl/nec_test.qsf": "MOVED"})}
    b = qg.input_stability_bar(base, other)
    check("the OTHER .qsf moving is still a RED", b["pass"] is False)
    check("...and is listed as OFFENDING",
          b["value"]["moved_offending"] == ["hdl/nec_test.qsf"], str(b["value"]))
    both = {"sha256": "xxx", "files": {"hdl/nec_test_ucore.qsf": "REWRITTEN",
                                       "hdl/nec_test.qsf": "1",
                                       "hdl/rtl/ucore/v30u_eu.sv": "MOVED"}}
    b = qg.input_stability_bar(base, both)
    check("an RTL flip ALONGSIDE the exempt rewrite is still a RED",
          b["pass"] is False, str(b["value"]))
    check("...and the two are separated, not merged",
          b["value"]["moved_exempt"] == ["hdl/nec_test_ucore.qsf"]
          and b["value"]["moved_offending"] == ["hdl/rtl/ucore/v30u_eu.sv"],
          str(b["value"]))

    # THE MID-BUILD RTL FLIP, AS A UNIT TEST.
    moved = {"sha256": "bbb", "files": {"hdl/a.sv": "1", "hdl/b.sv": "CHANGED"}}
    b = qg.input_stability_bar(pre, moved)
    check("a file that moved mid-build is a RED", b["pass"] is False)
    check("...and the RED NAMES the file",
          "hdl/b.sv" in b["value"]["moved"], str(b["value"]["moved"]))
    check("...and carries both hashes",
          b["value"]["pre_sha256"] == "aaa" and b["value"]["post_sha256"] == "bbb")
    # An input that APPEARED or VANISHED is a move too -- absence is a value.
    gone = {"sha256": "ccc", "files": {"hdl/a.sv": "1"}}
    check("a vanished input is a RED", qg.input_stability_bar(pre, gone)["pass"]
          is False)
    added = {"sha256": "ddd", "files": dict(pre["files"], **{"hdl/c.sv": "3"})}
    b = qg.input_stability_bar(pre, added)
    check("a NEW input is a RED", b["pass"] is False)
    check("...and names it", "hdl/c.sv" in b["value"]["moved"])
    # ORDER, not just presence: `mf` must be taken before the compile.  The
    # structural guarantee is that `input_manifest()` is called before `build()`
    # in main(); this reads the source so a reordering edit trips the test.
    src = (SW / "quartus_gate.py").read_text()
    i_pre = src.index("mf = input_manifest()")
    i_build = src.index("b, rc = build(tree, a.keep_db")
    i_post = src.index('rec["inputs_post"] = input_manifest()')
    check("main() hashes inputs BEFORE build() and again AFTER",
          i_pre < i_build < i_post, f"{i_pre} {i_build} {i_post}")
    # ...and NOT on --parse-only, where there is no interval to bracket and the
    # bar would pass vacuously.  A vacuous bar is worse than an absent one.
    check("E7 is guarded by `not a.parse_only`",
          "if not a.parse_only:" in src[i_build:i_post + 200], "guard missing")


def q12_e8_seed_honoured():
    print("\nQ12 E8: the fitter HONOURED the seed  (the accepted-and-ignored trap)")
    check("both readings agree -> PASS",
          qg.seed_honoured_bar(5, {"command_line": 5, "settings": 5})["pass"])
    # ⚠ THE STRONG READING IS THE FITTER SETTINGS ROW -- the seed Quartus USED.
    # The `Info: Command:` echo says only what the binary was HANDED, so it
    # cannot carry the bar on its own.
    check("the command echo ALONE is NOT enough",
          qg.seed_honoured_bar(5, {"command_line": 5, "settings": None})["pass"]
          is False)
    check("the settings row alone IS enough",
          qg.seed_honoured_bar(5, {"command_line": None, "settings": 5})["pass"])
    check("a DISAGREEING settings echo -> RED",
          qg.seed_honoured_bar(5, {"command_line": 5, "settings": 1})["pass"]
          is False)
    check("a DISAGREEING command line -> RED",
          qg.seed_honoured_bar(5, {"command_line": 1, "settings": 5})["pass"]
          is False)
    # ⚠ NO ECHO AT ALL IS A RED, NOT A PASS.  If it passed, a Quartus that
    # silently dropped --seed would give 8 identical fits, a spread of 0.00 MHz
    # and a green gate -- the reassuring-result failure mode.
    check("NO echo at all -> RED (absence is not agreement)",
          qg.seed_honoured_bar(5, {"command_line": None, "settings": None})
          ["pass"] is False)

    with tempfile.TemporaryDirectory(prefix="qgtest-") as d:
        tree = Path(d)
        rpt = tree / f"{qg.REVISION}.fit.rpt"
        check("no fit.rpt and no log -> nothing claimed",
              qg.parse_fit_seed(tree) == {"command_line": None,
                                          "settings": None,
                                          "settings_row": None})
        # ⚠ THE REAL FORMATS, AND THEY ARE NOT THE OBVIOUS ONES.  Measured on
        # this tree's own reports: the row is `Fitter Initial Placement Seed`
        # (NOT `Seed`), and `fit.rpt` contains NO `Info: Command:` line at all
        # -- that echo goes to stdout, i.e. into the gate's transcript.  A
        # first cut of the parser assumed both and E8 went RED on a fit that
        # had honoured the seed exactly.
        rpt.write_text(
            "; Fitter Aggressive Routability Optimizations ; Automatically ; "
            "Automatically ;\n"
            "; Fitter Initial Placement Seed               ; 42            ; "
            "42            ;\n"
            "; Weak Pull-Up Resistor                       ; Off           ; "
            "Off           ;\n")
        log = ("Info: Command: quartus_fit --seed=42 --recompile=off nec_test "
               "-c nec_test_ucore\n")
        seen = qg.parse_fit_seed(tree, log)
        check("both readings are recovered from the REAL formats",
              seen["settings"] == 42 and seen["command_line"] == 42, str(seen))
        check("...and the matched row is retained for audit",
              "Fitter Initial Placement Seed" in (seen["settings_row"] or ""),
              str(seen["settings_row"]))
        check("...and E8 PASSES", qg.seed_honoured_bar(42, seen)["pass"])
        check("the OLD `; Seed ;` guess finds nothing (regression guard)",
              qg.parse_fit_seed(tree, "")["command_line"] is None)
        # The sweep appends every stage to ONE log, so the LAST echo is this
        # seed's -- an earlier seed's must not be read as the current one.
        multi = log + ("Info: Command: quartus_fit --seed=43 nec_test\n")
        check("the LAST fit echo in a shared log wins",
              qg.parse_fit_seed(tree, multi)["command_line"] == 43)
        # THE CASE THAT MATTERS: asked 42, Quartus placed with 1.
        rpt.write_text("; Fitter Initial Placement Seed ; 1 ; 1 ;\n")
        seen = qg.parse_fit_seed(tree, log)
        check("a fitter that IGNORED the seed is visible",
              seen["settings"] == 1 and seen["command_line"] == 42, str(seen))
        check("...and E8 goes RED on it",
              qg.seed_honoured_bar(42, seen)["pass"] is False)

    # AND THE GROUND TRUTH: if a real fit.rpt is on disk, the parser must read
    # it.  Skipped when there is none, never silently passed.
    live = ROOT / "hdl" / "output_files_ucore" / f"{qg.REVISION}.fit.rpt"
    if live.is_file():
        seen = qg.parse_fit_seed(live.parent, "")
        check("the parser reads a REAL Quartus fit.rpt",
              isinstance(seen["settings"], int), str(seen))
    else:
        print("  [skip] no live fit.rpt on disk to check the parser against")


def q13_sweep_refusals():
    print("\nQ13 the sweep's REFUSALS (sweep-only flags cannot be ignored)")
    rc, out = run_gate(["--seeds", "4", "--parse-only"])
    check_refused("--seeds --parse-only", rc, out)
    check("explains the 0.00 MHz failure mode",
          "0.00 MHz" in out or "DISTRIBUTION" in out, out[:300])
    # THE ACCEPTED-AND-IGNORED TRAP, CLOSED IN ADVANCE FOR THE NEW FLAGS.
    for flag in (["--no-asm"], ["--no-truefmax"], ["--artifact-dir", "/tmp/x"]):
        rc, out = run_gate(flag)
        check_refused(f"{flag[0]} without --seeds", rc, out)
        check(f"{flag[0]}: names the trap",
              "ACCEPTED AND IGNORED" in out.upper(), out[:300])
    # ...and WITH --seeds they are accepted.
    rc, out = run_gate(["--dry-run", "--seeds", "3", "--no-asm"])
    check("--no-asm WITH --seeds is accepted", rc == 0, out.strip()[-200:])
    check("...and quartus_asm is gone", "quartus_asm" not in out, out)
    for bad in ("0", "abc"):
        rc, out = run_gate(["--seeds", bad])
        check(f"--seeds {bad} is refused", rc == 2, f"rc={rc}")
        check(f"--seeds {bad} says REFUSING", "REFUS" in out.upper())


def q14_truefmax_parse():
    print("\nQ14 the per-k-class ceilings are parsed off the probe's own artifact")
    art_txt = ROOT / "docs" / "notes" / "t1half2" / "ctl_baseline.truefmax.txt"
    if not art_txt.exists():
        check("the committed truefmax artifact exists", False, str(art_txt))
        return
    tf = qg.parse_truefmax(art_txt)
    check("the five exception classes are all present",
          sum(1 for k in tf if k.startswith(("DEFAULT", "k="))) == 5,
          str(sorted(tf)))
    d = tf["DEFAULT (whole-design worst, expect k=1)"]
    check("DEFAULT is 42.09 MHz at k=1", d["fmax_mhz"] == 42.09 and d["k"] == 1.0,
          str(d))
    check("...and its endpoints are recovered",
          "upc_opc[6]" in (d["from"] or "") and "ad_in_q[16]" in (d["to"] or ""),
          str(d))
    e = tf["k=0.5  (not $v30u_ce) -> t1_half2   -- the ENABLE arc"]
    check("the k=0.5 ENABLE arc is 90.91 MHz at k=0.5",
          e["fmax_mhz"] == 90.91 and e["k"] == 0.5, str(e))
    check("...which is the wave's whole finding: it does NOT bind",
          e["fmax_mhz"] > d["fmax_mhz"])
    check("a missing artifact parses to {}, not a crash",
          qg.parse_truefmax(ROOT / "no" / "such" / "file.txt") == {})

    # ⚠ THE EXIT CODE IS NOT THE MEASUREMENT.  `quartus_sta` running the probe
    # has been observed to write ALL five classes and then crash in Tcl
    # teardown with rc=2 (2 of 16 draws in the first N=8 baseline).  The gate
    # judges the ARTIFACT.
    check("a whole artifact is COMPLETE", qg.truefmax_complete(tf))
    check("{} is not complete", qg.truefmax_complete({}) is False)
    for drop in ("k=0.5", "DEFAULT", "k=2.5"):
        part = {k: v for k, v in tf.items() if not k.startswith(drop)}
        check(f"an artifact missing the {drop} class is INCOMPLETE",
              qg.truefmax_complete(part) is False)
    # A class that is PRESENT but carries no ceiling is incomplete too --
    # a header with no number is absence wearing a label.
    hollow = {k: (dict(v, fmax_mhz=None) if k.startswith("k=0.5") else v)
              for k, v in tf.items()}
    check("a class present but with NO ceiling is INCOMPLETE",
          qg.truefmax_complete(hollow) is False)
    src = (SW / "quartus_gate.py").read_text()
    check("the sweep accepts a truefmax artifact on COMPLETENESS, not on rc",
          "truefmax_complete(parse_truefmax(cand))" in src)
    check("...and records the rc either way",
          '"salvaged_despite_rc": tf_salvaged' in src)


def q15_summary_stats():
    print("\nQ15 the distribution summary, and WHICH number is the quotable one")
    s = qg._stat([42.09, 39.79, 40.5, 41.0])
    check("min/max are draws that happened",
          s["min"] == 39.79 and s["max"] == 42.09, str(s))
    check("spread is max-min", s["spread"] == round(42.09 - 39.79, 4), str(s))
    check("the median of an even N is the mean of the middle two",
          s["median"] == (40.5 + 41.0) / 2.0, str(s))
    check("the draws themselves are carried, not just the summary",
          s["sorted"] == [39.79, 40.5, 41.0, 42.09])
    check("an odd N takes the middle draw",
          qg._stat([3.0, 1.0, 2.0])["median"] == 2.0)
    check("no draws -> None, not 0", qg._stat([])["min"] is None)
    check("None draws are dropped, not counted as 0",
          qg._stat([5.0, None])["n"] == 1)
    # THE QUOTING RULE ITSELF: the WORST draw is the one that may be quoted.
    src = (SW / "quartus_gate.py").read_text()
    check("`worst_of_n` is the MIN over the draws, not the mean or the max",
          "worst = min(ok_fm)" in src)
    check("N >= 5 is required for a PROMOTION grade",
          '"promotion_grade": n >= 5' in src)
    check("the sweep's verdict does not depend on the BEST draw",
          "max(ok_fm)" not in src)


def q16_paired_reporting():
    print("\nQ16 THE PAIRED FIGURE: whole-design AND core-domain, from ONE run")
    art_txt = ROOT / "docs" / "notes" / "t1half2" / "ctl_baseline.truefmax.txt"
    if not art_txt.exists():
        check("the committed truefmax artifact exists", False, str(art_txt))
        return
    tf = qg.parse_truefmax(art_txt)

    # --- the definition itself, because it is the load-bearing choice ------- #
    check("the core-domain class list is exactly the three core-INTERNAL SDC "
          "classes", qg.CORE_DOMAIN_CLASSES == ("k=4.0", "k=1.5", "k=2.5"),
          str(qg.CORE_DOMAIN_CLASSES))
    check("...and it EXCLUDES DEFAULT (which is the whole design)",
          "DEFAULT" not in qg.CORE_DOMAIN_CLASSES)
    # ⚠ THE ONE THAT WOULD MAKE THE FIGURE A LIE.  `k=0.5` is
    # `(not $v30u_ce) -> t1_half2`: its LAUNCH side is outside the core by
    # construction, so counting it would put a rig register inside a figure
    # whose whole claim is that both endpoints are the core's.
    check("...and it EXCLUDES k=0.5, whose launch side is outside the core",
          "k=0.5" not in qg.CORE_DOMAIN_CLASSES)

    cd = qg.core_domain_fmax(tf)
    check("the core-domain figure is the MINIMUM over the three",
          cd["fmax_mhz"] == 59.51, str(cd))
    check("...which on this artifact is the k=4.0 CE multicycle",
          cd["class"] == "k=4.0" and cd["k"] == 4.0, str(cd))
    check("...quoted WITH its binding cone, both endpoints named",
          bool(cd["from"]) and bool(cd["to"]), str(cd))
    check("...and it carries all three classes, not just the winner",
          sorted(cd["classes"]) == ["k=1.5", "k=2.5", "k=4.0"],
          str(cd["classes"]))
    d = tf["DEFAULT (whole-design worst, expect k=1)"]
    check("the two halves are DIFFERENT numbers on this tree "
          "(42.09 whole-design vs 59.51 core-domain)",
          d["fmax_mhz"] == 42.09 and cd["fmax_mhz"] != d["fmax_mhz"])

    # --- ABSENCE IS NOT DATA ------------------------------------------------ #
    for drop in qg.CORE_DOMAIN_CLASSES:
        part = {k: v for k, v in tf.items() if not k.startswith(drop)}
        got = qg.core_domain_fmax(part)
        check(f"a missing {drop} class gives NO figure, not a min over the rest",
              got["fmax_mhz"] is None and got["missing"] == [drop], str(got))
    hollow = {k: (dict(v, fmax_mhz=None) if k.startswith("k=4.0") else v)
              for k, v in tf.items()}
    check("a class present but with NO ceiling gives no figure either",
          qg.core_domain_fmax(hollow)["fmax_mhz"] is None)
    check("an empty artifact gives no figure and does not crash",
          qg.core_domain_fmax({})["fmax_mhz"] is None)
    # NON-VACUITY: the minimum must actually track the data.
    moved = {k: (dict(v, fmax_mhz=12.0) if k.startswith("k=1.5") else v)
             for k, v in tf.items()}
    got = qg.core_domain_fmax(moved)
    check("the binding class FOLLOWS the numbers (k=1.5 at 12.0 MHz binds)",
          got["fmax_mhz"] == 12.0 and got["class"] == "k=1.5", str(got))

    # --- the contract, in the source ---------------------------------------- #
    src = (SW / "quartus_gate.py").read_text()
    check("the sweep records a `paired` block",
          '"paired": paired' in src)
    check("the whole-design half is still THE PROMOTION GATE",
          '"is_promotion_gate": True' in src)
    check("...and the core-domain half is NOT a gate",
          '"is_promotion_gate": False' in src)
    # ⚠ THE FAILURE MODE THE PAIRING EXISTS TO AVOID: a core-domain number
    # that some bar starts reading would re-scope the promotion gate onto the
    # figure that excludes both binding cones.
    for bar in ("E3_fmax", "E5_tns", "E9_all_seeds_pass"):
        seg = src.split(f'"{bar}"')[1][:600] if f'"{bar}"' in src else ""
        check(f"no bar {bar} reads the core-domain figure",
              "core_domain" not in seg and "core_fmax" not in seg)
    check("both halves are worst-of-N over the SAME seed set",
          '"seeds": seeds, "fmax_mhz": core_worst' in src)
    check("the core-domain worst-of-N is a MIN, not a mean or a max",
          "core_worst = min(core_ok)" in src)

    # --- and it survives a real invocation of the summary path -------------- #
    rc, out = run_gate(["--dry-run", "--seeds", "5"])
    check("--dry-run --seeds 5 still exits 0 with the pairing in the tool",
          rc == 0, out.strip()[-200:])


def main():
    global VERBOSE
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("-v", "--verbose", action="store_true")
    VERBOSE = ap.parse_args().verbose

    print("== test_quartus_gate: the --retention flag's and the DISTRIBUTION "
          "gate's falsifier (no Quartus binary required)")
    q1_retention_commands()
    q2_control_unchanged()
    q3_env_refused()
    q4_env_with_flag_ok()
    q5_unset_ok()
    q6_retention_parse_only_refused()
    q7_configuration_still_derived()
    q9_sweep_commands()
    q10_seed_spec()
    q11_e7_input_ordering()
    q12_e8_seed_honoured()
    q13_sweep_refusals()
    q14_truefmax_parse()
    q15_summary_stats()
    q16_paired_reporting()

    print(f"\n{NCHECK - len(FAILS)} / {NCHECK} checks pass")
    for f in FAILS:
        print(f"  FAIL  {f}")
    print(f"=== test_quartus_gate: {'PASS' if not FAILS else 'FAIL'}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
