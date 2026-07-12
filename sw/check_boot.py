#!/usr/bin/env python3
"""check_boot - mission G: replay the real reset flow in the RTL core and
diff it against the chip's very first measurement (capture8, sw/testdata/
largemode_boot_real.hex).

The TB (+bootimg mode) loads sw/boot.bin, holds RESET, releases, and
records per-cycle pin records with no backdoor involvement. Comparison is
aligned at the RESET release edge and covers the reset-to-first-fetch
pattern, the EA far jump, and the steady-state 64-cycle boot loop.

Column policy (the boot capture predates the calibrated sampling of the
suite pipeline; only artifact-free columns are compared):
  qs:              from release (the reset E blip at release+7 included)
  bs_early:        from release+8 (pins float INTA-low before the first
                   status on the real chip)
  t/ube/addr/data/ps: from release+9 (first T1); addr on T1 rows, data on
                   T2/T3 rows and on T4/Ti status rows (= next address),
                   NOT on T1 rows (raw-capture sampling artifact), ps on
                   T2 rows of active cycles.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
from decode_capture import decode  # noqa: E402

ROOT = SW.parent
BIN = ROOT / "hdl" / "tb" / "obj_dir" / "Vtb_v30_core"
CAPTURE = SW / "testdata" / "largemode_boot_real.hex"
BOOTBIN = SW / "boot.bin"

T_NAME = {0: "Ti", 1: "T1", 2: "T2", 3: "T3", 4: "Tw", 5: "T4"}
BS_NAME = {0: "INTA", 1: "IOR", 2: "IOW", 3: "HALT",
           4: "CODE", 5: "MEMR", 6: "MEMW", 7: "PASV"}
QS_NAME = {0: "-", 1: "F", 2: "E", 3: "S"}


def load_real():
    recs = [decode(int(l, 16)) for l in CAPTURE.read_text().split() if l]
    rel = next(i for i, r in enumerate(recs) if not r["reset"])
    return recs[rel:]


def run_sim(n):
    td = tempfile.mkdtemp(prefix="boot_")
    img = Path(td) / "boot.hex"
    out = Path(td) / "out.txt"
    data = BOOTBIN.read_bytes()
    img.write_text("\n".join(f"{b:02x}" for b in data) + "\n")
    r = subprocess.run([str(BIN), f"+bootimg={img}", f"+bootn={n}",
                        f"+out={out}"], capture_output=True, text=True)
    if "BOOT DONE" not in r.stdout:
        print(r.stdout, r.stderr)
        sys.exit("sim failed")
    sim = []
    for line in out.read_text().splitlines():
        p = line.split()
        if p and p[0] == "r":
            sim.append({"t": int(p[1]), "bs_early": int(p[2]),
                        "qs": int(p[3]), "ube_n": int(p[4]),
                        "ad_addr": int(p[5], 16), "ad_data": int(p[6], 16),
                        "ps": int(p[7], 16)})
    return sim


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 220
    real = load_real()
    sim = run_sim(n + 4)
    bad = 0
    for i in range(min(n, len(real), len(sim))):
        r, s = real[i], sim[i]
        mm = []
        if QS_NAME[r["qs"]] != QS_NAME[s["qs"]]:
            mm.append(f"qs {QS_NAME[r['qs']]}!={QS_NAME[s['qs']]}")
        if i >= 8 and r["bs_early"] != s["bs_early"]:
            mm.append(f"bs {BS_NAME[r['bs_early']]}!="
                      f"{BS_NAME[s['bs_early']]}")
        if i >= 9:
            if r["t_state"] != s["t"]:
                mm.append(f"t {T_NAME.get(r['t_state'])}!="
                          f"{T_NAME.get(s['t'])}")
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
                      f"{r['ad_addr']:05x}/{r['ad_data']:04x} | sim "
                      f"{T_NAME.get(s['t'])} {BS_NAME[s['bs_early']]} "
                      f"{QS_NAME[s['qs']]} "
                      f"{s['ad_addr']:05x}/{s['ad_data']:04x}]")

    # loop-period check: CODE T1 at 00100 recurrence
    t1s = [i for i, r in enumerate(real[:n])
           if r["t_state"] == 1 and r["bs_early"] == 4
           and r["ad_addr"] == 0x00100]
    t1s_s = [i for i, r in enumerate(sim[:n])
             if r["t"] == 1 and r["bs_early"] == 4
             and r["ad_addr"] == 0x00100]
    print(f"\nloop CODE T1 @00100: real {t1s} sim {t1s_s}")
    if len(t1s) >= 2:
        print(f"real loop period {t1s[1] - t1s[0]}; "
              f"sim loop period "
              f"{(t1s_s[1] - t1s_s[0]) if len(t1s_s) >= 2 else '?'}")
    print(f"\n{'BOOT REPLAY MATCHES' if bad == 0 else f'{bad} rows differ'}"
          f" over {n} rows from RESET release")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
