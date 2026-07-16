# Class-5 PHASE S design (Codex gpt-5.6-sol, thread 019f663c)

Partial PAUSE-ONLY veto of the eval_ext resume, gated by a ZERO-FALSE-PAUSE
predicate frozen from an opportunity audit. GO S0-S2; GO S3 only if the audit
finds a zero-FP pause predicate with >=10% baseline positive-mass coverage on
held-out AND fresh corpora. NO-GO if coverage negligible or any fresh false
pause. Realistic payoff 10-30% (likely <15%) of positive class-5 mass.
Do NOT force GO; leave the ambiguous core (popc=2,cad<=9,dage17-35) on legacy.

## Verdict

A partial, pause-only Phase S is the only defensible local policy. Do not force GO, and do not touch ambiguous cells.

However, two blockers precede the behavioral edit:

1. The current `selected_prefetch_grant` hook is declared but not consumed. Slot requests still use `pick_ext`/`pick_any`.
2. The supplied “confident” statistics establish a high-confidence GO region, but not yet a zero-false-positive PAUSE region. `cad>=16` alone is only approximately 85% pause—far too risky given the prior over-pause failure.

Phase S should proceed only after an opportunity audit finds a pause predicate with zero chip-GO observations across discovery and held-out corpora.

# 1. Partial policy: yes, pause-only

The correct fallback is legacy:

```text
Ambiguous cell     → legacy grant
Confident GO       → legacy grant
Non-boundary cell  → legacy grant
Confident PAUSE    → suppress one eval_ext prefetch opportunity
```

Do not implement a force-GO path. Forcing GO could bypass:

- Queue capacity.
- `q_aged`.
- EU reservation priority.
- Flush/hold logic.
- Existing `prefetch_ext` arbitration exceptions.

Legacy already handles the bulk GO population correctly.

A pause-only veto has a useful safety property:

- It can fix positive gap errors where the model is early.
- It cannot directly make an existing early model even earlier.
- Its entire risk is measurable as new or worsened negative gap impulses.

The global `pf_lim` experiment failed because it applied to a broad population. That does not refute a high-precision veto. It establishes the required stop condition: no observed false pause in independent data.

## Ambiguous core

Leave these untouched:

```text
popc=2
cad<=9
dage approximately 17..35
```

The observed 24/14 split cannot support a deterministic override.

# 2. First fix the hook plumbing

At current HEAD, the hook is not actually live:

- `selected_prefetch_grant` is only declared at [v30_biu.sv](/home/wickerwaka/src/nec_test/hdl/rtl/core/v30_biu.sv:692).
- `req_eval_ext` still depends on `pick_ext`.
- Plain slots still depend on `pick_any` ([v30_biu.sv](/home/wickerwaka/src/nec_test/hdl/rtl/core/v30_biu.sv:620)).

There is also a potential circularity:

```text
slot_is_eval_ext depends on slot_fire
slot_fire depends on req_eval_ext
req_eval_ext would depend on selected_prefetch_grant
selected_prefetch_grant would depend on slot_is_eval_ext
```

Do not wire it that way.

## Phase S0: behavior-preserving grant integration

Define slot context independently of whether a slot fires:

```systemverilog
wire eval_ext_candidate =
    state == ST_TI && !nxt_live && eval_ext && !flush_defer;
```

Preserve the exceptional `flush_hold` use of `prefetch_ext` separately. It occurs after the original eval window and must not accidentally switch to `prefetch_ok`.

Create:

```systemverilog
wire legacy_evalext_pf_grant = prefetch_ext;
wire legacy_plain_pf_grant   = prefetch_ok;

wire selected_evalext_pf_grant = legacy_evalext_pf_grant; // S0
wire selected_plain_pf_grant   = legacy_plain_pf_grant;   // unchanged in Phase S
```

Then construct slot-local pick-valid signals without changing priority:

```systemverilog
wire pick_evalext =
    want_half2 || want_eu || selected_evalext_pf_grant;

wire pick_plain =
    want_half2 || want_eu || selected_plain_pf_grant;
```

Use:

- `pick_evalext` only for `SLOT_EVAL_EXT`.
- `pick_plain` for ordinary staged slots.
- Preserve existing `pick_ext` semantics for `flush_hold` until separately proven.
- Preserve explicit EU-only `defer_idle`.
- Preserve all far-flush rules exactly.

The descriptor still uses the existing priority:

```text
want_half2 > want_eu > prefetch
```

S0 must pass all Phase-R equality gates before adding counters or policy.

