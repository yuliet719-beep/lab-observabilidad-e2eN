"""Correlador AIOps (Módulo B) + generador de hallazgos de seguridad (Módulo C).

Recibe webhooks de Alertmanager por pipeline:
  /alerts/static    -> solo se registra (línea base de comparación de ruido)
  /alerts/aiops     -> enriquecimiento: trace_id del request fallido/lento (Jaeger), causa raíz
                       candidata (span más profundo con error / mayor self-time + aristas del
                       servicegraph), cambios recientes (caos/ruido) y agrupación en incidentes
  /alerts/security  -> hallazgos normalizados (formato tipo OCSF, como Security Hub; y tipo SCC)
"""
import json
import os
import time
from collections import defaultdict
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

JAEGER = os.getenv("JAEGER_URL", "http://jaeger:16686")
PROM = os.getenv("PROM_URL", "http://prometheus:9090")
DATA = os.getenv("DATA_DIR", "/data")
JAEGER_UI = os.getenv("JAEGER_PUBLIC_URL", "http://localhost:16686")
os.makedirs(DATA, exist_ok=True)

NOTIF = Counter("aiops_notifications_total", "Notificaciones recibidas de Alertmanager", ["pipeline", "status", "severity"])
INCIDENTS = Counter("aiops_incidents_total", "Incidentes abiertos por el correlador", ["root_cause"])
FINDINGS = Counter("security_findings_total", "Hallazgos de seguridad generados", ["finding_type", "severity"])
ENRICH_LAT = Histogram("aiops_enrichment_seconds", "Tiempo de enriquecimiento")

app = FastAPI(title="aiops-correlator")
open_incidents: dict = {}  # root_cause -> incident
INCIDENT_WINDOW = 600


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def append(name, obj):
    with open(os.path.join(DATA, name), "a") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def prom_query(q):
    try:
        r = httpx.get(f"{PROM}/api/v1/query", params={"query": q}, timeout=3)
        return r.json()["data"]["result"]
    except Exception:
        return []


def find_trace(service: str, signal: str):
    """Busca el trace más reciente fallido (o lento) del servicio en los últimos 3 min."""
    params = {"service": service, "lookback": "2m", "limit": 20}
    if "errors" in signal:
        params["tags"] = json.dumps({"error": "true"})
    else:
        params["minDuration"] = "300ms"
    try:
        r = httpx.get(f"{JAEGER}/api/traces", params=params, timeout=15)
        traces = r.json().get("data") or []
    except Exception as e:
        return None, None, f"jaeger error: {e}"
    if not traces:
        return None, None, "sin traces"
    # el más reciente
    traces.sort(key=lambda t: max(s["startTime"] for s in t["spans"]), reverse=True)
    t = traces[0]
    # evidencia: se persiste el trace completo (Jaeger en memoria rota los traces antiguos)
    os.makedirs(os.path.join(DATA, "traces"), exist_ok=True)
    with open(os.path.join(DATA, "traces", f'{t["traceID"]}.json'), "w") as f:
        json.dump(t, f)
    return t["traceID"], analyze_trace(t, signal), None


def analyze_trace(t, signal):
    procs = {pid: p["serviceName"] for pid, p in t["processes"].items()}
    spans = {s["spanID"]: s for s in t["spans"]}
    children = defaultdict(list)
    for s in t["spans"]:
        for ref in s.get("references", []):
            if ref["refType"] == "CHILD_OF" and ref["spanID"] in spans:
                children[ref["spanID"]].append(s)

    def depth(s):
        d, cur = 0, s
        while cur.get("references") and cur["references"][0]["spanID"] in spans:
            cur = spans[cur["references"][0]["spanID"]]
            d += 1
        return d

    def tags(s):
        return {x["key"]: x["value"] for x in s.get("tags", [])}

    if "errors" in signal:
        errs = [s for s in t["spans"] if tags(s).get("error") in (True, "true") or tags(s).get("otel.status_code") == "ERROR"]
        if not errs:
            return {"service": "desconocido"}
        s = max(errs, key=depth)
        tg = tags(s)
        return {"service": procs[s["processID"]], "span": s["operationName"], "error.type": tg.get("error.type"),
                "db.system.name": tg.get("db.system.name"), "db.query.text": tg.get("db.query.text")}
    # latencia: span con mayor tiempo propio (self-time)
    def self_time(s):
        return s["duration"] - sum(c["duration"] for c in children[s["spanID"]])

    s = max(t["spans"], key=self_time)
    return {"service": procs[s["processID"]], "span": s["operationName"], "self_time_ms": round(self_time(s) / 1000, 1)}


