# V30 BIU ledger-cell-2 prospective closure

## Verdict

PASS.  The targeted common-key population is closed prospectively by the
controlled consumer-byte role (`modrm` or `disp8`).  The fresh held-out
validation has zero unseen keys and zero action, exact-T1, address/width, or
QS-sequence mismatches.

This is a closure claim for mismatch-ledger cell 2 only.  It is not a claim
that the complete BIU state machine or the frozen v1 oracle is closed.

## Original-arm reproduction

`sw/testdata/biu_blackbox/case2-original-arms.json` was reconstructed directly
from the retained raw captures.  Both arms have the externally reconstructed
key

```text
[2, 0, "IDLE", 0, "read", "CODE", -3, "S", 0, 3]
```

The original `read_mov` ModRM arm predicts/observes CODE at `+2`, address
`selected+2`, width 16, with no intervening QS.  Its packed-raw SHA-256 is
`4f5e4483c450e62034996567f1850e12b16a8ba691f3fee2e00289a0bd5f634b`.

The original `held_read_disp8` arm observes MEMR at `+3`, address `0x2000`,
width 16, with no intervening QS.  Its packed-raw SHA-256 is
`699529437503b564e94eca84f3ac26d1c4f3aa093359a07583daf7e198c7a4c1`.

## Prospective rule

The rule was frozen before fresh factorial capture in
`sw/testdata/biu_blackbox/case2-micro-oracle-v1.json`, SHA-256
`6055084cf83da1cdec619611b1ad85640fb42067897eb53253e3fead3fb3d201`.

For the registered common key:

- `consumer_byte_role=modrm` predicts CODE, T1 `+2`, selected address `+2`,
  width 16, and no intervening QS.
- `consumer_byte_role=disp8` predicts MEMR, T1 `+3`, address `0x2000`, width
  16, and no intervening QS.

The rule contains no form, padding, seed, structural ordinal, preparation
history, exact history fingerprint, classifier, or post-result exclusion.
`sw/biu_case2_predict.py` is the standalone application of this frozen rule to
one state certificate and controlled byte-role event.

## Factorial experiment

The discovery forms were `MOV AW,[BW]` (`8b07`) and its disp8-zero equivalent
(`8b4700`).  Fresh validation held out the equivalent DW destination forms
`MOV DW,[BW]` (`8b17`) and `MOV DW,[BW+0]` (`8b5700`).

Each population used two paired padding controls.  Pairing ModRM pads 3 and 9
with disp8 pads 2 and 8 aligns the challenged final-byte address and total
stream-consumption position.  Every setup crossed waits 0 through 7 and 15,
preparation histories A and B, 4 MHz and 8 MHz, and five reset-per-probe
repetitions.  History B adds one Tw to a preparation CODE access; the selected
collision access is unchanged.

The complete registered pin-derived certificate (ordered queue bytes/tags,
depth, next-fetch address/parity, current bus transaction/T-state,
instruction-byte consumption, current QS, controlled request, predecessor,
and selected completion offset) matched exactly across the two byte roles.
It also remained equal across unrelated padding after address translation and
queue-head modulo-six normalization:

- Discovery: 40 exact role-pair groups, zero certificate differences.
- Validation: 40 exact role-pair groups, zero certificate differences.

## Results and retained evidence

`sw/testdata/biu_blackbox/case2-prospective-20260729-r2/manifest.json`
(SHA-256
`7f7599a2548e9654ebe65a1e9aa59be0a3799e1a2e8fa8a27429f02d57e3a38f`)
records:

- Discovery: 80 targeted records, zero unseen and zero mismatches.
- Fresh validation: 80 targeted records, zero unseen and zero mismatches.
- Full control matrix: 1,440 records.

`sw/testdata/biu_blackbox/case2-prospective-20260729-r2/audit.json`
(SHA-256
`b46f1dea06df00033fd1ce274a4c5dbae37a0e05a71bc9227ef29f2aa4c3444b`)
independently inventories all 1,520 raw captures and their packed-raw and
observable SHA-256 hashes.  It proves:

- Exactly 1,440 requested factorial cells were captured once each.
- All five repetitions have identical observable hashes in every cell.
- Requested and observed Tw counts agree.
- All 144 A/B preparation-history pairs are observably distinct.
- Every capture contains 4,096 clocks and ends idle, with no overflow.
- Both prospective outcome gates and both certificate-equality gates pass.

The two frozen v1 artifacts remained unchanged before and after capture:

- `chip-oracle-v1.json`:
  `23c0313ddf67510b12b0de1b513ef6e9f6a3fec9482b61b90110a98c0f3fc9be`
- `chip-oracle-v1.validation.json`:
  `cdc551359d4aa4ad0222be754aa7bd883e9420409d86c66b2dde92a9ad70449d`

No CPU RTL or Stage C file was changed.

## Exact commands

```sh
python3 sw/biu_case2_micro_oracle.py \
  sw/testdata/biu_blackbox/case2-micro-oracle-v1.json

python3 sw/biu_case2_campaign.py \
  sw/testdata/biu_blackbox/case2-micro-oracle-v1.json \
  sw/testdata/biu_blackbox/case2-prospective-20260729-r2 \
  --host root@mister-nec --live

python3 sw/biu_case2_audit.py \
  sw/testdata/biu_blackbox/case2-micro-oracle-v1.json \
  sw/testdata/biu_blackbox/case2-prospective-20260729-r2
```
