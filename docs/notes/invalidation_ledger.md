# THE INVALIDATION LEDGER

**Opened 2026-08-04, session SM1, by the user directive of that date**
(`CLAUDE.md` § "Correctness target"):

> Where the rig or a golden is found defective, fix the rig and RE-CAPTURE;
> goldens invalidated by rig defects are DISCARDED from all gate sets —
> archived by rename with an invalidation ledger entry (the w1evt-biased
> precedent; raw captures stay retained, nothing gates on them).

This file is the register the directive names. It did not exist before this
session; **no invalidation had ever been recorded in this project.**

## What an entry must carry

| field | meaning |
|---|---|
| **WHAT** | the artifact or population, by path, with its size |
| **WHY** | what is false about it — stated as a property of the artifact, not of anyone's opinion of it |
| **WHICH RIG DEFECT** | the named finding, and whether the defect is fixed |
| **WHAT REPLACES IT** | the interim gate, the re-capture that closes it, or "nothing" |
| **THE ARCHIVE** | where the raw data went. **Nothing is ever deleted.** |
| **GATE STATUS** | every standing figure that moved, and the new status of each gate |

## A caution about the precedent this directive cites

**The w1evt-biased event is an ARCHIVE-BY-RENAME, not an invalidation**, and
reading it as one will produce the wrong mechanics. `ucsim_t_provenance.md`
§24.4 / §24.7: `tests/v30/v0.1-w1evt` was renamed to `v0.1-w1evt-biased` because
its case generation was BIASED (706 rerolls), a fresh tranche was emitted on the
same committed path, and **both** were re-scored at 1,200/1,200. §24.7's own
words: *"the old suite is **not retracted** — it was a true statement about the
1,200 cases it contained."* The biased suite is a **live standing gate to this
day** (`standing_gates.md` §B).

So the precedent supplies the *habit* — rename, never delete; keep the evidence
with the artifact; land it as its own commit; report both numbers — and not the
*disposition*. **INV-1 below is the project's first artifact that is actually
invalid**, and it is invalid in a specific way the precedent has no case for:
the captured data is TRUE and its LABEL is FALSE.

---

## INV-1 — THE EVT-SCORED FUZZ POPULATION, AS A GATE

**Opened 2026-08-04 (SM1). Status: INVALIDATED. The rig defect is FIXED; the
re-capture is SM2's and needs a bitstream.**

### WHAT

Not a file and not a directory — a **population selection** and the two standing
figures computed over it:

| | |
|---|---|
| the seeds | **760** banked fuzz seeds carrying `evt.hold = 300`: `tests/v30/fuzz_bank/mc1/seeds/*.json.gz` (**369**) and `tests/v30/fuzz_bank/mc2/seeds/*.json.gz` (**391**) |
| measured, this session | all 760 are inside the **1,008-seed scored EVT population**; the other 248 scored EVT seeds carry `hold = 2`. (The remaining 157 armed-but-unscored seeds are `OPEN_BUS` and all carry `hold = 2`. 760 + 248 + 157 = 1,165 = every `evt`-armed banked seed.) |
| the figures | `timed_fuzz --evt-replay`'s **EVT** and **COMBINED** columns: ucore **EVT 192/1,008**, **COMBINED 1,675/2,710**; sim **EVT 709/1,008**, **COMBINED 1,981/2,710** |
| **NOT** invalidated | the **REGISTERED** column. Its 1,702 seeds are by definition the ones with no `evt` axis. **ucore 1,483/1,702 and sim 1,272/1,702 are untouched**, and were re-run this session at exactly those values. |

### WHY

**F46.** `hdl/rtl/hps_axi_slave.sv` stored the pin-event hold in an **8-bit**
register (`evt_hold <= wdata[23:16]`), carried as `input [7:0] evt_hold` into
`hdl/rtl/nec_bus.sv`'s scheduler. A banked hold of 300 reached the socket as
`300 & 0xFF` = **44** clocks. The truncation was **silent**.

The captures are not corrupt. `chip_rows` in all 760 files is **true silicon** —
it is exactly what the part did with INT asserted for 44 clocks. What is false
is the **`evt.hold` label**, and therefore the DIRECTIVE the harness hands an
engine when it replays the seed.

That distinction decides everything about the disposition, and it is why the
invalidation is of a GATE and not of a capture:

* a **replaying** engine (`sim` under `--evt-replay`) is HANDED the capture's
  acknowledge positions, so it barely notices: **565/760 cycle-exact**;
* a **predicting** engine (any RTL core) computes its own recognition from the
  directive, is told 300 where the part got 44, and re-enters the handler two to
  four times where the socket entered once: **22/760 cycle-exact**.

