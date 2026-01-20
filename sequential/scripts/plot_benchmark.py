#!/usr/bin/env python3
"""
=============================================================================
VF2++ Sequential Benchmark - Analisi e Visualizzazione Performance
=============================================================================

Questo script:
1. Legge automaticamente tutti i CSV dalla directory ../output/
2. Genera grafici comparativi SEPARATI per grafi ISOMORFI e NON ISOMORFI
3. Include analisi Throughput (MB/s)
4. Salva i grafici come immagini PNG ad alta risoluzione

Posizione: sequential/scripts/plot_benchmark.py
CSV input: sequential/output/results_*.csv
Grafici output: sequential/plots/

=============================================================================
"""

import os
import glob
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

# =============================================================================
# CONFIGURAZIONE
# =============================================================================

SCRIPT_DIR = Path(__file__).parent
CSV_DIR = SCRIPT_DIR.parent / "output"
OUTPUT_DIR = SCRIPT_DIR.parent / "plots"

TIME_COLUMN = "Time_VF2_s"
THROUGHPUT_COLUMN = "Throughput_MB_s"

plt.style.use('seaborn-v0_8-whitegrid')
COLORS = ['#2ecc71', '#3498db', '#9b59b6', '#e74c3c']  # O0, O1, O2, O3
FIGSIZE_LARGE = (14, 8)
FIGSIZE_MEDIUM = (12, 7)
DPI = 150

COLOR_ISO = '#3498db'
COLOR_DIFF = '#e74c3c'

SIZE_ORDER = ['1MB', '50MB', '100MB', '200MB', '500MB']

# =============================================================================
# FUNZIONI DI UTILITÀ
# =============================================================================

def load_all_csv_files(directory):
    """Carica tutti i file CSV nella directory specificata."""
    csv_pattern = os.path.join(directory, "results_*.csv")
    csv_files = glob.glob(csv_pattern)
    
    if not csv_files:
        print(f"[ERRORE] Nessun file CSV trovato in: {directory}")
        return {}
    
    data = {}
    
    for filepath in sorted(csv_files):
        filename = os.path.basename(filepath)
        optimizer = filename.replace("results_", "").replace(".csv", "")
        
        try:
            df = pd.read_csv(filepath)
            
            # Aggiungi colonna Type se non presente
            if 'Type' not in df.columns and 'Isomorphic' in df.columns:
                df['Type'] = df['Isomorphic'].apply(lambda x: 'iso' if x == 1 else 'diff')
            
            # Calcola Throughput se non presente
            if THROUGHPUT_COLUMN not in df.columns and 'RAM_Graph_MB' in df.columns:
                df[THROUGHPUT_COLUMN] = df.apply(
                    lambda row: row['RAM_Graph_MB'] / row[TIME_COLUMN] if row[TIME_COLUMN] > 0 else 0, 
                    axis=1
                )
            
            data[optimizer] = df
            print(f"[OK] Caricato: {filename} ({len(df)} righe)")
            
        except Exception as e:
            print(f"[ERRORE] Impossibile leggere {filename}: {e}")
    
    return data


def get_size_from_ram(ram_mb):
    """Converte RAM in etichetta Size."""
    if ram_mb <= 2:
        return "1MB"
    elif ram_mb <= 55:
        return "50MB"
    elif ram_mb <= 105:
        return "100MB"
    elif ram_mb <= 205:
        return "200MB"
    else:
        return "500MB"


def ensure_size_column(df):
    """Assicura che il DataFrame abbia la colonna Size."""
    if 'Size' not in df.columns and 'RAM_Graph_MB' in df.columns:
        df['Size'] = df['RAM_Graph_MB'].apply(get_size_from_ram)
    return df


# =============================================================================
# FUNZIONI DI PLOTTING - TEMPI
# =============================================================================

