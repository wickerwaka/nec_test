#!/usr/bin/env python3
"""INS microcode-EU offline pilot (2026-08-01).

Tests whether the V20/V30 EU micro-sequencer mechanism (docs/V20UC.TXT,
docs/notes/microcode_analysis.md) predicts the Case 250 INS factorial planes
from a handful of GLOBAL constants, replacing the per-(off,len) rail
constants currently in hdl/rtl/core/v30_eu.sv.

Mechanism model (single sequential micro-march, ROM rows 0318-0347):
  - F/OPR interlock: read data available to the EU at T4, one clock later
    when the completing read had wait states (the campaign-3 eval law):
        e(x) = 1 if x.tw > 0 else 0
  - COUNT-driven shift loops make every geometry dependence linear in
    S = off + len (bit offset + field length) or in off alone.

Laws (constants frozen from fz12302 + fz12466, validated on fz12547 +
fz12569 untouched):

  W1.T1  = max(R1.T4 + e(R1) + 3*S + 30,          # R1-anchored march
               R2.T4 + e(R2) + 2*S + 9)           # R2 F-stall + tail loop
  W2.T1  = W1.T4 + 1 + e(W1)                      # split high-half chain
  R2req  = R1.T4 + e(R1) + 18 + off               # off-count loop -> issue
  R2.T1  = max(R2req, busfree + 2)                # BIU grant on 2-clock grid

R1/R2 mean the FINAL (high) halves for split accesses; the EU-issued request
event for a split R2 is its LOW half.  The +/-1 residue on R2.T1 is the bus
grid-parity term (biu_rebuild_design.md B1/§4), i.e. BIU-layer, not EU.

Result at pilot time: write rails 1312/1312 exact (incl. the four
fz12569 C1 w12/w14 cells the FSM RTL fails); R2-issue 782/800 exact.

Usage:  python3 sw/ins_ucode_pilot.py   (from repo root; offline only)
"""
import json
import sys
from collections import Counter

FAMS = {
    'ALIGNED_IMMEDIATE_INS_OFF2_LEN9': dict(off=2, ln=9, split=False),
    'SPLIT_REGISTER_INS_OFF1_LEN7':    dict(off=1, ln=7, split=True),
    'SPLIT_REGISTER_INS_OFF1_LEN8':    dict(off=1, ln=8, split=True),
    'ALIGNED_REGISTER_INS_OFF1_LEN7':  dict(off=1, ln=7, split=False),
}
SEEDS = (12302, 12466, 12547, 12569)
FIT, VAL = (12302, 12466), (12547, 12569)


def load(seed):
    d = json.load(open(f'sw/case250_fz{seed}_factorial.json'))
    target = d['cases'][str(seed)]['target']
    cells = []
    for r in d['records']:
        fam = FAMS[r['family']]
        near = r['chip_near']
        reads = [x for x in near if x['bs'] == 5]
        writes = [x for x in near if x['bs'] == 6]
        codes = [x for x in near if x['bs'] == 4]
        assert len(reads) == (4 if fam['split'] else 2)
        assert len(writes) == (2 if fam['split'] else 1)
        for x in reads + writes:
            assert abs(x['addr'] - target) <= 3
        if fam['split']:
            r1l, r1h, r2l, r2h = reads
        else:
            (r1h, r2h), r1l, r2l = reads, None, None
        cells.append(dict(
            seed=seed, off=fam['off'], S=fam['off'] + fam['ln'],
            split=fam['split'], role=r['role'], wait=r['wait'],
            hist=r['history'], R1=r1h, R2=r2h, R1L=r1l, R2L=r2l,
            W1=writes[0], W2=writes[1] if fam['split'] else None,
            codes=codes))
    return cells


def e(x):
    return 1 if x['tw'] > 0 else 0


def w1_pred(c):
    return max(c['R1']['t4'] + e(c['R1']) + 3 * c['S'] + 30,
               c['R2']['t4'] + e(c['R2']) + 2 * c['S'] + 9)


def w2_pred(c):
    return c['W1']['t4'] + 1 + e(c['W1'])


def r2_pred(c):
    ev = c['R2L'] if c['split'] else c['R2']
    req = c['R1']['t4'] + e(c['R1']) + 18 + c['off']
    prior = [x for x in c['codes'] if x['t4'] < ev['t1']]
    prior += [x for x in (c['R1'], c['R1L']) if x and x['t4'] < ev['t1']]
    return max(req, max(x['t4'] for x in prior) + 2), ev['t1']


def main():
    sb, fail = {}, 0
    for seed in SEEDS:
        s = sb.setdefault(seed, dict(w1=Counter(), w2=Counter(), r2=Counter()))
        for c in load(seed):
            s['w1'][c['W1']['t1'] - w1_pred(c)] += 1
            if c['W2']:
                s['w2'][c['W2']['t1'] - w2_pred(c)] += 1
            p, a = r2_pred(c)
            s['r2'][a - p] += 1
    for grp, seeds in (('FIT', FIT), ('VALIDATE (frozen)', VAL)):
        print(f'== {grp} ==')
        for sd in seeds:
            s = sb[sd]
            print(f'  fz{sd}: W1 {dict(sorted(s["w1"].items()))}'
                  f'  W2 {dict(sorted(s["w2"].items()))}'
                  f'  R2issue {dict(sorted(s["r2"].items()))}')
    tot_w = sum(sum(s['w1'].values()) + sum(s['w2'].values()) for s in sb.values())
    ex_w = sum(s['w1'][0] + s['w2'][0] for s in sb.values())
    tot_r = sum(sum(s['r2'].values()) for s in sb.values())
    ex_r = sum(s['r2'][0] for s in sb.values())
    print(f'write rails exact: {ex_w}/{tot_w}')
    print(f'R2-issue exact:    {ex_r}/{tot_r} (residue = grid parity, BIU layer)')
    if ex_w != tot_w:
        fail = 1
    sys.exit(fail)


if __name__ == '__main__':
    main()
