"""Exporta CVEs activos (resultados JSON de Trivy) como métricas Prometheus — Golden Signal de Seguridad.

En nube: GCP Artifact Analysis / SCC 'Vulnerability' findings y Amazon Inspector -> Security Hub.
"""
import glob
import json
import os
import time
from collections import Counter

from prometheus_client import Gauge, start_http_server

CVES = Gauge("security_cves_active", "CVEs activos por imagen y severidad", ["image", "severity", "fixable"])
SCAN_TS = Gauge("security_last_scan_timestamp_seconds", "Último escaneo", ["image"])
DIR = os.getenv("TRIVY_DIR", "/data/trivy")

start_http_server(9109)
while True:
    for f in glob.glob(f"{DIR}/*.json"):
        d = json.load(open(f))
        img = d.get("ArtifactName", os.path.basename(f))
        c = Counter()
        for r in d.get("Results", []):
            for v in r.get("Vulnerabilities") or []:
                c[(v["Severity"], "yes" if v.get("FixedVersion") else "no")] += 1
        for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "UNKNOWN"]:
            for fx in ["yes", "no"]:
                CVES.labels(img, sev, fx).set(c.get((sev, fx), 0))
        SCAN_TS.labels(img).set(os.path.getmtime(f))
    time.sleep(30)
