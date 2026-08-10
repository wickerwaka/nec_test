#!/usr/bin/env python3
"""fz2_failview -- THE HUMAN-READABLE FAILURE ATLAS FOR AN fz2 CORPUS.

One self-contained snippet per seed in a `fz2_ledger` failure ledger: what the
chip was EXECUTING when the two legs forked, and the bus rows on either side of
the fork, chip beside core, with the diverging cells marked.

WHAT IS READ, AND WHAT IS DERIVED
---------------------------------
Everything here comes out of three artifacts and nothing else:

  * the failure ledger (`sw/testdata/fz2/fz2_failure_ledger_*.json`) -- the
    seed list, the family partition, `first_bad_row`, `compare_window`, and the
    sha256 of every capture it names;
  * the banked capture itself, which carries BOTH legs as `real` (the socketed
    NEC chip) and `sim` (the RTL core in fabric).  Its bytes are checked
    against the ledger's sha256 before a single row is read, so a capture being
    rewritten underneath this tool is a loud failure and not a quiet one;
  * the seed's image, re-derived through `fuzz_campaign.compose_case` with the
    stratum's own overrides and gated on the banked `image_sha256`.  It is used
    ONLY to fill a gap in the fetched-byte map (see below) and a `GEN_DRIFT` is
    reported, not smoothed.

Nothing is replayed.  `fz2_replay` exists for that and it is a `tb_sys` run per
seed; this tool needs no engine because the capture already holds both legs.

THE THREE THINGS A SNIPPET SHOWS, AND HOW EACH IS DERIVED
---------------------------------------------------------
1. THE FORK ROW is RE-DERIVED, not copied.  `fuzz_classify.diff_rows(real, sim,
   window=compare_window)` is the corpus's own scorer -- the same column policy
   `fuzz_campaign` scored the capture with -- and its `first` must equal the
   ledger's `first_bad_row`.  A seed where it does not gets a snippet that SAYS
   SO and no disassembly, because a fork row that cannot be reproduced cannot
   be pointed at an instruction.

2. THE EXECUTED ASSEMBLY comes from the SHADOW QUEUE, which is
   `check_core.build_rows_sim`'s reconstruction applied to the CHIP rows: a
   CODE fetch's T4 pushes one byte (odd address or `UBE` high) or two (even and
   `UBE` low) with their addresses; `QS = F`/`S` pops one; `QS = E` flushes.
   Every pop is therefore a (address, byte) pair that the part actually
   retired, and a `QS = F` pop opens a new group -- one instruction, or one
   prefix, since a prefix retires with its own F pop.

   THE BYTES ARE THE BUS'S, NOT THE IMAGE'S.  The disassembly window is built
   from the fetched-byte map -- what the part was handed on AD -- and the image
   fills a gap only where nothing was fetched.  That is what makes a RAW-tier
   seed readable at all: it executes at a mirrored, misaligned address that no
   linear sweep of a 64 KiB image would ever land on, and where the two
   disagree the bus is the artifact.  Every such disagreement is COUNTED and
   reported per seed.

   A window is disassembled with `objdump -D -b binary -m i8086`, the precedent
   this repo already set.  ⚠ THAT IS AN 8086 DECODER AND THE PART IS A V30: the
   `0F` two-byte group, `BRKEM`, the bit-field and packed-BCD instructions do
   not exist for it and it will render them as whatever an 8086 would make of
   the bytes.  The RETIRED BYTE COUNT comes from the queue and is exact, so
   every line where the decoder's length disagrees with it is marked `[len]`
   and the retired count is printed.  That marker is the honest signature of a
   V30-only encoding; it is not smoothed away and no per-opcode table is kept.

3. THE DIVERGENCE TABLE marks exactly what the scorer scores.  The marks are
   not re-implemented from the column rules -- they are the tokens of the
   `RowDiff.other` strings `diff_rows` itself produced, plus `qs`.  A cell this
   tool marks is a cell that put the seed in the ledger.

WHAT IT CANNOT DO
-----------------
* It cannot name a mechanism.  The family label is the ledger's and the
  per-family summary below it is MEASURED over that family's own seeds (first
  diverging column, tier and wait-source mix, arch outcome) -- there is no
  committed classifier for the A-15 partition and inventing prose for one would
  be inventing the partition.
* It cannot disassemble a fork with no retired instruction before it (a seed
  that forks inside the reset sequence, before the first `QS = F`).  Those are
  reported as `NO-DISPATCH`, with their count in the coverage line.

USAGE
-----
    python3 sw/fz2_failview.py --ledger <ledger.json> [--suffix -F14-archive] \
        --split docs/notes/fz2_atlas --index docs/notes/fz2_failure_atlas.md
"""
import argparse
import collections
import gzip
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

import fuzz_campaign as fzc                                    # noqa: E402
import fuzz_classify as fc                                     # noqa: E402
import fz2_w1 as fz                                            # noqa: E402

