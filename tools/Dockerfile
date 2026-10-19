# Imagen de utilidades del laboratorio: correlador AIOps, flow logs, exportador CVE, carga, caos
FROM python:3.12-slim
WORKDIR /app
COPY tools/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY aiops/correlator/app.py ./correlator.py
COPY network/flowlogs/flowlogs.py security/scanner/exporter.py loadgen/loadgen.py chaos/intruder.py chaos/run_experiments.py ./
ENV PYTHONUNBUFFERED=1
