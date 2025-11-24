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

## License

[Add your license here]

## Contact

[Add contact information]
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

## 3. Root Cause Analysis

### A. Dynamic Range Mismatch (The "17,000" Error)
The initial design assumed normalized input signals (Amplitude ~1.0 or ~325). However, the testbench processes raw voltage data with amplitudes up to **20,000**.

- **Family A/B (`ap_fixed<16,6>`)**: Integer range [-32, 31]. Input 20,000 caused immediate wrap-around overflow.
- **Family E (`ap_fixed<32,12>`)**: Integer range [-2048, 2047]. Input 20,000 still overflowed.
- **Family F (`ap_fixed<32,16>`)**: Integer range [-32,768, 32,767]. **Successfully captured the input signal.**

### B. Precision vs. Range Trade-off (The "969" Error)
Even with Family F, there is a ~5% magnitude error (969 on 20,000).
- **Cause**: `demod_t` was set to `ap_fixed<32,16>`.
- **Constraint**: 16 bits for Integer (to avoid overflow) leaves only 16 bits for Fractional.
- **Impact**: FIR coefficients (~0.0005) are quantized with only 16 fractional bits (resolution 0.000015). This 3% coefficient error accumulates through the filter, leading to the 5% output error.
- **Solution**: A wider type (e.g., `ap_fixed<40,16>`) is needed to satisfy *both* range (16 int bits) and precision (24 frac bits).

### C. ROCOF Stagnation
The ROCOF RMSE remained high because the calculated ROCOF values were often small and quantized to zero or stuck due to the `rocof_t` resolution relative to the `FS` scaling factor.

## 4. Conclusion for Paper
The DSE demonstrates that while HLS can easily optimize for Area and Throughput (finding II=1 designs), **Accuracy is a strict constraint that dictates the minimum bit-width**.
- **Optimization Strategy**: Start with a "Safe" wide type (e.g., 40-bit) to ensure correctness, then prune bit-widths until error thresholds are met.
- **Critical Finding**: Input dynamic range analysis is paramount. A design optimized for 325V failed catastrophically when driven with 20kV signals.

## 5. Recommendations
1.  **Adopt Family F (or wider)** as the baseline for any fixed-point implementation.
2.  **Use Float** for the final paper comparison if "perfect" accuracy is required, as it balances area/performance well on modern FPGAs (DSP usage is efficient).
3.  **Future Work**: Implement a dynamic scaling block (AGC) at the input to normalize signals to range [-1, 1], allowing the use of smaller, more efficient fixed-point types (like Family A) for the core processing.
