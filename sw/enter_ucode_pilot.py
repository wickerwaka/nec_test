#!/usr/bin/env python3
"""ENTER/PREPARE (C8) microcode-march pilot (2026-08-01) — offline only.

Second refit pilot after sw/ins_ucode_pilot.py: tests whether the ROM's
ENTER micro-sequence (docs/V20UC.TXT rows 0260-0273) predicts the retained
C8 goldens from GLOBAL constants, replacing the S_PREP_* FSM states, fitted
dly values, and the prep_acc/w4skip patch flags in v30_eu.sv.

March model (constants frozen on golden cases [0:100], validated [100:500]):

  bp_req   = disphi_pop + 3            # rows 0261-0262: issue BP push
  lvl_pop  = disphi_pop + 4            # row 0264 (w0; F-interlock not binding)
  walk_req = lvl_pop + 9  (nest>=2, first copy MEMR, row 026B)
           = lvl_pop + 10 (nest==1, frame MEMW, row 0270)
  chain    : every subsequent stack txn T1 = prev stack txn T4 + 1
             (copy read/push pairs, split halves, frame push - no cases)
  retire   : next F pop = last stack T4 + 1   (nest >= 1)
             max(lvl_pop + 5, bp_push.T4 + 1) (nest == 0)

  grant(req, busfree): bus slots exist at busfree+1 and busfree+3; after
  that the bus is free-running and T1 = req exactly.
      T1 = busfree+1 if req <= busfree+1
           busfree+3 if req <= busfree+3
           req       otherwise

The waited tranche (tests/v30/enter_nesting/goldens_waited.json.gz) is
digest-level; the march model's structural claims validated there:
  - MEMW count == nest+1 at every wait (the F-interlock at ROM row 0263:
    the level pop at 0264 cannot precede BP-push acceptance - the property
    whose absence in the FSM was the task #31 PUSH-BP-drop bug)
  - every transaction duration == 3 + wait (uniform-wait records)

Usage:  python3 sw/enter_ucode_pilot.py   (from repo root; offline only)
"""
import gzip
import json
import sys
from collections import Counter

K = dict(bp_req=3, lvl=4, rq_rd=9, rq_wr=10, chain=1, ret0=5, ret=1)


def grant(req, busfree):
    if busfree is None:
        return req
    if req <= busfree + 1:
        return busfree + 1
    if req <= busfree + 3:
        return busfree + 3
    return req


def txns(case):
    out = []
    for i, r in enumerate(case['cycles']):
        if r[8] == 'T1' and r[7] != 'PASV':
            out.append(dict(kind=r[7], t1=i, addr=r[1], t4=None))
        if r[8] == 'T4' and out:
            for t in reversed(out):
                if t['t4'] is None and t['t1'] < i:
                    t['t4'] = i
                    break
    return out


def busfree_before(T, t1):
    prior = [t['t4'] for t in T if t['t4'] is not None and t['t4'] < t1]
    return max(prior) if prior else None


def check(case, cnt):
    nest = case['bytes'][3]
    sp = case['initial']['regs']['sp']
    T = txns(case)
    pops = [(i, r[10], r[9]) for i, r in enumerate(case['cycles'])
            if r[9] in 'FS']
    if len(pops) < 4 or pops[0][1] != 0xC8:
        cnt['skip'] += 1
        return
    disphi, lvl = pops[2][0], pops[3][0]
    stack = [t for t in T if t['kind'] != 'CODE']
    nbp = 2 if (sp - 2) & 1 else 1
    bpp = stack[:nbp]

    # BP push (first half)
    p = grant(disphi + K['bp_req'], busfree_before(T, bpp[0]['t1']))
    cnt['bp'][p - bpp[0]['t1']] += 1
    # split second half chains
    if nbp == 2:
        cnt['chain'][bpp[0]['t4'] + K['chain'] - bpp[1]['t1']] += 1
    # level pop
    cnt['lvl'][disphi + K['lvl'] - lvl] += 1
    # walk
    walk = stack[nbp:]
    if nest >= 1:
        rq = K['rq_rd'] if nest >= 2 else K['rq_wr']
        p = grant(lvl + rq, busfree_before(T, walk[0]['t1']))
        cnt['w0'][p - walk[0]['t1']] += 1
        for prev, t in zip(walk, walk[1:]):
            cnt['chain'][prev['t4'] + K['chain'] - t['t1']] += 1
        pend = walk[-1]['t4'] + K['ret']
    else:
        pend = max(lvl + K['ret0'], bpp[-1]['t4'] + K['ret'])
    cnt['end'][pend - (len(case['cycles']) - 1)] += 1


def waited_checks():
    d = json.load(gzip.open('tests/v30/enter_nesting/goldens_waited.json.gz'))
    push_ok = dur_ok = dur_n = 0
    for g in d:
        nest = g['nest']
        # stack-region pushes only (char_enter.walk_of convention)
        memw = [t for t in g['full']
                if t[0] == 'MEMW' and 0x2000 <= t[1] <= 0x3FFF]
        push_ok += (len(memw) == nest + 1)
        if isinstance(g.get('waits'), int):      # uniform-wait records
            for t in g['full']:
                dur_n += 1
                dur_ok += (t[3] == 3 + g['waits'])
    return push_ok, len(d), dur_ok, dur_n


def main():
    d = json.load(gzip.open('tests/v30/v0.1/C8.json.gz'))
    fail = 0
    for name, cs in (('FIT[0:100]', d[:100]), ('VALIDATE[100:500]', d[100:])):
        cnt = dict(bp=Counter(), lvl=Counter(), w0=Counter(),
                   chain=Counter(), end=Counter(), skip=0)
        for c in cs:
            check(c, cnt)
        print(f'== {name} (skipped {cnt["skip"]}) ==')
        for k in ('bp', 'lvl', 'w0', 'chain', 'end'):
            h = dict(sorted(cnt[k].items()))
            n = sum(cnt[k].values())
            print(f'  {k:6s} exact {cnt[k][0]}/{n}  {h}')
            if cnt[k][0] != n:
                fail = 1
    po, pn, do, dn = waited_checks()
    print(f'== WAITED digests ==')
    print(f'  push count nest+1: {po}/{pn}')
    print(f'  txn duration 3+w:  {do}/{dn}')
    if po != pn:
        fail = 1
    sys.exit(fail)


if __name__ == '__main__':
    main()
