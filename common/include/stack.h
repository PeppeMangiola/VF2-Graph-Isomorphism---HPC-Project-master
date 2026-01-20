/*
 * VF2++ Graph Isomorphism - Stack per Backtracking
 * HPC Project
 * 
 * Stack dinamico per gestire lo stato del matching durante il backtracking
 */

#ifndef VF2PP_STACK_H
#define VF2PP_STACK_H

#include <stdbool.h>
#include <stdlib.h>
#include <stdio.h>

/* ============================================================================
 * STRUTTURE DATI
 * ============================================================================ */

/**
 * Elemento dello stack: rappresenta un nodo di G1 con i suoi candidati in G2
 * - node: ID del nodo di G1 da mappare
 * - candidates: array di ID dei nodi candidati in G2
 * - num_candidates: numero di candidati
 * - flags: array booleano, flags[i] = true se candidates[i] è già stato provato
 * - current_idx: indice del prossimo candidato da provare (ottimizzazione)
 */
typedef struct {
    int   node;
    int*  candidates;
    int   num_candidates;
    bool* flags;
    int   current_idx;
} StackElement;

/**
 * Stack dinamico con ridimensionamento automatico
 * - elements: array di elementi
 * - top: indice del top (-1 se vuoto)
 * - capacity: capacità corrente
 */
typedef struct {
    StackElement* elements;
    int           top;
    int           capacity;
} Stack;

/* ============================================================================
 * FUNZIONI STACK
 * ============================================================================ */

/**
 * Inizializza uno stack vuoto
 * @param stack Puntatore allo stack da inizializzare
 * @return 0 se successo, -1 se errore
 */
int stack_init(Stack* stack);

/**
 * Inizializza uno stack con capacità specifica
 * @param stack Puntatore allo stack
 * @param initial_capacity Capacità iniziale
 * @return 0 se successo, -1 se errore
 */
int stack_init_with_capacity(Stack* stack, int initial_capacity);

/**
 * Libera la memoria dello stack (inclusi tutti gli elementi)
 * @param stack Puntatore allo stack
 */
void stack_free(Stack* stack);

/**
 * Resetta lo stack senza deallocare (per riuso)
 * @param stack Puntatore allo stack
 */
void stack_reset(Stack* stack);

/**
 * Push di un nuovo elemento
 * NOTA: candidates e flags vengono COPIATI, il chiamante può liberarli dopo
 * @param stack Stack
 * @param node ID del nodo di G1
 * @param candidates Array di candidati
 * @param num_candidates Numero di candidati
 * @return 0 se successo, -1 se errore
 */
int stack_push(Stack* stack, int node, const int* candidates, int num_candidates);

/**
 * Pop dell'elemento in cima (libera la memoria dell'elemento)
 * @param stack Stack
 * @return 0 se successo, -1 se stack vuoto
 */
int stack_pop(Stack* stack);

void stack_clear(Stack* s);
/**
 * Restituisce puntatore all'elemento in cima senza rimuoverlo
 * @param stack Stack
 * @return Puntatore all'elemento, NULL se stack vuoto
 */
StackElement* stack_peek(Stack* stack);

/**
 * Controlla se lo stack è vuoto
 * @param stack Stack
 * @return true se vuoto, false altrimenti
 */
bool stack_is_empty(const Stack* stack);

/**
 * Restituisce il numero di elementi nello stack
 * @param stack Stack
 * @return Numero di elementi
 */
int stack_size(const Stack* stack);

#endif /* VF2PP_STACK_H */
