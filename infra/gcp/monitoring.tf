# ---------- AIOps (Módulo B) ----------
# Las reglas de grabación (SLI y líneas base ±2σ) se despliegan en GKE como GMP Rules
# (infra/k8s/gmp-rules.yaml, generadas desde observability/prometheus/rules). Las políticas
# de Cloud Monitoring consultan esas series con PromQL.

resource "google_monitoring_notification_channel" "email" {
  display_name = "SRE lab"
  type         = "email"
  labels       = { email_address = var.notification_email }
}

resource "google_monitoring_alert_policy" "correlated" {
  display_name = "AIOps - error_rate > baseline+2σ Y p99 > SLO (correlada)"
  combiner     = "OR"
  severity     = "CRITICAL"
  conditions {
    display_name = "error ratio anómalo correlacionado con latencia"
    condition_prometheus_query_language {
      query               = <<-PROMQL
        (sli:error_ratio:rate1m > on(service_name) aiops:error_ratio:band_upper)
        and on(service_name)
        (sli:latency_p99:1m > ${var.slo_latency_threshold_s})
      PROMQL
      duration            = "30s"
      evaluation_interval = "30s"
      labels              = { pipeline = "aiops", severity = "page" }
    }
  }
  alert_strategy {
    auto_close           = "1800s"
    notification_prompts = ["OPENED", "CLOSED"]
  }
  documentation {
    mime_type = "text/markdown"
    subject   = "[$${policy.display_name}] $${metric.label.service_name}"
    content   = "El correlador AIOps añade trace_id del request fallido y la causa raíz candidata. Runbook: docs/RUNBOOK.md#correlated"
  }
  notification_channels = [google_monitoring_notification_channel.email.id]
}

resource "google_monitoring_alert_policy" "latency_anomaly" {
  display_name = "AIOps - p99 fuera de banda y sobre SLO"
  combiner     = "OR"
  severity     = "ERROR"
  conditions {
    display_name = "latencia anómala"
    condition_prometheus_query_language {
      query               = <<-PROMQL
        (sli:latency_p99:1m > on(service_name) aiops:latency_p99:band_upper)
        and on(service_name) (sli:latency_p99:1m > ${var.slo_latency_threshold_s})
        and on(service_name) (sli:latency_good_ratio:rate1m < 0.99)
      PROMQL
      duration            = "30s"
      evaluation_interval = "30s"
    }
  }
  notification_channels = [google_monitoring_notification_channel.email.id]
}

# Detección de anomalías nativa sobre data-service: pronóstico (forecast) de saturación de conexiones Cloud SQL
resource "google_monitoring_alert_policy" "cloudsql_forecast" {
  display_name = "Anomaly/Forecast - conexiones Cloud SQL (data-service)"
  combiner     = "OR"
  conditions {
    display_name = "conexiones Postgres pronosticadas > 80"
    condition_threshold {
      filter          = "resource.type = \"cloudsql_database\" AND metric.type = \"cloudsql.googleapis.com/database/postgresql/num_backends\""
      comparison      = "COMPARISON_GT"
      threshold_value = 80
      duration        = "0s"
      forecast_options { forecast_horizon = "3600s" }
      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }
  notification_channels = [google_monitoring_notification_channel.email.id]
}

# ---------- Network & Security (Módulo C) ----------
resource "google_logging_metric" "auth_failures" {
  name   = "security/auth_failures"
  filter = "resource.type=\"k8s_container\" AND (jsonPayload.\"event.name\"=\"auth.failure\" OR textPayload:\"security.auth.failure\")"
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }
}

resource "google_logging_metric" "firewall_denied" {
  name   = "network/firewall_denied"
  filter = "logName=\"projects/${var.project_id}/logs/compute.googleapis.com%2Ffirewall\" AND jsonPayload.disposition=\"DENIED\""
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    labels {
      key        = "dest_port"
      value_type = "STRING"
    }
  }
  label_extractors = { dest_port = "EXTRACT(jsonPayload.connection.dest_port)" }
}

# Flujo E-W no permitido: alguien distinto de data-service hablando con Cloud SQL (5432)
resource "google_logging_metric" "unexpected_db_flows" {
  name   = "network/unexpected_db_flows"
  filter = <<-EOT
    logName="projects/${var.project_id}/logs/compute.googleapis.com%2Fvpc_flows"
    AND jsonPayload.connection.dest_port=5432
    AND NOT jsonPayload.src_gke_details.pod.pod_workload.workload_name="data-service"
  EOT
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }
}

resource "google_logging_metric" "flow_bytes" {
  name   = "network/flow_bytes"
  filter = "logName=\"projects/${var.project_id}/logs/compute.googleapis.com%2Fvpc_flows\""
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "DISTRIBUTION"
    labels {
      key        = "direction"
      value_type = "STRING"
    }
  }
  value_extractor  = "EXTRACT(jsonPayload.bytes_sent)"
  label_extractors = { direction = "EXTRACT(jsonPayload.reporter)" }
  bucket_options {
    exponential_buckets {
      num_finite_buckets = 32
      growth_factor      = 2
      scale              = 1
    }
  }
}

resource "google_monitoring_alert_policy" "security" {
  display_name = "Seguridad - fuerza bruta / tráfico E-W anómalo"
  combiner     = "OR"
  severity     = "CRITICAL"
  conditions {
    display_name = "auth fallida > 0.5/s"
    condition_threshold {
      filter          = "metric.type=\"logging.googleapis.com/user/${google_logging_metric.auth_failures.name}\" AND resource.type=\"k8s_container\""
      comparison      = "COMPARISON_GT"
      threshold_value = 30
      duration        = "60s"
      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_SUM"
        cross_series_reducer = "REDUCE_SUM"
      }
    }
  }
  conditions {
    display_name = "flujos no permitidos hacia Cloud SQL"
    condition_threshold {
      filter          = "metric.type=\"logging.googleapis.com/user/${google_logging_metric.unexpected_db_flows.name}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "0s"
      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_SUM"
        cross_series_reducer = "REDUCE_SUM"
      }
    }
  }
  notification_channels = [google_monitoring_notification_channel.email.id]
}

resource "google_monitoring_dashboard" "security_golden_signals" {
  dashboard_json = file("${path.module}/dashboards/golden-signals-seguridad.json")
}
