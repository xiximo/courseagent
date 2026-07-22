"""WorkflowGraph 解释执行器：画布即运行时控制面。"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from sqlalchemy.orm import Session

from app.course_agent.workflow.conditions import eval_condition, guess_intent_from_text
from app.course_agent.workflow.graph_loader import index_graph, load_workflow_graph
from app.course_agent.workflow.nodes import execute_node
from app.course_agent.workflow.state_store import apply_state_patch
from app.course_agent.workflow.types import (
    AssistantOut,
    NodeOutput,
    TurnInput,
    TurnResult,
    WorkflowRuntimeState,
)

ROLE_ENTRY_ACTIONS = frozenset({"学生课程", "教师培训", "平台服务"})


class WorkflowEngine:
    def __init__(self, db: Session, agent_id: str, config_json: dict | None) -> None:
        self.db = db
        self.agent_id = agent_id
        self.graph = load_workflow_graph(config_json)
        self.nodes, self.edges = index_graph(self.graph)
        self.policies = self.graph.get("policies") or {}
        self.entry_node_id = str(self.graph.get("entryNodeId") or next(iter(self.nodes), ""))

    def create_initial_state(self, *, is_preview: bool = False) -> WorkflowRuntimeState:
        return WorkflowRuntimeState(
            current_node_id=self.entry_node_id,
            is_preview=is_preview,
            awaiting_input=True,
        )

    def bootstrap(self, state: WorkflowRuntimeState) -> TurnResult:
        """会话创建：执行入口节点，发出欢迎语。"""
        messages: list[AssistantOut] = []
        node = self.nodes.get(state.current_node_id)
        if node is None:
            messages.append(AssistantOut(content="流程入口未配置，请检查工作流画布。"))
            return TurnResult(
                state=state,
                user_text="",
                assistant_messages=self._with_node_actions(state, messages),
            )

        output = execute_node(
            db=self.db,
            agent_id=self.agent_id,
            node=node,
            state=state,
            turn=None,
            bootstrap=True,
        )
        if not isinstance(output, NodeOutput):
            # bootstrap 不应流式
            final: NodeOutput | None = None
            for item in output:
                if isinstance(item, NodeOutput):
                    final = item
            output = final or NodeOutput(messages=[], intent="other", wait_for_user=True)
        if output.state_patch:
            apply_state_patch(state, output.state_patch)
        messages.extend(output.messages)
        state.awaiting_input = True
        return TurnResult(
            state=state,
            user_text="",
            assistant_messages=self._with_node_actions(state, messages),
        )

    def handle_turn(self, state: WorkflowRuntimeState, content: str) -> TurnResult:
        result: TurnResult | None = None
        for kind, payload in self.iter_handle_turn(state, content, stream=False):
            if kind == "turn_complete":
                result = payload  # type: ignore[assignment]
        if result is None:
            return TurnResult(state=state, user_text=content, assistant_messages=[])
        return result

    def iter_handle_turn(
        self,
        state: WorkflowRuntimeState,
        content: str,
        *,
        stream: bool = True,
    ) -> Iterator[tuple[str, Any]]:
        """执行一轮对话。

        产出：
        - ("delta", {"text": str}) 模型增量（仅 stream=True 且走 LLM 时）
        - ("turn_complete", TurnResult) 本轮结束
        """
        max_chars = int(self.policies.get("maxInputChars") or 500)
        text = (content or "").strip()
        turn = TurnInput(
            text=text,
            quick_action=text if text else None,
            is_empty=not bool(text),
            too_long=len(text) > max_chars,
            char_count=len(text),
        )

        # 若文案恰好是快捷按钮，记为 quick_action
        turn.quick_action = self._match_quick_action(state, text)

        emitted: list[AssistantOut] = []

        if turn.is_empty:
            emitted.append(AssistantOut(content="请输入您的问题。"))
            yield (
                "turn_complete",
                TurnResult(
                    state=state,
                    user_text=content,
                    assistant_messages=self._with_node_actions(state, emitted),
                ),
            )
            return
        if turn.too_long:
            emitted.append(
                AssistantOut(content=f"输入过长，请精简后重新发送（限 {max_chars} 字）。")
            )
            yield (
                "turn_complete",
                TurnResult(
                    state=state,
                    user_text=content,
                    assistant_messages=self._with_node_actions(state, emitted),
                ),
            )
            return

        # 全局快捷：重新开始 / 查看所有课程 → 跳到 session_control
        global_intent = guess_intent_from_text(text)
        if (
            (global_intent == "restart" and text in ("重新开始", "重来", "reset"))
            or global_intent == "list_courses"
            or text == "查看所有课程"
        ):
            control = self._find_node_by_type("session_control")
            if control:
                state.current_node_id = control["id"]

        title_hint = text if len(text) <= 40 else None
        # 无次数上限；仅用「本轮已执行节点」打断图内死循环（如 A→B→A）
        executed_nodes: set[str] = set()

        while True:
            node_id = state.current_node_id
            if node_id in executed_nodes:
                # 同轮再次进入同一节点：停下来等用户，避免死循环
                if not emitted:
                    emitted.append(
                        AssistantOut(
                            content="暂时无法继续，请换一种问法，或点击页头「重新开始」。"
                        )
                    )
                state.awaiting_input = True
                break
            executed_nodes.add(node_id)

            node = self.nodes.get(node_id)
            if node is None:
                emitted.append(AssistantOut(content="当前流程节点丢失，已停止。请重新开始。"))
                state.awaiting_input = True
                break

            raw = execute_node(
                db=self.db,
                agent_id=self.agent_id,
                node=node,
                state=state,
                turn=turn,
                bootstrap=False,
                stream=stream,
            )
            if isinstance(raw, NodeOutput):
                output = raw
            else:
                output = None
                for item in raw:
                    if isinstance(item, NodeOutput):
                        output = item
                    else:
                        yield ("delta", {"text": str(item)})
                if output is None:
                    output = NodeOutput(
                        messages=[AssistantOut(content="模型暂时不可用，请稍后重试。")],
                        intent="other",
                        wait_for_user=True,
                    )

            if output.state_patch:
                apply_state_patch(state, output.state_patch)
            emitted.extend(output.messages)

            if output.wait_for_user:
                state.awaiting_input = True
                break

            edge = self._select_edge(state, turn, output)
            if edge is None:
                if not emitted:
                    emitted.append(
                        AssistantOut(
                            content="暂时无法继续，请点击「重新开始」或联系人工客服。"
                        )
                    )
                state.awaiting_input = True
                break

            apply_state_patch(
                state, edge.get("apply") if isinstance(edge.get("apply"), dict) else None
            )
            target = str(edge.get("target") or "")
            if not target or target not in self.nodes:
                emitted.append(AssistantOut(content="流程边目标无效，请检查画布配置。"))
                state.awaiting_input = True
                break

            # 自环且不等待：视为本轮结束，避免空转
            if target == node_id:
                if not emitted:
                    emitted.append(
                        AssistantOut(
                            content="已收到。请继续提问，或点击页头「重新开始」。"
                        )
                    )
                state.awaiting_input = True
                break

            state.current_node_id = target

            # 跳转后消费本轮控制信号，避免目标节点用同一 quick_action 再次跳出
            # 查看所有课程需保留文案，供 session_control 识别并生成目录
            consumed_qa = turn.quick_action
            turn.quick_action = None
            if turn.text.strip() in ROLE_ENTRY_ACTIONS:
                turn.text = ""
            elif consumed_qa == "查看所有课程" or turn.text.strip() == "查看所有课程":
                # 保留 text，供控制节点列出内容
                pass

        yield (
            "turn_complete",
            TurnResult(
                state=state,
                user_text=content,
                assistant_messages=self._with_node_actions(state, emitted),
                title_hint=title_hint,
            ),
        )

    def _node_quick_actions(self, node_id: str | None) -> list[str]:
        """读取画布节点 config.quickActions（按图配置展示）。"""
        if not node_id:
            return []
        node = self.nodes.get(node_id)
        if not node or not isinstance(node.get("config"), dict):
            return []
        out: list[str] = []
        for item in node["config"].get("quickActions") or []:
            text = str(item).strip()
            if text and text not in out:
                out.append(text)
        return out

    def _all_graph_quick_actions(self) -> set[str]:
        known: set[str] = set()
        for node in self.nodes.values():
            cfg = node.get("config") if isinstance(node.get("config"), dict) else {}
            for item in cfg.get("quickActions") or []:
                text = str(item).strip()
                if text:
                    known.add(text)
        return known

    def _with_node_actions(
        self, state: WorkflowRuntimeState, messages: list[AssistantOut]
    ) -> list[AssistantOut]:
        """回复下方按钮以当前等待节点的图配置为准。"""
        node_actions = self._node_quick_actions(state.current_node_id)
        enriched: list[AssistantOut] = []
        for msg in messages:
            # 节点配置优先；若节点未配则保留消息自带按钮
            actions = list(node_actions) if node_actions else [
                str(a).strip() for a in (msg.quick_actions or []) if str(a).strip()
            ]
            enriched.append(
                AssistantOut(
                    content=msg.content,
                    citations=msg.citations,
                    quick_actions=actions or None,
                )
            )
        return enriched

    def _select_edge(
        self,
        state: WorkflowRuntimeState,
        turn: TurnInput,
        output: Any,
    ) -> dict[str, Any] | None:
        min_c = int(self.policies.get("minConstraintsForRecommend") or 2)
        candidates = [
            e
            for e in self.edges
            if e.get("source") == state.current_node_id
        ]
        candidates.sort(key=lambda e: int(e.get("priority") or 100))
        for edge in candidates:
            when = edge.get("when") if isinstance(edge.get("when"), dict) else {"type": "always"}
            if eval_condition(
                when,
                state=state,
                turn=turn,
                output=output,
                min_constraints_fallback=min_c,
            ):
                return edge
        return None

    def _match_quick_action(self, state: WorkflowRuntimeState, text: str) -> str | None:
        if not text:
            return None
        # 图中任意节点配置过的快捷文案均可识别（含当前节点）
        known = self._all_graph_quick_actions()
        known.update(
            {
                "学生课程",
                "教师培训",
                "平台服务",
                "重新开始",
                "查看所有课程",
                "了解报名方式",
            }
        )
        return text if text in known else None

    def _find_node_by_type(self, ntype: str) -> dict[str, Any] | None:
        for node in self.nodes.values():
            if node.get("type") == ntype:
                return node
        return None
