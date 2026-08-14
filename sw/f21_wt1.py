#!/usr/bin/env python3
"""f21_wt1 -- THE FLASH #21 WRITE-T1 SCORER: clauses (v) and (vi).

WHY THIS EXISTS
---------------
`ce_contract_reland_results_2026-08-13.md` §10 owes two silicon clauses,
because the `t1_half2` re-land MOVED A PIN IN TIME (the AD turnaround on a
write T1 now sits at `ce_half`+1.0 fabric periods instead of +0.5):

  (v)  the MEMW/IOW write-T1 rows must be BYTE-IDENTICAL on silicon -- the
       turnaround is the only pin transition the wave moves, so those rows are
       its whole silicon surface, and any diff there is the wave's;
  (vi) the turnaround must be visible AT THE CORRECT INSTANT in the two-sample
       rows -- `nec_bus` banks two AD samples per CPU clock, and the ADDRESS
       sample (`ad_early`, at `tick_fall`, recorded as `ad_addr`) must still
       carry the ADDRESS while the end-of-cycle sample (`tick_rise`, recorded
       as `ad_data`) must still carry the WRITE WORD, on 100 % of write T1s.

The offline argument predicts (vi) exactly.  It is an argument about a RIG, and
silicon is not a rig, so it is confirmed or refuted here and nowhere else.

WHAT A WRITE T1 IS, IN THE CAPTURE'S OWN UNITS
----------------------------------------------
`nec_bus.sv:700` packs one 64-bit record per CPU clock; `fz2` unpacks it to

    t          T-state    0 Ti · 1 T1 · 2 T2 · 3 T3 · 4 Tw · 5 T4
    bs_early   BS at the address phase   2 IOW · 6 MEMW  (the write cycles)
    ad_addr    ad_early  [19:0]  -- the ADDRESS-phase sample, at `tick_fall`
    ad_data    ad_in_q[15:0]     -- the end-of-cycle sample, at `tick_rise`

so a write T1 is `t == 1 and bs_early in (2, 6)`, and the two samples this
wave moves the boundary between are exactly `ad_addr` and `ad_data` ON THAT
ROW.  Measured shape of a healthy write cycle (a banked FLASH #20 capture):

    T1  bs 6  ad_addr 0x1cd5   ad_data 0x83f0      <- address | write word
    T2  bs 6  ad_addr 0x183f0  ad_data 0x83f0      <- turned around, both data

THE FIVE MEASUREMENTS, AND WHICH ARE INDEPENDENT OF WHICH
---------------------------------------------------------
  V-A  CORE column, AFTER era vs BEFORE era, write-T1 rows byte-identical.
       This is clause (v) as the task states it: "vs the F20 capture".  It
       compares the FPGA core against ITSELF across the pin move.
  V-B  CORE vs CHIP on the AFTER capture, write-T1 rows byte-identical.
       This is clause (v) read as "on silicon": the socketed part is the
       reference no bitstream can move.  Rows at or after a failing seed's
       `first_bad_row` are counted SEPARATELY, because a seed that already
       diverges is not evidence about a turnaround.
  VI-A ADDRESS SAMPLE.  `(ad_addr & 0xFFFF) != ad_data` -- if the turnaround
       had moved EARLY the address-phase sample would already hold the write
       word and this is the signature that says so.  Rows where the address's
       low 16 bits happen to equal the write word are AMBIGUOUS by
       construction and are counted apart, never as passes.
       Corroborated, on rows a diverging seed cannot poison, by
       `ad_addr(core) == ad_addr(chip)`.
  VI-B DATA SAMPLE.  `ad_data(T1) == ad_data(T2)` -- the write word is already
       standing at the end of T1.  If the turnaround had moved LATE the T1
       end-of-cycle sample would still hold the address and this fails.
       Corroborated by `ad_data(core) == ad_data(chip)`.
  VI-C TURNAROUND COMPLETE BY T2.  `(ad_addr & 0xFFFF) == ad_data` on the T2
       row.  This is the control that VI-A is measuring a turnaround at all
       and not a bus that never turns: VI-A and VI-C are the SAME predicate
       with the OPPOSITE expected answer one row apart.

NON-VACUITY
-----------
`--null N` perturbs N write-T1 rows of the AFTER core table in memory -- one
bit of the T1's `ad_addr`, one of its `ad_data`, one of the following T2's
`ad_addr`, chosen deterministically -- and requires ALL FIVE clause counts to
move.  A scorer that cannot fail is not a scorer, and a null that could only
move one clause would leave the other four unproved.  `--self-test` runs the
identity pair and then the null and prints both, which is how this tool is
proved before the board is touched.

THE BASELINE IS NOT ZERO, AND IT IS REGISTERED RATHER THAN ASSUMED
------------------------------------------------------------------
Measured on the banked FLASH #20 captures before FLASH #21 was built: V-B has
**4** differing clean rows and they differ in `ad_data` ALONE --
`fz2c/406046` @3525, `fz2e/521016` @361, `fz2e/529009` @907, `fz2e/531039`
@1011.  `ad_data` at a T1 is not in `diff_rows`' column policy, so **those
four rows are invisible to every standing gate in this repo** and they are a
FLASH #20-era quantity, not this wave's.  `--baseline` takes them as the bar
so that the wave is scored against what was there, not against a zero nobody
has ever measured.
"""
import argparse
import gzip
import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
CAMPAIGNS = ROOT / "sw" / "testdata" / "campaigns"

