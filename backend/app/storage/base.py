"""对象存储抽象：POC 默认本地目录，可选 MinIO。"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class ObjectStorage(Protocol):
    bucket: str

    def ensure_bucket(self) -> None: ...

    def build_object_key(self, sprs_file_id: str, file_name: str) -> str: ...

    def put_bytes(
        self,
        object_key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> int: ...

    def get_bytes(self, object_key: str) -> bytes: ...

    def exists(self, object_key: str) -> bool: ...

    def remove_object(self, object_key: str) -> None: ...

    def remove_prefix(self, prefix: str) -> int: ...

    def list_keys(self, prefix: str = "") -> list[str]: ...
