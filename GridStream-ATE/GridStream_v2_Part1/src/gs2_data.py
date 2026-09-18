"""GESL loading, reference labels (offline oracle) and metrics."""

from __future__ import annotations
import csv, math, os
import numpy as np
import pandas as pd

from gs2_core import (FN, FR, EPS, NTAPS, GROUP_DELAY, log2_hw, log2_hw_scalar,
                      pmu_front_end, sliding_lse, report_edges, reduce_max,
                      reduce_last, reduce_mean, causal_vbar_log2,
                      V1_THRESH_UPPER, V1_THRESH_LOWER)

CHANNELS = ["Voltage.Va", "Voltage.Vb", "Voltage.Vc",
            "Current.Ia", "Current.Ib", "Current.Ic"]

RECORD_IDS = [45, 55, 677, 901, 907, 971]

DEAD_RATIO = 16.0   # magnitude below M0/DEAD_RATIO counts as a de-energised line


# ----------------------------------------------------------------------------
# metadata
# ----------------------------------------------------------------------------

def load_metadata(path: str) -> dict:
    with open(path, newline="") as fh:
        rows = list(csv.reader(fh))
    hdr = [h.strip() for h in rows[0]]
    val = rows[1]
    d = {}
    for i, h in enumerate(hdr):
        d[h] = val[i].strip() if i < len(val) else ""
    return d


def load_record(data_dir: str, rid: int):
    meta = load_metadata(os.path.join(data_dir, f"sigId{rid}Metadata.csv"))
    df = pd.read_csv(os.path.join(data_dir, f"sigId{rid}PoW.csv"))
    fs_meta = float(meta["Rate (Hz)"])
    dur = float(meta["Duration (s)"])
    n = len(df)
    fs_rec = (n - 1) / dur if dur > 0 else fs_meta
    return dict(id=rid, meta=meta, df=df, fs=fs_meta, fs_recovered=fs_rec,
                n=n, duration=dur,
                provider=meta.get("Data Source", ""),
                description=meta.get("Description", ""))


# ----------------------------------------------------------------------------
# per-channel processing: raw -> report-rate b, lv, f  (all causal)
# ----------------------------------------------------------------------------

def process_channel(x: np.ndarray, fs: float, use_cordic: bool = True):
    n = x.size
    W = int(round(fs / FN))                       # one nominal cycle
    mag, ang, est_v, freq = pmu_front_end(x, fs, use_cordic=use_cordic)
    resid = x - est_v
    L = sliding_lse(resid, W)

    edges = report_edges(n, fs)
    Lmax = reduce_max(L, edges)                   # report-wise maximum
    mag_rep = reduce_last(mag, edges)             # causal: last sample of report
    f_rep = reduce_mean(freq, edges)

    lvbar, dead_r_causal = causal_vbar_log2(mag_rep)   # available AT report r
    lb = log2_hw(np.maximum(Lmax, EPS))
    b = lb - log2_hw_scalar(float(W)) - 2.0 * lvbar + 1.0

    lv_rep = log2_hw(np.maximum(mag_rep, EPS))

    # Validity mask.  The first NTAPS+W samples are the FIR/LSE start-up
    # transient and the last GROUP_DELAY samples are affected by the reflection
    # padding; neither is a measurement, so both are excluded from labels and
    # from every metric.
    lo = NTAPS + W
    hi = n - GROUP_DELAY
    valid_s = np.zeros(n, dtype=bool)
    valid_s[lo:hi] = True

    # De-energised ("dead line") samples.  When the phasor magnitude collapses
    # to a small fraction of the record's own level -- a breaker or recloser
    # open interval -- the normalised GOF has no meaning, because both the
    # residual and the normaliser go to zero together.  Detecting a dead line
    # is a separate, trivial comparator, not the job of a residual trigger, so
    # these samples are EXCLUDED from labelling and from every metric.  The
    # excluded fraction is reported per channel.
    M0 = float(np.median(mag[valid_s])) if valid_s.any() else 0.0
    dead_s = valid_s & (mag < M0 / DEAD_RATIO)
    valid_s = valid_s & ~dead_s

    valid_r = np.array([valid_s[edges[r]:edges[r + 1]].all()
                        for r in range(edges.size - 1)])
    return dict(W=W, edges=edges, L=L, Lmax=Lmax, b=b, lv=lv_rep, f=f_rep,
                mag=mag, est_v=est_v, resid=resid, lvbar=lvbar, freq=freq,
                valid_s=valid_s, valid_r=valid_r, dead_s=dead_s, M0=M0,
                dead_r=dead_r_causal,
                gate_r=(~valid_r) | dead_r_causal)


# ----------------------------------------------------------------------------
# offline (NON-CAUSAL) oracle -- reference labels only, never online
# ----------------------------------------------------------------------------

ORACLE_RISE_OCT = math.log2(10.0)     # an event is a >=10x rise in normalised GOF
AMBIENT_BAND_OCT = 1.0                # magnitude band used to pick ambient samples


