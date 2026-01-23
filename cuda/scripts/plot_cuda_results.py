#!/usr/bin/env python3
"""
VF2++ CUDA Performance Analysis
Eseguire da PowerShell: python cuda\scripts\plot_cuda_results.py
"""

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os

# =============================================================================
# CONFIGURAZIONE
# =============================================================================

SCRIPT_DIR = "./cuda/scripts"
PROJECT_DIR = "./"
OUTPUT_DIR = "./cuda/output"
PLOTS_DIR ="./cuda/plots"

CUDA_CSV = "./cuda/output/test_cuda.csv"
SEQ_CSV = "./seq/output/risultati_seq_mix.csv"

os.makedirs(PLOTS_DIR, exist_ok=True)

# Colori
COLORS = {
    64: '#1f77b4',
    128: '#ff7f0e',
    256: '#2ca02c',
    512: '#d62728'
}

# =============================================================================
# CARICAMENTO DATI
# =============================================================================

def load_data():
    """Carica i dati CSV."""
    if not os.path.exists(CUDA_CSV):
        print(f"[ERRORE] File non trovato: {CUDA_CSV}")
        return None, None
    
    cuda_df = pd.read_csv(CUDA_CSV)
    
    seq_df = None
    if os.path.exists(SEQ_CSV):
        seq_df = pd.read_csv(SEQ_CSV)
    
    return cuda_df, seq_df

# =============================================================================
# ANALISI E PLOTTING
# =============================================================================

