# THE IE-RISE / PIN-FALL DIRECTED BOARD CELL — RESULTS

    pre-registration  docs/notes/ie_pinfall_cell_prereg_2026-08-11.md,
                      committed at `c0b7d16898` BEFORE the first board contact
    tool              sw/ie_pinfall_cell.py
    branch            fuzz-v2-on-relanding, base `ae3da7c59a`
    era               FLASH #17 resident (`sw/testdata/flash_log.jsonl`,
                      20 entries before AND after, sof `26c19f613e2caae8…`)
    board             CAPTURE ONLY, SOCKET ONLY (`use_core=False`, explicit).
                      No flash, no RTL edit, no bitstream.
    captures          2,200 sweep cells (2,424 captures with the stability
                      repetitions) + 3,630 confirmation captures
                      = **6,054 socket captures**, 0 transport errors
    date              2026-08-11

**NOTHING LANDS FROM THIS SITTING.**  `git diff --stat c0b7d16898 -- hdl/` is
empty.  The deliverable is a measurement, three verdicts and two next-wave
candidates.

---

## 0. HEADLINE

**The ucore's INT recognition threshold is EXACTLY silicon's on the
free-running leg — 876 comparable cells, ZERO disagreements, at four wait
levels — and it is ONE CLOCK EARLY at a HALT WAKE, at all four wait levels,
in 30 cells and in one direction only.**

    leg      w | silicon T* | ucore T* | delta
    eirun    0 |     3      |    3     |   0
    eirun    1 |     4      |    4     |   0
    eirun    2 |     5      |    5     |   0
    eirun    3 |     6      |    6     |   0
    eihlt    0 |     2      |    1     |  +1
    eihlt    1 |     3      |    2     |  +1
    eihlt    2 |     4      |    3     |  +1
    eihlt    3 |     5      |    4     |  +1

Every threshold is **SHARP** on both engines — no interleaving of taken and
not-taken `fall_off` at any wait, on either leg, on either engine.

And the three bookings that asked for this cell:

| booking | verdict |
|---|---|
| **C-γ** (wave-5) — the vectoring HALT wake's escaping prefetch | **ITS PREMISE IS REFUTED IN THE DIRECTED REGIME.**  `wake_prefetch` — CODE cycles between the HALT display and the INTA — is **IDENTICAL on silicon and the ucore in all 114 cells where it is defined at all** (a HALT display AND an INTA on both legs; 960 HLT-leg cells were compared), including the six cells where the ucore's acknowledge is **EIGHT clocks late**.  The lateness the C2 seats show is reproduced here **with ZERO extra fetch cycles**, so a prefetch-suspend cannot be its mechanism. |
| **C-β** (wave-4) — the park cost when the display is cancelled | **NOT FIRED, AND NOT A DIVERGENCE.**  With the pin already high before the HLT the part drives **no HALT display at all** (`n_halt = 0`) and acknowledges at `HLT pop + 6`; the ucore does the same, cell for cell, at every `rise_off < 0`. |
| **§64.1 / the C2 census** — separate `fz2c/404040` from the four `run − arm == 2` seats | **NOT SEPARATED, AND THE REASON IS NOW MEASURED RATHER THAN ARGUED.**  The one divergence this cell finds is a **HALT-wake** divergence, and those four seats' extra acknowledges are **NOT HALT-adjacent — 0 of 5, on their own banked rows.**  They are outside the regime in which silicon and the ucore differ at all. |

---

## 1. THE §3 CONTROLS — RUN FIRST, BECAUSE NOTHING ELSE IS QUOTABLE WITHOUT THEM

| control | result |
|---|---|
| the two engines are running the same program | `anchor_t1`, `t_ei`, `n_rows`, and the pin's `rise` and `fall`: **0 differences in 1,920 comparable cells** each.  Silicon and `tb_sys ret` put the eighth `F` pop on the same clock at every wait. |
| the pin path works and it is IE that the sweep is moving | `ierun`/`iehlt` (IE never falls): **69–71 of 112 cells recognise the request BEFORE `t_ei`** — i.e. as soon as it arrives — and **37–39 of the remaining 41–43 are taken**.  The only untaken controls are `hold ∈ {1, 2}`. |
| the observable is not manufactured by the rig | every `NOT TAKEN` cell is a capture in which `evt_fired` is true and `pin_int` is measured high and then low at the requested clocks; no cell reports an INTA without a pin. |
| the threshold is not a metastable race | **330 boundary cells × 11 repetitions = 3,630 captures, TAKE-unstable 0.** |

