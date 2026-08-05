# The shared artifact / receipt layer — SPECIFICATION ONLY

**Status: SPEC.  NOTHING IN THIS DOCUMENT IS BUILT.**  It is the design note the
second Codex phase review's **concern 1 (HIGH)** was routed to, written in SM3
sitting 13 with the explicit instruction *not* to build it: it is a substantial
infrastructure change and it gets its own sitting.  `sw/quartus_gate.py`'s
receipt (SM3 sitting 13, concern 2) is written to §3 below and is the layer's
**first and so far only instance**.

> **Standing principle.**  *"A guiding principal here needs to be simplicity.
> This is 80's era hardware, they aren't wasting silicon on anything that isn't
> necessary.  Complex or confusing behavior that we see is likely to be simple
> systems interacting in ways you do not fully understand yet."*  It applies to
> the tooling too: this layer must be a **postcondition and a hash**, not a
> build system.

---

## §1 THE PROBLEM, STATED FROM THE RECORD RATHER THAN IN THE ABSTRACT

`ucore_provenance.md` records **seven** incarnations of one failure, and every
one of them is a scorer that ran against an artifact nobody proved was the
artifact it named:

| # | where | what happened |
|---|---|---|
| 1 | §67.6 | `x1_retention.build()` did not exist; `capture` ran whatever binary was lying there |
| 2 | §73.7 | `build()` existed, compiled the current RTL to **`Vtb_sys`**, and `capture` opened **`tb_sys`** — a *different file*, six days old.  It printed `REBUILT` every time.  §69.2's "byte-identical" was **a binary compared with itself** |
| 3 | `standing_gates.md` §C | `hdl/tb/obj_dir/Vtb_v30_core` was STALE for two weeks because `check_seq` never calls `check_core.build()` |
| 4 | §73.1 | the ucore's DEFAULT bitstream configuration fell to **19.42 MHz** and no gate saw it, because the standing set had no Quartus leg |
| 5 | `CLAUDE.md` | `s15_census.py` ran the **model** against a `--core ucore` report and printed the model's families for the ucore's seeds |
| 6 | §72.7a | `fuzz_campaign lint` was believed hung; it was silent.  A gate whose *liveness* nobody could read |
| 7 | INV-1 | 760 seeds scored against a capture taken under a directive the rig never applied |

**They are one bug.**  In every case a scorer's *input* was a file path, and a
file path is not an identity.  Nothing in the tree connects "the number I am
about to write into the ledger" to "the exact bytes that produced it".

**What this layer is NOT for.**  It is not a build system, not a cache, not
reproducible-builds-in-general, and it does not make Quartus deterministic.  It
answers exactly one question, on demand: **"which bytes produced this number?"**

---

## §2 THE POSTCONDITION — the whole design in one sentence

> **Every binary, bitstream or generated table on a scorer's path must appear in
> a RECEIPT that names the inputs it was built from, and a scorer must refuse to
> run against an artifact with no receipt or a receipt whose input hash does not
> match the tree it is being asked about.**

Two consequences, and they are the only two:

* **P-1 (identity)** — a scorer records, beside its result, the receipt id of
  every artifact it executed.  A number with no artifact ids is not quotable.
* **P-2 (freshness)** — before executing an artifact, the scorer re-hashes the
  artifact's declared inputs *from the tree* and compares.  A mismatch is a hard
  error naming both hashes, not a rebuild and not a warning.

P-2 is what would have caught incarnations 2, 3 and 5 on the first run.  P-1 is
what would have made 1 and 4 visible in the ledger without anyone looking for
them.

---

## §3 THE RECEIPT SCHEMA

One JSON object per built artifact, written **atomically** beside it as
`<artifact>.receipt.json`, plus a copy appended to a repo-level
`sw/testdata/receipts/<kind>.jsonl` so history survives a `rm -rf` of a build
directory.

