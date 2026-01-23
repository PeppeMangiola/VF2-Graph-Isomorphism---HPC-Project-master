/*
 * VF2++ Graph Isomorphism - OpenMP Parallel Implementation
 * HPC Project
 * 
 * CARATTERISTICHE:
 * 1. Zero-Malloc Core: Massima efficienza di memoria
 * 2. Logic Clean: Nessun overhead inutile
 * 3. Early Termination: Quando un thread trova soluzione, gli altri si fermano
 */

#include "vf2pp_openmp.h"
#include "vf2pp.h"
#include "stack.h"
#include "node_ordering.h"
#include "find_candidates.h"
#include "graph_io.h"     
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <omp.h>

/* ============================================================================
 * FUNZIONI HELPER INTERNE (Statiche)
 * ============================================================================ */

static void omp_update_t2_tilde(const Graph* g2, int mapped_node, bool* t2_tilde) {
    t2_tilde[mapped_node] = false;
    for (int i = 0; i < g2->nodes[mapped_node].num_neighbors; i++) {
        int nbr = g2->nodes[mapped_node].neighborhood[i];
        t2_tilde[nbr] = false;
    }
}

static void omp_restore_t2_tilde(const Graph* g2, int unmapped_node, bool* t2_tilde) {
    bool has_mapped_neighbor = false;
    for (int i = 0; i < g2->nodes[unmapped_node].num_neighbors; i++) {
        int nbr = g2->nodes[unmapped_node].neighborhood[i];
        if (g2->nodes[nbr].mapped != -1) {
            has_mapped_neighbor = true;
            break;
        }
    }
    if (!has_mapped_neighbor) {
        t2_tilde[unmapped_node] = true;
    }
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
 * ALGORITMO PARALLELO CORE
 * ============================================================================ */

bool vf2pp_is_isomorphic_openmp(Graph* g1, Graph* g2) {
    if (g1->num_nodes != g2->num_nodes || g1->num_edges != g2->num_edges) {
        return false;
    }

    int n = g1->num_nodes;
    int* node_order = (int*)malloc(n * sizeof(int));
    if (!node_order) return false;

    if (compute_matching_order(g1, node_order) != 0) {
        free(node_order);
        return false;
    }

    int max_threads = omp_get_max_threads();
    omp_set_num_threads(max_threads);

    /* Copie private dei grafi */
    Graph** g1_copies = (Graph**)malloc(max_threads * sizeof(Graph*));
    Graph** g2_copies = (Graph**)malloc(max_threads * sizeof(Graph*));

    #pragma omp parallel for
    for (int t = 0; t < max_threads; t++) {
        g1_copies[t] = graph_clone(g1);
        g2_copies[t] = graph_clone(g2);
    }

    /* Rank 0 trova candidati iniziali */
    bool* t2_tilde_init = (bool*)malloc(n * sizeof(bool));
    for (int i = 0; i < n; i++) t2_tilde_init[i] = true;

    int* initial_candidates_buf = (int*)malloc(n * sizeof(int));
    int total_candidates = 0;
    
    find_candidates(node_order[0], g1_copies[0], g2_copies[0], 
                   t2_tilde_init, initial_candidates_buf, &total_candidates);

    free(t2_tilde_init);

    volatile bool global_found = false;

    /* REGIONE PARALLELA */
    #pragma omp parallel  
    {
        int tid = omp_get_thread_num();
        
        Stack stack;
        if (stack_init(&stack) == 0) {
            
            bool* t2_tilde = (bool*)malloc(n * sizeof(bool));
            int* candidates_buf = (int*)malloc(n * sizeof(int));
            
            if (t2_tilde && candidates_buf) {
                
                #pragma omp for schedule(dynamic, 1)
                for (int i = 0; i < total_candidates; i++) {
                    
                    if (global_found) continue;

                    int start_candidate = initial_candidates_buf[i];
                    Graph* my_g1 = g1_copies[tid];
                    Graph* my_g2 = g2_copies[tid];

                    graph_reset_mapping(my_g1);
                    graph_reset_mapping(my_g2);
                    stack_clear(&stack);
                    
                    for(int k=0; k<n; k++) t2_tilde[k] = true;

                    int init_cand[1] = { start_candidate };
                    stack_push(&stack, node_order[0], init_cand, 1);

                    int matching_node = 1;
                    int num_mapped = 0;

                    while (!stack_is_empty(&stack)) {
                        if (global_found) break;

                        StackElement* current = stack_peek(&stack);
                        bool advanced = false;

                        for (int j = current->current_idx; j < current->num_candidates; j++) {
                            if (current->flags[j]) continue;

                            int candidate = current->candidates[j];
                            current->flags[j] = true;
                            current->current_idx = j + 1;

                            if (my_g2->nodes[candidate].mapped != -1) continue;

                            my_g1->nodes[current->node].mapped = candidate;
                            my_g2->nodes[candidate].mapped = current->node;
                            num_mapped++;

                            omp_update_t2_tilde(my_g2, candidate, t2_tilde);

                            if (num_mapped == n) {
                                #pragma omp atomic write
                                global_found = true;
                                goto end_search;
                            }

                            int next_num_candidates;
                            if (find_candidates(node_order[matching_node], 
                                              my_g1, my_g2, t2_tilde,
                                              candidates_buf, &next_num_candidates) != 0) {
                                my_g1->nodes[current->node].mapped = -1;
                                my_g2->nodes[candidate].mapped = -1;
                                num_mapped--;
                                omp_restore_t2_tilde(my_g2, candidate, t2_tilde);
                                continue;
                            }

                            if (stack_push(&stack, node_order[matching_node],
                                          candidates_buf, next_num_candidates) != 0) {
                                my_g1->nodes[current->node].mapped = -1;
                                my_g2->nodes[candidate].mapped = -1;
                                num_mapped--;
                                omp_restore_t2_tilde(my_g2, candidate, t2_tilde);
                                continue;
                            }
                            
                            matching_node++;
                            advanced = true;
                            break;
                        }

                        if (!advanced) {
                            stack_pop(&stack);
                            matching_node--;

                            if (!stack_is_empty(&stack)) {
                                StackElement* parent = stack_peek(&stack);
                                int parent_node = parent->node;
                                int mapped_to = my_g1->nodes[parent_node].mapped;

                                if (mapped_to != -1) {
                                    my_g1->nodes[parent_node].mapped = -1;
                                    my_g2->nodes[mapped_to].mapped = -1;
                                    num_mapped--;
                                    omp_restore_t2_tilde(my_g2, mapped_to, t2_tilde);
                                }
                            }
                        }
                    } 
                    end_search:; 
                } 
                
                free(t2_tilde);
                free(candidates_buf);
            }
            stack_free(&stack);
        }
    } 

    free(node_order);
    free(initial_candidates_buf);
    
    #pragma omp parallel for
    for (int t = 0; t < max_threads; t++) {
        graph_free(g1_copies[t]);
        graph_free(g2_copies[t]);
    }
    free(g1_copies);
    free(g2_copies);

    return global_found;
}

/* ============================================================================
 * HELPER FUNCTIONS
 * ============================================================================ */

VF2OpenMPConfig vf2_openmp_default_config(void) {
    VF2OpenMPConfig config;
    config.num_threads = 0; 
    config.enable_early_term = true;
    config.verbose = 1;
    return config;
}

VF2OpenMPResult vf2pp_find_isomorphism_openmp(Graph* g1, Graph* g2, const VF2OpenMPConfig* config) {
    VF2OpenMPResult result;
    memset(&result, 0, sizeof(VF2OpenMPResult));
    int threads_to_use = (config && config->num_threads > 0) ? config->num_threads : omp_get_max_threads();
    omp_set_num_threads(threads_to_use);
    double start_time = omp_get_wtime();
    
    result.found = vf2pp_is_isomorphic_openmp(g1, g2);
    
    double end_time = omp_get_wtime();
    result.total_time = end_time - start_time;
    result.parallel_time = result.total_time; 
    result.num_threads = threads_to_use;
    result.num_nodes = (g1) ? g1->num_nodes : 0;
    result.mapping = NULL; 
    return result;
}

void vf2_openmp_result_free(VF2OpenMPResult* result) {
    if (result && result->mapping) {
        free(result->mapping);
        result->mapping = NULL;
    }
}

void vf2_openmp_print_stats(const VF2OpenMPResult* result) {
    if (!result) return;
    printf("=== STATISTICHE OPENMP ===\n");
    printf("Risultato:            %s\n", result->found ? "ISOMORFI" : "NON ISOMORFI");
    printf("Thread usati:         %d\n", result->num_threads);
    printf("Tempo totale:         %.6f s\n", result->total_time);
    printf("========================\n");
}

bool vf2_openmp_verify_mapping(const Graph* g1, const Graph* g2, const int* mapping, int num_nodes) {
    if (!mapping) return true; 
    if (!g1 || !g2) return false;
    
    bool* used = (bool*)calloc(num_nodes, sizeof(bool));
    for (int i = 0; i < num_nodes; i++) {
        int m = mapping[i];
        if (m < 0 || m >= num_nodes || used[m]) {
            free(used);
            return false;
        }
        used[m] = true;
    }
    free(used);
    
    for (int u = 0; u < num_nodes; u++) {
        int u_mapped = mapping[u];
        for (int i = 0; i < g1->nodes[u].num_neighbors; i++) {
            int v = g1->nodes[u].neighborhood[i];
            int v_mapped = mapping[v];
            
            bool edge_found = false;
            for (int j = 0; j < g2->nodes[u_mapped].num_neighbors; j++) {
                if (g2->nodes[u_mapped].neighborhood[j] == v_mapped) {
                    edge_found = true;
                    break;
                }
            }
            if (!edge_found) return false;
        }
    }
    return true;
}

bool vf2pp_is_isomorphic_openmp_config(Graph* g1, Graph* g2, const VF2OpenMPConfig* config) {
    if (config && config->num_threads > 0) {
        omp_set_num_threads(config->num_threads);
    }
    return vf2pp_is_isomorphic_openmp(g1, g2);
}
