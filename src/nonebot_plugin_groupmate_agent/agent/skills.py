from __future__ import annotations

import inspect
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from langchain.tools import tool
from nonebot.log import logger

from .optional_tools.types import AgentSkill, OptionalToolContext


@dataclass
class AgentSkillToolSetup:
    skills: list[AgentSkill]
    tools: list[Any]
    base_tools: list[Any]
    tools_by_skill: dict[str, list[Any]]


def normalize_agent_skills(skills: Iterable[AgentSkill]) -> list[AgentSkill]:
    """Validate and de-duplicate skills while preserving declaration order."""

    normalized: list[AgentSkill] = []
    skill_indexes: dict[str, int] = {}
    for skill in skills:
        name = str(skill.name or "").strip()
        description = str(skill.description or "").strip()
        if not name or not description:
            logger.warning("跳过 AgentSkill：name 和 description 不能为空")
            continue
        tool_names = tuple(dict.fromkeys(str(item).strip() for item in skill.tool_names if str(item).strip()))
        if name in skill_indexes:
            index = skill_indexes[name]
            existing = normalized[index]
            merged_tool_names = tuple(dict.fromkeys((*existing.tool_names, *tool_names)))
            normalized[index] = AgentSkill(
                name=existing.name,
                description=existing.description,
                prompt=existing.prompt,
                tool_names=merged_tool_names,
            )
            logger.warning(f"合并重复 AgentSkill 的工具映射，保留首个 description/prompt: {name}")
            continue
        skill_indexes[name] = len(normalized)
        normalized.append(
            AgentSkill(
                name=name,
                description=description,
                prompt=skill.prompt,
                tool_names=tool_names,
            )
        )
    return normalized


def build_agent_skill_index(skills: Iterable[AgentSkill]) -> str:
    normalized = normalize_agent_skills(skills)
    if not normalized:
        return ""

    lines = [f"- {skill.name}: {skill.description}" for skill in normalized]
    return (
        "【可按需读取的技能】\n"
        "下面只列出技能索引。当前任务明显需要某项技能时，先调用 `load_agent_skill` 读取完整规则；"
        "不要预先读取无关技能。\n"
        + "\n".join(lines)
    )


def prepare_agent_skill_tools(tools: Iterable[Any], skills: Iterable[AgentSkill]) -> AgentSkillToolSetup:
    """Split tools into always-visible and skill-gated groups."""

    normalized_skills = normalize_agent_skills(skills)
    tool_names_in_order: list[str] = []
    tool_by_name: dict[str, Any] = {}
    for tool_item in tools:
        tool_name = str(getattr(tool_item, "name", None) or "").strip()
        if not tool_name:
            logger.warning(f"跳过没有 name 的 Agent 工具: {tool_item!r}")
            continue
        if tool_name not in tool_by_name:
            tool_names_in_order.append(tool_name)
        else:
            logger.warning(f"Agent 工具名重复，后加载的工具会覆盖前者: {tool_name}")
        tool_by_name[tool_name] = tool_item

    normalized_tools = [tool_by_name[tool_name] for tool_name in tool_names_in_order]
    tools_by_skill: dict[str, list[Any]] = {skill.name: [] for skill in normalized_skills}
    lazy_tool_names: set[str] = set()
    for skill in normalized_skills:
        for tool_name in skill.tool_names:
            tool_item = tool_by_name.get(tool_name)
            if tool_item is None:
                logger.warning(f"AgentSkill `{skill.name}` 引用了不存在的工具: {tool_name}")
                continue
            tools_by_skill[skill.name].append(tool_item)
            lazy_tool_names.add(tool_name)

    return AgentSkillToolSetup(
        skills=normalized_skills,
        tools=normalized_tools,
        base_tools=[tool_item for tool_item in normalized_tools if tool_item.name not in lazy_tool_names],
        tools_by_skill=tools_by_skill,
    )


async def resolve_agent_skill_prompt(skill: AgentSkill, ctx: OptionalToolContext) -> str:
    prompt: Any = skill.prompt
    if callable(prompt):
        prompt = prompt(ctx)
    if inspect.isawaitable(prompt):
        prompt = await prompt
    return str(prompt or "").strip()


def create_agent_skill_loader_tool(
    skills: Iterable[AgentSkill],
    ctx: OptionalToolContext,
):
    skill_map = {skill.name: skill for skill in normalize_agent_skills(skills)}
    if not skill_map:
        return None

    @tool("load_agent_skill")
    async def load_agent_skill(skill_name: str) -> str:
        """按名称读取一项技能的完整规则，并启用该技能关联的工具。"""

        normalized_name = str(skill_name or "").strip()
        skill = skill_map.get(normalized_name)
        if skill is None:
            return f"未找到技能 {normalized_name!r}。可用技能: {', '.join(skill_map)}"

        prompt = await resolve_agent_skill_prompt(skill, ctx)
        if not prompt:
            return f"技能 `{normalized_name}` 没有额外规则；其关联工具现已启用。"
        return prompt

    return load_agent_skill
