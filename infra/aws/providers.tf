terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 6.69" }
  }
}

provider "aws" {
  region = var.region
  default_tags { tags = { project = "lab-observabilidad-e2e", environment = "sandbox" } }
}

data "aws_caller_identity" "me" {}
data "aws_availability_zones" "az" { state = "available" }
