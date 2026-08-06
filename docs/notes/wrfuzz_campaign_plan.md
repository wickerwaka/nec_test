# wrfuzz — the RANDOM-WAIT FUZZ campaign (task #38)

**Opened 2026-08-05**, branch `ucsim`, from HEAD `1a2a9eff4e`.
**Directed by the user** on accepting the silicon-match verdict
(`docs/notes/sm3_verdict_2026-08-05.md`: *"Okay. Let's close this campaign"*,
with a successor campaign focused on fuzz testing with random waits).

Ledger: **`docs/notes/wrfuzz_provenance.md`**.
Corpus pre-registration: **`docs/notes/wrfuzz_corpus_prereg_2026-08-05.md`**.
Gate authority: `docs/notes/standing_gates.md`.
Invalidation register: `docs/notes/invalidation_ledger.md`.

> **THE STANDING PRINCIPLE, in the user's own words, and it governs this
> campaign as it governed the last two.**
>
> *"A guiding principal here needs to be simplicity.  This is 80's era
> hardware, they aren't wasting silicon on anything that isn't necessary.
> Complex or confusing behavior that we see is likely to be simple systems
> interacting in ways you do not fully understand yet."*
>
> Read as a work rule: a large fitted table, a many-cased rule or a per-opcode
> special case is a **signal of misunderstanding, not a deliverable**.  That
> applies to the corpus too — five vector shapes with four parameters each,
> not a family of stimuli tuned until a number moves.

---

## §1 WHY THIS CAMPAIGN, AND WHAT IT INHERITS

**Wait-state cycle accuracy is the project's standing #1 priority**, and it has
been since before the ucsim-t campaign: *arbitrary-wait accuracy beats w0, and
the target is a random-wait physical-versus-core match.*  Every campaign since
has moved that number and none has been about it directly.  Where it stands at
this campaign's opening, all figures cited from `standing_gates.md` at
`f3f7b6b20d` via the SM3 verdict §(d.1):

| | `ucore` | model |
|---|---|---|
| `timed_fuzz` REGISTERED (1,702 banked seeds) | **1,557 (91.5 %)** | 1,338 |
| … EVT (1,008) | **931 (92.4 %)** | 798 |
| … COMBINED (2,710) | **2,488 (91.8 %)** | 2,136 |
| the b2 victory tranche (188) | **177** | 159 |
| the b3 priority tranche, IN FABRIC | **178 / 178 (100.0 %)** | — |

**What the residue is.**  222 of 2,710 banked seeds (8.19 %) diverge from
silicon on the `ucore`.  Every one carries a named disposition **except nine
banked seeds and twenty-seven S16 `ARCH` cells** — the SM3 verdict §(e) states
that partition and this campaign does not re-litigate it.

**What this campaign adds that no previous one had.**  Every wait axis in the
tree so far is one of exactly two things: a **CONSTANT** level (`--waits N`,
`fix0..fix3`) or the rig's **OWN SEEDED LFSR** (`wrand`, wmax ∈ {1,2,3,7,15},
poly 0xB400, one draw per bus cycle).  The third source has existed in the RTL
since Phase 2a and has been driven exactly twice — by `timed_wvec_gate`'s
frozen 88-cell corpus and by §68.6's directed H3-B cell — and never by a fuzz
corpus:

> **the PER-ACCESS WAIT VECTOR**: an explicit, host-specified Tw count for
> every bus cycle, applied by the SAME buffer to the socketed chip and to the
> fabric core, and replayable byte for byte into both offline engines.

That is this campaign's new axis.  It is not a new mechanism in the part; it is
a stimulus the part has never been asked to answer at scale.

**Inherited, and not re-derived**: the generation stack (`gen_soup`, `gen_raw`,
`fuzz_campaign`), the banked corpus and its sha gate, the classifier and its
accept engine, `timed_fuzz`'s scoring policy and column policy, the artifact /
receipt layer, the era guard, `s15_census`'s family taxonomy, and every gate in
`standing_gates.md`.

---

## §2 SCOPE — WHAT IS IN AND WHAT IS OUT, AND WHO DECIDED

