#!/usr/bin/env python3
"""
=============================================================================
VF2++ Sequential Benchmark - Analisi e Visualizzazione Performance
=============================================================================

Questo script:
1. Legge automaticamente tutti i CSV dalla directory ../output/
2. Estrae i tempi di esecuzione VF2++ per ogni ottimizzatore (O0, O1, O2, O3)
3. Genera grafici comparativi (barplot)
4. Salva i grafici come immagini PNG ad alta risoluzione

Colonna analizzata: Time_VF2_s (tempo di esecuzione algoritmo VF2++)

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
# CONFIGURAZIONE PERCORSI
# =============================================================================

# Directory dello script
SCRIPT_DIR = Path(__file__).parent

# Directory dei CSV (../output rispetto allo script)
CSV_DIR = SCRIPT_DIR.parent / "output"

# Directory di output per i grafici (../plots rispetto allo script)
OUTPUT_DIR = SCRIPT_DIR.parent / "plots"

# Colonna contenente il tempo di esecuzione VF2++
TIME_COLUMN = "Time_VF2_s"

# =============================================================================
# CONFIGURAZIONE GRAFICI
# =============================================================================

# Stile grafici
plt.style.use('seaborn-v0_8-whitegrid')
COLORS = ['#2ecc71', '#3498db', '#9b59b6', '#e74c3c']  # Verde, Blu, Viola, Rosso per O0-O3
FIGSIZE_LARGE = (14, 8)
FIGSIZE_MEDIUM = (12, 7)
DPI = 150

# =============================================================================
# FUNZIONI DI UTILITÀ
# =============================================================================

def load_all_csv_files(directory):
    """
    Carica tutti i file CSV nella directory specificata.
    
    Returns:
        dict: Dizionario {nome_ottimizzatore: DataFrame}
    """
    csv_pattern = os.path.join(directory, "results_*.csv")
    csv_files = glob.glob(csv_pattern)
    
    if not csv_files:
        print(f"[ERRORE] Nessun file CSV trovato in: {directory}")
        print(f"[INFO] Pattern cercato: {csv_pattern}")
        return {}
    
    data = {}
    
    for filepath in sorted(csv_files):
        filename = os.path.basename(filepath)
        # Estrae il nome dell'ottimizzatore dal filename (es: results_O3.csv -> O3)
        optimizer = filename.replace("results_", "").replace(".csv", "")
        
        try:
            df = pd.read_csv(filepath)
            
            if TIME_COLUMN not in df.columns:
                print(f"[WARNING] Colonna '{TIME_COLUMN}' non trovata in {filename}")
                continue
            
            data[optimizer] = df
            print(f"[OK] Caricato: {filename} ({len(df)} righe)")
            
        except Exception as e:
            print(f"[ERRORE] Impossibile leggere {filename}: {e}")
    
    return data


def categorize_ram_size(ram_mb):
    """
    Categorizza la RAM in etichette leggibili.
    """
    if ram_mb <= 2:
        return "1 MB"
    elif ram_mb <= 55:
        return "50 MB"
    elif ram_mb <= 105:
        return "100 MB"
    elif ram_mb <= 205:
        return "200 MB"
    else:
        return "500 MB"


# =============================================================================
# FUNZIONI DI PLOTTING
# =============================================================================

def plot_barplot_by_size(data, output_dir):
    """
    Crea un barplot raggruppato che confronta i tempi VF2++ 
    per ogni ottimizzatore e dimensione di input.
    
    Considera SOLO i casi isomorfi (Isomorphic=1) dove VF2++ lavora davvero.
    """
    print("\n[PLOT] Generazione barplot comparativo per dimensione...")
    
    # Prepara dati per il plot
    plot_data = []
    
    for optimizer, df in data.items():
        # Filtra solo casi isomorfi (dove VF2++ lavora davvero)
        df_iso = df[df["Isomorphic"] == 1].copy()
        
        if df_iso.empty:
            continue
        
        # Aggiungi categoria RAM
        df_iso["RAM_Category"] = df_iso["RAM_Graph_MB"].apply(categorize_ram_size)
        
        for _, row in df_iso.iterrows():
            plot_data.append({
                "Optimizer": optimizer,
                "RAM_Category": row["RAM_Category"],
                "Time_VF2_s": row[TIME_COLUMN]
            })
    
    if not plot_data:
        print("[WARNING] Nessun dato disponibile per il barplot")
        return
    
    df_plot = pd.DataFrame(plot_data)
    
    # Ordine delle categorie RAM
    ram_order = ["1 MB", "50 MB", "100 MB", "200 MB", "500 MB"]
    df_plot["RAM_Category"] = pd.Categorical(df_plot["RAM_Category"], 
                                              categories=ram_order, 
                                              ordered=True)
    
    # Pivot per il barplot
    pivot_df = df_plot.pivot_table(index="RAM_Category", 
                                    columns="Optimizer", 
                                    values="Time_VF2_s",
                                    aggfunc="mean")
    
    # Ordina colonne (ottimizzatori)
    pivot_df = pivot_df.reindex(sorted(pivot_df.columns), axis=1)
    
    # Crea figura
    fig, ax = plt.subplots(figsize=FIGSIZE_LARGE)
    
    # Barplot
    x = np.arange(len(pivot_df.index))
    width = 0.18
    n_optimizers = len(pivot_df.columns)
    
    for i, (optimizer, color) in enumerate(zip(pivot_df.columns, COLORS)):
        offset = (i - n_optimizers/2 + 0.5) * width
        bars = ax.bar(x + offset, pivot_df[optimizer], width, 
                      label=optimizer, color=color, edgecolor='black', linewidth=0.5)
        
        # Aggiungi valori sopra le barre
        for bar, val in zip(bars, pivot_df[optimizer]):
            if pd.notna(val) and val > 0:
                ax.annotate(f'{val:.2f}s',
                           xy=(bar.get_x() + bar.get_width()/2, bar.get_height()),
                           xytext=(0, 3),
                           textcoords="offset points",
                           ha='center', va='bottom',
                           fontsize=8, fontweight='bold')
    
    # Configurazione assi
    ax.set_xlabel("Dimensione Input (RAM)", fontsize=12, fontweight='bold')
    ax.set_ylabel("Tempo VF2++ (secondi) - Scala Log", fontsize=12, fontweight='bold')
    ax.set_title("Confronto Tempi VF2++ - Versione Sequenziale\n(Solo casi isomorfi)",
                 fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(pivot_df.index, fontsize=11)
    ax.legend(title="Ottimizzatore", fontsize=10, title_fontsize=11)
    ax.grid(axis='y', alpha=0.3)
    
    # Scala logaritmica per l'asse Y (i tempi variano molto)
    ax.set_yscale('log')
    
    plt.tight_layout()
    
    # Salva
    output_path = output_dir / "barplot_vf2_time_by_size.png"
    plt.savefig(output_path, dpi=DPI, bbox_inches='tight', facecolor='white')
    print(f"[SALVATO] {output_path}")
    plt.close()


def plot_barplot_linear(data, output_dir):
    """
    Crea un barplot con scala lineare per ogni dimensione separatamente.
    Più facile da leggere per confronti diretti.
    """
    print("\n[PLOT] Generazione barplot scala lineare per ogni dimensione...")
    
    # Prepara dati
    plot_data = []
    
    for optimizer, df in data.items():
        df_iso = df[df["Isomorphic"] == 1].copy()
        if df_iso.empty:
            continue
        
        df_iso["RAM_Category"] = df_iso["RAM_Graph_MB"].apply(categorize_ram_size)
        
        for _, row in df_iso.iterrows():
            plot_data.append({
                "Optimizer": optimizer,
                "RAM_Category": row["RAM_Category"],
                "Time_VF2_s": row[TIME_COLUMN]
            })
    
    if not plot_data:
        return
    
    df_plot = pd.DataFrame(plot_data)
    ram_order = ["1 MB", "50 MB", "100 MB", "200 MB", "500 MB"]
    
    # Crea subplot per ogni dimensione
    fig, axes = plt.subplots(1, 5, figsize=(18, 5))
    fig.suptitle("Tempo VF2++ per Dimensione Input - Confronto Ottimizzatori\n(Solo casi isomorfi)",
                 fontsize=14, fontweight='bold', y=1.02)
    
    for idx, ram_cat in enumerate(ram_order):
        ax = axes[idx]
        df_size = df_plot[df_plot["RAM_Category"] == ram_cat]
        
        if df_size.empty:
            ax.set_visible(False)
            continue
        
        # Raggruppa per ottimizzatore
        grouped = df_size.groupby("Optimizer")[TIME_COLUMN].mean().sort_index()
        
        bars = ax.bar(grouped.index, grouped.values, 
                      color=COLORS[:len(grouped)], edgecolor='black', linewidth=0.5)
        
        # Valori sopra le barre
        for bar, val in zip(bars, grouped.values):
            ax.annotate(f'{val:.3f}s',
                       xy=(bar.get_x() + bar.get_width()/2, bar.get_height()),
                       xytext=(0, 3),
                       textcoords="offset points",
                       ha='center', va='bottom',
                       fontsize=9, fontweight='bold')
        
        ax.set_title(ram_cat, fontsize=12, fontweight='bold')
        ax.set_xlabel("Ottimizzatore", fontsize=10)
        if idx == 0:
            ax.set_ylabel("Tempo (s)", fontsize=10)
        ax.grid(axis='y', alpha=0.3)
        ax.tick_params(axis='x', rotation=0)
    
    plt.tight_layout()
    
    output_path = output_dir / "barplot_vf2_time_linear_by_size.png"
    plt.savefig(output_path, dpi=DPI, bbox_inches='tight', facecolor='white')
    print(f"[SALVATO] {output_path}")
    plt.close()


def plot_speedup(data, output_dir):
    """
    Crea un grafico dello speedup relativo rispetto a O0 (baseline).
    """
    print("\n[PLOT] Generazione grafico speedup relativo...")
    
    if "O0" not in data:
        print("[WARNING] O0 non trovato, impossibile calcolare speedup")
        return
    
    # Prepara dati
    plot_data = []
    
    for optimizer, df in data.items():
        df_iso = df[df["Isomorphic"] == 1].copy()
        if df_iso.empty:
            continue
        
        df_iso["RAM_Category"] = df_iso["RAM_Graph_MB"].apply(categorize_ram_size)
        
        for _, row in df_iso.iterrows():
            plot_data.append({
                "Optimizer": optimizer,
                "RAM_Category": row["RAM_Category"],
                "Time_VF2_s": row[TIME_COLUMN]
            })
    
    df_plot = pd.DataFrame(plot_data)
    
    # Calcola speedup rispetto a O0
    ram_order = ["1 MB", "50 MB", "100 MB", "200 MB", "500 MB"]
    
    speedup_data = []
    
    for ram_cat in ram_order:
        df_size = df_plot[df_plot["RAM_Category"] == ram_cat]
        
        # Tempo O0 per questa dimensione
        t_o0 = df_size[df_size["Optimizer"] == "O0"]["Time_VF2_s"].mean()
        
        if pd.isna(t_o0) or t_o0 == 0:
            continue
        
        for optimizer in df_size["Optimizer"].unique():
            t_opt = df_size[df_size["Optimizer"] == optimizer]["Time_VF2_s"].mean()
            speedup = t_o0 / t_opt if t_opt > 0 else 0
            
            speedup_data.append({
                "Optimizer": optimizer,
                "RAM_Category": ram_cat,
                "Speedup": speedup
            })
    
    if not speedup_data:
        return
    
    df_speedup = pd.DataFrame(speedup_data)
    
    # Pivot
    pivot_df = df_speedup.pivot_table(index="RAM_Category", 
                                       columns="Optimizer", 
                                       values="Speedup")
    
    # Ordina
    pivot_df = pivot_df.reindex(ram_order)
    pivot_df = pivot_df.reindex(sorted(pivot_df.columns), axis=1)
    
    # Plot
    fig, ax = plt.subplots(figsize=FIGSIZE_LARGE)
    
    pivot_df.plot(kind='bar', ax=ax, color=COLORS[:len(pivot_df.columns)],
                  edgecolor='black', linewidth=0.5)
    
    # Linea di riferimento (speedup = 1)
    ax.axhline(y=1, color='red', linestyle='--', linewidth=2, label='Baseline (O0)')
    
    ax.set_xlabel("Dimensione Input (RAM)", fontsize=12, fontweight='bold')
    ax.set_ylabel("Speedup (rispetto a O0)", fontsize=12, fontweight='bold')
    ax.set_title("Speedup Ottimizzatori rispetto a O0\n(Speedup = Tempo_O0 / Tempo_Opt)",
                 fontsize=14, fontweight='bold')
    ax.legend(title="Ottimizzatore", fontsize=10)
    ax.grid(axis='y', alpha=0.3)
    ax.tick_params(axis='x', rotation=0)
    
    plt.tight_layout()
    
    output_path = output_dir / "speedup_vs_O0.png"
    plt.savefig(output_path, dpi=DPI, bbox_inches='tight', facecolor='white')
    print(f"[SALVATO] {output_path}")
    plt.close()


def plot_summary_table(data, output_dir):
    """
    Crea una tabella riepilogativa come immagine.
    """
    print("\n[PLOT] Generazione tabella riepilogativa...")
    
    # Prepara dati
    summary = []
    
    for optimizer, df in sorted(data.items()):
        df_iso = df[df["Isomorphic"] == 1]
        
        if df_iso.empty:
            continue
        
        times = df_iso[TIME_COLUMN]
        
        summary.append({
            "Ottimizzatore": optimizer,
            "Min (s)": f"{times.min():.4f}",
            "Max (s)": f"{times.max():.2f}",
            "Media (s)": f"{times.mean():.2f}",
            "Std Dev": f"{times.std():.2f}",
            "Totale (s)": f"{times.sum():.2f}"
        })
    
    if not summary:
        return
    
    df_summary = pd.DataFrame(summary)
    
    # Crea figura con tabella
    fig, ax = plt.subplots(figsize=(10, 3))
    ax.axis('off')
    
    table = ax.table(cellText=df_summary.values,
                     colLabels=df_summary.columns,
                     cellLoc='center',
                     loc='center',
                     colColours=['#3498db']*len(df_summary.columns))
    
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1.2, 1.8)
    
    # Stile header
    for i in range(len(df_summary.columns)):
        table[(0, i)].set_text_props(fontweight='bold', color='white')
    
    plt.title("Riepilogo Statistiche Tempi VF2++ (Solo casi isomorfi)",
              fontsize=14, fontweight='bold', pad=20)
    
    plt.tight_layout()
    
    output_path = output_dir / "summary_table.png"
    plt.savefig(output_path, dpi=DPI, bbox_inches='tight', facecolor='white')
    print(f"[SALVATO] {output_path}")
    plt.close()


# =============================================================================
# MAIN
# =============================================================================

def main():
    """
    Funzione principale.
    """
    print("=" * 70)
    print("VF2++ SEQUENTIAL BENCHMARK - ANALISI PERFORMANCE")
    print("=" * 70)
    
    print(f"\nDirectory script: {SCRIPT_DIR}")
    print(f"Directory CSV:    {CSV_DIR}")
    print(f"Directory output: {OUTPUT_DIR}")
    
    # Verifica che la directory CSV esista
    if not CSV_DIR.exists():
        print(f"\n[ERRORE] Directory CSV non trovata: {CSV_DIR}")
        return
    
    # Crea directory output
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    # Carica tutti i CSV
    print("\n" + "-" * 70)
    print("CARICAMENTO DATI")
    print("-" * 70)
    
    data = load_all_csv_files(CSV_DIR)
    
    if not data:
        print("\n[ERRORE] Nessun dato caricato. Verifica i file CSV.")
        return
    
    print(f"\nOttimizzatori trovati: {sorted(data.keys())}")
    
    # Genera grafici
    print("\n" + "-" * 70)
    print("GENERAZIONE GRAFICI")
    print("-" * 70)
    
    plot_barplot_by_size(data, OUTPUT_DIR)
    plot_barplot_linear(data, OUTPUT_DIR)
    plot_speedup(data, OUTPUT_DIR)
    plot_summary_table(data, OUTPUT_DIR)
    
    # Riepilogo finale
    print("\n" + "=" * 70)
    print("COMPLETATO!")
    print("=" * 70)
    print(f"\nGrafici salvati in: {OUTPUT_DIR}")
    print("\nFile generati:")
    for f in sorted(OUTPUT_DIR.glob("*.png")):
        print(f"  - {f.name}")


if __name__ == "__main__":
    main()
