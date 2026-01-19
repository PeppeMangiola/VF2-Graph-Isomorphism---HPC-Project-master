/*
 * VF2++ Graph Isomorphism - MPI Parallel Implementation
 * HPC Project
 * 
 * Implementazione parallela dell'algoritmo VF2++ usando MPI.
 * 
 * STRATEGIA DI PARALLELIZZAZIONE:
 * ================================
 * L'algoritmo VF2++ è basato su backtracking. La parallelizzazione avviene
 * dividendo lo spazio di ricerca al PRIMO LIVELLO dell'albero:
 * 
 * 1. Rank 0 calcola i candidati per il primo nodo dell'ordine di matching
 * 2. I candidati vengono distribuiti staticamente tra i processi (round-robin)
 * 3. Ogni processo esplora INDIPENDENTEMENTE i sottoalberi dei suoi candidati
 * 4. Comunicazione asincrona per early termination
 * 5. Riduzione finale per determinare il risultato globale
 * 
 * Esempio con 4 processi e 8 candidati iniziali:
 *   Rank 0: candidati [0, 4]
 *   Rank 1: candidati [1, 5]
 *   Rank 2: candidati [2, 6]
 *   Rank 3: candidati [3, 7]
 */

#include "vf2pp_mpi.h"
#include "stack.h"
#include "node_ordering.h"
#include "find_candidates.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

/* ============================================================================
 * FUNZIONI HELPER INTERNE (copiate da vf2pp.c per indipendenza)
 * ============================================================================ */

/**
 * Aggiorna T2_tilde dopo aver mappato un nodo
 */
static void mpi_update_t2_tilde(const Graph* g2, int mapped_node, bool* t2_tilde) {
    t2_tilde[mapped_node] = false;
    
    for (int i = 0; i < g2->nodes[mapped_node].num_neighbors; i++) {
        int nbr = g2->nodes[mapped_node].neighborhood[i];
        t2_tilde[nbr] = false;
    }
}

/**
 * Ripristina T2_tilde dopo backtrack
 */
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
 * ALGORITMO VF2++ PARALLELO
 * ============================================================================ */

/**
 * Esplora un sottoalbero di ricerca partendo da un candidato specifico
 * per il primo nodo dell'ordine di matching.
 * 
 * @param g1 Grafo pattern
 * @param g2 Grafo target
 * @param node_order Ordine di matching
 * @param first_candidate Candidato iniziale per node_order[0]
 * @param n Numero di nodi
 * @param rank Rank MPI (per logging)
 * @param should_terminate Puntatore a flag per early termination
 * @param comm Communicator MPI
 * @return true se trovato isomorfismo, false altrimenti
 */
