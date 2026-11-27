variable "region" {
  description = "Região AWS (o AWS Academy Learner Lab usa us-east-1)"
  type        = string
  default     = "us-east-1"
}

variable "owner" {
  description = "Dono dos recursos (vai nas tags)"
  type        = string
  default     = "lorraine"
}

variable "my_ip_cidr" {
  description = "Seu IP público em /32: só ele pode fazer SSH. Descubra com: curl -s ifconfig.me"
  type        = string

  validation {
    condition     = can(cidrhost(var.my_ip_cidr, 0)) && endswith(var.my_ip_cidr, "/32")
    error_message = "Use um único IP no formato x.x.x.x/32."
  }
}

variable "instance_type" {
  description = "t3.medium (2 vCPU, 4 GB): suficiente para k3s + Argo CD"
  type        = string
  default     = "t3.medium"
}

variable "key_name" {
  description = "Par de chaves para SSH (no Learner Lab já existe o vockey)"
  type        = string
  default     = "vockey"
}

variable "instance_profile" {
  description = "Instance profile da EC2. O Learner Lab não deixa criar roles; usa o LabInstanceProfile pronto"
  type        = string
  default     = "LabInstanceProfile"
}

variable "git_repo_url" {
  description = "Repositório que o Argo CD observa"
  type        = string
  default     = "https://github.com/Alerpina/netlab.git"
}

variable "argocd_version" {
  description = "Versão do Argo CD"
  type        = string
  default     = "v3.6.3"
}

variable "k3s_version" {
  description = "Versão do k3s (Kubernetes leve)"
  type        = string
  default     = "v1.37.2+k3s1"
}
