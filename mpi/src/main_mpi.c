/*
 * =============================================================================
 * VF2++ Graph Isomorphism - MPI Parallel Version
 * HPC Project
 * =============================================================================
 * 
 * STRATEGIA DI PARALLELIZZAZIONE MPI
 * ===================================
 * 
 * L'algoritmo VF2++ viene parallelizzato dividendo i candidati iniziali
 * tra i processi MPI. Ogni processo esplora indipendentemente il suo
 * sottoalbero di ricerca con early termination.
 * 
 * USO:
 *   mpirun -np 4 ./vf2pp_mpi_O3 g1.txt g2.txt [verbose]
 * 
 * =============================================================================
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include <mpi.h>

#include "graph.h"
#include "graph_io.h"
#include "vf2pp.h"
#include "timing.h"
#include "vf2pp_mpi.h"

/* ============================================================================
 * COSTANTI E CONFIGURAZIONE
 * ============================================================================ */

#define CSV_OUTPUT_PATH "./mpi/output/risultati_mpi.csv"

/* ============================================================================
 * FUNZIONI HELPER
 * ============================================================================ */

/**
 * Estrae il tag di ottimizzazione dal nome dell'eseguibile
 */
static void get_optimizer_tag(const char* path, char* buffer, size_t size) {
    const char* filename = path;
    const char* last_slash = strrchr(path, '/');
    const char* last_backslash = strrchr(path, '\\');

    if (last_slash && last_backslash) {
        filename = (last_slash > last_backslash) ? last_slash + 1 : last_backslash + 1;
    } else if (last_slash) {
        filename = last_slash + 1;
    } else if (last_backslash) {
        filename = last_backslash + 1;
    }

    if (strstr(filename, "Ofast") != NULL) strncpy(buffer, "Ofast", size);
    else if (strstr(filename, "O3") != NULL) strncpy(buffer, "O3", size);
    else if (strstr(filename, "O2") != NULL) strncpy(buffer, "O2", size);
    else if (strstr(filename, "O1") != NULL) strncpy(buffer, "O1", size);
    else if (strstr(filename, "O0") != NULL) strncpy(buffer, "O0", size);
    else strncpy(buffer, "Ox", size);
    
    buffer[size - 1] = '\0';
}

/**
 * Scrive i risultati in formato CSV
 */
static void write_output_csv(const char* filename, const char* opt_tag,
                              int num_procs, int is_isomorphic, 
                              double time_load, double time_algo, 
                              double time_total, double ram_mb,
                              double compute_time, double comm_time) {
    
    FILE* f = fopen(filename, "a");
    if (f == NULL) {
        fprintf(stderr, "Attenzione: impossibile scrivere su %s\n", filename);
        return;
    }

    fseek(f, 0, SEEK_END);
    if (ftell(f) == 0) {
        fprintf(f, "Optimizer,NumProcs,Isomorphic,Time_Load_s,Time_VF2_s,Time_Total_s,"
                   "RAM_Graph_MB,Compute_Time_s,Comm_Time_s\n");
    }

    fprintf(f, "%s,%d,%d,%.6f,%.6f,%.6f,%.2f,%.6f,%.6f\n", 
            opt_tag,
            num_procs,
            is_isomorphic, 
            time_load, 
            time_algo, 
            time_total, 
            ram_mb,
            compute_time,
            comm_time);
    
    fclose(f);
}

/* ============================================================================
 * MAIN
 * ============================================================================ */

