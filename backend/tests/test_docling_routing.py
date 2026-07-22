import fitz

from app.config import get_settings
from app.processing import pdf_converter
from app.processing.pdf_converter import convert_pdf_to_markdown


def _make_text_pdf(text: str = "Chapter 1 Scope\n\nBody text.") -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text, fontsize=12)
    payload = document.tobytes()
    document.close()
    return payload


def _make_empty_page_pdf() -> bytes:
    document = fitz.open()
    document.new_page()
    payload = document.tobytes()
    document.close()
    return payload


def test_docling_routing_disabled_for_empty_pdf(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("DOCLING_WORKER_ENABLED", "false")
    try:
        convert_pdf_to_markdown(_make_empty_page_pdf())
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "无文字层" in str(exc) or "OCR" in str(exc)
    finally:
        get_settings.cache_clear()


def test_docling_routing_uses_worker_for_scan_pdf(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("DOCLING_WORKER_ENABLED", "true")
    monkeypatch.setenv("DOCLING_WORKER_URL", "http://127.0.0.1:8090")
    monkeypatch.setenv("DOCLING_FALLBACK_ON_NO_TEXT_LAYER", "true")

    def fake_convert(payload, probe, *, file_name: str):
        return pdf_converter.PdfConvertResult(
            markdown="<!-- pdf-meta:{} -->\n\n# 扫描件正文",
            metadata={"pageCount": 1},
            parse_engine="docling+rapidocr",
            parse_quality="ocr",
            has_tables=False,
            has_figures=True,
            page_count=1,
            char_count=20,
            warnings=["PDF 无文字层，已通过 Docling worker 解析"],
        )

    monkeypatch.setattr(pdf_converter, "_convert_via_docling_worker", fake_convert)

    try:
        result = convert_pdf_to_markdown(_make_empty_page_pdf(), file_name="scan.pdf")
        assert result.parse_engine == "docling+rapidocr"
        assert result.parse_quality == "ocr"
        assert "扫描件正文" in result.markdown
    finally:
        get_settings.cache_clear()


def test_text_pdf_still_uses_pymupdf_when_docling_enabled(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("DOCLING_WORKER_ENABLED", "true")
    monkeypatch.setenv("DOCLING_WORKER_URL", "http://127.0.0.1:8090")
    try:
        result = convert_pdf_to_markdown(_make_text_pdf())
        assert result.parse_engine in {"pymupdf", "pymupdf+pdfplumber"}
    finally:
        get_settings.cache_clear()
