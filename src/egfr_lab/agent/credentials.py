"""API 키를 읽는 단일 경로.

이 저장소는 **공개**다. 키가 저장소 안에 들어가면 커밋 사고로 바로 유출된다.
그래서 기본 저장 위치를 저장소 **바깥**(~/.config/egfr-evidence-lab/)으로 둔다.

읽는 순서:
  1. 환경 변수
  2. ~/.config/egfr-evidence-lab/<name>  (권한 600 권장)

키 값은 절대 로그·trace·예외 메시지에 넣지 않는다. 실패할 때도 경로와 이름만 말한다.
"""
from __future__ import annotations

import os
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "egfr-evidence-lab"


class CredentialError(RuntimeError):
    """키를 찾지 못했을 때. 메시지에 키 값을 담지 않는다."""


def key_path(name: str) -> Path:
    return CONFIG_DIR / name


def load_key(env_var: str, file_name: str) -> str:
    value = os.environ.get(env_var, "").strip()
    if value:
        return value

    path = key_path(file_name)
    if path.exists():
        value = path.read_text(encoding="utf-8").strip()
        if value:
            return value

    raise CredentialError(
        f"API 키를 찾지 못했다. 환경 변수 {env_var} 를 설정하거나 {path} 에 키를 저장하라. "
        "저장소 안에는 두지 마라(공개 저장소다)."
    )


def redact(text: str, secret: str) -> str:
    """혹시 모를 노출을 막는 마지막 방어선."""
    if secret and secret in text:
        return text.replace(secret, "<redacted>")
    return text
