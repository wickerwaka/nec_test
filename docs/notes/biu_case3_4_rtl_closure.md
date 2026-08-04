# V30 BIU/EU cases 3 and 4: direct-address reservation and QS launch

## Case 3: direct-address ModRM is not no-displacement

The prior `eu_rsv_modrm` rule tested only `mod == 00`, but the `r/m == 110`
encoding has a mandatory disp16.  It therefore falsely reserved direct-address
reads/RMWs at the ModRM pop, before their displacement was consumed.

The `fz16` uniform-w1 residual localized this error:

- waited CODE `05b2` completed while `01 3e db 24` decoded;
- the chip immediately launched CODE `05b4`;
- the RTL treated ModRM `3e` as no-displacement and delayed that fetch by
  three clocks;
- changing either of the two immediately preceding CODE waits removed the
  error.

The corrected predicate adds `q_byte[2:0] != 3'b110`.  The frozen discovery
oracle is `sw/testdata/biu_blackbox/case3-direct-oracle-v1.json`, SHA-256
`f2a11c2c6a33a9991b14791496479c48a7ca8db429e2cefa83d1b24e24a7f1b5`.
After the fix, `fz16` uniform-w1 is fully clean on both fabric and Verilator:
final offset 0, peak excursion 0, writes identical.

## Case 4: final disp16 pop colliding with a CODE launch

The broader case-3 matrices exposed a separate EU queue-consumer discrepancy.
Bus action, exact T1, address, and width already agreed, but when a fresh
disp16-high byte became consumable in the same CPU clock as a class-5 CODE
launch:

- the chip reported `QS=S` at the following CODE T1;
- the RTL reported it one clock before T1.

This held across direct-address and ordinary base+disp16 read, RMW, write, and
LEA forms.  Disp8 and no-displacement controls were clean.  The mismatch was
1:1 with the launch collision over 260 discovery cells.  The frozen rule is
`sw/testdata/biu_blackbox/case4-qs-launch-oracle-v1.json`, SHA-256
`614ddb90b100859b400bb59a9a63c3f08c2d24ff843dfab28556b05f222b25f5`.

The BIU now exports the combinational class-5 due window as `qpop_law_hold`.
The EU uses it only for a fresh final displacement pop, retrying that pop at
the following T1.  No registered state or savestate field was added.

## Verification

- Assertion-enabled Verilator build: PASS.
- Full zero-wait gate: 169,000/169,000.
- Prospective ordinary-disp16 pad-14 matrix: 252/252 exact chip/fabric records.
- Replays:
  - direct-address pad 2: 252/252;
  - direct-address pad 10: 252/252;
  - ordinary disp16 pad 10: 252/252.
- Each matrix covers waits 0-7 and 15, histories A/B, 4/8 MHz, reader
  destinations AW/DW, RMW, write, LEA, disp8, and no-displacement controls.
- Quartus: 0 errors; setup slack +3.817 ns; hold slack +0.260 ns.
- Deployed SOF SHA-256:
  `412f13440b96887c6b2cf23e68f9096e34a4b60c29c868db44590678028433e8`.

The attempted placement-normalized case-3 oracle v2 was correctly falsified
by pad 10; queue-consumer timing is phase-sensitive, so it is retained as a
failed artifact rather than counted as closure evidence.

These two rules close the selected residuals, not the complete wait-state
model.  Fresh sampling still finds small residuals (`fz6`, `fz7`, and `fz12`
depending on wait distribution).