def graph_edges():
    """Aristas del servicegraph con mayor tasa de fallo/latencia (confirma la causa raíz)."""
    fail = prom_query('sum by (client, server) (rate(traces_service_graph_request_failed_total[2m])) / '
                      'sum by (client, server) (rate(traces_service_graph_request_total[2m])) > 0.01')
    lat = prom_query('histogram_quantile(0.99, sum by (client, server, le) (rate(traces_service_graph_request_server_seconds_bucket[2m]))) > 0.15')
    return {
        "failing_edges": [f'{r["metric"].get("client")}->{r["metric"].get("server")}: {float(r["value"][1]):.1%}' for r in fail],
        "slow_edges": [f'{r["metric"].get("client")}->{r["metric"].get("server")}: {float(r["value"][1])*1000:.0f}ms' for r in lat],
    }


def recent_changes():
    out = []
    p = os.path.join(DATA, "changes.jsonl")
    if os.path.exists(p):
        for line in open(p).readlines()[-5:]:
            c = json.loads(line)
            if time.time() - c.get("ts", 0) < 900:
                out.append(c)
    return out


@app.post("/alerts/{pipeline}")
async def alerts(pipeline: str, request: Request):
    payload = await request.json()
    received = time.time()
    for a in payload.get("alerts", []):
        lab = a.get("labels", {})
        rec = {
            "received_at": received, "received_iso": now_iso(), "pipeline": pipeline, "status": a["status"],
            "alertname": lab.get("alertname"), "service": lab.get("service_name") or lab.get("mesh_workload") or lab.get("src_svc"),
            "severity": lab.get("severity"), "startsAt": a.get("startsAt"), "fingerprint": a.get("fingerprint"),
            "summary": a.get("annotations", {}).get("summary"),
        }
        NOTIF.labels(pipeline, a["status"], lab.get("severity", "none")).inc()
        append("notifications.jsonl", rec)
        if pipeline == "aiops" and a["status"] == "firing" and lab.get("severity") == "page":
            enrich(rec, lab)
        if pipeline == "security" and a["status"] == "firing":
            finding(rec, lab, a)
    return {"ok": True}


def enrich(rec, lab):
    t0 = time.time()
    trace_id, rc, err = find_trace(rec["service"], lab.get("signal", "errors"))
    edges = graph_edges()
    root = (rc or {}).get("service", rec["service"])
    inc = open_incidents.get(root)
    if not inc or time.time() - inc["opened_at"] > INCIDENT_WINDOW:
        inc = {"incident_id": f"INC-{int(time.time())}", "opened_at": time.time(), "alerts": []}
        open_incidents[root] = inc
        INCIDENTS.labels(root).inc()
    inc["alerts"].append(rec["alertname"] + "/" + str(rec["service"]))
    enriched = {
        **rec,
        "incident_id": inc["incident_id"],
        "trace_id": trace_id,
        "trace_url": f"{JAEGER_UI}/trace/{trace_id}" if trace_id else None,
        "root_cause_candidate": rc,
        "service_graph": edges,
        "recent_changes": recent_changes(),
        "slo": {
            "error_ratio_1m": _val(f'sli:error_ratio:rate1m{{service_name="{rec["service"]}"}}'),
            "latency_p99_1m_s": _val(f'sli:latency_p99:1m{{service_name="{rec["service"]}"}}'),
            "error_band_upper": _val(f'aiops:error_ratio:band_upper{{service_name="{rec["service"]}"}}'),
        },
        "enrichment_error": err,
        "enrichment_ms": round((time.time() - t0) * 1000),
    }
    ENRICH_LAT.observe(time.time() - t0)
    append("incidents.jsonl", enriched)
    print("ENRICHED ALERT", json.dumps(enriched, ensure_ascii=False), flush=True)


def _val(q):
    r = prom_query(q)
    return round(float(r[0]["value"][1]), 4) if r else None


def finding(rec, lab, a):
    sev = "HIGH" if lab.get("severity") == "page" else "MEDIUM"
    f = {
        # Estructura tipo OCSF Detection Finding (Security Hub) con equivalentes SCC
        "class_name": "Detection Finding", "time": rec["received_iso"], "severity": sev,
        "finding_info": {"title": lab.get("alertname"), "desc": rec["summary"], "types": [lab.get("finding_type")],
                          "uid": a.get("fingerprint")},
        "resources": [{"name": rec["service"], "labels": lab}],
        "scc_equivalent": {"category": lab.get("finding_type", "").split("/")[-1].upper().replace(" ", "_"),
                           "state": "ACTIVE", "findingClass": "THREAT" if "TTPs" in lab.get("finding_type", "") else "VULNERABILITY"},
    }
    FINDINGS.labels(lab.get("finding_type", "n/a"), sev).inc()
    append("findings.jsonl", f)


@app.get("/incidents")
def incidents():
    p = os.path.join(DATA, "incidents.jsonl")
    return [json.loads(x) for x in open(p)] if os.path.exists(p) else []


@app.get("/metrics")
def metrics():
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/health")
def health():
    return {"status": "ok"}
