/*
 * =============================================================================
 * VF2++ Graph Isomorphism - OpenMP Parallel Version
 * HPC Project
 * =============================================================================
 * 
 * STRATEGIA DI PARALLELIZZAZIONE OPENMP
 * ======================================
 * 
 * L'algoritmo VF2++ viene parallelizzato dividendo i candidati iniziali
 * tra i thread OpenMP. Ogni thread esplora indipendentemente il suo
 * sottoalbero di ricerca con early termination.
 * 
 * USO:
 *   OMP_NUM_THREADS=4 ./vf2pp_openmp_O3 g1.txt g2.txt [verbose] [num_threads]
 * 
 * =============================================================================
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include <omp.h>

#include "graph.h"
#include "graph_io.h"
#include "vf2pp.h"
#include "timing.h"
#include "vf2pp_openmp.h"

/* ============================================================================
 * COSTANTI E CONFIGURAZIONE
 * ============================================================================ */

#define CSV_OUTPUT_PATH "./openmp/output/risultati_openmp.csv"

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
                              int num_threads, int is_isomorphic, 
                              double time_load, double time_algo, 
                              double time_total, double ram_mb,
                              double parallel_time, int candidates_explored) {
    
    FILE* f = fopen(filename, "a");
    if (f == NULL) {
        fprintf(stderr, "Attenzione: impossibile scrivere su %s\n", filename);
        return;
    }

    fseek(f, 0, SEEK_END);
    if (ftell(f) == 0) {
        fprintf(f, "Optimizer,NumThreads,Isomorphic,Time_Load_s,Time_VF2_s,Time_Total_s,"
                   "RAM_Graph_MB,Parallel_Time_s,Candidates_Explored\n");
    }

    fprintf(f, "%s,%d,%d,%.6f,%.6f,%.6f,%.2f,%.6f,%d\n", 
            opt_tag,
            num_threads,
            is_isomorphic, 
            time_load, 
            time_algo, 
            time_total, 
            ram_mb,
            parallel_time,
            candidates_explored);
    
    fclose(f);
}

/* ============================================================================
 * MAIN
 * ============================================================================ */

int main(int argc, char* argv[]) {
    
    char opt_tag[16];
    get_optimizer_tag(argv[0], opt_tag, sizeof(opt_tag));
    
    if (argc < 3) {
        fprintf(stderr, "Uso: OMP_NUM_THREADS=N %s <grafo1> <grafo2> [verbose] [num_threads]\n", 
                argv[0]);
        return EXIT_FAILURE;
    }
    
    const char* file_g1 = argv[1];
    const char* file_g2 = argv[2];
    int verbose = (argc >= 4) ? atoi(argv[3]) : 0;
    int user_threads = (argc >= 5) ? atoi(argv[4]) : 0;
    
    Timer timer_total, timer_load;
    double time_load = 0.0;
    double ram_total_mb = 0.0;
    
    /* ========== CARICAMENTO GRAFI ========== */
    timer_start(&timer_total);
    timer_start(&timer_load);
    
    if (verbose) {
        printf("Caricamento grafo G1 da: %s\n", file_g1);
    }
    
    Graph* g1 = graph_read_from_file(file_g1);
    if (g1 == NULL) {
        fprintf(stderr, "ERRORE: impossibile caricare G1 da '%s'\n", file_g1);
        return EXIT_FAILURE;
    }
    
    if (verbose) {
        printf("Caricamento grafo G2 da: %s\n", file_g2);
    }
    
    Graph* g2 = graph_read_from_file(file_g2);
    if (g2 == NULL) {
        fprintf(stderr, "ERRORE: impossibile caricare G2 da '%s'\n", file_g2);
        graph_free(g1);
        return EXIT_FAILURE;
    }
    
    timer_stop(&timer_load);
    time_load = timer_elapsed(&timer_load);
    
    /* Calcolo RAM */
    size_t ram_g1 = graph_memory_size(g1);
    size_t ram_g2 = graph_memory_size(g2);
    ram_total_mb = (double)(ram_g1 + ram_g2) / (1024.0 * 1024.0);
    
    /* Configurazione OpenMP */
    VF2OpenMPConfig config = vf2_openmp_default_config();
    config.num_threads = user_threads;
    config.verbose = verbose;
    
    /* Info grafi */
    int max_threads = (user_threads > 0) ? user_threads : omp_get_max_threads();
    
    printf("\n=== VF2++ OPENMP PARALLELO [%s] ===\n", opt_tag);
    printf("Thread OpenMP: %d\n", max_threads);
    printf("G1: %d nodi, %d archi, RAM: %.2f MB\n", 
           g1->num_nodes, g1->num_edges / 2, (double)ram_g1 / (1024.0 * 1024.0));
    printf("G2: %d nodi, %d archi, RAM: %.2f MB\n", 
           g2->num_nodes, g2->num_edges / 2, (double)ram_g2 / (1024.0 * 1024.0));
    printf("RAM Totale Grafi: %.2f MB\n", ram_total_mb);
    printf("\nEsecuzione algoritmo parallelo...\n");
    
    /* ========== ESECUZIONE VF2++ PARALLELO ========== */
    VF2OpenMPResult omp_result = vf2pp_find_isomorphism_openmp(g1, g2, &config);
    
    /* Fine timing totale */
    timer_stop(&timer_total);
    double time_total = timer_elapsed(&timer_total);
    
    /* ========== OUTPUT RISULTATI ========== */
    printf("\n=== RISULTATO ===\n");
    if (omp_result.found) {
        printf("I grafi sono ISOMORFI\n");
        printf("Trovato da thread: %d\n", omp_result.finder_thread);
        
        /* Verifica correttezza mapping */
        if (omp_result.mapping != NULL) {
            bool valid = vf2_openmp_verify_mapping(g1, g2, omp_result.mapping, 
                                                    omp_result.num_nodes);
            printf("Mapping verificato: %s\n", valid ? "CORRETTO" : "ERRORE!");
        }
    } else {
        printf("I grafi NON sono isomorfi\n");
    }
    
    printf("\n=== METRICHE ===\n");
    printf("Tag Optimizer:      %s\n", opt_tag);
    printf("Thread OpenMP:      %d\n", omp_result.num_threads);
    printf("Tempo caricamento:  %.6f s\n", time_load);
    printf("Tempo VF2++ OpenMP: %.6f s\n", omp_result.total_time);
    printf("  - Parallelo:      %.6f s\n", omp_result.parallel_time);
    printf("  - Overhead:       %.6f s\n", omp_result.total_time - omp_result.parallel_time);
    printf("Tempo totale:       %.6f s\n", time_total);
    printf("RAM Grafi:          %.2f MB\n", ram_total_mb);
    printf("Candidati esplorati: %d\n", omp_result.candidates_explored);
    
    /* Scrivi CSV */
    write_output_csv(CSV_OUTPUT_PATH, opt_tag, omp_result.num_threads,
                     omp_result.found ? 1 : 0, 
                     time_load, omp_result.total_time, time_total, 
                     ram_total_mb,
                     omp_result.parallel_time,
                     omp_result.candidates_explored);
    
    if (verbose) {
        printf("\nRisultati aggiunti a: %s\n", CSV_OUTPUT_PATH);
        vf2_openmp_print_stats(&omp_result);
    }
    
    /* ========== CLEANUP ========== */
    vf2_openmp_result_free(&omp_result);
    graph_free(g1);
    graph_free(g2);
    
    return EXIT_SUCCESS;
}
