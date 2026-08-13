# TIMING50 — `CHAIN_MAX` 12 → 7: THE PRE-REGISTRATION

**Committed BEFORE the edit.**  Tree `298d522872` (`master`), isolated
worktree.  **Offline.  Quartus in scope.  NO board, NO flash.**

## STANDING DESIGN PRINCIPLE (verbatim, user directive 2026-08-01)

> SIMPLICITY: this is 80's era hardware — nothing on the die is wasted.
> Complex or confusing observed behavior is likely simple systems interacting
> in ways not yet understood. A large fitted table, a many-cased rule, or a
> per-opcode special case is a signal of misunderstanding, not a deliverable.

## THE ce/ce_half CONTRACT (USER, Reading B — UNIVERSAL)

The only assumables are **(a)** `ce` and `ce_half` never coincide, and
**(b)** ≥ 1 idle cycle between assertions.  **No div-based derivation
anywhere.**  The harness registered in §3 is built to that contract and to
nothing narrower.

---

## §1 THE EDIT

`hdl/rtl/ucore/v30u_eu.sv:3044`

```
-localparam bit [3:0] CHAIN_MAX = 4'd12;
+localparam bit [3:0] CHAIN_MAX = 4'd7;
```

**One line.  Nothing else in `hdl/rtl/ucore/` changes.**

### 1.1 THE `[3:0]` WIDTH — CHECKED, AND NARROWING IS **REFUSED**

The brief asks whether the declared width can narrow with the bound.  Every
comparison and every use was read:

| site | text | what a `[2:0]` `chain` would do |
|---|---|---|
| `v30u_eu.sv:3049` | `reg [3:0] chain;` | the loop variable itself |
| `:3430` | `for (chain = 0; chain < CHAIN_MAX; chain = chain + 4'd1)` | at `chain == 7` the increment **wraps to 0** and the loop never terminates — an **elaboration hang**, not a runtime bug |
| `:3433` | `chain_used = chain + 4'd1` | `chain_used` must hold 7; 3 bits holds 7 but the `+ 4'd1` operand is 4-bit |
| `:3435/3437/3439` | `cp_seen[{chain, st_n}]`, a `[0:1023]` array | `{chain, st_n}` is **4 + 6 bits by construction**; a 3-bit `chain` silently re-keys the whole `CHAIN_PROBE` census |
| `:3451` | `(chain != 4'd0)` | 4-bit literal comparison |
| `:3010/3011` | `reg [3:0] chain_hi`, `reg [3:0] chain_used` | simulation-only; hold 7 fine, but see the wrap above |

**The width stays `[3:0]`.**  It is one literal of declaration and it is what
makes `chain + 1 == 8` representable, which is what makes `8 < 7` false and
the loop terminate.  Narrowing it buys nothing (the loop is unrolled at
elaboration; the declared width of an elaboration-time constant is not a
fabric cost) and risks an elaboration hang.  **Refused, with the reason
named.**

---

## §2 THE BOUND — THREE SOURCES, AND ONLY ONE OF THEM IS A GATE

The claim being tightened is *"no more than 6 zero-cost model steps ever ride
one clock."*  `CHAIN_MAX = 7` is that bound **plus one spare position**,
because fabric has no assertion.

| # | source | what it is | status |
|---|---|---|---|
| 1 | `ucore_provenance.md` §51.2 — the transition-graph argument (nine states enterable at position ≥ 1) **plus** a `(position, state)` census over 347 golden forms × 12 waits + the boot march: 24 / 9 / 5 / 3 / 2 / 1, **max depth 6** | this tree's own derivation | **CITATION** |
| 2 | `m72_downstream_timing_2026-08-12.md` §3 — the graph re-derived independently in another repo before §51.2 was read; same nine states, same depth 6 | replication | **CITATION** |
| 3 | an LFSR-environment harness reporting `CHAIN_DEPTH_MAX 6` on four seeds × 420,000 clocks, entry state 25 (`S_EPOP`) | corroboration on a stimulus distribution with nothing in common with the golden suite | **CITATION** (it was a scratch artifact in the M72 session and is in neither repo) |
| 4 | **`CHAIN OVERFLOW`** — `v30u_eu.sv:3763`, §51.3's `$fatal`, which fires if the loop ends with `stop` still low | **THE PROOF** | **GATE** |

**The three sources are citation.  The `$fatal` is the proof.**  A bound is
not established by three people agreeing about a graph; it is established by
an assertion that would have fired and did not, over every population this
tree runs.

### 2.1 SOURCE 3 IS PORTED INTO THIS TREE AS A STANDING GATE — §3

Source 3 exists only as prose in another repo's report.  This wave builds it
here, because the whole point of tightening a bound is that something in the
tree keeps checking it after the sitting that tightened it ends.

