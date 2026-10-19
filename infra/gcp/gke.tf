# GKE Autopilot + Cloud Service Mesh gestionado (observabilidad L7: métricas, trazas y fault injection)
resource "google_container_cluster" "gke" {
  name                = "gke-lab-e2e"
  location            = var.region
  enable_autopilot    = true
  network             = google_compute_network.vpc.id
  subnetwork          = google_compute_subnetwork.gke.id
  deletion_protection = false

  ip_allocation_policy {
    cluster_secondary_range_name  = "pods"
    services_secondary_range_name = "services"
  }

  private_cluster_config {
    enable_private_nodes    = true
    enable_private_endpoint = false
    master_ipv4_cidr_block  = "172.16.0.0/28"
  }

  fleet { project = var.project_id }

  monitoring_config {
    enable_components = ["SYSTEM_COMPONENTS", "APISERVER", "SCHEDULER", "CONTROLLER_MANAGER"]
    managed_prometheus { enabled = true }
  }

  logging_config {
    enable_components = ["SYSTEM_COMPONENTS", "WORKLOADS"]
  }

  depends_on = [google_project_service.apis]
}

resource "google_gke_hub_feature" "mesh" {
  name     = "servicemesh"
  location = "global"
  fleet_default_member_config {
    mesh { management = "MANAGEMENT_AUTOMATIC" }
  }
  depends_on = [google_project_service.apis]
}
