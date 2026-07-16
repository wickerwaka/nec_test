# Class-5 band+age replay (Codex "Test A") — findings

Tool: [sw/class5_bandage.py](/home/wickerwaka/src/nec_test/sw/class5_bandage.py)
Raw per-opportunity dump: `sw/class5_bandage.jsonl.gz` (8220 rows), run log
`sw/class5_bandage.log`. Board = ground truth; model internals label the
aligned prefix. Discovery seeds 90000-90007, held-out 91000-91005; waits
w1/w2/w3 + LFSR (4,3) and (7,7). NO RTL changed.

## Verdict: mid-band aliasing is REAL and recoverable; low-band residual is NOT it

Codex's hypothesis was that the class-5 "50/50 irreducible" boundary is
**timer-state aliasing** — identical instantaneous queue counts give both GO and
PAUSE because they differ in **band-entry age**. This is **confirmed for the
mid-band (queue count 3-4)** and **refuted as the explanation for the low-band
(count 0-2) residual**.

Population: 8220 aligned CODE->CODE prefetch-resume opportunities (disc 4601,
held 3588, after dropping 31 idle==2 ambiguous). GO ~96%, PAUSE ~4%.

### 1. MID-band (q_cnt in 3-4): the 50/50 boundary becomes DETERMINISTIC

Best count = `q_cnt`, timer = **clocks continuously spent in the 3-4 band, per
CPU clock** (`entry_cpu`). Rule that fits:

```
q_cnt in 3-4, band-age <  2  -> GO   (chip resumes immediately)
q_cnt in 3-4, band-age >= 2  -> PAUSE
```

| corpus | mid-band opps | rule mispredictions | collision |
|---|---|---|---|
| discovery | 189 | 1 | 0.53% |
| **held-out** | 169 | **0** | **0.00%** |

The same instantaneous q_cnt=3 (or 4) that previously produced BOTH GO and PAUSE
is fully separated by band-entry age. This is exactly the missing state Codex
predicted.

**Polarity is INVERTED vs Intel 8086.** Intel: fresh 3-4 -> delay 2 clocks then
go. V30: fresh-in-band (age<2) -> GO, aged-in-band (age>=2) -> PAUSE. Codex
explicitly allowed that NEC need not retain Intel's exact policy; the *kind of
state* (a 2-clock band-age) is the same. `q_cnt-pop` and `q_avl-pop+aged` give
nearly-as-clean separation; `occupied` and `cnt_next` do NOT cleanly separate the
mid-band (both age buckets stay mixed).

FULL-band (q_cnt>=5): 100% PAUSE (blocked) on both corpora — trivially
deterministic.

### 2. LOW-band (q_cnt 0-2): residual is EU-drain, NOT band-age

The aggregate minority mass floors at ~1.2-1.4% for every (count, timer) combo
because it is dominated by a **separate** low-band boundary that age cannot touch
(age only exists inside 3-4):

| corpus | low-band opps | GO | PAUSE | pause rate | eu_consuming on those pauses |
|---|---|---|---|---|---|
| discovery | 4399 | 4336 | 63 | 1.43% | 63/63 = 1 |
| held-out | 3404 | 3355 | 49 | 1.44% | 48/49 = 1 |

**Every** low-band pause has `eu_consuming=1` (EU actively draining the queue).
But `eu_consuming=1` is not sufficient (across the corpus eu_consuming=1 is
~1300 GO vs ~40 PAUSE), so adding it to the key only trims the residual to
~1.0-1.2%; the `(q_cnt<=2, eu_consuming=1)` cell stays genuinely mixed. This is
the pre-existing "irreducible q_cnt=2 boundary" from the streamcadence /
pauseaudit work — a low-band/EU-ownership phenomenon, **not** mid-band timer
aliasing.

## Bottom line

- The 8086 band+age mapping is **sufficient and held-out-clean for the mid-band
  (3-4) component** of class-5: a `(q_cnt, clocks-in-3-4-band, >=2)` rule with
  inverted polarity turns that 50/50 boundary deterministic (0/169 held-out
  collisions). Class-5's mid-band mass is recoverable and a shadow RTL predictor
  can be built from the dump.
- The 8086 band+age mapping is **insufficient for the low-band (0-2) residual**:
  identical `(count, age, bus, EU-ownership)` still yields both GO and PAUSE
  there. That residual is gated by EU queue-consumption at q_cnt<=2 and remains at
  the observable floor — a distinct mechanism to be attacked separately (band B/E
  controlled ladders), not by the mid-band timer.

Timer-semantics note: all six start-event x clock-domain variants
(entry/freefirst/fetchdone x cpu/free) collapse to the same mid-band result,
because within a contiguous 3-4 run the model's bus is essentially never idle
before the resume edge — so "per free-bus slot" == "per CPU clock" here.
`entry_cpu` is the simplest and is the recommended timer.
