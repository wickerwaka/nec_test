#!/usr/bin/env python3
"""Physical one-factor sweeps for opposing odd immediate-INS write rails."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path

from b1_recapture import board_idle
from causal_wrand import accesses
from check_seq import compose, run_chip, run_tb
from gen_seq import generate


CASES = {
    8336: {
        "lfsr": 38263, "target": 0x2CD1, "write": 242,
        "roles": {"CLAST": 239, "RFIRST": 240, "RSECOND": 241},
    },
    8276: {
        "lfsr": 49723, "target": 0x2AAD, "write": 67,
        "roles": {"CLAST": 64, "RFIRST": 65, "RSECOND": 66},
    },
    8579: {
        "lfsr": 50156, "target": 0x29BB, "write": 97,
        "roles": {"CLAST": 94, "RFIRST": 95, "RSECOND": 96},
    },
}


def wait_vector(initial, n=4096):
    lfsr = initial & 0xffff
    result = []
    for _ in range(n):
        result.append(((lfsr & 0xff) * 16) >> 8)
        lfsr = (lfsr >> 1) ^ (0xb400 if lfsr & 1 else 0)
    return result


def encode(rows):
    return json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()


def target(rows, ordinal, address):
    bus = accesses(rows)
    access = bus[ordinal]
    if access["bs"] != 6 or access["addr"] != address:
        raise RuntimeError(f"target write moved: {access}")
    return access, bus[max(0, ordinal - 3):ordinal + 3]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="root@mister-nec")
    parser.add_argument("--seeds", default="8276,8579")
    parser.add_argument("--roles", default="CLAST,RFIRST,RSECOND")
    parser.add_argument("--waits", default="0,1,2,3,4,5,6,7,15")
    parser.add_argument("--out", type=Path,
                        default=Path("sw/case165_ins_split_write_factorial.json"))
    parser.add_argument("--raw-dir", type=Path,
                        default=Path("sw/testdata/biu_blackbox/case165_ins_split"))
    args = parser.parse_args()
    args.raw_dir.mkdir(parents=True, exist_ok=True)
    exts = tuple(x for x in Path("sw/case31_all_exts.txt").read_text().strip().split(",") if x)
    roles = tuple(x.strip().upper() for x in args.roles.split(",") if x)
    waits = tuple(int(x, 0) for x in args.waits.split(",") if x)
    records = []
    try:
        for seed in (int(x) for x in args.seeds.split(",") if x):
            case = CASES[seed]
            image, _ = compose(generate(f"fz{seed}", exts=exts))
            base = wait_vector(case["lfsr"])
            for history in ("A", "B"):
                prepared = list(base)
                if history == "B":
                    prepared[5], prepared[6] = prepared[6], prepared[5]
                for role in roles:
                    selected = case["roles"][role]
                    for wait in waits:
                        vector = list(prepared)
                        vector[selected] = wait
                        chip_rows = run_chip(
                            image, args.host, use_core=False, wvec=vector)
                        rtl_rows = run_tb(image, 4200, wvec=vector)
                        chip, chip_near = target(
                            chip_rows, case["write"], case["target"])
                        rtl, rtl_near = target(
                            rtl_rows, case["write"], case["target"])
                        payload = encode(chip_rows)
                        sha = hashlib.sha256(payload).hexdigest()
                        raw_path = args.raw_dir / (
                            f"fz{seed}_{history}_{role}_w{wait:02d}_{sha[:12]}.json.gz")
                        with gzip.open(raw_path, "wb") as stream:
                            stream.write(payload)
                        records.append({
                            "seed": seed, "history": history, "role": role,
                            "selected": selected, "wait": wait,
                            "chip_write": chip, "rtl_write": rtl,
                            "chip_near": chip_near, "rtl_near": rtl_near,
                            "raw_capture_sha256": sha,
                            "raw_capture": str(raw_path),
                        })
                        print(
                            f"fz{seed} H={history} {role} w={wait:2d} "
                            f"write={chip['t1']}/{rtl['t1']} "
                            f"delta={rtl['t1']-chip['t1']:+d}", flush=True)
        args.out.write_text(json.dumps({
            "schema": "v30-eu-ins-split-write-factorial-v1",
            "records": records,
        }, indent=2, sort_keys=True) + "\n")
    finally:
        board_idle()
        print("board idle; use_core=0", flush=True)


if __name__ == "__main__":
    main()
