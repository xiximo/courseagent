from app.services.persona_users import (
    LEGACY_PERSONA_USERNAMES,
    PERSONA_USERS,
    TEST_USER_PASSWORD,
)


def test_persona_users_are_not_seeded():
    assert PERSONA_USERS == []
    assert LEGACY_PERSONA_USERNAMES == ("fatloss", "muscle", "wellness", "member")
    assert TEST_USER_PASSWORD == "test1234"
