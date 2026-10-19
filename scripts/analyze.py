"""Análisis de evidencias del LAB: MTTD, SLO/error budget, ruido estático vs AIOps, seguridad.

Lee data/ (experiments.json, notifications.jsonl, incidents.jsonl, findings.jsonl, traces/) y consulta Prometheus.
Escribe docs/evidencias/resultados.json y figuras PNG.
Uso: python3 scripts/analyze.py   (con el stack aún arriba)
"""
import json
import os
import statistics
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "docs" / "evidencias"
OUT.mkdir(parents=True, exist_ok=True)
PROM = os.getenv("PROM_URL", "http://localhost:9090")
SLO_AVAIL, SLO_LAT, WINDOW_28D = 0.995, 0.99, 28 * 86400

NAVY, BLUE, ORANGE, RED, GREY, GREEN = "#0B2545", "#2F6690", "#E07A1F", "#C0392B", "#8D99AE", "#2E8B57"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.spines.top": False, "axes.spines.right": False})


def jl(name):
    p = DATA / name
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.exists() else []


def q(expr, t):
    u = f"{PROM}/api/v1/query?" + urllib.parse.urlencode({"query": expr, "time": t})
    r = json.load(urllib.request.urlopen(u))["data"]["result"]
    return r


def qv(expr, t):
    r = q(expr, t)
    return float(r[0]["value"][1]) if r else 0.0


def qr(expr, start, end, step=15):
    u = f"{PROM}/api/v1/query_range?" + urllib.parse.urlencode({"query": expr, "start": start, "end": end, "step": step})
    return json.load(urllib.request.urlopen(u))["data"]["result"]


exp = json.loads((DATA / "experiments.json").read_text())
T0 = exp["t0"]
notifs = jl("notifications.jsonl")
incidents = jl("incidents.jsonl")
findings = jl("findings.jsonl")
attack = {k: float((DATA / f"attack_{k}").read_text()) for k in ("start", "end") if (DATA / f"attack_{k}").exists()}
res = {"t0": T0, "t0_iso": datetime.fromtimestamp(T0).isoformat()}


# ---------------- Ruido: estático vs AIOps ----------------
def count_window(a, b):
    firing = [n for n in notifs if n["status"] == "firing" and a <= n["received_at"] <= b]
    by = defaultdict(Counter)
    for n in firing:
        by[n["pipeline"]][n["alertname"]] += 1
    return {p: {"total": sum(c.values()), "pages": sum(1 for n in firing if n["pipeline"] == p and n.get("severity") == "page"),
                "por_alerta": dict(c)} for p, c in by.items()}


# Ventana de ruido = desde que existe línea base (T0+5 min) hasta el inicio de E1, sin fallas inyectadas
nw = {"start": T0 + 300, "end": exp["E1"]["start"]}
res["ruido"] = {"ventana_min": round((nw["end"] - nw["start"]) / 60, 1), "notificaciones": count_window(nw["start"], nw["end"])}

# Instancias de alerta que llegaron a 'firing' en Prometheus (antes de Alertmanager)
def alert_firings(a, b, pipeline):
    r = qr(f'ALERTS{{alertstate="firing", pipeline="{pipeline}"}}', a, b, 15)
    n = 0
    for s in r:
        prev = None
        for ts, _ in s["values"]:
            ts = float(ts)
            if prev is None or ts - prev > 30:
                n += 1
            prev = ts
    return n


res["ruido"]["instancias_firing"] = {p: alert_firings(nw["start"], nw["end"], p) for p in ("static", "aiops")}
st = res["ruido"]["notificaciones"].get("static", {}).get("total", 0)
ai = res["ruido"]["notificaciones"].get("aiops", {}).get("total", 0)
res["ruido"]["reduccion_notificaciones_pct"] = round(100 * (1 - ai / st), 1) if st else None
# normalizado a alertas/día
dur_d = (nw["end"] - nw["start"]) / 86400
res["ruido"]["por_dia"] = {"static": round(st / dur_d), "aiops": round(ai / dur_d)}


