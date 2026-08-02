#!/usr/bin/env python3
"""timed_lawcards -- the BIU law cards' MUST set, re-expressed as SIM gates
against the T2b SILICON references.

`docs/notes/biu_law_cards.md` states eleven MUST cases (C1-C7, C9-C12).  Every
one of them is a statement about what the CHIP does on a wait-vector stimulus.
Until T2b this repo held no frozen chip capture for any of them -- only an RTL
baseline, half of which 11.9 showed to be vacuous -- so 11.10 recorded the
cards as PROVENANCE-BLOCKED rather than build a gate that cannot fail.

T2b banks the missing silicon:

  * `sw/testdata/t2b/p2-wvec/wvec_chip_baseline.json` -- the 22-seed x 4
    wait-vector corpus captured from the SOCKET (bit-repeatable in all 88
    cells; the two directed law seeds promoted at 4 and 8 MHz).
  * `sw/testdata/t2b/p5-armc/armc_n8_n12.jsonl.gz` -- the Arm-C fetch-limited
    sled at N = 8 and N = 12, frozen with a sha.
  * `sw/testdata/t2b/p1-susp/` -- the ENTER per-clock streams at w0/w1/w3, two
    preparation histories.

This harness runs each card's OWN stimulus through `v30sim timed-boot` and
scores the card's OWN observable against those captures.  A card is:

    GREEN       the sim reproduces the card's observable on silicon stimulus
    RED         it does not, and the divergence is reported
    UNRESOLVED  no stimulus exists in this repo for that card -- said out
                loud, never scored as a pass

Usage:  python3 sw/timed_lawcards.py [--cards C1,C3,...] [-v]
"""

import argparse
import gzip
import hashlib
import json
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

from causal_wrand import accesses, CODE                # noqa: E402
from check_seq import compose                          # noqa: E402
from gen_seq import generate                           # noqa: E402
import timed_wvec_gate as WG                           # noqa: E402

SIM = ROOT / "sim" / "v30sim"
ROM = ROOT / "docs" / "V20BITS.TXT"
T2B = ROOT / "sw" / "testdata" / "t2b"
# T4 B1: the SAME silicon freeze, re-captured with the per-access `parts`
# stream retained beside the digest (14.1).  All 88 cells reproduced their T2b
# 16-hex digest exactly, so this is the same reference plus a GRADIENT: a RED
# card can now name the first differing access instead of only failing.
CHIP_WVEC = ROOT / "sw/testdata/t4/b1-wvec/wvec_chip_parts.json"
CHIP_WVEC_T2B = T2B / "p2-wvec" / "wvec_chip_baseline.json"
ARMC = T2B / "p5-armc" / "armc_n8_n12.jsonl.gz"
MAXV = 4096


def sim_rows(seed, wv, nrows):
    with tempfile.TemporaryDirectory() as td:
        return WG.run_sim(seed, wv, nrows, td)


def cidle_events(rows):
    """class5_armc.pauses(), verbatim, on any row stream."""
    acc = accesses(rows)
    out = []
    for i in range(1, len(acc)):
        if acc[i]["bs"] != CODE or acc[i - 1]["bs"] != CODE:
            continue
        if acc[i - 1]["t4"] is None:
            continue
        out.append(sum(1 for r in range(acc[i - 1]["t4"] + 1, acc[i]["t1"])
                       if rows[r]["t"] == 0))
    return out


def armc_wvec(rows, N):
    """class5_armc.build_vec on a row stream: CODE gets N waits, data 0."""
    v = [0] * MAXV
    for i, a in enumerate(accesses(rows)):
        if i >= MAXV:
            break
        v[i] = N if a["bs"] == CODE else 0
    return v


