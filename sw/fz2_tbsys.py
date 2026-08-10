#!/usr/bin/env python3
"""fz2_tbsys -- the fuzz-v2 rig RTL's FOUR tb_sys LEGS (plan task T6).

WHAT THIS SCORES.  T5 landed three pin-event schedulers, an NMI vector-read
overlay (TVEC/VECCTL) and an effective-pin trace field in `hdl/rtl/nec_bus.sv`
+ `hps_axi_slave.sv` + `system_large.sv`.  `hdl/tb/tb_v30_core.sv` CANNOT
express any of it -- its batch grammar carries ONE `evt` tuple, has no TVEC and
no vecsub bit, and it does not instantiate `nec_bus` or `hps_axi_slave` at all.
So `tb_sys` -- the Verilated `system_large`, image loaded and events armed
THROUGH THE AXI BRIDGE exactly as the ARM does it -- is the only offline
instrument for these features, which is consistent with the standing rule that
where the two TBs disagree fabric sides with `tb_sys` (1,654 of 1,654 cells).

THE FOUR LEGS.  Two are CONTROLS and without them the positive legs prove
nothing:

  (a) three events        INT at A, NMI at B, terminating NMI at C.  All three
                          fire (STATUS[5:3] == 3'b111) and all three assertions
                          are visible in capture bits [54:52] -- which the old
                          static-PINS encoding could not show.
  (b) interception        IVT vector 2 deliberately WRONG (a spin loop), TVEC ->
                          testimage.TERM_AT, terminator's vecsub_en SET.  MEMR
                          T1 at linear 0x00008 then 0x0000A return the TVEC
                          halves, cap_record[59] is high across them, the next
                          CODE T1 is at the termination handler, STATUS[6] sets,
                          and the 15-word dump + 0xF00D come out.
  (c) NEGATIVE CONTROL    the SAME image and the SAME event with vecsub_en
                          CLEAR.  The CPU must reach the WRONG vector and must
                          NOT terminate.  If this leg terminates too, leg (b)
                          proved nothing and this file says so.
  (d) MUST-NOT-FIRE       a stimulus NMI (its own vecsub_en clear) firing BEFORE
                          the terminator: no substitution on ITS entry, and the
                          terminator's entry substituted anyway.  This is the
                          leg that proves a functional NMI and a terminating NMI
                          coexist -- the single most important semantic in the
                          change, and the only formulation under which arming on
                          "which directive fired" beats arming on "which pin
                          went high".

INERTNESS.  `baseline --tag pre` is captured BEFORE tb_sys.sv is touched and
`--tag post` after; `inert` diffs the capture files BYTE FOR BYTE.  Two
reference runs: a no-event run and a LEGACY single-scheduler run driven through
the historical `+evpin/+evaddr/+evdelay/+evhold` plusargs, so the claim covers
the path `x1_retention.py` actually uses.

RECEIPTS.  The tb_sys binaries are receipted artifacts (`sw/artifact.py`) and
the layer NEVER rebuilds behind your back -- a stale one once produced a false
"6 survivors" that stood for a day (ucore_provenance.md §67.6/§67.7).  Every
command here prints the receipt id of the binary it ran; quote it beside the
number.
"""
import argparse
import filecmp
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))

import artifact as art                                    # noqa: E402
import testimage as ti                                    # noqa: E402
import x1_retention as x1                                 # noqa: E402

OUT = Path.home() / ".cache" / "ucsimt-tmp" / "fz2-tbsys"

BUS_STATUS = {0: "INTA", 1: "IOR", 2: "IOW", 3: "HALT",
              4: "CODE", 5: "MEMR", 6: "MEMW", 7: "PASV"}
T_STATES = {0: "TI", 1: "T1", 2: "T2", 3: "T3", 4: "TW", 5: "T4"}

# --------------------------------------------------------------------------- #
# THE STIMULUS.  One image shape for every leg: a NOP sled at the anchor ending
# in `JMP $`.  The spin is deliberate -- it is what makes leg (c) a real
# negative control.  A sled that ran off into the 0xCC fill would hit INT3 and
# terminate through the vector-3 backstop, so EVERY leg would dump and the
# control would control nothing.
# --------------------------------------------------------------------------- #
SLED_N = 0x40
SPIN = b"\xEB\xFE"                       # JMP $
BODY = b"\x90" * SLED_N + SPIN

