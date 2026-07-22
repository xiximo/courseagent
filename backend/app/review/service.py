from __future__ import annotations

import json
import logging
import re
import time
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.errors import ApiBusinessError
from app.db.models.llm_config import LlmConfigRecord
from app.db.models.standard import Standard
from app.indexing.service import IndexingService
from app.llm.doubao_client import DoubaoChatMessage, DoubaoClientError, chat_completion
from app.processing.parser import extract_attachment_text
from app.schemas.indexing import ChunkSearchHitDto
from app.schemas.qa import CitationDto
from app.schemas.review import (
    BasicInfoDto,
    ComparisonItemDto,
    DraftAnalysisResultDto,
    ElementItemDto,
    TestMethodComparisonDto,
    ToolTraceStepDto,
)
from app.review.report_synthesis import ReportSynthesisService
from app.review.report_store import ReviewReportStore
from app.services.llm_settings import is_llm_configured, resolve_llm_runtime

logger = logging.getLogger(__name__)

DISCLAIMER = "建议仅供审核参考，最终结论以人工审核为准"

SOURCE_TYPES = {
    "national": "国标",
    "industry": "行标",
    "enterprise": "企标",
    "oem": "其他车企",
}

ANALYSIS_SYSTEM_PROMPT = """你是企业标准审核辅助助手。请分析用户提供的新编标准草案文本，输出严格 JSON（不要 markdown 代码块）：

{
  "summary": "草案整体摘要（100字内）",
  "basicInfo": {
    "standardNo": "标准编号",
    "name": "标准名称",
    "scope": "适用范围摘要",
    "publishDate": "发布日期或空",
    "effectiveDate": "实施日期或空",
    "partCode": "Part 编码或空",
    "partName": "Part 名称或空",
    "draftType": "企标/国标/行标等"
  },
  "elements": [
    {
      "category": "术语|技术要求|性能指标|尺寸公差|材料要求|环境条件|外观质量|试验项目|试验方法|引用标准|其他",
      "clauseNo": "条款编号如 4.2.1",
      "name": "具体指标/项目名称，如「邵氏硬度」「拉伸强度」",
      "requirement": "指标要求或限值，如「60±5」「≥10 MPa」「不应有裂纹」",
      "unit": "单位，如 mm、MPa、℃，无则空",
      "content": "完整条款原文或补充说明",
      "position": "所属章节，如「第4章 技术要求 4.2」"
    }
  ],
  "testMethods": [
    {
      "name": "试验项目名称，如「硬度试验」「耐臭氧试验」",
      "content": "试验方法、条件、判定要求等完整内容",
      "position": "章节位置"
    }
  ],
  "referenceNos": ["GB/T 12345-2020"],
  "issues": [
    {
      "type": "missing|conflict|expired|insufficient",
      "description": "问题描述",
      "suggestion": "改进建议"
    }
  ],
  "suggestions": ["审核关注点1", "审核关注点2"]
}

规则：
1. 从草案文本中提取，不要编造不存在的内容。
2. **要素识别须细化到具体指标**：技术要求、性能参数、尺寸公差、材料、环境条件、外观、试验项目等，每条指标单独一项，不要只输出章节标题。
3. 表格中的每一行指标须拆分为独立 elements 条目。
4. 含数值、范围、±、≥、≤ 的条款须填入 requirement 与 unit。
5. category=试验项目 或 试验方法 的条目，同时填入 testMethods 数组（name 与 elements 一致）。
6. 使用简体中文。"""

CLAUSE_NO_PATTERN = re.compile(r"^(\d+(?:\.\d+)+)")
UNIT_IN_TEXT_PATTERN = re.compile(
    r"(mm|cm|m|μm|MPa|kPa|N(?:·mm)?|kN|℃|°C|%|级|Shore\s*[AHD]|g|kg|min|h|次|rpm|Hz|V|A|W)",
    re.IGNORECASE,
)
REQUIREMENT_HINT_PATTERN = re.compile(
    r"(应|不应|不得|不大于|不小于|不低于|不高于|≥|≤|>|<|±|＋|\-|~|～|至)"
)

COMPARE_SYSTEM_PROMPT = """你是企业标准试验方法对比审核专家。知识库未检索到对照条款时，请基于行业通用规范进行推理对比。

请严格输出 JSON（不要 markdown 代码块）：
{
  "comparisons": [
    {
      "sourceType": "national|industry|enterprise|oem",
      "standardNo": "参考标准号，无法确定则填 —",
      "standardName": "参考标准名称或空",
      "matchedClause": "推断的对照条款位置或空",
      "diff": "same|stricter|looser|missing|conflict",
      "note": "推理对比说明，须说明依据"
    }
  ]
}

规则：
1. 不得捏造知识库中不存在的具体条款原文。
2. 可引用行业通用标准号（如 GB/T、QC/T）作为推理参考，但须在 note 中标注「推理」。
3. 确实无法对比时 diff 填 missing。
4. 使用简体中文。"""