T_NAME = {0: "Ti", 1: "T1", 2: "T2", 3: "T3", 4: "Tw", 5: "T4"}
BS_NAME = {0: "INTA", 1: "IOR", 2: "IOW", 3: "HALT",
           4: "CODE", 5: "MEMR", 6: "MEMW", 7: "PASV"}
QS_NAME = {0: "-", 1: "F", 2: "E", 3: "S"}

# `RowDiff.other` token -> the column of this tool's table that carries it.
# `nxta` is the next-address preview and it rides on `ad_data`, which is the
# same cell as `data`.
TOK_COL = {"bs": "bs", "t": "t", "ube": "ube", "addr": "addr",
           "data": "data", "nxta": "data", "ps": "ps"}


# --------------------------------------------------------------------------- #
# corpus access
# --------------------------------------------------------------------------- #
def cap_path(entry, suffix):
    """The ledger's capture path with `suffix` applied to the campaign dir.

    The ledger always names the LIVE dir; an archived corpus is the same file
    tree under `<cid><suffix>`.  The sha256 gate below is what makes the
    substitution safe -- a wrong dir does not silently score."""
    p = entry["capture"]
    cid = entry["cid"]
    return p.replace(f"/campaigns/{cid}/", f"/campaigns/{cid}{suffix}/")


def git_tracked(path):
    """Whether git has this file. The atlas rests on a ledger, and whether
    that ledger is COMMITTED or is still a working-tree file another session
    is producing is exactly the kind of thing a reader needs told rather than
    assumed."""
    r = subprocess.run(["git", "ls-files", "--error-unmatch", str(path)],
                       cwd=ROOT, capture_output=True, text=True, check=False)
    return r.returncode == 0


def read_capture(path, want_sha):
    raw = Path(path).read_bytes()
    got = hashlib.sha256(raw).hexdigest()
    if got != want_sha:
        raise ValueError(f"capture sha256 {got[:16]}… != ledger {want_sha[:16]}…")
    return json.loads(gzip.decompress(raw))


def ov_for(cid, k):
    """The stratum's overrides -- `fz2_replay.ov_for`, same table, same rule."""
    for st in fz.STRATA:
        if st["cid"] == cid and st["k_lo"] <= k < st["k_lo"] + st["n"]:
            return fz.ov_of(st)
    raise KeyError((cid, k))


def regen_image(cid, k):
    """(image, sha256).  `derive_case` -> `build` -> `compose_case`, the same
    three calls in the same order the capture path makes them."""
    cfg = fzc.derive_case(cid, k, ov_for(cid, k))
    g = fzc.build(cfg)
    image, _meta = fzc.compose_case(g, cfg)
    return bytes(image), hashlib.sha256(bytes(image)).hexdigest()


# --------------------------------------------------------------------------- #
# the shadow queue  (check_core.build_rows_sim's reconstruction)
# --------------------------------------------------------------------------- #
def shadow(recs):
    """(pops, bmap).

    pops  -- [(row_index, qs, addr, byte)] in retirement order.
    bmap  -- {linear_addr: byte} for every byte the bus DELIVERED on a CODE
             fetch, whether or not it was ever popped.
    """
    queue = []
    pend = None
    pend_data = None
    pops = []
    bmap = {}
    for i, r in enumerate(recs):
        if r["t"] == 1 and r["bs_early"] == 4:
            w = 2 if (r["ad_addr"] & 1) == 0 and not r["ube_n"] else 1
            pend = (w, r["ad_addr"])
            pend_data = None
        if r["t"] in (3, 4) and pend:
            pend_data = r["ad_data"]
        if r["t"] == 5 and pend:
            w, addr = pend
            if pend_data is not None:
                if w == 2:
                    queue.append((addr, pend_data & 0xFF))
                    queue.append((addr + 1, pend_data >> 8))
                    bmap[addr] = pend_data & 0xFF
                    bmap[addr + 1] = pend_data >> 8
                else:
                    b = pend_data >> 8 if addr & 1 else pend_data & 0xFF
                    queue.append((addr, b))
                    bmap[addr] = b
            pend = None
        if r["qs"] in (1, 3) and queue:
            a, b = queue.pop(0)
            pops.append((i, r["qs"], a, b))
        elif r["qs"] == 2:
            queue = []
    return pops, bmap


def groups_of(pops):
    """The retired stream cut at every `QS = F` pop.

    A group is one instruction OR one prefix -- on this part a prefix retires
    with its own F pop, so `26 8b 07` arrives as two groups and that is a fact
    about the queue, not a defect in the cut."""
    out = []
    cur = None
    for i, qs, a, b in pops:
        if qs == 1:
            if cur:
                out.append(cur)
            cur = {"f_row": i, "addr": a, "bytes": [b], "last_row": i}
        elif cur is not None:
            cur["bytes"].append(b)
            cur["last_row"] = i
    if cur:
        out.append(cur)
    return out


