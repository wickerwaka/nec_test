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
import base64
import collections
import os
import queue
import re
import struct
import subprocess
import sys
import tempfile
import threading
import time
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import testimage                                    # noqa: E402
import v30ctl                                       # noqa: E402
from analyze_capture import decode_large, decode_words  # noqa: E402

REMOTE_DIR = "/media/fat/v30"

# THE CLOCK DIVIDER OF RECORD (ucsim_t_provenance.md 21.1).
#
# `cfg(div=None)` sends '-' meaning "leave the board default", and the divider
# lives ON THE BOARD: it survives process exit AND session exit.  Every capture
# taken without setting it therefore inherits whatever the previous session
# left, and the whole banked corpus's frequency was never RECORDED anywhere.
# MEASURED cost: at div=4 (8 MHz) the address-phase sampling edge lands before
# the status pulse and the DISPLAY CLOCK disappears from `bs_early`, a COMPARED
# column -- two S10 readings were produced by it and retracted.
#
# 8 = 4 MHz = the frequency the banked corpus is (recoverably) at.  Capture
# drivers SET it; they do not inherit it.
DIV_OF_RECORD = 8


class RunError(Exception):
    pass


class RigMismatch(RunError):
    """THE RIG CANNOT BE SHOWN TO HOLD THE DIRECTIVE IT WAS HANDED.

    One class, two ways in, because the disposition is the same either way:
      * the readback disagreed with what was sent (INV-1's signature), or
      * the board's `serve` is too old to be asked at all.
    Both mean the next capture would be scored against a directive nothing
    ever confirmed, which is precisely what happened to INV-1's 760 seeds.

    A SUBCLASS of RunError so every existing `except RunError` still catches
    it -- but `run_image` re-raises it instead of reconnecting, because a
    reconnect+retry is for a TRANSPORT fault and this is a rig-integrity
    FINDING.  Retrying it produces a second identical failure reported under
    the generic transport message, which is how a finding turns into a
    footnote."""


