from app.course_agent.course_catalog import find_course, recommend_offerings
from app.course_agent.course_skills import (
    execute_query_course_detail,
    execute_recommend_courses,
)


def test_query_course_detail_ok():
    text = execute_query_course_detail({"course_name": "北京线下班"})
    assert text.startswith("SKILL_OK")
    assert "3800" in text
    assert "海淀" in text


def test_query_course_detail_missing_and_unknown():
    missing = execute_query_course_detail({})
    assert "SKILL_FALLBACK: missing_param" in missing
    unknown = execute_query_course_detail({"course_name": "广州线下班"})
    assert "SKILL_FALLBACK: not_found" in unknown


def test_recommend_courses_shanghai_weekend():
    text = execute_recommend_courses(
        {"city": "上海", "time_preference": "周末"}
    )
    assert text.startswith("SKILL_OK")
    assert "周末研修班" in text or "线上直播班" in text


def test_recommend_courses_missing_param():
    text = execute_recommend_courses({"city": "上海"})
    assert "SKILL_FALLBACK: missing_param" in text


def test_catalog_alias_match():
    assert find_course("北京班") is not None
    matches = recommend_offerings(city="北京", time_preference="工作日")
    assert matches
    assert matches[0][0].name == "北京线下班"
