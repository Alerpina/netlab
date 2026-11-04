#!/usr/bin/env bash
# Sobe o NetBox local com o netbox-docker (projeto oficial da comunidade).
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d netbox-docker ]; then
  git clone -b release --depth 1 https://github.com/netbox-community/netbox-docker.git
fi
cp docker-compose.override.yml netbox-docker/

cd netbox-docker
docker compose pull
docker compose up -d

echo
echo "NetBox subindo em http://localhost:8000 (a primeira subida leva alguns minutos)."
echo "1) Crie o usuário admin:"
echo "   docker compose -f netbox/netbox-docker/docker-compose.yml exec netbox /opt/netbox/netbox/manage.py createsuperuser"
echo "2) Gere um token em Admin > API Tokens e exporte:"
echo "   export NETBOX_TOKEN=<token>"
