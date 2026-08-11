#!/usr/bin/env python3
"""test_fuzz_classify - offline unit tests for the Phase-2 verdict engine
(task #29). Runnable directly: `python3 sw/test_fuzz_classify.py`.

Ground truth is a real Verilator TB capture of a small soup seed (no board):
  * TB-vs-TB self-compare  -> SUCCESS
  * flip a functional write's data byte on one side -> FUNCTIONAL
  * drop the done marker on one side                -> FUNCTIONAL/done_mismatch
  * inject a Tw row into a w0 CHIP capture          -> QUARANTINE/provenance
Plus diff_rows/wrapper parity, an escalation-STOP dry-run, and a drift smoke.
"""
import copy
import sys
from pathlib import Path

SW = Path(__file__).resolve().parent
sys.path.insert(0, str(SW))
import check_seq                                       # noqa: E402
import fuzz_classify as fc                             # noqa: E402
from gen_soup import gen_soup                          # noqa: E402

FAILS = []


def check(name, cond, extra=""):
    tag = "ok  " if cond else "FAIL"
    if not cond:
        FAILS.append(name)
    print(f"  {tag} {name}{('  ' + extra) if extra else ''}")


def _tb_capture(seed="soup7"):
    """A completed TB capture for a soup seed (deterministic, board-free)."""
    g = gen_soup(seed, evt_pin=None, wild=False)
    image, _meta = check_seq.compose(g)
    rows = check_seq.run_tb(image, 4200, waits=0)
    return g, rows


def _find_write_data_row(rows, window):
    """Row index of a T3/T4 data cycle belonging to a MEMW/IOW txn (a
    functionally-observable write) so a flip there is real functional evidence."""
    for tx in fc.extract_txns(rows):
        if tx["start"] >= window:
            break
        if fc.KIND[tx["kind"]] in ("MEMW", "IOW"):
            for j in range(tx["start"] + 1, tx["end"] + 1):
                if fc._tstate(rows[j]) in (3, 4):
                    return j
    return None


def _find_done_t1(rows, window):
    for tx in fc.extract_txns(rows):
        if tx["start"] >= window:
            break
        if fc.KIND[tx["kind"]] == "IOW" and \
                (tx["addr"] & 0xFFFF) == fc.OUT_PORT_DONE:
            return tx["start"]
    return None


def _tier_domain_falsifier():
    """THE TIER DOMAIN IS A CONTRACT AND THIS IS ITS FALSIFIER.

    `Ctx.tier` is only ever compared for EQUALITY, so an out-of-domain value
    does not raise -- it makes every `ctx.tier == "A"` / `== "B"` branch
    silently False, INCLUDING the arch-dump comparison.  That is exactly what
    `check_fuzz_bank.replay_classify` did until 2026-08-11: it passed the banked
    config literal ("soup"/"raw") straight into `Ctx`, and because `fuzz_bank`
    computes the banked `replay_verdict` by calling that same function, the
    621-seed round-trip compared the defect against itself and read green.
    `docs/notes/cfb_tier_prereg_2026-08-11.md`.

    So the test asserts BOTH halves: the mapping's own domain, and that the
    banked call site actually applies it -- the Ctx `replay_classify` hands to
    `classify` must carry 'A'/'B' when fed a banked-style entry.  Board-free and
    TB-free: the replay's regeneration and TB legs are stubbed, because what is
    under test is the context, not the capture."""
    import check_fuzz_bank as cfb                        # noqa: PLC0415
    import fuzz_campaign as fzc                          # noqa: PLC0415
    import timed_fuzz as tf                              # noqa: PLC0415

    check("ctx_tier maps the config vocabulary onto Ctx.tier",
          fzc.ctx_tier("soup") == "A" and fzc.ctx_tier("raw") == "B")
    for bad in ("A", "B", "Soup", "", None, 0):
        try:
            fzc.ctx_tier(bad)
            raised = False
        except ValueError:
            raised = True
        except Exception:                                # noqa: BLE001
            raised = False
        check(f"ctx_tier RAISES outside its domain ({bad!r})", raised)

    saved = (fzc.derive_case, fzc.build, fzc.compose_case, tf.banked_wvec,
             check_seq.run_tb, fc.classify)
    seen = {}

    def _spy(real, sim, ctx, engine=None):
        seen["tier"] = ctx.tier
        return fc.Verdict(fc.SUCCESS, "", None, 0, 0, 1, False, False, True,
                          True, [], [], None, fc.SIGV, None)
    try:
        fzc.derive_case = lambda cid, k, ov: {}
        fzc.build = lambda cfg: {}
        fzc.compose_case = lambda g, cfg: (b"\x00", {"anchor_linear": 0})
        tf.banked_wvec = lambda e: None
        check_seq.run_tb = lambda *a, **kw: [{}]
        fc.classify = _spy
        for lit, want in (("soup", "A"), ("raw", "B")):
            entry = {"cid": "tst", "k": 1, "ov": {}, "tier": lit,
                     "waits": {"wrand": False, "fixed": 0}, "evt": None,
                     "chip_rows": [{}], "seed": f"tst/{lit}",
                     "cfg_hash": "0" * 12, "image_sha256": "x"}
            seen.clear()
            cfb.replay_classify(entry, None)
            check(f"replay_classify maps the banked {lit!r} tier -> {want!r}",
                  seen.get("tier") == want, f"(got {seen.get('tier')!r})")
    finally:
        (fzc.derive_case, fzc.build, fzc.compose_case, tf.banked_wvec,
         check_seq.run_tb, fc.classify) = saved


