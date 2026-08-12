"""SummarizeAgent — AI 会话总结，配置驱动的 LangGraph 工作流

由 config.steps 动态构建 StateGraph：
  Step 1 (llm_call): 内容分类
  Step 2 (llm_call): 提取结论
  Step 3 (transform): 组装 Markdown (纯代码)
"""
from __future__ import annotations

import json
import logging
from datetime import date

from langgraph.graph import StateGraph

from ..base import BaseAgent, AgentState
from .. import register

logger = logging.getLogger("jeff-api")


@register("conversation-summarizer")
class SummarizeAgent(BaseAgent):
    """AI 会话 → 博客草稿"""

    def build_graph(self) -> StateGraph:
        return self._build_linear_graph()

    def assemble_output(self, state: dict) -> dict:
        """从 state 提取最终输出。

        如果 config 中定义了 transform step 产出 final_markdown，
        则直接使用；否则子类自行组装。
        """
        classify = state.get("classify_result", {})
        extract = state.get("extract_result", {})
        final_md = state.get("final_markdown", "")

        # 确保是 dict
        if isinstance(classify, str):
            classify = json.loads(classify)
        if isinstance(extract, str):
            extract = json.loads(extract)

        title = extract.get("title", "")
        if not title:
            # fallback：尝试从 classify 拿标题提示
            title = classify.get("title_hint", "AI 会话总结")

        tags = extract.get("tags", [])
        slug = extract.get("slug", "") or self._slugify(title)
        summary = extract.get("summary", "")

        markdown = final_md if final_md else self._assemble_fallback(title, summary, tags, extract, classify, state)

        return {
            "title": title,
            "slug": slug,
            "tags": tags,
            "markdown": markdown,
            "summary": summary,
        }

    # ── 内置 transform 函数（由 config steps 中的 transform_func 指定） ──

    def _transform_assemble_markdown(self, state: dict) -> str:
        """纯代码组装 Markdown（不消耗 LLM token）。"""
        classify = self._ensure_dict(state.get("classify_result", {}))
        extract = self._ensure_dict(state.get("extract_result", {}))

        title = extract.get("title", classify.get("title_hint", "未命名"))
        slug = extract.get("slug", "") or self._slugify(title)
        summary = extract.get("summary", "由 AI 自动总结的会话内容")
        tags = extract.get("tags", [])
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

    # ── 辅助 ────────────────────────────────────────────────────────

    @staticmethod
    def _ensure_dict(v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return {}
        return v if isinstance(v, dict) else {}

    @staticmethod
    def _slugify(text: str) -> str:
        import re
        slug = text.lower().strip()
        slug = re.sub(r"[^\w\s-]", "", slug)
        slug = re.sub(r"[\s_]+", "-", slug)
        slug = re.sub(r"-{2,}", "-", slug)
        return slug.strip("-")[:80]

    @staticmethod
    def _assemble_fallback(title, summary, tags, classify, extract, state) -> str:
        """当 config 中没有 transform step 时的 fallback 组装。"""
        body = extract.get("markdown", "") if isinstance(extract, dict) else ""
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
