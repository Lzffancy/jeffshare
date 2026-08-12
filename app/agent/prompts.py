"""LLM Prompt 模板 — AI 会话总结工作流"""

# ── Step 1: 内容分类 ──────────────────────────────────────────
CLASSIFY_PROMPT = """你是一个内容分析助手。分析以下 AI 对话内容，判定其类型和主题。

对话内容：
{conversation}

请以 JSON 格式返回（不要包含其他内容）：
{{
  "category": "tech" | "product" | "research" | "misc",
  "title_hint": "简短的主题关键词，用于生成标题"
}}

分类标准：
- tech: 技术实现、编程、架构、工具使用
- product: 产品设计、用户体验、功能规划
- research: 学术研究、文献分析、方法论
- misc: 其他或无法明确归类"""

# ── Step 2: 提取结论 ──────────────────────────────────────────
EXTRACT_PROMPT = """你是一个知识提取助手。从以下 AI 对话中提取关键信息。

对话分类：{category}
对话主题：{title_hint}

对话内容：
{conversation}

请提取并返回 JSON（不要包含其他内容）：
{{
  "key_points": ["核心观点1", "核心观点2", ...],  // 3-5 条最重要的结论或知识
  "decisions": ["决策1", ...],                     // 对话中做出的明确决定（可能为空数组）
  "action_items": ["行动项1", ...],                 // 待办或后续行动（可能为空数组）
  "tags": ["标签1", "标签2", ...]                  // 3-5 个标签，用于文章分类
}}"""

# ── Step 3: 生成 Markdown ─────────────────────────────────────
GENERATE_MD_PROMPT = """你是一个技术博客编辑。根据以下结构化信息，生成一篇完整的博客文章（Markdown 格式）。

标题建议：{title_hint}
分类：{category}
标签：{tags}

关键结论：
{key_points}

决策记录：
{decisions}

后续行动：
{action_items}

原始对话（供参考）：
{conversation}

要求：
1. 标题简洁有力，20 字以内
2. 正文结构清晰，包含：
   - 一句话摘要
   - 背景/问题
   - 核心讨论内容（分小节）
   - 结论/要点总结
3. 在文末附上标签
4. 不要包含任何对话中的人名或头像
5. 语言自然流畅，像真人写的博客

请以 JSON 格式返回（不要包含其他内容）：
{{
  "title": "文章标题",
  "slug": "english-slug",
  "summary": "一句话摘要",
  "markdown": "完整的 Markdown 正文（不包含 frontmatter）"
}}
"""
