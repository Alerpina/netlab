# Rede própria do lab: nada compartilhado com a VPC padrão da conta.

resource "aws_vpc" "lab" {
  cidr_block           = "10.42.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = { Name = "netlab-vpc" }
}

# Porta de saída para a internet (baixar imagens, falar com o GitHub)
resource "aws_internet_gateway" "lab" {
  vpc_id = aws_vpc.lab.id
  tags   = { Name = "netlab-igw" }
}

# Subnet pública: a rota padrão vai para o internet gateway
resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.lab.id
  cidr_block              = "10.42.1.0/24"
  availability_zone       = "${var.region}a"
  map_public_ip_on_launch = true
  tags                    = { Name = "netlab-public" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.lab.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.lab.id
  }

  tags = { Name = "netlab-public-rt" }
}

resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

# Security group = firewall da instância (stateful: a resposta volta sozinha)
resource "aws_security_group" "k3s" {
  name        = "netlab-k3s"
  description = "SSH so do meu IP; API do Kubernetes e Argo CD nao ficam expostos"
  vpc_id      = aws_vpc.lab.id
  tags        = { Name = "netlab-k3s-sg" }
}

resource "aws_vpc_security_group_ingress_rule" "ssh_from_me" {
  security_group_id = aws_security_group.k3s.id
  description       = "SSH do meu IP"
  cidr_ipv4         = var.my_ip_cidr
  ip_protocol       = "tcp"
  from_port         = 22
  to_port           = 22
}

resource "aws_vpc_security_group_egress_rule" "all_out" {
  security_group_id = aws_security_group.k3s.id
  description       = "Saida liberada (imagens, GitHub, pacotes)"
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}