# --------------------------------------------------------------------------- #
# disassembly
# --------------------------------------------------------------------------- #
_DIS_CACHE = {}


def _objdump(addr, buf):
    """[(vma, 'aa bb', 'mnemonic')] for a byte window placed at `addr`."""
    key = (addr, bytes(buf))
    if key in _DIS_CACHE:
        return _DIS_CACHE[key]
    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
        f.write(bytes(buf))
        tmp = f.name
    try:
        p = subprocess.run(
            ["objdump", "-D", "-b", "binary", "-m", "i8086", "-M", "intel",
             f"--adjust-vma=0x{addr:x}", tmp],
            capture_output=True, text=True, check=False)
        out = []
        started = False
        for ln in p.stdout.splitlines():
            if ln.endswith("<.data>:"):
                started = True
                continue
            if not started or "\t" not in ln:
                continue
            head, rest = ln.split("\t", 1)
            head = head.strip().rstrip(":")
            try:
                vma = int(head, 16)
            except ValueError:
                # objdump's byte-continuation line for a long instruction, and
                # the `...` elision -- neither starts a new instruction
                if out:
                    out[-1] = (out[-1][0],
                               (out[-1][1] + " " + rest.split("\t")[0]).strip(),
                               out[-1][2])
                continue
            if "\t" in rest:
                hx, txt = rest.split("\t", 1)
            else:
                hx, txt = rest, ""
            out.append((vma, hx.strip(), " ".join(txt.split())))
    finally:
        os.unlink(tmp)
    _DIS_CACHE[key] = out
    return out


def window(addr, n, bmap, image):
    """`n` bytes from `addr`, bus first, image (mirrored to 16 bits) as filler.
    Returns (bytes, n_from_image)."""
    buf = bytearray()
    filled = 0
    for j in range(n):
        a = (addr + j) & 0xFFFFF
        if a in bmap:
            buf.append(bmap[a])
        elif image is not None:
            buf.append(image[a & 0xFFFF])
            filled += 1
        else:
            break
    return bytes(buf), filled


def disasm_group(g, bmap, image):
    """(text, note) for one retired group.

    The group's own retired bytes are decoded first.  Only if the decoder does
    not land exactly on the group's length is the window extended with what
    followed on the bus -- and then the disagreement is REPORTED, because a
    length the 8086 decoder does not agree with is the signature of a V30-only
    encoding and it is the reader's business."""
    n = len(g["bytes"])
    exact = bytes(g["bytes"])
    ins = _objdump(g["addr"], exact)
    if ins and ins[0][0] == g["addr"] and len(ins) == 1 and \
            len(ins[0][1].split()) == n and ".byte" not in ins[0][2]:
        return ins[0][2], ""
    buf, _fill = window(g["addr"], n + 8, bmap, image)
    ins2 = _objdump(g["addr"], buf)
    if not ins2:
        return "??", "[no decode]"
    txt = ins2[0][2]
    got = len(ins2[0][1].split())
    if got == n:
        return txt, ""
    return txt, f"[len {got}≠{n} retired]"


# --------------------------------------------------------------------------- #
# rendering
# --------------------------------------------------------------------------- #
def marks_of(dr):
    """{row: set(column)} -- the SCORER's own marks, taken from the strings
    `diff_rows` produced rather than re-derived from its rules."""
    out = {}
    flick = set()
    for rd in dr.rows:
        cols = set()
        if rd.qs_mm:
            cols.add("qs")
        for s in rd.other:
            tok = s.split(" ", 1)[0]
            if tok in TOK_COL:
                cols.add(TOK_COL[tok])
        out[rd.i] = cols
        if rd.flicker:
            flick.add(rd.i)
    return out, flick


def leg_cell(r, cols):
    def m(c):
        return "*" if c in cols else " "
    return (f"{m('t')}{T_NAME.get(r['t'], '??'):<2}"
            f"{m('bs')}{BS_NAME[r['bs_early']]:<4}"
            f"{m('addr')}{r['ad_addr']:05x}"
            f"{m('data')}{r['ad_data']:04x}"
            f"{m('ube')}{r['ube_n']}"
            f"{m('ps')}{r['ps']:x}"
            f"{m('qs')}{QS_NAME[r['qs']]}")


def addr_txt(a):
    """The linear address, plus the mirrored image offset it was answered from
    when it is above 64 K.  `test_mem` decodes `addr[15:1]` and leaves
    `addr[19:16]` unconnected, so a fetch at 0x6bea0 is answered by image byte
    0xbea0 -- which is the only reading under which an escaped seed's bytes
    make sense."""
    return f"{a:05x}" + (f"(+{a & 0xFFFF:04x})" if a >= 0x10000 else "")


def asm_line(g, bmap, image, mark=" "):
    txt, note = disasm_group(g, bmap, image)
    hx = " ".join(f"{b:02x}" for b in g["bytes"])
    return (f"  {mark} {addr_txt(g['addr']) + ':':<14}{hx:<17} "
            f"{txt} {note}").rstrip()


