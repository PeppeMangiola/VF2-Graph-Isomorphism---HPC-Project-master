/*
 * VF2++ Graph Isomorphism - Find Candidates Implementation
 * HPC Project
 */

#include "find_candidates.h"
#include <stdlib.h>
#include <string.h>

/* ============================================================================
 * FUNZIONI HELPER
 * ============================================================================ */

/**
 * Comparatore per ordinare nodi per grado (crescente)
 */
static int compare_nodes_by_degree(const void* a, const void* b) {
    const Node* na = (const Node*)a;
    const Node* nb = (const Node*)b;
    return na->num_neighbors - nb->num_neighbors;
}

/**
 * Verifica se un valore è presente in un array
 */
static bool array_contains(const int* arr, int size, int val) {
    for (int i = 0; i < size; i++) {
        if (arr[i] == val) return true;
    }
    return false;
}

/* ============================================================================
 * IMPLEMENTAZIONE PRINCIPALE
 * ============================================================================ */

int find_candidates(int u, const Graph* g1, const Graph* g2, 
                    const bool* t2_tilde,
                    int* out_candidates, int* out_num_candidates) {
    
    if (g1 == NULL || g2 == NULL || t2_tilde == NULL || 
        out_candidates == NULL || out_num_candidates == NULL) {
        return -1;
    }
    
    if (u < 0 || u >= g1->num_nodes) {
        return -1;
    }
    
    *out_num_candidates = 0;
    
    const Node* u_node = &g1->nodes[u];
    int u_degree = u_node->num_neighbors;
    
    /* Trova i vicini di u che sono già mappati (covered neighbors) */
    Node* covered_neighbors = NULL;
    int num_covered = 0;
    
    if (u_node->num_neighbors > 0) {
        covered_neighbors = (Node*)malloc(u_node->num_neighbors * sizeof(Node));
        if (covered_neighbors == NULL) return -1;
        
        for (int i = 0; i < u_node->num_neighbors; i++) {
            int nbr = u_node->neighborhood[i];
            int mapping = g1->nodes[nbr].mapped;
            
            if (mapping != -1) {
                /* Copia le info del nodo mappato in G2 */
                covered_neighbors[num_covered] = g2->nodes[mapping];
                num_covered++;
            }
        }
    }
    
    /* CASO 1: Nessun vicino di u è già mappato */
    if (num_covered == 0) {
        /* I candidati sono tutti i nodi non mappati in T2_tilde con stesso grado */
        for (int v = 0; v < g2->num_nodes; v++) {
            if (g2->nodes[v].mapped == -1 && 
                t2_tilde[v] && 
                g2->nodes[v].num_neighbors == u_degree) {
                out_candidates[(*out_num_candidates)++] = v;
            }
        }
        
        if (covered_neighbors) free(covered_neighbors);
        return 0;
    }
    
    /* CASO 2: Un solo vicino di u è mappato */
    if (num_covered == 1) {
        /* I candidati sono i vicini del nodo mappato con stesso grado */
        Node* mapped_neighbor = &covered_neighbors[0];
        
        for (int i = 0; i < mapped_neighbor->num_neighbors; i++) {
            int v = mapped_neighbor->neighborhood[i];
            
            if (g2->nodes[v].mapped == -1 && 
                g2->nodes[v].num_neighbors == u_degree) {
                out_candidates[(*out_num_candidates)++] = v;
            }
        }
        
        free(covered_neighbors);
        return 0;
    }
    
    /* CASO 3: Più vicini di u sono mappati */
    /* I candidati devono essere vicini di TUTTI i nodi mappati */
    
    /* Ordina covered_neighbors per grado crescente (ottimizzazione) */
    qsort(covered_neighbors, num_covered, sizeof(Node), compare_nodes_by_degree);
    
    /* Parti dai vicini del nodo con meno vicini (primo dopo l'ordinamento) */
    Node* smallest = &covered_neighbors[0];
    
    for (int i = 0; i < smallest->num_neighbors; i++) {
        int v = smallest->neighborhood[i];
        
        /* Verifica vincoli base */
        if (g2->nodes[v].mapped != -1) continue;
        if (g2->nodes[v].num_neighbors != u_degree) continue;
        
        /* Verifica che v sia vicino di tutti gli altri covered neighbors */
        bool valid = true;
        
        for (int j = 1; j < num_covered && valid; j++) {
            Node* other = &covered_neighbors[j];
            
            /* Cerca v tra i vicini di other */
            bool found = false;
            for (int k = 0; k < other->num_neighbors; k++) {
                if (other->neighborhood[k] == v) {
                    found = true;
                    break;
                }
            }
            
            if (!found) {
                valid = false;
            }
        }
        
        if (valid) {
            out_candidates[(*out_num_candidates)++] = v;
        }
    }
    
    free(covered_neighbors);
    return 0;
}

