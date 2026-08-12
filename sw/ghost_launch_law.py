#!/usr/bin/env python3
"""ghost_launch_law -- THE `8F` mod=3 GHOST READ IS DECORATED AT **LAUNCH**,
NOT AT **POST**.

WHAT THIS TOOL IS FOR.  `docs/notes/ghost_pred_cell_results_2026-08-11.md` left
the wave a seven-row NON-MONOTONE `dQS` table (1 AND, 2-3 BARE, 5 SP, 6 AND,
7+ BARE, 4 never observed) and said so in terms: *"the next wave's job is the
MECHANISM that produces it"*.  This tool is that derivation, and it re-runs
offline from bytes already in the tree -- the 528 retained board cells plus
`tb_sys ret`.  NO BOARD.

THE QUANTITY.  `dGR` = the number of clocks between

  (a) the FIRST clock on which the `8F` ghost read's own micro-row is current
      -- `upc_opc == 8'h8f && upc_loc == 4'd4`, which is **`v30u_eu.sv`'s own
      existing constant** (`ghost_preread_tail`, line 924), not a fitted one --
      i.e. the clock the read is POSTED, and

  (b) the clock the BIU actually LAUNCHES the bus cycle: the ghost read's T1.

It is the age of the posted request when the bus finally takes it, and it is
read out of the ucore's save-state map (`SSA_E_UPC_LOC` / `SSA_E_UPC_OPC`)
through M10-SYS, at the same freeze the `ghost_pred_cell rails` leg uses.

THE LAW.

    dGR == 0   ->  SS:SP           the posting micro-row's own stack drive
    dGR == 1   ->  stale & SP      both drivers on the rail -- the wired AND
    dGR >= 2   ->  stale           the row has released; only the stale rail

ONE monotone predicate on ONE quantity.  No opcode is named in it, there is no
modulus, no mask table and no per-class case.

WHY THE `dQS` TABLE LOOKED LIKE A TABLE.  Two separate artefacts of its anchor:

  * it anchored on `QS == 1` (opcode pop) when the anchoring event is the
    request.  Re-anchored on the LAST queue op OF ANY KIND the seven rows
    become the CONTIGUOUS range `dQ in [1,7]`, and its `dQS == 4` silence is
    just the clock at which the last op switches from the next opcode's `F`
    to the `8F`'s own ModR/M `S`;
  * `dQ mod 4` then partitions 672/672 of the non-multiply blocks -- which is
    why the table was non-monotone -- but it is an ALIAS: `dGR` and `dQ mod 4`
    agree only while `dGR < 4`, and the cells where they disagree are exactly
    the ones the `dQS` key got wrong.

THE MULTIPLY CLASS IS NOT A SEPARATE MECHANISM.  `ghost_pred_cell_results`
§3.2's second finding -- *"the key's ONLY impure bin is entirely and exactly
`mul` and `imul` at `w1`/`w2` -- 32 blocks of 32"* -- is those cells at
`dGR == 4` and `dGR == 5`, which every counting key aliases onto a low residue
and which `dGR >= 2 -> BARE` reads correctly.  `mul`/`imul` were used to select
NOTHING here and the law scores them **32/32**.  ⚠ This does NOT authorise
deleting `ghost_uses_mul_hi`: that arm produces a DIFFERENT VALUE
(`tmpa & opr`), not a decoration, and its deletion is a second mechanism to be
measured as one.

DISCIPLINE.  The three-way map was read off the SEVEN derivation legs and then
held BYTE-FIXED for the four disjoint validation legs and for the two multiply
legs.  Nothing below re-fits after seeing a score.
"""
import sys, os, re, json, gzip, time, argparse
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ghost_pred_cell as G                                   # noqa: E402
import fz2_m10 as m10                                         # noqa: E402
import fz2_tbsys as tbs                                       # noqa: E402

OUT = G.OUT / "launch-law"
BLOCK = 2                     # a STEADY block; block 0 is the COLD one
GHOST_LOC = 4                 # v30u_eu.sv:924 -- the 8F ghost row, its constant
GHOST_OPC = 0x8F
DLO, DHI = -10, 1

# THE LAW.  Frozen here; `score` never edits it.
def law(dgr):
    if dgr is None:
        return None
    return "SP" if dgr == 0 else "AND" if dgr == 1 else "BARE"


