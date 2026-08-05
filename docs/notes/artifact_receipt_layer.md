# The shared artifact / receipt layer

> ## ⚠ STATUS CHANGED — **IT IS BUILT (SM3 SITTING 14, 2026-08-05).**
>
> The text below is the SPECIFICATION exactly as sitting 13 wrote it, and it is
> left unedited so that what was designed stays readable beside what was built.
> **Where the implementation deviates, the deviation is recorded as an erratum
> box beside the section it deviates from — never silently.**  Four such boxes
> exist: §3 (E-1, E-2), §4 (E-3), §7 (E-4).
>
> | | |
> |---|---|
> | the layer | **`sw/artifact.py`** (559 lines) — `Recipe` / `build` / `require` / `ensure` / `diff_receipts` |
> | §5's delta manifest | **`sw/receipt_diff.py`** |
> | §6's non-vacuity proof | **`sw/test_artifact.py`** — **45/45 checks**, and it runs the real `tb_sys.stale-s6` fixture |
> | the migration | `ucore_provenance.md` **§75** has the gate → receipt table and the itemised UNMIGRATED remainder |
>
> **What the build measured that the spec could not know**: every Verilator
> binary in the tree was ALREADY byte-identical to a fresh rebuild, and
> Verilator 5.032 is byte-reproducible here across `-Mdir` locations.  That is
> what makes the migration provably number-neutral — see §75.

**Status when written: SPEC.  NOTHING IN THIS DOCUMENT IS BUILT.**  It is the
design note the
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

> ### ERRATUM E-1 (SM3 sitting 14) — **`inputs` HAD TO INCLUDE FILES THE COMMAND NEVER READS**
>
> §3 rule 1 says `inputs.files` is "every file the command reads".  Built
> against the real tree, that definition is **under-closed**, and the file it
> omits is the one the whole ucore is made of.
>
> `hdl/rtl/ucore/v30u_ucrom.sv` does `$readmemh(ucrom.hex)` /
> `$readmemh(ucdecode.hex)` **AT RUN TIME**.  Verilator never opens either
> file; the *binary* opens them, every run.  So under the spec's wording the
> ucore's **entire architecture — 1,028 microcode rows and 8,192 decode
> entries — would have sat outside the identity of every number ever scored
> against it.**  `v30u_ucrom.sv`'s own F44 block exists precisely because a
> wrong `HEXDIR` yields an all-zero ROM and *a run that completes normally*.
> The same applies to the FSM core's `int9d_race.hex`.
>
> **The rule as built is**: `inputs` is what the ARTIFACT is a function of, not
> what the COMMAND reads.  The two `.hex` tables are declared, and a table
> change costs one 18-second rebuild.  `check_ucore_tables` (G0) already
> checked those bytes against `sim/`; nothing tied them to a SCORED NUMBER.
>
> ### ERRATUM E-2 (SM3 sitting 14) — **THE TOOL VERSION IS CHECKED, NOT ONLY RECORDED**
>
> §3 keeps `tool` outside the hashed `inputs` region, which is right — it is
> not a file.  But a schema that only *records* it lets a compiler upgrade
> silently invalidate every binary in the tree, which is the same shape as the
> seven incarnations one level down.  As built, `tool` is inside `build_key`
> (so an upgrade rebuilds) and `require()` re-probes it and fails on a
> mismatch.  The probe command is carried in the receipt (`tool_probe`) so
> `require()` can ask without a `Recipe`.  Three lines.

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

> ### ERRATUM E-3 (SM3 sitting 14) — **THE PROMOTE IS TWO RENAMES, AND THE GUARANTEE IS RECOVERED ELSEWHERE**
>
> §4's `rename(<staging>, <destination>)` cannot be one step: POSIX will not
> rename a directory onto a non-empty directory.  As built it is
> `dest -> trash`, `staging -> dest`, `rm -rf trash`, and there is a
> microsecond window in which the destination does not exist.
>
> **The property §4 wanted is not weakened, it is strengthened.**  `require()`
> re-hashes the declared **`outputs`** as well as the inputs, so a destination
> that is absent, partial, or paired with a receipt written for different bytes
> is a hard error *whatever produced it* — a crashed promote, a hand-copied
> binary, `cp` from another checkout, or the `tb_sys.stale-s6` restore that
> §6's second self-test actually performs.  The promote protects the build; the
> output hash protects the scorer, and the scorer is who the spec is for.
>
> One consequence worth writing down: the promote replaces the whole `obj_dir`,
> so Verilator's incremental state is discarded on every real rebuild.
> **MEASURED: a clean `tb_v30_core` build is 17.8 s and a clean `tb_sys` is
> 12.6 s**, and a build whose content key has not moved costs **0 s** because
> it does not run at all.  The old mtime path cost ~0.1 s on a no-op and could
> not answer the question.  That is the whole price of the layer.

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

> ### ERRATUM E-4 (SM3 sitting 14) — **WHAT THE MIGRATION ACTUALLY TOOK, AND WHY THE ORDER MOVED**
>
> Steps **1, 3 and 4 are DONE**, plus the whole of the standing Verilator
> ladder, which this table did not itemise.  Steps **2, 5 and 6 are NOT**, and
> the risk each still carries is itemised in `ucore_provenance.md` §75.
>
> **The order moved for one reason**: step 3 (`check_core.build`) turned out to
> be the *only producer* of `Vtb_v30_core`, and eleven tools consume it.  So
> `check_core.recipe()` became the single declaration and everything else
> asserts against it — `check_seq` (which never built at all: **incarnation
> #3**, and `check_fuzz_bank` / `check_mod3_illegal` / `check_enter_nesting`
> inherit the fix through it), `check_boot`, `ulockstep`, `timed_fuzz`,
> `timed_wvec_gate`, and `tb_bootrun` (the choke point for `timed_enter_replay`
> and `timed_ins_replay`).  Doing step 3 without them would have left the
> receipt sitting beside a binary that six standing gates still opened by path.
>
> **Step 2 (`safe_flash.sh` → `flash_log.jsonl`) was NOT taken and it is still
> the highest value per line in the list.**  It was excluded because it is the
> one item that ends at the board, and this sitting is board-free by its own
> terms.  The build-side half it needs now exists: `quartus_gate` emits a §3
> receipt with an `id` and hashed `outputs`, so `flash_log` gaining a
> `receipt_id` is a one-field change whenever a board sitting next runs.

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
