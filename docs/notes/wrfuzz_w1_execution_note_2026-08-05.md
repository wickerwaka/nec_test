# wrfuzz W1 — EXECUTION NOTE (deviations from the corpus pre-registration)

**Committed 2026-08-05, BEFORE any board contact of this sitting.**
Spec: `docs/notes/wrfuzz_corpus_prereg_2026-08-05.md` (committed at W0).
Plan: `docs/notes/wrfuzz_campaign_plan.md`.  Ledger: `wrfuzz_provenance.md` §W1.
Driver: `sw/wrfuzz_w1.py`.  Branch `ucsim`, from HEAD `622c3f15d2`.

> *"A guiding principal here needs to be simplicity.  This is 80's era
> hardware, they aren't wasting silicon on anything that isn't necessary.
> Complex or confusing behavior that we see is likely to be simple systems
> interacting in ways you do not fully understand yet."*

**W1 does not re-register anything.**  The 28 strata, their sizes, their
k-blocks, the exclusions and the bars B-1 … B-9 are the pre-registration's and
are executed as written.  This note exists because the standing discipline is
that **anything at all that deviates from the registered spec is committed
before the board is touched** — so what follows is the complete list of places
where executing the spec required a choice the spec did not make, plus the two
instrument changes the bars needed in order to be measurable at all.

---

## §1 THE TWO INSTRUMENT CHANGES (both in `sw/fuzz_campaign.py`)

Neither moves an image byte, neither enters `cfg_hash`, and both default to
`None` so every pre-task-#38 invocation and every `--tb-only` run means
exactly what it meant.

### 1.1 `bus_cycles` — a per-capture field, because **B-5 is per capture**

B-5 is *"no capture reaches 4,096 bus cycles … `wvec_shapes.bus_cycle_bound()`
**per capture**"*, and no field carried it.  `eval_case` now computes it off
the SOCKET leg's own rows (no engine in the loop, ~2 ms per capture, measured)
and `result_line` banks it.  Without it the bar could only have been scored on
the ~10 % of seeds whose rows are retained, which is not what it says.

**Recorded in advance, so the result cannot be read as a surprise**: the
board's capture buffer is `v30ctl.CAP_RECORDS = 4096` **clock** records and a
bus cycle is at least 4 clocks, so a board capture **cannot structurally exceed
~1,024 bus cycles**.  B-5 is therefore expected to be met by a factor of four,
and it is measured anyway — the W0 smoke's largest OFFLINE capture was 728
cycles and the offline engines are not bounded by the rig's buffer.

### 1.2 `era` — a per-capture stamp, because **B-2 says "every capture"**

B-2 is *"**Every capture** embeds the artifact layer's input-manifest hash for
the bitstream/RTL layer, the generator git SHA, `RIG_EVT_HOLD_BITS`, and the
pinned `flash_log` entry"*.  What existed was the campaign MANIFEST's
`flash_pin` plus the per-line `gen_git` — i.e. three of the four, and the
strongest of them in a single file that can be rewritten after the captures
exist.  `fuzz_campaign.era_of()` now assembles the block and `cmd_run` stamps
it onto every line it writes:

| field | value for `wr1` |
|---|---|
| `sof_sha256` | `1a01a6975e4aca6f…` (**FLASH #10**, `flash_log` tail, `verify OK`) |
| `rtl.receipt_id` | `a2d605a47f61af37…` — the quartus receipt whose OUTPUT is that `.sof` |
| `rtl.inputs_sha256` | `42752f3a57483002…`, **88 files** |
| `gen_git` | `622c3f15d2` |
| `rig_evt_hold_bits` | **12** (F46 / gap R1) |

The receipt is found by matching the pinned `.sof` sha256 against the
`quartus_bitstream.jsonl` outputs — the RTL layer is **named**, not asserted.
`rtl.inputs_sha256 = None` is itself a B-2 failure and the pre-flight refuses.

---

## §2 THE FOUR EXECUTION CHOICES THE SPEC LEFT OPEN

### 2.1 B-9's per-stratum allocation — **declared here, before any capture**

The spec registers *"a declared 5 % stratified sub-sample = **158 seeds** × 3
reps"*.  5 % of 3,150 is 157.5, so no proportional per-stratum split is
integral, and the spec does not give one.  Declared now:

> **largest-remainder apportionment of 158 over the 28 strata.**
> `floor(0.05·n)` everywhere (soup 7, raw 3 = 140), then the 18 remaining seats
> to the largest fractional parts — raw's `.75` before soup's `.5`, ties broken
> by ascending stratum index.  Result: **raw 4 each (56)**, **soup strata 0-3 →
> 8 each (32)**, **soup strata 4-13 → 7 each (70)** = **158**.
> Within a stratum the seeds are **evenly spaced** across the k-block,
> `k_lo + (j·n)//m`.

Any deterministic subset is unbiased here — the seeds are independent draws
keyed by `k` — so the choice is made for SPREAD and REPRODUCIBILITY, and it is
written down before the first capture rather than after a number is seen.
`sw/wrfuzz_w1.py::b9_alloc()` is the arithmetic; it asserts its own total.

### 2.2 B-9 runs **3 FRESH repetitions**, not 1 banked + 2 fresh

The board-time table budgets B-9 at *"316 seed-loops"* = 158 × **2 extra**
reps, i.e. it assumes the corpus pass supplies repetition 1.  It cannot: the
corpus pass retains rows only for divergent seeds plus the ~70-seed SUCCESS
ballast, so most of the 158 would have **no rep-1 rows to compare against**.
The B-9 pass therefore takes **three fresh repetitions per seed = 474
seed-loops**, ~40 s more board time at the derated 4.0 seeds/s.

**The bar is unchanged — 158 / 158 stable.**  Three fresh repetitions is
strictly at least as strong a test as one banked plus two fresh, and it is
self-contained: no code path has to decide in advance which seeds to retain.

### 2.3 B-9 compares **both A/B legs**, and scores the bar on both

*"The same seed, the same vector, three repetitions, gives the same rows."*
`capture_board` is one seed-loop producing TWO captures (socket then fabric),
so both are compared, rep 1 against reps 2 and 3, and a seed is STABLE only if
all four comparisons are clean.  Comparing only the socket would have been the
weaker reading of the same sentence.

The comparator is the registered one: `fuzz_classify.diff_rows`' own window and
column policy (rows 9+).  That policy tolerates the 1-cycle F↔S queue-status
flicker as cosmetic; the flicker rows are **counted and reported beside the
bar**, never folded into it silently.

### 2.4 `div_guard` cadence

B-7 asks for `div_guard()` PINNED *"with its readback recorded on every
probe"*.  The divider is in fact commanded on **every single capture** by
construction — `check_seq.run_chip` passes `div=DIV_OF_RECORD` positionally
(never inherited, 21.1) and `ServeRunner.cfg`'s cache key contains `div`, so
the A/B flip re-sends `CFG` with the divider on every seed.  The driver
RECORDS `s13_board.div_guard`'s readback at **every stratum boundary** plus
pre-flight, B-9 start/end and the close — 30-plus readbacks of the same live
transport attribute.  Recording it 6,300 times would be the same fact written
6,300 times; recording it 0 times would be assuming it.

---

## §3 WHAT THIS SITTING WILL NOT DO

* **NO FLASHING.**  FLASH #10 is resident and correct for socket capture.
  `fuzz_campaign run` REFUSES if the `flash_log` tail moves off the manifest
  pin, and `--allow-stale` is not passed anywhere in the driver.
* **No scoring of any engine against the captures beyond what a bar requires.**
  The survey is W2's.  In particular **no family census is run and no
  engine-vs-silicon rate is quoted** — `wrfuzz_w1.py bars` reports per-stratum
  VERDICT COUNTS (the capture record) and nothing that could be read as `S`.
* **No standing gate moves.**  `standing_gates.md` is untouched at W1 by
  design; no ratchet is re-registered.
* **No memory file is touched and Codex is not launched** — the coordinator
  routes this package.
* **No `--tb-only` run.**  F-4's trap is live (`check_seq.CORE` is pinned to
  `fsm`), and W1's comparator is the board.
