#!/usr/bin/env python3
"""qcensus -- the QUEUE-POP census, read straight out of the GOLDEN rows.

For every golden case this reconstructs, from the golden's own row stream and
nothing else:

  * every queue POP (row index, QS code F/S, byte value)
  * the READY clock of the byte it took -- the T4 row of the CODE cycle that
    delivered it, plus 2 (M3: a fetch pushes at the end of its T4 and the byte
    is poppable two clocks later).

Pops are sequential in memory, so pop k carries the byte at phys(cs,ip)+k and
its deliverer is the CODE cycle whose address range covers it (word fetch at
an even address, single upper byte at an odd one).  Fetch addresses come from
the T1 rows; the cycle straddling the window edge is extrapolated backwards
(back-to-back CODE: addr-2, T4-4), which is exactly the queue-empty priming
regime.  A case whose byte addresses are not fully covered is SKIPPED and
counted, never guessed at.

With `ready` known to the clock, `pop - ready` separates "the byte was late"
from "the decoder was late" -- which is the whole question the decoder's
byte-demand schedule (provenance 7.6) is standing in for.
"""

import argparse
import gzip
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))

import timed_gate                      # noqa: E402
import optable                         # noqa: E402

PREFIX = {0x26, 0x2E, 0x36, 0x3E, 0xF0, 0xF2, 0xF3, 0x64, 0x65}
# the 0F page's ModR/M blocks (pla3_check.EXT_BLOCKS columns 5/1)
EXT_MODRM = set(range(0x10, 0x20)) | set(range(0x28, 0x40))


def _has_modrm(op, ext):
    if ext:
        return op in EXT_MODRM
    o = optable.TABLE.get(op)
    return bool(o and o.modrm)


def fetch_list(rows):
    """CODE cycles as (t4_row, addr, nbytes), extrapolated back over the
    window edge.  -> list sorted by address."""
    fs = []
    for i, r in enumerate(rows):
        if r[8] == "T1" and r[7] == "CODE":
            addr = r[1] & 0xFFFFF
            fs.append((i + 3, addr, 1 if (addr & 1) else 2))
    if not fs:
        return fs
    t4, a, _ = fs[0]
    # back-to-back CODE across the window edge: the previous fetch's T4 is one
    # clock before this one's T1 (= t4-4), at addr-2.
    for j in range(1, 5):
        pa = a - 2 * j
        if pa < 0:
            break
        fs.append((t4 - 4 * j, pa, 2))
    return sorted(fs, key=lambda x: x[1])


def roles(byts):
    """Byte roles for the case instruction: 'P' prefix, 'O' opcode,
    'E' 0F-escape second byte, 'M' modrm, 'D' displacement, 'I' immediate."""
    out = []
    i = 0
    ext = False
    while i < len(byts) and byts[i] in PREFIX:
        out.append("P")
        i += 1
    if i < len(byts) and byts[i] == 0x0F:
        out.append("O")
        i += 1
        ext = True
        if i < len(byts):
            out.append("E")
            i += 1
    elif i < len(byts):
        out.append("O")
        i += 1
    op = byts[i - 1] if i else 0
    # the rest: modrm (per the PLA's own table) then disp then imm
    if i < len(byts) and _has_modrm(op, ext):
        mod = byts[i] >> 6
        rm = byts[i] & 7
        out.append("M%d" % mod)
        i += 1
        nd = 0
        if mod == 1:
            nd = 1
        elif mod == 2:
            nd = 2
        elif mod == 0 and rm == 6:
            nd = 2
        for j in range(min(nd, len(byts) - i)):
            out.append("D8" if nd == 1 else ("Dl" if j == 0 else "Dh"))
            i += 1
    j = 0
    while i < len(byts):
        out.append("I%d" % j)
        i += 1
        j += 1
    return out


def census_case(c):
    """-> ([(k, role, qs, ready, row)], ok)"""
    rows = c["cycles"]
    pops = [(i, r[9], r[10]) for i, r in enumerate(rows) if r[9] in ("F", "S")]
    if not pops:
        return None, False
    fs = fetch_list(rows)
    base = (((c["initial"]["regs"]["cs"] << 4) +
             c["initial"]["regs"]["ip"]) & 0xFFFFF)
    rl = roles(c["bytes"])
    out = []
    ok = True
    for k, (row, qs, byte) in enumerate(pops):
        a = (base + k) & 0xFFFFF
        ready = None
        for (t4, fa, n) in fs:
            if fa <= a < fa + n:
                ready = t4 + 2
                break
        if ready is None:
            ok = False
        out.append((k, rl[k] if k < len(rl) else "N", qs, ready, row))
    return out, ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", default=str(timed_gate.V01))
    ap.add_argument("--forms", default="all")
    ap.add_argument("--cases", type=int, default=0)
    ap.add_argument("--dump", default="")
    ap.add_argument("--empty", action="store_true",
                    help="only cases whose injected queue is empty")
    ap.add_argument("--top", type=int, default=12)
    ap.add_argument("--map", action="store_true",
                    help="ready-vs-pop map, both relative to the previous pop")
    ap.add_argument("--by", default="form",
                    help="form | role  -- aggregation key")
    args = ap.parse_args()

    suite = Path(args.suite)
    fh = open(args.dump, "w") if args.dump else None
    agg = defaultdict(Counter)
    skipped = Counter()
    for name, path in timed_gate.form_files(suite, args.forms):
        cases = json.load(gzip.open(path))
        if args.cases:
            cases = cases[:args.cases]
        for idx, c in enumerate(cases):
            if args.empty and c["initial"]["queue"]:
                continue
            ce, ok = census_case(c)
            if ce is None:
                continue
            if not ok:
                skipped[name] += 1
                continue
            if fh:
                fh.write(json.dumps({"form": name, "case": idx,
                                     "nb": len(c["bytes"]), "pops": ce}) + "\n")
            prev = None
            prevrole = "-"
            for (k, role, qs, ready, row) in ce:
                key = (name if args.by == "form" else "*",
                       role, qs, prevrole)
                if args.map:
                    agg[key][("rdy%+d" % (ready - prev) if prev is not None
                              else "rdy-", "pop%+d" % (row - prev)
                              if prev is not None else "pop-")] += 1
                else:
                    agg[key][("late=%s" % (row - ready),
                              "gap=%s" % (row - prev
                                          if prev is not None else "-"))] += 1
                prev, prevrole = row, role
    if fh:
        fh.close()
    for key in sorted(agg):
        tot = sum(agg[key].values())
        cells = ", ".join("%s %s x%d" % (a, b, n)
                          for (a, b), n in agg[key].most_common(args.top))
        print("%-8s %s<-%s %s n=%-5d %s" % (key[0], key[1], key[3], key[2],
                                            tot, cells))
    if skipped:
        print("\nskipped (address not covered): %d cases  %s"
              % (sum(skipped.values()), skipped.most_common(6)))


if __name__ == "__main__":
    sys.exit(main())
