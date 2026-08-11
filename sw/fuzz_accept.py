#!/usr/bin/env python3
"""fuzz_accept - acceptance rule engine for the massive fuzz expansion
(task #29, Phase 3). Plugs into the fuzz_classify AcceptEngine hook: when the
verdict tree finds functional or timing evidence, the engine decides whether a
KNOWN divergence class covers it (-> KNOWN_ACCEPTED) or nothing does (-> the
divergence surfaces as FUNCTIONAL / TIMING).

Three rule types (sw/testdata/fuzz_accept_rules.json + fuzz_accept_static.json):

  brkem_gap   (covers functional + timing) - the accepted "8080 gap". Applies
              iff the seed carries brkem_pos AND the first divergent row is at
              or after the chip CODE-fetch cycle that fetched the BRKEM opcode
              (a divergence BEFORE any BRKEM fetch is a real bug -> REJECT).
              Optional signature confirmation: the BRKEM entry bus signature
              (IVT 2xMEMR + 3xMEMW PSW/PS/PC push) upgrades the reason but is
              not required (positional evidence is sufficient).

  cadence_floor (covers timing ONLY - structurally cannot mask a functional
              bug, since the engine reaches the timing branch only when the
              functional/arch compare is already clean). Preconditions:
              waits>=1 or wrand. Aligns the retired CODE-fetch streams
              (timing_magnitude.faddr_resync greedy single-skip: mism==0, skip
              fraction <= spec_skip_frac_max per side), builds the offset series
              o_k, and accepts iff every step |o_k - o_{k-1}| <= max_step, every
              |o_k| <= slip_per_waited_fetch_max*waited_fetches(k) + 4 (and <=
              abs_slip_cap), and the first divergence is not before the first
              chip Tw. The rejection reason (code_mism / skip_frac / step_break@k
              / rate_break@k / pre_tw) rides the sub field so a floor-failing
              waited seed surfaces as a real TIMING.

  static_seed (covers functional + timing) - an exact/wildcard {key: "CLASS:
              reason (ledger ref)"} table, the known_divergences.json idiom.

RETIRED: `open_bus_escape` (2026-08-11, user ruling).  The rules file still
names it; the engine now SKIPS it and says so on stderr.  The tombstone above
`RETIRED_RULE_TYPES` states both defects (a false electrical story and a
tautological predicate).  Banked `open_bus` labels are NOT rewritten.
"""
import json
import sys
from bisect import bisect_right
from pathlib import Path

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
import fuzz_classify as fc                              # noqa: E402
from fuzz_classify import RuleHit, arch_dump            # noqa: E402

RULES_PATH = SW / "testdata" / "fuzz_accept_rules.json"
STATIC_PATH = SW / "testdata" / "fuzz_accept_static.json"


# ===========================================================================
# Shared fetch-alignment + cadence metrics (also used by calibrate_cadence).
# ===========================================================================
def _fetches(rows, window):
    return [(i, r["ad_addr"] & 0xFFFFF) for i, r in enumerate(rows[:window])
            if fc._tstate(r) == 1 and r["bs_early"] == 4]


def align_fetches(cf, kf):
    """Greedy single-skip alignment of the two retired CODE-fetch streams
    (mirrors timing_magnitude.faddr_resync:43, but also yields the aligned
    (chip_row, core_row) pairs and the per-side speculative-skip counts)."""
    ca = [a for _, a in cf]
    ka = [a for _, a in kf]
    ri = [r for r, _ in cf]
    ki = [r for r, _ in kf]
    i = j = mism = skc = skk = 0
    pairs = []
    while i < len(ca) and j < len(ka):
        if ca[i] == ka[j]:
            pairs.append((ri[i], ki[j]))
            i += 1
            j += 1
        elif i + 1 < len(ca) and ca[i + 1] == ka[j]:
            i += 1
            skc += 1
        elif j + 1 < len(ka) and ca[i] == ka[j + 1]:
            j += 1
            skk += 1
        else:
            mism += 1
            i += 1
            j += 1
    return pairs, mism, skc, skk, len(ca), len(ka)


