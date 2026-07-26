#!/usr/bin/env python3
"""prefix_clear_lint - standing gate for the RR4 one-shot-prefix-latch clear.

Guarantees every S_FIRST entry in v30_eu.sv either clears the prefix latches
(via clear_prefixes()/retire()) or is an authorized `// PFX-KEEP` (census
frozen at 4, signature-matched), and that no ad-hoc latch clear drifts back in.
This catches the NEXT new exit path at CI time, before any board work.

Rules (scratchpad/prefix_clear_design.md §6b):
 1. every `state <= S_FIRST` site has clear_prefixes()/retire() within the 12
    preceding lines (or same line), OR a `// PFX-KEEP` tag on the site or a
    preceding line within the window.
 2. PFX-KEEP census == EXACTLY 4, each signature-matched (backdoor: bkd_load;
    own-retires: seg_ovr_en/rep_en/lock_en <= 1'b1 within window).
 3. clear_prefixes() body clears exactly {seg_ovr_en, rep_en, lock_en}.
 4. drift guard: `<latch> <= 1'b0` for the three latches appears ONLY in
    clear_prefixes() body, the reset block, and the ss write-decode.
"""
import re
import sys
from pathlib import Path

EU = Path(__file__).resolve().parents[1] / "hdl/rtl/core/v30_eu.sv"
LATCHES = ("seg_ovr_en", "rep_en", "lock_en")
WINDOW = 12


def main():
    lines = EU.read_text().split("\n")
    errs = []
    sfirst = [i for i, l in enumerate(lines)
              if re.search(r"state\s*<=\s*S_FIRST", l)]
    keeps = []
    for i in sfirst:
        win = lines[max(0, i - WINDOW):i + 1]
        wtext = "\n".join(win)
        has_clear = ("clear_prefixes()" in wtext) or \
                    re.search(r"\bretire\(\)", wtext)
        is_keep = "PFX-KEEP" in wtext
        if is_keep:
            keeps.append(i)
            # signature match
            sig = ("bkd_load" in wtext) or \
                any(re.search(rf"{x}\s*<=\s*1'b1", wtext) for x in LATCHES)
            if not sig:
                errs.append(f":{i+1} PFX-KEEP without a valid signature "
                            f"(need bkd_load or <latch> <= 1'b1 in window)")
        elif not has_clear:
            errs.append(f":{i+1} state<=S_FIRST with NO clear_prefixes()/"
                        f"retire()/PFX-KEEP in the {WINDOW}-line window: "
                        f"{lines[i].strip()}")

    if len(keeps) != 4:
        errs.append(f"PFX-KEEP census = {len(keeps)} (must be EXACTLY 4): "
                    f"lines {[k+1 for k in keeps]}")

    # rule 3: clear_prefixes body
    m = re.search(r"task automatic clear_prefixes\(\);(.*?)endtask",
                  "\n".join(lines), re.S)
    if not m:
        errs.append("clear_prefixes() task not found")
    else:
        body = m.group(1)
        cleared = set(re.findall(r"(\w+)\s*<=\s*1'b0", body))
        if cleared != set(LATCHES):
            errs.append(f"clear_prefixes() body clears {cleared}, "
                        f"expected {set(LATCHES)}")

    # rule 4: drift guard -- <latch> <= 1'b0 only in clear_prefixes/reset/ss
    txt = "\n".join(lines)
    cp_span = m.span(1) if m else (0, 0)
    for i, l in enumerate(lines):
        for x in LATCHES:
            if re.search(rf"{x}\s*<=\s*1'b0", l):
                off = sum(len(z) + 1 for z in lines[:i])
                in_cp = cp_span[0] <= off <= cp_span[1]
                # reset block: scan upward to the enclosing `if (srst`, stopping
                # at an always_ff / endtask / `else if (ce)` block boundary.
                in_reset = False
                for j in range(i, max(0, i - 200), -1):
                    if re.search(r"if\s*\(srst", lines[j]):
                        in_reset = True
                        break
                    if re.search(r"always_ff|endtask|else if\s*\(ce\)", lines[j]):
                        break
                # ss write-decode: ss_wdata nearby
                ctx = "\n".join(lines[max(0, i - 8):i + 1])
                in_ss = "ss_wdata" in ctx or "ss_we" in ctx
                if not (in_cp or in_reset or in_ss):
                    errs.append(f":{i+1} ad-hoc '{x} <= 1'b0' outside "
                                f"clear_prefixes/reset/ss: {l.strip()}")

    if errs:
        print("prefix_clear_lint: FAIL")
        for e in errs:
            print("  " + e)
        return 1
    print(f"prefix_clear_lint: PASS ({len(sfirst)} S_FIRST sites; "
          f"4 PFX-KEEP; clear_prefixes single source; no drift)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
