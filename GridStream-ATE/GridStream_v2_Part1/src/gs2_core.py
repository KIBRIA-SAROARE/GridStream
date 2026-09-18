"""
GridStream-v2 : Adaptive Threshold Engine (ATE) -- Part 1 core library.

Every online quantity in this file is CAUSAL.  Offline / non-causal quantities
exist only inside functions whose name contains `oracle` or `offline`, and they
are used only to build reference labels and hindsight baselines.

Signal chain (Section 3 of the design record):

    raw PoW --> NCO --> FIR(257) --> CORDIC --> phasor        (v1, UNCHANGED)
                                       |
                                       +--> reconstruction --> residual
                                                 --> sliding LSE  L[n]
    C1  b = log2 L - log2 W - 2*log2 Vbar + 1      Vbar = causal HELD EWMA
    C2  b_amb  = causal minimum-statistics tracker
    C3  kH,kL  = ATE(6 causal features)
        trigger:  b >= b_amb + kH                  (an ADD and a COMPARE)
    C2' hysteresis FSM, kappa and b_amb LATCHED, feature EWMAs HELD while asserted
"""

from __future__ import annotations
import math
import numpy as np
from scipy.signal import firwin, lfilter

# ----------------------------------------------------------------------------
# 1. Configuration -- every constant used anywhere in Part 1 lives here.
# ----------------------------------------------------------------------------

FN            = 60.0        # nominal system frequency [Hz]
NTAPS         = 257         # v1 FIR length
FIR_CUTOFF_HZ = 10.0        # v1 FIR cutoff
FIR_WINDOW    = "hamming"   # identified from the v1 reference (see provenance)
GROUP_DELAY   = (NTAPS - 1) // 2

FR            = 120.0       # synchrophasor reporting rate [reports/s]

N_ACQ         = 32          # ambient-tracker acquisition length [reports]
MS_SUBWIN     = 16          # minimum-statistics sub-window length [reports]
MS_NSUB       = 4           # number of sub-windows -> memory 64 reports

ALPHA_V       = 1.0 / 16.0  # Vbar EWMA rate, at REPORT rate
VBAR_HOLD_OCT = 1.0         # freeze Vbar if |log2 mag - log2 Vbar| exceeds this
VBAR_HOLD_MAX = 600         # ... but re-acquire UPWARD after this many
                            # reports (5 s: longer than any protection
                            # operation, shorter than a load-level change)
DEAD_OCT      = 4.0         # signal-presence gate: 16x below Vbar = dead line

ALPHA_SLOW    = 1.0 / 256.0 # slow feature EWMA (~2.1 s at 120 rep/s)
ALPHA_FAST    = 1.0 / 16.0  # fast feature EWMA
MAX_DECAY     = 0.01        # decay of the running-max feature [octaves/report]

KAPPA_MIN_HI  = math.log2(10.0)   # physical floor: a 10x rise in normalised GOF
KAPPA_MAX_HI  = 24.0
KAPPA_MIN_LO  = 0.5
KAPPA_GAP_MIN = 0.25        # hysteresis depth Delta is clamped to
KAPPA_GAP_MAX = 6.0         # [KAPPA_GAP_MIN, KAPPA_GAP_MAX] octaves

Q_HI          = 0.998       # quantile defining kappa_H*
Q_LO          = 0.900       # quantile defining kappa_L*
KAPPA_HI_PAD  = 0.5         # additive pad on the kappa_H* target

EPS           = 1e-30

# v1 fixed thresholds, transported verbatim from et_pmu_scaled.py
V1_THRESH_UPPER = 1.0e7
V1_THRESH_LOWER = 3.0e2

# ----------------------------------------------------------------------------
# 2. Hardware log2 primitive: priority encoder + 64-entry mantissa ROM
# ----------------------------------------------------------------------------

LOG2_ROM_BITS = 6
LOG2_ROM_N    = 1 << LOG2_ROM_BITS
LOG2_ROM      = np.log2(1.0 + np.arange(LOG2_ROM_N) / LOG2_ROM_N)


