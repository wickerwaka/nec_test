#!/usr/bin/env python3
"""G-LC3 directed RMW-write gadget (board-free MUTATION GATE). Builds an RMW
mem-write (ADD word[disp16],imm / INC word[disp16] — the eu_defer_wr / S_WREQ
path, the H-PHASE cell v30_biu.sv:660) and sweeps leading-phase (j) x queue-fill
(k) x wvec (uniform w1..w5 + random) to find a config where reverting the
`ext_ok_wr` Tw-parity widen (M-LC3: !tw_par -> 1'b0) changes the OBSERVABLE model
bus stream. That config becomes the board-free G-LC3 gate (silicon provenance =
the board uRMW capture, taken separately). NO board here.

Mirrors sw/biu_law_lc6_gadget.py. Prints DISCRIMINATOR lines; writes hits to
sw/biu_law_lc3_gadget.json. Restores RTL via git checkout.
"""
import subprocess
import sys
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "sw"))
from gen_seq import Prog, PC0, SP0, DATA_LO, DATA_HI  # noqa: E402
from check_seq import compose                     # noqa: E402
from causal_wrand import run_tb_internal, accesses  # noqa: E402
BIU = ROOT / "hdl/rtl/core/v30_biu.sv"

# M-LC3: revert the H-PHASE ext_ok_wr widen to strict (the SAME mutation the
# battery uses). Syntactically valid (no stale-binary trap).
LC3_OLD = "(eu_ready_p1 && !eu_ready_p2 && !tw_par);"
LC3_NEW = "(eu_ready_p1 && !eu_ready_p2 && 1'b0);"

MEM = 0x2500                                       # DS:0 -> data window


def rmw_bytes(kind):
    lo, hi = MEM & 0xFF, MEM >> 8
    if kind == "ADD":       # ADD word [disp16], imm16  (81 /0)
        return bytes([0x81, 0x06, lo, hi, 0x01, 0x00])
    if kind == "INC":       # INC word [disp16]         (FF /0)
        return bytes([0xFF, 0x06, lo, hi])
    if kind == "NEG":       # NEG word [disp16]         (F7 /3)
        return bytes([0xF7, 0x1E, lo, hi])
    raise ValueError(kind)


def build_image(kind, j_lead, k_fill, trailing=8):
    # k_fill is now the RMW-write COUNT: a back-to-back RMW-write sequence
    # sustains queue-drain competition (each write's readiness races a refill
    # prefetch at its T4 -- the eval_ext eu_defer_wr cell the H-PHASE widen
    # arbitrates). j_lead NOPs shift the leading bus-grid phase.
    rng = random.Random("lc3-gadget")
    p = Prog(rng)
    for _ in range(j_lead):
        p.emit([0x90])
    for _ in range(max(1, k_fill)):
        p.emit(rmw_bytes(kind))
    for _ in range(trailing):
        p.emit([0x90])
    instr = p.assemble()
    regs = {"PS": 0, "PC": PC0, "SS": 0, "SP": SP0,
            "DS0": 0, "DS1": 0, "PSW": 0xF202,
            "AW": 0x1234, "BW": 0x2345, "CW": 0x0003, "DW": 0x0040,
            "BP": 0x3456, "IX": 0x2500, "IY": 0x2A00}
    ram = [(a, rng.getrandbits(8)) for a in range(DATA_LO, DATA_HI + 0x100)]
    ram += [(a, rng.getrandbits(8)) for a in range(0x3E00, 0x4000)]
    image, _meta = compose(dict(seed=0, instr=instr, regs=regs, ram=ram, ivt=None))
    return image


def wv_uniform(w):
    return [w] * 4096


def wv_rand(ws, wmax):
    rr = random.Random((ws << 8) | wmax)
    return [rr.randint(0, wmax) for _ in range(4096)]


def digest(image, wv):
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


KINDS = ["ADD", "INC"]
JS = range(0, 8)
KS = range(1, 9)   # RMW-write count
# H-PHASE lives on Tw parity -> sweep uniform w1..w6 (parity flips per +1 wait)
# plus a few random-per-cycle vectors.
WVS = [("u%d" % w, wv_uniform(w)) for w in range(1, 9)] + \
      [("r5_1", wv_rand(5, 1)), ("r7_3", wv_rand(7, 3)), ("r11_7", wv_rand(11, 7))]


def main():
    print("=== G-LC3 RMW gadget search ===", flush=True)
    restore()
    imgs = {(kind, j, k): build_image(kind, j, k)
            for kind in KINDS for j in JS for k in KS}
    print(f"built {len(imgs)} RMW gadget images", flush=True)

    print("baseline (unmutated) build + digests...", flush=True)
    build()
    base = {}
    for key, img in imgs.items():
        for wname, wv in WVS:
            try:
                base[key + (wname,)] = digest(img, wv)
            except Exception as e:
                base[key + (wname,)] = f"ERR:{e}"
    print("baseline done", flush=True)

    print("mutated (M-LC3 strict) build + digests...", flush=True)
    t = BIU.read_text()
    assert t.count(LC3_OLD) == 1
    BIU.write_text(t.replace(LC3_OLD, LC3_NEW, 1))
    hits = []
    try:
        build()
        for key, img in imgs.items():
            for wname, wv in WVS:
                b = base.get(key + (wname,))
                if not isinstance(b, str) or b.startswith("ERR"):
                    continue
                try:
                    m = digest(img, wv)
                except Exception as e:
                    m = f"ERR:{e}"
                if m != b:
                    kind, j, k = key
                    hits.append(dict(kind=kind, j=j, k=k, wv=wname))
                    print(f"  DISCRIMINATOR kind={kind} j={j} k={k} wv={wname}",
                          flush=True)
                    if len(hits) >= 8:
                        break
            if len(hits) >= 8:
                break
    finally:
        restore()

    Path(ROOT / "sw/biu_law_lc3_gadget.json").write_text(
        json.dumps(hits, indent=1) + "\n")
    print(f"=== LC3_GADGET_DONE hits={len(hits)} ===", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    finally:
        restore()
