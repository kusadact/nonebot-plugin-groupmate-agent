import importlib.util
import inspect
import re
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

from nonebot import require
from nonebot.log import logger

from . import (
    calculator,
    emoji_like,
    moderation,
    private_message,
    qq_avatar,
    qq_avatar_describer,
    scheduled_tasks,
    web_search,
)
from .registry import (
    build_registered_agent_tool_bundles,
    inspect_registered_agent_tool_factory,
    iter_registered_agent_tool_factories,
)
from .types import OptionalToolBundle, OptionalToolContext, OptionalToolStatus

BUILTIN_TOOL_MODULES = [
    web_search,
    scheduled_tasks,
    emoji_like,
    moderation,
    private_message,
    qq_avatar,
    qq_avatar_describer,
    calculator,
]


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def get_user_tools_dir() -> Path:
    require("nonebot_plugin_localstore")
    import nonebot_plugin_localstore as store

    tools_dir = store.get_data_dir("nonebot_plugin_groupmate_agent") / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    return tools_dir


def _module_display_name(module: ModuleType) -> str:
    tool_name = getattr(module, "__groupmate_agent_tool_name__", None)
    if tool_name:
        return str(tool_name)
    return module.__name__.rsplit(".", 1)[-1]


def _safe_module_name(name: str) -> str:
    return re.sub(r"\W+", "_", name).strip("_") or "tool"


def _iter_user_tool_paths(tools_dir: Path) -> list[Path]:
    if not tools_dir.exists():
        return []

    tool_paths: list[Path] = []
    for entry in sorted(tools_dir.iterdir(), key=lambda item: item.name):
        if entry.name.startswith(("_", ".")):
            continue
        if entry.is_file() and entry.suffix == ".py":
            tool_paths.append(entry)
        elif entry.is_dir() and (entry / "__init__.py").is_file():
            tool_paths.append(entry / "__init__.py")
    return tool_paths


def _load_user_tool_module_result(path: Path) -> tuple[ModuleType | None, str]:
    tool_name = path.parent.name if path.name == "__init__.py" else path.stem
    module_name = f"_groupmate_agent_user_tool_{_safe_module_name(tool_name)}"
    search_locations = [str(path.parent)] if path.name == "__init__.py" else None
    spec = importlib.util.spec_from_file_location(module_name, path, submodule_search_locations=search_locations)
    if spec is None or spec.loader is None:
        logger.warning(f"跳过用户 Agent 工具 {path}: 无法创建模块 spec")
        return None, "invalid module spec"

    for loaded_name in list(sys.modules):
        if loaded_name == module_name or loaded_name.startswith(f"{module_name}."):
            sys.modules.pop(loaded_name, None)

    module = importlib.util.module_from_spec(spec)
    module.__groupmate_agent_tool_name__ = tool_name
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        sys.modules.pop(module_name, None)
        logger.exception(f"加载用户 Agent 工具失败: {path}")
        return None, f"{type(e).__name__}: {e}"
    return module, ""


def _load_user_tool_module(path: Path) -> ModuleType | None:
    module, _ = _load_user_tool_module_result(path)
    return module


def _load_user_tool_modules() -> list[ModuleType]:
    tools_dir = get_user_tools_dir()
    modules: list[ModuleType] = []
    for path in _iter_user_tool_paths(tools_dir):
        module = _load_user_tool_module(path)
        if module is not None:
            modules.append(module)
    return modules


def _tool_name(tool_item: Any) -> str:
    return str(
        getattr(tool_item, "name", None)
        or getattr(tool_item, "__name__", None)
        or type(tool_item).__name__
    )


def _factory_source(factory: Any) -> str:
    module = getattr(factory, "__module__", "")
    name = str(getattr(factory, "__qualname__", None) or getattr(factory, "__name__", None) or type(factory).__name__)
    return f"registered:{module}.{name}" if module else f"registered:{name}"


