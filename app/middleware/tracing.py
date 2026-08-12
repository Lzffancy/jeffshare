"""Middleware tracing — 轻量 trace_id 全链路追踪

不引入 OpenTelemetry SDK，自研实现：
- 每个请求生成/透传 trace_id（优先级：X-Trace-Id → X-Request-Id → uuid4）
- 响应头回写 X-Trace-Id，供客户端排查时引用
- 通过 contextvars 在协程间传递，任意模块可用 get_trace_id() 读取
- TraceIdFilter 将 trace_id 注入每条日志记录

用法：
    from app.middleware.tracing import get_trace_id
    tid = get_trace_id()   # 当前请求的 trace_id，无请求上下文时返回 "-"
"""
from __future__ import annotations

import contextvars
import logging
import uuid
from typing import Any

# 请求上下文中的 trace_id（协程安全）
_trace_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "trace_id", default="-"
)

# 上游可透传的 trace_id 头，按优先级排序
_UPSTREAM_HEADERS = ("x-trace-id", "x-request-id")

# 响应回写头名
RESPONSE_HEADER = "X-Trace-Id"


def get_trace_id() -> str:
    """返回当前请求的 trace_id；无请求上下文时返回 '-'。"""
    return _trace_id.get()


def _extract_upstream(headers: Any) -> str | None:
    for name in _UPSTREAM_HEADERS:
        value = headers.get(name)
        if value:
            return value.strip()
    return None


class TracingMiddleware:
    """纯 ASGI 中间件：为每个请求生成/透传 trace_id，回写响应头。"""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {
            k.decode("latin-1").lower(): v.decode("latin-1")
            for k, v in scope.get("headers", [])
        }
        trace_id = _extract_upstream(headers) or uuid.uuid4().hex

        async def send_wrapper(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                msg_headers = list(message.get("headers", []))
                msg_headers.append(
                    (RESPONSE_HEADER.encode("latin-1"), trace_id.encode("latin-1"))
                )
                message["headers"] = msg_headers
            await send(message)

        token = _trace_id.set(trace_id)
        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            _trace_id.reset(token)


class TraceIdFilter(logging.Filter):
    """logging filter：为每条日志记录附加 trace_id 属性。"""

    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = _trace_id.get()
        return True


def setup_tracing_logging(level: int = logging.INFO) -> None:
    """配置根 logger：统一格式 + trace_id 注入。

    格式：[trace_id] LEVEL name - message
    """
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            "[%(trace_id)s] %(levelname)s %(name)s - %(message)s"
        )
    )
    handler.addFilter(TraceIdFilter())

    root = logging.getLogger()
    root.setLevel(level)
    # 移除默认 handler，避免重复输出
    for h in list(root.handlers):
        root.removeHandler(h)
    root.addHandler(handler)
