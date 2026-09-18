"""Evaluation of an ATE (or any margin rule) on the GESL records."""

from __future__ import annotations
import math
import numpy as np
import pandas as pd

from gs2_core import (FR, ATEBase, ATEConst, run_engine, KAPPA_MIN_HI,
                      KAPPA_MIN_LO, KAPPA_GAP_MIN, KAPPA_MAX_HI, Q_HI, Q_LO,
                      KAPPA_HI_PAD, AmbientTracker, FeatureBank, N_FEAT)
import gs2_data as D
from gs2_synth import ambient_pass


def load_channels(data_dir, ids, channels=None, use_cordic=True):
    channels = channels or D.CHANNELS
    out = []
    for rid in ids:
        rec = D.load_record(data_dir, rid)
        fs = rec["fs"]
        for ch in channels:
            x = rec["df"][ch].to_numpy(float)
            proc = D.process_channel(x, fs, use_cordic=use_cordic)
            lab, b_off, floor_off = D.oracle_labels(proc, fs)
            truth = D.report_truth(lab, proc["edges"])
            d, F = ambient_pass(proc["b"], proc["lv"], proc["f"],
                                proc["gate_r"])
            v = proc["valid_r"] & ~proc["dead_r"]
            amb = v & ~truth
            out.append(dict(rid=rid, ch=ch, fs=fs, proc=proc, truth=truth,
                            valid=v, d=d, F=F,
                            sample_labels=lab, b_off=b_off, floor_off=floor_off,
                            kh_star=float(np.quantile(d[amb], Q_HI)) + KAPPA_HI_PAD,
                            kl_star=float(np.quantile(d[amb], Q_LO)),
                            n_event_reports=int(truth[v].sum()),
                            duration=rec["duration"],
                            description=rec["description"]))
    return out


# ----------------------------------------------------------------------------

def eval_channel(c, ate: ATEBase, kappa_min_hi=KAPPA_MIN_HI):
    r = run_engine(c["proc"]["b"], c["proc"]["lv"], c["proc"]["f"], ate,
                   kappa_min_hi=kappa_min_hi, dead=c["proc"]["gate_r"])
    v = c["valid"]
    p = r["trig"][v].astype(bool)
    t = c["truth"][v].astype(bool)
    m = D.prf(p, t)
    m.update(D.event_metrics(p, t))
    m["bandwidth_reduction"] = D.bandwidth_reduction(p)
    m["n_reports"] = int(v.sum())
    m["has_events"] = bool(t.any())
    return m


def aggregate(rows):
    """Micro (pooled over reports) and macro (mean over event-bearing channels)."""
    tp = sum(r["tp"] for r in rows)
    fp = sum(r["fp"] for r in rows)
    fn = sum(r["fn"] for r in rows)
    pr = tp / (tp + fp) if tp + fp else 0.0
    rc = tp / (tp + fn) if tp + fn else 0.0
    micro = 2 * pr * rc / (pr + rc) if pr + rc else 0.0
    ev = [r for r in rows if r["has_events"]]
    macro = float(np.mean([r["f1"] for r in ev])) if ev else float("nan")
    nw = sum(r["n_event_windows"] for r in rows)
    nc = sum(r["n_caught"] for r in rows)
    lat = [r["latency_ms"] for r in rows if not math.isnan(r["latency_ms"])]
    quiet = [r for r in rows if not r["has_events"]]
    return dict(micro_f1=micro, macro_f1=macro, precision=pr, recall=rc,
                event_recall=nc / nw if nw else float("nan"),
                n_event_windows=nw, n_caught=nc,
                false_alarm_runs=sum(r["false_alarm_runs"] for r in rows),
                false_alarm_runs_quiet=sum(r["false_alarm_runs"] for r in quiet),
                duty_cycle=float(np.mean([r["duty_cycle"] for r in rows])),
                duty_cycle_quiet=float(np.mean([r["duty_cycle"] for r in quiet]))
                if quiet else float("nan"),
                latency_ms=float(np.mean(lat)) if lat else float("nan"),
                bandwidth_reduction=float(np.mean(
                    [min(r["bandwidth_reduction"], 1e6) for r in rows])),
                n_channels=len(rows), n_channels_with_events=len(ev))


def eval_all(channels, ate, kappa_min_hi=KAPPA_MIN_HI, label=""):
    rows = []
    for c in channels:
        m = eval_channel(c, ate, kappa_min_hi)
        m.update(rid=c["rid"], ch=c["ch"], method=label)
        rows.append(m)
    return rows, aggregate(rows)


# ----------------------------------------------------------------------------
# baselines
# ----------------------------------------------------------------------------

