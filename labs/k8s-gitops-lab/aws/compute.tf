# Data source: consulta algo que já existe (não cria). Aqui, a AMI Ubuntu 24.04 mais nova.
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }
}

# Key pair criado pelo Terraform a partir da SUA chave pública: a privada nunca sai do seu PC
resource "aws_key_pair" "lab" {
  key_name   = "netlab-k3s"
  public_key = file(pathexpand(var.ssh_public_key_path))
}

resource "aws_instance" "k3s" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.k3s.id]
  key_name               = aws_key_pair.lab.key_name
  iam_instance_profile   = var.instance_profile != "" ? var.instance_profile : null

  root_block_device {
    volume_type = "gp3"
    volume_size = 20
    encrypted   = true
  }

  # Só IMDSv2 (token): protege as credenciais da instância contra SSRF
  metadata_options {
    http_tokens = "required"
  }

  # Bootstrap: Terraform cria a máquina, o cloud-init instala k3s + Argo CD + a Application
  user_data = templatefile("${path.module}/user_data.sh.tftpl", {
    k3s_version    = var.k3s_version
    argocd_version = var.argocd_version
    git_repo_url   = var.git_repo_url
  })
  user_data_replace_on_change = true

  tags = { Name = "netlab-k3s" }
}
