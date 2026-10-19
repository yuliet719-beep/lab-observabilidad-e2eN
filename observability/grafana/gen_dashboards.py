"""Genera los dashboards de Grafana del LAB (JSON provisionado)."""
import json
from pathlib import Path

OUT = Path(__file__).parent / "dashboards"
PROM = {"type": "prometheus", "uid": "prom"}
LOKI = {"type": "loki", "uid": "loki"}
_id = [0]


def panel(title, targets, x, y, w=12, h=8, kind="timeseries", unit=None, ds=PROM, extra=None, desc=None):
    _id[0] += 1
    p = {
        "id": _id[0], "title": title, "type": kind, "datasource": ds,
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "targets": [{"refId": chr(65 + i), "expr": e, "legendFormat": l, "datasource": ds} for i, (e, l) in enumerate(targets)],
        "fieldConfig": {"defaults": {"unit": unit} if unit else {}, "overrides": []},
        "options": {"legend": {"displayMode": "list", "placement": "bottom"}},
    }
    if desc:
        p["description"] = desc
    if kind == "timeseries":
        p["fieldConfig"]["defaults"]["custom"] = {"lineWidth": 2, "fillOpacity": 8, "showPoints": "never"}
    if extra:
        for k, v in extra.items():
            if k == "defaults":
                p["fieldConfig"]["defaults"].update(v)
            elif k == "overrides":
                p["fieldConfig"]["overrides"] = v
            else:
                p[k] = v
    return p


def dash(uid, title, panels, refresh="10s"):
    return {"uid": uid, "title": title, "schemaVersion": 39, "time": {"from": "now-30m", "to": "now"},
            "refresh": refresh, "tags": ["lab-e2e"], "panels": panels, "timezone": "browser",
            "annotations": {"list": [{
                "name": "Caos / ruido", "datasource": PROM, "enable": True, "iconColor": "red",
                "expr": 'max by (kind) (lab_fault_active{kind="chaos_error_rate"} > 0)', "step": "15s", "titleFormat": "Caos activo",
            }]}}


def red_line(value, color="red"):
    return {"defaults": {"custom": {"thresholdsStyle": {"mode": "line"}, "lineWidth": 2, "fillOpacity": 8, "showPoints": "never"},
                         "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": None}, {"color": color, "value": value}]}}}


golden = [
    panel("Tráfico por servicio (req/s) — GCP y AWS", [("sli:requests:rate1m", "{{service_name}} ({{cloud_provider}})")], 0, 0, 8, unit="reqps"),
    panel("Error ratio vs banda dinámica (baseline + 2σ)", [
        ('sli:error_ratio:rate1m{service_name="service-a"}', "error ratio service-a"),
        ('aiops:error_ratio:band_upper{service_name="service-a"}', "banda superior"),
        ('sli:error_ratio:rate1m{service_name="data-service"}', "error ratio data-service"),
    ], 8, 0, 8, unit="percentunit"),
    panel("Latencia p99 vs SLO (300 ms) y banda", [
        ("sli:latency_p99:1m", "p99 {{service_name}}"),
        ('aiops:latency_p99:band_upper{service_name="service-a"}', "banda superior service-a"),
    ], 16, 0, 8, unit="s", extra=red_line(0.3)),
    panel("SLI disponibilidad service-a (objetivo 99,5 %)", [('1 - sli:error_ratio:rate1m{service_name="service-a"}', "disponibilidad")], 0, 8, 6, kind="stat", unit="percentunit",
          extra={"defaults": {"decimals": 2, "thresholds": {"mode": "absolute", "steps": [{"color": "red", "value": None}, {"color": "green", "value": 0.995}]}}}),
    panel("SLI latencia: % requests < 300 ms (objetivo 99 %)", [('sli:latency_good_ratio:rate1m{service_name="service-a"}', "good ratio")], 6, 8, 6, kind="stat", unit="percentunit",
          extra={"defaults": {"decimals": 2, "thresholds": {"mode": "absolute", "steps": [{"color": "red", "value": None}, {"color": "green", "value": 0.99}]}}}),
    panel("Error budget consumido (última hora, sobre presupuesto de 28 días)", [
        ('sum(sum_over_time(slo:bad_availability:increase1m{service_name="service-a"}[1h])) / (0.005 * avg(sli:requests:rate1m{service_name="service-a"}) * 2419200)', "disponibilidad"),
        ('sum(sum_over_time(slo:bad_latency:increase1m{service_name="service-a"}[1h])) / (0.01 * avg(sli:requests:rate1m{service_name="service-a"}) * 2419200)', "latencia"),
    ], 12, 8, 6, kind="stat", unit="percentunit", extra={"defaults": {"decimals": 3}}),
    panel("Alertas activas por pipeline", [('count by (pipeline) (ALERTS{alertstate="firing"})', "{{pipeline}}")], 18, 8, 6, kind="stat"),
    panel("Service mesh L7 — respuestas por clase (Envoy)", [
        ('sum by (mesh_workload, envoy_response_code_class) (rate(envoy_http_downstream_rq_xx{envoy_http_conn_manager_prefix="ingress"}[1m]))', "{{mesh_workload}} {{envoy_response_code_class}}xx")
    ], 0, 16, 12, unit="reqps"),
    panel("Grafo de servicios (servicegraph): p99 por arista", [
        ('histogram_quantile(0.99, sum by (client, server, le) (rate(traces_service_graph_request_server_seconds_bucket[1m])))', "{{client}} → {{server}}")
    ], 12, 16, 12, unit="s"),
    panel("Spans de BD (OTel DB semconv) — p99 por sistema", [
        ('histogram_quantile(0.99, sum by (le, db_system_name) (rate(traces_span_metrics_duration_seconds_bucket{service_name="data-service", db_system_name!=""}[1m])))', "{{db_system_name}} p99"),
    ], 0, 24, 12, unit="s"),
    panel("Notificaciones recibidas: estático vs AIOps", [
        ('sum by (pipeline) (increase(aiops_notifications_total{status="firing"}[30m]))', "{{pipeline}}")
    ], 12, 24, 12, kind="barchart", extra={"options": {"orientation": "horizontal", "legend": {"displayMode": "list", "placement": "bottom"}}}),
    panel("Logs de error correlacionados (Loki → trace_id)", [('{service_name=~"service-a|service-b|data-service"} |~ "(?i)error|timeout"', "")], 0, 32, 24, 9, kind="logs", ds=LOKI,
          extra={"options": {"showTime": True, "wrapLogMessage": True, "enableLogDetails": True}}),
]

