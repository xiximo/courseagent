import sys
from functools import lru_cache
from typing import Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_VECTOR_STORE = "faiss" if sys.platform == "win32" else "milvus"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "courseagent-backend"
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8080
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    jwt_secret: str = "dev-secret-change-in-production"
    jwt_expire_seconds: int = 86400
    init_admin_username: str = "admin"
    init_admin_password: str = "admin123"

    database_url: str = (
        "postgresql+psycopg2://postgres:password@127.0.0.1:5432/course"
    )

    # 对象存储：local（默认，本地目录）| minio
    storage_backend: str = "local"
    local_storage_root: str = "./data/attachments"
    local_storage_bucket: str = "course-attachments"

    minio_endpoint: str = "127.0.0.1:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "course-attachments"
    minio_secure: bool = False

    sprs_base_url: str = "https://srms.foton.com.cn"
    sprs_timeout_seconds: int = 60
    sprs_page_size: int = 10
    sprs_max_pages: int | None = None
    sprs_default_stand_type: str = "INLAND"
    sprs_download_attachments: bool = True
    sprs_tls_verify: bool = True
    sprs_tls_legacy_ciphers: bool = True

    docling_worker_enabled: bool = False
    docling_worker_url: str = "http://127.0.0.1:8090"
    docling_worker_timeout_seconds: int = 3600
    docling_worker_token: str = ""
    docling_worker_ocr: bool = True
    docling_worker_device: str = ""
    docling_fallback_on_no_text_layer: bool = True
    docling_fallback_on_likely_scanned: bool = False
    docling_worker_describe_figures: bool = True

    embedding_mode: str = "inline"
    embedding_enabled: bool = True
    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    embedding_vector_store: str = _DEFAULT_VECTOR_STORE
    milvus_lite_path: str = ""
    faiss_index_path: str = ""
    embedding_index_batch_size: int = 64
    embedding_worker_enabled: bool = False
    embedding_worker_url: str = "http://127.0.0.1:8091"
    embedding_worker_timeout_seconds: int = 600
    embedding_worker_token: str = ""
    index_auto_on_chunk: bool = False

    llm_enabled: bool = True
    doubao_api_key: str = ""
    doubao_model_name: str = "doubao-seed-2-0-pro-260215"
    doubao_endpoint_id: str = ""
    doubao_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    llm_timeout_seconds: int = 120
    qa_retrieval_top_k: int = 8

    @model_validator(mode="after")
    def normalize_embedding_config(self) -> Self:
        if self.embedding_worker_enabled:
            self.embedding_mode = "worker"
            self.embedding_enabled = True
        self.embedding_vector_store = (self.embedding_vector_store or _DEFAULT_VECTOR_STORE).strip().lower()
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
