"""Fitting the three ATE families and quantising them to int8.

All three families regress the SAME two targets (kappa_H*, kappa_L*) from the
SAME six causal features and differ only in hypothesis class:

    ATE-Q : linear                 6 -> 2          12 MACs
    ATE-S : additive stumps        S comparisons   0  multipliers
    ATE-M : MLP with ReLU          6 -> H -> 2     6H + 2H MACs

Loss is the pinball (quantile) loss.  kappa_H uses tau = 0.8 because
under-predicting the high margin causes false alarms, which is the expensive
error; kappa_L uses tau = 0.5.
"""

from __future__ import annotations
import numpy as np

from gs2_core import ATEQ, ATES, ATEM, N_FEAT

TAU_H = 0.6
TAU_L = 0.5


def pinball_grad(pred, targ, tau):
    """d/dpred of the pinball loss, elementwise."""
    e = targ - pred
    return np.where(e >= 0, -tau, (1.0 - tau))


def standardiser(X):
    mean = X.mean(0)
    sd = X.std(0)
    sd[sd < 1e-6] = 1.0
    return mean, 1.0 / sd


# ----------------------------------------------------------------------------
# a tiny Adam trainer shared by ATE-Q (no hidden layer) and ATE-M
# ----------------------------------------------------------------------------

def _adam(params, grads_fn, epochs, batch, n, rng, lr=0.02):
    m = [np.zeros_like(p) for p in params]
    v = [np.zeros_like(p) for p in params]
    b1, b2, eps = 0.9, 0.999, 1e-8
    step = 0
    for ep in range(epochs):
        idx = rng.permutation(n)
        for s in range(0, n, batch):
            sel = idx[s:s + batch]
            gs = grads_fn(sel)
            step += 1
            for i, g in enumerate(gs):
                m[i] = b1 * m[i] + (1 - b1) * g
                v[i] = b2 * v[i] + (1 - b2) * g * g
                mh = m[i] / (1 - b1 ** step)
                vh = v[i] / (1 - b2 ** step)
                params[i] -= lr * mh / (np.sqrt(vh) + eps)
    return params


def fit_linear(X, Y, seed=0, epochs=60, batch=512, lr=0.02):
    mean, inv_sd = standardiser(X)
    Z = (X - mean) * inv_sd
    n = Z.shape[0]
    rng = np.random.default_rng(seed)
    W = rng.normal(0, 0.05, (2, N_FEAT))
    b = np.array([Y[:, 0].mean(), Y[:, 1].mean()])
    taus = np.array([TAU_H, TAU_L])

    def grads(sel):
        z = Z[sel]
        y = Y[sel]
        p = z @ W.T + b
        g = pinball_grad(p, y, taus) / sel.size          # (B,2)
        return [g.T @ z, g.sum(0)]

    W, b = _adam([W, b], grads, epochs, batch, n, rng, lr)
    return ATEQ(W, b, mean, inv_sd)


def fit_mlp(X, Y, hidden=8, seed=0, epochs=80, batch=512, lr=0.02):
    mean, inv_sd = standardiser(X)
    Z = (X - mean) * inv_sd
    n = Z.shape[0]
    rng = np.random.default_rng(seed)
    W1 = rng.normal(0, np.sqrt(2.0 / N_FEAT), (hidden, N_FEAT))
    b1 = np.zeros(hidden)
    W2 = rng.normal(0, np.sqrt(2.0 / hidden), (2, hidden))
    b2 = np.array([Y[:, 0].mean(), Y[:, 1].mean()])
    taus = np.array([TAU_H, TAU_L])

    def grads(sel):
        z = Z[sel]
        y = Y[sel]
        a = z @ W1.T + b1
        h = np.maximum(a, 0.0)
        p = h @ W2.T + b2
        g = pinball_grad(p, y, taus) / sel.size
        gW2 = g.T @ h
        gb2 = g.sum(0)
        gh = g @ W2
        ga = gh * (a > 0)
        return [ga.T @ z, ga.sum(0), gW2, gb2]

    W1, b1, W2, b2 = _adam([W1, b1, W2, b2], grads, epochs, batch, n, rng, lr)
    return ATEM(W1, b1, W2, b2, mean, inv_sd)


