#!/usr/bin/env python3
"""fuzz_cov - lightweight coverage tracking for the A/B sequence fuzz.

Codex flagged the absence of any coverage metric: the fuzz ran green but
nobody could say WHAT it had exercised. This module makes breadth
measurable. Five axes accumulate across A/B gate runs and persist to a
JSON file so coverage accrues; report() renders them and flags
undersampled corners.

Axes
  form   - semantic gadget family emitted by gen_seq (generator truth,
           one tag per gadget invocation). This is the primary breadth
           metric: which instruction families the corpus has touched.
  opsig  - objective opcode signature decoded from the emitted bytes
           (prefixes stripped; group /r ext and mod3-vs-mem folded in).
           Independent of the generator's own labelling - maps the
           corpus onto documented-form space and cross-checks `form`.
  prefix - prefix combination per instruction
           (none / seg:xx / rep / repnz / rep+seg / lock).
  qfill  - prefetch-queue depth at each instruction dispatch (the F pop),
           reconstructed from the capture trace (bucketed 0..6+). Shows
           which queue-fill phases at dispatch the corpus has hit - the
           exact axis the Mission D disp-reader law turned on.
  waits  - wait-state setting the seed ran at.

A seed's contribution to form/opsig/prefix is static (from its bytes);
qfill comes from the chip-position trace of the run.
"""
import argparse
import json
from collections import Counter
from pathlib import Path

SW = Path(__file__).resolve().parent
DEFAULT_COV = SW / "testdata" / "fuzz_coverage.json"
DEFAULT_DIV = SW / "testdata" / "fuzz_divergences.jsonl"

SEG_PREFIX = {0x26: "es", 0x2E: "cs", 0x36: "ss", 0x3E: "ds"}
REP_PREFIX = {0xF2: "repnz", 0xF3: "rep"}
PREFIX_BYTES = set(SEG_PREFIX) | set(REP_PREFIX) | {0xF0}

# group opcodes: the /reg field of the modrm selects the operation
GROUP_OPS = {0x80, 0x81, 0x82, 0x83, 0xC0, 0xC1, 0xD0, 0xD1, 0xD2, 0xD3,
             0xF6, 0xF7, 0xFE, 0xFF, 0x8F}
# non-group opcodes that still carry a modrm (fold reg/mem into the sig)
MODRM_OPS = ({0x00, 0x01, 0x02, 0x03, 0x08, 0x09, 0x0A, 0x0B,
              0x10, 0x11, 0x12, 0x13, 0x18, 0x19, 0x1A, 0x1B,
              0x20, 0x21, 0x22, 0x23, 0x28, 0x29, 0x2A, 0x2B,
              0x30, 0x31, 0x32, 0x33, 0x38, 0x39, 0x3A, 0x3B,
              0x62, 0x69, 0x6B, 0x84, 0x85, 0x86, 0x87,
              0x88, 0x89, 0x8A, 0x8B, 0x8C, 0x8D, 0x8E,
              0xC4, 0xC5})
# 0F second bytes that consume a modrm (fold reg/mem); the rest are
# fixed-form or imm-only (BRKEM et al are forbidden and never emitted)
F0_MODRM = {0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17,
            0x18, 0x19, 0x1A, 0x1B, 0x1C, 0x1D, 0x1E, 0x1F,
            0x28, 0x2A, 0x31, 0x33, 0x39, 0x3B}


def decode_sig(ins):
    """(prefix_tag, opsig) for one instruction's bytes.
    prefix_tag: 'none' | 'seg:xx' | 'rep' | 'repnz' | 'lock' | combos joined
    opsig: e.g. '88.r', '8b.m', '81/4.r', '0f1c.m', 'b8', 'eb'."""
    i = 0
    segs, reps, lock = [], [], False
    while i < len(ins) and ins[i] in PREFIX_BYTES:
        b = ins[i]
        if b in SEG_PREFIX:
            segs.append(SEG_PREFIX[b])
        elif b in REP_PREFIX:
            reps.append(REP_PREFIX[b])
        else:
            lock = True
        i += 1
    ptags = []
    if reps:
        ptags.append(reps[-1])
    if segs:
        ptags.append("seg:" + segs[-1])
    if lock:
        ptags.append("lock")
    prefix = "+".join(ptags) if ptags else "none"

    if i >= len(ins):
        return prefix, "?"
    op = ins[i]
    i += 1
    if op == 0x0F:
        if i >= len(ins):
            return prefix, "0f?"
        b2 = ins[i]
        i += 1
        sig = f"0f{b2:02x}"
        if b2 in F0_MODRM and i < len(ins):
            sig += ".r" if (ins[i] >> 6) == 3 else ".m"
        return prefix, sig
    if op in GROUP_OPS and i < len(ins):
        m = ins[i]
        sig = f"{op:02x}/{(m >> 3) & 7}" + (".r" if (m >> 6) == 3 else ".m")
        return prefix, sig
    if op in MODRM_OPS and i < len(ins):
        return prefix, f"{op:02x}" + (".r" if (ins[i] >> 6) == 3 else ".m")
    return prefix, f"{op:02x}"


