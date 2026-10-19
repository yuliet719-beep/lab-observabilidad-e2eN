"""Escenario de seguridad (solo sandbox): fuerza bruta N-S, escaneo de puertos E-W y movimiento lateral.

Se ejecuta desde un contenedor no inventariado (10.10.0.66 en 'internet' y 10.20.0.250 dentro de la VPC GCP,
simulando un pod comprometido). Genera las señales de: auth fallida, flujos REJECT y flujos E-W no permitidos.
"""
import os
import random
import socket
import time

import httpx

EDGE = os.getenv("EDGE", "http://10.10.0.20:10000")
SCAN_NET = os.getenv("SCAN_NET", "10.20.0")
DUR = int(os.getenv("BRUTE_SECONDS", "90"))

print("[1] fuerza bruta contra /login", flush=True)
t_end = time.time() + DUR
n = 0
with httpx.Client(base_url=EDGE, timeout=3) as c:
    while time.time() < t_end:
        try:
            c.post("/login", json={"username": random.choice(["admin", "root", "ana", "soporte"]), "password": f"pw{random.randint(0, 99999)}"},
                   headers={"x-forwarded-for": "45.155.205.233"})
        except Exception:
            pass
        n += 1
        time.sleep(1 / 12)
print(f"    {n} intentos", flush=True)

print("[2] escaneo de puertos E-W en la VPC GCP", flush=True)
for host in [20, 21, 30, 31, 40, 50]:
    for port in [22, 80, 443, 3306, 5432, 6379, 8000, 8080, 9000, 9901, 10000]:
        s = socket.socket(); s.settimeout(0.3)
        try:
            s.connect((f"{SCAN_NET}.{host}", port))
        except Exception:
            pass
        finally:
            s.close()
        time.sleep(0.02)

print("[3] movimiento lateral: conexión directa a Cloud SQL y a data-service (bypass del mesh)", flush=True)
for _ in range(10):
    for target in [(f"{SCAN_NET}.40", 5432), (f"{SCAN_NET}.31", 8000)]:
        s = socket.socket(); s.settimeout(1)
        try:
            s.connect(target); s.send(b"\x00\x00\x00\x08\x04\xd2\x16\x2f")
        except Exception:
            pass
        finally:
            s.close()
    time.sleep(1)
print("fin", flush=True)
