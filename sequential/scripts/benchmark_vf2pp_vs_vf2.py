#!/usr/bin/env python3
"""
================================================================================
VF2++ vs VF2 Base - Benchmark di Confronto Performance
================================================================================

Questo script confronta le performance tra:
  1. VF2++ (la tua implementazione sequenziale in C)
  2. VF2 Base (NetworkX - implementazione di riferimento)

Ispirato a: https://github.com/kpetridis24/vf2-pp

REQUISITI:
    pip install networkx matplotlib

ESECUZIONE:
    python benchmark_vf2pp_vs_vf2.py
    python benchmark_vf2pp_vs_vf2.py 100 1000 100   # (min, max, step)

OUTPUT:
    - Report testuale in console
    - Grafici PNG in sequential/plots/benchmark/
    - CSV con tutti i risultati

================================================================================
"""

import os
import sys
import time
import subprocess
import shutil
import csv
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Tuple, Optional

# ==============================================================================
# VERIFICA DIPENDENZE
# ==============================================================================

try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False
    print("=" * 60)
    print("[ERRORE] NetworkX non installato!")
    print("Esegui: pip install networkx matplotlib")
    print("=" * 60)
    sys.exit(1)

try:
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    print("[WARNING] matplotlib non installato. I grafici non verranno generati.")
    print("Esegui: pip install matplotlib")

# ==============================================================================
# CONFIGURAZIONE PATHS
# ==============================================================================

SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent.parent
BUILD_DIR = PROJECT_ROOT / "build"
OUTPUT_DIR = SCRIPT_DIR.parent / "plots" / "benchmark"
TEMP_DIR = PROJECT_ROOT / "temp_benchmark"

# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class BenchmarkResult:
    """Risultato di un singolo test."""
    graph_type: str
    num_nodes: int
    num_edges: int
    vf2pp_time: float
    vf2_time: float
    vf2pp_result: bool
    vf2_result: bool
    
    @property
    def results_match(self) -> bool:
        return self.vf2pp_result == self.vf2_result


@dataclass
class BenchmarkSuite:
    """Collezione di risultati per un tipo di grafo."""
    graph_type: str
    results: List[BenchmarkResult] = field(default_factory=list)
    
    def add(self, result: BenchmarkResult):
        self.results.append(result)
    
    @property
    def nodes(self) -> List[int]:
        return [r.num_nodes for r in self.results]
    
    @property
    def vf2pp_times(self) -> List[float]:
        return [r.vf2pp_time for r in self.results]
    
    @property
    def vf2_times(self) -> List[float]:
        return [r.vf2_time for r in self.results]


# ==============================================================================
# FUNZIONI UTILITY
# ==============================================================================

def save_graph_to_file(G: nx.Graph, filepath: str) -> str:
    """
    Salva un grafo NetworkX nel formato richiesto dal progetto.
    
    Formato:
        N M
        nodo    vicino1 vicino2 ...
    """
    N = G.number_of_nodes()
    M = G.number_of_edges()
    
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    with open(filepath, "w") as f:
        f.write(f"{N} {M}\n")
        for node in sorted(G.nodes()):
            neighbors = sorted(list(G.neighbors(node)))
            if neighbors:
                f.write(f"{node}\t{' '.join(map(str, neighbors))}\n")
            else:
                f.write(f"{node}\n")
    
    return filepath


def run_vf2pp_executable(exec_path: Path, g1_file: str, g2_file: str, 
                          work_dir: str) -> Tuple[bool, float]:
    """
    Esegue l'eseguibile VF2++ e restituisce (is_isomorphic, tempo).
    
    Il tempo viene misurato esternamente da Python per consistenza
    con la misurazione di NetworkX.
    """
    if not exec_path.exists():
        print(f"  [ERRORE] Eseguibile non trovato: {exec_path}")
        return False, 0.0
    
    try:
        start_time = time.perf_counter()
        
        result = subprocess.run(
            [str(exec_path), os.path.basename(g1_file), os.path.basename(g2_file)],
            cwd=work_dir,
            capture_output=True,
            text=True,
            timeout=300
        )
        
        elapsed = time.perf_counter() - start_time
        
        # Il return code 0 indica grafi isomorfi
        is_isomorphic = (result.returncode == 0)
        
        return is_isomorphic, elapsed
        
    except subprocess.TimeoutExpired:
        print("  [TIMEOUT] VF2++ ha superato il tempo limite")
        return False, 0.0
    except Exception as e:
        print(f"  [ERRORE] Esecuzione fallita: {e}")
        return False, 0.0


