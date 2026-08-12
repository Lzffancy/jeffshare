// trace.js — 前端 trace_id 生成/透传工具
//
// 前端是链路起点：每次用户操作生成一个 trace_id，随请求传给后端。
// 后端透传（X-Trace-Id 优先级最高），从而把「前端操作」和「后端日志」串起来。
//
// 用法：
//   import { newTraceId, fetchWithTrace } from "../utils/trace";
//   const tid = newTraceId();              // 生成新 trace_id（每次用户操作）
//   const resp = await fetchWithTrace("/api/xxx", { method: "POST", ... });

/**
 * 生成一个新的 trace_id（32 位 hex，与后端 uuid4().hex 格式一致）。
 * 优先使用 crypto.randomUUID（去掉连字符），降级用 Math.random。
 */
export function newTraceId() {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID().replace(/-/g, "");
  }
  // 降级：16 字节随机 hex
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

/**
 * 带 trace_id 的 fetch 封装。
 * 自动注入 X-Trace-Id 请求头；若响应头回写 X-Trace-Id，则优先采用后端透传的值。
 * 额外参数 traceId 可显式指定（默认自动生成一个）。
 */
export async function fetchWithTrace(url, options = {}) {
  const traceId = options.traceId || newTraceId();
  const headers = new Headers(options.headers || {});
  headers.set("X-Trace-Id", traceId);

  const resp = await fetch(url, { ...options, headers });

  // 后端可能透传/回写不同的 trace_id，以响应头为准（保持与后端一致）
  const serverTraceId = resp.headers.get("X-Trace-Id");
  const finalTraceId = serverTraceId || traceId;

  // 前端日志也带 trace_id，形成完整链路
  console.debug(`[trace:${finalTraceId}] ${options.method || "GET"} ${url} -> ${resp.status}`);

  return resp;
}
