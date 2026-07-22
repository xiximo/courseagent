from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.errors import ApiBusinessError
from app.config import get_settings
from app.course_agent.lead_service import (
    CourseAgentLeadService,
    VisitorContext,
    is_restart_text,
)
from app.course_agent.llm_helper import CourseAgentLlmHelper
from app.course_agent.material_service import MaterialService
from app.course_agent.model_service import ModelService
from app.course_agent.rag import (
    enrich_citations_with_attachments,
    format_hits_for_prompt,
    hits_to_citations_from_hits,
    retrieve_for_agent,
)
from app.course_agent.state_machine import (
    AgentMessage,
    Citation,
    SessionState,
    _msg_id,
    _now_iso,
    create_initial_state,
    create_welcome_message,
    process_message,
)
from app.course_agent.workflow import (
    WorkflowEngine,
    state_from_session,
    state_to_session_fields,
)
from app.course_agent.workflow.graph_loader import load_workflow_graph
from app.course_agent.workflow.types import AssistantOut
from app.db.models.course_agent import (
    CourseAgentLeadRecord,
    CourseAgentMessageRecord,
    CourseAgentRecord,
    CourseAgentSessionRecord,
)
from app.schemas.course_agent import (
    CourseAgentConfigDto,
    CourseAgentLeadDetailDto,
    CourseAgentLeadSummaryDto,
    CourseAgentMessageDto,
    CourseAgentPatchBody,
    CourseAgentSessionDto,
    CourseAgentSessionStateDto,
    CourseAgentSummaryDto,
    CreateCourseAgentBody,
    PublicAgentConfigDto,
)

CourseAgentType = Literal["basic", "workflow", "autonomous"]
from app.services.llm_settings import get_or_create_llm_config, resolve_llm_runtime

DEFAULT_STATE_MACHINE = [
    {"id": "welcome", "label": "欢迎分流", "description": "说明服务范围，提供三大入口", "enabled": True},
    {"id": "identity", "label": "身份澄清", "description": "未澄清身份前不得推荐班型", "enabled": True},
    {"id": "constraints", "label": "约束采集", "description": "城市、日期、形式、目标", "enabled": True},
    {"id": "recommend", "label": "班型推荐", "description": "推荐 1—2 个真实班型", "enabled": True},
    {"id": "qa", "label": "详情追问", "description": "关联当前班型 RAG 问答", "enabled": True},
    {"id": "enroll", "label": "报名引导", "description": "仅提供资料中已有报名方式", "enabled": True},
]

DEFAULT_KNOWLEDGE_BASES: list[dict] = []

AUTONOMOUS_STATE_MACHINE = [
    {
        "id": "welcome",
        "label": "自主对话",
        "description": "LLM 自主理解意图并规划多轮回复",
        "enabled": True,
    },
]


def _read_agent_type(cfg: dict) -> CourseAgentType:
    raw = cfg.get("agentType") or (cfg.get("_meta") or {}).get("agentType") or "workflow"
    if raw in ("basic", "workflow", "autonomous"):
        return raw  # type: ignore[return-value]
    return "workflow"


def _is_default_agent(cfg: dict) -> bool:
    if bool(cfg.get("isDefault")):
        return True
    meta = cfg.get("_meta") or {}
    return bool(meta.get("isDefault"))


def _set_default_flag(cfg: dict, *, is_default: bool) -> dict:
    next_cfg = dict(cfg)
    next_cfg["isDefault"] = is_default
    meta = dict(next_cfg.get("_meta") or {})
    meta["isDefault"] = is_default
    next_cfg["_meta"] = meta
    return next_cfg


def _new_agent_id() -> str:
    return f"agt_{secrets.token_hex(4)}"


def _default_config(
    agent_id: str,
    name: str,
    description: str,
    status: str,
    *,
    agent_type: CourseAgentType = "workflow",
) -> dict:
    env = get_settings()
    return {
        "temperature": 0.3,
        "boundKnowledgeBaseIds": [],
        "boundModelIds": [],
        "model": {
            "provider": "doubao",
            "stream": False,
            "modelName": env.doubao_model_name,
            "endpointId": env.doubao_endpoint_id,
            "baseUrl": env.doubao_base_url,
        },
        "stateMachine": DEFAULT_STATE_MACHINE,
        "knowledgeBases": DEFAULT_KNOWLEDGE_BASES,
        "embed": {
            "embedKey": "emb_demo_7x9k2m",
            "allowedOrigins": [
                "http://localhost:5173",
                "http://127.0.0.1:5173",
                "http://localhost:5174",
                "http://127.0.0.1:5174",
            ],
            "theme": "light",
            "position": "bottom-right",
        },
        "conversation": {
            "welcomeMessage": (
                "您好！我是 AI 课程顾问，可为您提供学生夏令营、教师培训或 OPC 平台服务咨询。"
            ),
            "systemPrompt": "",
            "menuButtons": ["学生课程", "教师培训", "平台服务"],
            "resetMessage": "已为您重新开始。",
            "emptyInputMessage": "请输入您的问题。",
            "tooLongMessage": "输入过长，请精简后重新发送（限 500 字）。",
            "outOfScopeMessage": "抱歉，我仅提供课程与平台服务咨询。",
        },
        "_meta": {
            "agentId": agent_id,
            "name": name,
            "description": description,
            "status": status,
            "agentType": agent_type,
        },
        "agentType": agent_type,
    }


