# 8086 prefetch article vs V30 class-5: Codex analysis + additional tests
# Source: righto.com/2023/01/inside-8086-processors-instruction.html
# Codex gpt-5.6-sol, thread 019f663c, 2026-07-16

The 8086 rule is a strong new hypothesis, but it does not yet justify implementing a static “3–4 bytes means pause two clocks” rule. The most promising interpretation is narrower: class-5 may be the missing state of a two-clock mid-band delay timer. Your existing `occupied` measurement already weakens the simpler “we counted bytes wrong” explanation.

## 1. Fit against the existing evidence

The match is striking:

- The dominant class-5 error is +2 clocks, exactly the Intel 8086 mid-band delay described by Shirriff.
- The affected boundary is around 3–4 effective bytes.
- Starved queues refill immediately, while full queues stop prefetching—qualitatively the same 0–2 / 3–4 / 5–6 bands.
- Cadence and demand-age predicting the decision at 80–85% could mean they are proxies for the age of an unmodeled two-clock delay.
- Factor-Q showing causal dependence on queue count is consistent with crossing between occupancy bands.
- A timer explains why identical instantaneous counts can produce both GO and PAUSE: one cell has already spent two clocks in the mid-band; another has just entered it.

However, three points prevent calling it proven.

First, the RTL’s `occupied` at an `eval_ext` decision is not merely the stale T4 count. It is:

```text
cnt_next = q_cnt - pop_now + push_now
occupied = cnt_next + infl
```

At `ST_TI`, `infl` should normally be zero, so `occupied` is effectively the post-pop/post-deferred-push count already. See [v30_biu.sv](/home/wickerwaka/src/nec_test/hdl/rtl/core/v30_biu.sv:304) and its queue update at [v30_biu.sv](/home/wickerwaka/src/nec_test/hdl/rtl/core/v30_biu.sv:914). Therefore, if your “50/50 on occupied” census sampled the actual decision row correctly, a count-only band rule is already refuted. The likely missing discriminator is then band-entry age or loader phase—not merely correcting `q_cnt(T4)` to `cnt_next`.

Second, “bulk burst while occupied ≤4” is compatible with the Intel rule only if the two-clock delay has already elapsed while the bus was occupied, or if the V30 timer starts before the free-bus decision. If the rule instead starts a fresh two-clock delay whenever the bus becomes free with 3–4 bytes, the bulk observations contradict it.

Third, the bidirectional errors, especially negative impulses and ±4/5 tails, are not explained by one missing pause alone. Some may be timer phase or remaining commit-grid effects, but that must be demonstrated.

