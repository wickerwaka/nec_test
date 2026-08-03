#!/usr/bin/env python3
"""s16_dispwin -- the DISPLAY WINDOW census (ucsim_t_provenance 25.6 item 1).

OFFLINE.  No board, no new capture.  Reads the BANKED captures only.

25.6 item 1 left this MEASURED, MECHANISM OPEN:

    "On a display window longer than one clock, from the SECOND display clock
     on and continuing through T1, the chip drives A19-A16 with the SEGMENT
     STATUS instead of the address nibble, and UBE takes the announced cycle's
     own value instead of changing at T1."

and named the confound: the ONE program that produces a multi-clock display
window (the HLT delay sweeps) has a fetch address whose top nibble collides
with a legal segment-status code, so the sweep alone cannot separate "address"
from "status" on its own FIRST display clock.

This tool does three things and nothing else:

  1. DETECTS display windows off the pins, with no model in the loop.  A
     DISPLAY WINDOW is the maximal run of clocks on which a non-PASV status is
     announced on `bs_early` BEFORE that cycle's own T1 opens -- excluding the
     clocks that are the BODY (T1..last Tw) of a cycle already running with
     that same status, which is what keeps a back-to-back same-status pair
     from being read as one long window.  The window is GRANTED if the row
     after it is that status's T1, and WITHDRAWN if it is not.

  2. CENSUSES every banked corpus for windows with L >= 2, and reports, per
     window, the two nibbles that decide 25.6 item 1:

         Na  = ad_addr >> 16 on the clock `display + 1`  (mid-cycle sample)
         Nt  = ad_addr >> 16 on T1                       (mid-cycle sample)
         Ns  = the cycle's own SEGMENT STATUS nibble, read off the pins at T2
               (ad_addr >> 16 there, which is the campaign's `ps` column one
               half-clock earlier -- see the identity check below)

     A window is UNCONFOUNDED when Na != Ns: there the sweep's collision is
     broken and the nibble on `display + 1` names itself.

  3. Checks the RIG IDENTITY  ps(c) == ad_addr(c+1) >> 16  over whole
     captures.  `ps` is the END-of-clock sample of A19-A16 and `ad_addr`'s top
     nibble is the MID-clock sample of the same four pads, so the two columns
     are one pin group half a clock apart.  If the identity holds the two
     columns may be read as one waveform, which is what makes the one-clock
     address window measurable at all.

    s16_dispwin.py --oracle          the confound-breaker: the sweeps' own
                                     INJECTED CS:IP and FLAGS predict both
                                     nibbles, with no model and no pins
    s16_dispwin.py --sweeps          the four banked HLT delay sweeps
    s16_dispwin.py --banked          every other banked raw capture
    s16_dispwin.py --fuzz            the 3,242-seed fuzz bank (chip_rows)
    s16_dispwin.py --goldens         the committed golden suites (L census only)
    s16_dispwin.py --identity        the ps / ad_addr half-clock identity
    s16_dispwin.py --show FILE[:i]   one capture's window neighbourhoods

A MEASUREMENT TOOL, not a gate.
"""
import argparse
import gzip
import json
import sys
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

BS_NAME = {0: "INTA", 1: "IOR", 2: "IOW", 3: "HALT",
           4: "CODE", 5: "MEMR", 6: "MEMW", 7: "PASV"}
T_NAME = {0: "Ti", 1: "T1", 2: "T2", 3: "T3", 4: "Tw", 5: "T4"}
PASV = 7


def _t(r):
    return r.get("t_state", r.get("t"))


# --------------------------------------------------------------------------- #
# 1.  THE DETECTOR -- pins only.
# --------------------------------------------------------------------------- #
def bodies(rows):
    """body[i] = the status of the bus cycle whose T1..last-Tw covers row i.

    The T4 row is deliberately NOT part of the body: on this part a cycle's
    own `bs_early` is already passive at T4, so a T4 row carrying a non-PASV
    status is always the NEXT cycle's announcement."""
    n = len(rows)
    body = [None] * n
    for i in range(n):
        if _t(rows[i]) == 1:
            s = rows[i]["bs_early"]
            j = i
            while j < n and _t(rows[j]) != 5:
                if body[j] is None:
                    body[j] = s
                j += 1
    return body


