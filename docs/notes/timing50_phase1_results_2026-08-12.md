# TIMING50 PHASE 1 — RESULTS

**Branch `master`.  Census + pre-registration `6eee1c0b67`
(`timing50_census_2026-08-12.md`), committed BEFORE any edit here.**
**OFFLINE ONLY.  NO BOARD, NO FLASH.**  `flash_log.jsonl` untouched, no socket
command issued, no Codex consulted, no nested task spawned.

The census's §0 records the **CE/CE_HALF portability contract** (user ruling,
2026-08-12) verbatim.  It governs every derivation here.

---

## §0 AMENDMENT A-1 — REGISTERED BEFORE THE BUILDS THAT SCORE IT

**P-3 as pre-registered** (census §7.3) was: *exclude `t1_half2` from the
uniform 4/3 collection, and add `-setup 2 -hold 1` into it and `-setup 3
-hold 2` out of it.*

**Implementing it exposed a THIRD arc of the same defect class, and A-1 adds
it to P-3's scope**: the **E-1 observation multicycle's `-from` collection was
also `$v30u_regs`**, so it too included `t1_half2`.

**The derivation, from the contract:** E-1's whole argument is written about
registers that **launch at a `ce`** — "the core launches its pins at E0".  A
`ce_half`-launched flop reaches the observation registers **half a cycle
later**, so the same reasoning grants it strictly *less*, never the same.  And
`t1_half2` does reach them: `t1_half2` → `ad_oe_data` → `ad_o` → the pads →
`ad_in_q`.

**A-1: E-1's `-from` becomes `$v30u_ce`.**  It is a **tightening**, in the safe
direction, and it is the same class of defect as the 4/3 split — an exception
written before the core's two enable phases were separated, silently reaching
the phase it was never derived for.

**A-1 is scored under P-3's bars, unchanged**, and it is registered here in a
commit that precedes every build in §2.

---

## §1 THE THREE ITEMS, AS DISPOSITIONED

| item | brief's form | **as landed** |
|---|---|---|
| **1** | SignalTap OFF for G6/flash, behind a flag for board debug | **LANDED as POLICY** — and MEASURED at **exactly zero** effect on the bitstream (§3) |
| **2** | E-1 observation multicycle `-setup 2` → `-setup 3` | **WITHDRAWN by the ruling** — the premise was `div/2 − 1`; under the contract the guaranteed window is **1 period** (census §5) |
| **3** | "the negedge modelling correction" | **BECAME A CORRECTNESS FIX, and it is the sitting's real result** (§4) — the tree's uniform 4/3 was **optimistic by two periods** on the `t1_half2` arc |

---

## §2 THE MEASUREMENTS

PLACEHOLDER-2

---

## §3 P-1 — THE SIGNALTAP POLICY

PLACEHOLDER-3

---

## §4 P-3 + A-1 — THE `t1_half2` CARVE-OUT

PLACEHOLDER-4

---

## §5 THE ZERO-BEHAVIOUR-CHANGE LADDER

PLACEHOLDER-5

---

## §6 THE NEW BAND, WHAT NOW BINDS, AND THE PHASE-2 RECOMMENDATION

PLACEHOLDER-6
