/*
 * VF2++ Graph Isomorphism - MPI Parallel Implementation (OPTIMIZED ZERO-MALLOC)
 * * OTTIMIZZAZIONI:
 * 1. Zero-Malloc: Allocazione strutture (Stack, T2, Buffer) una volta per processo.
 * 2. Reuse: Riutilizzo della memoria per ogni candidato assegnato.
 * 3. Fast Reset: Uso di stack_clear e reset mapping invece di free/malloc.
 */

#include "vf2pp_mpi.h"
#include "stack.h"
#include "node_ordering.h"
#include "find_candidates.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

/* ============================================================================
 * FUNZIONI HELPER INTERNE
 * ============================================================================ */

static void mpi_update_t2_tilde(const Graph* g2, int mapped_node, bool* t2_tilde) {
    t2_tilde[mapped_node] = false;
    for (int i = 0; i < g2->nodes[mapped_node].num_neighbors; i++) {
        int nbr = g2->nodes[mapped_node].neighborhood[i];
        t2_tilde[nbr] = false;
    }
}

static void mpi_restore_t2_tilde(const Graph* g2, int unmapped_node, bool* t2_tilde) {
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
 * ALGORITMO VF2++ PARALLELO CORE
 * ============================================================================ */

/**
 * Esplora un sottoalbero riutilizzando le strutture pre-allocate.
 * NON esegue malloc/free internamente.
 */
static bool explore_subtree_optimized(Graph* g1, Graph* g2, 
                                      const int* node_order, int first_candidate,
                                      int n, 
                                      volatile bool* should_terminate,
                                      Stack* stack, bool* t2_tilde, int* candidates_buf) {
    
    /* 1. RESET RAPIDO DELLE STRUTTURE */
    stack_clear(stack); // Assicurati che stack_clear esista in stack.c
    for(int i = 0; i < n; i++) t2_tilde[i] = true;

    /* 2. INIZIALIZZAZIONE STACK */
    int single_candidate[1] = { first_candidate };
    if (stack_push(stack, node_order[0], single_candidate, 1) != 0) {
        return false; 
    }
    
    int matching_node = 1;
    int num_mapped = 0;
    
    /* 3. LOOP DFS */
    int check_counter = 0;
    while (!stack_is_empty(stack)) {
        
        /* Check early termination ogni 64 iterazioni per ridurre overhead */
        if ((++check_counter & 0x3F) == 0) {
            if (*should_terminate) return false;
        }

        StackElement* current = stack_peek(stack);
        bool advanced = false;
        
        for (int i = current->current_idx; i < current->num_candidates; i++) {
            if (current->flags[i]) continue;
            
            int candidate = current->candidates[i];
            current->flags[i] = true;
            current->current_idx = i + 1;
            
            if (g2->nodes[candidate].mapped != -1) continue;
            
            /* Applica Mapping */
            g1->nodes[current->node].mapped = candidate;
            g2->nodes[candidate].mapped = current->node;
            num_mapped++;
            
            mpi_update_t2_tilde(g2, candidate, t2_tilde);
            
            if (num_mapped == n) {
                return true; /* TROVATO! */
            }
            
            int next_num_candidates;
            /* Usiamo il buffer pre-allocato candidates_buf */
            if (find_candidates(node_order[matching_node], g1, g2, t2_tilde,
                               candidates_buf, &next_num_candidates) != 0) {
                /* Backtrack Immediato */
                g1->nodes[current->node].mapped = -1;
                g2->nodes[candidate].mapped = -1;
                num_mapped--;
                mpi_restore_t2_tilde(g2, candidate, t2_tilde);
                continue;
            }
            
            if (stack_push(stack, node_order[matching_node],
                          candidates_buf, next_num_candidates) != 0) {
                /* Backtrack Immediato (errore mem stack) */
                g1->nodes[current->node].mapped = -1;
                g2->nodes[candidate].mapped = -1;
                num_mapped--;
                mpi_restore_t2_tilde(g2, candidate, t2_tilde);
                continue;
            }
            
            matching_node++;
            advanced = true;
            break;
        }
        
        if (!advanced) {
            stack_pop(stack);
            matching_node--;
            
            if (!stack_is_empty(stack)) {
                StackElement* parent = stack_peek(stack);
                int parent_node = parent->node;
                int mapped_to = g1->nodes[parent_node].mapped;
                
                if (mapped_to != -1) {
                    g1->nodes[parent_node].mapped = -1;
                    g2->nodes[mapped_to].mapped = -1;
                    num_mapped--;
                    mpi_restore_t2_tilde(g2, mapped_to, t2_tilde);
                }
            }
        }
    }
    
    return false;
}

/* ============================================================================
 * FUNZIONE PRINCIPALE MPI
 * ============================================================================ */

bool vf2pp_is_isomorphic_mpi(Graph* g1, Graph* g2, MPI_Comm comm) {
    int rank, size;
    MPI_Comm_rank(comm, &rank);
    MPI_Comm_size(comm, &size);
    
    /* Check Preliminari */
    if (g1 == NULL || g2 == NULL) return false;
    if (g1->num_nodes == 0 && g2->num_nodes == 0) return true;
    if (g1->num_nodes != g2->num_nodes || g1->num_edges != g2->num_edges) return false;
    
    int n = g1->num_nodes;
    
    /* Reset Mappings */
    graph_reset_mapping(g1);
    graph_reset_mapping(g2);
    
    int* node_order = (int*)malloc(n * sizeof(int));
    if (!node_order || compute_matching_order(g1, node_order) != 0) {
        free(node_order);
        return false;
    }
    
    /* ===================================================================
     * FASE 1: Rank 0 calcola tutti i candidati iniziali
     * =================================================================== */
    int* all_candidates = NULL;
    int total_candidates = 0;
    
    if (rank == 0) {
        bool* t2_tilde_init = (bool*)malloc(n * sizeof(bool));
        for (int i = 0; i < n; i++) t2_tilde_init[i] = true;
        
        all_candidates = (int*)malloc(n * sizeof(int));
        find_candidates(node_order[0], g1, g2, t2_tilde_init,
                       all_candidates, &total_candidates);
        free(t2_tilde_init);
    }
    
    /* Broadcast Candidati */
    MPI_Bcast(&total_candidates, 1, MPI_INT, 0, comm);
    
    if (total_candidates == 0) {
        if (rank == 0) free(all_candidates);
        free(node_order);
        return false;
    }
    
    if (rank != 0) {
        all_candidates = (int*)malloc(total_candidates * sizeof(int));
    }
    MPI_Bcast(all_candidates, total_candidates, MPI_INT, 0, comm);
    
    /* ===================================================================
     * FASE 2: Distribuzione (Static Round-Robin)
     * =================================================================== */
    int my_count = 0;
    for (int i = rank; i < total_candidates; i += size) my_count++;
    
    int* my_candidates = NULL;
    if (my_count > 0) {
        my_candidates = (int*)malloc(my_count * sizeof(int));
        int idx = 0;
        for (int i = rank; i < total_candidates; i += size) {
            my_candidates[idx++] = all_candidates[i];
        }
    }
    free(all_candidates);
    
    /* ===================================================================
     * FASE 3: ESPLORAZIONE "ZERO-MALLOC"
     * Allocazione risorse UNA VOLTA per processo
     * =================================================================== */
    
    bool local_found = false;
    volatile bool should_terminate = false;
    
    /* 1. Alloca Stack */
    Stack stack;
    if (stack_init(&stack) != 0) {
        free(my_candidates);
        free(node_order);
        return false;
    }
    
    /* 2. Alloca Buffer Riutilizzabili */
    bool* t2_tilde = (bool*)malloc(n * sizeof(bool));
    int* candidates_buf = (int*)malloc(n * sizeof(int));
    
    if (t2_tilde && candidates_buf) {
        /* Loop sui candidati assegnati a questo processo */
        for (int c = 0; c < my_count && !local_found && !should_terminate; c++) {
            
            /* RESET MAPPE (Fondamentale in MPI perché riusiamo g1/g2) */
            graph_reset_mapping(g1);
            graph_reset_mapping(g2);
            
            /* Chiamata ottimizzata senza malloc */
            local_found = explore_subtree_optimized(g1, g2, node_order, my_candidates[c],
                                                    n, &should_terminate,
                                                    &stack, t2_tilde, candidates_buf);
            
            /* Check messaggi MPI (Early Termination) */
            if (!local_found) {
                int flag;
                MPI_Iprobe(MPI_ANY_SOURCE, VF2_TAG_FOUND, comm, &flag, MPI_STATUS_IGNORE);
                if (flag) {
                    should_terminate = true;
                }
            }
        }
    }
    
    /* Cleanup Risorse Locali */
    stack_free(&stack);
    if(t2_tilde) free(t2_tilde);
    if(candidates_buf) free(candidates_buf);
    
    /* ===================================================================
     * FASE 4: Comunicazione & Riduzione
     * =================================================================== */
    
    /* Se ho trovato, avviso tutti */
    if (local_found) {
        int msg = 1;
        for (int i = 0; i < size; i++) {
            if (i != rank) {
                // Invio non bloccante o bloccante veloce (buffered)
                MPI_Send(&msg, 1, MPI_INT, i, VF2_TAG_FOUND, comm);
            }
        }
    }
    
    /* Svuota eventuali messaggi in arrivo per evitare deadlock futuri */
    int flag;
    MPI_Status status;
    while (1) {
        MPI_Iprobe(MPI_ANY_SOURCE, VF2_TAG_FOUND, comm, &flag, &status);
        if (!flag) break;
        int dummy;
        MPI_Recv(&dummy, 1, MPI_INT, status.MPI_SOURCE, VF2_TAG_FOUND, comm, MPI_STATUS_IGNORE);
    }
    
    int global_result = 0;
    int local_result = local_found ? 1 : 0;
    MPI_Allreduce(&local_result, &global_result, 1, MPI_INT, MPI_MAX, comm);
    
    if (my_candidates) free(my_candidates);
    free(node_order);
    
    return (global_result > 0);
}

/* ============================================================================
 * WRAPPER CON METRICHE (Usato dal Main)
 * ============================================================================ */

VF2MpiResult vf2pp_find_isomorphism_mpi(Graph* g1, Graph* g2, MPI_Comm comm) {
    VF2MpiResult result;
    memset(&result, 0, sizeof(VF2MpiResult));
    result.finder_rank = -1;
    
    int rank;
    MPI_Comm_rank(comm, &rank);
    
    double start_time = MPI_Wtime();
    
    /* Chiama la funzione ottimizzata */
    result.found = vf2pp_is_isomorphic_mpi(g1, g2, comm);
    
    double end_time = MPI_Wtime();
    result.total_time = end_time - start_time;
    result.comm_time = 0; // Semplificato per questa versione ottimizzata
    result.compute_time = result.total_time; 
    
    if (result.found) {
        /* Identifica chi ha trovato */
        int local_found = result.found ? rank : 999999;
        int global_finder;
        MPI_Allreduce(&local_found, &global_finder, 1, MPI_INT, MPI_MIN, comm);
        if (global_finder != 999999) result.finder_rank = global_finder;
        else result.finder_rank = -1;

        /* Estrai mapping (solo se locale) */
        if (rank == result.finder_rank) {
            result.mapping = (int*)malloc(g1->num_nodes * sizeof(int));
            if (result.mapping) {
                for(int i=0; i<g1->num_nodes; i++) result.mapping[i] = g1->nodes[i].mapped;
            }
        }
    }
    
    return result;
}

void vf2_mpi_result_free(VF2MpiResult* result) {
    if (result && result->mapping) {
        free(result->mapping);
        result->mapping = NULL;
    }
}

void vf2_mpi_print_stats(const VF2MpiResult* result, MPI_Comm comm) {
    int rank, size;
    MPI_Comm_rank(comm, &rank);
    MPI_Comm_size(comm, &size);
    
    double local_time = result->total_time;
    double max_time = 0, min_time = 0, avg_time = 0;
    
    MPI_Reduce(&local_time, &max_time, 1, MPI_DOUBLE, MPI_MAX, 0, comm);
    MPI_Reduce(&local_time, &min_time, 1, MPI_DOUBLE, MPI_MIN, 0, comm);
    MPI_Reduce(&local_time, &avg_time, 1, MPI_DOUBLE, MPI_SUM, 0, comm);
    
    if (rank == 0) {
        printf("\n=== STATISTICHE MPI (Zero-Malloc) ===\n");
        printf("Processi:      %d\n", size);
        printf("Risultato:     %s\n", result->found ? "ISOMORFI" : "NON ISOMORFI");
        if (result->found) printf("Finder Rank:   %d\n", result->finder_rank);
        printf("Time Max:      %.6f s\n", max_time);
        printf("Time Min:      %.6f s\n", min_time);
        printf("Time Avg:      %.6f s\n", avg_time / size);
        printf("==============================\n");
    }
}