---

## §3 THE NEW INSTRUMENT — `hdl/tb/tb_chain_lfsr.sv` + `sw/chain_lfsr_gate.py`

**What it is**: the ucore (`v30_core`, ucore file list) in an environment that
is entirely LFSR — LFSR memory, LFSR `READY`, LFSR `INT`/`NMI`/`POLL_N`, and a
**contract-shaped CE train with LFSR gaps**.  It executes arbitrary bytes, not
347 known forms.

**The CE train is the part that must not be got wrong.**  It is generated to
Reading B and to nothing narrower:

* `ce` for one fabric clock, then `ce_half` on the **next** fabric clock
  (never coincident — clause (a) holds by construction, and it is
  **asserted** in the TB, not assumed);
* then an LFSR-drawn gap `g ∈ [0, 7]` of idle clocks before the next `ce`.
  **`g = 0` is the contract's minimum-gap pattern** — `ce` every two fabric
  clocks, the M72 catch-up-burst rate — and the harness must be shown to
  reach it, or the train is our div-8 train wearing a disguise.
* **The div-8 train is NOT used and no `div` appears in the file.**

**What it reports**: `CHAIN_DEPTH_MAX` (the RTL's own `+chaindepth`
observer, `v30u_eu.sv:3766-3769`), a 64-bit rolling signature over every core
output on every fabric clock, and the CE-train census (`g` histogram, minimum
gap reached).

**`CHAIN OVERFLOW` is armed in it** — it is armed in every non-synthesis build
of the ucore by construction, since it lives under `ifndef SYNTHESIS` with no
plusarg guard.

### 3.1 REGISTERED BARS FOR THE INSTRUMENT

| id | clause | bar |
|---|---|---|
| **H-1** | at `CHAIN_MAX = 12`, four seeds × ≥ 400,000 fabric clocks each | `CHAIN_DEPTH_MAX ≤ 6` on **every** seed, 0 `CHAIN OVERFLOW` |
| **H-2** | the CE train reaches the contract minimum | `g = 0` observed ≥ 1,000 times per seed, and `ce & ce_half` coincident **0** times |
| **H-3** | **NON-VACUITY**: a build with `CHAIN_MAX` forced BELOW the observed max (`4'd4`) on the same stimulus | `CHAIN OVERFLOW` **FIRES** |
| **H-4** | after the edit, the same four seeds at `CHAIN_MAX = 7` | `CHAIN_DEPTH_MAX ≤ 6`, 0 overflows, **and the 64-bit output signature BYTE-IDENTICAL to the `CHAIN_MAX = 12` run, seed for seed** |

**H-3 is the one that makes H-1 and H-4 mean anything.**  An assertion that
cannot fire is not evidence, and this repo has the vacuous-gate pattern by
name.

---

## §4 WHAT THE CHAIN IS AND IS **NOT** IN THE BINDING CONE

**This is a prediction, derived before the builds, and it is the one the
sitting is most likely to be wrong about — so it is registered as a claim
with a falsifier and not as background.**

The binding class on this tree is `v30u_eu|upc_opc[*] → nec_bus|ad_in_q[*]`,
29-40 levels, single-cycle, 60 of the top 60 in both configurations
(`timing50_e1_rederivation_2026-08-12.md` §5, R-3).

**Read structurally, that cone does not traverse the chain.**  The chain
writes `*_n` — next-state names — and every one of them terminates on a
register `D` pin.  The core's AD publication is a separate expression tree:

```
upc_page/upc_opc/upc_loc (REGISTERS)
    -> v30u_ucrom -> row
    -> v30u_eu's `assign eu_addr` / `eu_bs` / `eu_wdata` / `eu_pair`   (:2149-2177)
    -> v30u_biu's `assign ad_o`                                        (:1056-1065)
    -> nec_bus|ad_in_q
```

and `v30u_biu.sv:1046-1049` states the loop rule for exactly this reason:
*"this is REGISTER-ONLY LOOKAHEAD … `eu_pair` / `eu_wdata`, which are
functions of EU REGISTERS only, and `ad_o` is a pin that feeds nothing inside
the core."*

**MEASURED on the source, not asserted**: the transitive fan-in of
`eu_addr`, `eu_bs`, `eu_wdata`, `eu_pair`, `eu_post`, `eu_addr2`, `eu_seg`,
`eu_word`, `eu_split`, `eu_ghost_acc` — 301 nets — contains **ZERO** names
written inside the chain's `always @*` block or any of its `.svh` includes.
(Three apparent hits, `st` / `opr` / `opc_base`, were matches inside
**comments** and are not assignments.)

