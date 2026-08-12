"""Logic save_markdown — SaveMarkdownUseCase（用例编排）

保存 Markdown 到 content/posts/。
"""
from __future__ import annotations

import logging

from .dtos import SaveMarkdownInput

logger = logging.getLogger("jeff-api")


class SaveMarkdownUseCase:
    """保存 Markdown 到 content/posts/ 用例。"""

    def __init__(self, content_dir: str):
        import os
        self._dir = content_dir

    def execute(self, inp: SaveMarkdownInput) -> str:
        import os
        import re

        safe_slug = re.sub(r"[^a-z0-9\-]", "", inp.slug.lower())
        if not safe_slug or len(safe_slug) > 100:
            raise ValueError("slug 格式无效")

        os.makedirs(self._dir, exist_ok=True)
        filepath = os.path.join(self._dir, f"{safe_slug}.md")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(inp.markdown)

        logger.info(f"SaveMarkdownUseCase: 保存成功 — content/posts/{safe_slug}.md")
        return filepath
