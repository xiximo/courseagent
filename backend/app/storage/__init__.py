from functools import lru_cache

from app.config import Settings, get_settings
from app.storage.base import ObjectStorage


def build_storage(settings: Settings | None = None) -> ObjectStorage:
    """按配置构造存储实现（不缓存，便于传入自定义 Settings）。"""
    cfg = settings or get_settings()
    backend = (cfg.storage_backend or "local").strip().lower()
    if backend == "minio":
        from app.storage.minio_client import MinioStorage

        return MinioStorage(cfg)
    from app.storage.local_client import LocalFileStorage

    return LocalFileStorage(cfg)


@lru_cache
def get_storage() -> ObjectStorage:
    """POC 默认本地目录；设置 STORAGE_BACKEND=minio 可切回 MinIO。"""
    storage = build_storage(get_settings())
    storage.ensure_bucket()
    return storage


# 兼容旧导入名
def get_minio_storage() -> ObjectStorage:
    return get_storage()
