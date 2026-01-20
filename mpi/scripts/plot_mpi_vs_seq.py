#!/usr/bin/env python3
"""
==================================================================
VF2++ - Confronto Sequenziale vs MPI (Versione Completa)
==================================================================

Genera grafici che confrontano le performance della versione
sequenziale con la versione MPI.

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
SEQ_OUTPUT_DIR = PROJECT_ROOT / "sequential" / "output"
MPI_OUTPUT_DIR = SCRIPT_DIR.parent / "output"
PLOTS_DIR = SCRIPT_DIR.parent / "plots"

OPTIMIZERS = ["O0", "O1", "O2", "O3"]
PROC_COUNTS = [2, 4]
SIZE_ORDER = ['1MB', '50MB', '100MB', '200MB', '500MB']

COLOR_SEQ = '#3498db'
COLOR_MPI_2 = '#e74c3c'
COLOR_MPI_4 = '#2ecc71'
COLOR_ISO = '#3498db'
COLOR_DIFF = '#e74c3c'

plt.style.use('seaborn-v0_8-whitegrid')
DPI = 150

# =============================================================================
# FUNZIONI CARICAMENTO
# =============================================================================

def load_sequential_results():
    """Carica risultati sequenziali."""
    all_data = []
    
    for opt in OPTIMIZERS:
        csv_path = SEQ_OUTPUT_DIR / f"results_{opt}.csv"
        if csv_path.exists():
            try:
                df = pd.read_csv(csv_path)
                df['Optimizer'] = opt
                df['NumProcs'] = 1
                
                if 'Type' not in df.columns and 'Isomorphic' in df.columns:
                    df['Type'] = df['Isomorphic'].apply(lambda x: 'iso' if x == 1 else 'diff')
                
                # Calcola Throughput se non presente
                if 'Throughput_MB_s' not in df.columns and 'RAM_Graph_MB' in df.columns:
                    df['Throughput_MB_s'] = df.apply(
                        lambda r: r['RAM_Graph_MB'] / r['Time_VF2_s'] if r['Time_VF2_s'] > 0 else 0, axis=1)
                
                all_data.append(df)
                print(f"[OK] SEQ: {csv_path.name} ({len(df)} righe)")
            except Exception as e:
                print(f"[ERRORE] {csv_path.name}: {e}")
    
    if not all_data:
        return None
    
    return pd.concat(all_data, ignore_index=True)


def load_mpi_results():
    """Carica risultati MPI."""
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
                print(f"[OK] MPI: {csv_path.name} ({len(df)} righe)")
            except Exception as e:
                print(f"[ERRORE] {csv_path.name}: {e}")
    
    if not all_data:
        return None
    
    return pd.concat(all_data, ignore_index=True)


def get_seq_value(df, size, column, graph_type='iso', opt='O3'):
    """Ottiene valore sequenziale."""
    subset = df[(df['Size'] == size) & (df['Type'] == graph_type) & (df['Optimizer'] == opt)]
    if not subset.empty and column in subset.columns:
        return subset[column].mean()
    return 0


def get_mpi_value(df, size, np_val, column, graph_type='iso', opt='O3'):
    """Ottiene valore MPI."""
    subset = df[(df['Size'] == size) & (df['NumProcs'] == np_val) & 
                (df['Type'] == graph_type) & (df['Optimizer'] == opt)]
    if not subset.empty and column in subset.columns:
        return subset[column].mean()
    return 0


# =============================================================================
# GRAFICI CONFRONTO TEMPI
# =============================================================================

def plot_time_comparison(seq_df, mpi_df, graph_type='iso'):
    """Confronto tempi SEQ vs MPI per ogni ottimizzatore."""
    type_label = "Isomorfi" if graph_type == 'iso' else "Non Isomorfi"
    
    for opt in OPTIMIZERS:
        seq_opt = seq_df[seq_df['Optimizer'] == opt]
        mpi_opt = mpi_df[mpi_df['Optimizer'] == opt]
        
        if seq_opt.empty and mpi_opt.empty:
            continue
        
        sizes = [s for s in SIZE_ORDER if s in seq_opt['Size'].unique() or s in mpi_opt['Size'].unique()]
        if not sizes:
            continue
        
        fig, ax = plt.subplots(figsize=(12, 6))
        
        x = np.arange(len(sizes))
        width = 0.25
        
        # SEQ
        seq_times = [get_seq_value(seq_df, s, 'Time_VF2_s', graph_type, opt) or 0.001 for s in sizes]
        ax.bar(x - width, seq_times, width, label='SEQ', color=COLOR_SEQ, alpha=0.9)
        
        # MPI np=2
        mpi_2_times = [get_mpi_value(mpi_df, s, 2, 'Time_VF2_s', graph_type, opt) or 0.001 for s in sizes]
        ax.bar(x, mpi_2_times, width, label='MPI np=2', color=COLOR_MPI_2, alpha=0.8)
        
        # MPI np=4
        mpi_4_times = [get_mpi_value(mpi_df, s, 4, 'Time_VF2_s', graph_type, opt) or 0.001 for s in sizes]
        ax.bar(x + width, mpi_4_times, width, label='MPI np=4', color=COLOR_MPI_4, alpha=0.8)
        
        ax.set_xlabel('Dimensione Input', fontsize=12, fontweight='bold')
        ax.set_ylabel('Tempo VF2++ (s) - Scala Log', fontsize=12, fontweight='bold')
        ax.set_title(f'Confronto SEQ vs MPI - {opt}\n(Grafi {type_label})', fontsize=14, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(sizes)
        ax.set_yscale('log')
        ax.legend()
        ax.grid(True, alpha=0.3, axis='y')
        
        plt.tight_layout()
        filepath = PLOTS_DIR / f"seq_vs_mpi_{opt}_{graph_type}.png"
        plt.savefig(filepath, dpi=DPI, bbox_inches='tight', facecolor='white')
        plt.close()
        print(f"[GRAFICO] {filepath.name}")


# =============================================================================
# SPEEDUP CURVES
# =============================================================================

def plot_speedup_curves(seq_df, mpi_df, graph_type='iso'):
    """Curve di speedup."""
    type_label = "Isomorfi" if graph_type == 'iso' else "Non Isomorfi"
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    axes = axes.flatten()
    
    for idx, opt in enumerate(OPTIMIZERS):
        ax = axes[idx]
        
        sizes = [s for s in SIZE_ORDER if s in seq_df['Size'].unique()]
        
        markers = ['o', 's', '^', 'D', 'v']
        colors = plt.cm.viridis(np.linspace(0.2, 0.8, len(sizes)))
        
        for i, size in enumerate(sizes):
            seq_time = get_seq_value(seq_df, size, 'Time_VF2_s', graph_type, opt)
            if seq_time == 0:
                continue
            
            procs = [1] + PROC_COUNTS
            speedups = [1.0]
            
            for np_val in PROC_COUNTS:
                mpi_time = get_mpi_value(mpi_df, size, np_val, 'Time_VF2_s', graph_type, opt)
                speedups.append(seq_time / mpi_time if mpi_time > 0 else 0)
            
            ax.plot(procs, speedups, marker=markers[i % len(markers)], 
                   color=colors[i], linewidth=2, markersize=10, label=size)
        
        ax.plot([1, max(PROC_COUNTS)], [1, max(PROC_COUNTS)], 'k--', alpha=0.5, linewidth=2, label='Ideale')
        
        ax.set_xlabel('Numero Processi', fontsize=11)
        ax.set_ylabel('Speedup', fontsize=11)
        ax.set_title(f'Ottimizzatore {opt}', fontsize=12, fontweight='bold')
        ax.set_xticks([1] + PROC_COUNTS)
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3)
        ax.set_ylim(0, max(PROC_COUNTS) + 0.5)
    
    plt.suptitle(f'Speedup MPI vs Sequenziale (Grafi {type_label})', fontsize=14, fontweight='bold')
    plt.tight_layout()
    
    filepath = PLOTS_DIR / f"speedup_curves_{graph_type}.png"
    plt.savefig(filepath, dpi=DPI, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"[GRAFICO] {filepath.name}")


# =============================================================================
# EFFICIENZA
# =============================================================================

def plot_efficiency(seq_df, mpi_df, graph_type='iso'):
    """Efficienza parallela."""
    type_label = "Isomorfi" if graph_type == 'iso' else "Non Isomorfi"
    
    opt = 'O3'
    sizes = [s for s in SIZE_ORDER if s in seq_df['Size'].unique()]
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    x = np.arange(len(sizes))
    width = 0.35
    
    eff_2 = []
    eff_4 = []
    
    for size in sizes:
        seq_time = get_seq_value(seq_df, size, 'Time_VF2_s', graph_type, opt)
        
        mpi_2_time = get_mpi_value(mpi_df, size, 2, 'Time_VF2_s', graph_type, opt)
        eff_2.append((seq_time / mpi_2_time / 2 * 100) if mpi_2_time > 0 else 0)
        
        mpi_4_time = get_mpi_value(mpi_df, size, 4, 'Time_VF2_s', graph_type, opt)
        eff_4.append((seq_time / mpi_4_time / 4 * 100) if mpi_4_time > 0 else 0)
    
    ax.bar(x - width/2, eff_2, width, label='MPI np=2', color=COLOR_MPI_2, alpha=0.8)
    ax.bar(x + width/2, eff_4, width, label='MPI np=4', color=COLOR_MPI_4, alpha=0.8)
    
    ax.axhline(y=100, color='green', linestyle='--', alpha=0.7, linewidth=2, label='Ideale 100%')
    ax.axhline(y=50, color='orange', linestyle=':', alpha=0.7, linewidth=1.5)
    
    ax.set_xlabel('Dimensione Input', fontsize=12, fontweight='bold')
    ax.set_ylabel('Efficienza (%)', fontsize=12, fontweight='bold')
    ax.set_title(f'Efficienza Parallela MPI - {opt}\n(Grafi {type_label})', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(sizes)
    ax.legend()
    ax.grid(True, alpha=0.3, axis='y')
    ax.set_ylim(0, 120)
    
    plt.tight_layout()
    filepath = PLOTS_DIR / f"efficiency_{graph_type}.png"
    plt.savefig(filepath, dpi=DPI, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"[GRAFICO] {filepath.name}")


# =============================================================================
# OVERHEAD
# =============================================================================

def plot_overhead(seq_df, mpi_df, graph_type='iso'):
    """Overhead di parallelizzazione."""
    type_label = "Isomorfi" if graph_type == 'iso' else "Non Isomorfi"
    
    opt = 'O3'
    sizes = [s for s in SIZE_ORDER if s in seq_df['Size'].unique()]
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    x = np.arange(len(sizes))
    width = 0.35
    
    overhead_2 = []
    overhead_4 = []
    
    for size in sizes:
        seq_time = get_seq_value(seq_df, size, 'Time_VF2_s', graph_type, opt)
        
        mpi_2_time = get_mpi_value(mpi_df, size, 2, 'Time_VF2_s', graph_type, opt)
        overhead_2.append(max(0.001, mpi_2_time * 2 - seq_time) if mpi_2_time > 0 else 0.001)
        
        mpi_4_time = get_mpi_value(mpi_df, size, 4, 'Time_VF2_s', graph_type, opt)
        overhead_4.append(max(0.001, mpi_4_time * 4 - seq_time) if mpi_4_time > 0 else 0.001)
    
    ax.bar(x - width/2, overhead_2, width, label='MPI np=2', color=COLOR_MPI_2, alpha=0.8)
    ax.bar(x + width/2, overhead_4, width, label='MPI np=4', color=COLOR_MPI_4, alpha=0.8)
    
    ax.set_xlabel('Dimensione Input', fontsize=12, fontweight='bold')
    ax.set_ylabel('Overhead (s) - Scala Log', fontsize=12, fontweight='bold')
    ax.set_title(f'Overhead MPI - {opt}\n(Grafi {type_label})', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(sizes)
    ax.set_yscale('log')
    ax.legend()
    ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    filepath = PLOTS_DIR / f"overhead_{graph_type}.png"
    plt.savefig(filepath, dpi=DPI, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"[GRAFICO] {filepath.name}")


# =============================================================================
# THROUGHPUT
# =============================================================================

def plot_throughput_comparison(seq_df, mpi_df, graph_type='iso'):
    """Confronto throughput SEQ vs MPI."""
    type_label = "Isomorfi" if graph_type == 'iso' else "Non Isomorfi"
    
    opt = 'O3'
    sizes = [s for s in SIZE_ORDER if s in seq_df['Size'].unique()]
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    x = np.arange(len(sizes))
    width = 0.25
    
    # SEQ throughput
    seq_thr = [get_seq_value(seq_df, s, 'Throughput_MB_s', graph_type, opt) for s in sizes]
    ax.bar(x - width, seq_thr, width, label='SEQ', color=COLOR_SEQ, alpha=0.9)
    
    # MPI np=2
    mpi_2_thr = [get_mpi_value(mpi_df, s, 2, 'Throughput_MB_s', graph_type, opt) for s in sizes]
    ax.bar(x, mpi_2_thr, width, label='MPI np=2', color=COLOR_MPI_2, alpha=0.8)
    
    # MPI np=4
    mpi_4_thr = [get_mpi_value(mpi_df, s, 4, 'Throughput_MB_s', graph_type, opt) for s in sizes]
    ax.bar(x + width, mpi_4_thr, width, label='MPI np=4', color=COLOR_MPI_4, alpha=0.8)
    
    ax.set_xlabel('Dimensione Input', fontsize=12, fontweight='bold')
    ax.set_ylabel('Throughput (MB/s)', fontsize=12, fontweight='bold')
    ax.set_title(f'Throughput: SEQ vs MPI - {opt}\n(Grafi {type_label})', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(sizes)
    ax.legend()
    ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    filepath = PLOTS_DIR / f"throughput_seq_vs_mpi_{graph_type}.png"
    plt.savefig(filepath, dpi=DPI, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"[GRAFICO] {filepath.name}")


# =============================================================================
# SUMMARY
# =============================================================================

def plot_summary_all_optimizers(seq_df, mpi_df, graph_type='iso'):
    """Speedup riassuntivo per tutti gli ottimizzatori."""
    type_label = "Isomorfi" if graph_type == 'iso' else "Non Isomorfi"
    
    np_val = 4
    sizes = [s for s in SIZE_ORDER if s in seq_df['Size'].unique()]
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    x = np.arange(len(sizes))
    width = 0.2
    colors = {'O0': '#e74c3c', 'O1': '#f39c12', 'O2': '#3498db', 'O3': '#2ecc71'}
    
    for i, opt in enumerate(OPTIMIZERS):
        speedups = []
        for size in sizes:
            seq_time = get_seq_value(seq_df, size, 'Time_VF2_s', graph_type, opt)
            mpi_time = get_mpi_value(mpi_df, size, np_val, 'Time_VF2_s', graph_type, opt)
            speedups.append(seq_time / mpi_time if mpi_time > 0 else 0)
        
        offset = (i - 1.5) * width
        ax.bar(x + offset, speedups, width, label=opt, color=colors[opt], alpha=0.8)
    
    ax.axhline(y=1, color='red', linestyle='--', alpha=0.7, linewidth=2, label='Speedup=1')
    ax.axhline(y=np_val, color='green', linestyle=':', alpha=0.7, linewidth=2, label=f'Ideale ({np_val}x)')
    
    ax.set_xlabel('Dimensione Input', fontsize=12, fontweight='bold')
    ax.set_ylabel(f'Speedup (SEQ / MPI np={np_val})', fontsize=12, fontweight='bold')
    ax.set_title(f'Speedup MPI - Tutti gli Ottimizzatori\n(np={np_val}, Grafi {type_label})', 
                fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(sizes)
    ax.legend()
    ax.grid(True, alpha=0.3, axis='y')
    ax.set_ylim(0, np_val + 1)
    
    plt.tight_layout()
    filepath = PLOTS_DIR / f"speedup_summary_{graph_type}.png"
    plt.savefig(filepath, dpi=DPI, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"[GRAFICO] {filepath.name}")


def plot_iso_vs_diff(seq_df, mpi_df):
    """Confronto ISO vs DIFF."""
    print("\n[PLOT] Confronto ISO vs DIFF...")
    
    opt = 'O3'
    np_val = 4
    sizes = [s for s in SIZE_ORDER if s in seq_df['Size'].unique()]
    
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    
    x = np.arange(len(sizes))
    width = 0.35
    
    # Tempi
    ax1 = axes[0]
    iso_times = [get_mpi_value(mpi_df, s, np_val, 'Time_VF2_s', 'iso', opt) for s in sizes]
    diff_times = [get_mpi_value(mpi_df, s, np_val, 'Time_VF2_s', 'diff', opt) for s in sizes]
    
    ax1.bar(x - width/2, iso_times, width, label='Isomorfi', color=COLOR_ISO, alpha=0.8)
    ax1.bar(x + width/2, diff_times, width, label='Non Isomorfi', color=COLOR_DIFF, alpha=0.8)
    ax1.set_xlabel('Dimensione Input')
    ax1.set_ylabel('Tempo (s) - Log')
    ax1.set_title(f'Tempi MPI ({np_val} proc)')
    ax1.set_xticks(x)
    ax1.set_xticklabels(sizes)
    ax1.set_yscale('log')
    ax1.legend()
    ax1.grid(True, alpha=0.3, axis='y')
    
    # Speedup
    ax2 = axes[1]
    iso_speedups = []
    diff_speedups = []
    for size in sizes:
        seq_iso = get_seq_value(seq_df, size, 'Time_VF2_s', 'iso', opt)
        seq_diff = get_seq_value(seq_df, size, 'Time_VF2_s', 'diff', opt)
        mpi_iso = get_mpi_value(mpi_df, size, np_val, 'Time_VF2_s', 'iso', opt)
        mpi_diff = get_mpi_value(mpi_df, size, np_val, 'Time_VF2_s', 'diff', opt)
        iso_speedups.append(seq_iso / mpi_iso if mpi_iso > 0 else 0)
        diff_speedups.append(seq_diff / mpi_diff if mpi_diff > 0 else 0)
    
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
    iso_thr = [get_mpi_value(mpi_df, s, np_val, 'Throughput_MB_s', 'iso', opt) for s in sizes]
    diff_thr = [get_mpi_value(mpi_df, s, np_val, 'Throughput_MB_s', 'diff', opt) for s in sizes]
    
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


def print_comparison_table(seq_df, mpi_df, graph_type='iso'):
    """Tabella comparativa."""
    type_label = "ISOMORFI" if graph_type == 'iso' else "NON ISOMORFI"
    
    print(f"\n{'='*120}")
    print(f"CONFRONTO SEQ vs MPI - GRAFI {type_label}")
    print(f"{'='*120}")
    
    for opt in OPTIMIZERS:
        print(f"\n{'─'*120}")
        print(f"OTTIMIZZATORE: {opt}")
        print(f"{'─'*120}")
        
        sizes = [s for s in SIZE_ORDER if s in seq_df['Size'].unique()]
        
        print(f"\n{'Size':<8} {'SEQ':>15} {'MPI-2':>15} {'MPI-4':>15} {'Spd-2':>10} {'Spd-4':>10} {'Thr-SEQ':>10} {'Thr-4':>10}")
        print("-" * 100)
        
        for size in sizes:
            seq_t = get_seq_value(seq_df, size, 'Time_VF2_s', graph_type, opt)
            mpi_2_t = get_mpi_value(mpi_df, size, 2, 'Time_VF2_s', graph_type, opt)
            mpi_4_t = get_mpi_value(mpi_df, size, 4, 'Time_VF2_s', graph_type, opt)
            
            spd_2 = seq_t / mpi_2_t if mpi_2_t > 0 else 0
            spd_4 = seq_t / mpi_4_t if mpi_4_t > 0 else 0
            
            thr_seq = get_seq_value(seq_df, size, 'Throughput_MB_s', graph_type, opt)
            thr_4 = get_mpi_value(mpi_df, size, 4, 'Throughput_MB_s', graph_type, opt)
            
            print(f"{size:<8} {seq_t:>14.4f}s {mpi_2_t:>14.4f}s {mpi_4_t:>14.4f}s {spd_2:>9.2f}x {spd_4:>9.2f}x {thr_seq:>9.0f} {thr_4:>9.0f}")
    
    print(f"\n{'='*120}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 70)
    print("VF2++ - Confronto SEQ vs MPI (Completo)")
    print("=" * 70)
    print()
    
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    
    print("Caricamento dati...")
    seq_df = load_sequential_results()
    mpi_df = load_mpi_results()
    
    if seq_df is None or seq_df.empty:
        print("\n[ERRORE] Nessun dato sequenziale!")
        return
    
    if mpi_df is None or mpi_df.empty:
        print("\n[ERRORE] Nessun dato MPI!")
        return
    
    print(f"\nDati: SEQ={len(seq_df)}, MPI={len(mpi_df)}")
    
    # GRAFICI ISOMORFI
    print("\n" + "-" * 70)
    print("GENERAZIONE GRAFICI - GRAFI ISOMORFI")
    print("-" * 70)
    
    plot_time_comparison(seq_df, mpi_df, 'iso')
    plot_speedup_curves(seq_df, mpi_df, 'iso')
    plot_efficiency(seq_df, mpi_df, 'iso')
    plot_overhead(seq_df, mpi_df, 'iso')
    plot_throughput_comparison(seq_df, mpi_df, 'iso')
    plot_summary_all_optimizers(seq_df, mpi_df, 'iso')
    print_comparison_table(seq_df, mpi_df, 'iso')
    
    # GRAFICI NON ISOMORFI
    print("\n" + "-" * 70)
    print("GENERAZIONE GRAFICI - GRAFI NON ISOMORFI")
    print("-" * 70)
    
    plot_time_comparison(seq_df, mpi_df, 'diff')
    plot_speedup_curves(seq_df, mpi_df, 'diff')
    plot_efficiency(seq_df, mpi_df, 'diff')
    plot_overhead(seq_df, mpi_df, 'diff')
    plot_throughput_comparison(seq_df, mpi_df, 'diff')
    plot_summary_all_optimizers(seq_df, mpi_df, 'diff')
    print_comparison_table(seq_df, mpi_df, 'diff')
    
    # CONFRONTO ISO vs DIFF
    print("\n" + "-" * 70)
    print("CONFRONTO ISO vs DIFF")
    print("-" * 70)
    
    plot_iso_vs_diff(seq_df, mpi_df)
    
    print(f"\n{'='*70}")
    print("COMPLETATO!")
    print(f"{'='*70}")
    print(f"\nGrafici salvati in: {PLOTS_DIR}")


if __name__ == "__main__":
    main()
