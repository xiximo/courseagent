from functools import lru_cache
from io import BytesIO

from minio import Minio
from minio.error import S3Error

from app.config import Settings, get_settings


class MinioStorage:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        self.bucket = settings.minio_bucket

    def ensure_bucket(self) -> None:
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

    def build_object_key(self, sprs_file_id: str, file_name: str) -> str:
        safe_name = file_name.replace("\\", "_").replace("/", "_").strip() or "file"
        return f"sprs/attachments/{sprs_file_id}/{safe_name}"

    def put_bytes(
        self,
        object_key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> int:
        self.ensure_bucket()
        stream = BytesIO(data)
        self.client.put_object(
            self.bucket,
            object_key,
            stream,
            length=len(data),
            content_type=content_type,
        )
        return len(data)

    def get_bytes(self, object_key: str) -> bytes:
        response = self.client.get_object(self.bucket, object_key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def exists(self, object_key: str) -> bool:
        try:
            self.client.stat_object(self.bucket, object_key)
            return True
        except S3Error:
            return False

    def remove_object(self, object_key: str) -> None:
        self.client.remove_object(self.bucket, object_key)

    def list_keys(self, prefix: str = "") -> list[str]:
        if not self.client.bucket_exists(self.bucket):
            return []
        keys: list[str] = []
        for obj in self.client.list_objects(
            self.bucket, prefix=prefix or "", recursive=True
        ):
            if obj.object_name:
                keys.append(obj.object_name)
        return keys

    def remove_prefix(self, prefix: str) -> int:
        """删除 bucket 下指定前缀的全部对象，返回删除数量。"""
        keys = self.list_keys(prefix)
        for key in keys:
            self.client.remove_object(self.bucket, key)
        return len(keys)


@lru_cache
def get_minio_storage() -> MinioStorage:
    return MinioStorage(get_settings())
