# M10 — the "EA fork" family, DIAGNOSED (2026-08-10)

**SIMPLICITY: this is 80's era hardware — nothing on the die is wasted. Complex
or confusing observed behavior is likely simple systems interacting in ways not
yet understood. A large fitted table, a many-cased rule, or a per-opcode special
case is a signal of misunderstanding, not a deliverable.**

Wave-3 DIAGNOSTIC package M10.  **Offline, diagnosis only** — no RTL was
touched, no board, no flash, no Quartus.  Tree `fuzz-v2-on-relanding` at
`24ea7eb580`.

## 0. The headline, in four sentences

1. On the F15 ledger M10 (family `E1`, *"same-status data cycle, different
   address"*) is **41 seats**.
2. **31 of the 41 are P4′ seats, not M10 seats** — the chip retired an `8F`
   mod==3 within six `F` pops of the fork, the forking cycle is that form's
   ghost stack read, and the background rate for that coincidence is **5.84 %**
   (479 / 8,200 random rows in the *same* seeds).  The honest M10 count after
   the move is **10**, and two of those ten are not address forks at all, so
   the family is **8 seats**.
3. The register-file solve the F14 survey proposed **RAN** and it did not need
   a board: `+ss_at=<clk> +ss_mode=6` on the receipted `--core ucore`
   `tb_v30_core` binary reads the whole addressed save-state stream at any CE
   clock, the row↔clock offset **measures to 0**, and the ucore's own
   architectural registers at the fork are therefore readable.  On the P4′
   cheap subset it **names a shape**: the chip's ghost offset is a *retained
   address rail*, sometimes bitwise-ANDed with `SP`, and `ghost_relax` — the
   `FFFF / C000 / 8000 / 0080` mask in `v30u_eu.sv` — is the term that gets it
   wrong.
4. On the residual 8 the same solve comes back **EMPTY on 6 of 8**: no
   segment × (register, or bitwise pair of registers, or `+1` split half)
   over the ucore's whole architectural + EA register file reproduces the
   chip's address at **any** freeze in `[-12, +1]`.  That is the legitimate
   negative result the brief anticipated, and §6 specifies the directed cell —
   but §6.0 specifies a **free offline step that must be run first**.

## 1. Provenance — what this rests on

| thing | id |
|---|---|
| ledger | `sw/testdata/fz2/fz2_failure_ledger_f15_2026-08-10.json` |
| era (the bitstream the captures were taken on) | `.sof 2dc38a17d6c3…`, `flash_git 77838ef777` |
| corpus | `fz2c` + `fz2e`, 3,840 seeds, 3,838 scored, 116 failures |
| every capture | sha256-ASSERTED against the ledger before it is read (`fz2_m10.capture`) |
| offline engine | `hdl/tb/obj_dir_ucore/Vtb_v30_core`, artifact receipt `1f7af54a0174cede…` |
| tool | `sw/fz2_m10.py` (this campaign's; `survey` / `control` / `solve` / `report`) |
| the full 41-row table | `python3 sw/fz2_m10.py report` regenerates it from the three JSONs; nothing in it is typed by hand |
| survey output | `sw/testdata/fz2/fz2_m10_survey.json` |
| control output | `sw/testdata/fz2/fz2_m10_control.json` |
| solve outputs | `sw/testdata/fz2/fz2_m10_solve.json`, `…_solve_residual.json` |

The shadow-queue reconstruction, the group cut and the disassembly are
`sw/fz2_failview.py`'s — the atlas's own, validated there 116/116 with a
145/145 control on a disjoint corpus.  Nothing new was invented to read the
retired stream.

## 2. The F14 survey's M10 characterisation, checked against F15

| F14 survey said | F15 measures | verdict |
|---|---|---|
| ~40 seats | **41** | holds |
| 31/40 differ in the T1 address | **36/41** | holds in kind; the number moved |
| "not a segment/paragraph fork — only 11/31 are `mod 16 == 0`" | 11/41 chip addresses are `mod 16 == 0` | **the test was the wrong one** (below) |
| 34 distinct opcodes, no concentration | 33 distinct dispatched opcodes | holds *as stated*, and it is **misleading** (§3) |
| a 13-seed cheap subset (`≤8` diverging rows and `arch==OK`) | **12** such seats on F15 | holds |

Two corrections that matter.

**(a) The paragraph test.**  A pure segment fork means the two legs share the
offset, i.e. `Δ mod 16 == 0` — not that the chip's address is paragraph
aligned.  Measured properly, **19 of 41** are consistent with a segment-only
fork by that arithmetic.  Under the register solve exactly **one** of them
actually is one (`fz2c/406006`, §5.2), so the survey's *conclusion* — "not a
segment fork" — survives; its *evidence* did not.

**(b) The cheap subset is not M10.**  All **12** of the F15 cheap seats
(`arch_match` and `≤8` diverging rows) reclassify to P4′ under §3.  The honest
M10 cheap subset is **0** — every residual M10 seat carries `arch DIFF` and a
median of 2,259 diverging rows against the P4′ seats' median of 60.

**The first diverging column** at the fork is `data` 35, `qs` 3, `bs` 2,
`bs+data` 1.  On the 35 `data` seats the divergence is the `nxta` preview of the
*next* cycle's address, and the full 20-bit address appears at that cycle's own
`T1` one row later; every address quoted in this document is that `T1` address,
on both legs, by `fz2_m10.cycle_at`.

## 3. THE RECLASSIFICATION — 31 of 41 seats are P4′

### 3.1 What the artifact showed

`fz2_failview` names "the instruction in dispatch at the fork" as the last
`QS = F` pop at or before the fork row.  That cut **misses the 8F ghost
entirely**, because the ghost read is a bus cycle the `8F` mod==3 form issues
*after* it retires: by the time the cycle reaches the pins the queue has already
popped the next instruction's `F`, and the atlas names *that* one.  Five of the
ten seats the first cut called "cheap M10" have `8f c3` / `8f c9` / `8f d2` /
`8f e0` / `8f f5` **one pop back** and the fork is its stack read.

Scanning back six `F` pops instead:

```
RECLASSIFY, cut at the fork's OWN dispatch:  P4' (8F mod==3): 8   P5' (8E/1): 0   stays M10: 33
RECLASSIFY, nearest within 6 F pops:         P4': 31              P5': 0          stays M10: 10
  P4' distance histogram (F pops back): [(0, 8), (1, 18), (2, 3), (3, 2)]
```

The distance histogram is the mechanism's own signature: **8 seats fork while
the `8F` is still the dispatched instruction and 18 fork exactly one pop later**
— which is the ghost read arriving on the wire one instruction behind its
issuer.

The criterion is **the RTL's own predicate**, not a guess.
`v30u_eu.sv:915` gates the ghost on `upc_opc == 8'h8f` with `m_kind == OK_REG`
and `wb_kind == OK_REG`, i.e. exactly `8F` with `mod == 3`.

### 3.2 The base rate — the control that makes it a claim

Two controls, both in `sw/fz2_m10.py control`, both on the same reconstruction
and the same rule:

| control | measurement |
|---|---|
| **A** — 200 random rows inside each of the same 41 seeds' own scored windows | `8F` mod==3 within 6 `F` pops: **479 / 8,200 = 5.84 %** |
| **B** — the other **75** ledger failures at *their* own fork rows | **20 / 75 = 26.67 %** |
| **the M10 forks** | **31 / 41 = 75.61 %** |

Binomial, one-sided: `p = 3.6e-30` against control A, `p = 9.1e-11` against
control B.  Control B is the interesting one and it is reported as measured:
`8F` mod==3 is elevated at *every* family's forks (26.7 % against a 5.8 %
background), so it is a general trouble source in this corpus — and M10's forks
are still three times more concentrated on it than any other family's.

Control A is **conservative**: random *rows* weight an instruction by its
duration, and the ghost read is slow, so 5.84 % over-states the background.

### 3.3 P5′ is zero

No M10 seat retires an `8E` with `reg == 1` within six `F` pops of its fork.
The CS-retarget package takes **no** seats from M10.  (`v30u_eu.sv:1490` does
special-case `pe_opc_reg == 8'h8e` inside `ghost_ea_off`, so the two packages
touch the same rail — but no M10 seat reaches it.)

### 3.4 What moves, and what the P4′ agent inherits

**31 seats move to P4′.**  30 are `raw` tier, 1 is `soup`; 18 carry
`arch_match`, 12 have `≤8` diverging rows, median diverging rows 60.  Three of
them (`fz2e/518006`, `fz2e/518050`, `fz2e/522003`) have **identical** chip and
core addresses at the forking `T1` and fork on `qs`/`bs` instead — they are in
the family by label only and the P4′ agent should expect them to close on
timing, not on address.

The 23 distinct dispatched opcodes across the 31 seats are **not** 23
mechanisms: they are the instruction that happened to be popped when someone
else's bus cycle arrived.  The F14 survey's "34 distinct opcodes, no
concentration" is true of the label and false of the mechanism, and that is
exactly the reading that kept the family looking un-diagnosable.

## 4. THE REGISTER-FILE SOLVE — method, and why it is admissible

### 4.1 The instrument

`uscope.py` binds to the `v0.1` golden suite by `(form, idx)` and cannot be
pointed at an fz2 seed, so it was **not** used.  What was used is already in the
tree and needed no RTL change:

* `hdl/tb/tb_v30_core.sv` **save-state mode 6** (`+ss_at=<cpu_cyc>
  +ss_mode=6 +ss_scramble_seed=0`) — freeze at a CE clock, stream the whole
  addressed save-state map out through `SS_RDATA`, print it, restore, resume.
  It is §49.8's deciding measurement in its READ form: *"`+ss_at=<clk>` reads
  … out at the boundary … on the frozen binary, no RTL change"*.
* the seed driven exactly as `fz2_a1_rescore.one` drives it — image
  re-derived through `fuzz_campaign.compose_case` with the banked
  `image_sha256` **asserted**, the campaign's own wait source (`fixed` /
  `wrand` / `wvec`), the campaign's own terminating NMI on the TB's single
  scheduler.

