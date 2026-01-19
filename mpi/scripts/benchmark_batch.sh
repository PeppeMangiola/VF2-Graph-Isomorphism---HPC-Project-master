#!/bin/bash

# ==================================================================
# BENCHMARK BATCH MPI - VF2++
# ==================================================================
# Confronta le prestazioni della modalità batch:
# - Sequenziale: un processo elabora tutte le coppie
# - MPI: le coppie sono distribuite tra i processi
#
# REQUISITI:
#   - Input batch generati in inputs/batch/
#   - Eseguibili compilati (make mpi)
#
# USO:
#   ./benchmark_batch.sh [num_pairs] [target_mb]
# ==================================================================

set -e

# Setup percorsi
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"

INPUT_DIR="$PROJECT_ROOT/inputs/batch"
BUILD_DIR="$PROJECT_ROOT/build"
OUTPUT_DIR="$PROJECT_ROOT/mpi/output"
MPI_EXE="$BUILD_DIR/vf2pp_mpi_O3"

# Parametri
NUM_PAIRS=${1:-20}
TARGET_MB=${2:-5}
PROC_COUNTS=(1 2 4)

echo "=========================================="
echo "   BENCHMARK BATCH VF2++"
echo "=========================================="
echo "Coppie:      $NUM_PAIRS"
echo "Target MB:   $TARGET_MB"
echo "Processi:    ${PROC_COUNTS[*]}"
echo "=========================================="
echo ""

# Verifica eseguibile MPI
if [ ! -f "$MPI_EXE" ] && [ ! -f "$MPI_EXE.exe" ]; then
    echo "[ERRORE] Eseguibile MPI non trovato!"
    echo "         Esegui: make mpi"
    exit 1
fi

# Aggiungi .exe se necessario (Windows/WSL)
[ -f "$MPI_EXE.exe" ] && MPI_EXE="$MPI_EXE.exe"

# 1. Genera input batch se non esistono o se richiesto numero diverso
ACTUAL_PAIRS=$(ls -1 "$INPUT_DIR"/pair_*_g1.txt 2>/dev/null | wc -l)

if [ "$ACTUAL_PAIRS" -lt "$NUM_PAIRS" ] || [ ! -d "$INPUT_DIR" ]; then
    echo "[INFO] Generazione input batch..."
    cd "$PROJECT_ROOT/inputs"
    python3 generate_batch_inputs.py "$NUM_PAIRS" "$TARGET_MB"
    cd "$PROJECT_ROOT"
    ACTUAL_PAIRS=$(ls -1 "$INPUT_DIR"/pair_*_g1.txt 2>/dev/null | wc -l)
fi

echo "[INFO] Coppie trovate: $ACTUAL_PAIRS"
echo ""

# Crea directory output
mkdir -p "$OUTPUT_DIR"

# File CSV risultati
CSV_FILE="$OUTPUT_DIR/batch_results.csv"
printf "Mode,NumProcs,NumPairs,TotalTime_s,AvgTime_s,Throughput,Speedup,Efficiency\n" > "$CSV_FILE"

# Array per salvare i tempi
declare -a TIMES

# 2. Benchmark MPI per ogni numero di processi
echo "=========================================="
echo "BENCHMARK MPI BATCH"
echo "=========================================="

for i in "${!PROC_COUNTS[@]}"; do
    NP="${PROC_COUNTS[$i]}"
    
    echo ""
    echo "--- MPI np=$NP ---"
    
    # Esegui MPI batch mode e cattura output
    OUTPUT=$(mpirun --oversubscribe -np "$NP" "$MPI_EXE" --batch "$INPUT_DIR" 2>&1)
    
    # Estrai tempo totale dall'output
    MPI_WALL_TIME=$(echo "$OUTPUT" | grep "Tempo totale MPI:" | awk '{print $4}' | tr -d 's\r\n')
    [ -z "$MPI_WALL_TIME" ] && MPI_WALL_TIME="0"
    
    # Estrai throughput
    MPI_THROUGHPUT=$(echo "$OUTPUT" | grep "Throughput:" | awk '{print $2}' | tr -d '\r\n')
    [ -z "$MPI_THROUGHPUT" ] && MPI_THROUGHPUT="0"
    
    # Salva tempo per calcolo speedup
    TIMES[$i]="$MPI_WALL_TIME"
    
    # Calcola tempo medio
    MPI_AVG_TIME=$(echo "scale=6; $MPI_WALL_TIME / $ACTUAL_PAIRS" | bc)
    
    # Calcola speedup e efficienza (rispetto a np=1)
    if [ "$i" -eq 0 ]; then
        SPEEDUP="1.0000"
        EFFICIENCY="100.00"
        BASELINE_TIME="$MPI_WALL_TIME"
    else
        SPEEDUP=$(echo "scale=4; $BASELINE_TIME / $MPI_WALL_TIME" | bc)
        EFFICIENCY=$(echo "scale=2; $SPEEDUP / $NP * 100" | bc)
    fi
    
    # Determina mode label
    if [ "$NP" -eq 1 ]; then
        MODE="SEQ"
    else
        MODE="MPI"
    fi
    
    echo "Tempo totale:       ${MPI_WALL_TIME}s"
    echo "Tempo medio:        ${MPI_AVG_TIME}s"
    echo "Throughput:         ${MPI_THROUGHPUT} coppie/s"
    echo "Speedup:            ${SPEEDUP}x"
    echo "Efficienza:         ${EFFICIENCY}%"
    
    # Scrivi risultato
    printf "%s,%d,%d,%s,%s,%s,%s,%s\n" \
        "$MODE" "$NP" "$ACTUAL_PAIRS" "$MPI_WALL_TIME" "$MPI_AVG_TIME" \
        "$MPI_THROUGHPUT" "$SPEEDUP" "$EFFICIENCY" >> "$CSV_FILE"
done

echo ""
echo "=========================================="
echo "BENCHMARK BATCH COMPLETATO"
echo "=========================================="
echo ""
echo "Risultati salvati in: $CSV_FILE"
echo ""
cat "$CSV_FILE"
echo ""
echo "Per generare grafici: python mpi/scripts/plot_batch_results.py"
echo ""
