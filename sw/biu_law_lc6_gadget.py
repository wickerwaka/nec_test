#!/usr/bin/env python3
"""G-LC6 directed strio gadget (board-free). Builds a NON-REP OUTS single
(0x6E/0x6F) — the Family-5 `eu_rsv_strio` uline-1 veto cell (v30_eu.sv:1688) —
and sweeps queue-fill (k pre-NOPs) x leading-phase (j NOPs) x wvec to find a
config where breaking the LC6 pick_t3 veto changes the OBSERVABLE model bus
stream. That config becomes the directed G-LC6 gate. OUTS (not INS) so no I/O
read serving is needed (a port WRITE only). NO board.

Prints DISCRIMINATOR lines; writes the winning (op,j,k,ws,wmax) to
sw/biu_law_lc6_gadget.json. Always restores the RTL via git checkout.
"""
import subprocess
import sys
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "sw"))
import gen_seq                                    # noqa: E402
from gen_seq import Prog, PC0, SP0, DATA_LO, DATA_HI  # noqa: E402
from check_seq import compose                     # noqa: E402
from causal_wrand import run_tb_internal, accesses  # noqa: E402
BIU = ROOT / "hdl/rtl/core/v30_biu.sv"

LC6_OLD = "wire        pick_t3    = want_half2 || want_eu || (prefetch_ok && !eu_rsv_strio);"
LC6_NEW = "wire        pick_t3    = want_half2 || want_eu || prefetch_ok;"


def build_image(op, j_lead, k_fill, trailing=12):
    """A directed strio-single program: j leading NOPs (grid phase) + a non-REP
    OUTS single with k queue-fill NOPs ahead of it + trailing NOPs (prefetch
    contention after the strio completion eval)."""
    rng = random.Random("lc6-gadget")
    p = Prog(rng)
    ix = 0x2500
    iy = 0x2A00
    port = 0x40                                    # safe even band
    for _ in range(j_lead):
        p.emit([0x90])
    setup = [
        bytes([0xBE, ix & 0xFF, ix >> 8]),         # MOV SI, ix
        bytes([0xBF, iy & 0xFF, iy >> 8]),         # MOV DI, iy
        bytes([0xBA, port & 0xFF, port >> 8]),     # MOV DX, port
        [0xFC],                                    # CLD
    ]
    seq = setup + [[0x90]] * k_fill + [[op]]       # non-REP [seg] OUTS
    p.emit_atomic(seq)
    for _ in range(trailing):
        p.emit([0x90])
    instr = p.assemble()
    regs = {"PS": 0, "PC": PC0, "SS": 0, "SP": SP0,
            "DS0": 0, "DS1": 0, "PSW": 0xF202,
            "AW": 0x1234, "BW": 0x2345, "CW": 0x0003, "DW": port,
            "BP": 0x3456, "IX": ix, "IY": iy}
    ram = [(a, rng.getrandbits(8)) for a in range(DATA_LO, DATA_HI + 0x100)]
    ram += [(a, rng.getrandbits(8)) for a in range(0x3E00, 0x4000)]
    g = dict(seed=0, instr=instr, regs=regs, ram=ram, ivt=None)
    image, _meta = compose(g)
    return image


def wv_of(ws, wmax):
    rr = random.Random((ws << 8) | wmax)
    return [rr.randint(0, wmax) for _ in range(4096)]


def digest(image, ws, wmax):
    wv = wv_of(ws, wmax)
    rows = run_tb_internal(image, 4200, wv)
    acc = accesses([dict(t=r["t"], bs_early=r["bs"], qs=r["qs"],
                         ad_addr=r["addr"], ad_data=0) for r in rows])
    parts, prev = [], None
    for a in acc:
        gap = "" if prev is None else str(a['t1'] - prev)
        parts.append(f"{a['bs']},{a['tw']},{a['addr']},{a['npops']},g{gap}")
        prev = a['t1']
    return ";".join(parts)


def sh(cmd):
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=1200)


def build():
    # STALE-BINARY GUARD (class5 rule #2): a syntax-broken mutation makes
    # verilator exit non-zero; raise so we never sweep on a stale binary.
    # --core fsm EXPLICIT: this tool mutates hdl/rtl/core/v30_biu.sv (the
    # ARCHIVED FSM core) and has no ucore counterpart.  Pinned when
    # check_core.py's default flipped fsm -> ucore, 2026-08-04.
    r = sh([sys.executable, "sw/check_core.py", "--build", "--core", "fsm",
            "--suite-dir",
            "tests/v30/v0.1", "--opcodes", "all", "--cases", "1", "--waits", "0"])
    if r.returncode != 0:
        raise RuntimeError("verilator build FAILED (stale-binary guard)")


def restore():
    sh(["git", "checkout", "--", "hdl/rtl/core/v30_biu.sv"])


OPS = [0x6E, 0x6F]                                 # OUTSB, OUTSW
JS = range(0, 8)                                   # leading-phase NOPs
KS = range(0, 12)                                  # queue-fill NOPs
WVECS = [(0, 0), (5, 1), (7, 3), (11, 7), (3, 7), (9, 5)]


def main():
    print("=== G-LC6 strio gadget search ===", flush=True)
    restore()
    # precompute all gadget images (RTL-independent)
    imgs = {}
    for op in OPS:
        for j in JS:
            for k in KS:
                imgs[(op, j, k)] = build_image(op, j, k)
    print(f"built {len(imgs)} gadget images", flush=True)

    print("baseline (unmutated) build + digests...", flush=True)
    build()
    base = {}
    for key, img in imgs.items():
        for ws, wmax in WVECS:
            try:
                base[key + (ws, wmax)] = digest(img, ws, wmax)
            except Exception as e:
                base[key + (ws, wmax)] = f"ERR:{e}"
    print("baseline done", flush=True)

    print("mutated (M-LC6) build + digests...", flush=True)
    t = BIU.read_text()
    assert t.count(LC6_OLD) == 1
    BIU.write_text(t.replace(LC6_OLD, LC6_NEW, 1))
    hits = []
    try:
        build()
        for key, img in imgs.items():
            for ws, wmax in WVECS:
                b = base.get(key + (ws, wmax))
                if not isinstance(b, str) or b.startswith("ERR"):
                    continue
                try:
                    m = digest(img, ws, wmax)
                except Exception as e:
                    m = f"ERR:{e}"
                if m != b:
                    op, j, k = key
                    hit = dict(op=op, j=j, k=k, ws=ws, wmax=wmax)
                    hits.append(hit)
                    print(f"  DISCRIMINATOR op={op:#x} j={j} k={k} ws={ws} "
                          f"wmax={wmax}", flush=True)
                    if len(hits) >= 6:
                        break
            if len(hits) >= 6:
                break
    finally:
        restore()

    Path(ROOT / "sw/biu_law_lc6_gadget.json").write_text(
        json.dumps(hits, indent=1) + "\n")
    print(f"=== LC6_GADGET_DONE hits={len(hits)} ===", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    finally:
        restore()
