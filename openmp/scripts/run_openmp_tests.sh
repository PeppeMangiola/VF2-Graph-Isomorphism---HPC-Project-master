#!/bin/bash

# ==================================================================
# SCRIPT BENCHMARK OPENMP - VF2++ (Versione Completa)
# ==================================================================
# Esegue benchmark OpenMP per tutti gli ottimizzatori (O0-O3)
# Calcola speedup, efficienza, overhead e throughput
# 
# REQUISITI:
#   - Eseguibili OpenMP compilati (make openmp)
#   - Risultati sequenziali in sequential/output/results_O*.csv
#   - Input generati in inputs/inputs/
#
# USO:
#   ./run_openmp_tests.sh
# ==================================================================

# 1. Setup Percorsi
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"

INPUT_DIR="$PROJECT_ROOT/inputs/inputs"
BUILD_DIR="$PROJECT_ROOT/build"
SEQ_OUTPUT_DIR="$PROJECT_ROOT/sequential/output"
OMP_OUTPUT_DIR="$PROJECT_ROOT/openmp/output"

# 2. Configurazione
SIZES=("1MB" "50MB" "100MB" "200MB" "500MB")
OPTIMIZERS=("O0 O1 O2 O3")
TYPES=("iso" "diff")
THREAD_COUNTS=(1 2 4)

echo "=========================================="
echo "   BENCHMARK OPENMP VF2++"
echo "=========================================="
echo "Root:        $PROJECT_ROOT"
echo "Input:       $INPUT_DIR"
echo "SEQ Results: $SEQ_OUTPUT_DIR"
echo "OMP Output:  $OMP_OUTPUT_DIR"
echo "Thread:      ${THREAD_COUNTS[*]}"
echo "=========================================="
echo ""

# 3. Verifica prerequisiti
if [ ! -d "$SEQ_OUTPUT_DIR" ]; then
    echo "[ERRORE] Directory risultati sequenziali non trovata: $SEQ_OUTPUT_DIR"
    exit 1
fi

# 4. Crea directory output
mkdir -p "$OMP_OUTPUT_DIR"

cd "$PROJECT_ROOT" || exit 1

# 5. Funzione per leggere tempo sequenziale dal CSV
get_seq_time() {
    local opt=$1
    local size=$2
    local type=$3
    local csv_file="$SEQ_OUTPUT_DIR/results_${opt}.csv"
    
    if [ ! -f "$csv_file" ]; then
        echo "0"
        return
    fi
    
    local time=$(grep "^${size},${type}," "$csv_file" | head -1 | cut -d',' -f7 | tr -d '\r')
    
    if [ -z "$time" ] || [ "$time" = "" ]; then
        echo "0"
    else
        echo "$time"
    fi
}

# Funzione per formattare numeri decimali (aggiunge 0 se inizia con .)
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

# Funzione per creare header CSV
ensure_csv_header() {
    local csv_file=$1
    local header="Size,Type,Nodes,Edges,RAM_MB,NumThreads,Time_Load_s,Time_VF2_s,Time_Total_s,Seq_Time_s,Speedup,Efficiency,Overhead,Throughput_MB_s"
    
    if [ ! -f "$csv_file" ]; then
        echo "$header" > "$csv_file"
    elif [ ! -s "$csv_file" ]; then
        echo "$header" > "$csv_file"
    fi
}

# 6. Benchmark per ogni ottimizzatore
echo "Inizio benchmark OpenMP..."
echo ""

for OPT in "${OPTIMIZERS[@]}"; do
    
    EXE="$BUILD_DIR/vf2pp_openmp_${OPT}"
    if [ -f "$EXE.exe" ]; then
        EXE="$EXE.exe"
    fi
    
    if [ ! -f "$EXE" ]; then
        echo "[SKIP] Eseguibile non trovato: vf2pp_openmp_${OPT}"
        continue
    fi
    
    echo "=========================================="
    echo "OTTIMIZZATORE: $OPT"
    echo "=========================================="
    
    CSV_FILE="$OMP_OUTPUT_DIR/results_${OPT}.csv"
    ensure_csv_header "$CSV_FILE"
    
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
            
            for NT in "${THREAD_COUNTS[@]}"; do
                echo -n "  [RUN] $OPT | threads=$NT | $SIZE $TYPE ... "
                
                export OMP_NUM_THREADS=$NT
                OUTPUT=$("$EXE" "$G1" "$G2" 0 2>&1)
                
                TIME_LOAD=$(echo "$OUTPUT" | grep "Tempo caricamento:" | awk '{print $3}' | tr -d 's\r\n')
                TIME_VF2=$(echo "$OUTPUT" | grep "Tempo VF2++ OpenMP:" | awk '{print $4}' | tr -d 's\r\n')
                TIME_TOTAL=$(echo "$OUTPUT" | grep "Tempo totale:" | awk '{print $3}' | tr -d 's\r\n')
                RAM_MB=$(echo "$OUTPUT" | grep "RAM Totale Grafi:" | awk '{print $4}' | tr -d '\r\n')
                
                [ -z "$TIME_LOAD" ] && TIME_LOAD="0"
                [ -z "$TIME_VF2" ] && TIME_VF2="0"
                [ -z "$TIME_TOTAL" ] && TIME_TOTAL="0"
                [ -z "$RAM_MB" ] && RAM_MB="0"
                
                SPEEDUP="0"
                EFFICIENCY="0"
                OVERHEAD="0"
                THROUGHPUT="0"
                
                if [ "$TIME_VF2" != "0" ]; then
                    if [ "$RAM_MB" != "0" ]; then
                        THROUGHPUT=$(format_decimal "$(echo "scale=4; $RAM_MB / $TIME_VF2" | bc 2>/dev/null)")
                        [ -z "$THROUGHPUT" ] && THROUGHPUT="0"
                    fi
                    
                    if [ "$SEQ_TIME" != "0" ]; then
                        SPEEDUP=$(format_decimal "$(echo "scale=4; $SEQ_TIME / $TIME_VF2" | bc 2>/dev/null)")
                        [ -z "$SPEEDUP" ] && SPEEDUP="0"
                        
                        EFFICIENCY=$(format_decimal "$(echo "scale=2; $SPEEDUP / $NT * 100" | bc 2>/dev/null)")
                        [ -z "$EFFICIENCY" ] && EFFICIENCY="0"
                        
                        OVERHEAD=$(format_decimal "$(echo "scale=6; $TIME_VF2 * $NT - $SEQ_TIME" | bc 2>/dev/null)")
                        [ -z "$OVERHEAD" ] && OVERHEAD="0"
                    fi
                fi
                
                printf "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n" \
                    "$SIZE" "$TYPE" "$NODES" "$EDGES" "$RAM_MB" "$NT" \
                    "$TIME_LOAD" "$TIME_VF2" "$TIME_TOTAL" "$SEQ_TIME" \
                    "$SPEEDUP" "$EFFICIENCY" "$OVERHEAD" "$THROUGHPUT" >> "$CSV_FILE"
                
                echo "done (T: ${TIME_VF2}s, S: ${SPEEDUP}x)"
            done
        done
    done
    
    echo ""
    echo "[OK] Risultati: $CSV_FILE"
    echo ""
done

echo "=========================================="
echo "BENCHMARK OPENMP COMPLETATO"
echo "=========================================="
echo ""
echo "Prossimi passi:"
echo "  python openmp/scripts/plot_openmp_results.py"
echo ""
