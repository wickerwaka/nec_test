# V20 SingleStepTests data (local cache)

Gzipped JSON test files from https://github.com/SingleStepTests/v20
(branch `main`, suite v1.0.3, MIT license), used by `sw/pilot_v20.py`
for architectural cross-validation of the real V30 — including the
mission 12 unmasked-flags comparison (docs/facts/undefined_flags.md).

The `.json.gz` files are not committed (re-fetchable); `metadata.json`
(opcode status/flags-mask database) is. To restore the working set:

    cd tests/v30/v20suite
    for f in 00 27 37 B8 D2.4 F6.4 F6.6; do
      curl -sfO "https://raw.githubusercontent.com/SingleStepTests/v20/main/v1_native/$f.json.gz"
    done

Fetched 2026-07-10 (00/37/B8/metadata) and 2026-07-11 (27/D2.4/F6.4/F6.6).
