# BIU/EU cases 5 and 6: classic REP final-write close

Date: 2026-07-29

## Case 5: post-final-store prefetch restart

The original `fz6` uniform-w1 residual was the CODE fetch after the final
`REP MOVSB` store.  Silicon started that fetch one clock before RTL.

The chip-only factorial source is:

- `sw/testdata/biu_blackbox/case5-rep-store-chip-v1/summary.json`
- 160 captures: five repetitions, histories A/B, 4/8 MHz.
- REP counts 1/2/3, MOVS/STOS, byte/word, plus equal-length non-REP controls.

Frozen oracle:

- `sw/testdata/biu_blackbox/case5-rep-store-oracle-v1.json`
- SHA-256
  `72f248622917332aa7565aaed355ebee258d0041aa38ad8e0256e07c843784e3`

The generic dormant `store_pf_boost` was not valid: enabling it also
accelerated ordinary opcode-89 stores.  The missing discriminator is a final
classic REP MOVS/STOS store.  The existing savestated `last_was_store` shadow
now retains that semantic tag, and the occupied-5 boost fires only after the
EU leaves `S_BUSW`.

## Case 6: waited REP retirement

The remaining `fz7` discrepancy first appeared as a PUSH timing error, but
external QS reconstruction showed that the first byte after `REP MOVSB` was
already consumed one clock early by silicon.  The push was downstream.

Direct measurement relative to the final string-store T4 established:

- w0 REP close: the existing extra `S_EX` clock is correct.
- waited final REP MOVS/STOS write: silicon omits that extra clock.
- non-REP MOVS/STOS: unchanged.

Chip-only source:

- `sw/testdata/biu_blackbox/case6-rep-retire-chip-v1/summary.json`
- 1,440 retained captures.
- waits 0-7 and 15, histories A/B, 4/8 MHz, five repetitions.
- REP counts 1/2/3, MOVS/STOS byte/word, and non-REP controls.

Frozen oracle:

- `sw/testdata/biu_blackbox/case6-rep-retire-oracle-v1.json`
- SHA-256
  `46f5937fbd9a4c00654db94d41eaa5b69e8ebb32fdc6bb6727bc6c47689afbdd`

The EU reuses its already-savestated `str_wr` bit to record a Tw observed
specifically while the final classic REP write is in `S_BUSW`.  This avoids
the invalid global `waits_seen` history test.  At completion, `str_wr` selects
direct retirement; w0 retains `S_EX`.

## Verification

- Assertion-enabled Verilator build: PASS.
- Full zero-wait golden: 169000/169000.
- Cases 5+6 composed matrix, waits 0-7 and 15: zero mismatches.
- Held-out REPNE/REPC/REPNC and count-4 forms: zero mismatches.
- `fz7` selected-fetch collision sweep, waits 0-7 and 15 under two
  backgrounds: exact bus decision and T1 match.
- Forced Quartus build: 0 errors, setup slack +3.095 ns, hold +0.249 ns.
- Deployed SOF SHA-256:
  `2282c1a93c97d52c1ddc85fb4eac37e1ef7e5df99ac9ac5900428ea93daffb23`.
- Safe flash verified on the first status attempt.
- Original seeds 0-19: 20/20 cycle-clean for random-wmax3, uniform-w1, and
  uniform-w3 on both fabric and TB; writes identical.

## Remaining scope

This does not prove complete BIU/EU closure.  A fresh held-out census over
seeds 20-119 found additional families:

- random-wmax3: 88/100 cycle-clean;
- random-wmax7: 82/100 cycle-clean;
- uniform-w1: 93/100 cycle-clean;
- uniform-w3: 99/100 cycle-clean.

All 400 held-out runs retained byte-identical architectural writes.  The next
selected residual is `fz85` uniform-w3.  Its first contradiction is a branch
flush/redirect boundary: chip fetches CODE `0x56e` once, while RTL fetches it
twice before continuing at `0x570`.  It must be treated as a flush/doomed-fetch
experiment, not folded into the REP close rules.
