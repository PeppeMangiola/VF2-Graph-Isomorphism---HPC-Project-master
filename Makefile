# =============================================================================
# VF2++ Graph Isomorphism - HPC Project
# Makefile principale
# =============================================================================
#
# NOTA IMPORTANTE:
# - Compilazione e benchmark: eseguire da WSL con 'make <target>'
# - Generazione grafici: eseguire da PowerShell con 'python <script>'
#
# =============================================================================

# Compilatori
CC       = gcc
MPICC    = mpicc
NVCC     = nvcc

# Flag di base
CFLAGS_BASE  = -Wall -Wextra -std=c11 -D_POSIX_C_SOURCE=199309L
LDFLAGS      = -lm

# Flag OpenMP
OMP_FLAGS    = -fopenmp

# Flag CUDA
CUDA_FLAGS   = -arch=sm_60

# Livelli di ottimizzazione
OPT_LEVELS   = O0 O1 O2 O3

# Directory
COMMON_INC   = common/include
COMMON_SRC   = common/src
SEQ_SRC      = sequential/src
OMP_SRC      = openmp/src
OMP_INC      = openmp/include
MPI_SRC      = mpi/src
MPI_INC      = mpi/include
CUDA_SRC     = cuda/src
BUILD_DIR    = build
INPUT_DIR    = inputs/inputs
INPUT_BASE   = inputs

