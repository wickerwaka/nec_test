#!/usr/bin/env python3
"""s12_census -- the BOARD-FREE census session (ucsim_t_provenance 23).

OFFLINE.  No board, no new capture.  Every number is read off material that
was already on disk: the S10 banked captures (raw 64-bit words + rows), the
committed golden suites, and the fuzz bank.  NOT a gate -- a measurement tool.

  hltsweep   the S2 HLT delay sweep re-posed in a FIXED coordinate: the assert
             clock A and every event measured against the HALT DISPLAY clock,
             which 21.5 measured to be constant per program and independent of
             the delay.  The "~57-clock excursion" lives or dies here.
  psw        the emission instrument: `parse_result`'s PSW is read from the
             pass the DONE MARKER belongs to, and the old rule (`pushes[-1]`)
             read the last pass in the capture instead.  Scores both rules over
             every banked S10 capture at the emission cap and at full length.
  regold     re-derive the goldens the emission path could not produce, from
             the BANKED capture of the same image (truth source: the chip, but
             a banked chip run -- stated, not hidden).
  ackfam     the `ACK` first-divergence family of the EVT fuzz population,
             per seed, with the divergence context read off the CHIP capture.
"""
import argparse
import gzip
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

import emit_suite as es                                   # noqa: E402
import testimage                                          # noqa: E402
import v30run                                             # noqa: E402

S2 = ROOT / "sw" / "testdata" / "s10" / "s2-hltsweep"
S1 = ROOT / "sw" / "testdata" / "s10" / "s1-tranche"

BS = {0: "INTA", 1: "IOR", 2: "IOW", 3: "HALT", 4: "CODE", 5: "MEMR",
      6: "MEMW", 7: "PASV"}
QS = {0: "-", 1: "F", 2: "E", 3: "S"}
PASV = 7                                   # `bs_early` = nothing announced
HALT = 3


# --------------------------------------------------------------------------- #
# banked-capture helpers (chip only -- no model anywhere in this file)
# --------------------------------------------------------------------------- #
def raw_recs(path):
    """The decoded capture EXACTLY as `run_image` returns it (untrimmed)."""
    words = [int(l, 16) for l in gzip.open(path, "rt") if l.strip()]
    return v30run.decode_words(words)


def rows_of(path):
    return json.load(gzip.open(path))


def cycles(rows):
    """Bus cycles as dicts, DISPLAY-anchored, over `s10_board.capture` rows.

    THE ANCHORING RULE: a cycle is framed by what the part ANNOUNCED.  The
    display IS the status pulse (21.1), so one bus cycle is one contiguous run
    of the same non-`PASV` `bs_early`; `d` is the clock the status first
    appears and `t1` is the T1 row INSIDE that run -- or `None`, which is an
    announcement the part displayed and then never took a T1 for.

    This replaces a T1-anchored reading that was wrong at exactly one place
    (24.1, 24.15 item 12): the RIG's T-state counter keeps running THROUGH the
    HALT pseudo-cycle, so a woken prefetch whose display falls inside those
    T-states never gets a T1 of its own, and anchoring on `t == 1` could not
    see that cycle at all -- it walked to the next one (18 of the 296 banked
    sweep cells, every one of them in `A - H` in {-2 .. +1}: 9 walked to the
    acknowledge, 9 to the NEXT prefetch).  No HALT special case is needed: the
    same one rule frames every cycle in the corpus (199,282 status runs over
    the 296 banked captures, and not one of them carries a second T1).
    """
    out, i, n = [], 0, len(rows)
    while i < n:
        b = rows[i]["bs_early"]
        if b == PASV:                       # nothing announced on this clock
            i += 1
            continue
        j = i                               # the status pulse, end to end
        while j + 1 < n and rows[j + 1]["bs_early"] == b:
            j += 1
        t1 = next((k for k in range(i, j + 1) if rows[k]["t"] == 1), None)
        t4 = tw = None
        if t1 is not None:
            t4 = next((k for k in range(t1, n) if rows[k]["t"] == 5), None)
            tw = sum(1 for k in range(t1, t4 if t4 is not None else n)
                     if rows[k]["t"] == 4)
        out.append({"kind": BS[b], "d": i, "t1": t1, "t4": t4, "tw": tw or 0,
                    "addr": None if t1 is None else rows[t1]["ad_addr"]})
        i = j + 1
    return out


