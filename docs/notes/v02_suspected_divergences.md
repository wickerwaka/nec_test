# v0.2 suspected real divergences (KEEP + escalated) — 2026-07-18

Found during the flat-validity three-way discrimination of the collision re-emission.
These 7 cases fail BOTH memory models (got(flat) == got(mirror) != chip golden) -> NOT
mirror-dependent; a genuine chip-vs-RTL disagreement. Per the escalation rule they are
KEPT in v0.2 (never rerolled away) and flagged as an RTL lead.

All are pin-event (interrupt) cases; the divergence is in the FINAL FLAGS after the
instruction + interrupt entry + handler. Memory-model-independent.

  form     idx   exp_flags got(flat=mirror)  xor(diff bits)
  INT.90   239   f086      f856              08d0  (AC,Z,S,OF)
  INT.9D    44   f407      f0c6              04c1  (CY,Z,S,DF)
  INT.9D    62   f816      fc17              0401  (CY,DF)
  INT.9D   954   f403      f853              0c50  (AC,Z,DF,OF)
  INT.FB   142   f083      f852              08d1  (CY,AC,Z,S,OF)
  INT.FB   368   f857      f806              0051  (CY,AC,Z)
  INT.FB   730   f083      f0c3              0040  (Z)

INT.90 = nop <int>, INT.9D = pop psw <int>, INT.FB = ei <int>, all with various int
delays (d=1..8). Hypothesis: interrupt-boundary flag handling / the exact cycle the INT
is sampled relative to instruction retirement (pin-event timing sensitivity), or a real
interrupt-entry flag-masking bug. v0.1 pin-event goldens (w0) passed 169000/169000, so
these specific seed/delay combinations expose behavior v0.1's cases did not. NEEDS RTL
investigation - reported to coordinator, not fixed here.

## INVESTIGATION UPDATE (2026-07-18) — NOT an RTL execution bug; pin-event capture convention

Probe (before any RTL change): for all 7, the SIM's CYCLE trace matches the chip golden
EXACTLY (cycles_ok=True) - including the INTA position, i.e. the STI/POPF interrupt-
acceptance inhibit-shadow is honored correctly by our RTL. The divergence is ONLY in the
extracted final.flags. So this is NOT the inhibit-shadow hypothesis and NOT a timing bug.

Discrimination against the interrupt-PUSHED PSW (in final.ram, the true architectural
result) normalized (IE/BRK cleared):
  INT.90/239, INT.FB/142,368,730 (4): SIM == pushed_norm (ARCH-CORRECT); golden != it.
    -> CAPTURE ARTIFACT. The golden's final.flags (store-stub PUSH PSW, captured AFTER the
       handler) is contaminated with an architecturally-impossible value (EI/nop+interrupt
       cannot change arithmetic flags). OUR RTL IS CORRECT.
  INT.9D/44,62,954 (3, pop psw <int>): NEITHER SIM nor golden == pushed_norm. The pushed
    PSW itself is un-normalized (e.g. 0xec92, reserved bit12=0). More complex - POP PSW's
    own inhibit-shadow + interrupt + reserved-bit normalization. OPEN: needs deeper analysis;
    could be capture OR a real pop-psw/shadow interaction.

WHY w0 passed pin-event forms: passing cases have final.flags == initial (sparse final.regs
OMITS unchanged flags); the contamination only surfaces when the store-stub capture records
a CHANGED value, which is rare (3/1000/form) and specific. So the w0 gate for pin-event
forms was testing final.flags-when-changed, which its 200 cases/form rarely exercised in a
contaminating way.

PROPOSED (instrument, pre-registered gate to follow): extract pin-event final.flags from the
interrupt-PUSHED PSW (architectural result), not the post-handler store-stub PUSH PSW; re-
validate ALL pin-event goldens in v0.1 + v0.2. Hold for coordinator direction on the INT.9D
sub-case first.

## OPEN QUESTION — 0F31/0F26 same-seed re-capture non-determinism (logged, not chased)
Re-emitting some 0F31 (INS/EXT bit-field) and 0F26 (CMP4S) cases at the SAME seed produced
a DIFFERENT golden than the file (the three-way re-emit's attempt-0 classified them differently
than the file golden had). Emission non-determinism on these ops is itself a lead - possibly
state-dependent / uninitialized-input behavior. Recorded for later; not investigated now.
