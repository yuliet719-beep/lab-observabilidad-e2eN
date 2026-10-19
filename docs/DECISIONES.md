# Decisiones técnicas (ADR resumidos)

| # | Decisión | Motivo |
|---|---|---|
| D1 | Sandbox Docker Compose que emula GCP y AWS; IaC Terraform validado y no aplicado | Sin cuentas en la nube; la consigna exige caos solo en sandbox. Las redes `gcp`/`aws` y los atributos `cloud.provider` mantienen la semántica multi-nube. |
| D2 | AWS: ECS Service Connect en lugar de App Mesh | App Mesh llegó a fin de soporte el 30-sep-2026; Service Connect es el reemplazo recomendado por AWS para ECS. |
| D3 | AWS: CloudWatch Anomaly Detection en lugar de DevOps Guru | DevOps Guru no admite clientes nuevos desde el 29-oct-2026 (fin de soporte 30-sep-2027); AWS recomienda CloudWatch. |
| D4 | Regla de correlación con piso de 0,5 % en la banda | Con errores de base ≈ 0, σ ≈ 0 y cualquier 5xx aislado superaría "baseline + 2σ". El piso equivale al presupuesto del SLO de disponibilidad (99,5 %). |
| D5 | SLO de latencia p99 < 300 ms (99 % de requests < 300 ms) | En el sandbox de 2 vCPU el p99 de base ronda 150–250 ms. 300 ms deja margen para no paginar por la variabilidad normal y aun así detectar +200 ms. |
| D6 | Flow logs a partir de conntrack (no captura de paquetes) | Un primer prototipo con AF_PACKET en Python añadía ~300 ms de latencia de cola. conntrack entrega el mismo agregado (5-tupla, bytes, paquetes, estado) sin tocar el datapath. |
| D7 | Spans del sidecar atribuidos al servicio (como istio-proxy) | Hace que el servicegraph muestre aristas `service-a→service-b` y no `service-a→mesh-…`. |
| D8 | FastAPI 0.115 fijada | FastAPI 0.146 trae telemetría OTel propia que, combinada con la instrumentación oficial, duplicaba el trabajo por request y elevaba el p99. |
| D9 | Prioridad de CPU: apps > plano de observabilidad (cpus/cpu_shares) | Igual que *requests/limits* en producción: la observabilidad no debe degradar el servicio que observa. Jaeger en memoria sin límite llegó a consumir 1 vCPU. |
| D10 | E2 con fallas de BD reales (statement_timeout) en vez de 503 sintéticos | Produce spans de BD con error (convenciones DB) y latencia realista, lo que ejercita la regla errores + latencia. La variante mesh (abort 10 %) queda en `infra/k8s/40-chaos.yaml`. |