| item | disposition | authority |
|---|---|---|
| **H3-B — the grant-order swap** | **RE-ENTERS SCOPE.**  Its deferral was CAMPAIGN-scoped (the silicon-match phase), and it is a random-wait ARBITRATION mechanism, which is this campaign's subject | the campaign directive, 2026-08-05.  §68.6's own unrun spec is the entry point |
| **8080 / BRKEM** | **DEFERRED — carries.**  Corpora are **BRKEM-FREE BY CONSTRUCTION**, by a generation axis and not by post-filtering | user decision 2026-08-05, SM3 verdict §(a.3) |
| **the model-only residue (366 seeds)** | **FROZEN — carries.**  A defect in `sim/` and not in the `ucore` is not a work item | user decision 2026-08-05 |
| **V5** | **SEALED — carries.**  A standing REGISTERED FAILURE, not re-opened and not re-negotiated | ucsim-t; SM3 verdict §(d.3) |
| **the pin-event (EVT) axis** | **OUT of W0-W2 by design.**  The survey corpus is evt-free.  Crossing a brand-new wait axis with the pin axis confounds two things at once, and the EVT column carries its own quoting rule.  An EVT × vector cell is NAMED and reserved for W3+ | this plan, §6 |
| the nine catch-all seeds / the 27 `ARCH` cells | **not this campaign's**, unless the survey lands on one; the survey COUNTS them and does not chase them | SM3 verdict §(f) |

**Governance that carries in full and is restated so it cannot be assumed
away**: SILICON MATCH is the only correctness bar; pre-registration before
every run; directed cells over fitted tables; §64.1's disjoint validation (a
law re-keyed on the population that authorised it is a FIT, not a law);
sim-first routing for shared mechanisms; monotone ratchets, never re-scored
downward without a loud itemised entry; receipts and era guards on every
artifact a number is computed from; Codex at phase boundaries; and the board
discipline of `CLAUDE.md` in full.

---

## §3 THE STAGES

### W0 — CORPUS DESIGN AND PRE-REGISTRATION (this sitting)

**No board contact, no generation at scale, no mechanism work, no flashing.**

Deliverables: this plan; the corpus design and its pre-registration; the
generator extensions carrying the new axis; a ≤ 20-seed smoke population proved
through BOTH offline engines; the capture-integrity bars for W1; the shape of
W2's deliverable; the campaign ledger opened.

**Exit condition**: the pre-registrations are committed, the lint is green, and
the smoke proves `generation -> vector application -> scoring` end to end with
no board involved.

### W1 — SOCKET CAPTURE

Generate the pre-registered corpus and capture it.  Each seed is one
`capture_board` call: the **socketed chip** (`use_core=0`) and then the
**fabric core** (`use_core=1`), same image, same vector, same bitstream,
differing in the A/B select and in nothing else.

W1 **measures and reports; it does not diagnose.**  Its bars are the
capture-integrity bars of the pre-registration (B-1 … B-8) and nothing else.
A bar that fires is a STOP and a finding, not a tolerance.

### W2 — THE SURVEY (survey-then-fix)

Run the **full** batch, categorize **all** failures, then plan.  **Nothing
lands at W2.**  Its deliverable is one census document over one tree, with the
per-stratum table, the family taxonomy, the residue partition, the H3-B
signature count under the new axis, **the victory bar computed by §5's
registered formula and FROZEN**, and the directed-cell specs for W3+.

### W3+ — MECHANISM SITTINGS

One mechanism per sitting, each with its own pre-registration, its own
directed cell where the bank cannot discriminate, and its own falsifier.
Shared mechanisms land `sim/` first.  Between sittings the full ladder is
re-scored; a ratchet that moves down is a loud itemised entry.

### VICTORY

A pre-registered numeric bar on a **fresh stratified random-wait tranche**,
**scored IN FABRIC, hardware-versus-silicon**.  The number is registered from
the survey (§5) — **never after the tranche is scored**.

---

## §4 WHAT "VICTORY" MEANS HERE, AND WHY IT IS THE FABRIC

The comparison that decides this campaign is **the fabric core against the
socketed chip, on the same board, in the same session, on the same image and
the same wait vector**.  Not the TB against a golden, not the model against a
capture.  Three reasons, all of them findings this project already paid for:

1. **The fabric is stricter than the offline instruments, by a named class.**
   §56 measured `sw/u4_f42_fabric.py` at 143/283 where `tb_v30_core` scored
   259/283 on the same RTL, and **116 of 116 fabric-only failures were INTA
   float-retention rows**.  A campaign that declares victory offline declares
   it against the weaker comparator.
2. **The instrument-agreement rule points the same way.**  §88.A.6b: *where
   `tb_v30_core` and `tb_sys` disagree, fabric sides with `tb_sys`* — 35
   directed disagreements, 35 resolved in the fabric-shaped instrument's
   favour.
