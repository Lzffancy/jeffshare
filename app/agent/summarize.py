"""
AI 会话总结工作流

三步流水线：
  Step 1: 内容分类（识别主题和类型）
  Step 2: 提取结论（关键观点、决策、行动项）
  Step 3: 生成 Markdown（组装为博客文章格式）

当前实现：基于 OpenAI SDK 的顺序链。
后续可迁移至 LangGraph 以获得更好的可观测性和错误恢复能力。
"""
import json
import logging
import os

from openai import OpenAI

from .prompts import CLASSIFY_PROMPT, EXTRACT_PROMPT, GENERATE_MD_PROMPT

logger = logging.getLogger("jeff-api")

# ── OpenAI 客户端 ──────────────────────────────────────────────────
_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY", "")
        base_url = os.getenv("OPENAI_BASE_URL", "")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY 环境变量未设置，无法调用 LLM")
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        _client = OpenAI(**kwargs)
    return _client


# ── helper ─────────────────────────────────────────────────────────
def _call_llm(prompt: str, model: str = "gpt-4o-mini") -> dict:
    """调用 LLM 并解析为 JSON，失败时重试一次"""
    client = _get_client()
    for attempt in range(2):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=2048,
            )
            text = resp.choices[0].message.content.strip() if resp.choices else ""
            # 处理可能的 markdown code block 包裹
            if text.startswith("```"):
                lines = text.split("\n")
                # 去掉首行 ```json 和末行 ```
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                text = "\n".join(lines)
            return json.loads(text)
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"LLM call attempt {attempt+1} failed: {e}")
            if attempt == 0:
                continue
            raise RuntimeError(f"LLM 返回格式异常，已重试: {e}")


# ── 三步工作流 ────────────────────────────────────────────────────
def summarize_conversation(
    conversation: str,
    model: str = "gpt-4o-mini",
) -> dict:
    """
    对原始 AI 对话进行三步处理，返回结构化总结。

    Args:
        conversation: 原始对话文本
        model: LLM 模型名（默认 gpt-4o-mini）

    Returns:
        {
            "title": "AI 生成的标题",
            "slug": "english-slug",
            "tags": ["标签1", "标签2"],
            "markdown": "完整 Markdown（含 frontmatter 和正文）",
            "summary": "一句话摘要",
        }
    """
    logger.info(f"summarize_conversation: 开始处理，对话长度={len(conversation)} 字符，model={model}")

    # ── Step 1: 内容分类 ──
    logger.info("Step 1/3: 内容分类")
    classify_result = _call_llm(
        CLASSIFY_PROMPT.format(conversation=conversation),
        model=model,
    )
    category = classify_result.get("category", "misc")
    title_hint = classify_result.get("title_hint", "未命名主题")
    logger.info(f"  分类: category={category}, title_hint={title_hint}")

    # ── Step 2: 提取结论 ──
    logger.info("Step 2/3: 提取结论")
    extract_result = _call_llm(
        EXTRACT_PROMPT.format(
            conversation=conversation,
            category=category,
            title_hint=title_hint,
        ),
        model=model,
    )
    key_points = extract_result.get("key_points", [])
    decisions = extract_result.get("decisions", [])
    action_items = extract_result.get("action_items", [])
    tags = extract_result.get("tags", [])
    logger.info(f"  key_points={len(key_points)}, tags={tags}")

    # ── Step 3: 生成 Markdown ──
    logger.info("Step 3/3: 生成 Markdown")
    generate_result = _call_llm(
        GENERATE_MD_PROMPT.format(
            conversation=conversation,
            title_hint=title_hint,
            category=category,
            tags=tags,
            key_points="\n".join(f"- {p}" for p in key_points),
            decisions="\n".join(f"- {d}" for d in decisions) if decisions else "（无）",
            action_items="\n".join(f"- {a}" for a in action_items) if action_items else "（无）",
        ),
        model=model,
    )
    title = generate_result.get("title", title_hint)
    slug = generate_result.get("slug", "")
    summary = generate_result.get("summary", "")
    body = generate_result.get("markdown", "")

    # ── 组装完整 Markdown（含 frontmatter）──
    from datetime import date

    tag_lines = "\n".join(f"  - {t}" for t in tags)
    full_markdown = f"""---
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
    logger.info(f"summarize_conversation: 完成 — title={title}, slug={slug}")

    return {
        "title": title,
        "slug": slug,
        "tags": tags,
        "markdown": full_markdown,
        "summary": summary,
    }
