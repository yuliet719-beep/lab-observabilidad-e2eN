variable "project_id" {
  type        = string
  description = "ID del proyecto GCP (sandbox dedicado: los experimentos de caos nunca corren en recursos compartidos)"
}
variable "region" {
  type    = string
  default = "us-east1"
}
variable "slo_latency_threshold_s" {
  type        = number
  default     = 0.3
  description = "SLO_threshold de latencia p99 (s) usado por la regla de correlación"
}
variable "notification_email" {
  type    = string
  default = "equipo-sre@example.com"
}
variable "db_password" {
  type      = string
  sensitive = true
}
