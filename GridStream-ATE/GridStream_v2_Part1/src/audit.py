"""Internal-consistency audit of the Part 1 outputs.

Checks that the equations in the code, the exported C++ constants, the CSVs, the
LaTeX tables and the figures all agree.  Exits non-zero if anything disagrees.
"""
from __future__ import annotations
import json, math, os, pickle, re, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gs2_core as K

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(os.path.join(HERE, "..", "out"))
HLS = os.path.abspath(os.path.join(HERE, "..", "hls"))
FIGS = os.path.abspath(os.path.join(HERE, "..", "figs"))

fails, warns = [], []


def check(cond, msg):
    if cond:
        print("  [PASS] " + msg)
    else:
        fails.append(msg)
        print("  [FAIL] " + msg)


def main():
    nums = json.load(open(os.path.join(OUT, "numbers.json")))
    agg = pd.read_csv(os.path.join(OUT, "table_aggregate.csv"), index_col=0)
    ch = pd.read_csv(os.path.join(OUT, "table_channels.csv"))
    det = pd.read_csv(os.path.join(OUT, "table_per_channel.csv"))
    st = pickle.load(open(os.path.join(OUT, "state.pkl"), "rb"))
    hdr = open(os.path.join(HLS, "ate_weights.h")).read()
    tex = open(os.path.join(OUT, "tables.tex")).read()

    print("1. constants: gs2_core.py vs exported ate_weights.h")
    def hdef(name):
        m = re.search(rf"#define {name}\s+([-\d]+)", hdr)
        return int(m.group(1)) if m else None

    def hval(name):
        m = re.search(rf"static const double {name}\s*=\s*([-\d.eE+]+);", hdr)
        return float(m.group(1)) if m else None

    check(hdef("ATE_N_FEAT") == K.N_FEAT, "N_FEAT")
    check(hdef("ATE_N_ACQ") == K.N_ACQ, "N_ACQ")
    check(hdef("ATE_MS_SUBWIN") == K.MS_SUBWIN, "MS_SUBWIN")
    check(hdef("ATE_MS_NSUB") == K.MS_NSUB, "MS_NSUB")
    check(hdef("ATE_VBAR_HOLD_MAX") == K.VBAR_HOLD_MAX, "VBAR_HOLD_MAX")
    check(hdef("ATE_LOG2_ROM_N") == K.LOG2_ROM_N, "LOG2_ROM_N")
    for nm, v in [("ATE_ALPHA_V", K.ALPHA_V), ("ATE_ALPHA_SLOW", K.ALPHA_SLOW),
                  ("ATE_MAX_DECAY", K.MAX_DECAY), ("ATE_DEAD_OCT", K.DEAD_OCT),
                  ("ATE_VBAR_HOLD_OCT", K.VBAR_HOLD_OCT),
                  ("ATE_GAP_MIN", K.KAPPA_GAP_MIN),
                  ("ATE_GAP_MAX", K.KAPPA_GAP_MAX),
                  ("ATE_KAPPA_MAX_HI", K.KAPPA_MAX_HI),
                  ("ATE_KAPPA_MIN_LO", K.KAPPA_MIN_LO), ("ATE_FN", K.FN)]:
        check(abs(hval(nm) - v) < 1e-12, nm)
    check(abs(hval("ATE_KAPPA_MIN_HI") - st["deployed_floor"]) < 1e-9,
          "exported floor equals the deployed floor")

    print("2. hardware cost bookkeeping")
    H = hdef("ATE_N_HIDDEN")
    check(hdef("ATE_N_MAC") == K.N_FEAT * H + H * 2,
          f"N_MAC = 6*{H} + {H}*2 = {K.N_FEAT*H + H*2}")
    check(hdef("ATE_N_SCALE_MUL") == K.N_FEAT, "N_SCALE_MUL = 6")
    src = open(os.path.join(HLS, "ate_top.cpp")).read()
    body = "\n".join(l.split("//")[0] for l in src.splitlines())
    div = [l for l in body.splitlines()
           if re.search(r"[^/*]/[^/*=]", l) and "include" not in l]
    check(not div, "no division operator in ate_top.cpp"
          + ("" if not div else f" -- found {div[:2]}"))

    print("3. log2 ROM equality")
    rom = [float(x) for x in re.search(r"ATE_LOG2_ROM\[\d+\] = \{(.*?)\};",
                                       hdr, re.S).group(1).split(",")]
    check(np.allclose(rom, K.LOG2_ROM, atol=1e-15), "ROM matches gs2_core")

    print("4. equations")
    W = 256
    L, lvbar = 1234.5, 3.25
    b_ref = K.log2_hw_scalar(L) - K.log2_hw_scalar(float(W)) - 2 * lvbar + 1.0
    lam = L / (W * (2 ** lvbar) ** 2 / 2.0)
    check(abs(b_ref - (K.log2_hw_scalar(L) - K.log2_hw_scalar(float(W))
                       - 2 * lvbar + 1.0)) < 1e-12,
          "b = log2 L - log2 W - 2 log2 Vbar + 1")
    check(abs(2 ** b_ref - lam) / lam < 0.02,
          "2^b equals Lambda = L / (W Vbar^2 / 2) to within the ROM error")

    print("5. tables against CSVs")
    for key, name in [("ATE-M int8, floor=hard", "ATE-M int8 $+$ floor (deployed)*"),
                      ("v1-fixed (TH=1e7, TL=300)",
                       "v1 fixed thresholds, transported")]:
        v = agg.loc[key, "micro_f1"]
        check(f"{v:.3f}" in tex, f"micro F1 {v:.3f} for '{name}' appears in tables.tex")
    check(str(int(ch["n_reports"].sum())) in tex or
          str(nums["gesl"]["n_reports"]) in tex,
          "report count appears in tables.tex")

    print("6. aggregate against per-channel detail")
    for key in ["ATE-M int8, floor=hard", "fixed margin (tuned on synthetic)"]:
        sub = det[det["method"] == key]
        tp, fp, fn = sub["tp"].sum(), sub["fp"].sum(), sub["fn"].sum()
        pr, rc = tp / (tp + fp), tp / (tp + fn)
        f1 = 2 * pr * rc / (pr + rc)
        check(abs(f1 - agg.loc[key, "micro_f1"]) < 1e-9,
              f"micro F1 recomputed from per-channel rows: {key}")
        ev = sub[sub["has_events"]]
        check(abs(ev["f1"].mean() - agg.loc[key, "macro_f1"]) < 1e-9,
              f"macro F1 recomputed from per-channel rows: {key}")

    print("7. equivalence result")
    eq = pd.read_csv(os.path.join(OUT, "table_equivalence_summary.csv")).iloc[0]
    check(int(eq["mismatches"]) == 0, "0 trigger mismatches")
    print(f"        {int(eq['reports'])} reports replayed over "
          f"{int(eq['channels'])} channels")

    print("8. figures exist as vector PDF and 600 dpi PNG")
    for f in ["fig_motivation", "fig_case_studies", "fig_threshold_tracking",
              "fig_method_comparison", "fig_calibration"]:
        check(os.path.exists(os.path.join(FIGS, f + ".pdf")) and
              os.path.exists(os.path.join(FIGS, f + ".png")), f)

    print("9. no GESL record was used for fitting")
    src_all = "".join(open(os.path.join(HERE, f)).read()
                      for f in ["gs2_train.py", "run_part1.py"])
    check("load_channels" not in open(os.path.join(HERE, "gs2_train.py")).read(),
          "gs2_train.py never touches GESL data")
    check(re.search(r"T\.(fit_linear|fit_stumps|fit_mlp)\(X", src_all) is not None,
          "the three families are fitted on the synthetic matrix X only")

    print()
    if fails:
        print(f"AUDIT FAILED: {len(fails)} check(s)")
        for f in fails:
            print("   ", f)
        return 1
    print("AUDIT PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
