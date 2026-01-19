/*
 * VF2++ Graph Isomorphism - Timing Implementation
 * HPC Project
 */

#include "timing.h"
#include <stdio.h>
#include <math.h>

TimingStats timing_compute_stats(const double* times, int num_samples) {
    TimingStats stats = {0};
    
    if (times == NULL || num_samples <= 0) {
        return stats;
    }
    
    stats.num_samples = num_samples;
    stats.min = times[0];
    stats.max = times[0];
    
    double sum = 0.0;
    
    for (int i = 0; i < num_samples; i++) {
        sum += times[i];
        if (times[i] < stats.min) stats.min = times[i];
        if (times[i] > stats.max) stats.max = times[i];
    }
    
    stats.mean = sum / num_samples;
    
    /* Calcola deviazione standard */
    if (num_samples > 1) {
        double sum_sq_diff = 0.0;
        for (int i = 0; i < num_samples; i++) {
            double diff = times[i] - stats.mean;
            sum_sq_diff += diff * diff;
        }
        stats.std_dev = sqrt(sum_sq_diff / (num_samples - 1));
    } else {
        stats.std_dev = 0.0;
    }
    
    return stats;
}

void timing_print_stats(const TimingStats* stats, const char* label) {
    if (stats == NULL) {
        return;
    }
    
    printf("=== %s ===\n", label ? label : "Timing Statistics");
    printf("  Samples: %d\n", stats->num_samples);
    printf("  Min:     %.6f s\n", stats->min);
    printf("  Max:     %.6f s\n", stats->max);
    printf("  Mean:    %.6f s\n", stats->mean);
    printf("  Std Dev: %.6f s\n", stats->std_dev);
}
