/*
 * VF2++ Graph Isomorphism - Algorithm Implementation
 * HPC Project
 * 
 * Implementazione sequenziale dell'algoritmo VF2++
 */

#include "vf2pp.h"
#include "stack.h"
#include "node_ordering.h"
#include "find_candidates.h"
#include <stdlib.h>
#include <string.h>

/* ============================================================================
 * FUNZIONI HELPER INTERNE
 * ============================================================================ */

/**
 * Aggiorna T2_tilde dopo aver mappato un nodo
 */
static void update_t2_tilde_internal(const Graph* g2, int mapped_node, bool* t2_tilde) {
    /* Il nodo mappato esce dalla frontier */
    t2_tilde[mapped_node] = false;
    
    /* I suoi vicini non mappati escono dalla frontier "libera" */
    for (int i = 0; i < g2->nodes[mapped_node].num_neighbors; i++) {
        int nbr = g2->nodes[mapped_node].neighborhood[i];
        t2_tilde[nbr] = false;
    }
}

/**
 * Ripristina T2_tilde dopo backtrack
 */
static void restore_t2_tilde_internal(const Graph* g2, int unmapped_node, bool* t2_tilde) {
    bool has_mapped_neighbor = false;
    
    /* Controlla se il nodo ha ancora vicini mappati */
    for (int i = 0; i < g2->nodes[unmapped_node].num_neighbors; i++) {
        int nbr = g2->nodes[unmapped_node].neighborhood[i];
        if (g2->nodes[nbr].mapped != -1) {
            has_mapped_neighbor = true;
            break;
        }
    }
    
    /* Se non ha vicini mappati, torna nella frontier */
    if (!has_mapped_neighbor) {
        t2_tilde[unmapped_node] = true;
    }
    
    /* Ripristina i vicini */
    for (int i = 0; i < g2->nodes[unmapped_node].num_neighbors; i++) {
        int nbr = g2->nodes[unmapped_node].neighborhood[i];
        
        if (g2->nodes[nbr].mapped == -1) {
            bool nbr_has_mapped = false;
            
            for (int j = 0; j < g2->nodes[nbr].num_neighbors; j++) {
                int nbr2 = g2->nodes[nbr].neighborhood[j];
                if (g2->nodes[nbr2].mapped != -1) {
                    nbr_has_mapped = true;
                    break;
                }
            }
            
            if (!nbr_has_mapped) {
                t2_tilde[nbr] = true;
            }
        }
    }
}

/* ============================================================================
 * IMPLEMENTAZIONE ALGORITMO VF2++
 * ============================================================================ */

