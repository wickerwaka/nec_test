#!/usr/bin/env python3
"""wrfuzz_w2 -- THE SURVEY (task #38, W2).  OFFLINE, board-free, NON-LANDING.

It executes `docs/notes/wrfuzz_corpus_prereg_2026-08-05.md` §7's deliverable
shape over the W1 corpus (`cid = wr1`, 3,150 seeds, ledger §2) and NOTHING
else: it scores, it counts, it partitions, and it freezes the victory bar's
number.  **It fixes nothing and it lands nothing.**

> *"A guiding principal here needs to be simplicity.  This is 80's era
> hardware, they aren't wasting silicon on anything that isn't necessary.
> Complex or confusing behavior that we see is likely to be simple systems
> interacting in ways you do not fully understand yet."*

THREE COMPARATORS, AND THEIR INFORMATION CONDITIONS ARE DIFFERENT.  The EVT
quoting rule generalises (`standing_gates.md`): state what each engine was
told, per leg, and never rank two legs that were told different things.

  HW-vs-SILICON   the campaign's own comparator and the only one over the WHOLE
                  corpus: the `ucore` IN FABRIC (`use_core=1`) against the
                  socketed chip (`use_core=0`), same image, same 4,096-entry
                  vector, same bitstream, differing in the A/B select and in
                  nothing else.  Banked inline by `fuzz_campaign.capture_board`
                  at W1 as each seed's `verdict`; this tool READS it and never
                  recomputes it.  n = 3,150.
  chip-vs-model   the C++ timed model replayed offline against the banked
                  socket rows.  ATTRIBUTION ONLY (prereg §7.1's own words).
  chip-vs-ucoreTB the same core's RTL in the Verilator TB, offline.
                  ATTRIBUTION ONLY.

⚠ **THE TWO OFFLINE LEGS ARE COMPUTABLE ONLY WHERE ROWS WERE RETAINED.**  W1
retained 380 of 3,150 captures (ledger §2.5) -- EVERY non-exact seed plus a
SUCCESS ballast -- so the offline legs' denominator is a set that is
divergent-by-construction and **their rate is not a population rate**.  What
the retention IS sufficient for is exactly what the pre-registration asks of
them: the family census over every non-exact seed, and the cross-engine
partition.  Both are stated in those terms and never as an engine ranking.

Subcommands:
  seeds     materialise the 380 retained captures as banked-entry records so
            `timed_fuzz --seeddir` / `s15_census` can score them unchanged
  strata    the per-stratum HW-vs-SILICON table, over all 3,150
  fabric    the family census of the FABRIC residue -- `s15_census`'s own
            classifier applied to the rows the board actually produced
  counts    the counts prereg §4.2 / §7.5 asks for (class-A 8080, `mc1/721`
            signature, INTA rows, the opcode in flight at the first divergence)
  mod3      the `8F` mod-3 ghost's population -- and a B-4 re-run in passing.
            ⚠ its byte-scan leg is VACUOUS and says so; read the EXECUTION
            count in `counts` instead
  tranche   the victory tranche's cells, drawn per prereg §5

`strata` prints S and B = S - 5.0.  There is no `bar` subcommand: the bar is
one line of the table that produces it, so the two cannot drift apart.
"""
import argparse
import gzip
import json
import os
import sys
from collections import Counter, defaultdict
from multiprocessing import Pool
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

import fuzz_campaign as fzc                               # noqa: E402
import fuzz_classify as fc                                # noqa: E402
import timed_fuzz as tf                                   # noqa: E402
import ucsim_fuzz as uf                                   # noqa: E402
import wrfuzz_w1 as w1                                    # noqa: E402

CID = "wr1"
CDIR = fzc.CAMPAIGNS / CID
OUT = SW / "testdata" / "wrfuzz"
CACHE = Path(os.path.expanduser("~/.cache/ucsimt-tmp/wrfuzz_w2"))

STRATA = w1.STRATA
K_BASE, K_STRIDE = w1.K_BASE, w1.K_STRIDE


