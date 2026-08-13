# L1 — THE REGISTERED DECODE.  RESULTS, SCORED AS REGISTERED.

Pre-registration `107c0e3877` (`adcone_l1_prereg_2026-08-13.md`), committed
**before the edit**.  Anatomy `05bd462643` / `83c00e753f`
(`adcone_anatomy_2026-08-13.md`), committed **before the design**.  Edit
`9bf70f2eec`.  Branch `master`, isolated worktree, HEAD verified at
`faabb15128` on entry.  **OFFLINE ONLY.  NO BOARD, NO FLASH.  No Codex
consulted, no nested task spawned.**

---

## §0 HEADLINE

*(filled from the G6 sweeps — see §2.)*

---

## §1 THE PIN-IDENTITY LADDER — EVERY LEG AS REGISTERED

`hdl/rtl/ucore/v30u_eu.sv` is the only RTL file this wave edits, and
`sw/ss_flop_whitelist_ucore.txt` the only other functional file.  The `.sdc` is
**untouched**.

| leg | registered | measured | |
|---|---|---|---|
| `r7_lint` | PASS, 0 violations, 20 nets / 1 carrier / 3 tainted / 51 `stop` | **PASS**, identical counts | ✓ |
| `ss_lint --core ucore` | `SS_COUNT` **232** unchanged, flops **220 → 221**, whitelist **2 → 3**, 0 UNMAPPED | **232**; BIU 91 mapped, EU **130** flops → 127 mapped + **3** whitelisted; **221** flops, **0 UNMAPPED** | ✓ **P-5 MET** |
| `check_core --opcodes all --cases 0` | 169,000 | **169,000/169,000** | ✓ |
| `check_core --opcodes 8F.0 --cases 0` | 500 | **500/500** (cycles 500, arch 500) | ✓ |
| HLT sweeps ⚠ `--waits 0/1/2/3` | 97 · 93 · 45 · 44 = 279/283 | **97 · 93 · 45 · 44 = 279/283** | ✓ |
| `ulockstep --golden all --cases 50` | 17,350 | **17,350/17,350 ALL LOCKSTEP** | ✓ |
| `ghost_launch_law score` | 200/200 | **200/200 = 100.0 %** | ✓ |
| `check_boot --core ucore` | 220 and 400 | **MATCH over 220** and **over 400** rows | ✓ |
| `check_ab_sim --core ucore` | MATCH 187 rows | **MATCH over 187 rows** | ✓ |
| `v0.1-w1` / `-w3` | 1,200 each | **1,200/1,200** each | ✓ |
| `v0.1-w1 --opcodes EB` | 200 | **200/200** | ✓ |
| the four `evt` cells (w0/w1/w2/w3) | 200 / 1,200 / 200 / 1,200 | **200 / 1,200 / 200 / 1,200** | ✓ |
| `v0.1-w1evt-biased` | 1,200 | **1,200/1,200** | ✓ |
| **S16 display walk** `sm3_s16_score --core ucore` | 1,320/1,371 | **1,320/1,371**, signature census `busstat_other` 24 · `ARCH` 27 | ✓ |
| `fz2_immaterial falsify` | G1-G8 PASS | **G1-G8 PASS**, 22 members / 84 non-members of 106 | ✓ |
| `test_artifact` | 45/45 | **45/45**, non-vacuous | ✓ |

### 1.1 THE TWO LEGS THAT WOULD HAVE CAUGHT A MOVED PIN — **BOTH BYTE-IDENTICAL**

`check_core` and the golden suites score against *goldens*, so they answer *"is
the core still right"*.  Neither answers *"did anything at all change"*.  These
two do, and they are the registered **P-3**:

**(a) `chain_lfsr_gate` — 4 seeds × 400,000 fabric clocks of ARBITRARY BYTES**,
with LFSR memory, LFSR `READY` and LFSR `INT`, i.e. a stimulus distribution with
nothing in common with the golden suite.  It emits a per-seed running signature.

| seed | before | after |
|---|---|---|
| 1 | `2138eabbcea8796c` | **`2138eabbcea8796c`** |
| 2 | `fad6633fc67db084` | **`fad6633fc67db084`** |
| 3 | `f90444c46a589273` | **`f90444c46a589273`** |
| 4 | `5404f98f2d8bc343` | **`5404f98f2d8bc343`** |

`CHAIN_DEPTH_MAX 6` / `entry_st 25` / `coincide 0` / `ce_clocks` and all eight
gap counts identical too; **the only diff in the whole transcript is the
Verilator binary receipt, which must change.**

**(b) `fz2_replay --all-failures --pass-sample 200 --leg ret` — the FULL
`tb_sys` replay of the fuzz-v2 corpus**, 306 seeds, scored against the banked
**socket** rows with the corpus's own column policy and window.

```
before  tb_sys receipt c7b10164b3fb1892…
after   tb_sys receipt f5a82f26f80eb297…
seeds: 306 vs 306
replayed rows compared: 1,243,278
tables block identical: True
IDENTICAL: 306 seeds, 1,243,278 replayed rows, every `sys` field and every
           banked reference field unmoved
```

`sw/adcone_replay_diff.py` compares `n`, `nrows`, `bad`, `flick`, `first`,
`fired`, `vecused` per seed plus the banked `fabric_bad` / `fabric_first` /
`win` / `family`, and the whole `tables` block.  **A pin that moved on any clock
of any of those 306 programs moves at least one of those fields.**

⚠ **BOTH `fz2_replay` LEGS RAN WITH `--no-fabric-era-guard`, AND THAT IS
STATED RATHER THAN WORKED AROUND.**  The guard already REFUSED on the
**pre-edit** tree — `hdl/rtl/ucore/v30u_eu.sv`, `hdl/nec_test.sdc` and
`hdl/nec_test.qsf` have all moved since FLASH #20's bitstream
(`26d6e79166183a21…`) — so this tree was a cross-era read *before this wave
touched it*.  **What these two legs measure is BEFORE vs AFTER on ONE tree.
They say nothing about fabric, and no fabric claim is made from them.**

### 1.2 ONE REGISTERED FIGURE READ DIFFERENTLY, AND IT IS THE ENVIRONMENT

`test_quartus_gate` is registered at **200/200**; it printed **199/199 with one
`[skip]`** — *"no live `fit.rpt` on disk to check the parser against"*.  The
sweep's own clean build had just deleted `hdl/output_files_ucore/`.  It is a
**conditional check, not a lost one**; re-run with a build present it reads
200/200 (§2.4).  Reported here rather than quietly rounded up.

---

## §2 THE MEASUREMENT — G6 `--seeds 5`, BOTH CONFIGURATIONS

*(filled from the sweeps.)*

---

## §3 THE CENSUS — WHAT BINDS NOW

*(filled from the post-sweep probes.)*

---

## §4 THE VERDICT AND THE NEXT LEVER

*(filled.)*