# 3. Exact Phase-S state

Use three small saturating history fields and one one-shot waited token.

## A. Fetch cadence

```systemverilog
reg [5:0] clocks_since_code_t1;
reg [5:0] last_code_cadence;
```

Behavior:

```text
Every CE clock:
    clocks_since_code_t1 saturates upward.

On every actual CODE T1:
    last_code_cadence    = clocks_since_code_t1
    clocks_since_code_t1 = 0
```

The policy uses `last_code_cadence`, which is the interval between the predecessor fetch and the fetch before it. This matches the analysis definition at [class5_streamcadence.py](/home/wickerwaka/src/nec_test/sw/class5_streamcadence.py:66).

Count actual `state==ST_T1 && cur_fetch`, not displays or `nxt_live`.

A six-bit saturating count is sufficient for thresholds around 9–29 and avoids wraparound turning a very old cadence into a “tight burst.”

## B. Demand age

```systemverilog
reg [5:0] demand_age;
```

Match the analysis semantics exactly:

```text
If q_cnt <= 1:
    demand_age = 0
Else:
    demand_age saturates upward
```

The tool defines age as clocks since `q_cnt` was last at or below one ([class5_streamcadence.py](/home/wickerwaka/src/nec_test/sw/class5_streamcadence.py:40)).

Be explicit about edge semantics. Because the policy is evaluated after a waited predecessor completes, latch the age visible at that predecessor’s T4. Do not use live `demand_age` several clocks later.

## C. Waited-resume snapshot

```systemverilog
reg       waited_resume_active;
reg [5:0] resume_cadence;
reg [5:0] resume_demand_age;
reg [2:0] resume_qcnt;
reg [3:0] resume_occ;       // diagnostic initially
reg [3:0] resume_popcnt;    // diagnostic/predicate only if validated
```

Arm at the T4 of a waited, sequential, non-discarded CODE fetch:

```text
state == ST_T4
cur_fetch
!evald                   // waited completion; zero-wait already evaluated at T3
!fetch_discard
!q_flush
```

Latch pre-push state:

```text
resume_cadence   = last_code_cadence
resume_demand_age= demand_age
resume_qcnt      = q_cnt
resume_occ       = occupied or a separately chosen T4 diagnostic
resume_popcnt    = pop_cnt
```

`q_cnt` must be the registered T4 value, not `cnt_next` after the deferred push.

## D. One-shot lifetime

This veto must apply only to the first `eval_ext` prefetch opportunity after that waited fetch.

Clear `waited_resume_active` on:

- The `eval_ext` cycle, whether vetoed or allowed.
- Any intervening EU bus-cycle commit.
- Any CODE commit.
- Flush or redirect.
- Fetch discard.
- Reset.

Do not leave the predicate active until a CODE commits. If the veto suppresses CODE and the token stays active, it could suppress every later opportunity indefinitely.

# 4. Exact grant equation

First define the narrow boundary:

```systemverilog
wire resume_boundary =
    waited_resume_active &&
    eval_ext_candidate &&
    legacy_evalext_pf_grant &&
    !want_half2 &&
    !want_eu &&
    resume_qcnt == 3'd2;
```

Whether `resume_qcnt==2`, `pop_cnt`, or an `occ` qualifier belongs here must be frozen from the opportunity audit. Do not use `occ~4` as an imprecise range in RTL.

Then:

```systemverilog
wire confident_pause = resume_boundary &&
                       pause_history_predicate;

wire resume_slot_grant =
    confident_pause ? 1'b0 : legacy_evalext_pf_grant;

wire selected_evalext_pf_grant =
    waited_resume_active
        ? resume_slot_grant
        : legacy_evalext_pf_grant;
```

Plain-slot grant remains legacy:

```systemverilog
wire selected_plain_pf_grant = prefetch_ok;
```

Thus a vetoed eval slot tears down normally, and the following ordinary slot reuses legacy policy. This produces exactly one pause decision without introducing a new delivery path.

## Threshold policy

Do not hardcode `cad>=16` alone. Its measured false-GO rate is about 15%.

The first predicate worth auditing is:

```text
cad >= 16 AND demand_age >= 29
```

Potentially also require the exact consuming boundary:

```text
resume_qcnt == 2
resume_popcnt == 2
```

But thresholds must be selected by a zero-false-pause constraint, not headline accuracy.

Perform a grid search over:

```text
cad threshold:  12..24
dage threshold: 20..40
optional popcnt exact/range
q_cnt fixed at 2
```

