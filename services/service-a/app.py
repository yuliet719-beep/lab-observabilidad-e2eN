"""service-a — API de borde (Norte-Sur). Despliegue objetivo: GKE Autopilot (GCP) + Cloud Service Mesh.

Endpoints públicos: /api/orders/{id}, /api/checkout, /api/inventory/{sku}, /login
Llama a service-b (AWS ECS) a través del sidecar/mesh: SERVICE_B_URL.
"""
import asyncio
import hashlib
import os
import random
import time

import httpx
from fastapi import FastAPI, HTTPException, Request
from opentelemetry import metrics, trace
from pydantic import BaseModel

from telemetry import instrument_app, setup_telemetry

SERVICE = "service-a"
log = setup_telemetry(SERVICE)
tracer = trace.get_tracer(SERVICE)
meter = metrics.get_meter(SERVICE)
auth_counter = meter.create_counter("auth.attempts", description="Intentos de autenticación por resultado")

SERVICE_B_URL = os.getenv("SERVICE_B_URL", "http://mesh-service-b:10000")
client = httpx.AsyncClient(base_url=SERVICE_B_URL, timeout=httpx.Timeout(2.0))

# Usuarios de prueba (hash SHA-256; solo sandbox)
USERS = {u: hashlib.sha256(f"{u}-pass".encode()).hexdigest() for u in ["ana", "luis", "maria", "carlos", "sofia"]}

app = FastAPI(title=SERVICE)
instrument_app(app, with_httpx=True)


class Checkout(BaseModel):
    customer: str
    sku: str
    qty: int = 1


class Login(BaseModel):
    username: str
    password: str


async def _work(ms_min=3, ms_max=12):
    await asyncio.sleep(random.uniform(ms_min, ms_max) / 1000)


async def _forward(method: str, path: str, **kw):
    try:
        r = await client.request(method, path, **kw)
    except httpx.TimeoutException:
        trace.get_current_span().set_attribute("error.type", "timeout")
        log.error("upstream timeout service-b %s", path)
        raise HTTPException(status_code=504, detail="upstream timeout")
    if r.status_code >= 500:
        log.error("upstream error service-b %s status=%s", path, r.status_code)
        raise HTTPException(status_code=502, detail=f"service-b {r.status_code}")
    if r.status_code == 404:
        raise HTTPException(status_code=404, detail="not found")
    return r.json()


@app.get("/health")
async def health():
    return {"status": "ok", "service": SERVICE}


@app.get("/api/orders/{order_id}")
async def get_order(order_id: int):
    await _work()
    return await _forward("GET", f"/orders/{order_id}")


@app.get("/api/inventory/{sku}")
async def get_inventory(sku: str):
    await _work()
    return await _forward("GET", f"/inventory/{sku}")


@app.post("/api/checkout")
async def checkout(body: Checkout):
    await _work(5, 15)
    return await _forward("POST", "/checkout", json=body.model_dump())


@app.post("/login")
async def login(body: Login, request: Request):
    src = request.headers.get("x-forwarded-for", request.client.host if request.client else "unknown")
    span = trace.get_current_span()
    span.set_attribute("enduser.id", body.username)
    ok = USERS.get(body.username) == hashlib.sha256(body.password.encode()).hexdigest()
    outcome = "success" if ok else "failure"
    auth_counter.add(1, {"outcome": outcome})
    span.set_attribute("auth.outcome", outcome)
    if not ok:
        # Evento de seguridad estructurado (alimenta 'Golden Signals de Seguridad')
        log.warning("security.auth.failure user=%s source.address=%s", body.username, src,
                    extra={"event.name": "auth.failure", "enduser.id": body.username, "source.address": src})
        raise HTTPException(status_code=401, detail="invalid credentials")
    log.info("security.auth.success user=%s", body.username)
    return {"token": hashlib.md5(f"{body.username}{time.time()}".encode()).hexdigest()}