BS_IOW, BS_MEMW = 2, 6
WRITE_BS = (BS_IOW, BS_MEMW)
T1, T2 = 1, 2

# the row fields that make a captured cycle.  "byte-identical" is equality of
# the whole record; the key list is fixed here so a capture that GAINS a field
# is a loud KeyError rather than a silent pass.
ROW_KEYS = ("idx", "ad_addr", "ad_data", "ps", "bs_early", "bs_late", "qs",
            "ube_n", "rd_n", "lock_n", "pin_int", "pin_nmi", "pin_poll_n",
            "rst", "t", "vec_armed")

# ⚠ THE CORE-vs-CHIP COLUMN SET IS NOT THE WHOLE ROW, AND INVENTING A NEW
# COMPARATOR HERE WOULD BE INVENTING A RESULT.  `fuzz_classify.diff_rows` is
# the corpus's own policy and on a T1 row it compares `t`, `bs_early`, `ube_n`,
# `qs` and `ad_addr` -- and NOT `ps` (which it reads only at T2), NOT `lock_n`,
# and NOT `ad_data`.  Measured on the banked FLASH #20 captures: `ps` differs
# between the socketed part and the FPGA core on 1,054 of 1,106 sampled write
# T1s, so a whole-row equality test reports a catastrophe that the standing
# corpus has never scored and does not mean.
#
# `ad_data` IS ADDED HERE, DELIBERATELY, and it is the point of the clause:
# THE END-OF-CYCLE SAMPLE ON A WRITE T1 IS EXACTLY THE QUANTITY THIS WAVE
# MOVES, AND THE STANDING COMPARATOR IS BLIND TO IT.  That blindness is why
# clause (vi) is owed at all -- the corpus could not see a turnaround that
# moved by a whole sample.
WT1_CMP = ("t", "bs_early", "ube_n", "qs", "ad_addr", "ad_data")
WT1_UNSCORED = ("ps", "bs_late", "rd_n", "lock_n", "pin_int", "pin_nmi",
                "pin_poll_n", "rst", "vec_armed")


def row_tuple(r):
    return tuple(r[k] for k in ROW_KEYS)


def is_write_t1(r):
    return r["t"] == T1 and r["bs_early"] in WRITE_BS


def load_campaign(d):
    """-> {seed: {'chip': [rows], 'core': [rows], 'path': str}}

    `real` is the SOCKETED PART and `sim` is the FPGA core; the capture's own
    field names are historical and are translated here once, at the boundary,
    so nothing below has to remember which is which."""
    out = {}
    cap = pathlib.Path(d) / "captures"
    if not cap.is_dir():
        raise SystemExit(f"no captures/ under {d}")
    for p in sorted(cap.glob("*.json.gz")):
        with gzip.open(p) as fh:
            j = json.load(fh)
        seed = j["line"]["seed"]
        out[seed] = {"chip": j["real"], "core": j["sim"], "path": str(p)}
    return out


