# V30 golden tranche, 3 wait states per bus cycle

Same format and conventions as tests/v30/v0.1 (see its README/metadata);
captured with the harness CFG waits=3 (three Tw inserted per bus cycle
via READY). 200 cases per form, both queue variants, seed base `v30-w3`.

Replay with:

    sw/check_core.py --suite-dir tests/v30/v0.1-w3 --waits 3 \
        --opcodes B8,8B,89,F7.6,EB,E8

Cycle-level laws extracted from this tranche are documented in
docs/facts/biu_model.md ("Wait states, cycle-level laws").
