#!/usr/bin/env python3
"""wvec_shapes -- the PER-ACCESS WAIT VECTOR axis of the random-wait fuzz
campaign (task #38, W0).

A wait VECTOR is one Tw count per BUS CYCLE, indexed by the bus-cycle ordinal
counted from the run's start.  Three independent implementations index it with
that one ordinal and they are the reason this axis exists at all:

  the board   `hdl/rtl/wvec_buf.sv` (1024 x 32 bit = 4096 byte entries) read by
              `hdl/rtl/nec_bus.sv` at `bus_idx`, armed by `WRAND.replay`.
              Applied by the SAME buffer to the socketed chip and to the fabric
              core, so an A/B pair differs in the core and in nothing else.
  the TB      `hdl/tb/tb_v30_core.sv` `+wvec=<file>` -> `wvec_arr[wbus_idx]`.
  the model   `sim/biu_timed.cpp::next_waits` -> `wvec_[bus_idx_]`,
              `v30sim timed-boot --wvec=<file>`.

The index agreement is MEASURED, not assumed: `ucore_provenance.md` §68.6's
bar R0 scored the chip's ACHIEVED per-cycle waits against the vector it was
handed at **45,699 / 45,699 = 100.0 %** over 186 fresh captures.

--------------------------------------------------------------------------- #
FOUR PROPERTIES OF THE RIG THAT THIS MODULE EXISTS TO NOT TRIP OVER.  Each is
read off the RTL / the C++ / the host code named beside it, and each one is a
place where the three implementations do something DIFFERENT.

  (1) THE FILE ENCODINGS ARE NOT THE SAME, AND THE MISMATCH IS SILENT.
      The TB reads its vector with `$readmemh` -- HEX.  The model reads its
      vector with `fscanf(f, "%d")` -- DECIMAL (`sim/timed_runner.cpp:404`).
      Hand a TB-format file to the model and `1f` parses as `1`, the next
      `%d` fails on `f`, the loop STOPS, and the model silently runs the
      truncated vector with the uniform `--waits` level after it.  There is no
      diagnostic anywhere.  So this module NEVER writes "a wvec file"; it
      writes `write_tb()` or `write_sim()`, and `check_encodings()` proves on
      every lint that the two round-trip to the same list.

  (2) THE OUT-OF-RANGE BEHAVIOURS ARE THREE DIFFERENT THINGS.
      Past the end of the loaded vector the model falls back to the UNIFORM
      `--waits` level (`biu_timed.cpp:156`); the TB reads its zero-filled
      array and gets 0 (`tb_v30_core.sv:128`); the board's `bus_idx` is 12
      bits and WRAPS to entry 0 of whatever is still in the RAM.  The rule
      that makes all three agree is: ALWAYS EMIT EXACTLY `NWVEC` ENTRIES and
      never let a run exceed `NWVEC` bus cycles.  `bus_cycle_bound()` is the
      measurement that says a capture stayed inside it.

  (3) THE BOARD'S REPLAY RAM IS NOT CLEARED BETWEEN RUNS.
      `v30ctl.Harness.load_wvec` writes only `len(tw_list)` bytes.  A short
      load therefore leaves the PREVIOUS run's bytes in the tail, and the
      chip reads them.  Same rule as (2): always exactly `NWVEC`.

  (4) THE FIELD IS FIVE BITS, NOT EIGHT.
      `nec_bus.sv` takes `wvec_byte[4:0]`, the TB takes `wvec_arr[..][4:0]`,
      the model takes `wvec_[k] & 31`.  All three mask identically, so a
      value above 31 is not a divergence -- it is a LIE in the ledger about
      what the part was told.  `build()` refuses to emit one.

--------------------------------------------------------------------------- #
THE SHAPES.  Five, each with a stated purpose and at most four parameters.
A large fitted family of shapes would be the same mistake as a large fitted
law table; these are five simple stimuli, and the campaign reads them against
the `fixed` and `wrand` controls that already exist.

  uni    i.i.d. uniform over 0..wmax.  The wrand LFSR's distribution with a
         HOST-side draw instead of the rig's own generator, so any agreement
         that depends on the LFSR mirror rather than on the wait VALUES is
         separated from any that does not.  This is the control shape.
  walk   a flat baseline with `+extra` on one access in every `period`.
         `period` is co-prime with the natural 4/5/6-clock bus cadence, so the
         perturbation DRIFTS across the program's own arbitration instants one
         clock at a time without anybody having to predict where they are.
         This is §65.2's "move the EU request in CLOCK steps" made
         self-sweeping; §68.6 drove the measured-period form of it.
  skew   alternating BLOCKS of `wlo` and `whi`, block length >= 16 accesses.
         The point is the block INTERIOR: after 8+ accesses at one level the
         prefetcher is in STEADY STATE rather than recovering, which is the
         one H3-B stimulus §68.6 named and did not try -- all three that were
         tried reach the access through an `EB 00` flush and a cold refill.
  burst  a quiet baseline with a single very long wait every `gap` accesses.
         The high end of the 5-bit field, which the LFSR reduction
         `(x*(wmax+1))>>8` reaches only at wmax=15 and never above it.
  edge   i.i.d. over {0, 1, 30, 31} -- the corners of the field, and the
         0-vs-1 boundary where "no Tw row at all" turns into "one Tw row".

Everything here is a pure function of `(cid, k, spec)`; nothing reads a
capture, so a banked seed's vector regenerates offline forever.  The vector is
banked in FULL anyway (`wvec_hex`), because a vector that only exists as a
derivation is a vector nobody can check the rig against.
"""
import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))

