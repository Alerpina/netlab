#!/usr/bin/env bash
# Endurece o droplet do lab: só SSH (com chave) entra; o resto fica fechado.
#
#   - SSH: só chave, sem senha, poucas tentativas, só root (que já usa chave)
#   - Firewall (ufw): nega toda entrada, exceto SSH com limite de taxa
#   - Docker: bloqueia acesso externo direto aos containers (o Docker ignora o ufw)
#   - fail2ban: bane IPs que erram o SSH várias vezes
#   - Atualizações de segurança automáticas
#   - Desliga serviços de rede que o lab não usa
#
# Uso (como root, dentro do clone):  ./scripts/harden-droplet.sh
# Não derruba a sessão atual. Teste um SSH novo em outro terminal antes de fechar este.
set -euo pipefail

log() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
die() { printf '\n\033[1;31mERRO: %s\033[0m\n' "$*" >&2; exit 1; }
[[ $EUID -eq 0 ]] || die "rode como root"
export DEBIAN_FRONTEND=noninteractive
# Não deixa o apt reiniciar serviços sozinho: um restart do Docker derrubaria os switches do lab
export NEEDRESTART_MODE=l

PUBLIC_IF="$(ip route show default | awk '{print $5; exit}')"
[[ -n "$PUBLIC_IF" ]] || die "não achei a interface pública"

log "1/6 SSH só com chave"
[[ -s /root/.ssh/authorized_keys ]] || die "root não tem chave em authorized_keys; não vou desligar a senha"
# Arquivo com prefixo 00 é lido primeiro: vence o 50-cloud-init.conf da DigitalOcean
cat > /etc/ssh/sshd_config.d/00-netlab-hardening.conf <<'SSHD'
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitEmptyPasswords no
PubkeyAuthentication yes
PermitRootLogin prohibit-password
AllowUsers root
MaxAuthTries 3
LoginGraceTime 30
MaxStartups 10:30:60
X11Forwarding no
AllowAgentForwarding no
ClientAliveInterval 300
ClientAliveCountMax 2
SSHD
sshd -t || die "configuração do SSH inválida; nada foi recarregado"
systemctl reload ssh
sshd -T | grep -E '^(passwordauthentication|permitrootlogin|maxauthtries) '

log "2/6 Firewall (ufw): só SSH entra"
apt-get install -y -qq ufw >/dev/null
ufw default deny incoming >/dev/null
ufw default allow outgoing >/dev/null
ufw delete allow OpenSSH >/dev/null 2>&1 || true
ufw limit 22/tcp comment 'SSH com limite de taxa' >/dev/null
ufw --force enable >/dev/null

log "3/6 Docker: nada de fora chega direto nos containers"
# O Docker cria regras próprias que pulam o ufw. A chain DOCKER-USER roda antes delas:
# deixa passar respostas de conexões que os containers abriram e bloqueia o resto vindo de fora.
if ! grep -q 'netlab: DOCKER-USER' /etc/ufw/after.rules; then
  cat >> /etc/ufw/after.rules <<RULES

# netlab: DOCKER-USER (bloqueia acesso externo aos containers)
*filter
:DOCKER-USER - [0:0]
-A DOCKER-USER -i $PUBLIC_IF -m conntrack --ctstate RELATED,ESTABLISHED -j RETURN
-A DOCKER-USER -i $PUBLIC_IF -j DROP
-A DOCKER-USER -j RETURN
COMMIT
RULES
fi
ufw reload >/dev/null   # aplica sem reiniciar o Docker (o lab continua no ar)
iptables -S DOCKER-USER

log "4/6 fail2ban no SSH"
apt-get install -y -qq fail2ban >/dev/null
cat > /etc/fail2ban/jail.d/netlab.conf <<'JAIL'
[sshd]
enabled  = true
backend  = systemd
maxretry = 4
findtime = 10m
bantime  = 1h
JAIL
systemctl enable --now fail2ban >/dev/null
systemctl restart fail2ban
sleep 2
fail2ban-client status sshd | grep -E 'Currently|Total' || true

log "5/6 Atualizações de segurança automáticas"
apt-get install -y -qq unattended-upgrades >/dev/null
cat > /etc/apt/apt.conf.d/20auto-upgrades <<'APT'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT
apt-get -qq update && apt-get -y -qq upgrade >/dev/null

log "6/6 Serviços de rede desnecessários"
for svc in vsftpd proftpd pure-ftpd telnet.socket rpcbind rpcbind.socket avahi-daemon cups exim4 postfix; do
  if systemctl list-unit-files "$svc"* >/dev/null 2>&1 && systemctl is-enabled "$svc" >/dev/null 2>&1; then
    systemctl disable --now "$svc" >/dev/null 2>&1 && echo "desligado: $svc"
  fi
done
echo "Portas escutando para fora (deve ser só a 22):"
ss -tlnpH | awk '{print $4}' | grep -vE '^(127\.|\[::1\]|::1)' | sort -u

cat <<'DONE'

=====================================================================
 Pronto. Antes de fechar esta sessão, abra OUTRO terminal no seu PC
 e confirme que entra:   ssh netlab
 Se não entrar, use o Console da DigitalOcean (Droplet > Access).

 Se o apt avisar de kernel novo, reinicie numa hora sem demo:  reboot
 Depois do reboot, suba o lab de novo:
   make lab-up LAB_SIZE=mini && set -a && source build/lab.env && set +a && make deploy
=====================================================================
DONE
