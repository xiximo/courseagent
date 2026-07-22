import fitz

from app.processing.pdf_converter import convert_pdf_to_markdown, validate_pdf_payload


def _make_text_pdf(
    text: str = "Chapter 1 Scope\n\nThis standard defines basic requirements.\n\nTable 1 Test conditions\n\n1.1 Terms",
) -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text, fontsize=12)
    payload = document.tobytes()
    document.close()
    return payload


def test_validate_pdf_payload() -> None:
    validate_pdf_payload(_make_text_pdf())
    try:
        validate_pdf_payload(b"not a pdf")
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "PDF" in str(exc)


def test_convert_text_pdf() -> None:
    result = convert_pdf_to_markdown(_make_text_pdf())
    assert result.page_count == 1
    assert result.char_count > 0
    assert "Scope" in result.markdown or "standard" in result.markdown
    assert result.parse_engine in {"pymupdf", "pymupdf+pdfplumber"}
    assert result.parse_quality in {"high", "medium", "low"}


def test_reject_empty_pdf_text() -> None:
    document = fitz.open()
    document.new_page()
    payload = document.tobytes()
    document.close()
    try:
        convert_pdf_to_markdown(payload)
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "无文字层" in str(exc) or "未抽取" in str(exc)
