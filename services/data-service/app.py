"""data-service — tercer microservicio (Módulo A). Accede a dos motores gestionados:

  * Cloud SQL for PostgreSQL (GCP)  -> tabla orders     (CLOUDSQL_DSN)
  * Amazon RDS for PostgreSQL (AWS) -> tabla inventory  (RDS_DSN)

Spans de base de datos con OTel DB Semantic Conventions (opt-in estable "database").
Incluye:
  - /admin/chaos : inyección de fallas controlada (E2: error rate 10 %), solo sandbox.
  - Perfil de "variabilidad natural" (NOISE_PROFILE=on): micro-cortes y job batch periódico
    que generan el ruido que dispara umbrales estáticos (Módulo B).
"""
import os
import random
import threading
import time

from fastapi import FastAPI, Header, HTTPException
from opentelemetry import metrics, trace
from psycopg import errors as pgerrors
from psycopg_pool import ConnectionPool
from pydantic import BaseModel

from telemetry import instrument_app, setup_telemetry

SERVICE = "data-service"
log = setup_telemetry(SERVICE)
tracer = trace.get_tracer(SERVICE)
meter = metrics.get_meter(SERVICE)

app = FastAPI(title=SERVICE)
instrument_app(app, with_httpx=False, with_psycopg=True)

cloudsql = ConnectionPool(os.getenv("CLOUDSQL_DSN", "postgresql://app:app@cloudsql:5432/orders"), min_size=2, max_size=10, open=True)
rds = ConnectionPool(os.getenv("RDS_DSN", "postgresql://app:app@rds:5432/inventory"), min_size=2, max_size=10, open=True)

CHAOS_TOKEN = os.getenv("CHAOS_TOKEN", "sandbox-only")
state = {"error_rate": 0.0, "mode": "db_timeout", "blip": False, "batch": False}
lock = threading.Lock()


def _fault_gauge(options):
    yield metrics.Observation(state["error_rate"], {"kind": "chaos_error_rate"})
    yield metrics.Observation(1 if state["blip"] else 0, {"kind": "noise_blip"})
    yield metrics.Observation(1 if state["batch"] else 0, {"kind": "noise_batch"})


meter.create_observable_gauge("lab.fault.active", callbacks=[_fault_gauge], description="Fallas activas (caos/ruido)")


# ---------- Perfil de variabilidad natural (ruido) ----------
def _noise_loop():
    rnd = random.Random(int(os.getenv("NOISE_SEED", "42")))
    next_blip = time.time() + rnd.uniform(120, 300)
    next_batch = time.time() + rnd.uniform(180, 360)
    while True:
        now = time.time()
        if now >= next_blip:
            state["blip"] = True
            log.warning("noise: micro-corte de conexiones (20 s)")
            time.sleep(20)
            state["blip"] = False
            next_blip = time.time() + rnd.uniform(240, 480)
        if now >= next_batch:
            state["batch"] = True
            log.info("noise: job batch de reportes iniciado (45 s)")
            time.sleep(45)
            state["batch"] = False
            next_batch = time.time() + rnd.uniform(300, 540)
        time.sleep(1)


if os.getenv("NOISE_PROFILE", "on") == "on":
    threading.Thread(target=_noise_loop, daemon=True).start()


def _maybe_fail(pool, span_name):
    """Aplica caos (E2) o ruido antes de la consulta real."""
    if state["blip"] and random.random() < 0.04:
        log.error("db connection reset (transitorio)")
        raise HTTPException(status_code=503, detail="connection reset")
    if state["error_rate"] > 0 and random.random() < state["error_rate"]:
        # Falla realista: consulta que excede statement_timeout (300 ms) -> QueryCanceled
        try:
            with pool.connection() as conn:
                conn.execute("SET statement_timeout = '300ms'")
                conn.execute("SELECT pg_sleep(1)")
        except pgerrors.QueryCanceled as e:
            trace.get_current_span().set_attribute("error.type", "QueryCanceled")
            log.error("db statement timeout en %s: %s", span_name, str(e).strip())
            raise HTTPException(status_code=503, detail="db timeout")


class NewOrder(BaseModel):
    customer: str
    sku: str
    qty: int = 1


class Chaos(BaseModel):
    error_rate: float = 0.0
    mode: str = "db_timeout"


@app.get("/health")
def health():
    return {"status": "ok", "service": SERVICE}


@app.get("/orders/{order_id}")
def get_order(order_id: int):
    _maybe_fail(cloudsql, "orders")
    with cloudsql.connection() as conn:
        row = conn.execute("SELECT id, customer, sku, qty, created_at FROM orders WHERE id = %s", (order_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="order not found")
    return {"id": row[0], "customer": row[1], "sku": row[2], "qty": row[3], "created_at": row[4].isoformat()}


@app.get("/inventory/{sku}")
def get_inventory(sku: str):
    _maybe_fail(rds, "inventory")
    with rds.connection() as conn:
        if state["batch"] and random.random() < 0.15:
            # job batch compitiendo por I/O -> consultas lentas
            conn.execute("SELECT pg_sleep(%s)", (random.uniform(0.07, 0.13),))
        row = conn.execute("SELECT sku, stock FROM inventory WHERE sku = %s", (sku,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="sku not found")
    return {"sku": row[0], "stock": row[1]}


@app.post("/orders")
def create_order(body: NewOrder):
    _maybe_fail(cloudsql, "orders")
    with cloudsql.connection() as conn:
        oid = conn.execute(
            "INSERT INTO orders (customer, sku, qty) VALUES (%s, %s, %s) RETURNING id", (body.customer, body.sku, body.qty)
        ).fetchone()[0]
    with rds.connection() as conn:
        conn.execute("UPDATE inventory SET stock = GREATEST(stock - %s, 0) WHERE sku = %s", (body.qty, body.sku))
    return {"id": oid, "status": "created"}


@app.post("/admin/chaos")
def chaos(body: Chaos, x_chaos_token: str = Header(default="")):
    if x_chaos_token != CHAOS_TOKEN:
        raise HTTPException(status_code=403, detail="forbidden")
    with lock:
        state["error_rate"] = max(0.0, min(body.error_rate, 0.5))
        state["mode"] = body.mode
    log.warning("chaos: error_rate=%s mode=%s", state["error_rate"], body.mode)
    return state
