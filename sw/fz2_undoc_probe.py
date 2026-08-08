#!/usr/bin/env python3
"""fuzz-v2 -- THE UNDOC-OPCODE PROBE.  A MEASUREMENT TOOL, NOT A GATE.

T2's finding F4 said `0xF1` parks the EU forever, and `undoc` was the largest
depressor of erratum E-1's terminator-reached column (59.6 %).  Every figure
behind that was taken through `check_seq.CORE`, which is pinned to the ARCHIVED
fsm core -- so the finding could equally be a property of the CORPUS or an
artifact of the INSTRUMENT, and E-1 cannot be registered until it is known
which.  This probe asks the question directly and on both engines.

ONE IMAGE PER OPCODE, and nothing else in it: the v2 map with a ONE-BYTE body.
Execution falls off the body into the `0xCC` fill, traps to INT3, vectors to
the terminator and dumps -- so `0x90` is the control that says the harness
terminates at all, and any opcode that does not dump differs from the control
in exactly one byte.

WHAT IS REPORTED, per (opcode, core): whether the run reached the done marker,
whether it produced a MAGIC-anchored dump, how many bus rows it produced, how
far the code fetches got, and the last few bus cycles.  No threshold, no
verdict.  The engine, its binary and its receipt id are printed beside every
row, because a `--core` flag that is accepted and ignored is the exact failure
this probe exists to rule out.
"""
import argparse
import sys
from pathlib import Path

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))

import check_seq                                          # noqa: E402
import fuzz_campaign as fzc                               # noqa: E402
import fuzz_classify as fc                                # noqa: E402
import optable                                            # noqa: E402
import testimage as ti                                    # noqa: E402

# The three opcodes `gen_soup.emit_undoc` can draw (`optable.UNDOC`), plus the
# NOP control.  The pool is READ FROM THE TABLE, not restated here.
UNDOC = sorted(c for c, i in optable.TABLE.items()
               if i.policy == optable.UNDOC)
CONTROL = 0x90


def probe(body, core, rows=fzc.TB_ROWS, waits=0):
    """One image, one engine.  -> a dict of measured facts.

    `body` is the WHOLE fuzz body, so a two-byte form (a group extension and
    its ModR/M) is expressible without a second tool."""
    image, meta = ti.compose(instr=bytes(body))
    # A LEG THAT REFUSES TO RUN IS A MEASUREMENT, NOT AN EXCEPTION: the
    # archived core's SVAs `$stop` the TB on some forms, and "no capture" is
    # exactly the fact the reviewer needs beside the other engine's rows.
    try:
        recs = check_seq.run_tb(image, rows, waits=waits, core=core)
    except RuntimeError as e:                              # noqa: BLE001
        return {"body": bytes(body).hex(), "core": core, "rows": 0,
                "done_idx": None, "arch_ok": False, "code_fetches": 0,
                "fetched_past_body": 0, "fetched_terminator": 0,
                "last_code": None,
                "last_bs": [str(e).splitlines()[0][:80]]}
    di = fc._done_idx(recs)
    code = [r for r in recs
            if fc._tstate(r) == 1 and r["bs_early"] == 4]
    anchor = meta["anchor_phys"]
    past = [r for r in code if (r["ad_addr"] & 0xFFFF) > anchor]
    term = [r for r in code
            if ti.TERM_AT <= (r["ad_addr"] & 0xFFFF) < ti.CODE_HI]
    return {
        "body": bytes(body).hex(), "core": core,
        "rows": len(recs),
        "done_idx": di,
        "arch_ok": fc.arch_dump(recs, len(recs)) is not None,
        "code_fetches": len(code),
        "fetched_past_body": len(past),
        "fetched_terminator": len(term),
        "last_code": (code[-1]["ad_addr"] & 0xFFFF) if code else None,
        "last_bs": [check_seq.BS_NAME[r["bs_early"]] for r in recs[-6:]],
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cores", default="ucore,fsm")
    ap.add_argument("--ops", default=None,
                    help="comma list of hex BODIES (`f1`, `fef8`, ...); "
                         "default = optable.UNDOC + the NOP control")
    ap.add_argument("--rows", type=int, default=fzc.TB_ROWS)
    ap.add_argument("--waits", type=int, default=0)
    a = ap.parse_args()
    ops = ([bytes.fromhex(x) for x in a.ops.split(",")] if a.ops
           else [bytes([o]) for o in [CONTROL] + UNDOC])
    cores = [c for c in a.cores.split(",") if c]

    print(f"fz2 undoc probe: bodies={[b.hex() for b in ops]} cores={cores} "
          f"rows={a.rows} waits={a.waits}")
    print(f"  body = ONE byte at the anchor {ti.ANCHOR0:04x}; everything after "
          f"it is 0xCC (INT3) -> vector {ti.TERM_VECTOR} -> terminator "
          f"{ti.TERM_AT:04x} -> dump + done marker")
    eng = {}
    for c in cores:
        eng[c] = fzc.tb_engine(c)
        print(f"  ENGINE {c}: bin={eng[c][1]}\n"
              f"           receipt={eng[c][2]}")
    print()
    hdr = (f"  {'body':<8}{'core':<8}{'done':<7}{'dump':<7}{'rows':<7}"
           f"{'codefetch':<11}{'past body':<11}{'in term':<9}{'last code'}")
    print(hdr)
    for body in ops:
        for c in cores:
            r = probe(body, c, rows=a.rows, waits=a.waits)
            info = optable.TABLE.get(body[0])
            nm = info.mnem if info else "?"
            print(f"  {body.hex():<8}{c:<8}"
                  f"{str(r['done_idx']):<7}{str(r['arch_ok']):<7}"
                  f"{r['rows']:<7}{r['code_fetches']:<11}"
                  f"{r['fetched_past_body']:<11}{r['fetched_terminator']:<9}"
                  f"{'----' if r['last_code'] is None else format(r['last_code'], '04x')}"
                  f"   [{nm}]  tail={r['last_bs']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