NWVEC = 4096          # wvec_buf.sv: 1024 words x 4 bytes.  Hard, all three legs.
WFIELD = 31           # the applied field is [4:0] in all three legs.

SHAPES = ("uni", "walk", "skew", "burst", "edge")


# --------------------------------------------------------------------------- #
# the per-seed draw
# --------------------------------------------------------------------------- #
def draw_spec(cid, k, shape):
    """The shape's parameters for seed `cid/k`, drawn from a namespace of this
    axis's OWN (`wrfuzz/...`), never from `derive_axes`'s stream.

    This is `derive_case`'s `force_wrand` / `force_evt` precedent exactly: a
    new axis must not consume draws from the frozen seed->axes derivation, or
    every banked seed in the tree re-derives to a different program."""
    r = random.Random(f"wrfuzz/{cid}/{k}/{shape}")
    if shape == "uni":
        return {"shape": "uni", "wmax": r.choice([1, 2, 3, 7, 15]),
                "seed": r.getrandbits(16)}
    if shape == "walk":
        period = r.choice([5, 7, 11, 13])
        return {"shape": "walk", "w": r.choice([0, 1, 2, 3]),
                "extra": r.choice([1, 2, 3]), "period": period,
                "phase": r.randrange(period)}
    if shape == "skew":
        blk = r.choice([16, 24, 32])
        return {"shape": "skew", "wlo": r.choice([0, 1]),
                "whi": r.choice([3, 7, 15]), "blk": blk,
                "phase": r.randrange(2 * blk)}
    if shape == "burst":
        gap = r.choice([29, 37, 53])
        return {"shape": "burst", "wbase": r.choice([0, 1]),
                "wbig": r.choice([16, 24, 31]), "gap": gap,
                "phase": r.randrange(gap)}
    if shape == "edge":
        return {"shape": "edge", "seed": r.getrandbits(16)}
    raise ValueError(f"unknown wvec shape {shape!r}")


EDGE_POOL = (0, 1, 30, 31)