class ServeRunner:
    """Persistent `v30ctl.py serve` session over one ssh connection.
    Eliminates the per-case ssh handshakes, remote python start-ups, and
    scp round trips of the legacy path (mission 13). Every RUN still does
    the full stop/load/start/host-reset cycle on the harness."""

    def __init__(self, host):
        self.host = host
        self.proc = None
        self.q = None
        self.last_waits = None  # (waits, use_core) tuple key
        self.last_wrand = None  # WRAND state key (None = never enabled)
        self.last_replay = False  # replay mode currently armed
        self.ver = 1             # serve protocol version, from the banner
        self.v2 = False          # serve protocol >= v2 (BASE/DELTA/cap)
        self.v3 = False          # serve protocol >= v3 (verified readback)
        self.last_term = None    # last run's fired/vec_used/readback record
        self.base = None         # image cached device-side via BASE
        # --- S1 transport diagnostics (RR2 serve-drop investigation) ---
        # Blind-spot fixes: the two L6 drops surfaced only as "connection
        # closed" because remote stderr was DEVNULL and no in-flight context
        # was retained. We now (a) capture remote stderr, (b) keep a rolling
        # transcript of the last serve lines, so a drop reports a REASON.
        self.stderr_buf = collections.deque(maxlen=60)   # last remote stderr lines
        self.transcript = collections.deque(maxlen=40)   # last sent/recv serve lines
        self.stderr_thread = None

    def _reader(self, proc, q):
        for line in proc.stdout:
            q.put(line)
        q.put(None)

    def _stderr_reader(self, proc):
        # Drain remote stderr (was DEVNULL) so a drop carries a reason.
        try:
            for line in proc.stderr:
                self.stderr_buf.append(line.rstrip("\n"))
        except (ValueError, OSError):
            pass

    def _diag(self):
        """Diagnostic tail for a drop/timeout: remote stderr + serve
        transcript. Turns the opaque 'connection closed' into a cause."""
        parts = []
        if self.stderr_buf:
            parts.append("remote-stderr[-8]: "
                         + " | ".join(list(self.stderr_buf)[-8:]))
        if self.transcript:
            parts.append("transcript[-6]: "
                         + " ; ".join(list(self.transcript)[-6:]))
        rc = None if self.proc is None else self.proc.poll()
        parts.append(f"remote-exit={rc}")
        return " || ".join(parts) if parts else "no diagnostics captured"

    def _readline(self, timeout):
        try:
            line = self.q.get(timeout=timeout)
        except queue.Empty:
            diag = self._diag()
            self.close()
            raise RunError(f"serve: response timeout [{diag}]") from None
        if line is None:
            diag = self._diag()
            self.close()
            raise RunError(f"serve: connection closed [{diag}]")
        self.transcript.append("< " + line.strip())
        return line.strip()

    def _send(self, s):
        head = s.split("\n", 1)[0]
        self.transcript.append("> " + (head[:80] + "…" if len(head) > 80 else head))
        try:
            self.proc.stdin.write(s + "\n")
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError) as e:
            diag = self._diag()
            self.close()
            raise RunError(f"serve: send failed: {e} [{diag}]") from None

    def ensure(self):
        if self.proc and self.proc.poll() is None:
            return
        self.close()
        self.stderr_buf.clear()
        self.transcript.clear()
        # S1: ssh keepalive so a transient link stall fails fast+diagnosably
        # instead of hanging, and idle-timeout drops are distinguishable from
        # remote crashes; remote stderr is captured (was DEVNULL). The remote
        # serve process is unchanged.
        self.proc = subprocess.Popen(
            ["ssh",
             "-o", "ServerAliveInterval=15",
             "-o", "ServerAliveCountMax=4",
             "-o", "TCPKeepAlive=yes",
             self.host,
             f"cd {REMOTE_DIR} && exec python3 v30ctl.py serve"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, bufsize=1)
        self.q = queue.Queue()
        threading.Thread(target=self._reader, args=(self.proc, self.q),
                         daemon=True).start()
        self.stderr_thread = threading.Thread(
            target=self._stderr_reader, args=(self.proc,), daemon=True)
        self.stderr_thread.start()
        banner = self._readline(20)
        if not banner.startswith("OK SERVE"):
            self.close()
            raise RunError(f"serve: bad banner {banner[:80]!r}")
        # NEGOTIATE ON THE VERSION NUMBER, not on a substring.  `"v2" in
        # banner` reads False against `OK SERVE v3` and would have silently
        # dropped a v3 board back onto the v1 RUN path.
        m = re.match(r"OK SERVE v(\d+)", banner)
        self.ver = int(m.group(1)) if m else 1
        self.v2 = self.ver >= 2
        self.v3 = self.ver >= 3
        self.base = None         # device-side cache gone on reconnect
        self.last_waits = None  # (waits, use_core) tuple key
        self.last_wrand = None  # WRAND state key (None = never enabled)
        self.last_replay = False  # replay mode currently armed
        # MECHANIZED WAIT-RIG GUARD (task #24, sticky-WRAND 2nd occurrence).
        # Force the wait rig to a KNOWN-CLEAN state at every connect: random
        # OFF, replay OFF, UNCONDITIONALLY. last_wrand/last_replay track only
        # THIS runner, so a fresh process would otherwise inherit whatever
        # R_WRAND a PRIOR session left enabled and never clear it (the 16:10
        # f0lock tranche was captured this way, minting phantom Tw). A wait
        # spec explicitly requested for a run re-enables it afterwards.
        self.rig_clean = False
        self._force_clean_rig()
        # DIVIDER PROVENANCE (21.1): what THIS connection has commanded.  None
        # means "never set" -- the board's own sticky value, whose frequency is
        # unknown to this process.  `div_readback` is what a capture manifest
        # records so an un-pinned capture is catchable at read time.
        self.div_commanded = None

    def cfg(self, waits, use_core=None, div=None):
        key = (waits, use_core, div)
        if self.last_waits == key:
            return
        uc = "-" if use_core is None else str(int(bool(use_core)))
        dv = "-" if div is None else str(int(div))
        # CFG <div> <waits> <vector> <small> [use_core]; keep vector, force
        # large mode (small=0). div '-' leaves the board default (E2 freq
        # sweep sets it explicitly); use_core '-' leaves the board default.
        self._send(f"CFG {dv} {waits} - 0 {uc}")
        line = self._readline(10)
        if line != "OK CFG":
            self.close()
            raise RunError(f"serve: cfg failed: {line[:120]}")
        self.last_waits = key
        if div is not None:
            self.div_commanded = int(div)   # 21.1 provenance

    @property
    def div_readback(self):
        """The divider provenance string for a capture manifest (21.1).
        UNPINNED is not an error here -- it is the fact that must be RECORDED,
        because a suite whose manifest says UNPINNED has no known frequency."""
        if self.div_commanded is None:
            return ("div=UNPINNED (inherited sticky board state; frequency "
                    "UNKNOWN to this process -- ucsim_t_provenance 21.1)")
        return (f"div={self.div_commanded} ({32 // self.div_commanded} MHz), "
                f"commanded by this connection")

    def _force_clean_rig(self):
        """Force the wait rig clean at connect (random OFF, replay OFF),
        UNCONDITIONALLY - defeats the sticky-None skip in wrand()/replay() so a
        fresh connection cannot inherit a prior session's stale R_WRAND. The
        wait-rig readback is recorded for provenance (rig_readback)."""
        self._send("WRAND 0 - -")
        line = self._readline(10)
        if line != "OK WRAND":
            self.close()
            raise RunError(f"serve: rig-clear(random) failed: {line[:120]}")
        self.last_wrand = ('off',)
        self._send("WRAND - - - 0")
        line = self._readline(10)
        if line != "OK WRAND":
            self.close()
            raise RunError(f"serve: rig-clear(replay) failed: {line[:120]}")
        self.last_replay = False
        self.rig_clean = True
        # provenance: both rig-clear commands returned OK -> rig commanded clean
        self.rig_readback = "WRAND=0 replay=0 (commanded clean at connect, OK/OK)"

    def wrand(self, spec):
        """Seeded random per-access waits. spec = None (uniform, board
        default) or (wmax, seed) to enable random 0..wmax with that seed.
        The SAME seed drives both A/B positions, so a run applies the
        identical wait pattern to chip and fabric core. To stay compatible
        with a serve that predates WRAND, nothing is sent until random is
        first requested (a fresh session that only runs uniform never emits
        the command)."""
        if spec is None and self.last_wrand is None:
            return
        key = ('off',) if spec is None else ('on', spec[0], spec[1])
        if self.last_wrand == key:
            return
        if spec is None:
            self._send("WRAND 0 - -")
        else:
            self._send(f"WRAND 1 {spec[0]} {spec[1]}")
        line = self._readline(10)
        if line != "OK WRAND":
            self.close()
            raise RunError(f"serve: wrand failed: {line[:120]}")
        self.last_wrand = key

    def replay(self, tw_list):
        """Explicit wait-vector replay (Phase 2a). tw_list = None (disable) or
        a list of per-bus-cycle Tw counts. Loads the vector into the harness
        replay RAM and arms replay mode (applied identically to chip and core).
        Requires the replay-capable bitstream + serve."""
        if tw_list is None:
            if self.last_replay:
                self._send("WRAND - - - 0")
                line = self._readline(10)
                if line != "OK WRAND":
                    self.close()
                    raise RunError(f"serve: replay-off failed: {line[:120]}")
                self.last_replay = False
            return
        blob = bytes(min(255, max(0, int(x))) for x in tw_list)
        self._send("WVEC")
        self._send(base64.b64encode(blob).decode())
        line = self._readline(20)
        if not line.startswith("OK WVEC"):
            self.close()
            raise RunError(f"serve: WVEC failed: {line[:120]}")
        self._send("WRAND - - - 1")
        line = self._readline(10)
        if line != "OK WRAND":
            self.close()
            raise RunError(f"serve: replay-on failed: {line[:120]}")
        self.last_replay = True

    @staticmethod
    def _delta(base, image, gran=256):
        """Block-granular patch stream (u32 off, u16 len, bytes)* for
        DELTA; empty bytes when the images are identical.

        A differing run is split into <=0xFFFF-byte records so the u16 length
        field never overflows: a whole-image raw fuzz seed (task #29) can make
        the entire 64 KB differ in one contiguous run, which struct.pack('<IH')
        cannot encode. Multiple records are transparent to the serve-side
        applier (each is applied in turn)."""
        def emit(start, end):
            while start < end:
                clen = min(end - start, 0xFFFF)
                out.extend(struct.pack("<IH", start, clen))
                out.extend(image[start:start + clen])
                start += clen

        out = bytearray()
        n = len(image)
        run_start = None
        for i in range(0, n, gran):
            j = min(i + gran, n)
            differ = image[i:j] != base[i:j]
            if differ and run_start is None:
                run_start = i
            elif not differ and run_start is not None:
                emit(run_start, i)
                run_start = None
        if run_start is not None:
            emit(run_start, n)
        return bytes(out) if out else b""

    @staticmethod
    def _evts(evt, evts):
        """The ONE scheduler table this client sends.  `evt` is the historical
        name for scheduler 0; `evts` is the general form.  Both together is a
        contradiction, not a merge, and it raises."""
        if evt is not None and evts is not None:
            raise RunError("run(): pass evt= OR evts=, not both -- evt is "
                           "exactly evts[0] and a merge would silently pick "
                           "one")
        out = [None] * v30ctl.EVT_N
        if evt is not None:
            out[0] = tuple(evt)
        for n, e in enumerate(evts or ()):
            if n >= v30ctl.EVT_N:
                raise RunError(f"run(): evts has {len(evts)} entries; the rig "
                               f"has EVT_N={v30ctl.EVT_N} schedulers")
            out[n] = None if e is None else tuple(e)
        return out

    def rig_readback_check(self):
        """Ask the BOARD to run `v30ctl.Harness.rig_readback_check()` -- write
        two distinct values into every fuzz-v2 register, read each back, raise
        on the first disagreement, restore what it found.

        The per-RUN `verify=True` proves the rig held THIS directive; this
        proves the registers round-trip, which is the stuck-bit / dropped-
        nibble case (F46's signature) a single directive can pass by luck.
        Session-start check, not a per-seed one.  Returns the register names
        the board reported."""
        self.ensure()
        if not self.v3:
            raise RigMismatch(
                f"serve on {self.host} is protocol v{self.ver}; RBCHECK needs "
                f"v3.  Deploy sw/v30ctl.py to {REMOTE_DIR} on the board.")
        self._send("RBCHECK")
        line = self._readline(30)
        if not line.startswith("OK RBCHECK"):
            self.close()
            raise RigMismatch(f"serve: RBCHECK failed: {line[:200]}")
        parts = line.split(maxsplit=3)
        return parts[3].split(",") if len(parts) > 3 else []

    def _check_readback(self, evts, tvec, vecsub, tok, fired_mask):
        """INV-1's missing step, ON THE CAPTURE PATH.  Repack what was SENT
        with `v30ctl`'s own packers and compare against the raw register words
        the rig reported, sampled after programming and before the CPU was
        released.  RAISES on any disagreement: a run whose directive the rig
        did not hold is not a capture, it is a capture of something else.

        Returns the term record the result line banks."""
        rb = tok.get("rb")
        vec_used = (tok.get("vec") == "1")
        if rb is None:
            if self.v3:
                self.close()
                raise RunError("serve v3 reply carried no `rb=` readback")
            return {"fired": fired_mask, "vec_used": None, "readback": None,
                    "readback_ok": None, "serve_ver": self.ver}
        parts = rb.split(",")
        if len(parts) != v30ctl.EVT_N + 2:
            self.close()
            raise RunError(f"serve: malformed readback {rb!r}")
        got = {}
        for n, pair in enumerate(parts[:v30ctl.EVT_N]):
            a, _, c = pair.partition(":")
            got[f"EVT_ADDR[{n}]"] = int(a, 16)
            got[f"EVT_CFG[{n}]"] = int(c, 16)
        got["TVEC"] = int(parts[-2], 16)
        got["VECCTL"] = int(parts[-1], 16)
        want = {}
        for n, e in enumerate(evts):
            if e is None:
                # a scheduler this run did not ask for is DISARMED, and the
                # address register is whatever the previous run left: the arm
                # bit is the whole directive when arm=0, so only it is checked
                want[f"EVT_CFG[{n}]"] = got[f"EVT_CFG[{n}]"] & ~(1 << 31)
            else:
                a, d, ho, p = e
                want[f"EVT_ADDR[{n}]"] = v30ctl.pack_evt_addr(a)
                want[f"EVT_CFG[{n}]"] = v30ctl.pack_evt_cfg(
                    delay=d, hold=ho, pin=p, arm=True)
        want["TVEC"] = v30ctl.pack_tvec(*(tvec or (0, 0)))
        want["VECCTL"] = vecsub
        bad = {k: (got[k], v) for k, v in want.items() if got[k] != v}
        if bad:
            self.close()
            raise RigMismatch(
                "serve: THE RIG IS NOT HOLDING THE DIRECTIVE IT WAS HANDED "
                "(INV-1): " + "; ".join(
                    f"{k} rig={g:#010x} sent={w:#010x}"
                    for k, (g, w) in sorted(bad.items())))
        return {"fired": fired_mask, "vec_used": vec_used, "readback": got,
                "readback_ok": True, "serve_ver": self.ver}

    def run(self, image, timeout=3.0, evt=None, iord=None, pins=None,
            cap=None, iords=None, want_raw=False, evts=None, tvec=None,
            vecsub=0, pin_share=False, term_out=None):
        """evt = (linear_addr, delay, hold, pin 0=INT 1=NMI 2=POLL);
        iord = 16-bit I/O read data; pins = static PINS bits (b0 INT,
        b1 NMI, b2 POLL_N); cap = capture-record prefix to return
        (v2 serve only). Returns (recs, evt_fired), or
        (recs, evt_fired, words) with want_raw.

        `want_raw` returns the UNDECODED 64-bit capture words.  SM2 / §59.7:
        `s10_board.capture()` has asked for them since ADDENDUM #6 and this
        module never had the parameter, so every s10/s13 probe raised
        `TypeError` at import-time-clean/run-time.  The words were already
        being unpacked here and thrown away; the blackbox retention rule
        (*full per-clock rows + sha256, never digests alone*) wants them.

        THE T11 ADDITIONS -- the rig has had EVT_N schedulers, an NMI
        vector-read overlay and its arming mask since T5/T8, and this client
        could reach exactly one of them:

          evts      list of up to `v30ctl.EVT_N` scheduler directives, index n
                    = scheduler n, each `None` or `(addr, delay, hold, pin)`.
                    `evt` is the historical spelling of `evts[0]` and still
                    means exactly that; passing BOTH raises.
          tvec      (CS, IP) served by the NMI vector-read overlay at linear
                    0x00008 / 0x0000A -- the DATA is substituted, which is why
                    a seed that scribbles the IVT cannot break the terminator.
          vecsub    VECCTL mask, bit n = scheduler n's FIRE arms the overlay.
                    Keyed on WHICH DIRECTIVE FIRED, not on which pin went high.
          pin_share explicit consent for two schedulers on one pin (a stimulus
                    NMI beside a terminating NMI).  The rig REFUSES by default.
          term_out  a dict, updated in place with what the rig reported and
                    what it held: fired / vec_used / readback / readback_ok.

        THE READBACK IS NOT OPTIONAL.  Any directive beyond `evts[0]` requires
        serve v3, which verifies every EVT/TVEC/VECCTL write against the rig
        before releasing the CPU and returns the raw register words; those
        words are compared HERE against a repack of what was sent, using
        `v30ctl`'s own packers.  There is no second packer -- forking one is
        how INV-1 happened.  A pre-v3 board RAISES rather than running
        unverified."""
        evts = self._evts(evt, evts)
        opts = ""
        for n, e in enumerate(evts):
            if e is None:
                continue
            a, d, ho, p = e
            opts += f" {'evt' if n == 0 else f'evt{n + 1}'}={a:05x}:{d}:{ho}:{p}"
        if tvec is not None:
            opts += f" tvec={tvec[0]:04x}:{tvec[1]:04x}"
        if vecsub:
            opts += f" vecsub={vecsub:x}"
        if pin_share:
            opts += " pinok=1"
        needs_v3 = (tvec is not None or vecsub or pin_share
                    or any(e is not None for e in evts[1:]))
        if needs_v3 and not self.v3:
            self.close()
            raise RigMismatch(
                f"serve on {self.host} is protocol v{self.ver}; the "
                f"terminating-NMI directive (evts[1:]/tvec/vecsub) needs v3, "
                f"which VERIFIES every EVT/TVEC/VECCTL write against the rig "
                f"and returns the readback.  Running it unverified is INV-1.  "
                f"Deploy sw/v30ctl.py to {REMOTE_DIR} on the board.")
        if iord is not None:
            opts += f" iord={iord:04x}"
        if iords is not None:
            # per-IOR ordered sequence (INS / REP INS); empty list resets+disables
            opts += " iords=" + ",".join(f"{v & 0xFFFF:04x}" for v in iords)
        if pins is not None:
            opts += f" pins={pins:x}"
        if cap is not None and self.v2:
            opts += f" cap={cap}"
        image = bytes(image)
        use_delta = False
        if self.v2:
            patch = self._delta(self.base, image) \
                if self.base is not None else None
            if patch is None or len(patch) > 8192:
                # (re)establish the baseline, then run an empty delta
                self._send("BASE")
                self._send(base64.b64encode(image).decode())
                br = self._readline(30)
                if not br.startswith("OK BASE"):
                    self.close()
                    raise RunError(f"serve: BASE failed: {br[:120]}")
                self.base = image
                patch = b""
            self._send(f"DELTA {timeout}{opts}")
            self._send(base64.b64encode(patch).decode())
            use_delta = True
        else:
            self._send(f"RUN {timeout}{opts}")
            self._send(base64.b64encode(image).decode())
        hdr = self._readline(timeout + 10)
        if not hdr.startswith("OK "):
            self.close()
            # the board's OWN readback check fired: `set_event` /
            # `set_term_vector` / `set_vecsub_en` verify before the CPU is
            # released, and `RigReadbackError` is v30ctl's name for it.  It is
            # the same finding as a client-side mismatch, one layer earlier.
            if "RigReadbackError" in hdr:
                raise RigMismatch(f"serve: {hdr[:240]}")
            raise RunError(f"serve: run failed: {hdr[:120]}")
        fields = hdr.split()
        # positional fields, then the v3 `k=v` tokens.  A pre-v3 reply simply
        # has no tokens; a v3 reply's crc still sits at index 4.
        pos = [f for f in fields if "=" not in f]
        tok = dict(f.split("=", 1) for f in fields if "=" in f)
        fired_mask = int(pos[3]) if len(pos) > 3 else 0
        fired = bool(fired_mask)
        if use_delta:
            if len(pos) < 5:
                self.close()
                raise RunError("serve: DELTA reply missing crc")
            want = zlib.crc32(image) & 0xFFFFFFFF
            if int(pos[4], 16) != want:
                self.close()
                raise RunError(f"serve: image crc mismatch "
                               f"{pos[4]} != {want:08x}")
        self.last_term = self._check_readback(evts, tvec, vecsub, tok,
                                              fired_mask)
        if term_out is not None:
            term_out.clear()
            term_out.update(self.last_term)
        blob = base64.b64decode(self._readline(10))
        words = struct.unpack(f"<{len(blob) // 8}Q", blob)
        if want_raw:
            return decode_words(words), fired, words
        return decode_words(words), fired

    def close(self):
        if self.proc:
            try:
                self.proc.kill()
            except OSError:
                pass
        self.proc = None
        self.q = None


_runners = {}


def _run_image_legacy(image, host, tag="test", waits=0):
    """Original per-case scp+ssh path (fallback)."""
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


def run_image(image, host, tag="test", waits=0, evt=None, iord=None,
              pins=None, want_fired=False, cap=None, use_core=None,
              wrand=None, wvec=None, iords=None, div=None, want_raw=False,
              evts=None, tvec=None, vecsub=0, pin_share=False,
              term_out=None):
    """Run an image, return capture records (or (recs, evt_fired) with
    want_fired, or (recs, evt_fired, raw_words) with want_raw -- which
    implies want_fired, because that is the shape `s10_board.capture()`
    unpacks). Uses the persistent serve session unless V30_NO_SERVE=1;
    transport errors get one reconnect, then one legacy-path attempt
    before giving up (legacy path supports no evt/iord/pins).

    use_core selects the Campaign 4 A/B position (True = internal v30_core,
    False = socketed chip, None = leave the board default). It requires a
    board bitstream that carries CFG.use_core (bit 25) and the serve v2
    5-field CFG command; the legacy path cannot set it.

    wrand enables seeded random per-access waits: None = uniform (`waits`),
    or (wmax, seed) = random 0..wmax with that seed. The same seed drives
    both A/B positions. Requires the WRAND-capable bitstream + serve; serve
    path only."""
    # the directives with no legacy-path equivalent, named once
    serve_only = (evt is not None or iord is not None or pins is not None
                  or use_core is not None or wrand is not None
                  or wvec is not None or want_raw
                  or evts is not None or tvec is not None or vecsub
                  or pin_share)
    if os.environ.get("V30_NO_SERVE") == "1":
        if serve_only:
            raise RunError("evt/evts/tvec/vecsub/iord/pins/use_core/wrand/"
                           "wvec/want_raw require serve")
        return _run_image_legacy(image, host, tag, waits)
    r = _runners.get(host)
    if r is None:
        r = _runners[host] = ServeRunner(host)
    for attempt in (1, 2):
        try:
            r.ensure()
            r.cfg(waits, use_core, div)
            r.wrand(wrand if wvec is None else None)
            r.replay(wvec)
            got = r.run(image, evt=evt, iord=iord, pins=pins,
                        cap=cap, iords=iords, want_raw=want_raw,
                        evts=evts, tvec=tvec, vecsub=vecsub,
                        pin_share=pin_share, term_out=term_out)
            if want_raw:
                return got                       # (recs, fired, words)
            recs, fired = got
            return (recs, fired) if want_fired else recs
        except RigMismatch:
            # NOT a transport fault: do not reconnect, do not fall back, do
            # not let the generic message replace the finding.
            r.close()
            raise
        except RunError as e:
            r.close()
            if attempt == 2:
                print(f"serve path failed twice ({e}); trying legacy path",
                      file=sys.stderr)
    if serve_only:
        raise RunError("serve path failed and evt/evts/tvec/vecsub/iord/pins/"
                       "use_core/wrand/wvec/want_raw have no legacy fallback")
    return _run_image_legacy(image, host, tag, waits)


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
    """Phase-split the trace and extract final register state.

    THE DUMP IS DONE-RELATIVE AND MAGIC-ANCHORED (fuzz-v2 D6/D7), the same rule
    `fuzz_classify.arch_dump` reads: the LAST `len(store_order)` IOW words at
    the register port strictly BEFORE the first done marker, carrying MAGIC at
    its declared index.

    Done-relative because the board image RE-RUNS the program for as long as
    the capture lasts, so "the first N register words" and "the last MEMW to
    the PSW scratch word" could come from different passes -- MEASURED on the
    220 banked S10 captures (ucsim_t_provenance.md 23.1): a capture ending
    between a later pass's clear and its own PUSH PSW returned PSW 0 (706
    emission rerolls at w1, the whole HLT.INT w1 golden cell 0/49), and one in
    220 returned a plausible but WRONG PSW.  PSW is now a WORD IN THE RUN --
    the terminator pops its own interrupt frame and emits IP/CS/FLAGS as
    ordinary port writes -- so the `MEMW @ 0xFFEC` channel, its re-run hazard
    and the `PC = stub_linear + 6 - PS*16` derivation are all gone with the
    store stub.

    ASYMMETRY WITH `arch_dump` IS DELIBERATE: this is the board path and it
    RAISES where the classifier returns None.  A missing or forged done marker
    on hardware is a capture-integrity event for the caller to quarantine, not
    a seed property to be scored."""
    txns = extract_txns_large(recs)

    order = meta["store_order"]
    done = [t for t in txns if KIND[t["kind"]] == "IOW"
            and (t["addr"] & 0xFFFF) == testimage.OUT_PORT_DONE]
    if not done:
        raise RunError("no done marker in trace (runaway test?) — quarantine")
    if done[0]["data"] != meta["done_sentinel"]:
        raise RunError(f"done marker data {done[0]['data']:04x} != sentinel")
    d0 = done[0]["start"]
    regw = [t for t in txns if KIND[t["kind"]] == "IOW"
            and (t["addr"] & 0xFFFF) == testimage.OUT_PORT_REGS
            and t["start"] < d0]
    if len(regw) < len(order):
        raise RunError(f"only {len(regw)} register words before the done marker")

    magic_at = order.index("MAGIC")
    tail = regw[-len(order):]
    if tail[magic_at]["data"] != meta["magic"]:
        raise RunError(f"dump anchor {tail[magic_at]['data']:04x} != MAGIC "
                       f"{meta['magic']:04x} at index {magic_at}")
    # >1 anchor before the done marker = the terminating NMI landed mid-dump and
    # the handler restarted; the second run's AW is the first run's shuttle, so
    # the record is unrepairable and the caller must discard it.
    n_magic = sum(1 for t in regw if t["data"] == meta["magic"])
    if n_magic > 1:
        raise RunError(f"dump restarted ({n_magic} MAGIC anchors before done) "
                       "— discard")

    regs_out = {name: tail[i]["data"] for i, name in enumerate(order)}

    # test-phase bus activity: anchor .. dump anchor
    anchor_i = next((i for i, t in enumerate(txns)
                     if t["addr"] == meta["anchor_linear"]
                     and KIND[t["kind"]] == "CODE"), None)
    store_i = txns.index(tail[0])
    test_txns = txns[anchor_i:store_i] if anchor_i is not None else []

    return {
        "regs": regs_out,
        "test_txns": [
            {"kind": KIND[t["kind"]], "addr": t["addr"], "data": t["data"],
             "ube_n": t["ube_n"], "cycles": t["end"] - t["start"] + 1}
            for t in test_txns],
    }


# fuzz-v2: with an EMPTY body the anchor byte is itself the 0xCC (INT3) fill,
# and INT3 pushes the address of the next instruction -- so an echo case comes
# back one byte past its anchor.  It was +6 in v1: the pad ahead of the store
# stub's PUSH PSW.  MEASURED on the Verilator TB at T12, all 15 dump words
# round-tripping and MAGIC 0x5EED present; it is not a recalled constant.
TERM_PC_DELTA = 1


def run_test(regs=None, instr=b"", host="root@mister-nec", tag="test",
             ivt=None, waits=0, ram=None, evt=None,
             iord=None, pins=None, use_core=None, div=None):
    """Compose, run on the board, parse.

    `stub_linear=` IS GONE (fuzz-v2 T1/T12).  It used to tell `compose` where
    to park the fall-through store stub; v2 has no stub, the code region is
    0xCC (INT3) and IVT[3] is composed to reach the terminator, so there is
    nothing left for a caller to place or to name.  It is REMOVED rather than
    accepted-and-ignored: a caller that still passes it is asking for a
    mechanism that no longer exists, and it should hear so."""
    image, meta = testimage.compose(regs=regs, instr=instr, ivt=ivt, ram=ram)
    recs, fired = run_image(image, host, tag, waits=waits, evt=evt,
                            iord=iord, pins=pins, want_fired=True,
                            use_core=use_core, div=div)
    res = parse_result(recs, meta)
    res["meta"] = meta
    res["recs"] = recs
    res["evt_fired"] = fired
    return res


#----------------------------------------------------------------------------
def cmd_echo(host):
    """Inject distinctive values into every register, empty test body,
    verify they all echo back."""
    inject = {
        "AW": 0x1111, "BW": 0x2222, "CW": 0x3333, "DW": 0x4444,
        "SP": 0x5555, "BP": 0x6666, "IX": 0x7777, "IY": 0x8888,
        "DS0": 0x9999, "DS1": 0xAAAA, "SS": 0xBBBB,
        "PS": testimage.REG_DEFAULTS["PS"],     # fuzz-v2 code region
        "PC": testimage.REG_DEFAULTS["PC"],
        "PSW": 0x0000,   # normalized: reserved bits forced
    }
    res = run_test(regs=inject, instr=b"", host=host, tag="echo")
    regs = res["regs"]
    exp = res["meta"]["regs_in"]
    fails = 0
    for name in testimage.STORE_ORDER + ["PSW", "PC"]:
        want = exp[name] if name != "PC" else \
            (exp["PC"] + TERM_PC_DELTA) & 0xFFFF
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
        res = run_test(regs={"PSW": pattern,
                             "PS": testimage.REG_DEFAULTS["PS"],
                             "PC": testimage.REG_DEFAULTS["PC"]},
                       instr=b"", host=host, tag="pswprobe")
        injected = res["meta"]["regs_in"]["PSW"]
        got = res["regs"]["PSW"]
        print(f"requested {pattern:04x} injected {injected:04x} "
              f"read back {got:04x} diff {injected ^ got:04x}")
    return 0


def cmd_profile(host):
    """Mission 13: time the legacy path's stages, then the serve path,
    then a 50-case verified echo burst."""
    inject = {"AW": 0x1111, "BW": 0x2222, "CW": 0x3333, "DW": 0x4444,
              "SP": 0x5555, "BP": 0x6666, "IX": 0x7777, "IY": 0x8888,
              "DS0": 0x9999, "DS1": 0xAAAA, "SS": 0xBBBB,
              "PS": testimage.REG_DEFAULTS["PS"],
              "PC": testimage.REG_DEFAULTS["PC"], "PSW": 0x0000}
    image, meta = testimage.compose(regs=inject, instr=b"")

    print("legacy path stages (one case):")
    with tempfile.TemporaryDirectory() as td:
        binp = Path(td) / "prof.bin"
        capp = Path(td) / "prof.hex"
        binp.write_bytes(image)
        t0 = time.time()
        subprocess.run(["scp", "-q", str(binp), f"{host}:{REMOTE_DIR}/"],
                       check=True, timeout=60)
        t_scp = time.time() - t0
        t0 = time.time()
        subprocess.run(["ssh", host, f"cd {REMOTE_DIR} && timeout 10 "
                        "python3 v30ctl.py cfg --small 0 --waits 0 "
                        ">/dev/null"], check=True, timeout=60)
        t_cfg = time.time() - t0
        t0 = time.time()
        subprocess.run(["ssh", host, f"cd {REMOTE_DIR} && timeout 30 "
                        "python3 v30ctl.py run prof.bin --cap prof.hex "
                        "--timeout 3"], capture_output=True, timeout=60)
        t_run = time.time() - t0
        t0 = time.time()
        subprocess.run(["scp", "-q", f"{host}:{REMOTE_DIR}/prof.hex",
                        str(capp)], check=True, timeout=60)
        t_back = time.time() - t0
    total = t_scp + t_cfg + t_run + t_back
    print(f"  scp image     {t_scp * 1000:7.0f} ms")
    print(f"  ssh cfg       {t_cfg * 1000:7.0f} ms")
    print(f"  ssh run       {t_run * 1000:7.0f} ms")
    print(f"  scp capture   {t_back * 1000:7.0f} ms")
    print(f"  TOTAL         {total * 1000:7.0f} ms/case")

    print("\nserve path:")
    r = ServeRunner(host)
    t0 = time.time()
    r.ensure()
    r.cfg(0)
    print(f"  connect+cfg   {(time.time() - t0) * 1000:7.0f} ms (once)")
    t0 = time.time()
    r.run(image)
    print(f"  first run     {(time.time() - t0) * 1000:7.0f} ms")
    r.close()

    print("\n50-case verified echo burst (serve, full compose+parse):")
    n, fails = 50, 0
    t0 = time.time()
    for i in range(n):
        res = run_test(regs=inject, instr=b"", host=host, tag=f"b{i}")
        got = res["regs"]
        exp = res["meta"]["regs_in"]
        ok = all(got.get(k) == exp[k] for k in testimage.STORE_ORDER) and \
            got["PSW"] == exp["PSW"] and \
            got["PC"] == (exp["PC"] + TERM_PC_DELTA) & 0xFFFF
        if not ok:
            fails += 1
    per = (time.time() - t0) / n
    print(f"  {n} cases, {fails} failures, {per * 1000:.0f} ms/case "
          f"({1 / per:.1f} cases/s)")
    return 1 if fails else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["echo", "psw-probe", "profile"])
    ap.add_argument("--host", default="root@mister-nec")
    args = ap.parse_args()
    if args.cmd == "echo":
        sys.exit(cmd_echo(args.host))
    if args.cmd == "psw-probe":
        sys.exit(cmd_psw_probe(args.host))
    if args.cmd == "profile":
        sys.exit(cmd_profile(args.host))


if __name__ == "__main__":
    main()
