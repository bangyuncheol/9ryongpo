"""환경 변수 설정. 값은 저장소 루트의 .env 에서 읽는다(커밋 금지)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# src/server/app/config.py → 저장소 루트
REPO_ROOT = Path(__file__).resolve().parents[3]
SERVER_DIR = Path(__file__).resolve().parents[1]

load_dotenv(REPO_ROOT / ".env")


def _resolve(path_str: str) -> Path:
    p = Path(path_str)
    return p if p.is_absolute() else (REPO_ROOT / p).resolve()


@dataclass(frozen=True)
class Settings:
    eum_service_key: str
    data_go_kr_key: str
    openai_api_key: str
    openai_model: str
    vapid_public_key: str
    vapid_private_key: str
    vapid_subject: str
    sim_admin_token: str
    feed: str  # "sim" | "live"
    db_path: Path
    auction_dir: Path
    eum_base_url: str = "https://genix.pohang-eum.kr/dpg"
    http_timeout_s: float = 15.0


def load_settings() -> Settings:
    feed = os.getenv("FEED", "sim").strip().lower()
    if feed not in ("sim", "live"):
        raise ValueError(f"FEED 값은 sim 또는 live 여야 합니다: {feed!r}")
    return Settings(
        eum_service_key=os.getenv("EUM_SERVICE_KEY", "").strip(),
        data_go_kr_key=os.getenv("DATA_GO_KR_KEY", "").strip(),
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-6.1-sol").strip(),
        vapid_public_key=os.getenv("VAPID_PUBLIC_KEY", "").strip(),
        vapid_private_key=os.getenv("VAPID_PRIVATE_KEY", "").strip(),
        vapid_subject=os.getenv("VAPID_SUBJECT", "").strip(),
        sim_admin_token=os.getenv("SIM_ADMIN_TOKEN", "").strip(),
        feed=feed,
        db_path=_resolve(os.getenv("DB_PATH", "./data/app.db").strip()),
        auction_dir=REPO_ROOT / "data" / "auction",
    )


settings = load_settings()
