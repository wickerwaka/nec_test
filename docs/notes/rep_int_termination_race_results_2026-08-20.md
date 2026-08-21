# REP termination versus external INT -- results

Date: 2026-08-20

Pre-registration: `docs/notes/rep_int_termination_race_prereg_2026-08-20.md`,
committed as `f688db385b` before the first socketed-V30 capture.  The tested
baseline was `e61f2e0988`.  No bitstream was flashed.

## 1. Verdict

The report is confirmed.  In the unmodified ucore, an external INT recognized
on the same completed SCASB iteration as the REP termination condition wins
too early in `C_REP`.  The pushed IP names the repeat prefix, so IRET restarts
the instruction after DI/CX have already advanced past the terminator.

The directed bare-core sweep reproduced exactly 20 overruns in 600 placements:

| arm | failing delays | pre-fix final state | pushed IP | INTA / ISR |
|---|---|---|---|---|
| REPNE SCASB, match terminates | 59..68 | `IY=240C CW=0000` | `0500` | 2 / 1 |
| REPE SCASB, mismatch terminates | 59..68 | `IY=240C CW=0000` | `0500` | 2 / 1 |

The socketed V30 does not overrun.  All 24 preregistered cells (delays 58..69
on both arms) ended at `IY=2406 CW=0006`, serviced the external interrupt
exactly once, and contained two INTA cycles.  Their pushed PC was `0102`, the
post-instruction boundary in the whole-image geometry.  This confirms that
silicon consults the completed iteration's termination result before servicing
the pending external INT.

## 2. Test and retained hardware evidence

`sw/rep_int_term_race.py` builds both SCASB polarities around a terminator at
element 6 of 12.  The six-byte tail has the opposite comparison polarity, so
a lost decision produces the unique `240C/0000` signature.  The ISR is
`INC BP; IRET`; BP, pushed PC, and INTA count independently prove that the
interrupt was serviced rather than lost.

The RTL regression runs 300 delays per arm in one invocation of the bare
`v30_core` testbench.  The hardware subcommand explicitly selects the socket
(`use_core=False`) and was run only after the preregistration commit.

Retained evidence:

- `sw/testdata/rep-int-term-race/board.json`: derived rows and run metadata;
- `sw/testdata/rep-int-term-race/board.raw.json.gz`: every raw 64-bit capture;
- `sw/testdata/rep-int-term-race/SHA256SUMS`: hashes for both files;
- `sw/testdata/rep-int-term-race/rtl-post.json`: the post-fix 600-cell result.

`gzip -t board.raw.json.gz` and `sha256sum -c SHA256SUMS` passed.  The run used
the socketed V30 at divider 8, completed in 2.2 seconds, did not flash, closed
the serve session, returned the board to `completed; socket selected`, and a
post-run process check found no `v30ctl` or `serve` process.

After the complete hardware artifacts had been written, the driver hit a
reporting-only `Path.relative_to()` exception because `--out` was relative.
The output path is now resolved before capture.  The board was not rerun:
the raw and derived artifacts were complete, their hashes passed, and the
safe-close checks had already completed.

## 3. RTL correction

`hdl/rtl/ucore/v30u_eu_cond.svh:C_REP` now evaluates `TEST_Z` / `TEST_CY`
immediately after the existing count-exhaustion check.  External INT and TF
withdrawal are considered only when that result says another REP iteration
would run.

`TEST_NONE` still sets `taken=1`, so REP STOSB/MOVSB and the existing
`INT.F3AA` withdrawal path retain their previous ordering.  Count exhaustion
also retains highest priority.

## 4. Post-fix verification

Directed result:

- `python3 sw/rep_int_term_race.py rtl --out sw/testdata/rep-int-term-race/rtl-post.json`
- **600/600 pass, 0 overruns**;
- REPNE and REPE each still service 83 interrupts, exactly matching pre-fix;
- aggregate ISR counts remain `{0:434, 1:166}` and INTA counts remain
  `{0:434, 2:166}`;
- former race delays 59..68 now end at `IY=2406 CW=0006`, push `0502`, and
  retain two INTA cycles.

Compatibility and standing gates:

- all 12 SCAS/CMPS forms (`A6,A7,AE,AF,F2A6,F2A7,F2AE,F2AF,F3A6,F3A7,F3AE,F3AF`):
  **6,000/6,000**, cycles and architecture;
- `INT.F3AA` in `v0.1`, `v0.1-w0evt`, `-w1evt`, `-w2evt`, and `-w3evt` at
  waits 0/0/1/2/3: **200/200 in each suite**, cycles and architecture;
- `check_core.py --core ucore --opcodes all --cases 0`:
  **169,000/169,000**, cycles and architecture;
- `ss_lint.py`, `r7_lint.py`, `check_ucore_tables.py`, and
  `prefix_clear_lint.py`: PASS;
- `test_artifact.py`: **45/45 PASS**.

The post-fix Verilator binary receipt is
`dce1d81113b4d54996dba027c2b88d77be5017df91140cc11ef9bdc39097e2b7`.

Per the later instruction to build once, Quartus was limited to one retention
fit (`--seeds 1 --retention`), with no further seed sweep:

| seed | configuration | Fmax | worst setup slack | ALMs | verdict |
|---:|---|---:|---:|---:|---|
| 1 | `X1_AD_RETENTION=1` | 39.63 MHz | +7.233 ns | 10,286 / 41,910 | PASS |

The bitstream receipt is
`c5881aaa847cfa0b35a475046cafa7124240af70e1fc9fd4ddd09a144f494dc0`;
the one-build distribution record is
`95ffb67a388df9d835e343d6a4e91e67d244257761ee4cb692b3a43c80b77924`.
As the gate reports, N=1 is an intermediate-wave measurement, not a
multi-seed promotion distribution.

## 5. Reproduction

```bash
# Directed post-fix sweep
python3 sw/rep_int_term_race.py rtl \
  --out sw/testdata/rep-int-term-race/rtl-post.json

# SCAS/CMPS family
python3 sw/check_core.py --core ucore \
  --opcodes A6,A7,AE,AF,F2A6,F2A7,F2AE,F2AF,F3A6,F3A7,F3AE,F3AF \
  --cases 0

# Complete golden corpus
python3 sw/check_core.py --core ucore --opcodes all --cases 0

# One retention build, as requested
python3 sw/quartus_gate.py --seeds 1 --retention \
  --label rep-int-term-retention-single-20260820 \
  --artifact-dir sw/testdata/g6dist/rep-int-term-retention-single-20260820
```
