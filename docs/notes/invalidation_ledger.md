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

**This file carries a SECOND register, opened 2026-08-09: § SUPERSEDED
POPULATIONS — NOT INVALIDATIONS (`SUP-n`).** A supersession is filed there and
never here, because *nothing is wrong with a superseded artifact*: its **WHICH
RIG DEFECT** field reads **NONE**, no capture is false, and it is retired from
the DEFAULT population by a `status` key in its own manifest rather than
discarded from every gate set. Do not read a `SUP-n` entry as evidence of a
defect, and do not file a defect as a `SUP-n`.

**It carries a THIRD register, § EXCLUDED SEEDS (`EXC-n`), and — opened
2026-08-11 — a FOURTH, § ERRATA AGAINST DERIVED COLUMNS (`ERR-n`).** The first
three are all about **CAPTURES**. `ERR-n` is the only one about a **DERIVED
COLUMN** — something this tree *computed* from a capture and stored beside it,
which can be wrong while every capture behind it is true. Its **WHICH RIG
DEFECT** field also reads **NONE**, and it carries a field none of the others
has: a named **INSTRUMENT** defect with its fix commit. Its disposition is
neither discard nor retire nor drop — the column is **RECOMPUTED IN PLACE** and
every movement is reported. Read its six preconditions before filing one; it is
not a licence to edit data that disagrees with a gate.

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