def by_idx(rows):
    return {r["idx"]: r for r in rows}


def write_t1_idxs(rows):
    return {r["idx"] for r in rows if is_write_t1(r)}


def perturb(bank, n):
    """NON-VACUITY: on the first N write-T1 rows of the core column, flip bit 0
    of the T1's `ad_addr` AND its `ad_data` AND the following T2's `ad_addr`.
    Deterministic by construction, and it touches one bit of each of the three
    samples the five clauses read, so ALL FIVE must move.  A null that could
    only move one clause would leave four of them unproved."""
    hit = 0
    for seed in sorted(bank):
        rows = bank[seed]["core"]
        for p, r in enumerate(rows):
            if hit >= n:
                return hit
            if is_write_t1(r):
                r["ad_addr"] ^= 1
                r["ad_data"] ^= 1
                nxt = rows[p + 1] if p + 1 < len(rows) else None
                if nxt is not None and nxt["t"] == T2:
                    nxt["ad_addr"] ^= 1
                hit += 1
    return hit


def score(before, after, first_bad):
    res = {}

    # ---- V-A: core column, era vs era ------------------------------------
    shared = sorted(set(before) & set(after))
    va = {"seeds_before": len(before), "seeds_after": len(after),
          "seeds_shared": len(shared), "rows": 0, "identical": 0,
          "differing": 0, "membership_moved": 0, "len_mismatch": 0,
          "diffs": []}
    for seed in shared:
        rb_all, ra_all = before[seed]["core"], after[seed]["core"]
        if len(rb_all) != len(ra_all):
            va["len_mismatch"] += 1
        for p in range(max(len(rb_all), len(ra_all))):
            rb = rb_all[p] if p < len(rb_all) else None
            ra = ra_all[p] if p < len(ra_all) else None
            wb = rb is not None and is_write_t1(rb)
            wa_ = ra is not None and is_write_t1(ra)
            if not (wb or wa_):
                continue
            va["rows"] += 1
            if wb != wa_:
                va["membership_moved"] += 1
                va["differing"] += 1
                if len(va["diffs"]) < 50:
                    va["diffs"].append({"seed": seed, "pos": p,
                                        "why": "write-T1 in only one era",
                                        "after": wa_})
                continue
            # SAME ENGINE ON BOTH SIDES: here the whole row IS comparable and
            # the test is whole-record equality, unlike V-B.
            if row_tuple(rb) == row_tuple(ra):
                va["identical"] += 1
            else:
                va["differing"] += 1
                if len(va["diffs"]) < 50:
                    va["diffs"].append({
                        "seed": seed, "pos": p, "idx": ra["idx"],
                        "fields": [k for k in ROW_KEYS if rb[k] != ra[k]]})
    res["V_A"] = va

    # ---- V-B / VI-A / VI-B / VI-C on the AFTER capture ---------------------
    vb = {"rows": 0, "identical": 0, "differing": 0,
          "rows_clean": 0, "differing_clean": 0, "diffs": [],
          "diffs_clean": [],
          "qs_flicker_only": 0, "unscored_cols_differ": 0, "policy": WT1_CMP}
    via = {"rows": 0, "not_write_word": 0, "ambiguous": 0, "early_turnaround": 0,
           "rows_clean": 0, "addr_eq_chip": 0, "hits": [], "early": []}
    vib = {"rows": 0, "t2_present": 0, "data_holds": 0, "data_moves": 0,
           "rows_clean": 0, "data_eq_chip": 0, "hits": []}
    vic = {"rows": 0, "turned": 0, "not_turned": 0, "hits": []}

    for seed in sorted(after):
        core, chip = after[seed]["core"], after[seed]["chip"]
        fb = first_bad.get(seed)
        # ⚠ `first_bad_row` IS A LIST POSITION, NOT THE `idx` FIELD.
        # `fuzz_classify.diff_rows` walks `real[i]` against `sim[i]` and reports
        # `i`; the captures start at `idx` 33 and are contiguous, so position
        # and `idx` differ by a constant and comparing one to the other silently
        # mis-splits the population.  Positions are used throughout below, and
        # the two columns are aligned BY POSITION for the same reason -- that is
        # the alignment the corpus's own comparator uses.
        for p, r in enumerate(core):
            if not is_write_t1(r):
                continue
            i = r["idx"]
            clean = fb is None or p < fb

            # V-B
            vb["rows"] += 1
            if clean:
                vb["rows_clean"] += 1
            cr = chip[p] if p < len(chip) else None
            if cr is not None and cr["idx"] != i:
                cr = None                      # the two columns are not aligned
            if cr is not None:
                bad = [k for k in WT1_CMP if cr[k] != r[k]]
                if any(cr[k] != r[k] for k in WT1_UNSCORED):
                    vb["unscored_cols_differ"] += 1
            else:
                bad = ["ROW ABSENT ON CHIP"]
            if not bad:
                vb["identical"] += 1
            elif bad == ["qs"] and {cr["qs"], r["qs"]} == {1, 3}:
                # the historical `qs` flicker class: 1 vs 3 with nothing else
                # moving is not a divergence in `diff_rows` either.
                vb["identical"] += 1
                vb["qs_flicker_only"] += 1
            else:
                vb["differing"] += 1
                rec = {"seed": seed, "pos": p, "idx": i,
                       "clean": clean, "fields": bad}
                if clean:
                    vb["differing_clean"] += 1
                    # the clean rows are the informative ones and are NEVER
                    # crowded out of the sample by the post-`first_bad` ones.
                    if len(vb["diffs_clean"]) < 200:
                        vb["diffs_clean"].append(rec)
                if len(vb["diffs"]) < 50:
                    vb["diffs"].append(rec)

            # VI-A  address sample is NOT the write word.
            #
            # ⚠ A SHARPER PREDICATE WAS TRIED AND IT DOES NOT SEPARATE THE
            # CLASSES, AND THAT IS RECORDED RATHER THAN QUIETLY DROPPED.  A T2
            # row's address-phase sample reads `{ps, write word}` -- measured,
            # `ad_addr 0x27c58` beside `ad_data 0x7c58` with `ps` 2 -- so an
            # EARLY turnaround should carry the 20-bit signature `ad_addr ==
            # (ps << 16) | ad_data`.  Measured on the banked FLASH #20
            # captures: ALL of the low-16 coincidences satisfy it too
            # (`fz2c/409014` writes 0xcccc to 0x0cccc, `fz2c/400016` writes
            # 0x00fe to 0x000fe), because a write whose word equals its own
            # address low half is indistinguishable from an early turnaround
            # BY CONSTRUCTION.  So `early_turnaround` is REPORTED and NOT
            # BARRED, and the quantity that does discriminate is the one that
            # is barred: agreement with the SOCKETED PART, which sees the same
            # coincidences and would not see the same early turnaround.
            # An actually-early turnaround is 42,185 rows, not 7.
            via["rows"] += 1
            if r["ad_addr"] == ((r["ps"] << 16) | r["ad_data"]):
                via["early_turnaround"] += 1
                via["ambiguous"] += 1
                if len(via["early"]) < 50:
                    via["early"].append({"seed": seed, "pos": p, "idx": i,
                                         "ad_addr": r["ad_addr"],
                                         "ad_data": r["ad_data"], "ps": r["ps"]})
            elif (r["ad_addr"] & 0xFFFF) == r["ad_data"]:
                via["ambiguous"] += 1
            else:
                via["not_write_word"] += 1
            if clean and cr is not None:
                via["rows_clean"] += 1
                if cr["ad_addr"] == r["ad_addr"]:
                    via["addr_eq_chip"] += 1
                elif len(via["hits"]) < 50:
                    via["hits"].append({"seed": seed, "idx": i,
                                        "core": r["ad_addr"], "chip": cr["ad_addr"]})

            # VI-B  data sample already holds the write word
            vib["rows"] += 1
            nxt = core[p + 1] if p + 1 < len(core) else None
            if nxt is not None and nxt["t"] == T2 and nxt["bs_early"] in WRITE_BS:
                vib["t2_present"] += 1
                if nxt["ad_data"] == r["ad_data"]:
                    vib["data_holds"] += 1
                else:
                    vib["data_moves"] += 1
                    if len(vib["hits"]) < 50:
                        vib["hits"].append({"seed": seed, "idx": i,
                                            "t1": r["ad_data"], "t2": nxt["ad_data"]})
                # VI-C  the T2 early sample HAS turned around
                vic["rows"] += 1
                if (nxt["ad_addr"] & 0xFFFF) == nxt["ad_data"]:
                    vic["turned"] += 1
                else:
                    vic["not_turned"] += 1
                    if len(vic["hits"]) < 50:
                        vic["hits"].append({"seed": seed, "idx": i + 1,
                                            "ad_addr": nxt["ad_addr"],
                                            "ad_data": nxt["ad_data"]})
            if clean and cr is not None:
                vib["rows_clean"] += 1
                if cr["ad_data"] == r["ad_data"]:
                    vib["data_eq_chip"] += 1

    res["V_B"], res["VI_A"], res["VI_B"], res["VI_C"] = vb, via, vib, vic
    return res


