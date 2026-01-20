#!/usr/bin/env python3
"""
==================================================================
VF2++ MPI - Confronto tra Ottimizzatori (Versione Completa)
==================================================================

Genera grafici che confrontano le performance MPI tra i diversi
livelli di ottimizzazione del compilatore.

Include: Tempi, Speedup, Efficienza, Overhead, Throughput
SEPARATI per GRAFI ISOMORFI e NON ISOMORFI

==================================================================
"""

import os
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
COLOR_ISO = '#3498db'
COLOR_DIFF = '#e74c3c'

plt.style.use('seaborn-v0_8-whitegrid')
DPI = 150

# =============================================================================
# FUNZIONI
# =============================================================================

def load_all_results():
    """Carica tutti i CSV dei risultati MPI."""
    all_data = []
    
    for opt in OPTIMIZERS:
        csv_path = MPI_OUTPUT_DIR / f"results_{opt}.csv"
        if csv_path.exists():
            try:
                df = pd.read_csv(csv_path)
                df['Optimizer'] = opt
                
                # Calcola Throughput se non presente
                if 'Throughput_MB_s' not in df.columns and 'RAM_MB' in df.columns:
                    df['Throughput_MB_s'] = df.apply(
                        lambda r: r['RAM_MB'] / r['Time_VF2_s'] if r['Time_VF2_s'] > 0 else 0, axis=1)
                
                all_data.append(df)
                print(f"[OK] Caricato: {csv_path.name} ({len(df)} righe)")
            except Exception as e:
                print(f"[ERRORE] {csv_path.name}: {e}")
        else:
            print(f"[SKIP] Non trovato: {csv_path.name}")
    
    if not all_data:
        return None
    
    return pd.concat(all_data, ignore_index=True)


def get_mean_value(df, size, np_val, column):
    """Ottiene il valore medio per una data configurazione."""
    subset = df[(df['Size'] == size) & (df['NumProcs'] == np_val)]
    values = subset[column].values
    if len(values) > 0:
        return np.mean(values)
    return 0


# =============================================================================
# GRAFICI TEMPI
# =============================================================================

