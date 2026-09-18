"""Publication-ready figures, generated directly from the Part 1 output files.

IEEE column widths: 3.5 in (single) and 7.16 in (double).
Every figure is written as a vector PDF and a 600 dpi PNG.
Palette: Okabe-Ito subset, validated for colour-vision deficiency
(worst adjacent pair dE 9.6 deutan, 18.4 normal); every series also carries a
distinct dash pattern or marker so the figures survive greyscale printing.
"""
from __future__ import annotations
import os, pickle, sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gs2_core import KAPPA_MIN_HI, run_engine, log2_hw

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(os.path.join(HERE, "..", "out"))
FIGS = os.path.abspath(os.path.join(HERE, "..", "figs"))
os.makedirs(FIGS, exist_ok=True)

W1, W2 = 3.5, 7.16
BLUE, ORANGE, GREEN, SKY, PINK = "#0072B2", "#D55E00", "#009E73", "#56B4E9", "#CC79A7"
C = [BLUE, ORANGE, GREEN, SKY, PINK]
INK, INK2, MUTED, FAINT = "#1a1a1a", "#4d4d4d", "#8c8c8c", "#c9c9c9"
MARKERS = ["o", "s", "^", "D", "v", "P"]
DASH = [(), (5, 2), (1, 1.7), (6, 2, 1, 2), (3, 1.4, 1, 1.4)]

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "axes.labelsize": 10.5, "axes.titlesize": 10.5,
    "xtick.labelsize": 9, "ytick.labelsize": 9, "legend.fontsize": 9,
    "axes.edgecolor": INK2, "axes.linewidth": 0.8,
    "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "axes.labelcolor": INK,
    "axes.spines.top": False, "axes.spines.right": False,
    "lines.linewidth": 1.5, "figure.dpi": 120,
    "legend.frameon": False, "savefig.bbox": "tight", "savefig.pad_inches": 0.02,
})


def save(fig, name):
    fig.savefig(os.path.join(FIGS, name + ".pdf"))
    fig.savefig(os.path.join(FIGS, name + ".png"), dpi=600)
    plt.close(fig)
    print("  wrote", name)


def is_current(ch):
    return ch.startswith("Current")


# ---------------------------------------------------------------------------

def fig_motivation(chans, kopt):
    fig, ax = plt.subplots(1, 2, figsize=(W2, 2.6))
    raw, nrm = [], []
    for c in chans:
        v = c["valid"]
        raw.append(np.percentile(
            log2_hw(np.maximum(c["proc"]["Lmax"][v], 1e-30)), 10.0))
        nrm.append(np.percentile(c["proc"]["b"][v], 10.0))
    raw, nrm = np.array(raw), np.array(nrm)
    x = np.arange(len(chans))

    a = ax[0]
    a.scatter(x, raw, s=15, facecolor="none", edgecolor=MUTED, linewidth=1.0,
              marker="s")
    a.scatter(x, nrm, s=15, color=BLUE, marker="o")
    a.set_xlabel("GESL channel")
    a.set_ylabel("ambient floor  [octaves]")
    a.set_ylim(nrm.min() - 16, raw.max() + 13)
    a.annotate(f"raw  $\\log_2 L$\nspread {raw.max()-raw.min():.0f} octaves",
               (0.02, 0.97), xycoords="axes fraction", va="top", fontsize=9,
               color=MUTED)
    a.annotate(f"normalised  $b=\\log_2\\Lambda$\nspread "
               f"{nrm.max()-nrm.min():.0f} octaves",
               (0.02, 0.17), xycoords="axes fraction", va="top", fontsize=9,
               color=BLUE)
    a.set_title("(a) the residual carries the sensor scale", loc="left", pad=6)

    b = ax[1]
    order = np.argsort(kopt)
    cols = [ORANGE if is_current(chans[i]["ch"]) else BLUE for i in order]
    b.bar(np.arange(len(kopt)), kopt[order], color=cols, width=0.82, linewidth=0)
    b.axhline(KAPPA_MIN_HI, color=INK, ls="--", lw=1.1)
    b.annotate("physical floor $\\log_2 10$", (0.4, KAPPA_MIN_HI + 0.3),
               fontsize=9, color=INK)
    b.set_xlabel("GESL channel, sorted by required margin")
    b.set_ylabel("$\\kappa_H$ in hindsight  [octaves]")
    b.set_ylim(0, kopt.max() * 1.18)
    b.legend(handles=[Patch(color=BLUE, label="voltage"),
                      Patch(color=ORANGE, label="current")],
             loc="upper left", handlelength=1.1, handletextpad=0.4)
    b.set_title("(b) a $45\\times$ spread in the margin each channel needs",
                loc="left", pad=6)
    fig.subplots_adjust(wspace=0.32)
    save(fig, "fig_motivation")