def plot_cuda_vs_threads(cuda_df, seq_df):
    """Grafico: tempo CUDA vs numero threads per dimensione."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    
    for idx, graph_type in enumerate(['iso', 'diff']):
        ax = axes[idx]
        type_label = "Isomorfi" if graph_type == 'iso' else "Non Isomorfi"
        
        # Filtra per tipo
        df_type = cuda_df[cuda_df['Type'] == graph_type]
        
        sizes = df_type['Size'].unique()
        
        for size in sorted(sizes, key=lambda x: int(x.replace('MB', ''))):
            df_size = df_type[df_type['Size'] == size]
            
            # Raggruppa per threads e calcola media
            grouped = df_size.groupby('Threads')['Time_Algo_s'].agg(['mean', 'std']).reset_index()
            
            ax.errorbar(grouped['Threads'], grouped['mean'], 
                       yerr=grouped['std'], marker='o', label=f'{size}',
                       capsize=3, linewidth=2, markersize=6)
        
        # Sequenziale baseline (linea orizzontale tratteggiata)
        if seq_df is not None:
            seq_type = seq_df[seq_df['Type'] == graph_type]
            for size in sorted(sizes, key=lambda x: int(x.replace('MB', ''))):
                seq_size = seq_type[seq_type['Size'] == size]
                if not seq_size.empty:
                    mean_seq = seq_size['Time_Algo_s'].mean()
                    ax.axhline(y=mean_seq, linestyle='--', alpha=0.5, 
                              label=f'{size} (SEQ)')
        
        ax.set_xlabel('Threads per Block')
        ax.set_ylabel('Tempo (s)')
        ax.set_title(f'CUDA Performance - {type_label}')
        ax.legend(loc='upper right', fontsize=8)
        ax.set_xscale('log', base=2)
        ax.set_xticks([64, 128, 256, 512])
        ax.get_xaxis().set_major_formatter(plt.ScalarFormatter())
        ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(os.path.join(PLOTS_DIR, 'cuda_time_vs_threads.png'), dpi=150)
    plt.close()
    print("[OK] cuda_time_vs_threads.png")

def plot_speedup(cuda_df, seq_df):
    """Grafico: speedup CUDA vs sequenziale."""
    if seq_df is None:
        print("[SKIP] Speedup: baseline sequenziale non disponibile")
        return
    
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    
    for idx, graph_type in enumerate(['iso', 'diff']):
        ax = axes[idx]
        type_label = "Isomorfi" if graph_type == 'iso' else "Non Isomorfi"
        
        # Baseline sequenziale
        seq_type = seq_df[seq_df['Type'] == graph_type]
        seq_means = seq_type.groupby('Size')['Time_Algo_s'].mean()
        
        # CUDA
        cuda_type = cuda_df[cuda_df['Type'] == graph_type]
        
        sizes = cuda_type['Size'].unique()
        threads_configs = sorted(cuda_type['Threads'].unique())
        
        x = np.arange(len(sizes))
        width = 0.2
        
        for i, threads in enumerate(threads_configs):
            cuda_threads = cuda_type[cuda_type['Threads'] == threads]
            speedups = []
            
            for size in sizes:
                cuda_time = cuda_threads[cuda_threads['Size'] == size]['Time_Algo_s'].mean()
                seq_time = seq_means.get(size, cuda_time)
                speedup = seq_time / cuda_time if cuda_time > 0 else 0
                speedups.append(speedup)
            
            offset = (i - len(threads_configs)/2 + 0.5) * width
            bars = ax.bar(x + offset, speedups, width, 
                         label=f'{threads} threads', color=COLORS.get(threads, 'gray'))
        
        ax.axhline(y=1.0, linestyle='--', color='red', alpha=0.7, label='Baseline (SEQ)')
        ax.set_xlabel('Dimensione Input')
        ax.set_ylabel('Speedup (SEQ/CUDA)')
        ax.set_title(f'CUDA Speedup - {type_label}')
        ax.set_xticks(x)
        ax.set_xticklabels(sizes)
        ax.legend(loc='upper right', fontsize=8)
        ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    plt.savefig(os.path.join(PLOTS_DIR, 'cuda_speedup.png'), dpi=150)
    plt.close()
    print("[OK] cuda_speedup.png")

def plot_optimization_levels(cuda_df):
    """Grafico: confronto livelli di ottimizzazione CUDA (se disponibile)."""
    # Questo richiede che i dati includano info sui livelli di ottimizzazione
    # Per ora, plottiamo solo se ci sono dati sufficienti
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Raggruppa per threads e calcola statistiche
    grouped = cuda_df.groupby(['Threads', 'Size'])['Time_Algo_s'].agg(['mean', 'std']).reset_index()
    
    sizes = grouped['Size'].unique()
    
    for size in sorted(sizes, key=lambda x: int(x.replace('MB', ''))):
        df_size = grouped[grouped['Size'] == size]
        ax.plot(df_size['Threads'], df_size['mean'], marker='s', 
               label=f'{size}', linewidth=2, markersize=8)
    
    ax.set_xlabel('Threads per Block')
    ax.set_ylabel('Tempo medio (s)')
    ax.set_title('CUDA: Tempo vs Configurazione Thread')
    ax.set_xscale('log', base=2)
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(os.path.join(PLOTS_DIR, 'cuda_thread_config.png'), dpi=150)
    plt.close()
    print("[OK] cuda_thread_config.png")

def generate_summary(cuda_df, seq_df):
    """Genera summary statistico."""
    summary_file = os.path.join(OUTPUT_DIR, 'cuda_summary.txt')
    
    with open(summary_file, 'w') as f:
        f.write("=" * 60 + "\n")
        f.write("VF2++ CUDA BENCHMARK SUMMARY\n")
        f.write("=" * 60 + "\n\n")
        
        for graph_type in ['iso', 'diff']:
            type_label = "ISOMORFI" if graph_type == 'iso' else "NON ISOMORFI"
            f.write(f"--- GRAFI {type_label} ---\n\n")
            
            cuda_type = cuda_df[cuda_df['Type'] == graph_type]
            
            for size in sorted(cuda_type['Size'].unique(), 
                              key=lambda x: int(x.replace('MB', ''))):
                f.write(f"  {size}:\n")
                
                # Baseline sequenziale
                if seq_df is not None:
                    seq_time = seq_df[(seq_df['Type'] == graph_type) & 
                                     (seq_df['Size'] == size)]['Time_Algo_s'].mean()
                    f.write(f"    Sequenziale: {seq_time:.4f} s\n")
                else:
                    seq_time = None
                
                # CUDA per thread config
                cuda_size = cuda_type[cuda_type['Size'] == size]
                for threads in sorted(cuda_size['Threads'].unique()):
                    cuda_time = cuda_size[cuda_size['Threads'] == threads]['Time_Algo_s'].mean()
                    cuda_std = cuda_size[cuda_size['Threads'] == threads]['Time_Algo_s'].std()
                    
                    speedup_str = ""
                    if seq_time:
                        speedup = seq_time / cuda_time
                        speedup_str = f" (speedup: {speedup:.2f}x)"
                    
                    f.write(f"    CUDA {threads} threads: {cuda_time:.4f} ± {cuda_std:.4f} s{speedup_str}\n")
                
                f.write("\n")
        
        f.write("=" * 60 + "\n")
    
    print(f"[OK] Summary: {summary_file}")

# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 60)
    print("VF2++ CUDA Performance Analysis")
    print("=" * 60)
    print()
    
    cuda_df, seq_df = load_data()
    
    if cuda_df is None:
        print("[ERRORE] Impossibile caricare i dati CUDA")
        return
    
    print(f"Record CUDA caricati: {len(cuda_df)}")
    if seq_df is not None:
        print(f"Record SEQ caricati: {len(seq_df)}")
    print()
    
    # Genera grafici
    plot_cuda_vs_threads(cuda_df, seq_df)
    plot_speedup(cuda_df, seq_df)
    plot_optimization_levels(cuda_df)
    
    # Genera summary
    generate_summary(cuda_df, seq_df)
    
    print()
    print(f"Grafici salvati in: {PLOTS_DIR}")

if __name__ == "__main__":
    main()
