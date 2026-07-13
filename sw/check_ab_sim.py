#!/usr/bin/env python3
"""check_ab_sim - Campaign 4 Mission A/C, simulation half.

Runs the v30_core INSIDE the real integration (system_large) behind the
actual nec_bus capture path, via hdl/tb/tb_ab.sv under Verilator with the
A/B mux set to the core position (CFG.use_core=1). It drains the harness
capture buffer and diffs the core's boot trace against the real chip's
first boot measurement (sw/testdata/largemode_boot_real.hex) — the same
golden and the same column policy sw/check_boot.py uses for the standalone
core replay.

A match here proves the in-FPGA A/B harness observes the core exactly as it
observes the socketed chip: the capture path, memory model and pin sampling
serve both identically. The on-silicon confirmation is sw/check_seq.py with
CFG.use_core toggled on the board (Mission C/E).

Usage: check_ab_sim.py [nrows] [--build] [--keep]
"""
import subprocess
import sys
import tempfile
from pathlib import Path

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
from decode_capture import decode  # noqa: E402

ROOT = SW.parent
TB_DIR = ROOT / "hdl" / "tb"
OBJ = TB_DIR / "obj_dir_ab"
BIN = OBJ / "tb_ab"
CAPTURE = SW / "testdata" / "largemode_boot_real.hex"

RTL = [
    TB_DIR / "tb_ab.sv",
    ROOT / "hdl" / "rtl" / "system_large.sv",
    ROOT / "hdl" / "rtl" / "nec_bus.sv",
    ROOT / "hdl" / "rtl" / "test_mem.sv",
    ROOT / "hdl" / "rtl" / "capture_buf.sv",
    ROOT / "hdl" / "rtl" / "hps_axi_slave.sv",
    ROOT / "hdl" / "rtl" / "core" / "v30_core.sv",
    ROOT / "hdl" / "rtl" / "core" / "v30_biu.sv",
    ROOT / "hdl" / "rtl" / "core" / "v30_eu.sv",
]

T_NAME = {0: "Ti", 1: "T1", 2: "T2", 3: "T3", 4: "Tw", 5: "T4"}
BS_NAME = {0: "INTA", 1: "IOR", 2: "IOW", 3: "HALT",
           4: "CODE", 5: "MEMR", 6: "MEMW", 7: "PASV"}
QS_NAME = {0: "-", 1: "F", 2: "E", 3: "S"}


def build(force=False):
    stale = force or not BIN.exists()
    if not stale:
        bt = BIN.stat().st_mtime
        stale = any(f.stat().st_mtime > bt for f in RTL)
    if not stale:
        return
    cmd = ["verilator", "--binary", "--timing", "-Wno-fatal",
           "--top-module", "tb_ab", "-Mdir", str(OBJ), "-o", "tb_ab",
           *[str(f) for f in RTL]]
    print("building tb_ab ...", file=sys.stderr)
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not BIN.exists():
        sys.stderr.write(r.stdout + r.stderr)
        sys.exit("tb_ab build failed")


def run_core(nrows, keep=False):
    td = tempfile.mkdtemp(prefix="ab_")
    cap = Path(td) / "core_cap.hex"
    r = subprocess.run([str(BIN), f"+cap={cap}", f"+ncap={nrows + 20}"],
                       capture_output=True, text=True)
    if "AB TESTS PASSED" not in r.stdout:
        sys.stderr.write(r.stdout + r.stderr)
        sys.exit("tb_ab run failed / A-B self-checks failed")
    recs = [decode(int(l, 16)) for l in cap.read_text().split() if l]
    if keep:
        print(f"kept core capture: {cap}", file=sys.stderr)
    # align at RESET release, like check_boot
    rel = next(i for i, d in enumerate(recs) if not d["reset"])
    return recs[rel:]


def load_real():
    recs = [decode(int(l, 16)) for l in CAPTURE.read_text().split() if l]
    rel = next(i for i, r in enumerate(recs) if not r["reset"])
    return recs[rel:]


def main():
    args = sys.argv[1:]
    force = "--build" in args
    keep = "--keep" in args
    pos = [a for a in args if not a.startswith("-")]
    n = int(pos[0]) if pos else 200

    build(force)
    real = load_real()
    sim = run_core(n)

    bad = 0
    for i in range(min(n, len(real), len(sim))):
        r, s = real[i], sim[i]
        mm = []
        if QS_NAME[r["qs"]] != QS_NAME[s["qs"]]:
            mm.append(f"qs {QS_NAME[r['qs']]}!={QS_NAME[s['qs']]}")
        if i >= 8 and r["bs_early"] != s["bs_early"]:
            mm.append(f"bs {BS_NAME[r['bs_early']]}!={BS_NAME[s['bs_early']]}")
        if i >= 9:
            if r["t_state"] != s["t_state"]:
                mm.append(f"t {T_NAME.get(r['t_state'])}!={T_NAME.get(s['t_state'])}")
            if r["ube_n"] != s["ube_n"]:
                mm.append(f"ube {r['ube_n']}!={s['ube_n']}")
            t = r["t_state"]
            active = r["bs_early"] != 7
            if t == 1 and r["ad_addr"] != s["ad_addr"]:
                mm.append(f"addr {r['ad_addr']:05x}!={s['ad_addr']:05x}")
            if t in (2, 3) and r["ad_data"] != s["ad_data"]:
                mm.append(f"data {r['ad_data']:04x}!={s['ad_data']:04x}")
            if t in (0, 5) and active and r["ad_data"] != s["ad_data"]:
                mm.append(f"nxta {r['ad_data']:04x}!={s['ad_data']:04x}")
            if t == 2 and active and r["ps"] != s["ps"]:
                mm.append(f"ps {r['ps']:x}!={s['ps']:x}")
        if mm:
            bad += 1
            if bad <= 12:
                print(f"row {i:3d} (release+{i}): " + ", ".join(mm) +
                      f"   [real {T_NAME.get(r['t_state'])} "
                      f"{BS_NAME[r['bs_early']]} {QS_NAME[r['qs']]} "
                      f"{r['ad_addr']:05x}/{r['ad_data']:04x} | core "
                      f"{T_NAME.get(s['t_state'])} {BS_NAME[s['bs_early']]} "
                      f"{QS_NAME[s['qs']]} {s['ad_addr']:05x}/{s['ad_data']:04x}]")

    # loop-period sanity: CODE T1 at 00100 recurrence
    t1s = [i for i, r in enumerate(real[:n])
           if r["t_state"] == 1 and r["bs_early"] == 4
           and r["ad_addr"] == 0x00100]
    t1c = [i for i, r in enumerate(sim[:n])
           if r["t_state"] == 1 and r["bs_early"] == 4
           and r["ad_addr"] == 0x00100]
    print(f"\nloop CODE T1 @00100: real {t1s} core {t1c}")
    print(f"\n{'AB SIM MATCHES CHIP BOOT' if bad == 0 else f'{bad} rows differ'}"
          f" over {min(n, len(real), len(sim))} rows from RESET release")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
