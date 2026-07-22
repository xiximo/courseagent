from app.course_agent.rag import hits_to_citations_from_hits
from app.schemas.indexing import ChunkSearchHitDto


def test_hits_to_citations_from_hits_uses_file_name():
    hits = [
        ChunkSearchHitDto(
            chunkId="c1",
            attachmentId="a1",
            standardId="s1",
            fileName="夏令营手册.pdf",
            chunkType="clause",
            docRole="body",
            positionLabel="第二章 · 费用",
            content="费用说明",
            score=0.9,
            source="hybrid",
        ),
        ChunkSearchHitDto(
            chunkId="c2",
            attachmentId="a1",
            standardId="s1",
            fileName="夏令营手册.pdf",
            chunkType="clause",
            docRole="body",
            positionLabel="第一章",
            content="课程介绍",
            score=0.8,
            source="hybrid",
        ),
    ]
    cites = hits_to_citations_from_hits(hits)
    assert cites[0].document == "夏令营手册.pdf"
    assert cites[0].chapter == "第二章 · 费用"
    assert cites[0].attachment_id == "a1"
    assert cites[0].chunk_id == "c1"
