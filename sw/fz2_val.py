#!/usr/bin/env python3
"""fz2_val -- AMENDMENT A-9's VALIDATION POPULATION for C-1's two rate clauses.

    python3 sw/fz2_val.py strata      # the registered grid (board-free)
    python3 sw/fz2_val.py freeze      # derive+build every seed, write the file
    python3 sw/fz2_val.py overlap     # 0-overlap, checked the way C-11 checks it
    python3 sw/fz2_val.py preflight --board
    python3 sw/fz2_val.py capture
    python3 sw/fz2_val.py score

WHY THIS FILE EXISTS.  `docs/notes/fz2_corpus_prereg_2026-08-08.md` §16 (A-5)
LOWERED C-1's two rate clauses -- soup 99.0 -> 90.0 %, raw 95.0 -> 75.0 % -- by
user decision, AFTER the corpus had measured them and ON the population that
produced the measurement.  `ucore_provenance.md` §64.1 says a replacement
chosen on the data that refuted its predecessor is FITTED and its score on that
data is not evidence, so `fz2_w1._c1_verdict` prints
`MET (rate clauses UNVALIDATED -- A-5)` and the numbers are not quotable.

§16.2 registered, IN ADVANCE, exactly what would lift that marker:

  * a DISJOINT population -- a k-block of this generator's seeds that is not
    one of the 3,840 in `SEED_LIST_SHA256`, drawn from the same strata by the
    same frozen rule;
  * size >= 480 seeds, split across BOTH TIERS so each clause is scored on its
    own mechanism (§5.2);
  * 0 seed overlap with either banked bank, checked the way C-11 checks it;
  * captured on the board BEFORE its terminator-reached rate is looked at;
  * scored AS WRITTEN, 90.0 and 75.0, with NO FURTHER ADJUSTMENT.

This file is that measurement and nothing else.  It designs no bar, it moves no
value, and it cannot: `E1` is IMPORTED from `fz2_w1`, so there is exactly one
place in the tree where those two numbers live and this scorer cannot hold a
different pair from the one the corpus scorer holds.

  > *"A guiding principal here needs to be simplicity.  This is 80's era
  > hardware, they aren't wasting silicon on anything that isn't necessary.
  > Complex or confusing behavior that we see is likely to be simple systems
  > interacting in ways you do not fully understand yet."*

THE GRID IS THE CENSUS GRID, MOVED.  Twelve strata -- tier x event class x
{fix0, wrand3, wvec-uni} -- at `k_base = 600000` instead of 400000, n = 80,
**960 seeds, 480 soup and 480 raw**.  §2.2 RESERVED `k >= 600000` for exactly
this ("any later directed or victory tranche draws from there and is therefore
disjoint from every seed above by construction"), so the disjointness is a
property of the layout and not of a rule somebody has to remember -- and it is
checked anyway, three independent ways, by `overlap`.

IT IS NOT BANKED, AND THAT IS DELIBERATE.  C-11 gates that the census bank IS
the 480 enumerated seeds and that the standing replayed bank is <= 3,500.  A
third promoted cid would move both.  This population exists to score two rates
off its own `results.jsonl`; `keep_rows_every` is 0 and `fuzz_bank.promote` is
never called on `fz2v`.  Every seed still self-classifies -- A-4's `stalled`
and A-7's `long_insn` are computed in `eval_case` from rows that are in hand,
not from banked ones -- so the residue can be reported without retaining a byte.

THE SCORER IS PROVED TO BE THE CORPUS'S OWN BEFORE IT SCORES ANYTHING.
`score` first re-computes the FOUR `pct` cells of the committed
`sw/testdata/fz2/fz2_bars.json` with the very function it is about to point at
`fz2v`, and REFUSES if any of them differs.  A validation measured with a
second, subtly different instrument would validate the instrument.

BOARD DISCIPLINE (CLAUDE.md), in code: single-writer asked of the board, socket
leg explicit through `fuzz_campaign.capture_board`, `div_guard` at every
stratum boundary with its readback recorded, no flashing, `board_idle()` with
`use_core=0` at the close, and a stratum that writes fewer lines than it was
asked for HALTS the driver.
"""
import argparse
import hashlib
import json
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

import fuzz_campaign as fzc                                # noqa: E402
import fz2_w1 as W                                         # noqa: E402

HOST = W.HOST
OUT = W.OUT
PREREG = W.PREREG

# --------------------------------------------------------------------------- #
# THE REGISTERED GRID -- prereg §23 (amendment A-9), which is §2.1's CENSUS
# grid at a different `k_base`.  Nothing here is a new design: the tiers, the
# event classes, the three census wait sources, `n = 80` and the 1,000-apart
# k-blocks are all §2.1/§2.2's, transcribed and then ASSERTED.
# --------------------------------------------------------------------------- #
VAL_CID = "fz2v"
VAL_K_BASE = 600000                    # §2.2's RESERVED band, by construction
VAL_POP = "val"


