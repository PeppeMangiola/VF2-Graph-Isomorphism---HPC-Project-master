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
 * MODALITÀ DI ESECUZIONE:
 * 
 * 1. SINGLE-PAIR (default):
 *    OMP_NUM_THREADS=4 ./vf2pp_openmp_O3 g1.txt g2.txt [verbose]
 *    - Parallelizza l'algoritmo su una singola coppia di grafi
 *    - Ogni thread esplora un sottoinsieme dei candidati iniziali
 * 
 * 2. BATCH MODE:
 *    OMP_NUM_THREADS=4 ./vf2pp_openmp_O3 --batch ./inputs/
 *    - Distribuisce multiple coppie di grafi tra i thread
 *    - Gestisce workload più grandi con parallelismo task-based
 * 
 * =============================================================================
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include <omp.h>
#include <dirent.h>
#include <sys/stat.h>

#include "graph.h"
#include "graph_io.h"
#include "vf2pp.h"
#include "timing.h"
#include "vf2pp_openmp.h"

/* ============================================================================
 * COSTANTI E CONFIGURAZIONE
 * ============================================================================ */

#define MAX_FILENAME_LEN 512
#define MAX_PAIRS 1000
#define CSV_OUTPUT_PATH "./openmp/output/risultati_openmp.csv"

/* ============================================================================
 * STRUTTURE DATI 
 * ============================================================================ */

/**
 * Rappresenta una coppia di grafi da confrontare (per batch mode)
 */
typedef struct {
    char g1_path[MAX_FILENAME_LEN];
    char g2_path[MAX_FILENAME_LEN];
    int  pair_id;
} GraphPair;

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
        /* Header CSV */
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
 * MODALITÀ 1: SINGLE PAIR CON PARALLELIZZAZIONE OPENMP
 * ============================================================================ */

