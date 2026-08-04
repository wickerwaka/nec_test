# Case 41: uniform-w1/w3 wait closure checkpoint

Date: 2026-07-30

This checkpoint closes the wait-sensitive residuals in the all-extension
`fz320..fz419` corpus.  It is not a claim that the complete BIU/EU transducer
has been discovered.

## Chip-derived rules added

1. A scheduled CODE opportunity whose first due clock collides with an owning
   `S_DHI` displacement-high reservation yields to CODE when the completed
   fetch accumulated exactly three Tw clocks.  The same certificate owns the
   slot at four Tw.  The controlled `fz324` selected-fetch sweep matches for
   waits 0--7 and 15; the independent Case-13 RMW boundary table is unchanged.

2. Aligned immediate INS uses two independent write deadlines.  At offsets
   zero and one, its R.T1-anchored deadline advances one clock when the relevant
   predecessor accumulated at least two Tw:

   - offset zero: the most recent CODE fetch;
   - offset greater than zero: the preceding completed operand read.

   The completion-anchored floor is unchanged and overtakes the early deadline
   at `Tw = len - 1`.  `fz328` (off1/len7) and `fz391` (off0/len5) match selected
   waits 0--7 and 15.  Held-out offsets 2, 3, and 7 retain the ordinary anchor.

The predecessor classes are pin-reconstructible bus-history state.  They are
not program seeds, structural ordinals, or opcode fingerprints.  All four
state bits needed to preserve the live/current duration classes are in
savestate v9.

## Evidence

- `sw/case41_dhi_tw3_factorials.log`
- `sw/case41_ie_anchor_factorials.log`
- `sw/case41_waitclass_controls.log`
- `sw/case41_predclass_bank_320.log`
- `sw/case41_predclass_bank_520.log`
- `sw/case41_predclass_bank_620.log`
- `sw/case41_final_current_uniform_w1.log`
- `sw/case41_final_current_uniform_w3.log`
- `sw/case41_predclass_check_core.log`
- `sw/case41_final_ss_lint.log`

Current gates:

- uniform w1: 100/100 exact;
- uniform w3: 100/100 exact;
- three independent random-wait banks: 300/300 exact;
- architectural/cycle goldens: 169000/169000;
- savestate lint/flop census: 194/194 architectural flops mapped.

Uniform w0 is 99/100 because `fz413` has one PSW-only row (`2 != 6`) with no
bus, T-state, address, or QS divergence.  It is retained as an architectural
flags discrepancy and is not classified as a wait-model residual.

## Remaining acceptance work

This checkpoint covers a finite corpus and the controlled boundaries above.
Complete closure still requires prospective validation with fresh explicit and
random wait vectors, held-out opcode/addressing families, alternate preparation
histories, and the standalone certificate-to-next-action oracle described in
`docs/notes/biu_blackbox_campaign.md`.