# --------------------------------------------------------------------------- #
# the stratum of a seed -- DERIVED from its k, never from a stored label, so a
# mislabelled record cannot move a stratum's denominator.
# --------------------------------------------------------------------------- #
def stratum_of(k):
    i = (int(k) - K_BASE) // K_STRIDE
    if not (0 <= i < len(STRATA)):
        raise ValueError(f"k={k} is outside the registered blocks")
    st = STRATA[i]
    if not (st["k_lo"] <= int(k) < st["k_lo"] + st["n"]):
        raise ValueError(f"k={k} is outside stratum {i}'s registered size")
    return st


def results():
    return [json.loads(l) for l in
            (CDIR / "results.jsonl").read_text().splitlines() if l.strip()]


def cap_path(r):
    return CDIR / "captures" / f"{r['tier']}_{r['k']}_{r['cfg_hash']}.json.gz"


# --------------------------------------------------------------------------- #
# `seeds` -- the retained captures as banked-entry records.
#
# `fuzz_bank.promote` is NOT used: it applies PROMOTION CAPS (10 per timing
# signature, 50 per rule class, 1-in-50 cadence), which are right for a standing
# regression bank and wrong for a census, whose whole job is to account for
# every non-exact seed.  The record written here is `fuzz_bank`'s own shape --
# same keys, same `ov`, same `chip_rows` -- so `timed_fuzz` and `s15_census`
# read it with no flag and no special case.
# --------------------------------------------------------------------------- #
def _mk(args):
    r, dest = args
    cap = json.loads(gzip.decompress(cap_path(r).read_bytes()))
    st = stratum_of(r["k"])
    entry = dict(r)
    entry["ov"] = w1.ov_of(st)
    entry["chip_rows"] = cap["real"]
    entry["fabric_rows"] = cap["sim"]
    entry["stratum"] = st["i"]
    entry["stratum_label"] = w1.label(st)
    blob = gzip.compress(json.dumps(entry).encode())
    p = dest / f"{r['tier']}_{r['k']}_{r['cfg_hash']}.json.gz"
    p.write_bytes(blob)
    return str(p)


def cmd_seeds(a):
    dest = Path(a.dest or (CACHE / "seeds"))
    dest.mkdir(parents=True, exist_ok=True)
    rows = [r for r in results() if cap_path(r).exists()]
    print(f"== wrfuzz_w2 seeds -- {len(rows)} retained captures -> {dest}")
    with Pool(a.jobs) as pool:
        made = pool.map(_mk, [(r, dest) for r in rows], chunksize=8)
    print(f"  wrote {len(made)}")
    n_div = sum(1 for r in rows if r["verdict"] != "SUCCESS")
    allrows = results()
    n_div_all = sum(1 for r in allrows if r["verdict"] != "SUCCESS")
    print(f"  non-exact among them {n_div} of {n_div_all} in the corpus "
          f"({'ALL RETAINED' if n_div == n_div_all else 'MISSING ROWS'})")
    return 0 if n_div == n_div_all else 1


# --------------------------------------------------------------------------- #
# `strata` -- the HW-vs-SILICON table.  Read off the bank; nothing is re-run.
# --------------------------------------------------------------------------- #
def class_a(r, cap=None):
    """§63.5's 8080 class-A criterion, verbatim and board-free: the CHIP's cell
    at the first contested slot is `CODE 00484` AND the chip's window contains
    `CODE:00008` (the 8080 `RST 1` vector fetch).  Needs rows, so it is defined
    only on a retained capture; a seed with no rows is `None` (unknown), never
    silently False."""
    if r["verdict"] == "SUCCESS":
        return False
    if cap is None:
        p = cap_path(r)
        if not p.exists():
            return None
        cap = json.loads(gzip.decompress(p.read_bytes()))
    chip = cap["real"]
    win = uf.window_of(chip)
    lc = [(i, fc.BS_NAME[x["bs_early"]], x["ad_addr"] & 0xFFFFF)
          for i, x in enumerate(chip[:win])
          if x.get("t_state", x.get("t")) == 1]
    ls = [(i, fc.BS_NAME[x["bs_early"]], x["ad_addr"] & 0xFFFFF)
          for i, x in enumerate(cap["sim"][:win])
          if x.get("t_state", x.get("t")) == 1]
    m = min(len(lc), len(ls))
    j = next((x for x in range(m) if lc[x][1:] != ls[x][1:]), None)
    if j is None:
        return False
    cell = (lc[j][1], lc[j][2])
    if cell != ("CODE", 0x00484):
        return False
    return any(c[1] == "CODE" and c[2] == 0x00008 for c in lc)