def _waited_fetch_rows(rows, window):
    """Chip T1 rows of CODE fetches whose bus cycle carried >=1 Tw (t==4)."""
    out = []
    n = min(window, len(rows))
    i = 0
    while i < n:
        if fc._tstate(rows[i]) == 1 and rows[i]["bs_early"] == 4:
            for j in range(i + 1, min(i + 12, n)):
                t = fc._tstate(rows[j])
                if t == 4:
                    out.append(i)
                    break
                if t == 5:
                    break
        i += 1
    return out


def cadence_metrics(real, sim, dr, thr):
    """Compute the cadence-floor metrics for a waited divergent pair. Returns a
    dict of raw stats plus (ok, reason) evaluated against the thresholds `thr`.
    Pure + board-free so calibrate_cadence can share it in observe mode."""
    window = dr.n
    cf = _fetches(real, window)
    kf = _fetches(sim, window)
    pairs, mism, skc, skk, nca, nka = align_fetches(cf, kf)
    o = [c - k for c, k in pairs]
    if o:
        o = [x - o[0] for x in o]
    steps = [o[k] - o[k - 1] for k in range(1, len(o))]
    maxstep = max((abs(s) for s in steps), default=0)
    absmax_o = max((abs(x) for x in o), default=0)
    skfrac_c = skc / max(1, nca)
    skfrac_k = skk / max(1, nka)
    waited_rows = _waited_fetch_rows(real, window)
    waited_total = len(waited_rows)
    first_tw = next((i for i, r in enumerate(real[:window])
                     if fc._tstate(r) == 4), None)

    # per-aligned-index waited-fetch count (cumulative chip waits up to pair k)
    def waited_at(k):
        return bisect_right(waited_rows, pairs[k][0]) if k < len(pairs) else 0

    reason = None
    if mism > 0:
        reason = "code_mism"
    elif skfrac_c > thr["spec_skip_frac_max"] or skfrac_k > thr["spec_skip_frac_max"]:
        reason = "skip_frac"
    elif first_tw is not None and dr.first is not None and dr.first < first_tw:
        reason = "pre_tw"
    else:
        for k in range(1, len(o)):
            if abs(o[k] - o[k - 1]) > thr["max_step"]:
                reason = f"step_break@{k}"
                break
        if reason is None:
            for k in range(len(o)):
                cap = thr["slip_per_waited_fetch_max"] * waited_at(k) + 4
                if abs(o[k]) > min(cap, thr["abs_slip_cap"]):
                    reason = f"rate_break@{k}"
                    break
    worst_rate = max((abs(o[k]) / max(1, waited_at(k)) for k in range(len(o))),
                     default=0.0)
    return {"ok": reason is None, "reason": reason, "mism": mism,
            "skfrac_c": skfrac_c, "skfrac_k": skfrac_k, "maxstep": maxstep,
            "absmax_o": absmax_o, "final_o": o[-1] if o else 0,
            "nfetch": len(pairs), "waited_total": waited_total,
            "first_tw": first_tw, "worst_rate": worst_rate}


# ===========================================================================
# BRKEM 8080-gap positional evidence.
# ===========================================================================
def _brkem_fetch_row(real, window, brkem_linear):
    """T4 row of the chip CODE-fetch cycle whose T1 word address covers
    brkem_linear (addr <= linear < addr+2). None if never fetched."""
    n = min(window, len(real))
    i = 0
    while i < n:
        r = real[i]
        if fc._tstate(r) == 1 and r["bs_early"] == 4:
            a = r["ad_addr"] & 0xFFFFF
            if a <= brkem_linear < a + 2:
                for j in range(i, min(i + 12, n)):
                    if fc._tstate(real[j]) == 5:
                        return j
                return i
        i += 1
    return None


def _brkem_signature(real, window, fetch_row):
    """Optional confirmation: the BRKEM entry bus signature just after the
    fetch - IVT vector read (>=2 MEMR) then the 3 PSW/PS/PC pushes (>=3 MEMW).
    Returns True when both are present within a short window after the fetch."""
    memr = memw = 0
    n = min(window, len(real))
    for r in real[fetch_row:min(fetch_row + 60, n)]:
        if fc._tstate(r) == 1:
            if r["bs_early"] == 5:
                memr += 1
            elif r["bs_early"] == 6:
                memw += 1
    return memr >= 2 and memw >= 3


