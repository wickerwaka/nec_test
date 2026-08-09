#!/usr/bin/env python3
"""r7_lint -- THE R7' STRUCTURAL INVARIANT, ENFORCED INSTEAD OF COMMENTED.

WHY IT EXISTS
-------------
`ucore_provenance.md` §73 closed R7': the live `READY` pin was reaching the
EU's next-state cone single-cycle, at 55-63 logic levels, and the DEFAULT build
measured **19.42 MHz**.  The fix moved the read's data-edge PSW load off the
head of the EU's twelve-position loader chain and onto the `psw` register's own
`D` pin.  The invariant that keeps it closed was then written down -- as a
COMMENT, in `hdl/rtl/ucore/v30u_eu.sv`:

    "`eu_rd_edge` is the ONLY thing in this module that carries the LIVE
     `READY` pin.  [...] everything else the EU reads [...] is REGISTER-ONLY."

Nothing enforced it.  Commit `5403671558` crossed it in THREE places, left the
comment standing, and took the tree from 45.98 MHz to 15.14 MHz.  No gate saw
it: the standing set has no structural check, and G6 was not run.  This is the
same vacuous-gate pattern `docs/notes/artifact_receipt_layer.md` tracks by
name; the answer to a comment nobody can violate accidentally is a gate.

WHAT IT CHECKS
--------------
(a) THE READY-CARRIER CHECK.  For every net that leaves the BIU and enters the
    EU (derived from the two instantiations in the core's top file -- not from
    a name prefix), the net's combinational cone inside the BIU is walked.  A
    net whose cone reaches the bare `ready` INPUT PIN is a live-READY carrier
    and is a VIOLATION unless it is in `READY_CARRIER_EXCEPTIONS` below.

(b) THE `stop` CONTROL CHECK.  `stop` is what breaks the twelve-position
    chain, so a condition that gates `stop` is IN the chain's control cone.
    Every assignment to `stop` in the chain's own sources is located with a
    token-level parse of the enclosing `if`/`else if`/`case` arms, and it is a
    VIOLATION if any condition governing it transitively reads a carrier found
    by (a).  Note that (a)'s declared exception is NOT an exception here: §73's
    whole point is that the carrier may reach a register's `D` pin and MUST NOT
    reach control.

WHAT IT DOES **NOT** ESTABLISH
------------------------------
This is a STRUCTURAL check with a declared exception list.  It is not a
synthesis-accurate timing model and it cannot prove -- or disprove -- timing
closure.  Only Quartus can do that (`sw/quartus_gate.py`, G6).  A PASS here
means "the shape §73 closed R7' with is still the shape in the tree"; it does
not mean the build closes, and a RED here does not by itself mean it will not.
Its value is that it is FAST and it runs on every landing, where a 15-minute
Quartus build does not.

Known blind spots, stated so they are not discovered as surprises:
  * The BIU cone walk follows CONTINUOUS assignments only (`assign x = ...`,
    `wire x = ...`).  A net driven from a procedural `always_comb` variable
    cannot be resolved this way, so such a net is reported UNRESOLVED and must
    be DECLARED in `DECLARED_UNRESOLVED` with its argument.  That is the
    conservative direction: a NEW procedural output has to be declared, not
    discovered by Quartus three sittings later.
  * The taint walk in (b) covers the EU's continuous wires plus blocking
    assignments made inside the chain sources themselves.  A carrier laundered
    through a flop is, correctly, not tainted -- that is the invariant.
  * `--core fsm` is INFORMATIONAL ONLY.  The FSM core is archived
    (`docs/notes/fsm_core_archive_2026-08-04.md`); it is never gated here.

    python3 sw/r7_lint.py                  # the ucore, the gate
    python3 sw/r7_lint.py -v               # ...and print every net's verdict
    python3 sw/r7_lint.py --core fsm       # informational, never a gate

EXIT 0 = PASS, 1 = VIOLATION, 2 = the lint could not run (missing source).
"""
import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------- #
# THE DECLARED EXCEPTIONS.  Both lists are meant to stay SHORT.  An exception
# list that grows silently is how the invariant died the first time, so every
# entry carries the argument that admits it and the record it comes from.
# --------------------------------------------------------------------------- #
READY_CARRIER_EXCEPTIONS = {
    "eu_rd_edge":
        "§73 (SM3 sitting 12).  THE one declared carrier.  It exists because "
        "`interrupt_model.md`'s POP-PSW law consumes the popped image at the "
        "read's DATA EDGE, and that edge IS the READY sample.  It is admitted "
        "only because its single consumer is the `psw` register's own `D` pin "
        "(v30u_eu.sv `rd_edge_psw_take`), NOT the head of the loader chain -- "
        "which is exactly what R7' moved.  Check (b) therefore treats it as a "
        "carrier with NO exception: if it ever gates `stop`, R7' is re-opened.",
}

