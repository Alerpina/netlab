variable "cluster_name" {
  description = "Nome do cluster kind (o contexto do kubectl vira kind-<nome>)"
  type        = string
  default     = "gitops"
}

variable "argocd_chart_version" {
  description = "Versão do chart argo-cd (argoproj/argo-helm)"
  type        = string
  default     = "10.20.0"
}

variable "git_repo_url" {
  description = "Repositório que o Argo CD observa (fonte da verdade)"
  type        = string
  default     = "https://github.com/Alerpina/netlab.git"
}

variable "git_revision" {
  description = "Branch que o Argo CD acompanha"
  type        = string
  default     = "main"
}