def windows(rows):
    """-> [dict(i0, L, bs, t1)] -- every display window in the capture.

    `t1` is the row index of the announced cycle's T1, or None when the
    announcement was WITHDRAWN before it ever opened one."""
    n = len(rows)
    body = bodies(rows)
    ann = [rows[i]["bs_early"] != PASV and body[i] != rows[i]["bs_early"]
           for i in range(n)]
    # THE LEFT EDGE.  A record that opens in the MIDDLE of a bus cycle (every
    # committed golden case does -- its window starts at the first `F` pop)
    # carries T2/T3/Tw rows whose own T1 is off the front of the record, so
    # `bodies()` cannot know they belong to a running cycle and reads their
    # status as an announcement.  That fabricated a window of length 3 at w1,
    # 4 at w2 and 5 at w3 on the first row of half the waited golden cases --
    # exactly the body length of a waited cycle.  Rows before the record's
    # FIRST T1 are unclassifiable, and a window that starts there is dropped.
    first_t1 = next((i for i in range(n) if _t(rows[i]) == 1), n)
    for i in range(min(first_t1, n)):
        ann[i] = False
    out, i = [], 0
    while i < n:
        if not ann[i]:
            i += 1
            continue
        s = rows[i]["bs_early"]
        j = i
        while j < n and ann[j] and rows[j]["bs_early"] == s:
            j += 1
        t1 = j if (j < n and _t(rows[j]) == 1 and rows[j]["bs_early"] == s) \
            else None
        out.append(dict(i0=i, L=j - i, bs=s, t1=t1))
        i = j
    return out


# --------------------------------------------------------------------------- #
# 2.  THE MEASUREMENT -- the three nibbles per window.
# --------------------------------------------------------------------------- #
def measure(rows, w):
    """-> the row-2 nibbles 25.6 item 1 turns on, or None if the capture is
    cut short of them."""
    n = len(rows)
    i0, L, t1 = w["i0"], w["L"], w["t1"]
    d = dict(w)
    d["Na"] = rows[i0 + 1]["ad_addr"] >> 16 if i0 + 1 < n else None
    d["low_a"] = rows[i0 + 1]["ad_addr"] & 0xFFFF if i0 + 1 < n else None
    d["ube_d0"] = rows[i0]["ube_n"]
    d["ube_d1"] = rows[i0 + 1]["ube_n"] if i0 + 1 < n else None
    d["ps_d0"] = rows[i0]["ps"]
    if t1 is not None:
        d["Nt"] = rows[t1]["ad_addr"] >> 16
        d["low_t"] = rows[t1]["ad_addr"] & 0xFFFF
        d["ube_t1"] = rows[t1]["ube_n"]
        # the cycle's own SEGMENT STATUS, read on its T2 (the campaign's own
        # convention: `ps` is compared at T2 and nowhere else)
        d["Ns"] = rows[t1 + 1]["ad_addr"] >> 16 if t1 + 1 < n else None
    else:
        d["Nt"] = d["low_t"] = d["ube_t1"] = None
        # a WITHDRAWN announcement never reaches a T2; the status the pins
        # settle back to on the clock after `display + 1` is the same nibble
        d["Ns"] = rows[i0 + 2]["ad_addr"] >> 16 if i0 + 2 < n else None
    return d


def identity(rows):
    """-> (mismatches, compared) for  ps(c) == ad_addr(c+1) >> 16."""
    bad = 0
    for c in range(len(rows) - 1):
        if rows[c]["ps"] != (rows[c + 1]["ad_addr"] >> 16):
            bad += 1
    return bad, max(0, len(rows) - 1)


# --------------------------------------------------------------------------- #
# corpus loaders
# --------------------------------------------------------------------------- #
def raw_rows(p):
    return json.load(gzip.open(p))