static int run_single_pair_mode(int argc, char* argv[], const char* opt_tag) {
    
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

/* ============================================================================
 * MODALITÀ 2: BATCH MODE (distribuzione coppie)
 * ============================================================================ */

/**
 * Trova tutte le coppie di grafi in una directory
 */
static int find_graph_pairs(const char* dir_path, GraphPair* pairs, int max_pairs) {
    DIR* dir = opendir(dir_path);
    if (dir == NULL) {
        fprintf(stderr, "Impossibile aprire directory: %s\n", dir_path);
        return 0;
    }
    
    int num_pairs = 0;
    struct dirent* entry;
    
    while ((entry = readdir(dir)) != NULL && num_pairs < max_pairs) {
        char* name = entry->d_name;
        int len = strlen(name);
        
        /* Cerca file *_g1.txt o *_iso_g1.txt */
        if (len > 7 && strcmp(name + len - 7, "_g1.txt") == 0) {
            char g2_name[MAX_FILENAME_LEN];
            strncpy(g2_name, name, len - 7);
            g2_name[len - 7] = '\0';
            strcat(g2_name, "_g2.txt");
            
            char g2_path[MAX_FILENAME_LEN];
            snprintf(g2_path, MAX_FILENAME_LEN, "%s/%s", dir_path, g2_name);
            
            struct stat st;
            if (stat(g2_path, &st) == 0) {
                snprintf(pairs[num_pairs].g1_path, MAX_FILENAME_LEN, 
                         "%s/%s", dir_path, name);
                snprintf(pairs[num_pairs].g2_path, MAX_FILENAME_LEN, 
                         "%s/%s", dir_path, g2_name);
                pairs[num_pairs].pair_id = num_pairs;
                num_pairs++;
            }
        }
    }
    
    closedir(dir);
    return num_pairs;
}

static int run_batch_mode(const char* input_dir, int num_threads,
                          const char* opt_tag) {
    
    GraphPair* all_pairs = (GraphPair*)malloc(MAX_PAIRS * sizeof(GraphPair));
    if (all_pairs == NULL) {
        fprintf(stderr, "Errore allocazione memoria\n");
        return EXIT_FAILURE;
    }
    
    int num_pairs = find_graph_pairs(input_dir, all_pairs, MAX_PAIRS);
    
    printf("\n");
    printf("=== VF2++ OPENMP BATCH MODE [%s] ===\n", opt_tag);
    printf("Directory input: %s\n", input_dir);
    printf("Coppie trovate:  %d\n", num_pairs);
    printf("Thread OpenMP:   %d\n", (num_threads > 0) ? num_threads : omp_get_max_threads());
    printf("\n");
    
    if (num_pairs <= 0) {
        fprintf(stderr, "Nessuna coppia di grafi trovata!\n");
        free(all_pairs);
        return EXIT_FAILURE;
    }
    
    /* Prepara array di path */
    const char** g1_paths = (const char**)malloc(num_pairs * sizeof(char*));
    const char** g2_paths = (const char**)malloc(num_pairs * sizeof(char*));
    VF2BatchResult* results = (VF2BatchResult*)malloc(num_pairs * sizeof(VF2BatchResult));
    
    if (g1_paths == NULL || g2_paths == NULL || results == NULL) {
        fprintf(stderr, "Errore allocazione memoria\n");
        free(all_pairs);
        if (g1_paths) free(g1_paths);
        if (g2_paths) free(g2_paths);
        if (results) free(results);
        return EXIT_FAILURE;
    }
    
    for (int i = 0; i < num_pairs; i++) {
        g1_paths[i] = all_pairs[i].g1_path;
        g2_paths[i] = all_pairs[i].g2_path;
    }
    
    /* Esegui batch */
    double start_time = omp_get_wtime();
    
    int ret = vf2pp_batch_openmp(g1_paths, g2_paths, num_pairs, results, num_threads);
    
    double end_time = omp_get_wtime();
    double total_time = end_time - start_time;
    
    if (ret != 0) {
        fprintf(stderr, "Errore nell'esecuzione batch\n");
        free(all_pairs);
        free(g1_paths);
        free(g2_paths);
        free(results);
        return EXIT_FAILURE;
    }
    
    /* Stampa risultati */
    printf("=== RISULTATI BATCH ===\n");
    printf("Tempo totale OpenMP: %.4f s\n", total_time);
    printf("Throughput:          %.2f coppie/s\n", num_pairs / total_time);
    printf("\n");
    
    int num_iso = 0, num_non_iso = 0;
    double total_algo_time = 0;
    
    for (int i = 0; i < num_pairs; i++) {
        if (results[i].is_isomorphic) {
            num_iso++;
        } else {
            num_non_iso++;
        }
        total_algo_time += results[i].time_algo;
    }
    
    printf("Coppie isomorfe:      %d\n", num_iso);
    printf("Coppie non isomorfe:  %d\n", num_non_iso);
    printf("Tempo VF2++ totale:   %.4f s\n", total_algo_time);
    printf("Tempo VF2++ medio:    %.6f s\n", total_algo_time / num_pairs);
    
    /* Cleanup */
    free(all_pairs);
    free(g1_paths);
    free(g2_paths);
    free(results);
    
    return EXIT_SUCCESS;
}

/* ============================================================================
 * MAIN
 * ============================================================================ */

int main(int argc, char* argv[]) {
    
    char opt_tag[16];
    get_optimizer_tag(argv[0], opt_tag, sizeof(opt_tag));
    
    int ret;
    
    /*
     * Modalità di esecuzione:
     * 
     * 1. SINGLE-PAIR (default) - parallelizza l'algoritmo:
     *    OMP_NUM_THREADS=4 ./vf2pp_openmp g1.txt g2.txt [verbose] [threads]
     * 
     * 2. BATCH - distribuisce coppie tra thread:
     *    OMP_NUM_THREADS=4 ./vf2pp_openmp --batch ./inputs/ [threads]
     */
    
    if (argc >= 3 && strcmp(argv[1], "--batch") == 0) {
        int num_threads = (argc >= 4) ? atoi(argv[3]) : 0;
        ret = run_batch_mode(argv[2], num_threads, opt_tag);
    } else {
        ret = run_single_pair_mode(argc, argv, opt_tag);
    }
    
    return ret;
}
