"""本地目录对象存储（比赛 POC，避免依赖 MinIO）。"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


class LocalFileStorage:
    """把 object_key 映射到 `{root}/{bucket}/{object_key}` 文件。"""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.bucket = (settings.local_storage_bucket or "course-attachments").strip()
        root = Path(settings.local_storage_root or "./data/attachments").expanduser()
        if not root.is_absolute():
            # 相对 backend 工作目录
            root = Path.cwd() / root
        self.root = root.resolve()
        self._bucket_dir = self.root / self.bucket

    def ensure_bucket(self) -> None:
        self._bucket_dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, object_key: str) -> Path:
        key = (object_key or "").replace("\\", "/").lstrip("/")
        if not key or ".." in key.split("/"):
            raise ValueError(f"非法对象键: {object_key!r}")
        path = (self._bucket_dir / key).resolve()
        if not str(path).startswith(str(self._bucket_dir.resolve())):
            raise ValueError(f"对象键越界: {object_key!r}")
        return path

    def build_object_key(self, sprs_file_id: str, file_name: str) -> str:
        safe_name = file_name.replace("\\", "_").replace("/", "_").strip() or "file"
        return f"sprs/attachments/{sprs_file_id}/{safe_name}"

    def put_bytes(
        self,
        object_key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> int:
        del content_type  # 本地文件不单独存 content-type
        self.ensure_bucket()
        path = self._path_for(object_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return len(data)

    def get_bytes(self, object_key: str) -> bytes:
        path = self._path_for(object_key)
        if not path.is_file():
            raise FileNotFoundError(f"对象不存在: {object_key}")
        return path.read_bytes()

    def exists(self, object_key: str) -> bool:
        try:
            return self._path_for(object_key).is_file()
        except ValueError:
            return False

    def remove_object(self, object_key: str) -> None:
        path = self._path_for(object_key)
        if path.is_file():
            path.unlink()
            # 清理空目录
            parent = path.parent
            while parent != self._bucket_dir and parent.exists():
                try:
                    parent.rmdir()
                except OSError:
                    break
                parent = parent.parent

    def list_keys(self, prefix: str = "") -> list[str]:
        self.ensure_bucket()
        norm = (prefix or "").replace("\\", "/").lstrip("/")
        base = self._bucket_dir
        if norm:
            base = self._bucket_dir / norm
            if base.is_file():
                return [norm]
            if not base.exists():
                return []
        keys: list[str] = []
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(self._bucket_dir).as_posix()
            keys.append(rel)
        keys.sort()
        return keys

    def remove_prefix(self, prefix: str) -> int:
        keys = self.list_keys(prefix)
        for key in keys:
            self.remove_object(key)
        return len(keys)


@lru_cache
def get_local_storage() -> LocalFileStorage:
    storage = LocalFileStorage(get_settings())
    storage.ensure_bucket()
    logger.info("Local file storage ready: %s", storage._bucket_dir)
    return storage
