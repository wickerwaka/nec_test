#!/usr/bin/env python3
"""f7a_arbitrate - board arbitration for the F7a COLD-ARM assertion (task #29
Phase-5 triage).

The TB (Verilator, --assert) traps at v30_biu.sv:1073-1077 with
`F7a COLD-ARM VIOLATION` when the Family-7 strio idle-arm coincides with a
queue push (push_pend != 0). The fuzz soup reaches that state via a strio lead
under waits (with or without an interrupt) - a cross-domain combination the
task-#24 strio invariant never saw. The flashed FABRIC carries no assertions
(sim-only `ifdef VERILATOR`), so the board is the arbiter:

  run the SAME image+evt+waits on the socketed chip (use_core=0) AND the fabric
  core (use_core=1) and classify chip-vs-fabric. If FUNCTIONAL-clean (SUCCESS /
  TIMING / KNOWN_ACCEPTED-cadence) the fabric behaviour the TB would trap on is
  chip-CORRECT -> the invariant is over-narrow. A FUNCTIONAL verdict = real bug
  -> STOP.

Board discipline: ServeRunner.ensure() force-cleans the rig at connect; chip
legs cached; any RunError STOPs (no retry into a wedge); board left use_core=0.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))
import fuzz_campaign as fzc                             # noqa: E402
import fuzz_classify as fc                              # noqa: E402
from fuzz_accept import AcceptEngine                    # noqa: E402
import check_seq                                        # noqa: E402
from v30run import RunError                             # noqa: E402

HOST = "root@mister-nec"
CACHE = SW / "testdata" / "chipcache"
EVT_OV = {"force_tier": "soup", "force_contained": True, "strict": True,
          "force_evt": True}
WR_OV = {"force_tier": "soup", "force_contained": True, "strict": True,
         "force_wrand": [1, 3, 7]}

# (k, ov, label) - 2 interrupt-armed + 2 wrand-only (no evt) F7a firers
CASES = [(10001, EVT_OV, "NMI w1 (pinned reproducer)"),
         (10029, EVT_OV, "NMI wrand"),
         (20110, WR_OV, "no-evt wrand wmax1"),
         (20192, WR_OV, "no-evt wrand wmax7")]


def tb_assert_line(image, cfg, meta):
    """Re-run the TB to capture the F7a violation state line (or 'none')."""
    w = cfg["waits"]
    wrand = (w["wmax"], w["wseed"]) if w["wrand"] else None
    fixed = 0 if w["wrand"] else w["fixed"]
    evt = fzc._evt_tuple(cfg, meta)
    with tempfile.TemporaryDirectory(prefix="f7a_") as td:
        img = Path(td) / "img.hex"
        out = Path(td) / "out.txt"
        img.write_text("\n".join(f"{b:02x}" for b in bytes(image) * 16) + "\n")
        args = [str(check_seq.BIN), f"+bootimg={img}", "+bootn=4200",
                f"+waits={fixed}", f"+out={out}"]
        if wrand:
            args += ["+wrand=1", f"+wmax={wrand[0]}", f"+wseed={wrand[1]:04x}"]
        if evt:
            a, d, ho, p = evt
            args += [f"+evaddr={a:05x}", f"+evdelay={d}", f"+evhold={ho}",
                     f"+evpin={p}"]
        r = subprocess.run(args, capture_output=True, text=True, cwd=ROOT,
                           timeout=120)
        for ln in (r.stdout + r.stderr).splitlines():
            if "COLD-ARM VIOLATION" in ln:
                return ln.strip()
    return "none (no assertion)"


def _cap_chip(image, cfg, meta, use_core, tag):
    w = cfg["waits"]
    wrand = (w["wmax"], w["wseed"]) if w["wrand"] else None
    fixed = 0 if w["wrand"] else w["fixed"]
    evt = fzc._evt_tuple(cfg, meta)
    ck = CACHE / f"f7a_{tag}.json"
    if ck.exists():
        return json.loads(ck.read_text())
    rows = check_seq.run_chip(image, HOST, use_core=use_core, waits=fixed,
                              evt=evt, wrand=wrand)
    slim = [{"t": r.get("t_state", r.get("t")), "bs_early": r["bs_early"],
             "qs": r["qs"], "ube_n": r["ube_n"], "ad_addr": r["ad_addr"],
             "ad_data": r["ad_data"], "ps": r["ps"], "rst": r.get("rst", 0)}
            for r in rows]
    ck.write_text(json.dumps(slim))
    return slim


def main():
    engine = AcceptEngine.load()
    verdicts = []
    try:
        for k, ov, label in CASES:
            cfg = fzc.derive_case("PILOT", k, ov)
            g = fzc.build(cfg)
            image, meta = check_seq.compose(g)
            aline = tb_assert_line(image, cfg, meta)
            print(f"\n== k={k} [{label}] cfg_hash={cfg['cfg_hash']} ==")
            print(f"  TB: {aline}")
            try:
                chip = _cap_chip(image, cfg, meta, False, f"{k}_chip")
                fab = _cap_chip(image, cfg, meta, True, f"{k}_fab")
            except RunError as e:
                print(f"  BOARD RunError -> STOP (no retry into a wedge): {e}")
                return 2
            w = cfg["waits"]
            ctx = fc.Ctx(tier="A", waits=0 if w["wrand"] else w["fixed"],
                         wrand=w["wrand"], real_is_chip=True,
                         brkem_pos=g.get("brkem_pos", []),
                         seed=f"PILOT/{k}", cid="PILOT", cfg_hash=cfg["cfg_hash"])
            v = fc.classify(chip, fab, ctx, engine=engine)
            func_clean = v.verdict in (fc.SUCCESS, fc.TIMING, fc.KNOWN_ACCEPTED)
            print(f"  chip-vs-fabric: {v.verdict}/{v.sub} "
                  f"func_mismatch={v.func_mismatch} bad_rows={v.bad_rows} "
                  f"-> {'MATCH' if func_clean and not v.func_mismatch else 'DIVERGE'}")
            verdicts.append((k, label, v.verdict, v.func_mismatch, func_clean))
    finally:
        try:
            check_seq.run_chip(check_seq.compose(fzc.build(
                fzc.derive_case("PILOT", 0,
                                {"force_tier": "soup", "force_contained": True,
                                 "strict": True, "w0": True, "no_evt": True})))[0],
                HOST, use_core=False)
        except Exception as e:                          # noqa: BLE001
            print(f"  (post-run use_core=0 note: {e})")

    print("\n=== ARBITRATION SUMMARY ===")
    diverge = [x for x in verdicts if x[3] or not x[4]]
    for k, label, verd, fm, fc_clean in verdicts:
        print(f"  k={k} [{label}]: {verd} "
              f"{'DIVERGE' if fm or not fc_clean else 'MATCH (func-clean)'}")
    if diverge:
        print(f"\nVERDICT: DIVERGE on {len(diverge)} case(s) - REAL BUG, do not "
              f"widen the invariant. STOP and report forensics.")
        return 1
    print("\nVERDICT: MATCH on all cases - the F7a invariant is OVER-NARROW "
          "(fabric behaviour is chip-correct). Widen its guard (sim-only).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
