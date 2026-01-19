#!/usr/bin/env python3
"""
VF2++ Graph Isomorphism - Graph Generator
HPC Project

Target RAM rispettati con tempi di esecuzione ragionevoli.

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
# FUNZIONI
# ============================================================================

def calculate_ram_usage(num_nodes: int, num_edges: int) -> int:
    return SIZEOF_GRAPH + num_nodes * SIZEOF_NODE + num_edges * 2 * SIZEOF_INT


def calculate_edges_for_ram(target_ram: int, num_nodes: int) -> int:
    """Calcola quanti archi servono per raggiungere target_ram con num_nodes fisso."""
    # RAM = 16 + N*24 + E*8
    # E = (RAM - 16 - N*24) / 8
    edges = (target_ram - SIZEOF_GRAPH - num_nodes * SIZEOF_NODE) // (2 * SIZEOF_INT)
    
    # Verifica che non superi il massimo possibile
    max_edges = num_nodes * (num_nodes - 1) // 2
    if edges > max_edges:
        print(f"    ATTENZIONE: archi richiesti ({edges}) > max possibili ({max_edges})")
        edges = max_edges
    
    return max(0, edges)


def format_size(size_bytes: int) -> str:
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    elif size_bytes >= 1024:
        return f"{size_bytes / 1024:.2f} KB"
    return f"{size_bytes} B"


def generate_graph(num_nodes: int, num_edges: int, seed: int) -> nx.Graph:
    """
    Genera grafo con esattamente num_nodes e circa num_edges.
    Usa gnm_random_graph per controllo preciso.
    """
    if num_nodes < 2:
        return nx.empty_graph(num_nodes)
    
    max_edges = num_nodes * (num_nodes - 1) // 2
    actual_edges = min(num_edges, max_edges)
    
    print(f"      Generando: {num_nodes} nodi, {actual_edges} archi...", end=" ", flush=True)
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
    print("VF2++ Graph Generator")
    print("=" * 60)
    print(f"Seed: {seed}")
    print()
    print("Configurazione (nodi fissi per tempi ragionevoli):")
    print("-" * 60)
    for name, target, nodes, degree in SIZE_CONFIGS:
        print(f"  {name:6s}: {nodes:6d} nodi, grado ~{degree}")
    print("-" * 60)
    print()
    
    os.makedirs("inputs", exist_ok=True)
    
    with open("inputs/manifest.txt", 'w') as manifest:
        manifest.write(f"# VF2++ Test Inputs Manifest\n")
        manifest.write(f"# Seed: {seed}\n")
        manifest.write("# name,g1,g2,nodes,edges,degree,target_ram,actual_ram,isomorphic\n\n")
        
        for name, target_bytes, num_nodes, target_degree in SIZE_CONFIGS:
            # Calcola archi per raggiungere RAM target (per singolo grafo = target/2)
            single_target = target_bytes // 2
            num_edges = calculate_edges_for_ram(single_target, num_nodes)
            
            print("=" * 60)
            print(f"[{name}] Target: {format_size(target_bytes)}")
            print(f"  Parametri: {num_nodes} nodi, {num_edges} archi")
            
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
            
            print(f"      Generando copia isomorfa...", end=" ", flush=True)
            G2, perm = generate_isomorphic_copy(G1, seed=seed+1)
            print("OK", flush=True)
            
            save_graph_fast(G2, g2_iso)
            save_permutation(perm, perm_path)
            
            print(f"      Risultato: {actual_edges} archi, grado {actual_degree:.1f}, RAM {format_size(actual_ram*2)}")
            
            manifest.write(f"{name}_iso,{g1_iso},{g2_iso},{num_nodes},{actual_edges},{actual_degree:.1f},{target_bytes},{actual_ram*2},1\n")
            
            del G2
            
            # === NON ISOMORFI ===
            g1_diff = f"inputs/{name}_diff_g1.txt"
            g2_diff = f"inputs/{name}_diff_g2.txt"
            
            print(f"  [2/2] Coppia NON ISOMORFA:")
            
            # Riusa G1
            save_graph_fast(G1, g1_diff)
            edges1 = actual_edges
            ram1 = actual_ram
            deg1 = actual_degree
            
            del G1
            
            # G2 con 10% archi in meno (garantisce non-isomorfismo)
            num_edges_2 = int(num_edges * 0.9)
            G2_diff = generate_graph(num_nodes, num_edges_2, seed=seed+200)
            edges2 = G2_diff.number_of_edges()
            ram2 = calculate_ram_usage(num_nodes, edges2)
            deg2 = (2 * edges2) / num_nodes
            
            save_graph_fast(G2_diff, g2_diff)
            
            print(f"      G1: {edges1} archi, grado {deg1:.1f}")
            print(f"      G2: {edges2} archi, grado {deg2:.1f}")
            print(f"      RAM totale: {format_size(ram1 + ram2)}")
            
            del G2_diff
            
            manifest.write(f"{name}_diff,{g1_diff},{g2_diff},{num_nodes},{edges1}/{edges2},{deg1:.1f}/{deg2:.1f},{target_bytes},{ram1+ram2},0\n")
            
            print()
    
    print("=" * 60)
    print("GENERAZIONE COMPLETATA!")
    print("File in: inputs/")
    print("Manifest: inputs/manifest.txt")
    print()
    print("Prossimi passi:")
    print("  1. Testa con: ./build/vf2pp_seq_O3 inputs/1MB_iso_g1.txt inputs/1MB_iso_g2.txt")
    print("  2. Benchmark: make benchmark_seq")
    print()


if __name__ == "__main__":
    main()
