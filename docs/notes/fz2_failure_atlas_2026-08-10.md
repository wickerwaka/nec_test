# fz2 failure atlas — 2026-08-10

One snippet per seed in the fz2 true-failure ledger: the assembly the CHIP was executing when the legs forked, and the bus rows on either side of it with the diverging cells marked.

## How to regenerate this, exactly

```
python3 sw/fz2_failview.py --ledger sw/testdata/fz2/fz2_failure_ledger_f16_2026-08-10.json --split docs/notes/fz2_atlas --index docs/notes/fz2_failure_atlas_2026-08-10.md
```

* ledger `sw/testdata/fz2/fz2_failure_ledger_f16_2026-08-10.json` sha256 `f74d77748adcad52…`, derived 2026-08-10T20:42:55Z by `sw/fz2_ledger.py` — **NOT committed at generation time**: it is a working-tree file, and the sha256 above is what this atlas was built from
* corpus `fz2c`, `fz2e` (live dirs), 3840 seeds, 116 failures, seed match 96.9776 %
* bitstream `.sof` sha256 `fed558c0e61173ae…`, flashed 2026-08-10T20:27:33Z from `ddaed64457-dirty`, RTL receipt `f88783b66cf4a1ee…` (F16 wave-3 RETENTION draw 2 of 2)
* every capture is sha256-gated against the ledger before a row is read; every image is re-derived through `fuzz_campaign.compose_case` and gated on `image_sha256`

## What a snippet is, and what it is not

* **The fork row is re-derived, not copied.** `fuzz_classify.diff_rows(real, sim, window=compare_window)` is the corpus's own scorer; its first non-flicker row must equal the ledger's `first_bad_row`. Where it does not, the snippet says so and shows no disassembly.
* **The bytes are the bus's.** The disassembly window is the shadow-queue reconstruction of what the part actually fetched and retired (`CODE` T4 pushes, `QS=F/S` pops, `QS=E` flushes), with the re-derived image filling only what was never fetched. A raw-tier seed executes at a mirrored, misaligned address, and every address at or above 64 K is printed as `linear(+offset)` with the image offset it was answered from.
* **The decoder is an 8086 and the part is a V30.** `objdump -D -b binary -m i8086` is the precedent here. The retired byte count comes from the queue and is exact, so every line where the decoder's length disagrees carries `[len N≠M retired]` — that marker is the honest signature of a V30-only encoding, not a defect.
* **A prefix retires with its own `QS=F` pop** on this part, so it appears as its own line.
* **The marks are the scorer's.** A `*` is a cell `fuzz_classify.diff_rows` itself flagged — not a looser or stricter comparison invented here. `f` marks the fork row, `~` a tolerated F↔S queue-status flicker. That policy is asymmetric by column and the table shows it honestly: `qs` is compared on every row, `bs` from row 8, `t`/`ube` from row 9, `addr` only at a `T1` with an active non-`INTA` status, `data` at `T2`/`T3` and — as the next-address preview `nxta`, same cell — at `Ti`/`T4` on an active cycle, and `ps` only at a `T2`. An unmarked difference in the table is a column the corpus does not score at that T-state.
* **No mechanism is asserted.** The family labels are the ledger's A-15 partition, carried forward seed by seed; the per-family paragraph is measured over that family's own seeds.

## Coverage

| | |
|---|---|
| snippets emitted | 116 of 116 ledger failures |
| fork row reproduced from the capture | **116 / 116** |
| `diverging_rows` reproduced | 116 / 116 |
| image re-derived to the banked sha256 | 116 / 116 |
| forks with no instruction in dispatch (`NO-DISPATCH`) | 0 |
| captures unreadable / sha-drifted | 0 |
| bus bytes disagreeing with the re-derived image | 44 (in 3 seed(s)) |

No seed was left unhandled.

## Families

