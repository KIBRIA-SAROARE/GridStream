#ifndef PMU_TOP_H
#define PMU_TOP_H

#include <cmath>
#include <cstdint>
#include "ap_fixed.h"
#include "ap_int.h"

// Constants
#define FS 15360.0f
#define FN 60.0f
#define OMEGA_0 376.99111843077515f // 2*pi*60
#define FILTER_ORDER 256
#define NUM_TAPS 257
#define LUT_SIZE 256
#define GROUP_DELAY 128          // (NUM_TAPS - 1) / 2

// Scaling Factor (Injected by DSE or default)
#ifndef SCALE_ALPHA
#define SCALE_ALPHA 20000.0f
#endif

// Thresholds (Scaled)
// Original: Upper 1e7, Lower 300
// Scaled = Original / (ALPHA^2)
#define THRESH_UPPER (10000000.0f / (SCALE_ALPHA * SCALE_ALPHA))
#define THRESH_LOWER (300.0f / (SCALE_ALPHA * SCALE_ALPHA))

// Data Types (Injected by DSE or default to float)
#ifdef DSE_FIXED_POINT
    // These typedefs will be populated by the DSE runner via compiler flags or a generated header
    // For now, we define them here if DSE_TYPES_HEADER is defined
    #include "dse_types.h"
#else
    // Default Floating Point Reference
    typedef float adc_t;
    typedef float demod_t;
    typedef float fir_acc_t;
    typedef float mag_t;
    typedef float angle_t;
    typedef float freq_t;
    typedef float rocof_t;
    typedef float lse_t;
    typedef float data_t; // Generic fallback
    typedef int32_t int_t;
#endif

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
    data_t output[8] // Keep output generic or struct? Using data_t array for now to match TB
);

#endif // PMU_TOP_H