def oracle_labels(proc: dict, fs: float):
    """Non-causal reference labels.  Uses whole-record statistics; this is the
    definition of 'event' the paper evaluates against, and it is imperfect
    (see the synthetic validation of the oracle)."""
    W = proc["W"]
    mag = proc["mag"]
    L = proc["L"]
    v = proc["valid_s"]
    lvbar_off = log2_hw_scalar(max(float(np.median(mag[v])), EPS))  # NON-CAUSAL
    b_off = log2_hw(np.maximum(L, EPS)) - log2_hw_scalar(float(W)) \
        - 2.0 * lvbar_off + 1.0
    # The reference floor is taken only over samples whose magnitude sits within
    # one octave of the record level, so that a sag or an open interval cannot
    # define the ambient floor of the record.
    band = v & (np.abs(log2_hw(np.maximum(mag, EPS)) - lvbar_off)
                <= AMBIENT_BAND_OCT)
    ref = band if band.sum() > 0.05 * max(v.sum(), 1) else v
    floor_off = float(np.percentile(b_off[ref], 10.0))             # NON-CAUSAL
    lab = (b_off > (floor_off + ORACLE_RISE_OCT)) & v

    lab = _close_runs(lab, W)          # bridge gaps shorter than one cycle
    lab &= v
    lab = _open_runs(lab, max(1, W // 4))
    return lab, b_off, floor_off


def _runs(mask: np.ndarray):
    d = np.diff(np.concatenate([[0], mask.view(np.int8), [0]]))
    starts = np.where(d == 1)[0]
    ends = np.where(d == -1)[0]
    return list(zip(starts, ends))


def _close_runs(mask, gap):
    m = mask.copy()
    rs = _runs(m)
    for (s0, e0), (s1, e1) in zip(rs[:-1], rs[1:]):
        if s1 - e0 <= gap:
            m[e0:s1] = True
    return m


def _open_runs(mask, minlen):
    m = mask.copy()
    for s, e in _runs(m):
        if e - s < minlen:
            m[s:e] = False
    return m


def report_truth(sample_labels: np.ndarray, edges: np.ndarray) -> np.ndarray:
    """A report is an event report if ANY sample inside it is labelled --
    this matches the report-wise MAXIMUM used to decimate Lambda."""
    return np.array([sample_labels[edges[r]:edges[r + 1]].any()
                     for r in range(edges.size - 1)])


# ----------------------------------------------------------------------------
# metrics
# ----------------------------------------------------------------------------

def prf(pred: np.ndarray, truth: np.ndarray):
    pred = pred.astype(bool)
    truth = truth.astype(bool)
    tp = int(np.sum(pred & truth))
    fp = int(np.sum(pred & ~truth))
    fn = int(np.sum(~pred & truth))
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return dict(tp=tp, fp=fp, fn=fn, precision=prec, recall=rec, f1=f1)


def event_metrics(pred: np.ndarray, truth: np.ndarray):
    """Window-level behaviour: how many labelled event windows were caught,
    how many trigger runs were spurious, and the detection latency."""
    tw = _runs(truth.astype(bool))
    pw = _runs(pred.astype(bool))
    caught, lat = 0, []
    for s, e in tw:
        hit = np.where(pred[s:e])[0]
        if hit.size:
            caught += 1
            lat.append(int(hit[0]))
    false_runs = 0
    for s, e in pw:
        if not truth[s:e].any():
            false_runs += 1
    return dict(n_event_windows=len(tw), n_caught=caught,
                event_recall=(caught / len(tw)) if tw else float("nan"),
                false_alarm_runs=false_runs,
                latency_reports=float(np.mean(lat)) if lat else float("nan"),
                latency_ms=float(np.mean(lat)) / FR * 1e3 if lat else float("nan"),
                duty_cycle=float(np.mean(pred.astype(bool))))


def bandwidth_reduction(pred: np.ndarray) -> float:
    duty = float(np.mean(pred.astype(bool)))
    return float("inf") if duty <= 0 else 1.0 / duty


# ----------------------------------------------------------------------------
# v1 fixed-threshold baseline, transported verbatim
# ----------------------------------------------------------------------------

def v1_fixed_trigger(proc: dict, fs: float):
    """v1 rule applied to the RAW per-sample LSE with the published constants,
    then decimated to reports (a report is active if any sample is active)."""
    Lraw = proc["resid"] ** 2                      # v1 used the per-sample LSE
    state = 0
    out = np.zeros(Lraw.size, dtype=bool)
    for k in range(Lraw.size):
        if k < 256:
            state = 0
        elif state == 0:
            if Lraw[k] > V1_THRESH_UPPER:
                state = 1
        else:
            if Lraw[k] < V1_THRESH_LOWER:
                state = 0
        out[k] = state
    edges = proc["edges"]
    return np.array([out[edges[r]:edges[r + 1]].any()
                     for r in range(edges.size - 1)]), out
