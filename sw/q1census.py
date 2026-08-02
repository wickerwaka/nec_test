#!/usr/bin/env python3
"""q1census -- the QUEUE-POP census, read straight out of a PER-CLOCK PIN ROW
STREAM (chip capture or timed-sim emission), the way `sw/qcensus.py` reads it
out of the v0.1 goldens.

This is the T4 handoff's item 2 instrument (ucsim_t_provenance 13.7): the w0
strides of 9.1 are exact and were measured on single-instruction goldens with
an injected queue; what has never been measured is the same march on a FREE
RUNNING program, and under waits.

Everything here comes from the row stream and nothing else:

  * every CODE cycle -> (T1 row, address, width, T4 row, the bytes it carries)
    -- the data phase is read at T3, low byte = even address, and a fetch at an
    odd address delivers only the upper byte;
  * a queue MODEL driven by the QS pins: `E` clears it, `F` pops the first byte
    of an instruction, `S` pops a subsequent one.  So every pop gets its BYTE
    and its ADDRESS for free, and the instruction boundaries are the `F`s;
  * `ready` for a popped byte = its deliverer's T4 row + 2 (M3: a fetch pushes
    at the end of its T4 and the byte is poppable two clocks later);
  * the BYTE ROLE from decoding the instruction the `F` started (qcensus.roles).

The census cell is the one 9.1 was fitted on, and it is fully observable:
with the PREVIOUS pop at clock 0, the pair `(ready, pop)`.  Under waits the
same cell is keyed additionally by the Tw of the cycle the pop rides.
"""
import argparse
import gzip
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

import qcensus                                       # noqa: E402

TI, T1, T2, T3, TW, T4 = 0, 1, 2, 3, 4, 5
CODE = 4
QS_NONE, QS_F, QS_E, QS_S = 0, 1, 2, 3


def _t(r):
    return r.get("t_state", r.get("t"))


def fetches(rows):
    """Every CODE cycle in the stream -> dict address -> (t4_index, byte).

    A cycle is [T1 .. T4]; the read data phase is T3 (and any Tw after it, but
    T3 is where every capture in this repo samples it).  A fetch at an EVEN
    address delivers both bytes of the word; at an ODD address only the upper.
    """
    out = {}
    i, n = 0, len(rows)
    while i < n:
        r = rows[i]
        if _t(r) != T1 or r["bs_early"] != CODE:
            i += 1
            continue
        addr = r["ad_addr"] & 0xFFFFF
        j, data = i + 1, None
        while j < n and _t(rows[j]) != T1:
            if _t(rows[j]) == T3:
                data = rows[j]["ad_data"] & 0xFFFF
            if _t(rows[j]) == T4:
                break
            j += 1
        if j >= n or _t(rows[j]) != T4 or data is None:
            i += 1
            continue
        t4 = j
        if addr & 1:
            out[addr] = (t4, (data >> 8) & 0xFF)
        else:
            out[addr] = (t4, data & 0xFF)
            out[addr + 1] = (t4, (data >> 8) & 0xFF)
        i = j + 1
    return out


def pops(rows, fetch_map):
    """The pop stream, driven by the QS pins.

    Returns a list of dicts, one per F/S row, in order:
      row      the clock index of the pop
      qs       'F' | 'S'
      addr     the byte's address (None if the queue model lost sync)
      byte     its value
      ready    the deliverer's T4 + 2 (None if that fetch is off the window)
      tw       the Tw count of the bus cycle this pop rides (0 if none/idle)
      tstate   the T-state of the row the pop lands on
      bs       the bus status of the cycle the pop lands on
    """
    # Queue contents as ADDRESSES, in delivery order.  A fetch's bytes join at
    # its T4; the model does not need the poppable delay to know WHICH byte a
    # pop takes, only the order.
    pend = []                       # (t4, addr) not yet joined
    for a, (t4, _b) in sorted(fetch_map.items()):
        pend.append((t4, a))
    pend.sort()
    q = []
    pi = 0
    out = []
    # per-row bus context
    ctx = bus_context(rows)
    for i, r in enumerate(rows):
        while pi < len(pend) and pend[pi][0] <= i:
            q.append(pend[pi][1])
            pi += 1
        qs = r["qs"]
        if qs == QS_E:
            q = []
            # a flush also drops every fetch already in flight: the next push
            # after it is the redirect's.  Anything still pending that was
            # issued BEFORE this clock is dead.
            while pi < len(pend) and pend[pi][0] <= i + 2:
                pi += 1
            out.append({"row": i, "qs": "E"})
            continue
        if qs in (QS_F, QS_S):
            addr = q.pop(0) if q else None
            t4b = fetch_map.get(addr)
            tw, ts, bs = ctx[i]
            out.append({"row": i, "qs": "F" if qs == QS_F else "S",
                        "addr": addr,
                        "byte": t4b[1] if t4b else None,
                        "ready": (t4b[0] + 2) if t4b else None,
                        "tw": tw, "tstate": ts, "bs": bs})
    return out


