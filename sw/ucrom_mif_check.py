#!/usr/bin/env python3
"""ucrom_mif_check -- DID THE MICROCODE REACH THE BITSTREAM?

WHY THIS EXISTS, AND WHY IT EXISTS NOW.

`v30u_ucrom.sv`'s F44 block guards the SIMULATION side of one failure mode:
a wrong `HEXDIR` yields two `$readmemh` warnings, an all-zero microcode ROM,
and a run that COMPLETES NORMALLY.  Its own comment says the SYNTHESIS side of
F44 is *"the `ifdef`ed HEXDIR plus verifying the INITIALISED CONTENTS in the
post-fit netlist, which is what ucore_provenance.md §45.4 item 2 asks for"* --
and that verification was never built.

It became urgent at the **L1** landing (`adcone_l1_prereg_2026-08-13.md`).
With the decode's output registered, Quartus stopped declining to infer a
memory for `ucdecode` (it used to refuse for *"asynchronous read logic"*) and
built it as an **M10K ROM initialised from a `.mif` it generates itself**:

    altsyncram:ucdecode_rtl_0   OPERATION_MODE ROM   8192 x 12
    INIT_FILE db/nec_test_ucore.ram0_v30u_ucrom_f358d0ef.hdl.mif

**The whole offline ladder -- 169,000 golden cases, 17,350 lockstep cases,
1.2 million replayed fuzz rows -- runs on VERILATOR, which reads the `.hex`
files directly and never sees that `.mif`.**  So every functional gate this
repo owns is blind to a `.mif` that does not carry the microcode, and the
failure mode is the silent one F44 was written about: a table of zeros is a
machine that runs and is wrong.

This closes it, on the bytes Quartus will program:

  * every `.mif` Quartus emitted for `v30u_ucrom` is located by its own
    signature block (`-- v30u_ucrom`), not by a guessed filename;
  * it is matched to `ucdecode.hex` or `ucrom.hex` by its declared
    WIDTH/DEPTH -- 8192 x 12 and 1028 x 29 are unambiguous;
  * EVERY WORD is compared, and an address absent from the `.mif` is a
    MISMATCH, not a skip.

⚠ IT IS NOT A STANDING GATE ON ITS OWN.  It reads `hdl/db/`, which a clean
build deletes, so it can only run against a build that is still on disk.  Run
it after a G6 build and before any flash of a bitstream whose `ucdecode` is a
block memory.

    python3 sw/ucrom_mif_check.py [--db DIR]

exit 0 = every emitted table matches its `.hex` word for word
exit 1 = a word differs, or a table Quartus emitted matches no `.hex`
exit 2 = nothing to check (no `db/`, or no `v30u_ucrom` `.mif` in it)
"""
import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HEXDIR = ROOT / "hdl" / "rtl" / "ucore"
DEFAULT_DB = ROOT / "hdl" / "db"

# (width, depth) -> the .hex that is the source of truth for it
TABLES = {
    (12, 8192): "ucdecode.hex",
    (29, 1028): "ucrom.hex",
}


def parse_mif(path):
    """-> (width, depth, {addr: int}) or None if it is not a parseable MIF."""
    txt = path.read_text(errors="replace")
    m_w = re.search(r"^\s*WIDTH\s*=\s*(\d+)\s*;", txt, re.M)
    m_d = re.search(r"^\s*DEPTH\s*=\s*(\d+)\s*;", txt, re.M)
    if not (m_w and m_d):
        return None
    width, depth = int(m_w.group(1)), int(m_d.group(1))
    m_ar = re.search(r"^\s*ADDRESS_RADIX\s*=\s*(\w+)\s*;", txt, re.M)
    m_dr = re.search(r"^\s*DATA_RADIX\s*=\s*(\w+)\s*;", txt, re.M)
    arad = (m_ar.group(1) if m_ar else "HEX").upper()
    drad = (m_dr.group(1) if m_dr else "HEX").upper()
    base = {"UNS": 10, "DEC": 10, "HEX": 16, "BIN": 2, "OCT": 8}
    ab, db_ = base.get(arad), base.get(drad)
    if ab is None or db_ is None:
        raise SystemExit(f"{path.name}: unsupported radix {arad}/{drad}")

    body = txt.split("CONTENT", 1)[1] if "CONTENT" in txt else ""
    words = {}
    # `addr : data;`, `a..b : data;` and `[a..b] : data;` are all legal MIF.
    for line in body.splitlines():
        line = line.split("--", 1)[0].strip()
        if not line or ":" not in line:
            continue
        lhs, rhs = line.split(":", 1)
        rhs = rhs.strip().rstrip(";").strip()
        if not rhs:
            continue
        lhs = lhs.strip().strip("[]")
        try:
            val = int(rhs, db_)
        except ValueError:
            continue
        if ".." in lhs:
            lo, hi = lhs.split("..", 1)
            try:
                lo, hi = int(lo, ab), int(hi, ab)
            except ValueError:
                continue
            for a in range(min(lo, hi), max(lo, hi) + 1):
                words[a] = val
        else:
            try:
                words[int(lhs, ab)] = val
            except ValueError:
                continue
    return width, depth, words