def plot_time_by_size(data, output_dir, graph_type='iso'):
    """Barplot tempi VF2++ per dimensione e ottimizzatore."""
    type_label = "Isomorfi" if graph_type == 'iso' else "Non Isomorfi"
    
    print(f"\n[PLOT] Barplot tempi per dimensione ({type_label})...")
    
    plot_data = []
    
    for optimizer, df in data.items():
        df = ensure_size_column(df)
        df_filtered = df[df['Type'] == graph_type] if 'Type' in df.columns else df[df['Isomorphic'] == (1 if graph_type == 'iso' else 0)]
        
        if df_filtered.empty:
            continue
        
        for _, row in df_filtered.iterrows():
            plot_data.append({
                "Optimizer": optimizer,
                "Size": row.get('Size', get_size_from_ram(row.get('RAM_Graph_MB', 0))),
                "Time_VF2_s": row[TIME_COLUMN]
            })
    
    if not plot_data:
        print(f"[WARNING] Nessun dato per grafi {type_label}")
        return
    
    df_plot = pd.DataFrame(plot_data)
    df_plot['Size'] = pd.Categorical(df_plot['Size'], categories=SIZE_ORDER, ordered=True)
    
    pivot_df = df_plot.pivot_table(index='Size', columns='Optimizer', values='Time_VF2_s', aggfunc='mean')
    pivot_df = pivot_df.reindex(sorted(pivot_df.columns), axis=1)
    
    fig, ax = plt.subplots(figsize=FIGSIZE_LARGE)
    
    x = np.arange(len(pivot_df.index))
    width = 0.18
    n_opt = len(pivot_df.columns)
    
    for i, (opt, color) in enumerate(zip(pivot_df.columns, COLORS)):
        offset = (i - n_opt/2 + 0.5) * width
        values = pivot_df[opt].values
        bars = ax.bar(x + offset, values, width, label=opt, color=color, edgecolor='black', linewidth=0.5)
        
        for bar, val in zip(bars, values):
            if pd.notna(val) and val > 0:
                ax.annotate(f'{val:.2f}s',
                           xy=(bar.get_x() + bar.get_width()/2, bar.get_height()),
                           xytext=(0, 3), textcoords="offset points",
                           ha='center', va='bottom', fontsize=8, fontweight='bold')
    
    ax.set_xlabel("Dimensione Input", fontsize=12, fontweight='bold')
    ax.set_ylabel("Tempo VF2++ (s) - Scala Log", fontsize=12, fontweight='bold')
    ax.set_title(f"Tempi VF2++ Sequenziale per Ottimizzatore\n(Grafi {type_label})", fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(pivot_df.index)
    ax.set_yscale('log')
    ax.legend(title="Ottimizzatore")
    ax.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    filepath = output_dir / f"seq_time_by_size_{graph_type}.png"
    plt.savefig(filepath, dpi=DPI, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"[SALVATO] {filepath.name}")


def plot_time_linear_by_size(data, output_dir, graph_type='iso'):
    """Barplot scala lineare per ogni dimensione."""
    type_label = "Isomorfi" if graph_type == 'iso' else "Non Isomorfi"
    
    print(f"\n[PLOT] Barplot scala lineare ({type_label})...")
    
    plot_data = []
    
    for optimizer, df in data.items():
        df = ensure_size_column(df)
        df_filtered = df[df['Type'] == graph_type] if 'Type' in df.columns else df[df['Isomorphic'] == (1 if graph_type == 'iso' else 0)]
        
        if df_filtered.empty:
            continue
        
        for _, row in df_filtered.iterrows():
            plot_data.append({
                "Optimizer": optimizer,
                "Size": row.get('Size', get_size_from_ram(row.get('RAM_Graph_MB', 0))),
                "Time_VF2_s": row[TIME_COLUMN]
            })
    
    if not plot_data:
        return
    
    df_plot = pd.DataFrame(plot_data)
    
    fig, axes = plt.subplots(1, 5, figsize=(18, 5))
    fig.suptitle(f"Tempo VF2++ per Dimensione - Confronto Ottimizzatori\n(Grafi {type_label})",
                 fontsize=14, fontweight='bold', y=1.02)
    
    for idx, size in enumerate(SIZE_ORDER):
        ax = axes[idx]
        df_size = df_plot[df_plot['Size'] == size]
        
        if df_size.empty:
            ax.set_visible(False)
            continue
        
        grouped = df_size.groupby('Optimizer')['Time_VF2_s'].mean().sort_index()
        
        bars = ax.bar(grouped.index, grouped.values, color=COLORS[:len(grouped)], edgecolor='black', linewidth=0.5)
        
        for bar, val in zip(bars, grouped.values):
            ax.annotate(f'{val:.3f}s', xy=(bar.get_x() + bar.get_width()/2, bar.get_height()),
                       xytext=(0, 3), textcoords="offset points", ha='center', va='bottom',
                       fontsize=9, fontweight='bold')
        
        ax.set_title(size, fontsize=12, fontweight='bold')
        ax.set_xlabel("Ottimizzatore", fontsize=10)
        if idx == 0:
            ax.set_ylabel("Tempo (s)", fontsize=10)
        ax.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    filepath = output_dir / f"seq_time_linear_{graph_type}.png"
    plt.savefig(filepath, dpi=DPI, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"[SALVATO] {filepath.name}")


# =============================================================================
# FUNZIONI DI PLOTTING - SPEEDUP (rispetto a O0)
# =============================================================================

def plot_speedup_vs_O0(data, output_dir, graph_type='iso'):
    """Speedup degli ottimizzatori rispetto a O0."""
    type_label = "Isomorfi" if graph_type == 'iso' else "Non Isomorfi"
    
    print(f"\n[PLOT] Speedup vs O0 ({type_label})...")
    
    if 'O0' not in data:
        print("[WARNING] O0 non trovato")
        return
    
    plot_data = []
    
    for optimizer, df in data.items():
        df = ensure_size_column(df)
        df_filtered = df[df['Type'] == graph_type] if 'Type' in df.columns else df[df['Isomorphic'] == (1 if graph_type == 'iso' else 0)]
        
        for _, row in df_filtered.iterrows():
            plot_data.append({
                "Optimizer": optimizer,
                "Size": row.get('Size', get_size_from_ram(row.get('RAM_Graph_MB', 0))),
                "Time_VF2_s": row[TIME_COLUMN]
            })
    
    df_plot = pd.DataFrame(plot_data)
    
    speedup_data = []
    for size in SIZE_ORDER:
        df_size = df_plot[df_plot['Size'] == size]
        t_o0 = df_size[df_size['Optimizer'] == 'O0']['Time_VF2_s'].mean()
        
        if pd.isna(t_o0) or t_o0 == 0:
            continue
        
        for opt in df_size['Optimizer'].unique():
            t_opt = df_size[df_size['Optimizer'] == opt]['Time_VF2_s'].mean()
            speedup = t_o0 / t_opt if t_opt > 0 else 0
            speedup_data.append({"Optimizer": opt, "Size": size, "Speedup": speedup})
    
    if not speedup_data:
        return
    
    df_speedup = pd.DataFrame(speedup_data)
    pivot_df = df_speedup.pivot_table(index='Size', columns='Optimizer', values='Speedup')
    pivot_df = pivot_df.reindex(SIZE_ORDER)
    pivot_df = pivot_df.reindex(sorted(pivot_df.columns), axis=1)
    
    fig, ax = plt.subplots(figsize=FIGSIZE_LARGE)
    
    pivot_df.plot(kind='bar', ax=ax, color=COLORS[:len(pivot_df.columns)], edgecolor='black', linewidth=0.5)
    
    ax.axhline(y=1, color='red', linestyle='--', linewidth=2, label='Baseline (O0)')
    
    ax.set_xlabel("Dimensione Input", fontsize=12, fontweight='bold')
    ax.set_ylabel("Speedup (rispetto a O0)", fontsize=12, fontweight='bold')
    ax.set_title(f"Speedup Ottimizzatori rispetto a O0\n(Grafi {type_label})", fontsize=14, fontweight='bold')
    ax.legend(title="Ottimizzatore")
    ax.grid(axis='y', alpha=0.3)
    ax.tick_params(axis='x', rotation=0)
    
    plt.tight_layout()
    filepath = output_dir / f"seq_speedup_vs_O0_{graph_type}.png"
    plt.savefig(filepath, dpi=DPI, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"[SALVATO] {filepath.name}")


# =============================================================================
# FUNZIONI DI PLOTTING - THROUGHPUT
# =============================================================================

def plot_throughput(data, output_dir, graph_type='iso'):
    """Throughput (MB/s) per ottimizzatore e dimensione."""
    type_label = "Isomorfi" if graph_type == 'iso' else "Non Isomorfi"
    
    print(f"\n[PLOT] Throughput MB/s ({type_label})...")
    
    plot_data = []
    
    for optimizer, df in data.items():
        df = ensure_size_column(df)
        df_filtered = df[df['Type'] == graph_type] if 'Type' in df.columns else df[df['Isomorphic'] == (1 if graph_type == 'iso' else 0)]
        
        if df_filtered.empty:
            continue
        
        for _, row in df_filtered.iterrows():
            # Calcola throughput se non presente
            if THROUGHPUT_COLUMN in row and pd.notna(row[THROUGHPUT_COLUMN]):
                throughput = row[THROUGHPUT_COLUMN]
            elif 'RAM_Graph_MB' in row and row[TIME_COLUMN] > 0:
                throughput = row['RAM_Graph_MB'] / row[TIME_COLUMN]
            else:
                throughput = 0
            
            plot_data.append({
                "Optimizer": optimizer,
                "Size": row.get('Size', get_size_from_ram(row.get('RAM_Graph_MB', 0))),
                "Throughput_MB_s": throughput
            })
    
    if not plot_data:
        print(f"[WARNING] Nessun dato throughput per grafi {type_label}")
        return
    
    df_plot = pd.DataFrame(plot_data)
    df_plot['Size'] = pd.Categorical(df_plot['Size'], categories=SIZE_ORDER, ordered=True)
    
    pivot_df = df_plot.pivot_table(index='Size', columns='Optimizer', values='Throughput_MB_s', aggfunc='mean')
    pivot_df = pivot_df.reindex(sorted(pivot_df.columns), axis=1)
    
    fig, ax = plt.subplots(figsize=FIGSIZE_LARGE)
    
    x = np.arange(len(pivot_df.index))
    width = 0.18
    n_opt = len(pivot_df.columns)
    
    for i, (opt, color) in enumerate(zip(pivot_df.columns, COLORS)):
        offset = (i - n_opt/2 + 0.5) * width
        values = pivot_df[opt].values
        bars = ax.bar(x + offset, values, width, label=opt, color=color, edgecolor='black', linewidth=0.5)
        
        for bar, val in zip(bars, values):
            if pd.notna(val) and val > 0:
                ax.annotate(f'{val:.1f}',
                           xy=(bar.get_x() + bar.get_width()/2, bar.get_height()),
                           xytext=(0, 3), textcoords="offset points",
                           ha='center', va='bottom', fontsize=7, fontweight='bold')
    
    ax.set_xlabel("Dimensione Input", fontsize=12, fontweight='bold')
    ax.set_ylabel("Throughput (MB/s)", fontsize=12, fontweight='bold')
    ax.set_title(f"Throughput VF2++ Sequenziale\n(Grafi {type_label})", fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(pivot_df.index)
    ax.legend(title="Ottimizzatore")
    ax.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    filepath = output_dir / f"seq_throughput_{graph_type}.png"
    plt.savefig(filepath, dpi=DPI, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"[SALVATO] {filepath.name}")


def plot_throughput_scaling(data, output_dir, graph_type='iso'):
    """Come il throughput scala con la dimensione input."""
    type_label = "Isomorfi" if graph_type == 'iso' else "Non Isomorfi"
    
    print(f"\n[PLOT] Throughput scaling ({type_label})...")
    
    plot_data = []
    
    for optimizer, df in data.items():
        df = ensure_size_column(df)
        df_filtered = df[df['Type'] == graph_type] if 'Type' in df.columns else df[df['Isomorphic'] == (1 if graph_type == 'iso' else 0)]
        
        for _, row in df_filtered.iterrows():
            if THROUGHPUT_COLUMN in row and pd.notna(row[THROUGHPUT_COLUMN]):
                throughput = row[THROUGHPUT_COLUMN]
            elif 'RAM_Graph_MB' in row and row[TIME_COLUMN] > 0:
                throughput = row['RAM_Graph_MB'] / row[TIME_COLUMN]
            else:
                throughput = 0
            
            plot_data.append({
                "Optimizer": optimizer,
                "Size": row.get('Size', get_size_from_ram(row.get('RAM_Graph_MB', 0))),
                "Throughput_MB_s": throughput
            })
    
    if not plot_data:
        return
    
    df_plot = pd.DataFrame(plot_data)
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    markers = ['o', 's', '^', 'D']
    
    for i, opt in enumerate(sorted(df_plot['Optimizer'].unique())):
        df_opt = df_plot[df_plot['Optimizer'] == opt]
        
        throughputs = []
        for size in SIZE_ORDER:
            t = df_opt[df_opt['Size'] == size]['Throughput_MB_s'].mean()
            throughputs.append(t if pd.notna(t) else 0)
        
        ax.plot(SIZE_ORDER, throughputs, marker=markers[i % len(markers)], 
               color=COLORS[i % len(COLORS)], linewidth=2, markersize=10, label=opt)
    
    ax.set_xlabel("Dimensione Input", fontsize=12, fontweight='bold')
    ax.set_ylabel("Throughput (MB/s)", fontsize=12, fontweight='bold')
    ax.set_title(f"Scaling del Throughput con la Dimensione Input\n(Grafi {type_label})", fontsize=14, fontweight='bold')
    ax.legend(title="Ottimizzatore")
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    filepath = output_dir / f"seq_throughput_scaling_{graph_type}.png"
    plt.savefig(filepath, dpi=DPI, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"[SALVATO] {filepath.name}")


# =============================================================================
# CONFRONTO ISO vs DIFF
# =============================================================================

def plot_iso_vs_diff_comparison(data, output_dir):
    """Confronto diretto ISO vs DIFF."""
    print("\n[PLOT] Confronto ISO vs DIFF...")
    
    opt = 'O3' if 'O3' in data else list(data.keys())[0]
    df = ensure_size_column(data[opt])
    
    sizes = [s for s in SIZE_ORDER if s in df['Size'].unique()]
    
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    
    # Tempi
    ax1 = axes[0]
    x = np.arange(len(sizes))
    width = 0.35
    
    iso_times = []
    diff_times = []
    for size in sizes:
        iso_t = df[(df['Size'] == size) & (df['Type'] == 'iso')][TIME_COLUMN].mean()
        diff_t = df[(df['Size'] == size) & (df['Type'] == 'diff')][TIME_COLUMN].mean()
        iso_times.append(iso_t if pd.notna(iso_t) else 0)
        diff_times.append(diff_t if pd.notna(diff_t) else 0)
    
    ax1.bar(x - width/2, iso_times, width, label='Isomorfi', color=COLOR_ISO, alpha=0.8)
    ax1.bar(x + width/2, diff_times, width, label='Non Isomorfi', color=COLOR_DIFF, alpha=0.8)
    
    ax1.set_xlabel('Dimensione Input', fontsize=11)
    ax1.set_ylabel('Tempo VF2++ (s) - Log', fontsize=11)
    ax1.set_title(f'Tempi ({opt})', fontsize=12, fontweight='bold')
    ax1.set_xticks(x)
    ax1.set_xticklabels(sizes)
    ax1.set_yscale('log')
    ax1.legend()
    ax1.grid(True, alpha=0.3, axis='y')
    
    # Throughput
    ax2 = axes[1]
    
    iso_throughput = []
    diff_throughput = []
    for size in sizes:
        iso_row = df[(df['Size'] == size) & (df['Type'] == 'iso')]
        diff_row = df[(df['Size'] == size) & (df['Type'] == 'diff')]
        
        if not iso_row.empty and iso_row[TIME_COLUMN].values[0] > 0:
            iso_throughput.append(iso_row['RAM_Graph_MB'].values[0] / iso_row[TIME_COLUMN].values[0])
        else:
            iso_throughput.append(0)
        
        if not diff_row.empty and diff_row[TIME_COLUMN].values[0] > 0:
            diff_throughput.append(diff_row['RAM_Graph_MB'].values[0] / diff_row[TIME_COLUMN].values[0])
        else:
            diff_throughput.append(0)
    
    ax2.bar(x - width/2, iso_throughput, width, label='Isomorfi', color=COLOR_ISO, alpha=0.8)
    ax2.bar(x + width/2, diff_throughput, width, label='Non Isomorfi', color=COLOR_DIFF, alpha=0.8)
    
    ax2.set_xlabel('Dimensione Input', fontsize=11)
    ax2.set_ylabel('Throughput (MB/s)', fontsize=11)
    ax2.set_title(f'Throughput ({opt})', fontsize=12, fontweight='bold')
    ax2.set_xticks(x)
    ax2.set_xticklabels(sizes)
    ax2.legend()
    ax2.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    filepath = output_dir / "seq_comparison_iso_vs_diff.png"
    plt.savefig(filepath, dpi=DPI, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"[SALVATO] {filepath.name}")


# =============================================================================
# TABELLA RIEPILOGATIVA
# =============================================================================

def plot_summary_table(data, output_dir, graph_type='iso'):
    """Tabella riepilogativa."""
    type_label = "Isomorfi" if graph_type == 'iso' else "Non Isomorfi"
    
    print(f"\n[PLOT] Tabella riepilogativa ({type_label})...")
    
    summary = []
    
    for optimizer, df in sorted(data.items()):
        df = ensure_size_column(df)
        df_filtered = df[df['Type'] == graph_type] if 'Type' in df.columns else df[df['Isomorphic'] == (1 if graph_type == 'iso' else 0)]
        
        if df_filtered.empty:
            continue
        
        times = df_filtered[TIME_COLUMN]
        
        # Calcola throughput medio
        if THROUGHPUT_COLUMN in df_filtered.columns:
            avg_throughput = df_filtered[THROUGHPUT_COLUMN].mean()
        else:
            avg_throughput = (df_filtered['RAM_Graph_MB'] / df_filtered[TIME_COLUMN]).mean()
        
        summary.append({
            "Opt": optimizer,
            "Min (s)": f"{times.min():.4f}",
            "Max (s)": f"{times.max():.2f}",
            "Media (s)": f"{times.mean():.2f}",
            "Avg MB/s": f"{avg_throughput:.1f}"
        })
    
    if not summary:
        return
    
    df_summary = pd.DataFrame(summary)
    
    fig, ax = plt.subplots(figsize=(8, 2.5))
    ax.axis('off')
    
    table = ax.table(cellText=df_summary.values,
                     colLabels=df_summary.columns,
                     cellLoc='center',
                     loc='center',
                     colColours=['#3498db']*len(df_summary.columns))
    
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1.2, 1.8)
    
    for i in range(len(df_summary.columns)):
        table[(0, i)].set_text_props(fontweight='bold', color='white')
    
    plt.title(f"Riepilogo Sequenziale (Grafi {type_label})", fontsize=14, fontweight='bold', pad=20)
    
    plt.tight_layout()
    filepath = output_dir / f"seq_summary_table_{graph_type}.png"
    plt.savefig(filepath, dpi=DPI, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"[SALVATO] {filepath.name}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 70)
    print("VF2++ SEQUENTIAL BENCHMARK - ANALISI PERFORMANCE")
    print("=" * 70)
    
    print(f"\nDirectory CSV:    {CSV_DIR}")
    print(f"Directory output: {OUTPUT_DIR}")
    
    if not CSV_DIR.exists():
        print(f"\n[ERRORE] Directory CSV non trovata: {CSV_DIR}")
        return
    
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    print("\n" + "-" * 70)
    print("CARICAMENTO DATI")
    print("-" * 70)
    
    data = load_all_csv_files(CSV_DIR)
    
    if not data:
        print("\n[ERRORE] Nessun dato caricato.")
        return
    
    print(f"\nOttimizzatori trovati: {sorted(data.keys())}")
    
    # GRAFICI ISOMORFI
    print("\n" + "-" * 70)
    print("GENERAZIONE GRAFICI - GRAFI ISOMORFI")
    print("-" * 70)
    
    plot_time_by_size(data, OUTPUT_DIR, 'iso')
    plot_time_linear_by_size(data, OUTPUT_DIR, 'iso')
    plot_speedup_vs_O0(data, OUTPUT_DIR, 'iso')
    plot_throughput(data, OUTPUT_DIR, 'iso')
    plot_throughput_scaling(data, OUTPUT_DIR, 'iso')
    plot_summary_table(data, OUTPUT_DIR, 'iso')
    
    # GRAFICI NON ISOMORFI
    print("\n" + "-" * 70)
    print("GENERAZIONE GRAFICI - GRAFI NON ISOMORFI")
    print("-" * 70)
    
    plot_time_by_size(data, OUTPUT_DIR, 'diff')
    plot_time_linear_by_size(data, OUTPUT_DIR, 'diff')
    plot_speedup_vs_O0(data, OUTPUT_DIR, 'diff')
    plot_throughput(data, OUTPUT_DIR, 'diff')
    plot_throughput_scaling(data, OUTPUT_DIR, 'diff')
    plot_summary_table(data, OUTPUT_DIR, 'diff')
    
    # CONFRONTO ISO vs DIFF
    print("\n" + "-" * 70)
    print("CONFRONTO ISO vs DIFF")
    print("-" * 70)
    
    plot_iso_vs_diff_comparison(data, OUTPUT_DIR)
    
    print("\n" + "=" * 70)
    print("COMPLETATO!")
    print("=" * 70)
    print(f"\nGrafici salvati in: {OUTPUT_DIR}")
    print("\nFile generati:")
    for f in sorted(OUTPUT_DIR.glob("*.png")):
        print(f"  - {f.name}")


if __name__ == "__main__":
    main()
