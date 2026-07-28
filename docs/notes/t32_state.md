# Task #32 — escape containment (HLT-fence) — durable state

Goal: the ESCAPE phenomenon is ~37% of mc1 non-SUCCESS (open_bus 1018 + w0-TIMING
soup-escapes ~699 + fall-through done_mismatch ~542). Mechanism: compose()'s NOP
(0x90) fill lets wandering/escaping execution GLIDE out of the loaded program and
(on the chip) into out-of-image open-bus feedthrough, where chip and core diverge.
Fix: fill non-program/non-reserved image space with HLT (0xF4) so a wander HALTS
DETERMINISTICALLY inside the 64K image — both legs quiet at the same fence row =
classifiable (SUCCESS via the existing runaway_both path), no open-bus wander.

## Design (implemented)
- **Soup-only**, opt-in `fence` cfg axis (default OFF). Raw KEEPS 0x90 + the
  open_bus_escape rule (raw payload-mode relies on the 0x90 NOP surround and
  actively scrubs 0xF4 to avoid armed-wake timeouts — gen_raw.py:13-15,60-67).
- **Injection** (minimal, g-dict-carried):
  - `derive_case` (fuzz_campaign.py): new `fence` axis, added to the hashed core
    (fenced campaigns are cfg-distinct).
  - `build`: `g["fill"] = 0xF4 if (tier!="raw" and cfg["fence"]) else 0x90`.
  - `check_seq.compose`: forwards `fill=g.get("fill", 0x90)`.
  - `testimage.compose` default stays 0x90 → every non-fuzz caller byte-identical.
- **Bank-safe**: fence OFF => existing images byte-identical (VERIFIED: banked soup
  k=2218 regenerates to the SAME image_sha256; raw+fence still 0x90). So the just-
  re-frozen fuzz bank does NOT gen-drift. Making the fence the SOUP DEFAULT (the
  standing improvement) requires flipping the default + a bank re-freeze (board
  re-capture of soup chip_rows for fenced images) — a COORDINATED FOLLOW-UP, not
  done here (respects the just-completed re-freeze; needs coordinator go).
- **IVT**: uniform F4 fill is self-consistent — an interrupt vectoring through an
  empty (F4) IVT slot targets linear (0xF4F4<<4)+0xF4F4 = mirrored 0x4434, also
  F4 => HALT. So the fence contains interrupt-vectored escapes too (a bonus the
  NOP fill lacks). Placed IVT entries (evt tests) overlay as before.
- **gen_soup self-contained** (verified): forward branches clamp to the program
  (`tgt = min(idx+1+skip, n)`, gen_seq.py) and it falls through directly to the
  stub — NO reliance on fill glide. So the fence only affects genuine escapes.
- **Classifier: NO change needed.** HALT (bs=3) is a first-class functional event
  (fuzz_classify.py:205-206); both legs reaching HALT at the same position match ->
  no func_mismatch; with no done marker + clean cycle diff -> SUCCESS sub
  "runaway_both" (fuzz_classify.py:429-430,458-459; soup=tier "A"). Divergence
  BEFORE the fence -> func_mismatch/timing = real signal. open_bus_escape is
  tier-B/raw-only (fuzz_accept.py:354) -> soup fence never touches it.

## Validation
- **done-rate PRESERVED** (TB, 40 strict-soup w0): done OFF 25 == ON 25,
  done-changed 0 — the fence does NOT break normal completion.
- **TB escape proxy** (sw/t32_pilot.log, running): out-of-image test-space escape
  fetches OFF vs ON. NOTE the TB mirrors 64K->1MB and is fabric-only, so it cannot
  reproduce the chip-vs-core open-bus escape directly; the DEFINITIVE escape-
  reduction is the BOARD slice (chip-vs-core verdict mix).
- **suites/lints**: golden suites are -DV30_BACKDOOR (check_core, never
  testimage.compose) -> unaffected. Fence OFF => bank/lints byte-identical. (to
  prove-run.)
- **BOARD slice (~200 hw-ab)**: pending — the real escape-reduction + verdict-mix
  measurement (fenced soup, chip vs core: escapes now both-halt = SUCCESS).

## Files
sw/fuzz_campaign.py (derive_case fence axis + build g["fill"]), sw/check_seq.py
(compose fill forward). No RTL, no classifier change.

## MECHANISM ANSWER (the pilot null result) — SOUP DOES NOT ESCAPE

The TB pilot showed IDENTICAL escape fetches OFF/ON (fence never executes). Root-
caused by tracing the pilot's escaping seeds:

- **The pilot's escapers were RAW, not soup.** The pilot ov `{force_contained,
  strict}` did NOT force the tier; derive_axes draws ~20% RAW regardless. k=3/16/17
  (traced) are all tier=raw (forms=['raw']). Raw escapes via open-bus feedthrough —
  the KNOWN phenomenon, already typed by the tier-B open_bus_escape rule; raw is
  intentionally fence-exempt (payload mode needs the 0x90 surround, scrubs 0xF4).
- **Forced tier=soup: 0/50 escape. Forced tier=raw: 21/48 escape (4604 fetches).**
- **Board captures confirm**: soup TIMING/FUNCTIONAL 248/250 have NEITHER leg in
  test-space out-of-image; soup done_mismatch 171/172 neither; raw non-SUCCESS
  215/298 (72%) escape. SOUP is fully contained (forward-branch-clamp + fall-through
  to the stub).
- **The survey's "699 w0-TIMING soup-escapes" was a MISCHARACTERIZATION.** The rep
  seeds (mc1/28,34,35,49,51,65) show chip/fab out-of-image = 0 in test space; the
  only "out-of-image" fetches are the 4 RESET-STUB fetches (linear 0xFFFF0, present
  on BOTH legs in EVERY image). Counted broadly (>=0x10000) that reads as "chip
  out-of-image" but it is the boot vector, not an escape. Those soup families are
  IN-IMAGE cadence (TIMING) / done-marker (done_mismatch) divergences — the REAL
  signal, not escapes.

## RECOMMENDATION (report-first; nothing further implemented)
The HLT-fence premise is MOOT for soup: soup does not escape, so the fence has
nothing to intercept (hence the null pilot). NEITHER coordinator option applies —
there is NO generator containment gap (soup IS contained), and it is NOT irreducible
wild-EA escape (soup does not escape). The ~37% "escape signal lever" was a survey
artifact conflating (a) the RAW open-bus escape (~1018, already typed) with (b) a
mischaracterized soup in-image TIMING family (the #33 wait-state cadence signal)
and done_mismatch. Recommended:
1. DO NOT implement either fence-fallback; correct the escape accounting.
2. KEEP the fence plumbing (harmless, opt-in, default off, bank-safe) for possible
   future raw experiments; it is currently unused.
3. The real soup non-SUCCESS is REAL signal to root-cause, not contained: soup
   TIMING (2257) -> #33 wait-state cadence (#1 priority); soup FUNCTIONAL (686) ->
   value-bug residue (the #31 mc1 subset was this family).
4. Raw untyped residue (raw TIMING 213 + FUNCTIONAL 120) = raw escapes the open_bus
   rule refuses (divergence-before-escape-point) + real raw diffs — a raw-side
   coverage question, separate from soup and from the fence.