A number that separates two engines by **543 seeds** on the strength of a
directive **neither engine's silicon ever received** is not a measurement of
either engine. It also made the EVT column read as a large ucore deficit (547
ucore-only non-exact seeds, `ucore_gaps_2026-08-04.md` §T.5) that is an artifact
of the rig.

The corrected sub-population points the other way, which is the strongest single
argument that the poison was doing the work — measured this session over the
248 un-poisoned EVT seeds:

| engine | poisoned 760 | **un-poisoned 248** | as banked, 1,008 |
|---|---|---|---|
| ucore | 22 | **170 (68.5 %)** | 192 |
| sim | 565 | **144 (58.1 %)** | 709 |

**On the EVT seeds whose directive the rig actually applied, the ucore beats the
model by 26 seeds.** As banked it "loses" by 517.

### WHICH RIG DEFECT, AND IS IT FIXED

**F46 / `ucore_gaps_2026-08-04.md` gap R1. FIXED in this session's commit:**

* `hps_axi_slave.sv` — `evt_hold` is **12 bits**, packed `{wdata[30:27],
  wdata[23:16]}` into `EVT_CFG (0x20)`'s only free space. `evt_pin[26:24]` and
  `evt_arm[31]` do not move, and a host writing zeros in `[30:27]` gets exactly
  the old behaviour.
* `nec_bus.sv` — `input [11:0] evt_hold`, `ev_hold_cnt` widened to match.
* `system_large.sv` — the wire.
* `sw/v30ctl.py` — `RIG_EVT_HOLD_BITS = 12`, one place, with the RTL named as
  the authority; and `set_event` now **RAISES** on an out-of-range hold instead
  of truncating. *The root cause of INV-1 is not the width. It is that the rig
  silently applied a directive other than the one it was handed.*
* `sw/fuzz_campaign.py` — every new capture banks `evt.hold_bits` and
  `evt.hold_applied` beside `evt.hold`, so a seed says which rig took it rather
  than leaving it to be re-derived from whatever the RTL says later.

**No bitstream carries the fix.** `sw/testdata/flash_log.jsonl` ends at FLASH #3
(`924c4a61e0…`, 2026-08-04). Every flashed bitstream is 8-bit-hold silicon, so
the re-capture needs a fourth flash. That is SM2's.

### WHAT REPLACES IT

1. **Interim gate, available today** — the un-poisoned EVT sub-population:
   **248 seeds**, ucore **170/248**, sim **144/248**. Registered in
   `standing_gates.md` §B as the EVT figure, with its denominator stated.
2. **The closing measurement** — re-capture the 760 on a bitstream carrying the
   12-bit hold, at the hold the bank asks for. Then `evt.hold_bits = 12` is
   banked with the capture, `f46_invalidated` returns False by arithmetic, and
   the seeds re-enter the gate without anyone editing a list.

### THE ARCHIVE — and why it is NOT a rename

**Nothing was moved and nothing was deleted.** All 760 files are where they
were, with their `chip_rows` intact, and they are still read by
`check_fuzz_bank` (the 3,242-seed replay-regression control cited for the U5
comparator change) and by `s15_census --rmw`. Moving them would have silently
changed both of those corpora, which is a second falsehood introduced to record
the first.

The directive's *rename* mechanism assumes the invalid artifact IS a directory —
which is true of a golden suite (`v0.1-w1evt` → `-biased`) and false here: the
invalid thing is a **selection inside a shared directory**. A rename cannot
express it. So the exclusion is **DERIVED FROM THE RECORD**, in code, at
`sw/timed_fuzz.py::f46_invalidated`:

```python
h    = int(e.get("hold", 0))
bits = int(e.get("hold_bits", 8))   # no field => the 8-bit rig, by date
return h != (h & ((1 << bits) - 1))
```

A derivation is strictly stronger than a rename here, and the reason is the
project's own standing lesson about vacuous gates: **a list can drift away from
what it describes and a rename can be undone silently; a predicate computed from
the artifact cannot.** It also self-heals on re-capture.

`timed_fuzz` prints the excluded population on its own **`INVALIDATED`** line
with its count and, for reference only, its cycle-exact figure. It is not
summed into any gate.

### GATE STATUS — every figure that moved

