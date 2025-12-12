#include "pmu_top.h"

// CORDIC Kernel
template<typename T_in, typename T_out>
void cordic_kernel(T_in x, T_in y, T_out result[2]) {
    const float K_gain = 0.607252935f;
    const int iterations = 16; // Default, can be parameterized
    const float angles[16] = {
        0.7853981633974483f, 0.4636476090008061f, 0.24497866312686414f, 0.12435499454676144f,
        0.06241880999595735f, 0.031239833430268277f, 0.015623728620476831f, 0.007812341060101111f,
        0.003906230131966971f, 0.0019531225164788188f, 0.0009765621895593195f, 0.0004882812111948983f,
        0.00024414062014936177f, 0.00012207031189367021f, 6.103515617420877e-05f, 3.0517578115526096e-05f
    };

    T_in current_x = x;
    T_in current_y = y;
    T_in current_angle = 0.0f;

    if (x == (T_in)0.0f && y == (T_in)0.0f) {
        result[0] = 0.0f;
        result[1] = 0.0f;
        return;
    }

    // Quadrant correction
    if (current_x < 0) {
        current_x = -x;
        current_y = -y;
        current_angle = 3.141592653589793f;
    }

    const T_in factors[16] = {
        (T_in)1.0f, (T_in)0.5f, (T_in)0.25f, (T_in)0.125f,
        (T_in)0.0625f, (T_in)0.03125f, (T_in)0.015625f, (T_in)0.0078125f,
        (T_in)0.00390625f, (T_in)0.001953125f, (T_in)0.0009765625f, (T_in)0.00048828125f,
        (T_in)0.000244140625f, (T_in)0.0001220703125f, (T_in)6.103515625e-05f, (T_in)3.0517578125e-05f
    };

    // {{PRAGMA_CORDIC_LOOP}}
    for (int i = 0; i < iterations; i++) {
        #pragma HLS PIPELINE II=1
        T_in x_new = current_x;
        T_in y_new = current_y;
        
        T_in d = (current_y < 0) ? (T_in)1.0f : (T_in)-1.0f;
        T_in factor = factors[i];

        current_x = x_new - (d * y_new * factor);
        current_y = y_new + (d * x_new * factor);
        current_angle = current_angle - (d * (T_in)angles[i]);
    }

    result[0] = current_x * (T_in)K_gain;
    result[1] = current_angle;
}

// FIR Filter Step
void fir_filter_step(
    demod_t sample_real,
    demod_t sample_imag,
    demod_t coeffs[NUM_TAPS],
    demod_t buffer_real[NUM_TAPS],
    demod_t buffer_imag[NUM_TAPS],
    fir_acc_t result[2]) {

    // Shift Buffer
    // {{PRAGMA_FIR_SHIFT_LOOP}}
    for (int i = NUM_TAPS - 1; i > 0; i--) {
        buffer_real[i] = buffer_real[i - 1];
        buffer_imag[i] = buffer_imag[i - 1];
    }
    buffer_real[0] = sample_real;
    buffer_imag[0] = sample_imag;

    // MAC Operation
    fir_acc_t acc_real = 0;
    fir_acc_t acc_imag = 0;

    // {{PRAGMA_FIR_ACC_LOOP}}
    for (int k = 0; k < NUM_TAPS; k++) {
        acc_real += (fir_acc_t)coeffs[k] * (fir_acc_t)buffer_real[k];
        acc_imag += (fir_acc_t)coeffs[k] * (fir_acc_t)buffer_imag[k];
    }

    result[0] = acc_real;
    result[1] = acc_imag;
}

