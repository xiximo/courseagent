"""加载 / 规范化 Agent 的 workflowGraph。"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


DEFAULT_POLICIES = {
    "maxInputChars": 500,
    "minConstraintsForRecommend": 2,
}


def _default_graph() -> dict[str, Any]:
    """与前端 createDefaultWorkflowGraph 对齐的最小可运行拓扑。"""
    return {
        "version": "1",
        "entryNodeId": "n_entry",
        "policies": dict(DEFAULT_POLICIES),
        "nodes": [
            {
                "id": "n_entry",
                "type": "entry",
                "name": "欢迎与分流",
                "config": {
                    "welcomeText": (
                        "您好，我是 AI 教育中心课程顾问。可咨询学生暑期营、教师培训或 OPC 平台服务。"
                        "请选择入口，或直接说明您的身份。"
                    ),
                    "quickActions": ["学生课程", "教师培训", "平台服务"],
                },
            },
            {
                "id": "n_identity",
                "type": "identity",
                "name": "身份澄清",
                "config": {
                    "promptWhenUnknown": "请问您是学生/家长、教师，还是机构/企业人员？",
                    "allowedRoles": ["student", "teacher", "org"],
                },
            },
            {
                "id": "n_slots",
                "type": "slot_fill",
                "name": "约束采集",
                "config": {
                    "askOneMissingAtATime": True,
                    "slots": [
                        {
                            "key": "city",
                            "label": "城市/地点",
                            "askPrompt": "您更倾向哪个城市或地区上课？",
                            "requiredForCount": True,
                        },
                        {
                            "key": "date",
                            "label": "可用日期",
                            "askPrompt": "问您方便的上课时间？（如 7 月、8 月或周末）",
                            "requiredForCount": True,
                        },
                        {
                            "key": "format",
                            "label": "线上/线下",
                            "askPrompt": "您更希望线上还是线下？",
                            "requiredForCount": True,
                        },
                        {
                            "key": "goal",
                            "label": "学习目标",
                            "askPrompt": "您最希望达成的学习目标是什么？",
                            "requiredForCount": True,
                        },
                    ],
                },
            },
            {
                "id": "n_scope",
                "type": "scope",
                "name": "知识范围绑定",
                "config": {
                    "binding": {"student": None, "teacher": None, "org": None},
                    "missingKbText": "当前身份对应的知识库尚未配置或未完成索引，请联系人工客服。",
                },
            },
            {
                "id": "n_recommend",
                "type": "rag_recommend",
                "name": "班型推荐",
                "config": {
                    "maxCourses": 2,
                    "lockFirstCourse": True,
                    "systemExtra": "仅依据当前知识库资料推荐 1–2 个真实班型；理由须逐条对应已采集约束。",
                    "quickActions": ["了解报名方式", "查看所有课程", "重新开始"],
                },
            },
            {
                "id": "n_platform",
                "type": "rag_platform",
                "name": "平台服务介绍",
                "config": {
                    "forbidCourseRecommend": True,
                    "systemExtra": "仅介绍 OPC 平台、会员与企业合作；不得输出学生/教师班型推荐。",
                    "quickActions": ["查看所有课程", "重新开始"],
                },
            },
            {
                "id": "n_qa",
                "type": "rag_qa",
                "name": "详情追问",
                "config": {
                    "systemExtra": "围绕「聚焦班型」（lockedCourse）作答；已锁定具体班型时勿展开其他等级/班型；资料不足则明确说明。",
                    "quickActions": ["了解报名方式", "重新开始"],
                },
            },
            {
                "id": "n_enroll",
                "type": "rag_enroll",
                "name": "报名引导",
                "config": {
                    "systemExtra": "仅提供资料中已有的报名方式；禁止虚构链接、电话、余位或截止状态。",
                    "quickActions": ["重新开始"],
                },
            },
            {
                "id": "n_control",
                "type": "session_control",
                "name": "会话控制",
                "config": {
                    "restartText": "好的，已为您重新开始。请重新选择服务入口。",
                    "listCoursesIntro": "根据当前身份资料，可了解的班型/服务如下：",
                    "quickActions": ["学生课程", "教师培训", "平台服务"],
                },
            },
            {
                "id": "n_boundary",
                "type": "boundary",
                "name": "边界与异常",
                "config": {
                    "templates": {
                        "outOfScope": "该问题超出课程顾问服务范围。您可选择学生课程、教师培训或平台服务继续咨询。",
                        "modelError": "模型暂时不可用，请稍后重试，或联系人工客服。",
                        "crossMaterial": "该问题属于其他服务范畴，为避免信息混淆，请切换对应入口后再问。",
                    },
                    "quickActions": ["学生课程", "教师培训", "平台服务"],
                },
            },
        ],
        "edges": [
            {
                "id": "e_entry_student",
                "source": "n_entry",
                "target": "n_identity",
                "priority": 10,
                "when": {"type": "quick_action", "action": "学生课程"},
                "apply": {"role": "student", "roleStatus": "confirmed"},
            },
            {
                "id": "e_entry_teacher",
                "source": "n_entry",
                "target": "n_identity",
                "priority": 10,
                "when": {"type": "quick_action", "action": "教师培训"},
                "apply": {"role": "teacher", "roleStatus": "confirmed"},
            },
            {
                "id": "e_entry_org",
                "source": "n_entry",
                "target": "n_identity",
                "priority": 10,
                "when": {"type": "quick_action", "action": "平台服务"},
                "apply": {"role": "org", "roleStatus": "confirmed"},
            },
            {
                "id": "e_entry_restart",
                "source": "n_entry",
                "target": "n_control",
                "priority": 10,
                "when": {"type": "quick_action", "action": "重新开始"},
            },
            {
                "id": "e_entry_nl",
                "source": "n_entry",
                "target": "n_identity",
                "priority": 100,
                "when": {"type": "always"},
            },
            {
                "id": "e_id_out",
                "source": "n_identity",
                "target": "n_boundary",
                "priority": 10,
                "when": {"type": "intent", "intent": "out_of_scope"},
            },
            {
                "id": "e_id_restart",
                "source": "n_identity",
                "target": "n_control",
                "priority": 10,
                "when": {"type": "intent", "intent": "restart"},
            },
            {
                "id": "e_id_org_skip_slots",
                "source": "n_identity",
                "target": "n_scope",
                "priority": 15,
                "when": {
                    "type": "and",
                    "items": [
                        {"type": "role_status", "status": "confirmed"},
                        {"type": "role_eq", "role": "org"},
                    ],
                },
            },
            {
                "id": "e_id_confirmed",
                "source": "n_identity",
                "target": "n_slots",
                "priority": 20,
                "when": {"type": "role_status", "status": "confirmed"},
            },
            {
                "id": "e_id_wait",
                "source": "n_identity",
                "target": "n_identity",
                "priority": 100,
                "when": {"type": "always"},
            },
            {
                "id": "e_slot_restart",
                "source": "n_slots",
                "target": "n_control",
                "priority": 5,
                "when": {"type": "intent", "intent": "restart"},
            },
            {
                "id": "e_slot_list",
                "source": "n_slots",
                "target": "n_control",
                "priority": 5,
                "when": {"type": "intent", "intent": "list_courses"},
            },
            {
                "id": "e_slot_out",
                "source": "n_slots",
                "target": "n_boundary",
                "priority": 5,
                "when": {"type": "intent", "intent": "out_of_scope"},
            },
            {
                "id": "e_slot_ready",
                "source": "n_slots",
                "target": "n_scope",
                "priority": 20,
                "when": {"type": "constraints_ready", "min": 2},
            },
            {
                "id": "e_slot_wait",
                "source": "n_slots",
                "target": "n_slots",
                "priority": 100,
                "when": {"type": "always"},
            },
            {
                "id": "e_scope_org",
                "source": "n_scope",
                "target": "n_platform",
                "priority": 10,
                "when": {"type": "role_eq", "role": "org"},
            },
            {
                "id": "e_scope_course",
                "source": "n_scope",
                "target": "n_recommend",
                "priority": 20,
                "when": {
                    "type": "or",
                    "items": [
                        {"type": "role_eq", "role": "student"},
                        {"type": "role_eq", "role": "teacher"},
                    ],
                },
            },
            {
                "id": "e_rec_enroll",
                "source": "n_recommend",
                "target": "n_enroll",
                "priority": 10,
                "when": {
                    "type": "or",
                    "items": [
                        {"type": "intent", "intent": "ask_enroll"},
                        {"type": "quick_action", "action": "了解报名方式"},
                    ],
                },
            },
            {
                "id": "e_rec_restart",
                "source": "n_recommend",
                "target": "n_control",
                "priority": 10,
                "when": {
                    "type": "or",
                    "items": [
                        {"type": "intent", "intent": "restart"},
                        {"type": "quick_action", "action": "重新开始"},
                    ],
                },
            },
            {
                "id": "e_rec_list",
                "source": "n_recommend",
                "target": "n_control",
                "priority": 10,
                "when": {
                    "type": "or",
                    "items": [
                        {"type": "intent", "intent": "list_courses"},
                        {"type": "quick_action", "action": "查看所有课程"},
                    ],
                },
            },
            {
                "id": "e_rec_qa",
                "source": "n_recommend",
                "target": "n_qa",
                "priority": 30,
                "when": {"type": "intent", "intent": "ask_detail"},
            },
            {
                "id": "e_rec_other_to_qa",
                "source": "n_recommend",
                "target": "n_qa",
                "priority": 40,
                "when": {"type": "intent", "intent": "other"},
            },
            {
                "id": "e_rec_stay",
                "source": "n_recommend",
                "target": "n_recommend",
                "priority": 100,
                "when": {"type": "always"},
            },
            {
                "id": "e_plat_restart",
                "source": "n_platform",
                "target": "n_control",
                "priority": 10,
                "when": {
                    "type": "or",
                    "items": [
                        {"type": "intent", "intent": "restart"},
                        {"type": "quick_action", "action": "重新开始"},
                    ],
                },
            },
            {
                "id": "e_plat_list",
                "source": "n_platform",
                "target": "n_control",
                "priority": 10,
                "when": {
                    "type": "or",
                    "items": [
                        {"type": "intent", "intent": "list_courses"},
                        {"type": "quick_action", "action": "查看所有课程"},
                    ],
                },
            },
            {
                "id": "e_plat_out",
                "source": "n_platform",
                "target": "n_boundary",
                "priority": 10,
                "when": {"type": "intent", "intent": "out_of_scope"},
            },
            {
                "id": "e_plat_stay",
                "source": "n_platform",
                "target": "n_platform",
                "priority": 100,
                "when": {"type": "always"},
            },
            {
                "id": "e_qa_enroll",
                "source": "n_qa",
                "target": "n_enroll",
                "priority": 10,
                "when": {
                    "type": "or",
                    "items": [
                        {"type": "intent", "intent": "ask_enroll"},
                        {"type": "quick_action", "action": "了解报名方式"},
                    ],
                },
            },
            {
                "id": "e_qa_restart",
                "source": "n_qa",
                "target": "n_control",
                "priority": 10,
                "when": {
                    "type": "or",
                    "items": [
                        {"type": "intent", "intent": "restart"},
                        {"type": "quick_action", "action": "重新开始"},
                    ],
                },
            },
            {
                "id": "e_qa_cross",
                "source": "n_qa",
                "target": "n_boundary",
                "priority": 10,
                "when": {"type": "intent", "intent": "out_of_scope"},
            },
            {
                "id": "e_qa_stay",
                "source": "n_qa",
                "target": "n_qa",
                "priority": 100,
                "when": {"type": "always"},
            },
            {
                "id": "e_enroll_restart",
                "source": "n_enroll",
                "target": "n_control",
                "priority": 10,
                "when": {
                    "type": "or",
                    "items": [
                        {"type": "intent", "intent": "restart"},
                        {"type": "quick_action", "action": "重新开始"},
                    ],
                },
            },
            {
                "id": "e_enroll_qa",
                "source": "n_enroll",
                "target": "n_qa",
                "priority": 100,
                "when": {"type": "always"},
            },
            {
                "id": "e_ctrl_done",
                "source": "n_control",
                "target": "n_entry",
                "priority": 10,
                "when": {"type": "intent", "intent": "restart"},
                "apply": {"clearSession": True, "clearRole": True},
            },
            {
                "id": "e_ctrl_role",
                "source": "n_control",
                "target": "n_identity",
                "priority": 15,
                "when": {"type": "intent", "intent": "choose_role"},
            },
            {
                "id": "e_ctrl_list_back",
                "source": "n_control",
                "target": "n_entry",
                "priority": 20,
                "when": {"type": "always"},
            },
            {
                "id": "e_bound_restart",
                "source": "n_boundary",
                "target": "n_control",
                "priority": 10,
                "when": {"type": "quick_action", "action": "重新开始"},
            },
            {
                "id": "e_bound_student",
                "source": "n_boundary",
                "target": "n_identity",
                "priority": 10,
                "when": {"type": "quick_action", "action": "学生课程"},
                "apply": {
                    "role": "student",
                    "roleStatus": "confirmed",
                    "clearSession": True,
                },
            },
            {
                "id": "e_bound_teacher",
                "source": "n_boundary",
                "target": "n_identity",
                "priority": 10,
                "when": {"type": "quick_action", "action": "教师培训"},
                "apply": {
                    "role": "teacher",
                    "roleStatus": "confirmed",
                    "clearSession": True,
                },
            },
            {
                "id": "e_bound_org",
                "source": "n_boundary",
                "target": "n_identity",
                "priority": 10,
                "when": {"type": "quick_action", "action": "平台服务"},
                "apply": {
                    "role": "org",
                    "roleStatus": "confirmed",
                    "clearSession": True,
                },
            },
            {
                "id": "e_bound_back",
                "source": "n_boundary",
                "target": "n_entry",
                "priority": 100,
                "when": {"type": "always"},
            },
        ],
    }


SPEC_NODE_TYPES = {
    "entry",
    "identity",
    "slot_fill",
    "scope",
    "rag_recommend",
    "rag_qa",
    "rag_enroll",
    "rag_platform",
    "session_control",
    "boundary",
}


def load_workflow_graph(config_json: dict | None) -> dict[str, Any]:
    cfg = config_json or {}
    raw = cfg.get("workflowGraph")
    if not raw or not isinstance(raw, dict):
        return deepcopy(_default_graph())
    return normalize_workflow_graph(raw)


def normalize_workflow_graph(raw: dict[str, Any]) -> dict[str, Any]:
    base = _default_graph()
    nodes_in = raw.get("nodes")
    if not isinstance(nodes_in, list) or not nodes_in:
        return deepcopy(base)

    first = nodes_in[0] if isinstance(nodes_in[0], dict) else {}
    data = first.get("data") if isinstance(first.get("data"), dict) else {}
    # 旧七步 / RF 包装无法直接跑 → 默认图
    if data.get("kind") and first.get("type") not in SPEC_NODE_TYPES:
        return deepcopy(base)
    if first.get("type") == "agentNode" or data.get("nodeType"):
        return deepcopy(base)

    nodes = [n for n in nodes_in if isinstance(n, dict) and n.get("type") in SPEC_NODE_TYPES]
    if not nodes:
        return deepcopy(base)

    edges = raw.get("edges") if isinstance(raw.get("edges"), list) else base["edges"]
    policies = raw.get("policies") if isinstance(raw.get("policies"), dict) else {}
    entry = raw.get("entryNodeId")
    if not isinstance(entry, str) or not any(n.get("id") == entry for n in nodes):
        entry = nodes[0]["id"]

    return {
        "version": "1",
        "entryNodeId": entry,
        "policies": {
            "maxInputChars": int(policies.get("maxInputChars") or DEFAULT_POLICIES["maxInputChars"]),
            "minConstraintsForRecommend": int(
                policies.get("minConstraintsForRecommend")
                or DEFAULT_POLICIES["minConstraintsForRecommend"]
            ),
        },
        "nodes": nodes,
        "edges": edges,
        "meta": raw.get("meta") if isinstance(raw.get("meta"), dict) else {},
    }


def index_graph(graph: dict[str, Any]) -> tuple[dict[str, dict], list[dict]]:
    nodes = {n["id"]: n for n in graph.get("nodes") or [] if isinstance(n, dict) and n.get("id")}
    edges = [e for e in (graph.get("edges") or []) if isinstance(e, dict)]
    return nodes, edges
