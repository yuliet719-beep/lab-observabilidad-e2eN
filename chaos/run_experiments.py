"""Orquestador de experimentos de caos controlados (Módulo D) — SOLO SANDBOX.

Cronograma (minutos desde el arranque del stack; configurable por variables de entorno):
  0  .. BASELINE_MIN          línea base con perfil de ruido natural (aprende baseline ±2σ)
  BASELINE_MIN .. +NOISE_MIN  ventana de comparación de ruido: umbrales estáticos vs AIOps (sin caos)
  E1  latencia 200 ms en service-b (fault injection en el sidecar Envoy, 100 % de requests) — FAULT_MIN
  RECOVERY_MIN de recuperación
  E2  error rate 10 % en data-service (timeouts reales de BD vía /admin/chaos) — FAULT_MIN
  RECOVERY_MIN de recuperación

Hipótesis (formato Game Day):
  H-E1: si service-b añade 200 ms, el p99 de service-a supera el SLO (300 ms) y AIOpsLatencyAnomalySLO pagina en < 2 min
        con causa raíz service-b (mayor self-time en el trace).
  H-E2: si data-service falla el 10 % por timeout de BD, AIOpsCorrelatedErrorLatency pagina en < 2 min con el trace_id
        de un request fallido y causa raíz data-service (span SELECT con error).
Guardrails: abortar si la disponibilidad de service-a < 80 % durante 60 s (kill switch) — se restaura la configuración.
"""
import json
import os
import time
import urllib.parse
import urllib.request

DATA = os.getenv("DATA_DIR", "/data")
ENVOY_B = os.getenv("ENVOY_B_ADMIN", "http://mesh-service-b:9901")
DATA_SVC = os.getenv("DATA_SERVICE_ADMIN", "http://data-service:8000")
PROM = os.getenv("PROM_URL", "http://prometheus:9090")
TOKEN = os.getenv("CHAOS_TOKEN", "sandbox-only")
BASELINE_MIN = float(os.getenv("BASELINE_MIN", "35"))
NOISE_MIN = float(os.getenv("NOISE_MIN", "20"))
FAULT_MIN = float(os.getenv("FAULT_MIN", "5"))
RECOVERY_MIN = float(os.getenv("RECOVERY_MIN", "10"))
T0 = float(os.getenv("T0", str(time.time())))

timeline = {"t0": T0}


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def change(kind, detail):
    c = {"ts": time.time(), "kind": kind, "detail": detail}
    with open(os.path.join(DATA, "changes.jsonl"), "a") as f:
        f.write(json.dumps(c) + "\n")


def post(url, body=None, headers=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else b"", method="POST",
                                 headers={"content-type": "application/json", **(headers or {})})
    return urllib.request.urlopen(req, timeout=5).read().decode()


def prom(q):
    u = f"{PROM}/api/v1/query?" + urllib.parse.urlencode({"query": q})
    r = json.load(urllib.request.urlopen(u, timeout=5))["data"]["result"]
    return float(r[0]["value"][1]) if r else None


def wait_until(minute):
    target = T0 + minute * 60
    while time.time() < target:
        time.sleep(min(30, max(1, target - time.time())))


def guarded_wait(seconds, restore):
    end = time.time() + seconds
    bad = 0
    while time.time() < end:
        time.sleep(10)
        avail = prom('1 - sli:error_ratio:rate1m{service_name="service-a"}')
        bad = bad + 10 if (avail is not None and avail < 0.80) else 0
        if bad >= 60:
            log(f"GUARDRAIL: disponibilidad {avail:.1%} < 80 % por 60 s -> abortando experimento")
            restore()
            return False
    return True


def e1_on():
    post(f"{ENVOY_B}/runtime_modify?fault.http.delay.fixed_delay_percent=100&fault.http.delay.fixed_duration_ms=200")


def e1_off():
    post(f"{ENVOY_B}/runtime_modify?fault.http.delay.fixed_delay_percent=0")


def e2_on():
    post(f"{DATA_SVC}/admin/chaos", {"error_rate": 0.10, "mode": "db_timeout"}, {"x-chaos-token": TOKEN})


def e2_off():
    post(f"{DATA_SVC}/admin/chaos", {"error_rate": 0.0}, {"x-chaos-token": TOKEN})


def save():
    with open(os.path.join(DATA, "experiments.json"), "w") as f:
        json.dump(timeline, f, indent=1)


def main():
    for _ in range(60):  # esperar a que el sidecar y data-service estén listos
        try:
            e1_off(); e2_off()
            break
        except Exception:
            time.sleep(5)
    log(f"Línea base hasta el min {BASELINE_MIN}")
    wait_until(BASELINE_MIN)
    timeline["noise_window"] = {"start": time.time()}
    log("Ventana de comparación de ruido (sin caos)")
    wait_until(BASELINE_MIN + NOISE_MIN)
    timeline["noise_window"]["end"] = time.time()
    save()

    m = BASELINE_MIN + NOISE_MIN
    for name, on, off, desc in [
        ("E1", e1_on, e1_off, "latencia +200 ms en service-b (Envoy fault injection, 100 %)"),
        ("E2", e2_on, e2_off, "error rate 10 % en data-service (statement_timeout BD)"),
    ]:
        log(f"{name} INICIO: {desc}")
        timeline[name] = {"start": time.time(), "desc": desc}
        change("chaos-experiment", f"{name} start: {desc}")
        on()
        completed = guarded_wait(FAULT_MIN * 60, off)
        off()
        timeline[name].update({"end": time.time(), "completed": completed})
        change("chaos-experiment", f"{name} end")
        log(f"{name} FIN (completado={completed}); recuperación {RECOVERY_MIN} min")
        save()
        m += FAULT_MIN + RECOVERY_MIN
        wait_until(m)
        timeline[name]["recovery_end"] = time.time()
        save()
    log("Experimentos terminados")


if __name__ == "__main__":
    main()
