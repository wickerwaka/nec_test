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
