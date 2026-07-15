#!/usr/bin/env python3
"""timing_magnitude - quantify chip-vs-core divergence in CLOCK-CYCLE terms.

Reflash-free (cached chip refs + Verilator TB). Each capture row = one CPU clock.
Align chip and core by CODE-fetch T1 events (architecturally identical address
sequence); the row-index difference at each aligned fetch = the accumulated
clock offset at that point. Reports per seed / wait:
  - total cycle divergence (final offset), and as % of window clocks
  - drift rate (offset growth per 100 fetches / per 1000 clocks)
  - direction (net final vs total absolute variation = mono vs bidirectional)
  - cascade vs re-sync (fraction of fetches where offset returned to its start)
  - functional identity (fetch-addr sequence + memory-write (addr,data) sequence)
"""
import argparse, statistics, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_seq import compose, run_tb
from gen_seq import generate
from measure import chip_ref


def fetches(rows):
    """(row_index, addr) for each CODE-fetch T1."""
    return [(i, r["ad_addr"] & 0xFFFFF) for i, r in enumerate(rows)
            if r["t"] == 1 and r["bs_early"] == 4]


def writes(rows):
    """ordered (row, addr, data) for memory writes (MEMW): addr at T1, data T3."""
    out = []
    for i, r in enumerate(rows):
        if r["t"] == 1 and r["bs_early"] == 6:
            data = None
            for j in range(i + 1, min(i + 8, len(rows))):
                if rows[j]["t"] in (3, 4):      # T3 / last Tw carries the data
                    data = rows[j]["ad_data"]
                if rows[j]["t"] == 5:
                    break
            out.append((i, r["ad_addr"] & 0xFFFFF, data))
    return out


def faddr_resync(cf, kf):
    """resync-tolerant fetch-address identity: the retired fetch stream must
    match allowing speculative/doomed prefetches (present in one, not the other)
    to be skipped. Returns True if one is a subsequence-consistent alignment of
    the other (no genuine execution-order divergence)."""
    ca = [a for _, a in cf]; ka = [a for _, a in kf]
    i = j = mism = 0
    while i < len(ca) and j < len(ka):
        if ca[i] == ka[j]:
            i += 1; j += 1
        else:
            # skip a single speculative prefetch on whichever side, else count
            if i + 1 < len(ca) and ca[i + 1] == ka[j]:
                i += 1
            elif j + 1 < len(ka) and ca[i] == ka[j + 1]:
                j += 1
            else:
                mism += 1; i += 1; j += 1
    return mism == 0