def _apply_agent_type_defaults(cfg: dict, agent_type: CourseAgentType, name: str) -> dict:
    cfg = dict(cfg)
    cfg["agentType"] = agent_type
    meta = dict(cfg.get("_meta") or {})
    meta["agentType"] = agent_type
    cfg["_meta"] = meta
    embed = dict(cfg.get("embed") or {})
    embed["embedKey"] = f"emb_{secrets.token_hex(4)}"
    cfg["embed"] = embed
    conversation = dict(cfg.get("conversation") or {})

    if agent_type == "basic":
        from app.course_agent.llm_helper import SYSTEM_PROMPT

        cfg["stateMachine"] = []
        conversation["welcomeMessage"] = (
            f"您好！我是{name}，可直接就课程与平台服务向我提问。"
        )
        conversation.setdefault("systemPrompt", SYSTEM_PROMPT)
        conversation["menuButtons"] = []
    elif agent_type == "workflow":
        cfg["stateMachine"] = list(DEFAULT_STATE_MACHINE)
        if not cfg.get("workflowGraph"):
            cfg["workflowGraph"] = load_workflow_graph({})
        conversation.setdefault(
            "welcomeMessage",
            "您好！我是 AI 课程顾问，可为您提供学生夏令营、教师培训或 OPC 平台服务咨询。",
        )
        conversation.setdefault(
            "menuButtons", ["学生课程", "教师培训", "平台服务"]
        )
    else:
        cfg["stateMachine"] = list(AUTONOMOUS_STATE_MACHINE)
        meta["autonomyLevel"] = "high"
        cfg["_meta"] = meta
        conversation["welcomeMessage"] = (
            f"您好！我是{name}，将自主理解您的需求并结合知识库给出建议。"
        )
        conversation["menuButtons"] = []

    cfg["conversation"] = conversation
    return cfg


def _iso(dt: datetime | None) -> str:
    if dt is None:
        return datetime.now(UTC).isoformat()
    return dt.isoformat()