def case_of(form, seed_base, idx=None):
    """The sweep's / tranche's OWN case, regenerated from its own seed."""
    spec = es.EVT_FORMS[form]
    key = f"{seed_base}/{form}" if idx is None else f"{seed_base}/{form}/{idx}"
    case = es.gen_evt_case(spec, random.Random(key))
    nec = {es.INTEL2NEC[k]: v for k, v in case["regs"].items()}
    # fuzz-v2 T12: no `stub_linear=` -- there is no store stub to place.
    image, meta = testimage.compose(regs=nec, instr=case["instr"],
                                    ram=case["ram"], ivt=case["ivt"])
    return spec, case, image, meta


# --------------------------------------------------------------------------- #
# 1.  the HLT sweep in the HALT-DISPLAY coordinate
# --------------------------------------------------------------------------- #
def sweep_cells(form, waits):
    """-> list of per-delay measurements, all pins, no model."""
    spec, case, _, meta = case_of(form, "v30-s10-hlt")
    out = []
    for d in range(49):
        p = S2 / f"{form}_w{waits}_d{d}.rows.json.gz"
        if not p.exists():
            continue
        rows = rows_of(p)
        cyc = cycles(rows)
        anchor = next(c["t1"] for c in cyc
                      if c["kind"] == "CODE" and c["addr"] == meta["anchor_linear"])
        # the rig's own law (hdl/rtl/nec_bus.sv: arm on the anchor's CODE T1,
        # count `delay` clocks, stage the pin on the following tick_fall), i.e.
        # the clock the PART first samples the level.  Identical to the
        # `assert_cyc = t1 + 2 + delay_hw` the emission path already uses.
        A = anchor + 2 + d
        hd = next((i for i, r in enumerate(rows) if r["bs_early"] == HALT), None)
        hcyc = next((c for c in cyc if c["kind"] == "HALT"), None)
        inta = next((c for c in cyc if c["kind"] == "INTA"), None)
        # everything ANNOUNCED strictly after the HALT's own announcement.
        # (24.1: NOT "after the HALT pseudo-cycle's T4" -- the woken prefetch
        #  is displayed INSIDE those T-states and that framing walked past it.)
        post = [c for c in cyc
                if hcyc is not None and c["d"] > hcyc["d"]]
        first_post = post[0] if post else None
        woke = next((c for c in post if c["kind"] == "CODE"), None)
        out.append({
            "form": form, "waits": waits, "delay": d,
            "anchor_t1": anchor, "A": A,
            "halt_display": hd, "halt_t1": None if not hcyc else hcyc["t1"],
            "halt_t4": None if not hcyc else hcyc["t4"],
            "AH": None if hd is None else A - hd,
            "first_post_kind": None if not first_post else first_post["kind"],
            "first_post_d": None if not first_post else first_post["d"],
            "first_post_t1": None if not first_post else first_post["t1"],
            "woke_code_d": None if not woke else woke["d"],
            "woke_code_t1": None if not woke else woke["t1"],
            "inta1_d": None if not inta else inta["d"],
            "inta1_t1": None if not inta else inta["t1"],
        })
    return out


