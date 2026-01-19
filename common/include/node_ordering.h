/*
 * VF2++ Graph Isomorphism - Node Ordering
 * HPC Project
 * 
 * Calcolo dell'ordine di matching dei nodi secondo VF2++
 * L'ordine è cruciale per l'efficienza: si parte dai nodi con più vincoli
 */

#ifndef VF2PP_NODE_ORDERING_H
#define VF2PP_NODE_ORDERING_H

#include "graph.h"

/* ============================================================================
 * FUNZIONI NODE ORDERING
 * ============================================================================ */

/**
 * Calcola l'ordine di matching dei nodi di G1 secondo VF2++
 * 
 * Strategia:
 * 1. Seleziona il nodo con grado massimo come primo
 * 2. Esegue BFS dal nodo selezionato
 * 3. Per ogni livello BFS, ordina i nodi per grado decrescente
 * 4. Ripete per eventuali componenti disconnesse
 * 
 * @param g Grafo
 * @param order Array di output (deve essere pre-allocato con g->num_nodes elementi)
 * @return 0 se successo, -1 se errore
 */
int compute_matching_order(const Graph* g, int* order);

/**
 * Versione che alloca l'array di output
 * @param g Grafo
 * @param out_size Numero di elementi nell'array restituito
 * @return Array con l'ordine, NULL in caso di errore (da liberare con free())
 */
int* compute_matching_order_alloc(const Graph* g, int* out_size);

#endif /* VF2PP_NODE_ORDERING_H */
