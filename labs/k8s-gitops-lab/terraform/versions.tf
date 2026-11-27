terraform {
  required_version = ">= 1.6"
  required_providers {
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.17"
    }
  }
  # Lab local: o state fica na máquina. Em produção ele iria para um backend remoto
  # com lock (S3 + DynamoDB na AWS, Object Storage na OCI), nunca para o Git.
}

provider "helm" {
  kubernetes {
    config_path    = pathexpand("~/.kube/config")
    config_context = "kind-${var.cluster_name}"
  }
}
