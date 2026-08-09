#!/usr/bin/env python3
"""fuzz_classify - verdict engine for the massive fuzz expansion (task #29).

Every A/B seed lands in exactly one bucket:
  SUCCESS / FUNCTIONAL / TIMING / KNOWN_ACCEPTED / QUARANTINE.

The module has four parts:

1. diff_rows() - a STRUCTURED refactor of check_seq.diff()'s per-cycle column
   policy (bs from row 8; t/ube/addr/data/nxta/ps from row 9; INTA-T1 address a
   documented don't-care; F<->S queue-status flicker tolerated + counted). It
   returns per-row mismatch records and does not print; check_seq.diff() is now
   a thin printing wrapper delegating here, so its external behaviour is
   byte-identical (proven by the standing gates re-run at the phase boundary).

2. The verdict decision tree classify() with strict precedence:
     0. QUARANTINE  - run error / short capture / provenance alarms
     1. functional evidence - transaction-stream compare (adapted
        extract_txns for chip t_state and TB t rows) + the tier-A arch dump
     2. cycle diff (diff_rows)
     3. verdict assembly with an AcceptEngine hook (the real rule engine is
        Phase 3 fuzz_accept.py; a NullEngine ships here).

3. Signature + EscalationPolicy for dedup/novelty and stop-the-campaign logic.

4. Drift metrics (the prefetch-rebuild feed) for waited divergent seeds.
"""
import hashlib
import sys
from collections import Counter, deque
from dataclasses import dataclass, field
from pathlib import Path

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
import fuzz_cov                                        # noqa: E402
from testimage import (OUT_PORT_DONE, OUT_PORT_REGS,   # noqa: E402
                       DONE_SENTINEL, MAGIC, STORE_ORDER,
                       CODE_LO, CODE_HI, RESERVED)

# column-name maps (identical to check_seq's, kept local so this module has no
# import cycle with check_seq, which delegates its diff() here)
T_NAME = {0: "Ti", 1: "T1", 2: "T2", 3: "T3", 4: "Tw", 5: "T4"}
BS_NAME = {0: "INTA", 1: "IOR", 2: "IOW", 3: "HALT",
           4: "CODE", 5: "MEMR", 6: "MEMW", 7: "PASV"}
QS_NAME = {0: "-", 1: "F", 2: "E", 3: "S"}
KIND = {0: "INTA", 1: "IOR", 2: "IOW", 3: "HALT",
        4: "CODE", 5: "MEMR", 6: "MEMW", 7: "PASV"}

SUCCESS, FUNCTIONAL, TIMING = "SUCCESS", "FUNCTIONAL", "TIMING"
KNOWN_ACCEPTED, QUARANTINE = "KNOWN_ACCEPTED", "QUARANTINE"
SIGV = "sig-v1"
MIN_ROWS = 16


def _tstate(r):
    """T-state, tolerant of both chip captures (t_state or t) and TB rows (t)."""
    return r.get("t_state", r.get("t"))


# ===========================================================================
# 1. Structured cycle diff (check_seq.diff refactor).
# ===========================================================================
@dataclass
class RowDiff:
    i: int
    qs_mm: bool
    qs_txt: str
    other: list
    flicker: bool


@dataclass
class DiffResult:
    n: int
    rows: list
    dend: int

    @property
    def bad(self):
        return sum(1 for r in self.rows if not r.flicker)

    @property
    def flick(self):
        return sum(1 for r in self.rows if r.flicker)

    @property
    def first(self):
        for r in self.rows:
            if not r.flicker:
                return r.i
        return None


def _done_idx(recs):
    """First done-marker IOW T1 (identical to check_seq.done_idx)."""
    for i, r in enumerate(recs):
        if _tstate(r) == 1 and r["bs_early"] == 2 and \
                (r["ad_addr"] & 0xFFFF) == OUT_PORT_DONE:
            return i
    return None


