"""LLM Client — OpenAI SDK 封装

单例模式，支持重试、超时、token 统计。
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

from openai import OpenAI

logger = logging.getLogger("jeff-api")

_client: OpenAI | None = None
_default_model = "gpt-4o-mini"


def get_llm_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY", "")
        base_url = os.getenv("OPENAI_BASE_URL", "")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY 环境变量未设置")
        kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        timeout = int(os.getenv("OPENAI_TIMEOUT", "60"))
        kwargs["timeout"] = timeout
        _client = OpenAI(**kwargs)
        logger.info(f"LLM Client 初始化完成, base_url={base_url or '(default)'}, timeout={timeout}s")
    return _client


def chat(
    prompt: str,
    model: str | None = None,
    max_retries: int = 2,
    **model_params: Any,
) -> dict:
    """调用 LLM 并解析为 JSON dict。

    Args:
        prompt: 用户 prompt
        model: 模型名，默认从环境变量或 gpt-4o-mini
        max_retries: 解析失败时最大重试次数
        **model_params: temperature, max_tokens, top_p 等

    Returns:
        LLM 返回的 JSON dict

    Raises:
        RuntimeError: 调用或解析失败
    """
    client = get_llm_client()
    model = model or _default_model

    # 默认参数
    params: dict[str, Any] = {
        "temperature": 0.3,
        "max_tokens": 2048,
    }
    params.update(model_params)

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            ts = time.time()
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                **params,
            )
            elapsed_ms = int((time.time() - ts) * 1000)

            text = resp.choices[0].message.content.strip() if resp.choices else ""
            usage = resp.usage
            token_info = (
                f"prompt={usage.prompt_tokens}, completion={usage.completion_tokens}"
                if usage else "n/a"
            )

            # 处理 markdown code block 包裹
            text = _strip_markdown_fence(text)

            result = json.loads(text)
            logger.info(f"LLM call OK: model={model}, attempt={attempt+1}, {elapsed_ms}ms, tokens=({token_info})")
            return result

        except (json.JSONDecodeError, Exception) as e:
            last_error = e
            logger.warning(
                f"LLM call failed: model={model}, attempt={attempt+1}/{max_retries+1}: {_err_short(e)}"
            )
            if attempt < max_retries:
                time.sleep(0.5 * (attempt + 1))  # 退避
                continue

    raise RuntimeError(f"LLM 调用失败（已重试 {max_retries} 次）: {_err_short(last_error)}")


def _strip_markdown_fence(text: str) -> str:
    """去掉 ```json ... ``` 包裹。"""
    t = text.strip()
    if t.startswith("```"):
        lines = t.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        t = "\n".join(lines).strip()
    return t


def _err_short(e: Any) -> str:
    """错误信息截断（最多 120 字）。"""
    s = str(e)
    return s if len(s) <= 120 else s[:117] + "..."
