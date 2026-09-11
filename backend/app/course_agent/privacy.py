"""Admin 对话记录脱敏。"""

from __future__ import annotations

import re

PHONE_RE = re.compile(r"1[3-9]\d{9}")
IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


def mask_phone(text: str | None) -> str:
    raw = text or ""
    return PHONE_RE.sub(lambda m: f"{m.group()[:3]}****{m.group()[7:]}", raw)


def mask_username(value: str | None) -> str:
    raw = (value or "").strip()
    if not raw:
        return raw
    if len(raw) == 1:
        return "*"
    if len(raw) == 2:
        return f"{raw[0]}*"
    return f"{raw[0]}{'*' * (len(raw) - 2)}{raw[-1]}"


def mask_ip(value: str | None) -> str | None:
    raw = (value or "").strip()
    if not raw:
        return None
    if "." in raw:
        parts = raw.split(".")
        if len(parts) == 4:
            return f"{parts[0]}.{parts[1]}.*.*"
    return "***"


def mask_display_name(value: str | None) -> str:
    return mask_phone(mask_username(value))