**The minimum pulse width is 1 clock and it is phase-dependent**: a `hold = 1`
pulse is recognised at most phases and missed at a few, on both engines, on
both control legs.  So the pin sampler is not what the legs' `NOT TAKEN` cells
are measuring.

---

## 2. THE MEASURED LAW

> **A maskable request is taken iff the INT pin is still HIGH at
> `t_ei + (T* − 1)`, where `t_ei` is the setter's own queue `F` pop and
> `T*(w) = 3 + w` on a free-running stream and `T*(w) = 2 + w` at a `HLT`.**

Read as one predicate: **the recognition samples the pin a fixed number of
clocks after the setter retires, and at a `HLT` it samples one clock earlier.**
The `+w` is the wait axis and §4.0a of the pre-registration registered what it
means — see §3.

`T*` is **sharp** at every measured point.  The taken/not-taken partition on
`fall_off` for `rise_off < 0` is, on both engines and at every wait:

    NOT TAKEN : fall_off ∈ [−8, T*−1]        TAKEN : fall_off ∈ [T*, +16]

with no exception in the 1,084 board leg cells that fall in that partition.

### 2.1 The registered hypothesis table, scored as registered

| id | T\* | w0 | w1 | w2 | w3 |
|---|---:|---|---|---|---|
| **H1-ucore-3** | 3 | **CONFIRMED** | refuted | refuted | refuted |
| **H2-later-4** | 4 | refuted | **CONFIRMED** | refuted | refuted |
| **H2-later-5** | 5 | refuted | refuted | **CONFIRMED** | refuted |
| **H3-latch** | −1 | refuted | refuted | refuted | refuted |
| **H4-level-only** | 9 | refuted | refuted | refuted | refuted |

**REPORTED AS REGISTERED, NOT RESTATED: no single member of the registered
five holds at all four wait levels, and at w3 (`T* = 6`) NONE of the five
holds.**  The outcome is **registered outcome seven — `T*` is not
wait-invariant** — which §4 of the pre-registration named in advance precisely
so it could not be reached for afterwards.  The five hypotheses were written as
single integers; the measurement is a *family* `T*(w) = 3 + w`, and the honest
statement is that the registered table was the wrong shape and said so before
the run.

**H3-latch is refuted outright**: at no wait, on either leg, is a request
taken whose pin fell before `t_ei` — the smallest taken `fall_off` anywhere in
the whole 2,200-cell sweep is **+1**, on both engines (`iehlt_w0:r0:h1` on the
board, `eihlt_w0:r-12:h13` on `tb_sys`).  **H4-level-only
is refuted on this cell's own evidence** and not by citation: the acknowledge
sits 9 clocks after `t_ei` on the free-running leg at w0 while `T*` is 3, and
there are **751 board cells in which the chip acknowledges AFTER the pin has
already fallen — 240 of them with the pin down six clocks or more**, up to
`ack − fall = +11`.

### 2.2 The wait axis separates the two laws it was registered to separate

`T*` moves **exactly +1 per wait level** while the sled's boundary grid
stretches **1.00 / 1.12 / 1.28 / 1.44** — the eight pops span `t_ei −
anchor_t1` = **25 / 28 / 32 / 36** clocks at waits 0 / 1 / 2 / 3
(`anchor_t1` 145 / 207 / 240 / 273, `t_ei` 170 / 235 / 272 / 309).  A `T*` that were the FIRST
INSTRUCTION BOUNDARY at or after the IE rise would stretch with the grid; a
`T*` that is a fixed clock offset would not move at all.  **It does neither**:
it moves one clock per wait, which is the signature of a fixed offset from a
retire whose own pop→flag-write latency grows by one clock per wait state.
Both engines do it identically, so the quantity is not in dispute — only its
name is, and **naming it is booked, not claimed**.

---

## 3. THE ONE DIVERGENCE, IN FULL

Every board-vs-core difference in the 2,200-cell sweep, by column:

| column | differ / compared |
|---|---|
| `rise` · `fall` · `t_ei` · `anchor_t1` · `n_rows` | **0 / 1,920** each |
| **`wake_prefetch`** | **0 / 1,920** (defined on 114 cells; identical on all 114) |
| `taken` | 30 / 1,920 |
| `n_inta` | 36 / 1,920 |
| `ack_off` · `ack_off_hlt` | 46 / 1,920 |
| `n_halt` | 11 / 1,920 |
| `halt_first` · `halt_off` | 6 / 1,920 |

**All 57 distinct differing cells are on a HLT leg — 54 `eihlt` and 3 `iehlt`.
`eirun` (876 comparable cells at four wait levels) and `ierun` (84) have ZERO
differences in every column.**

### 3.1 The take flip — 30 cells, one predicate

All 30 are `eihlt`, all at `fall_off == T*_core(w)` exactly (+1 at w0, +2 at
w1, +3 at w2, +4 at w3), and all in one direction: **the ucore takes, silicon
does not.**  They occur at every `rise_off` from −16 to +2, i.e. the flip
depends on the pin's FALL and on nothing else.  There is no cell anywhere in
the sweep where silicon takes and the ucore does not.

### 3.2 The acknowledge position — 46 cells, and one of them matters a great deal

| (board, core) `ack_off_hlt` | cells | where |
|---|---|---|
| `(None, 6)` and `(None, 7)` | 30 | the take flip of §3.1 |
| `(13, 12)` | 10 | `eihlt_w1`, `rise_off = +6`, every hold — the ucore is **one clock EARLY** |
| **`(15, 23)`** | **6** | **`eihlt_w2`, `rise_off = +10`, every hold — the ucore is EIGHT CLOCKS LATE** |

**The eight-clock lateness is the C2 seats' own signature** (`fz2c/404071` +7,
`fz2e/514044` +9, `fz2e/516001` +16 on their banked fabric rows), and this cell
reproduces it in a directed program — with **`n_halt` 2 on both legs,
`halt_off` 6 on both legs, and `wake_prefetch` 0 on both legs.**

> **THIS REFUTES WAVE-5's DIAGNOSIS OF THE MECHANISM.**  `fz2_w5_p3_prereg`
> §1 located the failure as *"a code prefetch granted at the HALT WAKE, one to
> three clocks before the INTA microcode's own `I_SUSP`"*.  In the directed
> cell the ucore is eight clocks late at the wake **with no prefetch at all** —
> zero CODE cycles between the HALT display and the INTA, on both engines, in
> all 114 cells where the quantity exists (960 HLT-leg cells compared).  A prefetch-suspend, however carried, cannot close
> a divergence that occurs when there is no prefetch to suspend.

### 3.3 The HALT display — 11 cells

`n_halt` `(2, 0)` on 6 cells and `(4, 2)` on 5.  **Every one is `hold = 1`** —
a one-clock pulse arriving in the park window — and they appear on `iehlt` (IE
never falls) as well as `eihlt`, so this is **not an IE effect at all**:
silicon announces a HALT that the ucore does not announce when a one-clock
request lands on the park.  Booked separately as §5's candidate **N-2**.

---

## 4. THE SEATS — WHAT THIS CELL DOES AND DOES NOT SAY ABOUT THEM

Scored per the pre-registration's §4.4, which registered this as a
**consistency test, not a placement**, because the clock IE rises inside a seed
is not on the pins.

| id | registered test | result |
|---|---|---|
| **S-1** | does the measured `T*` differ from the ucore's? | **YES, but only at a HALT wake** — 0 on `eirun`, +1 on `eihlt`, at all four waits |
| **S-2** | if it differs, is the direction right for the four `run − arm == 2` seats, AND consistent with `fz2c/404040`? | **THE QUESTION IS MOOT FOR THOSE FIVE SEEDS AND THAT IS THE FINDING** — see below |
| **S-3** | is `fz2c/404040`'s `ack − fall = +7` reproducible in the cell? | **MET** — 59 board cells sit at exactly `ack − fall = +7` and the distribution runs to +11 |

**S-2, in full.**  The direction IS right: the ucore takes where silicon does
not, which is exactly the four seats' signature (core acknowledge runs exceed
chip: `fz2c/405002` +1, `fz2c/405013` +1, `fz2c/405072` +2, `fz2e/512056` +1,
against `fz2c/404040` at ±0).  **But the divergence this cell measures is
HALT-wake-only, and those five extra core acknowledges are NOT HALT-adjacent:
0 of 5 have a single BS = HALT row in the 40 clocks before them**, measured on
the seeds' own banked core rows, engine-free.  `fz2c/404040` likewise has none.

