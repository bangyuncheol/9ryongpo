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
    feed: str  # "sim" | "live"
    db_path: Path
    auction_dir: Path
    # 전화(설계 §4.3, 10/11). PHONE_ENABLED=1 인 서버 하나만 ClawOps 번호에 붙는다(번호당 연결 하나).
    phone_enabled: bool = False
    clawops_api_key: str = ""
    clawops_account_id: str = ""
    clawops_from_number: str = ""
    call_allowed_numbers: tuple[str, ...] = ()
    gemini_api_key: str = ""
    gemini_tts_model: str = "gemini-3.8-flash-tts"
    gemini_tts_voice: str = "Kore"
    stt_record: bool = False  # STT 비교 시험용 질문 음성 저장(data/stt_clips/)
    eum_base_url: str = "https://genix.pohang-eum.kr/dpg"
    http_timeout_s: float = 15.0


def _vapid_subject(raw: str) -> str:
    """'team@example.com' 처럼 주소만 넣어도 동작하게 mailto: 를 붙인다."""
    raw = raw.strip()
    if raw and "@" in raw and not raw.startswith(("mailto:", "https://")):
        return "mailto:" + raw
    return raw


def phone_digits(raw: str) -> str:
    """'010-1234-5678' · '+82 10 1234 5678' → '01012345678'. 국내 휴대폰 형식이 아니면 ''."""
    d = "".join(ch for ch in raw if ch.isdigit())
    if d.startswith("8210"):
        d = "0" + d[2:]
    return d if d.startswith("01") and len(d) in (10, 11) else ""


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
        vapid_subject=_vapid_subject(os.getenv("VAPID_SUBJECT", "")),
        feed=feed,
        db_path=_resolve(os.getenv("DB_PATH", "./data/app.db").strip()),
        auction_dir=REPO_ROOT / "data" / "auction",
        phone_enabled=os.getenv("PHONE_ENABLED", "0").strip() == "1",
        clawops_api_key=os.getenv("CLAWOPS_API_KEY", "").strip(),
        clawops_account_id=os.getenv("CLAWOPS_ACCOUNT_ID", "").strip(),
        clawops_from_number=os.getenv("CLAWOPS_FROM_NUMBER", "").strip(),
        call_allowed_numbers=tuple(n for n in (phone_digits(x) for x in os.getenv("CALL_ALLOWED_NUMBERS", "").split(",")) if n),
        gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip(),
        gemini_tts_model=os.getenv("GEMINI_TTS_MODEL", "gemini-3.8-flash-tts").strip(),
        gemini_tts_voice=os.getenv("GEMINI_TTS_VOICE", "Kore").strip(),
        stt_record=os.getenv("STT_RECORD", "0").strip() == "1",
    )


settings = load_settings()