def open_bus(r):
    """THE PRE-REGISTERED EXCLUSION (prereg §2.4), evaluated on EVERY seed.

    §2.4 names `fuzz_classify._open_bus_escaped_before` -- "did the chip make
    >= 8 out-of-image CODE fetches reading pure address feedthrough" -- and that
    function needs the chip's ROWS, which W1 retained for 380 of 3,150 seeds.
    It is nonetheless computable corpus-wide, because the capture path banks
    `fuzz_accept.open_bus_escape_metrics`' own counts in every seed's record
    (`ob_escape = {feed, out, frac}`, present on all 1,050 raw lines and absent
    on all 2,100 soup lines), and `feed` IS that function's counter.

    MEASURED, not assumed: over the 260 retained raw captures the predicate
    `feed >= 8` and the row-level detector agree on **259**, the one exception
    being a seed whose done-shrunk window is shorter than the window the metric
    was taken over.  Soup: **0 of 120** retained soup captures trip the row
    detector, and no soup line carries the field at all.

    ⚠ WHY NOT THE BANK's OWN `open_bus` LABEL.  That label is a
    KNOWN_ACCEPTED rule hit, and `fuzz_classify.classify` consults the accept
    engine ONLY inside the two branches a divergence reaches: **a SUCCESS seed
    can never be labelled `open_bus`, by construction of the decision tree.**
    Excluding on it would remove open-bus MISSES and keep open-bus EXACTS,
    which is an exclusion whose membership depends on the answer -- the exact
    shape §2.4 and §3.3 forbid.  It is reported beside this one and never used
    as the bar's denominator."""
    ob = r.get("ob_escape") or {}
    return int(ob.get("feed") or 0) >= 8


def _strata_table(rows, excl):
    tab = defaultdict(Counter)
    for r in rows:
        t = tab[stratum_of(r["k"])["i"]]
        t["n"] += 1
        if excl(r):
            t["open_bus"] += 1
            continue
        t["scored"] += 1
        if r["verdict"] == "SUCCESS":
            t["exact"] += 1
        else:
            t[f"miss_{r['verdict']}"] += 1
    out = []
    for st in STRATA:
        t = tab[st["i"]]
        rate = 100.0 * t["exact"] / t["scored"] if t["scored"] else float("nan")
        out.append({"i": st["i"], "tier": st["tier"], "src": st["src"],
                    "n": t["n"], "open_bus": t["open_bus"],
                    "scored": t["scored"], "exact": t["exact"], "rate": rate,
                    "func": t["miss_FUNCTIONAL"], "tim": t["miss_TIMING"],
                    "kacc": t["miss_KNOWN_ACCEPTED"]})
    return out


def _print_table(out):
    print(f"{'i':>3} {'tier':<5} {'source':<11} {'n':>5} {'OPEN':>5} "
          f"{'scored':>7} {'exact':>6} {'rate%':>7}  "
          f"{'FUNC':>5}{'TIM':>5}{'KACC':>5}")
    for o in out:
        print(f"{o['i']:>3} {o['tier']:<5} {o['src']:<11} {o['n']:>5} "
              f"{o['open_bus']:>5} {o['scored']:>7} {o['exact']:>6} "
              f"{o['rate']:>7.2f}  {o['func']:>5}{o['tim']:>5}{o['kacc']:>5}")
    S = sum(o["rate"] for o in out) / len(out)
    te, ts = sum(o["exact"] for o in out), sum(o["scored"] for o in out)
    print(f"  pooled  {te}/{ts} = {100.0*te/ts:.2f} %   "
          f"S = {S:.4f} %   B = S - 5.0 = {S-5.0:.4f} %")
    return S, te, ts