int* find_candidates_alloc(int u, const Graph* g1, const Graph* g2,
                           const bool* t2_tilde, int* out_num_candidates) {
    
    if (g2 == NULL || out_num_candidates == NULL) {
        return NULL;
    }
    
    /* Alloca buffer temporaneo (max possibili = tutti i nodi di G2) */
    int* temp = (int*)malloc(g2->num_nodes * sizeof(int));
    if (temp == NULL) return NULL;
    
    if (find_candidates(u, g1, g2, t2_tilde, temp, out_num_candidates) != 0) {
        free(temp);
        return NULL;
    }
    
    if (*out_num_candidates == 0) {
        free(temp);
        return NULL;
    }
    
    /* Ridimensiona all'esatto numero di candidati */
    int* result = (int*)realloc(temp, (*out_num_candidates) * sizeof(int));
    if (result == NULL) {
        /* realloc fallito, ma temp è ancora valido */
        return temp;
    }
    
    return result;
}

void update_t2_tilde(const Graph* g2, int mapped_node, bool* t2_tilde) {
    if (g2 == NULL || t2_tilde == NULL) return;
    if (mapped_node < 0 || mapped_node >= g2->num_nodes) return;
    
    /* Il nodo mappato non è più nella frontier */
    t2_tilde[mapped_node] = false;
    
    /* I vicini non mappati potrebbero uscire dalla frontier 
       (se non hanno più nessun vicino mappato) */
    /* In realtà in VF2++ i vicini ENTRANO nella frontier, non escono */
    /* Ma qui il comportamento è: rimuovi dalla frontier tutti i vicini del nodo mappato */
    for (int i = 0; i < g2->nodes[mapped_node].num_neighbors; i++) {
        int nbr = g2->nodes[mapped_node].neighborhood[i];
        /* I vicini vengono rimossi dalla T2_tilde "libera" 
           (saranno considerati solo se sono vicini di nodi mappati) */
        t2_tilde[nbr] = false;
    }
}

void restore_t2_tilde(const Graph* g2, int unmapped_node, bool* t2_tilde) {
    if (g2 == NULL || t2_tilde == NULL) return;
    if (unmapped_node < 0 || unmapped_node >= g2->num_nodes) return;
    
    /* Ripristina la frontier dopo backtrack */
    bool has_mapped_neighbor = false;
    
    /* Controlla se unmapped_node ha ancora vicini mappati */
    for (int i = 0; i < g2->nodes[unmapped_node].num_neighbors; i++) {
        int nbr = g2->nodes[unmapped_node].neighborhood[i];
        if (g2->nodes[nbr].mapped != -1) {
            has_mapped_neighbor = true;
            break;
        }
    }
    
    /* Se non ha più vicini mappati, torna nella frontier "libera" */
    if (!has_mapped_neighbor) {
        t2_tilde[unmapped_node] = true;
    }
    
    /* Ripristina i vicini che potrebbero tornare nella frontier */
    for (int i = 0; i < g2->nodes[unmapped_node].num_neighbors; i++) {
        int nbr = g2->nodes[unmapped_node].neighborhood[i];
        
        if (g2->nodes[nbr].mapped == -1) {
            /* Controlla se nbr ha ancora altri vicini mappati */
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