def run_networkx_vf2(G1: nx.Graph, G2: nx.Graph) -> Tuple[bool, float]:
    """
    Esegue l'algoritmo VF2 di NetworkX e restituisce (is_isomorphic, tempo).
    """
    start_time = time.perf_counter()
    is_isomorphic = nx.is_isomorphic(G1, G2)
    elapsed = time.perf_counter() - start_time
    
    return is_isomorphic, elapsed


# ==============================================================================
# GENERATORI DI GRAFI
# ==============================================================================

def generate_random_graph(n: int, p: float = 0.1, seed: int = 42) -> nx.Graph:
    """Genera un grafo random Erdos-Renyi."""
    return nx.gnp_random_graph(n, p, seed=seed)


def generate_complete_graph(n: int) -> nx.Graph:
    """Genera un grafo completo K_n."""
    return nx.complete_graph(n)


def generate_sparse_graph(n: int, seed: int = 42) -> nx.Graph:
    """Genera un grafo sparso (bassa densità)."""
    return nx.gnp_random_graph(n, p=0.02, seed=seed)


def generate_regular_graph(n: int, d: int = 4, seed: int = 42) -> nx.Graph:
    """Genera un grafo regolare (ogni nodo ha grado d)."""
    if n * d % 2 != 0:
        d = d + 1 if d < n - 1 else d - 1
    try:
        return nx.random_regular_graph(d, n, seed=seed)
    except:
        return nx.gnp_random_graph(n, p=d/n, seed=seed)


# ==============================================================================
# CLASSE PRINCIPALE BENCHMARK
# ==============================================================================