def escaped_code_region(recs, window):
    """The first CODE fetch that came from outside the two regions a v2 image
    ever executes from, as `(row, phys)`, or None.

    THE DOMAIN IS THE PHYSICAL OFFSET, because it is the only one that decodes:
    `hdl/rtl/test_mem.sv:47` decodes `addr[15:1]` and leaves `addr[19:16]`
    unconnected, so every address in the 1 MB space answers with mirrored image
    bytes.  THERE IS NO OPEN BUS ON THIS RIG.  The predicate this replaced
    tested `linear >= 0x10000 and ad_data == (linear & 0xFFFF)` on CODE T1 rows,
    where `ad_data == addr & 0xFFFF` holds by construction -- so it meant
    ">= 8 code fetches above 64 K", which under v2's randomized segments is
    normal and expected rather than evidence of anything.

    The two legitimate regions are the code region (body, handler table,
    terminator) and the loader page (the reset vector's far jump and the
    register-injection routine).  Nothing else in a v2 image is ever executed:
    every other byte of the code region is 0xCC, so an escape traps to INT3 and
    lands in the terminator at any alignment.

    IT IS A DIAGNOSTIC, AND IT IS NOT AN EXCLUSION.  It is reported on every
    result line as `escaped` / `escaped_n` (`fuzz_campaign.eval_case`) and it is
    never a reason to drop a seed from a population.

    ⚠ IT IS NO LONGER A PROVENANCE ALARM, and the reason is a MECHANISM.
    Amendment A-1 to `docs/notes/fz2_corpus_prereg_2026-08-08.md` (§11) removes
    it from `provenance_alarms` in BOTH tiers, completing erratum E-1's demotion
    -- E-1 had already ruled, in writing and before the capture, that the escape
    count "gates nothing", and only half of that landed.  The justification two
    paragraphs above ("every other byte of the code region is 0xCC, so an escape
    traps to INT3") is a SOUP-TIER property: the raw tier's whole-image mode is
    random bytes over 0x0000-0xFDFF with NO fill (prereg §5.2), so it executes
    outside [CODE_LO, CODE_HI) by design and this predicate is not written for
    it.  A raw seed that escapes AND fails to terminate is already caught by the
    terminator-reached bar; an escape on its own is a statement about the
    prefetch shadow.  Containment is measured as TERMINATOR-REACHED, which is
    E-1's predicate and the only one C-1 scores."""
    n = min(window, len(recs))
    for i in range(n):
        r = recs[i]
        if _tstate(r) == 1 and r["bs_early"] == 4:
            p = r["ad_addr"] & 0xFFFF
            if not (CODE_LO <= p < CODE_HI) and p not in RESERVED:
                return i, p
    return None


def diff_rows(real, sim, limit=4000, strict_qs=False, window=None):
    """Structured per-cycle diff. Returns a DiffResult carrying, in row order,
    one RowDiff for every row with any divergence. Column policy is byte-for-
    byte the historical check_seq.diff() policy.

    window: when None, the compare length is the done-shrunk historical window
    (min(len_real, len_sim, limit, dend+8)); when given (Tier B: never trust a
    possibly-forged done marker), the fixed min(len_real, len_sim, window)."""
    dend = _done_idx(real)
    if window is None:
        n = min(len(real), len(sim), limit,
                (dend + 8) if dend is not None else limit)
    else:
        n = min(len(real), len(sim), window)
    rows = []
    for i in range(n):
        r, s = real[i], sim[i]
        rt = r.get("t_state", r.get("t"))
        qs_mm = r["qs"] != s["qs"]
        other = []
        if i >= 8 and r["bs_early"] != s["bs_early"]:
            other.append(f"bs {BS_NAME[r['bs_early']]}!="
                         f"{BS_NAME[s['bs_early']]}")
        if i >= 9:
            if rt != s["t"]:
                other.append(f"t {T_NAME.get(rt)}!={T_NAME.get(s['t'])}")
            if r["ube_n"] != s["ube_n"]:
                other.append(f"ube {r['ube_n']}!={s['ube_n']}")
            active = r["bs_early"] != 7
            if rt == 1 and r["bs_early"] != 0 and \
                    r["ad_addr"] != s["ad_addr"]:
                other.append(f"addr {r['ad_addr']:05x}!={s['ad_addr']:05x}")
            if rt in (2, 3) and r["ad_data"] != s["ad_data"]:
                other.append(f"data {r['ad_data']:04x}!={s['ad_data']:04x}")
            if rt in (0, 5) and active and r["ad_data"] != s["ad_data"]:
                other.append(f"nxta {r['ad_data']:04x}!={s['ad_data']:04x}")
            if rt == 2 and active and r["ps"] != s["ps"]:
                other.append(f"ps {r['ps']:x}!={s['ps']:x}")
        qs_txt = (f"qs {QS_NAME[r['qs']]}!={QS_NAME[s['qs']]}"
                  if qs_mm else None)
        is_flicker = (qs_mm and not other and not strict_qs and
                      {r["qs"], s["qs"]} == {1, 3})
        if qs_mm or other:
            rows.append(RowDiff(i, qs_mm, qs_txt, other, is_flicker))
    return DiffResult(n, rows, dend)