def asm_cell(g, bmap, image, w=46):
    """The same line, trimmed to a fixed width for the two-leg block."""
    if g is None:
        return "(none)".ljust(w)
    s = asm_line(g, bmap, image)[4:]
    return (s if len(s) <= w else s[:w - 1] + "…").ljust(w)


def evt_txt(line):
    e = line.get("evt")
    if not e:
        return "none"
    pin = "NMI" if e.get("pin") else "INT"
    return (f"{pin} delay={e.get('delay')} hold={e.get('hold')}"
            f"/applied={e.get('hold_applied')}")


def wait_txt(line):
    w = line.get("waits") or {}
    if line.get("wvec_n"):
        return f"wvec n={line['wvec_n']}"
    if w.get("wrand"):
        return f"wrand wmax={w.get('wmax')} wseed={w.get('wseed')}"
    return f"fixed w{w.get('fixed')}"


def snippet(e, cap, image, img_ok, opt):
    """One seed's block.  Returns (text, stats)."""
    L = []
    line = cap["line"]
    real, sim = cap["real"], cap["sim"]
    win = e["compare_window"]
    dr = fc.diff_rows(real, sim, window=win)
    fb_got = dr.first
    fb_want = e["first_bad_row"]
    validated = fb_got == fb_want
    div_got = dr.bad + dr.flick
    stats = {"validated": validated, "div_ok": div_got == e["diverging_rows"],
             "no_dispatch": False, "bus_img_mismatch": 0, "img_ok": img_ok,
             "first_col": None}

    marks, flick = marks_of(dr)
    first_col = None
    if fb_got is not None:
        cols = sorted(marks.get(fb_got, set()))
        first_col = "+".join(cols) if cols else "?"
    stats["first_col"] = first_col

    ov = "  · §38.9 missed-trap overlay" if e.get("_overlay") else ""
    L.append(f"### `{e['seed']}` — {e['family']}")
    L.append("")
    L.append("```")
    L.append(f"seed {e['seed']}   tier {e['tier']}   family {e['family']}{ov}")
    L.append(f"first_bad row {fb_want}   diverging rows {e['diverging_rows']}"
             f" / window {win}   first column: {first_col}")
    L.append(f"waits {wait_txt(line)}   event {evt_txt(line)}"
             f"   term {(line.get('term') or {}).get('term_clocks')}"
             f" fired {(line.get('term') or {}).get('fired')}")
    L.append(f"mech {e['mech']}   arch {e['arch']}"
             f"   done chip/core {int(e['done_chip'])}/{int(e['done_core'])}")

    if not validated:
        L.append("")
        L.append("RECONSTRUCTION NOT VALIDATED — diff_rows(real, sim, "
                 f"window={win}) puts the first non-flicker divergence at "
                 f"{fb_got}, not at the ledger's {fb_want}.")
        L.append("NO DISASSEMBLY IS SHOWN: a fork row that cannot be "
                 "reproduced cannot be pointed at an instruction.")
        L.append("```")
        L.append("")
        return "\n".join(L), stats

    pops_c, bmap_c = shadow(real)
    pops_s, bmap_s = shadow(sim)
    gs_c = groups_of(pops_c)
    gs_s = groups_of(pops_s)

    if image is not None:
        stats["bus_img_mismatch"] = sum(
            1 for a, b in bmap_c.items() if image[a & 0xFFFF] != b)

    pre = [g for g in gs_c if g["f_row"] <= fb_want]
    if not pre:
        stats["no_dispatch"] = True
        L.append("")
        L.append("NO-DISPATCH — no `QS = F` pop happened at or before the "
                 "fork row on the chip leg, so no instruction was in "
                 "dispatch. There is nothing to disassemble.")
        L.append("```")
        L.append("")
        return "\n".join(L), stats

    L.append("")
    src = "bus bytes" + ("" if img_ok else ", image UNAVAILABLE (GEN_DRIFT)")
    if stats["bus_img_mismatch"]:
        src += f", {stats['bus_img_mismatch']} bus byte(s) ≠ image"
    L.append(f"CHIP, retired (shadow queue; {src}; objdump -m i8086):")
    for g in pre[-opt.insns:-1]:
        L.append(asm_line(g, bmap_c, image))
    L.append(asm_line(pre[-1], bmap_c, image, mark=">>")
             + f"   <-- IN DISPATCH AT THE FORK (F pop row "
               f"{pre[-1]['f_row']}, fork row {fb_want})")

    # THE TWO LEGS ARE ALIGNED BY THEIR OWN DISPATCH, NOT BY ROW NUMBER.  Each
    # leg's "at the fork" group is the last F pop at or before the fork row ON
    # THAT LEG, and the sequence runs forward from there.  A leg whose pop is
    # one clock late therefore shows one instruction EARLIER in its column,
    # which is the divergence itself and not an off-by-one in the cut.
    ic = len(pre) - 1
    pre_s = [j for j, g in enumerate(gs_s) if g["f_row"] <= fb_want]
    isv = pre_s[-1] if pre_s else None
    seq_c = gs_c[ic:ic + 1 + opt.after]
    seq_s = ([] if isv is None else gs_s[isv:isv + 1 + opt.after])
    same = ([(g["addr"], tuple(g["bytes"])) for g in seq_c] ==
            [(g["addr"], tuple(g["bytes"])) for g in seq_s])
    L.append("")
    if same and len(seq_c) > 1:
        L.append(f"AFTER THE FORK both legs retire the same "
                 f"{len(seq_c) - 1} further instruction(s):")
        for g in seq_c[1:]:
            L.append(asm_line(g, bmap_c, image))
    elif same:
        L.append("AFTER THE FORK neither leg retires another instruction "
                 "inside the capture.")
    else:
        L.append("AT AND AFTER THE FORK the legs dispatch differently "
                 "(chip | core; each leg from its OWN last F pop at or "
                 "before the fork row):")
        for j in range(max(len(seq_c), len(seq_s))):
            a = asm_cell(seq_c[j] if j < len(seq_c) else None, bmap_c, image)
            b = asm_cell(seq_s[j] if j < len(seq_s) else None, bmap_s, image)
            L.append(f"   {'>>' if j == 0 else '  '} {a} | {b}".rstrip())

    lo = max(0, fb_want - opt.before)
    hi = min(dr.n, fb_want + opt.after_rows + 1)
    L.append("")
    L.append(f"BUS ROWS {lo}..{hi - 1}   (`*` = a cell diff_rows scores, "
             f"`f` = the fork, `~` = tolerated F↔S flicker; window ends at "
             f"{dr.n})")
    L.append("  row | CHIP  t  bs   addr  data u ps qs"
             " | CORE  t  bs   addr  data u ps qs")
    for i in range(lo, hi):
        cols = marks.get(i, set())
        tag = "f" if i == fb_want else ("~" if i in flick else " ")
        L.append(f" {i:>5}{tag}| {leg_cell(real[i], cols)}"
                 f" | {leg_cell(sim[i], cols)}")
    L.append("```")
    L.append("")
    return "\n".join(L), stats


