"""Emulador de VPC Flow Logs (GCP y AWS) para el sandbox — Módulo C.

Fuente: tabla conntrack del kernel (netfilter, con nf_conntrack_acct=1). Los bridges que representan las
VPC tienen bridge-nf-call-iptables=1, por lo que cada conexión entre cargas queda registrada con
paquetes/bytes por sentido — la misma información que agregan los VPC Flow Logs de GCP y AWS.
(Una primera versión capturaba paquetes con AF_PACKET en Python y añadía ~300 ms de cola de latencia:
 se descartó; ver docs/DECISIONES.md.)

Cada 10 s (aggregation interval) se generan:
  * /data/flowlogs/aws-vpc-flow.log   -> formato AWS VPC Flow Logs v5 (campos por espacio)
  * /data/flowlogs/gcp-vpc-flow.jsonl -> jsonPayload de GCP compute.googleapis.com/vpc_flows
  * métricas Prometheus (:9108): vpc_flow_records_total, vpc_flow_bytes_total, vpc_flow_unexpected_total

Clasificación: N-S (internet <-> borde), E-W (intra-nube) y cross-cloud (GCP <-> AWS por interconexión).
Acción REJECT: SYN sin respuesta (UNREPLIED) o respondido con RST (puerto cerrado), análogo a un deny de firewall/SG.
"""
import json
import os
import re
import threading
import time
from collections import defaultdict

from prometheus_client import Counter, Gauge, start_http_server

OUT = os.getenv("OUT_DIR", "/data/flowlogs")
WINDOW = int(os.getenv("WINDOW", "10"))
os.makedirs(OUT, exist_ok=True)

# Inventario IP -> (workload, nube). IPs fijas en docker-compose.yml
INVENTORY = json.loads(open(os.getenv("INVENTORY", "/etc/flowlogs/inventory.json")).read())
IP2W = {ip: (w["name"], w["cloud"]) for w in INVENTORY["workloads"] for ip in w["ips"]}
ALLOWED = {(a, b, int(p)) for a, b, p in INVENTORY["allowed_edges"]}
INFRA = set(INVENTORY["observability_plane"])
SERVER_PORTS = set(INVENTORY["server_ports"])

REC = Counter("vpc_flow_records", "Registros de flow log", ["src_svc", "dst_svc", "direction", "action", "vpc"])
BYTES = Counter("vpc_flow_bytes", "Bytes en flujos", ["src_svc", "dst_svc", "direction", "vpc"])
UNEXP = Counter("vpc_flow_unexpected", "Flujos fuera de la matriz de tráfico permitido", ["src_svc", "dst_svc", "dst_port"])
ACTIVE = Gauge("vpc_flow_active_flows", "Flujos en la última ventana", ["direction"])

flows = defaultdict(lambda: {"packets": 0, "bytes": 0, "start": None, "end": None, "iface": ""})
lock = threading.Lock()


def who(ip):
    return IP2W.get(ip, ("unknown", "internet" if ip.startswith("10.10.") else "unknown"))


CT = os.getenv("CONNTRACK", "/proc/net/nf_conntrack")
KV = re.compile(r"(\w+)=(\S+)")
SUBNETS = tuple(os.getenv("VPC_PREFIXES", "10.10.,10.20.,10.30.").split(","))
seen = {}  # id conexión -> (orig_pkts, orig_bytes, reply_pkts, reply_bytes)


