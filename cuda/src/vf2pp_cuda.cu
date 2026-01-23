/*
 * VF2++ Graph Isomorphism - CUDA Version (OPTIMIZED)
 *
 * OTTIMIZZAZIONI APPLICATE:
 * 1. BITSET MATRIX: Check arco in O(1) invece di O(deg). Rimuove loop interno.
 * 2. MEMORY COMPRESSION: Uso di 'short' invece di 'int' per le mappe (2x cache efficiency).
 * 3. DYNAMIC SCHEDULING: Work stealing (invariato).
 */

#include <cuda_runtime.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h> // per memset

extern "C" {
#include "graph.h"
#include "vf2pp.h"
#include "node_ordering.h"
#include "find_candidates.h"
}

// Config Struct
typedef struct {
    int blocks;
    int threads_per_block;
    int device_id;
} VF2CudaConfig;

typedef struct {
    int cand0;
    int cand1;
} CudaJob;

#define CUDA_CHECK(call) \
    do { \
        cudaError_t err = call; \
        if (err != cudaSuccess) { \
            fprintf(stderr, "CUDA Error: %s at line %d\n", cudaGetErrorString(err), __LINE__); \
            exit(1); \
        } \
    } while(0)

// ============================================================================
// HOST HELPERS (Bitset Generation)
// ============================================================================

// Costruisce una matrice di adiacenza compressa (1 bit per arco)
// G2 è solitamente il grafo target (più grande), quindi beneficia di O(1) lookup
void build_bitset_g2(const Graph* g, unsigned int** bitset, int* pitch_ints) {
    int n = g->num_nodes;
    // Pitch allineato a 32 bit (int)
    *pitch_ints = (n + 31) / 32;
    
    size_t total_ints = (size_t)n * (*pitch_ints);
    *bitset = (unsigned int*)calloc(total_ints, sizeof(unsigned int));

    for(int i = 0; i < n; i++) {
        int deg = g->nodes[i].num_neighbors;
        for(int k = 0; k < deg; k++) {
            int neighbor = g->nodes[i].neighborhood[k];
            
            // Set bit (i, neighbor)
            // Riga i, Parola (neighbor / 32), Bit (neighbor % 32)
            int word_idx = i * (*pitch_ints) + (neighbor >> 5);
            int bit_idx  = neighbor & 31;
            
            (*bitset)[word_idx] |= (1u << bit_idx);
        }
    }
}

// ============================================================================
// DEVICE HELPER (Bitset & Cache)
// ============================================================================
// Funzione di caricamento con __ldg per accesso in sola lettura ottimizzato
__device__ __forceinline__ int load_ro(const int* ptr) {
#if __CUDA_ARCH__ >= 350
    return __ldg(ptr);
#else
    return *ptr;
#endif
}
// Versione per unsigned int (bitset)
__device__ __forceinline__ unsigned int load_ro_uint(const unsigned int* ptr) {
#if __CUDA_ARCH__ >= 350
    return __ldg(ptr);
#else
    return *ptr;
#endif
}

// Check Feasibility O(1) con Bitset
__device__ __forceinline__ bool check_feasibility_bitset(
    int u, int v, 
    const int* __restrict__ r1, const int* __restrict__ c1,
    const int* __restrict__ r2, // r2 serve solo per il grado qui
    const unsigned int* __restrict__ g2_bits, int pitch_ints,
    const short* map_g1, const short* map_g2
) {
    // 1. Check Grado (Fastest)
    int deg_u = load_ro(&r1[u+1]) - load_ro(&r1[u]);
    int deg_v = load_ro(&r2[v+1]) - load_ro(&r2[v]);
    if (deg_u > deg_v) return false;

    // 2. Check Connettività O(N_neighbors_u) * O(1)
    int start_u = load_ro(&r1[u]);
    int end_u   = load_ro(&r1[u+1]);
// Scorriamo i vicini di u in G1
    for (int i = start_u; i < end_u; i++) {
        int u_nbr = load_ro(&c1[i]);
        int v_mapped = (int)map_g1[u_nbr]; // Lettura da short, cast a int
// Se il vicino di u è mappato, controlliamo l'arco in G2
        if (v_mapped != -1) {
            // VERIFICA ESISTENZA ARCO (v, v_mapped) IN G2 TRAMITE BITSET
            // Calcolo indirizzo nella matrice bit
            int word_idx = v * pitch_ints + (v_mapped >> 5); // v_mapped / 32
            int bit_idx  = v_mapped & 31;                    // v_mapped % 32
        
            unsigned int word = load_ro_uint(&g2_bits[word_idx]);
            
            // Se il bit è 0, l'arco non esiste -> fail
            if (!((word >> bit_idx) & 1u)) {
                return false; 
            }
        }
    }
    return true;
}

