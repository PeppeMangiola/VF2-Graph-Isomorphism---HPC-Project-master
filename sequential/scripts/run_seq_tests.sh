#!/bin/bash

# ==================================================================
# SCRIPT BENCHMARK SEQUENZIALE - VF2++ (Versione Bash Corretta)
# ==================================================================
# Posizione file: sequential/scripts/run_seq_tests.sh
# ==================================================================

# 1. Setup Percorsi Assoluti
# Ottiene la cartella dove si trova lo script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
# Risale di due livelli per trovare la root del progetto
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"

INPUT_DIR="$PROJECT_ROOT/inputs/inputs"
BUILD_DIR="$PROJECT_ROOT/build"
SEQ_DIR="$PROJECT_ROOT/sequential"
OUTPUT_DIR="$SEQ_DIR/output"

# 2. FILE TEMPORANEO (Deve corrispondere esattamente al path nel main.c)
# Il tuo main.c scrive in: "./sequential/output/risultati_seq_mix.csv"
# Quindi il file assoluto è:
TEMP_FILE="$OUTPUT_DIR/risultati_seq_mix.csv"

# Configurazione Test
SIZES=("1MB" "50MB" "100MB" "200MB" "500MB")
OPTIMIZERS=("O0" "O1" "O2" "O3")
TYPES=("iso" "diff")

echo "=========================================="
echo "   BENCHMARK SEQUENZIALE VF2++ (BASH)    "
echo "=========================================="
echo "Root:       $PROJECT_ROOT"
echo "Output Dir: $OUTPUT_DIR"
echo "=========================================="

# 3. Creazione Cartelle Necessarie
mkdir -p "$OUTPUT_DIR"

# 4. IMPORTANTE: Ci posizioniamo nella ROOT del progetto
# Così il percorso relativo del C "./sequential/output/..." funziona.
cd "$PROJECT_ROOT" || { echo "ERRORE: Impossibile andare in $PROJECT_ROOT"; exit 1; }

echo ""
echo "Inizio benchmark..."
echo ""

# Ciclo Taglie
for SIZE in "${SIZES[@]}"; do
    echo "----------------------------------------"
    echo ">>> Taglia: $SIZE"
    
    # Ciclo Ottimizzatori
    for OPT in "${OPTIMIZERS[@]}"; do
        
        # Trova eseguibile (gestisce sia Linux che Windows/GitBash)
        EXE="$BUILD_DIR/vf2pp_seq_${OPT}.exe"
        if [ ! -f "$EXE" ]; then
            EXE="$BUILD_DIR/vf2pp_seq_${OPT}"
        fi
        
        if [ ! -f "$EXE" ]; then
            echo "    [SKIP] Eseguibile mancante: vf2pp_seq_${OPT}"
            continue
        fi

        # Definiamo il file CSV finale per QUESTO ottimizzatore
        FINAL_CSV="$OUTPUT_DIR/results_${OPT}.csv"

        # Ciclo Tipi (Isomorfi / Non Isomorfi)
        for TYPE in "${TYPES[@]}"; do
            
            G1="$INPUT_DIR/${SIZE}_${TYPE}_g1.txt"
            G2="$INPUT_DIR/${SIZE}_${TYPE}_g2.txt"
            
            if [ ! -f "$G1" ] || [ ! -f "$G2" ]; then
                # Salta silenziosamente se mancano gli input
                continue
            fi
            
            # A. PULIZIA: Rimuoviamo il file temporaneo vecchio se esiste
            if [ -f "$TEMP_FILE" ]; then
                rm "$TEMP_FILE"
            fi
            
            echo "    [RUN] $OPT | $SIZE | $TYPE ..."
            
            # B. ESECUZIONE
            # Eseguiamo dalla root. Il main creerà il file in sequential/output/risultati_seq_mix.csv
            "$EXE" "$G1" "$G2" 0
            
            # C. SMISTAMENTO (Sposta o Appendi)
            if [ -f "$TEMP_FILE" ]; then
                if [ ! -f "$FINAL_CSV" ]; then
                    # Se il CSV finale non esiste, spostiamo il file temporaneo (con Header)
                    mv "$TEMP_FILE" "$FINAL_CSV"
                else
                    # Se esiste, appendiamo solo l'ultima riga (dati) saltando l'header
                    tail -n 1 "$TEMP_FILE" >> "$FINAL_CSV"
                    rm "$TEMP_FILE"
                fi
            else
                echo "    [ERR] Output non generato! Controlla i percorsi."
            fi
            
        done # Fine Type
    done # Fine Opt
done # Fine Size

echo ""
echo "=========================================="
echo "Benchmark completato."
echo "File salvati in: $OUTPUT_DIR"
echo "=========================================="