# ===========================================================================
# Rules.
# ===========================================================================
class BrkemGapRule:
    covers = ("functional", "timing")
    name = "brkem_gap"

    def __init__(self, cfg):
        self.cfg = cfg

    def apply(self, vctx):
        ctx = vctx["ctx"]
        if not ctx.brkem_pos:
            return None
        real = vctx["real"]
        dr = vctx["dr"]
        window = dr.n
        first_lin = min(lin for _, lin in ctx.brkem_pos)
        frow = _brkem_fetch_row(real, window, first_lin)
        if frow is None:
            # BRKEM never fetched in-window: it cannot explain the divergence
            return None
        fb = dr.first
        if fb is not None and fb < frow:
            # divergence BEFORE the BRKEM fetch -> a real bug; the rule refuses
            return None
        confirmed = _brkem_signature(real, window, frow)
        reason = (f"8080 entry at linear {first_lin:05x} (fetch row {frow}, "
                  f"first_bad {fb}); signature "
                  + ("confirmed" if confirmed else "positional-only"))
        return RuleHit(self.name, "8080-gap", reason, vctx["covers"])


class LeaMod3Rule:
    """Task #30 accepted class: the illegal LEA reg,reg (mod=11) loads the
    chip's stale EA latch, which our behavioural core cannot reproduce exactly
    across all preceding-instruction contexts (exact in moffs contexts, residue
    otherwise; cycle-rows always match). Accept iff the seed carries a lea-mod3
    at an executed position AND the arch-dump diff is CONFINED to that LEA's
    destination register (a strict fail-safe like brkem_gap: if ANYTHING else in
    the dump differs - the reg was used downstream, or a second divergence - the
    rule refuses and the seed surfaces)."""
    covers = ("functional",)
    name = "lea_mod3"

    def __init__(self, cfg):
        self.cfg = cfg

    def apply(self, vctx):
        ctx = vctx["ctx"]
        if not ctx.lea_mod3_pos:
            return None
        dr = vctx["dr"]
        window = dr.n
        if ctx.tier == "B":
            return self._apply_raw(vctx)     # raw: no arch_dump; stream confinement
        ar = arch_dump(vctx["real"], window)
        as_ = arch_dump(vctx["sim"], window)
        if ar is None or as_ is None:
            return None                     # need both full dumps to bound it
        diff = {k for k in ar if ar.get(k) != as_.get(k)}
        dests = {reg for _lin, reg in ctx.lea_mod3_pos}
        if diff and diff <= dests:
            return RuleHit(self.name, "lea-mod3",
                           f"illegal LEA-mod3 stale-EA latch; arch diff confined "
                           f"to dest reg(s) {sorted(diff)}", "functional")
        return None

    def _apply_raw(self, vctx):
        """Raw tier (task #31, k=6475): no arch_dump. Confinement comes from the
        CAPTURE shape. The illegal LEA mod=11 loads the stale EA latch into ONE
        register; that register may then be used both as a pushed VALUE and as a
        store ADDRESS, so store addresses can diverge - but the CONTROL FLOW and
        the NUMBER of stores stay identical (only the divergent register's
        derived data/addresses move). Accept iff (a) an executed LEA mod=11 is
        present (ctx.lea_mod3_pos, driver-recovered), (b) both legs have the
        IDENTICAL code-fetch stream (no control-flow divergence / escape),
        (c) the SAME store COUNT (a push-/store-count difference = a different
        mechanism, e.g. the ENTER nesting-mask class - refuse), and (d) the first
        divergence is AT/AFTER the LEA executes (positional fail-safe like
        brkem_gap - an earlier divergence is a different bug)."""
        ctx = vctx["ctx"]
        dr = vctx["dr"]
        real, sim = vctx["real"], vctx["sim"]

        def cfetch_rows(rows):
            return [(i, r["ad_addr"] & 0xFFFFF) for i, r in enumerate(rows)
                    if fc._tstate(r) == 1 and r["bs_early"] == 4]

        def stores(rows):
            return [tx for tx in fc.extract_txns(rows)
                    if fc.KIND[tx["kind"]] in ("MEMW", "IOW")]

        cfr, cfs = cfetch_rows(real), cfetch_rows(sim)
        cr, cs = [a for _, a in cfr], [a for _, a in cfs]
        n = min(len(cr), len(cs))
        if not (cr[:n] == cs[:n] and abs(len(cr) - len(cs)) <= 2):
            return None                      # (b) control flow diverges
        if len(stores(real)) != len(stores(sim)):
            return None                      # (c) store-count diff -> ENTER-like
        lea_lins = {lin for lin, _ in ctx.lea_mod3_pos}
        lea_rows = [i for i, a in cfr if a in lea_lins]
        if lea_rows and dr.first is not None and dr.first < min(lea_rows):
            return None                      # (d) divergence before the LEA
        dests = sorted({reg for _lin, reg in ctx.lea_mod3_pos})
        return RuleHit(self.name, "lea-mod3",
                       f"raw illegal LEA-mod3 stale-EA latch; identical code-fetch "
                       f"stream + equal store count, divergence at/after the LEA, "
                       f"confined to dest reg(s) {dests}", "functional")