def strata():
    out, i = [], 0
    for tier in W.TIERS:
        for evt in W.EVTS:
            for src in W.WAITS["census"]:
                out.append({"pop": VAL_POP, "cid": VAL_CID, "i": i,
                            "tier": tier, "evt": evt, "src": src,
                            "n": W.N_PER,
                            "k_lo": VAL_K_BASE + W.K_STRIDE * i})
                i += 1
    return out


STRATA = strata()

# --- self-assertions.  A grid that has drifted from the document fails at
# --- import, not in a footnote.
assert len(STRATA) == 12, "2 tiers x 2 event classes x 3 census wait sources"
assert sum(s["n"] for s in STRATA) == 960
assert sum(s["n"] for s in STRATA if s["tier"] == "soup") == 480
assert sum(s["n"] for s in STRATA if s["tier"] == "raw") == 480
assert sum(s["n"] for s in STRATA) >= 480, "§16.2's registered minimum size"
assert STRATA[0]["k_lo"] == 600000 and STRATA[-1]["k_lo"] == 611000
assert all(s["n"] <= W.K_STRIDE for s in STRATA)
# §2.2 RESERVED k >= 600000 for exactly this, and the corpus asserts it cannot
# reach there.  Both halves are checked, here and in `fz2_w1`.
assert min(s["k_lo"] for s in STRATA) >= W.K_RESERVED
assert all(set(W.ov_of(st)) <= fzc.KNOWN_OV for st in STRATA)
# every wait source must leave a usable terminator delay, §3.2's floor
for _s in {s["src"] for s in STRATA}:
    _w = (int(_s[3:]) if _s.startswith("fix") else
          int(_s[5:]) if _s.startswith("wrand") else 8)
    assert W.term_clocks(_w) >= W.TERM_FLOOR


def seeds_of(st):
    return [st["k_lo"] + j for j in range(st["n"])]


def seed_list_sha256():
    keys = [f"{VAL_CID} {k}" for st in STRATA for k in seeds_of(st)]
    assert len(set(keys)) == 960
    return hashlib.sha256(("\n".join(keys) + "\n").encode()).hexdigest()


def label(st):
    return f"{st['pop']}/{st['tier']}/{st['evt']}/{st['src']}"


def _stratum_of(k):
    for j, st in enumerate(STRATA):
        if st["k_lo"] <= k < st["k_lo"] + st["n"]:
            return j
    return None


POP_PATH = OUT / "fz2v_population.json"
CAP_PATH = OUT / "fz2v_capture.json"
PRE_PATH = OUT / "fz2v_preflight.json"
SCORE_PATH = OUT / "fz2v_score.json"


# --------------------------------------------------------------------------- #
def cmd_strata(a):
    print("| i | pop | cid | tier | evt | wait | k range | n |")
    print("|---|---|---|---|---|---|---|---|")
    for st in STRATA:
        ks = seeds_of(st)
        print(f"| {st['i']} | {st['pop']} | {st['cid']} | {st['tier']} | "
              f"{st['evt']} | {st['src']} | {ks[0]}-{ks[-1]} | {st['n']} |")
    print(f"\nseeds: {sum(s['n'] for s in STRATA)}  "
          f"(soup {sum(s['n'] for s in STRATA if s['tier'] == 'soup')}, "
          f"raw {sum(s['n'] for s in STRATA if s['tier'] == 'raw')})")
    print(f"VAL_SEED_LIST_SHA256 = {seed_list_sha256()}")
    print(f"the clauses this population scores: soup >= {W.E1['soup']} %, "
          f"raw >= {W.E1['raw']} %  (imported from fz2_w1.E1)")
    return 0


# --------------------------------------------------------------------------- #
# freeze -- every seed named before it is generated, and before the board
# --------------------------------------------------------------------------- #
def _freeze_one(args):
    cid, k, j = args
    st = STRATA[j]
    cfg = fzc.derive_case(cid, k, W.ov_of(st))
    g = fzc.build(cfg)
    w = W.weff_of(cfg)
    e = cfg["evt"]
    img, _ = fzc.compose_case(g, cfg)
    return {"j": j, "cid": cid, "k": k, "tier": cfg["tier"],
            "cfg_hash": cfg["cfg_hash"], "nmax_eff": cfg["nmax_eff"],
            "weff": w, "term_clocks": W.term_clocks(w),
            "image_sha256": hashlib.sha256(bytes(img)).hexdigest(),
            "evt": None if not e else {"pin": e["pin"], "delay": e["delay"],
                                       "hold": e["hold"]},
            "wvec": cfg["wvec"], "waits": cfg["waits"],
            "has_tf": bool(g.get("has_tf")), "has_halt": bool(g.get("has_halt")),
            "raw_mode": g.get("raw_mode"), "n_ins": g["n_ins"]}


