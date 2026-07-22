from app.course_agent.rag import _match_attachment, _normalize_doc_label
from app.db.models.attachment import Attachment


def test_normalize_doc_label_strips_legacy_prefix():
    assert _normalize_doc_label("《素材A·暑期AI素养夏令营手册》") == "暑期ai素养夏令营手册"


def test_match_attachment_by_partial_name():
    attachment = Attachment(
        display_name="暑期AI素养夏令营手册.pdf",
        sprs_file_id="file-1",
    )
    matched = _match_attachment("《素材A·暑期AI素养夏令营手册》", [attachment])
    assert matched is attachment
