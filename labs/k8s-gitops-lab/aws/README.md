# k8s-gitops-lab na AWS (AWS Academy Learner Lab)

Terraform cria a rede e uma EC2; no primeiro boot, a EC2 instala **k3s** (Kubernetes leve), o **Argo CD** e a Application que faz o deploy do `podinfo` a partir deste repositório.

```mermaid
flowchart LR
    TF[Terraform no WSL] -- API da AWS --> VPC
    subgraph VPC[VPC 10.42.0.0/16]
      SUB[Subnet pública 10.42.1.0/24]
      SG[Security group: SSH só do seu IP]
      EC2[EC2 t3.medium<br/>k3s + Argo CD]
    end
    IGW[Internet Gateway] --- VPC
    GIT[(GitHub)] -- Argo CD sincroniza --> EC2
    YOU[Você] -- SSH + túnel --> EC2
```

Custo: t3.medium ~US$ 0,04/h, mais o disco de 20 GB. **Rode `terraform destroy` no fim.**

---

## Passo 0. Credenciais do Learner Lab

1. No AWS Academy: **Modules > Learner Lab > Start Lab**. Espere a bolinha ficar verde.
2. **AWS Details > AWS CLI: Show**. Copie o bloco `[default]` para `~/.aws/credentials` no WSL:
   ```bash
   mkdir -p ~/.aws && nano ~/.aws/credentials     # cole o bloco inteiro e salve
   chmod 600 ~/.aws/credentials
   ```
3. **AWS Details > Download PEM** (é a chave `vockey`). Mova para o WSL:
   ```bash
   cp /mnt/c/Users/lorraine/Downloads/labsuser.pem ~/.ssh/ && chmod 600 ~/.ssh/labsuser.pem
   ```

> **Entrevista:** "As credenciais são temporárias (têm session token) e vêm de uma role; na empresa o ideal é o mesmo: nada de chave de acesso fixa, e sim SSO ou OIDC do GitHub Actions assumindo uma role com o mínimo de permissão."

As credenciais expiram quando a sessão do lab acaba (~4 h). Se o Terraform disser `ExpiredToken`, copie de novo.

---

## Passo 1. Variáveis e `init`

```bash
cd ~/portfolio-devops/labs/k8s-gitops-lab/aws
cp terraform.tfvars.example terraform.tfvars
sed -i "s|203.0.113.10/32|$(curl -s ifconfig.me)/32|" terraform.tfvars
cat terraform.tfvars
terraform init
```

**O que acontece:** o `init` baixa o **provider** da AWS (o plugin que traduz o código em chamadas de API) e cria a pasta `.terraform/`. O `.terraform.lock.hcl` fixa a versão exata do provider.

| Conceito | Onde está | O que é |
|---|---|---|
| **provider** | `versions.tf` | plugin que fala com a API (aws, helm, kubernetes...) |
| **variable** | `variables.tf` | entrada; tem tipo, default e **validação** (veja o `my_ip_cidr`) |
| **tfvars** | `terraform.tfvars` | valores das variáveis desta execução (fora do Git) |
| **default_tags** | `versions.tf` | tag em tudo: saber de quem é e quanto custa |

---

## Passo 2. `plan`: ler antes de mudar

```bash
terraform plan
```

Leia a saída: `+ create` em cada recurso, e o resumo `Plan: 9 to add, 0 to change, 0 to destroy`.

| Recurso | Para que serve |
|---|---|
| `aws_vpc` | rede isolada do lab (10.42.0.0/16) |
| `aws_internet_gateway` | saída para a internet |
| `aws_subnet` (pública) | onde a EC2 fica; pública porque a rota padrão vai para o IGW |
| `aws_route_table` + association | a rota `0.0.0.0/0 -> IGW` |
| `aws_security_group` + regras | firewall **stateful**: entra só SSH do seu IP; a saída é livre |
| `aws_instance` | a EC2 com k3s |
| `data.aws_ami` | **data source**: consulta a AMI Ubuntu mais nova, não cria nada |