DECLARED_UNRESOLVED = {
    "eu_slot_busy_n":
        "§73, by elimination.  The `ts` advance (the READY sample) reaches the "
        "EU only through this net, and `S_PRERD` consumes it inside an arm "
        "that sets `stop` on EVERY branch, so its cone ends at `row_posted_n` "
        "/ `rd_pending_n` and never reaches the chain's next-state.  Driven "
        "from the procedural `slot_busy`, so the walk cannot resolve it; the "
        "argument is the declaration.",
    "q_ripe_lead_n":
        "§73's own list of REGISTER-ONLY EU inputs.  Driven from `poppable_n` "
        "off the queue's procedural next-state (`q_cnt`, `grn_ttl`, `grn_n`), "
        "which is the queue's own bookkeeping and not the READY sample.",
}

# --------------------------------------------------------------------------- #
CORES = {
    "ucore": {
        "dir": "hdl/rtl/ucore",
        "top": "v30_core.sv", "biu": "v30u_biu.sv", "eu": "v30u_eu.sv",
        "biu_mod": "v30u_biu", "eu_mod": "v30u_eu",
        "eu_incl": "v30u_eu_*.svh",
        "chain": ["v30u_eu_step.svh", "v30u_eu_row.svh"],
        "ready": "ready", "stop": "stop",
    },
    "fsm": {                       # ARCHIVED -- informational, never a gate
        "dir": "hdl/rtl/core",
        "top": "v30_core.sv", "biu": "v30_biu.sv", "eu": "v30_eu.sv",
        "biu_mod": "v30_biu", "eu_mod": "v30_eu",
        "eu_incl": "v30_eu_*.svh",
        "chain": [],
        "ready": "ready", "stop": "stop",
    },
}

KEYWORDS = {
    "begin", "end", "if", "else", "case", "casez", "casex", "endcase",
    "default", "assign", "wire", "logic", "reg", "input", "output", "inout",
    "always", "always_comb", "always_ff", "always_latch", "posedge", "negedge",
    "module", "endmodule", "function", "endfunction", "task", "endtask",
    "parameter", "localparam", "typedef", "enum", "struct", "packed", "bit",
    "int", "integer", "signed", "unsigned", "return", "unique", "priority",
    "for", "while", "generate", "endgenerate", "genvar", "initial", "final",
    "automatic", "static", "const", "void", "or", "and", "not", "xor",
}

TOKEN_RE = re.compile(
    r"\d*'[sS]?[bodhBODH][0-9a-fA-FxXzZ_?]+"       # sized literal
    r"|[A-Za-z_$][A-Za-z_0-9$]*"                   # identifier
    r"|\d[\d_.]*"                                  # number
    r"|<<<|>>>|===|!==|==\?|!=\?"
    r"|<=|>=|==|!=|&&|\|\||<<|>>|\+:|-:|->|::"
    r"|."
)


# --------------------------------------------------------------------------- #
# lexing
# --------------------------------------------------------------------------- #
def strip_comments(text):
    """Blank out comments IN PLACE so every character keeps its line number."""
    out = list(text)
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c == '/' and i + 1 < n and text[i + 1] == '/':
            while i < n and text[i] != '\n':
                out[i] = ' '
                i += 1
        elif c == '/' and i + 1 < n and text[i + 1] == '*':
            while i < n and not (text[i] == '*' and i + 1 < n
                                 and text[i + 1] == '/'):
                if text[i] != '\n':
                    out[i] = ' '
                i += 1
            for j in range(i, min(i + 2, n)):
                out[j] = ' '
            i += 2
        elif c == '"':
            i += 1
            while i < n and text[i] != '"':
                i += 1
            i += 1
        else:
            i += 1
    return ''.join(out)