```jsonc
{
  "schema": "nec_test/receipt",
  "schema_version": 1,

  "id":     "<sha256 of the canonical form of this object with `id` removed>",
  "kind":   "quartus_bitstream" | "verilator_binary" | "generated_table"
          | "golden_suite" | "chip_capture",
  "name":   "nec_test_ucore.sof",          // the artifact, repo-relative

  "inputs": {                              // WHAT IT IS A FUNCTION OF
    "n_files": 88,
    "sha256":  "<hash of the sorted `sha256  path` manifest>",
    "files":   { "<repo-relative path>": "<sha256 | \"MISSING\">" }
  },
  "command":  ["quartus_sh", "--flow", "compile", "nec_test", "-c",
               "nec_test_ucore"],
  "env":      { "V30_CORE": "ucore" },     // only vars the command READS
  "tool":     "Quartus Prime 17.1.0 Build 590 SJ Lite",
  "tool_sha256": null,                     // when the tool is in-tree, hash it

  "outputs":  { "nec_test_ucore.sof": "<sha256>",
                "nec_test_ucore.rbf": "<sha256>" },

  "git":      { "head": "<sha>", "describe": "…", "dirty_tracked": false },
  "started":  "2026-08-05T00:10:33Z",
  "completed":"2026-08-05T00:24:06Z",
  "rc": 0,

  "figures":  { /* kind-specific, free-form, RECORDED not gated */ },
  "verdict":  "PASS" | "RED" | null        // only when the producer is a GATE
}
```

**Rules that make the schema load-bearing rather than decorative:**

1. **`inputs.files` is a CLOSED list.**  A file the command reads and the list
   omits is a defect in the producer, not an oversight — and it is testable: see
   §6's mutation check.
2. **`MISSING` is a value.**  A vanished input must change `inputs.sha256`, so
   absence is hashed, never skipped.
3. **`dirty_tracked` counts TRACKED modifications only.**  Untracked build
   output in the tree is not tree drift and must not flip it.
4. **`id` is content-derived**, so two identical builds collide by construction
   and that collision is information.
5. **No timestamps, paths or hostnames inside `inputs`.**  Everything that
   varies without the artifact varying stays outside the hashed region.
6. **`figures` is never a bar.**  A gate's bars live in `verdict` + a `bars`
   block; resources and counts are recorded so the NEXT agent can see drift.

---

## §4 ATOMIC BUILD-AND-PROMOTE

The producer never writes into the location a scorer reads.

```
    build  -> <staging>/            (a temp dir beside the destination)
    verify -> the expected outputs EXIST and are non-empty
    hash   -> compute outputs{} and the receipt
    fsync  -> receipt + outputs
    rename -> <staging>/  ->  <destination>/     (atomic within one filesystem)
```

A crash therefore leaves either the OLD artifact with its OLD receipt, or the
new pair — never a new binary with a stale receipt, and never the case that
actually happened in §73.7 (a fresh binary under a name nothing opened).

**The postcondition the producer asserts before promoting**: every path in
`outputs` was written by *this* command — checked by stat-ing the staging dir
after the run, not by trusting the tool's exit code.  Incarnation 2 exits 0.

---

## §5 THE A/B DELTA MANIFEST

`gen_ucore_qsf.py --check` already proves one A/B claim (the two `.qsf` files
differ by the core and nothing else) and it proves it on *settings*.  The
receipt layer generalises it to *artifacts*:

```
    sw/receipt_diff.py <receipt-A> <receipt-B>
```

prints the **symmetric difference of `inputs.files`** — added, removed, and
changed-hash — and the `command`/`env` delta.  For a legitimate A/B pair the
output must be exactly the intended axis and nothing else:

| the pair | the ONLY expected delta |
|---|---|
| FSM vs ucore bitstream | `files_ucore.qip` ↔ `files.qip` and the two cores' RTL |
| retention vs control bitstream | `env` / `--verilog_macro` **only** — *identical* `inputs.files` |
| a golden re-capture | the rig's own version and nothing in `hdl/` |

