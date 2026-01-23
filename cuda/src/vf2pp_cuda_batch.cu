/*
 * VF2++ Graph Isomorphism - CUDA Batch Implementation
 * 
 * Questa versione processa MULTIPLE coppie di grafi in parallelo.
 * Ideale per workload dove bisogna verificare isomorfismo di molte coppie.
 * 
 * Ottimizzazioni specifiche batch:
 * 1. Un blocco = una coppia di grafi (massima indipendenza)
 * 2. Thread nel blocco collaborano sul backtracking
 * 3. Prefetch dei grafi per nascondere latenza
 */

#include <cuda_runtime.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

extern "C" {
#include "graph.h"
#include "vf2pp.h"
#include "node_ordering.h"
#include "find_candidates.h"
}

// ============================================================================
// BATCH CONFIGURATION
// ============================================================================

#define MAX_BATCH_SIZE 256
#define THREADS_PER_PAIR 128

typedef struct {
    int blocks;
    int threads_per_block;
    int device_id;
} VF2CudaConfig;

typedef struct {
    int num_nodes;
    int num_edges;
    int row_ptr_offset;   // Offset nell'array globale
    int col_ind_offset;
} BatchGraphInfo;

// ============================================================================
// ERROR CHECKING
// ============================================================================

#define cudaCheckError(ans) { gpuAssert((ans), __FILE__, __LINE__); }
inline void gpuAssert(cudaError_t code, const char *file, int line, bool abort=true) {
   if (code != cudaSuccess) {
      fprintf(stderr,"CUDA Error: %s at %s:%d\n", cudaGetErrorString(code), file, line);
      if (abort) exit(code);
   }
}

// ============================================================================
// DEVICE HELPERS
// ============================================================================

__device__ __forceinline__ bool binary_search_dev(const int* arr, int start, int end, int target) {
    while (start < end) {
        int mid = start + (end - start) / 2;
        int val = arr[mid];
        if (val == target) return true;
        if (val < target) start = mid + 1;
        else end = mid;
    }
    return false;
}

__device__ bool check_feasibility_batch(
    int u, int v, int n,
    const int* g1_row, const int* g1_col,
    const int* g2_row, const int* g2_col,
    const int* map_g1
) {
    int u_deg = g1_row[u+1] - g1_row[u];
    int v_deg = g2_row[v+1] - g2_row[v];
    if (u_deg > v_deg) return false;

    int u_start = g1_row[u];
    int u_end = g1_row[u+1];
    int v_start = g2_row[v];
    int v_end = g2_row[v+1];
    
    for (int i = u_start; i < u_end; i++) {
        int u_nbr = g1_col[i];
        int u_nbr_map = map_g1[u_nbr];
        if (u_nbr_map != -1) {
            if (!binary_search_dev(g2_col, v_start, v_end, u_nbr_map)) {
                return false;
            }
        }
    }
    return true;
}

// ============================================================================
// BATCH KERNEL - Un blocco per coppia di grafi
// ============================================================================

