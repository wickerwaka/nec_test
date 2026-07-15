#!/usr/bin/env python3
"""exp_resume - Stage-0 go/no-go: does the prefetch-RESUME law CLOSE?

Rebuild Phase-2 Stage 0 (reflash-free, socketed chip = ground truth). The
central risk of the BIU rebuild is the prefetch-resume-after-EU/retire law
under waits: the residual w>=1 drift is a bidirectional bus-phase-alignment
effect (biu_model.md Round 3 A2). This probe measures the chip's resume slot
as a function of (grid_phase, occupancy, fill_state) over many APERIODIC
leading-phase histories and asks whether resume_slot is a well-defined
FUNCTION of those inputs (the table CLOSES) or whether a hidden state variable
remains.

Method:
  - Build self-contained APERIODIC instruction streams (mixed 1/2/3-byte
    register/imm ops + occasional mem read/write, non-repeating RNG order,
    no jumps/flushes/traps -> clean fetch-limited draining/resume).
  - Sweep the leading bus-grid phase by prepending k NOPs (k=0..7); each NOP
    is 3 clocks so k parity flips the phase (the Round-3 A2 sweep).
  - Capture the chip per-cycle at w0/w1/w3 (run_chip, use_core=False).
  - Reconstruct queue occupancy; extract every RESUME event (a CODE fetch T1
    that is NOT back-to-back with the previous bus cycle) with its tuple.
  - CLOSURE TEST: group events by (phase_def, occ, fill_def); within each
    group, is resume_slot constant? Report contradictions per candidate
    definition, and whether the bidirectional flip is reproduced.

Usage:
  exp_resume.py capture [--seeds N] [--kmax K] [--waits 0,1,3] [--out FILE]
  exp_resume.py analyze [--in FILE]
"""
import argparse
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
import testimage                       # noqa: E402
from v30run import run_image           # noqa: E402

# (bytes, mnemonic) palette. All linear, non-flushing, non-trapping.
# BW=0x0800 (RAM), DS0=0 so mem ops are safe. Values chosen to never form a
# flush/trap. AW/BW get clobbered - irrelevant, we only read the bus grid.
PALETTE = [
    (b"\x90", "NOP"),
    (b"\x40", "INC AW"),
    (b"\x43", "INC BW"),
    (b"\x41", "INC CW"),
    (b"\xf8", "CLC"),
    (b"\xf9", "STC"),
    (b"\x27", "DAA"),
    (b"\x2f", "DAS"),
    (b"\xb8\x34\x12", "MOV AW,imm16"),
    (b"\xbb\x00\x08", "MOV BW,imm16"),   # keep BW pointing at RAM
    (b"\x05\x11\x11", "ADD AW,imm16"),
    (b"\x89\x07", "MOV [BW],AW"),        # mem write (EU access)
    (b"\x8b\x07", "MOV AW,[BW]"),        # mem read (EU access)
    (b"\x89\x07", "MOV [BW],AW"),        # weight mem ops up: fill->drain->resume
    (b"\x8b\x07", "MOV AW,[BW]"),
    (b"\x01\x07", "ADD [BW],AW"),        # RMW (read+write, longer)
]


def build_stream(seed, n_ops=40):
    r = random.Random(f"resume/{seed}")
    body = b""
    for _ in range(n_ops):
        body += r.choice(PALETTE)[0]
    return body


def reconstruct(recs):
    """Per-cycle queue occupancy (physical bytes present) + annotate rows.

    Credit a fetch at the T4 of the cycle it belongs to (cur_fetch/cur_word
    latched at that cycle's T1); -= 1 per F/S pop; = 0 at E flush.
    """
    out = []
    depth = 0
    cur_fetch = False
    cur_word = False
    for i, r in enumerate(recs):
        t = r["t"]
        bs = r["bs_early"]
        if t == 1:
            cur_fetch = (bs == 4)
            cur_word = (r["ad_addr"] & 1) == 0 and not r["ube_n"]
        if t == 5 and cur_fetch:
            depth += 2 if cur_word else 1
            cur_fetch = False
        q = r["qs"]
        if q in (1, 3):
            depth = max(depth - 1, 0)
        elif q == 2:
            depth = 0
        out.append({"i": i, "t": t, "bs": bs, "addr": r["ad_addr"],
                    "qs": q, "ube_n": r["ube_n"], "depth": depth})
    return out


