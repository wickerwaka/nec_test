#!/usr/bin/env python3
"""intcone_paired_table -- render a `--seeds N` distribution record as the
PAIRED table this wave registered (`standing_gates.md` §A).

It reads the sweep's own `distribution.json` and prints the two halves with
their binding cones and their `k`, plus the per-draw rows, so a document's
table is TRANSCRIBED from the artifact rather than typed from a terminal.

    python3 sw/intcone_paired_table.py sw/testdata/g6dist/<label>/distribution.json
"""
import json
import sys
from pathlib import Path


def short(n):
    """The endpoint names are 120 characters of hierarchy; keep the tail."""
    if not n:
        return "-"
    n = n.split("|")
    return "|".join(n[-2:]) if len(n) > 1 else n[-1]


def main(paths):
    for p in paths:
        d = json.loads(Path(p).read_text())
        pr = d.get("paired")
        print(f"\n=== {d.get('label')}  [{d.get('configuration')}]  "
              f"record {d.get('id', '')[:16]}…")
        print(f"    inputs {d['input_manifest']['n_files']} files "
              f"{d['input_manifest']['sha256'][:16]}…   verdict {d['verdict']}")
        print(f"    {'seed':>4} {'Fmax':>7} {'setup':>8} {'ALMs':>7} "
              f"{'core-dom':>9} {'cls':>6} {'k':>5}  binding cone")
        for s in d["per_seed"]:
            cd = s.get("core_domain") or {}
            b = next((x for x in d["binding_path_per_seed"]
                      if x["seed"] == s["seed"]), {})
            print(f"    {s['seed']:>4} {s['fmax_mhz']:>7} "
                  f"{s['worst_setup_ns']:>8} {s['alms']:>7} "
                  f"{str(cd.get('fmax_mhz')):>9} {str(cd.get('class')):>6} "
                  f"{str(cd.get('k')):>5}  {short(b.get('from'))} -> "
                  f"{short(b.get('to'))}")
        if not pr:
            print("    (no `paired` block -- record predates the pairing)")
            continue
        wd, cd = pr["whole_design"], pr["core_domain"]
        print(f"    WHOLE-DESIGN : {wd['quotable_as']}  seed {wd['seed']} "
              f"k={wd['k']}")
        print(f"                   {short(wd['binding_from'])} -> "
              f"{short(wd['binding_to'])}")
        print(f"    CORE-DOMAIN  : {cd['quotable_as']}  seed {cd['seed']}")
        print(f"                   {short(cd['binding_from'])} -> "
              f"{short(cd['binding_to'])}")
        print(f"                   per class: " + "  ".join(
            f"{k} {v['min']}" for k, v in cd["per_class_worst_of_n"].items()))
        print(f"                   off-class draws: "
              f"{cd.get('off_class_draws') or 'none'}   "
              f"derivable on {cd['n_draws_derivable']}/{cd['n']}")
        f = d["fmax"]
        print(f"    spread {f['spread']}  median {f['median']}  "
              f"draws {f['sorted']}")
        print(f"    ALMs {d['alms']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
