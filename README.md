<h1 align="center">Lorraine Gomes</h1>
<p align="center"><b>DevOps & Infraestrutura</b> · CI/CD · Observabilidade · Automação · Segurança</p>
<p align="center">
  <a href="https://www.linkedin.com/in/lorraine-gomes-barglini-24a084336/"><img src="https://img.shields.io/badge/LinkedIn-Lorraine%20Gomes-0A66C2?logo=linkedin&logoColor=white" alt="LinkedIn"></a>
  <img src="https://img.shields.io/badge/Foz%20do%20Igua%C3%A7u-PR-2B2326" alt="Foz do Iguaçu - PR">
</p>

---

### Sobre mim

Sou engenheira DevOps na **Intelltech IT**, com 4 anos na área e no mercado de TI desde os 17. Atuo de ponta a ponta: escrevo as pipelines, automatizo os servidores, monitoro as aplicações e fecho as brechas de segurança. Hoje cuido de ambientes Windows e Linux para produtos da área da saúde, on-premises e em nuvem.

Curso **Tecnologia em Defesa Cibernética na FIAP** (conclusão em 2027), e por isso trago a segurança para dentro de cada etapa do ciclo DevOps.

### O que eu faço no dia a dia

**🚀 CI/CD**
- Pipelines no **GitHub Actions** para aplicações **.NET/IIS** em vários ambientes (DEV e QA), com escolha de branch e de componente e regras por ambiente.
- Pipelines de produção para **Laravel**, com testes, build de artefato, **backup automático do banco**, modo manutenção, health check e rollback testado.
- Migração de um workflow monolítico para **pipelines isoladas por microsserviço**, uma em cada repositório.
- Gestão de **self-hosted runners** (Linux e Windows) e estudo de migração dos runners para a **OCI**.

**📈 Observabilidade**
- Stack **OpenTelemetry → Grafana Alloy → OTel Collector → Prometheus / Tempo / Loki → Grafana**.
- Dashboards de **RPS, taxa de erro e latência P50/P95/P99** a partir de spanmetrics, métricas de IIS e App Pools, e saúde de **SQL Server** por ambiente.
- Exporter próprio em **PowerShell** para IIS. Otimizei o exporter tirando as consultas WMI de dentro do loop: o número de consultas por coleta caiu cerca de 300 vezes, e o tempo de resposta, que passava de 16 s, ficou quase instantâneo.
- Alertas no **Telegram**.

**🛠️ Infraestrutura como código e automação**
- **Ansible via WinRM** para provisionar servidores Windows: IIS, .NET, SQL Server, Cassandra e RabbitMQ.
- Pipeline que instala agentes de monitoramento em qualquer servidor a partir de um único input.
- Ajuste de desempenho em larga escala: troca do Garbage Collector em **40+ App Pools** e limite de CPU por pool, com backup e comando de rollback.
- **Docker** e **Docker Compose** para ambientes locais e de onboarding.

**🔒 Segurança aplicada**
- **2FA (TOTP)** obrigatório, correção de **IDOR** e **política de senhas** com expiração em uma aplicação em produção.
- Hardening de servidores Linux: firewall, SSH só com chave, remoção de serviços expostos e de chaves órfãs.
- Troca de deploys por SSH com chave guardada no CI por um runner com **privilégio mínimo**, e workers de fila fora do root.
- Agente de consultas SQL com IA **somente leitura**: mascaramento de dados sensíveis, views dedicadas, limite de linhas e auditoria.

### Tecnologias

![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-2088FF?logo=githubactions&logoColor=white)
![Ansible](https://img.shields.io/badge/Ansible-EE0000?logo=ansible&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white)
![Linux](https://img.shields.io/badge/Linux-FCC624?logo=linux&logoColor=black)
![Windows Server](https://img.shields.io/badge/Windows%20Server-0078D6?logo=windows&logoColor=white)
![PowerShell](https://img.shields.io/badge/PowerShell-5391FE?logo=powershell&logoColor=white)
![Grafana](https://img.shields.io/badge/Grafana-F46800?logo=grafana&logoColor=white)
![Prometheus](https://img.shields.io/badge/Prometheus-E6522C?logo=prometheus&logoColor=white)
![OpenTelemetry](https://img.shields.io/badge/OpenTelemetry-425CC7?logo=opentelemetry&logoColor=white)
![Azure](https://img.shields.io/badge/Azure-0078D4?logo=microsoftazure&logoColor=white)
![Oracle Cloud](https://img.shields.io/badge/Oracle%20Cloud-F80000?logo=oracle&logoColor=white)
![DigitalOcean](https://img.shields.io/badge/DigitalOcean-0080FF?logo=digitalocean&logoColor=white)
![Nginx](https://img.shields.io/badge/Nginx-009639?logo=nginx&logoColor=white)
![IIS](https://img.shields.io/badge/IIS-5E5E5E?logo=windows&logoColor=white)
![SQL Server](https://img.shields.io/badge/SQL%20Server-CC2927?logo=microsoftsqlserver&logoColor=white)
![MySQL](https://img.shields.io/badge/MySQL-4479A1?logo=mysql&logoColor=white)
![n8n](https://img.shields.io/badge/n8n-EA4B71?logo=n8n&logoColor=white)

**Estudando agora:** Kubernetes · Terraform · GitOps (Argo CD) · AWS

### Projetos em destaque

> Os projetos da empresa são privados. Aqui ficam estudos de caso escritos e versões de demonstração, sem dados de clientes.

| Projeto | O que mostra |
|---|---|
| [netauto-lab](labs/netauto-lab) | Automação de rede com NetBox como fonte da verdade, Python, Ansible, Robot Framework, drift e GitHub Actions |
| _em breve_ | Pipeline de deploy com backup, manutenção, health check e rollback |
| _em breve_ | Stack de observabilidade com OpenTelemetry e Grafana |
| _em breve_ | Provisionamento de Windows Server com Ansible |
| _em breve_ | Infraestrutura em nuvem com Terraform, Kubernetes e GitOps |

---

<p align="center"><i>Automatizar o que se repete, medir o que importa e proteger desde o primeiro commit.</i></p>
