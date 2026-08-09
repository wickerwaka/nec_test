#!/usr/bin/env python3
"""ucsim_fuzz - the SEQUENCE gauntlet for sim/v30sim (campaign `ucsim`, S3).

Every gate before this one injects an architectural state and executes ONE
instruction.  This one executes PROGRAMS: for each banked fuzz seed it

  1. re-derives the case from `(cid, k, ov)` with sw/fuzz_campaign.derive_case
     + build + sw/check_seq.compose -- the SAME generator the capture used;
  2. VERIFIES sha256 against the banked `image_sha256`.  A mismatch is
     GEN-DRIFT and a hard failure (standing rule): the image the simulator
     would run is not the image the chip ran, so nothing downstream means
     anything;
  3. loads the image at physical 0 of a 64K-mirrored 1 MB space (how the
     capture board is wired), runs the ROM's own RESET sequence and executes
     from the reset vector THROUGH the load stub, the program and the store
     stub;
  4. compares, against the banked SOCKET capture (`chip_rows`):
       * the ordered functional bus stream -- kind / address / byte-enable /
         committed data, in order, with CODE fetches excluded exactly as
         sw/fuzz_classify.func_stream excludes them;
       * `chip_arch` -- the twelve registers the store stub dumped through
         OUT 0xFE plus the PSW from the last PUSH PSW at 0xFFEC, read out of
         the SIMULATOR's own bus stream by the same arch_dump rules.

Wait axes are TIMING-ONLY.  The banked seeds span w0..w15 fixed and random
wait patterns; the functional stream must be wait-INVARIANT, so a seed whose
ARCH outcome depends on its wait axis is a FINDING, not a simulator bug
(the rollup prints the per-wait-class census so a collapse in one class
cannot hide).

External events (`evt`) are REPLAYED, never predicted (ledger sec. 38): the
capture says where the acknowledge landed, expressed as a position in the
ordered bus stream, and the simulator computes every consequence from the ROM
-- including the REPX withdrawal (0223 `JMP INTR`) and the prefix-chain rewind
(0225-0227), which is the general, stacked-prefix test of the
"saved IP covers all prefixes" law.

Byte-lane conventions (both sides).  The V30 has a 16-bit bus, so an unaligned
word access is TWO byte cycles; the chip drives the whole 16-bit pattern on AD
in both of them and UBE/A0 select which lane commits:

    ube_n == 1                -> one byte at `addr`      = data & 0xFF
    ube_n == 0 and addr odd    -> one byte at `addr`      = data >> 8
    ube_n == 0 and addr even   -> two bytes: data & 0xFF @ addr, data >> 8 @ addr+1

so a write is compared as the (address, byte) commits it actually made, which
is lane-exact and never reads an indeterminate lane.

Usage:
  ucsim_fuzz.py [--bank mc1,mc2,t30-raw] [--limit N] [--jobs N]
                [--report out.json] [--details N] [--k K] [--no-evt]
                [--stat-clobber] [--coverage cov.json] [--census]
"""

import argparse
import gzip
import hashlib
import json
import os
import subprocess
import sys
import time
from collections import Counter, defaultdict
from multiprocessing import Pool
from pathlib import Path

SW = Path(__file__).resolve().parent
ROOT = SW.parent
sys.path.insert(0, str(SW))

import simbin                                          # noqa: E402

# U1: the C++ model THROUGH THE ARTIFACT/RECEIPT LAYER.  `simbin.SIM` is
# `sim/build/v30sim`, the binary `simbin.recipe()` declares; nothing here
# resolves the model by bare path any more.  See sw/simbin.py.
SIM = simbin.SIM
ROM = ROOT / "docs" / "V20BITS.TXT"
BANK = ROOT / "tests" / "v30" / "fuzz_bank"

import check_seq                                     # noqa: E402
import fuzz_campaign as fzc                          # noqa: E402
import fuzz_classify as fc                           # noqa: E402
from testimage import (OUT_PORT_REGS, OUT_PORT_DONE,  # noqa: E402
                       MAGIC, STORE_ORDER)

