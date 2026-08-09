#!/usr/bin/env python3
"""fuzz_campaign - orchestrator for the massive fuzz expansion (task #29).

Subcommands:
  new     - snapshot axes/knobs + generator git + the pinned flash_log build
            into sw/testdata/campaigns/<CID>/manifest.json
  run     - session of --session-seeds cases: derive -> generate -> compose ->
            capture (board hw-ab chip-then-fabric, or --tb-only) -> classify
            inline -> append-only fsync'd results.jsonl; resume from the jsonl
            tail; RunError -> reconnect+retry-once -> quarantine; >=5 consecutive
            quarantines trips the circuit breaker (wedge house rule); divergent
            captures gzipped immediately; coverage every 500; EscalationPolicy
            consulted after every seed
  status  - roll up a campaign's results.jsonl
  show    - re-derive one case (bit-reproducible from cid,k)
  replay  - parallel Verilator forensics over a set of cases
  lint    - generation-only safety scan (Phase 1 gate)

Everything is reproducible from (campaign_id, k) alone: `cfg/<cid>/<k>` draws
the axes (tier, event, waits) and the program seeds off `soup|raw/<cid>/<k>`.
All derived values are recorded verbatim in each result line; the manifest pins
the generator git SHA and the flashed bitstream.

nmax_eff capture-budget coupling: nmax_eff = max(nmin, nmax*C/(C+wmax)). C is
frozen from the TB pilot done_idx distribution (see NMAX_SCALE_C below).
"""
import argparse
import copy
import dataclasses
import gzip
import hashlib
import json
import math
from collections import Counter
import os
import random
import statistics
import subprocess
import sys
import time
from multiprocessing import Pool
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))
import check_seq                                        # noqa: E402
import fuzz_classify as fc                              # noqa: E402
import fuzz_cov                                         # noqa: E402
import optable                                          # noqa: E402
from fuzz_accept import AcceptEngine, open_bus_escape_metrics   # noqa: E402
from fuzz_classify import Ctx, classify, EscalationPolicy  # noqa: E402
from gen_soup import gen_soup, SoupKnobs                 # noqa: E402
from gen_raw import gen_raw                              # noqa: E402
from v30run import run_image, RunError, RigMismatch     # noqa: E402
import v30ctl                                           # noqa: E402
import wvec_shapes as wv                                # noqa: E402
import testimage as ti                                  # noqa: E402

RESERVED_LO = 0xFF00
NMIN, NMAX = 24, 80
# Capture-budget coupling constant. C=4 == a bus cycle is ~4 clocks (T1-T4), so
# a wmax equal to C halves the instruction budget. Confirmed by the TB pilot:
# at w0 the contained-soup done_idx stayed well inside the 4096-row window with
# nmax=80 (see sw/testdata/tb_pilot_done_dist.json), so the base budget holds
# and C=4 follows from the measured rows/instruction. FROZEN 2026-07-27.
NMAX_SCALE_C = 4
SESSION_SEEDS = 5000
TB_ROWS = 4200
CAMPAIGNS = SW / "testdata" / "campaigns"
FLASH_LOG = SW / "testdata" / "flash_log.jsonl"


# ===========================================================================
# Seed -> config derivation.
# ===========================================================================
def derive_axes(cid, k):
    """Draw the per-seed axes from the `cfg/<cid>/<k>` namespace."""
    r = random.Random(f"cfg/{cid}/{k}")
    tier = "raw" if r.random() < 0.20 else "soup"

    evt = None
    if r.random() < 0.25:
        x = r.random()
        pin = 0 if x < 0.70 else (1 if x < 0.95 else 2)   # INT / NMI / POLL
        if tier == "raw" and pin == 2:
            pin = 0
        delay = int(round(8 * (2048 / 8) ** r.random()))
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

    nmax_eff = max(NMIN, int(NMAX * NMAX_SCALE_C / (NMAX_SCALE_C + weff)))
    return {"cid": cid, "k": k, "tier": tier, "evt": evt, "waits": waits,
            "wild": None, "nmin": NMIN, "nmax_eff": nmax_eff}


NWVEC_BUDGET_HEAD = 1024


