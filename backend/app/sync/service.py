from __future__ import annotations

import hashlib
import io
import logging
import uuid
import zipfile
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.models.sprs_config import SprsConfigRecord
from app.db.models.sync_job_log import SyncLogLevel
from app.db.models.attachment import (
    Attachment,
    AttachmentDownloadStatus,
    AttachmentParseStatus,
)
from app.db.models.standard import Standard, StandardSyncStatus
from app.db.models.sync_job import (
    SyncJob,
    SyncJobStatus,
    SyncMode,
    SyncTriggerType,
)
from app.sync.attachment_parser import (
    AttachmentRef,
    extract_attachment_refs,
    guess_file_type,
)
from app.services.sprs_settings import get_or_create_sprs_config
from app.sync.errors import SprsError
from app.sync.job_logger import append_sync_log
from app.sync.mapper import apply_sprs_record
from app.sync.sprs_client import SprsClient
from app.storage import build_storage
from app.storage.base import ObjectStorage

logger = logging.getLogger(__name__)


def _standard_label(item: dict) -> str:
    sprs_id = str(item.get("id") or "?")
    name = (item.get("standName") or "").strip()
    if name:
        display = name if len(name) <= 36 else f"{name[:36]}…"
        return f"{display} [{sprs_id}]"
    return sprs_id


def _attachment_label(ref: AttachmentRef) -> str:
    return ref.display_name or ref.sprs_file_id


