/*
 * VF2++ Graph Isomorphism - Graph I/O
 * HPC Project
 * 
 * Funzioni per leggere/scrivere grafi da/su file
 * 
 * FORMATO FILE:
 * Riga 1: <num_nodes> <num_edges>
 * Righe successive: <node_id>\t<neighbor1> <neighbor2> ... <neighborN>
 * 
 * Esempio (triangolo):
 * 3 3
 * 0	1 2
 * 1	0 2
 * 2	0 1
 */

#ifndef VF2PP_GRAPH_IO_H
#define VF2PP_GRAPH_IO_H

#include "graph.h"

/* ============================================================================
 * COSTANTI
 * ============================================================================ */

#define GRAPH_IO_MAX_LINE_LENGTH 65536
#define GRAPH_IO_MAX_NEIGHBORS   16384

/* ============================================================================
 * FUNZIONI I/O
 * ============================================================================ */

/**
 * Legge un grafo da file
 * @param filename Percorso del file
 * @return Grafo letto, NULL in caso di errore
 */
Graph* graph_read_from_file(const char* filename);

/**
 * Scrive un grafo su file
 * @param g Grafo da scrivere
 * @param filename Percorso del file
 * @return 0 se successo, -1 se errore
 */
int graph_write_to_file(const Graph* g, const char* filename);

/**
 * Legge un grafo da un buffer di memoria
 * @param buffer Buffer contenente i dati del grafo
 * @param size Dimensione del buffer
 * @return Grafo letto, NULL in caso di errore
 */
Graph* graph_read_from_buffer(const char* buffer, size_t size);

#endif /* VF2PP_GRAPH_IO_H */
