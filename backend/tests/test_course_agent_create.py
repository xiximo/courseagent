from app.course_agent.service import _read_agent_type


def test_read_agent_type_default():
    assert _read_agent_type({}) == "workflow"


def test_read_agent_type_from_config():
    assert _read_agent_type({"agentType": "basic"}) == "basic"
    assert _read_agent_type({"_meta": {"agentType": "autonomous"}}) == "autonomous"
