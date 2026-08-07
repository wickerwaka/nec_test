# `sw/` artifact inventory (2026-08-07)

The untracked `sw/` tree had grown to 911,802 visible files.  Most of that was
the retained BIU black-box experimental ledger: 908,924 files in 251 raw-data
directories below `sw/testdata/biu_blackbox/`.  The root-level JSON files in
that directory are the frozen oracle/validation set and remain in the
repository.

## Repository-resident set

The cleanup retains and stages:

- 104 frozen BIU oracle and validation JSON files;
- 21 black-box/oracle Python tools, including the transitive imports used by
  `biu_case2_campaign.py` and `timed_ins_replay.py`;
- 65 experiment logs and 10 result JSON files cited by tracked notes or tools;
- this inventory and the narrow ignore rules for regenerated raw ledgers and
  top-level experiment output.

The retained evidence files are intentionally versioned even though their
general output patterns are ignored.

## External archive

The remaining 911,602 files were moved, without deletion, to:

```text
/home/wickerwaka/nec_test_archives/2026-08-07/sw_artifacts/
```

Archive layout:

- `biu_blackbox_raw/`: 251 raw campaign directories, 908,924 files;
- `sw_top_level_scratch/`: 2,660 superseded top-level logs, JSON dumps,
  scripts, stdout captures, and miscellaneous experiment files;
- `sw_other_untracked/`: 18 untracked campaign/control artifacts preserved
  with their original relative paths;
- `SHA256SUMS`: one SHA-256 entry for every archived file.

The `SHA256SUMS` file contains 911,602 entries and has SHA-256:

```text
d584313f537191aaa7c3e7071b0c7bfef2b439969fbe3e25ac2fbec88f4eea48
```

Verify the archive from its root with:

```sh
sha256sum -c --quiet SHA256SUMS
```

The archive is a directory tree on the same filesystem rather than a packed
file, so individual experiments can be inspected or restored without
expanding a multi-gigabyte tarball.