def cmd_hltsweep(args):
    print("=== S2 HLT sweep, re-posed against the HALT DISPLAY clock ===")
    print("(A = the clock the part first samples the asserted pin; H = the")
    print(" HALT status display clock, constant per program per 21.5)\n")
    allc = []
    for form in ("HLT.INT", "HLT.RES"):
        for w in (0, 1):
            cells = sweep_cells(form, w)
            allc += cells
            hs = {c["halt_display"] for c in cells if c["halt_display"] is not None}
            print(f"  {form} w{w}: H = {sorted(hs)}   anchor T1 = "
                  f"{sorted({c['anchor_t1'] for c in cells})}   "
                  f"H - anchor = {sorted({h - c['anchor_t1'] for h in hs for c in cells})[:3]}")
    print()
    # THRESHOLD 1 -- is the HALT status driven at all?
    print("  THRESHOLD 1: the HALT status is driven iff A - H >= ?")
    for form in ("HLT.INT", "HLT.RES"):
        for w in (0, 1):
            cells = [c for c in allc if c["form"] == form and c["waits"] == w]
            drv = [c for c in cells if c["halt_display"] is not None]
            nod = [c for c in cells if c["halt_display"] is None]
            H = drv[0]["halt_display"]
            lo = min(c["A"] - H for c in drv)
            hi = max(c["A"] - H for c in nod) if nod else None
            print(f"    {form:8s} w{w}: driven for A-H >= {lo:+d}  "
                  f"(not driven up to A-H = {hi:+d}); d* = "
                  f"{min(c['delay'] for c in drv)}, cells {len(drv)}/{len(cells)}")
    print()
    # THRESHOLD 2 -- what occupies the first bus slot after the HALT display.
    # Every clock below is a DISPLAY clock (21.1 / 24.1): D is the status
    # pulse, not the rig's T1.
    print("  THRESHOLD 2: the first bus cycle ANNOUNCED after the HALT display")
    print("    form     w   A-H   first-post    D-H   max(A+4,H+3)-H"
          "   T4(halt)-H   INTA1 D-H")
    for form in ("HLT.INT", "HLT.RES"):
        for w in (0, 1):
            cells = [c for c in allc
                     if c["form"] == form and c["waits"] == w
                     and c["halt_display"] is not None]
            seen = {}
            for c in cells:
                H = c["halt_display"]
                k = (c["AH"], c["first_post_kind"], c["first_post_d"] - H,
                     max(c["A"] + 4, H + 3) - H, c["halt_t4"] - H,
                     None if c["inta1_d"] is None else c["inta1_d"] - H)
                seen.setdefault(k, 0)
                seen[k] += 1
            for k in sorted(seen):
                if k[0] <= 3 or seen[k] > 1:
                    print(f"    {form:8s} {w}  {k[0]:+4d}   {k[1]:<9} "
                          f"{k[2]:+6d}   {k[3]:+12d}   {k[4]:+9d}   {k[5]}")
    print()
    # THRESHOLD 2, scored -- the woken fetch's DISPLAY against the law
    drv = [c for c in allc if c["halt_display"] is not None
           and c["woke_code_d"] is not None]
    off = [c for c in drv
           if c["woke_code_d"] != max(c["A"] + 4, c["halt_display"] + 3)]
    print(f"  THRESHOLD 2, scored: woken fetch DISPLAY == max(A+4, H+3) on "
          f"{len(drv) - len(off)}/{len(drv)} driven cells")
    for c in off:
        H = c["halt_display"]
        print(f"    OFF-LAW {c['form']} w{c['waits']} d{c['delay']} "
              f"A-H={c['AH']:+d}: D = H{c['woke_code_d']-H:+d}, law says "
              f"H{max(c['A']+4, H+3)-H:+d}")
    print()
    # THE EXCURSION, named
    print("  THE `woken fetch' METRIC (first CODE announced after H) vs the")
    print("  FIRST BUS CYCLE announced after H -- the 21.5 excursion, if any:")
    exc = 0
    for c in allc:
        if c["halt_display"] is None:
            continue
        H = c["halt_display"]
        if c["woke_code_d"] is not None and c["first_post_kind"] != "CODE":
            exc += 1
            print(f"    {c['form']} w{c['waits']} d{c['delay']:<3} A-H={c['AH']:+d}"
                  f"   first post = {c['first_post_kind']} at H{c['first_post_d']-H:+d}"
                  f"   but `woke CODE' = H{c['woke_code_d']-H:+d}"
                  f"  ->  metric jumps {c['woke_code_d']-c['first_post_d']} clocks")
    print(f"    -> {exc} cells")
    if args.dump:
        json.dump(allc, open(args.dump, "w"), indent=1)
        print(f"\n  dump -> {args.dump}")
    return 0


