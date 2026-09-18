// ate_tb.cpp -- replays vectors.csv through ate_step and writes trig_hls.csv.
// Columns of vectors.csv: chan,b,lv,fhz,dead
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include "ate_top.h"

int main(int argc, char **argv) {
    const char *vin  = argc > 1 ? argv[1] : "vectors.csv";
    const char *vout = argc > 2 ? argv[2] : "trig_hls.csv";
    FILE *fi = fopen(vin, "r");
    if (!fi) { fprintf(stderr, "cannot open %s\n", vin); return 1; }
    FILE *fo = fopen(vout, "w");
    fprintf(fo, "chan,trig,kappa_h,kappa_l,b_amb\n");

    char line[512];
    if (!fgets(line, sizeof line, fi)) return 1;   // header
    int prev_chan = -1;
    long n = 0;
    while (fgets(line, sizeof line, fi)) {
        int chan, dead;
        double b, lv, fhz;
        if (sscanf(line, "%d,%lf,%lf,%lf,%d", &chan, &b, &lv, &fhz, &dead) != 5)
            continue;
        if (chan != prev_chan) { ate_reset(); prev_chan = chan; }
        ate_t kh, kl, amb;
        int t = ate_step(b, lv, fhz, dead, &kh, &kl, &amb);
        fprintf(fo, "%d,%d,%.17g,%.17g,%.17g\n", chan, t,
                (double)kh, (double)kl, (double)amb);
        n++;
    }
    fclose(fi); fclose(fo);
    fprintf(stderr, "ate_tb: %ld reports\n", n);
    return 0;
}
