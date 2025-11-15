/*
 * rtGetInf.cpp
 *
 * Academic License - for use in teaching, academic research, and meeting
 * course requirements at degree granting institutions only.  Not for
 * government, commercial, or other organizational use.
 *
 * Code generation for model "LSE_Metric".
 *
 * Model version              : 1.60
 * Simulink Coder version : 25.2 (R2025b) 28-Jul-2025
 * C++ source code generated on : Sat Nov 15 01:52:19 2025
 *
 * Target selection: grt.tlc
 * Note: GRT includes extra infrastructure and instrumentation for prototyping
 * Embedded hardware selection: ASIC/FPGA->ASIC/FPGA
 * Emulation hardware selection:
 *    Differs from embedded hardware (Custom Processor->MATLAB Host Computer)
 * Code generation objective: Execution efficiency
 * Validation result: Not run
 */

#include "rtwtypes.h"

extern "C"
{

#include "rtGetInf.h"

}

extern "C"
{
  /* Return rtInf needed by the generated code. */
  real_T rtGetInf(void)
  {
    return rtInf;
  }

  /* Get rtInfF needed by the generated code. */
  real32_T rtGetInfF(void)
  {
    return rtInfF;
  }

  /* Return rtMinusInf needed by the generated code. */
  real_T rtGetMinusInf(void)
  {
    return rtMinusInf;
  }

  /* Return rtMinusInfF needed by the generated code. */
  real32_T rtGetMinusInfF(void)
  {
    return rtMinusInfF;
  }
}