# --------------------------------------------------------------------------- #
# family summaries -- MEASURED, not narrated
# --------------------------------------------------------------------------- #
def family_summary(fam, rows):
    """One paragraph per family, every number from that family's own seeds.

    There is no committed classifier for the A-15 partition -- the ledger
    carries the labels forward seed by seed and §38.5 describes the decision
    list in prose only -- so this tool does not paraphrase a mechanism it
    cannot cite.  It reports the label and what the family's own seeds MEASURE:
    where the fork lands, what the seeds are made of, and how they end."""
    n = len(rows)
    col = collections.Counter(r["first_col"] for r in rows if r["first_col"])
    tier = collections.Counter(r["tier"] for r in rows)
    wait = collections.Counter(r["wait"] for r in rows)
    mech = collections.Counter(r["mech"] for r in rows)
    arch = sum(1 for r in rows if not r["arch_match"])
    fb = sorted(r["first_bad"] for r in rows)
    med = fb[n // 2] if n else 0
    dv = sorted(r["div"] for r in rows)
    return (
        f"**{fam}** — {n} seed(s).  First diverging column: "
        + ", ".join(f"`{k}` {v}" for k, v in col.most_common()) + ".  "
        + "Tiers: " + ", ".join(f"{k} {v}" for k, v in tier.most_common())
        + ".  Wait source: "
        + ", ".join(f"{k} {v}" for k, v in wait.most_common())
        + f".  Median `first_bad` row {med} (range {fb[0]}–{fb[-1]}); "
        f"median diverging rows {dv[n // 2]}.  "
        + f"Terminator: " + ", ".join(f"{k} {v}" for k, v in mech.most_common())
        + f".  Architectural dump differs on {arch} of {n}.  "
        "The label is the ledger's; these numbers are this family's own "
        "seeds, and no mechanism is asserted here that the ledger does not "
        "carry.")


# --------------------------------------------------------------------------- #
def fam_slug(fam):
    return fam.split(" ")[0].replace("/", "_").lower()


def anchor(text):
    """The GitHub heading anchor for `text`."""
    out = []
    for ch in text.lower():
        if ch.isalnum() or ch in "-_":
            out.append(ch)
        elif ch in " \t":
            out.append("-")
    return "".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", default=str(
        ROOT / "sw/testdata/fz2/fz2_failure_ledger_f14_2026-08-10.json"))
    ap.add_argument("--suffix", default="",
                    help="campaign-dir suffix, e.g. -F14-archive")
    ap.add_argument("--split", default=None,
                    help="directory for one file per family")
    ap.add_argument("--index", required=True, help="the index / single output")
    ap.add_argument("--insns", type=int, default=5,
                    help="retired instructions shown up to and incl. the fork")
    ap.add_argument("--after", type=int, default=2,
                    help="retired instructions shown after the fork")
    ap.add_argument("--before", type=int, default=4, help="rows before fork")
    ap.add_argument("--after-rows", type=int, default=12, dest="after_rows")
    ap.add_argument("--seeds", default=None, help="comma list, for debugging")
    ap.add_argument("--json", default=None, help="machine-readable coverage")
    ap.add_argument("--control", default=None, metavar="LEDGER:SUFFIX",
                    help="a second, complete pass over a DIFFERENT ledger and "
                         "corpus whose numbers are measured into the index -- "
                         "the acceptance control for the reconstruction claim")
    opt = ap.parse_args()

    t0 = time.time()
    lp = Path(opt.ledger).resolve()
    lsha = hashlib.sha256(lp.read_bytes()).hexdigest()
    led = json.loads(lp.read_text())
    overlay = set(led.get("overlay_38_9") or [])
    fails = led["failures"]
    if opt.seeds:
        want = set(opt.seeds.split(","))
        fails = [f for f in fails if f["seed"] in want]

    lrel = lp.relative_to(ROOT) if lp.is_relative_to(ROOT) else lp
    cmd = (f"python3 sw/fz2_failview.py --ledger {lrel}"
           + (f" --suffix {opt.suffix}" if opt.suffix else "")
           + (f" --control {opt.control}" if opt.control else "")
           + (f" --split {opt.split}" if opt.split else "")
           + f" --index {opt.index}"
           + (f" --json {opt.json}" if opt.json else ""))

    # families in the ledger's own order, so the atlas's table of contents is
    # the ledger's partition and not this run's arrival order
    fam_order = list(led.get("family_counts") or {})
    by_fam, rows_meta, tot, problems = one_pass(
        fails, overlay, fam_order, opt.suffix, opt)

    # THE ACCEPTANCE CONTROL.  A second, complete pass over a DIFFERENT
    # ledger + corpus whose numbers are MEASURED here and not quoted from
    # memory.  It exists because the whole atlas rests on one claim -- that
    # `diff_rows` re-derives the ledger's `first_bad_row` from the banked
    # capture -- and a claim that is only ever checked on the population it is
    # reported for is not checked.
    ctl = None
    if opt.control:
        cl, csuf = opt.control.rsplit(":", 1)
        clp = Path(cl).resolve()
        cled = json.loads(clp.read_text())
        _b, _r, ctot, cprob = one_pass(
            cled["failures"], set(cled.get("overlay_38_9") or []),
            list(cled.get("family_counts") or {}), csuf, opt)
        ctl = {"ledger": str(clp.relative_to(ROOT)
                             if clp.is_relative_to(ROOT) else clp),
               "sha256": hashlib.sha256(clp.read_bytes()).hexdigest(),
               "suffix": csuf, "totals": dict(ctot),
               "problems": [f"{s} — {w}" for s, w in cprob]}

    # ---------------- index + the per-family files ----------------
    H_index(led, lrel, lsha, cmd, opt, tot, problems, by_fam, rows_meta, ctl)

    if opt.json:
        Path(opt.json).write_text(json.dumps({
            "ledger": str(lrel), "ledger_sha256": lsha, "suffix": opt.suffix,
            "cmd": cmd, "totals": dict(tot), "control": ctl,
            "problems": [{"seed": s, "why": w} for s, w in problems],
        }, indent=1) + "\n")

    print(f"{tot['n']} snippets, fork row reproduced {tot['validated']}/"
          f"{tot['n']}, image ok {tot['img_ok']}/{tot['n']}, "
          f"no-dispatch {tot['no_dispatch']}, cap errors {tot['cap_err']} "
          f"({time.time() - t0:.1f}s) -> {opt.index}")
    if ctl:
        print(f"control {ctl['suffix']}: fork row reproduced "
              f"{ctl['totals'].get('validated')}/{ctl['totals'].get('n')}")
    ok = tot["validated"] == tot["n"] and not tot["cap_err"]
    if ctl:
        ok = ok and ctl["totals"].get("validated") == ctl["totals"].get("n")
    return 0 if ok else 1