def _wvec_weff(v):
    """The capture-budget wait level a VECTOR represents.

    `nmax_eff`'s coupling constant is about CLOCKS (C=4 == a bus cycle is
    ~4 clocks), so the level that belongs in it is the vector's MEAN cost per
    access, not its maximum: a `burst` vector that is 0 everywhere except one
    access in 53 costs almost nothing, and budgeting it at 31 would shrink its
    programs to `NMIN` for no reason.  Rounded UP, over the first quarter of
    the vector (no run in this campaign reaches further -- see the bus-cycle
    bound B-5)."""
    head = v[:NWVEC_BUDGET_HEAD]
    return -(-sum(head) // max(1, len(head)))            # ceil(mean)


# EVERY override key this function knows.  An unknown key RAISES (fuzz-v2 task
# T2 requirement 5): `fence` was deleted here and a caller still passing it
# would otherwise have been accepted-and-ignored -- the exact trap
# `CLAUDE.md` names, and the one that hid `want_raw` for three days.
KNOWN_OV = frozenset({
    "force_tier", "force_contained", "w0", "force_fixed", "no_evt",
    "force_evt", "force_wrand", "strict", "no_brkem", "brkem_high",
    "mainline", "no8080", "wvec_shapes",
})


def derive_case(cid, k, ov=None):
    """derive_axes + optional pilot overrides + nmax_eff recompute + cfg_hash.
    ov keys: KNOWN_OV (an unknown key raises).  (`no8080` is accepted only as
    True and `brkem_high` only as False: see below.)"""
    ov = ov or {}
    unknown = sorted(set(ov) - KNOWN_OV)
    if unknown:
        raise ValueError(
            f"derive_case: unknown override key(s) {unknown}; known = "
            f"{sorted(KNOWN_OV)}.  (`fence` was DELETED by fuzz-v2 task T2: "
            "the v2 image is 0xCC-filled and `fill` now colours only the four "
            "carve-outs, so an HLT fence would fill the IVT, the data window, "
            "the stack and the loader page with 0xF4.)")
    ax = derive_axes(cid, k)
    if ov.get("force_tier"):
        ax["tier"] = ov["force_tier"]
    if ov.get("force_contained"):
        ax["wild"] = False
    if ov.get("w0"):
        ax["waits"] = {"wrand": False, "wmax": None, "wseed": None, "fixed": 0}
    if ov.get("force_fixed") is not None:
        # task #38: `w0` generalised.  A stratified corpus needs fix1/fix2/fix3
        # as CONTROL strata against the vector shapes, and `w0` could only
        # express one of the four.  `w0` is left exactly as it is so every
        # existing invocation still means what it meant.
        ax["waits"] = {"wrand": False, "wmax": None, "wseed": None,
                       "fixed": int(ov["force_fixed"])}
    if ov.get("no_evt"):
        ax["evt"] = None
    if ov.get("force_evt"):
        r = random.Random(f"pilotevt/{cid}/{k}")
        pin = 0 if r.random() < 0.7 else 1                 # INT / NMI mix
        ax["evt"] = {"pin": pin,
                     "delay": int(round(8 * (2048 / 8) ** r.random())),
                     "hold": 2}
    if ov.get("force_wrand"):
        r = random.Random(f"pilotwr/{cid}/{k}")
        wmax = r.choice(ov["force_wrand"])
        ax["waits"] = {"wrand": True, "wmax": wmax, "wseed": r.getrandbits(16),
                       "fixed": None}
    ax["strict"] = bool(ov.get("strict"))
    ax["no_brkem"] = bool(ov.get("no_brkem"))
    ax["brkem_high"] = bool(ov.get("brkem_high"))
    ax["mainline"] = bool(ov.get("mainline"))
    # THE task #32 HLT-FENCE AXIS IS DELETED (fuzz-v2 task T2 requirement 5).
    # It filled non-program image space with 0xF4 so an escape halted in-image.
    # v2 SUPERSEDES it with the 0xCC (INT3) fill, which is strictly better --
    # an escape at ANY alignment vectors to the terminator and still dumps,
    # where a HALT only stopped.  Adapting it was not an option: `fill` in v2
    # colours the four CARVE-OUTS (IVT, data window, stack, loader page), so a
    # fence would now write HALT over the IVT and the data the program reads.
    # A stale `fence` key RAISES in KNOWN_OV above rather than being ignored.
    # fuzz-v2 D9 -- THE 8080 EXCLUSION, BY CONSTRUCTION AND UNCONDITIONALLY.
    # It was task #38's opt-in `no8080` axis, and it was too narrow twice over:
    # it removed only the `0F FF` pair, when silicon says `0F` + ANY byte
    # >= 0x40 is a full BRKEM alias (`docs/facts/undocumented_0f.md`), and it
    # was default-off.  It is now ONE unconditional rule at THREE places that
    # all call `optable.scrub_0f`: `build()` sets `p_brkem = 0`, `gen_raw`
    # scrubs its own buffer, and `compose_case()` scrubs the composed image.
    # There is no axis and no cfg_hash entry, because there is no other
    # configuration to distinguish it from.
    #
    # REGISTERED PREDICTION (falsifiable, NOT CONFIRMED -- confirmation needs
    # the board capture of task T11).  §63.5's 24 unexplained 8080 entries --
    # seeds that reached emulation mode with NO `0F FF` anywhere in the image
    # -- were entering through the alias band this rule now closes.  TWO static
    # routes were MEASURED offline while landing it, both open under the old
    # system and both shut now:
    #   (1) a `0F` immediate or displacement byte meeting the next opcode.
    #       `optable.scan_code` never saw these because it walks INSTRUCTION
    #       BOUNDARIES and they are inside one; they only decode if execution
    #       lands off-boundary.  2,000 soup seeds carried 478 such pairs, 330
    #       of them in the >= 0x40 alias band, and the `0F FF` rule caught 0.
    #   (2) THE OLD SCRUB MADE THEM.  `gen_raw` rewrote only the SECOND byte of
    #       a HARD_BANNED pair to 0x90 -- and 0x90 >= 0x40, so `0F 34` became
    #       `0F 90`, a BRKEM alias by the same silicon finding.  Measured at
    #       ~10 per raw seed (5,032 over 500).  This is why BOTH bytes go.
    #       (0x90 is INFERENCE from the >= 0x40 band, not one of the six
    #       probed second bytes; 0x80 and 0xA0 flank it and both were probed.)
    # FALSIFIED IF a v2 capture still shows a static-route 8080 entry -- an
    # entry reached with no intervening write into the code region.  Even
    # confirmed it is NOT sufficient: a pair can be created at RUNTIME by a
    # write, which is what D9's second (capture-side) clause is for.
    if ov.get("no8080") is False:
        raise ValueError("no8080=False: the 0F scrub is unconditional in "
                         "fuzz-v2 (plan D9); there is no opt-out")
    if ov.get("brkem_high"):
        raise ValueError("brkem_high: refused -- fuzz-v2 eliminates 8080 "
                         "entry unconditionally (plan D9)")
    ax["no8080"] = True
    # task #38 -- THE PER-ACCESS WAIT VECTOR AXIS.
    # Drawn from this axis's OWN rng namespace, exactly as `force_wrand` and
    # `force_evt` do, so `derive_axes`'s frozen stream is untouched and every
    # banked seed in the tree still re-derives to its own program.
    ax["wvec"] = None
    if ov.get("wvec_shapes"):
        shapes = list(ov["wvec_shapes"])
        r = random.Random(f"wrfuzz/{cid}/{k}")
        ax["wvec"] = wv.draw_spec(cid, k, r.choice(shapes))
        # The vector SUPERSEDES both other wait sources in all three legs
        # (nec_bus.sv / tb_v30_core.sv / biu_timed.cpp all order replay >
        # random > uniform), so the record says so instead of carrying a
        # `waits` field that describes nothing.
        ax["waits"] = {"wrand": False, "wmax": None, "wseed": None, "fixed": 0}
    w = ax["waits"]
    if ax["wvec"]:
        weff = _wvec_weff(wv.build(ax["wvec"]))
    else:
        weff = w["wmax"] if w["wrand"] else w["fixed"]
    ax["nmax_eff"] = max(NMIN, int(NMAX * NMAX_SCALE_C / (NMAX_SCALE_C + weff)))
    core = {kk: ax[kk] for kk in ("tier", "evt", "waits", "wild", "nmax_eff",
                                  "strict", "no_brkem", "brkem_high",
                                  "mainline")}
    # task #38: the two new axes are in the hash, and they are added ONLY WHEN
    # SET.  Two configs differing in a vector spec MUST hash differently (the
    # lint proves it); a config with the axis OFF must hash exactly as it did
    # before task #38 existed, so a seed banked earlier still re-derives to its
    # own `cfg_hash` and its own banked FILENAME.  For these two axes
    # "off" and "the axis did not exist" are the same configuration, which is
    # what makes the omission true rather than convenient.
    # ⚠ FALSIFIER FOR THE RULE ITSELF: an axis whose default is a CHOICE
    # rather than an absence must be added UNCONDITIONALLY, or two genuinely
    # different configurations collide.  Do not copy this pattern without
    # checking that.
    if ax["wvec"]:
        core["wvec"] = ax["wvec"]
    # `no8080` is NOT in the hash: it is no longer an axis but a property of
    # every v2 image, and a hash entry with one possible value distinguishes
    # nothing.  What the images being different DOES change is `image_sha256`,
    # which is the thing the bank's GEN-DRIFT gate actually compares.
    ax["cfg_hash"] = hashlib.sha1(
        json.dumps(core, sort_keys=True).encode()).hexdigest()[:12]
    return ax


def build(cfg):
    """Materialise the g-dict for a derived config."""
    seed = f"{cfg['cid']}/{cfg['k']}"
    if cfg["tier"] == "raw":
        g = gen_raw(seed)
    else:
        pin = cfg["evt"]["pin"] if cfg["evt"] else None
        # strict = contained fall-through generation: suppress the deliberate
        # no-done breadth classes (BRKEM 8080-entry, TF single-step storm, undoc
        # opcodes, random-DS window escape) so the pilot measures fall-through.
        if cfg.get("strict"):
            knobs = SoupKnobs(p_brkem=0.0, p_tf=0.0, p_undoc=0.0, p_sreg_rand=0.0)
        elif cfg.get("mainline"):
            # mainline bug-hunt: suppress the DELIBERATE chip-vs-core-divergent
            # classes (BRKEM 8080-entry, TF single-step, undoc opcodes - the
            # chip implements behaviours the core intentionally does not) so any
            # FUNCTIONAL is a REAL mainline divergence. Keep random-DS (window-
            # only, func-clean chip==core) for breadth. Census: task #29 Phase 5.
            knobs = SoupKnobs(p_brkem=0.0, p_tf=0.0, p_undoc=0.0)
        elif cfg.get("no_brkem"):
            knobs = SoupKnobs(p_brkem=0.0)     # keep tf/undoc/sreg breadth (cheap)
        else:
            knobs = SoupKnobs()
        # fuzz-v2 D9: the 8080 exclusion AT THE KNOB, UNCONDITIONALLY and as a
        # MODIFIER, so it composes with every knob set instead of replacing
        # one.  Only BRKEM is out of scope; undoc / tf / sreg breadth is this
        # campaign's own breadth and is left alone.  The soup lint's 0F check
        # is keyed on the same allowed set, so re-raising `p_brkem` fails lint
        # loudly instead of silently disagreeing with the composed image.
        knobs = dataclasses.replace(knobs, p_brkem=0.0)
        g = gen_soup(seed, nmin=cfg["nmin"], nmax=cfg["nmax_eff"],
                     evt_pin=pin, wild=cfg["wild"], knobs=knobs)
    if cfg["evt"] and g.get("has_halt"):
        cfg["evt"]["hold"] = 300
    if cfg["evt"]:
        # F46 / gap R1: `hold` is what the HOST ASKED FOR.  Record what the RIG
        # CAN APPLY beside it, so a banked seed says which one its capture was
        # taken under instead of leaving it to be re-derived from an RTL width
        # that has already changed once.  These are added AFTER `cfg_hash` is
        # computed (derive_case) on purpose: the hash covers the axes, and the
        # rig's register width is not one of them.
        cfg["evt"]["hold_bits"] = v30ctl.RIG_EVT_HOLD_BITS
        cfg["evt"]["hold_applied"] = (cfg["evt"]["hold"]
                                      & ((1 << v30ctl.RIG_EVT_HOLD_BITS) - 1))
    return g


def scrub_0f_image(image):
    """Apply THE 0F RULE to a composed image over `optable.CODE_SPANS`.
    Returns (image, n_pairs).

    ONE RULE, held in `optable.scrub_0f` and stated there: a `0F` byte may be
    followed only by a byte in `optable.SCRUB_ALLOWED_0F`; every other `0F xx`
    pair becomes `90 90`.  It replaces `scrub_brkem_image`, which removed only
    the `0F FF` pair -- about 1/192 of the surface silicon actually has, since
    `docs/facts/undocumented_0f.md` measured that `0F` + ANY byte >= 0x40 is a
    full BRKEM alias.  With the v2 `0xCC` fill that gap was not academic:
    `0xCC >= 0x40`, so every body byte `0x0F` abutting the fill was an alias.

    `bad_0f_pairs()` is the independent check that says so on the artifact
    rather than in the argument."""
    buf = bytearray(image)
    n = optable.scrub_0f(buf, optable.CODE_SPANS)
    return bytes(buf), n


def bad_0f_pairs(image):
    """The check, not the argument: how many forbidden `0F xx` pairs remain in
    the code region.  Strictly stronger than the `no_brkem_pairs()` it
    replaces -- 0 here means no BRKEM pair AND no alias AND no lockup."""
    return len(optable.bad_0f_hits(bytes(image), optable.CODE_SPANS))


def compose_case(g, cfg):
    """`check_seq.compose` plus this campaign's image-level rules.

    THE ONE PLACE the composed image is built for a fuzz case, so that
    `eval_case`, `show`, `lint` and `ucsim_fuzz.regen` cannot drift apart --
    a regeneration path that composes differently from the capture path is the
    GEN-DRIFT failure the bank's sha gate exists to catch, and the cheapest way
    to never have it is to have one function.

    ⚠ THE 0F SCRUB IS UNCONDITIONAL (fuzz-v2 plan D9: "compose_case changes
    unconditionally; there is no version dispatch and no default-off axis").
    Every image composed here therefore differs from the one the same (cid, k)
    composed before this landing wherever a forbidden pair existed, so every
    seed of the DISCARDED v1 bank re-derives to a new sha256.  That is the
    intended consequence of the user's corpus decision, not an accident."""
    image, meta = check_seq.compose(g)
    image, _ = scrub_0f_image(image)
    return image, meta


def _weff(cfg):
    w = cfg["waits"]
    return w["wmax"] if w["wrand"] else w["fixed"]


def _waits_class_line(line):
    v = line.get("wvec")
    if v:
        return f"wvec-{v['shape']}"
    w = line.get("waits") or {}
    return "wrand" if w.get("wrand") else f"w{w.get('fixed', 0)}"


# ===========================================================================
# Capture legs.
# ===========================================================================
def _evt_tuple(cfg, meta):
    if not cfg["evt"]:
        return None
    e = cfg["evt"]
    return (meta["anchor_linear"] & 0xFFFFF, e["delay"], e["hold"], e["pin"])


# --------------------------------------------------------------------------- #
# THE TERMINATING NMI (fuzz-v2 plan D3, pre-registered in
# `docs/notes/fz2_corpus_prereg_2026-08-08.md` §3.1-§3.3).
#
# The image's INT3 backstop is broken by a runtime write over IVT[3] or over
# the terminator.  The NMI route is IMMUNE TO THE IVT by construction: the rig
# SUBSTITUTES THE VECTOR DATA at linear 0x00008 / 0x0000A from a register, so
# there is nothing in memory for the seed to scribble.  That is the whole
# reason `TVEC` is a register and not a pre-written image word.
#
# ONE directive, no per-seed table:
#   * scheduler `TERM_SCHED` (2), triggered on the anchor's own CODE T1 -- the
#     same trigger the stimulus event uses, so there is one anchor, not two;
#   * `TERM_CLOCKS` clocks later, `TERM_HOLD` clocks of NMI;
#   * `vecsub_en` set for THAT SCHEDULER ONLY, so a stimulus NMI on scheduler 0
#     enters through the seed's own IVT and only the terminator is substituted.
#
# The scheduler index, hold and vecsub mask are the ones `sw/fz2_tbsys.py`
# leg (d) proved on `tb_sys` -- the leg whose whole point is that a stimulus
# NMI and a terminating NMI coexist -- and are not re-chosen here.
# --------------------------------------------------------------------------- #
# AMENDMENT A-3 (2026-08-09, prereg sec.13).  The three constants below were
# CORRECTED after finding O-2a; `sw/fz2_termcost.py` is the instrument and it
# re-derives every number offline from the archived INV-2 capture.  What was
# wrong, stated as a property of the artifact:
#
#  * ANCHOR_W0 was 145, measured on the ucore TB in POST-RESET row numbers.
#    The reserve is subtracted from `CAP_ROWS`, which counts from record 0, and
#    the board holds RESET for the first 33 records.  On the board the anchor's
#    CODE T1 lands at absolute row 180 -- EXACTLY, on all 353 fixed-wait banked
#    captures, in BOTH tiers (180/242/275/308 at w0/w1/w2/w3).  A COORDINATE
#    error of 35 rows, not a tier effect.
#  * DUMP_W0 was 240 = 219 MEASURED (the dump proper) + 21 ESTIMATED for "the
#    NMI entry's two vector reads and three pushes".  The 219 is exact and
#    stands -- it reproduces to the clock on the board, both tiers.  The 21 is
#    the whole defect: the measured NMI-assert -> first `OUT 0xFE` cost is 53
#    minimum, 77 median, 463 maximum over 303 banked captures.
#  * The NMI ACCEPTANCE LATENCY -- the wait for the instruction boundary at
#    which NMI is taken -- was in no term of the formula at all.  It is named
#    now, as `ENTRY_MAX`, and it is added OUTSIDE the scaling because the
#    measurement says it is a CLOCK cost and not a bus-cycle cost: its maximum
#    shows no trend with `scale` (243 at scale 1.00, 305 at scale 4.75, and
#    max/scale FALLS monotonically over the eight scale levels the corpus
#    carries).  FALSIFIER: if the residue after this repair concentrates at
#    high `weff`, the term scales and this form is wrong.
#
# Net effect on the artifact that was mis-budgeted: the tail room left after
# the NMI assert was 281/335/417/500 rows at w0/w1/w2/w3 against a MEASURED
# tail floor of 273 at w0 and 499 at w3 -- 7 rows of slack at w0 and ONE at w3,
# for every seed in the corpus.  The observed required-reserve distribution is
# censored EXACTLY at 462.0 = TERM_MARGIN x 385, which is the arithmetic proof
# that the budget and not the seed was the binding limit.
CAP_ROWS = v30ctl.CAP_RECORDS      # 4,096 -- the rig's capture depth
ANCHOR_W0 = 180                    # MEASURED on the board, ABSOLUTE capture row
DUMP_W0 = 219                      # MEASURED: first `OUT 0xFE` -> done marker
ENTRY_MAX = 463                    # MEASURED: NMI assert -> first `OUT 0xFE`
TERM_MARGIN = 1.2                  # a DECLARED margin, not a fit
TERM_FLOOR = 512                   # registered floor on every seed's delay
TERM_SCHED = 2                     # scheduler 2 == the `evt3=` option
TERM_HOLD = 20                     # clocks of NMI (fz2_tbsys leg (a)/(d))
TERM_PIN = 1                       # 1 = NMI
TERM_VECSUB = 1 << TERM_SCHED      # VECCTL: only the terminator substitutes
TERM_TVEC = (0x0000, ti.TERM_AT)   # CS:IP -> the termination handler


def weff_of(cfg):
    """The seed's EFFECTIVE wait level -- the vector's ceil-mean when it has a
    vector, otherwise `wmax`/`fixed`.  `_weff` below is the older, vector-blind
    form kept for the coverage roll-up's own axis; this is the one the capture
    budget and `term_clocks` use, and there is no third rule."""
    if cfg.get("wvec"):
        return _wvec_weff(wv.build(cfg["wvec"]))
    w = cfg["waits"]
    return w["wmax"] if w["wrand"] else w["fixed"]


def term_clocks(weff):
    """ONE FORMULA, reusing the capture budget's OWN coupling constant.  The
    delay must be late enough not to truncate a normal run and early enough to
    leave the dump inside the 4,096-record capture.

    Three terms, each MEASURED (A-3), and one DECLARED margin:

        scale       = (NMAX_SCALE_C + weff) / NMAX_SCALE_C
        TERM_CLOCKS = CAP_ROWS
                      - ceil(TERM_MARGIN * (ANCHOR_W0 + DUMP_W0) * scale)
                      - ENTRY_MAX

    `ANCHOR_W0` and `DUMP_W0` are bus-cycle costs and scale; `ENTRY_MAX` is the
    NMI acceptance latency, which the measurement says is a CLOCK cost, and it
    is therefore added outside the scaling.  ONE formula and ONE set of
    constants for BOTH tiers: soup and raw were measured separately and are
    IDENTICAL in all three terms (anchor 180, dump 219, entry floor 53), so a
    per-tier table would be a fitted table with nothing to fit."""
    scale = (NMAX_SCALE_C + weff) / NMAX_SCALE_C
    return (CAP_ROWS - math.ceil(TERM_MARGIN * (ANCHOR_W0 + DUMP_W0) * scale)
            - ENTRY_MAX)


def term_directive(cfg, meta):
    """-> (evts, tvec, vecsub) for `run_chip`, with the seed's stimulus event
    (if any) on scheduler 0 and the terminator on `TERM_SCHED`."""
    evts = [None] * v30ctl.EVT_N
    evts[0] = _evt_tuple(cfg, meta)
    d = term_clocks(weff_of(cfg))
    assert d >= TERM_FLOOR, f"TERM_CLOCKS {d} below the registered floor"
    evts[TERM_SCHED] = (meta["anchor_linear"] & 0xFFFFF, d, TERM_HOLD,
                        TERM_PIN)
    return evts, TERM_TVEC, TERM_VECSUB


def wvec_of(cfg):
    """The seed's per-access wait vector, or None.  ALWAYS exactly
    `wv.NWVEC` entries: a short load leaves the board's replay RAM holding the
    PREVIOUS run's tail (`v30ctl.load_wvec` writes only what it is given) and
    sends the three legs three different ways past the end.  See
    `wvec_shapes` properties (2) and (3)."""
    if not cfg.get("wvec"):
        return None
    v = wv.build(cfg["wvec"])
    assert len(v) == wv.NWVEC, f"wvec length {len(v)} != {wv.NWVEC}"
    return v


def capture_tb(image, meta, cfg, core=None):
    """Single Verilator TB leg (temp hygiene handled inside run_tb).

    `core=None` is `check_seq.CORE`, i.e. the ARCHIVED fsm core -- see
    `tb_engine()` below, which is the call that makes the engine SAY WHICH ONE
    IT IS instead of leaving it to a module-level pin."""
    w = cfg["waits"]
    wrand = (w["wmax"], w["wseed"]) if w["wrand"] else None
    fixed = 0 if w["wrand"] else w["fixed"]
    return check_seq.run_tb(image, TB_ROWS, waits=fixed,
                            evt=_evt_tuple(cfg, meta), wrand=wrand,
                            wvec=wvec_of(cfg), core=core)


def tb_engine(core=None):
    """WHICH ENGINE A TB LEG ACTUALLY RAN -- (core, path, receipt id).

    Erratum E-1 was taken on the archived fsm core because `check_seq.CORE` is
    pinned to it and NOTHING IN THE OUTPUT SAID SO.  Every tool here that runs
    a TB leg prints this triple, and it is derived three independent ways:

      * `check_seq.tb_bin(core)` -- the binary that will be executed, built
        and proved fresh against this tree by the artifact layer;
      * `timed_fuzz.tb_bin(core)` -- the INDEPENDENT path rule (`obj_dir` for
        fsm, `obj_dir_<core>` otherwise), ASSERTED equal.  A `--core` flag
        that is accepted and ignored fails here rather than in a footnote;
      * `artifact.receipt_id` -- the bytes that binary was built from."""
    import artifact                                          # noqa: PLC0415
    import timed_fuzz                                        # noqa: PLC0415
    binp = Path(check_seq.tb_bin(core))
    want = Path(timed_fuzz.tb_bin(core if core is not None else check_seq.CORE))
    assert binp.resolve() == want.resolve(), \
        f"--core {core}: ran {binp}, timed_fuzz.tb_bin says {want}"
    return (core if core is not None else check_seq.CORE, str(binp),
            artifact.receipt_id(binp))


def capture_board(image, meta, cfg, host, term_out=None):
    """hw-ab: socketed chip (use_core=0) then fabric core (use_core=1), same
    image/evt/wrand/TVEC/VECCTL. ensure() force-cleans the rig at connect. One
    reconnect + retry on RunError, else the caller quarantines.

    THE TERMINATING NMI IS ARMED HERE, unconditionally and for every seed --
    `term_directive` above, `tvec` + `vecsub` on both legs of the A/B pair.
    There is no version dispatch and no default-off axis, on the same footing
    as `compose_case`'s unconditional 0F scrub (plan D9): the v1 bank is
    already discarded by that change, so a second, quieter split would buy
    nothing and cost a mode nobody can see in a result line.

    `pin_share=True` is the explicit consent the rig demands when two
    schedulers land on one pin -- a seed whose stimulus event is itself an NMI
    beside the terminating NMI.  It is passed because the OVERLAY IS KEYED ON
    WHICH DIRECTIVE FIRED, not on which pin went high, which is the only
    formulation under which the two coexist; it is not inferred from `vecsub`.

    `term_out`, when given, receives the SOCKET leg's rig readback and STATUS
    bits (`fired`, `vec_used`), which is what the result line's `term` column
    is scored from."""
    w = cfg["waits"]
    wrand = (w["wmax"], w["wseed"]) if w["wrand"] else None
    fixed = 0 if w["wrand"] else w["fixed"]
    evts, tvec, vecsub = term_directive(cfg, meta)
    vec = wvec_of(cfg)
    for attempt in (1, 2):
        try:
            real = check_seq.run_chip(image, host, use_core=False, waits=fixed,
                                      evts=evts, wrand=wrand, wvec=vec,
                                      tvec=tvec, vecsub=vecsub,
                                      pin_share=True, term_out=term_out)
            sim = check_seq.run_chip(image, host, use_core=True, waits=fixed,
                                     evts=evts, wrand=wrand, wvec=vec,
                                     tvec=tvec, vecsub=vecsub,
                                     pin_share=True)
            return real, sim, None
        except RigMismatch:
            # NOT quarantine material.  C-10's reconnect+retry+quarantine
            # ladder is for TRANSPORT faults; a rig holding a directive other
            # than the one it was handed is INV-1 happening again, and the
            # disposition is to STOP, fix the rig and RE-CAPTURE.
            raise
        except RunError as e:
            if attempt == 2:
                return None, None, f"run_error:{e}"
    return None, None, "run_error:unreachable"


def _raw_lea_mod3_pos(image, real):
    """Detect an EXECUTED illegal LEA (0x8d) mod=11 in a raw seed (task #31,
    k=6475): raw carries no gen-time lea_mod3 provenance, so recover it from the
    capture. Walk the executed in-image code-fetch PCs; from each contiguous
    region's entry, linear-decode via optable.ilen and flag any 0x8d whose modrm
    has mod==11 landing on an instruction boundary that the EU reached. Returns
    [(linear, dest_reg)] (LEA only - LDS/BOUND/LES mod=11 PARK, per the task #30
    whitelist re-confirmed in task #31, so they never produce a value divergence
    to accept)."""
    import optable
    pcs = []
    for r in real:
        if fc._tstate(r) == 1 and r["bs_early"] == 4:
            a = r["ad_addr"] & 0xFFFFF
            # fuzz-v2 T12, finding F5.  The filter here was `a < 0x10000`,
            # written when every seed ran at PS=0 so a code fetch was always a
            # 16-bit address.  Under D1's segment randomization a fetch is
            # normally ABOVE 64K -- 15 of 16 seeds -- so the filter silently
            # recovered nothing and the raw lea_mod3 rule went vacuous for
            # them.  It is DELETED, not widened: there is no open bus on this
            # rig (test_mem.sv decodes addr[15:1] only), so every 20-bit
            # address answers with mirrored image bytes and "is this fetch in
            # the image" is not a question that can be asked.  The decode below
            # already works in the physical domain (`image[pc & 0xFFFF]`); only
            # this collection step was in the wrong one.
            #
            # `out` stays 20-bit LINEAR on purpose: `fuzz_accept` matches it
            # against `r["ad_addr"] & 0xFFFFF` and `gen_soup.lea_mod3_pos`
            # emits linear too.  Returning the physical offset would have made
            # the rule match nothing -- the same vacuity by the opposite error.
            if not pcs or pcs[-1] != a:
                pcs.append(a)
    pcset = set(pcs)
    out = []
    seen_entry = set()
    for entry in sorted(pcset):
        if entry in seen_entry:
            continue
        pc = entry
        for _ in range(64):
            if pc not in pcset or pc in seen_entry:
                break
            seen_entry.add(pc)
            op = image[pc & 0xFFFF]
            if op == 0x8d:                          # LEA
                mrm = image[(pc + 1) & 0xFFFF]
                if (mrm >> 6) == 3:                 # mod=11 (illegal register form)
                    out.append((pc, (mrm >> 3) & 7))
            try:
                L = optable.ilen(image, pc & 0xFFFF)
            except Exception:                       # noqa: BLE001
                L = 1
            pc += max(1, L)
    return out


def _ctx_for(cfg, g, tb_only):
    w = cfg["waits"]
    # A wvec seed is a VARYING-wait run, so the classifier is told `wrand`:
    # the flag's meaning in `fuzz_classify` is "the wait level is not constant
    # across accesses", which is exactly what a vector makes true.  It is NOT
    # told the vector -- no accept rule is keyed on the new axis, because a
    # rule written for an axis before that axis has ever been surveyed is a
    # fitted rule.
    varying = w["wrand"] or bool(cfg.get("wvec"))
    return Ctx(tier="A" if cfg["tier"] == "soup" else "B",
               waits=0 if varying else w["fixed"], wrand=varying,
               real_is_chip=not tb_only,
               brkem_pos=g.get("brkem_pos", []),
               lea_mod3_pos=g.get("lea_mod3_pos", []),
               has_halt=g.get("has_halt", False),
               with_drift=(w["wrand"] or (not w["wrand"] and w["fixed"] > 0)),
               cid=cfg["cid"], seed=f"{cfg['cid']}/{cfg['k']}",
               cfg_hash=cfg["cfg_hash"])


def _escape_count(recs, window):
    """How many CODE fetches in the window came from outside the code region
    and the loader page -- `fuzz_classify.escaped_code_region`'s predicate,
    COUNTED instead of stopping at the first.  Erratum E-1 quotes a median
    per-seed count, so the count has to exist."""
    n = 0
    for r in recs[:window]:
        if fc._tstate(r) == 1 and r["bs_early"] == 4:
            p = r["ad_addr"] & 0xFFFF
            if not (fc.CODE_LO <= p < fc.CODE_HI) and p not in fc.RESERVED:
                n += 1
    return n


# ===========================================================================
# Result line (harmonised schema).
# ===========================================================================
# task #38 (wrfuzz W1) -- THE ERA STAMP, ON EVERY CAPTURE AND NOT ONLY ON THE
# MANIFEST.  Bar B-2 of the corpus pre-registration asks that *every capture*
# carry the artifact layer's input-manifest hash for the bitstream/RTL layer,
# the generator git SHA, `RIG_EVT_HOLD_BITS` and the pinned `flash_log` entry.
# The manifest already carried the flash pin, but a manifest is one file that
# can be rewritten after the fact; a per-line stamp is what makes ABSENT /
# MIXED / MISMATCH READABLE OFF THE RESULTS THEMSELVES.  `None` when nothing
# set it (every pre-task-#38 invocation, and `--tb-only`), so no existing
# reader changes meaning and no image byte moves -- the stamp is provenance
# and is NOT in `cfg_hash`.
_ERA = None


def set_era(era):
    global _ERA
    _ERA = era


def era_of(manifest):
    """The era block for a campaign manifest: the flash pin, the artifact
    receipt whose OUTPUT is that same `.sof` (so the RTL input manifest is
    named, not assumed), the generator SHA and the rig's evt-hold width."""
    pin = (manifest or {}).get("flash_pin") or {}
    sof = pin.get("sha256")
    rtl = {"receipt_id": None, "inputs_sha256": None, "n_files": None,
           "label": None}
    rp = SW / "testdata" / "receipts" / "quartus_bitstream.jsonl"
    if sof and rp.exists():
        for ln in rp.read_text().splitlines():
            ln = ln.strip()
            if not ln:
                continue
            try:
                r = json.loads(ln)
            except Exception:                           # noqa: BLE001
                continue
            if sof in json.dumps(r.get("outputs", {})):
                rtl = {"receipt_id": r.get("id"),
                       "inputs_sha256": r.get("inputs", {}).get("sha256"),
                       "n_files": r.get("inputs", {}).get("n_files"),
                       "label": r.get("label")}
    return {"sof_sha256": sof, "flash_ts": pin.get("ts"),
            "flash_git": pin.get("git_describe"),
            "flash_verify": pin.get("verify"),
            "rtl": rtl, "gen_git": _gen_git(),
            "rig_evt_hold_bits": v30ctl.RIG_EVT_HOLD_BITS,
            "rules_version": (manifest or {}).get("rules_version")}


def _ps3_8080(recs, win):
    """C-3's RUNTIME clause: PS3 set on a CODE T1 inside the window.  This is
    `timed_fuzz.native_exclusion`'s predicate, transcribed to take rows rather
    than a bank entry, so a native seed that merely CONTAINS BRKEM bytes is
    not excluded -- only one that actually entered emulation mode.  8080/BRKEM
    is deferred by user decision, so the seed is a DISCARD with the reason on
    its own result line, not a failure.

    ⚠ SOCKET (`use_core=0`) ROWS ONLY -- AMENDMENT A-2, and this is MEASURED,
    not assumed.  Only the SOCKET leg's `ps` column is the STATUS nibble at a
    `CODE` T1: the reset fetch at linear 0xFFFF0 reads `ps = 0x2`, i.e.
    {md, ie, CS}.  On the FABRIC-CORE leg (`use_core=1`) and on the Verilator
    TB's rows the same column at the same row reads `0xF`, the ADDRESS nibble
    A19-16 -- the two legs switch the pads from address to status one clock
    apart, and `diff_rows` never had to notice because it compares `ps` at T2
    only.  So on a core leg the predicate fires on the reset fetch of EVERY
    capture (382 of 382 archived board pairs, finding O-1).

    Sampling at T2 instead does NOT repair it: measured over the same 382
    pairs the core leg still fires on 103, and on the `t30-brkem` bank -- the
    one population where 8080 entry is known to exist -- a T2 core-leg sample
    detects 0 of the 87 entries the socket leg sees.  The mechanism is the RTL,
    not the comparator: `v30u_biu.data_ps` is `{md8080, psw_ie, segc}` and
    `md8080` is `v30u_eu.mode8080`, set only by an `MFC` row on the BRKEM path
    that is ledger R4, UNIMPLEMENTED.  The core's status PS3 is structurally 0,
    so a core-leg mode clause has nothing to detect even in principle.  The
    caller therefore asks this of the SOCKET leg alone and banks the core leg's
    answer as the non-gating diagnostic `ps3_8080_core`; see `eval_case`.

    The `CODE` term is what avoids the retained-PS3-on-stack-writes false
    positive, not the `T1` term: over the 382 pairs the same one seed
    (`wr1/219060`, PS3 on a MEMW at both T1 and T2) is the only thing `CODE`
    removes, at either T-state, and on the socket leg the T1 and T2 forms
    select the identical seed set (99/99 there, 87/87 on `t30-brkem`) with the
    first firing row exactly one later.  T1 is kept because it is unchanged and
    because it is `timed_fuzz.native_exclusion`'s own form."""
    if not recs:
        return None
    for r in recs[:min(win, len(recs))]:
        if r.get("t_state", r.get("t")) == 1 and r.get("bs_early") == 4 \
                and (int(r.get("ps", 0)) & 8):
            return True
    return False


def _wrote_term(recs, win):
    """§3.4: a MEMW or IOW into [TERM_AT, CODE_HI) before the first done
    marker.  The program overwrote the thing that terminates it -- the one leak
    plan D2 says is not preventable, declared as a discard class in advance.

    Returns [row, "MEMW"|"IOW", addr] for the first such cycle, or None.  The
    caller banks the BOOLEAN as `wrote_term` (the registered predicate) and
    this triple as `wrote_term_at`.

    ⚠ A NOTE FOR WHOEVER SCORES C-1, recorded rather than acted on: the
    registered predicate names IOW as well as MEMW, and on THIS rig an IOW
    cannot overwrite memory -- `hdl/rtl/test_mem.sv:48-49` gates both write
    enables on `cycle_type == BS_MEMW`, so an `OUT 0xBF00, AW` is a false
    positive.  (It was not always so: the `tb_v30_core` defect closed at SM3
    sitting 6 committed IOW cycles into `mem[]`, which is very likely where
    the clause comes from.)  The predicate is implemented AS REGISTERED and
    the evidence is banked beside it, so dropping the IOW clause is a
    one-line decision somebody can take on the numbers instead of a silent
    re-key here."""
    if not recs:
        return None
    for i, r in enumerate(recs[:min(win, len(recs))]):
        if r.get("t_state", r.get("t")) != 1:
            continue
        bs = r.get("bs_early")
        addr = r["ad_addr"] & 0xFFFF
        if bs == 2 and addr == ti.OUT_PORT_DONE:
            return None                      # reached the done marker first
        if bs in (2, 6) and ti.TERM_AT <= addr < ti.CODE_HI:
            return [i, "IOW" if bs == 2 else "MEMW", addr]
    return None


PIN_COL = {0: "pin_int", 1: "pin_nmi", 2: "pin_poll_n"}


def _pin_runs(recs, win):
    """C-6(b)'s PIN-LEVEL evidence, COUNTED OFF THE ROWS: every maximal run of
    consecutive rows on which each pin is asserted, as `[start, length]`.

    The levels are `nec_bus.sv`'s EFFECTIVE pins ([54:52]) -- host PINS OR-ed
    with every armed scheduler -- decoded since T11; before that
    `decode_words` skipped them and this could not be measured at all.
    POLL_N is ACTIVE LOW and counts as asserted when the level is 0.

    ALL THREE PINS, and every run, not the longest: with a stimulus NMI and a
    terminating NMI on the same wire the longest run is whichever held longer,
    and the bar asks whether each directive's OWN hold is on the pin.  Picking
    one number here would be answering the question in the instrument.

    Returns None when the rows carry no pin columns (the Verilator TB's do
    not) -- never an empty dict, which would read as a measured absence."""
    if not recs or PIN_COL[0] not in recs[0]:
        return None
    out = {}
    for pin, key in PIN_COL.items():
        runs, start = [], None
        for i, r in enumerate(recs[:min(win, len(recs))]):
            hi = (r[key] == 0) if pin == 2 else (r[key] == 1)
            if hi and start is None:
                start = i
            elif not hi and start is not None:
                runs.append([start, i - start])
                start = None
        if start is not None:
            runs.append([start, min(win, len(recs)) - start])
        out[key] = runs
    return out


def _vec_rows(recs, win):
    """How many rows the NMI vector-read overlay was ARMED for ([59]).  C-6(c)
    reads the interception off the rows; a seed whose capture is not banked
    still carries this one number on its result line."""
    if not recs or "vec_armed" not in recs[0]:
        return None
    return sum(1 for r in recs[:min(win, len(recs))] if r["vec_armed"])


BS_HALT, BS_PASV = 3, 7
# AMENDMENT A-4.  How long the bus must ALREADY have been quiet when the
# terminating NMI asserts before the part counts as having stopped BEFORE the
# terminator rather than because of it.  It is a clock count, not a fit: the
# longest non-HALT pre-NMI idle measured on a capture that DID reach the
# terminator is 213 clocks over 1,114 such captures in both banks, and the
# shortest one this class carries is 276.  The threshold is not what makes the
# falsifier pass -- clause (3) does that on its own -- and A-4 says so.
STALL_IDLE = 200


def stall_evidence(real, sim, hold_rows):
    """AMENDMENT A-4's fourth declared discard class, measured on the SOCKET
    leg's own rows: THE PART STOPPED BEFORE THE TERMINATOR ARRIVED, AND THE
    TERMINATOR DOES NOT RESTART IT.

    `f` is the row the terminating NMI asserts -- the unique `pin_nmi` run of
    length `TERM_HOLD`, the same identification `fz2_termcost` uses (a stimulus
    NMI holds 2 or 300 and is a different run).  `last` is the last non-PASV
    row before `f`.  `stalled` is TRUE iff ALL THREE hold:

      1. NOT A HALT -- `last.bs != HALT`.  A HALTed part is asleep, not
         stopped, and the NMI wakes it; §87.A's illegal-form stall drives no
         HALT status at all, because nothing announced it.  Leaving the HALT
         case out is what stops this class from swallowing plan D3's own
         subject -- an unwoken HALT is a FINDING about the backstop and must
         stay visible as UNDISPOSITIONED.
      2. STOPPED BEFORE THE TERMINATOR -- `f - last.idx >= STALL_IDLE`.  The
         bus was already quiet when the pin went high, so whatever stopped it
         happened before the terminator was scheduled and not because of it.
         Clauses (1) and (2) are computed from PRE-NMI rows alone and are
         therefore causally prior to everything the terminator does.
      3. STILL STOPPED AFTER IT -- not one non-PASV row at or after `f`.  The
         NMI asserts for its 20 clocks and the part issues no bus cycle at
         all: not a vector read, not a push, nothing.  This is STRICTLY
         STRONGER than "no dump" -- of the not-reached captures this class
         does NOT take, every one has post-NMI bus activity -- so the clause
         partitions the failures rather than restating them.

    Returns None when the question cannot be asked of these rows (no rows, no
    pin columns, no unique terminating NMI run) -- never False, which would
    read as a measured absence.  Otherwise a dict; the caller banks
    `stalled` = the boolean and this dict as `stalled_at`.

    THE POSITIVE HALF IS BANKED WITH IT.  A stalled seed is not a seed that
    contributed nothing: `core_last` is the same measurement on the FABRIC
    CORE's rows and `core_match` is whether the two engines park on the SAME
    CLOCK.  That is a real chip-vs-core agreement on a real mechanism, and it
    is recorded here so the discard does not discard the evidence."""
    if not real or not hold_rows:
        return None
    runs = hold_rows.get("pin_nmi") or []
    base = real[0]["idx"]
    hits = [s + base for s, L in runs if L == TERM_HOLD]
    if len(hits) != 1:
        return None
    f = hits[0]

    def leg(rows):
        if not rows:
            return None, 0
        act = [r for r in rows if r["idx"] < f and r["bs_early"] != BS_PASV]
        after = sum(1 for r in rows
                    if r["idx"] >= f and r["bs_early"] != BS_PASV)
        return (act[-1] if act else None), after

    last, after = leg(real)
    if last is None:
        return None
    clast, cafter = leg(sim)
    idle = f - last["idx"]
    stalled = (last["bs_early"] != BS_HALT and idle >= STALL_IDLE
               and after == 0)
    core_stalled = (clast is not None and cafter == 0
                    and clast["bs_early"] != BS_HALT
                    and (f - clast["idx"]) >= STALL_IDLE)
    return {"stalled": bool(stalled), "f": f, "last": last["idx"],
            "last_bs": last["bs_early"], "idle": idle, "after": after,
            "core_last": clast["idx"] if clast is not None else None,
            "core_after": cafter if clast is not None else None,
            "core_stalled": bool(core_stalled) if sim else None,
            # THE POSITIVE HALF: same park clock on both legs, to the clock.
            "core_match": (bool(stalled and core_stalled
                                and clast["idx"] == last["idx"])
                           if sim else None)}


# --------------------------------------------------------------------------- #
# AMENDMENT A-6 (prereg §17) -- WHY THIS CAPTURE DID NOT REACH THE TERMINATOR.
#
# IT IS A CENSUS AND NOT A DISCARD CLASS.  `fz2_w1.py bars` dispositions on
# A-4's four classes and on nothing here; this column exists so that a residue
# can be NAMED, which is the one thing 245 of the 269 undispositioned seeds of
# the 2026-08-09 re-capture could not be.  It is computed HERE, at capture
# time, while the rows are in hand -- A-4's own lesson, and the reason that
# amendment's `stalled` column exists.
#
# Every label below is either an EXISTING function's answer or the ABSENCE of a
# bus cycle.  There is no new predicate, no threshold that is not already
# registered (`STALL_IDLE`), and no per-opcode anything.
# --------------------------------------------------------------------------- #
SCORER_WINDOW = 4000        # `fuzz_classify.diff_rows`' own `limit`, in POSITIONS


def term_mechanism(real, sim, hold_rows):
    """The label, or None when the rows cannot be asked (no rows, no unique
    terminating-NMI run).  Applied in ONE fixed order:

      REACHED      the arch column is there as the scorer read it before A-6.
      WINDOW       D-1.  A COMPLETE dump is in the capture but lands past the
                   `SCORER_WINDOW`-POSITION comparison window, while
                   `term_clocks` budgets the terminator against `CAP_ROWS`
                   = 4,096 ABSOLUTE rows.  The two ends of one budget were in
                   different coordinate systems -- the same species of defect
                   A-3 found at the anchor, at the other end of the capture.
      FORGED_DONE  D-2.  A complete dump appears once a non-sentinel
                   `OUT 0xFC` stops being read as a done marker.  A raw image
                   is random bytes and contains such writes; `classify` says
                   so in its own comment and then `dump_words` trusted them.
      BUDGET       the register port WAS written at or after the terminating
                   NMI and no sentinel done marker followed: the capture ran
                   out mid-dump.  THIS, and only this, is the class the
                   `ENTRY_MAX` / `TERM_CLOCKS` budget moves.
      LONG_INSN    M-1.  Not one CODE fetch at or after the NMI, and the bus
                   still running.  The part is inside a SINGLE instruction
                   that outlives the capture -- a block transfer whose
                   iteration count came out of the same random bytes as the
                   opcode.  NMI recognition is an edge latch and the entry is
                   taken when that instruction retires, which is after the
                   last row of the capture.  No `TERM_CLOCKS` reaches it and
                   no capture-side repair can: the capture is 4,096 records
                   deep and one such instruction can run for hundreds of
                   thousands of clocks.
      STALLED      amendment A-4's fourth declared discard class, verbatim.
      HALT         no bus at or after the NMI and the last cycle was a HALT
                   announcement.  A-4's clause (1) excludes HALT on purpose
                   (plan D3's subject) and this keeps it visible.
      NEAR         no bus at or after the NMI, but the bus went quiet less
                   than `STALL_IDLE` clocks before it -- A-4's three withheld
                   seeds, whose stop cannot be told apart from the
                   terminator's own arrival.
      OTHER        none of the above.  Kept as a catch-all ON PURPOSE: a
                   census whose catch-all is engineered to be empty measures
                   its own taxonomy and nothing else.

    None is returned when the question cannot be asked of these rows -- no
    rows, no pin columns (a TB leg arms no terminator), or no unique
    terminating-NMI run -- and never a label, which would read as a measured
    answer.  `fz2_stall`'s `not evaluable` convention, applied here."""
    if not real or not hold_rows:
        return None
    if fc.arch_dump(real, SCORER_WINDOW) is not None:
        return "REACHED"
    n = len(real)
    if fc.arch_dump(real, n) is not None:
        return "WINDOW"
    if fc.arch_dump(real, n, sentinel_only=True) is not None:
        return "FORGED_DONE"
    st = stall_evidence(real, sim, hold_rows)
    if st is None:
        return None
    f = st["f"]
    post = [r for r in real if r["idx"] >= f]
    if any(r["bs_early"] == 2 and (r["ad_addr"] & 0xFFFF) == ti.OUT_PORT_REGS
           for r in post):
        return "BUDGET"
    if st["after"] == 0:
        if st["last_bs"] == BS_HALT:
            return "HALT"
        return "STALLED" if st["stalled"] else "NEAR"
    if not any(r["bs_early"] == 4 for r in post):
        return "LONG_INSN"
    return "OTHER"


def result_line(cfg, g, sha, v, di, gen_git, build_stale, ts, bus_cycles=None,
                arch=None):
    # task #38: the vector is banked IN FULL (`wvec_hex`, 2 chars per entry,
    # NWVEC entries) beside its spec and its sha256.  A vector that exists
    # only as a derivation is one nobody can check the rig's readback against,
    # and the whole point of the axis is that the rig applied THIS sequence.
    vec = wvec_of(cfg)
    return {
        "k": cfg["k"], "seed": f"{cfg['cid']}/{cfg['k']}", "cid": cfg["cid"],
        "tier": cfg["tier"], "cfg_hash": cfg["cfg_hash"],
        "wvec": cfg.get("wvec"), "no8080": True,
        "wvec_hex": wv.to_hex(vec) if vec else None,
        "wvec_sha256": wv.sha256_of(vec) if vec else None,
        "wvec_n": len(vec) if vec else 0,
        # task #38 bar B-5: the capture's own bus-cycle count, recorded PER
        # CAPTURE.  Past `wv.NWVEC` the three legs do three different things
        # (the board WRAPS, the model falls back to uniform, the TB reads out
        # of range), so a capture at or beyond it is outside the regime the
        # vector means anything in and must be quarantined rather than scored.
        "bus_cycles": bus_cycles,
        # fuzz-v2 ERRATUM E-1, THE THREE DECOMPOSITIONS, ON EVERY LINE.
        # `arch_ok` is the RESTATED bar -- a MAGIC-anchored 15-word dump on the
        # socket/real leg, i.e. the terminator was reached.  `escaped` is the
        # STRICT predicate the bar was moved off, RETAINED as a diagnostic
        # counter (row, physical offset) exactly as E-1 says.  `arch_restart`
        # is the seed the terminator entered twice, which is a DISCARD and not
        # a dump.  All three `None` when there are no rows.
        # THE COLUMNS THE PRE-REGISTRATION'S BARS ARE SCORED ON (§7 item 3).
        # `arch_words` is the socket leg's own 15-word dump and `arch_sim_*`
        # the fabric leg's, so C-2's non-vacuity ("each of the other 14 words
        # takes >= 2 distinct values") and the arch-exact decomposition can be
        # taken from the bank without re-reading a capture; `arch_match` is
        # the two compared.  `ps3_8080` and `wrote_term` are two of §3.4's
        # three declared discard classes (`arch_restart` is the third), each
        # detected independently and named before the capture.  `term` is
        # C-6's record: what the rig REPORTED (`fired`, `vec_used`) beside
        # what it was HANDED (`tvec`, `term_clocks`) and what the ROWS say
        # (`hold_rows`).  A bar whose column is absent reads NOT SCOREABLE,
        # never MET -- which is why they are defaulted to None and not to 0.
        **(arch or {"arch_ok": None, "arch_restart": None, "escaped": None,
                    "escaped_n": None, "arch_words": None,
                    "arch_sim_ok": None, "arch_sim_words": None,
                    "arch_match": None, "ps3_8080": None,
                    "ps3_8080_core": None,
                    "wrote_term": None, "wrote_term_at": None,
                    "stalled": None, "stalled_at": None,
                    "term": None}),
        "era": _ERA,
        "wild": g.get("wild"), "has_brkem": g.get("has_brkem", False),
        "brkem_pos": g.get("brkem_pos", []), "has_halt": g.get("has_halt", False),
        "has_tf": g.get("has_tf", False), "raw_mode": g.get("raw_mode"),
        "ivt_mode": g.get("ivt_mode"), "n_ins": g["n_ins"],
        "evt": cfg["evt"], "waits": cfg["waits"], "nmin": cfg["nmin"],
        "nmax_eff": cfg["nmax_eff"], "image_sha256": sha,
        "build_stale": build_stale, "gen_git": gen_git, "ts": ts,
        "verdict": v.verdict, "sub": v.sub, "first_bad": v.first_bad,
        "bad_rows": v.bad_rows, "flick": v.flick, "win": v.n,
        "func_mismatch": v.func_mismatch, "truncated": v.truncated,
        "done_real": v.done_real, "done_sim": v.done_sim, "done_idx": di,
        "alarms": v.alarms,
        "rule_hits": [{"rule": h.rule, "klass": h.klass, "covers": h.covers}
                      for h in v.rule_hits],
        "sig": v.sig, "sigv": v.sigv, "drift": v.drift,
    }


# ===========================================================================
# One-case evaluation (shared by sequential + parallel run and replay).
# ===========================================================================
_ENGINE = None            # per-process engine (Pool initializer / lazy)
_GEN_GIT = None


def _engine():
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = AcceptEngine.load()
    return _ENGINE


def _gen_git():
    global _GEN_GIT
    if _GEN_GIT is None:
        try:
            _GEN_GIT = subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                text=True).strip()
        except Exception:                               # noqa: BLE001
            _GEN_GIT = "unknown"
    return _GEN_GIT


