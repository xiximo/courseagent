from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.errors import ApiBusinessError
from app.db.models.harness_skill import HarnessSkillRecord, HarnessSkillVersionRecord


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.isoformat().replace("+00:00", "Z")


def to_skill_dto(skill: HarnessSkillRecord) -> dict:
    versions = sorted(skill.versions, key=lambda v: v.deployed_at, reverse=True)
    return {
        "id": skill.id,
        "name": skill.name,
        "description": skill.description,
        "activeVersion": skill.active_version,
        "versions": [
            {
                "version": v.version,
                "changelog": v.changelog,
                "deployedAt": _iso(v.deployed_at),
                "active": v.is_active,
            }
            for v in versions
        ],
    }


def list_skills(db: Session) -> list[dict]:
    stmt = (
        select(HarnessSkillRecord)
        .options(selectinload(HarnessSkillRecord.versions))
        .order_by(HarnessSkillRecord.id)
    )
    skills = db.scalars(stmt).all()
    return [to_skill_dto(s) for s in skills]


def get_skill(db: Session, skill_id: str) -> dict:
    skill = _load_skill(db, skill_id)
    if skill is None:
        raise ApiBusinessError("NOT_FOUND", f"Skill 不存在: {skill_id}", 404)
    return to_skill_dto(skill)


def activate_skill_version(db: Session, skill_id: str, version: str) -> dict:
    skill = _load_skill(db, skill_id)
    if skill is None:
        raise ApiBusinessError("NOT_FOUND", f"Skill 不存在: {skill_id}", 404)

    target = next((v for v in skill.versions if v.version == version), None)
    if target is None:
        raise ApiBusinessError("NOT_FOUND", f"版本不存在: {skill_id}@{version}", 404)

    for v in skill.versions:
        v.is_active = v.id == target.id
    skill.active_version = version
    db.commit()
    db.refresh(skill)
    return to_skill_dto(skill)


def _load_skill(db: Session, skill_id: str) -> HarnessSkillRecord | None:
    stmt = (
        select(HarnessSkillRecord)
        .where(HarnessSkillRecord.id == skill_id)
        .options(selectinload(HarnessSkillRecord.versions))
    )
    return db.scalars(stmt).first()