ANCHOR = ti.ANCHOR0                      # 0x8100, and PS:PC put it there
A_INT = ANCHOR + 0x00                    # scheduler trigger addresses: three
A_NMI = ANCHOR + 0x04                    # distinct CODE T1 linear addresses,
A_TERM = ANCHOR + 0x08                   # all inside the sled

WRONG_AT = 0xB000                        # the DELIBERATELY WRONG vector 2: a
WRONG_BODY = SPIN                        # spin, so a failed interception hangs

IRET_H0 = ti.IHT_AT                      # bare-IRET handler slots (compose puts
IRET_H1 = ti.IHT_AT + ti.IHT_STRIDE      # an IRET in every unfilled slot)

TVEC_TERM = (0x0000 << 16) | ti.TERM_AT  # {CS, IP} -> the termination handler

# host INT vector: tb_sys leaves CFG[23:16] at the harness default 0xFF, so an
# INTA is answered with vector 0xFF and the CPU reads IVT[0xFF] at 0x3FC.
INT_VECTOR = 0xFF

# capture_buf is 4096 deep (system_large instantiates LOG2_DEPTH=12), so this
# is the ceiling, not a taste.  The whole of every leg -- loader, sled, both
# interrupt entries and the 15-word dump -- lands inside ~1,500 records.
NCAP = 4000


def _img(ivt, ram=None):
    img, meta = ti.compose(instr=BODY, ivt=ivt, ram=ram)
    return img, meta


def img_three():
    """(a): INT vector -> bare IRET, NMI vector -> bare IRET.  The terminating
    NMI gets to TERM_AT through the OVERLAY, not through the image."""
    return _img({INT_VECTOR: (0, IRET_H0), 2: (0, IRET_H1)})


def img_wrong_vector():
    """(b)/(c): vector 2 points at a spin loop.  Terminating iff intercepted."""
    return _img({2: (0, WRONG_AT)},
                ram=[(WRONG_AT + i, b) for i, b in enumerate(WRONG_BODY)])


def img_coexist():
    """(d): vector 2 is a REAL working handler.  The stimulus NMI must use it;
    the terminating NMI must not."""
    return _img({2: (0, IRET_H1)})


# --------------------------------------------------------------------------- #
def run_tb(leg, image, cap_path, ncap=NCAP, waits=0, div=8, pins=None,
           evts=None, tvec=None, vecctl=None, timeout=3600,
           wrand=None, wvec=None, quiet=False):
    """One tb_sys run.  `evts` is {scheduler: (addr, delay, hold, pin)}.

    `wrand` is `(wmax, wseed)` and `wvec` a list of per-bus-cycle Tw counts --
    the SAME two arguments `check_seq.run_tb` takes for `tb_v30_core`, and the
    same priority the RTL has (replay > rand > uniform), so a caller that holds
    a `fuzz_campaign` cfg passes them without reshaping.  Naming NEITHER leaves
    WRAND unwritten, which is the inertness property `cmd_inert` checks."""
    binp = x1.BIN[leg]
    cap_path = Path(cap_path).resolve()
    cap_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=OUT) as td:
        img = Path(td) / "img.hex"
        img.write_text("\n".join(f"{b:02x}" for b in bytes(image)) + "\n")
        argv = [str(binp), f"+img={img}", f"+cap={cap_path}", f"+ncap={ncap}",
                f"+waits={waits}", f"+div={div}"]
        if pins is not None:
            argv.append(f"+pins={pins:x}")
        for n, (a, d, h, p) in sorted((evts or {}).items()):
            pre = ("ev", "ev2", "ev3")[n]
            argv += [f"+{pre}addr={a:05x}", f"+{pre}delay={d}",
                     f"+{pre}hold={h}", f"+{pre}pin={p}"]
        if tvec is not None:
            argv.append(f"+tvec={tvec:08x}")
        if vecctl is not None:
            argv.append(f"+vecctl={vecctl:x}")
        # The wait sources, in the RTL's own priority order.  `wvec` wins
        # because `nec_bus` says replay > rand > uniform, and a caller that
        # hands both is asking for the vector.
        if wvec is not None:
            wf = Path(td) / "wvec.hex"
            wf.write_text("\n".join(f"{min(255, max(0, int(x))):02x}"
                                    for x in wvec) + "\n")
            argv.append(f"+wvec={wf}")
        elif wrand is not None:
            wmax, wseed = wrand
            argv += ["+wrand=1", f"+wmax={wmax}", f"+wseed={wseed & 0xFFFF:04x}"]
        t0 = time.time()
        r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    out = r.stdout
    m = None
    for line in out.splitlines():
        if line.startswith("SYS DONE "):
            m = line
    if m is None:
        raise RuntimeError(f"tb_sys produced no SYS DONE line\n"
                           f"stdout tail: {out[-2000:]}\nstderr: {r.stderr[-800:]}")
    # echo the harness's own register readbacks -- the INV-1 lesson is that the
    # directive the rig APPLIED is the only one worth quoting
    readbacks = [l for l in out.splitlines()
                 if l.startswith(("SYS EVT", "SYS REG"))]
    if not quiet:
        for line in readbacks:
            print(f"      | {line}")
    parts = dict(p.split("=", 1) for p in m.split() if "=" in p)
    words = [int(x, 16) for x in cap_path.read_text().split() if x]
    return {"words": words,
            "fired": int(parts.get("fired", "0")),
            "vecused": int(parts.get("vecused", "0")),
            "stdout": out,
            "readbacks": readbacks,
            "secs": time.time() - t0,
            "argv": argv}