3. **The A/B pair removes the confounds by construction.**  One image, one
   vector, one bitstream, one `wvec_buf`; the ONLY difference is
   `CFG.use_core`.

**⚠ The registered risk this carries.**  The INTA float class (§56) is a real
divergence between the fabric scorer and the TB, and this campaign's corpus is
evt-free — so **INTA cycles arise only from software interrupts, not from pin
acknowledges**.  Whether the float class reaches the corpus is a W2
MEASUREMENT and not an assumption; W2 reports the INTA-row count per stratum.
**The scorer is chosen NOW and is not swapped after a result is seen** — that
would be choosing a comparator after seeing a number, which §56 names in terms
as the thing not to do.

---

## §5 THE VICTORY-BAR REGISTRATION PROTOCOL

**Registered in this document, before any survey number exists.**

**The tranche.**  A stratified population over the SAME 28 strata as the
survey, **7 seeds per stratum = 196**, drawn from a k-block **DISJOINT** from
every survey seed, plus **4 directed law-cells** (§6.4).  Frozen to a
`population.json` with its sha256 **committed before the first capture** — the
b2 precedent (`ucsim_t_provenance.md` §14.4) exactly.

**The bar.**  Let `S` be the survey's measured **hardware-versus-silicon
cycle-exact rate**, computed as the **unweighted mean of the 28 per-stratum
rates** (the tranche's own equal-per-cell weighting, so the two numbers are
comparable by construction).  Then

> **B = S − 5.0 percentage points**, converted to a whole seed count on the
> tranche's own scored denominator, rounded DOWN.

`S` is computed at W2, written into the census, and **FROZEN there**.  Neither
`S` nor the 5-point allowance may be re-derived after the tranche is scored.

**Why 5.0 points, registered now.**  The ucsim-t precedent measured a FRESH
tranche scoring *better* than the adversarially-selected bank (62.2 % against
a 55.6 % bar) and predicted that in advance for the reason it happened, so a
fresh disjoint tranche is not expected to be the harder population.  The
allowance is therefore for SAMPLING, not for slack: at p ≈ 0.9 the standard
error of a 196-seed mean is 2.1 points, and 5.0 ≈ 2.4 standard errors.

**The registered outcomes.**

| outcome | condition |
|---|---|
| **MET** | the tranche's fabric hardware-vs-silicon rate ≥ **B**, **and** every non-exact seed's first divergence falls in a family NAMED in the W2 census's taxonomy (the V3 precedent, which was met at 100 %) |
| **MISSED** | anything else.  **Reported as registered, never restated**; the tranche is not re-drawn, `B` is not re-derived, and no stratum is dropped |
| **VOID** | a capture-integrity bar (B-1 … B-8) fires on the tranche.  Fix the rig and RE-CAPTURE — the correctness directive's own clause |

**THE FALSIFIER FOR THE AXIS ITSELF, registered with the bar.**  If at W2 the
five `wvec` strata's hardware-vs-silicon rates are **not distinguishable** from
the five `wrand` strata's — no stratum pair differing by more than its combined
95 % interval — then **the new axis has bought nothing the existing rig did not
already buy**, and this campaign says so in its census in those words.  The
corpus design is not defended against its own result.

---

## §6 THE CORPUS, IN ONE PAGE

Full specification, sizes, k-blocks and bars:
**`docs/notes/wrfuzz_corpus_prereg_2026-08-05.md`**.  Summary:

### 6.1 The new axis
Five vector shapes — `uni`, `walk`, `skew`, `burst`, `edge` — each with a
stated purpose and at most four parameters (`sw/wvec_shapes.py`).  Every vector
is exactly **4,096 entries** of **0…31**, banked **in full** as `wvec_hex`
beside its spec and its sha256.

### 6.2 The strata
**2 tiers** (soup, raw) × **14 wait sources** (fix0-3, wrand1/2/3/7/15, and the
five shapes) = **28 strata**; **150 seeds per soup stratum, 75 per raw
stratum** = **3,150 seeds**.  The nine existing wait classes are CONTROLS, in
the same corpus and the same session, so the new axis is read against them and
not against a memory of them.

### 6.3 Board time
The measured hw-ab rate is **6.0 seeds/s** (`heartbeat.json`, mc1 and mc2).
Budgeted at **4.0 seeds/s** — the corpus is **≈ 13 minutes** of board time and
the whole W1 session is registered at **≤ 30 minutes**.  **Board time is not
the binding constraint at this size**; the size is chosen for per-stratum
resolution (±4.8 points at n = 150, ±6.8 at n = 75).