// ============================================================================
// KERNEL OPTIMIZED
// ============================================================================
// Kernel principale con ottimizzazioni
__global__ void vf2_kernel_optimized(
    int n,
    const int* __restrict__ r1, const int* __restrict__ c1,
    const int* __restrict__ r2, 
    // G2 c2 rimosso dalla logica critica, sostituito da bitset
    const unsigned int* __restrict__ g2_bits, int pitch_ints,
    const CudaJob* __restrict__ jobs, int num_jobs,  
    volatile int* job_counter,
    const int* __restrict__ node_order,
    int* result_found,
    short* global_mem, // Usiamo short per risparmiare banda
    size_t stride_shorts
) {
    // Layout memoria: [MapG1] [MapG2] [LastCand] (tutti short)
    int tid_physical = blockIdx.x * blockDim.x + threadIdx.x;
    short* ptr = global_mem + (tid_physical * stride_shorts);
    
    short* map_g1    = ptr; ptr += n;
    short* map_g2    = ptr; ptr += n;
    short* last_cand = ptr;
// Inizializzazione mappe e last_cand
    while (true) {
        if (*result_found) return;

        int job_idx = atomicAdd((int*)job_counter, 1);
        if (job_idx >= num_jobs) return;

        // Reset veloce (su short invece che int = 2x bandwidth speed)
        for(int i=0; i<n; i++) {
            map_g1[i] = -1;
            map_g2[i] = -1;
            last_cand[i] = -1;
        }

        int u0 = load_ro(&node_order[0]); 
        int v0 = load_ro(&jobs[job_idx].cand0);
        int u1 = load_ro(&node_order[1]); 
        int v1 = load_ro(&jobs[job_idx].cand1);

        map_g1[u0] = (short)v0; map_g2[v0] = (short)u0;
        map_g1[u1] = (short)v1; map_g2[v1] = (short)u1;

        int level = 2;

        while (level >= 2) {
            if (*result_found) break;

            if (level == n) {
                *result_found = 1;
                break;
            }
// Ottieni nodo u da mappare
            int u = load_ro(&node_order[level]);
            int v_found = -1;

            int start_search = (int)last_cand[level] + 1;
            
            for (int v = start_search; v < n; v++) {
                // Check veloce su map_g2 (in short)
                if (map_g2[v] == -1) {
                    if (check_feasibility_bitset(u, v, r1, c1, r2, g2_bits, pitch_ints, map_g1, map_g2)) {
                        v_found = v;
                        break; 
                    }
                }
            }

            if (v_found != -1) {
                last_cand[level] = (short)v_found;
                map_g1[u] = (short)v_found;
                map_g2[v_found] = (short)u;
                level++;
                last_cand[level] = -1;
            } else {
                level--;
                if (level >= 2) {
                    int u_prev = load_ro(&node_order[level]);
                    int v_prev = (int)map_g1[u_prev];
                    map_g1[u_prev] = -1;
                    map_g2[v_prev] = -1;
                }
            }
        }
    }
}

// ============================================================================
// HOST HELPERS (Sorting - Rimane utile per G1)
// ============================================================================

int compare_ints_opt(const void* a, const void* b) {
    return (*(int*)a - *(int*)b);
}

