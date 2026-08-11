# fz2 WAVE-6 — THE 8F GHOST-READ **ADDRESS RAIL** LAW — RESULTS: BOOKED, NOT LANDED

Pre-registration: `docs/notes/fz2_w6_ghostrail_prereg_2026-08-10.md`, committed
`3c4a43111a` **before the rail solve** (the derivation).  Read that first; this
document answers it clause by clause.

Branch `fuzz-v2-on-relanding`, base **`3999f0d669`** (`git rev-parse HEAD`
verified; the worktree provisioned at `master`/`29dcc5b05f` and was reset).
Offline throughout; **no board, no flash, no RTL change, no Quartus**.

⚠ **NO POST-RTL FIGURES EXIST** — nothing was landed, so nothing is cross-era.
The two `fz2_m10.py solve` columns are read on the receipted `--core ucore`
`tb_v30_core` binary at `3999f0d669` (receipt `id e6f630b2a955f731…`, RTL input
`v30u_eu.sv 6cd4defe…`), architectural register VALUES only, which no landing
touched.

---

## §0  HEADLINE — W6-D REFUTED: THERE IS NO SINGLE GHOST RAIL

**The pre-registered candidate `ghost_off = m_ea` is REFUTED on DERIVE, and so
is every other single rail.**  The 8F ghost read does **not** reuse one fixed
retained register.  Which register reproduces silicon's ghost address is a
function of **how many `F` pops separate the retired `8F` from the forking
bus cycle** — the pipeline distance the M10 survey already carried as
`near_dist`:

