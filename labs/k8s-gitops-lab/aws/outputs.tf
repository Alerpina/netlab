output "public_ip" {
  value = aws_instance.k3s.public_ip
}

output "ssh" {
  description = "labsuser.pem é a chave vockey, baixada em AWS Details no Learner Lab"
  value       = "ssh -i ~/.ssh/labsuser.pem ubuntu@${aws_instance.k3s.public_ip}"
}

output "tunel_argocd" {
  description = "Abre o painel do Argo CD em http://localhost:8080 sem expor nada na internet"
  value       = "ssh -i ~/.ssh/labsuser.pem -L 8080:localhost:8080 ubuntu@${aws_instance.k3s.public_ip} 'sudo k3s kubectl -n argocd port-forward svc/argocd-server 8080:80'"
}
