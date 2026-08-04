#!/usr/bin/env python3
"""sm3_sig_admit -- ADMIT the INV-1 re-capture's TIMING signatures to the
novelty ledger (SM3 item 0).

SM2 left `check_fuzz_bank --strict` FAILING on `new-sig TIMING 166` and
deliberately did NOT edit `tests/v30/fuzz_bank/sig_ledger.json`, because
admitting signatures to a NOVELTY register in order to turn a warning green is a
decision about what "novel" means for every future campaign
(`ucore_provenance.md` §59.7.13).  The decision was taken by the coordinator;
this is its execution, and it is deliberately a COMMITTED TOOL rather than an
ad-hoc edit, so the act is reproducible and its control is re-runnable.

**The control runs FIRST and the admission refuses without it.**  Every
signature admitted must come from a seed that carries a `recapture` block AND
banks `evt.hold == 300` with `evt.hold_bits == 12` -- i.e. a capture taken under
the directive the bank actually records.  A signature reachable from any other
seed is NOT an INV-1 consequence and is not admitted; the tool stops and says so.

Backward compatibility is a requirement, not a nicety: `check_fuzz_bank` reads
`set(json["sigs"])` and nothing else, so the admitted entries are ordinary
`sigs` entries in `fuzz_bank._update_ledger`'s own shape, with one extra
`admitted` key.  A reader that does not know about admissions is unaffected.
The event itself is recorded once under a new top-level `admissions` list.

  sm3_sigctl.py --jobs 8 --out ctl.json     # the control (a full bank replay)
  sm3_sig_admit.py --ctl ctl.json [--apply]  # dry-run unless --apply
"""
import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
import fuzz_classify as fc                              # noqa: E402

LEDGER = SW.parent / "tests" / "v30" / "fuzz_bank" / "sig_ledger.json"

WHY = ("INV-1 re-capture (SM2, 2026-08-04): the 760 EVT seeds whose banked "
       "evt.hold of 300 the 8-bit rig truncated to 44 were re-captured on "
       "FLASH #4 at a TRUE 300-clock hold.  372 of them moved FUNCTIONAL -> "
       "TIMING, and a seed that was never TIMING never had a TIMING signature "
       "in this ledger -- so these signatures are novel to the REGISTER and "
       "not to the machine.  They are the first observations of the part "
       "entering its interrupt handler 2-5 times under a level it was never "
       "physically given before.")

