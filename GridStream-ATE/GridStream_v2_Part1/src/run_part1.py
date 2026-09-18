"""GridStream-v2 Part 1 -- end-to-end reproducible run.

    python run_part1.py [--records 45,55,677,901,907,971] [--nenv 220]

Writes every table as a CSV under ../out plus numbers.json.
Nothing in this script fits anything on a GESL record except the baselines that
are explicitly labelled `oracle` or `LORO`.
"""

from __future__ import annotations
import argparse, json, math, os, pickle, sys, time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gs2_core import (FN, FR, N_FEAT, FEATURE_NAMES, KAPPA_MIN_HI, KAPPA_MIN_LO,
                      KAPPA_GAP_MIN, KAPPA_GAP_MAX, KAPPA_MAX_HI, Q_HI, Q_LO, KAPPA_HI_PAD,
                      ATEConst, ATEQ, ATES, ATEM, NTAPS, FIR_CUTOFF_HZ,
                      FIR_WINDOW, N_ACQ, MS_SUBWIN, MS_NSUB, ALPHA_SLOW,
                      ALPHA_V, MAX_DECAY, VBAR_HOLD_OCT, VBAR_HOLD_MAX,
                      LOG2_ROM_N, run_engine)
import gs2_data as D
import gs2_eval as E
import gs2_synth as S
import gs2_train as T

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(os.path.join(HERE, "..", "out"))
DATA = os.path.abspath(os.path.join(HERE, "..", "data"))
os.makedirs(OUT, exist_ok=True)

SEED_TRAIN = 20260831
SEED_TEST = 777
KGRID = np.round(np.arange(0.25, 24.01, 0.25), 2)


def log(*a):
    print(*a, flush=True)


# ---------------------------------------------------------------------------

def provenance(records):
    from scipy.signal import firwin
    from gs2_core import cordic_vec, log2_hw
    import re
    rows = []
    repo = os.path.abspath(os.path.join(HERE, "..", "..", "repo",
                                        "et_pmu_scaled.py"))
    if os.path.exists(repo):
        src = open(repo).read()
        c = np.array([float(x) for x in re.search(
            r"fir_coeffs_orig = \[(.*?)\]", src, re.S).group(1)
            .replace("\n", "").split(",") if x.strip()])
        h = firwin(NTAPS, FIR_CUTOFF_HZ, fs=15360.0, window=FIR_WINDOW)
        rows += [
            dict(check="v1 FIR array vs firwin(257, 10 Hz, hamming)",
                 value="max |diff| = %.2e" % np.abs(h - c).max(),
                 note="the v1 design is reproduced, but the transcribed array "
                      "in et_pmu_scaled.py carries three tap-level defects"),
            dict(check="v1 FIR array symmetry",
                 value="max |c - reverse(c)| = %.2e" % np.abs(c - c[::-1]).max(),
                 note="a linear-phase FIR must be exactly symmetric; tap 88 is "
                      "duplicated, tap 139 is dropped, tap 239 is duplicated"),
            dict(check="v1 FIR DC gain",
                 value="sum(taps) = %.6f" % c.sum(),
                 note="should be 1.0; the defects cost %.2f %% of DC gain"
                      % (100 * (1 - c.sum()))),
        ]
    rng = np.random.default_rng(0)
    xx = rng.normal(size=20000) * 1e4
    yy = rng.normal(size=20000) * 1e4
    m, a = cordic_vec(xx, yy)
    rows.append(dict(check="16-iteration CORDIC vs exact atan2/hypot",
                     value="max rel. magnitude error %.2e, max angle error "
                           "%.2e rad" % (np.abs(m / np.hypot(xx, yy) - 1).max(),
                                         np.abs(((a - np.arctan2(yy, xx) + np.pi)
                                                 % (2 * np.pi)) - np.pi).max()),
                     note="v1 front end, used unchanged"))
    u = np.exp2(rng.uniform(-40, 40, 200000))
    rows.append(dict(check="hardware log2 (priority encoder + %d-entry ROM)"
                           % LOG2_ROM_N,
                     value="max error %.4f octaves"
                           % np.abs(log2_hw(u) - np.log2(u)).max(),
                     note="identical primitive in Python and in exported C++"))
    for rid in records:
        rec = D.load_record(DATA, rid)
        rows.append(dict(check="GESL time base, record %d" % rid,
                         value="n/fs = %.4f s vs metadata Duration %.4f s"
                               % (rec["n"] / rec["fs"], rec["duration"]),
                         note="metadata Duration is truncated to 3 decimals"))
    return pd.DataFrame(rows)