# sim/biu.h Txn::Kind
SIM_KIND = {0: "CODE", 1: "MEMR", 2: "MEMW", 3: "IOR", 4: "IOW", 5: "INTA",
            6: "HALT"}
LIMIT_ROWS = 4000            # fuzz_classify.diff_rows' historical window cap
NMI_VECTOR = 2


# --------------------------------------------------------------------------- #
# stream normalisation
# --------------------------------------------------------------------------- #
def _commits(addr, ube, data):
    """The (address, byte) commits one WRITE bus cycle actually made."""
    if ube == 1:
        return ((addr, data & 0xFF),)
    if addr & 1:
        return ((addr, data >> 8),)
    return ((addr, data & 0xFF), (addr + 1, data >> 8))


def chip_stream(recs, window):
    """The chip's ordered functional stream over `window` rows, in the same
    normal form the simulator's is put in.  CODE and PASV are excluded, read
    DATA is an input and is excluded, INTA/HALT are bare position markers --
    all exactly sw/fuzz_classify.func_stream's conventions."""
    ev = []
    for tx in fc.extract_txns(recs):
        if tx["start"] >= window:
            break
        k = fc.KIND[tx["kind"]]
        a = tx["addr"] & 0xFFFFF
        if k in ("MEMW", "IOW"):
            ev.append(("W", k, a, tx["ube_n"],
                       _commits(a, tx["ube_n"], tx["data"])))
        elif k in ("MEMR", "IOR"):
            ev.append(("R", k, a, tx["ube_n"]))
        elif k == "INTA":
            ev.append(("INTA",))
        elif k == "HALT":
            ev.append(("HALT",))
    return ev


def sim_stream(tx):
    """The simulator's ordered functional stream.  The BIU logs a word access
    as one transaction; the 16-bit bus splits an UNALIGNED one into two byte
    cycles, and `addr2` carries the second cycle's address because a segment
    wrap sends it to the base of the segment rather than to addr+1 (A12)."""
    ev = []
    for kind, addr, addr2, data, width in tx:
        k = SIM_KIND[kind]
        if k in ("MEMW", "IOW"):
            if width == 1:
                # A byte cycle commits one byte; the lane it rides is the
                # address parity, and the simulator always presents the byte in
                # the low half, so the commit is the same either way.
                ev.append(("W", k, addr, 0 if addr & 1 else 1,
                           ((addr, data & 0xFF),)))
            elif addr & 1:
                ev.append(("W", k, addr, 0, ((addr, data & 0xFF),)))
                ev.append(("W", k, addr2, 1, ((addr2, data >> 8),)))
            else:
                ev.append(("W", k, addr, 0,
                           ((addr, data & 0xFF), (addr2, data >> 8))))
        elif k in ("MEMR", "IOR"):
            if width == 2 and (addr & 1):
                ev.append(("R", k, addr, 0))
                ev.append(("R", k, addr2, 1))
            else:
                ev.append(("R", k, addr, 0 if (width == 2 or addr & 1) else 1))
        elif k == "INTA":
            ev.append(("INTA",))
        elif k == "HALT":
            ev.append(("HALT",))
    return ev


def arch_of(stream):
    """`fuzz_classify.arch_dump`'s rule, applied to a normalised stream: the
    LAST `len(STORE_ORDER)` IOW-0xFE words strictly BEFORE the first IOW-0xFC
    done marker, anchored by MAGIC at `fc.MAGIC_AT`.

    PSW is a word in that run (the terminator pops its own interrupt frame),
    so the `MEMW @ 0xFFEC` channel is gone from this leg too -- the two arch
    readers must agree word for word or a model/chip arch compare means
    nothing."""
    regs, done = [], False
    for e in stream:
        if e[0] != "W":
            continue
        _, k, a, _u, commits = e
        if k != "IOW":
            continue
        port = a & 0xFFFF
        if port == OUT_PORT_DONE:
            done = True                     # width-agnostic: it is a MARKER
            break
        if port == OUT_PORT_REGS and len(commits) == 2:
            regs.append(commits[0][1] | (commits[1][1] << 8))
    if not done or len(regs) < len(STORE_ORDER):
        return None
    tail = regs[-len(STORE_ORDER):]
    if tail[fc.MAGIC_AT] != MAGIC:
        return None
    return dict(zip(STORE_ORDER, tail))


