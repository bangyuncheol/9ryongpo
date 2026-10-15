# syntax=docker/dockerfile:1
# Railway 배포용 이미지(2026-10-15, GCP VM 만료 후 전환). 화면(Vite)을 먼저 빌드하고 서버(FastAPI) 이미지에 넣는다.
# 로컬 개발·VM 절차는 바뀌지 않는다(src/deploy/). 비밀 값은 Railway Variables에만 둔다 — 이 파일에 적지 않는다.

# --- 1단계: 화면 빌드 ---
FROM node:22-slim AS web
WORKDIR /app/src/web
COPY src/web/package.json src/web/package-lock.json ./
RUN npm ci
COPY src/web/ ./
# 카카오맵 JavaScript 공개 키. Railway Variables 의 VITE_KAKAO_MAP_KEY 가 빌드 인자로 들어온다(비우면 Leaflet 지도).
ARG VITE_KAKAO_MAP_KEY=
ENV VITE_KAKAO_MAP_KEY=$VITE_KAKAO_MAP_KEY
RUN npm run build

# --- 2단계: 서버 ---
FROM python:3.12-slim AS server
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /uvx /bin/
WORKDIR /app/src/server
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY src/server/pyproject.toml src/server/uv.lock ./
RUN uv sync --frozen --no-dev
COPY src/server/ ./
# 위판 실적 CSV(서버 기동 시 적재)와 화면 빌드 결과. 경로는 config.REPO_ROOT(/app) 기준.
COPY data/auction/ /app/data/auction/
COPY --from=web /app/src/web/dist /app/src/web/dist
# SQLite 는 /app/db 에 둔다. 재배포해도 구독을 남기려면 Railway Volume 을 /app/db 에 붙인다.
ENV PATH="/app/src/server/.venv/bin:$PATH" \
    DB_PATH=/app/db/app.db \
    PYTHONUNBUFFERED=1
EXPOSE 8000
# Railway 가 PORT 를 넣어 준다. 프로세스 1개(SQLite 단일 쓰기, 설계 §1-19).
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1
