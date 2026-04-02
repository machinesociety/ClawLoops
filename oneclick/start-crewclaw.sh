#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${1:-$(pwd)}"
if [[ ! -f "$REPO_DIR/infra/compose/docker-compose.yml" ]]; then
  echo "未找到 CrewClaw 仓库：$REPO_DIR"
  echo "用法：$0 /path/to/CrewClaw"
  exit 1
fi

if [[ -f /etc/os-release ]]; then
  . /etc/os-release
  if [[ "${ID:-}" != "ubuntu" ]]; then
    echo "当前系统不是 Ubuntu（ID=${ID:-unknown}），脚本仅保证 Ubuntu 可用。"
  fi
fi

need_cmd() { command -v "$1" >/dev/null 2>&1; }

sudo_ok() {
  if [[ "$(id -u)" -eq 0 ]]; then
    return 0
  fi
  if ! need_cmd sudo; then
    echo "缺少 sudo，请以 root 运行或先安装 sudo。"
    exit 1
  fi
  sudo -n true >/dev/null 2>&1 || true
  return 0
}

install_packages() {
  sudo_ok
  sudo apt-get update -y
  sudo apt-get install -y "$@"
}

install_docker() {
  if need_cmd docker && docker --version >/dev/null 2>&1; then
    return 0
  fi

  install_packages ca-certificates curl gnupg lsb-release
  sudo install -m 0755 -d /etc/apt/keyrings
  if [[ ! -f /etc/apt/keyrings/docker.gpg ]]; then
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    sudo chmod a+r /etc/apt/keyrings/docker.gpg
  fi

  local arch codename
  arch="$(dpkg --print-architecture)"
  codename="$(. /etc/os-release && echo "$VERSION_CODENAME")"
  echo "deb [arch=${arch} signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu ${codename} stable" | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null

  sudo apt-get update -y
  sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

  sudo systemctl enable --now docker || true
}

ensure_docker_running() {
  sudo_ok
  sudo systemctl start docker || true
  if ! sudo docker info >/dev/null 2>&1; then
    echo "Docker 未能正常启动，请检查：sudo journalctl -u docker --no-pager -n 200"
    exit 1
  fi
}

primary_ip() {
  ip route get 1 2>/dev/null | awk '{print $(NF-2);exit}'
}

update_env_file() {
  local ip="$1"
  local env_dir="$REPO_DIR/infra/compose"
  local env_file="$env_dir/.env"
  local example="$env_dir/.env.example"

  if [[ ! -f "$env_file" ]]; then
    if [[ -f "$example" ]]; then
      cp "$example" "$env_file"
    else
      echo "缺少 $env_file 且找不到 $example"
      exit 1
    fi
  fi

  if grep -qE '^\s*DASHSCOPE_API_KEY\s*=\s*$' "$env_file"; then
    echo "检测到 DASHSCOPE_API_KEY 为空：LiteLLM 调用 DashScope 会失败。"
    echo "请编辑：$env_file 填写 DASHSCOPE_API_KEY，然后重新运行本脚本。"
    exit 1
  fi

  local clawloops_domain="clawloops.${ip}.nip.io"
  local rm_domain="runtime-manager.${ip}.nip.io"

  if grep -qE '^\s*CLAWLOOPS_DOMAIN=' "$env_file"; then
    sed -i "s|^CLAWLOOPS_DOMAIN=.*|CLAWLOOPS_DOMAIN=${clawloops_domain}|" "$env_file"
  else
    echo "CLAWLOOPS_DOMAIN=${clawloops_domain}" >>"$env_file"
  fi

  if grep -qE '^\s*RUNTIME_MANAGER_DOMAIN=' "$env_file"; then
    sed -i "s|^RUNTIME_MANAGER_DOMAIN=.*|RUNTIME_MANAGER_DOMAIN=${rm_domain}|" "$env_file"
  else
    echo "RUNTIME_MANAGER_DOMAIN=${rm_domain}" >>"$env_file"
  fi

  if grep -qE '^\s*RUNTIME_PUBLIC_HOST=' "$env_file"; then
    sed -i "s|^RUNTIME_PUBLIC_HOST=.*|RUNTIME_PUBLIC_HOST=${ip}|" "$env_file"
  else
    echo "RUNTIME_PUBLIC_HOST=${ip}" >>"$env_file"
  fi
}

update_traefik_dynamic_routes() {
  local ip="$1"
  local f="$REPO_DIR/infra/traefik/dynamic/middlewares.yml"
  if [[ ! -f "$f" ]]; then
    return 0
  fi

  local old_ip
  old_ip="$(grep -oE '([0-9]{1,3}\\.){3}[0-9]{1,3}' "$f" | head -n 1 || true)"
  if [[ -z "$old_ip" ]]; then
    return 0
  fi
  if [[ "$old_ip" == "$ip" ]]; then
    return 0
  fi

  sed -i "s/${old_ip//./\\.}/${ip//./\\.}/g" "$f"
}

compose_up() {
  local compose_dir="$REPO_DIR/infra/compose"
  cd "$compose_dir"

  if docker compose version >/dev/null 2>&1; then
    :
  else
    echo "docker compose 不可用（缺少 compose plugin），请确认 docker-compose-plugin 已安装。"
    exit 1
  fi

  sudo_ok
  sudo docker compose up -d --build
}

main() {
  install_docker
  ensure_docker_running

  local ip
  ip="$(primary_ip)"
  if [[ -z "$ip" ]]; then
    echo "无法自动识别服务器 IP，请手动设置 RUNTIME_PUBLIC_HOST 并更新路由域名。"
    exit 1
  fi

  update_env_file "$ip"
  update_traefik_dynamic_routes "$ip"
  compose_up

  echo "启动完成。"
  echo "主站（nip.io）：http://clawloops.${ip}.nip.io"
  echo "Traefik Dashboard：http://${ip}:8080"
}

main "$@"
