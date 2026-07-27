#!/usr/bin/env python3
"""fuzz_campaign - orchestrator for the massive fuzz expansion (task #29).

Phase 1 ships ONLY the `lint` subcommand: a generation-only safety scan that
proves the Tier A (gen_soup) and Tier B (gen_raw) generators can never hand the
board a chip-wedging image. The full driver (new/run/status/show/replay board
loop) lands in Phase 4.

Everything the driver will need is reproducible from `(campaign_id, k)` alone
via the namespaced seed->config derivation (§seed->config): `cfg/<cid>/<k>`
draws the axes (tier, event pin/delay/hold, wait mode), and the program itself
seeds off `soup/<cid>/<k>` or `raw/<cid>/<k>` inside the generators. `lint`
exercises that real derivation path so a drift in it is caught here, not on the
board.

lint asserts, over N seeds each tier:
  * soup: the assembled CODE stream carries no banned 0F pair, no banned group
    /reg ext (FE /2-7, 8E /1, FF /7), and no I/O to the forbidden 0xFC/0xFE
    ports (random DATA windows are not scanned - they are never fetched);
  * raw : the whole composed image below the reserved page (0x0000-0xFEFF)
    carries no residual 0F lockup pair and no stray HALT(F4)/POLL(9B) - i.e.
    the mandatory scrub pass held;
  * both: testimage.compose() succeeds.
"""
import argparse
import random
import sys
import time
from pathlib import Path

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
import check_seq                                      # noqa: E402
import optable                                        # noqa: E402
from gen_soup import gen_soup                          # noqa: E402
from gen_raw import gen_raw                            # noqa: E402

RESERVED_LO = 0xFF00     # raw scan covers 0x0000 .. RESERVED_LO-1
NMIN, NMAX = 24, 80


# ---------------------------------------------------------------------------
# Seed -> config derivation (bit-reproducible from (cid, k)).
# ---------------------------------------------------------------------------
def derive_axes(cid, k):
    """Draw the per-seed axes from the `cfg/<cid>/<k>` namespace."""
    r = random.Random(f"cfg/{cid}/{k}")
    tier = "raw" if r.random() < 0.20 else "soup"

    evt = None
    if r.random() < 0.25:
        x = r.random()
        pin = 0 if x < 0.70 else (1 if x < 0.95 else 2)   # INT / NMI / POLL
        if tier == "raw" and pin == 2:                    # POLL is soup-only
            pin = 0
        delay = int(round(8 * (2048 / 8) ** r.random()))  # log-uniform 8..2048
        evt = {"pin": pin, "delay": delay, "hold": 2}

    if r.random() < 0.50:
        wmax = r.choices([1, 2, 3, 7, 15], weights=[30, 25, 20, 15, 10])[0]
        waits = {"wrand": True, "wmax": wmax, "wseed": r.getrandbits(16),
                 "fixed": None}
        weff = wmax
    else:
        w = r.choices([0, 1, 2, 3], weights=[70, 10, 10, 10])[0]
        waits = {"wrand": False, "wmax": None, "wseed": None, "fixed": w}
        weff = w

    # capture-budget coupling: fewer instructions as waits stretch each access
    nmax_eff = max(NMIN, int(NMAX * 4 / (4 + weff)))
    return {"cid": cid, "k": k, "tier": tier, "evt": evt, "waits": waits,
            "nmin": NMIN, "nmax_eff": nmax_eff}


def build(cfg, force_tier=None):
    """Materialise the g-dict for a derived config. force_tier overrides the
    drawn tier (lint runs dedicated soup/raw passes over the derived axes)."""
    tier = force_tier or cfg["tier"]
    seed = f"{cfg['cid']}/{cfg['k']}"
    if tier == "raw":
        g = gen_raw(seed)
    else:
        pin = cfg["evt"]["pin"] if cfg["evt"] else None
        g = gen_soup(seed, nmin=cfg["nmin"], nmax=cfg["nmax_eff"], evt_pin=pin)
    # hold finalisation: a HALT/POLL seed needs the long level-hold to wake
    if cfg["evt"] and g.get("has_halt"):
        cfg["evt"]["hold"] = 300
    return g, tier