def key_counts(res):
    """The five numbers the five clauses are, in one tuple.  Used by the null:
    a perturbation must move EVERY one of them."""
    va, vb, via, vib, vic = (res["V_A"], res["V_B"], res["VI_A"],
                             res["VI_B"], res["VI_C"])
    return (va["differing"],
            vb["differing_clean"],
            via["rows_clean"] - via["addr_eq_chip"],
            vib["data_moves"] + (vib["rows_clean"] - vib["data_eq_chip"]),
            vic["not_turned"])


# the FLASH #20 baseline, measured on the banked captures before FLASH #21 was
# built and registered in `fz2_flash21_prereg_2026-08-13.md`.  Only the two
# CHIP-relative counts have a non-zero baseline; the three engine-internal
# structural counts are zero and are barred at zero.
BASELINE = {"V_B_clean": 4, "VI_A_chip": 0, "VI_B_chip": 4}


def verdicts(res, baseline=None):
    """-> {clause: 'MET'|'MISSED'}, on the registered predicates."""
    b = dict(BASELINE, **(baseline or {}))
    va, vb, via, vib, vic = (res["V_A"], res["V_B"], res["VI_A"],
                             res["VI_B"], res["VI_C"])
    v = {}
    v["V-A core era-vs-era"] = "MET" if va["differing"] == 0 else "MISSED"
    v["V-B core-vs-chip (clean rows)"] = (
        "MET" if vb["differing_clean"] <= b["V_B_clean"] else "MISSED")
    v["VI-A address sample"] = (
        "MET" if (via["rows_clean"] - via["addr_eq_chip"]) <= b["VI_A_chip"]
        else "MISSED")
    v["VI-B data sample"] = (
        "MET" if (vib["data_moves"] == 0
                  and (vib["rows_clean"] - vib["data_eq_chip"])
                  <= b["VI_B_chip"]) else "MISSED")
    v["VI-C turnaround by T2"] = "MET" if vic["not_turned"] == 0 else "MISSED"
    return v