# --------------------------------------------------------------------------- #
# 2.  the emission instrument: which PASS the PSW is read from
# --------------------------------------------------------------------------- #
def _psw_rules(txns, meta):
    """RETIRED SUB-COMMAND (fuzz-v2 T12).  See `cmd_psw`.

    This measured which PASS of a re-running board image the emission PSW was
    read from, over the `MEMW @ psw_push_addr` channel.  fuzz-v2 D6 DELETED
    that channel: the terminator pops its own interrupt frame and emits PSW as
    an ordinary port write inside the dump, so there is exactly one PSW per
    run and the hazard this instrument existed to measure cannot occur."""
    raise RuntimeError(
        "s12_census psw IS RETIRED (fuzz-v2 T12): it reads "
        "meta['psw_push_addr'], the `MEMW @ 0xFFEC` channel that fuzz-v2 D6 "
        "deleted.  PSW is now a WORD IN THE RUN -- see v30run.parse_result -- "
        "so the multi-pass hazard it measured is structurally gone.  The other "
        "s12_census sub-commands (hltsweep / regold / ackfam) are unaffected.")
    K = v30run.KIND                                          # noqa: W0101
    done = [t for t in txns if K[t["kind"]] == "IOW"
            and (t["addr"] & 0xFFFF) == testimage.OUT_PORT_DONE]
    pushes = [t for t in txns if K[t["kind"]] == "MEMW"
              and t["addr"] == meta["psw_push_addr"]]
    old = pushes[-1]["data"] if pushes else None
    if not done:
        return old, "NODONE"
    d0 = done[0]["start"]
    inpass = [t for t in pushes if t["start"] < d0]
    return old, (inpass[-1]["data"] if inpass else None)


def _plausible(v):
    return isinstance(v, int) and (v & 0xF002) == 0xF002 and (v & 0x0028) == 0


def banked_captures():
    """(label, raw path, meta) for every retained S10 capture."""
    for form in ("HLT.INT", "HLT.RES"):
        _, _, _, meta = case_of(form, "v30-s10-hlt")
        for w in (0, 1):
            for d in range(49):
                p = S2 / f"{form}_w{w}_d{d}.raw.hex.gz"
                if p.exists():
                    yield (f"{form}_w{w}_d{d}", p, meta)
    for form in es.EVT_FORMS:
        for w in (1, 3):
            for idx in (0, 2):
                p = S1 / f"{form}_w{w}_{idx}.raw.hex.gz"
                if not p.exists():
                    continue
                _, _, _, meta = case_of(form, f"v30-s10-w{w}evt", idx)
                yield (f"{form}_w{w}_{idx}", p, meta)


def cmd_psw(args):
    print("=== the emission PSW rule, over every banked S10 capture ===")
    print("  old = the last write to psw_push_addr in the CAPTURE")
    print("  new = the last write to psw_push_addr BEFORE the done marker\n")
    tab = Counter()
    diff = []
    n = 0
    for label, p, meta in banked_captures():
        recs = raw_recs(p)
        n += 1
        for cap in (es.EMIT_CAP, es.EMIT_CAP_RETRY):
            txns = v30run.extract_txns_large(recs[:cap])
            old, new = _psw_rules(txns, meta)
            tab[(cap, _plausible(old), _plausible(new), old == new)] += 1
            if old != new and _plausible(old) and _plausible(new):
                diff.append((label, cap, old, new))
    print(f"  captures: {n}")
    print("   cap   old-plausible  new-plausible  identical   n")
    for k in sorted(tab):
        print(f"  {k[0]:5d}   {str(k[1]):<13} {str(k[2]):<13}  {str(k[3]):<9}  {tab[k]}")
    print("\n  PLAUSIBLE-BUT-DIFFERENT (the old rule silently returned another"
          " pass's PSW):")
    for d in diff:
        print(f"    {d[0]} cap={d[1]}  old={d[2]:#06x}  new={d[3]:#06x}")
    return 0