security = [
    panel("Intentos de autenticación por resultado", [('sum by (outcome) (rate(auth_attempts_total[1m]))', "{{outcome}}")], 0, 0, 12, unit="reqps",
          desc="Golden signal 1: intentos fallidos (fuerza bruta)"),
    panel("Tráfico N-S / E-W / entre nubes (VPC Flow Logs)", [('sum by (direction) (rate(vpc_flow_bytes_total[1m]))', "{{direction}}")], 12, 0, 12, unit="Bps",
          desc="Golden signal 2: tráfico Norte-Sur / Este-Oeste"),
    panel("CVEs activos por severidad (Trivy)", [('sum by (severity) (security_cves_active)', "{{severity}}")], 0, 8, 8, kind="bargauge",
          extra={"options": {"orientation": "horizontal", "displayMode": "gradient"}}, desc="Golden signal 3: CVEs activos"),
    panel("Flujos REJECT por origen", [('sum by (src_svc) (rate(vpc_flow_records_total{action="REJECT"}[1m]))', "{{src_svc}}")], 8, 8, 8, unit="short"),
    panel("Flujos E-W fuera de la matriz permitida", [('sum by (src_svc, dst_svc, dst_port) (increase(vpc_flow_unexpected_total[5m]))', "{{src_svc}} → {{dst_svc}}:{{dst_port}}")], 16, 8, 8, kind="table",
          extra={"transformations": [{"id": "reduce", "options": {"reducers": ["max"]}}]}),
    panel("Hallazgos de seguridad (tipo SCC / Security Hub)", [('sum by (finding_type, severity) (security_findings_total)', "{{finding_type}} ({{severity}})")], 0, 16, 12, kind="table",
          extra={"transformations": [{"id": "reduce", "options": {"reducers": ["lastNotNull"]}}]}),
    panel("Alertas de seguridad activas", [('ALERTS{pipeline="security", alertstate="firing"}', "{{alertname}} {{src_svc}}")], 12, 16, 12, kind="table",
          extra={"transformations": [{"id": "reduce", "options": {"reducers": ["lastNotNull"]}}]}),
    panel("Eventos de autenticación fallida (logs)", [('{service_name="service-a"} |= "security.auth.failure"', "")], 0, 24, 24, 8, kind="logs", ds=LOKI,
          extra={"options": {"showTime": True, "wrapLogMessage": True}}),
]

OUT.mkdir(exist_ok=True)
(OUT / "golden-signals.json").write_text(json.dumps(dash("golden", "Golden Signals y SLO — multi-nube", golden), ensure_ascii=False, indent=1))
_id[0] = 0
(OUT / "security.json").write_text(json.dumps(dash("security", "Golden Signals de Seguridad", security), ensure_ascii=False, indent=1))
print("ok")