class VF2Benchmark:
    """
    Classe principale per il benchmark VF2++ vs VF2.
    """
    
    def __init__(self, node_range: range, exec_path: Path):
        self.node_range = list(node_range)
        self.exec_path = exec_path
        self.suites: List[BenchmarkSuite] = []
        
        # Crea directory temporanea
        TEMP_DIR.mkdir(parents=True, exist_ok=True)
    
    def _run_single_test(self, G1: nx.Graph, G2: nx.Graph, 
                         graph_type: str, tag: str) -> BenchmarkResult:
        """Esegue un singolo test di confronto."""
        
        # Salva grafi per VF2++
        g1_file = str(TEMP_DIR / f"{tag}_G1.txt")
        g2_file = str(TEMP_DIR / f"{tag}_G2.txt")
        
        save_graph_to_file(G1, g1_file)
        save_graph_to_file(G2, g2_file)
        
        # Esegui VF2++
        vf2pp_result, vf2pp_time = run_vf2pp_executable(
            self.exec_path, g1_file, g2_file, str(TEMP_DIR)
        )
        
        # Esegui NetworkX VF2
        vf2_result, vf2_time = run_networkx_vf2(G1, G2)
        
        # Cleanup
        try:
            os.remove(g1_file)
            os.remove(g2_file)
        except:
            pass
        
        return BenchmarkResult(
            graph_type=graph_type,
            num_nodes=G1.number_of_nodes(),
            num_edges=G1.number_of_edges(),
            vf2pp_time=vf2pp_time,
            vf2_time=vf2_time,
            vf2pp_result=vf2pp_result,
            vf2_result=vf2_result
        )
    
    def benchmark_random_graphs(self, probability: float = 0.1) -> BenchmarkSuite:
        """Benchmark su grafi random."""
        suite = BenchmarkSuite("Random")
        
        print(f"\n  [Random Graphs] probabilità = {probability}")
        print("  " + "-" * 50)
        
        for n in self.node_range:
            if n == 0:
                continue
            
            print(f"    n = {n:5d}", end=" ... ", flush=True)
            
            # Genera due grafi identici (stesso seed = isomorfi)
            G1 = generate_random_graph(n, probability, seed=42)
            G2 = generate_random_graph(n, probability, seed=42)
            
            result = self._run_single_test(G1, G2, "Random", f"random_{n}")
            suite.add(result)
            
            status = "OK" if result.results_match else "MISMATCH!"
            print(f"VF2++: {result.vf2pp_time:.4f}s | VF2: {result.vf2_time:.4f}s | {status}")
        
        self.suites.append(suite)
        return suite
    
    def benchmark_sparse_graphs(self) -> BenchmarkSuite:
        """Benchmark su grafi sparsi."""
        suite = BenchmarkSuite("Sparse")
        
        print(f"\n  [Sparse Graphs] probabilità = 0.02")
        print("  " + "-" * 50)
        
        for n in self.node_range:
            if n == 0:
                continue
            
            print(f"    n = {n:5d}", end=" ... ", flush=True)
            
            G1 = generate_sparse_graph(n, seed=42)
            G2 = generate_sparse_graph(n, seed=42)
            
            result = self._run_single_test(G1, G2, "Sparse", f"sparse_{n}")
            suite.add(result)
            
            status = "OK" if result.results_match else "MISMATCH!"
            print(f"VF2++: {result.vf2pp_time:.4f}s | VF2: {result.vf2_time:.4f}s | {status}")
        
        self.suites.append(suite)
        return suite
    
    def benchmark_complete_graphs(self, max_nodes: int = 300) -> BenchmarkSuite:
        """Benchmark su grafi completi (limitati per performance)."""
        suite = BenchmarkSuite("Complete")
        
        print(f"\n  [Complete Graphs] (max {max_nodes} nodi)")
        print("  " + "-" * 50)
        
        for n in self.node_range:
            if n == 0 or n > max_nodes:
                continue
            
            print(f"    n = {n:5d}", end=" ... ", flush=True)
            
            G1 = generate_complete_graph(n)
            G2 = generate_complete_graph(n)
            
            result = self._run_single_test(G1, G2, "Complete", f"complete_{n}")
            suite.add(result)
            
            status = "OK" if result.results_match else "MISMATCH!"
            print(f"VF2++: {result.vf2pp_time:.4f}s | VF2: {result.vf2_time:.4f}s | {status}")
        
        self.suites.append(suite)
        return suite
    
    def benchmark_regular_graphs(self, degree: int = 4) -> BenchmarkSuite:
        """Benchmark su grafi regolari."""
        suite = BenchmarkSuite("Regular")
        
        print(f"\n  [Regular Graphs] grado = {degree}")
        print("  " + "-" * 50)
        
        for n in self.node_range:
            if n == 0 or n <= degree:
                continue
            
            print(f"    n = {n:5d}", end=" ... ", flush=True)
            
            G1 = generate_regular_graph(n, degree, seed=42)
            G2 = generate_regular_graph(n, degree, seed=42)
            
            result = self._run_single_test(G1, G2, "Regular", f"regular_{n}")
            suite.add(result)
            
            status = "OK" if result.results_match else "MISMATCH!"
            print(f"VF2++: {result.vf2pp_time:.4f}s | VF2: {result.vf2_time:.4f}s | {status}")
        
        self.suites.append(suite)
        return suite
    
    def cleanup(self):
        """Rimuove file temporanei."""
        try:
            if TEMP_DIR.exists():
                shutil.rmtree(TEMP_DIR)
        except:
            pass


# ==============================================================================
# FUNZIONI DI OUTPUT
# ==============================================================================

def print_report(suites: List[BenchmarkSuite], opt_level: str):
    """Stampa un report testuale dei risultati."""
    
    print("\n")
    print("=" * 70)
    print(f"                    REPORT BENCHMARK VF2++ vs VF2")
    print(f"                       Ottimizzazione: {opt_level}")
    print("=" * 70)
    
    for suite in suites:
        print(f"\n┌{'─' * 54}┐")
        print(f"│ {suite.graph_type.upper() + ' GRAPHS':^52} │")
        print(f"├{'─' * 54}┤")
        print(f"│ {'Nodi':>8} │ {'Archi':>8} │ {'VF2++ (s)':>12} │ {'VF2 (s)':>12} │")
        print(f"├{'─' * 54}┤")
        
        for r in suite.results:
            print(f"│ {r.num_nodes:>8} │ {r.num_edges:>8} │ {r.vf2pp_time:>12.6f} │ "
                  f"{r.vf2_time:>12.6f} │")
        
        print(f"└{'─' * 54}┘")


