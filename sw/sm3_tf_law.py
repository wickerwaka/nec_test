#!/usr/bin/env python3
"""sm3_tf_law -- the BOARD-FREE discriminator for the BRK/TF single-step arm
(ucore_provenance sec.83.7, registered by SM3 sitting 22).

Every trap entry publishes its own return IP on the pads (the third push of the
entry frame), so the banked `chip_rows` of the 197 vector-1 seeds ALREADY
contain the readout of *which instruction boundary each trap was taken at*.
This tool turns that readout into instruction COUNTS by pairing it with the
architectural model's own per-instruction log (`ilog`), and answers the one
question sec.83.6 item 1 left open:

    when does a TF set by instruction X allow the FIRST trap, and does the
    handler's IRET get the same grace as the original setter?

It is engine-free on the chip side (structural entry detection in the raw
capture rows) and uses the architectural model ONLY as an instruction-boundary
ruler, never as an oracle: every quantity reported for the chip is derived from
`chip_rows`.

sec.83.4's scratch extractor read the pushed value back as `0` on 9 of 30 seeds
and reported them unreadable.  THAT WAS A TOOL DEFECT, not a population
property -- see `push_frame()`: an interrupt frame whose SP is ODD pushes each
word as TWO byte cycles, and a frame that straddles the capture window's end
has no T3/T4 data row for its last cycle.  Both are handled here.

Usage:
  sm3_tf_law.py --seeds mc2/1718,mc2/3061 [--json out.json] [--v]
  sm3_tf_law.py --pop v1reg            # the 145 REGISTERED vector-1 seeds
  sm3_tf_law.py --pop div29            # the 29 scored+divergent (needs --report)
"""

import argparse
import gzip
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

import simbin                                            # noqa: E402
import check_seq                                         # noqa: E402
import fuzz_campaign as fzc                              # noqa: E402
import fuzz_classify as fc                               # noqa: E402

SIM = simbin.SIM
ROM = ROOT / "docs" / "V20BITS.TXT"
BANK = ROOT / "tests" / "v30" / "fuzz_bank"

# sim/biu.h Txn::Kind
SIM_KIND = {0: "CODE", 1: "MEMR", 2: "MEMW", 3: "IOR", 4: "IOW", 5: "INTA",
            6: "HALT"}
LIMIT_ROWS = 4000

# The instructions that can LOAD the whole PSW, i.e. the only ones that can
# turn TF on without a hardware entry.  (An interrupt entry CLEARS it.)
POPF, IRET = 0x9D, 0xCF
# Every V30 prefix byte.  A prefix is a SEPARATE instruction boundary for
# interrupt recognition on this part -- which is not an assumption: the ROM
# carries the REPX withdrawal and the prefix-chain PC rewind (0223, 0225-0227)
# precisely because a request can be taken between a prefix and its opcode.
PREFIX = {0x26, 0x2E, 0x36, 0x3E, 0xF0, 0xF2, 0xF3, 0x64, 0x65}


def npfx(ins):
    """The number of leading PREFIX bytes of one `ilog` row's byte string."""
    n = 0
    for b in ins[3:]:
        if b in PREFIX:
            n += 1
        else:
            break
    return n


def opcode(ins):
    """The row's OPCODE byte, i.e. the first byte that is not a prefix."""
    b = ins[3 + npfx(ins):]
    return b[0] if isinstance(b, list) and b else \
        (ins[3 + npfx(ins)] if 3 + npfx(ins) < len(ins) else None)


# --------------------------------------------------------------------------- #
# seed plumbing (identical regeneration path to sw/ucsim_fuzz.py)
# --------------------------------------------------------------------------- #
def seed_path(sid):
    cid, k = sid.split("/")
    hits = sorted((BANK / cid / "seeds").glob(f"*_{k}_*.json.gz"))
    if len(hits) != 1:
        raise SystemExit(f"{sid}: {len(hits)} seed files")
    return hits[0]


