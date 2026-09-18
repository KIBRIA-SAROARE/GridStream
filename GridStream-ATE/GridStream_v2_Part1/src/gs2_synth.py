"""Synthetic three-phase environments used ONLY for fitting the ATE.

No GESL record is ever used to fit anything.  Each environment is a synthetic
site with its own sensor scale, ambient distortion floor, noise level, harmonic
content and frequency behaviour.  Its three phases are three channels, each with
its own required margin kappa*.
"""

from __future__ import annotations
import math
import numpy as np

from gs2_core import (FN, FR, EPS, N_FEAT, AmbientTracker, FeatureBank,
                      Q_HI, Q_LO, KAPPA_HI_PAD, log2_hw, log2_hw_scalar,
                      report_edges, reduce_max, reduce_last, reduce_mean,
                      causal_vbar_log2)
from gs2_data import process_channel, oracle_labels, report_truth

SYN_FS = 15360.0
SYN_DURATIONS = (2.0, 4.0, 6.0, 8.0, 10.0, 12.0)


def _pink(n, rng):
    """1/f noise, unit RMS -- models the slow drift of a real ambient floor."""
    f = np.fft.rfftfreq(n, 1.0)
    s = np.zeros_like(f)
    s[1:] = 1.0 / np.sqrt(f[1:])
    ph = rng.uniform(0, 2 * math.pi, f.size)
    y = np.fft.irfft(s * np.exp(1j * ph), n)
    sd = y.std()
    return y / sd if sd > 0 else y