| family | seeds | snippets |
|---|---:|---|
| A1 qs-pop one clock late | 5 | [a1](fz2_atlas/a1.md) |
| A2 qs-pop other offset | 4 | [a2](fz2_atlas/a2.md) |
| A3 cycle-time slip (non-qs) | 15 | [a3](fz2_atlas/a3.md) |
| B1 HALT-cycle address | 1 | [b1](fz2_atlas/b1.md) |
| B2 HALT entry (one leg only) | 2 | [b2](fz2_atlas/b2.md) |
| C1 vector-1 trap MISSED by core | 1 | [c1](fz2_atlas/c1.md) |
| C2 INTA-vectored delivery | 10 | [c2](fz2_atlas/c2.md) |
| C3 NMI(vec2) entry | 1 | [c3](fz2_atlas/c3.md) |
| C4 other-vector delivery | 1 | [c4](fz2_atlas/c4.md) |
| D1 chip fetched, core did not | 10 | [d1](fz2_atlas/d1.md) |
| D2 core fetched, chip did not | 10 | [d2](fz2_atlas/d2.md) |
| D3 both fetched, different address | 8 | [d3](fz2_atlas/d3.md) |
| E1 same-status data cycle, different address | 41 | [e1](fz2_atlas/e1.md) |
| E2 different-status data cycle | 4 | [e2](fz2_atlas/e2.md) |
| NEW/UNCLASSIFIED | 3 | [new_unclassified](fz2_atlas/new_unclassified.md) |

**A1 qs-pop one clock late** — 5 seed(s).  First diverging column: `qs` 3, `bs+data` 2.  Tiers: raw 3, soup 2.  Wait source: wrand 3, fixed 2.  Median `first_bad` row 3040 (range 327–3326); median diverging rows 424.  Terminator: REACHED 5.  Architectural dump differs on 0 of 5.  The label is the ledger's; these numbers are this family's own seeds, and no mechanism is asserted here that the ledger does not carry.

**A2 qs-pop other offset** — 4 seed(s).  First diverging column: `qs` 3, `bs` 1.  Tiers: soup 2, raw 2.  Wait source: wrand 3, fixed 1.  Median `first_bad` row 1199 (range 364–2653); median diverging rows 710.  Terminator: REACHED 3, LONG_INSN 1.  Architectural dump differs on 1 of 4.  The label is the ledger's; these numbers are this family's own seeds, and no mechanism is asserted here that the ledger does not carry.

**A3 cycle-time slip (non-qs)** — 15 seed(s).  First diverging column: `bs` 6, `data` 6, `bs+data` 3.  Tiers: raw 9, soup 6.  Wait source: wrand 7, fixed 7, wvec 1.  Median `first_bad` row 1167 (range 215–3526); median diverging rows 272.  Terminator: REACHED 14, FORGED_DONE 1.  Architectural dump differs on 4 of 15.  The label is the ledger's; these numbers are this family's own seeds, and no mechanism is asserted here that the ledger does not carry.

**B1 HALT-cycle address** — 1 seed(s).  First diverging column: `bs` 1.  Tiers: raw 1.  Wait source: wrand 1.  Median `first_bad` row 1947 (range 1947–1947); median diverging rows 1000.  Terminator: REACHED 1.  Architectural dump differs on 0 of 1.  The label is the ledger's; these numbers are this family's own seeds, and no mechanism is asserted here that the ledger does not carry.

**B2 HALT entry (one leg only)** — 2 seed(s).  First diverging column: `bs` 2.  Tiers: raw 2.  Wait source: fixed 2.  Median `first_bad` row 2608 (range 1574–2608); median diverging rows 5.  Terminator: REACHED 2.  Architectural dump differs on 0 of 2.  The label is the ledger's; these numbers are this family's own seeds, and no mechanism is asserted here that the ledger does not carry.

**C1 vector-1 trap MISSED by core** — 1 seed(s).  First diverging column: `bs+data` 1.  Tiers: raw 1.  Wait source: fixed 1.  Median `first_bad` row 2371 (range 2371–2371); median diverging rows 102.  Terminator: STALLED 1.  Architectural dump differs on 1 of 1.  The label is the ledger's; these numbers are this family's own seeds, and no mechanism is asserted here that the ledger does not carry.

**C2 INTA-vectored delivery** — 10 seed(s).  First diverging column: `bs+data` 4, `t` 3, `qs` 2, `bs+data+qs` 1.  Tiers: soup 9, raw 1.  Wait source: wrand 6, wvec 3, fixed 1.  Median `first_bad` row 584 (range 227–1475); median diverging rows 1024.  Terminator: REACHED 9, LONG_INSN 1.  Architectural dump differs on 7 of 10.  The label is the ledger's; these numbers are this family's own seeds, and no mechanism is asserted here that the ledger does not carry.

