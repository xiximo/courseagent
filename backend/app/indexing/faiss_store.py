"""本地 FAISS 向量存储（Windows 友好，无 Milvus Lite WAL 问题）。"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any

import faiss
import numpy as np

logger = logging.getLogger(__name__)

_store_lock = threading.Lock()


def _matches_filter(record: dict[str, Any], filter_fields: dict[str, str]) -> bool:
    for key, value in filter_fields.items():
        if str(record.get(key) or "") != value:
            return False
    return True


class FaissVectorStore:
    def __init__(self, *, base_path: str, dimension: int) -> None:
        self.base_path = Path(base_path)
        self.base_path.parent.mkdir(parents=True, exist_ok=True)
        self.index_file = self.base_path.with_suffix(".faiss")
        self.meta_file = self.base_path.with_suffix(".meta.json")
        self._dimension = dimension
        self._records: list[dict[str, Any]] = []
        self._index: faiss.IndexFlatIP | None = None
        self._load()

    def _load(self) -> None:
        if self.meta_file.exists():
            self._records = json.loads(self.meta_file.read_text(encoding="utf-8"))
        if self.index_file.exists() and self._records:
            self._index = faiss.read_index(str(self.index_file))
            for i, record in enumerate(self._records):
                if "vector" not in record:
                    record["vector"] = self._index.reconstruct(i).tolist()
        else:
            self._index = faiss.IndexFlatIP(self._dimension)
            self._records = []

    def _save(self) -> None:
        self.base_path.parent.mkdir(parents=True, exist_ok=True)
        if self._index is not None:
            faiss.write_index(self._index, str(self.index_file))
        meta = [{k: v for k, v in record.items() if k != "vector"} for record in self._records]
        self.meta_file.write_text(
            json.dumps(meta, ensure_ascii=False),
            encoding="utf-8",
        )

    def _rebuild_index(self) -> None:
        self._index = faiss.IndexFlatIP(self._dimension)
        if not self._records:
            return
        matrix = np.array(
            [record["vector"] for record in self._records],
            dtype=np.float32,
        )
        faiss.normalize_L2(matrix)
        self._index.add(matrix)

    def replace_attachment_vectors(
        self,
        attachment_id: str,
        row_batches: list[list[dict[str, Any]]],
    ) -> int:
        rows = [row for batch in row_batches for row in batch]
        with _store_lock:
            self._records = [
                record
                for record in self._records
                if record.get("attachment_id") != attachment_id
            ]
            for row in rows:
                record = dict(row)
                record["vector"] = list(record["vector"])
                self._records.append(record)
            self._rebuild_index()
            self._save()
        logger.info(
            "FAISS indexed %s chunks for attachment %s @ %s",
            len(rows),
            attachment_id,
            self.base_path,
        )
        return len(rows)

    def delete_by_attachment(self, attachment_id: str) -> int:
        with _store_lock:
            before = len(self._records)
            self._records = [
                record
                for record in self._records
                if record.get("attachment_id") != attachment_id
            ]
            removed = before - len(self._records)
            if removed:
                self._rebuild_index()
                self._save()
        return removed

    def search(
        self,
        query_vector: list[float],
        *,
        top_k: int = 10,
        filter_fields: dict[str, str] | None = None,
        filters: str | None = None,
        output_fields: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        del filters
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
            if not self._records or self._index is None or self._index.ntotal == 0:
                return []

            query = np.array([query_vector], dtype=np.float32)
            faiss.normalize_L2(query)
            candidate_k = min(max(top_k * 5, top_k), len(self._records))
            scores, ids = self._index.search(query, candidate_k)

            hits: list[dict[str, Any]] = []
            for idx, score in zip(ids[0], scores[0], strict=False):
                if idx < 0:
                    continue
                record = self._records[idx]
                if filter_fields and not _matches_filter(record, filter_fields):
                    continue
                hit = {field: record.get(field) for field in fields}
                hit["chunk_id"] = record.get("chunk_id") or record.get("id")
                hit["score"] = float(score)
                hit["distance"] = float(score)
                hits.append(hit)
                if len(hits) >= top_k:
                    break
        return hits


_store: FaissVectorStore | None = None
_store_key: tuple[str, int] | None = None


def default_faiss_index_path() -> str:
    backend_root = Path(__file__).resolve().parents[2]
    return str(backend_root / "data" / "vector_index")


def get_faiss_store(*, base_path: str, dimension: int) -> FaissVectorStore:
    global _store, _store_key
    with _store_lock:
        key = (base_path, dimension)
        if _store is None or _store_key != key:
            _store = FaissVectorStore(base_path=base_path, dimension=dimension)
            _store_key = key
        return _store
