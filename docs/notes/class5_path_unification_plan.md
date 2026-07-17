# Class-5 eval_ext/do_commit PATH UNIFICATION plan (Codex gpt-5.6-sol, thread 019f663c)

Phase R = pure behavior-preserving refactor (canonicalize the commit
decision). Phase S = LATER plug the measured class-5 resume policy into the
canonical slot arbiter. Phase R succeeds ONLY if ALL traces (incl class-5
controls fz90007/fz90011) are byte-identical. Gate after EVERY stage:
w0 169000/169000, w1 1200/1200, w3 1200/1200, targeted traces identical.
One commit per stage/substage; on failure revert ONLY the latest, do NOT
patch around. Do NOT add any class-5 demand/momentum logic in Phase R.

## Critical clarification

A genuinely behavior-preserving refactor cannot fix the fz90011 class-5 timing error. If the refactor removes path jitter or changes a T1 clock, it has become a behavioral scheduler change.

Therefore split the work into:

- **Phase R:** canonicalize decisions and commit plumbing with zero observable change.
- **Phase S:** later plug the measured class-5 resume policy into the canonical slot arbiter.

Phase R succeeds only if class-5 traces are also byte-for-byte unchanged. That gives Phase S a clean, single policy hook and makes any later timing change attributable.

# 1. Exact target structure

Create three distinct concepts.

### A. Canonical commit descriptor

Define one packed descriptor containing everything needed for a bus cycle:

```systemverilog
typedef struct packed {
    logic [2:0]  bus_type;
    logic [19:0] addr;
    logic        fetch;
    logic        wr;
    logic        swap;
    logic        split1;
    logic        split2;
    logic        wrap;
    logic [15:0] wdata;
    logic [1:0]  seg;
    logic        ube_n;
    logic [1:0]  kind;
} commit_desc_t;
```

Build exactly one combinational `pick_desc` from the existing `pick_*` wires. Initially this is a pure alias:

```text
pick_desc.bus_type = pick_type
pick_desc.addr     = pick_addr
...
```

Do not change `want_half2`, `want_eu`, `prefetch_ok`, or `prefetch_ext` during Phase R.

### B. Canonical slot decision

Represent every possible commit opportunity as:

```systemverilog
typedef enum logic [...] {
    SLOT_NONE,

    // Staged: descriptor goes to nxt_* first.
    SLOT_T3_EVAL,
    SLOT_TI_PLAIN,
    SLOT_T4_FLUSH_STAGED,

    // Direct: descriptor is displayed now and becomes cur_* / T1 next.
    SLOT_EVAL_EXT,
    SLOT_FF_TI,
    SLOT_DEFER_IDLE,
    SLOT_FLUSH_HOLD,
    SLOT_DEFER_T4,
    SLOT_FF_T4
} slot_id_t;

typedef enum logic {
    COMMIT_STAGED,
    COMMIT_DIRECT
} commit_mode_t;
```

The canonical decision is:

```systemverilog
slot_fire
slot_id
slot_mode
slot_desc
```

During Phase R, `slot_fire` must reproduce the old expressions exactly. Do not make every slot use the same eligibility predicate yet:

```text
SLOT_EVAL_EXT:
    legacy grant = pick_ext && !flush_defer

ordinary staged slots:
    legacy grant = pick_any

SLOT_DEFER_IDLE:
    legacy grant = want_eu

SLOT_FLUSH_HOLD:
    legacy grant = pick_ext && pick_fetch

SLOT_DEFER_T4:
    legacy grant = eu_req && eu_ready

far-flush slots:
    preserve their exact existing pick_any/flush/evald conditions
```

This is one decision representation, not yet one universal policy.

### C. Two descriptor delivery functions

Preserve the physical timing difference:

```text
commit_staged(desc):
    desc → nxt_*
    nxt_valid = 1
    status/address display via nxt_live
    T1 follows through existing nxt_live transition

commit_direct(desc):
    desc → cur_*
    state → ST_T1
    status/address displayed during the current special slot
```

Both consume the same `slot_desc`. Only delivery timing differs.

Do not collapse direct delivery into `nxt_*`; doing so changes T1/display timing.

## Slots that legitimately stay direct

These must remain one-clock-ahead display paths:

- `eval_ext`: picked cycle displays during the deferred-completion idle row.
- `ff_show`: far-flush redirect displays with QS=E during the idle flush row.
- `ff_t4`: zero-wait far flush displays target during the current T4.
- `defer_t4`: early-ready EU request displays during T4.
- `defer_idle`: armed reader/IVT request displays during the current Ti.
- `flush_hold`: near-flush redirect displays during the held Ti, exactly one idle after the rejected `eval_ext` slot.