# --------------------------------------------------------------------------- #
# the interrupt firing boundary, read out of the capture
# --------------------------------------------------------------------------- #
def entry_points(stream, pin):
    """Positions in the chip's ordered stream at which an EXTERNAL interrupt
    entry begins.  Policy: the boundary is replayed, its consequences computed.

      pin 0 (INTR) -- the first INTA cycle of each acknowledge pair.  Only the
                      pin can produce an INTA, so this is unambiguous.
      pin 1 (NMI)  -- no acknowledge; the entry's first bus cycles are the two
                      vector-table reads at 0x00008/0x0000A followed by the
                      three frame pushes.  A software `INT 2` in the program
                      would look identical, which is why the pushes are part
                      of the signature and why the count is reported.
      pin 2 (POLL) -- no entry at all.
    """
    out = []
    if pin == 0:
        prev = False
        for i, e in enumerate(stream):
            inta = e[0] == "INTA"
            if inta and not prev:
                out.append(i)
            prev = inta
    elif pin == 1:
        v = NMI_VECTOR * 4
        for i in range(len(stream) - 4):
            a, b = stream[i], stream[i + 1]
            if a[:4] == ("R", "MEMR", v, 0) and b[:4] == ("R", "MEMR", v + 2, 0):
                if all(stream[i + 2 + j][0] == "W" for j in range(3)):
                    out.append(i)
    return out


def _word(e):
    """The 16-bit value a WRITE event committed, or None if it is a byte cycle
    (a frame push at an odd SP splits, and then the frame is not readable as
    two clean words -- reported rather than guessed)."""
    if e[0] != "W" or len(e[4]) != 2:
        return None
    return e[4][0][1] | (e[4][1][1] << 8)


def frame_of(stream, i):
    """(cs, ip) out of the interrupt frame the chip pushed at entry `i`.
    The ROM pushes PSW (01F5), then PS (01F9), then PC (01FB), so the 2nd and
    3rd write cycles of the entry carry the resume address.  -> (-1, -1) when
    the capture window cut the frame short or the pushes were unaligned."""
    ws = []
    for j in range(i, min(len(stream), i + 12)):
        if stream[j][0] == "W":
            ws.append(stream[j])
            if len(ws) == 3:
                break
    if len(ws) < 3:
        return -1, -1
    cs, ip = _word(ws[1]), _word(ws[2])
    return (-1, -1) if cs is None or ip is None else (cs, ip)


# --------------------------------------------------------------------------- #
# per-seed work
# --------------------------------------------------------------------------- #
def regen(entry):
    """(image, meta, g, sha) -- the bit-reproducible regeneration path.

    Composes through `fuzz_campaign.compose_case`, which is THE ONE PLACE a
    fuzz case's image is built (task #38): a regeneration path that composes
    differently from the capture path is exactly the GEN-DRIFT the sha gate
    below exists to catch, and one function is the cheapest way never to have
    it.  ⚠ THAT IS NO LONGER A NO-OP FOR A v1 SEED: since fuzz-v2 D9 landed,
    `compose_case` applies the widened 0F scrub UNCONDITIONALLY, so a seed
    banked before it re-derives to a DIFFERENT sha256 wherever its image
    carried a forbidden `0F xx` pair, and this function reports GEN_DRIFT for
    it.  That is the intended consequence of the user's decision to discard the
    v1 corpus, not a defect in the regeneration path."""
    cfg = fzc.derive_case(entry["cid"], entry["k"], entry.get("ov") or {})
    g = fzc.build(cfg)
    image, meta = fzc.compose_case(g, cfg)
    return image, meta, g, hashlib.sha256(bytes(image)).hexdigest()


