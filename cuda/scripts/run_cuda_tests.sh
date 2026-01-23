#!/bin/bash

# ==================================================================
# SCRIPT BENCHMARK CUDA - VF2++
# ==================================================================

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"

INPUT_DIR="$PROJECT_ROOT/inputs/inputs"
BUILD_DIR="$PROJECT_ROOT/build"
SEQ_OUTPUT_DIR="$PROJECT_ROOT/sequential/output"
CUDA_OUTPUT_DIR="$PROJECT_ROOT/cuda/output"

SIZES=("1MB" "50MB" "100MB" "200MB" "500MB")
OPTIMIZERS=("O0" "O1" "O2" "O3")
TYPES=("iso" "diff")

echo "=========================================="
echo "   BENCHMARK CUDA VF2++"
echo "=========================================="

mkdir -p "$CUDA_OUTPUT_DIR"
cd "$PROJECT_ROOT" || exit 1

# Funzione per leggere tempo sequenziale
get_seq_time() {
    local opt=$1
    local size=$2
    local type=$3
    local csv_file="$SEQ_OUTPUT_DIR/results_${opt}.csv"
    
    if [ ! -f "$csv_file" ]; then
        echo "0"
        return
    fi
    
    local time=$(grep "^${size},${type}," "$csv_file" 2>/dev/null | head -1 | cut -d',' -f7 | tr -d '\r\n')
    
    if [ -z "$time" ]; then
        echo "0"
    else
        echo "$time"
    fi
}

format_decimal() {
    local num=$1
    if [[ "$num" == .* ]]; then
        echo "0$num"
    elif [[ "$num" == -.* ]]; then
        echo "-0${num:1}"
    else
        echo "$num"
    fi
}

# Funzione per estrarre numero da linea "Label: 0.123456 s"
extract_number() {
    echo "$1" | grep -oE '[0-9]+\.[0-9]+' | head -1
}

for OPT in "${OPTIMIZERS[@]}"; do
    
    EXE="$BUILD_DIR/vf2pp_cuda_${OPT}"
    if [ -f "$EXE.exe" ]; then
        EXE="$EXE.exe"
    fi
    
    if [ ! -f "$EXE" ]; then
        echo "[SKIP] Eseguibile non trovato: vf2pp_cuda_${OPT}"
        continue
    fi
    
    echo "=========================================="
    echo "OTTIMIZZATORE: $OPT"
    echo "=========================================="
    
    CSV_FILE="$CUDA_OUTPUT_DIR/results_${OPT}.csv"
    echo "Size,Type,Nodes,Edges,RAM_MB,Threads,Time_Load_s,Time_VF2_s,Time_Total_s,Seq_Time_s,Speedup,Throughput_MB_s" > "$CSV_FILE"
    
    for SIZE in "${SIZES[@]}"; do
        for TYPE in "${TYPES[@]}"; do
            
            G1="$INPUT_DIR/${SIZE}_${TYPE}_g1.txt"
            G2="$INPUT_DIR/${SIZE}_${TYPE}_g2.txt"
            
            if [ ! -f "$G1" ] || [ ! -f "$G2" ]; then
                echo "  [SKIP] $SIZE $TYPE - file non trovati"
                continue
            fi
            
            FIRST_LINE=$(head -1 "$G1" | tr -d '\r')
            NODES=$(echo "$FIRST_LINE" | awk '{print $1}')
            EDGES=$(echo "$FIRST_LINE" | awk '{print $2}')
            
            SEQ_TIME=$(get_seq_time "$OPT" "$SIZE" "$TYPE")
            
            echo -n "  [RUN] $OPT | $SIZE $TYPE ... "
            
            # Esegui e cattura output
            OUTPUT=$("$EXE" "$G1" "$G2" 0 2>&1)
            
            # Parsing robusto: estrai numeri decimali dalle righe
            TIME_LOAD=$(echo "$OUTPUT" | grep "Tempo caricamento:" | extract_number)
            TIME_VF2=$(echo "$OUTPUT" | grep "Tempo VF2++ CUDA:" | extract_number)
            TIME_TOTAL=$(echo "$OUTPUT" | grep "Tempo totale:" | extract_number)
            RAM_MB=$(echo "$OUTPUT" | grep "RAM Grafi:" | extract_number)
            
            # Default
            [ -z "$TIME_LOAD" ] && TIME_LOAD="0"
            [ -z "$TIME_VF2" ] && TIME_VF2="0"
            [ -z "$TIME_TOTAL" ] && TIME_TOTAL="0"
            [ -z "$RAM_MB" ] && RAM_MB="0"
            
            # Calcola metriche
            SPEEDUP="0"
            THROUGHPUT="0"
            
            if [ "$TIME_VF2" != "0" ]; then
                if [ "$RAM_MB" != "0" ]; then
                    THROUGHPUT=$(echo "scale=4; $RAM_MB / $TIME_VF2" | bc 2>/dev/null)
                    THROUGHPUT=$(format_decimal "$THROUGHPUT")
                    [ -z "$THROUGHPUT" ] && THROUGHPUT="0"
                fi
                
                if [ "$SEQ_TIME" != "0" ]; then
                    SPEEDUP=$(echo "scale=4; $SEQ_TIME / $TIME_VF2" | bc 2>/dev/null)
                    SPEEDUP=$(format_decimal "$SPEEDUP")
                    [ -z "$SPEEDUP" ] && SPEEDUP="0"
                fi
            fi
            
            # Scrivi CSV
            echo "$SIZE,$TYPE,$NODES,$EDGES,$RAM_MB,64,$TIME_LOAD,$TIME_VF2,$TIME_TOTAL,$SEQ_TIME,$SPEEDUP,$THROUGHPUT" >> "$CSV_FILE"
            
            echo "done (T: ${TIME_VF2}s, S: ${SPEEDUP}x)"
        done
    done
    
    echo ""
    echo "[OK] Risultati: $CSV_FILE"
    echo ""
done

echo "=========================================="
echo "BENCHMARK CUDA COMPLETATO"
echo "=========================================="