def main():
    print("test_fuzz_classify:")
    _tier_domain_falsifier()
    g, rows = _tb_capture()
    print(f"  (TB capture: {len(rows)} rows, {g['n_ins']} ins)")
    ctxA = fc.Ctx(tier="A", waits=0, wrand=False, real_is_chip=False)

    # --- diff_rows / wrapper parity: identical capture -> no diff rows -------
    res = fc.diff_rows(rows, copy.deepcopy(rows))
    check("diff_rows self-compare clean", res.bad == 0 and res.flick == 0,
          f"(bad={res.bad} flick={res.flick} n={res.n})")

    # --- 1. TB-vs-TB self-compare -> SUCCESS --------------------------------
    v = fc.classify(rows, copy.deepcopy(rows), ctxA)
    check("TB-vs-TB -> SUCCESS", v.verdict == fc.SUCCESS,
          f"(got {v.verdict}/{v.sub})")
    check("SUCCESS both done", v.done_real and v.done_sim)

    # --- 2. flip a functional write byte -> FUNCTIONAL ----------------------
    sim = copy.deepcopy(rows)
    window = res.n
    j = _find_write_data_row(sim, window)
    check("found a write-data row to mutate", j is not None, f"(row {j})")
    if j is not None:
        sim[j]["ad_data"] ^= 0x0001
        v = fc.classify(rows, sim, ctxA)
        check("flipped write -> FUNCTIONAL", v.verdict == fc.FUNCTIONAL,
              f"(got {v.verdict}/{v.sub})")
        check("FUNCTIONAL flags func_mismatch", v.func_mismatch)

    # --- 3. drop the done marker on one side -> FUNCTIONAL/done_mismatch -----
    sim = copy.deepcopy(rows)
    dt = _find_done_t1(sim, window)
    check("found the done marker T1", dt is not None, f"(row {dt})")
    if dt is not None:
        sim[dt]["ad_addr"] = (sim[dt]["ad_addr"] & 0xF0000) | 0x00AA  # off 0xFC
        v = fc.classify(rows, sim, ctxA)
        check("dropped done -> FUNCTIONAL", v.verdict == fc.FUNCTIONAL,
              f"(got {v.verdict}/{v.sub})")
        check("done_mismatch subclass", v.sub == "done_mismatch",
              f"(sub={v.sub})")

    # --- 4. Tw in a w0 chip capture -> QUARANTINE/provenance ----------------
    chip = copy.deepcopy(rows)
    for r in chip:                       # present it as a chip capture
        r["t_state"] = r["t"]
        r["rst"] = 0
    inj = dict(chip[200])
    inj["t_state"] = 4                    # a phantom Tw
    inj["t"] = 4
    chip.insert(200, inj)
    ctx_chip = fc.Ctx(tier="A", waits=0, wrand=False, real_is_chip=True)
    v = fc.classify(chip, copy.deepcopy(rows), ctx_chip)
    check("Tw@w0-chip -> QUARANTINE", v.verdict == fc.QUARANTINE,
          f"(got {v.verdict}/{v.sub})")
    check("provenance alarm tw_in_w0_chip", "tw_in_w0_chip" in v.alarms,
          f"(alarms={v.alarms})")

    # --- 5. done_data provenance: SHARED corruption vs ONE-SIDED junk -------
    # (task #29 P7, mc1 k=9192). A corrupt store stub is shared -> both legs
    # emit the same non-sentinel done data -> QUARANTINE. A one-sided junk done
    # write (a fall-through program that wanders into port 0xFC on one leg only)
    # is a functional divergence, NOT a capture-integrity STOP.
    def _set_done_data(rs, junk):
        dt = _find_done_t1(rs, len(rs))
        tx = next(t for t in fc.extract_txns(rs) if t["start"] == dt)
        for j in range(tx["start"], tx["end"] + 1):
            if fc._tstate(rs[j]) in (2, 3, 4):
                rs[j]["ad_data"] = junk
    # shared: both legs carry junk done (no escape) -> QUARANTINE
    r_shared = copy.deepcopy(rows)
    s_shared = copy.deepcopy(rows)
    _set_done_data(r_shared, 0x00C5)
    _set_done_data(s_shared, 0x00C5)
    v = fc.classify(r_shared, s_shared, fc.Ctx(tier="A", waits=1,
                                               real_is_chip=True))
    check("shared corrupt done -> QUARANTINE",
          v.verdict == fc.QUARANTINE and any("done_data_both" in a
                                             for a in v.alarms),
          f"(got {v.verdict}/{v.sub})")
    # one-sided: only the chip leg carries junk done -> NOT a provenance STOP
    r_one = copy.deepcopy(rows)
    _set_done_data(r_one, 0x00C5)
    v = fc.classify(r_one, copy.deepcopy(rows), fc.Ctx(tier="A", waits=1,
                                                       real_is_chip=True))
    check("one-sided junk done -> NOT provenance QUARANTINE",
          not any("done_data" in a for a in v.alarms), f"(alarms={v.alarms})")

    # --- 5b. AMENDMENT A-10: D-2's sentinel predicate reaches this clause ----
    # `docs/notes/fz2_corpus_prereg_2026-08-08.md` §27.  A done marker is an
    # `OUT 0xFC` carrying `0xF00D`; a non-sentinel one is not a done marker and
    # raises no done-related alarm.  Read literally that makes the clause
    # VACUOUS, so the predicate decides EXISTENCE and the shared-vs-one-sided
    # discriminator is untouched.  Five things are asserted together, because
    # an alarm that can no longer catch anything is a deletion:
    #   (a) the 604011 shape -- junk marker inside the window, the harness's
    #       real sentinel marker LATER IN THE CAPTURE -- no longer alarms;
    #   (b) and it SCORES, with the arch dumps compared;
    #   (c) a shared corrupt store with NO sentinel anywhere still QUARANTINEs
    #       and still STOPs                       (checks 5/A-1(c) above);
    #   (d) the shared-vs-one-sided discriminator is still what refuses a
    #       ONE-SIDED junk done when NO sentinel exists on either leg -- i.e.
    #       the suppressing predicate is not the only thing left standing;
    #   (e) a capture with no marker of any kind still reads as it should.
    def _append_txn(rs, src_start, src_end, data, addr=None):
        """Copy a transaction's rows onto the end of a capture, with new data
        (and optionally a new address) -- a second pass of the image."""
        for j in range(src_start, src_end + 1):
            r = copy.deepcopy(rs[j])
            if fc._tstate(r) in (2, 3, 4):
                r["ad_data"] = data
            if addr is not None and fc._tstate(r) == 1:
                r["ad_addr"] = (r["ad_addr"] & 0xF0000) | addr
            rs.append(r)

    dt0 = _find_done_t1(rows, len(rows))
    tx0 = next(t for t in fc.extract_txns(rows) if t["start"] == dt0)
    # (a) the 604011 shape, synthesised so a reviewer needs no board capture:
    #     both legs write junk to 0xFC at the terminator, and the harness's own
    #     sentinel marker appears later in the capture (the image re-ran).
    r_604, s_604 = copy.deepcopy(rows), copy.deepcopy(rows)
    _set_done_data(r_604, 0x179E)
    _set_done_data(s_604, 0x179E)
    for rs in (r_604, s_604):
        _append_txn(rs, tx0["start"], tx0["end"], fc.DONE_SENTINEL)
    v604 = fc.classify(r_604, s_604, fc.Ctx(tier="A", waits=1,
                                            real_is_chip=True))
    check("A-10(a): junk marker + a LATER sentinel -> NO done alarm",
          not any("done_data" in a for a in v604.alarms),
          f"(alarms={v604.alarms})")
    check("A-10(b): and the seed SCORES (not QUARANTINE)",
          v604.verdict != fc.QUARANTINE, f"(got {v604.verdict}/{v604.sub})")
    check("A-10(b): with the sentinel-anchored arch dump readable",
          fc.arch_dump(r_604, len(r_604), sentinel_only=True) is not None
          and (fc.arch_dump(r_604, len(r_604), sentinel_only=True)
               == fc.arch_dump(s_604, len(s_604), sentinel_only=True)))
    esc604 = fc.EscalationPolicy()
    check("A-10(a): and does NOT stop the campaign",
          not any(a == ("STOP", "provenance_alarm")
                  for a in esc604.consult(v604, ctxA)),
          "")
    # (d) ONE-SIDED junk with NO sentinel anywhere: the sentinel predicate does
    #     NOT suppress here (neither leg has a sentinel), so the ORIGINAL
    #     shared-vs-one-sided discriminator is what must refuse the alarm.
    r_1s, s_1s = copy.deepcopy(rows), copy.deepcopy(rows)
    _set_done_data(r_1s, 0x00C5)
    dt_s = _find_done_t1(s_1s, len(s_1s))
    s_1s[dt_s]["ad_addr"] = (s_1s[dt_s]["ad_addr"] & 0xF0000) | 0x00AA
    check("A-10(d): the one-sided fixture has NO sentinel on either leg",
          not fc.has_done(r_1s, len(r_1s), sentinel_only=True)[0]
          and not fc.has_done(s_1s, len(s_1s), sentinel_only=True)[0])
    v1s = fc.classify(r_1s, s_1s, fc.Ctx(tier="A", waits=1,
                                         real_is_chip=True))
    check("A-10(d): one-sided junk, no sentinel -> NO done alarm "
          "(the discriminator, not the predicate)",
          not any("done_data" in a for a in v1s.alarms),
          f"(alarms={v1s.alarms})")
    # and the SHARED form of that same fixture must still fire, which is what
    # makes (d) a discriminator test rather than a second suppression.
    r_sh2, s_sh2 = copy.deepcopy(rows), copy.deepcopy(rows)
    _set_done_data(r_sh2, 0x00C5)
    _set_done_data(s_sh2, 0x00C5)
    check("A-10(c): the shared fixture has NO sentinel on either leg",
          not fc.has_done(r_sh2, len(r_sh2), sentinel_only=True)[0]
          and not fc.has_done(s_sh2, len(s_sh2), sentinel_only=True)[0])
    vsh2 = fc.classify(r_sh2, s_sh2, fc.Ctx(tier="A", waits=1,
                                            real_is_chip=True))
    check("A-10(c): shared corrupt done, no sentinel -> STILL QUARANTINE",
          vsh2.verdict == fc.QUARANTINE
          and any("done_data_both" in a for a in vsh2.alarms),
          f"(got {vsh2.verdict}/{vsh2.sub})")
    escsh2 = fc.EscalationPolicy()
    check("A-10(c): and STILL STOPs the campaign",
          any(a == ("STOP", "provenance_alarm")
              for a in escsh2.consult(vsh2, ctxA)), "")
    # (e) a capture carrying NO write to the done port at all: no done alarm,
    #     and Tier A reads it as `runaway_both` -- the pre-existing path.
    r_no, s_no = copy.deepcopy(rows), copy.deepcopy(rows)
    for rs in (r_no, s_no):
        d = _find_done_t1(rs, len(rs))
        rs[d]["ad_addr"] = (rs[d]["ad_addr"] & 0xF0000) | 0x00AA
    vno = fc.classify(r_no, s_no, ctxA)
    check("A-10(e): no marker of any kind -> NO done alarm",
          not any("done_data" in a for a in vno.alarms),
          f"(alarms={vno.alarms})")
    check("A-10(e): and Tier A reads it as runaway_both",
          vno.sub == "runaway_both", f"(sub={vno.sub})")

    # --- 6. AMENDMENT A-1: the escape is a DIAGNOSTIC, and only the escape ---
    # `docs/notes/fz2_corpus_prereg_2026-08-08.md` §11.  The census halted on
    # its second seed (fz2c/400001) on an escape that fired at the SAME row and
    # the SAME address on BOTH legs with the seed otherwise clean, so the shape
    # reproduced here is that one: one escaping CODE T1, mirrored into both
    # legs.  Three things are asserted together, because a demotion nobody can
    # show still stops is not a safe stop condition:
    #   (a) the escape is still MEASURED   -- `escaped_code_region` finds it;
    #   (b) it raises NO alarm and NO STOP -- the seed scores;
    #   (c) another provenance alarm on the same rows still QUARANTINEs AND
    #       still STOPs -- the escalation path itself is intact.
    esc_row = dict(rows[0])
    esc_row.update({"t": 1, "t_state": 1, "bs_early": 4, "bs_late": 4,
                    "ad_addr": 0x0123B, "ad_data": 0x00CC, "rst": 0})
    r_esc = copy.deepcopy(rows)
    r_esc.insert(400, dict(esc_row))
    s_esc = copy.deepcopy(rows)
    s_esc.insert(400, dict(esc_row))
    found = fc.escaped_code_region(r_esc, len(r_esc))
    check("A-1(a): the escape is still MEASURED",
          found is not None and found[1] == 0x123B, f"({found})")
    v_esc = fc.classify(r_esc, s_esc, ctxA)
    check("A-1(b): escape raises NO provenance alarm",
          not any("escaped" in a for a in v_esc.alarms), f"({v_esc.alarms})")
    check("A-1(b): the escaping seed SCORES (not QUARANTINE)",
          v_esc.verdict != fc.QUARANTINE, f"(got {v_esc.verdict}/{v_esc.sub})")
    esc3 = fc.EscalationPolicy()
    acts3 = esc3.consult(v_esc, ctxA)
    check("A-1(b): and does NOT stop the campaign",
          not any(a == ("STOP", "provenance_alarm") for a in acts3),
          f"({acts3})")
    # (c) the OTHER alarms are untouched: same rows, one phantom Tw, and the
    # verdict AND the escalation must both still fire.
    esc4 = fc.EscalationPolicy()
    v_tw = fc.classify(chip, copy.deepcopy(rows), ctx_chip)
    acts4 = esc4.consult(v_tw, ctx_chip)
    check("A-1(c): a NON-demoted alarm still QUARANTINEs",
          v_tw.verdict == fc.QUARANTINE and "tw_in_w0_chip" in v_tw.alarms,
          f"(got {v_tw.verdict}/{v_tw.sub})")
    check("A-1(c): and still STOPs the campaign",
          any(a == ("STOP", "provenance_alarm") for a in acts4), f"({acts4})")
    esc5 = fc.EscalationPolicy()
    acts5 = esc5.consult(fc.classify(r_shared, s_shared,
                                     fc.Ctx(tier="A", waits=1,
                                            real_is_chip=True)),
                         fc.Ctx(tier="A", waits=1, real_is_chip=True))
    check("A-1(c): the shared corrupt-store alarm still STOPs",
          any(a == ("STOP", "provenance_alarm") for a in acts5), f"({acts5})")

    # --- escalation STOP dry-run: a w0 un-ruled FUNCTIONAL must STOP ---------
    esc = fc.EscalationPolicy()
    sim = copy.deepcopy(rows)
    j = _find_write_data_row(sim, window)
    sim[j]["ad_data"] ^= 0x0002
    vf = fc.classify(rows, sim, ctxA)
    acts = esc.consult(vf, ctxA)
    check("escalation STOPs on w0 functional",
          any(a == ("STOP", "w0_functional") for a in acts), f"({acts})")

    # a clean SUCCESS must NOT stop
    esc2 = fc.EscalationPolicy()
    acts2 = esc2.consult(fc.classify(rows, copy.deepcopy(rows), ctxA), ctxA)
    check("escalation quiet on SUCCESS", acts2 == [], f"({acts2})")

    # --- drift smoke: a waited divergent pair returns a drift dict -----------
    sim = copy.deepcopy(rows)
    sim.insert(50, copy.deepcopy(sim[50]))     # shove a 1-cycle slip
    ctxw = fc.Ctx(tier="A", waits=1, wrand=False, with_drift=True)
    vw = fc.classify(rows, sim, ctxw)
    check("drift metrics computed for waited seed",
          vw.drift is not None and "slips" in vw.drift,
          f"(bad={vw.bad_rows})")

    print(f"\n{'PASS' if not FAILS else 'FAIL'}: "
          f"{len(FAILS)} failure(s){(': ' + ', '.join(FAILS)) if FAILS else ''}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
