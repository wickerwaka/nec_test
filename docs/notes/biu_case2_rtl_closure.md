# V30 BIU case-2 RTL closure

## Result

The ordinary waited-CODE versus no-displacement memory-read collision is
closed on the socketed V30 and the synthesized fabric core.

Before the fix, the controlled A/B matrix had 12 mismatches:

- `MOV AW,[BW]`, `MOV DW,[BW]`, and `INC word [BW]`
- selected CODE access at Tw=4
- preparation histories A and B
- 4 MHz and 8 MHz

In every failing cell, the chip selected `MEMR 0x2000` at final-ModRM-pop +4,
while the RTL selected CODE at +3. Store and LEA controls matched.

## Discovered rule

At the waited CODE completion's deferred evaluation, a no-displacement
reader/RMW reservation is already externally distinguished at the final
ModRM pop, one EU state before the RTL's generic `eu_req` rises. That
reservation:

1. suppresses the immediate deferred-evaluation prefetch; and
2. prevents the rejected prefetch from arming the class-5 delayed-resume law.

The second condition is essential. Suppressing only `prefetch_ext` still
allowed `law_arm` to emit the same incorrect CODE fetch two clocks later.

The frozen pre-validation oracle is
`sw/testdata/biu_blackbox/case2-ea1-oracle-v1.json`, SHA-256
`80ed1f5544f2a5ad032d7e713c5940a6434a95aa36a6d1b8143cdff76ceb7bec`.
Fresh alternate-padding validation passed 216 records; its result SHA-256 is
`41bef82d96c5a93354369998789bedda7c05eee7b478def906680f0abadbb93c`.

## RTL mapping

- `v30_eu.sv` exports `eu_rsv_modrm` only for a memory ModRM pop with
  `mod=00` and a reader/RMW class. Stores, LEA, POP-memory, and immediate
  writes are excluded.
- `v30_core.sv` carries that semantic hint to the BIU.
- `v30_biu.sv` includes the hint in `pf_rsv_lead` and prevents `law_arm`
  while that lead veto is active.

The change adds no registered CPU state and requires no savestate-map change.

## Verification

- Assertion-enabled Verilator build: PASS.
- Full zero-wait golden gate: 169,000/169,000 cycles and architectural checks.
- Final original-padding hardware A/B:
  216/216 matches, summary SHA-256
  `2ee489d714358215042b430751ed4914a61a5771bbc690121dae5e3d3fa2dbda`.
- Final alternate-padding hardware A/B:
  216/216 matches, summary SHA-256
  `eb46fb00acd5d08eda3253886bc4fc0e7604edd453d6d3dd18eaa2bfbec938c6`.
- Matrix coverage: waits 0-7 and 15, histories A/B, 4/8 MHz, reader
  destinations AW/DW, RMW, store, LEA, and disp8-read controls.
- Final Quartus build: 0 errors, setup slack +5.139 ns, hold slack +0.254 ns.
- Deployed SOF SHA-256:
  `32b09dcc7728a5432d8fe4fdd58c201b10c2f34ea405fb763de6acff5bb46582`.

This closes one ordinary arbitration case. It does not claim closure of the
complete BIU/EU wait-state model.