| retired-`8F` distance | fitting rail (fork clock, `d=0`) | seats |
|---|---|---|
| **`near_dist == 0`** (the `8F` is STILL the dispatched instruction) | **`IND`** (the BIU's live index register) | `408021` `524030` (DERIVE) · `527037` `534060` (HOLDOUT) — **4 / 4** |
| **`near_dist == 1`** (a pop has retired since; `IND` reloaded) | **`M_EA`** (the retained ModR/M EA) | `518022` (DERIVE) · `530034` `519072` (M10 prior-art) |
| `near_dist == 1`, ALU-residue case | `EA_RESIDUE`/`TMPA` — **already closed by wave-4's unconditional AND** | `410008` `519016` `520040` |
| any | **EMPTY** — no term in the 3,208-expression space fits the chip (M10's reading-(i) upstream divergence) | `524055` `528010` `518033` `518067` |

The intersection of the chip-fit expression sets across the three solvable
DERIVE seats — over all 21 named terms **and** their 190 bitwise pairs — is
**EMPTY** (`sw/fz2_w6_railcheck.py`; §2).  `IND` never fits the `M_EA` seat at
**any** of its 14 freezes; `M_EA` never fits either `IND` seat at any freeze.
These are genuinely different physical registers, and the discriminator is
pipeline distance, not opcode.

**Per the pre-registration's mechanical rule (W6-D / §2.2 / §3.1) and the
brief's own instruction — "if DERIVE itself needs 2+ rails, the mechanism is not
understood: book it, land nothing; a 2-case rail rule to close 39 seats is a
fitted table wearing a law's clothes" — NO RTL WAS LANDED.**  The tree is
byte-identical to `3999f0d669` in `hdl/` (`git diff 3999f0d669 HEAD -- hdl/` is
empty).  **This is the pre-registered STOP outcome, reported as the result.**

**It is also the SIMPLICITY principle vindicated from outside a fit** (§3): the
one honest reading of the table is a **single mechanism** — *the ghost read
reuses the datapath's last-latched memory-address register* — whose OBSERVED
register identity changes with distance because the latch it reads is
overwritten one instruction later.  That is a **timing/retention** law, not a
`ghost_off = <register>` mux, and modelling it correctly needs a **retained
flop** (an 8F-issue address latch) — which W6-6 forbids this package from adding
without coordination.  So the correct fix is out of this wave's charter by
construction, and a static mux to approximate it would be the very
misunderstanding the principle names.

---

## §1  THE POPULATION AND THE FROZEN SPLIT (as registered)

39 address seats (`near_package == "P4"` & `t1_addr_differs`, F16 ledger),
split by `sha256(seed_id)[0] < 8` — **16 DERIVE / 23 HOLDOUT**, frozen in
`docs/notes/fz2_w6_split.json` and committed **before** the solve.  The split is
a hash of the seed id and has **no dependence on any address**.

Of the 39, most carry a **stimulus pin event** (NMI/INT) that `tb_v30_core`'s
single scheduler cannot honour (spent on the terminator), so they are **NOREPRO**
— M10's documented gate, not a wave-6 defect.  Solvable address forks: **5 of 16
DERIVE, 4 of 23 HOLDOUT.**  The NOREPRO seats are recoverable only on `tb_sys`
and were not solved here (M10 §8); M10's own results are cited for the two
NOREPRO rail seats it had solved on F15 (`530034`, `519072`).

---

## §2  THE DERIVATION — DERIVE ONLY, AND IT NAMES NO SINGLE RAIL

`python3 sw/fz2_m10.py solve --seeds <DERIVE>` → `sw/testdata/fz2/fz2_w6_solve_derive.json`.
Classified by `sw/fz2_w6_railcheck.py` at the fork clock `d=0` (M10's calibrated
freeze, where `SSA_B_CUR_ADDR == core_addr`):

```
fz2c/408021  (8f df, @0)  chip=13ef0 core=06b70  IND    {IND IND&SP PEND_OFF&… TMPB&…}
fz2e/524030  (8f cb, @0)  chip=33f00 core=2df00  IND    {IND IND&SP TMPB&…}
fz2e/518022  (f9,    @1)  chip=69ae0 core=73ae0  M_EA   {M_EA M_EA&SP R_EA&… WB_EA&…}
fz2e/524055  (fa,    @1)  chip=3a400 core=3a3c0  EMPTY  {}
fz2e/528010  (…,    @2)   chip=8b92d core=863a8  EMPTY  {}
```

**Intersection of the chip-fit sets across the three solvable seats
(408021 ∩ 524030 ∩ 518022), over terms AND bitwise pairs, window `d∈[-4,+1]`:
EMPTY.**  `408021 ∩ 524030 = {IND, …}` (the two direct-`8F` seats agree on
`IND`); `518022` shares **nothing** with either.  The result is **freeze-stable**:
`IND` fits `408021`/`524030` and `M_EA` fits `518022` at every freeze in which
their register is defined, and neither ever fits the other seat.

**No single rail — `m_ea`, `wb_ea`, `ind`, or any other named term or bitwise
pair — reproduces the chip on every solvable DERIVE address fork.**  W6-D is
refuted.

---

## §3  THE MECHANISM THIS EXPOSES (the SIMPLICITY reading)

`IND` (`v30u_eu.sv`, `ind_now`) is the BIU's **live** memory-address register;
`M_EA` (`m_ea`) is the **retained** ModR/M effective address.  For a `near_dist == 0`
ghost the `8F` is still the dispatched instruction and the address it reads is
the one currently in `IND`.  By `near_dist == 1` a pop has retired and reloaded
`IND`, but the `8F`-era address still survives in `M_EA`.  Read at the right
pipeline stage they are **the same value** — *the address the datapath held when
the ghost read was composed* — living in two different registers depending on
how long the bus cycle took to reach the pins.

So the ghost read is one simple system: **it reuses the last-latched
memory-address register.**  The current RTL's fitted selector —
`ghost_uses_ea = (ea_residue != tmpa)`, the `8E` special case, the low-bit mask
— is a **static approximation of a moving latch**, which is exactly why it is a
multi-case rule and exactly why it is wrong on ~39 seats.  Replacing it with a
different static rail (`m_ea`) would move the error, not remove it: it would
help the `near_dist == 1` seats and break the `near_dist == 0` seats, which want
`IND`.

**The correct model captures the `8F`'s address at issue and holds it for the
ghost read regardless of distance — a retained flop.**  W6-6 (no new flop
without coordination) puts that outside this package's charter, and the STOP
condition names exactly this case.

---

## §4  THE REGISTERED PREDICTIONS, ANSWERED

| id | registered | outcome |
|---|---|---|
| **W6-D** | DERIVE names a single rail | **REFUTED** — `IND` (dist 0) and `M_EA` (dist 1) are disjoint; intersection EMPTY (§2) |
| **W6-1** | ≥3 fresh HOLDOUT closures **(the deliverable)** | **N/A — nothing landed.** No law reached HOLDOUT scoring because DERIVE refuted the single-rail hypothesis first. The pre-registered fallback ("book, land nothing") is taken |
| **W6-2 / W6-3** | LOST=0 / none earlier | **VACUOUSLY HELD** — no RTL change; `git diff 3999f0d669 HEAD -- hdl/` empty |
| **W6-4** | `530034` not closed by rail-alone | **HELD** — not landed; and §2 confirms `530034` is an `M_EA`/dist-1 seat, not a dist-0 `IND` seat |
| **W6-5** | §64.1 four unmoved, `404040` bad=0 | **VACUOUSLY HELD** — no RTL change |
| **W6-6** | `ss_lint` unmoved, no flop | **HELD** — no RTL change; and §3 is the reason the *correct* fix (a flop) was **not** taken here |
| **W6-7..W6-15** | gates green | **VACUOUSLY HELD** — no RTL change; every standing gate is exactly `3999f0d669`'s |
| **W6-16** | non-vacuity | **N/A** — no closed seat |
| **W6-17** | **G6 two draws ≥ 38.0 MHz** | **NOT RUN — no RTL was built.** The 38.0 STOP is moot; there is no bitstream to time |

**Nothing was landed, so no gate was re-measured; every standing ratchet remains
whatever it was at `3999f0d669`.**  Quoting any of them here would be a number
with no run behind it.

---

## §5  WHAT THE NEXT WAVE SHOULD PRE-REGISTER (and why it is NOT done here)

The table hands the next wave a sharp, high-prior candidate — **but it must be
pre-registered fresh, because these seats have now been inspected here.**

1. **`near_dist == 0` → `ghost_off = IND`.**  Corroborated **4 / 4** across
   DERIVE (`408021`, `524030`) and HOLDOUT (`527037`, `534060`) — and the two
   HOLDOUT seats chose nothing, so this already has genuine holdout support.
   `ghost_read_stale_alu` (`v30u_eu.sv:915`) fires on `upc_opc == 8'h8f`, i.e.
   **exactly the dist-0 case**, so an `IND`-scoped law is expressible without a
   distance selector.  **This is the most likely next landing**; it deletes
   `ghost_uses_ea`, `ghost_ea_off`, the `8E` case and the low-bit mask, and
   replaces them with a single register read.  It should be pre-registered on a
   FRESH split and validated on seats it was not derived against — do not land
   it on the strength of this document.
2. **The unified retention law.**  Latch the `8F`'s memory-address register at
   issue and hold it for the ghost read; this is one flop and would subsume both
   the dist-0 and dist-1 seats. It needs the save-state single-writer's
   coordination (W6-6) and a G6 receipt, and the timing precedent (the ghost
   FEED drew 15.3 MHz) means it must be measured, not assumed.
3. **The EMPTY seats** (`524055`, `528010`, `518033`, `518067`) are M10's
   reading-(i) — upstream value divergence — and belong to whichever package
   owns the earlier instruction, not to the ghost address at all (M10 §6.0).

## §6  DISCIPLINE NOTES

* **Pre-registration held.**  The split was frozen by an address-independent
  hash and committed (`3c4a43111a`) before the solve; the derivation ran on
  DERIVE; the single-rail hypothesis was refuted there, before any HOLDOUT
  closure was scored — so no fitted law could be laundered through HOLDOUT.
* **The candidate came from M10, and M10 was right about `M_EA` — for the seats
  it named.**  `518022`/`530034`/`519072` are `M_EA`. What M10 did not have (its
  survey is `E1`-only and its cheap subset was 9 seats) was the dist-0 half of
  the population, which is `IND`. The two together are one distance-indexed
  mechanism.
* **No board, no flash, `sim/` not extended, no Quartus** — nothing was built to
  land, so G6 was not drawn.
* **Capture files are gitignored** and were read through symlinks removed before
  the commit.
* **Artifacts banked for re-run**: `sw/testdata/fz2/fz2_w6_solve_derive.json`,
  `…_holdout.json`, the classifier `sw/fz2_w6_railcheck.py`, the split
  `docs/notes/fz2_w6_split.json`.

## §7  RE-RUNNING THIS

```bash
git rev-parse HEAD                      # 3999f0d669 + the two wave-6 doc commits
python3 sw/check_core.py --build --core ucore                 # the solve instrument
L=sw/testdata/fz2/fz2_failure_ledger_f16_2026-08-10.json
# (captures must be linked from the shared checkout first)
python3 sw/fz2_m10.py solve --ledger $L --seeds <DERIVE 16> --out /tmp/d.json
python3 sw/fz2_m10.py solve --ledger $L --seeds <HOLDOUT 23> --out /tmp/h.json
python3 sw/fz2_w6_railcheck.py --solve /tmp/d.json --solve /tmp/h.json
#   -> DERIVE: IND:2  M_EA:1  EMPTY:2  NOREPRO:8
#   -> HOLDOUT: IND:2  EMPTY:2  NOREPRO:11
```
