#!/usr/bin/env bash
# Sobe o netauto-lab inteiro num droplet novo (Ubuntu 24.04) em ~15 minutos:
# Docker, containerlab, NetBox, seed, deploy, monitoramento e drift contínuo.
#
# Uso, como root, dentro do clone do repositório:
#   GRAFANA_CLOUD_OTLP_ENDPOINT=https://otlp-gateway-prod-sa-east-1.grafana.net/otlp \
#   GRAFANA_CLOUD_INSTANCE_ID=<instance id> \
#   ./scripts/bootstrap-droplet.sh
# O token do Grafana Cloud é pedido sem aparecer na tela (ou venha em GRAFANA_CLOUD_API_TOKEN).
#
# Tamanho: com menos de 12 GB de RAM usa o lab "mini" (1 spine, 2 leaves), que cabe em
# 2 vCPU / 6 GB. Para forçar: LAB_SIZE=full ou LAB_SIZE=mini.
#
# Segurança: nada fica exposto na internet além do SSH. NetBox e Alloy escutam só em
# 127.0.0.1; os dados saem para o Grafana Cloud por conexão de saída.
set -euo pipefail

LAB_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SECRETS="$LAB_DIR/build/lab.env"
NETBOX_URL="http://localhost:8000"
SRL_PASSWORD="NokiaSrl1!"   # padrão do containerlab; os SR Linux não ficam expostos

log() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
die() { printf '\n\033[1;31mERRO: %s\033[0m\n' "$*" >&2; exit 1; }
wait_for() {  # wait_for <segundos> <descrição> <comando...>
  local timeout=$1 what=$2; shift 2
  local start=$SECONDS
  until "$@" >/dev/null 2>&1; do
    (( SECONDS - start > timeout )) && die "tempo esgotado esperando: $what"
    sleep 10
  done
}

[[ $EUID -eq 0 ]] || die "rode como root (sudo -i)"
[[ -n "${GRAFANA_CLOUD_OTLP_ENDPOINT:-}" ]] || die "defina GRAFANA_CLOUD_OTLP_ENDPOINT"
[[ -n "${GRAFANA_CLOUD_INSTANCE_ID:-}" ]] || die "defina GRAFANA_CLOUD_INSTANCE_ID"
if [[ -z "${GRAFANA_CLOUD_API_TOKEN:-}" ]]; then
  read -rsp "Token do Grafana Cloud (glc_...): " GRAFANA_CLOUD_API_TOKEN; echo
fi
[[ "$GRAFANA_CLOUD_API_TOKEN" == glc_* ]] || die "o token do Grafana Cloud começa com glc_"

MEM_GB=$(( $(awk '/MemTotal/ {print $2}' /proc/meminfo) / 1024 / 1024 ))
if [[ -z "${LAB_SIZE:-}" ]]; then
  if (( MEM_GB < 12 )); then LAB_SIZE=mini; else LAB_SIZE=full; fi
fi
(( MEM_GB >= 5 )) || die "a máquina tem ${MEM_GB} GB; o lab mini precisa de pelo menos 6 GB"
export LAB_SIZE
echo "Memória: ${MEM_GB} GB -> lab ${LAB_SIZE}"

log "1/9 Pacotes, firewall e swap"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq git make jq curl ufw python3-venv python3-pip >/dev/null
ufw allow OpenSSH >/dev/null && ufw --force enable >/dev/null
if ! swapon --show | grep -q /swapfile; then
  fallocate -l 4G /swapfile && chmod 600 /swapfile && mkswap /swapfile >/dev/null && swapon /swapfile
  grep -q /swapfile /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

log "2/9 Docker e containerlab"
command -v docker >/dev/null || curl -fsSL https://get.docker.com | sh >/dev/null
command -v containerlab >/dev/null || bash -c "$(curl -sL https://get.containerlab.dev)" >/dev/null

log "3/9 Python e coleções Ansible"
cd "$LAB_DIR"
make venv >/dev/null
make collections >/dev/null

log "4/9 Fábrica SR Linux (containerlab)"
make lab-up