Evidence for these display laws is concentrated in [v30_biu.sv](/home/wickerwaka/src/nec_test/hdl/rtl/core/v30_biu.sv:735), [v30_biu.sv](/home/wickerwaka/src/nec_test/hdl/rtl/core/v30_biu.sv:862), and the display mux at [v30_biu.sv](/home/wickerwaka/src/nec_test/hdl/rtl/core/v30_biu.sv:1111).

## Slots that remain staged

- Zero-wait `eval_at_t3` via `do_commit`.
- Plain `ST_TI && pick_any`.
- Waited/fallback T4 flush staging where the current code calls `do_commit`.

# 2. Incremental implementation stages

Each stage should be its own commit. Stop immediately on any gate failure.

## Stage R0 — Freeze the baseline

No RTL changes.

Record:

- HEAD commit.
- Verilator build checksum if convenient.
- Full w0/w1/w3 totals.
- Raw traces for targeted cases.
- Current Factor-W and anchortrace outputs for fz90007 and fz90011.
- A small explicit-WVEC random replay set.

Commands:

```bash
python3 sw/check_core.py --build --opcodes all \
  --suite-dir tests/v30/v0.1

python3 sw/check_core.py --opcodes all \
  --suite-dir tests/v30/v0.1-w1 --waits 1

python3 sw/check_core.py --opcodes all \
  --suite-dir tests/v30/v0.1-w3 --waits 3
```

Expected:

```text
w0 169000/169000
w1 1200/1200
w3 1200/1200
```

Save baseline per-cycle output for later exact diffing.

## Stage R1 — Add the descriptor as an unused alias

Add `commit_desc_t pick_desc` and assign every field from the existing `pick_*` wires.

Do not connect it to sequential logic.

Add simulation-only assertions that every descriptor field equals its source wire. This is the smallest possible first step and must change nothing.

Gate:

- Build/lint.
- Full w0/w1/w3.
- Raw baseline trace diff: zero changed rows.

## Stage R2 — Parameterize staged capture only

Replace `do_commit()` with:

```systemverilog
task automatic stage_commit(input commit_desc_t d);
```

It writes `d.*` into `nxt_*`.

Initially every caller invokes:

```systemverilog
stage_commit(pick_desc);
```

Leave side effects explicit at the caller or clearly inside the task:

- Fetch descriptor: advance `fetch_off`.
- New EU access, not split-half continuation: assert `eu_started`.
- Do not double-apply either side effect.

The current side effects are in [v30_biu.sv](/home/wickerwaka/src/nec_test/hdl/rtl/core/v30_biu.sv:522).

Gate full w0/w1/w3 and trace equality.

## Stage R3 — Factor direct-entry descriptor loading

Create:

```systemverilog
task automatic enter_t1_direct(input commit_desc_t d);
```

It should only perform the mechanically common operations:

```text
state      <= ST_T1
tw_any     <= 0
evald      <= 0
cur_*      <= d.*
ube_n      <= d.ube_n
```

Keep source-specific side effects outside initially:

- `fetch_off` advancement.
- `eu_started`.
- `defer_idle` clearing.
- `flush_hold` clearing.
- `defer_t4` clearing.

Convert one site per substage:

1. ST_TI combined direct-entry block.
2. ST_T4 `defer_t4`.
3. ST_T4 `ff_t4`.

Run all gates after each conversion. Do not convert all three before testing.

## Stage R4 — Name every slot request without consuming it

Define exact aliases:

```text
req_eval_ext
req_ff_ti
req_defer_idle
req_flush_hold
req_defer_t4
req_ff_t4
req_t3_eval
req_ti_plain
req_t4_flush_staged
```

Each must be textually equivalent to its current condition.

Add simulation assertions comparing each alias to a retained `legacy_*` expression. No state-machine changes yet.

Examples:

```text
req_eval_ext =
    state==ST_TI && !nxt_live &&
    eval_ext && pick_ext && !flush_defer

req_ti_plain =
    state==ST_TI && !nxt_live &&
    !direct_request &&
    !flush_defer &&
    !eval_ext &&
    pick_any
```

Be careful: state-machine priority is part of the condition. A bare `pick_any` is not equivalent to the actual plain-idle slot if `nxt_live`, `eval_ext`, or a direct exception wins first.

## Stage R5 — Build the canonical slot arbiter in shadow mode

Create combinational `slot_fire`, `slot_id`, `slot_mode`, and `slot_desc`, but do not connect them to the state machine.