class CourseAgentService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.leads = CourseAgentLeadService(db)

    def list_leads(
        self, *, agent_id: str | None = None, limit: int = 50, offset: int = 0
    ) -> list[CourseAgentLeadSummaryDto]:
        return self.leads.list_leads(agent_id=agent_id, limit=limit, offset=offset)

    def get_lead(self, lead_id: uuid.UUID) -> CourseAgentLeadDetailDto:
        return self.leads.get_lead_detail(lead_id)

    def delete_lead(self, lead_id: uuid.UUID) -> dict[str, str]:
        return self.leads.delete_lead(lead_id)

    def list_agents(self) -> list[CourseAgentSummaryDto]:
        rows = self.db.scalars(
            select(CourseAgentRecord).order_by(CourseAgentRecord.updated_at.desc())
        ).all()
        return [self._to_summary(row) for row in rows]

    def get_default_agent_id(self) -> str | None:
        rows = self.db.scalars(
            select(CourseAgentRecord).order_by(CourseAgentRecord.updated_at.desc())
        ).all()
        if not rows:
            return None
        for row in rows:
            if _is_default_agent(row.config_json or {}):
                return row.agent_id
        return rows[0].agent_id

    def set_default_agent(self, agent_id: str) -> CourseAgentConfigDto:
        target = self._get_agent_row(agent_id, require_active=False)
        rows = self.db.scalars(select(CourseAgentRecord)).all()
        for row in rows:
            cfg = dict(row.config_json or {})
            want = row.agent_id == target.agent_id
            if _is_default_agent(cfg) == want and (
                bool(cfg.get("isDefault")) == want
            ):
                continue
            row.config_json = _set_default_flag(cfg, is_default=want)
            row.updated_at = datetime.now(UTC)
        self.db.commit()
        self.db.refresh(target)
        return self._to_config_dto(target)

    def create_agent(self, body: CreateCourseAgentBody) -> CourseAgentConfigDto:
        agent_id = _new_agent_id()
        while self.db.get(CourseAgentRecord, agent_id) is not None:
            agent_id = _new_agent_id()

        cfg = _default_config(
            agent_id,
            body.name.strip(),
            body.description.strip(),
            "draft",
            agent_type=body.agentType,
        )
        cfg = _apply_agent_type_defaults(cfg, body.agentType, body.name.strip())

        existing_count = self.db.scalar(
            select(func.count()).select_from(CourseAgentRecord)
        ) or 0

        row = CourseAgentRecord(
            agent_id=agent_id,
            name=body.name.strip(),
            description=body.description.strip(),
            status="draft",
            config_json=cfg,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        MaterialService(self.db).ensure_agent_materials(agent_id)
        if existing_count == 0:
            return self.set_default_agent(agent_id)
        return self._to_config_dto(row)

    def delete_agent(self, agent_id: str) -> dict[str, str]:
        target = self._get_agent_row(agent_id, require_active=False)
        was_default = _is_default_agent(target.config_json or {})
        # 知识库 / 模型为平台独立资源，删除 Agent 时不级联删除；仅解除遗留归属
        material = MaterialService(self.db)
        for row in material._list_kb_rows(agent_id):
            row.agent_id = None
        models = ModelService(self.db)
        for row in models._list_model_rows(agent_id):
            row.agent_id = None
        self.db.flush()

        # 重新加载后再删，避免会话内缓存对象状态异常
        row = self.db.get(CourseAgentRecord, agent_id)
        if row is None:
            raise ApiBusinessError("NOT_FOUND", f"Agent {agent_id} 不存在", 404)
        self.db.delete(row)
        self.db.commit()

        if was_default:
            next_default = self.db.scalars(
                select(CourseAgentRecord).order_by(CourseAgentRecord.updated_at.desc())
            ).first()
            if next_default is not None:
                self.set_default_agent(next_default.agent_id)
        return {"message": "Agent 已删除"}

    def get_agent(self, agent_id: str) -> CourseAgentConfigDto:
        MaterialService(self.db).ensure_agent_materials(agent_id)
        ModelService(self.db).list_models(agent_id)
        row = self._get_agent_row(agent_id, require_active=False)
        return self._to_config_dto(row)

    def update_agent(self, agent_id: str, body: CourseAgentPatchBody) -> CourseAgentConfigDto:
        row = self._get_agent_row(agent_id, require_active=False)
        cfg = dict(row.config_json or {})
        if body.name is not None:
            row.name = body.name
        if body.description is not None:
            row.description = body.description
        if body.status is not None:
            row.status = body.status
        if body.isDefault is True:
            return self.set_default_agent(agent_id)
        if body.isDefault is False:
            cfg = _set_default_flag(cfg, is_default=False)
        if body.temperature is not None:
            cfg["temperature"] = body.temperature
        if body.boundKnowledgeBaseIds is not None:
            cfg["boundKnowledgeBaseIds"] = list(body.boundKnowledgeBaseIds)
        if body.boundModelIds is not None:
            cfg["boundModelIds"] = list(body.boundModelIds)
        if body.stateMachine is not None:
            cfg["stateMachine"] = [s.model_dump() for s in body.stateMachine]
        if body.workflowGraph is not None:
            cfg["workflowGraph"] = body.workflowGraph
        if body.embed is not None:
            cfg["embed"] = body.embed.model_dump()
        if body.conversation is not None:
            cfg["conversation"] = body.conversation.model_dump()
        row.config_json = cfg
        row.updated_at = datetime.now(UTC)
        self.db.commit()
        self.db.refresh(row)
        return self._to_config_dto(row)

    def get_public_config(self, agent_id: str) -> PublicAgentConfigDto:
        row = self._get_agent_row(agent_id, require_active=True)
        conv = (row.config_json or {}).get("conversation") or {}
        embed = (row.config_json or {}).get("embed") or {}
        return PublicAgentConfigDto(
            agentId=row.agent_id,
            name=row.name,
            welcomeMessage=conv.get("welcomeMessage", ""),
            menuButtons=list(conv.get("menuButtons") or []),
            theme=embed.get("theme", "light"),
        )

    def create_session(
        self, agent_id: str, visitor: VisitorContext | None = None
    ) -> CourseAgentSessionDto:
        row = self._get_agent_row(agent_id)
        cfg = row.config_json or {}
        if self._uses_workflow(cfg):
            return self._create_workflow_session(
                row, is_preview=False, visitor=visitor
            )

        conv = cfg.get("conversation") or {}
        welcome = create_welcome_message(conv)
        state = create_initial_state()

        session = CourseAgentSessionRecord(
            agent_id=agent_id,
            title="新对话",
            step=state.step,
            role=state.role,
            constraints_json=state.constraints,
            recommended_courses=state.recommended_courses,
            locked_course=state.locked_course,
        )
        self.db.add(session)
        self.db.flush()

        lead = self.leads.open_lead(session, visitor)
        self._persist_message(session.id, welcome, lead_id=lead.id)
        self.db.commit()
        self.db.refresh(session)
        loaded = self._load_session(session.id)
        return self._to_session_dto(loaded)

    def send_message(
        self,
        session_id: uuid.UUID,
        content: str,
        visitor: VisitorContext | None = None,
    ) -> CourseAgentSessionDto:
        session = self._load_session(session_id)
        if session is None:
            raise ApiBusinessError("NOT_FOUND", "会话不存在", 404)

        if is_restart_text(content):
            return self.reset_session(session_id, visitor=visitor)

        agent = self._get_agent_row(session.agent_id)
        cfg = agent.config_json or {}
        if self._uses_workflow(cfg):
            return self._send_workflow_message(
                session, agent, content, visitor=visitor
            )

        if _read_agent_type(cfg) == "basic":
            return self._send_legacy_preview_message(session, agent, content)

        return self._send_legacy_message(session, agent, content, visitor=visitor)

    def reset_session(
        self, session_id: uuid.UUID, visitor: VisitorContext | None = None
    ) -> CourseAgentSessionDto:
        """重新开始：切新线索，清空对话区仅展示新欢迎语。"""
        session = self._load_session(session_id)
        if session is None:
            raise ApiBusinessError("NOT_FOUND", "会话不存在", 404)

        agent = self._get_agent_row(session.agent_id)
        cfg = agent.config_json or {}
        if self._uses_workflow(cfg):
            return self._reset_workflow_public_session(session, agent, visitor=visitor)
        return self._reset_legacy_public_session(session, agent, visitor=visitor)

    def create_preview_session(self, agent_id: str) -> CourseAgentSessionDto:
        row = self._get_agent_row(agent_id, require_active=False)
        cfg = row.config_json or {}
        if self._uses_workflow(cfg):
            return self._create_workflow_session(row, is_preview=True)

        conv = cfg.get("conversation") or {}
        welcome = create_welcome_message(conv)

        session = CourseAgentSessionRecord(
            agent_id=agent_id,
            title="对话预览",
            step="preview",
            role=None,
            constraints_json={},
            recommended_courses=[],
            locked_course=None,
        )
        self.db.add(session)
        self.db.flush()
        self._persist_message(session.id, welcome)
        self.db.commit()
        loaded = self._load_session(session.id)
        return self._to_session_dto(loaded)

    def send_preview_message(
        self, session_id: uuid.UUID, content: str
    ) -> CourseAgentSessionDto:
        session = self._load_session(session_id)
        if session is None:
            raise ApiBusinessError("NOT_FOUND", "会话不存在", 404)

        agent = self._get_agent_row(session.agent_id, require_active=False)
        cfg = agent.config_json or {}
        if self._uses_workflow(cfg):
            meta = (session.constraints_json or {}).get("_workflow") or {}
            if not meta.get("isPreview") and session.step == "preview":
                # 旧预览会话升级：走自由 RAG
                return self._send_legacy_preview_message(session, agent, content)
            return self._send_workflow_message(session, agent, content)

        if session.step != "preview":
            raise ApiBusinessError("INVALID_SESSION", "非预览会话", 400)
        return self._send_legacy_preview_message(session, agent, content)

    def reset_preview_session(self, session_id: uuid.UUID) -> CourseAgentSessionDto:
        session = self._load_session(session_id)
        if session is None:
            raise ApiBusinessError("NOT_FOUND", "会话不存在", 404)

        agent = self._get_agent_row(session.agent_id, require_active=False)
        cfg = agent.config_json or {}
        if self._uses_workflow(cfg):
            for message in list(session.messages):
                self.db.delete(message)
            engine = WorkflowEngine(self.db, agent.agent_id, cfg)
            state = engine.create_initial_state(is_preview=True)
            boot = engine.bootstrap(state)
            fields = state_to_session_fields(boot.state)
            session.step = fields["step"]
            session.role = fields["role"]
            session.constraints_json = fields["constraints_json"]
            session.recommended_courses = fields["recommended_courses"]
            session.locked_course = fields["locked_course"]
            session.title = "对话预览"
            session.updated_at = datetime.now(UTC)
            for msg in boot.assistant_messages:
                self._persist_workflow_assistant(session.id, agent.agent_id, msg)
            self.db.commit()
            loaded = self._load_session(session_id)
            return self._to_session_dto(loaded)

        if session.step != "preview":
            raise ApiBusinessError("INVALID_SESSION", "非预览会话", 400)

        for message in list(session.messages):
            self.db.delete(message)

        conv = cfg.get("conversation") or {}
        welcome = create_welcome_message(conv)
        self._persist_message(session.id, welcome)
        session.title = "对话预览"
        session.updated_at = datetime.now(UTC)
        self.db.commit()
        loaded = self._load_session(session_id)
        return self._to_session_dto(loaded)

    def _reset_workflow_public_session(
        self,
        session: CourseAgentSessionRecord,
        agent: CourseAgentRecord,
        visitor: VisitorContext | None = None,
    ) -> CourseAgentSessionDto:
        lead = self.leads.rotate_on_restart(session, visitor)
        engine = WorkflowEngine(self.db, agent.agent_id, agent.config_json)
        state = engine.create_initial_state(is_preview=False)
        boot = engine.bootstrap(state)
        fields = state_to_session_fields(boot.state)

        session.step = fields["step"]
        session.role = fields["role"]
        session.constraints_json = fields["constraints_json"]
        session.recommended_courses = fields["recommended_courses"]
        session.locked_course = fields["locked_course"]
        session.title = "新对话"
        session.updated_at = datetime.now(UTC)

        for msg in boot.assistant_messages:
            self._persist_workflow_assistant(
                session.id, agent.agent_id, msg, lead_id=lead.id
            )
        self.leads.sync_profile(lead, session)
        self.db.commit()
        loaded = self._load_session(session.id)
        return self._to_session_dto(loaded)

    def _reset_legacy_public_session(
        self,
        session: CourseAgentSessionRecord,
        agent: CourseAgentRecord,
        visitor: VisitorContext | None = None,
    ) -> CourseAgentSessionDto:
        lead = self.leads.rotate_on_restart(session, visitor)
        conv = (agent.config_json or {}).get("conversation") or {}
        welcome = create_welcome_message(conv)
        state = create_initial_state()

        session.step = state.step
        session.role = state.role
        session.constraints_json = state.constraints
        session.recommended_courses = state.recommended_courses
        session.locked_course = state.locked_course
        session.title = "新对话"
        session.updated_at = datetime.now(UTC)

        self._persist_message(session.id, welcome, lead_id=lead.id)
        self.leads.sync_profile(lead, session)
        self.db.commit()
        loaded = self._load_session(session.id)
        return self._to_session_dto(loaded)

    def _uses_workflow(self, cfg: dict) -> bool:
        agent_type = _read_agent_type(cfg)
        if agent_type == "workflow":
            return True
        graph = cfg.get("workflowGraph")
        return bool(isinstance(graph, dict) and graph.get("nodes"))

    def _create_workflow_session(
        self,
        agent: CourseAgentRecord,
        *,
        is_preview: bool,
        visitor: VisitorContext | None = None,
    ) -> CourseAgentSessionDto:
        engine = WorkflowEngine(self.db, agent.agent_id, agent.config_json)
        state = engine.create_initial_state(is_preview=is_preview)
        boot = engine.bootstrap(state)
        fields = state_to_session_fields(boot.state)

        session = CourseAgentSessionRecord(
            agent_id=agent.agent_id,
            title="对话预览" if is_preview else "新对话",
            step=fields["step"],
            role=fields["role"],
            constraints_json=fields["constraints_json"],
            recommended_courses=fields["recommended_courses"],
            locked_course=fields["locked_course"],
        )
        self.db.add(session)
        self.db.flush()
        lead_id = None
        if not is_preview:
            lead = self.leads.open_lead(session, visitor)
            lead_id = lead.id
        for msg in boot.assistant_messages:
            self._persist_workflow_assistant(
                session.id, agent.agent_id, msg, lead_id=lead_id
            )
        self.db.commit()
        loaded = self._load_session(session.id)
        return self._to_session_dto(loaded)

    def _send_workflow_message(
        self,
        session: CourseAgentSessionRecord,
        agent: CourseAgentRecord,
        content: str,
        visitor: VisitorContext | None = None,
    ) -> CourseAgentSessionDto:
        dto: CourseAgentSessionDto | None = None
        for kind, payload in self._iter_workflow_message_events(
            session, agent, content, visitor=visitor
        ):
            if kind == "done":
                dto = payload  # type: ignore[assignment]
        if dto is None:
            raise ApiBusinessError("INTERNAL", "工作流处理失败", 500)
        return dto

    def iter_send_message_events(
        self,
        session_id: uuid.UUID,
        content: str,
        visitor: VisitorContext | None = None,
    ):
        """公开对话流式事件：delta / done / error。"""
        try:
            session = self._load_session(session_id)
            if session is None:
                raise ApiBusinessError("NOT_FOUND", "会话不存在", 404)

            if is_restart_text(content):
                dto = self.reset_session(session_id, visitor=visitor)
                yield "done", dto.model_dump()
                return

            agent = self._get_agent_row(session.agent_id)
            cfg = agent.config_json or {}
            if self._uses_workflow(cfg):
                yield from self._iter_workflow_message_events(
                    session, agent, content, visitor=visitor, as_dict=True
                )
                return

            # 基础型：RAG + 可配置系统提示词（与预览路径一致）
            if _read_agent_type(cfg) == "basic":
                yield from self._iter_legacy_preview_message_events(
                    session, agent, content, as_dict=True
                )
                return

            dto = self._send_legacy_message(session, agent, content, visitor=visitor)
            yield "done", dto.model_dump()
        except ApiBusinessError as exc:
            yield "error", {
                "code": exc.code,
                "message": exc.message,
                "statusCode": exc.status_code,
            }

    def iter_send_preview_message_events(
        self,
        session_id: uuid.UUID,
        content: str,
    ):
        """预览对话流式事件：delta / done / error。"""
        try:
            session = self._load_session(session_id)
            if session is None:
                raise ApiBusinessError("NOT_FOUND", "会话不存在", 404)

            agent = self._get_agent_row(session.agent_id, require_active=False)
            cfg = agent.config_json or {}
            if self._uses_workflow(cfg):
                meta = (session.constraints_json or {}).get("_workflow") or {}
                if not meta.get("isPreview") and session.step == "preview":
                    yield from self._iter_legacy_preview_message_events(
                        session, agent, content, as_dict=True
                    )
                    return
                yield from self._iter_workflow_message_events(
                    session, agent, content, as_dict=True
                )
                return

            if session.step != "preview":
                raise ApiBusinessError("INVALID_SESSION", "非预览会话", 400)
            yield from self._iter_legacy_preview_message_events(
                session, agent, content, as_dict=True
            )
        except ApiBusinessError as exc:
            yield "error", {
                "code": exc.code,
                "message": exc.message,
                "statusCode": exc.status_code,
            }

    def _iter_workflow_message_events(
        self,
        session: CourseAgentSessionRecord,
        agent: CourseAgentRecord,
        content: str,
        visitor: VisitorContext | None = None,
        *,
        as_dict: bool = False,
    ):
        engine = WorkflowEngine(self.db, agent.agent_id, agent.config_json)
        is_preview = bool(
            ((session.constraints_json or {}).get("_workflow") or {}).get("isPreview")
        ) or session.title == "对话预览"

        lead: CourseAgentLeadRecord | None = None
        lead_id = None
        if not is_preview:
            lead = self.leads.ensure_open_lead(session, visitor)
            lead_id = lead.id

        state = state_from_session(
            step=session.step,
            role=session.role,
            constraints_json=session.constraints_json,
            recommended_courses=session.recommended_courses,
            locked_course=session.locked_course,
            entry_node_id=engine.entry_node_id,
            is_preview=is_preview,
        )
        # 确保节点仍在图中
        if state.current_node_id not in engine.nodes:
            state.current_node_id = engine.entry_node_id

        result = None
        for kind, payload in engine.iter_handle_turn(state, content, stream=True):
            if kind == "delta":
                yield "delta", payload
            elif kind == "turn_complete":
                result = payload

        if result is None:
            raise ApiBusinessError("INTERNAL", "工作流处理失败", 500)

        fields = state_to_session_fields(result.state)

        user_msg = AgentMessage(
            id=_msg_id(),
            role="user",
            content=content.strip() or content,
            created_at=_now_iso(),
        )
        self._persist_message(session.id, user_msg, lead_id=lead_id)

        for msg in result.assistant_messages:
            self._persist_workflow_assistant(
                session.id, agent.agent_id, msg, lead_id=lead_id
            )

        session.step = fields["step"]
        session.role = fields["role"]
        session.constraints_json = fields["constraints_json"]
        session.recommended_courses = fields["recommended_courses"]
        session.locked_course = fields["locked_course"]
        session.updated_at = datetime.now(UTC)
        if result.title_hint and (
            session.title in ("新对话", "对话预览") or not session.title
        ):
            session.title = result.title_hint

        if lead is not None:
            self.leads.sync_profile(lead, session)

        self.db.commit()
        loaded = self._load_session(session.id)
        dto = self._to_session_dto(loaded)
        yield "done", (dto.model_dump() if as_dict else dto)

    def _iter_legacy_preview_message_events(
        self,
        session: CourseAgentSessionRecord,
        agent: CourseAgentRecord,
        content: str,
        *,
        as_dict: bool = False,
    ):
        """旧预览路径：对 LLM 回复做增量推送。"""
        from app.llm.doubao_client import DoubaoChatMessage, DoubaoClientError, iter_chat_completion

        trimmed = content.strip()
        if not trimmed:
            raise ApiBusinessError("EMPTY_INPUT", "请输入您的问题。", 400)
        if trimmed in ("重新开始", "reset"):
            dto = self.reset_preview_session(session.id)
            yield "done", (dto.model_dump() if as_dict else dto)
            return

        conv = (agent.config_json or {}).get("conversation") or {}
        too_long = conv.get("tooLongMessage", "输入过长，请精简后重新发送（限 500 字）。")
        if len(trimmed) > 500:
            raise ApiBusinessError("INPUT_TOO_LONG", too_long, 400)

        user_msg = AgentMessage(
            id=_msg_id(),
            role="user",
            content=trimmed,
            created_at=_now_iso(),
        )
        self._persist_message(session.id, user_msg)
        session.updated_at = datetime.now(UTC)

        llm_cfg = resolve_llm_runtime(get_or_create_llm_config(self.db))
        hits = retrieve_for_agent(
            self.db,
            agent_id=session.agent_id,
            query=trimmed,
            top_k=llm_cfg.qa_top_k,
        )
        retrieval_context = format_hits_for_prompt(hits)
        citations = hits_to_citations_from_hits(hits)

        history = [self._record_to_agent_message(m) for m in session.messages]
        llm = CourseAgentLlmHelper(self.db, session.agent_id)

        reply_content: str
        if not hits:
            reply_content = (
                "知识库中暂无可用资料（当前文档数 0、切片数 0），无法检索到相关内容。"
                "请先在「知识库」上传文档，等待解析与索引完成后再试。"
            )
        elif llm.is_available():
            # 流式生成（与 generate_preview_reply 同构）
            from app.course_agent.llm_helper import resolve_system_prompt

            system_prompt = resolve_system_prompt(conv)
            history_lines: list[str] = []
            for msg in history[-8:]:
                role_label = "用户" if msg.role == "user" else "助手"
                snippet = (msg.content or "").strip().replace("\n", " ")
                if len(snippet) > 240:
                    snippet = snippet[:240] + "…"
                history_lines.append(f"{role_label}：{snippet}")
            context_parts = []
            if history_lines:
                context_parts.append("近期对话：\n" + "\n".join(history_lines))
            if retrieval_context:
                context_parts.append(f"检索到的资料片段：\n{retrieval_context}")
            context = "\n\n".join(context_parts) if context_parts else "（无额外上下文）"
            user_prompt = (
                f"用户问题：{trimmed}\n\n"
                f"上下文：\n{context}\n\n"
                "请依据资料片段回答；资料不足时明确说明未找到相关信息。"
            )
            parts: list[str] = []
            try:
                for delta in iter_chat_completion(
                    api_key=llm.runtime.api_key,
                    endpoint_id=llm.runtime.endpoint_id,
                    base_url=llm.runtime.base_url,
                    timeout_seconds=llm.runtime.timeout_seconds,
                    temperature=llm.runtime.temperature,
                    messages=[
                        DoubaoChatMessage(role="system", content=system_prompt),
                        DoubaoChatMessage(role="user", content=user_prompt),
                    ],
                ):
                    parts.append(delta)
                    yield "delta", {"text": delta}
                reply_content = "".join(parts).strip()
                if not reply_content:
                    reply_content = (
                        "模型暂时不可用，以下为检索到的相关资料：\n\n"
                        + (retrieval_context or "（无）")
                    )
            except DoubaoClientError:
                reply_content = (
                    "模型暂时不可用，以下为检索到的相关资料：\n\n"
                    + (retrieval_context or "（无）")
                )
        else:
            reply_content = (
                "当前未配置可用模型，以下为检索到的相关资料：\n\n"
                + (retrieval_context or "（无）")
            )

        enriched = enrich_citations_with_attachments(
            self.db, session.agent_id, citations
        )
        reply = AgentMessage(
            id=_msg_id(),
            role="assistant",
            content=reply_content,
            created_at=_now_iso(),
            citations=enriched,
        )
        self._persist_message(session.id, reply)
        self.db.commit()
        loaded = self._load_session(session.id)
        dto = self._to_session_dto(loaded)
        yield "done", (dto.model_dump() if as_dict else dto)

    def _persist_workflow_assistant(
        self,
        session_id: uuid.UUID,
        agent_id: str,
        msg: AssistantOut,
        *,
        lead_id: uuid.UUID | None = None,
    ) -> None:
        citations = None
        if msg.citations:
            citations = [
                Citation(
                    c.document,
                    c.chapter,
                    attachment_id=c.attachment_id,
                    chunk_id=c.chunk_id,
                )
                for c in msg.citations
            ]
            citations = enrich_citations_with_attachments(self.db, agent_id, citations)

        agent_msg = AgentMessage(
            id=_msg_id(),
            role="assistant",
            content=msg.content,
            created_at=_now_iso(),
            citations=citations,
            quick_actions=msg.quick_actions,
        )
        self._persist_message(session_id, agent_msg, lead_id=lead_id)

    def _send_legacy_message(
        self,
        session: CourseAgentSessionRecord,
        agent: CourseAgentRecord,
        content: str,
        visitor: VisitorContext | None = None,
    ) -> CourseAgentSessionDto:
        conv = (agent.config_json or {}).get("conversation") or {}

        lead: CourseAgentLeadRecord | None = None
        lead_id = None
        lead = self.leads.ensure_open_lead(session, visitor)
        lead_id = lead.id

        state = SessionState(
            step=session.step,  # type: ignore[arg-type]
            role=session.role,  # type: ignore[arg-type]
            constraints=dict(session.constraints_json or {}),
            recommended_courses=list(session.recommended_courses or []),
            locked_course=session.locked_course,
        )
        visible = [
            m
            for m in session.messages
            if m.lead_id is None or m.lead_id == lead_id
        ]
        history = [self._record_to_agent_message(m) for m in visible]

        new_state, new_messages, title = process_message(
            state, history, content, conversation=conv
        )

        session.step = new_state.step
        session.role = new_state.role
        session.constraints_json = new_state.constraints
        session.recommended_courses = new_state.recommended_courses
        session.locked_course = new_state.locked_course
        session.title = title if title != "新对话" else session.title
        session.updated_at = datetime.now(UTC)

        existing_count = len(visible)
        for msg in new_messages[existing_count:]:
            if msg.role == "assistant" and msg.citations:
                enriched = enrich_citations_with_attachments(
                    self.db, session.agent_id, msg.citations
                )
                if enriched is not None:
                    msg = AgentMessage(
                        id=msg.id,
                        role=msg.role,
                        content=msg.content,
                        created_at=msg.created_at,
                        citations=enriched,
                        quick_actions=msg.quick_actions,
                    )
            self._persist_message(session.id, msg, lead_id=lead_id)

        self.leads.sync_profile(lead, session)
        self.db.commit()
        loaded = self._load_session(session.id)
        return self._to_session_dto(loaded)

    def _send_legacy_preview_message(
        self,
        session: CourseAgentSessionRecord,
        agent: CourseAgentRecord,
        content: str,
    ) -> CourseAgentSessionDto:
        trimmed = content.strip()
        if not trimmed:
            raise ApiBusinessError("EMPTY_INPUT", "请输入您的问题。", 400)
        if trimmed in ("重新开始", "reset"):
            return self.reset_preview_session(session.id)

        conv = (agent.config_json or {}).get("conversation") or {}
        too_long = conv.get("tooLongMessage", "输入过长，请精简后重新发送（限 500 字）。")
        if len(trimmed) > 500:
            raise ApiBusinessError("INPUT_TOO_LONG", too_long, 400)

        user_msg = AgentMessage(
            id=_msg_id(),
            role="user",
            content=trimmed,
            created_at=_now_iso(),
        )
        self._persist_message(session.id, user_msg)
        session.updated_at = datetime.now(UTC)

        llm_cfg = resolve_llm_runtime(get_or_create_llm_config(self.db))
        hits = retrieve_for_agent(
            self.db,
            agent_id=session.agent_id,
            query=trimmed,
            top_k=llm_cfg.qa_top_k,
        )
        retrieval_context = format_hits_for_prompt(hits)
        citations = hits_to_citations_from_hits(hits)

        history = [self._record_to_agent_message(m) for m in session.messages]
        llm = CourseAgentLlmHelper(self.db, session.agent_id)

        reply_content: str
        if not hits:
            reply_content = (
                "知识库中暂无可用资料（当前文档数 0、切片数 0），无法检索到相关内容。"
                "请先在「知识库」上传文档，等待解析与索引完成后再试。"
            )
        elif llm.is_available():
            from app.course_agent.llm_helper import resolve_system_prompt

            generated = llm.generate_preview_reply(
                user_text=trimmed,
                retrieval_context=retrieval_context,
                history=history,
                system_prompt=resolve_system_prompt(conv),
            )
            if generated is not None:
                reply_content = generated.content
            else:
                reply_content = (
                    "模型暂时不可用，以下为检索到的相关资料：\n\n"
                    + retrieval_context.replace("（未检索到相关资料片段）", "").strip()
                )
        else:
            reply_content = "LLM 未配置。检索到的资料片段如下：\n\n" + retrieval_context

        assistant_msg = AgentMessage(
            id=_msg_id(),
            role="assistant",
            content=reply_content,
            created_at=_now_iso(),
            citations=citations or None,
        )
        enriched_citations = enrich_citations_with_attachments(
            self.db, session.agent_id, assistant_msg.citations
        )
        if enriched_citations is not None:
            assistant_msg = AgentMessage(
                id=assistant_msg.id,
                role=assistant_msg.role,
                content=assistant_msg.content,
                created_at=assistant_msg.created_at,
                citations=enriched_citations,
                quick_actions=assistant_msg.quick_actions,
            )
        self._persist_message(session.id, assistant_msg)

        if session.title == "对话预览" and len(trimmed) <= 40:
            session.title = trimmed

        self.db.commit()
        loaded = self._load_session(session.id)
        return self._to_session_dto(loaded)

    def get_public_attachment_extracted_text(
        self, attachment_id: uuid.UUID
    ):
        from app.db.models.attachment import Attachment
        from app.db.models.standard import Standard
        from app.processing.service import ProcessingService

        attachment = self.db.get(Attachment, attachment_id)
        if attachment is None:
            raise ApiBusinessError("NOT_FOUND", "文档不存在", 404)

        standard = self.db.get(Standard, attachment.standard_id)
        if standard is None or standard.stand_type != "COURSE_AGENT":
            raise ApiBusinessError("FORBIDDEN", "无权访问该文档", 403)

        result = ProcessingService(self.db).get_extracted_text(attachment_id)
        if result is None:
            raise ApiBusinessError("TEXT_NOT_FOUND", "文档尚未完成解析", 404)
        return result

    def verify_embed_access(
        self, agent_id: str, embed_key: str | None, origin: str | None
    ) -> None:
        row = self._get_agent_row(agent_id)
        embed = (row.config_json or {}).get("embed") or {}
        expected = embed.get("embedKey")
        if expected and embed_key and embed_key != expected:
            raise ApiBusinessError("FORBIDDEN", "embedKey 无效", 403)
        allowed = embed.get("allowedOrigins") or []
        # 仅嵌入 widget（带 X-Embed-Key）时校验来源域名；独立 /chat 页不限制
        if embed_key and allowed and origin:
            if not any(origin.startswith(o.rstrip("/")) for o in allowed):
                raise ApiBusinessError("FORBIDDEN", "来源域名未授权", 403)

    def _get_agent_row(
        self, agent_id: str, *, require_active: bool = True
    ) -> CourseAgentRecord:
        row = self.db.get(CourseAgentRecord, agent_id)
        if row is None:
            raise ApiBusinessError("NOT_FOUND", f"Agent {agent_id} 不存在", 404)
        if require_active and row.status != "active":
            raise ApiBusinessError(
                "AGENT_INACTIVE",
                "Agent 未启用（当前为草稿/停用）。管理端请用「预览对话」；公开对话页需先将状态设为启用。",
                400,
            )
        return row

    def _load_session(self, session_id: uuid.UUID) -> CourseAgentSessionRecord | None:
        return self.db.scalar(
            select(CourseAgentSessionRecord)
            .where(CourseAgentSessionRecord.id == session_id)
            .options(selectinload(CourseAgentSessionRecord.messages))
        )

    def _build_rag_query(self, user_text: str, state: SessionState) -> str:
        parts = [user_text.strip()]
        if state.role == "student":
            parts.append("暑期班 课程安排 上课时间")
        elif state.role == "teacher":
            parts.append("教师培训 研修班 开课时间")
        elif state.role == "org":
            parts.append("机构合作 课程方案")

        constraints = state.constraints or {}
        for key in ("date", "city", "format", "goal", "budget"):
            value = constraints.get(key)
            if value:
                parts.append(str(value))

        if state.recommended_courses:
            parts.extend(state.recommended_courses)
        if state.locked_course:
            parts.append(state.locked_course)

        return " ".join(p for p in parts if p)

    def _persist_message(
        self,
        session_id: uuid.UUID,
        msg: AgentMessage,
        *,
        lead_id: uuid.UUID | None = None,
    ) -> None:
        self.db.add(
            CourseAgentMessageRecord(
                session_id=session_id,
                lead_id=lead_id,
                role=msg.role,
                content=msg.content,
                citations_json=[c.to_dict() for c in msg.citations]
                if msg.citations
                else None,
                quick_actions_json=msg.quick_actions,
            )
        )
        if lead_id is not None:
            lead = self.db.get(CourseAgentLeadRecord, lead_id)
            if lead is not None:
                lead.message_count = int(lead.message_count or 0) + 1
                lead.updated_at = datetime.now(UTC)

    def _record_to_agent_message(self, rec: CourseAgentMessageRecord) -> AgentMessage:
        citations = None
        if rec.citations_json:
            citations = [
                Citation(
                    c["document"],
                    c["chapter"],
                    attachment_id=c.get("attachmentId"),
                    chunk_id=c.get("chunkId"),
                )
                for c in rec.citations_json
            ]
        return AgentMessage(
            id=str(rec.id),
            role=rec.role,
            content=rec.content,
            created_at=_iso(rec.created_at),
            citations=citations,
            quick_actions=list(rec.quick_actions_json) if rec.quick_actions_json else None,
        )

    def _to_summary(self, row: CourseAgentRecord) -> CourseAgentSummaryDto:
        cfg = row.config_json or {}
        return CourseAgentSummaryDto(
            agentId=row.agent_id,
            name=row.name,
            description=row.description,
            status=row.status,
            agentType=_read_agent_type(cfg),
            isDefault=_is_default_agent(cfg),
            updatedAt=_iso(row.updated_at),
        )

    def _to_config_dto(self, row: CourseAgentRecord) -> CourseAgentConfigDto:
        cfg = dict(row.config_json or {})
        model_svc = ModelService(self.db)
        material_svc = MaterialService(self.db)

        models = model_svc.list_models(row.agent_id)
        knowledge_bases = material_svc.ensure_agent_materials(row.agent_id)
        runtime = model_svc.get_runtime_model(row.agent_id)
        active_id = model_svc.get_active_model_id(row.agent_id)

        conversation = dict(cfg.get("conversation") or {})
        if _read_agent_type(cfg) == "basic":
            from app.course_agent.llm_helper import resolve_system_prompt

            conversation["systemPrompt"] = resolve_system_prompt(conversation)

        return CourseAgentConfigDto(
            agentId=row.agent_id,
            name=row.name,
            description=row.description,
            status=row.status,
            agentType=_read_agent_type(cfg),
            isDefault=_is_default_agent(cfg),
            temperature=float(cfg.get("temperature") if cfg.get("temperature") is not None else 0.3),
            boundKnowledgeBaseIds=[
                str(item) for item in (cfg.get("boundKnowledgeBaseIds") or []) if str(item).strip()
            ],
            boundModelIds=[
                str(item) for item in (cfg.get("boundModelIds") or []) if str(item).strip()
            ],
            model=runtime,
            activeModelId=active_id,
            models=models,
            stateMachine=cfg.get("stateMachine") or [],
            workflowGraph=cfg.get("workflowGraph"),
            knowledgeBases=knowledge_bases,
            embed=cfg.get("embed") or {"embedKey": ""},
            conversation=conversation,
            updatedAt=_iso(row.updated_at),
        )

    def _to_session_dto(self, row: CourseAgentSessionRecord) -> CourseAgentSessionDto:
        is_preview = bool(
            ((row.constraints_json or {}).get("_workflow") or {}).get("isPreview")
        ) or row.title == "对话预览" or row.step == "preview"

        active_lead_id: uuid.UUID | None = None
        if not is_preview:
            open_lead = self.leads.get_open_lead(row.id)
            if open_lead is not None:
                active_lead_id = open_lead.id

        messages = []
        for m in row.messages:
            # 公开对话只展示当前咨询线索的消息，重新开始后对话框被清空
            if active_lead_id is not None and m.lead_id != active_lead_id:
                continue
            citations = m.citations_json
            if citations and m.role == "assistant":
                parsed = [
                    Citation(
                        c["document"],
                        c["chapter"],
                        attachment_id=c.get("attachmentId"),
                        chunk_id=c.get("chunkId"),
                    )
                    for c in citations
                ]
                enriched = enrich_citations_with_attachments(
                    self.db, row.agent_id, parsed
                )
                if enriched:
                    citations = [c.to_dict() for c in enriched]
            messages.append(
                CourseAgentMessageDto(
                    id=str(m.id),
                    role=m.role,
                    content=m.content,
                    createdAt=_iso(m.created_at),
                    citations=citations,
                    quickActions=list(m.quick_actions_json)
                    if m.quick_actions_json
                    else None,
                )
            )
        state = CourseAgentSessionStateDto(
            step=row.step,
            role=row.role,
            constraints=row.constraints_json or {},
            recommendedCourses=list(row.recommended_courses or []),
            lockedCourse=row.locked_course,
        )
        return CourseAgentSessionDto(
            id=str(row.id),
            agentId=row.agent_id,
            title=row.title,
            messages=messages,
            state=state,
            createdAt=_iso(row.created_at),
            updatedAt=_iso(row.updated_at),
        )
