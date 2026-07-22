from app.processing.chunker import chunk_attachment_text


SAMPLE_STANDARD_MD = """<!-- page:1 -->
# 第1章 范围

本标准规定了道路车辆排气污染物的测量方法。

### 5.1 术语

5.1.1 轻型汽车 指最大总质量不超过 3500 kg 的 M1 类车辆。

5.1.2 重型汽车 指最大总质量超过 3500 kg 的车辆。

### 5.2 测量要求

5.2.1 试验应在规定环境条件下进行。

5.2.2 测量设备应经过计量检定。

表 1 试验环境条件

| 项目 | 要求 |
| --- | --- |
| 温度 | 23±5℃ |
| 湿度 | 45%～75% |

图 1 测量系统示意图

测量系统由取样器、分析器和记录装置组成。

<!-- page:2 -->
# 第2章 试验方法

6.1 加载减速法

6.1.1 车辆应预热至发动机正常工作温度。

6.1.2 按表 1 条件进行试验。
"""

SAMPLE_APPENDIX_MD = """# 附录A 资料性附录

A.1 补充说明

本附录给出推荐性说明。

| 序号 | 内容 |
| --- | --- |
| 1 | 示例 |
"""


def test_chunk_standard_structure() -> None:
    chunks = chunk_attachment_text(SAMPLE_STANDARD_MD, doc_role="body", parse_quality="high")
    types = {item.chunk_type for item in chunks}
    assert "clause" in types
    assert "table" in types
    assert "figure" in types

    table_chunks = [item for item in chunks if item.chunk_type == "table"]
    assert len(table_chunks) == 1
    assert table_chunks[0].table_caption == "表1 试验环境条件"
    assert "第1章 范围" in table_chunks[0].content
    assert table_chunks[0].content_json is not None
    assert table_chunks[0].content_json["headers"] == ["项目", "要求"]

    clause_521 = next(item for item in chunks if item.position_label == "5.2.1")
    assert clause_521.chunk_type == "clause"
    assert clause_521.clause_level == "clause"
    assert clause_521.parent_label is not None
    assert clause_521.page_start == 1

    figure_chunks = [item for item in chunks if item.chunk_type == "figure"]
    assert len(figure_chunks) == 1
    assert figure_chunks[0].figure_caption == "图1 测量系统示意图"
    assert "测量系统" in figure_chunks[0].content


def test_chunk_appendix_domain() -> None:
    chunks = chunk_attachment_text(SAMPLE_APPENDIX_MD, doc_role="body")
    appendix_chunks = [item for item in chunks if item.chunk_type in {"appendix", "table"}]
    assert appendix_chunks
    assert any(item.position_label == "A.1" for item in chunks)


def test_chunk_doc_role_explanation() -> None:
    chunks = chunk_attachment_text("编制说明\n\n本说明仅供理解标准条文。", doc_role="explanation")
    assert all(item.doc_role == "explanation" for item in chunks)


def test_fallback_by_page_when_no_structure() -> None:
    text = """<!-- page:1 -->
第一段内容。

<!-- page:2 -->
第二段内容。
"""
    chunks = chunk_attachment_text(text, doc_role="body", parse_quality="medium")
    assert len(chunks) >= 2
    assert chunks[0].page_start == 1
    assert chunks[1].page_start == 2


def test_long_clause_splits_by_paragraph() -> None:
    long_body = "6.3.1 长条款\n\n" + ("这是条款正文。" * 400)
    text = f"# 第6章 附加要求\n\n{long_body}"
    chunks = chunk_attachment_text(text, doc_role="body", parse_quality="high")
    clause_chunks = [item for item in chunks if item.position_label == "6.3.1"]
    assert len(clause_chunks) >= 2
    assert all(item.position_label == "6.3.1" for item in clause_chunks)


PRODUCT_HANDBOOK_MD = """# 第一章　平台定位

OPC平台服务希望以个人能力承接AI项目的学习者和专业人员，提供课程学习、能力测试、真实订单对接、AI工具和同行社区。

| 模块 | 作用 |
| --- | --- |
| AI素养学院 | 提供内容生成、软件系统与智能体等赛道课程。 |
| 接单吧 | 按认证等级匹配真实订单。 |
"""


def test_table_chunk_includes_section_context() -> None:
    chunks = chunk_attachment_text(PRODUCT_HANDBOOK_MD, doc_role="body", parse_quality="high")
    table_chunks = [item for item in chunks if item.chunk_type == "table"]
    assert len(table_chunks) == 1
    table = table_chunks[0]
    assert "第一章" in table.content
    assert "平台定位" in table.content
    assert "| 模块 | 作用 |" in table.content
    assert table.position_label == "第一章　平台定位"
    assert table.content_json is not None
    assert table.content_json["headers"] == ["模块", "作用"]