# --------------------------------------------------------------------------- #
# 3.  re-derive the goldens the emission path could not produce
# --------------------------------------------------------------------------- #
def cmd_regold(args):
    """Rebuild <form>.json.gz for the S2 sweep from the BANKED captures.

    PROVENANCE: the truth source is the socketed chip at div=8 with the S10
    manifest's recorded raw sha -- but it is a BANKED run, re-parsed offline,
    not a new board sitting.  The suite's emit_log records exactly that.
    """
    form, waits = args.form, args.waits
    spec, _, _, _ = case_of(form, "v30-s10-hlt")
    sd = ROOT / "tests" / "v30" / f"s10-hltsweep-w{waits}"
    sd.mkdir(parents=True, exist_ok=True)
    tests, bad = [], []
    for d in range(49):
        p = S2 / f"{form}_w{waits}_d{d}.raw.hex.gz"
        if not p.exists():
            bad.append((d, "no banked capture"))
            continue
        _, case, _, _ = case_of(form, "v30-s10-hlt")
        case["delay"] = d
        recs = raw_recs(p)
        try:
            t = es.emit_evt_case(spec, case, None, tag="s12regold",
                                 preload_n=0, waits=waits, recs_in=recs)
        except (es.ComposeError, es.RunError) as e:
            bad.append((d, str(e)))
            continue
        t["idx"] = d
        tests.append(t)
    print(f"  {form} w{waits}: {len(tests)}/49 goldens re-derived")
    for d, why in bad:
        print(f"    d={d}: {why}")
    if args.write and tests:
        with gzip.open(sd / f"{form}.json.gz", "wt") as f:
            json.dump(tests, f, separators=(",", ":"))
        with (sd / "emit_log.txt").open("a") as f:
            f.write(f"# TRUTH SOURCE: SOCKET (real chip, use_core=False), "
                    f"RE-DERIVED OFFLINE from the BANKED S10 capture "
                    f"sw/testdata/s10/s2-hltsweep/{form}_w{waits}_d*.raw.hex.gz "
                    f"(div=8, 4 MHz; sha in that directory's manifest.json).  "
                    f"No board contact.  {len(tests)}/49 cases.  "
                    f"See ucsim_t_provenance.md 23.1\n")
        print(f"  wrote {sd/f'{form}.json.gz'}")
    return 0


# --------------------------------------------------------------------------- #
# 4.  the `ACK` first-divergence family, per seed
# --------------------------------------------------------------------------- #
def cmd_ackfam(args):
    import fuzz_classify as fc
    import ucsim_fuzz as uf
    res = json.load(open(args.report))
    rows = []
    for r in res:
        if r["cat"] != "DIVERGE":
            continue
        entry = json.loads(gzip.decompress(Path(r["path"]).read_bytes()))
        recs = entry["chip_rows"]
        win = uf.window_of(recs)
        inta, halt = [], []
        prev = None
        for t in fc.extract_txns(recs):
            if t["start"] >= win:
                break
            k = fc.KIND[t["kind"]]
            if k == "INTA" and prev != "INTA":
                inta.append(t["start"])
            if k == "HALT":
                halt.append(t["start"])
            prev = k
        fb = r["first_bad"]
        di = min((abs(fb - x) for x in inta), default=None)
        dh = min((abs(fb - x) for x in halt), default=None)
        if dh is not None and (di is None or dh <= di):
            fam, off = "HALT", fb - min(halt, key=lambda x: abs(fb - x))
        elif di is not None:
            fam, off = "INTA", fb - min(inta, key=lambda x: abs(fb - x))
        else:
            fam, off = "NONE", None
        w = r["waits"] or {}
        wc = f"wrand{w.get('wmax')}" if w.get("wrand") else \
             f"fix{w.get('fixed') or 0}"
        rows.append({"cid": r["cid"], "k": r["k"], "path": r["path"],
                     "first_bad": fb, "n": r["n"], "ndiff": r["ndiff"],
                     "kind": r["kind"], "detail": r.get("detail", ""),
                     "fam": fam, "off": off, "waitclass": wc,
                     "pin": (r.get("evt") or {}).get("pin"),
                     "inta": inta, "halt": halt})
    ack = [r for r in rows if r["fam"] == "INTA" and abs(r["off"]) <= 12]
    waited = [r for r in ack if r["waitclass"] != "fix0"]
    print(f"  diverging seeds {len(rows)}   ACK family {len(ack)}   "
          f"waited {len(waited)}")
    if args.dump:
        json.dump(rows, open(args.dump, "w"), indent=1)
        print(f"  dump -> {args.dump}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("hltsweep")
    p.add_argument("--dump", default="")
    p.set_defaults(fn=cmd_hltsweep)
    p = sub.add_parser("psw")
    p.set_defaults(fn=cmd_psw)
    p = sub.add_parser("regold")
    p.add_argument("--form", default="HLT.INT")
    p.add_argument("--waits", type=int, default=1)
    p.add_argument("--write", action="store_true")
    p.set_defaults(fn=cmd_regold)
    p = sub.add_parser("ackfam")
    p.add_argument("--report", required=True)
    p.add_argument("--dump", default="")
    p.set_defaults(fn=cmd_ackfam)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
