#!/usr/bin/env python3
"""
VF2++ CUDA Performance Analysis - Confronto con Sequenziale
Analizza solo la configurazione con 64 threads e confronta con la baseline sequenziale.
Eseguire da PowerShell: python cuda\scripts\plot_cuda_results.py
"""

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os
import re

# =============================================================================
# CONFIGURAZIONE
# =============================================================================

PROJECT_DIR = "./"
OUTPUT_DIR = "./cuda/output"
PLOTS_DIR = "./cuda/plots"

CUDA_CSV = "./cuda/output/test_cuda.csv"
SEQ_CSV = "./sequential/output/risultati_seq_mix.csv"

os.makedirs(PLOTS_DIR, exist_ok=True)

# Stile grafici
plt.style.use('seaborn-v0_8-whitegrid')
COLORS = {
    'cuda': '#2ecc71',      # Verde
    'seq_O0': '#e74c3c',    # Rosso
    'seq_O1': '#3498db',    # Blu
    'seq_O2': '#9b59b6',    # Viola
    'seq_O3': '#f39c12',    # Arancione
    'iso': '#27ae60',       # Verde scuro
    'diff': '#c0392b',      # Rosso scuro
}

SIZES_ORDER = ['1MB', '50MB', '100MB', '200MB', '500MB']
SIZE_TO_MB = {s: int(s.replace('MB', '')) for s in SIZES_ORDER}

# =============================================================================
# CARICAMENTO E PREPROCESSING DATI
# =============================================================================

def fix_cuda_csv_header(filepath):
    """Corregge il CSV CUDA se la prima riga ha problemi."""
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    # Verifica se la prima riga è un header valido
    expected_header = "Size,Type,Nodes,Edges,RAM_MB,Blocks,Threads,Time_Load_s,Time_Algo_s,Time_Total_s,Found"
    
    if not lines[0].strip().startswith('Size,Type'):
        # Header mancante o corrotto - aggiungi header corretto
        print("[FIX] Aggiunto header mancante al CSV CUDA")
        lines.insert(0, expected_header + '\n')
        
        # Correggi prima riga dati se corrotta (es. "Found1MB" -> "Found\n1MB")
        if 'Found1MB' in lines[1]:
            lines[1] = lines[1].replace('Found1MB', 'Found\n1MB')
        
        with open(filepath, 'w') as f:
            f.writelines(lines)

def load_cuda_data():
    """Carica e preprocessa i dati CUDA, filtrando solo 64 threads."""
    if not os.path.exists(CUDA_CSV):
        print(f"[ERRORE] File non trovato: {CUDA_CSV}")
        return None
    
    # Prima prova a leggere direttamente
    try:
        df = pd.read_csv(CUDA_CSV)
        if 'Size' not in df.columns:
            raise ValueError("Header mancante")
    except:
        # Leggi manualmente con header esplicito
        print("[INFO] Lettura CSV con header esplicito...")
        df = pd.read_csv(CUDA_CSV, 
                        names=['Size', 'Type', 'Nodes', 'Edges', 'RAM_MB', 
                               'Blocks', 'Threads', 'Time_Load_s', 'Time_Algo_s', 
                               'Time_Total_s', 'Found'],
                        skiprows=1)
    
    # Pulisci colonna Size se necessario
    df['Size'] = df['Size'].astype(str).str.strip()
    
    # Rimuovi righe con Size non valido
    df = df[df['Size'].isin(SIZES_ORDER)]
    
    # Filtra solo 64 threads
    df = df[df['Threads'] == 64]
    
    print(f"[OK] CUDA: {len(df)} record caricati (64 threads)")
    return df

def load_seq_data():
    """Carica e preprocessa i dati sequenziali."""
    if not os.path.exists(SEQ_CSV):
        print(f"[WARN] File sequenziale non trovato: {SEQ_CSV}")
        return None
    
    df = pd.read_csv(SEQ_CSV)
    
    # Converti formato: RAM_Graph_MB -> Size, Isomorphic -> Type
    df['Size'] = df['RAM_Graph_MB'].apply(lambda x: f"{int(x)}MB")
    df['Type'] = df['Isomorphic'].apply(lambda x: 'iso' if x == 1 else 'diff')
    df['Time_Algo_s'] = df['Time_VF2_s']
    
    print(f"[OK] SEQ: {len(df)} record caricati")
    return df

# =============================================================================
# ANALISI STATISTICA
# =============================================================================