def decode(words):
    return [{"idx": i,
             "ad_addr": r & 0xFFFFF,
             "ad_data": (r >> 20) & 0xFFFF,
             "ps": (r >> 36) & 0xF,
             "bs_early": (r >> 40) & 7,
             "qs": (r >> 46) & 3,
             "ube_n": (r >> 49) & 1,
             "rst": (r >> 55) & 1,
             "t": (r >> 56) & 7,
             "int": (r >> 52) & 1,
             "nmi": (r >> 53) & 1,
             "poll_n": (r >> 54) & 1,
             "vec": (r >> 59) & 1,
             "raw": r} for i, r in enumerate(words)]


def txns(recs):
    """Bus transactions off the harness FSM's own T-state annotations."""
    out, cur = [], None
    for r in recs:
        ts = T_STATES.get(r["t"], "?")
        if ts == "T1":
            cur = {"start": r["idx"], "kind": BUS_STATUS[r["bs_early"]],
                   "addr": r["ad_addr"], "vec_t1": r["vec"], "data": None}
        elif ts in ("T3", "TW") and cur is not None:
            cur["data"] = r["ad_data"]
        elif ts == "T4" and cur is not None:
            cur["end"] = r["idx"]
            cur["vec_t4"] = r["vec"]
            out.append(cur)
            cur = None
    return out


def windows(recs, key, val=1):
    """Contiguous [first, last] index runs where `key` == `val`.

    `val=0` for POLL_N, which is ACTIVE LOW: the harness's PINS register drives
    it and a scheduler pulls it down (`NEC_POLL_N = poll_n_in & ~ev_poll`), so
    its assertion is a LOW window and its idle level is whatever PINS says --
    0 by default, which is why a run that does not set +pins can never see a
    POLL_N assertion at all."""
    out, st = [], None
    for r in recs:
        if r[key] == val and st is None:
            st = r["idx"]
        elif r[key] != val and st is not None:
            out.append((st, r["idx"] - 1))
            st = None
    if st is not None:
        out.append((st, recs[-1]["idx"]))
    return out


def dump(tx):
    """The arch dump: IOW words at OUT_PORT_REGS before the first
    OUT_PORT_DONE, and the done word.  Deliberately the raw shape, not
    fuzz_classify's -- that file belongs to T4."""
    regs, done = [], None
    for t in tx:
        if t["kind"] != "IOW":
            continue
        port = t["addr"] & 0xFFFF
        if port == ti.OUT_PORT_DONE and done is None:
            done = t["data"]
            break
        if port == ti.OUT_PORT_REGS:
            regs.append(t["data"])
    return regs, done


def show(recs, lo, hi, note=""):
    print(f"      {'idx':>5} {'T':<2} {'bs':<4} {'addr':>6} {'data':>5} "
          f"INT NMI /POLL VEC   raw")
    for r in recs:
        if lo <= r["idx"] <= hi:
            print(f"      {r['idx']:>5} {T_STATES.get(r['t'],'?'):<2} "
                  f"{BUS_STATUS[r['bs_early']]:<4} {r['ad_addr']:05x} "
                  f"{r['ad_data']:04x}   {r['int']}   {r['nmi']}    "
                  f"{r['poll_n']}   {r['vec']}   {r['raw']:016x}")
    if note:
        print(f"      -- {note}")