> **So the four `run − arm == 2` seats and `fz2c/404040` are still not
> separated — and the cell now says WHY: silicon and the ucore do not differ at
> all in the regime those seeds occupy.**  Their recognition threshold on a
> free-running stream is identical to silicon's over 876 cells and four wait
> levels.  Whatever separates them is not the IE-rise / pin-fall phase, and
> §64.1's wall is not where it was thought to be.

**Where the cell DOES land on the seats.**  The three C2 `sti; hlt` seats —
`fz2c/404071`, `fz2e/514044`, `fz2e/516001` — are the ones whose chip
acknowledge is preceded by **2 HALT rows**, and whose core acknowledge is
**+7 / +9 / +16 clocks late**.  Those are HALT-wake seats, they are in the
regime where this cell finds silicon and the ucore differing, and §3.2
reproduces an eight-clock lateness there in a directed program.  **They are the
seats the next wave should take, and the mechanism it should take them with is
NOT a prefetch suspend.**

The ten blocked C2 seeds in the FLASH #17 ledger, partitioned by what this cell
says about them:

| group | seeds | this cell's verdict |
|---|---|---|
| HALT-wake (2 HALT rows before the chip acknowledge) | `fz2c/404071` · `fz2e/514044` · `fz2e/516001` | **IN the divergent regime.**  Next-wave candidate **N-1**. |
| free-running (`run − arm == 2`, no HALT) | `fz2c/405002` · `fz2c/405013` · `fz2c/405072` · `fz2e/512056` | **OUTSIDE it.**  Recognition threshold measured identical to silicon; the mechanism is elsewhere.  §64.1's separation is NOT achieved and this cell says so. |
| the rest | `fz2c/410047` (`LONG_INSN`) · `fz2e/513019` · `fz2e/516065` | not addressed by this cell; `516065`'s core acknowledge is +17 at a non-HALT boundary. |

`fz2c/404040` stays a banked SUCCESS and this cell touched nothing that could
move it.

---

## 5. WHAT IS BOOKED — NEXT-WAVE CANDIDATES, NOT LANDINGS