def eval_case(cid, k, ov, tb_only, host, build_stale, keep_rows=False,
              core=None):
    """Derive -> build -> compose -> capture -> classify. Returns a dict with
    the result line, verdict/ctx (for escalation), done_idx, timings, coverage
    bits, and (on divergence, or keep_rows) the raw rows for the banker."""
    t = {}
    t0 = time.time()
    cfg = derive_case(cid, k, ov)
    t["derive"] = time.time() - t0
    t0 = time.time()
    g = build(cfg)
    t["build"] = time.time() - t0
    t0 = time.time()
    image, meta = compose_case(g, cfg)
    sha = hashlib.sha256(bytes(image)).hexdigest()
    t["compose"] = time.time() - t0

    t0 = time.time()
    run_error = None
    # None on a TB leg and a dict on a board leg: the Verilator TB has ONE
    # scheduler and no vector-read overlay, so it cannot arm a terminating NMI
    # and `term` must read absent rather than zero.
    term_rec = None
    if tb_only:
        try:
            real = capture_tb(image, meta, cfg, core=core)
            sim = copy.deepcopy(real)     # TB-vs-TB: plumbing + done-in-window
        except Exception as e:            # noqa: BLE001  (run_tb RuntimeError)
            real = sim = None
            run_error = f"run_error:tb:{str(e)[:120]}"
    else:
        term_rec = {}
        real, sim, run_error = capture_board(image, meta, cfg, host,
                                             term_out=term_rec)
    t["capture"] = time.time() - t0

    ctx = _ctx_for(cfg, g, tb_only)
    if run_error:
        ctx.run_error = run_error
    # raw seeds carry no gen-time lea_mod3 provenance; recover an executed illegal
    # LEA mod=11 from the capture so the (raw-aware) lea_mod3 rule can cover it.
    if cfg["tier"] == "raw" and real and not ctx.lea_mod3_pos:
        ctx.lea_mod3_pos = _raw_lea_mod3_pos(bytes(image), real)
    t0 = time.time()
    v = classify(real, sim, ctx, engine=_engine())
    t["classify"] = time.time() - t0

    di = fc._done_idx(real) if real else None
    # B-5, measured on the SOCKET leg's own rows -- no engine in the loop.
    bus_cycles = None
    if real:
        try:
            bus_cycles = wv.bus_cycle_bound(real)
        except Exception:                               # noqa: BLE001
            bus_cycles = None
    arch = None
    if real:
        esc = fc.escaped_code_region(real, v.n)
        # AMENDMENT A-6 (prereg §17), findings D-1 and D-2.  THE ARCH COLUMN IS
        # READ OVER THE WHOLE CAPTURE, and a done marker is one that carries
        # the sentinel.  `wrote_term` two lines down has been read this way
        # since T10 and its comment already gives the reason in full: `v.n` is
        # the COMPARISON window, shrunk to the done marker + 8 and capped at
        # `fuzz_classify.diff_rows`' `limit` of 4,000 POSITIONS, while
        # `term_clocks` budgets the terminator against `CAP_ROWS` = 4,096
        # ABSOLUTE rows.  A capture is 4,063 rows starting at absolute record
        # 33, so the two ends of one budget were 63 rows apart -- A-3's anchor
        # defect again, at the other end of the capture -- and a complete,
        # correct dump landing there read as "the terminator was never
        # reached".  D-2 is the same sentence about the OTHER axis: a raw
        # image is 64 K of random bytes, `classify` says in its own comment
        # that it "legitimately forges done markers with random data", and
        # `dump_words` then took the first such write as the boundary and
        # truncated the word list ahead of the terminator's real dump.
        #
        # NOTHING ELSE MOVES.  `classify` still compares the two legs over
        # `v.n` and every verdict, row-diff and signature is untouched: this
        # is the ARCH COLUMN's own window, not the comparison's.
        aw = fc.arch_dump(real, len(real), sentinel_only=True)
        asw = fc.arch_dump(sim, len(sim), sentinel_only=True) if sim else None
        wt = _wrote_term(real, len(real))
        # A-4: computed HERE, at capture time, while the rows are in hand, and
        # banked on the result line.  The 2026-08-09 re-capture had to be
        # classified out of retained rows, which exist for only 67 of its 312
        # undispositioned seeds; a column on the line needs no rows at all.
        holds = _pin_runs(real, len(real))
        st = stall_evidence(real, sim, holds)
        arch = {"arch_ok": aw is not None,
                "arch_restart": fc.dump_restarted(real, len(real),
                                                  sentinel_only=True),
                "escaped": list(esc) if esc else None,
                "escaped_n": _escape_count(real, v.n),
                # the arch column, BOTH LEGS, banked as words and not as a
                # verdict: C-2's non-vacuity test needs the values themselves
                "arch_words": aw,
                "arch_sim_ok": asw is not None,
                "arch_sim_words": asw,
                "arch_match": (aw is not None and aw == asw),
                # the two capture-time discard classes that are not
                # `arch_restart`, each detected on its own predicate.
                # AMENDMENT A-2: the SOCKET leg alone.  §3.4 registered this
                # "on either leg"; finding O-1 measured that the core leg's
                # `ps` at a CODE T1 is the ADDRESS nibble, so the OR fired on
                # 382 of 382 archived board pairs and made C-1's
                # UNDISPOSITIONED 0 by arithmetic.  A T2 sample does not repair
                # it (103/382 still fire, and 0 of 87 known 8080 entries are
                # detected); `_ps3_8080`'s docstring carries the measurement
                # and the RTL reason.  A TB leg is asked nothing at all and the
                # column reads None (NOT SCOREABLE), never a False that would
                # look like a measured absence.
                "ps3_8080": (None if tb_only else bool(_ps3_8080(real, v.n))),
                # RETIRED, NOT DROPPED (A-2).  The core leg's answer is still
                # COMPUTED and still REPORTED on every line -- it gates
                # nothing, it dispositions nothing, and it is here so that the
                # retirement stays visible in the bank rather than becoming an
                # absence nobody can audit.  (A-1's `escaped` precedent.)
                "ps3_8080_core": (None if tb_only else
                                  bool(_ps3_8080(sim, v.n))),
                # OVER THE WHOLE CAPTURE, not the compared window.  `v.n` is
                # shrunk to the done marker + 8, and everything below is
                # evidence about the RIG rather than about the comparison:
                # the terminating NMI fires at `term_clocks` (1,901 .. 3,634),
                # which on a seed that terminated normally is far outside that
                # window.  Scoring the pin off `v.n` would report "the
                # terminator never asserted" for exactly the seeds where it
                # did not need to.
                "wrote_term": wt is not None,
                "wrote_term_at": wt,
                # AMENDMENT A-4's fourth declared discard class.  `None` when
                # the rows cannot answer (a TB leg arms no terminator), never
                # a False that would look like a measured absence.
                "stalled": (None if st is None else st["stalled"]),
                # AMENDMENT A-6's CENSUS column.  It dispositions NOTHING --
                # `fz2_w1.py bars` reads A-4's four classes and does not import
                # it -- and it exists so that an UNDISPOSITIONED seed can be
                # NAMED without keeping its rows.  245 of the 269 seeds the
                # 2026-08-09 re-capture left undispositioned carried no rows
                # and could not be asked at all; this is the answer to that,
                # and it costs one string per line.
                "mech": term_mechanism(real, sim, holds),
                "stalled_at": st,
                # C-6: what the rig reported, what it was handed, what the
                # rows say.  `None` on a TB leg, which arms no terminator.
                "term": {
                    "fired": (term_rec or {}).get("fired"),
                    "vec_used": (term_rec or {}).get("vec_used"),
                    "readback_ok": (term_rec or {}).get("readback_ok"),
                    "tvec": list(TERM_TVEC),
                    "vecsub": TERM_VECSUB,
                    "term_clocks": term_clocks(weff_of(cfg)),
                    "term_hold": TERM_HOLD,
                    "evt_hold": (cfg["evt"] or {}).get("hold"),
                    "evt_pin": (cfg["evt"] or {}).get("pin"),
                    "hold_rows": holds,
                    "vec_rows": _vec_rows(real, len(real)),
                } if term_rec is not None else None}
    line = result_line(cfg, g, sha, v, di, _gen_git(), build_stale,
                        time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        bus_cycles=bus_cycles, arch=arch)
    # raw-tier open-bus escape metric: how much of the run left the 64K image
    # into open-bus feedthrough space (task #29 P7; drives the rollup escape
    # fraction and the open_bus_escape accept rule).
    if cfg["tier"] == "raw" and real:
        esc, n_out, _ = open_bus_escape_metrics(real, v.n)
        line["ob_escape"] = {"feed": len(esc), "out": n_out,
                             "frac": round(len(esc) / n_out, 3) if n_out else 0.0}
    qfill = fuzz_cov.qfill_at_dispatch(real) if real else []
    divergent = v.verdict != fc.SUCCESS
    # SUCCESS-ballast candidate: a cheap deterministic ~2% sample keeps its rows
    # so the driver can gzip a stratified SUCCESS sample (the fab-vs-TB
    # float-floor alarm at scale); the main loop enforces the per-stratum quota.
    ballast_cand = (not divergent and real is not None and k % 50 == 0)
    rows = (real, sim) if (divergent or keep_rows or ballast_cand) and real else None
    return {"k": k, "cfg_hash": cfg["cfg_hash"], "tier": cfg["tier"],
            "line": line, "verdict": v, "ctx": ctx, "di": di,
            "timeout": run_error is not None and tb_only,
            "timings": t, "qfill": qfill, "forms": g["forms"], "ins": g["ins"],
            "weff": _weff(cfg), "rows": rows, "ballast_cand": ballast_cand}


