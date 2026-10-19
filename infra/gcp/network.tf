# VPC con VPC Flow Logs (Módulo C) y reglas de firewall con logging
resource "google_project_service" "apis" {
  for_each = toset([
    "compute.googleapis.com", "container.googleapis.com", "sqladmin.googleapis.com",
    "servicenetworking.googleapis.com", "monitoring.googleapis.com", "logging.googleapis.com",
    "cloudtrace.googleapis.com", "mesh.googleapis.com", "gkehub.googleapis.com",
    "securitycenter.googleapis.com", "pubsub.googleapis.com",
  ])
  service            = each.value
  disable_on_destroy = false
}

resource "google_compute_network" "vpc" {
  name                    = "vpc-lab-gcp"
  auto_create_subnetworks = false
  depends_on              = [google_project_service.apis]
}

resource "google_compute_subnetwork" "gke" {
  name                     = "snet-gke"
  ip_cidr_range            = "10.20.0.0/20"
  region                   = var.region
  network                  = google_compute_network.vpc.id
  private_ip_google_access = true

  secondary_ip_range {
    range_name    = "pods"
    ip_cidr_range = "10.24.0.0/14"
  }
  secondary_ip_range {
    range_name    = "services"
    ip_cidr_range = "10.28.0.0/20"
  }

  # VPC Flow Logs: intervalo de 5 s, muestreo 50 %, metadatos completos (nombres de VM/pod/servicio)
  log_config {
    aggregation_interval = "INTERVAL_5_SEC"
    flow_sampling        = 0.5
    metadata             = "INCLUDE_ALL_METADATA"
  }
}

# Firewall: solo tráfico E-W permitido explícitamente; deny con logging para detectar tráfico anómalo
resource "google_compute_firewall" "allow_mesh" {
  name      = "fw-allow-mesh-ew"
  network   = google_compute_network.vpc.id
  priority  = 1000
  direction = "INGRESS"
  allow {
    protocol = "tcp"
    ports    = ["8000", "10000", "15000-15090"]
  }
  source_ranges = ["10.20.0.0/20", "10.24.0.0/14", "10.30.0.0/16"]
  log_config { metadata = "INCLUDE_ALL_METADATA" }
}

resource "google_compute_firewall" "deny_all_ingress" {
  name      = "fw-deny-all-ingress"
  network   = google_compute_network.vpc.id
  priority  = 65000
  direction = "INGRESS"
  deny { protocol = "all" }
  source_ranges = ["0.0.0.0/0"]
  log_config { metadata = "INCLUDE_ALL_METADATA" }
}

resource "google_compute_router" "router" {
  name    = "rt-lab"
  region  = var.region
  network = google_compute_network.vpc.id
}

resource "google_compute_router_nat" "nat" {
  name                               = "nat-lab"
  router                             = google_compute_router.router.name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"
  log_config {
    enable = true
    filter = "ERRORS_ONLY"
  }
}

# Acceso privado a Cloud SQL
resource "google_compute_global_address" "psa" {
  name          = "psa-cloudsql"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 20
  network       = google_compute_network.vpc.id
}

resource "google_service_networking_connection" "psa" {
  network                 = google_compute_network.vpc.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.psa.name]
}
