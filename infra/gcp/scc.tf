# Security Command Center (tier Standard, activación a nivel de proyecto).
# Los hallazgos ACTIVE de severidad HIGH/CRITICAL se publican en Pub/Sub para integrarlos con el pipeline AIOps.
resource "google_pubsub_topic" "scc_findings" {
  name = "scc-findings"
}

resource "google_scc_v2_project_notification_config" "high" {
  config_id    = "scc-high-findings"
  project      = var.project_id
  location     = "global"
  description  = "Hallazgos activos HIGH/CRITICAL -> pipeline AIOps"
  pubsub_topic = google_pubsub_topic.scc_findings.id
  streaming_config {
    filter = "state=\"ACTIVE\" AND (severity=\"HIGH\" OR severity=\"CRITICAL\")"
  }
  depends_on = [google_project_service.apis]
}