log "5/9 NetBox"
[[ -d netbox/netbox-docker ]] || git clone -q -b release --depth 1 \
  https://github.com/netbox-community/netbox-docker.git netbox/netbox-docker
cp netbox/docker-compose.override.yml netbox/netbox-docker/
# Na primeira subida as migrations demoram e o healthcheck pode desistir antes: tudo bem
(cd netbox/netbox-docker && docker compose up -d) || true
wait_for 900 "NetBox responder" curl -fsS "$NETBOX_URL/login/"
(cd netbox/netbox-docker && docker compose up -d)

log "6/9 Usuário e token do NetBox"
mkdir -p build && chmod 700 build
if [[ -f "$SECRETS" ]]; then
  echo "Reaproveitando $SECRETS"
else
  NB_PASS="$(openssl rand -base64 24 | tr -d '/+=' | cut -c1-24)"
  (cd netbox/netbox-docker && docker compose exec -T -e DJANGO_SUPERUSER_PASSWORD="$NB_PASS" netbox \
    /opt/netbox/netbox/manage.py createsuperuser --noinput --username admin --email admin@lab.local) >/dev/null
  # v2: o cabeçalho é "Bearer nbt_<key>.<token>"; v1: só o token
  NETBOX_TOKEN="$(curl -fsS -X POST "$NETBOX_URL/api/users/tokens/provision/" \
      -H 'Content-Type: application/json' -H 'Accept: application/json' \
      -d "$(jq -n --arg p "$NB_PASS" '{username:"admin",password:$p,write_enabled:true,description:"netauto-lab"}')" \
    | jq -r 'if .version == 2 then "nbt_\(.key).\(.token)" else .token end')"
  [[ -n "$NETBOX_TOKEN" && "$NETBOX_TOKEN" != null ]] || die "não consegui gerar o token do NetBox"
  umask 077
  cat > "$SECRETS" <<ENV
LAB_SIZE=$LAB_SIZE
NETBOX_URL=$NETBOX_URL
NETBOX_API=$NETBOX_URL
NETBOX_TOKEN=$NETBOX_TOKEN
NETBOX_ADMIN_PASSWORD=$NB_PASS
SRL_PASSWORD=$SRL_PASSWORD
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
ENV
  umask 022
fi
set -a
# shellcheck disable=SC1090
source "$SECRETS"
set +a

log "7/9 Monitoramento (gnmic + Grafana Alloy)"
umask 077
cat > monitoring/.env <<ENV
GRAFANA_CLOUD_OTLP_ENDPOINT=$GRAFANA_CLOUD_OTLP_ENDPOINT
GRAFANA_CLOUD_INSTANCE_ID=$GRAFANA_CLOUD_INSTANCE_ID
GRAFANA_CLOUD_API_TOKEN=$GRAFANA_CLOUD_API_TOKEN
SRL_PASSWORD=$SRL_PASSWORD
ENV
umask 022
make mon-up >/dev/null

log "8/9 Seed do NetBox e deploy na fábrica"
make seed
make render >/dev/null
wait_for 600 "SR Linux responderem via JSON-RPC" make pre
make deploy

log "9/9 Drift contínuo (systemd)"
cat > /etc/systemd/system/netauto-drift.service <<UNIT
[Unit]
Description=netauto-lab: render + drift a cada 5 minutos
After=docker.service
Requires=docker.service

[Service]
WorkingDirectory=$LAB_DIR
EnvironmentFile=$SECRETS
ExecStart=/usr/bin/make drift-watch
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now netauto-drift.service >/dev/null

IP="$(curl -fsS -4 https://ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')"
cat <<DONE

=====================================================================
 netauto-lab no ar.

 Dashboard: Grafana Cloud (dados chegando agora)
 Drift:     systemctl status netauto-drift   |  journalctl -u netauto-drift -f

 NetBox (sem expor na internet), a partir do seu PC:
   ssh -L 8000:localhost:8000 root@$IP
   http://localhost:8000   usuário: admin   senha: em $SECRETS

 Para trabalhar no lab neste servidor:
   cd $LAB_DIR && set -a && source $SECRETS && set +a

 Quando terminar: destrua o droplet no painel da DigitalOcean
 (desligar não para a cobrança).
=====================================================================
DONE
