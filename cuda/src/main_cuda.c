/*
 * VF2++ Graph Isomorphism - CUDA Version
 * HPC Project
 *
 * Entry point for CUDA benchmark.
 * Handles file loading, CSV formatting and calling the CUDA wrapper.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>

#include "graph.h"
#include "graph_io.h"
#include "timing.h"

// Forward declaration of the CUDA wrapper defined in .cu file
typedef struct {
    int blocks;
    int threads_per_block;
    int device_id;
} VF2CudaConfig;

#ifdef __cplusplus
extern "C" {
#endif
    bool vf2pp_find_isomorphism_cuda(Graph* g1, Graph* g2, VF2CudaConfig* config);
#ifdef __cplusplus
}
#endif

// --- HELPER FUNCTIONS FOR CSV OUTPUT ---

static void get_filename(const char* path, char* buffer) {
    const char* slash = strrchr(path, '/');
    if (slash) strcpy(buffer, slash + 1);
    else strcpy(buffer, path);
}

static void parse_metadata(const char* filename, char* size_out, char* type_out) {
    char temp[256];
    strncpy(temp, filename, 255);
    char* token = strtok(temp, "_");
    if (token) strcpy(size_out, token);
    else strcpy(size_out, "unknown");
    
    token = strtok(NULL, "_");
    if (token) strcpy(type_out, token);
    else strcpy(type_out, "unknown");
}

int main(int argc, char** argv) {
    if (argc < 3) {
        fprintf(stderr, "Usage: %s <g1> <g2> [blocks] [threads] [csv_out]\n", argv[0]);
        return 1;
    }

    const char* g1_path = argv[1];
    const char* g2_path = argv[2];
    int blocks = (argc > 3) ? atoi(argv[3]) : 0;
    int threads = (argc > 4) ? atoi(argv[4]) : 0;
    const char* csv_path = (argc > 5) ? argv[5] : NULL;

    // Timers
    Timer t_total, t_load, t_algo;
    timer_start(&t_total);

    // 1. Load Graphs
    timer_start(&t_load);
    Graph* g1 = graph_read_from_file(g1_path);
    Graph* g2 = graph_read_from_file(g2_path);
    timer_stop(&t_load);

    if (!g1 || !g2) {
        fprintf(stderr, "Error loading graphs\n");
        return 1;
    }

    // 2. Setup Config
    VF2CudaConfig config;
    config.blocks = blocks;
    config.threads_per_block = threads;
    config.device_id = 0;

    // printf("Running CUDA VF2++...\n"); // Verbose off per pulizia output
    
    // 3. Algorithm Execution
    timer_start(&t_algo);
    bool found = vf2pp_find_isomorphism_cuda(g1, g2, &config);
    timer_stop(&t_algo);
    
    timer_stop(&t_total);

    // 4. Reporting
    printf("Result: %s\n", found ? "ISOMORPHIC" : "NOT ISOMORPHIC");
    printf("Time Algo: %.6f s\n", timer_elapsed(&t_algo));

    // 5. CSV Output
    if (csv_path) {
        char fname[256], size_lbl[32], type_lbl[32];
        get_filename(g1_path, fname);
        parse_metadata(fname, size_lbl, type_lbl);
        
        double ram_mb = (double)(graph_memory_size(g1) + graph_memory_size(g2)) / (1024*1024);
        
        FILE* fp = fopen(csv_path, "a");
        if (fp) {
            fseek(fp, 0, SEEK_END);
            if (ftell(fp) == 0) {
                 fprintf(fp, "Size,Type,Nodes,Edges,RAM_MB,Blocks,Threads,Time_Load_s,Time_Algo_s,Time_Total_s,Found\n");
            }
            // Output coerente con le altre versioni
            fprintf(fp, "%s,%s,%d,%d,%.2f,%d,%d,%.6f,%.6f,%.6f,%d\n",
                    size_lbl, type_lbl, g1->num_nodes, g1->num_edges, ram_mb,
                    config.blocks, config.threads_per_block,
                    timer_elapsed(&t_load), timer_elapsed(&t_algo), timer_elapsed(&t_total),
                    found ? 1 : 0);
            fclose(fp);
        }
    }

    graph_free(g1);
    graph_free(g2);
    return 0;
}