# v30sim

C++20 microcode-driven simulator for the NEC V30 (uPD70116). Every instruction
is executed by walking the rows of `docs/V20BITS.TXT`; nothing is flattened
into per-opcode C++. It implements the native pages AND the 8080 emulation
pages (`110`/`101`, entered by `BRKEM`/`MFC`, left by `RETEM`/`ENDEM` and by
every interrupt's `MFS`).

As of the campaign close (S4, 2026-08-01) it is **architecturally exact** on
7.34 M single-instruction captures across two parts — `v0.1` (169 000),
`v0.2` (347 000), `v0.3` (3 699 998) and the real-µPD70108 `v20suite`
(3 125 000), the last two **also with every flags-mask disabled** — on the
specials (`f4a_boundary`, `mod3_illegal`, `f0lock_tranche`, `enter_nesting`)
and the eleven pin-event pseudo-forms, and on **2 125 / 2 125** of the banked
fuzz seeds whose capture recorded a complete architectural dump (register-,
PSW- and ordered-write-stream exact). Micro-row coverage **912 / 1028**.

Since the `ucsim-t` campaign close (T5, 2026-08-02) it ALSO has a **cycle-exact
timing mode** behind the same interpreter — see "Timed mode" below. No external
dependencies; plain `make` and a C++20 compiler.

* Architectural verdict: `docs/notes/ucsim_campaign_verdict_2026-08-01.md`
* Timing verdict: `docs/notes/ucsim_t_campaign_verdict_2026-08-02.md`
* Provenance for every semantic decision: `docs/notes/ucsim_provenance.md`
* Provenance for every TIMING decision: `docs/notes/ucsim_t_provenance.md`
* Micro-row coverage report: `sim/coverage_report.txt`

## What exists

| file | contents |
| --- | --- |
| `ucrom.h` / `ucrom.cpp` | `MicroOp`, `MatchPat`, `UcRom` loader for `docs/V20BITS.TXT`, field-name tables, and the precomputed `bank_of[page][opcode][row]` micro-address decode with `fetch(page, opc, row)` |
| `disasm.h` / `disasm.cpp` | disassembly printer (`PrintOpcode` / `PrintInstrs` / `RangeStr` transliteration) |
| `pla3_table.h` | generated pla_3 group-decode tables (`docs/facts/pla_model.md`) |
| `state.h` | machine state as the microcode sees it: regs, tmps, OPR/IND/COUNT, the latched ALU, the micro-PC |
| `biu.h` / `biu.cpp` | 1 MB epoch-stamped memory + I/O, functional queue, ordered transaction log. Every access completes instantly; the `F`/`Q` interlock CALL SITES live in `exec.cpp` and are preserved for a future cycle-accurate mode |
| `ea.h` / `ea.cpp`, `loader.h` / `loader.cpp` | ModR/M + EA, the pre-decode contract (prefixes, operand binding, pre-read, page select) |
| `alu.h` / `alu.cpp` | the micro-ALU: combinational `alu_eval` and the per-iteration `alu_step` |
| `exec_impl.h` | the per-micro-row interpreter as `template <class Bus> class CpuT`, incl. the hardware interrupt/NMI/trap entries (`interrupt`), the INTA bus cycle and the 8080 mode flag. `loader_impl.h` is the same treatment for the pre-decode hardware. Bus-policy split, ucsim-t T0 |
| `exec.h` / `exec.cpp` | the FUNCTIONAL instantiation: `using Cpu = CpuT<Biu>`, one out-of-line copy, `extern template` so no other TU instantiates it |
| `exec_timed.h` / `exec_timed.cpp` | the TIMED instantiation: `using CpuTimed = CpuT<BiuTimed>` |
| `biu_timed.h` / `biu_timed.cpp` | the TIMED bus: same Bus concept as `Biu`, owns a CPU clock, emits one row per clock. The T-state FSM, the READY/eval instant, the queue latency pipeline, the prefetch scheduler, the flush rules, the HALT display. **No fitted table and no per-opcode timing exception — grep for one** |
| `rows.h` / `rows.cpp` | `ClockRow` + the two emitters: `check_core.py::parse_out` text and chip_rows NDJSON |
| `timed_runner.h` / `timed_runner.cpp` | `timed-run`: cases in, per-clock row streams + final regs out |
| `case_runner.h` / `case_runner.cpp` | SingleStepTests ingestion and verdicts |
| `image_runner.h` / `image_runner.cpp` | whole-IMAGE replay (`v30sim image`): 64K-mirrored memory, the ROM's own RESET sequence, multi-instruction execution to the harness done marker, ordered bus stream out. Drives the S3 fuzz-bank sequence gauntlet (`sw/ucsim_fuzz.py`) |
| `main.cpp` | CLI dispatcher (`disasm`, `info`, `run`, `image`, `trace`, `timed-run`) |

## Normative sources

* `docs/V20BITS.TXT` — raw microcode ROM dump: header line, then 1028 rows of
  29 bits. Every 4th row carries a 15-character activation pattern in columns
  31..45 encoding a 13-bit mask/compare micro-address match.
* `docs/V20UCDIS.PAS` — Turbo Pascal disassembler; the normative encoding spec
  for every field position and printing rule. `docs/HEXRANGE.PAS` supplies the
  opcode-range renderer.
* `docs/V20UC.TXT` — golden output (CRLF line endings).
* `docs/pla_3.txt` + `pla3_outputs.txt`, `docs/pla_2.txt`, `docs/pla4.txt` —
  PLA dumps; identification and status in `docs/facts/pla_model.md`.

## Micro-address layout

13 bits: `[12:10]` page, `[9:2]` opcode byte, `[1:0]` row within the 4-row bank.
Pages are `0 = norep, 1 = rep, 2 = F6/F7, 3 = FE/FF, 4 = 0F, 5 = 8080/ED,
6 = 8080, 7 = internal` (microcode-internal entry points / far-jump targets).

## CLI

```
v30sim disasm <romfile>                 microcode disassembly (V20UC.TXT format)
v30sim info   <romfile>                 row/pattern counts, micro-address coverage
v30sim run    <romfile> [--queue] [--emit-final] [--mirror]
                        [--alu-hw-report] [--coverage] [--wrap-scan]
                        [--report=N]    run SingleStepTests cases from stdin
v30sim image  <romfile> [--coverage] [--trace[=idx]]
                                        replay 64 KB test IMAGES from stdin
v30sim trace  <romfile> <idx>           per-micro-row dump of one case
v30sim timed-run <romfile> [--waits N] [--ndjson] [--mirror]
                        [--case=IDX] [--steps=N]
                                        TIMED mode: one record per CPU clock
v30sim timed-boot <romfile> <image.bin> [--clocks N] [--ndjson]
                        [--waits N] [--wvec F] [--wmax K --wseed S]
                                        TIMED mode from RESET RELEASE over a
                                        flat 64 KB image; clock 0 = release
```

Both `run` and `image` speak NDJSON on stdin/stdout and are long-lived, so the
Python drivers stream whole suites through one process.

## Timed mode (campaign `ucsim-t`)

The simulator has two bus policies behind one interpreter.  `sim/biu.{h,cpp}`
is functional (every access completes instantly) and `sim/biu_timed.{h,cpp}`
models a CPU clock and emits one row per clock; the micro-sequencing code is
literally the same template in both cases, so the architectural answer cannot
drift between them.

`timed-run` emits the RAW per-clock pin records that `sw/check_core.py`'s
`parse_out` / `build_rows_sim` already read — the same textual format
`hdl/tb/tb_v30_core.sv` writes — so the golden 11-column `cycles` rows are
synthesized by the UNMODIFIED python comparator rather than by new C++.
`--ndjson` switches to the chip_rows record shape `sw/check_seq.py` consumes.

The status column follows the v0.1 README's column-7 semantics (the V30 drives
the NEXT cycle's status during T4) — modelled as a registered output driven one
clock early, not as a T4 special case, because the goldens show an idle Ti row
carrying it too.

### Where it is exact, as of the campaign close

| | |
| --- | --- |
| `v0.1` cycle rows at w0 | **165 490 / 166 400 (99.45 %)** — 907 REP `cx>=2` + 3 tails short |
| `v0.1-w1` / `v0.1-w3` | **1 200 / 1 200** each |
| boot from RESET release | **220 / 220** rows, loop period exact |
| ENTER waited tranche (154 socket digests) | **154 / 154** on all five levels |
| INS `case250` factorial vs the chip capture | **2 624 / 2 624** strict rails; 173 556 / 173 556 leading accesses, all same-T1 |
| law cards (silicon-referenced) | **7 GREEN / 0 RED / 4 UNRESOLVED** |
| banked fuzz programs, whole-window cycle-exact | **947 / 1 702 (55.6 %)**, median prefix fraction 1.000 |
| a FRESH random-wait tranche (216 seeds, never seen) | **117 / 188 (62.2 %)** |

The model is **not** cycle-exact over whole 1 300-4 000-clock programs; the
victory gate V5 is recorded FAILED. Every residual is a named family in
`docs/notes/ucsim_t_campaign_verdict_2026-08-02.md` §(c).

### The wait axis, and what drives it

The timed bus carries the rig's three wait sources in `hdl/rtl/nec_bus.sv`'s own
priority order (replay > random > uniform), all keyed on a BUS-CYCLE index and
latched at T1 entry: `--waits N` (uniform), `--wvec F` (an explicit per-access
vector) and `--wmax K --wseed S` (the rig's 16-bit Galois LFSR, poly `0xB400`,
drawn once per bus cycle). The whole wait axis reduces to ONE instant per bus
cycle — `e = (N == 0) ? 2 : 3 + N` — with the status release, the display clock,
`eu_done` and the queue push all at fixed offsets from it.

### The gates and instruments

```sh
python3 sw/timed_gate.py --suite tests/v30/v0.1    --forms all             # the w0 ratchet
python3 sw/timed_gate.py --suite tests/v30/v0.1-w1 --forms all --waits 1
python3 sw/timed_gate.py --suite tests/v30/v0.1-w3 --forms all --waits 3
python3 sw/timed_gate.py --sbs B8:0        # golden vs sim rows, side by side
python3 sw/check_boot.py --timed 220       # boot replay from RESET release
python3 sw/timed_scenario.py               # L1: the frozen decoder oracles, w0/w1/w3
python3 sw/timed_enter_replay.py           # the 154 ENTER socket digests
python3 sw/timed_ins_replay.py --raw       # the case250 INS factorial plane
python3 sw/timed_wvec_gate.py              # the silicon-frozen wvec corpus
python3 sw/timed_lawcards.py               # the inherited law cards as sim gates
python3 sw/timed_fuzz.py                   # 3 242 banked fuzz programs
python3 sw/timed_fuzz.py --seeddir sw/testdata/t4/b2-tranche/seeds   # the victory tranche
```

Read-only instruments, all usable on a chip capture or a sim emission:
`sw/timed_probe.py` (group a form's failures by FIRST divergent cell),
`sw/qcensus.py` / `sw/q1census.py` (every queue pop with the ready clock of the
byte it took), `sw/q1diff.py` (chip vs sim, pop by pop, naming which pop moved),
`sw/wchain.py` (T4-to-next-T1 spacing keyed by the two statuses),
`sw/repcensus.py` (the REP string loops: per-iteration bus geometry, the
window-closing pop's offset from the last store, `cx` and the entry phase, chip
and model through ONE reconstruction). Every mechanism in the timing ledger was
found by reading one of their outputs. Two env-gated stderr traces add the
model's own internals and touch no model state: `V30SIM_EVALTRACE=1` (one line
per eval point and per clock) and `V30SIM_ROWTRACE=1` (one line per MICRO-ROW —
the clock it is reached on, its ROM row index and its disassembly), which is
the instrument M10 and M11 were measured with.

Every timing behaviour, its provenance class (ROM / LAW / MEASURED /
ASSUMPTION), its evidence and its falsifier are in
`docs/notes/ucsim_t_provenance.md`; the mechanism ledger — fifteen entries and
the eval instant, each a register, a threshold or a fixed cycle index — is §(b)
of the timing verdict.  The post-closure addendum (`ucsim_t_provenance.md` §16)
adds two more of the same shape: **M10**, the EU's single bus-request slot
(freed when the bus takes the request, at the accepted cycle's own T1), and
**M11**, no redirect bubble on a taken micro-JMP back by one row.  Together
they closed the 907-case REP `cx >= 2` residual and took v0.1 at w0 to
166,397 / 166,400.

## Build and the standing gates

```sh
python3 sw/simbin.py --build   # builds sim/build/v30sim THROUGH THE RECEIPT LAYER
python3 sw/simbin.py --disasm  # GATE 1: the disasm gate, on the receipted binary
python3 sw/pla3_check.py       # GATE 2: PLA identification, exit 0 / 21 checks
```

**THE BINARY EVERY SCORER RUNS IS `sim/build/v30sim`** (SM3 sitting 15,
`ucore_provenance.md` §76.A).  `sw/simbin.py` declares what it is a function of
— the sources, the Makefile, **and `docs/V20BITS.TXT`, which is read at RUN
time and is therefore part of the model's identity even though the compiler
never opens it** — and every `--core sim` tool asserts that receipt before it
scores anything.  `make -C sim` still works and still writes `sim/v30sim`; that
binary has no receipt and is on no scorer's path.

The disasm gate is `v30sim disasm docs/V20BITS.TXT | diff - docs/V20UC.TXT`
and must produce no output — the streams are byte-identical, CRLF included.

## Running the suites

`sw/ucsim_check.py` is the PRODUCTION checker (`run --emit-final` plus the
`sw/check_core.py::check_case` architectural policy: metadata flags masks,
`dont_care` cells, pushed-PSW derivation for pin events, RAM reconstruction with
fallback, `known_divergences` by CLASS (VOID excluded / EDGE kept), the `iords`
sidecar and the flat-fail → 64K-mirror retry).

```sh
# G-A  169 000 cases
python3 sw/ucsim_check.py --suite tests/v30/v0.1 --report ga.json
python3 sw/ucsim_check.py --suite tests/v30/v0.1-w1     # wait tranches
python3 sw/ucsim_check.py --suite tests/v30/v0.1-w3
python3 sw/ucsim_check.py --suite tests/v30/v0.2

# G-B  3.7 M cases  (~9 min)
python3 sw/ucsim_check.py --suite tests/v30/v0.3

# G-D  3.125 M cases of real uPD70108 silicon  (~6 min)
#      --no-mirror: that rig is not the 64K-mirrored capture board
python3 sw/ucsim_check.py --suite tests/v30/v20suite --no-mirror

# G-C  the specials
python3 sw/ucsim_check.py --suite tests/v30/f4a_boundary
python3 sw/ucsim_check.py --suite tests/v30/mod3_illegal --forms goldens \
        --residue stale-ea
python3 sw/ucsim_check.py --suite tests/v30/f0lock_tranche
python3 sw/ucsim_check.py --enter-nesting

# the headline rollups
python3 sw/ucsim_check.py --suite tests/v30/v0.3 --raw-flags   # every mask off
python3 sw/ucsim_check.py --suite tests/v30/v0.2 --alu-hw      # PSW attribution
```

Useful flags: `--forms 88,89,...` / `--cases N` to narrow a run, `--subset
subset.json` to run a named case list, `--details N` for per-failure dumps,
`--wrap-scan out.json` for the A12 segment-boundary EXTRACTION pass (writes the
subset, performs no comparison).

`sw/ucsim_smoke.py` is the lighter bring-up survey (`--suite ... --all`,
`--s1b`, `--alu-hw`).

## The fuzz replay (S3 sequence gauntlet)

`sw/ucsim_fuzz.py` regenerates each banked seed's 64 KB image from `(cid, k,
ov)` with the SAME generator the capture used, **verifies `image_sha256` before
every replay** (a mismatch is GEN-DRIFT and a hard failure), runs it through
`v30sim image` from RESET release, and compares the ordered functional bus
stream plus `chip_arch` against the socket capture.

```sh
python3 sw/ucsim_fuzz.py --bank mc1,mc2,t30-raw      # F-A, ~22 s, 16 workers
python3 sw/ucsim_fuzz.py --bank t30-brkem            # F-B, the 8080 report
python3 sw/ucsim_fuzz.py --bank mc1 --k 1447 --details 20   # one seed
python3 sw/ucsim_fuzz.py --bank mc1,mc2,t30-raw --census    # executed-prefix census
python3 sw/ucsim_fuzz.py --bank mc1,mc2,t30-raw --stat-clobber  # the sec.60 falsifier
```

Wait axes are timing-only: the functional stream must be wait-INVARIANT, so a
seed whose architectural outcome depends on its wait axis is a FINDING, not a
simulator bug — the rollup prints the per-wait-class census so a collapse in
one class cannot hide.

## Micro-row coverage

```sh
python3 sw/ucsim_check.py --suite tests/v30/v0.1 --coverage cov.json   # accumulates
python3 sw/ucsim_fuzz.py  --bank mc1,mc2,t30-raw,t30-brkem --coverage fz.json
python3 sw/ucsim_check.py --coverage-report cov.json                   # names dead rows
python3 sw/ucsim_coverage_report.py cov.json fz.json  # -> sim/coverage_report.txt
```

`--coverage` on `ucsim_check.py` ACCUMULATES into the file, so the counter is
the union over every gate; `ucsim_fuzz.py --coverage` writes a bare 1028-entry
list. `sw/ucsim_coverage_report.py` merges the two and classifies every row no
gate executed (its docstring lists the full gate sequence); the committed
result is `sim/coverage_report.txt` — **912 / 1028 executed**, of the 116
unexecuted rows **9 substantive** (the POLL tail behind `JMP BUSY`, and bank A
of the one ambiguous micro-address), 14 post-`FARJMP` and 93 bank tails.

## What is deliberately not modelled

### In the FUNCTIONAL mode

Four numbered policies, each with the timing mechanism that would replace it
(`docs/notes/ucsim_provenance.md` §38, §57, and the verdict's §(d)):

* **cycle timing / prefetch.** The model fetches a byte when the decoder asks
  for it and keeps no speculative queue, so `final.queue` is not compared; the
  consumed-instruction-byte count stands in for it and is asserted on every
  case. **This is what the timed mode above replaces** — the functional mode
  keeps it, deliberately, so the architectural gates stay fast.
* **I/O port values** are REPLAYED from the capture (case name `iord=XXXX`, an
  `iords/` sidecar, or the case's own bus trace), never predicted.
* **the interrupt firing boundary** is replayed — single-instruction cases from
  the golden's pushed frame, sequence cases from two coordinates (bus position
  AND the recorded resume `CS:IP`). Every *consequence* — acknowledge, vector
  fetch, frame, resume PC, `CW`/`IY` at a REP abort, flush, mode flag — is
  computed from the ROM and diffed.
* **`BUSY`** is hard-FALSE (no pin model), which is why the five POLL busy-loop
  rows are unreached.

### In the TIMED mode

* **Interrupt / INTA timing under waits** — an explicit scope exclusion of the
  whole `ucsim-t` campaign, inherited from the RTL campaign. It is excluded
  from every timed gate, by construction in the victory tranche (`no_evt` set
  at GENERATION). Un-measured, not merely un-modelled.
* **The pin-event scheduler** — `timed-run` and `timed-boot` execute
  instructions; the INT / NMI / RESET event replay `case_runner` performs is not
  in the timed path, and the POLL pin's 5-clock sampling is not modelled. That
  is why 2 600 v0.1 cases in thirteen pseudo-forms sit outside the w0
  denominator. (The HALT bus pseudo-cycle IS modelled and measured.)
* **8080-mode timing** — never separated by any gate.
* **`BUSLOCK`** — `ClockRow::lock_n` is still a constant; no non-pin-event v0.1
  form exercises it.