def cmd_freeze(a):
    from multiprocessing import Pool
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = [(VAL_CID, k, j) for j, st in enumerate(STRATA) for k in seeds_of(st)]
    t0 = time.time()
    rows = []
    with Pool(a.jobs) as pool:
        for r in pool.imap(_freeze_one, jobs, chunksize=16):
            rows.append(r)
    rows.sort(key=lambda r: (r["j"], r["k"]))
    assert len(rows) == 960
    seeds_sha = hashlib.sha256(
        json.dumps(rows, sort_keys=True).encode()).hexdigest()
    summ = {}
    for tier in W.TIERS:
        rs = [r for r in rows if r["tier"] == tier]
        summ[tier] = {
            "n": len(rs),
            "evt": sum(1 for r in rs if r["evt"]),
            "pin_int": sum(1 for r in rs if r["evt"] and r["evt"]["pin"] == 0),
            "pin_nmi": sum(1 for r in rs if r["evt"] and r["evt"]["pin"] == 1),
            "pin_poll": sum(1 for r in rs if r["evt"] and r["evt"]["pin"] == 2),
            "hold2": sum(1 for r in rs if r["evt"] and r["evt"]["hold"] == 2),
            "hold300": sum(1 for r in rs if r["evt"] and r["evt"]["hold"] == 300),
            "has_tf": sum(1 for r in rs if r["has_tf"]),
            "has_halt": sum(1 for r in rs if r["has_halt"]),
            "raw_whole": sum(1 for r in rs if r["raw_mode"] == "whole"),
            "term_clocks_min": min(r["term_clocks"] for r in rs),
            "term_clocks_max": max(r["term_clocks"] for r in rs),
        }
    blob = {"stage": "fz2 A-9 validation freeze", "prereg": PREREG.name,
            "amendment": "A-9 (prereg §23)",
            "gen_git": fzc._gen_git(),
            "cid": VAL_CID, "k_base": VAL_K_BASE,
            "seeds_sha256": seeds_sha,
            "val_seed_list_sha256": seed_list_sha256(),
            "corpus_seed_list_sha256": W.seed_list_sha256(),
            "e1_scored_at": dict(W.E1),
            "cap_rows": W.CAP_ROWS, "anchor_w0": W.ANCHOR_W0,
            "dump_w0": W.DUMP_W0, "entry_max": W.ENTRY_MAX,
            "term_margin": W.TERM_MARGIN, "nmax_scale_c": fzc.NMAX_SCALE_C,
            "strata": [{**st, "ks": [seeds_of(st)[0], seeds_of(st)[-1]]}
                       for st in STRATA],
            "summary": summ,
            "seeds": rows}
    txt = json.dumps(blob, sort_keys=True, indent=1)
    POP_PATH.write_text(txt)
    sha = hashlib.sha256(txt.encode()).hexdigest()
    (OUT / "fz2v_population.sha256").write_text(f"{sha}  {POP_PATH.name}\n")
    print(f"froze {len(rows)} seeds in {time.time()-t0:.1f}s -> {POP_PATH}")
    print(f"  file sha256          {sha}   (moves with gen_git -- not the name)")
    print(f"  seeds_sha256         {seeds_sha}")
    print(f"  val_seed_list_sha256 {blob['val_seed_list_sha256']}")
    for tier in W.TIERS:
        print(f"  {tier:<5} {json.dumps(summ[tier])}")
    return 0


