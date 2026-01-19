#!/usr/bin/env python3
"""
==================================================================
VF2++ - Grafici Benchmark Batch MPI
==================================================================

Genera grafici che mostrano lo speedup della modalità batch MPI.

==================================================================
"""

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

# =============================================================================
# CONFIGURAZIONE
# =============================================================================

SCRIPT_DIR = Path(__file__).parent.resolve()
MPI_OUTPUT_DIR = SCRIPT_DIR.parent / "output"
PLOTS_DIR = SCRIPT_DIR.parent / "plots"

# =============================================================================
# FUNZIONI
# =============================================================================

def load_batch_results():
    """Carica risultati batch."""
    csv_path = MPI_OUTPUT_DIR / "batch_results.csv"
    if not csv_path.exists():
        print(f"[ERRORE] File non trovato: {csv_path}")
        print("         Esegui prima: bash mpi/scripts/benchmark_batch.sh")
        return None
    
    df = pd.read_csv(csv_path)
    print(f"[OK] Caricato: {csv_path.name} ({len(df)} righe)")
    print(df.to_string(index=False))
    print()
    return df


def plot_speedup(df):
    """Grafico: Speedup batch MPI."""
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Ordina per numero processi
    df_sorted = df.sort_values('NumProcs')
    
    procs = df_sorted['NumProcs'].values
    speedups = df_sorted['Speedup'].values
    
    # Barre speedup
    colors = plt.cm.Blues(np.linspace(0.4, 0.9, len(procs)))
    bars = ax.bar(range(len(procs)), speedups, color=colors, alpha=0.8, edgecolor='black')
    
    # Linea speedup ideale
    ideal = procs.astype(float)
    ax.plot(range(len(procs)), ideal, 'r--', linewidth=2, marker='o', 
            markersize=8, label='Speedup ideale')
    
    # Etichette sui bar
    for i, (bar, sp) in enumerate(zip(bars, speedups)):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
                f'{sp:.2f}x', ha='center', va='bottom', fontsize=11, fontweight='bold')
    
    ax.set_xlabel('Numero Processi MPI', fontsize=12)
    ax.set_ylabel('Speedup (T₁ / Tₙ)', fontsize=12)
    ax.set_title('Speedup MPI Batch Mode - Distribuzione Coppie di Grafi', 
                fontsize=14, fontweight='bold')
    ax.set_xticks(range(len(procs)))
    ax.set_xticklabels(procs)
    ax.legend(loc='upper left')
    ax.grid(True, alpha=0.3, axis='y')
    ax.set_ylim(0, max(max(procs), max(speedups)) * 1.2)
    
    plt.tight_layout()
    
    filepath = PLOTS_DIR / "batch_speedup.png"
    plt.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"[GRAFICO] {filepath.name}")


def plot_efficiency(df):
    """Grafico: Efficienza batch MPI."""
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    df_sorted = df.sort_values('NumProcs')
    
    procs = df_sorted['NumProcs'].values
    efficiencies = df_sorted['Efficiency'].values
    
    # Colori basati sul valore
    colors = ['#2ecc71' if e >= 80 else '#f39c12' if e >= 50 else '#e74c3c' 
              for e in efficiencies]
    
    bars = ax.bar(range(len(procs)), efficiencies, color=colors, alpha=0.8, edgecolor='black')
    
    # Linee riferimento
    ax.axhline(y=100, color='green', linestyle='--', linewidth=2, label='Ideale (100%)')
    ax.axhline(y=80, color='orange', linestyle=':', alpha=0.7, label='Buona (80%)')
    ax.axhline(y=50, color='red', linestyle=':', alpha=0.7, label='Minima (50%)')
    
    # Etichette
    for i, (bar, eff) in enumerate(zip(bars, efficiencies)):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2,
                f'{eff:.1f}%', ha='center', va='bottom', fontsize=11, fontweight='bold')
    
    ax.set_xlabel('Numero Processi MPI', fontsize=12)
    ax.set_ylabel('Efficienza (%)', fontsize=12)
    ax.set_title('Efficienza Parallela MPI Batch Mode', fontsize=14, fontweight='bold')
    ax.set_xticks(range(len(procs)))
    ax.set_xticklabels(procs)
    ax.legend(loc='upper right')
    ax.grid(True, alpha=0.3, axis='y')
    ax.set_ylim(0, max(120, max(efficiencies) + 10))
    
    plt.tight_layout()
    
    filepath = PLOTS_DIR / "batch_efficiency.png"
    plt.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"[GRAFICO] {filepath.name}")


