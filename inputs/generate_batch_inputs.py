#!/usr/bin/env python3
"""
==================================================================
VF2++ - Generatore Input per Batch Mode
==================================================================

Genera molte coppie di grafi piccoli per testare la modalità batch MPI.
L'obiettivo è mostrare speedup quasi-lineare quando si distribuiscono
molte query tra processi MPI.

USO:
    python generate_batch_inputs.py [num_pairs] [target_size_mb]

ESEMPIO:
    python generate_batch_inputs.py 100 5
    -> Genera 100 coppie di grafi da ~5MB ciascuna

OUTPUT:
    inputs/batch/pair_000_g1.txt, pair_000_g2.txt
    inputs/batch/pair_001_g1.txt, pair_001_g2.txt
    ...
    inputs/batch/manifest.json

==================================================================
"""

import os
import sys
import json
import random
import hashlib
from pathlib import Path
from datetime import datetime

# =============================================================================
# CONFIGURAZIONE
# =============================================================================

SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent  # inputs/ -> vf2pp_project/
OUTPUT_DIR = SCRIPT_DIR / "batch"  # inputs/batch/

# Parametri default
DEFAULT_NUM_PAIRS = 100
DEFAULT_TARGET_SIZE_MB = 5  # Grafi piccoli per batch veloce

# Seed fisso per riproducibilità
MASTER_SEED = 42

# =============================================================================
# FUNZIONI
# =============================================================================

def estimate_graph_params(target_mb):
    """
    Stima parametri del grafo per raggiungere target_mb in RAM.
    RAM ≈ 8*nodes + 8*edges bytes (approssimazione)
    """
    target_bytes = target_mb * 1024 * 1024
    
    # Per grafi densi: edges ≈ nodes * avg_degree / 2
    # Usiamo avg_degree ~ 50 per grafi piccoli
    avg_degree = 50
    
    # RAM ≈ 8*n + 8*(n*d/2) = 8n(1 + d/2)
    # n ≈ target_bytes / (8 * (1 + d/2))
    nodes = int(target_bytes / (8 * (1 + avg_degree / 2)))
    
    # Limiti ragionevoli
    nodes = max(100, min(nodes, 5000))
    
    return nodes, avg_degree


def generate_erdos_renyi_graph(num_nodes, avg_degree, seed):
    """Genera grafo Erdos-Renyi con grado medio specificato."""
    random.seed(seed)
    
    # Probabilità arco: p = avg_degree / (n-1)
    p = min(1.0, avg_degree / (num_nodes - 1))
    
    edges = set()
    for i in range(num_nodes):
        for j in range(i + 1, num_nodes):
            if random.random() < p:
                edges.add((i, j))
    
    return list(edges)


def generate_isomorphic_pair(num_nodes, avg_degree, seed):
    """
    Genera una coppia di grafi isomorfi.
    G2 è una permutazione casuale di G1.
    """
    edges_g1 = generate_erdos_renyi_graph(num_nodes, avg_degree, seed)
    
    # Permutazione casuale per G2
    random.seed(seed + 1000000)
    perm = list(range(num_nodes))
    random.shuffle(perm)
    
    # Applica permutazione
    edges_g2 = [(perm[u], perm[v]) for u, v in edges_g1]
    
    # Normalizza (u < v)
    edges_g2 = [(min(u, v), max(u, v)) for u, v in edges_g2]
    edges_g2.sort()
    
    return edges_g1, edges_g2, num_nodes


def write_graph_file(filepath, num_nodes, edges):
    """Scrive grafo in formato edge-list."""
    with open(filepath, 'w') as f:
        f.write(f"{num_nodes} {len(edges)}\n")
        for u, v in edges:
            f.write(f"{u} {v}\n")


def compute_file_hash(filepath):
    """Calcola MD5 hash di un file."""
    hasher = hashlib.md5()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            hasher.update(chunk)
    return hasher.hexdigest()


def main():
    # Parse argomenti
    num_pairs = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_NUM_PAIRS
    target_mb = float(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_TARGET_SIZE_MB
    
    print("=" * 60)
    print("VF2++ - Generatore Input Batch")
    print("=" * 60)
    print(f"Coppie da generare:  {num_pairs}")
    print(f"Dimensione target:   {target_mb} MB per grafo")
    print(f"Output directory:    {OUTPUT_DIR}")
    print(f"Master seed:         {MASTER_SEED}")
    print()
    
    # Crea directory output
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Stima parametri
    nodes, avg_degree = estimate_graph_params(target_mb)
    print(f"Parametri stimati:   {nodes} nodi, grado medio ~{avg_degree}")
    print()
    
    # Genera coppie
    manifest = {
        "generated_at": datetime.now().isoformat(),
        "master_seed": MASTER_SEED,
        "num_pairs": num_pairs,
        "target_mb": target_mb,
        "estimated_nodes": nodes,
        "estimated_avg_degree": avg_degree,
        "pairs": []
    }
    
    print("Generazione coppie...")
    
    for i in range(num_pairs):
        seed = MASTER_SEED + i * 1000
        
        # Genera coppia isomorfa
        edges_g1, edges_g2, n = generate_isomorphic_pair(nodes, avg_degree, seed)
        
        # Nomi file
        g1_name = f"pair_{i:03d}_g1.txt"
        g2_name = f"pair_{i:03d}_g2.txt"
        g1_path = OUTPUT_DIR / g1_name
        g2_path = OUTPUT_DIR / g2_name
        
        # Scrivi file
        write_graph_file(g1_path, n, edges_g1)
        write_graph_file(g2_path, n, edges_g2)
        
        # Calcola hash e size
        g1_size = g1_path.stat().st_size
        g2_size = g2_path.stat().st_size
        
        # Aggiungi al manifest
        manifest["pairs"].append({
            "id": i,
            "g1": g1_name,
            "g2": g2_name,
            "nodes": n,
            "edges": len(edges_g1),
            "g1_size_bytes": g1_size,
            "g2_size_bytes": g2_size,
            "seed": seed,
            "is_isomorphic": True
        })
        
        if (i + 1) % 10 == 0 or i == num_pairs - 1:
            print(f"  [{i+1}/{num_pairs}] {g1_name} - {n} nodi, {len(edges_g1)} archi")
    
    # Scrivi manifest
    manifest_path = OUTPUT_DIR / "manifest.json"
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)
    
    # Riepilogo
    total_size = sum(p["g1_size_bytes"] + p["g2_size_bytes"] for p in manifest["pairs"])
    total_size_mb = total_size / (1024 * 1024)
    
    print()
    print("=" * 60)
    print("GENERAZIONE COMPLETATA")
    print("=" * 60)
    print(f"Coppie generate:     {num_pairs}")
    print(f"Dimensione totale:   {total_size_mb:.2f} MB")
    print(f"Media per coppia:    {total_size_mb / num_pairs:.2f} MB")
    print(f"Manifest:            {manifest_path}")
    print()
    print("Prossimi passi:")
    print(f"  1. Benchmark sequenziale: make benchmark_batch_seq")
    print(f"  2. Benchmark MPI batch:   make benchmark_batch_mpi")
    print()


if __name__ == "__main__":
    main()
