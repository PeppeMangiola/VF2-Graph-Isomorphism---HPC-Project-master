#!/bin/bash
# =============================================================================
# VF2++ CUDA Benchmark Script
# Eseguire da WSL
# =============================================================================

set -e

# Directory
BUILD_DIR="./build"
INPUT_DIR="./inputs/inputs"
OUTPUT_DIR="./cuda/output"

# Crea output directory
mkdir -p "$OUTPUT_DIR"

# File output
CSV_FILE="$OUTPUT_DIR/test_cuda.csv"
SEQ_CSV="$OUTPUT_DIR/seq_baseline.csv"

# Ottimizzazioni da testare
OPT_LEVELS="O0 O1 O2 O3"

# Configurazioni GPU (threads per block)
THREAD_CONFIGS="64"

# Input sizes da testare
SIZES="1MB 50MB 100MB 200MB 500MB"

# Tipi di grafo
TYPES="iso diff"

# Numero ripetizioni per media
REPETITIONS=3

# Cleanup precedenti risultati

echo "=============================================="
echo "VF2++ CUDA Benchmark"
echo "=============================================="
echo ""


# =============================================================================
# BENCHMARK CUDA
# =============================================================================
echo ">>> Esecuzione benchmark CUDA..."

for opt in $OPT_LEVELS; do
    EXE="$BUILD_DIR/vf2pp_cuda_$opt.exe"
    
    if [[ ! -f "$EXE" ]]; then
        echo "[SKIP] Eseguibile $EXE non trovato"
        continue
    fi
    
    for threads in $THREAD_CONFIGS; do
        for size in $SIZES; do
            for type in $TYPES; do
                G1="$INPUT_DIR/${size}_${type}_g1.txt"
                G2="$INPUT_DIR/${size}_${type}_g2.txt"
                
                if [[ ! -f "$G1" || ! -f "$G2" ]]; then
                    continue
                fi
                
                for rep in $(seq 1 $REPETITIONS); do
                    echo "  CUDA $opt threads=$threads: $size $type (rep $rep)"
                    # blocks=0 per auto-calcolo
                    "$EXE" "$G1" "$G2" 0 $threads "$CSV_FILE"
                done
            done
        done
    done
done

echo ""
echo "=============================================="
echo "Benchmark completato!"
echo "=============================================="
echo ""
echo "Output CSV: $CSV_FILE"
echo "Baseline SEQ: $SEQ_CSV"
echo ""
echo "Per generare grafici, esegui da PowerShell:"
echo "  python cuda\\scripts\\plot_cuda_results.py"