def poll_conntrack():
    """Lee conntrack cada 2 s y acumula deltas por flujo (cliente -> servidor:puerto)."""
    while True:
        now = int(time.time())
        current = set()
        try:
            lines = open(CT).read().splitlines()
        except OSError:
            lines = []
        for ln in lines:
            parts = ln.split()
            if len(parts) < 6 or parts[2] not in ("tcp", "udp"):
                continue
            proto = 6 if parts[2] == "tcp" else 17
            state = parts[5] if proto == 6 else ""
            kv = KV.findall(ln)
            # primer bloque = sentido original; segundo = respuesta
            d = {}
            for k, v in kv:
                d.setdefault(k, []).append(v)
            try:
                src, dst = d["src"][0], d["dst"][0]
                dport = int(d["dport"][0])
                sport = int(d["sport"][0])
            except (KeyError, IndexError):
                continue
            if not (src.startswith(SUBNETS) and dst.startswith(SUBNETS)):
                continue
            op, ob = int(d.get("packets", ["0"])[0]), int(d.get("bytes", ["0"])[0])
            rp, rb = (int(d["packets"][1]), int(d["bytes"][1])) if len(d.get("packets", [])) > 1 else (0, 0)
            cid = (proto, src, dst, sport, dport)
            current.add(cid)
            p_op, p_ob, p_rp, p_rb = seen.get(cid, (0, 0, 0, 0))
            dp, db = (op - p_op) + (rp - p_rp), (ob - p_ob) + (rb - p_rb)
            unreplied = "[UNREPLIED]" in ln
            rejected = unreplied and state == "SYN_SENT" or (state == "CLOSE" and "[ASSURED]" not in ln and op <= 2)
            if cid not in seen or dp > 0:
                with lock:
                    f = flows[(src, dst, dport, proto)]
                    f["packets"] += max(dp, 0)
                    f["bytes"] += max(db, 0)
                    f["start"] = f["start"] or now
                    f["end"] = now
                    f["iface"] = "vpc"
                    if cid not in seen:
                        f["conns"] = f.get("conns", 0) + 1
                        if rejected:
                            f["rejected"] = f.get("rejected", 0) + 1
            seen[cid] = (op, ob, rp, rb)
        for cid in list(seen):
            if cid not in current:
                del seen[cid]
        time.sleep(2)


def direction(sc, dc):
    if "internet" in (sc, dc):
        return "north-south"
    if sc == dc:
        return "east-west"
    return "cross-cloud"


def flush_loop():
    aws = open(os.path.join(OUT, "aws-vpc-flow.log"), "a", buffering=1)
    gcp = open(os.path.join(OUT, "gcp-vpc-flow.jsonl"), "a", buffering=1)
    if aws.tell() == 0:
        aws.write("version account-id interface-id srcaddr dstaddr srcport dstport protocol packets bytes start end action log-status vpc-id flow-direction\n")
    while True:
        time.sleep(WINDOW)
        with lock:
            snap = dict(flows)
            flows.clear()
        counts = defaultdict(int)
        for (src, dst, port, proto), f in snap.items():
            (sw, sc), (dw, dc) = who(src), who(dst)
            d = direction(sc, dc)
            counts[d] += 1
            action = "REJECT" if f.get("rejected", 0) and f.get("rejected", 0) >= f.get("conns", 1) else "ACCEPT"
            vpc = dc if dc in ("gcp", "aws") else sc
            REC.labels(sw, dw, d, action, vpc).inc()
            BYTES.labels(sw, dw, d, vpc).inc(f["bytes"])
            if sw not in INFRA and dw not in INFRA and (sw, dw, port) not in ALLOWED:
                UNEXP.labels(sw, dw, str(port)).inc()
            if vpc == "aws":
                aws.write(f"5 123456789012 eni-lab0001 {src} {dst} 0 {port} {proto} {f['packets']} {f['bytes']} "
                          f"{f['start']} {f['end']} {action} OK vpc-lab-aws ingress\n")
            else:
                gcp.write(json.dumps({
                    "connection": {"src_ip": src, "dest_ip": dst, "dest_port": port, "protocol": proto},
                    "src_instance": {"vm_name": sw}, "dest_instance": {"vm_name": dw},
                    "bytes_sent": f["bytes"], "packets_sent": f["packets"],
                    "start_time": f["start"], "end_time": f["end"], "reporter": "DEST",
                    "src_vpc": {"vpc_name": f"vpc-lab-{sc}"}, "dest_vpc": {"vpc_name": f"vpc-lab-{dc}"},
                    "disposition": "DENIED" if action == "REJECT" else "ALLOWED",
                }) + "\n")
        for d in ("north-south", "east-west", "cross-cloud"):
            ACTIVE.labels(d).set(counts.get(d, 0))


if __name__ == "__main__":
    start_http_server(9108)
    threading.Thread(target=poll_conntrack, daemon=True).start()
    flush_loop()