def log2_hw(x):
    """Piecewise-linear-free log2: exponent from a priority encoder, fraction
    from a 64-entry ROM addressed by the top 6 mantissa bits (truncating).
    Identical in Python and in the exported C++."""
    x = np.asarray(x, dtype=np.float64)
    out = np.full(x.shape, -1023.0)
    pos = x > 0
    if not np.any(pos):
        return out if out.ndim else float(out)
    xp = x[pos] if x.ndim else x
    e = np.floor(np.log2(xp)).astype(np.int64)          # priority encoder
    m = xp / np.exp2(e.astype(np.float64))              # barrel shift -> [1,2)
    idx = np.clip(((m - 1.0) * LOG2_ROM_N).astype(np.int64), 0, LOG2_ROM_N - 1)
    val = e.astype(np.float64) + LOG2_ROM[idx]
    if x.ndim:
        out[pos] = val
        return out
    return float(val)


def log2_hw_scalar(x: float) -> float:
    if x <= 0.0:
        return -1023.0
    e = math.floor(math.log2(x))
    m = x / (2.0 ** e)
    idx = int((m - 1.0) * LOG2_ROM_N)
    if idx < 0:
        idx = 0
    elif idx >= LOG2_ROM_N:
        idx = LOG2_ROM_N - 1
    return e + LOG2_ROM[idx]


# ----------------------------------------------------------------------------
# 3. v1 PMU front end (unchanged from GridStream-v1)
# ----------------------------------------------------------------------------

CORDIC_ANGLES = np.array([math.atan(2.0 ** -i) for i in range(16)])
CORDIC_K = 0.607252935


def cordic_vec(x, y, iterations=16):
    """Vectorised 16-iteration CORDIC in vectoring mode; identical operation
    order to `cordic_kernel_optimized` in the v1 reference et_pmu_scaled.py."""
    cx = np.array(x, dtype=np.float64, copy=True)
    cy = np.array(y, dtype=np.float64, copy=True)
    ang = np.zeros_like(cx)
    neg = cx < 0
    cx[neg] = -cx[neg]
    cy[neg] = -cy[neg]
    ang[neg] = math.pi
    for i in range(iterations):
        d = np.where(cy < 0, 1.0, -1.0)
        f = 2.0 ** (-i)
        nx = cx - d * cy * f
        ny = cy + d * cx * f
        ang = ang - d * CORDIC_ANGLES[i]
        cx, cy = nx, ny
    return cx * CORDIC_K, ang


def fir_taps(fs: float) -> np.ndarray:
    """v1 M-class low-pass, redesigned at the record's own sampling rate."""
    return firwin(NTAPS, FIR_CUTOFF_HZ, fs=fs, window=FIR_WINDOW)


def pmu_front_end(x: np.ndarray, fs: float, use_cordic: bool = True):
    """Returns (mag, ang, est_v, freq) all aligned to the ORIGINAL sample index.

    mag  : phasor peak magnitude (same unit as x)
    est_v: reconstructed waveform
    freq : instantaneous frequency estimate [Hz]
    """
    n = x.size
    h = fir_taps(fs)
    w = 2.0 * math.pi * FN / fs

    # reflection padding of GROUP_DELAY samples, exactly as in v1
    pad = x[-GROUP_DELAY:][::-1]
    xp = np.concatenate([x, pad])
    k = np.arange(xp.size, dtype=np.float64)
    ph = w * k
    dI = xp * np.cos(ph)
    dQ = -xp * np.sin(ph)

    yI = lfilter(h, [1.0], dI)
    yQ = lfilter(h, [1.0], dQ)

    if use_cordic:
        mag_h, ang = cordic_vec(yI, yQ)
    else:
        mag_h = np.hypot(yI, yQ)
        ang = np.arctan2(yQ, yI)

    # output at filter index i corresponds to input index i - GROUP_DELAY
    sl = slice(GROUP_DELAY, GROUP_DELAY + n)
    mag = 2.0 * mag_h[sl]
    ang = ang[sl]

    idx = np.arange(n, dtype=np.float64)
    est_v = mag * np.cos(w * idx + ang)

    dth = np.diff(ang, prepend=ang[0])
    dth = (dth + math.pi) % (2.0 * math.pi) - math.pi
    freq = FN + dth * fs / (2.0 * math.pi)
    freq[:NTAPS] = FN
    return mag, ang, est_v, freq


