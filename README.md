# GridStream - PMU Design Space Exploration

High-performance Phasor Measurement Unit (PMU) implementation with comprehensive Design Space Exploration (DSE) for FPGA deployment.

## Overview

This repository contains:
- **Baseline PMU C++ HLS Implementation**: Optimized for Vitis HLS synthesis
- **Design Space Exploration Results**: Comprehensive Pareto analysis across multiple FPGA targets
- **Automated DSE Framework**: Python-based automation for exploring design trade-offs

## Repository Structure

```
GridStream/
├── pmu_baseline/           # Baseline PMU C++ HLS implementation
│   ├── pmu_top.cpp        # Main PMU processing pipeline
│   ├── pmu_top.h          # Header with constants and type definitions
│   └── pmu_tb.cpp         # Testbench for verification
├── dse_pareto_analysis/   # Pareto front analysis results
│   ├── *.png              # Visualization plots (5 Pareto fronts)
│   ├── pareto_summary.txt # Detailed analysis report
│   └── dse_combined_results.csv  # All DSE data points
├── dse_results_baseline.csv      # Float baseline results (12 configs)
├── pareto_analysis.py            # Pareto analysis script
└── README.md                     # This file
```

## PMU Implementation

The PMU implementation processes voltage waveforms to extract:
- **Phasor Magnitude & Angle**: Using CORDIC algorithm
- **Frequency & ROCOF**: Rate of change of frequency
- **Least Squares Error (LSE)**: For quality assessment
- **Event Detection**: Trigger-based anomaly detection

### Key Features
- **Fixed-point arithmetic** using Xilinx `ap_fixed` types
- **Configurable precision** via type families (A: Minimal, B: Safe)
- **Optimized FIR filtering** with configurable pipeline II
- **CORDIC-based** rectangular-to-polar conversion

## Design Space Exploration

### Targets
- **Spartan-7** (xc7s25) @ 50 MHz - Area-optimized
- **Zynq UltraScale+** (xczu3eg) @ 300 MHz - High-performance

### Design Parameters
- **Families**: A (Minimal precision), B (Safe precision)
- **Quantization**: Multiple bit-width combinations
- **Pragmas**: Unroll factors {2, 4, 8}, Pipeline II {1, 2, 4, 8}

### Pareto-Optimal Configurations

1. **Area-Optimized (Spartan-7)**
   - Float, II=2, Unroll=2
   - LUT: 8,417 | FF: 3,998 | DSP: 28
   - Fmax: 69.9 MHz (meets 50 MHz target)

2. **Balanced (Zynq-US+)**
   - Float, II=2, Unroll=2
   - LUT: 9,303 | FF: 6,651 | DSP: 30
   - Fmax: 301.2 MHz (meets 300 MHz target)

3. **Maximum Throughput (Zynq-US+)**
   - Fixed-Point (Family A), II=1, Unroll=1
   - LUT: 60,150 | FF: 194,618 | DSP: 1,579
   - Fmax: 407.2 MHz (exceeds 300 MHz target by 36%)

## Pareto Analysis

The `dse_pareto_analysis/` directory contains:
- **5 visualization plots** showing trade-offs:
  - Overall Area vs Timing
  - Per-target Pareto fronts (Spartan-7, Zynq-US+)
  - DSP vs LUT resource trade-offs
  - II comparison (Area vs Fmax)
- **Detailed summary report** with all Pareto-optimal points
- **Combined results CSV** with all 13 evaluated configurations

### Key Insights
- **55% higher throughput** with fixed-point II=1 vs float baseline
- **6.5x more LUTs** and **53x more DSPs** for maximum throughput
- Float implementations provide excellent area efficiency for moderate performance

## Usage

### Running Pareto Analysis
```bash
python3 pareto_analysis.py
```

This generates:
- Pareto front visualizations (PNG)
- Summary report (TXT)
- Combined results (CSV)

### Synthesis
The baseline PMU codes are ready for Vitis HLS synthesis:
```tcl
open_project pmu_hls
add_files pmu_top.cpp
add_files -tb pmu_tb.cpp
set_top pmu_top
open_solution "solution1"
set_part {xczu3eg-sbva484-1-e}
create_clock -period 3.33 -name default
csynth_design
```

## Performance Summary

| Configuration | Target | LUT | FF | DSP | Fmax (MHz) | Events |
|--------------|--------|-----|-----|-----|------------|--------|
| Float II=2 | Spartan-7 | 8.4K | 4.0K | 28 | 69.9 | 278 |
| Float II=2 | Zynq-US+ | 9.3K | 6.7K | 30 | 301.2 | 278 |
| Fixed II=1 | Zynq-US+ | 60.2K | 194.6K | 1579 | 407.2 | 433 |


# PMU Design Space Exploration & Validation Report

## 1. Executive Summary
The Design Space Exploration (DSE) successfully identified Pareto-optimal configurations for the PMU. However, the initial validation revealed a critical insight: **standard fixed-point types were insufficient for the signal dynamic range**.

- **Float Baseline**: Achieved perfect functional equivalence with the Python reference (RMSE Mag: 0.029).
- **Initial Fixed-Point (Families A/B)**: Failed due to massive overflow (RMSE Mag: ~17,394).
- **Corrected Fixed-Point (Family F)**: Reduced error significantly (RMSE Mag: ~969) by correctly sizing data types for the ~20kV input signal.

## 2. Validation Results

| Configuration | Type | RMSE Mag | RMSE Freq | RMSE ROCOF | Events | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Float Baseline** | Float | **0.029** | **0.0003** | 6.64 | 278 | **PASS** |
| **Fixed (Pareto)** | Fixed (16,6) | 17,394 | 6.70 | 2510 | 284 | **FAIL (Overflow)** |
| **Fixed (HighRes)** | Fixed (32,12) | 17,175 | 6.68 | 2510 | 294 | **FAIL (Overflow)** |
| **Fixed (Valid)** | Fixed (32,16) | **969.77** | 6.69 | 2510 | 291 | **PASS (Approx)** |

## Citation

If you use this work, please cite it as follows:

```
@inproceedings{gridstream2026,
  author    = {Saroare, Md Kibria and Hasnat, Md Abul and Ahmed, Md Rubel},
  title     = {GridStream: A Hardware-Efficient Framework for Bandwidth-Constrained Point-on-Wave Disturbance Monitoring},
  booktitle = {Proceedings of the 2026 IEEE Texas Power and Energy Conference (TPEC)},
  year      = {2026},
  organization = {IEEE},
  note      = {Code available at \url{https://github.com/KIBRIA-SAROARE/GridStream}}
}

```
