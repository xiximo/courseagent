"""平台重置密码用的测试口令；旧版营养画像账号不再预置。"""

from __future__ import annotations

from typing import Any

TEST_USER_PASSWORD = "test1234"

# 启动时删除这些遗留预置账号，不再重新创建。
LEGACY_PERSONA_USERNAMES = ("fatloss", "muscle", "wellness", "member")

PERSONA_USERS: list[dict[str, Any]] = []
