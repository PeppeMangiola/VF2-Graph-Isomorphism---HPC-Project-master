#!/usr/bin/env python3
"""
==================================================================
VF2++ MPI - Confronto tra Ottimizzatori (O0, O1, O2, O3)
==================================================================

Genera grafici che confrontano le performance MPI tra i diversi
livelli di ottimizzazione del compilatore.

SOLO GRAFI ISOMORFI - SCALA LOGARITMICA

==================================================================
"""

import os
import sys
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

# =============================================================================
# CONFIGURAZIONE
# =============================================================================

SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent.parent
MPI_OUTPUT_DIR = SCRIPT_DIR.parent / "output"
PLOTS_DIR = SCRIPT_DIR.parent / "plots"

OPTIMIZERS = ["O0", "O1", "O2", "O3"]
PROC_COUNTS = [2, 4]
COLORS = {'O0': '#e74c3c', 'O1': '#f39c12', 'O2': '#3498db', 'O3': '#2ecc71'}
SIZE_ORDER = ['1MB', '50MB', '100MB', '200MB', '500MB']

# =============================================================================
# FUNZIONI
# =============================================================================

def load_all_results():
    """Carica tutti i CSV dei risultati MPI, SOLO grafi isomorfi."""
    all_data = []
    
    for opt in OPTIMIZERS:
        csv_path = MPI_OUTPUT_DIR / f"results_{opt}.csv"
        if csv_path.exists():
            df = pd.read_csv(csv_path)
            df['Optimizer'] = opt
            # FILTRA SOLO ISO
            df = df[df['Type'] == 'iso']
            all_data.append(df)
            print(f"[OK] Caricato: {csv_path.name} ({len(df)} righe iso)")
        else:
            print(f"[SKIP] Non trovato: {csv_path.name}")
    
    if not all_data:
        return None
    
    return pd.concat(all_data, ignore_index=True)


def plot_time_comparison_by_procs(df):
    """Grafico: Tempo VF2++ per ogni ottimizzatore, diviso per numero processi."""
    
    for np_val in PROC_COUNTS:
        fig, ax = plt.subplots(figsize=(10, 6))
        
        data = df[df['NumProcs'] == np_val]
        
        if data.empty:
            ax.text(0.5, 0.5, 'Nessun dato', ha='center', va='center')
            continue
        
        sizes = [s for s in SIZE_ORDER if s in data['Size'].unique()]
        x = np.arange(len(sizes))
        width = 0.2
        
        for i, opt in enumerate(OPTIMIZERS):
            opt_data = data[data['Optimizer'] == opt]
            times = []
            for size in sizes:
                t = opt_data[opt_data['Size'] == size]['Time_VF2_s'].values
                times.append(t[0] if len(t) > 0 and t[0] > 0 else 0.001)
            
            offset = (i - 1.5) * width
            ax.bar(x + offset, times, width, label=opt, color=COLORS[opt], alpha=0.8)
        
        ax.set_xlabel('Dimensione Input', fontsize=12)
        ax.set_ylabel('Tempo VF2++ (s) - Scala Log', fontsize=12)
        ax.set_title(f'Confronto Ottimizzatori MPI - {np_val} Processi (Grafi Isomorfi)', 
                     fontsize=14, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(sizes)
        ax.set_yscale('log')
        ax.legend()
        ax.grid(True, alpha=0.3, axis='y')
        
        plt.tight_layout()
        
        filepath = PLOTS_DIR / f"mpi_confronto_opt_np{np_val}.png"
        plt.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='white')
        plt.close()
        print(f"[GRAFICO] {filepath.name}")


def plot_speedup_by_optimizer(df):
    """Grafico: Speedup per ogni ottimizzatore."""
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    sizes = [s for s in SIZE_ORDER if s in df['Size'].unique()]
    x = np.arange(len(sizes))
    width = 0.1
    
    bar_idx = 0
    for opt in OPTIMIZERS:
        for np_val in PROC_COUNTS:
            opt_np_data = df[(df['Optimizer'] == opt) & (df['NumProcs'] == np_val)]
            speedups = []
            for size in sizes:
                s = opt_np_data[opt_np_data['Size'] == size]['Speedup'].values
                speedups.append(s[0] if len(s) > 0 else 0)
            
            offset = (bar_idx - 3.5) * width
            alpha = 0.6 if np_val == 2 else 0.9
            hatch = '' if np_val == 2 else '//'
            ax.bar(x + offset, speedups, width, label=f'{opt} np={np_val}',
                  color=COLORS[opt], alpha=alpha, hatch=hatch,
                  edgecolor='black', linewidth=0.5)
            bar_idx += 1
    
    ax.axhline(y=1, color='red', linestyle='--', alpha=0.7, linewidth=2, label='Speedup=1')
    ax.axhline(y=2, color='orange', linestyle=':', alpha=0.5, label='Speedup=2')
    ax.axhline(y=4, color='green', linestyle=':', alpha=0.5, label='Speedup=4')
    
    ax.set_xlabel('Dimensione Input', fontsize=12)
    ax.set_ylabel('Speedup (SEQ/MPI)', fontsize=12)
    ax.set_title('Speedup MPI vs Sequenziale per Ottimizzatore (Grafi Isomorfi)', 
                fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(sizes)
    ax.legend(loc='upper left', fontsize=8, ncol=3)
    ax.grid(True, alpha=0.3, axis='y')
    ax.set_ylim(0, 2.5)
    
    plt.tight_layout()
    
    filepath = PLOTS_DIR / "mpi_speedup_per_opt.png"
    plt.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"[GRAFICO] {filepath.name}")


