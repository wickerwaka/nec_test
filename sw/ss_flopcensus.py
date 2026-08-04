#!/usr/bin/env python3
"""Flop-census-vs-savestate-map lint (standing gate, invoked by ss_lint.py).

Closes the ss_lint blind spot booked in docs/notes/standing_gates.md
(meta-finding #3): ss_lint verifies only symbols ALREADY in the map, so a NEW
*architectural* flop that nobody added to the SSA_ map passes vacuously until a
savestate restore first reads it (the `last_ea` regression, task #30). This
census works the other direction: it enumerates every FLOP DECLARATION in
v30_biu.sv + v30_eu.sv, classifies it architectural vs sim-only, and asserts
that every architectural flop is either SSA_-mapped or carries an explicit
whitelist justification. A new unmapped architectural flop FAILS the lint the
day it is declared, not the day a restore reads it.

CLASSIFICATION RULE (documented so it is auditable, not a heuristic pile-up):

  * A "flop" is a `reg`-declared signal (module-scope, `output reg` ports,
    comma-lists `reg a, b;`, memory arrays `reg [7:0] q_mem [0:5];`) that is a
    NON-BLOCKING (`<=`) assignment target in a sequential block. A `reg` /
    `output reg` assigned only with blocking `=` inside always_comb (the SV
    idiom for combinational outputs, e.g. eu_req/eu_ready/eu_soon) holds no
    state and is NOT a flop -- correctly absent from savestate. Convention in
    this codebase: architectural sequential state is always declared `reg`;
    `logic`/`wire` are combinational. That convention is not trusted blindly --
    the LOGIC-FLOP GUARD below fails the lint if any `logic`/`wire` signal is
    ever a `<=` statement target, which would be an un-censused flop. And the
    `<=` detector's completeness is self-tested: every currently-mapped reg
    MUST be recognized as a flop, else the detector has a blind spot.

  * A flop is SIM-ONLY (non-architectural, EXEMPT by construction) iff its
    declaration is lexically inside a preprocessor region excluded from the
    synthesis/board build: `ifndef SYNTHESIS`, or `ifdef X` for X in
    {VERILATOR, GRID_PHASE_STRICT, V30_PFX_ASSERT, V30_BACKDOOR}. These guard
    coverage counters (cov_*), debug shadows (dbg_*), SVA probes
    (law_dcnt_probe, cyc_saw_tw), the RR4 prefix-leak detector
    (pfx_last_op/pfx_grace), and the verification-only backdoor -- none of which
    exist in silicon, so none can appear in a savestate. (V30_BACKDOOR is
    "verification only, set by the testbench build" per v30_core.sv:16.)

  * Every other flop is ARCHITECTURAL and MUST be SSA_-mapped ("mapped" = its
    declared name appears on at least one line carrying an SSA_B_/SSA_E_ token,
    i.e. a save read-mux arm and/or a restore write arm) OR listed in the
    whitelist (sw/ss_flop_whitelist.txt), one `name  # justification` per line.

Exit 0 = clean, non-zero = a listed violation. No build required.

--core ucore
------------
The ucore (hdl/rtl/ucore) is a second, independent core with a DIFFERENT coding
style, so the `<=`-target rule above is vacuous on it and a second classifier is
used (see scan_clocked):

  * Its EU and its BIU are both a NEXT-STATE FUNCTION plus a REGISTER BANK
    (`always @*`/`always_comb` producing the next value, `always_ff @(posedge
    clk) if (ss_we || srst || ce)` committing it -- ucore U4 pass 3, the
    enable-form refactor).  In the BIU the flops are the `r_*` copies and the
    bare names are combinational; in the EU it is the other way round, the flop
    keeps the name and the next-state value is `<name>_n`.
  * The EU was ONE `always @(posedge clk)` block written in the model's own
    software style until U4 pass 3 -- every architectural register a
    module-scope `reg` assigned with BLOCKING `=` inside that clocked block,
    not a single `<=` in it, so the FSM rule would have censused 1 flop out of
    ~140.  That is why this second classifier exists; it is still needed,
    because the blocking style inside the next-state function is unchanged.
  * The EU body is split across `v30u_eu_*.svh` INCLUDES, and both save arms
    live in includes. A census that scanned only the `.sv` files would see
    neither the state nor the map, so the ucore scan FLATTENS `include` first.

  ucore rule: a `reg` is a FLOP iff it is an assignment target (`=` or `<=`,
  they are the same question) inside a block sensitive to a CLOCK EDGE. That is
  the general statement; the FSM's `<=` rule is its special case. The FSM leg
  keeps the original code path so its output is byte-stable as a standing gate.

  ucore "mapped": the read arms name `r_foo` and the write arms name `foo`, and
  several arms PACK many one-bit fields across MULTIPLE LINES, so the ucore scan
  accumulates an SSA_ statement to its `;` before harvesting names -- a
  line-at-a-time harvest silently loses every packed field on a continuation
  line and reports it UNMAPPED.
"""
import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BIU = ROOT / "hdl/rtl/core/v30_biu.sv"
EU = ROOT / "hdl/rtl/core/v30_eu.sv"
WHITELIST = ROOT / "sw/ss_flop_whitelist.txt"

