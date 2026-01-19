/*
 * VF2++ Graph Isomorphism - Find Candidates
 * HPC Project
 * 
 * Funzioni per trovare i candidati validi per il matching di un nodo
 */

#ifndef VF2PP_FIND_CANDIDATES_H
#define VF2PP_FIND_CANDIDATES_H

#include "graph.h"
#include <stdbool.h>

/* ============================================================================
 * FUNZIONI FIND CANDIDATES
 * ============================================================================ */

/**
 * Trova i candidati in G2 per mappare il nodo u di G1
 * 
 * Un nodo v di G2 è candidato se:
 * 1. Non è già mappato
 * 2. Ha lo stesso grado di u
 * 3. È nell'insieme T2_tilde (frontier) O nessun vicino di u è ancora mappato
 * 4. Se alcuni vicini di u sono già mappati, v deve essere vicino dei loro mapping
 * 
 * @param u ID del nodo di G1 da mappare
 * @param g1 Grafo G1 (pattern)
 * @param g2 Grafo G2 (target)
 * @param t2_tilde Array booleano: t2_tilde[v] = true se v è nella frontier di G2
 * @param out_candidates Array di output per i candidati (pre-allocato, size >= g2->num_nodes)
 * @param out_num_candidates Numero di candidati trovati
 * @return 0 se successo, -1 se errore
 */
int find_candidates(int u, const Graph* g1, const Graph* g2, 
                    const bool* t2_tilde,
                    int* out_candidates, int* out_num_candidates);

/**
 * Versione che alloca l'array di output
 * @param u ID del nodo di G1
 * @param g1 Grafo G1
 * @param g2 Grafo G2
 * @param t2_tilde Array frontier
 * @param out_num_candidates Numero di candidati
 * @return Array di candidati (da liberare con free()), NULL se errore o 0 candidati
 */
int* find_candidates_alloc(int u, const Graph* g1, const Graph* g2,
                           const bool* t2_tilde, int* out_num_candidates);

/**
 * Aggiorna T2_tilde dopo aver mappato un nuovo nodo
 * Rimuove il nodo mappato e i suoi vicini non mappati dalla frontier
 * 
 * @param g2 Grafo G2
 * @param mapped_node Nodo appena mappato
 * @param t2_tilde Array frontier (modificato in-place)
 */
void update_t2_tilde(const Graph* g2, int mapped_node, bool* t2_tilde);

/**
 * Ripristina T2_tilde dopo backtrack (unmapping di un nodo)
 * 
 * @param g2 Grafo G2
 * @param unmapped_node Nodo di cui è stato rimosso il mapping
 * @param t2_tilde Array frontier (modificato in-place)
 */
void restore_t2_tilde(const Graph* g2, int unmapped_node, bool* t2_tilde);

#endif /* VF2PP_FIND_CANDIDATES_H */