def plot_throughput(df):
    """Grafico: Throughput (coppie/secondo)."""
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    df_sorted = df.sort_values('NumProcs')
    
    procs = df_sorted['NumProcs'].values
    throughputs = df_sorted['Throughput'].values
    labels = [f'np={p}' for p in procs]
    
    colors = plt.cm.Greens(np.linspace(0.3, 0.9, len(procs)))
    
    bars = ax.bar(range(len(procs)), throughputs, color=colors, alpha=0.8, edgecolor='black')
    
    # Etichette
    for bar, tp in zip(bars, throughputs):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
                f'{tp:.1f}', ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    ax.set_xlabel('Numero Processi MPI', fontsize=12)
    ax.set_ylabel('Throughput (coppie/secondo)', fontsize=12)
    ax.set_title('Throughput VF2++ MPI Batch Mode', fontsize=14, fontweight='bold')
    ax.set_xticks(range(len(procs)))
    ax.set_xticklabels(labels)
    ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    
    filepath = PLOTS_DIR / "batch_throughput.png"
    plt.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"[GRAFICO] {filepath.name}")


def plot_time_comparison(df):
    """Grafico: Confronto tempi totali."""
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    df_sorted = df.sort_values('NumProcs')
    
    procs = df_sorted['NumProcs'].values
    times = df_sorted['TotalTime_s'].values
    labels = [f'np={p}' for p in procs]
    
    colors = plt.cm.Reds_r(np.linspace(0.3, 0.8, len(procs)))
    
    bars = ax.bar(range(len(procs)), times, color=colors, alpha=0.8, edgecolor='black')
    
    # Etichette
    for bar, t in zip(bars, times):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
                f'{t:.2f}s', ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    ax.set_xlabel('Numero Processi MPI', fontsize=12)
    ax.set_ylabel('Tempo Totale (s)', fontsize=12)
    ax.set_title('Tempo Totale Elaborazione Batch', fontsize=14, fontweight='bold')
    ax.set_xticks(range(len(procs)))
    ax.set_xticklabels(labels)
    ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    
    filepath = PLOTS_DIR / "batch_time.png"
    plt.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"[GRAFICO] {filepath.name}")