The Intel article also establishes that the 8086 queue is represented by three word registers, byte-half state, pointers, and an empty/full discriminator—not a generic “bytes including in-flight fetch” count. Its documented policy is 0–2 immediate, 3–4 delayed two clocks, and 5–6 blocked. But that is reverse-engineered Intel 8086 behavior, not proof that NEC retained the same BIU implementation. [Ken Shirriff’s 8086 prefetch analysis](https://www.righto.com/2023/01/inside-8086-processors-instruction.html)

My current judgment:

> The article probably identifies the missing *kind of state*: a small queue-band delay/phase state. It does not yet prove the exact V30 thresholds, timer start event, or timer clocking.

## 2. Which queue count should be tested?

Do not choose one definition yet. Score all plausible byte counts at the same decision edge:

| Candidate | Meaning |
|---|---|
| `q_cnt` | Registered bytes before this edge’s pop/push |
| `q_avl` | Bytes currently visible/poppable by the EU |
| `q_cnt - pop_now` | Stored bytes after current pop, before push |
| `cnt_next` | Stored bytes after current pop and deferred push |
| `q_avl - pop_now + q_aged` | Next poppable-byte count |
| `occupied` | `cnt_next + infl`; capacity reserved including in-flight bytes |

The article’s rule most naturally maps to bytes committed to the physical queue registers. In this RTL that is probably closest to `cnt_next`, not `q_avl` or `occupied` in general. But real V30 push visibility may not occur on the same edge as the model, so even `cnt_next` is only a candidate.

The decisive additional field is:

```text
midband_age = clocks continuously spent in candidate count 3–4
```

Also test alternative timer semantics:

- clocks since entering 3–4;
- clocks since the bus first became free in 3–4;
- clocks since the last fetch completed while in 3–4;
- CPU clocks versus free-bus/BIU opportunity clocks;
- timer preserved or restarted across an EU bus access.

That is much more likely to compress the apparent cadence/history dependence than adding more generic history features.

## 3. Prioritized additional tests

### A. Reanalyze every existing opportunity with candidate band FSMs

This is the first and most decisive test. It needs no new chip programs.

For every aligned waited CODE→CODE opportunity, record cycle-by-cycle:

- all six count definitions above;
- `pop_now`, `push_now`, `q_aged`, `push_pend`, `infl`;
- bus state and whether the bus was available for a prefetch;
- exact time each candidate count entered or left 0–2, 3–4, and 5–6;
- chip GO/PAUSE and exact successor CODE T1;
- whether an EU access was pending or gained ownership.

Replay several small candidate FSMs over the traces:

1. Delay starts on entry to 3–4.
2. Delay starts at the first free-bus opportunity in 3–4.
3. Delay starts at prior fetch completion if the settled result is 3–4.
4. Delay advances on every CPU clock.
5. Delay advances only on free BIU opportunity clocks.

The success condition is not merely improved accuracy. Require:

- zero or near-zero collisions on discovery;
- the same rule and thresholds on held-out programs;
- exact prediction of the signed Ti error, including timing-clean opportunities;
- no error-only sampling—the denominator must include all 17,052-style opportunities.

The crucial split is:

```text
candidate count 0–2              -> next free cycle
candidate count 3–4, age < 2     -> pause
candidate count 3–4, age >= 2    -> next free cycle
candidate count 5–6              -> blocked
```

If this becomes collision-free, the earlier “irreducible core” was timer-state aliasing. If identical count, age, bus availability, and EU ownership still produce both outcomes, the Intel rule is insufficient.

### B. Build a controlled V30 “band ladder”

After the retrospective test identifies the leading candidate, confirm it causally on the physical chip.

Construct a branch-flush-anchored linear sequence with:

- predictable one-byte QS pops;
- no EU memory/I/O request near the tested edge;
- a known free-bus opportunity;
- explicit wait-vector control over the preceding CODE fetch.

Target effective queue counts 0 through 6. For counts 3 and 4, independently arrange for the queue to have occupied that band for 0, 1, 2, and 3 clocks before the free-bus edge.

The essential factorial is:

```text
queue count ∈ {2,3,4,5}
band age   ∈ {0,1,2,3}
```

Measure the clocks from the free-bus opportunity to the next CODE T1.

This identifies both the band boundaries and what “delayed two clocks” means operationally. It also prevents accidentally fitting the random-wait corpus’s queue trajectories.

### C. Directly distinguish `q_cnt`, `q_avl`, `cnt_next`, and `occupied`

Create or mine matched pairs such as:

- Same `q_cnt=2`, but:
  - `push_now=0` → `cnt_next=2`;
  - `push_now=2`, `pop_now=1` → `cnt_next=3`;
  - `push_now=2`, `pop_now=0` → `cnt_next=4`.
- Same `cnt_next`, different `q_avl`, caused by `q_aged`.
- Same `cnt_next`, different `infl`, so only `occupied` differs.
- Same count and band age, but different prior wait count.

Interpretation:

- Follows `cnt_next`: settled physical queue bytes.
- Follows `q_avl`: loader-visible/poppable bytes.
- Follows `occupied` when only `infl` changes: capacity reservation includes in-flight bytes.
- Follows band age after all counts are matched: explicit delay state.
- Follows prior wait even after count and age match: additional bus-grid phase exists.

This should precede any RTL change.

### D. Verify odd-address fetch behavior, but separately

It is worth testing because an incorrect HL/half-word reconstruction could corrupt queue-byte accounting after redirects. On the 8086, an odd-target jump fetches the even word at target−1 and discards its low byte. [Shirriff’s discussion of the HL flip-flop and odd-address targets](https://www.righto.com/2023/01/inside-8086-processors-instruction.html)

Use matched even/odd branch targets and observe:

- first CODE bus address after flush;
- whether the odd target causes an even-address word fetch or an odd byte fetch;
- subsequent CODE addresses;
- QS F/S sequence;
- timing under N=0 and waited fetches.

This is lower priority than the band FSM because class-5’s linear resumes are overwhelmingly even-address fetches. Until verified, exclude redirect/odd-successor cells from the band-law fit.

### E. Loader-empty and microcode controls

These are secondary but may explain the q0/starvation behavior:

- Empty versus one-byte queue: measure spacing between QS F/SC-equivalent consumption events.
- Matched instruction streams using one versus two instruction bytes: determine whether the apparent starvation-age threshold is loader sequencing rather than BIU policy.
- Relative branches/calls/returns: measure prefetch suspension, queue flush, redirect T1, and any fixed passive clocks.
- Place a pending EU access during the 3–4 delay: confirm that EU ownership wins and determine whether the band timer keeps running, pauses, or restarts.

The 8086’s FC/SC, MT, SUSP, FLUSH, CORR, NXT, and RNI mechanisms are useful test generators, but their internal implementation should not be presumed on V30. [Shirriff’s loader and microcode discussion](https://www.righto.com/2023/01/inside-8086-processors-instruction.html)

## 4. Probable RTL shape if the test succeeds

If the physical V30 exhibits a deterministic band-plus-age rule, the implementation should be a small BIU policy state machine plugged into Phase R’s canonical grant hook—not a history fingerprint and not a pause-only exception.

Conceptually:

```text
true_q_bytes = measured winning queue-count definition

LOW   = true_q_bytes <= 2
MID   = true_q_bytes in 3..4
FULL  = true_q_bytes >= 5

on measured MID-entry/start event:
    mid_delay = 2

advance mid_delay according to measured clock semantics

prefetch grant:
    EU/split ownership       -> no prefetch
    LOW                      -> grant at next legal slot
    MID && mid_delay != 0    -> pause
    MID && mid_delay == 0    -> grant
    FULL                     -> block
```

Reset or recompute the timer on flush, redirect, queue-band transition, and possibly successful prefetch; the measurements must determine those details. Keep overflow protection and `q_aged` safety separate from the policy timer.

Critically, this should be a unified w0..wN rule if it is genuinely the V30’s queue policy. A wait-only gate would preserve w0 mechanically but risk encoding the wrong architecture. At w0, the two-clock delay may be hidden because it overlaps T-states or expires before the next free slot—that is the behavior the model should reproduce naturally.

A safe implementation sequence would be:

1. Add a shadow true-byte/band/timer predictor with no output effect.
2. Verify its predicted actions against all chip opportunity traces, including w0.
3. Confirm the controlled band ladder.
4. Repoint `selected_prefetch_grant` at the predictor.
5. Require:
   - w0 `169000/169000`;
   - w1/w3 full goldens;
   - exact band-ladder timing;
   - no new negative gap-error tail;
   - lower signed and absolute class-5 mass;
   - branch/flush, EU ownership, split/odd, INTA, and HALT unchanged;
   - held-out explicit-vector replay.

If the shadow predictor changes legal w0 behavior, do not special-case w0 immediately. That means either the timer’s start/clock semantics are wrong or the NEC BIU does not implement Intel’s policy.

Bottom line: reopen class-5. The article provides a plausible compact missing state—a two-clock mid-band age—not merely a different occupancy threshold. First run the full-opportunity band-age replay. That single analysis can either turn the 50/50 boundary deterministic or quickly falsify the clean 8086 mapping before further RTL work.
