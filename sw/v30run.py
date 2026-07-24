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
from analyze_capture import decode_large, decode_words  # noqa: E402

REMOTE_DIR = "/media/fat/v30"


class RunError(Exception):
    pass


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
        self.v2 = False          # serve protocol >= v2 (BASE/DELTA/cap)
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
        self.v2 = "v2" in banner
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

    def cfg(self, waits, use_core=None):
        key = (waits, use_core)
        if self.last_waits == key:
            return
        uc = "-" if use_core is None else str(int(bool(use_core)))
        # CFG <div> <waits> <vector> <small> [use_core]; keep div/vector,
        # force large mode (small=0). use_core '-' leaves the board default.
        self._send(f"CFG - {waits} - 0 {uc}")
        line = self._readline(10)
        if line != "OK CFG":
            self.close()
            raise RunError(f"serve: cfg failed: {line[:120]}")
        self.last_waits = key

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
        DELTA; empty bytes when the images are identical."""
        out = bytearray()
        n = len(image)
        run_start = None
        for i in range(0, n, gran):
            j = min(i + gran, n)
            differ = image[i:j] != base[i:j]
            if differ and run_start is None:
                run_start = i
            elif not differ and run_start is not None:
                out += struct.pack("<IH", run_start, i - run_start)
                out += image[run_start:i]
                run_start = None
        if run_start is not None:
            out += struct.pack("<IH", run_start, n - run_start)
            out += image[run_start:n]
        return bytes(out) if out else b""

    def run(self, image, timeout=3.0, evt=None, iord=None, pins=None,
            cap=None, iords=None):
        """evt = (linear_addr, delay, hold, pin 0=INT 1=NMI 2=POLL);
        iord = 16-bit I/O read data; pins = static PINS bits (b0 INT,
        b1 NMI, b2 POLL_N); cap = capture-record prefix to return
        (v2 serve only). Returns (recs, evt_fired)."""
        opts = ""
        if evt is not None:
            a, d, ho, p = evt
            opts += f" evt={a:05x}:{d}:{ho}:{p}"
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
            raise RunError(f"serve: run failed: {hdr[:120]}")
        fields = hdr.split()
        fired = bool(int(fields[3])) if len(fields) > 3 else False
        if use_delta:
            if len(fields) < 5:
                self.close()
                raise RunError("serve: DELTA reply missing crc")
            want = zlib.crc32(image) & 0xFFFFFFFF
            if int(fields[4], 16) != want:
                self.close()
                raise RunError(f"serve: image crc mismatch "
                               f"{fields[4]} != {want:08x}")
        blob = base64.b64decode(self._readline(10))
        words = struct.unpack(f"<{len(blob) // 8}Q", blob)
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
              wrand=None, wvec=None, iords=None):
    """Run an image, return capture records (or (recs, evt_fired) with
    want_fired). Uses the persistent serve session unless V30_NO_SERVE=1;
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
    if os.environ.get("V30_NO_SERVE") == "1":
        if evt is not None or iord is not None or pins is not None \
                or use_core is not None or wrand is not None or wvec is not None:
            raise RunError("evt/iord/pins/use_core/wrand/wvec require serve")
        return _run_image_legacy(image, host, tag, waits)
    r = _runners.get(host)
    if r is None:
        r = _runners[host] = ServeRunner(host)
    for attempt in (1, 2):
        try:
            r.ensure()
            r.cfg(waits, use_core)
            r.wrand(wrand if wvec is None else None)
            r.replay(wvec)
            recs, fired = r.run(image, evt=evt, iord=iord, pins=pins,
                                cap=cap, iords=iords)
            return (recs, fired) if want_fired else recs
        except RunError as e:
            r.close()
            if attempt == 2:
                print(f"serve path failed twice ({e}); trying legacy path",
                      file=sys.stderr)
    if evt is not None or iord is not None or pins is not None \
            or use_core is not None or wrand is not None or wvec is not None:
        raise RunError("serve path failed and evt/iord/pins/use_core/wrand/wvec "
                       "have no legacy fallback")
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
             ivt=None, stub_linear=None, waits=0, ram=None, evt=None,
             iord=None, pins=None):
    image, meta = testimage.compose(regs=regs, instr=instr, ivt=ivt,
                                    stub_linear=stub_linear, ram=ram)
    recs, fired = run_image(image, host, tag, waits=waits, evt=evt,
                            iord=iord, pins=pins, want_fired=True)
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


def cmd_profile(host):
    """Mission 13: time the legacy path's stages, then the serve path,
    then a 50-case verified echo burst."""
    inject = {"AW": 0x1111, "BW": 0x2222, "CW": 0x3333, "DW": 0x4444,
              "SP": 0x5555, "BP": 0x6666, "IX": 0x7777, "IY": 0x8888,
              "DS0": 0x9999, "DS1": 0xAAAA, "SS": 0xBBBB,
              "PS": 0x0000, "PC": 0x0400, "PSW": 0x0000}
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
            got["PC"] == (exp["PC"] + 6) & 0xFFFF
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
