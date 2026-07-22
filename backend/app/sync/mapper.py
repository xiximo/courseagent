from __future__ import annotations

from datetime import UTC, date, datetime

from app.db.models.standard import Standard, StandardSyncStatus


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _parse_modify_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        if len(value) == 10:
            parsed = datetime.fromisoformat(value)
            return parsed.replace(tzinfo=UTC)
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed
    except ValueError:
        return None


def build_standard_no(item: dict) -> str | None:
    parts = [
        (item.get("standSort") or item.get("standSortShow") or "").strip(),
        (item.get("standNumber") or "").strip(),
        (item.get("standYear") or "").strip(),
    ]
    parts = [p for p in parts if p]
    if not parts:
        return None
    if len(parts) >= 3:
        return f"{parts[0]} {parts[1]}-{parts[2]}"
    return " ".join(parts)


def _clip(value: str | None, max_len: int) -> str | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def apply_sprs_record(standard: Standard, item: dict) -> None:
    standard.stand_type = item.get("standType") or standard.stand_type
    standard.stand_sort = item.get("standSort") or item.get("standSortShow")
    standard.stand_number = item.get("standNumber")
    standard.stand_year = item.get("standYear")
    standard.standard_no = build_standard_no(item)
    standard.name = item.get("standName") or standard.name or "未命名标准"
    standard.english_name = item.get("standEnName")
    standard.country = item.get("country") or item.get("countryShow")
    standard.stand_state = item.get("standState")
    standard.stand_state_show = item.get("standStateShow") or item.get("standTextStatusShow")
    standard.stand_nature = item.get("standNature")
    standard.text_status = item.get("textStatus")
    standard.text_status_show = item.get("standTextStatusShow")
    standard.part_code = _clip(item.get("partClassificationCode"), 512)
    standard.part_name = _clip(item.get("partClassificationName"), 1024)
    standard.publish_date = _parse_date(item.get("issueTime"))
    standard.effective_date = _parse_date(item.get("putTime") or item.get("ssrq"))
    standard.valid_flag = item.get("validFlag")
    standard.sprs_modify_time = _parse_modify_time(item.get("modifyTime"))
    standard.attr_info_map = item.get("attrInfoMap")
    standard.attr_info_case_map = item.get("attrInfoCaseMap")
    standard.raw_payload = item
    standard.synced_at = datetime.now(UTC)
    if standard.sync_status == StandardSyncStatus.not_synced:
        standard.sync_status = StandardSyncStatus.synced