def regen(entry):
    cfg = fzc.derive_case(entry["cid"], entry["k"], entry.get("ov") or {})
    g = fzc.build(cfg)
    image, meta = check_seq.compose(g)
    return image, g, hashlib.sha256(bytes(image)).hexdigest()


# --------------------------------------------------------------------------- #
# entry detection -- ONE definition, applied to both sides
# --------------------------------------------------------------------------- #
def push_frame(writes):
    """The three descending word pushes of an entry frame -> (psw, cs, ip).

    Read through the COMMITS, never through `data`.  A push is a word write;
    when SP is EVEN it is one 16-bit cycle, and when SP is ODD the V30 splits
    it into two byte cycles -- the low byte on the HIGH lane at the odd
    address, the high byte on the LOW lane at addr+1.  In the odd case the
    captured `ad_data` is therefore NOT the pushed word in either cycle (it is
    the AD pattern, whose other half is stale), and the word only exists once
    the two committed BYTES are put back together.

    THIS IS THE DEFECT sec.83.4 REPORTED AS `9 SEEDS UNREADABLE`.  Those seeds
    have an odd SP; their push trains are perfectly legible byte-wise, and read
    through `data` they yield values like 0x1d05 where the true push is 0x051d.
    The frames were never unreadable -- the extractor read the wrong quantity,
    and the population property it implied does not exist."""
    b = {}
    order = []
    for w in writes:
        for a, v in w["commits"]:
            if a not in b:
                order.append(a)
            b[a] = v
        if len(b) >= 6:
            break
    if len(b) < 6:
        return None
    lo = min(b)
    if sorted(b) != list(range(lo, lo + 6)):
        return None
    if order[0] < lo + 4:            # PSW is pushed FIRST, at the top
        return None
    w16 = lambda a: b[a] | (b[a + 1] << 8)          # noqa: E731
    return w16(lo + 4), w16(lo + 2), w16(lo)


def entries(txns, vec=1):
    """Every hardware/software interrupt ENTRY through vector `vec`, detected
    STRUCTURALLY: the vector word pair at 4V / 4V+2 and the three descending
    word pushes of the frame, in either order.  Returns a list of dicts with
    the transaction index of the vector read and the pushed (psw, cs, ip)."""
    va, vb = 4 * vec, 4 * vec + 2
    out = []
    n = len(txns)
    for i, t in enumerate(txns):
        if t["kind"] != "MEMR" or (t["addr"] & 0xFFFFF) != va:
            continue
        # the CS half must follow within a couple of cycles
        j = None
        for q in range(i + 1, min(i + 4, n)):
            if txns[q]["kind"] == "MEMR" and (txns[q]["addr"] & 0xFFFFF) == vb:
                j = q
                break
        if j is None:
            continue
        # The frame's three pushes FOLLOW the vector pair -- measured, on both
        # sides (sec.83.2's chip rows and the model's txn stream agree on the
        # order: MEMR 4, MEMR 4V+2, then the three descending word writes).
        wr = [t2 for t2 in txns[j + 1:j + 13] if t2["kind"] == "MEMW"]
        fr = push_frame(wr)
        if fr is None:
            out.append({"tx": i, "vtx": i, "psw": None, "cs": None,
                        "ip": None, "bad": "frame"})
            continue
        # sec.83.2's signature is FIVE parts, and the fifth is load-bearing:
        # the TRANSFER to the handler the vector just named.  Without it a
        # stray pair of reads at 4/6 inside the load stub, followed by any
        # three descending writes, counts as an entry -- which is how a seed
        # acquires 22 phantom entries whose pushed IPs are bus feedthrough.
        tgt = ((txns[j]["data"] & 0xFFFF) << 4) + (t["data"] & 0xFFFF)
        got = None
        for t2 in txns[j + 1:j + 20]:
            if t2["kind"] == "CODE":
                got = t2["addr"] & 0xFFFFF
                break
        if got is None or (got & ~1) != (tgt & ~1):
            out.append({"tx": i, "vtx": i, "psw": None, "cs": None,
                        "ip": None, "bad": f"no transfer {got}!={tgt}"})
            continue
        out.append({"tx": i, "vtx": i, "psw": fr[0], "cs": fr[1], "ip": fr[2]})
    return out


