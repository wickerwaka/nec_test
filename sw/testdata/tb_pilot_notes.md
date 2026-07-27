# TB-only soup pilot (task #29 Phase 4)

Board-free Verilator pilots run through the campaign driver
(`fuzz_campaign.py run --tb-only`). Purpose: validate contained-mode
fall-through, freeze the `nmax_eff` capture-budget constant, and shake out the
TB-side event/wrand plumbing under the driver. No board.

## Main pilot: contained fall-through (N=1000, soup, w0, no-evt, strict)

`run PILOT --tb-only --force-tier soup --contained --strict --w0 --no-evt --session-seeds 1000`

- **done-in-window: 959/1000 = 95.9%** (gate >= 95%)
- **timeouts: 0/1000 = 0.00%** (gate < 1%)
- done_idx: min 524, median 1028, p95 1491, **max 2714** (<< the 4096-row window)
- all verdicts SUCCESS (TB-vs-TB self-compare exercises the full inline
  classifier + schema + fsync'd jsonl path)

`strict` = the contained fall-through generation used for THIS gate: it
suppresses the deliberate no-done breadth classes (BRKEM 8080-entry, TF
single-step storm, undoc opcodes, and the 40%-random DS load whose subsequent
windowed write escapes the window). Those classes are first-class campaign
features that classify window-only by design; they are simply not part of the
"does contained mode reliably reach the stub" question.

### Default-config no-done breakdown (same 1000 seeds, non-strict)

For reference, the FULL campaign config (non-strict) reaches done on only
64.3% at w0 - and every no-done seed is an intentional/accepted class:

| class | count | note |
|---|---|---|
| BRKEM (0F FF) | 168 | enters 8080 mode -> no chip done (per-run reset recovers) |
| TF single-step | 7 | deliberate step storm |
| random-DS escape | 182 | 40%-random DS0/DS1 load + windowed write -> window-only |
| reaches done | 643 | |

The plan's "~15% won't reach the stub" is really ~36% under these knobs,
dominated by BRKEM (p_brkem=0.005/instruction ~= 17%/seed over ~50 instrs) and
the random-DS load. **Flag for Phase-5 tuning review:** if 17% of board
captures landing in 8080-entry (recovered by per-run reset) is too much wasted
board time, lower `p_brkem`.

## nmax_eff scaling constant - FROZEN C = 4

`nmax_eff = max(nmin, nmax * C / (C + wmax))`, base nmax=80.

- At w0 (wmax=0 -> nmax_eff=80) the contained done_idx peaks at 2714 rows, a
  ~34% margin under the 4096-row window -> the base budget holds with headroom.
- C=4 is physically grounded: a bus cycle is T1-T4 = 4 clocks, so a wmax equal
  to C doubles per-access time and halves the instruction budget.
- Cross-check under waits (strict wrand N=200, wmax 1/3/7): in-window done_idx
  stayed <= 3280 (< 4096) with the C=4 coupling applied - the budget shrinks
  fast enough to keep done in-window as waits stretch each access.

C=4 is frozen (NMAX_SCALE_C in fuzz_campaign.py). A budget-coupled wrand board
re-measurement rides the Phase-5 pilot (per the coordinator's Phase-3 note).

## Plumbing shakeouts (evt + wrand, strict contained)

- **evt pilot** (N=200, `--force-evt`, INT/NMI + HALT): evt injection flows
  through run_tb; armed-INT HALT seeds wake and reach done. 159/200 done.
- **wrand pilot** (N=200, `--force-wrand 1,3,7`): seeded random waits flow
  through; 179/200 done, done_idx max 3280 in-window.

Both completed with no crash and no false circuit-breaker; the driver handled
every failure gracefully as a quarantine line.

## DISCOVERY: F7a COLD-ARM assertion under interrupt injection

The evt pilots surfaced a **repeatable RTL assertion** (13 seeds), reproduced
directly via `run_tb` (not a driver artifact):

```
F7a COLD-ARM VIOLATION: state=0 q_aged=0 push_pend=2 q_cnt=0 occupied=2
%Error: hdl/rtl/core/v30_biu.sv:1076: Assertion failed in ...u_biu
```

It fires when a pin event (seen on NMI pin=1, also INT) arms while the BIU has a
pending queue push in this exact cold/idle state (push_pend=2, q_cnt=0,
occupied=2). The curated suites never inject interrupts in this queue state, so
it was invisible - this is precisely the coverage-vacuity class the campaign
targets. hdl/ is frozen and Phase-5 board work is gated on review, so this is
reported, NOT fixed here. First reproducer: `PILOT` k=10001 (cfg_hash
e86076960685, evt pin=1 delay=125, w1). The driver quarantines these cleanly
(no circuit-breaker trip; a real run would bank them as provenance).

## Standing gates re-run at the phase boundary

- test_fuzz_classify.py: PASS
- test_fuzz_accept.py: PASS
- check_ff_t4.py: PASS 9/9 (no check_seq semantics change)
