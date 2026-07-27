#!/usr/bin/env python3
"""min_hang - delta-debug minimizer for the task #30 core-hang reproducer.

Board-free. Starts from the frozen pilot-w0 k=30 stream and greedily NOPs
instructions (preserving byte offsets, so branch/LOOP targets stay valid) while
the SPECIFIC wedge persists - the core stops fetching (a long trailing run of
idle rows) and never reaches the done marker. Distinguishes the wedge from a
runaway (bus stays active) and from completion (done marker present).
"""
import sys
from pathlib import Path

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
import fuzz_campaign as fzc                             # noqa: E402
import check_seq                                        # noqa: E402
import fuzz_classify as fc                              # noqa: E402
import testimage                                        # noqa: E402

QUIET_TAIL = 500


def wedge(rows):
    """(is_wedge, last_active_row). Wedge = no done marker AND a long trailing
    run of idle rows (the core stopped fetching)."""
    last_active = max((i for i, r in enumerate(rows)
                       if fc._tstate(r) == 1 and r["bs_early"] != 7), default=0)
    has_done = any(fc._tstate(r) == 1 and r["bs_early"] == 2
                   and (r["ad_addr"] & 0xFFFF) == 0xFC for r in rows)
    quiet = (len(rows) - 1) - last_active
    return (not has_done) and quiet > QUIET_TAIL, last_active


def build_base():
    cfg = fzc.derive_case("pilot-w0", 30,
                          {"force_tier": "soup", "force_contained": True,
                           "w0": True, "no_evt": True, "strict": True})
    g = fzc.build(cfg)
    return g


def offsets(g):
    offs = []
    o = 0
    for ins in g["ins"]:
        offs.append((o, len(ins)))
        o += len(ins)
    return offs


def run(g, instr):
    image, _ = testimage.compose(regs=g["regs"], instr=bytes(instr),
                                 ram=g["ram"], ivt=g.get("ivt"))
    rows = check_seq.run_tb(image, 4200, waits=0)
    return wedge(rows)


def make_instr(base, offs, keep):
    """base instr with every instruction NOT in `keep` replaced by 0x90s."""
    buf = bytearray(base)
    for i, (o, ln) in enumerate(offs):
        if i not in keep:
            buf[o:o + ln] = b"\x90" * ln
    return bytes(buf)


def main():
    g = build_base()
    base = g["instr"]
    offs = offsets(g)
    n = len(offs)
    isw, la = run(g, base)
    print(f"base: {n} instructions, wedge={isw} last_active={la}")
    if not isw:
        print("base does not wedge under this oracle - abort")
        return 1

    keep = set(range(n))
    changed = True
    rounds = 0
    while changed:
        changed = False
        rounds += 1
        for i in sorted(keep):
            trial = keep - {i}
            isw, la = run(g, make_instr(base, offs, trial))
            if isw:
                keep = trial
                changed = True
        print(f"  round {rounds}: kept {len(keep)} -> {sorted(keep)}")
    print(f"\nMINIMAL wedge set: {sorted(keep)} ({len(keep)} instructions)")
    for i in sorted(keep):
        o, ln = offs[i]
        print(f"  ins {i} @0x{0x500+o:04x}: {base[o:o+ln].hex()}")
    # emit the minimized instr bytes (NOP-padded) for a frozen repro
    mini = make_instr(base, offs, keep)
    isw, la = run(g, mini)
    print(f"\nminimized image: wedge={isw} last_active={la}")
    Path(SW / "testdata" / "core_hang_min.hex").write_text(
        "\n".join(f"{b:02x}" for b in
                  bytes(testimage.compose(regs=g["regs"], instr=mini,
                                          ram=g["ram"], ivt=g.get("ivt"))[0]))
        + "\n")
    print("wrote sw/testdata/core_hang_min.hex")
    return 0


if __name__ == "__main__":
    sys.exit(main())
