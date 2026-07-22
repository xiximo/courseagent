"""AI智审官评审报告合成：基于草案分析结果 + 检索证据生成 ReviewReportDto。"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from app.db.models.llm_config import LlmConfigRecord
from app.llm.doubao_client import DoubaoChatMessage, DoubaoClientError, chat_completion
from app.review.json_utils import extract_json_from_llm
from app.schemas.qa import CitationDto
from app.schemas.review import DraftAnalysisResultDto, TestMethodComparisonDto
from app.schemas.review_report import (
    REVIEW_REPORT_DISCLAIMER,
    REVIEW_REPORT_TITLE,
    ImprovementRowDto,
    MissingFeatureRowDto,
    ReviewReportBasicInfoDto,
    ReviewReportDto,
    SummaryPointDto,
)
from app.services.llm_settings import is_llm_configured, resolve_llm_runtime

logger = logging.getLogger(__name__)

DRAFT_EXCERPT_LIMIT = 6000
EVIDENCE_EXCERPT_LIMIT = 4000

REPORT_SYNTHESIS_SYSTEM_PROMPT = """你是 AI智审官，负责将企业标准草案分析结果合成为《企业标准专业性评审报告》。

请严格输出 JSON（不要 markdown 代码块），结构如下：
{
  "basicInfo": {
    "standardName": "标准名称",
    "standardNo": "标准编号，未提供则写「无（未提供）」",
    "partName": "所属零部件",
    "reviewDate": "YYYY-MM-DD"
  },
  "missingFeatures": [
    {
      "description": "缺失特性说明",
      "relatedStandards": "涉及标准（含标准号、名称与条款）",
      "citationIds": ["chunkId 或留空"]
    }
  ],
  "improvements": [
    {
      "featureElement": "特性要素",
      "suggestedContent": "建议内容",
      "suggestedMethod": "建议方法",
      "referenceStandards": "参考标准",
      "citationIds": []
    }
  ],
  "summaryPoints": [
    {
      "order": 1,
      "title": "小标题",
      "content": "具体说明与建议"
    }
  ],
  "finalConclusion": "最终结论段落"
}

章节语义：
1. missingFeatures：行标/国标/主机厂有而企标完全没有的要求（diff=missing）。
2. improvements：企标已有但量化不足、偏松、方法不完整、需对标提升的条款。
3. summaryPoints：对缺失与需提升问题的归纳，order 从 1 连续编号。
4. finalConclusion：总体水平判断与修订建议（一段完整文字）。