UCORE_DIR = ROOT / "hdl/rtl/ucore"
UCORE_WHITELIST = ROOT / "sw/ss_flop_whitelist_ucore.txt"

# Preprocessor macros whose guarded regions are excluded from the board build.
# `ifndef SYNTHESIS` -> sim region; `ifdef <one of these>` -> sim region.
SIM_IFDEF = {"VERILATOR", "GRID_PHASE_STRICT", "V30_PFX_ASSERT", "V30_BACKDOOR"}

# module-scope `reg ... ;` (may be a comma-list); the body is split on commas.
MODULE_REG = re.compile(r"^reg\b\s*(?:\[[^\]]*\])?\s*(.+?)\s*;")
# `output reg [..] name` port declaration (terminated by , or ) not ;).
PORT_REG = re.compile(r"^output\s+reg\b\s*(?:\[[^\]]*\])?\s*([A-Za-z_]\w*)")
# module-scope logic/wire (for the logic-flop guard); struct fields are skipped.
LOGIC_DECL = re.compile(r"^(?:output\s+|input\s+)?(?:logic|wire)\b"
                        r"\s*(?:\[[^\]]*\])?\s*(.+?)\s*;")
# statement-level non-blocking assignment: LHS at the start of a (possibly
# prefixed) statement, terminated by `;` on the same line. Requiring `;` on the
# line excludes wrapped relational `<=` comparisons (which continue with && / )).
STMT_PREFIX = re.compile(r"^(?:begin\s+|end\s+|else\s+|"
                         r"always_ff\s*|always\s*|@\s*\([^)]*\)\s*|"
                         r"if\s*\([^)]*\)\s*|"
                         r"[A-Za-z_]\w*\s*:\s*)+")  # always/@()/if/else/label/begin
NB_ASSIGN = re.compile(r"^([A-Za-z_]\w*)\s*(?:\[[^\]]*\])?\s*<=(?!=).*;\s*$")


def parse_names(decl_body):
    """Split a declaration body into bare signal names (drop array dims/inits)."""
    names = []
    for part in decl_body.split(","):
        m = re.match(r"\s*([A-Za-z_]\w*)", part)
        if m:
            names.append(m.group(1))
    return names


def scan(path, prefix):
    lines = path.read_text().splitlines()
    simstack = []                       # bool per open ifdef level: sim-only?
    struct_depth = 0                    # inside a typedef struct { ... } body?
    regs = {}                           # name -> (lineno, sim_only)
    logic_names = {}                    # name -> lineno (module-scope logic/wire)
    ssa_names = set()                   # names referenced on any SSA_ arm line
    nb_targets = set()                  # statement-level `<=` LHS targets

    for i, raw in enumerate(lines, 1):
        s = raw.strip()

        m = re.match(r"`(ifdef|ifndef)\s+(\w+)", s)
        if m:
            kind, sym = m.groups()
            sim = (kind == "ifndef" and sym == "SYNTHESIS") or \
                  (kind == "ifdef" and sym in SIM_IFDEF)
            simstack.append(sim)
            continue
        if s.startswith("`else"):
            if simstack:
                simstack[-1] = not simstack[-1]
            continue
        if s.startswith("`endif"):
            if simstack:
                simstack.pop()
            continue

        # skip typedef struct bodies: their `logic` members are fields, not flops
        if "struct packed" in s:
            struct_depth += 1
        elif struct_depth and "}" in s:
            struct_depth -= 1
            continue
        if struct_depth:
            continue

        sim_active = any(simstack)

        pm = PORT_REG.match(s)
        rm = MODULE_REG.match(s)
        if pm:
            regs[pm.group(1)] = (i, sim_active)
        elif rm:
            for nm in parse_names(rm.group(1)):
                regs[nm] = (i, sim_active)
        else:
            lm = LOGIC_DECL.match(s)
            if lm:
                for nm in parse_names(lm.group(1)):
                    logic_names.setdefault(nm, i)

        if prefix in raw:
            for nm in re.findall(r"\b([A-Za-z_]\w*)\b", raw):
                ssa_names.add(nm)

        # statement-level non-blocking assignment target (strip if()/label/begin)
        body = STMT_PREFIX.sub("", s)
        am = NB_ASSIGN.match(body)
        if am:
            nb_targets.add(am.group(1))

    return regs, logic_names, ssa_names, nb_targets