# --------------------------------------------------------------------------- #
# the two sides
# --------------------------------------------------------------------------- #
def chip_txns(entry):
    recs = entry["chip_rows"]
    dend = fc._done_idx(recs)
    n = min(len(recs), LIMIT_ROWS)
    if dend is not None:
        n = min(n, dend + 8)
    out = []
    for tx in fc.extract_txns(recs):
        if tx["start"] >= n:
            break
        k = fc.KIND[tx["kind"]]
        a, d, ube = tx["addr"] & 0xFFFFF, tx["data"], tx["ube_n"]
        # sw/ucsim_fuzz._commits, verbatim: the (address, byte) commits this
        # ONE bus cycle actually made, which is lane-exact.
        if d is None:
            cm = ()
        elif ube == 1:
            cm = ((a, d & 0xFF),)
        elif a & 1:
            cm = ((a, d >> 8),)
        else:
            cm = ((a, d & 0xFF), (a + 1, d >> 8))
        out.append({"kind": k, "addr": tx["addr"], "data": d, "ube_n": ube,
                    "start": tx["start"], "commits": cm})
    return out


def run_arch(image, fill, tf, max_ev, max_ins=20000):
    rec = {"i": 0, "fill": fill, "hex": bytes(image).hex(),
           "max_ev": max_ev, "max_ins": max_ins, "tf": 1 if tf else 0,
           "ilog": 1, "code": 1}
    p = subprocess.run([str(SIM), "image", str(ROM)],
                       input=json.dumps(rec, separators=(",", ":")).encode(),
                       stdout=subprocess.PIPE)
    for line in p.stdout.decode().splitlines():
        if line and '"coverage"' not in line:
            return json.loads(line)
    raise SystemExit("simulator produced no record")


def arch_txns(o):
    """[(kind, addr, data, ube_n, ev_before)] -- with the FUNCTIONAL event
    counter reconstructed exactly as sim/biu.cpp:45 advances it, so `ev_before`
    is directly comparable with the `ilog`'s ev0 column."""
    out, ev = [], 0
    for k, a20, a2, d, w in o["tx"]:
        kind = SIM_KIND[k]
        ube = 0 if w == 2 else 1
        # sw/ucsim_fuzz.sim_stream: the BIU logs a word access as ONE
        # transaction and `addr2` carries the second byte's address, because a
        # segment wrap sends it to the base of the segment rather than addr+1.
        cm = ((a20, d & 0xFF),) if w == 1 else \
             ((a20, d & 0xFF), (a2, d >> 8))
        out.append({"kind": kind, "addr": a20, "data": d, "ube_n": ube,
                    "ev": ev, "width": w, "commits": cm})
        if kind != "CODE":
            ev += 2 if (w == 2 and (a20 & 1)) else 1
    return out


def ins_index_of_ev(ilog, ev):
    """The index of the instruction that was RUNNING at functional event `ev`
    (ilog rows are [ev0, cs0, pc0, consumed bytes...], one per retired
    instruction, in order)."""
    lo, hi, best = 0, len(ilog) - 1, None
    while lo <= hi:
        mid = (lo + hi) // 2
        if ilog[mid][0] <= ev:
            best, lo = mid, mid + 1
        else:
            hi = mid - 1
    return best