def report(res, tag=""):
    va, vb, via, vib, vic = (res["V_A"], res["V_B"], res["VI_A"],
                             res["VI_B"], res["VI_C"])
    if tag:
        print(f"\n=== {tag}")
    print(f"  V-A  CORE era-vs-era : seeds shared {va['seeds_shared']} "
          f"(before {va['seeds_before']} / after {va['seeds_after']})")
    print(f"       write-T1 rows {va['rows']}  identical {va['identical']}  "
          f"differing {va['differing']}  (membership moved {va['membership_moved']})")
    print(f"  V-B  CORE vs CHIP    : write-T1 rows {vb['rows']}  "
          f"identical {vb['identical']}  differing {vb['differing']}"
          f"   [policy {'+'.join(WT1_CMP)}]")
    print(f"       on rows before first_bad: {vb['rows_clean']} rows, "
          f"{vb['differing_clean']} differing"
          f"   (qs-flicker-only {vb['qs_flicker_only']}, "
          f"unscored columns differ on {vb['unscored_cols_differ']})")
    print(f"  VI-A ADDRESS sample  : {via['not_write_word']} / {via['rows']} "
          f"are NOT the write word  (ambiguous {via['ambiguous']}, of which "
          f"{via['early_turnaround']} carry the 20-bit signature -- REPORTED, "
          f"NOT BARRED)")
    print(f"       vs chip on clean rows: {via['addr_eq_chip']} / {via['rows_clean']}")
    print(f"  VI-B DATA sample     : {vib['data_holds']} / {vib['t2_present']} "
          f"hold the write word into T2  (moved {vib['data_moves']})")
    print(f"       vs chip on clean rows: {vib['data_eq_chip']} / {vib['rows_clean']}")
    print(f"  VI-C turnaround by T2: {vic['turned']} / {vic['rows']} "
          f"(not turned {vic['not_turned']})")
    for k, verdict in verdicts(res).items():
        print(f"    {k:34s} {verdict}")
    return verdicts(res)


