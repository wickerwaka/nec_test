# SURVEY FIX #2 — `B1` RESULTS, reported against
# `b1_halt_addr_prereg_2026-08-09.md` (commit `48446a449d`), not restating it

Every bar below is quoted in the form it was registered in. **One registered
bar MISSED on its first measurement and is reported as a MISS with its
repair**; nothing is re-registered after the fact.

---

## 1. THE HEADLINE

**F58 — the HALT pseudo-cycle publishes the AD output latch as it stands, and
announces nothing of its own.** One register pair in `v30u_biu.sv`, in the idiom
`last_ube` already established, keyed on the two output enables the pads already
have. No opcode named, no table, no case split: the read/write asymmetry that
makes the class visible is not encoded anywhere — it falls out of which enable
is asserted when.

**The brief's identification was refuted before any RTL was touched** (prereg
§0): F55 landed 2026-08-05 as `39ac08ccd4` and has been in fabric since
FLASH #10. This is a different, adjacent mechanism — F55 governs who holds the
pads for the **body** of the pseudo-cycle (nobody), F58 governs the **value
published in its own address phase**, which silicon and the core both drive.
**F55's booking is therefore NOT discharged by this landing; it was already
discharged four days ago, and the `CLAUDE.md` line that still calls it "BOOKED
NOT LANDED" is a sitting-19 snapshot superseded by sitting 20 in the same file.**

---

## 2. MEASURED BARS (registered as found)

| # | bar | registered | measured | verdict |
|---|---|---|---|---|
| M1 | chip-leg law, every HALT in all 725 retained captures | 1,189 / 1,189 | **1,189 / 1,189**, 0 exceptions | **MET** |
| M2 | corpus rescore, HALT sites in lockstep | MISS 21 → 0 | **21 → 0** | **MET** |
| M3 | rows ENTERING the differing set | 0 | **0** over 725 seeds | **MET** |
| M4 | rows LEAVING it | 96 | **96** | **MET** |
| M5 | `ss_lint` | PASS, 0x8D / 226 / 0x8DE2, 214 flops | **PASS**, `SS_VERSION` **0x8D**, `SS_COUNT` **226**, `SS_TAG` **0x8DE2**, 103 BIU × 2 + 122 EU × 2 + tag, **214** architectural flops, **0 UNMAPPED** | **MET** |
| M6 | `r7_lint --core ucore` | PASS | **PASS**, 0 undeclared carriers, 0 undeclared unresolved, 0 `stop` sites | **MET** |

## 3. PREDICTED BARS