class ReviewAssistService:
    def __init__(self, db: Session, llm_config: LlmConfigRecord) -> None:
        self.db = db
        self.llm_config = resolve_llm_runtime(llm_config)
        self._traces: list[ToolTraceStepDto] = []
        self._trace_cursor = 0

    def analyze(
        self,
        *,
        text: str | None = None,
        file_bytes: bytes | None = None,
        file_name: str | None = None,
        created_by: str = "",
        created_by_user_id: uuid.UUID | None = None,
        persist_report: bool = True,
    ) -> DraftAnalysisResultDto:
        result: DraftAnalysisResultDto | None = None
        for event, payload in self.iter_analyze_events(
            text=text,
            file_bytes=file_bytes,
            file_name=file_name,
            created_by=created_by,
            created_by_user_id=created_by_user_id,
            persist_report=persist_report,
        ):
            if event == "result":
                result = DraftAnalysisResultDto.model_validate(payload)
            elif event == "error":
                raise ApiBusinessError(
                    str(payload.get("code") or "UNKNOWN"),
                    str(payload.get("message") or "分析失败"),
                    int(payload.get("statusCode") or 400),
                )
        if result is None:
            raise ApiBusinessError("INTERNAL_ERROR", "分析未返回结果", 500)
        return result

    def iter_analyze_events(
        self,
        *,
        text: str | None = None,
        file_bytes: bytes | None = None,
        file_name: str | None = None,
        created_by: str = "",
        created_by_user_id: uuid.UUID | None = None,
        persist_report: bool = True,
    ) -> Iterator[tuple[str, dict[str, Any]]]:
        self._traces = []
        self._trace_cursor = 0
        task_id = str(uuid.uuid4())

        try:
            content, _parse_note = self._parse_input(
                text=text,
                file_bytes=file_bytes,
                file_name=file_name,
            )
            yield from self._yield_new_traces()

            if not content.strip():
                raise ApiBusinessError(
                    "DRAFT_UNRECOGNIZED",
                    "草案格式无法识别，请重新上传 Word 文件或粘贴文本",
                    400,
                )

            if is_llm_configured(self.llm_config):
                self._add_running_trace(
                    "extract_structure",
                    f"文本长度={len(content)}",
                    "企标智审官正在识别要素、指标与试验方法…",
                )
                yield from self._yield_new_traces()
                llm_payload = self._extract_with_llm(content)
                self._clear_running_traces()
            else:
                llm_payload = None
            yield from self._yield_new_traces()

            if llm_payload is None:
                llm_payload = self._extract_with_rules(content)
                yield from self._yield_new_traces()

            basic_info = self._build_basic_info(llm_payload)
            elements = self._build_elements(llm_payload)
            elements = self._merge_elements(
                elements,
                self._extract_indicator_items_rules(content),
            )
            test_methods = self._merge_test_methods(
                list(llm_payload.get("testMethods") or []),
                self._extract_test_methods_rules(content),
                self._elements_to_test_methods(elements),
            )

            reference_nos = llm_payload.get("referenceNos") or self._extract_reference_nos(
                content
            )
            reference_checks = self._list_references_without_db_check(reference_nos)
            yield from self._yield_new_traces()

            test_comparisons: list[TestMethodComparisonDto] = []
            for progress in self._iter_compare_test_methods(test_methods):
                yield from self._yield_new_traces()
                if progress is not None:
                    test_comparisons = progress

            elements = self._attach_test_comparisons_to_elements(elements, test_comparisons)

            issues = llm_payload.get("issues") or []
            suggestions = llm_payload.get("suggestions") or []
            summary = (
                str(llm_payload.get("summary") or "").strip()
                or self._default_summary(basic_info)
            )
            citations = self._collect_citations(test_comparisons, reference_checks)

            result = DraftAnalysisResultDto(
                taskId=task_id,
                summary=summary,
                basicInfo=basic_info,
                elements=elements,
                testMethodComparisons=test_comparisons,
                referenceChecks=reference_checks,
                issues=issues,
                suggestions=suggestions,
                citations=citations,
                thinkingSteps=list(self._traces),
                analyzedAt=datetime.now(UTC).isoformat(),
            )
            yield "result", result.model_dump(mode="json")

            report_started = time.perf_counter()
            self._add_running_trace(
                "synthesize_report",
                f"分析任务={task_id}",
                "正在合成 AI智审官评审报告…",
            )
            yield from self._yield_new_traces()
            report_service = ReportSynthesisService(self.db, self.llm_config)
            report = report_service.synthesize(
                analysis=result,
                draft_excerpt=content,
                parse_note=_parse_note,
            )
            if persist_report:
                report = self._persist_report(
                    report,
                    created_by=created_by,
                    created_by_user_id=created_by_user_id,
                )
            self._clear_running_traces()
            self._add_trace(
                "synthesize_report",
                f"分析任务={task_id}",
                (
                    f"报告已生成：缺失 {len(report.missingFeatures)} 项，"
                    f"需提升 {len(report.improvements)} 项"
                ),
                report_started,
            )
            yield from self._yield_new_traces()
            yield "report", report.model_dump(mode="json")
        except ApiBusinessError as exc:
            yield from self._yield_new_traces()
            yield (
                "error",
                {
                    "code": exc.code,
                    "message": exc.message,
                    "statusCode": exc.status_code,
                },
            )

    def _persist_report(
        self,
        report,
        *,
        created_by: str,
        created_by_user_id: uuid.UUID | None,
    ):
        try:
            return ReviewReportStore(self.db).save(
                report,
                created_by=created_by,
                created_by_user_id=created_by_user_id,
            )
        except ApiBusinessError as exc:
            logger.warning("Review report persist skipped: %s", exc.message)
        except Exception:
            logger.exception("Review report persist failed")
        return report

    def _yield_new_traces(self) -> Iterator[tuple[str, dict[str, Any]]]:
        while self._trace_cursor < len(self._traces):
            step = self._traces[self._trace_cursor]
            self._trace_cursor += 1
            yield "thinking", step.model_dump(mode="json")

    def _parse_input(
        self,
        *,
        text: str | None,
        file_bytes: bytes | None,
        file_name: str | None,
    ) -> tuple[str, str]:
        started = time.perf_counter()
        if file_bytes:
            name = file_name or "draft.docx"
            ext = name.rsplit(".", 1)[-1].lower() if "." in name else "docx"
            try:
                result = extract_attachment_text(file_bytes, ext, name)
                note = (
                    f"解析完成：{result.char_count} 字符，引擎={result.parse_engine}，"
                    f"质量={result.parse_quality}"
                )
                self._add_trace(
                    "parse_document",
                    f"文件={name}，大小={len(file_bytes)}B",
                    note,
                    started,
                )
                return result.content, note
            except ValueError as exc:
                self._add_trace(
                    "parse_document",
                    f"文件={name}",
                    f"解析失败：{exc}",
                    started,
                    status="error",
                )
                raise ApiBusinessError("PARSE_FAILED", str(exc), 400) from exc

        if text and text.strip():
            content = text.strip()
            self._add_trace(
                "parse_document",
                f"文本输入，{len(content)} 字符",
                "直接使用粘贴文本",
                started,
            )
            return content, "paste"

        self._add_trace("parse_document", "无有效输入", "缺少文件或文本", started, status="error")
        return "", ""

    def _extract_with_llm(self, content: str) -> dict:
        started = time.perf_counter()
        trimmed = content[:12000]
        user_prompt = f"请分析以下新编标准草案：\n\n{trimmed}\n\n请输出 JSON。"

        try:
            raw = chat_completion(
                api_key=self.llm_config.api_key,
                endpoint_id=self.llm_config.endpoint_id,
                base_url=self.llm_config.base_url,
                timeout_seconds=self.llm_config.timeout_seconds,
                messages=[
                    DoubaoChatMessage(role="system", content=ANALYSIS_SYSTEM_PROMPT),
                    DoubaoChatMessage(role="user", content=user_prompt),
                ],
            )
        except DoubaoClientError as exc:
            logger.exception("Review assist LLM failed")
            self._add_trace(
                "extract_structure",
                f"文本长度={len(trimmed)}",
                f"LLM 调用失败，将使用规则抽取：{exc}",
                started,
                status="error",
            )
            return {}

        payload = self._extract_json(raw) or {}
        element_count = len(payload.get("elements") or [])
        method_count = len(payload.get("testMethods") or [])
        indicator_count = sum(
            1
            for item in payload.get("elements") or []
            if isinstance(item, dict)
            and str(item.get("category") or "") not in {"术语", "引用标准", "其他"}
        )
        self._add_trace(
            "extract_structure",
            f"文本长度={len(trimmed)}",
            f"企标智审官 {element_count} 项要素（{indicator_count} 项指标）、{method_count} 项试验方法",
            started,
        )
        return payload

    def _extract_with_rules(self, content: str) -> dict:
        started = time.perf_counter()
        payload = {
            "summary": self._default_summary_from_text(content),
            "basicInfo": self._extract_basic_info_rules(content),
            "elements": self._extract_elements_rules(content),
            "testMethods": self._extract_test_methods_rules(content),
            "referenceNos": self._extract_reference_nos(content),
            "issues": [],
            "suggestions": ["建议配置 LLM 以获得更精准的要素识别"],
        }
        self._add_trace(
            "extract_structure",
            f"文本长度={len(content)}",
            f"规则抽取：{len(payload['elements'])} 项要素、{len(payload['testMethods'])} 项试验方法",
            started,
        )
        return payload

    def _iter_compare_test_methods(
        self, test_methods: list[dict]
    ) -> Iterator[list[TestMethodComparisonDto] | None]:
        if not test_methods:
            started = time.perf_counter()
            self._add_trace(
                "compare_test_methods",
                "无试验方法",
                "跳过对比评审",
                started,
            )
            yield None
            yield []
            return

        total = min(len(test_methods), 8)
        self._add_running_trace(
            "compare_test_methods",
            f"共 {total} 项试验方法",
            "正在检索知识库并对比国标/行标/企标/其他车企…",
        )
        yield None

        indexing = IndexingService(self.db)
        results: list[TestMethodComparisonDto] = []
        llm_enabled = is_llm_configured(self.llm_config)

        for index, method in enumerate(test_methods[:8], start=1):
            name = str(method.get("name") or "试验方法").strip()
            content = str(method.get("content") or "").strip()
            query = f"{name} {content}".strip()[:200]
            started = time.perf_counter()

            try:
                search = indexing.hybrid_search_chunks(query, top_k=self.llm_config.qa_top_k)
                hits = search.hits
            except Exception as exc:
                logger.warning("Test method search failed: %s", exc)
                hits = []

            grouped = self._group_hits_by_source(hits)
            comparisons: list[ComparisonItemDto] = []
            missing_types: list[tuple[str, str]] = []

            for source_type, label in SOURCE_TYPES.items():
                source_hits = grouped.get(source_type, [])[:1]
                if not source_hits:
                    missing_types.append((source_type, label))
                    continue

                hit = source_hits[0]
                meta = self._resolve_hit_meta(hit)
                diff = self._classify_diff(content, hit.content or "")
                comparisons.append(
                    ComparisonItemDto(
                        sourceType=source_type,
                        sourceLabel=label,
                        standardNo=meta["standard_no"] or "—",
                        standardName=meta["standard_name"],
                        matchedClause=hit.positionLabel or "",
                        diff=diff,
                        note=self._diff_note(diff),
                        inferenceSource="knowledge_base",
                        citations=[
                            CitationDto(
                                standardId=hit.standardId,
                                attachmentId=hit.attachmentId,
                                chunkId=hit.chunkId,
                                standardNo=meta["standard_no"],
                                standardName=meta["standard_name"],
                                attachment=meta["attachment"] or None,
                                excerpt=(hit.content or "")[:200],
                                position=hit.positionLabel,
                            )
                        ],
                    )
                )

            kb_count = len(comparisons)
            llm_count = 0

            if missing_types and llm_enabled:
                llm_comparisons = self._llm_compare_missing_sources(
                    method_name=name,
                    method_content=content,
                    missing_types=missing_types,
                )
                comparisons.extend(llm_comparisons)
                llm_count = len(llm_comparisons)
            else:
                for source_type, label in missing_types:
                    note = (
                        f"知识库未检索到相关{label}条款"
                        if not llm_enabled
                        else f"知识库未检索到相关{label}条款，且 LLM 未返回推理结果"
                    )
                    comparisons.append(
                        ComparisonItemDto(
                            sourceType=source_type,
                            sourceLabel=label,
                            standardNo="—",
                            diff="missing",
                            note=note,
                            inferenceSource="none",
                        )
                    )

            comparisons.sort(
                key=lambda item: list(SOURCE_TYPES.keys()).index(item.sourceType)
                if item.sourceType in SOURCE_TYPES
                else 99
            )

            trace_parts = [f"知识库 {kb_count} 条"]
            if llm_count:
                trace_parts.append(f"企标智审官推理 {llm_count} 条")
            if missing_types and not llm_count:
                trace_parts.append(f"无依据 {len(missing_types)} 条")

            self._add_trace(
                "compare_test_methods",
                f"({index}/{total}) 试验方法={name}",
                "，".join(trace_parts),
                started,
            )
            if llm_count:
                self._add_trace(
                    "compare_test_methods_llm",
                    f"试验方法={name}，缺失类型={[t[1] for t in missing_types]}",
                    f"豆包推理补充 {llm_count} 条对比",
                    started,
                )

            results.append(
                TestMethodComparisonDto(
                    draftMethod=name,
                    draftContent=content,
                    comparisons=comparisons,
                )
            )
            yield None

        self._clear_running_traces()
        yield results

    def _compare_test_methods(self, test_methods: list[dict]) -> list[TestMethodComparisonDto]:
        result: list[TestMethodComparisonDto] = []
        for progress in self._iter_compare_test_methods(test_methods):
            if isinstance(progress, list):
                result = progress
        return result

    def _llm_compare_missing_sources(
        self,
        *,
        method_name: str,
        method_content: str,
        missing_types: list[tuple[str, str]],
    ) -> list[ComparisonItemDto]:
        if not missing_types:
            return []

        type_lines = "\n".join(
            f"- {source_type}（{label}）" for source_type, label in missing_types
        )
        user_prompt = (
            f"草案试验方法：\n名称：{method_name}\n内容：{method_content}\n\n"
            f"知识库未找到以下类型的对照条款，请进行推理对比：\n{type_lines}\n\n"
            "请输出 JSON。"
        )

        try:
            raw = chat_completion(
                api_key=self.llm_config.api_key,
                endpoint_id=self.llm_config.endpoint_id,
                base_url=self.llm_config.base_url,
                timeout_seconds=self.llm_config.timeout_seconds,
                messages=[
                    DoubaoChatMessage(role="system", content=COMPARE_SYSTEM_PROMPT),
                    DoubaoChatMessage(role="user", content=user_prompt),
                ],
            )
        except DoubaoClientError as exc:
            logger.warning("LLM test method comparison failed: %s", exc)
            return []

        payload = self._extract_json(raw) or {}
        items = payload.get("comparisons") or []
        if not isinstance(items, list):
            return []

        expected_types = {source_type for source_type, _ in missing_types}
        label_map = dict(missing_types)
        results: list[ComparisonItemDto] = []
        seen_types: set[str] = set()

        for item in items:
            if not isinstance(item, dict):
                continue
            source_type = str(item.get("sourceType") or "").strip()
            if source_type not in expected_types or source_type in seen_types:
                continue
            seen_types.add(source_type)

            diff = str(item.get("diff") or "missing").strip()
            if diff not in {"same", "stricter", "looser", "missing", "conflict"}:
                diff = "missing"

            note = str(item.get("note") or "").strip()
            if note and "推理" not in note and "豆包" not in note:
                note = f"【豆包推理】{note}"

            results.append(
                ComparisonItemDto(
                    sourceType=source_type,
                    sourceLabel=label_map.get(source_type, source_type),
                    standardNo=str(item.get("standardNo") or "—"),
                    standardName=str(item.get("standardName") or ""),
                    matchedClause=str(item.get("matchedClause") or ""),
                    diff=diff,
                    note=note or "企标智审官推理对比，建议人工复核",
                    inferenceSource="llm",
                )
            )

        return results

    def _list_references_without_db_check(self, reference_nos: list[str]) -> list[dict]:
        """仅从草案识别引用标准号，不查询数据库。"""
        started = time.perf_counter()
        refs = list(dict.fromkeys(ref.strip() for ref in reference_nos if ref and ref.strip()))[
            :50
        ]
        checks = [
            {
                "standardNo": ref,
                "note": "已从草案识别（未做库内核对）",
            }
            for ref in refs
        ]
        self._add_trace(
            "check_draft_references",
            f"识别 {len(refs)} 项引用标准",
            "已跳过数据库核对",
            started,
        )
        return checks

    def _check_references(self, reference_nos: list[str]) -> list[dict]:
        """保留供后续恢复库内核对时使用。"""
        return self._list_references_without_db_check(reference_nos)

    def _group_hits_by_source(
        self, hits: list[ChunkSearchHitDto]
    ) -> dict[str, list[ChunkSearchHitDto]]:
        grouped: dict[str, list[ChunkSearchHitDto]] = {
            key: [] for key in SOURCE_TYPES
        }
        for hit in hits:
            meta = self._resolve_hit_meta(hit)
            source_type = self._classify_standard_type(
                meta["standard_no"],
                meta.get("stand_type", ""),
                meta.get("standard_name", ""),
            )
            if len(grouped[source_type]) < 3:
                grouped[source_type].append(hit)
        return grouped

    @staticmethod
    def _classify_standard_type(standard_no: str, stand_type: str = "", name: str = "") -> str:
        no = (standard_no or "").upper()
        if re.match(r"^GB[/\s]?", no):
            return "national"
        if re.match(r"^(QC/T|JT/T|YD/T|NB/T|HG/T|SH/T|SY/T|DL/T)", no):
            return "industry"
        if re.match(r"^Q/", no) or "企标" in name or "企业标准" in name:
            return "enterprise"
        if any(kw in name for kw in ("主机厂", "OEM", "整车厂", "客户标准")):
            return "oem"
        if stand_type and stand_type.upper() in {"OEM", "CUSTOM"}:
            return "oem"
        return "enterprise"

    @staticmethod
    def _classify_diff(draft: str, reference: str) -> str:
        if not reference.strip():
            return "missing"
        draft_len = len(draft.strip())
        ref_len = len(reference.strip())
        if draft_len == 0:
            return "missing"
        ratio = draft_len / max(ref_len, 1)
        if 0.85 <= ratio <= 1.15:
            return "same"
        if ratio > 1.15:
            return "stricter"
        if ratio < 0.85:
            return "looser"
        return "same"

    @staticmethod
    def _diff_note(diff: str) -> str:
        return {
            "same": "与对照标准基本一致",
            "stricter": "草案要求严于对照标准",
            "looser": "草案要求宽于对照标准",
            "missing": "未找到可对照条款",
            "conflict": "存在冲突，需人工复核",
        }.get(diff, "需人工复核")

    def _resolve_hit_meta(self, hit: ChunkSearchHitDto) -> dict[str, str]:
        standard_no = ""
        standard_name = ""
        attachment_name = ""
        stand_type = ""

        if hit.standardId:
            standard = self.db.get(Standard, uuid.UUID(hit.standardId))
            if standard:
                standard_no = standard.standard_no or standard.stand_number or ""
                standard_name = standard.name or ""
                stand_type = standard.stand_type or ""

        if hit.attachmentId:
            from app.db.models.attachment import Attachment

            attachment = self.db.get(Attachment, uuid.UUID(hit.attachmentId))
            if attachment:
                attachment_name = attachment.display_name or ""

        return {
            "standard_no": standard_no,
            "standard_name": standard_name,
            "attachment": attachment_name,
            "stand_type": stand_type,
        }

    def _build_basic_info(self, payload: dict) -> BasicInfoDto:
        raw = payload.get("basicInfo") or {}
        if isinstance(raw, BasicInfoDto):
            return raw
        if not isinstance(raw, dict):
            raw = {}
        return BasicInfoDto(
            standardNo=str(raw.get("standardNo") or ""),
            name=str(raw.get("name") or ""),
            scope=str(raw.get("scope") or ""),
            publishDate=str(raw.get("publishDate") or ""),
            effectiveDate=str(raw.get("effectiveDate") or ""),
            partCode=str(raw.get("partCode") or ""),
            partName=str(raw.get("partName") or ""),
            draftType=str(raw.get("draftType") or ""),
        )

    def _build_elements(self, payload: dict) -> list[ElementItemDto]:
        items = payload.get("elements") or []
        result: list[ElementItemDto] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            result.append(self._normalize_element_dict(item))
        return result

    @staticmethod
    def _normalize_element_dict(item: dict) -> ElementItemDto:
        name = str(item.get("name") or "").strip()
        content = str(item.get("content") or "").strip()
        requirement = str(item.get("requirement") or "").strip()
        if not requirement and content:
            requirement = ReviewAssistService._guess_requirement(content)
        unit = str(item.get("unit") or "").strip()
        if not unit:
            unit = ReviewAssistService._guess_unit(requirement or content)
        return ElementItemDto(
            category=str(item.get("category") or "其他"),
            name=name or content[:40] or "未命名指标",
            content=content or requirement,
            position=str(item.get("position") or ""),
            clauseNo=str(item.get("clauseNo") or ""),
            requirement=requirement,
            unit=unit,
        )

    def _merge_elements(
        self,
        primary: list[ElementItemDto],
        supplemental: list[ElementItemDto],
    ) -> list[ElementItemDto]:
        merged = list(primary)
        seen = {
            (item.clauseNo, item.name, item.requirement or item.content)
            for item in merged
        }
        for item in supplemental:
            key = (item.clauseNo, item.name, item.requirement or item.content)
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)
        return merged[:80]

    @staticmethod
    def _merge_test_methods(
        *groups: list[dict],
    ) -> list[dict]:
        merged: list[dict] = []
        seen: set[str] = set()
        for group in groups:
            for item in group:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name") or "").strip()
                if not name or name in seen:
                    continue
                seen.add(name)
                merged.append(item)
        return merged[:15]

    @staticmethod
    def _elements_to_test_methods(elements: list[ElementItemDto]) -> list[dict]:
        methods: list[dict] = []
        for item in elements:
            if item.category not in {"试验方法", "试验项目"}:
                continue
            methods.append(
                {
                    "name": item.name,
                    "content": item.requirement or item.content,
                    "position": item.position or item.clauseNo,
                }
            )
        return methods

    def _attach_test_comparisons_to_elements(
        self,
        elements: list[ElementItemDto],
        comparisons: list[TestMethodComparisonDto],
    ) -> list[ElementItemDto]:
        if not comparisons:
            return elements

        comp_by_name = {item.draftMethod: item for item in comparisons}
        result: list[ElementItemDto] = []
        linked_names: set[str] = set()

        for element in elements:
            if element.category not in {"试验方法", "试验项目"}:
                result.append(element)
                continue

            comp = comp_by_name.get(element.name)
            if comp is None:
                for draft_name, draft_comp in comp_by_name.items():
                    if draft_name in element.name or element.name in draft_name:
                        comp = draft_comp
                        break

            if comp:
                linked_names.add(comp.draftMethod)
                result.append(
                    element.model_copy(update={"comparisons": comp.comparisons})
                )
            else:
                result.append(element)

        existing_names = {el.name for el in result if el.category in {"试验方法", "试验项目"}}
        for comp in comparisons:
            if comp.draftMethod in existing_names:
                continue
            result.append(
                ElementItemDto(
                    category="试验方法",
                    name=comp.draftMethod,
                    content=comp.draftContent,
                    requirement=comp.draftContent,
                    position="",
                    comparisons=comp.comparisons,
                )
            )

        return result

    @staticmethod
    def _guess_requirement(text: str) -> str:
        text = text.strip()
        if not text:
            return ""
        for sep in ("：", ":", "应为", "应不大于", "应不小于", "不应", "应"):
            if sep in text:
                tail = text.split(sep, 1)[-1].strip()
                if tail and len(tail) <= 120:
                    return tail
        if REQUIREMENT_HINT_PATTERN.search(text):
            return text[:120]
        return ""

    @staticmethod
    def _guess_unit(text: str) -> str:
        match = UNIT_IN_TEXT_PATTERN.search(text or "")
        return match.group(1) if match else ""

    @staticmethod
    def _classify_indicator_category(section_title: str, line: str) -> str:
        combined = f"{section_title} {line}"
        if any(k in combined for k in ("术语", "定义")):
            return "术语"
        if any(k in combined for k in ("引用", "规范性引用")):
            return "引用标准"
        if any(k in combined for k in ("试验方法", "检验方法", "测试方法")):
            return "试验方法"
        if any(k in combined for k in ("试验", "检验", "测试")) and "方法" not in combined:
            return "试验项目"
        if any(k in combined for k in ("尺寸", "公差", "偏差")):
            return "尺寸公差"
        if any(k in combined for k in ("材料", "牌号", "成分")):
            return "材料要求"
        if any(k in combined for k in ("温度", "湿度", "环境", "气候")):
            return "环境条件"
        if any(k in combined for k in ("外观", "表面", "颜色", "缺陷")):
            return "外观质量"
        if any(k in combined for k in ("性能", "强度", "硬度", "伸长", "拉伸", "压缩")):
            return "性能指标"
        if any(k in combined for k in ("要求", "技术", "指标")):
            return "技术要求"
        return "技术要求"

    def _extract_indicator_items_rules(self, content: str) -> list[ElementItemDto]:
        items: list[ElementItemDto] = []
        current_section = ""
        current_position = ""

        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            header = re.match(r"^#{1,4}\s*(.+)$", line)
            if header:
                current_section = header.group(1).strip()
                current_position = current_section
                continue

            chapter = re.match(r"^第[一二三四五六七八九十百千零\d]+章\s*(.+)$", line)
            if chapter:
                current_section = line
                current_position = line
                continue

            items.extend(
                self._parse_indicator_line(
                    line,
                    section_title=current_section,
                    position=current_position,
                )
            )

        items.extend(self._extract_table_indicators(content, current_position))
        return self._merge_elements([], items)

    def _parse_indicator_line(
        self,
        line: str,
        *,
        section_title: str,
        position: str,
    ) -> list[ElementItemDto]:
        if len(line) < 4 or line.startswith("|") or line.startswith("<!--"):
            return []

        clause_no = ""
        body = line
        clause_match = CLAUSE_NO_PATTERN.match(line)
        if clause_match:
            clause_no = clause_match.group(1)
            body = line[clause_match.end() :].strip(" .、\t")

        if not body or len(body) < 2:
            return []

        is_indicator = bool(clause_match) or bool(REQUIREMENT_HINT_PATTERN.search(body))
        is_indicator = is_indicator or bool(UNIT_IN_TEXT_PATTERN.search(body))
        if not is_indicator and not any(
            k in section_title for k in ("要求", "技术", "试验", "检验", "性能", "指标")
        ):
            return []

        category = self._classify_indicator_category(section_title, body)
        requirement = self._guess_requirement(body)
        unit = self._guess_unit(requirement or body)

        name = body
        if "：" in body:
            name = body.split("：", 1)[0].strip()
        elif ":" in body and len(body.split(":", 1)[0]) <= 20:
            name = body.split(":", 1)[0].strip()

        if len(name) > 60:
            name = name[:60]

        return [
            ElementItemDto(
                category=category,
                name=name,
                content=body,
                position=position or section_title,
                clauseNo=clause_no,
                requirement=requirement,
                unit=unit,
            )
        ]

    @staticmethod
    def _extract_table_indicators(content: str, default_position: str) -> list[ElementItemDto]:
        items: list[ElementItemDto] = []
        lines = content.splitlines()
        index = 0
        while index < len(lines):
            line = lines[index].strip()
            if not line.startswith("|"):
                index += 1
                continue

            block: list[str] = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                block.append(lines[index].strip())
                index += 1

            if len(block) < 2:
                continue

            headers = [cell.strip() for cell in block[0].strip("|").split("|")]
            data_rows = [
                row
                for row in block[2:]
                if row.strip() and not set(row.replace("|", "").strip()) <= {"-", ":"}
            ]

            name_col = 0
            req_col = 1 if len(headers) > 1 else 0
            for col_idx, header in enumerate(headers):
                if any(k in header for k in ("项目", "指标", "名称", "参数")):
                    name_col = col_idx
                if any(k in header for k in ("要求", "指标值", "限值", "数值", "标准")):
                    req_col = col_idx

            for row in data_rows[:30]:
                cells = [cell.strip() for cell in row.strip("|").split("|")]
                if not cells or all(not cell for cell in cells):
                    continue
                name = cells[name_col] if name_col < len(cells) else ""
                requirement = cells[req_col] if req_col < len(cells) else ""
                if not name:
                    continue
                items.append(
                    ElementItemDto(
                        category="技术要求",
                        name=name,
                        content=" | ".join(cells),
                        position=default_position or "表格",
                        requirement=requirement or ReviewAssistService._guess_requirement(
                            " | ".join(cells)
                        ),
                        unit=ReviewAssistService._guess_unit(requirement),
                    )
                )
        return items

    @staticmethod
    def _extract_reference_nos(content: str) -> list[str]:
        pattern = re.compile(
            r"(?:GB/T|GB|QC/T|JT/T|Q/[\w\u4e00-\u9fff]+)\s*[\d\.\-]+(?:\s*[-—]\s*\d{4})?",
            re.IGNORECASE,
        )
        found = pattern.findall(content)
        return list(dict.fromkeys(found))[:30]

    @staticmethod
    def _extract_basic_info_rules(content: str) -> dict:
        info: dict[str, str] = {}
        for line in content.splitlines()[:80]:
            line = line.strip()
            if not line:
                continue
            if "标准编号" in line or "标准号" in line:
                info["standardNo"] = re.sub(r"^.*[:：]", "", line).strip()
            elif line.startswith("#") and not info.get("name"):
                info["name"] = line.lstrip("#").strip()
            elif "适用范围" in line:
                info["scope"] = re.sub(r"^.*[:：]", "", line).strip()
            elif "发布" in line and "日期" in line:
                info["publishDate"] = re.sub(r"^.*[:：]", "", line).strip()
            elif "实施" in line and "日期" in line:
                info["effectiveDate"] = re.sub(r"^.*[:：]", "", line).strip()
        return info

    @staticmethod
    def _extract_elements_rules(content: str) -> list[dict]:
        elements: list[dict] = []
        service = ReviewAssistService.__new__(ReviewAssistService)
        for item in service._extract_indicator_items_rules(content):
            elements.append(
                {
                    "category": item.category,
                    "name": item.name,
                    "content": item.content,
                    "position": item.position,
                    "clauseNo": item.clauseNo,
                    "requirement": item.requirement,
                    "unit": item.unit,
                }
            )
        if elements:
            return elements[:50]

        section_pattern = re.compile(r"^#{1,3}\s*(.+)$", re.MULTILINE)
        for match in section_pattern.finditer(content):
            title = match.group(1).strip()
            category = "其他"
            if any(k in title for k in ("术语", "定义")):
                category = "术语"
            elif any(k in title for k in ("要求", "技术")):
                category = "技术要求"
            elif any(k in title for k in ("试验", "检验", "测试")):
                category = "试验方法"
            elif "引用" in title:
                category = "引用标准"
            start = match.end()
            next_match = section_pattern.search(content, start)
            end = next_match.start() if next_match else min(start + 500, len(content))
            snippet = content[start:end].strip()[:300]
            if snippet:
                elements.append(
                    {
                        "category": category,
                        "name": title,
                        "content": snippet,
                        "position": title,
                    }
                )
        return elements[:20]

    @staticmethod
    def _extract_test_methods_rules(content: str) -> list[dict]:
        methods: list[dict] = []
        section_pattern = re.compile(
            r"^#{1,3}\s*(.*(?:试验方法|检验方法|试验条件|测试方法).*)$",
            re.MULTILINE | re.IGNORECASE,
        )
        for match in section_pattern.finditer(content):
            title = match.group(1).strip()
            start = match.end()
            next_section = re.search(r"^#{1,3}\s", content[start:], re.MULTILINE)
            end = start + next_section.start() if next_section else min(start + 800, len(content))
            snippet = content[start:end].strip()[:500]
            methods.append(
                {
                    "name": title,
                    "content": snippet,
                    "position": title,
                }
            )
        if not methods:
            for line in content.splitlines():
                if "试验方法" in line or "检验方法" in line:
                    methods.append(
                        {
                            "name": line.strip()[:80],
                            "content": line.strip(),
                            "position": "",
                        }
                    )
                    if len(methods) >= 5:
                        break
        return methods[:10]

    @staticmethod
    def _default_summary(basic_info: BasicInfoDto) -> str:
        parts = []
        if basic_info.name:
            parts.append(f"草案《{basic_info.name}》")
        if basic_info.standardNo:
            parts.append(f"编号 {basic_info.standardNo}")
        return "，".join(parts) + "。" if parts else "已完成草案结构分析。"

    @staticmethod
    def _default_summary_from_text(content: str) -> str:
        first_line = next((ln.strip() for ln in content.splitlines() if ln.strip()), "")
        if first_line:
            return f"草案首行：{first_line[:100]}"
        return "已完成草案文本解析。"

    @staticmethod
    def _map_standard_status(raw: str | None) -> str:
        if not raw:
            return "active"
        if any(k in raw for k in ("废止", "作废", "obsolete")):
            return "obsolete"
        if any(k in raw for k in ("草案", "draft")):
            return "draft"
        return "active"

    @staticmethod
    def _collect_citations(
        comparisons: list[TestMethodComparisonDto],
        reference_checks: list[dict],
    ) -> list[CitationDto]:
        citations: list[CitationDto] = []
        seen: set[str] = set()
        for group in comparisons:
            for comp in group.comparisons:
                for cite in comp.citations:
                    key = cite.chunkId or cite.standardNo
                    if key and key not in seen:
                        seen.add(key)
                        citations.append(cite)
        return citations[:15]

    def _add_running_trace(
        self,
        tool_name: str,
        input_summary: str,
        output_summary: str = "执行中…",
    ) -> None:
        self._traces.append(
            ToolTraceStepDto(
                id=str(uuid.uuid4()),
                toolName=tool_name,
                inputSummary=input_summary,
                outputSummary=output_summary,
                durationMs=0,
                status="running",
                citationIds=[],
                timestamp=datetime.now(UTC).isoformat(),
            )
        )

    def _clear_running_traces(self) -> None:
        self._traces = [step for step in self._traces if step.status != "running"]

    def _add_trace(
        self,
        tool_name: str,
        input_summary: str,
        output_summary: str,
        started: float,
        *,
        status: str = "success",
    ) -> None:
        duration_ms = int((time.perf_counter() - started) * 1000)
        self._traces.append(
            ToolTraceStepDto(
                id=str(uuid.uuid4()),
                toolName=tool_name,
                inputSummary=input_summary,
                outputSummary=output_summary,
                durationMs=duration_ms,
                status=status,
                citationIds=[],
                timestamp=datetime.now(UTC).isoformat(),
            )
        )

    @staticmethod
    def _extract_json(raw: str) -> dict | None:
        text = raw.strip()
        fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if fence:
            text = fence.group(1).strip()
        try:
            data = json.loads(text)
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                try:
                    data = json.loads(text[start : end + 1])
                    return data if isinstance(data, dict) else None
                except json.JSONDecodeError:
                    return None
        return None