def fit_stumps(X, Y, n_stumps=16, seed=0, lr=0.15, n_thr=32):
    """Gradient boosting with depth-1 trees under the pinball loss.
    Both outputs share the stump set so the hardware evaluates one comparison
    per stump and adds a 2-vector."""
    mean, inv_sd = standardiser(X)
    Z = (X - mean) * inv_sd
    n = Z.shape[0]
    taus = np.array([TAU_H, TAU_L])
    base = np.array([np.quantile(Y[:, 0], TAU_H), np.quantile(Y[:, 1], TAU_L)])
    pred = np.tile(base, (n, 1))

    qs = np.linspace(0.05, 0.95, n_thr)
    cand = [np.quantile(Z[:, j], qs) for j in range(N_FEAT)]

    feat, thr, lo, hi = [], [], [], []
    for _ in range(n_stumps):
        g = pinball_grad(pred, Y, taus)          # (n,2) negative gradient = -g
        best = None
        for j in range(N_FEAT):
            zj = Z[:, j]
            for t in np.unique(cand[j]):
                m = zj >= t
                if m.sum() < 16 or (~m).sum() < 16:
                    continue
                vh = -g[m].mean(0)
                vl = -g[~m].mean(0)
                gain = (m.sum() * (vh ** 2).sum() + (~m).sum() * (vl ** 2).sum())
                if best is None or gain > best[0]:
                    best = (gain, j, t, vl, vh, m)
        if best is None:
            break
        _, j, t, vl, vh, m = best
        # line search on the step size in the pinball loss (scalar per output)
        step = lr * np.array([np.std(Y[:, 0]), np.std(Y[:, 1])]) * 2.0
        dlo, dhi = vl * step, vh * step
        pred[m] += dhi
        pred[~m] += dlo
        feat.append(j); thr.append(t); lo.append(dlo); hi.append(dhi)

    return ATES(base, feat, thr, np.array(lo), np.array(hi), mean, inv_sd)


# ----------------------------------------------------------------------------
# int8 quantisation
# ----------------------------------------------------------------------------

def _q(a, bits):
    lim = float(np.max(np.abs(a))) if a.size else 1.0
    if lim <= 0:
        lim = 1.0
    qmax = 2 ** (bits - 1) - 1
    scale = lim / qmax
    qa = np.clip(np.round(a / scale), -qmax, qmax)
    return qa, scale


def quantise_linear(m: ATEQ, wbits=8):
    qW, sW = _q(m.W, wbits)
    return ATEQ(qW * sW, m.b, m.mean, m.inv_sd), dict(qW=qW, sW=sW, wbits=wbits)


def quantise_mlp(m: ATEM, wbits=8):
    q1, s1 = _q(m.W1, wbits)
    q2, s2 = _q(m.W2, wbits)
    return (ATEM(q1 * s1, m.b1, q2 * s2, m.b2, m.mean, m.inv_sd),
            dict(qW1=q1, sW1=s1, qW2=q2, sW2=s2, wbits=wbits))


def quantise_stumps(m: ATES, wbits=8):
    qt, st = _q(m.thr, wbits)
    ql, sl = _q(m.lo, wbits)
    qh, sh = _q(m.hi, wbits)
    return (ATES(m.base, m.feat, qt * st, ql * sl, qh * sh, m.mean, m.inv_sd),
            dict(qthr=qt, sthr=st, qlo=ql, slo=sl, qhi=qh, shi=sh, wbits=wbits))


# ----------------------------------------------------------------------------
# training-set assembly from synthetic channels
# ----------------------------------------------------------------------------

def assemble(channels, max_per_chan=64, seed=0, ambient_only=True,
             target=("kh_opt", "gap_opt")):
    """One training row per sampled report: features seen so far -> the
    channel's scalar required margins."""
    rng = np.random.default_rng(seed)
    Xs, Ys = [], []
    for c in channels:
        n = c["F"].shape[0]
        mask = ~c["truth"] if ambient_only else np.ones(n, bool)
        idx = np.where(mask)[0]
        if idx.size == 0:
            continue
        if idx.size > max_per_chan:
            idx = rng.choice(idx, max_per_chan, replace=False)
        Xs.append(c["F"][idx])
        Ys.append(np.tile([c[target[0]], c[target[1]]], (idx.size, 1)))
    return np.vstack(Xs), np.vstack(Ys)


# ----------------------------------------------------------------------------
# decision-cost calibration
# ----------------------------------------------------------------------------

class Biased:
    """Wraps an ATE and adds a single learned scalar to kappa_H.

    Regressing kappa_H^opt under a symmetric loss is not the same as maximising
    F1: under-predicting the margin costs many false-positive reports, while
    over-predicting costs only a few report at the edge of an event, because a
    real event clears the ambient floor by several octaves.  One scalar, fitted
    on held-out SYNTHETIC channels only, absorbs that asymmetry.  In hardware it
    is folded into the output bias, so it costs nothing.
    """

    def __init__(self, base, beta_h=0.0, beta_l=0.0):
        self.base = base
        self.beta_h = float(beta_h)
        self.beta_l = float(beta_l)
        self.name = getattr(base, "name", "ATE") + "+bias"

    def predict(self, f):
        kh, kl = self.base.predict(f)
        return kh + self.beta_h, kl + self.beta_l


def calibrate_bias(model, channels, score_fn, grid=None):
    """Pick the scalar offset that maximises `score_fn` on held-out channels."""
    grid = grid if grid is not None else np.arange(-2.0, 6.01, 0.5)
    best = None
    for b in grid:
        s = score_fn(Biased(model, float(b)))
        if best is None or s > best[0]:
            best = (s, float(b))
    return Biased(model, best[1]), best[1], best[0]
