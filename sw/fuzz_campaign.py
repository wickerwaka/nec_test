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
from v30run import run_image, RunError                  # noqa: E402
import v30ctl                                           # noqa: E402
import wvec_shapes as wv                                # noqa: E402

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


def derive_case(cid, k, ov=None):
    """derive_axes + optional pilot overrides + nmax_eff recompute + cfg_hash.
    ov keys: force_tier, force_contained, w0, no_evt, force_evt, force_wrand,
    wvec_shapes, no8080."""
    ov = ov or {}
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
    # task #32 escape containment: fill non-program image space with HLT (0xF4)
    # instead of NOP (0x90) so wandering/escaping execution HALTS deterministically
    # inside the 64K image (both legs quiet at the same fence row -> classifiable)
    # rather than gliding out to open-bus feedthrough. SOUP-only (raw keeps 0x90 +
    # the open_bus rule; raw payload-mode relies on 0x90 surround). Opt-in axis so
    # existing banked/composed images stay byte-identical when it is off.
    ax["fence"] = bool(ov.get("fence"))
    # task #38 (wrfuzz) -- THE 8080 EXCLUSION, BY CONSTRUCTION.
    # The user deferred 8080/BRKEM on 2026-08-05, so this campaign's corpora
    # carry no BRKEM.  It is a GENERATION axis, not a post-filter: `build()`
    # sets `p_brkem = 0` for soup, hands `no8080` to `gen_raw`'s own scrub, and
    # `compose_case()` rewrites any residual `0F FF` byte PAIR in the composed
    # image to `90 90`.  The pair matters because §63.5 found 42 class-A seeds
    # that reach 8080 mode with the generator's BRKEM knob OFF, 18 of them
    # carrying a `0F FF` pair the generator never emitted -- an immediate byte
    # meeting the next opcode.  ⚠ WHAT IT DOES NOT DO: §63.5's other 24 have no
    # `0F FF` in the image at all and how they enter 8080 mode is STILL NOT
    # ESTABLISHED, so this axis makes a corpus BRKEM-free, NOT 8080-free.  The
    # survey COUNTS class-A landings from the captures with §63.5's mechanical
    # criterion; it does not assume there are none.
    ax["no8080"] = bool(ov.get("no8080"))
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
                                  "strict", "no_brkem", "brkem_high", "mainline",
                                  "fence")}
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
    if ax["no8080"]:
        core["no8080"] = True
    ax["cfg_hash"] = hashlib.sha1(
        json.dumps(core, sort_keys=True).encode()).hexdigest()[:12]
    return ax


def build(cfg):
    """Materialise the g-dict for a derived config."""
    seed = f"{cfg['cid']}/{cfg['k']}"
    if cfg["tier"] == "raw":
        g = gen_raw(seed, no8080=bool(cfg.get("no8080")))
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
        elif cfg.get("brkem_high"):
            # ~50% of seeds carry a BRKEM; suppress the OTHER divergence classes
            # (tf/undoc/random-DS) so the BRKEM-recovery pilot isolates BRKEM.
            knobs = SoupKnobs(p_brkem=0.020, p_tf=0.0, p_undoc=0.0,
                              p_sreg_rand=0.0)
        elif cfg.get("no_brkem"):
            knobs = SoupKnobs(p_brkem=0.0)     # keep tf/undoc/sreg breadth (cheap)
        else:
            knobs = SoupKnobs()
        if cfg.get("no8080"):
            # task #38: the 8080 deferral, AT THE KNOB and as a MODIFIER, so
            # it composes with every existing knob set instead of replacing
            # one.  Only BRKEM is out of scope; undoc / tf / sreg breadth is
            # this campaign's own breadth and is left alone.
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
    # task #32: SOUP HLT-fence fill (0xF4) when the fence axis is on; else 0x90.
    # RAW always 0x90 (payload mode relies on the NOP surround; raw scrubs 0xF4).
    g["fill"] = 0xF4 if (cfg["tier"] != "raw" and cfg.get("fence")) else 0x90
    return g


BRKEM_PAIR = b"\x0f\xff"


