# Terraform instala a plataforma (Argo CD); o Argo CD instala as aplicações a partir do Git.
# Cada um cuida de uma camada: IaC para a infraestrutura, GitOps para o que roda nela.

resource "helm_release" "argocd" {
  name             = "argocd"
  repository       = "https://argoproj.github.io/argo-helm"
  chart            = "argo-cd"
  version          = var.argocd_chart_version
  namespace        = "argocd"
  create_namespace = true
  wait             = true
  timeout          = 600

  # Enxuto para caber no notebook: sem Dex (SSO) e sem notificações
  values = [yamlencode({
    dex           = { enabled = false }
    notifications = { enabled = false }
    configs = {
      params = { "server.insecure" = true } # acesso só por port-forward local
    }
  })]
}

# Application do Argo CD criada por um chart, para não depender do CRD no momento do plan
resource "helm_release" "apps" {
  name       = "argocd-apps"
  repository = "https://argoproj.github.io/argo-helm"
  chart      = "argocd-apps"
  version    = "2.0.10"
  namespace  = "argocd"
  depends_on = [helm_release.argocd]

  values = [yamlencode({
    applications = {
      podinfo = {
        namespace = "argocd"
        project   = "default"
        source = {
          repoURL        = var.git_repo_url
          targetRevision = var.git_revision
          path           = "labs/k8s-gitops-lab/apps/podinfo"
        }
        destination = {
          server    = "https://kubernetes.default.svc"
          namespace = "demo"
        }
        syncPolicy = {
          automated   = { prune = true, selfHeal = true } # self-heal: desfaz mudança manual (drift)
          syncOptions = ["CreateNamespace=true"]
        }
      }
    }
  })]
}

output "proximos_passos" {
  value = <<-EOT
    kubectl -n argocd get pods
    kubectl -n demo get pods
    Senha do admin: kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d; echo
    Painel: kubectl -n argocd port-forward svc/argocd-server 8080:80  ->  http://localhost:8080
  EOT
}
