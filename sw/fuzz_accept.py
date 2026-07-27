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
"""
import json
import sys
from bisect import bisect_right
from pathlib import Path

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
import fuzz_classify as fc                              # noqa: E402
from fuzz_classify import RuleHit                       # noqa: E402

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