def ins_index_of_ip(ilog, cs, ip, near=None):
    """The index of the instruction that STARTS at (cs, ip) -- i.e. the
    instruction a pushed return address points at.  With `near`, the match
    closest to that index is taken (the corpus loops)."""
    hits = [i for i, e in enumerate(ilog) if e[1] == cs and e[2] == ip]
    if not hits:
        return None
    if near is None:
        return hits[0]
    return min(hits, key=lambda i: abs(i - near))


# --------------------------------------------------------------------------- #
def analyse(sid, verbose=False):
    entry = json.loads(gzip.decompress(seed_path(sid).read_bytes()))
    image, g, sha = regen(entry)
    if sha != entry["image_sha256"]:
        return {"seed": sid, "err": "GEN_DRIFT"}
    fill = g.get("fill", 0x90)

    def split(all_e):
        good = [e for e in all_e if e["ip"] is not None]
        bad = [e for e in all_e if e["ip"] is None]
        interior = sum(1 for e in bad
                       if good and good[0]["tx"] < e["tx"] < good[-1]["tx"])
        return good, len(bad), interior

    ct = chip_txns(entry)
    cfun = sum(1 for t in ct if t["kind"] != "CODE")
    ce, c_rej, c_int = split(entries(ct))

    o1 = run_arch(image, fill, True, cfun + 512)
    at1 = arch_txns(o1)
    ae1, a_rej, a_int = split(entries(at1))
    ilog1 = o1.get("ilog") or []

    o0 = run_arch(image, fill, False, cfun + 512)
    at0 = arch_txns(o0)
    ilog0 = o0.get("ilog") or []

    res = {"seed": sid, "chip_entries": len(ce), "arch_tf1_entries": len(ae1),
           "arch_tf0_entries": len(split(entries(at0))[0]),
           "rejects_chip": c_rej, "interior_rejects_chip": c_int,
           "rejects_arch": a_rej, "interior_rejects_arch": a_int,
           "chip_ip": [e["ip"] for e in ce],
           "arch_ip": [e["ip"] for e in ae1],
           "unreadable_chip": sum(1 for e in ce if e["ip"] is None),
           "unreadable_arch": sum(1 for e in ae1 if e["ip"] is None),
           "err_tf1": o1.get("err"), "err_tf0": o0.get("err")}

    # ---- (1) the prefix relation, sec.83.4 restated on readable data ------- #
    # GRACE CONVENTION, used identically everywhere below:
    #   S = index of the instruction that SET TF,
    #   T = index of the instruction whose retirement the trap was taken at,
    #   grace = T - S - 1 = the number of instructions that ran between the
    #           setter and the trapping instruction WITHOUT trapping.
    # The 8086/V30 textbook rule ("TF sampled at the start of the instruction")
    # is grace 0: the setter does not trap, the very next instruction does.
    ci = [e["ip"] for e in ce]
    ai = [e["ip"] for e in ae1]
    rel, m_match = "n/a", 0
    if ci and ai:
        n_id = 0
        while n_id < min(len(ci), len(ai)) and ci[n_id] == ai[n_id]:
            n_id += 1
        n_sh = 0
        while n_sh < min(len(ci), len(ai) - 1) and ci[n_sh] == ai[n_sh + 1]:
            n_sh += 1
        if n_sh > n_id:
            rel, m_match = "shift1", n_sh
        elif n_id:
            rel, m_match = "identical", n_id
        else:
            rel, m_match = "other", 0
        if rel == "shift1" and n_sh < min(len(ci), len(ai) - 1):
            rel = f"shift1({n_sh}/{len(ci)})"
        if rel == "identical" and n_id < min(len(ci), len(ai)):
            rel = f"identical({n_id}/{len(ci)})"
    res["prefix"] = rel
    res["match_len"] = m_match

    # ---- (2) THE HEAD: the setter, and the grace the CHIP granted --------- #
    # The chip's FIRST trap pushes (cs, ip).  With traps DISABLED the model
    # runs the same instruction stream up to that point (nothing has forked
    # yet), so its ilog is a valid ruler for counting instructions between the
    # setter and that boundary.  The setter is found FIRST, so the ambiguity of
    # a looping corpus is resolved by proximity to it, not by taking hit[0].
    # The head setter is the FIRST PSW load that turns TF on -- before it TF is
    # off (the seed's injected PSW is checked separately), so there is no
    # ambiguity to resolve and no `near` heuristic anywhere in the measurement.
    def head_chip(ilog, txns, ent):
        """The CHIP's head, from the chip's own pushed IP, ruled by a model run
        with traps DISABLED (which therefore contains no handler IRET to be
        confused with the setter)."""
        if not ent or ent[0]["ip"] is None:
            return {}
        ss = setters(ilog, txns)
        if not ss:
            return {"setter_ins": None, "why": "no PSW load sets TF"}
        s = ss[0]
        hits = [i for i, e in enumerate(ilog)
                if i > s["setter_ins"] and e[1] == ent[0]["cs"]
                and e[2] == ent[0]["ip"]]
        if not hits:
            return dict(s, trap_at_ins=None,
                        why="chip return IP is not a boundary of the tf=0 run")
        return dict(s, trap_at_ins=hits[0] - 1,
                    grace=(hits[0] - 1) - s["setter_ins"] - 1,
                    n_setters_before=0)

    def score(ilog, ent):
        """PREDICTED vs OBSERVED, on the chip's own first pushed (cs, ip)."""
        if not ent or ent[0]["ip"] is None:
            return {"verdict": "NO_CHIP_ENTRY"}
        ss = setters(ilog, at0)
        if not ss:
            return {"verdict": "NO_SETTER"}
        s = ss[0]
        pr = predict_head(ilog, s["setter_ins"], s["setter_op"])
        if pr is None:
            return {"verdict": "RULER_SHORT"}
        cs, ip, where, corollary = pr
        ok = (cs == ent[0]["cs"] and ip == ent[0]["ip"])
        return {"verdict": "HIT" if ok else "MISS",
                "pred": [cs, ip], "obs": [ent[0]["cs"], ent[0]["ip"]],
                "at": where, "corollary": corollary,
                "setter_op": s["setter_op"],
                "npfx_next": npfx(ilog[s["setter_ins"] + 1])
                if s["setter_ins"] + 1 < len(ilog) else None}

    def head_arch(ilog, txns, ent):
        """The MODEL's head.  Its trapping instruction is read from the entry's
        own position in the event stream, so no IP search is involved."""
        if not ent:
            return {}
        t = ins_index_of_ev(ilog, txns[ent[0]["vtx"]]["ev"])
        ss = setters(ilog, txns)
        if not ss or t is None:
            return {"setter_ins": None, "trap_at_ins": t}
        s = ss[0]
        return dict(s, trap_at_ins=t, grace=t - s["setter_ins"] - 1)

    res["head"] = head_chip(ilog0, at0, ce)
    res["law"] = score(ilog0, ce)
    res["arch_head"] = head_arch(ilog1, at1, ae1)

    # ---- (3) THE STORM: the grace an IRET gets ---------------------------- #
    # Measured in the tf=1 model, restricted to the prefix over which the
    # model's pushed-IP sequence IS the chip's (relation above), so every
    # cadence counted is one silicon also took.
    lim = m_match + 1 if rel.startswith("shift1") else m_match
    res["storm"] = storm_cadence(ilog1, at1, ae1[:max(lim, 0)])
    res["handler_op"] = handler_op(at1, ae1)
    if verbose:
        res["_ce"] = ce[:6]
        res["_ae"] = ae1[:6]
    return res