def cmd_strata(a):
    rows = results()
    print("== THE REGISTERED EXCLUSION (prereg §2.4: the open-bus escape "
          "detector, on every seed)")
    out = _strata_table(rows, open_bus)
    S, te, ts = _print_table(out)
    print("\n== FOR COMPARISON ONLY -- the bank's KNOWN_ACCEPTED/open_bus "
          "LABEL, which no SUCCESS seed can carry")
    lab = _strata_table(rows, lambda r: r["verdict"] == "KNOWN_ACCEPTED"
                        and r["sub"] == "open_bus")
    S2, te2, ts2 = _print_table(lab)
    print("\n== NO EXCLUSION AT ALL (the floor: every captured seed scored)")
    S3, te3, ts3 = _print_table(_strata_table(rows, lambda r: False))
    print(f"\n  S (FROZEN, the registered detector) = {S:.4f} %")
    print(f"  B = S - 5.0                          = {S-5.0:.4f} %")
    if a.report:
        Path(a.report).write_text(json.dumps(
            {"strata": out, "S": S, "B": S - 5.0,
             "pooled_exact": te, "pooled_scored": ts,
             "alt_bank_label": {"strata": lab, "S": S2, "exact": te2,
                                "scored": ts2},
             "alt_no_exclusion": {"S": S3, "exact": te3, "scored": ts3}},
            indent=1))
        print(f"  report -> {a.report}")
    return 0


# --------------------------------------------------------------------------- #
# `fabric` -- the family census of the residue the BOARD produced.
#
# `s15_census.one()` REPLAYS an engine and classifies chip-vs-engine.  The
# campaign's comparator is chip-vs-FABRIC, and §56 measured that the fabric
# scorer is stricter than the TB by one class (the INTA float), so the two are
# not interchangeable.  This runs `s15_census`'s OWN classifier -- imported,
# not forked -- over the rows the board produced.
# --------------------------------------------------------------------------- #
def _fab(path):
    import s15_census as s15                              # noqa: PLC0415
    entry = json.loads(gzip.decompress(Path(path).read_bytes()))
    chip, fab = entry["chip_rows"], entry["fabric_rows"]
    out = s15.classify(entry, chip, fab)
    out["path"] = str(path)
    out["stratum"] = entry["stratum"]
    out["stratum_label"] = entry["stratum_label"]
    out["waitclass"] = tf.wait_class(entry)
    out["verdict"] = entry["verdict"]
    out["sub"] = entry["sub"]
    return out


def cmd_fabric(a):
    import s15_census as s15                              # noqa: PLC0415
    src = Path(a.seeddir or (CACHE / "seeds"))
    paths = sorted(str(p) for p in src.glob("*.json.gz"))
    # the census is over the NON-EXACT seeds; the ballast is the control and is
    # reported separately rather than mixed in.
    keep, ob = [], 0
    for p in paths:
        e = json.loads(gzip.decompress(Path(p).read_bytes()))
        if e["verdict"] == "SUCCESS":
            continue
        if not a.with_open_bus and open_bus(e):
            ob += 1
            continue
        keep.append(p)
    print(f"== wrfuzz_w2 fabric census -- {len(keep)} SCORED non-exact seeds "
          f"(chip vs the ucore IN FABRIC, FLASH #10); "
          f"{ob} open-bus misses excluded per prereg §2.4", flush=True)
    with Pool(a.jobs) as pool:
        rows = pool.map(_fab, keep, chunksize=4)
    s15.report(rows, a.show)
    if a.dump:
        with gzip.open(a.dump, "wt") as f:
            json.dump(rows, f, separators=(",", ":"))
        print(f"\n  dump -> {a.dump}")
    return 0