def strip_directives(text):
    """Blank out `ifdef/`else/`endif/`include lines -- both arms are read."""
    lines = text.split('\n')
    for k, ln in enumerate(lines):
        if ln.lstrip().startswith('`'):
            lines[k] = ' ' * len(ln)
    return '\n'.join(lines)


def tokenize_fast(text):
    """-> [(tok, line)], whitespace dropped.  O(n): lines carried, not
    recounted."""
    toks = []
    line = 1
    pos = 0
    for m in TOKEN_RE.finditer(text):
        line += text.count('\n', pos, m.start())
        pos = m.start()
        t = m.group(0)
        if not t.isspace():
            toks.append((t, line))
    return toks


def idents(toks):
    return [t for t, _ in toks
            if re.match(r"^[A-Za-z_]", t) and t not in KEYWORDS]


# --------------------------------------------------------------------------- #
# structure
# --------------------------------------------------------------------------- #
def module_ports(text, modname):
    """-> {port: 'input'|'output'|'inout'} off the ANSI header."""
    m = re.search(r"\bmodule\s+" + re.escape(modname) + r"\b", text)
    if not m:
        return {}
    i = text.find('(', m.end())
    depth, j = 0, i
    while j < len(text):
        if text[j] == '(':
            depth += 1
        elif text[j] == ')':
            depth -= 1
            if depth == 0:
                break
        j += 1
    ports, direction = {}, None
    for entry in re.split(r",(?![^\[]*\])", text[i + 1:j]):
        toks = tokenize_fast(entry)
        names = []
        for k, (t, _) in enumerate(toks):
            if t in ("input", "output", "inout"):
                direction = t
            elif re.match(r"^[A-Za-z_]", t) and t not in KEYWORDS:
                names.append(t)
        if names and direction:
            ports[names[-1]] = direction
    return ports


def instance_conns(text, modname):
    """-> {port: [identifiers in the connected expression]} for the (single)
    instantiation of `modname` in `text`."""
    m = re.search(r"\b" + re.escape(modname) + r"\s+\w+\s*\(", text)
    if not m:
        return {}
    i = text.rindex('(', 0, m.end())
    depth, j = 0, i
    while j < len(text):
        if text[j] == '(':
            depth += 1
        elif text[j] == ')':
            depth -= 1
            if depth == 0:
                break
        j += 1
    body = text[i + 1:j]
    conns = {}
    for pm in re.finditer(r"\.(\w+)\s*\(", body):
        k = pm.end() - 1
        d, e = 0, k
        while e < len(body):
            if body[e] == '(':
                d += 1
            elif body[e] == ')':
                d -= 1
                if d == 0:
                    break
            e += 1
        conns[pm.group(1)] = idents(tokenize_fast(body[k + 1:e]))
    return conns


def continuous_drivers(text):
    """-> {name: (rhs_tokens, line)} for `assign x = ...;` and `wire x = ...;`

    LHS bit/part selects are deliberately NOT collected: this walk is about
    whole nets, and a partial driver would make the cone look complete when it
    is not."""
    out = {}
    for m in re.finditer(
            r"\b(?:assign|wire|logic)\b\s*(?:\[[^\]]*\]\s*)?"
            r"([A-Za-z_]\w*)\s*=\s*([^;]*);", text):
        name, rhs = m.group(1), m.group(2)
        line = text.count('\n', 0, m.start()) + 1
        if name in out:                      # multiple drivers: keep the first
            continue
        out[name] = (tokenize_fast(rhs), line)
    return out


