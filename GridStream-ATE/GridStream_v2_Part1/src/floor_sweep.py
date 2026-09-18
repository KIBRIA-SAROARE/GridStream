"""Sensitivity of the GESL result to the kappa_H floor.

This is an ANALYSIS on the test records, not a selection: the deployed floor was
fixed on held-out synthetic data before these numbers were computed.
"""
from __future__ import annotations
import os, pickle, sys
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gs2_core import ATEConst
import gs2_eval as E

OUT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "..", "out"))

if __name__ == "__main__":
    chans = pickle.load(open(os.path.join(OUT, "gesl_channels.pkl"), "rb"))
    models = pickle.load(open(os.path.join(OUT, "ate_models.pkl"), "rb"))
    st = pickle.load(open(os.path.join(OUT, "state.pkl"), "rb"))
    key = {"ATE-Q": "q8", "ATE-S": "s8", "ATE-M": "m8"}[st["deployed_family"]]
    rows = []
    for fl in np.round(np.arange(0.0, 6.01, 0.25), 2):
        _, a = E.eval_all(chans, models[key], kappa_min_hi=float(fl))
        _, c = E.eval_all(chans, ATEConst(max(fl, 1e-6), 1.0), kappa_min_hi=0.0)
        rows.append(dict(floor=float(fl), ate_micro=a["micro_f1"],
                         ate_macro=a["macro_f1"], ate_duty=a["duty_cycle"],
                         ate_event_recall=a["event_recall"],
                         ate_fa_quiet=a["false_alarm_runs_quiet"],
                         const_micro=c["micro_f1"], const_macro=c["macro_f1"],
                         const_duty=c["duty_cycle"],
                         const_event_recall=c["event_recall"],
                         const_fa_quiet=c["false_alarm_runs_quiet"]))
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(OUT, "table_floor_sweep_gesl.csv"), index=False)
    print(df.round(3).to_string(index=False))
