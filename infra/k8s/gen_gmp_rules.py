"""Genera infra/k8s/30-gmp-rules.yaml (Rules de Managed Service for Prometheus) desde observability/prometheus/rules."""
from pathlib import Path
import yaml

root = Path(__file__).resolve().parents[2]
docs = []
for f in ["recording.yml", "aiops-alerts.yml", "security-alerts.yml"]:
    groups = yaml.safe_load((root / "observability/prometheus/rules" / f).read_text())["groups"]
    for g in groups:
        g["interval"] = "30s"
    docs.append({"apiVersion": "monitoring.googleapis.com/v1", "kind": "Rules",
                 "metadata": {"name": f.replace(".yml", ""), "namespace": "lab"}, "spec": {"groups": groups}})
out = root / "infra/k8s/30-gmp-rules.yaml"
out.write_text("# Generado por gen_gmp_rules.py — mismas reglas del sandbox evaluadas por GMP\n" +
               "---\n".join(yaml.safe_dump(d, sort_keys=False, allow_unicode=True) for d in docs))
print("ok", out)
