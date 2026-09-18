#ifndef ATE_TOP_H
#define ATE_TOP_H
#ifdef __SYNTHESIS__
#include <ap_fixed.h>
#else
#include "ap_stub.h"
#endif

typedef double ate_t;   // Part 2 replaces this with ap_fixed<W,I> per DSE point

// One report.  Returns the event flag.  All state is internal and static, so
// the call is a drop-in for the report-rate stage of the GridStream pipeline.
int ate_step(ate_t b, ate_t lv, ate_t fhz, int dead,
             ate_t *kappa_h_out, ate_t *kappa_l_out, ate_t *b_amb_out);
void ate_reset();
#endif
