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
