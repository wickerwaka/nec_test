# AMENDMENT A-1 to `rep_cl0_silicon_prereg_2026-08-17.md`

**Committed BEFORE the board leg it governs.**  Amends the pre-registration at
`0dc40e51dc`.  Nothing in §0–§4 (the finding, the outcomes, the cell, the
predictions) is changed; this amendment adds a CAPTURE-LENGTH condition that
the original document did not anticipate, and registers its consequences.

---

## A-1.1 THE FINDING THAT PROMPTS IT

`EMIT_CAP = 2048` records, `EMIT_CAP_RETRY = 4096`, and the wait-state scaling
is `EMIT_CAP = min(4096, EMIT_CAP * (1 + args.waits))` — **a hard ceiling of
4096** (`sw/emit_suite.py:197-198`, `:2548`).

**MEASURED, offline, `v30sim timed-run --ndjson`, this tree:**

| case | clock rows |
|---|---|
| `F3 A5` CX=255 | 2,069 |
| `F3 A5` CX=256 | 2,077 |
| `F3 A5` CX=257 | 2,085 |
| `F3 A4` CX=257 | 2,085 |

That is the INSTRUCTION ALONE.  The emit path additionally captures the store
stub and the done marker.

So **every case in the derivation cell exceeds the 2048 default** and will fail
its first attempt with *"no done marker"*, retrying at 4096.

## A-1.2 WHAT IS REGISTERED

* **R-1.  The retry path is EXPECTED, not a fault.**  A first-attempt
  *"no done marker"* on every case of this cell is the registered normal
  outcome.  It is **not** a rig-integrity finding and does **not** stop the
  sitting.  The results document reports the attempt count.
* **R-2.  THE SEED IS NEVER REROLLED ON A CAPTURE-LENGTH FAILURE.**  This is
  the tool's own standing rule (`sw/emit_suite.py:199-200`, the `32db59a`
  lesson: capture-length rerolls bias a suite against long-trace cases).  The
  same image retries at the larger cap.  A rerolled seed in this cell
  **invalidates the cell**.
* **R-3.  WAITS ARE ZERO.**  `--waits 0` only.  At any non-zero wait the
  instruction alone would exceed the 4096 ceiling and the cell is not
  capturable by this path.  A capture taken at non-zero waits is VOID.
* **R-4.  HEADROOM IS ~2x AND IS NOT ASSUMED.**  4096 against a measured 2,085
  leaves roughly 2,000 records for the store stub and done marker.  The results
  document must report, per case, **the actual record count and the margin to
  4096**.  If any case lands within 256 records of the ceiling that is reported
  as a **registered near-miss**, and the validation cell (§3, which reaches
  CX=1024 and would need ~8,300 records) is **NOT capturable by this path** and
  must not be attempted with it.

## A-1.3 CONSEQUENCE FOR THE VALIDATION CELL

The prereg §3 validation cell (CX ∈ {512, 768, 1024}) needs roughly 4,200 /
6,300 / 8,300 records and is therefore **BEYOND the 4096 ceiling**.  It is
**not capturable by the `emit_suite` path as it stands**.

Registered disposition: the validation cell is **DEFERRED**, not abandoned, and
is **not** silently dropped from the claim.  Until it is captured by some
instrument, **no width rule derived from the derivation cell may be quoted as
validated** — exactly the standing rule the prereg §3 invoked.  Raising the cap
is a separate change with its own registration; it is **not** taken in the
sitting that captures the derivation cell.

⚠ **The derivation cell alone therefore settles WHAT SILICON DOES at
`CX = 256`, and nothing more.**  It does not validate a fix.