# ---------------------------------------------------------------------------
# ucore classifier: flatten includes, then classify by BLOCK, not by `<=`.
# ---------------------------------------------------------------------------
INCLUDE = re.compile(r'`include\s+"([^"]+)"')
# a block sensitive to a clock edge -- always / always_ff @(posedge|negedge ..)
ALWAYS_SEQ = re.compile(r"^always(?:_ff)?\s*@\s*\(?\s*(?:posedge|negedge)\b")
ALWAYS_ANY = re.compile(r"^always(?:_comb|_latch)?\b")
# a module-scope construct: ends whatever block context was open
MODSCOPE = re.compile(r"^(?:assign|wire|logic|reg|integer|genvar|localparam|"
                      r"parameter|typedef|function|task|initial|final|module|"
                      r"endmodule|import|export|input|output|inout)\b")
BLK_OPEN = re.compile(r"\b(?:begin|case[xz]?|function|task|fork)\b")
BLK_CLOSE = re.compile(r"\b(?:end|endcase|endfunction|endtask|join(?:_any|_none)?)\b")
UC_PREFIX = re.compile(
    r"^(?:begin\b\s*|end\b\s*|else\b\s*|@\s*\([^)]*\)\s*|"
    r"if\s*\([^)]*\)\s*|for\s*\([^)]*\)\s*|while\s*\([^)]*\)\s*|"
    r"case[xz]?\s*\([^)]*\)\s*|[A-Za-z_]\w*\s*:\s*|"
    r"(?:\d+'[hbdoHBDO])?[0-9A-Fa-fxzXZ_]+\s*:\s*|default\s*:\s*)+")
UC_ASSIGN = re.compile(r"^([A-Za-z_]\w*)\s*(?:\[[^\]]*\])*\s*(?:<=(?!=)|=(?![=~]))")
INT_DECL = re.compile(r"^(?:integer|int)\b\s*(.+?)\s*$")
FOR_HEADER = re.compile(r"\bfor\s*\([^)]*\)")


def flatten(path, out=None):
    """Textual `include` expansion -- what the compiler actually sees."""
    out = [] if out is None else out
    for i, raw in enumerate(path.read_text().splitlines(), 1):
        m = INCLUDE.search(raw)
        if m and not raw.strip().startswith("//"):
            sub = path.parent / m.group(1)
            if sub.exists():
                flatten(sub, out=out)
                continue
        out.append((path.name, i, raw))
    return out


def _nocomment(s):
    i = s.find("//")
    return (s[:i] if i >= 0 else s).strip()