# SM3 sitting 7.  A SECOND admissible cause, with its OWN control.  The tool
# refuses to write without a control, and the right response to a new cause is
# a new control -- not a weaker one.  `--cause` selects which, and the two
# controls are computed by two different tools over two different artifacts.
WHY_IOW = ("tb_v30_core IOW-store defect fixed (ucore_provenance.md §66.3 / "
           "§67.1): the testbench's memory commit was gated on `lat_write`, "
           "which includes 3'b010 = IOW, so an I/O write to port P stored into "
           "mem[P] for the RTL legs only.  The socket harness never did this "
           "and `sim/` never did this, which is how the defect was found.  "
           "With the commit restricted to MEMW, FIVE banked seeds replay to a "
           "BETTER verdict on the FSM leg this gate binds to, and a better "
           "verdict carries a different signature.  The signatures are novel "
           "to the REGISTER and not to the machine: nothing regressed "
           "(`worse 0`, `gen_drift 0`), and every one of them is reachable "
           "only from a seed the defect could touch.")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ctl", required=True,
                    help="sm3_sigctl.py --out artifact (the per-seed control)")
    ap.add_argument("--apply", action="store_true",
                    help="write the ledger (default: dry-run)")
    ap.add_argument("--date", default="2026-08-04")
    ap.add_argument("--cause", default="inv1", choices=("inv1", "iow"),
                    help="which admissible cause, and therefore which CONTROL "
                         "gates the write.  `inv1` (default): the seed carries "
                         "a recapture block with evt.hold==300 and "
                         "hold_bits==12.  `iow`: the seed is in the chip-side "
                         "IOW population (`sw/sm3_iowpop.py --out`, named by "
                         "--pop).")
    ap.add_argument("--pop", default="",
                    help="sm3_iowpop.py --out artifact; required for "
                         "--cause iow")
    a = ap.parse_args()

    ctl = json.loads(Path(a.ctl).read_text())
    led = json.loads(LEDGER.read_text())
    known = set(led["sigs"])

    new = [r for r in ctl["recs"] if r.get("new_sig")]
    if not new:
        print("nothing to admit"); return 1

    # --- THE CONTROL.  It gates the write. --------------------------------- #
    if a.cause == "inv1":
        why, ctl_txt = WHY, (
            "every admitted signature is reachable ONLY from a seed carrying "
            "a `recapture` block with evt.hold == 300 and evt.hold_bits == 12; "
            "0 from any other banked seed (sw/sm3_sigctl.py, full 3,242-seed "
            "replay)")
        bad = [r for r in new
               if not (r["recaptured"] and r.get("evt_hold") == 300
                       and r.get("evt_hold_bits") == 12)]
        label = "a true-300 / 12-bit re-captured seed"
    else:
        if not a.pop:
            print("--cause iow requires --pop (sm3_iowpop.py --out)")
            return 2
        pop = json.loads(Path(a.pop).read_text())
        popset = set(pop["paths"])
        why = WHY_IOW
        ctl_txt = (
            "every admitted signature is reachable ONLY from a seed in the "
            f"chip-side IOW population ({len(popset)} of {pop['n_bank']} "
            "banked seeds: the chip rows contain an IOW cycle whose port "
            "number is later read as memory).  The population is derived from "
            "the CAPTURES alone -- no engine, no testbench -- because the "
            "defect was in a replay instrument and a population defined by "
            "that instrument would be circular (sw/sm3_iowpop.py)")
        bad = [r for r in new if r["path"] not in popset]
        label = "the chip-side IOW population"
    print(f"control ({a.cause}): {len(new)} new-sig TIMING seeds, "
          f"{len({r['sig'] for r in new})} distinct signatures")
    print(f"  from {label:<42s}: {len(new) - len(bad)}")
    print(f"  from ANY OTHER seed                              : {len(bad)}")
    if bad:
        print(f"\nCONTROL FAILED -- these are not `{a.cause}` consequences "
              "and are NOT admitted:")
        for r in bad[:20]:
            print(f"   {r['path']}  hold={r.get('evt_hold')} "
                  f"bits={r.get('evt_hold_bits')} recap={r['recaptured']}")
        return 2
    stale = sorted({r["sig"] for r in new} & known)
    if stale:
        print(f"\nWARNING: {len(stale)} already present; not re-admitted")

    sigs = sorted({r["sig"] for r in new} - known)
    per = Counter(r["sig"] for r in new)
    first = {}
    for r in new:
        first.setdefault(r["sig"], r)
    print(f"\nto admit: {len(sigs)} signatures over {len(new)} seeds")
    print("  campaigns:", dict(Counter(r["campaign"] for r in new)))

    if not a.apply:
        print("\nDRY RUN -- pass --apply to write the ledger")
        return 0

    # --- the write ---------------------------------------------------------- #
    before = len(led["sigs"])
    before_hash = json.dumps(led["sigs"], sort_keys=True)
    for s in sigs:
        r = first[s]
        led["sigs"][s] = {
            "first_campaign": r["campaign"], "first_verdict": fc.TIMING,
            "klass": None, "tier": "raw" if r["seed"].startswith("raw") else
            ("soup" if r["seed"].startswith("soup") else "unknown"),
            "waits_class": ("recapture-evt" if a.cause == "inv1"
                            else "tb-iow-fix"),
            "count": per[s],
            "admitted": a.date,
        }
    led.setdefault("admissions", []).append({
        "date": a.date,
        "by": ("session SM3, item 0" if a.cause == "inv1"
               else "session SM3, sitting 7"),
        "cause": a.cause,
        "why": why,
        "seeds": len(new), "signatures": len(sigs),
        "control": ctl_txt,
        "gate_before": ("check_fuzz_bank --strict FAIL, new-sig TIMING 166"
                        if a.cause == "inv1" else
                        "check_fuzz_bank --strict FAIL, stable 3237 improved 5 "
                        "worse 0 gen_drift 0, new-sig TIMING 3"),
        "gate_after": "check_fuzz_bank --strict expected rc=0",
        "ledger_before": before, "ledger_after": len(led["sigs"]),
        "recorded": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sigs": sigs,
    })
    # a pre-existing entry must not have moved
    after = {k: v for k, v in led["sigs"].items() if k not in set(sigs)}
    if json.dumps(after, sort_keys=True) != before_hash:
        print("REFUSING: a pre-existing signature entry changed")
        return 3
    LEDGER.write_text(json.dumps(led, indent=1))
    print(f"\nwrote {LEDGER}:  sigs {before} -> {len(led['sigs'])}"
          f"  (+{len(sigs)}), 0 pre-existing entries touched")
    return 0


if __name__ == "__main__":
    sys.exit(main())
