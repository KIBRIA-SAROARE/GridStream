/*
 * DUT_Phasor.h
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

#ifndef DUT_Phasor_h_
#define DUT_Phasor_h_
#include <cmath>
#include "rtwtypes.h"
#include "rtw_continuous.h"
#include "rtw_solver.h"
#include "rt_nonfinite.h"
#include "DUT_Phasor_types.h"

extern "C"
{

#include "rtGetInf.h"

}

extern "C"
{

#include "rtGetNaN.h"

}

/* Macros for accessing real-time model data structure */
#ifndef rtmGetErrorStatus
#define rtmGetErrorStatus(rtm)         ((rtm)->errorStatus)
#endif

#ifndef rtmSetErrorStatus
#define rtmSetErrorStatus(rtm, val)    ((rtm)->errorStatus = (val))
#endif

/* Block signals (default storage) */
struct B_DUT_Phasor_T {
  real_T Imaginary;                    /* '<S1>/Imaginary' */
  real_T Real;                         /* '<S1>/Real' */
  real_T ImaginaryI;                   /* '<S1>/Imaginary (I)' */
  real_T RealI;                        /* '<S1>/Real (I)' */
};

/* Block states (default storage) for system '<Root>' */
struct DW_DUT_Phasor_T {
  dsphdl_ComplexToMagnitudeAngl_T obj; /* '<S1>/Complex to Magnitude-Angle' */
  dsphdl_ComplexToMagnitudeAn_h_T obj_j;/* '<S1>/Complex to Magnitude-Angle1' */
  dsphdl_NCO_DUT_Phasor_T obj_e;       /* '<S1>/NCO' */
  real_T DiscreteFIRFilter_states[256];/* '<S1>/Discrete FIR Filter' */
  real_T DiscreteFIRFilter1_states[256];/* '<S1>/Discrete FIR Filter1' */
  real_T DiscreteFIRFilter2_states[256];/* '<S1>/Discrete FIR Filter2' */
  real_T DiscreteFIRFilter3_states[256];/* '<S1>/Discrete FIR Filter3' */
  real_T DiscreteFIRFilter_simContextBuf[512];/* '<S1>/Discrete FIR Filter' */
  real_T DiscreteFIRFilter_simRevCoeff[257];/* '<S1>/Discrete FIR Filter' */
  real_T DiscreteFIRFilter1_simContextBu[512];/* '<S1>/Discrete FIR Filter1' */
  real_T DiscreteFIRFilter1_simRevCoeff[257];/* '<S1>/Discrete FIR Filter1' */
  real_T DiscreteFIRFilter2_simContextBu[512];/* '<S1>/Discrete FIR Filter2' */
  real_T DiscreteFIRFilter2_simRevCoeff[257];/* '<S1>/Discrete FIR Filter2' */
  real_T DiscreteFIRFilter3_simContextBu[512];/* '<S1>/Discrete FIR Filter3' */
  real_T DiscreteFIRFilter3_simRevCoeff[257];/* '<S1>/Discrete FIR Filter3' */
  int32_T DiscreteFIRFilter_circBuf;   /* '<S1>/Discrete FIR Filter' */
  int32_T DiscreteFIRFilter1_circBuf;  /* '<S1>/Discrete FIR Filter1' */
  int32_T DiscreteFIRFilter2_circBuf;  /* '<S1>/Discrete FIR Filter2' */
  int32_T DiscreteFIRFilter3_circBuf;  /* '<S1>/Discrete FIR Filter3' */
  int32_T Delay2_DSTATE;               /* '<S2>/Delay2' */
  int32_T Delay1_DSTATE;               /* '<S2>/Delay1' */
  boolean_T objisempty;                /* '<S1>/NCO' */
  boolean_T objisempty_o;              /* '<S1>/Complex to Magnitude-Angle1' */
  boolean_T objisempty_b;              /* '<S1>/Complex to Magnitude-Angle' */
};

/* Constant parameters (default storage) */
struct ConstP_DUT_Phasor_T {
  /* Pooled Parameter (Expression: hM)
   * Referenced by:
   *   '<S1>/Discrete FIR Filter'
   *   '<S1>/Discrete FIR Filter1'
   *   '<S1>/Discrete FIR Filter2'
   *   '<S1>/Discrete FIR Filter3'
   */
  real_T pooled2[257];
};

/* External inputs (root inport signals with default storage) */
struct ExtU_DUT_Phasor_T {
  real_T V_raw;                        /* '<Root>/V_raw' */
  real_T I_raw;                        /* '<Root>/I_raw' */
};

/* External outputs (root outports fed by signals with default storage) */
struct ExtY_DUT_Phasor_T {
  int32_T ROCOF_out;                   /* '<Root>/ROCOF_out' */
  real_T V_magnitude;                  /* '<Root>/V_magnitude' */
  int64_T Frequency_out;               /* '<Root>/Frequency_out' */
  real_T V_angle;                      /* '<Root>/V_angle' */
  real_T I_angle;                      /* '<Root>/I_angle' */
  real_T I_magnitude;                  /* '<Root>/I_magnitude' */
};

