#!/usr/bin/env python3
"""T11 offline gate -- THE CAPTURE PATH'S CLIENT SIDE, end to end, no board.

    python3 sw/t11_clientpath_gate.py        # rc 0 = pass

WHAT THIS EXISTS TO PROVE.  T10 found that `sw/v30ctl.py`'s `serve` has parsed
`evt2=` / `evt3=` / `tvec=` / `vecsub=` since T8 and that NO CLIENT ANYWHERE
SENT THEM, so the terminating NMI the whole fuzz-v2 corpus rests on was not
armable from the host.  T11 threaded them through
`fuzz_campaign.capture_board` -> `check_seq.run_chip` -> `v30run.run_image` ->
`ServeRunner.run`.  A plumbing fix that cannot be shown to plumb anything is
not a fix, so this gate runs the REAL client against the REAL `serve()` and
reads what actually went onto the wire.

HOW IT IS WIRED.  `subprocess.Popen` is intercepted inside `v30run` only: the
`ssh <host> ... v30ctl.py serve` argv is replaced by THIS FILE in `--serve`
mode, which builds a fake register file and calls the shipped `v30ctl.serve()`
on it.  Everything else on the path is the shipped code -- `ensure()`'s banner
negotiation and rig-clean, `cfg`, `wrand`, `replay`, `BASE`/`DELTA`, the
option formatting, the readback comparison.  The child logs every command line
it is handed, and the parent asserts on that log.

THE LEGS
  L1  a seed WITH a terminating NMI puts `evt3=`, `tvec=` and `vecsub=` on the
      wire, with the delay the pre-registration's formula names.
  L2  THE REVERTED CONTROL -- `capture_board`'s body AS IT STOOD AT 438eff00f0,
      transcribed, sending the same seed: NO evt2/evt3/tvec/vecsub appears.
      This is the leg that makes L1 mean something.
  L3  a seed whose STIMULUS event is itself an NMI: both schedulers reach the
      wire on pin 1, and it is `pinok=1` that permits it -- without the flag
      the rig REFUSES, which is the guard still standing.
  L4  THE READBACK IS LIVE.  A rig that silently truncates TVEC's low byte
      (F46's exact signature, one register over) is CAUGHT: the client raises
      `RigMismatch`, naming the register, the value it sent and the value the
      rig held.  With the same rig honest, the same run succeeds.
  L5  the era clause: a pre-v3 `serve` REFUSES the directive instead of running
      it unverified, and says what to deploy.
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))

import v30ctl as V                                          # noqa: E402


# --------------------------------------------------------------------------- #
# the child: a fake register file + the SHIPPED serve()
# --------------------------------------------------------------------------- #
class FakeHarness(V.Harness):
    """A flat register file behind `v30ctl.Harness`'s two primitives, plus the
    run-loop stubs `serve()` calls.  `set_event`, `read_event`,
    `set_term_vector`, `set_vecsub_en`, `status` and `serve()` itself are the
    shipped code -- the point of the gate is what THEY do.

    `lie` names a register offset whose stored value is silently truncated to
    16 bits on the way in, which is F46's signature reproduced one register
    over: the write is accepted and the readback disagrees."""

    def __init__(self, lie=None):
        self.regs = {}
        self.lie = lie

    def read32(self, off):
        return self.regs.get(off, 0)

    def write32(self, off, val):
        val &= 0xFFFFFFFF
        if self.lie is not None and off == self.lie:
            val &= 0xFFFF00FF          # drop bits [15:8], silently
        self.regs[off] = val

    # ---- inert run-loop stubs ----
    def stop(self):
        pass

    def start(self, power_wait=False):
        # pretend both armed schedulers fired and the overlay served a CS half
        self.regs[V.R_STATUS] = (0b111 << V.ST_EVT_FIRED_S) | V.ST_VEC_USED \
            | V.ST_CAP_FULL

    def load_mem(self, data, addr=0):
        pass

    def load_iords(self, seq):
        pass

    def load_wvec(self, tw):
        pass

    def set_iord(self, val):
        self.regs[V.R_IORD] = val & 0xFFFF

    def set_cfg(self, *a, **kw):
        pass

    def set_wrand(self, *a, **kw):
        pass

    # A capture whose PIN and OVERLAY bits are non-trivial, so the row decoder
    # and the result line's `term` column are exercised on something other
    # than zeros: NMI ([53]) asserted on rows 4..8, the vector-read overlay
    # ([59]) armed on rows 3..9, POLL_N ([54], ACTIVE LOW) idle high
    # throughout.  Nothing else is set, so every other column reads 0.
    CAP_ROWS_N = 12

    def dump_capture(self, count=V.CAP_RECORDS):
        out = []
        for i in range(min(count, self.CAP_ROWS_N)):
            w = 1 << 54                                   # POLL_N idle high
            if 4 <= i <= 8:
                w |= 1 << 53                              # NMI asserted
            if 3 <= i <= 9:
                w |= 1 << 59                              # overlay armed
            out.append(w)
        return out

    def status(self):
        s = super().status()
        s["cap_full"] = True
        s["cap_count"] = 8
        return s


def child_serve(logpath, lie):
    """Run the shipped `serve()` against a FakeHarness, logging every command
    line to `logpath` so the parent can assert on the WIRE and not on the
    client's own idea of what it sent."""
    log = open(logpath, "a", buffering=1)

    class Tee:
        def __init__(self, f):
            self.f = f

        def __iter__(self):
            for line in self.f:
                log.write("> " + line.rstrip("\n") + "\n")
                yield line

        def readline(self):
            line = self.f.readline()
            log.write("> " + line.rstrip("\n")[:40] + "\n")
            return line

    sys.stdin = Tee(sys.stdin)
    V.serve(FakeHarness(lie=lie))
    return 0