| gate | before | **after** | status |
|---|---|---|---|
| `timed_fuzz --core ucore --evt-replay` **REGISTERED** | 1,483/1,702 | **1,483/1,702** | **UNCHANGED.** Re-run this session. |
| `timed_fuzz --core sim` **REGISTERED** | 1,272/1,702 | **1,272/1,702** | **UNCHANGED.** Re-run this session. |
| **EVT**, ucore | 192/1,008 | **170/248** | **RE-REGISTERED** on the un-poisoned sub-population. The 1,008 figure is STRUCK. |
| **EVT**, sim | 709/1,008 | **144/248** | **RE-REGISTERED**, same. |
| **COMBINED**, ucore | 1,675/2,710 | **1,653/1,950** | **RE-REGISTERED** (denominator 2,710 → 1,950). |
| **COMBINED**, sim | 1,981/2,710 | **1,416/1,950** | **RE-REGISTERED**, same. |
| the **full 1,008-seed EVT column** as a gate | a standing ratchet | — | **SUSPENDED pending an SM2 re-capture.** |

**A contradiction this closes.** `standing_gates.md` registered `EVT 192/1,008`
as a standing ratchet on the same day `ucore_gaps_2026-08-04.md` §T.5 said of
the same number *"the EVT column is RIG-POISONED and is not a gate."* Both were
current. The gaps report was right and the gate list had not caught up.

*Falsifier for this entry*: a capture in the 760 whose acknowledge pattern is
consistent with a hold longer than 255 clocks — i.e. evidence the truncation did
not actually happen on the wire.

---

## AUDITED AND **NOT** INVALIDATED

Recorded because an unexamined suspicion is indistinguishable from an
unexamined artifact. Each of these was checked this session and cleared.

| candidate | verdict | the evidence that clears it |
|---|---|---|
| **every `tests/v30` golden suite** | **CLEAN of F46** | The golden emitter's `EVT(...)` spec table (`sw/emit_suite.py:632-657`) declares a max hold of **6**, across all 15 forms. Measured over every suite, `evt.hold` ∈ {0, 2, 6} — always ≤ 255. `hold = 300` is injected ONLY by `fuzz_campaign.py`'s `has_halt` branch, which no golden path takes. |
| the four `v0.1-w*evt` cells and `w1evt-biased` | **CLEAN** | holds 0 and 2 only |
| the four `s10`/`s13` HLT sweeps | **CLEAN** | hold 0 |
| the **b2 victory tranche** (171/188) | **CLEAN** | all 216 seeds carry `evt: none` |
| the **b3 priority tranche** (176/178) and **b4** (435/449) | **CLEAN of F46** | zero cells carry an `evt` axis. X3's issue is bitstream vintage, not hold — and it is a **declared** deviation (§55.2), with the F51 change proved inert on that population offline. **No standing gate consumes either directory** (`sw/u4_tranche.py` is the only reader, and it is not in `standing_gates.md`), so nothing needs suspending. |
| **the sticky-divider era** | **CLOSED, nothing in a gate set** | `ucsim_t_provenance.md` §21.1: two readings were produced at `div = 4` and **retracted before landing**; *"Nothing in the banked corpus is retracted"* — `v0.1`, `-w1`, `-w3` carry the correct display status in their stored rows, so they were emitted at 4 MHz and their provenance is recoverable from their content. The uncorrected emission was preserved-not-deleted at `sw/testdata/s10/s1-instrument/`, and §22.6 pinned the rig (`DIV_OF_RECORD = 8`, stamped into every `emit_log.txt`; `div_guard` readback `PINNED`). |
| **the composed-AD mask** (F51 / U5) | **poisons no golden** | It was a defect in the **comparator** (`hdl/tb/tb_v30_core.sv`), not in any emission. No golden in the tree was emitted from a TB — every `emit_log.txt` opens `# TRUTH SOURCE: SOCKET (real chip, use_core=False)`, and the four suites predating that header carry the equivalent in `metadata.json`. The load-bearing control is §57.2: replaying all **3,242** banked seeds through the corrected comparator moved **no** seed's verdict — *worse 0*. What the mask did poison were **FSM-core scores**, and that is already booked (168,400/169,000 and 16/283, `standing_gates.md` §C). |
| **R6 — the s10/s13 per-repetition rows** | **a retention GAP, not poison** | Both manifests bank every per-rep `raw_sha` and `evt_fired`; only the per-rep *rows* are missing, so `HLT.INT_w2_d0`'s `stable_identical: false` cannot be **verified** as the same pad artefact as `HLT.INT_w0_d0`. Nothing captured is wrong; a verification is unavailable and needs the board. Standing caveat retained: `stable_key` changed at §26.1 and keys stored before it are internally valid and **not comparable across the change**. |
| the campaign result logs (`sw/testdata/campaigns/*/results.jsonl`, 3,005 records asking `hold=300`) | **metadata only, no gate** | no standing gate reads `sw/testdata/campaigns/` |
| the campaign raw capture archives (13,252 files) | **CLEAN** | schema is `{"real": [rows]}`; they carry no `evt` axis at all |
