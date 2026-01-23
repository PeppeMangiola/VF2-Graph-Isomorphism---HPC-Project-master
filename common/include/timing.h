/*
 * VF2++ Graph Isomorphism - Timing Utilities
 * HPC Project
 * * Funzioni per misurare il tempo con alta precisione
 */

#ifndef VF2PP_TIMING_H
#define VF2PP_TIMING_H

#include <time.h>
#include <stdint.h>

/* AGGIUNTA PER WINDOWS: Header necessario */
#ifdef _WIN32
    #include <windows.h>
#endif

/* ============================================================================
 * STRUTTURE
 * ============================================================================ */

/**
 * Timer ad alta precisione
 * - Linux: usa clock_gettime / CLOCK_MONOTONIC
 * - Windows: usa QueryPerformanceCounter
 */
typedef struct {
#ifdef _WIN32
    /* Strutture specifiche Windows */
    LARGE_INTEGER start;
    LARGE_INTEGER end;
    LARGE_INTEGER frequency;
#else
    /* Strutture originali Linux */
    struct timespec start;
    struct timespec end;
#endif
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
#ifdef _WIN32
    QueryPerformanceFrequency(&timer->frequency);
    QueryPerformanceCounter(&timer->start);
#else
    clock_gettime(CLOCK_MONOTONIC, &timer->start);
#endif
}

/**
 * Ferma il timer
 * @param timer Puntatore al timer
 */
static inline void timer_stop(Timer* timer) {
#ifdef _WIN32
    QueryPerformanceCounter(&timer->end);
#else
    clock_gettime(CLOCK_MONOTONIC, &timer->end);
#endif
}

/**
 * Calcola il tempo trascorso in secondi
 * @param timer Puntatore al timer
 * @return Tempo in secondi (double)
 */
static inline double timer_elapsed(const Timer* timer) {
#ifdef _WIN32
    /* Calcolo per Windows */
    return (double)(timer->end.QuadPart - timer->start.QuadPart) / (double)timer->frequency.QuadPart;
#else
    /* Calcolo originale per Linux */
    double start_sec = timer->start.tv_sec + timer->start.tv_nsec / 1e9;
    double end_sec = timer->end.tv_sec + timer->end.tv_nsec / 1e9;
    return end_sec - start_sec;
#endif
}

#endif // VF2PP_TIMING_H