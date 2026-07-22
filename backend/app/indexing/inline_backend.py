"""进程内向量化与本地向量索引。"""



from __future__ import annotations



import logging

import time

import uuid



from app.config import get_settings

from app.indexing.engine import embed_texts, embedding_dimension

from app.indexing.faiss_store import default_faiss_index_path, get_faiss_store

from app.indexing.milvus_store import default_milvus_lite_path, get_milvus_store

from app.indexing.types import (

    EmbeddingBackendError,

    IndexChunkPayload,

    IndexChunksResult,

    SearchHit,

    SearchResult,

)



logger = logging.getLogger(__name__)





def _resolve_milvus_path() -> str:

    settings = get_settings()

    configured = (settings.milvus_lite_path or "").strip()

    return configured or default_milvus_lite_path()





def _resolve_faiss_path() -> str:

    settings = get_settings()

    configured = (settings.faiss_index_path or "").strip()

    return configured or default_faiss_index_path()





def _get_store():

    settings = get_settings()

    dim = embedding_dimension(settings.embedding_model)

    store_kind = settings.embedding_vector_store

    if store_kind == "milvus":

        return get_milvus_store(db_path=_resolve_milvus_path(), dimension=dim)

    if store_kind == "faiss":

        return get_faiss_store(base_path=_resolve_faiss_path(), dimension=dim)

    raise EmbeddingBackendError(f"不支持的向量存储: {store_kind}")





def _build_filter_fields(

    *,

    standard_id: str | None,

    attachment_id: str | None,

    chunk_type: str | None,

    doc_role: str | None,

) -> dict[str, str]:

    fields: dict[str, str] = {}

    if standard_id:

        fields["standard_id"] = standard_id

    if attachment_id:

        fields["attachment_id"] = attachment_id

    if chunk_type:

        fields["chunk_type"] = chunk_type

    if doc_role:

        fields["doc_role"] = doc_role

    return fields





def _build_milvus_filter(filter_fields: dict[str, str]) -> str:

    parts = [f'{key} == "{value}"' for key, value in filter_fields.items()]

    return " and ".join(parts)





def index_chunks_inline(

    *,

    standard_id: str,

    attachment_id: str,

    index_version: int,

    chunks: list[IndexChunkPayload],

    job_id: str | None = None,

) -> IndexChunksResult:

    if not chunks:

        raise EmbeddingBackendError("没有可索引的切片")



    settings = get_settings()

    started = time.perf_counter()

    store = _get_store()



    batch_size = max(1, settings.embedding_index_batch_size)

    row_batches: list[list[dict[str, object]]] = []

    for start in range(0, len(chunks), batch_size):

        batch = chunks[start : start + batch_size]

        vectors = embed_texts(

            [item.content for item in batch],

            model_name=settings.embedding_model,

        )

        rows = []

        for item, vector in zip(batch, vectors, strict=True):

            meta = item.metadata or {}

            content = item.content.strip()

            rows.append(

                {

                    "id": item.chunk_id,

                    "vector": vector,

                    "chunk_id": item.chunk_id,

                    "attachment_id": attachment_id,

                    "standard_id": standard_id,

                    "chunk_type": str(meta.get("chunk_type") or "clause"),

                    "doc_role": str(meta.get("doc_role") or "body"),

                    "position_label": str(meta.get("position_label") or ""),

                    "content": content[:8000],

                    "index_version": index_version,

                }

            )

        row_batches.append(rows)



    indexed = store.replace_attachment_vectors(attachment_id, row_batches)

    logger.info(

        "Indexed %s chunks for attachment %s in %.3fs",

        indexed,

        attachment_id,

        time.perf_counter() - started,

    )



    return IndexChunksResult(

        job_id=job_id or str(uuid.uuid4()),

        indexed_count=indexed,

        index_version=index_version,

        elapsed_sec=round(time.perf_counter() - started, 3),

    )





def delete_attachment_index_inline(attachment_id: str) -> int:

    store = _get_store()

    return store.delete_by_attachment(attachment_id)





def semantic_search_inline(

    query: str,

    *,

    top_k: int = 10,

    standard_id: str | None = None,

    attachment_id: str | None = None,

    chunk_type: str | None = None,

    doc_role: str | None = None,

) -> SearchResult:

    keyword = query.strip()

    if not keyword:

        raise EmbeddingBackendError("query 不能为空")



    settings = get_settings()

    started = time.perf_counter()

    vector = embed_texts([keyword], model_name=settings.embedding_model)[0]

    store = _get_store()

    filter_fields = _build_filter_fields(

        standard_id=standard_id,

        attachment_id=attachment_id,

        chunk_type=chunk_type,

        doc_role=doc_role,

    )

    search_kwargs: dict[str, object] = {

        "top_k": top_k,

        "filter_fields": filter_fields or None,

    }

    if settings.embedding_vector_store == "milvus":

        search_kwargs["filters"] = _build_milvus_filter(filter_fields) or None



    raw_hits = store.search(vector, **search_kwargs)

    hits = [

        SearchHit(

            chunk_id=str(item.get("chunk_id") or item.get("id") or ""),

            score=item.get("score"),

            attachment_id=item.get("attachment_id"),

            standard_id=item.get("standard_id"),

            chunk_type=item.get("chunk_type"),

            doc_role=item.get("doc_role"),

            position_label=item.get("position_label") or None,

            content=item.get("content"),

            index_version=item.get("index_version"),

        )

        for item in raw_hits

        if item.get("chunk_id") or item.get("id")

    ]

    return SearchResult(

        query=keyword,

        hits=hits,

        elapsed_sec=round(time.perf_counter() - started, 3),

    )

