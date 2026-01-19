/*
 * VF2++ Graph Isomorphism - Graph I/O Implementation
 * HPC Project
 */

#include "graph_io.h"
#include <string.h>
#include <ctype.h>
#include <errno.h>

/* ============================================================================
 * FUNZIONI HELPER INTERNE
 * ============================================================================ */

/**
 * Parsa una riga del file grafo
 * Formato: <node_id>\t<neighbor1> <neighbor2> ...
 */
static int parse_line(Graph* g, char* line) {
    /* Rimuovi newline */
    size_t len = strlen(line);
    if (len > 0 && line[len - 1] == '\n') {
        line[len - 1] = '\0';
        len--;
    }
    if (len > 0 && line[len - 1] == '\r') {
        line[len - 1] = '\0';
        len--;
    }
    
    /* Trova il tab separatore */
    char* tab_pos = strchr(line, '\t');
    if (tab_pos == NULL) {
        /* Nodo senza vicini */
        int node_id;
        if (sscanf(line, "%d", &node_id) != 1) {
            return -1;
        }
        if (node_id < 0 || node_id >= g->num_nodes) {
            return -1;
        }
        /* Nessun vicino da settare */
        return 0;
    }
    
    /* Parsa node_id */
    *tab_pos = '\0';
    int node_id;
    if (sscanf(line, "%d", &node_id) != 1) {
        return -1;
    }
    if (node_id < 0 || node_id >= g->num_nodes) {
        fprintf(stderr, "parse_line: node_id %d fuori range [0, %d)\n", 
                node_id, g->num_nodes);
        return -1;
    }
    
    /* Parsa vicini */
    char* neighbors_str = tab_pos + 1;
    
    int* temp_neighbors = (int*)malloc(GRAPH_IO_MAX_NEIGHBORS * sizeof(int));
    if (temp_neighbors == NULL) {
        return -1;
    }
    
    int num_neighbors = 0;
    char* token = strtok(neighbors_str, " ");
    
    while (token != NULL && num_neighbors < GRAPH_IO_MAX_NEIGHBORS) {
        /* Salta spazi bianchi iniziali */
        while (*token && isspace((unsigned char)*token)) {
            token++;
        }
        if (*token == '\0') {
            token = strtok(NULL, " ");
            continue;
        }
        
        char* endptr;
        errno = 0;
        long val = strtol(token, &endptr, 10);
        
        if (errno != 0 || endptr == token) {
            token = strtok(NULL, " ");
            continue;
        }
        
        /* Verifica range */
        if (val >= 0 && val < g->num_nodes) {
            temp_neighbors[num_neighbors++] = (int)val;
        }
        
        token = strtok(NULL, " ");
    }
    
    /* Setta i vicini */
    int result = graph_set_neighbors(g, node_id, temp_neighbors, num_neighbors);
    
    free(temp_neighbors);
    return result;
}

/* ============================================================================
 * IMPLEMENTAZIONE FUNZIONI I/O
 * ============================================================================ */

Graph* graph_read_from_file(const char* filename) {
    if (filename == NULL) {
        fprintf(stderr, "graph_read_from_file: filename NULL\n");
        return NULL;
    }
    
    FILE* file = fopen(filename, "r");
    if (file == NULL) {
        fprintf(stderr, "graph_read_from_file: impossibile aprire '%s': %s\n", 
                filename, strerror(errno));
        return NULL;
    }
    
    /* Leggi prima riga: num_nodes num_edges */
    char first_line[64];
    if (fgets(first_line, sizeof(first_line), file) == NULL) {
        fprintf(stderr, "graph_read_from_file: file vuoto\n");
        fclose(file);
        return NULL;
    }
    
    int num_nodes, num_edges;
    if (sscanf(first_line, "%d %d", &num_nodes, &num_edges) != 2) {
        fprintf(stderr, "graph_read_from_file: formato prima riga invalido\n");
        fclose(file);
        return NULL;
    }
    
    /* Crea grafo */
    Graph* g = graph_create(num_nodes);
    if (g == NULL) {
        fclose(file);
        return NULL;
    }
    
    /* Leggi righe successive */
    char* line = (char*)malloc(GRAPH_IO_MAX_LINE_LENGTH);
    if (line == NULL) {
        graph_free(g);
        fclose(file);
        return NULL;
    }
    
    while (fgets(line, GRAPH_IO_MAX_LINE_LENGTH, file) != NULL) {
        /* Salta righe vuote */
        if (line[0] == '\n' || line[0] == '\r' || line[0] == '\0') {
            continue;
        }
        
        if (parse_line(g, line) != 0) {
            /* Errore parsing, ma continua */
        }
    }
    
    free(line);
    fclose(file);
    
    return g;
}

int graph_write_to_file(const Graph* g, const char* filename) {
    if (g == NULL || filename == NULL) {
        return -1;
    }
    
    FILE* file = fopen(filename, "w");
    if (file == NULL) {
        fprintf(stderr, "graph_write_to_file: impossibile aprire '%s': %s\n",
                filename, strerror(errno));
        return -1;
    }
    
    /* Scrivi header */
    fprintf(file, "%d %d\n", g->num_nodes, g->num_edges / 2);  /* num_edges/2 per grafi non diretti */
    
    /* Scrivi ogni nodo con i suoi vicini */
    for (int i = 0; i < g->num_nodes; i++) {
        fprintf(file, "%d", i);
        
        if (g->nodes[i].num_neighbors > 0) {
            fprintf(file, "\t");
            for (int j = 0; j < g->nodes[i].num_neighbors; j++) {
                if (j > 0) {
                    fprintf(file, " ");
                }
                fprintf(file, "%d", g->nodes[i].neighborhood[j]);
            }
        }
        fprintf(file, "\n");
    }
    
    fclose(file);
    return 0;
}

Graph* graph_read_from_buffer(const char* buffer, size_t size) {
    if (buffer == NULL || size == 0) {
        return NULL;
    }
    
    /* Copia buffer per poterlo modificare */
    char* buf_copy = (char*)malloc(size + 1);
    if (buf_copy == NULL) {
        return NULL;
    }
    memcpy(buf_copy, buffer, size);
    buf_copy[size] = '\0';
    
    /* Trova prima riga */
    char* line_end = strchr(buf_copy, '\n');
    if (line_end == NULL) {
        free(buf_copy);
        return NULL;
    }
    *line_end = '\0';
    
    int num_nodes, num_edges;
    if (sscanf(buf_copy, "%d %d", &num_nodes, &num_edges) != 2) {
        free(buf_copy);
        return NULL;
    }
    
    Graph* g = graph_create(num_nodes);
    if (g == NULL) {
        free(buf_copy);
        return NULL;
    }
    
    /* Parsa righe successive */
    char* current = line_end + 1;
    char* buf_end = buf_copy + size;
    
    while (current < buf_end) {
        /* Trova fine riga */
        char* next_line = strchr(current, '\n');
        if (next_line != NULL) {
            *next_line = '\0';
        }
        
        if (*current != '\0' && *current != '\r') {
            parse_line(g, current);
        }
        
        if (next_line == NULL) {
            break;
        }
        current = next_line + 1;
    }
    
    free(buf_copy);
    return g;
}
