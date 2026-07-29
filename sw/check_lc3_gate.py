#!/usr/bin/env python3
"""G-LC3 directed RMW-write gate (board-free standing gate). Proves the H-PHASE
Tw-parity RMW-write commit widen (`ext_ok_wr`, v30_biu.sv:660, gated by `tw_par`)
is INTACT: builds hand-crafted RMW mem-write gadgets (ADD/INC word[disp16]) at
the discriminating (kind/j/k/wv) configs found by sw/biu_law_lc3_gadget.py and
asserts the model bus stream matches the frozen baseline. Reverting the parity
widen to strict (M-LC3) changes the stream -> this gate FAILS. This is the
board-free MUTATION GATE for LC3; the SILICON PROVENANCE (even->early/odd->late
15/15) is the separate board uRMW capture. Uses the CURRENT Verilator binary.
NO board.

Exit 0 = LC3 widen intact, non-zero = changed (mutation caught / regression).
"""
import sys
import json
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "sw"))
import biu_law_lc3_gadget as G                       # noqa: E402

BASELINE = ROOT / "sw/lc3_gate_baseline.json"


def wv_for(name):
    if name.startswith("u"):
        return G.wv_uniform(int(name[1:]))
    ws, wmax = name[1:].split("_")
    return G.wv_rand(int(ws), int(wmax))


def digest_sha(kind, j, k, wv):
    img = G.build_image(kind, j, k)
    return hashlib.sha256(G.digest(img, wv_for(wv)).encode()).hexdigest()[:16]


def main():
    ref = json.loads(BASELINE.read_text())     # {"kind:j:k:wv": sha, ...}
    bad = []
    for key, sha in ref.items():
        kind, j, k, wv = key.split(":")
        cur = digest_sha(kind, int(j), int(k), wv)
        if cur != sha:
            bad.append((key, sha, cur))
    if bad:
        print("check_lc3_gate: FAIL (H-PHASE RMW-write parity widen changed)")
        for key, r, c in bad:
            print(f"  - {key}: ref={r} cur={c}")
        return 1
    print(f"check_lc3_gate: PASS ({len(ref)} RMW-write gadgets, "
          f"ext_ok_wr/tw_par widen intact)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