# --------------------------------------------------------------------------- #
class Leg:
    def __init__(self, name, title):
        self.name, self.title = name, title
        self.checks = []

    def chk(self, what, cond, detail=""):
        self.checks.append((what, bool(cond), detail))
        print(f"    [{'PASS' if cond else 'FAIL'}] {what}"
              f"{('  ' + detail) if detail else ''}")
        return bool(cond)

    @property
    def ok(self):
        return all(c for _n, c, _d in self.checks)


def _receipt(leg):
    return str(art.receipt_id(x1.BIN[leg]))


def _hdr(leg, l):
    print(f"\n=== LEG ({l.name}) {l.title} ===")
    print(f"    DUT {x1.BIN[leg]}   receipt {_receipt(leg)[:16]}…")


# --------------------------------------------------------------------------- #
def leg_a(binleg, outdir):
    l = Leg("a", "THREE EVENTS -- three schedulers, three assertions on "
                 "bits [54:52]")
    _hdr(binleg, l)
    img, _meta = img_three()
    r = run_tb(binleg, img, outdir / "leg_a.hex",
               evts={0: (A_INT, 0, 40, 0),        # INT
                     1: (A_NMI, 300, 20, 1),      # NMI, stimulus
                     2: (A_TERM, 900, 20, 1)},    # NMI, terminating
               tvec=TVEC_TERM, vecctl=0b100)
    recs = decode(r["words"])
    tx = txns(recs)
    l.chk("STATUS[5:3] == 3'b111 (all three schedulers fired)",
          r["fired"] == 0b111, f"fired={r['fired']:#05b}")
    iw = windows(recs, "int")
    nw = windows(recs, "nmi")
    pw = windows(recs, "poll_n", 1)
    l.chk("INT asserted in the capture (bit [52])", len(iw) >= 1, f"windows={iw}")
    l.chk("NMI asserted TWICE, disjoint (bit [53])", len(nw) == 2,
          f"windows={nw}")
    l.chk("the two NMI windows do not overlap (edge latch gets two edges)",
          len(nw) == 2 and nw[0][1] < nw[1][0],
          f"{nw}")
    l.chk("POLL_N (bit [54]) never moves off the PINS register's own level -- "
          "no cross-talk between scheduler slices",
          all(x["poll_n"] == 0 for x in recs),
          f"poll_n==1 windows={pw[:2]}  n={len(recs)}")
    l.chk("INT window precedes both NMI windows (ordering by delay held)",
          bool(iw) and bool(nw) and iw[0][0] < nw[0][0],
          f"int={iw[0] if iw else None} nmi0={nw[0] if nw else None}")
    inta = [t for t in tx if t["kind"] == "INTA"]
    l.chk("the INT was RECOGNISED (INTA cycles on the bus)", len(inta) >= 2,
          f"{len(inta)} INTA cycles")
    regs, done = dump(tx)
    l.chk("terminated: 15 IOW words + the done marker",
          len(regs) == 15 and done == ti.DONE_SENTINEL,
          f"{len(regs)} words, done={done if done is None else f'{done:#06x}'}")
    l.chk("MAGIC at dump index 1", len(regs) > 1 and regs[1] == ti.MAGIC,
          f"{regs[1]:#06x}" if len(regs) > 1 else "no dump")
    print(f"    the three assertion windows, records: INT {iw}  NMI {nw}")
    if len(nw) == 2:
        show(recs, nw[0][0] - 1, nw[0][0] + 2, "first (stimulus) NMI assertion")
        show(recs, nw[1][0] - 1, nw[1][0] + 2, "second (terminating) NMI assertion")

    # ------------------------------------------------------------------ #
    # (a2) THE SAME THREE SCHEDULERS ON THE THREE DIFFERENT PINS.
    #
    # Run (a1) above puts two of the three directives on NMI, because that is
    # what "a stimulus NMI and a terminating NMI coexist" requires -- so it
    # moves bits [53] and [52] and leaves [54] alone.  To read the claim
    # "all three assertions are visible in [54:52]" LITERALLY, the three
    # schedulers have to drive the three pins, and POLL_N needs +pins=4:
    # `NEC_POLL_N = poll_n_in & ~ev_poll`, and poll_n_in is 0 by default, so
    # with the PINS register at its reset value a POLL_N drive changes NOTHING
    # on the wire and nothing in the capture.  That is a property of the
    # harness, not of the trace field.
    # ------------------------------------------------------------------ #
    print("    (a2) the same three schedulers on the three DIFFERENT pins, "
          "+pins=4 (POLL_N idle high)")
    r2 = run_tb(binleg, img, outdir / "leg_a2.hex", pins=0b100,
                evts={0: (A_INT, 0, 40, 0),        # INT     -> bit [52]
                      1: (A_NMI, 300, 40, 2),      # POLL_N  -> bit [54]
                      2: (A_TERM, 900, 20, 1)},    # NMI     -> bit [53]
                tvec=TVEC_TERM, vecctl=0b100)
    r2recs = decode(r2["words"])
    r2tx = txns(r2recs)
    i2 = windows(r2recs, "int")
    n2 = windows(r2recs, "nmi")
    p2 = windows(r2recs, "poll_n", 0)      # POLL_N is ACTIVE LOW
    l.chk("(a2) STATUS[5:3] == 3'b111", r2["fired"] == 0b111,
          f"fired={r2['fired']:#05b}")
    l.chk("(a2) bit [52] INT asserts", len(i2) >= 1, f"{i2}")
    l.chk("(a2) bit [53] NMI asserts exactly once", len(n2) == 1, f"{n2}")
    l.chk("(a2) bit [54] POLL_N is high at idle (+pins=4) and is pulled LOW "
          "exactly once by scheduler 1",
          len(p2) == 1 and r2recs[0]["poll_n"] == 1, f"low windows={p2}")
    l.chk("(a2) ALL THREE bits of [54:52] carry an assertion in ONE capture",
          len(i2) >= 1 and len(n2) == 1 and len(p2) == 1,
          f"INT {i2}  NMI {n2}  POLL_N(low) {p2}")
    r2regs, r2done = dump(r2tx)
    l.chk("(a2) terminated", len(r2regs) == 15 and r2done == ti.DONE_SENTINEL,
          f"{len(r2regs)} words, done="
          f"{r2done if r2done is None else f'{r2done:#06x}'}")
    for nm, wd in (("INT [52]", i2), ("NMI [53]", n2), ("POLL_N [54] low", p2)):
        if wd:
            show(r2recs, wd[0][0] - 1, wd[0][0] + 1, f"{nm} assertion edge")
    return l


