#!/bin-bash
echo "🚀 Iniciando teste de stress combinado (CPU, Memória e I/O)..."
echo "O sistema ficará sob carga pesada por 60 segundos."
echo "Um relatório 'report.sar' será gerado."

TEST_DURATION=60
TEMP_DIR="fio-test-data"
mkdir -p $TEMP_DIR

# 1. Coleta de Métricas (background)
echo "Iniciando monitoramento com 'sar'..."
sudo sar -u -r -S -b -o report.sar 1 $TEST_DURATION &
SAR_PID=$!

# 2. Stress de I/O (fio)
echo "Iniciando 'fio' (Stress de I/O)..."
fio --name=rand-write --ioengine=libaio --iodepth=64 --bs=4k \
    --direct=1 --size=500M --readwrite=randwrite --runtime=$TEST_DURATION \
    --directory=$TEMP_DIR --group_reporting &

# 3. Stress de CPU e Memória (stress-ng)
echo "Iniciando 'stress-ng' (Stress de CPU & Memória)..."
stress-ng --cpu 4 --cpu-method sqrt \
          --vm 2 --vm-bytes 512M --vm-method all \
          --timeout ${TEST_DURATION}s &

# 4. Teste de CPU (Sysbench)
echo "Iniciando 'sysbench' (Stress de CPU)..."
sysbench cpu --threads=4 --cpu-max-prime=20000 --time=$TEST_DURATION run &

echo "Aguardando $TEST_DURATION segundos para a conclusão..."
wait $SAR_PID
sleep 2
sudo pkill -f fio
sudo pkill -f stress-ng
sudo pkill -f sysbench
rm -rf $TEMP_DIR
echo "✅ Teste concluído! Relatório salvo em 'report.sar'."
