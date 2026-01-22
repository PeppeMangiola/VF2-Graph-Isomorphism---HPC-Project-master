/*
 * VF2++ Graph Isomorphism - MPI Parallel Implementation
 * STRATEGIA: Dynamic Master-Worker con Early Termination
 * * NOTE IMPLEMENTATIVE:
 * - Rispetta le dichiarazioni di vf2pp_mpi.h
 * - Usa TAG interni per la gestione del Dynamic Load Balancing
 */

#include "vf2pp_mpi.h"
#include "stack.h"
#include "node_ordering.h"
#include "find_candidates.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>


/* Tag INTERNI per la comunicazione Master-Worker 
 * (Questi sostituiscono la logica statica descritta nei vecchi commenti)
 */
#define TAG_REQ     10  // Worker richiede lavoro
#define TAG_TASK    11  // Master invia candidato (lavoro)
#define TAG_STOP    12  // Master dice che non c'è più lavoro
#define TAG_RESULT  13  // Worker invia risultato positivo
#define TAG_KILL    14  // Master ordina stop immediato (trovato da altri)

/* ============================================================================
 * FUNZIONI HELPER (Logica VF2++ interna)
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
 * EXPLORE SUBTREE (Worker Core Logic)
 * ============================================================================ */

static bool explore_subtree_optimized(Graph* g1, Graph* g2, 
                                      const int* node_order, int first_candidate,
                                      int n, 
                                      MPI_Comm comm,
                                      Stack* stack, bool* t2_tilde, int* candidates_buf) {
    
    /* Reset strutture senza free/malloc */
    stack_clear(stack);
    for(int i = 0; i < n; i++) t2_tilde[i] = true;

    /* Setup iniziale */
    int single_candidate[1] = { first_candidate };
    if (stack_push(stack, node_order[0], single_candidate, 1) != 0) return false;
    
    int matching_node = 1;
    int num_mapped = 0;
    int check_counter = 0;

    while (!stack_is_empty(stack)) {
        
        /* CHECK TERMINAZIONE ASINCRONO
         * Ogni 64 iterazioni controlliamo se il Master ci ha mandato un TAG_KILL 
         */
        if ((++check_counter & 0x3F) == 0) {
            int flag = 0;
            MPI_Iprobe(0, TAG_KILL, comm, &flag, MPI_STATUS_IGNORE);
            if (flag) return false; // Abort immediato, qualcun altro ha trovato
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
                return true; /* TROVATO ISOMORFISMO */
            }
            
            int next_num_candidates;
            if (find_candidates(node_order[matching_node], g1, g2, t2_tilde,
                               candidates_buf, &next_num_candidates) != 0) {
                g1->nodes[current->node].mapped = -1;
                g2->nodes[candidate].mapped = -1;
                num_mapped--;
                mpi_restore_t2_tilde(g2, candidate, t2_tilde);
                continue;
            }
            
            if (stack_push(stack, node_order[matching_node],
                          candidates_buf, next_num_candidates) != 0) {
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
 * FUNZIONE PRINCIPALE: vf2pp_find_isomorphism_mpi
 * Implementa la logica Master-Worker
 * ============================================================================ */

VF2MpiResult vf2pp_find_isomorphism_mpi(Graph* g1, Graph* g2, MPI_Comm comm) {
    VF2MpiResult result;
    // Inizializza struct a zero
    memset(&result, 0, sizeof(VF2MpiResult));
    result.finder_rank = -1;
    result.found = false;
    result.mapping = NULL;
    
    int rank, size;
    MPI_Comm_rank(comm, &rank);
    MPI_Comm_size(comm, &size);
    
    double start_time = MPI_Wtime();

    /* Quick check su dimensioni */
    if (g1->num_nodes != g2->num_nodes || g1->num_edges != g2->num_edges) {
        result.total_time = MPI_Wtime() - start_time;
        return result;
    }
    
    int n = g1->num_nodes;
    graph_reset_mapping(g1);
    graph_reset_mapping(g2);
    
    int* node_order = (int*)malloc(n * sizeof(int));
    if (compute_matching_order(g1, node_order) != 0) {
        free(node_order);
        return result;
    }

    /* ------------------------------------------------------------------
     * CASO 1: UN SOLO PROCESSO (Sequenziale)
     * ------------------------------------------------------------------ */
    if (size == 1) {
        bool* t2 = (bool*)malloc(n * sizeof(bool));
        int* cand_buf = (int*)malloc(n * sizeof(int));
        Stack stack;
        stack_init(&stack);
        
        for(int i=0; i<n; i++) t2[i] = true;
        int* roots = (int*)malloc(n * sizeof(int));
        int num_roots = 0;
        find_candidates(node_order[0], g1, g2, t2, roots, &num_roots);
        
        for(int i=0; i<num_roots; i++) {
            graph_reset_mapping(g1);
            graph_reset_mapping(g2);
            if(explore_subtree_optimized(g1, g2, node_order, roots[i], n, comm, &stack, t2, cand_buf)) {
                result.found = true;
                result.finder_rank = 0;
                result.mapping = (int*)malloc(n * sizeof(int));
                for(int k=0; k<n; k++) result.mapping[k] = g1->nodes[k].mapped;
                break;
            }
        }
        
        free(roots); free(t2); free(cand_buf); stack_free(&stack);
        free(node_order);
        result.total_time = MPI_Wtime() - start_time;
        return result;
    }

    /* ------------------------------------------------------------------
     * CASO 2: PARALLELO (Master-Worker)
     * ------------------------------------------------------------------ */
    
    // --- RANK 0: MASTER ---
    if (rank == 0) {
        bool* t2_temp = (bool*)malloc(n * sizeof(bool));
        for(int i=0; i<n; i++) t2_temp[i] = true;
        
        int* all_candidates = (int*)malloc(n * sizeof(int));
        int total_candidates = 0;
        find_candidates(node_order[0], g1, g2, t2_temp, all_candidates, &total_candidates);
        free(t2_temp);
        
        int current_idx = 0;
        int active_workers = size - 1; 
        bool solution_found = false;
        
        while (active_workers > 0) {
            MPI_Status status;
            MPI_Probe(MPI_ANY_SOURCE, MPI_ANY_TAG, comm, &status);
            
            int source = status.MPI_SOURCE;
            int tag = status.MPI_TAG;
            
            if (tag == TAG_REQ) {
                int dummy;
                MPI_Recv(&dummy, 0, MPI_INT, source, TAG_REQ, comm, MPI_STATUS_IGNORE);
                
                if (solution_found || current_idx >= total_candidates) {
                    // Stop worker
                    int stop_sig = 0;
                    MPI_Send(&stop_sig, 0, MPI_INT, source, TAG_STOP, comm);
                    active_workers--;
                } else {
                    // Invia lavoro
                    int task = all_candidates[current_idx++];
                    MPI_Send(&task, 1, MPI_INT, source, TAG_TASK, comm);
                }
            }
            else if (tag == TAG_RESULT) {
                solution_found = true;
                result.found = true;
                result.finder_rank = source;
                
                // Ricevi mapping
                result.mapping = (int*)malloc(n * sizeof(int));
                MPI_Recv(result.mapping, n, MPI_INT, source, TAG_RESULT, comm, MPI_STATUS_IGNORE);
                
                // Invia KILL a tutti gli altri worker
                for (int w = 1; w < size; w++) {
                    if (w != source) {
                         int kill_sig = 1;
                         MPI_Request req;
                         MPI_Isend(&kill_sig, 1, MPI_INT, w, TAG_KILL, comm, &req);
                    }
                }
                active_workers--; 
            }
        }
        free(all_candidates);
    }
    
    // --- RANK > 0: WORKERS ---
    else {
        Stack stack;
        stack_init(&stack);
        bool* t2_tilde = (bool*)malloc(n * sizeof(bool));
        int* candidates_buf = (int*)malloc(n * sizeof(int));
        
        while (true) {
            MPI_Send(NULL, 0, MPI_INT, 0, TAG_REQ, comm);
            
            MPI_Status status;
            int root_candidate;
            MPI_Recv(&root_candidate, 1, MPI_INT, 0, MPI_ANY_TAG, comm, &status);
            
            if (status.MPI_TAG == TAG_STOP || status.MPI_TAG == TAG_KILL) {
                break; 
            }
            else if (status.MPI_TAG == TAG_TASK) {
                graph_reset_mapping(g1);
                graph_reset_mapping(g2);
                
                bool found_local = explore_subtree_optimized(g1, g2, node_order, root_candidate,
                                                             n, comm,
                                                             &stack, t2_tilde, candidates_buf);
                if (found_local) {
                    int* mapping_flat = (int*)malloc(n * sizeof(int));
                    for(int i=0; i<n; i++) mapping_flat[i] = g1->nodes[i].mapped;
                    MPI_Send(mapping_flat, n, MPI_INT, 0, TAG_RESULT, comm);
                    free(mapping_flat);
                    break;
                }
            }
        }
        stack_free(&stack);
        free(t2_tilde);
        free(candidates_buf);
    }

    free(node_order);
    
    // Sincronizzazione per timing corretto
    MPI_Barrier(comm); 
    
    // Broadcast del risultato a tutti i processi (così il main su tutti i rank sa com'è andata)
    MPI_Bcast(&result.found, 1, MPI_C_BOOL, 0, comm);
    MPI_Bcast(&result.finder_rank, 1, MPI_INT, 0, comm);

    result.total_time = MPI_Wtime() - start_time;
    result.compute_time = result.total_time; // Semplificazione

    return result;
}

/* ============================================================================
 * WRAPPER FUNCTION (Richiesta da vf2pp_mpi.h)
 * ============================================================================ */

bool vf2pp_is_isomorphic_mpi(Graph* g1, Graph* g2, MPI_Comm comm) {
    VF2MpiResult res = vf2pp_find_isomorphism_mpi(g1, g2, comm);
    bool found = res.found;
    vf2_mpi_result_free(&res);
    return found;
}

/* ============================================================================
 * UTILITY FUNCTIONS (Richieste da vf2pp_mpi.h)
 * ============================================================================ */

void vf2_mpi_result_free(VF2MpiResult* result) {
    if (result && result->mapping) {
        free(result->mapping);
        result->mapping = NULL;
    }
}

void vf2_mpi_print_stats(const VF2MpiResult* result, MPI_Comm comm) {
    int rank;
    MPI_Comm_rank(comm, &rank);
    // Stampa solo il Master per evitare output duplicato
    if (rank == 0) {
        printf("\n=== STATISTICHE MPI (Dynamic Master-Worker) ===\n");
        printf("Risultato:     %s\n", result->found ? "ISOMORFI" : "NON ISOMORFI");
        if(result->found) {
            printf("Finder Rank:   %d\n", result->finder_rank);
        }
        printf("Total Time:    %.6f s\n", result->total_time);
        printf("=============================================\n");
    }
}