| # | bar | registered | measured | verdict |
|---|---|---|---|---|
| P1 | `check_core --core ucore --opcodes all --cases 0` | 169,000 / 169,000 UNCHANGED | **168,858 / 169,000 on the first RTL — MISSED**; **169,000 / 169,000** after the repair of §4 | **MISSED, then MET** |
| P2 | four HLT sweeps, `tb_v30_core --core ucore` | 97/97 · 93/95 · 45/46 · 44/45 = 279/283, same four survivors | **97/97 · 93/95 · 45/46 · 44/45 = 279/283**, survivors **`HLT.INT` idx 8 and 9 (w1) · idx 12 (w2) · idx 15 (w3)** — the registered cells, by name | **MET** |
| P3 | `check_boot --core ucore` | 220 and 400 MATCH | **MATCH over 220 rows** and **MATCH over 400 rows** | **MET** |
| P4 | `sw/test_artifact.py` | 45 / 45 | **45 / 45** | **MET** |
| P5 | `sw/gen_ucore_qsf.py --check` | PASS | **PASS** (also as G6's E1 leg) | **MET** |
| P6 | **G6**, two draws | PASS both, Fmax ≥ 32, TNS 0.000 setup AND hold | see §5 | see §5 |
| P7 | `ulockstep --golden all --cases 50` | non-blocking; may move AWAY from the model | **17,350 / 17,350 LOCKSTEP, unchanged** | see §3.1 |

### 3.1 P7 — why the defunct model did NOT move, and what that does and does not say

The user ruling of this sitting is that the C++ model is defunct and `ulockstep`
does not gate. It was run for the record and did not move. **That is not
evidence that the model shares F58**: `ulockstep`'s population is the golden
suites, and every HALT in them follows a CODE fetch, which is precisely the
degenerate case in which the old rule and F58 produce the same value (prereg
§1.2, 1,164 of 1,189 sites). The model is untested on this mechanism by this
gate, and `sim/` was not touched.

---

## 4. THE REGISTERED MISS, AND ITS REPAIR

**P1 read 168,858 / 169,000 on the first RTL.** The 142 failures were
`HLT.INT` 150/200, `HLT.NMI` 155/200, `HLT.RES` 153/200 — **arch 200/200 on all
three** — and every one of the 142 diverged first at **row 1** on `bus`.

**Cause.** A golden whose capture window OPENS on a HALT has no in-window bus
cycle to have driven the pads, so the new latch published its reset value. The
register it replaces does not have that problem because it has a reset-path
reconstruction: S9a's backdoor pre-window fetch walk fills `last_fetch_addr_rst`
for exactly this reason, and the new lanes had no equivalent.

**Repair, and why it is not a special case.** The two lanes are seeded at `srst`
from that same walk — `last_ad_lo <= last_fetch_addr_rst`, `last_ad_hi <=
data_ps(2'd2)`. The walk models FETCHES, which is the degenerate case, so the
seed reproduces the old behaviour exactly at the window's first clock and only
the in-window evolution is new. The reset value of a pad latch is "what the part
carried into the window", which is what the walk exists to reconstruct.

**This is what the gate is for.** The degeneracy argument of prereg §1.2 was
right about the mechanism and silent about the window boundary; `check_core`
found the boundary in one run. The corpus rescore of §2 was re-run on the
repaired RTL and is unchanged (M2/M3/M4 above are the repaired tree's numbers).

---

## 5. G6

Two draws on the final RTL, `db/` deleted before each — **one green build is not
closure**, and this tree has historically drawn between 19.42 and 47.85 MHz.

> **RIG NOTE, recorded because it nearly corrupted a receipt.** An earlier draw
> was started on RTL that the P1 repair then superseded. It was killed — but
> `pkill -f` did not reap it, and a second `quartus_sh` was started while the
> first was still fitting **into the same output directory**. Both were killed
> by PID, `hdl/db` and `hdl/incremental_db` were removed, and both draws were
> restarted from clean. **No receipt from the overlapping period is quoted.**

| draw | result | Fmax | worst setup | TNS setup / hold | ALMs | receipt |
|---|---|---|---|---|---|---|
| 1 | **PASS** | **40.11 MHz** | **+6.319 ns** | **0.000 / 0.000**, every domain | 12,210 / 41,910 (29 %) | `b2c7466038147a9b…` |
| 2 | **PASS** | **40.11 MHz** | **+6.319 ns** | **0.000 / 0.000**, every domain | 12,210 / 41,910 (29 %) | `bf9e0ad84703b07c…` |

Both draws: 0 errors, every stage Successful, **0 latches, 0 `lpm_divide`**,
`E1 gen_ucore_qsf --check` PASS, configuration **CONTROL/DEFAULT (no
`X1_AD_RETENTION`)**, input manifest **88 files `b5a6bb22b4ec9665…` — identical
across both draws**. **P6 MET.**

**READ THE BAND, NOT THE NUMBER.** `CLAUDE.md`'s 47.85 MHz is the pre-branch
tree (SM3 sitting 27) and is not this branch's. The `quartus_bitstream.jsonl`
history for `fuzz-v2-on-relanding` reads **39.37 · 39.57 · 39.83 · 40.96** on
its last four PASSing draws, so **40.11 sits inside the branch's own band and is
not a regression**; it is above three of the four. The two draws landed on the
*same* figure, which is a stability datapoint and not a closure claim —
Analysis & Synthesis is not reproducible run to run on this tool
(`ucore_provenance.md` §74.4a), and **one green build is not closure.**

---

## 6. WHAT IS NOT CLAIMED

* **No fabric figure.** No board was contacted, nothing was flashed. The
  prediction that these sites close in fabric is registered for a later flashed
  sitting and is not evidence now. Under the standing rule, a fabric figure
  taken on any earlier flash may not be quoted against this tree.
* **The banked corpus headline is not moved.** `SEED MATCH 3,639 / 3,837` and
  `ROW MATCH 11,159,527 / 11,322,230` stand exactly as `§38.4` registered them.
  The offline instrument's denominator is **725 of 3,837** — the
  retained-capture population — and it re-runs only the core leg. Only a board
  re-capture can move the banked figures.
* **The failure ledger is not edited.** `fz2_failure_ledger_2026-08-09.json`
  (sha256 `c86f49b896c39673…`) is byte-identical. Which of the 24 `B1` seeds
  leave it is a question for the re-capture, not for this sitting.
* **`fz2c/407064` is predicted NOT to become a passing seed.** It is the one
  `B1` member of `§38.9`'s 40-seed missed-trap population; its HALT cell closes
  and it re-diverges downstream on the vector-1 trap that fix #3 owns.
* Nothing in `sim/` was touched; `git diff -- sim` is empty.
* The `A1` / QS announcement path was not touched.
