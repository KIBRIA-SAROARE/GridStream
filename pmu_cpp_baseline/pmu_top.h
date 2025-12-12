#ifndef PMU_TOP_H
#define PMU_TOP_H

// #include "ap_fixed.h"
#include <cmath>

// Float II=1 Config
// All types are float
typedef int int_t;
typedef float data_t;
typedef float adc_t;

typedef float demod_t; 
typedef float fir_acc_t;
typedef float mag_t;
typedef float angle_t;

typedef float freq_t;
typedef float rocof_t;
typedef float lse_t;

// Signed difference type for LSE
typedef float diff_t;

#define FS 15360.0f
#define FN 60.0f
#define OMEGA_0 (2.0f * M_PI * FN)
#define LUT_SIZE 256
#define GROUP_DELAY 128
#define FILTER_ORDER 256
#define NUM_TAPS 257

// Scaling for Float (No scaling needed)
#define SCALE_ALPHA 1.0f
// Thresholds unscaled (10^7)
#define THRESH_UPPER 10000000.0f
#define THRESH_LOWER 300.0f

// Function Prototypes
void pmu_top(
    adc_t raw_sample,
    int_t sample_idx,
    demod_t cos_lut[LUT_SIZE],
    demod_t sin_lut[LUT_SIZE],
    demod_t fir_coeffs[NUM_TAPS],
    demod_t fir_buffer_real[NUM_TAPS],
    demod_t fir_buffer_imag[NUM_TAPS],
    adc_t raw_delay_line[GROUP_DELAY],
    angle_t prev_angle,
    freq_t prev_freq,
    int_t trigger_state,
    data_t output[8]
);

#endif