The priority must mirror the current state branches exactly.

For `ST_TI`:

1. Existing `nxt_live` consumption remains above new-slot arbitration.
2. `SLOT_EVAL_EXT`, `SLOT_FF_TI`, `SLOT_DEFER_IDLE`, and `SLOT_FLUSH_HOLD` use the same effective OR/priority as today.
3. `flush_defer` arms `flush_hold`; it is not itself a commit.
4. An empty `eval_ext` performs teardown.
5. `SLOT_TI_PLAIN` stages through `nxt_*`.
6. Early-reader arming remains after the plain decision.

For `ST_T3/TW`:

- `SLOT_T3_EVAL` exists only at `eval_at_t3 && pick_any`.

For `ST_T4`:

- `defer_t4` retains priority.
- Existing `nxt_live` retains priority.
- `ff_t4` remains direct.
- Flush fallback remains staged.
- Waited cycles still arm `eval_ext`.

Add shadow assertions:

```text
legacy direct branch taken  == slot_fire && slot_mode==DIRECT
legacy do_commit called      == slot_fire && slot_mode==STAGED
legacy source class          == slot_id expected for that branch
slot_desc                    == pick_desc
```

If simultaneous legacy direct causes can occur, retain source bits rather than assuming exclusivity. Assert and inventory overlaps before assigning a strict priority.

Gate full suites and traces.

## Stage R6 — Consume the canonical decision, preserving delivery mode

Replace the site-specific commit bodies with:

```text
if slot_fire && slot_mode==DIRECT:
    enter_t1_direct(slot_desc)

if slot_fire && slot_mode==STAGED:
    stage_commit(slot_desc)
```

Keep non-commit actions in their original branches:

- `flush_hold` arming/clearing.
- `defer_idle` arming/clearing.
- Fetch teardown.
- Queue push scheduling.
- `eu_hand`.
- `fetch_discard`.
- `eval_ext` lifecycle.
- `e_wait`.

Convert one state at a time:

1. ST_TI.
2. ST_T3/TW.
3. ST_T4.

Gate after each.

## Stage R7 — Drive display from the canonical direct decision

Only after R6 is exact, replace the duplicated `ext_show` cause expression with a direct-slot display signal:

```text
slot_show_now =
    slot_fire && slot_mode==DIRECT
```

But preserve source-specific QS=E behavior:

- `ff_show`.
- `ff_t4`.
- `ff_evalext`.
- Near-flush `flush_hold`.

Do not reduce `qs_e` to `slot_show_now`; QS=E and bus status display are related but not identical.

Drive display descriptor from the already-selected direct descriptor:

```text
disp_desc = direct slot ? slot_desc
          : nxt_live    ? nxt descriptor
          : cur descriptor
```

Preserve INTA floating-address and HALT pseudo-cycle rules.

This is the highest-risk pure-refactor stage. Keep it separate and easy to revert.

# 3. Gates after every stage

## Mandatory full gate

Every stage must pass:

```text
w0: 169000/169000
w1:   1200/1200
w3:   1200/1200
```

Architectural-only equality is insufficient. Require every compared cycle row to match.

## Baseline-versus-refactor trace gate

Because the goal is pure refactoring, also compare baseline versus current RTL directly for:

- Bus status.
- Address/data drive.
- T-state.
- QS F/S/E.
- `nxt_valid/nxt_live`.
- `eval_ext`.
- `defer_t4/defer_idle`.
- `flush_hold`.
- `eu_started`.
- `fetch_off`.
- `cur_*` and `nxt_*`.

The golden harness can mask some physically floating idle values. Direct baseline comparison should distinguish meaningful outputs from masked float retention.

## Targeted trace families

### Flush and branch

At minimum:

- `fz8304`: zero-wait far flush at T4, `ff_t4`.
- `fz84xxx` far-jump waited cases cited in the RTL comments.
- fz90018: far-flush at `eval_ext`, including `ff_evalext` QS=E.
- fz90003/fz90005/fz90018 near-flush waited cases exercising `flush_defer/flush_hold`.
- E9, Jcc, loop, far CALL, far JMP, RET variants.

Check exact row of:

- QS=E.
- Redirect CODE display.
- Redirect T1.
- Stale-fetch discard.

### EU reads and writes

- Register-EA and displacement readers.
- Stores with reservation timing d0/d1/d2.
- Odd split reads and writes.
- RMW read→write, especially `ext_ok_wr`.
- String read→write forwarding.
- IO reads/writes.

Check:

- `eu_started`.
- First and second split cycles.
- Write-data forwarding.
- `eu_done/eu_wdone/eu_rdone`.

### Interrupt and control

- INT, NMI, POLL.
- Both INTA cycles.
- BRK3, BRK immediate, BRKV.
- IVT reads and stack pushes.
- HALT entry and INT/NMI/reset wake.
- HALT pseudo-cycle address and UBE behavior.

HALT itself bypasses normal commit machinery ([v30_biu.sv](/home/wickerwaka/src/nec_test/hdl/rtl/core/v30_biu.sv:357)); the refactor must not accidentally classify `halt_show` as a slot.

### Class-5 controls

During Phase R, require fz90007 and fz90011 to remain exactly wrong in the same way. If either changes, the refactor is not behavior-preserving.

# 4. w0 neutrality

“`eval_ext` never fires at w0” does not make the entire refactor w0-neutral.

The refactor also touches w0-active paths:

- `eval_at_t3 && pick_any` at [v30_biu.sv](/home/wickerwaka/src/nec_test/hdl/rtl/core/v30_biu.sv:836).
- Plain ST_TI `do_commit`.
- `ff_show`.
- `ff_t4`.
- `defer_idle`.
- `defer_t4`.
- `nxt_live` display and consumption.
- INTA, HALT, and flush display multiplexing.

Therefore Phase R’s w0 argument is equivalence, not wait-gating:

> The same predicates choose the same descriptor, the same direct/staged mode, and the same side effects on the same edge.

Only the later class-5 policy can be mechanically w0-neutral via:

```text
if waited_resume_active:
    use new resume slot grant
else:
    use legacy prefetch grant exactly
```

# 5. Main risks and rollback boundaries

## Highest risks

1. **Fetch pointer advances twice or not at all.**  
   `fetch_off` currently advances in both staged and direct paths.

2. **`eu_started` moves by one clock.**  
   This can duplicate EU accesses or alter readiness/arbitration.

3. **Direct display becomes staged.**  
   Far flush, `defer_idle`, or `flush_hold` becomes one clock late.

4. **QS=E coupling breaks.**  
   `ff_evalext`, `ff_show`, and `ff_t4` have distinct E-display laws.

5. **`nxt_live` priority changes.**  
   A previously committed descriptor must beat new arbitration.

6. **Empty `eval_ext` teardown changes.**  
   No-selection `eval_ext` must still clear the completed cycle without running plain `do_commit` at its end.

7. **Simultaneous special causes are silently reprioritized.**  
   Inventory overlaps before converting the OR expression into a case statement.

8. **Split-half continuation loses priority.**  
   `want_half2` must remain above EU and CODE everywhere.

## Rollback discipline

Use one commit per stage/substage:

```text
R1 descriptor shadow
R2 staged task
R3a ST_TI direct helper
R3b defer_t4 helper
R3c ff_t4 helper
R4 slot request aliases
R5 shadow arbiter
R6a ST_TI consumes arbiter
R6b ST_T3 consumes arbiter
R6c ST_T4 consumes arbiter
R7 display descriptor
```

On failure, revert only the latest commit. Do not patch around a failure while continuing the refactor.

# 6. Success criterion and class-5 hook

## Phase-R success

All must hold:

- w0 `169000/169000`.
- w1 `1200/1200`.
- w3 `1200/1200`.
- Targeted flush/EU/interrupt/HALT traces identical.
- Explicit-WVEC baseline-versus-refactor traces identical.
- No changed `fetch_off`, `eu_started`, QS=E, or T1 clocks.
- fz90007/fz90011 class-5 traces remain unchanged.
- One canonical `slot_fire/slot_id/slot_mode/slot_desc` drives all new commits.
- Direct versus staged is delivery metadata only; descriptor selection is centralized.

## Separate Phase-S hook

Expose one prefetch-grant hook inside the canonical slot arbiter:

```systemverilog
legacy_prefetch_grant =
    slot_is_eval_ext ? prefetch_ext : prefetch_ok;

selected_prefetch_grant =
    waited_resume_active
        ? resume_slot_grant
        : legacy_prefetch_grant;
```

Priority remains:

```text
split half  >  eligible EU  >  selected prefetch
```

The later demand/momentum scheduler changes only:

- `waited_resume_active`.
- `resume_slot_grant`.
- Possibly a latched resume descriptor/deadline.

It must not modify direct/staged delivery, display muxing, flush behavior, or EU priority.

That is the clean handoff: Phase R creates a canonical slot boundary with exact legacy behavior; Phase S changes one prefetch policy input and can be validated independently against the class-5 signed gap-error census.
