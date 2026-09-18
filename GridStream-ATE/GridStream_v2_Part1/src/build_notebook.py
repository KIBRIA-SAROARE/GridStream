"""Build GridStream_v2_Part1.ipynb -- the Colab entry point.

The notebook orchestrates the same modules that produced every number, so there
is one source of truth: gs2_core.py, gs2_data.py, gs2_synth.py, gs2_train.py,
gs2_eval.py, gs2_export.py.
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(os.path.join(HERE, ".."))


def md(text):
    return {"cell_type": "markdown", "metadata": {}, "source": text.splitlines(True)}


def code(text):
    return {"cell_type": "code", "execution_count": None, "metadata": {},
            "outputs": [], "source": text.splitlines(True)}


CELLS = [
    md("""# GridStream-v2 — Part 1: the Adaptive Threshold Engine

This notebook runs the complete Part 1 workflow end to end and writes every
table, figure, weight file and HLS source that Part 2 and Part 3 need.

**Pipeline**

```
raw PoW -> NCO -> FIR(257) -> CORDIC -> phasor            (v1, unchanged)
                                |
                                +-> reconstruction -> residual -> sliding LSE  L[n]
  C1  b = log2 L - log2 W - 2 log2 Vbar + 1      Vbar = causal HELD EWMA
  C2  b_amb  = causal minimum-statistics tracker
  C3  kappa_H, Delta = ATE(6 causal features), int8
      trigger:  b >= b_amb + kappa_H            <- an ADD and a COMPARE
  C2' latched hysteresis FSM; kappa and b_amb latched, feature EWMAs held
```

**Rules this notebook obeys**

* every online quantity is causal; non-causal code lives only in functions whose
  name contains `oracle` or `offline`, and is used only for reference labels and
  for baselines that are explicitly marked as oracles;
* no GESL record takes part in fitting or in model selection — the ATE is fitted
  on synthetic environments and the deployed configuration is chosen on held-out
  synthetic channels;
* the exported C++ is compiled and replayed against the Python reference.
"""),
    md("""## 0. Setup

Put the six GESL record pairs (`sigId<ID>PoW.csv`, `sigId<ID>Metadata.csv`) in
`gs2/data/` and the modules in `gs2/src/`. On Colab, mount Drive or upload the
folder, then point `ROOT` at it."""),
    code("""import os, sys, subprocess
ROOT = os.environ.get("GS2_ROOT", "/content/gs2")   # change for your setup
if not os.path.isdir(ROOT):
    ROOT = os.path.abspath("..")
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)
os.chdir(SRC)
print("root:", ROOT)
print("records found:", sorted(f for f in os.listdir(os.path.join(ROOT, "data"))
                               if f.endswith("PoW.csv")))"""),
    md("""## 1. Configuration

Every constant used anywhere in Part 1 is declared in `gs2_core.py`. Printing
them here makes the run self-documenting."""),
    code("""import gs2_core as K
for name in ["FN", "NTAPS", "FIR_CUTOFF_HZ", "FIR_WINDOW", "FR", "N_ACQ",
             "MS_SUBWIN", "MS_NSUB", "ALPHA_V", "VBAR_HOLD_OCT",
             "VBAR_HOLD_MAX", "DEAD_OCT", "ALPHA_SLOW", "MAX_DECAY",
             "KAPPA_MIN_HI", "KAPPA_MAX_HI", "KAPPA_GAP_MIN", "KAPPA_GAP_MAX",
             "Q_HI", "Q_LO", "KAPPA_HI_PAD", "LOG2_ROM_N"]:
    print(f"{name:16s} {getattr(K, name)}")
print("features:", K.FEATURE_NAMES)"""),
    md("""## 2. The whole Part 1 run

`run_part1.py` performs, in order: provenance checks, synthetic environment
generation, fitting of ATE-Q / ATE-S / ATE-M, int8 quantisation, the
calibration-speed study, the kappa-floor study on synthetic data, GESL
evaluation against every baseline, and leave-one-record-out.

It takes roughly 20 minutes on a Colab CPU runtime."""),
    code("""!python run_part1.py --nenv 220 --ntest 60"""),
    md("""## 3. Finalisation