def scan_clocked(paths, prefix):
    """Block-aware census over the flattened source of one region."""
    lines = []
    for p in paths:
        flatten(p, out=lines)

    simstack, struct_depth, depth = [], 0, 0
    ctx = None                          # 'seq' | 'comb' | None
    regs, logic, ints = {}, {}, {}
    ssa_names = set()
    seq_t = set()
    arm, arm_open = [], False

    for fname, ln, raw in lines:
        s = _nocomment(raw)

        m = re.match(r"`(ifdef|ifndef)\s+(\w+)", s)
        if m:
            kind, sym = m.groups()
            simstack.append((kind == "ifndef" and sym == "SYNTHESIS") or
                            (kind == "ifdef" and sym in SIM_IFDEF))
            continue
        if s.startswith("`else"):
            if simstack:
                simstack[-1] = not simstack[-1]
            continue
        if s.startswith("`endif"):
            if simstack:
                simstack.pop()
            continue
        if s.startswith("`"):
            continue

        if "struct packed" in s:
            struct_depth += 1
        elif struct_depth and "}" in s:
            struct_depth -= 1
            continue
        if struct_depth:
            continue

        sim_active = any(simstack)

        # --- SSA arm names, accumulated to the statement's `;` (packed arms
        #     span lines; a per-line harvest loses the continuation fields) ---
        if arm_open or (prefix in s):
            arm_open = True
            arm.append(s)
            if ";" in s:
                for nm in re.findall(r"\b([A-Za-z_]\w*)\b", " ".join(arm)):
                    ssa_names.add(nm)
                arm, arm_open = [], False

        # --- block context ---
        if depth == 0:
            if ALWAYS_SEQ.match(s):
                ctx = "seq"
            elif ALWAYS_ANY.match(s):
                ctx = "comb"
            elif MODSCOPE.match(s):
                ctx = None

        # --- declarations (module scope) ---
        if depth == 0:
            pm = PORT_REG.match(s)
            if pm:
                regs[pm.group(1)] = (fname, ln, sim_active)
            elif s.endswith(";"):
                body = s[:-1]
                rm = MODULE_REG.match(body + ";")
                if rm:
                    for nm in parse_names(rm.group(1)):
                        regs[nm] = (fname, ln, sim_active)
                else:
                    lm = LOGIC_DECL.match(body + ";")
                    im = INT_DECL.match(body)
                    if lm:
                        for nm in parse_names(lm.group(1)):
                            logic.setdefault(nm, (fname, ln, sim_active))
                    elif im:
                        for nm in parse_names(im.group(1)):
                            ints.setdefault(nm, (fname, ln, sim_active))

        # --- assignment targets, attributed to their block ---
        # A `for` header's induction variable is re-initialised on every entry
        # to the loop, so it carries nothing across the edge; drop the whole
        # header (no ucore `for` header contains a nested paren) and keep the
        # loop BODY, which is where the real assignments are.
        if ctx is not None:
            s = FOR_HEADER.sub(" ", s)
            for stmt in s.split(";"):
                if not stmt.strip():
                    continue
                am = UC_ASSIGN.match(UC_PREFIX.sub("", stmt.strip()))
                if am and ctx == "seq":
                    seq_t.add(am.group(1))

        code = re.sub(r'"[^"]*"', "", s)
        depth += len(BLK_OPEN.findall(code)) - len(BLK_CLOSE.findall(code))
        if depth < 0:
            depth = 0

    return regs, logic, ints, ssa_names, seq_t


def load_whitelist(path=None):
    entries = {}
    path = path or WHITELIST
    if path.exists():
        for ln in path.read_text().splitlines():
            ln = ln.strip()
            if not ln or ln.startswith("#"):
                continue
            name = ln.split("#", 1)[0].strip()
            just = (ln.split("#", 1)[1].strip() if "#" in ln else "")
            if name:
                if not just:
                    # whitelist entries MUST carry a justification
                    entries[name] = None
                else:
                    entries[name] = just
    return entries