def plot_summary(df):
    """Grafico riassuntivo: speedup + efficienza."""
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    
    df_sorted = df.sort_values('NumProcs')
    procs = df_sorted['NumProcs'].values
    speedups = df_sorted['Speedup'].values
    efficiencies = df_sorted['Efficiency'].values
    
    # --- Speedup ---
    colors1 = plt.cm.Blues(np.linspace(0.4, 0.9, len(procs)))
    bars1 = ax1.bar(range(len(procs)), speedups, color=colors1, alpha=0.8, edgecolor='black')
    ax1.plot(range(len(procs)), procs.astype(float), 'r--', linewidth=2, marker='o', 
             markersize=8, label='Ideale')
    
    for bar, sp in zip(bars1, speedups):
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
                f'{sp:.2f}x', ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    ax1.set_xlabel('Numero Processi', fontsize=11)
    ax1.set_ylabel('Speedup', fontsize=11)
    ax1.set_title('Speedup', fontsize=12, fontweight='bold')
    ax1.set_xticks(range(len(procs)))
    ax1.set_xticklabels(procs)
    ax1.legend(loc='upper left')
    ax1.grid(True, alpha=0.3, axis='y')
    ax1.set_ylim(0, max(max(procs), max(speedups)) * 1.2)
    
    # --- Efficienza ---
    colors2 = ['#2ecc71' if e >= 80 else '#f39c12' if e >= 50 else '#e74c3c' 
               for e in efficiencies]
    bars2 = ax2.bar(range(len(procs)), efficiencies, color=colors2, alpha=0.8, edgecolor='black')
    ax2.axhline(y=100, color='green', linestyle='--', linewidth=2, alpha=0.7)
    ax2.axhline(y=80, color='orange', linestyle=':', alpha=0.5)
    
    for bar, eff in zip(bars2, efficiencies):
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2,
                f'{eff:.1f}%', ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    ax2.set_xlabel('Numero Processi', fontsize=11)
    ax2.set_ylabel('Efficienza (%)', fontsize=11)
    ax2.set_title('Efficienza', fontsize=12, fontweight='bold')
    ax2.set_xticks(range(len(procs)))
    ax2.set_xticklabels(procs)
    ax2.grid(True, alpha=0.3, axis='y')
    ax2.set_ylim(0, max(120, max(efficiencies) + 10))
    
    fig.suptitle('VF2++ MPI Batch Mode - Performance', fontsize=14, fontweight='bold', y=1.02)
    plt.tight_layout()
    
    filepath = PLOTS_DIR / "batch_summary.png"
    plt.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"[GRAFICO] {filepath.name}")


def print_summary(df):
    """Stampa riepilogo risultati."""
    
    print("\n" + "=" * 70)
    print("RIEPILOGO BENCHMARK BATCH MPI")
    print("=" * 70)
    
    df_sorted = df.sort_values('NumProcs')
    
    # Baseline
    baseline = df_sorted.iloc[0]
    print(f"\nBASELINE (np=1):")
    print(f"  Coppie elaborate:  {int(baseline['NumPairs'])}")
    print(f"  Tempo totale:      {baseline['TotalTime_s']:.2f}s")
    print(f"  Throughput:        {baseline['Throughput']:.2f} coppie/s")
    
    print(f"\nRISULTATI:")
    print(f"{'NP':>4} {'Tempo (s)':>12} {'Throughput':>12} {'Speedup':>10} {'Efficienza':>12}")
    print("-" * 55)
    
    for _, row in df_sorted.iterrows():
        print(f"{int(row['NumProcs']):>4} {row['TotalTime_s']:>12.2f} "
              f"{row['Throughput']:>12.2f} {row['Speedup']:>9.2f}x {row['Efficiency']:>11.1f}%")
    
    print("=" * 70)
    
    # Analisi
    max_speedup = df_sorted['Speedup'].max()
    max_procs = df_sorted.loc[df_sorted['Speedup'].idxmax(), 'NumProcs']
    avg_efficiency = df_sorted[df_sorted['NumProcs'] > 1]['Efficiency'].mean()
    
    print(f"\nANALISI:")
    print(f"  Speedup massimo:      {max_speedup:.2f}x (con {int(max_procs)} processi)")
    print(f"  Efficienza media:     {avg_efficiency:.1f}%")
    
    if avg_efficiency >= 80:
        print(f"  Valutazione:          ECCELLENTE scalabilità")
    elif avg_efficiency >= 60:
        print(f"  Valutazione:          BUONA scalabilità")
    else:
        print(f"  Valutazione:          Scalabilità limitata")
    
    print("=" * 70)


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 60)
    print("VF2++ - Grafici Benchmark Batch MPI")
    print("=" * 60)
    print()
    
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    
    df = load_batch_results()
    if df is None:
        return
    
    print("--- Generazione grafici ---")
    plot_speedup(df)
    plot_efficiency(df)
    plot_throughput(df)
    plot_time_comparison(df)
    plot_summary(df)
    
    print_summary(df)
    
    print(f"\nGrafici salvati in: {PLOTS_DIR}")


if __name__ == "__main__":
    main()
