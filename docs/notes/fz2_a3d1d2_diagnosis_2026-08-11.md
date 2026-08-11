# fz2 A3 / D1 / D2 — THE 35-SEAT BLOCK, RE-DIAGNOSED

    branch      fuzz-v2-on-relanding @ ae3da7c59a   (detached; worktree was
                provisioned at master 29dcc5b05f and RESET before any
                measurement -- see §0.1)
    ledger      sw/testdata/fz2/fz2_failure_ledger_f17_2026-08-11.json
                113 failures / denominator 3,837   era sof 26c19f613e2caae8…
    date        2026-08-11
    board       NOT TOUCHED.  No capture, no flash, no RTL edit, no re-score.
    RTL         `hdl/` BYTE-IDENTICAL to ae3da7c59a.  NOTHING LANDED.
    Quartus     NOT RUN.  No law landed, so no G6 was owed.

    reproduce   python3 sw/fz2_replay.py \
                  --ledger sw/testdata/fz2/fz2_failure_ledger_f17_2026-08-11.json \
                  --seeds <the 35 of §1> --leg ret --jobs 7 --out RUN.json

**THIS DOCUMENT IS A DIAGNOSIS AND A SET OF BOOKINGS. IT LANDS NOTHING, CLOSES
NOTHING, AND MOVES NO GATE.** The residue is unchanged: 113 ledger failures,
35 of them in this block, 15 FUNCTIONAL / 15 TIMING / 1 TRANSIENT / 4 COSMETIC
before and after.

---

## 0. THE HEADLINE, IN ONE PARAGRAPH

The ledger's `A3` / `D1` / `D2` labels **do not track mechanism**. They are
assigned from the bus structure at `first_bad_row` — the first row the column
policy scores — which is where an *upstream* divergence first becomes visible,
not where it is caused. Aligning the two legs' **bus-transaction streams**
(kind, address, UBE) instead of their rows splits the block into **six**
distinguishable mechanisms; `A3` alone splits four ways, and `D1` and `D2`
split into the *same* set as each other. Four of the six are already named,
open packages elsewhere in the campaign. **The block's genuine
prefetch-request-arbitration content is not 25 seats; on this evidence it is
the 2–3 TF trap-boundary seats of §6.**

### 0.1 The reset, stated because a measurement on the wrong tree is not a measurement

The isolated worktree provisioned at **master `29dcc5b05f`**, not at the
briefed `ae3da7c59a`. It was reset (`git checkout --detach ae3da7c59a`) and
`git rev-parse HEAD` verified **before the first measurement**. Every figure
in this document was taken after that reset.

### 0.2 The instrument, before any figure is quoted

`sw/fz2_replay.py --leg ret`, all 35 seats:

