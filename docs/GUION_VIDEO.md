# Guion del video de demostración (5–6 min)

Presentan: Yuliet Rojas y Manuel Santofimio. Pantallas: Grafana (http://localhost:3000), Jaeger (:16686), terminal y repositorio en GitHub.

| Min | Quién | En pantalla | Qué decir |
|---|---|---|---|
| 0:00–0:30 | Yuliet | README del repo (diagrama) | "Integramos los tres pilares, OpenTelemetry, AIOps, red y seguridad, y SRE en tres microservicios repartidos entre GCP y AWS. Sin cuentas en la nube, ejecutamos todo en un sandbox que emula ambas nubes; el Terraform de GCP y AWS está validado." |
| 0:30–1:15 | Yuliet | `services/common/telemetry.py` y `services/data-service/app.py` | "Cada servicio exporta trazas, métricas y logs por OTLP. data-service consulta Cloud SQL y RDS; sus spans de base de datos siguen las convenciones semánticas estables: `db.system.name`, `db.query.text`. Envoy actúa como sidecar del mesh, equivalente a Cloud Service Mesh y a ECS Service Connect, porque App Mesh ya no tiene soporte." |
| 1:15–2:00 | Manuel | Grafana → *Golden Signals y SLO* | "Este es el tráfico de las dos nubes. El SLO es 99,5 % de disponibilidad y p99 menor a 300 ms. Las líneas punteadas son la banda dinámica: media de 30 minutos más dos desviaciones estándar." |
| 2:00–2:45 | Manuel | `observability/prometheus/rules/aiops-alerts.yml` + figura de ruido | "La regla de correlación pide error rate sobre la línea base más 2σ **y** p99 sobre el SLO. En la misma ventana sin fallas, los umbrales estáticos enviaron X notificaciones y AIOps Y." (usar los datos de la Tabla 2) |
| 2:45–4:00 | Yuliet | Terminal: `docker compose --profile chaos run --rm -e BASELINE_MIN=0 -e NOISE_MIN=0 -e FAULT_MIN=3 -e RECOVERY_MIN=2 chaos-runner` → Grafana | "Inyectamos 200 ms en service-b. El p99 cruza el SLO y en menos de dos minutos llega la página. El correlador adjunta el trace_id del request lento y señala service-b como causa raíz." Abrir `GET http://localhost:9000/incidents`, copiar el trace_id y abrirlo en Jaeger. |
| 4:00–4:45 | Manuel | Jaeger: trace de E2 (span SELECT en rojo) | "En E2, el 10 % de las consultas a la base de datos excede el timeout. El span de BD en rojo explica el 502 que ve el cliente. ¿Se degradó el SLO? Sí: la disponibilidad bajó al Z % y el burn rate fue de N×; si no se mitiga, el presupuesto se agota en horas." |
| 4:45–5:30 | Yuliet | `docker compose --profile attack run --rm intruder` → Grafana *Golden Signals de Seguridad* | "Fuerza bruta, escaneo Este-Oeste y movimiento lateral hacia Cloud SQL. Los flow logs muestran los REJECT y el flujo no permitido; se generan hallazgos con formato Security Hub/SCC. También vemos los CVEs activos de las imágenes." |
| 5:30–6:00 | Manuel | Tabla de madurez del reporte | "Nos autoevaluamos con 3,1 de 5. El roadmap a 3 meses: aplicar el IaC, muestreo tail-based, alertas SLO multi-ventana y eBPF. Gracias." |

Para ensayar: `docker compose up -d`, esperar 5 minutos para que exista línea base y luego seguir el guion.
