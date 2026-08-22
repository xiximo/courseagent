from app.services.persona_users import PERSONA_USERS, TEST_USER_PASSWORD


def test_persona_users_cover_core_profiles():
    personas = {item["profile"]["persona"] for item in PERSONA_USERS}
    assert personas == {"fat_loss", "muscle_gain", "chronic_care", "platform"}
    usernames = [item["username"] for item in PERSONA_USERS]
    assert usernames == ["fatloss", "muscle", "wellness", "member"]
    assert TEST_USER_PASSWORD == "test1234"
    for item in PERSONA_USERS:
        assert item["profile"]["sampleQuestions"]
        assert item["roleCodes"] == ["end_user"]