def setter_before(ilog, txns, ti):
    """Walk back from (and including) instruction `ti` for the last instruction
    that LOADED the PSW with TF SET -- POPF (one word read) or IRET (three).
    The loaded value is read out of the model's own bus stream, so this names
    the ARM without the model having to expose PSW.  An entry that is NOT
    preceded by such an instruction is not a trap (the software-INT control),
    and that is reported as `setter_ins: None`, never guessed at."""
    for i in range(ti, -1, -1):
        if i >= len(ilog):
            continue
        e = ilog[i]
        op = e[3] if len(e) > 3 else None
        if op not in (POPF, IRET):
            continue
        ev0 = e[0]
        ev1 = ilog[i + 1][0] if i + 1 < len(ilog) else 1 << 62
        rd = [t for t in txns if t["kind"] == "MEMR" and ev0 <= t["ev"] < ev1]
        if not rd:
            continue
        val = rd[0]["data"] if op == POPF else (rd[2]["data"]
                                               if len(rd) > 2 else None)
        if val is None or not (val & 0x100):
            continue                      # a PSW load that did not set TF
        return {"setter_ins": i, "setter_op": op, "setter_psw": val,
                "setter_tf": True}
    return {"setter_ins": None}


def setters(ilog, txns):
    """Every instruction that LOADED the PSW with TF set, in order: POPF (one
    word read) or IRET (three).  The loaded value is read out of the bus
    stream, so the ARM is named without the model having to expose PSW."""
    out = []
    for i, e in enumerate(ilog):
        # THE OPCODE, NOT THE FIRST BYTE.  `2e cf` is a CS-prefixed IRET and it
        # arms the trap exactly as a bare one does; reading e[3] misses it and
        # sends the head measurement to the next PSW load hundreds of
        # instructions downstream (t30-raw/768).
        op = opcode(e) if len(e) > 3 else None
        if op not in (POPF, IRET):
            continue
        ev0 = e[0]
        ev1 = ilog[i + 1][0] if i + 1 < len(ilog) else 1 << 62
        rd = [t for t in txns if t["kind"] == "MEMR" and ev0 <= t["ev"] < ev1]
        if not rd:
            continue
        val = rd[0]["data"] if op == POPF else (rd[2]["data"]
                                               if len(rd) > 2 else None)
        if val is None or not (val & 0x100):
            continue
        out.append({"setter_ins": i, "setter_op": op, "setter_psw": val})
    return out


