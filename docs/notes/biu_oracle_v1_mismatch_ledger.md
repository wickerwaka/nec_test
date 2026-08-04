# V30 BIU frozen-oracle mismatch ledger

This is a read-only join of the frozen v1 oracle to its prospective held-out population. It does not refit the oracle.

## Totals

- Records: 756
- Exact matches: 224
- Unseen keys: 348
- Mismatches on overlapping keys: 184
- Action mismatches: 48
- Exact-T1 mismatches: 178
- Address mismatches: 48
- QS mismatches: 46

## Byte-role evidence

| Training role | Held-out role | Differing outputs | Count |
|---|---|---|---:|
| modrm | disp16_high | action, t1, address | 16 |
| modrm | disp16_high | t1 | 36 |
| modrm | disp8 | action, t1, address | 32 |
| modrm | disp8 | qs | 6 |
| modrm | disp8 | t1 | 54 |
| modrm | disp8 | t1, qs | 40 |

## Directed minimal-pair cells

Each row is one representative pair sharing the complete frozen oracle key. Form/padding identify stimulus recipes only; they are not proposed state variables.

| # | Roles | Differences | Training recipe | Held-out recipe |
|---:|---|---|---|---|
| 1 | modrm → disp16_high | action, t1, address | `{"form": "read_mov", "pad": 3, "parity": "odd", "request_class": "read", "wait": 4}` | `{"form": "held_read_disp16", "pad": 1, "parity": "odd", "request_class": "read", "wait": 1}` |
| 2 | modrm → disp8 | action, t1, address | `{"form": "read_mov", "pad": 3, "parity": "odd", "request_class": "read", "wait": 2}` | `{"form": "held_read_disp8", "pad": 2, "parity": "odd", "request_class": "read", "wait": 1}` |
| 3 | modrm → disp8 | t1, qs | `{"form": "none_lea", "pad": 2, "parity": "odd", "request_class": "none", "wait": 2}` | `{"form": "held_lea_disp8", "pad": 1, "parity": "odd", "request_class": "none", "wait": 1}` |
| 4 | modrm → disp16_high | t1 | `{"form": "read_mov", "pad": 3, "parity": "odd", "request_class": "read", "wait": 6}` | `{"form": "held_read_disp16", "pad": 1, "parity": "odd", "request_class": "read", "wait": 3}` |
| 5 | modrm → disp8 | t1 | `{"form": "read_mov", "pad": 2, "parity": "odd", "request_class": "read", "wait": 3}` | `{"form": "held_read_disp8", "pad": 1, "parity": "odd", "request_class": "read", "wait": 2}` |
| 6 | modrm → disp8 | qs | `{"form": "none_lea", "pad": 3, "parity": "odd", "request_class": "none", "wait": 2}` | `{"form": "held_lea_disp8", "pad": 2, "parity": "odd", "request_class": "none", "wait": 1}` |

## Interpretation

- Branch keys are unseen and must remain a separate flush study.
- Overlapping LEA/read/write/RMW keys prove that queue head, current QS, request class, predecessor, and completion offset are not enough.
- The next prospective variable to test is controlled instruction-byte role (ModRM versus disp8 versus high disp16 byte).
- A new variable is acceptable only if role toggles the result while alternate preparation history and padding do not.