def plot_time_comparison_by_procs(df, graph_type='iso'):
    """Tempo VF2++ per ogni ottimizzatore."""
    type_label = "Isomorfi" if graph_type == 'iso' else "Non Isomorfi"
    
    df_filtered = df[df['Type'] == graph_type]
    if df_filtered.empty:
        print(f"[SKIP] Nessun dato per grafi {type_label}")
        return
    
    for np_val in PROC_COUNTS:
        fig, ax = plt.subplots(figsize=(10, 6))
        
        data = df_filtered[df_filtered['NumProcs'] == np_val]
        if data.empty:
            plt.close()
            continue
        
        sizes = [s for s in SIZE_ORDER if s in data['Size'].unique()]
        x = np.arange(len(sizes))
        width = 0.2
        
        for i, opt in enumerate(OPTIMIZERS):
            opt_data = data[data['Optimizer'] == opt]
            times = [get_mean_value(opt_data, s, np_val, 'Time_VF2_s') or 0.001 for s in sizes]
            
            offset = (i - 1.5) * width
            ax.bar(x + offset, times, width, label=opt, color=COLORS[opt], alpha=0.8)
        
        ax.set_xlabel('Dimensione Input', fontsize=12, fontweight='bold')
        ax.set_ylabel('Tempo VF2++ (s) - Scala Log', fontsize=12, fontweight='bold')
        ax.set_title(f'Confronto Ottimizzatori MPI - {np_val} Processi\n(Grafi {type_label})', 
                     fontsize=14, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(sizes)
        ax.set_yscale('log')
        ax.legend()
        ax.grid(True, alpha=0.3, axis='y')
        
        plt.tight_layout()
        filepath = PLOTS_DIR / f"mpi_confronto_opt_np{np_val}_{graph_type}.png"
        plt.savefig(filepath, dpi=DPI, bbox_inches='tight', facecolor='white')
        plt.close()
        print(f"[GRAFICO] {filepath.name}")


# =============================================================================
# SPEEDUP
# =============================================================================

def plot_speedup_by_optimizer(df, graph_type='iso'):
    """Speedup per ogni ottimizzatore."""
    type_label = "Isomorfi" if graph_type == 'iso' else "Non Isomorfi"
    
    df_filtered = df[df['Type'] == graph_type]
    if df_filtered.empty:
        return
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    sizes = [s for s in SIZE_ORDER if s in df_filtered['Size'].unique()]
    x = np.arange(len(sizes))
    width = 0.1
    
    bar_idx = 0
    for opt in OPTIMIZERS:
        for np_val in PROC_COUNTS:
            opt_np_data = df_filtered[(df_filtered['Optimizer'] == opt) & (df_filtered['NumProcs'] == np_val)]
            speedups = [get_mean_value(opt_np_data, s, np_val, 'Speedup') for s in sizes]
            
            offset = (bar_idx - 3.5) * width
            alpha = 0.6 if np_val == 2 else 0.9
            hatch = '' if np_val == 2 else '//'
            ax.bar(x + offset, speedups, width, label=f'{opt} np={np_val}',
                  color=COLORS[opt], alpha=alpha, hatch=hatch, edgecolor='black', linewidth=0.5)
            bar_idx += 1
    
    ax.axhline(y=1, color='red', linestyle='--', alpha=0.7, linewidth=2, label='Speedup=1')
    ax.axhline(y=2, color='orange', linestyle=':', alpha=0.5)
    ax.axhline(y=4, color='green', linestyle=':', alpha=0.5)
    
    ax.set_xlabel('Dimensione Input', fontsize=12, fontweight='bold')
    ax.set_ylabel('Speedup (SEQ/MPI)', fontsize=12, fontweight='bold')
    ax.set_title(f'Speedup MPI vs Sequenziale per Ottimizzatore\n(Grafi {type_label})', 
                fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(sizes)
    ax.legend(loc='upper left', fontsize=8, ncol=3)
    ax.grid(True, alpha=0.3, axis='y')
    ax.set_ylim(0, 5)
    
    plt.tight_layout()
    filepath = PLOTS_DIR / f"mpi_speedup_per_opt_{graph_type}.png"
    plt.savefig(filepath, dpi=DPI, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"[GRAFICO] {filepath.name}")


# =============================================================================
# EFFICIENZA
# =============================================================================

def plot_efficiency_by_optimizer(df, graph_type='iso'):
    """Efficienza per ogni ottimizzatore."""
    type_label = "Isomorfi" if graph_type == 'iso' else "Non Isomorfi"
    
    df_filtered = df[df['Type'] == graph_type]
    if df_filtered.empty:
        return
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    sizes = [s for s in SIZE_ORDER if s in df_filtered['Size'].unique()]
    x = np.arange(len(sizes))
    width = 0.1
    
    bar_idx = 0
    for opt in OPTIMIZERS:
        for np_val in PROC_COUNTS:
            opt_np_data = df_filtered[(df_filtered['Optimizer'] == opt) & (df_filtered['NumProcs'] == np_val)]
            efficiencies = [get_mean_value(opt_np_data, s, np_val, 'Efficiency') for s in sizes]
            
            offset = (bar_idx - 3.5) * width
            alpha = 0.6 if np_val == 2 else 0.9
            hatch = '' if np_val == 2 else '//'
            ax.bar(x + offset, efficiencies, width, label=f'{opt} np={np_val}',
                  color=COLORS[opt], alpha=alpha, hatch=hatch, edgecolor='black', linewidth=0.5)
            bar_idx += 1
    
    ax.axhline(y=100, color='green', linestyle='--', alpha=0.7, linewidth=2, label='Ideale 100%')
    ax.axhline(y=50, color='orange', linestyle=':', alpha=0.5)
    
    ax.set_xlabel('Dimensione Input', fontsize=12, fontweight='bold')
    ax.set_ylabel('Efficienza (%)', fontsize=12, fontweight='bold')
    ax.set_title(f'Efficienza Parallela MPI per Ottimizzatore\n(Grafi {type_label})', 
                fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(sizes)
    ax.legend(loc='upper right', fontsize=8, ncol=3)
    ax.grid(True, alpha=0.3, axis='y')
    ax.set_ylim(0, 120)
    
    plt.tight_layout()
    filepath = PLOTS_DIR / f"mpi_efficiency_per_opt_{graph_type}.png"
    plt.savefig(filepath, dpi=DPI, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"[GRAFICO] {filepath.name}")


# =============================================================================
# OVERHEAD
# =============================================================================

def plot_overhead_by_optimizer(df, graph_type='iso'):
    """Overhead per ogni ottimizzatore."""
    type_label = "Isomorfi" if graph_type == 'iso' else "Non Isomorfi"
    
    df_filtered = df[df['Type'] == graph_type]
    if df_filtered.empty:
        return
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    sizes = [s for s in SIZE_ORDER if s in df_filtered['Size'].unique()]
    x = np.arange(len(sizes))
    width = 0.1
    
    bar_idx = 0
    for opt in OPTIMIZERS:
        for np_val in PROC_COUNTS:
            opt_np_data = df_filtered[(df_filtered['Optimizer'] == opt) & (df_filtered['NumProcs'] == np_val)]
            overheads = [get_mean_value(opt_np_data, s, np_val, 'Overhead') for s in sizes]
            
            offset = (bar_idx - 3.5) * width
            alpha = 0.6 if np_val == 2 else 0.9
            hatch = '' if np_val == 2 else '//'
            ax.bar(x + offset, overheads, width, label=f'{opt} np={np_val}',
                  color=COLORS[opt], alpha=alpha, hatch=hatch, edgecolor='black', linewidth=0.5)
            bar_idx += 1
    
    ax.axhline(y=0, color='black', linestyle='-', alpha=0.3)
    
    ax.set_xlabel('Dimensione Input', fontsize=12, fontweight='bold')
    ax.set_ylabel('Overhead (s)', fontsize=12, fontweight='bold')
    ax.set_title(f'Overhead MPI (T_mpi × NP - T_seq)\n(Grafi {type_label})', 
                fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(sizes)
    ax.legend(loc='upper left', fontsize=8, ncol=3)
    ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    filepath = PLOTS_DIR / f"mpi_overhead_per_opt_{graph_type}.png"
    plt.savefig(filepath, dpi=DPI, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"[GRAFICO] {filepath.name}")


# =============================================================================
# THROUGHPUT
# =============================================================================

def plot_throughput_by_optimizer(df, graph_type='iso'):
    """Throughput per ogni ottimizzatore."""
    type_label = "Isomorfi" if graph_type == 'iso' else "Non Isomorfi"
    
    df_filtered = df[df['Type'] == graph_type]
    if df_filtered.empty:
        return
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    sizes = [s for s in SIZE_ORDER if s in df_filtered['Size'].unique()]
    x = np.arange(len(sizes))
    width = 0.1
    
    bar_idx = 0
    for opt in OPTIMIZERS:
        for np_val in PROC_COUNTS:
            opt_np_data = df_filtered[(df_filtered['Optimizer'] == opt) & (df_filtered['NumProcs'] == np_val)]
            throughputs = [get_mean_value(opt_np_data, s, np_val, 'Throughput_MB_s') for s in sizes]
            
            offset = (bar_idx - 3.5) * width
            alpha = 0.6 if np_val == 2 else 0.9
            hatch = '' if np_val == 2 else '//'
            ax.bar(x + offset, throughputs, width, label=f'{opt} np={np_val}',
                  color=COLORS[opt], alpha=alpha, hatch=hatch, edgecolor='black', linewidth=0.5)
            bar_idx += 1
    
    ax.set_xlabel('Dimensione Input', fontsize=12, fontweight='bold')
    ax.set_ylabel('Throughput (MB/s)', fontsize=12, fontweight='bold')
    ax.set_title(f'Throughput MPI per Ottimizzatore\n(Grafi {type_label})', 
                fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(sizes)
    ax.legend(loc='upper left', fontsize=8, ncol=3)
    ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    filepath = PLOTS_DIR / f"mpi_throughput_per_opt_{graph_type}.png"
    plt.savefig(filepath, dpi=DPI, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"[GRAFICO] {filepath.name}")


# =============================================================================
# CONFRONTO ISO vs DIFF
# =============================================================================

def plot_iso_vs_diff_comparison(df):
    """Confronto ISO vs DIFF."""
    print("\n[PLOT] Confronto ISO vs DIFF...")
    
    sizes = [s for s in SIZE_ORDER if s in df['Size'].unique()]
    np_val = 4 if 4 in df['NumProcs'].unique() else 2
    
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    
    x = np.arange(len(sizes))
    width = 0.35
    
    # Tempi
    ax1 = axes[0]
    iso_times = [df[(df['Type'] == 'iso') & (df['Size'] == s) & (df['NumProcs'] == np_val)]['Time_VF2_s'].mean() for s in sizes]
    diff_times = [df[(df['Type'] == 'diff') & (df['Size'] == s) & (df['NumProcs'] == np_val)]['Time_VF2_s'].mean() for s in sizes]
    
    ax1.bar(x - width/2, iso_times, width, label='Isomorfi', color=COLOR_ISO, alpha=0.8)
    ax1.bar(x + width/2, diff_times, width, label='Non Isomorfi', color=COLOR_DIFF, alpha=0.8)
    ax1.set_xlabel('Dimensione Input')
    ax1.set_ylabel('Tempo (s) - Log')
    ax1.set_title(f'Tempi ({np_val} proc)')
    ax1.set_xticks(x)
    ax1.set_xticklabels(sizes)
    ax1.set_yscale('log')
    ax1.legend()
    ax1.grid(True, alpha=0.3, axis='y')
    
    # Speedup
    ax2 = axes[1]
    iso_speedups = [df[(df['Type'] == 'iso') & (df['Size'] == s) & (df['NumProcs'] == np_val)]['Speedup'].mean() for s in sizes]
    diff_speedups = [df[(df['Type'] == 'diff') & (df['Size'] == s) & (df['NumProcs'] == np_val)]['Speedup'].mean() for s in sizes]
    
    ax2.bar(x - width/2, iso_speedups, width, label='Isomorfi', color=COLOR_ISO, alpha=0.8)
    ax2.bar(x + width/2, diff_speedups, width, label='Non Isomorfi', color=COLOR_DIFF, alpha=0.8)
    ax2.axhline(y=1, color='red', linestyle='--', linewidth=1.5, alpha=0.7)
    ax2.set_xlabel('Dimensione Input')
    ax2.set_ylabel('Speedup')
    ax2.set_title(f'Speedup ({np_val} proc)')
    ax2.set_xticks(x)
    ax2.set_xticklabels(sizes)
    ax2.legend()
    ax2.grid(True, alpha=0.3, axis='y')
    
    # Throughput
    ax3 = axes[2]
    iso_thr = [df[(df['Type'] == 'iso') & (df['Size'] == s) & (df['NumProcs'] == np_val)]['Throughput_MB_s'].mean() for s in sizes]
    diff_thr = [df[(df['Type'] == 'diff') & (df['Size'] == s) & (df['NumProcs'] == np_val)]['Throughput_MB_s'].mean() for s in sizes]
    
    ax3.bar(x - width/2, iso_thr, width, label='Isomorfi', color=COLOR_ISO, alpha=0.8)
    ax3.bar(x + width/2, diff_thr, width, label='Non Isomorfi', color=COLOR_DIFF, alpha=0.8)
    ax3.set_xlabel('Dimensione Input')
    ax3.set_ylabel('Throughput (MB/s)')
    ax3.set_title(f'Throughput ({np_val} proc)')
    ax3.set_xticks(x)
    ax3.set_xticklabels(sizes)
    ax3.legend()
    ax3.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    filepath = PLOTS_DIR / "mpi_comparison_iso_vs_diff.png"
    plt.savefig(filepath, dpi=DPI, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"[GRAFICO] {filepath.name}")


# =============================================================================
# TABELLA RIEPILOGATIVA
# =============================================================================

def print_summary_table(df, graph_type='iso'):
    """Stampa tabella riepilogativa."""
    type_label = "ISOMORFI" if graph_type == 'iso' else "NON ISOMORFI"
    
    df_filtered = df[df['Type'] == graph_type]
    if df_filtered.empty:
        return
    
    print(f"\n{'='*100}")
    print(f"RIEPILOGO MPI - GRAFI {type_label}")
    print(f"{'='*100}")
    
    for np_val in PROC_COUNTS:
        print(f"\n--- {np_val} PROCESSI ---")
        
        data = df_filtered[df_filtered['NumProcs'] == np_val]
        sizes = [s for s in SIZE_ORDER if s in data['Size'].unique()]
        
        print(f"\n{'Size':<8}", end="")
        for opt in OPTIMIZERS:
            print(f"{opt:>15}", end="")
        print()
        print(f"{'':8}", end="")
        for opt in OPTIMIZERS:
            print(f"{'T/S/Thr':>15}", end="")
        print()
        print("-" * (8 + len(OPTIMIZERS) * 15))
        
        for size in sizes:
            print(f"{size:<8}", end="")
            for opt in OPTIMIZERS:
                opt_data = data[data['Optimizer'] == opt]
                t = get_mean_value(opt_data, size, np_val, 'Time_VF2_s')
                s = get_mean_value(opt_data, size, np_val, 'Speedup')
                thr = get_mean_value(opt_data, size, np_val, 'Throughput_MB_s')
                print(f"{t:.2f}/{s:.1f}x/{thr:.0f}", end="  ")
            print()
    
    print("=" * 100)


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 70)
    print("VF2++ MPI - Confronto Ottimizzatori (Completo)")
    print("=" * 70)
    print()
    
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    
    print("Caricamento dati...")
    df = load_all_results()
    
    if df is None or df.empty:
        print("\n[ERRORE] Nessun dato trovato!")
        return
    
    print(f"\nTotale righe: {len(df)}")
    print(f"Tipi: {df['Type'].unique()}")
    
    # GRAFICI ISOMORFI
    print("\n" + "-" * 70)
    print("GENERAZIONE GRAFICI - GRAFI ISOMORFI")
    print("-" * 70)
    
    plot_time_comparison_by_procs(df, 'iso')
    plot_speedup_by_optimizer(df, 'iso')
    plot_efficiency_by_optimizer(df, 'iso')
    plot_overhead_by_optimizer(df, 'iso')
    plot_throughput_by_optimizer(df, 'iso')
    print_summary_table(df, 'iso')
    
    # GRAFICI NON ISOMORFI
    print("\n" + "-" * 70)
    print("GENERAZIONE GRAFICI - GRAFI NON ISOMORFI")
    print("-" * 70)
    
    plot_time_comparison_by_procs(df, 'diff')
    plot_speedup_by_optimizer(df, 'diff')
    plot_efficiency_by_optimizer(df, 'diff')
    plot_overhead_by_optimizer(df, 'diff')
    plot_throughput_by_optimizer(df, 'diff')
    print_summary_table(df, 'diff')
    
    # CONFRONTO ISO vs DIFF
    print("\n" + "-" * 70)
    print("CONFRONTO ISO vs DIFF")
    print("-" * 70)
    
    plot_iso_vs_diff_comparison(df)
    
    print(f"\n{'='*70}")
    print("COMPLETATO!")
    print(f"{'='*70}")
    print(f"\nGrafici salvati in: {PLOTS_DIR}")


if __name__ == "__main__":
    main()