# --------------------------------------------------------------------------- #
# overlap -- §16.2's "0 seed overlap, checked the way C-11 checks it"
# --------------------------------------------------------------------------- #
def cmd_overlap(a):
    """THREE INDEPENDENT CHECKS, because one of them is the one C-11 makes and
    the other two are stronger.

      1. the `(cid, k)` KEY, which is what C-11 intersects (`banked['census']`
         vs `banked['enriched']`) -- against BOTH banked banks and against the
         whole frozen 3,840;
      2. the RAW k, ignoring the cid, so a future reader who forgets that the
         cid is part of the seed still sees a disjoint block;
      3. the composed IMAGE sha256, which is the only one that could catch two
         different keys deriving the same case.  It is not opt-in: 4,800
         recompositions cost about ten seconds and "the two populations are the
         same seeds under different names" is the failure this exists to
         exclude.

    ⚠ `cfg_hash` IS NOT A SEED IDENTITY AND IS NOT SCORED HERE.  It is
    `derive_case`'s hash of the CONFIGURATION AXES (`fuzz_campaign.py:264`) --
    tier, waits, nmax, evt, wvec -- while the program comes from
    `build`'s own RNG keyed on the string `f"{cid}/{k}"`.  Two seeds with the
    same axes therefore SHARE a `cfg_hash` by construction, and the corpus does
    it to itself: the frozen 3,840 carry only 2,969 distinct `cfg_hash`es.
    A `cfg_hash` intersection is REPORTED, with the corpus's own internal
    collision count beside it as the control that says what it means, and it
    does not fail this command.  (It was written as a FAIL condition first and
    fired at 36; the control is what showed the check, not the population, was
    wrong.)
    """
    if not POP_PATH.exists():
        print(f"overlap: {POP_PATH} missing -- run `freeze` first")
        return 2
    val = json.loads(POP_PATH.read_text())
    corp = json.loads((OUT / "fz2_population.json").read_text())
    hits = 0
    vkeys = {(VAL_CID, r["k"]) for r in val["seeds"]}
    ckeys = {(r["cid"], r["k"]) for r in corp["seeds"]}
    banked = {}
    for cid in ("fz2c", "fz2e"):
        d = ROOT / "tests" / "v30" / "fuzz_bank" / cid / "seeds"
        banked[cid] = {(cid, int(p.name.split("_")[1]))
                       for p in d.glob("*.json.gz")} if d.exists() else set()
    rec = {"stage": "fz2v overlap", "checks": {}}

    def chk(name, n, detail=""):
        nonlocal hits
        ok = (n == 0)
        hits += 0 if ok else 1
        rec["checks"][name] = {"overlap": n, "detail": detail}
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {n}{('  ' + detail) if detail else ''}")

    print(f"== §16.2 disjointness: {len(vkeys)} validation seeds")
    chk("(cid,k) vs the frozen 3,840", len(vkeys & ckeys))
    chk("(cid,k) vs the banked fz2c bank", len(vkeys & banked["fz2c"]),
        f"bank {len(banked['fz2c'])}")
    chk("(cid,k) vs the banked fz2e bank", len(vkeys & banked["fz2e"]),
        f"bank {len(banked['fz2e'])}")
    chk("raw k (cid ignored) vs the frozen 3,840",
        len({r['k'] for r in val['seeds']} & {r['k'] for r in corp['seeds']}))
    # the frozen corpus file carries no image hashes; recompose all 3,840
    from multiprocessing import Pool                          # noqa: PLC0415
    jobs = [(r["cid"], r["k"], W._stratum_of(r["cid"], r["k"]))
            for r in corp["seeds"]]
    with Pool(a.jobs) as pool:
        cimgs = set(pool.map(_corpus_img, jobs, chunksize=32))
    vimgs = {r["image_sha256"] for r in val["seeds"]}
    chk("composed image sha256 vs the frozen 3,840", len(vimgs & cimgs),
        f"{len(cimgs)} distinct corpus images, {len(vimgs)} distinct here")
    chk("the validation images are all distinct", 960 - len(vimgs))
    chk("the validation block is below no corpus k",
        sum(1 for r in val["seeds"] if r["k"] < W.K_RESERVED),
        f"K_RESERVED={W.K_RESERVED}")
    # REPORTED, NEVER SCORED -- see the docstring.  The control is the corpus's
    # own internal collision count, which says what a `cfg_hash` intersection
    # is worth as evidence: nothing.
    cf_v = {r["cfg_hash"] for r in val["seeds"]}
    cf_c = {r["cfg_hash"] for r in corp["seeds"]}
    rec["cfg_hash_observation"] = {
        "shared": len(cf_v & cf_c), "val_distinct": len(cf_v),
        "corpus_distinct": len(cf_c), "corpus_seeds": len(corp["seeds"]),
        "corpus_internal_collisions": len(corp["seeds"]) - len(cf_c)}
    print(f"  [note ] cfg_hash shared with the corpus: {len(cf_v & cf_c)} "
          f"-- NOT a seed identity: the corpus's own 3,840 seeds carry only "
          f"{len(cf_c)} distinct cfg_hashes "
          f"({len(corp['seeds']) - len(cf_c)} internal collisions)")
    rec["hits"] = hits
    print(f"\nFZ2V OVERLAP {'PASS' if hits == 0 else 'FAIL'}: {hits} hit(s)")
    return 0 if hits == 0 else 1


def _corpus_img(args):
    cid, k, j = args
    cfg = fzc.derive_case(cid, k, W.ov_of(W.STRATA[j]))
    img, _ = fzc.compose_case(fzc.build(cfg), cfg)
    return hashlib.sha256(bytes(img)).hexdigest()


