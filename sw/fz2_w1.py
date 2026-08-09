#!/usr/bin/env python3
"""fz2_w1 -- the CAPTURE DRIVER for the fuzz-v2 corpus (plan Phase 5, task T10).

It executes `docs/notes/fz2_corpus_prereg_2026-08-08.md` AS REGISTERED and
scores that document's capture-integrity bars C-1 .. C-11.  It designs nothing:
the 48 strata, their sizes, their k-blocks, the two populations, the E-1
containment values and the bars all come from the pre-registration, which is
committed before any generation at scale and before any board contact.

> *"A guiding principal here needs to be simplicity.  This is 80's era
> hardware, they aren't wasting silicon on anything that isn't necessary.
> Complex or confusing behavior that we see is likely to be simple systems
> interacting in ways you do not fully understand yet."*

TWO POPULATIONS, NEVER POOLED, AND THE SEPARATION IS STRUCTURAL:

  * **CENSUS** (`cid = fz2c`, 12 strata x 80 = 960 seeds).  Promoted into the
    bank by a FROZEN ARITHMETIC RULE -- every second k of every stratum, 480
    seeds, chosen before the first capture and independent of every verdict.
    Its rates are POPULATION rates because nothing selects on the outcome.
  * **ENRICHED** (`cid = fz2e`, 36 strata x 80 = 2,880 seeds).  Banked under
    `fuzz_bank.promote`'s existing divergence-driven quota rule, as an ADDITIVE
    regression corpus.  Its rates are NOT population rates and this driver
    refuses to compute one.

They are different campaign ids with disjoint k-blocks, so "never pooled" is a
property of the layout rather than a rule somebody has to remember.

BOARD DISCIPLINE (CLAUDE.md), in code and not in a comment:
  * SOCKET FIRST, and the A/B pair differs in `use_core` and in NOTHING else --
    `fuzz_campaign.capture_board` is the inherited primitive and is not
    re-implemented here.
  * THE DIVIDER IS PINNED and the runner's own `div_readback` is RECORDED at
    every stratum boundary.  An UNPINNED readback is a rig-integrity FINDING,
    printed and banked, never smoothed.
  * NO FLASHING.  The resident bitstream is the pin in the campaign manifest
    and `fuzz_campaign run` REFUSES if `flash_log`'s tail has moved off it.
  * `board_idle()` at the close, with `use_core=0` left selected.
  * A wedge STOPS the session; it is not nursed along.  `cmd_run`'s own
    circuit breaker (>= 5 consecutive quarantines) is left armed, and a stratum
    that writes fewer lines than it was asked for HALTS this driver.

RESUME IS BY `_done_ks()` -- every k actually present in `results.jsonl` --
and NOT by `fuzz_campaign._resume_k`, which returns `max(k) + 1` and would
silently skip every unwritten k below the highest one in a block-stratified
corpus.

Subcommands:
  strata      print the registered stratification (board-free)
  freeze      enumerate + derive + build EVERY seed, write the frozen
              population file and its sha256 (board-free)
  lint        prove the DOCUMENT and THIS CODE cannot disagree (board-free)
  preflight   single-writer, era/flash pin, offline regeneration, and the
              CAPTURE-PATH PRECONDITIONS -- everything that must be true
              before board time is spent
  capture     the 48 strata, in the registered k-blocks, in order
  stability   the C-9 sub-sample: 192 seeds x 3 repetitions
  control     the C-6 board control legs (>=2 TVEC values, >=2 hold values,
              the vecsub_en=0 negative control)
  bars        score C-1 .. C-11 from the banked results, OFFLINE
  idle        board_idle() + a closing div_guard readback
"""
import argparse
import gzip
import hashlib
import inspect
import json
import re
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

import check_seq                                          # noqa: E402
import fuzz_campaign as fzc                               # noqa: E402
import fuzz_classify as fc                                # noqa: E402
import fz2_longinsn                                        # noqa: E402
import fz2_stall                                          # noqa: E402
import testimage as ti                                    # noqa: E402
import v30ctl                                             # noqa: E402
import v30run                                             # noqa: E402
import wvec_shapes as wv                                  # noqa: E402

HOST = "root@mister-nec"
OUT = SW / "testdata" / "fz2"
PREREG = ROOT / "docs" / "notes" / "fz2_corpus_prereg_2026-08-08.md"

# --------------------------------------------------------------------------- #
# THE REGISTERED STRATIFICATION -- prereg §2, transcribed and then ASSERTED.
# Two populations, one grid rule each: tier x event class x wait source.
# --------------------------------------------------------------------------- #
CID = {"census": "fz2c", "enriched": "fz2e"}
K_BASE = {"census": 400000, "enriched": 500000}
K_STRIDE = 1000
K_RESERVED = 600000              # nothing in this corpus may use k >= this
N_PER = 80

TIERS = ("soup", "raw")
EVTS = ("noevt", "stim")
WAITS = {
    "census": ("fix0", "wrand3", "wvec-uni"),
    "enriched": ("fix0", "fix1", "fix2", "fix3",
                 "wrand1", "wrand3", "wrand7", "wrand15", "wvec-uni"),
}
POPS = ("census", "enriched")


def strata():
    """The 48 strata, in the registered order.  Population-major, then tier,
    then event class, then wait source; block `i` of a population starts at
    `K_BASE[pop] + K_STRIDE * i`."""
    out = []
    for pop in POPS:
        i = 0
        for tier in TIERS:
            for evt in EVTS:
                for src in WAITS[pop]:
                    out.append({"pop": pop, "cid": CID[pop], "i": i,
                                "tier": tier, "evt": evt, "src": src,
                                "n": N_PER,
                                "k_lo": K_BASE[pop] + K_STRIDE * i})
                    i += 1
    return out


STRATA = strata()

# --- the self-assertions.  A grid that has drifted from the document fails
# --- at import, not in a footnote.
assert len(STRATA) == 48, "2 populations, 2 tiers x 2 event classes x (3|9) waits"
_CEN = [s for s in STRATA if s["pop"] == "census"]
_ENR = [s for s in STRATA if s["pop"] == "enriched"]
assert len(_CEN) == 12 and len(_ENR) == 36
assert sum(s["n"] for s in _CEN) == 960, "the registered census is 960 seeds"
assert sum(s["n"] for s in _ENR) == 2880, "the registered enriched set is 2,880"
assert sum(s["n"] for s in STRATA) == 3840
assert _CEN[0]["k_lo"] == 400000 and _CEN[-1]["k_lo"] == 411000
assert _ENR[0]["k_lo"] == 500000 and _ENR[-1]["k_lo"] == 535000
assert all(s["n"] <= K_STRIDE for s in STRATA), "a stratum must fit its block"
assert max(s["k_lo"] + s["n"] for s in STRATA) < K_RESERVED


def seeds_of(st):
    return [st["k_lo"] + j for j in range(st["n"])]


def _all_seed_keys():
    return [f"{st['cid']} {k}" for st in STRATA for k in seeds_of(st)]


def seed_list_sha256():
    """The canonical name of the whole corpus: sha256 over `<cid> <k>` lines in
    the registered order.  The document carries this number, and `lint` proves
    the document and this code agree on it."""
    return hashlib.sha256(("\n".join(_all_seed_keys()) + "\n").encode()).hexdigest()


# the two populations are disjoint seed for seed, by construction and by test
assert len(set(_all_seed_keys())) == 3840
assert not ({k for st in _CEN for k in seeds_of(st)} &
            {k for st in _ENR for k in seeds_of(st)})


def label(st):
    return f"{st['pop'][:3]}/{st['tier']}/{st['evt']}/{st['src']}"


def ov_of(st):
    """The overrides for one stratum -- prereg §2.4's invocation, in code.
    Every key is one `fuzz_campaign.KNOWN_OV` accepts; an unknown key RAISES
    there rather than being accepted-and-ignored."""
    ov = {"force_tier": st["tier"]}
    ov["no_evt" if st["evt"] == "noevt" else "force_evt"] = True
    src = st["src"]
    if src.startswith("fix"):
        ov["force_fixed"] = int(src[3:])
    elif src.startswith("wrand"):
        ov["force_wrand"] = [int(src[5:])]
    elif src.startswith("wvec-"):
        ov["wvec_shapes"] = [src[5:]]
    else:
        raise ValueError(src)
    return ov


# every override this corpus uses must be one `derive_case` KNOWS; an unknown
# key raises there, but a RENAMED one would only raise at capture time, which
# is after board time has been spent
assert all(set(ov_of(st)) <= fzc.KNOWN_OV for st in STRATA), \
    "an override key this corpus needs is not in fuzz_campaign.KNOWN_OV"


# --------------------------------------------------------------------------- #
# TERM_CLOCKS -- the terminating NMI's delay after the anchor, prereg §3.2 as
# AMENDED BY A-3 (§13).
#
# ONE FORMULA, reusing the capture budget's OWN coupling constant
# (`NMAX_SCALE_C`): the bus-cycle costs scale, so the reserve does too, and the
# NMI acceptance latency -- a CLOCK cost -- is added outside the scaling.  All
# THREE constants are MEASURED, on the BOARD, in the capture's own absolute row
# numbers, by `sw/fz2_termcost.py` off the archived INV-2 capture: the anchor's
# CODE T1 at row 180 (exactly, 353 fixed-wait captures, both tiers), the dump
# 219 clocks from its first `OUT 0xFE` to the done marker (exactly, both
# tiers), and the NMI-assert -> first-`OUT` cost 53 min / 77 median / 463 max
# over 303 captures.  MARGIN is a stated margin, not a fit.
#
# The pre-A-3 values were ANCHOR_W0 = 145 (a POST-RESET row number, subtracted
# from a CAP_ROWS that counts from record 0) and DUMP_W0 = 240 (= 219 measured
# + 21 estimated for an entry that measures 53).  Finding O-2a.
# --------------------------------------------------------------------------- #
# T11: the formula and its constants now live in `fuzz_campaign`, because that
# is where the CAPTURE PATH arms the terminator (`term_directive`), and a
# delay this driver asserts on but the capture path computes some other way is
# exactly the fork the corpus cannot survive.  Bound here so this module's
# asserts and `lint`'s document cross-check read the SAME objects.
CAP_ROWS = fzc.CAP_ROWS            # 4,096 -- the rig's capture depth
ANCHOR_W0 = fzc.ANCHOR_W0          # MEASURED, absolute capture row
DUMP_W0 = fzc.DUMP_W0              # MEASURED, first `OUT 0xFE` -> done marker
ENTRY_MAX = fzc.ENTRY_MAX          # MEASURED, NMI assert -> first `OUT 0xFE`
TERM_MARGIN = fzc.TERM_MARGIN      # declared margin
TERM_FLOOR = fzc.TERM_FLOOR
weff_of = fzc.weff_of
term_clocks = fzc.term_clocks
assert CAP_ROWS == v30ctl.CAP_RECORDS