The map gives, per freeze: the eight GPRs, the four segment registers, `PC`,
`PSW`, `TMPA/B/C`, `OPR`, `IND`, `M_EA`, `R_EA`, `WB_EA`, `PEND_OFF`, and — the
ghost's own rails — `EA_RESIDUE` (`0x177`) and `EA_PAIR_RHS` (`0x178`).  Every
address is **lifted from `hdl/rtl/ucore/v30u_ss_pkg.sv` at run time**, never
transcribed.

### 4.2 Calibration, and the two gates a seat must pass

`cpu_cyc` counts CE posedges from reset release; the recorded row index counts
rows emitted while `recording`.  The offset is **measured, not assumed**: sweep
the freeze across the fork and read the BIU's own current-address register
(`SSA_B_CUR_ADDR_LO/HI`).  On `fz2e/519016`:

```
 d=-2 biu=a8106  SP=9922 SS=b355 IND=9922 TMPA=9a42
 d=-1 biu=a8106  SP=9924 SS=b355 IND=9922 TMPA=9a42
 d=+0 biu=bcf92  SP=9924 SS=b355 IND=9a42 TMPA=9a42     <- the forking cycle's own address
```

The offset is **0**: `cpu_cyc == row index`.

Two gates, both pre-declared, both refusing rather than fitting:

* **NOREPRO** — the offline replay must put the fork at the board's row with the
  board's core address.  3 of the 12 registered P4′ cheap seats fail it
  (`fz2c/409025`, `fz2e/517046`, `fz2e/535036`) and are **not scored**.  All
  three carry a **stimulus pin event** (NMI d=1218, INT d=63 hold=300, NMI
  d=789) and `tb_v30_core` has one scheduler, which is spent on the terminator.
  This is `fz2_replay.py`'s documented reason for existing; the seats are
  recoverable on `tb_sys`, which was not built for this diagnostic.
* **no free parameter** — the solve admits **no displacement**.  A displacement
  fits anything.  The space is 21 named 16-bit terms, their 190 pairwise `&`
  and `|` (the two things a shared internal bus can produce with two drivers
  live), each `+0` or `+1` (the RTL's own `acc_phys2 = acc_phys_base + 1` split
  half), times the four segment registers — **3,208 named expressions**, tested
  at 14 freezes.  An exact 20-bit hit is worth 2⁻²⁰ per expression, so the
  expected number of accidental fits is 3,208 / 2²⁰ ≈ **0.003 per freeze**: a
  fit is evidence and an EMPTY is a real absence.

## 5. RESULTS

### 5.1 The P4′ cheap subset — 6 of 9 scored seats NAME a shape

12 registered (`arch_match`, `≤8` diverging rows, chip ≠ core address),
3 NOREPRO, **9 scored**.