# ===========================================================================
# 2. Functional evidence (transaction streams + arch dump).
# ===========================================================================
def extract_txns(recs):
    """Bus transactions via the FSM T-state annotations - an adaptation of
    v30run.extract_txns_large that indexes by enumerate (TB rows carry no
    'idx') and reads the T-state tolerantly (chip t_state / TB t)."""
    txns, cur = [], None
    for i, r in enumerate(recs):
        t = _tstate(r)
        if t == 1:
            cur = {"start": i, "kind": r["bs_early"], "addr": r["ad_addr"],
                   "data": None, "ube_n": r["ube_n"]}
        elif t in (3, 4) and cur:
            cur["data"] = r["ad_data"]
        elif t == 5 and cur:
            cur["end"] = i
            txns.append(cur)
            cur = None
    return txns


def func_stream(recs, window):
    """Ordered functional events over the window: writes carry (kind,addr,ube,
    data); reads carry (kind,addr,ube) - read DATA is an input, excluded; INTA
    is a bare position marker (address is a documented don't-care); CODE and
    PASV (prefetch speculation) are excluded from functional evidence."""
    ev = []
    for tx in extract_txns(recs):
        if tx["start"] >= window:
            break
        k = KIND[tx["kind"]]
        if k in ("MEMW", "IOW"):
            ev.append(("W", k, tx["addr"] & 0xFFFFF, tx["ube_n"], tx["data"]))
        elif k in ("MEMR", "IOR"):
            ev.append(("R", k, tx["addr"] & 0xFFFFF, tx["ube_n"]))
        elif k == "INTA":
            ev.append(("INTA",))
        elif k == "HALT":
            ev.append(("HALT",))
    return ev


@dataclass
class FuncResult:
    mismatch: bool
    first_kind: str
    first_pos: int
    truncated: bool
    detail: str


def compare_functional(real, sim, window):
    """Order-sensitive common-prefix compare of the two functional streams. A
    pure length delta (one side ran longer) is `truncated`, not evidence."""
    a = func_stream(real, window)
    b = func_stream(sim, window)
    m = min(len(a), len(b))
    for i in range(m):
        if a[i] != b[i]:
            return FuncResult(True, a[i][0], i, False, f"{a[i]}!={b[i]}")
    if len(a) != len(b):
        return FuncResult(False, None, None, True, f"len {len(a)}vs{len(b)}")
    return FuncResult(False, None, None, False, "")


def has_done(recs, window, sentinel_only=False):
    """(present, data) for the first done-marker IOW to 0xFC inside window.

    `sentinel_only` -- AMENDMENT A-10 (prereg §27), and it is `dump_words`'
    parameter under `dump_words`' rule: a done marker is `OUT OUT_PORT_DONE`
    CARRYING `DONE_SENTINEL`.  With it set, a non-sentinel write to the done
    port is not a done marker and is skipped, so the answer is "did the
    HARNESS'S store emit its marker", not "did anything write to port 0xFC".

    DEFAULT FALSE, so every historical caller means what it meant."""
    for tx in extract_txns(recs):
        if tx["start"] >= window:
            break
        if KIND[tx["kind"]] == "IOW" and (tx["addr"] & 0xFFFF) == OUT_PORT_DONE:
            if sentinel_only and tx["data"] != DONE_SENTINEL:
                continue
            return True, tx["data"]
    return False, None


MAGIC_AT = STORE_ORDER.index("MAGIC")


