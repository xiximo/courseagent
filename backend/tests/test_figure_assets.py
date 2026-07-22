from uuid import UUID

from app.processing.figure_assets import rewrite_markdown_image_links


def test_rewrite_windows_absolute_image_path() -> None:
    attachment_id = UUID("11111111-1111-1111-1111-111111111111")
    api_url = f"/api/v1/qibiao/processing/attachments/{attachment_id}/extracted-assets/fig.png"
    markdown = (
        "![Image](C:\\Users\\wangx\\AppData\\Local\\Temp\\tmpabc\\figures\\fig.png)"
    )
    rewritten = rewrite_markdown_image_links(markdown, {"fig.png": api_url})
    assert rewritten == f"![Image]({api_url})"
