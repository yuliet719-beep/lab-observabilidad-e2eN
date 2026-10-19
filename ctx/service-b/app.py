"""service-b — lógica de pedidos. Despliegue objetivo: AWS ECS Fargate + ECS Service Connect.

Orquesta llamadas a data-service (que accede a Cloud SQL y RDS). Objetivo del experimento E1
(inyección de latencia de 200 ms en el sidecar Envoy de entrada).
"""
import asyncio
import os
import random

import httpx
from fastapi import FastAPI, HTTPException
from opentelemetry import trace
from pydantic import BaseModel

from telemetry import instrument_app, setup_telemetry

SERVICE = "service-b"
log = setup_telemetry(SERVICE)
tracer = trace.get_tracer(SERVICE)
DATA_URL = os.getenv("DATA_SERVICE_URL", "http://mesh-data-service:10000")
client = httpx.AsyncClient(base_url=DATA_URL, timeout=httpx.Timeout(1.5))

app = FastAPI(title=SERVICE)
instrument_app(app, with_httpx=True)


class Checkout(BaseModel):
    customer: str
    sku: str
    qty: int = 1


async def _call(method, path, **kw):
    try:
        r = await client.request(method, path, **kw)
    except httpx.TimeoutException:
        log.error("timeout data-service %s", path)
        raise HTTPException(status_code=504, detail="data-service timeout")
    if r.status_code >= 500:
        log.error("data-service error %s status=%s", path, r.status_code)
        raise HTTPException(status_code=502, detail=f"data-service {r.status_code}")
    if r.status_code == 404:
        raise HTTPException(status_code=404, detail="not found")
    return r.json()


@app.get("/health")
async def health():
    return {"status": "ok", "service": SERVICE}


@app.get("/orders/{order_id}")
async def order(order_id: int):
    with tracer.start_as_current_span("enrich-order"):
        o = await _call("GET", f"/orders/{order_id}")
        inv = await _call("GET", f"/inventory/{o['sku']}")
        await asyncio.sleep(random.uniform(2, 6) / 1000)
        o["stock"] = inv["stock"]
        return o


@app.get("/inventory/{sku}")
async def inventory(sku: str):
    return await _call("GET", f"/inventory/{sku}")


@app.post("/checkout")
async def checkout(body: Checkout):
    inv = await _call("GET", f"/inventory/{body.sku}")
    if inv["stock"] < body.qty:
        raise HTTPException(status_code=409, detail="sin stock")
    created = await _call("POST", "/orders", json=body.model_dump())
    log.info("checkout ok order_id=%s sku=%s", created["id"], body.sku)
    return created
