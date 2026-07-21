# f0lock_tranche — QUARANTINED (Tw rows UNVERIFIED)

**Do NOT consume these goldens as truth.** 400 socket captures (F0.6C/6D/6E/6F,
100/form, cold + qlen5/6 warm, seed_base f0lock, w0), emitted 2026-07-20 for the
Family-8 (LOCK-strio) investigation.

**QUARANTINE (2026-07-20):** the LOCK-window Tw rows in these goldens are
unverified. A live re-capture of the identical regenerated cases on the current
F8 board shows **NO Tw** (F0.6C idx0 golden Tw @ rows [6,12,18]; live re-capture
0 Tw). Non-locked controls (6C) reproduce exactly, so the board capture is not
globally broken — the discrepancy is LOCK-specific. Whether the golden Tw are a
genuine silicon LOCK-stretch law or a capture artifact (BUSLOCK/WR pin-sharing,
nec_test.sv:328) is an OPEN reproducibility investigation (architect + worker).

Consuming code must treat the tstate column of any Tw row here as suspect until
this note is cleared. The Family-8 fix (commit eae1ecf) matches these goldens in
SIM (400/400) but is BOARD-UNCONFIRMED pending this investigation.
