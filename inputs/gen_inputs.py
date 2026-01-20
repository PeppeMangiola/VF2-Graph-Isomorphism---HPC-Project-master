#!/usr/bin/env python3
"""
VF2++ Graph Isomorphism - Graph Generator (HARD VERSION)
HPC Project

Genera grafi per stress-test:
1. Isomorfi: Permutazione casuale.
2. Non Isomorfi (Hard): Stesso numero di nodi e archi, ma struttura leggermente alterata.

USO:
    python gen_inputs.py [seed]
"""

import os
import sys
import random
import networkx as nx
from typing import Tuple

# ============================================================================
# CONFIGURAZIONE
# ============================================================================

DEFAULT_SEED = 12345

SIZEOF_GRAPH = 16
SIZEOF_NODE = 24
SIZEOF_INT = 4

# Configurazioni calibrate per RAM target + tempi ragionevoli
# (name, target_bytes, num_nodes, target_degree)
SIZE_CONFIGS = [
    ("1MB",   1 * 1024 * 1024,    1200,  100),
    ("50MB",  50 * 1024 * 1024,   10000, 300),
    ("100MB", 100 * 1024 * 1024,  15000, 400),
    ("200MB", 200 * 1024 * 1024,  20000, 500),
    ("500MB", 500 * 1024 * 1024,  30000, 800),
]

# ============================================================================
# FUNZIONI UTILI
# ============================================================================

def calculate_ram_usage(num_nodes: int, num_edges: int) -> int:
    return SIZEOF_GRAPH + num_nodes * SIZEOF_NODE + num_edges * 2 * SIZEOF_INT


def calculate_edges_for_ram(target_ram: int, num_nodes: int) -> int:
    """Calcola quanti archi servono per raggiungere target_ram con num_nodes fisso."""
    edges = (target_ram - SIZEOF_GRAPH - num_nodes * SIZEOF_NODE) // (2 * SIZEOF_INT)
    max_edges = num_nodes * (num_nodes - 1) // 2
    if edges > max_edges:
        edges = max_edges
    return max(0, edges)


def format_size(size_bytes: int) -> str:
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    elif size_bytes >= 1024:
        return f"{size_bytes / 1024:.2f} KB"
    return f"{size_bytes} B"


def generate_graph(num_nodes: int, num_edges: int, seed: int) -> nx.Graph:
    """Genera grafo casuale."""
    if num_nodes < 2:
        return nx.empty_graph(num_nodes)
    
    max_edges = num_nodes * (num_nodes - 1) // 2
    actual_edges = min(num_edges, max_edges)
    
    print(f"      Generando base: {num_nodes} nodi, {actual_edges} archi...", end=" ", flush=True)
    G = nx.gnm_random_graph(num_nodes, actual_edges, seed=seed)
    print("OK", flush=True)
    return G


def save_graph_fast(G: nx.Graph, filepath: str):
    """Salva grafo in formato VF2++."""
    N = G.number_of_nodes()
    M = G.number_of_edges()
    
    print(f"      Salvando {filepath}...", end=" ", flush=True)
    with open(filepath, 'w', buffering=4*1024*1024) as f:
        f.write(f"{N} {M}\n")
        for node in range(N):
            neighbors = sorted(G.neighbors(node))
            if neighbors:
                f.write(f"{node}\t{' '.join(map(str, neighbors))}\n")
            else:
                f.write(f"{node}\n")
    print("OK", flush=True)


def generate_isomorphic_copy(G: nx.Graph, seed: int) -> Tuple[nx.Graph, dict]:
    """Genera copia isomorfa con permutazione random."""
    random.seed(seed)
    nodes = list(range(G.number_of_nodes()))
    perm = nodes.copy()
    random.shuffle(perm)
    
    mapping = {old: new for new, old in enumerate(perm)}
    G2 = nx.relabel_nodes(G, mapping)
    perm_dict = {new: old for old, new in mapping.items()}
    return G2, perm_dict

def perturb_graph_preserving_stats(G: nx.Graph, num_swaps: int, seed: int) -> nx.Graph:
    """
    Modifica il grafo preservando ESATTAMENTE numero di nodi e archi.
    OTTIMIZZATA: Usa Swap-and-Pop per rimozione O(1).
    """
    random.seed(seed)
    G_mod = G.copy()
    
    # Convertiamo in lista per accesso rapido
    edges = list(G_mod.edges())
    num_nodes = G_mod.number_of_nodes()
    
    swaps_done = 0
    attempts = 0
    max_attempts = num_swaps * 100 
    
    print(f"      Applicando {num_swaps} modifiche strutturali (Fast Rewire)...", end=" ", flush=True)
    
    while swaps_done < num_swaps and attempts < max_attempts:
        attempts += 1
        
        # 1. Scegli un INDICE a caso (invece che un elemento)
        if not edges: break
        idx = random.randrange(len(edges))
        u, v = edges[idx]
        
        # 2. Scegli coppia non collegata
        x = random.randint(0, num_nodes - 1)
        y = random.randint(0, num_nodes - 1)
        
        if x != y and not G_mod.has_edge(x, y):
            # Esegui scambio nel grafo
            G_mod.remove_edge(u, v)
            G_mod.add_edge(x, y)
            
            # --- TRUCCO DI OTTIMIZZAZIONE (Swap & Pop) ---
            # Invece di edges.remove((u,v)) che è lento:
            # 1. Sovrascrivi l'arco corrente con l'ultimo della lista
            last_edge = edges[-1]
            edges[idx] = last_edge
            
            # 2. Rimuovi l'ultimo (istantaneo)
            edges.pop()
            
            # 3. Aggiungi il nuovo arco
            edges.append((x, y))
            # ---------------------------------------------
            
            swaps_done += 1
            
    print(f"Fatto ({swaps_done} swaps)", flush=True)
    return G_mod


