# BIU/EU black-box cases 7 and 8

Date: 2026-07-29

These cases were discovered from socketed-chip pins with exact READY-vector
interventions.  Program seed and RTL internals were used only after the chip
decision tables were frozen.

## Case 7: class-5 resume versus final Jcc reservation

Fixture: `fz85`, taken Jcc at `00569`, selected CODE access 97.

Chip result:

- waits 0-2 allow the sequential target fetch before the redirect;
- waits 3-4 suppress it at the final `S_JWAIT` reservation;
- waits 5-7 and 15 also suppress it, with the measured redirect phase in the
  frozen table;
- four discovery and four held-out condition codes agree;
- histories A/B, 4/8 MHz, and five repetitions agree.

Artifacts:

- `sw/biu_case7_jwait_law_hw.py`
- `sw/biu_case7_jwait_law_oracle_v1.py`
- `sw/biu_case7_jwait_law_validate.py`
- `sw/testdata/biu_blackbox/case7-jwait-law-chip-v1/`
- `sw/testdata/biu_blackbox/case7-jwait-law-heldout-v1/`
- frozen oracle SHA-256
  `39efbad201de83e6b8182ce24a5c037b9d1ca8246cdb64eb19c5d6739c08f507`

RTL rule:

- EU exports the semantic final-Jcc reservation,
  `eu_law_hard_rsv = S_JWAIT && dly==1 && op_jcc`;
- a scheduled class-5 CODE resume yields only at that final clock;
- an outstanding/arming schedule converts to the existing savestated
  `flush_hold` direct redirect path after the flush.

Verification:

- discovery plus held-out RTL oracle: 144/144;
- held-out chip captures: 720/720 repeatable and table-identical;
- `fz85`, `fz86`, and `fz116`: exact bus sequence and clock alignment;
- full regression: 169000/169000;
- Quartus: 0 errors, setup +5.002 ns, hold +0.266 ns;
- deployed SOF SHA-256
  `069777b401397a38f1e26b67b25b5ce45bcc2fd03ee5952599909e31448f1b3e`.

Expanded 100-program census, before -> after case 7:

- random max-3: 88/100 -> 93/100 cycle-clean;
- random max-7: 82/100 -> 83/100;
- uniform wait-1: 93/100 -> 95/100;
- uniform wait-3: 99/100 -> 100/100;
- all 400 writes remained identical.

## Case 8: loop late reservation

Fixture: `fz62`, taken `LOOP`/`JCXZ` at `0052d`, selected CODE access 58.

Holding every other access at one Tw and changing only access 58:

- selected wait 0: one doomed `CODE 00532`, exact;
- selected wait 1: chip retains that doomed fetch, old RTL suppresses it;
- selected wait 2: both suppress it;
- waits 3-7 and 15: both suppress it with the measured redirect phase.

The E2 and E3 forms are behaviorally identical.  E0 has the same boundary
shifted by its longer decoder schedule.  E1 is not taken in this fixture.
Histories A/B agree.

Artifacts:

- `sw/biu_case8_loop_collision_hw.py`
- `sw/biu_case8_loop_collision_oracle_v1.py`
- `sw/biu_case8_loop_collision_validate.py`
- `sw/biu_case8_loop_shift_validate.py`
- `sw/testdata/biu_blackbox/case8-loop-collision-chip-v1/`
- frozen oracle SHA-256
  `adce3e75cd8512e4ed6929347231f4ce4eef239fd664a92b1ca7cc9f87c88aba`

RTL rule:

- EU exports `eu_loop_late_yield` only for taken-loop `S_JWAIT,dly==3`;
- BIU admits that semantic class to its existing age-zero `eval_ext`
  late-reservation yield;
- zero-wait is unaffected because `eval_ext` is absent;
- `dly<=2` remains a hard reservation.

Verification:

- frozen E2/E3 oracle: 36/36;
- pre-RTL shifted E0-E3 pilot: 72/72;
- `fz62` uniform wait-1: exact bus sequence and clock alignment;
- full regression: 169000/169000;
- Quartus: 0 errors, setup +4.069 ns, hold +0.252 ns;
- deployed SOF SHA-256
  `8b4d93b66c49a77e87c6d286ae7e02ff4d169adc058e3861a4ce78c8053e0ebc`.

Expanded 100-program census, after case 7 -> after case 8:

- random max-3: 93/100 -> 94/100 cycle-clean;
- random max-7: 83/100 -> 84/100;
- uniform wait-1: 95/100 -> 96/100;
- uniform wait-3 remains 100/100;
- all 400 writes remained identical.

## Remaining scope

Neither case proves complete BIU/EU closure.  After case 8 the remaining
uniform wait-1 failures are `fz70`, `fz83`, `fz84`, and `fz103`.  Random wait
residuals also remain and must be factorized prospectively rather than
converted into program-specific rules.
