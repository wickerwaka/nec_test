# Fuzz campaign rollup (task #29)

Campaigns: t30-brkem, t30-raw

Total seeds: **1200**

## Verdict x tier x waits-class

| tier | waits | SUCCESS | KNOWN_ACCEPTED | TIMING | FUNCTIONAL | QUARANTINE | n |
|---|---|---|---|---|---|---|---|
| raw | w0 | 132 | 0 | 176 | 103 | 0 | 411 |
| raw | w1 | 18 | 9 | 11 | 19 | 0 | 57 |
| raw | w2 | 12 | 12 | 13 | 5 | 0 | 42 |
| raw | w3 | 15 | 15 | 12 | 18 | 0 | 60 |
| raw | wrand | 96 | 141 | 122 | 115 | 0 | 474 |
| soup | w0 | 74 | 81 | 1 | 0 | 0 | 156 |

## Rule hits (zero-hit = stale)

- 8080-gap: 81
- cadence: 177
- lea-mod3: 0  <-- STALE (zero hits)

## Signatures

- distinct: 809; in-ledger: 809; **NEW (not in ledger): 0**

## Drift (accepted-TIMING outlier tripwire)

- accepted waited seeds with drift: 177; |final_off| p90 = 7; top-decile outliers: 21 (review for floor over-acceptance)

## QUARANTINE (0)


## Coverage

- t30-brkem: 200 seeds, 8772 instrs, 31 forms, 436 opsigs, 30 prefix-combos, 7 qfill-buckets
- t30-raw: 1000 seeds, 1000 instrs, 1 forms, 313 opsigs, 8 prefix-combos, 7 qfill-buckets

## Escalation-relevant seeds (103)

- t30-brkem/3 [w0-functional]: FUNCTIONAL/func:R@27
- t30-brkem/7 [w0-functional]: FUNCTIONAL/func:R@42
- t30-brkem/13 [w0-functional]: FUNCTIONAL/func:R@7
- t30-brkem/22 [w0-functional]: FUNCTIONAL/func:R@91
- t30-brkem/33 [w0-functional]: FUNCTIONAL/func:R@9
- t30-brkem/36 [w0-functional]: FUNCTIONAL/done_mismatch
- t30-brkem/94 [w0-functional]: FUNCTIONAL/func:R@15
- t30-brkem/137 [w0-functional]: FUNCTIONAL/func:R@59
- t30-brkem/148 [w0-functional]: FUNCTIONAL/func:R@39
- t30-brkem/180 [w0-functional]: FUNCTIONAL/func:R@118
- t30-raw/2 [w0-functional]: FUNCTIONAL/func:R@22
- t30-raw/12 [w0-functional]: FUNCTIONAL/func:R@17
- t30-raw/22 [w0-functional]: FUNCTIONAL/func:R@246
- t30-raw/27 [w0-functional]: FUNCTIONAL/func:R@98
- t30-raw/34 [w0-functional]: FUNCTIONAL/func:R@39
- t30-raw/36 [w0-functional]: FUNCTIONAL/func:R@131
- t30-raw/65 [w0-functional]: FUNCTIONAL/func:R@3
- t30-raw/82 [w0-functional]: FUNCTIONAL/func:R@1
- t30-raw/94 [w0-functional]: FUNCTIONAL/func:R@56
- t30-raw/98 [w0-functional]: FUNCTIONAL/func:R@10
- t30-raw/99 [w0-functional]: FUNCTIONAL/func:R@14
- t30-raw/118 [w0-functional]: FUNCTIONAL/func:INTA@43
- t30-raw/125 [w0-functional]: FUNCTIONAL/func:R@21
- t30-raw/129 [w0-functional]: FUNCTIONAL/func:R@37
- t30-raw/141 [w0-functional]: FUNCTIONAL/func:W@15
- t30-raw/153 [w0-functional]: FUNCTIONAL/func:R@110
- t30-raw/155 [w0-functional]: FUNCTIONAL/func:INTA@29
- t30-raw/171 [w0-functional]: FUNCTIONAL/func:INTA@166
- t30-raw/175 [w0-functional]: FUNCTIONAL/func:R@41
- t30-raw/230 [w0-functional]: FUNCTIONAL/func:R@35