def window_of(recs):
    dend = fc._done_idx(recs)
    n = min(len(recs), LIMIT_ROWS)
    if dend is not None:
        n = min(n, dend + 8)
    return n


def prepare(path, opt):
    """-> (job, err).  `job` is the NDJSON record for the simulator plus the
    chip-side facts the comparison needs."""
    entry = json.loads(gzip.decompress(Path(path).read_bytes()))
    try:
        image, meta, g, sha = regen(entry)
    except Exception as e:                                   # noqa: BLE001
        return None, {"path": path, "cat": "REGEN_ERROR", "detail": str(e)[:200]}
    if sha != entry["image_sha256"]:
        return None, {"path": path, "cat": "GEN_DRIFT",
                      "detail": f"{sha[:16]} != {entry['image_sha256'][:16]}"}

    recs = entry["chip_rows"]
    win = window_of(recs)
    cstream = chip_stream(recs, win)

    evt = entry.get("evt")
    fires = []
    if evt and not opt["no_evt"]:
        fires = entry_points(cstream, evt.get("pin", 0))

    fill = g.get("fill", 0x90)
    rec = {"i": 0, "fill": fill,
           "hex": bytes(image).hex(),
           "max_ev": len(cstream) + 512,
           "max_ins": 20000,
           "tf": 1}
    if fires:
        frames = [frame_of(cstream, i) for i in fires]
        rec["evt"] = {"pin": evt.get("pin", 0), "at": fires,
                      "cs": [f[0] for f in frames],
                      "ip": [f[1] for f in frames]}
    if opt["stat_clobber"]:
        rec["stat_clobber"] = 0x5555
    job = {"path": path, "rec": rec, "cstream": cstream,
           "frames": [frame_of(cstream, i) for i in fires],
           "chip_arch": entry.get("chip_arch"), "win": win,
           "nrows": len(recs),
           "verdict": entry.get("verdict"), "sub": entry.get("sub"),
           "tier": entry.get("tier"), "k": entry["k"], "cid": entry["cid"],
           "waits": entry.get("waits"), "evt": evt,
           "n_ins": g.get("n_ins"), "fires": fires,
           "has_brkem": entry.get("has_brkem"), "has_tf": entry.get("has_tf"),
           "done_real": entry.get("done_real"),
           "rule_hits": entry.get("rule_hits", [])}
    return job, None


# The one documented don't-care in the whole comparison: the `8F /0 mod3`
# ghost read.  tests/v30/v0.1/metadata.json declares the ADDRESS and DATA of
# that single MEMR row a don't-care -- the undocumented register-destination
# POP writes no register, only SP += 2 and one discarded stack read whose
# committed address is stale internal address-latch state.  sw/check_core.py
# honours it for the single-instruction gates; the sequence gauntlet honours it
# the same way, and counts how many seeds it covers so it cannot go vacuous.
def _ghost_8f(ilog, ev_index):
    """True if the instruction covering functional event `ev_index` is
    8F with mod == 3."""
    ins = None
    for e in ilog or []:
        if e[0] <= ev_index:
            ins = e
        else:
            break
    if not ins or len(ins) < 5:
        return False
    return ins[3] == 0x8F and (ins[4] & 0xC0) == 0xC0


