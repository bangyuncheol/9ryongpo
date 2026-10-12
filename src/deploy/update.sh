#!/usr/bin/env bash
# VM에서 새 코드 반영: 받기 → 의존성 → 화면 빌드 → 재시작. (리눅스 VM 전용)
#   사용: bash src/deploy/update.sh            (--no-restart 면 재시작 생략)
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
export PATH="$HOME/.local/bin:$PATH"
cd "$REPO"
# 로컬에서 `git push vm main`으로 받는 VM(origin 없음)은 pull을 건너뛴다
if git remote get-url origin >/dev/null 2>&1; then git pull --ff-only; fi
(cd src/server && uv sync --frozen && uv run pytest -q)
(cd src/web && npm ci && npm run build)
if [ "${1:-}" != "--no-restart" ]; then
  sudo systemctl restart wipan
  sleep 3
  curl -fsS http://127.0.0.1:8731/api/health && echo
fi