bool vf2pp_is_isomorphic(Graph* g1, Graph* g2) {
    /* Controlli preliminari */
    if (g1 == NULL || g2 == NULL) {
        return false;
    }
    
    if (g1->num_nodes == 0 && g2->num_nodes == 0) {
        return true;  /* Grafi vuoti sono isomorfi */
    }
    
    if (g1->num_nodes != g2->num_nodes) {
        return false;
    }
    
    if (g1->num_edges != g2->num_edges) {
        return false;
    }
    
    int n = g1->num_nodes;
    
    /* Reset mapping */
    graph_reset_mapping(g1);
    graph_reset_mapping(g2);
    
    /* Inizializza T2_tilde (tutti i nodi di G2 nella frontier iniziale) */
    bool* t2_tilde = (bool*)malloc(n * sizeof(bool));
    if (t2_tilde == NULL) {
        fprintf(stderr, "vf2pp: malloc t2_tilde fallito\n");
        return false;
    }
    for (int i = 0; i < n; i++) {
        t2_tilde[i] = true;
    }
    
    /* Calcola ordine di matching */
    int* node_order = (int*)malloc(n * sizeof(int));
    if (node_order == NULL) {
        fprintf(stderr, "vf2pp: malloc node_order fallito\n");
        free(t2_tilde);
        return false;
    }
    
    if (compute_matching_order(g1, node_order) != 0) {
        fprintf(stderr, "vf2pp: compute_matching_order fallito\n");
        free(t2_tilde);
        free(node_order);
        return false;
    }
    
    /* Inizializza stack */
    Stack stack;
    if (stack_init(&stack) != 0) {
        fprintf(stderr, "vf2pp: stack_init fallito\n");
        free(t2_tilde);
        free(node_order);
        return false;
    }
    
    /* Buffer per candidati */
    int* candidates_buf = (int*)malloc(n * sizeof(int));
    if (candidates_buf == NULL) {
        fprintf(stderr, "vf2pp: malloc candidates_buf fallito\n");
        stack_free(&stack);
        free(t2_tilde);
        free(node_order);
        return false;
    }
    
    /* Trova candidati per il primo nodo */
    int num_candidates;
    if (find_candidates(node_order[0], g1, g2, t2_tilde, 
                        candidates_buf, &num_candidates) != 0) {
        free(candidates_buf);
        stack_free(&stack);
        free(t2_tilde);
        free(node_order);
        return false;
    }
    
    /* Push primo nodo sullo stack */
    if (stack_push(&stack, node_order[0], candidates_buf, num_candidates) != 0) {
        free(candidates_buf);
        stack_free(&stack);
        free(t2_tilde);
        free(node_order);
        return false;
    }
    
    int matching_node = 1;  /* Prossimo nodo da matchare */
    int num_mapped = 0;     /* Numero di nodi mappati */
    bool found = false;
    
    /* Algoritmo principale: backtracking con stack */
    while (!stack_is_empty(&stack)) {
        StackElement* current = stack_peek(&stack);
        bool advanced = false;
        
        /* Cerca un candidato non ancora provato */
        for (int i = current->current_idx; i < current->num_candidates; i++) {
            if (current->flags[i]) {
                continue;  /* Già provato */
            }
            
            int candidate = current->candidates[i];
            
            /* Marca come provato */
            current->flags[i] = true;
            current->current_idx = i + 1;
            
            /* Verifica se il candidato è ancora disponibile */
            if (g2->nodes[candidate].mapped != -1) {
                continue;  /* Già mappato ad altro nodo */
            }
            
            /* Applica mapping */
            g1->nodes[current->node].mapped = candidate;
            g2->nodes[candidate].mapped = current->node;
            num_mapped++;
            
            /* Aggiorna T2_tilde */
            update_t2_tilde_internal(g2, candidate, t2_tilde);
            
            /* Controllo: abbiamo mappato tutti i nodi? */
            if (num_mapped == n) {
                found = true;
                goto cleanup;
            }
            
            /* Trova candidati per il prossimo nodo */
            int next_num_candidates;
            if (find_candidates(node_order[matching_node], g1, g2, t2_tilde,
                               candidates_buf, &next_num_candidates) != 0) {
                /* Errore, annulla mapping e continua */
                g1->nodes[current->node].mapped = -1;
                g2->nodes[candidate].mapped = -1;
                num_mapped--;
                restore_t2_tilde_internal(g2, candidate, t2_tilde);
                continue;
            }
            
            /* Push prossimo nodo */
            if (stack_push(&stack, node_order[matching_node], 
                          candidates_buf, next_num_candidates) != 0) {
                /* Errore, annulla mapping e continua */
                g1->nodes[current->node].mapped = -1;
                g2->nodes[candidate].mapped = -1;
                num_mapped--;
                restore_t2_tilde_internal(g2, candidate, t2_tilde);
                continue;
            }
            
            matching_node++;
            advanced = true;
            break;
        }
        
        /* Se non siamo avanzati, backtrack */
        if (!advanced) {
            stack_pop(&stack);
            matching_node--;
            
            if (!stack_is_empty(&stack)) {
                StackElement* parent = stack_peek(&stack);
                int parent_node = parent->node;
                int mapped_to = g1->nodes[parent_node].mapped;
                
                if (mapped_to != -1) {
                    /* Annulla mapping */
                    g1->nodes[parent_node].mapped = -1;
                    g2->nodes[mapped_to].mapped = -1;
                    num_mapped--;
                    
                    /* Ripristina T2_tilde */
                    restore_t2_tilde_internal(g2, mapped_to, t2_tilde);
                }
            }
        }
    }
    
cleanup:
    free(candidates_buf);
    stack_free(&stack);
    free(t2_tilde);
    free(node_order);
    
    return found;
}

VF2Result vf2pp_find_isomorphism(Graph* g1, Graph* g2) {
    VF2Result result;
    result.found = false;
    result.mapping = NULL;
    result.num_nodes = 0;
    
    if (g1 == NULL || g2 == NULL) {
        return result;
    }
    
    /* Esegui algoritmo */
    result.found = vf2pp_is_isomorphic(g1, g2);
    
    if (result.found && g1->num_nodes > 0) {
        /* Estrai mapping */
        result.num_nodes = g1->num_nodes;
        result.mapping = (int*)malloc(result.num_nodes * sizeof(int));
        
        if (result.mapping != NULL) {
            for (int i = 0; i < result.num_nodes; i++) {
                result.mapping[i] = g1->nodes[i].mapped;
            }
        }
    }
    
    return result;
}

void vf2_result_free(VF2Result* result) {
    if (result != NULL && result->mapping != NULL) {
        free(result->mapping);
        result->mapping = NULL;
    }
}

bool vf2pp_verify_mapping(const Graph* g1, const Graph* g2, 
                          const int* mapping, int num_nodes) {
    if (g1 == NULL || g2 == NULL || mapping == NULL) {
        return false;
    }
    
    if (g1->num_nodes != num_nodes || g2->num_nodes != num_nodes) {
        return false;
    }
    
    /* Verifica che il mapping sia una biiezione */
    bool* used = (bool*)calloc(num_nodes, sizeof(bool));
    if (used == NULL) {
        return false;
    }
    
    for (int i = 0; i < num_nodes; i++) {
        int m = mapping[i];
        if (m < 0 || m >= num_nodes || used[m]) {
            free(used);
            return false;
        }
        used[m] = true;
    }
    free(used);
    
    /* Verifica che gli archi siano preservati */
    for (int u = 0; u < num_nodes; u++) {
        int u_mapped = mapping[u];
        
        /* Per ogni vicino di u in G1 */
        for (int i = 0; i < g1->nodes[u].num_neighbors; i++) {
            int v = g1->nodes[u].neighborhood[i];
            int v_mapped = mapping[v];
            
            /* Verifica che (u_mapped, v_mapped) sia un arco in G2 */
            bool edge_found = false;
            for (int j = 0; j < g2->nodes[u_mapped].num_neighbors; j++) {
                if (g2->nodes[u_mapped].neighborhood[j] == v_mapped) {
                    edge_found = true;
                    break;
                }
            }
            
            if (!edge_found) {
                return false;
            }
        }
    }
    
    return true;
}