static bool explore_subtree(Graph* g1, Graph* g2, 
                           const int* node_order, int first_candidate,
                           int n, int rank,
                           volatile bool* should_terminate,
                           MPI_Comm comm) {
    (void)rank;  /* Per eventuali log di debug */
    (void)comm;
    
    /* Alloca strutture locali */
    bool* t2_tilde = (bool*)malloc(n * sizeof(bool));
    if (t2_tilde == NULL) return false;
    
    for (int i = 0; i < n; i++) {
        t2_tilde[i] = true;
    }
    
    Stack stack;
    if (stack_init(&stack) != 0) {
        free(t2_tilde);
        return false;
    }
    
    int* candidates_buf = (int*)malloc(n * sizeof(int));
    if (candidates_buf == NULL) {
        stack_free(&stack);
        free(t2_tilde);
        return false;
    }
    
    /* Inizializza con il primo candidato assegnato */
    /* Push di un elemento "finto" con un solo candidato: first_candidate */
    int single_candidate[1] = { first_candidate };
    if (stack_push(&stack, node_order[0], single_candidate, 1) != 0) {
        free(candidates_buf);
        stack_free(&stack);
        free(t2_tilde);
        return false;
    }
    
    int matching_node = 1;  /* Prossimo nodo da matchare (partiamo da 1, il primo è già fissato) */
    int num_mapped = 0;
    bool found = false;
    
    /* Algoritmo di backtracking */
    while (!stack_is_empty(&stack) && !(*should_terminate)) {
        StackElement* current = stack_peek(&stack);
        bool advanced = false;
        
        /* Cerca un candidato non ancora provato */
        for (int i = current->current_idx; i < current->num_candidates; i++) {
            if (current->flags[i]) {
                continue;
            }
            
            int candidate = current->candidates[i];
            
            current->flags[i] = true;
            current->current_idx = i + 1;
            
            /* Verifica disponibilità */
            if (g2->nodes[candidate].mapped != -1) {
                continue;
            }
            
            /* Applica mapping */
            g1->nodes[current->node].mapped = candidate;
            g2->nodes[candidate].mapped = current->node;
            num_mapped++;
            
            mpi_update_t2_tilde(g2, candidate, t2_tilde);
            
            /* Controllo completamento */
            if (num_mapped == n) {
                found = true;
                goto cleanup;
            }
            
            /* Trova candidati per il prossimo nodo */
            int next_num_candidates;
            if (find_candidates(node_order[matching_node], g1, g2, t2_tilde,
                               candidates_buf, &next_num_candidates) != 0) {
                /* Errore, backtrack */
                g1->nodes[current->node].mapped = -1;
                g2->nodes[candidate].mapped = -1;
                num_mapped--;
                mpi_restore_t2_tilde(g2, candidate, t2_tilde);
                continue;
            }
            
            /* Push prossimo nodo */
            if (stack_push(&stack, node_order[matching_node],
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
        
        /* Backtrack se necessario */
        if (!advanced) {
            stack_pop(&stack);
            matching_node--;
            
            if (!stack_is_empty(&stack)) {
                StackElement* parent = stack_peek(&stack);
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
        
        /* Check periodico per early termination (ogni ~100 iterazioni) */
        /* Il flag viene aggiornato dal loop principale */
    }
    
cleanup:
    free(candidates_buf);
    stack_free(&stack);
    free(t2_tilde);
    
    return found;
}

/* ============================================================================
 * FUNZIONE PRINCIPALE MPI
 * ============================================================================ */

bool vf2pp_is_isomorphic_mpi(Graph* g1, Graph* g2, MPI_Comm comm) {
    int rank, size;
    MPI_Comm_rank(comm, &rank);
    MPI_Comm_size(comm, &size);
    
    /* Controlli preliminari (tutti i rank devono fare lo stesso check) */
    if (g1 == NULL || g2 == NULL) {
        return false;
    }
    
    if (g1->num_nodes == 0 && g2->num_nodes == 0) {
        return true;
    }
    
    if (g1->num_nodes != g2->num_nodes || g1->num_edges != g2->num_edges) {
        return false;
    }
    
    int n = g1->num_nodes;
    
    /* Reset mapping su tutti i rank */
    graph_reset_mapping(g1);
    graph_reset_mapping(g2);
    
    /* Calcola ordine di matching (tutti i rank) */
    int* node_order = (int*)malloc(n * sizeof(int));
    if (node_order == NULL) {
        return false;
    }
    
    if (compute_matching_order(g1, node_order) != 0) {
        free(node_order);
        return false;
    }
    
    /* ===================================================================
     * FASE 1: Rank 0 trova i candidati per il primo nodo
     * =================================================================== */
    
    int* all_candidates = NULL;
    int total_candidates = 0;
    
    if (rank == 0) {
        bool* t2_tilde_init = (bool*)malloc(n * sizeof(bool));
        if (t2_tilde_init == NULL) {
            free(node_order);
            return false;
        }
        for (int i = 0; i < n; i++) {
            t2_tilde_init[i] = true;
        }
        
        all_candidates = (int*)malloc(n * sizeof(int));
        if (all_candidates == NULL) {
            free(t2_tilde_init);
            free(node_order);
            return false;
        }
        
        if (find_candidates(node_order[0], g1, g2, t2_tilde_init,
                           all_candidates, &total_candidates) != 0) {
            free(all_candidates);
            free(t2_tilde_init);
            free(node_order);
            return false;
        }
        
        free(t2_tilde_init);
    }
    
    /* ===================================================================
     * FASE 2: Broadcast numero di candidati e candidati stessi
     * =================================================================== */
    
    MPI_Bcast(&total_candidates, 1, MPI_INT, 0, comm);
    
    if (total_candidates == 0) {
        if (rank == 0 && all_candidates != NULL) {
            free(all_candidates);
        }
        free(node_order);
        return false;
    }
    
    if (rank != 0) {
        all_candidates = (int*)malloc(total_candidates * sizeof(int));
        if (all_candidates == NULL) {
            free(node_order);
            return false;
        }
    }
    
    MPI_Bcast(all_candidates, total_candidates, MPI_INT, 0, comm);
    
    /* ===================================================================
     * FASE 3: Distribuzione statica dei candidati
     * =================================================================== */
    
    /* Calcola quali candidati spettano a questo rank (round-robin) */
    int my_count = 0;
    for (int i = rank; i < total_candidates; i += size) {
        my_count++;
    }
    
    int* my_candidates = NULL;
    if (my_count > 0) {
        my_candidates = (int*)malloc(my_count * sizeof(int));
        if (my_candidates == NULL) {
            free(all_candidates);
            free(node_order);
            return false;
        }
        
        int idx = 0;
        for (int i = rank; i < total_candidates; i += size) {
            my_candidates[idx++] = all_candidates[i];
        }
    }
    
    free(all_candidates);  /* Non più necessario */
    
    /* ===================================================================
     * FASE 4: Esplorazione parallela dei sottoalberi
     * =================================================================== */
    
    bool local_found = false;
    volatile bool should_terminate = false;
    
    /* Esplora ogni candidato assegnato */
    for (int c = 0; c < my_count && !local_found && !should_terminate; c++) {
        /* Reset mapping prima di ogni esplorazione */
        graph_reset_mapping(g1);
        graph_reset_mapping(g2);
        
        local_found = explore_subtree(g1, g2, node_order, my_candidates[c],
                                      n, rank, &should_terminate, comm);
        
        /* Check se qualcun altro ha trovato (non bloccante) */
        if (!local_found) {
            int flag;
            MPI_Status status;
            MPI_Iprobe(MPI_ANY_SOURCE, VF2_TAG_FOUND, comm, &flag, &status);
            if (flag) {
                should_terminate = true;
                /* Ricevi il messaggio per pulire la coda */
                int dummy;
                MPI_Recv(&dummy, 1, MPI_INT, status.MPI_SOURCE, VF2_TAG_FOUND, 
                         comm, MPI_STATUS_IGNORE);
            }
        }
    }
    
    /* ===================================================================
     * FASE 5: Comunicazione del risultato
     * =================================================================== */
    
    /* Se abbiamo trovato, notifica tutti gli altri */
    if (local_found) {
        int msg = 1;
        for (int i = 0; i < size; i++) {
            if (i != rank) {
                MPI_Send(&msg, 1, MPI_INT, i, VF2_TAG_FOUND, comm);
            }
        }
    }
    
    /* Riduzione finale per determinare risultato globale */
    int local_result = local_found ? 1 : 0;
    int global_result = 0;
    
    MPI_Allreduce(&local_result, &global_result, 1, MPI_INT, MPI_MAX, comm);
    
    /* Cleanup */
    if (my_candidates != NULL) {
        free(my_candidates);
    }
    free(node_order);
    
    /* Svuota eventuali messaggi pendenti */
    int flag;
    MPI_Status status;
    while (1) {
        MPI_Iprobe(MPI_ANY_SOURCE, VF2_TAG_FOUND, comm, &flag, &status);
        if (!flag) break;
        int dummy;
        MPI_Recv(&dummy, 1, MPI_INT, status.MPI_SOURCE, VF2_TAG_FOUND, 
                 comm, MPI_STATUS_IGNORE);
    }
    
    return (global_result > 0);
}

/* ============================================================================
 * VERSIONE CON METRICHE
 * ============================================================================ */

VF2MpiResult vf2pp_find_isomorphism_mpi(Graph* g1, Graph* g2, MPI_Comm comm) {
    VF2MpiResult result;
    memset(&result, 0, sizeof(VF2MpiResult));
    result.finder_rank = -1;
    
    int rank, size;
    MPI_Comm_rank(comm, &rank);
    MPI_Comm_size(comm, &size);
    
    double start_time = MPI_Wtime();
    double comm_start, comm_end;
    double total_comm_time = 0.0;
    
    /* Controlli preliminari */
    if (g1 == NULL || g2 == NULL) {
        result.total_time = MPI_Wtime() - start_time;
        return result;
    }
    
    if (g1->num_nodes == 0 && g2->num_nodes == 0) {
        result.found = true;
        result.total_time = MPI_Wtime() - start_time;
        return result;
    }
    
    if (g1->num_nodes != g2->num_nodes || g1->num_edges != g2->num_edges) {
        result.total_time = MPI_Wtime() - start_time;
        return result;
    }
    
    int n = g1->num_nodes;
    result.num_nodes = n;
    
    graph_reset_mapping(g1);
    graph_reset_mapping(g2);
    
    int* node_order = (int*)malloc(n * sizeof(int));
    if (node_order == NULL) {
        result.total_time = MPI_Wtime() - start_time;
        return result;
    }
    
    if (compute_matching_order(g1, node_order) != 0) {
        free(node_order);
        result.total_time = MPI_Wtime() - start_time;
        return result;
    }
    
    /* FASE 1: Candidati iniziali */
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
    
    /* FASE 2: Broadcast */
    comm_start = MPI_Wtime();
    MPI_Bcast(&total_candidates, 1, MPI_INT, 0, comm);
    comm_end = MPI_Wtime();
    total_comm_time += (comm_end - comm_start);
    
    if (total_candidates == 0) {
        if (rank == 0 && all_candidates) free(all_candidates);
        free(node_order);
        result.comm_time = total_comm_time;
        result.total_time = MPI_Wtime() - start_time;
        result.compute_time = result.total_time - result.comm_time;
        return result;
    }
    
    if (rank != 0) {
        all_candidates = (int*)malloc(total_candidates * sizeof(int));
    }
    
    comm_start = MPI_Wtime();
    MPI_Bcast(all_candidates, total_candidates, MPI_INT, 0, comm);
    comm_end = MPI_Wtime();
    total_comm_time += (comm_end - comm_start);
    
    /* FASE 3: Distribuzione */
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
    
    /* FASE 4: Esplorazione */
    double compute_start = MPI_Wtime();
    
    bool local_found = false;
    volatile bool should_terminate = false;
    
    for (int c = 0; c < my_count && !local_found && !should_terminate; c++) {
        graph_reset_mapping(g1);
        graph_reset_mapping(g2);
        
        local_found = explore_subtree(g1, g2, node_order, my_candidates[c],
                                      n, rank, &should_terminate, comm);
        
        if (!local_found) {
            int flag;
            MPI_Status status;
            MPI_Iprobe(MPI_ANY_SOURCE, VF2_TAG_FOUND, comm, &flag, &status);
            if (flag) {
                should_terminate = true;
                int dummy;
                MPI_Recv(&dummy, 1, MPI_INT, status.MPI_SOURCE, VF2_TAG_FOUND, 
                         comm, MPI_STATUS_IGNORE);
            }
        }
    }
    
    double compute_end = MPI_Wtime();
    result.compute_time = compute_end - compute_start;
    
    /* FASE 5: Comunicazione risultato */
    comm_start = MPI_Wtime();
    
    if (local_found) {
        int msg = 1;
        for (int i = 0; i < size; i++) {
            if (i != rank) {
                MPI_Send(&msg, 1, MPI_INT, i, VF2_TAG_FOUND, comm);
            }
        }
    }
    
    int local_result = local_found ? 1 : 0;
    int global_result = 0;
    MPI_Allreduce(&local_result, &global_result, 1, MPI_INT, MPI_MAX, comm);
    
    /* Trova chi ha trovato */
    int finder = local_found ? rank : size;  /* size = nessuno */
    int global_finder;
    MPI_Allreduce(&finder, &global_finder, 1, MPI_INT, MPI_MIN, comm);
    
    comm_end = MPI_Wtime();
    total_comm_time += (comm_end - comm_start);
    
    /* Estrai mapping se trovato */
    if (local_found) {
        result.mapping = (int*)malloc(n * sizeof(int));
        if (result.mapping != NULL) {
            for (int i = 0; i < n; i++) {
                result.mapping[i] = g1->nodes[i].mapped;
            }
        }
    }
    
    /* Cleanup */
    if (my_candidates) free(my_candidates);
    free(node_order);
    
    /* Svuota messaggi pendenti */
    int flag;
    MPI_Status status;
    while (1) {
        MPI_Iprobe(MPI_ANY_SOURCE, VF2_TAG_FOUND, comm, &flag, &status);
        if (!flag) break;
        int dummy;
        MPI_Recv(&dummy, 1, MPI_INT, status.MPI_SOURCE, VF2_TAG_FOUND, 
                 comm, MPI_STATUS_IGNORE);
    }
    
    result.found = (global_result > 0);
    result.finder_rank = (global_result > 0) ? global_finder : -1;
    result.comm_time = total_comm_time;
    result.total_time = MPI_Wtime() - start_time;
    
    return result;
}

void vf2_mpi_result_free(VF2MpiResult* result) {
    if (result != NULL && result->mapping != NULL) {
        free(result->mapping);
        result->mapping = NULL;
    }
}

void vf2_mpi_print_stats(const VF2MpiResult* result, MPI_Comm comm) {
    int rank, size;
    MPI_Comm_rank(comm, &rank);
    MPI_Comm_size(comm, &size);
    
    /* Raccogli tempi di tutti i processi */
    double* all_compute_times = NULL;
    double* all_comm_times = NULL;
    
    if (rank == 0) {
        all_compute_times = (double*)malloc(size * sizeof(double));
        all_comm_times = (double*)malloc(size * sizeof(double));
    }
    
    MPI_Gather(&result->compute_time, 1, MPI_DOUBLE,
               all_compute_times, 1, MPI_DOUBLE, 0, comm);
    MPI_Gather(&result->comm_time, 1, MPI_DOUBLE,
               all_comm_times, 1, MPI_DOUBLE, 0, comm);
    
    if (rank == 0) {
        printf("\n=== STATISTICHE MPI ===\n");
        printf("Processi:        %d\n", size);
        printf("Risultato:       %s\n", result->found ? "ISOMORFI" : "NON ISOMORFI");
        
        if (result->found) {
            printf("Trovato da rank: %d\n", result->finder_rank);
        }
        
        printf("\nTempi per processo:\n");
        double max_compute = 0, min_compute = all_compute_times[0];
        double total_compute = 0;
        
        for (int i = 0; i < size; i++) {
            printf("  Rank %d: compute=%.6fs, comm=%.6fs\n", 
                   i, all_compute_times[i], all_comm_times[i]);
            
            if (all_compute_times[i] > max_compute) max_compute = all_compute_times[i];
            if (all_compute_times[i] < min_compute) min_compute = all_compute_times[i];
            total_compute += all_compute_times[i];
        }
        
        printf("\nBilancio carico:\n");
        printf("  Min compute: %.6fs\n", min_compute);
        printf("  Max compute: %.6fs\n", max_compute);
        printf("  Media:       %.6fs\n", total_compute / size);
        printf("  Sbilanciamento: %.2f%%\n", 
               (max_compute - min_compute) / max_compute * 100.0);
        
        printf("\nTempo totale:   %.6fs\n", result->total_time);
        
        free(all_compute_times);
        free(all_comm_times);
    }
}
