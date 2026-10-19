#!/usr/bin/env bash
# Escaneo de CVEs de las 3 imágenes con Trivy -> data/trivy/*.json (lo consume security-scanner)
set -euo pipefail
OUT="$(cd "$(dirname "$0")/.." && pwd)/data/trivy"; mkdir -p "$OUT"
for s in service-a service-b data-service; do
  docker run --rm -v /var/run/docker.sock:/var/run/docker.sock -v "$OUT":/out ${TRIVY_EXTRA_ARGS:-} \
    aquasec/trivy:0.65.0 image --quiet --format json -o /out/$s.json lab/$s:1.0
  echo "escaneado $s"
done
