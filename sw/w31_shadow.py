#!/usr/bin/env python3
"""w31_shadow -- THE BRK/TF TRAP'S RECOGNITION SHADOW, MEASURED ON SILICON
ALONE (task #41, wrfuzz W3.1).

> *"A guiding principal here needs to be simplicity.  This is 80's era
> hardware, they aren't wasting silicon on anything that isn't necessary.
> Complex or confusing behavior that we see is likely to be simple systems
> interacting in ways you do not fully understand yet."*

sec.83.4's readout, one campaign on: **every trap entry publishes its own return
IP on the pads** (the third push of the entry frame), so a TF storm's pushed-IP
sequence is a direct, engine-free readout of WHICH instruction boundaries the
part took a trap at.  sec.84 / sec.85 measured the storm CADENCE at grace 0 on
1,742 + 90 consecutive pairs and landed it in both engines.

**This tool asks the cadence question one level down: grace 0 AT WHICH
BOUNDARY, and 1 at which?**  It pairs consecutive chip entries with the
GENERATOR'S OWN instruction layout -- `fuzz_campaign.build(cfg)['ins']`, the
byte strings the image was composed from, so instruction lengths are known
exactly and no disassembler is in the loop -- and reports the grace per
retiring opcode.

NOTHING HERE IS AN ENGINE.  The chip's rows are the only input on the chip
side; the generator supplies the ruler (where instructions start), which is a
property of the IMAGE, not of any model of the part.
"""
import argparse
import gzip
import json
import sys
from collections import Counter, defaultdict
from multiprocessing import Pool
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

import check_seq                                          # noqa: E402
import fuzz_campaign as fzc                               # noqa: E402
import fuzz_classify as fc                                # noqa: E402
import ucsim_fuzz as uf                                   # noqa: E402

PREFIX = {0x26, 0x2E, 0x36, 0x3E, 0xF0, 0xF2, 0xF3, 0x64, 0x65}

# THE CLASSES, NAMED BEFORE THE COUNT.  `pla3_sreg_mov` is the ucore's OWN
# recognition-shadow class (`hdl/rtl/ucore/pla3_tables.svh`, bit 9) and it is
# exactly 8C / 8E.  The other two rows are the documented segment-register
# loads that are NOT in that class.
SREG_MOV = {0x8C, 0x8E}                       # MOV rm,sreg / MOV sreg,rm
# NOT 0x0F: on this part 0F is the TWO-BYTE OPCODE ESCAPE, not `POP CS`.  The
# first cut of this tool had it in the class and it reported 52 grace-0 pairs
# there; they are all the `0F` escape and none of them is a segment pop.
SREG_POP = {0x07, 0x17, 0x1F}                 # POP ES / SS / DS
SREG_FAR = {0xC4, 0xC5}                       # LES / LDS

# CONTROL TRANSFERS -- the RULER's own falsifier.  The layout walk below counts
# instruction boundaries in ADDRESS order, so a pair whose walk steps PAST a
# taken transfer is measuring the layout, not the part.  Such pairs are
# reported as UNRULED and never counted, rather than being allowed to
# manufacture a grace.
XFER = (set(range(0x70, 0x80)) | set(range(0xE0, 0xE4)) |
        {0x9A, 0xC2, 0xC3, 0xCA, 0xCB, 0xCC, 0xCD, 0xCE, 0xCF,
         0xE8, 0xE9, 0xEA, 0xEB, 0xF1, 0xFF, 0xFE, 0x62, 0x63, 0x0F})


def klass(op):
    if op in SREG_MOV:
        return "sreg_mov"
    if op in SREG_POP:
        return "sreg_pop"
    if op in SREG_FAR:
        return "sreg_far"
    return "other"


def launches(rows, n):
    return [(i, fc.BS_NAME[rows[i]["bs_early"]], rows[i]["ad_addr"] & 0xFFFFF)
            for i in range(min(n, len(rows)))
            if rows[i].get("t_state", rows[i].get("t")) == 1]


def cycle_data(rows, t1, n):
    for i in range(t1 + 1, min(t1 + 4, n)):
        if rows[i].get("t_state", rows[i].get("t")) in (2, 3):
            return rows[i]["ad_data"] & 0xFFFF
    return None


