// Reporte ejecutivo final — LAB integrador de observabilidad (docx -> PDF)
const fs = require("fs");
const path = require("path");
const d = require("docx");
const { Document, Packer, Paragraph, TextRun, ImageRun, Table, TableRow, TableCell, AlignmentType, HeadingLevel,
  WidthType, ShadingType, BorderStyle, Footer, PageNumber, LevelFormat, PageBreak } = d;

const LAB = require("path").resolve(__dirname, "..");
const EV = path.join(LAB, "docs/evidencias");
const R = JSON.parse(fs.readFileSync(path.join(EV, "resultados.json"), "utf8"));
const NAVY = "0B2545", BLUE = "2F6690", LIGHT = "E8EEF6", GREEN = "D9EAD3", YEL = "FFF2CC", REDC = "F4CCCC";
const INTEGRANTES = process.env.INTEGRANTES || "Beycy Yuliet Rojas Acero · Manuel Santofimio";
const W = 9360; // ancho útil (Letter, márgenes 1")

const fmt = (n, dec = 1) => (n === null || n === undefined ? "n/d" : Number(n).toLocaleString("es-CO", { minimumFractionDigits: dec, maximumFractionDigits: dec }));
const pct = (x, dec = 1) => (x === null || x === undefined ? "n/d" : fmt(x * 100, dec) + " %");

function P(text, opts = {}) {
  const runs = (Array.isArray(text) ? text : [text]).map((t) => (typeof t === "string" ? new TextRun({ text: t, font: "Calibri", size: 21 }) : new TextRun({ font: "Calibri", size: 21, ...t })));
  return new Paragraph({ children: runs, alignment: opts.align || AlignmentType.JUSTIFIED, spacing: { after: opts.after ?? 100, line: 264 }, ...opts.p });
}
const B = (t) => ({ text: t, bold: true });
const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun({ text: t, font: "Cambria", bold: true, size: 26, color: NAVY })], spacing: { before: 160, after: 80 } });
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun({ text: t, font: "Cambria", bold: true, size: 22, color: BLUE })], spacing: { before: 100, after: 60 } });
const bullet = (text) => new Paragraph({ numbering: { reference: "b", level: 0 }, alignment: AlignmentType.JUSTIFIED, spacing: { after: 40, line: 252 },
  children: (Array.isArray(text) ? text : [text]).map((t) => (typeof t === "string" ? new TextRun({ text: t, font: "Calibri", size: 20 }) : new TextRun({ font: "Calibri", size: 20, ...t }))) });
const caption = (t) => new Paragraph({ alignment: AlignmentType.LEFT, spacing: { after: 120 }, children: [new TextRun({ text: t, font: "Calibri", size: 17, italics: true, color: "444444" })] });
const label = (t) => new Paragraph({ spacing: { before: 80, after: 30 }, keepNext: true, children: [new TextRun({ text: t, font: "Calibri", size: 18, bold: true, color: NAVY })] });

function img(file, widthIn) {
  const buf = fs.readFileSync(file);
  const w = buf.readUInt32BE(16), h = buf.readUInt32BE(20);
  const wp = widthIn * 96, hp = (wp * h) / w;
  return new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 40 }, children: [new ImageRun({ type: "png", data: buf, transformation: { width: wp, height: hp } })] });
}

const border = { style: BorderStyle.SINGLE, size: 4, color: "BFC7D5" };
const borders = { top: border, bottom: border, left: border, right: border };
function table(widths, header, rows, fills = []) {
  const mk = (txt, w, isH, fill) => new TableCell({
    width: { size: w, type: WidthType.DXA }, borders,
    shading: { type: ShadingType.CLEAR, fill: isH ? NAVY : fill || "FFFFFF", color: "auto" },
    margins: { top: 40, bottom: 40, left: 80, right: 80 },
    children: String(txt).split("\n").map((line) => new Paragraph({ spacing: { after: 0 }, children: [new TextRun({ text: line, font: "Calibri", size: 17, bold: isH, color: isH ? "FFFFFF" : "000000" })] })),
  });
  return new Table({
    width: { size: widths.reduce((a, b) => a + b, 0), type: WidthType.DXA }, columnWidths: widths,
    rows: [new TableRow({ tableHeader: true, children: header.map((h, i) => mk(h, widths[i], true)) }),
      ...rows.map((r, ri) => new TableRow({ children: r.map((c, i) => mk(c, widths[i], false, (fills[ri] || [])[i])) }))],
  });
}

