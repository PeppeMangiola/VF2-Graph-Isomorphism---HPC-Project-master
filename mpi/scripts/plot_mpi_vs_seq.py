#!/usr/bin/env python3
"""
==================================================================
VF2++ - Confronto Sequenziale vs MPI
==================================================================

Genera grafici che confrontano le performance della versione
sequenziale con la versione MPI (np=2 e np=4).

SOLO GRAFI ISOMORFI - SCALA LOGARITMICA
Usa TUTTE le misurazioni presenti nel CSV e calcola la media.

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
MPI_OUTPUT_DIR = SCRIPT_DIR.parent / "output"
PLOTS_DIR = SCRIPT_DIR.parent / "plots"

OPTIMIZERS = ["O0", "O1", "O2", "O3"]
PROC_COUNTS = [2, 4]
SIZE_ORDER = ['1MB', '50MB', '100MB', '200MB', '500MB']

# Mappa Size a indice riga nel CSV sequenziale (0-based, dopo header)
# Solo ISO: righe 0, 2, 4, 6, 8
SEQ_ROW_MAP = {
    '1MB': 0,
    '50MB': 2,
    '100MB': 4,
    '200MB': 6,
    '500MB': 8,
}

# Colori
COLOR_SEQ = '#3498db'
COLOR_MPI_2 = '#e74c3c'
COLOR_MPI_4 = '#2ecc71'

# =============================================================================
# FUNZIONI
# =============================================================================

def load_sequential_results():
    """Carica risultati sequenziali, SOLO grafi isomorfi."""
    all_data = []
    
    for opt in OPTIMIZERS:
        csv_path = SEQ_OUTPUT_DIR / f"results_{opt}.csv"
        if csv_path.exists():
            df = pd.read_csv(csv_path)
            df['Optimizer'] = opt
            df['Version'] = 'SEQ'
            df['NumProcs'] = 1
            
            # Aggiungi Size basandosi sull'ordine (solo righe ISO: 0, 2, 4, 6, 8)
            sizes = []
            for idx in range(len(df)):
                for size, row_idx in SEQ_ROW_MAP.items():
                    if row_idx == idx:
                        sizes.append(size)
                        break
                else:
                    sizes.append(None)
            
            df['Size'] = sizes
            # Filtra solo righe ISO (quelle con Size non None)
            df = df[df['Size'].notna()]
            
            all_data.append(df)
            print(f"[OK] SEQ: {csv_path.name} ({len(df)} righe iso)")
        else:
            print(f"[SKIP] SEQ non trovato: {csv_path.name}")
    
    if not all_data:
        return None
    
    return pd.concat(all_data, ignore_index=True)


def load_mpi_results():
    """Carica risultati MPI, SOLO grafi isomorfi - TUTTE LE MISURAZIONI."""
    all_data = []
    
    for opt in OPTIMIZERS:
        csv_path = MPI_OUTPUT_DIR / f"results_{opt}.csv"
        if csv_path.exists():
            df = pd.read_csv(csv_path)
            df['Optimizer'] = opt
            df['Version'] = 'MPI'
            # Filtra solo ISO
            df = df[df['Type'] == 'iso']
            all_data.append(df)
            n_measurements = len(df)
            n_per_config = n_measurements // (len(SIZE_ORDER) * len(PROC_COUNTS)) if n_measurements > 0 else 0
            print(f"[OK] MPI: {csv_path.name} ({n_measurements} righe iso, ~{n_per_config} misurazioni per config)")
        else:
            print(f"[SKIP] MPI non trovato: {csv_path.name}")
    
    if not all_data:
        return None
    
    return pd.concat(all_data, ignore_index=True)


def get_mean_time(df, size, np_val=None):
    """Ottiene il tempo medio per una data configurazione."""
    if np_val is not None:
        subset = df[(df['Size'] == size) & (df['NumProcs'] == np_val)]
    else:
        subset = df[df['Size'] == size]
    
    times = subset['Time_VF2_s'].values
    if len(times) > 0:
        return np.mean(times)
    return 0


def plot_time_comparison(seq_df, mpi_df):
    """Grafico: Confronto tempi SEQ vs MPI per ogni ottimizzatore - SCALA LOG."""
    
    for opt in OPTIMIZERS:
        fig, ax = plt.subplots(figsize=(10, 6))
        
        seq_opt = seq_df[seq_df['Optimizer'] == opt]
        mpi_opt = mpi_df[mpi_df['Optimizer'] == opt]
        
        sizes = [s for s in SIZE_ORDER if s in seq_opt['Size'].values or s in mpi_opt['Size'].values]
        
        if not sizes:
            continue
        
        x = np.arange(len(sizes))
        width = 0.25
        
        # Tempi SEQ (media)
        seq_times = []
        for size in sizes:
            t = get_mean_time(seq_opt, size)
            seq_times.append(t if t > 0 else 0.001)
        
        ax.bar(x - width, seq_times, width, label='Sequenziale', color=COLOR_SEQ, alpha=0.8)
        
        # Tempi MPI np=2 (media di tutte le misurazioni)
        mpi_2_times = []
        for size in sizes:
            t = get_mean_time(mpi_opt, size, np_val=2)
            mpi_2_times.append(t if t > 0 else 0.001)
        
        ax.bar(x, mpi_2_times, width, label='MPI np=2', color=COLOR_MPI_2, alpha=0.8)
        
        # Tempi MPI np=4 (media di tutte le misurazioni)
        mpi_4_times = []
        for size in sizes:
            t = get_mean_time(mpi_opt, size, np_val=4)
            mpi_4_times.append(t if t > 0 else 0.001)
        
        ax.bar(x + width, mpi_4_times, width, label='MPI np=4', color=COLOR_MPI_4, alpha=0.8)
        
        ax.set_xlabel('Dimensione Input', fontsize=12)
        ax.set_ylabel('Tempo VF2++ (s) - Scala Log', fontsize=12)
        ax.set_title(f'Confronto SEQ vs MPI - Ottimizzatore {opt} (Grafi Isomorfi)', 
                     fontsize=14, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(sizes)
        ax.set_yscale('log')
        ax.legend()
        ax.grid(True, alpha=0.3, axis='y')
        
        plt.tight_layout()
        
        filepath = PLOTS_DIR / f"seq_vs_mpi_{opt}.png"
        plt.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='white')
        plt.close()
        print(f"[GRAFICO] {filepath.name}")


def plot_speedup_curves(seq_df, mpi_df):
    """Grafico: Curve di speedup al variare di np."""
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    axes = axes.flatten()
    
    for idx, opt in enumerate(OPTIMIZERS):
        ax = axes[idx]
        
        seq_opt = seq_df[seq_df['Optimizer'] == opt]
        mpi_opt = mpi_df[mpi_df['Optimizer'] == opt]
        
        sizes = [s for s in SIZE_ORDER if s in seq_opt['Size'].values]
        
        markers = ['o', 's', '^', 'D', 'v']
        colors = plt.cm.viridis(np.linspace(0.2, 0.8, len(sizes)))
        
        for i, size in enumerate(sizes):
            seq_time = get_mean_time(seq_opt, size)
            if seq_time == 0:
                continue
            
            procs = [1] + PROC_COUNTS
            speedups = [1.0]
            
            for np_val in PROC_COUNTS:
                mpi_time = get_mean_time(mpi_opt, size, np_val=np_val)
                if mpi_time > 0:
                    speedups.append(seq_time / mpi_time)
                else:
                    speedups.append(0)
            
            ax.plot(procs, speedups, marker=markers[i % len(markers)], 
                   color=colors[i], linewidth=2, markersize=10, label=size)
        
        # Linea speedup ideale
        ax.plot([1, max(PROC_COUNTS)], [1, max(PROC_COUNTS)], 
               'k--', alpha=0.5, linewidth=2, label='Ideale')
        
        ax.set_xlabel('Numero Processi', fontsize=11)
        ax.set_ylabel('Speedup', fontsize=11)
        ax.set_title(f'Ottimizzatore {opt}', fontsize=12, fontweight='bold')
        ax.set_xticks([1] + PROC_COUNTS)
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3)
        ax.set_ylim(0, max(PROC_COUNTS) + 0.5)
    
    plt.suptitle('Speedup MPI vs Sequenziale (Grafi Isomorfi)', fontsize=14, fontweight='bold')
    plt.tight_layout()
    
    filepath = PLOTS_DIR / "speedup_curves.png"
    plt.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"[GRAFICO] {filepath.name}")


def plot_efficiency(seq_df, mpi_df):
    """Grafico: Efficienza parallela."""
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    opt = 'O3'
    
    seq_opt = seq_df[seq_df['Optimizer'] == opt]
    mpi_opt = mpi_df[mpi_df['Optimizer'] == opt]
    
    sizes = [s for s in SIZE_ORDER if s in seq_opt['Size'].values]
    
    x = np.arange(len(sizes))
    width = 0.35
    
    eff_2 = []
    eff_4 = []
    
    for size in sizes:
        seq_time = get_mean_time(seq_opt, size)
        if seq_time == 0:
            eff_2.append(0)
            eff_4.append(0)
            continue
        
        mpi_2_time = get_mean_time(mpi_opt, size, np_val=2)
        if mpi_2_time > 0:
            speedup_2 = seq_time / mpi_2_time
            eff_2.append(speedup_2 / 2 * 100)
        else:
            eff_2.append(0)
        
        mpi_4_time = get_mean_time(mpi_opt, size, np_val=4)
        if mpi_4_time > 0:
            speedup_4 = seq_time / mpi_4_time
            eff_4.append(speedup_4 / 4 * 100)
        else:
            eff_4.append(0)
    
    ax.bar(x - width/2, eff_2, width, label='MPI np=2', color=COLOR_MPI_2, alpha=0.8)
    ax.bar(x + width/2, eff_4, width, label='MPI np=4', color=COLOR_MPI_4, alpha=0.8)
    
    ax.axhline(y=100, color='green', linestyle='--', alpha=0.7, linewidth=2, label='Efficienza ideale (100%)')
    ax.axhline(y=50, color='orange', linestyle=':', alpha=0.7, linewidth=1.5, label='50%')
    
    ax.set_xlabel('Dimensione Input', fontsize=12)
    ax.set_ylabel('Efficienza (%)', fontsize=12)
    ax.set_title(f'Efficienza Parallela MPI - Ottimizzatore {opt} (Grafi Isomorfi)', 
                fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(sizes)
    ax.legend()
    ax.grid(True, alpha=0.3, axis='y')
    ax.set_ylim(0, 120)
    
    plt.tight_layout()
    
    filepath = PLOTS_DIR / "efficiency.png"
    plt.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"[GRAFICO] {filepath.name}")


def plot_overhead(seq_df, mpi_df):
    """Grafico: Overhead di parallelizzazione - SCALA LOG."""
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    opt = 'O3'
    
    seq_opt = seq_df[seq_df['Optimizer'] == opt]
    mpi_opt = mpi_df[mpi_df['Optimizer'] == opt]
    
    sizes = [s for s in SIZE_ORDER if s in seq_opt['Size'].values]
    
    x = np.arange(len(sizes))
    width = 0.35
    
    overhead_2 = []
    overhead_4 = []
    
    for size in sizes:
        seq_time = get_mean_time(seq_opt, size)
        
        mpi_2_time = get_mean_time(mpi_opt, size, np_val=2)
        if mpi_2_time > 0:
            overhead_2.append(max(0.001, mpi_2_time * 2 - seq_time))
        else:
            overhead_2.append(0.001)
        
        mpi_4_time = get_mean_time(mpi_opt, size, np_val=4)
        if mpi_4_time > 0:
            overhead_4.append(max(0.001, mpi_4_time * 4 - seq_time))
        else:
            overhead_4.append(0.001)
    
    ax.bar(x - width/2, overhead_2, width, label='MPI np=2', color=COLOR_MPI_2, alpha=0.8)
    ax.bar(x + width/2, overhead_4, width, label='MPI np=4', color=COLOR_MPI_4, alpha=0.8)
    
    ax.set_xlabel('Dimensione Input', fontsize=12)
    ax.set_ylabel('Overhead (s) - Scala Log', fontsize=12)
    ax.set_title(f'Overhead di Parallelizzazione (T_mpi × NP - T_seq) - {opt} (Grafi Isomorfi)', 
                fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(sizes)
    ax.set_yscale('log')
    ax.legend()
    ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    
    filepath = PLOTS_DIR / "overhead.png"
    plt.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"[GRAFICO] {filepath.name}")


def plot_summary_all_optimizers(seq_df, mpi_df):
    """Grafico riassuntivo: Speedup per tutti gli ottimizzatori."""
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    np_val = 4
    
    sizes = [s for s in SIZE_ORDER if s in seq_df['Size'].values]
    
    x = np.arange(len(sizes))
    width = 0.2
    colors = {'O0': '#e74c3c', 'O1': '#f39c12', 'O2': '#3498db', 'O3': '#2ecc71'}
    
    for i, opt in enumerate(OPTIMIZERS):
        speedups = []
        
        seq_opt = seq_df[seq_df['Optimizer'] == opt]
        mpi_opt = mpi_df[mpi_df['Optimizer'] == opt]
        
        for size in sizes:
            seq_time = get_mean_time(seq_opt, size)
            mpi_time = get_mean_time(mpi_opt, size, np_val=np_val)
            
            if seq_time > 0 and mpi_time > 0:
                speedups.append(seq_time / mpi_time)
            else:
                speedups.append(0)
        
        offset = (i - 1.5) * width
        ax.bar(x + offset, speedups, width, label=opt, color=colors[opt], alpha=0.8)
    
    ax.axhline(y=1, color='red', linestyle='--', alpha=0.7, linewidth=2, label='Speedup=1 (no gain)')
    ax.axhline(y=np_val, color='green', linestyle=':', alpha=0.7, linewidth=2, label=f'Ideale ({np_val}x)')
    
    ax.set_xlabel('Dimensione Input', fontsize=12)
    ax.set_ylabel(f'Speedup (SEQ / MPI np={np_val})', fontsize=12)
    ax.set_title(f'Speedup MPI vs Sequenziale - Tutti gli Ottimizzatori (np={np_val}, Grafi Isomorfi)', 
                fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(sizes)
    ax.legend()
    ax.grid(True, alpha=0.3, axis='y')
    ax.set_ylim(0, np_val + 1)
    
    plt.tight_layout()
    
    filepath = PLOTS_DIR / "speedup_summary.png"
    plt.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"[GRAFICO] {filepath.name}")


def print_comparison_table(seq_df, mpi_df):
    """Stampa tabella comparativa."""
    
    print("\n" + "=" * 110)
    print("CONFRONTO SEQUENZIALE vs MPI (SOLO GRAFI ISOMORFI)")
    print("=" * 110)
    
    for opt in OPTIMIZERS:
        print(f"\n{'─'*110}")
        print(f"OTTIMIZZATORE: {opt}")
        print(f"{'─'*110}")
        
        seq_opt = seq_df[seq_df['Optimizer'] == opt]
        mpi_opt = mpi_df[mpi_df['Optimizer'] == opt]
        
        # Conta misurazioni
        n_mpi = len(mpi_opt)
        n_per_size = n_mpi // (len(SIZE_ORDER) * len(PROC_COUNTS)) if n_mpi > 0 else 0
        print(f"Misurazioni MPI totali: {n_mpi} (~{n_per_size} per configurazione)")
        
        print(f"\n{'Size':<8} {'SEQ (s)':>12} {'MPI-2 (s)':>12} {'MPI-4 (s)':>12} {'Speedup-2':>12} {'Speedup-4':>12} {'Eff-4 (%)':>10}")
        print("-" * 90)
        
        sizes = [s for s in SIZE_ORDER if s in seq_opt['Size'].values]
        
        for size in sizes:
            seq_time = get_mean_time(seq_opt, size)
            mpi_2_time = get_mean_time(mpi_opt, size, np_val=2)
            mpi_4_time = get_mean_time(mpi_opt, size, np_val=4)
            
            speedup_2 = seq_time / mpi_2_time if mpi_2_time > 0 else 0
            speedup_4 = seq_time / mpi_4_time if mpi_4_time > 0 else 0
            eff_4 = (speedup_4 / 4 * 100) if speedup_4 > 0 else 0
            
            print(f"{size:<8} {seq_time:>12.4f} {mpi_2_time:>12.4f} {mpi_4_time:>12.4f} {speedup_2:>11.2f}x {speedup_4:>11.2f}x {eff_4:>9.1f}%")
    
    print("\n" + "=" * 110)


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 60)
    print("VF2++ - Confronto Sequenziale vs MPI (Solo Isomorfi)")
    print("=" * 60)
    print()
    
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    
    print("Caricamento dati sequenziali...")
    seq_df = load_sequential_results()
    
    print("\nCaricamento dati MPI...")
    mpi_df = load_mpi_results()
    
    if seq_df is None or seq_df.empty:
        print("\n[ERRORE] Nessun dato sequenziale trovato!")
        return
    
    if mpi_df is None or mpi_df.empty:
        print("\n[ERRORE] Nessun dato MPI trovato!")
        return
    
    print(f"\nDati caricati: SEQ={len(seq_df)} righe, MPI={len(mpi_df)} righe")
    
    print("\n--- Generazione grafici ---")
    plot_time_comparison(seq_df, mpi_df)
    plot_speedup_curves(seq_df, mpi_df)
    plot_efficiency(seq_df, mpi_df)
    plot_overhead(seq_df, mpi_df)
    plot_summary_all_optimizers(seq_df, mpi_df)
    
    print_comparison_table(seq_df, mpi_df)
    
    print(f"\nGrafici salvati in: {PLOTS_DIR}")


if __name__ == "__main__":
    main()