def predict_head(ilog, S, op):
    """THE LAW, as a PREDICTION of the (cs, ip) the chip's FIRST trap must push.

        There is ONE arm bit.  At every instruction boundary -- and a PREFIX is
        an instruction boundary -- the machine first TAKES the trap if the arm
        bit is set (clearing it), and then SAMPLES TF into the arm bit.
        IRET's PSW write lands BEFORE its own boundary's sample; POPF's lands
        AFTER it.

    So the trap is taken at the FIRST boundary after an IRET setter's own
    boundary, and at the SECOND after a POPF setter's.  Returns
    (cs, ip, boundary_description) or None when the ruler runs out.

    The `p >= 2` (POPF) and `p >= 1` (IRET) branches land the trap INSIDE a
    prefix chain, where the ROM's own withdrawal rewinds the saved IP over the
    whole chain (0225-0227), so the pushed IP is the chain's first byte.  Those
    branches are COROLLARIES: they are stated because the law states them, and
    they are marked so that a run in which no seed exercises them cannot be
    reported as having confirmed them."""
    k = 2 if op == POPF else 1            # boundaries to consume after b0
    i, corollary = S + 1, False
    while k > 0:
        if i >= len(ilog):
            return None
        p = npfx(ilog[i])
        if p >= k:                        # the k-th boundary is INSIDE the
            corollary = True              # prefix chain of instruction i
            return ilog[i][1], ilog[i][2], f"mid-prefix of ins {i}", corollary
        k -= p + 1                        # p prefix boundaries + the opcode's
        i += 1
    return (ilog[i][1], ilog[i][2], f"end of ins {i - 1}", corollary) \
        if i < len(ilog) else None