# ===========================================================================
# run.
# ===========================================================================
def _pool_init(cid, ov, tb_only, host, build_stale, keep_every=0):
    global _EVAL_ARGS
    _EVAL_ARGS = (cid, ov, tb_only, host, build_stale, keep_every)
    _engine()


def _pool_eval(k):
    cid, ov, tb_only, host, build_stale, keep_every = _EVAL_ARGS
    # the SAME arithmetic the sequential loop uses; a `--keep-rows-every` that
    # worked at `--jobs 1` and was silently dropped at `--jobs 8` is the
    # accepted-and-ignored trap wearing a parallelism hat
    return eval_case(cid, k, ov, tb_only, host, build_stale,
                     keep_rows=(keep_every > 0 and k % keep_every == 0))


def _append_fsync(fh, obj):
    fh.write(json.dumps(obj) + "\n")
    fh.flush()
    os.fsync(fh.fileno())


def _resume_k(results_path):
    if not results_path.exists():
        return 0
    last = -1
    with open(results_path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    last = max(last, json.loads(line)["k"])
                except Exception:                       # noqa: BLE001
                    pass
    return last + 1


def cmd_run(a):
    cdir = CAMPAIGNS / a.cid
    manifest_path = cdir / "manifest.json"
    build_stale = False
    if not a.tb_only:
        if not manifest_path.exists():
            print(f"run: no manifest for {a.cid} - run `new {a.cid}` first")
            return 2
        manifest = json.loads(manifest_path.read_text())
        cur = _last_flash_entry()
        pin = manifest.get("flash_pin", {})
        if not cur or cur.get("sha256") != pin.get("sha256"):
            if not a.allow_stale:
                print("run: flash_log sof-sha does not match the manifest pin; "
                      "new RTL => new campaign, or pass --allow-stale")
                return 2
            build_stale = True
        # task #38 B-2: stamp the era onto every line this session writes.
        set_era(era_of(manifest))
    cdir.mkdir(parents=True, exist_ok=True)
    (cdir / "captures").mkdir(exist_ok=True)
    results_path = cdir / "results.jsonl"

    ov = {}
    if a.force_tier:
        ov["force_tier"] = a.force_tier
    if a.contained:
        ov["force_contained"] = True
    if a.w0:
        ov["w0"] = True
    if getattr(a, "force_fixed", None) is not None:
        ov["force_fixed"] = a.force_fixed
    if a.no_evt:
        ov["no_evt"] = True
    if a.strict:
        ov["strict"] = True
    if a.no_brkem:
        ov["no_brkem"] = True
    if a.mainline:
        ov["mainline"] = True
    if a.force_evt:
        ov["force_evt"] = True
    if a.force_wrand:
        ov["force_wrand"] = [int(x) for x in a.force_wrand.split(",")]
    if getattr(a, "wvec_shapes", None):
        shapes = [s for s in a.wvec_shapes.split(",") if s]
        bad = [s for s in shapes if s not in wv.SHAPES]
        if bad:
            print(f"run: unknown wvec shape(s) {bad}; known: {list(wv.SHAPES)}")
            return 2
        ov["wvec_shapes"] = shapes

    start = a.start if a.start is not None else _resume_k(results_path)
    end = start + a.session_seeds
    print(f"run {a.cid}: seeds [{start},{end}) tb_only={a.tb_only} "
          f"jobs={a.jobs} ov={ov}", flush=True)

    # THE KEEP-ROWS RULE (fuzz-v2 prereg §7 item 2).  `eval_case` has always
    # taken `keep_rows`; `cmd_run` never set it, so the only SUCCESS rows this
    # driver ever banked came through the ballast path -- a ~2 % sample capped
    # at 100 captures / ~17 per stratum.  A frozen census bank cannot be a
    # quota: its rates are population rates precisely because nothing about
    # the outcome, and nothing about how many seeds got there first, decides
    # membership.  `--keep-rows-every N` keeps every k with k % N == 0,
    # OUTSIDE the ballast quota entirely.  0 = off, which is every historical
    # invocation unchanged.
    keep_every = int(getattr(a, "keep_rows_every", 0) or 0)

    def keep_rows_for(k):
        return keep_every > 0 and k % keep_every == 0

    if keep_every:
        print(f"  keep-rows: every k % {keep_every} == 0, un-quota'd "
              f"(the frozen bank rule)", flush=True)

    engine = _engine()
    esc_cfg = dict(engine.escalation)
    if a.survey:
        # census mode: survey ALL w0 TIMING and (non-provenance) FUNCTIONAL
        # divergences instead of stopping on the first - for the recovery /
        # census pilots (BRKEM, raw) where soup breadth legitimately produces
        # w0 functionals. The HARD capture-integrity stops stay armed: any
        # provenance alarm and the >=5-consecutive-quarantine circuit breaker
        # still abort. A w0-mainline BUG-HUNT omits --survey to keep the
        # functional stop.
        esc_cfg["stop_new_w0_timing_sig"] = False
        esc_cfg["stop_w0_functional"] = False
        esc_cfg["max_new_sigs"] = 10 ** 9
    esc = EscalationPolicy(esc_cfg)
    cov = fuzz_cov.Coverage()
    consec_q = real_div = done_ok = done_win = timeouts = 0
    stage_t = {s: [] for s in ("derive", "build", "compose", "capture", "classify")}
    done_idxs = []
    t_start = time.time()
    stopped = None
    ballast = Counter()          # SUCCESS-ballast captured per (tier, waits-class)
    ballast_cap = 100 // 6 + 1   # ~17 per stratum, 100 total, stratified

    def handle(res):
        nonlocal consec_q, real_div, done_ok, done_win, timeouts, stopped
        v = res["verdict"]
        ctx = res["ctx"]
        _append_fsync(rf, res["line"])
        cov.add_program(res["forms"], res["ins"], waits=res["weff"])
        for d in res["qfill"]:
            cov.qfill[f"q{min(d, 6)}"] += 1
        if res["di"] is not None:
            done_ok += 1
            done_idxs.append(res["di"])
            if res["di"] < TB_ROWS - 8:
                done_win += 1
        if res["timeout"]:
            timeouts += 1
        # gzip divergent captures always; the frozen keep-rows bank always,
        # with NO quota; SUCCESS ballast up to the per-stratum quota
        # (stratified tier x waits-class) for the fab-vs-TB float-floor alarm
        want_cap = res["rows"] is not None and (v.verdict != fc.SUCCESS
                                                or keep_rows_for(res["k"]))
        if not want_cap and res.get("ballast_cand") and res["rows"] is not None:
            strat = (res["tier"], _waits_class_line(res["line"]))
            if sum(ballast.values()) < 100 and ballast[strat] < ballast_cap:
                ballast[strat] += 1
                want_cap = True
        if want_cap:
            gz = cdir / "captures" / f"{res['tier']}_{res['k']}_{res['cfg_hash']}.json.gz"
            with gzip.open(gz, "wt") as g:
                json.dump({"real": res["rows"][0], "sim": res["rows"][1],
                           "line": res["line"]}, g)
        for s, dt in res["timings"].items():
            stage_t[s].append(dt)
        if v.verdict == fc.QUARANTINE:
            consec_q += 1
        else:
            consec_q = 0
        if v.verdict in (fc.FUNCTIONAL, fc.TIMING):
            real_div += 1
        acts = esc.consult(v, ctx)
        for act, why in acts:
            if act == "STOP":
                stopped = f"escalation:{why} @k={res['k']}"
        if consec_q >= 5:
            stopped = (f"circuit_breaker:{consec_q} consecutive quarantines "
                       f"@k={res['k']} (wedge house rule)")
        if a.stop_after and real_div >= a.stop_after:
            stopped = f"stop_after:{real_div} real divergences @k={res['k']}"

    with open(results_path, "a") as rf:
        ks = range(start, end)
        if a.tb_only and a.jobs > 1:
            with Pool(a.jobs, initializer=_pool_init,
                      initargs=(a.cid, ov, True, a.host, build_stale,
                                keep_every)) as pool:
                for i, res in enumerate(pool.imap(_pool_eval, ks, chunksize=4)):
                    handle(res)
                    _progress(res, i, start, t_start, cov, cdir)
                    if stopped:
                        pool.terminate()
                        break
        else:
            for i, k in enumerate(ks):
                try:
                    res = eval_case(a.cid, k, ov, a.tb_only, a.host,
                                    build_stale,
                                    keep_rows=keep_rows_for(k))
                except RigMismatch as e:
                    # a rig-integrity FINDING, not a transport fault: STOP the
                    # session with the finding in the heartbeat, rather than
                    # quarantining it into a count nobody reads.
                    stopped = f"rig_mismatch @k={k}: {e}"
                    print(f"\n*** {stopped} ***", flush=True)
                    break
                handle(res)
                _progress(res, i, start, t_start, cov, cdir)
                if stopped:
                    break

    cov.save(cdir / "coverage.json")
    if not a.tb_only:
        # board etiquette: leave the socketed chip selected (use_core=0)
        try:
            g0 = build(derive_case(a.cid, start, ov))
            img0, _ = check_seq.compose(g0)
            check_seq.run_chip(img0, a.host, use_core=False)
            print("  board left use_core=0")
        except Exception as e:                          # noqa: BLE001
            print(f"  (post-session use_core=0 note: {e})")
    processed = (res["k"] - start + 1) if 'res' in dir() else 0
    _heartbeat(cdir, res["k"] if 'res' in dir() else start, processed - 1,
               start, t_start, status=(f"stopped:{stopped}" if stopped
                                        else "done"))
    print(f"\n=== run {a.cid}: {processed} seeds in {time.time()-t_start:.1f}s"
          f"{(' STOPPED ' + stopped) if stopped else ''}")
    if a.measure:
        for s in stage_t:
            xs = sorted(stage_t[s][:a.measure])
            if xs:
                print(f"  {s:<9} p50={_pct(xs,.5)*1000:.1f}ms "
                      f"p95={_pct(xs,.95)*1000:.1f}ms")
    if a.tb_only:
        tot = processed
        print(f"  done-in-window: {done_win}/{tot} = "
              f"{100*done_win/max(1,tot):.1f}%  timeouts: {timeouts}/{tot} = "
              f"{100*timeouts/max(1,tot):.2f}%")
        if done_idxs:
            di = sorted(done_idxs)
            print(f"  done_idx: min={di[0]} median={statistics.median(di):.0f} "
                  f"p95={_pct(di,.95)} max={di[-1]}")
        if a.done_dist:
            dist = {"cid": a.cid, "n": tot, "overrides": ov,
                    "nmax_scale_c": NMAX_SCALE_C, "tb_rows": TB_ROWS,
                    "done_ok": done_ok, "done_in_window": done_win,
                    "timeouts": timeouts, "done_idx": done_idxs}
            Path(a.done_dist).write_text(json.dumps(dist))
            print(f"  wrote done_idx distribution -> {a.done_dist}")
    _verdict_rollup(results_path)
    return 1 if stopped and ("circuit_breaker" in stopped
                             or "rig_mismatch" in stopped) else 0


def _heartbeat(cdir, k, i, start, t_start, status="alive"):
    """Liveness beacon: a small file rewritten frequently so a watcher can
    detect a stall/death by MTIME (never by process-wait - the self-matching
    pgrep watcher lesson, task #29 P7). status='alive' during the run, or the
    terminal reason ('stopped:...'/'done') at exit."""
    try:
        (cdir / "heartbeat.json").write_text(json.dumps({
            "k": k, "start": start, "done_this_session": (i + 1),
            "rate": round((i + 1) / max(1e-6, time.time() - t_start), 2),
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "status": status}))
    except Exception:                                       # noqa: BLE001
        pass


def _progress(res, i, start, t_start, cov, cdir):
    if (i + 1) % 25 == 0:
        _heartbeat(cdir, res["k"], i, start, t_start)
    if (i + 1) % 500 == 0:
        cov.save(cdir / "coverage.json")
        rate = (i + 1) / (time.time() - t_start)
        print(f"  k={res['k']} ({rate:.1f}/s) last={res['verdict'].verdict}"
              f"/{res['verdict'].sub}", flush=True)


def _pct(xs, p):
    if not xs:
        return 0
    s = sorted(xs)
    return s[min(len(s) - 1, int(p * len(s)))]


# ===========================================================================
# new / status / show / replay.
# ===========================================================================
def _last_flash_entry():
    if not FLASH_LOG.exists():
        return None
    last = None
    for line in FLASH_LOG.read_text().splitlines():
        line = line.strip()
        if line:
            try:
                last = json.loads(line)
            except Exception:                           # noqa: BLE001
                pass
    return last


def cmd_new(a):
    flash = _last_flash_entry()
    if not flash or flash.get("verify") != "OK":
        print("new: no valid VERIFY=OK flash_log entry to pin - flash via "
              "sw/safe_flash.sh (or backfill an entry) first")
        return 2
    cdir = CAMPAIGNS / a.cid
    cdir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "cid": a.cid,
        "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "gen_git": _gen_git(),
        "flash_pin": flash,
        "axes": {"raw_frac": 0.20, "nmin": NMIN, "nmax": NMAX,
                 "nmax_scale_c": NMAX_SCALE_C, "tb_rows": TB_ROWS,
                 "event_frac": 0.25, "wrand_frac": 0.50},
        "knobs": vars(SoupKnobs()),
        "rules_version": _engine().meta.get("version"),
        "sigv": _engine().meta.get("sigv"),
    }
    (cdir / "manifest.json").write_text(json.dumps(manifest, indent=1))
    print(f"new: wrote {cdir/'manifest.json'} (pin sha256 "
          f"{flash['sha256'][:12]}..., gen_git {manifest['gen_git']})")
    return 0


