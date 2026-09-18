# GridStream-v2 — Part 1 package

Adaptive Threshold Engine (ATE) for event-triggered point-on-wave streaming.
Everything here was produced by running `src/run_part1.py` and the scripts that
follow it. No number in `out/` or `figs/` was typed by hand.

Run date: 2026-09-01. Records: **45, 55, 677, 901, 907, 971** (record 7 removed
at the author's request; 971 added).

---

## Layout

```
data/    the six GESL record pairs (sigId<ID>PoW.csv, sigId<ID>Metadata.csv)
src/     the pipeline -- see below
out/     every table as CSV, tables.tex, numbers.json, ate_weights.json
figs/    five publication figures, vector PDF + 600 dpi PNG
hls/     ate_top.cpp, ate_top.h, ate_weights.h, ate_tb.cpp, ap_stub.h
GridStream_v2_Part1.ipynb   Colab entry point that drives all of the above
```

### Modules

| file | what it holds |
|---|---|
| `gs2_core.py` | every constant; the v1 PMU front end; the hardware `log2`; the causal normaliser; the ambient tracker; the six features; the three ATE families; `run_engine`, which **is** the deployed algorithm |
| `gs2_data.py` | GESL loading, report-rate decimation, the offline reference oracle, metrics |
| `gs2_synth.py` | synthetic three-phase environments and the per-channel optimal margin |
| `gs2_train.py` | fitting ATE-Q / ATE-S / ATE-M under the pinball loss, int8 quantisation, decision-cost bias |
| `gs2_eval.py` | GESL evaluation and every baseline |
| `gs2_export.py` | the C++ exporter |
| `run_part1.py` | the whole run |
| `finalize.py` | deployed-configuration selection, metadata cross-check |
| `floor_sweep.py` | sensitivity to the physical floor |
| `check_equivalence.py` | compiles the exported C++ and replays every report |
| `validate_oracle.py` | measures the reference oracle against synthetic ground truth |
| `make_figures.py`, `make_tables.py`, `audit.py` | outputs and the consistency audit |

Reproduce with:

```
cd src
python run_part1.py --nenv 220 --ntest 60
python finalize.py && python floor_sweep.py
python check_equivalence.py && python validate_oracle.py
python make_figures.py && python make_tables.py && python audit.py
```

---

## What the engine does

```
raw PoW --> NCO --> FIR(257) --> CORDIC --> phasor          (v1, UNCHANGED)
                                    |
                                    +--> reconstruction --> residual
                                              --> sliding LSE  L[n]
 C1  b = log2 L - log2 W - 2 log2 Vbar + 1     Vbar = causal HELD EWMA
 C2  b_amb = causal minimum-statistics tracker (32-report acquisition,
             then 4 sub-windows of 16 reports)
 C3  kappa_H, Delta = ATE(6 causal features), int8 weights
     trigger:   b >= b_amb + kappa_H            <-- an ADD and a COMPARE
 C2' latched hysteresis FSM; kappa and b_amb latched, feature EWMAs held
```

Reporting rate 120 reports/s. `Lambda` is decimated report-wise by **maximum**,
so a report is labelled an event report if **any** sample inside it is labelled.

**The six features** (all causal, all frozen while the FSM is asserted):
ambient floor `b_amb`; slow EWMA of the excess `d = b - b_amb`; slow EWMA of
`|d - mean d|`; a decaying running maximum of `d`; `log2` of the magnitude
jitter; `log2` of the frequency jitter. The decaying maximum is one comparator
and one register and is the cheapest causal proxy for the upper tail of `d`,
which is what the required margin is a quantile of.

**Two changes to the algorithm relative to the 2026-08 revision**, both forced by
records 677 and 971:

1. The magnitude normaliser's hold rule is now **asymmetric**. A sustained rise
   is a new operating level and the normaliser re-acquires after 5 s; a
   sustained drop is a de-energised line and the normaliser never follows it
   down. Without this, record 677's breaker-open interval dragged `Vbar` down by
   almost eight octaves and `Lambda` exploded on the way back.
2. A **signal-presence gate**: reports whose magnitude sits more than four
   octaves below the reference are de-energised, and the tracker, the features
   and the FSM all freeze. Up to 13.8 % of record 677's current reports are
   gated this way. Detecting a dead line is a separate, trivial comparator, not
   the job of a residual trigger.

**Two changes to the learning problem**, both of which mattered more than any
model choice:

3. The second ATE output is the **hysteresis depth** `Delta`, not an absolute
   `kappa_L`. An absolute release level taken from a low ambient quantile leaves
   the FSM latched indefinitely; that alone cost about 0.15 macro F1.
4. The training target is the **F1-optimal margin** for each synthetic channel,
   not the 0.998 ambient quantile. Even *perfect* knowledge of the ambient
   quantile scores 0.695 macro F1 on the GESL records, below a well-chosen
   constant, because a description of the ambient distribution is not the
   decision boundary that minimises detection error.

---

## Headline results

36 channels (6 records x 6 phase channels), 29 424 valid reports, 24 channels
containing a reference event and 12 containing none.

| method | micro F1 | macro F1 | event recall | FA on quiet ch. | duty cycle |
|---|---|---|---|---|---|
| v1 fixed thresholds, transported | 0.027 | 0.094 | 0.150 | 8 | 0.001 |
| causal empirical quantile | 0.130 | 0.281 | 0.675 | 5 | 0.109 |
| fixed margin, tuned on synthetic | 0.369 | 0.784 | 0.975 | 2 | 0.183 |
| ATE-Q int8 + floor | 0.371 | 0.752 | 0.925 | 1 | 0.165 |
| ATE-S int8 + floor | 0.377 | **0.814** | 0.975 | 1 | 0.167 |
| **ATE-M int8 + floor (deployed)** | **0.379** | 0.761 | 0.925 | 1 | 0.166 |
| ATE-M int8, leave-one-record-out | 0.376 | 0.806 | 0.900 | 2 | 0.165 |
| best constant, chosen in hindsight † | 0.377 | 0.813 | 0.950 | 1 | 0.164 |
| per-channel ambient quantile † | 0.211 | 0.695 | 0.750 | 1 | 0.230 |
| per-channel optimum in hindsight † | 0.933 | 0.914 | 0.775 | 0 | 0.099 |

† offline oracles. They use the reference labels and are upper bounds, not
methods.

**The deployed configuration was chosen on 540 held-out synthetic channels
before any GESL record was scored**, using pooled (micro) F1 — the metric that
counts false alarms on channels with no event. It selected ATE-M with the
physical floor.

Other measured facts:

* int8 quantisation costs nothing measurable; the int8 and float rows differ by
  at most 0.009 macro F1.
* 64 weight MACs per report (6x8 + 8x2), 6 standardiser multiplies, **no divider
  anywhere and no multiplier between the goodness-of-fit and the event flag**,
  1 888 bits of constant storage.
* The exported C++ reproduces the Python reference exactly: **0 trigger
  mismatches over 30 396 reports**, max |Δb_amb| 1.8e-15, max |Δκ_H| 7.1e-15.
* Ambient floor spread across the 36 channels: 9.7 octaves after normalisation.
  The margin each channel needs spans **45x** (0.25 to 11.25 octaves).
* Calibration speed (margin MAE against the required margin, held-out
  synthetic): at 0.2 s the learned engines read 1.10–1.23 octaves against the
  empirical quantile's 1.44; the empirical quantile catches up by about 1 s.

### The floor question, answered with numbers

The physical floor `kappa_H >= log2 10` and the learned margins do different
jobs, and the sweep separates them (`out/table_floor_sweep_gesl.csv`):

| floor | ATE-M micro F1 | ATE-M FA on quiet ch. | constant micro F1 | constant FA on quiet ch. |
|---|---|---|---|---|
| 0.00 | 0.315 | 202 | 0.089 | 4 895 |
| 1.00 | 0.352 | 1 | 0.158 | 5 |
| 2.00 | 0.359 | 1 | 0.209 | 3 |
| 3.25 | 0.378 | 1 | 0.369 | 2 |

With no floor the learned margins are worth about 0.23 micro F1 and cut spurious
trigger runs on the event-free channels by 24x. As the floor rises the two
converge, because the floor then sets the threshold on most channels. Both the
synthetic selection and the GESL sweep put the optimum at the physical value.

---

## Honest limits — do not overclaim

* **The ATE does not beat a well-chosen constant on macro F1.** It matches it
  (0.761 deployed, 0.814 for ATE-S, against 0.813 for the constant chosen with
  the test labels in hand). The separation is in pooled F1, in the false-alarm
  count on quiet channels, and in how far the floor can be safely lowered.
* **The family the selection rule picked is not the family that scored best on
  the test records.** The rule picked ATE-M (micro 0.379, macro 0.761); ATE-S
  reached macro 0.814. On 540 held-out synthetic channels ATE-M leads on both
  metrics, so this is a six-record sampling difference, not evidence that ATE-S
  is better. Quote the deployed row; mention ATE-S as an observation.
* **The MLP does not rank the channels.** Per channel, the correlation between
  the median predicted margin and the hindsight optimum is 0.54 for ATE-Q, 0.54
  for ATE-S and **0.06 for ATE-M**. ATE-M gets its aggregate score from the
  floor plus a good average level, not from per-channel adaptation. This is a
  real weakness and should be stated.
* **The physical floor clips most predictions.** The raw ATE-M output exceeds
  `log2 10` on 16 % of reports and on 5 of 36 channels; for ATE-Q it is 40 % and
  13 of 36. On these six records the floor, not the model, sets the threshold on
  the majority of channels.
* **The reference oracle is imperfect.** Against synthetic ground truth its
  precision is 0.25 (0.44 once the injected windows are padded by the detector's
  own response support) and it catches 31 % of injected event windows. Every
  GESL trigger metric is therefore a comparison between methods on a common
  reference, not an absolute detection rate.
* **The oracle and the detector share a definition.** Both call an event a
  tenfold rise in normalised goodness-of-fit above an ambient floor; the oracle
  computes that floor non-causally over the whole record and the detector tracks
  it causally. The comparison is meaningful for the calibration question, which
  is what the paper claims, and it is not independent evidence that
  goodness-of-fit detects disturbances.
* **Record 677 is the hard case for everyone.** Macro F1 0.230 for the deployed
  engine, 0.275 for the best constant, and only 0.675 for the hindsight ceiling.
  Report it; do not average it away.
* **No FPGA number exists yet.** There is no area, timing or power figure
  anywhere in this package. `hls/` contains the sources for Part 2 and nothing
  more.
* **`check_equivalence.py` establishes algorithm equivalence, not
  bit-exactness.** The `ap_*` stub maps the fixed-point types to `double`.
* **`Vbar` re-acquires only after 5 s.** A genuine step down in operating level
  leaves the normaliser stale for that long, which makes the detector
  conservative. This is deliberate and untested against a record that contains
  such a step.
* Never report F1 without the duty cycle.

### Also worth knowing

The v1 coefficient array in `et_pmu_scaled.py` carries **three transcription
defects**: a tap duplicated at index 88, a tap dropped at 139 and a tap
duplicated at 239. They break linear phase (asymmetry 8.3e-5) and cost 0.79 % of
DC gain. The intended design — `firwin(257, 10 Hz, hamming)` — is reproduced
exactly and is what Part 1 uses. Worth a footnote in the paper and a fix in the
repository.

---

## Cross-check of the reference labels against the GESL metadata

Record 677 is the strongest check available: the oracle places fault inception
at 1.993 s, the breaker opening at 3.093 s and the reclose at 5.277 s, giving a
fault of 1.10 s (66 cycles, documented 64.5) and an open interval of 2.19 s
(documented 2.2 s). Record 907's single window at 2.000–2.044 s matches the
documented 1-cycle BC fault and appears only on phases B and C. Record 901's
windows appear only on phase A, as documented. Full table in
`out/table_metadata_crosscheck.csv`.

---

## Handover to Part 2

* `hls/ate_top.cpp`, `hls/ate_top.h`, `hls/ate_weights.h`, `hls/ate_tb.cpp`
* `hls/vectors.csv` — 30 396 stimulus reports, and `hls/trig_hls.csv`, the
  expected response
* `out/ate_weights.json` — all three families in a portable form, for the
  weight-precision and hidden-width DSE axes
* `typedef double ate_t` in `ate_top.h` is the single point to replace with
  `ap_fixed<W,I>` for each DSE point
* `ATE_N_MAC`, `ATE_N_SCALE_MUL`, `ATE_ROM_BITS` are exported so the DSE tables
  can be cross-checked against the synthesis reports

**Do not proceed to Part 2 assuming any area number in the previous design
record.** All of them were analytic estimates and none is carried forward here.
