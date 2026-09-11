"""结构化班型目录：供 Function Calling Skill 查询与推荐。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CourseOffering:
    name: str
    audience: str
    city: str
    format: str
    time: str
    time_tags: tuple[str, ...]
    location: str
    fee: str
    teachers: str
    outline: str
    aliases: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "audience": self.audience,
            "city": self.city,
            "format": self.format,
            "time": self.time,
            "location": self.location,
            "fee": self.fee,
            "teachers": self.teachers,
            "outline": self.outline,
        }

    def format_detail(self) -> str:
        return (
            f"班型：{self.name}\n"
            f"面向：{self.audience}\n"
            f"时间：{self.time}\n"
            f"地点：{self.location}\n"
            f"费用：{self.fee}\n"
            f"师资：{self.teachers}\n"
            f"大纲：{self.outline}"
        )


COURSE_OFFERINGS: tuple[CourseOffering, ...] = (
    CourseOffering(
        name="北京线下班",
        audience="学生 / 青少年",
        city="北京",
        format="offline",
        time="2026年7月8日—7月19日，工作日 09:00–16:30",
        time_tags=("工作日", "暑期", "白天", "weekday"),
        location="北京市海淀区中关村大街1号 · AI教育中心一层实训室",
        fee="3800 元/期（含材料费）",
        teachers="王老师（课程总监）、李老师（项目实践导师）",
        outline="AI素养导论、提示词实践、小组项目、结营展示",
        aliases=("北京班", "北京线下", "海淀线下班"),
    ),
    CourseOffering(
        name="上海线下班",
        audience="学生 / 青少年",
        city="上海",
        format="offline",
        time="2026年7月15日—7月26日，工作日 09:00–16:30",
        time_tags=("工作日", "暑期", "白天", "weekday"),
        location="上海市浦东新区世纪大道100号 · AI教育中心上海校区",
        fee="3600 元/期",
        teachers="陈老师（班主任）、赵老师（创意编程导师）",
        outline="生成式AI入门、协作创作、作品路演、家长开放日",
        aliases=("上海班", "上海线下", "浦东线下班"),
    ),
    CourseOffering(
        name="线上直播班",
        audience="学生 / 在职学习者",
        city="全国",
        format="online",
        time="2026年7–8月，每周三、周六 19:30–21:00 直播，回看有效期 90 天",
        time_tags=("周末", "晚上", "灵活", "直播", "weekend", "online"),
        location="线上直播教室（腾讯会议 / 平台直播间）",
        fee="2800 元/期",
        teachers="周老师（主讲）、助教团队晚间答疑",
        outline="AI工具实操、作业讲评、作品点评、结营测验",
        aliases=("线上班", "直播班", "网课班"),
    ),
    CourseOffering(
        name="暑期集训班",
        audience="在职教师",
        city="北京",
        format="offline",
        time="2026年7月21日—7月27日，全天集训（含周末）",
        time_tags=("暑期", "集训", "全天", "weekday", "weekend"),
        location="北京市海淀区中关村大街1号 · 教师研修中心",
        fee="4200 元/期",
        teachers="刘教授（教学法）、孙老师（课堂案例教练）",
        outline="教师AI素养、备课工作流、课堂案例打磨、校本落地计划",
        aliases=("教师集训", "暑期教师班", "集训班"),
    ),
    CourseOffering(
        name="周末研修班",
        audience="在职教师",
        city="上海",
        format="offline",
        time="2026年9–11月，每周六 09:00–16:00，共 6 次",
        time_tags=("周末", "研修", "周六", "weekend"),
        location="上海市浦东新区世纪大道100号 · 教师研修教室",
        fee="1800 元/期",
        teachers="吴老师（教研组长）、钱老师（工具工作坊）",
        outline="周末专题工作坊、作业互评、教研分享、结业答辩",
        aliases=("教师周末班", "周末班", "研修班"),
    ),
)

_NAME_INDEX = {item.name: item for item in COURSE_OFFERINGS}


def list_course_names() -> list[str]:
    return [item.name for item in COURSE_OFFERINGS]


def find_course(course_name: str) -> CourseOffering | None:
    raw = (course_name or "").strip()
    if not raw:
        return None
    exact = _NAME_INDEX.get(raw)
    if exact is not None:
        return exact
    compact = raw.replace(" ", "")
    for item in COURSE_OFFERINGS:
        aliases = (item.name, *item.aliases)
        if any(alias in compact or compact in alias for alias in aliases):
            return item
    return None


def recommend_offerings(
    *,
    city: str,
    time_preference: str,
    limit: int = 2,
) -> list[tuple[CourseOffering, str]]:
    city_text = (city or "").strip()
    time_text = (time_preference or "").strip()
    if not city_text or not time_text:
        return []

    scored: list[tuple[int, CourseOffering, str]] = []
    for item in COURSE_OFFERINGS:
        score = 0
        reasons: list[str] = []
        if _city_matches(item, city_text):
            score += 3
            reasons.append(f"覆盖{item.city}或可远程参加")
        if _time_matches(item, time_text):
            score += 3
            reasons.append(f"时间安排（{item.time}）符合「{time_text}」")
        if score <= 0:
            continue
        if not reasons:
            reasons.append("综合匹配当前约束")
        scored.append((score, item, "；".join(reasons)))

    scored.sort(key=lambda row: (-row[0], row[1].name))
    return [(item, reason) for _, item, reason in scored[:limit]]


def _city_matches(item: CourseOffering, city_text: str) -> bool:
    compact = city_text.replace(" ", "")
    if item.city in compact or compact in item.city:
        return True
    if item.format == "online" and any(
        token in compact for token in ("线上", "远程", "全国", "不限", "任意")
    ):
        return True
    if any(token in compact for token in ("线上", "远程")) and item.format == "online":
        return True
    return False


def _time_matches(item: CourseOffering, time_text: str) -> bool:
    compact = time_text.replace(" ", "").lower()
    tags = "".join(item.time_tags)
    mapping = (
        ("周末", ("周末", "周六", "周日", "weekend")),
        ("工作日", ("工作日", "平时", "weekday", "周一", "周五")),
        ("晚上", ("晚上", "夜间", "晚间")),
        ("暑期", ("暑期", "暑假", "7月", "8月")),
        ("灵活", ("灵活", "有空就行", "不限")),
        ("线上", ("直播", "线上")),
    )
    for _label, tokens in mapping:
        if any(token in compact for token in tokens) and any(
            token in tags or token in item.time for token in tokens
        ):
            return True
    return any(tag in compact for tag in item.time_tags)


def catalog_overview() -> list[dict[str, Any]]:
    return [item.to_dict() for item in COURSE_OFFERINGS]