int main(int argc, char* argv[]) {
    int rank, size;
    
    MPI_Init(&argc, &argv);
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &size);
    
    char opt_tag[16];
    get_optimizer_tag(argv[0], opt_tag, sizeof(opt_tag));
    
    if (argc < 3) {
        if (rank == 0) {
            fprintf(stderr, "Uso: mpirun -np N %s <grafo1> <grafo2> [verbose]\n", 
                    argv[0]);
        }
        MPI_Finalize();
        return EXIT_FAILURE;
    }
    
    const char* file_g1 = argv[1];
    const char* file_g2 = argv[2];
    int verbose = (argc >= 4) ? atoi(argv[3]) : 0;
    
    Timer timer_total, timer_load;
    double time_load = 0.0;
    double ram_total_mb = 0.0;
    
    /* ========== CARICAMENTO GRAFI (tutti i rank) ========== */
    timer_start(&timer_total);
    timer_start(&timer_load);
    
    if (rank == 0 && verbose) {
        printf("Caricamento grafo G1 da: %s\n", file_g1);
    }
    
    Graph* g1 = graph_read_from_file(file_g1);
    if (g1 == NULL) {
        if (rank == 0) {
            fprintf(stderr, "ERRORE: impossibile caricare G1 da '%s'\n", file_g1);
        }
        MPI_Abort(MPI_COMM_WORLD, EXIT_FAILURE);
        return EXIT_FAILURE;
    }
    
    if (rank == 0 && verbose) {
        printf("Caricamento grafo G2 da: %s\n", file_g2);
    }
    
    Graph* g2 = graph_read_from_file(file_g2);
    if (g2 == NULL) {
        if (rank == 0) {
            fprintf(stderr, "ERRORE: impossibile caricare G2 da '%s'\n", file_g2);
        }
        graph_free(g1);
        MPI_Abort(MPI_COMM_WORLD, EXIT_FAILURE);
        return EXIT_FAILURE;
    }
    
    timer_stop(&timer_load);
    time_load = timer_elapsed(&timer_load);
    
    /* Calcolo RAM */
    size_t ram_g1 = graph_memory_size(g1);
    size_t ram_g2 = graph_memory_size(g2);
    ram_total_mb = (double)(ram_g1 + ram_g2) / (1024.0 * 1024.0);
    
    /* Info grafi (solo rank 0) */
    if (rank == 0) {
        printf("\n=== VF2++ MPI PARALLELO [%s] ===\n", opt_tag);
        printf("Processi MPI: %d\n", size);
        printf("G1: %d nodi, %d archi, RAM: %.2f MB\n", 
               g1->num_nodes, g1->num_edges / 2, (double)ram_g1 / (1024.0 * 1024.0));
        printf("G2: %d nodi, %d archi, RAM: %.2f MB\n", 
               g2->num_nodes, g2->num_edges / 2, (double)ram_g2 / (1024.0 * 1024.0));
        printf("RAM Totale Grafi: %.2f MB\n", ram_total_mb);
        printf("\nEsecuzione algoritmo parallelo...\n");
    }
    
    /* Sincronizza prima dell'algoritmo */
    MPI_Barrier(MPI_COMM_WORLD);
    
    /* ========== ESECUZIONE VF2++ PARALLELO ========== */
    VF2MpiResult mpi_result = vf2pp_find_isomorphism_mpi(g1, g2, MPI_COMM_WORLD);
    
    /* Fine timing totale */
    timer_stop(&timer_total);
    double time_total = timer_elapsed(&timer_total);
    
    /* ========== OUTPUT RISULTATI (solo rank 0) ========== */
    if (rank == 0) {
        printf("\n=== RISULTATO ===\n");
        if (mpi_result.found) {
            printf("I grafi sono ISOMORFI\n");
            printf("Trovato da rank: %d\n", mpi_result.finder_rank);
        } else {
            printf("I grafi NON sono isomorfi\n");
        }
        
        printf("\n=== METRICHE ===\n");
        printf("Tag Optimizer:     %s\n", opt_tag);
        printf("Processi MPI:      %d\n", size);
        printf("Tempo caricamento: %.6f s\n", time_load);
        printf("Tempo VF2++ MPI:   %.6f s\n", mpi_result.total_time);
        printf("  - Compute:       %.6f s\n", mpi_result.compute_time);
        printf("  - Comunicazioni: %.6f s\n", mpi_result.comm_time);
        printf("Tempo totale:      %.6f s\n", time_total);
        printf("RAM Grafi:         %.2f MB\n", ram_total_mb);
        
        /* Scrivi CSV */
        write_output_csv(CSV_OUTPUT_PATH, opt_tag, size,
                         mpi_result.found ? 1 : 0, 
                         time_load, mpi_result.total_time, time_total, 
                         ram_total_mb,
                         mpi_result.compute_time, mpi_result.comm_time);
        
        if (verbose) {
            printf("\nRisultati aggiunti a: %s\n", CSV_OUTPUT_PATH);
        }
    }
    
    /* Stampa statistiche dettagliate se verbose */
    if (verbose) {
        vf2_mpi_print_stats(&mpi_result, MPI_COMM_WORLD);
    }
    
    /* ========== CLEANUP ========== */
    vf2_mpi_result_free(&mpi_result);
    graph_free(g1);
    graph_free(g2);
    
    MPI_Finalize();
    return EXIT_SUCCESS;
}
