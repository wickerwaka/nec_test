# Task #31 residue — per-bug root-cause reports

Root-cause of the 22-seed genuine value-bug residue (`sw/t31_residue.py`), one
entry per confirmed bug. Fixes only after coordinator review, per family.

## k=6475 — the LEA mod=11 stale-EA latch, in a RAW seed (NOT a new bug)

**Verdict:** raw, wrand wmax=2. A single MEMW to in-image 0x3efe: chip stores
0x469c, fabric 0x27cc; every other write in the 4063-row trace is byte-identical.

**Root cause (hand-decoded along the executed path):**
- Execution runs the register-preamble at 0xff00 (`MOV DI,0x9465` among the reg
  loads) then far-jumps to 0:0x500 and runs linearly.
- At **PC 0x502 the instruction is `8d fd` = LEA DI, (modrm mod=11, rm=101)** —
  an ILLEGAL register-form LEA. This is the **task #30 stale-EA-latch class**:
  the chip loads its stale EA-offset latch into the dest reg (DI); the behavioural
  core reproduces this exactly only in moffs contexts, residue otherwise.
- DI is written by NOTHING else before the `57` = **PUSH DI at PC 0x51d**, which
  stores DI to SP-2 = 0x3efe. So the push exposes the latch: chip DI = 0x469c
  (stale EA latch), fabric DI = 0x27cc (core residue model). The arch diff is
  CONFINED to DI (the LEA dest) - exactly the `lea_mod3` accept criterion.

**Why it surfaced as FUNCTIONAL (not KNOWN_ACCEPTED/lea_mod3):** the `lea_mod3`
accept rule is **soup-only** - it needs the arch_dump (12-register store stub)
AND the `lea_mod3_pos` provenance, both produced by gen_soup. gen_raw emits none
of that, so a raw seed that RANDOMLY contains an LEA mod=11 (0x8d + a mod=11
modrm from the random byte stream) hits the known residue and is not covered ->
surfaces as a FUNCTIONAL value divergence. This is a **classification/coverage
gap, NOT a new RTL bug and NOT a regression** of the task #30 fix (the core no
longer hangs; it loads its residue value exactly as task #30 designed).

**Proposed disposition (NO RTL change):** extend LEA-mod=11 residue coverage to
raw tier. Options, in preference order:
1. **Raw-aware lea_mod3 acceptance** - detect an executed LEA mod=11 in a raw
   seed (scan the seed / executed stream for 0x8d with a mod=11 modrm at an
   instruction boundary) and accept iff the divergence is confined to that LEA's
   dest register (the same strict fail-safe as the soup rule). Needs a raw-path
   provenance/confirmation that does not rely on the arch_dump.
2. **Scrub LEA mod=11 in gen_raw** - neutralise 0x8d+mod=11 in the raw scrub pass
   (like the existing pair0f/halt/poll scrubs), so raw seeds never exercise the
   known residue. Simpler, but reduces raw breadth over a known class.
3. Book raw LEA mod=11 as an explicitly accepted static class.

Recommend (1) if a robust raw-side LEA-mod=11 confirmation is cheap, else (2).

**Sub-family sizing (linear ilen decode of the executed payloads):** k=6475 is
NOT a singleton - a small **raw mod=11 stale-latch sub-family** exists (the
register-form of the mem-only ops, all task #30 class):
- **k=6475** LEA (0x8d) mod=11 -> DI  (hand-verified)
- **k=3075** LDS (0xc5) mod=11 -> DI  (linear-decode; needs hand-confirm)
- **k=8398** BOUND (0x62) mod=11 -> DX (linear-decode; needs hand-confirm)

Caveat: k=3075/k=8398 are heuristic (linear decode assumes in-order flow). Note
that task #30 characterised BOUND/LES/LDS mod=11 as HALTing on BOTH chip and core
(park correct) - so if k=3075/k=8398 genuinely produce a VALUE divergence rather
than a park, that either contradicts the task #30 whitelist (a residue path the
whitelist missed) or the linear decode mis-identified the store source. Hand-
confirm both before the disposition; the fix in either case is raw-tier coverage
of the mod=11 stale-latch class, sized ~3 seeds (not 22).

So the value-bug residue partly COLLAPSES again: ~3 seeds are the known task #30
mod=11 stale-latch class (raw coverage gap), leaving the 0x3fe0 soup cluster (9,
a distinct MOV BP,0x3fe0 + ENTER/stale-latch mechanism - decode in progress) and
~10 singles for the remaining root-cause pass.
