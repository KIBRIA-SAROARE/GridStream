/*
 * DUT_Phasor_types.h
 *
 * Academic License - for use in teaching, academic research, and meeting
 * course requirements at degree granting institutions only.  Not for
 * government, commercial, or other organizational use.
 *
 * Code generation for model "DUT_Phasor".
 *
 * Model version              : 1.60
 * Simulink Coder version : 25.2 (R2025b) 28-Jul-2025
 * C++ source code generated on : Sat Nov 15 01:56:44 2025
 *
 * Target selection: grt.tlc
 * Note: GRT includes extra infrastructure and instrumentation for prototyping
 * Embedded hardware selection: ASIC/FPGA->ASIC/FPGA
 * Emulation hardware selection:
 *    Differs from embedded hardware (Custom Processor->MATLAB Host Computer)
 * Code generation objective: Execution efficiency
 * Validation result: Not run
 */

#ifndef DUT_Phasor_types_h_
#define DUT_Phasor_types_h_
#include "rtwtypes.h"
#ifndef struct_dsphdl_ComplexToMagnitudeAngl_T
#define struct_dsphdl_ComplexToMagnitudeAngl_T

struct dsphdl_ComplexToMagnitudeAngl_T
{
  int32_T isInitialized;
  real_T xPipeline[18];
  real_T yPipeline[18];
  real_T zPipeline[18];
  boolean_T validPipeline[441];
  real_T pPostScale;
  real_T pQuadrantIn[18];
  real_T pXYReversed[18];
  real_T pQuadrantOut;
  real_T pPipeout;
  real_T pXAbsolute;
  real_T pYAbsolute;
  real_T realInReg[3];
  real_T imagInReg[3];
};

#endif                              /* struct_dsphdl_ComplexToMagnitudeAngl_T */

#ifndef struct_dsphdl_ComplexToMagnitudeAn_h_T
#define struct_dsphdl_ComplexToMagnitudeAn_h_T

struct dsphdl_ComplexToMagnitudeAn_h_T
{
  int32_T isInitialized;
  real_T xPipeline[12];
  real_T yPipeline[12];
  real_T zPipeline[12];
  boolean_T validPipeline[225];
  real_T pPostScale;
  real_T pQuadrantIn[12];
  real_T pXYReversed[12];
  real_T pQuadrantOut;
  real_T pPipeout;
  real_T pXAbsolute;
  real_T pYAbsolute;
  real_T realInReg[3];
  real_T imagInReg[3];
};

#endif                              /* struct_dsphdl_ComplexToMagnitudeAn_h_T */

#ifndef struct_dsphdl_NCO_DUT_Phasor_T
#define struct_dsphdl_NCO_DUT_Phasor_T

struct dsphdl_NCO_DUT_Phasor_T
{
  int32_T isInitialized;
  int32_T phaseInc;
  int32_T phaseOff;
  int32_T tmpAcc;
  int32_T tmpAcc2;
  uint8_T dither;
  int16_T phaseQuant;
  int32_T acc;
  uint16_T phaseOutReg[6];
  boolean_T validReg[6];
  int16_T sineReg[6];
  int16_T cosReg[6];
};

#endif                                 /* struct_dsphdl_NCO_DUT_Phasor_T */

/* Forward declaration for rtModel */
typedef struct tag_RTM_DUT_Phasor_T RT_MODEL_DUT_Phasor_T;

#endif                                 /* DUT_Phasor_types_h_ */