def _interception_rows(l, recs, tx, want_ip, want_cs, want_vec, want_next,
                       tag, skip=0):
    """The shared row-level reading: the two aligned MEMR words of an NMI
    entry, cap_record[59] across them, and the CODE T1 that follows."""
    mr = [t for t in tx if t["kind"] == "MEMR" and (t["addr"] >> 1) == 4]
    cs = [t for t in tx if t["kind"] == "MEMR" and (t["addr"] >> 1) == 5]
    if len(mr) <= skip or len(cs) <= skip:
        l.chk(f"{tag}: MEMR at linear 0x00008 and 0x0000A both present",
              False, f"found {len(mr)} at 0x8, {len(cs)} at 0xA (skip={skip})")
        return None
    ip, csx = mr[skip], cs[skip]
    l.chk(f"{tag}: MEMR T1 at linear 0x00008", ip["addr"] == 0x00008,
          f"addr={ip['addr']:05x} rec {ip['start']}")
    l.chk(f"{tag}: 0x00008 returns {want_ip:#06x}", ip["data"] == want_ip,
          f"data={ip['data']:#06x}")
    l.chk(f"{tag}: MEMR T1 at linear 0x0000A", csx["addr"] == 0x0000A,
          f"addr={csx['addr']:05x} rec {csx['start']}")
    l.chk(f"{tag}: 0x0000A returns {want_cs:#06x}", csx["data"] == want_cs,
          f"data={csx['data']:#06x}")
    # T1..T3 of BOTH reads.  The CS read's T4 is deliberately excluded and
    # checked separately: the RTL disarms at `vec_hit_cs && next_t_state ==
    # ST_T4`, i.e. when the CS half COMPLETES (not on hold expiry, which would
    # race the very read the overlay exists to serve), so [59] is already low
    # on that record and that is the disarm's own evidence.
    span = [x for x in recs if ip["start"] <= x["idx"] < csx["end"]]
    l.chk(f"{tag}: cap_record[59] == {want_vec} across BOTH reads (T1..T3)",
          all(x["vec"] == want_vec for x in span),
          f"records {ip['start']}..{csx['end'] - 1}, "
          f"[59] set on {sum(x['vec'] for x in span)}/{len(span)}")
    if want_vec:
        t4 = [x for x in recs if x["idx"] == csx["end"]]
        l.chk(f"{tag}: [59] drops on the CS read's T4 -- the overlay disarms "
              f"when the CS half completes",
              bool(t4) and t4[0]["vec"] == 0,
              f"record {csx['end']} [59]={t4[0]['vec'] if t4 else '?'}")
    nxt = [t for t in tx if t["kind"] == "CODE" and t["start"] > csx["end"]]
    l.chk(f"{tag}: the next CODE T1 is at {want_next:#07x}",
          bool(nxt) and nxt[0]["addr"] == want_next,
          f"addr={nxt[0]['addr']:05x} rec {nxt[0]['start']}" if nxt else "none")
    print(f"    {tag}: the rows")
    show(recs, ip["start"], (nxt[0]["start"] if nxt else csx["end"]))
    return ip, csx, (nxt[0] if nxt else None)


