from __future__ import annotations

import re
from dataclasses import dataclass

ATT_FILE_PATTERN = re.compile(r"ATT_FILE_[A-Za-z0-9_]+")


@dataclass(frozen=True)
class AttachmentRef:
    sprs_file_id: str
    attr_field: str
    display_name: str | None


def _split_file_ids(raw: str) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()
    for part in raw.split(","):
        token = part.strip()
        if not token:
            continue
        for match in ATT_FILE_PATTERN.findall(token):
            if match not in seen:
                seen.add(match)
                ids.append(match)
    return ids


def _resolve_display_name(
    attr_field: str,
    attr_case_map: dict | None,
    index: int,
    total: int,
) -> str | None:
    if not attr_case_map:
        return None

    case_key = attr_field.lower()
    name_raw = attr_case_map.get(f"{case_key}Name") or attr_case_map.get(f"{case_key}name")
    if not name_raw or not isinstance(name_raw, str):
        return None

    names = [n.strip() for n in re.split(r",|，", name_raw) if n.strip()]
    if not names:
        return None
    if len(names) == 1 and total > 1:
        return names[0]
    if index < len(names):
        return names[index]
    return names[-1]


def extract_attachment_refs(
    attr_info_map: dict | None,
    attr_info_case_map: dict | None,
) -> list[AttachmentRef]:
    refs: list[AttachmentRef] = []
    seen_ids: set[str] = set()

    for field, value in (attr_info_map or {}).items():
        if not value or not isinstance(value, str):
            continue
        file_ids = _split_file_ids(value)
        if not file_ids:
            continue

        for index, file_id in enumerate(file_ids):
            if file_id in seen_ids:
                continue
            seen_ids.add(file_id)
            refs.append(
                AttachmentRef(
                    sprs_file_id=file_id,
                    attr_field=field,
                    display_name=_resolve_display_name(
                        field, attr_info_case_map, index, len(file_ids)
                    ),
                )
            )

    return refs


def guess_file_type(display_name: str | None, sprs_file_id: str) -> str:
    name = (display_name or sprs_file_id).lower()
    if name.endswith(".pdf"):
        return "pdf"
    if name.endswith(".docx"):
        return "docx"
    if name.endswith(".doc"):
        return "doc"
    if name.endswith(".txt"):
        return "txt"
    return "bin"