# ---------------- Experimentos: MTTD, SLO, error budget ----------------
EXPECTED_ROOT = {"E1": "service-b", "E2": "data-service"}
res["experimentos"] = {}
for name in ("E1", "E2"):
    e = exp.get(name)
    if not e:
        continue
    s, end, rec = e["start"], e["end"], e.get("recovery_end", e["end"] + 600)
    pages = sorted([n for n in notifs if n["pipeline"] == "aiops" and n["status"] == "firing" and n.get("severity") == "page" and s <= n["received_at"] <= end + 120],
                   key=lambda n: n["received_at"])
    static = sorted([n for n in notifs if n["pipeline"] == "static" and n["status"] == "firing" and s <= n["received_at"] <= end + 120], key=lambda n: n["received_at"])
    inc = [i for i in incidents if s <= i["received_at"] <= end + 120]
    # instante en que la alerta pasa a firing en Prometheus
    fire_ts = None
    for srs in qr('ALERTS{alertstate="firing", pipeline="aiops", severity="page"}', s, end + 120, 5):
        t = float(srs["values"][0][0])
        if t >= s and (fire_ts is None or t < fire_ts):
            fire_ts = t
    dur = rec - s
    total = qv(f'sum(increase(http_server_request_duration_seconds_count{{service_name="service-a"}}[{int(dur)}s]))', rec)
    bad_av = qv(f'sum(increase(http_server_request_duration_seconds_count{{service_name="service-a", http_response_status_code=~"5.."}}[{int(dur)}s]))', rec)
    good_lat = qv(f'sum(increase(http_server_request_duration_seconds_bucket{{service_name="service-a", le="0.3"}}[{int(dur)}s]))', rec)
    fdur = end - s
    f_total = qv(f'sum(increase(http_server_request_duration_seconds_count{{service_name="service-a"}}[{int(fdur)}s]))', end)
    f_bad_av = qv(f'sum(increase(http_server_request_duration_seconds_count{{service_name="service-a", http_response_status_code=~"5.."}}[{int(fdur)}s]))', end)
    f_good = qv(f'sum(increase(http_server_request_duration_seconds_bucket{{service_name="service-a", le="0.3"}}[{int(fdur)}s]))', end)
    rps = f_total / fdur if fdur else 0
    budget_av = (1 - SLO_AVAIL) * rps * WINDOW_28D
    budget_lat = (1 - SLO_LAT) * rps * WINDOW_28D
    p99_peak = max((float(v) for srs in qr('sli:latency_p99:1m{service_name="service-a"}', s, end, 15) for _, v in srs["values"]), default=0)
    err_peak = max((float(v) for srs in qr('sli:error_ratio:rate1m{service_name="service-a"}', s, end, 15) for _, v in srs["values"]), default=0)
    first = pages[0] if pages else None
    rc = (inc[0].get("root_cause_candidate") or {}) if inc else {}
    res["experimentos"][name] = {
        "descripcion": e["desc"], "duracion_falla_s": round(fdur),
        "mttd_notificacion_s": round(first["received_at"] - s, 1) if first else None,
        "mttd_firing_prometheus_s": round(fire_ts - s, 1) if fire_ts else None,
        "primera_alerta": first["alertname"] if first else None,
        "paginas_aiops": len(pages), "notificaciones_estaticas": len(static),
        "alertas_estaticas": dict(Counter(n["alertname"] for n in static)),
        "incidente": inc[0]["incident_id"] if inc else None,
        "trace_id": inc[0].get("trace_id") if inc else None,
        "causa_raiz_candidata": rc,
        "causa_raiz_correcta": rc.get("service") == EXPECTED_ROOT[name],
        "durante_falla": {
            "requests": round(f_total), "rps": round(rps, 2),
            "disponibilidad": round(1 - f_bad_av / f_total, 4) if f_total else None,
            "latency_good_ratio": round(f_good / f_total, 4) if f_total else None,
            "p99_pico_s": round(p99_peak, 3), "error_ratio_pico": round(err_peak, 4),
            "burn_rate_disponibilidad": round((f_bad_av / f_total) / (1 - SLO_AVAIL), 1) if f_total else None,
            "burn_rate_latencia": round((1 - f_good / f_total) / (1 - SLO_LAT), 1) if f_total else None,
        },
        "ventana_falla_mas_recuperacion": {"requests": round(total), "malas_disponibilidad": round(bad_av), "lentas_>300ms": round(total - good_lat)},
        "error_budget_28d": {
            "presupuesto_disponibilidad_req": round(budget_av), "presupuesto_latencia_req": round(budget_lat),
            "consumo_disponibilidad_pct": round(100 * bad_av / budget_av, 2) if budget_av else None,
            "consumo_latencia_pct": round(100 * (total - good_lat) / budget_lat, 2) if budget_lat else None,
        },
    }

