#!/usr/bin/env python3
"""T7 proof harness: the sim/ multi-schedule + NMI vector overlay legs.

Six legs, of which three are CONTROLS.  Every leg composes a REAL v2 image via
sw/testimage.compose, points TVEC at testimage.TERM_AT, and plants a
DELIBERATELY WRONG vector 2 (an infinite `JMP $` in the data window) so that a
run which does NOT take the substituted vector cannot terminate by accident.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path("/home/wickerwaka/src/nec_test")
sys.path.insert(0, str(ROOT / "sw"))
import testimage as ti  # noqa: E402

SIM = str(ROOT / "sim/build/v30sim")
ROM = str(ROOT / "docs/V20BITS.TXT")
TMP = Path(os.environ.get("T7TMP", str(Path.home() / ".cache/ucsimt-tmp/t7")))
TMP.mkdir(parents=True, exist_ok=True)


def build_preguard():
    """L7's NON-VACUITY CONTROL: this tree's sim/ with `BootEvt::of`'s
    empty-schedule guard REMOVED, so the check that the guard works can be
    shown to bite.  Returns the binary path, or None if the patch no longer
    applies (in which case the control is reported as unavailable rather than
    silently skipped)."""
    src = ROOT / "sim"
    out = TMP / "preguard"
    binp = TMP / "v30sim.preguard"
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(src, out,
                    ignore=shutil.ignore_patterns("*.o", "*.d", "build",
                                                  "v30sim"))
    f = out / "timed_runner.cpp"
    t = f.read_text()
    guard = ("        static const BootSched kNone;\n"
             "        if (sch.empty()) return kNone;\n")
    if guard not in t:
        return None
    f.write_text(t.replace(guard, ""))
    r = subprocess.run(["make", "-B", "-j8", "-C", str(out), "CXX=g++",
                        f"BIN={binp}"], capture_output=True)
    return str(binp) if r.returncode == 0 else None

WRONG_AT = 0x2800            # in the DATA carve-out (never 0xCC)
TVEC = (0x0000 << 16) | ti.TERM_AT      # CS=0000, IP=BF00
ANCHOR_LIN = (ti.REG_DEFAULTS["PS"] << 4) + ti.REG_DEFAULTS["PC"]

BODY_SPIN = bytes([0xEB, 0xFE])                          # JMP $
BODY_IOR = bytes([0xE4, 0x09, 0x8B, 0xD8, 0xEB, 0xFA])   # IN AL,9; MOV BW,AW; JMP
BODY_MEMR = bytes([0xA0, 0x09, 0x00, 0x8B, 0xD8, 0xEB, 0xF9])  # MOV AL,[9]; ...
BODY_MEMR_CS = bytes([0xA0, 0x0A, 0x00, 0x8B, 0xD8, 0xEB, 0xF9])  # ...[0x0A]


def build_image(body):
    img, meta = ti.compose(
        instr=body,
        ivt={2: (0x0000, WRONG_AT)},
        ram=[(WRONG_AT, 0xEB), (WRONG_AT + 1, 0xFE)],   # JMP $ at the wrong vector
    )
    return img, meta


def evt_doc(scheds, at, cs, ip, which, tvec=TVEC, pins=0):
    return {
        "evt": scheds,
        "pins": pins,
        "tvec": tvec,
        "fire": {"at": at, "cs": cs, "ip": ip, "which": which},
    }


# --------------------------------------------------------------------------- #
def run_functional(img, doc, max_ins=4000):
    rec = {"i": 0, "hex": img.hex(), "max_ins": max_ins, "max_ev": 20000,
           "tf": 0, "code": 0, "tvec": doc["tvec"],
           "evt": doc["evt"], "fire": doc["fire"]}
    p = subprocess.run([SIM, "image", ROM], input=json.dumps(rec) + "\n",
                       capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"image rc={p.returncode}: {p.stderr[:400]}")
    return json.loads(p.stdout.strip().splitlines()[0])


IOW, IOR = 4, 3          # Txn::Kind


def func_dump(out):
    """(words OUT to 0xFE, the value OUT to 0xFC or None)."""
    fe, fc = [], None
    for k, addr, _a2, data, _w in out["tx"]:
        if k != IOW:
            continue
        port = addr & 0xFFFF
        if port == ti.OUT_PORT_REGS:
            fe.append(data)
        elif port == ti.OUT_PORT_DONE:
            fc = data
    return fe, fc


# --------------------------------------------------------------------------- #
def run_timed(img, doc, clocks=6000, waits=0):
    ib = TMP / "img.bin"
    ib.write_bytes(img)
    ej = TMP / "evt.json"
    ej.write_text(json.dumps(doc))
    p = subprocess.run([SIM, "timed-boot", ROM, str(ib), f"--clocks={clocks}",
                        "--ndjson", f"--waits={waits}", f"--evt={ej}"],
                       capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"timed-boot rc={p.returncode}: {p.stderr[:400]}")
    rows, final = [], None
    for line in p.stdout.splitlines():
        r = json.loads(line)
        if "final" in r:
            final = r["final"]
        else:
            rows.append(r)
    return rows, final, p.stderr


def timed_cycles(rows):
    """[(bs, addr, data)] one per bus cycle.

    The T1 row carries the ADDRESS phase; T2/T3/Tw carry the data phase; the
    T4 row already displays the NEXT cycle's address and status (M1/M2), so it
    closes the cycle and contributes nothing to it."""
    out, cur = [], None
    for r in rows:
        t = r["t"]
        if t == 1:                                   # ST_T1
            if cur:
                out.append(tuple(cur))
            cur = [r["bs_early"], r["ad_addr"], None]
        elif cur is not None and t in (2, 3, 4):     # T2 / T3 / Tw
            cur[2] = r["ad_data"]
        elif cur is not None:                        # T4 or TI: cycle over
            out.append(tuple(cur))
            cur = None
    if cur:
        out.append(tuple(cur))
    return out


def timed_dump(rows):
    fe, fc = [], None
    for bs, addr, data in timed_cycles(rows):
        if bs != 2:                            # kBsIoW
            continue
        port = addr & 0xFFFF
        if port == ti.OUT_PORT_REGS:
            fe.append(data)
        elif port == ti.OUT_PORT_DONE:
            fc = data
    return fe, fc


# --------------------------------------------------------------------------- #
RES = []


def chk(name, cond, detail=""):
    RES.append(bool(cond))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))


def hdr(t):
    print()
    print("=" * 76)
    print(t)
    print("=" * 76)


TERM = dict(pin=1, addr=ANCHOR_LIN, delay=0, hold=64, vecsub=1)
STIM = dict(pin=1, addr=ANCHOR_LIN, delay=0, hold=64, vecsub=0)
# ...and the terminator with its assert still FAR IN THE FUTURE, so the
# must-not-fire control tests a schedule that is ARMED and has NOT YET FIRED.
# (A terminator that HAS fired arms the overlay for whatever recognition comes
# next -- that is the RTL's stated semantics, `|(ev_fire_pulse & vecsub_en)`,
# and it is not what "must not fire" means.)
TERM_LATE = dict(pin=1, addr=ANCHOR_LIN, delay=400, hold=64, vecsub=1)
LOOP_CS, LOOP_IP = ti.REG_DEFAULTS["PS"], ti.REG_DEFAULTS["PC"]


def main():
    img_spin, meta = build_image(BODY_SPIN)
    print(f"image: anchor {meta['anchor_linear']:#07x}  TERM_AT {ti.TERM_AT:#06x}  "
          f"TVEC {TVEC:#010x}  wrong vector 2 -> 0000:{WRONG_AT:04X}")
    print(f"       image[8..B] = {img_spin[8:12].hex()}  "
          f"(the WRONG vector the overlay must replace)")
    assert img_spin[8:12] == bytes([WRONG_AT & 0xFF, WRONG_AT >> 8, 0, 0])

    # ---------------------------------------------------------------- L1 ----
    hdr("L1  POSITIVE -- terminating NMI, vecsub=1, both engines")
    doc = evt_doc([TERM], at=[0], cs=[LOOP_CS], ip=[LOOP_IP], which=[0])
    f = run_functional(img_spin, doc)
    fe, fc = func_dump(f)
    chk("functional: fired 1", f["fired"] == 1, f"fired={f['fired']}")
    chk("functional: vecused", f["vecused"] == 1)
    chk("functional: 15 words OUT 0xFE", len(fe) == 15,
        f"{len(fe)}: {[hex(x) for x in fe]}")
    chk("functional: MAGIC at index 1", len(fe) > 1 and fe[1] == ti.MAGIC,
        f"{fe[1]:#06x}" if len(fe) > 1 else "")
    chk("functional: done marker 0xF00D to 0xFC", fc == ti.DONE_SENTINEL,
        f"{fc}")
    chk("functional: dumped PC/PS are the seed's loop, not the wrong vector",
        len(fe) > 3 and fe[2] == LOOP_IP and fe[3] == LOOP_CS,
        f"PC={fe[2]:#06x} PS={fe[3]:#06x}" if len(fe) > 3 else "")

    rows, final, err = run_timed(img_spin, doc)
    tfe, tfc = timed_dump(rows)
    chk("timed: 15 words OUT 0xFE", len(tfe) == 15,
        f"{len(tfe)}: {[hex(x) for x in tfe]}")
    chk("timed: MAGIC at index 1", len(tfe) > 1 and tfe[1] == ti.MAGIC)
    chk("timed: done marker 0xF00D to 0xFC", tfc == ti.DONE_SENTINEL, f"{tfc}")
    chk("timed and functional dumps are identical", tfe == fe,
        f"timed={[hex(x) for x in tfe]}")
    # the substituted word really was on the pins
    memr = [(a, d) for bs, a, d in timed_cycles(rows) if bs == 5]
    vecr = [(a, d) for a, d in memr if (a & 0xFFFFC) == 8]
    chk("timed: the two vector MEMR cycles are at linear 8 and A",
        [a for a, _ in vecr] == [8, 0xA], f"{[(hex(a), hex(d)) for a, d in vecr]}")
    chk("timed: their data phases carry TVEC, not memory",
        [d for _, d in vecr] == [TVEC & 0xFFFF, TVEC >> 16],
        f"{[hex(d) for _, d in vecr]}")
    chk("timed: no INTA cycle in the entry",
        not any(bs == 0 for bs, _, _ in timed_cycles(rows)))

    # ---------------------------------------------------------------- L2 ----
    hdr("L2  NEGATIVE CONTROL -- identical image and event, vecsub=0")
    doc0 = evt_doc([STIM], at=[0], cs=[LOOP_CS], ip=[LOOP_IP], which=[0])
    f0 = run_functional(img_spin, doc0)
    fe0, fc0 = func_dump(f0)
    chk("functional: fired 1", f0["fired"] == 1, f"fired={f0['fired']}")
    chk("functional: vecused == 0", f0["vecused"] == 0)
    chk("functional: NOT done", f0["done"] == 0)
    chk("functional: no words OUT 0xFE", len(fe0) == 0, f"{len(fe0)}")
    chk("functional: no done marker", fc0 is None, f"{fc0}")
    rows0, final0, _ = run_timed(img_spin, doc0)
    tfe0, tfc0 = timed_dump(rows0)
    chk("timed: no words OUT 0xFE", len(tfe0) == 0, f"{len(tfe0)}")
    chk("timed: no done marker", tfc0 is None, f"{tfc0}")
    vecr0 = [(a, d) for bs, a, d in timed_cycles(rows0)
             if bs == 5 and (a & 0xFFFFC) == 8]
    chk("timed: the vector reads returned MEMORY (the wrong vector)",
        [d for _, d in vecr0] == [WRONG_AT, 0x0000],
        f"{[(hex(a), hex(d)) for a, d in vecr0]}")
    chk("timed: the CPU went to the WRONG vector",
        final0 and final0["cs"] == 0 and final0["ip"] == WRONG_AT,
        f"cs={final0['cs']:#06x} ip={final0['ip']:#06x}" if final0 else "")

    # ---------------------------------------------------------------- L3 ----
    hdr("L3  MUST-NOT-FIRE CONTROL -- a stimulus NMI fires while a "
        "TERMINATING schedule is also armed")
    doc1 = evt_doc([STIM, TERM_LATE], at=[0], cs=[LOOP_CS], ip=[LOOP_IP], which=[0])
    f1 = run_functional(img_spin, doc1)
    fe1, fc1 = func_dump(f1)
    chk("functional: 2 schedules armed, firing names schedule 0",
        f1["fired"] == 1)
    chk("functional: vecused == 0 (the STIMULUS did not substitute)",
        f1["vecused"] == 0)
    chk("functional: NOT done", f1["done"] == 0 and not fe1)
    rows1, final1, _ = run_timed(img_spin, doc1)
    tfe1, tfc1 = timed_dump(rows1)
    chk("timed: no dump, no done marker", not tfe1 and tfc1 is None)
    chk("timed: the CPU went to the WRONG vector",
        final1 and final1["cs"] == 0 and final1["ip"] == WRONG_AT,
        f"cs={final1['cs']:#06x} ip={final1['ip']:#06x}" if final1 else "")
    # ...and TWO SCHEDULES, both asserting, with the firing naming the
    # TERMINATOR: it substitutes.  Without this the leg above proves only that
    # nothing fired.  The boundary is put 24 bus cycles in (the `IN AL,9`
    # loop's IOR cycles) so BOTH asserts are in the past when it is taken --
    # a directive shaped the way a real capture's is.
    img_ior2, _ = build_image(BODY_IOR)
    doc2 = evt_doc([STIM, dict(TERM, delay=60)],
                   at=[24], cs=[LOOP_CS], ip=[LOOP_IP], which=[1])
    f2 = run_functional(img_ior2, doc2)
    fe2, fc2 = func_dump(f2)
    chk("functional: 2 schedules, firing names the TERMINATOR -> terminates",
        f2["vecused"] == 1 and len(fe2) == 15 and fc2 == ti.DONE_SENTINEL,
        f"vecused={f2['vecused']} n={len(fe2)} done={fc2}")
    rows2, _, _ = run_timed(img_ior2, doc2, clocks=9000)
    tfe2, tfc2 = timed_dump(rows2)
    chk("timed: 2 schedules, firing names the TERMINATOR -> terminates",
        len(tfe2) == 15 and tfc2 == ti.DONE_SENTINEL,
        f"n={len(tfe2)} done={tfc2}")

    # ---------------------------------------------------------------- L4 ----
    hdr("L4  BS_MEMR QUALIFICATION -- `IN AL, 9` while ARMED is NOT "
        "intercepted, and `MOV AL,[9]` in the same window IS")
    # The window exists on the TIMED leg: the RTL arms at the schedule's own
    # assert clock and the recognition boundary is replayed, so the seed runs
    # between the two.  `at=24` puts the boundary 24 bus cycles in.
    img_ior, _ = build_image(BODY_IOR)
    d_ior = evt_doc([TERM], at=[24], cs=[LOOP_CS], ip=[LOOP_IP], which=[0])
    rows4, final4, _ = run_timed(img_ior, d_ior, clocks=9000)
    t4, c4 = timed_dump(rows4)
    ior4 = [(a & 0xFFFF, d) for bs, a, d in timed_cycles(rows4) if bs == 1]
    chk("timed IOR leg terminated (the overlay WAS armed through the loop)",
        len(t4) == 15 and c4 == ti.DONE_SENTINEL, f"n={len(t4)} done={c4}")
    chk("timed: >=8 IOR cycles at port 9 ran inside the armed window",
        sum(1 for p, _ in ior4 if p == 9) >= 8,
        f"{sum(1 for p, _ in ior4 if p == 9)} IOR at port 9")
    chk("timed: BW (the last IN AL,9 result) is the PORT constant 0x00FF, "
        "not TVEC's 0x00BF",
        final4 and final4["bx"] == 0x00FF,
        f"bx={final4['bx']:#06x}" if final4 else "")
    chk("timed: the dump's BW word agrees", len(t4) == 15 and t4[9] == 0x00FF,
        f"{t4[9]:#06x}" if len(t4) == 15 else "")

    img_mr, _ = build_image(BODY_MEMR)
    d_mr = evt_doc([TERM], at=[24], cs=[LOOP_CS], ip=[LOOP_IP], which=[0])
    rows5, final5, _ = run_timed(img_mr, d_mr, clocks=9000)
    t5, c5 = timed_dump(rows5)
    chk("timed MEMR leg terminated", len(t5) == 15 and c5 == ti.DONE_SENTINEL,
        f"n={len(t5)} done={c5}")
    chk("timed: BW (the last MOV AL,[9] result) IS TVEC's 0x00BF -- the SAME "
        "address, intercepted because the cycle is a MEMR",
        final5 and final5["bx"] == 0x00BF,
        f"bx={final5['bx']:#06x}" if final5 else "")
    # ...and with nothing armed the same read returns MEMORY
    d_mr0 = evt_doc([STIM], at=[24], cs=[LOOP_CS], ip=[LOOP_IP], which=[0])
    rows6, final6, _ = run_timed(img_mr, d_mr0, clocks=9000)
    chk("timed: unarmed, MOV AL,[9] returns MEMORY (0x0028)",
        final6 and final6["bx"] == 0x0028,
        f"bx={final6['bx']:#06x}" if final6 else "")

    # ---------------------------------------------------------------- L5 ----
    hdr("L5  THE DOCUMENTED CONSEQUENCE -- a seed MEMR of 0x0000A between the "
        "arm and the entry disarms the overlay EARLY (RTL parity, not a bug)")
    img_cs, _ = build_image(BODY_MEMR_CS)
    d_cs = evt_doc([TERM], at=[24], cs=[LOOP_CS], ip=[LOOP_IP], which=[0])
    rows7, final7, _ = run_timed(img_cs, d_cs, clocks=9000)
    t7, c7 = timed_dump(rows7)
    chk("timed: the seed's FIRST read of 0x0A saw TVEC's CS half, later ones "
        "saw memory (the overlay disarmed on it)",
        final7 and final7["bx"] == 0x0000,
        f"bx={final7['bx']:#06x}" if final7 else "")
    chk("timed: and the run therefore did NOT terminate -- the real vector "
        "CS half read memory", not t7 and c7 is None,
        f"n={len(t7)} done={c7}")

    # ---------------------------------------------------------------- L6 ----
    hdr("L6  INERTNESS -- with no schedules at all, byte-for-byte unchanged")
    p_none = subprocess.run([SIM, "timed-boot", ROM, str(TMP / "img.bin"),
                             "--clocks=3000", "--ndjson", "--waits=0"],
                            capture_output=True, text=True)
    ib = TMP / "img_spin.bin"
    ib.write_bytes(img_spin)
    a = subprocess.run([SIM, "timed-boot", ROM, str(ib), "--clocks=3000",
                        "--ndjson", "--waits=1"], capture_output=True, text=True)
    ej = TMP / "evt_empty.json"
    ej.write_text(json.dumps({"evt": [], "pins": 0, "tvec": TVEC,
                              "fire": {"at": [], "cs": [], "ip": [],
                                       "which": []}}))
    b = subprocess.run([SIM, "timed-boot", ROM, str(ib), "--clocks=3000",
                        "--ndjson", "--waits=1", f"--evt={ej}"],
                       capture_output=True, text=True)
    chk("timed-boot with an EMPTY evt list == timed-boot with no --evt at all",
        a.stdout == b.stdout and a.returncode == b.returncode == 0,
        f"{len(a.stdout.splitlines())} rows")
    fn = run_functional(img_spin, {"tvec": TVEC, "evt": [],
                                   "fire": {"at": [], "cs": [], "ip": [],
                                            "which": []}})
    chk("functional: no firing, no interception, no termination",
        fn["fired"] == 0 and fn["vecused"] == 0 and fn["done"] == 0)
    (void := p_none)  # noqa: F841

    # ---------------------------------------------------------------- L7 ----
    hdr("L7  A DIRECTIVE-LESS RUN THAT HALTS -- the empty-schedule case, with "
        "its NON-VACUITY CONTROL")
    # EVERY v2 image ends in HLT (the termination handler's last instruction),
    # and a seed with no event axis passes no --evt at all, so `sch` is EMPTY
    # on the commonest invocation there is.  `BootEvt::of` answers it with the
    # INERT DEFAULT schedule -- one rule, in one place, so no call site carries
    # a special case; `assert_clk()` answers -1, which is what the old scalar
    # code returned for `ev_trigger_ == 0`.
    ib2 = TMP / "hlt_only.bin"
    ib2.write_bytes(build_image(bytes([0xF4]))[0])       # the body HALTS
    r_new = subprocess.run([SIM, "timed-boot", ROM, str(ib2), "--clocks=2000",
                            "--ndjson"], capture_output=True, text=True)
    chk("no --evt on a program that HALTS: rc 0, rows emitted",
        r_new.returncode == 0 and len(r_new.stdout.splitlines()) == 2001,
        f"rc={r_new.returncode} rows={len(r_new.stdout.splitlines())}")
    pg = build_preguard()
    if pg:
        r_pg = subprocess.run([pg, "timed-boot", ROM, str(ib2),
                               "--clocks=2000", "--ndjson"],
                              capture_output=True, text=True)
        chk("NON-VACUITY: the same binary without the guard SIGSEGVs (139)",
            r_pg.returncode == -11 or r_pg.returncode == 139,
            f"rc={r_pg.returncode}")
    else:
        chk("NON-VACUITY control could be built", False,
            "-- the guard patch no longer applies")
    # ...and the v2 terminator's own HALT, reached through the overlay
    rows8, _, _ = run_timed(img_spin, doc)
    chk("the L1 terminating run reaches HLT and keeps emitting rows",
        any(r["bs_early"] == 3 for r in rows8),
        f"{sum(1 for r in rows8 if r['bs_early'] == 3)} HALT-status rows")

    print()
    print(f"T7 PROOF: {sum(RES)}/{len(RES)} checks",
          "PASS" if all(RES) else "*** FAIL ***")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
