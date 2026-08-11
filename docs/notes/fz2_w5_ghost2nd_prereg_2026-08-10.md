# fz2 WAVE-5 — THE 8F GHOST SEATS' **SECOND DIVERGENCE** — PRE-REGISTRATION

**SIMPLICITY: this is 80's era hardware — nothing on the die is wasted. Complex
or confusing observed behavior is likely simple systems interacting in ways not
yet understood. A large fitted table, a many-cased rule, or a per-opcode special
case is a signal of misunderstanding, not a deliverable.**

Committed **before the first line of RTL**.  Branch `fuzz-v2-on-relanding`,
base **`8280031c8d`** (the worktree provisioned at `master`/`29dcc5b05f` and was
reset; `git rev-parse HEAD` verified `8280031c8d`).  Offline throughout; **no
board, no flash, model defunct.**

Ledger: `sw/testdata/fz2/fz2_failure_ledger_f16_2026-08-10.json`.  Every
post-RTL `fz2_replay` figure is OFFLINE and CROSS-ERA and carries
`--no-fabric-era-guard` (said so beside every number); the tree is AHEAD of
FLASH #14 and no fabric figure may be quoted against it until a re-flash.

---

## §1  THE SURVEY — WHAT THE SECOND DIVERGENCE IS

Wave 4 landed the ghost-read ADDRESS law (`ghost_relax` deleted,
`ghost_off & gpr[R_SP]`).  It closed the ghost address for a subset; **most
ghost seats still fail, and the brief asks what their divergence is NOW.**

Re-derived on the LANDED tree (`fz2_replay --leg ret --no-fabric-era-guard`,
`tb_sys` receipt `b9ef61fd968f3b72…`), ghost-proximity by the RTL's OWN
predicate (`survey_one`/`nearest_package`: an `8F` mod==3 within six `F` pops
of the fork, over EVERY family, not just `E1`):

* **51 ghost-proximate seats** (31 `E1`, 6 `D1`, 3 `D2`, 3 `A3`, 3 `E2`,
  2 `D3`, 1 each `C1`/`C3`/`C4`).
* **4 CLOSED post-wave-4** (`sys_bad == 0`): `fz2e/519016`, `fz2e/520040`,
  `fz2e/527055`, `fz2e/528030`.
* **47 STILL FAILING**, and their FIRST divergence column partitions cleanly:

| class | n | what it is |
|---|---:|---|
| **RAIL** | 40 | the ghost read's **own T1 address** still forks (chip≠core address, no matched read precedes it).  This is M10's KNOWN-OPEN *"which rail / empty solve"* residual — wave-4's `& SP` is **not universal** (`fz2_m10_diagnosis` §5.2/§5.4, wave-4 §7 item 2).  It is the ADDRESS, not a second divergence. |
| **SPLIT** | 4 | the ghost read address **MATCHES**, then the core emits an EXTRA cycle at **`ghost_addr + 1`** — the odd-word **split second-half** — where silicon issues the ghost read as a **single cycle** and moves on.  **THIS is the genuine second divergence.** |
| **QS-ONLY** | 3 | `qs`-pop one clock off with identical addresses (`fz2e/518006`, `fz2e/518050`, `fz2e/522003`) — M10 §3.4 already flagged these as timing, not address. |

**ONE MECHANISM PER GROUP; the groups are NOT unified.**  This package acts on
**SPLIT only** and books RAIL (address, M10/P4′) and QS-ONLY (timing) untouched.

### §1.1  THE SPLIT MECHANISM, FROM THE ROWS (not recall)

The four SPLIT seats, each showing a matched ghost read then a spurious `+1`:

| seat | ghost read T1 (matched) | core's spurious 2nd cycle | chip's real next access | sys_bad |
|---|---|---|---|---:|
| `fz2c/410008` | `d4f33` (odd) row 1193 | `d4f34` = ghost+1 row 1199 | `d52d4` | 4 |
| `fz2e/528010` | `863a7` (odd) row 1378 | `863a8` = ghost+1 row 1384 | `8b92d` | 4 |
| `fz2e/535036` | `f9901` (odd) row 1709 | `f9902` = ghost+1 row 1717 | `fb10a` | 4 |
| `fz2c/409077` | `a5d10` row 817 (real-stack odd) | `a5d11` = ghost+1 row 821 | CODE `de522` | 3023 |