def leg_b(binleg, outdir):
    l = Leg("b", "INTERCEPTION -- a WRONG vector 2, TVEC -> TERM_AT, "
                 "vecsub_en SET")
    _hdr(binleg, l)
    img, _meta = img_wrong_vector()
    l.chk(f"the image's vector 2 really is the wrong one ({WRONG_AT:#06x})",
          bytes(img[8:12]) == bytes((WRONG_AT & 0xFF, WRONG_AT >> 8, 0, 0)),
          bytes(img[8:12]).hex())
    l.chk(f"and {WRONG_AT:#06x} holds a spin loop, so a MISSED interception "
          f"hangs instead of terminating",
          bytes(img[WRONG_AT:WRONG_AT + 2]) == SPIN,
          bytes(img[WRONG_AT:WRONG_AT + 2]).hex())
    r = run_tb(binleg, img, outdir / "leg_b.hex",
               evts={0: (A_NMI, 200, 20, 1)},
               tvec=TVEC_TERM, vecctl=0b001)
    recs = decode(r["words"])
    tx = txns(recs)
    l.chk("the scheduler fired", r["fired"] & 1, f"fired={r['fired']:#05b}")
    _interception_rows(l, recs, tx, TVEC_TERM & 0xFFFF, TVEC_TERM >> 16, 1,
                       ti.TERM_AT, "intercepted NMI entry")
    l.chk("STATUS[6] (vec_used) set after the run", r["vecused"] == 1,
          f"vecused={r['vecused']}")
    regs, done = dump(tx)
    l.chk("the 15-word dump came out", len(regs) == 15, f"{len(regs)} words")
    l.chk("MAGIC at dump index 1", len(regs) > 1 and regs[1] == ti.MAGIC,
          f"{regs[1]:#06x}" if len(regs) > 1 else "no dump")
    l.chk(f"the done marker {ti.DONE_SENTINEL:#06x} at port "
          f"{ti.OUT_PORT_DONE:#04x}", done == ti.DONE_SENTINEL,
          f"done={done if done is None else f'{done:#06x}'}")
    print(f"    the dump: {[f'{w:04x}' for w in regs]} done="
          f"{done if done is None else f'{done:04x}'}")
    return l, (regs, done, r)