/* Real-time Model Data Structure */
struct tag_RTM_DUT_Phasor_T {
  const char_T *errorStatus;
};

/* Constant parameters (default storage) */
extern const ConstP_DUT_Phasor_T DUT_Phasor_ConstP;

/* Class declaration for model DUT_Phasor */
class DUT_Phasor final
{
  /* public data and function members */
 public:
  /* Copy Constructor */
  DUT_Phasor(DUT_Phasor const&) = delete;

  /* Assignment Operator */
  DUT_Phasor& operator= (DUT_Phasor const&) & = delete;

  /* Move Constructor */
  DUT_Phasor(DUT_Phasor &&) = delete;

  /* Move Assignment Operator */
  DUT_Phasor& operator= (DUT_Phasor &&) = delete;

  /* Real-Time Model get method */
  RT_MODEL_DUT_Phasor_T * getRTM();

  /* External inputs */
  ExtU_DUT_Phasor_T DUT_Phasor_U;

  /* External outputs */
  ExtY_DUT_Phasor_T DUT_Phasor_Y;

  /* Initial conditions function */
  void initialize();

  /* model step function */
  void step();

  /* model terminate function */
  static void terminate();

  /* Constructor */
  DUT_Phasor();

  /* Destructor */
  ~DUT_Phasor();

  /* private data and function members */
 private:
  /* Block signals */
  B_DUT_Phasor_T DUT_Phasor_B;

  /* Block states */
  DW_DUT_Phasor_T DUT_Phasor_DW;

  /* private member function(s) for subsystem '<Root>'*/
  void ComplexToMagnitudeAngle_setupIm(dsphdl_ComplexToMagnitudeAngl_T *obj);
  void ComplexToMagnitudeAngle_resetIm(dsphdl_ComplexToMagnitudeAngl_T *obj);
  void ComplexToMagnitudeAngle_setup_h(dsphdl_ComplexToMagnitudeAn_h_T *obj);
  void ComplexToMagnitudeAngle_reset_h(dsphdl_ComplexToMagnitudeAn_h_T *obj);
  void DUT_Phasor_NCO_setupImpl(dsphdl_NCO_DUT_Phasor_T *obj);

  /* Real-Time Model */
  RT_MODEL_DUT_Phasor_T DUT_Phasor_M;
};

/*-
 * The generated code includes comments that allow you to trace directly
 * back to the appropriate location in the model.  The basic format
 * is <system>/block_name, where system is the system number (uniquely
 * assigned by Simulink) and block_name is the name of the block.
 *
 * Note that this particular code originates from a subsystem build,
 * and has its own system numbers different from the parent model.
 * Refer to the system hierarchy for this subsystem below, and use the
 * MATLAB hilite_system command to trace the generated code back
 * to the parent model.  For example,
 *
 * hilite_system('Streaming_ET_PMU_907/DUT_Phasor Estimation Algorithm1')    - opens subsystem Streaming_ET_PMU_907/DUT_Phasor Estimation Algorithm1
 * hilite_system('Streaming_ET_PMU_907/DUT_Phasor Estimation Algorithm1/Kp') - opens and selects block Kp
 *
 * Here is the system hierarchy for this model
 *
 * '<Root>' : 'Streaming_ET_PMU_907'
 * '<S1>'   : 'Streaming_ET_PMU_907/DUT_Phasor Estimation Algorithm1'
 * '<S2>'   : 'Streaming_ET_PMU_907/DUT_Phasor Estimation Algorithm1/Frequency_ROCOF'
 * '<S3>'   : 'Streaming_ET_PMU_907/DUT_Phasor Estimation Algorithm1/Frequency_ROCOF/HDL_unwrap_1'
 * '<S4>'   : 'Streaming_ET_PMU_907/DUT_Phasor Estimation Algorithm1/Frequency_ROCOF/HDL_unwrap_2'
 * '<S5>'   : 'Streaming_ET_PMU_907/DUT_Phasor Estimation Algorithm1/Frequency_ROCOF/HDL_unwrap_3'
 * '<S6>'   : 'Streaming_ET_PMU_907/DUT_Phasor Estimation Algorithm1/Frequency_ROCOF/HDL_unwrap_1/Compare To Constant'
 * '<S7>'   : 'Streaming_ET_PMU_907/DUT_Phasor Estimation Algorithm1/Frequency_ROCOF/HDL_unwrap_1/Compare To Constant1'
 * '<S8>'   : 'Streaming_ET_PMU_907/DUT_Phasor Estimation Algorithm1/Frequency_ROCOF/HDL_unwrap_2/Compare To Constant'
 * '<S9>'   : 'Streaming_ET_PMU_907/DUT_Phasor Estimation Algorithm1/Frequency_ROCOF/HDL_unwrap_2/Compare To Constant1'
 * '<S10>'  : 'Streaming_ET_PMU_907/DUT_Phasor Estimation Algorithm1/Frequency_ROCOF/HDL_unwrap_3/Compare To Constant'
 * '<S11>'  : 'Streaming_ET_PMU_907/DUT_Phasor Estimation Algorithm1/Frequency_ROCOF/HDL_unwrap_3/Compare To Constant1'
 */
#endif                                 /* DUT_Phasor_h_ */