def procedural_lhs(text):
    """-> (nonblocking, blocking) LHS name sets, statement-position only.

    Statement position matters: `(r_dage <= 3'd4)` is a COMPARISON and must not
    be read as a nonblocking assignment, which is what a bare `<=` scan does."""
    toks = tokenize_fast(text)
    nb, bl = set(), set()
    boundary = True
    k = 0
    decl = False
    while k < len(toks):
        t = toks[k][0]
        if t in (';',):
            boundary, decl = True, False
            k += 1
            continue
        if t in ('begin', 'end', 'else', ':', 'do', ')'):
            # `)` is a statement boundary because `if (c) x <= y;`,
            # `for (...) x <= y;` and `always @(posedge clk) x <= y;` all put a
            # real assignment there.  It is NOT one inside an expression,
            # because an expression's `<=` is preceded by an operand, never by
            # a close paren that ends a statement head.
            boundary = True
            k += 1
            continue
        if boundary and t in ('assign', 'wire', 'logic', 'reg', 'localparam',
                              'parameter', 'typedef'):
            decl = True
            boundary = False
            k += 1
            continue
        if boundary and re.match(r"^[A-Za-z_]", t) and t not in KEYWORDS:
            j = k + 1
            while j < len(toks) and toks[j][0] == '[':      # skip selects
                d = 0
                while j < len(toks):
                    if toks[j][0] == '[':
                        d += 1
                    elif toks[j][0] == ']':
                        d -= 1
                        if d == 0:
                            j += 1
                            break
                    j += 1
            if j < len(toks) and not decl:
                if toks[j][0] == '<=':
                    nb.add(t)
                elif toks[j][0] == '=':
                    bl.add(t)
            boundary = False
            k = j
            continue
        boundary = False
        k += 1
    return nb, bl


def constant_names(texts):
    """localparam / parameter / enum member names -- safe leaves."""
    out = set()
    for text in texts:
        for m in re.finditer(r"\b(?:localparam|parameter)\b([^;]*);", text):
            body = m.group(1)
            for mm in re.finditer(r"([A-Za-z_]\w*)\s*=", body):
                out.add(mm.group(1))
        for m in re.finditer(r"\benum\b[^{;]*\{([^}]*)\}", text):
            for mm in re.finditer(r"([A-Za-z_]\w*)", m.group(1)):
                if mm.group(1) not in KEYWORDS:
                    out.add(mm.group(1))
        for m in re.finditer(r"\bfunction\b[^;(]*?([A-Za-z_]\w*)\s*\(", text):
            out.add(m.group(1))
    return out


# --------------------------------------------------------------------------- #
# (a) the READY-carrier walk
# --------------------------------------------------------------------------- #
class BiuCone:
    def __init__(self, biu_text, const_names, ready, ports=None):
        self.drv = continuous_drivers(biu_text)
        self.nb, self.bl = procedural_lhs(biu_text)
        self.const = const_names
        self.ready = ready
        # The module's OTHER input ports.  Inside this module they cannot be
        # the READY pin -- that is what "bare `ready`" means -- so the walk
        # ends there.  A pin's value coming back round through the EU is
        # check (b)'s business, not this walk's.
        self.inputs = {k for k, v in (ports or {}).items()
                       if v == "input" and k != ready}

    def walk(self, net):
        """-> (carrier_paths, unresolved) ; each path is a list of
        'name@line' strings ending at the leaf that decided it."""
        carriers, unresolved = [], []
        seen = set()

        def rec(name, path):
            if name == self.ready:
                carriers.append(path + [f"{name} (the LIVE pin)"])
                return
            if name in seen:
                return
            seen.add(name)
            if name in self.drv:
                toks, line = self.drv[name]
                for ident in dict.fromkeys(idents(toks)):
                    rec(ident, path + [f"{name}@{line}"])
                return
            if name in self.const:
                return                                  # constant / function
            if name in self.inputs:
                return                                  # another input pin
            if name in self.nb:
                return                                  # a FLOP -- safe
            if name in self.bl:
                unresolved.append((name, path + [f"{name} (procedural)"]))
                return
            # not a net of this module at all (port, parameter from a package,
            # enum label): unknown -> conservative
            unresolved.append((name, path + [f"{name} (unknown)"]))

        rec(net, [])
        return carriers, unresolved


# --------------------------------------------------------------------------- #
# (b) the `stop` control walk -- a token-level statement parse
# --------------------------------------------------------------------------- #
class StopSite:
    def __init__(self, line, conds):
        self.line = line
        self.conds = conds            # [(text, line)] governing this `stop`


