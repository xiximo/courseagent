from app.course_agent.react_agent import (
    bind_tools_to_tenant_knowledge,
    default_tools_from_knowledge_bases,
    execute_kb_tool,
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


def test_default_tools_are_course_skills_only():
    tools = default_tools_from_knowledge_bases(
        [
            {"id": "kb_a", "name": "顾问课程 material_b87628a5", "materialLabel": "material_b"},
            {"id": "kb_c", "name": "平台白皮书", "materialLabel": "material_c"},
        ]
    )
    names = [item["name"] for item in tools]
    assert names == ["query_course_detail", "recommend_courses"]
    assert "search_kb_1" not in names
    assert "search_core_nutrition" not in names


def test_bind_unbound_kb_tool_uses_tenant_libraries():
    tools = bind_tools_to_tenant_knowledge(
        [
            {"name": "query_course_detail", "kind": "course_detail", "enabled": True},
            {"name": "search_kb_1", "kind": "kb", "knowledgeBaseIds": [], "enabled": True},
        ],
        ["kb_org_1", "kb_org_2"],
    )
    kb = next(item for item in tools if item["name"] == "search_kb_1")
    assert kb["knowledgeBaseIds"] == ["kb_org_1", "kb_org_2"]


def test_bind_injects_tenant_search_when_no_kb_tool():
    tools = bind_tools_to_tenant_knowledge(
        [{"name": "query_course_detail", "kind": "course_detail", "enabled": True}],
        ["kb_org_1"],
    )
    names = [item["name"] for item in tools]
    assert "search_knowledge" in names
    search = next(item for item in tools if item["name"] == "search_knowledge")
    assert search["knowledgeBaseIds"] == ["kb_org_1"]


def test_execute_kb_tool_falls_back_to_agent_libraries(monkeypatch):
    from app.course_agent import react_agent as ra
    from app.course_agent.state_machine import Citation
    from app.schemas.indexing import ChunkSearchHitDto

    hit = ChunkSearchHitDto(
        chunkId="c1",
        attachmentId="att1",
        standardId="std1",
        content="机构自己的课程大纲",
        score=0.9,
        fileName="顾问课程手册",
        positionLabel="第一章",
    )
    monkeypatch.setattr(ra, "retrieve_for_agent", lambda *args, **kwargs: [hit])
    text, cites = execute_kb_tool(
        None,
        tool={"name": "search_kb_1", "knowledgeBaseIds": []},
        query="课程大纲是什么",
        agent_id="agt_org",
    )
    assert "顾问课程手册" in text or "课程大纲" in text
    assert cites
    assert isinstance(cites[0], Citation)


def test_normalize_react_config_keeps_unbound_kb_tool():
    cfg = normalize_react_config(
        {
            "soul": "soul",
            "prohibitionRules": "no",
            "tools": [{"name": "search_docs_1", "knowledgeBaseIds": [], "enabled": True}],
        }
    )
    kb = next(item for item in cfg["tools"] if item["name"] == "search_docs_1")
    assert kb["enabled"] is True
    assert kb["knowledgeBaseIds"] == []


def test_normalize_react_config_drops_legacy_nutrition_tools():
    cfg = normalize_react_config(
        {
            "soul": "soul",
            "prohibitionRules": "no",
            "tools": [
                {
                    "name": "search_core_nutrition",
                    "knowledgeBaseIds": ["kb_a"],
                    "enabled": True,
                },
                {"name": "search_kb_1", "knowledgeBaseIds": ["kb_b"], "enabled": True},
                {"name": "search_docs_1", "knowledgeBaseIds": ["kb_c"], "enabled": True},
            ],
        }
    )
    names = [item["name"] for item in cfg["tools"]]
    assert "search_core_nutrition" not in names
    assert "search_kb_1" not in names
    assert "search_docs_1" in names


def test_normalize_preserves_kb_binding_on_course_skills():
    cfg = normalize_react_config(
        {
            "soul": "soul",
            "prohibitionRules": "no",
            "tools": [
                {
                    "name": "recommend_courses",
                    "knowledgeBaseIds": ["kb_org"],
                    "enabled": True,
                    "description": "根据城市和时间偏好推荐班型",
                }
            ],
        }
    )
    rec = next(item for item in cfg["tools"] if item["name"] == "recommend_courses")
    assert rec["knowledgeBaseIds"] == ["kb_org"]
    assert "根据城市" in rec["description"]


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
    assert names[:2] == [
        "query_course_detail",
        "recommend_courses",
    ]
    assert names[2] == "search_kb"
    assert names[3] == "search_kb_2"
    assert cfg["maxToolRounds"] == 5
    assert "get_user_profile" not in names
    assert "update_user_profile" not in names


def test_normalize_react_config_strips_profile_tools():
    cfg = normalize_react_config(
        {
            "soul": "soul",
            "prohibitionRules": "no",
            "tools": [
                {
                    "name": "get_user_profile",
                    "kind": "profile_get",
                    "enabled": True,
                },
                {
                    "name": "update_user_profile",
                    "kind": "profile_update",
                    "enabled": True,
                },
                {"name": "search_kb", "knowledgeBaseIds": ["a"], "enabled": True},
            ],
        }
    )
    names = [item["name"] for item in cfg["tools"]]
    assert names[:2] == ["query_course_detail", "recommend_courses"]
    assert "get_user_profile" not in names
    assert "update_user_profile" not in names
    assert "search_kb" in names


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
                reasoning="先查询班型再回答",
                tool_calls=[
                    DoubaoToolCall(id="c1", name="query_course_detail", arguments="{}")
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
    assert tool_events[0]["toolName"] == "query_course_detail"
    result = next(payload for kind, payload in events if kind == "result")
    assert "低蛋白" in result["content"]

