from app.course_agent.react_agent import (
    default_tools_from_knowledge_bases,
    iter_react_turn,
    normalize_react_config,
    sanitize_tool_name,
)
from app.course_agent.profile_tools import merge_profile
from app.course_agent.trace import merge_trace_into_constraints, tool_label
from app.llm.doubao_client import DoubaoCompletion, DoubaoToolCall


def test_sanitize_tool_name():
    assert sanitize_tool_name("search core") == "search_core"
    assert sanitize_tool_name("1abc") == "kb_1abc"
    assert sanitize_tool_name("??") == "search_kb"


def test_default_tools_include_profile_and_knowledge():
    tools = default_tools_from_knowledge_bases(
        [
            {"id": "kb_a", "name": "2026秋季健康膳食指南", "materialLabel": "material_a"},
            {"id": "kb_b", "name": "个性化饮食计划方案", "materialLabel": "material_b"},
            {"id": "kb_c", "name": "健康优选平台服务白皮书", "materialLabel": "material_c"},
        ]
    )
    names = {item["name"] for item in tools}
    assert names == {
        "get_user_profile",
        "update_user_profile",
        "search_core_nutrition",
        "search_platform_guide",
    }
    core = next(item for item in tools if item["name"] == "search_core_nutrition")
    platform = next(item for item in tools if item["name"] == "search_platform_guide")
    assert set(core["knowledgeBaseIds"]) == {"kb_a", "kb_b"}
    assert platform["knowledgeBaseIds"] == ["kb_c"]
    assert "会员价格" in core["description"]
    assert "禁止用于膳食方案" in platform["description"]


def test_normalize_react_config_unique_names():
    cfg = normalize_react_config(
        {
            "soul": "soul",
            "prohibitionRules": "no",
            "tools": [
                {"name": "search_kb", "knowledgeBaseIds": ["a"], "enabled": True},
                {"name": "search_kb", "knowledgeBaseIds": ["b"], "enabled": True},
            ],
        }
    )
    names = [item["name"] for item in cfg["tools"]]
    assert names[:2] == ["get_user_profile", "update_user_profile"]
    assert names[2] == "search_kb"
    assert names[3] == "search_kb_2"
    assert cfg["maxToolRounds"] == 5


def test_merge_profile_appends_kidney_constraint():
    current = {
        "personaLabel": "增肌强化",
        "goals": ["增肌"],
        "constraints": ["训练日晚饭较晚"],
        "conditions": [],
        "allergies": [],
    }
    updated = merge_profile(
        current,
        {
            "conditions": ["肾病"],
            "constraints": ["避免高蛋白"],
            "newFacts": "用户说自己有肾病",
        },
    )
    assert "肾病" in updated["conditions"]
    assert "避免高蛋白" in updated["constraints"]
    assert "增肌" in updated["goals"]
    assert updated["notes"][-1] == "用户说自己有肾病"


def test_tool_label_and_trace_merge():
    assert tool_label("get_user_profile") == "读取用户画像"
    merged = merge_trace_into_constraints(
        {"city": "上海"},
        [{"id": "a1", "title": "调用工具", "type": "tool"}],
    )
    assert merged["city"] == "上海"
    assert merged["_agentTrace"][0]["id"] == "a1"


class _FakeRuntime:
    is_configured = True
    api_key = "k"
    endpoint_id = "e"
    base_url = "http://example"
    timeout_seconds = 10
    temperature = 0.3


def test_iter_react_turn_emits_tool_traces(monkeypatch):
    from app.course_agent import react_agent as ra

    monkeypatch.setattr(ra, "resolve_agent_doubao_runtime", lambda db, agent_id: _FakeRuntime())

    calls = {"n": 0}

    def fake_turn(**kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return DoubaoCompletion(
                content="",
                reasoning="先读取用户画像再回答",
                tool_calls=[
                    DoubaoToolCall(id="c1", name="get_user_profile", arguments="{}")
                ],
                finish_reason="tool_calls",
                assistant_message={"role": "assistant", "content": None},
            )
        return DoubaoCompletion(
            content="建议选择低蛋白膳食方案。",
            reasoning="",
            tool_calls=[],
            finish_reason="stop",
            assistant_message={
                "role": "assistant",
                "content": "建议选择低蛋白膳食方案。",
            },
        )

    monkeypatch.setattr(ra, "chat_completion_turn", fake_turn)
    monkeypatch.setattr(
        ra,
        "execute_named_tool",
        lambda *args, **kwargs: ("画像：肾病、低蛋白", []),
    )

    events = list(
        iter_react_turn(
            None,
            agent_id="agt_test",
            react_cfg={"soul": "soul", "prohibitionRules": "no", "tools": []},
            user_text="我有肾病，怎么吃",
            history=[],
        )
    )
    kinds = [kind for kind, _ in events]
    assert kinds.count("trace") >= 4
    assert "delta" in kinds
    assert "result" in kinds
    tool_events = [
        payload
        for kind, payload in events
        if kind == "trace" and payload.get("type") == "tool"
    ]
    assert tool_events
    assert tool_events[0]["toolName"] == "get_user_profile"
    result = next(payload for kind, payload in events if kind == "result")
    assert "低蛋白" in result["content"]