DERIV = ["alu88", "alu44", "alu08", "memw", "pfxpro", "mempop", "mov8e"]
VALID = ["v_sub", "v_or", "v_inc", "v_lea"]
MULCL = ["mul", "imul"]


# --------------------------------------------------------------------------- #
def chip_blocks(legs):
    """(leg, cell, block, dQ, outcome) off the RETAINED board words."""
    tab = {r["cell"]: r for r in G._load("board")}
    out = []
    for leg in legs:
        for w in G.WAITS:
            f = G.OUT / "board" / f"{G.stratum_key(leg, w)}.raw.json.gz"
            if not f.exists():
                continue
            with gzip.open(f, "rt") as fh:
                sh = json.load(fh)
            for ck, ws in sh.items():
                r = tab[ck]
                if not r.get("ok"):
                    continue
                rows = G._rows_from_words([int(x, 16) for x in ws])
                for n, g in enumerate(r["ghost"]):
                    if n == 0:
                        continue
                    i = g["row"]
                    ops = [j for j in range(max(0, i - 60), i) if rows[j]["qs"]]
                    out.append((leg, ck, n, (i - ops[-1]) if ops else None,
                                G._classify(G.CHIP_RAIL[leg],
                                            g["addr"] - G.SEG_BASE["SS"])))
    return out


def cmd_dq(a):
    """THE PIN-SIDE HALF: re-anchor the key and show the alias."""
    legs = [k for k in G.CHIP_RAIL]
    recs = [r for r in chip_blocks(legs) if r[4]]
    print(f"  {len(recs)} scoreable blocks (block 0 excluded, the COLD one)\n")
    for name, sub in (("ALL", lambda r: True),
                      ("non-multiply", lambda r: r[0] not in MULCL),
                      ("multiply only", lambda r: r[0] in MULCL)):
        t = defaultdict(Counter)
        for r in recs:
            if sub(r):
                t[r[3] % 4 if r[3] is not None else None][r[4]] += 1
        n = sum(sum(c.values()) for c in t.values())
        pure = sum(sum(c.values()) for c in t.values() if len(c) == 1)
        print(f"  dQ mod 4, {name}: PURE {pure}/{n}")
        for k in sorted(t, key=str):
            print(f"     {k}: {dict(t[k])}"
                  f"{'' if len(t[k]) == 1 else '   <-- IMPURE'}")
        print("")
    t = defaultdict(Counter)
    for r in recs:
        t[r[3]][r[4]] += 1
    print("  dQ itself (last queue op of ANY kind) -- a CONTIGUOUS range,")
    print("  where the registered `dQS` key had a hole at 4:")
    for k in sorted(t, key=str):
        print(f"     dQ {k}: {dict(t[k])}")
    return 0


