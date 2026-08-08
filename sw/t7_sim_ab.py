#!/usr/bin/env python3
"""T7 inertness A/B: pre-change v30sim vs post-change v30sim, byte-for-byte.

The standing `timed_fuzz.py --evt-replay` ratchet cannot run in this tree --
`uf.regen` raises `body [0500,073f) is not inside the code region [8000,c000)`
on all 3,242 banked seeds, i.e. T1's v2 `testimage.compose` refuses the
DISCARDED v1 corpus, before `sim/` is ever invoked.  This is the substitute:
the same `timed-boot --evt` code path, driven over a battery of images and
LEGACY-SHAPE directives, with the two binaries' stdout+stderr compared byte
for byte.
"""
import itertools
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path("/home/wickerwaka/src/nec_test")
sys.path.insert(0, str(ROOT / "sw"))
import testimage as ti  # noqa: E402

NEW = str(ROOT / "sim/build/v30sim")
ROM = str(ROOT / "docs/V20BITS.TXT")
TMP = Path(os.environ.get("T7TMP", str(Path.home() / ".cache/ucsimt-tmp/t7ab")))
TMP.mkdir(parents=True, exist_ok=True)


def build_baseline():
    """The PRE-CHANGE model, built from `git show <REF>:sim/*` in a temp tree.

    Built here rather than taken from a path so the comparison is reproducible
    by anyone re-running this file.  `T7_BASE_REF` selects the reference
    commit; the default is the tip before this task's `sim/` edits."""
    ref = os.environ.get("T7_BASE_REF", "HEAD")
    out = TMP / "base"
    binp = TMP / "v30sim.base"
    files = subprocess.run(["git", "-C", str(ROOT), "ls-tree", "--name-only",
                            f"{ref}:sim"], capture_output=True, text=True,
                           check=True).stdout.split()
    out.mkdir(parents=True, exist_ok=True)
    for f in files:
        if f.endswith((".cpp", ".h", ".hex")) or f == "Makefile":
            blob = subprocess.run(["git", "-C", str(ROOT), "show",
                                   f"{ref}:sim/{f}"], capture_output=True,
                                  check=True).stdout
            (out / f).write_bytes(blob)
    subprocess.run(["make", "-B", "-j8", "-C", str(out), "CXX=g++",
                    f"BIN={binp}"], check=True, capture_output=True)
    return str(binp)

PS, PC = ti.REG_DEFAULTS["PS"], ti.REG_DEFAULTS["PC"]
ANCHOR = (PS << 4) + PC

BODIES = {
    "spin":  bytes([0xEB, 0xFE]),                              # JMP $
    "halt":  bytes([0xF4, 0xF4, 0xF4, 0xF4]),                  # HLT
    "poll":  bytes([0x9B, 0x90, 0xEB, 0xFB]),                  # POLL; NOP; JMP
    "work":  bytes([0xB8, 0x34, 0x12, 0x01, 0xC3, 0xA1, 0x00,  # MOV/ADD/MOV
                    0x21, 0xA3, 0x02, 0x21, 0xEB, 0xF3]),
    "iow":   bytes([0xE7, 0xFE, 0x40, 0xEB, 0xFB]),            # OUT 0xFE,AW
}


def image_for(body):
    img, _ = ti.compose(instr=body, ivt={2: (0x0000, 0x2800)},
                        ram=[(0x2800, 0xEB), (0x2801, 0xFE)])
    return img


def run(binp, img_path, evt_path, waits, clocks=2500):
    cmd = [binp, "timed-boot", ROM, str(img_path), f"--clocks={clocks}",
           "--ndjson", f"--waits={waits}"]
    if evt_path is not None:
        cmd.append(f"--evt={evt_path}")
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr


def main():
    global BASE
    BASE = build_baseline()
    print(f"baseline: {BASE}")
    imgs = {}
    for name, body in BODIES.items():
        pth = TMP / f"{name}.bin"
        pth.write_bytes(image_for(body))
        imgs[name] = pth

    # LEGACY-SHAPE directives: the schedule's fields at the TOP level and the
    # firing arrays at the top level too -- exactly what sw/timed_fuzz.py's
    # `evt_directive` writes today.
    directives = []
    for pin, delay, hold in itertools.product((0, 1, 2), (0, 5, 40), (0, 12, 300)):
        directives.append({"pin": pin, "addr": ANCHOR, "delay": delay,
                           "hold": hold, "pins": 4 if pin == 2 else 0,
                           "at": [0], "cs": [PS], "ip": [PC]})
    # ...and the no-firing forms (schedule only), and the empty one
    for pin in (0, 1, 2):
        directives.append({"pin": pin, "addr": ANCHOR, "delay": 7, "hold": 50,
                           "pins": 4 if pin == 2 else 0})
    directives.append({"pin": 0, "addr": ANCHOR, "delay": 0, "hold": 0,
                       "pins": 0})
    for i, d in enumerate(directives):
        (TMP / f"e{i}.json").write_text(json.dumps(d))

    n = diff = 0
    firsts = []
    for name, ip_ in imgs.items():
        for waits in (0, 1, 3):
            for k, d in enumerate(directives):
                ep = TMP / f"e{k}.json"
                a = run(BASE, ip_, ep, waits)
                b = run(NEW, ip_, ep, waits)
                n += 1
                if a != b:
                    diff += 1
                    if len(firsts) < 5:
                        firsts.append((name, waits, k))
            # ...and with NO --evt at all
            a = run(BASE, ip_, None, waits)
            b = run(NEW, ip_, None, waits)
            n += 1
            if a != b:
                diff += 1
                if len(firsts) < 5:
                    firsts.append((name, waits, "no-evt"))

    print(f"timed-boot A/B: {n} runs, {diff} differing")
    if firsts:
        print("  first differences:", firsts)

    # --- the FUNCTIONAL leg -------------------------------------------------
    # `image` output gained one key (`"vecused":N,`); everything else must be
    # byte-identical, so the comparison strips exactly that key from the new
    # output and nothing else.
    recs = []
    for name, ip_ in imgs.items():
        img = ip_.read_bytes()
        for k, d in enumerate(directives[:10] + directives[-4:]):
            legacy = {"pin": d["pin"], "at": d.get("at", []),
                      "cs": d.get("cs", []), "ip": d.get("ip", [])}
            recs.append({"i": len(recs), "hex": img.hex(), "max_ins": 3000,
                         "max_ev": 20000, "tf": 0, "evt": legacy})
    inp = "\n".join(json.dumps(r) for r in recs) + "\n"
    pa = subprocess.run([BASE, "image", ROM], input=inp, capture_output=True,
                        text=True)
    pb = subprocess.run([NEW, "image", ROM], input=inp, capture_output=True,
                        text=True)
    import re
    stripped = re.sub(r'"vecused":\d+,', "", pb.stdout)
    same = (pa.stdout == stripped) and pa.returncode == pb.returncode == 0
    nvec = pb.stdout.count('"vecused"')
    print(f"image A/B: {len(recs)} records, "
          f"{'IDENTICAL' if same else '*** DIFFER ***'} "
          f"(after removing the {nvec} new `vecused` keys)")
    if not same:
        la, lb = pa.stdout.splitlines(), stripped.splitlines()
        for i, (x, y) in enumerate(zip(la, lb)):
            if x != y:
                print("  first differing record", i)
                print("   base:", x[:300])
                print("   new :", y[:300])
                break
    ok = diff == 0 and same
    print("T7 A/B INERTNESS:", "PASS" if ok else "*** FAIL ***")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