def analyze(seed, waits, host):
    g = generate(seed, exts=())
    image, meta = compose(g)
    chip = [dict(r, t=r["t"]) for r in chip_ref(seed, waits, host)]
    core = run_tb(image, 4200, waits=waits)
    cf, kf = fetches(chip), fetches(core)
    n = min(len(cf), len(kf))
    # functional: fetch-address stream identical (resync-tolerant: speculative
    # doomed prefetches may differ without an execution divergence)
    faddr_ok = faddr_resync(cf, kf)
    cw, kw = writes(chip), writes(core)
    nw = min(len(cw), len(kw))
    # architectural output = ordered (addr,data) of memory writes
    writes_ok = all(cw[k][1:] == kw[k][1:] for k in range(nw)) and len(cw) == len(kw)
    # WRITE-ANCHORED clock offset (robust: writes are architectural, no
    # speculation) - chip_write_row - core_write_row at each common write
    woff = [cw[k][0] - kw[k][0] for k in range(nw)]
    woff0 = woff[0] if woff else 0
    woff = [o - woff0 for o in woff]
    wfinal = woff[-1] if woff else 0
    wabsmax = max([abs(o) for o in woff], default=0)
    # per-fetch clock offset = chip_row - core_row
    off = [cf[k][0] - kf[k][0] for k in range(n)]
    off0 = off[0] if off else 0
    off = [o - off0 for o in off]        # normalize to the first aligned fetch
    final = off[-1] if off else 0
    mx, mn = (max(off), min(off)) if off else (0, 0)
    # total absolute variation vs net (mono vs bidirectional)
    tv = sum(abs(off[k] - off[k - 1]) for k in range(1, len(off)))
    # re-sync: fraction of fetches at offset 0 after having diverged
    diverged = False
    resync = at0 = nz = 0
    for o in off:
        if o != 0:
            diverged = True; nz += 1
        elif diverged:
            resync += 1; at0 += 1
    # window clocks
    chip_clk, core_clk = len(chip), len(core)
    return dict(seed=seed, w=waits, nfetch=n, final=final, absmax=max(mx, -mn),
                mx=mx, mn=mn, tv=tv, faddr_ok=faddr_ok, writes_ok=writes_ok,
                nwrites=len(cw), wfinal=wfinal, wabsmax=wabsmax,
                nz=nz, chip_clk=chip_clk, core_clk=core_clk)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="root@mister-nec")
    ap.add_argument("--seeds", type=int, default=40)
    ap.add_argument("--start", type=int, default=90000)
    ap.add_argument("--waits", default="0,1,3")
    a = ap.parse_args()
    for w in [int(x) for x in a.waits.split(",")]:
        rows = []
        for s in range(a.start, a.start + a.seeds):
            r = analyze(s, w, a.host)
            rows.append(r)
            print(f"  w{w} s{s}: nfetch={r['nfetch']:4} wr_off={r['wfinal']:+4} "
                  f"wr_absmax={r['wabsmax']:3} | fetch_off={r['final']:+4} "
                  f"fetch_absmax={r['absmax']:3}[{r['mn']:+d},{r['mx']:+d}] "
                  f"faddr={'OK' if r['faddr_ok'] else 'MISM'} "
                  f"wr={'OK' if r['writes_ok'] else 'MISM'}({r['nwrites']})", flush=True)
        # WRITE-ANCHORED = the robust architectural timing offset
        wfin = [abs(r["wfinal"]) for r in rows]
        wamax = [r["wabsmax"] for r in rows]
        rate100f = [100 * abs(r["wfinal"]) / r["nfetch"] for r in rows if r["nfetch"]]
        rate1kc = [1000 * abs(r["wfinal"]) / r["core_clk"] for r in rows if r["core_clk"]]
        mono = sum(1 for r in rows if r["wfinal"] != 0 and r["wfinal"] == (r["wabsmax"] if r["wfinal"] > 0 else -r["wabsmax"]))
        signs = [r["wfinal"] for r in rows if r["wfinal"] != 0]
        pos = sum(1 for x in signs if x > 0); neg = sum(1 for x in signs if x < 0)
        clean = sum(1 for r in rows if r["wfinal"] == 0 and r["wabsmax"] == 0)
        faddr_all = all(r["faddr_ok"] for r in rows)
        wr_all = all(r["writes_ok"] for r in rows)
        print(f"=== w{w}: N={len(rows)} [WRITE-ANCHORED, architectural] | "
              f"|final_off| median={statistics.median(wfin):.0f} mean={statistics.mean(wfin):.1f} "
              f"WORST={max(wfin)} clk | peak-excursion median={statistics.median(wamax):.0f} "
              f"worst={max(wamax)} clk", flush=True)
        # +offset = chip's write at a later clock = chip slower = CORE FASTER/ahead
        print(f"    drift-rate median: {statistics.median(rate100f):.2f} cyc/100fetch, "
              f"{statistics.median(rate1kc):.2f} cyc/1000clk | final sign: +{pos}/-{neg} "
              f"(+ = core faster/ahead; {'mostly one-directional' if abs(pos-neg)>0.5*(pos+neg) else 'bidirectional/self-cancelling'}), "
              f"fully-clean={clean}/{len(rows)}", flush=True)
        print(f"    FUNCTIONAL: fetch-addr stream {'ALL-IDENTICAL' if faddr_all else 'has speculative-prefetch diffs'}, "
              f"memory-writes {'ALL-IDENTICAL' if wr_all else 'MISMATCH!'}", flush=True)


if __name__ == "__main__":
    main()