def _verdict_rollup(results_path):
    from collections import Counter
    if not results_path.exists():
        print("  (no results yet)")
        return
    verd = Counter()
    rules = Counter()
    sigs = set()
    n = 0
    with open(results_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            n += 1
            verd[r["verdict"]] += 1
            for h in r.get("rule_hits", []):
                rules[h["klass"]] += 1
            if r.get("sig"):
                sigs.add(r["sig"])
    print(f"  verdicts ({n}): {dict(verd)}")
    if rules:
        print(f"  rule hits: {dict(rules)}")
    print(f"  distinct signatures: {len(sigs)}")


def cmd_status(a):
    results_path = CAMPAIGNS / a.cid / "results.jsonl"
    print(f"status {a.cid}: next k = {_resume_k(results_path)}")
    _verdict_rollup(results_path)
    eng = _engine()
    zero = eng.zero_hit_rules()
    if zero:
        print(f"  (zero-hit rules this load: {zero})")
    return 0


def cmd_show(a):
    ov = {}
    if a.contained:
        ov["force_contained"] = True
    if a.force_tier:
        ov["force_tier"] = a.force_tier
    if getattr(a, "wvec_shapes", None):
        ov["wvec_shapes"] = [s for s in a.wvec_shapes.split(",") if s]
    cfg = derive_case(a.cid, a.k, ov)
    g = build(cfg)
    image, meta = compose_case(g, cfg)
    sha = hashlib.sha256(bytes(image)).hexdigest()
    vec = wvec_of(cfg)
    print(json.dumps({"cfg": {kk: cfg[kk] for kk in
                              ("tier", "evt", "waits", "wild", "nmin",
                               "nmax_eff", "cfg_hash", "wvec")},
                      "wvec_sha256": wv.sha256_of(vec) if vec else None,
                      "wvec_head": vec[:32] if vec else None,
                      "bad_0f_pairs": bad_0f_pairs(image),
                      "n_ins": g["n_ins"], "wild": g.get("wild"),
                      "has_brkem": g.get("has_brkem"), "brkem_pos": g.get("brkem_pos"),
                      "has_halt": g.get("has_halt"), "raw_mode": g.get("raw_mode"),
                      "image_sha256": sha, "anchor": meta["anchor_linear"]},
                     indent=1))
    return 0


# ===========================================================================
# measure -- fuzz-v2 ERRATUM E-1.  A MEASUREMENT TOOL, NOT A GATE.
# ===========================================================================
def _measure_one(args):
    cid, k, ov, core = args
    res = eval_case(cid, k, ov, tb_only=True, host=None, build_stale=False,
                    core=core)
    ln = res["line"]
    out = {kk: ln.get(kk) for kk in
           ("k", "tier", "raw_mode", "has_tf", "has_halt", "evt", "wild",
            "arch_ok", "arch_restart", "escaped", "escaped_n", "done_idx",
            "verdict")}
    out["has_undoc"] = "undoc" in (res["forms"] or [])
    # THE ENGINE NAMES ITSELF, per row.  A `--core` flag that is accepted and
    # ignored is the failure this whole erratum is about, and a header line
    # printed by the parent process would not have caught it: the rows come
    # from worker processes, and it is the WORKER that runs the binary.
    out["core"], out["tb_bin"], out["tb_receipt"] = tb_engine(core)
    return out


def cmd_measure(a):
    """ERRATUM E-1 -- both numbers, re-measured on THE REAL GENERATOR.

    E-1 restated the containment bar from (a) THE STRICT ESCAPE PREDICATE --
    any CODE fetch outside the code region -- to (b) THE OUTCOME, a
    MAGIC-anchored 15-word dump, after measuring 75/500 escapes on 500
    RANDOM-BYTE images of which 62 still dumped.  It explicitly did NOT
    register the restatement, because the population that motivated it was not
    the population the generator produces.  This command produces that
    population and reports BOTH numbers with no threshold applied.

    IT IS NOT A GATE and it consults NO EscalationPolicy: a provenance alarm
    is a hard STOP for a capture campaign, and stopping on the first escape is
    exactly what makes the escape RATE unmeasurable.  Nothing here decides
    anything -- the numbers go to the reviewer.

    THE ENGINE IS NAMED, NOT ASSUMED.  E-1's first measurement went through
    `check_seq.CORE`, which is pinned to the ARCHIVED fsm core
    (`standing_gates.md` §C / §F-4), and nothing in the output said so, so the
    numbers could not be quoted as ucore figures.  `--core` now selects the
    engine explicitly and EVERY ROW carries the core, the binary path and its
    receipt id, derived by `tb_engine()` inside the worker that ran it."""
    ov = {"force_tier": a.force_tier} if a.force_tier else {}
    ks = list(range(a.start, a.start + a.n))
    jobs = max(1, a.jobs)
    core, binp, rcpt = tb_engine(a.core)
    print(f"measure {a.cid}: {len(ks)} seeds via the Verilator TB "
          f"(core={core}, bin={binp}, receipt={rcpt}), jobs={jobs}, ov={ov}")
    t0 = time.time()
    rows = []
    with Pool(jobs, initializer=_engine) as pool:
        for i, r in enumerate(pool.imap_unordered(
                _measure_one, [(a.cid, k, ov, a.core) for k in ks],
                chunksize=4)):
            rows.append(r)
            if a.report_every and (i + 1) % a.report_every == 0:
                print(f"  {i+1}/{len(ks)} ({(i+1)/(time.time()-t0):.1f}/s)",
                      flush=True)

    def rep(name, sel):
        s = [r for r in rows if sel(r)]
        if not s:
            print(f"  {name:<28} n=0")
            return
        esc = [r for r in s if (r["escaped_n"] or 0) > 0]
        ok = [r for r in s if r["arch_ok"]]
        cnt = sorted(r["escaped_n"] for r in esc)
        med = statistics.median(cnt) if cnt else 0
        both = [r for r in esc if r["arch_ok"]]
        print(f"  {name:<28} n={len(s):<6} "
              f"(a) escaped {len(esc):<5} = {100*len(esc)/len(s):5.1f}% "
              f"(median {med:.0f} fetches, max {cnt[-1] if cnt else 0})   "
              f"(b) terminator reached {len(ok):<6} = "
              f"{100*len(ok)/len(s):5.1f}%   escaped-AND-dumped "
              f"{len(both)}/{len(esc) or 1}")

    # THE ROWS' OWN ACCOUNT of what ran, not the header's: if any worker
    # disagreed with the parent, the population is mixed and unquotable.
    seen = sorted({(r["core"], r["tb_bin"], r["tb_receipt"]) for r in rows})
    assert len(seen) == 1 and seen[0] == (core, binp, rcpt), \
        f"engine disagreement across workers: header={(core, binp, rcpt)} " \
        f"rows={seen}"
    print(f"\n=== E-1 on the T2 generator: {len(rows)} seeds in "
          f"{time.time()-t0:.1f}s   (cid={a.cid}, k in [{a.start},"
          f"{a.start + a.n}))")
    print(f"    ENGINE: core={seen[0][0]}  bin={seen[0][1]}\n"
          f"            receipt={seen[0][2]}  (all {len(rows)} rows agree)")
    rep("ALL", lambda r: True)
    rep("soup", lambda r: r["tier"] == "soup")
    # the three soup classes that CANNOT terminate offline, separated out so
    # the containment number is readable.  None of them is a containment
    # failure: a TF storm and an unwoken HALT are what plan D3's terminating
    # NMI exists for (Phase 2, not yet built), and `undoc` is the 0xF1 EU
    # wedge measured below.
    rep("  soup, clean (no TF/HALT/undoc)", lambda r: r["tier"] == "soup"
        and not r["has_tf"] and not r["has_halt"] and not r["has_undoc"])
    rep("  soup, TF set", lambda r: r["tier"] == "soup" and r["has_tf"])
    rep("  soup, HALT/POLL", lambda r: r["tier"] == "soup" and r["has_halt"])
    rep("  soup, undoc opcode", lambda r: r["tier"] == "soup"
        and r["has_undoc"])
    rep("  soup, wild", lambda r: r["tier"] == "soup" and r["wild"])
    rep("raw", lambda r: r["tier"] == "raw")
    rep("  raw, payload mode", lambda r: r["raw_mode"] == "payload")
    rep("  raw, whole-image mode", lambda r: r["raw_mode"] == "whole")
    nrs = sum(1 for r in rows if r["arch_restart"])
    print(f"  dumps the terminator entered TWICE (discard class): {nrs}")
    if a.out:
        Path(a.out).write_text(json.dumps(
            {"cid": a.cid, "start": a.start, "n": a.n, "core": core,
             "tb_bin": binp, "tb_receipt": rcpt,
             "gen_git": _gen_git(), "rows": rows}))
        print(f"  wrote per-seed rows -> {a.out}")
    return 0


def _replay_one(args):
    cid, k, ov = args
    res = eval_case(cid, k, ov, tb_only=True, host=None, build_stale=False)
    v = res["verdict"]
    return (k, v.verdict, v.sub, res["di"])


def cmd_replay(a):
    ov = {"force_contained": True} if a.contained else {}
    if a.force_tier:
        ov["force_tier"] = a.force_tier
    ks = list(range(a.start, a.start + a.n))
    jobs = min(8, max(1, (os.cpu_count() or 2) // 2), a.jobs or 8)
    print(f"replay {a.cid}: {len(ks)} cases via TB, jobs={jobs}")
    with Pool(jobs, initializer=_engine) as pool:
        for k, verdict, sub, di in pool.imap(
                _replay_one, [(a.cid, k, ov) for k in ks], chunksize=4):
            print(f"  k={k}: {verdict}/{sub} done_idx={di}")
    return 0


# ===========================================================================
# lint (Phase 1 gate, retained).
# ===========================================================================
def _lint_wvec(cid, n, ov):
    """task #38 -- the PER-ACCESS WAIT VECTOR axis, generation only.

    Six checks, each of which is a place a defect of this axis would be
    SILENT if nobody looked:

      1. every vector is exactly NWVEC entries and every entry is in [0,31]
         (`wvec_shapes.lint`, run first -- properties (2)(3)(4));
      2. the TB and model FILE encodings round-trip to the same list, and are
         different text whenever a value is >= 10 (property (1));
      3. two configs differing ONLY in the vector spec get DIFFERENT
         `cfg_hash`es -- the new axis is IN the hash;
      4. the axis OFF regenerates the image byte for byte, so nothing banked
         before task #38 drifts;
      5. THE 0F RULE leaves ZERO forbidden `0F xx` pairs in the composed
         image's code region, on BOTH tiers, measured on the artifact;
      6. the axis never makes the image a function of the wait vector: two
         seeds identical except for the vector produce the SAME image if and
         only if their `nmax_eff` agrees, and `nmax_eff` is a stated function
         of the vector's mean (`_wvec_weff`), never of anything else."""
    import tempfile
    hits = 0
    errs = wv.lint(max(20, min(n, 200)), quiet=True)
    for e in errs[:10]:
        hits += 1
        print(f"  WVEC HIT (shapes): {e}")
    t0 = time.time()
    off = dict(ov)
    off.pop("wvec_shapes", None)
    with tempfile.TemporaryDirectory() as td:
        for k in range(n):
            for tier in ("soup", "raw"):
                base = dict(off, force_tier=tier)
                cfg0 = derive_case(cid, k, base)
                img0, _ = compose_case(build(cfg0), cfg0)
                # (4) the axis OFF is byte-identical to a plain compose PLUS
                # THE 0F RULE, and nothing else.  It used to compare against
                # `check_seq.compose` alone; T3 made the 0F scrub
                # UNCONDITIONAL inside `compose_case`, so that form now fires
                # on every image the rule touches -- it would be asserting the
                # scrub never fires.  What the check is FOR is that
                # `compose_case` adds exactly one thing to `compose`, and that
                # the wait-vector axis is not that thing.
                g0 = build(cfg0)
                if bytes(img0) != scrub_0f_image(check_seq.compose(g0)[0])[0]:
                    hits += 1
                    print(f"  WVEC HIT: {tier}/{k} axis-off image moved")
                # (3)(6) with the axis ON
                cfgs = []
                for shape in wv.SHAPES:
                    c = derive_case(cid, k, dict(base, wvec_shapes=[shape]))
                    if not c["wvec"] or c["wvec"]["shape"] != shape:
                        hits += 1
                        print(f"  WVEC HIT: {tier}/{k}/{shape} spec not set")
                        continue
                    cfgs.append(c)
                    v = wvec_of(c)
                    if len(v) != wv.NWVEC or not all(0 <= x <= 31 for x in v):
                        hits += 1
                        print(f"  WVEC HIT: {tier}/{k}/{shape} vector invalid")
                    if k < 3:
                        for e in wv.check_encodings(v, td):
                            hits += 1
                            print(f"  WVEC HIT (enc): {tier}/{k}/{shape} {e}")
                    # (5) BRKEM-free by construction, on the ARTIFACT
                    img, _m = compose_case(build(c), c)
                    npair = bad_0f_pairs(img)
                    if npair:
                        hits += 1
                        print(f"  WVEC HIT: {tier}/{k}/{shape} {npair} "
                              f"forbidden 0F pairs survive the scrub")
                hashes = {c["cfg_hash"] for c in cfgs}
                if len(hashes) != len(cfgs):
                    hits += 1
                    print(f"  WVEC HIT: {tier}/{k} cfg_hash collides across "
                          f"{len(cfgs)} distinct vector specs")
                if cfgs and cfg0["cfg_hash"] in hashes:
                    hits += 1
                    print(f"  WVEC HIT: {tier}/{k} axis-on hash == axis-off hash")
    print(f"wvec: {n} seeds x 2 tiers x {len(wv.SHAPES)} shapes in "
          f"{time.time()-t0:.1f}s | hits={hits}")
    return hits


# ===========================================================================
# fuzz-v2 T2 lint legs: the bias helper (D1) and the handler pool (D8).
# ===========================================================================
from gen_soup import ANCHOR, SEG_NAMES                     # noqa: E402

# the (segment register, offset register) pairs whose product is a DESIGNED
# physical address, and the `phys` key that names the design.
SEG_OFF_PAIRS = (("PS", "PC"), ("SS", "SP"), ("DS0", "IX"), ("DS1", "IY"))


def _seg_off_hits(g, tag):
    """The D1 identity, on ONE g-dict.  -> list of failure strings."""
    r, ph = g["regs"], g.get("phys", {})
    out = []
    for seg, off in SEG_OFF_PAIRS:
        want = ph.get(off)
        if want is None:                      # raw IX/IY are free offsets
            continue
        got = ((r[seg] << 4) + r[off]) & 0xFFFF
        if got != want:
            out.append(f"{tag} ({seg},{off}) -> {got:04x}, designed {want:04x}")
    lows = {r[s] & 0xFFF for s in SEG_NAMES}
    if len(lows) != 1:
        out.append(f"{tag} segment registers disagree in the low 12 bits: "
                   f"{sorted(hex(x) for x in lows)}")
    return out


def _ivt_from_image(img):
    """[(vector, segment, offset, physical offset)] for all 256 composed
    vectors, read back off the ARTIFACT."""
    out = []
    for v in range(256):
        o = img[4 * v] | (img[4 * v + 1] << 8)
        s = img[4 * v + 2] | (img[4 * v + 3] << 8)
        out.append((v, s, o, ((s << 4) + o) & 0xFFFF))
    return out


def _lint_bias(cid, n, ov=None):
    """fuzz-v2 D1 -- SEGMENT RANDOMIZATION BY DERIVED OFFSET.

    Six checks, each one a place a defect would be silent:

      1. the identity, per register pair: `(seg*16 + off) & 0xFFFF` is the
         DESIGNED physical address, on both tiers;
      2. `PS, SS, DS0, DS1` agree in their low 12 bits (the shared physical
         base that makes a segment override a physical no-op);
      3. all 256 composed IVT vectors resolve INSIDE the code region, and
         vector `TERM_VECTOR` is compose's own (-> TERM_AT) rather than the
         generator's;
      4. the anchor: the composed image carries the body at `ANCHOR`;
      5. the `ps` column is LIVE -- every one of the 16 A19-16 values occurs
         for every one of the four segment registers over the population, and
         a single seed's four registers do not all share one k;
      6. NON-VACUITY: the identity check is re-run against a deliberately
         perturbed register set and MUST fire.  A bar that cannot fail is not
         a bar."""
    hits = 0
    t0 = time.time()
    kseen = {s: set() for s in SEG_NAMES}
    bases = set()
    same_k = 0
    for k in range(n):
        for tier in ("soup", "raw"):
            cfg = derive_case(cid, k, dict(ov or {}, force_tier=tier))
            g = build(cfg)
            tag = f"{tier}/{cid}/{k}"
            for e in _seg_off_hits(g, tag):                       # (1)(2)
                hits += 1
                print(f"  BIAS HIT: {e}")
            r = g["regs"]
            for s in SEG_NAMES:
                kseen[s].add(r[s] >> 12)
            bases.add(r["PS"] & 0xFFF)
            same_k += len({r[s] >> 12 for s in SEG_NAMES}) == 1
            if ti.TERM_VECTOR in (g.get("ivt") or {}):            # (3a)
                hits += 1
                print(f"  BIAS HIT: {tag} generator set vector "
                      f"{ti.TERM_VECTOR}, which is compose's")
            img, meta = compose_case(g, cfg)
            bad = [(v, p) for v, _s, _o, p in _ivt_from_image(img)
                   if not (ti.CODE_LO <= p < ti.CODE_HI)]
            if bad:                                               # (3b)
                hits += 1
                print(f"  BIAS HIT: {tag} {len(bad)} IVT vectors resolve "
                      f"outside the code region, e.g. {bad[:3]}")
            tv = _ivt_from_image(img)[ti.TERM_VECTOR]
            if tv[3] != ti.TERM_AT or tv[1] != 0:                 # (3c)
                hits += 1
                print(f"  BIAS HIT: {tag} vector {ti.TERM_VECTOR} is "
                      f"{tv[1]:04x}:{tv[2]:04x}, want 0000:{ti.TERM_AT:04x}")
            if meta["anchor_phys"] != ANCHOR:                     # (4)
                hits += 1
                print(f"  BIAS HIT: {tag} anchor {meta['anchor_phys']:04x} "
                      f"!= {ANCHOR:04x}")
            # the body, on the PRE-SCRUB compose: `compose_case` runs the 0F
            # rule over the code region afterwards and is entitled to move a
            # body byte, so comparing against the scrubbed image would be
            # asserting that the scrub never fires.
            pre, _ = check_seq.compose(g)
            if bytes(pre[ANCHOR:ANCHOR + len(g['instr'])]) != g["instr"]:
                hits += 1
                print(f"  BIAS HIT: {tag} body is not at the anchor")
    # (5) `Bias` is keyed on the seed alone, so the two tiers of one k share
    # it: the population here is `n` draws per register, not 2n.  Coupon
    # collector over 16 values needs ~54; the bar is armed from 200.
    if n >= 200:
        for s in SEG_NAMES:
            if len(kseen[s]) != 16:
                hits += 1
                print(f"  BIAS HIT: {s} took only {len(kseen[s])}/16 A19-16 "
                      f"values over {n} seeds")
    if same_k == 2 * n and n > 4:
        hits += 1
        print("  BIAS HIT: every seed gives all four segment registers the "
              "same k -- the override coverage is vacuous")
    # (6) the control: break the derivation and watch the check bite
    cfg = derive_case(cid, 0, dict(ov or {}, force_tier="soup"))
    gc = build(cfg)
    gc["regs"] = dict(gc["regs"], PS=(gc["regs"]["PS"] + 1) & 0xFFFF)
    ctl = _seg_off_hits(gc, "control")
    if len(ctl) != 2:      # the (PS,PC) identity AND the low-12 agreement
        hits += 1
        print(f"  BIAS HIT: the control did not fire as expected: {ctl}")
    print(f"bias: {n} seeds x 2 tiers in {time.time()-t0:.1f}s | "
          f"base_seg values {len(bases)} | A19-16 values per register "
          f"{ {s: len(kseen[s]) for s in SEG_NAMES} } | "
          f"control fired on {len(ctl)} checks | hits={hits}")
    return hits


# --- the handler pool (D8) -------------------------------------------------
# A handler that traps re-enters a handler and recurses without bound.  The
# scan below is the falsifier: it decodes each composed slot and reports both
# the FORBIDDEN CONTENT and, from the composed IVT, the RECURSION CYCLE that
# content would produce.  Trap sources and the vector each raises:
_TRAP_VEC = {0xCC: 3, 0xCE: 4, 0x62: 5, 0xD4: 0}     # INT3 / INTO / BOUND / AAM
_BANNED_POLICY = frozenset({optable.CFLOW_FWD, optable.CFLOW_GADGET,
                            optable.STACK, optable.PORT, optable.SREG,
                            optable.EVT_ONLY, optable.BRKEM, optable.UNDOC})


def _scan_slot(img, at, limit=None):
    """Decode one handler slot.  -> (violations, raised_vectors).

    Walks from the slot base to the appended IRET, exactly as the EU does.
    Everything it reports is read off the COMPOSED image, i.e. AFTER the 0F
    scrub, because the scrub can move an instruction boundary."""
    limit = limit or ti.IHT_STRIDE
    vio, raises = [], set()
    i = at
    end = at + limit
    while i < end:
        j = i
        while j < end and img[j] in optable.PREFIXES:
            j += 1
        if j >= end:
            vio.append((i - at, "ran off the slot without reaching IRET"))
            break
        op = img[j]
        if op == 0xCF:                       # the IRET compose appended: done
            return vio, raises
        if op == 0x0F:
            vio.append((i - at, "0F extension byte in a handler"))
            return vio, raises
        info = optable.TABLE.get(op)
        pol = info.policy if info else None
        if pol in _BANNED_POLICY:
            vio.append((i - at, f"{op:02x} policy {pol}"))
        if op in _TRAP_VEC:
            raises.add(_TRAP_VEC[op])
        if op == 0xCD and j + 1 < end:
            raises.add(img[j + 1])
        if op in (0x8D, 0x62):
            vio.append((i - at, f"{op:02x} requires a memory operand"))
        if info and info.modrm and j + 1 < end:
            mrm = img[j + 1]
            if (mrm >> 6) != 3:
                vio.append((i - at, f"{op:02x} modrm mod={mrm >> 6}, want 3"))
            ext = (mrm >> 3) & 7
            if op in (0xF6, 0xF7) and ext in (6, 7):
                vio.append((i - at, f"{op:02x} /{ext} DIV/IDIV"))
                raises.add(0)
            if op == 0xFF and ext == 6:
                vio.append((i - at, f"{op:02x} /6 PUSH"))
        step = max(1, optable.ilen(img, i))
        i += step
    else:
        vio.append((limit, "no IRET inside the slot"))
    return vio, raises


def _handler_cycle(img):
    """The recursion path a composed image admits, or None.

    vector -> slot (from the composed IVT) -> the vectors that slot's body can
    raise -> vector ...  Any cycle is unbounded re-entry, and every entry also
    pushes three words, so it eats the stack as well as the clock."""
    slot_of = {}
    for v, _s, _o, p in _ivt_from_image(img):
        if ti.IHT_AT <= p < ti.IHT_AT + ti.IHT_N * ti.IHT_STRIDE:
            slot_of[v] = p
    raises = {}
    for p in set(slot_of.values()):
        raises[p] = _scan_slot(img, p)[1]
    for v0 in sorted(slot_of):
        seen, path, v = set(), [], v0
        while v in slot_of and v not in seen:
            seen.add(v)
            p = slot_of[v]
            path.append((v, p))
            nxt = sorted(raises.get(p, ()))
            if not nxt:
                break
            v = nxt[0]
            if v in seen:
                path.append((v, slot_of.get(v)))
                return path
    return None


def _lint_handlers(cid, n, ov=None):
    """fuzz-v2 D8 -- THE HANDLER POOL, AND ITS RECURSION FALSIFIER.

    Three checks:
      1. over `n` seeds x 2 tiers x IHT_N slots, decoded off the COMPOSED
         image: 0 forbidden instructions and 0 slots that can raise anything;
      2. 0 recursion cycles in the composed vector->slot->vector graph;
      3. NON-VACUITY, twice.  The same scanner is pointed at an image whose
         slot has been overwritten with a body containing an EXCLUDED trapping
         opcode -- `CD v` (a software interrupt back into itself) and `F7 F6`
         (DIV by a register, the divide trap) -- and must report BOTH the
         violation AND the cycle.  Without this the zero above proves only
         that the scanner is asleep."""
    hits = 0
    t0 = time.time()
    slots = nins = 0
    for k in range(n):
        for tier in ("soup", "raw"):
            cfg = derive_case(cid, k, dict(ov or {}, force_tier=tier))
            img, _m = compose_case(build(cfg), cfg)
            for s in range(ti.IHT_N):
                at = ti.IHT_AT + s * ti.IHT_STRIDE
                vio, raises = _scan_slot(img, at)
                slots += 1
                nins += max(0, img.find(0xCF, at, at + ti.IHT_STRIDE) - at)
                if vio or raises:
                    hits += 1
                    print(f"  HANDLER HIT {tier}/{cid}/{k} slot {s} "
                          f"@{at:04x}: vio={vio[:3]} raises={sorted(raises)}")
            cyc = _handler_cycle(img)
            if cyc:
                hits += 1
                print(f"  HANDLER HIT {tier}/{cid}/{k}: recursion cycle {cyc}")
    # --- (3) the controls ---------------------------------------------------
    cfg = derive_case(cid, 0, dict(ov or {}, force_tier="soup"))
    base, _m = compose_case(build(cfg), cfg)
    ivt = _ivt_from_image(base)
    v_any = next(v for v, _s, _o, p in ivt
                 if ti.IHT_AT <= p < ti.IHT_AT + ti.IHT_N * ti.IHT_STRIDE)
    # (blob, the vector that blob RAISES) -- the plant goes in the slot THAT
    # vector maps to, so the cycle is one hop and needs no luck.
    for name, blob, vec in (
            (f"CD {v_any} (INT back into its own vector)",
             bytes([0xCD, v_any]), v_any),
            ("F7 F6 (DIV DW -- the divide trap, vector 0)",
             b"\xf7\xf6", 0)):
        img = bytearray(base)
        at = ivt[vec][3]
        if not (ti.IHT_AT <= at < ti.IHT_AT + ti.IHT_N * ti.IHT_STRIDE):
            hits += 1
            print(f"  handler CONTROL [{name}]: vector {vec} does not point "
                  f"into the handler table ({at:04x})")
            continue
        img[at:at + len(blob)] = blob
        img[at + len(blob)] = 0xCF
        vio, raises = _scan_slot(img, at)
        cyc = _handler_cycle(img)
        ok = bool(vio) and bool(raises) and cyc is not None
        print(f"  handler CONTROL [{name}] planted at slot {at:04x} "
              f"(vector {vec}): vio={vio} raises={sorted(raises)} "
              f"cycle={cyc if cyc is None else cyc[:4]} -> "
              f"{'FIRES' if ok else 'DID NOT FIRE'}")
        if not ok:
            hits += 1
    print(f"handlers: {n} seeds x 2 tiers x {ti.IHT_N} slots = {slots} slots, "
          f"{nins} body bytes decoded in {time.time()-t0:.1f}s | hits={hits}")
    return hits


def _body_of(image, meta):
    """The bytes the EU actually executes from the anchor: the composed,
    SCRUBBED body slice.  `g["instr"]` is the generator's INTENT, and erratum
    E-2 is that the two are not the same stream."""
    at = meta["anchor_phys"]
    return bytes(image[at:at + meta["instr_len"]])


def _reason_class(why):
    """`optable.scan_code` reasons, bucketed for counting: the opcode/port byte
    is the detail, the CLASS is what a reviewer counts."""
    if why.startswith("banned 0F"):
        return "banned 0F"
    if why.endswith("banned ext"):
        return why.split()[0] + " " + why.split()[1] + " banned ext"
    return why.rsplit(" ", 1)[0]


def _boundaries(buf):
    """The instruction-start offsets a linear decode of `buf` produces."""
    out, i = [], 0
    while i < len(buf):
        out.append(i)
        i += max(1, optable.ilen(buf, i))
    return out


def _lint_soup(cid, n, report_every, ov=None):
    """fuzz-v2 ERRATUM E-2 -- THE SCAN IS ON THE POST-SCRUB STREAM.

    It used to run `optable.scan_code(g["instr"])`, the generator's
    PRE-SCRUB byte stream.  T3's 0F rule rewrites the `0F` AND THE BYTE AFTER
    IT, and when the `0F` is an immediate that byte is the next instruction's
    opcode -- so the tail re-decodes and the boundaries move.  A lint that
    describes bytes which do not execute is the vacuous-gate pattern
    (`docs/notes/artifact_receipt_layer.md`), so the authority is now the
    composed image's body slice.

    THREE POPULATIONS, kept apart because they mean different things:

      * `hits` (the GATE) -- banned content in the executed stream that the
        scrub is supposed to have removed, i.e. any `0F` violation, plus the
        generator's own pre-scrub violations, plus a generator whose emitted
        instruction lengths do not length-decode.  The pre-scrub scan is
        RETAINED, not replaced: a banned byte the generator emitted is a
        generator bug even when the scrub happens to mask it.
      * `moved` -- bodies whose instruction boundaries the scrub shifted.
        E-2's own number, measured on every lint run rather than once.
      * `resid` -- banned group extensions / forbidden-port I/O that exist
        ONLY post-scrub, i.e. that the boundary shift manufactured.  E-2 rules
        these ACCEPTED and REPORTED: v2 containment is STRUCTURAL (the 0xCC
        fill plus INT3 catches an escape by any means), not policy-based.
        They are counted by reason and printed, never silently dropped."""
    hits = comp_err = wild = brkem = halt = tf = 0
    moved = 0
    resid = Counter()
    resid_ex = []
    t0 = time.time()
    for k in range(n):
        cfg = derive_case(cid, k, dict(ov or {}, force_tier="soup"))
        g = build(cfg)
        wild += bool(g["wild"])
        brkem += bool(g["brkem_pos"])
        halt += g["has_halt"]
        tf += g["has_tf"]
        # (i) the GENERATOR's stream: what it MEANT to emit.
        pre = optable.scan_code(g["instr"])
        if pre:
            hits += len(pre)
            print(f"  SOUP HIT (pre-scrub, generator) soup/{cid}/{k}: {pre[:4]}")
        off = 0
        for ins in g["ins"]:
            if optable.ilen(g["instr"], off) != len(ins):
                hits += 1
                print(f"  SOUP MALFORMED soup/{cid}/{k} @off {off}")
                break
            off += len(ins)
        # (ii) the ARTIFACT's stream: what the part executes.  This also
        # subsumes the compose check the old form did separately.
        try:
            image, meta = compose_case(g, cfg)
        except Exception as e:                          # noqa: BLE001
            comp_err += 1
            if comp_err <= 5:
                print(f"  SOUP COMPOSE ERR soup/{cid}/{k}: {e!r}")
            continue
        body = _body_of(image, meta)
        post = optable.scan_code(body)
        if body != g["instr"]:
            moved += _boundaries(body) != _boundaries(g["instr"])
        pre_why = {w for _o, w in pre}
        for at, why in post:
            if why.startswith("banned 0F"):
                hits += 1
                print(f"  SOUP HIT (post-scrub) soup/{cid}/{k} @{at}: {why}")
                continue
            if why in pre_why:
                continue        # the generator's own, already a gate hit above
            resid[_reason_class(why)] += 1
            if len(resid_ex) < 8:
                resid_ex.append(f"soup/{cid}/{k}@{at}: {why}")
        if report_every and (k + 1) % report_every == 0:
            print(f"  soup {k+1}/{n} ({(k+1)/(time.time()-t0):.0f}/s) "
                  f"hits={hits} comp_err={comp_err} moved={moved} "
                  f"resid={sum(resid.values())}", flush=True)
    print(f"soup: {n} seeds in {time.time()-t0:.1f}s | wild={wild} "
          f"brkem={brkem} halt={halt} tf={tf} | hits={hits} compose_err={comp_err}")
    print(f"  E-2, on the EXECUTED (post-scrub) body: boundaries moved on "
          f"{moved}/{n} = {100*moved/max(1,n):.1f}% of bodies; "
          f"{sum(resid.values())} scrub-created group-ext / port hits "
          f"in {len(resid)} classes: {dict(resid)}")
    for e in resid_ex:
        print(f"    e.g. {e}")
    print("  (E-2 ruling: these are REPORTED, not a lint failure -- v2 "
          "containment is structural, the 0xCC fill + INT3, not policy-based)")
    hits += _lint_soup_control(cid, ov)
    return hits, comp_err


def _lint_soup_control(cid, ov=None):
    """NON-VACUITY for the corrected scan.  A zero above proves nothing unless
    the scan can produce a non-zero, and unless it is demonstrably reading the
    POST-scrub bytes rather than the generator's.

    Four plants on one real seed, two of them the discriminator:

      A  `0F 34` planted in the GENERATOR's stream (the lockup pair).  The
         pre-scrub scan must FIRE, the post-scrub scan must be SILENT, and the
         composed body must read `90 90` there.  This is the check that could
         only pass if the two scans read different bytes -- under the old
         (pre-scrub) lint the second clause was untestable.
      B  `FE F8` (`FE /7`, a banned group extension) planted in the COMPOSED
         image's body -- the exact class E-2 measured at 3/2,000.  Must FIRE.
      C  `E6 FC` (`OUT 0xFC, AL`, the done-marker port) planted the same way.
         Must FIRE.
      D  `0F 34` planted in the COMPOSED body, i.e. AFTER the scrub, so the
         scrub cannot have removed it.  Must FIRE as a GATE hit -- the class
         that still fails the lint."""
    cfg = derive_case(cid, 0, dict(ov or {}, force_tier="soup"))
    g = build(cfg)
    img, meta = compose_case(g, cfg)
    at = meta["anchor_phys"]
    bad = 0

    def say(name, cond, detail):
        nonlocal bad
        print(f"  soup CONTROL [{name}]: {detail} -> "
              f"{'FIRES' if cond else 'DID NOT FIRE'}")
        if not cond:
            bad += 1

    # A -- planted before the scrub, AT THE ANCHOR, which is a decode boundary
    # by construction (a plant at an arbitrary offset can land mid-instruction,
    # where a linear decode never reaches it and the control is itself vacuous).
    ga = dict(g, instr=b"\x0f\x34" + bytes(g["instr"][2:]))
    pre_a = optable.scan_code(ga["instr"])
    img_a, meta_a = compose_case(ga, cfg)
    body_a = _body_of(img_a, meta_a)
    post_a = optable.scan_code(body_a)
    say("A 0F 34 planted PRE-scrub",
        bool(pre_a) and not post_a and body_a[0:2] == b"\x90\x90",
        f"pre={pre_a[:2]} post={post_a[:2]} body[0:2]={body_a[0:2].hex()}")

    # B, C, D -- planted after the scrub, in the composed image
    for name, blob in (("B FE /7 planted POST-scrub", b"\xfe\xf8"),
                       ("C OUT 0xFC planted POST-scrub", b"\xe6\xfc"),
                       ("D 0F 34 planted POST-scrub", b"\x0f\x34")):
        buf = bytearray(img)
        buf[at:at + len(blob)] = blob
        hit = optable.scan_code(_body_of(bytes(buf), meta))
        gate = [h for h in hit if h[1].startswith("banned 0F")]
        say(name, bool(hit), f"hit={hit[:2]} gate_class={len(gate)}")
        if name.startswith("D") and not gate:
            bad += 1
            print("  soup CONTROL [D]: fired, but NOT in the gate class")
    return bad


def _lint_raw(cid, n, report_every, ov=None):
    hits = comp_err = whole = payload = 0
    scrub_tot = {"pair0f": 0}
    t0 = time.time()
    for k in range(n):
        cfg = derive_case(cid, k, dict(ov or {}, force_tier="raw"))
        g = build(cfg)
        whole += g["raw_mode"] == "whole"
        payload += g["raw_mode"] == "payload"
        for key in scrub_tot:
            scrub_tot[key] += g["scrubbed"].get(key, 0)
        try:
            img, _m = compose_case(g, cfg)
        except Exception as e:                          # noqa: BLE001
            comp_err += 1
            if comp_err <= 5:
                print(f"  RAW COMPOSE ERR raw/{cid}/{k}: {e!r}")
            continue
        # the CODE REGION, on the WHOLE composed image: the harness page,
        # the composed IVT and the carve-outs are not code and are not the
        # rule's business (optable.CODE_SPANS says why).
        vio = optable.scan_raw_bytes(img, optable.CODE_SPANS)
        if vio:
            hits += len(vio)
            print(f"  RAW HIT raw/{cid}/{k} mode={g['raw_mode']}: {vio[:4]}")
        if report_every and (k + 1) % report_every == 0:
            print(f"  raw {k+1}/{n} ({(k+1)/(time.time()-t0):.0f}/s) "
                  f"hits={hits} comp_err={comp_err}", flush=True)
    print(f"raw: {n} seeds in {time.time()-t0:.1f}s | whole={whole} "
          f"payload={payload} | scrub_totals={scrub_tot} | "
          f"hits={hits} compose_err={comp_err}")
    return hits, comp_err


def cmd_lint(a):
    # NOTE (§72.7a -> §73.10): there was never a hang here.  `--report-every`
    # defaults to 0 and the RAW phase is 100,000 seeds ~= 25 minutes with the
    # worker at ~100 % CPU and nothing on stdout.  Pass `--report-every 5000`
    # if you want to watch it.
    ov = {}
    print(f"fuzz lint: cid={a.cid} soup_n={a.n} raw_n={a.raw_n} "
          f"wvec_n={a.wvec_n} bias_n={a.bias_n} handler_n={a.handler_n} "
          f"ov={ov}")
    bh = _lint_bias(a.cid, a.bias_n, ov) if a.bias_n else 0
    hh = _lint_handlers(a.cid, a.handler_n, ov) if a.handler_n else 0
    sh, sc = _lint_soup(a.cid, a.n, a.report_every, ov)
    rh, rc = _lint_raw(a.cid, a.raw_n, a.report_every, ov)
    wh = _lint_wvec(a.cid, a.wvec_n, ov) if a.wvec_n else 0
    total = sh + sc + rh + rc + wh + bh + hh
    print(f"\nLINT {'PASS' if total == 0 else 'FAIL'}: "
          f"soup hits={sh} compose_err={sc}; raw hits={rh} compose_err={rc}; "
          f"wvec hits={wh}; bias hits={bh}; handler hits={hh}")
    return 0 if total == 0 else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("new")
    p.add_argument("cid")
    p.set_defaults(func=cmd_new)

    p = sub.add_parser("run")
    p.add_argument("cid")
    p.add_argument("--host", default="root@mister-nec")
    p.add_argument("--session-seeds", type=int, default=SESSION_SEEDS)
    p.add_argument("--start", type=int, default=None)
    p.add_argument("--tb-only", action="store_true")
    p.add_argument("--jobs", type=int, default=1)
    p.add_argument("--stop-after", type=int, default=0)
    p.add_argument("--measure", type=int, default=0)
    p.add_argument("--allow-stale", action="store_true")
    p.add_argument("--force-tier", choices=["soup", "raw"])
    p.add_argument("--contained", action="store_true")
    p.add_argument("--w0", action="store_true")
    p.add_argument("--force-fixed", type=int, default=None,
                   help="task #38: force a FIXED wait level N (the general "
                        "form of --w0; the fix1/fix2/fix3 control strata)")
    p.add_argument("--no-evt", action="store_true")
    p.add_argument("--strict", action="store_true",
                   help="strict contained fall-through generation (pilot)")
    p.add_argument("--no-brkem", action="store_true",
                   help="p_brkem=0 (no 8080-entry dead captures); keeps other breadth")
    p.add_argument("--mainline", action="store_true",
                   help="suppress deliberate chip-vs-core-divergent classes "
                        "(brkem/tf/undoc); keep window-only breadth")
    p.add_argument("--survey", action="store_true",
                   help="census mode: survey all w0 TIMING sigs (keep the hard "
                        "functional/provenance stops + circuit breaker)")
    p.add_argument("--force-evt", action="store_true")
    p.add_argument("--force-wrand", default=None, help="comma wmax list, e.g. 1,3,7")
    p.add_argument("--wvec-shapes", default=None,
                   help="task #38: per-access WAIT VECTOR axis; comma shape "
                        f"list from {','.join(wv.SHAPES)}.  Supersedes the "
                        "fixed/wrand wait sources (replay > rand > uniform in "
                        "all three legs)")
    p.add_argument("--done-dist", default=None)
    p.add_argument("--keep-rows-every", type=int, default=0,
                   help="fuzz-v2 prereg §7 item 2: RETAIN the full per-clock "
                        "rows of every k with k %% N == 0, outside the "
                        "SUCCESS-ballast quota.  0 = off.  This is how a "
                        "FROZEN bank rule is expressed: the ballast path is "
                        "capped at 100 captures and cannot be one")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("status")
    p.add_argument("cid")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("show")
    p.add_argument("cid")
    p.add_argument("k", type=int)
    p.add_argument("--contained", action="store_true")
    p.add_argument("--force-tier", choices=["soup", "raw"])
    p.add_argument("--wvec-shapes", default=None)
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("replay")
    p.add_argument("cid")
    p.add_argument("--start", type=int, default=0)
    p.add_argument("--n", type=int, default=8)
    p.add_argument("--jobs", type=int, default=8)
    p.add_argument("--contained", action="store_true")
    p.add_argument("--force-tier", choices=["soup", "raw"])
    p.set_defaults(func=cmd_replay)

    p = sub.add_parser("measure", help="fuzz-v2 erratum E-1: escape count and "
                                       "terminator-reached rate (NOT a gate)")
    p.add_argument("cid")
    p.add_argument("--n", type=int, default=2000)
    p.add_argument("--start", type=int, default=0)
    p.add_argument("--jobs", type=int, default=8)
    p.add_argument("--force-tier", choices=["soup", "raw"])
    p.add_argument("--report-every", type=int, default=0)
    p.add_argument("--out", default=None, help="per-seed rows as JSON")
    p.add_argument("--core", default=None,
                   help="THE ENGINE, explicitly.  Default None = "
                        "`check_seq.CORE` = the ARCHIVED fsm core, which is "
                        "how E-1 was first measured without saying so.  Every "
                        "row carries the core, binary and receipt actually "
                        "used.")
    p.set_defaults(func=cmd_measure)

    p = sub.add_parser("lint")
    p.add_argument("--cid", default="lint")
    p.add_argument("--n", type=int, default=10000)
    p.add_argument("--raw-n", type=int, default=100000)
    p.add_argument("--wvec-n", type=int, default=200,
                   help="task #38: seeds for the wait-vector axis leg "
                        "(0 disables it)")
    p.add_argument("--bias-n", type=int, default=500,
                   help="fuzz-v2 T2: seeds for the segment/offset identity "
                        "leg, with its non-vacuity control (0 disables it)")
    p.add_argument("--handler-n", type=int, default=500,
                   help="fuzz-v2 T2: seeds for the handler-pool leg and its "
                        "recursion falsifier (0 disables it)")
    p.add_argument("--report-every", type=int, default=0)
    p.set_defaults(func=cmd_lint)

    a = ap.parse_args()
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