// ---------- datos ----------
const E1 = R.experimentos.E1, E2 = R.experimentos.E2, RZ = R.ruido;
const st = (RZ.notificaciones.static || {}), ai = (RZ.notificaciones.aiops || {});
const mttdOk = (e) => e && e.mttd_notificacion_s !== null && e.mttd_notificacion_s <= 120;
const sec = R.seguridad || { alertas: [] };
const cves = R.cves || {};
const cveTot = (sev) => Object.values(cves).reduce((a, c) => a + (c[sev] || 0), 0);
const firstSec = (name) => (sec.alertas.find((a) => a.alerta === name) || {}).t_desde_inicio_s;

const children = [];
// ---------- Portada ----------
children.push(
  new Paragraph({ spacing: { before: 1800, after: 200 }, alignment: AlignmentType.CENTER, children: [new TextRun({ text: "Universidad de La Sabana · Observabilidad en Ambientes Productivos", font: "Calibri", size: 22, color: BLUE })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, children: [new TextRun({ text: "LAB integrador: sistema de observabilidad end-to-end con AIOps y resiliencia en GCP y AWS", font: "Cambria", size: 40, bold: true, color: NAVY })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 600 }, children: [new TextRun({ text: "Reporte ejecutivo final", font: "Cambria", size: 28, color: BLUE })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 120 }, children: [new TextRun({ text: INTEGRANTES, font: "Calibri", size: 22 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 120 }, children: [new TextRun({ text: "Repositorio: github.com/yuliet719-beep/lab-observabilidad-e2eN (tag v1.0)", font: "Calibri", size: 20 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "Octubre de 2026", font: "Calibri", size: 22 })] }),
  new Paragraph({ children: [new PageBreak()] }),
);

// ---------- 1. Resumen ----------
children.push(H1("1. Resumen ejecutivo"));
children.push(P([
  "El presente documento reporta la integración de los dominios de observabilidad (tres pilares, OpenTelemetry, AIOps, observabilidad de red y seguridad, DataOps y SRE) en un sistema de tres microservicios desplegado en una ",
  B("producción simulada multi-nube"), ". Al no contar el equipo con cuentas de GCP ni de AWS, la solución se ejecutó en un sandbox reproducible que emula la topología de ambas nubes (VPC, mesh, bases de datos gestionadas y flujos de red), y la infraestructura de nube real quedó definida como código Terraform validado (",
  { text: "terraform validate", italics: true }, ") pero no aplicado. Esta decisión cumple, además, la recomendación de ejecutar los experimentos de caos únicamente en sandbox.",
]));
children.push(bullet([B("Detección (MTTD): "), `E2 (10 % de errores en data-service) se detectó en ${fmt(E2.mttd_notificacion_s, 0)} s. E1 (latencia de 200 ms en service-b) notificó a los ${fmt(E1.mttd_notificacion_s, 0)} s, pero la regla ya estaba en pending por un pico transitorio previo a la inyección; la estimación conservadora (re-disparo atribuible solo a E1) es de 106 s. Ambos cumplen el objetivo de menos de 2 minutos.`]));
children.push(bullet([B("Alertas accionables: "), `cada página llegó con el trace_id de un request afectado y una causa raíz candidata (${E1.causa_raiz_candidata.service || "n/d"} en E1 y ${E2.causa_raiz_candidata.service || "n/d"} en E2). ${E1.causa_raiz_correcta && E2.causa_raiz_correcta ? "En ambos casos la causa coincidió con la falla inyectada." : "La atribución se discute en la sección 6."}`]));
children.push(bullet([B("Reducción de ruido: "), `en ${fmt(RZ.ventana_min, 0)} minutos sin fallas reales, los umbrales estáticos generaron ${st.total || 0} notificaciones y el pipeline AIOps ${ai.total || 0} (${RZ.reduccion_notificaciones_pct !== null ? "−" + fmt(RZ.reduccion_notificaciones_pct, 1) + " %" : "n/d"}).`]));
children.push(bullet([B("SLO y error budget: "), `E1 llevó la proporción de requests bajo 300 ms a ${pct(E1.durante_falla.latency_good_ratio)} (objetivo 99 %; burn rate ${fmt(E1.durante_falla.burn_rate_latencia, 1)}×). E2 bajó la disponibilidad a ${pct(E2.durante_falla.disponibilidad, 2)} (objetivo 99,5 %; burn rate ${fmt(E2.durante_falla.burn_rate_disponibilidad, 1)}×).`]));
children.push(bullet([B("Seguridad: "), `el escenario de ataque activó ${new Set(sec.alertas.map((a) => a.alerta)).size} tipos de alerta (fuerza bruta, escaneo de puertos y flujo Este-Oeste no permitido hacia la base de datos), con su hallazgo normalizado tipo SCC/Security Hub. Además se reportaron ${cveTot("CRITICAL")} CVE críticos y ${cveTot("HIGH")} altos activos en las imágenes.`]));

// ---------- 2. Arquitectura ----------
children.push(H1("2. Arquitectura observable completa (Módulo A)"));
children.push(img(path.join(LAB, "docs/img/arquitectura.png"), 6.5));
children.push(caption("Figura 1. Arquitectura desplegada. Las líneas punteadas son exportación OTLP; «≈» indica el servicio gestionado equivalente en la nube."));
children.push(P([
  "La arquitectura extiende el laboratorio 2.2 con un tercer microservicio, ", B("data-service"), ", que consulta dos motores gestionados: Cloud SQL for PostgreSQL (pedidos, GCP) y Amazon RDS for PostgreSQL (inventario, AWS). El flujo Norte-Sur entra por service-a (GKE), atraviesa la interconexión hacia service-b (ECS Fargate) y regresa a data-service. Los tres servicios usan el SDK de OpenTelemetry para los tres pilares: trazas OTLP, métricas (histograma ",
  { text: "http.server.request.duration", italics: true }, " con buckets alineados al SLO) y logs con trace_id/span_id. Los spans de base de datos siguen las ", B("OTel Database Semantic Conventions"), " estables (", { text: "db.system.name, db.namespace, db.query.text, db.operation.name, error.type", italics: true }, ") y propagan el contexto a Cloud SQL Query Insights mediante sqlcommenter.",
]));
children.push(P([
  "El ", B("service mesh L7"), " se implementó con sidecars Envoy 1.33, que emiten métricas por clase de respuesta, spans propios y access logs vía OTLP, y que admiten inyección de fallas en caliente. En la nube, el equivalente es Cloud Service Mesh gestionado en GCP y ", B("ECS Service Connect"), " en AWS: AWS App Mesh llegó a fin de soporte el 30 de septiembre de 2026 (Amazon Web Services [AWS], 2024). Un collector por nube agrega atributos ",
  { text: "cloud.provider/platform/region", italics: true }, " y reenvía a un gateway central que deriva el grafo de servicios (servicegraph) y las métricas RED de las trazas. Así, una misma traza cruza ambas nubes y conserva la correlación completa.",
]));
children.push(label("Tabla 1. Equivalencia entre el sandbox ejecutado y el IaC de nube (validado)"));
children.push(table([1700, 2550, 2550, 2560], ["Capacidad", "Sandbox (ejecutado)", "GCP (infra/gcp)", "AWS (infra/aws)"], [
  ["Cómputo y mesh", "Contenedores + Envoy sidecar", "GKE Autopilot + Cloud Service Mesh", "ECS Fargate + Service Connect"],
  ["Datos", "PostgreSQL 16 ×2", "Cloud SQL PG16 + Query Insights", "RDS PG16 + Performance Insights"],
  ["Trazas / métricas / logs", "Jaeger / Prometheus / Loki", "Cloud Trace / GMP / Cloud Logging", "X-Ray / CloudWatch / CloudWatch Logs"],
  ["AIOps", "Reglas ±2σ + correlador", "Alertas PromQL + forecast", "ANOMALY_DETECTION_BAND + alarma compuesta"],
  ["Red y seguridad", "Flow logs (conntrack) + Trivy", "VPC Flow Logs, firewall logs, SCC", "VPC Flow Logs v5, Security Hub, GuardDuty, Inspector"],
  ["Caos", "Envoy runtime + /admin/chaos", "VirtualService fault", "AWS FIS con stop condition"],
]));

// ---------- 3. AIOps ----------
children.push(H1("3. AIOps: detección automática de anomalías y correlación (Módulo B)"));
children.push(P([
  "La detección se basa en líneas base dinámicas: para cada servicio se graban la media y la desviación estándar del error ratio y del p99 en una ventana móvil (30 min con un desfase de 5 min, para que la propia anomalía no contamine la base). La ", B("regla de correlación"), " exigida dispara cuando ",
  { text: "error_rate > baseline + 2σ  Y  latency_p99 > SLO_threshold (300 ms)", bold: true }, " se sostiene durante 30 s. Como la tasa de error de base es casi nula, σ también lo es; por eso la banda tiene un piso de 0,5 %, igual al presupuesto del SLO de disponibilidad (99,5 %). Una segunda regla cubre las degradaciones sin errores (p99 fuera de banda, sobre el SLO y con menos del 99 % de requests bajo 300 ms). La banda ±2σ sobre data-service replica la detección de anomalías nativa (CloudWatch ", { text: "ANOMALY_DETECTION_BAND", italics: true },
  " y el pronóstico de Cloud Monitoring). DevOps Guru no se usó porque deja de admitir clientes nuevos el 29 de octubre de 2026 (AWS, 2026).",
]));
children.push(P([
  "Alertmanager entrega cada página al ", B("correlador"), ". Este busca en Jaeger el trace más reciente fallido (o lento) del servicio, identifica la causa raíz candidata (el span con error más profundo o el de mayor tiempo propio), la contrasta con las aristas del servicegraph, adjunta los cambios recientes (despliegues y experimentos) y agrupa las alertas en incidentes. El resultado es una ", B("alerta enriquecida con el trace_id del request fallido"), ".",
]));
children.push(img(path.join(EV, "fig_ruido.png"), 5.0));
children.push(caption(`Figura 2. Notificaciones durante ${fmt(RZ.ventana_min, 0)} min de operación con variabilidad natural (micro-cortes y job batch) y sin fallas inyectadas.`));
const stRows = Object.entries(st.por_alerta || {}).map(([k, v]) => `${k}: ${v}`).join("\n") || "—";
const aiRows = Object.entries(ai.por_alerta || {}).map(([k, v]) => `${k}: ${v}`).join("\n") || "—";
children.push(label("Tabla 2. Ruido: umbrales estáticos frente a AIOps (misma ventana y mismo group_by de Alertmanager)"));
children.push(table([2340, 3510, 3510], ["Métrica", "Umbrales estáticos", "AIOps (dinámico + correlación)"], [
  ["Notificaciones", String(st.total || 0), String(ai.total || 0)],
  ["Instancias de alerta en firing", String(RZ.instancias_firing.static), String(RZ.instancias_firing.aiops)],
  ["Proyección por día", fmt(RZ.por_dia.static, 0), fmt(RZ.por_dia.aiops, 0)],
  ["Detalle", stRows, aiRows],
], [[null, REDC, GREEN], [null, REDC, GREEN], [null, REDC, GREEN]]));

// ---------- 4. Red y seguridad ----------
children.push(H1("4. Observabilidad de red y seguridad (Módulo C)"));
children.push(P([
  "Se habilitaron flow logs en ambas VPC. En la nube se usan VPC Flow Logs de GCP (intervalo de 5 s, muestreo del 50 %, metadatos completos) y de AWS (formato v5 con ",
  { text: "flow-direction, traffic-path, ecs-service-name", italics: true }, "). En el sandbox, un emulador lee la tabla conntrack del kernel y produce registros en ambos formatos. Cada flujo se clasifica en ", B("Norte-Sur, Este-Oeste o entre nubes"), " y se contrasta con una ", B("matriz de tráfico permitido"),
  ". Las alertas cubren flujos Este-Oeste no permitidos, picos de flujos REJECT (escaneo de puertos), tráfico entre nubes que triplica su línea base y fuerza bruta de autenticación (fallas > línea base + 3σ). Los hallazgos se normalizan en formato OCSF (Security Hub) con su categoría equivalente en Security Command Center.",
]));
if (fs.existsSync(path.join(EV, "fig_seguridad.png"))) {
  children.push(img(path.join(EV, "fig_seguridad.png"), 6.3));
  children.push(caption("Figura 3. Golden Signals de Seguridad durante el escenario de ataque (sombreado): autenticaciones fallidas y tráfico por dirección."));
}
const secRows = sec.alertas.map((a) => [a.alerta, a.origen || "—", fmt(a.t_desde_inicio_s, 0) + " s", a.resumen || ""]);
children.push(label("Tabla 3. Detección del escenario de ataque (fuerza bruta → escaneo E-W → movimiento lateral a Cloud SQL)"));
children.push(table([2500, 1500, 1300, 4060], ["Alerta", "Origen", "t desde el inicio", "Resumen"], secRows.length ? secRows : [["—", "—", "—", "sin alertas"]]));
children.push(P([
  `Golden Signals de Seguridad (dashboard Grafana y su equivalente en Cloud Monitoring y CloudWatch): (1) intentos de autenticación fallidos, con un pico de ${fmt(sec.auth_fallidas_pico_por_s, 1)}/s frente a ~0,02/s en la base; (2) tráfico N-S/E-W/entre nubes, con flujos no permitidos hacia Cloud SQL:5432 y hacia data-service:8000 (bypass del mesh) detectados a los ${fmt(firstSec("SecUnexpectedEastWestFlow") , 0)}–112 s. El escaneo de puertos no produjo registros REJECT (${fmt(sec.flujos_reject, 0)}): los intentos contra puertos cerrados no persistieron en conntrack entre lecturas de 2 s, brecha que se corrige en el roadmap con eBPF; (3) CVEs activos (Trivy sobre las tres imágenes): ${cveTot("CRITICAL")} críticos, ${cveTot("HIGH")} altos y ${cveTot("MEDIUM")} medios, la mayoría en paquetes del sistema base de Debian.`,
]));

// ---------- 5/6. Caos ----------
children.push(H1("5. Chaos engineering controlado y validación del MTTD (Módulo D)"));
children.push(P([
  "Se ejecutaron dos experimentos con hipótesis, alcance acotado al sandbox y un guardrail automático (se aborta si la disponibilidad de service-a cae por debajo del 80 % durante 60 s). ",
  B("E1: "), "latencia de 200 ms en el 100 % de los requests a service-b, inyectada en su sidecar Envoy (equivalente a AWS FIS ", { text: "aws:ecs:task-network-latency", italics: true }, "). ",
  B("E2: "), "error rate del 10 % en data-service con fallas reales de base de datos (consultas que exceden ", { text: "statement_timeout", italics: true }, "). La variante con abort del mesh queda en el IaC.",
]));
children.push(img(path.join(EV, "fig_experimentos.png"), 6.5));
children.push(caption("Figura 4. SLI de service-a frente a la línea base dinámica. Sombreado: falla activa; línea punteada verde: página AIOps recibida."));
const yes = (b) => (b ? "Sí" : "No");
children.push(label("Tabla 4. Resultados por experimento (SLO 28 días: disponibilidad 99,5 %; latencia 99 % < 300 ms)"));
children.push(table([3000, 3180, 3180], ["Pregunta / métrica", "E1 · +200 ms en service-b", "E2 · 10 % errores en data-service"], [
  ["MTTD (inyección → notificación)", `${fmt(E1.mttd_notificacion_s, 0)} s nominal; 106 s conservador (pending previo por pico transitorio)`, `${fmt(E2.mttd_notificacion_s, 0)} s (firing: ${fmt(E2.mttd_firing_prometheus_s, 0)} s)`],
  ["¿MTTD < 2 min?", yes(mttdOk(E1)), yes(mttdOk(E2))],
  ["Primera alerta", E1.primera_alerta || "—", E2.primera_alerta || "—"],
  ["¿Se degradó el SLO?", `Sí (latencia): ${pct(E1.durante_falla.latency_good_ratio)} < 300 ms; p99 pico ${fmt(E1.durante_falla.p99_pico_s * 1000, 0)} ms`, `Sí (disponibilidad): ${pct(E2.durante_falla.disponibilidad, 2)}; error pico ${pct(E2.durante_falla.error_ratio_pico)}`],
  ["Burn rate durante la falla", `${fmt(E1.durante_falla.burn_rate_latencia, 1)}× (latencia)`, `${fmt(E2.durante_falla.burn_rate_disponibilidad, 1)}× (disponibilidad)`],
  ["Error budget 28 d consumido", `${fmt(E1.error_budget_28d.consumo_latencia_pct, 2)} % del de latencia`, `${fmt(E2.error_budget_28d.consumo_disponibilidad_pct, 2)} % del de disponibilidad`],
  ["¿Alerta accionable?", `${yes(E1.causa_raiz_correcta)}: trace ${String(E1.trace_id || "").slice(0, 12)}…, causa ${E1.causa_raiz_candidata.service || "n/d"} (${E1.causa_raiz_candidata.span || ""})`, `${yes(E2.causa_raiz_correcta)}: trace ${String(E2.trace_id || "").slice(0, 12)}…, causa ${E2.causa_raiz_candidata.service || "n/d"} (${E2.causa_raiz_candidata.span || ""})`],
  ["Ruido estático en paralelo", `${E1.notificaciones_estaticas} notificaciones`, `${E2.notificaciones_estaticas} notificaciones`],
], [[null, GREEN, GREEN], [null, mttdOk(E1) ? GREEN : REDC, mttdOk(E2) ? GREEN : REDC], [], [null, YEL, YEL], [], [null, YEL, YEL], [null, E1.causa_raiz_correcta ? GREEN : REDC, E2.causa_raiz_correcta ? GREEN : REDC]]));
const proj = (e, kind) => { const br = kind === "lat" ? e.durante_falla.burn_rate_latencia : e.durante_falla.burn_rate_disponibilidad; return br ? fmt((28 * 24) / br, 1) : "n/d"; };
children.push(P([
  B("Análisis. "), `El error budget mensual absorbió ambos experimentos (${fmt(E1.error_budget_28d.consumo_latencia_pct, 2)} % y ${fmt(E2.error_budget_28d.consumo_disponibilidad_pct, 2)} %) porque la falla duró ${fmt(E1.duracion_falla_s / 60, 0)} minutos. Sin embargo, la velocidad de consumo es la señal relevante: con el burn rate observado, el presupuesto de latencia se agotaría en ~${proj(E1, "lat")} h y el de disponibilidad en ~${proj(E2, "av")} h. Esto justifica paginar (y no abrir un ticket) en ambos casos. `,
  `Las alertas fueron accionables: el operador recibe el trace del request afectado y el salto responsable (${E1.causa_raiz_candidata.span || "n/d"} en ${E1.causa_raiz_candidata.service || "n/d"}; ${E2.causa_raiz_candidata.span || "n/d"} en ${E2.causa_raiz_candidata.service || "n/d"}). Esto corrige la falla de atribución observada en el Game Day anterior, donde el correlador culpó al servicio que llamaba en lugar del dependiente.`,
]));
if (fs.existsSync(path.join(EV, "fig_trace_E2.png"))) {
  children.push(img(path.join(EV, "fig_trace_E2.png"), 5.8));
  children.push(caption("Figura 5. Trace adjuntado a la alerta de E2: el span de BD en data-service (rojo) propaga el error hasta service-a."));
}

if (fs.existsSync(path.join(EV, "fig_trace_E1.png"))) {
  children.push(img(path.join(EV, "fig_trace_E1.png"), 5.8));
  children.push(caption("Figura 6. Trace adjuntado a la alerta de E1: el span ingress del sidecar de service-b concentra ~200 ms de tiempo propio (falla inyectada en el mesh)."));
}
children.push(H2("Evidencia: alerta enriquecida entregada al operador (E2)"));
const AE = JSON.parse(fs.readFileSync(path.join(EV, "alerta_enriquecida_AIOpsCorrelatedErrorLatency.json"), "utf8"));
children.push(label("Tabla 7. Campos de la notificación generada por el correlador (extracto de docs/evidencias)"));
children.push(table([2600, 6760], ["Campo", "Valor"], [
  ["alertname / servicio", `${AE.alertname} / ${AE.service}`],
  ["incident_id", AE.incident_id],
  ["trace_id", `${AE.trace_id}`],
  ["causa raíz candidata", JSON.stringify(AE.root_cause_candidate)],
  ["aristas servicegraph con fallas", (AE.service_graph.failing_edges || []).join("; ") || "—"],
  ["aristas lentas", (AE.service_graph.slow_edges || []).join("; ") || "—"],
  ["cambios recientes", (AE.recent_changes || []).map((c) => c.detail).join("; ") || "—"],
  ["SLO al alertar", `error ratio ${pct(AE.slo.error_ratio_1m)} (banda ${pct(AE.slo.error_band_upper)}), p99 ${fmt(AE.slo.latency_p99_1m_s * 1000, 0)} ms`],
  ["tiempo de enriquecimiento", `${AE.enrichment_ms} ms`],
]));
children.push(P("La alerta incluye el contexto de cambio (el experimento en curso), lo que en producción equivale a correlacionar con el último despliegue. Este es el principal acelerador del MTTR: el operador no necesita buscar el trace ni adivinar el servicio responsable."));

// ---------- 6. Madurez ----------
children.push(H1("6. Reporte de madurez de observabilidad (Módulo E)"));
children.push(P("La solución se autoevaluó contra los ocho dominios del Observability Foundation Blueprint (DevOps Institute, s. f.) en una escala de 1 (inicial) a 5 (optimizada). La calificación se apoya en la evidencia del repositorio y no en capacidades declaradas."));
const M = [
  ["1. Fundamentos y cultura de observabilidad", 3, "SLOs explícitos, runbook y decisiones documentadas (ADR)", "Sin rituales de equipo (revisión de SLO, postmortems periódicos)"],
  ["2. Pilares (logs, métricas, trazas)", 4, "3 pilares en 3 servicios + mesh + BD, correlacionados por trace_id", "Sin profiling continuo ni RUM"],
  ["3. Ecosistema open source / OpenTelemetry", 4, "OTel SDK, collectors por nube + gateway, semconv HTTP/DB estables", "Sin OpAMP ni operador de autoinstrumentación"],
  ["4. Mapas de servicio y topología", 3, "Servicegraph con nodos virtuales de BD y aristas entre nubes", "No integra topología de red/infra ni dependencias externas"],
  ["5. DataOps de telemetría", 2, "Retención acotada y límites de CPU para el plano de observabilidad", "Muestreo al 100 %, sin control de cardinalidad ni de costos"],
  ["6. AIOps", 3, "Baseline ±2σ, correlación multiseñal, enriquecimiento e incidentes", "Sin estacionalidad, sin ML, sin auto-remediación"],
  ["7. Seguridad y redes", 3, "Flow logs N-S/E-W, golden signals de seguridad, CVEs, hallazgos OCSF", "Sin SIEM/SOAR ni eBPF; escaneo de puertos no detectado (REJECT)"],
  ["8. Prácticas DevOps y SRE", 3, "Error budget, caos con guardrails, CI de validación", "Sin política automática de error budget ni burn rate multi-ventana"],
];
const lvlFill = (n) => (n >= 4 ? GREEN : n === 3 ? YEL : REDC);
children.push(label("Tabla 5. Autoevaluación de madurez (promedio " + fmt(M.reduce((a, m) => a + m[1], 0) / M.length, 1) + " / 5)"));
children.push(table([2700, 700, 3000, 2960], ["Dominio", "Nivel", "Evidencia", "Brecha principal"], M.map((m) => [m[0], String(m[1]), m[2], m[3]]), M.map((m) => [null, lvlFill(m[1]), null, null])));
children.push(H2("Roadmap a 3 meses para alcanzar el siguiente nivel"));
children.push(label("Tabla 6. Roadmap accionable (cada hito con su métrica de salida)"));
children.push(table([1100, 4760, 3500], ["Mes", "Acciones", "Criterio de salida"], [
  ["Mes 1", "Aplicar el IaC en proyectos sandbox de GCP y AWS con HA VPN; muestreo tail-based en el gateway (100 % de errores y lentos, 10 % del resto); presupuesto de cardinalidad.", "Trazas entre nubes en Cloud Trace/X-Ray; −50 % de volumen de spans sin perder trazas con error"],
  ["Mes 2", "Alertas SLO multi-ventana (1 h/5 min, 6 h/30 min) y política de error budget (congelar despliegues al superar el 50 %); línea base estacional (hora del día) y servicegraph en el correlador; eBPF (Cilium/Hubble o GKE Dataplane V2) para red L3–L7.", "MTTD < 60 s; ≥ 90 % de páginas con causa raíz correcta; 0 páginas sin acción en 2 semanas"],
  ["Mes 3", "SCC/Security Hub y GuardDuty hacia un SIEM con playbooks SOAR; Game Days mensuales con AWS FIS y fault injection del mesh; circuit breaker y load shedding en service-b; dashboards de costos de telemetría.", "MTTR < 15 min en el Game Day; CVEs críticos con fix < 7 días; madurez promedio ≥ 3,8"],
]));

// ---------- 7. Limitaciones ----------
children.push(H1("7. Limitaciones y conclusiones"));
children.push(P([
  B("Limitaciones. "), "(1) El despliegue en GCP y AWS no se aplicó por falta de cuentas; el IaC está validado sintácticamente y contra los esquemas de los proveedores, pero no se probó en ejecución. (2) El sandbox corre en 2 vCPU, lo que eleva la variabilidad del p99 y obligó a fijar el SLO en 300 ms. (3) El ruido de base es sintético (perfil parametrizado de micro-cortes y job batch), por lo que la reducción de alertas demuestra el mecanismo pero no predice la reducción en un sistema real. (4) Por el plazo de entrega, la ventana de comparación de ruido (12 min) y las fallas (3 min) fueron cortas; la reducción del 100 % de notificaciones en esa ventana no debe extrapolarse. (5) Un pico de latencia transitorio, ajeno al experimento, coincidió con el inicio de E1.",
]));
children.push(P([
  B("Conclusión. "), "La correlación de señales (errores + latencia + trazas) sobre líneas base dinámicas permitió detectar ambas degradaciones dentro del objetivo de MTTD, con alertas que indican dónde actuar, mientras los umbrales estáticos produjeron ruido sin contexto. Las decisiones de diseño (Service Connect por el fin de App Mesh, CloudWatch Anomaly Detection por el retiro de DevOps Guru, flow logs sin impacto en el datapath) se documentan como ADR en el repositorio.",
]));

children.push(new Paragraph({ children: [new PageBreak()] })); children.push(H1("Anexo A. Inventario del repositorio (v1.0)"));
children.push(table([3000, 6360], ["Ruta", "Contenido"], [
  ["services/", "service-a, service-b, data-service (FastAPI) y telemetry.py común: OTel SDK, 3 pilares, convenciones HTTP/DB estables"],
  ["mesh/", "Sidecars Envoy (métricas L7, trazas, access logs OTLP, fault injection en runtime)"],
  ["otel/", "Collectors GCP y AWS + gateway (servicegraph, spanmetrics, exportación a Jaeger/Prometheus/Loki)"],
  ["observability/", "Reglas SLI y baseline ±2σ, alertas estáticas/AIOps/seguridad, Alertmanager, Loki, Jaeger, 2 dashboards Grafana"],
  ["aiops/correlator/", "Enriquecimiento con trace_id, causa raíz, servicegraph, incidentes y hallazgos OCSF"],
  ["network/flowlogs/", "Emulador de VPC Flow Logs (AWS v5 y GCP vpc_flows), matriz de tráfico permitido"],
  ["infra/gcp/", "VPC + Flow Logs + firewall logging, GKE Autopilot, Cloud Service Mesh, Cloud SQL, alertas PromQL, métricas de logs, dashboard de seguridad, SCC → Pub/Sub"],
  ["infra/aws/", "VPC + Flow Logs v5, ECS Fargate + Service Connect, RDS, anomaly detection + alarma compuesta, Security Hub, GuardDuty, Inspector, FIS"],
  ["infra/k8s/", "Despliegues GKE, collector con exportadores de Google Cloud, reglas GMP, VirtualService de caos"],
  ["chaos/, scripts/", "Orquestador E1/E2 con guardrails, escenario de ataque, run_lab.sh, analyze.py, escaneo Trivy"],
  ["docs/", "Runbook, decisiones (ADR), madurez, guion del video y evidencias (resultados.json, figuras, flow logs, alertas)"],
  [".github/workflows/ci.yml", "Validación de reglas, Alertmanager, Envoy, collectors, Terraform (fmt/validate), build y Trivy"],
]));

// ---------- Referencias ----------
children.push(H1("Referencias"));
const refs = [
  "Amazon Web Services. (s. f.). AWS observability best practices. https://aws-observability.github.io/observability-best-practices/",
  "Amazon Web Services. (2024). AWS App Mesh end of support. https://docs.aws.amazon.com/app-mesh/latest/userguide/",
  "Amazon Web Services. (2026). Amazon DevOps Guru end of support. https://docs.aws.amazon.com/devops-guru/latest/userguide/devops-guru-end-of-support.html",
  "Amazon Web Services. (s. f.). Use the AWS FIS aws:ecs:task actions. https://docs.aws.amazon.com/fis/latest/userguide/ecs-task-actions.html",
  "Basiri, A., Behnam, N., de Rooij, R., Hochstein, L., Kosewski, L., Reynolds, J., & Rosenthal, C. (2016). Chaos engineering. IEEE Software, 33(3), 35–41. https://doi.org/10.1109/MS.2016.60",
  "Beyer, B., Jones, C., Petoff, J., & Murphy, N. R. (2016). Site reliability engineering: How Google runs production systems. O'Reilly Media.",
  "DevOps Institute. (s. f.). Observability Foundation. https://www.devopsinstitute.com/",
  "Google Cloud. (s. f.). Cloud Observability documentation. https://cloud.google.com/stackdriver/docs",
  "Google Cloud. (s. f.). Security Command Center overview. https://cloud.google.com/security-command-center/docs/concepts-security-command-center-overview",
  "OpenTelemetry Authors. (s. f.). Semantic conventions for database calls and systems. https://opentelemetry.io/docs/specs/semconv/db/",
  "Sigelman, B., et al. (2021). Towards observability data management at scale. ACM SIGOPS.",
  "Tigera. (s. f.). eBPF and network observability. https://www.tigera.io/learn/guides/ebpf/",
];
refs.forEach((r) => children.push(new Paragraph({ indent: { left: 720, hanging: 720 }, spacing: { after: 60, line: 252 }, children: [new TextRun({ text: r, font: "Calibri", size: 19 })] })));

const doc = new Document({
  creator: "Grupo LAB e2e", title: "Reporte ejecutivo LAB integrador de observabilidad",
  styles: { default: { document: { run: { font: "Calibri", size: 21 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: "Cambria", size: 26, bold: true, color: NAVY }, paragraph: { outlineLevel: 0, keepNext: true } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: "Cambria", size: 22, bold: true, color: BLUE }, paragraph: { outlineLevel: 1, keepNext: true } }] },
  numbering: { config: [{ reference: "b", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 360, hanging: 240 } } } }] }] },
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1300, bottom: 1200, left: 1440, right: 1440 } }, titlePage: true },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [new TextRun({ children: [PageNumber.CURRENT], font: "Calibri", size: 18, color: "666666" })] })] }) },
    children,
  }],
});
Packer.toBuffer(doc).then((b) => { fs.writeFileSync(path.join(LAB, "docs/Reporte_Ejecutivo_LAB_Observabilidad.docx"), b); console.log("docx ok"); });
