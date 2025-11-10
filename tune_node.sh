#!/bin/bash
#
# #####################################################################
# ## SCRIPT DE TUNING DE PERFORMANCE: NÓ DOCKER/K8S
# ## Aplica as otimizações comprovadas (Rede, Memória, CPU)
# ## Autor: Marllus Lustosa (Baseado em testes de performance)
# #####################################################################
#

# Garante que está rodando como root
if [ "$EUID" -ne 0 ]; then
    echo "Por favor, rode este script como root (ou com sudo)."
    exit 1
fi

echo "🚀 Iniciando Otimização de Performance do Nó..."

# --- FASE 1: Instalação de Pacotes ---
echo "📦 Instalando pacotes de performance, monitoramento e Docker..."
apt-get update
apt-get install -y \
    htop iotop pcp atop iperf3 ethtool \
    linux-cpupower bpfcc-tools bpftrace linux-headers-amd64 \
    curl gnupg ca-certificates \
    iptables psmisc screen

# --- FASE 2: Escrita de Arquivos de Configuração ---

echo "📝 Aplicando configurações de Sysctl (Rede/Memória)..."
cat <<EOF > /etc/sysctl.d/99-docker-performance.conf
# === Tuning de Rede (BBR + Buffers) ===
net.core.default_qdisc = fq
net.ipv4.tcp_congestion_control = bbr
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216
net.core.rmem_default = 1048576
net.core.wmem_default = 1048576
net.ipv4.tcp_rmem = 4096 87380 16777216
net.ipv4.tcp_wmem = 4096 65536 16777216
net.core.netdev_max_backlog = 30000
net.core.somaxconn = 8192
net.ipv4.tcp_max_syn_backlog = 8192
net.ipv4.tcp_tw_reuse = 1
net.ipv4.tcp_fastopen = 3
net.ipv4.tcp_slow_start_after_idle = 0

# === Tuning de Memória (v5) ===
vm.swappiness = 0
vm.vfs_cache_pressure = 50

# === Tuning de FS e Sistema ===
fs.inotify.max_user_watches = 524288
fs.inotify.max_user_instances = 512
fs.file-max = 2097152

# === Requisitos de Rede do Docker/K8s ===
net.ipv4.ip_forward = 1
net.bridge.bridge-nf-call-iptables = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.netfilter.nf_conntrack_max = 1048576
EOF

echo "📝 Aplicando configuração do Daemon do Docker..."
mkdir -p /etc/docker
cat <<EOF > /etc/docker/daemon.json
{
  "storage-driver": "overlay2",
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  },
  "live-restore": true
}
EOF

echo "📝 Aplicando limites de sistema (ulimits)..."
cat <<EOF > /etc/security/limits.d/99-docker-limits.conf
* soft nofile 1048576
* hard nofile 1048576
* soft nproc 1048576
* hard nproc 1048576
EOF

echo "📝 Configurando módulos do kernel para o boot..."
cat <<EOF > /etc/modules-load.d/docker-performance.conf
br_netfilter
overlay
tcp_bbr
nf_conntrack
EOF

echo "📝 Desabilitando Transparent Huge Pages (THP) via rc.local..."
cat <<EOF > /etc/rc.local
#!/bin-bash
# Desabilita Transparent Huge Pages (THP)
echo never > /sys/kernel/mm/transparent_hugepage/enabled
echo never > /sys/kernel/mm/transparent_hugepage/defrag
exit 0
EOF
chmod +x /etc/rc.local

# --- FASE 3: Comandos de Configuração ---

echo "⚙️ Aplicando módulos do kernel e sysctl..."
modprobe overlay
modprobe br_netfilter
modprobe tcp_bbr
sysctl --system

echo "⚙️ Aplicando otimização de C-State (GRUB)..."
sed -i 's/GRUB_CMDLINE_LINUX_DEFAULT="/GRUB_CMDLINE_LINUX_DEFAULT="intel_idle.max_cstate=1 processor.max_cstate=1 /' /etc/default/grub
update-grub

echo "⚙️ Desabilitando serviços desnecessários..."
systemctl disable --now bluetooth.service cups.service ModemManager.service avahi-daemon.service smartd.service irqbalance.service

echo "⚙️ Habilitando rc.local (para THP)..."
systemctl enable rc-local.service
systemctl start rc-local.service

# --- FASE 4: Instalação do Docker ---
echo "🐳 Instalando Docker Engine (Método Oficial)..."
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc

echo "Types: deb" > /etc/apt/sources.list.d/docker.sources
echo "URIs: https://download.docker.com/linux/debian" >> /etc/apt/sources.list.d/docker.sources
echo "Suites: $(. /etc/os-release && echo "$VERSION_CODENAME")" >> /etc/apt/sources.list.d/docker.sources
echo "Components: stable" >> /etc/apt/sources.list.d/docker.sources
echo "Signed-By: /etc/apt/keyrings/docker.asc" >> /etc/apt/sources.list.d/docker.sources

apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker

echo "✅ Otimização concluída!"
echo "É altamente recomendado reiniciar o sistema para aplicar as mudanças do GRUB."
read -p "Reiniciar agora? (s/n) " REBOOT_NOW
if [[ "$REBOOT_NOW" == "s" || "$REBOOT_NOW" == "S" ]]; then
    echo "Reiniciando..."
    reboot
else
    echo "Por favor, reinicie manualmente ('sudo reboot') para completar a otimização."
fi
