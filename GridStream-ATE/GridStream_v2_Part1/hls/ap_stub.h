// ap_stub.h -- stand-in for the Vitis ap_* types so that ate_top.cpp can be
// compiled with a host compiler for the software/hardware equivalence check.
// Vitis HLS uses <ap_fixed.h> instead; the algorithm text is identical.
#ifndef AP_STUB_H
#define AP_STUB_H
template <int W, int I> struct ap_fixed_stub {
    double v;
    ap_fixed_stub() : v(0) {}
    ap_fixed_stub(double x) : v(x) {}
    operator double() const { return v; }
};
#define ap_fixed ap_fixed_stub
typedef bool ap_uint1;
#endif