# ---------------- Seguridad ----------------
if attack:
    a, b = attack["start"], attack["end"] + 150
    sec = sorted([n for n in notifs if n["pipeline"] == "security" and n["status"] == "firing" and a <= n["received_at"] <= b], key=lambda n: n["received_at"])
    res["seguridad"] = {
        "duracion_ataque_s": round(attack["end"] - attack["start"]),
        "alertas": [{"alerta": n["alertname"], "origen": n["service"], "t_desde_inicio_s": round(n["received_at"] - a, 1), "resumen": n["summary"]} for n in sec],
        "hallazgos": len([f for f in findings]),
        "auth_fallidas_pico_por_s": round(max((float(v) for srs in qr('sum(rate(auth_attempts_total{outcome="failure"}[1m]))', a, b, 15) for _, v in srs["values"]), default=0), 2),
        "flujos_reject": round(qv('sum(increase(vpc_flow_records_total{action="REJECT"}[10m]))', b)),
        "flujos_no_permitidos": [{**s["metric"], "conteo": float(s["value"][1])} for s in q('sum by (src_svc, dst_svc, dst_port) (increase(vpc_flow_unexpected_total[10m])) > 0', b)],
    }
res["cves"] = {s["metric"]["image"]: {} for s in q("security_cves_active", attack.get("end", T0 + 3600))}
for s in q("sum by (image, severity) (security_cves_active)", attack.get("end", T0 + 3600)):
    res["cves"][s["metric"]["image"]][s["metric"]["severity"]] = int(float(s["value"][1]))
res["flujos_por_direccion_bytes_1h"] = {s["metric"]["direction"]: round(float(s["value"][1])) for s in
                                       q("sum by (direction) (increase(vpc_flow_bytes_total[1h]))", nw["end"])}