def golden_rows(p):
    """The committed golden suites carry 11-column rows, not pin records.
    Only `bs_early`/`t` are recoverable there, which is enough for the LENGTH
    census (the falsification leg) and for nothing else."""
    inv_bs = {v: k for k, v in BS_NAME.items()}
    inv_t = {v: k for k, v in T_NAME.items()}
    out = []
    for c in json.load(gzip.open(p)):
        out.append([{"bs_early": inv_bs[r[7]], "t": inv_t[r[8]],
                     "ad_addr": r[1], "ad_data": r[6], "ps": r[1] >> 16,
                     "ube_n": r[5]} for r in c["cycles"]])
    return out


SWEEPS = [("sw/testdata/s10/s2-hltsweep", "w0"), ("sw/testdata/s10/s2-hltsweep", "w1"),
          ("sw/testdata/s13/p1b-ahsweep", "w2"), ("sw/testdata/s13/p1b-ahsweep", "w3")]
BANKED = ["sw/testdata/s10/s1-tranche", "sw/testdata/s10/s1-instrument",
          "sw/testdata/s10/s5-a30", "sw/testdata/s13/p2a-c2ramp",
          "sw/testdata/s13/p5-race", "sw/testdata/t2b", "sw/testdata/t4"]


ORACLE = [("tests/v30/s10-hltsweep-w0", "sw/testdata/s10/s2-hltsweep", "w0"),
          ("tests/v30/s10-hltsweep-w1", "sw/testdata/s10/s2-hltsweep", "w1"),
          ("tests/v30/s13-hltsweep-w2", "sw/testdata/s13/p1b-ahsweep", "w2"),
          ("tests/v30/s13-hltsweep-w3", "sw/testdata/s13/p1b-ahsweep", "w3")]


def do_oracle():
    """THE CONFOUND-BREAKER, with nothing but arithmetic in the loop.

    Each HLT-sweep case injects CS, IP and FLAGS.  Those three numbers predict
    BOTH nibbles independently of any pin and of any model:

        the address nibble   ((CS << 4) + IP) >> 16, the segment the woken
                             fetch is made in
        the status nibble    PS3:PS0 = MD:IE:S4:S3 with S4:S3 = 2 (CS) for a
                             code fetch and MD = 0 outside emulation mode,
                             i.e. 6 with IE set and 2 with IE clear

    25.6's confound was that `HLT.INT` puts the address in segment 5 and 5 is
    also a legal status code (SS with IE set).  `HLT.RES` -- the OTHER form of
    the SAME banked sweep -- puts it in segment 9, and 9 has PS3 set: the 8080
    EMULATION-MODE bit, in a program that is not in emulation mode and whose
    every other status sample in the same capture reads 1, 2 or 3.  There is
    no reading of 9 as a status.  The confound is broken by data already on
    disk."""
    print("form     w  CS   IP    linear  addr-nibble  IE  status-nibble")
    for gd, _rd, w in ORACLE:
        for form in ("HLT.INT", "HLT.RES"):
            p = ROOT / gd / f"{form}.json.gz"
            if not p.exists():
                continue
            r = json.load(gzip.open(p))[0]["initial"]["regs"]
            lin = ((r["cs"] << 4) + r["ip"]) & 0xFFFFF
            ie = (r["flags"] >> 9) & 1
            print("%-8s %s  %04X %04X  %05X   %X            %d   %X"
                  % (form, w[1], r["cs"], r["ip"], lin, lin >> 16, ie,
                     (4 if ie else 0) | 2))


def hdr():
    print("%-42s %-6s %-4s %-2s %-3s %-4s %-4s %-4s %-4s | %s"
          % ("capture", "status", "i0", "L", "t1", "Na", "Nt", "Ns", "ube",
             "verdict"))


