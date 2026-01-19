/*
 * VF2++ Graph Isomorphism - Graph Data Structures
 * HPC Project
 * 
 * Header per le strutture dati del grafo
 */

#ifndef VF2PP_GRAPH_H
#define VF2PP_GRAPH_H

#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>

/* ============================================================================
 * STRUTTURE DATI PRINCIPALI
 * ============================================================================ */

/**
 * Nodo del grafo
 * - neighborhood: array dei vicini (ID dei nodi adiacenti)
 * - num_neighbors: grado del nodo
 * - id: identificatore univoco del nodo (0-based)
 * - mapped: -1 se non mappato, altrimenti ID del nodo mappato nell'altro grafo
 */
typedef struct {
    int* neighborhood;
    int  num_neighbors;
    int  id;
    int  mapped;
} Node;

/**
 * Grafo rappresentato come lista di adiacenza
 * - num_nodes: numero totale di nodi
 * - num_edges: numero totale di archi (non diretto = ogni arco contato 2 volte)
 * - nodes: array di nodi
 */
typedef struct {
    int   num_nodes;
    int   num_edges;
    Node* nodes;
} Graph;

/* ============================================================================
 * FUNZIONI DI GESTIONE GRAFO
 * ============================================================================ */

/**
 * Crea un grafo vuoto con num_nodes nodi
 * @param num_nodes Numero di nodi
 * @return Puntatore al grafo allocato, NULL in caso di errore
 */
Graph* graph_create(int num_nodes);

/**
 * Libera tutta la memoria del grafo
 * @param g Puntatore al grafo da liberare
 */
void graph_free(Graph* g);

/**
 * Aggiunge i vicini a un nodo (sovrascrive eventuali vicini esistenti)
 * @param g Grafo
 * @param node_id ID del nodo
 * @param neighbors Array di ID dei vicini
 * @param num_neighbors Numero di vicini
 * @return 0 se successo, -1 se errore
 */
int graph_set_neighbors(Graph* g, int node_id, const int* neighbors, int num_neighbors);

/**
 * Resetta tutti i mapping del grafo a -1
 * @param g Grafo
 */
void graph_reset_mapping(Graph* g);

/**
 * Crea una copia profonda del grafo
 * @param g Grafo sorgente
 * @return Nuovo grafo (copia), NULL in caso di errore
 */
Graph* graph_clone(const Graph* g);

/**
 * Stampa il grafo su stdout (per debug)
 * @param g Grafo
 */
void graph_print(const Graph* g);

/**
 * Calcola la memoria occupata dal grafo in bytes
 * @param g Grafo
 * @return Dimensione in bytes
 */
size_t graph_memory_size(const Graph* g);

#endif /* VF2PP_GRAPH_H */