### 6.4 The directed law-cells
Four cells carrying the ONE H3-B stimulus §68.6 named and did not try: *drive
the access from a prefetcher in **steady state**, never flushed.*  All three
stimuli that missed the family reached their access through an `EB 00` flush
and a cold refill.  The `skew` shape's block INTERIOR is that steady state.

---

## §7 WHAT THIS CAMPAIGN IS NOT

* **Not a re-opening of the SM3 residue partition.**  L1/L2/L4 and the nine
  catch-all seeds keep their dispositions; the survey counts them where they
  appear and does not chase them.
* **Not an 8080 campaign.**  The corpus is BRKEM-free by construction.  ⚠ It
  is **not 8080-free** — §63.5 found 24 class-A seeds with no `0F FF` in the
  image whose 8080 entry is **still not established** — so class-A landings are
  an exclusion DECLARED IN ADVANCE and COUNTED, never a filter applied after
  the numbers are seen.
* **Not a model campaign.**  The model-only residue is frozen; `sim/` moves
  only where a mechanism is shared, and then it moves first.
* **Not a synthesis campaign.**  No flashing without explicit authorisation.
  ⚠ And when a bitstream IS needed, `standing_gates.md`'s G6 is one Quartus
  draw: the multi-seed worst-of-N gate is **still not built** (SM3 verdict
  §(f)), so a single green build is not closure.
* **Not a claim that the vector axis will find anything.**  §5 registers the
  falsifier that says it did not.

---

## §8 THE INSTRUMENTS, AND THE TRAPS ALREADY KNOWN IN THEM

Read `sw/wvec_shapes.py`'s header before touching this axis.  Four properties
of the rig, each measured off the RTL / C++ / host code, each a place the three
legs do something DIFFERENT:

1. **The file encodings are not the same and the mismatch is silent.**  The TB
   reads its vector with `$readmemh` (HEX); the model reads its vector with
   `fscanf("%d")` (DECIMAL).  A TB-format file handed to the model parses `1f`
   as `1`, fails on `f`, **stops**, and silently runs a truncated vector.
2. **Three different out-of-range behaviours, and the TB's is two.**  Past the
   vector's end the model falls back to the uniform level and the board's
   12-bit `bus_idx` WRAPS; the TB reads 0 from its zero-fill for a SHORT
   vector, but an index at or beyond 4,096 is an **out-of-range read of
   `wvec_arr[0:4095]` whose value the language does not define**.  The rule
   that makes all of it moot: always exactly 4,096 entries, and never let a
   run exceed 4,096 bus cycles (bar **B-5** measures it).
3. **The board's replay RAM is not cleared between runs** — a short load leaves
   the previous run's tail in place and the chip reads it.  Same rule.
4. **The field is five bits, not eight**, in all three legs.  A value above 31
   is not a divergence; it is a false statement in the ledger about what the
   part was told.  The generator refuses to emit one.

**And one more, found in W0's own tool and booked as F-4** — read it before
writing anything that runs the RTL in this campaign:

> ⚠ **`check_seq.CORE` IS PINNED TO `"fsm"`.**  Anything that reaches the TB
> through `check_seq.run_tb` runs the **ARCHIVED FSM CORE**, whatever `--core`
> the calling tool advertises.  That includes **`fuzz_campaign run <cid>
> --tb-only`**.  It is pinned deliberately (the gates that go through it are
> archived gates whose registered figures are FSM figures) and this campaign
> does **not** change it — W1's comparator is the board.  **But no wrfuzz
> number may be taken from a `--tb-only` run and called an `ucore` number.**
> W0's smoke made exactly this mistake, printed the `ucore`'s receipt over the
> FSM's rows, and was caught by the receipt layer.  Invoke `timed_fuzz.tb_bin
> (core)` directly and assert the path.

And the standing instrument rules that apply unchanged: match `s15_census
--core` to the report's core (gap R4); verify a flag exists with `--help`
before trusting a run that used it; `check_enter_nesting` is an archived FSM
gate that ignores unknown flags; look at the DENOMINATOR of every
cross-instrument comparison (the ninth vacuous-gate incarnation).

---

## §9 REVIEW TRAIL

| | |
|---|---|
| **W0 OPENED** | 2026-08-05, from HEAD `1a2a9eff4e` |
| **CODEX** | routed by the coordinator at the W0/W1 boundary — this plan and the corpus pre-registration together |
| **W1** | not started.  **No board has been contacted by this campaign.** |