def extract_resumes(rows):
    """A resume = a CODE fetch T1 not immediately back-to-back with the
    previous bus cycle's T4 (>=1 idle/other cycle between). Records the tuple
    the closure test needs."""
    ev = []
    # index bus-cycle T4s
    last_t4 = None
    last_t4_kind = None
    for i, row in enumerate(rows):
        if row["t"] == 5:
            # find this cycle's kind (its own T1 bs)
            pass
    # walk: track previous bus-cycle end + kind
    prev_end = None
    prev_kind = None
    cur_kind = None
    for i, row in enumerate(rows):
        t = row["t"]
        if t == 1:
            # is this a resume? CODE T1 with a gap since prev bus end
            if row["bs"] == 4 and prev_end is not None:
                gap = i - prev_end - 1
                if gap >= 1:
                    depth_hist = [rows[j]["depth"]
                                  for j in range(max(0, i - 10), i)]
                    ev.append({
                        "i": i,
                        "addr": row["addr"],
                        "gap": gap,                     # resume_slot observable
                        "prev_kind": prev_kind,         # 4=CODE else EU access
                        "occ": rows[i - 1]["depth"],    # occupancy at decision
                        "depth_hist": depth_hist,
                    })
            cur_kind = row["bs"]
        if t == 5:
            prev_end = i
            prev_kind = cur_kind
    return ev


def phase_defs(rows, i):
    """Candidate grid-phase definitions at row i (anchored to reset release,
    row 0). Returns dict name->parity."""
    # clock parity (ph_ff-like: advances every clock incl idles)
    p_clk = i & 1
    # grid-slot parity: count non-TI (bus-active) cycles before i
    slots = sum(1 for j in range(i) if rows[j]["t"] != 0)
    p_slot = slots & 1
    # T-state-pair parity: count T1..T4 excluding Tw (Tw=4) - "one grid pos
    # per bus cycle regardless of waits"
    tpair = sum(1 for j in range(i)
                if rows[j]["t"] in (1, 2, 3, 5))
    p_tpair = tpair & 1
    return {"clk": p_clk, "slot": p_slot, "tpair": p_tpair}


def fill_defs(ev):
    """Candidate fill_state descriptors from the depth history."""
    h = ev["depth_hist"]
    occ = ev["occ"]
    rising = 1 if (len(h) >= 4 and h[-1] > h[-4]) else 0
    sat_recent = 1 if (h and max(h) >= 5) else 0
    return {"none": 0, "rising": rising, "sat": sat_recent,
            "rising_sat": rising * 2 + sat_recent}


def cmd_capture(args):
    waits = [int(w) for w in args.waits.split(",")]
    allev = []
    host = args.host
    for seed in range(args.seeds):
        body = build_stream(seed, n_ops=args.nops)
        for k in range(args.kmax + 1):
            instr = b"\x90" * k + body
            regs = {"PS": 0, "PC": 0x0500, "BW": 0x0800, "DS0": 0,
                    "AW": 0x1234, "CW": 3, "DW": 0}
            image, meta = testimage.compose(regs=regs, instr=instr)
            for w in waits:
                try:
                    recs = run_image(bytes(image), host, tag="resume",
                                     use_core=False, waits=w)
                except Exception as e:
                    print(f"seed{seed} k{k} w{w}: RUN FAIL {e}",
                          file=sys.stderr)
                    continue
                rel = next(i for i, r in enumerate(recs) if not r["rst"])
                rows = reconstruct(recs[rel:])
                evs = extract_resumes(rows)
                eu_ord = 0
                all_ord = 0
                for e in evs:
                    e["ph"] = phase_defs(rows, e["i"])
                    e["fill"] = fill_defs(e)
                    e["ord"] = all_ord
                    all_ord += 1
                    if e["prev_kind"] != 4:            # EU-access-preceded
                        e["eu_ord"] = eu_ord
                        eu_ord += 1
                    else:
                        e["eu_ord"] = -1
                    e.update(seed=seed, k=k, w=w)
                    e.pop("depth_hist")
                    allev.append(e)
                print(f"seed{seed} k{k} w{w}: {len(evs)} resume events "
                      f"({len(rows)} rows)")
    Path(args.out).write_text(json.dumps(allev))
    print(f"\n{len(allev)} resume events -> {args.out}")
    return 0


def closure(events, w, phase_name, fill_name):
    """Group by (phase, occ, fill) at wait level w; return contradiction
    stats: groups where resume_slot (gap) is not constant."""
    groups = defaultdict(list)
    for e in events:
        if e["w"] != w:
            continue
        key = (e["ph"][phase_name], e["occ"], e["fill"][fill_name])
        groups[key].append(e["gap"])
    contradictions = 0
    total = 0
    worst = []
    for key, gaps in groups.items():
        total += 1
        u = set(gaps)
        if len(u) > 1:
            contradictions += 1
            worst.append((key, sorted(u), len(gaps)))
    worst.sort(key=lambda x: -x[2])
    return contradictions, total, worst


