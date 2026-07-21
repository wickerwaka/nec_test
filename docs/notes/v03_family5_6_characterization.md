# Task #24 Phase 1 — Family 5/6 characterization (data, not hypotheses)

Extraction from the on-disk v0.3 goldens (chip) vs the RTL core (check_core TB), zero board
cost. Chip = socket golden; RTL = internal v30_core. Method: bus-cycle order (`(busstat,
addr20)` at each T1) and per-column row diffs. Law-thinking deferred to the architect.

---

## Family 5 — single string-I/O prefetch ordering (44,935 cases)

Forms (7): OUTS 6E/6F/26.6E/2E.6F/36.6E, INS 6C/6D. 27,423 of the 44,935 have a resolvable
continuation-CODE fetch in both traces and are measured below (the rest are the pf-side /
window-edge cases that carry no in-window continuation fetch — see "cold-only").

**Measurement:** the CONTINUATION next-instruction CODE fetch (matched by address across the
two traces) — how many string-element DATA cycles (MEMR/IOR + IOW/MEMW) precede it, chip vs
RTL. `deferral = chip_data_before - rtl_data_before`.

**RTL is UNIFORM: rtl_data_before = 0 for ALL 27,423** — the RTL always prefetches the
continuation immediately, before the element's data cycles. The chip DEFERS it.

### [A] Deferral distribution, by form
| form | kind | width | seg-ovr | deferral counts |
|---|---|---|---|---|
| 6E | OUTS | byte | 0 | {2: 5000} |
| 6C | INS | byte | 0 | {2: 5000} |
| 26.6E | OUTS | byte | 1 | {2: 2503} |
| 36.6E | OUTS | byte | 1 | {2: 2506} |
| 6F | OUTS | word | 0 | {2: 2528, 3: 2472} |
| 6D | INS | word | 0 | {2: 2551, 3: 2449} |
| 2E.6F | OUTS | word | 1 | {2: 1281, 3: 1133} |

Overall: **deferral = 2** (21,369) or **3** (6,054). Never 0, never >3.

### [B] Cross-tabs (deferral vs conditioning variable)
| variable | deferral split |
|---|---|
| width | byte: {2: 15009} ; word: {2: 6360, 3: 6054} |
| memory pointer (SI/DI) parity | even: {2: 13998} ; odd: {2: 7371, 3: 6054} |
| port parity (DX&1) | even: {2, 3} ; odd: {2 only} |
| DF | df0: {2:10846,3:2929} ; df1: {2:10523,3:3125} (≈independent) |
| seg-override | seg0: {2,3} ; seg1: {2,3} (≈independent) |
| cold/pf | **cold(even) only — 0 pf(odd) cases divergent** |

**deferral=3 is EXACTLY: width=word AND memory-pointer=odd** (all 6,054: width all 2 ✓,
pointer all odd ✓; port all even ✓ — but word forms are even-port by the generator's
constraint, so port-parity is a consequence, not a condition). Otherwise deferral=2.

**Cold-only (verified):** e.g. 6C divergent = 5000, all even(cold), 0 odd(pf); a pf case's
chip and RTL bus order are IDENTICAL.

### [C] The CW=1 REP discriminating cell — REP is clean at EVERY CW, including CW=1
| REP form | CW=0 | CW=1 | CW=2 | CW>=3 |
|---|---|---|---|---|
| F36C/F36D/F36E/F36F | 0 div | **0 div** | 0 div | 0 div |

A CW=1 REP executes the identical element bus sequence as a single, yet **reproduces**
(0 divergent) while the single diverges. So the deferral is conditioned on the REP-prefix
PRESENCE, not the element sequence or count. Traces (cold):
```
6E single    CHIP: MEMR, IOW, CODE(cont)          RTL: CODE(cont), MEMR, IOW, CODE
F36E CW=1    CHIP: CODE(op), CODE(cont), MEMR, IOW  RTL: CODE(op), CODE(cont), MEMR, IOW  (identical)
```
Under REP the CHIP prefetches the continuation EARLY (matching the RTL's always-early); as a
single it DEFERS. **The RTL's uniform "prefetch-early" is correct for REP, wrong for singles.**

---

## Family 6 — word-REP-INS queue-status timing (16,342 cases)

Forms (4): 646D/656D/F26D/F36D (all word REP INS). Uniform across all 16,342:
| observable | value (all 16,342) |
|---|---|
| mismatch columns | qop (9) + dependent qbyte (10) + length only |
| qop mismatch (chip, sim) | **(F, -)** — chip asserts a queue-fetch marker the RTL omits |
| trace length delta | **sim = chip + 1 row** (RTL one row longer) |
| context of chip's extra qop=F | **(Ti, PASV)** — an idle/passive cycle between bus cycles |
| CW of divergent cases | CW=1: 3063, CW=2: 3137, CW=3: 3099, CW>=3: 7043 |

**INDEPENDENT of Family 5:** different signature (qop=F at an idle cycle + one extra RTL
row, arch-clean), and it is present at **CW=1** where Family 5's REP path is clean. Byte REP
INS (646C/…) and word non-REP are NOT in this family. It is a queue-status point-sample /
word-fetch-pacing timing difference specific to word REP INS.

---

## Families 1–4 (62 cases) — clean tabulation only (separate mechanisms, later phases)

| family | forms | cases | nature | mismatch columns |
|---|---|---|---|---|
| F1 timing | 0F31 (INS bit-field) | 25 | cycle-only, arch-clean | UBE(5)/tstate(8)/busstat(7) at cyc 9-10 |
| F2 BCD-4S | 0F26 (10), 0F22 (5), 0F20 (9) | 24 | mostly ARCH (functional); 0F20 mixed | final-state; 0F20 also data(6)/bus(1) |
| F3 pin-event | HLT.RES (6), IE0.90 (4) | 10 | ARCH (final-state) only | final regs/flags |
| F4 bus | 0F1B, 83.5, FF.3 | 3 | 1 cyc+arch each | bus-address(1)/data(6) |

Total 25 + 24 + 10 + 3 = **62**. Grand ledger total: 44,935 + 16,342 + 62 = **61,339**.