The split parity is `acc_split`'s `ghost_stack_phys[0]` (the REAL stack
address), which is why `409077` splits though its pin address is even.  The two
CLOSED even-address seats (`519016` `bcd52`, `520040` `7bb70`) never split —
`ghost_stack_phys` even — which is the control that says the discarded ghost
read is a **single bus cycle regardless of address parity**: an odd word cannot
be read in one cycle on a 16-bit multiplexed bus, so silicon's single ghost
cycle is a **dummy**, not a split word.

The first divergence surfaces on the `nxta` column (the T4/Ti preview of the
next T1 address) one row before the T1 `addr` — same value, one row early.  The
40 RAIL seats surface identically (address previewed on `nxta`), which is why a
raw column histogram reads "40 nxta"; the discriminator is whether a **matched**
ghost read precedes the fork (`_w5tmp/w5_discriminate.py`).

---

## §2  THE LAW — ONE DELETION

`hdl/rtl/ucore/v30u_eu.sv`, `acc_split` (currently lines 1565-1569):

```verilog
 wire       acc_split = !acc_byte &&
                        (ghost_read_stale_alu
-                        ? ((ghost_uses_ea || ghost_uses_mul_hi)
-                           ? acc_phys_base[0] : ghost_stack_phys[0])
+                        ? 1'b0
                                              : acc_phys[0]);
```

**The discarded 8F ghost read never splits.**  This DELETES a three-case split
sub-expression (`acc_phys_base[0]`, `ghost_stack_phys[0]`, the
`ghost_uses_ea || ghost_uses_mul_hi` mux) and replaces it with `0`.  It is the
brief's preferred shape — a partial close that removes fitted cases, no flop, no
signal, no save-state address, no `sw/` change, no new arm.

`acc_split` drives ONLY `eu_split` (line 2014, `!row_is_inta && acc_split`) and
`eu_pair2` (line 2089); a ghost read has `row_is_read` so `eu_split` becomes 0
and the BIU issues one cycle.  **`acc_phys` (the FIRST-byte address, line 1552)
is NOT touched** — it currently matches silicon on every SPLIT seat, so the
single remaining cycle keeps the address it already had.  `acc_phys2`'s two
ghost arms (lines 1559-1562) become **provably dead** (only consumed as the
second-cycle address, which no longer exists); whether to also delete them is
decided AFTER the re-score proves them inert — a byte-identical score with them
present vs removed is the same INERT test wave-4 used for V3/V4.  The default is
to leave them and BOOK the deletion, so this landing is exactly one line.

**SIMPLICITY note:** no evidence in this corpus shows silicon EVER splitting a
ghost read (the 2 even-address closes and the 4 odd-address/odd-stack failures
all say single-cycle).  `acc_phys`'s own `ghost_stack_phys` first-byte selection
(line 1552, the `eu_ghost_stack_first` odd case) is therefore also suspect, but
it is LEFT STANDING because it changes the first-byte address that currently
matches, and deleting a case on a population that does not exercise it is the
wave-4 error in the other direction.  Booked in §6.

---

## §3  REGISTERED PREDICTIONS (numeric bars BEFORE the build)

* **W5-1 (required):** the three CLEAN SPLIT seats **`fz2c/410008`,
  `fz2e/528010`, `fz2e/535036` CLOSE** (`sys_bad` 4 → 0 each).  Named in advance.
* **W5-2 (expected):** `fz2c/409077` (SPLIT, `sys_bad` 3023) **closes OR improves
  by ≥ 3000 rows** — its split at row 821 cascades a `bs` desync; removing the
  split should collapse it.  Not a required closure (a downstream owner may
  surface); reported as measured.
* **W5-3 (required):** the **4 already-closed** ghost seats (`519016`, `520040`,
  `527055`, `528030`) **STAY closed** (`sys_bad` 0).
* **W5-4 (required):** **0 LOST and 0 EARLIER** over all 116 ledger seeds —
  no seed's `sys_bad` increases and no still-failing seed's `first` row moves
  earlier.  Baseline per-seat `sys_bad` snapshot `_w5tmp/w5_baseline_bad.json`.
* **W5-5 (required):** the **40 RAIL** and **3 QS-ONLY** seats are NON-MOVERS
  (`sys_bad` unchanged) — the fix touches split, not address or qs.
* **W5-6 (scoping):** every seed whose score record changes is 8F-ghost-proximate
  (SPLIT class); 0 non-ghost movers.
* **W5-7 (non-vacuity):** `--perturb 1` on the closed SPLIT seats is DIVERGENT
  (the comparator is not vacuous on them).
