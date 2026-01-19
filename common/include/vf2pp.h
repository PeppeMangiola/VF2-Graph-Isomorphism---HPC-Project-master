/*
 * VF2++ Graph Isomorphism - Main Algorithm Header
 * HPC Project
 * 
 * Header principale per l'algoritmo VF2++
 */

#ifndef VF2PP_H
#define VF2PP_H

#include "graph.h"
#include <stdbool.h>

/* ============================================================================
 * STRUTTURE RISULTATO
 * ============================================================================ */

/**
 * Risultato dell'algoritmo VF2++
 * - found: true se trovato isomorfismo
 * - mapping: array dove mapping[i] = j significa che nodo i di G1 mappa a nodo j di G2
 *            NULL se found=false o se non richiesto
 * - num_nodes: dimensione del mapping
 */
typedef struct {
    bool  found;
    int*  mapping;
    int   num_nodes;
} VF2Result;

/* ============================================================================
 * FUNZIONI ALGORITMO
 * ============================================================================ */

/**
 * Verifica se G1 e G2 sono isomorfi usando VF2++
 * 
 * @param g1 Primo grafo
 * @param g2 Secondo grafo
 * @return true se isomorfi, false altrimenti
 */
bool vf2pp_is_isomorphic(Graph* g1, Graph* g2);

/**
 * Verifica isomorfismo e restituisce il mapping
 * 
 * @param g1 Primo grafo
 * @param g2 Secondo grafo
 * @return Struttura con risultato e mapping (mapping da liberare con free())
 */
VF2Result vf2pp_find_isomorphism(Graph* g1, Graph* g2);

/**
 * Libera la memoria di un VF2Result
 * @param result Puntatore al risultato
 */
void vf2_result_free(VF2Result* result);

/**
 * Verifica che un mapping sia valido (per testing)
 * @param g1 Primo grafo
 * @param g2 Secondo grafo  
 * @param mapping Array di mapping
 * @param num_nodes Dimensione del mapping
 * @return true se il mapping è un isomorfismo valido
 */
bool vf2pp_verify_mapping(const Graph* g1, const Graph* g2, 
                          const int* mapping, int num_nodes);

#endif /* VF2PP_H */
