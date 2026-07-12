from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

from nonebot.log import logger

from .types import AgentSkill, OptionalToolBundle, OptionalToolContext, ToolLimitSpec


@dataclass(frozen=True)
class AgentToolContext:
    session_id: str
    request_id: str | None
    user_id: str | None
    user_name: str | None
    interface: Any
    bot_id: str | None
    history: list[Any]
    direct_targets: list[dict[str, Any]]
    emoji_like_candidate_ids: set[str]
    has_direct_targets: bool
    is_multi_direct_reply: bool
    is_cross_user_direct_reply: bool
    has_admin_permission: bool
    config: Any
    model: Any
    stop_words: list[str]
    recent_forward_messages: list[dict[str, Any]] = field(default_factory=list)
    db_session: Any | None = None
    send_target: Any | None = None
    is_private: bool = False
    detach_request: Callable[[str], None] | None = None
    can_continue: Callable[[], Awaitable[bool]] | None = None
    mark_sent: Callable[[], None] | None = None
    clear_detached: Callable[[], None] | None = None
    create_detached_task: Callable[[Any, str], Any] | None = None
    bot: Any | None = None
    event: Any | None = None


@dataclass(frozen=True)
class AgentToolBundle:
    tools: Iterable[Any] = field(default_factory=tuple)
    instructions: Iterable[str] = field(default_factory=tuple)
    skills: Iterable[AgentSkill] = field(default_factory=tuple)
    name: str | None = None
    tool_limits: Iterable[ToolLimitSpec] = field(default_factory=tuple)


AgentToolResult = Any | Iterable[Any] | AgentToolBundle | OptionalToolBundle


AgentToolFactory = Callable[
    [AgentToolContext],
    AgentToolResult | Awaitable[AgentToolResult],
]

_registered_agent_tool_factories: list[AgentToolFactory] = []


def register_agent_tool(factory: AgentToolFactory | None = None):
    """Register a factory that returns one or more LangChain tools for groupmate-agent."""

    def decorator(func: AgentToolFactory) -> AgentToolFactory:
        _registered_agent_tool_factories.append(func)
        return func

    if factory is None:
        return decorator
    return decorator(factory)


def clear_registered_agent_tools() -> None:
    _registered_agent_tool_factories.clear()


def _tool_name(tool_item: Any) -> str:
    return str(
        getattr(tool_item, "name", None)
        or getattr(tool_item, "__name__", None)
        or type(tool_item).__name__
    )


def _factory_name(factory: AgentToolFactory) -> str:
    return str(getattr(factory, "__name__", None) or getattr(factory, "__qualname__", None) or type(factory).__name__)


def _source_name(factory: AgentToolFactory) -> str:
    module = getattr(factory, "__module__", "")
    name = str(getattr(factory, "__qualname__", None) or _factory_name(factory))
    return f"registered:{module}.{name}" if module else f"registered:{name}"


def _make_agent_tool_context(ctx: OptionalToolContext) -> AgentToolContext:
    return AgentToolContext(
        db_session=ctx.db_session,
        session_id=ctx.session_id,
        request_id=ctx.request_id,
        user_id=ctx.user_id,
        user_name=ctx.user_name,
        interface=ctx.interface,
        bot_id=ctx.bot_id,
        history=ctx.history,
        direct_targets=ctx.direct_targets,
        emoji_like_candidate_ids=ctx.emoji_like_candidate_ids,
        has_direct_targets=ctx.has_direct_targets,
        is_multi_direct_reply=ctx.is_multi_direct_reply,
        is_cross_user_direct_reply=ctx.is_cross_user_direct_reply,
        has_admin_permission=ctx.has_admin_permission,
        config=ctx.config,
        model=ctx.model,
        stop_words=ctx.stop_words,
        recent_forward_messages=ctx.recent_forward_messages,
        detach_request=ctx.detach_request,
        can_continue=ctx.can_continue,
        mark_sent=ctx.mark_sent,
        clear_detached=ctx.clear_detached,
        create_detached_task=ctx.create_detached_task,
        send_target=ctx.send_target,
        is_private=ctx.is_private,
        bot=ctx.bot,
        event=ctx.event,
    )


def _adapt_registered_skill(skill: AgentSkill) -> AgentSkill:
    prompt = skill.prompt
    if not callable(prompt):
        return skill

    async def adapted_prompt(ctx: OptionalToolContext) -> str:
        result = prompt(_make_agent_tool_context(ctx))
        if inspect.isawaitable(result):
            result = await result
        return str(result or "")

    return AgentSkill(
        name=skill.name,
        description=skill.description,
        prompt=adapted_prompt,
        tool_names=skill.tool_names,
    )


def _normalize_tool_result(result: Any, *, fallback_name: str) -> OptionalToolBundle:
    if result is None:
        return OptionalToolBundle(name=fallback_name)
    if isinstance(result, OptionalToolBundle):
        return result
    if isinstance(result, AgentToolBundle):
        return OptionalToolBundle(
            name=result.name or fallback_name,
            tools=[tool_item for tool_item in result.tools if tool_item is not None],
            prompt="\n".join(str(item).strip() for item in result.instructions if item and str(item).strip()),
            skills=[_adapt_registered_skill(skill) for skill in result.skills if skill is not None],
            tool_limits=list(result.tool_limits),
        )
    if hasattr(result, "name") and (hasattr(result, "invoke") or hasattr(result, "ainvoke")):
        return OptionalToolBundle(name=fallback_name, tools=[result])
    if isinstance(result, (str, bytes)):
        return OptionalToolBundle(name=fallback_name, tools=[result])
    if isinstance(result, Iterable):
        return OptionalToolBundle(
            name=fallback_name,
            tools=[tool_item for tool_item in result if tool_item is not None],
        )
    return OptionalToolBundle(name=fallback_name, tools=[result])


async def build_registered_agent_tool_bundles(ctx: OptionalToolContext) -> list[OptionalToolBundle]:
    bundles: list[OptionalToolBundle] = []
    agent_ctx = _make_agent_tool_context(ctx)

    for factory in list(_registered_agent_tool_factories):
        name = _factory_name(factory)
        try:
            result = factory(agent_ctx)
            if inspect.isawaitable(result):
                result = await result
            bundle = _normalize_tool_result(result, fallback_name=name)
        except Exception:
            logger.exception(f"加载注册 Agent 工具失败: {_source_name(factory)}")
            continue

        if bundle.tools or bundle.prompt or bundle.skills or bundle.tool_limits:
            bundles.append(bundle)

    return bundles


def iter_registered_agent_tool_factories() -> list[AgentToolFactory]:
    return list(_registered_agent_tool_factories)


async def inspect_registered_agent_tool_factory(
    factory: AgentToolFactory,
    ctx: OptionalToolContext,
) -> tuple[OptionalToolBundle | None, str]:
    try:
        result = factory(_make_agent_tool_context(ctx))
        if inspect.isawaitable(result):
            result = await result
        bundle = _normalize_tool_result(result, fallback_name=_factory_name(factory))
    except Exception as e:
        logger.exception(f"加载注册 Agent 工具失败: {_source_name(factory)}")
        return None, f"{type(e).__name__}: {e}"

    if not (bundle.tools or bundle.prompt or bundle.skills or bundle.tool_limits):
        return None, "empty bundle"
    return bundle, ""


__all__ = [
    "AgentToolBundle",
    "AgentToolContext",
    "AgentToolFactory",
    "build_registered_agent_tool_bundles",
    "clear_registered_agent_tools",
    "inspect_registered_agent_tool_factory",
    "iter_registered_agent_tool_factories",
    "register_agent_tool",
]