> **Entrevista:** "O Terraform monta um grafo de dependências pelas referências: a subnet usa `aws_vpc.lab.id`, então a VPC é criada antes. O `plan` mostra exatamente o que vai mudar; no time, ele roda no PR e alguém revisa antes do `apply`."

---

## Passo 3. `apply`

```bash
terraform apply        # digite yes
terraform output
```

Leva ~1 minuto para criar a infraestrutura. O cloud-init dentro da EC2 ainda leva **~5 minutos** instalando k3s e Argo CD.

Agora existe o **state** (`terraform.tfstate`): a memória do Terraform, que liga cada recurso do código ao ID real na AWS.

```bash
terraform state list
terraform state show aws_instance.k3s | head -20
```

> **Entrevista:** "O state é a fonte de verdade do Terraform sobre o que ele gerencia. Em equipe ele fica num backend remoto (S3 com lock), nunca no Git, porque pode ter dado sensível. Se alguém muda algo na mão pelo console, o próximo `plan` mostra o drift."

---

## Passo 4. Entrar na EC2 e ver o Kubernetes

```bash
$(terraform output -raw ssh)                       # entra na EC2
sudo tail -f /var/log/netlab-bootstrap.log         # espere "BOOTSTRAP OK" e saia com Ctrl+C
kubectl get nodes
kubectl get pods -A
kubectl -n demo get pods,svc
```

| Objeto | O que você vê |
|---|---|
| **Node** | a EC2 como nó do cluster |
| **Namespace** | `argocd`, `demo`, `kube-system`: separação lógica |
| **Pod** | os containers rodando (2 do podinfo) |
| **Deployment** | mantém as 2 réplicas e faz rolling update |
| **Service** | endereço fixo (ClusterIP) na frente dos pods |

> **Entrevista:** "k3s é um Kubernetes certificado e leve. Em produção na AWS eu usaria o EKS: a AWS gerencia o control plane e eu cuido dos nós (managed node groups ou Karpenter). Os objetos e o kubectl são os mesmos."

---

## Passo 5. Argo CD e GitOps

Num terminal **novo** no WSL:

```bash
cd ~/portfolio-devops/labs/k8s-gitops-lab/aws
eval "$(terraform output -raw tunel_argocd)"
```

Abra http://localhost:8080. Usuário `admin`; senha (na EC2):

```bash
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d; echo
```

Agora faça os exercícios do [README do lab](../README.md): réplicas pelo Git, self-heal (`kubectl -n demo scale deploy podinfo --replicas=1`), ImagePullBackOff e rollback com `git revert`.

> **Entrevista:** "Repare que nem a API do Kubernetes nem o Argo CD estão expostos: o security group só libera SSH do meu IP e eu acesso por túnel. Na produção seria Ingress com TLS e SSO, ou acesso via VPN ou SSM."

---

## Passo 6. Ver drift do Terraform (2 minutos)

No console da AWS, em **EC2 > Instances > netlab-k3s > Tags**, adicione uma tag `Teste=manual`. Depois:

```bash
terraform plan
```

O plano mostra a tag a remover: é o Terraform detectando mudança feita fora do código. `terraform apply` volta ao estado declarado.

---

## Passo 7. Destruir (sempre)

```bash
terraform destroy      # digite yes
```

> **Entrevista (FinOps):** "Ambiente de estudo e de teste se destrói quando não está em uso; com IaC, recriar leva minutos. Fora isso: tags para atribuir custo, rightsizing, desligar ambientes ociosos fora do horário, spot para cargas tolerantes e reservas ou savings plans para a base fixa."

---

## Problemas comuns

| Erro | Causa | Solução |
|---|---|---|
| `ExpiredToken` / `InvalidClientTokenId` | sessão do Learner Lab expirou | **Start Lab** e copie as credenciais de novo |
| `UnauthorizedOperation` em `iam:...` | o Learner Lab bloqueia criar IAM | o código já usa o `LabInstanceProfile` pronto |
| SSH com timeout | seu IP mudou | atualize `terraform.tfvars` e rode `terraform apply` |
| `kubectl` sem pods do podinfo | o bootstrap ainda está rodando | acompanhe `/var/log/netlab-bootstrap.log` |
