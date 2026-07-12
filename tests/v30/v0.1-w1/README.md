# V30 golden tranche, 1 wait state per bus cycle

Same format and conventions as tests/v30/v0.1 (see its README/metadata);
captured with the harness CFG waits=1 (one Tw inserted per bus cycle via
READY). 200 cases per form, both queue variants, seed base `v30-w1`.

Replay with:

    sw/check_core.py --suite-dir tests/v30/v0.1-w1 --waits 1 \
        --opcodes B8,8B,89,F7.6,EB,E8

Cycle-level laws extracted from this tranche are documented in
docs/facts/biu_model.md ("Wait states, cycle-level laws").