def dump_words(recs, window, sentinel_only=False):
    """The IOW-`OUT_PORT_REGS` data words written strictly BEFORE the first
    done marker (IOW-`OUT_PORT_DONE`), in order, or None when the window holds
    no done marker at all.

    DONE-RELATIVE, because the capture is not one run of the program: the board
    image RE-RUNS for as long as the capture lasts (`v30run.parse_result` bounds
    its search at the done marker for exactly this reason and the old
    `arch_dump` did not), and a terminator that is entered twice writes the
    register port twice.

    `sentinel_only` -- AMENDMENT A-6 (prereg §17), finding D-2.  A done marker
    is `OUT OUT_PORT_DONE` CARRYING `DONE_SENTINEL`; the harness store writes
    no other value, and `provenance_alarms` calls a non-sentinel one FORGED in
    its own words.  A raw-tier image is 64 K of random bytes and legitimately
    contains `OUT 0xFC, <junk>` -- `classify` says so out loud ("Tier B (raw)
    forges done markers with random data ... never trusts them") -- but THIS
    function trusted the first one whatever it carried, so a forged marker
    anywhere ahead of the terminator's dump truncated the word list and the
    arch column read None while a complete, correct 15-word dump sat in the
    rows behind it.  With `sentinel_only` a non-sentinel `OUT 0xFC` is not a
    boundary; it is not a register word either, so it is simply skipped.
    ONE predicate, no tier parameter -- the sentinel is the same in both.

    DEFAULT FALSE, so every historical caller means what it meant."""
    words, out = [], None
    for tx in extract_txns(recs):
        if tx["start"] >= window:
            break
        if KIND[tx["kind"]] != "IOW":
            continue
        port = tx["addr"] & 0xFFFF
        if port == OUT_PORT_DONE:
            if sentinel_only and tx["data"] != DONE_SENTINEL:
                continue
            out = words
            break
        if port == OUT_PORT_REGS:
            words.append(tx["data"])
    return out


def arch_dump(recs, window, sentinel_only=False):
    """The 15 STORE_ORDER registers of the LAST dump before the done marker,
    or None.

    ANCHORED, NOT POSITIONAL: the last `len(STORE_ORDER)` register words before
    the done marker must carry `MAGIC` at `MAGIC_AT`, or the run is not a dump
    and None is returned.  That makes a stray `OUT 0xFE` in the fuzz body
    harmless (it shifts the window, not the labels) instead of silently
    mislabelling every register, and it degrades to None rather than to a
    plausible wrong answer.

    PSW is now a word IN this run -- the terminator pops its own interrupt
    frame and emits IP/CS/FLAGS as ordinary port writes -- so the `MEMW @
    0xFFEC` channel and its re-run hazard are gone (plan D6).

    A dump the terminating NMI interrupted and restarted is NOT repaired here:
    the last run is returned and `dump_restarted()` reports it, because the
    restarted run's AW has already been clobbered by the first run's shuttle
    and the seed is the campaign's to DISCARD.

    `sentinel_only` is `dump_words`' (A-6 / D-2) and defaults False."""
    words = dump_words(recs, window, sentinel_only)
    if words is None or len(words) < len(STORE_ORDER):
        return None
    tail = words[-len(STORE_ORDER):]
    if tail[MAGIC_AT] != MAGIC:
        return None
    return dict(zip(STORE_ORDER, tail))


def dump_restarted(recs, window, sentinel_only=False):
    """True when more than one `MAGIC` anchor was written before the done
    marker: the terminating NMI landed mid-dump and the handler ran again.
    The second run's AW is the first run's shuttle value, so the dump is
    unrepairable and the seed must be DISCARDED, not fixed up.

    `sentinel_only` is `dump_words`' (A-6 / D-2) and defaults False."""
    words = dump_words(recs, window, sentinel_only)
    return words is not None and words.count(MAGIC) > 1