def handler_op(txns, ae):
    """The first opcode byte the handler executes, read out of the model's own
    CODE fetches at the vector target -- so the corpus's `handler` is NAMED and
    not assumed."""
    if not ae:
        return None
    v = ae[0]["vtx"]
    tgt = txns[v]["data"]
    for t in txns[v:v + 20]:
        if t["kind"] == "CODE" and (t["addr"] & 0xFFFF) == (tgt & 0xFFFF):
            return t["data"] & 0xFF
    return None


def storm_cadence(ilog, txns, ae):
    """For each consecutive pair of model traps: the instruction index of the
    handler's IRET (the RE-ARM) and of the instruction the NEXT trap was taken
    at, so the grace an IRET-armed TF gets is a measured integer in the SAME
    convention as the head."""
    out = []
    for n in range(len(ae) - 1):
        a, b = ae[n], ae[n + 1]
        if a["ip"] is None or b["ip"] is None:
            continue
        # the entry's own bus cycles run AFTER the trapping instruction retired
        # and BEFORE the next ilog row is opened, so this index IS T.
        ia = ins_index_of_ev(ilog, txns[a["vtx"]]["ev"])
        ib = ins_index_of_ev(ilog, txns[b["vtx"]]["ev"])
        if ia is None or ib is None or ib <= ia:
            continue
        iret = None
        for i in range(ib, ia, -1):
            if len(ilog[i]) > 3 and opcode(ilog[i]) == IRET:
                iret = i
                break
        if iret is None or iret >= ib:
            continue
        out.append({"iret_ins": iret, "trap_ins": ib,
                    "grace": ib - iret - 1})
    return out


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="")
    ap.add_argument("--seedfile", default="")
    ap.add_argument("--json", default="")
    ap.add_argument("--v", action="store_true")
    a = ap.parse_args()
    sids = [s for s in a.seeds.split(",") if s]
    if a.seedfile:
        sids += [l.strip() for l in Path(a.seedfile).read_text().splitlines()
                 if l.strip()]
    rows = []
    for sid in sids:
        try:
            r = analyse(sid, a.v)
        except Exception as e:                              # noqa: BLE001
            r = {"seed": sid, "err": f"{type(e).__name__}: {e}"}
        rows.append(r)
        print(json.dumps(r, separators=(",", ":"))[:600])
    print("== rollup", len(rows), "seeds")
    print("prefix:", Counter(r.get("prefix") for r in rows))
    print("CHIP head grace:", Counter(r.get("head", {}).get("grace")
                                     for r in rows))
    print("ARCH head grace:", Counter(r.get("arch_head", {}).get("grace")
                                     for r in rows))
    print("head setter op:",
          Counter(r.get("head", {}).get("setter_op") for r in rows))
    print("handler op:", Counter(r.get("handler_op") for r in rows))
    print("LAW verdict:", Counter(r.get("law", {}).get("verdict")
                                  for r in rows))
    print("LAW by (setter, npfx next):",
          Counter((hex(r["law"]["setter_op"]), r["law"]["npfx_next"],
                   r["law"]["verdict"])
                  for r in rows if r.get("law", {}).get("setter_op")))
    print("LAW corollary branches exercised:",
          sum(1 for r in rows if r.get("law", {}).get("corollary")))
    st = Counter()
    for r in rows:
        for s in r.get("storm", []):
            st[s["grace"]] += 1
    print("storm grace:", st)
    print("rejected 4/6 pairs (chip):",
          sum(r.get("rejects_chip", 0) or 0 for r in rows),
          "of which INTERIOR:",
          sum(r.get("interior_rejects_chip", 0) or 0 for r in rows))
    print("rejected 4/6 pairs (arch):",
          sum(r.get("rejects_arch", 0) or 0 for r in rows),
          "of which INTERIOR:",
          sum(r.get("interior_rejects_arch", 0) or 0 for r in rows))
    if a.json:
        Path(a.json).write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
