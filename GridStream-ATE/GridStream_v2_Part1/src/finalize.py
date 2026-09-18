"""Post-processing after run_part1.py:

  1. per-channel hindsight-optimal margins -> kappa_opt_real.pkl (figures use it)
  2. deployed configuration, chosen on HELD-OUT SYNTHETIC only
  3. cross-check of the reference oracle windows against the GESL metadata
"""
from __future__ import annotations
import json, os, pickle, re, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gs2_data as D
from run_part1 import eval_synth, OUT, SEED_TEST, get_synth

DATA = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "..", "data"))


def kappa_opt():
    det = pd.read_csv(os.path.join(OUT, "table_per_channel.csv"))
    ce = det[det["method"] == "hindsight ceiling (offline oracle)"]
    chans = pickle.load(open(os.path.join(OUT, "gesl_channels.pkl"), "rb"))
    key = {(r.rid, r.ch): r.kappa_h for r in ce.itertuples()}
    k = np.array([key[(c["rid"], c["ch"])] for c in chans])
    pickle.dump(k, open(os.path.join(OUT, "kappa_opt_real.pkl"), "wb"))
    print("kappa_opt (hindsight, per channel): min %.2f med %.2f max %.2f"
          % (k.min(), np.median(k), k.max()))
    return k


def select(ntest=60, extra_seeds=(4242, 90210)):
    models = pickle.load(open(os.path.join(OUT, "ate_models.pkl"), "rb"))
    te = get_synth(ntest, SEED_TEST, "test")
    # The nine candidate configurations differ by only a few points of micro F1
    # on 180 channels, which is inside run-to-run noise, so the selection set is
    # enlarged with independently seeded environments.  None of them is a GESL
    # record, so this changes nothing about the honesty of the GESL test.
    for sd in extra_seeds:
        te = te + get_synth(ntest, sd, f"sel{sd}")
    print(f"  selection set: {len(te)} synthetic channels")
    st = pickle.load(open(os.path.join(OUT, "state.pkl"), "rb"))
    rows = []
    for fam, key in [("ATE-Q", "q8"), ("ATE-S", "s8"), ("ATE-M", "m8")]:
        for fname, fval in st["floors"].items():
            r = eval_synth(te, models[key], fval)
            r.update(family=fam, floor=fname, kappa_min_hi=fval)
            rows.append(r)
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(OUT, "table_config_selection_synth.csv"), index=False)
    print("\nconfiguration selection on held-out synthetic")
    print(df[["family", "floor", "kappa_min_hi", "macro_f1", "micro_f1",
              "event_recall", "duty_cycle",
              "false_alarm_runs_quiet"]].round(3).to_string(index=False))
    # Selection rule, fixed in advance: pooled (micro) F1 over ALL held-out
    # synthetic channels.  Macro F1 averages only event-bearing channels and
    # is therefore blind to false alarms on quiet ones, which is exactly the
    # error an event-triggered recorder pays for in bandwidth.
    best = df.loc[df["micro_f1"].idxmax()]
    st["deployed_family"] = str(best["family"])
    st["deployed_floor"] = float(best["kappa_min_hi"])
    st["deployed_floor_name"] = str(best["floor"])
    st["deployed_name"] = f"{best['family']} int8, floor={best['floor']}"
    pickle.dump(st, open(os.path.join(OUT, "state.pkl"), "wb"))
    print(f"\nDEPLOYED: {st['deployed_name']} "
          f"(kappa floor {st['deployed_floor']:.2f} octaves)")
    return st


def metadata_crosscheck():
    """Compare the oracle's event windows against the documented event times
    and durations in the GESL metadata.  This is the only independent check on
    the reference labels available for the real records."""
    chans = pickle.load(open(os.path.join(OUT, "gesl_channels.pkl"), "rb"))
    rows = []
    for rid in sorted({c["rid"] for c in chans}):
        rec = D.load_record(DATA, rid)
        sub = [c for c in chans if c["rid"] == rid]
        fs = sub[0]["fs"]
        # union of the oracle windows over that record's channels
        n = sub[0]["sample_labels"].size
        u = np.zeros(n, bool)
        dead = np.zeros(n, bool)
        for c in sub:
            u |= c["sample_labels"]
            dead |= c["proc"]["dead_s"]
        w = D._runs(u)
        dw = D._runs(dead)
        cyc = fs / 60.0
        rows.append(dict(
            record=rid,
            metadata=rec["description"][:180],
            n_oracle_windows=len(w),
            first_window_s=round(w[0][0] / fs, 3) if w else None,
            oracle_windows="; ".join("%.3f-%.3f s (%.1f cyc)"
                                     % (s / fs, e / fs, (e - s) / cyc)
                                     for s, e in w[:6]),
            de_energised_intervals="; ".join("%.3f-%.3f s (%.2f s)"
                                             % (s / fs, e / fs, (e - s) / fs)
                                             for s, e in dw[:4]),
            span_first_to_last_s=round((w[-1][1] - w[0][0]) / fs, 3) if w else None))
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(OUT, "table_metadata_crosscheck.csv"), index=False)
    print("\nmetadata cross-check")
    for r in rows:
        print(f"  record {r['record']}: {r['n_oracle_windows']} window(s) | "
              f"{r['oracle_windows']}")
        if r["de_energised_intervals"]:
            print(f"      de-energised: {r['de_energised_intervals']}")
        print(f"      GESL says: {r['metadata'][:150]}")
    return df


if __name__ == "__main__":
    kappa_opt()
    st = select()
    metadata_crosscheck()
    nj = os.path.join(OUT, "numbers.json")
    n = json.load(open(nj))
    n["deployed"] = dict(name=st["deployed_name"], family=st["deployed_family"],
                         floor_name=st["deployed_floor_name"],
                         kappa_min_hi=st["deployed_floor"])
    json.dump(n, open(nj, "w"), indent=2)