def one_pass(fails, overlay, fam_order, suffix, opt):
    """Every seed of one ledger against one corpus. -> (by_fam, rows_meta,
    totals, problems)."""
    by_fam = collections.OrderedDict((f, []) for f in fam_order)
    rows_meta = collections.defaultdict(list)
    tot = collections.Counter()
    problems = []

    for e in fails:
        e = dict(e)
        e["_overlay"] = e["seed"] in overlay
        fam = e["family"]
        try:
            cap = read_capture(cap_path(e, suffix), e["capture_sha256"])
        except Exception as ex:                                # noqa: BLE001
            tot["cap_err"] += 1
            problems.append((e["seed"], f"CAPTURE: {ex}"))
            by_fam.setdefault(fam, []).append(
                f"### `{e['seed']}` — {fam}\n\n```\nCAPTURE UNREADABLE: "
                f"{ex}\n```\n")
            continue
        image, img_ok = None, False
        try:
            img, sha = regen_image(e["cid"], e["k"])
            img_ok = sha == e["image_sha256"]
            image = img if img_ok else None
            if not img_ok:
                problems.append((e["seed"], f"GEN_DRIFT {sha[:12]} != "
                                            f"{e['image_sha256'][:12]}"))
        except Exception as ex:                                # noqa: BLE001
            problems.append((e["seed"], f"REGEN: {ex}"))

        txt, st = snippet(e, cap, image, img_ok, opt)
        by_fam.setdefault(fam, []).append(txt)
        tot["n"] += 1
        tot["validated"] += int(st["validated"])
        tot["div_ok"] += int(st["div_ok"])
        tot["img_ok"] += int(st["img_ok"])
        tot["no_dispatch"] += int(st["no_dispatch"])
        tot["bus_img"] += st["bus_img_mismatch"]
        if st["bus_img_mismatch"]:
            tot["bus_img_seeds"] += 1
        if not st["validated"]:
            problems.append((e["seed"], "FORK ROW NOT REPRODUCED"))
        ln = cap["line"]
        rows_meta[fam].append({
            "tier": e["tier"], "wait": wait_txt(ln).split(" ")[0],
            "mech": e["mech"], "arch_match": e["arch_match"],
            "first_bad": e["first_bad_row"], "div": e["diverging_rows"],
            "first_col": st["first_col"]})
    return by_fam, rows_meta, tot, problems


