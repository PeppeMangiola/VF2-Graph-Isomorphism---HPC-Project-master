#!/bin/bash

# ==================================================================
# SCRIPT BENCHMARK MPI - VF2++
# ==================================================================
# Esegue benchmark MPI per tutti gli ottimizzatori (O0-O3)
# Calcola speedup rispetto alla versione sequenziale
# 
# MODALITÀ APPEND: i nuovi risultati vengono aggiunti ai CSV esistenti
#                  se il file non esiste, viene creato con header
#
# REQUISITI:
#   - Eseguibili MPI compilati (make mpi)
#   - Risultati sequenziali in sequential/output/results_O*.csv
#   - Input generati in inputs/inputs/
#
# USO:
#   ./run_mpi_tests.sh
# ==================================================================

# 1. Setup Percorsi
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"

INPUT_DIR="$PROJECT_ROOT/inputs/inputs"
BUILD_DIR="$PROJECT_ROOT/build"
SEQ_OUTPUT_DIR="$PROJECT_ROOT/sequential/output"
MPI_OUTPUT_DIR="$PROJECT_ROOT/mpi/output"

# 2. Configurazione
SIZES=("1MB" "50MB" "100MB" "200MB" "500MB")
OPTIMIZERS=("O0" "O1" "O2" "O3")
TYPES=("iso" "diff")
PROC_COUNTS=(2 4)

echo "=========================================="
echo "   BENCHMARK MPI VF2++"
echo "=========================================="
echo "Root:        $PROJECT_ROOT"
echo "Input:       $INPUT_DIR"
echo "SEQ Results: $SEQ_OUTPUT_DIR"
echo "MPI Output:  $MPI_OUTPUT_DIR"
echo "Processi:    ${PROC_COUNTS[*]}"
echo "Modalità:    APPEND (preserva risultati precedenti)"
echo "=========================================="
echo ""

# 3. Verifica prerequisiti
if [ ! -d "$SEQ_OUTPUT_DIR" ]; then
    echo "[ERRORE] Directory risultati sequenziali non trovata: $SEQ_OUTPUT_DIR"
    echo "         Esegui prima: make benchmark_seq"
    exit 1
fi

# Verifica che esistano i CSV sequenziali
SEQ_CSV_COUNT=$(ls -1 "$SEQ_OUTPUT_DIR"/results_O*.csv 2>/dev/null | wc -l)
if [ "$SEQ_CSV_COUNT" -eq 0 ]; then
    echo "[ERRORE] Nessun file results_O*.csv trovato in $SEQ_OUTPUT_DIR"
    echo "         Esegui prima: make benchmark_seq"
    exit 1
fi

echo "[OK] Trovati $SEQ_CSV_COUNT file CSV sequenziali"

# 4. Crea directory output
mkdir -p "$MPI_OUTPUT_DIR"

# 5. Ci posizioniamo nella ROOT del progetto
cd "$PROJECT_ROOT" || { echo "ERRORE: Impossibile andare in $PROJECT_ROOT"; exit 1; }

# 6. Funzione per leggere tempo sequenziale dal CSV
get_seq_time() {
    local opt=$1
    local size=$2
    local type=$3
    local csv_file="$SEQ_OUTPUT_DIR/results_${opt}.csv"
    
    if [ ! -f "$csv_file" ]; then
        echo "0"
        return
    fi
    
    # Mappa size+type a numero riga (1-based, +1 per header)
    local row=0
    case "${size}_${type}" in
        "1MB_iso")   row=2 ;;
        "1MB_diff")  row=3 ;;
        "50MB_iso")  row=4 ;;
        "50MB_diff") row=5 ;;
        "100MB_iso")  row=6 ;;
        "100MB_diff") row=7 ;;
        "200MB_iso")  row=8 ;;
        "200MB_diff") row=9 ;;
        "500MB_iso")  row=10 ;;
        "500MB_diff") row=11 ;;
        *) echo "0"; return ;;
    esac
    
    # Estrai Time_VF2_s (colonna 4) dalla riga corretta, rimuovi \r
    local time=$(sed -n "${row}p" "$csv_file" | tr -d '\r' | cut -d',' -f4)
    
    if [ -z "$time" ] || [ "$time" = "" ]; then
        echo "0"
    else
        echo "$time"
    fi
}

# Funzione per pulire valori da \r e spazi
clean_value() {
    echo "$1" | tr -d '\r\n ' 
}

# Funzione per creare header CSV se il file non esiste o è vuoto
ensure_csv_header() {
    local csv_file=$1
    local header="Size,Type,Nodes,Edges,RAM_MB,NumProcs,Time_Load_s,Time_VF2_s,Time_Total_s,Seq_Time_s,Speedup,Efficiency,Overhead"
    
    if [ ! -f "$csv_file" ]; then
        # File non esiste: crea con header
        echo "$header" > "$csv_file"
        echo "[INFO] Creato nuovo file CSV: $csv_file"
    elif [ ! -s "$csv_file" ]; then
        # File esiste ma è vuoto: aggiungi header
        echo "$header" > "$csv_file"
        echo "[INFO] Aggiunto header a file CSV vuoto: $csv_file"
    fi
    # Se il file esiste e non è vuoto, non fare nulla (append)
}

# 7. Benchmark per ogni ottimizzatore
echo ""
echo "Inizio benchmark MPI..."
echo ""