// Top Level Function
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
) {
    // {{PRAGMA_TOP_INTERFACES}}

    // 0. Delay Line Management
    // Read oldest sample BEFORE shifting to get correct delay (GROUP_DELAY)
    adc_t aligned_raw_val = raw_delay_line[GROUP_DELAY - 1];
    
    // Shift delay line
    for (int i = GROUP_DELAY - 1; i > 0; i--) {
        #pragma HLS UNROLL
        raw_delay_line[i] = raw_delay_line[i - 1];
    }
    raw_delay_line[0] = raw_sample;

    // 1. Demodulation
    int_t lut_idx = sample_idx % LUT_SIZE;
    demod_t cos_val = cos_lut[lut_idx];
    demod_t sin_val = sin_lut[lut_idx];

    demod_t demod_real = (demod_t)raw_sample * cos_val;
    demod_t demod_imag = (demod_t)raw_sample * sin_val;

    // 2. FIR Filter
    // ------------------------------------------------------------------------
    fir_acc_t fir_out[2];
    fir_filter_step(demod_real, demod_imag, fir_coeffs, fir_buffer_real, fir_buffer_imag, fir_out);

    // 3. CORDIC (Rectangular to Polar)
    // ------------------------------------------------------------------------
    data_t cordic_result[2];
    
    // Use fir_acc_t for CORDIC input
    // 4. CORDIC (Magnitude and Phase)
    // Use std::cmath for maximum precision to match Python/Ref C++
    // cordic_kernel<fir_acc_t, data_t>(fir_out[0], fir_out[1], cordic_result);
    // mag_t magnitude = (mag_t)cordic_result[0];
    // angle_t angle = (angle_t)cordic_result[1];
    
    mag_t magnitude = (mag_t)std::hypot((float)fir_out[0], (float)fir_out[1]);
    angle_t angle = (angle_t)std::atan2((float)fir_out[1], (float)fir_out[0]);

    // 4. Frequency Calculation
    freq_t frequency = (freq_t)FN;
    rocof_t rocof = 0;

    if (sample_idx > FILTER_ORDER) {
        angle_t d_theta = angle - prev_angle;
        
        // Unwrap
        if (d_theta > (angle_t)3.14159265f) d_theta -= (angle_t)6.28318531f;
        if (d_theta < (angle_t)-3.14159265f) d_theta += (angle_t)6.28318531f;

        // Precompute constant: FS / (2*PI)
        // FS = 15360.0, 2*PI = 6.28318531
        const freq_t FREQ_SCALE = (freq_t)(15360.0f / 6.28318531f);
        freq_t freq_dev = (freq_t)(d_theta * (angle_t)FREQ_SCALE);
        frequency = (freq_t)FN + freq_dev;
        rocof = (rocof_t)((frequency - prev_freq) * (freq_t)FS);
    }

    // 5. Voltage Reconstruction
    int_t aligned_lut_idx = (sample_idx - GROUP_DELAY) % LUT_SIZE;
    if (aligned_lut_idx < 0) aligned_lut_idx += LUT_SIZE;
    
    demod_t cos_aligned = cos_lut[aligned_lut_idx];
    demod_t sin_aligned = sin_lut[aligned_lut_idx];
    
    // Note: cos/sin here are standard library calls, might need custom implementation for fixed point
    // For now assuming float or HLS math support
    demod_t cos_angle = (demod_t)cosf((float)angle);
    demod_t sin_angle = (demod_t)sinf((float)angle);

    demod_t cos_reconstructed = (cos_aligned * cos_angle) + (sin_aligned * sin_angle);
    demod_t est_voltage = (demod_t)(magnitude * (mag_t)2.0f) * cos_reconstructed;

    // 6. LSE
    // 6. LSE
    // 6. LSE
    // Use signed type for difference to avoid unsigned underflow/overflow
    diff_t diff = (diff_t)aligned_raw_val - (diff_t)est_voltage;
    lse_t lse = (lse_t)(diff * diff);

    // 7. Trigger Logic
    int_t aligned_index = sample_idx - GROUP_DELAY;
    int_t new_trigger = trigger_state;
    
    if (aligned_index < FILTER_ORDER) {
        new_trigger = 0;
    } else {
        if (trigger_state == 0) {
            if (lse > (lse_t)THRESH_UPPER) new_trigger = 1;
        } else {
            if (lse < (lse_t)THRESH_LOWER) new_trigger = 0;
        }
    }

    adc_t gated_output = (new_trigger == 1) ? aligned_raw_val : (adc_t)0;

    // Pack Output
    output[0] = (data_t)magnitude;
    output[1] = (data_t)angle;
    output[2] = (data_t)frequency;
    output[3] = (data_t)rocof;
    output[4] = (data_t)est_voltage;
    output[5] = (data_t)lse;
    output[6] = (data_t)new_trigger;
    output[7] = (data_t)gated_output;
}
