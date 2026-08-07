#!/usr/bin/env python3
"""Chip-derived two-deadline oracle for the case250 INS families.

The certificate contains only instruction geometry and externally observed
completion facts for the final transfer of each dummy-read pass.  Seed,
structural access ordinal, preparation history, and RTL state are deliberately
not accepted.
"""


DEADLINES = {
    # (form, split, offset, length): ((r1 zero/waited), (r2 zero/waited))
    ("immediate", False, 2, 9): ((63, 64), (31, 32)),
    ("immediate", True, 1, 7): ((54, 55), (25, 26)),
    ("immediate", True, 1, 8): ((57, 58), (27, 28)),
    ("immediate", False, 1, 7): ((54, 55), (25, 26)),
}


def predict_write(certificate):
    key = (certificate["form"], certificate["split"],
           certificate["offset"], certificate["length"])
    if key not in DEADLINES:
        raise ValueError(f"unsupported INS geometry {key}")
    r1_delta, r2_delta = DEADLINES[key]
    decoder = certificate["r1_t4"] + r1_delta[
        certificate["r1_tw"] != 0]
    completion = certificate["r2_t4"] + r2_delta[
        certificate["r2_tw"] != 0]
    return {"action": "MEMW", "t1": max(decoder, completion),
            "decoder_deadline": decoder,
            "completion_deadline": completion}