def scan_chain(text, stop_name):
    """-> ([StopSite], {lhs: rhs_idents}) for one chain source file.

    The parse is deliberately small: `begin/end`, `if/else if/else`,
    `case/endcase` and simple statements.  A construct it does not know is
    consumed as a simple statement, which loses conditions rather than
    inventing them -- so an unparsed construct can only cause a MISS, never a
    false accusation, and the chain sources have no `for`/`while`/`fork`."""
    toks = tokenize_fast(text)
    n = len(toks)
    sites, assigns = [], {}

    def paren(i):
        """i points at '(' -> (idents, text, index after ')')"""
        d, j = 0, i
        while j < n:
            if toks[j][0] == '(':
                d += 1
            elif toks[j][0] == ')':
                d -= 1
                if d == 0:
                    break
            j += 1
        inner = toks[i + 1:j]
        return idents(inner), ' '.join(t for t, _ in inner), j + 1

    def stmt(i, conds):
        if i >= n:
            return i
        t, line = toks[i]
        if t == 'begin':
            i += 1
            if i < n and toks[i][0] == ':':               # begin : label
                i += 2
            while i < n and toks[i][0] != 'end':
                i = stmt(i, conds)
            return i + 1
        if t == 'if':
            chain = list(conds)
            while True:
                ids, ctext, j = paren(i + 1)
                chain = chain + [(ctext, toks[i][1], ids)]
                j = stmt(j, chain)
                if j < n and toks[j][0] == 'else':
                    if j + 1 < n and toks[j + 1][0] == 'if':
                        i = j + 1
                        continue
                    return stmt(j + 1, chain)
                return j
        if t in ('case', 'casez', 'casex'):
            ids, ctext, j = paren(i + 1)
            sel = conds + [(f"case ({ctext})", line, ids)]
            while j < n and toks[j][0] != 'endcase':
                lab, k = [], j
                while k < n and toks[k][0] != ':':
                    if toks[k][0] == '(':
                        _, _, k = paren(k)
                        continue
                    lab.append(toks[k])
                    k += 1
                arm = sel + [(' '.join(t for t, _ in lab) + ':', toks[j][1],
                              idents(lab))]
                j = stmt(k + 1, arm)
            return j + 1
        if t in ('endcase', 'end', 'else', 'endmodule'):
            return i + 1                                   # caller's business
        # --- a simple statement: consume to ';' ---------------------------- #
        j, lhs = i, None
        if re.match(r"^[A-Za-z_]", t) and t not in KEYWORDS:
            k = i + 1
            while k < n and toks[k][0] == '[':
                d = 0
                while k < n:
                    if toks[k][0] == '[':
                        d += 1
                    elif toks[k][0] == ']':
                        d -= 1
                        if d == 0:
                            k += 1
                            break
                    k += 1
            if k < n and toks[k][0] in ('=', '<='):
                lhs = t
        while j < n and toks[j][0] != ';':
            if toks[j][0] == 'begin':                      # unknown wrapper
                return stmt(j, conds)
            j += 1
        rhs = idents(toks[i:j])
        if lhs == stop_name:
            sites.append(StopSite(line, list(conds)))
        elif lhs is not None:
            assigns.setdefault(lhs, set()).update(x for x in rhs if x != lhs)
        return j + 1

    i = 0
    while i < n:
        j = stmt(i, [])
        i = j if j > i else i + 1
    return sites, assigns