| seat | chip | core | what fits the CHIP | what fits the CORE |
|---|---:|---:|---|---|
| `fz2c/410008` | `d4f33` | `d52d3` | `SS:(rail & SP)` | `SS:rail` |
| `fz2e/519016` | `bcd52` | `bcf92` | `SS:(rail & SP)` | `SS:rail` |
| `fz2e/520040` | `7bb70` | `7fbb7` | `SS:(rail & SP)` | `SS:rail` |
| `fz2e/519072` | `5aaa0` | `66a8a` | `SS:(SP & M_EA)` = `SS:(SP & WB_EA)` | `SS:EA_RESIDUE` |
| `fz2e/530034` | `68578` | `6be20` | `SS:M_EA` = `SS:WB_EA` — **plain, no AND** | `SS:EA_RESIDUE` |
| `fz2e/526054` | `593fe` | `b9fce` | **the same expression as the core** (`SS:IND+1`) with `SS` sampled one clock later (`b9b8` → `58fb`) | `SS:IND+1` at the earlier `SS` |
| `fz2e/518033` | `813a4` | `81324` | **EMPTY** | `SS:(TMPA & IND)` |
| `fz2e/524055` | `3a400` | `3a3c0` | **EMPTY** | `SS:0000` |
| `fz2e/528010` | `8b92d` | `863a8` | **EMPTY** | `SS:TMPB+1` |

"rail" is `EA_RESIDUE` and `TMPA` (equal at those freezes), i.e. exactly the
RTL's `ghost_off`.  Every chip-side fit on the first three seats is a
**wired-AND**; not one is a single term and not one is an OR.  The direct
predicate test — `SS:(ghost_off & SP)` evaluated with the RTL's own
`ghost_off = ghost_uses_ea ? ghost_ea_off : tmpa` — reproduces the chip exactly
on those three at freeze `-3` and `-2`.

### 5.2 What that says about `ghost_relax`

`v30u_eu.sv:1503`:

```verilog
wire [15:0] ghost_relax = eu_ghost_full ? 16'hFFFF
                         : eu_ghost_idle ? ((pe_op8 ? 16'hC000 : 16'h8000) |
                                            (ghost_next_byte ? 16'h0080 : 16'h0000))
                         : 16'h0000;
wire [15:0] ghost_bus_off = ghost_uses_mul_hi ? (tmpa & opr)
                            : (eu_ghost_idle && !q_ripe) ? gpr[R_SP]
                            : (ghost_off & (gpr[R_SP] | ghost_relax));
```

This is a mask table with four constants and a per-opcode-class case
(`ghost_uses_mul_hi` is `pla3_native(pe_opc_reg) == 14'h0104`).  **The
SIMPLICITY principle says that shape is a signal of misunderstanding**, and the
solve is the first measurement that agrees with it from outside the fit:

* on `410008`, `519016`, `520040` the chip performs the AND and the core does
  not — `ghost_relax` was non-zero across the differing bits and should have
  been **0**;
* on `530034` the chip performs **no** AND at all and takes a *different rail*
  (`M_EA`, the retained ModR/M address) where the core takes `EA_RESIDUE`;
* on `519072` the chip ANDs `SP` with `M_EA`, again not with `EA_RESIDUE`;
* on `526054` the offsets are **identical** and the fork is the **segment**:
  silicon samples `SS` one clock later than the ucore, after a `MOV SS`/`POP SS`
  has landed (`SS b9b8 → 58fb`, and `OPR` carries the same value one freeze
  earlier).

So the shape is `SS : (retained rail [& SP])` on five of six, and the two free
choices the ucore makes badly are **which rail** and **whether the AND
happens** — not a mask.  A wired-AND of two live drivers on one internal bus is
a simple system; a four-constant relax mask is what you write when you have not
found it.

**This is P4′'s to act on, not M10's.**

### 5.3 The residual M10 — 10 seats, of which 8 are address forks

