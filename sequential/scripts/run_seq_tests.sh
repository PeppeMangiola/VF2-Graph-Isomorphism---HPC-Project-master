#!/bin/bash

# ==================================================================
# SCRIPT BENCHMARK SEQUENZIALE - VF2++ (Versione Completa)
# ==================================================================
# Esegue benchmark sequenziale per tutti gli ottimizzatori (O0-O3)
# Include calcolo Throughput MB/s
#
# REQUISITI:
#   - Eseguibili sequenziali compilati (make sequential)
#   - Input generati in inputs/inputs/
#
# USO:
#   ./run_seq_tests.sh
# ==================================================================

# 1. Setup Percorsi
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"

INPUT_DIR="$PROJECT_ROOT/inputs/inputs"
BUILD_DIR="$PROJECT_ROOT/build"
SEQ_DIR="$PROJECT_ROOT/sequential"
OUTPUT_DIR="$SEQ_DIR/output"

# 2. Configurazione
SIZES=("1MB" "50MB" "100MB" "200MB" "500MB")
OPTIMIZERS=("O0" "O1" "O2" "O3")
TYPES=("iso" "diff")

echo "=========================================="
echo "   BENCHMARK SEQUENZIALE VF2++"
echo "=========================================="
echo "Root:       $PROJECT_ROOT"
echo "Output Dir: $OUTPUT_DIR"
echo "Sizes:      ${SIZES[*]}"
echo "Types:      ${TYPES[*]}"
echo "=========================================="

# 3. Crea directory output
mkdir -p "$OUTPUT_DIR"

# 4. Ci posizioniamo nella ROOT del progetto
cd "$PROJECT_ROOT" || { echo "ERRORE: Impossibile andare in $PROJECT_ROOT"; exit 1; }

# Funzione per creare header CSV
create_csv_header() {
    local csv_file=$1
    local header="Size,Type,Nodes,Edges,RAM_Graph_MB,Time_Load_s,Time_VF2_s,Time_Total_s,Isomorphic,Throughput_MB_s"
    echo "$header" > "$csv_file"
}

echo ""
echo "Inizio benchmark..."
echo ""

# Ciclo Ottimizzatori
for OPT in "${OPTIMIZERS[@]}"; do
    
    # Trova eseguibile
    EXE="$BUILD_DIR/vf2pp_seq_${OPT}"
    if [ -f "$EXE.exe" ]; then
        EXE="$EXE.exe"
    fi
    
    if [ ! -f "$EXE" ]; then
        echo "[SKIP] Eseguibile mancante: vf2pp_seq_${OPT}"
        continue
    fi
    
    echo "=========================================="
    echo "OTTIMIZZATORE: $OPT"
    echo "=========================================="
    
    # File CSV per questo ottimizzatore
    # File CSV per questo ottimizzatore
    CSV_FILE="$OUTPUT_DIR/results_${OPT}.csv"
    
    # Crea l'header SOLO se il file non esiste ancora
    if [ ! -f "$CSV_FILE" ]; then
        create_csv_header "$CSV_FILE"
    fi
    
    # Ciclo Taglie
    for SIZE in "${SIZES[@]}"; do
        for TYPE in "${TYPES[@]}"; do
            
            G1="$INPUT_DIR/${SIZE}_${TYPE}_g1.txt"
            G2="$INPUT_DIR/${SIZE}_${TYPE}_g2.txt"
            
            if [ ! -f "$G1" ] || [ ! -f "$G2" ]; then
                echo "  [SKIP] $SIZE $TYPE - file non trovati"
                continue
            fi
            
            echo -n "  [RUN] $OPT | $SIZE | $TYPE ... "
            
            # Esegui e cattura output
            OUTPUT=$("$EXE" "$G1" "$G2" 0 2>&1)
            
            # Estrai metriche
            NODES=$(echo "$OUTPUT" | grep "Nodi:" | head -1 | awk '{print $2}' | tr -d '\r')
            EDGES=$(echo "$OUTPUT" | grep "Archi:" | head -1 | awk '{print $2}' | tr -d '\r')
            RAM_MB=$(echo "$OUTPUT" | grep "RAM Totale Grafi:" | awk '{print $4}' | tr -d '\r')
            TIME_LOAD=$(echo "$OUTPUT" | grep "Tempo caricamento:" | awk '{print $3}' | tr -d 's\r')
            TIME_VF2=$(echo "$OUTPUT" | grep "Tempo VF2++:" | awk '{print $3}' | tr -d 's\r')
            TIME_TOTAL=$(echo "$OUTPUT" | grep "Tempo totale:" | awk '{print $3}' | tr -d 's\r')
            
            # Determina se isomorfo
            if echo "$OUTPUT" | grep -q "ISOMORFI"; then
                ISOMORPHIC=1
            else
                ISOMORPHIC=0
            fi
            
            # Default values
            [ -z "$NODES" ] && NODES="0"
            [ -z "$EDGES" ] && EDGES="0"
            [ -z "$RAM_MB" ] && RAM_MB="0"
            [ -z "$TIME_LOAD" ] && TIME_LOAD="0"
            [ -z "$TIME_VF2" ] && TIME_VF2="0"
            [ -z "$TIME_TOTAL" ] && TIME_TOTAL="0"
            
            # Calcola Throughput MB/s
         # --- FIX ROBUSTO: Debug + AWK ---
            
            # 1. Pulizia aggressiva: tieni solo numeri, punti e 'e' (per notazione scientifica)
            #    Sostituisce anche le virgole con punti per sicurezza.
            C_RAM=$(echo "$RAM_MB" | tr ',' '.' | tr -cd '0-9.eE-')
            C_TIME=$(echo "$TIME_VF2" | tr ',' '.' | tr -cd '0-9.eE-')

            # 2. DEBUG: Decommenta la riga sotto se esce ancora 0 per vedere cosa legge davvero
            # echo "DEBUG: RAM grezza='$RAM_MB' -> pulita='$C_RAM' | TIME grezza='$TIME_VF2' -> pulita='$C_TIME'"

            # 3. Calcolo con AWK (gestisce float, notazione scientifica e div/0 automaticamente)
            THROUGHPUT=$(awk -v r="$C_RAM" -v t="$C_TIME" 'BEGIN { if (t>0) printf "%.4f", r/t; else print "0" }')
            
            # Fallback se awk fallisce (es. stringa vuota)
            [ -z "$THROUGHPUT" ] && THROUGHPUT="0"
            
            # Scrivi riga CSV
            printf "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n" \
                "$SIZE" "$TYPE" "$NODES" "$EDGES" "$RAM_MB" \
                "$TIME_LOAD" "$TIME_VF2" "$TIME_TOTAL" "$ISOMORPHIC" "$THROUGHPUT" >> "$CSV_FILE"
            
            echo "done (VF2++: ${TIME_VF2}s, Throughput: ${THROUGHPUT} MB/s)"
        done
    done
    
    echo ""
    echo "[OK] Salvato: $CSV_FILE"
    echo ""
done

echo "=========================================="
echo "BENCHMARK SEQUENZIALE COMPLETATO"
echo "=========================================="
echo ""
echo "File salvati in: $OUTPUT_DIR"
ls -la "$OUTPUT_DIR"/*.csv 2>/dev/null
echo ""
echo "Prossimi passi:"
echo "  - Grafici: python sequential/scripts/plot_benchmark.py"
echo ""