async def _build_optional_tool_bundle(
    module: ModuleType,
    ctx: OptionalToolContext,
    *,
    source: str,
) -> OptionalToolBundle | None:
    name = _module_display_name(module)
    try:
        healthcheck = getattr(module, "healthcheck", None)
        if healthcheck is not None:
            ok, reason = await _maybe_await(healthcheck(ctx))
            if not ok:
                logger.info(f"跳过可选 Agent 工具 {name}: {reason}")
                return None

        builder = getattr(module, "build", None)
        if builder is None:
            logger.warning(f"可选 Agent 工具模块缺少 build(): {source}")
            return None

        bundle = await _maybe_await(builder(ctx))
    except Exception:
        logger.exception(f"加载可选 Agent 工具失败: {source}")
        return None

    if not isinstance(bundle, OptionalToolBundle):
        logger.warning(f"可选 Agent 工具 build() 返回值不是 OptionalToolBundle: {source}")
        return None
    if not (bundle.tools or bundle.prompt or bundle.tool_limits):
        return None
    return bundle


async def _inspect_optional_tool_module(
    module: ModuleType,
    ctx: OptionalToolContext,
    *,
    source: str,
) -> tuple[OptionalToolStatus, OptionalToolBundle | None]:
    name = _module_display_name(module)
    try:
        healthcheck = getattr(module, "healthcheck", None)
        if healthcheck is not None:
            ok, reason = await _maybe_await(healthcheck(ctx))
            if not ok:
                return OptionalToolStatus(name=name, source=source, enabled=False, reason=str(reason)), None

        builder = getattr(module, "build", None)
        if builder is None:
            return OptionalToolStatus(name=name, source=source, enabled=False, reason="missing build()"), None

        bundle = await _maybe_await(builder(ctx))
    except Exception as e:
        logger.exception(f"加载可选 Agent 工具失败: {source}")
        return OptionalToolStatus(name=name, source=source, enabled=False, reason=f"{type(e).__name__}: {e}"), None

    if not isinstance(bundle, OptionalToolBundle):
        return OptionalToolStatus(
            name=name,
            source=source,
            enabled=False,
            reason="build() did not return OptionalToolBundle",
        ), None
    if not (bundle.tools or bundle.prompt or bundle.tool_limits):
        return OptionalToolStatus(name=bundle.name or name, source=source, enabled=False, reason="empty bundle"), None

    return (
        OptionalToolStatus(
            name=bundle.name or name,
            source=source,
            enabled=True,
            tool_names=[_tool_name(tool_item) for tool_item in bundle.tools],
        ),
        bundle,
    )


async def load_optional_tool_bundles(ctx: OptionalToolContext) -> list[OptionalToolBundle]:
    bundles: list[OptionalToolBundle] = []

    for module in BUILTIN_TOOL_MODULES:
        bundle = await _build_optional_tool_bundle(module, ctx, source=module.__name__)
        if bundle is not None:
            bundles.append(bundle)

    for module in _load_user_tool_modules():
        bundle = await _build_optional_tool_bundle(
            module,
            ctx,
            source=getattr(module, "__file__", module.__name__),
        )
        if bundle is not None:
            bundles.append(bundle)

    bundles.extend(await build_registered_agent_tool_bundles(ctx))

    return bundles


async def list_optional_tool_statuses(ctx: OptionalToolContext) -> list[OptionalToolStatus]:
    statuses: list[OptionalToolStatus] = []

    for module in BUILTIN_TOOL_MODULES:
        status, _ = await _inspect_optional_tool_module(module, ctx, source="builtin")
        statuses.append(status)

    for path in _iter_user_tool_paths(get_user_tools_dir()):
        module, error = _load_user_tool_module_result(path)
        if module is None:
            tool_name = path.parent.name if path.name == "__init__.py" else path.stem
            statuses.append(
                OptionalToolStatus(
                    name=tool_name,
                    source=str(path),
                    enabled=False,
                    reason=error or "import failed",
                )
            )
            continue
        status, _ = await _inspect_optional_tool_module(
            module,
            ctx,
            source=getattr(module, "__file__", module.__name__),
        )
        statuses.append(status)

    for factory in iter_registered_agent_tool_factories():
        source = _factory_source(factory)
        bundle, reason = await inspect_registered_agent_tool_factory(factory, ctx)
        if bundle is None:
            name = source.removeprefix("registered:")
            statuses.append(OptionalToolStatus(name=name, source=source, enabled=False, reason=reason))
            continue
        statuses.append(
            OptionalToolStatus(
                name=bundle.name,
                source=source,
                enabled=True,
                tool_names=[_tool_name(tool_item) for tool_item in bundle.tools],
            )
        )

    return statuses