def _case(axcol, c, model, floor, tlim, title):
    p = c["proc"]
    r = run_engine(p["b"], p["lv"], p["f"], model, kappa_min_hi=floor,
                   collect=True, dead=p["gate_r"])
    t = p["edges"][:-1] / c["fs"]
    ts = np.arange(p["mag"].size) / c["fs"]
    ms = (ts >= tlim[0]) & (ts <= tlim[1])
    mr = (t >= tlim[0]) & (t <= tlim[1])
    gated = p["gate_r"]

    unit = "kA" if is_current(c["ch"]) else "kV"
    raw = (p["est_v"] + p["resid"]) / 1e3
    axcol[0].plot(ts[ms], raw[ms], color=INK2, lw=0.5)
    axcol[0].set_ylabel(f"waveform\n[{unit}]", labelpad=2)
    axcol[0].set_title(title, loc="left", pad=5)

    bb = np.where(gated, np.nan, p["b"])
    th = np.where(gated, np.nan, r["b_amb"] + r["kappa_h"])
    ab = np.where(gated, np.nan, r["b_amb"])
    axcol[1].plot(t[mr], bb[mr], color=BLUE, lw=1.0)
    axcol[1].plot(t[mr], ab[mr], color=INK, ls="--", lw=1.1)
    axcol[1].plot(t[mr], th[mr], color=ORANGE, lw=1.4)
    axcol[1].set_ylabel("octaves", labelpad=2)

    axcol[2].fill_between(t[mr], 0, c["truth"][mr].astype(float), step="mid",
                          color=FAINT, linewidth=0)
    axcol[2].step(t[mr], r["trig"][mr].astype(float) * 0.8, where="mid",
                  color=ORANGE, lw=1.4)
    g = gated[mr].astype(float)
    if g.any():
        axcol[2].fill_between(t[mr], 0, g, step="mid", color=PINK, alpha=0.30,
                              linewidth=0)
    axcol[2].set_yticks([])
    axcol[2].set_ylim(0, 1.02)
    axcol[2].set_xlabel("time [s]")
    for a in axcol:
        a.set_xlim(*tlim)


def fig_cases(chans, model, floor):
    fig, ax = plt.subplots(3, 2, figsize=(W2, 3.6), sharex="col",
                           gridspec_kw=dict(height_ratios=[1.0, 1.25, 0.34],
                                            hspace=0.20, wspace=0.24))
    c1 = [x for x in chans if x["rid"] == 907 and x["ch"] == "Current.Ic"][0]
    c2 = [x for x in chans if x["rid"] == 677 and x["ch"] == "Current.Ia"][0]
    _case(ax[:, 0], c1, model, floor, (1.94, 2.12),
          "(a) record 907: 1-cycle BC fault")
    _case(ax[:, 1], c2, model, floor, (1.7, 6.1),
          "(b) record 677: ABG fault, 2.2 s open, reclose")
    handles = [Line2D([], [], color=BLUE, lw=1.4, label="$b=\\log_2\\Lambda$"),
               Line2D([], [], color=INK, ls="--", lw=1.2, label="$b_{amb}$"),
               Line2D([], [], color=ORANGE, lw=1.6,
                      label="$b_{amb}+\\kappa_H$ (ATE)"),
               Patch(color=FAINT, label="reference event"),
               Patch(color=PINK, alpha=0.30, label="de-energised, gated")]
    fig.legend(handles=handles, ncol=5, loc="lower center",
               bbox_to_anchor=(0.5, -0.10), handlelength=1.5,
               handletextpad=0.4, columnspacing=1.1)
    save(fig, "fig_case_studies")