# ===========================================================================
# 0. Provenance alarms (mechanised QUARANTINE triggers).
# ===========================================================================
def provenance_alarms(real, sim, ctx, window):
    """Mechanised capture-integrity alarms - any hit means the capture cannot
    be trusted as evidence and the campaign must STOP to investigate:
      * a Tw row in a w0, non-wrand CHIP capture  (phantom sticky-WRAND wait)
      * BOTH legs write the SAME non-sentinel value to the done port and the
        harness's own `0xF00D` marker appears NOWHERE in either capture
                                                   (forged / corrupt store)
      * a reset asserted mid-window                (capture restarted).

    ⚠ `escaped_code_region` USED TO BE ON THIS LIST AND IS NOT ANY MORE.
    Amendment A-1 to `docs/notes/fz2_corpus_prereg_2026-08-08.md` (§11) removes
    it in BOTH tiers -- no soup/raw split, because a two-tier predicate would be
    a many-cased rule where a single demotion was already decided.  It completes
    erratum E-1, which had ruled BEFORE the capture that the escape count "gates
    nothing"; only the result-line half of that ruling had landed, so §2.4's
    "any provenance alarm still aborts" silently re-armed it and halted the
    census on its second seed.  The count is still measured and still reported
    (`escaped` / `escaped_n` on every result line); it is no longer an
    escalation.  See `escaped_code_region`'s own docstring for the mechanism.
    NOTHING ELSE IS DEMOTED: every alarm above is still a QUARANTINE and still a
    STOP."""
    alarms = []
    if ctx.real_is_chip and ctx.waits == 0 and not ctx.wrand:
        if any(_tstate(r) == 4 for r in real[:window]):
            alarms.append("tw_in_w0_chip")
    # A forged/corrupt done marker is a real alarm ONLY in Tier A (soup), where
    # the harness store must emit 0xF00D. Tier B (raw) legitimately forges done
    # markers with random data (a random OUT 0xFC), so the fixed-window verdict
    # never trusts them - not an integrity alarm there.
    #
    # SHARED-vs-ONE-SIDED discriminator (task #29 P7, mc1 k=9192): a genuine
    # corrupt store stub is DETERMINISTIC and SHARED across the chip and the
    # fabric core (same image, same stub), so BOTH legs emit the same wrong done
    # data. A ONE-SIDED (or mismatched) non-sentinel done write is a functional
    # DIVERGENCE, not a capture-integrity failure: k=9192 is a strict-soup
    # fall-through that wanders past the stub and OUTs junk (0x00c5) to port 0xFC
    # on the CHIP only (the core never reaches it). The normal classifier handles
    # that divergence; it must NOT hard-STOP the campaign as a forged store. So
    # fire the alarm only when both legs agree on a non-sentinel done value.
    # (The old "unless one leg got there via an open-bus escape" carve-out is
    # gone with the open-bus predicate.  It stayed gone through amendment A-1,
    # which took the escape OFF this list entirely: the carve-out existed to
    # decide WHICH of two alarms fired, and with only one of them left there is
    # nothing for it to arbitrate -- the shared-vs-one-sided discriminator below
    # is what separates a corrupt store from a divergence.)
    #
    # AMENDMENT A-10 (prereg §27) -- D-2's SENTINEL PREDICATE EXTENDS TO HERE.
    # §17.5 ruled that a done marker is one that CARRIES THE SENTINEL and gave
    # `dump_words` / `arch_dump` / `dump_restarted` the predicate; §17.6 says in
    # so many words that A-6 deliberately did not touch this function, and the
    # seed that forced the question (`fz2v/604011`, §26.2) was captured after.
    # The timing is stated in §27.0 and is not hidden here.
    #
    # THE MECHANISM: the terminator's tail is `MOV AW, 0xF00D` / `OUT 0xFC, AW`,
    # and a stimulus NMI can land on that ONE instruction boundary.  The seed's
    # own D8 modification handler then runs -- modifying registers is its entire
    # purpose -- and IRET returns INTO the `OUT`, so the store emits the
    # handler's AW.  The image re-runs, the terminating NMI fires, and the
    # second pass dumps cleanly with the true sentinel.  Nothing about the rig
    # or the part is wrong; the alarm's premise ("the harness store must emit
    # 0xF00D") predates D8 handlers and is what is wrong.
    #
    # THE PREDICATE, ONCE, UNIFORMLY: a done marker is `OUT 0xFC` carrying
    # `DONE_SENTINEL`.  So the question this clause asks is "did the HARNESS'S
    # done marker never appear AT ALL", and only then is a shared non-sentinel
    # write to the port evidence of a corrupt store.
    #
    # ⚠ WHY THIS IS NOT A DELETION.  Read literally -- "a non-sentinel OUT 0xFC
    # is not a done marker" applied to both reads below -- the clause becomes
    # VACUOUS: `has_done(..., sentinel_only=True)` can only ever return
    # `DONE_SENTINEL`, so `ddr != DONE_SENTINEL` is unreachable and the alarm
    # can never fire again.  An alarm that can no longer catch anything is a
    # deletion wearing an extension's clothes.  So the predicate is applied
    # where it decides EXISTENCE (the suppressing evidence) and the accusing
    # evidence -- the shared non-sentinel value, and the shared-vs-one-sided
    # discriminator below it -- is left exactly where it was.  A genuinely
    # corrupt store stub is deterministic and shared, so it corrupts BOTH legs
    # and NEITHER of them ever reaches the sentinel; that is still caught, and
    # `test_fuzz_classify` proves it still fires (§27.3).
    #
    # THE TWO WINDOWS ARE DIFFERENT ON PURPOSE, and this is D-1 (§17.4): the
    # capture is not one run of the program, and the SUPPRESSING evidence is
    # asked of the whole CAPTURE (the sentinel marker of 604011's second pass
    # sits at row 3406 of 4063, 2,267 rows past the comparison window), while
    # the ACCUSING read keeps the comparison `window` it has always had, so
    # this amendment cannot make the alarm fire anywhere it did not before.
    if ctx.tier == "A":
        sen_r, _ = has_done(real, len(real), sentinel_only=True)
        sen_s, _ = has_done(sim, len(sim), sentinel_only=True)
        pr, ddr = has_done(real, window)
        ps, dds = has_done(sim, window)
        both = pr and ps and ddr is not None and dds is not None
        if (not sen_r and not sen_s
                and both and ddr == dds and ddr != DONE_SENTINEL):
            alarms.append(f"done_data_both_{ddr:04x}")
    for tag, recs in (("real", real), ("sim", sim)):
        seen_run = False
        for r in recs[:window]:
            if r.get("rst", 0):
                if seen_run:
                    alarms.append(f"mid_rst_{tag}")
                    break
            else:
                seen_run = True
    return alarms