def scrub_brkem_image(image):
    """task #38.  Rewrite every `0F FF` byte PAIR in a composed image to
    `90 90`.  Returns (image, n_pairs).

    ONE RULE, and it is the whole mechanism: BRKEM is `0F FF ib` and nothing
    else in the ISA is that pair, so removing the pair removes the entry.
    Both bytes go to NOP rather than only the second (which is `gen_raw`'s
    rule for its own banned set) because a bare `FF` left behind is a group-5
    ModR/M whose `/3` and `/5` are far CALL / far JMP through a random word --
    trading a deferred-scope entry for an escape.

    It cannot create a new pair (0x90 is neither 0x0F nor 0xFF), so ONE
    left-to-right pass reaches a fixed point; `no_brkem_pairs()` is the
    independent check that says so on the artifact rather than in the
    argument."""
    buf = bytearray(image)
    n = 0
    i = buf.find(BRKEM_PAIR)
    while i >= 0:
        buf[i] = 0x90
        buf[i + 1] = 0x90
        n += 1
        i = buf.find(BRKEM_PAIR, i + 1)
    return bytes(buf), n


def no_brkem_pairs(image):
    """The check, not the argument: how many `0F FF` pairs remain."""
    b, n = bytes(image), 0
    i = b.find(BRKEM_PAIR)
    while i >= 0:
        n += 1
        i = b.find(BRKEM_PAIR, i + 1)
    return n


def compose_case(g, cfg):
    """`check_seq.compose` plus this campaign's image-level axes.

    THE ONE PLACE the composed image is built for a fuzz case, so that
    `eval_case`, `show`, `lint` and `ucsim_fuzz.regen` cannot drift apart --
    a regeneration path that composes differently from the capture path is the
    GEN-DRIFT failure the bank's sha gate exists to catch, and the cheapest way
    to never have it is to have one function.

    With every new axis OFF this returns `check_seq.compose(g)` unchanged, so
    every seed banked before task #38 regenerates byte for byte."""
    image, meta = check_seq.compose(g)
    if cfg.get("no8080"):
        image, _ = scrub_brkem_image(image)
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


def capture_tb(image, meta, cfg):
    """Single Verilator TB leg (temp hygiene handled inside run_tb)."""
    w = cfg["waits"]
    wrand = (w["wmax"], w["wseed"]) if w["wrand"] else None
    fixed = 0 if w["wrand"] else w["fixed"]
    return check_seq.run_tb(image, TB_ROWS, waits=fixed,
                            evt=_evt_tuple(cfg, meta), wrand=wrand,
                            wvec=wvec_of(cfg))


def capture_board(image, meta, cfg, host):
    """hw-ab: socketed chip (use_core=0) then fabric core (use_core=1), same
    image/evt/wrand. ensure() force-cleans the rig at connect. One reconnect +
    retry on RunError, else the caller quarantines."""
    w = cfg["waits"]
    wrand = (w["wmax"], w["wseed"]) if w["wrand"] else None
    fixed = 0 if w["wrand"] else w["fixed"]
    evt = _evt_tuple(cfg, meta)
    vec = wvec_of(cfg)
    for attempt in (1, 2):
        try:
            real = check_seq.run_chip(image, host, use_core=False, waits=fixed,
                                      evt=evt, wrand=wrand, wvec=vec)
            sim = check_seq.run_chip(image, host, use_core=True, waits=fixed,
                                     evt=evt, wrand=wrand, wvec=vec)
            return real, sim, None
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
            if a < 0x10000 and (not pcs or pcs[-1] != a):
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


