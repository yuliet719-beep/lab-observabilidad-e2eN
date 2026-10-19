"""Inicialización OpenTelemetry común (3 pilares) para los microservicios del LAB.

- Trazas: OTLP/gRPC -> collector de la nube donde corre el servicio (otel-gcp / otel-aws).
- Métricas: OTLP/gRPC, histograma http.server.request.duration con buckets alineados al SLO (250 ms).
- Logs: handler de logging estándar -> OTLP (correlación automática trace_id/span_id).
- DB: psycopg instrumentado con las convenciones semánticas estables de base de datos
  (OTEL_SEMCONV_STABILITY_OPT_IN=database -> db.system.name, db.namespace, db.query.text,
  db.operation.name, db.collection.name, error.type).
"""
import logging
import os

from opentelemetry import metrics, trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.metrics.view import ExplicitBucketHistogramAggregation, View
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# Buckets en segundos: 0.3 coincide con el umbral del SLO de latencia (p99 < 300 ms)
SLO_BUCKETS = [0.01, 0.025, 0.05, 0.075, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5, 0.75, 1.0, 2.0, 5.0]


def setup_telemetry(service_name: str) -> logging.Logger:
    resource = Resource.create(
        {
            "service.name": service_name,
            "service.namespace": "lab-e2e",
            "service.version": os.getenv("SERVICE_VERSION", "1.0.0"),
            "deployment.environment.name": os.getenv("DEPLOY_ENV", "sandbox"),
            "cloud.provider": os.getenv("CLOUD_PROVIDER", "gcp"),
            "cloud.platform": os.getenv("CLOUD_PLATFORM", "gcp_kubernetes_engine"),
            "cloud.region": os.getenv("CLOUD_REGION", "us-east1"),
        }
    )
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-gcp:4317")

    tp = TracerProvider(resource=resource)
    tp.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True), schedule_delay_millis=1000))
    trace.set_tracer_provider(tp)

    reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=endpoint, insecure=True), export_interval_millis=5000
    )
    views = [
        View(instrument_name="http.server.request.duration", aggregation=ExplicitBucketHistogramAggregation(SLO_BUCKETS)),
        View(instrument_name="http.client.request.duration", aggregation=ExplicitBucketHistogramAggregation(SLO_BUCKETS)),
        View(instrument_name="db.client.operation.duration", aggregation=ExplicitBucketHistogramAggregation(SLO_BUCKETS)),
    ]
    metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=[reader], views=views))

    lp = LoggerProvider(resource=resource)
    lp.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter(endpoint=endpoint, insecure=True), schedule_delay_millis=1000))
    set_logger_provider(lp)

    logger = logging.getLogger(service_name)
    logger.setLevel(logging.INFO)
    logger.addHandler(LoggingHandler(level=logging.INFO, logger_provider=lp))
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logger.addHandler(console)
    return logger


def instrument_app(app, with_httpx: bool = True, with_psycopg: bool = False):
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    FastAPIInstrumentor.instrument_app(app, excluded_urls="health,metrics,admin")
    if with_httpx:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        HTTPXClientInstrumentor().instrument()
    if with_psycopg:
        from opentelemetry.instrumentation.psycopg import PsycopgInstrumentor

        PsycopgInstrumentor().instrument(enable_commenter=True)