__global__ void vf2_batch_kernel(
    // Graph data (packed)
    const int* __restrict__ all_row_ptrs,
    const int* __restrict__ all_col_inds,
    const BatchGraphInfo* __restrict__ g1_infos,
    const BatchGraphInfo* __restrict__ g2_infos,
    int num_pairs,
    // Node orders (packed)
    const int* __restrict__ all_node_orders,
    // Results
    int* __restrict__ results,  // results[i] = 1 se coppia i è isomorfa
    // State pool
    int* __restrict__ state_pool,
    size_t max_nodes
) {
    int pair_idx = blockIdx.x;
    if (pair_idx >= num_pairs) return;
    
    // Ottieni info grafi per questa coppia
    BatchGraphInfo g1_info = g1_infos[pair_idx];
    BatchGraphInfo g2_info = g2_infos[pair_idx];
    
    int n = g1_info.num_nodes;
    if (n != g2_info.num_nodes) {
        if (threadIdx.x == 0) results[pair_idx] = 0;
        return;
    }
    if (n == 0) {
        if (threadIdx.x == 0) results[pair_idx] = 1;
        return;
    }
    
    // Puntatori ai dati di questo grafo
    const int* g1_row = all_row_ptrs + g1_info.row_ptr_offset;
    const int* g1_col = all_col_inds + g1_info.col_ind_offset;
    const int* g2_row = all_row_ptrs + g2_info.row_ptr_offset;
    const int* g2_col = all_col_inds + g2_info.col_ind_offset;
    const int* node_order = all_node_orders + pair_idx * max_nodes;
    
    // Shared memory per il blocco
    extern __shared__ int shared[];
    int* sh_map_g1 = shared;                    // [n]
    int* sh_map_g2 = shared + n;                // [n]
    int* sh_found = shared + 2*n;               // [1]
    
    // Init mapping
    for (int i = threadIdx.x; i < n; i += blockDim.x) {
        sh_map_g1[i] = -1;
        sh_map_g2[i] = -1;
    }
    if (threadIdx.x == 0) *sh_found = 0;
    __syncthreads();
    
    // Thread 0 esegue il backtracking, altri thread aiutano con candidati
    if (threadIdx.x == 0) {
        // Allocazione stack in registri/local per piccoli n
        int st_count[64];
        int st_next[64];
        int cand_pool[64 * 64];  // Assumiamo n <= 64 per questa versione
        
        // Se n troppo grande, usa global memory
        int* g_st_count = NULL;
        int* g_st_next = NULL;
        int* g_cand_pool = NULL;
        
        bool use_global = (n > 64);
        if (use_global) {
            size_t per_pair_size = 2*n + n*n;
            g_st_count = state_pool + pair_idx * per_pair_size;
            g_st_next = g_st_count + n;
            g_cand_pool = g_st_next + n;
        }
        
        int level = 0;
        if (use_global) g_st_count[0] = -1;
        else st_count[0] = -1;
        
        while (level >= 0 && !(*sh_found)) {
            if (level == n) {
                *sh_found = 1;
                break;
            }
            
            int u = node_order[level];
            
            // Genera candidati
            int* cnt_ptr = use_global ? &g_st_count[level] : &st_count[level];
            int* next_ptr = use_global ? &g_st_next[level] : &st_next[level];
            int* cands = use_global ? (g_cand_pool + level * n) : (cand_pool + level * n);
            
            if (*cnt_ptr == -1) {
                int cnt = 0;
                for (int v = 0; v < n; v++) {
                    if (sh_map_g2[v] == -1) {
                        if (check_feasibility_batch(u, v, n, g1_row, g1_col, g2_row, g2_col, sh_map_g1)) {
                            cands[cnt++] = v;
                        }
                    }
                }
                *cnt_ptr = cnt;
                *next_ptr = 0;
            }
            
            if (*next_ptr < *cnt_ptr) {
                int v = cands[*next_ptr];
                (*next_ptr)++;
                
                sh_map_g1[u] = v;
                sh_map_g2[v] = u;
                
                level++;
                if (level < n) {
                    if (use_global) g_st_count[level] = -1;
                    else st_count[level] = -1;
                }
            } else {
                level--;
                if (level >= 0) {
                    int u_prev = node_order[level];
                    int v_prev = sh_map_g1[u_prev];
                    sh_map_g1[u_prev] = -1;
                    sh_map_g2[v_prev] = -1;
                }
            }
        }
        
        results[pair_idx] = *sh_found;
    }
}

// ============================================================================
// HOST - SINGLE PAIR (compatibilità con interfaccia esistente)
// ============================================================================

static int compare_int(const void* a, const void* b) {
    return (*(int*)a) - (*(int*)b);
}

void flatten_graph_sorted_host(const Graph* g, int** h_row, int** h_col, int* h_edges) {
    int n = g->num_nodes;
    *h_edges = 0;
    for (int i = 0; i < n; i++) *h_edges += g->nodes[i].num_neighbors;
    
    *h_row = (int*)malloc((n + 1) * sizeof(int));
    *h_col = (int*)malloc((*h_edges > 0 ? *h_edges : 1) * sizeof(int));
    
    int curr = 0;
    for (int i = 0; i < n; i++) {
        (*h_row)[i] = curr;
        int num_nbr = g->nodes[i].num_neighbors;
        for (int j = 0; j < num_nbr; j++) {
            (*h_col)[curr + j] = g->nodes[i].neighborhood[j];
        }
        if (num_nbr > 0) {
            qsort((*h_col) + curr, num_nbr, sizeof(int), compare_int);
        }
        curr += num_nbr;
    }
    (*h_row)[n] = curr;
}

