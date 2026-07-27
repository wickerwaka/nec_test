#!/usr/bin/env python3
"""gen_raw - Tier B "raw bytes" generator for the massive fuzz expansion
(task #29).

Tier B abandons all structure: the payload (and, in whole-image mode, the
entire 0x0000-0xFEFF map) is uniform random bytes. The only guarantee is a
MANDATORY scrub pass that removes the handful of byte sequences that cannot be
allowed to reach the board because they wedge it rather than diverge:

  * 0F 34            - silent chip lockup (host reset required), and
    0F 35-0F 3F      - unprobed neighbours of the lockup,
    0F E0 / 0F F0    - V33 BRKXA/RETXA  ->  second byte forced to 0x90 (NOP)
  * F4 (HALT)        - a random DI/POPF can leave interrupts masked so an
    9B (POLL)          armed wake never arrives -> guaranteed timeout; both
                       bytes forced to 0x90 unconditionally, at ANY offset.
  * ED               - LEFT ALONE (native IN AW,DX here, not an 8080 lead).
  * other 0F >= 0x40 - LEFT IN: they alias BRKEM, the accepted 8080-gap class
                       that arrives "for free" and is recovered by per-run reset.

Tier B classification is window-only (fixed min(len,4000) window; a random
OUT 0xFC can forge the done marker, so done_idx is never trusted). The g-dict
matches the gen_seq/gen_soup contract plus extras (raw_mode, ivt_mode,
scrubbed counts, payload_sha1).
"""
import argparse
import hashlib
import random
import sys
from pathlib import Path

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
from gen_seq import PC0                              # noqa: E402  anchor 0:0x0500
from gen_soup import full_ivt, HANDLER_BYTES         # noqa: E402
import optable                                       # noqa: E402

IMG_HI = 0xFF00           # whole-image random band is 0x0000 .. IMG_HI-1
NOP = 0x90


def scrub(buf):
    """In-place scrub of a mutable byte buffer. Returns a dict of counts:
      pair0f  - banned 0F second-bytes rewritten to NOP (lockup + BRKXA band)
      halt    - F4 bytes rewritten to NOP
      poll    - 9B bytes rewritten to NOP
    ED is deliberately untouched; 0F >= 0x40 (BRKEM aliases) are left in."""
    counts = {"pair0f": 0, "halt": 0, "poll": 0}
    n = len(buf)
    # 0F pairs: walk only the 0F positions (find is C-fast), not every byte
    pos = 0
    while True:
        i = buf.find(0x0F, pos)
        if i < 0 or i >= n - 1:
            break
        if buf[i + 1] in optable.HARD_BANNED_0F:
            buf[i + 1] = NOP
            counts["pair0f"] += 1
        pos = i + 1
    # F4/9B -> NOP: count + a single C-level translate
    counts["halt"] = buf.count(0xF4)
    counts["poll"] = buf.count(0x9B)
    if counts["halt"] or counts["poll"]:
        buf[:] = bytes(buf).translate(_HALT_POLL_TABLE)
    return counts


_HALT_POLL_TABLE = bytes(NOP if x in (0xF4, 0x9B) else x for x in range(256))


def gen_raw(seed, whole_frac=0.70, ivt_overlay_frac=0.50):
    """-> g-dict (compose-ready) + raw provenance extras.

    raw_mode = 'whole' (0x0000-0xFEFF random) or 'payload' (random chunk at the
    anchor over a NOP field). ivt_mode = 'iret' (full IVT -> IRET handler) or
    'random' (IVT left random; whole-image only)."""
    rng = random.Random(f"raw/{seed}")
    whole = rng.random() < whole_frac
    plen = rng.randrange(256, 1025)
    payload = bytearray(rng.randbytes(plen))

    regs = {"PS": 0, "PC": PC0, "SS": 0, "SP": 0x3F00,
            "PSW": 0xF202,
            "AW": rng.getrandbits(16), "BW": rng.getrandbits(16),
            "CW": rng.getrandbits(16), "DW": rng.getrandbits(16),
            "BP": rng.getrandbits(16),
            "DS0": rng.getrandbits(16), "DS1": rng.getrandbits(16),
            "IX": rng.getrandbits(16), "IY": rng.getrandbits(16)}

    if whole:
        # place the raw payload at the compose anchor BEFORE scrubbing, so the
        # ram|payload seam at PC0-1|PC0 is scrubbed IN CONTEXT (an independently
        # scrubbed payload + ram can leave a banned pair straddling that seam -
        # a real chip-lockup hazard). instr is then the in-image scrubbed slice.
        img = bytearray(rng.randbytes(IMG_HI))
        img[PC0:PC0 + plen] = payload
        sc = scrub(img)
        instr = bytes(img[PC0:PC0 + plen])
        ram = list(enumerate(img))
        ivt_iret = rng.random() < ivt_overlay_frac
        if ivt_iret:
            ram += HANDLER_BYTES               # last-wins over the random fill
            ivt = full_ivt()
            ivt_mode = "iret"
        else:
            ivt = None
            ivt_mode = "random"
        raw_mode = "whole"
    else:
        # payload-only: the surrounding map is compose's 0x90 NOP fill, so the
        # PC0-1 seam byte is 0x90 (no cross-boundary pair possible).
        sc = scrub(payload)
        instr = bytes(payload)
        ram = list(HANDLER_BYTES)
        ivt = full_ivt()
        ivt_mode = "iret"
        raw_mode = "payload"

    payload_sha1 = hashlib.sha1(instr).hexdigest()

    return dict(seed=seed, instr=instr, regs=regs, ram=ram, ivt=ivt,
                n_ins=0, forms=["raw"], ins=[instr],
                raw_mode=raw_mode, ivt_mode=ivt_mode,
                scrubbed=sc, payload_sha1=payload_sha1)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("seed")
    ap.add_argument("--dump", action="store_true")
    a = ap.parse_args()
    g = gen_raw(a.seed)
    print(f"seed {g['seed']}: mode={g['raw_mode']} ivt={g['ivt_mode']} "
          f"plen={len(g['instr'])} scrub={g['scrubbed']} "
          f"sha1={g['payload_sha1'][:12]}")
    if a.dump:
        print(g["instr"].hex())


if __name__ == "__main__":
    main()