# ===========================================================================
# 3. Acceptance engine interface (Phase-3 fuzz_accept plugs in here).
# ===========================================================================
@dataclass
class RuleHit:
    rule: str
    klass: str          # the KNOWN_ACCEPTED subclass (8080-gap / cadence / ...)
    reason: str
    covers: str         # 'functional' | 'timing'


class AcceptEngine:
    """Contract: consider(vctx) returns a RuleHit that COVERS the divergence,
    or None. vctx is a dict carrying covers ('functional'|'timing'), ctx, the
    signature, sub-reason, and the raw evidence (real/sim/dr/func/drift)."""

    def consider(self, vctx):
        raise NotImplementedError


class NullEngine(AcceptEngine):
    """Phase-1/2 engine: accepts nothing (every divergence surfaces)."""

    def consider(self, vctx):
        return None


# ===========================================================================
# Context + Verdict.
# ===========================================================================
@dataclass
class Ctx:
    tier: str = "A"                 # 'A' (soup: arch dump) | 'B' (raw: window)
    waits: int = 0
    wrand: bool = False
    real_is_chip: bool = False
    strict_qs: bool = False
    run_error: str = None
    brkem_pos: list = field(default_factory=list)
    lea_mod3_pos: list = field(default_factory=list)  # (linear, dest_reg) task #30
    has_halt: bool = False
    with_drift: bool = False
    # identity (Phase-3 static-rule lookup keys; filled by the campaign driver)
    cid: str = None
    seed: str = None
    cfg_hash: str = None


@dataclass
class Verdict:
    verdict: str
    sub: str
    first_bad: int
    bad_rows: int
    flick: int
    n: int
    func_mismatch: bool
    truncated: bool
    done_real: bool
    done_sim: bool
    alarms: list
    rule_hits: list
    sig: str
    sigv: str
    drift: dict


def _quarantine(reason, sub, n=0):
    return Verdict(QUARANTINE, f"{reason}:{sub}", None, 0, 0, n, False, False,
                   False, False, [reason] if reason == "provenance_alarm" else [],
                   [], None, SIGV, None)


