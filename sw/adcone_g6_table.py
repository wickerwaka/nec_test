#!/usr/bin/env python3
"""adcone_g6_table -- read a `quartus_gate --seeds` artifact directory and
print the per-draw table this wave quotes, plus `worst-of-N@seeds{...}`.

It reads the RECEIPTS (`seed<N>_quartus_gate.json`) for Fmax / worst setup /
TNS / ALMs / configuration / seed-echo, and the truefmax artifacts for the
binding cone and the rungs.  It computes nothing the receipt does not already
contain except the min over the draws, which is the quotable figure.

    python3 sw/adcone_g6_table.py sw/testdata/g6dist/<label> [...]
"""
import json
import re
import sys
from pathlib import Path


DIVCLK = "emu|pll|pll_inst|altera_pll_i|general[0].gpll~PLL_OUTPUT_COUNTER|divclk"


def fmax_of(rec):
    """The `divclk` domain's own Fmax, off Quartus's own Fmax Summary.

    ⚠ NOT the `truefmax` DEFAULT row: that row is an UNCONSTRAINED
    `get_timing_paths`, i.e. the worst path by SLACK, and on a draw where a
    k=0.5 arc has the smallest slack it names that arc instead
    (`timing50_distribution_2026-08-13.md` §3.1 — CONTROL seed 3, 56.40 where
    Quartus says 40.95).  Quartus's Fmax Summary is the authority."""
    f = (rec.get("figures") or {}).get("fmax") or {}
    if DIVCLK in f:
        return float(f[DIVCLK])
    for k, v in f.items():
        if "gpll" in k and "pll_audio" not in k:
            return float(v)
    return None


def setup_of(rec):
    for row in (rec.get("figures") or {}).get("setup") or []:
        if row.get("clock") == DIVCLK:
            return row.get("slack"), row.get("tns")
    return None, None


def worst_tns(rec):
    """max |TNS| over EVERY domain, setup AND hold -- E5's own quantity."""
    fig = rec.get("figures") or {}
    vals = [abs(r.get("tns") or 0.0)
            for k in ("setup", "hold") for r in (fig.get(k) or [])]
    return max(vals) if vals else None


def dig(rec, *keys):
    cur = rec
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


def truefmax_bits(path):
    """-> (binding_from, binding_to, rung1_mhz, rung1_from, rung1_to, ce_size)"""
    if not path.exists():
        return {}
    txt = path.read_text(errors="replace")
    out = {}
    m = re.search(r"v30u_regs\s+(\d+)\s+v30u_ce\s+(\d+)\s+v30u_half\s+(\d+)", txt)
    if m:
        out["v30u_regs"], out["v30u_ce"], out["v30u_half"] = (
            int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.search(r"--- DEFAULT.*?\n\s*from\s*:\s*(\S+)\n\s*to\s*:\s*(\S+)\n"
                  r"\s*k = ([\d.]+)\s+slack =\s*([-+\d.]+)\s*->\s*T_min\s*"
                  r"([\d.]+) ns\s*=\s*([\d.]+) MHz", txt, re.S)
    if m:
        out["bind_from"], out["bind_to"] = m.group(1), m.group(2)
        out["bind_k"], out["bind_slack"] = float(m.group(3)), float(m.group(4))
        out["bind_mhz"] = float(m.group(6))
    # RUNG 1a is the one the distribution gate quotes -- "the worst k=1
    # survivor" -- and on the draws where the fitter duplicated `t1_half2` it
    # is CONTAMINATED (§6); the `k` printed beside it is how you tell.
    m = re.search(r"--- RUNG 1a:.*?\n\s*from\s*:\s*(\S+)\n\s*to\s*:\s*(\S+)\n"
                  r"\s*k = ([\d.]+)\s+slack =\s*([-+\d.]+)\s*->\s*T_min\s*"
                  r"([\d.]+) ns\s*=\s*([\d.]+) MHz", txt, re.S)
    if m:
        out["rung1_from"], out["rung1_to"] = m.group(1), m.group(2)
        out["rung1_k"] = float(m.group(3))
        out["rung1_mhz"] = float(m.group(6))
    return out


def short(n):
    if not n:
        return "-"
    n = n.split("|")[-1]
    return n


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    for d in sys.argv[1:]:
        d = Path(d)
        recs = sorted(d.glob("seed*_quartus_gate.json"),
                      key=lambda p: int(re.search(r"seed(\d+)", p.name).group(1)))
        if not recs:
            print(f"{d}: no receipts")
            continue
        print(f"=== {d.name} ===")
        print(f"{'seed':>4} {'Fmax':>7} {'wsetup':>8} {'|TNS|':>6} {'ALMs':>14} "
              f"{'cfg':>9} {'rung1a':>8} {'k':>4}  binding cone")
        rows = []
        for r in recs:
            n = int(re.search(r"seed(\d+)", r.name).group(1))
            rec = json.loads(r.read_text())
            f = fmax_of(rec)
            ws, _ = setup_of(rec)
            tns = worst_tns(rec)
            alm = dig(rec, "figures", "status", "alms") or "?"
            alm = re.sub(r"\s*/.*", "", str(alm)).strip()
            cfg = str(rec.get("configuration") or "?").split("/")[0]
            tf = truefmax_bits(d / f"seed{n}.truefmax.txt")
            rows.append((n, f, ws, alm, cfg, tf, tns))
            print(f"{n:>4} {f if f is not None else float('nan'):>7.2f} "
                  f"{(ws if isinstance(ws,(int,float)) else float('nan')):>8.3f} "
                  f"{(tns if tns is not None else float('nan')):>6.3f} "
                  f"{alm:>14} {cfg[:9]:>9} "
                  f"{tf.get('rung1_mhz', float('nan')):>8.2f} "
                  f"{tf.get('rung1_k', float('nan')):>4.1f}  "
                  f"{short(tf.get('bind_from'))} -> {short(tf.get('bind_to'))}")
        good = [r for r in rows if isinstance(r[1], (int, float))]
        if good:
            w = min(good, key=lambda r: r[1])
            seeds = ",".join(str(r[0]) for r in rows)
            print(f"  worst-of-{len(good)}@seeds{{{seeds}}} = {w[1]:.2f} MHz "
                  f"(seed {w[0]})   median "
                  f"{sorted(r[1] for r in good)[len(good)//2]:.2f}   best "
                  f"{max(r[1] for r in good):.2f}   spread "
                  f"{max(r[1] for r in good) - w[1]:.2f}")
            ce = {r[5].get("v30u_ce") for r in rows if r[5].get("v30u_ce")}
            if ce:
                print(f"  $v30u_ce at STA: {sorted(ce)}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
