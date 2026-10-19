# Imagen única parametrizada para los 3 microservicios (service-a, service-b, data-service)
FROM python:3.12-slim
ARG SERVICE
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY common/telemetry.py ./telemetry.py
COPY ${SERVICE}/app.py ./app.py
RUN useradd -u 10001 appuser
USER 10001
ENV OTEL_SEMCONV_STABILITY_OPT_IN=http,database \
    PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