# --------------------------------------------------------------------------- #
# `counts` -- the counts prereg §4.2 / §7.5 asks for, each with its criterion
# written beside it.  Every one is a COUNT that is REPORTED; none is a filter.
# --------------------------------------------------------------------------- #
def _counts_one(path):
    entry = json.loads(gzip.decompress(Path(path).read_bytes()))
    chip, fab = entry["chip_rows"], entry["fabric_rows"]
    win = uf.window_of(chip)
    out = {"k": entry["k"], "stratum": entry["stratum"],
           "label": entry["stratum_label"], "wc": tf.wait_class(entry),
           "verdict": entry["verdict"], "open_bus": open_bus(entry)}
    # INTA rows -- the §56 fabric float class.  The corpus is evt-free, so a
    # non-zero count is itself the finding.
    out["inta_rows"] = sum(1 for r in chip[:win]
                           if r.get("t_state", r.get("t")) == 1
                           and r["bs_early"] == 0)
    # the 8080 class-A criterion, §63.5 verbatim (see class_a above)
    out["class_a"] = class_a({"verdict": entry["verdict"]},
                             {"real": chip, "sim": fab})
    if entry["verdict"] == "SUCCESS":
        return out
    dr = fc.diff_rows(chip, fab)
    out["ndiff"] = len(dr.rows)
    out["n"] = dr.n
    if dr.rows:
        fb = dr.rows[0].i
        out["fb"] = fb
        out["kind"] = tf.first_kind(dr.rows[0])
        # the opcode in flight at the first divergence -- `fuzz_classify`'s own
        # reconstruction, the one the campaign's signature already uses.
        out["opsig"] = fc._last_opsig(chip, fb)
        # `mc1/721`'s signature (§86.G part C): a `data` column parting with a
        # VERY small diff stream -- both writes land, in the wrong order.
        out["mc1_721_sig"] = (out["kind"] == "data" and len(dr.rows) <= 4)
    return out


def cmd_counts(a):
    src = Path(a.seeddir or (CACHE / "seeds"))
    paths = sorted(str(p) for p in src.glob("*.json.gz"))
    with Pool(a.jobs) as pool:
        rows = pool.map(_counts_one, paths, chunksize=8)
    div = [r for r in rows if r["verdict"] != "SUCCESS" and not r["open_bus"]]
    print(f"== wrfuzz_w2 counts -- {len(rows)} retained captures, "
          f"{len(div)} of them SCORED misses")
    print(f"\n  INTA rows in the chip's window (the §56 float class):")
    print(f"    seeds with >= 1 INTA row : "
          f"{sum(1 for r in rows if r['inta_rows'])} / {len(rows)}")
    print(f"    INTA rows, total         : "
          f"{sum(r['inta_rows'] for r in rows)}")
    print(f"\n  8080 class-A landings (§63.5's criterion, on the SCORED misses):")
    ca = [r for r in div if r["class_a"]]
    print(f"    {len(ca)} / {len(div)}"
          + ("" if not ca else "   " + ", ".join(str(r['k']) for r in ca)))
    print(f"\n  `mc1/721`-signature seeds (a `data` part with ndiff <= 4):")
    m7 = [r for r in div if r.get("mc1_721_sig")]
    print(f"    {len(m7)} / {len(div)}"
          + ("" if not m7 else "   " + ", ".join(
              f"{r['k']}({r['label']},ndiff={r['ndiff']})" for r in m7)))
    print(f"\n  the opcode in flight at the first divergence, top 20:")
    for k, v in Counter(r.get("opsig") for r in div).most_common(20):
        print(f"    {v:>4}  {k}")
    print(f"\n  per stratum: scored misses / INTA-carrying seeds / class-A")
    for st in STRATA:
        s = [r for r in rows if r["stratum"] == st["i"]]
        d = [r for r in s if r["verdict"] != "SUCCESS" and not r["open_bus"]]
        print(f"    {st['i']:>3} {w1.label(st):<16} misses {len(d):>3}   "
              f"INTA {sum(1 for r in s if r['inta_rows']):>3}   "
              f"classA {sum(1 for r in d if r['class_a']):>3}")
    if a.report:
        Path(a.report).write_text(json.dumps(rows, indent=1))
        print(f"\n  report -> {a.report}")
    return 0


# --------------------------------------------------------------------------- #
# `mod3` -- the `8F` mod-3 ghost cell's population (prereg §4.2, §84.6).
# COUNTED, not chased: soup never emits it (`emit_stack` forces a windowed EA),
# the raw tier carries it naturally, and no knob was added for it.  The count is
# taken on the ARTIFACT -- the composed image -- so it is an upper bound on the
# seeds that can execute one, never an execution count.
# --------------------------------------------------------------------------- #
def _mod3_one(r):
    entry = dict(r)
    entry["ov"] = w1.ov_of(stratum_of(r["k"]))
    image, _meta, _g, sha = uf.regen(entry)
    b = bytes(image)
    n = sum(1 for i in range(len(b) - 1)
            if b[i] == 0x8F and (b[i + 1] >> 6) == 3)
    return {"k": r["k"], "stratum": stratum_of(r["k"])["i"], "n8f": n,
            "drift": sha != r["image_sha256"]}


