"""Compile the exported C++ and replay every GESL report through it, then
compare the trigger decisions against the Python reference that produced every
number in Part 1.

This establishes ALGORITHM equivalence (identical operation order, identical
constants).  It is NOT bit-exactness: the ap_* stub maps the fixed-point types
to double.  Bit-exactness requires a Vitis C simulation and belongs to Part 2.
"""

from __future__ import annotations
import os, pickle, subprocess, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gs2_core import run_engine, KAPPA_MIN_HI
import gs2_export as X

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(os.path.join(HERE, "..", "out"))
HLS = os.path.abspath(os.path.join(HERE, "..", "hls"))


def main():
    models = pickle.load(open(os.path.join(OUT, "ate_models.pkl"), "rb"))
    chans = pickle.load(open(os.path.join(OUT, "gesl_channels.pkl"), "rb"))
    state = pickle.load(open(os.path.join(OUT, "state.pkl"), "rb"))
    floor = state["deployed_floor"]
    model = models["m8"]

    info = X.export(model, HLS, kappa_min_hi=floor)
    print("exported:", info)

    # ---- write the stimulus ------------------------------------------------
    rows = []
    for i, c in enumerate(chans):
        p = c["proc"]
        for r in range(p["b"].size):
            rows.append((i, p["b"][r], p["lv"][r], p["f"][r],
                         int(p["gate_r"][r])))
    df = pd.DataFrame(rows, columns=["chan", "b", "lv", "fhz", "dead"])
    vec = os.path.join(HLS, "vectors.csv")
    df.to_csv(vec, index=False, float_format="%.17g")
    print(f"wrote {len(df)} report vectors over {len(chans)} channels")

    # ---- compile and run ---------------------------------------------------
    exe = os.path.join(HLS, "ate_tb")
    cmd = ["g++", "-O2", "-std=c++11", "-I", HLS,
           os.path.join(HLS, "ate_top.cpp"), os.path.join(HLS, "ate_tb.cpp"),
           "-o", exe]
    subprocess.run(cmd, check=True)
    out = os.path.join(HLS, "trig_hls.csv")
    subprocess.run([exe, vec, out], check=True)
    hls = pd.read_csv(out)

    # ---- Python reference --------------------------------------------------
    mism = 0
    total = 0
    dmax_amb = 0.0
    dmax_kh = 0.0
    per_chan = []
    off = 0
    for i, c in enumerate(chans):
        p = c["proc"]
        ref = run_engine(p["b"], p["lv"], p["f"], model,
                         kappa_min_hi=floor, collect=True, dead=p["gate_r"])
        n = p["b"].size
        sub = hls.iloc[off:off + n]
        off += n
        assert (sub["chan"] == i).all(), "channel alignment error"
        mm = int(np.sum(sub["trig"].to_numpy() != ref["trig"]))
        da = float(np.max(np.abs(sub["b_amb"].to_numpy() - ref["b_amb"])))
        dk = float(np.max(np.abs(sub["kappa_h"].to_numpy() - ref["kappa_h"])))
        mism += mm
        total += n
        dmax_amb = max(dmax_amb, da)
        dmax_kh = max(dmax_kh, dk)
        per_chan.append(dict(rid=c["rid"], ch=c["ch"], n_reports=n,
                             trigger_mismatches=mm, max_abs_db_amb=da,
                             max_abs_dkappa_h=dk))
    tab = pd.DataFrame(per_chan)
    tab.to_csv(os.path.join(OUT, "table_equivalence.csv"), index=False)
    print(tab.to_string(index=False))
    print(f"\nTOTAL: {mism} trigger mismatches over {total} reports "
          f"({len(chans)} channels), max |d b_amb| = {dmax_amb:.1e}, "
          f"max |d kappa_H| = {dmax_kh:.1e}")
    summary = dict(reports=total, channels=len(chans), mismatches=mism,
                   max_abs_db_amb=dmax_amb, max_abs_dkappa_h=dmax_kh,
                   **info)
    pd.DataFrame([summary]).to_csv(
        os.path.join(OUT, "table_equivalence_summary.csv"), index=False)
    return 0 if mism == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