def classify(real, sim, ctx, engine=None):
    """Return a Verdict for a chip/TB (or TB/TB) row-pair under ctx."""
    engine = engine or NullEngine()

    if ctx.run_error:
        return _quarantine("run_error", ctx.run_error)
    if not real or not sim or len(real) < MIN_ROWS or len(sim) < MIN_ROWS:
        return _quarantine("run_error", "short_capture")

    # cycle diff (also fixes the compare window)
    if ctx.tier == "B":
        w = min(len(real), len(sim), 4000)
        dr = diff_rows(real, sim, strict_qs=ctx.strict_qs, window=w)
    else:
        dr = diff_rows(real, sim, strict_qs=ctx.strict_qs)
    window = dr.n

    # 0. provenance alarms (highest precedence)
    alarms = provenance_alarms(real, sim, ctx, window)
    if alarms:
        v = _quarantine("provenance_alarm", ",".join(alarms), window)
        v.alarms = alarms
        return v

    # 1. functional evidence
    done_real, _ = has_done(real, window)
    done_sim, _ = has_done(sim, window)
    func = compare_functional(real, sim, window)
    func_mismatch = False
    sub = ""
    # exactly-one-done is functional evidence ONLY in Tier A (soup), where the
    # harness store must reach the 0xF00D done marker. Tier B (raw) forges done
    # markers (a random OUT 0xFC) and never trusts done_idx (fixed window), so a
    # raw done_mismatch is NOT functional - fall through to the txn/cycle compare.
    if done_real != done_sim and ctx.tier == "A":
        func_mismatch = True
        sub = "done_mismatch"
    elif func.mismatch:
        func_mismatch = True
        sub = f"func:{func.first_kind}@{func.first_pos}"
    elif ctx.tier == "A" and done_real and done_sim:
        ar, as_ = arch_dump(real, window), arch_dump(sim, window)
        if ar and as_ and ar != as_:
            func_mismatch = True
            sub = "arch:" + ",".join(k for k in ar if ar.get(k) != as_.get(k))
    if not func_mismatch and not done_real and not done_sim:
        sub = "runaway_both" if ctx.tier == "A" else "window_truncated"

    sig = (_compute_sig(real, sim, dr, ctx, func)
           if (func_mismatch or dr.bad > 0) else None)
    drift = (drift_metrics(real, sim, ctx)
             if (ctx.with_drift and (ctx.wrand or ctx.waits > 0) and dr.bad > 0)
             else None)

    # 3. verdict assembly
    rule_hits = []
    if func_mismatch:
        hit = engine.consider(dict(covers="functional", ctx=ctx, sig=sig,
                                   sub=sub, brkem_pos=ctx.brkem_pos,
                                   done_real=done_real, done_sim=done_sim,
                                   real=real, sim=sim, dr=dr, func=func))
        if hit:
            rule_hits.append(hit)
            verdict, vsub = KNOWN_ACCEPTED, hit.klass
        else:
            verdict, vsub = FUNCTIONAL, (sub or "functional")
    elif dr.bad > 0:
        hit = engine.consider(dict(covers="timing", ctx=ctx, sig=sig, sub=sub,
                                   real=real, sim=sim, dr=dr, drift=drift))
        if hit:
            rule_hits.append(hit)
            verdict, vsub = KNOWN_ACCEPTED, hit.klass
        else:
            verdict, vsub = TIMING, "timing"
    else:
        verdict, vsub = SUCCESS, (sub or "clean")

    assert verdict != KNOWN_ACCEPTED or rule_hits, \
        "KNOWN_ACCEPTED without a rule hit is an engine-contract violation"

    return Verdict(verdict, vsub, dr.first, dr.bad, dr.flick, window,
                   func_mismatch, func.truncated, done_real, done_sim,
                   alarms, rule_hits, sig, SIGV, drift)


# ===========================================================================
# Signature (dedup / novelty).
# ===========================================================================
def _fetches(recs):
    return [(i, r["ad_addr"] & 0xFFFFF) for i, r in enumerate(recs)
            if _tstate(r) == 1 and r["bs_early"] == 4]


def _last_opsig(recs, fb):
    """decode_sig of the last CODE-fetch word retired before first_bad
    (best-effort reconstruction of the last-dispatched opcode)."""
    last = None
    for i in range(min(fb, len(recs))):
        r = recs[i]
        if _tstate(r) == 1 and r["bs_early"] == 4:
            last = i
    if last is None:
        return "?"
    data = None
    for j in range(last + 1, min(last + 8, len(recs))):
        if _tstate(recs[j]) in (3, 4):
            data = recs[j]["ad_data"]
        if _tstate(recs[j]) == 5:
            break
    if data is None:
        return "?"
    return fuzz_cov.decode_sig(bytes([data & 0xFF, (data >> 8) & 0xFF]))[1]


def _compute_sig(real, sim, dr, ctx, func):
    """sha1 over (sigv, tier, waits-class, both sides' (t,bs) at first_bad,
    mismatching column set, last-dispatched opsig, functional kind, slip
    direction). Addresses/rows/seeds are excluded so one mechanism == one
    signature."""
    fb = dr.first
    wc = "wrand" if ctx.wrand else f"w{ctx.waits}"
    if fb is not None:
        r, s = real[fb], sim[fb]
        rtb = (r.get("t_state", r.get("t")), r["bs_early"])
        stb = (s["t"], s["bs_early"])
        rd = next((x for x in dr.rows if x.i == fb), None)
        cols = tuple(sorted({c.split()[0] for c in (rd.other if rd else [])}
                            | ({"qs"} if rd and rd.qs_mm else set())))
        opsig = _last_opsig(real, fb)
    else:
        rtb = stb = (None, None)
        cols = ()
        opsig = "?"
    slip = (len(real) > len(sim)) - (len(real) < len(sim))
    fk = func.first_kind if func.mismatch else None
    parts = (SIGV, ctx.tier, wc, rtb, stb, cols, opsig, fk, slip)
    return hashlib.sha1(repr(parts).encode()).hexdigest()[:16]


