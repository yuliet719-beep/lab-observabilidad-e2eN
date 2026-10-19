variable "region" {
  type    = string
  default = "us-east-1"
}
variable "service_b_image" {
  type    = string
  default = "docker.io/yulietrojas/service-b:1.0"
}
variable "slo_latency_threshold_ms" {
  type    = number
  default = 300
}
variable "alarm_email" {
  type    = string
  default = "equipo-sre@example.com"
}
variable "db_password" {
  type      = string
  sensitive = true
}