**N-1 — THE HALT-WAKE RECOGNITION SAMPLES ONE CLOCK EARLY.**
*Measured*: `T*_silicon − T*_ucore = +1` on `eihlt` at waits 0, 1, 2 and 3;
30 cells; one direction; sharp on both engines; 0 unstable in 11 repetitions of
every boundary cell.
*Shape it implies*: **one predicate, no flop, no opcode named** — the wake's
pin sample is taken one clock later than the ucore takes it, i.e. the wake
recognition should read the same pipeline stage the free-running path reads
rather than the one before it.  `v30u_eu.sv`'s `hlt_wake_int` geometry is the
owner (the same geometry wave-4's C-β names).
*Falsifier*: a capture in which silicon takes at `fall_off = T*_ucore` on a
HALT leg at any wait level — i.e. any cell that closes the gap from the other
side.  None exists in 876 `eihlt` cells.
*Pre-registered bar for the landing*: the 30 cells close and `eirun` stays at
**876/876 identical**; the four HLT sweeps hold 279/283; `HLT.RES` holds 49/49
at w0.

**N-2 — SILICON ANNOUNCES A HALT THE ucore DOES NOT, ON A ONE-CLOCK REQUEST AT
THE PARK.**
*Measured*: `n_halt` `(2, 0)` ×6 and `(4, 2)` ×5, every one at `hold = 1`, on
`iehlt` as well as `eihlt` — so **IE-independent**.
*Falsifier*: any `hold ≥ 2` cell with an `n_halt` difference.  None exists.
*Not opened here*: 11 cells, one stimulus width, and the cell was not designed
around it.

**C-γ IS RE-CLOSED WITH ITS RE-OPEN CONDITION DISCHARGED AND ITS PREMISE
REFUTED.**  Wave-5 booked it as *"re-opens on a directed board cell on that
race"*.  The cell exists now, it is run, and it says: the wake-edge divergence
is REAL and it is **eight clocks of acknowledge latency with zero prefetch
cycles on either engine**.  C-γ as formulated — a prefetch suspend — is
therefore not the mechanism, and the booking is replaced by **N-1** rather than
re-opened.

**C-β IS CLOSED AS NOT-A-DIVERGENCE IN THIS REGIME.**  Its falsifier is not
fired (with the pin already high the part drives no HALT display at all and
acknowledges at `HLT pop + 6`) and the ucore matches silicon on that cell for
cell.  What remains of C-β is inside N-1.

**§64.1's separation is NOT achieved, and the cell converts the wall into a
measurement**: the four `run − arm == 2` seats live in the free-running regime,
and in the free-running regime silicon and the ucore are identical over 876
cells at four wait levels.  A predicate that separates them cannot be a
recognition-threshold predicate, and any future attempt that builds one should
read this paragraph first.

---

## 6. INTEGRITY BARS, AS REGISTERED

| id | bar | result |
|---|---|---|
| **I-1** | single-writer asked of the board | **OK** at each of the three board commands (`uptime` returned, no `v30ctl`/`serve` process on the board, no local serve client) |
| **I-2** | `use_core=False` explicit; `EMIT_USE_CORE is False` asserted | **MET** — the assert is at import and every `run_image` call passes it by name |
| **I-3** | `div_guard` PINNED at preflight, every stratum boundary, and the end | **MET — PINNED on all 24 guards** (14 in `run`, 10 in `confirm`), `div=8 (4 MHz)`, 0 UNPINNED |
| **I-4** | 0 transport errors; 3 consecutive would STOP | **MET — 0 in 6,054 captures** |
| **I-5** | ≥ 5 % of points captured 3× and byte-identical | **MET on the DERIVED stream — 112 points (5.1 %) × 3, 0 unstable**, plus 330 boundary cells × 11 with **0 TAKE-unstable**.  ⚠ The BYTE clause is reported MISSED-AS-WRITTEN and characterised in §6.1: 61 of the 330 confirmation cells produce two distinct raw word streams, differing only in rows 0–8. |
| **I-6** | full per-clock capture words retained with a sha256 per cell | **MET** — `sw/testdata/ie-pinfall/{board,board-confirm,core}/*.raw.json.gz` + `SHA256SUMS` |
| **I-7** | NO FLASH | **MET** — `flash_log.jsonl` **20 entries before and after**, FLASH #17 resident throughout |
| **I-8** | `board_idle()` at the end | **MET**, and a post-session `check_ab_hw chip 800` proof: **MATCH over 800 rows** |
| **I-9** | the §3 control clauses | **MET** — §1 |

### 6.1 A MEASURED NOISE CLASS, REPORTED BECAUSE IT WAS FOUND

Of the 330 boundary cells captured 11×, **61 produced two distinct raw word
streams**.  Characterised rather than smoothed: the difference is confined to
**row indices 0–8** in every one of the 61, touches only `ad_addr` / `ad_data` /
`ps` / `ube_n`, and never touches `t`, `bs_early`, `qs` or `pin_int`.  It is the
pads' retained value on the capture's own pipeline prefix — the same rows
`fz2_f14_results_2026-08-10.md` §(c) records as unscored by any tool in this
tree (*"`addr`/`data`/`ps` are scored from release+9 and nothing in this tree
scores rows 0-8"*) — and it moved
no measured quantity: **TAKE was identical on 330 of 330 cells across all 11
repetitions.**

---

## 7. REPRODUCTION

    python3 sw/ie_pinfall_cell.py calib      # offline, tb_sys ret
    python3 sw/ie_pinfall_cell.py predict    # offline
    python3 sw/ie_pinfall_cell.py core       # offline, 2,200 cells, ~170 s
    python3 sw/ie_pinfall_cell.py run        # BOARD, 2,200 cells, ~46 s
    python3 sw/ie_pinfall_cell.py confirm    # BOARD, 330 x 11, ~78 s
    python3 sw/ie_pinfall_cell.py score
    python3 sw/ie_pinfall_cell.py seats
    python3 sw/ie_pinfall_cell.py idle

Artifacts: `sw/testdata/ie-pinfall/` — `calib.json`, `predictions.json`,
`core/`, `board/`, `board-confirm/`, `score.json`, `seats.json`, each with its
own `SHA256SUMS`.
