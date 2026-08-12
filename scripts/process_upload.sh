#!/bin/bash
# process_upload.sh — 由 UploadProcessingUseCase 调用
# 用法: bash scripts/process_upload.sh <upload_id>
#
# Claude CLI 智能处理管线:
#   source/{upload_id}/ 下的原始文件
#     → Claude 检测类型、清洗格式、处理图片
#     → 发布到 content/{posts|share|reports}/
#     → git commit + push
#
set -euo pipefail

UPLOAD_ID="${1:-}"
if [ -z "$UPLOAD_ID" ]; then
    echo '{"content_type":"","target_path":"","error":"missing upload_id"}' >&2
    exit 1
fi

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SOURCE_DIR="$PROJECT_ROOT/source/$UPLOAD_ID"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROMPT_FILE="$SCRIPT_DIR/process_upload_prompt.txt"

if [ ! -d "$SOURCE_DIR" ]; then
    echo "{\"content_type\":\"\",\"target_path\":\"\",\"error\":\"source dir not found: $SOURCE_DIR\"}" >&2
    exit 1
fi

echo "[process_upload] 源目录: $SOURCE_DIR"
echo "[process_upload] 文件列表:"
ls -la "$SOURCE_DIR"

# ============================================================
# 调用 Claude CLI（非交互模式）
# ============================================================
# --print / -p : 非交互，输出到 stdout
# --system-prompt : 注入处理规则（新版 CLI 已移除 --system-prompt-file，改用此参数）
# --add-dir= : 允许访问的目录（必须用 = 号，否则可变参数会吞掉后续 prompt）
# --allowedTools : 限制可用工具
# ============================================================
# 注意：
#   1. prompt 必须放在最前面，避免被 --add-dir 等可变参数吞掉
#   2. --add-dir 用 = 号传值，明确参数边界
# ============================================================

PROMPT_TEXT="处理 source/$UPLOAD_ID/ 目录下的新上传文件，按照 system prompt 中的规则发布到 content/ 对应位置。最后输出一行 JSON 包含 content_type 和 target_path。"

claude -p "$PROMPT_TEXT" \
    --system-prompt "$(cat "$PROMPT_FILE")" \
    --add-dir="$PROJECT_ROOT/source" \
    --add-dir="$PROJECT_ROOT/content" \
    --add-dir="$PROJECT_ROOT/site/public/images" \
    --allowedTools "Bash,Read,Write,Edit" \
    2>&1

# Claude CLI 输出通过 stdout 返回给 Python
exit $?