* the per-channel margin a perfectly-informed designer would have used;
* the deployed configuration, selected on 540 held-out synthetic channels using
  pooled (micro) F1, which — unlike macro F1 — counts false alarms on channels
  that contain no event;
* a cross-check of the reference oracle windows against the GESL metadata."""),
    code("""!python finalize.py"""),
    md("""## 4. Sensitivity of the result to the physical floor

The floor `kappa_H >= log2(10)` ties the trigger to the same tenfold rise in
normalised goodness-of-fit that defines a disturbance. This sweep separates what
the floor does from what the learned margins do."""),
    code("""!python floor_sweep.py"""),
    md("""## 5. Export to synthesizable C++ and prove equivalence

`gs2_export.py` writes `ate_top.cpp`, `ate_weights.h`, `ate_top.h`, `ate_tb.cpp`
and an `ap_*` stub. `check_equivalence.py` compiles the exported source with a
host compiler and replays every GESL report through it.

This establishes **algorithm** equivalence — identical operation order and
identical constants. Bit-exactness needs a Vitis C simulation and belongs to
Part 2."""),
    code("""!python check_equivalence.py"""),
    md("""## 6. Reference-oracle validation

The reference labels come from an offline, non-causal detector. Measuring it
against synthetic ground truth says how much of the GESL result is a property of
the reference rather than of the methods."""),
    code("""!python validate_oracle.py"""),
    md("""## 7. Figures and tables"""),
    code("""!python make_figures.py && python make_tables.py"""),
    code("""from IPython.display import Image, display
import glob, os
for f in sorted(glob.glob(os.path.join(ROOT, "figs", "fig_*.png"))):
    print(os.path.basename(f))
    display(Image(filename=f, width=900))"""),
    md("""## 8. Headline numbers"""),
    code("""import json, pandas as pd
OUT = os.path.join(ROOT, "out")
nums = json.load(open(os.path.join(OUT, "numbers.json")))
agg = pd.read_csv(os.path.join(OUT, "table_aggregate.csv"), index_col=0)
cols = ["micro_f1", "macro_f1", "precision", "recall", "event_recall",
        "false_alarm_runs_quiet", "duty_cycle", "latency_ms"]
print("deployed:", nums["deployed"])
display(agg[cols].astype(float).round(3))
display(pd.read_csv(os.path.join(OUT, "table_per_record_f1.csv"), index_col=0)
        .round(3))"""),
    md("""## 9. What this run does and does not establish

**Established**

* The v1 fixed thresholds do not transport: micro F1 0.027 across 36 channels.
* Normalising the residual by the causally tracked fundamental removes the
  sensor scale, but the ambient floor still spans about nine octaves and the
  margin each channel needs spans a factor of 45.
* The learned margins matter most where the physical floor is low. With no
  floor, a constant margin produces thousands of spurious trigger runs on the
  event-free channels while the ATE produces a few hundred; with the floor in
  place the two converge.
* int8 quantisation costs nothing measurable.
* The exported C++ reproduces the Python reference exactly: 0 trigger mismatches
  over 30,396 reports.

**Not established**

* Bit-exactness of the fixed-point implementation — Part 2.
* Any FPGA area, timing or power number — Part 2. Nothing in this notebook
  produces a synthesis result.
* Absolute detection performance. The reference oracle is imperfect (see the
  validation table), so the GESL numbers compare methods against a common
  reference; they are not absolute detection rates.
* That the ATE beats a well-chosen constant on macro F1. It does not; it matches
  it. The separation is in pooled F1, in the false-alarm count on quiet
  channels, and in how far the floor can be lowered safely.
"""),
]

nb = {"cells": CELLS,
      "metadata": {"kernelspec": {"display_name": "Python 3",
                                  "language": "python", "name": "python3"},
                   "language_info": {"name": "python", "version": "3.11"},
                   "colab": {"provenance": []}},
      "nbformat": 4, "nbformat_minor": 5}

path = os.path.join(OUT, "GridStream_v2_Part1.ipynb")
json.dump(nb, open(path, "w"), indent=1)
print("wrote", path)
