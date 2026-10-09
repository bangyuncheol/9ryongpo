"""가상 시계(설계 §1-15). 입항 예보·어종·푸시는 모두 이 시계의 now()를 읽는다.

FEED=live 이면 실제 한국 시각. FEED=sim 이면 재생·일시정지·배속·되감기가 되는 가상 시각.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, time as dtime, timedelta, timezone

KST = timezone(timedelta(hours=9))  # 한국은 서머타임이 없어 고정 오프셋으로 충분(윈도우 tzdata 불필요)
SIM_START = dtime(3, 0)


def real_now() -> datetime:
    return datetime.now(KST)


@dataclass
class VirtualClock:
    mode: str = "sim"                       # "sim" | "live"
    speed: float = 60.0                     # 재생 배속(가상 초 / 실제 초)
    playing: bool = False
    _anchor_virtual: datetime = field(default_factory=lambda: datetime.combine(real_now().date(), SIM_START, KST))
    _anchor_real: float = field(default_factory=time.monotonic)

    def now(self) -> datetime:
        if self.mode == "live":
            return real_now()
        if not self.playing:
            return self._anchor_virtual
        elapsed = time.monotonic() - self._anchor_real
        return self._anchor_virtual + timedelta(seconds=elapsed * self.speed)

    def _rebase(self) -> None:
        self._anchor_virtual = self.now()
        self._anchor_real = time.monotonic()

    def play(self, speed: float | None = None) -> None:
        self._rebase()
        if speed is not None:
            if not 0 < speed <= 3600:
                raise ValueError("배속은 0보다 크고 3600 이하여야 합니다.")
            self.speed = float(speed)
        self.playing = True

    def pause(self) -> None:
        self._rebase()
        self.playing = False

    def seek(self, hhmm: str) -> None:
        try:
            t = datetime.strptime(hhmm, "%H:%M").time()
        except ValueError:
            raise ValueError("시각은 HH:MM 형식이어야 합니다. 예: 03:30") from None
        self._anchor_virtual = datetime.combine(self._anchor_virtual.date(), t, KST)
        self._anchor_real = time.monotonic()

    def state(self) -> dict:
        return {"mode": self.mode, "now": self.now().isoformat(timespec="seconds"),
                "playing": self.playing if self.mode == "sim" else True,
                "speed": self.speed if self.mode == "sim" else 1.0}