# --------------------------------------------------------------------------- #
def run(core, verbose, gate=True, root=None):
    cfg = CORES[core]
    d = (root or ROOT) / cfg["dir"]
    for k in ("top", "biu", "eu"):
        if not (d / cfg[k]).exists():
            print(f"r7_lint: {d / cfg[k]} not found -- the lint CANNOT RUN")
            return 2

    def load(p):
        return strip_directives(strip_comments((d / p).read_text()))

    top_t, biu_t, eu_t = load(cfg["top"]), load(cfg["biu"]), load(cfg["eu"])
    incl = sorted(d.glob(cfg["eu_incl"]))
    const = constant_names([biu_t, eu_t, top_t]
                           + [load(p.name) for p in incl]
                           + [strip_comments(p.read_text())
                              for p in d.glob("*_ss_pkg.sv")]
                           + [strip_comments(p.read_text())
                              for p in d.glob("pla3_tables.svh")])

    biu_ports = module_ports(biu_t, cfg["biu_mod"])
    eu_ports = module_ports(eu_t, cfg["eu_mod"])
    biu_conn = instance_conns(top_t, cfg["biu_mod"])
    eu_conn = instance_conns(top_t, cfg["eu_mod"])

    # BIU -> EU nets: driven by a BIU output, read by an EU input.
    biu_out_nets = {}
    for port, ids in biu_conn.items():
        if biu_ports.get(port) == "output" and len(ids) == 1:
            biu_out_nets[ids[0]] = port
    eu_in_nets = set()
    for port, ids in eu_conn.items():
        if eu_ports.get(port) == "input":
            eu_in_nets.update(ids)
    # (net, BIU port).  The cone is walked from the PORT, because that is the
    # name the BIU's own drivers use; the NET is only what the top file calls
    # it, and the two differ (`halted_o` / `biu_halted`, `q_cnt_o` / `q_cnt`).
    crossing = sorted((net, port) for net, port in biu_out_nets.items()
                      if net in eu_in_nets)

    # --- THE ANTI-VACUITY CHECKS.  A lint that parses nothing PASSES, which is
    # this repo's most-repeated failure mode.  These make "I found nothing to
    # look at" an exit 2, never an exit 0. ---------------------------------- #
    for what, ok in (("BIU ports", biu_ports), ("EU ports", eu_ports),
                     ("BIU instantiation", biu_conn),
                     ("EU instantiation", eu_conn),
                     ("BIU->EU nets", crossing)):
        if not ok:
            print(f"r7_lint: parsed NO {what} -- the lint CANNOT RUN "
                  f"(this is exit 2, not a PASS)")
            return 2
    if biu_ports.get(cfg["ready"]) != "input":
        print(f"r7_lint: `{cfg['ready']}` is not an input of "
              f"{cfg['biu_mod']} -- the lint CANNOT RUN (exit 2)")
        return 2

    print(f"r7_lint: core={core}  {cfg['dir']}")
    print(f"  BIU -> EU nets: {len(crossing)}")

    cone = BiuCone(biu_t, const, cfg["ready"], biu_ports)
    carriers, viol_a, undeclared = {}, [], []
    for net, port in crossing:
        cp, un = cone.walk(port)
        if cp:
            carriers[net] = cp                 # keyed by the EU-side net name
            if port not in READY_CARRIER_EXCEPTIONS:
                viol_a.append((port, cp))
        elif un and port not in DECLARED_UNRESOLVED:
            undeclared.append((port, un))
        if verbose:
            tag = ("CARRIER" if cp else
                   ("unresolved" if un else "register-only"))
            note = ""
            if port in READY_CARRIER_EXCEPTIONS:
                note = "  [DECLARED exception]"
            elif port in DECLARED_UNRESOLVED and un:
                note = "  [DECLARED unresolved]"
            name = port if port == net else f"{port} (net `{net}`)"
            print(f"    {tag:<14} {name}{note}")

    print(f"\n  --- (a) live-READY carriers into the EU ---")
    print(f"  carriers found      : {len(carriers)} "
          f"({', '.join(sorted(carriers)) or 'none'})")
    print(f"  declared exceptions : "
          f"{', '.join(sorted(READY_CARRIER_EXCEPTIONS)) or 'none'}")
    base = root or ROOT
    src = str((d / cfg['biu']).relative_to(base))
    if viol_a:
        for net, paths in viol_a:
            line = cone.drv.get(net, ([], 0))[1]
            print(f"  VIOLATION {src}:{line}: `{net}` reaches the live "
                  f"`{cfg['ready']}` pin and is NOT declared")
            for p in paths[:3]:
                print(f"      chain: " + " <- ".join(p))
    else:
        print("  OK: no undeclared carrier")
    if undeclared:
        for net, un in undeclared:
            line = cone.drv.get(net, ([], 0))[1]
            print(f"  VIOLATION {src}:{line}: `{net}` reaches "
                  f"`{un[0][0]}`, which this walk cannot resolve, and is not "
                  f"in DECLARED_UNRESOLVED")
            print(f"      chain: " + " <- ".join(un[0][1]))

    # --- (b) ------------------------------------------------------------- #
    viol_b = []
    print(f"\n  --- (b) `{cfg['stop']}` under a live-READY condition ---")
    if not cfg["chain"]:
        print("  n/a: this core has no chain sources declared")
    else:
        eu_drv = dict(continuous_drivers(eu_t))
        for p in incl:
            for k, v in continuous_drivers(load(p.name)).items():
                eu_drv.setdefault(k, v)
        tainted = set(carriers)          # the exception is NOT excepted here
        # `via[x]` is the tainted signal x picked its taint up from -- kept so
        # the report can print the ACTUAL chain rather than re-deriving one.
        via = {}
        chain_sites, chain_assigns = [], {}
        for fn in cfg["chain"]:
            if not (d / fn).exists():
                continue
            sites, assigns = scan_chain(load(fn), cfg["stop"])
            chain_sites.append((fn, sites))
            for lhs, rhs in assigns.items():
                chain_assigns.setdefault(lhs, set()).update(rhs)
        edges = {name: set(idents(toks)) for name, (toks, _) in eu_drv.items()}
        for lhs, rhs in chain_assigns.items():          # the chain's own vars
            edges.setdefault(lhs, set()).update(rhs)
        changed = True
        while changed:
            changed = False
            for name, srcs in edges.items():
                if name in tainted:
                    continue
                hit = srcs & tainted
                if hit:
                    tainted.add(name)
                    via[name] = sorted(hit)[0]
                    changed = True
        print(f"  tainted signals     : {len(tainted)} "
              f"({', '.join(sorted(tainted))})")
        nsites = sum(len(s) for _, s in chain_sites)
        print(f"  `{cfg['stop']}` sites      : {nsites} in "
              f"{', '.join(cfg['chain'])}")
        if nsites == 0:                      # the same anti-vacuity rule
            print(f"  r7_lint: found NO `{cfg['stop']}` assignment in the "
                  f"chain sources -- check (b) CANNOT RUN (exit 2)")
            return 2
        for fn, sites in chain_sites:
            for s in sites:
                hits = [(ctext, cline, sorted(set(ids) & tainted))
                        for ctext, cline, ids in s.conds
                        if set(ids) & tainted]
                if hits:
                    viol_b.append((fn, s, hits))
        if viol_b:
            for fn, s, hits in viol_b:
                rel = f"{cfg['dir']}/{fn}"
                print(f"  VIOLATION {rel}:{s.line}: `{cfg['stop']}` is gated "
                      f"by a live-READY condition")
                for ctext, cline, names in hits:
                    ct = ctext if len(ctext) < 90 else ctext[:87] + "..."
                    print(f"      {rel}:{cline}: `{ct}`")
                    for nm in names:
                        print(f"        carrier chain: "
                              + " <- ".join(_chain_to(nm, via, carriers)))
        else:
            print("  OK: no `stop` sits under a live-READY condition")

    bad = bool(viol_a) + bool(undeclared) + bool(viol_b)
    if not gate:
        print(f"\n=== r7_lint [{core}]: "
              f"{'CLEAN' if not bad else 'WOULD FAIL'}  (INFORMATIONAL ONLY -- "
              f"this core is archived and is never gated)")
        return 0
    print(f"\n=== r7_lint: {'PASS' if not bad else 'FAIL'}   "
          f"({len(viol_a)} undeclared carrier(s), "
          f"{len(undeclared)} undeclared unresolved, "
          f"{len(viol_b)} `{cfg['stop']}` site(s))")
    return 1 if bad else 0


def _chain_to(name, via, carriers):
    """The chain the taint ACTUALLY came down, `name` back to `ready`."""
    path, seen = [name], {name}
    cur = name
    while cur not in carriers:
        nxt = via.get(cur)
        if nxt is None or nxt in seen:
            break
        path.append(nxt)
        seen.add(nxt)
        cur = nxt
    if cur in carriers:
        path.append("ready (the LIVE pin)")
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--core", default="ucore", choices=sorted(CORES))
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="print every BIU->EU net's verdict")
    ap.add_argument("--root", default="",
                    help="lint a checkout somewhere else (a worktree at an "
                         "older commit, say).  The DECLARED lists are this "
                         "file's, which is the point: they travel with the "
                         "gate, not with the tree being gated.")
    a = ap.parse_args()
    return run(a.core, a.verbose, gate=(a.core == "ucore"),
               root=Path(a.root).resolve() if a.root else None)


if __name__ == "__main__":
    sys.exit(main())
