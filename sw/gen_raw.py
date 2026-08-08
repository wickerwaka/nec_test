#!/usr/bin/env python3
"""gen_raw - Tier B "raw bytes" generator for the massive fuzz expansion
(task #29).

Tier B abandons all structure: the payload (and, in whole-image mode, the
entire 0x0000-0xFEFF map) is uniform random bytes. The only guarantee is a
MANDATORY scrub pass, and since the fuzz-v2 D9 landing it is ONE RULE, held in
`optable.scrub_0f`:

  * a 0F byte may be followed ONLY by a byte in optable.SCRUB_ALLOWED_0F (the
    documented extension whitelist minus BRKEM); every other 0F xx pair is
    rewritten to `90 90`.  That covers the 0F 34 lockup, the unprobed 0F 35-3F,
    V33 BRKXA/RETXA 0F E0/F0, BRKEM 0F FF, AND its entire >= 0x40 alias band -
    the surface `docs/facts/undocumented_0f.md` measured on silicon, which the
    two rules that stood here before covered about 1/192 of.
  * ED               - LEFT ALONE (native IN AW,DX here, not an 8080 lead).
  * F4 (HALT) / 9B (POLL) - NO LONGER SCRUBBED.  Their premise was a masked
    interrupt leaving an armed wake undelivered; plan D3's terminating NMI is
    non-maskable and its handler does not return, so both wake.  A coverage
    gain the terminator pays for, and sound only once it exists.

Tier B classification is window-only (fixed min(len,4000) window; a random
OUT 0xFC can forge the done marker, so done_idx is never trusted). The g-dict
matches the gen_seq/gen_soup contract plus extras (raw_mode, ivt_mode,
scrubbed counts, payload_sha1).

FUZZ v2 (task T2): the anchor is `gen_soup.ANCHOR` (inside the code region),
the segment registers come from `gen_soup.Bias`, the IVT is ALWAYS composed
(`ivt_overlay_frac` is gone) and the whole-image random band stops at the
handler table so a raw seed cannot erase the structures that terminate it.
"""
import argparse
import hashlib
import random
import sys
from pathlib import Path

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
from gen_soup import (ANCHOR, Bias, full_ivt,        # noqa: E402
                      handler_bodies, HANDLER_BYTES, SP0)
import optable                                       # noqa: E402
import testimage as ti                               # noqa: E402

IMG_HI = 0xFF00           # whole-image random band is 0x0000 .. IMG_HI-1


def scrub(buf, spans=None):
    """In-place scrub of a mutable byte buffer. Returns a dict of counts:
      pair0f  - 0F pairs rewritten to `90 90` by THE 0F RULE

    THE RULE ITSELF LIVES IN `optable.scrub_0f` and nowhere else, so this
    generation-time pass and `fuzz_campaign.compose_case`'s composed-image pass
    cannot drift apart.  `spans` is the code region (None = the whole buffer);
    see `optable.CODE_SPANS` for why the IVT and the data window are out."""
    return {"pair0f": optable.scrub_0f(buf, spans)}


def gen_raw(seed, whole_frac=0.70):
    """-> g-dict (compose-ready) + raw provenance extras.

    raw_mode = 'whole' (0x0000-0xFEFF random) or 'payload' (random chunk at the
    anchor over the 0xCC fill).

    `ivt_overlay_frac` IS GONE (plan D9's critical-files row: "the IVT is always
    composed").  Its 'random' arm left the IVT as raw bytes, which under v2 is
    not breadth but a hole: an escape traps to a vector that points anywhere,
    so the seed can neither terminate nor be scored.  `ivt_mode` is retained on
    the result line and is now always 'handlers'."""
    rng = random.Random(f"raw/{seed}")
    b = Bias(seed)
    whole = rng.random() < whole_frac
    plen = rng.randrange(256, 1025)
    payload = bytearray(rng.randbytes(plen))

    regs = {"PS": b.seg("PS"), "PC": b.off(ANCHOR),
            "SS": b.seg("SS"), "SP": b.off(SP0),
            "DS0": b.seg("DS0"), "DS1": b.seg("DS1"),
            "PSW": 0xF202,
            "AW": rng.getrandbits(16), "BW": rng.getrandbits(16),
            "CW": rng.getrandbits(16), "DW": rng.getrandbits(16),
            "BP": rng.getrandbits(16),
            "IX": rng.getrandbits(16), "IY": rng.getrandbits(16)}

    if whole:
        # place the raw payload at the compose anchor BEFORE scrubbing, so the
        # ram|payload seam at ANCHOR-1|ANCHOR is scrubbed IN CONTEXT (an
        # independently scrubbed payload + ram can leave a banned pair
        # straddling that seam - a real chip-lockup hazard). instr is then the
        # in-image scrubbed slice.
        img = bytearray(rng.randbytes(IMG_HI))
        img[ANCHOR:ANCHOR + plen] = payload
        # the WHOLE random band, not `optable.CODE_SPANS`: nothing in this
        # buffer is a designed structure yet -- compose lays the IVT, the
        # handlers and the loader page over it afterwards -- so every byte here
        # is potential code, including the 0F 34 that LOCKS THE CHIP.  The
        # region scoping belongs at `compose_case`, where the designed
        # structures exist and a rewrite could corrupt one.
        sc = scrub(img)
        instr = bytes(img[ANCHOR:ANCHOR + plen])
        # THE RANDOM BAND STOPS WHERE THE MAP'S FIXED STRUCTURES BEGIN.
        # `compose` lays the handler table and the terminator down BEFORE the
        # ram placements, so a whole-image raw seed used to overwrite both with
        # uniform random bytes: the terminator could not run (no dump, ever)
        # and the 8 interrupt handlers became random code that traps and
        # recurses without bound -- the exact failure D8 exists to close, let
        # in through the back door.  Two half-open pages, no other exception:
        # the IVT, the anchor body and the loader page are all composed AFTER
        # ram and win on their own.
        ram = [(a, v) for a, v in enumerate(img)
               if not (ti.IHT_AT <= a < ti.CODE_HI)]
        ram += HANDLER_BYTES                   # last-wins over the random fill
        raw_mode = "whole"
    else:
        # payload-only: this buffer IS the whole span, so no spans argument.
        # The v2 surround is 0xCC (INT3), and 0xCC >= 0x40 makes `0F CC` a
        # BRKEM alias, so the seam matters in BOTH directions now: the leading
        # seam is safe because 0xCC is not 0x0F, and the trailing one is closed
        # by `scrub_0f`'s end-of-span clause, which NOPs a `0F` sitting on the
        # last byte.  `compose_case`'s pass over the composed image is the
        # backstop that proves it on the artifact.
        sc = scrub(payload)
        instr = bytes(payload)
        ram = list(HANDLER_BYTES)
        raw_mode = "payload"

    payload_sha1 = hashlib.sha1(instr).hexdigest()

    return dict(seed=seed, instr=instr, regs=regs, ram=ram,
                ivt=full_ivt(b, rng), handlers=handler_bodies(seed),
                n_ins=0, forms=["raw"], ins=[instr],
                raw_mode=raw_mode, ivt_mode="handlers",
                phys={"PC": ANCHOR, "SP": SP0},
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