def classify(job, out, ilog=None):
    """-> result dict (cat + detail)."""
    r = {"path": job["path"], "cid": job["cid"], "k": job["k"],
         "tier": job["tier"], "verdict": job["verdict"],
         "waits": job["waits"], "evt": job["evt"], "fires": job["fires"],
         "n_ins": job["n_ins"], "chip_ev": len(job["cstream"])}
    if out is None:
        r["cat"] = "NO_OUTPUT"
        return r
    sstream = sim_stream(out["tx"])
    r["sim_ev"] = len(sstream)
    r["chip_halt"] = any(e[0] == "HALT" for e in job["cstream"])
    r["sim_halt"] = out.get("halt")
    r["sim_ins"] = out["ins"]
    r["sim_err"] = out.get("err")
    r["pfx"] = out.get("pfx")
    r["opm"] = out.get("opm")
    r["rep2"] = out.get("rep2")
    r["repbad"] = out.get("repbad")
    r["intem"] = out.get("intem")
    r["mfc"] = out.get("mfc")
    r["repok"] = out.get("repok")
    r["inta8080"] = out.get("inta8080")
    r["reppfx"] = out.get("reppfx")
    r["sim_fired"] = out.get("fired")
    r["frames"] = job.get("frames")

    # The HALT acknowledge is a STATUS-ONLY cycle: it carries no address and no
    # data, and whether the capture even yields a transaction for it depends on
    # whether the chip's T1 was followed by a T4 before it parked in Ti (a
    # halted V30 goes T1 -> Ti, and fuzz_classify.extract_txns only closes a
    # transaction on T4).  It is therefore not comparable evidence; the fact
    # that a side halted at all is compared separately.
    a = [e for e in job["cstream"] if e[0] != "HALT"]
    b = [e for e in sstream if e[0] != "HALT"]
    ghosts = 0
    while True:
        n = min(len(a), len(b))
        first = None
        for i in range(n):
            if a[i] != b[i]:
                first = i
                break
        if first is None or ilog is None:
            break
        # a MEMR whose only difference is the committed address, inside an
        # 8F mod3 -- the documented don't-care
        if (a[first][0] == "R" and b[first][0] == "R" and
                a[first][1] == b[first][1] == "MEMR" and
                _ghost_8f(ilog, first)):
            a = a[:first] + a[first + 1:]
            b = b[:first] + b[first + 1:]
            ghosts += 1
            continue
        break
    r["ghost_8f"] = ghosts
    r["first_bad"] = first
    if first is not None:
        r["cat"] = "STREAM"
        r["detail"] = (f"ev[{first}] chip={a[first]!r} sim={b[first]!r}")
        r["ctx"] = [[i, repr(a[i]), repr(b[i])]
                    for i in range(max(0, first - 3), min(n, first + 4))]
        return r
    if len(b) < len(a):
        # The simulator stopped short of the capture: a real failure unless it
        # ran out of its own budget.
        r["cat"] = "SIM_SHORT"
        r["detail"] = (f"sim stream {len(b)} < chip {len(a)}"
                       f" (err={out.get('err')}, halt={out.get('halt')})")
        return r

    ca = job["chip_arch"]
    if ca:
        sa = arch_of(sstream)
        if sa is None:
            r["cat"] = "ARCH_MISSING"
            r["detail"] = "the simulator's store stub never completed"
            return r
        diff = {k: (v, sa.get(k)) for k, v in ca.items() if sa.get(k) != v}
        if diff:
            r["cat"] = "ARCH"
            r["detail"] = " ".join(f"{k} chip={v[0]:04X} sim={v[1]:04X}"
                                   for k, v in diff.items())
            return r
        r["arch_checked"] = True
    r["cat"] = "OK"
    return r


_OPT = None


def _init(opt):
    global _OPT
    _OPT = opt