def get_synth(n_env, seed, tag):
    cache = os.path.join(OUT, f"synth_{tag}_{n_env}_{seed}.pkl")
    if os.path.exists(cache):
        return pickle.load(open(cache, "rb"))
    t0 = time.time()
    ds = S.build_dataset(n_env, seed)
    log(f"  synthetic {tag}: {len(ds)} channels / {n_env} environments "
        f"in {time.time() - t0:.1f}s")
    pickle.dump(ds, open(cache, "wb"))
    return ds


def eval_synth(channels, ate, kappa_min_hi):
    tp = fp = fn = 0
    f1s, duty, faq = [], [], []
    nw = nc = 0
    for c in channels:
        r = run_engine(c["b"], c["lv"], c["f"], ate, kappa_min_hi=kappa_min_hi,
                       dead=c["dead"])
        v = c["valid"]
        p = r["trig"][v].astype(bool)
        t = c["truth"][v].astype(bool)
        m = D.prf(p, t)
        tp += m["tp"]; fp += m["fp"]; fn += m["fn"]
        em = D.event_metrics(p, t)
        nw += em["n_event_windows"]; nc += em["n_caught"]
        duty.append(em["duty_cycle"])
        (f1s if t.any() else faq).append(m["f1"] if t.any()
                                         else em["false_alarm_runs"])
    pr = tp / (tp + fp) if tp + fp else 0.0
    rc = tp / (tp + fn) if tp + fn else 0.0
    return dict(micro_f1=2 * pr * rc / (pr + rc) if pr + rc else 0.0,
                macro_f1=float(np.mean(f1s)) if f1s else float("nan"),
                precision=pr, recall=rc,
                event_recall=nc / nw if nw else float("nan"),
                duty_cycle=float(np.mean(duty)),
                false_alarm_runs_quiet=int(np.sum(faq)) if faq else 0)