def plot_efficiency_by_optimizer(df):
    """Grafico: Efficienza per ogni ottimizzatore."""
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    sizes = [s for s in SIZE_ORDER if s in df['Size'].unique()]
    x = np.arange(len(sizes))
    width = 0.1
    
    bar_idx = 0
    for opt in OPTIMIZERS:
        for np_val in PROC_COUNTS:
            opt_np_data = df[(df['Optimizer'] == opt) & (df['NumProcs'] == np_val)]
            efficiencies = []
            for size in sizes:
                e = opt_np_data[opt_np_data['Size'] == size]['Efficiency'].values
                efficiencies.append(e[0] if len(e) > 0 else 0)
            
            offset = (bar_idx - 3.5) * width
            alpha = 0.6 if np_val == 2 else 0.9
            hatch = '' if np_val == 2 else '//'
            ax.bar(x + offset, efficiencies, width, label=f'{opt} np={np_val}',
                  color=COLORS[opt], alpha=alpha, hatch=hatch,
                  edgecolor='black', linewidth=0.5)
            bar_idx += 1
    
    ax.axhline(y=100, color='green', linestyle='--', alpha=0.7, linewidth=2, label='Ideale 100%')
    ax.axhline(y=50, color='orange', linestyle=':', alpha=0.5, label='50%')
    
    ax.set_xlabel('Dimensione Input', fontsize=12)
    ax.set_ylabel('Efficienza (%)', fontsize=12)
    ax.set_title('Efficienza Parallela MPI per Ottimizzatore (Grafi Isomorfi)', 
                fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(sizes)
    ax.legend(loc='upper right', fontsize=8, ncol=3)
    ax.grid(True, alpha=0.3, axis='y')
    ax.set_ylim(0, 120)
    
    plt.tight_layout()
    
    filepath = PLOTS_DIR / "mpi_efficiency_per_opt.png"
    plt.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"[GRAFICO] {filepath.name}")


def plot_overhead_by_optimizer(df):
    """Grafico: Overhead per ogni ottimizzatore."""
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    sizes = [s for s in SIZE_ORDER if s in df['Size'].unique()]
    x = np.arange(len(sizes))
    width = 0.1
    
    bar_idx = 0
    for opt in OPTIMIZERS:
        for np_val in PROC_COUNTS:
            opt_np_data = df[(df['Optimizer'] == opt) & (df['NumProcs'] == np_val)]
            overheads = []
            for size in sizes:
                o = opt_np_data[opt_np_data['Size'] == size]['Overhead'].values
                overheads.append(o[0] if len(o) > 0 else 0)
            
            offset = (bar_idx - 3.5) * width
            alpha = 0.6 if np_val == 2 else 0.9
            hatch = '' if np_val == 2 else '//'
            ax.bar(x + offset, overheads, width, label=f'{opt} np={np_val}',
                  color=COLORS[opt], alpha=alpha, hatch=hatch,
                  edgecolor='black', linewidth=0.5)
            bar_idx += 1
    
    ax.axhline(y=0, color='black', linestyle='-', alpha=0.3)
    
    ax.set_xlabel('Dimensione Input', fontsize=12)
    ax.set_ylabel('Overhead (s)', fontsize=12)
    ax.set_title('Overhead MPI (T_mpi × NP - T_seq) per Ottimizzatore (Grafi Isomorfi)', 
                fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(sizes)
    ax.legend(loc='upper left', fontsize=8, ncol=3)
    ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    
    filepath = PLOTS_DIR / "mpi_overhead_per_opt.png"
    plt.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"[GRAFICO] {filepath.name}")


def print_summary_table(df):
    """Stampa tabella riepilogativa."""
    
    print("\n" + "=" * 100)
    print("RIEPILOGO CONFRONTO OTTIMIZZATORI MPI (SOLO GRAFI ISOMORFI)")
    print("=" * 100)
    
    for np_val in PROC_COUNTS:
        print(f"\n--- {np_val} PROCESSI ---")
        print(f"{'Size':<8}", end="")
        for opt in OPTIMIZERS:
            print(f"{opt:>12}", end="")
        print(f"{'Best':>10}")
        print("-" * 70)
        
        data = df[df['NumProcs'] == np_val]
        sizes = [s for s in SIZE_ORDER if s in data['Size'].unique()]
        
        for size in sizes:
            print(f"{size:<8}", end="")
            
            times = []
            for opt in OPTIMIZERS:
                t = data[(data['Optimizer'] == opt) & (data['Size'] == size)]['Time_VF2_s'].values
                t_val = t[0] if len(t) > 0 else 0
                times.append((opt, t_val))
                print(f"{t_val:>12.4f}", end="")
            
            # Best optimizer
            valid_times = [(o, t) for o, t in times if t > 0]
            if valid_times:
                best = min(valid_times, key=lambda x: x[1])
                print(f"{best[0]:>10}")
            else:
                print(f"{'N/A':>10}")
    
    print("=" * 100)


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 60)
    print("VF2++ MPI - Confronto Ottimizzatori (Solo Isomorfi)")
    print("=" * 60)
    print()
    
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    
    print("Caricamento dati...")
    df = load_all_results()
    
    if df is None or df.empty:
        print("\n[ERRORE] Nessun dato trovato!")
        print(f"Verifica che esistano file in: {MPI_OUTPUT_DIR}")
        return
    
    print(f"\nTotale righe caricate: {len(df)}")
    
    print("\n--- Generazione grafici ---")
    plot_time_comparison_by_procs(df)
    plot_speedup_by_optimizer(df)
    plot_efficiency_by_optimizer(df)
    plot_overhead_by_optimizer(df)
    
    print_summary_table(df)
    
    print(f"\nGrafici salvati in: {PLOTS_DIR}")


if __name__ == "__main__":
    main()
