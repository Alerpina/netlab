terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
  # State local porque o Learner Lab é descartável. Em produção:
  # backend "s3" { bucket = "...", key = "netlab/terraform.tfstate", region = "us-east-1", use_lockfile = true }
}

provider "aws" {
  region = var.region

  # Tags em tudo que o Terraform criar: saber de quem é e quanto custa (FinOps)
  default_tags {
    tags = {
      Project   = "netlab"
      Lab       = "k8s-gitops"
      ManagedBy = "terraform"
      Owner     = var.owner
    }
  }
}
