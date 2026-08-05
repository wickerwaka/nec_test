#!/usr/bin/env python3
"""receipt_diff -- §5 of `docs/notes/artifact_receipt_layer.md`, the A/B DELTA
MANIFEST.

`gen_ucore_qsf.py --check` already proves one A/B claim -- that the two `.qsf`
files differ by the core and nothing else -- and it proves it on SETTINGS.  This
generalises it to ARTIFACTS: given two receipts it prints the symmetric
difference of their declared inputs, plus the command / env / tool delta.

For a legitimate A/B pair the output must be EXACTLY the intended axis:

    the pair                          the ONLY expected delta
    FSM vs ucore bitstream            files_ucore.qip <-> files.qip + the cores
    retention vs control binary       `command` (the -D macro) ONLY --
                                      inputs IDENTICAL
    a golden re-capture               the rig's version, nothing in hdl/

`--expect` turns that sentence into an assertion.  SM3 sitting 13 spent a whole
board session and two flashes establishing that FLASH #7 and #8 differ by the
macro alone; the BUILD-SIDE half of that claim is this one command, and the
board session is then measuring physics rather than bookkeeping.

    python3 sw/receipt_diff.py A.receipt.json B.receipt.json
    python3 sw/receipt_diff.py A B --expect-command      # inputs must match
    python3 sw/receipt_diff.py A B --expect rtl/ucore/v30u_eu.sv

EXIT 0 = the delta is within what was expected (or nothing was expected and the
delta is empty), 1 = it is not, 2 = the receipts could not be read.
"""
import argparse
import json
import sys
from pathlib import Path

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
import artifact as art                                     # noqa: E402


def load(p):
    p = Path(p)
    if p.is_dir():
        sys.exit(f"receipt_diff: {p} is a directory")
    if not p.is_file():
        # allow naming the ARTIFACT instead of its receipt
        r = art.receipt_path_for(p)
        if r.is_file():
            p = r
        else:
            print(f"receipt_diff: no receipt at {p}", file=sys.stderr)
            sys.exit(2)
    if p.suffix != ".json":
        r = art.receipt_path_for(p)
        if r.is_file():
            p = r
    try:
        return p, json.loads(p.read_text())
    except Exception as e:                                   # noqa: BLE001
        print(f"receipt_diff: {p}: {e}", file=sys.stderr)
        sys.exit(2)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--expect", action="append", default=[],
                    help="a repo-relative path allowed to differ (repeatable)")
    ap.add_argument("--expect-command", action="store_true",
                    help="the command and/or env may differ; the INPUT "
                         "manifests must be identical")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    pa, ra = load(a.a)
    pb, rb = load(a.b)
    d = art.diff_receipts(ra, rb)

    if a.json:
        print(json.dumps({"a": str(pa), "b": str(pb), **d}, indent=1))
    else:
        print(f"A  {ra.get('name')}   id {str(ra.get('id'))[:16]}…  "
              f"{ra.get('completed')}  label={ra.get('label')!r}")
        print(f"B  {rb.get('name')}   id {str(rb.get('id'))[:16]}…  "
              f"{rb.get('completed')}  label={rb.get('label')!r}")
        print(f"\ninputs: A {ra.get('inputs', {}).get('n_files')} files "
              f"{str(ra.get('inputs', {}).get('sha256'))[:16]}…   "
              f"B {rb.get('inputs', {}).get('n_files')} files "
              f"{str(rb.get('inputs', {}).get('sha256'))[:16]}…")
        for tag, ks in (("+ only in B", d["added"]),
                        ("- only in A", d["removed"]),
                        ("~ changed  ", d["changed"])):
            for k in ks:
                print(f"  {tag}  {k}")
        if d["n_input_delta"] == 0:
            print("  (input manifests are IDENTICAL)")
        for f in ("command", "env", "tool"):
            if d[f] is not None:
                print(f"\n{f} differs:\n  A {d[f][0]}\n  B {d[f][1]}")
        print(f"\noutputs identical: {d['outputs_identical']}")

    # --- the assertion ----------------------------------------------------- #
    allowed = set(a.expect)
    unexpected = [k for k in d["added"] + d["removed"] + d["changed"]
                  if k not in allowed]
    ok = not unexpected
    if not a.expect_command:
        ok = ok and d["command"] is None and d["env"] is None
    if d["tool"] is not None:
        ok = False
    if unexpected:
        print(f"\nUNEXPECTED input delta ({len(unexpected)}):", file=sys.stderr)
        for k in unexpected:
            print(f"  {k}", file=sys.stderr)
    if not a.expect_command and (d["command"] is not None or d["env"] is not None):
        print("\nUNEXPECTED command/env delta (pass --expect-command if it is "
              "the intended axis)", file=sys.stderr)
    if d["tool"] is not None:
        print("\nTOOL VERSIONS DIFFER -- these two artifacts were not built by "
              "the same compiler", file=sys.stderr)
    print("\n=== receipt_diff: "
          + ("AS EXPECTED" if ok else "DELTA IS NOT THE INTENDED AXIS"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
