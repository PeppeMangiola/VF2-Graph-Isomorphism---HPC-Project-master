/*
 * VF2++ Graph Isomorphism - Graph Implementation
 * HPC Project
 */

#include "graph.h"
#include <string.h>

/* ============================================================================
 * IMPLEMENTAZIONE FUNZIONI GRAFO
 * ============================================================================ */

Graph* graph_create(int num_nodes) {
    if (num_nodes < 0) {
        fprintf(stderr, "graph_create: num_nodes non può essere negativo\n");
        return NULL;
    }
    
    Graph* g = (Graph*)malloc(sizeof(Graph));
    if (g == NULL) {
        fprintf(stderr, "graph_create: malloc fallito per Graph\n");
        return NULL;
    }
    
    g->num_nodes = num_nodes;
    g->num_edges = 0;
    
    if (num_nodes == 0) {
        g->nodes = NULL;
        return g;
    }
    
    g->nodes = (Node*)malloc(num_nodes * sizeof(Node));
    if (g->nodes == NULL) {
        fprintf(stderr, "graph_create: malloc fallito per nodes\n");
        free(g);
        return NULL;
    }
    
    /* Inizializza tutti i nodi */
    for (int i = 0; i < num_nodes; i++) {
        g->nodes[i].neighborhood = NULL;
        g->nodes[i].num_neighbors = 0;
        g->nodes[i].id = i;
        g->nodes[i].mapped = -1;
    }
    
    return g;
}

void graph_free(Graph* g) {
    if (g == NULL) {
        return;
    }
    
    if (g->nodes != NULL) {
        for (int i = 0; i < g->num_nodes; i++) {
            if (g->nodes[i].neighborhood != NULL) {
                free(g->nodes[i].neighborhood);
            }
        }
        free(g->nodes);
    }
    
    free(g);
}

int graph_set_neighbors(Graph* g, int node_id, const int* neighbors, int num_neighbors) {
    if (g == NULL || node_id < 0 || node_id >= g->num_nodes) {
        return -1;
    }
    
    if (num_neighbors < 0) {
        return -1;
    }
    
    Node* node = &g->nodes[node_id];
    
    /* Libera vecchi vicini se esistono */
    if (node->neighborhood != NULL) {
        /* Aggiorna conteggio archi (rimuovi vecchi) */
        g->num_edges -= node->num_neighbors;
        free(node->neighborhood);
        node->neighborhood = NULL;
    }
    
    node->num_neighbors = num_neighbors;
    
    if (num_neighbors == 0) {
        return 0;
    }
    
    /* Alloca e copia nuovi vicini */
    node->neighborhood = (int*)malloc(num_neighbors * sizeof(int));
    if (node->neighborhood == NULL) {
        node->num_neighbors = 0;
        return -1;
    }
    
    memcpy(node->neighborhood, neighbors, num_neighbors * sizeof(int));
    
    /* Aggiorna conteggio archi */
    g->num_edges += num_neighbors;
    
    return 0;
}

void graph_reset_mapping(Graph* g) {
    if (g == NULL || g->nodes == NULL) {
        return;
    }
    
    for (int i = 0; i < g->num_nodes; i++) {
        g->nodes[i].mapped = -1;
    }
}

Graph* graph_clone(const Graph* g) {
    if (g == NULL) {
        return NULL;
    }
    
    Graph* clone = graph_create(g->num_nodes);
    if (clone == NULL) {
        return NULL;
    }
    
    clone->num_edges = g->num_edges;
    
    for (int i = 0; i < g->num_nodes; i++) {
        clone->nodes[i].id = g->nodes[i].id;
        clone->nodes[i].mapped = g->nodes[i].mapped;
        clone->nodes[i].num_neighbors = g->nodes[i].num_neighbors;
        
        if (g->nodes[i].num_neighbors > 0) {
            clone->nodes[i].neighborhood = (int*)malloc(g->nodes[i].num_neighbors * sizeof(int));
            if (clone->nodes[i].neighborhood == NULL) {
                graph_free(clone);
                return NULL;
            }
            memcpy(clone->nodes[i].neighborhood, g->nodes[i].neighborhood, 
                   g->nodes[i].num_neighbors * sizeof(int));
        }
    }
    
    return clone;
}

void graph_print(const Graph* g) {
    if (g == NULL) {
        printf("Graph: NULL\n");
        return;
    }
    
    printf("Graph: %d nodes, %d edges (directed count)\n", g->num_nodes, g->num_edges);
    
    for (int i = 0; i < g->num_nodes; i++) {
        printf("  Node %d (deg=%d, mapped=%d): ", 
               g->nodes[i].id, g->nodes[i].num_neighbors, g->nodes[i].mapped);
        
        for (int j = 0; j < g->nodes[i].num_neighbors; j++) {
            printf("%d ", g->nodes[i].neighborhood[j]);
        }
        printf("\n");
    }
}

size_t graph_memory_size(const Graph* g) {
    if (g == NULL) {
        return 0;
    }
    
    size_t size = sizeof(Graph);
    size += g->num_nodes * sizeof(Node);
    
    for (int i = 0; i < g->num_nodes; i++) {
        size += g->nodes[i].num_neighbors * sizeof(int);
    }
    
    return size;
}