def cmd_analyze(args):
    events = json.loads(Path(args.inp).read_text())
    waits = sorted(set(e["w"] for e in events))
    print(f"{len(events)} resume events across waits {waits}\n")
    # Only prefetch-resume-after-a-gap events; separate EU-access-preceded
    # (prev_kind != 4) from prefetch-pause (prev_kind == 4).
    for w in waits:
        we = [e for e in events if e["w"] == w]
        print(f"=== waits={w}  ({len(we)} events) ===")
        # gap distribution
        from collections import Counter
        gd = Counter(e["gap"] for e in we)
        print(f"  gap distribution: {dict(sorted(gd.items()))}")
        # bidirectional check: does gap vary with phase at fixed occ?
        for phase_name in ("clk", "slot", "tpair"):
            for fill_name in ("none", "rising", "sat", "rising_sat"):
                c, t, worst = closure(we, w, phase_name, fill_name)
                tag = f"phase={phase_name:5} fill={fill_name:10}"
                print(f"  {tag}: {c}/{t} groups CONTRADICT"
                      + (f"   worst {worst[0][0]}->{worst[0][1]}"
                         f" (n={worst[0][2]})" if worst else "   CLOSES"))
        print()
    return 0


def cmd_sweep(args):
    """Aligned phase-sweep closure test. For a fixed structural resume event
    (same seed, same EU-access-resume ordinal), occupancy and fill are IDENTICAL
    across k (same instruction stream, only the leading phase shifted by the k
    NOPs). So gap-vs-k isolates the grid PHASE as the sole varied input.
    VERDICT per (seed,eu_ord,w): if gap is a clean function of k-parity (exactly
    the two bidirectional values, one per parity) the resume law CLOSES over
    grid_phase; if gap wanders beyond parity, a hidden variable remains."""
    events = json.loads(Path(args.inp).read_text())
    waits = sorted(set(e["w"] for e in events))
    ks = sorted(set(e["k"] for e in events))
    seeds = sorted(set(e["seed"] for e in events))
    print("Aligned phase-sweep: gap vs k at fixed (seed, eu_ord). occ/fill "
          "constant across k => gap change is PURE grid-phase.\n")
    verdict = {"clean_parity": 0, "constant": 0, "wander": 0}
    for w in waits:
        print(f"=== waits={w} ===")
        for seed in seeds:
            # max eu_ord present for all k (align only where every k has it)
            for eo in range(0, 40):
                cells = {}
                occset, fillset = set(), set()
                for k in ks:
                    m = [e for e in events if e["w"] == w and e["seed"] == seed
                         and e["eu_ord"] == eo and e["k"] == k]
                    if len(m) == 1:
                        cells[k] = m[0]["gap"]
                        occset.add(m[0]["occ"])
                        fillset.add(m[0]["fill"]["rising_sat"])
                if len(cells) < len(ks):
                    continue
                gaps_by_par = {0: set(), 1: set()}
                for k, g in cells.items():
                    gaps_by_par[k & 1].add(g)
                allv = set(cells.values())
                row = " ".join(f"k{k}={cells[k]}" for k in ks)
                occ_note = "" if len(occset) == 1 else f" occVAR{sorted(occset)}"
                if len(allv) == 1:
                    tag = "CONSTANT"
                    verdict["constant"] += 1
                elif (len(gaps_by_par[0]) == 1 and len(gaps_by_par[1]) == 1):
                    tag = "CLEAN-PARITY"
                    verdict["clean_parity"] += 1
                else:
                    tag = "WANDER<<<"
                    verdict["wander"] += 1
                print(f"  seed{seed} eu_ord{eo}: {row}   [{tag}]{occ_note}")
    print(f"\nVERDICT counts: {verdict}")
    print("  CONSTANT/CLEAN-PARITY => gap is a function of grid-phase (occ/fill"
          " fixed) => the resume law CLOSES over grid_phase.")
    print("  WANDER => same (seed,eu_ord) [=same occ/fill] gives >2 gaps not"
          " parity-separated => HIDDEN VARIABLE beyond (phase,occ,fill).")
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("capture")
    c.add_argument("--host", default="root@mister-nec")
    c.add_argument("--seeds", type=int, default=8)
    c.add_argument("--kmax", type=int, default=7)
    c.add_argument("--nops", type=int, default=40)
    c.add_argument("--waits", default="0,1,3")
    c.add_argument("--out", default="/tmp/resume_events.json")
    c.set_defaults(fn=cmd_capture)
    a = sub.add_parser("analyze")
    a.add_argument("--in", dest="inp", default="/tmp/resume_events.json")
    a.set_defaults(fn=cmd_analyze)
    s = sub.add_parser("sweep")
    s.add_argument("--in", dest="inp", default="/tmp/resume_events.json")
    s.set_defaults(fn=cmd_sweep)
    args = ap.parse_args()
    sys.exit(args.fn(args))


if __name__ == "__main__":
    main()