def emit(tag, rows, w, out):
    m = measure(rows, w)
    if m["Na"] is None:
        return
    unconf = m["Ns"] is not None and m["Na"] != m["Ns"]
    ver = []
    ver.append("UNCONF" if unconf else "conf")
    if m["Nt"] is not None:
        ver.append("T1=status" if m["Nt"] == m["Ns"] else
                   ("T1=Na" if m["Nt"] == m["Na"] else "T1=?"))
    ver.append("ube@d+1" if m["ube_d1"] != m["ube_d0"] else "ube=held")
    print("%-42s %-6s %-4d %-2d %-3s %-4X %-4s %-4s %-4s | %s"
          % (tag, BS_NAME[m["bs"]], m["i0"], m["L"],
             "-" if m["t1"] is None else str(m["t1"]),
             m["Na"], "-" if m["Nt"] is None else "%X" % m["Nt"],
             "-" if m["Ns"] is None else "%X" % m["Ns"],
             "%d>%d" % (m["ube_d0"], m["ube_d1"]), " ".join(ver)))
    m["tag"] = tag
    out.append(m)


def do_raw(paths, args, out, label):
    tot = Counter()
    for p in paths:
        rows = raw_rows(p)
        ws = windows(rows)
        for w in ws:
            tot[w["L"]] += 1
            if w["L"] >= 2:
                emit(Path(p).name.replace(".rows.json.gz", ""), rows, w, out)
    print("# %s: %d captures, window lengths %s"
          % (label, len(paths), dict(sorted(tot.items()))))


