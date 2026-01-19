/*
 * VF2++ Graph Isomorphism - Sequential Version
 * HPC Project
 * 
 * MODIFICHE:
 * 1. Estrae SOLO il flag (O0, O1, O2, O3) dal nome dell'eseguibile.
 * 2. RAM calcolata dalla struttura dati (graph_memory_size), non dal processo.
 * 3. CSV senza nomi dei file.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "graph.h"
#include "graph_io.h"
#include "vf2pp.h"
#include "timing.h"

/* ============================================================================
 * FUNZIONI HELPER
 * ============================================================================ */

/**
 * Cerca un flag di ottimizzazione noto all'interno del nome del file.
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

    if (strstr(filename, "Ofast") != NULL) {
        strncpy(buffer, "Ofast", size);
    } 
    else if (strstr(filename, "O3") != NULL) {
        strncpy(buffer, "O3", size);
    }
    else if (strstr(filename, "O2") != NULL) {
        strncpy(buffer, "O2", size);
    }
    else if (strstr(filename, "O1") != NULL) {
        strncpy(buffer, "O1", size);
    }
    else if (strstr(filename, "O0") != NULL) {
        strncpy(buffer, "O0", size);
    } 
    else {
        strncpy(buffer, filename, size - 1);
        buffer[size - 1] = '\0';
        char* dot = strrchr(buffer, '.');
        if (dot && strcmp(dot, ".exe") == 0) {
            *dot = '\0';
        }
    }
    buffer[size - 1] = '\0';
}

static void print_usage(const char* prog_name) {
    fprintf(stderr, "Uso: %s <grafo1> <grafo2> [verbose]\n", prog_name);
}

/**
 * Scrive i risultati in formato CSV.
 */
static void write_output_csv(const char* filename, const char* opt_tag, 
                             int is_isomorphic, double time_load, 
                             double time_algo, double time_total, 
                             double ram_mb) {
    
    FILE* f = fopen(filename, "a");
    if (f == NULL) {
        fprintf(stderr, "Attenzione: impossibile scrivere su %s\n", filename);
        return;
    }

    fseek(f, 0, SEEK_END);
    if (ftell(f) == 0) {
        fprintf(f, "Optimizer,Isomorphic,Time_Load_s,Time_VF2_s,Time_Total_s,RAM_Graph_MB\n");
    }

    fprintf(f, "%s,%d,%.6f,%.6f,%.6f,%.2f\n", 
            opt_tag, 
            is_isomorphic, 
            time_load, 
            time_algo, 
            time_total, 
            ram_mb);
    
    fclose(f);
}

/* ============================================================================
 * MAIN
 * ============================================================================ */

int main(int argc, char* argv[]) {
    /* 1. Determina il tag dell'ottimizzatore (es. "O3") */
    char opt_tag[64];
    get_optimizer_tag(argv[0], opt_tag, sizeof(opt_tag));

    /* Parsing argomenti */
    if (argc < 3) {
        print_usage(argv[0]);
        return EXIT_FAILURE;
    }
    
    const char* file_g1 = argv[1];
    const char* file_g2 = argv[2];
    int verbose = 0;
    
    if (argc >= 4) {
        verbose = atoi(argv[3]);
    }
    
    Timer timer_total, timer_load, timer_algo;
    
    /* ========== INIZIO TIMING TOTALE ========== */
    timer_start(&timer_total);
    
    /* ========== CARICAMENTO GRAFI ========== */
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
    double time_load = timer_elapsed(&timer_load);
    
    /* ========== CALCOLO RAM STRUTTURE DATI ========== */
    size_t ram_g1 = graph_memory_size(g1);
    size_t ram_g2 = graph_memory_size(g2);
    double ram_total_mb = (double)(ram_g1 + ram_g2) / (1024.0 * 1024.0);
    
    /* Info grafi */
    printf("=== VF2++ [%s] ===\n", opt_tag);
    printf("G1: %d nodi, %d archi, RAM: %.2f MB\n", g1->num_nodes, g1->num_edges / 2, (double)ram_g1 / (1024.0 * 1024.0));
    printf("G2: %d nodi, %d archi, RAM: %.2f MB\n", g2->num_nodes, g2->num_edges / 2, (double)ram_g2 / (1024.0 * 1024.0));
    printf("RAM Totale Grafi: %.2f MB\n", ram_total_mb);
    
    /* ========== ESECUZIONE VF2++ ========== */
    printf("\nEsecuzione...\n");
    
    timer_start(&timer_algo);
    
    bool is_isomorphic = vf2pp_is_isomorphic(g1, g2);
    
    timer_stop(&timer_algo);
    double time_algo = timer_elapsed(&timer_algo);
    
    /* ========== FINE TIMING TOTALE ========== */
    timer_stop(&timer_total);
    double time_total = timer_elapsed(&timer_total);
    
    /* ========== OUTPUT RISULTATI ========== */
    printf("\n=== RISULTATO ===\n");
    if (is_isomorphic) {
        printf("I grafi sono ISOMORFI\n");
    } else {
        printf("I grafi NON sono isomorfi\n");
    }
    
    printf("\n=== METRICHE ===\n");
    printf("Tag Optimizer:     %s\n", opt_tag);
    printf("Tempo caricamento: %.6f s\n", time_load);
    printf("Tempo VF2++:       %.6f s\n", time_algo);
    printf("Tempo totale:      %.6f s\n", time_total);
    printf("RAM Grafi:         %.2f MB\n", ram_total_mb);
    
    /* Scrivi file CSV */
    write_output_csv("./sequential/output/risultati_seq_mix.csv", opt_tag, 
                     is_isomorphic ? 1 : 0, 
                     time_load, time_algo, time_total, ram_total_mb);
    
    if (verbose) {
        printf("\nRisultati aggiunti a: risultati_seq_mix.csv\n");
    }
    
    /* ========== CLEANUP ========== */
    graph_free(g1);
    graph_free(g2);
    
    return is_isomorphic ? EXIT_SUCCESS : EXIT_FAILURE;
}