def main_ucore():
    """The ucore leg: flattened includes + clocked-block classification."""
    errs = []
    wl = load_whitelist(UCORE_WHITELIST)
    for name, just in wl.items():
        if just is None:
            errs.append(f"whitelist entry '{name}' has no justification "
                        f"(format: `name  # reason`)")

    eu_files = [UCORE_DIR / "v30u_eu.sv"] + sorted(UCORE_DIR.glob("v30u_eu_*.svh"))
    regions = (
        ("BIU", "SSA_B_", [UCORE_DIR / "v30u_biu.sv"]),
        ("EU", "SSA_E_", eu_files),
    )

    summary = []
    for region, prefix, paths in regions:
        regs, logic_names, ints, ssa_names, seq_t = scan_clocked(paths, prefix)

        flops = {n: v for n, v in regs.items() if n in seq_t}
        comb_regs = [n for n in regs if n not in seq_t]
        arch = {n: v for n, v in flops.items() if not v[2]}
        simonly = {n: v for n, v in flops.items() if v[2]}

        mapped, unmapped, whitelisted = [], [], []
        for n, v in sorted(arch.items()):
            if n in ssa_names:
                mapped.append(n)
            elif n in wl:
                whitelisted.append(n)
            else:
                unmapped.append((n, v))
                errs.append(f"{region}: architectural flop '{n}' "
                            f"({v[0]}:{v[1]}) is UNMAPPED "
                            f"(no SSA_{region[0]}_ arm, no whitelist entry)")

        # LOGIC-FLOP / INTEGER-FLOP GUARD: the ucore's convention is that
        # sequential state is declared `reg`. A `logic`/`wire`/`integer`
        # assigned in a clocked block is state this census would not see.
        for n, v in sorted(list(logic_names.items()) + list(ints.items())):
            if n in seq_t and n not in regs and not v[2]:
                errs.append(f"{region}: '{n}' ({v[0]}:{v[1]}) is assigned in a "
                            f"clocked block but is not declared `reg` (a flop "
                            f"the census misses) -- declare it `reg` or "
                            f"whitelist it")

        label = paths[0].name if len(paths) == 1 else \
            f"{paths[0].name} +{len(paths) - 1} includes"
        summary.append((region, label, len(arch), len(mapped),
                        len(whitelisted), len(unmapped), len(simonly)))
        print(f"{region} ({label}): {len(arch)} architectural flops -> "
              f"{len(mapped)} SSA-mapped, {len(whitelisted)} whitelisted, "
              f"{len(unmapped)} UNMAPPED; {len(simonly)} sim-only exempt "
              f"({len(comb_regs)} comb/next-state regs skipped)")

    tot_arch = sum(r[2] for r in summary)
    tot_wl = sum(r[4] for r in summary)
    if errs:
        print("\nss_flopcensus: FAIL")
        for e in errs:
            print(f"  - {e}")
        return 1
    print(f"\nss_flopcensus: PASS ({tot_arch} architectural flops, all "
          f"SSA-mapped or whitelisted; {tot_wl} whitelist entries)")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--core", choices=("fsm", "ucore"), default="fsm",
                    help="which core's RTL to census (default: fsm)")
    args = ap.parse_args()
    if args.core == "ucore":
        return main_ucore()

    errs = []
    wl = load_whitelist()
    for name, just in wl.items():
        if just is None:
            errs.append(f"whitelist entry '{name}' has no justification "
                        f"(format: `name  # reason`)")

    summary = []
    for path, prefix, region in ((BIU, "SSA_B_", "BIU"), (EU, "SSA_E_", "EU")):
        regs, logic_names, ssa_names, nb_targets = scan(path, prefix)

        # A reg is a FLOP only if it is a non-blocking-assignment target; a reg
        # assigned only with `=` in always_comb is a combinational output.
        flops = {n: (li, so) for n, (li, so) in regs.items() if n in nb_targets}
        comb_regs = [n for n in regs if n not in nb_targets]

        arch = {n: li for n, (li, so) in flops.items() if not so}
        simonly = {n: li for n, (li, so) in flops.items() if so}

        # SELF-TEST: every currently-SSA-mapped reg must be detected as a flop.
        # If a mapped reg is not in nb_targets the `<=` detector has a blind
        # spot (e.g. a multi-line assignment) and the whole census is suspect.
        for n in sorted(regs):
            if n in ssa_names and n not in nb_targets and n != "ss_rdata":
                errs.append(f"{region}: mapped reg '{n}' not detected as a flop "
                            f"by the `<=` scan -- detector blind spot, fix it")

        mapped, unmapped, whitelisted = [], [], []
        for n, li in sorted(arch.items()):
            if n in ssa_names:
                mapped.append(n)
            elif n in wl:
                whitelisted.append(n)
            else:
                unmapped.append((n, li))
                errs.append(f"{region}: architectural flop '{n}' "
                            f"({path.name}:{li}) is UNMAPPED "
                            f"(no SSA_{region[0]}_ arm, no whitelist entry)")

        # LOGIC-FLOP GUARD: a logic/wire that is a `<=` statement target is a
        # flop the reg-census would miss -> convention broken, fail loudly.
        for n, li in sorted(logic_names.items()):
            if n in nb_targets and n not in regs:
                errs.append(f"{region}: '{n}' ({path.name}:{li}) is declared "
                            f"logic/wire but non-blocking-assigned (a flop the "
                            f"census misses) -- declare it `reg` or whitelist it")

        summary.append((region, path.name, len(arch), len(mapped),
                        len(whitelisted), len(unmapped), len(simonly)))
        print(f"{region} ({path.name}): {len(arch)} architectural flops -> "
              f"{len(mapped)} SSA-mapped, {len(whitelisted)} whitelisted, "
              f"{len(unmapped)} UNMAPPED; {len(simonly)} sim-only exempt "
              f"({len(comb_regs)} comb output-regs skipped)")

    if errs:
        print("\nss_flopcensus: FAIL")
        for e in errs:
            print(f"  - {e}")
        return 1
    tot_arch = sum(r[2] for r in summary)
    tot_wl = sum(r[4] for r in summary)
    print(f"\nss_flopcensus: PASS ({tot_arch} architectural flops, all "
          f"SSA-mapped or whitelisted; {tot_wl} whitelist entries)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
