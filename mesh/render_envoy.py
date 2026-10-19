"""Genera la configuración del sidecar Envoy (service mesh L7 del sandbox) para cada servicio.

Equivalencias en nube:
  - GCP: Cloud Service Mesh (Envoy/Istio gestionado) en GKE -> mismas métricas L7 y fault injection (VirtualService.fault).
  - AWS: App Mesh llegó a fin de soporte el 30-sep-2026 -> se usa ECS Service Connect (también basado en Envoy).

Uso: python mesh/render_envoy.py  (escribe mesh/envoy-<svc>.yaml)
"""
from pathlib import Path

SERVICES = {
    # sidecar: (upstream_app, collector de su nube)
    "service-a": ("service-a:8000", "otel-gcp"),
    "service-b": ("service-b:8000", "otel-aws"),
    "data-service": ("data-service:8000", "otel-gcp"),
}

TEMPLATE = """# Generado por render_envoy.py — sidecar mesh para {svc}
admin:
  address: {{ socket_address: {{ address: 0.0.0.0, port_value: 9901 }} }}
layered_runtime:
  layers:
  - name: static
    static_layer: {{}}
  - name: admin            # permite /runtime_modify (inyección de fallas en caliente)
    admin_layer: {{}}
static_resources:
  listeners:
  - name: ingress
    traffic_direction: INBOUND
    address: {{ socket_address: {{ address: 0.0.0.0, port_value: 10000 }} }}
    filter_chains:
    - filters:
      - name: envoy.filters.network.http_connection_manager
        typed_config:
          "@type": type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager
          stat_prefix: ingress
          generate_request_id: true
          tracing:
            provider:
              name: envoy.tracers.opentelemetry
              typed_config:
                "@type": type.googleapis.com/envoy.config.trace.v3.OpenTelemetryConfig
                grpc_service: {{ envoy_grpc: {{ cluster_name: otel }}, timeout: 1s }}
                service_name: {svc}   # spans del sidecar atribuidos a la carga (igual que istio-proxy)
          access_log:
          - name: envoy.access_loggers.open_telemetry
            typed_config:
              "@type": type.googleapis.com/envoy.extensions.access_loggers.open_telemetry.v3.OpenTelemetryAccessLogConfig
              common_config:
                log_name: mesh_access
                transport_api_version: V3
                grpc_service: {{ envoy_grpc: {{ cluster_name: otel }} }}
              resource_attributes:
                values:
                - {{ key: service.name, value: {{ string_value: mesh-{svc} }} }}
              body: {{ string_value: "%REQ(:METHOD)% %REQ(:PATH)% %RESPONSE_CODE% %RESPONSE_FLAGS% %DURATION%ms" }}
              attributes:
                values:
                - {{ key: event.name, value: {{ string_value: mesh.access }} }}
                - {{ key: http.response.status_code, value: {{ string_value: "%RESPONSE_CODE%" }} }}
                - {{ key: envoy.response_flags, value: {{ string_value: "%RESPONSE_FLAGS%" }} }}
                - {{ key: duration_ms, value: {{ string_value: "%DURATION%" }} }}
                - {{ key: source.address, value: {{ string_value: "%DOWNSTREAM_REMOTE_ADDRESS_WITHOUT_PORT%" }} }}
                - {{ key: destination.service, value: {{ string_value: {svc} }} }}
                - {{ key: traceparent, value: {{ string_value: "%REQ(TRACEPARENT)%" }} }}
          route_config:
            name: local
            virtual_hosts:
            - name: app
              domains: ["*"]
              routes:
              - match: {{ prefix: "/" }}
                route: {{ cluster: local_app, timeout: 3s }}
          http_filters:
          - name: envoy.filters.http.fault
            typed_config:
              "@type": type.googleapis.com/envoy.extensions.filters.http.fault.v3.HTTPFault
              # 0 % por defecto; el experimento activa vía runtime:
              #   fault.http.delay.fixed_delay_percent / fault.http.delay.fixed_duration_ms
              #   fault.http.abort.abort_percent / fault.http.abort.http_status
              delay:
                fixed_delay: 0.2s
                percentage: {{ numerator: 0, denominator: HUNDRED }}
              abort:
                http_status: 503
                percentage: {{ numerator: 0, denominator: HUNDRED }}
          - name: envoy.filters.http.router
            typed_config:
              "@type": type.googleapis.com/envoy.extensions.filters.http.router.v3.Router
  clusters:
  - name: local_app
    type: STRICT_DNS
    connect_timeout: 1s
    load_assignment:
      cluster_name: local_app
      endpoints:
      - lb_endpoints:
        - endpoint: {{ address: {{ socket_address: {{ address: {host}, port_value: {port} }} }} }}
  - name: otel
    type: STRICT_DNS
    connect_timeout: 1s
    typed_extension_protocol_options:
      envoy.extensions.upstreams.http.v3.HttpProtocolOptions:
        "@type": type.googleapis.com/envoy.extensions.upstreams.http.v3.HttpProtocolOptions
        explicit_http_config: {{ http2_protocol_options: {{}} }}
    load_assignment:
      cluster_name: otel
      endpoints:
      - lb_endpoints:
        - endpoint: {{ address: {{ socket_address: {{ address: {collector}, port_value: 4317 }} }} }}
"""

if __name__ == "__main__":
    here = Path(__file__).parent
    for svc, (upstream, collector) in SERVICES.items():
        host, port = upstream.split(":")
        (here / f"envoy-{svc}.yaml").write_text(TEMPLATE.format(svc=svc, host=host, port=port, collector=collector))
        print("ok", svc)