def bus_context(rows):
    """Per row: (tw_of_the_cycle_this_row_is_in, t_state, bs).  Idle rows get
    tw = -1 so they never masquerade as a zero-wait cycle."""
    n = len(rows)
    ctx = [(-1, TI, 7)] * n
    i = 0
    while i < n:
        if _t(rows[i]) != T1:
            ctx[i] = (-1, _t(rows[i]), rows[i]["bs_early"])
            i += 1
            continue
        j = i + 1
        tw = 0
        while j < n and _t(rows[j]) != T1:
            if _t(rows[j]) == TW:
                tw += 1
            if _t(rows[j]) == T4:
                j += 1
                break
            j += 1
        bs = rows[i]["bs_early"]
        for k in range(i, min(j, n)):
            ctx[k] = (tw, _t(rows[k]), bs)
        i = j
    return ctx


def roles_of(byts):
    return qcensus.roles(byts)


def annotate(pl, imgbytes=None):
    """Give every pop a ROLE by decoding each instruction the `F`s start.

    The byte values come from the stream itself, so no image is needed; a pop
    whose byte is unknown (deliverer off-window) breaks its instruction and
    every pop in it is rolled 'N'."""
    out = []
    i = 0
    n = len(pl)
    while i < n:
        p = pl[i]
        if p["qs"] == "E":
            out.append(dict(p, role="E"))
            i += 1
            continue
        if p["qs"] != "F":
            out.append(dict(p, role="N"))
            i += 1
            continue
        j = i + 1
        grp = [p]
        while j < n and pl[j]["qs"] == "S":
            grp.append(pl[j])
            j += 1
        byts = [g.get("byte") for g in grp]
        if any(b is None for b in byts):
            rl = ["N"] * len(grp)
        else:
            rl = roles_of(byts)
            rl += ["N"] * (len(grp) - len(rl))
        for g, rr in zip(grp, rl):
            out.append(dict(g, role=rr))
        i = j
    return out


def cells(ann, want_tw=False):
    """The 9.1 census cell: previous pop at clock 0, the pair (ready, pop),
    keyed by (role, prev_role).  Flushes reset the chain."""
    agg = defaultdict(Counter)
    prev = None
    prole = "-"
    for p in ann:
        if p["role"] == "E":
            prev, prole = None, "-"
            continue
        if p.get("ready") is None or p["role"] == "N":
            prev, prole = p["row"], p["role"]
            continue
        if prev is not None:
            key = (p["role"], prole) + ((p["tw"],) if want_tw else ())
            agg[key][(p["ready"] - prev, p["row"] - prev)] += 1
        prev, prole = p["row"], p["role"]
    return agg


# --------------------------------------------------------------------------- #
def load_rows(path):
    if str(path).endswith(".json.gz"):
        e = json.loads(gzip.decompress(Path(path).read_bytes()))
        return e["chip_rows"]
    return [json.loads(l) for l in Path(path).read_text().splitlines()
            if l.startswith("{") and '"t"' in l]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rows", nargs="+")
    ap.add_argument("--tw", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--dump", default="")
    args = ap.parse_args()

    agg = defaultdict(Counter)
    fh = open(args.dump, "w") if args.dump else None
    for p in args.rows:
        rows = load_rows(p)
        if args.limit:
            rows = rows[:args.limit]
        ann = annotate(pops(rows, fetches(rows)))
        if fh:
            fh.write(json.dumps({"path": str(p), "pops": ann}) + "\n")
        for k, c in cells(ann, args.tw).items():
            agg[k].update(c)
    if fh:
        fh.close()
    for k in sorted(agg, key=lambda k: (-sum(agg[k].values()), k)):
        tot = sum(agg[k].values())
        cs = ", ".join("rdy%+d->pop%+d x%d" % (a, b, n)
                       for (a, b), n in agg[k].most_common(args.top))
        print("%-24s n=%-6d %s" % (str(k), tot, cs))


if __name__ == "__main__":
    sys.exit(main() or 0)