def per_record_table(rows, methods):
    """Mean F1 per record over that record's event-bearing channels."""
    df = pd.DataFrame(rows)
    df = df[df["has_events"]]
    piv = df.pivot_table(index="rid", columns="method", values="f1",
                         aggfunc="mean")
    keep = [m for m in methods if m in piv.columns]
    piv = piv[keep]
    piv.loc["mean"] = piv.mean()
    return piv


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--records", default=",".join(str(r) for r in D.RECORD_IDS))
    ap.add_argument("--nenv", type=int, default=220)
    ap.add_argument("--ntest", type=int, default=60)
    args = ap.parse_args()
    records = [int(r) for r in args.records.split(",") if r.strip()]
    numbers = {"records": records, "generated": time.strftime("%Y-%m-%d %H:%M")}
    log(f"=== GridStream-v2 Part 1 ===  records {records}")

    prov = provenance(records)
    prov.to_csv(os.path.join(OUT, "table_provenance.csv"), index=False)
    log("\n[0] provenance\n" + prov.to_string(index=False))

    # ---------------- synthetic ------------------------------------------
    log("\n[1] synthetic environments (training data -- no GESL record used)")
    tr = get_synth(args.nenv, SEED_TRAIN, "train")
    te = get_synth(args.ntest, SEED_TEST, "test")
    X, Y = T.assemble(tr, max_per_chan=64, seed=1)
    kh_tr = np.array([c["kh_star"] for c in tr])
    log(f"  train {len(tr)} ch / held-out {len(te)} ch / {X.shape[0]} rows")
    log("  synthetic kappa_H*: min %.2f med %.2f p95 %.2f max %.2f"
        % (kh_tr.min(), np.median(kh_tr), np.percentile(kh_tr, 95), kh_tr.max()))
    numbers["synthetic"] = dict(n_train_env=args.nenv, n_test_env=args.ntest,
                                n_train_ch=len(tr), n_test_ch=len(te),
                                n_rows=int(X.shape[0]),
                                kh_star_min=float(kh_tr.min()),
                                kh_star_med=float(np.median(kh_tr)),
                                kh_star_max=float(kh_tr.max()))

    # oracle validation against the injected disturbances
    tp = fp = 0; tpM = fnM = 0; wtot = wcau = 0
    for c in te:
        v = c["valid"]
        o, e, mi = c["truth"][v], c["truth_exact"][v], c["truth_micro"][v]
        tp += int((o & (e | mi)).sum()); fp += int((o & ~(e | mi)).sum())
        tpM += int((o & e).sum()); fnM += int((~o & e).sum())
        for s, en in D._runs(e):
            wtot += 1
            if o[s:en].any():
                wcau += 1
    orc = dict(precision_vs_any_injected=tp / max(tp + fp, 1),
               report_recall_vs_major=tpM / max(tpM + fnM, 1),
               window_recall_vs_major=wcau / max(wtot, 1),
               n_major_windows=wtot)
    numbers["oracle_validation"] = orc
    log("  oracle vs injected: precision %.2f, report recall %.2f, "
        "window recall %.2f over %d injected windows"
        % (orc["precision_vs_any_injected"], orc["report_recall_vs_major"],
           orc["window_recall_vs_major"], wtot))
    pd.DataFrame([orc]).to_csv(os.path.join(OUT, "table_oracle_validation.csv"),
                               index=False)

    # ---------------- fit -------------------------------------------------
    log("\n[2] fitting the three ATE families on synthetic data only")
    ate_q = T.fit_linear(X, Y, seed=2)
    ate_s = T.fit_stumps(X, Y, n_stumps=16, seed=3)
    ate_m = T.fit_mlp(X, Y, hidden=8, seed=4)
    ate_q8 = T.quantise_linear(ate_q, 8)[0]
    ate_s8 = T.quantise_stumps(ate_s, 8)[0]
    ate_m8 = T.quantise_mlp(ate_m, 8)[0]

    # decision-cost calibration on held-out SYNTHETIC channels only
    def synth_macro(m):
        return eval_synth(te, m, 0.0)["macro_f1"]
    betas = {}
    ate_q = T.calibrate_bias(ate_q, te, synth_macro)[0]
    ate_s = T.calibrate_bias(ate_s, te, synth_macro)[0]
    ate_m = T.calibrate_bias(ate_m, te, synth_macro)[0]
    ate_q8, betas["ATE-Q"], _ = T.calibrate_bias(ate_q8, te, synth_macro)
    ate_s8, betas["ATE-S"], _ = T.calibrate_bias(ate_s8, te, synth_macro)
    ate_m8, betas["ATE-M"], _ = T.calibrate_bias(ate_m8, te, synth_macro)
    log("  decision-cost bias (octaves, fitted on held-out synthetic): "
        + ", ".join(f"{k} {v:+.2f}" for k, v in betas.items()))
    numbers["decision_bias_oct"] = betas
    Xte, Yte = T.assemble(te, max_per_chan=64, seed=5)
    mae = {}
    for nm, mdl in [("ATE-Q", ate_q), ("ATE-Q int8", ate_q8),
                    ("ATE-S", ate_s), ("ATE-S int8", ate_s8),
                    ("ATE-M", ate_m), ("ATE-M int8", ate_m8)]:
        p = np.array([mdl.predict(f) for f in Xte])
        mae[nm] = dict(kh=float(np.abs(p[:, 0] - Yte[:, 0]).mean()),
                       kl=float(np.abs(p[:, 1] - Yte[:, 1]).mean()))
        log("  %-11s held-out synthetic margin MAE: kH %.3f oct, kL %.3f oct"
            % (nm, mae[nm]["kh"], mae[nm]["kl"]))
    numbers["margin_mae_heldout_synth"] = mae
    pd.DataFrame(mae).T.to_csv(os.path.join(OUT, "table_margin_mae.csv"))
    pickle.dump(dict(q=ate_q, s=ate_s, m=ate_m, q8=ate_q8, s8=ate_s8, m8=ate_m8),
                open(os.path.join(OUT, "ate_models.pkl"), "wb"))

    # ---------------- calibration speed ----------------------------------
    log("\n[3] calibration speed on held-out synthetic (margin MAE vs horizon)")
    hor_s = [0.1, 0.2, 0.5, 1.0, 2.0]
    crows = []
    for hs in hor_s:
        r = int(round(hs * FR))
        row = {"horizon_s": hs}
        for nm, mdl in [("ATE-Q int8", ate_q8), ("ATE-S int8", ate_s8),
                        ("ATE-M int8", ate_m8)]:
            errs = []
            for c in te:
                idx = np.where(c["valid"])[0]
                idx = idx[idx < r]
                if idx.size == 0:
                    continue
                errs.append(abs(mdl.predict(c["F"][idx[-1]])[0] - c["kh_star"]))
            row[nm] = float(np.mean(errs)) if errs else float("nan")
        # empirical quantile with the same amount of history
        errs, cerrs = [], []
        for c in te:
            idx = np.where(c["valid"])[0]
            idx = idx[idx < r]
            if idx.size < 4:
                continue
            errs.append(abs(np.quantile(c["d"][idx], Q_HI) + KAPPA_HI_PAD
                            - c["kh_star"]))
            cerrs.append(abs(float(np.median(kh_tr)) - c["kh_star"]))
        row["empirical-Q"] = float(np.mean(errs)) if errs else float("nan")
        row["fixed constant"] = float(np.mean(cerrs)) if cerrs else float("nan")
        crows.append(row)
    cdf = pd.DataFrame(crows)
    cdf.to_csv(os.path.join(OUT, "table_calibration_speed.csv"), index=False)
    log(cdf.round(3).to_string(index=False))
    numbers["calibration_speed"] = cdf.to_dict("records")

    # ---------------- floor study ----------------------------------------
    log("\n[4] kappa_H floor study, selected on held-out SYNTHETIC only")
    frows = []
    for fl in np.round(np.arange(0.0, 5.01, 0.25), 2):
        r = eval_synth(te, ate_m8, float(fl))
        r["kappa_min_hi"] = float(fl)
        frows.append(r)
    fdf = pd.DataFrame(frows)
    fdf.to_csv(os.path.join(OUT, "table_floor_study_synth.csv"), index=False)
    learned_floor = float(fdf.loc[fdf["macro_f1"].idxmax(), "kappa_min_hi"])
    log(fdf.round(3).to_string(index=False))
    log(f"  learned floor = {learned_floor:.2f} octaves "
        f"(argmax macro F1 on held-out synthetic)")
    numbers["learned_floor_oct"] = learned_floor
    numbers["hard_floor_oct"] = KAPPA_MIN_HI
    floors = {"hard": KAPPA_MIN_HI, "learned": learned_floor, "none": 0.0}

    # ---------------- GESL ------------------------------------------------
    log("\n[5] GESL channels")
    t0 = time.time()
    chans = E.load_channels(DATA, records)
    log(f"  {len(chans)} channels in {time.time()-t0:.1f}s")
    chdf = pd.DataFrame([dict(
        rid=c["rid"], ch=c["ch"], fs=c["fs"], duration_s=c["duration"],
        n_reports=int(c["valid"].sum()),
        excluded_dead_pct=100.0 * float(c["proc"]["dead_s"].mean()),
        n_event_reports=c["n_event_reports"],
        n_event_windows=len(D._runs(c["sample_labels"])),
        kh_star=c["kh_star"], kl_star=c["kl_star"],
        b_min=float(c["proc"]["b"][c["valid"]].min()),
        b_max=float(c["proc"]["b"][c["valid"]].max())) for c in chans])
    chdf.to_csv(os.path.join(OUT, "table_channels.csv"), index=False)
    log(chdf.round(2).to_string(index=False))
    pickle.dump(chans, open(os.path.join(OUT, "gesl_channels.pkl"), "wb"))
    kk = chdf["kh_star"].to_numpy()
    numbers["gesl"] = dict(
        n_channels=len(chans),
        n_channels_with_events=int((chdf["n_event_windows"] > 0).sum()),
        n_reports=int(chdf["n_reports"].sum()),
        kh_star_min=float(kk.min()), kh_star_max=float(kk.max()),
        ambient_spread_octaves=float(chdf["b_min"].max() - chdf["b_min"].min()))

    # ---------------- methods --------------------------------------------
    log("\n[6] method comparison on the GESL records")
    results, detail = {}, []

    def add(name, rows, agg, extra=None):
        for r in rows:
            r["method"] = name
        results[name] = dict(agg, **(extra or {}))
        detail.extend(rows)

    rows = [E.run_v1_fixed(c) for c in chans]
    add("v1-fixed (TH=1e7, TL=300)", rows, E.aggregate(rows))

    rows = [E.run_empirical_q(c, kappa_min_hi=0.0) for c in chans]
    add("empirical-Q (causal)", rows, E.aggregate(rows))

    rows, agg = E.per_record_statistical(chans, kappa_min_hi=0.0)
    add("per-channel statistical (offline oracle)", rows, agg)

    rows, agg = E.hindsight_ceiling(chans, grid=KGRID, kappa_min_hi=0.0)
    add("hindsight ceiling (offline oracle)", rows, agg)

    # fair fixed margin: best constant on HELD-OUT SYNTHETIC
    best = None
    for kh in KGRID:
        r = eval_synth(te, ATEConst(kh, 1.0), 0.0)
        if best is None or r["macro_f1"] > best[1]:
            best = (float(kh), r["macro_f1"])
    k_syn = best[0]
    log(f"  best constant margin on held-out synthetic: {k_syn:.2f} octaves")
    numbers["fixed_margin_from_synth_oct"] = k_syn
    rows, agg = E.eval_all(chans, ATEConst(k_syn, 1.0), kappa_min_hi=0.0)
    add("fixed margin (tuned on synthetic)", rows, agg, {"kappa": k_syn})

    # oracle fixed margin: best constant on GESL itself
    kfix, kagg, krows = E.best_fixed_margin(chans, grid=KGRID, kappa_min_hi=0.0)
    add("fixed margin (best constant, offline oracle)", krows, kagg,
        {"kappa": kfix[0], "gap": kfix[1]})
    numbers["fixed_margin_oracle"] = list(kfix)
    log(f"  best constant margin on GESL (oracle): kappa_H={kfix[0]:.2f}, "
        f"Delta={kfix[1]:.2f} octaves")

    for fname, fval in floors.items():
        for nm, mdl in [("ATE-Q", ate_q8), ("ATE-S", ate_s8), ("ATE-M", ate_m8)]:
            rows, agg = E.eval_all(chans, mdl, kappa_min_hi=fval)
            add(f"{nm} int8, floor={fname}", rows, agg, {"kappa_min": fval})
    for nm, mdl in [("ATE-Q", ate_q), ("ATE-S", ate_s), ("ATE-M", ate_m)]:
        rows, agg = E.eval_all(chans, mdl, kappa_min_hi=floors["learned"])
        add(f"{nm} float, floor=learned", rows, agg)

    # ---------------- leave-one-record-out --------------------------------
    log("\n[7] leave-one-record-out (ATE fitted on the OTHER records only)")
    loro_rows = []
    for held in records:
        trc = [c for c in chans if c["rid"] != held]
        Xl = np.vstack([c["F"][c["valid"]][::4] for c in trc])
        Yl = np.vstack([np.tile([c["kh_star"], c["kl_star"]],
                                (c["F"][c["valid"]][::4].shape[0], 1))
                        for c in trc])
        mdl = T.quantise_mlp(T.fit_mlp(Xl, Yl, hidden=8, seed=7), 8)[0]
        for c in [c for c in chans if c["rid"] == held]:
            m = E.eval_channel(c, mdl, kappa_min_hi=floors["learned"])
            m.update(rid=c["rid"], ch=c["ch"], method="ATE-M int8 (LORO)")
            loro_rows.append(m)
    add("ATE-M int8 (leave-one-record-out)", loro_rows, E.aggregate(loro_rows))

    agg_df = pd.DataFrame(results).T
    agg_df.index.name = "method"
    agg_df.to_csv(os.path.join(OUT, "table_aggregate.csv"))
    cols = ["macro_f1", "micro_f1", "precision", "recall", "event_recall",
            "false_alarm_runs", "false_alarm_runs_quiet", "duty_cycle",
            "duty_cycle_quiet", "latency_ms"]
    log(agg_df[cols].astype(float).round(3).to_string())

    det = pd.DataFrame(detail)
    det.to_csv(os.path.join(OUT, "table_per_channel.csv"), index=False)

    head = ["v1-fixed (TH=1e7, TL=300)", "fixed margin (tuned on synthetic)",
            "ATE-Q int8, floor=learned", "ATE-S int8, floor=learned",
            "ATE-M int8, floor=learned", "ATE-M int8 (leave-one-record-out)",
            "empirical-Q (causal)", "fixed margin (best constant, offline oracle)",
            "per-channel statistical (offline oracle)",
            "hindsight ceiling (offline oracle)"]
    prt = per_record_table(detail, head)
    prt.to_csv(os.path.join(OUT, "table_per_record_f1.csv"))
    log("\nper-record mean F1 over event-bearing channels")
    log(prt.round(3).to_string())

    # ---------------- bandwidth ------------------------------------------
    bw = []
    for name in head:
        sub = [r for r in detail if r["method"] == name]
        if not sub:
            continue
        duty = float(np.mean([r["duty_cycle"] for r in sub]))
        bw.append(dict(method=name, mean_duty_cycle=duty,
                       bandwidth_reduction=(1.0 / duty) if duty > 0 else
                       float("inf"),
                       event_recall=E.aggregate(sub)["event_recall"]))
    bwdf = pd.DataFrame(bw)
    bwdf.to_csv(os.path.join(OUT, "table_bandwidth.csv"), index=False)
    log("\nbandwidth\n" + bwdf.round(3).to_string(index=False))

    numbers["aggregate"] = {k: {kk2: (None if isinstance(vv, float) and
                                      math.isnan(vv) else vv)
                                for kk2, vv in v.items()}
                            for k, v in results.items()}
    numbers["config"] = dict(FR=FR, NTAPS=NTAPS, FIR_CUTOFF_HZ=FIR_CUTOFF_HZ,
                             N_ACQ=N_ACQ, MS_SUBWIN=MS_SUBWIN, MS_NSUB=MS_NSUB,
                             ALPHA_SLOW=ALPHA_SLOW, ALPHA_V=ALPHA_V,
                             MAX_DECAY=MAX_DECAY, VBAR_HOLD_OCT=VBAR_HOLD_OCT,
                             VBAR_HOLD_MAX=VBAR_HOLD_MAX, Q_HI=Q_HI, Q_LO=Q_LO,
                             KAPPA_HI_PAD=KAPPA_HI_PAD,
                             KAPPA_GAP_MIN=KAPPA_GAP_MIN,
                             features=FEATURE_NAMES)
    json.dump(numbers, open(os.path.join(OUT, "numbers.json"), "w"), indent=2)
    pickle.dump(dict(records=records, floors=floors, k_syn=k_syn, kfix=kfix),
                open(os.path.join(OUT, "state.pkl"), "wb"))
    log("\nwrote " + OUT)


if __name__ == "__main__":
    main()
