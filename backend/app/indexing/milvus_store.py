"""Milvus Lite 向量存储。"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

from pymilvus import MilvusClient
from pymilvus.exceptions import MilvusException

logger = logging.getLogger(__name__)

COLLECTION_NAME = "text_chunks"
_store_lock = threading.Lock()


class MilvusVectorStore:
    def __init__(
        self,
        *,
        db_path: str,
        dimension: int,
        metric_type: str = "COSINE",
    ) -> None:
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = str(path)
        self._dimension = dimension
        self._metric_type = metric_type
        self._client = MilvusClient(self.db_path)
        self._ensure_collection()

    @property
    def client(self) -> MilvusClient:
        return self._client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None  # type: ignore[assignment]

    def _ensure_collection(self) -> None:
        if self._client.has_collection(COLLECTION_NAME):
            self._ensure_loaded()
            logger.info(
                "Milvus Lite collection exists: %s @ %s",
                COLLECTION_NAME,
                self.db_path,
            )
            return

        self._create_collection()
        self._ensure_loaded()

    def _create_collection(self) -> None:
        self._client.create_collection(
            collection_name=COLLECTION_NAME,
            dimension=self._dimension,
            metric_type=self._metric_type,
            auto_id=False,
            id_type="string",
            max_length=64,
            enable_dynamic_field=True,
            primary_field_name="id",
            vector_field_name="vector",
        )
        logger.info("Milvus Lite collection ready: %s @ %s", COLLECTION_NAME, self.db_path)

    def _ensure_loaded(self) -> None:
        try:
            self._client.load_collection(collection_name=COLLECTION_NAME)
        except MilvusException as exc:
            message = str(exc).lower()
            if "already loaded" in message or "loaded" in message:
                return
            raise

    def replace_attachment_vectors(
        self,
        attachment_id: str,
        row_batches: list[list[dict[str, Any]]],
    ) -> int:
        with _store_lock:
            return self._write_attachment_vectors(attachment_id, row_batches)

    def _write_attachment_vectors(
        self,
        attachment_id: str,
        row_batches: list[list[dict[str, Any]]],
    ) -> int:
        self._ensure_loaded()
        rows = [row for batch in row_batches for row in batch]
        if not rows:
            self._client.delete(
                collection_name=COLLECTION_NAME,
                filter=f'attachment_id == "{attachment_id}"',
            )
            return 0

        self._client.delete(
            collection_name=COLLECTION_NAME,
            filter=f'attachment_id == "{attachment_id}"',
        )
        self._client.upsert(collection_name=COLLECTION_NAME, data=rows)
        return len(rows)

    def upsert(self, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        with _store_lock:
            self._ensure_loaded()
            self._client.upsert(collection_name=COLLECTION_NAME, data=rows)
        return len(rows)

    def delete_by_attachment(self, attachment_id: str) -> int:
        with _store_lock:
            self._ensure_loaded()
            result = self._client.delete(
                collection_name=COLLECTION_NAME,
                filter=f'attachment_id == "{attachment_id}"',
            )
        if isinstance(result, dict):
            return int(result.get("delete_count", 0) or 0)
        return 0

    def search(
        self,
        query_vector: list[float],
        *,
        top_k: int = 10,
        filters: str | None = None,
        filter_fields: dict[str, str] | None = None,
        output_fields: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        if filters is None and filter_fields:
            filters = " and ".join(
                f'{key} == "{value}"' for key, value in filter_fields.items()
            )
        fields = output_fields or [
            "chunk_id",
            "attachment_id",
            "standard_id",
            "chunk_type",
            "doc_role",
            "position_label",
            "content",
            "index_version",
        ]
        with _store_lock:
            self._ensure_loaded()
            results = self._client.search(
                collection_name=COLLECTION_NAME,
                data=[query_vector],
                filter=filters or "",
                limit=top_k,
                output_fields=fields,
            )
        hits: list[dict[str, Any]] = []
        for batch in results:
            for item in batch:
                entity = dict(item.get("entity", {}))
                entity["distance"] = item.get("distance")
                entity["score"] = item.get("distance")
                hits.append(entity)
        return hits


_store: MilvusVectorStore | None = None
_store_key: tuple[str, int] | None = None


def get_milvus_store(*, db_path: str, dimension: int) -> MilvusVectorStore:
    global _store, _store_key
    with _store_lock:
        key = (db_path, dimension)
        if _store is None or _store_key != key:
            if _store is not None:
                _store.close()
            _store = MilvusVectorStore(db_path=db_path, dimension=dimension)
            _store_key = key
        return _store


def reset_store() -> None:
    global _store, _store_key
    with _store_lock:
        if _store is not None:
            _store.close()
        _store = None
        _store_key = None


def default_milvus_lite_path() -> str:
    backend_root = Path(__file__).resolve().parents[2]
    return str(backend_root / "data" / "milvus_qibiao.db")