def build(spec, n=NWVEC):
    """spec -> a list of exactly `n` Tw counts, each 0..31.

    RAISES on an out-of-field value rather than masking it: all three legs
    mask identically, so masking here would be correct in the machine and
    false in the ledger."""
    s = spec["shape"]
    if s == "uni":
        r = random.Random(f"uni/{spec['seed']}/{spec['wmax']}")
        v = [r.randrange(0, spec["wmax"] + 1) for _ in range(n)]
    elif s == "walk":
        w, ex, p, ph = spec["w"], spec["extra"], spec["period"], spec["phase"]
        v = [w + ex if (i % p) == ph else w for i in range(n)]
    elif s == "skew":
        lo, hi, b, ph = spec["wlo"], spec["whi"], spec["blk"], spec["phase"]
        v = [hi if (((i + ph) // b) & 1) else lo for i in range(n)]
    elif s == "burst":
        base, big, g, ph = spec["wbase"], spec["wbig"], spec["gap"], spec["phase"]
        v = [big if ((i + ph) % g) == 0 else base for i in range(n)]
    elif s == "edge":
        r = random.Random(f"edge/{spec['seed']}")
        v = [r.choice(EDGE_POOL) for _ in range(n)]
    else:
        raise ValueError(f"unknown wvec shape {s!r}")
    bad = [(i, x) for i, x in enumerate(v) if not (0 <= x <= WFIELD)]
    if bad:
        raise ValueError(f"wvec {spec}: {len(bad)} entries outside [0,{WFIELD}], "
                         f"first {bad[0]}")
    return v


# --------------------------------------------------------------------------- #
# banking / transport
# --------------------------------------------------------------------------- #
def to_hex(v):
    """The banked form: `2*len(v)` hex chars, entry k at chars [2k, 2k+2).
    Literal and complete -- NOT a digest and NOT a derivation."""
    return "".join(f"{x:02x}" for x in v)


def from_hex(s):
    return [int(s[i:i + 2], 16) for i in range(0, len(s), 2)]


def sha256_of(v):
    return hashlib.sha256(bytes(v)).hexdigest()


def write_tb(path, v):
    """`+wvec=<path>` for `hdl/tb/tb_v30_core.sv`.  $readmemh -> HEX."""
    Path(path).write_text("\n".join(f"{x & 0xFF:02x}" for x in v) + "\n")
    return str(path)


def write_sim(path, v):
    """`--wvec=<path>` for `v30sim timed-boot`.  fscanf %d -> DECIMAL."""
    Path(path).write_text("\n".join(str(int(x)) for x in v) + "\n")
    return str(path)


def check_encodings(v, tmpdir):
    """Round-trip both writers and prove they mean the same list.  This is the
    non-vacuity test for property (1) above: it FAILS if `write_sim` is ever
    given the TB's spelling or the other way round."""
    tb = Path(tmpdir) / "wv_tb.hex"
    sm = Path(tmpdir) / "wv_sim.txt"
    write_tb(tb, v)
    write_sim(sm, v)
    back_tb = [int(x, 16) for x in tb.read_text().split()]
    back_sim = [int(x, 10) for x in sm.read_text().split()]
    errs = []
    if back_tb != list(v):
        errs.append(f"tb round-trip differs at {_first_diff(back_tb, v)}")
    if back_sim != list(v):
        errs.append(f"sim round-trip differs at {_first_diff(back_sim, v)}")
    # ...and the trap itself, asserted rather than assumed: for any vector
    # containing a value >= 10 the two FILES are different text.  If they ever
    # stop being different, one of the two writers has silently changed.
    if max(v, default=0) >= 10 and tb.read_text() == sm.read_text():
        errs.append("tb and sim files are identical text with values >= 10 -- "
                    "one of the two writers has changed encoding")
    return errs


def _first_diff(a, b):
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return f"[{i}] {x} != {y}"
    return f"length {len(a)} != {len(b)}"


# --------------------------------------------------------------------------- #
# the measurement side: was the vector APPLIED?
# --------------------------------------------------------------------------- #
def achieved_waits(rows):
    """Per bus cycle, the number of Tw the part actually took, read off the
    pins with no engine in the loop.  A cycle is T1..T4 plus its Tw run, so
    `length - 4`.  `sw/sm3_h3_cell.py::achieved_waits`, verbatim -- the
    function §68.6's R0 = 45,699/45,699 was scored with."""
    import sm3_ackgeom as ag                                # noqa: PLC0415
    cy = ag.cycles(rows, len(rows))
    return [max(0, (c[2] - c[1] + 1) - 4) for c in cy]


def applied_score(rows, v):
    """(matched, total, first_bad) -- the R0 statistic for one capture.

    The LAST cycle of a capture is dropped: a record cut mid-cycle has no T4,
    so its length is not its wait count.  Everything else is compared."""
    ach = achieved_waits(rows)
    if len(ach) > 1:
        ach = ach[:-1]
    n = min(len(ach), len(v))
    first_bad = None
    m = 0
    for i in range(n):
        if ach[i] == v[i]:
            m += 1
        elif first_bad is None:
            first_bad = (i, ach[i], v[i])
    return m, n, first_bad


def bus_cycle_bound(rows):
    """How many bus cycles this capture ran.  Property (2): a capture at or
    beyond NWVEC is OUTSIDE the regime in which the three legs agree about
    what the vector says, and must be quarantined rather than scored."""
    import sm3_ackgeom as ag                                # noqa: PLC0415
    return len(ag.cycles(rows, len(rows)))


# --------------------------------------------------------------------------- #
def lint(n=200, cids=("wrlint",), quiet=False):
    """Generation-only safety scan for this axis.  No board, no engine."""
    import tempfile
    errs = []
    seen_hash = {}
    with tempfile.TemporaryDirectory() as td:
        for cid in cids:
            for k in range(n):
                for shape in SHAPES:
                    spec = draw_spec(cid, k, shape)
                    if spec["shape"] != shape:
                        errs.append(f"{cid}/{k}/{shape}: spec shape mismatch")
                    try:
                        v = build(spec)
                    except Exception as e:                  # noqa: BLE001
                        errs.append(f"{cid}/{k}/{shape}: build: {e}")
                        continue
                    if len(v) != NWVEC:
                        errs.append(f"{cid}/{k}/{shape}: length {len(v)}")
                    if from_hex(to_hex(v)) != v:
                        errs.append(f"{cid}/{k}/{shape}: hex round-trip")
                    if k < 4:            # the file legs are slow; sample them
                        errs += [f"{cid}/{k}/{shape}: {e}"
                                 for e in check_encodings(v, td)]
                    # determinism: the same (cid,k,shape) is the same vector
                    key = (cid, k, shape)
                    h = sha256_of(v)
                    if key in seen_hash and seen_hash[key] != h:
                        errs.append(f"{cid}/{k}/{shape}: NOT DETERMINISTIC")
                    seen_hash[key] = h
                    if build(spec) != v:
                        errs.append(f"{cid}/{k}/{shape}: rebuild differs")
    # distinctness: a shape whose draw collapses to one vector is a stratum
    # with one member wearing n members' clothes.
    for shape in SHAPES:
        hs = {seen_hash[(cid, k, shape)] for cid in cids for k in range(n)}
        if len(hs) < max(2, n // 4):
            errs.append(f"{shape}: only {len(hs)} distinct vectors over "
                        f"{n * len(cids)} seeds")
        elif not quiet:
            print(f"  {shape:<6} {len(hs)} distinct vectors / {n * len(cids)} seeds")
    return errs


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("lint")
    p.add_argument("--n", type=int, default=200)
    p = sub.add_parser("show")
    p.add_argument("cid")
    p.add_argument("k", type=int)
    p.add_argument("--shape", default="uni", choices=SHAPES)
    p.add_argument("--head", type=int, default=64)
    a = ap.parse_args()
    if a.cmd == "lint":
        errs = lint(a.n)
        for e in errs[:20]:
            print(f"  WVEC LINT HIT: {e}")
        print(f"WVEC LINT {'PASS' if not errs else 'FAIL'}: {len(errs)} hits "
              f"over {a.n} seeds x {len(SHAPES)} shapes")
        return 0 if not errs else 1
    spec = draw_spec(a.cid, a.k, a.shape)
    v = build(spec)
    print(json.dumps({"spec": spec, "sha256": sha256_of(v), "len": len(v),
                      "head": v[:a.head]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