(OUT / "resultados.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
print(json.dumps(res, ensure_ascii=False, indent=1))


# ---------------- Figuras ----------------
def series(expr, a, b, step=15):
    r = qr(expr, a, b, step)
    if not r:
        return [], []
    v = r[0]["values"]
    return [datetime.fromtimestamp(float(t)) for t, _ in v], [float(x) for _, x in v]


a, b = nw["start"] - 300, exp["E2"].get("recovery_end", exp["E2"]["end"] + 600)
fig, axs = plt.subplots(3, 1, figsize=(10, 7.2), sharex=True)
x, y = series('sli:latency_p99:1m{service_name="service-a"}', a, b)
x2, y2 = series('aiops:latency_p99:band_upper{service_name="service-a"}', a, b)
axs[0].plot(x, [v * 1000 for v in y], color=NAVY, lw=1.6, label="p99 service-a")
axs[0].plot(x2, [v * 1000 for v in y2], color=BLUE, lw=1, ls="--", label="banda superior (baseline + 2σ)")
axs[0].axhline(300, color=RED, lw=1, label="SLO_threshold 300 ms")
axs[0].set_ylabel("ms"); axs[0].set_yscale("log"); axs[0].legend(loc="upper left", fontsize=7, frameon=False)
x, y = series('sli:error_ratio:rate1m{service_name="service-a"}', a, b)
x2, y2 = series('aiops:error_ratio:band_upper{service_name="service-a"}', a, b)
axs[1].plot(x, [v * 100 for v in y], color=NAVY, lw=1.6, label="error rate service-a")
axs[1].plot(x2, [v * 100 for v in y2], color=BLUE, lw=1, ls="--", label="banda superior (mín. 0,5 %)")
axs[1].set_ylabel("% 5xx"); axs[1].legend(loc="upper left", fontsize=7, frameon=False)
x, y = series('sli:latency_good_ratio:rate1m{service_name="service-a"}', a, b)
axs[2].plot(x, [v * 100 for v in y], color=NAVY, lw=1.6, label="% requests < 300 ms")
axs[2].axhline(99, color=RED, lw=1, label="objetivo 99 %")
axs[2].set_ylabel("%"); axs[2].legend(loc="lower left", fontsize=7, frameon=False)
for ax in axs:
    for name, col in (("E1", ORANGE), ("E2", RED)):
        e = exp[name]
        ax.axvspan(datetime.fromtimestamp(e["start"]), datetime.fromtimestamp(e["end"]), color=col, alpha=0.12)
    for n in notifs:
        if n["pipeline"] == "aiops" and n["status"] == "firing" and n.get("severity") == "page" and a <= n["received_at"] <= b:
            ax.axvline(datetime.fromtimestamp(n["received_at"]), color=GREEN, lw=1, ls=":")
axs[0].text(datetime.fromtimestamp(exp["E1"]["start"]), axs[0].get_ylim()[1] * 0.6, " E1", color=ORANGE, fontweight="bold")
axs[0].text(datetime.fromtimestamp(exp["E2"]["start"]), axs[0].get_ylim()[1] * 0.6, " E2", color=RED, fontweight="bold")
axs[2].xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
axs[0].set_title("service-a: SLI frente a la línea base dinámica (sombreado = falla; punteado verde = página AIOps)", loc="left", fontsize=9)
fig.tight_layout(); fig.savefig(OUT / "fig_experimentos.png", dpi=170); plt.close(fig)

# barras ruido
nz = res["ruido"]["notificaciones"]
fig, ax = plt.subplots(figsize=(5.5, 2.6))
labels = ["Umbrales estáticos", "AIOps (dinámico + correlación)"]
vals = [nz.get("static", {}).get("total", 0), nz.get("aiops", {}).get("total", 0)]
ax.barh(labels, vals, color=[GREY, NAVY])
for i, v in enumerate(vals):
    ax.text(v, i, f" {v}", va="center")
ax.set_xlabel(f"notificaciones en {res['ruido']['ventana_min']} min sin fallas reales")
fig.tight_layout(); fig.savefig(OUT / "fig_ruido.png", dpi=170); plt.close(fig)


# waterfall de traces enriquecidos
def waterfall(trace_id, title, fname):
    p = DATA / "traces" / f"{trace_id}.json"
    if not p.exists():
        return
    t = json.loads(p.read_text())
    pr = {k: v["serviceName"] for k, v in t["processes"].items()}
    spans = [s for s in t["spans"] if "http send" not in s["operationName"] and "http receive" not in s["operationName"]]
    spans.sort(key=lambda s: s["startTime"])
    t0 = spans[0]["startTime"]
    col = {"service-a": BLUE, "service-b": ORANGE, "data-service": GREEN}
    fig, ax = plt.subplots(figsize=(8, 0.28 * len(spans) + 0.8))
    for i, s in enumerate(spans):
        tg = {x["key"]: x["value"] for x in s.get("tags", [])}
        err = tg.get("error") in (True, "true") or tg.get("otel.status_code") == "ERROR"
        ax.barh(i, s["duration"] / 1000, left=(s["startTime"] - t0) / 1000, color=RED if err else col.get(pr[s["processID"]], GREY), height=0.6)
        ax.text((s["startTime"] - t0) / 1000 + s["duration"] / 1000 + 3, i, f'{pr[s["processID"]]} · {s["operationName"][:38]} ({s["duration"]/1000:.0f} ms)', va="center", fontsize=7)
    ax.invert_yaxis(); ax.set_yticks([]); ax.set_xlabel("ms desde el inicio del trace")
    ax.set_title(f"{title}\ntrace_id {trace_id}", loc="left", fontsize=8)
    ax.set_xlim(0, max((s["startTime"] - t0 + s["duration"]) / 1000 for s in spans) * 1.6)
    fig.tight_layout(); fig.savefig(OUT / fname, dpi=170); plt.close(fig)


for name in ("E1", "E2"):
    tid = res["experimentos"].get(name, {}).get("trace_id")
    if tid:
        waterfall(tid, f"{name}: trace adjuntado automáticamente a la alerta (rojo = span con error)", f"fig_trace_{name}.png")

# seguridad
if attack:
    a, b = attack["start"] - 300, attack["end"] + 150
    fig, axs = plt.subplots(1, 2, figsize=(10, 2.8))
    x, y = series('sum(rate(auth_attempts_total{outcome="failure"}[1m]))', a, b)
    axs[0].plot(x, y, color=RED, lw=1.6); axs[0].set_title("Autenticaciones fallidas /s", loc="left", fontsize=9)
    for d, c in (("north-south", NAVY), ("east-west", BLUE), ("cross-cloud", ORANGE)):
        x, y = series(f'sum(rate(vpc_flow_bytes_total{{direction="{d}"}}[1m]))', a, b)
        axs[1].plot(x, [v / 1024 for v in y], color=c, lw=1.4, label=d)
    axs[1].set_title("Tráfico por dirección (KiB/s, flow logs)", loc="left", fontsize=9); axs[1].legend(fontsize=7, frameon=False)
    for ax in axs:
        ax.axvspan(datetime.fromtimestamp(attack["start"]), datetime.fromtimestamp(attack["end"]), color=RED, alpha=0.1)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    fig.tight_layout(); fig.savefig(OUT / "fig_seguridad.png", dpi=170); plt.close(fig)

# muestras de evidencia
for i in incidents:
    if i.get("trace_id"):
        (OUT / f"alerta_enriquecida_{i['alertname']}.json").write_text(json.dumps(i, ensure_ascii=False, indent=1))
if findings:
    (OUT / "hallazgos_seguridad.json").write_text(json.dumps(findings[:10], ensure_ascii=False, indent=1))
for f, n in (("flowlogs/aws-vpc-flow.log", 40), ("flowlogs/gcp-vpc-flow.jsonl", 20)):
    p = DATA / f
    if p.exists():
        lines = p.read_text().splitlines()
        rej = [x for x in lines if "REJECT" in x or "DENIED" in x][:15]
        (OUT / ("muestra_" + Path(f).name)).write_text("\n".join(lines[:n - len(rej)] + rej) + "\n")
print("figuras ->", OUT)