def _make_env(rng: np.random.Generator):
    dur = float(rng.choice(SYN_DURATIONS))
    n = int(SYN_FS * dur)
    t = np.arange(n) / SYN_FS

    amp = 10.0 ** rng.uniform(2.0, 5.0)               # sensor scale, 100 .. 1e5
    df = rng.uniform(0.0, 0.5)                        # frequency wander [Hz]
    fm = rng.uniform(0.02, 0.5)
    fi = FN + df * np.sin(2 * math.pi * fm * t + rng.uniform(0, 6.28)) \
        + rng.uniform(-0.05, 0.05) * t / max(dur, 1e-9)     # slow ramp
    ph = 2 * math.pi * np.cumsum(fi) / SYN_FS

    mflk = rng.uniform(0.0, 0.06)                     # flicker depth
    fflk = rng.uniform(0.5, 12.0)
    env_am = 1.0 + mflk * np.sin(2 * math.pi * fflk * t + rng.uniform(0, 6.28))

    harm_orders = [2, 3, 5, 7, 11, 13]
    harm_amp = 10.0 ** rng.uniform(-4.0, math.log10(0.12), size=len(harm_orders))
    harm_ph = rng.uniform(0, 6.28, size=(3, len(harm_orders)))
    # harmonics are NOT stationary in a real feeder: modulate them slowly
    harm_mod = 1.0 + (rng.uniform(0.0, 0.45) if rng.random() < 0.5
                      else 0.0) * _pink(n, rng)

    snr_db = rng.uniform(24.0, 80.0)
    noise_sd = amp / (10.0 ** (snr_db / 20.0))
    pink_frac = rng.uniform(0.0, 0.8)

    lsb = amp * 10.0 ** rng.uniform(-5.0, -2.5)       # ADC quantisation step

    # background non-stationarity that is NOT a reportable event: commutation
    # notches and small load-switching micro-transients
    notch_depth = rng.uniform(0.0, 0.012) if rng.random() < 0.35 else 0.0
    n_micro = int(rng.uniform(0, 6) * dur) if rng.random() < 0.5 else 0
    micro_windows = []

    # Operating-level variation.  A current channel on a real feeder can change
    # by one to two decades within a single recording (load change, breaker
    # operation upstream, a lightly loaded phase).  The normalised GOF is very
    # sensitive to this, so it must be present in training.
    lvl = np.ones(n)
    level_windows = []
    if rng.random() < 0.35:
        span = 10.0 ** rng.uniform(0.3, 2.0)          # 2x .. 100x
        if rng.random() < 0.5:                        # step to a new level
            k0 = int(rng.uniform(0.2, 0.8) * n)
            k1 = min(n, k0 + int(rng.uniform(0.1, 0.6) * n))
            lvl[k0:k1] = 1.0 / span
            ramp = max(2, int(SYN_FS * 0.01))
            lvl[k0:k0 + ramp] = np.linspace(1.0, 1.0 / span, ramp)
            lvl[max(0, k1 - ramp):k1] = np.linspace(1.0 / span, 1.0, ramp)
            # the two level transitions are genuine disturbances; record them
            pad = int(SYN_FS * 0.05)
            level_windows += [(max(0, k0 - pad), min(n, k0 + ramp + pad)),
                              (max(0, k1 - ramp - pad), min(n, k1 + pad))]
        else:                                         # slow drift
            lvl = np.exp2(np.log2(span) * 0.5 *
                          np.sin(2 * math.pi * rng.uniform(0.02, 0.2) * t
                                 + rng.uniform(0, 6.28)))

    chans = []
    for p in range(3):
        p0 = -2 * math.pi * p / 3.0
        unb = rng.uniform(0.93, 1.07)
        x = amp * unb * env_am * np.cos(ph + p0)
        for j, h in enumerate(harm_orders):
            x = x + amp * unb * harm_amp[j] * harm_mod * \
                np.cos(h * (ph + p0) + harm_ph[p, j])
        x = x * lvl                      # operating-level variation
        wn = rng.normal(0.0, 1.0, n)
        x = x + noise_sd * ((1 - pink_frac) * wn + pink_frac * _pink(n, rng))
        if notch_depth > 0:
            per = int(SYN_FS / FN / 6)                # 6-pulse commutation
            w = max(2, int(SYN_FS * 2e-4))
            k0 = int(rng.uniform(0, per))
            idx = np.arange(k0, n - w, per)
            for k in idx:
                x[k:k + w] -= amp * unb * notch_depth
        for _ in range(n_micro):
            k = int(rng.uniform(0, n - 200))
            m = int(rng.uniform(20, 200))
            micro_windows.append((k, k + m))
            tt = np.arange(m) / SYN_FS
            x[k:k + m] += amp * unb * 10.0 ** rng.uniform(-4.2, -2.0) * \
                np.exp(-tt / 0.002) * np.cos(2 * math.pi *
                                             rng.uniform(300, 3000) * tt)
        chans.append(x)

    # ---- events -------------------------------------------------------------
    n_ev = rng.integers(0, 3)
    ev_windows = []
    for _ in range(int(n_ev)):
        kind = rng.choice(["fault", "impulse", "arcing", "switching"])
        cyc = SYN_FS / FN
        if kind == "fault":
            elen = int(rng.uniform(1.0, 60.0) * cyc)
        elif kind == "impulse":
            elen = int(rng.uniform(0.05, 2.0) * cyc)
        elif kind == "arcing":
            elen = int(rng.uniform(2.0, 30.0) * cyc)
        else:
            elen = int(rng.uniform(0.2, 4.0) * cyc)
        s = int(rng.uniform(0.25, 0.90) * n)
        e = min(n, s + max(8, elen))
        if any(not (e < s2 or s > e2) for s2, e2 in ev_windows):
            continue
        sev = 10.0 ** rng.uniform(-1.0, 0.7)          # 0.1 .. 5 pu
        aff = rng.choice([[0], [1], [2], [0, 1], [1, 2], [0, 1, 2]], p=None) \
            if False else [int(k) for k in rng.choice(3, size=int(rng.integers(1, 4)),
                                                      replace=False)]
        for p in aff:
            seg = slice(s, e)
            m = e - s
            tt = np.arange(m) / SYN_FS
            if kind == "fault":
                sag = rng.uniform(0.1, 0.9)
                chans[p][seg] *= sag
                chans[p][seg] += amp * sev * 0.3 * np.exp(-tt / 0.01) * \
                    np.cos(2 * math.pi * rng.uniform(300, 900) * tt)
            elif kind == "impulse":
                chans[p][seg] += amp * sev * np.exp(-tt / 0.0008) * \
                    np.cos(2 * math.pi * rng.uniform(1000, 5000) * tt)
            elif kind == "arcing":
                per = int(SYN_FS / FN / 2)
                burst = np.zeros(m)
                for k0 in range(0, m, per):
                    k1 = min(m, k0 + max(2, per // 8))
                    burst[k0:k1] = 1.0
                chans[p][seg] += amp * sev * 0.4 * burst * \
                    np.cos(2 * math.pi * rng.uniform(1500, 4000) * tt)
            else:
                chans[p][seg] += amp * sev * 0.5 * np.exp(-tt / 0.003) * \
                    np.cos(2 * math.pi * rng.uniform(400, 2000) * tt)
        ev_windows.append((s, e))

    chans = [np.round(c / lsb) * lsb for c in chans]
    return chans, ev_windows, micro_windows + level_windows


def ambient_pass(b, lv, f, dead=None):
    """Run the causal tracker + feature bank with the FSM held in state 0.
    Returns per-report excess d and the feature matrix.  This is what the
    training targets and the calibration-speed study are built from."""
    nrep = b.size
    trk = AmbientTracker()
    fb = FeatureBank()
    d = np.empty(nrep)
    F = np.empty((nrep, N_FEAT))
    for r in range(nrep):
        if dead is not None and dead[r]:
            d[r] = 0.0
            F[r] = fb.vector(trk.b_amb)
            continue
        amb = trk.update(float(b[r]))
        d[r] = float(b[r]) - amb
        fb.update(d[r], float(lv[r]), float(f[r]), hold=False)
        F[r] = fb.vector(amb)
    return d, F


OPT_GRID = np.round(np.arange(0.5, 14.01, 0.5), 2)
OPT_GAPS = (0.5, 1.0, 2.0, 4.0)


def optimal_margin(b, lv, f, dead, valid, truth):
    """The margin a perfectly-informed designer would program into THIS channel.

    For a channel that contains labelled events it is the kappa_H that maximises
    the report-level F1 of the deployed FSM; for a quiet channel it is the
    smallest kappa_H that produces no trigger at all.  This -- not the 0.998
    ambient quantile -- is what the ATE is trained to predict, because the
    quantile is a description of the ambient distribution, not the decision
    boundary that minimises the detection error.
    """
    from gs2_core import ATEConst, run_engine
    from gs2_data import prf
    t = truth[valid].astype(bool)
    best = None
    for kh in OPT_GRID:
        for gp in OPT_GAPS:
            r = run_engine(b, lv, f, ATEConst(kh, gp), kappa_min_hi=0.0,
                           dead=dead)
            p = r["trig"][valid].astype(bool)
            if t.any():
                score = prf(p, t)["f1"]
            else:
                score = -float(p.mean())      # quiet: fewest triggered reports
            if best is None or score > best[0]:
                best = (score, float(kh), float(gp))
        if not t.any() and best[0] == 0.0:
            break
    return best[1], best[2], best[0]


def build_dataset(n_env: int, seed: int, use_cordic: bool = False):
    """Returns a list of channel dicts.  `use_cordic=False` here only for speed;
    the GESL evaluation uses the exact v1 CORDIC chain."""
    rng = np.random.default_rng(seed)
    out = []
    for i in range(n_env):
        chans, evw, micw = _make_env(rng)
        for p, x in enumerate(chans):
            proc = process_channel(x, SYN_FS, use_cordic=use_cordic)
            edges = proc["edges"]
            lab = np.zeros(x.size, dtype=bool)
            for s, e in evw:
                lab[s:e] = True
            truth_exact = report_truth(lab, edges)
            labm = np.zeros(x.size, dtype=bool)
            for s, e in micw:
                labm[s:e] = True
            truth_micro = report_truth(labm, edges)
            lab_or, _, _ = oracle_labels(proc, SYN_FS)
            truth_oracle = report_truth(lab_or, edges)

            d, F = ambient_pass(proc["b"], proc["lv"], proc["f"], proc["gate_r"])
            v = proc["valid_r"] & ~proc["dead_r"]
            # the ORACLE label is the truth used everywhere, exactly as on the
            # GESL records; the exact injected windows are kept only to
            # validate the oracle itself.
            amb_mask = v & ~truth_oracle
            if amb_mask.sum() < 32:
                continue
            kh = float(np.quantile(d[amb_mask], Q_HI)) + KAPPA_HI_PAD
            kl = float(np.quantile(d[amb_mask], Q_LO))
            kh_opt, gap_opt, f1_opt = optimal_margin(
                proc["b"], proc["lv"], proc["f"], proc["gate_r"], v,
                truth_oracle)
            out.append(dict(env=i, phase=p, b=proc["b"], lv=proc["lv"],
                            f=proc["f"], d=d, F=F, valid=v,
                            dead=proc["gate_r"],
                            truth=truth_oracle, truth_exact=truth_exact,
                            truth_micro=truth_micro,
                            kh_star=kh, kl_star=kl, edges=edges,
                            kh_opt=kh_opt, gap_opt=gap_opt,
                            f1_opt=f1_opt))
    return out
