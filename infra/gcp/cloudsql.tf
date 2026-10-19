# Cloud SQL for PostgreSQL 16 (base "orders" de data-service) con Query Insights
resource "google_sql_database_instance" "orders" {
  name                = "cloudsql-orders"
  database_version    = "POSTGRES_16"
  region              = var.region
  deletion_protection = false

  settings {
    tier              = "db-custom-1-3840"
    edition           = "ENTERPRISE"
    availability_type = "ZONAL"

    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.vpc.id
    }

    insights_config {
      query_insights_enabled  = true
      query_string_length     = 1024
      record_application_tags = true # lee los comentarios sqlcommenter (traceparent) de OTel
      record_client_address   = true
    }

    database_flags {
      name  = "log_min_duration_statement"
      value = "250"
    }
    database_flags {
      name  = "cloudsql.enable_pgaudit"
      value = "on"
    }
  }
  depends_on = [google_service_networking_connection.psa]
}

resource "google_sql_database" "orders" {
  name     = "orders"
  instance = google_sql_database_instance.orders.name
}

resource "google_sql_user" "app" {
  name     = "app"
  instance = google_sql_database_instance.orders.name
  password = var.db_password
}