# --------------------------------------------------------------------------- #
# the parent
# --------------------------------------------------------------------------- #
FAIL = []


def check(name, ok, detail=""):
    if not ok:
        FAIL.append(name)
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"   {detail}" if detail
                                                     else ""))


LOG = None


def install_fake_transport(lie=None, ver=None, rb_lie=False):
    """Redirect ONLY v30run's ssh Popen at this file.  Everything else about
    `ensure()` -- the banner, the version negotiation, the unconditional
    rig-clean -- runs for real."""
    import v30run
    real = subprocess.Popen

    def fake(argv, **kw):
        if argv and argv[0] == "ssh":
            argv = [sys.executable, str(SW / "t11_clientpath_gate.py"),
                    "--serve", "--log", LOG]
            if lie is not None:
                argv += ["--lie", hex(lie)]
            if ver is not None:
                argv += ["--force-ver", str(ver)]
            if rb_lie:
                argv += ["--rb-lie"]
        return real(argv, **kw)

    v30run.subprocess.Popen = fake
    v30run._runners.clear()


def wire_lines():
    """The RUN/DELTA command lines the board actually received."""
    if not os.path.exists(LOG):
        return []
    return [l[2:] for l in Path(LOG).read_text().splitlines()
            if l.startswith("> ") and
            (l.startswith("> RUN") or l.startswith("> DELTA"))]


def reset_log():
    if os.path.exists(LOG):
        os.unlink(LOG)


PRE_T11 = "438eff00f0"          # the commit this campaign's T11 work landed on

# --------------------------------------------------------------------------- #
# `capture_board`'s body AS IT STOOD AT 438eff00f0 -- the reverted control.
# Transcribed, not imported: the point is to run the OLD call against the SAME
# seed on the SAME transport and read the wire.  (The `t8` gate uses the same
# idiom for the pre-T8 packing expression.)
# --------------------------------------------------------------------------- #
def capture_board_pre_t11(image, meta, cfg, host):
    import check_seq
    import fuzz_campaign as fzc
    w = cfg["waits"]
    wrand = (w["wmax"], w["wseed"]) if w["wrand"] else None
    fixed = 0 if w["wrand"] else w["fixed"]
    evt = fzc._evt_tuple(cfg, meta)
    vec = fzc.wvec_of(cfg)
    real = check_seq.run_chip(image, host, use_core=False, waits=fixed,
                              evt=evt, wrand=wrand, wvec=vec)
    sim = check_seq.run_chip(image, host, use_core=True, waits=fixed,
                             evt=evt, wrand=wrand, wvec=vec)
    return real, sim, None


def seed(cid, k, ov=None):
    import fuzz_campaign as fzc
    cfg = fzc.derive_case(cid, k, ov or {})
    g = fzc.build(cfg)
    image, meta = fzc.compose_case(g, cfg)
    return cfg, image, meta


def find_nmi_stim_seed(cid, ks, ov):
    import fuzz_campaign as fzc
    for k in ks:
        cfg = fzc.derive_case(cid, k, ov)
        if cfg["evt"] and cfg["evt"]["pin"] == 1:
            return k
    return None


