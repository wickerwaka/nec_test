# PRE-REGISTRATION — THE `EMIT_CAP` REPAIR, AND THE `rep_cl0` RE-CAPTURE

**Committed BEFORE the instrument is touched and before any board contact.**
Closes the rig defect named in `invalidation_ledger.md` § INV-3.

| | |
|---|---|
| tree | `master`, HEAD **`707570b067`** |
| the defect | INV-3 *WHICH RIG DEFECT* — `EMIT_CAP`'s ceiling, plus a length failure that reaches the reroll path |
| scope | `sw/emit_suite.py` only, then ONE socket capture.  **NO FLASH.** |

---

## 1. THE DEFECT, MEASURED

`v30sim timed-run --ndjson`, `F3 A5` at CX=257, instruction alone:

| `SI`/`DI` alignment | clock rows | vs the 4,096 ceiling |
|---|---|---|
| even / even | 2,085 | fits |
| odd / even | 3,113 | fits |
| **odd / odd** | **4,140** | **EXCEEDS** |
| `F3 AF` odd / odd | 3,631 | fits |

A doubly-odd word operand splits **every** access into two byte cycles.  That
is the whole mechanism, and it is why exactly the doubly-odd `F3A5` images
quarantined and were rerolled — the systematic exclusion INV-3 records.

Two code paths carry it, both in `sw/emit_suite.py`:

1. **The ceiling** — `EMIT_CAP = 2048`, `EMIT_CAP_RETRY = 4096` (`:248-249`),
   clamped by `EMIT_CAP = min(4096, EMIT_CAP * (1 + args.waits))` (`:2548`).
2. **The retry predicate** — `if "no done marker" not in str(e) …: raise`
   (`:1547`, `:1899`).  The failure *"only N register words before the done
   marker"* does **not** match, so it never retries; it re-raises and
   `cmd_emit` rerolls the seed.

## 2. WHAT IS REGISTERED — THE FIX

* **F-1.  The ceiling rises to 8,192.**  Measured worst case in the derivation
  **and** validation cells is 4,140 rows plus the store stub; 8,192 is ~2x that.
  The `min(…)` clamp rises with it so a wait-state emission is not silently
  re-clamped to the old value.
* **F-2.  A CAPTURE-LENGTH FAILURE MAY NEVER REACH THE REROLL PATH.**  This is
  the substance of the repair, not F-1.  The rule is ONE sentence: *a length
  failure retries once at the raised cap, and if the retry also fails the run
  STOPS with a named error.*  A seed is never rerolled for being slow.  This
  makes the tool **structurally incapable** of the thing A-1 R-2 forbids,
  rather than leaving it to a registration nobody can enforce at runtime.
* **F-3.  The "only N register words" failure is a length failure** and is
  covered by F-2's single rule.  It is not given its own branch — one predicate,
  both symptoms, per the standing simplicity principle.
* **F-4.  Reroll-on-length is REFUSED LOUDLY, not silently tolerated.**  If the
  run stops under F-2, it names the case, the cap it reached and the row count.
  An accepted-and-ignored failure here is what produced INV-3.

## 3. THE GATE ON THE FIX — scored BEFORE the board

* **G-1.  Byte-identity.**  With no directed override and a fixed `--seed`, the
  emitter generates **byte-identical** cases to `707570b067` over all 359 forms
  and ≥ 3 seed bases.  *Falsifier*: any difference.  **Demonstrated
  non-vacuous** — a deliberate perturbation must turn it RED.
* **G-2.  Non-vacuity of F-2.**  A case constructed to exceed even 8,192 must
  **stop the run with the named error** and must **not** reroll.  Demonstrated
  positively, not argued.
* **G-3.  `EMIT_USE_CORE` stays `False`** and the per-run assertions are
  unweakened.
* **G-4.  P-6 holds** — `git diff --stat` over `v0.1`/`v0.2`/`v0.3`/`v20suite`
  EMPTY.

## 4. THE RE-CAPTURE

Same cell as the pre-registration at `0dc40e51dc` §3 as amended by A-2:
`F3A4`/`F3A5` × CX ∈ {255, 256, 257} × DF ∈ {0,1} × both preloads = **24
cases**, socket only, `use_core=False`, waits 0, **no flash**.

* **RC-1.  ZERO REROLLS.**  `emit_log.txt` carries **no `reroll:` line**.  This
  is INV-3's own registered falsifier: *"If it rerolls even once, the ceiling
  fix is insufficient and the disposition is re-opened rather than re-argued."*
* **RC-2.  ALL SIX `F3A5` ALIGNMENT STRATA PRESENT.**  The re-captured `F3A5`
  cases must include **at least one doubly-odd (`SI` odd **and** `DI` odd)
  image** — the class INV-3 says was excluded.  *Falsifier*: none present.
  Without RC-2 the repair is unproven even if RC-1 passes, because RC-1 alone
  is also satisfied by a cell that never drew a hard case.
* **RC-3.  P-1 … P-7 re-scored as registered**, unchanged in wording.
* **RC-4.  ⚠ THE OUTCOME MUST BE `H-ENGINE`, OR INV-3'S *WHY* IS WRONG.**
  INV-3 registered that if the re-captured cell reads anything else, its bias
  analysis is **retracted, not defended**.  That clause stands and is scored.

## 5. WHAT IS STILL NOT DONE

No fix to either engine.  No width rule derived.  The 72-case validation cell
(A-2 §A-2.2) is captured only **after** this re-capture certifies, and **no
width rule may be quoted as validated until that validation cell is scored.**
A per-row special case for microcode row `0094` remains refused in advance.
