# Fuzz campaign rollup (task #29)

Campaigns: mc1

Total seeds: **7**

## Verdict x tier x waits-class

| tier | waits | SUCCESS | KNOWN_ACCEPTED | TIMING | FUNCTIONAL | QUARANTINE | n |
|---|---|---|---|---|---|---|---|
| raw | wrand | 0 | 0 | 1 | 0 | 0 | 1 |
| soup | w0 | 2 | 0 | 0 | 0 | 0 | 2 |
| soup | w2 | 0 | 0 | 1 | 0 | 0 | 1 |
| soup | wrand | 0 | 0 | 3 | 0 | 0 | 3 |

## Rule hits (zero-hit = stale)

- 8080-gap: 0  <-- STALE (zero hits)
- cadence: 0  <-- STALE (zero hits)
- lea-mod3: 0  <-- STALE (zero hits)

## Signatures

- distinct: 5; in-ledger: 0; **NEW (not in ledger): 5**

## QUARANTINE (0)


## Coverage

- mc1: 7 seeds, 241 instrs, 28 forms, 133 opsigs, 15 prefix-combos, 7 qfill-buckets

## Escalation-relevant seeds (0)

