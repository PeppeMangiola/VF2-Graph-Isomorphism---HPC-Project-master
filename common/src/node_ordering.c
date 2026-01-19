/*
 * VF2++ Graph Isomorphism - Node Ordering Implementation
 * HPC Project
 * 
 * Implementa l'euristica VF2++ per ordinare i nodi di G1
 */

#include "node_ordering.h"
#include <string.h>
#include <stdlib.h>

/* ============================================================================
 * STRUTTURE HELPER
 * ============================================================================ */

/* Struttura per BFS */
typedef struct {
    int* queue;
    int  front;
    int  rear;
    int  capacity;
} BFSQueue;

/* Struttura per ordinare nodi per grado */
typedef struct {
    int node_id;
    int degree;
} NodeDegree;

/* ============================================================================
 * FUNZIONI HELPER
 * ============================================================================ */

static int compare_by_degree_desc(const void* a, const void* b) {
    const NodeDegree* na = (const NodeDegree*)a;
    const NodeDegree* nb = (const NodeDegree*)b;
    return nb->degree - na->degree;  /* Decrescente */
}

static int bfs_queue_init(BFSQueue* q, int capacity) {
    q->queue = (int*)malloc(capacity * sizeof(int));
    if (q->queue == NULL) return -1;
    q->front = 0;
    q->rear = 0;
    q->capacity = capacity;
    return 0;
}

static void bfs_queue_free(BFSQueue* q) {
    if (q->queue) free(q->queue);
    q->queue = NULL;
}

static void bfs_queue_push(BFSQueue* q, int val) {
    q->queue[q->rear++] = val;
}

static int bfs_queue_pop(BFSQueue* q) {
    return q->queue[q->front++];
}

static bool bfs_queue_empty(BFSQueue* q) {
    return q->front >= q->rear;
}

/* ============================================================================
 * IMPLEMENTAZIONE PRINCIPALE
 * ============================================================================ */

int compute_matching_order(const Graph* g, int* order) {
    if (g == NULL || order == NULL) {
        return -1;
    }
    
    if (g->num_nodes == 0) {
        return 0;
    }
    
    int n = g->num_nodes;
    
    /* Array per tracciare nodi già ordinati */
    bool* ordered = (bool*)calloc(n, sizeof(bool));
    if (ordered == NULL) return -1;
    
    /* Array per BFS visited */
    bool* visited = (bool*)calloc(n, sizeof(bool));
    if (visited == NULL) {
        free(ordered);
        return -1;
    }
    
    /* Queue per BFS */
    BFSQueue queue;
    if (bfs_queue_init(&queue, n) != 0) {
        free(ordered);
        free(visited);
        return -1;
    }
    
    /* Array per ordinare nodi nel livello corrente */
    NodeDegree* level_nodes = (NodeDegree*)malloc(n * sizeof(NodeDegree));
    if (level_nodes == NULL) {
        free(ordered);
        free(visited);
        bfs_queue_free(&queue);
        return -1;
    }
    
    int order_idx = 0;
    
    /* Itera finché tutti i nodi sono ordinati (gestisce componenti disconnesse) */
    while (order_idx < n) {
        /* Trova il nodo non ordinato con grado massimo */
        int start_node = -1;
        int max_degree = -1;
        
        for (int i = 0; i < n; i++) {
            if (!ordered[i] && g->nodes[i].num_neighbors > max_degree) {
                max_degree = g->nodes[i].num_neighbors;
                start_node = i;
            }
        }
        
        if (start_node == -1) {
            break;  /* Tutti ordinati */
        }
        
        /* Aggiungi il nodo di partenza */
        order[order_idx++] = start_node;
        ordered[start_node] = true;
        
        /* Reset BFS */
        memset(visited, 0, n * sizeof(bool));
        queue.front = 0;
        queue.rear = 0;
        
        /* Inizia BFS dal nodo di partenza */
        visited[start_node] = true;
        bfs_queue_push(&queue, start_node);
        
        while (!bfs_queue_empty(&queue)) {
            /* Raccogli tutti i nodi al livello corrente */
            int level_size = queue.rear - queue.front;
            int* current_level = (int*)malloc(level_size * sizeof(int));
            if (current_level == NULL) break;
            
            for (int i = 0; i < level_size; i++) {
                current_level[i] = bfs_queue_pop(&queue);
            }
            
            /* Trova tutti i vicini non visitati */
            int num_level_nodes = 0;
            
            for (int i = 0; i < level_size; i++) {
                int node = current_level[i];
                
                for (int j = 0; j < g->nodes[node].num_neighbors; j++) {
                    int neighbor = g->nodes[node].neighborhood[j];
                    
                    if (!visited[neighbor]) {
                        visited[neighbor] = true;
                        
                        /* Aggiungi a level_nodes se non ordinato */
                        if (!ordered[neighbor]) {
                            level_nodes[num_level_nodes].node_id = neighbor;
                            level_nodes[num_level_nodes].degree = g->nodes[neighbor].num_neighbors;
                            num_level_nodes++;
                        }
                        
                        /* Aggiungi alla queue per continuare BFS */
                        bfs_queue_push(&queue, neighbor);
                    }
                }
            }
            
            free(current_level);
            
            /* Ordina nodi del livello per grado decrescente */
            if (num_level_nodes > 0) {
                qsort(level_nodes, num_level_nodes, sizeof(NodeDegree), compare_by_degree_desc);
                
                /* Aggiungi all'ordine finale */
                for (int i = 0; i < num_level_nodes; i++) {
                    int node_id = level_nodes[i].node_id;
                    if (!ordered[node_id]) {
                        order[order_idx++] = node_id;
                        ordered[node_id] = true;
                    }
                }
            }
        }
    }
    
    /* Cleanup */
    free(ordered);
    free(visited);
    free(level_nodes);
    bfs_queue_free(&queue);
    
    return 0;
}

int* compute_matching_order_alloc(const Graph* g, int* out_size) {
    if (g == NULL || out_size == NULL) {
        return NULL;
    }
    
    *out_size = g->num_nodes;
    
    if (g->num_nodes == 0) {
        return NULL;
    }
    
    int* order = (int*)malloc(g->num_nodes * sizeof(int));
    if (order == NULL) {
        return NULL;
    }
    
    if (compute_matching_order(g, order) != 0) {
        free(order);
        return NULL;
    }
    
    return order;
}