def entries(rows, n):
    """Every interrupt entry, structurally (sec.83.2's detector): a vector PAIR
    at 4V / 4V+2 followed by three DESCENDING word pushes.  The third push
    carries the return IP."""
    lc = launches(rows, n)
    out = []
    for j in range(len(lc) - 4):
        if lc[j][1] != "MEMR" or lc[j + 1][1] != "MEMR":
            continue
        a0, a1 = lc[j][2], lc[j + 1][2]
        if a1 != a0 + 2 or a0 % 4 or a0 >= 0x400:
            continue
        # AN ODD-SP FRAME PUSHES EACH WORD AS TWO BYTE CYCLES (`sm3_tf_law.
        # push_frame`), so it is SIX descending writes, not three, and its
        # third write is a byte of the flags word rather than the return IP.
        # Such an entry is DETECTED (or a pair straddling it silently reads as
        # a grace of 1) and its IP is declared UNREADABLE.  That defect is the
        # one this tool's first cut had, and it manufactured a grace on the
        # only two `MOV SP, imm16` pairs whose immediate was odd.
        w = [c for c in lc[j + 2:j + 12] if c[1] == "MEMW"]
        if len(w) < 3:
            continue
        # a WORD frame is three descending word writes; a BYTE frame is six
        # byte writes whose addresses walk DOWN in pairs and UP inside each
        # pair (`6b99, 6b9a, 6b97, 6b98, ...`), so "strictly descending" is
        # wrong for it and misses the entry entirely.
        a = [x[2] for x in w[:3]]
        if not all(w[0][2] - 8 <= v <= w[0][2] + 2 for v in a):
            continue
        word = (a[0] - a[1]) == 2 and not (a[0] & 1)
        out.append({"vec": a0 // 4, "row": lc[j][0], "odd_frame": not word,
                    "psw": cycle_data(rows, w[0][0], n) if word else None,
                    "cs": cycle_data(rows, w[1][0], n) if word else None,
                    "ip": cycle_data(rows, w[2][0], n) if word else None})
    return out


def layout(entry):
    """addr -> (length, opcode-after-prefixes) for every instruction the
    GENERATOR laid down, walked from the program's own entry PC.  The bytes
    come from the composed image (displacements are patched there), the
    LENGTHS from the generator's instruction list."""
    cfg = fzc.derive_case(entry["cid"], entry["k"], entry.get("ov") or {})
    g = fzc.build(cfg)
    image, meta = check_seq.compose(g)
    pc = g["regs"]["PC"] & 0xFFFF
    cs = g["regs"]["PS"] & 0xFFFF
    lay = {}

    def place(pc, n):
        base = ((cs << 4) + pc) & 0xFFFFF
        bs = [image[(base + i) & 0xFFFFF] for i in range(n)]
        i = 0
        while i < n - 1 and bs[i] in PREFIX:
            i += 1
        lay[pc] = {"len": n, "op": bs[i], "npfx": i,
                   "bytes": "".join(f"{b:02x}" for b in bs)}
        return (pc + n) & 0xFFFF

    for ins in g["ins"]:
        pc = place(pc, len(ins))
    # ...and then whatever the program falls into, which `g['ins']` does not
    # carry but a trap storm runs straight through.
    #
    # fuzz-v2 T12: this used to walk the STORE STUB that `compose` appended at
    # `meta['stub_linear']` -- ten instructions, hand-listed here.  There is no
    # stub in v2.  The program falls into the 0xCC apron, and every one of
    # those bytes is a ONE-BYTE INT3, so the layout past the program is uniform
    # and needs no table: one entry per address until the terminator.  That is
    # the whole of what replaced the ten-instruction list, which is the shape
    # this campaign's SIMPLICITY principle predicts.
    end = meta["term_at"] & 0xFFFF
    while pc != end:
        pc = place(pc, 1)
    for n in _TERM_LAYOUT:
        pc = place(pc, n)
    return lay, cs


