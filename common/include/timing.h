/*
 * VF2++ Graph Isomorphism - Timing Utilities
 * HPC Project
 * 
 * Funzioni per misurare il tempo con alta precisione
 */

#ifndef VF2PP_TIMING_H
#define VF2PP_TIMING_H

#include <time.h>
#include <stdint.h>

/* ============================================================================
 * STRUTTURE
 * ============================================================================ */

/**
 * Timer ad alta precisione usando CLOCK_MONOTONIC
 */
typedef struct {
    struct timespec start;
    struct timespec end;
} Timer;

/**
 * Statistiche di timing per multiple esecuzioni
 */
typedef struct {
    double min;
    double max;
    double mean;
    double std_dev;
    int    num_samples;
} TimingStats;

/* ============================================================================
 * FUNZIONI TIMING
 * ============================================================================ */

/**
 * Avvia il timer
 * @param timer Puntatore al timer
 */
static inline void timer_start(Timer* timer) {
    clock_gettime(CLOCK_MONOTONIC, &timer->start);
}

/**
 * Ferma il timer
 * @param timer Puntatore al timer
 */
static inline void timer_stop(Timer* timer) {
    clock_gettime(CLOCK_MONOTONIC, &timer->end);
}

/**
 * Calcola il tempo trascorso in secondi
 * @param timer Puntatore al timer
 * @return Tempo in secondi (double)
 */
static inline double timer_elapsed(const Timer* timer) {
    double start_sec = timer->start.tv_sec + timer->start.tv_nsec / 1e9;
    double end_sec = timer->end.tv_sec + timer->end.tv_nsec / 1e9;
    return end_sec - start_sec;
}

/**
 * Calcola statistiche da un array di tempi
 * @param times Array di tempi
 * @param num_samples Numero di campioni
 * @return Struttura con statistiche
 */
TimingStats timing_compute_stats(const double* times, int num_samples);

/**
 * Stampa statistiche formattate
 * @param stats Statistiche
 * @param label Etichetta descrittiva
 */
void timing_print_stats(const TimingStats* stats, const char* label);

#endif /* VF2PP_TIMING_H */