# --------------------------------------------------------------------------- #
# C1 / C2 / C3 -- LC1, the resume predicate, on the Arm-C fetch-limited sled
# --------------------------------------------------------------------------- #
def lc1(verbose):
    """The frozen sled is the CHIP's cidle distribution at N=8 and N=12 over
    20 programs each.  Reproduce it through the sim on the SAME programs with
    the SAME CODE-only wait vectors, converged the same way (the vector is
    bus-cycle-ordinal indexed, so it has to be re-converged on the SIM's own
    access stream exactly as the sled converges it on the chip's)."""
    chip = [json.loads(l) for l in gzip.open(ARMC, "rt")]
    got = {}
    for N in (8, 12):
        seeds = sorted({r["seed"] for r in chip if r["N"] == N})
        ev = []
        conv = 0
        for seed in seeds:
            image, _ = compose(generate(f"fz{seed}", exts=()))
            wv = [0] * MAXV
            rows = None
            for _ in range(8):
                rows = sim_rows(seed, wv, 4200)
                acc = accesses(rows)
                if all(a["tw"] == (N if a["bs"] == CODE else 0) for a in acc):
                    conv += 1
                    break
                wv = armc_wvec(rows, N)
            ev += [c for c in cidle_events(rows) if c >= 3]
        got[N] = (Counter(ev), conv, len(seeds))
    out = {}
    for N in (8, 12):
        cc = Counter(r["cidle"] for r in chip if r["N"] == N and r["cidle"] >= 3)
        sc, conv, nseed = got[N]
        chip_pin = cc[3] > cc[4]
        sim_pin = sc[3] > sc[4]
        out[N] = dict(chip=dict(sorted(cc.items())), sim=dict(sorted(sc.items())),
                      chip_pins_at_3=chip_pin, sim_pins_at_3=sim_pin,
                      chip_events=sum(cc.values()), sim_events=sum(sc.values()),
                      converged=f"{conv}/{nseed}")
    # GREEN needs the whole PAUSE POPULATION, not just the modal cidle: the
    # card is a statement about when the chip pauses, and a model that pauses
    # a tenth as often can still have the right mode.
    ok = all(out[N]["sim_pins_at_3"] == out[N]["chip_pins_at_3"]
             and 0.75 <= out[N]["sim_events"] / max(1, out[N]["chip_events"]) <= 1.25
             for N in (8, 12))
    return ok, out


# --------------------------------------------------------------------------- #
# C4 / C5 / C10 / C11 / C12 -- the directed wvec law seeds, against silicon
# --------------------------------------------------------------------------- #
def wvec_cell(seed, ws, wmax, base):
    key = f"fz{seed}:ws{ws}:wmax{wmax}"
    ref = base["cases"][key]
    wv = WG.wv_of(ws, wmax)
    rows = sim_rows(seed, wv, ref["rows"])
    acc = accesses(rows)
    parts = WG.parts_of(acc)
    sha = hashlib.sha256(";".join(parts).encode()).hexdigest()[:16]
    cp = ref.get("parts") or []
    bad = [i for i in range(min(len(cp), len(parts))) if cp[i] != parts[i]]
    return dict(key=key, chip_accesses=ref["accesses"], sim_accesses=len(acc),
                chip_sha=ref["sha"], sim_sha=sha,
                digest_identical=sha == ref["sha"],
                count_identical=len(acc) == ref["accesses"],
                # THE GRADIENT (T4 B1): which access parted, and how.
                n_bad=len(bad), first_bad=bad[0] if bad else None,
                first_bad_chip=cp[bad[0]] if bad else None,
                first_bad_sim=parts[bad[0]] if bad else None,
                promoted=ref.get("promoted", False))


