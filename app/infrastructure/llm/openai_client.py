"""Infrastructure LLM — OpenAI Client 实现

实现 domain.agent.services.ILlmClient 接口。
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

from openai import OpenAI

from app.domain.agent.services import ILlmClient

logger = logging.getLogger("jeff-api")


class OpenAIClient(ILlmClient):
    """ILlmClient 的 OpenAI 实现。"""

    def __init__(self, api_key: str | None = None, base_url: str | None = None,
                 default_model: str = "gpt-4o-mini", timeout: int = 60):
        api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        base_url = base_url or os.getenv("OPENAI_BASE_URL", "")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY 环境变量未设置")

        kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        kwargs["timeout"] = timeout

        self._client = OpenAI(**kwargs)
        self._default_model = default_model
        logger.info(f"OpenAIClient 初始化完成, base_url={base_url or '(default)'}")

    def chat(self, prompt: str, model: str | None = None,
             max_retries: int = 2, **params: Any) -> dict:
        """调用 LLM 返回 JSON dict。"""
        model = model or self._default_model

        call_params: dict[str, Any] = {
            "temperature": params.get("temperature", 0.3),
            "max_tokens": params.get("max_tokens", 2048),
        }
        # top_p 等可选参数
        for k in ("top_p", "frequency_penalty", "presence_penalty"):
            if k in params:
                call_params[k] = params[k]

        last_error = None
        for attempt in range(max_retries + 1):
            try:
                ts = time.time()
                resp = self._client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    **call_params,
                )
                elapsed_ms = int((time.time() - ts) * 1000)

                text = resp.choices[0].message.content.strip() if resp.choices else ""
                usage = resp.usage
                token_info = (
                    f"prompt={usage.prompt_tokens}, completion={usage.completion_tokens}"
                    if usage else "n/a"
                )

                text = _strip_markdown_fence(text)
                result = json.loads(text)
                logger.info(f"LLM OK: model={model}, attempt={attempt+1}, {elapsed_ms}ms, tokens=({token_info})")
                return result

            except (json.JSONDecodeError, Exception) as e:
                last_error = e
                logger.warning(f"LLM retry: attempt={attempt+1}/{max_retries+1}: {_err_short(e)}")
                if attempt < max_retries:
                    time.sleep(0.5 * (attempt + 1))
                    continue

        raise RuntimeError(f"LLM 调用失败（已重试 {max_retries} 次）: {_err_short(last_error)}")


def _strip_markdown_fence(text: str) -> str:
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
    s = str(e)
    return s if len(s) <= 120 else s[:117] + "..."
