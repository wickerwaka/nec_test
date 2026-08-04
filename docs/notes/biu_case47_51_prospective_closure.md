# Cases 47--51: prospective wait-model checkpoint

Date: 2026-07-30

This checkpoint resolves every counterexample found in the first three fresh
all-extension random-wait banks after Case 41.  It is evidence of prospective
generalization, not proof that the complete BIU/EU transducer is closed.

## Chip-derived transitions

1. **Immediate INS retains CODE-wait displacement (fz737).**
   The preceding CODE cycle delays operand `R.T1` after its first Tw, but it
   does not move the independent decoder/write deadline.  The retained state is
   `min(max(CODE_Tw - 1, 0), 5)`, replacing the lossy `CODE_Tw >= 2` bit.
   Across CODE waits 0--7/15 and operand-read waits 0--3/7, the observed rule is
   the maximum of the fixed write deadline and the read-completion floor.

2. **Owning S_DHI has a two/three-Tw CODE-retention band (fz731).**
   When the scheduled CODE due clock coincides with an owning displacement-high
   pop, Tw2 and Tw3 retain CODE; Tw4 returns the slot to the EU reservation.
   The Tw0/Tw1 due clocks fall outside this collision in both preparations.

3. **Single INS/OUTS reservation owns a scheduled CODE collision (fz895).**
   An `S_RSV` single-string-I/O request becomes ready on the next clock.  It
   blocks a coincident scheduled CODE due clock and retains the direct idle-grid
   commit even when the preceding fetch leaves two fresh queue bytes.

4. **CD/CE dly3 reserves a saturated idle IVT slot (fz992).**
   At the four-old-byte certificate, an idle `dly=3` software-interrupt state
   suppresses plain CODE.  The later `dly=1` state arms the existing direct IVT
   commit, preserving both the MEMR decision and exact T1.

5. **Prefix assertion observes overlap accepts (fz824).**
   A REP-string close can accept its successor prefix directly in `S_EX`.
   The CPU rows already matched the chip with the assertion disabled; the
   assertion observer now records that accepted opcode so the following prefix
   target is not falsely reported as a leak.

Every behavioral transition above was checked with two preparation histories
and selected waits 0--7 plus 15.  The fz737 two-dimensional surface additionally
crossed operand-read waits.

## Evidence

- `sw/case47_fz737_2d_factorial.log`
- `sw/case47_fz737_postfix_factorial.log`
- `sw/case47_fz737_history_b.log`
- `sw/case48_fz731_postfix_a.log`
- `sw/case48_fz731_postfix_b.log`
- `sw/case50_fz895_post_a.log`
- `sw/case50_fz895_post_b.log`
- `sw/case51_fz992_final2_a.log`
- `sw/case51_fz992_final2_b.log`
- `sw/case49_fz824_noassert_compare.log`
- `sw/case49_fz824_assert_postfix.log`

Prospective and regression gates:

- fresh `fz720..819`, base wait seed `0x9d2b`: 100/100;
- fresh `fz820..919`, base wait seed `0xc713`: 100/100;
- fresh `fz920..1019`, base wait seed `0x4e91`: 100/100;
- prior random `fz320..419`, base wait seed `0x5a17`: 100/100;
- uniform w1 and w3 `fz320..419`: 100/100 each;
- full architectural/cycle goldens: 169000/169000;
- savestate lint/flop census: 194/194 architectural flops mapped;
- prefix-clear lint: PASS.

## Remaining closure work

The standalone certificate-to-next-action oracle is still not a complete
composition of these rules, and finite random banks cannot prove absence of
another hidden state.  Continue with new explicit/random vectors and held-out
families; any mismatch reopens discovery rather than becoming a seed rule.