| seat | fork | col | div | in dispatch | note |
|---|---:|---|---:|---|---|
| `fz2e/501069` | 1547 | `bs` | 1960 | `ac` (LODSB) | **not an address fork** |
| `fz2e/510043` | 971 | `bs` | 2259 | `aa` (STOSB) | **not an address fork** |
| `fz2c/406006` | 478 | `data` | 16 | `0f 3b 2a 8c` | segment fork, §5.4 |
| `fz2c/406054` | 470 | `data` | 3141 | `ff b8 2b 1a` (`FF /7`) | solve EMPTY |
| `fz2c/408019` | 1617 | `data` | 1087 | `29 96 23 ca` | solve EMPTY |
| `fz2e/518038` | 429 | `data` | 194 | `c1 62 06 9a` | solve EMPTY |
| `fz2e/522019` | 396 | `data` | 3075 | `11 6c 9c` | solve EMPTY |
| `fz2e/524034` | 457 | `data` | 3479 | `84 82 84 65` | solve EMPTY |
| `fz2e/530001` | 442 | `data` | 20 | `86 79 68` | solve EMPTY |
| `fz2e/535027` | 296 | `bs+data` | 3226 | `a4` (MOVSB) | chip `CS/DS:IX`, core `SS:SP` |

**`fz2e/501069` and `fz2e/510043` are mis-filed.**  Both legs drive the *same*
address, linear `0x00004` — the **vector-1** IVT entry — and the fork column is
`bs`.  Both are preceded by `cf` (IRET); the other leg drives `0x00004` two rows
later (`501069`: core row 1548, chip row 1550; `510043`: core 972, chip 974).
This is single-step/trap **delivery timing**, i.e. C1/P2 territory, and there is
no address to solve.  They should leave `E1`.

**M10 proper is 8 seats.**  All 8 carry `arch DIFF`.

### 5.4 The solve on the residual 8 — EMPTY on 6

All 8 pass the NOREPRO gate (8/8 scored).  Chip-side fits, best over the whole
freeze sweep `[-12, +1]`:

* **`fz2c/406006` — NAMED, and it is a pure segment fork.**  Chip `57b6f`,
  core `7b3cf`, **the same offset** `0x970f`, and the chip uses **`SS`
  (`4e46`)** where the core uses **`DS` (`71cc`)**.  The dispatched form is
  `0f 3b 2a 8c` — an undocumented `0F`-page opcode.  One seat, one term, and it
  is the *only* one of the 19 `Δ mod 16 == 0` seats that actually is a segment
  fork.
* **`fz2e/535027` — NAMED but incoherent.**  Chip `CS:IX` = `DS:IX`, core
  `SS:SP`.  Different segment *and* different offset register on `a4` (MOVSB)
  with a `bs+data` fork and 3,226 diverging rows; this is very unlikely to be an
  EA-formation question and should be re-triaged.
* **the other 6 — `SS`/`DS`:`IND` = `M_EA` = `WB_EA` reproduces the CORE
  exactly on every one of them** (the architecturally-correct ModR/M effective
  address, which is what those instructions ask for), **and NOTHING in the
  3,208-expression space reproduces the CHIP at any of the 14 freezes.**  The
  chip's address is also not a *different cycle*: it appears nowhere as a `T1`
  address on the core's leg within ±40 rows, on any of the 8.

**That is the negative result, stated as a negative result.**  The ucore
computes the architecturally-correct EA and silicon drives something that is not
any single term, any bitwise pair, or any `+1` split half of the ucore's own
architectural + EA register file at that clock.  Two readings survive:

* **(i) upstream value divergence** — the chip's registers at the fork already
  differ from the ucore's.  All 8 seats carry `arch DIFF`, so this cannot be
  excluded from the ledger; the two legs are bus-identical up to the fork, but a
  register that differs without being *used* leaves no bus trace until it is,
  and the fork is that moment.
* **(ii) a rail the ucore does not model** at all, so it is not in the save-state
  map and no readout can find it.

**Nothing in this diagnostic distinguishes (i) from (ii), and no fix should be
attempted until something does.**

## 6. WHAT THE NEXT WAVE SHOULD DO

### 6.0 STEP ZERO — free, offline, and it decides (i) vs (ii)

Do this before spending a single socket capture.  For each of the 6 EMPTY
seats, freeze the ucore at the fork (`fz2_m10.py solve --seeds …` already
writes the full register dump into `fz2_m10_solve_residual.json`) and ask
whether the CHIP's address becomes expressible if **one** register is allowed to
differ — i.e. solve `chip = seg:(base + δ)` for a single named base and report
δ.  If the same δ also equals the difference between the ucore's result and the
architectural result of some instruction retired earlier in that seed's stream,
reading (i) is established and **M10 is not an EA family at all** — it is
downstream of a decode/execute bug in an earlier instruction, and the seats
belong to whichever package owns that opcode.  Six of the eight dispatched forms
are ordinary ModR/M memory operations (`29 /r`, `11 /r`, `84 /r`, `86 /r`,
`c1 /r`) and one is the undocumented `FF /7`; that mix is exactly what reading
(i) predicts and reading (ii) does not.

