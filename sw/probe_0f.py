#!/usr/bin/env python3
"""probe_0f - Campaign 2 mission 9: undocumented 0F-space survey.

For each candidate second byte b: run [0F b] followed by four 1-byte marker
instructions INC AW / INC CW / INC DW / INC BW at offsets 2..5; the store
stub (which begins with 6 NOPs, tolerating over-consumption) follows at +6.

If the run completes, the set of incremented markers reveals how many bytes
the opcode consumed (length = 6 - #markers when the executed markers are
the trailing ones); register/PSW deltas beyond the markers and test-phase
bus transactions reveal side effects. If the run produces no done marker,
the opcode ran away / hung — v30ctl's per-run host reset recovers the board
and the probe is recorded as quarantined.

Exclusions (verified against docs/facts/instructions.json 0F encodings):
documented second bytes 10-1F (TEST1/NOT1/CLR1/SET1), 20/22/26 (ADD4S/
SUB4S/CMP4S), 28/2A (ROL4/ROR4), 31/33/39/3B (INS/EXT), FF (BRKEM - enters
8080 emulation mode with no recovery path!), and E0/F0 (V33 BRKXA/RETXA,
not risked).

Robustness: one retry then skip-and-log per case; incremental JSONL log;
flushed prints.

Usage: probe_0f.py all [--host ...]        # marker survey (16 bytes)
       probe_0f.py followup [--host ...]   # raw-capture classification of
                                           # the runaway class + 0F 24 rerun
Results feed docs/facts/undocumented_0f.md.
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from v30run import run_test                           # noqa: E402

LOG = Path(__file__).resolve().parent / "testdata" / "0f_log.jsonl"

DOCUMENTED = set(range(0x10, 0x20)) | {0x20, 0x22, 0x26, 0x28, 0x2A,
                                       0x31, 0x33, 0x39, 0x3B, 0xFF}
NEVER = {0xFF, 0xE0, 0xF0}   # BRKEM / V33 BRKXA / V33 RETXA

# spread across the space
PROBES = [0x00, 0x04, 0x08, 0x0C, 0x21, 0x24, 0x27, 0x2C,
          0x30, 0x34, 0x40, 0x60, 0x80, 0xA0, 0xC0, 0xE4]

INJECT = {"AW": 0x1000, "CW": 0x2000, "DW": 0x3000, "BW": 0x0800,
          "BP": 0x0900, "IX": 0x0010, "IY": 0x0020,
          "DS0": 0x0000, "DS1": 0x0000, "SS": 0x0000, "SP": 0x0F00,
          "PS": 0, "PC": 0x0500, "PSW": 0x0000}
MARKERS = ["AW", "CW", "DW", "BW"]      # INC 40 41 42 43 at offsets 2..5


def log_line(obj):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as f:
        f.write(json.dumps(obj) + "\n")


def probe(host, b):
    instr = bytes([0x0F, b, 0x40, 0x41, 0x42, 0x43])
    res = None
    for attempt in (1, 2):
        try:
            res = run_test(regs=dict(INJECT), instr=instr, host=host,
                           tag=f"zf{b:02x}")
            break
        except Exception as e:                        # noqa: BLE001
            err = str(e)[:160]
            print(f"    attempt {attempt}: {err}", flush=True)
            if attempt == 2:
                kind = ("runaway (no done marker)" if "done marker" in err
                        else "run failed")
                return {"b": b, "status": kind, "error": err}
            time.sleep(2)
    regs = res["regs"]
    inc = [m for m in MARKERS if regs[m] == INJECT[m] + 1]
    other = {k: f"{INJECT[k]:04X}->{regs[k]:04X}" for k in INJECT
             if k not in ("PSW", "PC") and regs.get(k) is not None
             and regs[k] != INJECT[k]
             and not (k in MARKERS and regs[k] == INJECT[k] + 1)}
    # length inference: executed markers should be the trailing ones
    n = len(inc)
    trailing_ok = inc == MARKERS[4 - n:] if n else False
    length = 6 - n if trailing_ok else None
    psw_in = (INJECT["PSW"] & 0x0ED5) | 0xF002
    # test-phase bus side effects (excluding code fetches)
    txns = [{"kind": t["kind"], "addr": t["addr"], "data": t["data"],
             "ube_n": t["ube_n"]}
            for t in res["test_txns"] if t["kind"] != "CODE"]
    test_cycles = sum(t["cycles"] for t in res["test_txns"])
    return {"b": b, "status": "executed", "markers_inc": inc,
            "length": length, "other_reg_changes": other,
            "psw": f"{psw_in:04X}->{regs['PSW']:04X}",
            "pc_final": f"{regs['PC']:04X}", "noncode_txns": txns,
            "test_txn_cycles": test_cycles}


def cmd_followup(host):
    """Raw-capture classification of the runaway class (mission 9 analysis
    runs, reproducible): (a) bus behavior of runaway bytes, (b) vector =
    third byte check, (c) 0F 24 with sane CL."""
    import testimage
    from v30run import run_image, extract_txns_large, KIND

    def raw(instr, tag):
        image, meta = testimage.compose(regs=dict(INJECT), instr=instr)
        recs = run_image(image, host, tag)
        txns = extract_txns_large(recs)
        ai = next((i for i, t in enumerate(txns)
                   if t["addr"] == meta["anchor_linear"]
                   and KIND[t["kind"]] == "CODE"), None)
        return txns[ai:] if ai is not None else txns

    # (a) runaway class: BRKEM aliases show MEMR IVT[0x40] + 3 pushes;
    #     0F 34 shows a silent lockup (few fetches, then bus quiet)
    for b in (0x24, 0x34, 0x40, 0x60, 0x80, 0xA0, 0xC0, 0xE4):
        try:
            after = raw(bytes([0x0F, b, 0x40, 0x41, 0x42, 0x43]),
                        f"raw{b:02x}")
        except Exception as e:                        # noqa: BLE001
            print(f"0F {b:02X}: raw run failed: {str(e)[:100]}", flush=True)
            continue
        kinds = {}
        for t in after:
            kinds[KIND[t["kind"]]] = kinds.get(KIND[t["kind"]], 0) + 1
        noncode = [(KIND[t["kind"]], hex(t["addr"]), hex(t["data"]))
                   for t in after if KIND[t["kind"]] != "CODE"][:6]
        print(f"0F {b:02X}: {len(after)} txns, kinds={kinds}, "
              f"first non-code={noncode}", flush=True)
    # (b) vector = third byte? 0F 40 06 -> expect IVT entry 6 @ 0x18
    after = raw(bytes([0x0F, 0x40, 0x06, 0x34, 0x12, 0x43]), "vec06")
    noncode = [(KIND[t["kind"]], hex(t["addr"]), hex(t["data"]))
               for t in after if KIND[t["kind"]] != "CODE"][:6]
    print(f"0F 40 06 34 12: first non-code={noncode}", flush=True)
    # (c) 0F 24 with sane CL and BCD string data
    regs = dict(INJECT, CW=0x0004)
    res = run_test(regs=regs,
                   instr=bytes([0x0F, 0x24, 0x40, 0x41, 0x42, 0x43]),
                   host=host, tag="s24",
                   ram=[(0x10, 0x34), (0x11, 0x12),
                        (0x20, 0x66), (0x21, 0x88)])
    r = res["regs"]
    inc = [m for m in MARKERS if r[m] == regs[m] + 1]
    print(f"0F 24 CW=4: markers={inc} PSW->{r['PSW']:04x} "
          f"CW={r['CW']:04x} IX={r['IX']:04x} IY={r['IY']:04x}",
          flush=True)
    for t in res["test_txns"]:
        if t["kind"] != "CODE":
            print(f"   {t['kind']} @{t['addr']:05x} data={t['data']:04x} "
                  f"ube_n={t['ube_n']}", flush=True)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["all", "followup"])
    ap.add_argument("--host", default="root@mister-nec")
    args = ap.parse_args()
    if args.cmd == "followup":
        return cmd_followup(args.host)
    bad = [b for b in PROBES if b in DOCUMENTED or b in NEVER]
    if bad:
        print(f"REFUSING: probe list contains excluded bytes {bad}")
        return 1
    results = []
    for b in PROBES:
        print(f"0F {b:02X}:", flush=True)
        r = probe(args.host, b)
        results.append(r)
        log_line(r)
        if r["status"] == "executed":
            print(f"  len={r['length']} markers={r['markers_inc']} "
                  f"other={r['other_reg_changes']} psw={r['psw']} "
                  f"txns={r['noncode_txns']}", flush=True)
        else:
            print(f"  {r['status'].upper()} {r.get('error', '')}",
                  flush=True)
    print("\nJSON summary:", flush=True)
    print(json.dumps(results, indent=1), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