# --------------------------------------------------------------------------- #
# preflight
# --------------------------------------------------------------------------- #
def cmd_preflight(a):
    OUT.mkdir(parents=True, exist_ok=True)
    rec = {"stage": "fz2v preflight", "host": HOST,
           "gen_git": fzc._gen_git(),
           "val_seed_list_sha256": seed_list_sha256(),
           "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "div_guards": []}
    ok = True

    print("== capture-path preconditions (prereg §7)")
    gaps = W.capture_path_gaps()
    rec["capture_path_gaps"] = [{"item": i, "detail": d} for i, d in gaps]
    for i, d in gaps:
        print(f"  *** MISSING: {i} -- {d}")
    if gaps:
        ok = False
    else:
        print("  all capture-path preconditions present")

    print("== the frozen population, committed BEFORE this capture")
    if not POP_PATH.exists():
        ok = False
        print(f"  *** {POP_PATH} is missing -- run `freeze`")
    else:
        pop = json.loads(POP_PATH.read_text())
        rec["population"] = {k: pop.get(k) for k in
                             ("seeds_sha256", "val_seed_list_sha256",
                              "gen_git", "e1_scored_at")}
        if pop.get("val_seed_list_sha256") != seed_list_sha256():
            ok = False
            print("  *** the frozen file is a DIFFERENT population from this code")
        if pop.get("e1_scored_at") != dict(W.E1):
            ok = False
            print(f"  *** the frozen file was written against E1 "
                  f"{pop.get('e1_scored_at')}, the tree holds {dict(W.E1)} -- "
                  f"§16.2 forbids a second re-registration")
        rc = subprocess.run(["git", "status", "--porcelain", str(POP_PATH)],
                            cwd=ROOT, capture_output=True, text=True)
        rec["population_committed"] = (rc.stdout.strip() == "")
        if rc.stdout.strip():
            ok = False
            print(f"  *** the frozen population is NOT committed: "
                  f"{rc.stdout.strip()!r}")
        else:
            print("  the frozen population is committed and matches this code")

    if a.board:
        print("== single-writer / reachability")
        rc, up, err = W._ssh("uptime")
        rec["uptime"] = up if rc == 0 else f"UNREACHABLE rc={rc} {err[:120]}"
        print(f"  uptime: {rec['uptime']}")
        if rc != 0:
            rec["single_writer"] = "UNKNOWN (unreachable)"
            ok = False
        else:
            rc, ps, _ = W._ssh(
                "ps w | grep -E 'v30ctl|serve' | grep -v grep || true")
            others = [l for l in ps.splitlines() if l.strip()]
            rec["board_procs"] = others
            rec["single_writer"] = "VIOLATED" if others else "OK"
            if others:
                ok = False
                for l in others:
                    print(f"    {l}")
            else:
                print("  no v30/serve process on the board -> SINGLE WRITER")
        lp = subprocess.run(["bash", "-lc",
                             "pgrep -af '[v]30ctl.py serve' || true"],
                            capture_output=True, text=True).stdout.strip()
        rec["local_serve_procs"] = [l for l in lp.splitlines() if l.strip()]
        if rec["local_serve_procs"]:
            ok = False
            print(f"  *** local serve client(s) running: "
                  f"{rec['local_serve_procs']} ***")

    print("== era / flash pin")
    flash = fzc._last_flash_entry()
    rec["flash_log_tail"] = {k: (flash or {}).get(k)
                             for k in ("sha256", "ts", "git_describe", "verify")}
    rig = W.resident_rig_gap()
    rec["resident_rig"] = rig
    if rig.get("gap"):
        ok = False
        print(f"  *** the RESIDENT bitstream does not carry this tree's rig "
              f"RTL: {rig['why']}")
        for f, tree, built in rig["gap"]:
            print(f"      {f}: tree {tree[:12]}… built-from {str(built)[:12]}…")
    else:
        print(f"  resident bitstream carries this tree's rig RTL ({rig['why']})")
    mp = fzc.CAMPAIGNS / VAL_CID / "manifest.json"
    if not mp.exists():
        ok = False
        rec["manifest"] = None
        print(f"  *** no manifest for {VAL_CID} -- "
              f"`python3 sw/fuzz_campaign.py new {VAL_CID}`")
    else:
        man = json.loads(mp.read_text())
        era = fzc.era_of(man)
        rec["manifest"] = era
        if (flash or {}).get("sha256") != (man.get("flash_pin") or {}).get("sha256"):
            ok = False
            print(f"  *** {VAL_CID}: flash pin MISMATCH against flash_log tail")
        for k in ("sof_sha256", "gen_git", "rig_evt_hold_bits"):
            if era.get(k) in (None, ""):
                ok = False
                print(f"  *** {VAL_CID}: era field ABSENT: {k}")
        if not era["rtl"]["inputs_sha256"]:
            ok = False
            print(f"  *** {VAL_CID}: no quartus receipt carries the pinned .sof")
        else:
            print(f"  era: sof {era['sof_sha256'][:12]}… receipt "
                  f"{str(era['rtl']['receipt_id'])[:12]}… "
                  f"({era['rtl']['n_files']} files) gen_git {era['gen_git']}")

    print(f"== generation / regeneration sample ({a.sample} per stratum)")
    hits = 0
    per = []
    for j, st in enumerate(STRATA):
        ov = W.ov_of(st)
        step = max(1, st["n"] // a.sample)
        ks = [st["k_lo"] + x for x in range(0, st["n"], step)][:a.sample]
        npair = 0
        for k in ks:
            cfg = fzc.derive_case(VAL_CID, k, ov)
            img, _ = fzc.compose_case(fzc.build(cfg), cfg)
            sha = hashlib.sha256(bytes(img)).hexdigest()
            cfg2 = fzc.derive_case(VAL_CID, k, ov)
            img2, _ = fzc.compose_case(fzc.build(cfg2), cfg2)
            if sha != hashlib.sha256(bytes(img2)).hexdigest():
                hits += 1
                print(f"  GEN_DRIFT {label(st)}/{k}")
            npair += fzc.bad_0f_pairs(img)
            if cfg["tier"] != st["tier"]:
                hits += 1
                print(f"  TIER WRONG {label(st)}/{k}")
            if (cfg["evt"] is None) != (st["evt"] == "noevt"):
                hits += 1
                print(f"  EVT CLASS WRONG {label(st)}/{k}: {cfg['evt']}")
            if W.term_clocks(W.weff_of(cfg)) < W.TERM_FLOOR:
                hits += 1
                print(f"  TERM_CLOCKS FLOOR {label(st)}/{k}")
        if npair:
            hits += 1
            print(f"  0F PAIRS {label(st)}: {npair}")
        per.append({"j": j, "stratum": label(st), "sampled": len(ks),
                    "bad_0f_pairs": npair})
    rec["regen_sample"] = {"per_stratum": per, "hits": hits,
                           "seeds": sum(p["sampled"] for p in per)}
    print(f"  {rec['regen_sample']['seeds']} seeds, hits={hits}")
    ok = ok and hits == 0

    if a.board:
        print("== board health")
        W.div_guard("fz2v-preflight", rec["div_guards"])
        try:
            regs = W.v30run._runners[HOST].rig_readback_check()
            rec["rig_readback_check"] = {"ok": True, "registers": regs}
            print(f"  rig_readback_check: {len(regs)} registers round-tripped")
        except Exception as e:                              # noqa: BLE001
            ok = False
            rec["rig_readback_check"] = {"ok": False, "error": str(e)[:300]}
            print(f"  *** rig_readback_check FAILED: {str(e)[:200]}")
        r = subprocess.run([sys.executable, str(SW / "check_ab_hw.py"), "all",
                            "800", "--host", HOST],
                           capture_output=True, text=True, timeout=900)
        tail = (r.stdout + r.stderr).strip().splitlines()
        rec["check_ab_hw"] = {"rc": r.returncode, "tail": tail[-12:]}
        for l in tail[-12:]:
            print(f"  {l}")
        if r.returncode != 0:
            ok = False
            print("  *** check_ab_hw FAILED ***")
        W.div_guard("fz2v-preflight-end", rec["div_guards"])
        W.board_idle()
        print("  board left use_core=0 (board_idle)")
    rec["board_leg"] = bool(a.board)
    rec["verdict"] = "OK" if ok else "BLOCKED"
    PRE_PATH.write_text(json.dumps(rec, indent=1))
    print(f"\nFZ2V PREFLIGHT: {rec['verdict']}  -> {PRE_PATH}")
    return 0 if ok else 1


# --------------------------------------------------------------------------- #
# capture
# --------------------------------------------------------------------------- #
def _preflight_ok():
    if not PRE_PATH.exists():
        return False, "no fz2v_preflight.json -- run `preflight --board` first"
    d = json.loads(PRE_PATH.read_text())
    if d.get("verdict") != "OK":
        return False, f"preflight verdict is {d.get('verdict')!r}"
    if d.get("val_seed_list_sha256") != seed_list_sha256():
        return False, "preflight was taken against a DIFFERENT population"
    if d.get("gen_git") != fzc._gen_git():
        return False, (f"preflight was taken at {d.get('gen_git')}, tree is "
                       f"{fzc._gen_git()}")
    if not d.get("board_leg"):
        return False, "preflight did not run its board leg"
    return True, "ok"


def cmd_capture(a):
    OUT.mkdir(parents=True, exist_ok=True)
    gaps = W.capture_path_gaps()
    if gaps:
        print("capture: REFUSED -- capture-path preconditions unmet:")
        for i, d in gaps:
            print(f"  {i}: {d}")
        return 2
    good, why = _preflight_ok()
    if not good:
        print(f"capture: REFUSED -- {why}")
        return 2
    rec = {"stage": "fz2v capture", "host": a.host, "cid": VAL_CID,
           "val_seed_list_sha256": seed_list_sha256(),
           "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "strata": [], "div_guards": []}
    t_all = time.time()
    halted = None
    for st in STRATA:
        done = W._done_ks(VAL_CID)
        ks = seeds_of(st)
        missing = [k for k in ks if k not in done]
        if not missing:
            print(f"== {label(st):<26} already complete, skipped")
            rec["strata"].append({"stratum": label(st), "n": st["n"],
                                  "written": st["n"], "skipped": True})
            continue
        start, n = missing[0], missing[-1] - missing[0] + 1
        print(f"\n== {label(st):<26} k [{start},{start+n}) n={n}", flush=True)
        W.div_guard(f"{VAL_CID}-{st['i']:02d}-{label(st)}", rec["div_guards"])
        t0 = time.time()
        # `_run_args` is fz2_w1's -- ONE implementation of the invocation, not
        # two.  `pop` is not "census", so `keep_rows_every` is 0: this
        # population is scored off its result lines and is never banked.
        rc = fzc.cmd_run(W._run_args(st, start, n, a.host))
        dt = time.time() - t0
        written = sum(1 for k in ks if k in W._done_ks(VAL_CID))
        rec["strata"].append({"stratum": label(st), "cid": VAL_CID,
                              "k_lo": st["k_lo"], "n": st["n"],
                              "written": written, "rc": rc,
                              "seconds": round(dt, 1),
                              "rate": round(n / max(1e-6, dt), 2)})
        rec["board_seconds"] = round(time.time() - t_all, 1)
        CAP_PATH.write_text(json.dumps(rec, indent=1))
        print(f"  {label(st)}: {written}/{st['n']} in {dt:.1f}s rc={rc}")
        if written < st["n"] or rc != 0:
            halted = (f"{label(st)} wrote {written}/{st['n']} rc={rc} "
                      f"-- STOPPED, not nursed")
            print(f"\n*** {halted} ***")
            break
    rec["board_seconds"] = round(time.time() - t_all, 1)
    rec["halted"] = halted
    rec["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    CAP_PATH.write_text(json.dumps(rec, indent=1))
    tot = sum(s["written"] for s in rec["strata"])
    print(f"\nFZ2V CAPTURE: {tot} seeds in {rec['board_seconds']/60:.1f} min"
          f"{'  HALTED: ' + halted if halted else ''}")
    return 1 if halted else 0


# --------------------------------------------------------------------------- #
# score -- the two rate clauses, AS REGISTERED, and nothing else
# --------------------------------------------------------------------------- #
def _rate(lines, tier_of):
    """C-1's rate arithmetic, and it is `fz2_w1.cmd_bars`' arithmetic: the
    per-TIER terminator-reached fraction over the FULL stratum, discards
    included (§5.3: "per population, over the FULL stratum")."""
    out = {}
    for tier in W.TIERS:
        sel = [r for r in lines if tier_of(r) == tier]
        ok = sum(1 for r in sel if r.get("arch_ok"))
        out[tier] = {"n": len(sel), "reached": ok,
                     "pct": round(100.0 * ok / len(sel), 2) if sel else None}
    return out


def _mirror_check():
    """THE INSTRUMENT IS PROVED TO BE THE CORPUS'S BEFORE IT IS POINTED AT THE
    VALIDATION POPULATION.  `_rate` is re-run over `fz2c` and `fz2e` and its
    four `pct` cells are compared against the COMMITTED `fz2_bars.json`.  A
    validation measured with a second, subtly different scorer would be
    validating the scorer."""
    p = OUT / "fz2_bars.json"
    if not p.exists():
        return False, {"why": "fz2_bars.json absent"}
    want = json.loads(p.read_text())["bars"]["C-1"]["measured"]["per_tier"]
    got, bad = {}, []
    for pop in W.POPS:
        cid = W.CID[pop]
        lines = W._lines(cid)

        def tier_of(r, cid=cid):
            j = W._stratum_of(cid, r["k"])
            return None if j is None else W.STRATA[j]["tier"]
        for tier, v in _rate(lines, tier_of).items():
            key = f"{pop}/{tier}"
            got[key] = v
            w = want.get(key, {})
            if (v["pct"], v["reached"], v["n"]) != (w.get("pct"),
                                                    w.get("reached"),
                                                    w.get("n")):
                bad.append({"cell": key, "recomputed": v,
                            "committed": {k: w.get(k) for k in
                                          ("n", "reached", "pct")}})
    return not bad, {"cells": got, "disagreements": bad}


def cmd_score(a):
    OUT.mkdir(parents=True, exist_ok=True)
    lines = W._lines(VAL_CID)
    if not lines:
        print(f"score: no results for {VAL_CID} -- run `capture` first")
        return 2

    print("== the scorer is the corpus's own (mirror check against "
          "fz2_bars.json)")
    mok, mdet = _mirror_check()
    for c, v in sorted(mdet.get("cells", {}).items()):
        print(f"  {c:<16} {v['reached']}/{v['n']} = {v['pct']} %")
    if not mok:
        print("  *** MIRROR CHECK FAILED -- this scorer does not reproduce the "
              "committed corpus figures.  REFUSING to score.")
        for b in mdet.get("disagreements", []):
            print(f"      {b}")
        return 2
    print("  PASS: all four committed C-1 cells reproduced exactly")

    def tier_of(r):
        j = _stratum_of(r["k"])
        return None if j is None else STRATA[j]["tier"]

    rates = _rate(lines, tier_of)
    per = []
    for j, st in enumerate(STRATA):
        ks = set(seeds_of(st))
        got = [r for r in lines if r["k"] in ks]
        per.append({"j": j, "stratum": label(st), "n": st["n"],
                    "captured": len(got),
                    "reached": sum(1 for r in got if r.get("arch_ok")),
                    "rows_exact": sum(1 for r in got
                                      if r.get("bad_rows") == 0),
                    "arch_exact": sum(1 for r in got
                                      if r.get("arch_match") is True),
                    "verdicts": dict(Counter(r["verdict"] for r in got))})

    # the declared discard classes and the residue, REPORTED (E-1c is NOT a
    # clause this population scores -- §16.2 registers the two RATE clauses and
    # only those -- but a rate quoted without its residue is half a number)
    disc = Counter()
    undisp = 0
    for r in lines:
        if r.get("arch_ok"):
            continue
        named = False
        for cls in ("arch_restart", "ps3_8080", "wrote_term", "stalled",
                    "long_insn"):
            if r.get(cls):
                disc[cls] += 1
                named = True
        if not named:
            undisp += 1
            disc["UNDISPOSITIONED"] += 1

    clauses = {}
    for tier in W.TIERS:
        bar = W.E1[tier]
        v = rates[tier]
        clauses[tier] = {"registered": bar, "measured_pct": v["pct"],
                         "reached": v["reached"], "n": v["n"],
                         "verdict": ("MET" if (v["pct"] is not None
                                               and v["pct"] >= bar)
                                     else "MISSED")}
    validated = all(c["verdict"] == "MET" for c in clauses.values())

    cap = json.loads(CAP_PATH.read_text()) if CAP_PATH.exists() else {}
    pre = json.loads(PRE_PATH.read_text()) if PRE_PATH.exists() else {}
    guards = pre.get("div_guards", []) + cap.get("div_guards", [])
    rec = {"stage": "fz2v score (prereg §16.2 / A-9)",
           "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "cid": VAL_CID, "captured": len(lines),
           "val_seed_list_sha256": seed_list_sha256(),
           "e1_registered": dict(W.E1), "e1_prior": dict(W.E1_PRIOR),
           "mirror_check": {"pass": mok, **mdet},
           "clauses": clauses, "validated": validated,
           "per_stratum": per,
           "discards": dict(disc), "undispositioned": undisp,
           "quarantines": sum(1 for r in lines
                              if r["verdict"] == "QUARANTINE"),
           "div_guards": len(guards),
           "div_guards_unpinned": [g for g in guards
                                   if g["state"] != "PINNED"],
           "halted": cap.get("halted"),
           "board_seconds": cap.get("board_seconds")}
    SCORE_PATH.write_text(json.dumps(rec, indent=1))

    print(f"\n== the A-9 validation population, {len(lines)} seeds captured")
    print(f"{'stratum':<28} {'cap':>4} {'reached':>7} {'rows=':>6} {'arch=':>6}")
    for p in per:
        print(f"{p['stratum']:<28} {p['captured']:>4} {p['reached']:>7} "
              f"{p['rows_exact']:>6} {p['arch_exact']:>6}")
    print(f"\n{'clause':<10} {'measured':>22} {'registered':>12}   verdict")
    for tier in W.TIERS:
        c = clauses[tier]
        print(f"E-1{'a' if tier == 'soup' else 'b'} {tier:<5} "
              f"{c['reached']:>6}/{c['n']} = {c['measured_pct']:>6} % "
              f"{'>= ' + str(c['registered']) + ' %':>12}   {c['verdict']}")
    print(f"\ndiscards (reported, not scored): {dict(disc)}   "
          f"undispositioned {undisp}")
    print(f"\nFZ2V VALIDATION: {'PASS' if validated else 'FAIL'}  -> "
          f"{SCORE_PATH}")
    if validated:
        print("  Both re-registered rate clauses hold on a population that was "
              "not used to select them (§16.2).  The `UNVALIDATED` marker may "
              "come off.")
    else:
        print("  A-5's re-registration is REFUTED on its first disjoint "
              "measurement.  The `UNVALIDATED` marker STAYS, and no adjustment "
              "is permitted (§16.2).")
    return 0 if validated else 1


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("strata")
    p.set_defaults(func=cmd_strata)
    p = sub.add_parser("freeze")
    p.add_argument("--jobs", type=int, default=4)
    p.set_defaults(func=cmd_freeze)
    p = sub.add_parser("overlap")
    p.add_argument("--jobs", type=int, default=8)
    p.set_defaults(func=cmd_overlap)
    p = sub.add_parser("preflight")
    p.add_argument("--sample", type=int, default=4)
    p.add_argument("--board", action="store_true")
    p.set_defaults(func=cmd_preflight)
    p = sub.add_parser("capture")
    p.add_argument("--host", default=HOST)
    p.set_defaults(func=cmd_capture)
    p = sub.add_parser("score")
    p.set_defaults(func=cmd_score)
    a = ap.parse_args()
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
