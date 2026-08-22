import uuid

from app.course_agent.service import can_access_owned_session


def test_session_requires_matching_owner():
    owner = uuid.uuid4()
    other = uuid.uuid4()
    assert can_access_owned_session(owner, owner)
    assert not can_access_owned_session(owner, None)
    assert not can_access_owned_session(owner, other)
    assert not can_access_owned_session(None, None)
    assert not can_access_owned_session(None, owner)