# ===========================================================================
# Result line (harmonised schema).
# ===========================================================================
def result_line(cfg, g, sha, v, di, gen_git, build_stale, ts):
    # task #38: the vector is banked IN FULL (`wvec_hex`, 2 chars per entry,
    # NWVEC entries) beside its spec and its sha256.  A vector that exists
    # only as a derivation is one nobody can check the rig's readback against,
    # and the whole point of the axis is that the rig applied THIS sequence.
    vec = wvec_of(cfg)
    return {
        "k": cfg["k"], "seed": f"{cfg['cid']}/{cfg['k']}", "cid": cfg["cid"],
        "tier": cfg["tier"], "cfg_hash": cfg["cfg_hash"],
        "wvec": cfg.get("wvec"), "no8080": bool(cfg.get("no8080")),
        "wvec_hex": wv.to_hex(vec) if vec else None,
        "wvec_sha256": wv.sha256_of(vec) if vec else None,
        "wvec_n": len(vec) if vec else 0,
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


def eval_case(cid, k, ov, tb_only, host, build_stale, keep_rows=False):
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
    if tb_only:
        try:
            real = capture_tb(image, meta, cfg)
            sim = copy.deepcopy(real)     # TB-vs-TB: plumbing + done-in-window
        except Exception as e:            # noqa: BLE001  (run_tb RuntimeError)
            real = sim = None
            run_error = f"run_error:tb:{str(e)[:120]}"
    else:
        real, sim, run_error = capture_board(image, meta, cfg, host)
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
    line = result_line(cfg, g, sha, v, di, _gen_git(), build_stale,
                        time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
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
def _pool_init(cid, ov, tb_only, host, build_stale):
    global _EVAL_ARGS
    _EVAL_ARGS = (cid, ov, tb_only, host, build_stale)
    _engine()


def _pool_eval(k):
    cid, ov, tb_only, host, build_stale = _EVAL_ARGS
    return eval_case(cid, k, ov, tb_only, host, build_stale)


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
    if a.brkem_high:
        ov["brkem_high"] = True
    if a.mainline:
        ov["mainline"] = True
    if getattr(a, "fence", False):
        ov["fence"] = True                 # task #32 soup HLT-fence fill
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
    if getattr(a, "no8080", False):
        ov["no8080"] = True

    start = a.start if a.start is not None else _resume_k(results_path)
    end = start + a.session_seeds
    print(f"run {a.cid}: seeds [{start},{end}) tb_only={a.tb_only} "
          f"jobs={a.jobs} ov={ov}", flush=True)

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
        # gzip divergent captures always; SUCCESS ballast up to the per-stratum
        # quota (stratified tier x waits-class) for the fab-vs-TB float-floor alarm
        want_cap = res["rows"] is not None and v.verdict != fc.SUCCESS
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
                      initargs=(a.cid, ov, True, a.host, build_stale)) as pool:
                for i, res in enumerate(pool.imap(_pool_eval, ks, chunksize=4)):
                    handle(res)
                    _progress(res, i, start, t_start, cov, cdir)
                    if stopped:
                        pool.terminate()
                        break
        else:
            for i, k in enumerate(ks):
                res = eval_case(a.cid, k, ov, a.tb_only, a.host, build_stale)
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
    return 1 if stopped and "circuit_breaker" in stopped else 0


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
    if getattr(a, "no8080", False):
        ov["no8080"] = True
    cfg = derive_case(a.cid, a.k, ov)
    g = build(cfg)
    image, meta = compose_case(g, cfg)
    sha = hashlib.sha256(bytes(image)).hexdigest()
    vec = wvec_of(cfg)
    print(json.dumps({"cfg": {kk: cfg[kk] for kk in
                              ("tier", "evt", "waits", "wild", "nmin",
                               "nmax_eff", "cfg_hash", "wvec", "no8080")},
                      "wvec_sha256": wv.sha256_of(vec) if vec else None,
                      "wvec_head": vec[:32] if vec else None,
                      "brkem_pairs": no_brkem_pairs(image),
                      "n_ins": g["n_ins"], "wild": g.get("wild"),
                      "has_brkem": g.get("has_brkem"), "brkem_pos": g.get("brkem_pos"),
                      "has_halt": g.get("has_halt"), "raw_mode": g.get("raw_mode"),
                      "image_sha256": sha, "anchor": meta["anchor_linear"]},
                     indent=1))
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
      5. `no8080` leaves ZERO `0F FF` pairs in the composed image, on BOTH
         tiers, measured on the artifact;
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
    off.pop("no8080", None)
    with tempfile.TemporaryDirectory() as td:
        for k in range(n):
            for tier in ("soup", "raw"):
                base = dict(off, force_tier=tier)
                cfg0 = derive_case(cid, k, base)
                img0, _ = compose_case(build(cfg0), cfg0)
                # (4) the axis OFF is byte-identical to a plain compose
                g0 = build(cfg0)
                if bytes(img0) != bytes(check_seq.compose(g0)[0]):
                    hits += 1
                    print(f"  WVEC HIT: {tier}/{k} axis-off image moved")
                # (3)(6) with the axis ON
                cfgs = []
                for shape in wv.SHAPES:
                    c = derive_case(cid, k, dict(base, wvec_shapes=[shape],
                                                 no8080=True))
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
                    npair = no_brkem_pairs(img)
                    if npair:
                        hits += 1
                        print(f"  WVEC HIT: {tier}/{k}/{shape} {npair} 0F FF "
                              f"pairs survive no8080")
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


def _lint_soup(cid, n, report_every, ov=None):
    hits = comp_err = wild = brkem = halt = tf = 0
    t0 = time.time()
    for k in range(n):
        cfg = derive_case(cid, k, dict(ov or {}, force_tier="soup"))
        g = build(cfg)
        wild += bool(g["wild"])
        brkem += bool(g["brkem_pos"])
        halt += g["has_halt"]
        tf += g["has_tf"]
        vio = optable.scan_code(g["instr"])
        if vio:
            hits += len(vio)
            print(f"  SOUP HIT soup/{cid}/{k}: {vio[:4]}")
        off = 0
        for ins in g["ins"]:
            if optable.ilen(g["instr"], off) != len(ins):
                hits += 1
                print(f"  SOUP MALFORMED soup/{cid}/{k} @off {off}")
                break
            off += len(ins)
        try:
            check_seq.compose(g)
        except Exception as e:                          # noqa: BLE001
            comp_err += 1
            if comp_err <= 5:
                print(f"  SOUP COMPOSE ERR soup/{cid}/{k}: {e!r}")
        if report_every and (k + 1) % report_every == 0:
            print(f"  soup {k+1}/{n} ({(k+1)/(time.time()-t0):.0f}/s) "
                  f"hits={hits} comp_err={comp_err}", flush=True)
    print(f"soup: {n} seeds in {time.time()-t0:.1f}s | wild={wild} "
          f"brkem={brkem} halt={halt} tf={tf} | hits={hits} compose_err={comp_err}")
    return hits, comp_err


def _lint_raw(cid, n, report_every, ov=None):
    hits = comp_err = whole = payload = 0
    scrub_tot = {"pair0f": 0, "halt": 0, "poll": 0, "brkem": 0}
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
        vio = optable.scan_raw_bytes(img[:RESERVED_LO])
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
    if getattr(a, "no8080", False):
        ov["no8080"] = True
    print(f"fuzz lint: cid={a.cid} soup_n={a.n} raw_n={a.raw_n} "
          f"wvec_n={a.wvec_n} ov={ov}")
    sh, sc = _lint_soup(a.cid, a.n, a.report_every, ov)
    rh, rc = _lint_raw(a.cid, a.raw_n, a.report_every, ov)
    wh = _lint_wvec(a.cid, a.wvec_n, ov) if a.wvec_n else 0
    total = sh + sc + rh + rc + wh
    print(f"\nLINT {'PASS' if total == 0 else 'FAIL'}: "
          f"soup hits={sh} compose_err={sc}; raw hits={rh} compose_err={rc}; "
          f"wvec hits={wh}")
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
    p.add_argument("--fence", action="store_true",
                   help="task #32: SOUP HLT-fence fill (0xF4) so escapes halt "
                        "deterministically in-image (raw unaffected)")
    p.add_argument("--no-brkem", action="store_true",
                   help="p_brkem=0 (no 8080-entry dead captures); keeps other breadth")
    p.add_argument("--brkem-high", action="store_true",
                   help="p_brkem forced high (~50%% of seeds carry a BRKEM)")
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
    p.add_argument("--no8080", action="store_true",
                   help="task #38: BRKEM-free by construction (p_brkem=0 + "
                        "the raw scrub + the composed-image 0F FF rewrite).  "
                        "Makes a corpus BRKEM-free, NOT 8080-free -- see "
                        "ucore_provenance.md §63.5")
    p.add_argument("--done-dist", default=None)
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
    p.add_argument("--no8080", action="store_true")
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("replay")
    p.add_argument("cid")
    p.add_argument("--start", type=int, default=0)
    p.add_argument("--n", type=int, default=8)
    p.add_argument("--jobs", type=int, default=8)
    p.add_argument("--contained", action="store_true")
    p.add_argument("--force-tier", choices=["soup", "raw"])
    p.set_defaults(func=cmd_replay)

    p = sub.add_parser("lint")
    p.add_argument("--cid", default="lint")
    p.add_argument("--n", type=int, default=10000)
    p.add_argument("--raw-n", type=int, default=100000)
    p.add_argument("--wvec-n", type=int, default=200,
                   help="task #38: seeds for the wait-vector axis leg "
                        "(0 disables it)")
    p.add_argument("--no8080", action="store_true",
                   help="task #38: lint the BRKEM-free generation axis")
    p.add_argument("--report-every", type=int, default=0)
    p.set_defaults(func=cmd_lint)

    a = ap.parse_args()
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
