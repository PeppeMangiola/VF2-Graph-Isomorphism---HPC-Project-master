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
 * MODALITÀ DI ESECUZIONE:
 * 
 * 1. SINGLE-PAIR (default):
 *    mpirun -np 4 ./vf2pp_mpi_O3 g1.txt g2.txt [verbose]
 *    - Parallelizza l'algoritmo su una singola coppia di grafi
 *    - Ogni processo esplora un sottoinsieme dei candidati iniziali
 * 
 * 2. BATCH MODE:
 *    mpirun -np 4 ./vf2pp_mpi_O3 --batch ./inputs/
 *    - Distribuisce multiple coppie di grafi tra i processi
 *    - Gestisce workload più grandi di un singolo nodo
 * 
 * =============================================================================
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include <mpi.h>
#include <dirent.h>
#include <sys/stat.h>

#include "graph.h"
#include "graph_io.h"
#include "vf2pp.h"
#include "timing.h"
#include "vf2pp_mpi.h"

/* ============================================================================
 * COSTANTI E CONFIGURAZIONE
 * ============================================================================ */

#define MAX_FILENAME_LEN 512
#define MAX_PAIRS 1000
#define CSV_OUTPUT_PATH "./mpi/output/risultati_mpi.csv"

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

/**
 * Risultato di un confronto (per batch mode)
 */
typedef struct {
    int    pair_id;
    int    is_isomorphic;
    double time_load;
    double time_algo;
    double time_total;
    double ram_mb;
    int    num_nodes;
    int    num_edges;
} PairResult;

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
        /* Header CSV */
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
 * MODALITÀ 1: SINGLE PAIR CON PARALLELIZZAZIONE VERA
 * ============================================================================ */

