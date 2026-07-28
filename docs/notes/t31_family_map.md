# Task #31 — in-image FUNCTIONAL divergences: family map (boundary report)

Scope: the 806 FUNCTIONAL divergences in mc1 (10,003 seeds). This is the
family-map boundary — clusters, counts, and minimization status — BEFORE the deep
root-cause pass. Tools: `sw/t31_family_map.py` (character clustering),
`sw/t31_root_signal.py` (transaction-based root signal).

## 1. Divergence-character families (robust: describes which columns differ)

Clustered by sub-class x primary differing column x w0/waited. Character-based
counts are robust (they just describe the trace); the mechanism ROUTING in §2
requires minimization to confirm.

| sub-class | n | notes |
|---|---|---|
| done_mismatch | 542 | soup fall-through/desync: real & sim disagree on reaching the done marker |
| func:W (write divergence) | ~114 | incl. 59 with a MEMW/IOW data-value mismatch (`+dataval`) |
| func:R (read divergence) | ~101 | 79 raw, 22 soup |
| func:INTA | 29 | interrupt-acknowledge context |

(full character table: `python3 sw/t31_family_map.py` — 34 leaf families.)

## 2. Root-signal routing (best-effort; minimization confirms)

Transaction-T1-address analysis (`t31_root_signal.py`) separates root mechanism.
Trace-only separation is INHERENTLY imprecise here — address multiplexing (T2/T3
carry segment/status on the upper `ad_addr` bits), passive out-of-image parks,
and txn-boundary ambiguity mean escape-vs-genuine cannot be fully resolved from
statistics. That is precisely what minimization resolves. Best-estimate routing:

| root signal | task | n | mechanism |
|---|---|---|---|
| **prefetch_split** | **#33 (cross-link)** | **117** | qs/rd_n queue-phase split under waits; k=15 heads it |
| escape-consequence | #32 | **dominant** (bracket 27–689) | a leg far-jumps out of the 64K image and the paths split |
| value_bug (same in-image addr, diff data) | #31 | 1 confirmed (k=6475) + a ~37-seed func:W+dataval candidate pool | genuine functional value divergence |
| addr_split (both in-image) | #31 | few | in-image control-flow split |
| other / unresolved | review | ~660 | fb lands on passive/boundary rows — needs per-seed minimization |

## 3. CROSS-FAMILY COLLAPSE (the predicted consolidation — confirmed pattern)

The escape meta-finding pattern repeats. Two mechanisms account for the great
majority of the 806, spanning ALL four apparent sub-classes:

