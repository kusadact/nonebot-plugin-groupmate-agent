import asyncio
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

from langchain.tools import tool

from tests.helpers import install_package_stub, load_module

install_package_stub("groupmate_agent_tool_pkg")
install_package_stub("groupmate_agent_tool_pkg.agent")
install_package_stub("groupmate_agent_tool_pkg.agent.optional_tools")
types = load_module("groupmate_agent_tool_pkg.agent.optional_tools.types", "agent/optional_tools/types.py")
registry = load_module(
    "groupmate_agent_tool_pkg.agent.optional_tools.registry",
    "agent/optional_tools/registry.py",
)
STUB_TOOL_MODULE_NAMES = (
    "calculator",
    "emoji_like",
    "moderation",
    "qq_avatar",
    "qq_avatar_describer",
    "scheduled_tasks",
    "web_search",
)
for name in STUB_TOOL_MODULE_NAMES:
    module = ModuleType(f"groupmate_agent_tool_pkg.agent.optional_tools.{name}")

    async def _empty_build(ctx, _name=name):
        return types.OptionalToolBundle(name=_name)

    module.build = _empty_build
    if name == "web_search":

        async def _disabled_healthcheck(ctx):
            return False, "disabled in test"

        module.healthcheck = _disabled_healthcheck

    sys.modules[module.__name__] = module
loader = load_module(
    "groupmate_agent_tool_pkg.agent.optional_tools.loader",
    "agent/optional_tools/loader.py",
)
calculator = load_module(
    "groupmate_agent_tool_pkg.agent.optional_tools.calculator",
    "agent/optional_tools/calculator.py",
)


def make_ctx():
    return types.OptionalToolContext(
        db_session=SimpleNamespace(name="db"),
        session_id="group-1",
        request_id="req-1",
        user_id="user-1",
        user_name="Alice",
        interface=SimpleNamespace(name="interface"),
        bot_id="bot-1",
        history=[],
        direct_targets=[],
        emoji_like_candidate_ids=set(),
        has_direct_targets=False,
        is_multi_direct_reply=False,
        is_cross_user_direct_reply=False,
        has_admin_permission=False,
        config=SimpleNamespace(),
        model=SimpleNamespace(name="model"),
        stop_words=[],
        send_target=SimpleNamespace(id="group-1"),
        is_private=False,
        bot=SimpleNamespace(name="bot"),
        event=SimpleNamespace(name="event"),
    )


def test_calculator_tool_returns_integer_float_and_error_results():
    bundle = asyncio.run(calculator.build(None))
    assert isinstance(bundle, types.OptionalToolBundle)
    assert bundle.name == "calculator"

    tool = bundle.tools[0]
    assert tool.name == "calculate_expression"
    assert tool.invoke({"expression": "2 + 3 * 4"}) == "14"
    assert tool.invoke({"expression": "1 / 4"}) == "计算结果是：0.2500000000"
    assert tool.invoke({"expression": "unknown_name + 1"}).startswith("计算失败。请检查表达式是否正确")


def test_registered_agent_tool_bundle_is_converted_to_optional_bundle():
    registry.clear_registered_agent_tools()

    @registry.register_agent_tool
    def build_registered_tools(ctx):
        @tool("get_registered_session_id")
        async def get_registered_session_id() -> str:
            """获取当前会话 ID。"""
            return ctx.session_id

        return registry.AgentToolBundle(
            name="registered_demo",
            tools=[get_registered_session_id],
            instructions=["- 需要会话 ID 时调用 `get_registered_session_id`"],
            tool_limits=[types.ToolLimitSpec(tool_name="get_registered_session_id", run_limit=1)],
        )

    bundles = asyncio.run(registry.build_registered_agent_tool_bundles(make_ctx()))

    assert len(bundles) == 1
    bundle = bundles[0]
    assert isinstance(bundle, types.OptionalToolBundle)
    assert bundle.name == "registered_demo"
    assert bundle.prompt == "- 需要会话 ID 时调用 `get_registered_session_id`"
    assert bundle.tool_limits == [types.ToolLimitSpec(tool_name="get_registered_session_id", run_limit=1)]
    assert bundle.tools[0].name == "get_registered_session_id"

    registry.clear_registered_agent_tools()


def test_registered_agent_tool_accepts_single_tool_return():
    registry.clear_registered_agent_tools()

    @tool("echo_registered")
    async def echo_registered(text: str) -> str:
        """回显输入。"""
        return text

    @registry.register_agent_tool
    async def build_single_tool(ctx):
        return echo_registered

    bundles = asyncio.run(registry.build_registered_agent_tool_bundles(make_ctx()))

    assert len(bundles) == 1
    assert bundles[0].name == "build_single_tool"
    assert bundles[0].tools == [echo_registered]

    registry.clear_registered_agent_tools()


def test_registered_agent_tool_context_includes_recent_forward_messages():
    ctx = make_ctx()
    ctx.recent_forward_messages = [{"message_id": "101", "forward_id": "fwd-1"}]

    agent_ctx = registry._make_agent_tool_context(ctx)

    assert agent_ctx.recent_forward_messages == [{"message_id": "101", "forward_id": "fwd-1"}]


def test_loader_includes_registered_tools_in_statuses():
    registry.clear_registered_agent_tools()
    loader.get_user_tools_dir = lambda: Path("/__groupmate_agent_no_user_tools__")

    @registry.register_agent_tool
    def build_status_tool(ctx):
        @tool("status_tool")
        async def status_tool() -> str:
            """测试状态工具。"""
            return "ok"

        return registry.AgentToolBundle(name="status_bundle", tools=[status_tool])

    statuses = asyncio.run(loader.list_optional_tool_statuses(make_ctx()))
    status = next(item for item in statuses if item.name == "status_bundle")

    assert status.enabled is True
    assert status.source.startswith("registered:")
    assert status.tool_names == ["status_tool"]

    registry.clear_registered_agent_tools()
