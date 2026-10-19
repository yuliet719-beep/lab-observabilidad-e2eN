output "gke_cluster" { value = google_container_cluster.gke.name }
output "cloudsql_private_ip" { value = google_sql_database_instance.orders.private_ip_address }
output "flow_logs_query" {
  value = "logName=\"projects/${var.project_id}/logs/compute.googleapis.com%2Fvpc_flows\""
}