def _run_chunk(paths):
    jobs, results = [], []
    for p in paths:
        job, err = prepare(p, _OPT)
        if err:
            results.append(err)
        else:
            jobs.append(job)
    if jobs:
        payload = []
        for i, j in enumerate(jobs):
            j["rec"]["i"] = i
            payload.append(json.dumps(j["rec"], separators=(",", ":")))
        argv = [str(SIM), "image", str(ROM)]
        if _OPT["coverage"]:
            argv.append("--coverage")
        p = subprocess.run(argv, input="\n".join(payload).encode(),
                           stdout=subprocess.PIPE)
        outs = [None] * len(jobs)
        cov = None
        for line in p.stdout.decode().splitlines():
            if not line:
                continue
            o = json.loads(line)
            if "coverage" in o:
                cov = o["coverage"]
                continue
            if 0 <= o["i"] < len(outs):
                outs[o["i"]] = o
        for j, o in zip(jobs, outs):
            res = classify(j, o)
            if res["cat"] != "OK":
                # Second pass on the failures only: re-run this one image with
                # the per-instruction log so the documented 8F mod3 don't-care
                # can be recognised (and so the report can NAME the instruction
                # that produced the divergent bus event).
                j["rec"]["ilog"] = 1
                q = subprocess.run(argv, stdout=subprocess.PIPE,
                                   input=json.dumps(dict(j["rec"], i=0),
                                                    separators=(",", ":")
                                                    ).encode())
                for line in q.stdout.decode().splitlines():
                    if not line or '"coverage"' in line:
                        continue
                    o2 = json.loads(line)
                    res = classify(j, o2, ilog=o2.get("ilog"))
                    ins = None
                    for e in (o2.get("ilog") or []):
                        if res.get("first_bad") is not None and \
                                e[0] <= res["first_bad"]:
                            ins = e
                    res["at_ins"] = ins
                    break
            results.append(res)
        if cov:
            results.append({"cat": "_coverage", "coverage": cov})
    return results