# ---------------------------------------------------------------------------
# lint subcommand.
# ---------------------------------------------------------------------------
def _lint_soup(cid, n, report_every):
    hits = comp_err = wild = brkem = halt = tf = 0
    t0 = time.time()
    for k in range(n):
        cfg = derive_axes(cid, k)
        g, _ = build(cfg, force_tier="soup")
        wild += g["wild"]
        brkem += bool(g["brkem_pos"])
        halt += g["has_halt"]
        tf += g["has_tf"]
        vio = optable.scan_code(g["instr"])
        if vio:
            hits += len(vio)
            print(f"  SOUP HIT seed soup/{cid}/{k}: {vio[:4]}")
        # well-formedness: the static ilen walk must reproduce the generator's
        # own instruction boundaries exactly (catches malformed multi-byte emits)
        off = 0
        for ins in g["ins"]:
            if optable.ilen(g["instr"], off) != len(ins):
                hits += 1
                print(f"  SOUP MALFORMED soup/{cid}/{k} @off {off}: "
                      f"ilen={optable.ilen(g['instr'], off)} real={len(ins)} "
                      f"{g['instr'][off:off + 6].hex()}")
                break
            off += len(ins)
        try:
            check_seq.compose(g)
        except Exception as e:                        # noqa: BLE001
            comp_err += 1
            if comp_err <= 5:
                print(f"  SOUP COMPOSE ERR soup/{cid}/{k}: {e!r}")
        if report_every and (k + 1) % report_every == 0:
            rate = (k + 1) / (time.time() - t0)
            print(f"  soup {k + 1}/{n}  ({rate:.0f}/s)  hits={hits} "
                  f"comp_err={comp_err}", flush=True)
    dt = time.time() - t0
    print(f"soup: {n} seeds in {dt:.1f}s ({n / dt:.0f}/s) | "
          f"wild={wild} brkem={brkem} halt={halt} tf={tf} | "
          f"hits={hits} compose_err={comp_err}")
    return hits, comp_err


def _lint_raw(cid, n, report_every):
    hits = comp_err = whole = payload = ivt_iret = 0
    scrub_tot = {"pair0f": 0, "halt": 0, "poll": 0}
    t0 = time.time()
    for k in range(n):
        cfg = derive_axes(cid, k)
        g, _ = build(cfg, force_tier="raw")
        whole += g["raw_mode"] == "whole"
        payload += g["raw_mode"] == "payload"
        ivt_iret += g["ivt_mode"] == "iret"
        for key in scrub_tot:
            scrub_tot[key] += g["scrubbed"][key]
        try:
            img, _meta = check_seq.compose(g)
        except Exception as e:                        # noqa: BLE001
            comp_err += 1
            if comp_err <= 5:
                print(f"  RAW COMPOSE ERR raw/{cid}/{k}: {e!r}")
            continue
        vio = optable.scan_raw_bytes(img[:RESERVED_LO])
        if vio:
            hits += len(vio)
            print(f"  RAW HIT seed raw/{cid}/{k} mode={g['raw_mode']}: {vio[:4]}")
        if report_every and (k + 1) % report_every == 0:
            rate = (k + 1) / (time.time() - t0)
            print(f"  raw {k + 1}/{n}  ({rate:.0f}/s)  hits={hits} "
                  f"comp_err={comp_err}", flush=True)
    dt = time.time() - t0
    print(f"raw: {n} seeds in {dt:.1f}s ({n / dt:.0f}/s) | "
          f"whole={whole} payload={payload} ivt_iret={ivt_iret} | "
          f"scrub_totals={scrub_tot} | hits={hits} compose_err={comp_err}")
    return hits, comp_err


def cmd_lint(args):
    print(f"fuzz lint: cid={args.cid} soup_n={args.n} raw_n={args.raw_n}")
    sh, sc = _lint_soup(args.cid, args.n, args.report_every)
    rh, rc = _lint_raw(args.cid, args.raw_n, args.report_every)
    total = sh + sc + rh + rc
    print(f"\nLINT {'PASS' if total == 0 else 'FAIL'}: "
          f"soup hits={sh} compose_err={sc}; raw hits={rh} compose_err={rc}")
    return 0 if total == 0 else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    lp = sub.add_parser("lint", help="generation-only safety scan")
    lp.add_argument("--cid", default="lint", help="campaign id for derivation")
    lp.add_argument("--n", type=int, default=10000, help="soup seed count")
    lp.add_argument("--raw-n", type=int, default=100000, help="raw seed count")
    lp.add_argument("--report-every", type=int, default=0,
                    help="progress line cadence (0 = quiet until the tail)")
    lp.set_defaults(func=cmd_lint)
    a = ap.parse_args()
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