def cmd_mod3(a):
    rows = results()
    with Pool(a.jobs) as pool:
        out = pool.map(_mod3_one, rows, chunksize=16)
    drift = sum(1 for o in out if o["drift"])
    car = [o for o in out if o["n8f"]]
    print(f"== wrfuzz_w2 mod3 -- `8F` at mod == 3 in the COMPOSED image, "
          f"{len(rows)} seeds")
    print(f"  GEN-DRIFT (B-4 re-run in passing): {drift}")
    print(f"  ⚠ VACUOUS -- DO NOT QUOTE AS A POPULATION.  A 64 KB image with")
    print(f"    random fill contains the byte pair by chance almost always, so")
    print(f"    this counts DATA, not executed forms.  The count that means")
    print(f"    something is the EXECUTION one: the form in flight at the first")
    print(f"    divergence, printed by `wrfuzz_w2.py counts`.  Kept, and")
    print(f"    labelled, because the vacuous-instrument pattern is this")
    print(f"    project's most repeated failure (wrfuzz_provenance.md §3.4 F-12).")
    print(f"  seeds whose image carries at least one `8F`/mod-3 pair: "
          f"{len(car)} / {len(rows)}   [VACUOUS]")
    print(f"  pairs, total: {sum(o['n8f'] for o in out)}   [VACUOUS]")
    per = Counter()
    for o in out:
        if o["n8f"]:
            per[o["stratum"]] += 1
    print("  by stratum (only the non-zero ones):")
    for i in sorted(per):
        print(f"    {i:>3} {w1.label(STRATA[i]):<16} {per[i]}")
    if a.report:
        Path(a.report).write_text(json.dumps(out))
        print(f"  report -> {a.report}")
    return 0 if drift == 0 else 1


# --------------------------------------------------------------------------- #
# `tranche` -- THE VICTORY TRANCHE, drawn per prereg §5 and campaign plan §5.
#
# Seeds are DRAWN here and CAPTURED at the victory sitting.  Everything about
# the population is fixed now and frozen with a sha256, the b2 precedent
# (`ucsim_t_provenance.md` §14.4) exactly.
# --------------------------------------------------------------------------- #
V_BASE = 300000
D_BASE = 328000
# The four directed H3-B cells (prereg §5.2): `skew`, blk = 32 (the longest
# block, i.e. the deepest interior), no pin event, scored as their own cells.
DIRECTED = (("D1", "soup", 0, 7), ("D2", "soup", 1, 15),
            ("D3", "raw", 0, 7), ("D4", "raw", 1, 15))
D_N = 25            # see cmd_tranche's docstring for the derivation


