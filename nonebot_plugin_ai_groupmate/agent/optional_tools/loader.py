import inspect
from typing import Any

from nonebot.log import logger

from . import calculator, emoji_like, moderation, report, voice, web_search
from .types import OptionalToolBundle, OptionalToolContext

OPTIONAL_TOOL_MODULES = [
    web_search,
    report,
    emoji_like,
    voice,
    moderation,
    calculator,
]


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def load_optional_tool_bundles(ctx: OptionalToolContext) -> list[OptionalToolBundle]:
    bundles: list[OptionalToolBundle] = []

    for module in OPTIONAL_TOOL_MODULES:
        name = module.__name__.rsplit(".", 1)[-1]
        healthcheck = getattr(module, "healthcheck", None)
        if healthcheck is not None:
            ok, reason = await _maybe_await(healthcheck(ctx))
            if not ok:
                logger.info(f"跳过可选 Agent 工具 {name}: {reason}")
                continue

        builder = getattr(module, "build", None)
        if builder is None:
            logger.warning(f"可选 Agent 工具模块缺少 build(): {module.__name__}")
            continue

        bundle = await _maybe_await(builder(ctx))
        if bundle.tools or bundle.prompt or bundle.tool_limits:
            bundles.append(bundle)

    return bundles