**This is precisely SM3 sitting 13's concern-3(b) question asked mechanically.**
That sitting had to spend a whole board session and two flashes to establish
that FLASH #7 and FLASH #8 differ by the macro alone; with delta manifests the
*build-side* half of that claim is a one-line check, and the board session is
then measuring physics rather than bookkeeping.

---

## §6 THE LAYER'S OWN NON-VACUITY PROOF

A receipt layer that has never rejected anything is incarnation 8.  It ships
with, and is gated by, two self-tests:

* **MUTATION** — for each producer, touch one byte of one declared input, re-run
  the *scorer* (not the producer) and require a hard `INPUT MISMATCH` naming
  both hashes.  Then touch a file that is genuinely irrelevant and require the
  scorer to run.  A producer whose declared input list is under-closed fails the
  first half; one that hashes the world fails the second.
* **STALE-ARTIFACT** — restore a known-old binary under the current name and
  require refusal.  §73.7's `tb_sys.stale-s6` is retained in the tree and is the
  ready-made fixture: it is a real historical artifact that a real scorer really
  ran.

---

## §7 MIGRATION ORDER — cheapest first, and each one buys a named incarnation

| # | producer / scorer | closes | notes |
|---|---|---|---|
| 1 | **`sw/quartus_gate.py`** | 4 | **ALREADY WRITES A §3 RECEIPT** (SM3 s13).  Migration = adopt the shared writer and the `.jsonl` history; no behaviour change |
| 2 | **`sw/safe_flash.sh` → `flash_log.jsonl`** | — | already a ledger with a sha256 and a VERIFY; add `receipt_id` of the bitstream so "what is on the board" resolves to its inputs.  **Highest value per line in the whole list** |
| 3 | **`check_core.build()` / the Verilator binaries** | 2, 3 | the three `obj_dir*` trees.  Gives P-2 to every RTL scorer at once, which is most of the ladder |
| 4 | **`x1_retention.build()` / `tb_sys`** | 1, 2 | the ad-hoc post-condition added in s12 becomes the shared one and is deleted |
| 5 | **`gen_ucore_tables.py` / the generated ROM+PLA tables** | — | `check_ucore_tables`' 9,988 becomes "9,988 against receipt `<id>`" |
| 6 | **`emit_suite` / the golden suites and the fuzz bank** | 7 | the biggest and the last: a golden's receipt would have carried the rig's `evt_hold` width, and INV-1 is exactly a golden whose capture conditions were not part of its identity |

**Step 2 alone would have answered concern 3(b)'s bookkeeping half**, and steps
1-3 are together perhaps a day.  Step 6 is its own project and must not be
attempted with the others.

---

## §8 WHAT THIS LAYER DELIBERATELY DOES NOT DO

* It does **not** rebuild anything.  A mismatch is an error with two hashes in
  it; deciding to rebuild is the agent's job, and an automatic rebuild is how
  incarnation 2 stayed invisible for six days.
* It does **not** try to make Quartus bit-reproducible.  Two builds from
  identical inputs may differ; the receipt records both `outputs` hashes and
  that difference is *data* (§73.1's "the two builds had exchanged places" is a
  finding that a reproducibility requirement would have suppressed).
* It does **not** version chip captures' *content*.  A capture's receipt names
  the rig, the image and the directive — the retained rows stay exactly as they
  are, because `CLAUDE.md`'s invalidation discipline is about disposition, not
  storage, and INV-1's raw captures are retained precisely because nothing
  gates on them.
* It does **not** gate the fast ladder.  §9.

---

## §9 WHERE IT SITS RELATIVE TO THE GATES

The receipt check is a **postcondition on promotion**, not a step in the inner
loop.  Concretely, the same split concern 2 registers for the Quartus gate:

* the **fast ladder** (Verilator, the goldens, the fuzz bank) runs as it does
  today and does not wait on receipts;
* **no RTL landing is accepted and no bitstream is flashed** without the
  receipts for the artifacts involved.

That is the line at which the cost is paid once and the identity question is
actually asked.