def qfill_at_dispatch(recs):
    """Reconstruct prefetch-queue depth at each F (first-opcode-byte) pop
    from a capture trace, yielding the fill PRESENT AT DISPATCH (pre-pop).
    Mirrors analyze_capture.analyze_large's depth model: CODE fetch T4
    adds 2 (even word) or 1 (odd single-byte fetch); F/S/E pops decrement.
    """
    depth = 0
    cur_word = None
    out = []
    for r in recs:
        t = r.get("t", r.get("t_state"))
        if t == 1:                       # T1: latch this cycle's kind/width
            cur_word = (r["bs_early"] == 4 and (r["ad_addr"] & 1) == 0
                        and not r["ube_n"])
        elif t == 5 and cur_word is not None:   # T4
            if r["bs_early"] == 4:               # CODE fetch completed
                depth = min(depth + (2 if cur_word else 1), 6)
            cur_word = None
        q = r["qs"]
        if q == 1:                       # F: first byte of an opcode
            out.append(min(depth, 6))
            depth = max(depth - 1, 0)
        elif q in (2, 3):                # E (empty) / S (subsequent byte)
            if q == 2:
                out.append(0)
            depth = max(depth - 1, 0)
    return out


class Coverage:
    def __init__(self):
        self.form = Counter()
        self.opsig = Counter()
        self.prefix = Counter()
        self.qfill = Counter()
        self.waits = Counter()
        self.seeds = 0
        self.instrs = 0

    def add_program(self, forms, per_ins_bytes, waits=0):
        """forms: gen_seq gadget tags; per_ins_bytes: list[bytes] one per
        emitted instruction; waits: run wait setting."""
        self.seeds += 1
        self.waits[str(waits)] += 1
        for f in forms:
            self.form[f] += 1
        for ins in per_ins_bytes:
            self.instrs += 1
            pfx, sig = decode_sig(ins)
            self.opsig[sig] += 1
            self.prefix[pfx] += 1

    def add_trace(self, recs):
        for d in qfill_at_dispatch(recs):
            self.qfill[f"q{d}"] += 1

    def to_dict(self):
        return {"seeds": self.seeds, "instrs": self.instrs,
                "form": dict(self.form), "opsig": dict(self.opsig),
                "prefix": dict(self.prefix), "qfill": dict(self.qfill),
                "waits": dict(self.waits)}

    @classmethod
    def load(cls, path=DEFAULT_COV):
        c = cls()
        p = Path(path)
        if p.exists():
            d = json.loads(p.read_text())
            c.seeds = d.get("seeds", 0)
            c.instrs = d.get("instrs", 0)
            for k in ("form", "opsig", "prefix", "qfill", "waits"):
                c.__dict__[k] = Counter(d.get(k, {}))
        return c

    def save(self, path=DEFAULT_COV):
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.to_dict(), indent=1, sort_keys=True))

    def report(self, universe=None, low=5):
        """universe: optional dict axis->iterable of expected keys, so
        NEVER-exercised corners show as 0. low: flag counts <= this."""
        universe = universe or {}
        lines = [f"fuzz coverage: {self.seeds} seeds, {self.instrs} instrs"]
        for axis, title in (("form", "instruction families (form)"),
                            ("opsig", "opcode signatures (opsig)"),
                            ("prefix", "prefix combinations"),
                            ("qfill", "queue fill at dispatch"),
                            ("waits", "wait settings")):
            ctr = getattr(self, axis)
            uni = set(universe.get(axis, ()))
            keys = set(ctr) | uni
            lines.append(f"\n== {title} ==  ({len(ctr)} seen"
                         + (f", {len(uni - set(ctr))} unexercised" if uni
                            else "") + ")")
            for k in sorted(keys, key=lambda x: (-ctr.get(x, 0), x)):
                n = ctr.get(k, 0)
                flag = "  <-- UNEXERCISED" if n == 0 else (
                    "  <-- undersampled" if n <= low else "")
                lines.append(f"   {k:<16} {n:>8}{flag}")
        return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="render fuzz coverage report")
    ap.add_argument("--cov-file", default=str(DEFAULT_COV))
    ap.add_argument("--low", type=int, default=5)
    a = ap.parse_args()
    c = Coverage.load(a.cov_file)
    try:
        from gen_seq import form_universe
        uni = {"form": form_universe()}
    except Exception:
        uni = {}
    print(c.report(universe=uni, low=a.low))


if __name__ == "__main__":
    main()