class SyncService:
    def __init__(
        self,
        db: Session,
        settings: Settings | None = None,
        sprs: SprsClient | None = None,
        storage: ObjectStorage | None = None,
    ) -> None:
        self.db = db
        self.settings = settings or get_settings()
        self.runtime_config: SprsConfigRecord = get_or_create_sprs_config(db)
        self.sprs = sprs or SprsClient(
            self.settings,
            base_url=self.runtime_config.base_url,
            timeout_seconds=self.runtime_config.timeout_seconds,
        )
        self.storage = storage or build_storage(self.settings)

    def _record_item_failure(
        self,
        job_id: uuid.UUID,
        item: dict,
        exc: Exception,
        *,
        action: str,
    ) -> SyncJob:
        self.db.rollback()
        job = self.db.get(SyncJob, job_id)
        if not job:
            raise ValueError("同步任务不存在") from exc
        job.failed_count += 1
        append_sync_log(
            self.db,
            job.id,
            f"{action} {_standard_label(item)} 失败: {exc}",
            SyncLogLevel.warn,
        )
        self.db.commit()
        return job

    @staticmethod
    def _normalize_max_pages(value: int | None) -> int | None:
        if value is None or value <= 0:
            return None
        return value

    def _page_cap(self, job: SyncJob) -> int | None:
        return self._normalize_max_pages(job.max_pages)

    def _page_window(self, job: SyncJob, remote_total: int) -> tuple[int, int]:
        start_page = max(1, job.start_page or 1)
        page_cap = self._page_cap(job)
        if page_cap is None:
            end_page = remote_total
        else:
            end_page = min(remote_total, start_page + page_cap - 1)
        return start_page, end_page

    def _log_page_window(
        self,
        job: SyncJob,
        *,
        start_page: int,
        end_page: int,
        remote_total: int,
        action: str,
    ) -> None:
        page_cap = self._page_cap(job)
        if start_page > remote_total:
            append_sync_log(
                self.db,
                job.id,
                f"开始页 {start_page} 已超过远端总页数 {remote_total}，{action}结束",
            )
            return
        if page_cap and end_page < remote_total:
            append_sync_log(
                self.db,
                job.id,
                f"远端共 {remote_total} 页，本次从第 {start_page} 页{action}至第 {end_page} 页",
            )
        elif start_page > 1:
            append_sync_log(
                self.db,
                job.id,
                f"从第 {start_page} 页继续{action}，远端共 {remote_total} 页",
            )

    def create_job(
        self,
        sync_mode: SyncMode,
        stand_type: str | None = None,
        trigger_type: SyncTriggerType = SyncTriggerType.manual,
        page_size: int | None = None,
        max_pages: int | None = None,
        start_page: int | None = None,
    ) -> SyncJob:
        stand_type = stand_type or self.runtime_config.default_stand_type
        page_size = page_size or self.runtime_config.page_size
        if max_pages is None:
            max_pages = self.runtime_config.max_pages
        max_pages = self._normalize_max_pages(max_pages)
        start_page = max(1, start_page or 1)
        prefix = "FULL" if sync_mode == SyncMode.full else "INC"
        batch_no = f"{prefix}-{stand_type}-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"

        job = SyncJob(
            batch_no=batch_no,
            status=SyncJobStatus.pending,
            trigger_type=trigger_type,
            sync_mode=sync_mode,
            stand_type=stand_type,
            page_size=page_size,
            start_page=start_page,
            max_pages=max_pages,
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)

        mode_label = "全量" if sync_mode == SyncMode.full else "增量"
        cap_label = f"，本批最多 {max_pages} 页" if max_pages else "，本批页数=不限制"
        start_label = f"，开始页={start_page}" if start_page > 1 else ""
        append_sync_log(
            self.db,
            job.id,
            f"创建{mode_label}同步任务，标准类型={stand_type}，分页大小={page_size}{start_label}{cap_label}",
        )
        self.db.commit()
        return job

    def retry_job(self, job_id: uuid.UUID) -> SyncJob:
        job = self.db.get(SyncJob, job_id)
        if not job:
            raise ValueError("同步任务不存在")
        if job.status == SyncJobStatus.running:
            raise ValueError("任务正在执行中，无法重试")

        job.status = SyncJobStatus.pending
        job.failure_reason = None
        job.finished_at = None
        job.started_at = None
        self.db.commit()
        self.db.refresh(job)
        return job

    def run_job(self, job_id: uuid.UUID) -> None:
        job = self.db.get(SyncJob, job_id)
        if not job:
            raise ValueError("同步任务不存在")

        self.runtime_config = get_or_create_sprs_config(self.db)
        self.sprs = SprsClient(
            self.settings,
            base_url=self.runtime_config.base_url,
            timeout_seconds=self.runtime_config.timeout_seconds,
        )

        job.status = SyncJobStatus.running
        job.started_at = datetime.now(UTC)
        job.success_count = 0
        job.failed_count = 0
        job.failure_reason = None
        append_sync_log(self.db, job.id, "同步任务开始执行")
        self.db.commit()

        try:
            if job.sync_mode == SyncMode.full:
                self._run_full(job)
            else:
                self._run_incremental(job)

            if job.failed_count > 0 and job.success_count > 0:
                job.status = SyncJobStatus.partial
            elif job.failed_count > 0:
                job.status = SyncJobStatus.failed
            else:
                job.status = SyncJobStatus.completed
            append_sync_log(
                self.db,
                job.id,
                (
                    f"同步完成：成功 {job.success_count} 条，失败 {job.failed_count} 条，"
                    f"状态={job.status.value}"
                ),
            )
        except SprsError as exc:
            job.status = SyncJobStatus.failed
            job.failure_reason = exc.message
            job.failed_count += 1
            append_sync_log(self.db, job.id, exc.message, SyncLogLevel.error)
            logger.exception("SPRS sync job failed: %s", job.batch_no)
        except Exception as exc:
            job.status = SyncJobStatus.failed
            job.failure_reason = str(exc)
            job.failed_count += 1
            append_sync_log(self.db, job.id, str(exc), SyncLogLevel.error)
            logger.exception("Unexpected sync job failure: %s", job.batch_no)
        finally:
            job.finished_at = datetime.now(UTC)
            self.db.commit()

    def _run_full(self, job: SyncJob) -> None:
        stand_type = job.stand_type or self.settings.sprs_default_stand_type
        page_size = job.page_size
        start_page = max(1, job.start_page or 1)
        current = start_page
        end_page: int | None = None

        page_cap = self._page_cap(job)
        cap_label = f"，本批最多 {page_cap} 页" if page_cap else "，本批页数=不限制"
        start_label = f"，startPage={start_page}" if start_page > 1 else ""
        append_sync_log(
            self.db,
            job.id,
            f"开始全量同步：standType={stand_type}，pageSize={page_size}{start_label}{cap_label}",
        )
        self.db.commit()

        while end_page is None or current <= end_page:
            append_sync_log(
                self.db,
                job.id,
                f"拉取列表第 {current} 页…",
            )
            page_data = self.sprs.fetch_laws_page(stand_type, current, page_size)
            remote_total = int(page_data.get("pageCount") or 1)
            job.remote_page_total = remote_total
            start_page, end_page = self._page_window(job, remote_total)
            if current == start_page:
                self._log_page_window(
                    job,
                    start_page=start_page,
                    end_page=end_page,
                    remote_total=remote_total,
                    action="拉取",
                )
                if start_page > remote_total:
                    self.db.commit()
                    return
            job.page_total = end_page
            job.page_current = current
            items = page_data.get("list") or []
            append_sync_log(
                self.db,
                job.id,
                f"第 {current}/{end_page} 页获取 {len(items)} 条标准（远端共 {remote_total} 页）",
            )
            self.db.commit()

            if items:
                append_sync_log(
                    self.db,
                    job.id,
                    f"开始处理第 {current} 页的 {len(items)} 条标准（含附件下载，可能较慢）…",
                )
                self.db.commit()

            for idx, item in enumerate(items, 1):
                label = _standard_label(item)
                append_sync_log(
                    self.db,
                    job.id,
                    f"第 {current} 页 [{idx}/{len(items)}] 处理标准：{label}",
                )
                self.db.commit()
                try:
                    self._process_standard_record(
                        job=job,
                        item=item,
                        force_metadata=True,
                        force_attachments=True,
                    )
                    job.success_count += 1
                    append_sync_log(
                        self.db,
                        job.id,
                        f"第 {current} 页 [{idx}/{len(items)}] 标准完成：{label}",
                    )
                except Exception as exc:
                    job = self._record_item_failure(
                        job.id,
                        item,
                        exc,
                        action="标准",
                    )
                    logger.warning(
                        "Failed to sync standard %s: %s",
                        item.get("id"),
                        exc,
                    )
                else:
                    self.db.commit()

            current += 1

    def _run_incremental(self, job: SyncJob) -> None:
        stand_type = job.stand_type or self.settings.sprs_default_stand_type
        page_size = job.page_size
        start_page = max(1, job.start_page or 1)
        current = start_page
        end_page: int | None = None

        page_cap = self._page_cap(job)
        cap_label = f"，本批最多 {page_cap} 页" if page_cap else "，本批页数=不限制"
        start_label = f"，startPage={start_page}" if start_page > 1 else ""
        append_sync_log(
            self.db,
            job.id,
            f"开始增量同步：standType={stand_type}，pageSize={page_size}{start_label}{cap_label}",
        )
        self.db.commit()

        while end_page is None or current <= end_page:
            append_sync_log(self.db, job.id, f"扫描列表第 {current} 页…")
            page_data = self.sprs.fetch_laws_page(stand_type, current, page_size)
            remote_total = int(page_data.get("pageCount") or 1)
            job.remote_page_total = remote_total
            start_page, end_page = self._page_window(job, remote_total)
            if current == start_page:
                self._log_page_window(
                    job,
                    start_page=start_page,
                    end_page=end_page,
                    remote_total=remote_total,
                    action="扫描",
                )
                if start_page > remote_total:
                    self.db.commit()
                    return
            job.page_total = end_page
            job.page_current = current
            items = page_data.get("list") or []
            append_sync_log(
                self.db,
                job.id,
                f"第 {current}/{end_page} 页扫描 {len(items)} 条标准（远端共 {remote_total} 页）",
            )
            self.db.commit()

            if items:
                append_sync_log(
                    self.db,
                    job.id,
                    f"开始处理第 {current} 页的 {len(items)} 条标准（含附件下载，可能较慢）…",
                )
                self.db.commit()

            for idx, item in enumerate(items, 1):
                try:
                    sprs_id = item.get("id")
                    if not sprs_id:
                        continue

                    label = _standard_label(item)
                    existing = self.db.scalar(
                        select(Standard).where(Standard.sprs_id == sprs_id)
                    )
                    remote_mtime = _parse_modify_time(item.get("modifyTime"))
                    metadata_changed = (
                        existing is None
                        or existing.sprs_modify_time is None
                        or remote_mtime is None
                        or remote_mtime > existing.sprs_modify_time
                    )

                    if metadata_changed:
                        append_sync_log(
                            self.db,
                            job.id,
                            f"第 {current} 页 [{idx}/{len(items)}] 处理标准：{label}",
                        )
                        self.db.commit()
                        self._process_standard_record(
                            job=job,
                            item=item,
                            force_metadata=True,
                            force_attachments=True,
                        )
                    else:
                        append_sync_log(
                            self.db,
                            job.id,
                            f"第 {current} 页 [{idx}/{len(items)}] 跳过元数据（未变更）：{label}",
                        )
                        self.db.commit()
                        standard = existing
                        if standard and self.runtime_config.download_attachments:
                            self._sync_attachments(
                                job=job,
                                standard=standard,
                                item=item,
                                force_download=False,
                            )
                    job.success_count += 1
                    append_sync_log(
                        self.db,
                        job.id,
                        f"第 {current} 页 [{idx}/{len(items)}] 标准完成：{label}",
                    )
                except Exception as exc:
                    job = self._record_item_failure(
                        job.id,
                        item,
                        exc,
                        action="标准",
                    )
                    logger.warning(
                        "Incremental sync failed for %s: %s",
                        item.get("id"),
                        exc,
                    )
                else:
                    self.db.commit()

            current += 1

    def _process_standard_record(
        self,
        job: SyncJob,
        item: dict,
        force_metadata: bool,
        force_attachments: bool,
    ) -> Standard:
        sprs_id = item["id"]
        standard = self.db.scalar(
            select(Standard).where(Standard.sprs_id == sprs_id)
        )

        if standard is None:
            standard = Standard(sprs_id=sprs_id, name=item.get("standName") or sprs_id)
            self.db.add(standard)

        if force_metadata:
            apply_sprs_record(standard, item)

        standard.last_sync_job_id = job.id
        append_sync_log(self.db, job.id, "  ↳ 写入元数据…")
        self.db.flush()
        append_sync_log(self.db, job.id, "  ↳ 元数据已写入")
        self.db.flush()

        if self.runtime_config.download_attachments:
            self._sync_attachments(
                job=job,
                standard=standard,
                item=item,
                force_download=force_attachments,
            )

        return standard

    def _sync_attachments(
        self,
        job: SyncJob,
        standard: Standard,
        item: dict,
        force_download: bool,
    ) -> None:
        refs = extract_attachment_refs(
            item.get("attrInfoMap"),
            item.get("attrInfoCaseMap"),
        )
        active_ids = {ref.sprs_file_id for ref in refs}

        if not refs:
            append_sync_log(self.db, job.id, "  ↳ 无附件")
            self.db.flush()
        else:
            append_sync_log(
                self.db,
                job.id,
                f"  ↳ 共 {len(refs)} 个附件",
            )
            self.db.flush()

        for ref in refs:
            attachment = self.db.scalar(
                select(Attachment).where(Attachment.sprs_file_id == ref.sprs_file_id)
            )
            if attachment is None:
                attachment = Attachment(
                    standard_id=standard.id,
                    sprs_file_id=ref.sprs_file_id,
                    attr_field=ref.attr_field,
                    display_name=ref.display_name,
                    file_type=guess_file_type(ref.display_name, ref.sprs_file_id),
                    storage_backend="minio",
                    storage_bucket=self.storage.bucket,
                    storage_key=self.storage.build_object_key(
                        ref.sprs_file_id,
                        ref.display_name or f"{ref.sprs_file_id}.bin",
                    ),
                    download_status=AttachmentDownloadStatus.pending,
                    parse_status=AttachmentParseStatus.pending,
                )
                self.db.add(attachment)
            else:
                attachment.standard_id = standard.id
                attachment.attr_field = ref.attr_field
                attachment.display_name = ref.display_name or attachment.display_name
                attachment.file_type = guess_file_type(
                    attachment.display_name, attachment.sprs_file_id
                )

            should_download = force_download or attachment.download_status in {
                AttachmentDownloadStatus.pending,
                AttachmentDownloadStatus.failed,
            }
            if should_download:
                append_sync_log(
                    self.db,
                    job.id,
                    f"  ↳ 下载附件：{_attachment_label(ref)}",
                )
                self.db.commit()
                try:
                    self._download_attachment(attachment, [ref], job=job)
                    append_sync_log(
                        self.db,
                        job.id,
                        (
                            f"  ↳ 附件就绪：{_attachment_label(ref)}"
                            f"（{attachment.file_size or 0} 字节）"
                        ),
                    )
                    self.db.commit()
                except Exception as exc:
                    logger.warning(
                        "Attachment download failed %s for standard %s: %s",
                        ref.sprs_file_id,
                        standard.sprs_id,
                        exc,
                    )
                    append_sync_log(
                        self.db,
                        job.id,
                        (
                            f"附件 {ref.display_name or ref.sprs_file_id} "
                            f"下载失败: {exc}"
                        ),
                        SyncLogLevel.warn,
                    )
                    self.db.commit()
            else:
                append_sync_log(
                    self.db,
                    job.id,
                    f"  ↳ 跳过附件（已就绪）：{_attachment_label(ref)}",
                )
                self.db.flush()

        for attachment in list(standard.attachments):
            if attachment.sprs_file_id not in active_ids:
                attachment.download_status = AttachmentDownloadStatus.failed
                attachment.failure_reason = "SPRS 附件引用已移除"
                attachment.parse_status = AttachmentParseStatus.skipped

        downloaded = [
            att
            for att in standard.attachments
            if att.download_status == AttachmentDownloadStatus.ready
        ]
        if downloaded:
            standard.sync_status = StandardSyncStatus.attachment_downloaded
        elif standard.sync_status == StandardSyncStatus.not_synced:
            standard.sync_status = StandardSyncStatus.synced

    def _download_attachment(
        self,
        attachment: Attachment,
        refs: list[AttachmentRef],
        *,
        job: SyncJob | None = None,
    ) -> None:
        file_ids = [attachment.sprs_file_id]
        try:
            content, content_type = self.sprs.download_files(file_ids)
            if job is not None:
                append_sync_log(
                    self.db,
                    job.id,
                    (
                        f"  ↳ SPRS 已响应，上传 MinIO："
                        f"{attachment.display_name or attachment.sprs_file_id}"
                        f"（{len(content)} 字节）"
                    ),
                )
                self.db.commit()
            files = _unpack_download(content, content_type, refs)

            if attachment.sprs_file_id in files:
                payload = files[attachment.sprs_file_id]
            elif len(files) == 1:
                payload = next(iter(files.values()))
            else:
                raise ValueError("无法从 SPRS 下载结果中匹配附件")

            payload = _normalize_downloaded_payload(payload, attachment)

            object_key = self.storage.build_object_key(
                attachment.sprs_file_id,
                attachment.display_name or f"{attachment.sprs_file_id}.bin",
            )
            size = self.storage.put_bytes(object_key, payload, _guess_content_type(attachment))
            attachment.storage_key = object_key
            attachment.file_size = size
            attachment.content_hash = hashlib.sha256(payload).hexdigest()
            attachment.download_status = AttachmentDownloadStatus.ready
            attachment.parse_status = AttachmentParseStatus.pending
            attachment.failure_reason = None
            attachment.downloaded_at = datetime.now(UTC)
        except SprsError as exc:
            attachment.download_status = AttachmentDownloadStatus.failed
            attachment.failure_reason = exc.message
            raise
        except Exception as exc:
            attachment.download_status = AttachmentDownloadStatus.failed
            attachment.failure_reason = str(exc)
            raise