### 6.1 THE DIRECTED CELL, if step zero comes back empty

One opcode, explicit register setup, **≈ 90 socket captures**.  Registered in
advance:

* **program**: a fixed preamble loading `AW BW CW DW SP BP IX IY` and
  `ES CS SS DS` to distinct, non-aliasing values (each segment's paragraph
  disjoint from every other, each index register distinct in every nibble, so
  that no two candidate expressions can collide), then **one** `29 /r` (`SUB
  r/m16, r16`) memory form, then a `NOP` fence.
* **sweep**: the 8 ModR/M `r/m` bases at `mod = 2` (`disp16`, so the
  displacement is explicit and readable) × the 5 segment-override cases
  (none, `26`, `2E`, `36`, `3E`) = **40 cells**, at **two wait levels** (`w0`,
  `w1`) = 80, plus **10 controls**: the same 10 cells re-run at the end of the
  session (rig-integrity), `div_guard()` PINNED on every probe, socket only
  (`use_core=False`).
* **the measurement**: the operand read's `T1` address, compared to
  `(seg<<4) + EA` computed from the preamble's own values.
* **the pre-registered bar**: if all 80 cells match the architectural EA, then
  the chip forms the EA correctly under clean state and **reading (i) is
  established by elimination** — the residual M10 is an upstream value
  divergence and the family dissolves.  If any cell forks, that cell is the
  minimal reproducer and the diagnosis becomes a one-cell question instead of an
  8-seat one.
* **what would make it wrong**: choosing the opcode after seeing the result.
  `29 /r` is named here, before any capture, because it is the residual family's
  most ordinary member (`fz2c/408019`).

### 6.2 Ledger hygiene the next wave should land

1. **Move 31 seats from `E1` to P4′** (the list is `fz2_m10_survey.json`, field
   `near_package == "P4"`, with `near_dist` and the retired `8F` bytes beside
   each).  Three of them (`518006`, `518050`, `522003`) have equal addresses and
   fork on `qs`/`bs` — flag them as timing, not address.
2. **Move `fz2e/501069` and `fz2e/510043` out of `E1`** to the trap-delivery
   family; they are the *same* address two rows apart.
3. `E1`'s remaining count is **8**, and the family label should say
   *"EA fork, cause not in the ucore's register file"* rather than
   *"same-status data cycle, different address"*, which describes 41 seats and
   explains none.

## 7. FALSIFIERS

* **The reclassification** is refuted if the `8F` mod==3 proximity at M10 forks
  is not separable from control A/B — re-run `fz2_m10.py control` with a
  different `--seed`; the rates must stay near 5.8 % / 26.7 % against
  75.6 %.  It is *also* refuted if a P4′ landing that changes only the ghost
  address moves none of the 31.
* **The `ghost_relax` finding** is refuted if a build with `ghost_relax` forced
  to `0` fails to close `fz2c/410008`, `fz2e/519016`, `fz2e/520040` — those
  three are named in advance and the solve says the AND is unconditional there.
  It is **not** claimed that forcing it to 0 closes the other six; `530034` and
  `519072` need the *rail* changed and `526054` needs the segment sample moved.
* **The residual EMPTY** is refuted the moment any named term reproduces one of
  the six.  The search space, the freeze range and the per-seat register dumps
  are in `fz2_m10_solve_residual.json`; anyone can widen the space and try.
* **The calibration** is refuted if `cpu_cyc != row` on any seat — the tool
  reports the BIU address at every freeze and a seat whose freeze never shows
  the forking address is reported, not scored.

## 8. What was NOT done, and why

* **No board.**  Every number here is offline.
* **`sim/` was not extended** (defunct, per the brief) and no architectural
  readout was invented — save-state mode 6 already existed.
* **`tb_sys` was not used**, so the 3 NOREPRO seats stay un-scored rather than
  being scored on a harness whose event model does not match their capture.
  Recovering them is a `fz2_replay.py`-shaped job for whoever wants those three.
* **No RTL was touched.**  `ghost_relax` is diagnosed, not edited.
