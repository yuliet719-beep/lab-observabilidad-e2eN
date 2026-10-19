#!/usr/bin/env bash
# Ejecuta el laboratorio completo de punta a punta (≈ 95 min) en el sandbox local.
#   1) escaneo de CVEs  2) stack limpio  3) línea base + ventana de ruido  4) E1 y E2  5) escenario de seguridad  6) análisis
# Requisitos: Docker (Compose v2), Linux/WSL2 con nf_conntrack (para los flow logs), Python 3.10+.
set -euo pipefail
cd "$(dirname "$0")/.."
export NOISE_PROFILE=on
sudo sysctl -w net.netfilter.nf_conntrack_acct=1 >/dev/null 2>&1 || echo "aviso: no se pudo activar nf_conntrack_acct (bytes de flujos en 0)"
docker compose down -v --remove-orphans >/dev/null 2>&1 || true
rm -rf data && mkdir -p data/trivy data/flowlogs
docker compose build
SKIP_SCAN=${SKIP_SCAN:-0}; [ "$SKIP_SCAN" = 1 ] || ./scripts/cve_scan.sh
docker compose up -d
T0=$(date +%s); echo "T0=$T0" | tee data/T0
docker compose --profile chaos run --rm -e T0="$T0" chaos-runner | tee data/chaos-runner.log
echo "== Escenario de seguridad (fuerza bruta, escaneo E-W, movimiento lateral)"
date +%s > data/attack_start
docker compose --profile attack run --rm intruder | tee data/intruder.log
date +%s > data/attack_end
sleep 150
python3 scripts/analyze.py
echo "Listo: evidencias en data/ y docs/evidencias/"