def sliding_lse(resid: np.ndarray, W: int) -> np.ndarray:
    """Causal sliding sum of squared residuals over W samples.
    L[k] uses samples k-W+1 .. k only."""
    e2 = resid * resid
    c = np.concatenate([[0.0], np.cumsum(e2)])
    L = np.empty_like(e2)
    k = np.arange(e2.size)
    lo = np.maximum(0, k - W + 1)
    L = c[k + 1] - c[lo]
    return L


# ----------------------------------------------------------------------------
# 4. Report-rate decimation and the causal normaliser
# ----------------------------------------------------------------------------

def report_edges(n: int, fs: float):
    """Report boundaries: report r covers samples [e[r], e[r+1])."""
    step = fs / FR
    nrep = int(n // step)
    e = np.round(np.arange(nrep + 1) * step).astype(np.int64)
    e[-1] = min(e[-1], n)
    return e


def reduce_max(v: np.ndarray, edges: np.ndarray) -> np.ndarray:
    return np.array([v[edges[r]:edges[r + 1]].max() for r in range(edges.size - 1)])


def reduce_last(v: np.ndarray, edges: np.ndarray) -> np.ndarray:
    return v[edges[1:] - 1]


def reduce_mean(v: np.ndarray, edges: np.ndarray) -> np.ndarray:
    return np.array([v[edges[r]:edges[r + 1]].mean() for r in range(edges.size - 1)])


def causal_vbar_log2(mag_rep: np.ndarray) -> np.ndarray:
    """Causal HELD EWMA of the phasor magnitude, in the log2 domain.

    Returns lvbar[r] = the value AVAILABLE AT THE START of report r, i.e. it is
    formed from magnitudes of reports 0..r-1 only.  Frozen whenever the incoming
    magnitude departs from the running value by more than VBAR_HOLD_OCT octaves,
    so that a sag cannot deflate its own normaliser.

    The hold is ASYMMETRIC and this matters:

    * a sustained RISE above the reference is a new operating level (load pick-up,
      reclose, tap change), so after VBAR_HOLD_MAX held reports the normaliser
      re-acquires at the new level;
    * a sustained DROP is a de-energised line -- a breaker or recloser that has
      opened -- and the normaliser must NEVER follow it down, because the
      residual goes to zero with it and Lambda would explode on the way back.

    Returns (lvbar, dead) where dead[r] is the causal signal-presence flag:
    the measured magnitude is more than DEAD_OCT octaves below the reference,
    so the normalised GOF is meaningless for that report.
    """
    nrep = mag_rep.size
    lv_in = np.array([log2_hw_scalar(max(m, EPS)) for m in mag_rep])
    lvbar = np.empty(nrep)
    dead = np.zeros(nrep, dtype=bool)
    s = lv_in[0]
    held = 0
    for r in range(nrep):
        lvbar[r] = s                       # value used by report r (causal)
        d = lv_in[r] - s
        dead[r] = d < -DEAD_OCT
        if abs(d) <= VBAR_HOLD_OCT:        # healthy: track
            s = s + ALPHA_V * d
            held = 0
        elif d > 0:                        # sustained rise: new level
            held += 1
            if held >= VBAR_HOLD_MAX:
                s = lv_in[r]
                held = 0
        else:                              # sustained drop: hold indefinitely
            held = 0
    return lvbar, dead


# ----------------------------------------------------------------------------
# 5. Causal ambient tracker (minimum statistics)
# ----------------------------------------------------------------------------

class AmbientTracker:
    """One report at a time.  Acquisition = running minimum over the first
    N_ACQ reports.  Afterwards = minimum over MS_NSUB sub-window minima, so the
    tracker forgets after MS_NSUB*MS_SUBWIN reports and can follow a rising
    ambient floor."""

    def __init__(self):
        self.r = 0
        self.run_min = math.inf
        self.cur_min = math.inf
        self.ring = [math.inf] * MS_NSUB
        self.slot = 0
        self.filled = 0
        self.b_amb = 0.0

    def update(self, b: float) -> float:
        if b < self.run_min:
            self.run_min = b
        if b < self.cur_min:
            self.cur_min = b
        self.r += 1
        if self.r % MS_SUBWIN == 0:
            self.ring[self.slot] = self.cur_min
            self.slot = (self.slot + 1) % MS_NSUB
            self.filled = min(self.filled + 1, MS_NSUB)
            self.cur_min = math.inf
        if self.r <= N_ACQ or self.filled == 0:
            self.b_amb = self.run_min
        else:
            m = math.inf
            for i in range(MS_NSUB):
                if self.ring[i] < m:
                    m = self.ring[i]
            self.b_amb = min(m, self.cur_min)
        return self.b_amb


# ----------------------------------------------------------------------------
# 6. Six causal features
# ----------------------------------------------------------------------------

N_FEAT = 6
FEATURE_NAMES = [
    "f0_b_amb",           # ambient floor level                    [octaves]
    "f1_mean_excess",     # slow EWMA of d = b - b_amb             [octaves]
    "f2_mad_excess",      # slow EWMA of |d - mean d|              [octaves]
    "f3_decaying_max",    # running max of d, decaying             [octaves]
    "f4_log2_mag_jitter", # log2 of slow EWMA of |d log2 mag|      [log2 octaves]
    "f5_log2_frq_jitter", # log2 of slow EWMA of |f - FN|          [log2 Hz]
]


class FeatureBank:
    """Six causal statistics of the ambient excess, updated once per report.
    `update(hold=True)` freezes every state while the FSM is asserted, so an
    event cannot pollute the ambient statistics.

    f3 is a decaying running maximum: one comparator, one subtract and one
    register.  It is the cheapest causal proxy for the upper tail of d, which
    is what kappa_H* is a quantile of.
    """

    def __init__(self):
        self.m1 = 0.0
        self.mad = 0.0
        self.dmax = 0.0
        self.jm = 0.0
        self.jf = 0.0
        self.prev_lv = None
        self.init = False

    def update(self, excess: float, lv: float, fhz: float, hold: bool):
        if self.prev_lv is None:
            self.prev_lv = lv
        if not hold:
            if not self.init:
                self.m1 = excess
                self.mad = 0.0
                self.dmax = excess
                self.jm = abs(lv - self.prev_lv)
                self.jf = abs(fhz - FN)
                self.init = True
            else:
                self.m1 += ALPHA_SLOW * (excess - self.m1)
                self.mad += ALPHA_SLOW * (abs(excess - self.m1) - self.mad)
                dec = self.dmax - MAX_DECAY
                self.dmax = excess if excess > dec else dec
                self.jm += ALPHA_SLOW * (abs(lv - self.prev_lv) - self.jm)
                self.jf += ALPHA_SLOW * (abs(fhz - FN) - self.jf)
            self.prev_lv = lv

    def vector(self, b_amb: float) -> np.ndarray:
        return np.array([
            b_amb,
            self.m1,
            self.mad,
            self.dmax,
            log2_hw_scalar(max(self.jm, 1e-9)),
            log2_hw_scalar(max(self.jf, 1e-9)),
        ])


# ----------------------------------------------------------------------------
# 7. ATE predictor families
# ----------------------------------------------------------------------------

class ATEBase:
    """Common interface: predict(f) -> (kappa_H, Delta) BEFORE constraints.

    The second output is the HYSTERESIS DEPTH Delta, not kappa_L itself:
    kappa_L = kappa_H - Delta.  Predicting the depth rather than an absolute
    release level is what keeps the FSM releasing -- an absolute kappa_L taken
    from a low ambient quantile leaves the trigger latched indefinitely.
    """
    name = "base"

    def predict(self, f: np.ndarray):
        raise NotImplementedError


class ATEConst(ATEBase):
    name = "fixed"

    def __init__(self, kh: float, gap: float = 1.0):
        self.kh, self.gap = float(kh), float(gap)

    def predict(self, f):
        return self.kh, self.gap


class ATEQ(ATEBase):
    """Linear model, 6 inputs -> 2 outputs, fitted with the pinball loss."""
    name = "ATE-Q"

    def __init__(self, W, bias, mean, inv_sd):
        self.W = np.asarray(W, float)        # (2,6)
        self.b = np.asarray(bias, float)     # (2,)
        self.mean = np.asarray(mean, float)
        self.inv_sd = np.asarray(inv_sd, float)

    def predict(self, f):
        z = (f - self.mean) * self.inv_sd
        y = self.W @ z + self.b
        return float(y[0]), float(y[1])


class ATES(ATEBase):
    """Additive ensemble of decision stumps.  One comparison and one table
    lookup per stump: ZERO multipliers."""
    name = "ATE-S"

    def __init__(self, base, feat, thr, lo, hi, mean, inv_sd):
        self.base = np.asarray(base, float)   # (2,)
        self.feat = np.asarray(feat, int)     # (S,)
        self.thr = np.asarray(thr, float)     # (S,)
        self.lo = np.asarray(lo, float)       # (S,2)
        self.hi = np.asarray(hi, float)       # (S,2)
        self.mean = np.asarray(mean, float)
        self.inv_sd = np.asarray(inv_sd, float)

    def predict(self, f):
        z = (f - self.mean) * self.inv_sd
        acc = self.base.copy()
        for s in range(self.feat.size):
            acc += self.hi[s] if z[self.feat[s]] >= self.thr[s] else self.lo[s]
        return float(acc[0]), float(acc[1])


class ATEM(ATEBase):
    """MLP 6 -> H -> 2 with ReLU.  6*H + H*2 weight MACs."""
    name = "ATE-M"

    def __init__(self, W1, b1, W2, b2, mean, inv_sd):
        self.W1 = np.asarray(W1, float)
        self.b1 = np.asarray(b1, float)
        self.W2 = np.asarray(W2, float)
        self.b2 = np.asarray(b2, float)
        self.mean = np.asarray(mean, float)
        self.inv_sd = np.asarray(inv_sd, float)

    def predict(self, f):
        z = (f - self.mean) * self.inv_sd
        h = np.maximum(self.W1 @ z + self.b1, 0.0)
        y = self.W2 @ h + self.b2
        return float(y[0]), float(y[1])

    @property
    def n_mac(self):
        return self.W1.size + self.W2.size


# ----------------------------------------------------------------------------
# 8. The deployed engine -- ONE causal loop.  This IS the algorithm.
# ----------------------------------------------------------------------------

def run_engine(b_rep, lv_rep, f_rep, ate: ATEBase,
               kappa_min_hi: float = KAPPA_MIN_HI,
               collect: bool = False, dead=None):
    """Replay one channel report by report.

    b_rep  : normalised GOF in octaves, one value per report (report-wise max)
    lv_rep : log2 phasor magnitude per report
    f_rep  : frequency estimate per report [Hz]

    Returns dict with the trigger vector and, if `collect`, the per-report
    traces needed for figures and for the exported-C++ equivalence check.
    """
    nrep = b_rep.size
    trk = AmbientTracker()
    fb = FeatureBank()
    state = 0
    kh_l = kl_l = 0.0
    amb_l = 0.0

    trig = np.zeros(nrep, dtype=np.int8)
    tr_amb = np.empty(nrep) if collect else None
    tr_kh = np.empty(nrep) if collect else None
    tr_kl = np.empty(nrep) if collect else None
    tr_feat = np.empty((nrep, N_FEAT)) if collect else None

    for r in range(nrep):
        b = float(b_rep[r])
        gated = bool(dead[r]) if dead is not None else False
        if gated:
            # de-energised: freeze everything and hold the FSM state
            if collect:
                tr_amb[r] = trk.b_amb
                tr_kh[r] = kh_l
                tr_kl[r] = kl_l
                tr_feat[r] = fb.vector(trk.b_amb)
            trig[r] = state
            continue
        if state == 0:
            amb = trk.update(b)
        else:
            amb = amb_l                      # LATCHED while asserted
        fb.update(b - amb, float(lv_rep[r]), float(f_rep[r]), hold=(state == 1))
        fv = fb.vector(amb)

        if state == 0:
            kh, gap = ate.predict(fv)
            kh = min(max(kh, kappa_min_hi), KAPPA_MAX_HI)
            gap = min(max(gap, KAPPA_GAP_MIN), KAPPA_GAP_MAX)
            kl = max(kh - gap, KAPPA_MIN_LO)
        else:
            kh, kl = kh_l, kl_l              # LATCHED

        if collect:
            tr_amb[r] = amb
            tr_kh[r] = kh
            tr_kl[r] = kl
            tr_feat[r] = fv

        if state == 0:
            if b >= amb + kh:                # an ADD and a COMPARE
                state = 1
                kh_l, kl_l, amb_l = kh, kl, amb
        else:
            if b < amb_l + kl_l:
                state = 0
        trig[r] = state

    out = {"trig": trig}
    if collect:
        out.update(b_amb=tr_amb, kappa_h=tr_kh, kappa_l=tr_kl, feat=tr_feat)
    return out