for OPT in "${OPTIMIZERS[@]}"; do
    
    # Trova eseguibile MPI
    EXE="$BUILD_DIR/vf2pp_mpi_${OPT}"
    if [ -f "$EXE.exe" ]; then
        EXE="$EXE.exe"
    fi
    
    if [ ! -f "$EXE" ]; then
        echo "[SKIP] Eseguibile MPI non trovato: vf2pp_mpi_${OPT}"
        continue
    fi
    
    echo "=========================================="
    echo "OTTIMIZZATORE: $OPT"
    echo "=========================================="
    
    # File CSV output per questo ottimizzatore
    CSV_FILE="$MPI_OUTPUT_DIR/results_${OPT}.csv"
    
    # Assicura che il file abbia l'header (crea se non esiste, append se esiste)
    ensure_csv_header "$CSV_FILE"
    
    for SIZE in "${SIZES[@]}"; do
        for TYPE in "${TYPES[@]}"; do
            
            G1="$INPUT_DIR/${SIZE}_${TYPE}_g1.txt"
            G2="$INPUT_DIR/${SIZE}_${TYPE}_g2.txt"
            
            if [ ! -f "$G1" ] || [ ! -f "$G2" ]; then
                echo "  [SKIP] $SIZE $TYPE - file non trovati"
                continue
            fi
            
            # Leggi info grafo (prima riga: nodes edges) - pulisci \r
            FIRST_LINE=$(head -1 "$G1" | tr -d '\r')
            NODES=$(echo "$FIRST_LINE" | awk '{print $1}')
            EDGES=$(echo "$FIRST_LINE" | awk '{print $2}')
            
            # Leggi tempo sequenziale
            SEQ_TIME=$(get_seq_time "$OPT" "$SIZE" "$TYPE")
            
            for NP in "${PROC_COUNTS[@]}"; do
                echo -n "  [RUN] $OPT | np=$NP | $SIZE $TYPE ... "
                
                # Esegui MPI e cattura output
                OUTPUT=$(mpirun --oversubscribe -np "$NP" "$EXE" "$G1" "$G2" 0 2>&1)
                
                # Estrai metriche dall'output - pulisci ogni valore
                TIME_LOAD=$(echo "$OUTPUT" | grep "Tempo caricamento:" | awk '{print $3}' | tr -d 's\r\n')
                TIME_VF2=$(echo "$OUTPUT" | grep "Tempo VF2++ MPI:" | awk '{print $4}' | tr -d 's\r\n')
                TIME_TOTAL=$(echo "$OUTPUT" | grep "Tempo totale:" | awk '{print $3}' | tr -d 's\r\n')
                RAM_MB=$(echo "$OUTPUT" | grep "RAM Totale Grafi:" | awk '{print $4}' | tr -d '\r\n')
                
                # Default se parsing fallisce
                [ -z "$TIME_LOAD" ] && TIME_LOAD="0"
                [ -z "$TIME_VF2" ] && TIME_VF2="0"
                [ -z "$TIME_TOTAL" ] && TIME_TOTAL="0"
                [ -z "$RAM_MB" ] && RAM_MB="0"
                
                # Calcola metriche
                SPEEDUP="0"
                EFFICIENCY="0"
                OVERHEAD="0"
                
                if [ "$TIME_VF2" != "0" ] && [ "$SEQ_TIME" != "0" ]; then
                    SPEEDUP=$(echo "scale=4; $SEQ_TIME / $TIME_VF2" | bc 2>/dev/null)
                    [ -z "$SPEEDUP" ] && SPEEDUP="0"
                    
                    EFFICIENCY=$(echo "scale=2; $SPEEDUP / $NP * 100" | bc 2>/dev/null)
                    [ -z "$EFFICIENCY" ] && EFFICIENCY="0"
                    
                    OVERHEAD=$(echo "scale=6; $TIME_VF2 * $NP - $SEQ_TIME" | bc 2>/dev/null)
                    [ -z "$OVERHEAD" ] && OVERHEAD="0"
                fi
                
                # APPEND: Scrivi riga CSV
                printf "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n" \
                    "$SIZE" "$TYPE" "$NODES" "$EDGES" "$RAM_MB" "$NP" \
                    "$TIME_LOAD" "$TIME_VF2" "$TIME_TOTAL" "$SEQ_TIME" \
                    "$SPEEDUP" "$EFFICIENCY" "$OVERHEAD" >> "$CSV_FILE"
                
                echo "done (VF2++: ${TIME_VF2}s, Speedup: ${SPEEDUP}x, Eff: ${EFFICIENCY}%)"
            done
        done
    done
    
    # Conta righe nel CSV (escluso header)
    ROW_COUNT=$(($(wc -l < "$CSV_FILE") - 1))
    echo ""
    echo "[OK] Risultati aggiunti a: $CSV_FILE (totale: $ROW_COUNT righe)"
    echo ""
done

echo "=========================================="
echo "BENCHMARK MPI COMPLETATO"
echo "=========================================="
echo ""
echo "File aggiornati in: $MPI_OUTPUT_DIR"
ls -la "$MPI_OUTPUT_DIR"/*.csv 2>/dev/null
echo ""
echo "Nota: I nuovi risultati sono stati AGGIUNTI ai file esistenti"
echo ""
echo "Prossimi passi:"
echo "  - Confronto ottimizzatori: python mpi/scripts/plot_mpi_optimizers.py"
echo "  - Confronto SEQ vs MPI:    python mpi/scripts/plot_mpi_vs_seq.py"
echo ""
