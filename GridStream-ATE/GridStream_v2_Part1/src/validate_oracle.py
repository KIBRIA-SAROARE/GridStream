"""Validate the offline reference oracle against synthetic ground truth.

Uses a fresh set of environments with an INDEPENDENT seed, so no environment
here took part in fitting or in model selection.
"""
from __future__ import annotations
import os, sys
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gs2_synth as S
import gs2_data as D
from gs2_core import NTAPS, FR

# A residual detector cannot localise an event more sharply than its own
# response support: the 257-tap FIR plus the one-cycle LSE window.  Injected
# windows are therefore padded by that support before scoring precision.
PAD_REPORTS = int(np.ceil((NTAPS + S.SYN_FS / 60.0) / (S.SYN_FS / FR)))

OUT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "..", "out"))


def _dilate(mask, k):
    if k <= 0:
        return mask
    out = mask.copy()
    for s in range(1, k + 1):
        out[s:] |= mask[:-s]
        out[:-s] |= mask[s:]
    return out


def main(n_env=60, seed=31337):
    ds = S.build_dataset(n_env, seed)
    tp = fp = 0
    tp_pad = fp_pad = 0
    tpM = fnM = 0
    wtot = wcau = 0
    for c in ds:
        v = c["valid"]
        o = c["truth"][v]
        e = c["truth_exact"][v]
        mi = c["truth_micro"][v]
        tp += int((o & (e | mi)).sum())
        fp += int((o & ~(e | mi)).sum())
        ep = _dilate(e | mi, PAD_REPORTS)
        tp_pad += int((o & ep).sum())
        fp_pad += int((o & ~ep).sum())
        tpM += int((o & e).sum())
        fnM += int((~o & e).sum())
        for s, en in D._runs(e):
            wtot += 1
            if o[s:en].any():
                wcau += 1
    row = dict(n_environments=n_env, n_channels=len(ds), seed=seed,
               pad_reports=PAD_REPORTS,
               precision_vs_any_injected=tp / max(tp + fp, 1),
               precision_vs_padded_injected=tp_pad / max(tp_pad + fp_pad, 1),
               report_recall_vs_major=tpM / max(tpM + fnM, 1),
               window_recall_vs_major=wcau / max(wtot, 1),
               n_major_windows=wtot)
    df = pd.DataFrame([row])
    df.to_csv(os.path.join(OUT, "table_oracle_validation.csv"), index=False)
    print(df.T.to_string())


if __name__ == "__main__":
    main()
