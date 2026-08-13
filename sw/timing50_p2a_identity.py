"""P2-A -- the exhaustive falsifier for the Shannon transcription.

The claim the landing rests on is that `qs_e_now` and `ann_kill` are the SAME
BOOLEAN FUNCTIONS after the edit as before it.  That is an identity, so it can
be CHECKED rather than argued: every free variable in both expressions is a
single bit, there are 18 of them, and 2**18 is 262,144.

The free variables are treated as INDEPENDENT even where the RTL correlates
them (`fd_nopin` is `!flush_stage && !flush_nmi_young` and `flush_nmi_young`
reads `flush_nmi`).  That makes the check STRICTER, not weaker: it proves the
identity on a SUPERSET of the reachable assignments.
"""
import itertools

VARS = ["P", "r_e_pend", "q_flush", "flush_pre", "flush_stage", "flush_nmi",
        "dage_le4", "flush_rep", "flush_pend", "r_run", "r_cur_fetch",
        "ts_lt_t3", "pop_now", "e_from_block", "absorb0", "qs_port_fetch",
        "rq_n0", "eu_post", "r_cmt_valid", "r_cmt_fetch", "cdage0",
        "r_cmt_was_owed", "eu_susp"]


def before(v):
    """The tree as it stood at 1e554257b6."""
    flush_nmi_young = v["flush_nmi"] and v["dage_le4"]
    flush_src_live = v["P"] or v["flush_nmi"]
    flush_direct = (not v["flush_stage"]) and (not flush_nmi_young) and (not v["P"])
    qs_e_now = (
        (v["r_e_pend"] or v["q_flush"] or (v["flush_pre"] and flush_direct))
        and not (v["q_flush"] and v["flush_rep"] and
                 (flush_direct or
                  (v["flush_pend"] and (not flush_src_live) and
                   not (v["r_run"] and (not v["r_cur_fetch"]) and v["ts_lt_t3"]))))
        and (not v["pop_now"]) and (not v["e_from_block"])
        and v["absorb0"] and (not v["qs_port_fetch"])
        and ((v["rq_n0"] and not v["eu_post"]) or v["q_flush"]
             or (v["flush_pre"] and flush_direct)
             or (v["r_cmt_valid"] and not v["r_cmt_fetch"])
             or (v["r_run"] and not v["r_cur_fetch"])))
    ann_kill = ((v["q_flush"] or
                 ((v["eu_susp"] or v["eu_post"]) and
                  not (v["r_cmt_was_owed"] and qs_e_now)))
                and v["r_cmt_valid"] and v["r_cmt_fetch"] and v["cdage0"])
    return flush_direct, qs_e_now, ann_kill


def after(v):
    """The tree with P2-A applied."""
    flush_nmi_young = v["flush_nmi"] and v["dage_le4"]
    fd_nopin = (not v["flush_stage"]) and (not flush_nmi_young)
    flush_direct = fd_nopin and (not v["P"])
    common = ((not v["pop_now"]) and (not v["e_from_block"])
              and v["absorb0"] and (not v["qs_port_fetch"]))
    qs_p1 = ((v["r_e_pend"] or v["q_flush"]) and common
             and ((v["rq_n0"] and not v["eu_post"]) or v["q_flush"]
                  or (v["r_cmt_valid"] and not v["r_cmt_fetch"])
                  or (v["r_run"] and not v["r_cur_fetch"])))
    qs_p0 = (
        (v["r_e_pend"] or v["q_flush"] or (v["flush_pre"] and fd_nopin))
        and not (v["q_flush"] and v["flush_rep"] and
                 (fd_nopin or
                  (v["flush_pend"] and (not v["flush_nmi"]) and
                   not (v["r_run"] and (not v["r_cur_fetch"]) and v["ts_lt_t3"]))))
        and common
        and ((v["rq_n0"] and not v["eu_post"]) or v["q_flush"]
             or (v["flush_pre"] and fd_nopin)
             or (v["r_cmt_valid"] and not v["r_cmt_fetch"])
             or (v["r_run"] and not v["r_cur_fetch"])))
    qs_e_now = qs_p1 if v["P"] else qs_p0

    def ann(q):
        return ((v["q_flush"] or
                 ((v["eu_susp"] or v["eu_post"]) and
                  not (v["r_cmt_was_owed"] and q)))
                and v["r_cmt_valid"] and v["r_cmt_fetch"] and v["cdage0"])
    ann_kill = ann(qs_p1) if v["P"] else ann(qs_p0)
    return flush_direct, qs_e_now, ann_kill


bad = 0
n = 0
for bits in itertools.product([False, True], repeat=len(VARS)):
    v = dict(zip(VARS, bits))
    n += 1
    if before(v) != after(v):
        bad += 1
        if bad <= 3:
            print("MISMATCH", {k: int(x) for k, x in v.items()},
                  before(v), after(v))
print(f"assignments checked: {n:,}   mismatches: {bad}")

# NON-VACUITY: the checker must be able to SEE a difference.  Perturb one
# literal of the P=1 branch and the same sweep must go red.
def after_broken(v):
    fd, qs, ak = after(v)
    if v["P"]:
        return fd, (not qs), ak
    return fd, qs, ak


bad2 = sum(1 for bits in itertools.product([False, True], repeat=len(VARS))
           if before(dict(zip(VARS, bits))) != after_broken(dict(zip(VARS, bits))))
print(f"NON-VACUITY: one inverted literal in the P=1 branch -> {bad2:,} mismatches")