# File sorgenti comuni
COMMON_SOURCES = $(wildcard $(COMMON_SRC)/*.c)
COMMON_HEADERS = $(wildcard $(COMMON_INC)/*.h)

# File sorgenti MPI specifici
MPI_SOURCES    = $(MPI_SRC)/vf2pp_mpi.c
MPI_HEADERS    = $(MPI_INC)/vf2pp_mpi.h

# File sorgenti OpenMP specifici
OMP_SOURCES    = $(OMP_SRC)/vf2pp_openmp.c
OMP_HEADERS    = $(OMP_INC)/vf2pp_openmp.h

# =============================================================================
# TARGET PRINCIPALI
# =============================================================================

.PHONY: all clean help gen_inputs inputs test sequential openmp mpi cuda \
        test_seq benchmark_seq test_mpi benchmark_mpi test_openmp benchmark_openmp \
        inputs_batch benchmark_batch

all: sequential openmp mpi
	@echo "=== Build completata (SEQ, OpenMP, MPI) ==="

help:
	@echo "=============================================="
	@echo "VF2++ HPC Project - Makefile"
	@echo "=============================================="
	@echo ""
	@echo ">>> ESEGUIRE DA WSL <<<"
	@echo ""
	@echo "COMPILAZIONE:"
	@echo "  make sequential   - Compila versione sequenziale (O0-O3)"
	@echo "  make openmp       - Compila versione OpenMP (O0-O3)"
	@echo "  make mpi          - Compila versione MPI (O0-O3)"
	@echo "  make cuda         - Compila versione CUDA (O0-O3)"
	@echo "  make all          - Compila SEQ + OpenMP + MPI"
	@echo ""
	@echo "INPUT (WSL con python3):"
	@echo "  make inputs       - Genera input test (1MB-500MB)"
	@echo "  make inputs_batch - Genera input batch (20 coppie da 1MB)"
	@echo ""
	@echo "BENCHMARK SEQUENZIALE (WSL):"
	@echo "  make test_seq     - Test rapido su 1MB"
	@echo "  make benchmark_seq- Benchmark completo (O0-O3)"
	@echo ""
	@echo "BENCHMARK OPENMP (WSL):"
	@echo "  make test_openmp    - Test rapido OpenMP (1MB, 4 thread)"
	@echo "  make benchmark_openmp - Benchmark completo (O0-O3, 1-8 thread)"
	@echo ""
	@echo "BENCHMARK MPI (WSL):"
	@echo "  make test_mpi       - Test rapido MPI (1MB, np=2)"
	@echo "  make benchmark_mpi  - Benchmark single-pair (O0-O3, np=2,4)"
	@echo "  make benchmark_batch- Benchmark batch (np=1,2,4)"
	@echo ""
	@echo ">>> GRAFICI - ESEGUIRE DA POWERSHELL <<<"
	@echo ""
	@echo "  python sequential\\scripts\\plot_benchmark.py"
	@echo "  python openmp\\scripts\\plot_openmp_results.py"
	@echo "  python mpi\\scripts\\plot_mpi_optimizers.py"
	@echo "  python mpi\\scripts\\plot_mpi_vs_seq.py"
	@echo ""
	@echo "PULIZIA (WSL):"
	@echo "  make clean        - Rimuove build/"
	@echo "  make clean_all    - Rimuove build/ e input"
	@echo ""

# =============================================================================
# DIRECTORY
# =============================================================================

$(BUILD_DIR):
	@mkdir -p $(BUILD_DIR)

$(INPUT_DIR):
	@mkdir -p $(INPUT_DIR)

# =============================================================================
# GENERATORE INPUT (WSL con python3)
# =============================================================================

inputs: | $(INPUT_DIR)
	@echo "=== Generazione input (Python/NetworkX) ==="
	cd $(INPUT_BASE) && python3 gen_inputs.py
	@echo "[OK] Input generati in $(INPUT_DIR)/"

inputs_batch:
	@echo "=== Generazione input batch ==="
	@mkdir -p inputs/batch
	cd inputs && python3 generate_batch_inputs.py 20 5
	@echo "[OK] Input batch generati in inputs/batch/"

# =============================================================================
# VERSIONE SEQUENZIALE
# =============================================================================

SEQ_MAIN = $(SEQ_SRC)/main.c

sequential: $(addprefix $(BUILD_DIR)/vf2pp_seq_, $(OPT_LEVELS))
	@echo "[OK] Versione sequenziale compilata (O0-O3)"

$(BUILD_DIR)/vf2pp_seq_O0: $(SEQ_MAIN) $(COMMON_SOURCES) $(COMMON_HEADERS) | $(BUILD_DIR)
	$(CC) $(CFLAGS_BASE) -O0 -g -I$(COMMON_INC) $(SEQ_MAIN) $(COMMON_SOURCES) -o $@ $(LDFLAGS)

$(BUILD_DIR)/vf2pp_seq_O1: $(SEQ_MAIN) $(COMMON_SOURCES) $(COMMON_HEADERS) | $(BUILD_DIR)
	$(CC) $(CFLAGS_BASE) -O1 -I$(COMMON_INC) $(SEQ_MAIN) $(COMMON_SOURCES) -o $@ $(LDFLAGS)

$(BUILD_DIR)/vf2pp_seq_O2: $(SEQ_MAIN) $(COMMON_SOURCES) $(COMMON_HEADERS) | $(BUILD_DIR)
	$(CC) $(CFLAGS_BASE) -O2 -I$(COMMON_INC) $(SEQ_MAIN) $(COMMON_SOURCES) -o $@ $(LDFLAGS)

$(BUILD_DIR)/vf2pp_seq_O3: $(SEQ_MAIN) $(COMMON_SOURCES) $(COMMON_HEADERS) | $(BUILD_DIR)
	$(CC) $(CFLAGS_BASE) -O3 -I$(COMMON_INC) $(SEQ_MAIN) $(COMMON_SOURCES) -o $@ $(LDFLAGS)

# =============================================================================
# VERSIONE OPENMP
# =============================================================================

OMP_MAIN    = $(OMP_SRC)/main_openmp.c
OMP_VF2     = $(OMP_SRC)/vf2pp_openmp.c
OMP_ALL_SRC = $(OMP_MAIN) $(OMP_VF2) $(COMMON_SOURCES)
OMP_ALL_INC = -I$(COMMON_INC) -I$(OMP_INC)

openmp: $(addprefix $(BUILD_DIR)/vf2pp_openmp_, $(OPT_LEVELS))
	@echo "[OK] Versione OpenMP compilata (O0-O3)"

$(BUILD_DIR)/vf2pp_openmp_O0: $(OMP_MAIN) $(OMP_VF2) $(COMMON_SOURCES) $(COMMON_HEADERS) $(OMP_HEADERS) | $(BUILD_DIR)
	$(CC) $(CFLAGS_BASE) -O0 -g $(OMP_FLAGS) $(OMP_ALL_INC) $(OMP_ALL_SRC) -o $@ $(LDFLAGS)

$(BUILD_DIR)/vf2pp_openmp_O1: $(OMP_MAIN) $(OMP_VF2) $(COMMON_SOURCES) $(COMMON_HEADERS) $(OMP_HEADERS) | $(BUILD_DIR)
	$(CC) $(CFLAGS_BASE) -O1 $(OMP_FLAGS) $(OMP_ALL_INC) $(OMP_ALL_SRC) -o $@ $(LDFLAGS)

$(BUILD_DIR)/vf2pp_openmp_O2: $(OMP_MAIN) $(OMP_VF2) $(COMMON_SOURCES) $(COMMON_HEADERS) $(OMP_HEADERS) | $(BUILD_DIR)
	$(CC) $(CFLAGS_BASE) -O2 $(OMP_FLAGS) $(OMP_ALL_INC) $(OMP_ALL_SRC) -o $@ $(LDFLAGS)

$(BUILD_DIR)/vf2pp_openmp_O3: $(OMP_MAIN) $(OMP_VF2) $(COMMON_SOURCES) $(COMMON_HEADERS) $(OMP_HEADERS) | $(BUILD_DIR)
	$(CC) $(CFLAGS_BASE) -O3 $(OMP_FLAGS) $(OMP_ALL_INC) $(OMP_ALL_SRC) -o $@ $(LDFLAGS)

# =============================================================================
# VERSIONE MPI
# =============================================================================

MPI_MAIN = $(MPI_SRC)/main_mpi.c
MPI_VF2  = $(MPI_SRC)/vf2pp_mpi.c
MPI_ALL_SRC = $(MPI_MAIN) $(MPI_VF2) $(COMMON_SOURCES)
MPI_ALL_INC = -I$(COMMON_INC) -I$(MPI_INC)

mpi: $(addprefix $(BUILD_DIR)/vf2pp_mpi_, $(OPT_LEVELS))
	@echo "[OK] Versione MPI compilata (O0-O3)"

$(BUILD_DIR)/vf2pp_mpi_O0: $(MPI_MAIN) $(MPI_VF2) $(COMMON_SOURCES) $(COMMON_HEADERS) $(MPI_HEADERS) | $(BUILD_DIR)
	$(MPICC) $(CFLAGS_BASE) -O0 -g $(MPI_ALL_INC) $(MPI_ALL_SRC) -o $@ $(LDFLAGS)

$(BUILD_DIR)/vf2pp_mpi_O1: $(MPI_MAIN) $(MPI_VF2) $(COMMON_SOURCES) $(COMMON_HEADERS) $(MPI_HEADERS) | $(BUILD_DIR)
	$(MPICC) $(CFLAGS_BASE) -O1 $(MPI_ALL_INC) $(MPI_ALL_SRC) -o $@ $(LDFLAGS)

$(BUILD_DIR)/vf2pp_mpi_O2: $(MPI_MAIN) $(MPI_VF2) $(COMMON_SOURCES) $(COMMON_HEADERS) $(MPI_HEADERS) | $(BUILD_DIR)
	$(MPICC) $(CFLAGS_BASE) -O2 $(MPI_ALL_INC) $(MPI_ALL_SRC) -o $@ $(LDFLAGS)

$(BUILD_DIR)/vf2pp_mpi_O3: $(MPI_MAIN) $(MPI_VF2) $(COMMON_SOURCES) $(COMMON_HEADERS) $(MPI_HEADERS) | $(BUILD_DIR)
	$(MPICC) $(CFLAGS_BASE) -O3 $(MPI_ALL_INC) $(MPI_ALL_SRC) -o $@ $(LDFLAGS)

# =============================================================================
# VERSIONE CUDA
# =============================================================================

CUDA_MAIN    = $(CUDA_SRC)/main_cuda.c
CUDA_KERNEL  = $(CUDA_SRC)/vf2pp_kernel.cu

cuda: $(addprefix $(BUILD_DIR)/vf2pp_cuda_, $(OPT_LEVELS))
	@echo "[OK] Versione CUDA compilata (O0-O3)"

$(BUILD_DIR)/vf2pp_cuda_O0: $(CUDA_MAIN) $(CUDA_KERNEL) $(COMMON_SOURCES) $(COMMON_HEADERS) | $(BUILD_DIR)
	$(NVCC) $(CUDA_FLAGS) -O0 -g -I$(COMMON_INC) $(CUDA_MAIN) $(CUDA_KERNEL) $(COMMON_SOURCES) -o $@ $(LDFLAGS)

$(BUILD_DIR)/vf2pp_cuda_O1: $(CUDA_MAIN) $(CUDA_KERNEL) $(COMMON_SOURCES) $(COMMON_HEADERS) | $(BUILD_DIR)
	$(NVCC) $(CUDA_FLAGS) -O1 -I$(COMMON_INC) $(CUDA_MAIN) $(CUDA_KERNEL) $(COMMON_SOURCES) -o $@ $(LDFLAGS)

$(BUILD_DIR)/vf2pp_cuda_O2: $(CUDA_MAIN) $(CUDA_KERNEL) $(COMMON_SOURCES) $(COMMON_HEADERS) | $(BUILD_DIR)
	$(NVCC) $(CUDA_FLAGS) -O2 -I$(COMMON_INC) $(CUDA_MAIN) $(CUDA_KERNEL) $(COMMON_SOURCES) -o $@ $(LDFLAGS)

$(BUILD_DIR)/vf2pp_cuda_O3: $(CUDA_MAIN) $(CUDA_KERNEL) $(COMMON_SOURCES) $(COMMON_HEADERS) | $(BUILD_DIR)
	$(NVCC) $(CUDA_FLAGS) -O3 -I$(COMMON_INC) $(CUDA_MAIN) $(CUDA_KERNEL) $(COMMON_SOURCES) -o $@ $(LDFLAGS)

# =============================================================================
# TEST E BENCHMARK SEQUENZIALE (WSL)
# =============================================================================

test_seq: sequential
	@echo "=== Test rapido sequenziale (1MB) ==="
	@echo "--- Grafi isomorfi ---"
	./$(BUILD_DIR)/vf2pp_seq_O3 $(INPUT_DIR)/1MB_iso_g1.txt $(INPUT_DIR)/1MB_iso_g2.txt
	@echo ""
	@echo "--- Grafi non isomorfi ---"
	./$(BUILD_DIR)/vf2pp_seq_O3 $(INPUT_DIR)/1MB_diff_g1.txt $(INPUT_DIR)/1MB_diff_g2.txt

benchmark_seq: sequential
	@echo "=== Benchmark sequenziale ==="
	@mkdir -p sequential/output
	bash sequential/scripts/run_seq_tests.sh
	@echo ""
	@echo "[INFO] Per grafici, esegui da PowerShell:"
	@echo "       python sequential\\scripts\\plot_benchmark.py"

# =============================================================================
# TEST E BENCHMARK OPENMP (WSL)
# =============================================================================

test_openmp: openmp
	@echo "=== Test rapido OpenMP (1MB, 4 thread) ==="
	@mkdir -p openmp/output
	@echo "--- Grafi isomorfi ---"
	OMP_NUM_THREADS=4 ./$(BUILD_DIR)/vf2pp_openmp_O3 $(INPUT_DIR)/1MB_iso_g1.txt $(INPUT_DIR)/1MB_iso_g2.txt 1
	@echo ""
	@echo "--- Grafi non isomorfi ---"
	OMP_NUM_THREADS=4 ./$(BUILD_DIR)/vf2pp_openmp_O3 $(INPUT_DIR)/1MB_diff_g1.txt $(INPUT_DIR)/1MB_diff_g2.txt 1

benchmark_openmp: sequential openmp
	@echo "=== Benchmark OpenMP ==="
	@mkdir -p openmp/output
	@mkdir -p openmp/plots
	bash openmp/scripts/run_openmp_tests.sh
	@echo ""
	@echo "[INFO] Per grafici, esegui da PowerShell:"
	@echo "       python openmp\\scripts\\plot_openmp_results.py"

# =============================================================================
# TEST E BENCHMARK MPI (WSL)
# =============================================================================

test_mpi: mpi
	@echo "=== Test rapido MPI (1MB, 2 processi) ==="
	@mkdir -p mpi/output
	@echo "--- Grafi isomorfi ---"
	mpirun --oversubscribe -np 2 ./$(BUILD_DIR)/vf2pp_mpi_O3 $(INPUT_DIR)/1MB_iso_g1.txt $(INPUT_DIR)/1MB_iso_g2.txt
	@echo ""
	@echo "--- Grafi non isomorfi ---"
	mpirun --oversubscribe -np 2 ./$(BUILD_DIR)/vf2pp_mpi_O3 $(INPUT_DIR)/1MB_diff_g1.txt $(INPUT_DIR)/1MB_diff_g2.txt

benchmark_mpi: sequential mpi
	@echo "=== Benchmark MPI single-pair ==="
	@mkdir -p mpi/output
	bash mpi/scripts/run_mpi_tests.sh
	@echo ""
	@echo "[INFO] Per grafici, esegui da PowerShell:"
	@echo "       python mpi\\scripts\\plot_mpi_optimizers.py"
	@echo "       python mpi\\scripts\\plot_mpi_vs_seq.py"

# =============================================================================
# BENCHMARK BATCH MPI (WSL)
# =============================================================================

benchmark_batch: mpi
	@echo "=== Benchmark Batch MPI ==="
	@mkdir -p mpi/output
	@mkdir -p inputs/batch
	bash mpi/scripts/benchmark_batch.sh
	@echo ""
	@echo "[INFO] Per grafici, esegui da PowerShell:"
	@echo "       python mpi\\scripts\\plot_batch_results.py"

# =============================================================================
# PULIZIA
# =============================================================================

clean:
	rm -rf $(BUILD_DIR)
	@echo "[OK] Directory build/ rimossa"

clean_results:
	rm -f sequential/output/*.csv
	rm -f sequential/plots/*.png
	rm -f openmp/output/*.csv
	rm -f openmp/plots/*.png
	rm -f mpi/output/*.csv
	rm -f mpi/plots/*.png
	@echo "[OK] Risultati rimossi"

clean_inputs:
	rm -f $(INPUT_DIR)/*.txt
	rm -f inputs/batch/*.txt
	rm -f inputs/batch/*.json
	@echo "[OK] Input rimossi"

clean_all: clean clean_inputs clean_results
	@echo "[OK] Pulizia completa"
