#!/usr/bin/env bash
# 대회 제공 GCP VM(우분투·데비안 기준) 첫 설치. VM 안에서 한 번 실행한다.
#   사용: bash src/deploy/setup_vm.sh <HTTPS 주소 호스트>   예) bash src/deploy/setup_vm.sh 34-64-1-2.sslip.io
# 전제: 저장소가 ~/9ryongpo 에 클론돼 있고, 루트에 .env 를 직접 올려 두었다(커밋 금지 파일).
# 개발용 명령은 맥·윈도우 공통이어야 하지만, 이 파일은 리눅스 VM 전용이다.
set -euo pipefail

HOST="${1:-}"
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
[ -f "$REPO/.env" ] || { echo "저장소 루트에 .env 가 없습니다. 먼저 올려 주세요." >&2; exit 1; }

echo "== 1/5 기본 패키지"
sudo apt-get update -y
sudo apt-get install -y git curl ca-certificates

echo "== 2/5 uv(파이썬)와 Node.js"
command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
if ! command -v node >/dev/null; then
  curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
  sudo apt-get install -y nodejs
fi

echo "== 3/5 서버·화면 빌드"
bash "$REPO/src/deploy/update.sh" --no-restart

echo "== 4/5 상시 실행(systemd)"
sed -e "s|__USER__|$USER|g" -e "s|__REPO__|$REPO|g" -e "s|__HOME__|$HOME|g" \
  "$REPO/src/deploy/wipan.service" | sudo tee /etc/systemd/system/wipan.service >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable --now wipan
sleep 3
curl -fsS http://127.0.0.1:8731/api/health && echo

echo "== 5/5 HTTPS"
if [ -n "$HOST" ]; then
  sudo apt-get install -y debian-keyring debian-archive-keyring apt-transport-https
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null
  sudo apt-get update -y && sudo apt-get install -y caddy
  sed "s|__HOST__|$HOST|g" "$REPO/src/deploy/Caddyfile" | sudo tee /etc/caddy/Caddyfile >/dev/null
  sudo systemctl reload caddy
  echo "완료: https://$HOST  (80·443 포트가 열려 있어야 인증서가 발급됩니다)"
else
  # 공유 VM이라 80·443을 잡지 않고 Cloudflare 터널로 내보낸다.
  # .env 에 TUNNEL_TOKEN(대시보드에서 만든 터널, 주소는 대시보드 Public Hostname)이 있으면 고정 주소, 없으면 임시 주소(다시 뜰 때마다 바뀜).
  if ! command -v cloudflared >/dev/null; then
    curl -fsSL -o /tmp/cloudflared.deb "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-$(dpkg --print-architecture).deb"
    sudo dpkg -i /tmp/cloudflared.deb
  fi
  if grep -q '^TUNNEL_TOKEN=.' "$REPO/.env"; then TUNNEL_ARGS="run"; else TUNNEL_ARGS="--url http://127.0.0.1:8731"; fi
  sudo tee /etc/systemd/system/wipan-tunnel.service >/dev/null <<EOF
[Unit]
Description=배마중 HTTPS 터널
After=wipan.service
[Service]
User=$USER
EnvironmentFile=$REPO/.env
ExecStart=$(command -v cloudflared) tunnel --no-autoupdate $TUNNEL_ARGS
Restart=always
RestartSec=5
[Install]
WantedBy=multi-user.target
EOF
  sudo systemctl daemon-reload
  sudo systemctl enable wipan-tunnel
  sudo systemctl restart wipan-tunnel
  sleep 8
  if [ "$TUNNEL_ARGS" = "run" ]; then
    echo "고정 터널 연결: $(sudo journalctl -u wipan-tunnel --no-pager | grep -c 'Registered tunnel connection')개 (주소는 Cloudflare 대시보드 Public Hostname)"
  else
    echo "터널 주소: $(sudo journalctl -u wipan-tunnel --no-pager | grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' | tail -1)"
  fi
fi