# Every wait source this corpus registers must leave a usable delay.  The
# `wvec-uni` level is 8: `draw_spec` draws wmax from {1,2,3,7,15} and
# `_wvec_weff` is the ceil-mean, so ceil(15/2) = 8 is its worst case.
for _s in {s["src"] for s in STRATA}:
    _w = (int(_s[3:]) if _s.startswith("fix") else
          int(_s[5:]) if _s.startswith("wrand") else 8)
    assert term_clocks(_w) >= TERM_FLOOR, f"TERM_CLOCKS floor breached at {_s}"


# --------------------------------------------------------------------------- #
# THE CENSUS BANK RULE -- frozen arithmetic, no verdict in it.
# --------------------------------------------------------------------------- #
CENSUS_BANK_STEP = 2               # every second k of every census stratum


def census_bank_seeds():
    out = [k for st in _CEN for k in seeds_of(st)
           if (k - st["k_lo"]) % CENSUS_BANK_STEP == 0]
    assert len(out) == 480, "the frozen census bank is 480 seeds"
    return out


# `cmd_run --keep-rows-every N` keeps `k % N == 0`, which is the SAME SET as
# "every second k of every stratum" only because every census `k_lo` is even.
# Checked, not assumed: if a later k-block moved to an odd base the driver
# would silently retain the OTHER half of every stratum.
assert set(census_bank_seeds()) == {
    k for st in _CEN for k in seeds_of(st) if k % CENSUS_BANK_STEP == 0}, \
    "the keep-rows arithmetic and the frozen bank rule name different seeds"


# --------------------------------------------------------------------------- #
# THE C-9 SUB-SAMPLE -- declared here, derived, fixed before any capture.
# 5 % of 3,840 is 192, and 0.05 x 80 = 4 EXACTLY in every stratum, so the
# largest-remainder apportionment has NO remainder to distribute.  The function
# is kept in its general form (and asserts the total) because a later change to
# `N_PER` must not silently turn an exact allocation into a fitted one.
# Within a stratum the seeds are EVENLY SPACED across the k-block: any
# deterministic subset is unbiased -- the seeds are independent draws keyed by
# k -- so the choice is made for spread and reproducibility, not for balance.
# --------------------------------------------------------------------------- #
C9_FRAC = 0.05
C9_REPS = 3


def c9_alloc():
    base = {j: int(C9_FRAC * s["n"]) for j, s in enumerate(STRATA)}
    frac = {j: C9_FRAC * STRATA[j]["n"] - base[j] for j in base}
    total = round(C9_FRAC * sum(s["n"] for s in STRATA))
    left = total - sum(base.values())
    for j in sorted(frac, key=lambda x: (-frac[x], x))[:left]:
        base[j] += 1
    assert sum(base.values()) == total == 192
    return base