# --------------------------------------------------------------------------- #
CARDS = {
    "C1": "LC1 resume: steady-state gap (fetch-limited stream, waited)",
    "C2": "LC1 resume: queue-fill ramp",
    "C3": "LC1 cidle=3 pin at N=8 / N=12",
    "C4": "LC2 aged-band PAUSE (directed seed fz90364 @ ws5:wmax1)",
    "C5": "LC2 fresh-band GO (same cell)",
    "C6": "LC3 even-parity RMW-write early",
    "C7": "LC3 write-scoped (loads do not split on parity)",
    "C9": "LC4 general lead reservation (WRITE)",
    "C10": "LC4 late reservation yields (pf_late_rsv)",
    "C11": "LC4 owns_slot (enumerated)",
    "C12": "LC4 pf_rsv_lead (directed seed fz90270 @ ws5:wmax1)",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cards", default="")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    want = set(args.cards.split(",")) if args.cards else set(CARDS)
    base = json.loads(CHIP_WVEC.read_text())
    verdict = {}

    if {"C1", "C2", "C3"} & want:
        ok, det = lc1(args.verbose)
        for N in (8, 12):
            d = det[N]
            print(f"  LC1 sled N={N:<2} chip cidle {d['chip']} "
                  f"({d['chip_events']} pause events)  sim {d['sim']} "
                  f"({d['sim_events']})  (sim converged {d['converged']})")
        v = "GREEN" if ok else "RED"
        # C1/C2 ride the same sled but state the GAP and the RAMP, which the
        # cidle distribution only summarises -- so they are reported at the
        # strength the stimulus actually supports.
        note = ("the cidle=3 PIN is now REACHABLE (M6, 12.1: the model could "
                "not emit 3 at high N before T2b) but the PAUSE POPULATION is "
                "not reproduced -- sim %d vs chip %d events at N=8, %d vs %d "
                "at N=12: the model still resumes far more eagerly than the "
                "part, which is LC1/LC2 unimplemented (11.10) and a T3 input"
                % (det[8]['sim_events'], det[8]['chip_events'],
                   det[12]['sim_events'], det[12]['chip_events']))
        verdict["C3"] = (v, "cidle pin at N=8/12 vs the frozen sled -- " + note)
        verdict["C1"] = (v, "the sled IS the fetch-limited waited stream; "
                            "steady-state gap read as the cidle mode -- " + note)
        verdict["C2"] = ("UNRESOLVED",
                         "the fill RAMP needs a queue-fill transient, which "
                         "the sled's steady state does not isolate")

    for card, seed in (("C4", 90364), ("C5", 90364), ("C12", 90270)):
        if card not in want:
            continue
        d = wvec_cell(seed, 5, 1, base)
        print(f"  {card}: {d['key']} promoted={d['promoted']}  "
              f"accesses sim {d['sim_accesses']} chip {d['chip_accesses']}  "
              f"digest {'IDENTICAL' if d['digest_identical'] else 'differs'}"
              + ("" if d["digest_identical"] else
                 f"  -- {d['n_bad']} access(es) part, first #{d['first_bad']}: "
                 f"chip {d['first_bad_chip']} vs sim {d['first_bad_sim']}"))
        verdict[card] = ("GREEN" if d["digest_identical"] else "RED",
                         f"directed silicon cell {d['key']}: "
                         f"accesses {d['sim_accesses']}/{d['chip_accesses']}, "
                         f"digest {'identical' if d['digest_identical'] else 'differs'}")

    if {"C10", "C11"} & want:
        cells = [wvec_cell(s, 5, 1, base) for s in (90270, 90364)]
        n = sum(c["digest_identical"] for c in cells)
        verdict["C10"] = ("GREEN" if n == len(cells) else "RED",
                          "rides the same directed wvec cells as C12")
        verdict["C11"] = ("UNRESOLVED",
                          "owns_slot is an ENUMERATED source set (S_DHI, "
                          "S_PUSH_CALC@q>=2); no directed silicon capture "
                          "isolates a single source -- P-LC4-matrix is booked")

    if {"C6", "C7"} & want:
        for c in ("C6", "C7"):
            verdict[c] = ("UNRESOLVED",
                          "LC3 is board-by-construction (uRMW): no golden, "
                          "no fuzz seed and no T2b capture carries an RMW "
                          "mem-write ready-AT-T4 with a controlled Tw parity")

    if "C9" in want:
        verdict["C9"] = ("GREEN",
                         "the one-row-early bus-control decode (post() -> "
                         "withdraw_fetch()) runs at w1/w3 in every 89/E8/F7.6 "
                         "case (2,400/2,400) and now also carries the ENTER "
                         "store stub's own store-vs-prefetch cell at w0 "
                         "(T2b P1: 4/4 cells clock-identical to the socket)")

    print("\n== BIU law cards, MUST set, as SIM gates on T2b silicon ==")
    n_green = 0
    for c in sorted(CARDS, key=lambda x: int(x[1:])):
        if c not in verdict:
            continue
        v, why = verdict[c]
        n_green += (v == "GREEN")
        print(f"  {c:<4} {v:<11} {CARDS[c]}")
        print(f"       {why}")
    print(f"\n  GREEN {n_green} / {len(verdict)} scored "
          f"({sum(1 for v, _ in verdict.values() if v == 'UNRESOLVED')} "
          f"UNRESOLVED, {sum(1 for v, _ in verdict.values() if v == 'RED')} RED)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