# --------------------------------------------------------------------------- #
def main():
    # U1 / P-2.  EAGERLY, before any loop: `ArtifactError` is a
    # `RuntimeError`, and a per-case `except Exception` would turn one
    # sentence naming a stale binary into N unreadable case failures.
    simbin.ensure(why=__name__)
    ap = argparse.ArgumentParser()
    # ⚠ THE v1 CORPUS, `status: SUPERSEDED` SINCE 2026-08-09 (SUP-1,
    # docs/notes/invalidation_ledger.md).  MEASUREMENT TOOL, NOT A GATE:
    # the banks are NAMED here, deliberately, and nothing was moved or
    # deleted, so this default still resolves to the same 3,157 seeds.
    ap.add_argument("--bank", default="mc1,mc2,t30-raw")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--k", type=int, default=None,
                    help="run only this seed k (one bank)")
    ap.add_argument("--jobs", type=int, default=os.cpu_count())
    ap.add_argument("--chunk", type=int, default=8)
    ap.add_argument("--details", type=int, default=12)
    ap.add_argument("--report", default=None)
    ap.add_argument("--no-evt", action="store_true",
                    help="do not replay external events (diagnostic)")
    ap.add_argument("--stat-clobber", action="store_true",
                    help="Codex item 8: overwrite the ALU status latch on every "
                         "interrupt entry; a seed whose outcome CHANGES is a "
                         "seed that discriminates latch survival")
    ap.add_argument("--coverage", default=None,
                    help="accumulate micro-row coverage into this JSON")
    ap.add_argument("--census", action="store_true",
                    help="print the executed-opcode / prefix census (F1, A19)")
    a = ap.parse_args()

    opt = {"no_evt": a.no_evt, "stat_clobber": a.stat_clobber,
           "coverage": bool(a.coverage)}

    banks = [b for b in a.bank.split(",") if b]
    paths = []
    for b in banks:
        ps = sorted((BANK / b / "seeds").glob("*.json.gz"))
        if a.k is not None:
            ps = [p for p in ps if f"_{a.k}_" in p.name]
        if a.limit:
            ps = ps[:a.limit]
        paths += [str(p) for p in ps]
    if not paths:
        print("ucsim_fuzz: no seeds")
        return 2

    t0 = time.time()
    chunks = [paths[i:i + a.chunk] for i in range(0, len(paths), a.chunk)]
    results = []
    cover = [0] * 1028
    with Pool(a.jobs, initializer=_init, initargs=(opt,)) as pool:
        done = 0
        for res in pool.imap_unordered(_run_chunk, chunks):
            for r in res:
                if r.get("cat") == "_coverage":
                    for i, n in enumerate(r["coverage"]):
                        cover[i] += n
                else:
                    results.append(r)
            done += 1
            if done % 20 == 0:
                sys.stderr.write(f"\r  {len(results)}/{len(paths)} seeds "
                                 f"({time.time() - t0:.0f}s)")
                sys.stderr.flush()
    sys.stderr.write("\r" + " " * 60 + "\r")

    # ---------------- rollup ----------------
    per_bank = defaultdict(Counter)
    for r in results:
        per_bank[r.get("cid") or Path(r["path"]).parts[-3]][r["cat"]] += 1
    cats = Counter(r["cat"] for r in results)
    print(f"\nucsim_fuzz: {len(results)} seeds over {len(banks)} bank(s) "
          f"in {time.time() - t0:.1f}s")
    for b in banks:
        c = per_bank.get(b, Counter())
        tot = sum(c.values())
        ok = c.get("OK", 0)
        arch = sum(1 for r in results if r.get("cid") == b
                   and r.get("arch_checked"))
        print(f"  {b:10s} {ok}/{tot} OK   "
              f"[arch-compared {arch}]   "
              + "  ".join(f"{k}={v}" for k, v in sorted(c.items())
                          if k != "OK"))
    print(f"  TOTAL      {cats.get('OK', 0)}/{len(results)}   "
          + "  ".join(f"{k}={v}" for k, v in sorted(cats.items()) if k != "OK"))

    # Wait axes are TIMING-ONLY: the simulator has no wait input, so a chip
    # functional outcome that DID depend on waits would show up as one wait
    # class collapsing.  Printed every run so it cannot go unnoticed.
    def _wclass(r):
        w = r.get("waits") or {}
        return ("wrand%s" % w.get("wmax")) if w.get("wrand") \
            else ("w%s" % w.get("fixed"))
    wt, wok = Counter(), Counter()
    for r in results:
        wt[_wclass(r)] += 1
        if r["cat"] == "OK":
            wok[_wclass(r)] += 1
    print("  wait-class census (functional stream must be wait-invariant):")
    print("    " + "  ".join(f"{k}={wok[k]}/{wt[k]}" for k in sorted(wt)))

    bad = [r for r in results if r["cat"] != "OK"]
    for r in bad[:a.details]:
        print(f"\n  -- {r.get('cid')}/{r.get('k')} [{r.get('tier')}] "
              f"{r['cat']} verdict={r.get('verdict')} "
              f"waits={r.get('waits')} evt={r.get('evt')}")
        print(f"     {r.get('detail', '')[:400]}")
        for row in (r.get("ctx") or [])[:8]:
            print(f"       {row[0]:5d} chip {row[1]}")
            print(f"       {row[0]:5d} sim  {row[2]}")

    if a.census:
        pfx = [0] * 256
        opm = [0] * 256
        rep2 = []
        for r in results:
            for i, w in enumerate(r.get("pfx") or []):
                for bit in range(32):
                    if w >> bit & 1:
                        pfx[i * 32 + bit] += 1
            for i, w in enumerate(r.get("opm") or []):
                for bit in range(32):
                    if w >> bit & 1:
                        opm[i * 32 + bit] += 1
            for ch in (r.get("rep2") or []):
                rep2.append((r.get("cid"), r.get("k"), ch))
        print("\n  executed-prefix census (seeds in which the byte was "
              "consumed as a PREFIX):")
        print("    " + " ".join(f"{b:02X}:{n}" for b, n in enumerate(pfx) if n))
        print(f"  distinct opcode bytes executed: {sum(1 for n in opm if n)}/256")
        print(f"  conflicting REP-family chains (A19): {len(rep2)}")
        for cid, k, ch in rep2[:10]:
            print(f"    {cid}/{k}: " + " ".join(f"{x:02X}" for x in ch))

    if a.coverage:
        Path(a.coverage).write_text(json.dumps(cover))
        print(f"  coverage -> {a.coverage} "
              f"({sum(1 for x in cover if x)}/1028 rows)")

    if a.report:
        Path(a.report).write_text(json.dumps(results, indent=1))
        print(f"  report -> {a.report}")

    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
