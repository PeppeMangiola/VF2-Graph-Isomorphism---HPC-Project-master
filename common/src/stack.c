/*
 * VF2++ Graph Isomorphism - Stack Implementation
 * HPC Project
 */

#include "stack.h"
#include <string.h>

#define STACK_INITIAL_CAPACITY 16

/* ============================================================================
 * IMPLEMENTAZIONE FUNZIONI STACK
 * ============================================================================ */

int stack_init(Stack* stack) {
    return stack_init_with_capacity(stack, STACK_INITIAL_CAPACITY);
}

int stack_init_with_capacity(Stack* stack, int initial_capacity) {
    if (stack == NULL || initial_capacity <= 0) {
        return -1;
    }
    
    stack->elements = (StackElement*)malloc(initial_capacity * sizeof(StackElement));
    if (stack->elements == NULL) {
        fprintf(stderr, "stack_init: malloc fallito\n");
        return -1;
    }
    
    stack->top = -1;
    stack->capacity = initial_capacity;
    
    /* Inizializza elementi a zero per sicurezza */
    memset(stack->elements, 0, initial_capacity * sizeof(StackElement));
    
    return 0;
}

void stack_free(Stack* stack) {
    if (stack == NULL) {
        return;
    }
    
    /* Libera tutti gli elementi ancora nello stack */
    for (int i = 0; i <= stack->top; i++) {
        if (stack->elements[i].candidates != NULL) {
            free(stack->elements[i].candidates);
        }
        if (stack->elements[i].flags != NULL) {
            free(stack->elements[i].flags);
        }
    }
    
    if (stack->elements != NULL) {
        free(stack->elements);
        stack->elements = NULL;
    }
    
    stack->top = -1;
    stack->capacity = 0;
}

void stack_reset(Stack* stack) {
    if (stack == NULL) {
        return;
    }
    
    /* Libera elementi ma mantieni l'array */
    for (int i = 0; i <= stack->top; i++) {
        if (stack->elements[i].candidates != NULL) {
            free(stack->elements[i].candidates);
            stack->elements[i].candidates = NULL;
        }
        if (stack->elements[i].flags != NULL) {
            free(stack->elements[i].flags);
            stack->elements[i].flags = NULL;
        }
    }
    
    stack->top = -1;
}

/**
 * Ridimensiona lo stack (interno)
 */
static int stack_resize(Stack* stack, int new_capacity) {
    StackElement* new_elements = (StackElement*)realloc(
        stack->elements, 
        new_capacity * sizeof(StackElement)
    );
    
    if (new_elements == NULL) {
        fprintf(stderr, "stack_resize: realloc fallito\n");
        return -1;
    }
    
    stack->elements = new_elements;
    stack->capacity = new_capacity;
    
    return 0;
}

int stack_push(Stack* stack, int node, const int* candidates, int num_candidates) {
    if (stack == NULL) {
        return -1;
    }
    
    /* Espandi se necessario */
    if (stack->top >= stack->capacity - 1) {
        if (stack_resize(stack, stack->capacity * 2) != 0) {
            return -1;
        }
    }
    
    stack->top++;
    StackElement* elem = &stack->elements[stack->top];
    
    elem->node = node;
    elem->num_candidates = num_candidates;
    elem->current_idx = 0;
    
    if (num_candidates > 0 && candidates != NULL) {
        /* Alloca e copia candidati */
        elem->candidates = (int*)malloc(num_candidates * sizeof(int));
        if (elem->candidates == NULL) {
            stack->top--;
            return -1;
        }
        memcpy(elem->candidates, candidates, num_candidates * sizeof(int));
        
        /* Alloca e inizializza flags */
        elem->flags = (bool*)malloc(num_candidates * sizeof(bool));
        if (elem->flags == NULL) {
            free(elem->candidates);
            elem->candidates = NULL;
            stack->top--;
            return -1;
        }
        memset(elem->flags, 0, num_candidates * sizeof(bool));  /* tutti false */
    } else {
        elem->candidates = NULL;
        elem->flags = NULL;
    }
    
    return 0;
}

int stack_pop(Stack* stack) {
    if (stack == NULL || stack->top < 0) {
        return -1;
    }
    
    StackElement* elem = &stack->elements[stack->top];
    
    /* Libera memoria dell'elemento */
    if (elem->candidates != NULL) {
        free(elem->candidates);
        elem->candidates = NULL;
    }
    if (elem->flags != NULL) {
        free(elem->flags);
        elem->flags = NULL;
    }
    
    stack->top--;
    
    /* Shrink se molto sottoutilizzato (opzionale, per efficienza memoria) */
    if (stack->top < stack->capacity / 4 && stack->capacity > STACK_INITIAL_CAPACITY) {
        stack_resize(stack, stack->capacity / 2);
    }
    
    return 0;
}

StackElement* stack_peek(Stack* stack) {
    if (stack == NULL || stack->top < 0) {
        return NULL;
    }
    
    return &stack->elements[stack->top];
}

bool stack_is_empty(const Stack* stack) {
    return (stack == NULL || stack->top < 0);
}

int stack_size(const Stack* stack) {
    if (stack == NULL) {
        return 0;
    }
    return stack->top + 1;
}