# --------------------------------------------------------------------------- #
def fuzz_one(path):
    e = json.loads(gzip.decompress(Path(path).read_bytes()))
    rows = e["chip_rows"]
    ws = windows(rows)
    lens = Counter(w["L"] for w in ws)
    hits = []
    for w in ws:
        if w["L"] >= 2:
            m = measure(rows, w)
            if m["Na"] is not None:
                m["tag"] = "%s/%s" % (Path(path).parent.parent.name,
                                      Path(path).stem.replace(".json", ""))
                hits.append(m)
    bad, cmp_ = identity(rows)
    return dict(lens=dict(lens), hits=hits, ident=(bad, cmp_), n=len(ws))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--oracle", action="store_true")
    ap.add_argument("--sweeps", action="store_true")
    ap.add_argument("--banked", action="store_true")
    ap.add_argument("--fuzz", action="store_true")
    ap.add_argument("--goldens", action="store_true")
    ap.add_argument("--identity", action="store_true")
    ap.add_argument("--show", default="")
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--report", default="")
    args = ap.parse_args()
    out = []

    if args.show:
        p, _, sel = args.show.partition(":")
        rows = raw_rows(p)
        print(" i    t   bsE  bsL  ad_addr A19-16 ps ube  data")
        for w in windows(rows):
            if w["L"] < 2 and not sel:
                continue
            a, b = w["i0"] - 3, (w["t1"] or w["i0"] + w["L"]) + 3
            print("--- window i0=%d L=%d %s t1=%s"
                  % (w["i0"], w["L"], BS_NAME[w["bs"]], w["t1"]))
            for i in range(max(0, a), min(len(rows), b)):
                r = rows[i]
                print("%5d %-3s %-4s %-4s  %05X   %X     %X  %d   %04X"
                      % (i, T_NAME[_t(r)], BS_NAME[r["bs_early"]],
                         BS_NAME.get(r.get("bs_late"), "?"), r["ad_addr"],
                         r["ad_addr"] >> 16, r["ps"], r["ube_n"], r["ad_data"]))
        return

    if args.oracle:
        do_oracle()

    if args.sweeps:
        hdr()
        for d, w in SWEEPS:
            ps = sorted((ROOT / d).glob(f"*_{w}_*.rows.json.gz"))
            do_raw(ps, args, out, f"{d} {w}")

    if args.banked:
        hdr()
        for d in BANKED:
            ps = sorted((ROOT / d).glob("**/*.rows.json.gz"))
            if ps:
                do_raw(ps, args, out, d)

    if args.goldens:
        tot = Counter()
        for sd in sorted((ROOT / "tests" / "v30").iterdir()):
            if not sd.is_dir() or sd.name == "fuzz_bank":
                continue
            sub = Counter()
            for p in sorted(sd.glob("*.json.gz")):
                try:
                    cases = golden_rows(p)
                except Exception:                                # noqa: BLE001
                    continue
                for rows in cases:
                    for w in windows(rows):
                        sub[w["L"]] += 1
            if sub:
                print("%-28s %s" % (sd.name, dict(sorted(sub.items()))))
                tot += sub
        print("ALL GOLDEN SUITES  %s" % dict(sorted(tot.items())))

    if args.fuzz or args.identity:
        paths = []
        for b in ("mc1", "mc2", "t30-raw", "t30-brkem"):
            paths += sorted(str(p) for p in
                            (ROOT / "tests/v30/fuzz_bank" / b / "seeds")
                            .glob("*.json.gz"))
        if args.limit:
            paths = paths[:args.limit]
        lens, ib, ic, nseed = Counter(), 0, 0, 0
        hits = []
        with Pool(args.jobs) as pool:
            for r in pool.imap_unordered(fuzz_one, paths, chunksize=8):
                nseed += 1
                for k, v in r["lens"].items():
                    lens[k] += v
                hits += r["hits"]
                ib += r["ident"][0]
                ic += r["ident"][1]
        print("# fuzz bank: %d seeds, %d display windows, lengths %s"
              % (nseed, sum(lens.values()), dict(sorted(lens.items()))))
        print("# rig identity ps(c) == ad_addr(c+1)>>16 : %d mismatches / %d"
              % (ib, ic))
        if hits:
            hdr()
            for m in sorted(hits, key=lambda x: (x["tag"], x["i0"])):
                unconf = m["Ns"] is not None and m["Na"] != m["Ns"]
                ver = ["UNCONF" if unconf else "conf"]
                if m["Nt"] is not None:
                    ver.append("T1=status" if m["Nt"] == m["Ns"] else
                               ("T1=Na" if m["Nt"] == m["Na"] else "T1=?"))
                ver.append("ube@d+1" if m["ube_d1"] != m["ube_d0"]
                           else "ube=held")
                print("%-42s %-6s %-4d %-2d %-3s %-4X %-4s %-4s %-4s | %s"
                      % (m["tag"], BS_NAME[m["bs"]], m["i0"], m["L"],
                         "-" if m["t1"] is None else str(m["t1"]),
                         m["Na"], "-" if m["Nt"] is None else "%X" % m["Nt"],
                         "-" if m["Ns"] is None else "%X" % m["Ns"],
                         "%d>%d" % (m["ube_d0"], m["ube_d1"]), " ".join(ver)))
        out += hits

    if out:
        n = len(out)
        unc = sum(1 for m in out if m["Ns"] is not None and m["Na"] != m["Ns"])
        t1s = [m for m in out if m["Nt"] is not None]
        print("\nSUMMARY  multi-clock windows %d   UNCONFOUNDED (Na != Ns) %d"
              % (n, unc))
        print("  T1 nibble == segment status : %d / %d"
              % (sum(1 for m in t1s if m["Nt"] == m["Ns"]), len(t1s)))
        print("  T1 nibble == display+1      : %d / %d"
              % (sum(1 for m in t1s if m["Nt"] == m["Na"]), len(t1s)))
        print("  low 16 equal at d+1 and T1  : %d / %d"
              % (sum(1 for m in t1s if m["low_a"] == m["low_t"]), len(t1s)))
        # UBE, stated as the two things that are actually claimed: it has
        # already CHANGED by display+1 (where the announced value differs from
        # the one on the pads at all), and it does not change again at T1.
        chg = [m for m in out if m["ube_d0"] != m["ube_d1"]]
        print("  UBE differs from the pre-announce value at display+1 : "
              "%d / %d windows (the other %d announce the SAME UBE)"
              % (len(chg), n, n - len(chg)))
        print("  UBE at display+1 == UBE at T1 : %d / %d"
              % (sum(1 for m in t1s if m["ube_d1"] == m["ube_t1"]), len(t1s)))
        print("  status x length: %s"
              % dict(Counter("%s.L%d" % (BS_NAME[m["bs"]], m["L"])
                             for m in out)))
        print("  Na x Ns: %s"
              % dict(Counter("%X/%X" % (m["Na"], m["Ns"] if m["Ns"] is not None
                                        else 15) for m in out)))
    if args.report:
        json.dump(out, open(args.report, "w"), indent=1)


main()