def save_to_csv(suites: List[BenchmarkSuite], filepath: Path):
    """Salva i risultati in un file CSV."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'graph_type', 'nodes', 'edges', 
            'vf2pp_time_s', 'vf2_time_s',
            'vf2pp_result', 'vf2_result', 'match'
        ])
        
        for suite in suites:
            for r in suite.results:
                writer.writerow([
                    r.graph_type, r.num_nodes, r.num_edges,
                    f"{r.vf2pp_time:.6f}", f"{r.vf2_time:.6f}",
                    r.vf2pp_result, r.vf2_result, r.results_match
                ])
    
    print(f"\n[CSV] Risultati salvati in: {filepath}")


def plot_results(suites: List[BenchmarkSuite], output_dir: Path, opt_level: str):
    """Genera grafici dei risultati."""
    if not HAS_MATPLOTLIB:
        print("[WARNING] matplotlib non disponibile, grafici non generati")
        return
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    for suite in suites:
        if not suite.results:
            continue
        
        graph_type = suite.graph_type.lower()
        
        # Grafico 1: Confronto tempi
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.plot(suite.nodes, suite.vf2_times, 'o--', 
                label='NetworkX VF2', color='#e74c3c', linewidth=2, markersize=8)
        ax.plot(suite.nodes, suite.vf2pp_times, 's-', 
                label='VF2++ (C)', color='#2ecc71', linewidth=2, markersize=8)
        ax.set_xlabel('Numero di nodi', fontsize=12)
        ax.set_ylabel('Tempo (secondi)', fontsize=12)
        ax.set_title(f'Confronto Tempi - Grafi {suite.graph_type}\n({opt_level})', 
                     fontsize=14, fontweight='bold')
        ax.legend(fontsize=11)
        ax.grid(True, alpha=0.3)
        ax.set_yscale('log')
        
        filepath = output_dir / f"times_{graph_type}_{opt_level}.png"
        plt.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='white')
        plt.close()
        print(f"[GRAFICO] {filepath.name}")


# ==============================================================================
# MAIN
# ==============================================================================

def main():
    print("=" * 70)
    print("         VF2++ vs VF2 Base - Benchmark di Confronto")
    print("=" * 70)
    
    # Parsing argomenti
    if len(sys.argv) >= 4:
        node_min = int(sys.argv[1])
        node_max = int(sys.argv[2])
        node_step = int(sys.argv[3])
        node_range = range(node_min, node_max + 1, node_step)
        print(f"\nRange nodi: {node_min} - {node_max} (step {node_step})")
    else:
        node_range = range(100, 1001, 100)
        print(f"\nRange nodi: 100 - 1000 (step 100)  [default]")
    
    print(f"\nDirectory progetto: {PROJECT_ROOT}")
    print(f"Directory build:    {BUILD_DIR}")
    print(f"Directory output:   {OUTPUT_DIR}")
    
    # Lista eseguibili da testare
    executables = []
    for opt in ["O0", "O1", "O2", "O3"]:
        exe = BUILD_DIR / f"vf2pp_seq_{opt}.exe"
        if not exe.exists():
            exe = BUILD_DIR / f"vf2pp_seq_{opt}"
        if exe.exists():
            executables.append((exe, opt))
    
    if not executables:
        print("\n[ERRORE] Nessun eseguibile trovato!")
        print("Esegui prima: make sequential")
        return
    
    print(f"\nEseguibili trovati: {[opt for _, opt in executables]}")
    
    # Esegui benchmark per ogni livello di ottimizzazione
    for exec_path, opt_level in executables:
        print("\n")
        print("*" * 70)
        print(f"* BENCHMARK CON OTTIMIZZAZIONE {opt_level}")
        print("*" * 70)
        print(f"Eseguibile: {exec_path}")
        
        benchmark = VF2Benchmark(node_range, exec_path)
        
        try:
            # Esegui tutti i tipi di test
            benchmark.benchmark_random_graphs(probability=0.1)
            benchmark.benchmark_sparse_graphs()
            benchmark.benchmark_complete_graphs(max_nodes=300)
            # Regular graphs rimossi: causano blocchi a 400+ nodi
            # benchmark.benchmark_regular_graphs(degree=4)
            
            # Output risultati
            print_report(benchmark.suites, opt_level)
            
            # Salva CSV
            csv_path = OUTPUT_DIR / f"results_{opt_level}.csv"
            save_to_csv(benchmark.suites, csv_path)
            
            # Genera grafici
            print(f"\n[INFO] Generazione grafici...")
            plot_results(benchmark.suites, OUTPUT_DIR, opt_level)
            
        except Exception as e:
            print(f"\n[ERRORE] {e}")
            import traceback
            traceback.print_exc()
        finally:
            benchmark.cleanup()
    
    print("\n" + "=" * 70)
    print("                    BENCHMARK COMPLETATO!")
    print(f"                  Risultati in: {OUTPUT_DIR}")
    print("=" * 70)


if __name__ == "__main__":
    main()