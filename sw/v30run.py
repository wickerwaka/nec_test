#!/usr/bin/env python3
"""v30run - run composed test images on the harness and extract results.

Local orchestrator: composes the image (testimage.py), ships it to the DE10
over SSH, runs it via v30ctl.py, pulls the capture back, and parses the
trace into injected/final register state per docs/notes/loadstore_design.md.

Requires large (max) mode on the harness (queue status not yet used by this
parser, but the T-state/BS transaction extraction is the large-mode path).

Usage:
  v30run.py echo [--host root@mister-nec]      # register echo experiment
  v30run.py psw-probe [--host ...]             # PSW reserved-bit probe
"""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import testimage                                    # noqa: E402
from analyze_capture import decode_large            # noqa: E402

REMOTE_DIR = "/media/fat/v30"


class RunError(Exception):
    pass


def run_image(image, host, tag="test", waits=0):
    """Ship the image, run it, return the capture records."""
    with tempfile.TemporaryDirectory() as td:
        binp = Path(td) / f"{tag}.bin"
        capp = Path(td) / f"{tag}.hex"
        binp.write_bytes(image)
        subprocess.run(["scp", "-q", str(binp), f"{host}:{REMOTE_DIR}/"],
                       check=True, timeout=60)
        r = subprocess.run(
            ["ssh", host,
             f"cd {REMOTE_DIR} && "
             f"timeout 10 python3 v30ctl.py cfg --small 0 --waits {waits} "
             f">/dev/null && "
             f"timeout 30 python3 v30ctl.py run "
             f"{tag}.bin --cap {tag}.hex --timeout 3"],
            capture_output=True, text=True, timeout=90)
        if r.returncode != 0:
            raise RunError(f"remote run failed: {r.stdout} {r.stderr}")
        subprocess.run(["scp", "-q", f"{host}:{REMOTE_DIR}/{tag}.hex",
                        str(capp)], check=True, timeout=60)
        return decode_large(str(capp))


def extract_txns_large(recs):
    """Bus transactions via the harness FSM T-state annotations."""
    txns, cur = [], None
    for r in recs:
        t = r["t"]
        if t == 1:      # T1
            cur = {"start": r["idx"], "kind": r["bs_early"],
                   "addr": r["ad_addr"], "data": None,
                   "ube_n": r["ube_n"]}
        elif t in (3, 4) and cur:   # T3/TW
            cur["data"] = r["ad_data"]
        elif t == 5 and cur:        # T4
            cur["end"] = r["idx"]
            txns.append(cur)
            cur = None
    return txns


KIND = {0: "INTA", 1: "IOR", 2: "IOW", 3: "HALT",
        4: "CODE", 5: "MEMR", 6: "MEMW", 7: "PASV"}


def parse_result(recs, meta):
    """Phase-split the trace and extract final register state."""
    txns = extract_txns_large(recs)

    # store anchor: first IOW at the register port
    regw = [t for t in txns if KIND[t["kind"]] == "IOW"
            and (t["addr"] & 0xFFFF) == testimage.OUT_PORT_REGS]
    done = [t for t in txns if KIND[t["kind"]] == "IOW"
            and (t["addr"] & 0xFFFF) == testimage.OUT_PORT_DONE]
    if not done:
        raise RunError("no done marker in trace (runaway test?) — quarantine")
    if done[0]["data"] != meta["done_sentinel"]:
        raise RunError(f"done marker data {done[0]['data']:04x} != sentinel")
    if len(regw) < len(meta["store_order"]):
        raise RunError(f"only {len(regw)} register words in trace")

    regs_out = {name: regw[i]["data"]
                for i, name in enumerate(meta["store_order"])}

    # PSW from the PUSH PSW memory write in the scratch area
    pushes = [t for t in txns if KIND[t["kind"]] == "MEMW"
              and t["addr"] == meta["psw_push_addr"]]
    regs_out["PSW"] = pushes[-1]["data"] if pushes else None

    # final PC from stub placement (design section 4)
    regs_out["PC"] = (meta["stub_linear"] + 6  # 6-NOP pad executed
                      - ((regs_out["PS"] << 4) & 0xFFFFF)) & 0xFFFF

    # test-phase bus activity: anchor .. store anchor
    anchor_i = next((i for i, t in enumerate(txns)
                     if t["addr"] == meta["anchor_linear"]
                     and KIND[t["kind"]] == "CODE"), None)
    store_i = txns.index(regw[0])
    test_txns = txns[anchor_i:store_i] if anchor_i is not None else []

    return {
        "regs": regs_out,
        "test_txns": [
            {"kind": KIND[t["kind"]], "addr": t["addr"], "data": t["data"],
             "ube_n": t["ube_n"], "cycles": t["end"] - t["start"] + 1}
            for t in test_txns],
    }


def run_test(regs=None, instr=b"", host="root@mister-nec", tag="test",
             ivt=None, stub_linear=None, waits=0):
    image, meta = testimage.compose(regs=regs, instr=instr, ivt=ivt,
                                    stub_linear=stub_linear)
    recs = run_image(image, host, tag, waits=waits)
    res = parse_result(recs, meta)
    res["meta"] = meta
    res["recs"] = recs
    return res


#----------------------------------------------------------------------------
def cmd_echo(host):
    """Inject distinctive values into every register, empty test body,
    verify they all echo back."""
    inject = {
        "AW": 0x1111, "BW": 0x2222, "CW": 0x3333, "DW": 0x4444,
        "SP": 0x5555, "BP": 0x6666, "IX": 0x7777, "IY": 0x8888,
        "DS0": 0x9999, "DS1": 0xAAAA, "SS": 0xBBBB,
        "PS": 0x0000, "PC": 0x0400,
        "PSW": 0x0000,   # normalized: reserved bits forced
    }
    res = run_test(regs=inject, instr=b"", host=host, tag="echo")
    regs = res["regs"]
    exp = res["meta"]["regs_in"]
    fails = 0
    for name in testimage.STORE_ORDER + ["PSW", "PC"]:
        want = exp[name] if name != "PC" else (exp["PC"] + 6) & 0xFFFF
        got = regs.get(name)
        ok = got == want
        # PSW compare: only the normalized-injected value
        if name == "PSW" and got is not None:
            ok = got == exp["PSW"]
            want = exp["PSW"]
        mark = "ok " if ok else "FAIL"
        if not ok:
            fails += 1
        print(f"{mark} {name:<4} injected {want:04x} read back "
              f"{got if got is None else f'{got:04x}'}")
    print("ECHO TEST PASSED" if fails == 0 else f"{fails} REGISTER(S) FAILED")
    return 1 if fails else 0


def cmd_psw_probe(host):
    """Which PSW bits are writable? Inject patterns without normalization
    guard rails (except MD, kept 1 for safety) and read back."""
    for pattern in (0x0000, 0x0FD5, 0x0AA0, 0x0555):
        res = run_test(regs={"PSW": pattern, "PS": 0, "PC": 0x0400},
                       instr=b"", host=host, tag="pswprobe")
        injected = res["meta"]["regs_in"]["PSW"]
        got = res["regs"]["PSW"]
        print(f"requested {pattern:04x} injected {injected:04x} "
              f"read back {got:04x} diff {injected ^ got:04x}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["echo", "psw-probe"])
    ap.add_argument("--host", default="root@mister-nec")
    args = ap.parse_args()
    if args.cmd == "echo":
        sys.exit(cmd_echo(args.host))
    if args.cmd == "psw-probe":
        sys.exit(cmd_psw_probe(args.host))


if __name__ == "__main__":
    main()