def fig_tracking(chans, models, floor, kopt, deployed_key, sweep):
    fig, ax = plt.subplots(1, 2, figsize=(W2, 2.7))
    a = ax[0]
    fams = [("ATE-Q", "q8"), ("ATE-S", "s8"), ("ATE-M", "m8")]
    for i, (nm, k) in enumerate(fams):
        pm = np.array([np.median([models[k].predict(f)[0]
                                  for f in c["F"][c["valid"]]]) for c in chans])
        a.scatter(kopt, pm, s=26, marker=MARKERS[i], edgecolor=C[i],
                  facecolor=C[i] if k == deployed_key else "none", linewidth=1.2,
                  label=f"{nm}  ($r$={np.corrcoef(kopt, pm)[0,1]:.2f})")
    lim = (0, max(kopt.max(), 12) * 1.05)
    a.plot(lim, lim, color=MUTED, lw=0.9, ls=":")
    a.axhline(KAPPA_MIN_HI, color=INK, ls="--", lw=1.0)
    a.annotate("floor", (lim[1] * 0.02, KAPPA_MIN_HI + 0.22), fontsize=8.5)
    a.set_xlim(*lim)
    a.set_ylim(0, 7.4)
    a.set_xlabel("$\\kappa_H$ in hindsight  [octaves]")
    a.set_ylabel("ATE prediction, median  [octaves]")
    a.set_title("(a) does the engine rank the channels?", loc="left", pad=6)
    a.legend(loc="lower right", handletextpad=0.2, labelspacing=0.25,
             fontsize=8.5)

    b = ax[1]
    b.plot(sweep["floor"], sweep["ate_micro"], color=BLUE, marker="o", ms=4,
           label="ATE-M int8 + floor")
    b.plot(sweep["floor"], sweep["const_micro"], color=ORANGE, marker="s",
           ms=4, dashes=(5, 2), label="constant margin = floor")
    b.set_xlabel("$\\kappa_H$ floor  [octaves]")
    b.set_ylabel("micro $F_1$ on GESL")
    b.axvline(KAPPA_MIN_HI, color=INK, ls="--", lw=1.0)
    b.annotate("$\\log_2 10$", (KAPPA_MIN_HI + 0.15, 0.425), fontsize=9,
               va="top")
    b.set_ylim(0, 0.45)
    b.set_title("(b) the floor and the engine are complementary", loc="left",
                pad=6)
    b.legend(loc="lower left", handlelength=2.0, handletextpad=0.4,
             fontsize=8.5)
    fig.subplots_adjust(wspace=0.32)
    save(fig, "fig_threshold_tracking")


def fig_methods(agg, order, labels, oracle):
    fig, ax = plt.subplots(1, 2, figsize=(W2, 3.1))
    y = np.arange(len(order))[::-1]
    a = ax[0]
    for k, metric, off, hatch in [(0, "micro_f1", -0.19, None),
                                  (1, "macro_f1", 0.19, "///")]:
        vals = [agg.loc[m, metric] for m in order]
        cols = [MUTED if o else (BLUE if k == 0 else SKY)
                for o in oracle]
        a.barh(y + off, vals, height=0.36, color=cols, linewidth=0,
               hatch=hatch, edgecolor="white")
        for yy, vv in zip(y + off, vals):
            a.annotate(f"{vv:.3f}", (vv + 0.012, yy), va="center", fontsize=8,
                       color=INK2)
    a.set_yticks(y)
    a.set_yticklabels(labels)
    a.set_xlim(0, 1.12)
    a.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
    a.set_xlabel("$F_1$ on the six GESL records")
    a.legend(handles=[Patch(color=BLUE, label="micro (all reports pooled)"),
                      Patch(facecolor=SKY, hatch="///", edgecolor="white",
                            label="macro (event-bearing channels)"),
                      Patch(color=MUTED, label="offline oracle")],
             loc="upper center", bbox_to_anchor=(0.45, -0.28), ncol=1,
             handlelength=1.2, handletextpad=0.4, labelspacing=0.25,
             fontsize=8.2)
    a.set_title("(a) detection quality", loc="left", pad=6)

    b = ax[1]
    for i, m in enumerate(order):
        b.scatter(agg.loc[m, "duty_cycle"], agg.loc[m, "event_recall"], s=52,
                  marker=MARKERS[i % len(MARKERS)],
                  color=MUTED if oracle[i] else C[i % len(C)],
                  facecolor="none" if oracle[i] else
                  (MUTED if oracle[i] else C[i % len(C)]),
                  linewidth=1.4, zorder=3, label=labels[i])
    b.set_xlabel("duty cycle  [fraction of reports]")
    b.set_ylabel("event-window recall")
    b.set_xlim(-0.01, 0.26)
    b.set_ylim(0, 1.08)
    b.set_title("(b) bandwidth against coverage", loc="left", pad=6)
    b.legend(loc="lower right", fontsize=8.2, handletextpad=0.2,
             labelspacing=0.25)
    fig.subplots_adjust(wspace=0.32)
    save(fig, "fig_method_comparison")


