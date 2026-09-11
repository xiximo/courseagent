from app.course_agent.profile_tools import parse_profile_extract_payload
from app.course_agent.schedule import (
    force_chat_only_schedule,
    is_visible_in_chat,
    normalize_schedule,
    run_due_harness_jobs,
)


def test_normalize_schedule_defaults():
    data = normalize_schedule(None)
    assert data["enabled"] is False
    assert data["intervalHours"] == 2
    assert data["runMode"] == "chat"
    assert data["visibleInChat"] is True
    assert data["target"] == "all_users"
    assert data["onlyIfNewMessages"] is True
    assert data["lookbackHours"] == 24
    assert "不要编造" in data["taskPrompt"]


def test_scheduled_mode_hides_from_chat_by_default():
    data = normalize_schedule({"runMode": "scheduled", "enabled": True})
    assert data["visibleInChat"] is False
    assert is_visible_in_chat({"schedule": data}) is False


def test_interval_hours_clamped_and_fractional():
    data = normalize_schedule({"intervalHours": 0.5, "lookbackHours": 9999})
    assert data["intervalHours"] == 0.5
    assert data["lookbackHours"] == 720
    tiny = normalize_schedule({"intervalHours": 0.01})
    assert tiny["intervalHours"] == 0.05


def test_explicit_visible_in_chat_wins():
    data = normalize_schedule({"runMode": "scheduled", "visibleInChat": True})
    assert data["visibleInChat"] is True


def test_parse_profile_extract_payload():
    assert parse_profile_extract_payload("")["hasUpdate"] is False
    fenced = """```json
{"hasUpdate": true, "allergies": ["花生"], "newFacts": "对花生过敏"}
```"""
    data = parse_profile_extract_payload(fenced)
    assert data["allergies"] == ["花生"]
    assert parse_profile_extract_payload('{"hasUpdate": false}')["hasUpdate"] is False


def test_force_chat_only_schedule_disables_timer():
    data = force_chat_only_schedule({"enabled": True, "runMode": "scheduled"})
    assert data["enabled"] is False
    assert data["runMode"] == "chat"
    assert data["visibleInChat"] is True


def test_run_due_harness_jobs_is_retired():
    assert run_due_harness_jobs(None) == 0