def save_permutation(perm_dict: dict, filepath: str):
    with open(filepath, 'w') as f:
        for new_id in sorted(perm_dict.keys()):
            f.write(f"{new_id} {perm_dict[new_id]}\n")


# ============================================================================
# MAIN
# ============================================================================

def main():
    seed = DEFAULT_SEED
    if len(sys.argv) > 1:
        try:
            seed = int(sys.argv[1])
        except ValueError:
            pass
    
    print("=" * 60)
    print("VF2++ HARD Graph Generator")
    print("=" * 60)
    print(f"Seed: {seed}")
    print()
    
    os.makedirs("inputs", exist_ok=True)
    
    with open("inputs/manifest.txt", 'w') as manifest:
        manifest.write(f"# VF2++ Test Inputs Manifest (Hard Mode)\n")
        manifest.write(f"# Seed: {seed}\n")
        manifest.write("# name,g1,g2,nodes,edges,degree,target_ram,actual_ram,isomorphic\n\n")
        
        for name, target_bytes, num_nodes, target_degree in SIZE_CONFIGS:
            single_target = target_bytes // 2
            num_edges = calculate_edges_for_ram(single_target, num_nodes)
            
            print("=" * 60)
            print(f"[{name}] Target: {format_size(target_bytes)}")
            
            # === ISOMORFI ===
            g1_iso = f"inputs/{name}_iso_g1.txt"
            g2_iso = f"inputs/{name}_iso_g2.txt"
            perm_path = f"inputs/{name}_iso_permutation.txt"
            
            print(f"  [1/2] Coppia ISOMORFA:")
            G1 = generate_graph(num_nodes, num_edges, seed=seed)
            actual_edges = G1.number_of_edges()
            actual_ram = calculate_ram_usage(num_nodes, actual_edges)
            actual_degree = (2 * actual_edges) / num_nodes if num_nodes > 0 else 0
            
            save_graph_fast(G1, g1_iso)
            G2, perm = generate_isomorphic_copy(G1, seed=seed+1)
            save_graph_fast(G2, g2_iso)
            save_permutation(perm, perm_path)
            
            manifest.write(f"{name}_iso,{g1_iso},{g2_iso},{num_nodes},{actual_edges},{actual_degree:.1f},{target_bytes},{actual_ram*2},1\n")
            del G2
            
            # === NON ISOMORFI (HARD) ===
            g1_diff = f"inputs/{name}_diff_g1.txt"
            g2_diff = f"inputs/{name}_diff_g2.txt"
            
            print(f"  [2/2] Coppia NON ISOMORFA (HARD - Stessi archi):")
            
            # Salviamo G1 (lo stesso di prima)
            save_graph_fast(G1, g1_diff)
            
            # Generiamo G2 partendo da G1, permutandolo E modificandolo
            # 1. Permutazione (così i nodi hanno ID diversi)
            G2_temp, _ = generate_isomorphic_copy(G1, seed=seed+200)
            
            # 2. Perturbazione (Rewiring): Cambio il 5% degli archi
            num_swaps = max(1, int(actual_edges * 0.05))
            G2_diff = perturb_graph_preserving_stats(G2_temp, num_swaps, seed=seed+300)
            
            # Verifica che il numero di archi sia identico
            edges2 = G2_diff.number_of_edges()
            assert actual_edges == edges2, "Errore: numero archi cambiato!"
            
            save_graph_fast(G2_diff, g2_diff)
            
            print(f"      G1: {actual_edges} archi")
            print(f"      G2: {edges2} archi (modificati {num_swaps})")
            
            manifest.write(f"{name}_diff,{g1_diff},{g2_diff},{num_nodes},{actual_edges}/{edges2},{actual_degree:.1f}/{actual_degree:.1f},{target_bytes},{actual_ram*2},0\n")
            
            del G1
            del G2_temp
            del G2_diff
            print()
    
    print("=" * 60)
    print("GENERAZIONE COMPLETATA!")

if __name__ == "__main__":
    main()