规则：
1. 优先使用输入中的「分析结果」与「检索证据」，不要编造不存在的标准条款原文。
2. 知识库未命中、仅能凭行业经验推断时，在 relatedStandards/referenceStandards 末尾标注「【推理，建议人工核实】」。
3. 统计性表述（如「共 N 项未量化」）须有分析结果支撑，无法统计时不要编造具体数字。
4. citationIds 仅填写输入证据片段中给出的 chunkId；无则留空数组。
5. 使用简体中文；无内容的数组可为 []，但不要省略必填字段。"""

REPORT_JSON_SCHEMA_HINT = """{
  "basicInfo": {"standardName":"","standardNo":"","partName":"","reviewDate":""},
  "missingFeatures": [{"description":"","relatedStandards":"","citationIds":[]}],
  "improvements": [{"featureElement":"","suggestedContent":"","suggestedMethod":"","referenceStandards":"","citationIds":[]}],
  "summaryPoints": [{"order":1,"title":"","content":""}],
  "finalConclusion": ""
}"""


class ReportSynthesisService:
    def __init__(self, db: Session, llm_config: LlmConfigRecord) -> None:
        self.db = db
        self.llm_config = resolve_llm_runtime(llm_config)

    def synthesize(
        self,
        *,
        analysis: DraftAnalysisResultDto,
        draft_excerpt: str = "",
        parse_note: str = "",
    ) -> ReviewReportDto:
        if is_llm_configured(self.llm_config):
            llm_report = self._synthesize_with_llm(
                analysis=analysis,
                draft_excerpt=draft_excerpt,
                parse_note=parse_note,
            )
            if llm_report is not None:
                return llm_report
        return self._synthesize_with_rules(analysis)

    def _synthesize_with_llm(
        self,
        *,
        analysis: DraftAnalysisResultDto,
        draft_excerpt: str,
        parse_note: str,
    ) -> ReviewReportDto | None:
        evidence = self._build_evidence_context(analysis)
        user_prompt = self._build_user_prompt(
            analysis=analysis,
            draft_excerpt=draft_excerpt,
            evidence=evidence,
            parse_note=parse_note,
        )

        for attempt in range(2):
            try:
                raw = chat_completion(
                    api_key=self.llm_config.api_key,
                    endpoint_id=self.llm_config.endpoint_id,
                    base_url=self.llm_config.base_url,
                    timeout_seconds=self.llm_config.timeout_seconds,
                    messages=[
                        DoubaoChatMessage(
                            role="system",
                            content=REPORT_SYNTHESIS_SYSTEM_PROMPT,
                        ),
                        DoubaoChatMessage(role="user", content=user_prompt),
                    ],
                    temperature=0.1,
                )
            except DoubaoClientError as exc:
                logger.warning("Report synthesis LLM failed: %s", exc)
                return None

            payload = extract_json_from_llm(raw)
            if payload is None and attempt == 0:
                user_prompt = (
                    f"{user_prompt}\n\n"
                    "上次输出不是合法 JSON。请仅输出一个 JSON 对象，"
                    f"结构如下：\n{REPORT_JSON_SCHEMA_HINT}"
                )
                continue
            if payload is None:
                return None

            try:
                return self._post_process(payload, analysis)
            except Exception as exc:
                logger.warning("Report synthesis validation failed: %s", exc)
                if attempt == 0:
                    user_prompt = (
                        f"{user_prompt}\n\n"
                        f"JSON 校验失败：{exc}。请修正后重新输出。"
                    )
                    continue
                return None
        return None

    def _build_user_prompt(
        self,
        *,
        analysis: DraftAnalysisResultDto,
        draft_excerpt: str,
        evidence: str,
        parse_note: str,
    ) -> str:
        analysis_json = analysis.model_dump(
            mode="json",
            exclude={"thinkingSteps"},
        )
        trimmed_draft = draft_excerpt.strip()[:DRAFT_EXCERPT_LIMIT]
        sections = [
            "请根据以下材料合成评审报告 JSON。",
            "",
            "【输出格式示意】（仅说明字段结构，禁止照搬示例中的零部件与数值）",
            REPORT_JSON_SCHEMA_HINT,
            "",
            "【草案分析结果】",
            json.dumps(analysis_json, ensure_ascii=False, indent=2),
            "",
            "【检索与对比证据】",
            evidence or "（无额外检索证据）",
        ]
        if trimmed_draft:
            sections.extend(
                [
                    "",
                    "【草案摘录】",
                    trimmed_draft,
                ]
            )
        if parse_note:
            sections.extend(["", f"【解析说明】{parse_note}"])
        sections.extend(
            [
                "",
                f"【评审日期】{date.today().isoformat()}",
                "",
                "请输出 JSON。",
            ]
        )
        return "\n".join(sections)

    def _build_evidence_context(self, analysis: DraftAnalysisResultDto) -> str:
        lines: list[str] = []

        for issue in analysis.issues[:20]:
            if not isinstance(issue, dict):
                continue
            lines.append(
                f"- 问题[{issue.get('type', '')}]：{issue.get('description', '')}；"
                f"建议：{issue.get('suggestion', '')}"
            )

        for suggestion in analysis.suggestions[:10]:
            lines.append(f"- 关注点：{suggestion}")

        for group in analysis.testMethodComparisons[:8]:
            lines.append(f"\n试验方法「{group.draftMethod}」对比：")
            for comp in group.comparisons[:4]:
                cite_ids = [c.chunkId for c in comp.citations if c.chunkId]
                cite_hint = f"，citationIds={cite_ids}" if cite_ids else ""
                lines.append(
                    f"  - [{comp.sourceLabel}] {comp.standardNo} "
                    f"{comp.matchedClause} diff={comp.diff} "
                    f"{comp.note}{cite_hint}"
                )

        for cite in analysis.citations[:12]:
            chunk_id = cite.chunkId or ""
            lines.append(
                f"- 证据 chunkId={chunk_id} "
                f"{cite.standardNo} {cite.standardName} "
                f"{cite.position} {cite.excerpt[:120]}"
            )

        text = "\n".join(lines)
        return text[:EVIDENCE_EXCERPT_LIMIT]

    def _post_process(
        self,
        payload: dict,
        analysis: DraftAnalysisResultDto,
    ) -> ReviewReportDto:
        basic_raw = payload.get("basicInfo") if isinstance(payload.get("basicInfo"), dict) else {}
        basic_info = ReviewReportBasicInfoDto(
            standardName=str(
                basic_raw.get("standardName") or analysis.basicInfo.name or ""
            ).strip(),
            standardNo=str(
                basic_raw.get("standardNo") or analysis.basicInfo.standardNo or ""
            ).strip()
            or "无（未提供）",
            partName=str(
                basic_raw.get("partName")
                or analysis.basicInfo.partName
                or analysis.basicInfo.partCode
                or ""
            ).strip(),
            reviewDate=str(basic_raw.get("reviewDate") or date.today().isoformat()).strip(),
        )

        missing_features = self._parse_missing_features(payload.get("missingFeatures"))
        improvements = self._parse_improvements(payload.get("improvements"))
        summary_points = self._parse_summary_points(payload.get("summaryPoints"))
        final_conclusion = str(payload.get("finalConclusion") or analysis.summary or "").strip()

        if not missing_features and not improvements:
            rule_fallback = self._synthesize_with_rules(analysis)
            missing_features = rule_fallback.missingFeatures
            improvements = rule_fallback.improvements
            if not summary_points:
                summary_points = rule_fallback.summaryPoints
            if not final_conclusion:
                final_conclusion = rule_fallback.finalConclusion

        return ReviewReportDto(
            taskId=str(uuid.uuid4()),
            sourceTaskId=analysis.taskId,
            title=REVIEW_REPORT_TITLE,
            basicInfo=basic_info,
            missingFeatures=missing_features,
            improvements=improvements,
            summaryPoints=summary_points,
            finalConclusion=final_conclusion,
            disclaimer=REVIEW_REPORT_DISCLAIMER,
            citations=self._merge_citations(analysis),
            generatedAt=datetime.now(UTC).isoformat(),
        )

    def _synthesize_with_rules(self, analysis: DraftAnalysisResultDto) -> ReviewReportDto:
        basic = analysis.basicInfo
        missing_features: list[MissingFeatureRowDto] = []
        improvements: list[ImprovementRowDto] = []

        for issue in analysis.issues:
            if not isinstance(issue, dict):
                continue
            issue_type = str(issue.get("type") or "")
            description = str(issue.get("description") or "").strip()
            suggestion = str(issue.get("suggestion") or "").strip()
            if not description:
                continue
            if issue_type == "missing":
                missing_features.append(
                    MissingFeatureRowDto(
                        description=description,
                        relatedStandards=suggestion or "建议人工对标行标/国标",
                    )
                )
            elif issue_type in {"insufficient", "conflict", "expired"}:
                improvements.append(
                    ImprovementRowDto(
                        featureElement=description[:40],
                        suggestedContent=suggestion or description,
                        suggestedMethod="建议参照对标标准中的试验方法",
                        referenceStandards="待人工核实",
                    )
                )

        missing_features.extend(
            self._missing_from_comparisons(analysis.testMethodComparisons)
        )
        improvements.extend(
            self._improvements_from_comparisons(analysis.testMethodComparisons)
        )

        missing_features = self._dedupe_missing(missing_features)[:15]
        improvements = self._dedupe_improvements(improvements)[:15]

        summary_points = [
            SummaryPointDto(order=index, title="", content=item)
            for index, item in enumerate(analysis.suggestions[:8], start=1)
        ]
        if not summary_points and (missing_features or improvements):
            summary_points.append(
                SummaryPointDto(
                    order=1,
                    title="审核关注点",
                    content="建议结合缺失特性与需提升结论逐项修订草案。",
                )
            )

        final_conclusion = analysis.summary.strip() or (
            "建议结合上述缺失特性与需提升结论修订草案，提升技术先进性与可执行性。"
        )

        return ReviewReportDto(
            taskId=str(uuid.uuid4()),
            sourceTaskId=analysis.taskId,
            title=REVIEW_REPORT_TITLE,
            basicInfo=ReviewReportBasicInfoDto(
                standardName=basic.name,
                standardNo=basic.standardNo or "无（未提供）",
                partName=basic.partName or basic.partCode,
                reviewDate=date.today().isoformat(),
            ),
            missingFeatures=missing_features,
            improvements=improvements,
            summaryPoints=summary_points,
            finalConclusion=final_conclusion,
            disclaimer=REVIEW_REPORT_DISCLAIMER,
            citations=self._merge_citations(analysis),
            generatedAt=datetime.now(UTC).isoformat(),
        )

    @staticmethod
    def _parse_missing_features(raw: object) -> list[MissingFeatureRowDto]:
        if not isinstance(raw, list):
            return []
        rows: list[MissingFeatureRowDto] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            description = str(item.get("description") or "").strip()
            if not description:
                continue
            citation_ids = [
                str(value).strip()
                for value in item.get("citationIds") or []
                if str(value).strip()
            ]
            rows.append(
                MissingFeatureRowDto(
                    description=description,
                    relatedStandards=str(item.get("relatedStandards") or "").strip(),
                    citationIds=citation_ids,
                )
            )
        return rows

    @staticmethod
    def _parse_improvements(raw: object) -> list[ImprovementRowDto]:
        if not isinstance(raw, list):
            return []
        rows: list[ImprovementRowDto] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            feature = str(item.get("featureElement") or "").strip()
            if not feature:
                continue
            citation_ids = [
                str(value).strip()
                for value in item.get("citationIds") or []
                if str(value).strip()
            ]
            rows.append(
                ImprovementRowDto(
                    featureElement=feature,
                    suggestedContent=str(item.get("suggestedContent") or "").strip(),
                    suggestedMethod=str(item.get("suggestedMethod") or "").strip(),
                    referenceStandards=str(item.get("referenceStandards") or "").strip(),
                    citationIds=citation_ids,
                )
            )
        return rows

    @staticmethod
    def _parse_summary_points(raw: object) -> list[SummaryPointDto]:
        if not isinstance(raw, list):
            return []
        rows: list[SummaryPointDto] = []
        for index, item in enumerate(raw, start=1):
            if not isinstance(item, dict):
                continue
            content = str(item.get("content") or "").strip()
            title = str(item.get("title") or "").strip()
            if not content and not title:
                continue
            order_raw = item.get("order")
            order = int(order_raw) if isinstance(order_raw, int) and order_raw >= 1 else index
            rows.append(SummaryPointDto(order=order, title=title, content=content))
        rows.sort(key=lambda row: row.order)
        for idx, row in enumerate(rows, start=1):
            row.order = idx
        return rows

    @staticmethod
    def _missing_from_comparisons(
        comparisons: list[TestMethodComparisonDto],
    ) -> list[MissingFeatureRowDto]:
        rows: list[MissingFeatureRowDto] = []
        for group in comparisons:
            for comp in group.comparisons:
                if comp.diff != "missing":
                    continue
                related = ReportSynthesisService._format_standard_ref(comp)
                if comp.inferenceSource == "llm" and "【推理" not in related:
                    related = f"{related}【推理，建议人工核实】"
                rows.append(
                    MissingFeatureRowDto(
                        description=f"{group.draftMethod}：{comp.note or '对照标准有而草案缺失'}",
                        relatedStandards=related,
                        citationIds=[
                            c.chunkId for c in comp.citations if c.chunkId
                        ],
                    )
                )
        return rows

    @staticmethod
    def _improvements_from_comparisons(
        comparisons: list[TestMethodComparisonDto],
    ) -> list[ImprovementRowDto]:
        rows: list[ImprovementRowDto] = []
        for group in comparisons:
            for comp in group.comparisons:
                if comp.diff not in {"stricter", "looser", "conflict"}:
                    continue
                ref = ReportSynthesisService._format_standard_ref(comp)
                rows.append(
                    ImprovementRowDto(
                        featureElement=group.draftMethod,
                        suggestedContent=comp.note or f"对照{comp.sourceLabel}需调整",
                        suggestedMethod=group.draftContent[:200] or "建议参照对标标准试验方法",
                        referenceStandards=ref,
                        citationIds=[
                            c.chunkId for c in comp.citations if c.chunkId
                        ],
                    )
                )
        return rows

    @staticmethod
    def _format_standard_ref(comp) -> str:
        parts = [comp.standardNo, comp.standardName, comp.matchedClause]
        return " ".join(part for part in parts if part and part != "—").strip() or "待人工核实"

    @staticmethod
    def _dedupe_missing(rows: list[MissingFeatureRowDto]) -> list[MissingFeatureRowDto]:
        seen: set[str] = set()
        result: list[MissingFeatureRowDto] = []
        for row in rows:
            key = row.description
            if key in seen:
                continue
            seen.add(key)
            result.append(row)
        return result

    @staticmethod
    def _dedupe_improvements(rows: list[ImprovementRowDto]) -> list[ImprovementRowDto]:
        seen: set[str] = set()
        result: list[ImprovementRowDto] = []
        for row in rows:
            key = (row.featureElement, row.suggestedContent)
            if key in seen:
                continue
            seen.add(key)
            result.append(row)
        return result

    @staticmethod
    def _merge_citations(analysis: DraftAnalysisResultDto) -> list[CitationDto]:
        citations: list[CitationDto] = []
        seen: set[str] = set()
        for cite in analysis.citations:
            key = cite.chunkId or cite.standardNo
            if key and key not in seen:
                seen.add(key)
                citations.append(cite)
        for group in analysis.testMethodComparisons:
            for comp in group.comparisons:
                for cite in comp.citations:
                    key = cite.chunkId or cite.standardNo
                    if key and key not in seen:
                        seen.add(key)
                        citations.append(cite)
        return citations[:20]
