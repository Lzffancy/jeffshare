"""种子数据 — 首次启动时写入 Agent 默认配置

运行时机：FastAPI app 启动事件中调用 seed_all()
幂等：已存在同名 Agent 定义则跳过
"""
from __future__ import annotations

import json
import logging

from .db import get_conn
from .models import (
    AgentDefinition,
    AgentVersionConfig,
    AgentStepConfig,
    StepType,
    WorkflowType,
    ConfigStatus,
)

logger = logging.getLogger("jeff-api")

# ── 会话总结 Agent 默认配置 ──────────────────────────────────────


CONVERSATION_SUMMARIZER_STEPS = [
    AgentStepConfig(
        order=1,
        name="内容分类",
        type=StepType.LLM_CALL,
        prompt_template=(
            "你是一个内容分析助手。分析以下 AI 对话内容，判定其类型和主题。\n\n"
            "对话内容：\n{conversation}\n\n"
            '请以 JSON 格式返回（不要包含其他内容）：\n'
            '{{\n'
            '  "category": "tech" | "product" | "research" | "misc",\n'
            '  "title_hint": "简短的主题关键词，用于生成标题"\n'
            '}}\n\n'
            "分类标准：\n"
            "- tech: 技术实现、编程、架构、工具使用\n"
            "- product: 产品设计、用户体验、功能规划\n"
            "- research: 学术研究、文献分析、方法论\n"
            "- misc: 其他或无法明确归类"
        ),
        prompt_params=["conversation"],
        output_key="classify_result",
        output_schema={"category": "string", "title_hint": "string"},
    ),
    AgentStepConfig(
        order=2,
        name="提取结论",
        type=StepType.LLM_CALL,
        prompt_template=(
            "你是一个知识提取助手。从以下 AI 对话中提取关键信息。\n\n"
            "对话分类：{classify_result}\n\n"
            "对话内容：\n{conversation}\n\n"
            '请提取并返回 JSON（不要包含其他内容）：\n'
            '{{\n'
            '  "title": "简洁的博客标题，20字以内",\n'
            '  "slug": "english-slug",\n'
            '  "summary": "一句话摘要",\n'
            '  "key_points": ["核心观点1", "核心观点2", ...],\n'
            '  "decisions": ["决策1", ...],\n'
            '  "action_items": ["行动项1", ...],\n'
            '  "tags": ["标签1", "标签2", ...],\n'
            '  "markdown": "完整的 Markdown 正文（结构化博客文章）"\n'
            '}}'
        ),
        prompt_params=["conversation", "classify_result"],
        output_key="extract_result",
        model_params_override={"temperature": 0.2},
    ),
    AgentStepConfig(
        order=3,
        name="组装 Markdown",
        type=StepType.TRANSFORM,
        prompt_params=[],
        output_key="final_markdown",
        transform_func="assemble_markdown",
    ),
]


def ensure_agent(
    name: str,
    display_name: str,
    description: str,
    workflow_type: str,
    agent_class: str,
    model: str,
    model_params: dict,
    steps: list[AgentStepConfig],
    changelog: str = "初始版本",
) -> None:
    """幂等写入：Agent 定义 + active v1 版本。"""
    conn = get_conn()

    # 检查 Agent 定义是否存在
    row = conn.execute("SELECT id FROM agent_definitions WHERE name = ?", (name,)).fetchone()

    if row is None:
        conn.execute(
            """INSERT INTO agent_definitions (name, display_name, description, workflow_type, agent_class)
               VALUES (?, ?, ?, ?, ?)""",
            (name, display_name, description, workflow_type, agent_class),
        )
        conn.commit()
        agent_row = conn.execute("SELECT id FROM agent_definitions WHERE name = ?", (name,)).fetchone()
        agent_id = agent_row["id"]
        logger.info(f"seed: 创建 Agent 定义 — {name}")
    else:
        agent_id = row["id"]

    # 检查是否已有版本
    existing = conn.execute(
        "SELECT COUNT(*) as cnt FROM agent_versions WHERE agent_id = ?", (agent_id,)
    ).fetchone()
    if existing and existing["cnt"] > 0:
        logger.info(f"seed: Agent '{name}' 已有版本，跳过种子数据")
        return

    steps_json = json.dumps([s.model_dump(exclude_none=True) for s in steps], ensure_ascii=False)
    params_json = json.dumps(model_params, ensure_ascii=False)

    conn.execute(
        """INSERT INTO agent_versions (agent_id, version, status, model, model_params, steps, changelog)
           VALUES (?, 1, 'active', ?, ?, ?, ?)""",
        (agent_id, model, params_json, steps_json, changelog),
    )
    conn.commit()
    logger.info(f"seed: 创建 Agent '{name}' v1 (active)")


def seed_all():
    """写入所有 Agent 的种子数据。"""
    steps = CONVERSATION_SUMMARIZER_STEPS
    ensure_agent(
        name="conversation-summarizer",
        display_name="AI 会话总结",
        description="将 AI 对话沉淀为结构化博客草稿",
        workflow_type=WorkflowType.LINEAR_CHAIN.value,
        agent_class="SummarizeAgent",
        model="gpt-4o-mini",
        model_params={"temperature": 0.3, "max_tokens": 2048, "top_p": 1.0},
        steps=steps,
        changelog="初始版本：三步串行（内容分类 → 提取结论 → 组装 Markdown），LangGraph 驱动",
    )
    logger.info("seed: 全部完成")