def compute_stats(df, group_cols, time_col='Time_Algo_s'):
    """Calcola statistiche aggregate per gruppo."""
    stats = df.groupby(group_cols)[time_col].agg([
        ('mean', 'mean'),
        ('std', 'std'),
        ('min', 'min'),
        ('max', 'max'),
        ('count', 'count')
    ]).reset_index()
    stats['std'] = stats['std'].fillna(0)
    return stats

# =============================================================================
# GRAFICI
# =============================================================================

def plot_cuda_vs_seq_time(cuda_df, seq_df):
    """Grafico 1: Tempo CUDA 64T vs Sequenziale per ogni optimizer (grafici separati per iso/diff)."""
    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    
    for idx, graph_type in enumerate(['iso', 'diff']):
        ax = axes[idx]
        type_label = "Grafi Isomorfi" if graph_type == 'iso' else "Grafi Non Isomorfi"
        
        # CUDA stats
        cuda_type = cuda_df[cuda_df['Type'] == graph_type]
        cuda_stats = compute_stats(cuda_type, ['Size'])
        
        # Ordina per size
        cuda_stats['Size_MB'] = cuda_stats['Size'].map(SIZE_TO_MB)
        cuda_stats = cuda_stats.sort_values('Size_MB')
        
        x = np.arange(len(SIZES_ORDER))
        width = 0.15
        
        # Barre CUDA
        cuda_means = [cuda_stats[cuda_stats['Size'] == s]['mean'].values[0] 
                      if s in cuda_stats['Size'].values else 0 for s in SIZES_ORDER]
        cuda_stds = [cuda_stats[cuda_stats['Size'] == s]['std'].values[0] 
                     if s in cuda_stats['Size'].values else 0 for s in SIZES_ORDER]
        
        bars_cuda = ax.bar(x - 2*width, cuda_means, width, yerr=cuda_stds,
                          label='CUDA 64T', color=COLORS['cuda'], capsize=3)
        
        # Barre Sequenziali per ogni optimizer
        if seq_df is not None:
            seq_type = seq_df[seq_df['Type'] == graph_type]
            
            for i, opt in enumerate(['O0', 'O1', 'O2', 'O3']):
                seq_opt = seq_type[seq_type['Optimizer'] == opt]
                seq_stats = compute_stats(seq_opt, ['Size'])
                
                seq_means = [seq_stats[seq_stats['Size'] == s]['mean'].values[0] 
                            if s in seq_stats['Size'].values else 0 for s in SIZES_ORDER]
                seq_stds = [seq_stats[seq_stats['Size'] == s]['std'].values[0] 
                           if s in seq_stats['Size'].values else 0 for s in SIZES_ORDER]
                
                offset = (i - 1) * width
                ax.bar(x + offset + width, seq_means, width, yerr=seq_stds,
                      label=f'SEQ {opt}', color=COLORS[f'seq_{opt}'], capsize=3, alpha=0.8)
        
        ax.set_xlabel('Dimensione Input', fontsize=12)
        ax.set_ylabel('Tempo Algoritmo (s)', fontsize=12)
        ax.set_title(f'CUDA 64T vs Sequenziale - {type_label}', fontsize=14, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(SIZES_ORDER)
        ax.legend(loc='upper left', fontsize=9)
        ax.grid(True, alpha=0.3, axis='y')
        
        # Scala logaritmica se i valori variano molto
        if max(cuda_means) / (min([m for m in cuda_means if m > 0]) + 0.0001) > 100:
            ax.set_yscale('log')
    
    plt.tight_layout()
    plt.savefig(os.path.join(PLOTS_DIR, 'cuda64_vs_seq_time.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("[OK] cuda64_vs_seq_time.png")

def plot_speedup_by_optimizer(cuda_df, seq_df):
    """Grafico 2: Speedup CUDA 64T rispetto a ogni optimizer sequenziale."""
    if seq_df is None:
        print("[SKIP] Speedup: baseline sequenziale non disponibile")
        return
    
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    
    for idx, graph_type in enumerate(['iso', 'diff']):
        ax = axes[idx]
        type_label = "Grafi Isomorfi" if graph_type == 'iso' else "Grafi Non Isomorfi"
        
        cuda_type = cuda_df[cuda_df['Type'] == graph_type]
        cuda_stats = compute_stats(cuda_type, ['Size'])
        
        seq_type = seq_df[seq_df['Type'] == graph_type]
        
        x = np.arange(len(SIZES_ORDER))
        width = 0.2
        
        for i, opt in enumerate(['O0', 'O1', 'O2', 'O3']):
            seq_opt = seq_type[seq_type['Optimizer'] == opt]
            seq_stats = compute_stats(seq_opt, ['Size'])
            
            speedups = []
            for size in SIZES_ORDER:
                cuda_row = cuda_stats[cuda_stats['Size'] == size]
                seq_row = seq_stats[seq_stats['Size'] == size]
                
                if not cuda_row.empty and not seq_row.empty:
                    cuda_time = cuda_row['mean'].values[0]
                    seq_time = seq_row['mean'].values[0]
                    speedup = seq_time / cuda_time if cuda_time > 0 else 0
                else:
                    speedup = 0
                speedups.append(speedup)
            
            offset = (i - 1.5) * width
            bars = ax.bar(x + offset, speedups, width, 
                         label=f'vs SEQ {opt}', color=COLORS[f'seq_{opt}'], alpha=0.85)
            
            # Etichette sui bar
            for bar, sp in zip(bars, speedups):
                if sp > 0:
                    height = bar.get_height()
                    ax.annotate(f'{sp:.2f}x',
                               xy=(bar.get_x() + bar.get_width() / 2, height),
                               xytext=(0, 3), textcoords="offset points",
                               ha='center', va='bottom', fontsize=7, rotation=45)
        
        ax.axhline(y=1.0, linestyle='--', color='red', alpha=0.7, linewidth=2, label='Baseline (1x)')
        ax.set_xlabel('Dimensione Input', fontsize=12)
        ax.set_ylabel('Speedup (SEQ / CUDA)', fontsize=12)
        ax.set_title(f'Speedup CUDA 64T - {type_label}', fontsize=14, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(SIZES_ORDER)
        ax.legend(loc='upper right', fontsize=9)
        ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    plt.savefig(os.path.join(PLOTS_DIR, 'cuda64_speedup_by_optimizer.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("[OK] cuda64_speedup_by_optimizer.png")

def plot_time_breakdown(cuda_df):
    """Grafico 3: Breakdown tempi CUDA (Load vs Algo) per tipo di grafo."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    
    for idx, graph_type in enumerate(['iso', 'diff']):
        ax = axes[idx]
        type_label = "Grafi Isomorfi" if graph_type == 'iso' else "Grafi Non Isomorfi"
        
        cuda_type = cuda_df[cuda_df['Type'] == graph_type]
        
        # Calcola medie per size
        load_stats = compute_stats(cuda_type, ['Size'], 'Time_Load_s')
        algo_stats = compute_stats(cuda_type, ['Size'], 'Time_Algo_s')
        
        sizes_data = []
        load_times = []
        algo_times = []
        
        for size in SIZES_ORDER:
            load_row = load_stats[load_stats['Size'] == size]
            algo_row = algo_stats[algo_stats['Size'] == size]
            
            if not load_row.empty and not algo_row.empty:
                sizes_data.append(size)
                load_times.append(load_row['mean'].values[0])
                algo_times.append(algo_row['mean'].values[0])
        
        x = np.arange(len(sizes_data))
        width = 0.6
        
        # Stacked bar chart
        bars1 = ax.bar(x, load_times, width, label='Tempo Load', color='#3498db')
        bars2 = ax.bar(x, algo_times, width, bottom=load_times, label='Tempo Algoritmo', color='#e74c3c')
        
        ax.set_xlabel('Dimensione Input', fontsize=12)
        ax.set_ylabel('Tempo (s)', fontsize=12)
        ax.set_title(f'Breakdown Tempi CUDA 64T - {type_label}', fontsize=14, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(sizes_data)
        ax.legend(loc='upper left', fontsize=10)
        ax.grid(True, alpha=0.3, axis='y')
        
        # Annotazioni percentuali
        for i, (load, algo) in enumerate(zip(load_times, algo_times)):
            total = load + algo
            if total > 0:
                load_pct = (load / total) * 100
                algo_pct = (algo / total) * 100
                ax.annotate(f'{load_pct:.1f}%', xy=(i, load/2), ha='center', va='center', 
                           fontsize=9, color='white', fontweight='bold')
                ax.annotate(f'{algo_pct:.1f}%', xy=(i, load + algo/2), ha='center', va='center',
                           fontsize=9, color='white', fontweight='bold')
    
    plt.tight_layout()
    plt.savefig(os.path.join(PLOTS_DIR, 'cuda64_time_breakdown.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("[OK] cuda64_time_breakdown.png")

def plot_iso_vs_diff_comparison(cuda_df, seq_df):
    """Grafico 4: Confronto diretto iso vs diff per CUDA e SEQ."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    
    # CUDA comparison
    ax = axes[0]
    
    cuda_iso = compute_stats(cuda_df[cuda_df['Type'] == 'iso'], ['Size'])
    cuda_diff = compute_stats(cuda_df[cuda_df['Type'] == 'diff'], ['Size'])
    
    x = np.arange(len(SIZES_ORDER))
    width = 0.35
    
    iso_means = [cuda_iso[cuda_iso['Size'] == s]['mean'].values[0] 
                 if s in cuda_iso['Size'].values else 0 for s in SIZES_ORDER]
    diff_means = [cuda_diff[cuda_diff['Size'] == s]['mean'].values[0] 
                  if s in cuda_diff['Size'].values else 0 for s in SIZES_ORDER]
    
    ax.bar(x - width/2, iso_means, width, label='Isomorfi', color=COLORS['iso'])
    ax.bar(x + width/2, diff_means, width, label='Non Isomorfi', color=COLORS['diff'])
    
    ax.set_xlabel('Dimensione Input', fontsize=12)
    ax.set_ylabel('Tempo Algoritmo (s)', fontsize=12)
    ax.set_title('CUDA 64T: Isomorfi vs Non Isomorfi', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(SIZES_ORDER)
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3, axis='y')
    ax.set_yscale('log')
    
    # SEQ O3 comparison
    ax2 = axes[1]
    
    if seq_df is not None:
        seq_o3 = seq_df[seq_df['Optimizer'] == 'O3']
        seq_iso = compute_stats(seq_o3[seq_o3['Type'] == 'iso'], ['Size'])
        seq_diff = compute_stats(seq_o3[seq_o3['Type'] == 'diff'], ['Size'])
        
        iso_means_seq = [seq_iso[seq_iso['Size'] == s]['mean'].values[0] 
                        if s in seq_iso['Size'].values else 0 for s in SIZES_ORDER]
        diff_means_seq = [seq_diff[seq_diff['Size'] == s]['mean'].values[0] 
                         if s in seq_diff['Size'].values else 0 for s in SIZES_ORDER]
        
        ax2.bar(x - width/2, iso_means_seq, width, label='Isomorfi', color=COLORS['iso'])
        ax2.bar(x + width/2, diff_means_seq, width, label='Non Isomorfi', color=COLORS['diff'])
        
        ax2.set_xlabel('Dimensione Input', fontsize=12)
        ax2.set_ylabel('Tempo Algoritmo (s)', fontsize=12)
        ax2.set_title('SEQ O3: Isomorfi vs Non Isomorfi', fontsize=14, fontweight='bold')
        ax2.set_xticks(x)
        ax2.set_xticklabels(SIZES_ORDER)
        ax2.legend(fontsize=10)
        ax2.grid(True, alpha=0.3, axis='y')
        ax2.set_yscale('log')
    
    plt.tight_layout()
    plt.savefig(os.path.join(PLOTS_DIR, 'cuda64_iso_vs_diff.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("[OK] cuda64_iso_vs_diff.png")

def plot_scaling_analysis(cuda_df, seq_df):
    """Grafico 5: Analisi di scaling - tempo vs dimensione input."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    
    for idx, graph_type in enumerate(['iso', 'diff']):
        ax = axes[idx]
        type_label = "Grafi Isomorfi" if graph_type == 'iso' else "Grafi Non Isomorfi"
        
        # CUDA
        cuda_type = cuda_df[cuda_df['Type'] == graph_type]
        cuda_stats = compute_stats(cuda_type, ['Size'])
        cuda_stats['Size_MB'] = cuda_stats['Size'].map(SIZE_TO_MB)
        cuda_stats = cuda_stats.sort_values('Size_MB')
        
        ax.plot(cuda_stats['Size_MB'], cuda_stats['mean'], 'o-', 
               linewidth=2, markersize=8, label='CUDA 64T', color=COLORS['cuda'])
        ax.fill_between(cuda_stats['Size_MB'], 
                       cuda_stats['mean'] - cuda_stats['std'],
                       cuda_stats['mean'] + cuda_stats['std'],
                       alpha=0.2, color=COLORS['cuda'])
        
        # Sequenziale per ogni optimizer
        if seq_df is not None:
            seq_type = seq_df[seq_df['Type'] == graph_type]
            
            for opt in ['O0', 'O3']:  # Solo O0 e O3 per leggibilità
                seq_opt = seq_type[seq_type['Optimizer'] == opt]
                seq_stats = compute_stats(seq_opt, ['Size'])
                seq_stats['Size_MB'] = seq_stats['Size'].map(SIZE_TO_MB)
                seq_stats = seq_stats.sort_values('Size_MB')
                
                ax.plot(seq_stats['Size_MB'], seq_stats['mean'], 's--', 
                       linewidth=2, markersize=6, label=f'SEQ {opt}', 
                       color=COLORS[f'seq_{opt}'], alpha=0.8)
        
        ax.set_xlabel('Dimensione Input (MB)', fontsize=12)
        ax.set_ylabel('Tempo Algoritmo (s)', fontsize=12)
        ax.set_title(f'Scaling Analysis - {type_label}', fontsize=14, fontweight='bold')
        ax.legend(fontsize=10)
        ax.grid(True, alpha=0.3)
        ax.set_xscale('log')
        ax.set_yscale('log')
    
    plt.tight_layout()
    plt.savefig(os.path.join(PLOTS_DIR, 'cuda64_scaling.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("[OK] cuda64_scaling.png")

def plot_throughput(cuda_df, seq_df):
    """Grafico 6: Throughput (MB/s) per CUDA e SEQ."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    
    for idx, graph_type in enumerate(['iso', 'diff']):
        ax = axes[idx]
        type_label = "Grafi Isomorfi" if graph_type == 'iso' else "Grafi Non Isomorfi"
        
        cuda_type = cuda_df[cuda_df['Type'] == graph_type]
        cuda_stats = compute_stats(cuda_type, ['Size'])
        
        x = np.arange(len(SIZES_ORDER))
        width = 0.15
        
        # Throughput CUDA
        cuda_throughputs = []
        for size in SIZES_ORDER:
            row = cuda_stats[cuda_stats['Size'] == size]
            if not row.empty:
                time = row['mean'].values[0]
                mb = SIZE_TO_MB[size]
                throughput = mb / time if time > 0 else 0
            else:
                throughput = 0
            cuda_throughputs.append(throughput)
        
        ax.bar(x - 2*width, cuda_throughputs, width, label='CUDA 64T', color=COLORS['cuda'])
        
        # Throughput SEQ per ogni optimizer
        if seq_df is not None:
            seq_type = seq_df[seq_df['Type'] == graph_type]
            
            for i, opt in enumerate(['O0', 'O1', 'O2', 'O3']):
                seq_opt = seq_type[seq_type['Optimizer'] == opt]
                seq_stats = compute_stats(seq_opt, ['Size'])
                
                seq_throughputs = []
                for size in SIZES_ORDER:
                    row = seq_stats[seq_stats['Size'] == size]
                    if not row.empty:
                        time = row['mean'].values[0]
                        mb = SIZE_TO_MB[size]
                        throughput = mb / time if time > 0 else 0
                    else:
                        throughput = 0
                    seq_throughputs.append(throughput)
                
                offset = (i - 1) * width
                ax.bar(x + offset + width, seq_throughputs, width, 
                      label=f'SEQ {opt}', color=COLORS[f'seq_{opt}'], alpha=0.85)
        
        ax.set_xlabel('Dimensione Input', fontsize=12)
        ax.set_ylabel('Throughput (MB/s)', fontsize=12)
        ax.set_title(f'Throughput - {type_label}', fontsize=14, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(SIZES_ORDER)
        ax.legend(loc='upper right', fontsize=9)
        ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    plt.savefig(os.path.join(PLOTS_DIR, 'cuda64_throughput.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("[OK] cuda64_throughput.png")

# =============================================================================
# SUMMARY REPORT
# =============================================================================

def generate_summary_report(cuda_df, seq_df):
    """Genera un report testuale con tutti i risultati."""
    report_file = os.path.join(OUTPUT_DIR, 'cuda64_analysis_summary.txt')
    
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("=" * 70 + "\n")
        f.write("VF2++ CUDA 64 THREADS - ANALISI COMPLETA vs SEQUENZIALE\n")
        f.write("=" * 70 + "\n\n")
        
        for graph_type in ['iso', 'diff']:
            type_label = "GRAFI ISOMORFI" if graph_type == 'iso' else "GRAFI NON ISOMORFI"
            f.write(f"\n{'='*70}\n")
            f.write(f"{type_label}\n")
            f.write(f"{'='*70}\n\n")
            
            cuda_type = cuda_df[cuda_df['Type'] == graph_type]
            
            for size in SIZES_ORDER:
                cuda_size = cuda_type[cuda_type['Size'] == size]
                if cuda_size.empty:
                    continue
                
                cuda_mean = cuda_size['Time_Algo_s'].mean()
                cuda_std = cuda_size['Time_Algo_s'].std()
                cuda_load = cuda_size['Time_Load_s'].mean()
                
                f.write(f"--- {size} ---\n")
                f.write(f"  CUDA 64T:  {cuda_mean:.4f} ± {cuda_std:.4f} s  (load: {cuda_load:.4f} s)\n")
                
                if seq_df is not None:
                    seq_type = seq_df[seq_df['Type'] == graph_type]
                    
                    for opt in ['O0', 'O1', 'O2', 'O3']:
                        seq_opt = seq_type[(seq_type['Optimizer'] == opt) & 
                                          (seq_type['Size'] == size)]
                        if not seq_opt.empty:
                            seq_mean = seq_opt['Time_Algo_s'].mean()
                            speedup = seq_mean / cuda_mean if cuda_mean > 0 else 0
                            f.write(f"  SEQ {opt}:   {seq_mean:.4f} s  (speedup CUDA: {speedup:.2f}x)\n")
                
                f.write("\n")
        
        # Statistiche aggregate
        f.write("\n" + "=" * 70 + "\n")
        f.write("STATISTICHE AGGREGATE\n")
        f.write("=" * 70 + "\n\n")
        
        f.write("Totale test CUDA: {}\n".format(len(cuda_df)))
        f.write("Configurazione: 64 threads per block\n\n")
        
        # Best/Worst speedup
        if seq_df is not None:
            f.write("Speedup CUDA vs SEQ O3:\n")
            seq_o3 = seq_df[seq_df['Optimizer'] == 'O3']
            
            for graph_type in ['iso', 'diff']:
                type_label = "Isomorfi" if graph_type == 'iso' else "Non Isomorfi"
                cuda_type = cuda_df[cuda_df['Type'] == graph_type]
                seq_type = seq_o3[seq_o3['Type'] == graph_type]
                
                speedups = []
                for size in SIZES_ORDER:
                    cuda_row = cuda_type[cuda_type['Size'] == size]
                    seq_row = seq_type[seq_type['Size'] == size]
                    
                    if not cuda_row.empty and not seq_row.empty:
                        speedup = seq_row['Time_Algo_s'].mean() / cuda_row['Time_Algo_s'].mean()
                        speedups.append((size, speedup))
                
                if speedups:
                    best = max(speedups, key=lambda x: x[1])
                    worst = min(speedups, key=lambda x: x[1])
                    f.write(f"  {type_label}:\n")
                    f.write(f"    - Miglior speedup: {best[0]} -> {best[1]:.2f}x\n")
                    f.write(f"    - Peggior speedup: {worst[0]} -> {worst[1]:.2f}x\n")
        
        f.write("\n" + "=" * 70 + "\n")
        f.write("Grafici generati in: {}\n".format(PLOTS_DIR))
        f.write("=" * 70 + "\n")
    
    print(f"[OK] Report: {report_file}")

# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 70)
    print("VF2++ CUDA 64 Threads - Performance Analysis vs Sequenziale")
    print("=" * 70)
    print()
    
    # Carica dati
    cuda_df = load_cuda_data()
    seq_df = load_seq_data()
    
    if cuda_df is None or len(cuda_df) == 0:
        print("[ERRORE] Nessun dato CUDA disponibile")
        return
    
    print(f"\nDati caricati:")
    print(f"  - CUDA 64T: {len(cuda_df)} record")
    if seq_df is not None:
        print(f"  - SEQ: {len(seq_df)} record")
    print()
    
    # Genera grafici
    print("Generazione grafici...")
    plot_cuda_vs_seq_time(cuda_df, seq_df)
    plot_speedup_by_optimizer(cuda_df, seq_df)
    plot_time_breakdown(cuda_df)
    plot_iso_vs_diff_comparison(cuda_df, seq_df)
    plot_scaling_analysis(cuda_df, seq_df)
    plot_throughput(cuda_df, seq_df)
    
    # Genera report
    print("\nGenerazione report...")
    generate_summary_report(cuda_df, seq_df)
    
    print()
    print("=" * 70)
    print(f"Analisi completata! Grafici salvati in: {PLOTS_DIR}")
    print("=" * 70)

if __name__ == "__main__":
    main()
