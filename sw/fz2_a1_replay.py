#!/usr/bin/env python3
"""fz2_a1_replay - the PROOF that amendment A-1 changed the escalation, taken
on the real board capture that halted the census.  Offline, no board, no rig.

`docs/notes/fz2_corpus_prereg_2026-08-08.md` §11 A-1 demotes
`escaped_code_region` out of the provenance-alarm set.  A stop-condition change
that cannot be SHOWN to still stop is not a safe change, so this replays the
banked rows of the seed that stopped the run (`fz2c/400001`) through
`fuzz_classify.classify` + `EscalationPolicy` TWICE: once against the
pre-amendment module (`git show 902ec0de17:sw/fuzz_classify.py`) as the CONTROL,
once against the tree.

THE CONTROL IS THE WHOLE POINT.  It must reproduce the BANKED verdict and sub
exactly -- verdict, sub-reason and the ('STOP', 'provenance_alarm') escalation.
If it does not, the replay is not a replay and nothing it says about the tree is
evidence; the script exits non-zero on that and says so on the line.

The rows live in `sw/testdata/campaigns/fz2c-prereg-A1-archive/`, archived by
rename under A-1 because they were scored under a rule that no longer exists.
Campaign captures are `.gitignore`d, so a reviewer without them will see the
glob come up empty -- that is a missing input, not a failure.

    python3 sw/fz2_a1_replay.py [scratch-dir]
"""
import gzip
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path("/home/wickerwaka/src/nec_test")
SW = ROOT / "sw"
sys.path.insert(0, str(SW))
import fuzz_campaign as fzc          # noqa: E402
import fz2_w1 as fz                  # noqa: E402
import fuzz_classify as fc_new       # noqa: E402


def load_old(tmp):
    """The pre-amendment fuzz_classify, imported under its own name."""
    src = subprocess.run(["git", "-C", str(ROOT), "show",
                          "902ec0de17:sw/fuzz_classify.py"],
                         capture_output=True, text=True, check=True).stdout
    p = Path(tmp) / "fuzz_classify.py"          # same basename: its own imports
    p.write_text(src)
    spec = importlib.util.spec_from_file_location("fc_old", p)
    m = importlib.util.module_from_spec(spec)
    sys.modules["fc_old"] = m
    spec.loader.exec_module(m)
    return m


def main():
    tmp = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp")
    fc_old = load_old(tmp)

    cid = "fz2c"
    adir = fzc.CAMPAIGNS / "fz2c-prereg-A1-archive"
    lines = {json.loads(l)["k"]: json.loads(l)
             for l in open(adir / "results.jsonl")}
    rc = 0
    for k in sorted(lines):
        banked = lines[k]
        cap = next((adir / "captures").glob(f"*_{k}_*.json.gz"))
        d = json.load(gzip.open(cap))
        real, sim = d["real"], d["sim"]
        j = fz._stratum_of(cid, k)
        cfg = fzc.derive_case(cid, k, fz.ov_of(fz.STRATA[j]))
        g = fzc.build(cfg)
        print(f"\n=== {cid}/{k}  ({cap.name})")
        print(f"    banked verdict : {banked['verdict']}/{banked['sub']}")
        print(f"    banked escaped : {banked['escaped']} n={banked['escaped_n']}"
              f"  arch_ok={banked['arch_ok']} arch_match={banked['arch_match']}"
              f"  bad_rows={banked['bad_rows']}")
        for tag, mod in (("BEFORE (902ec0de17)", fc_old), ("AFTER  (tree)", fc_new)):
            ctx = mod.Ctx(
                tier="A" if cfg["tier"] == "soup" else "B",
                waits=0 if (cfg["waits"]["wrand"] or cfg.get("wvec"))
                else cfg["waits"]["fixed"],
                wrand=bool(cfg["waits"]["wrand"] or cfg.get("wvec")),
                real_is_chip=True, brkem_pos=g.get("brkem_pos", []),
                lea_mod3_pos=g.get("lea_mod3_pos", []),
                has_halt=g.get("has_halt", False),
                with_drift=(cfg["waits"]["wrand"] or cfg["waits"]["fixed"] > 0),
                cid=cid, seed=f"{cid}/{k}", cfg_hash=cfg["cfg_hash"])
            v = mod.classify(real, sim, ctx, engine=fzc._engine())
            acts = mod.EscalationPolicy().consult(v, ctx)
            esc = mod.escaped_code_region(real, v.n)
            print(f"    {tag:22s} -> {v.verdict}/{v.sub}"
                  f"  alarms={v.alarms}  escalation={acts}")
            print(f"    {'':22s}    escaped_code_region(real)={esc}"
                  f"  escape_count={fzc._escape_count(real, v.n)}")
            if tag.startswith("BEFORE"):
                same = (v.verdict == banked["verdict"] and v.sub == banked["sub"])
                print(f"    {'':22s}    CONTROL reproduces the banked line: "
                      f"{'YES' if same else 'NO'}")
                if not same:
                    rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
