/*
 * LSE_Metric.h
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

#ifndef LSE_Metric_h_
#define LSE_Metric_h_
#include <cmath>
#include "rtwtypes.h"
#include "rtw_continuous.h"
#include "rtw_solver.h"
#include "rt_nonfinite.h"
#include "LSE_Metric_types.h"

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
struct B_LSE_Metric_T {
  int16_T NCO_o1;                      /* '<S1>/NCO' */
};

/* Block states (default storage) for system '<Root>' */
struct DW_LSE_Metric_T {
  dsphdl_NCO_LSE_Metric_T obj;         /* '<S1>/NCO' */
  boolean_T Relay_Mode;                /* '<S1>/Relay' */
  boolean_T objisempty;                /* '<S1>/NCO' */
};

/* External inputs (root inport signals with default storage) */
struct ExtU_LSE_Metric_T {
  real_T In1;                          /* '<Root>/In1' */
  real_T signal1;                      /* '<Root>/signal1' */
  int64_T signal2;                     /* '<Root>/signal2' */
  real_T signal3;                      /* '<Root>/signal3' */
};

/* External outputs (root outports fed by signals with default storage) */
struct ExtY_LSE_Metric_T {
  real_T Out1;                         /* '<Root>/Out1' */
};

/* Real-time Model Data Structure */
struct tag_RTM_LSE_Metric_T {
  const char_T *errorStatus;
};

/* Class declaration for model LSE_Metric */
class LSE_Metric final
{
  /* public data and function members */
 public:
  /* Copy Constructor */
  LSE_Metric(LSE_Metric const&) = delete;

  /* Assignment Operator */
  LSE_Metric& operator= (LSE_Metric const&) & = delete;

  /* Move Constructor */
  LSE_Metric(LSE_Metric &&) = delete;

  /* Move Assignment Operator */
  LSE_Metric& operator= (LSE_Metric &&) = delete;

  /* Real-Time Model get method */
  RT_MODEL_LSE_Metric_T * getRTM();

  /* External inputs */
  ExtU_LSE_Metric_T LSE_Metric_U;

  /* External outputs */
  ExtY_LSE_Metric_T LSE_Metric_Y;

  /* Initial conditions function */
  void initialize();

  /* model step function */
  void step();

  /* model terminate function */
  static void terminate();

  /* Constructor */
  LSE_Metric();

  /* Destructor */
  ~LSE_Metric();

  /* private data and function members */
 private:
  /* Block signals */
  B_LSE_Metric_T LSE_Metric_B;

  /* Block states */
  DW_LSE_Metric_T LSE_Metric_DW;

  /* private member function(s) for subsystem '<Root>'*/
  void LSE_Metric_NCO_setupImpl(dsphdl_NCO_LSE_Metric_T *obj);

  /* Real-Time Model */
  RT_MODEL_LSE_Metric_T LSE_Metric_M;
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
 * hilite_system('Streaming_ET_PMU_907/LSE_Metric')    - opens subsystem Streaming_ET_PMU_907/LSE_Metric
 * hilite_system('Streaming_ET_PMU_907/LSE_Metric/Kp') - opens and selects block Kp
 *
 * Here is the system hierarchy for this model
 *
 * '<Root>' : 'Streaming_ET_PMU_907'
 * '<S1>'   : 'Streaming_ET_PMU_907/LSE_Metric'
 */
#endif                                 /* LSE_Metric_h_ */
