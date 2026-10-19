# Autoevaluación de madurez — Observability Foundation Blueprint (8 dominios, escala 1–5)

| Dominio | Nivel | Evidencia | Brecha |
|---|---|---|---|
| 1. Fundamentos y cultura | 3 | SLOs, runbook, ADR | Sin rituales de SLO ni postmortems periódicos |
| 2. Pilares | 4 | 3 pilares correlacionados por trace_id (apps, mesh, BD) | Sin profiling continuo ni RUM |
| 3. Open source / OpenTelemetry | 4 | SDK OTel, collectors por nube + gateway, semconv estables | Sin OpAMP ni operador de autoinstrumentación |
| 4. Mapas de servicio y topología | 3 | Servicegraph con nodos de BD y aristas entre nubes | Sin topología de red/infra |
| 5. DataOps | 2 | Retención acotada, límites de recursos | Muestreo al 100 %, sin control de cardinalidad ni de costos |
| 6. AIOps | 3 | Baseline ±2σ, correlación, enriquecimiento, incidentes | Sin estacionalidad, ML ni auto-remediación |
| 7. Seguridad y redes | 3 | Flow logs N-S/E-W, golden signals de seguridad, CVEs, hallazgos OCSF | Sin SIEM/SOAR ni eBPF |
| 8. DevOps y SRE | 3 | Error budget, caos con guardrails, CI | Sin política automática de error budget ni burn rate multi-ventana |

**Promedio: 3,1 / 5.**

## Roadmap a 3 meses
- **Mes 1.** Aplicar `infra/gcp` + `infra/aws` con HA VPN y muestreo tail-based en el gateway (100 % de errores y lentos, 10 % del resto). Salida: trazas entre nubes en Cloud Trace/X-Ray y −50 % de volumen de spans.
- **Mes 2.** Alertas SLO multi-ventana, política de error budget, línea base estacional, servicegraph en el correlador y eBPF (Hubble/Dataplane V2). Salida: MTTD < 60 s y ≥ 90 % de páginas con causa raíz correcta.
- **Mes 3.** SCC/Security Hub/GuardDuty hacia un SIEM con playbooks SOAR, Game Days mensuales con FIS y fault injection del mesh, circuit breaker y load shedding. Salida: MTTR < 15 min y madurez ≥ 3,8.