| leg | result |
|---|---|
| **FABRIC ERA GUARD** | **PASS** — bitstream `26c19f613e2caae8…` (FLASH #17), receipt `287665a1027b42dd…`, **its 88/88 declared inputs hash IDENTICAL in the tree at HEAD**. No `--no-fabric-era-guard`, no caveat. |
| `tb_sys` **ret** binary | receipt **`c5c8916cfb7c6fbb8915f1156c5fd0d18d71f0f0fef9c7cbc6ce0f06d8e48102`**, tree key `82a907e0f81a64e0…` |
| `tb_sys` **base** binary | receipt **`d07384e3e6517999ca849652d243d8175281566be04f7aacdcd3625d05a61d2a`** |
| verdict agreement | fabric FAIL 35 / replay FAIL 35 — **35 / 35 = 100.0 %** |
| `first_bad_row` agreement | **35 / 35 IDENTICAL** |
| by wait mode | fixed 16/16 · wrand 16/16 · wvec 3/3 |
| by stimulus event | no event 8/8 · event 27/27 |
| by family | A3 15/15 · D1 10/10 · D2 10/10 |

**Every seat in this block is fully reproducible offline.** Nothing below rests
on a replay whose verdict or fork position disagrees with the board.

⚠ The banked captures are read directly (`real` = socketed µPD70116,
`sim` = fabric ucore, both FLASH #17, 4,063 rows each). The transaction-stream
and clock analyses of §2–§8 are computed on the **banked** rows, so the
offline-replay row-count bias of `fz2_flash17_results` §5.3 does not apply to
them; the replay above is the instrument *check*, not the data source.

---

## 1. THE METHOD, AND WHY IT DIFFERS FROM THE LEDGER'S

`fuzz_classify.diff_rows` compares **rows** under a column policy that scores
`ad_addr` only on T1-of-an-active-cycle, `ad_data` only on T2/T3 (data) and
T4/Ti (next-address), and `ps` only on an active T2. That policy is right, and
a check confirms it is not hiding anything meaningful: relaxing it to "any
column, any row" from row 9 makes `ps` differ at row 9 on **all 35** seats,
which is the retained-vs-driven upper nibble on non-T2 rows and carries no
information. **`first_bad_row` is the first meaningful divergence.** The
problem is not the comparator; it is that a row index is the wrong unit for
attribution.

So this diagnosis works in the **transaction** domain. For each seat both legs'
records are reduced with `fuzz_classify.extract_txns` to an ordered list of
bus transactions, each identified by `(kind, address, UBE)` and carrying its
start clock. Two derived quantities do all the work:

* **`j`** — the index of the first transaction whose *identity* differs. If
  `j` reaches the end of the shorter stream, the two legs executed the
  **identical bus transaction sequence** and only clocks and/or written data
  can differ.
* **the clock-delta profile** — `core.start - chip.start` over the identical
  prefix, and where in the stream it *steps*.

For a seat whose streams do diverge, the smallest local edit `(p, q)` is found
that re-aligns them (`chip[j+p+k] == core[j+q+k]`), together with the length of
the re-aligned run. `p` and `q` are searched **independently over 0..8**, so a
*replacement* (chip does 1 transaction where the core does 2) is representable;
an earlier pass that allowed only a pure insert or delete mis-scored eight
seats and its numbers are not quoted anywhere below.

---

## 2. THE PARTITION

| mechanism | n | defining measurement |
|---|---:|---|
| **ENTRY-CLOCK** | 6 | transaction stream **identical over the whole window**; the *only* clock steps in the entire run land **on an interrupt-entry transaction** |
| **DATA-ONLY** | 4 | stream **and** clocks identical; only the value written differs |
| **GHOST-ADDR** | 3 | 2 transactions replaced **at the same clock** at a different address, then perfect re-align |
| **CORE-STOPS** | 2 | core matches for 220 / 658 transactions then issues **none at all** |
| **ONE-EDIT** | 5 | one local edit of 1–2 transactions, then re-aligns 87–256 transactions |
| **CASCADE-\*** | 15 | diverge and do not re-align (`frac` 0.00–0.86) |

Cross-cut against the ledger's families and against
`docs/notes/fz2_materiality_census_2026-08-11.md`'s consequence classes:

| mechanism | A3 | D1 | D2 | FUNC | TIME | TRAN | COSM |
|---|---:|---:|---:|---:|---:|---:|---:|
| ENTRY-CLOCK | 6 | 0 | 0 | 0 | 6 | 0 | 0 |
| DATA-ONLY | 4 | 0 | 0 | 2 | 0 | 1 | 1 |
| GHOST-ADDR | 3 | 0 | 0 | 0 | 0 | 0 | 3 |
| CORE-STOPS | 2 | 0 | 0 | 2 | 0 | 0 | 0 |
| ONE-EDIT | 0 | 2 | 3 | 2 | 3 | 0 | 0 |
| CASCADE(entry) | 0 | 2 | 2 | 1 | 3 | 0 | 0 |
| CASCADE(chip-fetch) | 0 | 2 | 0 | 2 | 0 | 0 | 0 |
| CASCADE(core-fetch) | 0 | 0 | 3 | 2 | 1 | 0 | 0 |
| CASCADE | 0 | 4 | 2 | 4 | 2 | 0 | 0 |
| **total** | **15** | **10** | **10** | **15** | **15** | **1** | **4** |

**`A3` covers four mechanisms. `D1` and `D2` cover the same four as each
other.** No mechanism is confined to one family and no family is confined to
one mechanism.

### 2.1 Every seat, assigned by name

`esc` = `escaped_n` (F14 §4 caveat applies to any seat with `esc > 0`).

#### ENTRY-CLOCK (6) — all A3, all TIMING, all `esc = 0`

| seat | tier | steps (index, delta, entry transaction) |
|---|---|---|
| `fz2c/404049` | soup | txn 37 −1 @ `INTA 08106` |
| `fz2c/405025` | soup | txn 40 −1 @ `MEMR 00008` |
| `fz2e/510048` | soup | txn 48 −2 @ `MEMR 00008`; txn 326 −2 @ `MEMR 00008` |
| `fz2e/515047` | soup | txn 50 **+2** @ `MEMR 00008` |
| `fz2e/516066` | soup | txn 139 −2 @ `MEMR 00008` |
| `fz2e/527017` | raw | txn 817 −1 @ `MEMR 00008` |

Stream lengths, chip / core: 314/314 · 250/250 · 387/387 · 182/182 · 199/199 ·
879/879 — **identical, transaction for transaction, across the whole compare
window in every case**, and the clock delta is exactly 0 for every transaction
before the step.

#### DATA-ONLY (4) — all A3

| seat | class | esc | arch | fork opcode |
|---|---|---:|---|---|
| `fz2c/406046` | FUNCTIONAL | 138 | `DW` | `e7 fe` `out 0xfe,ax` |
| `fz2e/531039` | FUNCTIONAL | 40 | `BW` | `30 9d 56 94` `xor [di-0x6baa],bl` |
| `fz2e/513026` | TRANSIENT | 2 | — | `cc` `int3` |
| `fz2e/529009` | COSMETIC | 0 | — | `a3 4b 72` `mov ds:0x724b,ax` |

Stream identity 406/406 · 243/243 · 103/103 · 264/264, **clock delta constant 0
throughout**. The bus schedule is bit-identical; the divergence is entirely in
a written value / a register.

#### GHOST-ADDR (3) — all A3, all COSMETIC

| seat | esc | the replaced pair |
|---|---:|---|
| `fz2c/409065` | 225 | `MEMR 5760f @1535` vs `MEMR 575b7 @1535` |
| `fz2e/521049` | 64 | `MEMR 53f39 @2151` vs `MEMR 4ff39 @2151` |
| `fz2e/525017` | 39 | `MEMR 2e255 @1142` vs `MEMR 2e055 @1142` |

`p = q = 2`, same start clock, then **perfect re-align** (`frac` 1.00 over 440 /
108 / 113 transactions). This is the census §2.3 ghost-read signature drawn in
the transaction domain.

#### CORE-STOPS (2) — both A3, both FUNCTIONAL, both `arch NODUMP`

| seat | esc | streams | fork opcode | ModR/M `mod` |
|---|---:|---|---|---|
| `fz2c/407067` | 44 | 373 chip / **220** core | `0f 31 36 05 19` | `0x36` → **00 (memory)** |
| `fz2e/527065` | 0 | 726 chip / **658** core | `0f 31 9c 65 27` | `0x9c` → **10 (memory)** |

Measured on `fz2c/407067`: after row 1594 the core issues **zero** transactions
for the remaining 2,406 rows of the window while the chip issues 150+. It is
not slow; it is dead.

#### ONE-EDIT (5)

| seat | fam | class | esc | edit | re-align | at the fork |
|---|---|---|---:|---|---|---|
| `fz2e/501066` | D2 | FUNCTIONAL | 0 | chip[0] ↔ core[1] | **87/87** | `MEMR 00004 @524` vs `CODE 3813c @520` |
| `fz2e/512062` | D2 | TIMING | 0 | chip[1] ↔ core[2] | **119/119** | `INTA 07af4 @291` vs `CODE 98104 @289` |
| `fz2e/530017` | D2 | TIMING | 139 | chip[2] ↔ core[1] | **239/239** | `MEMR cdf5b @1441` vs `MEMR c5f50 @1441` |
| `fz2e/530020` | D1 | TIMING | 15 | chip[1] ↔ core[2] | **224/224** | `MEMR 49cf7 @297` vs `MEMR 3fcf1 @297` |
| `fz2c/409077` | D1 | FUNCTIONAL | 251 | chip[0] ↔ core[1] | 256/268 (0.96) | `CODE de522 @821` vs `MEMR a5d11 @821` |

#### CASCADE-\* (15)

| seat | sub | fam | class | esc | frac | at the fork |
|---|---|---|---|---:|---:|---|
| `fz2c/407000` | entry | D1 | FUNCTIONAL | 39 | 0.55 | `CODE 9798e @3046` vs `MEMR 00008 @3048` |
| `fz2e/511014` | entry | D1 | TIMING | 0 | 0.08 | `CODE 2beae @379` vs `INTA 06549 @381` |
| `fz2e/514072` | entry | D2 | TIMING | 0 | 0.18 | `INTA 0a6ce @327` vs `CODE 1810a @329` |
| `fz2e/516026` | entry | D2 | TIMING | 0 | 0.72 | `MEMR 00008 @1762` vs `CODE d813c @1760` |
| `fz2e/531030` | chip-fetch | D1 | FUNCTIONAL | 0 | 0.13 | `CODE 7810d @3225` vs `MEMW ec9e0 @3219` |
| `fz2e/532021` | chip-fetch | D1 | FUNCTIONAL | 0 | 0.56 | `CODE 48dee @3034` vs `MEMR 19170 @3033` |
| `fz2c/404041` | core-fetch | D2 | FUNCTIONAL | 0 | 0.01 | `MEMR 00004 @942` vs `CODE 4811e @937` |
| `fz2e/528053` | core-fetch | D2 | TIMING | 2 | 0.62 | `MEMR 3b716 @299` vs `CODE d8112 @299` |
| `fz2e/531032` | core-fetch | D2 | FUNCTIONAL | 0 | 0.00 | `MEMW 64e3f @1315` vs `CODE e8130 @1317` |
| `fz2e/520005` | — | D1 | FUNCTIONAL | 0 | 0.86 | `MEMR 74e84 @485` vs `MEMR 6ce74 @485` |
| `fz2e/530046` | — | D1 | FUNCTIONAL | 197 | 0.02 | `MEMR becf7 @1346` vs `MEMR bccf7 @1346` |
| `fz2e/532000` | — | D1 | FUNCTIONAL | 0 | 0.09 | `MEMR fcd9c @427` vs `MEMR f3a7c @427` |
| `fz2e/535004` | — | D1 | TIMING | 42 | 0.35 | `MEMR 70d4e @1132` vs `MEMR 6f3ca @1132` |
| `fz2c/408068` | — | D2 | TIMING | 0 | 0.17 | `MEMR d3f53 @427` vs `MEMR d3ed0 @427` |
| `fz2e/534062` | — | D2 | FUNCTIONAL | 29 | 0.15 | `MEMR bbf6f @1272` vs `MEMR b3efc @1272` |

⚠ **The six bare-`CASCADE` seats fork on a same-clock, same-status,
different-address data cycle — which is the definition of family `E1`, not of
`D1`/`D2`.** Diagnosing them here would duplicate the M10 EA-fork diagnostic
(`sw/fz2_m10.py`), which owns that shape. `fz2e/534062`'s fork instruction is
`8f ed` (`8F` with ModR/M `0xED` → `mod = 3`), so it is the **P4′ `8F` mod=3
ghost** package's, and its chip-leg address `b:bf6f` against the core's
`b:3efc` is the "`core == SS:SP`, chip is not" shape that package already
measures.

---

## 3. ENTRY-CLOCK — BOOKED. Six A3 seats are one interrupt-entry clock.

For all six, the entire program's bus transaction stream is identical and the
clock delta is 0 everywhere except at an interrupt entry. The measurement that
makes this a *characterisation* rather than an observation is the **entry gap**:
the number of clocks between the end of the last preceding bus cycle and the
announce of the entry's first transaction, on each leg, for **every** interrupt
entry in the window.

| seat | txn | entry | prev | prev ends chip / core | gap chip | gap core | verdict |
|---|---:|---|---|---|---:|---:|---|
| `fz2c/404049` | 37 | INTA | HALT | 221 / 221 | 3 | 2 | **DIFFER −1** |
| `fz2c/404049` | 58 | INTA | CODE | 368 / 367 | 4 | 4 | AGREE |
| `fz2c/404049` | 79 | INTA | CODE | 510 / 509 | 2 | 2 | AGREE |
| `fz2c/405025` | 40 | MEMR | CODE | 212 / 212 | 5 | 4 | **DIFFER −1** |
| `fz2e/510048` | 48 | MEMR | CODE | 318 / 318 | 4 | 2 | **DIFFER −2** |
| `fz2e/510048` | 326 | MEMR | CODE | 3266 / 3264 | 4 | 2 | **DIFFER −2** |
| `fz2e/515047` | 50 | MEMR | CODE | 409 / 409 | 2 | 4 | **DIFFER +2** |
| `fz2e/516066` | 39 | MEMR | CODE | 493 / 493 | 21 | 21 | AGREE |
| `fz2e/516066` | 139 | MEMR | CODE | 1810 / 1810 | 4 | 2 | **DIFFER −2** |
| `fz2e/527017` | 425 | INTA | CODE | 1721 / 1721 | 1 | 1 | AGREE |
| `fz2e/527017` | 817 | MEMR | CODE | 3309 / 3309 | 5 | 4 | **DIFFER −1** |

**11 interrupt entries measured; the entry gap AGREES on 4 and DIFFERS on 7.**

Two readings the table supports, and one it does not:

* **Supported.** Split by entry type: **6 of 7 NMI vector-read entries
  (`MEMR 00008`) differ; 3 of 4 `INTA` entries agree.** The residue is
  concentrated on the NMI entry.
* **Supported, and it is the built-in control.** `fz2e/516066` and
  `fz2e/527017` each contain an entry that agrees *exactly* and one that does
  not, in the same seed on the same bitstream. Whatever the mechanism is, it is
  **not** a uniform constant offset on every entry. `fz2e/516066` txn 39 agrees
  at gap 21 — a long gap, i.e. an entry that was not latency-limited.
* **NOT supported.** No single constant fits. The observed (chip → core) gap
  pairs are 4→2 (×4), 5→4 (×2), 3→2, 2→4, against agreeing pairs at 4→4, 2→2,
  21→21, 1→1. Chip gap 4 both agrees once and differs four times, so the gap
  alone is not the predicate. **No law is proposed and none is fitted.**

**Materiality.** The entry involved is the **rig's own terminating NMI**
(`fuzz_campaign.term_directive`, `vecsub_en`), not part of the generated
program. All six seats are TIMING with bit-identical architectural dumps and
`done_delta` of 1–4 clocks. **The cost of this mechanism is the divergence flag
and 1–4 clocks of total run length, and nothing else.**

**Re-open condition.** This is interrupt-recognition territory (the H1
re-entry recognition floor, the recognition shadow, §86's sampling boundary),
not bus arbitration. It should be taken by whoever owns recognition, with a
directed capture that produces two-digit numbers of *NMI* entries at small
gaps. **Falsifier for any future claim: it must reproduce the four AGREE rows
above, not only the seven DIFFER rows.**

---

## 4. DATA-ONLY — BOOKED to the datapath. Not a "cycle-time slip".

Four A3 seats have a bit-identical transaction stream *and* a constant-0 clock
delta over the whole window. There is no schedule component at all: the ledger
label "cycle-time slip (non-qs)" is wrong for these four, and the census
already classes one TRANSIENT and one COSMETIC.

The two FUNCTIONAL ones are single-register:

* `fz2c/406046` — `arch DW`, 2 diverging rows in a 4,000-row window. `fixed w0`,
  no event. The scored diff is the `data` column of an `IOW` (`out 0xfe,ax`
  after `mov ax,dx`): the chip writes `1af1`, the core writes `8fbd`, and the
  final `DW` is `1af1` / `8fbd`. **`DW` already differed before the write; the
  write is where it became visible.**
* `fz2e/531039` — `arch BW`, 4 diverging rows.

**Re-open condition.** These need an architectural bisect (which earlier
instruction set the register differently), not a bus analysis. A `w0`,
no-event, 2-diverging-row seed like `fz2c/406046` is the cheapest architectural
falsifier in the entire F17 residue and is recommended as the first one taken.

---

## 5. CORE-STOPS — ALREADY DECLARED. `0F 31` with a memory ModR/M.

Both seats are `0F 31` (`INS reg,reg`, `sw/optable.py` `_put0f(0x31, "INS
reg,reg", EA, modrm=True)`) with a **memory** ModR/M, and the core stops dead.

This is not a new finding. The corpus generator declares it, in its own
docstring — `sw/gen_seq.py`, `_gen_insext`:

> `"""INS/EXT bit-field (0F 31/33 reg-form, 0F 39/3B imm4-form). ONLY the`
> `reg forms (mem-mod is parked in the core). ..."""`

The structured generator therefore never emits the memory form; the `raw` and
`soup` tiers reach it anyway, because they are random bytes and `0F 31` is in
`SCRUB_ALLOWED_0F` (the D9 scrub removes only `0F` pairs outside the documented
whitelist, and the whole `0F 10–1F` / `20` / `22` / `26` / `28` / `2A` /
`31` / `33` / `39` / `3B` set is whitelisted **by design**). So these bytes are
in the corpus deliberately and the park is being exercised deliberately.

⚠ **Worth flagging to whoever schedules gates: the standing gate that would see
this, `sw/timed_ins_replay.py`, CANNOT RUN ON THIS BRANCH** (it dies in
`image_of(seed)` on `gen_seq._v1_anchor_stop`; `standing_gates.md` §A/§B and
the CLAUDE.md branch banner). A declared park with no runnable gate is the
shape of defect that stayed invisible for six days once before.

**Re-open condition.** Unparking `0F 31/33/39/3B` mem-mod is its own work item
with its own directed suite. Nothing in this block should be attributed to it
beyond these two seats.

---

## 6. THE TF TRAP BOUNDARY AFTER AN `0F`-EXTENDED INSTRUCTION — THE LEAD. BOOKED, NOT LANDED.

### 6.1 Why these two seats matter more than the other 33

`fz2_materiality_census_2026-08-11.md` §5 names **ten** `soup`-tier,
non-escaped, FUNCTIONAL seeds as *"the highest-confidence functional residue"*.
**Exactly two of the ten fall in this block, and both are `D2`:**

| seat | tier | esc | arch |
|---|---|---:|---|
| `fz2c/404041` | soup | 0 | `BW,CW,IY,PC,PS,PSW,SP` |
| `fz2e/501066` | soup | 0 | `IX` |

Both share a precondition and a shape.

### 6.2 The precondition, from the shadow-queue reconstruction

Both programs execute `push 0x100` / `popf` — **`0x100` is `PSW.TF`** — and
then an `0F`-extended bit-manipulation instruction:

```
fz2c/404041   4810f: 68 00 01   push 0x100
              48112: 9d         popf
              48113: 0f 1e 57 a0 a2      (0F 1E = bitop rm,imm; ModR/M 0x57 -> mod=01)

fz2e/501066   38130: 68 00 01   push 0x100
              38133: 9d         popf
              38134: 0f 1b e8 4f         (0F 1B = bitop rm,imm; ModR/M 0xE8 -> mod=11)
```

Instruction lengths are **not** in dispute: `optable` gives `0F 1E` + ModR/M
`0x57` (`[BX]+disp8`) + `imm8` = 5 bytes, and the chip retired 5; `0F 1B` +
ModR/M `0xE8` (register) + `imm8` = 4 bytes, and the chip retired 4. Both legs
consume the same number of bytes. The `[len N≠M retired]` annotations in the
atlas are `objdump -m i8086` not knowing the V30 `0F` map, not a disagreement
between the legs.

### 6.3 The shape, in the transaction domain

**`fz2e/501066`** — the clean one. Both legs run `… CODE 38138, CODE 3813a`.
Then:

```
  CHIP                                CORE
  MEMR 00004 @524   (IVT[1] offset)   CODE 3813c @520      <-- ONE EXTRA PREFETCH
  MEMR 00006 @530   (IVT[1] segment)  MEMR 00004 @531
  MEMW c3efe @540   0xf102  (PSW)     MEMR 00006 @537
  MEMW c3efc @548   0x2935  (PS)      MEMW c3efe @547  0xf102
  MEMW c3efa @554   0xede8  (PC)      MEMW c3efc @555  0x2935
  CODE 7be60 @560   (handler)         MEMW c3efa @561  0xedeb   <-- PUSHED PC DIFFERS
                                      CODE 7be60 @567  (handler)
```

**Over a 165-transaction window the ONLY structural difference is that the core
issues one extra `CODE` prefetch before entering the vector-1 trap.** The
streams then re-align **87/87, perfectly**. The consequence is architectural,
not cosmetic: the pushed return address is `ede8` on the chip and `edeb` on the
core — the two legs trapped at different instruction boundaries — and the
seat's `arch IX` divergence follows from the handler running with a different
return address.

**`fz2c/404041`** — the same shape, cascading. Both legs run `… CODE 4811c`.
The chip then reads `MEMR 00004 / 00006` and pushes PSW/PS/PC. The core instead
prefetches `CODE 4811e` and **retires the far `CALL` at `48118`**
(`9a 21 8a 62 9f  call 0x9f62:0x8a21`) — visible as `MEMW 93efe 0x3f62`,
`MEMW 93efc 0x8afd`, `CODE a8041` — and only *then*, at transaction 966, takes
the trap. Seven architectural words diverge and the streams re-align 2/342.

**One sentence:** *at the retirement boundary of an `0F`-extended instruction
with `PSW.TF` set, the ucore issues one or two further prefetches — and on
`fz2c/404041` retires a further instruction — before it takes the vector-1
single-step trap; silicon takes it at the boundary.*

### 6.4 The control, corpus-wide — 72 captures, 62 exact, 10 movers all failures

⚠ **A correction, recorded because the first reading of this was wrong.** An
initial pass counted vector-1 entries per leg and read `fz2c/404041` and
`fz2e/501066` as *"chip takes vector 1, core does not"*. **That is false.** Both
legs take the trap on both seats (20/20 and 2/2 entries respectively). What
differs is **where**, not **whether**. The claim in §6.3 is stated in those
corrected terms.

The control scans **all 654 banked captures** for reads of `IVT[1]`
(linear `0x00004` / `0x00006`) and compares, per capture, the number of entries
on each leg and the number of `CODE` fetches preceding the first entry:

| | captures | of which ledger failures |
|---|---:|---:|
| either leg enters vector 1 | **72** | |
| identical entry count **and** identical `CODE`-before-first-entry | **62** | 12 |
| DIFFERENT number of vector-1 entries | 7 | **7** |
| same count, first entry after a different `CODE` count | 3 | **3** |

**All 10 movers are ledger failures; the 62 that agree include 12 captures that
are ledger failures for other reasons.** The three clean movers — the +1/+2
prefetch-before-trap shape — are:

| seat | ledger family | entries chip / core | `CODE` before first entry, chip / core | delta |
|---|---|---|---|---|
| `fz2c/404041` | **D2** | 10 / 10 | 85 / 87 | **CORE +2** |
| `fz2e/501066` | **D2** | 1 / 1 | 61 / 62 | **CORE +1** |
| `fz2e/513019` | **C2** | 17 / 17 | 82 / 84 | **CORE +2** |

⚠ **`fz2e/513019` is filed `C2 INTA-vectored delivery`, not `D2`** — and it is
another of the census's ten highest-confidence `soup`/non-escaped FUNCTIONAL
seeds. **The mechanism crosses the ledger's family boundary**, which is the
same point §0 makes about the labels generally. The remaining 7 movers are
gross count differences (one leg never trapping at all) and are all escaped or
runaway seeds; they are not evidence for this shape and are not counted toward
it.

### 6.5 The mechanism prediction, and the predicate it bears on

`ucore_provenance.md` §86 (SM3 sitting 25) registers the BRK/TF single-step
arm's sampling boundary as **ONE predicate — the `QS = 1` opcode pop** —
*"because a prefix retires with its own F pop"*.

An `0F`-extended instruction is a **two-byte opcode**. Its `0F` byte is popped
as an opcode-first-byte (`QS = 1`) and its second byte is popped after it. A
boundary predicate written as "the `QS = 1` opcode pop" therefore has a
different meaning on `0F xx` than on a one-byte opcode: the pop that the
predicate keys on is the `0F`, one pop *earlier* than the instruction whose
retirement should arm the trap. **The +1/+2 prefetch-before-trap offset
measured in §6.3–§6.4 is what that would look like on the bus.**

This is a **prediction, not a measurement.** Nothing in this document reads
`SSA_E_BRK` or any of the arm's five flops; that is the next step, not this
one.

### 6.6 Verdict: BOOKED. The blocker is the denominator.

**The derivable population is THREE seats.** A DERIVE/HOLDOUT split by
address-independent hash over three seats is not a validation — it is a
one-or-two-seed holdout whose score carries no information, and the standing
rule that *"a refuted key's REPLACEMENT must be validated on data that was not
used to select it"* cannot be honoured at that size. Deriving a predicate on
`fz2c/404041` + `fz2e/501066` and "validating" it on `fz2e/513019` would be
fitting with a ceremony attached.

**A clean book beats a fitted land. Booked.**

**Re-open condition.** A directed TF × `0F` capture. The corpus is known to
carry **101 `PSW.TF` seeds** (CLAUDE.md, FLASH #14 line), of which only 72
captures reach `IVT[1]` at all in the banked set; a directed population that
crosses TF with the whitelisted `0F` band (`0F 10–1F` bitops, `0F 28/2A` ROL4/
ROR4, `0F 31/33/39/3B` INS/EXT, `0F 20/22/26` 4S) at both `mod = 3` and
`mod ≠ 3` would give a two-digit denominator and a real split. **Register the
split before deriving.**

⚠ Note for scheduling: this is `C1`'s registered directed-cell debt, and
`sw/sm3_tf_floor_cell.py` — the tool that would exercise it — **cannot run on
this branch** (CLAUDE.md, FLASH #14 line). Two of the three seats in the only
lead this block produced sit behind a tool that this branch cannot execute.

---

## 7. THE REP-STRING PREFETCH-ARBITRATION HYPOTHESIS — RAISED AND REFUTED

**This section records a hypothesis that was formed and then killed by its own
control. It is written down because a refutation that is not written down gets
re-derived.**

### 7.1 What suggested it

`fz2e/531032` (`f3 ab`, `REP STOSW`, `D2`, FUNCTIONAL, `esc = 0`), transactions
around row 1273–1360:

```
CHIP: MEMW 4e3a  MEMW 4e3b  MEMW 4e3c  CODE e8130  CODE e8132  CODE e8134
      MEMW 4e3d  MEMW 4e3e  MEMW 4e3f  MEMW 4e40  MEMW 4e41  MEMW 4e42
      MEMW 4e43  MEMW 4e44  MEMW 4e45  MEMW 4e46  MEMW 4e47   <-- 11 stores, NO fetch

CORE: MEMW 4e3a  MEMW 4e3b  MEMW 4e3c  CODE e8130  CODE e8132  CODE e8134
      MEMW 4e3d  MEMW 4e3e  CODE e8130  CODE e8132  CODE e8134     <-- SAME 3 addresses
      MEMW 4e3f  MEMW 4e40  CODE e8130  CODE e8132  CODE e8134     <-- again
```

The reading: *during a REP string loop the ucore re-runs the fetch path once
per iteration — flushing and re-fetching the prefix and opcode from the same
three addresses — where silicon keeps the loop internal and leaves the queue
alone.* Simple, one predicate, 80s-plausible.

### 7.2 The control that killed it

Pre-registered discriminator: the **longest run of consecutive data cycles**
(`MEMR`/`MEMW`/`IOR`/`IOW` with no `CODE` between them) on each leg, measured
over **all 654 banked captures**.

| population | n | core run SHORTER | equal | core run LONGER | median delta |
|---|---:|---:|---:|---:|---:|
| all banked captures | 654 | 14 | 630 | 10 | 0 |
| ledger FAILURES | 113 | 14 | 89 | 10 | 0 |
| **ledger PASSES** | **541** | **0** | **541** | **0** | **0** |

**The core and the chip have the identical longest data-cycle run on 541 of
541 non-failing captures** — including captures with runs of 97 — and every one
of the 24 differing captures is already a ledger failure. Within the block
itself the core sustains runs of **596** (`fz2e/531030`, chip 596 core 597),
**419** (`fz2e/527065`, 419/419), **404** (`fz2c/407000`, 404/404) and **370**
(`fz2e/520005`, chip 372) without inserting a fetch.

**The ucore has no structural inability to hold a long data-only run.**
`fz2e/531032` (chip 384 / core 170) is a single seed that had already forked at
transaction 254, row 1313 — the re-fetch pattern is **downstream** of that
fork, not its cause.

**REFUTED.** The hypothesis is not carried forward and no RTL was written
against it.

### 7.3 What survives from that line: an exact arithmetic invariant

Of the seats whose architectural diff is a subset of `{CW, IX, IY}`, **all four
satisfy `ΔIX = ΔIY = −step · ΔCW` with a single step per seat**:

| seat | mechanism | arch | ΔCW (core−chip) | ΔIX | ΔIY | step | verdict |
|---|---|---|---:|---:|---:|---:|---|
| `fz2e/520005` | CASCADE | `CW,IX,IY` | +1 | −1 | −1 | **1** (byte) | CONSISTENT |
| `fz2e/531030` | CASCADE(chip-fetch) | `CW,IY` | −1 | — | +2 | **2** (word) | CONSISTENT |
| `fz2e/532021` | CASCADE(chip-fetch) | `CW,IX,IY` | −1 | +2 | +2 | **2** (word) | CONSISTENT |
| `fz2e/531032` | CASCADE(core-fetch) | `CW,IY` | +122 | — | −244 | **2** (word) | CONSISTENT |

**4 of 4.** The architectural cost of these four seats is *exactly* "the string
loop ran a different number of iterations", and **nothing else in the register
file moved** — no flag-only corruption, no ALU divergence. `fz2e/531030`
(INT, delay 62) and `fz2e/532021` (INT, delay 528) differ by **one** iteration
and both exit to an interrupt, which is the §3 recognition question observed at
iteration granularity rather than clock granularity. `fz2e/531032` (+122
iterations) does not fit that reading and is booked as an outlier.
`fz2e/520005` has **no event at all** (`fixed w2`), so its loop exit is a `CW`
test, and its fork is a same-clock different-address `MEMR` — it belongs with
the `E1` shape of §2.1, not with the recognition question.

**Re-open condition.** The invariant is a cheap, exact predicate and should be
re-run as a check on any future landing that claims to move a string-loop seat:
*if a fix moves `CW` it must move `IX`/`IY` by exactly `−step · ΔCW`, or it has
broken something else.*

---

## 8. WHAT CLOSED — NOTHING. THE ACCOUNTING.

The block is **15 FUNCTIONAL / 15 TIMING / 1 TRANSIENT / 4 COSMETIC**, before
and after. No seat moved, `bars` is untouched, no gate ran or moved, `hdl/` is
byte-identical to `ae3da7c59a`.

What changed is **attribution**:

| | seats | FUNC | TIME | disposition |
|---|---:|---:|---:|---|
| ENTRY-CLOCK | 6 | 0 | 6 | booked to interrupt recognition (§3) |
| DATA-ONLY | 4 | 2 | 0 | booked to the datapath (§4) |
| GHOST-ADDR | 3 | 0 | 0 | booked to the ghost-read package |
| CORE-STOPS | 2 | 2 | 0 | already declared park, `_gen_insext` (§5) |
| TF trap boundary | 2 | 2 | 0 | **the lead** — booked, blocker = denominator 3 (§6) |
| E1/M10-shaped | 6 | 4 | 2 | booked to M10 (one of them to P4′ `8F`) |
| remainder (cascade) | 12 | 5 | 7 | no mechanism claimed |

* Of 15 FUNCTIONAL: 2 are a declared park, 2 are the TF lead, 2 are
  datapath-only, and 9 cascade — 4 of those E1/M10-shaped and 2 explained
  arithmetically as a string-iteration count (§7.3).
* Of 15 TIMING: 6 are the terminating-NMI entry clock, with **bit-identical bus
  transactions and bit-identical architectural dumps**, costing 1–4 clocks of
  total run length; 9 cascade.
* The 5 immaterial seats (3 ghost-read COSMETIC, 1 TRANSIENT, 1 COSMETIC) carry
  **no schedule component whatsoever** — identical transactions at identical
  clocks.

**The `D1`/`D2` "prefetch-request arbitration" reading of 20 seats is not
supported by the transaction-domain evidence.** In every `D1`/`D2` seat the
"one leg fetched and the other did not" is the first *visible* consequence of a
divergence in state — an EA, an iteration count, or a trap boundary — that had
already happened.

---

## 9. FALSIFIERS FOR THIS DOCUMENT

Everything above is recomputable from the banked captures plus the F17 ledger,
offline, with no board. Each claim and what would break it:

1. **The partition (§2).** Recompute `extract_txns` alignment with `p, q`
   searched independently over `0..8`. If any seat listed as
   stream-identical shows `j < min(len(a), len(b))`, §2.1 is wrong for that
   seat. *(A pure insert/delete search — `p` or `q` forced to 0 — mis-scores
   eight seats; do not use it.)*
2. **ENTRY-CLOCK (§3).** If any of the six shows a clock step at a
   non-interrupt transaction, the mechanism name is wrong. If the four AGREE
   rows do not reproduce, the table is wrong.
3. **CORE-STOPS (§5).** If `fz2c/407067`'s core leg issues any transaction
   after row 1594 within the window, "stops dead" is wrong.
4. **The TF lead (§6).** If `fz2e/501066`'s streams do not re-align 87/87 after
   the single extra `CODE 3813c`, or if either leg's vector-1 entry count is
   not 1/1 and 20/20 respectively, §6.3 is wrong. If the corpus-wide control
   does not read 72 / 62 / 7 / 3, §6.4 is wrong.
5. **The REP refutation (§7).** If the longest-data-run control does not read
   **541/541 equal on non-failures**, the refutation is unsound and the
   hypothesis must be re-opened.
6. **The invariant (§7.3).** If any of the four seats violates
   `ΔIX = ΔIY = −step · ΔCW`, §7.3 is wrong.
7. **The instrument (§0.2).** If the era guard does not PASS at HEAD, or the
   replay does not reproduce 35/35 verdict and 35/35 `first_bad_row`, **no
   figure in this document is quotable** — every one of them is read against
   a fabric column, and the guard is what says the RTL is the RTL in the
   socket.