static int run_single_pair_mode(int argc, char* argv[], int rank, int size,
                                 const char* opt_tag) {
    
    if (argc < 3) {
        if (rank == 0) {
            fprintf(stderr, "Uso: mpirun -np N %s <grafo1> <grafo2> [verbose]\n", 
                    argv[0]);
        }
        MPI_Barrier(MPI_COMM_WORLD);
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

/**
 * Processa una singola coppia usando l'algoritmo SEQUENZIALE
 * (per batch mode, ogni rank processa indipendentemente)
 */
static PairResult process_pair_sequential(const GraphPair* pair, int rank) {
    PairResult result;
    Timer timer_total, timer_load, timer_algo;
    
    memset(&result, 0, sizeof(PairResult));
    result.pair_id = pair->pair_id;
    
    timer_start(&timer_total);
    timer_start(&timer_load);
    
    Graph* g1 = graph_read_from_file(pair->g1_path);
    if (g1 == NULL) {
        fprintf(stderr, "[Rank %d] ERRORE: impossibile caricare G1: %s\n", 
                rank, pair->g1_path);
        return result;
    }
    
    Graph* g2 = graph_read_from_file(pair->g2_path);
    if (g2 == NULL) {
        fprintf(stderr, "[Rank %d] ERRORE: impossibile caricare G2: %s\n", 
                rank, pair->g2_path);
        graph_free(g1);
        return result;
    }
    
    timer_stop(&timer_load);
    result.time_load = timer_elapsed(&timer_load);
    result.num_nodes = g1->num_nodes;
    result.num_edges = g1->num_edges / 2;
    
    size_t ram_g1 = graph_memory_size(g1);
    size_t ram_g2 = graph_memory_size(g2);
    result.ram_mb = (double)(ram_g1 + ram_g2) / (1024.0 * 1024.0);
    
    timer_start(&timer_algo);
    bool is_iso = vf2pp_is_isomorphic(g1, g2);
    timer_stop(&timer_algo);
    
    result.time_algo = timer_elapsed(&timer_algo);
    result.is_isomorphic = is_iso ? 1 : 0;
    
    timer_stop(&timer_total);
    result.time_total = timer_elapsed(&timer_total);
    
    graph_free(g1);
    graph_free(g2);
    
    return result;
}

static int run_batch_mode(const char* input_dir, int rank, int size,
                          const char* opt_tag) {
    
    GraphPair* all_pairs = NULL;
    int num_pairs = 0;
    double start_time, end_time;
    
    if (rank == 0) {
        all_pairs = (GraphPair*)malloc(MAX_PAIRS * sizeof(GraphPair));
        if (all_pairs == NULL) {
            fprintf(stderr, "Errore allocazione memoria\n");
            num_pairs = -1;
        } else {
            num_pairs = find_graph_pairs(input_dir, all_pairs, MAX_PAIRS);
        }
        
        printf("\n");
        printf("=== VF2++ MPI BATCH MODE [%s] ===\n", opt_tag);
        printf("Directory input: %s\n", input_dir);
        printf("Coppie trovate:  %d\n", num_pairs);
        printf("Processi MPI:    %d\n", size);
        printf("\n");
    }
    
    MPI_Bcast(&num_pairs, 1, MPI_INT, 0, MPI_COMM_WORLD);
    
    if (num_pairs <= 0) {
        if (rank == 0) {
            fprintf(stderr, "Nessuna coppia di grafi trovata o errore!\n");
            if (all_pairs) free(all_pairs);
        }
        return EXIT_FAILURE;
    }
    
    if (rank != 0) {
        all_pairs = (GraphPair*)malloc(num_pairs * sizeof(GraphPair));
    }
    
    MPI_Bcast(all_pairs, num_pairs * sizeof(GraphPair), MPI_BYTE, 0, MPI_COMM_WORLD);
    
    MPI_Barrier(MPI_COMM_WORLD);
    start_time = MPI_Wtime();
    
    /* Distribuzione round-robin */
    int my_count = 0;
    for (int i = rank; i < num_pairs; i += size) {
        my_count++;
    }
    
    PairResult* my_results = NULL;
    if (my_count > 0) {
        my_results = (PairResult*)malloc(my_count * sizeof(PairResult));
        if (my_results == NULL) {
            fprintf(stderr, "[Rank %d] Errore allocazione risultati\n", rank);
            free(all_pairs);
            MPI_Abort(MPI_COMM_WORLD, EXIT_FAILURE);
            return EXIT_FAILURE;
        }
    }
    
    int result_idx = 0;
    for (int i = rank; i < num_pairs; i += size) {
        if (rank == 0) {
            printf("[Rank %d] Elaborazione coppia %d/%d...\n", rank, i + 1, num_pairs);
        }
        
        my_results[result_idx] = process_pair_sequential(&all_pairs[i], rank);
        result_idx++;
    }
    
    MPI_Barrier(MPI_COMM_WORLD);
    end_time = MPI_Wtime();
    
    /* Raccolta risultati */
    int* recv_counts = NULL;
    int* displs = NULL;
    PairResult* all_results = NULL;
    
    if (rank == 0) {
        recv_counts = (int*)malloc(size * sizeof(int));
        displs = (int*)malloc(size * sizeof(int));
        all_results = (PairResult*)malloc(num_pairs * sizeof(PairResult));
    }
    
    MPI_Gather(&my_count, 1, MPI_INT, recv_counts, 1, MPI_INT, 0, MPI_COMM_WORLD);
    
    if (rank == 0) {
        displs[0] = 0;
        for (int i = 1; i < size; i++) {
            displs[i] = displs[i-1] + recv_counts[i-1];
        }
        
        for (int i = 0; i < size; i++) {
            recv_counts[i] *= sizeof(PairResult);
            displs[i] *= sizeof(PairResult);
        }
    }
    
    MPI_Gatherv(my_results, my_count * sizeof(PairResult), MPI_BYTE,
                all_results, recv_counts, displs, MPI_BYTE,
                0, MPI_COMM_WORLD);
    
    if (rank == 0) {
        double total_time = end_time - start_time;
        
        printf("\n");
        printf("=== RISULTATI BATCH ===\n");
        printf("Tempo totale MPI: %.4f s\n", total_time);
        printf("Throughput:       %.2f coppie/s\n", num_pairs / total_time);
        printf("\n");
        
        int num_iso = 0, num_non_iso = 0;
        double total_algo_time = 0;
        
        for (int i = 0; i < num_pairs; i++) {
            if (all_results[i].is_isomorphic) {
                num_iso++;
            } else {
                num_non_iso++;
            }
            total_algo_time += all_results[i].time_algo;
        }
        
        printf("Coppie isomorfe:      %d\n", num_iso);
        printf("Coppie non isomorfe:  %d\n", num_non_iso);
        printf("Tempo VF2++ totale:   %.4f s\n", total_algo_time);
        printf("Tempo VF2++ medio:    %.6f s\n", total_algo_time / num_pairs);
        
        printf("\nRisultati salvati in: %s\n", CSV_OUTPUT_PATH);
        
        free(recv_counts);
        free(displs);
        free(all_results);
    }
    
    if (my_results) free(my_results);
    free(all_pairs);
    
    return EXIT_SUCCESS;
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
    
    int ret;
    
    /*
     * Modalità di esecuzione:
     * 
     * 1. SINGLE-PAIR (default) - parallelizza l'algoritmo:
     *    mpirun -np 4 ./vf2pp_mpi g1.txt g2.txt [verbose]
     * 
     * 2. BATCH - distribuisce coppie tra processi:
     *    mpirun -np 4 ./vf2pp_mpi --batch ./inputs/
     */
    
    if (argc >= 3 && strcmp(argv[1], "--batch") == 0) {
        ret = run_batch_mode(argv[2], rank, size, opt_tag);
    } else {
        ret = run_single_pair_mode(argc, argv, rank, size, opt_tag);
    }
    
    MPI_Finalize();
    return ret;
}