# --------------------------------------------------------------------------- #
def cmd_sweep(a):
    """Freeze the ucore across [-10,+1] around each cell's ghost T1 and retain
    `upc_loc` / `upc_opc`.  ~2.5 s a cell; the cache is what `score` reads."""
    A = m10.ss_addrs()
    a_loc, a_opc = A["SSA_E_UPC_LOC"], A["SSA_E_UPC_OPC"]
    cal = G._cal()
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = OUT / "_run.hex"
    rows, t0 = [], time.time()
    for leg in G._select(a.legs):
        for w in G.WAITS:
            for al in G.ALIGNS:
                img, meta = G.image_of(leg, al)
                ncap = G.ncap_for(w, cal)
                tmp.unlink(missing_ok=True)
                r = tbs.run_tb("ret", img, tmp, ncap=ncap, waits=w, quiet=True)
                f = G.features(G._rows_from_words(r["words"]), leg, al, meta)
                if not f.get("ok"):
                    print(f"  {leg:<8} w{w} a{al}  INVALID: {f['why']}")
                    continue
                gr = f["ghost"][BLOCK]["row"]
                loc, opc = {}, {}
                for d in range(DLO, DHI + 1):
                    rr = tbs.run_tb("ret", img, tmp, ncap=ncap, waits=w,
                                    quiet=True, ss_at=gr + d)
                    ss = {int(m.group(1), 16): int(m.group(2), 16)
                          for m in re.finditer(m10.SS6_RE, rr["stdout"])}
                    loc[d], opc[d] = ss.get(a_loc), ss.get(a_opc)
                rows.append({"leg": leg, "waits": w, "align": al,
                             "ghost_row": gr, "loc": loc, "opc": opc})
                print(f"  {leg:<8} w{w} a{al}  row={gr}  "
                      f"({time.time()-t0:.0f}s)", flush=True)
    tmp.unlink(missing_ok=True)
    p = OUT / "sweep.json"
    old = json.loads(p.read_text())["rows"] if p.exists() else []
    keep = [r for r in old
            if (r["leg"], r["waits"], r["align"]) not in
            {(r2["leg"], r2["waits"], r2["align"]) for r2 in rows}]
    p.write_text(json.dumps({"tool": "ghost_launch_law sweep",
                             "receipt": G._tbsys_receipt(), "git": G._git_head(),
                             "dlo": DLO, "dhi": DHI, "block": BLOCK,
                             "rows": keep + rows,
                             "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                 time.gmtime())}, indent=1))
    print(f"\n  -> {p}   {len(keep)+len(rows)} cells")
    return 0


def dgr_of(loc, opc):
    """clocks from the FIRST clock the 8F ghost row is current, to the T1."""
    first, d = None, 0
    while str(d) in loc or d in loc:
        L = loc.get(str(d), loc.get(d))
        O = opc.get(str(d), opc.get(d))
        if L == GHOST_LOC and O == GHOST_OPC:
            first = d
            d -= 1
            continue
        if first is not None:
            break
        d -= 1
    return None if first is None else -first


def cmd_score(a):
    """THE LAW, applied UNCHANGED, per population."""
    p = OUT / "sweep.json"
    if not p.exists():
        raise SystemExit("ghost_launch_law: run `sweep` first")
    sw = {(r["leg"], r["waits"], r["align"]): r
          for r in json.loads(p.read_text())["rows"]}
    obs = {}
    for r in G._load("board"):
        if r.get("ok") and r["leg"] in G.CHIP_RAIL:
            g = r["ghost"][BLOCK]
            o = G._classify(G.CHIP_RAIL[r["leg"]],
                            g["addr"] - G.SEG_BASE["SS"])
            if o:
                obs[(r["leg"], r["waits"], r["align"])] = o

    grand = Counter()
    for name, legs, note in (
            ("DERIVATION -- the set the map was READ OFF; NOT evidence",
             DERIV, ""),
            ("VALIDATION -- DISJOINT, and it selected nothing",
             VALID, "the four `v_*` legs of the frozen-key registration"),
            ("MULTIPLY -- the one class every counting key FAILED",
             MULCL, "used to select nothing; see the module docstring")):
        bins, miss = defaultdict(Counter), []
        for k, o in sorted(obs.items()):
            if k[0] not in legs or k not in sw:
                continue
            d = dgr_of(sw[k]["loc"], sw[k]["opc"])
            pred = law(d)
            bins[d][o] += 1
            grand[("HIT" if pred == o else "MISS")] += 1
            if pred != o:
                miss.append((k, o, pred, d))
        n = sum(sum(c.values()) for c in bins.values())
        hit = sum(v for d, c in bins.items() for o, v in c.items()
                  if law(d) == o)
        print(f"\n== {name}")
        if note:
            print(f"   ({note})")
        print(f"   {hit}/{n} = {100*hit/n if n else 0:.1f} %")
        for d in sorted(bins, key=str):
            print(f"     dGR {str(d):<4} law={str(law(d)):<5} {dict(bins[d])}"
                  f"{'' if len(bins[d]) == 1 else '   <-- IMPURE'}")
        for k, o, pr, d in miss:
            print(f"     MISS {k}  measured={o} law={pr} dGR={d}")
    tot = grand["HIT"] + grand["MISS"]
    print(f"\n== ALL THREE POPULATIONS: {grand['HIT']}/{tot} = "
          f"{100*grand['HIT']/tot if tot else 0:.1f} %")
    return 0 if grand["MISS"] == 0 else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    s = ap.add_subparsers(dest="cmd", required=True)
    c = s.add_parser("dq", help="the pin-side re-anchoring and the alias")
    c.set_defaults(fn=cmd_dq)
    c = s.add_parser("sweep", help="tb_sys freezes -> the cache (slow)")
    c.add_argument("--legs", default=",".join(DERIV + VALID + MULCL))
    c.set_defaults(fn=cmd_sweep)
    c = s.add_parser("score", help="the law, applied unchanged")
    c.set_defaults(fn=cmd_score)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