def open_bus_escape_metrics(real, window):
    """The v1-era out-of-image CODE-fetch counter.  RETAINED, UNCHANGED, AND NO
    LONGER CARRYING AN ELECTRICAL CLAIM.

    Returns (escape_rows, n_out, first_out_row): the CODE T1 rows at linear
    >= 0x10000 whose `ad_data == ad_addr & 0xFFFF`, the total out-of-image code
    fetches, and the first out-of-image fetch row.

    ⚠ WHAT IT DOES **NOT** MEAN.  This used to be documented as an "open-bus
    escape signature" - out-of-image fetches reading address feedthrough because
    "nothing drives the multiplexed AD bus".  **THAT STORY IS FALSE ON THIS
    RIG.**  `hdl/rtl/test_mem.sv` decodes `addr[15:1]` and leaves `addr[19:16]`
    unconnected, so the 64K image is MIRRORED across the whole 1 MB space and
    every fetch, escaped or not, returns defined image bytes on BOTH legs.  And
    the `ad_data == ad_addr & 0xFFFF` test is the ADDRESS phase of a multiplexed
    bus, so it is a tautology on its own domain: it held on 140,741 of 140,741
    chip CODE T1 rows over all 725 retained FLASH #13 captures, 100.0000 %, zero
    counterexamples.  What the counter actually measures is therefore
    ">= N code fetches above 64 K", which under fuzz-v2's randomized segments is
    a statement about segment arithmetic.  (`fuzz_classify.escaped_code_region`;
    `docs/notes/fz2_corpus_prereg_2026-08-08.md` §38.2.)

    IT IS KEPT BECAUSE TWO REGISTERED POPULATIONS ARE DEFINED BY ITS EXACT
    COUNT, and re-opening them is a different piece of work from retiring a
    label: `timed_fuzz.excuse`'s `OPEN_BUS` exclusion over the four v1 banks,
    and the `ob_escape = {feed, out, frac}` field the capture path banks, which
    `wrfuzz_w2.open_bus` reads as the wrfuzz campaign's pre-registered
    exclusion.  The rows, the test and the count are unchanged; only the
    mechanism claim is withdrawn.

    THE V2 DIAGNOSTIC FOR "THIS PROGRAM LEFT ITS CODE REGION" IS
    `fuzz_classify.escaped_code_region` (`escaped` / `escaped_n`), which works
    in the PHYSICAL-OFFSET domain - the only one `test_mem.sv` decodes."""
    esc_rows = []
    n_out = 0
    first_out = None
    n = min(window, len(real))
    for i in range(n):
        r = real[i]
        if fc._tstate(r) == 1 and r["bs_early"] == 4:
            a = r["ad_addr"] & 0xFFFFF
            if a >= 0x10000:
                n_out += 1
                if first_out is None:
                    first_out = i
                if r["ad_data"] == (a & 0xFFFF):
                    esc_rows.append(i)
    return esc_rows, n_out, first_out


