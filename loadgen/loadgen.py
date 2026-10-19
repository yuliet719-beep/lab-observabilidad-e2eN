"""Generador de carga Norte-Sur (clientes de internet -> mesh-service-a). Tasa constante con llegadas Poisson."""
import asyncio
import os
import random
import time

import httpx

TARGET = os.getenv("TARGET", "http://mesh-service-a:10000")
RPS = float(os.getenv("RPS", "20"))
USERS = ["ana", "luis", "maria", "carlos", "sofia"]
stats = {"ok": 0, "4xx": 0, "5xx": 0, "err": 0}


def pick():
    r = random.random()
    if r < 0.55:
        oid = random.randint(1, 5000) if random.random() > 0.01 else random.randint(900000, 999999)  # 1 % inexistentes (404)
        return "GET", f"/api/orders/{oid}", None
    if r < 0.80:
        return "POST", "/api/checkout", {"customer": f"cliente-{random.randint(1, 500)}", "sku": f"SKU-{random.randint(0, 199):04d}", "qty": 1}
    if r < 0.95:
        return "GET", f"/api/inventory/SKU-{random.randint(0, 199):04d}", None
    u = random.choice(USERS)
    pwd = f"{u}-pass" if random.random() > 0.03 else "typo"  # ~3 % errores humanos de contraseña
    return "POST", "/login", {"username": u, "password": pwd}


async def one(client):
    m, path, body = pick()
    try:
        r = await client.request(m, path, json=body, headers={"x-forwarded-for": f"181.{random.randint(48, 63)}.{random.randint(0, 255)}.{random.randint(1, 254)}"})
        k = "ok" if r.status_code < 400 else ("4xx" if r.status_code < 500 else "5xx")
        stats[k] += 1
    except Exception:
        stats["err"] += 1


async def reporter():
    while True:
        await asyncio.sleep(60)
        print(time.strftime("%H:%M:%S"), stats, flush=True)


async def main():
    async with httpx.AsyncClient(base_url=TARGET, timeout=5, limits=httpx.Limits(max_connections=200)) as client:
        asyncio.create_task(reporter())
        while True:
            asyncio.create_task(one(client))
            await asyncio.sleep(random.expovariate(RPS))


asyncio.run(main())
