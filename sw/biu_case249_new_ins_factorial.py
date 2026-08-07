#!/usr/bin/env python3
"""Physical semantic-role factorials for prospective INS residuals.

Each retained cell changes one observable bus access wait, verifies that the
requested Tw count was actually delivered on chip and RTL, and records both
write rails.  Structural ordinals select interventions only; derived records
also resolve the read/write roles from bus kind and address.
"""

import argparse
import gzip
import hashlib
import json
from pathlib import Path

from b1_recapture import board_idle
from causal_wrand import accesses
from check_seq import compose, run_chip, run_tb
from gen_seq import generate
from biu_case165_ins_split_write_factorial import encode, wait_vector


CASES = {
    12302: {
        "lfsr": 0x85E9, "family": "ALIGNED_IMMEDIATE_INS_OFF2_LEN9",
        "target": 0x02B3C,
        "roles": {"R1": 164, "C1": 165, "C2": 166, "R2": 167,
                  "W1": 168},
    },
    12466: {
        "lfsr": 0x8555, "family": "SPLIT_IMMEDIATE_INS_OFF1_LEN7",
        "target": 0x02CCF,
        "roles": {"R1L": 53, "R1H": 54, "C1": 55, "C2": 56,
                  "R2L": 57, "R2H": 58, "W1": 59, "W2": 60},
    },
    12547: {
        "lfsr": 0x84E4, "family": "SPLIT_IMMEDIATE_INS_OFF1_LEN8",
        "target": 0x02B79,
        "roles": {"R1L": 47, "R1H": 48, "C1": 49, "C2": 50,
                  "R2L": 51, "R2H": 52, "W1": 53, "W2": 54},
    },
    12569: {
        "lfsr": 0x84FE, "family": "ALIGNED_IMMEDIATE_INS_OFF1_LEN7",
        "target": 0x02A70,
        "roles": {"R1": 107, "C1": 108, "R2": 109, "W1": 110},
    },
}


def resolve(rows, case):
    bus = accesses(rows)
    target = case["target"]
    split = case["family"].startswith("SPLIT_")
    w1s = [i for i, a in enumerate(bus)
           if a["bs"] == 6 and a["addr"] == target]
    if not w1s:
        raise RuntimeError("target low write missing")
    w1 = w1s[-1]
    writes = [w1]
    if split:
        w2s = [i for i, a in enumerate(bus[w1:], w1)
               if a["bs"] == 6 and a["addr"] == target + 1]
        if not w2s:
            raise RuntimeError("target high write missing")
        writes.append(w2s[0])
        reads = [i for i, a in enumerate(bus[:w1])
                 if a["bs"] == 5 and a["addr"] in (target, target + 1)]
        if len(reads) < 4:
            raise RuntimeError(f"target split reads missing: {reads}")
        reads = reads[-4:]
    else:
        reads = [i for i, a in enumerate(bus[:w1])
                 if a["bs"] == 5 and a["addr"] == target]
        if len(reads) < 2:
            raise RuntimeError(f"target reads missing: {reads}")
        reads = reads[-2:]
    return bus, [bus[x] for x in writes], {"reads": reads, "writes": writes}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="root@mister-nec")
    ap.add_argument("--seeds", default=",".join(str(x) for x in CASES))
    ap.add_argument("--waits", default=",".join(str(i) for i in range(16)))
    ap.add_argument("--roles", default="all")
    ap.add_argument("--histories", default="A,B")
    ap.add_argument("--out", type=Path,
                    default=Path("sw/case249_new_ins_factorial.json"))
    ap.add_argument("--raw-dir", type=Path, default=Path(
        "sw/testdata/biu_blackbox/case249_new_ins"))
    args = ap.parse_args()
    args.raw_dir.mkdir(parents=True, exist_ok=True)
    waits = tuple(int(x, 0) for x in args.waits.split(",") if x)
    requested = None if args.roles == "all" else tuple(
        x.strip().upper() for x in args.roles.split(",") if x)
    histories = tuple(x for x in args.histories.split(",") if x)
    exts = tuple(x for x in Path("sw/case31_all_exts.txt").read_text()
                 .strip().split(",") if x)
    records = []
    try:
        for seed in (int(x) for x in args.seeds.split(",") if x):
            case = CASES[seed]
            image, _ = compose(generate(f"fz{seed}", exts=exts))
            base = wait_vector(case["lfsr"])
            resolve(run_tb(image, 4200, wvec=base), case)
            roles = requested or tuple(case["roles"])
            for history in histories:
                prepared = list(base)
                if history == "B":
                    prepared[5], prepared[6] = prepared[6], prepared[5]
                for role in roles:
                    if role not in case["roles"]:
                        continue
                    selected = case["roles"][role]
                    for wait in waits:
                        vector = list(prepared)
                        vector[selected] = wait
                        chip_rows = run_chip(
                            image, args.host, use_core=False, wvec=vector)
                        rtl_rows = run_tb(image, 4200, wvec=vector)
                        chip_bus, chip_writes, chip_resolved = resolve(
                            chip_rows, case)
                        rtl_bus, rtl_writes, rtl_resolved = resolve(
                            rtl_rows, case)
                        for side, bus in (("chip", chip_bus),
                                          ("RTL", rtl_bus)):
                            if bus[selected]["tw"] != wait:
                                raise RuntimeError(
                                    f"fz{seed} H={history} {role} requested "
                                    f"Tw={wait}, {side} observed "
                                    f"Tw={bus[selected]['tw']}")
                        payload = encode(chip_rows)
                        sha = hashlib.sha256(payload).hexdigest()
                        raw = args.raw_dir / (
                            f"fz{seed}_{history}_{role}_w{wait:02d}_"
                            f"{sha[:12]}.json.gz")
                        with gzip.open(raw, "wb") as stream:
                            stream.write(payload)
                        lo = min(case["roles"].values()) - 3
                        hi = max(case["roles"].values()) + 3
                        record = {
                            "seed": seed, "family": case["family"],
                            "history": history, "role": role,
                            "selected": selected, "wait": wait,
                            "chip_writes": chip_writes,
                            "rtl_writes": rtl_writes,
                            "chip_resolved": chip_resolved,
                            "rtl_resolved": rtl_resolved,
                            "chip_near": chip_bus[lo:hi],
                            "rtl_near": rtl_bus[lo:hi],
                            "raw_capture": str(raw),
                            "raw_capture_sha256": sha,
                        }
                        records.append(record)
                        args.out.write_text(json.dumps({
                            "schema": "v30-case249-new-ins-factorial-v1",
                            "cases": CASES, "records": records,
                        }, indent=2, sort_keys=True) + "\n")
                        pairs = ",".join(
                            f"{c['t1']}/{r['t1']}"
                            for c, r in zip(chip_writes, rtl_writes))
                        print(f"fz{seed} H={history} {role} w={wait:2d} "
                              f"writes={pairs}", flush=True)
    finally:
        board_idle()
        print("board idle; use_core=0", flush=True)


if __name__ == "__main__":
    main()