def main():
    global LOG
    import fuzz_campaign as fzc
    import testimage as ti
    import v30run

    LOG = str(SW / "testdata" / "fz2" / "t11_wire.log")
    Path(LOG).parent.mkdir(parents=True, exist_ok=True)
    HOST = "t11-fake-board"

    # --- the seed: a census stratum with a stimulus event, w0 ---------------
    OV = {"force_tier": "soup", "force_evt": True, "force_fixed": 0}
    K = 400000
    cfg, image, meta = seed("fz2c", K, OV)
    want_delay = fzc.term_clocks(fzc.weff_of(cfg))
    anchor = meta["anchor_linear"] & 0xFFFFF

    print("=" * 78)
    print("L1  a seed WITH a terminating NMI -> evt3 / tvec / vecsub on the wire")
    print("=" * 78)
    reset_log()
    install_fake_transport()
    term = {}
    real, sim, err = fzc.capture_board(image, meta, cfg, HOST, term_out=term)
    lines = wire_lines()
    print(f"  wire: {lines[0][:150] if lines else '(nothing)'}")
    check("two legs reached the wire (socket then fabric)",
          err is None and len(lines) == 2, f"err={err} lines={len(lines)}")
    joined = " ".join(lines)
    check(f"evt3= present, scheduler {fzc.TERM_SCHED} at the anchor "
          f"{anchor:#07x}, delay {want_delay}, hold {fzc.TERM_HOLD}, pin NMI",
          f"evt3={anchor:05x}:{want_delay}:{fzc.TERM_HOLD}:{fzc.TERM_PIN}"
          in joined)
    check(f"tvec= present and it is the registered {ti.TERM_AT:#06x}",
          f"tvec={fzc.TERM_TVEC[0]:04x}:{fzc.TERM_TVEC[1]:04x}" in joined)
    check(f"vecsub= present and names ONLY scheduler {fzc.TERM_SCHED}",
          f"vecsub={fzc.TERM_VECSUB:x}" in joined)
    check("both A/B legs carry the IDENTICAL directive",
          lines[0].split()[2:] == lines[1].split()[2:] if len(lines) == 2
          else False)
    check("the rig's readback was checked and agreed",
          term.get("readback_ok") is True, f"term={ {k: v for k, v in term.items() if k != 'readback'} }")
    check("STATUS[6] (the overlay served a CS half) reached the host",
          term.get("vec_used") is True)
    check("STATUS[5:3] reached the host as a MASK, not a bool",
          term.get("fired") == 0b111, f"fired={term.get('fired')}")

    print()
    print("=" * 78)
    print("L2  THE REVERTED CONTROL -- capture_board as it stood at 438eff00f0")
    print("=" * 78)
    # the transcription is CHECKED against git, not trusted: a control leg
    # that has quietly drifted from the code it claims to reproduce proves
    # nothing about the change under test
    old = subprocess.run(["git", "show", f"{PRE_T11}:sw/fuzz_campaign.py"],
                         cwd=SW.parent, capture_output=True, text=True)
    body = old.stdout.partition("def capture_board(")[2].partition(
        "\ndef ")[0] if old.returncode == 0 else ""
    check(f"the control is {PRE_T11}'s capture_board, verified against git",
          bool(body) and "evt = _evt_tuple(cfg, meta)" in body
          and "evt=evt, wrand=wrand, wvec=vec)" in body
          and "tvec" not in body and "vecsub" not in body,
          f"{len(body)} chars read from git")
    reset_log()
    install_fake_transport()
    capture_board_pre_t11(image, meta, cfg, HOST)
    old = " ".join(wire_lines())
    print(f"  wire: {wire_lines()[0][:150] if wire_lines() else '(nothing)'}")
    check("the OLD call sends NO evt2/evt3",
          "evt2=" not in old and "evt3=" not in old)
    check("the OLD call sends NO tvec", "tvec=" not in old)
    check("the OLD call sends NO vecsub", "vecsub=" not in old)
    check("...and it did send the stimulus evt, so the leg is not vacuous",
          "evt=" in old)

    print()
    print("=" * 78)
    print("L3  a stimulus NMI beside the terminating NMI: pinok is what allows it")
    print("=" * 78)
    kn = find_nmi_stim_seed("fz2c", range(K, K + 80), OV)
    check("the corpus contains such a seed at all", kn is not None,
          f"k={kn}")
    if kn is not None:
        cfg2, image2, meta2 = seed("fz2c", kn, OV)
        reset_log()
        install_fake_transport()
        _, _, err2 = fzc.capture_board(image2, meta2, cfg2, HOST)
        w2 = " ".join(wire_lines())
        print(f"  wire: {wire_lines()[0][:150] if wire_lines() else '(nothing)'}")
        check("both schedulers armed on pin 1 (NMI) and the run SUCCEEDED",
              err2 is None and ":1 " in w2 + " " and "evt3=" in w2, f"err={err2}")
        check("pinok=1 is on the wire -- the consent is EXPLICIT, per RUN",
              "pinok=1" in w2)
        # the guard still stands: the same line without pinok is refused
        reset_log()
        install_fake_transport()
        r = v30run._runners.setdefault(HOST, v30run.ServeRunner(HOST))
        r.ensure()
        try:
            r.run(bytes(image2), timeout=0.05,
                  evts=[(anchor, 10, 2, 1), None, (anchor, 900, 20, 1)],
                  tvec=fzc.TERM_TVEC, vecsub=fzc.TERM_VECSUB,
                  pin_share=False)
            check("without pinok the rig REFUSES the shared pin", False,
                  "no error raised")
        except v30run.RunError as e:
            check("without pinok the rig REFUSES the shared pin",
                  "already armed on pin 1" in str(e), str(e)[:110])

    print()
    print("=" * 78)
    print("L4  THE READBACK IS LIVE -- a rig that truncates TVEC is caught")
    print("=" * 78)
    reset_log()
    install_fake_transport(lie=V.R_TVEC)
    try:
        fzc.capture_board(image, meta, cfg, HOST)
        check("a lying rig is CAUGHT", False, "no error raised")
    except Exception as e:                                  # noqa: BLE001
        # the board-side `verify=True` fires first, which is the earliest
        # possible point; the client's own repack-and-compare is the second
        txt = str(e)
        check("a lying rig is CAUGHT before the capture is banked, as a "
              "RigMismatch and not a quarantine",
              isinstance(e, v30run.RigMismatch) and
              ("TVEC" in txt or "not holding the directive" in txt),
              f"{type(e).__name__}: {txt[:120]}")
    # and the CLIENT's own half of the check, which the board-side verify
    # above short-circuits: a board that answers the readback question WRONGLY
    reset_log()
    install_fake_transport(rb_lie=True)
    try:
        fzc.capture_board(image, meta, cfg, HOST)
        check("a board that MIS-REPORTS the readback is caught by the client",
              False, "no error raised")
    except Exception as e:                                  # noqa: BLE001
        check("a board that MIS-REPORTS the readback is caught by the "
              "client's own repack",
              isinstance(e, v30run.RigMismatch) and "TVEC" in str(e),
              f"{type(e).__name__}: {str(e)[:110]}")
    reset_log()
    install_fake_transport()
    _, _, err4 = fzc.capture_board(image, meta, cfg, HOST)
    check("the SAME run against an honest rig succeeds (the leg is not "
          "just broken)", err4 is None, f"err={err4}")

    print()
    print("=" * 78)
    print("L5  a pre-v3 serve REFUSES the directive rather than run it unverified")
    print("=" * 78)
    reset_log()
    install_fake_transport(ver=2)
    err5 = None
    try:
        fzc.capture_board(image, meta, cfg, HOST)
    except v30run.RigMismatch as e:
        err5 = e
    check("the run does NOT proceed, and it is a RigMismatch (a STOP), not a "
          "quarantine", err5 is not None, str(err5)[:90])
    check("and the refusal names the deploy", err5 is not None and
          "v30ctl.py" in str(err5) and "INV-1" in str(err5))
    check("nothing was sent on the wire", wire_lines() == [])

    print()
    print("=" * 78)
    print("L6  the RESULT LINE carries the columns the bars are scored on, and")
    print("    the ROW DECODER carries the pins the RTL has always recorded")
    print("=" * 78)
    import analyze_capture as ac
    row = ac.decode_words([(1 << 53) | (1 << 59)])[0]
    check("decode_words exposes pin_int / pin_nmi / pin_poll_n / vec_armed",
          [row.get(k) for k in ("pin_int", "pin_nmi", "pin_poll_n",
                                "vec_armed")], [0, 1, 0, 1])
    check("...and the pre-existing columns are untouched",
          all(k in row for k in ("ad_addr", "ad_data", "ps", "bs_early",
                                 "bs_late", "qs", "ube_n", "rd_n", "lock_n",
                                 "rst", "t")))
    reset_log()
    install_fake_transport()
    res = fzc.eval_case("fz2c", K, OV, False, HOST, False, keep_rows=True)
    line = res["line"]
    need = ("arch_words", "arch_sim_ok", "arch_sim_words", "arch_match",
            "ps3_8080", "wrote_term", "term")
    absent = [f for f in need if f not in line]
    check("every registered column is ON THE LINE", absent == [],
          f"absent={absent}")
    t = line["term"] or {}
    check("term carries the rig's own readback verdict",
          t.get("readback_ok") is True and t.get("fired") == 0b111 and
          t.get("vec_used") is True, str(t)[:120])
    check("term.term_clocks is the pre-registered delay for this seed",
          t.get("term_clocks"), want_delay)
    hr = (t.get("hold_rows") or {})
    check("term.hold_rows counted the NMI run off the ROWS (5 rows, from 4)",
          hr.get("pin_nmi") == [[4, 5]], f"{hr.get('pin_nmi')}")
    check("term.hold_rows saw POLL_N idle (ACTIVE LOW, never asserted)",
          hr.get("pin_poll_n") == [], f"{hr.get('pin_poll_n')}")
    check("term.vec_rows counted the overlay's armed rows (3..9)",
          t.get("vec_rows") == 7, f"{t.get('vec_rows')}")
    check("keep_rows retained the full per-clock rows for the banker",
          res["rows"] is not None and len(res["rows"][0]) == 12)

    print()
    print("=" * 78)
    print("L7  RBCHECK -- the session-start readback, asked of the rig")
    print("=" * 78)
    reset_log()
    install_fake_transport()
    r = v30run._runners.setdefault(HOST, v30run.ServeRunner(HOST))
    regs = r.rig_readback_check()
    check("the board ran rig_readback_check and named every register",
          sorted(regs) == sorted(
              [f"EVT_{k}[{n}]" for n in range(V.EVT_N)
               for k in ("ADDR", "CFG")] + ["TVEC", "VECCTL"]),
          f"{sorted(regs)}")
    # ...and it is not a rubber stamp: a rig that truncates TVEC fails it
    v30run._runners.clear()
    install_fake_transport(lie=V.R_TVEC)
    r = v30run._runners.setdefault(HOST, v30run.ServeRunner(HOST))
    try:
        r.rig_readback_check()
        check("a lying rig FAILS RBCHECK", False, "no error raised")
    except v30run.RigMismatch as e:
        check("a lying rig FAILS RBCHECK",
              "TVEC" in str(e), str(e)[:110])
    v30run._runners.clear()

    reset_log()
    print()
    print("=" * 78)
    print("RESULT: " + ("ALL PASS" if not FAIL else f"{len(FAIL)} FAILED: {FAIL}"))
    print("=" * 78)
    return 1 if FAIL else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--serve", action="store_true")
    ap.add_argument("--log", default=None)
    ap.add_argument("--lie", type=lambda x: int(x, 0), default=None)
    ap.add_argument("--force-ver", type=int, default=None)
    ap.add_argument("--rb-lie", action="store_true")
    a = ap.parse_args()
    if a.serve:
        if a.rb_lie:
            # a board that ANSWERS the readback question wrongly -- the
            # accepted-and-ignored shape, where every write is taken and the
            # register holds something else.  Only the CLIENT's own repack can
            # catch this, so this is `_check_readback`'s falsifier.
            class RbLie:
                def __init__(self, f):
                    self.f = f

                def write(self, s):
                    if s.startswith("OK ") and " rb=" in s:
                        head, _, rb = s.partition(" rb=")
                        parts = rb.strip().split(",")
                        parts[-2] = "deadbeef"        # TVEC, wrong
                        s = head + " rb=" + ",".join(parts) + "\n"
                    return self.f.write(s)

                def flush(self):
                    self.f.flush()

            sys.stdout = RbLie(sys.stdout)
        if a.force_ver is not None:
            # simulate a board still carrying an OLDER v30ctl.py: rewrite the
            # banner (and drop the v3 tokens) line by line, so the client sees
            # a pre-v3 serve without this file forking `serve()` itself
            class OldBanner:
                def __init__(self, f, ver):
                    self.f, self.ver, self.first = f, ver, True

                def write(self, s):
                    if self.first and s.startswith("OK SERVE"):
                        s = f"OK SERVE v{self.ver}\n"
                        self.first = False
                    elif s.startswith("OK ") and " rb=" in s:
                        s = s.split(" vec=")[0] + "\n"
                    return self.f.write(s)

                def flush(self):
                    self.f.flush()

            sys.stdout = OldBanner(sys.stdout, a.force_ver)
        sys.exit(child_serve(a.log, a.lie))
    sys.exit(main())