def c9_seeds():
    alloc = c9_alloc()
    out = []
    for j, st in enumerate(STRATA):
        m, n = alloc[j], st["n"]
        for x in range(m):
            out.append({"j": j, "cid": st["cid"], "k": st["k_lo"] + (x * n) // m})
    assert len(out) == 192
    assert len({(o["cid"], o["k"]) for o in out}) == 192
    return out


# --------------------------------------------------------------------------- #
# THE CAPTURE-PATH PRECONDITIONS (prereg §6).
#
# The v2 rig RTL, `v30ctl`'s host registers and `tb_sys` all carry the three
# schedulers and the NMI vector overlay (tasks T5/T6/T8).  THE CAPTURE PATH
# DOES NOT: `v30run.ServeRunner.run` emits one `evt=` option and no
# `tvec=`/`vecsub=`, so `fuzz_campaign.capture_board` cannot arm the
# terminating NMI, and the result line carries neither the 8080 capture-time
# discard nor the arch column's own words.  Each item below is a STOP that this
# driver checks BEFORE board time is spent, and each is checked the way
# CLAUDE.md's `want_raw` lesson says to: the parameter must exist AND be
# honoured, never merely accepted.
# --------------------------------------------------------------------------- #
REQUIRED_LINE_FIELDS = (
    "arch_ok", "arch_restart", "escaped", "escaped_n",   # exist today
    "arch_words", "arch_sim_ok", "arch_sim_words", "arch_match",
    "ps3_8080", "wrote_term", "term",
    # AMENDMENT A-4: the fourth discard class is computed AT CAPTURE TIME and
    # banked on the line, so a future capture classifies itself and needs no
    # retained rows.  Made a PRECONDITION here, checked before board time, for
    # the reason the 2026-08-09 re-capture demonstrated: rows exist for only
    # 67 of its 312 undispositioned seeds and the other 245 cannot be asked.
    "stalled", "stalled_at",
    # AMENDMENT A-7: the FIFTH discard class, the same way and for the same
    # reason.  A capture taken under A-7 self-classifies on both columns and
    # keeps no rows to do it.
    "long_insn", "long_insn_at",
)
REQUIRED_ROW_FIELDS = ("pin_int", "pin_nmi", "pin_poll_n", "vec_armed")


def _sig_has(fn, names):
    try:
        p = inspect.signature(fn).parameters
    except (TypeError, ValueError):                       # noqa: BLE001
        return []
    return [n for n in names if n not in p]


def capture_path_gaps():
    """Every precondition the capture path does not yet meet, as a list of
    (item, detail).  EMPTY is the only value that permits a capture."""
    gaps = []
    miss = _sig_has(v30run.ServeRunner.run, ("evts", "tvec", "vecsub"))
    if miss:
        gaps.append(("serve client", f"v30run.ServeRunner.run lacks {miss}; "
                                     "the board's `serve` accepts evt2/evt3/"
                                     "tvec/vecsub and the client never sends "
                                     "them"))
    miss = _sig_has(v30run.run_image, ("evts", "tvec", "vecsub"))
    if miss:
        gaps.append(("run_image", f"v30run.run_image lacks {miss}"))
    miss = _sig_has(check_seq.run_chip, ("evts", "tvec", "vecsub"))
    if miss:
        gaps.append(("run_chip", f"check_seq.run_chip lacks {miss}"))
    src = inspect.getsource(fzc.capture_board)
    if "tvec" not in src or "vecsub" not in src:
        gaps.append(("capture_board", "fuzz_campaign.capture_board never "
                                      "programs TVEC/VECCTL, so the "
                                      "terminating NMI cannot be armed"))
    if "keep_rows" not in inspect.getsource(fzc.cmd_run):
        gaps.append(("keep_rows", "fuzz_campaign.cmd_run has no keep-rows "
                                  "control, so the frozen census bank's rows "
                                  "are not retained"))
    src = inspect.getsource(fzc.result_line) + inspect.getsource(fzc.eval_case)
    missing = [f for f in REQUIRED_LINE_FIELDS if f'"{f}"' not in src]
    if missing:
        gaps.append(("result line", f"fields absent: {missing}"))
    import analyze_capture as ac                          # noqa: PLC0415
    src = inspect.getsource(ac.decode_words)
    missing = [f for f in REQUIRED_ROW_FIELDS if f'"{f}"' not in src]
    if missing:
        gaps.append(("row decode", f"analyze_capture.decode_words does not "
                                   f"expose {missing} (nec_bus records the "
                                   f"effective pins at [54:52] and vec_armed "
                                   f"at [59])"))
    return gaps


# The RTL files the fuzz-v2 DIRECTIVE lives in.  Not "the whole design": a
# core change is a new campaign by the flash-pin rule already, and this test is
# the narrower one -- can the resident bitstream be HANDED this corpus at all.
RIG_RTL = ("hdl/rtl/hps_axi_slave.sv", "hdl/rtl/nec_bus.sv",
           "hdl/rtl/system_large.sv")


def resident_rig_gap():
    """Whether the bitstream on the board was built from THIS tree's rig RTL.

    Offline, and from artifacts only: the flash log's tail names the resident
    `.sof`, the quartus receipt whose OUTPUTS contain that `.sof` names every
    input file with its sha256, and those are compared against the working
    tree file for file.  Returns {'gap': [(file, tree_sha, built_sha)],
    'why': str, 'receipt': id}; an empty `gap` is the passing value."""
    flash = fzc._last_flash_entry()
    sof = (flash or {}).get("sha256")
    out = {"gap": [], "why": "", "receipt": None, "flash_sha256": sof}
    if not sof:
        out["gap"] = [("<flash_log>", "", "")]
        out["why"] = "no flash_log entry to read"
        return out
    rp = SW / "testdata" / "receipts" / "quartus_bitstream.jsonl"
    hit = None
    for ln in rp.read_text().splitlines() if rp.exists() else []:
        ln = ln.strip()
        if not ln:
            continue
        try:
            r = json.loads(ln)
        except Exception:                                   # noqa: BLE001
            continue
        if sof in json.dumps(r.get("outputs", {})):
            hit = r
    if hit is None:
        out["gap"] = [("<receipt>", "", "")]
        out["why"] = f"no quartus receipt outputs the pinned .sof {sof[:12]}…"
        return out
    out["receipt"] = hit.get("id")
    files = (hit.get("inputs") or {}).get("files") or {}
    for f in RIG_RTL:
        p = ROOT / f
        tree = hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else ""
        built = files.get(f)
        if tree != built:
            out["gap"].append((f, tree, built))
    out["why"] = (f"receipt {str(hit.get('id'))[:12]}…, "
                  f"{hit.get('label')!r}")
    return out


# --------------------------------------------------------------------------- #
# board primitives (wrfuzz_w1's, unchanged -- one implementation, not two)
# --------------------------------------------------------------------------- #
def div_guard(tag, rec=None):
    """s13_board.div_guard's contract: PIN the divider, then ask the TRANSPORT
    what it commanded and record the answer.  UNPINNED is a rig-integrity
    FINDING -- recorded, not smoothed."""
    img, _ = ti.compose(regs={}, instr=bytes([0x90]))
    v30run.run_image(bytes(img), HOST, tag="fz2div", waits=0, use_core=False,
                     div=v30run.DIV_OF_RECORD)
    r = v30run._runners.get(HOST)
    rb = (r.div_readback if r is not None
          else "div=UNKNOWN (no live serve runner to ask)")
    state = "PINNED" if ("UNPINNED" not in str(rb)
                         and "UNKNOWN" not in str(rb)) else "UNPINNED"
    print(f"  [div guard] {tag}: {rb}   -> {state}", flush=True)
    if state != "PINNED":
        print("  [div guard] *** UNPINNED READBACK -- recorded, not smoothed "
              "***", flush=True)
    d = {"tag": tag, "readback": str(rb), "state": state,
         "rig": getattr(r, "rig_readback", None),
         "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    if rec is not None:
        rec.append(d)
    return d


def board_idle():
    img, _ = ti.compose(regs={}, instr=bytes([0x90]))
    check_seq.run_chip(img, HOST, use_core=False)


def _ssh(cmd, timeout=30):
    r = subprocess.run(["ssh", "-o", "ConnectTimeout=10", HOST, cmd],
                       capture_output=True, text=True, timeout=timeout)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


# --------------------------------------------------------------------------- #
# strata
# --------------------------------------------------------------------------- #
def cmd_strata(a):
    print(f"| i | pop | cid | tier | evt | wait | k range | n |")
    print(f"|---|---|---|---|---|---|---|---|")
    for st in STRATA:
        ks = seeds_of(st)
        print(f"| {st['i']} | {st['pop']} | {st['cid']} | {st['tier']} | "
              f"{st['evt']} | {st['src']} | {ks[0]}-{ks[-1]} | {st['n']} |")
    print(f"\nseeds: {sum(s['n'] for s in STRATA)}  "
          f"(census {sum(s['n'] for s in _CEN)}, "
          f"enriched {sum(s['n'] for s in _ENR)})")
    print(f"SEED_LIST_SHA256 = {seed_list_sha256()}")
    print(f"census bank (frozen, every {CENSUS_BANK_STEP}nd k): "
          f"{len(census_bank_seeds())}")
    print(f"C-9 sub-sample: {len(c9_seeds())} seeds x {C9_REPS} reps")
    return 0


# --------------------------------------------------------------------------- #
# freeze -- every seed named before it is generated
# --------------------------------------------------------------------------- #
def _freeze_one(args):
    cid, k, j = args
    st = STRATA[j]
    cfg = fzc.derive_case(cid, k, ov_of(st))
    g = fzc.build(cfg)
    w = weff_of(cfg)
    e = cfg["evt"]
    return {"j": j, "cid": cid, "k": k, "tier": cfg["tier"],
            "cfg_hash": cfg["cfg_hash"], "nmax_eff": cfg["nmax_eff"],
            "weff": w, "term_clocks": term_clocks(w),
            "evt": None if not e else {"pin": e["pin"], "delay": e["delay"],
                                       "hold": e["hold"]},
            "wvec": cfg["wvec"], "waits": cfg["waits"],
            "has_tf": bool(g.get("has_tf")), "has_halt": bool(g.get("has_halt")),
            "raw_mode": g.get("raw_mode"), "n_ins": g["n_ins"]}


def cmd_freeze(a):
    from multiprocessing import Pool
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = [(st["cid"], k, j) for j, st in enumerate(STRATA)
            for k in seeds_of(st)]
    t0 = time.time()
    rows = []
    with Pool(a.jobs) as pool:
        for r in pool.imap(_freeze_one, jobs, chunksize=16):
            rows.append(r)
    rows.sort(key=lambda r: (r["j"], r["k"]))
    assert len(rows) == 3840
    # THE CORPUS'S CONTENT HASH, over the derived seeds ALONE.  `gen_git` is
    # provenance and it MOVES with the tree (this very commit changes it), so
    # the file-level sha256 is not a reproducible name for the corpus and the
    # document does not quote it as one.  `seeds_sha256` is a pure function of
    # the strata and the generator, and a reviewer re-running `freeze` at any
    # later HEAD reproduces it byte for byte or the generator moved.
    seeds_sha = hashlib.sha256(
        json.dumps(rows, sort_keys=True).encode()).hexdigest()
    blob = {
        "stage": "fz2 T10 freeze", "prereg": PREREG.name,
        "gen_git": fzc._gen_git(),
        "seeds_sha256": seeds_sha,
        "seed_list_sha256": seed_list_sha256(),
        "cap_rows": CAP_ROWS, "anchor_w0": ANCHOR_W0, "dump_w0": DUMP_W0,
        "entry_max": ENTRY_MAX,
        "term_margin": TERM_MARGIN, "nmax_scale_c": fzc.NMAX_SCALE_C,
        "census_bank": census_bank_seeds(),
        "c9": c9_seeds(),
        "strata": [{**st, "ks": [seeds_of(st)[0], seeds_of(st)[-1]]}
                   for st in STRATA],
        "seeds": rows,
    }
    txt = json.dumps(blob, sort_keys=True, indent=1)
    p = OUT / "fz2_population.json"
    p.write_text(txt)
    sha = hashlib.sha256(txt.encode()).hexdigest()
    (OUT / "fz2_population.sha256").write_text(f"{sha}  {p.name}\n")

    # what the corpus CONTAINS, counted now rather than discovered later
    def cnt(sel, rs=rows):
        return sum(1 for r in rs if sel(r))
    summ = {}
    for pop in POPS:
        rs = [r for r in rows if r["cid"] == CID[pop]]
        summ[pop] = {
            "n": len(rs),
            "evt": cnt(lambda r: r["evt"], rs),
            "pin_int": cnt(lambda r: r["evt"] and r["evt"]["pin"] == 0, rs),
            "pin_nmi": cnt(lambda r: r["evt"] and r["evt"]["pin"] == 1, rs),
            "pin_poll": cnt(lambda r: r["evt"] and r["evt"]["pin"] == 2, rs),
            "hold2": cnt(lambda r: r["evt"] and r["evt"]["hold"] == 2, rs),
            "hold300": cnt(lambda r: r["evt"] and r["evt"]["hold"] == 300, rs),
            "has_tf": cnt(lambda r: r["has_tf"], rs),
            "has_halt": cnt(lambda r: r["has_halt"], rs),
            "raw_whole": cnt(lambda r: r["raw_mode"] == "whole", rs),
            "term_clocks_min": min(r["term_clocks"] for r in rs),
            "term_clocks_max": max(r["term_clocks"] for r in rs),
        }
    blob["summary"] = summ
    txt = json.dumps(blob, sort_keys=True, indent=1)
    p.write_text(txt)
    sha = hashlib.sha256(txt.encode()).hexdigest()
    (OUT / "fz2_population.sha256").write_text(f"{sha}  {p.name}\n")
    print(f"froze {len(rows)} seeds in {time.time()-t0:.1f}s -> {p}")
    print(f"  file sha256      {sha}   (moves with gen_git -- not the name)")
    print(f"  seeds_sha256     {blob['seeds_sha256']}")
    print(f"  seed_list_sha256 {blob['seed_list_sha256']}")
    for pop in POPS:
        print(f"  {pop:<9} {json.dumps(summ[pop])}")
    return 0


# --------------------------------------------------------------------------- #
# lint -- the DOCUMENT and THIS CODE cannot disagree
# --------------------------------------------------------------------------- #
_ROW_RE = re.compile(
    r"^\|\s*(\d+)\s*\|\s*(census|enriched)\s*\|\s*(fz2[ce])\s*\|\s*(soup|raw)"
    r"\s*\|\s*(noevt|stim)\s*\|\s*([a-z0-9-]+)\s*\|\s*(\d+)-(\d+)\s*\|"
    r"\s*(\d+)\s*\|")


def cmd_lint(a):
    """Parse the pre-registration's own stratum table and its seed-list hash
    and prove they are THIS code's.  A document that drifts from the driver is
    a pre-registration that constrains nothing."""
    if not PREREG.exists():
        print(f"lint: {PREREG} is missing")
        return 2
    text = PREREG.read_text()
    doc = []
    for line in text.splitlines():
        m = _ROW_RE.match(line.strip())
        if m:
            doc.append({"i": int(m.group(1)), "pop": m.group(2),
                        "cid": m.group(3), "tier": m.group(4),
                        "evt": m.group(5), "src": m.group(6),
                        "k_lo": int(m.group(7)), "k_hi": int(m.group(8)),
                        "n": int(m.group(9))})
    hits = 0
    if len(doc) != len(STRATA):
        hits += 1
        print(f"  ROWS: document has {len(doc)} stratum rows, code has "
              f"{len(STRATA)}")
    for d, st in zip(doc, STRATA):
        ks = seeds_of(st)
        want = {"i": st["i"], "pop": st["pop"], "cid": st["cid"],
                "tier": st["tier"], "evt": st["evt"], "src": st["src"],
                "k_lo": ks[0], "k_hi": ks[-1], "n": st["n"]}
        if d != want:
            hits += 1
            print(f"  ROW MISMATCH doc={d} code={want}")
    for name, val in (("SEED_LIST_SHA256", seed_list_sha256()),
                      ("CENSUS_BANK_N", str(len(census_bank_seeds()))),
                      ("C9_N", str(len(c9_seeds()))),
                      ("C9_REPS", str(C9_REPS)),
                      ("CORPUS_N", str(sum(s["n"] for s in STRATA))),
                      ("TERM_MARGIN", str(TERM_MARGIN)),
                      ("ANCHOR_W0", str(ANCHOR_W0)),
                      ("DUMP_W0", str(DUMP_W0)),
                      ("ENTRY_MAX", str(ENTRY_MAX)),
                      ("CAP_ROWS", str(CAP_ROWS))):
        m = re.search(rf"^{name}\s*=\s*(\S+)\s*$", text, re.M)
        if not m:
            hits += 1
            print(f"  ABSENT from the document: {name}")
        elif m.group(1) != val:
            hits += 1
            print(f"  {name}: document {m.group(1)!r} != code {val!r}")
    # the frozen population artifact, if it exists, must be THIS corpus and the
    # document must quote ITS content hash -- doc <-> artifact <-> code.
    pop = OUT / "fz2_population.json"
    m = re.search(r"^SEEDS_SHA256\s*=\s*(\S+)\s*$", text, re.M)
    if not m:
        hits += 1
        print("  ABSENT from the document: SEEDS_SHA256")
    elif not pop.exists():
        hits += 1
        print(f"  {pop} is missing -- run `freeze`")
    else:
        d = json.loads(pop.read_text())
        if d.get("seeds_sha256") != m.group(1):
            hits += 1
            print(f"  SEEDS_SHA256: document {m.group(1)!r} != frozen "
                  f"population {d.get('seeds_sha256')!r}")
        if d.get("seed_list_sha256") != seed_list_sha256():
            hits += 1
            print("  the frozen population is a DIFFERENT corpus from this code")
    # the bars the document registers must all be scored by `bars`
    doc_bars = set(re.findall(r"^\|\s*\*\*(C-\d+)\*\*", text, re.M))
    if doc_bars != set(BARS):
        hits += 1
        print(f"  BARS: document {sorted(doc_bars)} != code {sorted(BARS)}")
    print(f"\nFZ2 LINT {'PASS' if hits == 0 else 'FAIL'}: {hits} hit(s); "
          f"{len(doc)} stratum rows checked")
    return 0 if hits == 0 else 1


# --------------------------------------------------------------------------- #
# preflight
# --------------------------------------------------------------------------- #
def cmd_preflight(a):
    OUT.mkdir(parents=True, exist_ok=True)
    rec = {"stage": "fz2 preflight", "host": HOST,
           "gen_git": fzc._gen_git(),
           "seed_list_sha256": seed_list_sha256(),
           "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "div_guards": []}
    ok = True

    # ---- 1. THE CAPTURE PATH ITSELF ---------------------------------------
    print("== capture-path preconditions (prereg §6)")
    gaps = capture_path_gaps()
    rec["capture_path_gaps"] = [{"item": i, "detail": d} for i, d in gaps]
    for i, d in gaps:
        print(f"  *** MISSING: {i} -- {d}")
    if gaps:
        ok = False
    else:
        print("  all capture-path preconditions present")

    # ---- 2. SINGLE WRITER (asked of the board, not assumed) ---------------
    if a.board:
        print("== single-writer / reachability")
        rc, up, err = _ssh("uptime")
        rec["uptime"] = up if rc == 0 else f"UNREACHABLE rc={rc} {err[:120]}"
        print(f"  uptime: {rec['uptime']}")
        if rc != 0:
            rec["single_writer"] = "UNKNOWN (unreachable)"
            ok = False
        else:
            rc, ps, _ = _ssh("ps w | grep -E 'v30ctl|serve' | grep -v grep || true")
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

    # ---- 3. THE ERA, and the flash pin the campaign refuses without -------
    print("== era / flash pin")
    flash = fzc._last_flash_entry()
    rec["flash_log_tail"] = {k: (flash or {}).get(k)
                             for k in ("sha256", "ts", "git_describe", "verify")}
    # THE RESIDENT BITSTREAM MUST CARRY THE RIG THIS CORPUS DRIVES.
    # C-4 gates that a capture NAMES an RTL input manifest; it does not gate
    # that the manifest is THIS tree's.  The whole fuzz-v2 directive lives in
    # `hps_axi_slave.sv` (TVEC / VECCTL / EVT1-2) and `nec_bus.sv` (the three
    # schedulers, the vector-read overlay, the effective-pin capture bits), so
    # a bitstream built before them answers every one of those registers with
    # zeros.  The readback would catch it at the first seed -- but only after
    # the board session had started, which is what this whole section exists
    # to prevent.  Compared per FILE, against the pinned .sof's own receipt.
    rig = resident_rig_gap()
    rec["resident_rig"] = rig
    if rig.get("gap"):
        ok = False
        print(f"  *** the RESIDENT bitstream does not carry this tree's rig "
              f"RTL: {rig['why']}")
        for f, tree, built in rig["gap"]:
            print(f"      {f}: tree {tree[:12]}… built-from {str(built)[:12]}…")
    else:
        print(f"  resident bitstream carries this tree's rig RTL "
              f"({rig['why']})")
    rec["manifests"] = {}
    for pop in POPS:
        mp = fzc.CAMPAIGNS / CID[pop] / "manifest.json"
        if not mp.exists():
            print(f"  no manifest for {CID[pop]} -- "
                  f"`fuzz_campaign.py new {CID[pop]}`")
            rec["manifests"][CID[pop]] = None
            ok = False
            continue
        man = json.loads(mp.read_text())
        era = fzc.era_of(man)
        rec["manifests"][CID[pop]] = era
        if (flash or {}).get("sha256") != (man.get("flash_pin") or {}).get("sha256"):
            ok = False
            print(f"  *** {CID[pop]}: flash pin MISMATCH against flash_log tail")
        for k in ("sof_sha256", "gen_git", "rig_evt_hold_bits"):
            if era.get(k) in (None, ""):
                ok = False
                print(f"  *** {CID[pop]}: era field ABSENT: {k}")
        if not era["rtl"]["inputs_sha256"]:
            ok = False
            print(f"  *** {CID[pop]}: no quartus receipt carries the pinned "
                  f".sof -- the RTL input-manifest hash is ABSENT (C-4)")

    # ---- 4. GENERATION, REGENERATED, before board time is spent -----------
    print(f"== generation / regeneration sample ({a.sample} per stratum)")
    hits = 0
    per = []
    for j, st in enumerate(STRATA):
        ov = ov_of(st)
        step = max(1, st["n"] // a.sample)
        ks = [st["k_lo"] + x for x in range(0, st["n"], step)][:a.sample]
        npair = 0
        for k in ks:
            cfg = fzc.derive_case(st["cid"], k, ov)
            img, _ = fzc.compose_case(fzc.build(cfg), cfg)
            sha = hashlib.sha256(bytes(img)).hexdigest()
            cfg2 = fzc.derive_case(st["cid"], k, ov)
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
            v = fzc.wvec_of(cfg)
            if st["src"].startswith("wvec-"):
                if v is None or len(v) != wv.NWVEC or \
                        not all(0 <= x <= 31 for x in v) or \
                        cfg["wvec"]["shape"] != st["src"][5:]:
                    hits += 1
                    print(f"  WVEC BAD {label(st)}/{k}")
            elif v is not None:
                hits += 1
                print(f"  WVEC UNEXPECTED {label(st)}/{k}")
            w = cfg["waits"]
            if st["src"].startswith("fix") and \
                    (w["wrand"] or w["fixed"] != int(st["src"][3:])):
                hits += 1
                print(f"  WAITS WRONG {label(st)}/{k}: {w}")
            if st["src"].startswith("wrand") and \
                    (not w["wrand"] or w["wmax"] != int(st["src"][5:])):
                hits += 1
                print(f"  WAITS WRONG {label(st)}/{k}: {w}")
            if term_clocks(weff_of(cfg)) < TERM_FLOOR:
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

    # ---- 5. THE BOARD ITSELF ----------------------------------------------
    if a.board:
        print("== board health")
        div_guard("preflight", rec["div_guards"])
        # C-6(a), ASKED OF THE RIG rather than assumed: two distinct values
        # into every EVT/TVEC/VECCTL register, each read back.  The capture
        # path verifies every RUN's own directive; this is the session-start
        # check for the stuck bit a single directive can pass by luck.
        try:
            regs = v30run._runners[HOST].rig_readback_check()
            rec["rig_readback_check"] = {"ok": True, "registers": regs}
            print(f"  rig_readback_check: {len(regs)} registers round-tripped")
        except Exception as e:                              # noqa: BLE001
            ok = False
            rec["rig_readback_check"] = {"ok": False, "error": str(e)[:300]}
            print(f"  *** rig_readback_check FAILED: {str(e)[:200]}")
        r = subprocess.run([sys.executable, str(SW / "check_ab_hw.py"), "all",
                            "800", "--host", HOST],
                           capture_output=True, text=True, timeout=600)
        tail = (r.stdout + r.stderr).strip().splitlines()
        rec["check_ab_hw"] = {"rc": r.returncode, "tail": tail[-12:]}
        for l in tail[-12:]:
            print(f"  {l}")
        if r.returncode != 0:
            ok = False
            print("  *** check_ab_hw FAILED ***")
        div_guard("preflight-end", rec["div_guards"])
        board_idle()
        print("  board left use_core=0 (board_idle)")
    rec["board_leg"] = bool(a.board)

    rec["verdict"] = "OK" if ok else "BLOCKED"
    (OUT / "fz2_preflight.json").write_text(json.dumps(rec, indent=1))
    print(f"\nFZ2 PREFLIGHT: {rec['verdict']}  -> "
          f"{OUT/'fz2_preflight.json'}")
    return 0 if ok else 1


# --------------------------------------------------------------------------- #
# capture
# --------------------------------------------------------------------------- #
def _done_ks(cid):
    """EVERY k present in the campaign's results -- NOT `max(k)+1`.
    `fuzz_campaign._resume_k` returns the highest k plus one, which in a
    block-stratified corpus silently skips every unwritten k below it."""
    p = fzc.CAMPAIGNS / cid / "results.jsonl"
    if not p.exists():
        return set()
    out = set()
    with open(p) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.add(json.loads(line)["k"])
                except Exception:                       # noqa: BLE001
                    pass
    return out


def _run_args(st, start, n, host):
    a = argparse.Namespace(
        cid=st["cid"], host=host, session_seeds=n, start=start, tb_only=False,
        jobs=1, stop_after=0, measure=0, allow_stale=False,
        force_tier=st["tier"], contained=False, w0=False, force_fixed=None,
        no_evt=(st["evt"] == "noevt"), force_evt=(st["evt"] == "stim"),
        strict=False, no_brkem=False, mainline=False, survey=True,
        force_wrand=None, wvec_shapes=None, done_dist=None,
        # THE FROZEN CENSUS BANK RULE, handed to the capture path as
        # arithmetic.  Every census stratum's `k_lo` is even
        # (400000 + 1000*i), so "every second k of every stratum" IS
        # `k % 2 == 0`; the assert beside `census_bank_seeds` is that
        # equivalence, checked rather than asserted in prose.  The enriched population keeps the existing
        # divergence-driven quota rule and sets 0.
        keep_rows_every=(CENSUS_BANK_STEP if st["pop"] == "census" else 0))
    src = st["src"]
    if src.startswith("fix"):
        a.force_fixed = int(src[3:])
    elif src.startswith("wrand"):
        a.force_wrand = src[5:]
    elif src.startswith("wvec-"):
        a.wvec_shapes = src[5:]
    return a


def _preflight_ok():
    p = OUT / "fz2_preflight.json"
    if not p.exists():
        return False, "no fz2_preflight.json -- run `preflight --board` first"
    d = json.loads(p.read_text())
    if d.get("verdict") != "OK":
        return False, f"preflight verdict is {d.get('verdict')!r}"
    if d.get("seed_list_sha256") != seed_list_sha256():
        return False, "preflight was taken against a DIFFERENT corpus"
    if d.get("gen_git") != fzc._gen_git():
        return False, (f"preflight was taken at {d.get('gen_git')}, tree is "
                       f"{fzc._gen_git()}")
    if not d.get("board_leg"):
        return False, "preflight did not run its board leg"
    return True, "ok"


def cmd_capture(a):
    OUT.mkdir(parents=True, exist_ok=True)
    gaps = capture_path_gaps()
    if gaps:
        print("capture: REFUSED -- the capture path cannot arm or record what "
              "the pre-registration says every seed carries:")
        for i, d in gaps:
            print(f"  {i}: {d}")
        return 2
    good, why = _preflight_ok()
    if not good:
        print(f"capture: REFUSED -- {why}")
        return 2
    pops = [a.pop] if a.pop else list(POPS)
    rec_path = OUT / "fz2_capture.json"
    rec = {"stage": "fz2 capture", "host": a.host, "pops": pops,
           "seed_list_sha256": seed_list_sha256(),
           "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "strata": [], "div_guards": []}
    t_all = time.time()
    halted = None
    for st in STRATA:
        if st["pop"] not in pops:
            continue
        done = _done_ks(st["cid"])
        ks = seeds_of(st)
        missing = [k for k in ks if k not in done]
        if not missing:
            print(f"== {label(st):<26} already complete, skipped")
            rec["strata"].append({"stratum": label(st), "n": st["n"],
                                  "written": st["n"], "skipped": True})
            continue
        start, n = missing[0], missing[-1] - missing[0] + 1
        print(f"\n== {label(st):<26} k [{start},{start+n}) n={n}", flush=True)
        div_guard(f"{st['cid']}-{st['i']:02d}-{label(st)}", rec["div_guards"])
        t0 = time.time()
        rc = fzc.cmd_run(_run_args(st, start, n, a.host))
        dt = time.time() - t0
        written = sum(1 for k in ks if k in _done_ks(st["cid"]))
        rec["strata"].append({"stratum": label(st), "cid": st["cid"],
                              "k_lo": st["k_lo"], "n": st["n"],
                              "written": written, "rc": rc,
                              "seconds": round(dt, 1),
                              "rate": round(n / max(1e-6, dt), 2)})
        rec["board_seconds"] = round(time.time() - t_all, 1)
        rec_path.write_text(json.dumps(rec, indent=1))
        print(f"  {label(st)}: {written}/{st['n']} in {dt:.1f}s rc={rc}")
        if written < st["n"] or rc != 0:
            halted = (f"{label(st)} wrote {written}/{st['n']} rc={rc} "
                      f"-- STOPPED, not nursed")
            print(f"\n*** {halted} ***")
            break
    rec["board_seconds"] = round(time.time() - t_all, 1)
    rec["halted"] = halted
    rec["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    rec_path.write_text(json.dumps(rec, indent=1))
    tot = sum(s["written"] for s in rec["strata"])
    print(f"\nFZ2 CAPTURE: {tot} seeds in {rec['board_seconds']/60:.1f} min"
          f"{'  HALTED: ' + halted if halted else ''}")
    return 1 if halted else 0


# --------------------------------------------------------------------------- #
# stability (C-9)
# --------------------------------------------------------------------------- #
def cmd_stability(a):
    OUT.mkdir(parents=True, exist_ok=True)
    gaps = capture_path_gaps()
    if gaps:
        print("stability: REFUSED -- capture-path preconditions unmet "
              f"({len(gaps)} item(s); see `preflight`)")
        return 2
    seeds = c9_seeds()
    rec = {"stage": "fz2 C-9 stability", "reps": C9_REPS, "n_seeds": len(seeds),
           "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "div_guards": [], "seeds": []}
    div_guard("c9-start", rec["div_guards"])
    t0 = time.time()
    stable = unstable = errs = 0
    for idx, s in enumerate(seeds):
        st = STRATA[s["j"]]
        bdir = fzc.CAMPAIGNS / st["cid"] / "captures" / "c9"
        bdir.mkdir(parents=True, exist_ok=True)
        cfg = fzc.derive_case(st["cid"], s["k"], ov_of(st))
        g = fzc.build(cfg)
        image, meta = fzc.compose_case(g, cfg)
        reps, err = [], None
        for _ in range(C9_REPS):
            real, sim, e = fzc.capture_board(image, meta, cfg, a.host)
            if e:
                err = e
                break
            reps.append((real, sim))
        if err or len(reps) < C9_REPS:
            errs += 1
            rec["seeds"].append({"stratum": label(st), "k": s["k"],
                                 "error": err or "short"})
            print(f"  [{idx+1}/{len(seeds)}] {label(st)}/{s['k']} ERROR {err}")
            continue
        cells = []
        for leg in (0, 1):
            for j in (1, 2):
                d = fc.diff_rows(reps[0][leg], reps[j][leg])
                cells.append({"leg": "chip" if leg == 0 else "fabric",
                              "rep": j + 1, "n": d.n, "bad": d.bad,
                              "flick": d.flick, "first": d.first})
        # the ARCH column is compared too: a stable row set with an unstable
        # dump would be a finding the row diff cannot see.
        dumps = [fc.arch_dump(r[0], min(len(r[0]), 4000)) for r in reps]
        arch_stable = all(d == dumps[0] for d in dumps)
        bad = sum(c["bad"] for c in cells)
        blob = json.dumps({"k": s["k"], "stratum": label(st),
                           "cfg_hash": cfg["cfg_hash"],
                           "image_sha256": hashlib.sha256(bytes(image)).hexdigest(),
                           "arch": dumps,
                           "reps": [{"chip": r[0], "fabric": r[1]} for r in reps]})
        p = bdir / f"{st['tier']}_{s['k']}_{cfg['cfg_hash']}.json.gz"
        with gzip.open(p, "wt") as f:
            f.write(blob)
        if bad == 0 and arch_stable:
            stable += 1
        else:
            unstable += 1
        rec["seeds"].append({"stratum": label(st), "k": s["k"], "bad": bad,
                             "arch_stable": arch_stable, "cells": cells,
                             "rows": p.name,
                             "sha256": hashlib.sha256(p.read_bytes()).hexdigest()})
        if (idx + 1) % 20 == 0 or bad or not arch_stable:
            print(f"  [{idx+1}/{len(seeds)}] {label(st)}/{s['k']} bad={bad} "
                  f"arch_stable={arch_stable} "
                  f"({(idx+1)/(time.time()-t0):.1f} seeds/s)", flush=True)
    div_guard("c9-end", rec["div_guards"])
    # full per-clock rows retained WITH a sha256 beside them, never a digest
    # alone -- the blackbox retention rule, per campaign id
    for pop in POPS:
        bdir = fzc.CAMPAIGNS / CID[pop] / "captures" / "c9"
        if bdir.exists():
            (bdir / "SHA256SUMS").write_text("\n".join(
                f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}"
                for p in sorted(bdir.glob("*.json.gz"))) + "\n")
    rec.update(seconds=round(time.time() - t0, 1), stable=stable,
               unstable=unstable, errors=errs,
               finished=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    (OUT / "fz2_c9.json").write_text(json.dumps(rec, indent=1))
    print(f"\nC-9: {stable}/{len(seeds)} stable, {unstable} unstable, "
          f"{errs} errors, {rec['seconds']/60:.1f} min")
    return 0 if (unstable == 0 and errs == 0) else 1


# --------------------------------------------------------------------------- #
# control (C-6's board legs)
# --------------------------------------------------------------------------- #
# TWO TVEC VALUES that differ in BOTH halves and land on DIFFERENT physical
# addresses, so the proof is that the whole 32-bit word is served rather than
# that some default happened to work.
TVEC_A = (0x0000, ti.TERM_AT)                 # -> 0xBF00, the terminator
TVEC_B = (ti.TERM_AT >> 4, 0x0008)            # -> 0xBF08, same page, other CS:IP


def cmd_control(a):
    print("control: the C-6 board legs (>=2 TVEC values, >=2 hold values, the "
          "vecsub_en=0 negative control)")
    gaps = capture_path_gaps()
    if gaps:
        print("control: REFUSED -- capture-path preconditions unmet:")
        for i, d in gaps:
            print(f"  {i}: {d}")
        print("  (the offline equivalents are `sw/fz2_tbsys.py` legs a-d, "
              "which DO run today)")
        return 2
    print("  NOT IMPLEMENTED beyond the refusal: the leg's shape is registered "
          "in the pre-registration §6 C-6 and its host-side calls do not exist "
          "on this tree.  Implementing them against an API that has not been "
          "written would be a guess, not a driver.")
    return 2


# --------------------------------------------------------------------------- #
# bars
# --------------------------------------------------------------------------- #
BARS = ("C-1", "C-2", "C-3", "C-4", "C-5", "C-6", "C-7", "C-8", "C-9", "C-10",
        "C-11")

# the E-1 VALUE, registered per tier (prereg §5)
#
# AMENDMENT A-5 (prereg §16), 2026-08-09 -- BY USER DECISION the two RATE
# clauses are RE-REGISTERED: soup 99.0 -> 90.0, raw 95.0 -> 75.0.  BOTH new
# values were chosen AFTER this corpus measured soup 98.54 / 98.89 % and raw
# 83.54 / 83.61 %, ON that same population, and NEITHER IS DERIVED from any
# mechanism -- unlike the old values, each of which sat below a computed
# expectation (99.9 % and 95.9 %, prereg §5.3) and each of which was missed.
# `ucore_provenance.md` §64.1: a replacement chosen on the data that refuted
# its predecessor is FITTED, and its score on that data is not evidence -- so
# a MET on these clauses is marked UNVALIDATED below and is NOT a ratchet
# until it has been measured on a DISJOINT population (§16.2).
# E-1c (0 UNDISPOSITIONED) is UNTOUCHED and is now C-1's sole blocker.
E1 = {"soup": 90.0, "raw": 75.0}
E1_PRIOR = {"soup": 99.0, "raw": 95.0}          # what §5.3 registered
E1_A5 = ("[A-5: soup LOWERED from 99.0, raw from 95.0 -- set AFTER measuring "
         "soup 98.54/98.89 % and raw 83.54/83.61 % ON THIS POPULATION, NOT "
         "DERIVED, and UNVALIDATED until scored on a DISJOINT population]")


def _lines(cid):
    p = fzc.CAMPAIGNS / cid / "results.jsonl"
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


def _stratum_of(cid, k):
    for j, st in enumerate(STRATA):
        if st["cid"] == cid and st["k_lo"] <= k < st["k_lo"] + st["n"]:
            return j
    return None


def _c1_verdict(met, undisp):
    """C-1's verdict, with AMENDMENT A-5's marker.

    The two RATE clauses were re-registered on the population that measured
    them (§16.0), so `ucore_provenance.md` §64.1 applies: their score on that
    population is not evidence for the values.  While they read MET they read
    MET *UNVALIDATED*, and the marker stays on the verdict string until they
    have been scored on a DISJOINT population (§16.2).  A bare `MET` on the
    selecting population is exactly what §64.1 forbids, so this function will
    not emit one.  E-1c carries no marker -- it did not move.
    """
    v = "MET" if (met and undisp == 0) else "MISSED"
    if met:
        v += " (rate clauses UNVALIDATED -- A-5)"
    return v


def _need(lines, field):
    """Whether a registered field is present on the lines at all -- a bar
    scored off an absent field must read NOT SCOREABLE, never MET."""
    return bool(lines) and any(field in r for r in lines)


def cmd_bars(a):
    OUT.mkdir(parents=True, exist_ok=True)
    rec = {"stage": "fz2 bars", "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                    time.gmtime()),
           "seed_list_sha256": seed_list_sha256(), "bars": {}, "pops": {}}
    lines = {pop: _lines(CID[pop]) for pop in POPS}
    allines = [r for pop in POPS for r in lines[pop]]

    def bar(name, statement, registered, measured, verdict, finding=None):
        rec["bars"][name] = {"statement": statement, "registered": registered,
                             "measured": measured, "verdict": verdict,
                             "finding": finding}

    # ---- the per-stratum roll-up and THE THREE DECOMPOSITIONS -------------
    for pop in POPS:
        per = []
        for j, st in enumerate(STRATA):
            if st["pop"] != pop:
                continue
            ks = set(seeds_of(st))
            got = [r for r in lines[pop] if r["k"] in ks]
            rows_exact = sum(1 for r in got if r.get("bad_rows") == 0)
            arch_exact = sum(1 for r in got if r.get("arch_match") is True)
            unscoreable = sum(1 for r in got
                              if not r.get("arch_ok") or
                              r.get("arch_sim_ok") is False)
            per.append({"j": j, "stratum": label(st), "n": st["n"],
                        "captured": len(got),
                        "rows_exact": rows_exact, "arch_exact": arch_exact,
                        "unscoreable": unscoreable,
                        "verdicts": dict(Counter(r["verdict"] for r in got))})
        rec["pops"][pop] = {
            "cid": CID[pop], "captured": sum(p["captured"] for p in per),
            "per_stratum": per,
            # THE THREE DECOMPOSITIONS, REPORTED SEPARATELY AND NEVER AS ONE
            # AGGREGATE.  Each population-level figure is the UNWEIGHTED MEAN
            # of the per-stratum rates, which is what a stratified design
            # supports; a pooled count is not computed anywhere in this file.
            "rows_exact_mean_pct": _mean_pct(per, "rows_exact"),
            "arch_exact_mean_pct": _mean_pct(per, "arch_exact"),
            "unscoreable_total": sum(p["unscoreable"] for p in per),
        }

    # ---- C-1: CONTAINMENT, the E-1 VALUE ----------------------------------
    if not _need(allines, "wrote_term"):
        bar("C-1", "containment (E-1)",
            f"soup >= {E1['soup']} %, raw >= {E1['raw']} %, "
            f"0 undispositioned {E1_A5}",
            {"why": "line field `wrote_term` absent"},
            "NOT SCOREABLE")
    else:
        m = {}
        undisp = undisp3 = undisp4 = 0
        # AMENDMENT A-4 -- the FOURTH declared discard class.  Nothing about
        # any bar's text or value moves; §3.4's list gains one row.  The
        # three-term figure is computed and reported BESIDE the four-term one
        # on every line of this table, so the delta the class buys is visible
        # rather than absorbed -- the A-2 lesson, where a class that fired on
        # 3,840 of 3,840 would have driven this count to 0 by arithmetic.
        capidx = {pop: fz2_stall.capture_index(CID[pop]) for pop in POPS}
        src = Counter()
        # AMENDMENT A-7 -- the FIFTH declared discard class, THE CAPTURE
        # WINDOW'S OWN LIMIT.  Same shape as A-4's arrival and the same four
        # protections (§19.0): an independent detector that names no dump, a
        # HARD falsifier run over every banked capture in every bank, no bar's
        # text or value moved, and the rescore reported BOTH WAYS.  The
        # four-class figure is kept beside the five-class one permanently, so
        # what this class buys stays visible instead of being absorbed.
        src_li = Counter()
        # AMENDMENT A-6's CENSUS COLUMN, REPORTED AND NOT USED AS A CLASS.
        # `mech` is read off the result line as a banked field; this file does
        # not import `term_mechanism`, and the disposition set below is the
        # five DECLARED classes and nothing else -- A-6's other labels
        # (`BUDGET`, `NEAR`, `OTHER`) disposition nothing and never have.
        # ⚠ `fz2_longinsn.resolve` DOES read `mech`, for one label only, and
        # only because since A-7 `term_mechanism` reaches that label by calling
        # A-7's own detector; that file's docstring carries the argument and
        # the one-way direction of it.  It is here so that the residue E-1c
        # counts can be NAMED in the scored artifact rather than only in a
        # census run beside it -- `mech_undispositioned` is the one table this
        # sitting exists to produce.  A-6 §17.1.
        mech_all = Counter()
        mech_undisp = Counter()
        mech_p3 = {"arch_ok_vs_mech": 0, "stalled_vs_mech": 0, "absent": 0}
        for pop in POPS:
            for tier in TIERS:
                sel = [r for r in lines[pop]
                       if _stratum_of(CID[pop], r["k"]) is not None
                       and STRATA[_stratum_of(CID[pop], r["k"])]["tier"] == tier]
                ok = sum(1 for r in sel if r.get("arch_ok"))
                bad = [r for r in sel if not r.get("arch_ok")]
                def _d3(r):
                    return bool(r.get("arch_restart") or r.get("ps3_8080")
                                or r.get("wrote_term"))
                d3 = [r for r in bad if _d3(r)]
                rest = [r for r in bad if not _d3(r)]
                for r in sel:
                    mech_all[str(r.get("mech"))] += 1
                    if "mech" not in r:
                        mech_p3["absent"] += 1
                        continue
                    # P3, THE HARD SELF-CONSISTENCY FALSIFIER (§17.8).  The two
                    # columns come from the same rows through the same
                    # functions; a disagreement is a defect in A-6, not a
                    # finding about the part.
                    if bool(r.get("arch_ok")) != (r.get("mech") in
                                                  ("REACHED", "WINDOW",
                                                   "FORGED_DONE")):
                        mech_p3["arch_ok_vs_mech"] += 1
                    if r.get("stalled") is not None and \
                            bool(r["stalled"]) != (r.get("mech") == "STALLED"):
                        mech_p3["stalled_vs_mech"] += 1
                nstall = nlong = 0
                for r in rest:
                    st, _, how = fz2_stall.resolve(r, capidx[pop])
                    src[how] += 1
                    nstall += bool(st)
                    if st:
                        continue
                    # A-7.  Asked ONLY of a seed the four classes did not take,
                    # so the two are disjoint in the count exactly as they are
                    # disjoint in the predicate (A-4 clause (3) is A-7 clause
                    # (1)'s negation; `fz2_longinsn falsify` checks it).
                    li, _, lihow = fz2_longinsn.resolve(r, capidx[pop])
                    src_li[lihow] += 1
                    nlong += bool(li)
                    if not li:
                        mech_undisp[str(r.get("mech"))] += 1
                disp, dispst = len(d3), len(d3) + nstall
                disp5 = dispst + nlong
                undisp3 += len(bad) - disp
                undisp4 += len(bad) - dispst
                undisp += len(bad) - disp5
                m[f"{pop}/{tier}"] = {
                    "n": len(sel), "reached": ok,
                    "pct": round(100.0 * ok / len(sel), 2) if sel else None,
                    "dispositioned": disp5,
                    "dispositioned_4class": dispst,
                    "dispositioned_3class": disp, "stalled": nstall,
                    "long_insn": nlong,
                    "undispositioned": len(bad) - disp5,
                    "undispositioned_4class": len(bad) - dispst,
                    "undispositioned_3class": len(bad) - disp}
        met = all(v["pct"] is not None
                  and v["pct"] >= E1[k.split("/")[1]] for k, v in m.items())
        bar("C-1", "containment measured as TERMINATOR-REACHED (E-1's "
            "predicate), with the escape count kept as a diagnostic",
            f"soup >= {E1['soup']} %, raw >= {E1['raw']} %, per population "
            f"{E1_A5}; and 0 UNDISPOSITIONED non-dumping seeds (E-1c, "
            "UNTOUCHED by A-5)",
            # `undispositioned_3class` is what this bar read before A-4 and
            # `undispositioned_4class` what it read before A-7; BOTH are kept
            # on the record permanently, so what each class buys stays visible
            # rather than absorbed.  `classified_from` says HOW each
            # remaining seed was asked: `line` = A-4's own capture-time column
            # (self-classifying), `rows` = recomputed from a banked capture,
            # `none` = neither, i.e. UNCLASSIFIABLE -- and an unclassifiable
            # seed stays UNDISPOSITIONED.  It is never extrapolated.
            {"per_tier": m, "undispositioned": undisp,
             "mech_census": dict(mech_all),
             "mech_undispositioned": dict(mech_undisp),
             "mech_selfcheck": mech_p3,
             "undispositioned_3class": undisp3,
             "undispositioned_4class": undisp4,
             "stalled_total": undisp3 - undisp4,
             "long_insn_total": undisp4 - undisp,
             "classified_from": dict(src),
             "classified_from_long_insn": dict(src_li)},
            _c1_verdict(met, undisp))

    # ---- C-2: the ARCH COLUMN IS NON-VACUOUS ------------------------------
    if not _need(allines, "arch_words"):
        bar("C-2", "the arch column is non-vacuous",
            "MAGIC constant; the other 14 words each take >= 2 values",
            {"why": "line field `arch_words` absent"}, "NOT SCOREABLE")
    else:
        vals = {n: set() for n in ti.STORE_ORDER}
        ndump = 0
        for r in allines:
            w = r.get("arch_words")
            if not w:
                continue
            ndump += 1
            for n in ti.STORE_ORDER:
                vals[n].add(w.get(n))
        magic_ok = vals["MAGIC"] == {ti.MAGIC}
        flat = sorted(n for n in ti.STORE_ORDER
                      if n != "MAGIC" and len(vals[n]) < 2)
        bar("C-2", "the arch column is non-vacuous -- demonstrated, not assumed",
            "MAGIC == 0x5EED on every dump; each of the other 14 STORE_ORDER "
            "words takes >= 2 distinct values across the corpus",
            {"dumps": ndump, "magic_constant": magic_ok,
             "distinct": {n: len(vals[n]) for n in ti.STORE_ORDER},
             "flat_words": flat},
            "MET" if (magic_ok and not flat and ndump) else "MISSED")

    # ---- C-3: 8080-FREE, BOTH CLAUSES -------------------------------------
    print("== C-3 / C-5: regenerating every image")
    from multiprocessing import Pool
    t0 = time.time()
    drift = pairs = vecmm = 0
    ref_of = {(CID[pop], r["k"]): r for pop in POPS for r in lines[pop]}
    jobs = [(cid, k, r.get("image_sha256"), r.get("wvec_hex"))
            for (cid, k), r in sorted(ref_of.items())]
    if jobs:
        with Pool(a.jobs) as pool:
            for k, cid, sha, npair, vhex in pool.imap_unordered(
                    _regen_one, jobs, chunksize=16):
                pairs += npair
                ref = ref_of[(cid, k)]
                if sha != ref.get("image_sha256"):
                    drift += 1
                    print(f"  GEN_DRIFT {cid}/{k}")
                if (ref.get("wvec_hex") or None) != vhex:
                    vecmm += 1
                    print(f"  WVEC RE-DERIVE MISMATCH {cid}/{k}")
        print(f"  {len(jobs)} seeds in {time.time()-t0:.1f}s")
    ps3 = sum(1 for r in allines if r.get("ps3_8080"))
    bar("C-3", "8080-free by BOTH clauses",
        "0 forbidden `0F xx` pairs on every composed image (generation) AND "
        "0 captures showing PS3 on a CODE T1 (runtime)",
        {"bad_0f_pairs": pairs, "seeds": len(jobs), "ps3_8080": ps3,
         "ps3_scoreable": _need(allines, "ps3_8080")},
        "MET" if (pairs == 0 and ps3 == 0 and _need(allines, "ps3_8080"))
        else ("NOT SCOREABLE" if not _need(allines, "ps3_8080") else "MISSED"))

    # ---- C-4: ERA ----------------------------------------------------------
    eras = Counter(json.dumps(r.get("era"), sort_keys=True) for r in allines)
    absent = sum(n for e, n in eras.items() if e == "null")
    incomplete = 0
    for e, n in eras.items():
        if e == "null":
            continue
        d = json.loads(e)
        if not (d.get("sof_sha256") and d.get("gen_git")
                and d.get("rig_evt_hold_bits")
                and (d.get("rtl") or {}).get("inputs_sha256")):
            incomplete += n
    stale = sum(1 for r in allines if r.get("build_stale"))
    bar("C-4", "era", "0 captures with an absent, incomplete or mixed era stamp",
        {"distinct_eras": len(eras), "absent": absent, "incomplete": incomplete,
         "build_stale": stale, "lines": len(allines)},
        "NOT SCOREABLE" if not allines else
        ("MET" if (len(eras) == 1 and not absent and not incomplete
                   and not stale) else "MISSED"))

    # ---- C-5: GEN-DRIFT ----------------------------------------------------
    bar("C-5", "no gen-drift", "0 GEN_DRIFT; 0 wvec re-derive mismatches",
        {"gen_drift": drift, "wvec_mismatch": vecmm, "seeds": len(jobs)},
        "NOT SCOREABLE" if not jobs else
        ("MET" if (drift == 0 and vecmm == 0) else "MISSED"))

    # ---- C-6: THE RIG APPLIED THE DIRECTIVES -------------------------------
    ctl = OUT / "fz2_control.json"
    c6 = json.loads(ctl.read_text()) if ctl.exists() else None
    holds = Counter()
    hold_exact = hold_bad = 0
    # FINDING O-2, 2026-08-09: C-6(b) IS NOT EVALUABLE AS WRITTEN, and this
    # code DECLINES to evaluate it rather than inventing a reading.
    #
    # The bar's text says "every event seed's counted high-row run equals its
    # own `hold` +/- 1 clock" -- singular.  The instrument that supplies the
    # evidence, `fuzz_campaign._pin_runs`, deliberately returns EVERY run on
    # ALL THREE pins as a dict of [start, length] lists, and its docstring says
    # in terms that picking one "would be answering the question in the
    # instrument" -- because a stimulus NMI and the terminating NMI share the
    # wire.  So `abs(t["hold_rows"] - e["hold"])` is `dict - int` and raises
    # TypeError on the first event seed; before T12 no board capture had ever
    # reached this line.  The bar's text and its own instrument were never
    # reconciled.
    #
    # NOT REPAIRED HERE.  Choosing what "the counted high-row run" means, after
    # the capture, is a comparator decision on a registered bar and belongs to
    # the coordinator in an amendment -- the O-1 precedent exactly.  Nothing is
    # lost by waiting: `term.hold_rows` is banked on EVERY result line, counted
    # over the whole capture, so C-6(b) is fully scoreable offline whenever it
    # is ruled on.  C-6's verdict is unaffected either way: it already reads
    # NOT SCOREABLE because `cmd_control` is unimplemented on this tree, so
    # `fz2_control.json` does not exist and `c6 is None`.
    hold_shape = None
    if _need(allines, "term"):
        for r in allines:
            e = r.get("evt")
            t = r.get("term") or {}
            if e:
                holds[e.get("hold")] += 1
            hr = t.get("hold_rows")
            if hr is not None and e:
                if isinstance(hr, (int, float)):
                    if abs(hr - e["hold"]) <= 1:
                        hold_exact += 1
                    else:
                        hold_bad += 1
                else:
                    hold_shape = (f"NOT EVALUABLE: hold_rows is "
                                  f"{type(hr).__name__}, not a scalar -- "
                                  f"finding O-2, C-6(b) awaits a ruling")
    bar("C-6", "the rig applied the directives it was handed",
        "EVT2/EVT3_CFG + TVEC + VECCTL round-trip on the readback path; a "
        "PIN-LEVEL proof by counted rows at >= 2 hold values (every seed's "
        "counted high-row run equals its own `hold`, +/- 1 clock); "
        "interception proven on the rows at >= 2 distinct TVEC values",
        {"holds_in_corpus": dict(holds), "hold_rows_exact": hold_exact,
         "hold_rows_off": hold_bad, "control_leg": c6,
         "pin_level_clause": hold_shape or "scalar",
         "scoreable": _need(allines, "term")},
        "NOT SCOREABLE" if (not _need(allines, "term") or c6 is None
                            or hold_shape)
        else ("MET" if (hold_bad == 0 and len(holds) >= 2
                        and c6.get("verdict") == "MET") else "MISSED"))

    # ---- C-7: the bus-cycle bound -----------------------------------------
    bc = [r["bus_cycles"] for r in allines if r.get("bus_cycles") is not None]
    over = [r["k"] for r in allines if (r.get("bus_cycles") or 0) >= wv.NWVEC]
    bar("C-7", "no capture reaches 4,096 bus cycles",
        "0 seeds at or beyond 4,096",
        {"scored": len(bc), "max": max(bc) if bc else None,
         "at_or_over": len(over), "ks": over[:20]},
        "MET" if (bc and not over) else ("NOT SCOREABLE" if not bc else "MISSED"))

    # ---- C-8 / C-10: board discipline + transport --------------------------
    guards = []
    for f in ("fz2_preflight.json", "fz2_capture.json", "fz2_c9.json",
              "fz2_control.json", "fz2_idle.json"):
        p = OUT / f
        if p.exists():
            guards += json.loads(p.read_text()).get("div_guards", [])
    unpinned = [g for g in guards if g["state"] != "PINNED"]
    bar("C-8", "board discipline",
        "div_guard PINNED on 100 % of probes; 0 unpinned readbacks",
        {"div_guards": len(guards), "unpinned": len(unpinned),
         "unpinned_detail": unpinned},
        "MET" if (guards and not unpinned) else
        ("NOT SCOREABLE" if not guards else "MISSED"))
    cap = json.loads((OUT / "fz2_capture.json").read_text()) \
        if (OUT / "fz2_capture.json").exists() else {}
    c9 = json.loads((OUT / "fz2_c9.json").read_text()) \
        if (OUT / "fz2_c9.json").exists() else {}
    quar = sum(1 for r in allines if r["verdict"] == fc.QUARANTINE)
    runerr = sum(1 for r in allines
                 if str(r.get("sub") or "").startswith("run_error"))
    bar("C-10", "transport", "circuit breaker not tripped; no short stratum; "
        "the transport-error count is REPORTED, not barred",
        {"quarantines": quar, "run_error_lines": runerr,
         "consecutive_quarantine_break_at": _quar_break(allines),
         "halted": cap.get("halted"), "c9_errors": c9.get("errors")},
        "MET" if (cap and not cap.get("halted")
                  and _quar_break(allines) is None) else
        ("NOT SCOREABLE" if not cap else "MISSED"))

    # ---- C-9: stability ----------------------------------------------------
    bar("C-9", "the capture is stable, rows AND arch",
        f"{len(c9_seeds())} / {len(c9_seeds())} stable over {C9_REPS} reps",
        {"seeds": c9.get("n_seeds"), "stable": c9.get("stable"),
         "unstable": c9.get("unstable"), "errors": c9.get("errors")},
        "MET" if (c9.get("stable") == len(c9_seeds()) and not c9.get("unstable")
                  and not c9.get("errors")) else
        ("NOT SCOREABLE" if not c9 else "MISSED"))

    # ---- C-11: bank integrity ---------------------------------------------
    banked = {}
    capped = {}
    for pop in POPS:
        d = ROOT / "tests" / "v30" / "fuzz_bank" / CID[pop]
        mp = d / "manifest.json"
        man = json.loads(mp.read_text()) if mp.exists() else {}
        banked[pop] = sorted(int(p.name.split("_")[1])
                             for p in (d / "seeds").glob("*.json.gz")) \
            if (d / "seeds").exists() else []
        capped[pop] = (man.get("promotion") or {}).get("_capped", 0)
    want = census_bank_seeds()
    exact = banked["census"] == want
    total = len(banked["census"]) + len(banked["enriched"])
    bar("C-11", "bank integrity: the census bank IS the frozen rule and the "
        "two populations are never pooled",
        "census bank == the 480 enumerated seeds, seed for seed; 0 `_capped` "
        "on either cid; standing bank <= 3,500 seeds; 0 seeds in both banks",
        {"census_banked": len(banked["census"]), "census_expected": len(want),
         "census_exact": exact, "enriched_banked": len(banked["enriched"]),
         "capped": capped, "total": total,
         "overlap": len(set(banked["census"]) & set(banked["enriched"]))},
        "MET" if (exact and not any(capped.values()) and total <= 3500
                  and not (set(banked["census"]) & set(banked["enriched"])))
        else ("NOT SCOREABLE" if not banked["census"] else "MISSED"))

    (OUT / "fz2_bars.json").write_text(json.dumps(rec, indent=1))
    print(f"\n{'bar':<5} {'verdict':<14} measured")
    for b in BARS:
        d = rec["bars"][b]
        print(f"{b:<5} {d['verdict']:<14} {json.dumps(d['measured'])[:130]}")
    for pop in POPS:
        p = rec["pops"][pop]
        print(f"\n{pop}: captured {p['captured']}  "
              f"rows-exact {p['rows_exact_mean_pct']}  "
              f"arch-exact {p['arch_exact_mean_pct']}  "
              f"unscoreable {p['unscoreable_total']}   "
              "(three decompositions, never one aggregate)")
    # EXACT string equality, deliberately: A-5's `MET (rate clauses
    # UNVALIDATED -- A-5)` is NOT counted as MET here, and must not be
    # "fixed" into one.  An unvalidated re-registration does not clear a bar
    # (§16.1); the marker comes off when §16.2's disjoint population is
    # measured, and the count follows it then.
    missed = [b for b in BARS if rec["bars"][b]["verdict"] != "MET"]
    print(f"\nFZ2 BARS: {len(BARS)-len(missed)}/{len(BARS)} MET"
          f"{'  NOT MET: ' + ','.join(missed) if missed else ''}")
    return 0 if not missed else 1


def _mean_pct(per, key):
    xs = [100.0 * p[key] / p["captured"] for p in per if p["captured"]]
    return round(sum(xs) / len(xs), 2) if xs else None


def _regen_one(args):
    cid, k, _sha, _vhex = args
    j = _stratum_of(cid, k)
    cfg = fzc.derive_case(cid, k, ov_of(STRATA[j]))
    img, _ = fzc.compose_case(fzc.build(cfg), cfg)
    v = fzc.wvec_of(cfg)
    return (k, cid, hashlib.sha256(bytes(img)).hexdigest(),
            fzc.bad_0f_pairs(img), wv.to_hex(v) if v else None)


def _quar_break(lines):
    run = 0
    for r in lines:
        run = run + 1 if r["verdict"] == fc.QUARANTINE else 0
        if run >= 5:
            return r["k"]
    return None


# --------------------------------------------------------------------------- #
def cmd_idle(a):
    OUT.mkdir(parents=True, exist_ok=True)
    rec = {"stage": "fz2 close", "div_guards": [],
           "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    div_guard("idle", rec["div_guards"])
    board_idle()
    rc, ps, _ = _ssh("ps w | grep -E 'v30ctl|serve' | grep -v grep || true")
    rec["board_procs_after"] = [l for l in ps.splitlines() if l.strip()]
    rec["use_core"] = 0
    rec["board_idle"] = "OK"
    (OUT / "fz2_idle.json").write_text(json.dumps(rec, indent=1))
    print("board_idle: OK, use_core=0 left selected")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("strata")
    p.set_defaults(func=cmd_strata)
    p = sub.add_parser("freeze")
    p.add_argument("--jobs", type=int, default=4)
    p.set_defaults(func=cmd_freeze)
    p = sub.add_parser("lint")
    p.set_defaults(func=cmd_lint)
    p = sub.add_parser("preflight")
    p.add_argument("--sample", type=int, default=4)
    p.add_argument("--board", action="store_true",
                   help="also contact the board (div_guard + check_ab_hw)")
    p.set_defaults(func=cmd_preflight)
    p = sub.add_parser("capture")
    p.add_argument("--host", default=HOST)
    p.add_argument("--pop", choices=POPS, default=None)
    p.set_defaults(func=cmd_capture)
    p = sub.add_parser("stability")
    p.add_argument("--host", default=HOST)
    p.set_defaults(func=cmd_stability)
    p = sub.add_parser("control")
    p.add_argument("--host", default=HOST)
    p.set_defaults(func=cmd_control)
    p = sub.add_parser("bars")
    p.add_argument("--jobs", type=int, default=8)
    p.set_defaults(func=cmd_bars)
    p = sub.add_parser("idle")
    p.set_defaults(func=cmd_idle)
    a = ap.parse_args()
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
