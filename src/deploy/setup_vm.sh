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
curl -fsS http://127.0.0.1:8000/api/health && echo

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
  echo "HTTPS 호스트를 주지 않았습니다. 포트가 막혀 있으면 deploy 스킬의 'Cloudflare 터널' 절차를 따르세요."
fi
