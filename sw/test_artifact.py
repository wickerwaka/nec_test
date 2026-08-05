#!/usr/bin/env python3
"""test_artifact -- THE ARTIFACT LAYER'S OWN NON-VACUITY PROOF.

`docs/notes/artifact_receipt_layer.md` §6:

    "A receipt layer that has never rejected anything is incarnation 8."

So the layer ships gated by this file, and this file's job is to make it FAIL,
on purpose, in every way it is supposed to fail.  It runs entirely inside a
throw-away directory outside the repo -- it builds nothing real, touches no RTL,
and needs no tool but `python3`.

  MUTATION      §6's first half.  Perturb one byte of one DECLARED input and
                require the SCORER (not the producer) to refuse, naming both
                hashes.  Then perturb a file that is genuinely IRRELEVANT and
                require the scorer to run.
                A producer whose declared input list is UNDER-CLOSED fails the
                first half; one that HASHES THE WORLD fails the second.
  STALE         §6's second half, on the REAL historical fixture:
                `hdl/tb/obj_dir_sys/tb_sys.stale-s6` -- the binary a real
                scorer really ran for six days (`ucore_provenance.md` §73.7).
  WRONG NAME    incarnations 2 and 7 as a unit test: the command writes
                `Vout.bin`, the recipe declares `out.bin`.  The build must
                ABORT, and the PREVIOUS artifact and receipt must survive
                byte-identical -- because a scorer that runs after a failed
                build must run against something whose identity still holds.
  CONTENT KEY   touching an input without changing it must NOT rebuild; a
                compiler version change MUST invalidate.

    python3 sw/test_artifact.py            # exit 0 = the layer rejects
    python3 sw/test_artifact.py -v         # show every assertion

EXIT 0 = all checks pass, 1 = the layer failed to reject something.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))
import artifact as art                                     # noqa: E402

VERBOSE = False
FAILS = []
NCHECK = 0

# the disposable "compiler": concatenates its declared inputs into <outdir>/NAME
CC = ("import sys,pathlib;o=pathlib.Path(sys.argv[1]);n=sys.argv[2];"
      "o.mkdir(parents=True,exist_ok=True);"
      "(o/n).write_bytes(b''.join(pathlib.Path(p).read_bytes() "
      "for p in sys.argv[3:] if not p.startswith('--')))")
CC_FAIL = "import sys;sys.exit(3)"

# the real historical fixture named by the spec (§6 STALE-ARTIFACT)
STALE_S6 = ROOT / "hdl" / "tb" / "obj_dir_sys" / "tb_sys.stale-s6"


def check(name, cond, detail=""):
    global NCHECK
    NCHECK += 1
    if cond:
        if VERBOSE:
            print(f"  ok   {name}", flush=True)
    else:
        FAILS.append(name)
        print(f"  FAIL {name}   {detail}", flush=True)
    return cond


def raises(name, fn, want):
    """The layer must refuse, and the refusal must NAME the thing."""
    try:
        fn()
    except art.ArtifactError as e:
        msg = str(e)
        return check(name, want in msg,
                     f"refused, but the message does not contain {want!r}:\n"
                     f"{msg[:400]}")
    except Exception as e:                                   # noqa: BLE001
        return check(name, False, f"raised {type(e).__name__}: {e}")
    return check(name, False, "DID NOT RAISE -- the layer accepted it")


def mkrecipe(td, name="out.bin", writes=None, prog=CC, tool_probe=None,
             extra_inputs=()):
    """A complete, self-contained recipe over three source files."""
    src = td / "src"
    src.mkdir(parents=True, exist_ok=True)
    for f, body in (("a.txt", b"AAA"), ("b.txt", b"BBB")):
        p = src / f
        if not p.exists():
            p.write_bytes(body)
    # an UNDECLARED file living right next to the declared ones
    (src / "irrelevant.txt").write_bytes(b"not an input")
    inputs = [src / "a.txt", src / "b.txt", *extra_inputs]
    work = td / "obj"
    return art.Recipe(
        kind="test_artifact",
        artifact=work / name,
        inputs=inputs,
        command=["python3", "-c", prog, art.TOK_OUT, writes or name,
                 str(src / "a.txt"), str(src / "b.txt")],
        tool="python3-test",
        tool_probe=tool_probe,
        workdir=work,
        label="selftest")


# --------------------------------------------------------------------------- #
def t_build_and_key(td):
    print("\n[1] BUILD, RECEIPT, and the CONTENT-ADDRESSED KEY", flush=True)
    r = mkrecipe(td)
    rebuilt, rec = art.build(r, quiet=True)
    check("first build rebuilds", rebuilt)
    check("artifact promoted", r.artifact.is_file())
    check("receipt beside artifact", r.receipt_path.is_file())
    check("receipt schema", rec["schema"] == art.SCHEMA
          and rec["schema_version"] == art.SCHEMA_VERSION)
    check("receipt id is content-derived",
          rec["id"] == art.canonical_id(rec))
    check("inputs is a CLOSED list (2 files, not the world)",
          rec["inputs"]["n_files"] == 2, str(rec["inputs"]["files"]))
    check("irrelevant.txt is NOT an input",
          not any("irrelevant" in k for k in rec["inputs"]["files"]))
    check("outputs hashed", art.relpath(r.artifact) in rec["outputs"])
    check("P-1 receipt_id resolves", art.receipt_id(r.artifact) == rec["id"])
    check("history appended",
          (art.RECEIPT_DIR / "test_artifact.jsonl").is_file())

    rebuilt2, rec2 = art.build(r, quiet=True)
    check("second build is a NO-OP", not rebuilt2)
    check("id stable across the no-op", rec2["id"] == rec["id"])

    # THE KEY IS CONTENT, NOT MTIME.  Every previous freshness check in this
    # tree compared mtimes; mtime is why incarnation 2 survived six days.
    os.utime(td / "src" / "a.txt", (time.time() + 10, time.time() + 10))
    rebuilt3, rec3 = art.build(r, quiet=True)
    check("touch WITHOUT a content change does NOT rebuild", not rebuilt3)
    check("id unmoved by the touch", rec3["id"] == rec["id"])
    return r, rec


def t_mutation(td, r, rec0):
    print("\n[2] MUTATION -- spec §6 first half", flush=True)
    before = (td / "src" / "a.txt").read_bytes()

    # (a) a DECLARED input moves: the SCORER must refuse.
    (td / "src" / "a.txt").write_bytes(b"AAB")
    raises("a perturbed DECLARED input makes require() refuse",
           lambda: art.require(r.artifact, why="test"), "STALE")
    try:
        art.require(r.artifact)
    except art.ArtifactError as e:
        m = str(e)
        check("the refusal names the file", "src/a.txt" in m or "a.txt" in m)
        check("the refusal names BOTH hashes",
              m.count("receipt ") >= 1 and "tree " in m)

    rebuilt, rec1 = art.build(r, quiet=True)
    check("the producer then rebuilds", rebuilt)
    check("and mints a NEW receipt id", rec1["id"] != rec0["id"])
    check("require() accepts the rebuild",
          art.require(r.artifact)["id"] == rec1["id"])
    (td / "src" / "a.txt").write_bytes(before)
    art.build(r, quiet=True)

    # (b) an IRRELEVANT file moves: the scorer must RUN.  A producer that
    #     hashes the world fails here, and hashing the world is how a
    #     freshness layer becomes noise everyone learns to ignore.
    (td / "src" / "irrelevant.txt").write_bytes(b"changed, and it matters not")
    (td / "unrelated_elsewhere.txt").write_bytes(b"nor does this")
    ok = True
    try:
        art.require(r.artifact, why="test")
    except art.ArtifactError as e:                           # noqa: BLE001
        ok = False
        print(f"       {e}")
    check("a perturbed IRRELEVANT file does NOT block the scorer", ok)
    check("and does not force a rebuild either",
          not art.build(r, quiet=True)[0])


def t_stale_artifact(td, r):
    print("\n[3] STALE ARTIFACT -- spec §6 second half, on the REAL fixture", flush=True)
    good = r.artifact.read_bytes()
    if STALE_S6.is_file():
        shutil.copyfile(STALE_S6, r.artifact)
        src = f"the real {art.relpath(STALE_S6)}"
    else:
        r.artifact.write_bytes(b"an older binary that a scorer really ran")
        src = "a synthetic old binary (the tb_sys.stale-s6 fixture is absent)"
    print(f"      restored under the published name: {src}")
    raises("a STALE artifact under the current name is refused",
           lambda: art.require(r.artifact, why="test"), "STALE")
    try:
        art.require(r.artifact)
    except art.ArtifactError as e:
        check("the refusal names it as an OUTPUT mismatch", "OUTPUT" in str(e))
    check("and the producer repairs it", art.build(r, quiet=True)[0])
    check("bytes restored", r.artifact.read_bytes() == good)

    print("\n[4] NO RECEIPT -- the state all seven incarnations lived in", flush=True)
    r.receipt_path.unlink()
    raises("an artifact with NO receipt is refused",
           lambda: art.require(r.artifact, why="test"), "NO RECEIPT")
    art.build(r, quiet=True)

    print("\n[5] ARTIFACT ABSENT", flush=True)
    keep = r.artifact.read_bytes()
    r.artifact.unlink()
    raises("a missing artifact is refused",
           lambda: art.require(r.artifact, why="test"), "ARTIFACT ABSENT")
    r.artifact.write_bytes(keep)


def t_wrong_name(td):
    print("\n[6] WRONG OUTPUT NAME -- incarnations 2 and 7, as a unit test", flush=True)
    r = mkrecipe(td / "wn")
    art.build(r, quiet=True)
    good_bytes = r.artifact.read_bytes()
    good_rec = r.receipt_path.read_text()

    # the compiler writes `Vout.bin`; the recipe (and every scorer) says
    # `out.bin`.  §73.7: this state printed REBUILT every time for six days.
    bad = mkrecipe(td / "wn", writes="Vout.bin")
    (td / "wn" / "src" / "a.txt").write_bytes(b"forces a rebuild")
    raises("a build whose command writes ANOTHER NAME aborts",
           lambda: art.build(bad, quiet=True), "BUILD FAILED")
    try:
        art.build(bad, quiet=True)
    except art.ArtifactError as e:
        check("the abort says the output was NOT WRITTEN",
              "NOT WRITTEN" in str(e))
        check("the abort lists what the command DID write",
              "Vout.bin" in str(e))
    check("NOTHING was promoted: the old artifact survives byte-identical",
          r.artifact.read_bytes() == good_bytes)
    check("...and so does its receipt",
          r.receipt_path.read_text() == good_rec)
    check("no staging or trash directory is left behind",
          not [p for p in (td / "wn").iterdir()
               if p.name.startswith(".obj.")],
          str(list((td / "wn").iterdir())))
    # and the scorer, run after that failed build, refuses -- because the
    # inputs moved and the artifact is the OLD one.  This is the whole point.
    raises("the scorer refuses after the failed build",
           lambda: art.require(r.artifact, why="test"), "STALE")

    print("\n[7] BUILD RC != 0, and a MISSING DECLARED INPUT", flush=True)
    (td / "wn" / "src" / "a.txt").write_bytes(b"AAA")
    art.build(mkrecipe(td / "wn"), quiet=True)
    rcfail = mkrecipe(td / "wn", prog=CC_FAIL)
    (td / "wn" / "src" / "a.txt").write_bytes(b"moved again")
    raises("a nonzero rc aborts the build",
           lambda: art.build(rcfail, quiet=True), "BUILD FAILED")
    check("the artifact still exists after the failed build",
          r.artifact.is_file())
    (td / "wn" / "src" / "a.txt").write_bytes(b"AAA")

    miss = mkrecipe(td / "wn", extra_inputs=[td / "wn" / "src" / "gone.txt"])
    raises("a DECLARED input that does not exist aborts the build",
           lambda: art.build(miss, quiet=True), "DECLARED INPUT MISSING")


def t_tool(td):
    print("\n[8] TOOL VERSION (deviation D-2)", flush=True)
    r = mkrecipe(td / "tv", tool_probe=["python3", "--version"])
    _, rec = art.build(r, quiet=True)
    check("the tool version is recorded", bool(rec["tool"]),
          str(rec["tool"]))
    d = json.loads(r.receipt_path.read_text())
    d["tool"] = "python3 0.0.0-from-1998"
    r.receipt_path.write_text(json.dumps(d))
    raises("a receipt built by a DIFFERENT tool version is refused",
           lambda: art.require(r.artifact, why="test"), "TOOL")


def t_delta(td):
    print("\n[9] THE A/B DELTA MANIFEST -- spec §5", flush=True)
    a = mkrecipe(td / "ab", name="a.bin")
    _, ra = art.build(a, quiet=True)
    # same inputs, different command: the RETENTION-vs-CONTROL shape
    b = art.Recipe(kind="test_artifact", artifact=(td / "ab" / "obj2" / "a.bin"),
                   inputs=a.inputs,
                   command=a.command + ["--flag"],
                   tool="python3-test", workdir=td / "ab" / "obj2",
                   label="selftest-b")
    _, rb = art.build(b, quiet=True)
    d = art.diff_receipts(ra, rb)
    check("identical inputs -> zero input delta", d["n_input_delta"] == 0)
    check("the command delta is reported", d["command"] is not None)

    rc_ = subprocess.run([sys.executable, str(SW / "receipt_diff.py"),
                          str(a.receipt_path), str(b.receipt_path)],
                         capture_output=True, text=True)
    check("receipt_diff exits 1 on an unexplained command delta",
          rc_.returncode == 1, rc_.stdout[-300:])
    rc_ = subprocess.run([sys.executable, str(SW / "receipt_diff.py"),
                          str(a.receipt_path), str(b.receipt_path),
                          "--expect-command"], capture_output=True, text=True)
    check("...and 0 when the command IS the declared axis",
          rc_.returncode == 0, rc_.stdout[-300:])

    # one input differs
    (td / "ab" / "src" / "b.txt").write_bytes(b"BBC")
    _, rb2 = art.build(b, quiet=True)
    d2 = art.diff_receipts(ra, rb2)
    check("a one-file input delta is reported as exactly one file",
          d2["n_input_delta"] == 1 and len(d2["changed"]) == 1,
          json.dumps(d2))


def main():
    global VERBOSE
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args()
    VERBOSE = a.verbose

    base = Path(tempfile.mkdtemp(prefix="artifact_selftest_",
                                 dir=Path.home() / ".cache"))
    # keep the layer's shared history out of the repo for a self-test run
    hist = art.RECEIPT_DIR
    art.RECEIPT_DIR = base / "receipts"
    try:
        r, rec = t_build_and_key(base)
        t_mutation(base, r, rec)
        t_stale_artifact(base, r)
        t_wrong_name(base)
        t_tool(base)
        t_delta(base)
    finally:
        art.RECEIPT_DIR = hist
        if a.keep:
            print(f"\nkept: {base}")
        else:
            shutil.rmtree(base, ignore_errors=True)

    print(f"\n=== test_artifact: {NCHECK - len(FAILS)}/{NCHECK} checks pass")
    if FAILS:
        print("FAILED: " + ", ".join(FAILS))
        print("=== THE LAYER DID NOT REJECT SOMETHING IT MUST REJECT.")
        return 1
    print("=== the layer rejects a perturbed input, a stale artifact, a "
          "receipt-less\n    artifact, a wrong-named output and a mismatched "
          "tool -- and runs\n    through an irrelevant change.  NON-VACUOUS.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
