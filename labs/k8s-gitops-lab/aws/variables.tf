variable "region" {
  description = "Região AWS (conta própria: us-east-2 Ohio; AWS Academy Learner Lab: us-east-1)"
  type        = string
  default     = "us-east-2"
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

variable "ssh_public_key_path" {
  description = "Chave pública que o Terraform cadastra na AWS como key pair"
  type        = string
  default     = "~/.ssh/netlab.pub"
}

variable "ssh_private_key_path" {
  description = "Chave privada correspondente (só usada para montar o comando de SSH no output)"
  type        = string
  default     = "~/.ssh/netlab"
}

variable "instance_profile" {
  description = "Instance profile da EC2. Vazio = sem role (o lab não precisa). No AWS Academy, use LabInstanceProfile"
  type        = string
  default     = ""
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
