"""Application services — 用例编排

每个 UseCase 协调 domain 服务 + repository 完成一个完整的用户需求。
"""
from __future__ import annotations

import logging

from app.domain.agent.services import (
    AgentOrchestrator,
    ILlmClient,
    IWorkflowEngine,
    WorkflowContext,
)
from app.domain.agent.repository import IAgentConfigRepo, IExecutionRepo
from .dtos import SummarizeInput, SummarizeOutput, SaveMarkdownInput

logger = logging.getLogger("jeff-api")


class SummarizeUseCase:
    """AI 会话总结用例。

    流程：
      1. 从 repo 加载 active 版本配置
      2. 构建 WorkflowContext（注入 conversation）
      3. 通过 AgentOrchestrator 执行步骤
      4. 从 context.outputs 提取结果，转换为 SummarizeOutput
    """

    def __init__(
        self,
        repo: IAgentConfigRepo,
        llm: ILlmClient,
        engine: IWorkflowEngine,
    ):
        self._repo = repo
        self._llm = llm
        self._engine = engine

    def execute(self, inp: SummarizeInput, agent_name: str = "conversation-summarizer") -> SummarizeOutput:
        # 1. 加载配置
        version = self._repo.get_active_version(agent_name)

        # 2. 构建上下文
        context = WorkflowContext(inputs={"conversation": inp.conversation})

        # 3. 执行
        orchestrator = AgentOrchestrator(
            version=version, llm=self._llm, engine=self._engine
        )
        context = orchestrator.execute(context)

        # 4. 组装输出
        import json

        classify = context.get("classify_result", {})
        extract = context.get("extract_result", {})
        final_md = context.get("final_markdown", "")

        if isinstance(classify, str):
            classify = json.loads(classify)
        if isinstance(extract, str):
            extract = json.loads(extract)

        title = extract.get("title", "")
        if not title:
            title = classify.get("title_hint", "AI 会话总结")

        tags = extract.get("tags", [])
        slug = extract.get("slug", "") or SummarizeUseCase._slugify(title)

        markdown = final_md or SummarizeUseCase._assemble_fallback(title, extract.get("summary", ""), tags, extract)

        return SummarizeOutput(
            title=title,
            slug=slug,
            tags=tags,
            markdown=markdown,
            summary=extract.get("summary", ""),
        )

    @staticmethod
    def _slugify(text: str) -> str:
        import re
        slug = text.lower().strip()
        slug = re.sub(r"[^\w\s-]", "", slug)
        slug = re.sub(r"[\s_]+", "-", slug)
        slug = re.sub(r"-{2,}", "-", slug)
        return slug.strip("-")[:80]

    @staticmethod
    def _assemble_fallback(title: str, summary: str, tags: list[str], extract: dict) -> str:
        from datetime import date

        body = extract.get("markdown", "")
        tag_lines = "\n".join(f"  - {t}" for t in tags) if tags else "  - ai-summary"
        return f"""---
title: {title}
date: {date.today().isoformat()}
tags:
{tag_lines}
draft: false
source: ai
---

> {summary}

{body}
"""


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