**Opened 2026-08-04 (SM1). CLOSED 2026-08-04 (SM2) by re-capture.
Status: **CLOSED — the population is REBUILT and back in the gate.**
The rig defect is FIXED in RTL, in the host tool, in the bitstream (FLASH #4)
and on the board.  The closure record is §CLOSURE below and
`ucore_provenance.md` §59.7.3-§59.7.7.**

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
if h != (h & ((1 << bits) - 1)):                        # (a) REPRESENTABILITY
    return True
if "hold_applied" in e and int(e["hold_applied"]) != h:  # (b) APPLICATION
    return True
return False
```

**Limb (b) was added 2026-08-04 (SM3 sitting 5, `ucore_provenance.md` §64.3)
after a Codex review found that the predicate implemented only the one defect
we had found, not the property this entry claims.** Limb (a) asks whether the
rig *could* hold the number; limb (b) asks whether it *did*. (a) derives (b) for
F46 and for nothing else: a representable-but-mis-applied directive — a
scheduler that clamps, a host that rounds, a register widened again later —
passes (a) and would have stayed silently SCORED. **The root cause named above
is "the rig silently applied a directive other than the one it was handed", and
limb (b) is that sentence as a predicate.**

*Proof that no current record is mis-applied*: `timed_fuzz --core sim
--evt-replay --pop evt` under `--rig-hold banked` and `--rig-hold applied`
produces **byte-identical** reports (EVT 780/1,008 both, no `INVALIDATED` line
on either). If any banked record disagreed with itself the two modes would hand
the engine different directives and part.

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

### §CLOSURE — SM2, 2026-08-04.  THE RE-CAPTURE

**The bitstream INV-1 was waiting for exists**: `FLASH #4`,
`nec_test_ucore.sof 67ddd59413d58934716260966cfc981f4f0d7065e90b8a8e655010e7687e4320`,
built from HEAD with the 12-bit `evt_hold`.  The board's own host tool was
replaced with the repo's 12-bit copy in the same step — a 12-bit bitstream
driven by an 8-bit host is still an 8-bit rig, and the old copy is preserved on
the board as `v30ctl.py.pre-sm2.bak`.

**THE WIRE WAS PROVED BEFORE THE POPULATION WAS TOUCHED**, in the two halves the
falsifier asks for.  `EVT_CFG` round-trips 8/8 including 256, 300 and 4,095
(`hold = 300` packs to `0x882C0000`: `[23:16] = 44` — the exact value F46
truncated to — plus `[30:27] = 1`).  And on the PIN, one seed, one image, five
directives differing only in `hold`, INTA T1 rows counted: **2 at `hold=44`, 6
at 300, 12 at 600**, against **2** in that seed's old banked capture.  The part
entered its handler ONCE under what the rig applied and THREE times under what
the bank asked for.

**THE RE-CAPTURE.**  All 760, socket (`use_core=False`), divider PINNED, each
seed's image hash-checked against its banked `image_sha256` first:
**760 new, 0 errors, 0 GEN-DRIFT, `evt_fired` 760/760.**

**WHAT THE PART DOES UNDER A TRUE 300-CLOCK LEVEL** — registered as a
measurement, never as a bar, because it had never been observed:

| INTA T1 rows | 0 | 2 | 4 | 6 | 8 | 10 |
|---|---|---|---|---|---|---|
| OLD (44 applied) | 28 | **732** | 0 | 0 | 0 | 0 |
| **NEW (300 applied)** | 21 | 1 | 40 | 125 | **265** | **308** |

### THE ARCHIVE, AND THE MECHANISM THAT KEEPS BOTH

`sw/testdata/inv1-archive/{mc1,mc2}/seeds/` — **760 byte-identical copies** of
the entries as they stood before the re-capture, with `SHA256SUMS`
(sha256 `6f79283222d169fdf1f7a8e599c403faacdd0d8d8801abb55c567d89a392355a`) and
a manifest.  **Deliberately OUTSIDE `tests/v30/fuzz_bank/`**: `check_fuzz_bank`
globs `*/seeds/*.json.gz` under that root, so an archive placed inside it would
have silently grown the 3,242-seed corpus — the same reasoning that kept the
originals from being moved in the first place.  (They are also in git history at
`64641a5644`; the copy exists so the guarantee does not depend on that.)

The entries themselves were **rewritten IN PLACE**, which is this entry's own
stated closure — *"a re-capture on the widened rig banks `hold_bits = 12`, and
the seed leaves this set by arithmetic… the seeds re-enter the gate without
anyone editing a list."*  Each carries a `recapture` block naming the bitstream,
the flash, the prior `chip_rows` sha256, the prior `banked_ts`, the prior
`replay_verdict` and the archive path.

`replay_verdict` was **recomputed and the movement REPORTED**, because leaving
it stale would have made `check_fuzz_bank` cry 700 spurious regressions and
recomputing it silently would have made that gate vacuous on these seeds:

| banked → re-captured | seeds |
|---|---|
| `FUNCTIONAL` → **`TIMING`** | **372** |
| `FUNCTIONAL` → `FUNCTIONAL` | 348 |
| `FUNCTIONAL` → **`KNOWN_ACCEPTED`** | **18** |
| `TIMING` → `TIMING` | 20 |
| `KNOWN_ACCEPTED` → `KNOWN_ACCEPTED` | 2 |
| **worse** | **0** |

### THE CLOSURE BARS (`ucore_provenance.md` §59.2, pre-registered) — ALL MET

| bar | result |
|---|---|
| every `hold=300` entry banks `hold_bits = 12` and `hold_applied = 300` | **760/760 MET** |
| `f46_invalidated` True anywhere in the bank | **0 MET** |
| the originals archived | **760 MET** |
| `timed_fuzz`'s `INVALIDATED` line | **gone, both engines** — the derivation self-healed |

### GATE STATUS — the second movement, and the sign flip

| gate | SM1 (INV-1 as opened) | **SM2 (re-captured)** |
|---|---|---|
| `timed_fuzz --core ucore` **REGISTERED** | 1,483/1,702 | **1,483/1,702 — UNCHANGED, to the seed** |
| `timed_fuzz --core sim` **REGISTERED** | 1,272/1,702 | **1,272/1,702 — UNCHANGED** |
| **EVT**, ucore | 170/248 (interim sub-gate) | **468 / 1,008 (46.4 %)** |
| **EVT**, sim | 144/248 | **363 / 1,008 (36.0 %)** |
| **COMBINED**, ucore | 1,653/1,950 | **1,951 / 2,710 (72.0 %)** |
| **COMBINED**, sim | 1,416/1,950 | **1,635 / 2,710 (60.3 %)** |
| the full 1,008-seed EVT column | **SUSPENDED** | **UN-SUSPENDED.  It is a gate again.** |

**The decomposition is the control**, and it is why the new number can be
trusted:

| sub-population | ucore | sim |
|---|---|---|
| the **248** never poisoned | **170/248** | **144/248** — *identical to SM1, seed for seed* |
| the **760** re-captured | **298/760** (was 22) | **219/760** (was 565) |
| total | **468/1,008** | **363/1,008** |

**THE SIGN FLIPPED.**  As banked, this column said the ucore lost to the model
by **517** seeds.  On captures taken under the directive the bank actually
records, **the ucore beats the model by 105.**  SM1 predicted the sign from the
un-poisoned 248 alone (a 26-seed margin) and the corrected full column
reproduces it and widens it.  §T.5's "547 ucore-only non-exact seeds" were the
rig, and are gone.

*The falsifier this entry registered* — *a capture in the 760 whose acknowledge
pattern is consistent with a hold longer than 255 clocks* — was **not** met by
any of the 760 old captures (732 of them show a single handler entry), and its
mirror image was demonstrated directly on the pin.  **INV-1 is closed as
diagnosed.**

---

## INV-2 — THE T12 fuzz-v2 CORPUS CAPTURE, AS A GATE

**Opened 2026-08-09.  Status: OPEN — archived by rename, re-capture in the same
sitting.**  The rig defect is FIXED in `sw/fuzz_campaign.py` at `c32b8cbb9d`
(amendment A-3, `fz2_corpus_prereg_2026-08-08.md` §13), committed before any
board contact of that sitting.

### WHAT

| | |
|---|---|
| the artifact | the **first fuzz-v2 corpus capture**, 3,840 seeds, taken 2026-08-09 on FLASH #12 in 10.8 minutes of board time |
| the banks | `sw/testdata/campaigns/fz2c/` (960 result lines, 552 retained captures) and `sw/testdata/campaigns/fz2e/` (2,880 lines, 374 captures) — **74 MB, 926 full per-clock capture files** |
| the scorings | `sw/testdata/fz2/fz2_bars.json`, `fz2_capture.json`, `fz2_c9.json`, `fz2_preflight.json`, `fz2_idle.json` |
| sha256, before the move | `results.jsonl` fz2c `f67b496c56a39707…`, fz2e `b95cb470c91a28aa…`; `fz2_bars.json` `e3fc9cfe5da0aa75…`; `fz2_capture.json` `01e0ed2192d23a54…`; `fz2_c9.json` `817566da12e86d24…` |

### WHY

Not because the rows are false.  **They are true silicon** and they are
retained.  What is false is what they can be scored AGAINST: every one of the
3,840 seeds was handed a terminating-NMI delay computed by a budget that left
**7 rows of tail slack at w0 and 1 at w3**, so on 1,048 seeds the terminator
fired, was intercepted, and the dump ran off the end of the 4,096-record
capture.  A capture whose termination is decided by the instrument's own
arithmetic error cannot measure a containment bar.  Stated as a property of the
artifact: **`(anchor + tail) / scale` over the 194 fully-observable completions
is PINNED at 461.1 against a reserve of 462.0** — the distribution is
right-censored at the budget, and no value above it exists in the data because
none could be recorded.

### WHICH RIG DEFECT

**O-2a**, named in §12.3 of the pre-registration and diagnosed in §13.2:
`ANCHOR_W0` was a post-RESET row number subtracted from a `CAP_ROWS` that counts
from record 0 (a 35-row coordinate error), `DUMP_W0` carried a 21-clock
*estimate* for an NMI entry that measures 53 minimum and 463 maximum, and the
NMI acceptance latency was in no term of the formula at all.  **FIXED** at
`c32b8cbb9d`: `ANCHOR_W0` 145→180, `DUMP_W0` 240→219, new measured term
`ENTRY_MAX` = 463, `TERM_MARGIN` and `TERM_FLOOR` unchanged.  The instrument
that diagnosed it, `sw/fz2_termcost.py`, reads only banked captures and
re-derives every number offline.

### WHAT REPLACES IT

A **re-capture of the same 3,840 seeds** — `SEED_LIST_SHA256`
`45d25f31a325c496…` is unchanged, so it is the same corpus, seed for seed —
against the **unchanged** bars C-1 … C-11.  Nothing gates on the archived
capture in the interim; it was never a ratchet (§8.2: *"a first registration is
not a ratchet"*), so no standing figure moves and none is suspended.

### THE ARCHIVE

**Renamed, never deleted, and nothing was rewritten:**

| from | to |
|---|---|
| `sw/testdata/campaigns/fz2c/` | `sw/testdata/campaigns/fz2c-INV2-archive/` |
| `sw/testdata/campaigns/fz2e/` | `sw/testdata/campaigns/fz2e-INV2-archive/` |
| `sw/testdata/fz2/fz2_{bars,capture,c9,preflight,idle}.json` | `sw/testdata/fz2/inv2-archive/` |

All 926 retained per-clock captures moved with their banks.  The precedent is
INV-1's (archive by rename, raw captures retained, nothing deleted) and the
w1evt-biased habit; the *disposition* is INV-1's, not the biased suite's,
because here the label is what is false.

**THE ARCHIVE IS LOAD-BEARING AND MUST NOT BE PRUNED.**  It is the only evidence
of the un-repaired rig, it is the population A-3's three constants were measured
on, and it is what makes the repair attributable: without it the improvement is
unverifiable and the before/after cannot be audited.  `sw/fz2_termcost.py` reads
the archive names first, by design.

### GATE STATUS

| figure | before | after |
|---|---|---|
| every standing gate in `standing_gates.md` | — | **UNMOVED.**  No standing gate reads `sw/testdata/campaigns/` |
| the fuzz-v2 bars C-1 … C-11 | 6 MET / 3 MISSED / 2 NOT SCOREABLE (§12.1) | **VOID pending the re-capture** — not restated, not carried forward |
| the census/enriched decompositions | 94.9 % / 72.08 % and 94.34 % / 69.72 % | **VOID pending the re-capture** |
| `SEEDS_SHA256` | `386c65fd641b84a1…` | `48a0f01176fd31b7…` (`TERM_CLOCKS` is derived from the constants) |
| `SEED_LIST_SHA256` | `45d25f31a325c496…` | **UNCHANGED** — the same 3,840 seeds |

### THE FALSIFIER, registered with the entry

If the re-capture's UNDISPOSITIONED count does **not** fall, the diagnosis is
wrong and O-2a is not a budget defect.  If the residue that survives is **not**
dominated by §13.5's stopped-CPU class (O-2d), the partition drawn off the
banked captures is wrong.  Either outcome is reported as registered.

---

## INV-3 — THE `rep_cl0` DERIVATION CELL, AS A GATE

**Opened 2026-08-17.**  Pre-registration `0dc40e51dc`, amendments
`bb37f154f2` (A-1) and `5fd01af2c0` (A-2); results
`docs/notes/rep_cl0_silicon_results_2026-08-17.md`.

### WHAT

`tests/v30/rep_cl0-INV3-archive/` — 24 socket captures (12 `F3A4` + 12 `F3A5`),
full per-clock rows, taken 2026-08-17 to ask silicon what `REP MOVSB` does at
`CX = 0x0100`.  **It has never gated anything and it never will.**

### WHY

**A-1 R-2, registered before the run, reads: *"THE SEED IS NEVER REROLLED ON A
CAPTURE-LENGTH FAILURE … A rerolled seed in this cell invalidates the cell."*
Eight seeds were rerolled** — one on `F3A4` (index 11), seven on `F3A5` — and
the emit log records each.

The reroll is not uniform, which is what makes it false rather than merely
untidy: **six of the seven `F3A5` quarantines are precisely the doubly-odd
images** (odd `SI` **and** odd `DI`), which split every word access into two
byte cycles and so exceed the 4,096-record ceiling.  Every surviving `F3A5`
case has at most one odd operand.  A whole alignment class was therefore
excluded **from inside `P-3`, the cell's own gating control** — and a control
with a systematically missing stratum is not a control.

⚠ **The direction of the bias runs OPPOSITE to the observation** (rerolling
selects for SHORT traces, and short is `H-SILICON`'s signature), and the four
`F3A4` `CX=256` cases carrying the headline are **first-choice, un-rerolled**
images.  **Both facts are recorded as reasoning and NEITHER is a waiver.**
R-2 invalidates on the artifact, not on the persuasiveness of the residue;
choosing the un-rerolled subset *after* seeing the result is the fitting this
register exists to prevent.

### WHICH RIG DEFECT

**NAMED, and NOT yet fixed at the time of filing.**  Two instrument paths, both
in `sw/emit_suite.py`:

1. **The ceiling.**  `EMIT_CAP = 2048`, `EMIT_CAP_RETRY = 4096`, and
   `EMIT_CAP = min(4096, EMIT_CAP * (1 + waits))` (`:197-198`, `:2548`).  A
   doubly-odd `F3A5` at these counts exceeds 4,096 and **has no larger retry to
   fall to**, so the case dies and the seed is rerolled.
2. **A second failure mode with NO retry path at all.**  *"only N register words
   before the done marker"* does not match the retry predicate, so it rerolls
   straight from 2,048 without ever trying 4,096.  This is the `F3A4` index-11
   reroll.

A-1 R-2 was written assuming a capture-length failure always ends in a
successful retry.  **That assumption is false, and the assumption is the
defect** — the reroll is `cmd_emit` behaving as designed on an error the
registration did not anticipate.

### WHAT REPLACES IT

**A RE-CAPTURE**, under its own pre-registration, after the ceiling is raised so
that no case in the cell can reroll.  Until that capture exists:

* **no figure in `rep_cl0_silicon_results_2026-08-17.md` may be quoted as a
  gate**, and
* the finding it points to — that silicon executes the loop where both engines
  skip it — **stands as an OBSERVATION with its instrument named, not as a
  certified result.**

The validation cell (A-2 §A-2.2, 72 disjoint-form cases) is **not** captured
until the re-capture certifies, and **no width rule may be quoted as validated**
until it is.

### THE ARCHIVE

**Renamed, never deleted, nothing rewritten:**

| from | to |
|---|---|
| `tests/v30/rep_cl0/` | `tests/v30/rep_cl0-INV3-archive/` |

The precedent is INV-2's (archive by rename; the invalid thing IS a directory,
so a rename can express it — unlike INV-1, where it was a selection inside a
shared directory).  All 24 per-clock captures moved with it, with the
`seeds.json` maps and `emit_log.txt` that **record the rerolls** and are the
only evidence of the un-repaired instrument.  **THE ARCHIVE IS LOAD-BEARING AND
MUST NOT BE PRUNED**: it is the before-column that makes the re-capture's repair
attributable.

### GATE STATUS

**No standing figure moves.**  The cell was new, gated nothing, and entered no
ratchet — the ladder is untouched and `P-6` was MET (`git diff --stat` over
`v0.1`/`v0.2`/`v0.3`/`v20suite` EMPTY, verified).  Nothing in
`docs/notes/standing_gates.md` changes.

⚠ **What does NOT change either: the REP `CL == 0` defect in both engines is
still measured, still reproducible offline, and still un-fixed.**  INV-3
invalidates a CAPTURE, not the offline finding — `sw/testdata/rep_cl0/`'s two
drivers reproduce the engine behaviour with no board in the loop.

### THE FALSIFIER, registered with the entry

The re-capture must complete the full 24-case cell with **ZERO rerolls** and
`emit_log.txt` carrying **no `reroll:` line**.  If it rerolls even once, the
ceiling fix is insufficient and the disposition is re-opened rather than
re-argued.  If the re-captured cell then reads anything other than
`H-ENGINE`, **this entry's WHY is wrong** and the bias analysis above must be
retracted rather than defended.

---

# SUPERSEDED POPULATIONS — **NOT** INVALIDATIONS

**Opened 2026-08-09.** This register was opened for artifacts that are FALSE.
The entries below are for artifacts that are TRUE and no longer USED. They are
filed here because they change what a gate measures and that must be findable in
one place — and they are filed under their own heading because filing a
retirement as an invalidation would say something about the data that is not so.

| | an INVALIDATION (INV-n) | a SUPERSESSION (SUP-n) |
|---|---|---|
| what is wrong with the capture | something — it was scored against a directive it never saw, or its label is false | **nothing** |
| the named rig defect | required | **NONE — and that field must read NONE** |
| the predicate | `timed_fuzz.f46_invalidated`, over the record | `bank_status.is_superseded`, over the manifest |
| the disposition | out of every gate set, permanently | out of the DEFAULT population; back with one flag |
| what it says | this measurement was not of what we thought | a better instrument exists |

**The two are independent.** A seed can be neither, either or both, and neither
predicate is computed from the other. `f46_invalidated` is **0 bank-wide** and
stays 0 — SUP-1 does not touch it and alleges nothing.

---

## SUP-1 — THE v1 FUZZ CORPUS, AS A REPLAYED POPULATION

**Opened 2026-08-09, branch `fuzz-v2-on-relanding`. Status: RETIRED BY STATUS.
No rig defect. Nothing moved, renamed or deleted.**

### WHAT

| | |
|---|---|
| the artifact | the **v1 fuzz bank** — four campaigns, **3,242 banked seeds**, captured 2026-07-28 |
| the cids | `mc1` **1,295** · `mc2` **1,294** · `t30-raw` **568** · `t30-brkem` **85** |
| where it is | `tests/v30/fuzz_bank/{mc1,mc2,t30-raw,t30-brkem}/` — **exactly where it has always been, byte for byte** |
| what changed in it | four `manifest.json` files gained `status`, `superseded_by`, `as_of_commit`, `superseded_ledger`, `superseded_note`. **No seed file, sig index, result shard or `chip_rows` was touched.** |
| the tree it was set on | `as_of_commit` `c07fbc0169ed31ca27b94be7a5759c085fb83d0d` |

### WHY — superseded, **not false**

The user directive of this campaign is *"I do not care about the old fuzz data,
discard it, move on"*, and the fuzz-v2 corpus was captured, scored and banked to
replace it. Until this entry the v1 seeds were still replayed **on every
`check_fuzz_bank` run** — 3,242 of the 3,865 seeds in the gate, for **+19.2 %
wall time and zero information about the population the project now develops
against** (`fz2_corpus_prereg_2026-08-08.md` §21.4).

**Nothing is alleged about the captures.** They are true silicon; they were taken
from the socket; they will remain true. Every figure ever quoted off them stays
true *of them*. What ended is their standing as the population a landing is
developed and scored against.

This also **RESOLVES C-11's third clause**, which §21.4 reported and did not
resolve. *"Standing bank ≤ 3,500"* was scored as `fz2c + fz2e` = **623** while
§2.1 justifies the number with *"every banked seed is replayed on every gate
run"* — a population of **3,865**, breaching the ceiling by 365.
**COORDINATOR RULING, 2026-08-09: §2.1's reading is correct** — gate wall time is
the cost the number exists to bound. The repair is not to shrink `fz2`; it is to
stop replaying a corpus that was discarded. The two readings now agree at **623**
and `fz2_w1.cmd_bars` computes **the §2.1 one** (`replayed`), recording both.

### WHICH RIG DEFECT

# **NONE.**

No rig defect is alleged, none is diagnosed, and none is fixed by this entry.
No capture is false, no directive was mis-applied, no label is wrong.
`f46_invalidated` is **0** across the whole bank before and after. If this entry
is ever read as evidence that something was wrong with the v1 captures, it is
being read wrongly.

### WHAT REPLACES IT

The **fuzz-v2 corpus**, `fz2c` **480** + `fz2e` **143** = **623** banked seeds
(`fz2_corpus_prereg_2026-08-08.md` §21), promoted 2026-08-09 and replaying
**623 stable / 0 improved / 0 worse / 0 GEN-DRIFT / 0 errors**.

It is a better instrument on the axes this campaign cares about, and it is
**measured, not asserted** (census over the banked records):

| axis | v1, 3,242 seeds | v2, 623 seeds |
|---|---|---|
| per-access WAIT VECTOR (task #38) | **0** — the axis did not exist | **169** `wvec-uni` (+454 flat) |
| `PSW.TF` / single-step | **0** seeds carry `has_tf` | **22** |
| census promotion rule | divergence-driven quota (a selection artefact) | **480 by the FROZEN rule**, `census_exact` true — population rates are population rates |
| `evt` pin events | 1,165 armed (760 at hold 300) | 295 armed (108 at hold 300) |
| 8080 / BRKEM | 50 seeds with BRKEM positions + the 85-seed `t30-brkem` bank | **0** — every v2 seed is `no8080` |

### THE ARCHIVE — there is none, because **nothing moved**

**This is the whole point of the mechanism.** INV-1's own words:

> a list can drift away from what it describes and a rename can be undone
> silently; a predicate computed from the artifact cannot.

INV-1 archived by rename because its captures had to leave a gate set
permanently. A supersession does not: the population must stay **reachable on
request**, so a historical figure can be re-derived. So it is a **STATUS**, in
each campaign's own `manifest.json`, and the population is a predicate over the
manifests — `sw/bank_status.py`, a leaf module with no engine behind it:

```
python3 sw/bank_status.py                       # the replayed population
python3 sw/bank_status.py --include-superseded  # everything banked
```

A bank with **no** `status` key is `ACTIVE`, so no existing bank and no future
promotion has to be edited to keep meaning what it means. Every consumer that
excludes a bank **says so on its own line**; a consumer that dropped 3,242 seeds
silently would defeat the mechanism.

### GATE STATUS — every figure that moved, and every one that did not

| gate | before | after |
|---|---|---|
| `check_fuzz_bank` **population** | **3,865** seeds | **623** seeds |
| `check_fuzz_bank` **verdict** | **FAIL** — see §"THE BEFORE WAS RED" below | **PASS** — `623 banked seeds \| stable 623 improved 0 worse 0 \| gen_drift 0 regen_err 0 \| float-floor 0 \| new-sig TIMING 0` |
| `check_fuzz_bank` **wall time** | **1,580 s** (26 m 20 s) | **266 s** (4 m 26 s) — **−83.2 %** |
| `check_fuzz_bank --include-superseded` | — | **3,865 seeds selected — the pre-SUP-1 population exactly, path for path** (proved: `bank_status.seed_paths(include_superseded=True)` is set- and order-identical to the historical `BANK.glob("*/seeds/*.json.gz")`). It still FAILS, for the reason below, which is not SUP-1's |
| `timed_fuzz --core ucore --evt-replay` | REGISTERED 1,564/1,702 · EVT 937/1,008 · COMBINED 2,501/2,710 | **NOT MEASURABLE ON THIS BRANCH, with or without the flag** — see §"THE BEFORE WAS RED". Without it: 0 seeds. With it: 3,242 seeds, **all `GEN_DRIFT`** (measured: `--bank mc1 --limit 40` → `GEN_DRIFT=40  SCORED 0`) |
| `timed_fuzz --core sim --evt-replay` | REGISTERED 1,343/1,702 · EVT 802/1,008 · COMBINED 2,145/2,710 | **NOT MEASURABLE ON THIS BRANCH**, same cause, same evidence |
| `timed_fuzz --seeddir …/b2-tranche/seeds` | 182/188 (ucore), 161/188 (sim) | **UNTOUCHED** — `--seeddir` does not read the bank |
| FZ2 bars | 8/11 MET, NOT MET C-1, C-3, C-6 | **8/11 MET, NOT MET C-1, C-3, C-6.** Only C-11's `measured` moved (gains `replayed` 623, `all_banked_incl_superseded` 3,865, `superseded_cids`); no other bar's `measured` changed by one character |
| C-11, §4.3's reading (`fz2c + fz2e`) | 623 ≤ 3,500 **MET** | 623 ≤ 3,500 **MET** |
| C-11, §2.1's reading (replayed) | 3,865 ≤ 3,500 **BREACHED by 365** | **623 ≤ 3,500 MET** — and this is the one the scorer computes |
| `f46_invalidated`, bank-wide | **0** | **0** |
| every other standing gate | — | **UNMOVED.** No other gate reads the bank glob |

### THE BEFORE WAS RED, AND THE WHOLE RED WAS THE v1 CORPUS

**This was not in the brief and it is not what anyone expected. It is measured,
and it corrects the framing of the finding this entry acts on.** §21.4 costed
the v1 corpus at *"+19.2 % wall time and zero information"*. The true cost was
higher: **on branch `fuzz-v2-on-relanding`, `check_fuzz_bank` over the 3,865-seed
population FAILS**, and every failing seed is a v1 seed —

```
check_fuzz_bank: FAIL | 3865 banked seeds | stable 623 improved 0 worse 0
                      | gen_drift 3157 regen_err 85 | float-floor 0
                      | new-sig TIMING 0                        (1,580 s)
```

`mc1` **1,295** + `mc2` **1,294** + `t30-raw` **568** = **3,157 GEN-DRIFT**, and
all **85** `t30-brkem` seeds raise
`brkem_high: refused -- fuzz-v2 eliminates 8080 entry unconditionally (plan D9)`.
The **623** fz2 seeds are the only stable ones in the tree.

**THE CAUSE IS fuzz-v2's OWN PLAN D9, AND IT LANDED LONG BEFORE THIS ENTRY**
(`sw/fuzz_campaign.py`, commits `e45772e4e0` … `b155b6166b`): the `0F` scrub is
now **unconditional** at all three build sites, so every v1 image regenerates to
a different sha256; and `brkem_high` is **refused outright**, so the BRKEM bank
cannot be composed at all. Both are deliberate, registered and correct. Their
side effect is that **the v1 corpus stopped being replayable on this branch the
day D9 landed** — GEN-DRIFT is the gate's designed report for exactly this: *a
generator change silently moved the seed*.

Three consequences, stated so no one has to rediscover them:

1. **SUP-1 takes `check_fuzz_bank` from FAIL to PASS.** That is a real
   improvement and it must not be quoted as a repair — nothing was repaired.
   A corpus the generator no longer builds stopped being replayed.
2. **`timed_fuzz`'s two v1 fuzz-bank ratchets were already unmeasurable on this
   branch**, before SUP-1 and independently of it: `--include-superseded`
   selects all 3,242 and every one categorises `GEN_DRIFT` (`--bank mc1
   --limit 40` → `GEN_DRIFT=40  SCORED 0`). Honouring status in
   `timed_fuzz.seeds_of` therefore costs those ratchets **nothing D9 had not
   already taken**. They are re-derivable only on a tree whose generator
   predates fuzz-v2 — merge-base `7e949925b7`, or `master`.
3. **"Reachable on request" means the SEEDS, not the REPLAY.** The flag returns
   the population path for path; it cannot return a replay the generator can no
   longer produce. This entry claims the first and does not claim the second.

### WHAT IS LOST — stated plainly, because retirement has a cost

1. **The 532 `OPEN_BUS` seeds.** The v1 bank is 3,242 seeds of which 2,710 are
   scoreable and **532 are `OPEN_BUS`-excused**. That excused population was a
   standing reservoir — every landing that shrank it did so by moving seeds out
   of it, and several were quoted that way (SM3 sitting 25's *"plus 51
   `OPEN_BUS`"*). Off the default population, that reservoir stops being watched.
2. **The 8080 / BRKEM class, and the `t30-brkem` bank entirely.** 85 banked seeds
   and 50 seeds carrying BRKEM positions. **The v2 corpus has ZERO of them** —
   every fz2 seed is `no8080`. This class is DEFERRED BY USER DECISION
   (2026-08-05) and structurally unreachable in the ucore, so nothing was gating
   on it; but the coverage is gone, not merely idle, and a future 8080 campaign
   must re-capture rather than re-read.
3. **INV-1's 760 re-captured EVT seeds.** All 760 live in `mc1`/`mc2`. They cost
   a board session, a 12-bit `evt_hold` in RTL, in flash and on the pin, and a
   closure with its own bars. They remain byte-identical and reachable; they are
   no longer replayed. **INV-1's own tooling (`sw/inv1_recapture.py`) reads them
   explicitly and is unaffected** — its predicate is `f46_invalidated`, not
   status, and it passes `include_superseded=True` deliberately.
4. **Re-scoring any pre-v2 landing on the population it was developed against —
   and this one was ALREADY lost, by D9, not by SUP-1.** Every ucore landing
   from H1 through the take-clock leg was measured on these 3,242 seeds, seed
   for seed, and their *"N gained, ZERO lost over all 3,242"* claims are
   statements about this corpus. **On this branch those claims cannot be
   re-derived at all**: the seeds are reachable with the flag, but the generator
   that built their images is gone, so every one of them scores `GEN_DRIFT`.
   Reproducing them needs a tree whose `sw/fuzz_campaign.py` predates fuzz-v2
   (merge-base `7e949925b7` or `master`) — a checkout, not a flag. **That is the
   standing hazard of this entry, and `standing_gates.md` says it in each row.**
5. **The wait-class mix.** v1 carries 1,765 `wrand` and 1,477 fixed-wait seeds
   across w0/w1/w2/w3; v2's 623 are 454 flat + 169 `wvec-uni`. The v2 corpus is
   better on the per-access axis and **thinner in absolute seed count by 5.2×**.
   Fewer seeds see fewer things; this is a real reduction in incidental coverage
   that no axis table shows.

### THE FALSIFIER, registered with the entry

The claim is **"nothing moved, status only"**, and the falsifier is about the
POPULATION, not about any figure's value — because D9 already took the replay
and this entry must not be credited with something it did not do.

**FALSIFIED IF** `bank_status.seed_paths(include_superseded=True)` is ever not
set- and order-identical to the historical `tests/v30/fuzz_bank/*/seeds/*.json.gz`
glob, or if `python3 sw/bank_status.py --include-superseded` prints anything but
**3865**, or if any file under `tests/v30/fuzz_bank/*/seeds/` differs by one byte
from its pre-SUP-1 content. All three were checked when this entry was written;
the first is an equality test anyone can re-run in a second.

**ALSO FALSIFIED IF** any consumer of that glob is found excluding superseded
seeds **without printing the exclusion**. A silently smaller denominator is how
a gate goes vacuous without anyone noticing, which is why `check_fuzz_bank`
returns **1**, not 0, if every bank in the tree is ever retired at once.

If any consumer of `tests/v30/fuzz_bank/*/seeds/*.json.gz` is found excluding
superseded seeds **without printing the exclusion**, the mechanism is defective
regardless of the arithmetic: a silently smaller denominator is how a gate goes
vacuous without anyone noticing.

---

# EXCLUDED SEEDS — **NOT** INVALIDATIONS AND **NOT** SUPERSESSIONS

**Opened 2026-08-09.** A third class, opened because filing it as either of the
two above would say something untrue. An excluded seed's capture is **true
silicon** (so it is not an INV) and **no better instrument replaced it** (so it
is not a SUP). It is a true capture **of a feature this project has deferred**,
and therefore not a member of the population any rate is computed over.

| | INVALIDATION (INV-n) | SUPERSESSION (SUP-n) | **EXCLUSION (EXC-n)** |
|---|---|---|---|
| what is wrong with the capture | something | nothing | **nothing** |
| named rig defect | required | NONE | **NONE** |
| the predicate | `timed_fuzz.f46_invalidated` | `bank_status.is_superseded` | **`bank_status.excluded_of`, over the manifest** |
| granularity | per capture | per campaign | **per seed** |
| the disposition | out of every gate set, permanently | out of the DEFAULT replayed population; back with `--include-superseded` | **out of every scored rate's NUMERATOR AND DENOMINATOR, and out of the replayed bank; back with `--include-excluded`** |
| what it says | this measurement was not of what we thought | a better instrument exists | **this is a true measurement of something we are not scoring** |

## EXC-1 — THE TWO RUNTIME 8080 ENTRIES IN `fz2e`

**Opened 2026-08-09, branch `fuzz-v2-on-relanding`. Status: EXCLUDED BY STATUS.
No rig defect. Nothing moved, renamed or deleted.**

| | |
|---|---|
| the seeds | **`fz2e/509069`** (soup, `FUNCTIONAL`, `sig 8cb79b8ba571898b`, 1,126 divergent rows) and **`fz2e/521059`** (raw, `KNOWN_ACCEPTED/open_bus`, 2,814 divergent rows) |
| the files | `tests/v30/fuzz_bank/fz2e/seeds/soup_509069_e6e5f2c9b2ec.json.gz` and `raw_521059_17de21d60cf3.json.gz` — **exactly where they have always been, byte for byte** |
| what changed | `tests/v30/fuzz_bank/fz2e/manifest.json` gained an `excluded_seeds` list. **No seed file, sig index, result shard, `chip_rows` or `results.jsonl` line was touched.** |
| the argument | `fz2_corpus_prereg_2026-08-08.md` **§31** (AMENDMENT A-12), the coordinator's ruling on §29.7 |
| the tree it was set on | `as_of_commit` `20816b9462` |

### WHY

Both seeds entered **8080 mode at RUNTIME** — a `MEMW` into the code region
manufactured a `0F xx` pair after the compose-time scrub had run (§29.1), and
`fuzz_campaign._ps3_8080` detected it on both. **8080/BRKEM is DEFERRED BY USER
DECISION 2026-08-05**, *not to be tested or considered until a later campaign*.
A capture in which the part entered a deferred mode is evidence about neither
side of the ledger: it is not a success and it is not a failure, **it is not a
member**. Scoring one — in a numerator, in a denominator, or in a regression
bank that fails a future landing on a deferred feature's divergence — is what
this entry stops.

### WHICH RIG DEFECT

# **NONE.**

The captures are true silicon, taken from the socket, and they stay true. Every
row in them remains readable and re-scoreable; `--include-excluded` replays them
in full.

### THE FALSIFIER

**FALSIFIED IF** a `ps3_8080` seed is ever found inside a scored rate or inside
the replayed bank while this entry stands — which is exactly what C-3's **R3′b**
computes, in both directions, on every `fz2_w1 bars` run: every `ps3_8080` seed
with a banked file must be named in `excluded_seeds`, **and** no banked file may
be excluded that the campaign results do not show `ps3_8080` for. A list that
drifts away from the artifact it describes fails, loudly.

**ALSO FALSIFIED IF** any consumer drops an excluded seed **without printing the
exclusion**.

### ADDENDUM, 2026-08-10 — THE ERA THIS ENTRY IS ABOUT, AND WHAT A-13 CHANGES

**Nothing above is retracted or rewritten.** This addendum states the era the
entry was always about, because a re-capture has since made it matter.

The two seeds are excluded on the strength of **their banked captures** —
`tests/v30/fuzz_bank/fz2e/seeds/{soup_509069_e6e5f2c9b2ec,raw_521059_17de21d60cf3}.json.gz`,
promoted 2026-08-09T18:09–18:10Z from the **F12-era** corpus, and byte-identical
since. Recomputing `fuzz_campaign._ps3_8080` over the `chip_rows` those two files
carry fires on **both**, and over **all 623 banked captures it fires on those two
and nothing else** (`prereg §34.3`). **EXC-1 is exactly right about the bank,
seed for seed.**

`0ac4c2a83a` then re-captured the corpus on FLASH #13 **without re-promoting the
bank**, and on that capture `fz2e/521059` **does not** enter 8080 mode while
`fz2c/408029` and `fz2e/523042` do (prereg §33). All three are `raw` tier with
identical `image_sha256` across the eras: **a runtime 8080 entry is a property of
the capture, not of the seed**, on a tier whose socket leg is not reproducible
(`0ac4c2a83a` bar C1). **This is not a defect in these captures and not a
retraction of this entry.**

**AMENDMENT A-13** (`fz2_corpus_prereg_2026-08-08.md` §34) therefore re-registers
C-3's **R3′b** to justify a *bank* exclusion against **the banked capture's own
rows, recomputed**, rather than against a campaign result line that may now be a
different capture. The falsifier below is unchanged in force and stronger in
form: it no longer trusts a stored column in another file, it decompresses every
banked seed and recomputes the predicate over the exact rows `check_fuzz_bank`
replays.

---

## EXC-2 — THE THREE RUNTIME 8080 ENTRIES IN THE **FLASH #13** CORPUS

**Opened 2026-08-10, branch `fuzz-v2-on-relanding`. Status: EXCLUDED BY STATUS.
No rig defect. Nothing moved, renamed or deleted.**

| | |
|---|---|
| the seeds | **`fz2c/408029`** (raw, stratum 8, `KNOWN_ACCEPTED/open_bus`, `sig dcc39a8e7bf43c1f`, 3,074 divergent rows), **`fz2e/509069`** (soup, stratum 21, `FUNCTIONAL/func:R@94`, `sig 8cb79b8ba571898b`, 1,126 rows — **also EXC-1**, and identical leaf for leaf across the re-capture) and **`fz2e/523042`** (raw, stratum 35, `KNOWN_ACCEPTED/open_bus`, `sig 626ef279e6b4d248`, 2,789 rows) |
| the artifact | `sw/testdata/campaigns/{fz2c,fz2e}/results.jsonl`, the **FLASH #13** re-capture of `0ac4c2a83a` (2026-08-10T00:51:09–01:02:21Z, 3,840 seeds, 0 halts) |
| what changed | **NOTHING IN ANY MANIFEST.** The exclusion is by arithmetic: `fz2_w1.py bars` filters a `ps3_8080` line out of its tier's numerator **and** denominator and prints the count (C-1 `excluded_ps3_8080`: `census/soup` 0 · `census/raw` 1 · `enriched/soup` 1 · `enriched/raw` 1, total **3**) |
| the argument | `fz2_corpus_prereg_2026-08-08.md` **§31** (A-12, what *discarded* means) and **§34** (A-13, which artifact justifies which half) |
| the tree it was set on | `as_of_commit` `db80e00596` |

### WHY

Same mechanism as EXC-1: a `MEMW` into the code region manufactured a `0F xx`
pair after the compose-time scrub had run, and the part entered 8080 mode at
runtime. **8080/BRKEM is DEFERRED BY USER DECISION 2026-08-05.** A capture in
which the part entered a deferred mode is not a member of the scored population.

### WHY NO MANIFEST RECORD IS WRITTEN — AND WHY WRITING ONE WOULD BE WRONG

**`fz2c/408029` and `fz2e/523042` have no file under
`tests/v30/fuzz_bank/<cid>/seeds/`.** The bank was promoted from the F12-era
corpus, in which neither seed diverged at all (`SUCCESS`). An `excluded_seeds`
record for a file that is not in the bank is itself a **failure** of C-3's R3′b
(*"excluded record names a file that is not in the bank"*), and it would be a
record about nothing: an exclusion is a statement about a replayed capture, and
there is no replayed capture to make it about.

`fz2e/509069` **is** banked, and its record already exists — **EXC-1's**. It is
not duplicated here.

### WHICH RIG DEFECT

# **NONE.**

The captures are true silicon, taken from the socket on FLASH #13, and they stay
true. They are retained in full in `sw/testdata/campaigns/{fz2c,fz2e}/captures/`.

### WHAT THIS ENTRY IS FOR

**A future promotion.** The bank was deliberately **not** re-promoted from this
corpus (prereg §34.5, with the numbers that move: the replayed population would
go **621 → 622**, `fz2e` banking 144 rather than 143). If it ever is, these
seeds' captures become banked files, and each one must then carry an
`excluded_seeds` record with a reason — which R3′b will demand, loudly, in its
A-13 form.

### THE FALSIFIER

**FALSIFIED IF** a `ps3_8080` line in the current corpus is ever found inside a
scored rate's numerator or denominator — which C-3's **R3′a** recomputes from
`sel_all` a second way on every `bars` run — or inside the replayed bank without
an `excluded_seeds` record, which **R3′b** recomputes off the banked rows
themselves.

**ALSO FALSIFIED IF** the exclusion is ever dropped **without being printed**
(R3′c).

# ERRATA AGAINST DERIVED COLUMNS — **NOT** INVALIDATIONS, **NOT** SUPERSESSIONS, **NOT** EXCLUSIONS

**Opened 2026-08-11.** A fourth register, opened for the same reason the third
was: filing this as any of the other three would say something untrue.

The three registers above are all about **CAPTURES** — data the rig produced.
This one is about a **DERIVED COLUMN**: something the tree *computes* from a
capture and stores beside it. A derived column can be wrong while every capture
it was computed from is perfectly true, and when it is, none of the three
dispositions applies — there is nothing to discard (INV), nothing to retire
(SUP) and nothing to drop from a rate (EXC). What there is, is **a wrong number
that must be recomputed with every movement reported.**

| | INVALIDATION (INV-n) | SUPERSESSION (SUP-n) | EXCLUSION (EXC-n) | **ERRATUM (ERR-n)** |
|---|---|---|---|---|
| what is wrong with the **capture** | something | nothing | nothing | **nothing** |
| what is wrong with the **derived column** | — | — | — | **it was computed by an instrument since found defective** |
| named **rig** defect | required | NONE | NONE | **NONE — and that field must read NONE** |
| named **instrument** defect | — | — | — | **required, with its fix commit** |
| granularity | per capture | per campaign | per seed | **per derived column, bank-wide** |
| the disposition | out of every gate set, permanently | out of the DEFAULT population; back with `--include-superseded` | out of every scored rate's numerator AND denominator; back with `--include-excluded` | **RECOMPUTED IN PLACE by the corrected instrument; nothing leaves any population** |
| how the gate returns green | re-capture | not applicable | not applicable | **by arithmetic — banker and checker compute the same corrected function — with NO list edited and NO seed excused** |
| what it says | this measurement was not of what we thought | a better instrument exists | this is a true measurement of something we are not scoring | **the measurement is true; the label we computed beside it was wrong** |

**AN `ERR-n` IS NOT A LICENCE TO EDIT DATA THAT DISAGREES WITH A GATE.** Its
preconditions are strict, all of them must be met, and each must be stated in
the entry:

1. the column is **DERIVED** — computed by this tree, never measured by the rig;
2. the **instrument defect is named and already fixed**, in its own commit;
3. the movement is **fully attributed BEFORE the rewrite**, seed by seed, in a
   document committed before it;
4. the originals are **archived byte-identical before a byte is touched**;
5. every rewritten entry is **PRINTED** and carries a provenance block naming
   what it replaced;
6. the untouchable fields are **proved untouched mechanically**, not asserted.

If any of those is missing, the honest disposition is a RED gate, not an ERR-n.
`cfb_tier_prereg_2026-08-11.md` §R.6 is the worked example of choosing the RED:
the same 90 seeds were left failing for a day rather than rewritten behind an
instrument fix that had no pre-registration of its own.

---

## ERR-1 — THE BANKED `replay_verdict` COLUMN OF THE 621-SEED fuzz-v2 BANK

**Opened AND CLOSED 2026-08-11, branch `fuzz-v2-on-relanding`, by
re-derivation. No rig defect. Nothing moved, renamed or deleted.**

### WHAT

| | |
|---|---|
| the artifact | the **derived replay columns** of the fuzz-v2 bank — `replay_verdict`, `replay_sig`, `replay_sub` on each entry, plus the **replay** contribution to `tests/v30/fuzz_bank/sig_ledger.json` |
| the population | `fz2c` 480 + `fz2e` 143 = 623 banked files, **− 2 EXC-1 = 621 replayed** (296 `soup` + 325 `raw`) |
| where it is | `tests/v30/fuzz_bank/{fz2c,fz2e}/seeds/*.json.gz` — **exactly where it has always been** |
| what changed in it | **three fields per entry** plus a new `rederive` provenance block, and the ledger's replay-sig keys. **No `chip_rows`, `chip_arch`, `image_sha256`, discovery `verdict`/`sub`/`sig`, `manifest.json`, sig index or result shard was touched** — proved mechanically, see THE MECHANICS |
| the tree it was set on | `921e756534` |
| the commits | prereg `537c6697c5` · archive `77ecf565d9` · tool `32fd811ed7` · rewrite `a54cc27454` |

### WHY — the column, not the capture

`sw/fuzz_bank.py:261` (`_write_bank`) computes the banked `replay_verdict` by
calling **`check_fuzz_bank.replay_classify` itself**. Until `09ec85e4bb` that
call site built `fc.Ctx(tier=entry["tier"])` with the banked config literal
`"soup"`/`"raw"`, while `Ctx.tier`'s declared domain is `'A'`/`'B'` — so every
tier branch in the classifier was silently False, **the arch-dump comparison
among them**. The banked column IS that defect's output.

Because the **same defective function was both the banker and the checker**,
`check_fuzz_bank` read `stable 621 / worse 0` for as long as the defect stood:
the round-trip compared the defect against itself. That green was a statement
about the determinism of an instrument, not about the bank
(`cfb_tier_prereg_2026-08-11.md` §2).

**Nothing is alleged about any capture.** `chip_rows` are true silicon, taken
from the socket, and they stay true — measured, not assumed: `gen_drift 0` and
`regen_err 0` on the full 621 in both the RED run and the green one, every image
still regenerating to its banked `sha256`, and the live bank's `chip_rows`
hashing **identical to the archive** after the rewrite. What was wrong was a
**label this tree computed and stored beside them.**

### WHICH RIG DEFECT

# **NONE.**

No rig defect is alleged, none is diagnosed, and none is fixed by this entry.
No capture is false, no directive was mis-applied, no board was touched, no
bitstream is implicated. **The defect is an INSTRUMENT defect and it is named**:
`check_fuzz_bank.replay_classify`'s tier-domain mismatch, **FIXED at
`09ec85e4bb`** by `fuzz_campaign.ctx_tier`, the one home of the mapping, which
**raises** outside its domain. Its own falsifier — 9 board-free checks, proved
non-vacuous — is `sw/test_fuzz_classify._tier_domain_falsifier()`.

### WHAT REPLACES IT

The same column, recomputed by the corrected instrument:
**`python3 sw/cfb_rederive.py --apply`**. Not a re-capture, not a re-bank, not a
re-promotion — the identical `(chip, sim)` row pairs read by a classifier
finally inside its own domain.

### THE ARCHIVE

`sw/testdata/cfb-tier-archive/{fz2c,fz2e}/seeds/` — **621 byte-identical
copies** of the entries as they stood at `921e756534`, plus a byte-identical
`sig_ledger.json`, `SHA256SUMS` (622 files; sha256 of `SHA256SUMS` itself
`4c2162cd6f2a6785ca722b01211696859a55580d75bfe9a69de635a5e15075ac`) and a
manifest, committed at `77ecf565d9` **before a byte of the bank was written**.

**Deliberately OUTSIDE `tests/v30/fuzz_bank/`**, for INV-1's own reason:
`bank_status.seed_paths()` globs `*/seeds/*.json.gz` under that root, so an
archive placed inside it would have silently grown the replayed corpus. (The
originals are also in git history at `921e756534`; the copy exists so the
guarantee does not depend on that.)

### THE MECHANICS — how "untouched" is proved rather than asserted

`sw/cfb_rederive.py` may write **four keys and no others**
(`replay_verdict`, `replay_sig`, `replay_sub`, `rederive`). For every entry it
hashes the canonical JSON of **every other key**, before and after, and
**aborts the whole run on a single mismatch** — `621/621 identical`. A
GEN-DRIFT is a STOP, not a repair. A negative ledger count is a STOP. `--limit`
is refused with `--apply`, because a partial rewrite is a truncated bank.

An **independent check that does not use the tool's own hash function**
compared the live bank against the archive key by key: **621/621 identical, 0
differing**, and `chip_rows` alone hash to
`5b93d459a9d21425fa9bc7386e705b732ddf8d163cce1d5e2be794b9c5a5b395` on **both**.

**Printed, never silent**: one line per entry (moved or not), one line per
ledger key added or removed. Each entry now carries a `rederive` block naming
its prior `replay_verdict`/`replay_sig`/`replay_sub`, its prior `banked_ts`, the
fix commit and the archive path — **faithful on 621/621 against the archive** —
so the movement stays derivable from the artifact, not only from a document.

### GATE STATUS — the movement, reported

| | RED (`921e756534`, mapped classifier vs defective column) | **GREEN (`a54cc27454`, re-derived)** |
|---|---|---|
| `check_fuzz_bank` | `FAIL \| 621 \| stable 531 improved 0 worse 90` | **`PASS \| 621 \| stable 621 improved 0 worse 0`** |
| `gen_drift` / `regen_err` | 0 / 0 | **0 / 0** |
| `float-floor` | 35 | **0** |
| `new-sig TIMING` | 148 | **0** |

**THE 90 ARE NOT ERASED BY THE GREEN.** They are, and stay, a finding about the
bank's derived column, itemized seed by seed in
`cfb_tier_prereg_2026-08-11.md` §R.2 and recorded in each entry's own
`rederive` block: **55 `soup`** where `done_mismatch` came alive
(`fuzz_classify.py:586`; 33 `TIMING`→`FUNCTIONAL`, 22
`KNOWN_ACCEPTED`→`FUNCTIONAL`) and **35 `raw`** where tier B's fixed 4,000-row
window came alive (`:562`; `SUCCESS` → 25 `TIMING` + 10 `KNOWN_ACCEPTED`, which
is `float-floor 35` seed for seed). **Nothing about the RTL, the model, the TB
binary or the silicon moved in either direction.**

Both registered clauses were scored on a **full dry run before `--apply`** and
again on the applied record:

* the **90 movers land EXACTLY on §R.2's committed after-column** — mover set
  equal seed for seed, **0 extra and 0 missing**, both mechanism splits exact —
  and, cross-checked independently against the RED run's own 90 `WORSE` lines,
  **90/90 agree on verdict AND sub**;
* the **531 non-movers' verdicts are byte-identical, 0 moved**, and their subs
  byte-identical on **521**, the 10 exceptions being exactly the sub-only class
  §R.5 measured and this sitting's §P-4 registered **in advance**.

The ledger moved **12,303 → 12,384** signatures (**+354, −273**), every key
printed, no count negative — the arithmetic registered at §P-6 before the run.

### WHAT IS **NOT** CLOSED BY THIS ENTRY

**The SUPERSEDED v1 banks still carry the defective column.** `mc1` · `mc2` ·
`t30-raw` · `t30-brkem` — **3,242 seeds** — were banked through the same
defective call site and are **NOT re-derived**, because on this branch they
**cannot** be: plan D9 makes the `0F` scrub unconditional, so every v1 image
regenerates to a different `sha256` and `replay_classify` STOPs at GEN-DRIFT
before it classifies (`3,157 GEN-DRIFT + 85 refused, 0 scored`). Re-deriving
them needs a checkout of a pre-fuzz-v2 generator. **Their `replay_verdict` is
the defective instrument's output and must not be quoted as anything else**;
`--include-superseded` still selects them and still fails, for D9's reason.

### THE FALSIFIER

**FALSIFIED IF** `check_fuzz_bank` and `cfb_rederive` ever disagree on a banked
seed's `replay_verdict` on an unchanged tree — that is the round-trip this
entry restored, and it is checked on every gate run by construction, because
the two call the same `replay_classify`.

**ALSO FALSIFIED IF** any live banked entry's non-mutable fields ever differ
from `sw/testdata/cfb-tier-archive/`'s copy of it. The archive is the standing
control on the claim *"only the derived columns moved"*, and the comparison is
four lines of Python over 621 files.

**ALSO FALSIFIED IF** a future sitting makes this gate green by editing a list,
excusing a seed, or narrowing the population. This entry's green came from
arithmetic; anything that comes from a list is a different thing wearing its
name.

---

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