def best_fixed_margin(channels, grid=None, kappa_min_hi=0.0,
                      gaps=(0.5, 1.0, 2.0, 4.0), objective="macro_f1"):
    grid = grid if grid is not None else np.arange(0.25, 10.01, 0.25)
    best = None
    for kh in grid:
        for gp in gaps:
            rows, agg = eval_all(channels, ATEConst(kh, gp),
                                 kappa_min_hi=kappa_min_hi)
            if best is None or agg[objective] > best[1][objective]:
                best = ((float(kh), float(gp)), agg, rows)
    return best


def hindsight_ceiling(channels, grid=None, kappa_min_hi=0.0,
                      gaps=(0.5, 1.0, 2.0, 4.0)):
    """Per-channel best (kappa_H, gap) chosen WITH the labels: an upper bound,
    not an achievable method."""
    grid = grid if grid is not None else np.arange(0.25, 12.01, 0.25)
    rows = []
    for c in channels:
        bestm, bestk = None, None
        for kh in grid:
            for g in gaps:
                m = eval_channel(c, ATEConst(kh, g),
                                 kappa_min_hi=kappa_min_hi)
                key = m["f1"] if m["has_events"] else -m["duty_cycle"]
                if bestm is None or key > bestm[0]:
                    bestm = (key, m)
                    bestk = (float(kh), float(g))
        m = bestm[1]
        m.update(rid=c["rid"], ch=c["ch"], method="ceiling",
                 kappa_h=bestk[0], gap=bestk[1])
        rows.append(m)
    return rows, aggregate(rows)


def per_record_statistical(channels, kappa_min_hi=0.0):
    """Offline per-channel statistical calibration: kappa from that channel's
    own ambient distribution, computed with the labels known.  NON-CAUSAL."""
    rows = []
    for c in channels:
        m = eval_channel(c, ATEConst(c["kh_star"],
                                     max(0.25, c["kh_star"] - c["kl_star"])),
                         kappa_min_hi=kappa_min_hi)
        m.update(rid=c["rid"], ch=c["ch"], method="per-record-Q")
        rows.append(m)
    return rows, aggregate(rows)


class EmpiricalQ(ATEBase):
    """Causal, non-learned baseline: running empirical quantile of the excess
    over all reports seen so far.  Needs a sorted history -> O(R) memory."""
    name = "empirical-Q"

    def __init__(self):
        self.hist = []

    def predict(self, f):
        # f is unused; the engine feeds excess through the feature bank, so this
        # baseline is implemented separately in run_empirical_q().
        raise NotImplementedError


def run_empirical_q(c, kappa_min_hi=0.0, warmup=32):
    """Causal empirical-quantile margin, evaluated with the same FSM."""
    b = c["proc"]["b"]
    nrep = b.size
    trk = AmbientTracker()
    hist = []
    state = 0
    kh_l = kl_l = amb_l = 0.0
    trig = np.zeros(nrep, np.int8)
    dead = c["proc"]["gate_r"]
    for r in range(nrep):
        if dead[r]:
            trig[r] = state
            continue
        if state == 0:
            amb = trk.update(float(b[r]))
        else:
            amb = amb_l
        d = float(b[r]) - amb
        if state == 0:
            if len(hist) >= warmup:
                kh = float(np.quantile(hist, Q_HI)) + KAPPA_HI_PAD
                kl = max(kh - 1.0, float(np.quantile(hist, Q_LO)))
            else:
                kh, kl = KAPPA_MAX_HI, KAPPA_MAX_HI - 1.0
            kh = min(max(kh, kappa_min_hi), KAPPA_MAX_HI)
            kl = min(max(kl, KAPPA_MIN_LO), kh - KAPPA_GAP_MIN)
        else:
            kh, kl = kh_l, kl_l
        if state == 0:
            hist.append(d)
            if b[r] >= amb + kh:
                state = 1
                kh_l, kl_l, amb_l = kh, kl, amb
        else:
            if b[r] < amb_l + kl_l:
                state = 0
        trig[r] = state
    v = c["valid"]
    p = trig[v].astype(bool)
    t = c["truth"][v].astype(bool)
    m = D.prf(p, t)
    m.update(D.event_metrics(p, t))
    m["bandwidth_reduction"] = D.bandwidth_reduction(p)
    m["n_reports"] = int(v.sum())
    m["has_events"] = bool(t.any())
    m.update(rid=c["rid"], ch=c["ch"], method="empirical-Q")
    return m


def run_v1_fixed(c):
    rep, _ = D.v1_fixed_trigger(c["proc"], c["fs"])
    v = c["valid"]
    p = rep[v].astype(bool)
    t = c["truth"][v].astype(bool)
    m = D.prf(p, t)
    m.update(D.event_metrics(p, t))
    m["bandwidth_reduction"] = D.bandwidth_reduction(p)
    m["n_reports"] = int(v.sum())
    m["has_events"] = bool(t.any())
    m.update(rid=c["rid"], ch=c["ch"], method="v1-fixed")
    return m
