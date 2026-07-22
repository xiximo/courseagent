from app.course_agent.state_machine import (
    AgentMessage,
    create_initial_state,
    create_welcome_message,
    process_message,
)


def test_welcome_message_has_quick_actions():
    msg = create_welcome_message()
    assert msg.role == "assistant"
    assert msg.quick_actions


def test_identity_gate_before_recommend():
    state = create_initial_state()
    messages: list[AgentMessage] = [create_welcome_message()]
    state, messages, _ = process_message(state, messages, "推荐个便宜的班")
    assert state.step == "identity"
    assert "家长" in messages[-1].content or "身份" in messages[-1].content


def test_student_recommend_flow():
    state = create_initial_state()
    messages: list[AgentMessage] = [create_welcome_message()]
    state, messages, _ = process_message(
        state, messages, "我是家长，孩子在北京，7月有空，想线下学 AI"
    )
    assert state.role == "student"
    assert state.recommended_courses or state.step == "constraints"

