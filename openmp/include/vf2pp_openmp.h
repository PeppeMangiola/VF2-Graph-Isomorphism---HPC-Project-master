/*
 * =============================================================================
 * VF2++ Graph Isomorphism - OpenMP Parallel Implementation
 * HPC Project
 * =============================================================================
 * 
 * Header per l'implementazione parallela OpenMP dell'algoritmo VF2++.
 * 
 * STRATEGIA DI PARALLELIZZAZIONE:
 * ================================
 * L'algoritmo VF2++ è basato su backtracking, che è intrinsecamente sequenziale.
 * La parallelizzazione OpenMP avviene al primo livello dell'albero di ricerca:
 * 
 * - I candidati iniziali per il primo nodo vengono distribuiti tra i thread
 * - Ogni thread esplora INDIPENDENTEMENTE i sottoalberi assegnati
 * - Early termination: quando un thread trova soluzione, gli altri si fermano
 * 
 * SINCRONIZZAZIONE:
 * - Variabile shared "found" per early termination
 * - Dati del grafo read-only (no race condition)
 * - Strutture di stato PRIVATE per ogni thread
 * 
 * =============================================================================
 */

#ifndef VF2PP_OPENMP_H
#define VF2PP_OPENMP_H

#include <stdbool.h>
#include <omp.h>
#include "graph.h"

#ifdef __cplusplus
extern "C" {
#endif

/* ============================================================================
 * STRUTTURE DATI
 * ============================================================================ */

/**
 * Risultato dell'algoritmo VF2++ con metriche OpenMP
 */
typedef struct {
    bool    found;              /* true se isomorfi */
    int*    mapping;            /* mapping G1->G2 (se found) */
    int     num_nodes;          /* numero di nodi */
    int     finder_thread;      /* thread che ha trovato (-1 se non trovato) */
    double  total_time;         /* tempo totale di esecuzione */
    double  parallel_time;      /* tempo nella regione parallela */
    int     num_threads;        /* numero di thread usati */
    int     candidates_explored;/* candidati esplorati (totale) */
} VF2OpenMPResult;

/**
 * Configurazione per l'esecuzione OpenMP
 */
typedef struct {
    int     num_threads;        /* 0 = default OMP */
    bool    enable_early_term;  /* abilita early termination */
    int     verbose;            /* livello di verbosità */
} VF2OpenMPConfig;

/* ============================================================================
 * FUNZIONI PRINCIPALI
 * ============================================================================ */

/**
 * Verifica se due grafi sono isomorfi usando OpenMP.
 * Parallelizza al primo livello dell'albero di ricerca.
 * 
 * @param g1 Primo grafo (pattern)
 * @param g2 Secondo grafo (target)
 * @return true se isomorfi, false altrimenti
 */
bool vf2pp_is_isomorphic_openmp(Graph* g1, Graph* g2);

/**
 * Versione con configurazione esplicita.
 * 
 * @param g1 Primo grafo
 * @param g2 Secondo grafo
 * @param config Configurazione (NULL per default)
 * @return true se isomorfi
 */
bool vf2pp_is_isomorphic_openmp_config(Graph* g1, Graph* g2, 
                                        const VF2OpenMPConfig* config);

/**
 * Trova isomorfismo e restituisce risultato dettagliato.
 * Include mapping e metriche di performance.
 * 
 * @param g1 Primo grafo
 * @param g2 Secondo grafo
 * @param config Configurazione (NULL per default)
 * @return Struttura con risultato e metriche
 */
VF2OpenMPResult vf2pp_find_isomorphism_openmp(Graph* g1, Graph* g2,
                                               const VF2OpenMPConfig* config);

/**
 * Libera la memoria allocata nel risultato.
 * 
 * @param result Puntatore al risultato da liberare
 */
void vf2_openmp_result_free(VF2OpenMPResult* result);

/* ============================================================================
 * UTILITY
 * ============================================================================ */

/**
 * Stampa statistiche dell'esecuzione OpenMP.
 * 
 * @param result Risultato dell'esecuzione
 */
void vf2_openmp_print_stats(const VF2OpenMPResult* result);

/**
 * Restituisce configurazione di default.
 * 
 * @return Configurazione con valori default
 */
VF2OpenMPConfig vf2_openmp_default_config(void);

/**
 * Verifica che un mapping sia corretto.
 * Utile per debug e validazione.
 * 
 * @param g1 Primo grafo
 * @param g2 Secondo grafo
 * @param mapping Array del mapping
 * @param num_nodes Numero di nodi
 * @return true se mapping valido
 */
bool vf2_openmp_verify_mapping(const Graph* g1, const Graph* g2,
                                const int* mapping, int num_nodes);

#ifdef __cplusplus
}
#endif

#endif /* VF2PP_OPENMP_H */
