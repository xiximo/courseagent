"""课程顾问 Function Calling Skill：查询班型详情、推荐适合班型。"""

from __future__ import annotations

from typing import Any

from app.course_agent.course_catalog import find_course, recommend_offerings

QUERY_COURSE_DETAIL_NAME = "query_course_detail"
RECOMMEND_COURSES_NAME = "recommend_courses"

OUT_OF_KNOWLEDGE_REPLY = "该问题不在我的知识范围内"

QUERY_COURSE_DETAIL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "course_name": {
            "type": "string",
            "description": "用户提到的班型名称，如北京线下班、上海线下班、线上直播班、暑期集训班、周末研修班",
        }
    },
    "required": ["course_name"],
}

RECOMMEND_COURSES_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "city": {
            "type": "string",
            "description": "用户所在或希望上课的城市，如北京、上海；若只想上线上课可填「线上」",
        },
        "time_preference": {
            "type": "string",
            "description": "时间偏好，如周末、工作日、暑期、晚上、时间灵活",
        },
    },
    "required": ["city", "time_preference"],
}

QUERY_COURSE_DETAIL_TOOL = {
    "id": "tool_query_course_detail",
    "name": QUERY_COURSE_DETAIL_NAME,
    "kind": "course_detail",
    "description": (
        "根据班型名称查询完整信息（时间、地点、费用、师资、大纲）。"
        "用户问到某个班型的详情、价格、上课地点或课程安排时必须调用。"
        "不要编造目录中不存在的班型。"
    ),
    "knowledgeBaseIds": [],
    "enabled": True,
}

RECOMMEND_COURSES_TOOL = {
    "id": "tool_recommend_courses",
    "name": RECOMMEND_COURSES_NAME,
    "kind": "course_recommend",
    "description": (
        "根据城市和时间偏好推荐最匹配的 1–2 个班型，并给出推荐理由。"
        "用户提到「我在上海」「只有周末有空」等约束时必须调用。"
        "城市或时间偏好不明确时不要猜测，应提示用户补充。"
    ),
    "knowledgeBaseIds": [],
    "enabled": True,
}

BUILTIN_COURSE_SKILLS = [QUERY_COURSE_DETAIL_TOOL, RECOMMEND_COURSES_TOOL]

COURSE_SKILL_SCHEMAS: dict[str, dict[str, Any]] = {
    QUERY_COURSE_DETAIL_NAME: QUERY_COURSE_DETAIL_SCHEMA,
    RECOMMEND_COURSES_NAME: RECOMMEND_COURSES_SCHEMA,
}


def execute_query_course_detail(args: dict[str, Any]) -> str:
    course_name = str(args.get("course_name") or args.get("courseName") or "").strip()
    if not course_name:
        return (
            "SKILL_FALLBACK: missing_param。缺少必填参数 course_name。"
            "请提示用户补充班型名称，例如北京线下班、上海线下班、线上直播班。"
        )
    course = find_course(course_name)
    if course is None:
        return (
            f"SKILL_FALLBACK: not_found。目录中没有名为「{course_name}」的班型。"
            "请不要编造，可请用户确认班型名称，或改用推荐班型工具。"
        )
    return f"SKILL_OK: query_course_detail\n{course.format_detail()}"


def execute_recommend_courses(args: dict[str, Any]) -> str:
    city = str(args.get("city") or "").strip()
    time_preference = str(
        args.get("time_preference") or args.get("timePreference") or ""
    ).strip()
    missing: list[str] = []
    if not city:
        missing.append("city（城市）")
    if not time_preference:
        missing.append("time_preference（时间偏好）")
    if missing:
        return (
            "SKILL_FALLBACK: missing_param。缺少必填参数："
            + "、".join(missing)
            + "。请提示用户补充，例如「我在上海，只有周末有空」。"
        )
    matches = recommend_offerings(city=city, time_preference=time_preference)
    if not matches:
        return (
            f"SKILL_FALLBACK: not_found。未找到同时满足城市「{city}」"
            f"与时间偏好「{time_preference}」的班型。"
            "请不要编造班型，可请用户放宽条件，或说明该约束下暂无匹配班型。"
        )
    lines = [
        f"SKILL_OK: recommend_courses（城市={city}，时间偏好={time_preference}）"
    ]
    for index, (course, reason) in enumerate(matches, start=1):
        lines.append(f"\n推荐 {index}：{course.name}\n理由：{reason}\n{course.format_detail()}")
    return "\n".join(lines)