def leg_c(binleg, outdir, b_ref):
    l = Leg("c", "NEGATIVE CONTROL -- the SAME image and event, vecsub_en "
                 "CLEAR: must NOT terminate")
    _hdr(binleg, l)
    img, _meta = img_wrong_vector()
    r = run_tb(binleg, img, outdir / "leg_c.hex",
               evts={0: (A_NMI, 200, 20, 1)},
               tvec=TVEC_TERM, vecctl=0b000)
    recs = decode(r["words"])
    tx = txns(recs)
    l.chk("the scheduler still fired (the control differs by vecsub_en ONLY)",
          r["fired"] & 1, f"fired={r['fired']:#05b}")
    _interception_rows(l, recs, tx, WRONG_AT, 0x0000, 0, WRONG_AT,
                       "un-intercepted NMI entry")
    l.chk("STATUS[6] (vec_used) CLEAR", r["vecused"] == 0,
          f"vecused={r['vecused']}")
    l.chk("cap_record[59] LOW on every record of the run",
          all(x["vec"] == 0 for x in recs),
          f"[59] set on {sum(x['vec'] for x in recs)}/{len(recs)}")
    regs, done = dump(tx)
    l.chk("NO done marker -- the run did NOT terminate", done is None,
          f"done={done if done is None else f'{done:#06x}'}")
    l.chk("NO 15-word dump", len(regs) < 15, f"{len(regs)} IOW words at "
          f"{ti.OUT_PORT_REGS:#04x}")
    l.chk("the CPU is spinning at the WRONG vector at the end of the capture",
          any(t["kind"] == "CODE" and t["addr"] in (WRONG_AT, WRONG_AT + 1)
              for t in tx[-12:]),
          f"last CODE addrs="
          f"{[f'{t['addr']:05x}' for t in tx[-12:] if t['kind'] == 'CODE'][-4:]}")
    bregs, bdone, _br = b_ref
    l.chk("THE CONTROL CONTROLS: leg (b) terminated and leg (c) did not",
          bdone == ti.DONE_SENTINEL and done is None,
          f"b.done={bdone if bdone is None else f'{bdone:#06x}'}  "
          f"c.done={done if done is None else f'{done:#06x}'}  "
          f"b.words={len(bregs)} c.words={len(regs)}")
    return l


def leg_d(binleg, outdir):
    l = Leg("d", "MUST-NOT-FIRE CONTROL -- a stimulus NMI must NOT be "
                 "substituted; the terminating one must")
    _hdr(binleg, l)
    img, _meta = img_coexist()
    l.chk(f"the image's vector 2 is a REAL working handler ({IRET_H1:#06x}, "
          f"a bare IRET)",
          bytes(img[8:12]) == bytes((IRET_H1 & 0xFF, IRET_H1 >> 8, 0, 0))
          and img[IRET_H1] == ti.IRET_BYTE,
          f"{bytes(img[8:12]).hex()} / [{IRET_H1:04x}]={img[IRET_H1]:#04x}")
    r = run_tb(binleg, img, outdir / "leg_d.hex",
               evts={0: (A_NMI, 200, 20, 1),        # stimulus NMI, vecsub CLEAR
                     2: (A_TERM, 900, 20, 1)},      # terminating NMI, vecsub SET
               tvec=TVEC_TERM, vecctl=0b100)
    recs = decode(r["words"])
    tx = txns(recs)
    l.chk("both schedulers fired (STATUS[3] and STATUS[5])",
          r["fired"] == 0b101, f"fired={r['fired']:#05b}")
    nw = windows(recs, "nmi")
    l.chk("two disjoint NMI assertions", len(nw) == 2 and nw[0][1] < nw[1][0],
          f"{nw}")
    _interception_rows(l, recs, tx, IRET_H1, 0x0000, 0, IRET_H1,
                       "STIMULUS NMI entry (vecsub_en CLEAR -- must NOT be "
                       "substituted)", skip=0)
    _interception_rows(l, recs, tx, TVEC_TERM & 0xFFFF, TVEC_TERM >> 16, 1,
                       ti.TERM_AT,
                       "TERMINATING NMI entry (vecsub_en SET -- must be "
                       "substituted)", skip=1)
    l.chk("STATUS[6] (vec_used) set -- the overlay served exactly once",
          r["vecused"] == 1, f"vecused={r['vecused']}")
    vw = windows(recs, "vec")
    l.chk("cap_record[59] rises ONCE, and only after the first (stimulus) "
          "NMI entry", len(vw) == 1 and vw[0][0] > nw[0][1] if nw else False,
          f"vec windows={vw}  nmi windows={nw}")
    regs, done = dump(tx)
    l.chk("terminated: 15 words + done marker",
          len(regs) == 15 and done == ti.DONE_SENTINEL,
          f"{len(regs)} words, done={done if done is None else f'{done:#06x}'}")
    return l


# --------------------------------------------------------------------------- #
# inertness
# --------------------------------------------------------------------------- #
INERT_CASES = {
    # name           evts (legacy plusargs only) / None
    "noevent": None,
    "legacy1": {0: (A_NMI, 200, 20, 1)},
}


