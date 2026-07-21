# f0lock_tranche — CLEAN re-capture (2026-07-20)

400 socket captures (F0.6C/6D/6E/6F, 100/form, cold + qlen5/6 warm, seed_base
f0lock, w0), re-captured 2026-07-20 on a wait-rig-clean board with the mechanized
guard (v30run ServeRunner force-cleans R_WRAND + replay at connect).

**History:** the ORIGINAL 16:10 capture was TAINTED by a stale R_WRAND left
enabled by a prior process (F7-side leg-b wrand fuzz), minting phantom Tw rows
(+3 cold / +1 warm) inside the LOCK windows. Those were mis-read as a "LOCK-window
bus-cycle stretch law" (Family 8); the fix (commit eae1ecf) was REVERTED once the
artifact was identified. This clean re-capture has **0 Tw** and the post-revert
RTL (F5a/F7 arms only) passes it **400/400** (cyc+arch) — F0.6C-6F have no LOCK
timing divergence; the string-I/O ordering was already correct.

Standing rule: a Tw in a waits=0 golden is a PROVENANCE ALARM, not a law to fit.