**M72's failing class was a different endpoint**: `upc_opc → ucdecode → ucrom
→ the chain → r_kind / modrm_reg` — a `CORE→CORE` path.  On this tree
`CORE→CORE` carries **+30.696 (CTL) / +30.789 (RET)** against a 4-period
budget and is nowhere near binding.  **The chain is deep in M72 because M72's
budget for it is two `clk_sys` periods; here it is four, and the class it
binds is not the class that binds here.**

### 4.1 SO THE HONEST PREDICTION IS: AREA YES, BAND PROBABLY NOT

| id | clause | bar |
|---|---|---|
| **P-1** | ALMs fall | **whole-design ALMs strictly below the 12,271 (CTL) / 12,317 (RET) of `timing50_e1_rederivation_2026-08-12.md` §5**, on the worst of the two draws in each configuration |
| **P-2** | `CORE→CORE` worst slack **improves** (this is the class the chain is actually in) | > +30.696 (CTL) / > +30.789 (RET) |
| **P-3** | the binding class stays `CORE→ANY`, `upc_opc[*] → ad_in_q[*]` | as measured by `sta_census.tcl` on the fitted db |
| **P-4** | **THE BAND FLOOR** — worst-of-2 improves by **≥ 1.0 MHz on at least one configuration** against the honest band **CONTROL 41.18 / RETENTION 42.28** | **PREDICTED TO MISS.**  §4 says the chain is not in the binding cone, so the expected movement is placement noise, not a lever. |

### 4.2 THE DISPOSITION RULE, WRITTEN BEFORE THE BUILDS

Registered verbatim from the brief and **binding on this sitting**:

> a **P-4** miss **is a finding, not a failure** — it reports that the chain
> was NOT the binding term here.  **NO REVERT in that case unless ALMs also
> fail to improve** (i.e. unless **P-1** misses too).

So:

* **P-1 met, P-4 missed** → **LAND**, and report that the lever bought area
  and depth and not band.
* **P-1 missed AND P-4 missed** → **REVERT.**
* any **H-1/H-3/H-4** miss, or **any** `CHAIN OVERFLOW` on any population →
  **REVERT**, unconditionally, whatever the band did.
* **G6 red** (Fmax < 32, worst setup ≤ 0, or TNS ≠ 0.000 on any domain,
  setup or hold) → **REVERT.**

---

## §5 THE LADDER THAT MUST BE GREEN TO LAND

Registered at the values this tree carries, so a miss is visible as a miss:

| gate | bar |
|---|---|
| `sw/gen_ucore_qsf.py --check` | PASS |
| `python3 sw/r7_lint.py` | PASS, 0 violations |
| `python3 sw/test_artifact.py` | 45/45 |
| `python3 sw/ss_lint.py --core ucore` | exit 0, **no flop added or removed** |
| `check_core --core ucore --opcodes all --cases 0` | **169,000/169,000** |
| `check_core --core ucore --opcodes 8F.0` | **500/500** |
| the four HLT sweeps (⚠ `--waits 0/1/2/3`) | **97 · 93 · 45 · 44 = 279/283** |
| `v0.1-w1` / `-w3` / `EB` | 1,200 / 1,200 / 200 |
| the four `evt` cells | 200 / 1,200 / 200 / 1,200 |
| `v0.1-w1evt-biased` | 1,200 |
| `ulockstep.py --golden all --cases 50` | **17,350/17,350** |
| `check_boot.py --core ucore` | 220 / 400 MATCH |
| **the new gate** `sw/chain_lfsr_gate.py` | depth ≤ 6 observed, **0** overflows, signature identical to the pre-edit run |
| **G6** `sw/quartus_gate.py` ×2 and `--retention` ×2 | PASS on every draw; worst-of-2 reported per §4.1 |

Legs the brief names that this tree may or may not be able to run
(`ghost_launch_law score`, the ie-pinfall replay, `fz2_replay`) are attempted
and **reported as attempted** — where a leg cannot run here, the reason is
named and it gates nothing, per the standing rule that a figure that cannot
be measured may not be quoted.

---

## §6 WHAT IS **NOT** BEING CLAIMED

* **Not** that 50 MHz is reachable.  `timing50_e1_rederivation_2026-08-12.md`
  §6.3 measured the ceiling behind the whole observation class at
  **44.10 / 45.17 MHz**, and the wall behind that (`div_cnt → t1_half2`) is
  RTL and behaviour-visible.
* **Not** that the depth bound is now proven for all inputs.  It is
  **asserted continuously** by `CHAIN OVERFLOW` over every population this
  tree runs, which is a different and better thing than proven-once.
* **Not** a new corpus-scoped claim beyond the one §51.2 declined to make.
  §51.2 declined to tighten *because tightening makes a claim*; this document
  makes that claim, names its three sources, and arms its falsifier.
