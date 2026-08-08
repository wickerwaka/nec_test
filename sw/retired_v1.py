#!/usr/bin/env python3
"""retired_v1 - one place that says "this tool served the v1 fuzz image and is
retired", so that no such tool dies with a confusing TypeError instead.

WHY THIS EXISTS.  fuzz-v2 tasks T1/T2 removed `compose(stub_linear=)`, the
`meta["stub_linear"]` / `meta["psw_push_addr"]` channels and the v1 code
anchor.  About a dozen tools existed only to interrogate the store-stub image
or the fuzz corpus that was DISCARDED BY USER DECISION.  Left alone they fail
with

    TypeError: compose() got an unexpected keyword argument 'stub_linear'

three frames below the thing the reader actually wants to know, which is that
nobody is expected to run this tool any more.  `accepted-and-ignored` is the
failure mode this repo tracks by name; `dies-confusingly` is its neighbour.
A retirement is a DECISION and it should read as one.

WHAT RETIREMENT IS AND IS NOT.  The file is not deleted, its git history is
intact, and the reasoning is recorded at the call site.  Retirement here means
exactly: *no standing or archived gate runs this, its campaign is closed, and
the corpus it interrogated is gone.*  If that turns out to be wrong for a
given tool the fix is to port it and delete its stamp -- which is a two-line
change, deliberately.
"""


class RetiredTool(RuntimeError):
    """Raised by a tool that fuzz-v2 T12 retired rather than ported."""


def retire(tool, campaign, reason, ported_alternative=None):
    """Raise, naming the decision.  Call it at module scope or first thing in
    main() -- whichever the tool's shape makes unavoidable."""
    msg = [
        f"{tool} IS RETIRED (fuzz-v2 T12, 2026-08-08).",
        f"  campaign : {campaign}",
        f"  reason   : {reason}",
        "  what changed: T1/T2 removed the v1 store-stub image "
        "(`compose(stub_linear=)`, `meta['stub_linear']`, "
        "`meta['psw_push_addr']`) and moved the code anchor to "
        "[0x8000,0xC000).  This tool reads mechanisms that no longer exist.",
        "  the old fuzz corpus is DISCARDED BY USER DECISION; nothing gates "
        "on it.",
    ]
    if ported_alternative:
        msg.append(f"  use instead: {ported_alternative}")
    msg.append(
        "  this is a DECISION, not a breakage: if you need this tool, port it "
        "and delete the retire() call -- do not re-add stub_linear.")
    raise RetiredTool("\n".join(msg))
