/*
 * VF2++ Graph Isomorphism - MPI Parallel Version Header
 * HPC Project
 * 
 * Parallelizzazione dell'algoritmo VF2++ con MPI
 * 
 * STRATEGIA: Divisione dei candidati iniziali tra i processi.
 * Ogni processo esplora indipendentemente il suo sottoalbero di ricerca.
 * Early termination quando un processo trova l'isomorfismo.
 */

#ifndef VF2PP_MPI_H
#define VF2PP_MPI_H

#include "graph.h"
#include <stdbool.h>
#include <mpi.h>

/* ============================================================================
 * STRUTTURE DATI MPI
 * ============================================================================ */

/**
 * Risultato esteso per MPI con metriche di performance
 */
typedef struct {
    bool   found;           /* true se trovato isomorfismo */
    int    finder_rank;     /* rank che ha trovato (o -1) */
    double compute_time;    /* tempo di calcolo effettivo (esclude comunicazioni) */
    double comm_time;       /* tempo speso in comunicazioni MPI */
    double total_time;      /* tempo totale */
    int*   mapping;         /* mapping trovato (solo su finder_rank, NULL altrove) */
    int    num_nodes;       /* dimensione mapping */
} VF2MpiResult;

/* ============================================================================
 * TAG MPI PER COMUNICAZIONE
 * ============================================================================ */

#define VF2_TAG_FOUND       100   /* Notifica isomorfismo trovato */
#define VF2_TAG_TERMINATE   101   /* Segnale di terminazione */
#define VF2_TAG_MAPPING     102   /* Invio mapping */

/* ============================================================================
 * FUNZIONI ALGORITMO MPI
 * ============================================================================ */

/**
 * Verifica se G1 e G2 sono isomorfi usando VF2++ parallelizzato con MPI
 * 
 * STRATEGIA DI PARALLELIZZAZIONE:
 * 1. Rank 0 calcola i candidati per il primo nodo dell'ordine di matching
 * 2. I candidati vengono divisi equamente tra tutti i processi
 * 3. Ogni processo esplora indipendentemente i suoi sottoalberi
 * 4. Se un processo trova l'isomorfismo, notifica gli altri (early termination)
 * 5. MPI_Allreduce per raccogliere il risultato finale
 * 
 * @param g1 Primo grafo (pattern)
 * @param g2 Secondo grafo (target)
 * @param comm Communicator MPI (tipicamente MPI_COMM_WORLD)
 * @return true se isomorfi, false altrimenti
 * 
 * NOTA: Tutti i processi devono chiamare questa funzione con gli stessi grafi.
 *       I grafi vengono modificati internamente (campo mapped) e resettati alla fine.
 */
bool vf2pp_is_isomorphic_mpi(Graph* g1, Graph* g2, MPI_Comm comm);

/**
 * Versione con risultato esteso (include metriche di performance)
 * 
 * @param g1 Primo grafo
 * @param g2 Secondo grafo
 * @param comm Communicator MPI
 * @return Struttura con risultato e metriche
 */
VF2MpiResult vf2pp_find_isomorphism_mpi(Graph* g1, Graph* g2, MPI_Comm comm);

/**
 * Libera la memoria di un VF2MpiResult
 * @param result Puntatore al risultato
 */
void vf2_mpi_result_free(VF2MpiResult* result);

/**
 * Stampa statistiche di performance MPI (solo rank 0)
 * 
 * @param result Risultato dell'algoritmo
 * @param comm Communicator MPI
 */
void vf2_mpi_print_stats(const VF2MpiResult* result, MPI_Comm comm);

#endif /* VF2PP_MPI_H */