def H_index(led, lrel, lsha, cmd, opt, tot, problems, by_fam, rows_meta, ctl):
    era = led.get("era") or {}
    corp = led.get("corpus") or {}
    H = []
    H.append(f"# fz2 failure atlas — {led.get('ts', '')[:10]}")
    H.append("")
    H.append("One snippet per seed in the fz2 true-failure ledger: the "
             "assembly the CHIP was executing when the legs forked, and the "
             "bus rows on either side of it with the diverging cells marked.")
    H.append("")
    H.append("## How to regenerate this, exactly")
    H.append("")
    H.append("```")
    H.append(cmd)
    H.append("```")
    H.append("")
    H.append(f"* ledger `{lrel}` sha256 `{lsha[:16]}…`, "
             f"derived {led.get('ts')} by `{led.get('tool')}` — "
             + ("committed" if git_tracked(lrel) else
                "**NOT committed at generation time**: it is a working-tree "
                "file, and the sha256 above is what this atlas was built "
                "from"))
    H.append(f"* corpus `{'`, `'.join(corp.get('campaigns', []))}`"
             + (f" (suffix `{opt.suffix}`)" if opt.suffix else " (live dirs)")
             + f", {corp.get('seeds')} seeds, {corp.get('failures')} failures, "
             f"seed match {corp.get('seed_match_pct')} %")
    H.append(f"* bitstream `.sof` sha256 `{str(era.get('sof_sha256'))[:16]}…`, "
             f"flashed {era.get('flash_ts')} from `{era.get('flash_git')}`, "
             f"RTL receipt `{str((era.get('rtl') or {}).get('receipt_id'))[:16]}…`"
             f" ({(era.get('rtl') or {}).get('label')})")
    H.append(f"* every capture is sha256-gated against the ledger before a row "
             f"is read; every image is re-derived through "
             f"`fuzz_campaign.compose_case` and gated on `image_sha256`")
    H.append("")
    H.append("## What a snippet is, and what it is not")
    H.append("")
    H.append(
        "* **The fork row is re-derived, not copied.** "
        "`fuzz_classify.diff_rows(real, sim, window=compare_window)` is the "
        "corpus's own scorer; its first non-flicker row must equal the "
        "ledger's `first_bad_row`. Where it does not, the snippet says so and "
        "shows no disassembly.\n"
        "* **The bytes are the bus's.** The disassembly window is the "
        "shadow-queue reconstruction of what the part actually fetched and "
        "retired (`CODE` T4 pushes, `QS=F/S` pops, `QS=E` flushes), with the "
        "re-derived image filling only what was never fetched. A raw-tier "
        "seed executes at a mirrored, misaligned address, and every address "
        "at or above 64 K is printed as `linear(+offset)` with the image "
        "offset it was answered from.\n"
        "* **The decoder is an 8086 and the part is a V30.** `objdump -D -b "
        "binary -m i8086` is the precedent here. The retired byte count comes "
        "from the queue and is exact, so every line where the decoder's "
        "length disagrees carries `[len N≠M retired]` — that marker is the "
        "honest signature of a V30-only encoding, not a defect.\n"
        "* **A prefix retires with its own `QS=F` pop** on this part, so it "
        "appears as its own line.\n"
        "* **The marks are the scorer's.** A `*` is a cell "
        "`fuzz_classify.diff_rows` itself flagged — not a looser or stricter "
        "comparison invented here. `f` marks the fork row, `~` a tolerated "
        "F↔S queue-status flicker. That policy is asymmetric by column and "
        "the table shows it honestly: `qs` is compared on every row, `bs` "
        "from row 8, `t`/`ube` from row 9, `addr` only at a `T1` with an "
        "active non-`INTA` status, `data` at `T2`/`T3` and — as the "
        "next-address preview `nxta`, same cell — at `Ti`/`T4` on an active "
        "cycle, and `ps` only at a `T2`. An unmarked difference in the table "
        "is a column the corpus does not score at that T-state.\n"
        "* **No mechanism is asserted.** The family labels are the ledger's "
        "A-15 partition, carried forward seed by seed; the per-family "
        "paragraph is measured over that family's own seeds.")
    H.append("")
    H.append("## Coverage")
    H.append("")
    H.append(f"| | |")
    H.append(f"|---|---|")
    H.append(f"| snippets emitted | {tot['n']} of "
             f"{len(led['failures'])} ledger failures |")
    H.append(f"| fork row reproduced from the capture | **{tot['validated']} "
             f"/ {tot['n']}** |")
    H.append(f"| `diverging_rows` reproduced | {tot['div_ok']} / {tot['n']} |")
    H.append(f"| image re-derived to the banked sha256 | {tot['img_ok']} "
             f"/ {tot['n']} |")
    H.append(f"| forks with no instruction in dispatch (`NO-DISPATCH`) | "
             f"{tot['no_dispatch']} |")
    H.append(f"| captures unreadable / sha-drifted | {tot['cap_err']} |")
    H.append(f"| bus bytes disagreeing with the re-derived image | "
             f"{tot['bus_img']} (in {tot['bus_img_seeds']} seed(s)) |")
    H.append("")
    if problems:
        H.append("### Seeds this tool could not handle cleanly")
        H.append("")
        for s, why in problems:
            H.append(f"* `{s}` — {why}")
        H.append("")
    else:
        H.append("No seed was left unhandled.")
        H.append("")

    if ctl:
        c = ctl["totals"]
        H.append("### Acceptance control — the same derivation on a "
                 "different corpus")
        H.append("")
        H.append(
            f"The reconstruction claim is checked a second time, in this same "
            f"run, against `{ctl['ledger']}` (sha256 `{ctl['sha256'][:16]}…`) "
            f"over the `{ctl['suffix']}` corpus: **fork row reproduced "
            f"{c.get('validated')} / {c.get('n')}**, `diverging_rows` "
            f"{c.get('div_ok')} / {c.get('n')}, image re-derived "
            f"{c.get('img_ok')} / {c.get('n')}, `NO-DISPATCH` "
            f"{c.get('no_dispatch', 0)}, captures unreadable "
            f"{c.get('cap_err', 0)}. That population selected nothing here — "
            "it is a different bitstream era and a different failure set — "
            "so it is a control and not a fit.")
        if ctl["problems"]:
            H.append("")
            H.append("Control residue: " + "; ".join(ctl["problems"]) + ".")
        H.append("")

    H.append("## Families")
    H.append("")
    H.append("| family | seeds | snippets |")
    H.append("|---|---:|---|")
    for fam in by_fam:
        if not by_fam[fam]:
            continue
        slug = fam_slug(fam)
        tgt = (f"{Path(opt.split).name}/{slug}.md" if opt.split
               else f"#{anchor(fam)}")
        H.append(f"| {fam} | {len(by_fam[fam])} | [{slug}]({tgt}) |")
    H.append("")

    for fam in by_fam:
        if rows_meta[fam]:
            H.append(family_summary(fam, rows_meta[fam]))
            H.append("")

    if opt.split:
        d = ROOT / opt.split
        d.mkdir(parents=True, exist_ok=True)
        for fam, blocks in by_fam.items():
            if not blocks:
                continue
            slug = fam_slug(fam)
            body = [f"# {fam}", "",
                    f"{len(blocks)} seed(s). Generated by `{cmd}` — see "
                    f"[the atlas index](../{Path(opt.index).name}) for the "
                    "reading rules, the coverage table and the provenance.",
                    ""]
            if rows_meta[fam]:
                body += [family_summary(fam, rows_meta[fam]), ""]
            body += blocks
            (d / f"{slug}.md").write_text("\n".join(body))
    else:
        for fam in by_fam:
            if not by_fam[fam]:
                continue
            H.append(f"## {fam}")
            H.append("")
            H.extend(by_fam[fam])

    (ROOT / opt.index).write_text("\n".join(H) + "\n")


if __name__ == "__main__":
    sys.exit(main())
