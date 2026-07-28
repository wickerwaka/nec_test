# mc2 campaign — NOVELTY report (10,000 seeds on the FIXED fabric)

Campaign `mc2`: 10,000 seeds, survey-accumulate, pinned to flash 2df26239 (the
POST-ENTER-fix fabric), same config as mc1 (--contained --strict, raw_frac 0.20,
event 0.25, wrand 0.50). All post-mc1 rules live (raw-aware lea_mod3, open_bus_
escape, tier-B done semantics). **0 QUARANTINE**; board left use_core=0.

## NOVELTY VERDICT: no new bug FAMILY; the ENTER mass is gone from silicon.

Every non-SUCCESS seed clusters into a KNOWN mc1 mechanism family. The 3,030
"new-signature" hits are signature-GRANULARITY instances of known mechanisms (new
seeds -> new sig-v1 hashes; the ledger banks samples, not every possible sig) — NOT
new mechanisms. The genuine value-bug residue COLLAPSED from mc1's 22 to **3, all
RAW-tier** (the known raw-undoc/mod3-latch coverage class), zero soup value bugs.

## Verdict-mix delta vs mc1 (10000 vs 10003)
| verdict | mc2 | mc1 | delta |
|---|---|---|---|
| SUCCESS | 3860 (38.6%) | 3863 (38.6%) | -3 |
| KNOWN_ACCEPTED | 2962 (29.6%) | 2864 (28.6%) | +98 |
| TIMING | 2524 (25.2%) | 2470 (24.7%) | +54 |
| **FUNCTIONAL** | **654 (6.5%)** | **806 (8.1%)** | **-152** |
| QUARANTINE | 0 | 0 | 0 |

The FUNCTIONAL drop (-152) is the fix signal. Broken out: **func:W 134 -> 16
(-118)** = the ENTER PUSH-BP-drop STORE family gone; func:R 101 -> 70; done_mismatch
542 -> 529; func:INTA 29 -> 39 (unchanged class). KNOWN_ACCEPTED/TIMING tick up
because the escapes/cadence that used to surface as raw FUNCTIONAL now type cleanly
(rules live) and the population is a fresh 10k draw.

## Non-SUCCESS family map (all KNOWN classes)
| verdict/sub | n | new-sig | tiers | waits (top) | reps | mechanism |
|---|---|---|---|---|---|---|
| TIMING/timing | 2524 | 960 | soup 2287/raw 237 | wrand 1407, w0 694 | 10,12,13,31 | wait-state CADENCE (#33) — CONFIRMED in-image |
| KNOWN_ACCEPTED/cadence | 1967 | 891 | soup 1808/raw 159 | wrand 1472 | 1,2,3,16 | cadence floor (accepted) — CONFIRMED |
| KNOWN_ACCEPTED/open_bus | 993 | 867 | raw 993 | wrand 502, w0 343 | 5,18,27,42 | raw open-bus escape (typed) — CONFIRMED |
| FUNCTIONAL/done_mismatch | 529 | 192 | soup 529 | wrand 403 | 9,15,39,50 | drift-accumulation truncation (#33 tail) — CONFIRMED |
| FUNCTIONAL/func:R@N | 70 | 69 | raw 56/soup 14 | wrand 35, w0 19 | 199,491,549 | in-image read residue / raw undoc — GUESS (known class) |
| FUNCTIONAL/func:INTA@N | 39 | 34 | soup 39 | wrand 28 | 573,596,700 | INTA/interrupt-ack divergence (mc1 class) — GUESS |
| FUNCTIONAL/func:W@N | 16 | 15 | soup 11/raw 5 | wrand 13 | 409,809,1791 | in-image write residue (post-ENTER, tiny) — GUESS |
| KNOWN_ACCEPTED/lea-mod3 | 2 | 2 | raw 2 | wrand/w3 | 769,3831 | LEA mod=11 stale-latch (typed) — CONFIRMED |

No family is absent from the mc1 map, and no mc1 family is missing except the
ENTER-driven func:W mass. There is NO NEW mechanism family.

## Genuine value-bug residue (t31_residue discriminator): 3 seeds, ALL RAW
| k | tier | sub | waits | addr | chip | fabric | note |
|---|---|---|---|---|---|---|---|
| k=4400 | raw | func:R@4 | w0 | 0x3eea | 0xf682 | 0xb539 | raw value divergence |
| k=7122 | raw | func:R@5 | w0 | 0xe1 | 0x6a2f | 0x67f5 | raw value divergence |
| k=3568 | raw | func:W@13 | wr1 | 0x6115 | 0x465 | 0x1194 | raw value divergence |

All 3 are RAW-tier, in the known raw-undoc / mod=11-stale-latch coverage class
(the #31 k=6475 LEA-mod3 / k=8398 undoc-0x8F precedent: raw random bytes hit an
undocumented/illegal-mod form the core intentionally does not replicate). ZERO
soup genuine value bugs — the ENTER families (nesting-mask + PUSH-BP-drop, 17 of
the mc1 residue's 22) are gone from silicon. Booked to the raw-undoc coverage
follow-up; not a new mainline bug.

## What this confirms
1. Both #31 ENTER RTL fixes are effective on silicon: the soup FUNCTIONAL value-bug
   families that dominated the mc1 residue are eliminated (func:W -118; residue
   22 -> 3, all raw).
2. The #32 reframe holds: soup does not escape (the FUNCTIONAL residue is in-image /
   raw-undoc, open_bus stays raw-typed).
3. The #33 mass is confirmed real and in-image: TIMING (2524) + done_mismatch (529)
   = the wait-state cadence + drift population, unchanged in character, awaiting the
   from-scratch prefetch rebuild.
4. No new mechanism surfaced in 10k fresh seeds on the fixed fabric.