def cmd_tranche(a):
    """Draw the tranche.  Nothing is generated and nothing is captured.

    THE STRATIFIED BODY: the same 28 strata, **7 seeds per stratum = 196**,
    `k in [300000 + 1000*i, +7)` -- the §2.2 block layout at a new base, so it
    is disjoint from every survey seed BY CONSTRUCTION and not by a check.

    THE FOUR DIRECTED CELLS are SELECTED, not forced, and that is a deliberate
    choice with a cost: `derive_case` has no override that pins a vector
    shape's PARAMETERS (`ov` carries `wvec_shapes`, a shape list, and the
    parameters come from `wvec_shapes.draw_spec`'s own deterministic stream).
    Rather than add a forcing knob to the generator in a SURVEY sitting, the
    cells are drawn by SEARCHING each cell's own k-block for the seeds whose
    drawn spec already is `(skew, blk = 32, wlo, whi)`.  The draw is
    deterministic in `(cid, k)`, so the membership is reproducible and frozen;
    the generator gap is BOOKED for W3 rather than closed here.

    `D_N = 25` per cell: §68.6's own class-B statistic came from 186 captures
    carrying 7,254 paired accesses (~39 per capture).  A wrfuzz capture reaches
    a p95 of 673 bus cycles, so 25 seeds x 4 cells is the same order of paired
    accesses as the measurement this is asked to be read against."""
    import wvec_shapes as wv                              # noqa: PLC0415
    pop = {"cid": "wr2", "drawn": "wrfuzz W2 survey, 2026-08-06",
           "prereg": "docs/notes/wrfuzz_corpus_prereg_2026-08-05.md §5",
           "plan": "docs/notes/wrfuzz_campaign_plan.md §5",
           "disjoint_from": "wr1, k in [200000, 227075)",
           "reps": 3, "promotion_reps": 5, "body": [], "directed": []}
    for st in STRATA:
        ks = list(range(V_BASE + K_STRIDE * st["i"],
                        V_BASE + K_STRIDE * st["i"] + 7))
        pop["body"].append({"i": st["i"], "tier": st["tier"], "src": st["src"],
                            "n": 7, "k": ks, "ov": w1.ov_of(st)})
    # THE 12 PROMOTION CELLS, declared HERE and mechanically: the FIRST seed of
    # each of the ten `wvec` strata (five shapes x two tiers -- the axis under
    # test) plus the first seed of `soup/fix0` and `raw/fix0` (its w0 anchor in
    # each tier).  b2's rule was "the first seed of each of the 9 wait classes
    # for mc1, plus three named others"; transposed to a 14-source grid that
    # would be 14, so the transposition names the NEW axis and its anchor.
    promo = [b["k"][0] for b in pop["body"] if b["src"].startswith("wvec")] + \
            [b["k"][0] for b in pop["body"] if b["src"] == "fix0"]
    assert len(promo) == 12, promo
    pop["promotion_cells"] = sorted(promo)
    for name, tier, wlo, whi in DIRECTED:
        base = D_BASE + K_STRIDE * (int(name[1:]) - 1)
        ks, k = [], base
        while len(ks) < D_N and k < base + 20 * K_STRIDE:
            sp = wv.draw_spec("wr2", k, "skew")
            if sp["blk"] == 32 and sp["wlo"] == wlo and sp["whi"] == whi:
                ks.append(k)
            k += 1
        pop["directed"].append(
            {"cell": name, "tier": tier, "wlo": wlo, "whi": whi, "blk": 32,
             "n": len(ks), "k": ks,
             "ov": {"force_tier": tier, "no_evt": True, "no8080": True,
                    "wvec_shapes": ["skew"]},
             "selection": "draw_spec('wr2', k, 'skew') == (blk 32, wlo, whi)"})
    blob = json.dumps(pop, indent=1, sort_keys=True)
    dest = Path(a.report or (OUT / "victory_population.json"))
    dest.write_text(blob)
    import hashlib                                        # noqa: PLC0415
    sha = hashlib.sha256(blob.encode()).hexdigest()
    print(f"== wrfuzz_w2 tranche -- FROZEN")
    print(f"  body      {sum(b['n'] for b in pop['body'])} seeds over "
          f"{len(pop['body'])} strata, k in [{V_BASE}, "
          f"{V_BASE + K_STRIDE*27 + 7})")
    for d in pop["directed"]:
        print(f"  {d['cell']}  {d['tier']:<5} skew wlo={d['wlo']} "
              f"whi={d['whi']} blk=32   n={d['n']}  k {d['k'][0]}..{d['k'][-1]}")
    print(f"  promotion cells (5 reps): {pop['promotion_cells']}")
    print(f"  total seeds {sum(b['n'] for b in pop['body']) + sum(d['n'] for d in pop['directed'])}"
          f"   seed-loops at 3 reps (+2 on the 12) = "
          f"{3*(sum(b['n'] for b in pop['body']) + sum(d['n'] for d in pop['directed'])) + 24}")
    print(f"  {dest}")
    print(f"  sha256 {sha}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("seeds", "strata", "fabric", "counts",
                                    "mod3", "tranche"))
    ap.add_argument("--dest", default="")
    ap.add_argument("--seeddir", default="")
    ap.add_argument("--report", default="")
    ap.add_argument("--dump", default="")
    ap.add_argument("--show", default="")
    ap.add_argument("--with-open-bus", action="store_true")
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 4)
    a = ap.parse_args()
    return {"seeds": cmd_seeds, "strata": cmd_strata, "fabric": cmd_fabric,
            "counts": cmd_counts, "mod3": cmd_mod3,
            "tranche": cmd_tranche}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