* **W5-8 ss:** **NO flop, NO SSA address added** — pure combinational deletion.
  `ss_lint --core ucore` PASS and UNMOVED (`SS_VERSION` **0x8D**, `SS_COUNT`
  **226**, `SS_TAG` **0x8DE2**, 214 flops, 0 UNMAPPED — the base tree's values).
* **W5-9 gates:** `gen_ucore_qsf --check` PASS · `r7_lint` PASS, **no new
  exception**, tainted set unchanged (the edit only REMOVES terms from
  `acc_split`, shrinking its cone) · `test_artifact` 45/45 ·
  `check_core 8F.0` **500/500** · `check_core INT.F3AA` **200/200** ·
  `check_core all` **169,000/169,000** · four HLT sweeps **97·93·45·44 = 279/283** ·
  four `evt` cells **200·1200·200·1200** + biased **1200/1200** ·
  `ulockstep --golden all` **17,350/17,350** · `check_fuzz_bank` PASS **621**.
* **W5-10 G6 (decides it):** CONTROL build, **TWO DRAWS**, `db`/`incremental_db`
  deleted first.  Predicted **inside the branch's control band ~38.4–40.5**
  (removing a 16-bit OR-mux from `acc_split` is timing-neutral-to-positive).
  **38.0 MHz is the STOP** — any draw below 38.0 is STOP-and-report, RTL not
  landed.  Fmax ≥ 32, worst setup > 0, TNS 0.000 setup AND hold both draws.

**Falsifiers.**  W5-1 is refuted if any of the three clean seats fails to reach
`sys_bad == 0`.  The single-cycle reading is refuted if any ghost seat's CHIP
stream shows a matched `addr, addr+1` consecutive pair (a real silicon split) —
none does in this corpus.  W5-4 is the hard gate: a single lost seat reverts the
landing.

## §4  WHAT IS NOT CLAIMED

* The **40 RAIL** seats (the ghost address itself — *which rail* and the
  non-universal `& SP`) are M10/P4′ territory and are NOT touched.
* The **3 QS-ONLY** seats (qs-pop timing) are NOT touched.
* No claim that silicon's single ghost cycle is universally `acc_phys_base`;
  only that the SECOND cycle is spurious.  `acc_phys` line 1552 is left standing.

## §5  RE-RUN

```bash
git rev-parse HEAD                       # the wave-5 landing
L=sw/testdata/fz2/fz2_failure_ledger_f16_2026-08-10.json
python3 sw/fz2_tbsys.py build --leg ret
python3 sw/fz2_replay.py --ledger $L --all-failures --pass-sample 0 \
        --leg ret --jobs 8 --no-fabric-era-guard --out /tmp/landed.json
# the SPLIT/RAIL/QS partition + 0-lost proof: _w5tmp/w5_discriminate.py
python3 sw/gen_ucore_qsf.py --check
python3 sw/r7_lint.py
python3 sw/ss_lint.py --core ucore
python3 sw/test_artifact.py
python3 sw/check_core.py --build --core ucore
python3 sw/check_core.py --core ucore --opcodes 8F.0     --cases 0   # 500/500
python3 sw/check_core.py --core ucore --opcodes INT.F3AA --cases 0   # 200/200
python3 sw/check_core.py --core ucore --opcodes all      --cases 0   # 169,000
for w in 0 1; do python3 sw/check_core.py --core ucore \
    --suite-dir tests/v30/s10-hltsweep-w$w --waits $w; done           # 97, 93
for w in 2 3; do python3 sw/check_core.py --core ucore \
    --suite-dir tests/v30/s13-hltsweep-w$w --waits $w; done           # 45, 44
python3 sw/ulockstep.py --golden all --cases 50                       # 17,350
python3 sw/check_fuzz_bank.py                                         # PASS 621
python3 sw/quartus_gate.py                                            # G6, TWICE
```

⚠ `check_core --suite-dir` takes `--waits` and it DEFAULTS TO 0.  Captures are
gitignored and live only in the shared checkout; a fresh worktree must link them.

## §6  BOOKED, NOT DONE

1. **`acc_phys2`'s two ghost arms** (lines 1559-1562) — dead after this landing;
   delete once a re-score proves inert (the wave-4 V3/V4 precedent).
2. **`acc_phys`'s `ghost_stack_phys` first-byte selection** (line 1552,
   `eu_ghost_stack_first` odd case) — suspect under the single-cycle reading but
   left standing because it moves a currently-matching address.
3. **The 40 RAIL seats** — the ghost address's *which rail* / non-universal
   `& SP`, M10/P4′'s to close.
4. **The 3 QS-ONLY seats** — qs-pop timing.