def load_first_bad(path):
    """-> {seed: first_bad_row}.

    ⚠ A DISCARDED SEED IS GIVEN `first_bad` 0, NOT `None`.  `fz2e/509069` is
    the ledger's one `ps3_8080` discard: it is out of the denominator, so it
    has no `first_bad_row`, but its two columns diverge from end to end.
    Treating an absent `first_bad` as "clean everywhere" put all 41 of its
    write-T1 disagreements into the clean population and made the FLASH #20
    BASELINE read as a residue it does not have.  Measured, then fixed."""
    if not path:
        return {}
    j = json.loads(pathlib.Path(path).read_text())
    fb = {f["seed"]: f["first_bad_row"] for f in j["failures"]
          if f.get("first_bad_row") is not None}
    for d in j.get("discards") or []:
        fb[d["seed"]] = 0
    return fb


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cid", default="fz2c,fz2e")
    ap.add_argument("--before-suffix", default="-F20-archive",
                    help="the BEFORE campaign dir is <cid><suffix>")
    ap.add_argument("--after-suffix", default="")
    ap.add_argument("--ledger", default=None,
                    help="AFTER-era failure ledger, for the first_bad split")
    ap.add_argument("--null", type=int, default=0,
                    help="NON-VACUITY: perturb N write-T1 rows of the AFTER "
                         "core column and require the clauses to move")
    ap.add_argument("--self-test", action="store_true",
                    help="score the identity pair (BEFORE against itself) and "
                         "then the same pair with --null; both are printed")
    ap.add_argument("--json", default=None)
    a = ap.parse_args()

    cids = [c.strip() for c in a.cid.split(",") if c.strip()]
    first_bad = load_first_bad(a.ledger)

    before, after = {}, {}
    for c in cids:
        before.update(load_campaign(CAMPAIGNS / f"{c}{a.before_suffix}"))
        if a.self_test:
            after.update(load_campaign(CAMPAIGNS / f"{c}{a.before_suffix}"))
        else:
            after.update(load_campaign(CAMPAIGNS / f"{c}{a.after_suffix}"))

    if a.self_test:
        base = score(before, after, first_bad)
        report(base, "IDENTITY PAIR (before vs before)")
        kb = key_counts(base)
        n = perturb(after, a.null or 5)
        pert = score(before, after, first_bad)
        report(pert, f"NULL: {n} write-T1 rows perturbed")
        kp = key_counts(pert)
        moved = sum(1 for x, y in zip(kb, kp) if x != y)
        print(f"\n  clause COUNTS: base {kb}  null {kp}")
        print(f"  counts that MOVED under the null: {moved} / 5")
        print("  NON-VACUOUS" if moved == 5 else "  *** VACUOUS -- the scorer "
              "does not notice a perturbation on every clause")
        return 0 if moved == 5 else 2

    if a.null:
        n = perturb(after, a.null)
        print(f"== NON-VACUITY CONTROL: {n} write-T1 rows perturbed")
    res = score(before, after, first_bad)
    v = report(res, "FLASH #21 clauses (v) and (vi)")
    if a.json:
        p = pathlib.Path(a.json)
        p.parent.mkdir(parents=True, exist_ok=True)
        blob = json.dumps({"verdicts": v, "result": res}, indent=1, sort_keys=True)
        p.write_text(blob)
        print(f"  -> {p}  sha256 {hashlib.sha256(blob.encode()).hexdigest()[:16]}…")
    return 0 if all(x == "MET" for x in v.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
