# Runbook de alertas — LAB e2e

Cada página AIOps llega enriquecida por el correlador (`data/incidents.jsonl`, `GET :9000/incidents`) con:
`incident_id`, `trace_id` + enlace a Jaeger, **causa raíz candidata** (span con error más profundo o span con mayor tiempo propio), aristas del *servicegraph* con fallas o lentitud, **cambios recientes** (experimentos, despliegues) y valores del SLO en el momento de la alerta.

## <a id="correlated"></a>AIOpsCorrelatedErrorLatency
**Significa:** el error rate del servicio supera su línea base + 2σ (con un mínimo de 0,5 %, igual al presupuesto del SLO) **y** el p99 supera el SLO_threshold (300 ms) durante 30 s.
1. Abre el `trace_url` de la alerta y confirma el span en rojo (servicio y operación de la causa raíz candidata).
2. Si la causa es `data-service` y el span es de BD (`db.system.name=postgresql`), revisa Query Insights (Cloud SQL) o Performance Insights (RDS) y las conexiones activas.
3. Revisa `recent_changes`: si hay un despliegue o experimento en curso, haz rollback o detén el experimento (`/admin/chaos error_rate=0`, `runtime_modify ...percent=0`, `aws fis stop-experiment`).
4. Mitiga: reduce el `statement_timeout`, aplica *load shedding* y un *circuit breaker* en service-b (ver roadmap) y escala data-service.
5. Cierra con un postmortem *blameless* si se consumió más del 2 % del error budget mensual.

## <a id="latency"></a>AIOpsLatencyAnomalySLO
**Significa:** p99 fuera de banda **y** > 300 ms **y** < 99 % de requests bajo 300 ms (degradación sin errores).
1. En el trace, el span con mayor *self-time* indica el salto lento. Una arista `service-a→service-b` lenta con `service-b` rápido apunta al sidecar o la red (mesh, VPN entre nubes).
2. Revisa las métricas L7 del mesh (`envoy_cluster_upstream_rq_time`) y los flow logs `cross-cloud`.
3. Si coincide con una inyección de fallas, el experimento se valida; si no, escala a red.

## Seguridad
| Alerta | Primeros pasos |
|---|---|
| SecAuthBruteForce | Identifica `source.address` en los logs (`security.auth.failure`), bloquéalo en Cloud Armor/WAF y fuerza el bloqueo de cuentas tras N intentos. |
| SecUnexpectedEastWestFlow | Flujo fuera de la matriz permitida (p. ej. pod desconocido → Cloud SQL:5432). Aísla el pod/tarea, revisa SCC/GuardDuty y rota credenciales. |
| SecRejectedFlowsSpike | Escaneo de puertos: identifica el origen en los flow logs (REJECT) y la carga de trabajo comprometida. |
| SecCriticalCVEActive | Reconstruye la imagen con la versión corregida (Trivy `FixedVersion`) y vuelve a desplegar. |