# ===========================================================================
# TOMBSTONE -- `OpenBusEscapeRule` / the `open_bus` acceptance class.
# RETIRED 2026-08-11 BY USER RULING, WITH ITS REASON STATED.
#
# It was a raw-tier (B) KNOWN_ACCEPTED rule: accept a divergence iff the chip
# capture showed >= 8 out-of-image CODE fetches reading `ad_data == addr &
# 0xFFFF` before the first divergent row.  TWO DEFECTS RETIRED IT, and they are
# named here rather than dropped silently:
#
#   (1) THE ELECTRICAL STORY WAS FALSE ON THIS RIG.  The rule's own reason
#       string said the board returns "open-bus address feedthrough" because
#       "nothing drives the multiplexed AD bus" out of image.  There is no open
#       bus here: `hdl/rtl/test_mem.sv` decodes `addr[15:1]` and leaves
#       `addr[19:16]` unconnected, so the 64K image is MIRRORED across the whole
#       1 MB space and every fetch, escaped or not, returns defined image bytes
#       on BOTH legs.  The rule's board-vs-TB note ("the BOARD feeds back the
#       address, the TB mirrors the image") described a difference that does not
#       exist.  Prereg §38.2(a); `fuzz_classify.escaped_code_region`.
#
#   (2) THE PREDICATE WAS A TAUTOLOGY, AND IT DID NOT DISCRIMINATE.
#       `ad_data == ad_addr & 0xFFFF` on a chip CODE T1 row is the ADDRESS phase
#       of a multiplexed bus: it held on 140,741 of 140,741 such rows over all
#       725 retained FLASH #13 captures, 100.0000 %, zero counterexamples.  The
#       rule therefore reduced to ">= 8 code fetches above 64 K", which under
#       fuzz-v2's randomized segments is segment arithmetic.  It fired on 243 of
#       251 NON-diverging raw seeds (96.8 %) -- a class covering 97 % of the
#       successes is not a failure class -- and across the 153 seeds it accepted
#       the first divergence was NEVER within 8 rows of the escape (min 147,
#       median 1,374, max 3,517).  Prereg §38.2(b)(c).
#
# THE CORRECT VOCABULARY IS `escaped`: `fuzz_classify.escaped_code_region`, the
# fuzz-v2 PHYSICAL-OFFSET containment diagnostic reported as `escaped` /
# `escaped_n` on every result line.  It is a diagnostic and never an exclusion.
#
# THIS COMPLETES TWO EARLIER RULINGS RATHER THAN OPENING A NEW ONE: amendment
# A-15 (prereg §38, user, 2026-08-09) already ruled that `open_bus` is "a
# description of a divergence, not a disposition of it", and explicitly left
# `sw/fuzz_accept.py` alone; the 2026-08-11 ruling finishes the job in the code.
#
# NOTHING BANKED IS REWRITTEN.  Banked `KNOWN_ACCEPTED/open_bus` verdicts, their
# `sub` strings and their `rule_hits` are historical record and stand exactly as
# captured (prereg §38.3).  `sw/fuzz_report.py` renders the banked label as
# `escaped (legacy label: open_bus)` so old data stays readable while the false
# name stops propagating.  `open_bus_escape_metrics` above is RETAINED with its
# behaviour unchanged -- see its docstring for the two registered populations
# that are defined by its exact count.
# ===========================================================================
RETIRED_RULE_TYPES = {
    "open_bus_escape":
        "retired 2026-08-11 by user ruling -- there is no open bus on this rig "
        "(test_mem.sv mirrors the image across the 1 MB space) and the rule's "
        "`ad_data == addr & 0xFFFF` test is the address phase of a multiplexed "
        "bus, true on 140,741 of 140,741 chip CODE T1 rows.  The fuzz-v2 "
        "vocabulary is `escaped` (fuzz_classify.escaped_code_region).  See the "
        "tombstone in sw/fuzz_accept.py.",
}

_ANNOUNCED = set()


def _announce_retired(rtype):
    """A config that still names a RETIRED rule type is SKIPPED LOUDLY.

    Announced on stderr, once per process, rather than raised: the rules file
    `sw/testdata/fuzz_accept_rules.json` is banked config that the retirement
    sitting deliberately did not edit, and EVERY consumer of
    `AcceptEngine.load()` -- `check_fuzz_bank`, `fuzz_bank`, `fuzz_campaign`,
    `sm3_sigctl`, `f7a_arbitrate`, `inv1_recapture` -- would die on a raise.
    What must not happen is a SILENT skip, and this is the thing that prevents
    it."""
    if rtype in _ANNOUNCED:
        return
    _ANNOUNCED.add(rtype)
    print(f"fuzz_accept: rule type {rtype!r} is RETIRED and is NOT loaded -- "
          f"{RETIRED_RULE_TYPES[rtype]}", file=sys.stderr)