def _term_layout():
    """Instruction lengths of the composed terminator, DERIVED not tabled.

    The v1 code carried a hand-written ten-entry list of the store stub's
    instruction sizes.  A hand list is exactly the fitted table the campaign's
    SIMPLICITY principle warns about -- it drifts the moment the terminator is
    edited, silently, because nothing checks it.  Assemble each source line and
    take its length instead: it cannot drift."""
    import testimage as _ti                                  # noqa: PLC0415
    from v30asm import Assembler                             # noqa: PLC0415
    a = Assembler()
    out = []
    for line in (_ti.TERM_HANDLER + _ti.DUMP_TAIL).splitlines():
        if line.strip():
            out.append(len(a.assemble(line, org=0)))
    return tuple(out)


_TERM_LAYOUT = _term_layout()


def one(path):
    e = json.load(gzip.open(path))
    n = uf.window_of(e["chip_rows"])
    ce = entries(e["chip_rows"], n)
    v1 = [x for x in ce if x["vec"] == 1]
    out = {"k": e["k"], "st": e.get("stratum_label"), "n_v1": len(v1),
           "pairs": [], "unruled": 0}
    if len(v1) < 2:
        return out
    lay, cs = layout(e)
    for a, b in zip(v1, v1[1:]):
        ra, rb = a["ip"], b["ip"]
        if ra is None or rb is None or a["cs"] != cs:
            out["unruled"] += 1
            continue
        ia = lay.get(ra)
        if ia is None:
            out["unruled"] += 1
            continue
        # walk instructions from ra until the next trap's return address
        pc, g_, ops, hit = ra, 0, [], False
        while g_ <= 4:
            cur = lay.get(pc)
            if cur is None:
                break
            ops.append(cur["op"])
            pc = (pc + cur["len"]) & 0xFFFF
            if pc == rb:
                hit = True
                break
            if cur["op"] in XFER:
                break               # the ruler cannot walk past a transfer
            g_ += 1
        if hit:
            out["pairs"].append({"ip": ra, "grace": g_,
                                 "op": ia["op"], "npfx": ia["npfx"],
                                 "cls": klass(ia["op"]),
                                 "ops": ops, "bytes": ia["bytes"]})
        else:
            out["unruled"] += 1
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeddir",
                    default=str(Path.home() / ".cache/ucsimt-tmp/wrfuzz_w2/seeds"))
    ap.add_argument("--jobs", type=int, default=12)
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    paths = sorted(str(p) for p in Path(a.seeddir).glob("*.json.gz"))
    with Pool(a.jobs) as pool:
        rows = pool.map(one, paths, chunksize=4)
    pairs = [p for r in rows for p in r["pairs"]]
    print(f"== w31_shadow -- {len(rows)} captures, "
          f"{sum(r['n_v1'] for r in rows)} chip vector-1 entries, "
          f"{len(pairs)} consecutive pairs ruled, "
          f"{sum(r['unruled'] for r in rows)} unruled")
    print("\n  GRACE x CLASS  (grace = instruction boundaries the chip ran "
          "PAST between one trap and the next)")
    tab = defaultdict(Counter)
    for p in pairs:
        tab[p["cls"]][p["grace"]] += 1
    for cls in ("other", "sreg_mov", "sreg_pop", "sreg_far"):
        c = tab[cls]
        print(f"    {cls:<10} " + "  ".join(f"g{g}={c[g]}"
                                            for g in sorted(c)) or "-")
    print("\n  GRACE x OPCODE (opcodes with any grace > 0, and the top clean "
          "ones for contrast)")
    byop = defaultdict(Counter)
    for p in pairs:
        byop[p["op"]][p["grace"]] += 1
    dirty = {op: c for op, c in byop.items() if sum(v for g, v in c.items() if g)}
    for op in sorted(dirty):
        c = byop[op]
        print(f"    {op:02x} {klass(op):<9} " +
              "  ".join(f"g{g}={c[g]}" for g in sorted(c)))
    clean = sorted(((sum(c.values()), op) for op, c in byop.items()
                    if op not in dirty), reverse=True)[:12]
    print("    -- clean (grace 0 only), the twelve most frequent: " +
          ", ".join(f"{op:02x}({n})" for n, op in clean))
    print(f"\n  distinct opcodes seen {len(byop)};  "
          f"grace>0 pairs {sum(1 for p in pairs if p['grace'])};  "
          f"grace 0 pairs {sum(1 for p in pairs if not p['grace'])}")
    if a.out:
        json.dump(rows, open(a.out, "w"))
        print(f"  dump -> {a.out}")


if __name__ == "__main__":
    main()