def load_hex(name, depth):
    """`$readmemh` semantics: one word per line, index from 0, unwritten = 0."""
    path = HEXDIR / name
    vals = [0] * depth
    n = 0
    for line in path.read_text().splitlines():
        line = line.split("//", 1)[0].strip()
        if not line:
            continue
        if n >= depth:
            n += 1
            continue
        vals[n] = int(line, 16)
        n += 1
    return vals, n


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=str(DEFAULT_DB),
                    help="the build's db/ directory (a clean build deletes it)")
    args = ap.parse_args()
    dbdir = Path(args.db)
    if not dbdir.is_dir():
        print(f"ucrom_mif_check: NOTHING TO CHECK -- no {dbdir} "
              f"(a clean build deletes it; run this against a build still on disk)")
        return 2

    mifs = []
    for p in sorted(dbdir.glob("*.mif")):
        head = p.read_text(errors="replace")[:400]
        if "v30u_ucrom" in head:
            mifs.append(p)
    if not mifs:
        print(f"ucrom_mif_check: NOTHING TO CHECK -- no v30u_ucrom .mif in {dbdir}")
        return 2

    print(f"ucrom_mif_check: {len(mifs)} v30u_ucrom table(s) emitted into {dbdir}")
    bad = 0
    seen = set()
    for p in mifs:
        parsed = parse_mif(p)
        if parsed is None:
            print(f"  {p.name}: UNPARSEABLE -- no WIDTH/DEPTH")
            bad += 1
            continue
        width, depth, words = parsed
        hexname = TABLES.get((width, depth))
        if hexname is None:
            print(f"  {p.name}: {depth} x {width} -- MATCHES NO KNOWN TABLE "
                  f"(known: {sorted(TABLES)})")
            bad += 1
            continue
        seen.add(hexname)
        vals, nlines = load_hex(hexname, depth)
        mask = (1 << width) - 1
        miss = [a for a in range(depth) if a not in words]
        diff = [a for a in range(depth)
                if a in words and words[a] != (vals[a] & mask)]
        nz = sum(1 for a in range(depth) if words.get(a, 0) != 0)
        tag = "OK " if not miss and not diff else "BAD"
        print(f"  [{tag}] {p.name}")
        print(f"        {depth} x {width}  <- {hexname} ({nlines} lines)  "
              f"non-zero words {nz}")
        if miss:
            print(f"        MISSING {len(miss)} address(es), first {miss[:6]}")
            bad += 1
        if diff:
            print(f"        DIFFER  {len(diff)} word(s), first {diff[:6]}")
            for a in diff[:4]:
                print(f"          @{a}: mif {words[a]:#x} vs hex "
                      f"{vals[a] & mask:#x}")
            bad += 1
        if not miss and not diff:
            print(f"        every one of {depth} words identical")

    for (w, d), name in TABLES.items():
        if name not in seen:
            print(f"  note: {name} ({d} x {w}) has NO emitted .mif in this build "
                  f"-- it was not built as a memory (LUTs), so this file has "
                  f"nothing to check for it")

    if bad:
        print(f"ucrom_mif_check: FAIL ({bad} problem(s))")
        return 1
    print("ucrom_mif_check: PASS -- every emitted microcode table matches its "
          ".hex word for word")
    return 0


if __name__ == "__main__":
    sys.exit(main())