Objective:

```text
maximize corrected positive gap mass
subject to:
    chip-GO count == 0 in discovery
    chip-GO count == 0 in held-out
```

Then freeze the predicate and run a third fresh-program corpus. If the fresh corpus contains any veto cell where the chip goes, do not ship that predicate.

The existing uniform-wait stream-cadence corpus is insufficient by itself. It has only five default programs and uniform waits ([class5_streamcadence.py](/home/wickerwaka/src/nec_test/sw/class5_streamcadence.py:81)). Threshold selection must include the explicit random-wait vectors that define the actual target.

# 5. Staged implementation plan

## S0 — Integrate selected grant, legacy-only

- Remove circular `slot_is_eval_ext` dependency.
- Add candidate-context grant selection.
- Route eval-ext request through `selected_evalext_pf_grant`.
- Keep it equal to `prefetch_ext`.

Gate:

```text
w0 169000/169000
w1 1200/1200
w3 1200/1200
Phase-R baseline trace equality
```

## S1 — Add counters, no behavioral use

Add cadence, demand age, and waited snapshot state. Keep selected grant legacy.

Add debug dump fields.

Gate all goldens and Phase-R trace equality. Internal states may differ only by the newly added unused registers.

## S2 — Shadow predicate

Compute `resume_boundary` and `confident_pause`, but do not veto.

Log every shadow-veto opportunity:

```text
seed/vector
slot clock
qcnt/occ/popcnt
cadence/dage
chip action
baseline gap_error
```

Run discovery, held-out, and fresh corpora. Require zero chip-GO observations before S3.

## S3 — Enable one-shot eval-ext veto

Only change:

```systemverilog
selected_evalext_pf_grant =
    confident_pause ? 1'b0 : legacy_evalext_pf_grant;
```

Do not change plain grant, display, delivery, flush, or EU policy.

Run the full validation suite. Revert immediately on any new held-out false pause.

# 6. Validation criteria

The proposed criterion is close but needs more precise signed accounting.

## Mandatory functional/cycle gates

- w0 `169000/169000`.
- w1 `1200/1200`.
- w3 `1200/1200`.
- No bus type/address sequence divergence.
- Flush, EU, interrupt, INTA, HALT targeted traces unchanged except targeted CODE timing.
- Fabric/TB equality before flash.

## Signed gap-error acceptance

Measure paired baseline versus patched intervals.

Track separately:

```text
fixed_positive:
    baseline gap_error > 0
    patched error closer to zero

new_negative:
    baseline gap_error == 0
    patched gap_error < 0

worsened_negative:
    patched gap_error more negative than baseline

overshot_positive:
    baseline positive becomes patched negative
```

Hard gates:

- `new_negative == 0` on discovery and held-out.
- `worsened_negative == 0`.
- `overshot_positive == 0`.
- Positive impulse mass decreases.
- Total `|mass|` decreases.
- No new transition class.
- Worst-case peak excursion does not increase.

Signed net moving toward zero is secondary. Net can improve while positive and negative tails both get worse due cancellation. Optimize absolute mass and tails first.

## Opportunity-level acceptance

Every actual `confident_pause` firing must map to a chip PAUSE in:

1. Discovery.
2. Held-out by program.
3. Fresh seeds never used for threshold selection.
4. Uniform and random wait backgrounds.
5. wmax 1, 3, 7, and preferably 15.

This is the Phase-S equivalent of Gate A.

# 7. Is it worth doing?

Only as a narrowly scoped experiment with a strict stop rule.

The apparent 85% ceiling is not the expected improvement. That is classification accuracy within a selected boundary population, not coverage of total drift mass. A zero-false-positive intersection such as `cad>=16 && dage>=29` will cover less.

Realistic outcomes:

- Best plausible high-precision reduction: roughly 10–30% of positive class-5 mass.
- More likely if zero-FP coverage is sparse: under 10–15%.
- If the pause region retains a 15% false-positive rate, risk/reward is poor because one false pause can inject a 2–3-clock negative impulse and erase several correct decisions.

My go/no-go:

- **GO** through S0–S2.
- **GO S3** only if the shadow opportunity audit finds a pause predicate with zero false pauses on held-out and fresh corpora and meaningful coverage—preferably at least 10% of baseline positive impulse mass.
- **NO-GO** if zero-FP coverage is negligible or any fresh false pause appears.

That leaves the irreducible ambiguous core on the proven legacy behavior and avoids repeating the blanket-threshold failure.