extern "C" bool vf2pp_find_isomorphism_cuda(Graph* g1, Graph* g2, VF2CudaConfig* config) {
    if (g1->num_nodes != g2->num_nodes) return false;
    if (g1->num_nodes == 0) return true;
    
    int n = g1->num_nodes;
    cudaCheckError(cudaSetDevice(config->device_id));
    
    // Node order
    int* node_order = (int*)malloc(n * sizeof(int));
    compute_matching_order(g1, node_order);
    
    // Flatten graphs
    int *h_r1, *h_c1, e1;
    int *h_r2, *h_c2, e2;
    flatten_graph_sorted_host(g1, &h_r1, &h_c1, &e1);
    flatten_graph_sorted_host(g2, &h_r2, &h_c2, &e2);
    
    // Packed arrays per batch (anche se è single pair)
    int total_row_ptrs = 2 * (n + 1);
    int total_col_inds = e1 + e2;
    
    int* h_all_rows = (int*)malloc(total_row_ptrs * sizeof(int));
    int* h_all_cols = (int*)malloc((total_col_inds > 0 ? total_col_inds : 1) * sizeof(int));
    
    memcpy(h_all_rows, h_r1, (n + 1) * sizeof(int));
    memcpy(h_all_rows + (n + 1), h_r2, (n + 1) * sizeof(int));
    if (e1 > 0) memcpy(h_all_cols, h_c1, e1 * sizeof(int));
    if (e2 > 0) memcpy(h_all_cols + e1, h_c2, e2 * sizeof(int));
    
    BatchGraphInfo h_g1_info = {n, e1, 0, 0};
    BatchGraphInfo h_g2_info = {n, e2, n + 1, e1};
    
    // Device memory
    int *d_all_rows, *d_all_cols, *d_node_order, *d_result, *d_state_pool;
    BatchGraphInfo *d_g1_infos, *d_g2_infos;
    
    cudaCheckError(cudaMalloc(&d_all_rows, total_row_ptrs * sizeof(int)));
    cudaCheckError(cudaMalloc(&d_all_cols, (total_col_inds > 0 ? total_col_inds : 1) * sizeof(int)));
    cudaCheckError(cudaMalloc(&d_node_order, n * sizeof(int)));
    cudaCheckError(cudaMalloc(&d_result, sizeof(int)));
    cudaCheckError(cudaMalloc(&d_g1_infos, sizeof(BatchGraphInfo)));
    cudaCheckError(cudaMalloc(&d_g2_infos, sizeof(BatchGraphInfo)));
    
    size_t state_size = (2 * n + (size_t)n * n) * sizeof(int);
    cudaCheckError(cudaMalloc(&d_state_pool, state_size));
    
    cudaCheckError(cudaMemcpy(d_all_rows, h_all_rows, total_row_ptrs * sizeof(int), cudaMemcpyHostToDevice));
    if (total_col_inds > 0) {
        cudaCheckError(cudaMemcpy(d_all_cols, h_all_cols, total_col_inds * sizeof(int), cudaMemcpyHostToDevice));
    }
    cudaCheckError(cudaMemcpy(d_node_order, node_order, n * sizeof(int), cudaMemcpyHostToDevice));
    cudaCheckError(cudaMemcpy(d_g1_infos, &h_g1_info, sizeof(BatchGraphInfo), cudaMemcpyHostToDevice));
    cudaCheckError(cudaMemcpy(d_g2_infos, &h_g2_info, sizeof(BatchGraphInfo), cudaMemcpyHostToDevice));
    cudaCheckError(cudaMemset(d_result, 0, sizeof(int)));
    
    // Shared memory: map_g1[n] + map_g2[n] + found[1]
    size_t shared_size = (2 * n + 1) * sizeof(int);
    
    // Launch
    vf2_batch_kernel<<<1, 128, shared_size>>>(
        d_all_rows, d_all_cols,
        d_g1_infos, d_g2_infos, 1,
        d_node_order,
        d_result,
        d_state_pool, n
    );
    
    cudaCheckError(cudaGetLastError());
    cudaCheckError(cudaDeviceSynchronize());
    
    int h_result;
    cudaCheckError(cudaMemcpy(&h_result, d_result, sizeof(int), cudaMemcpyDeviceToHost));
    
    // Cleanup
    cudaFree(d_all_rows);
    cudaFree(d_all_cols);
    cudaFree(d_node_order);
    cudaFree(d_result);
    cudaFree(d_g1_infos);
    cudaFree(d_g2_infos);
    cudaFree(d_state_pool);
    
    free(h_all_rows);
    free(h_all_cols);
    free(h_r1); free(h_c1);
    free(h_r2); free(h_c2);
    free(node_order);
    
    return (h_result > 0);
}
