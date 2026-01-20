#!/usr/bin/env python3
"""
==================================================================
VF2++ OpenMP - Analisi e Visualizzazione Performance (Completo)
==================================================================

Genera grafici per la versione OpenMP:
- Confronto tempi per numero di thread
- Confronto diretto SEQ vs OpenMP
- Speedup rispetto alla versione sequenziale
- Efficienza parallela
- Overhead di parallelizzazione
- Throughput (MB/s)

SEPARATI per grafi ISOMORFI e NON ISOMORFI

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
SEQ_OUTPUT_DIR = PROJECT_ROOT / "sequential" / "output"
OMP_OUTPUT_DIR = SCRIPT_DIR.parent / "output"
PLOTS_DIR = SCRIPT_DIR.parent / "plots"

OPTIMIZERS = ["O0", "O1", "O2", "O3"]
THREAD_COUNTS = [1, 2, 4, 8]
SIZE_ORDER = ['1MB', '50MB', '100MB', '200MB', '500MB']

# Colori
COLORS = {'O0': '#e74c3c', 'O1': '#f39c12', 'O2': '#3498db', 'O3': '#2ecc71'}
COLOR_SEQ = '#3498db'
COLOR_OMP = {'1': '#95a5a6', '2': '#f39c12', '4': '#e74c3c', '8': '#9b59b6'}
COLOR_ISO = '#3498db'
COLOR_DIFF = '#e74c3c'

plt.style.use('seaborn-v0_8-whitegrid')
DPI = 150

# =============================================================================
# FUNZIONI DI CARICAMENTO
# =============================================================================

def load_omp_results():
    """Carica tutti i CSV dei risultati OpenMP."""
    all_data = []
    
    for opt in OPTIMIZERS:
        csv_path = OMP_OUTPUT_DIR / f"results_{opt}.csv"
        if csv_path.exists():
            try:
                df = pd.read_csv(csv_path)
                df['Optimizer'] = opt
                all_data.append(df)
                print(f"[OK] OMP: {csv_path.name} ({len(df)} righe)")
            except Exception as e:
                print(f"[ERRORE] {csv_path.name}: {e}")
        else:
            print(f"[SKIP] Non trovato: {csv_path.name}")
    
    if not all_data:
        return None
    
    return pd.concat(all_data, ignore_index=True)


def load_seq_results():
    """Carica risultati sequenziali."""
    all_data = []
    
    for opt in OPTIMIZERS:
        csv_path = SEQ_OUTPUT_DIR / f"results_{opt}.csv"
        if csv_path.exists():
            try:
                df = pd.read_csv(csv_path)
                df['Optimizer'] = opt
                df['NumThreads'] = 0  # Marker per SEQ
                
                # Assicura colonna Type
                if 'Type' not in df.columns and 'Isomorphic' in df.columns:
                    df['Type'] = df['Isomorphic'].apply(lambda x: 'iso' if x == 1 else 'diff')
                
                all_data.append(df)
                print(f"[OK] SEQ: {csv_path.name} ({len(df)} righe)")
            except Exception as e:
                print(f"[ERRORE] {csv_path.name}: {e}")
        else:
            print(f"[SKIP] SEQ non trovato: {csv_path.name}")
    
    if not all_data:
        return None
    
    return pd.concat(all_data, ignore_index=True)


def get_mean_value(df, size, nt, column, graph_type='iso'):
    """Ottiene il valore medio per una data configurazione."""
    subset = df[(df['Size'] == size) & (df['NumThreads'] == nt) & (df['Type'] == graph_type)]
    values = subset[column].values
    if len(values) > 0:
        return np.mean(values)
    return 0


def get_seq_time(seq_df, size, graph_type='iso', opt='O3'):
    """Ottiene il tempo sequenziale."""
    subset = seq_df[(seq_df['Size'] == size) & (seq_df['Type'] == graph_type) & (seq_df['Optimizer'] == opt)]
    if not subset.empty and 'Time_VF2_s' in subset.columns:
        return subset['Time_VF2_s'].mean()
    return 0


# =============================================================================
# GRAFICI TEMPI
# =============================================================================

def plot_time_by_threads(df, graph_type='iso'):
    """Tempo VF2++ per numero di thread."""
    type_label = "Isomorfi" if graph_type == 'iso' else "Non Isomorfi"
    
    print(f"\n[PLOT] Tempo per thread ({type_label})...")
    
    df_filtered = df[df['Type'] == graph_type]
    if df_filtered.empty:
        print(f"[SKIP] Nessun dato per grafi {type_label}")
        return
    
    sizes = [s for s in SIZE_ORDER if s in df_filtered['Size'].unique()]
    threads = sorted([t for t in df_filtered['NumThreads'].unique() if t > 0])
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    x = np.arange(len(sizes))
    width = 0.8 / len(threads)
    
    for i, nt in enumerate(threads):
        times = []
        for size in sizes:
            t = get_mean_value(df_filtered, size, nt, 'Time_VF2_s', graph_type)
            times.append(t if t > 0 else 0.001)
        
        offset = (i - len(threads)/2 + 0.5) * width
        color = COLOR_OMP.get(str(nt), '#333333')
        ax.bar(x + offset, times, width, label=f'{nt} thread', color=color, alpha=0.8)
    
    ax.set_xlabel('Dimensione Input', fontsize=12, fontweight='bold')
    ax.set_ylabel('Tempo VF2++ (s) - Scala Log', fontsize=12, fontweight='bold')
    ax.set_title(f'Tempo VF2++ OpenMP per Numero Thread\n(Grafi {type_label})', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(sizes)
    ax.set_yscale('log')
    ax.legend(title='Thread')
    ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    filepath = PLOTS_DIR / f"omp_time_by_threads_{graph_type}.png"
    plt.savefig(filepath, dpi=DPI, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"[SALVATO] {filepath.name}")


# =============================================================================
# CONFRONTO SEQ vs OMP
# =============================================================================

def plot_seq_vs_omp(omp_df, seq_df, graph_type='iso'):
    """Confronto diretto SEQ vs OpenMP."""
    type_label = "Isomorfi" if graph_type == 'iso' else "Non Isomorfi"
    
    print(f"\n[PLOT] Confronto SEQ vs OMP ({type_label})...")
    
    for opt in OPTIMIZERS:
        omp_opt = omp_df[(omp_df['Optimizer'] == opt) & (omp_df['Type'] == graph_type)]
        seq_opt = seq_df[(seq_df['Optimizer'] == opt) & (seq_df['Type'] == graph_type)]
        
        if omp_opt.empty:
            continue
        
        sizes = [s for s in SIZE_ORDER if s in omp_opt['Size'].unique()]
        threads = sorted([t for t in omp_opt['NumThreads'].unique() if t > 0])
        
        fig, ax = plt.subplots(figsize=(12, 6))
        
        x = np.arange(len(sizes))
        n_bars = len(threads) + 1  # +1 per SEQ
        width = 0.8 / n_bars
        
        # Barra SEQ
        seq_times = []
        for size in sizes:
            t = get_seq_time(seq_df, size, graph_type, opt)
            seq_times.append(t if t > 0 else 0.001)
        
        offset = (0 - n_bars/2 + 0.5) * width
        ax.bar(x + offset, seq_times, width, label='SEQ', color=COLOR_SEQ, alpha=0.9)
        
        # Barre OMP
        for i, nt in enumerate(threads):
            times = []
            for size in sizes:
                t = get_mean_value(omp_opt, size, nt, 'Time_VF2_s', graph_type)
                times.append(t if t > 0 else 0.001)
            
            offset = (i + 1 - n_bars/2 + 0.5) * width
            color = COLOR_OMP.get(str(nt), '#333333')
            ax.bar(x + offset, times, width, label=f'OMP {nt}T', color=color, alpha=0.8)
        
        ax.set_xlabel('Dimensione Input', fontsize=12, fontweight='bold')
        ax.set_ylabel('Tempo VF2++ (s) - Scala Log', fontsize=12, fontweight='bold')
        ax.set_title(f'Confronto SEQ vs OpenMP - {opt}\n(Grafi {type_label})', fontsize=14, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(sizes)
        ax.set_yscale('log')
        ax.legend()
        ax.grid(True, alpha=0.3, axis='y')
        
        plt.tight_layout()
        filepath = PLOTS_DIR / f"seq_vs_omp_{opt}_{graph_type}.png"
        plt.savefig(filepath, dpi=DPI, bbox_inches='tight', facecolor='white')
        plt.close()
        print(f"[SALVATO] {filepath.name}")


# =============================================================================
# SPEEDUP
# =============================================================================

def plot_speedup(df, graph_type='iso'):
    """Speedup rispetto alla versione sequenziale."""
    type_label = "Isomorfi" if graph_type == 'iso' else "Non Isomorfi"
    
    print(f"\n[PLOT] Speedup ({type_label})...")
    
    df_filtered = df[df['Type'] == graph_type]
    if df_filtered.empty:
        return
    
    sizes = [s for s in SIZE_ORDER if s in df_filtered['Size'].unique()]
    threads = sorted([t for t in df_filtered['NumThreads'].unique() if t > 1])
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    x = np.arange(len(sizes))
    width = 0.8 / len(threads)
    
    for i, nt in enumerate(threads):
        speedups = []
        for size in sizes:
            s = get_mean_value(df_filtered, size, nt, 'Speedup', graph_type)
            speedups.append(s)
        
        offset = (i - len(threads)/2 + 0.5) * width
        color = COLOR_OMP.get(str(nt), '#333333')
        ax.bar(x + offset, speedups, width, label=f'{nt} thread', color=color, alpha=0.8)
    
    ax.axhline(y=1, color='red', linestyle='--', linewidth=2, alpha=0.7, label='Speedup=1')
    max_threads = max(threads) if threads else 4
    ax.axhline(y=max_threads, color='green', linestyle=':', linewidth=1.5, alpha=0.5, label=f'Ideale ({max_threads}x)')
    
    ax.set_xlabel('Dimensione Input', fontsize=12, fontweight='bold')
    ax.set_ylabel('Speedup (SEQ / OpenMP)', fontsize=12, fontweight='bold')
    ax.set_title(f'Speedup OpenMP vs Sequenziale\n(Grafi {type_label})', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(sizes)
    ax.legend(loc='upper left')
    ax.grid(True, alpha=0.3, axis='y')
    ax.set_ylim(0, max_threads + 1)
    
    plt.tight_layout()
    filepath = PLOTS_DIR / f"omp_speedup_{graph_type}.png"
    plt.savefig(filepath, dpi=DPI, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"[SALVATO] {filepath.name}")


def plot_speedup_curves(df, graph_type='iso'):
    """Curve di speedup al variare dei thread."""
    type_label = "Isomorfi" if graph_type == 'iso' else "Non Isomorfi"
    
    print(f"\n[PLOT] Curve speedup ({type_label})...")
    
    df_filtered = df[df['Type'] == graph_type]
    if df_filtered.empty:
        return
    
    sizes = [s for s in SIZE_ORDER if s in df_filtered['Size'].unique()]
    threads = sorted(df_filtered['NumThreads'].unique())
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    markers = ['o', 's', '^', 'D', 'v']
    colors = plt.cm.viridis(np.linspace(0.2, 0.8, len(sizes)))
    
    for i, size in enumerate(sizes):
        speedups = []
        for nt in threads:
            s = get_mean_value(df_filtered, size, nt, 'Speedup', graph_type)
            if nt == 1 and s == 0:
                s = 1.0  # 1 thread = speedup 1
            speedups.append(s)
        
        ax.plot(threads, speedups, marker=markers[i % len(markers)],
               color=colors[i], linewidth=2, markersize=10, label=size)
    
    # Linea ideale
    ax.plot(threads, threads, 'k--', alpha=0.5, linewidth=2, label='Ideale')
    
    ax.set_xlabel('Numero Thread', fontsize=12, fontweight='bold')
    ax.set_ylabel('Speedup', fontsize=12, fontweight='bold')
    ax.set_title(f'Curve di Speedup OpenMP\n(Grafi {type_label})', fontsize=14, fontweight='bold')
    ax.set_xticks(threads)
    ax.legend(loc='upper left')
    ax.grid(True, alpha=0.3)
    max_t = max(threads) if threads else 8
    ax.set_ylim(0, max_t + 0.5)
    
    plt.tight_layout()
    filepath = PLOTS_DIR / f"omp_speedup_curves_{graph_type}.png"
    plt.savefig(filepath, dpi=DPI, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"[SALVATO] {filepath.name}")


# =============================================================================
# EFFICIENZA
# =============================================================================

def plot_efficiency(df, graph_type='iso'):
    """Efficienza parallela."""
    type_label = "Isomorfi" if graph_type == 'iso' else "Non Isomorfi"
    
    print(f"\n[PLOT] Efficienza ({type_label})...")
    
    df_filtered = df[df['Type'] == graph_type]
    if df_filtered.empty:
        return
    
    sizes = [s for s in SIZE_ORDER if s in df_filtered['Size'].unique()]
    threads = sorted([t for t in df_filtered['NumThreads'].unique() if t > 1])
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    x = np.arange(len(sizes))
    width = 0.8 / len(threads)
    
    for i, nt in enumerate(threads):
        efficiencies = []
        for size in sizes:
            e = get_mean_value(df_filtered, size, nt, 'Efficiency', graph_type)
            efficiencies.append(e)
        
        offset = (i - len(threads)/2 + 0.5) * width
        color = COLOR_OMP.get(str(nt), '#333333')
        ax.bar(x + offset, efficiencies, width, label=f'{nt} thread', color=color, alpha=0.8)
    
    ax.axhline(y=100, color='green', linestyle='--', linewidth=2, alpha=0.7, label='Ideale 100%')
    ax.axhline(y=50, color='orange', linestyle=':', linewidth=1.5, alpha=0.5, label='50%')
    
    ax.set_xlabel('Dimensione Input', fontsize=12, fontweight='bold')
    ax.set_ylabel('Efficienza (%)', fontsize=12, fontweight='bold')
    ax.set_title(f'Efficienza Parallela OpenMP\n(Grafi {type_label})', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(sizes)
    ax.legend(loc='upper right')
    ax.grid(True, alpha=0.3, axis='y')
    ax.set_ylim(0, 120)
    
    plt.tight_layout()
    filepath = PLOTS_DIR / f"omp_efficiency_{graph_type}.png"
    plt.savefig(filepath, dpi=DPI, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"[SALVATO] {filepath.name}")


# =============================================================================
# OVERHEAD
# =============================================================================

def plot_overhead(df, graph_type='iso'):
    """Overhead di parallelizzazione."""
    type_label = "Isomorfi" if graph_type == 'iso' else "Non Isomorfi"
    
    print(f"\n[PLOT] Overhead ({type_label})...")
    
    df_filtered = df[df['Type'] == graph_type]
    if df_filtered.empty:
        return
    
    sizes = [s for s in SIZE_ORDER if s in df_filtered['Size'].unique()]
    threads = sorted([t for t in df_filtered['NumThreads'].unique() if t > 1])
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    x = np.arange(len(sizes))
    width = 0.8 / len(threads)
    
    for i, nt in enumerate(threads):
        overheads = []
        for size in sizes:
            o = get_mean_value(df_filtered, size, nt, 'Overhead', graph_type)
            overheads.append(o)
        
        offset = (i - len(threads)/2 + 0.5) * width
        color = COLOR_OMP.get(str(nt), '#333333')
        ax.bar(x + offset, overheads, width, label=f'{nt} thread', color=color, alpha=0.8)
    
    ax.axhline(y=0, color='black', linestyle='-', linewidth=1, alpha=0.3)
    
    ax.set_xlabel('Dimensione Input', fontsize=12, fontweight='bold')
    ax.set_ylabel('Overhead (s)', fontsize=12, fontweight='bold')
    ax.set_title(f'Overhead OpenMP (T_omp × NT - T_seq)\n(Grafi {type_label})', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(sizes)
    ax.legend(loc='upper left')
    ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    filepath = PLOTS_DIR / f"omp_overhead_{graph_type}.png"
    plt.savefig(filepath, dpi=DPI, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"[SALVATO] {filepath.name}")


# =============================================================================
# THROUGHPUT
# =============================================================================

def plot_throughput(df, graph_type='iso'):
    """Throughput (MB/s) per numero thread."""
    type_label = "Isomorfi" if graph_type == 'iso' else "Non Isomorfi"
    
    print(f"\n[PLOT] Throughput ({type_label})...")
    
    df_filtered = df[df['Type'] == graph_type]
    if df_filtered.empty:
        return
    
    # Calcola throughput se non presente
    if 'Throughput_MB_s' not in df_filtered.columns:
        df_filtered = df_filtered.copy()
        df_filtered['Throughput_MB_s'] = df_filtered.apply(
            lambda row: row['RAM_MB'] / row['Time_VF2_s'] if row['Time_VF2_s'] > 0 else 0, axis=1)
    
    sizes = [s for s in SIZE_ORDER if s in df_filtered['Size'].unique()]
    threads = sorted([t for t in df_filtered['NumThreads'].unique() if t > 0])
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    x = np.arange(len(sizes))
    width = 0.8 / len(threads)
    
    for i, nt in enumerate(threads):
        throughputs = []
        for size in sizes:
            t = get_mean_value(df_filtered, size, nt, 'Throughput_MB_s', graph_type)
            throughputs.append(t)
        
        offset = (i - len(threads)/2 + 0.5) * width
        color = COLOR_OMP.get(str(nt), '#333333')
        bars = ax.bar(x + offset, throughputs, width, label=f'{nt} thread', color=color, alpha=0.8)
        
        # Annotazioni
        for bar, val in zip(bars, throughputs):
            if val > 0:
                ax.annotate(f'{val:.0f}', xy=(bar.get_x() + bar.get_width()/2, bar.get_height()),
                           xytext=(0, 3), textcoords="offset points", ha='center', va='bottom',
                           fontsize=7, fontweight='bold')
    
    ax.set_xlabel('Dimensione Input', fontsize=12, fontweight='bold')
    ax.set_ylabel('Throughput (MB/s)', fontsize=12, fontweight='bold')
    ax.set_title(f'Throughput OpenMP\n(Grafi {type_label})', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(sizes)
    ax.legend(title='Thread')
    ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    filepath = PLOTS_DIR / f"omp_throughput_{graph_type}.png"
    plt.savefig(filepath, dpi=DPI, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"[SALVATO] {filepath.name}")


def plot_throughput_seq_vs_omp(omp_df, seq_df, graph_type='iso'):
    """Confronto throughput SEQ vs OMP."""
    type_label = "Isomorfi" if graph_type == 'iso' else "Non Isomorfi"
    
    print(f"\n[PLOT] Throughput SEQ vs OMP ({type_label})...")
    
    opt = 'O3'
    omp_opt = omp_df[(omp_df['Optimizer'] == opt) & (omp_df['Type'] == graph_type)]
    seq_opt = seq_df[(seq_df['Optimizer'] == opt) & (seq_df['Type'] == graph_type)]
    
    if omp_opt.empty:
        return
    
    sizes = [s for s in SIZE_ORDER if s in omp_opt['Size'].unique()]
    threads = sorted([t for t in omp_opt['NumThreads'].unique() if t > 0])
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    x = np.arange(len(sizes))
    n_bars = len(threads) + 1
    width = 0.8 / n_bars
    
    # SEQ throughput
    seq_throughputs = []
    for size in sizes:
        row = seq_opt[seq_opt['Size'] == size]
        if not row.empty and 'Time_VF2_s' in row.columns and row['Time_VF2_s'].values[0] > 0:
            ram = row['RAM_Graph_MB'].values[0] if 'RAM_Graph_MB' in row.columns else 0
            t = ram / row['Time_VF2_s'].values[0]
            seq_throughputs.append(t)
        else:
            seq_throughputs.append(0)
    
    offset = (0 - n_bars/2 + 0.5) * width
    ax.bar(x + offset, seq_throughputs, width, label='SEQ', color=COLOR_SEQ, alpha=0.9)
    
    # OMP throughput
    for i, nt in enumerate(threads):
        throughputs = []
        for size in sizes:
            t = get_mean_value(omp_opt, size, nt, 'Throughput_MB_s', graph_type)
            if t == 0:
                # Calcola manualmente
                row = omp_opt[(omp_opt['Size'] == size) & (omp_opt['NumThreads'] == nt)]
                if not row.empty and row['Time_VF2_s'].values[0] > 0:
                    t = row['RAM_MB'].values[0] / row['Time_VF2_s'].values[0]
            throughputs.append(t)
        
        offset = (i + 1 - n_bars/2 + 0.5) * width
        color = COLOR_OMP.get(str(nt), '#333333')
        ax.bar(x + offset, throughputs, width, label=f'OMP {nt}T', color=color, alpha=0.8)
    
    ax.set_xlabel('Dimensione Input', fontsize=12, fontweight='bold')
    ax.set_ylabel('Throughput (MB/s)', fontsize=12, fontweight='bold')
    ax.set_title(f'Throughput: SEQ vs OpenMP - {opt}\n(Grafi {type_label})', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(sizes)
    ax.legend()
    ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    filepath = PLOTS_DIR / f"omp_throughput_seq_vs_omp_{graph_type}.png"
    plt.savefig(filepath, dpi=DPI, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"[SALVATO] {filepath.name}")


# =============================================================================
# CONFRONTO ISO vs DIFF
# =============================================================================

def plot_iso_vs_diff(omp_df):
    """Confronto ISO vs DIFF."""
    print("\n[PLOT] Confronto ISO vs DIFF...")
    
    sizes = [s for s in SIZE_ORDER if s in omp_df['Size'].unique()]
    nt = 4 if 4 in omp_df['NumThreads'].unique() else omp_df['NumThreads'].max()
    
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    
    x = np.arange(len(sizes))
    width = 0.35
    
    # Tempi
    ax1 = axes[0]
    iso_times = [get_mean_value(omp_df, s, nt, 'Time_VF2_s', 'iso') for s in sizes]
    diff_times = [get_mean_value(omp_df, s, nt, 'Time_VF2_s', 'diff') for s in sizes]
    
    ax1.bar(x - width/2, iso_times, width, label='Isomorfi', color=COLOR_ISO, alpha=0.8)
    ax1.bar(x + width/2, diff_times, width, label='Non Isomorfi', color=COLOR_DIFF, alpha=0.8)
    ax1.set_xlabel('Dimensione Input')
    ax1.set_ylabel('Tempo (s) - Log')
    ax1.set_title(f'Tempi ({nt} thread)')
    ax1.set_xticks(x)
    ax1.set_xticklabels(sizes)
    ax1.set_yscale('log')
    ax1.legend()
    ax1.grid(True, alpha=0.3, axis='y')
    
    # Speedup
    ax2 = axes[1]
    iso_speedups = [get_mean_value(omp_df, s, nt, 'Speedup', 'iso') for s in sizes]
    diff_speedups = [get_mean_value(omp_df, s, nt, 'Speedup', 'diff') for s in sizes]
    
    ax2.bar(x - width/2, iso_speedups, width, label='Isomorfi', color=COLOR_ISO, alpha=0.8)
    ax2.bar(x + width/2, diff_speedups, width, label='Non Isomorfi', color=COLOR_DIFF, alpha=0.8)
    ax2.axhline(y=1, color='red', linestyle='--', linewidth=1.5, alpha=0.7)
    ax2.set_xlabel('Dimensione Input')
    ax2.set_ylabel('Speedup')
    ax2.set_title(f'Speedup ({nt} thread)')
    ax2.set_xticks(x)
    ax2.set_xticklabels(sizes)
    ax2.legend()
    ax2.grid(True, alpha=0.3, axis='y')
    
    # Throughput
    ax3 = axes[2]
    iso_thr = [get_mean_value(omp_df, s, nt, 'Throughput_MB_s', 'iso') for s in sizes]
    diff_thr = [get_mean_value(omp_df, s, nt, 'Throughput_MB_s', 'diff') for s in sizes]
    
    ax3.bar(x - width/2, iso_thr, width, label='Isomorfi', color=COLOR_ISO, alpha=0.8)
    ax3.bar(x + width/2, diff_thr, width, label='Non Isomorfi', color=COLOR_DIFF, alpha=0.8)
    ax3.set_xlabel('Dimensione Input')
    ax3.set_ylabel('Throughput (MB/s)')
    ax3.set_title(f'Throughput ({nt} thread)')
    ax3.set_xticks(x)
    ax3.set_xticklabels(sizes)
    ax3.legend()
    ax3.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    filepath = PLOTS_DIR / "omp_comparison_iso_vs_diff.png"
    plt.savefig(filepath, dpi=DPI, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"[SALVATO] {filepath.name}")


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
    print(f"RIEPILOGO OPENMP - GRAFI {type_label}")
    print(f"{'='*100}")
    
    sizes = [s for s in SIZE_ORDER if s in df_filtered['Size'].unique()]
    threads = sorted(df_filtered['NumThreads'].unique())
    
    print(f"\n{'Size':<8}", end="")
    for nt in threads:
        print(f"{'T='+str(nt):>14}", end="")
    print()
    
    print(f"{'':8}", end="")
    for nt in threads:
        print(f"{'Time/Spd/Thr':>14}", end="")
    print()
    print("-" * (8 + len(threads) * 14))
    
    for size in sizes:
        print(f"{size:<8}", end="")
        for nt in threads:
            t = get_mean_value(df_filtered, size, nt, 'Time_VF2_s', graph_type)
            s = get_mean_value(df_filtered, size, nt, 'Speedup', graph_type)
            thr = get_mean_value(df_filtered, size, nt, 'Throughput_MB_s', graph_type)
            print(f"{t:.2f}/{s:.1f}x/{thr:.0f}", end="  ")
        print()
    
    print(f"{'='*100}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 70)
    print("VF2++ OPENMP - ANALISI PERFORMANCE COMPLETA")
    print("=" * 70)
    print()
    
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    
    print("Caricamento dati...")
    omp_df = load_omp_results()
    seq_df = load_seq_results()
    
    if omp_df is None or omp_df.empty:
        print("\n[ERRORE] Nessun dato OpenMP trovato!")
        return
    
    print(f"\nDati OMP: {len(omp_df)} righe")
    if seq_df is not None:
        print(f"Dati SEQ: {len(seq_df)} righe")
    
    # GRAFICI ISOMORFI
    print("\n" + "-" * 70)
    print("GENERAZIONE GRAFICI - GRAFI ISOMORFI")
    print("-" * 70)
    
    plot_time_by_threads(omp_df, 'iso')
    if seq_df is not None:
        plot_seq_vs_omp(omp_df, seq_df, 'iso')
        plot_throughput_seq_vs_omp(omp_df, seq_df, 'iso')
    plot_speedup(omp_df, 'iso')
    plot_speedup_curves(omp_df, 'iso')
    plot_efficiency(omp_df, 'iso')
    plot_overhead(omp_df, 'iso')
    plot_throughput(omp_df, 'iso')
    print_summary_table(omp_df, 'iso')
    
    # GRAFICI NON ISOMORFI
    print("\n" + "-" * 70)
    print("GENERAZIONE GRAFICI - GRAFI NON ISOMORFI")
    print("-" * 70)
    
    plot_time_by_threads(omp_df, 'diff')
    if seq_df is not None:
        plot_seq_vs_omp(omp_df, seq_df, 'diff')
        plot_throughput_seq_vs_omp(omp_df, seq_df, 'diff')
    plot_speedup(omp_df, 'diff')
    plot_speedup_curves(omp_df, 'diff')
    plot_efficiency(omp_df, 'diff')
    plot_overhead(omp_df, 'diff')
    plot_throughput(omp_df, 'diff')
    print_summary_table(omp_df, 'diff')
    
    # CONFRONTO ISO vs DIFF
    print("\n" + "-" * 70)
    print("CONFRONTO ISO vs DIFF")
    print("-" * 70)
    
    plot_iso_vs_diff(omp_df)
    
    print(f"\n{'='*70}")
    print("COMPLETATO!")
    print(f"{'='*70}")
    print(f"\nGrafici salvati in: {PLOTS_DIR}")
    print("\nFile generati:")
    for f in sorted(PLOTS_DIR.glob("*.png")):
        print(f"  - {f.name}")


if __name__ == "__main__":
    main()
