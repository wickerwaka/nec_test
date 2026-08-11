# fz2 WAVE-5 — THE 8F GHOST SEATS' **SECOND DIVERGENCE** — RESULTS, AS REGISTERED

Pre-registration: `docs/notes/fz2_w5_ghost2nd_prereg_2026-08-10.md`, committed
`15284289e9` **before the first line of RTL**.  Read that first; this document
answers it clause by clause and does not restate it.

Branch `fuzz-v2-on-relanding`, base **`8280031c8d`** (the worktree provisioned
at `master`/`29dcc5b05f` and was reset; `git rev-parse HEAD` verified
`8280031c8d`).  Offline throughout; **no board, no flash, model defunct.**
Every `fz2_replay` figure is OFFLINE and CROSS-ERA, `--no-fabric-era-guard`,
`tb_sys` — said so beside every number.

---

## §0  HEADLINE — A DIAGNOSIS WAVE.  NO RTL LANDS.

**The registered law (`acc_split`'s ghost branch → `1'b0`) was REFUTED on its
own three named seats and is NOT landed.  The RTL is byte-identical to base
(`git diff` empty), and a rebuilt-and-rescored control reproduces the baseline
EXACTLY — 116 seeds, 0 differing, Σ diverging rows `118,662 = 118,662`.**

The value this wave delivers is the **correct partition and mechanism of the
second divergence**, which overturns the reading its own prereg carried in from
the row-column histogram:

| | |
|---|---|
| **W5-1 REFUTED** | the three clean seats did **NOT** close — they REGRESSED (`410008` 4→1249, `528010` 4→2067, `535036` 4→243) |
| **W5-4 VIOLATED** | **9 seeds worse, 0 closed** under the registered fix — the hard 0-lost gate fails, so the landing reverts by its own rule |
| **the mechanism** | the "split second-half" is **NOT a spurious extra cycle**.  It is the core's SOURCE for a real PAIRED bus cycle that silicon fills with a fresh successor read; the wave-4 `acc_split` machinery drives it at `ghost+1` (≈4 rows off, `bad=4`), and DELETING it deletes the cycle and desyncs the whole tail (`bad`→hundreds) |
| **the disposition** | the four "SPLIT" seats are **not a separable second mechanism** — they are the ADDRESS/rail problem (M10's) on the ghost's paired second cycle.  Booked to M10/P4′, not landed. |

**G6 was NOT run: nothing landed, so no Quartus receipt is owed** (the prereg's
W5-10 gate was conditional on a landing).

---

## §1  THE SURVEY — THE PARTITION IS THE DELIVERABLE

Ghost-proximity by the RTL's own predicate (`8F` mod==3 within six `F` pops,
`fz2_m10.survey_one`/`nearest_package`) over EVERY family on the LANDED-base
`tb_sys` column (receipt `b9ef61fd968f3b72…`):

* **51 ghost-proximate seats** (31 `E1`, 6 `D1`, 3 `D2`, 3 `A3`, 3 `E2`,
  2 `D3`, 1 each `C1`/`C3`/`C4`) — the wave-4 doc's `51 / 39` re-confirmed.
* **4 CLOSED post-wave-4**: `fz2e/519016`, `fz2e/520040`, `fz2e/527055`,
  `fz2e/528030`.
* **47 STILL FAILING**, partitioned by their FIRST divergence:

| class | n | seats / note |
|---|---:|---|
| **RAIL** | 40 | the ghost read's OWN T1 address still forks — M10's *which rail / empty solve* residual; wave-4's `& SP` is not universal.  The ADDRESS, not a second divergence. |
| **"SPLIT"** | 4 | `fz2c/409077`, `fz2c/410008`, `fz2e/528010`, `fz2e/535036` — ghost read matches, then the ghost's PAIRED second cycle forks (§2). |
| **QS-ONLY** | 3 | `fz2e/518006`, `fz2e/518050`, `fz2e/522003` — qs-pop one clock off, identical addresses (M10 §3.4 timing). |

The raw column histogram reads "40 nxta / 4 qs / 3 bs", but `nxta` is only the
T4/Ti preview of the next T1 `addr` one row early — the SAME value, one row
sooner — so a `nxta` first-divergence is an ADDRESS fork previewed.  The
discriminator that separates SPLIT from RAIL is whether a **matched** ghost read
precedes the fork (`_w5tmp/w5_discriminate.py`), not the column name.

## §2  THE MECHANISM, FROM THE ROWS — AND WHY THE PREREG WAS WRONG

The prereg read the four SPLIT seats as *"the core emits a spurious extra cycle
at `ghost+1` where silicon issues one cycle"* and predicted deleting the split
would close them.  The rows on `fz2c/410008` say otherwise:

```
        CHIP                         CORE (baseline, with split)
1193 T1 MEMR d4f33   ghost read      1193 T1 MEMR d4f33     <- matches
1199 T1 MEMR d52d4   REAL successor  1199 T1 MEMR d4f34     <- ghost+1, WRONG addr
1203 T1 MEMR 28d30                   1203 T1 MEMR 28d30     <- re-converge
```

**Both streams have THREE cycles here and they are aligned; only the middle
cycle's ADDRESS differs** (`d52d4` vs `d4f34`), which is `bad = 4` (nxta + addr +
2×data of that one cycle).  Silicon's middle cycle is a genuine successor read
at `d52d4`; the core sources ITS middle cycle from the `acc_split` /
`acc_phys2 = ghost+1` machinery — a fitted approximation that lands within four
rows.

With the split forced off (`acc_split` ghost → 0) the core LOSES that middle
cycle entirely and jumps `d4f33 → 28d30`, one bus cycle short of silicon, and
the whole tail shifts (`bad` 4 → 1249):

```
        CHIP                         CORE (landed, split removed)
1193 T1 MEMR d4f33                   1193 T1 MEMR d4f33
1199 T1 MEMR d52d4                   1199 T1 MEMR 28d30     <- middle cycle GONE
1203 T1 MEMR 28d30                   1203 T1 IOW  03740     <- desynced
```

So the wave-4 `acc_split`/`acc_phys2` ghost machinery is **not a splittable word
— it is a cycle-count PLACEHOLDER that holds the paired successor slot at a
wrong-but-close address.**  The two wave-4 closes (`bcd52`, `7bb70`, EVEN) never
split and never needed the placeholder; the four failures need the placeholder's
ADDRESS to be the real successor, which is M10's *which rail* question moved to
the paired cycle.  **It is the address domain, and it is not a separable,
removable, decode-rail mechanism — it is the wrong law to have registered.**

## §3  PER-PREDICTION DISPOSITION (reported as registered)

| id | registered | measured |
|---|---|---|
| **W5-1** | 3 clean SPLIT seats close | **REFUTED** — they REGRESS (4→1249 / 4→2067 / 4→243) |
| **W5-2** | `409077` closes or −≥3000 rows | held-moot — it improved 3023→1429 under a REVERTED change; not landed |
| **W5-3** | 4 closed seats stay closed | held (they never moved) |
| **W5-4** | 0 lost / 0 earlier | **VIOLATED** — 9 worse, 0 closed; the landing reverts by its own gate |
| **W5-5** | RAIL/QS non-movers | **REFUTED** — 10 RAIL improved, 5 RAIL worsened (cascade reshuffle, 0 closures); the change is not confined to the split |
| **W5-6** | movers all ghost | **MET** — 19 movers, 19/19 ghost-proximate, 0 non-ghost |
| **W5-7** | non-vacuity | n/a (nothing closed) |
| **W5-8** | no flop / ss unmoved | n/a (no landing); `ss_lint` base **PASS**, `SS_VERSION` 0x8D / 226 / 0x8DE2 / 214 flops |
| **W5-9** | standing gates | base tree UNCHANGED; `r7_lint` **PASS** (3 tainted, 51 stop, 0 viol), `ss_lint` **PASS** re-run in §0's control |
| **W5-10** | G6 ≥ 38.0 | **NOT RUN** — nothing landed |

The net Σ-rows under the reverted change was −864 (10 RAIL improved, 9 worse),
but **0 seeds reached `bad = 0`** and the improvements are cascade-length
reshuffles on seats that fork on address regardless — not closures.  A change
that closes nothing and regresses its own directed seats is not landable, and
choosing to keep it for a net-rows number would be scoring a comparator after
seeing the result.

## §4  THE CONTROL — THE REVERT IS EXACT

`hdl/rtl/ucore/v30u_eu.sv` restored (`git diff` empty).  `tb_sys` rebuilt from
the reverted source and the full 116-seed column re-scored: **0 seeds differ
from baseline, Σ diverging rows `118,662 = 118,662`.**  The tree a reviewer
inherits is `8280031c8d` unmodified plus two committed documents.

## §5  BOOKED, NOT DONE — the remainder, named

1. **The four "SPLIT" seats are M10/P4′'s**, re-scoped: the ghost read's PAIRED
   second cycle drives `ghost+1` where silicon drives a real successor read
   (`fz2c/410008`: `d52d4`).  Its address is the *which rail* question on the
   second cycle; naming that rail on `410008`/`528010`/`535036` and validating
   on a disjoint seat is the P4′ job.  Do NOT re-derive it by scanning these
   three — that is fitting on the selection population.
2. **The 40 RAIL seats** — the ghost address's *which rail* / non-universal
   `& SP`, M10 §5.2/§5.4's open residual.
3. **The 3 QS-ONLY seats** (`518006`, `518050`, `522003`) — qs-pop one clock
   off, identical addresses.  These are the closest thing in this population to
   the brief's "clock-late decode rail" hypothesis and are the one untouched
   lead worth a dedicated look; they are NOT address seats.
4. **`acc_phys2`'s `ghost+1` is a fitted placeholder, not a split** — the wave-4
   comment *"an odd stack POP has already launched its first byte"* describes a
   word split that this wave's rows do not support; the second cycle is a real
   successor access whose address the machinery approximates.  A future landing
   that gives it the correct successor address (not `+1`) closes the four seats;
   removing it does not.

## §6  RE-RUN

```bash
git rev-parse HEAD                       # base 8280031c8d + 2 docs, RTL unchanged
L=sw/testdata/fz2/fz2_failure_ledger_f16_2026-08-10.json
# link gitignored captures from the shared checkout first
python3 sw/fz2_tbsys.py build --leg ret
python3 sw/fz2_replay.py --ledger $L --all-failures --pass-sample 0 \
        --leg ret --jobs 8 --no-fabric-era-guard --out /tmp/base.json
# the partition + the SPLIT/RAIL/QS discriminator + the 0-diff control:
#   _w5tmp/w5_analyze.py  _w5tmp/w5_discriminate.py  _w5tmp/compare.py
# to reproduce the refutation, apply the prereg §2 one-liner, rebuild, rescore;
# 410008/528010/535036 go 4 -> {1249,2067,243}, 0 close.
python3 sw/r7_lint.py            # PASS
python3 sw/ss_lint.py --core ucore   # PASS 226 / 214 flops
```

⚠ `check_core --suite-dir` takes `--waits` (defaults 0).  Captures are
gitignored and live only in the shared checkout.