**C3 NMI(vec2) entry** — 1 seed(s).  First diverging column: `bs` 1.  Tiers: raw 1.  Wait source: wrand 1.  Median `first_bad` row 2994 (range 2994–2994); median diverging rows 433.  Terminator: REACHED 1.  Architectural dump differs on 1 of 1.  The label is the ledger's; these numbers are this family's own seeds, and no mechanism is asserted here that the ledger does not carry.

**C4 other-vector delivery** — 1 seed(s).  First diverging column: `data` 1.  Tiers: raw 1.  Wait source: fixed 1.  Median `first_bad` row 2233 (range 2233–2233); median diverging rows 1749.  Terminator: REACHED 1.  Architectural dump differs on 1 of 1.  The label is the ledger's; these numbers are this family's own seeds, and no mechanism is asserted here that the ledger does not carry.

**D1 chip fetched, core did not** — 10 seed(s).  First diverging column: `bs+data` 6, `bs+data+qs` 1, `ube` 1, `bs` 1, `bs+qs` 1.  Tiers: raw 9, soup 1.  Wait source: fixed 5, wrand 4, wvec 1.  Median `first_bad` row 1138 (range 304–3218); median diverging rows 808.  Terminator: REACHED 10.  Architectural dump differs on 7 of 10.  The label is the ledger's; these numbers are this family's own seeds, and no mechanism is asserted here that the ledger does not carry.

**D2 core fetched, chip did not** — 10 seed(s).  First diverging column: `qs` 4, `bs+data` 3, `bs` 3.  Tiers: soup 5, raw 5.  Wait source: wrand 5, fixed 4, wvec 1.  Median `first_bad` row 933 (range 288–1759); median diverging rows 1267.  Terminator: REACHED 10.  Architectural dump differs on 4 of 10.  The label is the ledger's; these numbers are this family's own seeds, and no mechanism is asserted here that the ledger does not carry.

**D3 both fetched, different address** — 8 seed(s).  First diverging column: `data` 6, `bs+data` 2.  Tiers: raw 8.  Wait source: fixed 5, wrand 3.  Median `first_bad` row 881 (range 328–3048); median diverging rows 2177.  Terminator: REACHED 5, STALLED 1, WINDOW 1, LONG_INSN 1.  Architectural dump differs on 6 of 8.  The label is the ledger's; these numbers are this family's own seeds, and no mechanism is asserted here that the ledger does not carry.

**E1 same-status data cycle, different address** — 41 seed(s).  First diverging column: `data` 35, `qs` 3, `bs` 2, `bs+data` 1.  Tiers: raw 38, soup 3.  Wait source: fixed 24, wrand 11, wvec 6.  Median `first_bad` row 571 (range 236–3164); median diverging rows 404.  Terminator: REACHED 33, STALLED 4, LONG_INSN 3, BUDGET 1.  Architectural dump differs on 23 of 41.  The label is the ledger's; these numbers are this family's own seeds, and no mechanism is asserted here that the ledger does not carry.

**E2 different-status data cycle** — 4 seed(s).  First diverging column: `bs` 2, `t` 1, `bs+data` 1.  Tiers: raw 3, soup 1.  Wait source: fixed 4.  Median `first_bad` row 655 (range 345–1249); median diverging rows 9.  Terminator: REACHED 3, STALLED 1.  Architectural dump differs on 2 of 4.  The label is the ledger's; these numbers are this family's own seeds, and no mechanism is asserted here that the ledger does not carry.

**NEW/UNCLASSIFIED** — 3 seed(s).  First diverging column: `bs+data+t` 1, `qs` 1, `data` 1.  Tiers: raw 2, soup 1.  Wait source: wrand 3.  Median `first_bad` row 1090 (range 695–3029); median diverging rows 502.  Terminator: REACHED 3.  Architectural dump differs on 2 of 3.  The label is the ledger's; these numbers are this family's own seeds, and no mechanism is asserted here that the ledger does not carry.