def cmd_baseline(a):
    OUT.mkdir(parents=True, exist_ok=True)
    d = OUT / a.tag
    d.mkdir(parents=True, exist_ok=True)
    print(f"  DUT {x1.BIN[a.leg]}   receipt {_receipt(a.leg)[:16]}…")
    print(f"  git {art.git_state()}")
    img, _m = img_coexist()
    for nm, evts in INERT_CASES.items():
        r = run_tb(a.leg, img, d / f"{nm}.hex", evts=evts)
        print(f"  {nm}: {len(r['words'])} records  fired={r['fired']}  "
              f"vecused={r['vecused']}  ({r['secs']:.0f}s)  -> {d/f'{nm}.hex'}")
    (d / "meta.json").write_text(json.dumps(
        {"receipt": _receipt(a.leg), "git": art.git_state(),
         "tree": x1.tree_key(), "leg": a.leg,
         "when": time.strftime("%Y-%m-%dT%H:%M:%S")}, indent=1))
    return 0


def cmd_inert(a):
    pre, post = OUT / "pre", OUT / "post"
    pm = json.loads((pre / "meta.json").read_text())
    qm = json.loads((post / "meta.json").read_text())
    print("=== INERTNESS: tb_sys with all three schedulers disarmed and "
          "VECCTL zero ===")
    print(f"  pre   receipt {pm['receipt'][:16]}…  git {pm['git']}  "
          f"tree {pm['tree'][:16]}…")
    print(f"  post  receipt {qm['receipt'][:16]}…  git {qm['git']}  "
          f"tree {qm['tree'][:16]}…")
    print(f"  the two binaries are DIFFERENT artifacts: "
          f"{pm['receipt'] != qm['receipt']}")
    ok = True
    for nm in INERT_CASES:
        same = filecmp.cmp(pre / f"{nm}.hex", post / f"{nm}.hex", shallow=False)
        n = len((pre / f"{nm}.hex").read_text().split())
        ok = ok and same
        print(f"  [{'PASS' if same else 'FAIL'}] {nm}: {n} records "
              f"{'BYTE-IDENTICAL' if same else 'DIFFER'}")
    print(f"INERTNESS {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def cmd_build(a):
    for leg in (("base", "ret") if a.leg == "all" else (a.leg,)):
        did = x1.build(leg, force=a.force)
        print(f"  {leg}: {'REBUILT' if did else 'up to date'}  {x1.BIN[leg]}  "
              f"receipt {_receipt(leg)}")
    return 0


def cmd_legs(a):
    OUT.mkdir(parents=True, exist_ok=True)
    d = OUT / f"legs-{a.leg}"
    d.mkdir(parents=True, exist_ok=True)
    x1.build(a.leg)
    print(f"tb_sys leg   {a.leg}")
    print(f"binary       {x1.BIN[a.leg]}")
    print(f"receipt      {_receipt(a.leg)}")
    print(f"tree key     {x1.tree_key()}")
    print(f"git          {art.git_state()}")
    la = leg_a(a.leg, d)
    lb, bref = leg_b(a.leg, d)
    lc = leg_c(a.leg, d, bref)
    ld = leg_d(a.leg, d)
    print("\n=== SUMMARY ===")
    bad = 0
    for l in (la, lb, lc, ld):
        n = sum(1 for _w, c, _dd in l.checks if not c)
        bad += n
        print(f"  ({l.name}) {'PASS' if l.ok else 'FAIL'}  "
              f"{len(l.checks) - n}/{len(l.checks)} checks   {l.title}")
    print(f"  receipt {_receipt(a.leg)}")
    print(f"T6 LEGS {'PASS' if bad == 0 else f'FAIL ({bad} checks)'}")
    return 0 if bad == 0 else 1


def main():
    ap = argparse.ArgumentParser()
    s = ap.add_subparsers(dest="cmd", required=True)
    b = s.add_parser("build")
    b.add_argument("--leg", choices=("base", "ret", "all"), default="all")
    b.add_argument("--force", action="store_true")
    b.set_defaults(fn=cmd_build)
    p = s.add_parser("baseline", help="capture the inertness reference")
    p.add_argument("--tag", required=True, choices=("pre", "post"))
    p.add_argument("--leg", choices=("base", "ret"), default="ret")
    p.set_defaults(fn=cmd_baseline)
    i = s.add_parser("inert")
    i.set_defaults(fn=cmd_inert)
    g = s.add_parser("legs")
    g.add_argument("--leg", choices=("base", "ret"), default="ret")
    g.set_defaults(fn=cmd_legs)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