class CadenceFloorRule:
    covers = ("timing",)
    name = "cadence_floor"

    def __init__(self, cfg):
        self.cfg = cfg
        self.thr = cfg["thresholds"]

    def apply(self, vctx):
        ctx = vctx["ctx"]
        if not (ctx.wrand or ctx.waits >= 1):
            return None
        m = cadence_metrics(vctx["real"], vctx["sim"], vctx["dr"], self.thr)
        if not m["ok"]:
            vctx["sub_out"] = f"cadence_reject:{m['reason']}"
            return None
        reason = (f"cadence floor: maxstep={m['maxstep']} |o|max={m['absmax_o']} "
                  f"waited={m['waited_total']} worst_rate={m['worst_rate']:.2f}")
        return RuleHit(self.name, "cadence", reason, "timing")


class StaticRule:
    covers = ("functional", "timing")
    name = "static_seed"

    def __init__(self, exact, wildcard):
        self.exact = exact          # {key: "CLASS: reason"}
        self.wildcard = wildcard    # [[prefix, "CLASS: reason"], ...]

    def _keys(self, ctx):
        ks = []
        if ctx.seed is not None:
            ks.append(str(ctx.seed))
            if ctx.tier is not None:
                ks.append(f"{ctx.tier}/{ctx.seed}")
            if ctx.cid is not None:
                ks.append(f"{ctx.cid}/{ctx.seed}")
        if ctx.cfg_hash is not None:
            ks.append(str(ctx.cfg_hash))
        return ks

    def apply(self, vctx):
        ctx = vctx["ctx"]
        for k in self._keys(ctx):
            if k in self.exact:
                return self._hit(self.exact[k], vctx["covers"])
        key0 = f"{ctx.tier}/{ctx.seed}" if ctx.seed is not None else ""
        for prefix, val in self.wildcard:
            if key0.startswith(prefix) or (ctx.seed is not None
                                           and str(ctx.seed).startswith(prefix)):
                return self._hit(val, vctx["covers"])
        return None

    @staticmethod
    def _hit(val, covers):
        klass, _, reason = val.partition(":")
        return RuleHit("static_seed", klass.strip(),
                       reason.strip() or "static", covers)


# ===========================================================================
# Engine.
# ===========================================================================
class AcceptEngine(fc.AcceptEngine):
    def __init__(self, rules, escalation, meta):
        self.rules = rules
        self.escalation = escalation
        self.meta = meta
        self.hits = {r.name: 0 for r in rules}

    @classmethod
    def load(cls, rules_path=RULES_PATH, static_path=STATIC_PATH):
        rdoc = json.loads(Path(rules_path).read_text())
        rules = []
        for r in rdoc["rules"]:
            if not r.get("enabled", True):
                continue
            if r["type"] == "brkem_gap":
                rules.append(BrkemGapRule(r))
            elif r["type"] == "lea_mod3":
                rules.append(LeaMod3Rule(r))
            elif r["type"] in RETIRED_RULE_TYPES:
                _announce_retired(r["type"])
            elif r["type"] == "cadence_floor":
                rules.append(CadenceFloorRule(r))
        sdoc = {}
        if static_path and Path(static_path).exists():
            sdoc = json.loads(Path(static_path).read_text())
        rules.append(StaticRule(sdoc.get("exact", {}),
                                sdoc.get("wildcard", [])))
        return cls(rules, rdoc.get("escalation", {}),
                   {"version": rdoc.get("version"),
                    "sigv": rdoc.get("sigv")})

    def consider(self, vctx):
        for rule in self.rules:
            if vctx["covers"] not in rule.covers:
                continue
            hit = rule.apply(vctx)
            if hit is not None:
                self.hits[rule.name] += 1
                return hit
        return None

    def zero_hit_rules(self):
        """Rules that never fired - flagged stale by the campaign rollup."""
        return [n for n, c in self.hits.items() if c == 0]


if __name__ == "__main__":
    eng = AcceptEngine.load()
    print(f"fuzz_accept: loaded {len(eng.rules)} rules "
          f"(v{eng.meta['version']}); escalation keys="
          f"{sorted(eng.escalation)}")
    for r in eng.rules:
        extra = ""
        if isinstance(r, CadenceFloorRule):
            extra = f"  thresholds={r.thr}"
        print(f"  {r.name:<14} covers={r.covers}{extra}")
