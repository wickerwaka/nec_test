#!/usr/bin/env python3
"""artifact -- THE SHARED ARTIFACT / RECEIPT LAYER.

`docs/notes/artifact_receipt_layer.md` is the specification; this is its
implementation.  Read the spec first -- the deviations are recorded there as
errata beside the text they deviate from, and are summarised in §D below.

WHY IT EXISTS.  `ucore_provenance.md` records SEVEN incarnations of one bug: a
scorer that ran against an artifact nobody proved was the artifact it named.
They are all the same bug -- *a file path is not an identity*.  Nothing in the
tree connected "the number I am about to write into the ledger" to "the exact
bytes that produced it".

WHAT IT IS.  A postcondition and a hash.  It is NOT a build system, NOT a cache,
NOT reproducible-builds-in-general.  It answers exactly one question, on demand:
**which bytes produced this number?**


  §A  THE POSTCONDITION -- the whole design in one sentence

      Every binary on a scorer's path must appear in a RECEIPT that names the
      inputs it was built from, and a scorer must REFUSE TO RUN against an
      artifact with no receipt, or a receipt whose input hashes do not match
      the tree it is being asked about.

      P-1 (identity)   a scorer can name the receipt id of every artifact it
                       executed.  A number with no artifact id is not quotable.
      P-2 (freshness)  before executing, the declared inputs are re-hashed FROM
                       THE TREE and compared.  A mismatch is a hard error
                       naming both hashes -- not a rebuild, not a warning.


  §B  THE THREE ENTRY POINTS -- and there are only three

      recipe = Recipe(kind=..., artifact=..., inputs=[...], command=[...],
                      tool="verilator", outputs=[...])

      build(recipe)      the PRODUCER.  Content-keyed: rebuilds iff the key
                         moved.  Builds into a staging dir and PROMOTES.
      require(artifact)  the SCORER POSTCONDITION.  Raises ArtifactError,
                         loudly, naming what is stale.  Needs no Recipe -- the
                         receipt is self-describing.
      ensure(recipe)     build-if-needed then require.  What a gate calls.

      Plus `diff_receipts()` for §5's A/B delta manifest, exposed as
      `sw/receipt_diff.py`.


  §C  THE BUILD KEY IS CONTENT, NOT MTIME

      Every previous freshness check in this tree compared mtimes, and mtime is
      why incarnation 2 survived six days: the compiler wrote a DIFFERENT FILE,
      so the file the scorer opened had an old mtime and an old mtime is
      indistinguishable from "up to date" when nothing forces the comparison.

      `build_key` = sha256( inputs.sha256 | tool | command | env ).  A build is
      skipped iff the key matches AND every declared output still hashes to
      what the receipt says.  Touching a file without changing it does NOT
      rebuild; reverting a file to an already-built state does NOT rebuild;
      upgrading the compiler DOES.


  §D  DEVIATIONS FROM THE SPEC, recorded (see the spec's own erratum block)

      D-1  §4 asks for `rename(<staging>, <destination>)` as ONE atomic step.
           POSIX cannot rename a directory onto a non-empty directory, so the
           promote is two renames (dest -> trash, staging -> dest) and there is
           a microsecond window in which the destination does not exist.  The
           guarantee the spec wanted is recovered STRICTLY MORE STRONGLY by
           `require()` re-hashing `outputs` as well as `inputs`: a destination
           that is absent, partial, or paired with a receipt written for
           different bytes is a hard error, whatever produced it.
      D-2  the spec's schema puts `tool` OUTSIDE the hashed `inputs` region.
           Kept -- but `require()` compares the CURRENT tool version against the
           receipt's and fails on a mismatch, and `tool` is in `build_key`.  A
           compiler upgrade silently invalidating every binary in the tree is
           incarnation-shaped, and this is three lines.
      D-3  `build_key` is an added field (the brief's "content-addressed build
           key").  `id` is still the spec's content hash of the whole object.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent

SCHEMA = "nec_test/receipt"
SCHEMA_VERSION = 1
RECEIPT_DIR = ROOT / "sw" / "testdata" / "receipts"

# the two tokens a recorded `command` may carry, so that neither the checkout
# location nor the (per-build, temporary) staging directory leaks into the
# hashed object.  Substituted at exec time; stored unsubstituted.
TOK_ROOT = "@ROOT@"
TOK_OUT = "@OUT@"


class ArtifactError(RuntimeError):
    """A scorer was asked to run against bytes nobody vouched for."""


def _shout(title, lines):
    bar = "=" * 72
    msg = "\n".join([bar, f"  ARTIFACT LAYER -- {title}", bar] +
                    [f"  {ln}" for ln in lines] + [bar])
    print(msg, file=sys.stderr, flush=True)
    return msg


# --------------------------------------------------------------------------- #
# hashing
# --------------------------------------------------------------------------- #
def relpath(p):
    """Repo-relative POSIX path.  Paths outside the repo are recorded absolute
    (and are then a portability finding, not a silent one)."""
    p = Path(p)
    try:
        return Path(p).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(Path(p).resolve())


def sha256_file(p):
    """The file's hash, or the literal string `MISSING`.

    Spec §3 rule 2: MISSING IS A VALUE.  A vanished input must change
    `inputs.sha256`, so absence is hashed and never skipped."""
    p = Path(p)
    if not p.is_file():
        return "MISSING"
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def manifest(paths):
    """{n_files, sha256, files} over a CLOSED list (spec §3 rule 1).

    A file the command reads and this list omits is a defect in the producer,
    not an oversight -- and `sw/test_artifact.py`'s MUTATION check is what makes
    that testable rather than aspirational."""
    ent = sorted({relpath(p): None for p in paths})
    files = {r: sha256_file(ROOT / r) for r in ent}
    blob = "\n".join(f"{h}  {r}" for r, h in sorted(files.items())).encode()
    return {"n_files": len(files),
            "sha256": hashlib.sha256(blob).hexdigest(),
            "files": files}


def canonical_id(rec):
    """sha256 of the canonical form of the object with `id` removed (spec §3
    rule 4): two identical builds collide BY CONSTRUCTION, and that collision
    is information."""
    r = {k: v for k, v in rec.items() if k != "id"}
    return hashlib.sha256(
        json.dumps(r, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


# --------------------------------------------------------------------------- #
# tool + tree state
# --------------------------------------------------------------------------- #
_TOOLV = {}
_TOOL_CMD = {"verilator": ["verilator", "--version"],
             "quartus_sh": None}          # supplied by the caller (path varies)


def tool_version(tool, probe=None):
    """One line identifying the tool.  Cached per process.

    The probe is CARRIED IN THE RECEIPT (`tool_probe`), so `require()` can
    re-ask the question later without a Recipe -- otherwise D-2's tool check
    would silently degrade to "no probe, no comparison", which is the
    vacuous-gate shape one level down."""
    key = (tool, tuple(probe) if probe else None)
    if key in _TOOLV:
        return _TOOLV[key]
    cmd = probe or _TOOL_CMD.get(tool)
    v = None
    if cmd:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            v = (r.stdout + r.stderr).strip().splitlines()
            v = v[0].strip() if v else None
        except Exception:                                    # noqa: BLE001
            v = None
    _TOOLV[key] = v
    return v


_GIT = {}


def git_state():
    """Spec §3 rule 3: `dirty_tracked` counts TRACKED modifications only.
    Untracked build output in the tree is not tree drift and must not flip it."""
    if _GIT:
        return dict(_GIT)

    def sh(*a):
        try:
            return subprocess.run(a, cwd=ROOT, capture_output=True, text=True,
                                  check=True).stdout.strip()
        except Exception:                                    # noqa: BLE001
            return "unknown"
    _GIT.update({"head": sh("git", "rev-parse", "HEAD"),
                 "describe": sh("git", "describe", "--always", "--dirty"),
                 "dirty_tracked": bool(sh("git", "status", "--porcelain",
                                          "-uno"))})
    return dict(_GIT)


# --------------------------------------------------------------------------- #
# the recipe
# --------------------------------------------------------------------------- #
class Recipe:
    """WHAT AN ARTIFACT IS A FUNCTION OF, declared in one place.

    kind      receipt family; also the `<kind>.jsonl` history file
    artifact  THE file a scorer opens.  Its receipt lives beside it.
    inputs    the CLOSED list of files the command reads
    command   argv, with @ROOT@ and @OUT@ tokens (see the module docstring)
    outputs   files the command must have written, `artifact` first.  Declaring
              the WRONG NAME here is what turns incarnations 2 and 7 from a
              six-day silence into a build-time abort.
    workdir   the directory built into and promoted; defaults to
              `artifact.parent`
    """

    def __init__(self, kind, artifact, inputs, command, tool,
                 outputs=None, env=None, cwd=None, workdir=None,
                 tool_probe=None, label=""):
        self.kind = kind
        self.artifact = Path(artifact).resolve()
        self.inputs = [Path(p) for p in inputs]
        self.command = list(command)
        self.tool = tool
        self.tool_probe = tool_probe
        self.outputs = [Path(p).resolve()
                        for p in (outputs or [self.artifact])]
        if self.artifact not in self.outputs:
            self.outputs.insert(0, self.artifact)
        self.env = dict(env or {})
        self.cwd = Path(cwd or ROOT)
        self.workdir = Path(workdir).resolve() if workdir \
            else self.artifact.parent
        self.label = label
        for o in self.outputs:
            if self.workdir not in o.parents:
                raise ValueError(f"output {o} is not under workdir "
                                 f"{self.workdir}")

    @property
    def receipt_path(self):
        return self.artifact.parent / (self.artifact.name + ".receipt.json")

    def resolved_command(self, out):
        return [c.replace(TOK_OUT, str(out)).replace(TOK_ROOT, str(ROOT))
                for c in self.command]

    def build_key(self, mf=None):
        """§C.  Everything the artifact is a function of, in one hash."""
        mf = mf or manifest(self.inputs)
        blob = json.dumps({"inputs": mf["sha256"],
                           "tool": tool_version(self.tool, self.tool_probe),
                           "command": self.command,
                           "env": self.env,
                           "outputs": [relpath(o) for o in self.outputs]},
                          sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(blob).hexdigest()


# --------------------------------------------------------------------------- #
# receipts on disk
# --------------------------------------------------------------------------- #
def receipt_path_for(artifact):
    artifact = Path(artifact).resolve()
    return artifact.parent / (artifact.name + ".receipt.json")


def load_receipt(artifact):
    p = receipt_path_for(artifact)
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:                                        # noqa: BLE001
        return None


def _write_json_atomic(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / f".{path.name}.tmp{os.getpid()}"
    with open(tmp, "w") as f:
        f.write(json.dumps(obj, indent=1, sort_keys=True) + "\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def append_history(rec):
    """A copy in a repo-level `.jsonl` so history survives `rm -rf obj_dir`
    (spec §3).  The obj_dirs are gitignored; this file is not."""
    RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
    p = RECEIPT_DIR / f"{rec['kind']}.jsonl"
    with open(p, "a") as f:
        f.write(json.dumps(rec, sort_keys=True, separators=(",", ":")) + "\n")
        f.flush()
        os.fsync(f.fileno())
    return p


# --------------------------------------------------------------------------- #
# THE PRODUCER
# --------------------------------------------------------------------------- #
def build(recipe, force=False, quiet=False):
    """-> (rebuilt: bool, receipt: dict).  Raises ArtifactError on any failure.

    Spec §4: build into a staging directory beside the destination, verify the
    DECLARED outputs exist and were written by THIS command (stat the staging
    dir -- do NOT trust the exit code; incarnation 2 exits 0), hash, write the
    receipt, then promote.
    """
    mf = manifest(recipe.inputs)
    key = recipe.build_key(mf)
    old = load_receipt(recipe.artifact)
    if not force and old and old.get("build_key") == key:
        # ...and the bytes are still the bytes.  A matching key with a moved
        # output is exactly the crashed-mid-promote case, and it rebuilds.
        if all(sha256_file(ROOT / r) == h
               for r, h in (old.get("outputs") or {}).items()):
            return False, old

    missing = [r for r, h in mf["files"].items() if h == "MISSING"]
    if missing:
        raise ArtifactError(_shout(
            f"DECLARED INPUT MISSING -- {relpath(recipe.artifact)}",
            [f"recipe {recipe.kind}/{recipe.label or recipe.artifact.name}",
             "these declared inputs do not exist:"] +
            [f"    {m}" for m in missing[:20]]))

    staging = recipe.workdir.parent / f".{recipe.workdir.name}.staging.{os.getpid()}"
    trash = recipe.workdir.parent / f".{recipe.workdir.name}.trash.{os.getpid()}"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)

    cmd = recipe.resolved_command(staging)
    env = dict(os.environ)
    env.update(recipe.env)
    if not quiet:
        print(f"artifact: BUILD {recipe.kind}/{relpath(recipe.artifact)}\n"
              f"  {' '.join(cmd)}", flush=True)
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    t0 = time.time()
    promoted = False
    try:
        r = subprocess.run(cmd, cwd=str(recipe.cwd), env=env)
        rc = r.returncode
        # THE POSTCONDITION THE PRODUCER ASSERTS BEFORE PROMOTING (spec §4).
        # Every declared output must have been written by THIS command, into
        # the staging dir.  This is the check that turns incarnations 2 and 7 --
        # `build()` compiling into `Vtb_sys` while `capture` opened `tb_sys` --
        # into an abort at the build instead of a silent six-day regression.
        staged = {}
        bad = []
        for o in recipe.outputs:
            s = staging / o.relative_to(recipe.workdir)
            if not s.is_file():
                bad.append(f"{relpath(o)}: NOT WRITTEN (the command wrote "
                           f"somewhere else, or under another name)")
            elif s.stat().st_size == 0:
                bad.append(f"{relpath(o)}: written but EMPTY")
            elif s.stat().st_mtime < t0 - 1:
                bad.append(f"{relpath(o)}: mtime PRECEDES this command")
            else:
                staged[relpath(o)] = sha256_file(s)
        if rc != 0 or bad:
            names = sorted(p.name for p in staging.iterdir())[:12]
            raise ArtifactError(_shout(
                f"BUILD FAILED -- {relpath(recipe.artifact)}",
                [f"recipe   {recipe.kind}/{recipe.label or ''}",
                 f"command  {' '.join(cmd)}",
                 f"rc       {rc}"] +
                [f"OUTPUT   {b}" for b in bad] +
                [f"staging  {staging}",
                 f"         holds: {', '.join(names)}"
                 f"{' ...' if len(names) == 12 else ''}",
                 "",
                 "NOTHING WAS PROMOTED.  The previous artifact and its receipt "
                 "are untouched.",
                 ]))

        rec = {
            "schema": SCHEMA,
            "schema_version": SCHEMA_VERSION,
            "kind": recipe.kind,
            "name": relpath(recipe.artifact),
            "label": recipe.label,
            "inputs": mf,
            "command": recipe.command,
            "env": recipe.env,
            "tool": tool_version(recipe.tool, recipe.tool_probe),
            "tool_name": recipe.tool,
            "tool_probe": list(recipe.tool_probe) if recipe.tool_probe else None,
            "tool_sha256": None,
            "outputs": staged,
            "build_key": recipe.build_key(mf),
            "git": git_state(),
            "started": started,
            "completed": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "seconds": round(time.time() - t0, 1),
            "rc": rc,
            "figures": {},
            "verdict": None,
        }
        rec["id"] = canonical_id(rec)
        _write_json_atomic(
            staging / (recipe.artifact.name + ".receipt.json"), rec)

        # --- PROMOTE (deviation D-1 in the module docstring) --------------- #
        if recipe.workdir.exists():
            os.rename(recipe.workdir, trash)
        os.rename(staging, recipe.workdir)
        promoted = True
    finally:
        shutil.rmtree(staging, ignore_errors=True)
        # ONLY delete the displaced old build once the new one is in place.
        # If the second rename failed, `trash` is the ONLY copy of the previous
        # artifact and deleting it would turn a failed build into data loss.
        if promoted:
            shutil.rmtree(trash, ignore_errors=True)
        elif trash.exists():
            os.rename(trash, recipe.workdir)          # put it back

    append_history(rec)
    if not quiet:
        print(f"artifact: PROMOTED {relpath(recipe.artifact)}  "
              f"receipt {rec['id'][:16]}…  ({rec['seconds']}s)", flush=True)
    return True, rec


# --------------------------------------------------------------------------- #
# THE SCORER POSTCONDITION
# --------------------------------------------------------------------------- #
def require(artifact, why=""):
    """P-1 + P-2.  -> the receipt.  Raises ArtifactError, loudly.

    The receipt is self-describing, so this needs no Recipe: any tool anywhere
    can assert the postcondition on any path it is about to execute.

    It does NOT rebuild (spec §8).  A mismatch is an error with two hashes in
    it; deciding to rebuild is the agent's job, and an automatic rebuild here is
    how incarnation 2 stayed invisible for six days.
    """
    artifact = Path(artifact)
    rp = receipt_path_for(artifact)
    if not artifact.is_file():
        raise ArtifactError(_shout(
            f"ARTIFACT ABSENT -- {relpath(artifact)}",
            [f"asked for by: {why or 'a scorer'}",
             "there is nothing at that path to run."]))
    rec = load_receipt(artifact)
    if rec is None:
        raise ArtifactError(_shout(
            f"NO RECEIPT -- {relpath(artifact)}",
            [f"asked for by: {why or 'a scorer'}",
             f"expected     {relpath(rp)}",
             "",
             "This binary was not built through the artifact layer, so NOTHING",
             "in the tree says what it is a function of.  That is precisely the",
             "state in which all seven incarnations of the vacuous-gate pattern",
             "happened.  Rebuild it through its recipe."]))
    if rec.get("schema") != SCHEMA:
        raise ArtifactError(_shout(
            f"NOT A RECEIPT -- {relpath(rp)}",
            [f"schema {rec.get('schema')!r}, expected {SCHEMA!r}"]))

    bad = []
    for r, h in sorted((rec.get("inputs") or {}).get("files", {}).items()):
        now = sha256_file(ROOT / r)
        if now != h:
            bad.append(f"INPUT   {r}\n            receipt {h[:16]}…"
                       f"   tree {now[:16] if now != 'MISSING' else now}…")
    for r, h in sorted((rec.get("outputs") or {}).items()):
        now = sha256_file(ROOT / r)
        if now != h:
            bad.append(f"OUTPUT  {r}\n            receipt {h[:16]}…"
                       f"   tree {now[:16] if now != 'MISSING' else now}…")
    cur_tool = tool_version(rec.get("tool_name") or "", rec.get("tool_probe"))
    if rec.get("tool") and cur_tool and cur_tool != rec["tool"]:
        bad.append(f"TOOL    receipt {rec['tool']!r}   now {cur_tool!r}")
    if bad:
        raise ArtifactError(_shout(
            f"STALE -- {relpath(artifact)}",
            [f"asked for by : {why or 'a scorer'}",
             f"receipt      : {relpath(rp)}",
             f"receipt id   : {rec.get('id', '?')[:16]}…",
             f"built        : {rec.get('completed')}",
             "",
             f"{len(bad)} declared file(s) DO NOT MATCH THE TREE:"] +
            [f"  {b}" for b in bad[:20]] +
            (["  …"] if len(bad) > 20 else []) +
            ["",
             "The number this scorer was about to produce would not have been",
             "a number about this tree.  REBUILD, then re-run."]))
    return rec


_ENSURED = {}


def ensure(recipe, force=False, quiet=True, why=""):
    """build-if-needed, then require.  What a gate calls.  Memoised per process
    so a per-seed loop pays the hashing once.  -> the artifact Path."""
    k = (str(recipe.artifact), recipe.build_key())
    if not force and k in _ENSURED:
        return recipe.artifact
    build(recipe, force=force, quiet=quiet)
    rec = require(recipe.artifact, why=why or recipe.label or recipe.kind)
    _ENSURED[k] = rec["id"]
    return recipe.artifact


def receipt_id(artifact):
    """P-1: what a scorer prints beside its result."""
    rec = load_receipt(artifact)
    return (rec or {}).get("id")


# --------------------------------------------------------------------------- #
# §5  THE A/B DELTA MANIFEST
# --------------------------------------------------------------------------- #
def diff_receipts(a, b):
    """The symmetric difference of two receipts.  For a legitimate A/B pair the
    output must be EXACTLY the intended axis and nothing else."""
    fa = (a.get("inputs") or {}).get("files", {})
    fb = (b.get("inputs") or {}).get("files", {})
    added = sorted(set(fb) - set(fa))
    removed = sorted(set(fa) - set(fb))
    changed = sorted(k for k in set(fa) & set(fb) if fa[k] != fb[k])
    return {
        "added": added, "removed": removed, "changed": changed,
        "command": None if a.get("command") == b.get("command")
                   else [a.get("command"), b.get("command")],
        "env": None if a.get("env") == b.get("env")
               else [a.get("env"), b.get("env")],
        "tool": None if a.get("tool") == b.get("tool")
                else [a.get("tool"), b.get("tool")],
        "outputs_identical": (a.get("outputs") == b.get("outputs")),
        "n_input_delta": len(added) + len(removed) + len(changed),
    }