void flatten_graph_opt(const Graph* g, int** row, int** col, int* num_edges) {
    int n = g->num_nodes;
    *num_edges = 0;
    for(int i=0; i<n; i++) *num_edges += g->nodes[i].num_neighbors;

    *row = (int*)malloc((n + 1) * sizeof(int));
    *col = (int*)malloc((*num_edges) * sizeof(int));

    int cur = 0;
    for(int i=0; i<n; i++) {
        (*row)[i] = cur;
        int deg = g->nodes[i].num_neighbors;
        for(int j=0; j<deg; j++) {
            (*col)[cur + j] = g->nodes[i].neighborhood[j];
        }
        // Ordiniamo comunque per G1 (coerenza di accesso memoria)
        qsort((*col) + cur, deg, sizeof(int), compare_ints_opt);
        cur += deg;
    }
    (*row)[n] = cur;
}

// ============================================================================
// MAIN WRAPPER
// ============================================================================

extern "C" bool vf2pp_find_isomorphism_cuda(Graph* g1, Graph* g2, VF2CudaConfig* config) {
    if (g1->num_nodes != g2->num_nodes) return false;
    if (g1->num_nodes == 0) return true;
    int n = g1->num_nodes;

    // Check limiti per short optimization
    if (n > 32766) {
        fprintf(stderr, "Error: Graph too large for short optimization (Max 32766 nodes)\n");
        return false;
    }

    // --- 1. JOB GENERATION (CPU) ---
    // (Invariata: genera i job iniziali)
    int* node_order = (int*)malloc(n * sizeof(int));
    compute_matching_order(g1, node_order);

    int capacity = 4096;
    int num_jobs = 0;
    CudaJob* h_jobs = (CudaJob*)malloc(capacity * sizeof(CudaJob));

    bool* t2 = (bool*)malloc(n * sizeof(bool));
    int* c0_buf = (int*)malloc(n * sizeof(int));
    int* c1_buf = (int*)malloc(n * sizeof(int));
    for(int i=0; i<n; i++) t2[i] = true;

    int c0_count;
    find_candidates(node_order[0], g1, g2, t2, c0_buf, &c0_count);

    for(int i=0; i<c0_count; i++) {
        int v0 = c0_buf[i];
        g1->nodes[node_order[0]].mapped = v0;
        g2->nodes[v0].mapped = node_order[0];

        int c1_count;
        find_candidates(node_order[1], g1, g2, t2, c1_buf, &c1_count);
        
        for(int j=0; j<c1_count; j++) {
            if (num_jobs >= capacity) {
                capacity *= 2;
                h_jobs = (CudaJob*)realloc(h_jobs, capacity * sizeof(CudaJob));
            }
            h_jobs[num_jobs].cand0 = v0;
            h_jobs[num_jobs].cand1 = c1_buf[j];
            num_jobs++;
        }
        g1->nodes[node_order[0]].mapped = -1;
        g2->nodes[v0].mapped = -1;
    }
    free(t2); free(c0_buf); free(c1_buf);

    if (num_jobs == 0) {
        free(node_order); free(h_jobs);
        return false;
    }

    // --- 2. GPU SETUP ---
    cudaSetDevice(config->device_id);

    // Flatten G1 (CSR standard)
    int *h_r1, *h_c1, e1;
    flatten_graph_opt(g1, &h_r1, &h_c1, &e1);

    // Flatten G2:
    // Ci serve r2 per i gradi
    int *h_r2, *dummy_c2, e2;
    flatten_graph_opt(g2, &h_r2, &dummy_c2, &e2); // dummy_c2 non verrà usato nel kernel per check
    free(dummy_c2); // Possiamo liberarlo, useremo il bitset

    // Generazione BITSET per G2
    unsigned int* h_g2_bits;
    int pitch_ints;
    build_bitset_g2(g2, &h_g2_bits, &pitch_ints);

    int *d_r1, *d_c1, *d_r2, *d_order, *d_res, *d_job_counter;
    unsigned int *d_g2_bits;
    CudaJob* d_jobs;

    CUDA_CHECK(cudaMalloc(&d_r1, (n+1)*sizeof(int)));
    CUDA_CHECK(cudaMalloc(&d_c1, e1*sizeof(int)));
    CUDA_CHECK(cudaMalloc(&d_r2, (n+1)*sizeof(int)));
    CUDA_CHECK(cudaMalloc(&d_g2_bits, n * pitch_ints * sizeof(unsigned int))); // Alloc bitset
    CUDA_CHECK(cudaMalloc(&d_order, n*sizeof(int)));
    CUDA_CHECK(cudaMalloc(&d_jobs, num_jobs*sizeof(CudaJob)));
    CUDA_CHECK(cudaMalloc(&d_res, sizeof(int)));
    CUDA_CHECK(cudaMalloc(&d_job_counter, sizeof(int)));

    CUDA_CHECK(cudaMemcpy(d_r1, h_r1, (n+1)*sizeof(int), cudaMemcpyHostToDevice));
    CUDA_CHECK(cudaMemcpy(d_c1, h_c1, e1*sizeof(int), cudaMemcpyHostToDevice));
    CUDA_CHECK(cudaMemcpy(d_r2, h_r2, (n+1)*sizeof(int), cudaMemcpyHostToDevice));
    CUDA_CHECK(cudaMemcpy(d_g2_bits, h_g2_bits, n * pitch_ints * sizeof(unsigned int), cudaMemcpyHostToDevice));
    CUDA_CHECK(cudaMemcpy(d_order, node_order, n*sizeof(int), cudaMemcpyHostToDevice));
    CUDA_CHECK(cudaMemcpy(d_jobs, h_jobs, num_jobs*sizeof(CudaJob), cudaMemcpyHostToDevice));
    CUDA_CHECK(cudaMemset(d_res, 0, sizeof(int)));
    CUDA_CHECK(cudaMemset(d_job_counter, 0, sizeof(int)));

    // --- 3. MEMORY POOL (SHORT) ---
    int threads_per_blk = (config->threads_per_block > 0) ? config->threads_per_block : 256;
    int blocks = (config->blocks > 0) ? config->blocks : 128; 
    
    int total_physical_threads = blocks * threads_per_blk;
    
    // 3 vettori da N per ogni thread fisico, ma ora sono SHORT (2 byte)
    size_t shorts_per_thread = (size_t)3 * n; 
    short* d_pool;
    size_t pool_bytes = total_physical_threads * shorts_per_thread * sizeof(short);
    
    // Check memoria (ora è molto più difficile finire la memoria grazie a short)
    size_t free_mem, total_mem;
    cudaMemGetInfo(&free_mem, &total_mem);
    if (pool_bytes > free_mem * 0.95) {
        printf("WARN: Reducing concurrency to fit memory (even with short opt).\n");
        total_physical_threads = (free_mem * 0.95) / (shorts_per_thread * sizeof(short));
        blocks = total_physical_threads / threads_per_blk;
        pool_bytes = total_physical_threads * shorts_per_thread * sizeof(short);
    }
    CUDA_CHECK(cudaMalloc(&d_pool, pool_bytes));

    // --- 4. LAUNCH ---
    vf2_kernel_optimized<<<blocks, threads_per_blk>>>(
        n, d_r1, d_c1, d_r2, 
        d_g2_bits, pitch_ints, // Passiamo il bitset
        d_jobs, num_jobs,
        d_job_counter,
        d_order,
        d_res, d_pool, shorts_per_thread
    );
    CUDA_CHECK(cudaDeviceSynchronize());

    int h_res;
    CUDA_CHECK(cudaMemcpy(&h_res, d_res, sizeof(int), cudaMemcpyDeviceToHost));

    // Cleanup
    cudaFree(d_r1); cudaFree(d_c1); cudaFree(d_r2); 
    cudaFree(d_g2_bits); // Free bitset
    cudaFree(d_order); cudaFree(d_jobs); cudaFree(d_res); cudaFree(d_pool); cudaFree(d_job_counter);
    free(h_r1); free(h_c1); free(h_r2); 
    free(h_g2_bits); // Free bitset host
    free(node_order); free(h_jobs);

    return (h_res > 0);
}