"""M6 — pilot22 추론 API.

M5 의 `ActivityPredictor` 를 그대로 감싼다. 전처리와 적용 범위 판정을
서비스에서 다시 구현하지 않는다. 두 번 구현하면 두 경로의 출력이 갈라진다.
"""
from __future__ import annotations

from .app import ServingConfig, build_app

__all__ = ["ServingConfig", "build_app"]