# ===========================================================================
# 4. Drift metrics (prefetch-rebuild feed for waited divergent seeds).
# ===========================================================================
def drift_metrics(real, sim, ctx):
    """Per-fetch clock-offset series + slip events (with queue occupancy) for a
    waited divergent seed. Alignment identity via timing_magnitude.faddr_resync
    (imported lazily to avoid an import cycle through check_seq)."""
    from timing_magnitude import faddr_resync
    cf, kf = _fetches(real), _fetches(sim)
    n = min(len(cf), len(kf))
    off = [cf[i][0] - kf[i][0] for i in range(n)]
    if off:
        off = [o - off[0] for o in off]
    occ = fuzz_cov.qfill_at_dispatch(real)
    cps, prev = [], None
    for k, o in enumerate(off):
        if o != prev:
            cps.append((k, o))
            prev = o
        if len(cps) >= 256:
            break
    slips = []
    for k in range(1, n):
        d = off[k] - off[k - 1]
        if d != 0:
            slips.append({"fidx": k, "delta": d,
                          "occ": occ[k] if k < len(occ) else None})
        if len(slips) >= 256:
            break
    waited = sum(1 for r in real if _tstate(r) == 4)
    final = off[-1] if off else 0
    return {"faddr_ok": faddr_resync(cf, kf), "nfetch": n, "final": final,
            "waited_fetches": waited, "changepoints": cps, "slips": slips,
            "direction": "+" if final > 0 else ("-" if final < 0 else "0")}


# ===========================================================================
# EscalationPolicy (driver consults after every seed).
# ===========================================================================
DEFAULT_ESCALATION = {
    "stop_w0_functional": True,
    "stop_provenance": True,
    "stop_new_w0_timing_sig": True,
    "max_new_sigs": 25,
    "quarantine_rate": 0.02,
    "quarantine_window": 500,
    "per_sig_cap": 10,
}


class EscalationPolicy:
    """Consult after every seed; returns a list of (action, reason) tuples.
    STOP conditions (plan §Escalation): any un-ruled FUNCTIONAL at w0/no-wrand;
    any provenance alarm; first w0 TIMING with a NEW signature; more than
    max_new_sigs novel signatures/campaign; quarantine rate over threshold in
    the rolling window."""

    def __init__(self, rules=None):
        self.r = {**DEFAULT_ESCALATION, **(rules or {})}
        self.seen_sigs = set()
        self.new_sigs = 0
        self.sig_counts = Counter()
        self.qwindow = deque(maxlen=self.r["quarantine_window"])

    def consult(self, verdict, ctx):
        actions = []
        self.qwindow.append(verdict.verdict == QUARANTINE)
        w0 = (not ctx.wrand and ctx.waits == 0)

        if verdict.verdict == QUARANTINE and verdict.alarms and \
                self.r["stop_provenance"]:
            actions.append(("STOP", "provenance_alarm"))

        novel = verdict.sig is not None and verdict.sig not in self.seen_sigs
        if verdict.sig is not None:
            if novel:
                self.new_sigs += 1
            self.seen_sigs.add(verdict.sig)
            self.sig_counts[verdict.sig] += 1

        if verdict.verdict == FUNCTIONAL and w0 and not verdict.rule_hits and \
                self.r["stop_w0_functional"]:
            actions.append(("STOP", "w0_functional"))
        if verdict.verdict == TIMING and w0 and novel and \
                self.r["stop_new_w0_timing_sig"]:
            actions.append(("STOP", "new_w0_timing_sig"))
        if self.new_sigs > self.r["max_new_sigs"]:
            actions.append(("STOP", "too_many_new_sigs"))
        if len(self.qwindow) >= self.r["quarantine_window"]:
            rate = sum(self.qwindow) / len(self.qwindow)
            if rate > self.r["quarantine_rate"]:
                actions.append(("STOP", "quarantine_rate"))
        return actions


if __name__ == "__main__":
    print("fuzz_classify: verdict engine module - run sw/test_fuzz_classify.py")