def fig_calibration(cdf):
    fig, ax = plt.subplots(figsize=(W1, 2.4))
    cols = [c for c in cdf.columns if c != "horizon_s"]
    for i, c in enumerate(cols):
        ax.plot(cdf["horizon_s"], cdf[c], color=C[i % len(C)],
                marker=MARKERS[i % len(MARKERS)], ms=4.5,
                dashes=DASH[i % len(DASH)] if DASH[i % len(DASH)] else
                (None, None), label=c)
    ax.set_xscale("log")
    ax.set_xticks(cdf["horizon_s"])
    ax.set_xticklabels([f"{v:g}" for v in cdf["horizon_s"]])
    ax.minorticks_off()
    ax.set_xlabel("observation horizon  [s]")
    ax.set_ylabel("margin MAE  [octaves]")
    ax.legend(handlelength=2.0, handletextpad=0.4, labelspacing=0.22,
              fontsize=8.5)
    save(fig, "fig_calibration")


def main():
    chans = pickle.load(open(os.path.join(OUT, "gesl_channels.pkl"), "rb"))
    models = pickle.load(open(os.path.join(OUT, "ate_models.pkl"), "rb"))
    st = pickle.load(open(os.path.join(OUT, "state.pkl"), "rb"))
    floor = st["deployed_floor"]
    key = {"ATE-Q": "q8", "ATE-S": "s8", "ATE-M": "m8"}[st["deployed_family"]]
    kopt = pickle.load(open(os.path.join(OUT, "kappa_opt_real.pkl"), "rb"))
    agg = pd.read_csv(os.path.join(OUT, "table_aggregate.csv"), index_col=0)
    cdf = pd.read_csv(os.path.join(OUT, "table_calibration_speed.csv"))

    print("figures ->", FIGS)
    fig_motivation(chans, kopt)
    fig_cases(chans, models[key], floor)
    sweep = pd.read_csv(os.path.join(OUT, 'table_floor_sweep_gesl.csv'))
    fig_tracking(chans, models, floor, kopt, key, sweep)

    order = [st["deployed_name"], "ATE-M int8 (leave-one-record-out)",
             "fixed margin (tuned on synthetic)", "empirical-Q (causal)",
             "v1-fixed (TH=1e7, TL=300)",
             "fixed margin (best constant, offline oracle)",
             "hindsight ceiling (offline oracle)"]
    labels = [f"ATE-{st['deployed_family'][-1]} int8 + floor",
              "ATE-M int8, leave-one-record-out", "fixed margin (synthetic)",
              "empirical-$Q$", "v1 fixed thresholds",
              "best constant, hindsight", "hindsight ceiling"]
    oracle = [False, False, False, False, False, True, True]
    keep = [i for i, o in enumerate(order) if o in agg.index]
    fig_methods(agg, [order[i] for i in keep], [labels[i] for i in keep],
                [oracle[i] for i in keep])
    fig_calibration(cdf)


if __name__ == "__main__":
    main()