1. **Escape (-> #32):** the dominant root. A raw or strict-soup program wanders
   out of the 64K image; the chip and fabric core then take different
   out-of-image paths. Shows up as func:R (real reads out-of-image feedthrough),
   func:W (real writes out-of-image), func:INTA, AND done_mismatch (real wanders
   past / never reaches the done marker). Bracketed 27–689 by trace stats;
   minimization needed for the exact split, but it is clearly the largest slice.
2. **Prefetch/queue split (-> #33 cross-link): 117, one mechanism, 5 sub-classes.**
   A qs/rd_n queue-phase divergence under wait states appears across
   done_mismatch (50), func:W (26 waited + 12 w0), func:R (21 waited + 7 w0), and
   func:INTA (1). k=15 (the earlier priority read) heads it. This is cadence/
   prefetch territory — cross-link to task #33, do NOT fix ad hoc.

**Residual genuine in-image functional-value bugs appear to be a SMALL pool**
(single-digit confirmed so far; the func:W+dataval candidates mostly have
out-of-image write addresses = escapes). Strong hypothesis pending minimization:
task #31 largely COLLAPSES into #32 (escape) + #33 (prefetch-split), with a small
genuine-value-bug residue. This mirrors the escape meta-finding exactly.

## 4. Minimization status

TB-first replay (chip capture frozen as oracle; TB = same RTL as the fabric core)
reproduces faithfully for a SUBSET (e.g. k=969 raw: chip-vs-TB func:R@5 fb=369,
matches the board), but some seeds show an EARLY chip-vs-TB startup delta
(k=15, k=226 diverge at row ~11 in TB vs 416/499 on board) — a chip-vs-TB reset/
startup difference (the reason the bank stores chip-vs-TB verdicts separately).
So: **TB-first where the round-trip is clean; board legs (chip-vs-fabric, chip =
oracle) where a startup delta masks the real divergence.** Both are cheap
(~56 ms/board-leg; TB replay is board-free).

Proposed minimization targets (one rep per candidate family), board-bounded:
- **k=15** — prefetch_split head (-> #33 cross-link). Board legs (TB startup delta).
- **k=6475** — the confirmed value_bug candidate (-> #31). TB-first.
- **k=226 / k=204** — func:W / func:R candidates. TB-first, board fallback.
- **k=410 / k=444 / k=169** — the cleanest w0 reps. TB-first.

## 5. Recommendation at this boundary

Given the cross-family collapse, I recommend the deep pass MINIMIZE the two
mechanism heads first — one escape rep and k=15 (prefetch-split) — to CONFIRM the
collapse, before enumerating the small genuine-value-bug residue. If confirmed,
task #31's real deliverable is the small residue (a handful of genuine functional
bugs), with the bulk correctly routed to #32 (escape containment) and #33
(cadence/prefetch). Awaiting review before the root-cause pass.

---

# COLLAPSE-CONFIRMATION BOUNDARY (task #31, mechanism heads minimized)

Both mechanism heads reproduced; the collapse is CONFIRMED. Genuine value-bug
residue precisely enumerated (`sw/t31_residue.py`).

## Head 1 — prefetch/queue split (-> task #33): k=15 board-reproduced

Reproduced k=15 on the board (chip use_core=0 vs fabric use_core=1, wrand
seed=54219 wmax=2). Verdict FUNCTIONAL/done_mismatch, first_bad=695 (character
identical to the campaign's 416; the exact row shifts with compose/wait detail).
At the split BOTH legs fetch code at the SAME in-image address 0x51c, but the
chip has qs=1/rd_n=0 (queue fetch in progress) while the fabric has qs=0/rd_n=1 -
a queue-phase divergence at a HEAVILY-WAITED in-image code fetch.

**#33 law-fitting datapoint (first seed of the dataset):**
`{first_bad:695, fidx:46, occ:0, tw:7, cum_wait:350, parity:0, kind:CODE,
chip:{qs:1,rd_n:0}, fabric:{qs:0,rd_n:1}}` - i.e. queue EMPTY (occ=0), a 7-wait
fetch, even wait-parity. Board oracle used (TB shows the startup delta). This
moves to task #33's dataset as its seed; NOT fixed here.

## Head 2 — escape (-> task #32): board-confirmed archetype

The escape mechanism is already board-confirmed (k=16, the open_bus archetype:
deterministic chip-vs-core divergence in out-of-image/open-bus space). The
FUNCTIONAL escape families are the same root - a raw or strict-soup program
wanders out of the 64K image and the legs take different out-of-image paths.
These formally move to task #32's ledger as its impact case.

## Genuine value-bug residue: 22 seeds (the real #31 deliverable)

Discriminator (`t31_residue.py`): IDENTICAL code-fetch stream in both legs (same
execution path) + a differing store DATA value at a shared in-image address =>
neither escape (paths would diverge) nor prefetch split (fetch stream identical).
This isolates the genuine EU-compute/store-path divergences from the escape/
desync bulk. Result: **22 of 806** FUNCTIONAL. Sub-clusters:

1. **chip=0x3fe0 cluster (9 seeds)** - all soup, func:W around PC ~0x510,
   identical code path, the CHIP (oracle) writes a CONSTANT 0x3fe0 while the
   fabric writes program-varying values. One mechanism. Needs root-cause to
   decide real-store-path-bug vs undefined/uninitialised-source value (the
   constant chip value hints at a defined chip behaviour the core mis-computes,
   but could be an undefined-source read). k=862/2398/4024/6407/7542/9124/9312/
   9440 (+1).
2. **k=6475 - the clean distinct value bug (ROOT-CAUSE FIRST).** raw, wrand
   wmax=2. A single MEMW to in-image 0x3efe: chip stores 0x469c, fabric stores
   0x27cc, and EVERY other write in the whole 4063-row trace (rows 484-4019) is
   byte-identical in both legs. A perfectly isolated store-value divergence - the
   most LEA-like find. This is a real EU-compute or store-path bug.
3. **~12 others** - mixed raw/soup; per-seed root-cause needed (some may fold
   into the 0x3fe0 mechanism or be their own).

## Collapse verdict + routing

806 FUNCTIONAL = escape (dominant, -> #32) + prefetch/queue split (117, -> #33,
k=15 datapoint seeded) + a SMALL genuine value-bug residue (22, -> #31). The
escape meta-finding pattern holds; #31's real work is the 22-seed residue, which
itself collapses toward a 9-seed 0x3fe0 family + k=6475 + a dozen singles.

Routing on this confirmation: escape families -> #32 ledger; prefetch_split (117)
-> #33 dataset (k=15 instrumented datapoint is its seed); #31 proceeds on the 22
residue - **root-cause k=6475 first** (confirmed clean value bug), then the
0x3fe0 cluster (9-seed family). Root-cause report per confirmed bug before fixes,
as established. Awaiting review before the root-cause pass.