def _parse_modify_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        if len(value) == 10:
            parsed = datetime.fromisoformat(value)
            return parsed.replace(tzinfo=UTC)
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed
    except ValueError:
        return None


def _normalize_downloaded_payload(payload: bytes, attachment: Attachment) -> bytes:
    file_type = (attachment.file_type or "").lower()
    name = (attachment.display_name or "").lower()
    if file_type != "docx" and not name.endswith(".docx"):
        return payload

    from app.processing.docx_payload import prepare_docx_payload

    return prepare_docx_payload(payload, attachment.display_name or attachment.sprs_file_id)


def _unpack_download(
    content: bytes,
    content_type: str,
    refs: list[AttachmentRef],
) -> dict[str, bytes]:
    # 单文件下载：SPRS 直接返回文件本体。DOCX 也以 PK 开头，不能按 zip 包解压。
    if len(refs) == 1:
        return {refs[0].sprs_file_id: content}

    if content[:2] == b"PK" or "zip" in content_type.lower():
        result: dict[str, bytes] = {}
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            for name in zf.namelist():
                if name.endswith("/"):
                    continue
                data = zf.read(name)
                matched_id = _match_file_id(name, refs)
                if matched_id:
                    result[matched_id] = data
                else:
                    result[name] = data
        return result

    return {"__single__": content}


def _match_file_id(filename: str, refs: list[AttachmentRef]) -> str | None:
    lower_name = filename.lower()
    for ref in refs:
        display = (ref.display_name or "").lower()
        if display and display in lower_name:
            return ref.sprs_file_id
        if ref.sprs_file_id.lower() in lower_name:
            return ref.sprs_file_id
    return None


def _guess_content_type(attachment: Attachment) -> str:
    file_type = (attachment.file_type or "").lower()
    mapping = {
        "pdf": "application/pdf",
        "doc": "application/msword",
        "docx": (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
        "txt": "text/plain",
    }
    return mapping.get(file_type, "application/octet-stream")
